"""직원 관리 (SCR-27, API-USR-01~05, 2026-10-25) — 명단·업무 기록 모으기, 배치 바꾸기, 직원 추가·고치기.

고치는 길은 하나다: 배치 바꾸기(USR-03)·정보 고치기(USR-05)·설정 사용자 고치기(SET-03) 모두 update_user를 거친다.
  1. 그 직원 행을 잠그고(FOR UPDATE) 바뀐 뒤 칸을 확인한다 (app/domain/staff.py — 역할·공정·자기 자신·관리자 0명)
  2. app_user를 고친다 (비밀번호는 scrypt 해시만 — 원문은 저장·응답·수정 이력 어디에도 남기지 않음)
  3. 사람마다 수정 이력 (문서 종류 APP_USER, 문서 키 = user_id) + 바뀐 칸 전·후 (FR-USR-01-05)
  4. 사용 중지·역할 변경은 3D 라인 뷰 토큰 확인(security.token_user)의 기억을 지운다
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db import Db
from .. import security
from ..config import get_settings
from ..domain import staff as rules
from ..domain.passwords import hash_password
from ..errors import AppError, not_found, validation


def _dt(v) -> datetime:
    return datetime.fromisoformat(v) if isinstance(v, str) else v     # psql로 도는 시험 Db는 글자로 돌려준다


def _range(db: Db, period: str) -> tuple[datetime, datetime]:
    now = _dt(db.scalar("common.now"))
    start = _dt(db.scalar("staff.data_start")) if period == "all" else None
    return rules.period_range(period, now, start)


def users(db: Db, include_inactive: bool = False) -> list[dict]:
    return db.all("staff.users", include_inactive=include_inactive)


def overview(db: Db, period: str, include_inactive: bool = False) -> dict:
    """직원 명단 + 지금 교대 + 사람마다 숫자 4칸 + 배치표 + 담당 0명 칸 (API-USR-01)"""
    frm, to = _range(db, period)
    mine: dict[str, list] = {}
    for e in db.all("staff.events", user_id=None, **{"from": frm, "to": to}):
        mine.setdefault(e["user_id"], []).append(e)
    sh = db.one("staff.current_shift") or {"shift_id": None, "shift_type": None, "is_on": False}
    is_on = rules.on(sh["is_on"])
    rows = users(db, include_inactive)
    board, empty = rules.board(rows)
    return {"period": period, "from": frm, "to": to,
            "shift": {"shift_id": sh["shift_id"], "shift_type": sh["shift_type"], "on": is_on},
            "users": [{**u, "on_shift": is_on and rules.on(u["is_active"]) and u["home_shift_type"] == sh["shift_type"],
                       "kpis": rules.kpis(u["role_code"], mine.get(u["user_id"], []))} for u in rows],
            "board": board, "empty": empty}


def activity(db: Db, user_id: str, period: str, page: int = 1, size: int = 80) -> dict:
    """한 사람의 숫자 4칸 + 최근 한 일 (최신이 위, API-USR-02). 사용 중지된 직원도 지난 기록은 그대로 본다"""
    u = db.one("staff.user", user_id=user_id)
    if u is None:
        raise not_found("직원")
    frm, to = _range(db, period)
    evs = db.all("staff.events", user_id=user_id, **{"from": frm, "to": to})
    page_items = evs[(page - 1) * size: page * size]
    return {"period": period, "from": frm, "to": to, "user": u, "kpis": rules.kpis(u["role_code"], evs), "total": len(evs),
            "page": page, "size": size,
            "items": [{k: e[k] for k in ("at", "kind", "text", "screen", "key")} for e in page_items]}


def _save(db: Db, actor_id: str, cur: dict, new: dict, reason: str | None) -> dict | None:
    """바뀐 칸이 있으면 app_user 고치기 + 수정 이력. 없으면 None"""
    changes = rules.diff(cur, new)
    if not changes:
        return None
    row = db.one("staff.user_set", user_id=cur["user_id"], user_name=new["user_name"], role_code=new["role_code"],
                 home_shift_type=new["home_shift_type"], home_process_code=new["home_process_code"],
                 home_process_code_2=new["home_process_code_2"], is_active=new["is_active"],
                 password_hash=hash_password(new["password"]) if new.get("password") else None)
    ver = db.scalar("documents.save_revision", doc_type="APP_USER", doc_key=cur["user_id"], author_kind="HUMAN", author=actor_id,
                    reason=(reason or "").strip() or None, status_after="ACTIVE" if rules.on(row["is_active"]) else "INACTIVE",
                    content=rules.public(row), changes=changes)
    if any(c["field"] in ("is_active", "role_code") for c in changes):
        security.reset_user_state_cache()
    return {"user": rules.public(row), "revision_id": db.scalar("staff.revision_id", user_id=cur["user_id"], version_no=ver),
            "version_no": int(ver)}


def _lock(db: Db, user_id: str) -> dict:
    cur = db.one("staff.user_lock", user_id=user_id)
    if cur is None:
        raise not_found(f"직원 {user_id}")
    return cur


def update_user(db: Db, actor_id: str, user_id: str, change: dict, reason: str | None = None) -> dict:
    """직원 정보 고치기 (API-USR-05, SET-03): 이름·역할·사용 여부·비밀번호 (+ 담당 교대·공정). 바뀐 칸이 없으면 422 NO_CHANGE"""
    cur = _lock(db, user_id)
    new = rules.updated_user(cur, change, actor_id, [r["user_id"] for r in db.all("staff.active_mgr_ids")],
                             get_settings().password_min_length)
    out = _save(db, actor_id, cur, new, reason)
    if out is None:
        raise validation("바뀐 칸이 없음", reason="NO_CHANGE")
    return out


def assign(db: Db, actor_id: str, changes: list[dict], reason: str | None = None) -> dict:
    """배치 바꾸기 (API-USR-03, 여러 명 한 번에): 모두 확인한 뒤 저장 — 한 사람이라도 틀리면 아무것도 바꾸지 않는다"""
    ids = [c.get("user_id") for c in changes]
    if not ids or len(set(ids)) != len(ids):
        raise validation("바꿀 직원이 없거나 같은 직원이 두 번 있음", reason="CHANGES")
    plan = []
    for c in sorted(changes, key=lambda c: c["user_id"]):     # 잠그는 차례를 늘 같게 (함께 고칠 때 서로 기다리다 멈추지 않게)
        cur = _lock(db, c["user_id"])
        plan.append((cur, rules.check_assignment(cur, c)))
    done = [{"user_id": cur["user_id"], "revision_id": out["revision_id"], "version_no": out["version_no"]}
            for cur, new in plan if (out := _save(db, actor_id, cur, new, reason)) is not None]
    if not done:
        raise validation("바뀐 내용이 없음", reason="NO_CHANGE")
    rows = users(db)
    board, empty = rules.board(rows)
    return {"changed": done, "users": rows, "board": board, "empty": empty}


def create_user(db: Db, actor_id: str, body: dict) -> dict:
    """직원 추가 (API-USR-04): 수정 이력 v0 "직원 추가" (사유를 주면 그 글). 아이디를 비우면 U + 다음 번호"""
    new = rules.new_user(body, [r["user_id"] for r in db.all("staff.user_ids")], get_settings().password_min_length)
    row = db.one("staff.user_insert", user_id=new["user_id"], user_name=new["user_name"], role_code=new["role_code"],
                 home_shift_type=new["home_shift_type"], home_process_code=new["home_process_code"],
                 home_process_code_2=new["home_process_code_2"], password_hash=hash_password(new["password"]))
    if row is None:
        raise AppError(409, "INVALID_STATE", f"직원을 만들지 못함: {new['user_id']}", {"reason": "DUPLICATE"})
    changes = rules.diff({}, {**rules.public(row), "password": new["password"]})      # 비밀번호는 값 없이 "비밀번호 정함" 한 줄만
    ver = db.scalar("documents.save_revision", doc_type="APP_USER", doc_key=row["user_id"], author_kind="HUMAN", author=actor_id,
                    reason=(body.get("reason") or "").strip() or "직원 추가", status_after="ACTIVE",
                    content=rules.public(row), changes=changes)
    return {"user": rules.public(row), "revision_id": db.scalar("staff.revision_id", user_id=row["user_id"], version_no=ver),
            "version_no": int(ver)}
