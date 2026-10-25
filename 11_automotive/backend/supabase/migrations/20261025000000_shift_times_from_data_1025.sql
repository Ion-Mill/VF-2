-- 2026-10-25 (구현_중_수정사항/1025_수정간단내용.md 8·9장) 최종용·영상용 데이터(교대 09~18 / 21~06)에 맞춘 백엔드·DB
-- ① 교대 안 휴식 = 교대 시작 + 4시간 (fn_shift_break_start·v_shift_progress) — 주간 12:00·야간 00:00을 박아 두던 것.
--    교대 08~17/20~05(옛 9월 데이터)도 그대로 맞다
-- ② fn_ensure_work_day: 일요일은 휴무로 (생성기 휴무 규칙)
-- ③ fn_demo_snapshot_refresh(text[]): 기준점의 표 몇 개만 지금 값으로 (사내 문서 조각 적재 뒤 — 실시간 기록이 기준점에 들어가지 않게)
-- ④ fn_demo_reset: 표 잠금을 먼저 한꺼번에, 짧게 기다리고 다시 (화면 조회와 교착해 500 나던 것)
-- ⑤ fn_auto_work_order_draft: 이 알람의 작업지시서가 이미 있으면 만들지 않음 (DB 중계가 최종용 오전 사건 문서를 같이 보낼 때),
--    교대 사이 알람의 담당 교대 = 바로 앞에 시작한 교대 (시각 8~16시를 박지 않음)
-- ⑥ 알림 규칙 설명 글: 교대·일일 보고서 시각을 박지 않음
-- 원본: backend/db/functions/35_live_calc.sql·70_realtime.sql·80_demo_reset.sql, db/views/10_views.sql·30_live_rules.sql,
--   db/seed/30_notification_rules.sql (같은 글자)
-- 되돌리기: 20261020020000·20261024000000·20261014000000 마이그레이션의 같은 이름 정의를 다시 실행하고
--   DROP FUNCTION fn_demo_snapshot_refresh(text[]). 칸 이름·타입은 그대로라 뷰는 CREATE OR REPLACE로 되돌릴 수 있다.

CREATE OR REPLACE FUNCTION fn_shift_break_start(p_shift_type text, p_work_date date) RETURNS timestamptz
LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        (SELECT s.start_at + interval '4 hours' FROM shift s WHERE s.work_date = p_work_date AND s.shift_type = p_shift_type),
        (SELECT (p_work_date + (t.start_at AT TIME ZONE 'Asia/Seoul')::time) AT TIME ZONE 'Asia/Seoul' + interval '4 hours'
           FROM shift t WHERE t.shift_type = p_shift_type ORDER BY t.start_at DESC LIMIT 1),
        CASE WHEN p_shift_type = 'DAY' THEN (p_work_date + time '12:00') AT TIME ZONE 'Asia/Seoul'
             ELSE (p_work_date + 1 + time '00:00') AT TIME ZONE 'Asia/Seoul' END);
$$;

