"""알림·브리핑·알림 규칙 (AST-01·02, 6.35·6.36·6.43 — API명세서 NTF-01~04, AST-01, SET-01).
알릴지 말지·중요도·받는 사람은 규칙(DB)이 정한다 (R-38). 비서는 문장만 바꿀 수 있다 (/api/assistant/notifications/...).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, require
from .common import changed, must

router = APIRouter(prefix="/api", tags=["알림"])

BUCKETS = ("SAFETY", "URGENT", "PRODUCTION", "CAUTION", "INFO")
RANK_BUCKET = {"R0": "SAFETY", "R0_1": "CAUTION", "R1": "URGENT", "R2": "PRODUCTION", "R3": "CAUTION", "R4": "INFO"}
# 작업자 요약형에 남기는 줄 (FR-AST-01-07): ① 잠금·표지 ③ 담당 공정의 처리 안 된 긴급·주의 알람 ④ 담당 공정 공구 수명 90%
OPERATOR_RULES = {"ALARM_STOP", "ALARM_WARN", "TOOL_LIFE_90"}


def counts(rows: list[dict], bucket_key: str = "count_bucket") -> dict:
    """머리 "전체 N건 (안전 a · 긴급 b · 생산 c · 주의 d · 참고 e)" — N = 줄 수 (FR-AST-COM-21, 0-1은 주의)"""
    out = {b.lower(): sum(1 for r in rows if r[bucket_key] == b) for b in BUCKETS}
    return {"total": len(rows), **out}


@router.get("/notifications")
def mine(status: str = Query("open", pattern="^(open|processed|all)$"), sort: str = Query("recent", pattern="^(recent|rank)$"),
         importance: str | None = Query(None, pattern="^(URGENT|CAUTION|INFO)$"), equipment_id: str | None = None,
         kind: str | None = Query(None, pattern="^(fault|doc)$", description="칸: fault 고장·확인 알림 / doc 문서 알림 (비우면 둘 다)"),
         limit: int = Query(100, le=500), actor: Actor = Depends(require("NOTIFICATION", "VIEW")), db: Db = Depends(get_db)):
    """알림 목록 (API-NTF-01, 이브 사이드바 알림 탭): 자기 역할분, MGR은 전부 (R-76). 카드마다 중요도·보고 순위·×N 묶음·폭주·
    24시간 넘음·관련 정보·처리할 역할·전달 방식(delivery_kind: POPUP 긴급 팝업 / BUBBLE 이브 말풍선 / LIST 목록 — 2026-10-13)·
    문서 알림이면 열 문서(doc_type·doc_key). 머리에 전체 N건·순위별 건수 (처리 안 된 것)와
    이브 아이콘 숫자(badge = 처리 안 된 고장·확인 + 문서)"""
    items = db.all("notifications.mine", user_id=actor.user_id, all_visible=actor.role == "MGR", status=status, sort=sort,
                   importance=importance, equipment_id=equipment_id, kind=kind, limit=limit)
    open_items = [dict(i, count_bucket=RANK_BUCKET.get(i["report_rank"], "INFO")) for i in items
                  if str(i["is_processed"]).lower() in ("false", "f")]
    badge = {"fault": sum(1 for i in open_items if i["delivery_kind"] != "BUBBLE"),
             "doc": sum(1 for i in open_items if i["delivery_kind"] == "BUBBLE")}
    return {"counts": counts(open_items), "badge": {**badge, "total": badge["fault"] + badge["doc"]}, "items": items}


def _received(db: Db, actor: Actor, notification_id: int) -> bool:
    return db.scalar("notifications.is_recipient", notification_id=notification_id, user_id=actor.user_id) in (True, "t")


@router.get("/notifications/{notification_id}")
def get(notification_id: int, actor: Actor = Depends(require("NOTIFICATION", "VIEW")), db: Db = Depends(get_db)):
    """알림 1건 — 받은 사람만, MGR은 전부 (R-76)"""
    n = must(db.one("notifications.get", notification_id=notification_id), "알림")
    if actor.role != "MGR" and not _received(db, actor, notification_id):
        raise AppError(403, "FORBIDDEN", "이 알림을 받은 사람만 볼 수 있음", {"reason": "NOT_RECIPIENT"})
    return n


@router.post("/notifications/{notification_id}/read")
def read(notification_id: int, actor: Actor = Depends(require("NOTIFICATION", "VIEW")), db: Db = Depends(get_db)):
    """읽음 (NTF-02, 처리 아님 — 받는 사람 본인). 문서 수정 알림만은 받은 사람이 열면 처리된다 (6.36).
    MGR은 받지 않은 알림을 열어도 오류가 아니다 (전부 보기 — 읽음 표시만 없음)"""
    if actor.role != "MGR" and not _received(db, actor, notification_id):
        raise AppError(403, "FORBIDDEN", "이 알림을 받은 사람만 읽음 표시함", {"reason": "NOT_RECIPIENT"})
    return db.one("notifications.read", notification_id=notification_id, user_id=actor.user_id)


class ResolveIn(BaseModel):
    action_plan: str | None = Field(None, description="반복 알람(1단계)은 조치 계획 한 줄 필수 (6.36)")
    memo: str | None = None


@router.post("/notifications/{notification_id}/resolve")
def resolve(notification_id: int, body: ResolveIn, actor: Actor = Depends(require("NOTIFICATION", "VIEW")),
            db: Db = Depends(get_db)):
    """처리 (NTF-03). 처리할 수 있는 역할은 규칙의 processor_roles (DB가 확인, 자동 처리 규칙은 INVALID_STATE).
    처리 시각·사람을 돌려준다"""
    n = must(db.one("notifications.get", notification_id=notification_id), "알림")
    if n["rule_code"] == "REPEAT_ALARM" and not (body.action_plan or "").strip():
        raise AppError(422, "VALIDATION", "반복 알람은 조치 계획(action_plan) 한 줄이 필요함")
    memo = body.action_plan if n["rule_code"] == "REPEAT_ALARM" else (body.memo or body.action_plan)
    db.scalar("notifications.process", notification_id=notification_id, actor=actor.user_id, memo=memo)
    done = db.one("notifications.get", notification_id=notification_id)
    return {"notification_id": notification_id, "processed_at": done["processed_at"], "processed_by": done["processed_by"]}


@router.post("/notifications/{notification_id}/ack")
def ack(notification_id: int, actor: Actor = Depends(require("NOTIFICATION", "VIEW")), db: Db = Depends(get_db)):
    """긴급 팝업 확인 (API-NTF-04): 소리 끔·읽음 표시. 처리는 아니다 — 긴급 팝업은 로그인한 전원이 받고(2026-10-13),
    처리는 그 설비 OPR·MNT의 작업기록서·간이 작업기록 확정 때 자동 (받는 사람 본인만)"""
    if not db.exec("notifications.ack", notification_id=notification_id, user_id=actor.user_id):
        raise AppError(403, "FORBIDDEN", "이 알림을 받은 사람만 확인할 수 있음")
    return {"ok": True}


# ---------------- 교대 시작 브리핑 (AST-01) ----------------
def _members(line: dict) -> list[dict]:
    m = line.get("members") or []
    return json.loads(m) if isinstance(m, str) else m


def _operator_line(line: dict, processes: tuple[str, ...] | None) -> bool:
    """작업자 요약형 줄: 잠금·표지 + 담당 공정(두 칸) 설비의 정지·주의 알람·공구 수명"""
    if line["report_rank"] == "R0":
        return True
    if processes and line.get("process_code") not in processes:
        return False
    return any(m.get("item_kind") == "DOWN" or m.get("rule_code") in OPERATOR_RULES for m in _members(line))


@router.get("/assistant/briefing")
def briefing(shift_id: str | None = None, view: str | None = Query(None, pattern="^(full|operator)$"),
             actor: Actor = Depends(require("BRIEFING", "VIEW")), db: Db = Depends(get_db)):
    """교대 시작 브리핑 재료 (AST-01, FR-AST-01-02~07, FR-AST-COM-21). 비서는 이 순서대로 문장만 쓴다.
      · lines: 보고 순위 줄 전부 (6.43 R0 안전 → R4 참고). 같은 설비·같은 원인은 한 줄(1건), 개수를 자르지 않음
      · prev_shift: 지난 교대 양품·손실(추정)·잠정 여부 / this_shift: 총 목표(목표 + 이월)·작업지시·로트·예방 정비
    전형(full) S·M·G / 요약형(operator) O — OPR(권한 범위 SUMMARY)은 늘 요약형: 잠금·표지, 담당 공정 긴급·주의 알람과
    공구 수명, 지난 교대 양품, 총 목표"""
    summary = actor.scope == "SUMMARY" or view == "operator"
    processes = actor.user.processes if summary else ()
    lines = db.all("notifications.report_lines")
    prev = db.one("notifications.briefing_prev_shift", shift_id=shift_id)
    this = db.one("notifications.briefing_this_shift", shift_id=shift_id,
                  process_codes=",".join(processes) if processes else None)
    if summary:
        lines = [ln for ln in lines if _operator_line(ln, processes)]
        prev = prev and {k: prev[k] for k in ("shift_id", "good_qty", "is_provisional")}
        this = this and {k: this[k] for k in ("shift_id", "target_qty", "carry_over_qty", "total_target_qty",
                                              "carry_over_is_provisional", "pm_due")}
    return {"view": "operator" if summary else "full", "counts": counts(lines), "lines": lines,
            "prev_shift": prev, "this_shift": this}


# ---------------- 알림 규칙 설정 (SET-01) ----------------
@router.get("/settings/notification-rules")
def rules(_: Actor = Depends(require("SETTINGS", "VIEW")), db: Db = Depends(get_db)):
    """알림 규칙 목록 (SET-01, 6.36)"""
    return db.all("notifications.rules")


class RuleIn(BaseModel):
    rule_code: str
    is_enabled: bool | None = None
    condition_text: str | None = None


@router.patch("/settings/notification-rules")
def rule_update(body: RuleIn, actor: Actor = Depends(require("SETTINGS", "SETTING")), db: Db = Depends(get_db)):
    """알림 규칙 켜기·끄기·설명 (SET-01, MGR — DB 트리거가 다시 확인). 기준 숫자 바꾸기는 [선택 필요: 기술 회의]"""
    return changed(db.exec("notifications.rule_update", rule_code=body.rule_code, is_enabled=body.is_enabled,
                           condition_text=body.condition_text, actor=actor.user_id), "알림 규칙")
