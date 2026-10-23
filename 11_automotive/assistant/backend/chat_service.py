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
import re
import threading
import time
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import compose_service as CMPS
from backend import work_record_service as WRS
from backend import config as C
from backend import voice_service as VOICE
from backend.voice.pipeline import VoiceError
from backend.chat_mapping import UnknownStatus, role_gate, to_backend
from backend.llm import external as EXT
from backend.rag.chunker import CorpusError, load_corpus
from backend.repositories import backend_tools as BT
from backend.safety import fixed_block as FB
from backend.services.answer import answer
from backend.tools.query_tools import ToolInputError

log = logging.getLogger("assistant")

UNAVAILABLE_MESSAGE = "비서가 지금 답하지 못합니다. 잠시 후 다시 시도해 주세요"
DENIED_ANSWER = "이 정보는 지금 역할로는 볼 수 없어요. 값은 알려 드리지 않습니다. 권한이 있는 담당자에게 물어봐 주세요."
CONTEXT_KEYS = ("screen", "equipment_id", "alarm_key", "alarm_event_id", "new_chat")     # answer()가 보는 화면 문맥 칸 (그 밖의 칸은 버린다)


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
    screen_text: str | None = Field(None, max_length=8000, description="화면 정보판 글자. context에 넣지 않는다. 채팅 기록에도 저장하지 않는다.")


def _env(name: str, default: str = "") -> str:
    return {**C._dotenv(), **os.environ}.get(name, default)


def service_key(x_service_key: str | None = Header(default=None)) -> None:
    expected = _env("MOM_ASSISTANT_KEY")
    if not expected or not x_service_key or not hmac.compare_digest(x_service_key.encode(), expected.encode()):
        raise PermissionError("service key")


# docs_url=None 등: 자동 문서 화면을 열지 않는다 (서비스 키가 필요한 내부 서비스)
app = FastAPI(title="MOM AI 비서 서비스", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None, lifespan=VOICE.lifespan)


@app.exception_handler(PermissionError)
def _unauthorized(_, __):
    return JSONResponse(status_code=401, content={"code": "UNAUTHORIZED", "message": "서비스 키가 맞지 않음", "detail": {}})


@app.exception_handler(Unavailable)
def _unavailable(_, exc: Unavailable):
    log.warning("비서 응답 실패: %s", exc.why)
    return JSONResponse(status_code=503, content={"code": "ASSISTANT_UNAVAILABLE", "message": UNAVAILABLE_MESSAGE, "detail": {"retryable": True}})


@app.exception_handler(WRS.AssistUnavailable)
def _assist_unavailable(_, exc: WRS.AssistUnavailable):
    log.warning("메모 정리 입구 실패: %s", exc.why)
    return JSONResponse(status_code=503, content={"code": "ASSISTANT_UNAVAILABLE", "message": UNAVAILABLE_MESSAGE, "detail": {"retryable": True}})


@app.exception_handler(VoiceError)
def _voice_error(_, exc: VoiceError):
    log.info("음성 입구: %s", exc.code)
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "detail": {}})


@app.exception_handler(CMPS.ComposeUnavailable)
def _compose_unavailable(_, exc: CMPS.ComposeUnavailable):
    log.warning("문장 입구 실패: %s", exc.why)
    return JSONResponse(status_code=503, content={"code": "ASSISTANT_UNAVAILABLE", "message": UNAVAILABLE_MESSAGE, "detail": {"retryable": True}})


# ---------------------------------------------------------------- 앞 답 보관 (이어 묻기, FOLLOWUP=1, 2026-10-18)
# answer()는 FOLLOWUP=1일 때 답에 내부 칸 `_followup`(이 답의 기록)을 붙이고, 다음 질문에서 prev로 받아 "방금 내용 쉽게"·"짧게"·"다시"에 쓴다.
# 비서 서비스가 사용자별로 바로 앞 답 하나만 PREV_TTL_S 동안 메모리에 두고 다시 넘긴다 (재시작하면 사라진다 — DB에 안 쓴다). 화면에는 보내지 않는다.
# 화면이 새 대화의 첫 질문에 context.new_chat="1"을 실으면 보관한 것을 지운다.
PREV_TTL_S = 1800
PREV_MAX_USERS = 500
_now = time.monotonic
_prev_lock = threading.Lock()
_prev: dict[str, tuple[float, dict]] = {}


def _prev_take(user_id: str, new_chat: bool) -> dict | None:
    with _prev_lock:
        if new_chat:
            _prev.pop(user_id, None)
            return None
        hit = _prev.get(user_id)
        if hit is None:
            return None
        if _now() - hit[0] > PREV_TTL_S:
            _prev.pop(user_id, None)
            return None
        return hit[1]


# 상태 되묻기 다음 글 (2026-10-22). FOLLOWUP이 꺼져 있어도, 상태 빈 칸을 물은 답 하나만 기억해 다음 글에 한 번 넘긴다.
_status_prev: dict[str, tuple[float, dict]] = {}


def _status_prev_take(user_id: str, new_chat: bool) -> dict | None:
    with _prev_lock:
        if new_chat:
            _status_prev.pop(user_id, None)
            return None
        hit = _status_prev.pop(user_id, None)
        if hit is None or _now() - hit[0] > PREV_TTL_S:
            return None
        return hit[1]


def _status_prev_keep(user_id: str, rec: dict) -> None:
    with _prev_lock:
        _status_prev[user_id] = (_now(), rec)


