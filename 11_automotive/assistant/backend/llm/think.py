"""Qwen "깊게 생각" 버튼의 요청 단위 상태 (2026-10-15 사용자 결정 — 생각 예산 6,000토큰, 버튼으로 켜고 끈다).

비서 창에서 버튼을 누른 요청은 **그 요청 안에서만** 생각을 켠다(contextvars — `external.py`·`deadline.py`와 같은 방식).
`config.settings()`가 `override()`를 읽어 생각 예산·시간 예산을 채우고, `client.chat_json`이 그 값으로 요청 본문을 만든다.
값이 없으면(기본) 아무것도 바뀌지 않는다 — 꺼진 상태의 요청 본문은 예전과 한 글자도 다르지 않다.

- 생각은 문법(GBNF) 없는 JSON 스키마 호출(분류·줄 고르기·따로 검증·뜻 판정)에서만 켠다. 새 글 쓰기(문법 길)는 켜면 답이 생각 칸으로 들어가 본문이 비므로 켜지 않는다
  (2026-10-15 사전 확인 `Qwen_생각켜기_확인_20261015.md`, llama.cpp #20345).
- 깊은 생각 요청은 **동시에 하나만** 받는다(서버가 `--parallel 2`라 4~5분짜리가 겹치면 다른 질문이 막힌다).
이 모듈은 backend의 다른 모듈을 import하지 않는다(config가 이 모듈을 import하므로 순환을 막는다).
"""
from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager
from dataclasses import dataclass

DEEP_BUDGET = 6000        # 켜졌을 때 생각 예산(토큰). 서버는 0(끔)과 이 값만 받는다 — 사용자 결정 2026-10-15 (12,000 → 6,000)
DEEP_READ_S = 180.0       # 호출 하나를 기다리는 시간. 6,000토큰 ≈ 1분 [추정: 4,096토큰 38.6초·12,000토큰 115.7초 실측에서 환산] + 여유
DEEP_BUDGET_S = 900.0     # 한 답 전체. 생각을 켠 호출 4~5번 ≈ 5분 + 여유


@dataclass
class ThinkRequest:
    budget: int
    calls: int = 0        # 생각을 켜서 보낸 호출 수(실패 포함). 0이면 규칙만으로 답했거나 문법 길뿐이었다 — 화면이 사실대로 표시한다
    failures: int = 0     # 그중 실패(연결·시간 초과·형식 오류) — 그 단계는 기본 동작(원문 줄·기본 문장)으로 돌아갔다


_current: contextvars.ContextVar[ThinkRequest | None] = contextvars.ContextVar("think_request", default=None)
_busy = threading.Lock()   # 깊은 생각 요청 동시 1개


def current() -> ThinkRequest | None:
    return _current.get()


def override() -> int:
    """이 요청이 고른 생각 예산(켜졌으면 DEEP_BUDGET, 아니면 0)."""
    r = _current.get()
    return r.budget if r else 0


@contextmanager
def think_request(budget: int | None):
    """budget이 DEEP_BUDGET일 때만 요청 상태를 만든다. 그 밖에는 아무것도 안 하고 None을 돌려준다. 끝나면 반드시 되돌린다(다음 요청에 새지 않게)."""
    if budget != DEEP_BUDGET:
        yield None
        return
    req = ThinkRequest(budget=budget)
    token = _current.set(req)
    try:
        yield req
    finally:
        _current.reset(token)


def note_call() -> None:
    r = _current.get()
    if r is not None:
        r.calls += 1


def note_failure() -> None:
    r = _current.get()
    if r is not None:
        r.failures += 1


def try_acquire() -> bool:
    """깊은 생각 자리를 기다리지 않고 잡는다. 이미 하나가 돌고 있으면 False."""
    return _busy.acquire(blocking=False)


def release() -> None:
    try:
        _busy.release()
    except RuntimeError:   # 잡지 않은 자리를 놓으려 한 경우 — 상태를 깨지 않는다
        pass


def busy() -> bool:
    return _busy.locked()
