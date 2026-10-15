"""기준 정보·코드·설정·시연 (SCR-25, API명세서 SET-02·03, SIM-01~03, NFR-DATA-08·10).

설정을 바꾸는 것은 MGR만 (R-58 — SETTINGS·SETTING). 알림 규칙 설정(SET-01)은 notifications.py.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, User, current_user, require
from .common import changed

router = APIRouter(prefix="/api", tags=["기준 정보·설정·시연"])


@router.get("/codes")
def codes(code_group: str | None = None, _: User = Depends(current_user), db: Db = Depends(get_db)):
    """코드 한국어 이름 (논리 ERD 6장). 화면과 비서가 같은 이름을 쓰게 한다."""
    return db.all("common.codes", code_group=code_group)


@router.get("/dataset")
def dataset(_: User = Depends(current_user), db: Db = Depends(get_db)):
    """가상 데이터 정보 (R-59, NFR-DATA-08). 화면 구석의 '가상 운영 데이터' 표시는 2026-10-07 팀 UI 검토로 뺐다 —
    값 꼬리표 [가상]·비서 답의 '가상'에 쓴다 (NFR-USE-06)."""
    return db.one("common.dataset_info")


@router.get("/admin/retention")
def retention(_: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """보관 기간이 지난 행 수 (지우지 않음). 실제 삭제·집계 방식은 [선택 필요: 기술 회의]"""
    return db.all("reports.retention")


# ---------------- 설정 (SET-02·03) ----------------
@router.get("/settings/targets")
def targets(_: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """교대 목표(90)·하루 목표(180) — 지금 교대와 다가오는 교대 (SET-02). 총 목표 = 목표 + 이월 (R-88)"""
    return db.all("settings.targets")


class TargetsIn(BaseModel):
    shift_target_qty: int | None = Field(None, ge=0)
    daily_target_qty: int | None = Field(None, ge=0)


@router.patch("/settings/targets")
def targets_update(body: TargetsIn, _: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """목표 바꾸기 (MGR, SET-02). 아직 시작하지 않은 교대·근무일에만 — 지난·진행 중 값은 그대로. 야간 이월을 다시 계산한다"""
    if body.shift_target_qty is None and body.daily_target_qty is None:
        raise AppError(422, "VALIDATION", "바꿀 값이 없음", {"reason": "NO_CHANGE"})
    out = db.one("settings.targets_update", **body.model_dump())
    db.scalar("settings.targets_refresh_carry")
    return out


@router.get("/settings/users")
def users(_: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """사용자·역할 목록 (SET-03, NFR-SEC-04). 비밀번호 해시는 내보내지 않는다"""
    return db.all("settings.users")


class UserIn(BaseModel):
    user_id: str
    user_name: str | None = None
    role_code: str | None = Field(None, pattern="^(OPR|MNT|SUP|MGR)$")
    home_shift_type: str | None = Field(None, pattern="^(DAY|NIGHT)$")
    home_process_code: str | None = None
    home_process_code_2: str | None = None   # 두 번째 담당 공정 (OPR만, 2026-10-10)
    is_active: bool | None = None      # 퇴사·중지 = false (행은 지우지 않음, 6.53 #20)


@router.patch("/settings/users")
def user_update(body: UserIn, _: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """사용자·역할 고치기 (MGR, SET-03). 권한 표는 다음 요청부터 (60초 캐시)"""
    return changed(db.exec("settings.user_update", **body.model_dump()), "사용자")


# ---------------- 시연 (SIM-01·02, NFR-DATA-10·11) ----------------
@router.get("/sim/clock")
def sim_clock(_: User = Depends(current_user), db: Db = Depends(get_db)):
    """시연 시계 지금 값 (app_now)"""
    return db.one("common.sim_clock")


class SimClockIn(BaseModel):
    mode: str = "SIM"
    skip_to_1700: bool = Field(False, description="넘기기: 지금 → 오늘 17:00 (API-SIM-02, 2026-10-13 — 다음 날 06:00으로 넘기기는 없음)")
    sim_at: datetime | None = Field(None, description="시계를 이 시각으로 (MGR 준비용 — 시연 발표 중 넘기기는 skip_to_1700)")
    speed: float | None = Field(None, description="배속 180·60·10·1 (1초 = 1분 → 60)")
    paused: bool | None = None


@router.post("/sim/clock")
def set_sim_clock(body: SimClockIn, user: User = Depends(current_user), db: Db = Depends(get_db)):
    """시연 시계 배속·일시정지·넘기기 (API-SIM-02, NFR-DATA-10). 시연 모드에서는 누구나 배속·일시정지·17:00 넘기기,
    시각 직접 지정(sim_at)과 시연 모드 밖은 MGR만. 지금 시연 시각을 돌려준다.
    넘기는 동안 남은 주간 교대 기록을 만드는 일은 시뮬레이터(생성기 Realtime.skip) 몫 — 서버 연결 방식은 [선택 필요: 기술 회의]"""
    if (not get_settings().demo_mode or body.sim_at is not None) and user.role_code != "MGR":
        raise AppError(403, "FORBIDDEN", "시각 직접 지정과 시연 모드 밖 시계 바꾸기는 MGR만")
    sim_at = body.sim_at
    if body.skip_to_1700:
        t = db.one("common.today_1700")
        if t["past"] in (True, "t"):
            raise AppError(409, "INVALID_STATE", "이미 17:00이 지남 — 넘기기는 지금 → 17:00만", {"reason": "PAST_1700"})
        sim_at = t["at"]
    return db.one("common.sim_set", mode=body.mode, sim_at=sim_at, speed=body.speed, paused=body.paused)


class InjectIn(BaseModel):
    equipment_id: str
    alarm_code: str
    scenario_code: str = Field(pattern="^S[1346]$",
                               description="사건 버튼 S1·S3·S4·S6 (2026-10-13 — S2·S5는 과거 기록이라 버튼 없음)")
    at: datetime | None = None       # 비우면 시연 시계 지금
    lot_no: str | None = None


@router.post("/sim/inject")
def inject(body: InjectIn, user: User = Depends(current_user), db: Db = Depends(get_db)):
    """시연 사건 넣기 (SIM-01, NFR-DATA-11) — 알람 1건을 '주입' 표시로 기록 (알림·반복 알람 판정은 실제와 같게).
    시연 모드가 아니면 MGR만"""
    if not get_settings().demo_mode and user.role_code != "MGR":
        raise AppError(403, "FORBIDDEN", "시연 모드가 아니면 MGR만 사건을 넣을 수 있음")
    return {"alarm_event_id": db.scalar("alarms.ingest", equipment_id=body.equipment_id, alarm_code=body.alarm_code,
                                        occurred_at=body.at, lot_no=body.lot_no, prev_alarm_event_id=None, is_injected=True,
                                        scenario_code=body.scenario_code)}


@router.post("/sim/reset")
def sim_reset(_: User = Depends(current_user), db: Db = Depends(get_db)):
    """시연 데이터 처음으로 (SIM-03, 시연 모드만): 운영 데이터를 시연 기준점으로 되돌리고 시연 시계를 그 시각에 멈춘다.
    설정·계정·접속 기록은 그대로. 화면에는 실시간 connection 사건이 가서 전부 다시 읽는다. 기준점이 없으면 INVALID_STATE"""
    if not get_settings().demo_mode:
        raise AppError(403, "FORBIDDEN", "시연 모드에서만 시연 데이터를 되돌릴 수 있음")
    return db.one("common.demo_reset")["result"]


@router.post("/sim/snapshot")
def sim_snapshot(_: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """시연 기준점 만들기 (시연 모드, MGR): 지금 운영 데이터를 SIM-03의 "처음"으로 삼는다.
    목업·생성기 적재 뒤에는 자동으로 만들어진다"""
    if not get_settings().demo_mode:
        raise AppError(403, "FORBIDDEN", "시연 모드에서만 시연 기준점을 바꿀 수 있음")
    return {"tables": db.scalar("common.demo_snapshot")}
