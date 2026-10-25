-- 시뮬레이터(설비 수집기) → 플랫폼 한 방향 받기 (FR-AST-COM-11). 서비스 키(ingest)로만 부른다.
-- 알람은 alarms.ingest, CMM 결과 파일은 quality.import_cmm

-- name: state_change
SELECT fn_state_change(:equipment_id, :state_code, CAST(:at AS timestamptz), CAST(:execution AS text),
                       coalesce(CAST(:warn_marker AS boolean), false), CAST(:reason_suggested_code AS text),
                       CAST(:alarm_event_id AS bigint), CAST(:pm_record_id AS bigint)) AS state_log_id;

-- name: production
SELECT fn_report_production(:lot_no, :equipment_id, :worker_user_id, CAST(:gq AS int), coalesce(CAST(:rq AS int), 0),
                            coalesce(CAST(:sq AS int), 0), CAST(:at AS timestamptz), CAST(:shift_id AS text)) AS op_report_id;

-- 재공 (5분, 병목 앞뒤 1분). 같은 시각이 또 오면 덮어쓴다. 한도 넘김은 DB 트리거가 막는다 (R-13)
-- name: wip
INSERT INTO wip_log (buffer_code, logged_at, wip_qty, soak_shelf_qty, interval_type)
VALUES (:buffer_code, coalesce(CAST(:at AS timestamptz), app_now()), :wip_qty, CAST(:soak_shelf_qty AS int),
        coalesce(CAST(:interval_type AS varchar), 'MIN5'))
ON CONFLICT (buffer_code, logged_at) DO UPDATE SET wip_qty = EXCLUDED.wip_qty, soak_shelf_qty = EXCLUDED.soak_shelf_qty;

-- 센서 여러 개를 한 번에: rows = [{"sensor_code":..., "sampled_at":..., "interval_type":"MIN1_AVG", "value":...}]
-- name: sensors
INSERT INTO sensor_sample (equipment_id, sensor_code, sampled_at, interval_type, value)
SELECT :equipment_id, r.sensor_code, r.sampled_at, coalesce(r.interval_type, 'MIN1_AVG'), r.value
  FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(sensor_code varchar, sampled_at timestamptz, interval_type varchar, value real)
ON CONFLICT DO NOTHING;

-- name: bottleneck
INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code, alarm_event_id)
VALUES (coalesce(CAST(:at AS timestamptz), app_now()),
        (SELECT new_process_code FROM bottleneck_log WHERE changed_at < coalesce(CAST(:at AS timestamptz), app_now())
          ORDER BY changed_at DESC LIMIT 1),
        :process_code, :cause_code, CAST(:alarm_event_id AS bigint))
RETURNING bottleneck_log_id;

-- name: order_create
SELECT fn_create_order(:product_code, CAST(:order_qty AS int), CAST(:due_at AS timestamptz), CAST(:at AS timestamptz)) AS order_no;

-- name: lot_start
SELECT fn_start_lot(:order_no, :material_lot_no, CAST(:input_qty AS int), CAST(:at AS timestamptz)) AS lot_no;

-- name: lot_arrived
SELECT fn_lot_to_inspection(:lot_no);

-- ---------------------------------------------------------------------
-- 시연 서버 → DB 표 맞추기 (POST /api/ingest/sync, 2026-10-23 — app/services/sim_sync.py). 시연 모드만.
-- 시뮬레이터 10/1 기록(생성기 export와 같은 칸·번호)을 표째로 덮어쓴다. 넣는 문장은 표·칸 이름이 바뀌어 서비스가 만들고,
-- 표·칸 이름은 아래 목록(DB 카탈로그)에 있는 것만 쓴다.
-- name: sync_columns
SELECT c.table_name::text, c.column_name::text, (c.is_generated = 'ALWAYS') AS generated,
       CASE WHEN c.is_nullable = 'NO' AND c.is_identity = 'NO' THEN c.column_default END AS not_null_default
  FROM information_schema.columns c
 WHERE c.table_schema = 'public' AND c.table_name IN (SELECT jsonb_array_elements_text(CAST(:tables AS jsonb)))
 ORDER BY c.table_name, c.ordinal_position;

-- name: sync_pkeys
SELECT c.conrelid::regclass::text AS table_name, a.attname::text AS column_name
  FROM pg_constraint c JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, n) ON true
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
 WHERE c.contype = 'p' AND c.connamespace = 'public'::regnamespace
   AND c.conrelid::regclass::text IN (SELECT jsonb_array_elements_text(CAST(:tables AS jsonb)))
 ORDER BY 1, k.n;

-- name: sync_identity
SELECT table_name::text, column_name::text FROM information_schema.columns
 WHERE table_schema = 'public' AND is_identity = 'YES'
   AND table_name IN (SELECT jsonb_array_elements_text(CAST(:tables AS jsonb)));

-- 생성기 적재(tools/load_generated.py)와 같게: 알림·자동 규칙 끔(app.loading). 순환 외래 키는 원래 커밋 때 확인(95_deferred_fks)
-- name: sync_loading
SELECT set_config('app.loading', :value, true);

-- 넣은 뒤 업무 번호 카운터(PO 등)·공구 누적 같은 "지금 상태" 칸을 맞춘다 (load_generated --realtime 끝과 같음)
-- name: sync_after
SELECT (SELECT count(*) FROM fn_sync_doc_numbers()) AS doc_numbers, fn_sync_after_load() AS tools;

-- 새로 들어온 알람의 뒷일 = fn_ingest_alarm의 기록 뒤 부분 (등급별 알림 R-38 → OP-30 정지 초안 → 반복 알람 R-70)
-- name: sync_alarm_notify
SELECT fn_raise_notification(
           CASE m.severity WHEN 'STOP' THEN 'ALARM_STOP' WHEN 'WARN' THEN 'ALARM_WARN' ELSE 'ALARM_GUIDE' END,
           format('%s 알람 %s (%s)', a.equipment_id, a.alarm_code, m.name_ko),
           jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id, 'lot_no', a.lot_no),
           a.occurred_at,
           p_recipients => ARRAY(SELECT u.user_id FROM app_user u
                                  WHERE u.is_active AND (m.severity = 'STOP'
                                        OR (u.role_code = 'OPR' AND (fn_equipment_process(a.equipment_id)
                                                IN (u.home_process_code, u.home_process_code_2) OR u.home_process_code IS NULL))
                                        OR (u.role_code = 'MNT' AND m.severity = 'WARN'))))
  FROM alarm_event a JOIN alarm_master m USING (alarm_code)
 WHERE a.alarm_event_id = :alarm_event_id;

-- name: sync_alarm_auto_wo
SELECT fn_auto_work_order_draft(a.alarm_event_id, 'STOP_ALARM')
  FROM alarm_event a JOIN alarm_master m USING (alarm_code)
 WHERE a.alarm_event_id = :alarm_event_id AND m.severity = 'STOP' AND fn_equipment_process(a.equipment_id) = 'OP-30';

-- name: sync_alarm_repeat
SELECT fn_check_repeat_alarm(a.alarm_event_id)
  FROM alarm_event a JOIN alarm_master m USING (alarm_code)
 WHERE a.alarm_event_id = :alarm_event_id AND m.severity <> 'GUIDE';

-- DB에 그 함수가 있나 (옛 로컬 DB에는 10/20에 생긴 fn_auto_work_order_draft가 없을 수 있다)
-- name: sync_has_function
SELECT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = :fn) AS ok;
