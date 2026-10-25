"""기준 정보·코드·설정·시연 (SCR-25, API명세서 SET-02·03, SIM-01~03, NFR-DATA-08·10).

설정을 바꾸는 것은 MGR만 (R-58 — SETTINGS·SETTING). 알림 규칙 설정(SET-01)은 notifications.py.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, User, current_user, require, require_any
from ..services import sim_link
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
def _sim_control(user: User) -> None:
    """시연 조작(시계·사건·처음으로·상황 일으키기)은 MOM_SIM_CONTROL_USERS에 든 사람만 (비우면 누구나 — 2026-10-24).
    여러 명이 같은 공장(DB 1개)을 볼 때, 누가 [처음으로]를 눌러 모두의 10/1 기록이 지워지는 일을 막는다"""
    allowed = get_settings().sim_control_users
    if allowed and user.user_id not in allowed:
        raise AppError(403, "FORBIDDEN", "시연 조작은 진행자만 할 수 있음 (MOM_SIM_CONTROL_USERS)", {"reason": "SIM_CONTROL"})


@router.get("/sim/clock")
def sim_clock(_: User = Depends(current_user), db: Db = Depends(get_db)):
    """시연 시계 지금 값 (app_now). 시뮬레이터가 이어져 있으면(MOM_SIM_URL) 시뮬레이터 시계·사건 버튼 상태·회차(run_id)"""
    if sim_link.enabled():
        return sim_link.call("GET", "sim/clock")
    return db.one("common.sim_clock")


LEGACY_SKIP = {"TODAY_17:00": "TODAY_DAY_END", "TODAY_20:00": "TODAY_NIGHT_START"}   # 시각이 이름에 박혀 있던 옛 이름 (생성기와 같음)


class SimClockIn(BaseModel):
    mode: str = "SIM"
    skip_to_1700: bool = Field(False, description="넘기기: 지금 → 오늘 주간 교대 끝 (옛 이름 그대로, API-SIM-02 — 다음 날 아침으로 넘기기는 없음)")
    skip: str | None = Field(None, pattern="^TODAY_(DAY_END|NIGHT_START|17:00|20:00)$",
                             description="넘기기 목표 (생성기 Realtime.skip과 같은 이름): TODAY_DAY_END(오늘 주간 교대 끝) / "
                                         "TODAY_NIGHT_START(야간 교대 시작 — 주간 끝 뒤 휴무). 옛 이름 TODAY_17:00·TODAY_20:00도 받음 "
                                         "(시각은 그날 교대에서, 2026-10-25)")
    sim_at: datetime | None = Field(None, description="시계를 이 시각으로 (MGR 준비용 — 시연 발표 중 넘기기는 skip_to_1700)")
    speed: float | None = Field(None, description="배속 180·60·10·1 (1초 = 1분 → 60)")
    paused: bool | None = None


@router.post("/sim/clock")
def set_sim_clock(body: SimClockIn, user: User = Depends(current_user), db: Db = Depends(get_db)):
    """진행자 제한: MOM_SIM_CONTROL_USERS (2026-10-24).
    시연 시계 배속·일시정지·넘기기 (API-SIM-02, NFR-DATA-10). 시연 모드에서는 누구나 배속·일시정지·주간 끝 넘기기,
    시각 직접 지정(sim_at)과 시연 모드 밖은 MGR만. 지금 시연 시각을 돌려준다.
    넘기는 동안 남은 주간 교대 기록을 만드는 일은 시뮬레이터(생성기 Realtime.skip) 몫 — 서버 연결 방식은 [선택 필요: 기술 회의]"""
    _sim_control(user)
    target = body.skip or ("TODAY_DAY_END" if body.skip_to_1700 else None)
    if sim_link.enabled() and body.sim_at is None:
        # 시뮬레이터가 시계의 주인 — 넘기면 DB 중계가 DB 시계를 따라 맞춘다 (배속·일시정지·넘기기는 시연 발표자 누구나, 기획서 15장)
        return sim_link.call("POST", "sim/clock", {k: v for k, v in {"speed": body.speed, "paused": body.paused, "skip": target}.items()
                                                    if v is not None})
    if (not get_settings().demo_mode or body.sim_at is not None) and user.role_code != "MGR":
        raise AppError(403, "FORBIDDEN", "시각 직접 지정과 시연 모드 밖 시계 바꾸기는 MGR만")
    sim_at = body.sim_at
    if target:
        name = LEGACY_SKIP.get(target, target).split("_", 1)[1]          # DAY_END | NIGHT_START
        label = "주간 교대 끝" if name == "DAY_END" else "야간 교대 시작"
        t = db.one("common.skip_target", target=name)
        if t["at"] is None:
            raise AppError(409, "INVALID_STATE", f"오늘 {label}이 없음 (휴무일 또는 교대 없음)", {"reason": "NO_SHIFT_" + name})
        if t["past"] in (True, "t"):
            raise AppError(409, "INVALID_STATE", f"이미 {label}이 지남 — 넘기기는 지금 → 오늘 {label}만", {"reason": "PAST_" + name})
        sim_at = t["at"]
    return db.one("common.sim_set", mode=body.mode, sim_at=sim_at, speed=body.speed, paused=body.paused)


class InjectIn(BaseModel):
    equipment_id: str | None = Field(None, description="시뮬레이터가 이어져 있지 않을 때 필수 (이어져 있으면 사건이 대상 설비를 정함)")
    alarm_code: str | None = Field(None, description="시뮬레이터가 이어져 있지 않을 때 필수")
    scenario_code: str = Field(pattern="^S[1346]$",
                               description="사건 버튼 S1·S3·S4·S6 (2026-10-13 — S2·S5는 과거 기록이라 버튼 없음)")
    at: datetime | None = None       # 비우면 시연 시계 지금
    lot_no: str | None = None


@router.post("/sim/inject")
def inject(body: InjectIn, user: User = Depends(current_user), db: Db = Depends(get_db)):
    """시연 사건 넣기 (SIM-01, NFR-DATA-11) — 알람 1건을 '주입' 표시로 기록 (알림·반복 알람 판정은 실제와 같게).
    시연 모드가 아니면 MGR만"""
    _sim_control(user)
    if sim_link.enabled():
        # 시뮬레이터가 사건을 처음부터 끝까지 돌린다 (알람 연쇄·정지·로트) — 알람은 DB 중계로 들어온다
        return sim_link.call("POST", "sim/inject", {"scenario_code": body.scenario_code})
    if not get_settings().demo_mode and user.role_code != "MGR":
        raise AppError(403, "FORBIDDEN", "시연 모드가 아니면 MGR만 사건을 넣을 수 있음")
    if not body.equipment_id or not body.alarm_code:
        raise AppError(422, "VALIDATION", "equipment_id·alarm_code가 필요함")
    return {"alarm_event_id": db.scalar("alarms.ingest", equipment_id=body.equipment_id, alarm_code=body.alarm_code,
                                        occurred_at=body.at, lot_no=body.lot_no, prev_alarm_event_id=None, is_injected=True,
                                        scenario_code=body.scenario_code)}


@router.post("/sim/reset")
def sim_reset(user: User = Depends(current_user), db: Db = Depends(get_db),
              x_presenter_key: Annotated[str | None, Header(description="최종용 시연 서버의 발표자 키 (그대로 넘김, 2026-10-25)")] = None):
    """시연 데이터 처음으로 (SIM-03, 시연 모드만): 운영 데이터를 시연 기준점으로 되돌리고 시연 시계를 그 시각에 멈춘다.
    설정·계정·접속 기록은 그대로. 화면에는 실시간 connection 사건이 가서 전부 다시 읽는다. 기준점이 없으면 INVALID_STATE"""
    _sim_control(user)
    if sim_link.enabled():
        # 시뮬레이터만 되돌린다 — 회차가 바뀌면 DB 중계가 DB를 시연 기준점으로 되돌린다 (두 번 되돌리지 않게)
        return sim_link.call("POST", "sim/reset", presenter_key=x_presenter_key or get_settings().presenter_key or None)
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


# ---------------- 시뮬레이터에만 있는 시연 조작 (2026-10-23, 화면 → 백엔드 전환 C2 — MOM_SIM_URL이 있을 때만) ----------------
def _need_sim():
    if not sim_link.enabled():
        raise AppError(404, "NOT_FOUND", "시뮬레이터가 이어져 있지 않음 (MOM_SIM_URL)")


class SimFireIn(BaseModel):
    kind: str = Field(pattern="^(warn|stop|air|maint)$", description="알림 미리보기 [상황 일으키기] (API-SIM-01 딸림)")


@router.post("/sim/fire")
def sim_fire(body: SimFireIn, user: User = Depends(current_user)):
    """알림 미리보기 [상황 일으키기] — 시뮬레이터가 지금 분에 진짜 알람을 일으킨다 (화면 담당 확인용)"""
    _sim_control(user)
    _need_sim()
    return sim_link.call("POST", "sim/fire", {"kind": body.kind})


class SimEquipmentIn(BaseModel):
    equipment_id: str


@router.post("/sim/work-record-confirmed")
def sim_work_record_confirmed(body: SimEquipmentIn,
                              actor: Actor = Depends(require_any(("WORK_RECORD", "CONFIRM"), ("WORK_RECORD_SIMPLE", "CONFIRM")))):
    """작업기록서 확정 뒤 고장 설비 복귀 (API-MNT-11 시연 연결): 시뮬레이터가 그 설비의 고장(DOWN)을 끝낸다"""
    _need_sim()
    return sim_link.call("POST", "maint/work-records/confirm", {"equipment_id": body.equipment_id, "by": actor.user_id})


class SimPmStartIn(BaseModel):
    equipment_id: str
    minutes: int = Field(60, ge=1, le=480)
    pm_task_ids: list[str] = []


@router.post("/sim/pm-start")
def sim_pm_start(body: SimPmStartIn, actor: Actor = Depends(require("PM_RECORD", "CREATE"))):
    """[정비 시작] (API-PM-02 시연 연결): 시뮬레이터가 그 설비를 정비(MAINT)로 둔다. 기록은 DB 중계로 들어온다"""
    _need_sim()
    return sim_link.call("POST", "maint/pm-start", {**body.model_dump(), "role": "MNT", "user_id": actor.user_id})


class SimPmEndIn(BaseModel):
    equipment_id: str
    pm_task_ids: list[str] = []
    done_by: str | None = None
    result: str = "NORMAL"
    memo: str | None = None
    items: list[dict] = []


@router.post("/sim/pm-end")
def sim_pm_end(body: SimPmEndIn, actor: Actor = Depends(require("PM_RECORD", "CREATE"))):
    """[정비 끝] (API-PM-02 시연 연결): 시뮬레이터가 정비를 끝내고 실시 기록을 남긴다"""
    _need_sim()
    return sim_link.call("POST", "maint/pm-end", {**body.model_dump(), "role": "MNT", "user_id": actor.user_id})


# ---------------- 비서가 다듬은 문장 (2026-10-24, 화면 → 백엔드 전환 — 시연 서버 llm_compose를 그대로 씀) ----------------
@router.post("/assist/{kind}")
def assist_text(kind: str, body: dict, _: User = Depends(current_user)):
    """화면이 기본 문장을 보여 주면서 비서(외부 Claude)가 다듬어 둔 문장이 있는지 묻는다 — 기다리지 않는다.
    kind = work-order-text · guide-card-text · briefing-text · alarm-text. 다듬기는 시연 서버(MOM_LLM_COMPOSE=1)가 비서 서비스에
    백그라운드로 맡기고 받아 둔다 (frontend/tools/llm_compose.py). 시뮬레이터가 없거나 꺼져 있거나 실패하면 {ready: false} — 화면은 기본 문장"""
    if kind not in ("work-order-text", "guide-card-text", "briefing-text", "alarm-text"):
        raise AppError(404, "NOT_FOUND", f"없는 문장 종류: {kind}")
    if not sim_link.enabled():
        return {"ready": False}
    try:
        return sim_link.call("POST", f"assist/{kind}", body)
    except AppError:
        return {"ready": False}
