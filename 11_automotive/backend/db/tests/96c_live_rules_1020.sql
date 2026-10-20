-- 2026-10-20 상 1·2번 (구현_중_수정사항 1020 36장): 실시간 알림 4종(병목 이동·재공 경고·관리도 이상·납기 위험)과 속도 손실
BEGIN;
SELECT t.freeze('2026-09-15 12:00+09');

-- ---------- 근무 분: 휴식 1시간(12:00~13:00)·교대 사이는 빠진다
SELECT t.eq(fn_work_minutes('2026-09-15 11:00+09', '2026-09-15 14:00+09'), 120::numeric, '11:00~14:00 = 180분 − 휴식 60분');
SELECT t.eq(fn_work_minutes('2026-09-15 16:00+09', '2026-09-15 21:00+09'), 120::numeric, '16:00~21:00 = 주간 끝 60분 + 야간 시작 60분 (교대 사이 빠짐)');
SELECT t.eq(fn_add_work_minutes('2026-09-15 11:30+09', 60), '2026-09-15 13:30+09'::timestamptz, '11:30 + 근무 60분 = 휴식 지나 13:30');

-- ---------- 병목 기록 → 이동 알림 + 앞 구간 속도 손실 (원인 ①②③만)
INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code) VALUES ('2026-09-15 08:30+09', NULL, 'OP-30', 'BASE');
INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code) VALUES ('2026-09-15 10:00+09', 'OP-30', 'OP-30', 'C2');
INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code) VALUES ('2026-09-15 11:30+09', 'OP-30', 'OP-50', 'C3');
INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code) VALUES ('2026-09-15 11:40+09', 'OP-50', 'OP-30', 'C4');
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'BOTTLENECK_MOVE')::int, 3, '병목 기록마다 이동 알림 (원인 ④ 묶음 대기는 빼고)');
SELECT t.eq((SELECT message FROM notification n JOIN bottleneck_log b USING (bottleneck_log_id) WHERE b.cause_code = 'C3'),
            '[병목] OP-30 → OP-50 (원인 ③ 검사 강화)', '문장 = 이전 → 새 병목 (원인)');
SELECT t.ok((SELECT related_info LIKE 'DOC-07 §7.5 ③%' FROM notification n JOIN bottleneck_log b USING (bottleneck_log_id) WHERE b.cause_code = 'C3'),
            '관련 정보 = DOC-07 §7.5 해당 원인 조치 줄');
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              JOIN bottleneck_log b USING (bottleneck_log_id) WHERE b.cause_code = 'C3'), 'U10,U11', '받는 사람 = 반장');
-- 원인 ② 구간 10:00~11:30 = 근무 90분 → 계획 25.71개, 실제 0(OP-50 완료 없음), 고장 손실 = 10:55 정지 0.29 + 10:58~ 정지 32분 ÷ 7
SELECT t.eq((SELECT speed_loss_qty FROM bottleneck_log WHERE cause_code = 'C2'),
            round(90 / 3.5 - 0 - (0.29 + 32 / 7.0), 2), '닫힌 구간의 속도 손실 = 계획 − 실제 − 고장 손실');
SELECT t.eq((SELECT speed_loss_qty FROM bottleneck_log WHERE cause_code = 'BASE'), 0::numeric, '기준 병목 구간은 속도 손실 0');
SELECT t.ok(fn_speed_loss_qty('2026-09-15 08:00+09', '2026-09-15 17:00+09') >= (SELECT speed_loss_qty FROM bottleneck_log WHERE cause_code = 'C2'),
            '교대 속도 손실 합에 닫힌 구간이 들어감 (전에는 늘 0)');

-- ---------- 재공 경고: 경고 기준(20) 넘으면 위치마다 교대에 처음 1번, 한도(30)면 "앞 공정 막힘"
INSERT INTO wip_log (buffer_code, logged_at, wip_qty, interval_type) VALUES ('WIP-40-50', '2026-09-15 11:05+09', 18, 'MIN5');
INSERT INTO wip_log (buffer_code, logged_at, wip_qty, interval_type) VALUES ('WIP-40-50', '2026-09-15 11:10+09', 23, 'MIN5');
INSERT INTO wip_log (buffer_code, logged_at, wip_qty, interval_type) VALUES ('WIP-40-50', '2026-09-15 11:15+09', 25, 'MIN5');
SELECT t.eq((SELECT string_agg(message, ' | ') FROM notification WHERE rule_code = 'WIP_WARN'),
            '[재공] WIP-40-50 재공 23개 — 경고 기준 20개 초과', '경고 기준을 넘은 첫 기록에서 1건, 같은 교대에는 더 안 냄');
INSERT INTO wip_log (buffer_code, logged_at, wip_qty, interval_type) VALUES ('WIP-20-30', '2026-09-15 11:10+09', 30, 'MIN5');
SELECT t.eq((SELECT message FROM notification WHERE rule_code = 'WIP_WARN' AND buffer_code = 'WIP-20-30'),
            '[재공] WIP-20-30 재공 30개 — 한도 30 도달, 앞 공정 막힘', '한도에 닿으면 앞 공정 막힘 문장');
INSERT INTO wip_log (buffer_code, logged_at, wip_qty, interval_type) VALUES ('WIP-40-50', '2026-09-15 20:10+09', 24, 'MIN5');
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'WIP_WARN' AND buffer_code = 'WIP-40-50')::int, 2, '다음 교대(야간)에는 다시 1건');

