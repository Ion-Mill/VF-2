-- QR (2026-10-13 가정 "재고·로트는 QR로 관리" [제안]) — app/routers/qr.py
-- QR 안에는 번호만 있다. 찍으면 지금 상태를 여기서 읽는다.

-- name: lot_info
SELECT l.lot_no, l.order_no, l.status, l.input_qty, l.completed_qty, l.scrap_qty, l.material_lot_no, l.plan_mode,
       l.passed_at, l.shipped_qty, l.fg_remaining_qty,
       (SELECT h.hold_reason FROM lot_hold h WHERE h.lot_no = l.lot_no AND h.result = 'IN_PROGRESS' ORDER BY h.held_at DESC LIMIT 1)
           AS open_hold_reason
  FROM v_production_lot l WHERE l.lot_no = :no;

-- name: mat_info
SELECT m.material_lot_no, m.item_no, i.item_name, m.status, m.received_date, m.received_qty, m.supplier_cert_no,
       m.heat_batch_no,
       coalesce((SELECT sum(p.input_qty) FROM production_lot p WHERE p.material_lot_no = m.material_lot_no), 0)::int AS used_qty
  FROM raw_material_lot m JOIN inventory_item i USING (item_no)
 WHERE m.material_lot_no = :no;

-- name: item_info
SELECT item_no, category, item_name, unit, owner_role, safety_stock, on_hand_qty, is_low, stock_ratio
  FROM v_inventory_status WHERE item_no = :no;

-- name: scan_log
INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result, shipment_no, instruction_id, txn_id,
                     detail)
VALUES (app_now(), :actor, CAST(:raw_code AS text), :code_kind, CAST(:ref_no AS text), :purpose, :result,
        CAST(:shipment_no AS text), CAST(:instruction_id AS bigint), CAST(:txn_id AS bigint), CAST(:detail AS text))
RETURNING scan_id;

-- 실사: 지금 재고를 잠그고 읽는다 (같은 품목을 동시에 두 번 세어 조정이 겹치지 않게). 차이만큼 inventory.stocktake
-- name: item_lock
SELECT on_hand_qty FROM inventory_item WHERE item_no = :item_no FOR UPDATE;

-- name: ship_head
SELECT shipment_no, status FROM shipment WHERE shipment_no = :shipment_no;

-- name: ship_has_lot
SELECT qty FROM shipment_line WHERE shipment_no = :shipment_no AND lot_no = :lot_no;

-- name: ship_unchecked
SELECT array_to_string(fn_ship_qr_unchecked(:shipment_no), ',') AS unchecked,
       (SELECT count(*) FROM shipment_line WHERE shipment_no = :shipment_no)::int AS total;

-- 찍은 기록 (최근 순) — 출하 번호·번호(로트·품목)·목적으로 거름
-- name: scans
SELECT q.scan_id, q.scanned_at, q.user_id, u.user_name, q.raw_code, q.code_kind, q.ref_no, q.purpose, q.result,
       q.shipment_no, q.instruction_id, q.txn_id, q.detail
  FROM qr_scan q JOIN app_user u USING (user_id)
 WHERE (CAST(:shipment_no AS text) IS NULL OR q.shipment_no = :shipment_no)
   AND (CAST(:ref_no AS text) IS NULL OR q.ref_no = :ref_no)
   AND (CAST(:purpose AS text) IS NULL OR q.purpose = :purpose)
 ORDER BY q.scanned_at DESC, q.scan_id DESC
 LIMIT CAST(:limit AS int);

-- name: ship_unchecked_list
SELECT array_to_string(fn_ship_qr_unchecked(:shipment_no), ',');
