"""이브(AI 비서) 답이 공용 DB·시연 서버 값과 맞는지 데이터 종류별로 본다 (2026-10-25, 배포_안내.md 10장).

서버에서:  cd ~/VF-2/11_automotive/deploy && docker compose exec -T backend python - < 이브_답변_점검.py
  - 정답은 돌릴 때마다 공용 DB에서 다시 뽑는다 (시연 시계가 흐르면 정답도 바뀐다). 뽑는 길은 이브가 쓰는 백엔드 조회 도구
    (app/assistant/tools.py)와 같은 읽기 전용 연결이다 — 공용 DB에 쓰지 않는다.
  - 질문은 U12(공장 관리자)로 /api/assistant/chat에 보낸다: 화면과 같은 길(백엔드 → 비서 → Claude). 질문마다 외부 Claude 요금이
    조금 들고, 질문·답이 공용 DB chat_log에 U12 기록으로 남는다(사용자가 묻는 것과 같다).
  - 판정: 정답의 숫자·이름이 답 글자 안에 있으면 "맞음", 없으면 "확인 필요"(말을 바꿔 썼을 수 있으니 사람이 본다).
  - 환경 변수: DRY=1 이면 정답만 뽑고 묻지 않는다. ONLY=1,4,7 이면 그 번호만.
답이 어느 길로 갔는지는 이어서 이브 컨테이너에서 이브_답변_출처.py.
"""
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.assistant import tools
from app.config import get_settings
from app.db import Db, readonly_engine
from app.domain.tokens import create_token

STATE_KO = {"RUN": ("가공", "가동"), "IDLE": ("대기",), "DOWN": ("고장", "정지"), "SETUP": ("준비",),
            "MAINT": ("정비",), "BLOCKED": ("막힘",)}
ONLY = {int(x) for x in os.environ.get("ONLY", "").split(",") if x.strip().isdigit()}
DRY = os.environ.get("DRY") == "1"


def nums(x) -> list[str]:
    """답에서 찾을 숫자 글자 후보 (18.8 → 18.8·19, 100.0 → 100)"""
    if x is None:
        return []
    v = float(x)
    out = {f"{v:g}", f"{v:.1f}".rstrip("0").rstrip(".")}
    if abs(v - round(v)) < 1e-9 or abs(v) >= 100:
        out.add(str(int(round(v))))
    return sorted(out)


def kday(d: date) -> str:
    return f"{d.month}월 {d.day}일"


def iso(d: date) -> str:
    return datetime(d.year, d.month, d.day).isoformat() + "+09:00"


