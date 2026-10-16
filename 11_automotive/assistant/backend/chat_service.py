"""AI 비서 서비스 입구 — 기존 백엔드(`11_automotive/backend`)가 `MOM_ASSISTANT_URL`로 부르는 `POST /chat`.

실행: uvicorn backend.chat_service:app --host 127.0.0.1 --port 8100   (assistant/ 폴더에서)

  · 백엔드와 같은 서비스 키(`X-Service-Key` == 환경변수 MOM_ASSISTANT_KEY)가 있어야 받는다. 사람 로그인·`X-Role` 머리말은 쓰지 않는다
    (역할은 백엔드가 로그인으로 확인해 `user.role_code`로 넘긴다). 밖에 열지 말고 127.0.0.1에서만 연다.
  · 요청 칸은 백엔드 계약 그대로(question·context·allowed_tools·out_of_role·history·user). 외부 LLM 선택 칸(`llm`)은 없다 —
    Claude로 보낼지는 서버 설정 ASSISTANT_PROVIDER(=claude)로만 정한다 (분석문서 9.3).
  · 실패는 모두 503 ASSISTANT_UNAVAILABLE (retryable). 모델 이름·CLI 경로·EXTERNAL_LLM_* 같은 안쪽 사정은 응답에 싣지 않는다 (9.3.1).
    백엔드는 비-2xx를 받으면 status = NO_RESPONSE 로 기록하고 화면은 기본 문구를 보인다.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import config as C
from backend.chat_mapping import UnknownStatus, role_gate, to_backend
from backend.llm import external as EXT
from backend.rag.chunker import CorpusError, load_corpus
from backend.services.answer import answer

log = logging.getLogger("assistant")

UNAVAILABLE_MESSAGE = "비서가 지금 답하지 못합니다. 잠시 후 다시 시도해 주세요"
CONTEXT_KEYS = ("screen", "equipment_id", "alarm_key", "alarm_event_id")     # answer()가 보는 화면 문맥 칸 (그 밖의 칸은 버린다)


class Unavailable(Exception):
    """비서가 답할 수 없다 — 까닭은 서버 로그에만 남기고 응답에는 싣지 않는다."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


class UserIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=40)
    role_code: Literal["OPR", "MNT", "SUP", "MGR"]
    home_process_code: str | None = None
    home_process_code_2: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    out_of_role: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)     # 이어 묻기는 첫 판에서 쓰지 않는다 (FOLLOWUP=0)
    user: UserIn


def _env(name: str, default: str = "") -> str:
    return {**C._dotenv(), **os.environ}.get(name, default)


def service_key(x_service_key: str | None = Header(default=None)) -> None:
    expected = _env("MOM_ASSISTANT_KEY")
    if not expected or not x_service_key or not hmac.compare_digest(x_service_key.encode(), expected.encode()):
        raise PermissionError("service key")


# docs_url=None 등: 자동 문서 화면을 열지 않는다 (서비스 키가 필요한 내부 서비스)
app = FastAPI(title="MOM AI 비서 서비스", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(PermissionError)
def _unauthorized(_, __):
    return JSONResponse(status_code=401, content={"code": "UNAUTHORIZED", "message": "서비스 키가 맞지 않음", "detail": {}})


@app.exception_handler(Unavailable)
def _unavailable(_, exc: Unavailable):
    log.warning("비서 응답 실패: %s", exc.why)
    return JSONResponse(status_code=503, content={"code": "ASSISTANT_UNAVAILABLE", "message": UNAVAILABLE_MESSAGE, "detail": {"retryable": True}})


def _context(raw: dict[str, Any]) -> dict[str, str]:
    return {k: str(raw[k]) for k in CONTEXT_KEYS if raw.get(k) not in (None, "")}


def _provider() -> str | None:
    p = _env("ASSISTANT_PROVIDER", "local").strip().lower()
    return "claude" if p == "claude" else None


@app.post("/chat", dependencies=[Depends(service_key)])
def chat(req: ChatRequest) -> dict:
    gated = role_gate(req.question, req.out_of_role)        # 권한 밖 질문은 LLM·조회 없이 값 없는 답
    if gated is not None:
        return gated
    provider = _provider()
    if provider == "claude" and not C.settings().external_app:      # 서버 끄는 스위치 — 꺼져 있으면 외부로 한 글자도 안 보낸다
        raise Unavailable("external switch off")
    try:
        with EXT.external_request(provider) as ext:                  # provider가 None이면 아무것도 안 바뀐다. 끝나면 되돌린다
            a = answer(req.question, req.user.role_code, _context(req.context))
            if ext is not None:
                miss = ext.material_failure()                        # 재료를 정하는 단계의 외부 호출 실패 → 오류 (다른 LLM으로 몰래 바꾸지 않는다)
                if miss:
                    raise Unavailable(f"external material failure: {miss[0]}")
                if ext.polish_failures():                            # 다듬는 단계 실패는 이미 정해진 재료(원문 줄·기본 문장)로 답한 것 — 기록만
                    log.info("외부 LLM 일부 단계 실패: %s", [j for j, _ in ext.polish_failures()])
        return to_backend(a)
    except Unavailable:
        raise
    except UnknownStatus as e:
        raise Unavailable(str(e)) from e
    except Exception as e:      # 답을 만들다 멈춤 (조회 도구 실패 포함) — 안쪽 사정은 로그에만
        raise Unavailable(f"{type(e).__name__}") from e


@app.get("/health", dependencies=[Depends(service_key)])
def health() -> dict:
    try:
        corpus = {"status": "ok", "chunks": len(load_corpus())}
    except CorpusError:
        corpus = {"status": "error"}
    return {"status": "ok", "corpus": corpus, "provider": "claude" if _provider() else "local",
            "external_enabled": C.settings().external_app}