CREATE OR REPLACE VIEW v_shift_progress AS
WITH b0 AS (
    SELECT t.*, least(greatest(app_now(), t.start_at), t.end_at) AS as_of,
           t.start_at + interval '4 hours' AS break_start_at
      FROM v_shift_target t
), b AS (
    SELECT b0.*, b0.break_start_at + interval '1 hour' AS break_end_at,
           -- 최근 계획 60분 창의 시작: 휴식이 끼면 그만큼 앞으로
           b0.as_of - interval '60 minutes'
             - greatest(interval '0', least(b0.as_of, b0.break_start_at + interval '1 hour')
                                      - greatest(b0.as_of - interval '60 minutes', b0.break_start_at)) AS rate_from_at
      FROM b0
), m AS (
    SELECT b.*,
           least(b.planned_time_min,
                 greatest(0, (extract(epoch FROM (b.as_of - b.start_at))
                              - extract(epoch FROM greatest(interval '0', least(b.as_of, b.break_end_at)
                                                                          - greatest(b.start_at, b.break_start_at)))) / 60)
                )::numeric AS elapsed_min,
           (SELECT coalesce(sum(o.gq + o.rq), 0) FROM operation_report o
             WHERE o.shift_id = b.shift_id AND o.process_code = 'OP-50' AND o.end_at <= b.as_of)::int AS actual_qty,
           (SELECT coalesce(sum(o.gq + o.rq), 0) FROM operation_report o
             WHERE o.shift_id = b.shift_id AND o.process_code = 'OP-50' AND o.end_at <= b.as_of
               AND o.end_at > b.rate_from_at)::int AS last_hour_qty,
           (SELECT coalesce(sum(o.sq), 0) FROM operation_report o
             WHERE o.shift_id = b.shift_id AND o.end_at <= b.as_of)::int AS defect_qty,
           fn_failure_loss_qty(b.start_at, b.as_of) AS failure_loss_qty,
           fn_speed_loss_qty(b.start_at, b.as_of)   AS speed_loss_qty
      FROM b
), f AS (
    SELECT m.*,
           CASE WHEN m.elapsed_min <= 0 THEN NULL
                WHEN m.elapsed_min < 60 THEN m.actual_qty / m.elapsed_min
                ELSE m.last_hour_qty / 60.0 END AS rate_per_min
      FROM m
), p AS (
    SELECT f.*, round(f.actual_qty + f.rate_per_min * (f.planned_time_min - f.elapsed_min))::int AS forecast_qty FROM f
)
SELECT p.shift_id, p.work_date, p.shift_type, p.start_at, p.end_at, p.as_of, p.planned_time_min, p.supervisor_user_id,
       p.break_start_at, p.break_end_at,
       p.target_qty, p.carry_over_qty, p.total_target_qty, p.carry_over_is_provisional, p.report_status, p.is_report_confirmed,
       p.actual_qty, p.defect_qty,
       round(p.elapsed_min, 1) AS elapsed_min, round(p.planned_time_min - p.elapsed_min, 1) AS remaining_min,
       p.last_hour_qty, round(p.rate_per_min, 3) AS rate_per_min, p.forecast_qty,
       greatest(0, p.total_target_qty - p.forecast_qty)                AS shortfall_qty,
       p.forecast_qty < 0.9 * p.total_target_qty                        AS is_target_risk,
       p.failure_loss_qty, p.speed_loss_qty, p.failure_loss_qty + p.speed_loss_qty AS loss_qty,
       true                                                             AS loss_is_estimated
  FROM p;

CREATE OR REPLACE FUNCTION fn_ensure_work_day(p_date date) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE tpl date; n int := 0;
BEGIN
    SELECT max(work_date) INTO tpl FROM work_day WHERE is_workday AND work_date < p_date
       AND EXISTS (SELECT 1 FROM shift s WHERE s.work_date = work_day.work_date);
    IF tpl IS NULL THEN RETURN 0; END IF;
    INSERT INTO work_day (work_date, is_workday, daily_target_qty)
    SELECT p_date, extract(isodow FROM p_date) <> 7, daily_target_qty FROM work_day WHERE work_date = tpl
    ON CONFLICT (work_date) DO NOTHING;
    IF NOT (SELECT is_workday FROM work_day WHERE work_date = p_date) THEN RETURN 0; END IF;
    WITH ins AS (
        INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, carry_over_qty,
                           supervisor_user_id)
        SELECT to_char(p_date, 'YYYY-MM-DD') || '-' || left(s.shift_type, 1), p_date, s.shift_type,
               s.start_at + (p_date - tpl) * interval '1 day', s.end_at + (p_date - tpl) * interval '1 day',
               s.planned_time_min, s.target_qty, 0, s.supervisor_user_id
          FROM shift s WHERE s.work_date = tpl
        ON CONFLICT DO NOTHING RETURNING 1)
    SELECT count(*) INTO n FROM ins;
    RETURN n;
