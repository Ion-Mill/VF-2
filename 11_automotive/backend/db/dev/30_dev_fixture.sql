-- =====================================================================
-- 30_dev_fixture.sql — 개발·시험용 작은 운영 데이터 (2026-09-14 야간 ~ 09-15 주간)
-- 생성기 30일 데이터가 오기 전까지 화면·API를 붙여 보는 목업 데이터 겸 db/tests 의 바탕.
-- 장면: VF2-01 알람 992(정지) → 작업지시서·작업기록서 진행 중 / VF2-02 예방 정비(MAINT) /
--       LOT-2609-038-1 측정 대기(CMM 결과 파일 예시와 같은 로트) / LOT-2609-041-1 OP-30에서 두 대에 나뉨
-- =====================================================================
SET app.loading = 'on';

INSERT INTO work_day (work_date, is_workday, daily_target_qty) VALUES
  ('2026-09-14', true, 180), ('2026-09-15', true, 180), ('2026-09-16', true, 180);
INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, supervisor_user_id) VALUES
  ('2026-09-14-D', '2026-09-14', 'DAY',   '2026-09-14 08:00+09', '2026-09-14 17:00+09', 480, 90, 'U10'),
  ('2026-09-14-N', '2026-09-14', 'NIGHT', '2026-09-14 20:00+09', '2026-09-15 05:00+09', 480, 90, 'U11'),
  ('2026-09-15-D', '2026-09-15', 'DAY',   '2026-09-15 08:00+09', '2026-09-15 17:00+09', 480, 90, 'U10'),
  ('2026-09-15-N', '2026-09-15', 'NIGHT', '2026-09-15 20:00+09', '2026-09-16 05:00+09', 480, 90, 'U11');

-- 공구: VF-2 두 대 × T01~T05 (6.25). VF2-01 T05(M6 탭)는 340/400 구멍 = 85%
INSERT INTO tool (tool_id, equipment_id, tool_no, item_no, tool_role, cum_usage, last_changed_at)
SELECT e || '-' || t.no, e, t.no, t.item, 'IN_USE',
       CASE WHEN e = 'VF2-01' AND t.no = 'T05' THEN 340 ELSE t.cum END, '2026-09-10 09:00+09'
  FROM (VALUES ('VF2-01'), ('VF2-02')) eq(e),
       (VALUES ('T01','TL-FM50',100), ('T02','TL-EM10',50), ('T03','TL-BB45',120), ('T04','TL-DR50',300), ('T05','TL-TAP6',120)) t(no, item, cum);

-- 재고 입고 (관리 역할이 기록 — R-77)
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind)
SELECT item_no, 'IN', q, '2026-09-14 09:00+09', CASE owner_role WHEN 'SUP' THEN 'U10' ELSE 'U07' END, 'RECEIPT'
  FROM inventory_item JOIN (VALUES ('TL-EM10',12), ('TL-DR50',8), ('TL-TAP6',10), ('TL-BB45',6), ('TL-FM50',20),
                                   ('CS-WLUB',6), ('CS-COOL',40), ('CS-CFLT',3), ('CS-AFLT',3), ('CS-SLUB',5), ('CS-GRS',3)) v(i, q)
    ON v.i = item_no;

INSERT INTO raw_material_lot (material_lot_no, item_no, received_date, received_qty, supplier_cert_no, heat_batch_no, status)
VALUES ('MAT-2609-05', 'RM-6061', '2026-09-14', 360, 'CERT-VIRTUAL-0905', 'HB-0905', 'AVAILABLE');
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, material_lot_no)
VALUES ('RM-6061', 'IN', 360, '2026-09-14 09:30+09', 'U10', 'MATERIAL_RECEIPT', 'MAT-2609-05');

-- 작업지시·로트
INSERT INTO production_order (order_no, product_code, order_qty, created_at, due_at, status, started_at, completed_at) VALUES
  ('PO-2609-038', 'BRK-A100', 36, '2026-09-14 19:00+09', '2026-09-16 14:00+09', 'DONE', '2026-09-14 20:10+09', '2026-09-15 07:30+09'),
  ('PO-2609-040', 'BRK-A100', 36, '2026-09-15 07:30+09', '2026-09-16 14:00+09', 'DONE', '2026-09-15 08:05+09', '2026-09-15 15:40+09'),
  ('PO-2609-041', 'BRK-A100', 36, '2026-09-15 08:00+09', '2026-09-16 14:00+09', 'IN_PROGRESS', '2026-09-15 09:10+09', NULL);
INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty, status) VALUES
  ('LOT-2609-038-1', 'PO-2609-038', 1, '2026-09-14-N', 'MAT-2609-05', 36, 'WAIT_INSPECTION'),
  ('LOT-2609-040-1', 'PO-2609-040', 1, '2026-09-15-D', 'MAT-2609-05', 36, 'WAIT_INSPECTION'),
  ('LOT-2609-041-1', 'PO-2609-041', 1, '2026-09-15-D', 'MAT-2609-05', 36, 'IN_PROCESS');
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, lot_no)
SELECT 'RM-6061', 'USE', -input_qty, CASE lot_no WHEN 'LOT-2609-038-1' THEN '2026-09-14 20:10+09'::timestamptz
                                                 WHEN 'LOT-2609-040-1' THEN '2026-09-15 08:05+09' ELSE '2026-09-15 09:10+09' END,
       'LOT_INPUT', lot_no
  FROM production_lot;
INSERT INTO inspection_plan (lot_no, plan_mode) VALUES
  ('LOT-2609-038-1', 'NORMAL'), ('LOT-2609-040-1', 'NORMAL'), ('LOT-2609-041-1', 'NORMAL');

-- 공정 실적
INSERT INTO operation_report (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, end_at, pq, gq, rq, sq) VALUES
  ('LOT-2609-038-1', 'OP-10', 'SAW-01', 'U04', '2026-09-14-N', '2026-09-14 20:10+09', '2026-09-14 20:50+09', 36, 36, 0, 0),
  ('LOT-2609-038-1', 'OP-20', 'MIL-01', 'U04', '2026-09-14-N', '2026-09-14 20:20+09', '2026-09-14 22:40+09', 36, 36, 0, 0),
  ('LOT-2609-038-1', 'OP-30', 'VF2-01', 'U05', '2026-09-14-N', '2026-09-14 20:40+09', '2026-09-15 01:00+09', 36, 36, 0, 0),
  ('LOT-2609-038-1', 'OP-40', 'WSH-01', 'U06', '2026-09-14-N', '2026-09-15 00:30+09', '2026-09-15 02:00+09', 36, 36, 0, 0),
  ('LOT-2609-038-1', 'OP-50', 'CMM-01', 'U06', '2026-09-14-N', '2026-09-15 03:30+09', '2026-09-15 04:50+09', 36, 35, 1, 0),
  ('LOT-2609-040-1', 'OP-10', 'SAW-01', 'U01', '2026-09-15-D', '2026-09-15 08:05+09', '2026-09-15 08:45+09', 36, 36, 0, 0),
  ('LOT-2609-040-1', 'OP-20', 'MIL-01', 'U01', '2026-09-15-D', '2026-09-15 08:15+09', '2026-09-15 10:30+09', 36, 36, 0, 0),
  ('LOT-2609-040-1', 'OP-30', 'VF2-02', 'U02', '2026-09-15-D', '2026-09-15 08:30+09', '2026-09-15 10:30+09', 18, 18, 0, 0),
  ('LOT-2609-040-1', 'OP-40', 'WSH-01', 'U03', '2026-09-15-D', '2026-09-15 12:30+09', '2026-09-15 14:00+09', 36, 36, 0, 0),
  ('LOT-2609-040-1', 'OP-50', 'CMM-01', 'U03', '2026-09-15-D', '2026-09-15 14:10+09', '2026-09-15 15:40+09', 36, 36, 0, 0),
  ('LOT-2609-041-1', 'OP-10', 'SAW-01', 'U01', '2026-09-15-D', '2026-09-15 09:10+09', '2026-09-15 09:50+09', 36, 36, 0, 0),
  ('LOT-2609-041-1', 'OP-20', 'MIL-01', 'U01', '2026-09-15-D', '2026-09-15 09:20+09', '2026-09-15 11:40+09', 36, 36, 0, 0),
  ('LOT-2609-041-1', 'OP-30', 'VF2-01', 'U02', '2026-09-15-D', '2026-09-15 09:40+09', NULL, 20, 20, 0, 0),
  ('LOT-2609-041-1', 'OP-30', 'VF2-02', 'U02', '2026-09-15-D', '2026-09-15 12:00+09', NULL, 16, 16, 0, 0);
-- LOT-2609-040-1은 OP-30을 VF2-02에서만 18개 기록 (나머지는 이 목업에 없음 — 가공 설비 = VF2-02)

-- 예방 정비 (VF2-02 매월 항목) → MAINT 구간
INSERT INTO pm_task (pm_task_id, equipment_id, doc04_section, area, item_name, cycle_code, lockout_level, default_role,
                     default_item_no, on_calendar, source_tag) VALUES
  ('PM-VF2-02-2.3-01', 'VF2-02', '2.3', '축 윤활', '윤활유 저장소 양 점검·보충 (개발용 이름)', 'MONTHLY', 'TWO_POINT', 'MNT', 'CS-WLUB', true, 'REAL'),
  ('PM-VF2-01-2.1-01', 'VF2-01', '2.1', '절삭유', '절삭유 농도 확인 (개발용 이름)', 'DAILY', 'NONE', 'OPR', NULL, true, 'REAL');
INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status, current_version) VALUES
  ('PM-VF2-02-2.3-01', '2026-09-15', '2026-09-15 12:00+09', 'U07', 'U07', 'REFILLED', 'CONFIRMED', 0),
  ('PM-VF2-01-2.1-01', '2026-09-14', '2026-09-14 08:10+09', 'U02', 'U07', 'NORMAL', 'CONFIRMED', 0);
-- 예방 정비 실시 기록도 수정 이력 대상 (v0 = 사람이 처음 저장한 것)
INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, status_after, content_snapshot)
SELECT 'PM_RECORD', pm_record_id::text, 0, 'HUMAN', recorded_by, done_at, status, jsonb_build_object('result', result)
  FROM pm_record;

-- 알람: VF2-01 108(주의) → 994(정지) → 992(정지) — S1 모양 (설계서 7장)
INSERT INTO alarm_event (alarm_event_id, equipment_id, alarm_code, severity_at_event, occurred_at, cleared_at, lot_no, prev_alarm_event_id) VALUES
  (1, 'VF2-01', '108', 'WARN', '2026-09-15 10:52+09', '2026-09-15 10:53+09', 'LOT-2609-041-1', NULL),
  (2, 'VF2-01', '994', 'STOP', '2026-09-15 10:55+09', '2026-09-15 10:57+09', 'LOT-2609-041-1', 1),
  (3, 'VF2-01', '992', 'STOP', '2026-09-15 10:58+09', NULL,                  'LOT-2609-041-1', 2);
SELECT setval(pg_get_serial_sequence('alarm_event', 'alarm_event_id'), 3);

