"""채팅 음성 입력(`POST /transcribe`, `GET /voice/status`, backend/voice/*) 시험 (2026-10-20).
진짜 모델·소리는 쓰지 않는다 — 가짜 엔진이 부른 횟수와 받은 힌트를 기록한다. 스위치 끔 = 기존 동작 그대로, 소리 저장 없음, 로그에 글자 없음을 확인한다."""
import dataclasses
import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend import config as C
from backend import voice_service as VS
from backend.voice import pipeline as V
from backend.voice import settings as S
from backend.voice import text as T

pytestmark = pytest.mark.own_backend
KEY = "test-service-key"
H = {"X-Service-Key": KEY}
client = TestClient(CS.app)          # with 로 열지 않는다 — lifespan(모델 미리 올리기)이 돌지 않는다
GOOD = "BRK-A100 LOT-2609-127-1 알람 원인이 뭐야?"


class Fake:
    """가짜 엔진: decode 는 seconds 길이의 배열(range)을, transcribe 는 정해 둔 글자를 돌려주고 받은 힌트를 기록한다."""

    def __init__(self, text=GOOD, seconds=4.0, delay=0.0, decode_error=None, error=None):
        self.ready = True
        self.text, self.seconds, self.delay, self.decode_error, self.error = text, seconds, delay, decode_error, error
        self.hints, self.decoded = [], []

    def load(self):
        pass

    def decode(self, data):
        self.decoded.append(len(data))
        if self.decode_error:
            raise self.decode_error
        return range(int(self.seconds * 16000))

    def transcribe(self, samples, hint):
        self.hints.append(hint)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.text


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    monkeypatch.setenv("MOM_ASSISTANT_KEY", KEY)
    monkeypatch.setenv("ASSISTANT_VOICE", "1")
    for k in ("VOICE_MODEL", "VOICE_DEVICE", "VOICE_COMPUTE", "VOICE_THREADS", "VOICE_MAX_SECONDS", "VOICE_MIN_SECONDS", "VOICE_MAX_BYTES",
              "VOICE_TIMEOUT_S", "VOICE_QUEUE_MAX", "VOICE_HINT", "VOICE_HINT_TEXT"):
        monkeypatch.delenv(k, raising=False)
    yield
    for _ in range(60):                       # 앞 시험이 남긴 일이 끝나길 잠깐 기다린다 (다음 시험의 줄 세기를 깨지 않게)
        if V._voice._pending == 0:
            break
        time.sleep(0.05)
    V._voice._engine = None


@pytest.fixture
def tweak(monkeypatch):
    """설정 일부를 바꾼다 (환경변수의 안전 범위를 벗어난 값, 예: 0.3초 제한)."""
    def go(**kw):
        real = S.settings
        monkeypatch.setattr(V, "settings", lambda: dataclasses.replace(real(), **kw))
        monkeypatch.setattr(VS, "settings", lambda: dataclasses.replace(real(), **kw))
    return go


def post(data=b"x" * 2000, headers=H):
    return client.post("/transcribe", content=data, headers=headers)


# ---------------------------------------------------------------- 설정
def test_settings_defaults_off():
    s = S.settings()
    assert (s.model, s.device, s.compute, s.timeout_s, s.max_seconds) == ("large-v3-turbo", "cpu", "int8", 15.0, 20.0)
    assert s.hint == S.DEFAULT_HINT


def test_settings_switch_default_is_off(monkeypatch):
    monkeypatch.delenv("ASSISTANT_VOICE", raising=False)
    assert S.settings().enabled is False


def test_settings_bad_values_fall_back(monkeypatch):
    monkeypatch.setenv("VOICE_DEVICE", "tpu")
    monkeypatch.setenv("VOICE_COMPUTE", "weird")
    monkeypatch.setenv("VOICE_MODEL", "../../etc/passwd; rm")
    monkeypatch.setenv("VOICE_TIMEOUT_S", "9999")
    monkeypatch.setenv("VOICE_MAX_SECONDS", "abc")
    s = S.settings()
    assert (s.device, s.compute, s.model, s.timeout_s, s.max_seconds) == ("cpu", "int8", "large-v3-turbo", 120.0, 20.0)


def test_settings_hint_can_be_turned_off_or_replaced(monkeypatch):
    monkeypatch.setenv("VOICE_HINT", "0")
    assert S.settings().hint == ""
    monkeypatch.setenv("VOICE_HINT", "1")
    monkeypatch.setenv("VOICE_HINT_TEXT", "가나다, LOT-1")
    assert S.settings().hint == "가나다, LOT-1"


