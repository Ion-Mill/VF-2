-- 지표 (R-44·R-45), 보고 순위 (6.43), 잠금 중 설비 (R-53), 보관 기간 보고 (R-75)
BEGIN;
SELECT t.freeze('2026-09-15 17:00+09');
-- VF2-01 9/15 주간: RUN 08:00~10:55 (175분) + 10:57~10:58 (1분) = 176분, DOWN 10:55~10:57 + 10:58~17:00 = 364분
SELECT t.eq((SELECT run_min FROM v_shift_equipment_kpi WHERE shift_id = '2026-09-15-D' AND equipment_id = 'VF2-01'), 176.00::numeric, 'RUN 분');
SELECT t.eq((SELECT down_min FROM v_shift_equipment_kpi WHERE shift_id = '2026-09-15-D' AND equipment_id = 'VF2-01'), 364.00::numeric, 'DOWN 분');
SELECT t.eq((SELECT availability_pct FROM v_shift_equipment_kpi WHERE shift_id = '2026-09-15-D' AND equipment_id = 'VF2-01'), 36.7::numeric,
            'R-45 가동률 = 176 ÷ 480');
-- E = 7.0 × PQ(20) ÷ 176 = 79.5%, QBR = 100% → OEE = 0.3667 × 0.7955 × 1 = 29.2%
SELECT t.eq((SELECT performance_pct FROM v_shift_equipment_kpi WHERE shift_id = '2026-09-15-D' AND equipment_id = 'VF2-01'), 79.5::numeric, '성능');
SELECT t.eq((SELECT oee_pct FROM v_shift_equipment_kpi WHERE shift_id = '2026-09-15-D' AND equipment_id = 'VF2-01'), 29.2::numeric, 'OEE');
-- VF2-02: MAINT 90분 → PBT = 480 − 90 = 390 (R-44)
SELECT t.eq((SELECT pbt_min FROM v_shift_equipment_kpi WHERE shift_id = '2026-09-15-D' AND equipment_id = 'VF2-02'), 390.00::numeric,
            'R-44 PBT = 480 − 정비');

-- R-53 잠금 중 설비: MR-0901이 6.4 체크, 7.3 아직 → VF2-01 잠금 → 보고 순위 0 (맨 위)
SELECT t.eq((SELECT equipment_id FROM v_lock_status), 'VF2-01', 'R-53 잠금 중 설비');
SELECT fn_raise_notification('ALARM_STOP', 'VF2-01 알람 992', '{"alarm_event_id": 3, "equipment_id": "VF2-01"}', '2026-09-15 10:58+09');
SELECT fn_raise_notification('ALARM_WARN', 'VF2-01 알람 108', '{"alarm_event_id": 1, "equipment_id": "VF2-01"}', '2026-09-15 10:52+09');
SELECT fn_raise_notification('WIP_WARN', 'WIP-20-30 재공 22개', '{"buffer_code": "WIP-20-30"}', '2026-09-15 16:00+09');
SELECT fn_raise_notification('PM_DUE_SOON', '내일 예방 정비', '{"pm_task_id": "PM-VF2-02-2.3-01"}', '2026-09-15 16:10+09');
SELECT t.eq((SELECT string_agg(report_rank, ',' ORDER BY rank_order, rank_group, occurred_at) FROM v_report_lines), 'R0,R1,R2,R3,R4',
            '6.43 순서: 안전 → 긴급 → 생산 위험 → 주의 → 참고 (화면 줄)');
SELECT t.eq((SELECT title FROM v_report_lines ORDER BY rank_order LIMIT 1), '잠금·표지 중: VF2-01', '잠금 중 설비가 맨 위');
-- 하루가 지나면 처리 안 된 주의 알림은 0-1로 올라감
SELECT t.freeze('2026-09-16 12:00+09');
SELECT t.eq((SELECT string_agg(report_rank, ',' ORDER BY rank_order, rank_group, occurred_at) FROM v_report_lines), 'R0,R0_1,R1,R2,R4',
            '24시간 넘은 주의 알림(108, 25시간)만 0-1로, 재공 경고(20시간)는 그대로');
-- DOWN 설비와 그 정지 알람 알림은 한 줄 (FR-AST-COM-21 같은 설비·같은 원인 → 1건)
SELECT t.eq((SELECT count(*) FROM v_report_lines WHERE equipment_id = 'VF2-01' AND report_rank = 'R1')::int, 1, '같은 설비 긴급은 한 줄');
SELECT t.eq((SELECT member_count FROM v_report_lines WHERE equipment_id = 'VF2-01' AND report_rank = 'R1'), 2, '묶인 항목 2건 = 1줄');

-- 지금 상태 뷰
SELECT t.eq((SELECT state_code || '/' || open_alarm_code FROM v_equipment_now WHERE equipment_id = 'VF2-01'), 'DOWN/992', '설비 지금 상태');
-- 로트 추적 한 줄
SELECT t.eq((SELECT jsonb_array_length(trace->'operations') FROM v_lot_trace WHERE lot_no = 'LOT-2609-038-1'), 5, '로트 추적: 공정 5개');
SELECT t.eq((SELECT trace->'material'->>'material_lot_no' FROM v_lot_trace WHERE lot_no = 'LOT-2609-038-1'), 'MAT-2609-05', '로트 추적: 원자재');
-- 예방 정비 다음 기한 (매월: 9/15 + 1달)
SELECT t.eq((SELECT next_due_date FROM v_pm_task_due WHERE pm_task_id = 'PM-VF2-02-2.3-01'), '2026-10-15'::date, 'R-43 다음 기한');
-- 보관 기간 보고: 30일 데이터라 지난 행 없음
SELECT t.eq((SELECT sum(rows_past) FROM fn_retention_report())::int, 0, 'R-75 시연 데이터는 지워질 행 없음');
SELECT t.ok((SELECT sum(rows_past) FROM fn_retention_report('2028-12-01 00:00+09')) > 0, '2년 뒤 시각으로 보면 지난 행이 나옴');
ROLLBACK;
