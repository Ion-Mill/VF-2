"""시연 서버 → 백엔드 DB 중계 시험 (2026-10-20, 2026-10-23 고침 — db_relay.py) — 가짜 백엔드로 (네트워크·DB를 부르지 않음).

실행 (frontend/ 폴더에서):  ..\\데이터생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
지키는 것: ① 주소·키가 없으면 안 켜짐 (공용 DB 백엔드 주소도 됨 — "DB 1개 = 공장 1개", 2026-10-23)
② 백엔드가 시계를 거절하면(MOM_SIM_SYNC·시연 모드 둘 다 꺼짐) 안 켜짐
③ 처음 맞출 때 DB를 먼저 되돌리고 줄을 보냄 ④ 다음부터는 바뀐 줄만 ⑤ 센서 1분 값이 5초 값으로 바뀌면 옛 줄을 지움
⑥ [처음으로](회차가 바뀜)면 DB를 되돌리고 처음부터 다시 보냄 ⑦ 되돌리기가 실패하면 줄을 보내지 않음
⑧ 함께 보낸 것이 막히면 표 하나씩 다시 보내 막힌 표만 남김 ⑨ 상태가 그대로면 표를 다시 만들지 않음
⑩ 되돌릴 때 시뮬레이터 시작점을 보내고, DB 기준점과 다르면(BASELINE_MISMATCH) 중계가 꺼짐
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db_relay import DbRelay  # noqa: E402

CLOCK = {"sim_at": "2026-10-01T08:00:00+09:00", "speed": 60, "paused": False}
ALARM_COLS = ["alarm_event_id", "equipment_id", "alarm_code"]
STATE_COLS = ["state_log_id", "equipment_id", "state_code", "end_at"]
SENSOR_COLS = ["equipment_id", "sensor_code", "sampled_at", "value", "interval_type"]


class FakeBackend:
    def __init__(self, clock_status=200, reset_status=200, refuse=(), mismatch=False):
        self.calls, self.clock_status, self.reset_status, self.refuse = [], clock_status, reset_status, set(refuse)
        self.mismatch = mismatch

    def __call__(self, url, body, key):
        path = url.split("8000", 1)[1]
        self.calls.append((path, body))
        if path == "/api/ingest/clock":
            return self.clock_status, ({} if self.clock_status == 200 else {"detail": {"reason": "NOT_DEMO_MODE"}})
        if path == "/api/ingest/reset":
            if self.mismatch:
                return 409, {"code": "INVALID_STATE", "detail": {"reason": "BASELINE_MISMATCH",
                                                                 "diff": {"alarm_event": {"db": 400, "sim": 355}}}}
            return self.reset_status, {"sim_at": "2026-10-01T08:00:00+09:00"}
        if path == "/api/ingest/sync":
            if self.refuse & set(body["tables"]):
                return 409, {"message": "R-35"}
            return 200, {"tables": {}}
        return 404, {}

    def paths(self):
        return [p for p, _ in self.calls if p != "/api/ingest/clock"]

    def syncs(self):
        return [b["tables"] for p, b in self.calls if p == "/api/ingest/sync"]


class Sim:
    """시연 서버 State._relay_snap 흉내: 회차·표"""

    def __init__(self):
        self.run_id, self.n, self.made = 1, 0, 0
        self.tables = {"alarm_event": (ALARM_COLS, [("356", "VF2-01", "362")]),
                       "equipment_state_log": (STATE_COLS, [("8582", "VF2-01", "RUN", "")])}

    def snap(self, last_sig):
        sig = (self.run_id, self.n)
        if sig == last_sig:
            return sig, self.run_id, None
        self.made += 1
        return sig, self.run_id, {k: (c, list(r)) for k, (c, r) in self.tables.items()}

    def change(self, **tables):
        self.tables.update(tables)
        self.n += 1


BASE = {"start_at": "2026-10-01T08:00:00+09:00", "id_after": {"alarm_event": 355, "equipment_state_log": 8581}}


def relay(fake, sim):
    return DbRelay("http://127.0.0.1:8000", "k", lambda: CLOCK, sim.snap, lambda: BASE, post=fake, log=lambda *_: None)


def test_off_unless_url_and_key(monkeypatch, tmp_path):
    sim = Sim()
    monkeypatch.setenv("MOM_ENV_FILE", str(tmp_path / "없음.env"))       # 이 PC의 backend/.env.supabase 와 상관없이
    monkeypatch.setenv("MOM_DB_RELAY_URL", "http://127.0.0.1:8020")
    monkeypatch.setenv("MOM_INGEST_KEY", "k")
    assert DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None) is not None
    monkeypatch.setenv("MOM_DB_RELAY_URL", "https://mom-api.example.com")     # 배포한 백엔드 주소도 됨
    assert DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None) is not None
    monkeypatch.delenv("MOM_INGEST_KEY")
    assert DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None) is None
    monkeypatch.setenv("MOM_INGEST_KEY", "k")
    monkeypatch.delenv("MOM_DB_RELAY_URL")
    assert DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None) is None


def test_auto_from_backend_env(monkeypatch, tmp_path):
    """주소를 안 줘도 백엔드 환경 파일이 중계를 받으면(MOM_SIM_SYNC=true) 켠다 — 키도 그 파일에서 (2026-10-24)"""
    sim = Sim()
    env = tmp_path / "backend.env"
    env.write_text("MOM_SIM_SYNC=true\nMOM_INGEST_KEY=k2\n", encoding="utf-8")
    monkeypatch.setenv("MOM_ENV_FILE", str(env))
    monkeypatch.delenv("MOM_DB_RELAY_URL", raising=False)
    monkeypatch.delenv("MOM_INGEST_KEY", raising=False)
    monkeypatch.setenv("MOM_BACKEND_URL", "http://127.0.0.1:8020")
    r = DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None)
    assert r is not None and r.url == "http://127.0.0.1:8020" and r.key == "k2"
    monkeypatch.setenv("MOM_DB_RELAY_URL", "off")                          # 끄기
    assert DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None) is None
    monkeypatch.delenv("MOM_DB_RELAY_URL")
    env.write_text("MOM_SIM_SYNC=false\nMOM_INGEST_KEY=k2\n", encoding="utf-8")   # 공용 DB를 보기만 하는 팀원 = 꺼짐
    assert DbRelay.from_env(lambda: CLOCK, sim.snap, log=lambda *_: None) is None


def test_refuses_when_backend_not_demo_mode():
    fake = FakeBackend(clock_status=409)
    r = relay(fake, Sim())
    assert r.start() is False and r.enabled is False
    assert fake.paths() == []                                  # 되돌리기·보내기 없음


def test_first_sync_resets_then_sends_only_changes():
    fake, sim = FakeBackend(), Sim()
    r = relay(fake, sim)
    r.sync_once()
    assert fake.paths() == ["/api/ingest/reset", "/api/ingest/sync"]          # DB 먼저 되돌림
    assert [b for p, b in fake.calls if p == "/api/ingest/reset"] == [BASE]    # 되돌릴 때 시뮬레이터 시작점을 보냄
    first = fake.syncs()[0]
    assert first["alarm_event"]["upsert"] == [["356", "VF2-01", "362"]]
    assert list(first) == ["alarm_event", "equipment_state_log"]               # 부모(알람) 먼저
    # 구간이 닫히고 새 구간이 열림 → 바뀐 줄 2개만, 알람은 안 보냄
    sim.change(equipment_state_log=(STATE_COLS, [("8582", "VF2-01", "RUN", "2026-10-01T08:05:00+09:00"),
                                                 ("8583", "VF2-01", "IDLE", "")]))
    r.sync_once()
    second = fake.syncs()[1]
    assert list(second) == ["equipment_state_log"] and len(second["equipment_state_log"]["upsert"]) == 2
    r.sync_once()                                                              # 그대로 → 표를 다시 만들지도 않음
    assert len(fake.syncs()) == 2 and sim.made == 2
    assert fake.paths().count("/api/ingest/reset") == 1


def test_sensor_minute_value_replaced_by_5s_is_deleted():
    fake, sim = FakeBackend(), Sim()
    sim.tables = {"sensor_sample": (SENSOR_COLS, [("VF2-01", "AirPressure", "T1", "105", "MIN1_AVG")])}
    r = relay(fake, sim)
    r.sync_once()
    sim.change(sensor_sample=(SENSOR_COLS, [("VF2-01", "AirPressure", "T1", "104.9", "SEC5"),
                                            ("VF2-01", "AirPressure", "T1+5", "104.7", "SEC5")]))
    r.sync_once()
    s = fake.syncs()[1]["sensor_sample"]
    assert s["delete"] == [["VF2-01", "AirPressure", "T1", "MIN1_AVG"]] and len(s["upsert"]) == 2


def test_new_run_resets_db_and_resends_everything():
    fake, sim = FakeBackend(), Sim()
    r = relay(fake, sim)
    r.sync_once()
    sim.run_id += 1                                                            # 시연 서버 [처음으로]
    sim.n = 0
    r.reset()
    r.sync_once()
    assert fake.paths() == ["/api/ingest/reset", "/api/ingest/sync", "/api/ingest/reset", "/api/ingest/sync"]
    assert fake.syncs()[1] == fake.syncs()[0]                                  # 같은 줄이라도 처음부터 다시


def test_failed_reset_sends_nothing():
    fake, sim = FakeBackend(reset_status=409), Sim()
    r = relay(fake, sim)
    r.sync_once()
    assert fake.syncs() == [] and r.run_seen is None                          # 옛 회차 DB에 섞지 않음, 다음에 다시


def test_blocked_table_alone_is_retried():
    fake, sim = FakeBackend(refuse={"equipment_state_log"}), Sim()
    r = relay(fake, sim)
    r.sync_once()
    assert [list(t) for t in fake.syncs()] == [["alarm_event", "equipment_state_log"], ["alarm_event"], ["equipment_state_log"]]
    assert "alarm_event" in r.sent and "equipment_state_log" not in r.sent
    fake.refuse.clear()
    r.sync_once()                                                              # 상태는 그대로지만 덜 보냈으므로 다시 만든다
    assert list(fake.syncs()[-1]) == ["equipment_state_log"]


def test_baseline_mismatch_turns_relay_off():
    fake, sim = FakeBackend(mismatch=True), Sim()
    r = relay(fake, sim)
    r.sync_once()
    assert r.enabled is False and fake.syncs() == []                          # 번호가 겹칠 DB에는 보내지 않음
