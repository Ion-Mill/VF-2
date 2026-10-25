"""생성기 결과 CSV를 DB에 넣는다 (논리 ERD 11.1, docs/04_데이터적재_약속.md).

쓰는 법 (생성기 폴더 = VF-2/11_automotive/생성기):
    python tools/load_generated.py <생성기 폴더> --psql "psql -d mom"                # 기준 정보 22 + 9월 33 (센서 빼고)
    python tools/load_generated.py <생성기 폴더> --psql "psql -d mom" --sensor-only  # 센서만 따로 (9월 약 98만 행)
    python tools/load_generated.py <생성기 폴더> --psql "psql -d mom" --realtime     # + 10/1 리허설 기록 (out_realtime)
    --dry-run      칼럼 확인·넣는 순서·SQL만 보여 주고 넣지 않음
    --keep-going   (진단용) 테이블마다 따로 넣고 실패한 테이블을 모두 알려 줌

하는 일:
 1. <폴더>/masters/*.csv (기준 정보), <폴더>/out/*.csv (9월)와 out/manifest.json(rows) 을 읽는다.
 2. 머리 줄 = 논리 ERD 5장 속성 (이름으로 맞춤). CSV에 있는데 DB에 없는 칼럼이 있거나(아래 IGNORE 빼고), DB의 필수
    칼럼(기본값 없음)이 CSV에 없으면(아래 DERIVED 빼고) 멈춘다 (종료 코드 2). 물리 추가 칼럼은 DB 기본값·생성 칼럼이 채운다.
 3. 외래 키 순서로 한 트랜잭션 안에서 넣는다. 기준 정보는 "있으면 고치고 없으면 넣기"(시드가 이미 넣은 role·
    notification_rule — 물리 추가 칸은 그대로 둠), 운영 기록은 그대로 넣는다. app.loading = on (알림 NOTIFY·자동 알림 끔),
    순환 FK는 커밋 때 확인. CHECK·FK·고유·겹침 금지·역할 트리거는 그대로 걸린다 — 규칙을 어긴 데이터는 들어가지 않는다.
 4. 일련번호 시퀀스·업무 번호 카운터를 맞추고, 알람 ↔ 관련 재고 품목, 시연 기준점(fn_demo_snapshot — SIM-03이
    되돌아갈 실시간 시작 상태), dataset_info(manifest)를 남긴다.
 5. 줄 수가 manifest rows와 같은지 확인한다 (다르면 종료 코드 3).
날짜 (2026-10-25): 기록 기간·실시간 시작은 manifest의 profile(final|video)로 생성기 profiles/<이름>.json에서 읽는다
  (최종용 10/1~10/25·10/26 09:00, 영상용 10/1~10/23·10/24 09:00). profile이 없는 옛 out/ 은 9/1~9/30·10/1 08:00.
  시연 기준점 시각 = 실시간 시작 = 시연 서버 시뮬레이터 시작점(Realtime.baseline) — DB 중계 [처음으로]가 이 둘을 비교한다.
--realtime: 실시간 기록(out_realtime*)을 과거 번호 다음부터 붙인다 (작업지시·로트는 덮어씀, ERD 11.1).
  시연 기준점은 과거 기록 끝(실시간 시작)에서 만들므로, SIM-03(처음으로)을 누르면 실시간 기록이 사라진다.
  단 실시간 날짜의 근무일·교대(work_day·shift)는 기록이 아니라 달력이라 기준점 전에 넣는다 — 되돌린 뒤 시뮬레이터가 다시
  보내는 실시간 기록이 그 교대를 가리킨다.
표준 라이브러리 + psql만 쓴다.
"""
import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
import tempfile

EXCLUDE_ALWAYS = {("inventory_item", "on_hand_qty")}   # 거래(inventory_txn) 트리거가 채운다
SENSOR = "sensor_sample"
CALENDAR = ("work_day", "shift")      # 실시간 날짜의 근무일·교대 — 기준점 전에 넣는 달력 (머리 설명 --realtime)

