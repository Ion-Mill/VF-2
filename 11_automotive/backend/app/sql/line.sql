-- 3D 라인 뷰·현장 보기·2D 배치도 (PRD-01, SCR-04·05·26)

-- name: plant
SELECT layout_id, width_x_mm, depth_y_mm, ceiling_z_mm, origin_desc, axis_desc, equipment_gap_mm, aisle_width_mm,
       work_band_mm, floor_area_m2 FROM plant_layout;

-- name: objects
SELECT object_id, object_kind, object_name, x_min_mm, x_max_mm, y_min_mm, y_max_mm, height_mm, source_tag, buffer_code
  FROM layout_object ORDER BY object_id;

-- name: equipment_layout
SELECT equipment_id, process_code, model, size_x_mm, size_y_mm, size_z_mm, center_x_mm, center_y_mm, facing,
       size_source_tag, ref_model,
       (SELECT coalesce(jsonb_agg(jsonb_build_object('shape_seq', s.shape_seq, 'part_code', s.part_code, 'part_name', s.part_name,
                'shape_kind', s.shape_kind, 'size_x_mm', s.size_x_mm, 'size_y_mm', s.size_y_mm, 'size_z_mm', s.size_z_mm,
                'offset_x_mm', s.offset_x_mm, 'offset_y_mm', s.offset_y_mm, 'offset_z_mm', s.offset_z_mm) ORDER BY s.shape_seq), '[]')
          FROM equipment_part_shape s WHERE s.equipment_id = e.equipment_id) AS parts
  FROM equipment e WHERE e.is_active ORDER BY center_x_mm;

-- name: equipment_now
SELECT * FROM v_equipment_now ORDER BY process_code, equipment_id;

-- name: wip_latest
SELECT DISTINCT ON (w.buffer_code) w.buffer_code, w.logged_at, w.wip_qty, w.soak_shelf_qty, b.limit_qty, b.warn_over_qty,
       b.warn_enabled AND w.wip_qty > b.warn_over_qty AS is_warn, w.wip_qty >= b.limit_qty AS is_full
  FROM wip_log w JOIN wip_buffer b USING (buffer_code)
 WHERE w.logged_at <= app_now()
 ORDER BY w.buffer_code, w.logged_at DESC;

-- name: bottleneck_now
SELECT b.bottleneck_log_id, b.changed_at, b.new_process_code AS process_code, b.cause_code, b.prev_process_code
  FROM bottleneck_log b WHERE b.changed_at <= app_now() ORDER BY b.changed_at DESC LIMIT 1;

-- 지표 카드의 처음 값 = 라인 OEE (OP-30 2대 합, FR-PRD-01-21). 설비를 누르면 /api/kpi?scope=equipment 의 그 설비 값
-- name: line_oee
SELECT * FROM v_shift_line_oee WHERE shift_id = :shift_id;

-- 교대 하나의 목표 대비 실적·예측 (지난 교대는 끝 시각 기준). shift_id를 비우면 지금(또는 가장 최근 시작한) 교대
-- name: shift_progress
SELECT * FROM v_shift_progress
 WHERE shift_id = coalesce(CAST(:shift_id AS text),
                           (SELECT shift_id FROM shift WHERE start_at <= app_now() ORDER BY start_at DESC LIMIT 1));

-- 시간대별 실적 (그래프: 총 목표선·예측 점선은 화면이 shift_progress 값으로 그린다). 지금 시각까지만
-- name: shift_hourly
SELECT h.hour_start, least(h.hour_start + interval '1 hour', s.end_at) AS hour_end,
       coalesce(sum(o.gq + o.rq), 0)::int AS qty,
       (sum(coalesce(sum(o.gq + o.rq), 0)) OVER (ORDER BY h.hour_start))::int AS cum_qty
  FROM shift s
 CROSS JOIN LATERAL generate_series(s.start_at, s.end_at - interval '1 second', interval '1 hour') AS h(hour_start)
  LEFT JOIN operation_report o ON o.shift_id = s.shift_id AND o.process_code = 'OP-50' AND o.end_at > h.hour_start
        AND o.end_at <= h.hour_start + interval '1 hour' AND o.end_at <= app_now()
 WHERE s.shift_id = :shift_id AND h.hour_start <= app_now()
 GROUP BY h.hour_start, s.end_at ORDER BY h.hour_start;

-- name: replay_states
SELECT equipment_id, state_code, start_at, end_at, warn_marker, reason_code
  FROM equipment_state_log
 WHERE start_at < CAST(:to AS timestamptz) AND coalesce(end_at, 'infinity') > CAST(:from AS timestamptz)
 ORDER BY start_at;

-- name: replay_wip
SELECT buffer_code, logged_at, wip_qty, soak_shelf_qty FROM wip_log
 WHERE logged_at BETWEEN CAST(:from AS timestamptz) AND CAST(:to AS timestamptz) ORDER BY logged_at;

-- name: replay_sensors
SELECT equipment_id, sensor_code, sampled_at, interval_type, value FROM sensor_sample
 WHERE equipment_id = :equipment_id AND sampled_at BETWEEN CAST(:from AS timestamptz) AND CAST(:to AS timestamptz)
 ORDER BY sampled_at;

-- name: replay_events
SELECT 'ALARM' AS kind, alarm_event_id AS id, equipment_id, alarm_code AS code, occurred_at AS at FROM alarm_event
 WHERE occurred_at BETWEEN CAST(:from AS timestamptz) AND CAST(:to AS timestamptz)
UNION ALL
SELECT 'BOTTLENECK', bottleneck_log_id, NULL, new_process_code, changed_at FROM bottleneck_log
 WHERE changed_at BETWEEN CAST(:from AS timestamptz) AND CAST(:to AS timestamptz)
ORDER BY at;
