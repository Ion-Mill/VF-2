-- =====================================================================
-- 80_demo_reset.sql — 시연 데이터 처음으로 (API명세서 SIM-03, NFR-DATA-10, 2026-10-08)
--   fn_demo_snapshot(): 지금 운영 데이터를 시연 기준점(demo_snapshot 스키마)으로 복사 (목업·생성기 적재 뒤 자동)
--   fn_demo_reset()   : 운영 데이터를 기준점으로 되돌리고 시연 시계를 그때 시각에 멈춰 둔다. 화면에는 RESYNC
-- 대상 = public의 운영 표 전부 (파티션은 부모로). 빼는 것: 설정·계정·코드(role·role_permission·code_label·notification_rule·
--   app_user — 시연 중 바꾼 설정은 남김), 접속 기록(access_log — 감사 기록은 지우지 않음), dataset_info, sim_clock,
--   그리고 이 표들이 가리키는 기준 표(process).
-- 센서 값(sensor_sample, 9월 약 98만 행·DB 약 120MB)은 복사하지 않는다: 추가만 되는 시계열이라 되돌릴 때
--   "기준점 시연 시각 이후 값"만 지운다 — 복사본을 두면 DB가 두 배가 되어 Supabase 무료 한도(500MB)에 가까워진다 (1014 수정사항 7장).
--   센서를 기준점 뒤에 따로 넣어도(--sensor-only) 그대로 남는다.
-- 되돌릴 때는 트리거를 끈 채(session_replication_role = replica) 그대로 채운다 — 재고 수량 같은 계산 값도 복사본 그대로.
-- 이 설정은 슈퍼유저만 바꿀 수 있어 두 함수는 스키마 주인 권한으로 돈다 (Docker의 POSTGRES_USER는 슈퍼유저).
-- =====================================================================

-- 남기는 표가 가리키는 기준 표(예: app_user → process)도 뺀다 — TRUNCATE는 남기는 표의 외래 키를 깨지 못한다
CREATE OR REPLACE FUNCTION fn_demo_tables() RETURNS SETOF text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    -- 남기는 표 + 그 표가 (여러 단계로) 가리키는 기준 표 전부 (예: sensor_sample → sensor_item → alarm_master)
    WITH RECURSIVE keep(oid) AS (
        SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname IN ('role', 'role_permission', 'code_label', 'notification_rule', 'app_user',
                                                      'access_log', 'dataset_info', 'sim_clock', 'sensor_sample', 'sensor_hourly',
                                                      'alarm_check_step')   -- 문서 기준 표 (2026-10-20)
        UNION
        SELECT f.confrelid FROM pg_constraint f JOIN keep k ON f.conrelid = k.oid WHERE f.contype = 'f'
    )
    SELECT c.relname::text
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind IN ('r','p') AND NOT c.relispartition
       AND c.oid NOT IN (SELECT oid FROM keep)
     ORDER BY c.relname;
$$;

CREATE OR REPLACE FUNCTION fn_demo_snapshot() RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE t text; v_tables text[] := ARRAY(SELECT fn_demo_tables());
BEGIN
    FOR t IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'demo_snapshot' AND c.relkind = 'r' AND c.relname <> 'meta' LOOP
        EXECUTE format('DROP TABLE demo_snapshot.%I', t);
    END LOOP;
    FOREACH t IN ARRAY v_tables LOOP
        EXECUTE format('CREATE TABLE demo_snapshot.%I AS SELECT * FROM public.%I', t, t);
    END LOOP;
    INSERT INTO demo_snapshot.meta (id, taken_at, sim_at, clock_mode, speed, tables)
    SELECT 1, now(), app_now(), mode, speed, v_tables FROM sim_clock WHERE id = 1
    ON CONFLICT (id) DO UPDATE SET taken_at = EXCLUDED.taken_at, sim_at = EXCLUDED.sim_at, clock_mode = EXCLUDED.clock_mode,
                                   speed = EXCLUDED.speed, tables = EXCLUDED.tables;
    RETURN cardinality(v_tables);
END $$;
COMMENT ON FUNCTION fn_demo_snapshot() IS '시연 기준점 만들기 (SIM-03). 목업(dev/90)·생성기 적재 뒤 부른다';

-- 기준점의 표 몇 개만 지금 값으로 바꾼다 (2026-10-25). 사내 문서 조각처럼 기준점을 만든 뒤에 넣는 기준 자료용 —
-- 전부 다시 찍으면(fn_demo_snapshot) 그사이 붙인 실시간 기록(생성기 --realtime, 최종용 10/26 오전)까지 기준점에 들어가
-- 시연 서버 [처음으로] 때 시뮬레이터 시작점과 달라진다(BASELINE_MISMATCH). 기준점에 없는 표·없는 기준점은 건너뜀. 반환: 바꾼 표 수
CREATE OR REPLACE FUNCTION fn_demo_snapshot_refresh(p_tables text[]) RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE t text; n int := 0;
BEGIN
    FOR t IN SELECT x FROM unnest(p_tables) x
              WHERE x = ANY ((SELECT tables FROM demo_snapshot.meta WHERE id = 1)::text[]) LOOP
        EXECUTE format('DROP TABLE IF EXISTS demo_snapshot.%I', t);
        EXECUTE format('CREATE TABLE demo_snapshot.%I AS SELECT * FROM public.%I', t, t);
        n := n + 1;
    END LOOP;
    RETURN n;