# ---------------------------------------------------------------- 글자 검사·정리 (측정에서 본 실제 출력 포함)
def test_repeat_detection_on_measured_outputs():
    loop = "브랜드인 백라스 마이너스 우큰 리프트스 마이너스 우큰 리프트스 마이너스 우큰 리프트스 마이너스 우큰 리프트스 마이너스 한 알람 범인이 뭐야?"
    assert T.looks_repeated(loop)
    assert T.looks_repeated("K-A100, LOT-2609-127-1, VF2-02, 고전압, 인터넷, CMM, 알람, 알람, 알람, 알람")
    assert not T.looks_repeated(GOOD)
    assert not T.looks_repeated("고전압 작업 전에 인터록 확인 절차 알려줘")


def test_hint_echo_on_measured_outputs():
    hint = S.DEFAULT_HINT
    assert T.is_hint_echo("K-A100, LOT-2609, VF2-02, 고전압, 인터록, CMM, 알람", hint)          # 대형 모델 무음 출력
    assert T.is_hint_echo("K-A100, LOT-2609-127-1, VF2-02, 고전압, 인터넷, CMM, 알람", hint)     # CPU 무음 출력
    assert not T.is_hint_echo(GOOD, hint)                       # 진짜 질문 (5낱말)
    assert not T.is_hint_echo("VF2-02 설비의 고전압 인터록 알람 원인과 조치 순서를 알려 줘", hint)
    assert not T.is_hint_echo("K-A100, LOT-2609, VF2-02, 고전압, 인터록, CMM, 알람", "")          # 힌트가 없으면 비교하지 않는다


def test_known_hallucinations():
    assert T.is_known_hallucination("시청해 주셔서 감사합니다.")
    assert T.is_known_hallucination("구독과 좋아요 부탁드립니다")
    assert not T.is_known_hallucination("감사합니다. 알람 원인이 뭐예요?")


def test_normalize_codes():
    assert T.normalize_codes("brk-a100 lot - 2609 알람 원인이 뭐야") == "BRK-A100 LOT-2609 알람 원인이 뭐야"
    assert T.normalize_codes("A100 마이너스 127 로트") == "A100-127 로트"
    assert T.normalize_codes("vf2-02 설비") == "VF2-02 설비"
    assert T.normalize_codes("브레이게이 100 라트 마이너스 2609") == "브레이게이 100 라트 마이너스 2609"      # 한글 음역은 건드리지 않는다
    assert T.normalize_codes("e-mail 보내줘") == "e-mail 보내줘"                                             # 숫자 없는 하이픈 낱말은 그대로


def test_postprocess_passes_good_text_and_rejects_bad():
    assert T.postprocess("  BRK-A100 LOT-2609-127-1 알람 원인이 뭐야?  ", S.DEFAULT_HINT) == (GOOD, None)
    assert T.postprocess("", "") == ("", "no_speech")
    assert T.postprocess("시청해 주셔서 감사합니다", "") == ("", "hallucination")
    assert T.postprocess("알람 알람 알람 알람 알람", "") == ("", "repeated")
    assert T.postprocess("K-A100, LOT-2609, VF2-02, 고전압, 인터록, CMM, 알람", S.DEFAULT_HINT)[1] == "hint_echo"


# ---------------------------------------------------------------- 입구
def test_off_switch_returns_404_and_never_touches_engine(monkeypatch):
    monkeypatch.setenv("ASSISTANT_VOICE", "0")
    eng = Fake()
    V.set_engine(eng)
    r = post()
    assert r.status_code == 404 and r.json()["code"] == "VOICE_OFF"
    assert eng.decoded == [] and eng.hints == []
    assert client.get("/voice/status", headers=H).json() == {"enabled": False, "ready": False, "max_seconds": 20.0}


def test_service_key_required():
    V.set_engine(Fake())
    assert client.post("/transcribe", content=b"x" * 2000).status_code == 401
    assert client.post("/transcribe", content=b"x" * 2000, headers={"X-Service-Key": "nope"}).status_code == 401
    assert client.get("/voice/status").status_code == 401


def test_success_returns_text_and_passes_hint():
    eng = Fake()
    V.set_engine(eng)
    r = post()
    assert r.status_code == 200
    j = r.json()
    assert j["text"] == GOOD and j["reason"] is None and j["seconds"] == 4.0
    assert eng.hints == [S.DEFAULT_HINT]
    assert client.get("/voice/status", headers=H).json() == {"enabled": True, "ready": True, "max_seconds": 20.0}


