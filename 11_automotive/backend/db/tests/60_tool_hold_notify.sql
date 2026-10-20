-- 공구 사용·교체 (R-10·R-40·R-41, 공구 사용 기록 B안), 로트 보류·검사 강화 (R-27·R-28), 알림 묶기·반복 알람 (R-38·R-70)
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');

-- 공구: 041-1의 VF2-01 실적에 5개 → T05(M6 탭 4구멍/개) 340 + 20 = 360 = 90% → 교체 알림
SELECT t.eq(fn_add_tool_usage((SELECT op_report_id FROM operation_report WHERE lot_no = 'LOT-2609-041-1' AND equipment_id = 'VF2-01'), 5), 5,
            '공구 5개에 사용량 더함');
SELECT t.eq((SELECT cum_usage FROM tool WHERE tool_id = 'VF2-01-T05'), 360.000::numeric, 'R-10 누적 = 340 + 5 × 4');
SELECT t.eq((SELECT usage_rate_pct FROM v_tool_life WHERE tool_id = 'VF2-01-T05'), 90.0::numeric, '사용률 90%');
SELECT t.ok(EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TOOL_LIFE_90' AND tool_id = 'VF2-01-T05' AND NOT is_processed),
            'R-40 사용률 90% 교체 알림');
-- 교체: 누적 0, 재고 1개 차감, 알림 자동 처리
SELECT t.throws($$SELECT fn_tool_change('VF2-01-T05', 'U10', 'LIFE_90')$$, 'OPR', '공구 교체는 OPR·MNT');
SELECT fn_tool_change('VF2-01-T05', 'U02', 'LIFE_90', NULL, '2026-09-15 13:05+09');
SELECT t.eq((SELECT cum_usage FROM tool WHERE tool_id = 'VF2-01-T05'), 0.000::numeric, '교체 뒤 누적 0');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'TL-TAP6'), 9.000::numeric, 'R-41 M6 탭 1개 차감');
SELECT t.ok((SELECT is_processed AND process_kind = 'AUTO' FROM notification WHERE rule_code = 'TOOL_LIFE_90' AND tool_id = 'VF2-01-T05'),
            '교체 기록으로 수명 알림 자동 처리');
-- 페이스밀은 교체 1회에 5개 (6.25)
SELECT fn_tool_change('VF2-02-T01', 'U07', 'BROKEN', NULL, '2026-09-15 13:06+09');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'TL-FM50'), 15.000::numeric, '페이스밀 인서트 5개 차감');
-- 같은 실적에서 교체 뒤 3개 더 → 구간 2 (교체 기록과 연결)
SELECT fn_add_tool_usage((SELECT op_report_id FROM operation_report WHERE lot_no = 'LOT-2609-041-1' AND equipment_id = 'VF2-01'), 3,
                         '2026-09-15 13:30+09');
SELECT t.eq((SELECT seg || '/' || parts_qty || '/' || cum_after FROM tool_usage WHERE tool_id = 'VF2-01-T05' ORDER BY seg DESC LIMIT 1),
            '2/3/12.000', '교체 뒤 구간 2: 3개, 누적 12');
SELECT t.ok((SELECT tool_change_id IS NOT NULL FROM tool_usage WHERE tool_id = 'VF2-01-T05' AND seg = 2), '구간 2는 교체 기록을 가리킴');
SELECT t.eq((SELECT seg || '/' || parts_qty FROM tool_usage WHERE tool_id = 'VF2-01-T02' ORDER BY seg DESC LIMIT 1), '1/8',
            '교체 없는 공구는 구간 1에 더함');

-- 로트 보류 (사람만): 041-1 의심 로트 → 보류, 검사 강화
SELECT t.throws($$SELECT fn_lot_hold('LOT-2609-041-1', 'U02', 'AI_SUSPECT', '충돌 의심')$$, 'SUP', '보류는 SUP·MGR만');
SELECT fn_lot_hold('LOT-2609-041-1', 'U10', 'AI_SUSPECT', '정지 등급 알람 992 중 가공 (충돌 의심)', 2, 3);
SELECT t.eq((SELECT status FROM production_lot WHERE lot_no = 'LOT-2609-041-1'), 'ON_HOLD', '로트 보류');
SELECT t.eq((SELECT plan_mode || '/' || enhance_reason FROM inspection_plan WHERE lot_no = 'LOT-2609-041-1'), 'ENHANCED/HOLD_LOT',
            'R-28 보류 로트 검사 강화');
SELECT t.throws($$SELECT fn_lot_hold('LOT-2609-041-1', 'U10', 'SUPERVISOR', '또')$$, 'ux_lot_hold_open', '열린 보류는 하나');
-- 다음 로트 2개는 강화, 세 번째는 보통 (R-28: 충돌·정지 등급 → 2개)
INSERT INTO production_order (order_no, product_code, order_qty, created_at, due_at, status, started_at)
VALUES ('PO-2609-042', 'BRK-A100', 60, '2026-09-15 13:00+09', '2026-09-16 14:00+09', 'IN_PROGRESS', '2026-09-15 13:10+09');
INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty) VALUES
  ('LOT-2609-042-1', 'PO-2609-042', 1, '2026-09-15-D', 'MAT-2609-05', 20),
  ('LOT-2609-042-2', 'PO-2609-042', 2, '2026-09-15-D', 'MAT-2609-05', 20),
  ('LOT-2609-042-3', 'PO-2609-042', 3, '2026-09-15-D', 'MAT-2609-05', 20);
