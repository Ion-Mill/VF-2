-- 한 행·여러 표 규칙이 실제로 막는지 (R-01·R-04·R-06a·R-11·R-13·R-19·R-21·R-22·R-24·R-24a·R-35·R-36·R-38·R-55·R-77·R-81)
BEGIN;

-- R-04 같은 설비 상태 구간 겹침
SELECT t.throws($$INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, end_at)
                  VALUES ('VF2-02', 'IDLE', 'READY', '2026-09-15 09:00+09', '2026-09-15 09:10+09')$$,
                'ex_state_no_overlap', 'R-04 상태 구간 겹침 금지');
-- 겹치지 않으면 들어간다 (다른 설비)
INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, end_at)
VALUES ('SAW-01', 'IDLE', 'READY', '2026-09-15 09:00+09', '2026-09-15 09:10+09');
SELECT t.ok(true, 'R-04 다른 설비는 같은 시각 가능');

-- R-01 DOWN은 알람 필수, R-22 정지 등급만
SELECT t.throws($$INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, end_at)
                  VALUES ('SAW-01', 'DOWN', 'STOPPED', '2026-09-15 07:00+09', '2026-09-15 07:10+09')$$,
                'ck_state_down_alarm', 'R-01 DOWN 구간은 알람 필수');
SELECT t.throws($$INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, end_at, alarm_event_id)
                  VALUES ('VF2-01', 'DOWN', 'STOPPED', '2026-09-15 07:00+09', '2026-09-15 07:10+09', 1)$$,
                'R-22', 'R-22 주의 등급 알람으로 DOWN 불가');
-- R-21 RUN이면 사유 없음 / 확정은 SUP만
SELECT t.throws($$INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, end_at, reason_code, reason_status)
                  VALUES ('SAW-01', 'RUN', 'ACTIVE', '2026-09-15 07:00+09', '2026-09-15 07:10+09', 'M01', 'ENTERED')$$,
                'ck_state_run_reason', 'R-21 RUN 구간은 정지 사유를 비움');
SELECT t.throws($$UPDATE equipment_state_log SET reason_status = 'CONFIRMED', reason_confirmed_by = 'U02',
                       reason_confirmed_at = '2026-09-15 12:00+09' WHERE alarm_event_id = 3$$,
                'SUP', 'R-21 정지 사유 확정은 SUP만');

-- R-19 생산 수량 = 양품 + 재작업 + 불량, 공정의 설비여야 함
SELECT t.throws($$INSERT INTO operation_report (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, pq, gq, rq, sq)
                  VALUES ('LOT-2609-041-1', 'OP-40', 'WSH-01', 'U03', '2026-09-15-D', '2026-09-15 13:00+09', 10, 9, 0, 0)$$,
                'ck_operation_report_qty', 'R-19 PQ = GQ + RQ + SQ');
SELECT t.throws($$INSERT INTO operation_report (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, pq, gq, rq, sq)
                  VALUES ('LOT-2609-041-1', 'OP-40', 'VF2-01', 'U03', '2026-09-15-D', '2026-09-15 13:00+09', 1, 1, 0, 0)$$,
                'fk_operation_report_equipment', '공정 실적의 설비는 그 공정 설비');

-- 업무 번호 형식: 로트 번호 = 작업지시 몸통 + 순번
SELECT t.throws($$INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty)
                  VALUES ('LOT-2609-041-3', 'PO-2609-041', 2, '2026-09-15-D', 'MAT-2609-05', 10)$$,
                'ck_production_lot_no', '로트 번호 형식');
-- R-06a 사용 가능이 아닌 원자재 로트는 투입 불가
INSERT INTO raw_material_lot (material_lot_no, item_no, received_date, received_qty, supplier_cert_no)
VALUES ('MAT-2609-06', 'RM-6061', '2026-09-15', 360, 'CERT-X');
SELECT t.throws($$INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty)
                  VALUES ('LOT-2609-041-2', 'PO-2609-041', 2, '2026-09-15-D', 'MAT-2609-06', 10)$$,
                'R-06a', 'R-06a 입고 검사 대기 원자재는 투입 불가');
