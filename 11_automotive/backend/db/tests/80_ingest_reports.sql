-- 알람 받기·작업지시서 초안·측정 지시 (60_ingest) / 보고서 초안·시간 규칙 알림 (70_reports)
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
-- 이 파일은 초안 저장 API(fn_create_work_order_draft)를 직접 시험한다 — 정지 알람 자동 초안(2026-10-20)은 끔 (96d에서 시험)
SET LOCAL app.auto_work_order = 'off';

-- 알람 받기: 정지 등급 → 긴급 알림, 받는 사람 = 사용 중인 전원 (2026-10-13 — 로그인한 전원에게 팝업, 처리 책임은 그 설비 OPR·MNT)
SELECT fn_ingest_alarm('VF2-02', '254', '2026-09-15 13:00+09', 'LOT-2609-041-1');
SELECT t.eq((SELECT rule_code || '/' || importance FROM notification ORDER BY notification_id DESC LIMIT 1), 'ALARM_STOP/URGENT', '정지 → 긴급');
SELECT t.eq((SELECT string_agg(user_id, ',' ORDER BY user_id) FROM notification_recipient
              WHERE notification_id = (SELECT max(notification_id) FROM notification)),
            'U01,U02,U03,U04,U05,U06,U07,U08,U09,U10,U11,U12', '긴급 받는 사람 = 전원');
SELECT t.ok((SELECT bool_and(popup_sound) FROM notification_recipient WHERE notification_id = (SELECT max(notification_id) FROM notification)),
            '반장도 팝업 + 소리');
SELECT t.throws($$SELECT fn_ingest_alarm('VF2-02', '99999')$$, '코드집에 없는', '코드집에 없는 알람 번호는 받지 않음');
SELECT fn_ingest_alarm('VF2-02', '314', '2026-09-15 13:01+09');
SELECT t.eq((SELECT string_agg(DISTINCT u.role_code, ',') FROM notification_recipient r JOIN app_user u USING (user_id)
              WHERE r.notification_id = (SELECT max(notification_id) FROM notification)), 'OPR', '조작 안내는 작업자에게만');

-- 작업지시서 AI비서 초안 (번호·고정 서식 표시·v0)
SELECT t.eq(fn_create_work_order_draft('VF2-02', '알람 254 점검', '스핀들 모터 과열',
              (SELECT max(alarm_event_id) FROM alarm_event WHERE alarm_code = '254'), NULL, NULL,
              '[{"step_text": "냉각 팬 확인", "source_section": "DOC-03 §2.9"}]', '[{"item_no": "CS-SLUB", "qty": 0.5}]'),
            'MW-0902', '작업지시서 번호 MW-0902');
SELECT t.eq((SELECT status || '/' || safety_block_doc_rev || '/' || has_high_voltage_notice FROM maintenance_work_order WHERE wo_no = 'MW-0902'),
            'AI_DRAFT/DOC-05 Rev.1/true', 'AI비서 초안 + 고정 서식 블록 표시 + 고전압 문구(OP-30)');
SELECT t.eq((SELECT author_kind || '/' || version_no FROM document_revision WHERE doc_key = 'MW-0902'), 'AI/0', 'v0 = AI비서 초안');
-- 같은 알람이 2단계와 겹치면 작업지시서는 1개 (R-71): 2단계 알림을 계기로 더 부르면 기존 작업지시서에 계기·단계만 더함
INSERT INTO notification (rule_code, importance, raised_at, message, alarm_event_id, equipment_id, prev_stage_notification_id, repeat_stage_status)
VALUES ('REPEAT_ALARM_2', 'CAUTION', app_now(), '2단계', (SELECT max(alarm_event_id) FROM alarm_event WHERE alarm_code = '254'),
        'VF2-02', (SELECT max(notification_id) FROM notification), 'S2_OPEN');
SELECT t.eq(fn_create_work_order_draft('VF2-02', '원인 점검', '2단계', NULL,
              (SELECT max(notification_id) FROM notification WHERE rule_code = 'REPEAT_ALARM_2'), NULL,
              '[{"step_text": "원인 점검 단계", "source_section": "DOC-03 §2.9"}]'), 'MW-0902', 'R-71 겹치면 같은 작업지시서');
SELECT t.eq((SELECT array_to_string(trigger_kind, ',') FROM v_work_order WHERE wo_no = 'MW-0902'), 'STOP_ALARM,REPEAT_STAGE2', '계기 2개');
SELECT t.eq((SELECT count(*) FROM work_order_step WHERE wo_no = 'MW-0902')::int, 2, '원인 점검 단계 덧붙임');
-- 사람이 직접 만든 작업지시서: 수정 중에서 시작, v0 = HUMAN, 작성은 MNT만
SELECT t.throws($$SELECT fn_create_work_order_draft('VF2-01', 'x', 'y', p_pm_record_id => 2, p_author => 'U02')$$, 'MNT',
                'OPR은 작업지시서를 만들 수 없음');
CREATE TEMP TABLE human_wo AS SELECT fn_create_work_order_draft('VF2-01', '절삭유 점검', '농도 낮음', p_pm_record_id => 2,
                                                                 p_author => 'U09') AS wo_no;
SELECT t.eq((SELECT m.status || '/' || r.author_kind || '/' || r.author_user_id FROM maintenance_work_order m
               JOIN document_revision r ON r.doc_type = 'WORK_ORDER' AND r.doc_key = m.wo_no
              WHERE m.wo_no = (SELECT wo_no FROM human_wo)), 'EDITING/HUMAN/U09', '직접 작성 = 수정 중 + v0 사람');

