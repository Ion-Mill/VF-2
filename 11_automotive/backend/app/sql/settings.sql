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

-- 사용자 고치기(SET-03 PATCH)는 2026-10-25부터 직원 관리와 같은 길 — app/services/staff.py update_user, app/sql/staff.sql user_set
