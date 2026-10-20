-- =====================================================================
-- DB 계정 나누기 (NFR-SEC: 최소 권한). 관리자 계정으로 한 번 실행:
--   psql -v app_password='...' -v ai_password='...' -f db/roles.sql
-- 비밀번호는 저장소에 두지 않는다 (환경 변수 → MOM_DATABASE_URL, MOM_READONLY_DATABASE_URL)
--
--   (스키마 주인)  apply.sh를 돌리는 계정 — 표·함수를 만든다. 앱은 이 계정으로 붙지 않는다
--   mom_app       API 서버. 읽기·쓰기·함수 실행. 표 구조는 못 바꿈
--   mom_ai_ro     AI 비서 조회 도구. 읽기만. 비밀번호 해시·접속 기록은 못 봄
-- 추가만 하는 표·확정 문서 잠금은 트리거가 막으므로 mom_app도 못 고친다.
-- =====================================================================
-- Supabase에서는 btree_gist 확장 함수의 주인이 관리 계정이라 ON ALL FUNCTIONS 가 함수마다 "no privileges" 경고를 낸다
-- (수백 줄, 해롭지 않음 — 우리 함수에는 그대로 걸린다). 경고는 숨기고 오류만 보인다
SET client_min_messages = error;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mom_app') THEN CREATE ROLE mom_app LOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mom_ai_ro') THEN CREATE ROLE mom_ai_ro LOGIN; END IF;
END $$;
ALTER ROLE mom_app PASSWORD :'app_password';
ALTER ROLE mom_ai_ro PASSWORD :'ai_password';
ALTER ROLE mom_app SET timezone = 'Asia/Seoul';
ALTER ROLE mom_ai_ro SET timezone = 'Asia/Seoul';
ALTER ROLE mom_ai_ro SET default_transaction_read_only = on;
ALTER ROLE mom_ai_ro SET statement_timeout = '5s';

GRANT USAGE ON SCHEMA public TO mom_app, mom_ai_ro;

-- API 서버
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mom_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO mom_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mom_app;

-- AI 비서 (읽기만)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mom_ai_ro;
-- 채팅 기록(chat_log)은 본인만 보는 개인 기록이라 비서 읽기 계정도 직접 읽지 않는다 (서버 API로 본인 것만, 5.G.7)
REVOKE SELECT ON app_user, access_log, chat_log, briefing_check FROM mom_ai_ro;
GRANT SELECT (user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active)
    ON app_user TO mom_ai_ro;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mom_app;
GRANT EXECUTE ON FUNCTION app_now() TO mom_ai_ro;
-- 교대 진행 뷰(v_shift_progress)가 부르는 읽기 전용 계산 함수 (손실 수량·교대 실적, R-46·R-47)
GRANT EXECUTE ON FUNCTION fn_failure_loss_qty(timestamptz, timestamptz), fn_speed_loss_qty(timestamptz, timestamptz),
                          fn_shift_actual_qty(text) TO mom_ai_ro;
-- 2026-10-20: 속도 손실·로트 예상 완료 계산 (v_shift_progress·v_production_lot이 부름 — functions/35_live_calc.sql)
GRANT EXECUTE ON FUNCTION fn_shift_break_start(text, date), fn_work_minutes(timestamptz, timestamptz),
                          fn_add_work_minutes(timestamptz, numeric), fn_lot_expected_complete(text),
                          fn_interval_losses(timestamptz, timestamptz, text) TO mom_ai_ro;

-- 나중에 만드는 표·함수도 같은 권한 (스키마 주인 계정으로 실행했을 때)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mom_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO mom_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO mom_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
