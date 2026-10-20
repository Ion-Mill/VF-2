"""채팅 음성 입력 설정 (2026-10-20) — assistant/.env 와 환경변수에서 **요청 때마다** 읽는다.

`config.Settings`(큰 데이터클래스)는 건드리지 않는다. 음성은 이 모듈만 읽는다.
스위치 ASSISTANT_VOICE 가 꺼져 있으면(기본) `/transcribe` 는 404 이고 모델을 올리지도 않는다.
모델 이름·장치·계산 형식은 서버를 켤 때 한 번만 쓰인다(바꾸면 비서를 다시 켠다). 나머지는 요청마다 읽는다.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from backend import config as C

# 소리에 자주 나오는 낱말·코드 모양을 인식기에 미리 알려 주는 짧은 글 (측정: 코드가 섞인 질문의 글자 오류율 21.2% -> 4.0%).
# 힌트는 소음·무음에서 그대로 새어 나올 수 있어서 text.is_hint_echo / 반복 검사 / VAD 가 함께 막는다.
DEFAULT_HINT = "BRK-A100, LOT-2609-127-1, VF2-02, 고전압, 인터록, CMM, 알람"
DEVICES = ("cpu", "cuda", "auto")
COMPUTE_TYPES = ("int8", "int8_float16", "int8_float32", "float16", "float32", "default")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,80}$")


def _env(name: str, default: str = "") -> str:
    return {**C._dotenv(), **os.environ}.get(name, default)


def _flag(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class VoiceSettings:
    enabled: bool
    model: str
    device: str
    compute: str
    threads: int          # 0 = 인식 엔진 기본값
    max_seconds: float    # 이보다 긴 소리는 거절(413) — 자르지 않는다
    min_seconds: float    # 이보다 짧으면 인식하지 않고 빈 글자
    max_bytes: int
    timeout_s: float      # 줄 서서 기다린 시간까지 합친 총 제한
    queue_max: int        # 돌고 있는 것 말고 기다릴 수 있는 건수
    hint: str             # 빈 글자 = 힌트 없음


def settings() -> VoiceSettings:
    model = _env("VOICE_MODEL", "large-v3-turbo").strip()
    device = _env("VOICE_DEVICE", "cpu").strip().lower()
    compute = _env("VOICE_COMPUTE", "int8").strip().lower()
    hint_on = _flag(_env("VOICE_HINT", "1"))
    hint_text = _env("VOICE_HINT_TEXT", "").strip() or DEFAULT_HINT
    return VoiceSettings(
        enabled=_flag(_env("ASSISTANT_VOICE", "0")),
        model=model if _MODEL_RE.match(model) else "large-v3-turbo",
        device=device if device in DEVICES else "cpu",
        compute=compute if compute in COMPUTE_TYPES else "int8",
        threads=C._int_clamped(_env("VOICE_THREADS", "0"), 0, 0, 64),
        max_seconds=float(C._int_clamped(_env("VOICE_MAX_SECONDS", "20"), 20, 3, 60)),
        min_seconds=max(0.3, min(3.0, C._float(_env("VOICE_MIN_SECONDS", "0.7"), 0.7))),
        max_bytes=C._int_clamped(_env("VOICE_MAX_BYTES", "1500000"), 1_500_000, 50_000, 10_000_000),
        timeout_s=max(2.0, min(120.0, C._float(_env("VOICE_TIMEOUT_S", "15"), 15.0))),
        queue_max=C._int_clamped(_env("VOICE_QUEUE_MAX", "2"), 2, 0, 20),
        hint=hint_text[:300] if hint_on else "",
    )
