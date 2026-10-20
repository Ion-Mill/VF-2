"""보고서·문서함·수정 이력·사내 문서 (PRD-02·04, AST-03, R-35·R-36·R-52·R-72 — API명세서 RPT-01~05, DOC-01·02, DOCS-01·02).

AI비서 초안(v0) → 사람이 고침(v1…) → 확정. 확정 뒤 수정(revise)은 사유 필수 + 확정 권한자만 (DB가 한 번 더 확인).
교대 보고서 확정은 그 교대 반장만 (R-36), 일일 보고서 확정은 MGR — 잠정 칸(확정 안 된 교대)이 있으면 확정 불가 (R-72).
문서를 고치는 요청은 version을 보낸다 — 다르면 CONFLICT_VERSION.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..domain.permissions import doc_viewable
from ..errors import AppError
from ..security import Actor, permissions, require
from ..services import documents
from .common import changed, check_version, must

router = APIRouter(prefix="/api", tags=["보고서·문서"])


class EditIn(BaseModel):
    version: int
    changes: dict


class ReviseIn(BaseModel):
    reason: str = Field(min_length=1)
    changes: dict
    version: int | None = None


class VersionIn(BaseModel):
    version: int


class DailyConfirmIn(VersionIn):
    memo: str | None = Field(None, max_length=2000, description="관리자 메모 (선택). 비우면 있던 메모 그대로")


def _not_locked(doc_type: str, row: dict, what: str) -> None:
    if documents.is_locked(doc_type, row["status"]):
        raise AppError(409, "INVALID_STATE", f"확정된 {what}는 …/revise (사유 필수)로 고친다")


def _locked(doc_type: str, row: dict, what: str) -> None:
    if not documents.is_locked(doc_type, row["status"]):
        raise AppError(409, "INVALID_STATE", f"확정 전 {what}는 PATCH로 고친다")


# ---------------- 교대 보고서 (RPT-01~04) ----------------
def _own_shift(db: Db, actor: Actor, shift_id: str) -> None:
    """저장·확정·확정 후 수정은 그 교대 반장만 (API명세서 RPT-02~04 "그 교대 S"). 확정은 DB 트리거(R-36)가 한 번 더 막는다"""
    sup = db.scalar("documents.shift_supervisor", shift_id=shift_id)
    if sup is None or sup != actor.user_id:
        raise AppError(403, "FORBIDDEN", f"교대 보고서는 그 교대 반장({sup or '없음'})만 고치고 확정함",
                       {"reason": "NOT_SHIFT_SUPERVISOR"})


@router.get("/reports/shift/{shift_id}")
def shift_report(shift_id: str, _: Actor = Depends(require("SHIFT_REPORT", "VIEW")), db: Db = Depends(get_db)):
    """교대 보고서 (RPT-01): 생산(총 목표 = 목표 + 이월·실적·불량·가동률), 특이 사항, 인계 사항, 상태, 버전, 필수 정지 stops[]
    stops[] = 필수 정지마다 연결된 작업지시서 wo_no와 보고서 시점 상태 wo_status_at_report (2026-10-20, documents.sql report_stops)"""
    row = must(db.one("documents.shift_report", shift_id=shift_id), "교대 보고서")
    return {**row, **_report_sections(db, shift_id=shift_id, work_date=None)}


@router.patch("/reports/shift/{shift_id}")
def shift_report_edit(shift_id: str, body: EditIn, actor: Actor = Depends(require("SHIFT_REPORT", "EDIT")),
                      db: Db = Depends(get_db)):
    """저장 (RPT-02, 그 교대 반장) = 새 버전. 확정 뒤에는 /revise"""
    _own_shift(db, actor, shift_id)
    _not_locked("SHIFT_REPORT", must(db.one("documents.shift_report", shift_id=shift_id), "교대 보고서"), "교대 보고서")
    return {"version_no": documents.edit_shift_report(db, shift_id, actor.user_id, body.changes, None, body.version)}


@router.post("/reports/shift/{shift_id}/confirm")
def shift_report_confirm(shift_id: str, body: VersionIn, actor: Actor = Depends(require("SHIFT_REPORT", "CONFIRM")),
                         db: Db = Depends(get_db)):
    """확정 (RPT-03, 그 교대 반장만 — DB 트리거 R-36) → 잠김. 확정 요청 알림 자동 처리, 주간이면 야간 이월 다시 계산,
    일일 보고서가 있으면 그 칸을 다시 채운다. AI비서 초안 그대로도 확정할 수 있다 (6.16) [확인 필요]"""
    _own_shift(db, actor, shift_id)
    check_version(db, "SHIFT_REPORT", shift_id, body.version)
    changed(db.exec("documents.shift_report_confirm", shift_id=shift_id, actor=actor.user_id), "교대 보고서 확정")
    return {"shift_id": shift_id, "status": "CONFIRMED"}


@router.post("/reports/shift/{shift_id}/revise")
def shift_report_revise(shift_id: str, body: ReviseIn, actor: Actor = Depends(require("SHIFT_REPORT", "CONFIRM")),
                        db: Db = Depends(get_db)):
    """확정 후 수정 (RPT-04, 그 교대 반장): 사유 필수 → 새 버전 + 관리자에게 문서 수정 알림 (FR-AST-03-06·07)"""
    _own_shift(db, actor, shift_id)
    _locked("SHIFT_REPORT", must(db.one("documents.shift_report", shift_id=shift_id), "교대 보고서"), "교대 보고서")
    return {"version_no": documents.edit_shift_report(db, shift_id, actor.user_id, body.changes, body.reason, body.version)}


def _report_sections(db: Db, shift_id: str | None, work_date: date | None) -> dict:
    """교대·일일 보고서의 원기록 칸 (2026-10-20): 필수 정지·순간 정지 한 줄·로트·병목·정비 (documents.sql report_*)"""
    k = {"shift_id": shift_id, "work_date": work_date}
    return {"stops": db.all("documents.report_stops", **k), "micro_stops": db.one("documents.report_micro_stops", **k),
            "lots": db.all("documents.report_lots", **k), "bottleneck": db.all("documents.report_bottleneck", **k),
            "maintenance": db.all("documents.report_maintenance", **k)}


# ---------------- 일일 보고서 (RPT-05) ----------------
@router.get("/reports/daily/{work_date}")
def daily_report(work_date: date, _: Actor = Depends(require("DAILY_REPORT", "VIEW")), db: Db = Depends(get_db)):
    """일일 보고서 (RPT-05, 조회 S·M·G): 하루 생산(목표 180 고정·실적·부족 = 180 − 실적), 손실, OEE, 오늘의 문제, 관리자 메모, 필수 정지
    잠정 교대(provisional_shift_ids). memo = 관리자 메모, stops[] = 교대 보고서와 같은 필수 정지 목록 (2026-10-20)"""
    row = must(db.one("documents.daily_report", work_date=work_date), "일일 보고서")
    out = {**row, **_report_sections(db, shift_id=None, work_date=work_date)}
    # 손실 전체를 손실 수량 큰 순으로 (FR-PRD-04-03 — 고장 정지 + 병목 속도 손실, 모두 추정)
    out["losses"] = sorted(
        [{"kind": "FAILURE", "label": f"{x['equipment_id']} {x['reason_name'] or x['reason_code']}", "minutes": x["minutes"],
          "loss_qty": x["loss_qty"]} for x in out["stops"]]
        + [{"kind": "SPEED", "label": f"{x['process_code']} {x['cause_name']}", "minutes": x["minutes"], "loss_qty": x["speed_loss_qty"]}
           for x in out["bottleneck"] if float(x["speed_loss_qty"] or 0) > 0],
        key=lambda x: -float(x["loss_qty"] or 0))
    out["shifts"] = db.all("documents.report_shift_compare", work_date=work_date)
    out["alarms"] = db.one("documents.report_alarm_counts", shift_id=None, work_date=work_date)
    out["mttr"] = db.one("documents.report_mttr", shift_id=None, work_date=work_date)
    out["inventory"] = {"items": db.all("documents.report_inventory_usage", shift_id=None, work_date=work_date),
                        "finished": db.one("documents.report_fg_line", shift_id=None, work_date=work_date)}
    return out


@router.patch("/reports/daily/{work_date}")
def daily_report_edit(work_date: date, body: EditIn, actor: Actor = Depends(require("DAILY_REPORT", "EDIT")),
                      db: Db = Depends(get_db)):
    """일일 보고서 저장 = 새 버전 (RPT-05, MGR). 확정 뒤에는 /revise"""
    _not_locked("DAILY_REPORT", must(db.one("documents.daily_report", work_date=work_date), "일일 보고서"), "일일 보고서")
    return {"version_no": documents.edit_daily_report(db, str(work_date), actor.user_id, body.changes, None, body.version)}


@router.post("/reports/daily/{work_date}/confirm")
def daily_report_confirm(work_date: date, body: DailyConfirmIn, actor: Actor = Depends(require("DAILY_REPORT", "CONFIRM")),
                         db: Db = Depends(get_db)):
    """일일 보고서 확정 (RPT-05, MGR) + 관리자 메모(memo, 선택). 잠정 칸(확정 안 된 교대 보고서)이 있으면 INVALID_STATE (R-72)
    [확정] 비활성. memo는 조회 응답의 memo로 나온다 — 전에는 버려졌다 (2026-10-20)"""
    row = must(db.one("documents.daily_report", work_date=work_date), "일일 보고서")
    pending = row["provisional_shift_ids"]
    if pending not in (None, [], "[]"):
        raise AppError(409, "INVALID_STATE", f"확정 안 된 교대 보고서가 있어 확정할 수 없음 (잠정: {pending})",
                       {"provisional_shift_ids": pending})
    check_version(db, "DAILY_REPORT", str(work_date), body.version)
    changed(db.exec("documents.daily_report_confirm", work_date=work_date, actor=actor.user_id, memo=body.memo),
            "일일 보고서 확정")
    return {"work_date": work_date, "status": "CONFIRMED"}


@router.post("/reports/daily/{work_date}/revise")
def daily_report_revise(work_date: date, body: ReviseIn, actor: Actor = Depends(require("DAILY_REPORT", "CONFIRM")),
                        db: Db = Depends(get_db)):
    """일일 보고서 확정 후 수정 (MGR): 사유 필수 → 새 버전"""
    _locked("DAILY_REPORT", must(db.one("documents.daily_report", work_date=work_date), "일일 보고서"), "일일 보고서")
    return {"version_no": documents.edit_daily_report(db, str(work_date), actor.user_id, body.changes, body.reason,
                                                      body.version)}


# ---------------- 문서함·수정 이력 (DOC-01·02) ----------------
def _doc_viewable(db: Db, actor: Actor, doc_type: str, doc_key: str) -> bool:
    return doc_viewable(permissions(db), actor.role, doc_type, doc_key)


def _can_view_doc(db: Db, actor: Actor, doc_type: str, doc_key: str) -> None:
    if not _doc_viewable(db, actor, doc_type, doc_key):
        raise AppError(403, "FORBIDDEN", f"{actor.role} 역할은 {doc_type} 문서를 볼 수 없음")


@router.get("/documents")
def inbox(doc_type: str | None = Query(None, alias="type"), status: str | None = None, mine: bool = False,
          limit: int = Query(200, le=1000), actor: Actor = Depends(require("REVISION_HISTORY", "VIEW")),
          db: Db = Depends(get_db)):
    """문서함 (DOC-01, SCR-18): 문서 6종 중 역할이 볼 수 있는 것만. mine = 내 할 일만 (할 일이 위로)"""
    rows = db.all("documents.inbox", user_id=actor.user_id, role=actor.role, doc_type=doc_type, status=status,
                  todo_only=mine, limit=limit)
    return [r for r in rows if _doc_viewable(db, actor, r["doc_type"], r["doc_key"])]


@router.get("/documents/{doc_type}/{doc_key}/revisions")
def revisions(doc_type: str, doc_key: str, actor: Actor = Depends(require("REVISION_HISTORY", "VIEW")),
              db: Db = Depends(get_db)):
    """수정 이력 (DOC-02): 버전 목록·바뀐 칸 수·사유 (누가·언제·왜). OPR은 자기가 고친 것만 (OWN)"""
    _can_view_doc(db, actor, doc_type, doc_key)
    own = actor.user_id if actor.scope == "OWN" else None
    return db.all("documents.revisions", doc_type=doc_type, doc_key=doc_key, own_user=own)


@router.get("/documents/revisions/{revision_id}")
def revision(revision_id: int, actor: Actor = Depends(require("REVISION_HISTORY", "VIEW")), db: Db = Depends(get_db)):
    """버전 1개 + 바뀐 칸 (전/후). OPR(OWN)은 목록과 같은 규칙 — 자기가 고친 버전만 (번호로 직접 열어도)"""
    r = must(db.one("documents.revision", revision_id=revision_id), "버전")
    _can_view_doc(db, actor, r["doc_type"], r["doc_key"])
    if actor.scope == "OWN" and r.get("author_user_id") != actor.user_id:
        raise AppError(403, "FORBIDDEN", "수정 이력은 자기가 고친 것만 볼 수 있음 (OPR)", {"reason": "NOT_OWN_REVISION"})
    return r


# ---------------- 사내 문서 (DOCS-01·02) ----------------
@router.get("/internal-docs")
def internal_docs(_: Actor = Depends(require("INTERNAL_DOC", "VIEW")), db: Db = Depends(get_db)):
    """사내 문서 목록 (DOC-01~07 + 용어집). 원문 출처는 내보내지 않는다 (R-85)"""
    return db.all("documents.internal_docs")


@router.get("/internal-docs/{doc_no}")
def internal_doc(doc_no: str, _: Actor = Depends(require("INTERNAL_DOC", "VIEW")), db: Db = Depends(get_db)):
    """사내 문서 1건 (Rev·승인 정보)"""
    return must(db.one("documents.internal_doc", doc_no=doc_no), "사내 문서")


@router.get("/internal-docs/{doc_no}/sections/{section}")
def internal_doc_section(doc_no: str, section: str, view: str = Query("card", pattern="^(card|full)$"),
                         _: Actor = Depends(require("INTERNAL_DOC", "VIEW")), db: Db = Depends(get_db)):
    """출처 요약 카드·팝업 (DOCS-01, R-85): 문서 이름·번호·개정·절 제목 + 앞 2~3줄(card) 또는 그 절 본문(full).
    절 내용은 현행판 문서 조각(doc_chunk)에서 — 조각은 AI 비서 서비스가 만든다"""
    row = must(db.one("documents.doc_section", doc_no=doc_no, section=section.lstrip("§")), "사내 문서 절")
    body = row.pop("body") or ""
    if view == "card":
        row["preview"] = "\n".join(body.splitlines()[1:4])
    else:
        row["body"] = body
    return row


@router.post("/internal-docs/{doc_no}/revisions/{rev}/approve")
def internal_doc_approve(doc_no: str, rev: str, actor: Actor = Depends(require("INTERNAL_DOC", "APPROVE")),
                         db: Db = Depends(get_db)):
    """사내 문서 개정 승인 (DOCS-02, MGR, R-52): 새 현행판 + 문서 버전 + 관련 역할 전체에게 문서 수정 알림"""
    before = must(db.one("documents.internal_doc", doc_no=doc_no), "사내 문서")
    changed(db.exec("documents.internal_doc_approve", doc_no=doc_no, rev=rev, actor=actor.user_id), "사내 문서 개정 승인")
    db.scalar("documents.internal_doc_save_revision", doc_no=doc_no, actor=actor.user_id, rev=rev,
              reason=f"{rev} 개정 승인", content={"current_rev": rev},
              changes=[{"field": "current_rev", "before": before["current_rev"], "after": rev}])
    return db.one("documents.internal_doc", doc_no=doc_no)
