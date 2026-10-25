"""비서용 읽기 전용 조회 도구 12개 (FR-MNT-01-04, ai-operations-assistant 규칙 3.3; 센서 값 `sensor_trend`는 2026-10-19에 더했다).

[11_automotive 이식 2026-10-16] 원본은 simulator/out CSV를 직접 읽었다. 여기서는 기존 백엔드의 비서 조회 도구(`/api/assistant/tools/{name}`, 14개)를
`repositories/backend_tools.py`로 부르고, 결과를 **원본이 돌려주던 행 모양으로 번역**한다 — 3,000줄 넘는 `services/answer.py`가 읽는 칸 이름을 그대로 두기 위해서다.
함수 이름·인자·`_result(...)` 모양은 원본 그대로다.

SQL을 쓰지 않고, 입력(설비·기간)을 검증하고, 결과가 비어 있으면 숫자를 지어내지 않는다. 모든 결과에 조회 도구명·데이터 범위·기준 시각·가상 여부를 붙인다.
백엔드 도구가 주지 않는 정보(건별 알람, 계획 정지·필수 정지, 작업지시 번호로 로트 찾기 …)는 **지어내지 않고** 결과에 `partial`/`unsupported` 표시를 달아 답 문장이 밝히게 한다.
권한: 허용 목록(`allowed_tools`)에 없는 도구는 호출하지 않고 ToolDenied (chat_service가 권한 밖 답으로 바꾼다).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from backend.config import DATA_LABEL, REFERENCE_AT, settings
from backend.repositories import backend_tools as BT
from backend.services import metrics as M
from backend.services import shifts as SH
from backend.services import sim_clock
from backend.tools import sim_live

EQUIPMENT = {"SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01"}
REF = datetime.fromisoformat(REFERENCE_AT[:19])
KST = timezone(timedelta(hours=9))
MAX_DAYS = 31            # 백엔드 도구의 기간 상한 (alarms·kpi·production·stop_reasons)
CHUNK_DAYS = 30


class ToolInputError(ValueError):
    pass


def _check_equipment(eq):
    if eq is not None and eq not in EQUIPMENT:
        raise ToolInputError(f"알 수 없는 설비: {eq}")


def _result(tool, rows, data_range, as_of=None, **extra):
    return {"tool": tool, "as_of": as_of or REFERENCE_AT, "range": data_range, "is_synthetic": True, "label": DATA_LABEL,
            "rows": rows, "empty": not rows, **extra}


def _period(start: date | None, end: date | None, default_days=30):
    end = end or date(2026, 9, 30)
    start = start or end - timedelta(days=default_days - 1)
    if start > end:
        raise ToolInputError("기간의 시작이 끝보다 늦다")
    return start, end


SHIFT_KO = {"D": "주간", "N": "야간"}
SHIFT_TYPE = {"D": "DAY", "N": "NIGHT"}


def _range(start: date, end: date, shift: str | None) -> str:
    """화면에 그대로 보이는 범위 글자. 교대는 D/N 대신 주간/야간으로 쓴다 (2026-10-08)."""
    return f"{start} ~ {end}" + (f" {SHIFT_KO.get(shift, shift)}" if shift else "")


def _dt(day: date, hour: int = 0, minute: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=KST).isoformat()


def _at(day: date, minutes: int) -> str:
    return _dt(day, minutes // 60, minutes % 60)


def _date_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """백엔드 도구의 기간 상한(31일)을 넘지 않게 30일씩 나눈다."""
    out, cur = [], start
    while cur <= end:
        stop = min(end, cur + timedelta(days=CHUNK_DAYS - 1))
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


def _windows(start: date, end: date, shift: str | None) -> list[tuple[str, str]]:
    """[시작, 끝) 시각 구간들. 교대를 정하면 날마다 교대 시간대만. 시연 시계가 있으면 그 근무, 없으면 주간 08~17, 야간 20~다음 날 05."""
    if shift is None:
        return [(_dt(a), _dt(b + timedelta(days=1))) for a, b in _date_chunks(start, end)]
    live = sim_clock.current()
    out, d = [], start
    while d <= end:
        if live is None:
            out.append((_dt(d, 8), _dt(d, 17)) if shift == "D" else (_dt(d, 20), _dt(d + timedelta(days=1), 5)))
        elif shift == "D":
            out.append((_at(d, live.day_start), _at(d, live.day_end)))
        else:
            out.append((_at(d, live.night_start), _at(d + timedelta(days=1), live.night_end)))
        d += timedelta(days=1)
    return out


def _call(name: str, args: dict) -> BT.ToolResult:
    return BT.call_tool(name, args)


def _num(x, default=0.0):
    return default if x is None else float(x)


def _gather(name: str, windows: list[tuple[str, str]], extra: dict) -> tuple[list[dict], str | None]:
    rows, now = [], None
    for a, b in windows:
        r = _call(name, {"from": a, "to": b, **extra})
        rows += r.rows
        now = r.now or now
    return rows, now


# ---------------------------------------------------------------- 설비 상태
def equipment_status(role, equipment_id=None):
    _check_equipment(equipment_id)
    r = _call("equipment_status", {"equipment_id": equipment_id})
    rows = [{"equipment_id": x["equipment_id"], "process_code": x.get("process_code"), "last_state": x.get("state_code"),
             "since": x.get("state_since"), "minutes": x.get("state_minutes"), "open_alarm_code": x.get("open_alarm_code"),
             "open_alarm_severity": x.get("open_alarm_severity"), "is_locked": bool(x.get("is_locked")),
             "current_lot_no": x.get("current_lot_no")} for x in r.rows]
    cfg = settings()
    if cfg.sensor_live:   # SENSOR_LIVE: 권한 확인은 위 공용 DB 호출 그대로 쓰고, 지금 상태만 시연 서버 값으로 바꾼다 (읽지 못하면 공용 DB 값 그대로)
        got = sim_live.fetch_states(cfg.sim_server_url, equipment_id)
        if got:
            sim_at, live_rows = got
            return _result("설비 상태 조회", live_rows, "지금 (시연 화면 시계)", as_of=sim_at, live=True)
    return _result("설비 상태 조회", sorted(rows, key=lambda x: x["equipment_id"]), "지금", as_of=r.now)


def current_shift(role) -> tuple[date, str] | None:
    """가장 최근에 시작한 교대 (교대가 시작된 날짜, "D"|"N"). 시연 시계가 있으면 그 시각·근무.
    없으면 백엔드 업무 시각(app_now): 20시 이후 = 그날 야간, 8~20시 = 그날 주간, 0~8시 = 전날 야간. 시각을 못 얻으면 None."""
    live = sim_clock.current()
    if live is not None:
        return SH.kind_at(live.at, live.day_start, live.night_start)
    try:
        now = datetime.fromisoformat(str(equipment_status(role)["as_of"]))
    except Exception:   # noqa: BLE001 — 시계를 못 얻으면 부른 쪽이 지금 동작(하루 전체) 그대로 간다
        return None
    if now.tzinfo is not None:
        now = now.astimezone(KST)
    if now.hour >= 20:
        return now.date(), "N"
    if now.hour >= 8:
        return now.date(), "D"
    return now.date() - timedelta(days=1), "N"


# ---------------------------------------------------------------- 알람 (백엔드는 건별이 아니라 집계)
def alarms(role, equipment_id=None, code=None, start=None, end=None, shift=None, unprocessed_only=False):
    """알람 횟수 — 설비·알람 번호별 집계(times·처음·마지막·정지 분). 건별 행과 처리 여부는 백엔드 도구에 없다(`partial`)."""
    _check_equipment(equipment_id)
    start, end = _period(start, end)
    rows, now = _gather("alarms", _windows(start, end, shift), {"equipment_id": equipment_id, "alarm_code": code})
    merged: dict[tuple, dict] = {}
    for x in rows:
        k = (x["equipment_id"], x["alarm_code"])
        m = merged.setdefault(k, {"equipment_id": x["equipment_id"], "alarm_code": x["alarm_code"], "name_ko": x.get("name_ko"),
                                  "severity": x.get("severity_at_event"), "times": 0, "first_at": x.get("first_at"),
                                  "last_at": x.get("last_at"), "down_min": 0.0})
        m["times"] += int(x.get("times") or 0)
        m["down_min"] = round(m["down_min"] + _num(x.get("down_min")), 1)
        if x.get("first_at") and (not m["first_at"] or x["first_at"] < m["first_at"]):
            m["first_at"] = x["first_at"]
        if x.get("last_at") and (not m["last_at"] or x["last_at"] > m["last_at"]):
            m["last_at"] = x["last_at"]
    out = sorted(merged.values(), key=lambda m: (m["equipment_id"], m["alarm_code"]))
    return _result("알람 조회", out, _range(start, end, shift), as_of=now, aggregated=True, partial=True,
                   note="알람은 설비·알람 번호별 횟수만 조회됩니다 (처리 여부·반복 알람 단계는 아직 조회할 수 없음)")


# ---------------------------------------------------------------- 정지 (백엔드는 손실 정지만)
STOP_GROUPS = [("FAILURE", "고장"), ("MATERIALS", "자재·흐름"), ("SETUP", "준비"), ("OPERATION", "조작")]   # 계획(PLANNED)은 도구가 주지 않는다


def stops(role, equipment_id=None, start=None, end=None, shift=None):
    """손실 정지를 사유 그룹별로. 계획 정지·필수 정지(고장 5분 이상)·순간 정지는 백엔드 도구에 없어 `partial`로 밝힌다 (DOC-07 §5.1·§5.4)."""
    _check_equipment(equipment_id)
    start, end = _period(start, end)
    rows, now = _gather("stop_reasons", _windows(start, end, shift), {"equipment_id": equipment_id})
    agg: dict[tuple, dict] = {}
    for x in rows:
        k = (x["equipment_id"], x["reason_code"])
        m = agg.setdefault(k, {"equipment_id": x["equipment_id"], "reason_code": x["reason_code"], "reason_name": x.get("reason_name"),
                               "reason_group": x.get("reason_group"), "times": 0, "minutes": 0.0, "loss_qty": 0.0})
        m["times"] += int(x.get("times") or 0)
        m["minutes"] = round(m["minutes"] + _num(x.get("minutes")), 1)
        m["loss_qty"] = round(m["loss_qty"] + _num(x.get("loss_qty")), 1)
    out = sorted(agg.values(), key=lambda m: (-m["minutes"], m["equipment_id"], m["reason_code"]))
    known = {g for g, _ in STOP_GROUPS}
    by_group = []
    for group, group_ko in STOP_GROUPS + [("UNKNOWN", "코드표에 없음")]:
        mine = [m for m in out if (m["reason_group"] if m["reason_group"] in known else "UNKNOWN") == group]
        if group == "UNKNOWN" and not mine:
            continue
        merged: dict[str, dict] = {}   # 라인 전체 질문은 설비마다 행이 있어 같은 사유가 여러 줄이 된다 — 사유 코드별로 합쳐 한 줄로 (표시용, 행 out은 그대로)
        for m in mine:
            r = merged.setdefault(m["reason_code"], {"code": m["reason_code"], "name": m["reason_name"], "count": 0, "minutes": 0.0})
            r["count"] += m["times"]
            r["minutes"] = round(r["minutes"] + m["minutes"], 1)
        by_group.append({"group": group, "group_ko": group_ko, "count": sum(m["times"] for m in mine),
                         "minutes": M.round_half_up(sum(m["minutes"] for m in mine), 1),
                         "reasons": sorted(merged.values(), key=lambda r: -r["minutes"])})
    fail = next((g for g in by_group if g["group"] == "FAILURE"), None)
    # 고장 그룹 정지만의 손실 수량 추정 — loss_qty_est_total은 손실 정지 전체(고장·자재·준비·조작)의 합이다
    fail_loss = int(M.round_half_up(sum(m["loss_qty"] for m in out if m["reason_group"] == "FAILURE"), 0))
    return _result("지표·손실 조회 (정지)", out, _range(start, end, shift), as_of=now,
                   total_count=sum(m["times"] for m in out), total_minutes=M.round_half_up(sum(m["minutes"] for m in out), 1),
                   total_failure_min=fail["minutes"] if fail else 0.0, loss_qty_est_total=int(M.round_half_up(sum(m["loss_qty"] for m in out), 0)),
                   loss_qty_failure_est=fail_loss,
                   by_group=by_group, cycle_min={}, all_empty=not out, partial=True,
                   note="손실 정지만 조회됩니다 (계획 정지·필수 정지·순간 정지는 아직 조회할 수 없음)")


# ---------------------------------------------------------------- 지표
def kpi(role, equipment_id, start=None, end=None, shift=None):
    """가동률·성능·양품률·OEE (교대 합), MTTR·MTBF (30일, `reliability` 도구가 허용된 역할만) — DOC-07 §6.

    교대별 행을 합친다: A = ΣAPT ÷ ΣPBT, E = 가동 시간 가중 평균(E = PRI × PQ ÷ APT 이므로 ΣPRI·PQ ÷ ΣAPT 와 같다),
    QBR = Σ(GQ+RQ) ÷ ΣPQ, OEE = PBT 가중 평균(OEE = PRI × (GQ+RQ) ÷ PBT)."""
    if equipment_id is None:
        raise ToolInputError("설비를 정해야 한다")
    _check_equipment(equipment_id)
    start, end = _period(start, end)
    rows, now = [], None
    for a, b in _date_chunks(start, end):
        r = _call("kpi", {"from_date": a.isoformat(), "to_date": b.isoformat(), "equipment_id": equipment_id,
                          "shift_type": SHIFT_TYPE.get(shift)})
        rows += r.rows
        now = r.now or now
    rng = _range(start, end, shift)
    if not rows:
        return _result("지표 조회", [], rng, as_of=now)
    apt, pbt = sum(_num(x.get("run_min")) for x in rows), sum(_num(x.get("pbt_min")) for x in rows)
    pq, gq, rq = (sum(int(x.get(k) or 0) for x in rows) for k in ("pq", "gq", "rq"))
    perf = sum(_num(x.get("performance_pct")) * _num(x.get("run_min")) for x in rows) / apt if apt else None
    oee = sum(_num(x.get("oee_pct")) * _num(x.get("pbt_min")) for x in rows) / pbt if pbt else None
    row = {"equipment_id": equipment_id, "pbt_min": pbt, "apt_min": apt, "pq": pq, "gq": gq, "rq": rq,
           "availability_pct": M.availability(apt, pbt), "performance_pct": None if perf is None else M.round_half_up(perf, 1),
           "qbr_pct": M.quality_buy_rate(gq, rq, pq), "oee_pct": None if oee is None else M.round_half_up(oee, 1),
           "mttr_30d_min": None, "mtbf_30d_h": None, "failures_30d": None, "reliability_hidden": True,
           "formula": "A = APT ÷ PBT, E = PRI × PQ ÷ APT, QBR = (GQ + RQ) ÷ PQ, OEE = A × E × QBR (DOC-07 §6.2)"}
    if BT.is_allowed("reliability"):         # MTTR·MTBF는 채팅 권한상 MNT·MGR만 — 허용되지 않은 역할에는 값도 칸도 만들지 않는다
        rel = _call("reliability", {"equipment_id": equipment_id}).rows
        mine = next((x for x in rel if x.get("equipment_id") == equipment_id), None)
        row.update(reliability_hidden=False,
                   mttr_30d_min=None if not mine or mine.get("mttr_min") is None else float(mine["mttr_min"]),
                   mtbf_30d_h=None if not mine or mine.get("mtbf_hours") is None else float(mine["mtbf_hours"]),
                   failures_30d=int(mine["failure_count"]) if mine and mine.get("failure_count") is not None else 0)
    else:
        for k in ("mttr_30d_min", "mtbf_30d_h", "failures_30d"):
            row.pop(k)
    return _result("지표 조회", [row], rng, as_of=now)


# ---------------------------------------------------------------- 생산
def production(role, start=None, end=None, shift=None):
    start, end = _period(start, end, default_days=1)
    rows, now = [], None
    for a, b in _date_chunks(start, end):
        r = _call("production", {"from_date": a.isoformat(), "to_date": b.isoformat()})
        rows += r.rows
        now = r.now or now
    out = []
    for x in rows:
        kind = "D" if x.get("shift_type") == "DAY" else "N"
        if shift is not None and kind != shift:
            continue
        out.append({"report_id": x["shift_id"], "prod_date": x["shift_id"][:10], "shift": kind,
                    "target": x.get("total_target_qty"), "output": x.get("actual_qty"), "scrap": x.get("defect_qty"),
                    "status": "확정" if x.get("is_report_confirmed") else "미확정",
                    "target_own_qty": x.get("target_qty"), "carry_over_qty": x.get("carry_over_qty"),
                    "forecast_qty": x.get("forecast_qty"), "shortfall_qty": x.get("shortfall_qty"), "loss_qty": x.get("loss_qty"),
                    "is_target_risk": x.get("is_target_risk"), "carry_over_is_provisional": x.get("carry_over_is_provisional")})
    out.sort(key=lambda r: (r["prod_date"], r["shift"]))
    return _result("생산 실적 조회", out, _range(start, end, shift), as_of=now,
                   rule="목표 = 교대 목표 + 이월 (확정 전 교대 값·이월은 잠정)")


# ---------------------------------------------------------------- 로트
def lots(role, lot_id=None, order_id=None):
    if not lot_id and not order_id:
        raise ToolInputError("로트 번호나 작업지시 번호가 필요하다")
    if not lot_id:      # 백엔드 로트 도구는 로트 번호로만 찾는다
        return _result("로트·작업지시 조회", [], order_id, unsupported="order_no",
                       note="작업지시 번호로 로트를 찾는 조회는 아직 없습니다 (로트 번호로 물어봐 주세요)")
    r = _call("lot", {"lot_no": lot_id})
    rows = [{"lot_id": x["lot_no"], "lot_no": x["lot_no"], "qty": x.get("input_qty"), "status": x.get("status"),
             "completed_qty": x.get("completed_qty"), "plan_mode": x.get("plan_mode"), "passed_at": x.get("passed_at"),
             "shipped_qty": x.get("shipped_qty"), "shipment_nos": x.get("shipment_nos"), "trace": x.get("trace")} for x in r.rows]
    return _result("로트·작업지시 조회", rows, lot_id, as_of=r.now)


# ---------------------------------------------------------------- 정비
def work_orders(role, equipment_id=None, status=None):
    _check_equipment(equipment_id)
    r = _call("work_orders", {"equipment_id": equipment_id})
    rows = [{"work_order_id": x["wo_no"], "wo_no": x["wo_no"], "equipment_id": x.get("equipment_id"), "triggers": x.get("trigger_kind"),
             "title": x.get("title"), "status": x.get("status"), "assignee": x.get("assignee_user_id"), "created_at": x.get("created_at"),
             "approval_wait_min": x.get("approval_wait_min")} for x in r.rows if not status or x.get("status") == status]
    return _result("작업지시 조회", rows, "최근 20건", as_of=r.now)


# 작업기록 원인·조치 글에 제조사 매뉴얼 문서 번호(ID0003 등)가 섞여 있으면 답 전체가 "원문 출처 표기가 섞여 내보내지 않았습니다"로 막힌다 (2026-10-21 시연 "992 지난 조치").
# 조회 결과를 만들 때 그 번호만 뗀다("체크리스트(ID0003)를 쓴다" → "체크리스트를 쓴다"). 기록 원문은 DB에 그대로 두고 채팅이 보이는 글만 다룬다 (D-03). 데이터 쪽 정리는 DB·생성기 담당 몫.
_MANUAL_ID = re.compile(r"\s*[(（]\s*(?:TG|RD|AD|ID|SA)\d{4}\s*[)）]|[,，]?\s*(?:서비스\s*알림\s*)?(?<![A-Za-z0-9])(?:TG|RD|AD|ID|SA)\d{4}(?![0-9])")


def mask_manual_ids(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", _MANUAL_ID.sub("", text or "")).strip()


def work_records(role, equipment_id=None, alarm_code=None):
    _check_equipment(equipment_id)
    r = _call("work_records", {"equipment_id": equipment_id, "alarm_code": alarm_code})
    rows = [{"work_record_id": x["record_no"], "record_no": x["record_no"], "kind": x.get("record_type"), "equipment_id": x.get("equipment_id"),
             "alarm_code": x.get("alarm_code") or "", "start": x.get("confirmed_at") or "", "repair_min": x.get("repair_min"),
             "cause": mask_manual_ids(x.get("cause") or ""), "action": mask_manual_ids(x.get("action") or ""), "confirmed_at": x.get("confirmed_at")} for x in r.rows]
    rows.sort(key=lambda x: x["start"])                    # 백엔드는 최근 순 20건 — 원본처럼 오래된 것부터
    return _result("작업기록 조회", rows, "확정된 최근 20건", as_of=r.now)


def pm_due(role, equipment_id=None):
    _check_equipment(equipment_id)
    r = _call("pm_due", {"within_days": 0, "equipment_id": equipment_id})
    rows = [{"pm_task_id": x.get("pm_task_id"), "equipment_id": x.get("equipment_id"), "item": x.get("item_name"),
             "frequency": x.get("cycle_code") or "", "next_due": str(x.get("next_due_date") or ""),
             "days_overdue": x.get("days_overdue"), "overdue": "true" if (x.get("days_overdue") or 0) > 0 else "false"} for x in r.rows]
    return _result("예방 정비 기한 조회", rows, "오늘까지 기한", as_of=r.now)


def tool_life(role, equipment_id=None, min_pct=0):
    _check_equipment(equipment_id)
    r = _call("tool_life", {"equipment_id": equipment_id})
    rows = []
    for t in r.rows:
        pct = _num(t.get("usage_rate_pct"))
        if pct >= min_pct:
            rows.append({"equipment_id": t.get("equipment_id"), "tool_no": t.get("tool_no"), "tool_name": t.get("item_name"),
                         "usage_unit": t.get("usage_unit"), "used": t.get("cum_usage"), "limit": t.get("life_limit"),
                         "usage_pct": pct, "remaining_pct": t.get("remaining_pct"), "parts_left": t.get("parts_left")})
    rows.sort(key=lambda x: -x["usage_pct"])
    return _result("공구 수명 조회", rows, "지금", as_of=r.now, rule="공구 수명 90% 이상 = 교체 알림 (DOC-07 §9, 가상 규칙)")


# ---------------------------------------------------------------- 센서 (OP-30 VF2-01·VF2-02만, 2026-10-19)
MAX_SENSOR_MINUTES = 360            # 백엔드 도구의 기간 상한 (minutes 1~360)


def sensor_trend(role, equipment_id, minutes=60, sensor_code=None):
    """OP-30 설비의 센서별 최소·평균·최대·마지막 값과 정상 범위 [참고] — 공용 DB 시계 기준 최근 N분(1~360). 알람 기준값은 없다 (DOC-07 §3).
    채팅 권한: MNT·MGR만 (허용 목록에 없으면 `_call`이 백엔드를 부르기 전에 ToolDenied). 도구가 기준 시각(`now`)을 주지 않으면 `clock_known`이 False —
    답 문장은 시각을 지어내지 않는다."""
    if not equipment_id:
        raise ToolInputError("설비를 정해야 한다")
    _check_equipment(equipment_id)
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= MAX_SENSOR_MINUTES:
        raise ToolInputError(f"기간은 1~{MAX_SENSOR_MINUTES}분이어야 한다")
    r = _call("sensor_trend", {"equipment_id": equipment_id, "minutes": minutes, "sensor_code": sensor_code})
    keys = ("equipment_id", "sensor_code", "sensor_name", "unit", "samples", "min_value", "avg_value", "max_value", "last_value", "last_at",
            "normal_min", "normal_max", "is_out_of_normal")
    rows = [{k: x.get(k) for k in keys} for x in r.rows]
    cfg = settings()
    if cfg.sensor_live and rows:      # SENSOR_LIVE: 권한·이름·단위·정상 범위는 위 공용 DB 조회 그대로 쓰고, 값만 시연 서버의 지금 값으로 바꾼다 (읽지 못하면 공용 DB 값 그대로)
        got = sim_live.fetch_sensors(cfg.sim_server_url, equipment_id)
        if got:
            sim_at, vals = got
            live = []
            for x in rows:
                v = vals.get(x.get("sensor_code"))
                if v is None:
                    continue
                lo, hi = x.get("normal_min"), x.get("normal_max")
                out = None if lo is None or hi is None else bool(v < float(lo) or v > float(hi))
                live.append({**x, "samples": 1, "min_value": v, "avg_value": v, "max_value": v, "last_value": v, "last_at": sim_at, "is_out_of_normal": out})
            if live:
                return _result("센서 추세 조회", live, "지금 값 (시연 화면 시계)", as_of=sim_at, minutes=minutes, equipment_id=equipment_id,
                               clock_known=True, live=True, rule="정상 범위는 [참고] — 알람 기준값이 아니다 (DOC-07 §3). 값은 시연 서버가 만든 가상 값")
    return _result("센서 추세 조회", rows, f"직전 {minutes}분 (공용 DB 시계)", as_of=r.now, minutes=minutes, equipment_id=equipment_id,
                   clock_known=bool(r.now), rule="정상 범위는 [참고] — 알람 기준값이 아니다 (DOC-07 §3)")


# ---------------------------------------------------------------- 재고
def inventory(role, item_id=None, short_only=False):
    r = _call("inventory", {"item_no": item_id})
    rows = [{"item_id": x["item_no"], "item_no": x["item_no"], "name": x.get("item_name"), "category": x.get("category"), "unit": x.get("unit"),
             "on_hand": x.get("on_hand_qty"), "safety_stock": x.get("safety_stock"), "short": "true" if x.get("is_low") else "false",
             "shipped_7d": x.get("shipped_7d")} for x in r.rows]
    if short_only:
        rows = [x for x in rows if x["short"] == "true"]
    return _result("재고 조회", rows, "지금", as_of=r.now, rule="재고 부족 = 재고 ≤ 안전 재고 (DOC-07 §10.2)")


TOOLS = {
    "equipment_status": equipment_status, "alarms": alarms, "stops": stops, "kpi": kpi, "production": production,
    "lots": lots, "work_orders": work_orders, "work_records": work_records, "pm_due": pm_due,
    "tool_life": tool_life, "inventory": inventory, "sensor_trend": sensor_trend,
}


# ---------------------------------------------------------------- 지금 병목 (시연 서버 값, 2026-10-25)
def bottleneck_now(role):
    """지금 병목 공정·원인·시작 시각을 시연 서버(`GET /api/line/twin`)에서 읽는다. SENSOR_LIVE=1일 때만이고, 못 읽으면 None —
    부른 쪽(answer.py)이 "아직 못 읽어요" 안내로 답한다. 공용 DB에는 병목을 읽는 비서 도구가 없고 DB 시계도 시연 시계를 따라가지 않아 DB 값으로 되돌아가지 않는다.
    권한은 설비 상태와 같은 라인 보기(LINE_VIEW) — `equipment_status`가 허용된 역할만 (DB를 부르지 않는다)."""
    if not BT.is_allowed("equipment_status"):
        raise BT.ToolDenied("equipment_status")
    cfg = settings()
    if not cfg.sensor_live:
        return None
    got = sim_live.fetch_bottleneck(cfg.sim_server_url)
    if got is None:
        return None
    sim_at = got.pop("sim_at")
    return _result("병목 조회", [got], "지금 (시연 화면 시계)", as_of=sim_at, live=True)
