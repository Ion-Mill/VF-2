"""9월 CSV ↔ DB 적재 대조 + 10/1 실시간 중계 상태 점검 (읽기만, 2026-10-24).

생성기 out/(9월)·masters/ CSV의 줄 수와 DB 표의 줄 수를 표마다 맞춰 보고, 10/1 08:00 뒤 DB에 들어온 줄(중계)을 센다.
DB에는 아무것도 쓰지 않는다 (읽기 전용 거래, 기본은 읽기 계정 MOM_READONLY_DATABASE_URL).

쓰는 법 (11_automotive 에서, 백엔드 가상환경):
    node scripts/py.mjs tools/check_sept_live.py                    # backend/.env.supabase 의 공용 DB
    node scripts/py.mjs tools/check_sept_live.py --env .env          # 로컬 Docker DB
    node scripts/py.mjs tools/check_sept_live.py --app               # 읽기 계정에 권한 없는 표가 있으면 앱 계정으로
    node scripts/py.mjs tools/check_sept_live.py --no-sensor         # 센서 CSV(약 98만 줄) 세기를 건너뜀
(--env-file 이 아니라 --env 다. Node 24가 --env-file 을 자기 옵션으로 가져간다 — scripts/py.mjs 머리말)

결과 끝 "판정": 9월 표가 모두 같으면 9월 적재 OK, 10/1 줄이 0이면 중계가 아직 돈 적 없음(또는 [처음으로]로 지워짐).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent.parent          # backend
ROOT = HERE.parent                                      # 11_automotive

# 표마다 "10/1 시연 시작 전" 조건 (frontend/tools/server_past.py PAST_WHERE + 생산·설비 표). %(c)s = 시작 시각, %(d)s = 시작 날짜
PAST = {
    "work_day": "work_date < %(d)s",
    "shift": "start_at < %(c)s",
    "shift_report": "shift_id IN (SELECT shift_id FROM shift WHERE start_at < %(c)s)",
    "daily_report": "work_date < %(d)s",
    "production_order": "created_at < %(c)s",
    "production_lot": "input_shift_id IN (SELECT shift_id FROM shift WHERE start_at < %(c)s)",
    "raw_material_lot": "received_date < %(d)s",
    "operation_report": "start_at < %(c)s",
    "equipment_state_log": "start_at < %(c)s",
    "alarm_event": "occurred_at < %(c)s",
    "bottleneck_log": "changed_at < %(c)s",
    "wip_log": "logged_at < %(c)s",
    "sensor_sample": "sampled_at < %(c)s",
    "tool_change": "changed_at < %(c)s",
    "tool_usage": "recorded_at < %(c)s",
    "inspection_plan": "lot_no IN (SELECT l.lot_no FROM production_lot l JOIN shift s ON s.shift_id = l.input_shift_id WHERE s.start_at < %(c)s)",
    "inspection_result": "measured_at < %(c)s",
    "cmm_import": "received_at < %(c)s",
    "defect_record": "found_at < %(c)s",
    "lot_hold": "held_at < %(c)s",
    "pm_record": "(done_at < %(c)s OR (done_at IS NULL AND due_date < %(d)s))",
    "maintenance_work_order": "created_at < %(c)s",
    "work_order_step": "wo_no IN (SELECT wo_no FROM maintenance_work_order WHERE created_at < %(c)s)",
    "work_order_part": "wo_no IN (SELECT wo_no FROM maintenance_work_order WHERE created_at < %(c)s)",
    "work_record": "start_at < %(c)s",
    "work_record_check": "record_no IN (SELECT record_no FROM work_record WHERE start_at < %(c)s)",
    "work_record_part": "record_no IN (SELECT record_no FROM work_record WHERE start_at < %(c)s)",
    "inventory_txn": "txn_at < %(c)s",
    "shipment": "shipped_at < %(c)s",
    "shipment_line": "shipment_no IN (SELECT shipment_no FROM shipment WHERE shipped_at < %(c)s)",
    "notification": "raised_at < %(c)s",
    "notification_recipient": "notification_id IN (SELECT notification_id FROM notification WHERE raised_at < %(c)s)",
    "document_revision": "created_at < %(c)s",
    "document_revision_change": "revision_id IN (SELECT revision_id FROM document_revision WHERE created_at < %(c)s)",
}
# 시연 서버 → DB 중계가 넣는 10/1 표 17개 (생성기 Realtime.tables()) + DB가 그 줄로 만드는 것 2개
LIVE = ["production_order", "production_lot", "inspection_plan", "alarm_event", "pm_record", "equipment_state_log",
        "operation_report", "tool_change", "tool_usage", "bottleneck_log", "wip_log", "lot_hold", "cmm_import",
        "inspection_result", "defect_record", "inventory_txn", "sensor_sample", "notification", "maintenance_work_order"]
LAST_AT = {"alarm_event": "occurred_at", "operation_report": "end_at", "equipment_state_log": "start_at",
           "wip_log": "logged_at", "sensor_sample": "sampled_at", "notification": "raised_at"}
# 시뮬레이터가 이어 붙일 번호 (생성기 gen/realtime.py ID_TABLES) — 9월 마지막 번호 = out/manifest.json rows
# CSV보다 DB 줄이 많아도 되는 기준 정보 (DB 시드가 더함)
EXTRA_OK = {"notification_rule": "DB 시드(db/seed/30_notification_rules.sql)가 규칙을 더함 — 2026-10-20부터 29개"}
ID_TABLES = ("equipment_state_log", "operation_report", "bottleneck_log", "alarm_event", "tool_change", "inspection_result",
             "cmm_import", "defect_record", "pm_record", "inventory_txn", "lot_hold")


def read_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def fmt(v) -> str:
    if isinstance(v, datetime):
        return (v.astimezone(KST) if v.tzinfo else v).strftime("%Y-%m-%d %H:%M")
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def csv_info(path: Path) -> tuple[list[str], int]:
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        head = next(r, [])
        return head, sum(1 for _ in r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default=".env.supabase", help="backend/ 안 환경 파일 (기본 .env.supabase)")
    ap.add_argument("--gen", default=str(ROOT / "생성기"), help="생성기 폴더")
    ap.add_argument("--app", action="store_true", help="읽기 계정 대신 앱 계정(MOM_DATABASE_URL) — 그래도 읽기만 한다")
    ap.add_argument("--no-sensor", action="store_true", help="센서 CSV 세기 건너뜀")
    a = ap.parse_args()

    try:
        import psycopg
    except ImportError:
        print("psycopg 없음 — 백엔드 가상환경으로 돌린다 (node scripts/py.mjs tools/check_sept_live.py)")
        return 2
    env = read_env(HERE / a.env)
    key = "MOM_DATABASE_URL" if a.app else "MOM_READONLY_DATABASE_URL"
    url = env.get(key, "").replace("postgresql+psycopg://", "postgresql://")
    if not url:
        print(f"backend/{a.env} 에 {key} 가 없음")
        return 2
    gen = Path(a.gen)
    cfg = json.loads((gen / "config.json").read_text(encoding="utf-8"))
    start = datetime.fromisoformat(cfg["realtime"]["start"])
    cutoff = start if start.tzinfo else start.replace(tzinfo=KST)
    arg = {"c": cutoff, "d": cutoff.date()}
    manifest = json.loads((gen / "out" / "manifest.json").read_text(encoding="utf-8"))

    host = url.split("@")[-1].split("/")[0]
    print(f"DB = {host} ({key}), 기준 시각 = {cutoff.isoformat()}, 생성기 out/ = {manifest.get('created_at')} seed {manifest.get('seed')}")

    con = psycopg.connect(url, connect_timeout=10, autocommit=True)
    con.execute("SET default_transaction_read_only = on")
    con.execute("SET statement_timeout = '180s'")

    def one(sql, params=None):
        try:
            return con.execute(sql, params or {}).fetchone(), None
        except Exception as e:                          # 권한 없음·표 없음 — 그 표만 건너뜀
            return None, f"{type(e).__name__}: {str(e).splitlines()[0][:90]}"

    bad, notes = [], []

    # 1) 기준 정보
    print("\n[1] 기준 정보 (masters/*.csv 줄 수 = DB 줄 수)")
    print(f"  {'표':28s} {'CSV':>8s} {'DB':>8s}  결과")
    for p in sorted((gen / cfg["run"]["masters_dir"]).glob("*.csv")):
        t = p.stem
        _, n = csv_info(p)
        row, err = one(f'SELECT count(*) FROM "{t}"')
        if err:
            print(f"  {t:28s} {n:>8d} {'-':>8s}  못 읽음 ({err})"); notes.append(t); continue
        ok = row[0] == n
        extra = not ok and row[0] > n and t in EXTRA_OK
        print(f"  {t:28s} {n:>8d} {row[0]:>8d}  {'같음' if ok else ('같음 + ' + EXTRA_OK[t]) if extra else '다름'}")
        if not ok and not extra:
            bad.append(f"masters/{t}")

    # 2) 9월 기록
    print("\n[2] 9월 기록 (out/*.csv 줄 수 = DB의 10/1 08:00 전 줄 수)")
    print(f"  {'표':28s} {'CSV':>8s} {'DB 9월':>8s} {'DB 10/1~':>9s}  결과")
    live_rows = {}
    for p in sorted((gen / cfg["run"]["out_dir"]).glob("*.csv")):
        t = p.stem
        if t == "sensor_sample" and a.no_sensor:
            n = None
        else:
            _, n = csv_info(p)
        where = PAST.get(t)
        if not where:
            print(f"  {t:28s} {n if n is not None else '-':>8}  (기준 조건 없음 — 이 스크립트에 추가 필요)"); notes.append(t); continue
        row, err = one(f'SELECT count(*) FILTER (WHERE {where}), count(*) FILTER (WHERE ({where}) IS NOT TRUE) FROM "{t}"', arg)
        if err:
            print(f"  {t:28s} {n if n is not None else '-':>8}  못 읽음 ({err})"); notes.append(t); continue
        past, live = row
        live_rows[t] = live
        ok = n is None or past == n
        print(f"  {t:28s} {n if n is not None else '-':>8} {past:>8d} {live:>9d}  {'같음' if ok else '다름'}")
        if not ok:
            bad.append(f"out/{t}")

    # 2-1) 값 합계 몇 가지 (줄 수만 같고 값이 다른 경우를 잡는다)
    print("\n[2-1] 값 합계 (operation_report 투입·양품, 9월)")
    s_pq = s_gq = 0
    with io.open(gen / "out" / "operation_report.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            s_pq += int(float(r["pq"] or 0)); s_gq += int(float(r["gq"] or 0))
    row, err = one(f"SELECT coalesce(sum(pq),0), coalesce(sum(gq),0) FROM operation_report WHERE {PAST['operation_report']}", arg)
    if err:
        print(f"  못 읽음 ({err})")
    else:
        ok = (int(row[0]), int(row[1])) == (s_pq, s_gq)
        print(f"  CSV pq {s_pq} gq {s_gq} / DB pq {int(row[0])} gq {int(row[1])} → {'같음' if ok else '다름'}")
        if not ok:
            bad.append("operation_report 합계")

    # 3) 중계 기준점: 9월 마지막 번호 = manifest rows (시뮬레이터가 그다음 번호부터 씀)
    print("\n[3] 9월 마지막 번호 (시뮬레이터 시작점 = out/manifest.json rows)")
    for t in ID_TABLES:
        head, _ = csv_info(gen / "out" / f"{t}.csv")
        idc = head[0]
        row, err = one(f'SELECT coalesce(max("{idc}"), 0) FROM "{t}" WHERE {PAST[t]}', arg)
        want = manifest["rows"].get(t)
        if err:
            print(f"  {t:24s} 못 읽음 ({err})"); continue
        ok = int(row[0]) == int(want)
        print(f"  {t:24s} {idc:20s} DB {int(row[0]):>8d}  manifest {want:>8}  {'같음' if ok else '다름'}")
        if not ok:
            bad.append(f"번호 {t}")

    # 4) 10/1 실시간 (중계)
    print("\n[4] 10/1 08:00 뒤 DB 줄 (시연 서버 → 백엔드 /api/ingest/sync 중계)")
    total_live = 0
    for t in LIVE:
        n = live_rows.get(t)
        if n is None:
            continue
        total_live += n
        last = ""
        if t in LAST_AT and n:
            row, err = one(f'SELECT max("{LAST_AT[t]}") FROM "{t}"')
            if row and row[0]:
                last = f"  마지막 {row[0].astimezone(KST):%m-%d %H:%M}"
        print(f"  {t:28s} {n:>8d}{last}")
    for label, sql in (("DB 시계 app_now()", "SELECT app_now()"),
                       ("sim_clock", "SELECT mode, sim_anchor, speed, is_paused, updated_at FROM sim_clock"),
                       ("dataset_info", "SELECT seed, period_from, period_to, loaded_at, left(config_sha256, 12) FROM dataset_info"),
                       ("시연 기준점", "SELECT * FROM demo_snapshot.meta LIMIT 1")):
        row, err = one(sql)
        print(f"  {label:18s} {err or ', '.join(fmt(v) for v in row) if row else err or '(없음)'}")
    want_sha = manifest.get("config_sha256", "")[:12]
    print(f"  (생성기 out/manifest config_sha256 앞 12자 = {want_sha})")

    # 판정
    print("\n[판정]")
    print("  9월 적재: " + ("OK — CSV와 DB가 표마다 같음" if not bad else "다름 → " + ", ".join(bad)))
    if notes:
        print("  못 읽은 표(권한·없음): " + ", ".join(notes) + "  → --app 으로 다시")
    print("  10/1 실시간: " + (f"DB에 10/1 줄 {total_live}개 (중계가 돈 흔적)" if total_live else
                              "10/1 줄 0개 — 중계가 아직 안 켜졌거나 [처음으로]로 지워진 상태 (frontend/README.md '10/1 기록을 DB에도 넣기')"))
    con.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
