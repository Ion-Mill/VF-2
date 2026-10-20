"""문서 수정 = 새 버전 저장 + 본문 고치기 (R-35, FR-AST-03).

순서 (한 트랜잭션):
  1. 지금 본문을 읽는다.
  2. 바뀐 칸만 골라 document_revision_change 모양으로 만든다 (바뀐 게 없으면 거절).
  3. fn_save_revision → 새 version_no. 확정된 문서면 DB가 사유·권한자를 확인한다.
  4. 본문 표를 고치고 current_version = 새 version_no. 확정된 문서는 DB 잠금 트리거가 이 짝을 확인한다.
상태: AI비서 초안 → 수정 중, 확정 → 확정 후 수정(REVISED, 다시 확정 없음 — 6.16). 작업기록서는 확인 표시가 풀린다 (6.15).
version을 주면 지금 버전과 같아야 한다 — 다르면 409 CONFLICT_VERSION (API명세서 1장 "고치기").
확정된 문서를 사유 없이 고치면 422 VALIDATION (API명세서 1장 "확정 후 수정 reason 필수") — DB도 R-35로 한 번 더 막는다.
"""
from __future__ import annotations

from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db import Db
from ..errors import AppError, not_found

LOCKED = {
    "SHIFT_REPORT": {"CONFIRMED", "REVISED"},
    "DAILY_REPORT": {"CONFIRMED", "REVISED"},
    "PM_RECORD": {"CONFIRMED"},          # 논리 ERD 5.D.8: DRAFT / CONFIRMED (확정 뒤 고쳐도 CONFIRMED, 새 버전 + 사유)
    "SHIPMENT": {"CONFIRMED", "REVISED"},
    "WORK_RECORD": {"CONFIRMED", "CHECKED"},
    "WORK_ORDER": {"APPROVED", "IN_PROGRESS", "DONE", "CANCELLED"},
}


def _must(row: dict | None, what: str) -> dict:
    if row is None:
        raise not_found(what)
    return row


def _diff(current: dict, changes: dict[str, Any], fields: tuple[str, ...]) -> list[dict]:
    out = []
    for f in fields:
        if f not in changes or changes[f] is None:
            continue
        before = current.get(f)
        if str(before) != str(changes[f]):
            out.append({"field": f, "before": None if before is None else str(before), "after": str(changes[f])})
    if not out:
        raise AppError(422, "VALIDATION", "바뀐 칸이 없음", {"reason": "NO_CHANGE"})
    return out


def _guard(doc_type: str, cur: dict, reason: str | None, version: int | None) -> None:
    if version is not None and int(cur["current_version"]) != int(version):
        raise AppError(409, "CONFLICT_VERSION", f"다른 사람이 먼저 고쳤음 (지금 v{cur['current_version']}, 보낸 v{version})",
                       {"current_version": int(cur["current_version"])})
    if cur["status"] in LOCKED[doc_type] and not (reason or "").strip():
        raise AppError(422, "VALIDATION", "확정된 문서를 고치려면 사유(reason)가 필요함 (R-35)", {"reason": "REASON_REQUIRED"})


def is_locked(doc_type: str, status: str) -> bool:
    return status in LOCKED[doc_type]


def _next_status(doc_type: str, status: str) -> str:
    if status in LOCKED[doc_type]:
        return "REVISED" if doc_type in ("SHIFT_REPORT", "DAILY_REPORT", "SHIPMENT") else status
    return "EDITING" if status == "AI_DRAFT" else status


def _save(db: Db, doc_type: str, key: str, actor_id: str, reason: str | None, status_after: str,
          content: dict, diffs: list[dict]) -> int:
    return db.scalar("documents.save_revision", doc_type=doc_type, doc_key=key, author_kind="HUMAN", author=actor_id,
                     reason=reason, status_after=status_after, content=content, changes=diffs)


def edit_shift_report(db: Db, shift_id: str, actor_id: str, changes: dict, reason: str | None, version: int | None = None) -> int:
    cur = _must(db.one("documents.shift_report", shift_id=shift_id), "교대 보고서")
    _guard("SHIFT_REPORT", cur, reason, version)
    fields = ("notable_text", "handover_text")
    diffs = _diff(cur, changes, fields)
    status = _next_status("SHIFT_REPORT", cur["status"])
    content = {f: changes.get(f, cur.get(f)) for f in fields}
    ver = _save(db, "SHIFT_REPORT", shift_id, actor_id, reason, status, content, diffs)
    db.exec("documents.shift_report_update", shift_id=shift_id, notable_text=changes.get("notable_text"),
            handover_text=changes.get("handover_text"), status=status, version=ver)
    return ver


