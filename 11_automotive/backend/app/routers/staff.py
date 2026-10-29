"""직원 관리 (SCR-27, 2026-10-25) — 관리자(MGR)만 읽고 바꾼다 (NFR-SEC-04·05, 권한 STAFF·VIEW / STAFF·EDIT).

  API-USR-01~03 (API명세서): 명단·배치표, 한 사람 업무 기록, 배치 바꾸기
  API-USR-04·05 (구현_중_수정사항/1025_직원관리_백엔드_요청.md 3장 [제안], 팀 결정 "A·B 다 한다"): 직원 추가, 정보 고치기
    (이름·역할·사용 중지/다시 사용·비밀번호 다시 정하기). 지우기는 없다 — 지난 기록의 "누가" 칸 때문에 사용 중지만 (6.53 USER)
업무 기록은 새로 쌓지 않고 기존 표의 "누가" 칸을 모은다 (FR-USR-01-10, app/sql/staff.sql events). 채팅 기록·순위·점수는 없다.
바꾼 것은 사람마다 수정 이력(문서 종류 APP_USER) → 문서함 › 수정 이력(SCR-17)에 "직원 배치"로 (MGR만 봄).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..security import Actor, User, current_user, require
from ..services import staff

router = APIRouter(prefix="/api", tags=["직원 관리"])

PERIOD = "^(today|7d|30d|sep|all)$"     # 처음 값 7d (FR-USR-01-09). all = 기록 전체, sep = 9월 전체(옛 값)


@router.get("/users")
def users_public(_: User = Depends(current_user), db: Db = Depends(get_db)):
    """직원 이름·역할·배치 목록 — 로그인한 누구나 (2026-10-25, 시연 서버 /api/users와 같은 모양 `{users}`).
    화면이 이름 표시·담당 공정 알림과 직원 관리에서 바꾼 배치를 바로 적용(FR-USR-01-06)하는 데 쓴다.
    사용 중지된 직원도 (지난 기록의 이름). 숫자·업무 기록·로그인 시각은 없음"""
    return {"users": db.all("staff.users_public")}


@router.get("/staff")
def staff_list(period: str = Query("7d", pattern=PERIOD),
               include_inactive: bool = Query(False, description="사용 중지된 직원도 (맨 뒤, 배치표에는 넣지 않음)"),
               _: Actor = Depends(require("STAFF", "VIEW")), db: Db = Depends(get_db)):
    """직원 명단 + 지금 교대 + 사람마다 역할별 숫자 4칸 + 배치표 + 담당 0명 공정 칸 (USR-01, FR-USR-01-01~03·07·09)"""
    return staff.overview(db, period, include_inactive)


@router.get("/staff/{user_id}/activity")
def staff_activity(user_id: str, period: str = Query("7d", pattern=PERIOD), page: int = Query(1, ge=1),
                   size: int = Query(80, ge=1, le=500),
                   _: Actor = Depends(require("STAFF", "VIEW")), db: Db = Depends(get_db)):
    """직원 상세: 숫자 4칸(합계만, 양품률만 비율) + 최근 한 일 (최신이 위, 누르면 열 화면·키). USR-02, FR-USR-01-07·08"""
    return staff.activity(db, user_id, period, page, size)


class AssignChange(BaseModel):
    user_id: str
    home_shift_type: str | None = None
    home_process_code: str | None = None     # 비우려면 ""
    home_process_code_2: str | None = None
    procs: list[str] | None = None           # 또는 담당 공정 목록 (화면이 보내는 모양, 2개까지)


class AssignIn(BaseModel):
    changes: list[AssignChange] = Field(min_length=1)
    reason: str | None = None


@router.patch("/staff/assignments")
def staff_assign(body: AssignIn, actor: Actor = Depends(require("STAFF", "EDIT")), db: Db = Depends(get_db)):
    """배치 바꾸기 (USR-03, 여러 명 한 번에, FR-USR-01-04~06): 담당 교대·담당 공정. 같은 역할만 그 줄(공정 = OPR), 담당 공정 2개까지 —
    어기면 VALIDATION (한 사람이라도 틀리면 아무것도 안 바꿈). 역할·사용 여부는 USR-05. 저장하면 바로 적용, 사람마다 수정 이력"""
    return staff.assign(db, actor.user_id, [c.model_dump(exclude_none=True) for c in body.changes], body.reason)


class StaffIn(BaseModel):
    user_id: str | None = None               # 비우면 U + 다음 번호 (예: U13)
    user_name: str
    role_code: str
    home_shift_type: str | None = None       # 관리자 말고는 필요
    home_process_code: str | None = None
    home_process_code_2: str | None = None
    procs: list[str] | None = None
    password: str                            # 서버가 scrypt 해시로만 저장 (응답·이력에 없음)
    reason: str | None = None


@router.post("/staff")
def staff_create(body: StaffIn, actor: Actor = Depends(require("STAFF", "EDIT")), db: Db = Depends(get_db)):
    """직원 추가 (USR-04 [제안]): 수정 이력 v0 "직원 추가". 아이디가 이미 있으면 409 INVALID_STATE(DUPLICATE),
    비밀번호 최소 길이 = MOM_PASSWORD_MIN_LENGTH (기본 8, [선택 필요])"""
    return staff.create_user(db, actor.user_id, body.model_dump())


class StaffPatch(BaseModel):
    user_name: str | None = None
    role_code: str | None = None             # 작업자가 아니게 되면 담당 공정 두 칸을 비움
    is_active: bool | None = None            # false = 사용 중지 (로그인·3D 라인 뷰 막힘, 배치표에서 빠짐), true = 다시 사용
    password: str | None = None              # 비밀번호 다시 정하기 (이력에는 "비밀번호 바꿈"만)
    home_shift_type: str | None = None       # 배치는 보통 USR-03으로 (역할을 바꾸며 같이 정할 때)
    home_process_code: str | None = None
    home_process_code_2: str | None = None
    procs: list[str] | None = None
    reason: str | None = None


@router.patch("/staff/{user_id}")
def staff_update(user_id: str, body: StaffPatch, actor: Actor = Depends(require("STAFF", "EDIT")), db: Db = Depends(get_db)):
    """직원 정보 고치기 (USR-05 [제안]): 보낸 칸만. 지금 로그인한 관리자는 자기 자신을 사용 중지하거나 MGR이 아닌 역할로 바꾸지
    못하고, 사용 중인 MGR이 0명이 되는 변경은 VALIDATION. 바뀐 칸이 없으면 VALIDATION(NO_CHANGE)"""
    change = body.model_dump(exclude_none=True)
    reason = change.pop("reason", None)
    return staff.update_user(db, actor.user_id, user_id, change, reason)
