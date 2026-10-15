"""재고·원자재·출하·공구 (INV-01, ML-01, 6.9·6.25·6.27 — API명세서 INV-01~05, TOOL-01·02).
재고 수량은 거래(inventory_txn)를 더해 DB 트리거가 맞춘다 — 직접 고치지 않는다. 품목별 관리 역할만 입고·조정 (R-77, DB 확인).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import Db, get_db
from ..errors import AppError
from ..security import Actor, require
from ..services import documents
from .common import changed, must

router = APIRouter(prefix="/api", tags=["재고·출하·공구"])

CATEGORY_KO = {"TOOL": "공구", "CONSUMABLE": "정비 소모품", "MATERIAL": "원자재", "FINISHED": "완제품"}


def owned_item(db: Db, actor: Actor, item_no: str) -> dict:
    """범위 OWNED_ITEMS: 그 품목의 관리 역할만 입고·실사 (기획서 13.2, INV-02 — 소모품 MNT / 공구·원자재·완제품 SUP).
    여기서 403 FORBIDDEN으로 먼저 막고, DB(R-77 inventory_txn_check)가 한 번 더 막는다."""
    item = must(db.one("inventory.item_meta", item_no=item_no), "재고 품목")
    if actor.scope == "OWNED_ITEMS" and item["owner_role"] != actor.role:
        raise AppError(403, "FORBIDDEN", f"{actor.role}는 {CATEGORY_KO.get(item['category'], item['category'])} "
                                         f"{item_no}의 입고·실사를 할 수 없음 (관리 역할 {item['owner_role']})",
                       {"reason": "NOT_ITEM_OWNER", "owner_role": item["owner_role"]})
    return item


@router.get("/inventory")
def items(_: Actor = Depends(require("INVENTORY", "VIEW")), db: Db = Depends(get_db)):
    """재고 13품목 (INV-01): 재고·안전 재고·관리 역할·부족 여부, 완제품·보류 수량"""
    return db.all("inventory.items")


@router.get("/inventory/{item_no}/txns")
def txns(item_no: str, limit: int = Query(100, le=1000), _: Actor = Depends(require("INVENTORY", "VIEW")),
         db: Db = Depends(get_db)):
    """품목 1개의 거래 내역 (잔량 누계)"""
    return db.all("inventory.txns", item_no=item_no, limit=limit)


class TxnIn(BaseModel):
    item_no: str
    kind: str = Field(pattern="^(RECEIPT|ADJUST)$", description="RECEIPT 입고 / ADJUST 실사 조정")
    qty: Decimal = Field(description="입고는 양수, 실사 조정은 차이(+/-)")
    reason: str | None = Field(None, description="실사 조정은 필수")
    fg_lot_no: str | None = Field(None, description="완제품 실사 조정은 로트")


@router.post("/inventory/txns")
def txn(body: TxnIn, actor: Actor = Depends(require("INV_RECEIPT", "INPUT")), db: Db = Depends(get_db)):
    """입고 · 실사 조정 (INV-02): 그 품목 관리 역할만 (소모품 MNT / 공구·원자재·완제품 SUP — R-77, DB 확인).
    재고 부족 알림은 다시 확인해 자동 처리 (R-39). 거래 기록을 돌려준다"""
    owned_item(db, actor, body.item_no)
    if body.kind == "RECEIPT":
        if body.qty <= 0:
            raise AppError(422, "VALIDATION", "입고 수량은 0보다 커야 함")
        txn_id = db.scalar("inventory.receipt", item_no=body.item_no, qty=body.qty, actor=actor.user_id, memo=body.reason)
    else:
        if not (body.reason or "").strip():
            raise AppError(422, "VALIDATION", "실사 조정은 사유(reason)가 필요함")
        txn_id = db.scalar("inventory.stocktake", item_no=body.item_no, qty_change=body.qty, actor=actor.user_id,
                           memo=body.reason, fg_lot_no=body.fg_lot_no)
    db.scalar("inventory.check_stock", item_no=body.item_no, actor=actor.user_id)
    return {"txn_id": txn_id, "item_no": body.item_no, "kind": body.kind}


class SafetyIn(BaseModel):
    safety_stock: Decimal = Field(ge=0)


@router.patch("/inventory/items/{item_no}/safety-stock")
def safety_stock(item_no: str, body: SafetyIn, actor: Actor = Depends(require("SAFETY_STOCK", "SETTING")),
                 db: Db = Depends(get_db)):
    """안전 재고 설정 (INV-05, MGR). 완제품은 대상 아님"""
    changed(db.exec("inventory.safety_stock", item_no=item_no, safety_stock=body.safety_stock, actor=actor.user_id),
            "안전 재고 (완제품은 대상 아님)")
    db.scalar("inventory.check_stock", item_no=item_no, actor=actor.user_id)
    return {"ok": True}


# ---------------- 원자재 로트 (INV-03) ----------------
class MaterialIn(BaseModel):
    item_no: str
    qty: Decimal = Field(gt=0)
    supplier_cert_no: str
    heat_batch_no: str | None = None


@router.post("/raw-lots")
def material_receipt(body: MaterialIn, actor: Actor = Depends(require("INV_RECEIPT", "INPUT")), db: Db = Depends(get_db)):
    """원자재 입고 → 원자재 로트(입고 검사 대기) + 입고 거래. 원자재 품목만, 관리 역할(SUP)만 (13.2)"""
    item = owned_item(db, actor, body.item_no)
    if item["category"] != "MATERIAL":
        raise AppError(422, "VALIDATION", f"{body.item_no}은 원자재가 아님 ({CATEGORY_KO.get(item['category'])})")
    return {"material_lot_no": db.scalar("inventory.material_receipt", actor=actor.user_id, **body.model_dump())}


class MaterialInspectIn(BaseModel):
    result: str = Field(pattern="^(AVAILABLE|RECEIPT_HOLD)$", description="사용 가능 / 입고 보류 (성적서 대조 결과)")


@router.post("/raw-lots/{material_lot_no}/inspect")
def material_inspect(material_lot_no: str, body: MaterialInspectIn, _: Actor = Depends(require("MATERIAL_CHECK", "INPUT")),
                     db: Db = Depends(get_db)):
    """원자재 입고 검사 (INV-03, SUP — 성적서 대조) → 사용 가능 / 입고 보류"""
    changed(db.exec("inventory.material_check", material_lot_no=material_lot_no, status=body.result), "입고 검사")
    return {"material_lot_no": material_lot_no, "status": body.result}


# ---------------- 출하 (INV-04) ----------------
def ship_qr_gate(db: Db, shipment_no: str) -> None:
    """[제안] MOM_QR_SHIP_CHECK_REQUIRED=true면 출하 줄의 로트 QR을 모두 찍어야 확정 (POST /api/shipments/{no}/qr-check)"""
    if not get_settings().qr_ship_check_required:
        return
    left = [x for x in (db.scalar("qr.ship_unchecked_list", shipment_no=shipment_no) or "").split(",") if x]
    if left:
        raise AppError(409, "INVALID_STATE", f"출하 전 QR 확인 안 한 로트: {', '.join(left)}",
                       {"reason": "QR_NOT_CHECKED", "lots": left})


@router.get("/shipments")
def shipments(status: str | None = None, limit: int = Query(100, le=500), _: Actor = Depends(require("SHIPMENT", "VIEW")),
              db: Db = Depends(get_db)):
    """출하 목록 (INV-04)"""
    return db.all("inventory.shipments", status=status, limit=limit)


@router.get("/shipments/candidates")
def candidates(_: Actor = Depends(require("SHIPMENT", "VIEW")), db: Db = Depends(get_db)):
    """출하할 수 있는 로트 (합격·해제, 남은 완제품 있음) — 먼저 합격한 순 (FIFO 제안, R-67)"""
    return db.all("inventory.shipment_candidates")


@router.get("/shipments/{shipment_no}")
def shipment(shipment_no: str, _: Actor = Depends(require("SHIPMENT", "VIEW")), db: Db = Depends(get_db)):
    """출하 1건 + 줄"""
    s = must(db.one("inventory.shipment", shipment_no=shipment_no), "출하")
    s["lines"] = db.all("inventory.shipment_lines", shipment_no=shipment_no)
    return s


class ShipLineIn(BaseModel):
    lot_no: str
    qty: int = Field(gt=0)


class ShipmentIn(BaseModel):
    customer_code: str
    due_date: date
    memo: str | None = None
    lines: list[ShipLineIn] = []
    confirm: bool = False                 # true면 줄을 넣고 바로 확정 (FIFO·남은 수량 확인 → 완제품 재고 차감)
    fifo_skip_reason: str | None = Field(None, description="먼저 합격한 로트를 건너뛸 때 사유 (R-68)")


@router.post("/shipments")
def shipment_create(body: ShipmentIn, actor: Actor = Depends(require("SHIPMENT", "CREATE")), db: Db = Depends(get_db)):
    """출하 등록 (INV-04, SUP): 출하처·로트·수량 (합격·해제 로트만 — 보류 로트면 INVALID_STATE). confirm이면 확정까지.
    출하 번호를 돌려준다"""
    if body.confirm and not body.lines:
        raise AppError(422, "VALIDATION", "확정하려면 로트 줄이 필요함")
    no = db.scalar("inventory.shipment_create", customer_code=body.customer_code, due_date=body.due_date, memo=body.memo)
    for ln in body.lines:
        changed(db.exec("inventory.shipment_line_set", shipment_no=no, lot_no=ln.lot_no, qty=ln.qty),
                f"출하 줄 {ln.lot_no} (합격한 로트만)")
    if body.confirm:
        ship_qr_gate(db, no)
        db.scalar("inventory.shipment_confirm", shipment_no=no, actor=actor.user_id, fifo_skip_reason=body.fifo_skip_reason)
    return {"shipment_no": no, "status": "CONFIRMED" if body.confirm else "DRAFT"}


class LineIn(BaseModel):
    qty: int = Field(gt=0)


@router.put("/shipments/{shipment_no}/lines/{lot_no}")
def line_set(shipment_no: str, lot_no: str, body: LineIn, _: Actor = Depends(require("SHIPMENT", "EDIT")),
             db: Db = Depends(get_db)):
    """출하 줄 넣기·수량 바꾸기 (초안, 합격한 로트만)"""
    return changed(db.exec("inventory.shipment_line_set", shipment_no=shipment_no, lot_no=lot_no, qty=body.qty),
                   "출하 줄 (합격한 로트만)")


@router.delete("/shipments/{shipment_no}/lines/{lot_no}")
def line_delete(shipment_no: str, lot_no: str, _: Actor = Depends(require("SHIPMENT", "EDIT")), db: Db = Depends(get_db)):
    """출하 줄 빼기 (초안만)"""
    return changed(db.exec("inventory.shipment_line_delete", shipment_no=shipment_no, lot_no=lot_no), "출하 줄 삭제 (초안만)")


class ConfirmShipmentIn(BaseModel):
    fifo_skip_reason: str | None = Field(None, description="먼저 합격한 로트를 건너뛸 때 사유 (R-68)")


@router.post("/shipments/{shipment_no}/confirm")
def shipment_confirm(shipment_no: str, body: ConfirmShipmentIn, actor: Actor = Depends(require("SHIPMENT", "CONFIRM")),
                     db: Db = Depends(get_db)):
    """출하 확정 (SUP): FIFO·남은 수량 확인 → 완제품 재고 차감 → 잠금. QR 확인 필수 설정이면 안 찍은 로트가 없어야 함"""
    ship_qr_gate(db, shipment_no)
    return {"lines": db.scalar("inventory.shipment_confirm", shipment_no=shipment_no, actor=actor.user_id,
                               fifo_skip_reason=body.fifo_skip_reason)}


class EditIn(BaseModel):
    changes: dict
    reason: str | None = None
    version: int | None = None


@router.patch("/shipments/{shipment_no}")
def shipment_edit(shipment_no: str, body: EditIn, actor: Actor = Depends(require("SHIPMENT", "EDIT")),
                  db: Db = Depends(get_db)):
    """출하 고치기 = 새 버전 (INV-04 확정 후 수정 — reason 필수)"""
    return {"version_no": documents.edit_shipment(db, shipment_no, actor.user_id, body.changes, body.reason, body.version)}


# ---------------- 공구 (TOOL-01·02) ----------------
@router.get("/tools")
def tools(equipment_id: str | None = None, _: Actor = Depends(require("TOOL_LIFE", "VIEW")), db: Db = Depends(get_db)):
    """공구 수명 (TOOL-01): 사용률·단위·한도·남은 부품 수"""
    return db.all("inventory.tools", equipment_id=equipment_id)


@router.get("/tools/{tool_id}/changes")
def tool_changes(tool_id: str, _: Actor = Depends(require("TOOL_LIFE", "VIEW")), db: Db = Depends(get_db)):
    """공구 교체 내역"""
    return db.all("inventory.tool_changes", tool_id=tool_id)


class ToolChangeIn(BaseModel):
    reason: str = Field(pattern="^(LIFE_90|ALARM_362|ALARM_174|BROKEN|OTHER)$", description="교체 사유 코드")
    alarm_event_id: int | None = None


@router.post("/tools/{tool_id}/change")
def tool_change(tool_id: str, body: ToolChangeIn, actor: Actor = Depends(require("TOOL_CHANGE", "INPUT")),
                db: Db = Depends(get_db)):
    """공구 교체 기록 (TOOL-02): 사용량 0 + 재고 차감 + 수명 알림 자동 처리"""
    return {"tool_change_id": db.scalar("inventory.tool_change", tool_id=tool_id, actor=actor.user_id, reason=body.reason,
                                        alarm_event_id=body.alarm_event_id)}
