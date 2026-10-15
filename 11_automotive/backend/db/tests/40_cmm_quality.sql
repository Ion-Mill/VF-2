-- CMM 결과 파일 자동 기록 (R-78~R-82, 가공 설비 P-11)과 로트 판정·합격 입고 (R-25·R-69)
-- 값은 사용자 폴더 "Claude outputs/"의 예시 파일 3개 (MOM-CMM-CSV v0.1)를 app/domain/cmm_csv.py가 읽은 모양 그대로
BEGIN;
SELECT t.freeze('2026-09-15 16:00+09');

-- ① S01 FIRST: 지시(1번 초품)가 있음 → 성공, 6항목 정상
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_S01_FIRST.csv', 'processed/CMM-01_LOT-2609-038-1_S01_FIRST.csv',
  '{"format": "MOM-CMM-CSV v0.1 (예시 · 가상 데이터)", "cmm_id": "CMM-01", "program": "BRK-A100_OP50_R0",
    "lot_no": "LOT-2609-038-1", "sample_no": "S01", "part_seq": 1, "insp_kind": "FIRST", "operator": "U01",
    "measured_at": "2026-09-15T08:41:20+09:00", "room_temp_c": 20.2, "part_temp_c": 23.8, "temp_comp": true, "cte_um_per_m_k": 23.6}',
  '[{"item_seq":1,"position":null,"actual":45.011,"cmm_judgement":"PASS"},{"item_seq":2,"position":null,"actual":150.060,"cmm_judgement":"PASS"},
    {"item_seq":3,"position":null,"actual":12.020,"cmm_judgement":"PASS"},{"item_seq":4,"position":null,"actual":110.018,"cmm_judgement":"PASS"},
    {"item_seq":5,"position":null,"actual":0.017,"cmm_judgement":"PASS"},{"item_seq":8,"position":null,"actual":55.050,"cmm_judgement":"PASS"}]');
SELECT t.eq((SELECT status FROM cmm_import WHERE file_name LIKE '%S01_FIRST.csv'), 'SUCCESS', 'S01 초품 파일 성공');
SELECT t.eq((SELECT count(*) FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 1 AND check_status = 'NORMAL')::int,
            6, 'S01 측정값 6개 정상');
SELECT t.eq((SELECT inspector_id FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 1 LIMIT 1), 'U03',
            '측정자 = 측정 시작 때 확인한 사람 (파일의 operator가 아니라)');
SELECT t.eq((SELECT status FROM cmm_instruction WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 1), 'DONE', '측정 지시 완료');
SELECT t.ok((SELECT raw_header ? 'cte_um_per_m_k' FROM cmm_import WHERE file_name LIKE '%S01_FIRST.csv'),
            '양식에 없는 머리 칸(cte)도 원본 그대로 보관');

-- ② S06 SAMPLE: 6번 부품에 지시가 없음 (발췌 = 1·5·10…) → 확인 필요, 측정값은 남김
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_S06_SAMPLE.csv', 'error/CMM-01_LOT-2609-038-1_S06_SAMPLE.csv',
  '{"format": "MOM-CMM-CSV v0.1 (예시 · 가상 데이터)", "cmm_id": "CMM-01", "program": "BRK-A100_OP50_R0",
    "lot_no": "LOT-2609-038-1", "sample_no": "S06", "part_seq": 6, "insp_kind": "SAMPLE", "operator": "U01",
    "measured_at": "2026-09-15T12:31:05+09:00", "room_temp_c": 20.4, "part_temp_c": 21.6, "temp_comp": true}',
  '[{"item_seq":1,"position":null,"actual":45.027,"cmm_judgement":"FAIL"},{"item_seq":2,"position":null,"actual":150.040,"cmm_judgement":"PASS"},
    {"item_seq":3,"position":null,"actual":12.030,"cmm_judgement":"PASS"},{"item_seq":4,"position":null,"actual":110.022,"cmm_judgement":"PASS"},
    {"item_seq":5,"position":null,"actual":0.021,"cmm_judgement":"PASS"},{"item_seq":8,"position":null,"actual":55.020,"cmm_judgement":"PASS"}]');
SELECT t.eq((SELECT status || '/' || error_kind FROM cmm_import WHERE file_name LIKE '%S06_SAMPLE.csv'), 'NEEDS_CHECK/LOT_MISMATCH',
            'S06은 지시와 다름 → 확인 필요');
SELECT t.eq((SELECT judgement FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 6 AND item_seq = 1), 'FAIL',
            'R-79 45.027 > 45.025 → 플랫폼도 불합격');
