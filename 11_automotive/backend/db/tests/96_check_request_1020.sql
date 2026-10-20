-- 2026-10-20 정비 탭 확인 요청 반영 (구현_중_수정사항 1020): 일일 보고서 관리자 메모, 문서 알림 4종, 예방 정비 하루 전 묶기
BEGIN;
SELECT t.freeze('2026-09-15 09:00+09');

-- ---------- 1. 관리자 메모 떼기 (생성기 9월 글 · 시연 서버 글)
SELECT t.eq(fn_split_memo('전체 6건 (긴급 0 · 생산 2): 1) [생산] 병목 관리자 메모: 내일 오전 정비 일정 확인.'),
            ARRAY['전체 6건 (긴급 0 · 생산 2): 1) [생산] 병목', '내일 오전 정비 일정 확인.'], '생성기 글: 끝의 "관리자 메모: …"를 뗀다');
SELECT t.eq(fn_split_memo('오늘의 문제 / 관리자 메모: 공구 주문'), ARRAY['오늘의 문제', '공구 주문'], '시연 서버 글: " / " 앞까지');
SELECT t.eq(fn_split_memo('메모 없는 글'), ARRAY['메모 없는 글', NULL], '메모가 없으면 글 그대로');
SELECT t.ok((SELECT is_nullable = 'YES' FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'daily_report' AND column_name = 'memo'),
            'daily_report.memo 칸 (선택)');

-- ---------- 2. 작업지시서 승인 요청 (WO_APPROVAL_REQUEST → 반장, 말풍선)
SELECT fn_ingest_alarm('VF2-02', '254', '2026-09-15 09:00+09', 'LOT-2609-041-1') AS a1 \gset
SELECT fn_create_work_order_draft('VF2-02', '알람 254 점검', '주축 모터 과열', p_alarm_event_id => :a1) AS wo1 \gset
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'WO_APPROVAL_REQUEST' AND n.wo_no = :'wo1'), 'U10,U11', '초안이 생기면 반장에게 승인 요청');
UPDATE maintenance_work_order SET status = 'EDITING', assignee_user_id = 'U08' WHERE wo_no = :'wo1';
SELECT t.ok(NOT (SELECT is_processed FROM notification WHERE rule_code = 'WO_APPROVAL_REQUEST' AND wo_no = :'wo1'),
            '수정 중이어도 승인 전이면 열려 있음');
UPDATE maintenance_work_order SET status = 'APPROVED', approved_by = 'U10', approved_at = app_now() WHERE wo_no = :'wo1';
SELECT t.ok((SELECT is_processed AND process_kind = 'AUTO' AND processed_by = 'U10' FROM notification
              WHERE rule_code = 'WO_APPROVAL_REQUEST' AND wo_no = :'wo1'), '승인하면 승인 요청 자동 처리');
-- 승인 대기 30분이 되면 승인 요청은 닫히고 승인 대기 알림이 이어받는다
SELECT fn_ingest_alarm('VF2-02', '992', '2026-09-15 09:00+09', 'LOT-2609-041-1') AS a2 \gset
SELECT fn_create_work_order_draft('VF2-02', '알람 992 점검', '과전류', p_alarm_event_id => :a2) AS wo2 \gset
SELECT t.ok(:'wo2' <> :'wo1', '두 번째 작업지시서');
SELECT t.freeze('2026-09-15 09:31+09');
SELECT fn_run_time_rules(10);
SELECT t.ok((SELECT is_processed FROM notification WHERE rule_code = 'WO_APPROVAL_REQUEST' AND wo_no = :'wo2'),
            '승인 대기 30분이 뜨면 승인 요청 자동 처리');
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'APPROVAL_WAIT_30M' AND wo_no = :'wo2')::int, 1, '승인 대기 30분 알림');

-- ---------- 3. 작업기록서 확정 전 (→ 담당 MNT) · 확인 요청 (→ 반장)
INSERT INTO work_record (record_no, record_type, wo_no, equipment_id, cause, action, start_at, safety_block_required, status, current_version)
VALUES ('MR-0950', 'FULL', :'wo1', 'VF2-02', '(시험) 베어링 마모', '(시험) 주축 모터 점검', '2026-09-15 09:20+09', false, 'AI_DRAFT', 0);
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'WR_CONFIRM_PENDING' AND n.wo_no = :'wo1'), 'U08', '작업기록서가 생기면 그 작업지시서 담당 MNT에게만');
-- 목업 MR-0901(적재 때 생긴 것 — 알림 없음)을 확정 → 확인 요청
SELECT t.freeze('2026-09-15 12:40+09');
UPDATE work_record_check SET is_checked = true, checked_by = 'U07', checked_at = app_now() WHERE record_no = 'MR-0901';
SELECT fn_confirm_work_record('MR-0901', 'U07');
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'WR_CHECK_REQUEST' AND n.wo_no = 'MW-0901'), 'U10,U11', '확정하면 반장에게 확인 요청');
UPDATE maintenance_work_order SET status = 'IN_PROGRESS' WHERE wo_no = :'wo1';
SELECT fn_confirm_work_record('MR-0950', 'U08');
SELECT t.ok((SELECT is_processed AND processed_by = 'U08' FROM notification WHERE rule_code = 'WR_CONFIRM_PENDING' AND wo_no = :'wo1'),
            '확정하면 확정 전 알림 자동 처리');
UPDATE work_record SET status = 'CHECKED', checked_by = 'U10', checked_at = app_now() WHERE record_no = 'MR-0901';
SELECT t.ok((SELECT is_processed AND processed_by = 'U10' FROM notification WHERE rule_code = 'WR_CHECK_REQUEST' AND wo_no = 'MW-0901'),
            '반장이 확인하면 확인 요청 자동 처리');
