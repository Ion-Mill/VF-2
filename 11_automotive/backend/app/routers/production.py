"""생산: 목표·작업지시·지표·로트·보류 (PRD-01·03·05, QLT-01 판정, API명세서 LINE-03·04·05, LOT-01~03).
R-24a·R-25~R-29·R-48·R-88."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, require, require_any
from .common import must, period

router = APIRouter(prefix="/api", tags=["생산·로트"])


@router.get("/production/target")
def target(shift_id: str | None = None,
           _: Actor = Depends(require_any(("LINE_VIEW", "VIEW"), ("FIELD_VIEW", "VIEW"), ("PRODUCTION", "VIEW"))),
           db: Db = Depends(get_db)):
    """목표 대비 실적·예측 (LINE-03, FR-PRD-01-15, FR-AST-02-04). 총 목표 = 목표 + 이월 (이월은 같은 날
    주간 → 야간만, 확정 전이면 잠정). 예측·부족·목표 미달 위험(예측 < 총 목표의 90%), 손실 합(추정), 시간대별 실적.
    shift_id를 비우면 지금(또는 가장 최근 시작한) 교대"""
    row = must(db.one("line.shift_progress", shift_id=shift_id), "교대")
    return {**row, "hourly": db.all("line.shift_hourly", shift_id=row["shift_id"])}


@router.get("/production/orders")
def orders(shift_id: str | None = None, status: str | None = None, frm: datetime | None = Query(None, alias="from"),
           to: datetime | None = None, limit: int = Query(100, le=500), _: Actor = Depends(require("PRODUCTION", "VIEW")),
           db: Db = Depends(get_db)):
    """작업지시 진행 표 (LINE-05, PRD-03): 목표·완료·불량·로트·지금 공정·납기·지연 여부·상태"""
    return db.all("production.orders", shift_id=shift_id, status=status, limit=limit, **{"from": frm, "to": to})


@router.get("/kpi")
def kpi(scope: str = Query("line", pattern="^(line|equipment)$"), frm: date | None = Query(None, alias="from"),
        to: date | None = None, shift_id: str | None = None, equipment_id: str | None = None,
        _: Actor = Depends(require("KPI", "VIEW")), db: Db = Depends(get_db)):
    """지표 (LINE-04): OEE·가동률·성능·양품률(교대별)과 주의 표시, MTTR·MTBF(설비별 30일, 주의 = MTTR 120분 초과).
    scope=line 라인 OEE (OP-30 2대 합 — 지표 카드 처음 값), scope=equipment 설비별. shift_id 또는 from~to (기본 오늘)"""
    if frm and to and (to < frm or (to - frm).days > 31):
        raise AppError(422, "VALIDATION", "기간은 31일까지, 시작 ≤ 끝")
    period_ = {"shift_id": shift_id, "from": frm, "to": to}
    rows = (db.all("production.kpi_line", **period_) if scope == "line"
            else db.all("production.kpi_equipment", equipment_id=equipment_id, **period_))
    return {"scope": scope, "rows": rows, "reliability": db.all("assistant.reliability", equipment_id=equipment_id)}


@router.get("/kpi/stops")
def stop_ranking(frm: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                 _: Actor = Depends(require("KPI", "VIEW")), db: Db = Depends(get_db)):
    """정지 사유 순위 (손실 정지만, 계획 정지 제외). 3D 화면에서는 뺐고 교대 보고서 필수 정지 칸·비서 질문에 쓴다"""
    frm, to = period(db, frm, to, default_hours=24 * 7)
    return db.all("production.stop_ranking", **{"from": frm, "to": to})


# ---------------- 로트 (LOT-01~03) ----------------
@router.get("/lots")
def lots(status: str | None = None, order_no: str | None = None, limit: int = Query(100, le=500),
         _: Actor = Depends(require("PRODUCTION", "VIEW")), db: Db = Depends(get_db)):
    """로트 목록 (LOT-01) — 작업지시·상태로 거르기"""
    return db.all("production.lots", status=status, order_no=order_no, limit=limit)


@router.get("/lots/suspects")
def suspect_lots(since: datetime | None = Query(None, description="이 시각 뒤 (비우면 7일)"),
                 _: Actor = Depends(require("LOT_TRACE", "VIEW")), db: Db = Depends(get_db)):
    """의심 로트 제안 목록 (API-LOT-01, FR-PRD-05-05, 2026-10-20): 정지 등급 알람 때 그 설비에서 가공 중이던 로트(연쇄 알람은 첫
    알람부터)·공구 수명을 넘겨 가공한 로트. 제안만 — 알림을 만들지 않고 보류는 반장이 정한다"""
    return db.all("production.suspect_lots", alarm_event_id=None, lot_no=None, since=since)


@router.get("/lots/{lot_no}")
def lot(lot_no: str, _: Actor = Depends(require("PRODUCTION", "VIEW")), db: Db = Depends(get_db)):
    """로트 1개 (완료 수량·검사 방식·출하 수량)"""
    return must(db.one("production.lot", lot_no=lot_no), "로트")


@router.get("/lots/{lot_no}/trace")
def trace(lot_no: str, _: Actor = Depends(require("LOT_TRACE", "VIEW")), db: Db = Depends(get_db)):
    """로트 추적 (LOT-01, FR-PRD-05): 원자재 → 공정·설비·작업자 → 검사 → 보류 → 출하 + 의심 로트 제안 이유(suspect, 2026-10-20)"""
    row = must(db.one("production.lot_trace", lot_no=lot_no), "로트")
    return {**row, "suspect": db.all("production.suspect_lots", alarm_event_id=None, lot_no=lot_no, since=None)}


@router.post("/lots/{lot_no}/judge")
def judge(lot_no: str, _: Actor = Depends(require("QUALITY", "CHECK")), db: Db = Depends(get_db)):
    """로트 판정 다시 돌리기 (보통은 검사 결과가 들어올 때 DB가 부른다). PASS / HOLD_REVIEW / NOT_READY"""
    return {"result": db.scalar("production.lot_judge", lot_no=lot_no)}


@router.get("/holds")
def holds(open_only: bool = True, _: Actor = Depends(require("LOT_TRACE", "VIEW")), db: Db = Depends(get_db)):
    """보류 목록 (열린 것만 기본)"""
    return db.all("production.holds", open_only=open_only)


def _open_hold(db: Db, lot_no: str) -> int:
    row = db.one("production.open_hold", lot_no=lot_no)
    if row is None:
        raise AppError(409, "INVALID_STATE", f"로트 {lot_no}에 열린 보류가 없음")
    return int(row["hold_id"])


class HoldIn(BaseModel):
    trigger_type: str = Field("SUPERVISOR", description="보류 계기 코드 (논리 ERD lot_hold.trigger_type)")
    reason: str
    next_lots: int = Field(2, ge=1, le=2, description="다음 몇 로트까지 강화 검사 (R-26, 1 또는 2)")
    alarm_event_id: int | None = None
    tool_id: str | None = None


@router.post("/lots/{lot_no}/hold")
def hold(lot_no: str, body: HoldIn, actor: Actor = Depends(require("LOT_HOLD", "INPUT")), db: Db = Depends(get_db)):
    """보류 (LOT-02, 사람만 — 비서는 제안만, R-51). 보류되면 측정은 강화 검사로 바뀐다. 로트 상태를 돌려준다"""
    hold_id = db.scalar("production.lot_hold", lot_no=lot_no, actor=actor.user_id, trigger_type=body.trigger_type,
                        reason=body.reason, next_lots=body.next_lots, alarm_event_id=body.alarm_event_id, tool_id=body.tool_id)
    return {"hold_id": hold_id, "lot": db.one("production.lot", lot_no=lot_no)}


class ReleaseIn(BaseModel):
    pass_qty: int | None = Field(None, ge=0, description="해제 때 합격 수량 (비우면 완료 수량 − 폐기 수량)")


@router.post("/lots/{lot_no}/release")
def release(lot_no: str, body: ReleaseIn, actor: Actor = Depends(require("LOT_HOLD", "INPUT")), db: Db = Depends(get_db)):
    """보류 해제 (LOT-02, SUP·MGR) — 합격 수량을 정해 출하 가능으로 (합격 0개면 INVALID_STATE — 전부 불량은 폐기)"""
    db.scalar("production.lot_release", hold_id=_open_hold(db, lot_no), actor=actor.user_id, pass_qty=body.pass_qty)
    return {"lot": db.one("production.lot", lot_no=lot_no)}


class ScrapIn(BaseModel):
    qty: int = Field(ge=0, description="폐기 수량")


@router.post("/lots/{lot_no}/scrap")
def scrap_propose(lot_no: str, body: ScrapIn, actor: Actor = Depends(require("LOT_SCRAP", "CREATE")),
                  db: Db = Depends(get_db)):
    """폐기 제안 (LOT-03, SUP) → 승인 (MGR)"""
    db.scalar("production.scrap_propose", hold_id=_open_hold(db, lot_no), actor=actor.user_id, qty=body.qty)
    return {"lot": db.one("production.lot", lot_no=lot_no)}


@router.post("/lots/{lot_no}/scrap/approve")
def scrap_approve(lot_no: str, actor: Actor = Depends(require("LOT_SCRAP", "APPROVE")), db: Db = Depends(get_db)):
    """폐기 승인 (LOT-03, MGR)"""
    db.scalar("production.scrap_approve", hold_id=_open_hold(db, lot_no), actor=actor.user_id)
    return {"lot": db.one("production.lot", lot_no=lot_no)}