SELECT t.eq(fn_create_inspection_plan('LOT-2609-042-1'), 'ENHANCED', '다음 로트 1 강화');
SELECT t.eq(fn_create_inspection_plan('LOT-2609-042-2'), 'ENHANCED', '다음 로트 2 강화');
SELECT t.eq(fn_create_inspection_plan('LOT-2609-042-3'), 'NORMAL', '세 번째는 보통');
SELECT t.eq((SELECT count(*) FROM fn_planned_parts('LOT-2609-042-1'))::int, 20, '강화 로트는 전수');
-- 해제: 고른 합격 수량만 완제품 (R-69 ②). 041-1은 아직 OP-50 실적이 없어 완료 수량 0 → 해제 수량 초과 막힘
SELECT t.throws($$SELECT fn_lot_release((SELECT hold_id FROM lot_hold WHERE lot_no = 'LOT-2609-041-1'), 'U10', 10)$$,
                '완료 수량', '완료 수량보다 많이 해제 불가');
SELECT t.throws($$SELECT fn_lot_release((SELECT hold_id FROM lot_hold WHERE lot_no = 'LOT-2609-041-1'), 'U10', 0)$$,
                '1개 이상', '합격 0개 해제 불가 (전부 불량이면 폐기)');
-- 폐기: 반장 제안 → 관리자 승인
SELECT fn_lot_scrap_propose((SELECT hold_id FROM lot_hold WHERE lot_no = 'LOT-2609-041-1'), 'U10', 36);
SELECT t.throws($$SELECT fn_lot_scrap_approve((SELECT hold_id FROM lot_hold WHERE lot_no = 'LOT-2609-041-1'), 'U10')$$,
                'MGR', '폐기 승인은 MGR만');
SELECT fn_lot_scrap_approve((SELECT hold_id FROM lot_hold WHERE lot_no = 'LOT-2609-041-1'), 'U12');
SELECT t.eq((SELECT status || '/' || scrap_qty FROM production_lot WHERE lot_no = 'LOT-2609-041-1'), 'SCRAPPED/36', '로트 폐기');

-- 알림 묶기: 같은 설비·같은 알람이 1분 안에 또 나면 첫 알림에 횟수만 (DOC-07 10.2, FR-AST-02-11 — 2026-10-20 "3번 → 1건")
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES
  ('VF2-02', '314', 'GUIDE', '2026-09-15 13:00:05+09'), ('VF2-02', '314', 'GUIDE', '2026-09-15 13:00:20+09'),
  ('VF2-02', '314', 'GUIDE', '2026-09-15 13:00:40+09');
SELECT fn_raise_notification('ALARM_GUIDE', '314', jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', 'VF2-02'),
                             a.occurred_at)
  FROM alarm_event a WHERE alarm_code = '314' ORDER BY occurred_at;
SELECT t.eq((SELECT count(*)::text || '/' || max(repeat_count) FROM notification WHERE rule_code = 'ALARM_GUIDE'), '1/3',
            '1분 안 3번 → 알림 1건 ×3');
SELECT t.throws($$SELECT fn_process_notification((SELECT min(notification_id) FROM notification WHERE rule_code = 'ALARM_GUIDE'), 'U07')$$,
                'OPR·SUP', '조작 안내 알림 처리는 OPR·SUP');
SELECT fn_process_notification((SELECT min(notification_id) FROM notification WHERE rule_code = 'ALARM_GUIDE'), 'U02');
SELECT t.ok(true, '조작 안내 알림 사람 처리');

-- 반복 알람 1단계 → 2단계 (R-70) — VF2-02 알람 108 사례 모양 (설계서 5.8): 9/8·9/9·9/10 → 9/14 재발
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES
  ('VF2-02', '108', 'WARN', '2026-09-08 10:00+09'), ('VF2-02', '108', 'WARN', '2026-09-09 10:00+09'),
  ('VF2-02', '108', 'WARN', '2026-09-10 10:00+09');
SELECT t.eq(fn_check_repeat_alarm(a.alarm_event_id), CASE WHEN a.occurred_at < '2026-09-10' THEN 'NONE' ELSE 'STAGE1' END, '반복 판정 ' || a.occurred_at::date)
  FROM alarm_event a WHERE equipment_id = 'VF2-02' AND alarm_code = '108' ORDER BY occurred_at;
SELECT t.throws($$SELECT fn_process_notification((SELECT notification_id FROM notification WHERE rule_code = 'REPEAT_ALARM'), 'U07', '')$$,
                'ck_notification_repeat_memo', '1단계 처리는 조치 계획 한 줄 필수');