-- 설비 상태 구간 (9/15 주간)
INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, end_at, warn_marker,
                                 reason_code, reason_status, reason_entered_by, reason_confirmed_by, reason_confirmed_at,
                                 alarm_event_id, pm_record_id, stop_loss_qty) VALUES
  ('VF2-01', 'RUN',  'ACTIVE',  '2026-09-15 08:00+09', '2026-09-15 10:55+09', false, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('VF2-01', 'DOWN', 'STOPPED', '2026-09-15 10:55+09', '2026-09-15 10:57+09', false, 'F01', 'CONFIRMED', 'U02', 'U10', '2026-09-15 11:30+09', 2, NULL, 0.29),
  ('VF2-01', 'RUN',  'ACTIVE',  '2026-09-15 10:57+09', '2026-09-15 10:58+09', false, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('VF2-01', 'DOWN', 'STOPPED', '2026-09-15 10:58+09', NULL,                  false, 'F01', 'ENTERED', 'U02', NULL, NULL, 3, NULL, NULL),
  ('VF2-02', 'RUN',  'ACTIVE',  '2026-09-15 08:00+09', '2026-09-15 10:30+09', false, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('VF2-02', 'MAINT', NULL,     '2026-09-15 10:30+09', '2026-09-15 12:00+09', false, 'P01', 'CONFIRMED', 'U07', 'U10', '2026-09-15 12:05+09', NULL, 1, NULL),
  ('VF2-02', 'RUN',  'ACTIVE',  '2026-09-15 12:00+09', NULL,                  false, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);

-- 작업지시서 MW-0901 (992) — 승인·진행 중 / 작업기록서 MR-0901 — 수정 중
INSERT INTO maintenance_work_order (wo_no, alarm_event_id, equipment_id, lot_no, created_at, title, symptom, status,
    assignee_user_id, approved_by, approved_at, safety_block_doc_rev, has_high_voltage_notice, current_version)
VALUES ('MW-0901', 3, 'VF2-01', 'LOT-2609-041-1', '2026-09-15 10:59+09', '(개발용) 알람 992 점검', '과부하 뒤 과전류 (충돌 의심)',
        'IN_PROGRESS', 'U07', 'U10', '2026-09-15 11:10+09', 'DOC-05 Rev.1', true, 1);
INSERT INTO work_order_step (wo_no, step_no, step_text, source_section) VALUES
  ('MW-0901', 1, '(개발용) 서보 앰프 상태 확인', 'DOC-03 §2.1'),
  ('MW-0901', 2, '(개발용) 축 모터 케이블 확인', 'DOC-03 §2.1');
INSERT INTO work_order_part (wo_no, item_no, suggested_qty) VALUES ('MW-0901', 'CS-WLUB', 1);
INSERT INTO work_record (record_no, record_type, wo_no, alarm_event_id, equipment_id, lot_no, cause, action, worker_memo,
                         start_at, safety_block_required, status, current_version)
VALUES ('MR-0901', 'FULL', 'MW-0901', 3, 'VF2-01', 'LOT-2609-041-1', '(개발용) 케이블 절삭유 침투',
        '(개발용) 케이블 교체·건조', '앰프 쪽 냄새남, 케이블 봤는데 절삭유 묻어있음', '2026-09-15 11:15+09', true, 'EDITING', 1);
INSERT INTO work_record_check (record_no, check_seq, check_kind, wo_no, step_no, loto_step_code, is_checked, checked_by, checked_at)
SELECT 'MR-0901', row_number() OVER (), 'LOTO', NULL, NULL, s, s <= '6.6', CASE WHEN s <= '6.6' THEN 'U07' END,
       CASE WHEN s <= '6.6' THEN '2026-09-15 11:20+09'::timestamptz END
  FROM unnest(ARRAY['6.1','6.2','6.3','6.4','6.5','6.6','7.1','7.2','7.3']) s;
INSERT INTO work_record_check (record_no, check_seq, check_kind, wo_no, step_no, is_checked)
VALUES ('MR-0901', 10, 'STEP', 'MW-0901', 1, false), ('MR-0901', 11, 'STEP', 'MW-0901', 2, false);
INSERT INTO work_record_part (record_no, item_no, qty, proposed_by_kind) VALUES ('MR-0901', 'CS-WLUB', 0.5, 'AI');

-- 문서 버전 v0 (AI비서 초안) → v1 (사람)
INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, reason, status_after, content_snapshot) VALUES
  ('WORK_ORDER', 'MW-0901', 0, 'AI', NULL, '2026-09-15 10:59+09', NULL, 'AI_DRAFT', '{"title": "알람 992 점검"}'),
  ('WORK_ORDER', 'MW-0901', 1, 'HUMAN', 'U07', '2026-09-15 11:05+09', NULL, 'EDITING', '{"title": "(개발용) 알람 992 점검"}'),
  ('WORK_RECORD', 'MR-0901', 0, 'AI', NULL, '2026-09-15 11:16+09', NULL, 'AI_DRAFT', '{"cause": "케이블 확인 필요"}'),
  ('WORK_RECORD', 'MR-0901', 1, 'HUMAN', 'U07', '2026-09-15 11:40+09', NULL, 'EDITING', '{"cause": "(개발용) 케이블 절삭유 침투"}');
INSERT INTO document_revision_change (revision_id, field_name, before_value, after_value)
SELECT revision_id, '원인', '케이블 확인 필요', '(개발용) 케이블 절삭유 침투' FROM document_revision
 WHERE doc_type = 'WORK_RECORD' AND doc_key = 'MR-0901' AND version_no = 1;

-- 측정 지시 (LOT-2609-038-1: 초품 1번, 발췌 5번) — CMM 결과 파일 예시(S01·S06·F12)와 맞춰 보기용
INSERT INTO cmm_instruction (lot_no, part_seq, insp_kind, issued_at, started_at, started_by, status) VALUES
  ('LOT-2609-038-1', 1, 'FIRST',  '2026-09-15 08:30+09', '2026-09-15 08:38+09', 'U03', 'STARTED'),
  ('LOT-2609-038-1', 5, 'SAMPLE', '2026-09-15 12:20+09', NULL, NULL, 'ISSUED');

-- 교대 보고서 초안 (9/14 야간 — 확정됨, 9/15 주간 — 초안)
INSERT INTO shift_report (shift_id, status, target_qty, actual_qty, defect_qty, availability_pct, notable_text, handover_text,
                          confirmed_by, confirmed_at, current_version) VALUES
  ('2026-09-14-N', 'CONFIRMED', 90, 84, 1, '{"VF2-01": 78.5, "VF2-02": 80.1}', '(개발용) 특이 사항 없음', '없음', 'U11', '2026-09-15 05:20+09', 0),
  ('2026-09-15-D', 'AI_DRAFT', 90, 0, 0, '{"VF2-01": 0, "VF2-02": 0}', '(개발용 초안)', '(개발용 초안)', NULL, NULL, 0);
INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, reason, status_after, content_snapshot) VALUES
  ('SHIFT_REPORT', '2026-09-14-N', 0, 'AI', NULL, '2026-09-15 05:00+09', NULL, 'AI_DRAFT', '{"notable_text": "(개발용) 특이 사항 없음"}'),
  ('SHIFT_REPORT', '2026-09-15-D', 0, 'AI', NULL, '2026-09-15 17:00+09', NULL, 'AI_DRAFT', '{"notable_text": "(개발용 초안)"}');

RESET app.loading;
-- 적재 뒤 번호 카운터 맞추기
SELECT fn_sync_doc_numbers();
-- 야간 이월 (R-88): 9/14 주간은 목업 밖(기록 없음) → 0, 9/15 야간은 9/15 주간 실적(확정 전 — 잠정)으로 계산
SELECT work_date, fn_refresh_carry_over(work_date) AS carry_over_qty FROM work_day ORDER BY work_date;
