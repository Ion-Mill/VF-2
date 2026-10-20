-- 2026-10-20 브리핑 "먼저 챙길 일" 체크 저장 (briefing_check): 사용자별·교대별·항목별, 거듭 체크 안전, 입력 길이·빈 글자 막기,
-- 시연 되돌리기 목록, 비서 읽기 계정은 못 읽음
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');

INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES ('U02', 'r1/S1', 'r1/pm:PM-VF2-01-W-05', app_now());
SELECT t.eq((SELECT count(*) FROM briefing_check WHERE user_id = 'U02')::int, 1, '체크 1건');
SELECT t.eq((SELECT checked_at FROM briefing_check WHERE user_id = 'U02'), '2026-09-15 13:00+09'::timestamptz, '시각은 시연 시계(app_now)');

-- 거듭 체크는 한 줄 (API 쿼리와 같은 ON CONFLICT)
INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES ('U02', 'r1/S1', 'r1/pm:PM-VF2-01-W-05', app_now())
ON CONFLICT (user_id, shift_id, item_key) DO NOTHING;
SELECT t.eq((SELECT count(*) FROM briefing_check WHERE user_id = 'U02')::int, 1, '같은 항목을 또 체크해도 1건');

-- 다른 사용자·다른 교대·다른 항목은 따로
INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES
    ('U03', 'r1/S1', 'r1/pm:PM-VF2-01-W-05', app_now()), ('U02', 'r1/S2', 'r1/pm:PM-VF2-01-W-05', app_now()),
    ('U02', 'r1/S1', 'r1/lock', app_now());
SELECT t.eq((SELECT count(*) FROM briefing_check)::int, 4, '사용자·교대·항목이 다르면 따로 (4건)');
SELECT t.eq((SELECT count(*) FROM briefing_check WHERE user_id = 'U02' AND shift_id = 'r1/S1')::int, 2, '본인·그 교대만 2건');

-- 풀기는 그 한 줄만, 없는 걸 풀어도 오류 아님
DELETE FROM briefing_check WHERE user_id = 'U02' AND shift_id = 'r1/S1' AND item_key = 'r1/lock';
DELETE FROM briefing_check WHERE user_id = 'U02' AND shift_id = 'r1/S1' AND item_key = 'r1/없는-항목';
SELECT t.eq((SELECT count(*) FROM briefing_check)::int, 3, '풀면 그 줄만 사라짐');

-- 입력 막기
SELECT t.throws($$INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES ('U02', '  ', 'x', app_now())$$, 'briefing_check', '빈 교대 글자는 안 됨');
SELECT t.throws($$INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES ('U02', 'S1', '', app_now())$$, 'briefing_check', '빈 항목 글자는 안 됨');
SELECT t.throws($$INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES ('U02', 'S1', repeat('가', 121), app_now())$$, 'value too long', '항목 글자는 120자까지');
SELECT t.throws($$INSERT INTO briefing_check (user_id, shift_id, item_key, checked_at) VALUES ('없는사람', 'S1', 'x', app_now())$$, 'briefing_check_user_id_fkey', '없는 사용자는 안 됨');

-- 시연 "처음으로"가 비우는 표에 들어 있고, 비서 읽기 계정은 읽지 못한다 (chat_log처럼 개인 기록)
SELECT t.ok('briefing_check' IN (SELECT fn_demo_tables()), '시연 되돌리기 목록에 있음');
SELECT t.ok(NOT has_table_privilege('mom_ai_ro', 'briefing_check', 'SELECT'), '비서 읽기 계정(mom_ai_ro)은 못 읽음');
SELECT t.ok(has_table_privilege('mom_app', 'briefing_check', 'INSERT'), '앱 계정(mom_app)은 쓸 수 있음');
ROLLBACK;
