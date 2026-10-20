"""인식된 글자의 검사와 가벼운 정리 (2026-10-20). 소리·모델을 쓰지 않는 순수 함수 — 시험하기 쉽다.

측정(261003_창민/음성입력_측정_20261020)에서 본 사고를 막는다:
  · 힌트를 주면 무음·소음에서 힌트 문장이 그대로 나오거나("K-A100, LOT-2609-127-1, … 알람, 알람, 알람") 같은 말이 반복된다.
  · 힌트가 없으면 무음에서 "감사합니다."가 나온다 (VAD 가 먼저 막지만 방송 문구류는 한 번 더 거른다).
거절하면 빈 글자와 까닭을 돌려주고, 화면은 "다시 말해 주세요"를 보인다. 사용자 질문을 몰래 고쳐 쓰지는 않는다 — 고치는 것은 코드 표기(공백·하이픈·대소문자)뿐이다.
"""
from __future__ import annotations

import re
import zlib

_SPLIT = re.compile(r"[\s,]+")
_PUNCT = re.compile(r"[\s,.;:!?·…'\"()\[\]{}\-_/\\]+")
# 방송 자막식 환각 문구 (무음·소음 입력에서 Whisper 류가 지어내는 대표 문장)
KNOWN_HALLUCINATIONS = ("시청해 주셔서", "시청해주셔서", "구독과 좋아요", "자막 제공", "자막제공", "다음 영상에서", "MBC 뉴스")
_MINUS = re.compile(r"(?<=[A-Za-z0-9])\s*마이너스\s*(?=[A-Za-z0-9])")
_DASH_SPACE = re.compile(r"(?<=[A-Za-z0-9])\s*-\s*(?=[A-Za-z0-9])")
_CODE = re.compile(r"\b[A-Za-z][A-Za-z0-9]{0,5}(?:-[A-Za-z0-9]+)+\b")


def _squash(s: str) -> str:
    return _PUNCT.sub("", s).lower()


def _words(text: str) -> list[str]:
    return [w for w in _SPLIT.split(text.strip()) if w]


def looks_repeated(text: str) -> bool:
    """같은 낱말이 4번 이상 이어지거나, 2~3 낱말 묶음이 3번 이상 이어지거나, 글이 너무 잘 압축되면(= 반복) 참."""
    w = _words(text)
    run = 1
    for a, b in zip(w, w[1:]):
        run = run + 1 if a == b else 1
        if run >= 4:
            return True
    for n in (2, 3):
        for i in range(len(w) - n * 3 + 1):
            if w[i:i + n] == w[i + n:i + 2 * n] == w[i + 2 * n:i + 3 * n]:
                return True
    raw = text.encode("utf-8")
    return len(raw) >= 60 and len(raw) / max(1, len(zlib.compress(raw))) > 2.6


def is_known_hallucination(text: str) -> bool:
    t = text.strip()
    return any(p in t for p in KNOWN_HALLUCINATIONS)


def is_hint_echo(text: str, hint: str) -> bool:
    """결과가 6낱말 이상이고 그중 70% 이상이 힌트 낱말(또는 그 일부)이면 힌트가 새어 나온 것이다.
    측정에서 본 새어 나옴: "K-A100, LOT-2609, VF2-02, 고전압, 인터록, CMM, 알람" (7낱말 중 6~7개). 앞 일부만 나와도 힌트 낱말에 들어 있으면 센다.
    진짜 질문 "BRK-A100 LOT-2609-127-1 알람 원인이 뭐야?"는 5낱말이고 조사·동사가 섞여 문턱을 넘지 않는다."""
    if not hint:
        return False
    hint_set = {s for s in (_squash(p) for p in _words(hint)) if s}
    toks = [s for s in (_squash(w) for w in _words(text)) if s]
    if len(toks) < 6:
        return False

    def near(t: str) -> bool:
        return t in hint_set or (len(t) >= 4 and any(t in h or h in t for h in hint_set if len(h) >= 4))

    return sum(1 for t in toks if near(t)) / len(toks) >= 0.7


def normalize_codes(text: str) -> str:
    """코드 표기만 가볍게 맞춘다: "A100 마이너스 127" -> "A100-127", "LOT - 2609" -> "LOT-2609", "brk-a100" -> "BRK-A100"."""
    t = _MINUS.sub("-", text)
    t = _DASH_SPACE.sub("-", t)
    t = _CODE.sub(lambda m: m.group(0).upper() if any(c.isdigit() for c in m.group(0)) else m.group(0), t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def postprocess(text: str, hint: str = "") -> tuple[str, str | None]:
    """(글자, 거절 까닭). 거절이면 글자는 빈 글자. 까닭: no_speech | hallucination | repeated | hint_echo"""
    t = (text or "").strip()
    if not t:
        return "", "no_speech"
    if is_known_hallucination(t):
        return "", "hallucination"
    if looks_repeated(t):
        return "", "repeated"
    if is_hint_echo(t, hint):
        return "", "hint_echo"
    return normalize_codes(t), None
