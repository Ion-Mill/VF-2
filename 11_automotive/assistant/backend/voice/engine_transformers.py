"""원본 Whisper 저장소를 PyTorch(Transformers)로 CPU에서 돌리는 실행기 (2026-10-20, 사용자 결정 "원본 openai/whisper-large-v3, fp32, CPU").

선택용이다: `VOICE_ENGINE=transformers` 일 때만 쓰이고, 기본은 faster-whisper(engine.py)다. **한 프로세스에 faster-whisper(ctranslate2)와 torch 를 같이 올리지 않는다**
(둘 다 OpenMP DLL `libiomp5md.dll` 을 가져서 "OMP Error #15"가 날 수 있다) — pipeline 이 설정에 따라 둘 중 하나만 만든다. torch·transformers·silero_vad 는 **모델을 올릴 때만** import 한다.

엔진 계약은 engine.py 와 같다 (ready / load / decode / transcribe).
  · 모델: `openai/whisper-large-v3` (Hugging Face 공식 페이지). 개정(커밋) 고정 — 가중치가 몰래 바뀌지 않게. `model.safetensors`(fp16, 약 3.1GB)를 받아 **fp32로 올린다**
    (모델 카드의 CPU 예시와 같음. Transformers 5.x 는 `dtype` 기본이 "auto"라 이 파일의 fp16 이 그대로 올라오므로 **반드시 직접 지정**한다).
  · 힌트(initial_prompt) = `processor.get_prompt_ids`, 언어 `ko`, 빔 5, `max_new_tokens=160`. 온도 목록은 넘기지 않는다 — 재시도(온도 올리기) 반복이 없다.
  · 무음: faster-whisper 의 내장 VAD 가 없으므로 silero-vad 로 앞뒤 무음을 자른다. 말이 하나도 없으면 인식하지 않고 빈 글자("no_speech").
  · 소리 읽기는 audio.py (PyAV).
"""
from __future__ import annotations

import threading
from typing import Any

from backend.voice.audio import SAMPLE_RATE, decode_audio
from backend.voice.settings import VoiceSettings

MAX_NEW_TOKENS = 160
OPENAI_LARGE_V3 = "openai/whisper-large-v3"
# 2024-08-12 마지막 커밋 (Hugging Face 저장소 기록). 가중치 파일 model.safetensors 의 LFS sha256 = a8e94b85976e5864ba3e9525c7e6c83b2a1eca42d4b797a0c7c24d778e40fd95
OPENAI_LARGE_V3_REVISION = "06f233fe06e710322aca913c1bc4249a0d71fce1"
_ALIASES = {"large-v3": OPENAI_LARGE_V3, "large-v3-turbo": "openai/whisper-large-v3-turbo"}
VAD_PAD_MS = 400                 # 말 앞뒤로 남기는 여유 (faster-whisper VAD 기본과 같음)
MIN_SPEECH_MS = 250


def resolve_model(model: str, revision: str) -> tuple[str, str | None]:
    """(저장소 이름, 개정). `large-v3` 같은 짧은 이름은 openai 저장소로, 모르는 짧은 이름은 openai/whisper-large-v3 로.
    개정은 설정값이 있으면 그것, 없으면 openai/whisper-large-v3 에 한해 고정 커밋, 그 밖은 None(= 저장소 기본)."""
    repo = _ALIASES.get(model, model)
    if "/" not in repo:
        repo = OPENAI_LARGE_V3
    return repo, (revision or (OPENAI_LARGE_V3_REVISION if repo == OPENAI_LARGE_V3 else None))


class TransformersWhisperEngine:
    def __init__(self, s: VoiceSettings):
        self._s = s
        self._lock = threading.Lock()
        self._model: Any = None
        self._processor: Any = None
        self._vad: Any = None
        self._torch: Any = None
        self._dtype: Any = None
        self._get_speech_timestamps: Any = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            import torch  # noqa: PLC0415 — 모델을 올릴 때만 부른다 (스위치가 꺼져 있거나 faster-whisper 면 import 하지 않음)
            from silero_vad import get_speech_timestamps, load_silero_vad  # noqa: PLC0415
            from transformers import WhisperForConditionalGeneration, WhisperProcessor  # noqa: PLC0415
            from transformers.utils import logging as hf_logging  # noqa: PLC0415

            hf_logging.set_verbosity_error()          # 요청마다 반복되는 경고(max_new_tokens 와 max_length 동시 지정 등)로 로그가 넘치지 않게
            if self._s.threads:
                torch.set_num_threads(self._s.threads)
            repo, revision = resolve_model(self._s.model, self._s.revision)
            dtype = torch.bfloat16 if self._s.dtype == "bfloat16" else torch.float32
            kw: dict[str, Any] = {"use_safetensors": True, "local_files_only": self._s.local_only}
            if revision:
                kw["revision"] = revision
            model = WhisperForConditionalGeneration.from_pretrained(repo, dtype=dtype, **kw)    # 5.x: torch_dtype 가 아니라 dtype. 직접 지정 필수
            model.eval()
            self._processor = WhisperProcessor.from_pretrained(repo, **kw)
            self._vad = load_silero_vad()             # 패키지에 들어 있는 모델 (내려받기 없음)
            self._get_speech_timestamps = get_speech_timestamps
            self._torch = torch
            self._dtype = dtype
            self._model = model                       # 맨 마지막에 — ready 가 참이 되는 시점

    def decode(self, data: bytes):
        return decode_audio(data)

    def _trim(self, audio):
        """앞뒤 무음을 자른다. 말이 없으면 None."""
        torch = self._torch
        stamps = self._get_speech_timestamps(torch.from_numpy(audio), self._vad, sampling_rate=SAMPLE_RATE,
                                             min_speech_duration_ms=MIN_SPEECH_MS, speech_pad_ms=VAD_PAD_MS)
        if not stamps:
            return None
        return audio[max(0, int(stamps[0]["start"])): min(len(audio), int(stamps[-1]["end"]))]

    def transcribe(self, samples, hint: str) -> str:
        self.load()
        import numpy as np  # noqa: PLC0415
        torch = self._torch
        audio = self._trim(np.asarray(samples, dtype=np.float32))
        if audio is None:
            return ""
        proc = self._processor
        feats = proc(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt", return_attention_mask=True)
        gen: dict[str, Any] = dict(language="ko", task="transcribe", num_beams=5, do_sample=False, max_new_tokens=MAX_NEW_TOKENS)
        if hint:
            gen["prompt_ids"] = proc.get_prompt_ids(hint, return_tensors="pt")
        with torch.inference_mode():
            ids = self._model.generate(feats.input_features.to(self._dtype), attention_mask=feats.attention_mask, **gen)
        text = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
        if hint and text.startswith(hint):            # 힌트가 결과 앞에 그대로 붙어 나오는 경우를 막는다
            text = text[len(hint):].strip()
        return text