def test_hint_off_sends_empty_hint(monkeypatch):
    monkeypatch.setenv("VOICE_HINT", "0")
    eng = Fake()
    V.set_engine(eng)
    assert post().status_code == 200 and eng.hints == [""]


def test_empty_and_oversize_bodies():
    V.set_engine(Fake())
    assert post(b"").status_code == 400 and post(b"").json()["code"] == "EMPTY_AUDIO"
    big = post(b"x" * 1_500_001)
    assert big.status_code == 413 and big.json()["code"] == "AUDIO_TOO_LARGE"


def test_oversize_without_declared_length_is_stopped():
    V.set_engine(Fake())

    def chunks():                                  # content-length 없는 조각 전송
        for _ in range(4):
            yield b"x" * 500_000
    r = client.post("/transcribe", content=chunks(), headers=H)
    assert r.status_code == 413


def test_too_short_audio_returns_empty_text_without_transcribing():
    eng = Fake(seconds=0.3)
    V.set_engine(eng)
    j = post().json()
    assert j["text"] == "" and j["reason"] == "too_short" and eng.hints == []


def test_too_long_audio_is_refused_not_truncated():
    V.set_engine(Fake(seconds=25.0))
    r = post()
    assert r.status_code == 413 and r.json()["code"] == "AUDIO_TOO_LONG"


def test_undecodable_audio_is_400():
    V.set_engine(Fake(decode_error=ValueError("bad")))
    r = post()
    assert r.status_code == 400 and r.json()["code"] == "BAD_AUDIO"


def test_engine_failure_is_503_without_inner_details():
    V.set_engine(Fake(error=RuntimeError("C:\\models\\secret-path 없음")))
    r = post()
    assert r.status_code == 503 and r.json()["code"] == "VOICE_FAILED"
    assert "secret-path" not in r.text


@pytest.mark.parametrize("text,reason", [("", "no_speech"), ("시청해 주셔서 감사합니다", "hallucination"), ("알람 알람 알람 알람 알람 알람", "repeated"),
                                          ("K-A100, LOT-2609, VF2-02, 고전압, 인터록, CMM, 알람", "hint_echo")])
def test_bad_engine_text_is_turned_into_empty_text_with_reason(text, reason):
    V.set_engine(Fake(text=text))
    j = post().json()
    assert j["text"] == "" and j["reason"] == reason


def test_timeout_returns_503(tweak):
    tweak(timeout_s=0.3)
    V.set_engine(Fake(delay=0.8))
    r = post()
    assert r.status_code == 503 and r.json()["code"] == "VOICE_TIMEOUT"


def test_busy_when_queue_is_full(tweak):
    tweak(queue_max=0, timeout_s=5.0)
    V.set_engine(Fake(delay=0.6))
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("first", post()))
    t.start()
    time.sleep(0.2)                                # 첫 건이 돌고 있다
    second = post()
    t.join()
    assert second.status_code == 429 and second.json()["code"] == "VOICE_BUSY"
    assert out["first"].status_code == 200


def test_requests_are_processed_one_at_a_time(tweak):
    tweak(queue_max=2, timeout_s=10.0)
    running, peak = [0], [0]
    lock = threading.Lock()

    class Slow(Fake):
        def transcribe(self, samples, hint):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.15)
            with lock:
                running[0] -= 1
            return GOOD
    V.set_engine(Slow())
    rs = []
    ts = [threading.Thread(target=lambda: rs.append(post().status_code)) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert rs == [200, 200, 200] and peak[0] == 1


def test_text_and_audio_are_not_logged(caplog):
    V.set_engine(Fake(text="비밀번호는 777입니다 알람 원인이 뭐야"))
    with caplog.at_level(logging.DEBUG):
        assert post().status_code == 200
    assert "비밀번호" not in caplog.text and "777" not in caplog.text


def test_off_switch_never_creates_the_engine(monkeypatch):
    """스위치가 꺼져 있으면 미리 올리기도 요청도 엔진 객체를 만들지 않는다 (faster-whisper 가 없는 PC에서도 비서가 돈다)."""
    monkeypatch.setenv("ASSISTANT_VOICE", "0")
    V._voice._engine = None
    V.preload()
    assert post().status_code == 404
    assert V._voice._engine is None