-- R-24a 로트 상태 건너뛰기
SELECT t.throws($$UPDATE production_lot SET status = 'PASSED' WHERE lot_no = 'LOT-2609-041-1'$$,
                'R-24a', 'R-24a 생산 중 → 합격 직행 불가');

-- R-11 재고 음수 금지
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, memo)
                  VALUES ('CS-WLUB', 'ADJUST', -100, '2026-09-15 18:00+09', 'U07', 'STOCKTAKE', '실사 차이')$$,
                'R-11', 'R-11 재고가 음수가 되는 거래 막음');
-- R-77 입고 등록은 품목 관리 역할만 (공구 = SUP)
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind)
                  VALUES ('TL-TAP6', 'IN', 5, '2026-09-15 18:00+09', 'U07', 'RECEIPT')$$,
                'R-77', 'R-77 공구 입고는 SUP');
-- R-55 출처 칸이 맞아야 함
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, lot_no)
                  VALUES ('TL-TAP6', 'IN', 5, '2026-09-15 18:00+09', 'U10', 'RECEIPT', 'LOT-2609-041-1')$$,
                'ck_inventory_txn_source', 'R-55 입고 등록은 출처 FK 없음');
SELECT t.throws($$INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, memo)
                  VALUES ('TL-TAP6', 'ADJUST', 1, '2026-09-15 18:00+09', 'U10', 'STOCKTAKE', ' ')$$,
                'ck_inventory_txn_adjust_memo', '조정은 사유 필수');
-- 수불대장은 고칠 수 없음
SELECT t.throws($$UPDATE inventory_txn SET qty_change = 999 WHERE source_kind = 'RECEIPT'$$,
                '추가만', '입출고 거래는 추가만');
-- 정상 입고는 재고 수량에 더해진다
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'TL-TAP6'), 10.000::numeric, '입고 뒤 M6 탭 재고');

-- R-24 알람은 적용 공정 설비에서만
SELECT t.throws($$INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at)
                  VALUES ('SAW-01', '992', 'STOP', '2026-09-15 13:00+09')$$,
                'R-24', 'R-24 OP-30 알람이 OP-10 설비에서 날 수 없음');
-- R-13 재공 한도
SELECT t.throws($$INSERT INTO wip_log VALUES ('WIP-20-30', '2026-09-15 13:00+09', 31, NULL, 'MIN5')$$, 'R-13', 'R-13 재공 30 한도');
INSERT INTO wip_log VALUES ('WIP-30-40', '2026-09-15 13:00+09', 45, NULL, 'MIN5');
SELECT t.ok(true, 'R-13 WIP-30-40은 60까지');
SELECT t.throws($$INSERT INTO wip_log VALUES ('WIP-20-30', '2026-09-15 13:05+09', 5, 3, 'MIN5')$$, 'ck_wip_log_soak',
                '온도 맞춤 선반 수량은 WIP-40-50만');

-- R-02 작업지시서는 OP-30만, 계기 1개 이상
SELECT t.throws($$INSERT INTO maintenance_work_order (wo_no, pm_record_id, equipment_id, created_at, title, symptom,
                     safety_block_doc_rev, has_high_voltage_notice) VALUES ('MW-0909', 2, 'SAW-01', now(), 'x', 'x', 'DOC-05 Rev.1', false)$$,
                'R-02', 'R-02 작업지시서는 OP-30 설비만');
SELECT t.throws($$INSERT INTO maintenance_work_order (wo_no, equipment_id, created_at, title, symptom, safety_block_doc_rev,
                     has_high_voltage_notice) VALUES ('MW-0909', 'VF2-01', now(), 'x', 'x', 'DOC-05 Rev.1', true)$$,
                'ck_wo_trigger', '작업지시서 계기 1개 이상');
SELECT t.throws($$INSERT INTO maintenance_work_order (wo_no, alarm_event_id, equipment_id, created_at, title, symptom,
                     safety_block_doc_rev, has_high_voltage_notice) VALUES ('MW-0909', 1, 'VF2-01', now(), 'x', 'x', 'DOC-05 Rev.1', true)$$,
                'R-02', 'R-02 주의 등급 알람으로 작업지시서 불가');
