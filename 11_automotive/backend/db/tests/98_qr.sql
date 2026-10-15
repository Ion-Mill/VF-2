-- QR 찍은 기록 (90_physical_extras qr_scan + 86_qr, 2026-10-13 가정 "재고·로트는 QR로 관리" [제안])
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result)
VALUES (app_now(), 'U10', 'MOM:ITEM:TL-EM10', 'ITEM', 'TL-EM10', 'LOOKUP', 'OK');
-- 추가만 한다
SELECT t.throws($$UPDATE qr_scan SET result = 'MISMATCH'$$, '추가만', '찍은 기록은 고칠 수 없음');
SELECT t.throws($$DELETE FROM qr_scan$$, '추가만', '찍은 기록은 지울 수 없음');
-- 못 찍었으면(MANUAL) 사유 필수, 찍었으면 글자 필수
SELECT t.throws($$INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result, instruction_id)
                  VALUES (app_now(), 'U03', NULL, 'NONE', NULL, 'MEASURE_START', 'MANUAL', 2)$$,
                'ck_qr_scan_manual', '수동 확인은 사유 필수');
SELECT t.throws($$INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result)
                  VALUES (app_now(), 'U10', NULL, 'LOT', 'LOT-2609-038-1', 'LOOKUP', 'OK')$$,
                'ck_qr_scan_manual', '찍은 기록은 글자 필수');
SELECT t.throws($$INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result)
                  VALUES (app_now(), 'U10', 'LOT-2609-038-1', 'LOT', 'LOT-2609-038-1', 'SHIP_CHECK', 'OK')$$,
                'ck_qr_scan_ship', '출하 확인은 출하 번호 필수');
-- 출하 줄마다 QR 확인 여부: 안 찍은 로트 → 찍은 뒤 빈 목록. 다른 로트·MISMATCH는 확인으로 치지 않음
SELECT fn_lot_pass('LOT-2609-038-1', '2026-09-15 09:00+09');
INSERT INTO shipment (shipment_no, customer_code, due_date) VALUES ('SHP-2609-901', 'CUST-01', '2026-09-16');
INSERT INTO shipment_line (shipment_no, lot_no, qty, lot_passed_at)
SELECT 'SHP-2609-901', lot_no, 1, passed_at FROM v_production_lot WHERE lot_no = 'LOT-2609-038-1';
SELECT t.eq(fn_ship_qr_unchecked('SHP-2609-901'), ARRAY['LOT-2609-038-1'], '찍기 전: 038-1 안 찍음');
INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result, shipment_no, detail)
VALUES (app_now(), 'U10', 'LOT-2609-040-1', 'LOT', 'LOT-2609-040-1', 'SHIP_CHECK', 'MISMATCH', 'SHP-2609-901', '출하 줄에 없는 로트');
SELECT t.eq(fn_ship_qr_unchecked('SHP-2609-901'), ARRAY['LOT-2609-038-1'], '다른 로트를 찍어도 확인 안 됨');
INSERT INTO qr_scan (scanned_at, user_id, raw_code, code_kind, ref_no, purpose, result, shipment_no)
VALUES (app_now(), 'U10', 'MOM:LOT:LOT-2609-038-1', 'LOT', 'LOT-2609-038-1', 'SHIP_CHECK', 'OK', 'SHP-2609-901');
SELECT t.eq(fn_ship_qr_unchecked('SHP-2609-901'), '{}'::text[], '찍은 뒤: 남은 로트 없음');
ROLLBACK;
