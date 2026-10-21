"""센서 값을 시연 서버의 지금 값으로 답하기 SENSOR_LIVE (2026-10-21) 최소 시험 — 진짜 Claude·네트워크·DB·시연 서버를 부르지 않는다 (가짜 백엔드·시연 서버 값은 바꿔치기).

문제: 채팅의 센서 값은 공용 DB(시계 10/1 08:00 정지)라 화면(시연 서버)의 값과 달랐다 (주축 부하 1.1% ↔ 41.8%).
지키는 것: 스위치 켬 + 시연 서버를 읽으면 그 지금 값과 "시연 화면 시계"로 답하고(정상 범위 [참고]·bar 그대로), 못 읽거나 스위치가 꺼져 있으면 공용 DB 값 그대로다.
"""
import pytest

from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON
from backend.tools import sim_live

LIVE = {"SpindleLoadPct": 41.8, "SpindleMotorTemp": 37.4, "AirPressure": 104.3, "Xload": 6.7, "Yload": 18.6, "Zload": 24.6, "DcVolt": 312.5}
TWIN = {"clock": {"sim_at": "2026-10-01T13:43:00+09:00"}, "equipment": {"VF2-01": {"sensor": LIVE}, "VF2-02": {"sensor": {**LIVE, "SpindleLoadPct": 30.2}}}}


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("SENSOR_LIVE", "1")
    monkeypatch.setattr(sim_live, "fetch_sensors", lambda url, eq: sim_live.parse_twin(TWIN, eq))


def ask(q, role="MNT"):
    a = A.answer(q, role, {"new_chat": "1"})
    a.pop("_followup", None)
    return a


def test_parse_twin_reads_the_clock_and_the_seven_sensor_values():
    at, vals = sim_live.parse_twin(TWIN, "VF2-01")
    assert at == "2026-10-01T13:43:00+09:00" and vals["SpindleLoadPct"] == 41.8 and len(vals) == 7


@pytest.mark.parametrize("doc", [None, [], {}, {"clock": {}, "equipment": {}}, {"clock": {"sim_at": "2026-10-01T13:43:00+09:00"}, "equipment": {"VF2-01": {"sensor": {}}}},
                                 {"clock": {"sim_at": "2026-10-01T13:43:00+09:00"}, "equipment": {"VF2-01": {"sensor": {"Xload": True}}}}])
def test_parse_twin_returns_none_for_a_missing_or_wrong_shape(doc):
    assert sim_live.parse_twin(doc, "VF2-01") is None


def test_live_answer_uses_the_demo_server_values_and_clock():
    a = ask("VF2-01 센서 추세")
    c = a["conclusion"]
    assert a["status"] == "답변" and "시연 화면 시계" in c and "지금 값" in c and "13:43" in c and "08:00" not in c
    assert "주축 부하: 41.8% — 정상 [참고]" in c and "주축 모터 온도: 37.4℃ — 정상 [참고]" in c and "105" not in c and "104.3 psi(약 7.2 bar) — 정상 [참고]" in c
    assert "정상 범위" not in c and "비정상으로 표시된 센서: 없음" in c and "알람 판정이 아니에요" in c        # 범위 대신 판정, 알람 판정이 아니라는 안내
    assert "추세" in c and a["current_data"][0]["as_of"].startswith("2026-10-01T13:43")


def test_two_equipment_are_listed_side_by_side_with_live_values():
    c = ask("VF2 두 대 센서 값 비교해 줘")["conclusion"]
    assert "VF2-01 센서" in c and "VF2-02 센서" in c and "지금 VF2-01 41.8% · VF2-02 30.2%" in c


def test_when_the_demo_server_cannot_be_read_the_database_values_are_used(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_sensors", lambda url, eq: None)
    c = ask("VF2-01 센서 추세")["conclusion"]
    assert "공용 DB 시계" in c and "직전 60분" in c and "시연 화면 시계" not in c


def test_switch_off_keeps_the_database_values(monkeypatch):
    monkeypatch.setenv("SENSOR_LIVE", "0")
    c = ask("VF2-01 센서 추세")["conclusion"]
    assert "공용 DB 시계" in c and "41.8" not in c


def _live(**over):
    return {"clock": {"sim_at": "2026-10-01T13:43:00+09:00"}, "equipment": {"VF2-01": {"sensor": {**LIVE, **over}}}}


def test_high_value_is_marked_abnormal_with_the_reference_range(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_sensors", lambda url, eq: sim_live.parse_twin(_live(SpindleMotorTemp=43.1), eq))
    c = ask("VF2-01 센서 추세")["conclusion"]
    assert "주축 모터 온도: 43.1℃ — 비정상(높음, 참고 범위 28~42℃) [참고]" in c and "비정상으로 표시된 센서: 주축 모터 온도" in c
    assert c.count("비정상(") == 1


def test_low_pressure_is_abnormal_low_with_bar_in_the_range(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_sensors", lambda url, eq: sim_live.parse_twin(_live(AirPressure=99.0), eq))
    c = ask("VF2-01 센서 추세")["conclusion"]
    assert "공기 압력: 99 psi(약 6.8 bar) — 비정상(낮음, 참고 범위 100~110 psi(약 6.9~7.6 bar)) [참고]" in c


def test_the_edge_of_the_range_is_normal(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_sensors", lambda url, eq: sim_live.parse_twin(_live(SpindleMotorTemp=42.0, DcVolt=300.0), eq))
    c = ask("VF2-01 센서 추세")["conclusion"]
    assert "주축 모터 온도: 42℃ — 정상 [참고]" in c and "직류 버스 전압: 300 V — 정상 [참고]" in c and "비정상으로 표시된 센서: 없음" in c


def test_a_sensor_without_a_range_says_no_basis():
    from backend.services import sensor as SN
    r = {"live": True, "clock_known": True, "as_of": "2026-10-01T13:43:00+09:00", "equipment_id": "VF2-01", "minutes": 60,
         "rows": [{"equipment_id": "VF2-01", "sensor_code": "Xload", "sensor_name": "X축 부하", "unit": "%", "last_value": 6.7, "normal_min": None, "normal_max": None}]}
    assert "X축 부하: 6.7% — 판정 기준 없음" in SN.render("VF2-01", r).text
