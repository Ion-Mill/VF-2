-- 2026-10-20 요구사항 대조 중 (구현_중_수정사항 1020 36장): 재고 거래 → 재고 부족, CMM 파일 오류 처리, 반복 알람 2단계·효과 확인,
-- 예방 정비 하루 전 알림의 작업자 담당 항목
BEGIN;
SELECT t.freeze('2026-09-15 12:00+09');

-- ---------- 예방 정비 소모품 차감으로 안전 재고(4L) 이하 → 재고 부족 (전에는 이 길에서 확인을 안 불렀다)
INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status)
VALUES ('PM-VF2-02-2.3-01', '2026-10-15', '2026-09-15 11:50+09', 'U07', 'U07', 'REFILLED', 'DRAFT') RETURNING pm_record_id AS pmr \gset
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, pm_record_id)
VALUES ('CS-WLUB', 'USE', -2.5, app_now(), 'U07', 'PM_RECORD', :pmr);
SELECT t.eq((SELECT count(*) FROM notification WHERE rule_code = 'STOCK_LOW' AND item_no = 'CS-WLUB' AND NOT is_processed)::int, 1,
            '6L → 3.5L (안전 4L 이하) → 재고 부족 1건');
INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind)
VALUES ('CS-WLUB', 'IN', 5, app_now(), 'U07', 'RECEIPT');
SELECT t.ok((SELECT bool_and(is_processed) FROM notification WHERE rule_code = 'STOCK_LOW' AND item_no = 'CS-WLUB'), '입고로 안전 재고를 넘으면 자동 처리');

-- ---------- CMM 결과 파일 오류: 반장이 [처리] (자동 처리할 기록이 없음)
SELECT fn_raise_notification('CMM_FILE_ERROR', '결과 파일 읽기 실패: x.csv', '{"equipment_id": "CMM-01"}') AS cmm \gset
SELECT t.throws($$SELECT fn_process_notification((SELECT max(notification_id) FROM notification WHERE rule_code = 'CMM_FILE_ERROR'), 'U03')$$,
                'SUP', '작업자는 처리 못 함');
SELECT fn_process_notification(:cmm, 'U10', '파일 다시 받음');
SELECT t.ok((SELECT is_processed AND process_kind = 'MANUAL' FROM notification WHERE notification_id = :cmm), '반장이 처리');

-- ---------- 반복 알람: 효과 확인 기한이 지나도록 재발이 없으면 시간 규칙이 "효과 있음"으로 닫는다
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES ('VF2-02', '108', 'WARN', '2026-09-05 10:00+09')
RETURNING alarm_event_id AS old108 \gset
INSERT INTO notification (rule_code, importance, raised_at, message, alarm_event_id, equipment_id, repeat_stage_status, effect_check_due_at,
                          is_processed, process_kind, processed_by, processed_at, process_memo)
VALUES ('REPEAT_ALARM', 'CAUTION', '2026-09-05 10:00+09', '108 7일 3번', :old108, 'VF2-02', 'S1_CLOSED', '2026-09-12 10:00+09',
        true, 'MANUAL', 'U10', '2026-09-05 10:30+09', '인서트 교체') RETURNING notification_id AS s1 \gset
SELECT fn_run_time_rules(10);
SELECT t.eq((SELECT repeat_stage_status FROM notification WHERE notification_id = :s1), 'EFFECTIVE', '7일 재발 없음 → 효과 있음');

-- ---------- 반복 알람 2단계: 조치 작업이 진행 중일 때 난 알람은 재발로 세지 않는다
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES ('VF2-02', '120', 'WARN', '2026-09-14 10:00+09')
RETURNING alarm_event_id AS a120 \gset
INSERT INTO notification (rule_code, importance, raised_at, message, alarm_event_id, equipment_id, repeat_stage_status, effect_check_due_at,
                          is_processed, process_kind, processed_by, processed_at, process_memo)
VALUES ('REPEAT_ALARM', 'CAUTION', '2026-09-14 10:00+09', '120 7일 3번', :a120, 'VF2-02', 'S1_CLOSED', '2026-09-21 10:00+09',
        true, 'MANUAL', 'U10', '2026-09-14 10:30+09', '공기 배관 점검') RETURNING notification_id AS s1b \gset
INSERT INTO work_record (record_no, record_type, alarm_event_id, equipment_id, action, start_at, safety_block_required, status, current_version)
VALUES ('MR-S-0960', 'SIMPLE', :a120, 'VF2-02', '(시험) 공기 배관 점검 중', '2026-09-14 10:20+09', false, 'EDITING', 0);
SELECT t.eq((SELECT fn_check_repeat_alarm(fn_ingest_alarm('VF2-02', '120', '2026-09-15 11:00+09'))), 'NONE',
            '조치 기록이 확정 전이면 다시 나도 2단계 아님');
SELECT t.eq((SELECT repeat_stage_status FROM notification WHERE notification_id = :s1b), 'S1_CLOSED', '1단계는 그대로');
SELECT fn_confirm_work_record('MR-S-0960', 'U02');
SELECT fn_ingest_alarm('VF2-02', '120', '2026-09-15 11:30+09');
SELECT t.eq((SELECT repeat_stage_status FROM notification WHERE notification_id = :s1b), 'ESCALATED', '조치가 끝난 뒤 재발 → 2단계');

-- ---------- 예방 정비 하루 전: 작업자 담당 항목(OPR)이 있으면 그 설비 공정의 작업자도 받는다
SELECT t.freeze('2026-09-14 10:00+09');
INSERT INTO pm_task (pm_task_id, equipment_id, doc04_section, area, item_name, cycle_code, lockout_level, default_role, on_calendar, source_tag)
VALUES ('PM-VF2-01-4.1-01', 'VF2-01', '4.1', '칩', '(시험) 칩 컨베이어 청소', 'WEEKLY', 'NONE', 'OPR', true, 'VIRTUAL');
INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status)
VALUES ('PM-VF2-01-4.1-01', '2026-09-08', '2026-09-08 10:00+09', 'U07', 'U07', 'NORMAL', 'CONFIRMED');
SELECT fn_raise_pm_due_soon();
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              JOIN notification_pm_task l USING (notification_id) WHERE n.rule_code = 'PM_DUE_SOON' AND l.pm_task_id = 'PM-VF2-01-4.1-01'),
            'U02,U05,U07,U08,U09', '받는 사람 = MNT + OP-30 작업자(주간·야간)');
ROLLBACK;
