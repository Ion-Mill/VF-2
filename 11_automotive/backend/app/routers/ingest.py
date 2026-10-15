"""시뮬레이터(설비 수집기) → 플랫폼 (서비스 키 X-Service-Key: ingest). 설비 쪽으로는 아무것도 보내지 않는다 (FR-AST-COM-11).

시각(at)을 비우면 시연 시계(app_now). 시뮬레이터가 자기 시각을 보내면 그 시각으로 기록한다.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..security import service_key
from ..services import cmm
from .common import changed

router = APIRouter(prefix="/api/ingest", tags=["설비 데이터 받기"], dependencies=[Depends(service_key("ingest"))])


class AlarmIn(BaseModel):
    equipment_id: str
    alarm_code: str
    occurred_at: datetime | None = None
    lot_no: str | None = None
    prev_alarm_event_id: int | None = None
    is_injected: bool = False           # 시연용 주입 (NFR-DATA-11)
    scenario_code: str | None = None


@router.post("/alarms")
def alarm(body: AlarmIn, db: Db = Depends(get_db)):
    """알람 1건 → 기록 + 등급별 알림 + 반복 알람 판정"""
    return {"alarm_event_id": db.scalar("alarms.ingest", **body.model_dump())}


class ClearIn(BaseModel):
    cleared_at: datetime | None = None


@router.post("/alarms/{alarm_event_id}/clear")
def alarm_clear(alarm_event_id: int, body: ClearIn, db: Db = Depends(get_db)):
    """알람 해제 시각"""
    return changed(db.exec("alarms.clear", alarm_event_id=alarm_event_id, cleared_at=body.cleared_at), "알람 해제")


class StateIn(BaseModel):
    equipment_id: str
    state_code: str = Field(pattern="^(RUN|IDLE|BLOCKED|SETUP|DOWN|MAINT)$")
    at: datetime | None = None
    execution: str | None = Field(None, pattern="^(ACTIVE|READY|STOPPED)$")
    warn_marker: bool = False
    reason_suggested_code: str | None = None
    alarm_event_id: int | None = None   # DOWN이면 필수 (정지 등급 알람)
    pm_record_id: int | None = None     # MAINT면 필수


@router.post("/state")
def state(body: StateIn, db: Db = Depends(get_db)):
    """설비 상태 바뀜 → 구간 닫고 열기 (같은 상태 다시 오면 그대로)"""
    return {"state_log_id": db.scalar("ingest.state_change", **body.model_dump())}


class ProductionIn(BaseModel):
    lot_no: str
    equipment_id: str
    worker_user_id: str
    gq: int = Field(ge=0)
    rq: int = Field(0, ge=0)
    sq: int = Field(0, ge=0)
    at: datetime | None = None
    shift_id: str | None = None


@router.post("/production")
def production(body: ProductionIn, db: Db = Depends(get_db)):
    """공정 실적 더하기 (OP-30이면 공구 사용 누적·수명 알림)"""
    return {"op_report_id": db.scalar("ingest.production", **body.model_dump())}


class WipIn(BaseModel):
    buffer_code: str
    wip_qty: int = Field(ge=0)
    soak_shelf_qty: int | None = Field(None, ge=0)
    at: datetime | None = None
    interval_type: str = Field("MIN5", pattern="^(MIN5|MIN1)$")


@router.post("/wip")
def wip(body: WipIn, db: Db = Depends(get_db)):
    """재공 수량 (한도 넘김은 DB가 막음, R-13)"""
    db.exec("ingest.wip", **body.model_dump())
    return {"ok": True}


class SensorRow(BaseModel):
    sensor_code: str
    sampled_at: datetime
    interval_type: str = Field("MIN1_AVG", pattern="^(MIN1_AVG|SEC5)$")
    value: float


class SensorsIn(BaseModel):
    equipment_id: str
    rows: list[SensorRow] = Field(max_length=5000)


@router.post("/sensors")
def sensors(body: SensorsIn, db: Db = Depends(get_db)):
    """센서 값 여러 개 (최대 5000)"""
    n = db.exec("ingest.sensors", equipment_id=body.equipment_id, rows=[r.model_dump(mode="json") for r in body.rows])
    return {"inserted": n}


class BottleneckIn(BaseModel):
    process_code: str
    cause_code: str = Field(pattern="^(C1|C2|C3|C4|FAILURE|BASE)$")
    at: datetime | None = None
    alarm_event_id: int | None = None


@router.post("/bottleneck")
def bottleneck(body: BottleneckIn, db: Db = Depends(get_db)):
    """병목 공정 바뀜"""
    return {"bottleneck_log_id": db.scalar("ingest.bottleneck", **body.model_dump())}


class OrderIn(BaseModel):
    product_code: str
    order_qty: int = Field(gt=0)
    due_at: datetime
    at: datetime | None = None


@router.post("/orders")
def order(body: OrderIn, db: Db = Depends(get_db)):
    """작업지시 만들기 (시뮬레이터 계획) → PO-YYMM-NNN"""
    return {"order_no": db.scalar("ingest.order_create", **body.model_dump())}


class LotStartIn(BaseModel):
    order_no: str
    material_lot_no: str
    input_qty: int = Field(gt=0)
    at: datetime | None = None


@router.post("/lots")
def lot_start(body: LotStartIn, db: Db = Depends(get_db)):
    """로트 투입 (OP-10 시작): 원자재 사용·검사 방식·작업지시 생산 중 (R-06a·R-08·R-28)"""
    return {"lot_no": db.scalar("ingest.lot_start", **body.model_dump())}


@router.post("/lots/{lot_no}/arrived")
def lot_arrived(lot_no: str, db: Db = Depends(get_db)):
    """로트가 OP-50에 도착 → 검사 대기"""
    db.scalar("ingest.lot_arrived", lot_no=lot_no)
    return {"ok": True}


class CmmIn(BaseModel):
    file_name: str
    content: str = Field(max_length=1_000_000)
    file_ref: str | None = None


@router.post("/cmm")
def cmm_result(body: CmmIn, db: Db = Depends(get_db)):
    """CMM 결과 파일 내용 (공유 폴더 대신 API로 보낼 때)"""
    return cmm.import_text(db, body.file_name, body.content, body.file_ref)
