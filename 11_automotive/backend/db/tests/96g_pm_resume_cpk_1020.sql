-- 2026-10-20 요구사항 대조 중 (구현_중_수정사항 1020 36장): [정비 시작]·[정비 끝] (FR-MNT-04-10), 강화 → 보통 검사 복귀 (R-29),
-- Cpk 기준 미달 → 그 특성 전수 측정 (DOC-06 §5.2)
BEGIN;
SELECT t.freeze('2026-09-15 15:00+09');

-- ---------- [정비 시작] → MAINT 구간 + 실시 기록(수정 중), 끝나기 전에는 "실시 기록 확인" 알림 없음
SELECT t.throws($$SELECT fn_pm_start('PM-VF2-01-2.1-01', 'U07')$$, '고장 정지 중', 'VF2-01은 고장 정지 중 → 작업지시서로');
SELECT fn_pm_start('PM-VF2-02-2.3-01', 'U07') AS pmr \gset
SELECT t.eq((SELECT state_code || '/' || pm_record_id FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND end_at IS NULL),
            'MAINT/' || :pmr, 'VF2-02 MAINT 구간 = 그 실시 기록');
SELECT t.eq((SELECT end_at FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND state_code = 'RUN'
              AND start_at = '2026-09-15 12:00+09'), '2026-09-15 15:00+09'::timestamptz, '앞 구간(RUN)은 정비 시작 시각에 닫힘');
SELECT t.eq((SELECT count(*)::int FROM notification WHERE rule_code = 'PM_RECORD_CHECK' AND equipment_id = 'VF2-02'), 0,
            '정비 중에는 실시 기록 확인 알림 없음');
SELECT t.throws($$SELECT fn_pm_start('PM-VF2-02-2.3-01', 'U07')$$, '이미 정비 중', '정비 중에 또 시작 못 함');
SELECT t.throws($$SELECT fn_pm_start('PM-VF2-02-2.3-01', 'U02')$$, 'MNT', '실시 기록은 MNT');

-- ---------- [정비 끝 · 실시 기록] 90분 뒤 → 구간 닫힘(대기), 실시 시각 = 끝난 시각, 알림
SELECT t.freeze('2026-09-15 16:30+09');
SELECT fn_pm_end(:pmr, 'U07', 'REFILLED', 1.5, 'L', '윤활유 보충');
SELECT t.eq((SELECT round(extract(epoch FROM end_at - start_at) / 60)::int FROM equipment_state_log WHERE pm_record_id = :pmr), 90,
            'MAINT 구간 = [정비 시작] ~ [정비 끝] 90분');
SELECT t.eq((SELECT state_code FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND end_at IS NULL), 'IDLE', '끝나면 대기');
SELECT t.eq((SELECT (done_at = '2026-09-15 16:30+09')::text || '/' || result || '/' || status FROM pm_record WHERE pm_record_id = :pmr),
            'true/REFILLED/DRAFT', '실시 시각 = 끝난 시각, 결과, 수정 중');
SELECT t.eq((SELECT count(*)::int FROM notification n JOIN notification_pm_task l USING (notification_id)
              WHERE n.rule_code = 'PM_RECORD_CHECK' AND l.pm_task_id = 'PM-VF2-02-2.3-01'), 1, '끝나면 실시 기록 확인 알림');
SELECT t.throws(format('SELECT fn_pm_end(%s, %L)', :pmr, 'U07'), '열려 있지 않음', '두 번 끝내기 막힘');

-- ---------- 강화 → 보통 (R-29): 041-1 보류 (다음 2개 강화)
SELECT fn_lot_hold('LOT-2609-041-1', 'U10', 'AI_SUSPECT', '정지 등급 알람 992 중 가공 (충돌 의심)', 2, 3) AS hid \gset
SELECT t.throws(format('SELECT fn_resume_normal(%s, %L)', :hid, 'U10'), '해제·폐기가 먼저', '보류 로트가 끝나기 전에는 안 됨');
SELECT fn_lot_scrap_propose(:hid, 'U10', 36);
SELECT fn_lot_scrap_approve(:hid, 'U12');
SELECT t.throws(format('SELECT fn_resume_normal(%s, %L)', :hid, 'U10'), '모두 합격', '강화한 다음 로트가 아직 없음');
INSERT INTO production_order (order_no, product_code, order_qty, created_at, due_at, status, started_at)
VALUES ('PO-2609-042', 'BRK-A100', 40, '2026-09-15 13:00+09', '2026-09-16 14:00+09', 'IN_PROGRESS', '2026-09-15 13:10+09');
INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty) VALUES
  ('LOT-2609-042-1', 'PO-2609-042', 1, '2026-09-15-D', 'MAT-2609-05', 20),
  ('LOT-2609-042-2', 'PO-2609-042', 2, '2026-09-15-D', 'MAT-2609-05', 20);
