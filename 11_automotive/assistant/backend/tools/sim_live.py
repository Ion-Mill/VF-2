"""시연 서버(8765)의 지금 센서 값·설비 상태 읽기 (SENSOR_LIVE=1, 2026-10-21, 설비 상태는 2026-10-22).

채팅의 센서 값·설비 상태는 공용 DB에서 읽는데 DB 시계가 10/1 08:00에 멈춰 있어 화면(시연 서버 시계)에 보이는 값과 달랐다 (예: 주축 부하 DB 1.1% ↔ 화면 41.8%).
시연에서는 화면과 같은 지금 값을 답하도록, 시연 서버의 `GET /api/line/twin`을 읽는다. 센서는 `equipment[설비].sensor`, 상태는 `state_code`·`since_at`·`alarm`.
읽기 전용(GET)이고 시연 서버를 새로 켜지 않는다. 실패하면 None — 부른 쪽이 공용 DB 값으로 답한다. 이 값은 시연 서버가 만든 가상 값이다.
잠금 여부는 이 응답에 없다. 잠금이라고 말하지 않는다.
"""
from __future__ import annotations

import json
import urllib.request

TIMEOUT_S = 2.0
CODES = ("SpindleLoadPct", "SpindleMotorTemp", "AirPressure", "Xload", "Yload", "Zload", "DcVolt")


def parse_twin(doc: object, equipment_id: str) -> tuple[str, dict[str, float]] | None:
    """시연 서버 응답 → (시연 시계 시각, {센서 코드: 값}). 모양이 다르거나 값이 하나도 없으면 None."""
    if not isinstance(doc, dict):
        return None
    clock = doc.get("clock")
    sim_at = clock.get("sim_at") if isinstance(clock, dict) else None
    equipment = doc.get("equipment")
    eq = equipment.get(equipment_id) if isinstance(equipment, dict) else None
    sensor = eq.get("sensor") if isinstance(eq, dict) else None
    if not isinstance(sim_at, str) or len(sim_at) < 16 or not isinstance(sensor, dict):
        return None
    vals: dict[str, float] = {}
    for code in CODES:
        v = sensor.get(code)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals[code] = float(v)
    return (sim_at, vals) if vals else None


def fetch_sensors(base_url: str, equipment_id: str) -> tuple[str, dict[str, float]] | None:
    doc = _get_twin(base_url)
    return None if doc is None else parse_twin(doc, equipment_id)


EQ_IDS = ("SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01")


def _state_row(eq: str, item: object) -> dict | None:
    """시연 서버 설비 하나 → 설비 상태 행. 상태 코드가 없으면 None. 잠금은 응답에 없어 is_locked는 거짓이고, 답은 잠금이라고 말하지 않는다."""
    if not isinstance(item, dict):
        return None
    state = item.get("state_code")
    if not isinstance(state, str) or not state:
        return None
    since = item.get("since_at") if isinstance(item.get("since_at"), str) else ""
    minutes = item.get("minutes")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)):
        minutes = 0
    alarm = item.get("alarm") if isinstance(item.get("alarm"), dict) else None
    code = sev = None
    if isinstance(alarm, dict) and not alarm.get("cleared_at"):
        raw = alarm.get("alarm_code")
        if isinstance(raw, str) and raw:
            code = raw
            sev = alarm.get("severity") if isinstance(alarm.get("severity"), str) else None
    lot = item.get("lot_no") if isinstance(item.get("lot_no"), str) else None
    proc = item.get("process_code") if isinstance(item.get("process_code"), str) else None
    return {"equipment_id": eq, "process_code": proc, "last_state": state, "since": since, "minutes": float(minutes),
            "open_alarm_code": code, "open_alarm_severity": sev, "is_locked": False, "current_lot_no": lot}


def parse_states(doc: object, equipment_id: str | None = None) -> tuple[str, list[dict]] | None:
    """시연 서버 응답 → (시연 시계 시각, 설비 상태 행). 설비 하나를 지정했는데 그 설비가 없으면 None."""
    if not isinstance(doc, dict):
        return None
    clock = doc.get("clock")
    sim_at = clock.get("sim_at") if isinstance(clock, dict) else None
    equipment = doc.get("equipment")
    if not isinstance(sim_at, str) or len(sim_at) < 16 or not isinstance(equipment, dict):
        return None
    want = (equipment_id,) if equipment_id else EQ_IDS
    if equipment_id and equipment_id not in equipment:
        return None
    rows = [row for eq in want if (row := _state_row(eq, equipment.get(eq))) is not None]
    return (sim_at, rows) if rows else None


def _get_twin(base_url: str) -> object | None:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/line/twin", timeout=TIMEOUT_S) as r:   # noqa: S310 — 주소는 서버 설정(SIM_SERVER_URL)에서만 온다
            return json.loads(r.read().decode("utf-8"))
    except Exception:   # noqa: BLE001 — 연결·시간 초과·형식 오류: 시연 서버 값을 못 읽었으니 공용 DB 값으로 간다
        return None


def fetch_states(base_url: str, equipment_id: str | None = None) -> tuple[str, list[dict]] | None:
    doc = _get_twin(base_url)
    return None if doc is None else parse_states(doc, equipment_id)


def parse_bottleneck(doc: object) -> dict | None:
    """시연 서버 응답 → 지금 병목 {sim_at, process_code, cause_code, since_at, equipment_process}. 병목 공정이나 시계가 없거나 모양이 다르면 None.
    병목 판단은 시연 서버가 DOC-07 §7.3 규칙으로 이미 했다 — 여기서는 그 결과를 읽기만 하고 다시 판단하지 않는다.
    equipment_process = 설비가 속한 공정 (질문이 "VF2-01이 병목이야?"처럼 설비를 짚을 때 쓴다)."""
    if not isinstance(doc, dict):
        return None
    clock = doc.get("clock")
    sim_at = clock.get("sim_at") if isinstance(clock, dict) else None
    bn = doc.get("bottleneck")
    if not isinstance(sim_at, str) or len(sim_at) < 16 or not isinstance(bn, dict):
        return None
    process, cause = bn.get("process_code"), bn.get("cause_code")
    if not isinstance(process, str) or not process or not isinstance(cause, str) or not cause:
        return None
    since = bn.get("since_at") if isinstance(bn.get("since_at"), str) and len(bn["since_at"]) >= 16 else None
    equipment = doc.get("equipment") if isinstance(doc.get("equipment"), dict) else {}
    proc_of = {eq: item["process_code"] for eq, item in equipment.items()
               if isinstance(item, dict) and isinstance(item.get("process_code"), str) and item["process_code"]}
    return {"sim_at": sim_at, "process_code": process, "cause_code": cause, "since_at": since, "equipment_process": proc_of}


def fetch_bottleneck(base_url: str) -> dict | None:
    doc = _get_twin(base_url)
    return None if doc is None else parse_bottleneck(doc)
