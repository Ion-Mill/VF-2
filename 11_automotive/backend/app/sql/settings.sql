-- 설정 (SCR-25, API명세서 SET-01~03). 바꾸는 것은 MGR만 (R-58 — 라우터 권한 SETTINGS·SETTING)

-- 교대 목표·하루 목표: 지금 교대와 다가오는 교대 (총 목표 = 목표 + 이월, R-88)
-- name: targets
SELECT s.shift_id, s.work_date, s.shift_type, s.start_at, s.target_qty, s.carry_over_qty,
       s.target_qty + s.carry_over_qty AS total_target_qty, d.daily_target_qty
  FROM shift s JOIN work_day d USING (work_date)
 WHERE s.end_at > app_now() ORDER BY s.start_at LIMIT 6;

-- 아직 시작하지 않은 교대의 교대 목표, 아직 교대가 시작하지 않은 근무일의 하루 목표를 바꾼다 (지난·진행 중 값은 그대로)
-- name: targets_update
WITH sh AS (
    UPDATE shift SET target_qty = CAST(:shift_target_qty AS int)
     WHERE CAST(:shift_target_qty AS int) IS NOT NULL AND start_at > app_now()
    RETURNING shift_id),
wd AS (
    UPDATE work_day SET daily_target_qty = CAST(:daily_target_qty AS int)
     WHERE CAST(:daily_target_qty AS int) IS NOT NULL AND is_workday
       AND NOT EXISTS (SELECT 1 FROM shift s WHERE s.work_date = work_day.work_date AND s.start_at <= app_now())
    RETURNING work_date)
SELECT (SELECT count(*) FROM sh)::int AS shifts_changed, (SELECT count(*) FROM wd)::int AS days_changed;

-- 목표를 바꾼 뒤 다가오는 야간 이월을 다시 계산 (주간 목표가 바뀌면 이월도 바뀜)
-- name: targets_refresh_carry
SELECT count(fn_refresh_carry_over(work_date))::int AS refreshed FROM shift WHERE shift_type = 'NIGHT' AND end_at > app_now();

-- name: users
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active, created_at, last_login_at
  FROM app_user ORDER BY role_code, user_id;

-- 사용자 고치기 (비밀번호는 여기서 바꾸지 않음 — tools/gen_dev_users.py, 로그인 방식은 [선택 필요: 기술 회의])
-- name: user_update
UPDATE app_user
   SET user_name = coalesce(CAST(:user_name AS varchar), user_name),
       role_code = coalesce(CAST(:role_code AS varchar), role_code),
       home_shift_type = coalesce(CAST(:home_shift_type AS varchar), home_shift_type),
       home_process_code = coalesce(CAST(:home_process_code AS varchar), home_process_code),
       home_process_code_2 = coalesce(CAST(:home_process_code_2 AS varchar), home_process_code_2),
       is_active = coalesce(CAST(:is_active AS boolean), is_active)
 WHERE user_id = :user_id;
