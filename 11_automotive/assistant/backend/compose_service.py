"""문장 입구 — 프로그램이 만든 기본 문장 줄을 받아 다듬은 줄만 돌려준다 (`POST /compose/{kind}`, 2026-10-17).

chat_service의 서비스 키(X-Service-Key)가 그대로 걸린다(`app.include_router(..., dependencies=[Depends(service_key)])`). 호출자는 시연 서버다.
  · 이 입구는 DB·백엔드를 읽지 않는다. 받은 줄만 다듬는다. 줄 안에 사람 이름·사용자 ID·계정 정보가 있으면 보내지 않고 실패한다(privacy.outbound_guard).
  · 외부 LLM(Claude)으로만 간다. 스위치 셋 — ASSISTANT_PROVIDER=claude, EXTERNAL_LLM_APP=1, LLM_ENABLED=1 — 이 모두 맞아야 하고, 하나라도 꺼져 있으면
    외부로 한 글자도 안 보내고 503이다. 로컬 LLM·다른 길로 몰래 바꾸지 않는다.
  · 실패는 모두 503 ASSISTANT_UNAVAILABLE(retryable). 까닭은 서버 로그에만 남기고 응답에는 싣지 않는다. 부른 쪽은 지금의 기본 문장을 그대로 쓴다.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend import config as C
from backend.llm import compose as CMP
from backend.llm import deadline as DL
from backend.llm import external as EXT

log = logging.getLogger("assistant")

router = APIRouter()


class ComposeUnavailable(Exception):
    """이 입구가 다듬은 줄을 줄 수 없다 — chat_service가 503 ASSISTANT_UNAVAILABLE로 바꾼다."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")        # 정해진 칸만 받는다 — 사람·계정 칸을 끼워 보낼 길이 없다
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")
    text: str = Field(min_length=1, max_length=CMP.MAX_IN_CHARS)


class ComposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[LineIn] = Field(min_length=1, max_length=CMP.MAX_LINES)


def _provider_is_claude(env) -> bool:
    return env("ASSISTANT_PROVIDER", "local").strip().lower() == "claude"


@router.post("/compose/{kind}")
def compose(kind: Literal["shift_report", "daily_report", "work_order", "guide_card", "briefing"], req: ComposeRequest) -> dict:
    from backend import chat_service as CS      # 서비스 키 환경을 읽는 함수만 빌려 쓴다(순환 import를 피해 호출 때 import)
    if not _provider_is_claude(CS._env):
        raise ComposeUnavailable("provider is not claude")
    if not C.settings().external_app:
        raise ComposeUnavailable("external switch off")
    try:
        with EXT.external_request("claude"):
            s = C.settings()                     # 외부 모드 값(시간 예산·모델)이 채워진 설정
            if not s.llm_enabled:
                raise ComposeUnavailable("llm disabled")
            with DL.answer_deadline(s.budget_s):
                out = CMP.compose(kind, [{"id": l.id, "text": l.text} for l in req.lines])
    except ComposeUnavailable:
        raise
    except CMP.ComposeFailed as e:
        raise ComposeUnavailable(e.why) from e
    except Exception as e:  # noqa: BLE001 — 안쪽 사정은 로그에만
        raise ComposeUnavailable(type(e).__name__) from e
    return {"kind": kind, "lines": out["lines"], "tries": out["tries"]}
