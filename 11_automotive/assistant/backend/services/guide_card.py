"""MNT-02 알람 대응 지침카드 (UI설계서 SCR-09·6.1, ai-operations-assistant 규칙 4.1).

칸 순서 고정: 알람 → 심각도 → 누가 → (연쇄) → 먼저 할 일 → 안전 → 생산 영향 → 지난 기록 → 버튼 → 출처 더보기.
- 알람 의미·심각도·누가: 알람 코드집 DOC-02 (심각도·누가는 팀 정의 [가상]).
- 먼저 할 일: 고장 대응 매뉴얼 DOC-03 점검 순서 표의 작업자(★) 줄 그대로 (로컬 LLM 미연결 = 기본 표시).
- 안전: 고정 서식(DOC-05). AI가 쓰지 않는다.
- 생산 영향·지난 기록: 프로그램 계산·조회 결과. 손실은 (추정)과 계산식을 함께 보인다.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from backend.auth.permissions import require
from backend.config import DATA_LABEL
from backend.demo_state import DemoState
from backend.repositories.csv_repo import get_repo
from backend.safety import templates as S
from backend.services import metrics as M
from backend.services.answer import _clean, _field, doc03_steps
from backend.services.cite import chunk, cite, evidence
from backend.services.notifications import SEVERITY_KO, alarm_key
from backend.services.shifts import shift_id_of
from backend.tools import query_tools as T

SYMBOL = {"STOP": "⚠", "WARNING": "▲", "GUIDE": "ⓘ"}
CHAIN_WINDOW = timedelta(minutes=1)
NEXT_BUNDLE = "다음 묶음(B)에서 연결합니다"


class NotFound(LookupError):
    pass


def _sec(ref: str) -> tuple[str, str] | None:
    if "§" not in ref:
        return None
    doc, sec = ref.split("§")
    return doc.strip(), sec.strip()


def _current_order(now: datetime) -> dict | None:
    shift = shift_id_of(now)   # 자정 뒤는 전날 야간 (2026-10-11 P3 고침 — 전에는 그날 야간으로 셌다)
    return next((o for o in get_repo().table("production_order") if o["start_shift"] == shift and o["status"] == "대기"), None)


def build(state: DemoState, alarm_event_id: str, role: str) -> dict:
    require(role, "view_guide_card")
    role = role.upper()
    a = next((x for x in state.alarms() if x["alarm_event_id"] == alarm_event_id), None)
    if a is None:
        raise NotFound(alarm_event_id)
    now = state.now
    master = {m["code"]: m for m in get_repo().master("alarm_master")}
    m = master.get(a["alarm_code"])
    eq = a["equipment_id"]
    proc = state.equipment()[eq]["process"]
    key = alarm_key(a)
    # is_synthetic: 알람 사건·정지 시간·손실·지난 기록은 가상 운영 데이터 (API명세서 공통 규칙, 2026-10-11 P1)
    head = {"alarm_event_id": alarm_event_id, "equipment_id": eq, "process": proc, "occurred_at": a["occurred_at"],
            "key": key, "data_label": DATA_LABEL, "is_synthetic": True, "as_of": now.isoformat()}
    if m is None:  # SCR-09 상태 표: 코드집에 없는 번호
        return {**head, "unknown": True, "message": f"알람 코드집에 없음 — 보전 담당자 호출 (번호 {key})",
                "alarm": {"key": key, "name_ko": a["name_ko"], "name_en": "", "evidence": []}}

    d2s, d3s = _sec(m["doc02_section"]), _sec(m["doc03_section"])
    d2 = chunk(*d2s) if d2s else None
    d3 = chunk(*d3s) if d3s else None
    ev2 = [evidence(d2)] if d2 else []
    ev3 = [evidence(d3)] if d3 else []
    sev = a["severity"]

    # [4] 연쇄: 같은 설비 1분 안 앞선 알람이 있고, 그 번호가 이 알람의 사내 문서 설명에 있을 때만
    t = datetime.fromisoformat(a["occurred_at"])
    prev = sorted([p for p in state.alarms() if p["equipment_id"] == eq and p is not a
                   and timedelta(0) < t - datetime.fromisoformat(p["occurred_at"]) <= CHAIN_WINDOW], key=lambda p: p["occurred_at"])
    easy = _clean(_field(d2, "쉬운 설명")) if d2 else ""
    doc_text = (d2.text if d2 else "") + (d3.text if d3 else "")
    chain = None
    if prev and all(p["code"] in doc_text for p in prev):
        chain = {"codes": [p["code"] for p in prev] + [a["code"]], "sentence": easy, "evidence": ev2}

    # [5] 먼저 할 일: DOC-03 점검 순서 표의 작업자(★) 줄
    # 점검 순서 표만 읽고 자르지 않는다 (2026-10-08: 알람 번호 목록 표를 점검 순서로 읽던 문제·개수 자르기 수정)
    all_steps = doc03_steps(m["doc03_section"], a["code"])
    steps = [s for s in all_steps if s["operator"]] or all_steps

    # [6] 안전 (고정 서식)
    if sev == "STOP":
        safety = S.stop_block(eq)
    elif sev == "WARNING":
        safety = S.short_task(a["code"], eq) or S.not_applicable("WARNING")
    else:
        safety = S.not_applicable("GUIDE")
    safety_ev = cite(safety["cite"]["doc_id"], safety["cite"]["section"])

    # [7] 생산 영향 (코드 계산, 추정)
    cycle = float(state.equipment()[eq]["cycle_min"])
    if a["stop_min"]:
        stop_min, ongoing = float(a["stop_min"]), False
    else:
        stop_min, ongoing = max(0, math.floor((now - t).total_seconds() / 60)), not a["cleared_at"]
    production = None
    if sev in ("STOP", "WARNING"):
        loss = M.loss_qty_estimate(stop_min, cycle)
        order = _current_order(now) if ongoing else None
        production = {"stop_min": stop_min, "ongoing": ongoing, "loss_qty_est": loss, "cycle_min": cycle,
                      "formula": f"정지 {stop_min:g}분 ÷ 기준 사이클 {cycle:g}분 = 약 {loss}개 (추정)",
                      "order": order["order_id"] if order else None,
                      "lot": None, "lot_note": "이번 교대 로트 기록 없음 (가상 데이터는 9/30까지)" if ongoing else None,
                      "evidence": [x for x in [cite("DOC-07", "5.3")] if x], "label": DATA_LABEL, "is_synthetic": True,
                      "is_estimated": True}  # 손실 수량은 추정 (FR-AST-COM-19)

    # [8] 지난 기록
    week = [p for p in state.alarms() if p["equipment_id"] == eq and p["alarm_code"] == a["alarm_code"]
            and timedelta(0) <= t - datetime.fromisoformat(p["occurred_at"]) < timedelta(days=7)]
    recs = T.work_records(role, eq, a["alarm_code"])["rows"]
    reps = [r for r in get_repo().table("repeat_alarm") if r["equipment_id"] == eq and r["alarm_code"] == a["alarm_code"]]
    repeat = None
    if reps:
        r = reps[-1]
        repeat = (f"반복 알람 2단계 — 지난 조치 효과 없음, 원인 점검 ({r['status']})" if r["stage"] == "2"
                  else f"반복 알람 1단계 — {'조치 계획 있음' if r['plan_at'] else '조치 계획 대기'}")
    history = {"week_count": len(week), "records": [{"id": w["work_record_id"], "date": w["start"][:10], "kind": w["kind"],
                                                     "cause": w["cause"]} for w in recs[-3:]],
               "repeat": repeat, "empty_text": "기록 없음"}

    # [9] 버튼 (등급별, UI설계서 SCR-09)
    ask = {"label": "더 묻기", "action": "ask", "enabled": True, "question": f"{key} 알람 뜨면 뭐부터 봐?"}
    if sev == "STOP" and proc == "OP-30":
        buttons = [ask, {"label": "작업지시서 보기 — AI비서 초안", "action": "SCR-11", "enabled": False, "reason": f"작업지시서 화면은 {NEXT_BUNDLE}"}]
    elif sev == "STOP":
        buttons = [{"label": "간이 작업기록 쓰기 — 보전 담당자 확정", "action": "SCR-13", "enabled": False, "reason": f"간이 작업기록 화면은 {NEXT_BUNDLE}"}]
    elif sev == "WARNING":
        buttons = [ask, {"label": "간이 작업기록 쓰기", "action": "SCR-13", "enabled": False, "reason": f"간이 작업기록 화면은 {NEXT_BUNDLE}"}]
    else:
        buttons = [ask]

    sources = []
    for e in ev2 + ev3 + ([safety_ev] if safety_ev else []) + (production["evidence"] if production else []):
        if e and e["cite"] not in [s["cite"] for s in sources]:
            sources.append(e)
    return {
        **head, "unknown": False,
        "alarm": {"key": key, "name_ko": m["name_ko"], "name_en": m["name_en"], "meaning": easy, "evidence": ev2},
        "severity": {"code": sev, "ko": SEVERITY_KO.get(sev, sev), "symbol": SYMBOL.get(sev, "ⓘ"), "tag": "가상 · 팀 정의",
                     "evidence": ev2},
        "who": {"text": "작업자 조치 가능" if "작업자" in m["who"] else "보전 담당자 호출", "raw": m["who"], "evidence": ev2},
        "chain": chain,
        "first_steps": {"items": steps, "evidence": ev3, "mode": "기본 표시 — DOC-03 점검 순서 표의 작업자(★) 줄 그대로 (로컬 LLM 미연결)",
                        "all_count": len(all_steps)},
        "safety": {**safety, "evidence": [safety_ev] if safety_ev else []},
        "production": production,
        "history": history,
        "buttons": buttons,
        "sources": sources,
        "caution": "근거 안내이며 실행 지시가 아닙니다. 전기 측정·수리는 자격자/HFO 작업입니다." if sev == "STOP" else "근거 안내이며 실행 지시가 아닙니다.",
    }
