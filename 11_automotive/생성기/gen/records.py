"""시간 흐름 결과(Sim)를 논리 ERD 칸 모양의 줄로 바꾼다 (④ 파생 기록 중 3단계 범위).

칸 순서는 ERD 속성 순서. 계산 칸(completed_qty, duration_min, stop_loss_qty 등)은 넣지 않는다.
"""
from __future__ import annotations

from datetime import timedelta

from .calendar import Calendar
from .common import at
from .flow import MNT_BY_SHIFT, OPR_BY_PROC, Sim

COLS = {
    "raw_material_lot": ["material_lot_no", "item_no", "received_date", "received_qty", "supplier_cert_no",
                         "heat_batch_no", "status"],
    "production_order": ["order_no", "product_code", "order_qty", "created_at", "due_at", "status", "started_at",
                         "completed_at"],
    "production_lot": ["lot_no", "order_no", "lot_seq", "input_shift_id", "material_lot_no", "input_qty", "status",
                       "scrap_qty", "judged_at"],
    "operation_report": ["op_report_id", "lot_no", "process_code", "equipment_id", "worker_user_id", "shift_id",
                         "start_at", "end_at", "pq", "gq", "rq", "sq"],
    "wip_log": ["buffer_code", "logged_at", "wip_qty", "soak_shelf_qty", "interval_type"],
    "alarm_event": ["alarm_event_id", "equipment_id", "alarm_code", "severity_at_event", "occurred_at", "cleared_at",
                    "lot_no", "prev_alarm_event_id", "is_injected", "scenario_code"],
    "equipment_state_log": ["state_log_id", "equipment_id", "state_code", "mtconnect_execution", "start_at", "end_at",
                            "warn_marker", "reason_suggested_code", "reason_code", "reason_status",
                            "reason_entered_by", "reason_confirmed_by", "reason_confirmed_at", "alarm_event_id",
                            "pm_record_id"],
    "tool_usage": ["tool_id", "op_report_id", "parts_qty", "usage_qty", "cum_after", "recorded_at"],
    "tool_change": ["tool_change_id", "tool_id", "changed_at", "changed_by", "cum_before", "change_reason",
                    "related_alarm_event_id"],
    "defect_record": ["defect_record_id", "lot_no", "process_code", "defect_code", "qty", "disposition", "result_id",
                      "found_at", "recorded_by"],
}
MTC = {"RUN": "ACTIVE", "IDLE": "READY", "BLOCKED": "READY", "DOWN": "STOPPED"}


def material_rows(sim: Sim) -> list[dict]:
    return [{"material_lot_no": ml.material_lot_no, "item_no": "RM-6061", "received_date": ml.received_date,
             "received_qty": ml.received_qty, "supplier_cert_no": ml.supplier_cert_no,
             "heat_batch_no": ml.heat_batch_no, "status": "AVAILABLE"} for ml in sim.materials]


def order_rows(sim: Sim, cfg: dict) -> list[dict]:
    cal = sim.cal
    rows = []
    for o in sim.orders:
        if o.start_work_date is not None:
            wd, st = o.start_work_date, o.start_shift_type
        else:                                   # 아직 시작 안 한 작업지시: 만든 교대 기준으로 예정 납기
            sh = cal.shift_or_near(o.created_m)
            wd, st = sh.work_date, sh.shift_type
        # 납기 = 투입 근무일 + 근무일 1일(주간) / 2일(야간). 일요일은 세지 않음 (토요일 야간 → 화요일, 1013 기록 5장)
        due, k = wd, 0
        while k < (1 if st == "DAY" else 2):
            due += timedelta(days=1)
            if due.weekday() != 6:
                k += 1
        status = "DONE" if o.done_m is not None else ("IN_PROGRESS" if o.started_m is not None else "WAITING")
        rows.append({"order_no": o.order_no, "product_code": "BRK-A100", "order_qty": o.qty,
                     "created_at": cal.to_dt(o.created_m), "due_at": at(due, cfg["sim"]["order_due_time"]),
                     "status": status,
                     "started_at": cal.to_dt(o.started_m) if o.started_m is not None else None,
                     "completed_at": cal.to_dt(o.done_m) if o.done_m is not None else None})
    return rows


def lot_rows(sim: Sim) -> list[dict]:
    rows = []
    for lot in sim.lots:
        closed = lot is not lot.order.cur_lot or lot.order.cut == lot.order.qty
        done = closed and lot.finished + lot.scrap == lot.input_qty
        rows.append({"lot_no": lot.lot_no, "order_no": lot.order.order_no, "lot_seq": lot.lot_seq,
                     "input_shift_id": lot.shift_id, "material_lot_no": lot.material_lot_no,
                     "input_qty": lot.input_qty, "status": "WAIT_INSPECTION" if done else "IN_PROCESS",
                     "scrap_qty": lot.scrap or None, "judged_at": None})
    return rows


def report_rows(sim: Sim) -> tuple[list[dict], dict]:
    cal = sim.cal
    reps = sorted(sim.reports.items(), key=lambda kv: (kv[1]["start_m"], kv[1]["equipment_id"], kv[1]["lot_no"]))
    rows, ids = [], {}
    for i, (key, r) in enumerate(reps, 1):
        ids[key] = i
        rows.append({"op_report_id": i, "lot_no": r["lot_no"], "process_code": r["process_code"],
                     "equipment_id": r["equipment_id"], "worker_user_id": r["worker_user_id"],
                     "shift_id": r["shift_id"], "start_at": cal.to_dt(r["start_m"]),
                     "end_at": cal.to_dt(r["end_m"] + 1), "pq": r["pq"], "gq": r["gq"], "rq": r["rq"], "sq": r["sq"]})
    return rows, ids