def gather(db: Db) -> tuple[datetime, list[dict]]:
    """질문과 정답 — 각 항목: q(질문), truth(사람이 읽을 정답), must(답에 있어야 할 글자 묶음: 묶음마다 후보 중 하나)"""
    now = db.scalar("common.now")
    today = now.date()
    yday = today - timedelta(days=1)
    run = lambda name, **a: tools.run(db, name, a)  # noqa: E731

    def sql(q, **p):
        try:
            with db.conn.begin_nested():   # 저장점 — 못 읽어도 뒤 조회가 막히지 않게
                return [dict(r) for r in db.conn.execute(text(q), p).mappings()]
        except Exception:  # noqa: BLE001 — 읽기 전용 계정이 못 읽는 표면 정답을 비운다
            return []

    def alarm_n(a: str, b: str, code: str | None = None) -> tuple[int, int]:
        """(알람 표에서 직접 센 건수, 백엔드 알람 조회 도구 합계). 정답은 앞 값 — 도구가 알람 1건을 상태 기록 2행에 걸쳐
        두 번 세는 경우가 있다(#187 메모). 두 값이 다르면 정답 줄에 함께 적는다"""
        q = "SELECT count(*) AS n FROM alarm_event WHERE occurred_at >= CAST(:a AS timestamptz) AND occurred_at < CAST(:b AS timestamptz)"
        p = {"a": a, "b": b}
        if code:
            q, p = q + " AND alarm_code = :c", {**p, "c": code}
        tool_n = sum(r["times"] for r in run("alarms", **{"from": a, "to": b}) if not code or r["alarm_code"] == code)
        direct = sql(q, **p)
        return (int(direct[0]["n"]) if direct else tool_n), tool_n

    def alarm_truth(label: str, n: tuple[int, int]) -> str:
        return f"{label} {n[0]}건" + (f" (알람 조회 도구는 {n[1]}건 — 두 번 세는 문제)" if n[0] != n[1] else "")

    # 실적이 있는 가장 최근 날 (날짜를 콕 집어 묻는 질문용)
    prod = run("production", from_date=str(today - timedelta(days=10)), to_date=str(yday))
    work_days = sorted({r["shift_id"][:10] for r in prod if (r["actual_qty"] or 0) > 0})
    wd = date.fromisoformat(work_days[-1]) if work_days else yday
    alarms_7 = run("alarms", **{"from": iso(today - timedelta(days=7)), "to": iso(today)})
    top_code = max(alarms_7, key=lambda r: r["times"])["alarm_code"] if alarms_7 else "2075"

    cases = []

    eq = run("equipment_status")
    cases.append({"q": "지금 설비 상태 알려줘", "kind": "시연 서버·설비",
                  "truth": ", ".join(f"{r['equipment_id']} {r['state_code']}" for r in eq),
                  "must": [[r["equipment_id"]] for r in eq]})
    v2 = next((r for r in eq if r["equipment_id"] == "VF2-02"), None)
    if v2:
        cases.append({"q": "VF2-02 상태 어때?", "kind": "시연 서버·설비",
                      "truth": f"VF2-02 {v2['state_code']} {v2['state_since']}부터 {float(v2['state_minutes']):g}분",
                      "must": [["VF2-02"], list(STATE_KO.get(v2["state_code"], (v2["state_code"],)))]})
    bn = sql("SELECT new_process_code, changed_at, cause_code FROM bottleneck_log ORDER BY changed_at DESC LIMIT 1")
    cases.append({"q": "병목 어디야?", "kind": "시연 서버·병목",
                  "truth": f"{bn[0]['new_process_code']} ({bn[0]['changed_at']}부터, {bn[0]['cause_code']})" if bn else "모름(표 권한 없음)",
                  "must": [[bn[0]["new_process_code"]]] if bn else []})

    y_prod = [r for r in prod if r["shift_id"].startswith(str(yday))]
    y_sum = sum(int(r["actual_qty"] or 0) for r in y_prod)
    cases.append({"q": "어제 생산 실적 몇 개야?", "kind": "DB·생산(상대 날짜)",
                  "truth": f"{yday} 실적 {y_sum}개 ({', '.join(r['shift_id'] + ' ' + str(r['actual_qty']) for r in y_prod) or '교대 없음'})",
                  "must": [nums(y_sum)]})
    wd_day = next((r for r in prod if r["shift_id"] == f"{wd}-D"), None)
    if wd_day:
        cases.append({"q": f"{kday(wd)} 주간 생산 실적 몇 개야?", "kind": "DB·생산(날짜 지정)",
                      "truth": f"{wd}-D 실적 {wd_day['actual_qty']} / 목표 {wd_day['total_target_qty']}",
                      "must": [nums(wd_day["actual_qty"])]})

    y_n = alarm_n(iso(yday), iso(today))
    cases.append({"q": "어제 알람 몇 건이야?", "kind": "DB·알람(상대 날짜)", "truth": alarm_truth(str(yday), y_n), "must": [nums(y_n[0])]})
    wd_n = alarm_n(iso(wd), iso(wd + timedelta(days=1)))
    cases.append({"q": f"{kday(wd)}에 알람 몇 번 떴어?", "kind": "DB·알람(날짜 지정)", "truth": alarm_truth(str(wd), wd_n),
                  "must": [nums(wd_n[0])]})
    code_n = alarm_n(iso(today - timedelta(days=7)), iso(today), top_code)
    cases.append({"q": f"최근 7일 {top_code} 알람 몇 번 떴어?", "kind": "DB·알람(번호)",
                  "truth": alarm_truth(f"{today - timedelta(days=7)}~{yday} {top_code}", code_n), "must": [nums(code_n[0])]})
    start = date(today.year, today.month, 1)
    m_n = alarm_n(iso(start), now.isoformat())
    cases.append({"q": f"{today.month}월에 알람 몇 건 있었어?", "kind": "DB·알람(달)",
                  "truth": alarm_truth(f"{start}~지금", m_n), "must": [nums(m_n[0])]})

    k = [r for r in run("kpi", from_date=str(wd), to_date=str(wd), equipment_id="VF2-02", shift_type="DAY")]
    if k:
        cases.append({"q": f"{kday(wd)} 주간 VF2-02 OEE 얼마야?", "kind": "DB·지표",
                      "truth": f"{k[0]['shift_id']} VF2-02 OEE {k[0]['oee_pct']}% (가동 {k[0]['availability_pct']}·성능 {k[0]['performance_pct']}·품질 {k[0]['quality_pct']})",
                      "must": [nums(k[0]["oee_pct"])]})
    rel = [r for r in run("reliability", equipment_id="VF2-02")]
    if rel:
        cases.append({"q": "VF2-02 MTTR 얼마야?", "kind": "DB·지표",
                      "truth": f"MTTR {rel[0]['mttr_min']}분, MTBF {rel[0]['mtbf_hours']}시간, 고장 {rel[0]['failure_count']}번 (최근 30일)",
                      "must": [nums(rel[0]["mttr_min"])] if rel[0]["mttr_min"] is not None else []})
    st = run("stop_reasons", **{"from": iso(today - timedelta(days=7)), "to": iso(today), "equipment_id": "VF2-02"})
    if st:
        top = max(st, key=lambda r: float(r["minutes"] or 0))
        cases.append({"q": "최근 7일 VF2-02 정지 원인 뭐가 제일 많아?", "kind": "DB·정지",
                      "truth": f"{top['reason_name']} {top['times']}번 {top['minutes']}분",
                      "must": [[top["reason_name"]]]})

    inv = [r for r in run("inventory") if r["is_low"]]
    cases.append({"q": "재고 부족한 거 있어?", "kind": "DB·재고",
                  "truth": ", ".join(f"{r['item_name']} {float(r['on_hand_qty']):g}/{float(r['safety_stock']):g}{r['unit']}" for r in inv) or "없음",
                  "must": [[r["item_name"]] for r in inv[:3]] or [["없"]]})
    pm = [r for r in run("pm_due", within_days=0) if (r["days_overdue"] or 0) > 0]
    cases.append({"q": "예방 정비 기한 넘긴 거 있어?", "kind": "DB·정비",
                  "truth": ", ".join(f"{r['equipment_id']} {r['item_name']} {r['days_overdue']}일 지남" for r in pm) or "없음",
                  "must": [[r["equipment_id"]] for r in pm[:2]] or [["없"]]})
    wo = run("work_orders", open_only=True)
    cases.append({"q": "진행 중인 정비 작업지시 있어?", "kind": "DB·작업지시",
                  "truth": ", ".join(f"{r.get('wo_no')} {r.get('equipment_id')}" for r in wo) or "없음",
                  "must": [[str(r.get("equipment_id"))] for r in wo[:2]] or [["없"]]})
    wr = run("work_records", equipment_id="VF2-02")
    if wr:
        cases.append({"q": "VF2-02 최근 작업기록 알려줘", "kind": "DB·작업기록",
                      "truth": f"{wr[0]['record_no']} 알람 {wr[0]['alarm_code']} — {wr[0]['action']}",
                      "must": [[str(wr[0]["alarm_code"])]]})
    tl = run("tool_life", equipment_id="VF2-02")
    if tl:
        low = max(tl, key=lambda r: float(r["usage_rate_pct"]))
        cases.append({"q": "VF2-02 공구 수명 얼마나 남았어?", "kind": "DB·공구",
                      "truth": f"가장 적게 남은 공구 {low['tool_no']} {low['item_name']} 남은 {low['remaining_pct']}% (사용률 {low['usage_rate_pct']}%)",
                      "must": [[low["tool_no"]], nums(low["remaining_pct"])]})
    sn = [r for r in run("sensor_trend", equipment_id="VF2-01", sensor_code="AirPressure", minutes=60)]
    if sn:
        cases.append({"q": "VF2-01 공기 압력 지금 얼마야?", "kind": "DB·센서",
                      "truth": f"{sn[0]['last_value']}{sn[0]['unit']} ({sn[0]['last_at']}), 정상 {sn[0]['normal_min']}~{sn[0]['normal_max']}",
                      "must": [nums(sn[0]["last_value"])]})
    lot = sql("SELECT lot_no, status, input_qty, scrap_qty FROM production_lot WHERE judged_at IS NOT NULL ORDER BY judged_at DESC LIMIT 1")
    if lot:
        cases.append({"q": f"{lot[0]['lot_no']} 판정 났어?", "kind": "DB·로트",
                      "truth": f"{lot[0]['lot_no']} {lot[0]['status']} 투입 {lot[0]['input_qty']} 불량 {lot[0]['scrap_qty']}",
                      "must": [[lot[0]["lot_no"]]]})
    return now, cases


