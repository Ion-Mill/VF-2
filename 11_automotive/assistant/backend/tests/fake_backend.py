"""시험용 가짜 백엔드 — `11_automotive/backend/app/sql/assistant.sql`의 조회 도구 14개가 돌려주는 **열 모양 그대로** 행을 돌려준다.

`backend_tools._post`를 바꿔 끼운다 (네트워크·DB 없음). 호출 기록(`calls`)으로 어떤 도구를 어떤 인자로 불렀는지, 서비스 키·`on_behalf_of`가 실렸는지 본다.
값은 시험용 가짜다 (실제 생성기 데이터가 아님).
"""
from __future__ import annotations

from typing import Callable

NOW = "2026-10-01T08:00:00+09:00"
KEY = "test-service-key"

# 센서 7종 (데이터생성기/masters/sensor_item.csv) — 정상 범위 [참고]. 값 (최소, 평균, 최대, 마지막)은 시험용 가짜다 (조사 노트 5장의 모양: 설비가 서 있는 시간이라 주축 부하 0 근처,
# 주축 모터 온도는 정상 범위 아래라 `is_out_of_normal=True` 한 종류, 나머지는 범위 안).
SENSORS = [  # (코드, 이름, 단위, 정상 최소, 정상 최대)
    ("SpindleLoadPct", "주축 부하", "%", 0, 185), ("SpindleMotorTemp", "주축 모터 온도", "℃", 28, 42), ("AirPressure", "공기 압력", "psi", 100, 110),
    ("Xload", "X축 부하", "%", 0, 65), ("Yload", "Y축 부하", "%", 0, 65), ("Zload", "Z축 부하", "%", 0, 65), ("DcVolt", "직류 버스 전압", "V", 300, 330)]
SENSOR_VALUES = {
    "VF2-01": {"SpindleLoadPct": (0, 0.86, 2.8, 1.1), "SpindleMotorTemp": (27.7, 28.1, 28.9, 28.4), "AirPressure": (102.8, 105.81, 109.1, 105),
               "Xload": (0, 0.31, 1.2, 0.5), "Yload": (0, 0.22, 0.9, 0.4), "Zload": (0, 0.18, 0.7, 0.3), "DcVolt": (311.2, 317.3, 322.8, 318.1)},
    "VF2-02": {"SpindleLoadPct": (0, 0.92, 3.1, 1.3), "SpindleMotorTemp": (27.8, 28.2, 29.0, 28.5), "AirPressure": (101.9, 105.2, 108.7, 104.6),
               "Xload": (0, 0.28, 1.1, 0.4), "Yload": (0, 0.2, 0.8, 0.3), "Zload": (0, 0.15, 0.6, 0.2), "DcVolt": (310.4, 316.8, 321.9, 317.5)}}
SENSOR_LAST_AT = "2026-10-01T07:59:00+09:00"      # DB 시계 08:00 바로 앞 한 분


def sensor_trend_rows(args: dict) -> list[dict]:
    """`sensor_trend` 도구 (assistant.sql) 흉내: 설비·센서로 거르고, 값 개수는 창 안의 1분 평균 수(N분 창이면 N-1개 — 시계 08:00 값은 아직 없다)."""
    minutes = int(args.get("minutes") or 60)
    out = []
    for eq, vals in SENSOR_VALUES.items():
        for code, name, unit, lo, hi in SENSORS:
            mn, av, mx, last = vals[code]
            out.append({"equipment_id": eq, "sensor_code": code, "sensor_name": name, "unit": unit, "samples": max(minutes - 1, 0), "min_value": mn,
                        "avg_value": av, "max_value": mx, "last_value": last, "last_at": SENSOR_LAST_AT, "normal_min": lo, "normal_max": hi,
                        "normal_range_tag": "REFERENCE", "is_out_of_normal": mn < lo or mx > hi})
    return out


