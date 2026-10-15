"""라우터 공통: 기간 기본값, 조회 결과 없으면 404, 바뀐 행이 없으면 409."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..db import Db
from ..errors import AppError, not_found


def must(row, what: str):
    if row is None:
        raise not_found(what)
    return row


def changed(n: int, what: str) -> dict:
    """UPDATE ... WHERE 상태 조건 → 0행이면 지금 상태에서 할 수 없는 일"""
    if not n:
        raise AppError(409, "INVALID_STATE", f"{what}: 지금 상태에서 할 수 없음 (이미 처리됐거나 상태가 다름)")
    return {"ok": True}


def period(db: Db, frm: datetime | None, to: datetime | None, default_hours: int = 24) -> tuple[datetime, datetime]:
    """기간 기본값 = 시연 시계(app_now) 기준 최근 default_hours 시간"""
    if to is None:
        to = db.scalar("common.now")
        if isinstance(to, str):            # psql로 도는 시험 Db는 글자로 돌려준다
            to = datetime.fromisoformat(to)
    if frm is None:
        frm = to - timedelta(hours=default_hours)
    if frm >= to:
        raise AppError(422, "VALIDATION", "기간: 시작이 끝보다 늦음")
    return frm, to


def check_version(db: Db, doc_type: str, doc_key: str, version: int | None) -> None:
    """문서를 고치는 요청의 version이 지금 버전과 다르면 CONFLICT_VERSION (API명세서 1장 — 다른 사람이 먼저 고침)"""
    if version is None:
        return
    cur = db.scalar("documents.current_version", doc_type=doc_type, doc_key=str(doc_key))
    if cur is None:
        raise not_found(doc_type)
    if int(cur) != int(version):
        raise AppError(409, "CONFLICT_VERSION", f"다른 사람이 먼저 고쳤음 (지금 v{cur}, 보낸 v{version}) — 다시 열어 고친다",
                       {"current_version": int(cur)})