-- ---------- 관리도 이상: 측정기 자동 값 50개 이상 항목, 평균 ± 3σ(이동 범위) 밖 → 반장, 다음 측정이 오면 자동 처리
SELECT fn_import_cmm('spc.csv', 'processed/spc.csv',
  '{"cmm_id": "CMM-01", "lot_no": "LOT-2609-040-1", "part_seq": 99, "insp_kind": "SAMPLE", "operator": "U03",
    "measured_at": "2026-09-15T08:59:00+09:00", "part_temp_c": 20.5, "temp_comp": true}',
  '[{"item_seq":3,"position":null,"actual":12.010,"cmm_judgement":"PASS"}]');
SELECT max(cmm_import_id) AS imp FROM cmm_import \gset
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                               instrument_id, inspector_id, measured_at, input_method, remeasure_seq, use_for_judgement,
                               cmm_import_id, cmm_judgement, part_temp_c)
SELECT 'LOT-2609-040-1', g, 'BRK-A100', 2, 'SAMPLE', NULL, 150.000 + (g % 2) * 0.010, 'PASS', 'CMM-01', 'U03',
       '2026-09-15 09:00+09'::timestamptz + make_interval(mins => g), 'CMM_AUTO', 1, true, :imp, 'PASS', 20.5
  FROM generate_series(100, 154) g;
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'SPC_OUT')::int, 0, '한계 안이면 알림 없음');
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                               instrument_id, inspector_id, measured_at, input_method, remeasure_seq, use_for_judgement,
                               cmm_import_id, cmm_judgement, part_temp_c)
VALUES ('LOT-2609-040-1', 155, 'BRK-A100', 2, 'SAMPLE', NULL, 150.100, 'PASS', 'CMM-01', 'U03', '2026-09-15 10:00+09', 'CMM_AUTO', 1, true,
        :imp, 'PASS', 20.5);
SELECT t.ok((SELECT message LIKE '[품질] 항목 2 측정값 150.1 — 관리 한계(%' AND NOT is_processed FROM notification WHERE rule_code = 'SPC_OUT'),
            '3σ 밖 점 → 관리도 이상 1건');
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                               instrument_id, inspector_id, measured_at, input_method, remeasure_seq, use_for_judgement,
                               cmm_import_id, cmm_judgement, part_temp_c)
VALUES ('LOT-2609-040-1', 156, 'BRK-A100', 2, 'SAMPLE', NULL, 150.005, 'PASS', 'CMM-01', 'U03', '2026-09-15 10:02+09', 'CMM_AUTO', 1, true,
        :imp, 'PASS', 20.5);
SELECT t.ok((SELECT is_processed AND process_kind = 'AUTO' AND processed_by = 'U03' FROM notification WHERE rule_code = 'SPC_OUT'),
            '다음 부품을 재면 자동 처리');

-- ---------- 로트 납기 지연 위험: 예상 완료(남은 부품 × 3.5분, 근무 시간) > 납기
--   12:00에 LOT-2609-041-1(남은 36개, 앞에 열린 로트 없음) → 126분 → 휴식 지나 15:06
SELECT t.eq(fn_lot_expected_complete('LOT-2609-041-1'), '2026-09-15 15:06+09'::timestamptz, '예상 완료 = 지금 + 남은 36개 × 3.5분 (휴식 뺌)');
SELECT t.eq(fn_raise_lot_due_risk(), 0, '납기(9/16 14:00) 안이면 알림 없음');
UPDATE production_order SET due_at = '2026-09-15 14:00+09' WHERE order_no = 'PO-2609-041';
SELECT t.eq(fn_raise_lot_due_risk(), 1, '예상 완료가 납기보다 늦으면 1건');
SELECT t.eq(fn_raise_lot_due_risk(), 0, '로트마다 1번');
SELECT t.ok((SELECT message LIKE '[납기] LOT-2609-041-1 예상 완료 09/15 15:06가 납기 09/15 14:00보다 늦음' FROM notification WHERE rule_code = 'LOT_DUE_RISK'),
            '문장에 예상 완료·납기');
SELECT t.eq((SELECT expected_complete_at FROM v_production_lot WHERE lot_no = 'LOT-2609-041-1'), '2026-09-15 15:06+09'::timestamptz,
            '로트 목록(v_production_lot)의 예상 완료 시각도 채움');

-- ---------- 알림 폭주 (FR-AST-02-12, 중): 10분에 10건 넘으면 켜짐 → 5건 아래로 내려가면 풀림
SELECT t.freeze('2026-09-16 10:00+09');
SELECT fn_raise_notification('WIP_WARN', '폭주 시험 ' || g, '{"buffer_code": "WIP-10-20"}', '2026-09-16 09:55+09'::timestamptz + make_interval(secs => g))
  FROM generate_series(1, 11) g;
SELECT t.ok((SELECT active AND count_10min = 11 FROM fn_flood_state('2026-09-16 09:56+09')), '10분에 11건 → 폭주');
SELECT t.ok((SELECT is_flood FROM notification WHERE message = '폭주 시험 11'), '11번째 알림에 폭주 표시');
SELECT t.ok(NOT (SELECT is_flood FROM notification WHERE message = '폭주 시험 10'), '10건까지는 폭주 아님');
SELECT t.ok((SELECT active FROM fn_flood_state('2026-09-16 10:05:04+09')), '5건 이상 남아 있으면 계속 폭주 (10:05:04 → 최근 10분 7건)');
SELECT t.ok(NOT (SELECT active FROM fn_flood_state('2026-09-16 10:05:07+09')), '5건 아래(10:05:07 → 4건)로 내려가면 풀림');
SELECT t.ok(NOT (SELECT active FROM fn_flood_state('2026-09-16 09:55:09+09')), '9건까지는 켜지지 않음');

ROLLBACK;