SELECT fn_create_inspection_plan('LOT-2609-042-1'), fn_create_inspection_plan('LOT-2609-042-2');
UPDATE inspection_plan SET judgement = 'PASS', judged_at = '2026-09-15 16:00+09' WHERE lot_no = 'LOT-2609-042-1';
SELECT t.throws(format('SELECT fn_resume_normal(%s, %L)', :hid, 'U10'), '모두 합격', '강화 로트 하나가 아직 판정 전');
UPDATE inspection_plan SET judgement = 'PASS', judged_at = '2026-09-15 16:10+09' WHERE lot_no = 'LOT-2609-042-2';
SELECT t.throws(format('SELECT fn_resume_normal(%s, %L)', :hid, 'U10'), '원인 조치', '원인 조치 기록(확정 작업기록서·공구 교체)이 없음');
INSERT INTO tool_change (tool_id, changed_at, changed_by, cum_before, change_reason, related_alarm_event_id)
VALUES ('VF2-01-T05', '2026-09-15 16:35+09', 'U07', 10, 'BROKEN', 3);
SELECT t.throws(format('SELECT fn_resume_normal(%s, %L)', :hid, 'U02'), 'SUP', '확인은 반장');
SELECT t.freeze('2026-09-15 16:40+09');
SELECT fn_resume_normal(:hid, 'U10');
SELECT t.eq((SELECT normal_resumed_by || '/' || (normal_resumed_at = '2026-09-15 16:40+09')::text FROM lot_hold WHERE hold_id = :hid), 'U10/true',
            '두 조건이 맞으면 보통으로 (반장·시각)');
SELECT t.throws(format('SELECT fn_resume_normal(%s, %L)', :hid, 'U10'), '이미 보통', '두 번은 안 됨');

-- ---------- Cpk 기준 미달 → 전수 측정, 기준 이상이 되면 관리자 승인으로 보통
SELECT fn_import_cmm('cpk.csv', 'processed/cpk.csv',
  '{"cmm_id": "CMM-01", "lot_no": "LOT-2609-040-1", "part_seq": 99, "insp_kind": "SAMPLE", "operator": "U03",
    "measured_at": "2026-09-15T08:59:00+09:00", "part_temp_c": 20.5, "temp_comp": true}',
  '[{"item_seq":3,"position":null,"actual":12.010,"cmm_judgement":"PASS"}]');
SELECT max(cmm_import_id) AS imp FROM cmm_import \gset
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                               instrument_id, inspector_id, measured_at, input_method, remeasure_seq, use_for_judgement,
                               cmm_import_id, cmm_judgement, part_temp_c)
SELECT 'LOT-2609-040-1', g, 'BRK-A100', 2, 'SAMPLE', NULL, 150.000 + (g % 2) * 0.400, 'PASS', 'CMM-01', 'U03',
       '2026-09-15 09:00+09'::timestamptz + make_interval(secs => g), 'CMM_AUTO', 1, true, :imp, 'PASS', 20.5
  FROM generate_series(100, 154) g;
SELECT t.eq(fn_check_cpk(), 1, 'Cpk 0.3 < 1.33 → 전체 길이 전수 측정');
SELECT t.ok((SELECT is_full_check_by_cpk FROM inspection_item WHERE product_code = 'BRK-A100' AND item_seq = 2), '전수 측정 표시');
SELECT t.ok(fn_issue_cmm_instruction('LOT-2609-040-1', 3) IS NOT NULL, '전수 측정 중이면 발췌 로트도 3번 부품에 측정 지시');
SELECT t.throws($$SELECT fn_resume_sampling('BRK-A100', 2, 'U12')$$, '기준', '아직 기준 미만이면 보통으로 못 감');
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                               instrument_id, inspector_id, measured_at, input_method, remeasure_seq, use_for_judgement,
                               cmm_import_id, cmm_judgement, part_temp_c)
SELECT 'LOT-2609-040-1', g, 'BRK-A100', 2, 'SAMPLE', NULL, 150.000 + (g % 2) * 0.001, 'PASS', 'CMM-01', 'U03',
       '2026-09-15 10:00+09'::timestamptz + make_interval(secs => g), 'CMM_AUTO', 1, true, :imp, 'PASS', 20.5
  FROM generate_series(200, 999) g;
SELECT t.throws($$SELECT fn_resume_sampling('BRK-A100', 2, 'U10')$$, 'MGR', '보통으로 되돌리기는 관리자');
SELECT t.ok(fn_resume_sampling('BRK-A100', 2, 'U12') >= 1.33, 'Cpk 기준 이상 → 관리자 승인으로 보통');
SELECT t.ok(NOT (SELECT is_full_check_by_cpk FROM inspection_item WHERE product_code = 'BRK-A100' AND item_seq = 2), '전수 표시 꺼짐');
SELECT t.throws($$SELECT fn_issue_cmm_instruction('LOT-2609-040-1', 4)$$, 'R-09', '보통으로 돌아가면 다시 1번·5의 배수만');
ROLLBACK;
