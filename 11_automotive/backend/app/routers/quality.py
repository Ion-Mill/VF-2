"""품질: 검사 기록·CMM 결과 파일·측정 지시·관리도·Cpk (QLT-01, DOC-06, R-78~R-81 — API명세서 QLT-01~05).

측정 결과 파일 읽기(공유 폴더 감시 → cmm_import)는 서버 안쪽 일 (app/workers/cmm_watcher.py). 여기 /cmm-imports POST는
직접 올리기용이다.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..domain.cmm_csv import CmmFormatError
from ..errors import AppError
from ..security import Actor, permissions, require, require_any
from ..services import cmm
from . import qr as qr_router
from .common import changed, must, period

router = APIRouter(prefix="/api", tags=["품질"])
MAX_CSV_BYTES = 1_000_000
MEASURE_PROCESS = "OP-50"     # 측정 담당 = 담당 공정이 OP-50(검사)인 작업자 (API명세서 QLT-02 "O(측정 담당)", UI설계서 1장 [제안])


def _measurer(db: Db, actor: Actor) -> None:
    """검사 결과 입력·결과 파일 올리기·측정 지시·측정 시작: 반장(QUALITY·CHECK 권한)은 그대로, 작업자는 측정 담당(OP-50)만"""
    if permissions(db).allows(actor.role, "QUALITY", "CHECK"):
        return
    if MEASURE_PROCESS not in actor.user.processes:
        raise AppError(403, "FORBIDDEN", f"측정 담당({MEASURE_PROCESS} 작업자)만 입력함 — 이 사용자 담당 공정: "
                       f"{'·'.join(actor.user.processes) or '없음'}", {"reason": "NOT_MEASURER"})


# ---------------- 검사 기록 (QLT-01~03) ----------------
@router.get("/inspection/results")
def results(lot_no: str, _: Actor = Depends(require("QUALITY", "VIEW")), db: Db = Depends(get_db)):
    """검사 기록 (QLT-01): 로트의 측정값·입력 방식(자동/수동/태블릿)·부품 온도·확인 상태 (재측정 포함, 판정에 쓰는 값 표시)"""
    return db.all("quality.results", lot_no=lot_no)


class ResultIn(BaseModel):
    lot_no: str
    part_seq: int = Field(gt=0)
    item_seq: int = Field(description="게이지(6)·외관(7)은 judgement, 3차원 측정기 항목은 measured_value (수동 입력)")
    insp_kind: str = Field(pattern="^(FIRST|SAMPLE|ENHANCED)$")
    judgement: str | None = Field(None, pattern="^(PASS|FAIL)$")
    measured_value: Decimal | None = None
    inspector_id: str | None = Field(None, description="수동 입력 때 실제로 잰 작업자 (비우면 입력한 사람 — 작업자여야 함)")


@router.post("/inspection/results")
def result_create(body: ResultIn, actor: Actor = Depends(require_any(("QUALITY", "INPUT"), ("QUALITY", "CHECK"))),
                  db: Db = Depends(get_db)):
    """게이지·외관 결과 (태블릿 합격·불합격, FR-QLT-01-20) 또는 3차원 측정기 값 수동 입력 (QLT-02, FR-QLT-01-19 — "수동" 표시,
    확인 필요에서 시작해 반장이 고르면 판정에 씀, R-81). 측정자는 작업자(OPR)만 (DB 확인), 입력은 측정 담당·반장"""
    _measurer(db, actor)
    if body.measured_value is None:
        if body.judgement is None:
            raise AppError(422, "VALIDATION", "judgement(게이지·외관) 또는 measured_value(수동 입력) 중 하나가 필요함")
        rid = db.scalar("quality.tablet_result", actor=actor.user_id, lot_no=body.lot_no, part_seq=body.part_seq,
                        item_seq=body.item_seq, insp_kind=body.insp_kind, judgement=body.judgement)
        return {"result_id": rid, "input_method": "TABLET"}
    rid = db.scalar("quality.manual_result", actor=actor.user_id, inspector=body.inspector_id or actor.user_id,
                    lot_no=body.lot_no, part_seq=body.part_seq, item_seq=body.item_seq, insp_kind=body.insp_kind,
                    measured_value=body.measured_value)
    if rid is None:
        raise AppError(404, "NOT_FOUND", "로트 또는 검사 항목 없음")
    return {"result_id": rid, "input_method": "MANUAL", "check_status": "NEEDS_CHECK"}


class SelectIn(BaseModel):
    use_for_judgement: bool = Field(True, description="이 측정값을 판정에 쓸지 (같은 부품·항목의 다른 값은 판정에서 빠짐)")


@router.post("/inspection/results/{result_id}/select")
def select(result_id: int, body: SelectIn, actor: Actor = Depends(require("QUALITY", "CHECK")), db: Db = Depends(get_db)):
    """재측정 값 고르기 · 반장 확인 (QLT-03, SUP, FR-QLT-01-20~22) → 확인 상태 = 반장 확인"""
    db.scalar("quality.check_measurement", result_id=result_id, actor=actor.user_id, use_for_judgement=body.use_for_judgement)
    return {"result_id": result_id, "check_status": "CHECKED"}


# ---------------- CMM 결과 파일 (QLT-04) ----------------
@router.get("/inspection/cmm-imports")
def imports(status: str | None = Query(None, description="비우면 전부, PROBLEM = 실패·확인 필요만"),
            limit: int = Query(100, le=500), _: Actor = Depends(require("QUALITY", "VIEW")), db: Db = Depends(get_db)):
    """결과 파일 기록·오류 목록 (QLT-04): 파일 이름·받은 시각·상태·오류"""
    rows = db.all("quality.imports", problem_only=status == "PROBLEM", limit=limit)
    return rows if status in (None, "PROBLEM") else [r for r in rows if r["status"] == status]


@router.post("/inspection/cmm-imports")
def upload(file: UploadFile = File(...), actor: Actor = Depends(require_any(("QUALITY", "INPUT"), ("QUALITY", "CHECK"))),
           db: Db = Depends(get_db)):
    """결과 파일 직접 올리기 (보통은 공유 폴더 감시 app/workers/cmm_watcher.py가 받는다). 측정 담당·반장"""
    _measurer(db, actor)
    raw = file.file.read(MAX_CSV_BYTES + 1)     # 동기 처리기 (DB 호출이 동기라 스레드에서 돈다)
    name = file.filename or "upload.csv"
    ref = cmm.save_upload(raw[:MAX_CSV_BYTES], name)
    if len(raw) > MAX_CSV_BYTES:
        return cmm.record_failure(db, name, ref, CmmFormatError(f"파일이 너무 큼 (>{MAX_CSV_BYTES} bytes)"))
    try:
        text = cmm.decode(raw)
    except CmmFormatError as e:
        return cmm.record_failure(db, name, ref, e)
    return cmm.import_text(db, name, text, file_ref=ref)


# ---------------- 측정 지시 (R-78, FR-QLT-01-15) ----------------
@router.get("/inspection/instructions")
def instructions(_: Actor = Depends(require("QUALITY", "VIEW")), db: Db = Depends(get_db)):
    """열린 측정 지시"""
    return db.all("quality.instructions_open")


class InstructionIn(BaseModel):
    lot_no: str
    part_seq: int = Field(gt=0)
    first: bool = False       # 초품


@router.post("/inspection/instructions")
def issue(body: InstructionIn, actor: Actor = Depends(require_any(("QUALITY", "INPUT"), ("QUALITY", "CHECK"))),
          db: Db = Depends(get_db)):
    """측정 지시 (R-78). 발췌 로트는 1·5의 배수 순번만, 보류 로트는 강화 검사 — DB가 정한다. 측정 담당·반장"""
    _measurer(db, actor)
    return {"instruction_id": db.scalar("quality.instruction_issue", **body.model_dump())}


class StartIn(BaseModel):
    scanned_code: str | None = Field(None, description="부품 꼬리표 로트 QR(바코드)을 찍은 글자 — 지시의 로트와 같아야 함")
    no_scan_reason: str | None = Field(None, description="라벨이 상해 못 찍었을 때 사유 (찍은 기록에 '수동'으로 남음)")


@router.post("/inspection/instructions/{instruction_id}/start")
def start(instruction_id: int, body: StartIn | None = None, actor: Actor = Depends(require("QUALITY", "INPUT")),
          db: Db = Depends(get_db)):
    """측정 시작 (측정 담당 작업자가 부품을 CMM에 올림). 이때부터 결과 미수신 시간을 잰다.
    로트 QR 확인 (DOC-06 §3.6 "측정 전에 바코드로 확인", FR-QLT-01-20): 찍은 로트가 지시와 다르면 409 LOT_MISMATCH.
    못 찍으면 no_scan_reason (수동 확인)"""
    _measurer(db, actor)
    body = body or StartIn()
    ins = must(db.one("quality.instruction_get", instruction_id=instruction_id), "측정 지시")
    if body.scanned_code:
        kind, no = qr_router.read_code(body.scanned_code)
        if kind != "LOT" or no != ins["lot_no"]:
            raise AppError(409, "INVALID_STATE", f"찍은 QR({no})이 측정 지시의 로트({ins['lot_no']})와 다름 — 부품을 확인",
                           {"reason": "LOT_MISMATCH", "expected": ins["lot_no"], "scanned": no})
        scan = dict(raw_code=body.scanned_code, kind=kind, no=no, result="OK", detail=None)
    elif (body.no_scan_reason or "").strip():
        scan = dict(raw_code=None, kind="NONE", no=None, result="MANUAL", detail=body.no_scan_reason.strip())
    else:
        raise AppError(422, "VALIDATION", "측정 시작 전에 로트 QR을 찍어야 함 (scanned_code) — 못 찍으면 no_scan_reason")
    row = db.one("quality.instruction_start", instruction_id=instruction_id, actor=actor.user_id)
    changed(1 if row else 0, "측정 시작")
    qr_router.log_scan(db, actor, scan["raw_code"], scan["kind"], scan["no"], "MEASURE_START", scan["result"],
                       instruction_id=instruction_id, detail=scan["detail"])
    return row


# ---------------- 불량 집계·관리도·Cpk (QLT-05) ----------------
@router.get("/quality/summary")
def summary(frm: datetime | None = Query(None, alias="from"), to: datetime | None = None, product_code: str | None = None,
            points: int = Query(50, ge=1, le=500), _: Actor = Depends(require("QUALITY", "VIEW")), db: Db = Depends(get_db)):
    """불량 집계·관리도·Cpk (QLT-05, FR-QLT-01-08~13): 불량 코드별 수(기본 최근 7일), 기준값이 있는 항목마다 관리도 점(최근
    points개, I-MR)과 Cpk (50개 미만이면 '계산 중' — is_calculating)"""
    frm, to = period(db, frm, to, default_hours=24 * 7)
    items = []
    for it in db.all("quality.measurable_items", product_code=product_code):
        cpk = db.one("quality.cpk", product_code=it["product_code"], item_seq=it["item_seq"], equipment_id=None)
        chart = db.all("quality.chart_points", product_code=it["product_code"], item_seq=it["item_seq"], limit=points,
                       **{"from": frm, "to": to})
        items.append({**it, "cpk": cpk, "chart": chart})
    return {"from": frm, "to": to, "defects": db.all("quality.defects", **{"from": frm, "to": to}), "items": items}


@router.get("/quality/cpk")
def cpk(product_code: str, item_seq: int, equipment_id: str | None = None, _: Actor = Depends(require("QUALITY", "VIEW")),
        db: Db = Depends(get_db)):
    """Cpk (I-MR) 항목 하나. 50개 미만이면 '계산 중'. 설비별(가공 설비 — 05 결정기록 P-11)은 참고용"""
    return db.one("quality.cpk", product_code=product_code, item_seq=item_seq, equipment_id=equipment_id)


@router.get("/quality/defects")
def defects(frm: datetime | None = Query(None, alias="from"), to: datetime | None = None,
            _: Actor = Depends(require("QUALITY", "VIEW")), db: Db = Depends(get_db)):
    """불량 코드별 수량 (기본 최근 7일)"""
    frm, to = period(db, frm, to, default_hours=24 * 7)
    return db.all("quality.defects", **{"from": frm, "to": to})
