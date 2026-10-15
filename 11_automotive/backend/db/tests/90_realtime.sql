-- 실시간 받기: 상태 바뀜(fn_state_change)·실적 더하기(fn_report_production)·정지 손실 계산 (70_realtime)
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');

-- 상태 바뀜: VF2-02 RUN(12:00~) → IDLE 13:00. 열린 구간이 닫히고 새 구간이 열림
SELECT t.ok(fn_state_change('VF2-02', 'IDLE', '2026-09-15 13:00+09', 'READY', false, 'M01') > 0, 'IDLE 구간 열기');
SELECT t.eq((SELECT end_at FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND start_at = '2026-09-15 12:00+09'),
            '2026-09-15 13:00+09'::timestamptz, '앞 RUN 구간 닫힘');
SELECT t.eq((SELECT reason_status FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND end_at IS NULL), 'SUGGESTED', '제안 사유 → SUGGESTED');
-- 같은 상태를 또 보내면 새 구간을 만들지 않음 (중복 전송)
SELECT t.eq(fn_state_change('VF2-02', 'IDLE', '2026-09-15 13:01+09', 'READY', false, 'M01'),
            (SELECT state_log_id FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND end_at IS NULL), '같은 상태 다시 → 같은 구간');
-- 시각이 거꾸로면 막음 (R-04)
SELECT t.throws($$SELECT fn_state_change('VF2-02', 'RUN', '2026-09-15 12:30+09', 'ACTIVE')$$, 'R-04', '지금 구간 시작보다 앞 시각');
-- DOWN은 정지 등급 알람이 있어야 함
SELECT t.throws($$SELECT fn_state_change('VF2-02', 'DOWN', '2026-09-15 13:05+09', 'STOPPED')$$, 'ck_state_down_alarm', 'DOWN인데 알람 없음');
-- IDLE 13:00~13:14 (14분) 닫힘 → 정지 손실 = 14 ÷ 7.0 = 2.00
SELECT fn_state_change('VF2-02', 'RUN', '2026-09-15 13:14+09', 'ACTIVE');
SELECT t.eq((SELECT stop_loss_qty FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND start_at = '2026-09-15 13:00+09'),
            2.00::numeric, '정지 손실 = 구간 길이 ÷ 기준 사이클');
-- 사유를 계획 정지(P02)로 고치면 손실 계산 안 함
UPDATE equipment_state_log SET reason_code = 'P02', reason_status = 'ENTERED', reason_entered_by = 'U02'
 WHERE equipment_id = 'VF2-02' AND start_at = '2026-09-15 13:00+09';
SELECT t.ok((SELECT stop_loss_qty IS NULL FROM equipment_state_log WHERE equipment_id = 'VF2-02' AND start_at = '2026-09-15 13:00+09'),
            '계획 정지는 손실 계산 안 함');
-- 적재한 값(생성기)은 INSERT 때 그대로 둔다: 목업 DOWN 구간 0.29
SELECT t.eq((SELECT stop_loss_qty FROM equipment_state_log WHERE alarm_event_id = 2), 0.29::numeric, '적재한 손실 값 유지');

-- 실적 더하기: 같은 로트·공정·설비·교대는 한 행에 더함 → OP-30이면 공구 사용 누적
SELECT t.freeze('2026-09-15 13:20+09');
SELECT t.eq((SELECT cum_usage FROM tool WHERE tool_id = 'VF2-02-T05'), 120::numeric, '탭 누적 처음 120');
SELECT t.ok(fn_report_production('LOT-2609-041-1', 'VF2-02', 'U02', 2) > 0, '실적 2개');
SELECT t.eq((SELECT pq || '/' || gq FROM operation_report WHERE lot_no = 'LOT-2609-041-1' AND equipment_id = 'VF2-02'), '18/18', '16 + 2 = 18');
SELECT t.eq((SELECT cum_usage FROM tool WHERE tool_id = 'VF2-02-T05'), 120 + 2 * (SELECT usage_per_part FROM tool_type WHERE item_no = 'TL-TAP6'),
            '공구 사용 = 부품 수 × 부품당 사용');
SELECT t.throws($$SELECT fn_report_production('LOT-2609-041-1', 'VF2-02', 'U02', 0)$$, '0', '0개 실적은 받지 않음');
SELECT t.throws($$SELECT fn_report_production('LOT-2609-041-1', 'VF2-02', 'U02', 1, 0, 0, '2026-09-15 18:00+09')$$, '교대가 없음',
                '교대 밖 시각 실적');
-- OP-10 실적은 공구 누적 없음 + 새 행
SELECT fn_report_production('LOT-2609-041-1', 'SAW-01', 'U01', 1, 0, 0, '2026-09-15 13:20+09');
SELECT t.eq((SELECT pq FROM operation_report WHERE lot_no = 'LOT-2609-041-1' AND process_code = 'OP-10'), 37, 'OP-10 36 + 1');
ROLLBACK;

-- 작업지시·로트 투입·검사 대기 (시뮬레이터 실시간)
BEGIN;
SELECT t.freeze('2026-09-15 14:00+09');
SELECT t.eq(fn_create_order('BRK-A100', 72, '2026-09-17 17:00+09'), 'PO-2609-042', '작업지시 번호 PO-2609-042');
CREATE TEMP TABLE before_rm AS SELECT on_hand_qty FROM inventory_item WHERE item_no = 'RM-6061';
SELECT t.eq(fn_start_lot('PO-2609-042', 'MAT-2609-05', 36), 'LOT-2609-042-1', '첫 로트 LOT-2609-042-1');
SELECT t.eq((SELECT status || '/' || (started_at IS NOT NULL) FROM production_order WHERE order_no = 'PO-2609-042'), 'IN_PROGRESS/true',
            '첫 투입 → 작업지시 생산 중');
SELECT t.eq((SELECT input_shift_id FROM production_lot WHERE lot_no = 'LOT-2609-042-1'), '2026-09-15-D', '투입 교대 = 그 시각 교대');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'RM-6061'), (SELECT on_hand_qty - 36 FROM before_rm), '원자재 36 사용');
SELECT t.eq((SELECT plan_mode FROM inspection_plan WHERE lot_no = 'LOT-2609-042-1'), 'NORMAL', '검사 방식 만들어짐');
SELECT t.eq(fn_start_lot('PO-2609-042', 'MAT-2609-05', 36), 'LOT-2609-042-2', '둘째 로트');
SELECT t.throws($$SELECT fn_start_lot('PO-2609-042', 'MAT-2609-05', 1)$$, 'R-08', '작업지시 수량을 넘는 투입');
SELECT fn_lot_to_inspection('LOT-2609-042-1');
SELECT t.eq((SELECT status FROM production_lot WHERE lot_no = 'LOT-2609-042-1'), 'WAIT_INSPECTION', 'OP-50 도착 → 검사 대기');
SELECT t.throws($$SELECT fn_lot_to_inspection('LOT-2609-042-1')$$, '생산 중이 아님', '두 번 바꾸기 불가');
SELECT t.freeze('2026-09-15 18:00+09');
SELECT t.throws($$SELECT fn_start_lot('PO-2609-042', 'MAT-2609-05', 1)$$, 'R-08', '수량 확인이 먼저');
ROLLBACK;

