-- =====================================================================
-- Supabase 잠그기 — db/roles.sql 다음에 스키마 주인(postgres)으로 한 번 (supabase/load_data.sh 가 부름)
-- Supabase는 public 스키마를 API(PostgREST)로 내보내고 anon·authenticated 역할에 권한을 준다.
-- 이 DB는 우리 API 서버(mom_app)·비서 읽기 계정(mom_ai_ro)만 쓰므로:
--   1) anon·authenticated 의 public·demo_snapshot 권한을 모두 거둔다 (앞으로 만드는 표도)
--   2) 모든 표에 RLS를 켜고, mom_app(읽기·쓰기)·mom_ai_ro(읽기) 정책만 둔다 — Supabase 보안 점검(advisor)의
--      "RLS 꺼짐" 경고도 없어진다. 표 주인(postgres)과 SECURITY DEFINER 함수(시연 되돌리기)는 RLS를 건너뛴다
--   3) DB 시간대 = 한국 (앱 연결은 따로 Asia/Seoul을 걸지만 SQL 편집기·psql도 같게)
-- 화면(프런트엔드)이 Supabase API를 직접 부르지 않는다 — 화면은 우리 API 서버만 부른다.
-- =====================================================================
SET client_min_messages = error;   -- btree_gist 확장 함수(관리 계정 소유)마다 나는 "no privileges could be revoked" 경고 숨김
DO $$
DECLARE r record; v_roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ') INTO v_roles FROM pg_roles WHERE rolname IN ('anon', 'authenticated');
    IF v_roles IS NOT NULL THEN
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %s', v_roles);
        EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %s', v_roles);
        EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %s', v_roles);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %s', v_roles);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %s', v_roles);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %s', v_roles);
        IF to_regnamespace('demo_snapshot') IS NOT NULL THEN
            EXECUTE format('REVOKE ALL ON SCHEMA demo_snapshot FROM %s', v_roles);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA demo_snapshot FROM %s', v_roles);
        END IF;
    END IF;
    FOR r IN SELECT c.oid::regclass AS t, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') LOOP
        EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', r.t);
        EXECUTE format('DROP POLICY IF EXISTS mom_app_all ON %s', r.t);
        EXECUTE format('CREATE POLICY mom_app_all ON %s TO mom_app USING (true) WITH CHECK (true)', r.t);
        EXECUTE format('DROP POLICY IF EXISTS mom_ai_ro_read ON %s', r.t);
        EXECUTE format('CREATE POLICY mom_ai_ro_read ON %s FOR SELECT TO mom_ai_ro USING (true)', r.t);
    END LOOP;
    EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'Asia/Seoul');
END $$;

-- 확인: RLS가 꺼진 public 표 (0행이어야 함)
SELECT c.relname AS rls_off FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity;