def ask(tok: str, q: str) -> dict:
    req = urllib.request.Request("http://127.0.0.1:8000/api/assistant/chat", method="POST",
                                 data=json.dumps({"question": q, "context": {"new_chat": "1"}}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def main():
    with readonly_engine().connect() as conn:      # 읽기 전용 계정·읽기 전용 트랜잭션 (db.py readonly_engine)
        now, cases = gather(Db(conn))
        conn.rollback()
    print(f"시연 시계 {now:%Y-%m-%d %H:%M} 기준 · 질문 {len(cases)}개{' (DRY: 묻지 않음)' if DRY else ''}\n")
    tok = create_token("U12", "MGR", get_settings().jwt_secret, 30)
    tally = {"맞음": 0, "확인 필요": 0, "오류": 0}
    for i, c in enumerate(cases, 1):
        if ONLY and i not in ONLY:
            continue
        print(f"[{i}] ({c['kind']}) {c['q']}\n    정답(DB): {c['truth']}")
        if DRY:
            print()
            continue
        try:
            d = ask(tok, c["q"])
            ans = (d.get("answer") or "").replace("\n", " ")
            flat = ans.replace(",", "")
            ok = all(any(m in flat for m in group) for group in c["must"] if group) if c["must"] else None
            mark = "맞음" if ok else "확인 필요"
            tally[mark] += 1
            print(f"    이브({d.get('status')}): {ans[:300]}\n    판정: {mark}\n")
        except Exception as e:  # noqa: BLE001
            tally["오류"] += 1
            print(f"    오류: {type(e).__name__} {str(e)[:120]}\n")
    if not DRY:
        print("합계:", ", ".join(f"{k} {v}" for k, v in tally.items()))


main()
