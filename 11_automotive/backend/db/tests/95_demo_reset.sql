-- 시연 데이터 처음으로 (API명세서 SIM-03): 목업 뒤 만든 기준점(dev/90)으로 되돌림
BEGIN;
SELECT t.throws($$SELECT count(*) FROM demo_snapshot.meta$$, 'permission denied', '앱 계정은 기준점을 직접 못 읽음')
  WHERE current_user = 'mom_app';
SELECT t.freeze('2026-09-15 15:00+09');
-- 시연 중에 바뀐 것들
SELECT fn_ingest_alarm('VF2-02', '254', '2026-09-15 14:00+09');
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U10', confirmed_at = app_now() WHERE shift_id = '2026-09-15-D';
SELECT fn_tool_change('VF2-01-T05', 'U02', 'LIFE_90', NULL, '2026-09-15 14:30+09');
SELECT t.ok((SELECT count(*) FROM alarm_event) = 4 AND (SELECT on_hand_qty FROM inventory_item WHERE item_no = 'TL-TAP6') = 9,
            '시연 중: 알람 4건, M6 탭 재고 9');
-- 되돌리기
SELECT t.eq((fn_demo_reset() ->> 'tables')::int > 50, true, '운영 표를 기준점으로 되돌림');
SELECT t.eq((SELECT count(*)::int FROM alarm_event), 3, '시연 중 알람이 없어짐');
SELECT t.eq((SELECT status FROM shift_report WHERE shift_id = '2026-09-15-D'), 'AI_DRAFT', '확정 전으로');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'TL-TAP6'), 10.000::numeric, '재고도 그대로 (트리거로 두 번 더하지 않음)');
SELECT t.eq((SELECT cum_usage FROM tool WHERE tool_id = 'VF2-01-T05'), 340.000::numeric, '공구 누적도 기준점 값');
SELECT t.ok((SELECT is_paused FROM sim_clock), '시연 시계는 기준점 시각에 멈춤');
SELECT t.eq((SELECT count(*)::int FROM role_permission) > 0 AND (SELECT count(*) FROM app_user) = 12, true, '설정·계정은 그대로');
-- 일련번호가 이어지고 트리거가 다시 돈다 (함수 밖에서는 replica 아님)
SELECT t.eq(fn_ingest_alarm('VF2-02', '254', '2026-09-15 14:05+09'), 4::bigint, '알람 번호가 4부터 다시');
SELECT t.ok(EXISTS (SELECT 1 FROM notification WHERE alarm_event_id = 4), '되돌린 뒤에도 알림 트리거·함수가 돈다');
SELECT t.eq(current_setting('session_replication_role'), 'origin', 'replica는 함수 안에서만');
ROLLBACK;