SELECT t.throws($$UPDATE maintenance_work_order SET status = 'EDITING' WHERE wo_no = 'MW-0901'$$,
                '6.13', '작업지시서 상태 되돌리기 불가');

-- R-36 교대 보고서는 그 교대 반장만 확정
SELECT t.throws($$UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U11', confirmed_at = now()
                  WHERE shift_id = '2026-09-15-D'$$, 'R-36', 'R-36 다른 반장은 확정 불가');

-- R-81 측정 위치·판정용 값
SELECT t.throws($$INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                     instrument_id, inspector_id, measured_at, part_temp_c, input_method, entered_by, check_status, use_for_judgement)
                  VALUES ('LOT-2609-040-1', 1, 'BRK-A100', 1, 'FIRST', 'STD', 45.01, 'PASS', 'CMM-01', 'U03', now(), 20, 'MANUAL', 'U03', 'NEEDS_CHECK', true)$$,
                'inspection_result_position_check', '측정 위치 코드는 TOP·MID·BOTTOM (표준 = 빈칸, 2026-10-14)');
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
       instrument_id, inspector_id, measured_at, part_temp_c, input_method, entered_by, check_status, use_for_judgement)
VALUES ('LOT-2609-040-1', 1, 'BRK-A100', 1, 'FIRST', NULL, 45.010, 'PASS', 'CMM-01', 'U03', now(), 20, 'MANUAL', 'U03', 'NEEDS_CHECK', true);
SELECT t.throws($$INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                     instrument_id, inspector_id, measured_at, part_temp_c, input_method, entered_by, check_status, remeasure_seq, use_for_judgement)
                  VALUES ('LOT-2609-040-1', 1, 'BRK-A100', 1, 'FIRST', NULL, 45.011, 'PASS', 'CMM-01', 'U03', now(), 20, 'MANUAL', 'U03',
                          'NEEDS_CHECK', 2, true)$$,
                'ux_inspection_result_judgement', 'R-81 판정에 쓰는 값은 부품·항목·위치당 하나 (빈칸끼리도 같다고 봄)');
SELECT t.throws($$INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                     instrument_id, inspector_id, measured_at, part_temp_c, input_method, entered_by, check_status, use_for_judgement)
                  VALUES ('LOT-2609-040-1', 2, 'BRK-A100', 1, 'FIRST', NULL, 45.011, 'PASS', 'CMM-01', 'U03', now(), 20, 'MANUAL', 'U03',
                          'NORMAL', true)$$,
                'ck_inspection_result_manual', '수동 입력은 확인 필요에서 시작');
SELECT t.throws($$INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                     instrument_id, inspector_id, measured_at, part_temp_c, input_method, entered_by, check_status, use_for_judgement)
                  VALUES ('LOT-2609-040-1', 3, 'BRK-A100', 1, 'FIRST', NULL, 45.011, 'PASS', 'CMM-01', 'U07', now(), 20, 'MANUAL', 'U07',
                          'NEEDS_CHECK', true)$$,
                '측정자', '측정자는 OPR');

-- R-38 알림은 관련 기록 필수
SELECT t.throws($$INSERT INTO notification (rule_code, importance, raised_at, message) VALUES ('WIP_WARN', 'CAUTION', now(), 'x')$$,
                'ck_notification_related', 'R-38 알림에는 관련 기록 필수');
-- R-35 AI는 v0만
SELECT t.throws($$INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, created_at, status_after, content_snapshot)
                  VALUES ('WORK_ORDER', 'MW-0901', 2, 'AI', now(), 'EDITING', '{}')$$,
                'ck_document_revision_ai_v0', 'R-35 AI 작성은 v0(AI비서 초안)만');
SELECT t.throws($$DELETE FROM document_revision$$, '추가만', '문서 버전은 지울 수 없음');

-- 사람만 하는 일 (R-51): 비서는 사용자 계정이 아니므로 어떤 *_by 칸에도 못 들어감
SELECT t.throws($$UPDATE maintenance_work_order SET approved_by = 'assistant' WHERE wo_no = 'MW-0901'$$,
                '사용 중인 사용자가 아님', 'R-51 비서는 승인자가 될 수 없음 (사용자 계정이 아님)');

ROLLBACK;