SELECT fn_process_notification((SELECT notification_id FROM notification WHERE rule_code = 'REPEAT_ALARM'), 'U07',
                               '축 윤활·볼스크류 점검 일정 앞당김', '2026-09-10 15:00+09');
SELECT t.eq((SELECT repeat_stage_status FROM notification WHERE rule_code = 'REPEAT_ALARM'), 'S1_CLOSED', '1단계 닫힘');
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES ('VF2-02', '108', 'WARN', '2026-09-14 09:00+09');
SELECT t.eq(fn_check_repeat_alarm(currval(pg_get_serial_sequence('alarm_event','alarm_event_id'))), 'STAGE2', '조치 계획 뒤 7일 안 재발 → 2단계');
SELECT t.eq((SELECT repeat_stage_status || '/' || (prev_stage_notification_id IS NOT NULL) FROM notification WHERE rule_code = 'REPEAT_ALARM_2'),
            'S2_OPEN/true', '2단계 알림은 1단계를 가리킴');
SELECT t.eq((SELECT repeat_stage_status FROM notification WHERE rule_code = 'REPEAT_ALARM'), 'ESCALATED', '1단계는 다음 단계로 넘어감');
SELECT t.ok(NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CAUSE_CHECK_REQUEST'), 'OP-30은 원인 점검 요청 대신 작업지시서');
-- 다른 공정(OP-10 SAW-01 5303.00): 2단계면 MNT에게 원인 점검 요청 (R-71)
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES
  ('SAW-01', '5303.00', 'WARN', '2026-09-01 10:00+09'), ('SAW-01', '5303.00', 'WARN', '2026-09-02 10:00+09'),
  ('SAW-01', '5303.00', 'WARN', '2026-09-03 10:00+09');
SELECT fn_check_repeat_alarm(alarm_event_id) FROM alarm_event WHERE alarm_code = '5303.00' ORDER BY occurred_at;
SELECT fn_process_notification((SELECT notification_id FROM notification WHERE rule_code = 'REPEAT_ALARM' AND equipment_id = 'SAW-01'),
                               'U10', '가이드 레일 윤활 점검', '2026-09-03 12:00+09');
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES ('SAW-01', '5303.00', 'WARN', '2026-09-05 10:00+09');
SELECT t.eq(fn_check_repeat_alarm(currval(pg_get_serial_sequence('alarm_event','alarm_event_id'))), 'STAGE2', '다른 공정 2단계');
SELECT t.ok(EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CAUSE_CHECK_REQUEST' AND equipment_id = 'SAW-01'),
            'R-71 다른 공정은 MNT 원인 점검 요청');
SELECT t.eq((SELECT string_agg(DISTINCT u.role_code, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              JOIN app_user u USING (user_id) WHERE n.rule_code = 'CAUSE_CHECK_REQUEST'), 'MNT', '원인 점검 요청 받는 사람 = MNT');
-- 원인 점검 간이 기록 확정 → 요청·2단계 자동 처리, 효과 확인 기한 +7일
INSERT INTO work_record (record_no, record_type, cause_check_notification_id, equipment_id, action, start_at, safety_block_required, status)
VALUES ('MR-S-0910', 'SIMPLE', (SELECT notification_id FROM notification WHERE rule_code = 'CAUSE_CHECK_REQUEST'), 'SAW-01',
        '레일 윤활 펌프 점검', '2026-09-05 13:00+09', false, 'EDITING');
SELECT t.throws($$SELECT fn_confirm_work_record('MR-S-0910', 'U01')$$, 'MNT', '원인 점검 간이 기록 확정은 MNT');
SELECT fn_confirm_work_record('MR-S-0910', 'U09', '2026-09-05 14:00+09');
SELECT t.eq((SELECT repeat_stage_status || '/' || is_processed || '/' || (effect_check_due_at = '2026-09-12 14:00+09')
               FROM notification WHERE rule_code = 'REPEAT_ALARM_2' AND equipment_id = 'SAW-01'), 'S2_CHECKED/true/true',
            '원인 점검 확정 → 2단계 처리, 7일 효과 확인 기한');

-- 재고 부족 (R-39): 축 윤활유 4L 이하 → 관리 역할(MNT) + MGR
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, memo)
VALUES ('CS-WLUB', 'ADJUST', -2.5, '2026-09-15 13:40+09', 'U07', 'STOCKTAKE', '실사 차이');
SELECT fn_check_stock('CS-WLUB', 'U07');
SELECT t.eq((SELECT string_agg(DISTINCT u.role_code, ',' ORDER BY u.role_code) FROM notification n JOIN notification_recipient r USING (notification_id)
              JOIN app_user u USING (user_id) WHERE n.rule_code = 'STOCK_LOW'), 'MGR,MNT', 'R-39 재고 부족 → 관리 역할 + MGR');
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind) VALUES ('CS-WLUB', 'IN', 6, '2026-09-15 14:00+09', 'U07', 'RECEIPT');
SELECT fn_check_stock('CS-WLUB', 'U07');
SELECT t.ok((SELECT is_processed FROM notification WHERE rule_code = 'STOCK_LOW'), '입고로 안전 재고를 넘으면 자동 처리');
ROLLBACK;
