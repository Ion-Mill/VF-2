"""문서 처음 만들기 = 본문 행 + v0 버전 (R-35: 모든 문서는 v0부터 이력이 남는다).

  · 사람이 처음 저장 → 상태 EDITING, v0 author_kind = HUMAN
  · AI비서 초안      → 상태 AI_DRAFT, v0 author_kind = AI (작업지시서·작업기록서만, 6.15·6.13)
간이 작업기록은 AI비서 초안이 없다 (사람이 처음 저장).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db import Db
from ..errors import AppError


def create_work_record_full(db: Db, wo_no: str, author_kind: str, author: str | None, cause: str | None = None,
                            action: str | None = None, worker_memo: str | None = None, start_at=None) -> dict:
    status = "AI_DRAFT" if author_kind == "AI" else "EDITING"
    row = db.one("maintenance.wr_create_full", wo_no=wo_no, cause=cause, action=action, worker_memo=worker_memo,
                 start_at=start_at, status=status)
    if not row:
        raise AppError(404, "NOT_FOUND", f"작업지시서 {wo_no} 없음")
    db.scalar("documents.save_revision", doc_type="WORK_RECORD", doc_key=row["record_no"], author_kind=author_kind,
              author=author, reason=None, status_after=status,
              content={"wo_no": wo_no, "cause": cause, "action": action or "", "worker_memo": worker_memo}, changes=[])
    return row


def create_work_record_simple(db: Db, actor: str, equipment_id: str, action: str, alarm_event_id: int | None = None,
                              cause_check_notification_id: int | None = None, lot_no: str | None = None,
                              worker_memo: str | None = None, start_at=None, safety_block_required: bool = False) -> str:
    row = db.one("maintenance.wr_create_simple", alarm_event_id=alarm_event_id,
                 cause_check_notification_id=cause_check_notification_id, equipment_id=equipment_id, lot_no=lot_no,
                 action=action, worker_memo=worker_memo, start_at=start_at,
                 safety_block_required=safety_block_required)
    record_no = row["record_no"]
    # 잠금·표지 필요 여부는 DB가 알람 잠금 수준으로 정한다 (화면이 False를 보내도 FULL·TWO_POINT 알람이면 참, 2026-10-20)
    if row["safety_block_required"] in (True, "t", "true"):
        db.exec("maintenance.wr_add_loto", record_no=record_no)
    db.scalar("documents.save_revision", doc_type="WORK_RECORD", doc_key=record_no, author_kind="HUMAN", author=actor,
              reason=None, status_after="EDITING", content={"action": action, "worker_memo": worker_memo}, changes=[])
    return record_no


def create_pm_record(db: Db, actor: str, pm_task_id: str, due_date, result: str, done_by: str | None = None,
                     done_at=None, measured_value=None, measured_unit: str | None = None, memo: str | None = None) -> int:
    rid = db.scalar("maintenance.pm_record_create", pm_task_id=pm_task_id, due_date=due_date, done_at=done_at,
                    done_by=done_by or actor, actor=actor, result=result, measured_value=measured_value,
                    measured_unit=measured_unit, memo=memo)
    db.scalar("documents.save_revision", doc_type="PM_RECORD", doc_key=str(rid), author_kind="HUMAN", author=actor,
              reason=None, status_after="EDITING", content={"result": result, "measured_value": measured_value,
                                                             "measured_unit": measured_unit, "memo": memo}, changes=[])
    return rid
