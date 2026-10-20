"""음성 인식 엔진 — faster-whisper (CTranslate2) 를 사내 서버에서 돌린다 (2026-10-20, 사용자 결정: 자체 서버·CPU).

소리는 이 PC 밖으로 나가지 않는다. 모델 파일은 처음 한 번 Hugging Face 에서 내려받는다(large-v3-turbo 약 1.6GB) —
스위치를 켜기 전에 미리 받아 두는 절차는 실행_안내.md 에 있다.
faster-whisper·av 는 **이 파일 안에서만, 모델을 올릴 때만** import 한다 (스위치가 꺼져 있거나 패키지가 없어도 비서는 그대로 돈다).

엔진 계약(시험의 가짜 엔진도 같다):
    ready -> bool                         모델이 올라와 있나
    load() -> None                        모델 올리기 (여러 번 불러도 한 번만)
    decode(data: bytes) -> 1차원 float32 배열, 16kHz 모노 (webm/opus·mp4·wav 등을 읽는다)
    transcribe(samples, hint: str) -> str
"""
from __future__ import annotations

import io
import threading
from typing import Any

from backend.voice.settings import VoiceSettings

SAMPLE_RATE = 16000
MAX_NEW_TOKENS = 160     # 20초 안쪽 발화에 넉넉한 값. 같은 말을 끝없이 되풀이하는 환각의 길이를 이 값으로 묶는다


class FasterWhisperEngine:
    def __init__(self, s: VoiceSettings):
        self._s = s
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel      # noqa: PLC0415 — 모델을 올릴 때만 부른다
            kw: dict[str, Any] = {"device": self._s.device, "compute_type": self._s.compute}
            if self._s.threads:
                kw["cpu_threads"] = self._s.threads
            self._model = WhisperModel(self._s.model, **kw)

    def decode(self, data: bytes):
        from faster_whisper.audio import decode_audio    # noqa: PLC0415 — av 로 읽는다
        return decode_audio(io.BytesIO(data), sampling_rate=SAMPLE_RATE)

    def transcribe(self, samples, hint: str) -> str:
        self.load()
        # temperature=0.0 한 번만: 기본값은 실패 때 온도를 올려 다시 돌려서 소음 입력이 20초대까지 늘어졌다 (측정). 반복은 text.looks_repeated 가 거른다.
        kw: dict[str, Any] = dict(
            language="ko", beam_size=5, condition_on_previous_text=False, temperature=0.0,
            vad_filter=True, max_new_tokens=MAX_NEW_TOKENS,
        )
        if hint:
            kw["initial_prompt"] = hint
        segments, _info = self._model.transcribe(samples, **kw)
        return " ".join(seg.text.strip() for seg in segments).strip()
