"""비서용 읽기 전용 조회 도구 10개 (FR-MNT-01-04, ai-operations-assistant 규칙 3.3).

SQL을 쓰지 않고, 입력(설비·기간·역할)을 검증하고, 결과가 비어 있으면 숫자를 지어내지 않는다.
모든 결과에 조회 도구명·데이터 범위·기준 시각·가상 여부를 붙인다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from backend.auth.permissions import require
from backend.config import DATA_LABEL, REFERENCE_AT
from backend.repositories.csv_repo import get_repo
from backend.services import metrics as M

EQUIPMENT = {"SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01"}
REF = datetime.fromisoformat(REFERENCE_AT[:19])


class ToolInputError(ValueError):
    pass


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s[:19])


def _check_equipment(eq):
    if eq is not None and eq not in EQUIPMENT:
        raise ToolInputError(f"알 수 없는 설비: {eq}")


def _result(tool, rows, data_range, **extra):
    return {"tool": tool, "as_of": REFERENCE_AT, "range": data_range, "is_synthetic": True, "label": DATA_LABEL,
            "rows": rows, "empty": not rows, **extra}


def _period(start: date | None, end: date | None, default_days=30):
    end = end or date(2026, 9, 30)
    start = start or end - timedelta(days=default_days - 1)
    if start > end:
        raise ToolInputError("기간의 시작이 끝보다 늦다")
    return start, end


SHIFT_KO = {"D": "주간", "N": "야간"}


def _range(start: date, end: date, shift: str | None) -> str:
    """화면에 그대로 보이는 범위 글자. 교대는 D/N 대신 주간/야간으로 쓴다 (2026-10-08)."""
    return f"{start} ~ {end}" + (f" {SHIFT_KO.get(shift, shift)}" if shift else "")


def _in_shift_period(shift_id: str, start: date, end: date, shift: str | None):
    rows = {s["shift_id"]: s for s in get_repo().table("calendar_shift")}
    s = rows.get(shift_id)
    return bool(s) and start <= date.fromisoformat(s["prod_date"]) <= end and (shift is None or s["shift"] == shift)


def equipment_status(role, equipment_id=None):
    require(role, "view_ops")
    _check_equipment(equipment_id)
    logs = get_repo().table("equipment_state_log")
    last = {}
    for r in logs:
        if equipment_id and r["equipment_id"] != equipment_id:
            continue
        if r["equipment_id"] not in last or r["end"] > last[r["equipment_id"]]["end"]:
            last[r["equipment_id"]] = r
    rows = [{"equipment_id": k, "last_state": v["state"], "until": v["end"],
             "note": "교대 사이(05:00~08:00) 라인 정지 — 기준 시각에는 가공하지 않음"} for k, v in sorted(last.items())]
    return _result("설비 상태 조회", rows, "마지막 기록")


def alarms(role, equipment_id=None, code=None, start=None, end=None, shift=None, unprocessed_only=False):
    require(role, "view_ops")
    _check_equipment(equipment_id)
    start, end = _period(start, end)
    rows = []
    for a in get_repo().table("alarm_event"):
        if equipment_id and a["equipment_id"] != equipment_id:
            continue
        if code and a["alarm_code"] != code and a["code"] != code:
            continue
        if not _in_shift_period(a["shift_id"], start, end, shift):
            continue
        if unprocessed_only and a["processed"] == "true":
            continue
        rows.append({k: a[k] for k in ("alarm_event_id", "equipment_id", "axis", "alarm_code", "name_ko", "severity",
                                       "occurred_at", "stop_min", "processed", "work_order_id", "work_record_id")})
    rows.sort(key=lambda r: r["occurred_at"])
    return _result("알람 조회", rows, _range(start, end, shift))


STOP_GROUPS = [("FAILURE", "고장"), ("MATERIALS", "자재·흐름"), ("SETUP", "준비"), ("OPERATION", "조작"), ("PLANNED", "계획")]


def stops(role, equipment_id=None, start=None, end=None, shift=None):
    """정지 기록 전부를 사유 그룹별로 + 필수 정지 판정 (DOC-07 §5.1·§5.4). 지표·손실 조회의 한 부분.

    rows = 필수 정지(교대 보고서 정지 칸). by_group = 멈춘 기록 전부를 그룹·사유별로 센 것
    (2026-10-08: "몇 번 멈췄어?"에 고장만 세어 앞 공정 대기·준비 정지가 빠지던 문제, FR-MNT-01-04).
    """
    require(role, "view_ops")
    _check_equipment(equipment_id)
    start, end = _period(start, end)
    eq_cycle = {e["equipment_id"]: float(e["cycle_min"]) for e in get_repo().master("equipment")}
    reasons = {r["code"]: r for r in get_repo().master("downtime_reason")}
    rows = [d for d in get_repo().table("downtime")
            if (not equipment_id or d["equipment_id"] == equipment_id) and _in_shift_period(d["shift_id"], start, end, shift)]
    st = [M.Stop(d["downtime_id"], d["equipment_id"], d["start"], d["end"], float(d["minutes"]), d["reason_code"],
                 eq_cycle[d["equipment_id"]], d["alarm_event_id"]) for d in rows]
    req = M.required_stops(st)
    out = [{"stop_id": s.stop_id, "equipment_id": s.equipment_id, "start": s.start, "minutes": s.minutes,
            "reason_code": s.reason_code, "loss_qty_est": s.loss_qty, "alarm_event_id": s.alarm_event_id} for s in req["items"]]
    by_group = []
    for group, group_ko in STOP_GROUPS:
        mine = [s for s in st if reasons.get(s.reason_code, {}).get("group") == group]
        codes = sorted({s.reason_code for s in mine})
        by_group.append({"group": group, "group_ko": group_ko, "count": len(mine),
                         "minutes": M.round_half_up(sum(s.minutes for s in mine), 1),
                         "reasons": [{"code": c, "name": reasons[c]["name"], "count": sum(1 for s in mine if s.reason_code == c),
                                      "minutes": M.round_half_up(sum(s.minutes for s in mine if s.reason_code == c), 1)} for c in codes]})
    unknown = [s for s in st if s.reason_code not in reasons]
    if unknown:  # 사유 코드표에 없는 기록도 빼지 않고 따로 센다 (합계가 맞아야 한다)
        by_group.append({"group": "UNKNOWN", "group_ko": "코드표에 없음", "count": len(unknown),
                         "minutes": M.round_half_up(sum(s.minutes for s in unknown), 1),
                         "reasons": [{"code": c, "name": "코드표에 없음", "count": sum(1 for s in unknown if s.reason_code == c),
                                      "minutes": M.round_half_up(sum(s.minutes for s in unknown if s.reason_code == c), 1)}
                                     for c in sorted({s.reason_code for s in unknown})]})
    cycles = {eq: eq_cycle[eq] for eq in sorted({s.equipment_id for s in req["items"]} | ({equipment_id} if equipment_id else set()))}
    return _result("지표·손실 조회 (정지)", out, _range(start, end, shift),
                   micro_count=req["micro_count"], micro_minutes=req["micro_minutes"],
                   total_failure_min=sum(s.minutes for s in req["items"]),
                   loss_qty_est_total=sum(s.loss_qty for s in req["items"]),
                   total_count=len(st), total_minutes=M.round_half_up(sum(s.minutes for s in st), 1),
                   by_group=by_group, cycle_min=cycles, all_empty=not st)


def kpi(role, equipment_id, start=None, end=None, shift=None):
    """가동률·성능·양품률·OEE (교대 합), MTTR·MTBF (30일) — DOC-07 §6."""
    require(role, "view_ops")
    if equipment_id is None:
        raise ToolInputError("설비를 정해야 한다")
    _check_equipment(equipment_id)
    start, end = _period(start, end)
    eq = {e["equipment_id"]: e for e in get_repo().master("equipment")}[equipment_id]
    ops = [o for o in get_repo().table("op_result")
           if o["equipment_id"] == equipment_id and _in_shift_period(o["shift_id"], start, end, shift)]
    if not ops:
        return _result("지표 조회", [], f"{start} ~ {end}")
    apt = sum(float(o["run_min"]) for o in ops)
    pbt = sum(float(o["pbt_min"]) for o in ops)
    pq = sum(int(o["pq"]) for o in ops)
    gq = sum(int(o["gq"]) for o in ops)
    a = M.availability(apt, pbt)
    e = M.performance(float(eq["cycle_min"]), pq, apt)
    q = M.quality_buy_rate(gq, 0, pq)
    downs = sorted((a_ for a_ in get_repo().table("alarm_event")
                    if a_["equipment_id"] == equipment_id and a_["severity"] == "STOP"), key=lambda x: x["occurred_at"])
    ttr = [float(d["stop_min"]) for d in downs]
    tbf = [(_dt(downs[i + 1]["occurred_at"]) - _dt(downs[i]["cleared_at"])).total_seconds() / 3600 for i in range(len(downs) - 1)]
    row = {"equipment_id": equipment_id, "pbt_min": pbt, "apt_min": apt, "pq": pq, "gq": gq,
           "availability_pct": a, "performance_pct": e, "qbr_pct": q,
           "oee_pct": M.oee_from(apt, pbt, float(eq["cycle_min"]), pq, gq),
           "mttr_30d_min": M.mttr(ttr), "mtbf_30d_h": M.mtbf(tbf, len(downs)), "failures_30d": len(downs),
           "formula": "A = APT ÷ PBT, E = PRI × PQ ÷ APT, QBR = (GQ + RQ) ÷ PQ, OEE = A × E × QBR (DOC-07 §6.2)"}
    return _result("지표 조회", [row], _range(start, end, shift))


def production(role, start=None, end=None, shift=None):
    require(role, "view_ops")
    start, end = _period(start, end, default_days=1)
    rows = [r for r in get_repo().table("shift_report")
            if start <= date.fromisoformat(r["prod_date"]) <= end and (shift is None or r["shift"] == shift)]
    keep = ("report_id", "prod_date", "shift", "target", "output", "scrap", "required_stop_min", "loss_qty_est", "status")
    return _result("생산 실적 조회", [{k: r[k] for k in keep} for r in rows], _range(start, end, shift))


def lots(role, lot_id=None, order_id=None):
    require(role, "view_ops")
    if not lot_id and not order_id:
        raise ToolInputError("로트 번호나 작업지시 번호가 필요하다")
    rows = [l for l in get_repo().table("production_lot")
            if (lot_id and l["lot_id"] == lot_id) or (order_id and l["order_id"] == order_id)]
    return _result("로트·작업지시 조회", rows, lot_id or order_id)


def work_orders(role, equipment_id=None, status=None):
    require(role, "view_ops")
    _check_equipment(equipment_id)
    rows = [w for w in get_repo().table("maintenance_work_order")
            if (not equipment_id or w["equipment_id"] == equipment_id) and (not status or w["status"] == status)]
    return _result("작업지시 조회", rows, "2026-09-01 ~ 2026-09-30")


def work_records(role, equipment_id=None, alarm_code=None):
    require(role, "view_ops")
    _check_equipment(equipment_id)
    by_alarm = {a["alarm_event_id"]: a for a in get_repo().table("alarm_event")}
    wo_alarm = {w["work_order_id"]: w["alarm_event_id"] for w in get_repo().table("maintenance_work_order")}
    rows = []
    for w in get_repo().table("work_record"):
        # 원인 점검 작업기록서는 알람이 아니라 작업지시서(계기: 반복 알람 2단계)에 붙어 있다
        aid = w["alarm_event_id"] or wo_alarm.get(w["work_order_id"], "")
        a = by_alarm.get(aid, {})
        if equipment_id and w["equipment_id"] != equipment_id:
            continue
        if alarm_code and a.get("alarm_code") != alarm_code:
            continue
        rows.append({"work_record_id": w["work_record_id"], "kind": w["kind"], "equipment_id": w["equipment_id"],
                     "alarm_code": a.get("alarm_code", ""), "start": w["start"], "repair_min": w["repair_min"],
                     "cause": w["cause"], "action": w["action"], "confirmed_by": w["confirmed_by"]})
    rows.sort(key=lambda r: r["start"])
    return _result("작업기록 조회", rows, "2026-09-01 ~ 2026-09-30")


def pm_due(role, equipment_id=None):
    require(role, "view_ops")
    _check_equipment(equipment_id)
    rows = [p for p in get_repo().table("pm_schedule")
            if (not equipment_id or p["equipment_id"] == equipment_id) and (p["overdue"] == "true" or p["frequency"] == "계획")]
    return _result("예방 정비 기한 조회", rows, "기준 시각까지 기한 넘김 + 2026-10-01 계획")


def tool_life(role, equipment_id=None, min_pct=0):
    require(role, "view_ops")
    _check_equipment(equipment_id)
    rows = []
    for t in get_repo().table("tool_state"):
        if equipment_id and t["equipment_id"] != equipment_id:
            continue
        pct = M.tool_usage_pct(float(t["used"]), float(t["limit"]))
        if pct >= min_pct:
            rows.append({**{k: t[k] for k in ("equipment_id", "tool_no", "tool_name", "usage_unit", "used", "limit", "since")},
                         "usage_pct": pct})
    rows.sort(key=lambda r: -r["usage_pct"])
    return _result("공구 수명 조회", rows, "기준 시각", rule="공구 수명 90% 이상 = 교체 알림 (DOC-07 §9, 가상 규칙)")


def inventory(role, item_id=None, short_only=False):
    require(role, "view_ops")
    rows = [i for i in get_repo().table("inventory_state")
            if (not item_id or i["item_id"] == item_id) and (not short_only or i["short"] == "true")]
    return _result("재고 조회", rows, "기준 시각", rule="재고 부족 = 재고 ≤ 안전 재고 (DOC-07 §10.2)")


TOOLS = {
    "equipment_status": equipment_status, "alarms": alarms, "stops": stops, "kpi": kpi, "production": production,
    "lots": lots, "work_orders": work_orders, "work_records": work_records, "pm_due": pm_due,
    "tool_life": tool_life, "inventory": inventory,
}