def _prev_keep(user_id: str, rec: dict | None) -> None:
    if rec is None:
        return
    with _prev_lock:
        _prev[user_id] = (_now(), rec)
        if len(_prev) > PREV_MAX_USERS:
            _prev.pop(min(_prev, key=lambda k: _prev[k][0]), None)


def _context(raw: dict[str, Any]) -> dict[str, str]:
    return {k: str(raw[k]) for k in CONTEXT_KEYS if raw.get(k) not in (None, "")}


def _provider() -> str | None:
    p = _env("ASSISTANT_PROVIDER", "local").strip().lower()
    return "claude" if p == "claude" else None


SENSOR_WORDS = re.compile(r"센서|추세")


def _gate_list(question: str, out_of_role: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """권한 문에 넘길 목록. 안전 서식 질문(잠금·고전압·보호구)은 센서 문에서 뺀다 — "고전압 대기는 몇 분 기다려야 해?"의 `전압`·`몇`이
    센서 값 질문으로 읽혀 반장·작업자의 안전 질문이 막혔다 (2026-10-21 시연). 센서·추세를 직접 말하면 빼지 않고, MTTR 문은 그대로다.
    센서 값은 `allowed_tools`에서 한 번 더 막힌다 — 이 면제는 친절한 거절 문구만 건너뛴다."""
    if FB.select(question) and not SENSOR_WORDS.search(question):
        return [i for i in out_of_role if i.get("tool") != "sensor_trend"]
    return out_of_role


@app.post("/chat", dependencies=[Depends(service_key)])
def chat(req: ChatRequest) -> dict:
    gated = role_gate(req.question, _gate_list(req.question, req.out_of_role))        # 권한 밖 질문은 LLM·조회 없이 값 없는 답
    if gated is not None:
        return gated
    provider = _provider()
    if provider == "claude" and not C.settings().external_app:      # 서버 끄는 스위치 — 꺼져 있으면 외부로 한 글자도 안 보낸다
        raise Unavailable("external switch off")
    try:
        # 누구를 대신해 묻는지·허용 도구는 이 요청 안에서만 (contextvars) — 허용 목록에 없는 조회 도구는 백엔드를 부르기 전에 막는다
        with BT.acting_as(req.user.user_id, req.allowed_tools), EXT.external_request(provider) as ext:   # provider가 None이면 아무것도 안 바뀐다. 끝나면 되돌린다
            ctx = _context(req.context)
            keep_prev = C.settings().followup
            new_chat = ctx.get("new_chat") == "1"
            prev = _prev_take(req.user.user_id, new_chat) if keep_prev else _status_prev_take(req.user.user_id, new_chat)
            a = answer(req.question, req.user.role_code, ctx, prev=prev, screen_text=req.screen_text)
            rec = a.pop("_followup", None)      # 화면·백엔드로 나가지 않는다
            status_rec = a.pop("_status_ask", None)
            if keep_prev:
                _prev_keep(req.user.user_id, rec)
            elif status_rec:
                _status_prev_keep(req.user.user_id, status_rec)
            if ext is not None:
                miss = ext.material_failure()                        # 재료를 정하는 단계의 외부 호출 실패 → 오류 (다른 LLM으로 몰래 바꾸지 않는다)
                if miss:
                    raise Unavailable(f"external material failure: {miss[0]}")
                if ext.polish_failures():                            # 다듬는 단계 실패는 이미 정해진 재료(원문 줄·기본 문장)로 답한 것 — 기록만
                    log.info("외부 LLM 일부 단계 실패: %s", [j for j, _ in ext.polish_failures()])
        return to_backend(a)
    except Unavailable:
        raise
    except BT.ToolDenied as e:      # 이 역할에 허용되지 않은 조회 — 값 없이 권한 밖으로 답한다 (사람 이름·값을 섞어 보내지 않는다)
        log.info("권한 밖 도구: %s", e.tool)
        return {"answer": DENIED_ANSWER, "sources": [], "related": [], "status": "OUT_OF_ROLE"}
    except ToolInputError as e:     # 질문에서 읽은 설비·기간이 조회 도구가 받을 수 없는 값
        raise Unavailable(f"tool input: {e}") from e
    except UnknownStatus as e:
        raise Unavailable(str(e)) from e
    except Exception as e:      # 답을 만들다 멈춤 (조회 도구 실패 포함) — 안쪽 사정은 로그에만
        raise Unavailable(f"{type(e).__name__}") from e


app.include_router(CMPS.router, dependencies=[Depends(service_key)])     # POST /compose/{kind} — 기본 문장 줄 다듬기 (같은 서비스 키)
app.include_router(WRS.router, dependencies=[Depends(service_key)])      # POST /work-record-assist — 작업기록서 메모 정리 (2026-10-20, API-MNT-10)
app.include_router(VOICE.router, dependencies=[Depends(service_key)])    # POST /transcribe · GET /voice/status — 채팅 마이크 (ASSISTANT_VOICE=1일 때만, 같은 서비스 키)


@app.get("/health", dependencies=[Depends(service_key)])
def health() -> dict:
    try:
        corpus = {"status": "ok", "chunks": len(load_corpus())}
    except CorpusError:
        corpus = {"status": "error"}
    return {"status": "ok", "corpus": corpus, "provider": "claude" if _provider() else "local",
            "external_enabled": C.settings().external_app}
