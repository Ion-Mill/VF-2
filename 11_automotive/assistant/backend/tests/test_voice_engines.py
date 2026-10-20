"""채팅 음성 입력 — 실행기 고르기(`VOICE_ENGINE`)와 Transformers(원본 Whisper) 실행기의 모델 없는 부분 시험 (2026-10-20).
진짜 모델·torch 는 올리지 않는다: 설정 읽기, 저장소·개정 고르기, 소리 읽기(PyAV), "고르기만으로는 무거운 패키지를 import 하지 않는다"를 확인한다.
(원본 모델을 올려 도는지·속도는 사용자가 따로 잰다.)"""
import dataclasses
import io
import math
import struct
import subprocess
import sys
import wave

import pytest

from backend import config as C
from backend.voice import audio as A
from backend.voice import engine_transformers as ET
from backend.voice import pipeline as V
from backend.voice import settings as S
from backend.voice.engine import FasterWhisperEngine

pytestmark = pytest.mark.own_backend


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    for k in ("ASSISTANT_VOICE", "VOICE_MODEL", "VOICE_DEVICE", "VOICE_COMPUTE", "VOICE_THREADS", "VOICE_ENGINE", "VOICE_DTYPE",
              "VOICE_MODEL_REVISION", "VOICE_LOCAL_ONLY", "VOICE_HINT", "VOICE_HINT_TEXT"):
        monkeypatch.delenv(k, raising=False)
    yield
    V._voice._engine = None


# ---------------------------------------------------------------- 설정
def test_engine_settings_defaults():
    s = S.settings()
    assert (s.engine, s.dtype, s.revision, s.local_only) == ("faster-whisper", "float32", "", False)


def test_engine_settings_valid_values(monkeypatch):
    monkeypatch.setenv("VOICE_ENGINE", " Transformers ")
    monkeypatch.setenv("VOICE_DTYPE", "BFLOAT16")
    monkeypatch.setenv("VOICE_MODEL_REVISION", "06F233FE06E710322ABA913C1BC4249A0D71FCE1")
    monkeypatch.setenv("VOICE_LOCAL_ONLY", "1")
    s = S.settings()
    assert (s.engine, s.dtype, s.local_only) == ("transformers", "bfloat16", True)
    assert s.revision == "06f233fe06e710322aba913c1bc4249a0d71fce1"      # 소문자로 맞춘다


@pytest.mark.parametrize("engine,dtype,rev", [("tensorrt", "float16", "../../etc"), ("", "int8", "v1.0; rm -rf"), ("onnx", "fp64", "zzzzzzz")])
def test_engine_settings_bad_values_fall_back(monkeypatch, engine, dtype, rev):
    monkeypatch.setenv("VOICE_ENGINE", engine)
    monkeypatch.setenv("VOICE_DTYPE", dtype)
    monkeypatch.setenv("VOICE_MODEL_REVISION", rev)
    s = S.settings()
    assert (s.engine, s.dtype, s.revision) == ("faster-whisper", "float32", "")


def test_model_name_with_slash_is_accepted(monkeypatch):
    monkeypatch.setenv("VOICE_MODEL", "openai/whisper-large-v3")
    assert S.settings().model == "openai/whisper-large-v3"


# ---------------------------------------------------------------- 최대 녹음 길이 (2026-10-20: 60초까지, transformers 는 30초 창 하나라 30초로 묶음)
def test_max_seconds_default_is_20_and_60_is_allowed(monkeypatch):
    assert S.settings().max_seconds == 20.0
    monkeypatch.setenv("VOICE_MAX_SECONDS", "60")
    assert S.settings().max_seconds == 60.0


def test_max_seconds_is_clamped_to_60_for_faster_whisper(monkeypatch):
    monkeypatch.setenv("VOICE_MAX_SECONDS", "999")
    assert S.settings().max_seconds == 60.0


def test_transformers_engine_caps_max_seconds_at_30(monkeypatch):
    monkeypatch.setenv("VOICE_ENGINE", "transformers")
    monkeypatch.setenv("VOICE_MAX_SECONDS", "60")
    assert S.settings().max_seconds == S.TRANSFORMERS_MAX_SECONDS == 30.0
    monkeypatch.setenv("VOICE_MAX_SECONDS", "15")
    assert S.settings().max_seconds == 15.0                                 # 더 짧게 정한 값은 그대로


