"""설비 지금 상태를 시연 서버 시계로 답하기 (SENSOR_LIVE, 2026-10-22). 진짜 Claude·네트워크·DB·시연 서버를 부르지 않는다.

지키는 것: ① "VF2-01 가동 상태"는 문서 길이 아니라 설비 상태 조회 ② 스위치 켬 + 시연 값을 읽으면 그 상태와 "시연 화면 시계"
③ 못 읽거나 스위치가 꺼져 있으면 공용 DB 값이고 그 문구는 없다. 잠금은 시연 응답에 없어 잠금이라고 말하지 않는다.
"현재 vf2-01 상태는"은 종류가 비어 되묻는다 (test_status_askback.py).
"""
import pytest

from backend.services import answer as A
from backend.tests.fake_backend import FakeBackend
from backend.tools import sim_live

TWIN = {"clock": {"sim_at": "2026-10-01T09:30:00+09:00"}, "equipment": {
    "VF2-01": {"state_code": "DOWN", "since_at": "2026-10-01T09:12:00+09:00", "minutes": 18, "process_code": "OP-30",
               "alarm": {"alarm_code": "994", "severity": "STOP", "cleared_at": None}, "lot_no": "LOT-2609-127-1"},
    "VF2-02": {"state_code": "RUN", "since_at": "2026-10-01T08:00:00+09:00", "minutes": 90, "process_code": "OP-30", "alarm": None},
}}


@pytest.fixture
def v3(monkeypatch):
    for k in ("PARSE_V2", "PARSE_V3", "PARSE_V5", "PURE_EXTERNAL", "PURE_KEEP_SIGNALS", "PURE_SAFETY"):
        monkeypatch.setenv(k, "1")


def test_parse_states_reads_the_open_alarm_and_skips_a_cleared_one():
    at, rows = sim_live.parse_states(TWIN, "VF2-01")
    assert at.startswith("2026-10-01T09:30") and rows[0]["last_state"] == "DOWN" and rows[0]["open_alarm_code"] == "994"
    assert rows[0]["is_locked"] is False
    assert sim_live.parse_states({"clock": {"sim_at": "2026-10-01T09:30:00+09:00"}, "equipment": {}}, "VF2-01") is None


def test_current_status_question_uses_the_tool(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    a = A.answer("VF2-01 가동 상태", "OPR", {})
    text = " ".join(str(x) for x in (a.get("conclusion"), a.get("current_data")))
    assert "설비 상태" in text and "VF2-01" in text and "RUN" in text and "문서에 없음" not in text
    assert "시연 화면 시계" not in text


def test_live_answer_uses_the_demo_server_state(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    monkeypatch.setenv("SENSOR_LIVE", "1")
    monkeypatch.setattr(sim_live, "fetch_states", lambda url, eq: sim_live.parse_states(TWIN, eq))
    a = A.answer("VF2-01 가동 상태", "OPR", {})
    text = a.get("conclusion") or ""
    assert "VF2-01 DOWN" in text and "09:12부터 18분" in text and "알람 994" in text and "시연 화면 시계" in text
    assert "잠금" not in text and "07:12" not in text


def test_when_the_demo_server_cannot_be_read_the_database_state_is_used(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    monkeypatch.setenv("SENSOR_LIVE", "1")
    monkeypatch.setattr(sim_live, "fetch_states", lambda url, eq: None)
    text = A.answer("VF2-01 가동 상태", "OPR", {})["conclusion"]
    assert "RUN" in text and "07:12부터 48분" in text and "시연 화면 시계" not in text