SELECT t.ok(EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CMM_FILE_ERROR'), 'CMM 파일 확인 필요 알림');

-- ③ F12 ENHANCED: 3단(위·중간·아래)은 재측정이 아니라 별도 측정값, 판정용은 표준만
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_F12_ENHANCED.csv', 'error/CMM-01_LOT-2609-038-1_F12_ENHANCED.csv',
  '{"format": "MOM-CMM-CSV v0.1 (예시 · 가상 데이터)", "cmm_id": "CMM-01", "program": "BRK-A100_OP50_ENH_R0",
    "lot_no": "LOT-2609-038-1", "sample_no": "F12", "part_seq": 12, "insp_kind": "ENHANCED", "operator": "U06",
    "measured_at": "2026-09-15T15:10:44+09:00", "room_temp_c": 20.3, "part_temp_c": 20.9, "temp_comp": true}',
  '[{"item_seq":1,"position":null,"actual":45.019,"cmm_judgement":"PASS"},{"item_seq":1,"position":"TOP","actual":45.021,"cmm_judgement":"PASS"},
    {"item_seq":1,"position":"MID","actual":45.018,"cmm_judgement":"PASS"},{"item_seq":1,"position":"BOTTOM","actual":45.016,"cmm_judgement":"PASS"},
    {"item_seq":2,"position":null,"actual":149.980,"cmm_judgement":"PASS"},{"item_seq":3,"position":null,"actual":12.010,"cmm_judgement":"PASS"},
    {"item_seq":4,"position":null,"actual":109.991,"cmm_judgement":"PASS"},{"item_seq":5,"position":null,"actual":0.024,"cmm_judgement":"PASS"},
    {"item_seq":8,"position":null,"actual":54.990,"cmm_judgement":"PASS"}]');
SELECT t.eq((SELECT count(*) FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 12 AND item_seq = 1 AND remeasure_seq = 1)::int,
            4, '부싱 구멍 4줄(표준+3단) 모두 재측정 1회차');
SELECT t.eq((SELECT count(*) FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 12 AND use_for_judgement)::int,
            9, '판정용 값 = 위치마다 첫 측정 (1번 표준+3단 4줄, 나머지 5항목 — 2026-10-14 3단도 판정에 씀)');

-- ④ 같은 부품을 다시 잼 → 덮어쓰지 않고 재측정 2회차, 확인 필요, 판정용 아님 (R-81)
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_S01_FIRST_2.csv', 'processed/x.csv',
  '{"cmm_id": "CMM-01", "lot_no": "LOT-2609-038-1", "part_seq": 1, "insp_kind": "FIRST", "operator": "U03",
    "measured_at": "2026-09-15T09:10:00+09:00", "part_temp_c": 21.0, "temp_comp": true}',
  '[{"item_seq":1,"position":null,"actual":45.012,"cmm_judgement":"PASS"}]');
SELECT t.eq((SELECT remeasure_seq || '/' || check_status || '/' || use_for_judgement FROM inspection_result
              WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 1 AND item_seq = 1 ORDER BY remeasure_seq DESC LIMIT 1),
            '2/NEEDS_CHECK/false', 'R-81 재측정은 따로 보관');
SELECT t.eq((SELECT count(*) FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 1 AND item_seq = 1)::int, 2,
            '첫 측정값은 지워지지 않음');
SELECT t.eq((SELECT status || '/' || error_kind FROM cmm_import WHERE file_name = 'CMM-01_LOT-2609-038-1_S01_FIRST_2.csv'),
            'NEEDS_CHECK/LOT_MISMATCH', '열린 지시가 없는 재측정 → 확인 필요 (지시 다시 내리기 필요)');

-- ⑤ 판정 불일치: 측정기는 합격, 플랫폼 기준으로는 불합격 → 불일치 표시 + 알림 (R-79)
INSERT INTO cmm_instruction (lot_no, part_seq, insp_kind, issued_at, started_at, started_by, status)
VALUES ('LOT-2609-038-1', 5, 'SAMPLE', '2026-09-15 15:30+09', '2026-09-15 15:31+09', 'U03', 'STARTED')
ON CONFLICT DO NOTHING;
UPDATE cmm_instruction SET status = 'STARTED', started_at = '2026-09-15 15:31+09', started_by = 'U03'
 WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 5;
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_S05_SAMPLE_202609151535.csv', 'processed/y.csv',
  '{"cmm_id": "CMM-01", "lot_no": "LOT-2609-038-1", "part_seq": 5, "insp_kind": "SAMPLE", "operator": "U03",
    "measured_at": "2026-09-15T15:35:00+09:00", "part_temp_c": 27.1, "temp_comp": false}',
  '[{"item_seq":1,"position":null,"actual":45.026,"cmm_judgement":"PASS"},{"item_seq":2,"position":null,"actual":150.0,"cmm_judgement":"PASS"},
    {"item_seq":3,"position":null,"actual":12.0,"cmm_judgement":"PASS"},{"item_seq":4,"position":null,"actual":110.0,"cmm_judgement":"PASS"},
    {"item_seq":5,"position":null,"actual":0.01,"cmm_judgement":"PASS"},{"item_seq":8,"position":null,"actual":55.0,"cmm_judgement":"PASS"}]');
