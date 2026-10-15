-- =====================================================================
-- 50_retention.sql — 데이터 보관 기간 (NFR-DATA-13, 논리 ERD 6.53, R-75)
-- 실제 삭제·집계·보관 저장소 이동 방식은 [선택 필요: 기술 회의]라서,
-- 여기서는 "기간이 지난 행이 몇 개인지" 보여 주는 보고 함수만 둔다 (지우지 않음).
-- 30일 가상 데이터에서는 모든 값이 0이어야 한다 (설계서 5.19 "시연에서 지워지는 기록은 없다").
-- =====================================================================

CREATE OR REPLACE FUNCTION fn_retention_report(p_now timestamptz DEFAULT NULL)
RETURNS TABLE (rule_no int, stage text, table_name text, keep_for text, after_that text, rows_past bigint)
LANGUAGE sql STABLE AS $$
    WITH n AS (SELECT coalesce(p_now, app_now()) AS now)
    -- #1 L1 센서 5초(SEC5): 90일. 단, 정지 등급 알람 + 작업기록서가 있는 구간(앞뒤 30분)은 2년
    SELECT 1, 'L1', 'sensor_sample_5s', '90일 (정지 알람+작업기록서 구간 2년)', '삭제',
           (SELECT count(*) FROM sensor_sample_5s s, n
             WHERE s.sampled_at < n.now - interval '90 days'
               AND NOT (s.sampled_at >= n.now - interval '2 years' AND EXISTS (
                    SELECT 1 FROM alarm_event a JOIN work_record w ON w.alarm_event_id = a.alarm_event_id
                                                 OR w.wo_no IN (SELECT wo_no FROM maintenance_work_order m WHERE m.alarm_event_id = a.alarm_event_id)
                     WHERE a.equipment_id = s.equipment_id AND a.severity_at_event = 'STOP'
                       AND s.sampled_at BETWEEN a.occurred_at - interval '30 minutes' AND a.occurred_at + interval '30 minutes')))
    UNION ALL
    SELECT 2, 'L2', 'sensor_sample_1m', '1년', '1시간 집계(sensor_hourly)로 줄임',
           (SELECT count(*) FROM sensor_sample_1m, n WHERE sampled_at < n.now - interval '1 year')
    UNION ALL
    SELECT 3, 'L2', 'wip_log', '1년', '1시간 집계(wip_hourly)로 줄임',
           (SELECT count(*) FROM wip_log, n WHERE logged_at < n.now - interval '1 year')
    UNION ALL
    SELECT 2, 'L2', 'sensor_hourly', '집계 2년', '삭제',
           (SELECT count(*) FROM sensor_hourly, n WHERE hour_at < n.now - interval '2 years')
    UNION ALL
    SELECT 4, 'L3', 'equipment_state_log', '2년', '삭제',
           (SELECT count(*) FROM equipment_state_log, n WHERE coalesce(end_at, start_at) < n.now - interval '2 years')
    UNION ALL
    -- #5 보류·의심 로트와 연결된 알람은 15년 (#9와 같이)
    SELECT 5, 'L3', 'alarm_event', '2년 (보류 로트 연결 알람은 15년)', '삭제',
           (SELECT count(*) FROM alarm_event a, n WHERE a.occurred_at < n.now - interval '2 years'
               AND NOT EXISTS (SELECT 1 FROM lot_hold h WHERE h.related_alarm_event_id = a.alarm_event_id))
    UNION ALL
    SELECT 6, 'L3', 'bottleneck_log', '2년', '삭제',
           (SELECT count(*) FROM bottleneck_log, n WHERE changed_at < n.now - interval '2 years')
    UNION ALL
    SELECT 7, 'L3', 'notification', '2년', '삭제',
           (SELECT count(*) FROM notification, n WHERE raised_at < n.now - interval '2 years')
    UNION ALL
    -- #8 공구·소모품·예비품 입출고 = 원자재·완제품 아닌 것 (DOC-07 §11 Rev.2)
    SELECT 8, 'L3', 'inventory_txn (공구·소모품)', '2년', '삭제',
           (SELECT count(*) FROM inventory_txn t JOIN inventory_item i USING (item_no), n
             WHERE i.category NOT IN ('MATERIAL','FINISHED') AND t.txn_at < n.now - interval '2 years')
    UNION ALL
    -- L4는 운영 DB 2년 → 보관 저장소(읽기 전용) → 15년 뒤 삭제 [15년은 임시값]
    SELECT 9, 'L4', 'production_lot (로트 추적 사슬)', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM production_lot l, n
             WHERE coalesce((SELECT max(s.shipped_at) FROM shipment_line sl JOIN shipment s USING (shipment_no)
                              WHERE sl.lot_no = l.lot_no), l.judged_at) < n.now - interval '2 years')
    UNION ALL
    -- #9 로트 추적 사슬에 원자재 투입·완제품 입출고(inventory_txn)와 검사 계획(inspection_plan)도 들어간다 (DOC-07 §11 Rev.2)
    SELECT 9, 'L4', 'inventory_txn (원자재·완제품)', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM inventory_txn t JOIN inventory_item i USING (item_no), n
             WHERE i.category IN ('MATERIAL','FINISHED') AND t.txn_at < n.now - interval '2 years')
    UNION ALL
    SELECT 9, 'L4', 'inspection_plan', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM inspection_plan p JOIN production_lot l USING (lot_no), n
             WHERE coalesce(p.judged_at, l.judged_at) < n.now - interval '2 years')
    UNION ALL
    SELECT 10, 'L4', 'inspection_result', '운영 2년 → 보관 15년', '보관 저장소로 이동 (측정값 삭제 금지)',
           (SELECT count(*) FROM inspection_result, n WHERE measured_at < n.now - interval '2 years')
    UNION ALL
    -- cmm_import·원본 결과 파일의 기간은 [선택 필요: 팀] (논리 ERD 6.53 #10) — #10과 같게 하는 것을 [제안]으로 셈
    SELECT 10, 'L4', 'cmm_import', '[선택 필요: 팀] (제안: #10과 같게)', '보관 저장소로 이동 (제안)',
           (SELECT count(*) FROM cmm_import, n WHERE received_at < n.now - interval '2 years')
    UNION ALL
    SELECT 11, 'L4', 'shipment', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM shipment, n WHERE shipped_at < n.now - interval '2 years')
    UNION ALL
    SELECT 12, 'L4', 'work_record', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM work_record, n WHERE confirmed_at < n.now - interval '2 years')
    UNION ALL
    SELECT 14, 'L4', 'shift_report', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM shift_report r JOIN shift s USING (shift_id), n WHERE r.confirmed_at < n.now - interval '2 years')
    UNION ALL
    SELECT 18, 'CHAT', 'chat_log', '30일 (질문 시각부터, 2026-10-13)', '삭제 (fn_purge_chat_log — 스케줄러가 매일)',
           (SELECT count(*) FROM chat_log, n WHERE asked_at < n.now - interval '30 days')
    UNION ALL
    SELECT 19, 'ACCESS_LOG', 'access_log', '1년', '삭제',
           (SELECT count(*) FROM access_log WHERE at < now() - interval '1 year')
    ORDER BY 1, 3;
$$;
COMMENT ON FUNCTION fn_retention_report(timestamptz) IS
    '보관 기간이 지난 행 수 보고 (지우지 않음). 실제 삭제·집계·이동은 [선택 필요: 기술 회의]';

-- AI 비서 채팅 기록 30일 삭제 (6.53 #18, R-75·R-87 — 2026-10-13 팀 결정 [가상]). 다른 보관 규칙과 달리 이것만 실제로 지운다:
-- 팀이 기간과 처리(삭제)를 정했고, 개인 질문 기록이라 오래 둘 이유가 없다. 반환: 지운 행 수
CREATE OR REPLACE FUNCTION fn_purge_chat_log(p_now timestamptz DEFAULT NULL) RETURNS int
LANGUAGE sql AS $$
    WITH d AS (DELETE FROM chat_log WHERE asked_at < coalesce(p_now, app_now()) - interval '30 days' RETURNING 1)
    SELECT count(*)::int FROM d;
$$;
