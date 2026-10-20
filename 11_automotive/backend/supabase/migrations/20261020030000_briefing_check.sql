-- =====================================================================
-- 2026-10-20 브리핑 "먼저 챙길 일" 체크 저장 — 이미 올린 mom-db에 바뀐 부분만 (새 표 briefing_check 1개)
--   같은 내용이 db/schema/80_notification_auth.sql 원본에 있다 (처음부터 만들 때는 build_migration.sh).
--   API: GET·POST /api/assistant/briefing/checks (app/routers/notifications.py)
-- 스키마 주인(postgres)으로 한 번 (두 번 돌려도 오류 없음 — 이미 있으면 그대로 두거나 정책만 다시 만든다). 이 파일은 저장소에만 있다 — 공용 mom-db 적용은 DB 담당 몫이다
-- (적용 전에는 API가 이 표를 못 찾아 오류를 내고, 화면은 이 브라우저 저장으로 계속 동작한다)
-- 되돌리기: DROP TABLE briefing_check; (그리고 demo_snapshot.briefing_check, demo_snapshot.meta.tables 에서 이름 빼기)
-- =====================================================================
SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS briefing_check (
    user_id     varchar(20) NOT NULL REFERENCES app_user,
    shift_id    varchar(40) NOT NULL CHECK (btrim(shift_id) <> ''),
    item_key    varchar(120) NOT NULL CHECK (btrim(item_key) <> ''),
    checked_at  timestamptz NOT NULL,
    PRIMARY KEY (user_id, shift_id, item_key)
);
COMMENT ON TABLE briefing_check IS '물리 추가 (2026-10-20): 브리핑 먼저 챙길 일 체크 — 본인 것만, 시각은 시연 시계(app_now)';

-- 권한·RLS (supabase/sql/lockdown.sql과 같은 모양). 개인 체크라 비서 읽기 계정(mom_ai_ro)에는 주지 않는다 (chat_log처럼)
GRANT SELECT, INSERT, UPDATE, DELETE ON briefing_check TO mom_app;
ALTER TABLE briefing_check ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mom_app_all ON briefing_check;
CREATE POLICY mom_app_all ON briefing_check TO mom_app USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS mom_ai_ro_read ON briefing_check;
CREATE POLICY mom_ai_ro_read ON briefing_check FOR SELECT TO mom_ai_ro USING (true);

-- 시연 "처음으로"가 이 표도 비우고 기준점 값(빈 표)으로 되돌리게 기준점 복사본과 목록에 넣는다
CREATE TABLE IF NOT EXISTS demo_snapshot.briefing_check AS SELECT * FROM public.briefing_check;
UPDATE demo_snapshot.meta SET tables = array_append(tables, 'briefing_check') WHERE NOT ('briefing_check' = ANY (tables));
