"""소리 원본 바이트 -> 16kHz 모노 float32 배열 (2026-10-20). 실행기와 무관한 모듈 — PyAV(`av`)만 쓴다.

`faster_whisper.audio.decode_audio`와 같은 일을 하지만, 그쪽은 `faster_whisper` 패키지를 import 해야 하고 그러면 CTranslate2가 같이 올라온다.
Transformers 실행기(`engine_transformers`)는 torch 를 쓰므로 한 프로세스에 둘이 같이 올라가지 않게(OpenMP DLL 충돌 위험) 이 모듈을 따로 둔다.
webm/opus·mp4/aac·wav 등 브라우저가 만드는 형식을 FFmpeg 내장판(PyAV)이 읽는다. 시스템에 ffmpeg 가 없어도 된다.
"""
from __future__ import annotations

import gc
import io

import numpy as np

SAMPLE_RATE = 16000


def decode_audio(data: bytes, sampling_rate: int = SAMPLE_RATE) -> np.ndarray:
    """깨진 파일·소리가 없는 파일이면 예외 (pipeline 이 BAD_AUDIO 로 바꾼다)."""
    import av  # noqa: PLC0415 — 소리를 읽을 때만 부른다

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=sampling_rate)
    chunks: list[np.ndarray] = []
    with av.open(io.BytesIO(data), mode="r", metadata_errors="ignore") as container:
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray())
        for out in resampler.resample(None):          # 남은 소리 비우기
            chunks.append(out.to_ndarray())
    del resampler
    gc.collect()                                       # PyAV 리샘플러가 메모리를 늦게 놓는 문제 (faster-whisper 이슈 #390 와 같은 처방)
    if not chunks:
        raise ValueError("no audio frames")
    pcm = np.concatenate([c.reshape(-1) for c in chunks])
    return pcm.astype(np.float32) / 32768.0
