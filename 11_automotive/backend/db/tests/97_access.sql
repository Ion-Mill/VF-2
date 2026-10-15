-- 역할별 권한을 DB에서도 지키는지 (85_access + 20_integrity, 기획서 13.1·13.2)
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
-- 원자재 로트는 원자재 품목만 (MNT가 자기 관리 품목을 원자재 로트로 등록하던 틈)
SELECT t.throws($$INSERT INTO raw_material_lot (material_lot_no, item_no, received_date, received_qty, supplier_cert_no)
                  VALUES ('MAT-2609-90', 'CS-WLUB', '2026-09-15', 10, 'X')$$, '원자재 품목만', '소모품을 원자재 로트로 등록 불가');
INSERT INTO raw_material_lot (material_lot_no, item_no, received_date, received_qty, supplier_cert_no)
VALUES ('MAT-2609-91', 'RM-6061', '2026-09-15', 10, 'CERT-1');
SELECT t.ok(EXISTS (SELECT 1 FROM raw_material_lot WHERE material_lot_no = 'MAT-2609-91'), '원자재(RM-6061)는 등록됨');
-- 입고 거래는 품목 관리 역할만 (R-77): MNT = 정비 소모품 / SUP = 공구·원자재·완제품 / OPR = 없음
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, material_lot_no)
                  VALUES ('RM-6061', 'IN', 10, app_now(), 'U07', 'MATERIAL_RECEIPT', 'MAT-2609-91')$$, 'R-77', 'MNT는 원자재 입고 불가');
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind)
                  VALUES ('CS-WLUB', 'IN', 1, app_now(), 'U10', 'RECEIPT')$$, 'R-77', 'SUP는 정비 소모품 입고 불가');
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind)
                  VALUES ('TL-TAP6', 'IN', 1, app_now(), 'U02', 'RECEIPT')$$, 'R-77', 'OPR는 입고 불가');
-- 작업지시서 승인: SUP·MGR만, MGR이면 대리 승인으로 보임 (13.1 "승인(대리)")
SELECT t.eq((SELECT approved_as_proxy FROM v_work_order WHERE wo_no = 'MW-0901'), false, '반장 승인 = 대리 아님');
CREATE TEMP TABLE wo AS SELECT fn_create_work_order_draft('VF2-02', '대리 승인 시험', 'x', p_pm_record_id => 1,
                                                           p_author => 'U07') AS wo_no;
UPDATE maintenance_work_order SET assignee_user_id = 'U07' WHERE wo_no = (SELECT wo_no FROM wo);
SELECT t.throws($$UPDATE maintenance_work_order SET status = 'APPROVED', approved_by = 'U09', approved_at = app_now()
                  WHERE wo_no = (SELECT wo_no FROM wo)$$, 'SUP', 'MNT는 승인 불가');
UPDATE maintenance_work_order SET status = 'APPROVED', approved_by = 'U12', approved_at = app_now()
 WHERE wo_no = (SELECT wo_no FROM wo);
SELECT t.eq((SELECT approved_as_proxy FROM v_work_order WHERE wo_no = (SELECT wo_no FROM wo)), true, 'MGR 승인 = 대리 승인');
ROLLBACK;
