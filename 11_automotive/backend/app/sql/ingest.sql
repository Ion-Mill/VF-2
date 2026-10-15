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
