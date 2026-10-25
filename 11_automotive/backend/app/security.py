"""로그인·권한 (NFR-SEC-01~07). 버튼 숨기기만이 아니라 서버가 role_permission 표로 막는다 (NFR-SEC-05).
"사람만" 하는 일은 DB 함수·트리거가 한 번 더 막는다 (R-51) — 비서는 사용자 계정이 아니다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import jwt
from fastapi import Depends, Header

from .config import get_settings
from .db import Db, get_db, side_engine
from .domain.permissions import PermissionTable
from .domain.tokens import decode_token
from .errors import AppError


@dataclass(frozen=True)
class User:
    user_id: str
    user_name: str
    role_code: str
    home_process_code: str | None = None
    home_process_code_2: str | None = None      # 두 번째 담당 공정 (OPR만, 2026-10-10)

    @property
    def processes(self) -> tuple[str, ...]:
        """담당 공정 두 칸 (빈 칸 빼고) — "담당 공정"을 쓰는 곳은 두 칸을 함께 본다 (논리 ERD 5.H.1)"""
        return tuple(p for p in (self.home_process_code, self.home_process_code_2) if p)


@dataclass(frozen=True)
class Actor:
    user: User
    scope: str          # 권한 범위 (ALL / OWN / SUMMARY / PROXY / OWNED_ITEMS)

    @property
    def user_id(self) -> str:
        return self.user.user_id

    @property
    def role(self) -> str:
        return self.user.role_code


_perm_cache: tuple[float, PermissionTable] | None = None
PERM_TTL_SECONDS = 60


def permissions(db: Db) -> PermissionTable:
    global _perm_cache
    now = time.monotonic()
    if _perm_cache is None or now - _perm_cache[0] > PERM_TTL_SECONDS:
        _perm_cache = (now, PermissionTable(db.all("common.permissions")))
    return _perm_cache[1]


def reset_permission_cache() -> None:
    global _perm_cache
    _perm_cache = None


def current_user(authorization: str | None = Header(default=None), db: Db = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "UNAUTHORIZED", "로그인 필요")
    try:
        claims = decode_token(authorization[7:], get_settings().jwt_secret)
    except jwt.PyJWTError:
        raise AppError(401, "UNAUTHORIZED", "로그인이 만료됐거나 올바르지 않음") from None
    row = db.one("common.user_public", user_id=claims["sub"])
    if not row or not row["is_active"]:
        raise AppError(401, "UNAUTHORIZED", "사용 중인 사용자가 아님")
    return User(row["user_id"], row["user_name"], row["role_code"], row["home_process_code"], row.get("home_process_code_2") or None)


def token_user(authorization: str | None = Header(default=None)) -> User:
    """DB를 읽지 않는 로그인 확인 (2026-10-24): 토큰 서명·만료와 토큰 안의 역할만 본다.
    1초마다 모든 화면이 부르는 /api/line/twin 전용 — 여기서 요청마다 DB 연결을 잡으면 접속자가 많을 때 연결 줄이 막힌다.
    읽기만 하는 주소에만 쓴다 (사용 중지·역할 변경은 다음 로그인부터 반영). 바꾸는 주소는 지금처럼 current_user"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "UNAUTHORIZED", "로그인 필요")
    try:
        claims = decode_token(authorization[7:], get_settings().jwt_secret)
    except jwt.PyJWTError:
        raise AppError(401, "UNAUTHORIZED", "로그인이 만료됐거나 올바르지 않음") from None
    if not claims.get("role"):
        raise AppError(401, "UNAUTHORIZED", "로그인이 만료됐거나 올바르지 않음")
    return User(claims["sub"], claims["sub"], claims["role"])


def permissions_side() -> PermissionTable:
    """권한표 (60초 기억). 기억이 지났으면 요청과 다른 작은 연결 줄(db.side_engine)로 다시 읽는다"""
    if _perm_cache is not None and time.monotonic() - _perm_cache[0] <= PERM_TTL_SECONDS:
        return _perm_cache[1]
    with side_engine().connect() as conn:
        return permissions(Db(conn))


def require(target: str, action: str) -> Callable[..., Actor]:
    """권한 의존성: Depends(require("SHIPMENT", "CONFIRM"))"""

    def dep(user: User = Depends(current_user), db: Db = Depends(get_db)) -> Actor:
        scope = permissions(db).scope(user.role_code, target, action)
        if scope is None:
            raise AppError(403, "FORBIDDEN", f"{user.role_code} 역할은 {target}·{action} 권한이 없음")
        return Actor(user, scope)

    dep.permission = [(target, action)]    # 문서 만들기(tools/gen_api_doc.py)용 표시
    return dep


def require_any(*pairs: tuple[str, str]) -> Callable[..., Actor]:
    """여러 권한 중 하나 (예: 정식·간이 작업기록 중 하나라도 확정 가능)"""

    def dep(user: User = Depends(current_user), db: Db = Depends(get_db)) -> Actor:
        table = permissions(db)
        for target, action in pairs:
            scope = table.scope(user.role_code, target, action)
            if scope is not None:
                return Actor(user, scope)
        raise AppError(403, "FORBIDDEN", f"{user.role_code} 역할은 권한이 없음")

    dep.permission = list(pairs)
    return dep


def service_key(kind: str) -> Callable[..., str]:
    """시뮬레이터(ingest)·AI 비서 서비스(assistant)용 API 키. 사람 로그인과 따로 둔다."""

    def dep(x_service_key: str | None = Header(default=None)) -> str:
        s = get_settings()
        expected = s.ingest_key if kind == "ingest" else s.assistant_key
        if not expected or x_service_key != expected:
            raise AppError(401, "UNAUTHORIZED", f"{kind} 서비스 키가 맞지 않음")
        return kind

    dep.service = kind
    return dep