def wip_rows(sim: Sim) -> list[dict]:
    cal = sim.cal
    return [{"buffer_code": w["buffer_code"], "logged_at": cal.to_dt(w["m"]), "wip_qty": w["wip_qty"],
             "soak_shelf_qty": 0 if w["buffer_code"] == "WIP-40-50" else None, "interval_type": "MIN5"}
            for w in sim.wip_rows]


def alarm_rows(sim: Sim) -> list[dict]:
    cal = sim.cal
    return [{"alarm_event_id": e["id"], "equipment_id": e["equipment_id"], "alarm_code": e["alarm_code"],
             "severity_at_event": e["severity"], "occurred_at": cal.to_dt(e["occurred_m"]),
             "cleared_at": cal.to_dt(e["cleared_m"]) if e["cleared_m"] is not None else None,
             "lot_no": e["lot_no"], "prev_alarm_event_id": e.get("prev"), "is_injected": False,
             "scenario_code": None} for e in sim.alarm_events]


def state_rows(sim: Sim, maint_pm_ids: dict[int, int]) -> list[dict]:
    """설비 상태 구간. maint_pm_ids: maint_done 번호 → 그 정비의 pm_record_id (MAINT 구간 연결)."""
    cal: Calendar = sim.cal
    rows = []
    for eq, mc in sim.mach.items():
        runs = mc.state_runs + [[cal.n_min, None]]
        for (a, st), (b, _) in zip(runs[:-1], runs[1:]):
            state, reason, warn, alarm_id, mref = st
            sh = cal.shift_or_near(a)
            rec = {"equipment_id": eq, "state_code": state, "mtconnect_execution": MTC.get(state),
                   "start_at": cal.to_dt(a), "end_at": cal.to_dt(b), "warn_marker": bool(warn),
                   "reason_suggested_code": None, "reason_code": reason, "alarm_event_id": alarm_id,
                   "pm_record_id": maint_pm_ids.get(mref) if mref is not None else None,
                   "reason_status": None, "reason_entered_by": None, "reason_confirmed_by": None,
                   "reason_confirmed_at": None}
            if state != "RUN":
                rec["reason_status"] = "CONFIRMED"
                if reason not in ("P02", "P03"):
                    who = MNT_BY_SHIFT[sh.shift_type][0] if state in ("DOWN", "MAINT") else \
                        OPR_BY_PROC[sh.shift_type][mc.proc]
                    rec["reason_entered_by"] = who
                rec["reason_confirmed_by"] = sh.supervisor
                rec["reason_confirmed_at"] = max(sh.end, cal.to_dt(b))
            rows.append(rec)
    rows.sort(key=lambda r: (r["start_at"], r["equipment_id"]))
    for i, r in enumerate(rows, 1):
        r["state_log_id"] = i
    return rows


def tool_rows(sim: Sim, rep_ids: dict) -> tuple[list[dict], list[dict]]:
    cal = sim.cal
    usage = []
    for (tool_id, key), u in sim.tool_usage.items():
        usage.append({"tool_id": tool_id, "op_report_id": rep_ids[key], "parts_qty": u["parts"],
                      "usage_qty": round(u["usage"], 3), "cum_after": round(u["cum_after"], 3),
                      "recorded_at": cal.to_dt(u["m"])})
    changes = []
    for i, c in enumerate(sorted(sim.tool_changes, key=lambda c: (c["changed_m"], c["tool_id"])), 1):
        changes.append({"tool_change_id": i, "tool_id": c["tool_id"], "changed_at": cal.to_dt(c["changed_m"]),
                        "changed_by": c["changed_by"], "cum_before": round(c["cum_before"], 3),
                        "change_reason": c["change_reason"], "related_alarm_event_id": c["related_alarm_event_id"]})
    return usage, changes


def defect_rows(sim: Sim, fail_rid: dict | None = None) -> list[dict]:
    """fail_rid: 측정 불합격 부품 pid → 불합격 측정값 result_id (부품마다 한 줄인 치수 불량만 연결)."""
    cal = sim.cal
    fail_rid = fail_rid or {}
    ds = sorted(sim.defects.values(), key=lambda d: (d["found_m"], d["lot_no"], d["defect_code"], d.get("pid") or 0))
    return [{"defect_record_id": i, "lot_no": d["lot_no"], "process_code": d["process_code"],
             "defect_code": d["defect_code"], "qty": d["qty"], "disposition": d["disposition"],
             "result_id": fail_rid.get(d.get("pid")) if d.get("pid") else None,
             "found_at": cal.to_dt(d["found_m"]), "recorded_by": d["recorded_by"]} for i, d in enumerate(ds, 1)]


def fill_shift_actuals(sim: Sim):
    """교대 실적(OP-50 GQ + RQ)과 야간 이월 (설계서 5.3, R-88)."""
    act = {}
    for r in sim.reports.values():
        if r["process_code"] == "OP-50":
            act[r["shift_id"]] = act.get(r["shift_id"], 0) + r["gq"] + r["rq"]
    by_day = {}
    for s in sim.cal.shifts:
        s.actual_qty = act.get(s.shift_id, 0)
        by_day.setdefault(s.work_date, {})[s.shift_type] = s
    for d, ss in by_day.items():
        ss["NIGHT"].carry_over_qty = max(0, ss["DAY"].target_qty - ss["DAY"].actual_qty)
