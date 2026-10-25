"""3D 라인 뷰·현장 보기·다시 보기 (PRD-01·06, SCR-04·05·06·26, API명세서 LINE-01·02·06).
현장 보기는 같은 데이터를 작업자 화면으로 보여준다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, require, require_any
from ..services import sim_link
from .common import must, period

router = APIRouter(prefix="/api", tags=["라인"])
VIEW = require_any(("LINE_VIEW", "VIEW"), ("FIELD_VIEW", "VIEW"))


@router.get("/line/layout")
def layout(_: Actor = Depends(VIEW), db: Db = Depends(get_db)):
    """공장·설비 실제 크기 배치 (LINE-01) — 바닥·통로·재공 자리·설비 외형·부품 도형. 3D 장면을 처음 그릴 때 한 번"""
    return {"plant": db.one("line.plant"), "objects": db.all("line.objects"), "equipment": db.all("line.equipment_layout")}


@router.get("/line/twin")
def twin(shift_id: str | None = None, full: bool = Query(False, description="화면 전체 트윈 (2026-10-23): 공구·지표·작업지시·알람·센서·정지 분까지 한 번에"),
         _: Actor = Depends(VIEW), db: Db = Depends(get_db)):
    """지금 상태 한 번에 (LINE-02): 설비별 상태·지속 시간·현재 로트·현재 알람, 재공, 병목, 교대 진행(총 목표 = 목표 + 이월,
    실적·예측·손실 합 — 고장 + 속도, 추정), 라인 OEE(지표 카드 처음 값). shift_id를 비우면 지금(또는 가장 최근) 교대.
    바뀌면 /api/stream/events 사건이 오고 화면이 이것을 다시 부른다.
    full=true: 화면이 1초마다 한 번에 받는 나머지 — 시간대별 실적, 설비별 지표·MTTR, 작업지시, 공구 수명, 실시간 구간 알람,
    지금 센서 값, 설비별 멈춘 분·고장 손실, 지금 사유, 오늘 완제품 수, 마지막 측정값, 의심 로트 (화면 → 백엔드 전환 C2)"""
    shift = must(db.one("line.shift_progress", shift_id=shift_id), "교대")
    out = {"now": db.scalar("common.now"), "equipment": db.all("line.equipment_now"), "wip": db.all("line.wip_latest"),
           "bottleneck": db.one("line.bottleneck_now"), "shift": shift,
           "line_oee": db.one("line.line_oee", shift_id=shift["shift_id"])}
    if not full:
        return out
    sid, live_from = shift["shift_id"], db.scalar("line.live_from")
    no_period = {"from": None, "to": None}
    out.update({
        "live_from": live_from,
        "hourly": db.all("line.shift_hourly", shift_id=sid),
        "kpi_equipment": db.all("production.kpi_equipment", shift_id=sid, equipment_id=None, **no_period),
        "reliability": db.all("assistant.reliability", equipment_id=None),
        "orders": db.all("production.orders", shift_id=None, status=None, limit=30, **no_period),
        "tools": db.all("inventory.tools", equipment_id=None),
        "alarms": db.all("alarms.list", equipment_id=None, alarm_code=None, limit=1000, **{"from": live_from, "to": FAR_FUTURE}),
        "sensors": db.all("line.sensor_latest"),
        "stops": db.all("line.shift_equipment_stops", shift_id=sid),
        "reasons": db.all("line.equipment_reason_now"),
        "done_today": db.scalar("line.done_today"),
        "last_measure": db.all("line.last_measure"),
        "suspect_lots": db.all("production.suspect_lots", alarm_event_id=None, lot_no=None, since=live_from),
        "bottleneck_log": db.all("line.bottleneck_since", since=live_from),
        # 시뮬레이터 시계·사건 버튼 상태·회차 (MOM_SIM_URL이 있을 때만 — 없으면 DB 시계만, 사건 버튼 없음)
        "sim": sim_link.call("GET", "sim/clock") if sim_link.enabled() else None,
    })
    return out


FAR_FUTURE = datetime(9999, 1, 1, tzinfo=timezone.utc)


@router.get("/replay")
def replay(frm: datetime | None = Query(None, alias="from"), to: datetime | None = None, equipment_id: str | None = None,
           _: Actor = Depends(require("LINE_VIEW", "VIEW")), db: Db = Depends(get_db)):
    """다시 보기 (LINE-06, PRD-06): 시각별 상태·재공·알람·병목 사건, equipment_id를 주면 그 설비 센서 값
    (평소 1분 평균, 알람 앞뒤 30분은 1초). 한 번에 24시간까지, 센서는 6시간까지"""
    frm, to = period(db, frm, to, default_hours=2)
    if to - frm > timedelta(hours=24):
        raise AppError(422, "VALIDATION", "다시 보기는 24시간까지")
    out = {"from": frm, "to": to, "states": db.all("line.replay_states", **{"from": frm, "to": to}),
           "wip": db.all("line.replay_wip", **{"from": frm, "to": to}),
           "events": db.all("line.replay_events", **{"from": frm, "to": to}), "sensors": [],
           # 2026-10-23 (화면 → 백엔드 전환 C2): 알람 전체 칸·병목 원인·완제품 시각 — 다시 보기 화면이 그대로 그린다
           "alarms": db.all("alarms.list", equipment_id=None, alarm_code=None, limit=1000, **{"from": frm, "to": to}),
           "bottleneck": db.all("line.replay_bottleneck", **{"from": frm, "to": to}),
           "done": db.all("line.replay_done", **{"from": frm, "to": to})}
    if equipment_id:
        if to - frm > timedelta(hours=6):
            raise AppError(422, "VALIDATION", "센서 값은 6시간까지 (equipment_id를 비우거나 기간을 줄인다)")
        out["sensors"] = db.all("line.replay_sensors", equipment_id=equipment_id, **{"from": frm, "to": to})
    return out