END $$;
COMMENT ON FUNCTION fn_demo_snapshot_refresh(text[]) IS '시연 기준점의 표 몇 개만 지금 값으로 (사내 문서 조각 적재 뒤 — 실시간 기록은 기준점에 넣지 않음)';

-- 반환: {"tables": 되돌린 표 수, "sim_at": 시연 시계}
-- session_replication_role = replica (트리거·외래 키 확인 끔)는 함수 안에서만 — 끝나면 원래대로
-- 함수 SET 절이나 set_config()로 걸지 않고 EXECUTE 'SET LOCAL …'로 건다: Supabase는 postgres 역할이 슈퍼유저가 아니라
-- SET 문으로만 이 값을 바꿀 수 있다 (2026-10-15 실제 프로젝트에서 확인 — SET 절·set_config는 permission denied)
CREATE OR REPLACE FUNCTION fn_demo_reset() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    m demo_snapshot.meta%ROWTYPE; t text; v_cols text; r record;
    v_prev text := current_setting('session_replication_role');
    v_lock text := current_setting('lock_timeout'); v_try int;
BEGIN
    SELECT * INTO m FROM demo_snapshot.meta WHERE id = 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION '시연 기준점이 없음 — 먼저 fn_demo_snapshot() (POST /api/sim/snapshot)' USING ERRCODE = '23514';
    END IF;
    SET CONSTRAINTS ALL IMMEDIATE;     -- 같은 트랜잭션에 미뤄 둔 외래 키 확인이 있으면 먼저 끝낸다 (TRUNCATE 전)
    -- 표 잠금을 먼저 한꺼번에 (2026-10-25): TRUNCATE가 표를 하나씩 잠그는 동안 화면 조회가 다른 표를 쥐고 있으면 교착 → 500
    --   (DB 중계 [처음으로] 때 실제로 났음). 짧게(0.5초 — 교착 판정 1초 전) 기다려 못 잡으면 놓고 조금 쉬었다 다시 — 조회는 죽이지 않는다
    FOR v_try IN 1..15 LOOP                -- 최대 약 20초 (중계는 30초 기다림)
        BEGIN
            PERFORM set_config('lock_timeout', '500ms', true);
            EXECUTE 'LOCK TABLE ' || (SELECT string_agg(format('public.%I', x), ', ') FROM unnest(m.tables) x) || ' IN ACCESS EXCLUSIVE MODE';
            EXIT;
        EXCEPTION WHEN lock_not_available OR deadlock_detected THEN
            IF v_try = 15 THEN RAISE; END IF;
            PERFORM pg_sleep(0.1 * v_try);
        END;
    END LOOP;
    PERFORM set_config('lock_timeout', v_lock, true);
    EXECUTE 'SET LOCAL session_replication_role = replica';
    EXECUTE 'TRUNCATE ' || (SELECT string_agg(format('public.%I', x), ', ') FROM unnest(m.tables) x);
    FOREACH t IN ARRAY m.tables LOOP
        -- 생성 칼럼(GENERATED ALWAYS)은 빼고 넣는다
        SELECT string_agg(format('%I', a.attname), ', ' ORDER BY a.attnum) INTO v_cols
          FROM pg_attribute a
         WHERE a.attrelid = format('public.%I', t)::regclass AND a.attnum > 0 AND NOT a.attisdropped AND a.attgenerated = ''
           AND EXISTS (SELECT 1 FROM information_schema.columns c
                        WHERE c.table_schema = 'demo_snapshot' AND c.table_name = t AND c.column_name = a.attname);
        EXECUTE format('INSERT INTO public.%I (%s) OVERRIDING SYSTEM VALUE SELECT %s FROM demo_snapshot.%I', t, v_cols, v_cols, t);
    END LOOP;
    -- 센서: 기준점 시각 이후 값만 지운다 (위 설명)
    DELETE FROM sensor_sample WHERE sampled_at >= m.sim_at;
    -- 일련번호를 되돌린 데이터의 최대값에 맞춘다
    FOR r IN SELECT c.table_name, c.column_name FROM information_schema.columns c
              WHERE c.table_schema = 'public' AND c.is_identity = 'YES' AND c.table_name = ANY (m.tables) LOOP
        EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, %L), coalesce((SELECT max(%I) FROM public.%I), 0) + 1, false)',
                       'public.' || r.table_name, r.column_name, r.column_name, r.table_name);
    END LOOP;
    -- 시연 시계: 기준점 시각에 멈춰 둔다 (발표자가 다시 돌린다)
    PERFORM fn_sim_set(m.clock_mode, m.sim_at, m.speed, true);
    PERFORM pg_notify('mom_events', '{"table": "*", "op": "RESYNC"}');   -- 화면이 전부 다시 읽게 (connection 사건)
    EXECUTE format('SET LOCAL session_replication_role = %s', v_prev);   -- 원래대로 (origin)
    RETURN jsonb_build_object('tables', cardinality(m.tables), 'sim_at', m.sim_at, 'snapshot_taken_at', m.taken_at);
END $$;
COMMENT ON FUNCTION fn_demo_reset() IS '시연 데이터 처음으로 (SIM-03): 기준점으로 되돌리고 시연 시계를 그 시각에 멈춤';
