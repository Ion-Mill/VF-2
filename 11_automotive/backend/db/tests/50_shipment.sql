-- 출하 (R-67 합격 로트만, R-68 FIFO, 출하 출고 거래, R-35 확정 잠금)
BEGIN;
-- 두 로트를 합격시킨다: 038-1 (9/15 09:00), 040-1 (9/15 16:30) — 같은 날이면 로트 번호 순
SELECT fn_lot_pass('LOT-2609-038-1', '2026-09-15 09:00+09');
SELECT fn_lot_pass('LOT-2609-040-1', '2026-09-15 16:30+09');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'FG-BRK-A100'), 72.000::numeric, '완제품 36 + 36');
SELECT t.freeze('2026-09-16 14:00+09');

-- R-67 합격 안 된 로트는 출하 불가
INSERT INTO shipment (shipment_no, customer_code, due_date) VALUES ('SHP-2609-001', 'CUST-01', '2026-09-16');
INSERT INTO shipment_line (shipment_no, lot_no, qty, lot_passed_at) VALUES ('SHP-2609-001', 'LOT-2609-041-1', 10, '2026-09-15 00:00+09');
SELECT t.throws($$SELECT fn_confirm_shipment('SHP-2609-001', 'U10')$$, 'R-67', 'R-67 생산 중 로트는 출하 불가');
DELETE FROM shipment_line WHERE shipment_no = 'SHP-2609-001';

-- R-68 먼저 합격한 038-1을 두고 040-1만 고르면 사유 필수
INSERT INTO shipment_line (shipment_no, lot_no, qty, lot_passed_at) VALUES ('SHP-2609-001', 'LOT-2609-040-1', 36, '2026-09-15 16:30+09');
SELECT t.throws($$SELECT fn_confirm_shipment('SHP-2609-001', 'U10')$$, 'R-68', 'R-68 FIFO 건너뛰면 사유 필수');
SELECT t.throws($$SELECT fn_confirm_shipment('SHP-2609-001', 'U07', 'x')$$, 'SUP', '출하 확정은 SUP만');
-- 남은 수량보다 많이 내보낼 수 없음
UPDATE shipment_line SET qty = 37 WHERE shipment_no = 'SHP-2609-001';
SELECT t.throws($$SELECT fn_confirm_shipment('SHP-2609-001', 'U10', '고객 요청 로트')$$, '남은 완제품', '남은 수량 초과 불가');
UPDATE shipment_line SET qty = 36 WHERE shipment_no = 'SHP-2609-001';
SELECT t.eq(fn_confirm_shipment('SHP-2609-001', 'U10', '고객 요청 로트'), 1, '사유를 적으면 확정');
SELECT t.eq((SELECT fifo_skip_reason FROM shipment WHERE shipment_no = 'SHP-2609-001'), '고객 요청 로트', 'FIFO 사유 저장');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'FG-BRK-A100'), 36.000::numeric, '출하 출고 36 차감');
SELECT t.eq((SELECT fg_remaining_qty FROM v_production_lot WHERE lot_no = 'LOT-2609-040-1'), 0, '040-1 남은 완제품 0');
SELECT t.eq((SELECT shipment_nos FROM v_production_lot WHERE lot_no = 'LOT-2609-040-1'), 'SHP-2609-001', '로트 추적에 출하 번호');
SELECT t.eq((SELECT total_qty || '/' || basis_order_nos FROM v_shipment WHERE shipment_no = 'SHP-2609-001'), '36/PO-2609-040', '출하 합계·근거 작업지시');
SELECT t.ok(NOT (SELECT is_late FROM shipment WHERE shipment_no = 'SHP-2609-001'), '납기일 출하 → 늦지 않음');

-- 두 번째 출하: 038-1 (FIFO 순서대로라 사유 없이 확정)
INSERT INTO shipment (shipment_no, customer_code, due_date) VALUES ('SHP-2609-002', 'CUST-01', '2026-09-15');
INSERT INTO shipment_line VALUES ('SHP-2609-002', 'LOT-2609-038-1', 36, '2026-09-15 09:00+09');
SELECT t.eq(fn_confirm_shipment('SHP-2609-002', 'U10'), 1, 'FIFO 순서면 사유 없이 확정');
SELECT t.ok((SELECT is_late FROM shipment WHERE shipment_no = 'SHP-2609-002'), '납기 9/15 → 9/16 출하는 늦음 표시');

-- 출하한 로트는 보류할 수 없음 (6.8)
SELECT t.throws($$SELECT fn_lot_hold('LOT-2609-038-1', 'U10', 'SUPERVISOR', '확인')$$, '출하한 로트', '출하한 로트 보류 불가');
-- 확정된 출하는 직접 못 고침 (R-35, SHIPMENT 7번째 문서)
SELECT t.throws($$UPDATE shipment SET memo = '고침' WHERE shipment_no = 'SHP-2609-001'$$, 'R-35', '확정 출하 직접 수정 불가');
SELECT t.throws($$SELECT fn_confirm_shipment('SHP-2609-001', 'U10')$$, '작성 중이 아님', '두 번 확정 불가');
ROLLBACK;
