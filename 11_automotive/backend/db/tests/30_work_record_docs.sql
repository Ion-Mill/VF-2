-- 작업기록서 확정 (R-32·R-34, 6.13 완료 계기, 6.36 자동 처리)과 문서 잠금·버전 (R-35)
BEGIN;
SELECT t.freeze('2026-09-15 12:40+09');

-- 정지 알람 알림 하나 만들어 둔다 (확정되면 자동 처리돼야 함)
SELECT fn_raise_notification('ALARM_STOP', 'VF2-01 알람 992 (정지)', '{"alarm_event_id": 3, "equipment_id": "VF2-01"}');
SELECT t.eq((SELECT count(*) FROM notification_recipient nr JOIN notification n USING (notification_id)
              WHERE n.rule_code = 'ALARM_STOP')::int, 12, '긴급 알림 받는 사람 = 전원 12명 (규칙 기본 역할 — 2026-10-13 로그인한 전원)');
SELECT t.ok((SELECT bool_and(popup_sound) FROM notification_recipient), '긴급은 팝업 + 소리');

-- R-32 잠금·표지 9단계 중 6단계만 → 확정 불가
SELECT t.throws($$SELECT fn_confirm_work_record('MR-0901', 'U07')$$, 'R-32', 'R-32 잠금·표지 9단계 전에 확정 불가');
UPDATE work_record_check SET is_checked = true, checked_by = 'U07', checked_at = app_now()
 WHERE record_no = 'MR-0901' AND check_kind = 'LOTO';
-- 확정은 MNT만 (작업기록서)
SELECT t.throws($$SELECT fn_confirm_work_record('MR-0901', 'U02')$$, 'MNT', '작업기록서 확정은 MNT');
SELECT t.throws($$SELECT fn_confirm_work_record('MR-0901', 'U10')$$, 'MNT', '반장도 작업기록서 확정 불가 (확인만)');
SELECT fn_confirm_work_record('MR-0901', 'U07');
SELECT t.eq((SELECT status FROM work_record WHERE record_no = 'MR-0901'), 'CONFIRMED', '작업기록서 확정');
SELECT t.eq((SELECT repair_min FROM work_record WHERE record_no = 'MR-0901'), 85.00::numeric, '수리 시간 = 11:15 ~ 12:40');
SELECT t.eq((SELECT status FROM maintenance_work_order WHERE wo_no = 'MW-0901'), 'DONE', '짝 작업지시서 완료 (6.13)');
SELECT t.eq((SELECT on_hand_qty FROM inventory_item WHERE item_no = 'CS-WLUB'), 5.500::numeric, 'R-34 사용 부품 0.5L 차감');
SELECT t.ok((SELECT is_processed AND process_kind = 'AUTO' AND processed_by = 'U07' FROM notification WHERE rule_code = 'ALARM_STOP'),
            '정지 알람 알림 자동 처리');
SELECT t.ok(NOT EXISTS (SELECT 1 FROM v_lock_status WHERE equipment_id = 'VF2-01'), 'R-53 7.3 체크 뒤 잠금 풀림');

-- 확인은 SUP
UPDATE work_record SET status = 'CHECKED', checked_by = 'U10', checked_at = app_now() WHERE record_no = 'MR-0901';
SELECT t.ok(true, '반장 확인');
SELECT t.throws($$UPDATE work_record SET checked_by = 'U09' WHERE record_no = 'MR-0901'$$, 'SUP', '확인은 SUP만');

-- R-35 확정된 문서는 그냥 못 고침
SELECT t.throws($$UPDATE work_record SET cause = '다른 원인' WHERE record_no = 'MR-0901'$$, 'R-35', '확정 뒤 직접 수정 불가');
SELECT t.throws($$SELECT fn_save_revision('WORK_RECORD', 'MR-0901', 'HUMAN', 'U07', NULL, 'CONFIRMED',
                    '{"cause": "다른 원인"}')$$, '사유', '확정 뒤 수정은 사유 필수');
SELECT t.throws($$SELECT fn_save_revision('WORK_RECORD', 'MR-0901', 'HUMAN', 'U10', '오타', 'CONFIRMED',
                    '{"cause": "다른 원인"}')$$, 'R-35', '확정 뒤 수정은 확정 권한자만');
