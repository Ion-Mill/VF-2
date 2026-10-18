"""기존 백엔드(`11_automotive/backend`)의 비서 조회 도구 호출 (읽기 전용) — `POST {MOM_BACKEND_URL}/api/assistant/tools/{name}`.

  · 서비스 키(`X-Service-Key` = MOM_ASSISTANT_KEY)와 "누구를 대신해 묻는지"(`on_behalf_of`)를 같이 보낸다. 백엔드가 그 사용자의 역할 권한으로 거르고
    접근 기록에 남긴다. 비서(LLM)는 SQL을 쓰지 않고 정해진 도구 14개만 쓴다 (FR-AST-COM-14).
  · 누구를 대신하는지·어떤 도구가 허용인지는 요청마다 contextvars로 둔다(전역 변수 금지 — 다음 사용자의 요청으로 새지 않게).
    허용 목록(`allowed_tools`)에 없는 도구는 백엔드를 부르기 전에 ToolDenied로 막는다 (백엔드도 같은 검사를 한다 — 이중).
  · 실패(연결·시간 초과·형식·4xx/5xx)는 BackendToolError. 안쪽 사정은 호출한 쪽(chat_service)이 응답에 싣지 않는다.
"""
from __future__ import annotations

import contextvars
import json
import os
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable

DEFAULT_TIMEOUT_S = 10.0


class BackendToolError(RuntimeError):
    """백엔드 조회 도구를 부르지 못했다 (설정 없음·연결·시간 초과·응답 형식·오류 응답)."""


class ToolDenied(PermissionError):
    """이 사용자에게 허용되지 않은 도구 — 백엔드를 부르지 않는다."""

    def __init__(self, tool: str):
        super().__init__(tool)
        self.tool = tool


@dataclass(frozen=True)
class Caller:
    user_id: str
    allowed: frozenset[str]


@dataclass(frozen=True)
class ToolResult:
    rows: list[dict]
    now: str | None       # 백엔드 업무 시각(app_now) — 답의 "기준 시각"


_caller: contextvars.ContextVar[Caller | None] = contextvars.ContextVar("backend_tool_caller", default=None)


@contextmanager
def acting_as(user_id: str, allowed: Iterable[str]):
    """이 요청 동안 `user_id`를 대신해 `allowed` 도구만 쓴다. 끝나면 반드시 되돌린다."""
    token = _caller.set(Caller(user_id, frozenset(allowed)))
    try:
        yield
    finally:
        _caller.reset(token)


def current() -> Caller | None:
    return _caller.get()


def is_allowed(name: str) -> bool:
    c = _caller.get()
    return c is not None and name in c.allowed


def _env(name: str, default: str = "") -> str:
    from backend import config as C       # 늦게 import — config가 이 폴더의 다른 모듈을 import하지 않게
    return {**C._dotenv(), **os.environ}.get(name, default)


def _post(url: str, headers: dict[str, str], payload: dict, timeout: float) -> Any:
    """HTTP POST(JSON). 시험이 이 함수를 바꿔 끼운다."""
    req = urllib.request.Request(url, method="POST", data=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310 (설정한 내부 주소만)
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise BackendToolError(f"HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise BackendToolError(type(e).__name__) from None


def call_tool(name: str, args: dict | None = None) -> ToolResult:
    c = _caller.get()
    if c is None:
        raise BackendToolError("누구를 대신해 묻는지 정해지지 않음")
    if name not in c.allowed:
        raise ToolDenied(name)
    base, key = _env("MOM_BACKEND_URL").rstrip("/"), _env("MOM_ASSISTANT_KEY")
    if not base or not key:
        raise BackendToolError("MOM_BACKEND_URL·MOM_ASSISTANT_KEY 설정 없음")
    try:
        timeout = float(_env("MOM_BACKEND_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_S
    args = {k: v for k, v in (args or {}).items() if v is not None}
    data = _post(f"{base}/api/assistant/tools/{name}", {"X-Service-Key": key}, {"on_behalf_of": c.user_id, "args": args}, timeout)
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise BackendToolError("응답 형식이 틀림")
    return ToolResult([r for r in data["rows"] if isinstance(r, dict)], data.get("now") if isinstance(data.get("now"), str) else None)
