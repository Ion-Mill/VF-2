"""정비: 작업지시서·작업기록서·간이 작업기록·예방 정비 (MNT-03·04·05, 6.13·6.15 — API명세서 MNT-02~12, PM-01·02).

상태 바꾸기의 "누가"는 서버 권한(role_permission) + DB 트리거가 두 번 확인한다 (R-51: 승인·확정은 사람만).
작업기록서 확정 때 잠금·표지 9단계가 모두 체크돼야 한다 (R-32, fn_confirm_work_record).
문서를 고치는 요청은 version을 보낸다 — 다르면 CONFLICT_VERSION (API명세서 1장).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..assistant import client
from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, permissions, require, require_any
from ..services import documents, records
from .common import changed, check_version, must

router = APIRouter(prefix="/api/maint", tags=["정비"])


# ---------------- 작업지시서 (MNT-02~08) ----------------
@router.get("/work-orders")
def wo_list(status: str | None = None, mine: bool = False, limit: int = Query(100, le=500),
            actor: Actor = Depends(require("WORK_ORDER", "VIEW")), db: Db = Depends(get_db)):
    """작업지시서 목록 (MNT-02). mine = 내가 담당인 것만"""
    return db.all("maintenance.wo_list", status=status, assignee=actor.user_id if mine else None, limit=limit)


@router.get("/work-orders/{wo_no}")
def wo_get(wo_no: str, actor: Actor = Depends(require("WORK_ORDER", "VIEW")), db: Db = Depends(get_db)):
    """작업지시서 (MNT-03): 계기·자동 칸·제목·증상·작업 순서·안전 블록 표시·예상 부품·담당·상태·승인 대기 시간.
    담당 MNT가 열면 "작업지시서 배정" 알림(WO_ASSIGNED)이 처리된다 (6.36 처리 표, 2026-10-13)"""
    wo = must(db.one("maintenance.wo_get", wo_no=wo_no), "작업지시서")
    if wo.get("assignee_user_id") == actor.user_id:
        db.scalar("maintenance.wo_assigned_seen", wo_no=wo_no, actor=actor.user_id)
    wo["steps"] = db.all("maintenance.wo_steps", wo_no=wo_no)
    wo["parts"] = db.all("maintenance.wo_parts", wo_no=wo_no)
    return wo


class StepIn(BaseModel):
    step_text: str
    source_section: str | None = None


class PartIn(BaseModel):
    item_no: str
    qty: Decimal


class WoDraftIn(BaseModel):
    equipment_id: str
    title: str
    symptom: str
    alarm_event_id: int | None = None
    trigger_notification_id: int | None = None
    pm_record_id: int | None = None
    lot_no: str | None = None
    steps: list[StepIn] = []
    parts: list[PartIn] = []


@router.post("/work-orders")
def wo_create(body: WoDraftIn, actor: Actor = Depends(require("WORK_ORDER", "CREATE")), db: Db = Depends(get_db)):
    """보전 담당자가 직접 만들기 → 수정 중(v0 = 사람). AI비서 초안과 같은 DB 함수 (같은 알람·2단계가 겹치면 기존 것에 더함, R-71)"""
    wo_no = db.scalar("maintenance.wo_create_draft", equipment_id=body.equipment_id, title=body.title, symptom=body.symptom,
                      alarm_event_id=body.alarm_event_id, trigger_notification_id=body.trigger_notification_id,
                      pm_record_id=body.pm_record_id, lot_no=body.lot_no, author=actor.user_id,
                      steps=[s.model_dump() for s in body.steps], parts=[p.model_dump() for p in body.parts])
    return {"wo_no": wo_no}


class EditIn(BaseModel):
    version: int                    # 지금 버전 (다르면 CONFLICT_VERSION)
    changes: dict
    reason: str | None = None       # 확정(승인)된 문서를 고칠 때 필수 (R-35)


@router.patch("/work-orders/{wo_no}")
def wo_edit(wo_no: str, body: EditIn, actor: Actor = Depends(require("WORK_ORDER", "EDIT")), db: Db = Depends(get_db)):
    """내용 수정 = 새 버전 (MNT-04, AI비서 초안 → 수정 중)"""
    return {"version_no": documents.edit_work_order(db, wo_no, actor.user_id, body.changes, body.reason, body.version)}


class AssignIn(BaseModel):
    mnt_user_id: str


@router.post("/work-orders/{wo_no}/assign")
def wo_assign(wo_no: str, body: AssignIn, _: Actor = Depends(require("WORK_ORDER", "ASSIGN")), db: Db = Depends(get_db)):
    """담당 지정 (MNT-05, SUP — 승인 전 필수)"""
    return changed(db.exec("maintenance.wo_assign", wo_no=wo_no, assignee=body.mnt_user_id), "담당자 지정")


class VersionIn(BaseModel):
    version: int


@router.post("/work-orders/{wo_no}/approve")
def wo_approve(wo_no: str, body: VersionIn, actor: Actor = Depends(require("WORK_ORDER", "APPROVE")),
               db: Db = Depends(get_db)):
    """승인 (MNT-06, 반장만). 관리자 대리 승인(범위 PROXY)은 거절.
    담당 없이·AI비서 초안 그대로는 INVALID_STATE (사람이 열어 수정 중이 되어야 함, 6.13).
    조회 칸 approved_as_proxy 는 그대로 두고, 새 승인 응답의 proxy 는 항상 거짓."""
    if actor.role != "SUP" or actor.scope == "PROXY":
        raise AppError(403, "FORBIDDEN", "작업지시서 승인은 반장만 함")
    check_version(db, "WORK_ORDER", wo_no, body.version)
    changed(db.exec("maintenance.wo_approve", wo_no=wo_no, actor=actor.user_id), "작업지시서 승인")
    return {"status": "APPROVED", "proxy": False}


@router.post("/work-orders/{wo_no}/start")
def wo_start(wo_no: str, actor: Actor = Depends(require("WORK_ORDER", "EDIT")), db: Db = Depends(get_db)):
    """작업 시작 (MNT-07, 담당 MNT만): 승인됨 → 진행 중. 승인 전이면 INVALID_STATE (6.13), 담당이 아니면 FORBIDDEN"""
    wo = must(db.one("maintenance.wo_get", wo_no=wo_no), "작업지시서")
    if wo["assignee_user_id"] != actor.user_id:
        raise AppError(403, "FORBIDDEN", f"작업 시작은 담당 보전 담당자({wo['assignee_user_id'] or '미지정'})만 함",
                       {"reason": "NOT_ASSIGNEE"})
    changed(db.exec("maintenance.wo_start", wo_no=wo_no), "작업 시작")
    return {"status": "IN_PROGRESS"}


class CancelIn(BaseModel):
    reason: str


@router.post("/work-orders/{wo_no}/cancel")
def wo_cancel(wo_no: str, body: CancelIn, actor: Actor = Depends(require("WORK_ORDER", "CANCEL"))):
    """취소 API는 주소를 남긴다. 관리자 취소를 뺐고 반장에게 새로 주지 않아 누가 불러도 거절한다."""
    raise AppError(403, "FORBIDDEN", f"{actor.role} 역할은 작업지시서 취소 권한이 없음",
                   {"wo_no": wo_no, "reason": "NO_CANCEL"})


# ---------------- 작업기록서 (정식 FULL, MNT-09~11) / 간이 작업기록 (SIMPLE, MNT-12) ----------------
WR_VIEW = require_any(("WORK_RECORD", "VIEW"), ("WORK_RECORD_SIMPLE", "VIEW"))
# 첫 관문: 정식·간이 중 하나라도 그 행동 권한이 있어야 함 (SUP·MGR은 여기서 403). 기록 종류별 확인은 _record_perm이 한 번 더
WR_EDIT = require_any(("WORK_RECORD", "EDIT"), ("WORK_RECORD_SIMPLE", "EDIT"))
WR_CONFIRM = require_any(("WORK_RECORD", "CONFIRM"), ("WORK_RECORD_SIMPLE", "CONFIRM"))


def _record_perm(db: Db, actor: Actor, record_no: str, action: str) -> dict:
    """정식 기록은 WORK_RECORD, 간이 기록은 WORK_RECORD_SIMPLE 권한으로 본다"""
    rec = must(db.one("maintenance.wr_get", record_no=record_no), "작업기록")
    target = "WORK_RECORD" if rec["record_type"] == "FULL" else "WORK_RECORD_SIMPLE"
    if not permissions(db).allows(actor.role, target, action):
        raise AppError(403, "FORBIDDEN", f"{actor.role} 역할은 {target}·{action} 권한이 없음")
    return rec


@router.get("/work-records")
def wr_list(record_type: str | None = None, status: str | None = None, limit: int = Query(100, le=500),
            equipment_id: str | None = None, alarm_code: str | None = None,
            actor: Actor = Depends(WR_VIEW), db: Db = Depends(get_db)):
    """작업기록 목록 (OPR은 간이 기록만). 설비·알람 번호로 거르기 (같은 사례 찾기 — 2026-10-20)"""
    if not permissions(db).allows(actor.role, "WORK_RECORD", "VIEW"):
        record_type = "SIMPLE"           # OPR은 간이 기록만 (13.1)
    return db.all("maintenance.wr_list", record_type=record_type, status=status, limit=limit,
                  equipment_id=equipment_id, alarm_code=alarm_code)


@router.get("/work-records/{record_no}")
def wr_get(record_no: str, actor: Actor = Depends(WR_VIEW), db: Db = Depends(get_db)):
    """작업기록서 조회 (MNT-09): 칸 전부 + 체크 항목(잠금·표지 9칸·작업 순서) + 쓴 부품"""
    rec = _record_perm(db, actor, record_no, "VIEW")
    rec["checks"] = db.all("maintenance.wr_checks", record_no=record_no)
    rec["parts"] = db.all("maintenance.wr_parts", record_no=record_no)
    return rec


class WrFullIn(BaseModel):
    wo_no: str
    cause: str | None = None
    action: str | None = None
    worker_memo: str | None = None
    start_at: datetime | None = None


@router.post("/work-records")
def wr_create_full(body: WrFullIn, actor: Actor = Depends(require("WORK_RECORD", "CREATE")), db: Db = Depends(get_db)):
    """정식 작업기록서 만들기 (작업지시서 1건 = 1건). 잠금·표지 9단계 + 작업 순서 체크칸이 함께 생긴다"""
    return records.create_work_record_full(db, body.wo_no, "HUMAN", actor.user_id, body.cause, body.action,
                                           body.worker_memo, body.start_at)


class CheckSet(BaseModel):
    check_seq: int
    is_checked: bool = True


class WrPartIn(BaseModel):
    item_no: str
    qty: Decimal


class WrEditIn(BaseModel):
    version: int
    changes: dict = {}
    reason: str | None = None            # 확정 뒤 수정은 필수 (반장 확인이 풀린다)
    checks: list[CheckSet] = []          # 잠금·표지 9칸·작업 순서 체크
    parts: list[WrPartIn] = []           # 사용 부품 (확정할 때 재고에서 빠진다)


@router.patch("/work-records/{record_no}")
def wr_edit(record_no: str, body: WrEditIn, actor: Actor = Depends(WR_EDIT), db: Db = Depends(get_db)):
    """작업기록서 수정 (MNT-09): 고친 칸(새 버전)·체크·사용 부품을 한 번에. 칸 전부를 돌려준다"""
    _record_perm(db, actor, record_no, "EDIT")
    check_version(db, "WORK_RECORD", record_no, body.version)
    if not (body.changes or body.checks or body.parts):
        raise AppError(422, "VALIDATION", "바뀐 칸이 없음", {"reason": "NO_CHANGE"})
    if body.changes:
        documents.edit_work_record(db, record_no, actor.user_id, body.changes, body.reason, body.version)
    for c in body.checks:
        changed(db.exec("maintenance.wr_check_item", record_no=record_no, check_seq=c.check_seq, is_checked=c.is_checked,
                        actor=actor.user_id), "체크")
    for p in body.parts:
        db.exec("maintenance.wr_set_part", record_no=record_no, item_no=p.item_no, qty=p.qty, proposed_by_kind="HUMAN")
    return wr_get(record_no, actor, db)


class CheckIn(BaseModel):
    is_checked: bool = True


@router.post("/work-records/{record_no}/checks/{check_seq}")
def wr_check(record_no: str, check_seq: int, body: CheckIn, actor: Actor = Depends(WR_EDIT), db: Db = Depends(get_db)):
    """체크 1칸 (잠금·표지 단계·작업 순서 — 체크한 사람·시각이 남는다)"""
    _record_perm(db, actor, record_no, "EDIT")
    return changed(db.exec("maintenance.wr_check_item", record_no=record_no, check_seq=check_seq, is_checked=body.is_checked,
                           actor=actor.user_id), "체크")


@router.put("/work-records/{record_no}/parts")
def wr_part(record_no: str, body: WrPartIn, actor: Actor = Depends(WR_EDIT), db: Db = Depends(get_db)):
    """쓴 부품 1줄 (확정할 때 재고에서 빠진다)"""
    _record_perm(db, actor, record_no, "EDIT")
    db.exec("maintenance.wr_set_part", record_no=record_no, item_no=body.item_no, qty=body.qty, proposed_by_kind="HUMAN")
    return {"ok": True}


class AssistIn(BaseModel):
    memo: str


@router.post("/work-records/{record_no}/assist")
def wr_assist(record_no: str, body: AssistIn, actor: Actor = Depends(require("WORK_RECORD", "EDIT")),
              db: Db = Depends(get_db)):
    """메모를 비서로 정리 (MNT-10): AI 비서 서비스가 원인·조치 칸 AI비서 초안을 돌려준다 (저장하지 않음 — 보전 담당자가
    PATCH로 넣는다). 비서가 없거나 응답이 틀리면 ASSISTANT_UNAVAILABLE"""
    rec = _record_perm(db, actor, record_no, "EDIT")
    # 알람 번호(근거 문서 찾기)·재고 품목(메모에 나온 사용 부품 고르기 — 비서는 지어내지 않고 이 목록에서만, 2026-10-20)
    out = client.call("/work-record-assist", {"record_no": record_no, "equipment_id": rec["equipment_id"],
                                              "memo": body.memo, "user_id": actor.user_id,
                                              "alarm_code": db.scalar("maintenance.wr_alarm_code", record_no=record_no),
                                              "items": db.all("maintenance.assist_items")})
    return {"record_no": record_no, "author_kind": "AI",
            "cause": out.get("cause"), "action": out.get("action"), "sources": out.get("sources") or [],
            "parts": out.get("parts") or []}          # 사용 부품 제안 [{item_no, qty}] (FR-MNT-05-02, 2026-10-20 — 전에는 버렸다)


@router.post("/work-records/{record_no}/confirm")
def wr_confirm(record_no: str, body: VersionIn, actor: Actor = Depends(WR_CONFIRM), db: Db = Depends(get_db)):
    """확정 (MNT-11): 작업지시서 완료·사용 부품 재고 차감·알람 알림 자동 처리·MTTR 다시 계산 (정식 = MNT).
    잠금·표지 9칸이 덜 차면 INVALID_STATE (R-32)"""
    _record_perm(db, actor, record_no, "CONFIRM")
    check_version(db, "WORK_RECORD", record_no, body.version)
    db.scalar("maintenance.wr_confirm", record_no=record_no, actor=actor.user_id)
    return {"record_no": record_no, "status": "CONFIRMED"}


@router.post("/work-records/{record_no}/check")
def wr_sup_check(record_no: str, actor: Actor = Depends(require("WORK_RECORD", "CHECK")), db: Db = Depends(get_db)):
    """반장 확인 표시 (정식 기록, 확정 뒤)"""
    return changed(db.exec("maintenance.wr_sup_check", record_no=record_no, actor=actor.user_id), "반장 확인")


class QuickIn(BaseModel):
    equipment_id: str
    action: str
    alarm_event_id: int | None = None
    cause_check_notification_id: int | None = None   # 다른 공정 원인 점검 요청 (R-70)
    lot_no: str | None = None
    worker_memo: str | None = None
    start_at: datetime | None = None
    safety_block_required: bool = False   # 알람 잠금 수준이 FULL·TWO_POINT면 DB가 참으로 정함 (R-32·33)


@router.post("/quick-records")
def quick_create(body: QuickIn, actor: Actor = Depends(require("WORK_RECORD_SIMPLE", "CREATE")), db: Db = Depends(get_db)):
    """간이 작업기록 저장 (MNT-12): 주의 등급 알람·다른 공정 알람·원인 점검 요청. AI비서 초안 없음.
    체크 9칸은 PATCH /api/maint/work-records/{id} 로"""
    return {"record_no": records.create_work_record_simple(db, actor.user_id, **body.model_dump())}


class QuickConfirmIn(BaseModel):
    version: int | None = None


@router.post("/quick-records/{record_no}/confirm")
def quick_confirm(record_no: str, body: QuickConfirmIn, actor: Actor = Depends(require("WORK_RECORD_SIMPLE", "CONFIRM")),
                  db: Db = Depends(get_db)):
    """간이 작업기록 확정 (MNT-12): 주의 등급은 OPR·MNT, 다른 공정 정지 등급·원인 점검은 MNT만 (DB가 다시 확인)"""
    rec = _record_perm(db, actor, record_no, "CONFIRM")
    if rec["record_type"] != "SIMPLE":
        raise AppError(409, "INVALID_STATE", "정식 작업기록서는 /api/maint/work-records/{id}/confirm 으로 확정")
    check_version(db, "WORK_RECORD", record_no, body.version)
    db.scalar("maintenance.wr_confirm", record_no=record_no, actor=actor.user_id)
    return {"record_no": record_no, "status": "CONFIRMED"}


# ---------------- 예방 정비 (PM-01·02) ----------------
@router.get("/pm-schedule")
def pm_schedule(equipment_id: str | None = None, frm: date | None = Query(None, alias="from"), to: date | None = None,
                _: Actor = Depends(require("PM_SCHEDULE", "VIEW")), db: Db = Depends(get_db)):
    """예방 정비 일정 (PM-01): 항목·주기·다음 기한·넘긴 날 수·잠금·표지 수준, 제때 실시율(기간, 기본 최근 30일 — 목표 90%)"""
    return {"items": db.all("maintenance.pm_schedule", equipment_id=equipment_id),
            "on_time": db.all("maintenance.pm_on_time", equipment_id=equipment_id, **{"from": frm, "to": to})}


class PmRecordIn(BaseModel):
    pm_task_id: str
    due_date: date
    result: str
    done_by: str | None = None
    done_at: datetime | None = None
    measured_value: Decimal | None = None
    measured_unit: str | None = None
    memo: str | None = None


@router.post("/pm-records")
def pm_record_create(body: PmRecordIn, actor: Actor = Depends(require("PM_RECORD", "CREATE")), db: Db = Depends(get_db)):
    """예방 정비 실시 기록 (PM-02) 저장 (v0). 확정하면 소모품 재고 차감 (…/confirm)"""
    return {"pm_record_id": records.create_pm_record(db, actor.user_id, **body.model_dump())}


class PmStartIn(BaseModel):
    due_date: date | None = None        # 비우면 그 항목의 다음 기한


@router.post("/pm-tasks/{pm_task_id}/start")
def pm_start(pm_task_id: str, body: PmStartIn | None = None, actor: Actor = Depends(require("PM_RECORD", "CREATE")),
             db: Db = Depends(get_db)):
    """[정비 시작] (FR-MNT-04-10, API-PM-02 — 2026-10-20): 실시 기록(수정 중)을 만들고 그 설비에 MAINT 구간을 연다.
    설비를 켜고 끄는 명령이 아니라 기록이다. 이미 정비 중·고장 정지 중이면 INVALID_STATE (DB가 막음)"""
    rid = db.scalar("maintenance.pm_start", pm_task_id=pm_task_id, actor=actor.user_id, due_date=body.due_date if body else None)
    return {"pm_record_id": rid, "maint": db.one("maintenance.pm_open_maint", pm_record_id=rid)}


class PmEndIn(BaseModel):
    result: str = "NORMAL"
    measured_value: Decimal | None = None
    measured_unit: str | None = None
    memo: str | None = None


@router.post("/pm-records/{pm_record_id}/end")
def pm_end(pm_record_id: int, body: PmEndIn, actor: Actor = Depends(require("PM_RECORD", "CREATE")), db: Db = Depends(get_db)):
    """[정비 끝 · 실시 기록] (FR-MNT-04-10): MAINT 구간을 닫고 실시 시각 = 끝난 시각, 결과를 적는다 (v0). 확정은 …/confirm"""
    db.scalar("maintenance.pm_end", pm_record_id=pm_record_id, actor=actor.user_id, result=body.result,
              measured_value=body.measured_value, measured_unit=body.measured_unit, memo=body.memo)
    db.scalar("documents.save_revision", doc_type="PM_RECORD", doc_key=str(pm_record_id), author_kind="HUMAN", author=actor.user_id,
              reason=None, status_after="EDITING", content={"result": body.result, "measured_value": body.measured_value,
                                                            "measured_unit": body.measured_unit, "memo": body.memo}, changes=[])
    return must(db.one("documents.pm_record_get", pm_record_id=pm_record_id), "예방 정비 기록")


@router.get("/pm-records/{pm_record_id}")
def pm_record_get(pm_record_id: int, _: Actor = Depends(require("PM_RECORD", "VIEW")), db: Db = Depends(get_db)):
    """예방 정비 실시 기록 1건"""
    return must(db.one("documents.pm_record_get", pm_record_id=pm_record_id), "예방 정비 기록")


class PmEditIn(BaseModel):
    changes: dict
    reason: str | None = None
    version: int | None = None


@router.patch("/pm-records/{pm_record_id}")
def pm_record_edit(pm_record_id: int, body: PmEditIn, actor: Actor = Depends(require("PM_RECORD", "EDIT")),
                   db: Db = Depends(get_db)):
    """예방 정비 기록 고치기 = 새 버전"""
    return {"version_no": documents.edit_pm_record(db, pm_record_id, actor.user_id, body.changes, body.reason, body.version)}


class PmConfirmIn(BaseModel):
    used_qty: Decimal | None = None     # 기본 소모품을 쓴 양 (재고 차감)


@router.post("/pm-records/{pm_record_id}/confirm")
def pm_record_confirm(pm_record_id: int, body: PmConfirmIn, actor: Actor = Depends(require("PM_RECORD", "CONFIRM")),
                      db: Db = Depends(get_db)):
    """예방 정비 기록 확정 → 소모품 재고 차감·기한 알림 자동 처리"""
    r = db.one("maintenance.pm_record_confirm", pm_record_id=pm_record_id, actor=actor.user_id, used_qty=body.used_qty)
    if not r or not r["confirmed"]:
        raise AppError(409, "INVALID_STATE", "예방 정비 기록: 수정 중인 기록만 확정")
    return r