# CSV에 있지만 DB가 계산으로 보이는 칼럼 (논리 ERD "계산" 속성 — 넣지 않고, 넣은 뒤 같은지 확인)
IGNORE = {
    ("maintenance_work_order", "trigger_kind"):
        "SELECT count(*) FROM _ld_maintenance_work_order t JOIN v_work_order v USING (wo_no) "
        "WHERE NOT (string_to_array(t.trigger_kind, '|') <@ v.trigger_kind::text[] "
        "AND v.trigger_kind::text[] <@ string_to_array(t.trigger_kind, '|'))",
}
# DB에는 저장하지만 생성기는 "계산"이라 비워 둔 칼럼 → 넣을 때 DB가 계산 (그 재료 테이블을 먼저 넣는다)
DERIVED = {
    "shift_report": {
        "availability_pct": "(SELECT coalesce(jsonb_object_agg(k.equipment_id, k.availability_pct), '{}'::jsonb) "
                            "FROM v_shift_equipment_kpi k WHERE k.shift_id = t.shift_id AND k.process_code = 'OP-30')",
    },
    # 관리자 메모 (2026-10-20): 생성기는 issues_summary 끝에 "관리자 메모: …"를 붙여 둔다 → 떼어 memo 칸으로 (fn_split_memo)
    "daily_report": {"memo": "(fn_split_memo(t.issues_summary))[2]"},
}
# CSV 값을 바꿔 넣는 칼럼 (위 DERIVED와 짝)
TRANSFORM = {("daily_report", "issues_summary"): "(fn_split_memo(t.issues_summary))[1]"}

COLS_SQL = """
SELECT c.table_name, c.column_name,
       (c.is_generated = 'ALWAYS') AS gen,
       (c.is_nullable = 'YES' OR c.column_default IS NOT NULL OR c.is_identity = 'YES') AS optional,
       CASE WHEN c.is_nullable = 'NO' AND c.is_identity = 'NO' THEN coalesce(c.column_default, '') ELSE '' END AS not_null_default
  FROM information_schema.columns c JOIN information_schema.tables t USING (table_schema, table_name)
 WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE' ORDER BY c.table_name, c.ordinal_position;"""
FK_SQL = """
SELECT DISTINCT conrelid::regclass::text, confrelid::regclass::text, condeferrable
  FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace;"""
PK_SQL = """
SELECT c.conrelid::regclass::text, a.attname
  FROM pg_constraint c JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, n) ON true
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
 WHERE c.contype = 'p' AND c.connamespace = 'public'::regnamespace ORDER BY 1, k.n;"""
IDENTITY_SQL = """
SELECT table_name, column_name FROM information_schema.columns
 WHERE table_schema = 'public' AND is_identity = 'YES';"""


def psql_rows(psql, sql):
    out = subprocess.run(shlex.split(psql) + ["-X", "-AtF", "\t", "-c", sql], check=True, capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    return [line.split("\t") for line in out.splitlines() if line]


def load_order(tables, fks):
    deps = {t: set() for t in tables}
    for child, parent, deferrable in fks:
        if child in deps and parent in deps and child != parent and deferrable != "t":
            deps[child].add(parent)
    order, done = [], set()
    while deps:
        ready = sorted(t for t, d in deps.items() if d <= done)
        if not ready:
            raise SystemExit(f"외래 키 순서를 정할 수 없음 (순환): {sorted(deps)}")
        for t in ready:
            order.append(t)
            done.add(t)
            del deps[t]
    # DB가 계산해 채우는 칼럼이 있는 테이블은 재료(다른 기록)가 다 들어간 뒤에
    return [t for t in order if t not in DERIVED] + [t for t in order if t in DERIVED]


def demo_dates(gen_dir, manifest):
    """(기록 시작일, 기록 끝일, 실시간 시작 'YYYY-MM-DDTHH:MM') — manifest의 profile로 생성기 프로필 파일에서 (위 머리 설명)"""
    prof = manifest.get("profile")
    if not prof:
        return "2026-09-01", "2026-09-30", "2026-10-01T08:00"
    cfg = json.load(open(os.path.join(gen_dir, "profiles", f"{prof}.json"), encoding="utf-8"))
    return cfg["period"]["start_date"], cfg["period"]["end_date"], cfg["realtime"]["start"]


def read_manifest(folder):
    p = os.path.join(folder, "manifest.json")
    if not os.path.exists(p):
        return {}, {}
    m = json.load(open(p, encoding="utf-8"))
    if isinstance(m.get("rows"), dict):          # 생성기 형식 (2026-10-13~)
        return m, {k: int(v) for k, v in m["rows"].items()}
    if isinstance(m.get("files"), list):         # 옛 약속 형식
        return m, {f["table"]: int(f["rows"]) for f in m["files"] if isinstance(f.get("rows"), int)}
    return m, {}


def csv_files(folder, include_sensor, only_sensor=False):
    out = {}
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".csv"):
            continue
        t = name[:-4]
        if only_sensor and t != SENSOR:
            continue
        if t == SENSOR and not include_sensor:
            continue
        out[t] = os.path.abspath(os.path.join(folder, name))
    return out


def header(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh))


