"""AI 비서 (API명세서 2.4 AST-02 + 비서 서비스가 부르는 API).

  · 화면 → POST /api/assistant/chat (사용자 로그인, API-AST-02): 질문을 AI 비서 서비스(MOM_ASSISTANT_URL)로 넘긴다. 답은 그
    사용자의 역할이 볼 수 있는 것만 — 서비스는 아래 조회 도구를 on_behalf_of로 부른다. 질문·답은 chat_log에 사용자별로
    30일 저장하고(2026-10-13) GET /api/assistant/chat 으로 본인 기록만 본다. 비서가 응답하지 않으면 status = NO_RESPONSE
  · 채팅 권한 (2026-10-13 [가상]): MTTR(reliability)·센서 데이터(sensor_trend) 도구는 MNT·MGR만 — 다른 역할은 도구 목록에서
    빠지고, 서비스에는 "누가 볼 수 있는지"(out_of_role)를 넘겨 권한 밖 답(OUT_OF_ROLE)을 쓰게 한다
  · 비서 서비스 → (서비스 키 X-Service-Key: assistant) 아래 API. 브리핑 재료는 /api/assistant/briefing (notifications.py)

  · 조회 도구 14개: 읽기 전용 연결, 대신 묻는 사용자(on_behalf_of)의 역할 권한으로 거름
  · 초안 저장: 작업지시서·작업기록서 AI비서 초안(v0, AI_DRAFT)만. 승인·확정·보류·출하는 사람만 (R-51 — DB도 막음)
  · 알림 문장 바꾸기: 규칙이 만든 알림의 글만 (알릴지·중요도·받는 사람은 못 바꿈, R-38)
LLM 호출·프롬프트·RAG(사내 문서 검색)는 이 서버 밖 AI 비서 서비스가 한다 [선택 필요: 기술 회의].
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ..assistant import client, tools
from ..audit import log_access
from ..db import Db, get_db, get_ro_db
from ..errors import AppError
from ..security import Actor, User, permissions, require, service_key
from ..services import records
from .common import changed
from .maintenance import WoDraftIn

router = APIRouter(prefix="/api/assistant", tags=["AI 비서"])
SERVICE = [Depends(service_key("assistant"))]     # 비서 서비스만 (사람 로그인과 따로)


def _user(db: Db, user_id: str) -> User:
    row = db.one("common.user_public", user_id=user_id)
    if not row or not row["is_active"]:
        raise AppError(403, "FORBIDDEN", f"사용 중인 사용자가 아님: {user_id}")
    return User(row["user_id"], row["user_name"], row["role_code"], row["home_process_code"], row.get("home_process_code_2") or None)


def _allowed(db: Db, user: User) -> set[str]:
    """이 사용자 대신 쓸 수 있는 조회 도구: 권한 표(13장) + 채팅 권한(chat_roles — MTTR·센서는 MNT·MGR, 2026-10-13)"""
    table = permissions(db)
    if not table.allows(user.role_code, "ASSISTANT", "INPUT"):
        return set()
    return {t.name for t in tools.TOOLS.values() if table.allows(user.role_code, *t.permission)
            and (t.chat_roles is None or user.role_code in t.chat_roles)}


def _out_of_role(user: User) -> list[dict]:
    """채팅 권한 때문에 뺀 도구와 볼 수 있는 역할 — 비서는 값 없이 "누가 볼 수 있는지"만 말한다 (5.G.7)"""
    return [{"tool": t.name, "about": tools.OUT_OF_ROLE_TEXT.get(t.name, t.name), "roles": list(t.chat_roles)}
            for t in tools.TOOLS.values() if t.chat_roles is not None and user.role_code not in t.chat_roles]


@router.get("/tools", dependencies=SERVICE)
def tool_list(on_behalf_of: str, db: Db = Depends(get_ro_db)):
    """이 사용자가 쓸 수 있는 도구의 JSON Schema (LLM 도구 정의에 그대로)"""
    return tools.schemas(_allowed(db, _user(db, on_behalf_of)))


class ToolCallIn(BaseModel):
    on_behalf_of: str
    args: dict[str, Any] = Field(default_factory=dict)


@router.post("/tools/{name}", dependencies=SERVICE)
def tool_call(name: str, body: ToolCallIn, request: Request, db: Db = Depends(get_ro_db)):
    """조회 도구 실행 (읽기 전용). 대신 묻는 사용자의 권한으로 거르고 접근 기록에 남긴다"""
    user = _user(db, body.on_behalf_of)
    if name not in _allowed(db, user):
        log_access(user.user_id, "API", "POST", f"/api/assistant/tools/{name}", 403, None, {"tool": name, "denied": True})
        raise AppError(403, "FORBIDDEN", f"{user.role_code} 역할은 도구 {name}를 쓸 수 없음")
    rows = tools.run(db, name, body.args)
    log_access(user.user_id, "API", "POST", f"/api/assistant/tools/{name}", 200,
               request.client.host if request.client else None, {"tool": name, "args": body.args, "rows": len(rows)})
    return {"tool": name, "rows": rows, "now": db.scalar("common.now")}


@router.post("/drafts/work-order", dependencies=SERVICE)
def draft_work_order(body: WoDraftIn, db: Db = Depends(get_db)):
    """작업지시서 AI비서 초안 (고정 서식 블록은 AI가 쓰지 않고 붙었다는 표시만, R-33). 겹치면 기존 것에 더함 (R-71)"""
    wo_no = db.scalar("maintenance.wo_create_draft", equipment_id=body.equipment_id, title=body.title, symptom=body.symptom,
                      alarm_event_id=body.alarm_event_id, trigger_notification_id=body.trigger_notification_id,
                      pm_record_id=body.pm_record_id, lot_no=body.lot_no, author=None,
                      steps=[s.model_dump() for s in body.steps], parts=[p.model_dump() for p in body.parts])
    return {"wo_no": wo_no}


class WrDraftIn(BaseModel):
    wo_no: str
    cause: str | None = None
    action: str | None = None


@router.post("/drafts/work-record", dependencies=SERVICE)
def draft_work_record(body: WrDraftIn, db: Db = Depends(get_db)):
    """정식 작업기록서 AI비서 초안 (v0 = AI). 확정은 보전 담당자"""
    return records.create_work_record_full(db, body.wo_no, "AI", None, body.cause, body.action)


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)


@router.put("/notifications/{notification_id}/message", dependencies=SERVICE)
def notification_message(notification_id: int, body: MessageIn, db: Db = Depends(get_db)):
    """알림 문장을 비서 문장으로 바꾸기 (알릴지·중요도는 못 바꿈, R-38)"""
    return changed(db.exec("notifications.set_message", notification_id=notification_id, message=body.message), "알림 문장")


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict, description="지금 화면·설비·알람 (예: {\"screen\": \"SCR-09\", \"alarm_event_id\": 3})")
    prev_chat_id: int | None = Field(None, description="이어서 물을 때 앞 질문의 chat_id (본인 것만) [제안]")


HISTORY_TURNS = 5        # 이어서 물을 때 비서에게 넘기는 앞 질문·답 수 [제안]


def _history(db: Db, actor: Actor, prev_chat_id: int | None) -> list[dict]:
    if prev_chat_id is None:
        return []
    prev = db.one("assistant.chat_get", chat_id=prev_chat_id, user_id=actor.user_id)
    if prev is None:
        raise AppError(404, "NOT_FOUND", f"내 채팅 기록에 없음: {prev_chat_id}")
    return list(reversed(db.all("assistant.chat_thread", chat_id=prev_chat_id, user_id=actor.user_id, turns=HISTORY_TURNS)))


@router.post("/chat")
def chat(body: ChatIn, request: Request, actor: Actor = Depends(require("ASSISTANT", "INPUT")), db: Db = Depends(get_db)):
    """비서에게 질문 (API-AST-02 POST, FR-MNT-01, FR-AST-COM): chat_id·answer·sources[](사내 문서 이름·번호·개정·§만)·
    related[](기록 번호)·status(OK / NOT_IN_DOCS 문서에 없음 / OUT_OF_ROLE 권한 밖 / REFUSED 거부 / NO_RESPONSE 응답 없음).
    질문·답은 chat_log에 저장 (사용자별 30일, 2026-10-13). 비서 서비스가 없거나 응답이 틀리면 status = NO_RESPONSE,
    answer = null (화면은 기본 문구) — 그래도 질문은 기록에 남는다"""
    allowed = sorted(_allowed(db, actor.user))
    history = _history(db, actor, body.prev_chat_id)
    try:
        out = client.chat_answer(client.call("/chat", {
            "question": body.question, "context": body.context, "allowed_tools": allowed,
            "out_of_role": _out_of_role(actor.user), "history": history,
            "user": {"user_id": actor.user_id, "role_code": actor.role, "home_process_code": actor.user.home_process_code,
                     "home_process_code_2": actor.user.home_process_code_2}}))
    except AppError as e:
        if e.code != "ASSISTANT_UNAVAILABLE":
            raise
        out = {"answer": None, "sources": [], "related": [], "status": "NO_RESPONSE",
               "reason": (e.detail or {}).get("reason") if isinstance(e.detail, dict) else None}
    chat_id = db.scalar("assistant.chat_insert", user_id=actor.user_id, screen_context=body.context or None,
                        question=body.question, answer=out["answer"], sources=out["sources"] or None,
                        status=out["status"], prev_chat_id=body.prev_chat_id)
    log_access(actor.user_id, "API", "POST", "/api/assistant/chat", 200, request.client.host if request.client else None,
               {"status": out["status"], "sources": len(out["sources"]), "chat_id": chat_id})
    return {"chat_id": chat_id, **out}


@router.get("/chat")
def chat_history(since: datetime | None = Query(None, description="이 시각 뒤 (비우면 30일 안 전부)"),
                 limit: int = Query(100, le=500), actor: Actor = Depends(require("ASSISTANT", "INPUT")),
                 db: Db = Depends(get_db)):
    """내 채팅 기록 (API-AST-02 GET, 이브 사이드바 채팅 기록 탭): 본인 것만, 30일 안 (질문 시각·질문·답·출처·상태)"""
    return db.all("assistant.chat_list", user_id=actor.user_id, since=since, limit=limit)


@router.get("/chat/{chat_id}")
def chat_one(chat_id: int, actor: Actor = Depends(require("ASSISTANT", "INPUT")), db: Db = Depends(get_db)):
    """채팅 기록 1건 (본인 것만 — 다른 사람 것은 없는 것처럼 404)"""
    row = db.one("assistant.chat_get", chat_id=chat_id, user_id=actor.user_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", f"내 채팅 기록에 없음: {chat_id}")
    return row