-- 측정 지시: 발췌 로트는 1·5의 배수만, 강화 로트는 검사 구분 = 강화
SELECT t.throws($$SELECT fn_issue_cmm_instruction('LOT-2609-040-1', 6)$$, 'R-09', '발췌 로트 6번 부품 지시 불가');
SELECT t.ok(fn_issue_cmm_instruction('LOT-2609-040-1', 10) > 0, '발췌 10번 지시');
SELECT t.eq((SELECT insp_kind FROM cmm_instruction WHERE lot_no = 'LOT-2609-040-1' AND part_seq = 10), 'SAMPLE', '검사 구분 = 발췌');
SELECT fn_lot_hold('LOT-2609-041-1', 'U10', 'AI_SUSPECT', '충돌 의심', 2, 3);
SELECT fn_issue_cmm_instruction('LOT-2609-041-1', 7);
SELECT t.eq((SELECT insp_kind || '/' || enhance_reason FROM cmm_instruction WHERE lot_no = 'LOT-2609-041-1'), 'ENHANCED/HOLD_LOT', '보류 로트는 강화');

-- 시간 규칙: 승인 대기 (MW-0902 13:00 생성 → 15:10이면 30분·2시간 둘 다)
SELECT t.freeze('2026-09-15 15:10+09');
UPDATE cmm_instruction SET status = 'STARTED', started_at = '2026-09-15 14:50+09', started_by = 'U03'
 WHERE lot_no = 'LOT-2609-040-1' AND part_seq = 10;
SELECT t.ok(fn_run_time_rules(10) >= 3, '시간 규칙 알림 생성');
SELECT t.eq((SELECT string_agg(rule_code, ',' ORDER BY rule_code) FROM notification
              WHERE rule_code IN ('APPROVAL_WAIT_30M','APPROVAL_WAIT_2H') AND wo_no = 'MW-0902'),
            'APPROVAL_WAIT_2H,APPROVAL_WAIT_30M', '승인 대기 30분·2시간');
-- 결과 미수신: 040-1 10번(14:50 시작) + 목업의 038-1 1번(08:38 시작, 결과 없음) → 로트마다 1건
SELECT t.eq((SELECT string_agg(lot_no, ',' ORDER BY lot_no) FROM notification WHERE rule_code = 'CMM_NO_RESULT'),
            'LOT-2609-038-1,LOT-2609-040-1', '측정 시작 뒤 10분 넘게 결과 없는 로트마다 미수신 알림');
SELECT t.eq(fn_run_time_rules(10), 0, '두 번 돌려도 같은 알림을 또 만들지 않음');
UPDATE maintenance_work_order SET status = 'EDITING', assignee_user_id = 'U07' WHERE wo_no = 'MW-0902';
UPDATE maintenance_work_order SET status = 'APPROVED', approved_by = 'U10', approved_at = app_now() WHERE wo_no = 'MW-0902';
SELECT t.ok((SELECT bool_and(is_processed) FROM notification WHERE rule_code LIKE 'APPROVAL_WAIT%' AND wo_no = 'MW-0902'),
            '승인하면 승인 대기 알림 자동 처리');

-- 교대 보고서 초안 (9/15 주간, 17:00)
SELECT t.freeze('2026-09-15 17:00+09');
DELETE FROM shift_report WHERE shift_id = '2026-09-15-D';
SELECT t.eq(fn_create_shift_report_draft('2026-09-15-D'), 'EXISTS', '이미 버전이 있는 보고서(삭제해도 버전은 남음)');
ROLLBACK;

BEGIN;
SELECT t.freeze('2026-09-16 06:00+09');
-- 새 날짜로 시험: 9/16 주간·야간 교대 보고서가 없음 → 일일 보고서 초안이 교대 초안을 만들고 확정 요청
INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, supervisor_user_id) VALUES
  ('2026-09-16-D', '2026-09-16', 'DAY',   '2026-09-16 08:00+09', '2026-09-16 17:00+09', 480, 90, 'U10'),
  ('2026-09-16-N', '2026-09-16', 'NIGHT', '2026-09-16 20:00+09', '2026-09-17 05:00+09', 480, 90, 'U11');
INSERT INTO work_day VALUES ('2026-09-17', true, 180);
SELECT t.freeze('2026-09-17 06:00+09');
SELECT t.eq(fn_create_daily_report_draft('2026-09-16'), 2, '확정 안 된 교대 2개 → 잠정');
SELECT t.eq((SELECT count(*) FROM shift_report WHERE shift_id LIKE '2026-09-16-%')::int, 2, '교대 보고서 초안도 만듦');
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'SHIFT_REPORT_PENDING'), 'U10,U11', 'R-72 확정 요청 → 그 교대 반장');
SELECT t.ok((SELECT issues_summary LIKE '%잠정%' FROM daily_report WHERE work_date = '2026-09-16'), '일일 보고서에 잠정 표시');
SELECT t.eq((SELECT version_no || '/' || author_kind FROM document_revision WHERE doc_type = 'DAILY_REPORT' AND doc_key = '2026-09-16'),
            '0/AI', '일일 보고서 v0');
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U10', confirmed_at = app_now() WHERE shift_id = '2026-09-16-D';
SELECT t.ok((SELECT is_processed FROM notification WHERE rule_code = 'SHIFT_REPORT_PENDING' AND shift_id = '2026-09-16-D'),
            '반장이 확정하면 확정 요청 알림 자동 처리');
SELECT t.ok((SELECT handover_text LIKE '0 안전: % / 4 참고: %' FROM shift_report WHERE shift_id = '2026-09-16-D'), '인계 사항 = 순위별 칸 (생성기 모양)');
SELECT t.eq(fn_create_daily_report_draft('2026-09-16'), 0, '두 번 만들지 않음');
ROLLBACK;
