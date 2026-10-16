"""외부 LLM 선택 스위치의 요청 단위 상태 (2026-10-15, `research_notes/외부LLM_스위치_최종기획서_20261014.md` 4절·5.1절).

비서 창 스위치에서 "Claude"를 고른 요청은 이 요청 안에서만 공급자가 바뀐다(contextvars — 요청마다 따로, `deadline.py`와 같은 방식).
`config.settings()`가 `override()`를 읽어 공급자·모델·시간 예산을 채우므로 모든 LLM 호출(분류·줄 고르기·검증·새 글·판정 …)이 같이 바뀐다.
값이 없으면(기본) 아무것도 바뀌지 않는다 — 로컬 Qwen 동작은 한 글자도 달라지지 않는다.

이 모듈은 backend의 다른 모듈을 import하지 않는다(config가 이 모듈을 import하므로 순환을 막는다).
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field

# 재료를 정하는 단계 — 외부 호출이 실패하면 오류(`EXTERNAL_LLM_UNAVAILABLE`)로 끝낸다 (최종기획서 4.3절, 사용자 결정 Q3).
# 그 밖의 호출(새 글 쓰기·뜻 판정·다듬기 …)은 실패해도 이미 정해진 재료로 지금의 안전한 폴백(원문 줄·기본 문장)으로 답한다.
# 2026-10-15 PURE_EXTERNAL: 순수 길의 외부 호출 "pure_answer"도 답 전체가 이 호출 하나라 실패하면 오류로 끝낸다(자동 대체 없음)
MATERIAL_JOBS = frozenset({"route", "select", "verify", "pure_answer"})


class ExternalLlmFailure(Exception):
    """재료를 정하는 단계의 외부 호출 실패. LlmUnavailable·LlmBadOutput이 아니라서 jobs.py의 폴백에 잡히지 않고 앱 입구까지 올라간다."""

    def __init__(self, job: str, reason: str):
        super().__init__(f"{job}: {reason}")
        self.job, self.reason = job, reason


@dataclass
class ExternalRequest:
    provider: str
    failures: list[tuple[str, str]] = field(default_factory=list)   # (작업 이름, 까닭) — 외부 호출이 실패한 것 전부
    calls: int = 0   # 이 요청에서 외부로 보내려고 한 호출 수(실패 포함). 0이면 규칙만으로 답한 것 — 화면이 "외부 LLM이 답함"이라고 거짓 표시하지 않게 한다

    def material_failure(self) -> tuple[str, str] | None:
        return next(((j, r) for j, r in self.failures if j in MATERIAL_JOBS), None)

    def polish_failures(self) -> list[tuple[str, str]]:
        return [(j, r) for j, r in self.failures if j not in MATERIAL_JOBS]


_current: contextvars.ContextVar[ExternalRequest | None] = contextvars.ContextVar("external_request", default=None)


def current() -> ExternalRequest | None:
    return _current.get()


def override() -> str | None:
    """이 요청이 고른 공급자('claude') 또는 None(= 서버 기본, 로컬)."""
    r = _current.get()
    return r.provider if r else None


@contextmanager
def external_request(provider: str | None):
    """provider가 'claude'일 때만 요청 상태를 만든다. 그 밖에는 아무것도 안 하고 None을 돌려준다. 끝나면 반드시 되돌린다(다음 요청에 새지 않게)."""
    if provider != "claude":
        yield None
        return
    req = ExternalRequest(provider="claude")
    token = _current.set(req)
    try:
        yield req
    finally:
        _current.reset(token)


def note_call() -> None:
    r = _current.get()
    if r is not None:
        r.calls += 1


def note_failure(job: str, reason: str) -> None:
    r = _current.get()
    if r is not None:
        r.failures.append((job, reason))