def edit_daily_report(db: Db, work_date: str, actor_id: str, changes: dict, reason: str | None, version: int | None = None) -> int:
    cur = _must(db.one("documents.daily_report", work_date=work_date), "일일 보고서")
    _guard("DAILY_REPORT", cur, reason, version)
    fields = ("issues_summary", "memo")         # memo = 관리자 메모 (2026-10-20). 빈 글자는 메모 지우기
    if "memo" in changes:                       # 비교는 빈 글자로 맞춰서 (없음 → "" 도 바뀐 것으로 보지 않게)
        changes = {**changes, "memo": (changes["memo"] or "").strip()}
        cur = {**cur, "memo": cur.get("memo") or ""}
    diffs = _diff(cur, changes, fields)
    status = _next_status("DAILY_REPORT", cur["status"])
    ver = _save(db, "DAILY_REPORT", str(work_date), actor_id, reason, status,
                {f: changes.get(f, cur.get(f)) for f in fields}, diffs)
    db.exec("documents.daily_report_update", work_date=work_date, issues_summary=changes.get("issues_summary"),
            memo_given="memo" in changes, memo=changes.get("memo") or None, status=status, version=ver)
    return ver


def edit_pm_record(db: Db, pm_record_id: int, actor_id: str, changes: dict, reason: str | None, version: int | None = None) -> int:
    cur = _must(db.one("documents.pm_record_get", pm_record_id=pm_record_id), "예방 정비 기록")
    _guard("PM_RECORD", cur, reason, version)
    fields = ("result", "measured_value", "measured_unit", "memo")
    diffs = _diff(cur, changes, fields)
    status = _next_status("PM_RECORD", cur["status"])
    ver = _save(db, "PM_RECORD", str(pm_record_id), actor_id, reason, status,
                {f: changes.get(f, cur.get(f)) for f in fields}, diffs)
    db.exec("documents.pm_record_update", pm_record_id=pm_record_id, result=changes.get("result"),
            measured_value=changes.get("measured_value"), measured_unit=changes.get("measured_unit"),
            memo=changes.get("memo"), status=status, version=ver)
    return ver


def edit_shipment(db: Db, shipment_no: str, actor_id: str, changes: dict, reason: str | None, version: int | None = None) -> int:
    cur = _must(db.one("inventory.shipment", shipment_no=shipment_no), "출하")
    _guard("SHIPMENT", cur, reason, version)
    fields = ("memo",)
    diffs = _diff(cur, changes, fields)
    status = _next_status("SHIPMENT", cur["status"])
    ver = _save(db, "SHIPMENT", shipment_no, actor_id, reason, status, {"memo": changes.get("memo", cur.get("memo"))}, diffs)
    db.exec("documents.shipment_update", shipment_no=shipment_no, memo=changes.get("memo"), status=status, version=ver)
    return ver


def edit_work_order(db: Db, wo_no: str, actor_id: str, changes: dict, reason: str | None, version: int | None = None) -> int:
    cur = _must(db.one("maintenance.wo_get", wo_no=wo_no), "작업지시서")
    _guard("WORK_ORDER", cur, reason, version)
    fields = ("title", "symptom")
    diffs = _diff(cur, changes, fields)
    status = _next_status("WORK_ORDER", cur["status"])
    ver = _save(db, "WORK_ORDER", wo_no, actor_id, reason, status, {f: changes.get(f, cur.get(f)) for f in fields}, diffs)
    db.exec("maintenance.wo_update_content", wo_no=wo_no, title=changes.get("title"), symptom=changes.get("symptom"),
            version=ver)
    return ver


def edit_work_record(db: Db, record_no: str, actor_id: str, changes: dict, reason: str | None, version: int | None = None) -> int:
    cur = _must(db.one("maintenance.wr_get", record_no=record_no), "작업기록")
    _guard("WORK_RECORD", cur, reason, version)
    fields = ("cause", "action", "worker_memo", "end_at", "repair_min")
    diffs = _diff(cur, changes, fields)
    status = _next_status("WORK_RECORD", cur["status"])
    ver = _save(db, "WORK_RECORD", record_no, actor_id, reason, status, {f: changes.get(f, cur.get(f)) for f in fields}, diffs)
    db.exec("maintenance.wr_update_content", record_no=record_no, cause=changes.get("cause"), action=changes.get("action"),
            worker_memo=changes.get("worker_memo"), end_at=changes.get("end_at"), repair_min=changes.get("repair_min"),
            version=ver)
    return ver
