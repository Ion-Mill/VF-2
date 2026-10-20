"""로그인·내 정보·역할 바꿔 보기 (API명세서 AUTH-01~04, SCR-01, NFR-SEC-07 [선택 필요: 기술 회의] — 지금은 아이디·비밀번호 + JWT)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..audit import log_access
from ..config import get_settings
from ..db import Db, get_db
from ..domain.passwords import DUMMY_HASH, verify_password
from ..domain.tokens import create_token
from ..errors import AppError
from ..security import User, current_user, permissions

router = APIRouter(prefix="/api", tags=["로그인"])


class LoginIn(BaseModel):
    user_id: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    user_name: str
    role_code: str
    home: str                    # 역할별 첫 화면 (UI 4.1, 2026-10-13): OPR = SCR-26 현장 보기, 나머지 = SCR-04 3D 라인 뷰
    process_codes: list[str] = []      # 담당 공정 (OPR은 두 개까지 — API-AUTH-01, 2026-10-20)
    shift_type: str | None = None      # 기본 교대 (D 주간 / N 야간)


# 2026-10-13 팀 결정: MNT 첫 화면 SCR-18 → SCR-04 (문서함은 메뉴), MGR SCR-16 → SCR-04. 로그인 팝업 없음
# (MGR 일일 보고서는 DAILY_REPORT_PENDING 말풍선 → SCR-16)
HOME = {"OPR": "SCR-26", "MNT": "SCR-04", "SUP": "SCR-04", "MGR": "SCR-04"}


def _token_for(row: dict) -> TokenOut:
    s = get_settings()
    return TokenOut(access_token=create_token(row["user_id"], row["role_code"], s.jwt_secret, s.jwt_minutes),
                    user_id=row["user_id"], user_name=row["user_name"], role_code=row["role_code"], home=HOME[row["role_code"]],
                    process_codes=[p for p in (row.get("home_process_code"), row.get("home_process_code_2")) if p],
                    shift_type=row.get("home_shift_type") or None)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Db = Depends(get_db)):
    """아이디·비밀번호 로그인 → JWT. 실패도 접근 기록에 남는다"""
    row = db.one("common.user_by_id", user_id=body.user_id)
    pw_ok = verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)
    ok = bool(row and row["is_active"] and pw_ok)
    # 실패도 남긴다 (요청 트랜잭션은 되돌려지므로 따로 저장). 없는 아이디는 user_id 칸을 비우고 detail에만
    log_access(row["user_id"] if row else None, "LOGIN" if ok else "LOGIN_FAIL", "POST", "/api/auth/login",
               200 if ok else 401, request.client.host if request.client else None, {"user_id": body.user_id})
    if not ok:
        raise AppError(401, "UNAUTHORIZED", "아이디 또는 비밀번호가 맞지 않음")
    db.exec("common.touch_login", user_id=row["user_id"])
    return _token_for(row)


@router.post("/auth/logout")
def logout(request: Request, user: User = Depends(current_user)):
    """로그아웃 (AUTH-02). 토큰은 화면이 버린다 (서버에 세션 없음 — 로그인 방식은 [선택 필요: 기술 회의]). 접근 기록에 남긴다"""
    log_access(user.user_id, "LOGOUT", "POST", "/api/auth/logout", 200, request.client.host if request.client else None, None)
    return {"ok": True}


class DemoRoleIn(BaseModel):
    role: str
    user_id: str | None = None      # 비우면 그 역할의 첫 사용자


@router.post("/demo/role", response_model=TokenOut)
def demo_role(body: DemoRoleIn, request: Request, db: Db = Depends(get_db)):
    """역할 바꿔 보기 (AUTH-04, 시연 모드만 — NFR-DATA-12). 바뀐 역할의 토큰·첫 화면. 시연 모드가 아니면 없음과 같다"""
    if not get_settings().demo_mode:
        raise AppError(404, "NOT_FOUND", "없음")
    row = (db.one("common.user_public", user_id=body.user_id) if body.user_id
           else db.one("common.first_user_of_role", role_code=body.role))
    if not row or not row["is_active"] or row["role_code"] != body.role:
        raise AppError(404, "NOT_FOUND", f"{body.role} 역할의 사용자 없음")
    log_access(row["user_id"], "LOGIN", "POST", "/api/demo/role", 200,
               request.client.host if request.client else None, {"demo": True, "role": body.role})
    return _token_for(row)


@router.get("/me")
def me(user: User = Depends(current_user), db: Db = Depends(get_db)):
    """내 정보·권한 (AUTH-03): 역할·담당 공정·첫 화면·할 수 있는 일 목록 (화면이 버튼을 숨길 때 씀 — 막는 것은 서버)"""
    return {"user_id": user.user_id, "user_name": user.user_name, "role_code": user.role_code,
            "home_process_code": user.home_process_code, "home_process_code_2": user.home_process_code_2,
            "home": HOME[user.role_code],
            "permissions": permissions(db).targets(user.role_code)}
