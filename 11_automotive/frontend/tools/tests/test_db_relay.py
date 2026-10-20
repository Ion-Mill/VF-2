"""시연 서버 → 백엔드 DB 중계 시험 (2026-10-20, db_relay.py) — 가짜 백엔드로 (네트워크·DB를 부르지 않음).

실행 (frontend/ 폴더에서):  ..\\생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
지키는 것: ① 로컬 주소·키가 없으면 안 켜짐 ② 백엔드가 시계를 거절하면(시연 모드 아님 = 공용 DB 서버) 안 켜짐
③ 알람 번호를 DB 번호로 바꿔 상태에 씀 ④ DOWN이 알람보다 먼저 와도 알람 뒤에 보냄 ⑤ 같은 사건의 앞 알람을 연쇄로 이음
⑥ [처음으로]는 대응표만 비움
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db_relay import DbRelay  # noqa: E402

CLOCK = {"sim_at": "2026-10-01T08:00:00+09:00", "speed": 60, "paused": False}


class FakeBackend:
    def __init__(self, clock_status=200):
        self.calls, self.next_id, self.clock_status = [], 900, clock_status

    def __call__(self, url, body, key):
        path = url.split("8020", 1)[1]
        self.calls.append((path, body))
        if path == "/api/ingest/clock":
            return self.clock_status, ({} if self.clock_status == 200 else {"detail": {"reason": "NOT_DEMO_MODE"}})
        if path == "/api/ingest/alarms":
            self.next_id += 1
            return 200, {"alarm_event_id": self.next_id}
        return 200, {"state_log_id": 1}


def relay(fake):
    return DbRelay("http://127.0.0.1:8020", "k", lambda: CLOCK, post=fake, log=lambda *_: None)


def test_off_unless_local_and_key(monkeypatch):
    monkeypatch.setenv("MOM_DB_RELAY_URL", "https://vbz.supabase.co")
    monkeypatch.setenv("MOM_INGEST_KEY", "k")
    assert DbRelay.from_env(lambda: CLOCK, log=lambda *_: None) is None
    monkeypatch.setenv("MOM_DB_RELAY_URL", "http://127.0.0.1:8020")
    monkeypatch.delenv("MOM_INGEST_KEY")
    assert DbRelay.from_env(lambda: CLOCK, log=lambda *_: None) is None
    monkeypatch.delenv("MOM_DB_RELAY_URL")
    assert DbRelay.from_env(lambda: CLOCK, log=lambda *_: None) is None


def test_refuses_when_backend_not_demo_mode():
    fake = FakeBackend(clock_status=409)
    r = relay(fake)
    assert r.start() is False and r.enabled is False
    r.feed([{"type": "alarm", "alarm_event_id": 356, "equipment_id": "VF2-01", "alarm_code": "108"}])
    assert r.q.empty()                                     # 꺼지면 받지도 않음


def test_s1_chain_and_down_before_alarm():
    fake = FakeBackend()
    r = relay(fake)
    evs = [
        {"type": "alarm", "at": "2026-10-01T08:43:00+09:00", "alarm_event_id": 356, "equipment_id": "VF2-01", "alarm_code": "108",
         "severity": "WARN", "scenario_code": "S1"},
        {"type": "alarm", "at": "2026-10-01T08:45:00+09:00", "alarm_event_id": 357, "equipment_id": "VF2-01", "alarm_code": "994",
         "severity": "STOP", "scenario_code": "S1"},
        # 시뮬레이터는 DOWN을 그 알람(358)보다 먼저 보낸다
        {"type": "state_changed", "at": "2026-10-01T08:46:00+09:00", "equipment_id": "VF2-01", "state": "DOWN", "reason": "F01",
         "warn": False, "alarm_event_id": 358, "mtconnect_execution": "STOPPED"},
        {"type": "alarm", "at": "2026-10-01T08:46:00+09:00", "alarm_event_id": 358, "equipment_id": "VF2-01", "alarm_code": "992",
         "severity": "STOP", "scenario_code": "S1"},
        {"type": "state_changed", "at": "2026-10-01T08:47:00+09:00", "equipment_id": "SAW-01", "state": "RUN", "reason": None,
         "warn": False, "alarm_event_id": None, "mtconnect_execution": "ACTIVE"},
    ]
    for e in evs:
        r.handle(e)
    alarms = [b for p, b in fake.calls if p == "/api/ingest/alarms"]
    states = [b for p, b in fake.calls if p == "/api/ingest/state"]
    assert [a["prev_alarm_event_id"] for a in alarms] == [None, 901, 902]          # 108 → 994 → 992 연쇄 (DB 번호)
    assert all(a["is_injected"] and a["scenario_code"] == "S1" for a in alarms)
    paths = [p for p, _ in fake.calls]
    assert paths.index("/api/ingest/state") > 2                                     # DOWN은 992 알람 뒤에
    assert states[0]["alarm_event_id"] == 903 and states[0]["state_code"] == "DOWN"  # 시뮬레이터 358 → DB 903
    assert states[1] == {"equipment_id": "SAW-01", "state_code": "RUN", "at": "2026-10-01T08:47:00+09:00",
                         "execution": "ACTIVE", "warn_marker": False, "reason_suggested_code": None, "alarm_event_id": None}
    assert r.stats["alarms"] == 3 and r.stats["states"] == 2


def test_reset_clears_map_only():
    fake = FakeBackend()
    r = relay(fake)
    r.handle({"type": "alarm", "alarm_event_id": 356, "equipment_id": "VF2-01", "alarm_code": "108", "scenario_code": None})
    assert r.amap == {356: 901}
    r.handle({"type": "_reset"})
    assert r.amap == {} and r.pending == {}
    assert not any(p.endswith("/reset") for p, _ in fake.calls)                     # DB는 되돌리지 않음


def test_only_alarm_and_state_are_queued():
    r = relay(FakeBackend())
    r.feed([{"type": "sensor"}, {"type": "wip_changed"}, {"type": "alarm"}, {"type": "state_changed"}, {"type": "bottleneck_changed"}])
    assert r.q.qsize() == 2