DEFAULT_ROWS: dict[str, list[dict] | Callable[[dict], list[dict]]] = {
    "equipment_status": [
        {"equipment_id": "VF2-01", "process_code": "OP-30", "state_code": "RUN", "state_since": "2026-10-01T07:12:00+09:00", "state_minutes": 48.0,
         "warn_marker": None, "open_alarm_code": None, "open_alarm_severity": None, "is_locked": False, "current_lot_no": "LOT-2609-128-1"},
        {"equipment_id": "VF2-02", "process_code": "OP-30", "state_code": "DOWN", "state_since": "2026-10-01T07:40:00+09:00", "state_minutes": 20.0,
         "warn_marker": None, "open_alarm_code": "992", "open_alarm_severity": "STOP", "is_locked": True, "current_lot_no": None}],
    "alarms": [
        {"equipment_id": "VF2-01", "alarm_code": "2075", "name_ko": "윤활 압력 낮음", "severity_at_event": "WARN", "times": 3,
         "first_at": "2026-09-12T09:10:00+09:00", "last_at": "2026-09-28T14:02:00+09:00", "down_min": 0.0},
        {"equipment_id": "VF2-02", "alarm_code": "2075", "name_ko": "윤활 압력 낮음", "severity_at_event": "WARN", "times": 2,
         "first_at": "2026-09-15T10:00:00+09:00", "last_at": "2026-09-20T11:00:00+09:00", "down_min": 0.0}],
    "kpi": [
        {"shift_id": "2026-09-29-D", "equipment_id": "VF2-01", "availability_pct": 80.0, "performance_pct": 90.0, "quality_pct": 95.0, "oee_pct": 68.4,
         "run_min": 384.0, "down_min": 60.0, "maint_min": 36.0, "pbt_min": 480.0, "pq": 50, "gq": 47, "rq": 1, "sq": 2},
        {"shift_id": "2026-09-29-N", "equipment_id": "VF2-01", "availability_pct": 60.0, "performance_pct": 70.0, "quality_pct": 100.0, "oee_pct": 42.0,
         "run_min": 288.0, "down_min": 192.0, "maint_min": 0.0, "pbt_min": 480.0, "pq": 30, "gq": 30, "rq": 0, "sq": 0}],
    "reliability": [
        {"equipment_id": "VF2-01", "process_code": "OP-30", "failure_count": 4, "down_min": 200.0, "mttr_min": 50.0, "mtbf_hours": 168.0, "is_mttr_warn": False}],
    "production": [
        {"shift_id": "2026-09-29-D", "shift_type": "DAY", "target_qty": 90, "carry_over_qty": 0, "total_target_qty": 90, "carry_over_is_provisional": False,
         "actual_qty": 84, "defect_qty": 2, "forecast_qty": 84, "shortfall_qty": 6, "is_target_risk": True, "is_report_confirmed": True,
         "failure_loss_qty": 5, "speed_loss_qty": 1, "loss_qty": 6, "daily_target_qty": 180, "order_nos": "PO-2609-01"},
        {"shift_id": "2026-09-29-N", "shift_type": "NIGHT", "target_qty": 90, "carry_over_qty": 6, "total_target_qty": 96, "carry_over_is_provisional": False,
         "actual_qty": 96, "defect_qty": 0, "forecast_qty": 96, "shortfall_qty": 0, "is_target_risk": False, "is_report_confirmed": False,
         "failure_loss_qty": 0, "speed_loss_qty": 0, "loss_qty": 0, "daily_target_qty": 180, "order_nos": "PO-2609-01"}],
    "lot": [
        {"lot_no": "LOT-2609-041-1", "status": "PASSED", "input_qty": 30, "completed_qty": 30, "plan_mode": "NORMAL", "passed_at": "2026-09-14T16:00:00+09:00",
         "shipped_qty": 30, "shipment_nos": "SHP-2609-01", "trace": [{"process": "OP-30", "equipment_id": "VF2-01"}]}],
    "work_orders": [
        {"wo_no": "WO-2609-0007", "equipment_id": "VF2-01", "trigger_kind": "ALARM", "title": "윤활 점검", "status": "IN_PROGRESS",
         "assignee_user_id": "U07", "created_at": "2026-09-28T14:10:00+09:00", "approval_wait_min": 12.0},
        {"wo_no": "WO-2609-0006", "equipment_id": "VF2-02", "trigger_kind": "PM", "title": "정기 점검", "status": "DONE",
         "assignee_user_id": "U08", "created_at": "2026-09-20T09:00:00+09:00", "approval_wait_min": 5.0}],
    "work_records": [      # 백엔드는 최근 것부터 (ORDER BY confirmed_at DESC)
        {"record_no": "WR-2609-0009", "record_type": "FULL", "equipment_id": "VF2-01", "alarm_code": "2075", "cause": "윤활유 부족",
         "action": "보충", "repair_min": 25, "confirmed_at": "2026-09-28T15:00:00+09:00"},
        {"record_no": "WR-2609-0004", "record_type": "FULL", "equipment_id": "VF2-01", "alarm_code": "2075", "cause": "필터 막힘",
         "action": "교체", "repair_min": 40, "confirmed_at": "2026-09-12T11:00:00+09:00"}],
    "pm_due": [
        {"pm_task_id": 12, "equipment_id": "VF2-01", "item_name": "가이드 레일 윤활", "cycle_code": "WEEKLY", "last_done_at": "2026-09-20T09:00:00+09:00",
         "next_due_date": "2026-09-27", "days_overdue": 4}],
    "tool_life": [
        {"tool_id": "T05", "equipment_id": "VF2-01", "tool_no": "T05", "item_name": "엔드밀 12mm", "usage_unit": "MIN", "cum_usage": 460.0,
         "life_limit": 500.0, "usage_rate_pct": 92.0, "remaining_pct": 8.0, "parts_left": 12},
        {"tool_id": "T01", "equipment_id": "VF2-01", "tool_no": "T01", "item_name": "페이스밀", "usage_unit": "MIN", "cum_usage": 100.0,
         "life_limit": 500.0, "usage_rate_pct": 20.0, "remaining_pct": 80.0, "parts_left": 200}],
    "inventory": [
        {"item_no": "RM-001", "item_name": "알루미늄 봉재 6061", "category": "RAW", "unit": "개", "on_hand_qty": 20.0, "safety_stock": 50.0, "is_low": True, "shipped_7d": 0.0},
        {"item_no": "FG-001", "item_name": "브래킷 A100", "category": "FG", "unit": "개", "on_hand_qty": 300.0, "safety_stock": 100.0, "is_low": False, "shipped_7d": 90.0}],
    "stop_reasons": [
        {"equipment_id": "VF2-01", "reason_code": "F01", "reason_name": "공구 파손", "reason_group": "FAILURE", "times": 2, "minutes": 70.0, "loss_qty": 10.0},
        {"equipment_id": "VF2-01", "reason_code": "S01", "reason_name": "단취 준비", "reason_group": "SETUP", "times": 1, "minutes": 20.0, "loss_qty": 3.0}],
    "sensor_trend": sensor_trend_rows,      # 함수 — 인자(분·센서)로 거른 행을 만든다
    "equipment_spec": [      # 비서는 아직 이 도구로 답 가지를 만들지 않는다 (가짜 행만)
        {"equipment_id": "VF2-01", "process_code": "OP-30", "process_name": "머시닝", "model": "Haas VF-2", "controller": "Haas NGC", "std_cycle_min": 30.0,
         "batch_qty": 6, "batch_time_min": 30.0, "size_x_mm": 2000, "size_y_mm": 2200, "size_z_mm": 2700, "size_source_tag": "REFERENCE", "ref_model": "VF-2", "has_sensor": True},
        {"equipment_id": "VF2-02", "process_code": "OP-30", "process_name": "머시닝", "model": "Haas VF-2", "controller": "Haas NGC", "std_cycle_min": 30.0,
         "batch_qty": 6, "batch_time_min": 30.0, "size_x_mm": 2000, "size_y_mm": 2200, "size_z_mm": 2700, "size_source_tag": "REFERENCE", "ref_model": "VF-2", "has_sensor": True}],
}


