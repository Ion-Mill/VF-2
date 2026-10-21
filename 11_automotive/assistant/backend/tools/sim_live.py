"""시연 서버(8765)의 지금 센서 값 읽기 (SENSOR_LIVE=1, 2026-10-21).

채팅의 센서 값은 공용 DB에서 읽는데 DB 시계가 10/1 08:00에 멈춰 있어 화면(시연 서버 시계)에 보이는 값과 달랐다 (예: 주축 부하 DB 1.1% ↔ 화면 41.8%).
시연에서는 화면과 같은 지금 값을 답하도록, 시연 서버의 `GET /api/line/twin`의 `equipment[설비].sensor`를 읽는다. 읽기 전용(GET)이고 시연 서버를 새로 켜지 않는다.
실패하면 None — 부른 쪽이 공용 DB 값으로 답한다. 이 값은 시연 서버가 만든 가상 값이다.
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
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/line/twin", timeout=TIMEOUT_S) as r:   # noqa: S310 — 주소는 서버 설정(SIM_SERVER_URL)에서만 온다
            return parse_twin(json.loads(r.read().decode("utf-8")), equipment_id)
    except Exception:   # noqa: BLE001 — 연결·시간 초과·형식 오류: 시연 서버 값을 못 읽었으니 공용 DB 값으로 간다
        return None
