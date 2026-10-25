"""3D 라인 뷰·현장 보기·다시 보기 (PRD-01·06, SCR-04·05·06·26, API명세서 LINE-01·02·06).
현장 보기는 같은 데이터를 작업자 화면으로 보여준다."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from ..config import get_settings
from ..db import Db, engine, get_db
from ..errors import AppError
from ..security import Actor, User, permissions, permissions_side, require, require_any, token_user
from ..services import sim_link
from .common import must, period

router = APIRouter(prefix="/api", tags=["라인"])
VIEW_PAIRS = (("LINE_VIEW", "VIEW"), ("FIELD_VIEW", "VIEW"))
VIEW = require_any(*VIEW_PAIRS)


@router.get("/line/layout")
def layout(_: Actor = Depends(VIEW), db: Db = Depends(get_db)):
    """공장·설비 실제 크기 배치 (LINE-01) — 바닥·통로·재공 자리·설비 외형·부품 도형. 3D 장면을 처음 그릴 때 한 번"""
    return {"plant": db.one("line.plant"), "objects": db.all("line.objects"), "equipment": db.all("line.equipment_layout")}


# ---- 트윈 함께 쓰기 (2026-10-24, 여러 명 접속) ----
# 화면은 사람마다 1초에 한 번 /api/line/twin?full=true를 부른다 (쿼리 19개, 로컬 DB에서도 약 0.3초). 내용은 역할·사람과 관계없이 같으므로
# 계산한 결과를 twin_cache_seconds(기본 1초) 동안 두고 같이 쓴다 → 접속자가 늘어도 DB는 1초에 한 번만 읽는다.
# 같은 순간에 여러 요청이 오면 한 요청만 계산하고 나머지는 그 결과를 기다린다(잠금).
# 계산 중에 온 요청은 기다리지 않고 바로 앞 값을 받는다. 앞 값으로 답하는 요청은 DB 연결을 아예 잡지 않는다(토큰만 확인).
_twin_cache: dict[tuple, tuple[float, dict]] = {}
_twin_lock = threading.Lock()


def _sim_control(user: User) -> bool:
    allowed = get_settings().sim_control_users
    return not allowed or user.user_id in allowed


def _no_db() -> None:
    return None


def _twin_view(user: User = Depends(token_user), db: Db | None = Depends(_no_db)) -> Actor:
    """VIEW(LINE_VIEW 또는 FIELD_VIEW)와 같은 권한 확인을 DB 연결 없이 (토큰 역할 + 60초 기억한 권한표).
    시험(tests/test_routers_db.py)은 db를 넘겨 그 DB의 권한표로 본다"""
    table = permissions(db) if db is not None else permissions_side()
    for target, action in VIEW_PAIRS:
        scope = table.scope(user.role_code, target, action)
        if scope is not None:
            return Actor(user, scope)
    raise AppError(403, "FORBIDDEN", f"{user.role_code} 역할은 권한이 없음")


_twin_view.permission = list(VIEW_PAIRS)        # 권한표 시험·API 문서(tests/role_matrix_util.py, tools/gen_api_doc.py)가 읽는 표시


@router.get("/line/twin")
def twin(shift_id: str | None = None, full: bool = Query(False, description="화면 전체 트윈 (2026-10-23): 공구·지표·작업지시·알람·센서·정지 분까지 한 번에"),
         actor: Actor = Depends(_twin_view), db: Db | None = Depends(_no_db)):
    """twin_cache_seconds 안의 같은 요청(shift_id·full)은 한 번 계산한 결과를 같이 쓴다. sim_control = 이 사용자가 시연 조작을 할 수 있는지.
    DB 연결은 새로 계산할 때만 잡는다 — 접속자가 많아도 연결 줄(Supabase 무료 15개)과 처리 스레드가 막히지 않게 (2026-10-24 여러 명 시험)"""
    def compute() -> dict:
        if db is not None:
            return _twin(shift_id, full, db)
        with engine().begin() as conn:
            return _twin(shift_id, full, Db(conn))

    ttl = float(get_settings().twin_cache_seconds or 0)
    out = _cached_twin((shift_id, full), ttl, compute) if ttl > 0 else compute()
    return {**out, "sim_control": _sim_control(actor.user)} if full else out


_twin_busy: dict[tuple, threading.Event] = {}


def _cached_twin(key: tuple, ttl: float, compute) -> dict:
    """1) ttl 안이면 그대로 2) 지났으면 한 요청만 새로 계산 — 그동안 다른 요청은 바로 앞 값(최대 ttl×5 지난 것)을 받고 연결을 바로 놓는다
    3) 앞 값이 없거나 너무 오래됐으면(서버를 막 켰을 때) 계산이 끝날 때까지 기다린다"""
    while True:
        with _twin_lock:
            hit = _twin_cache.get(key)
            age = time.monotonic() - hit[0] if hit else None
            if hit and age < ttl:
                return hit[1]
            busy = _twin_busy.get(key)
            if busy is None:
                busy = _twin_busy[key] = threading.Event()
                break                                   # 내가 계산한다
            if hit and age < ttl * 5:
                return hit[1]                           # 누가 계산 중 — 앞 값을 준다
        busy.wait(30)                                   # 앞 값이 없으면 계산이 끝나길 기다렸다가 다시 본다
    try:
        out = compute()
        with _twin_lock:
            _twin_cache[key] = (time.monotonic(), out)
        return out
    finally:
        with _twin_lock:
            _twin_busy.pop(key, None)
        busy.set()


def _twin(shift_id: str | None, full: bool, db: Db) -> dict:
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
