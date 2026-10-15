-- 재고·출하·공구 (INV-01, ML-01)

-- 재고 13품목 (INV-01): 재고·안전 재고·관리 역할·부족 여부. 완제품 줄에는 보류 수량 —
-- 판정 대기·보류 검토·보류 로트의 완료 수량은 재고에 넣지 않고 따로 센다 (DOC-07 4.3)
-- name: items
SELECT v.item_no, v.category, v.item_name, v.unit, v.owner_role, v.safety_stock, v.on_hand_qty, v.is_low, v.stock_ratio,
       v.product_note,
       CASE WHEN v.category = 'FINISHED' THEN
            (SELECT coalesce(sum(l.completed_qty), 0) FROM v_production_lot l
              WHERE l.status IN ('WAIT_JUDGEMENT','HOLD_REVIEW','ON_HOLD'))::int END AS held_qty
  FROM v_inventory_status v ORDER BY v.category, v.item_no;

-- name: txns
SELECT t.txn_id, t.item_no, t.txn_type, t.qty_change, t.txn_at, t.txn_by, t.source_kind, t.work_record_no, t.pm_record_id,
       t.tool_change_id, t.lot_no, t.material_lot_no, t.fg_lot_no, t.shipment_no, t.ship_lot_no, t.memo,
       sum(t.qty_change) OVER (ORDER BY t.txn_at, t.txn_id) AS balance
  FROM inventory_txn t WHERE t.item_no = :item_no ORDER BY t.txn_at DESC, t.txn_id DESC LIMIT CAST(:limit AS int);

-- name: receipt
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, memo)
VALUES (:item_no, 'IN', :qty, app_now(), :actor, 'RECEIPT', CAST(:memo AS text)) RETURNING txn_id;

-- name: stocktake
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, fg_lot_no, memo)
VALUES (:item_no, 'ADJUST', :qty_change, app_now(), :actor, 'STOCKTAKE', CAST(:fg_lot_no AS text), :memo) RETURNING txn_id;

-- name: check_stock
SELECT fn_check_stock(:item_no, :actor);

-- name: safety_stock
UPDATE inventory_item SET safety_stock = :safety_stock, safety_stock_set_by = :actor, safety_stock_set_at = app_now()
 WHERE item_no = :item_no AND category <> 'FINISHED';

-- 원자재 입고 (SUP): 원자재 로트 + 입고 거래. 입고 검사 대기에서 시작 (6.9)
-- name: material_receipt
WITH lot AS (
    INSERT INTO raw_material_lot (material_lot_no, item_no, received_date, received_qty, supplier_cert_no, heat_batch_no, status)
    VALUES (fn_next_doc_no('MAT', app_now(), 2), :item_no, CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date), :qty,
            :supplier_cert_no, CAST(:heat_batch_no AS text), 'WAIT_RECEIPT_CHECK')
    RETURNING material_lot_no, item_no, received_qty),
t AS (
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, material_lot_no)
    SELECT item_no, 'IN', received_qty, app_now(), :actor, 'MATERIAL_RECEIPT', material_lot_no FROM lot RETURNING 1)
SELECT material_lot_no FROM lot;

-- name: material_check
UPDATE raw_material_lot SET status = :status WHERE material_lot_no = :material_lot_no AND status = 'WAIT_RECEIPT_CHECK';

-- name: shipments
SELECT shipment_no, shipped_at, customer_code, due_date, confirmed_by, status, fifo_skip_reason, memo, current_version,
       is_late, total_qty, line_count, basis_order_nos
  FROM v_shipment
 WHERE (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
 ORDER BY coalesce(shipped_at, due_date::timestamptz) DESC LIMIT CAST(:limit AS int);

-- name: shipment
SELECT * FROM v_shipment WHERE shipment_no = :shipment_no;

-- qr_checked_at: 출하 전에 그 로트 QR을 찍어 맞다고 확인한 시각 (qr_scan, 2026-10-13 QR 가정 [제안]). 안 찍었으면 비어 있음
-- name: shipment_lines
SELECT sl.lot_no, sl.qty, sl.lot_passed_at, l.order_no, l.status AS lot_status,
       (SELECT max(q.scanned_at) FROM qr_scan q WHERE q.purpose = 'SHIP_CHECK' AND q.result = 'OK'
           AND q.shipment_no = sl.shipment_no AND q.ref_no = sl.lot_no) AS qr_checked_at
  FROM shipment_line sl JOIN production_lot l USING (lot_no)
 WHERE sl.shipment_no = :shipment_no ORDER BY sl.lot_passed_at, sl.lot_no;

-- 출하할 수 있는 로트 (합격·해제, 남은 완제품 > 0) — FIFO 순서 (R-67·R-68). 화면 목록에도 이것만 나온다
-- name: shipment_candidates
SELECT l.lot_no, l.order_no, l.due_at, l.passed_at, l.fg_remaining_qty,
       row_number() OVER (ORDER BY (l.passed_at AT TIME ZONE 'Asia/Seoul')::date, l.lot_no) AS fifo_rank
  FROM v_production_lot l
 WHERE l.status IN ('PASSED','RELEASED') AND l.fg_remaining_qty > 0
 ORDER BY fifo_rank;

-- name: shipment_create
INSERT INTO shipment (shipment_no, customer_code, due_date, memo)
VALUES (fn_next_doc_no('SHP', app_now()), :customer_code, :due_date, CAST(:memo AS text)) RETURNING shipment_no;

-- name: shipment_line_set
INSERT INTO shipment_line (shipment_no, lot_no, qty, lot_passed_at)
SELECT :shipment_no, l.lot_no, :qty, l.passed_at FROM v_production_lot l
 WHERE l.lot_no = :lot_no AND l.passed_at IS NOT NULL
ON CONFLICT (shipment_no, lot_no) DO UPDATE SET qty = EXCLUDED.qty;

-- name: shipment_line_delete
DELETE FROM shipment_line sl USING shipment s
 WHERE sl.shipment_no = s.shipment_no AND s.status = 'DRAFT' AND sl.shipment_no = :shipment_no AND sl.lot_no = :lot_no;

-- name: shipment_confirm
SELECT fn_confirm_shipment(:shipment_no, :actor, CAST(:fifo_skip_reason AS text)) AS lines;

-- name: tools
SELECT tool_id, equipment_id, tool_no, item_no, item_name, tool_role, cum_usage, usage_unit, usage_per_part, life_limit,
       usage_rate_pct, remaining_pct, parts_left, last_changed_at
  FROM v_tool_life WHERE (CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text))
 ORDER BY usage_rate_pct DESC;

-- name: tool_changes
SELECT tool_change_id, tool_id, changed_at, changed_by, cum_before, change_reason, related_alarm_event_id
  FROM tool_change WHERE tool_id = :tool_id ORDER BY changed_at DESC LIMIT 50;

-- name: tool_change
SELECT fn_tool_change(:tool_id, :actor, :reason, CAST(:alarm_event_id AS bigint)) AS tool_change_id;


-- 품목 관리 역할·종류 (서버가 OWNED_ITEMS 범위를 먼저 확인 — DB R-77이 한 번 더)
-- name: item_meta
SELECT item_no, category, owner_role FROM inventory_item WHERE item_no = :item_no;