# ---------------------------------------------------------------- 저장소·개정 고르기
def test_resolve_model_pins_the_original_repo():
    repo, rev = ET.resolve_model("openai/whisper-large-v3", "")
    assert (repo, rev) == ("openai/whisper-large-v3", ET.OPENAI_LARGE_V3_REVISION)
    assert len(ET.OPENAI_LARGE_V3_REVISION) == 40


def test_resolve_model_aliases_and_unknown_names():
    assert ET.resolve_model("large-v3", "") == ("openai/whisper-large-v3", ET.OPENAI_LARGE_V3_REVISION)
    assert ET.resolve_model("large-v3-turbo", "") == ("openai/whisper-large-v3-turbo", None)       # 다른 저장소는 고정값을 쓰지 않는다
    assert ET.resolve_model("somethingelse", "") == ("openai/whisper-large-v3", ET.OPENAI_LARGE_V3_REVISION)
    assert ET.resolve_model("someone/custom-whisper", "") == ("someone/custom-whisper", None)


def test_resolve_model_explicit_revision_wins():
    assert ET.resolve_model("openai/whisper-large-v3", "abcdef1")[1] == "abcdef1"
    assert ET.resolve_model("large-v3-turbo", "main") == ("openai/whisper-large-v3-turbo", "main")


# ---------------------------------------------------------------- 실행기 고르기
def test_make_engine_follows_the_setting(monkeypatch):
    s = S.settings()
    assert isinstance(V.make_engine(s), FasterWhisperEngine)
    t = V.make_engine(dataclasses.replace(s, engine="transformers"))
    assert isinstance(t, ET.TransformersWhisperEngine) and t.ready is False


def test_pipeline_creates_the_selected_engine_lazily(monkeypatch):
    monkeypatch.setenv("VOICE_ENGINE", "transformers")
    V._voice._engine = None
    eng = V._voice._engine_for(V.settings())
    assert isinstance(eng, ET.TransformersWhisperEngine)
    assert V._voice._engine_for(V.settings()) is eng                      # 한 번만 만든다


@pytest.mark.parametrize("engine", ["faster-whisper", "transformers"])
def test_choosing_an_engine_does_not_import_heavy_packages(engine):
    """고르고 만들기만 해서는 torch·transformers·faster_whisper·ctranslate2 를 올리지 않는다 (모델을 올릴 때 비로소). 새 프로세스로 확인한다."""
    code = ("import sys, dataclasses\n"
            "from backend.voice import pipeline as V, settings as S\n"
            f"V.make_engine(dataclasses.replace(S.settings(), engine={engine!r}))\n"
            "print(sorted(m for m in ('torch','transformers','silero_vad','faster_whisper','ctranslate2') if m in sys.modules))\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(C.ROOT), capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-400:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


# ---------------------------------------------------------------- 소리 읽기 (PyAV, 실행기와 무관)
def _wav(seconds: float, rate: int, channels: int = 1, hz: float = 440.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            v = int(12000 * math.sin(2 * math.pi * hz * i / rate))
            frames += struct.pack("<h", v) * channels
        w.writeframes(bytes(frames))
    return buf.getvalue()


def test_decode_audio_returns_16k_mono_float32():
    a = A.decode_audio(_wav(1.0, 16000))
    assert a.dtype.name == "float32" and a.ndim == 1
    assert abs(len(a) - 16000) <= 400                                       # 코덱 여유
    assert 0.2 < float(abs(a).max()) < 0.5                                  # 12000/32768 ≈ 0.37


def test_decode_audio_resamples_and_downmixes():
    a = A.decode_audio(_wav(0.5, 48000, channels=2))
    assert a.ndim == 1 and abs(len(a) - 8000) <= 400


def test_decode_audio_rejects_garbage():
    with pytest.raises(Exception):
        A.decode_audio(b"this is not audio at all" * 50)
    with pytest.raises(Exception):
        A.decode_audio(b"")
