-- 2026-10-25 교대 시각을 박지 않고 shift 행에서 (최종용·영상용 데이터 = 교대 09~18 / 21~06):
-- 휴식 = 교대 시작 + 4시간, 일요일 휴무, 기준점 일부만 다시 찍기, 이미 작업지시서가 있는 알람은 자동 초안 안 만듦
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');

-- ① 휴식 시작: 개발 데이터(08~17/20~05)는 예전과 같은 12:00·00:00
SELECT t.eq(fn_shift_break_start('DAY', '2026-09-15'), '2026-09-15 12:00+09'::timestamptz, '주간 08:00 시작 → 휴식 12:00');
SELECT t.eq(fn_shift_break_start('NIGHT', '2026-09-15'), '2026-09-16 00:00+09'::timestamptz, '야간 20:00 시작 → 휴식 00:00');
SELECT t.eq((SELECT break_start_at FROM v_shift_progress WHERE shift_id = '2026-09-15-D'), '2026-09-15 12:00+09'::timestamptz,
            '교대 진행 뷰도 같은 휴식 시각');

-- 새 교대 시각(09~18 / 21~06)의 근무일 — 휴식 13:00·01:00, 근무 분은 그 휴식을 뺌
INSERT INTO work_day (work_date, is_workday, daily_target_qty) VALUES ('2026-09-17', true, 180);
INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, carry_over_qty, supervisor_user_id) VALUES
  ('2026-09-17-D', '2026-09-17', 'DAY',   '2026-09-17 09:00+09', '2026-09-17 18:00+09', 480, 90, 0, 'U10'),
  ('2026-09-17-N', '2026-09-17', 'NIGHT', '2026-09-17 21:00+09', '2026-09-18 06:00+09', 480, 90, 0, 'U11');
SELECT t.eq(fn_shift_break_start('DAY', '2026-09-17'), '2026-09-17 13:00+09'::timestamptz, '주간 09:00 시작 → 휴식 13:00');
SELECT t.eq(fn_shift_break_start('NIGHT', '2026-09-17'), '2026-09-18 01:00+09'::timestamptz, '야간 21:00 시작 → 휴식 01:00');
SELECT t.eq(fn_work_minutes('2026-09-17 09:00+09', '2026-09-17 14:00+09'), 240::numeric, '09:00~14:00 = 300분 − 휴식 60분');
SELECT t.eq(fn_work_minutes('2026-09-17 09:00+09', '2026-09-17 13:00+09'), 240::numeric, '09:00~13:00 = 휴식 전 240분');
SELECT t.eq(fn_work_minutes('2026-09-17 18:00+09', '2026-09-17 21:00+09'), 0::numeric, '교대 사이 18:00~21:00은 0');
SELECT t.eq(fn_shift_break_start('DAY', '2026-09-20'), '2026-09-20 12:00+09'::timestamptz, '교대 행이 없으면 옛 고정값');

-- ② 근무일 만들기: 가장 최근 근무일(9/17, 09~18)을 본뜸, 일요일(9/20)은 휴무
SELECT t.eq(fn_ensure_work_day('2026-09-18'), 2, '금요일 9/18 교대 2개');
SELECT t.eq((SELECT start_at FROM shift WHERE shift_id = '2026-09-18-D'), '2026-09-18 09:00+09'::timestamptz, '교대 시각도 본뜸 (09:00)');
SELECT t.eq(fn_ensure_work_day('2026-09-20'), 0, '일요일은 교대를 만들지 않음');
SELECT t.eq((SELECT is_workday FROM work_day WHERE work_date = '2026-09-20'), false, '일요일 근무일 = 휴무');

-- ③ 기준점 일부만: 문서 조각만 지금 값으로, 다른 표(알람)는 기준점 그대로
SELECT fn_demo_snapshot();
INSERT INTO doc_chunk (doc_no, doc_rev, section, chunk_text, built_at)
SELECT doc_no, current_rev, '시험 1025', '시험 조각', now() FROM internal_doc ORDER BY doc_no LIMIT 1;
SELECT fn_ingest_alarm('VF2-02', '254', '2026-09-15 12:30+09');
SELECT t.eq(fn_demo_snapshot_refresh(ARRAY['doc_chunk', 'internal_doc', '없는_표']), 2, '기준점에 있는 표 2개만 다시 찍음');
SELECT fn_demo_reset();
SELECT t.eq((SELECT count(*) FROM doc_chunk WHERE section = '시험 1025')::int, 1, '되돌려도 새 문서 조각은 남음');
SELECT t.eq((SELECT count(*) FROM alarm_event WHERE alarm_code = '254')::int, 0, '기준점 뒤 알람은 되돌리면 사라짐');

-- ④ 자동 초안: 이 알람의 작업지시서가 이미 있으면(끝났어도) 새로 만들지 않음
UPDATE maintenance_work_order SET status = 'DONE', completed_at = app_now() WHERE alarm_event_id = 3 AND status <> 'DONE';
SELECT t.ok(fn_auto_work_order_draft(3, 'STOP_ALARM') IS NULL, '알람 3(992)은 MW-0901이 있어 초안 안 만듦');
SELECT t.eq((SELECT count(*) FROM maintenance_work_order WHERE alarm_event_id = 3)::int, 1, '작업지시서는 그대로 1건');

-- ⑤ 교대 사이(17:00~20:00) 정지 알람의 초안 담당 = 바로 앞에 시작한 교대(주간)의 보전 담당
SET LOCAL app.auto_work_order = 'off';
SELECT fn_ingest_alarm('VF2-02', '992', '2026-09-15 18:30+09');
SET LOCAL app.auto_work_order = 'on';
CREATE TEMP TABLE _wo ON COMMIT DROP AS SELECT fn_auto_work_order_draft((SELECT max(alarm_event_id) FROM alarm_event), 'STOP_ALARM') AS wo_no;
SELECT t.eq((SELECT u.home_shift_type FROM maintenance_work_order w JOIN _wo USING (wo_no) JOIN app_user u ON u.user_id = w.assignee_user_id),
            'DAY', '18:30 알람 → 주간 보전 담당');
ROLLBACK;
