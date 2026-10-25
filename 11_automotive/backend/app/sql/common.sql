-- 공통 쿼리. 이름 규칙: "파일이름.쿼리이름" (예: common.now)
-- 매개변수는 :이름. 형식을 알 수 없는 자리에는 CAST(:x AS 형식)을 쓴다 (tools/check_queries.py가 PREPARE로 확인)

-- name: now
SELECT app_now() AS now;

-- name: permissions
SELECT role_code, target, action, scope FROM role_permission;

-- name: codes
SELECT code_group, code, name_ko, sort_order FROM code_label
 WHERE CAST(:code_group AS text) IS NULL OR code_group = CAST(:code_group AS text)
 ORDER BY code_group, sort_order;

-- name: user_by_id
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active, password_hash
  FROM app_user WHERE user_id = :user_id;

-- 비밀번호 해시 없이 (읽기 전용 계정 mom_ai_ro도 읽을 수 있는 칸만)
-- name: user_public
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active FROM app_user WHERE user_id = :user_id;

-- name: touch_login
UPDATE app_user SET last_login_at = now() WHERE user_id = :user_id;

-- name: access_log
INSERT INTO access_log (user_id, action, method, path, status_code, client_ip, detail)
VALUES (CAST(:user_id AS varchar), :action, CAST(:method AS varchar), CAST(:path AS varchar), CAST(:status_code AS smallint),
        CAST(:client_ip AS inet), CAST(:detail AS jsonb));

-- name: dataset_info
SELECT is_virtual, label, seed, period_from, period_to, loaded_at FROM dataset_info WHERE id = 1;

-- name: sim_clock
SELECT mode, sim_anchor, real_anchor, speed, is_paused, app_now() AS now FROM sim_clock WHERE id = 1;

-- name: sim_set
SELECT fn_sim_set(:mode, CAST(:sim_at AS timestamptz), CAST(:speed AS numeric), CAST(:paused AS boolean)) AS now;

-- 여러 서버가 떠도 스케줄러·파일 감시가 한 번만 돌게 (트랜잭션이 끝나면 풀림)
-- name: try_lock
SELECT pg_try_advisory_xact_lock(CAST(:key AS bigint)) AS locked;

-- 시연 [역할 바꿔 보기] (AUTH-04): 그 역할의 사용 중인 첫 사용자
-- name: first_user_of_role
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active
  FROM app_user WHERE role_code = :role_code AND is_active ORDER BY user_id LIMIT 1;

-- 시연 데이터 처음으로 (SIM-03): 기준점으로 되돌리고 시연 시계를 그 시각에 멈춤
-- name: demo_reset
SELECT fn_demo_reset() AS result;

-- 시연 기준점 만들기 (지금 데이터를 "처음"으로)
-- name: demo_snapshot
SELECT fn_demo_snapshot() AS tables;

-- 운영 데이터가 가상인지 (모든 운영 데이터 응답의 is_synthetic, NFR-DATA-08)
-- name: is_synthetic
SELECT is_virtual FROM dataset_info WHERE id = 1;

-- 시연 넘기기 목표 시각 (API-SIM-02): 오늘(시연 시계, 한국 시간) 주간 교대 끝(DAY_END) 또는 야간 교대 시작(NIGHT_START).
-- 2026-10-25: 시각(17:00·20:00)을 박지 않고 그날 shift 행에서 — 생성기 Realtime.skip과 같은 이름. 그날 교대가 없으면 at = NULL
-- name: skip_target
SELECT t.at, app_now() >= t.at AS past
  FROM (SELECT CASE CAST(:target AS text) WHEN 'DAY_END' THEN s.end_at WHEN 'NIGHT_START' THEN s.start_at END AS at
          FROM (SELECT CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) AS d) today
          LEFT JOIN shift s ON s.work_date = today.d
                           AND s.shift_type = CASE CAST(:target AS text) WHEN 'DAY_END' THEN 'DAY' ELSE 'NIGHT' END) t;