-- 바른 길: 사유 있는 새 버전 → 본문 current_version + 1
SELECT t.eq(fn_save_revision('WORK_RECORD', 'MR-0901', 'HUMAN', 'U07', '원인 문장 보완', 'CONFIRMED',
                             '{"cause": "케이블 절삭유 침투 (커넥터 포함)"}',
                             '[{"field": "원인", "before": "(개발용) 케이블 절삭유 침투", "after": "케이블 절삭유 침투 (커넥터 포함)"}]'),
            2, '새 버전 v2');
UPDATE work_record SET cause = '케이블 절삭유 침투 (커넥터 포함)', current_version = 2, status = 'CONFIRMED',
                       checked_by = NULL, checked_at = NULL
 WHERE record_no = 'MR-0901';
SELECT t.ok(true, '사유 있는 버전 뒤 본문 수정 (확인 표시 풀림 — 6.15)');
SELECT t.eq((SELECT count(*) FROM document_revision_change c JOIN document_revision r USING (revision_id)
              WHERE r.doc_key = 'MR-0901' AND r.version_no = 2)::int, 1, '바뀐 칸 기록');
-- 워크플로 칸만 바꾸는 것은 허용 (확인)
UPDATE work_record SET status = 'CHECKED', checked_by = 'U10', checked_at = app_now() WHERE record_no = 'MR-0901';
SELECT t.ok(true, '확정된 문서도 상태·확인자 칸은 바꿀 수 있음');

-- 교대 보고서: 반장 확정 → 확정 후 수정(REVISED)
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U10', confirmed_at = app_now() WHERE shift_id = '2026-09-15-D';
SELECT t.throws($$UPDATE shift_report SET notable_text = '고침' WHERE shift_id = '2026-09-15-D'$$, 'R-35', '확정 교대 보고서 직접 수정 불가');
SELECT t.throws($$SELECT fn_save_revision('SHIFT_REPORT', '2026-09-15-D', 'HUMAN', 'U11', '오타', 'REVISED', '{}')$$,
                '그 교대 반장', '다른 반장은 확정 뒤 수정 불가');
SELECT fn_save_revision('SHIFT_REPORT', '2026-09-15-D', 'HUMAN', 'U10', '실적 숫자 정정', 'REVISED', '{"actual_qty": 82}');
UPDATE shift_report SET actual_qty = 82, status = 'REVISED', current_version = 1 WHERE shift_id = '2026-09-15-D';
SELECT t.eq((SELECT status FROM shift_report WHERE shift_id = '2026-09-15-D'), 'REVISED', '확정 후 수정본이 바로 잠김 (6.16)');

-- 간이 작업기록: 주의 등급(108) 알람은 OPR 확정 가능, 정지 등급 다른 공정은 MNT만
INSERT INTO work_record (record_no, record_type, alarm_event_id, equipment_id, action, start_at, safety_block_required, status)
VALUES ('MR-S-0901', 'SIMPLE', 1, 'VF2-01', '부하 조건 확인 뒤 재시작', '2026-09-15 10:52+09', false, 'EDITING');
SELECT fn_confirm_work_record('MR-S-0901', 'U02');
SELECT t.eq((SELECT confirmed_by FROM work_record WHERE record_no = 'MR-S-0901'), 'U02', '주의 등급 간이 기록은 OPR 확정');
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES ('SAW-01', '6302.00', 'STOP', '2026-09-15 12:00+09');
INSERT INTO work_record (record_no, record_type, alarm_event_id, equipment_id, action, start_at, safety_block_required, status)
VALUES ('MR-S-0902', 'SIMPLE', currval(pg_get_serial_sequence('alarm_event','alarm_event_id')), 'SAW-01', '톱날 교체', '2026-09-15 12:00+09', false, 'EDITING');
SELECT t.throws($$SELECT fn_confirm_work_record('MR-S-0902', 'U01')$$, 'MNT', '다른 공정 정지 등급 간이 기록은 MNT만 확정');
SELECT t.throws($$INSERT INTO work_record (record_no, record_type, alarm_event_id, equipment_id, action, start_at, safety_block_required, status)
                  VALUES ('MR-S-0903', 'SIMPLE', 2, 'VF2-01', 'x', now(), false, 'AI_DRAFT')$$,
                'ck_work_record_simple_status', '간이 작업기록에는 AI비서 초안 단계 없음');
ROLLBACK;
