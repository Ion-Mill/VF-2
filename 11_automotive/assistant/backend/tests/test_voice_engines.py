"""채팅 음성 입력 — faster-whisper 설정과 실행기 만들기 (모델은 올리지 않음)."""
import subprocess
import sys

import pytest

from backend import config as C
from backend.voice import pipeline as V
from backend.voice import settings as S
from backend.voice.engine import FasterWhisperEngine

pytestmark = pytest.mark.own_backend


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    for k in ("ASSISTANT_VOICE", "VOICE_MODEL", "VOICE_DEVICE", "VOICE_COMPUTE", "VOICE_THREADS",
              "VOICE_HINT", "VOICE_HINT_TEXT", "VOICE_MAX_SECONDS", "VOICE_TIMEOUT_S"):
        monkeypatch.delenv(k, raising=False)
    yield
    V._voice._engine = None


def test_model_name_with_slash_is_accepted(monkeypatch):
    monkeypatch.setenv("VOICE_MODEL", "Systran/faster-whisper-large-v3-turbo")
    assert S.settings().model == "Systran/faster-whisper-large-v3-turbo"


def test_max_seconds_default_is_60_and_shorter_values_are_kept(monkeypatch):
    assert (S.settings().max_seconds, S.settings().timeout_s) == (60.0, 40.0)
    monkeypatch.setenv("VOICE_MAX_SECONDS", "20")
    assert S.settings().max_seconds == 20.0


def test_max_seconds_is_clamped_to_60(monkeypatch):
    monkeypatch.setenv("VOICE_MAX_SECONDS", "999")
    assert S.settings().max_seconds == 60.0


def test_make_engine_is_faster_whisper():
    assert isinstance(V.make_engine(S.settings()), FasterWhisperEngine)


def test_creating_engine_does_not_import_heavy_packages():
    code = (
        "import sys\n"
        "from backend.voice import pipeline as V, settings as S\n"
        "V.make_engine(S.settings())\n"
        "print(sorted(m for m in ('torch','transformers','silero_vad','faster_whisper','ctranslate2') if m in sys.modules))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=str(C.ROOT), capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-400:]
    assert out.stdout.strip().splitlines()[-1] == "[]"