def check_columns(files, cols, errors, label, upsert):
    for t, path in files.items():
        if t not in cols:
            errors.append(f"[{label}] {t}: DB에 없는 테이블")
            continue
        hdr = header(path)
        insertable = {c for c, gen, _opt in cols[t] if not gen and (t, c) not in EXCLUDE_ALWAYS}
        extra = [h for h in hdr if h not in insertable and (t, h) not in IGNORE]
        # 있으면 고치기(upsert)는 시드가 이미 넣은 행의 물리 추가 칸을 그대로 두므로 필수 확인은 새 행이 생길 때 DB가 한다
        required = [] if upsert else [c for c, gen, opt in cols[t]
                                      if not gen and not opt and c not in hdr and c not in DERIVED.get(t, {})]
        if extra or required:
            errors.append(f"[{label}] {t}: CSV에만 있음 {extra} / DB 필수인데 CSV에 없음 {required}")


# psql은 생성기 폴더(BASE_DIR)에서 돌리고 CSV는 그 안의 상대 경로(masters/x.csv)로 넘긴다.
# Windows psql은 \\copy 파일 경로의 한글(예: 11_automotive/생성기)을 읽지 못한다 (2026-10-15 Supabase 적재에서 확인).
# 파일 이름은 영문(표 이름)이라 상대 경로면 한글이 끼지 않는다.
BASE_DIR = None


def copy_cmd(table, cols, path):
    rel = os.path.relpath(path, BASE_DIR).replace(os.sep, "/") if BASE_DIR else path
    return (f"\\copy {table} ({', '.join(cols)}) FROM '{rel}' "
            f"WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')")


def table_lines(t, path, upsert, pk, checks, defaults, tmp=None):
    """테이블 1개를 넣는 SQL 줄들.
    빈칸(NULL)인데 DB는 NOT NULL + 기본값인 칼럼(예: production_lot.scrap_qty 빈칸 = 0)은 기본값으로 넣는다 (ERD 필수 "—")"""
    hdr = header(path)
    if upsert and not all(k in hdr for k in pk):
        upsert = False            # PK 칸이 CSV에 없으면(기본값 칸) 덮어쓸 기준이 없다 → 그냥 넣기 (10/1 tool_usage 등은 새 행)
    ignored = [h for h in hdr if (t, h) in IGNORE]
    derived = DERIVED.get(t, {})
    cols = [h for h in hdr if h not in ignored]
    dflt = {c: defaults[(t, c)] for c in cols if defaults.get((t, c))}
    if not upsert and not ignored and not derived and not dflt:
        return [copy_cmd(t, cols, path)]
    tmp = tmp or f"_ld_{t}"
    lines = [f"CREATE TEMP TABLE {tmp} ON COMMIT DROP AS SELECT {', '.join(cols)} FROM {t} WITH NO DATA;"]
    lines += [f"ALTER TABLE {tmp} ADD COLUMN {c} text;" for c in ignored]
    lines.append(copy_cmd(tmp, hdr, path))
    for c in ignored:
        checks.append((f"{t}.{c} (CSV) = DB 계산 값", IGNORE[(t, c)]))
    dcols = [c for c in derived if c not in cols]
    ins_cols = cols + dcols
    ins_vals = [TRANSFORM[(t, c)] if (t, c) in TRANSFORM else f"coalesce(t.{c}, {dflt[c]})" if c in dflt else f"t.{c}"
                for c in cols] + [derived[c] for c in dcols]
    if upsert:
        setc = [c for c in cols if c not in pk]
        on = " AND ".join(f"x.{k} = t.{k}" for k in pk)
        if setc:
            lines.append(f"UPDATE {t} x SET " + ", ".join(f"{c} = coalesce(t.{c}, {dflt[c]})" if c in dflt else f"{c} = t.{c}"
                                                          for c in setc) + f" FROM {tmp} t WHERE {on};")
        lines.append(f"INSERT INTO {t} ({', '.join(ins_cols)}) SELECT {', '.join(ins_vals)} FROM {tmp} t "
                     f"WHERE NOT EXISTS (SELECT 1 FROM {t} x WHERE {on});")
    else:
        lines.append(f"INSERT INTO {t} ({', '.join(ins_cols)}) SELECT {', '.join(ins_vals)} FROM {tmp} t;")
    return lines


def build(files, is_upsert, pks, fks, checks, defaults):
    order = load_order(list(files), fks)
    return order, [(t, table_lines(t, files[t], is_upsert(t), pks.get(t, []), checks, defaults)) for t in order]