SELECT t.ok(NOT (SELECT is_processed FROM notification WHERE rule_code = 'WR_CHECK_REQUEST' AND wo_no = :'wo1'),
            '다른 작업기록서의 확인 요청은 그대로');

-- ---------- 4. 예방 정비 기한 하루 전 = 같은 기한 날짜끼리 1건 (9/16 기한 3개 중 1개는 9월식 항목별 알림이 이미 있음)
INSERT INTO pm_task (pm_task_id, equipment_id, doc04_section, area, item_name, cycle_code, lockout_level, default_role, on_calendar, source_tag)
VALUES ('PM-VF2-01-3.1-01', 'VF2-01', '3.1', '공압', '(시험) 공기 필터', 'WEEKLY', 'NONE', 'MNT', true, 'VIRTUAL'),
       ('PM-VF2-01-3.1-02', 'VF2-01', '3.1', '공압', '(시험) 압력 확인', 'WEEKLY', 'NONE', 'MNT', true, 'VIRTUAL'),
       ('PM-VF2-02-3.1-01', 'VF2-02', '3.1', '공압', '(시험) 공기 필터', 'WEEKLY', 'NONE', 'MNT', true, 'VIRTUAL'),
       ('PM-VF2-02-3.1-02', 'VF2-02', '3.1', '공압', '(시험) 압력 확인', 'WEEKLY', 'NONE', 'MNT', true, 'VIRTUAL');
INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status)
SELECT pm_task_id, '2026-09-09', '2026-09-09 10:00+09', 'U07', 'U07', 'NORMAL', 'CONFIRMED' FROM pm_task WHERE doc04_section = '3.1';
SELECT fn_raise_notification('PM_DUE_SOON', 'VF2-02 예방 정비 내일: (시험) 압력 확인',
                             '{"pm_task_id": "PM-VF2-02-3.1-02", "equipment_id": "VF2-02"}', '2026-09-15 08:00+09') AS legacy \gset
SELECT fn_run_time_rules(10);
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id IS NULL)::int, 1,
            '기한 9/16 항목은 1건으로 묶는다');
SELECT t.eq((SELECT message FROM notification WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id IS NULL),
            '기한 09/16 (내일) 예방 정비 3건', '문장 = 기한 날짜 + 건수 (이미 항목별로 알린 1개는 빼고)');
SELECT t.eq((SELECT related_info FROM notification WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id IS NULL),
            'VF2-01 (시험) 공기 필터 · VF2-01 (시험) 압력 확인 · VF2-02 (시험) 공기 필터', '관련 정보 = 항목 목록');
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'PM_DUE_SOON' AND n.pm_task_id IS NULL), 'U07,U08,U09', '받는 사람 = MNT');
SELECT t.eq(fn_run_time_rules(10), 0, '두 번 돌려도 묶음을 또 만들지 않음');

-- ---------- 5. 예방 정비 실시 기록 확인 (설비마다 1건, 초안 기록의 항목)
INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status) VALUES
  ('PM-VF2-01-3.1-01', '2026-09-16', '2026-09-15 09:40+09', 'U07', 'U07', 'NORMAL', 'DRAFT'),
  ('PM-VF2-01-3.1-02', '2026-09-16', '2026-09-15 09:50+09', 'U07', 'U07', 'NORMAL', 'DRAFT');
SELECT t.eq((SELECT string_agg(message, ' | ') FROM notification WHERE rule_code = 'PM_RECORD_CHECK'),
            'VF2-01 예방 정비 2건 끝남 — 실시 기록 확인', '같은 설비 초안 2건 → 알림 1건');
SELECT t.eq((SELECT count(*) FROM notification_pm_task l JOIN notification n USING (notification_id)
              WHERE n.rule_code = 'PM_RECORD_CHECK')::int, 2, '묶인 항목 2개');
UPDATE pm_record SET status = 'CONFIRMED' WHERE pm_task_id = 'PM-VF2-01-3.1-01' AND status = 'DRAFT';
SELECT t.ok(NOT (SELECT is_processed FROM notification WHERE rule_code = 'PM_RECORD_CHECK'), '1건만 확정 → 아직 열림');
UPDATE pm_record SET status = 'CONFIRMED' WHERE pm_task_id = 'PM-VF2-01-3.1-02' AND status = 'DRAFT';
SELECT t.ok((SELECT is_processed AND processed_by = 'U07' FROM notification WHERE rule_code = 'PM_RECORD_CHECK'),
            '묶인 기록이 모두 확정 → 자동 처리');
SELECT t.ok(NOT (SELECT is_processed FROM notification WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id IS NULL),
            '하루 전 묶음은 VF2-02 항목이 남아 아직 열림');

-- ---------- 6. 기한을 넘기면 하루 전 묶음·9월식 항목별 알림 모두 자동 처리 (기한 넘김 알림이 이어받음)
SELECT t.freeze('2026-09-17 09:00+09');
SELECT fn_run_time_rules(10);
SELECT t.ok((SELECT bool_and(is_processed AND process_kind = 'AUTO') FROM notification WHERE rule_code = 'PM_DUE_SOON'),
            '기한이 지나면 하루 전 알림(묶음·항목별) 자동 처리');
SELECT t.eq((SELECT string_agg(pm_task_id, ',' ORDER BY pm_task_id) FROM notification
              WHERE rule_code = 'PM_OVERDUE' AND pm_task_id LIKE '%-3.1-%'), 'PM-VF2-02-3.1-01,PM-VF2-02-3.1-02', '안 한 항목은 기한 넘김');

ROLLBACK;
