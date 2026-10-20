"""채팅 음성 입력 처리 줄 (2026-10-20) — 크기·길이 검사 → 디코딩 → 인식 → 글자 검사.

  · 한 번에 1건만 돌린다(CPU 한 건 약 4~5초, 측정). 기다릴 수 있는 건수는 VOICE_QUEUE_MAX, 넘으면 429.
  · 줄 선 시간까지 합쳐 VOICE_TIMEOUT_S 안에 못 끝내면 503 VOICE_TIMEOUT. 돌고 있던 일은 끝까지 돌지만(끊을 수 없다) 기다리던 일은 건너뛴다.
  · 소리는 메모리에서만 쓰고 저장하지 않는다. 로그에는 길이·걸린 시간·글자 수만 남기고 **글자 내용은 남기지 않는다**.
  · 스위치(ASSISTANT_VOICE)가 꺼져 있으면 404 VOICE_OFF — 모델도 올리지 않는다.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from backend.voice import text as T
from backend.voice.engine import SAMPLE_RATE, FasterWhisperEngine
from backend.voice.settings import VoiceSettings, settings

log = logging.getLogger("assistant")


class VoiceError(Exception):
    """음성 입구 실패 — chat_service 가 이 상태 코드·코드 이름의 JSON 으로 바꾼다. 안쪽 사정(모델 경로 등)은 싣지 않는다."""

    def __init__(self, code: str, status: int, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.status, self.message = code, status, message


def _err(code: str) -> VoiceError:
    return VoiceError(code, *_ERRORS[code])


_ERRORS = {
    "VOICE_OFF": (404, "음성 입력이 꺼져 있습니다"),
    "EMPTY_AUDIO": (400, "소리가 비어 있습니다"),
    "BAD_AUDIO": (400, "소리를 읽지 못했습니다. 다시 녹음해 주세요"),
    "AUDIO_TOO_LARGE": (413, "녹음이 너무 큽니다"),
    "AUDIO_TOO_LONG": (413, "녹음이 너무 깁니다. 짧게 나눠 말해 주세요"),
    "VOICE_BUSY": (429, "지금 다른 음성을 처리 중입니다. 잠시 후 다시 시도해 주세요"),
    "VOICE_TIMEOUT": (503, "음성 인식이 오래 걸려 멈췄습니다. 다시 시도해 주세요"),
    "VOICE_FAILED": (503, "음성 인식에 실패했습니다. 잠시 후 다시 시도해 주세요"),
}


class Voice:
    def __init__(self) -> None:
        self._engine: Any = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")
        self._lock = threading.Lock()
        self._pending = 0

    # ------------------------------------------------------------ 시험이 바꾸는 곳
    def set_engine(self, engine: Any) -> None:
        self._engine = engine

    def _engine_for(self, s: VoiceSettings) -> Any:
        if self._engine is None:
            self._engine = FasterWhisperEngine(s)
        return self._engine

    # ------------------------------------------------------------ 상태·미리 올리기
    def status(self) -> dict:
        s = settings()
        return {"enabled": s.enabled, "ready": bool(s.enabled and self._engine is not None and self._engine.ready),
                "max_seconds": s.max_seconds}

    def preload(self) -> None:
        """서버를 켤 때 스위치가 켜져 있으면 모델을 미리 올린다 (첫 질문이 느려지지 않게). 기다리지 않는다."""
        s = settings()
        if not s.enabled:
            return

        def _load() -> None:
            try:
                t0 = time.monotonic()
                self._engine_for(s).load()
                log.info("음성 모델 준비: %.1f초", time.monotonic() - t0)
            except Exception as e:  # noqa: BLE001 — 패키지·모델 파일 문제는 로그에만. 요청이 오면 VOICE_FAILED 로 답한다
                log.warning("음성 모델 준비 실패: %s", type(e).__name__)

        self._pool.submit(_load)

    # ------------------------------------------------------------ 인식
    def transcribe(self, data: bytes) -> dict:
        s = settings()
        if not s.enabled:
            raise _err("VOICE_OFF")
        if not data:
            raise _err("EMPTY_AUDIO")
        if len(data) > s.max_bytes:
            raise _err("AUDIO_TOO_LARGE")
        with self._lock:
            if self._pending > s.queue_max:      # 돌고 있는 1건 + 기다리는 queue_max 건까지
                raise _err("VOICE_BUSY")
            self._pending += 1
        deadline = time.monotonic() + s.timeout_s
        fut = self._pool.submit(self._job, data, s, deadline)
        try:
            return fut.result(timeout=s.timeout_s)
        except FutureTimeout:
            log.warning("음성 인식 시간 초과(%.0f초)", s.timeout_s)
            raise _err("VOICE_TIMEOUT") from None
        except VoiceError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("음성 인식 실패: %s", type(e).__name__)
            raise _err("VOICE_FAILED") from e

    def _job(self, data: bytes, s: VoiceSettings, deadline: float) -> dict:
        try:
            if time.monotonic() > deadline:          # 줄에서 기다리다 이미 시간이 지났다 — 돌리지 않는다
                raise _err("VOICE_TIMEOUT")
            t0 = time.monotonic()
            eng = self._engine_for(s)
            try:
                samples = eng.decode(data)
            except Exception as e:  # noqa: BLE001 — 깨진 파일·모르는 형식
                log.info("음성 디코딩 실패: %s", type(e).__name__)
                raise _err("BAD_AUDIO") from e
            seconds = len(samples) / SAMPLE_RATE
            if seconds > s.max_seconds:
                raise _err("AUDIO_TOO_LONG")
            if seconds < s.min_seconds:
                return {"text": "", "reason": "too_short", "seconds": round(seconds, 2), "ms": int((time.monotonic() - t0) * 1000)}
            raw = eng.transcribe(samples, s.hint)
            text, reason = T.postprocess(raw, s.hint)
            ms = int((time.monotonic() - t0) * 1000)
            log.info("음성 인식 %.1f초 소리 → %d ms, %d자%s", seconds, ms, len(text), f" (거절: {reason})" if reason else "")
            return {"text": text, "reason": reason, "seconds": round(seconds, 2), "ms": ms}
        finally:
            with self._lock:
                self._pending -= 1


_voice = Voice()
transcribe = _voice.transcribe
status = _voice.status
preload = _voice.preload
set_engine = _voice.set_engine
