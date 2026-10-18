"""한 답 전체의 LLM 시간 예산 (2026-10-10 계획 3단계 B).

예전: 작업(분류·줄 고르기·다듬기)마다 예산을 따로 셌고, 읽기 시간 초과는 차단기를 켜지 않아
한 답이 15초(LLM_BUDGET_S)를 넘을 수 있었다.
지금: answer() 시작에 Deadline을 하나 만들고(contextvars — 요청마다 따로), 모든 LLM 호출이 남은 시간 안에서만 기다린다.
남은 시간이 한 번 부를 만큼(MIN_CALL_S)도 없으면 부르지 않고, 부른 쪽이 기본 문장을 쓴다.
"""
from __future__ import annotations

import contextvars
import time
from collections.abc import Iterator
from contextlib import contextmanager

MIN_CALL_S = 2.0   # 이보다 적게 남으면 LLM을 부르지 않는다
MARGIN_S = 0.3     # 답을 마무리할 몫


class Deadline:
    def __init__(self, budget_s: float):
        self.budget_s = budget_s
        self.t0 = time.monotonic()

    def left(self) -> float:
        return self.budget_s - (time.monotonic() - self.t0)

    def timeout_for(self, read_s: float) -> float | None:
        """이번 호출에 기다릴 시간(초). 모자라면 None — 부르지 않는다."""
        t = min(read_s, self.left() - MARGIN_S)
        return t if t >= MIN_CALL_S else None


_current: contextvars.ContextVar[Deadline | None] = contextvars.ContextVar("llm_deadline", default=None)


@contextmanager
def answer_deadline(budget_s: float) -> Iterator[Deadline]:
    """한 답을 만드는 동안 쓸 예산. 안에서 부르는 chat_json이 이 예산을 본다."""
    token = _current.set(Deadline(budget_s))
    try:
        yield _current.get()
    finally:
        _current.reset(token)


def current() -> Deadline | None:
    return _current.get()