class FakeBackend:
    """`install(monkeypatch)` 뒤 `backend_tools.call_tool`이 이 가짜를 부른다."""

    def __init__(self, rows: dict[str, list[dict]] | None = None, key: str = KEY):
        self.rows = {**DEFAULT_ROWS, **(rows or {})}
        self.key = key
        self.calls: list[dict] = []
        self.fail_with: Exception | None = None

    def install(self, monkeypatch) -> "FakeBackend":
        from backend import config as C
        from backend.repositories import backend_tools as BT
        monkeypatch.setattr(C, "_dotenv", lambda: {})
        monkeypatch.setenv("MOM_BACKEND_URL", "http://backend.test")
        monkeypatch.setenv("MOM_ASSISTANT_KEY", self.key)
        monkeypatch.setattr(BT, "_post", self._post)
        return self

    def _post(self, url: str, headers: dict, payload: dict, timeout: float):
        name = url.rsplit("/", 1)[-1]
        self.calls.append({"url": url, "tool": name, "headers": headers, "on_behalf_of": payload.get("on_behalf_of"),
                           "args": payload.get("args", {}), "timeout": timeout})
        if self.fail_with is not None:
            raise self.fail_with
        args = payload.get("args", {})
        rows = self.rows.get(name, [])
        rows = rows(args) if isinstance(rows, Callable) else rows
        for col in ("equipment_id", "alarm_code", "lot_no", "item_no", "sensor_code"):      # 실제 SQL처럼 인자로 거른다 (비우면 전체)
            if args.get(col) is not None:
                rows = [r for r in rows if r.get(col) == args[col]]
        return {"tool": name, "rows": rows, "now": NOW}

    def tools_called(self) -> list[str]:
        return [c["tool"] for c in self.calls]
