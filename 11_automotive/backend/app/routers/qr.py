"""QR로 재고·로트 관리 (2026-10-13 가정 [제안] — 기획서·요구사항·UI설계서에는 아직 없음, docs/품질·재고관리/README.md "가정").

QR 안에는 번호만 있다 (app/domain/qr.py). 찍으면 서버가 지금 상태를 읽어 돌려주고, 찍은 일은 qr_scan에 남긴다.
QR로 할 수 있는 일:
  · 조회   POST /api/qr/scan                — 로트·원자재 로트·품목 무엇이든. 이 역할이 지금 할 수 있는 일(can)도 함께
  · 입고·실사 POST /api/qr/inventory          — 품목 QR. 그 품목 관리 역할만 (소모품 MNT / 공구·원자재·완제품 SUP, R-77)
  · 출하 전 로트 확인 POST /api/shipments/{no}/qr-check — 출하 줄에 없는 로트면 MISMATCH (기록은 남고 줄은 그대로)
  · 측정 시작 로트 확인 — POST /api/inspection/instructions/{id}/start 의 scanned_code (quality.py)
사용(차감)은 QR로 하지 않는다: 차감은 공구 교체·작업기록·예방 정비·로트 투입이 자동으로 한다 (FR-INV-01-03 차감 규칙).
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..db import Db, get_db
from ..domain import qr
from ..errors import AppError
from ..security import Actor, permissions, require
from .common import must
from .inventory import CATEGORY_KO, owned_item

router = APIRouter(prefix="/api", tags=["QR"])


def read_code(code: str) -> tuple[str, str]:
    try:
        return qr.parse(code)
    except qr.QrError as e:
        raise AppError(422, "VALIDATION", str(e), {"reason": "BAD_QR"}) from None


def log_scan(db: Db, actor: Actor, raw_code: str | None, kind: str, no: str | None, purpose: str, result: str,
             shipment_no: str | None = None, instruction_id: int | None = None, txn_id=None, detail: str | None = None):
    return db.scalar("qr.scan_log", actor=actor.user_id, raw_code=raw_code, code_kind=kind, ref_no=no, purpose=purpose,
                     result=result, shipment_no=shipment_no, instruction_id=instruction_id, txn_id=txn_id, detail=detail)


def read_info(db: Db, kind: str, no: str) -> dict | None:
    """번호로 지금 상태 읽기 (없으면 None)"""
    if kind == "LOT":
        return db.one("qr.lot_info", no=no)
    if kind == "MAT":
        return db.one("qr.mat_info", no=no)
    return db.one("qr.item_info", no=no)


def _can(db: Db, actor: Actor, kind: str, info: dict) -> list[str]:
    """이 역할이 이 대상에 지금 할 수 있는 일 (화면이 버튼을 고를 때 씀 — 막는 것은 각 API가 다시 한다)"""
    p = permissions(db)
    out: list[str] = []
    if kind == "ITEM":
        scope = p.scope(actor.role, "INV_RECEIPT", "INPUT")
        if scope is not None and (scope != "OWNED_ITEMS" or info["owner_role"] == actor.role):
            if info["category"] not in ("MATERIAL", "FINISHED"):
                out.append("RECEIPT")
            if info["category"] != "FINISHED":
                out.append("STOCKTAKE")
    elif kind == "MAT":
        if info["status"] == "WAIT_RECEIPT_CHECK" and p.allows(actor.role, "MATERIAL_CHECK", "INPUT"):
            out.append("MATERIAL_CHECK")
    elif kind == "LOT":
        if info["status"] in ("PASSED", "RELEASED") and int(info["fg_remaining_qty"] or 0) > 0 \
                and p.allows(actor.role, "SHIPMENT", "EDIT"):
            out.append("SHIP")
        if info["status"] == "WAIT_INSPECTION" and p.allows(actor.role, "QUALITY", "INPUT"):
            out.append("MEASURE")
    return out


class ScanIn(BaseModel):
    code: str = Field(description="찍은 QR 글자 그대로 (MOM:LOT:LOT-2609-041-1 또는 번호만)")


@router.post("/qr/scan")
def scan(body: ScanIn, actor: Actor = Depends(require("INVENTORY", "VIEW")), db: Db = Depends(get_db)):
    """QR 조회: 로트·원자재 로트·품목의 지금 상태 + 이 역할이 할 수 있는 일. 없는 번호면 found=false (기록은 남김)"""
    kind, no = read_code(body.code)
    info = read_info(db, kind, no)
    log_scan(db, actor, body.code, kind, no, "LOOKUP", "OK" if info else "NOT_FOUND")
    if info is None:
        return {"kind": kind, "no": no, "found": False, "info": None, "can": []}
    return {"kind": kind, "no": no, "found": True, "payload": qr.payload(kind, no), "info": info,
            "can": _can(db, actor, kind, info)}


@router.get("/qr/label/{kind}/{no}")
def label(kind: str, no: str, _: Actor = Depends(require("INVENTORY", "VIEW")), db: Db = Depends(get_db)):
    """라벨에 넣을 QR 내용과 사람이 읽을 줄. QR 그림은 화면(브라우저)이 그린다 — 서버는 글자만 준다"""
    try:
        payload = qr.payload(kind, no.upper())
    except qr.QrError as e:
        raise AppError(422, "VALIDATION", str(e), {"reason": "BAD_QR"}) from None
    kind = kind.upper()
    info = must(read_info(db, kind, no.upper()), qr.KIND_KO[kind])
    if kind == "ITEM":
        lines = [info["item_no"], info["item_name"], f"관리 {info['owner_role']}"]
    elif kind == "MAT":
        lines = [info["material_lot_no"], info["item_name"], f"성적서 {info['supplier_cert_no']}"]
    else:
        lines = [info["lot_no"], f"작업지시 {info['order_no']}", f"원자재 {info['material_lot_no']}"]
    return {"kind": kind, "no": no.upper(), "payload": payload, "lines": lines}


class QrInventoryIn(BaseModel):
    code: str
    kind: str = Field(pattern="^(RECEIPT|STOCKTAKE)$", description="RECEIPT 입고 / STOCKTAKE 실사 (센 수량)")
    qty: Decimal | None = Field(None, gt=0, description="입고 수량")
    counted_qty: Decimal | None = Field(None, ge=0, description="실사: 센 수량 (차이만큼 조정 거래를 만든다)")
    reason: str | None = Field(None, description="실사 사유 (차이가 있으면 필수)")


@router.post("/qr/inventory")
def qr_inventory(body: QrInventoryIn, actor: Actor = Depends(require("INV_RECEIPT", "INPUT")), db: Db = Depends(get_db)):
    """품목 QR로 입고·실사 (INV-02와 같은 권한 — 그 품목 관리 역할만). 원자재는 로트로 입고(/api/raw-lots),
    완제품 실사는 로트별이라 재고 화면에서. 거래 기록과 찍은 기록을 남긴다"""
    kind, no = read_code(body.code)
    if kind != "ITEM":
        raise AppError(422, "VALIDATION", f"입고·실사는 품목 QR로 — 찍은 것은 {qr.KIND_KO[kind]} {no}",
                       {"reason": "WRONG_QR_KIND"})
    item = owned_item(db, actor, no)
    cat = CATEGORY_KO.get(item["category"], item["category"])
    if body.kind == "RECEIPT":
        if item["category"] in ("MATERIAL", "FINISHED"):
            raise AppError(422, "VALIDATION", f"{cat}은 QR 품목 입고 대상 아님 (원자재 = 원자재 로트 입고, 완제품 = 합격 때 자동)")
        if body.qty is None:
            raise AppError(422, "VALIDATION", "입고 수량(qty)이 필요함")
        txn_id = db.scalar("inventory.receipt", item_no=no, qty=body.qty, actor=actor.user_id, memo=body.reason)
        out = {"item_no": no, "kind": "RECEIPT", "txn_id": txn_id, "qty": body.qty}
    else:
        if item["category"] == "FINISHED":
            raise AppError(422, "VALIDATION", "완제품 실사는 로트별 — 재고 화면 실사 조정으로")
        if body.counted_qty is None:
            raise AppError(422, "VALIDATION", "센 수량(counted_qty)이 필요함")
        before = Decimal(str(db.scalar("qr.item_lock", item_no=no)))
        diff = body.counted_qty - before
        txn_id = None
        if diff != 0:
            if not (body.reason or "").strip():
                raise AppError(422, "VALIDATION", f"센 수량({body.counted_qty})이 재고({before})와 다름 — 사유(reason)가 필요함",
                               {"before_qty": before, "counted_qty": body.counted_qty})
            txn_id = db.scalar("inventory.stocktake", item_no=no, qty_change=diff, actor=actor.user_id,
                               memo=body.reason.strip(), fg_lot_no=None)
        out = {"item_no": no, "kind": "STOCKTAKE", "txn_id": txn_id, "before_qty": before,
               "counted_qty": body.counted_qty, "diff": diff}
    log_scan(db, actor, body.code, kind, no, body.kind, "OK", txn_id=out["txn_id"])
    db.scalar("inventory.check_stock", item_no=no, actor=actor.user_id)
    return out


class ShipCheckIn(BaseModel):
    code: str = Field(description="부품 꼬리표(로트)의 QR")


@router.post("/shipments/{shipment_no}/qr-check")
def ship_check(shipment_no: str, body: ShipCheckIn, actor: Actor = Depends(require("SHIPMENT", "EDIT")),
               db: Db = Depends(get_db)):
    """출하 전 확인 (출하 등록 3단계): 내보낼 로트 꼬리표를 찍어 출하 줄과 맞는지 본다. 작성 중(DRAFT) 출하만.
    맞으면 ok=true, 출하 줄에 없는 로트면 ok=false·MISMATCH (찍은 기록은 남김). 남은 로트(unchecked)를 함께 돌려준다"""
    head = must(db.one("qr.ship_head", shipment_no=shipment_no), "출하")
    if head["status"] != "DRAFT":
        raise AppError(409, "INVALID_STATE", f"출하 {shipment_no}는 이미 확정됨 — 확인은 확정 전에", {"reason": "NOT_DRAFT"})
    kind, no = read_code(body.code)
    if kind != "LOT":
        result, detail = "MISMATCH", f"로트 QR이 아님 ({qr.KIND_KO[kind]})"
    elif db.one("qr.ship_has_lot", shipment_no=shipment_no, lot_no=no) is None:
        result, detail = "MISMATCH", "출하 줄에 없는 로트"
    else:
        result, detail = "OK", None
    log_scan(db, actor, body.code, kind, no, "SHIP_CHECK", result, shipment_no=shipment_no, detail=detail)
    left = db.one("qr.ship_unchecked", shipment_no=shipment_no)
    return {"shipment_no": shipment_no, "lot_no": no, "ok": result == "OK", "result": result, "message": detail,
            "unchecked": [x for x in (left["unchecked"] or "").split(",") if x], "total": int(left["total"])}


@router.get("/qr/scans")
def scans(shipment_no: str | None = None, ref_no: str | None = None,
          purpose: str | None = Query(None, pattern="^(LOOKUP|RECEIPT|STOCKTAKE|SHIP_CHECK|MEASURE_START)$"),
          limit: int = Query(100, le=500), _: Actor = Depends(require("INVENTORY", "VIEW")), db: Db = Depends(get_db)):
    """찍은 기록 (최근 순): 누가·언제·무엇을·결과. 비서가 "이 로트 출하 전에 확인했어?"에 답할 때도 씀"""
    return db.all("qr.scans", shipment_no=shipment_no, ref_no=ref_no, purpose=purpose, limit=limit)
