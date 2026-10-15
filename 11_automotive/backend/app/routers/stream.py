"""SSE 실시간 채널 (API명세서 STR-01·3장, NFR-PERF: 알림 팝업·3D 라인 뷰 갱신).

사건 이름: state_changed, wip_changed, bottleneck_changed, alarm, urgent_popup, notification, kpi_updated,
document_changed, connection (app/domain/events.py). 데이터 = {table, op, id, equipment_id, …, at}.
브라우저 EventSource는 머리글(Authorization)을 못 붙이므로 ?token= 으로 받는다 (같은 JWT).
사건에는 무엇이 바뀌었는지만 있고 내용은 없다 → 화면이 권한 있는 API로 다시 읽는다.
역할별로 거른다 (app/domain/events.py visible_events): 알림·긴급 팝업은 받은 사람만(MGR은 목록 갱신만), 문서는 볼 수 있는
역할만. 역할·권한은 연결할 때 읽는다 — 역할이 바뀌면 화면이 다시 연결한다.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..db import Db, engine
from ..domain.events import visible_events
from ..domain.permissions import PermissionTable
from ..domain.tokens import decode_token
from ..errors import AppError
from ..realtime import broadcaster
from ..security import permissions

router = APIRouter(prefix="/api", tags=["실시간"])
KEEPALIVE_SECONDS = 15


def sse(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _connect_user(user_id: str) -> tuple[str | None, PermissionTable | None]:
    """사용 중인 사용자의 역할과 권한 표 (스레드에서 부른다 — DB 호출이 동기)"""
    with engine().begin() as conn:
        db = Db(conn)
        row = db.one("common.user_public", user_id=user_id)
        if not row or not row["is_active"]:
            return None, None
        return row["role_code"], permissions(db)


def _received(notification_id, user_id: str) -> bool:
    """이 사용자가 받은 알림인가 (알림 사건마다, 스레드에서)"""
    if notification_id is None:
        return False
    with engine().begin() as conn:
        return bool(Db(conn).scalar("notifications.is_recipient", notification_id=int(notification_id), user_id=user_id))


@router.get("/stream/events")
async def stream(request: Request, token: str = Query(...)):
    """실시간 사건 (STR-01, SSE). 바뀐 것의 종류·번호만 보낸다 — 화면이 해당 API를 다시 부른다. ?token= (EventSource).
    역할별로 거른다: 알림·긴급 팝업은 받은 사람만, 문서 사건은 그 문서를 볼 수 있는 역할만"""
    try:
        claims = decode_token(token, get_settings().jwt_secret)
    except jwt.PyJWTError:
        raise AppError(401, "UNAUTHORIZED", "로그인이 만료됐거나 올바르지 않음") from None
    user_id = claims["sub"]
    role, table = await asyncio.to_thread(_connect_user, user_id)
    if role is None:
        raise AppError(401, "UNAUTHORIZED", "사용 중인 사용자가 아님")

    async def events():
        q = broadcaster.subscribe()
        try:
            now = datetime.now(timezone.utc).isoformat()
            yield sse("connection", {"status": "connected", "user_id": user_id, "role_code": role, "at": now})
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                data = json.loads(payload)
                data["at"] = datetime.now(timezone.utc).isoformat()     # 마지막 갱신 시각 (연결 끊김 띠, UI 2.8)
                got = (data.get("table") == "notification" and data.get("op") != "RESYNC"
                       and await asyncio.to_thread(_received, data.get("id"), user_id))
                for name in visible_events(data, role, table, received=bool(got)):
                    yield sse(name, data)
        finally:
            broadcaster.unsubscribe(q)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
