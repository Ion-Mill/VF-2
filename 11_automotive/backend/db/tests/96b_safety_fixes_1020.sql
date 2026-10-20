-- 2026-10-20 시연 안전·버그 고침 (구현_중_수정사항 1020 35장): 간이 작업기록 잠금·표지 강제, 측정값 위치별 판정,
-- 일부 폐기 → 해제, 예방 정비 기한 알림은 주 1회 이상 주기만
BEGIN;
SELECT t.freeze('2026-09-15 12:00+09');

-- ---------- 1. 간이 작업기록: 알람 잠금 수준이 FULL·TWO_POINT면 화면이 거짓을 보내도 잠금·표지 9단계 필요 (R-32·33)
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 11:50+09', 'LOT-2609-041-1') AS a2075 \gset
INSERT INTO work_record (record_no, record_type, alarm_event_id, equipment_id, action, start_at, safety_block_required, status, current_version)
VALUES ('MR-S-0950', 'SIMPLE', :a2075, 'VF2-02', '(시험) 축 윤활유 보충', '2026-09-15 11:55+09', false, 'EDITING', 0);
SELECT t.ok((SELECT safety_block_required FROM work_record WHERE record_no = 'MR-S-0950'), '2075(보충용 2점 잠금) 간이 기록은 화면이 거짓을 보내도 잠금·표지 필요');
SELECT t.throws($$UPDATE work_record SET status = 'CONFIRMED', confirmed_by = 'U02', confirmed_at = app_now() WHERE record_no = 'MR-S-0950'$$,
                'R-32', '9단계 체크 없이 확정 불가');
UPDATE work_record SET safety_block_required = false WHERE record_no = 'MR-S-0950';
SELECT t.ok((SELECT safety_block_required FROM work_record WHERE record_no = 'MR-S-0950'), '한 번 필요한 잠금·표지는 끌 수 없음');
-- 잠금 수준 NONE 알람(108)은 화면 값 그대로
INSERT INTO work_record (record_no, record_type, alarm_event_id, equipment_id, action, start_at, safety_block_required, status, current_version)
VALUES ('MR-S-0951', 'SIMPLE', 1, 'VF2-01', '(시험) 공구 확인', '2026-09-15 11:55+09', false, 'EDITING', 0);
SELECT t.ok(NOT (SELECT safety_block_required FROM work_record WHERE record_no = 'MR-S-0951'), '잠금 수준 NONE 알람(108)은 거짓 그대로');
SELECT t.ok(fn_simple_record_needs_loto(3), '정지 등급(992, FULL)도 필요');

-- ---------- 3. 측정값: 같은 부품·항목이라도 위치(TOP·MID·BOTTOM)가 다르면 판정에서 빼지 않는다 (R-81)
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_F12_ENHANCED.csv', 'processed/f12.csv',
  '{"cmm_id": "CMM-01", "lot_no": "LOT-2609-038-1", "part_seq": 12, "insp_kind": "ENHANCED", "operator": "U06",
    "measured_at": "2026-09-15T11:10:00+09:00", "part_temp_c": 20.9, "temp_comp": true}',
  '[{"item_seq":1,"position":null,"actual":45.019,"cmm_judgement":"PASS"},{"item_seq":1,"position":"TOP","actual":45.021,"cmm_judgement":"PASS"},
    {"item_seq":1,"position":"MID","actual":45.018,"cmm_judgement":"PASS"},{"item_seq":1,"position":"BOTTOM","actual":45.016,"cmm_judgement":"PASS"}]');
SELECT fn_import_cmm('CMM-01_LOT-2609-038-1_F12_ENHANCED_2.csv', 'processed/f12b.csv',
  '{"cmm_id": "CMM-01", "lot_no": "LOT-2609-038-1", "part_seq": 12, "insp_kind": "ENHANCED", "operator": "U06",
    "measured_at": "2026-09-15T11:20:00+09:00", "part_temp_c": 20.9, "temp_comp": true}',
  '[{"item_seq":1,"position":"TOP","actual":45.022,"cmm_judgement":"PASS"}]');
SELECT fn_check_measurement((SELECT result_id FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 12
                              AND item_seq = 1 AND position = 'TOP' AND remeasure_seq = 2), 'U10', true);
SELECT t.eq((SELECT string_agg(coalesce(position, '표준') || ':' || remeasure_seq, ',' ORDER BY position NULLS FIRST, remeasure_seq)
               FROM inspection_result WHERE lot_no = 'LOT-2609-038-1' AND part_seq = 12 AND item_seq = 1 AND use_for_judgement),
            '표준:1,BOTTOM:1,MID:1,TOP:2', 'TOP 재측정을 판정용으로 고르면 TOP 1회차만 빠지고 표준·MID·BOTTOM은 그대로');

-- ---------- 4. 일부 폐기: 반장 제안 → 관리자 승인(보류는 열린 채 폐기 수량만) → 반장이 나머지 해제 (1013 7장)
SELECT fn_lot_hold('LOT-2609-038-1', 'U10', 'SUPERVISOR', '(시험) 전수 검사') AS h \gset
SELECT hold_id AS hid FROM lot_hold WHERE lot_no = 'LOT-2609-038-1' AND result = 'IN_PROGRESS' \gset
SELECT fn_lot_scrap_propose(:hid, 'U10', 2);
SELECT t.throws($$SELECT fn_lot_release((SELECT hold_id FROM lot_hold WHERE lot_no = 'LOT-2609-038-1' AND result = 'IN_PROGRESS'), 'U10', 34)$$,
                '폐기 승인 대기', '폐기 제안이 있으면 관리자 승인 전에는 해제 불가');
SELECT fn_lot_scrap_approve(:hid, 'U12');
SELECT t.eq((SELECT h.result || '/' || l.status || '/' || l.scrap_qty FROM lot_hold h JOIN production_lot l USING (lot_no) WHERE h.hold_id = :hid),
            'IN_PROGRESS/ON_HOLD/2', '일부 폐기 승인 → 보류는 열린 채, 폐기 수량 2');
SELECT fn_lot_release(:hid, 'U10', 34);
SELECT t.eq((SELECT h.result || '/' || l.status || '/' || h.released_pass_qty FROM lot_hold h JOIN production_lot l USING (lot_no) WHERE h.hold_id = :hid),
            'RELEASED/RELEASED/34', '나머지 34개 해제');

-- ---------- 5. 예방 정비 기한 알림: 달력에 있어도 매일 점검은 알리지 않는다 (주 1회 이상만)
--   목업 PM-VF2-01-2.1-01 = 매일·달력, 마지막 9/14 → 기한 9/15
SELECT t.freeze('2026-09-14 10:00+09');
SELECT fn_run_time_rules(10);
SELECT t.eq((SELECT count(*) FROM notification n LEFT JOIN notification_pm_task l USING (notification_id)
              WHERE n.rule_code = 'PM_DUE_SOON' AND 'PM-VF2-01-2.1-01' IN (n.pm_task_id, l.pm_task_id))::int, 0, '매일 점검은 하루 전 알림 없음');
SELECT t.freeze('2026-09-17 10:00+09');
SELECT fn_run_time_rules(10);
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'PM_OVERDUE' AND pm_task_id = 'PM-VF2-01-2.1-01')::int, 0,
            '매일 점검은 기한 넘김 알림도 없음');

ROLLBACK;