SELECT t.ok((SELECT is_judgement_mismatch AND check_status = 'NEEDS_CHECK' FROM inspection_result
              WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 5 AND item_seq = 1), 'R-79 판정 불일치 → 확인 필요');
SELECT t.ok((SELECT is_temp_flag FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 5 AND item_seq = 1),
            'R-82 부품 온도 27.1 ℃ → 온도 확인 표시');
SELECT t.ok(EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CMM_JUDGE_MISMATCH'), '판정 불일치 알림');
-- 반장 확인 → 알림 자동 처리
SELECT fn_check_measurement((SELECT result_id FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 5 AND item_seq = 1),
                            'U10', true);
SELECT t.ok((SELECT bool_and(is_processed) FROM notification WHERE rule_code = 'CMM_JUDGE_MISMATCH'), '반장 확인 뒤 불일치 알림 처리');
SELECT t.throws($$SELECT fn_check_measurement(1, 'U02', true)$$, 'SUP', '측정값 확인은 SUP만');

-- ⑥ 없는 로트·양식 오류 → 기록하지 않고 실패
SELECT fn_import_cmm('bad_lot.csv', 'error/bad_lot.csv', '{"lot_no": "LOT-2609-999-1", "part_seq": 1, "insp_kind": "FIRST"}', '[]');
SELECT t.eq((SELECT status FROM cmm_import WHERE file_name = 'bad_lot.csv'), 'FAILED', '없는 로트 → 실패');
SELECT fn_record_cmm_failure('broken.csv', 'error/broken.csv', 'FORMAT', '열 빠짐: actual');
SELECT t.eq((SELECT count(*) FROM inspection_result r JOIN cmm_import c USING (cmm_import_id) WHERE c.status = 'FAILED')::int, 0,
            'R-80 실패 파일은 측정값을 기록하지 않음');

-- ⑦ 가공 설비 (P-11): 038-1은 VF2-01 한 대, 041-1은 두 대 → 설비 미상
SELECT t.eq((SELECT DISTINCT machined_equipment_id FROM v_inspection_result WHERE lot_no = 'LOT-2609-038-1'), 'VF2-01', 'P-11 가공 설비 1대');
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, judgement, instrument_id, inspector_id,
                               measured_at, input_method, use_for_judgement)
VALUES ('LOT-2609-041-1', 1, 'BRK-A100', 6, 'FIRST', NULL, 'PASS', 'CMM-01', 'U03', app_now(), 'TABLET', true);
SELECT t.ok((SELECT machined_equipment_id IS NULL FROM v_inspection_result WHERE lot_no = 'LOT-2609-041-1'), 'P-11 두 대에 나뉘면 설비 미상');

-- ⑧ 로트 판정 (R-25): 040-1 (36개 → 측정 부품 8개: 1,5,10,…,35)
SELECT t.eq((SELECT planned_measure_qty FROM v_production_lot WHERE lot_no = 'LOT-2609-040-1'), 8, 'R-09 36개 → 측정 8개');
SELECT t.eq(fn_lot_judge('LOT-2609-040-1'), 'NOT_READY', '측정 전에는 판정 안 함');
SELECT t.eq((SELECT status FROM production_lot WHERE lot_no = 'LOT-2609-040-1'), 'WAIT_JUDGEMENT', '판정 대기');
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement, instrument_id,
                               inspector_id, measured_at, part_temp_c, input_method, entered_by, check_status, checked_by, checked_at, use_for_judgement)
SELECT 'LOT-2609-040-1', p, 'BRK-A100', i.item_seq, CASE WHEN p = 1 THEN 'FIRST' ELSE 'SAMPLE' END, NULL,
       coalesce(i.nominal, 0) + 0.001, 'PASS', 'CMM-01', 'U03', app_now(), 20, 'MANUAL', 'U03', 'CHECKED', 'U10', app_now(), true
  FROM fn_planned_parts('LOT-2609-040-1') p, inspection_item i WHERE i.method = 'CMM' AND i.in_sampling;
SELECT t.eq(fn_lot_judge('LOT-2609-040-1', '2026-09-15 16:30+09'), 'PASS', '모두 합격 → 로트 합격');
SELECT t.eq((SELECT qty_change FROM inventory_txn WHERE source_kind = 'LOT_PASS' AND fg_lot_no = 'LOT-2609-040-1'), 36.000::numeric,
            'R-69 합격 수량 36 = 완제품 합격 입고');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'FG-BRK-A100'), 36.000::numeric, '완제품 재고 36');
SELECT t.ok((SELECT passed_at = '2026-09-15 16:30+09' FROM v_production_lot WHERE lot_no = 'LOT-2609-040-1'), '합격 시각 = 판정 시각');
ROLLBACK;