END $$;
COMMENT ON FUNCTION fn_ensure_work_day(date) IS '근무일·교대 2개를 가장 최근 근무일을 본떠 만든다 (적재 뒤 10/1, 스케줄러가 오늘·내일)';

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
-- 새 함수 권한 (db/roles.sql·supabase/sql/lockdown.sql과 같게): 앱 계정만. 공용 DB는 함수 기본 권한이 PUBLIC 실행이라 꼭 거둔다
REVOKE EXECUTE ON FUNCTION fn_demo_snapshot_refresh(text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fn_demo_snapshot_refresh(text[]) TO mom_app;
DO $$
DECLARE v_roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ') INTO v_roles FROM pg_roles WHERE rolname IN ('anon', 'authenticated');
    IF v_roles IS NOT NULL THEN
        EXECUTE format('REVOKE ALL ON FUNCTION fn_demo_snapshot_refresh(text[]) FROM %s', v_roles);
    END IF;
END $$;

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

CREATE OR REPLACE FUNCTION fn_auto_work_order_draft(p_alarm_event_id bigint, p_trigger text, p_trigger_notification_id bigint DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    a alarm_event%ROWTYPE; m alarm_master%ROWTYPE;
    v_sec text; v_steps jsonb; v_parts jsonb; v_title text; v_symptom text; v_wo text; v_shift text; v_mnt text;
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on'
       OR current_setting('app.auto_work_order', true) IS NOT DISTINCT FROM 'off' THEN RETURN NULL; END IF;
    SELECT * INTO a FROM alarm_event WHERE alarm_event_id = p_alarm_event_id;
    SELECT * INTO m FROM alarm_master WHERE alarm_code = a.alarm_code;
    IF fn_equipment_process(a.equipment_id) <> 'OP-30' THEN RETURN NULL; END IF;
    IF p_trigger = 'STOP_ALARM' AND EXISTS (SELECT 1 FROM maintenance_work_order
                                              WHERE equipment_id = a.equipment_id AND status NOT IN ('DONE','CANCELLED')) THEN
        RETURN NULL;   -- 그 설비에 진행 중인 작업지시서가 있으면 새로 만들지 않는다 (화면과 같음)
    END IF;
    IF p_trigger = 'STOP_ALARM' AND EXISTS (SELECT 1 FROM maintenance_work_order WHERE alarm_event_id = p_alarm_event_id) THEN
        RETURN NULL;   -- 이 알람의 작업지시서가 이미 있음 (2026-10-25 — DB 중계가 오전 사건의 끝난 작업지시서와 알람을 같이 보낼 때)
    END IF;
    SELECT 'DOC-03 §' || section INTO v_sec FROM alarm_guide_map WHERE alarm_code = a.alarm_code AND doc_no = 'DOC-03' ORDER BY seq LIMIT 1;
    v_sec := coalesce(v_sec, 'DOC-03');
    -- 작업 순서 (참조 줄 풀기)
    WITH base AS (
        SELECT s.seq, s.step_text FROM alarm_check_step s
         WHERE s.alarm_code = a.alarm_code
           AND (CASE WHEN p_trigger = 'REPEAT_2' AND EXISTS (SELECT 1 FROM alarm_check_step x WHERE x.alarm_code = a.alarm_code AND x.step_kind = 'MNT')
                     THEN s.step_kind = 'MNT' ELSE s.step_kind IN ('OPR','MNT') END)
    ), expanded AS (
        SELECT b.seq, 0 AS sub, b.step_text, v_sec AS src
          FROM base b WHERE b.step_text !~ '§\d+\.\d+ 점검 \d+~\d+와 같다$'
        UNION ALL
        SELECT b.seq, r.n, t.step_text || format(' (§%s 점검 %s)', mm.g[1], r.n), 'DOC-03 §' || mm.g[1]
          FROM base b
          CROSS JOIN LATERAL (SELECT regexp_match(b.step_text, '§(\d+\.\d+) 점검 (\d+)~(\d+)와 같다$') AS g) mm
          CROSS JOIN LATERAL generate_series(mm.g[2]::int, mm.g[3]::int) r(n)
          JOIN LATERAL (SELECT s2.step_text FROM alarm_check_step s2
                          JOIN alarm_guide_map gm ON gm.alarm_code = s2.alarm_code AND gm.doc_no = 'DOC-03' AND gm.section = mm.g[1]
                         WHERE s2.step_kind IN ('OPR','MNT') ORDER BY s2.seq OFFSET r.n - 1 LIMIT 1) t ON true
         WHERE mm.g IS NOT NULL
    )
    SELECT coalesce(jsonb_agg(jsonb_build_object('step_text', step_text, 'source_section', src) ORDER BY seq, sub), '[]'::jsonb)
      INTO v_steps FROM expanded;
    -- 예상 부품 = 지난 같은 알람 작업기록서에 쓴 부품
    SELECT coalesce(jsonb_agg(jsonb_build_object('item_no', item_no, 'qty', qty) ORDER BY item_no), '[]'::jsonb) INTO v_parts
      FROM (SELECT p.item_no, max(p.qty) AS qty
              FROM work_record_part p JOIN work_record w USING (record_no)
              LEFT JOIN maintenance_work_order o ON o.wo_no = w.wo_no
              JOIN alarm_event e ON e.alarm_event_id = coalesce(w.alarm_event_id, o.alarm_event_id)
             WHERE e.alarm_code = a.alarm_code AND e.alarm_event_id <> a.alarm_event_id
             GROUP BY p.item_no) x;
    v_title := CASE WHEN p_trigger = 'REPEAT_2' THEN format('%s 알람 %s 반복 — 원인 점검 (2단계)', a.equipment_id, a.alarm_code)
                    ELSE format('%s 알람 %s (%s) 점검', a.equipment_id, a.alarm_code, btrim(regexp_replace(m.name_ko, '\(.*\)', ''))) END;
    v_symptom := coalesce((SELECT step_text FROM alarm_check_step WHERE alarm_code = a.alarm_code AND step_kind = 'SYMPTOM'), m.easy_desc, m.name_ko)
                 || CASE WHEN coalesce(m.chain_rule, '') <> '' THEN ' — 연쇄 알람 ' || m.chain_rule ELSE '' END;
    v_wo := fn_create_work_order_draft(a.equipment_id, v_title, v_symptom,
                p_alarm_event_id => CASE WHEN p_trigger = 'REPEAT_2' THEN NULL ELSE a.alarm_event_id END,
                p_trigger_notification_id => p_trigger_notification_id,
                p_steps => v_steps, p_parts => v_parts, p_lot_no => a.lot_no, p_at => a.occurred_at);
    -- 담당 = 알람 시각 교대의 보전 담당자 (사람이 바꿀 수 있음)
    SELECT shift_type INTO v_shift FROM shift WHERE start_at <= a.occurred_at AND end_at > a.occurred_at;
    -- 교대 사이(라인 정지)면 바로 앞에 시작한 교대 (2026-10-25 — 시각 8~16시를 박지 않음)
    v_shift := coalesce(v_shift, (SELECT shift_type FROM shift WHERE start_at <= a.occurred_at ORDER BY start_at DESC LIMIT 1), 'DAY');
    SELECT user_id INTO v_mnt FROM app_user WHERE is_active AND role_code = 'MNT' AND home_shift_type = v_shift ORDER BY user_id LIMIT 1;
    UPDATE maintenance_work_order SET assignee_user_id = coalesce(assignee_user_id, v_mnt)
     WHERE wo_no = v_wo AND status = 'AI_DRAFT' AND v_mnt IS NOT NULL;
    RETURN v_wo;
END $$;

UPDATE notification_rule SET condition_text = '일일 보고서 AI비서 초안이 생길 때 (야간 교대 보고서 확정 즉시, 늦어도 야간 교대 끝 1시간 뒤) → MGR'
 WHERE rule_code = 'DAILY_REPORT_PENDING';
UPDATE notification_rule SET condition_text = '교대 끝(주간·야간) 교대 보고서 AI비서 초안이 생길 때 → 그 교대 반장'
 WHERE rule_code = 'SHIFT_REPORT_PENDING';