def run_script(psql, lines):
    # SQL 파일 경로에 한글이 있으면(Windows 사용자 이름 등) psql이 못 연다 → 그때만 생성기 폴더에 잠깐 둔다
    tmpdir = None if tempfile.gettempdir().isascii() else BASE_DIR
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8", dir=tmpdir) as tf:
        tf.write("\n".join(lines) + "\n")
    arg = os.path.basename(tf.name) if tmpdir else tf.name
    try:
        return subprocess.run(shlex.split(psql) + ["-X", "-q", "-f", arg], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=BASE_DIR)
    finally:
        os.unlink(tf.name)


def check_lines(checks):
    """적재 트랜잭션 안에서 계산 칼럼 비교 — 다르면 멈춘다"""
    out = []
    for label, sql in checks:
        safe = label.replace("'", "''")
        out.append(f"DO $$ DECLARE n bigint; BEGIN EXECUTE $q${sql}$q$ INTO n; "
                   f"IF n > 0 THEN RAISE EXCEPTION '계산 칼럼이 다름: {safe} — %줄', n; END IF; END $$;")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gen_dir", help="생성기 폴더 (masters/, out/, out_realtime/ 가 있는 곳)")
    ap.add_argument("--psql", default="psql -d mom")
    ap.add_argument("--realtime", action="store_true", help="10/1 리허설 기록(out_realtime)도 넣음")
    ap.add_argument("--sensor", action="store_true", help="센서 CSV도 같이 넣음 (기본은 뺌 — --sensor-only로 따로)")
    ap.add_argument("--sensor-only", action="store_true", help="센서 CSV만 넣음 (9월, --realtime이면 10/1도)")
    ap.add_argument("--out-dir", default="out_final", help="과거 기록 폴더 이름 (기본 out_final — 2026-10-25 10월 데이터로). out_video | 옛 9월 out")
    ap.add_argument("--rt-dir", default="out_realtime_final", help="실시간 기록 폴더 이름 (기본 out_realtime_final — 2026-10-25). out_realtime_video")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-going", action="store_true", help="진단용: 테이블마다 따로 넣고 실패를 모두 보고")
    a = ap.parse_args()
    global BASE_DIR
    BASE_DIR = os.path.abspath(a.gen_dir)

    masters_dir = os.path.join(a.gen_dir, "masters")
    out_dir = os.path.join(a.gen_dir, a.out_dir)
    rt_dir = os.path.join(a.gen_dir, a.rt_dir)
    manifest, rows = read_manifest(out_dir)
    rt_manifest, rt_rows = read_manifest(rt_dir) if a.realtime else ({}, {})

    cols, defaults = {}, {}
    for row in psql_rows(a.psql, COLS_SQL):
        t, c, gen, opt = row[:4]
        cols.setdefault(t, []).append((c, gen == "t", opt == "t"))
        if len(row) > 4 and row[4]:
            defaults[(t, c)] = row[4]
    pks = {}
    for t, c in psql_rows(a.psql, PK_SQL):
        pks.setdefault(t, []).append(c)
    fks = psql_rows(a.psql, FK_SQL)

    if a.sensor_only:
        masters = {}
        past = csv_files(out_dir, True, only_sensor=True)
        rt = csv_files(rt_dir, True, only_sensor=True) if a.realtime else {}
    else:
        masters = csv_files(masters_dir, False)
        past = csv_files(out_dir, a.sensor)
        rt = csv_files(rt_dir, a.sensor) if a.realtime else {}
    if not masters and not past and not rt:
        sys.exit(f"넣을 CSV가 없음: {a.gen_dir}")

    errors = []
    check_columns(masters, cols, errors, "masters", upsert=True)
    check_columns(past, cols, errors, "out", upsert=False)
    check_columns(rt, cols, errors, "out_realtime", upsert=True)
    both = set(masters) & set(past)
    if both:
        errors.append(f"masters와 out에 같은 테이블: {sorted(both)}")
    if errors:
        print("칼럼 약속 위반 (논리 ERD 5장·11.1):\n  " + "\n  ".join(errors))
        sys.exit(2)

    checks1, checks2 = [], []
    files1 = {**masters, **past}
    order1, steps1 = build(files1, lambda t: t in masters, pks, fks, checks1, defaults)
    # 실시간 날짜의 근무일·교대는 기준점 전에 (머리 설명 --realtime). 있으면 고치고 없으면 넣기
    cal = {t: rt.pop(t) for t in CALENDAR if t in rt}
    steps_cal = [(t, table_lines(t, cal[t], True, pks.get(t, []), checks1, defaults, tmp=f"_ld_rt_{t}")) for t in CALENDAR if t in cal]
    steps1 = steps1 + steps_cal
    p_from, p_to, rt_start = demo_dates(a.gen_dir, manifest)
    print(f"기록 기간 {p_from} ~ {p_to}, 시연 기준점(실시간 시작) {rt_start}")
    order2, steps2 = build(rt, lambda t: True, pks, fks, checks2, defaults) if rt else ([], [])
    print("넣는 순서:", " → ".join(order1))
    if order2:
        print("10/1 넣는 순서:", " → ".join(order2))

    head = ["\\set ON_ERROR_STOP 1", "BEGIN;", "SET LOCAL app.loading = 'on';", "SET CONSTRAINTS ALL DEFERRED;"]
    identity = psql_rows(a.psql, IDENTITY_SQL)

    def setvals(tables):
        return [f"SELECT setval(pg_get_serial_sequence('{t}', '{c}'), coalesce((SELECT max({c}) FROM {t}), 0) + 1, false);"
                for t, c in identity if t in tables]

    if a.keep_going:
        fails = []
        for t, lines in steps1 + steps2:
            r = run_script(a.psql, head + lines + ["COMMIT;"])
            if r.returncode != 0:
                fails.append(f"{t}:\n      " + "\n      ".join(r.stderr.strip().splitlines()[:6]))
                print(f"  FAIL {t}")
            else:
                print(f"  ok   {t}")
        print(f"\n실패 {len(fails)}개" + ("" if not fails else ":\n  " + "\n  ".join(fails)))
        sys.exit(1 if fails else 0)

    meta = json.dumps({"past": manifest, "realtime": rt_manifest or None}, ensure_ascii=False).replace("'", "''")
    after1 = ["\\o " + os.devnull] + setvals(files1)
    if not a.sensor_only:
        after1 += ["SELECT count(*) FROM fn_sync_doc_numbers();",
                   "SELECT fn_sync_after_load();",   # 공구 누적 등 "지금 상태" 칸 (masters = 9/1 시작 상태)
                   f"SELECT fn_ensure_work_day(DATE '{rt_start[:10]}');",   # 시연 날 근무일·교대 (실시간 기록에 있으면 그대로)
                   "SELECT fn_seed_alarm_related_items();",
                   # SIM-03(시연 데이터 처음으로)이 돌아갈 곳 = 과거 기록 끝 = 실시간 시작 (시계는 SIM으로 멈춤)
                   f"SELECT fn_sim_set('SIM', '{rt_start.replace('T', ' ')}+09', 60, true);",
                   "SELECT fn_demo_snapshot();",
                   f"""UPDATE dataset_info SET seed = {int(manifest.get('seed') or 0) or 'NULL'},
                       config_sha256 = {("'" + manifest['config_sha256'] + "'") if manifest.get('config_sha256') else 'NULL'},
                       period_from = DATE '{p_from}', period_to = DATE '{p_to}',
                       loaded_at = now(), manifest = '{meta}'::jsonb WHERE id = 1;"""]
    after1 += ["\\o"]
    scripts = [head + [l for _, ls in steps1 for l in ls] + check_lines(checks1) + after1 + ["COMMIT;"]]
    if steps2:
        scripts.append(head + [l for _, ls in steps2 for l in ls] + check_lines(checks2) + ["\\o " + os.devnull]
                       + setvals(rt) + ([] if a.sensor_only else ["SELECT count(*) FROM fn_sync_doc_numbers();",
                                                                   "SELECT fn_sync_after_load();"])
                       + ["\\o", "COMMIT;"])

    if a.dry_run:
        for s in scripts:
            print("\n".join(s))
        return
    for i, s in enumerate(scripts, 1):
        r = run_script(a.psql, s)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            sys.exit(f"적재 실패 ({i}단계) — 이 단계는 하나도 넣지 않음 (트랜잭션 되돌림)")

    bad = []
    expect = dict(rows)
    for t, n in rt_rows.items():
        if t in rt and all(k in header(rt[t]) for k in pks.get(t, [])):
            expect[t] = max(expect.get(t, 0), n)   # 덮어쓰기(작업지시·로트·검사 방식 — 9월 끝 로트가 이어짐)라 합이 아님
        else:
            expect[t] = expect.get(t, 0) + n
    loaded = set(files1) | set(rt)
    for t, n in expect.items():
        if t not in loaded:
            continue
        got = int(psql_rows(a.psql, f"SELECT count(*) FROM {t}")[0][0])
        if got < n:
            bad.append(f"{t}: manifest {n}줄, DB {got}줄")
    if bad:
        print("줄 수가 다름:\n  " + "\n  ".join(bad))
        sys.exit(3)
    print(f"적재 완료: 테이블 {len(loaded)}개")


if __name__ == "__main__":
    main()
