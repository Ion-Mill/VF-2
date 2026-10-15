"""알람·지침카드·정지 사유 (MNT-02, PRD-01 정지 사유, R-21 — API명세서 MNT-01, LINE-07·08)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, permissions, require, require_any
from .common import changed, must, period

router = APIRouter(prefix="/api", tags=["알람·정지"])
ALARM_VIEW = require_any(("LINE_VIEW", "VIEW"), ("FIELD_VIEW", "VIEW"), ("GUIDE_CARD", "VIEW"))


@router.get("/alarms")
def alarms(frm: datetime | None = Query(None, alias="from"), to: datetime | None = None, equipment_id: str | None = None,
           alarm_code: str | None = None, limit: int = Query(200, le=1000), _: Actor = Depends(ALARM_VIEW),
           db: Db = Depends(get_db)):
    """기간 안 알람 목록 (기본 최근 24시간)"""
    frm, to = period(db, frm, to)
    return db.all("alarms.list", equipment_id=equipment_id, alarm_code=alarm_code, limit=limit, **{"from": frm, "to": to})


@router.get("/alarms/{alarm_event_id}")
def alarm(alarm_event_id: int, _: Actor = Depends(ALARM_VIEW), db: Db = Depends(get_db)):
    """알람 1건 + 코드집 내용"""
    return must(db.one("alarms.get", alarm_event_id=alarm_event_id), "알람")


@router.get("/maint/guide-card/{alarm_event_id}")
def guide_card(alarm_event_id: int, _: Actor = Depends(require("GUIDE_CARD", "VIEW")), db: Db = Depends(get_db)):
    """지침카드 (MNT-01, FR-MNT-02): 알람·심각도·누가·연쇄 알람·먼저 할 일·안전 블록·생산 영향·지난 기록·출처 목록.
    비서는 이 재료로 문장만 쓴다. 고정 서식 블록(잠금·표지)은 화면이 그대로 붙인다 (R-33)"""
    card = must(db.one("alarms.guide_card", alarm_event_id=alarm_event_id), "알람")
    card["same_cases"] = db.all("alarms.same_cases", alarm_code=card["alarm_code"], equipment_id=card["equipment_id"])
    return card


@router.get("/downtimes")
def downtimes(shift_id: str | None = None, frm: datetime | None = Query(None, alias="from"), to: datetime | None = None,
              equipment_id: str | None = None, pending_only: bool = False,
              _: Actor = Depends(require("DOWNTIME_REASON", "VIEW")), db: Db = Depends(get_db)):
    """정지 구간 목록 + 비서 추천 사유 (LINE-07, SCR-14 — 필요 여부 판단 중). shift_id 또는 기간(기본 최근 24시간)"""
    frm, to = period(db, frm, to)
    return db.all("alarms.state_logs", shift_id=shift_id, equipment_id=equipment_id, pending_only=pending_only,
                  **{"from": frm, "to": to})


class DowntimeIn(BaseModel):
    reason_code: str | None = None     # 입력할 사유 (확정 때는 비우면 입력된 사유 그대로)
    confirm: bool = False              # true = 반장 확정 (R-21)


@router.patch("/downtimes/{state_log_id}")
def downtime_patch(state_log_id: int, body: DowntimeIn,
                   actor: Actor = Depends(require_any(("DOWNTIME_REASON", "INPUT"), ("DOWNTIME_REASON", "CONFIRM"))),
                   db: Db = Depends(get_db)):
    """정지 사유 입력 (OPR·MNT) / 확정 (SUP) — LINE-08, R-21. 바뀐 구간을 돌려준다"""
    action = "CONFIRM" if body.confirm else "INPUT"
    if not permissions(db).allows(actor.role, "DOWNTIME_REASON", action):
        raise AppError(403, "FORBIDDEN", f"{actor.role} 역할은 정지 사유 {'확정' if body.confirm else '입력'} 권한이 없음")
    if body.confirm:
        changed(db.exec("alarms.reason_confirm", state_log_id=state_log_id, reason_code=body.reason_code, actor=actor.user_id),
                "정지 사유 확정")
    else:
        if not body.reason_code:
            raise AppError(422, "VALIDATION", "reason_code 필요")
        changed(db.exec("alarms.reason_input", state_log_id=state_log_id, reason_code=body.reason_code, actor=actor.user_id),
                "정지 사유 입력")
    return db.one("alarms.state_log_get", state_log_id=state_log_id)
