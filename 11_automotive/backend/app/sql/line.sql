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
SELECT DISTINCT ON (w.buffer_code) w.buffer_code, w.logged_at, w.wip_qty, w.soak_shelf_qty, b.limit_qty, b.warn_over_qty, b.warn_enabled,
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
SELECT equipment_id, state_code, start_at, end_at, warn_marker, reason_code, reason_suggested_code, alarm_event_id
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

-- ---------- 화면 전체 트윈 (GET /api/line/twin?full=true, 2026-10-23 화면 → 백엔드 전환 C2) ----------
-- 실시간 구간 시작 = 생성기 데이터 끝 뒤 첫 교대 시작 (영상용 10/24 09:00, 최종용 10/26 09:00, 옛 9월 데이터 10/1 08:00).
-- 그 교대가 아직 없으면 데이터 끝 다음 날의 가장 최근 주간 교대 시작 시각(없으면 08:00), 생성기 데이터가 없으면 지금부터 24시간 전
-- name: live_from
SELECT coalesce((SELECT coalesce((SELECT min(s.start_at) FROM shift s WHERE s.work_date > d.period_to),
                                 ((period_to + 1) + coalesce((SELECT (t.start_at AT TIME ZONE 'Asia/Seoul')::time FROM shift t WHERE t.shift_type = 'DAY'
                                                                ORDER BY t.start_at DESC LIMIT 1), time '08:00')) AT TIME ZONE 'Asia/Seoul')
                   FROM dataset_info d WHERE id = 1 AND period_to IS NOT NULL),
                app_now() - interval '24 hours') AS live_from;

-- 설비별 지금 센서 값 (센서 항목마다 지금 시각까지의 마지막 값)
-- name: sensor_latest
SELECT e.equipment_id, i.sensor_code, x.value, x.sampled_at
  FROM equipment e CROSS JOIN sensor_item i
 CROSS JOIN LATERAL (SELECT s.value, s.sampled_at FROM sensor_sample s
                      WHERE s.equipment_id = e.equipment_id AND s.sensor_code = i.sensor_code AND s.sampled_at <= app_now()
                      ORDER BY s.sampled_at DESC LIMIT 1) x
 WHERE e.has_sensor
 ORDER BY e.equipment_id, i.sensor_code;

-- 교대 시작 ~ 지금 설비별 멈춘 분(DOWN·IDLE·BLOCKED·SETUP)과 고장 손실(고장 그룹 5분 이상 ÷ 기준 사이클, 추정 — 시연 서버 twin과 같은 식)
-- name: shift_equipment_stops
SELECT l.equipment_id,
       round(sum(extract(epoch FROM least(coalesce(l.end_at, 'infinity'), app_now(), s.end_at) - greatest(l.start_at, s.start_at)) / 60)
             FILTER (WHERE l.state_code IN ('DOWN', 'IDLE', 'BLOCKED', 'SETUP'))::numeric, 0)::int AS stop_min,
       round(coalesce(sum(extract(epoch FROM least(coalesce(l.end_at, 'infinity'), app_now(), s.end_at) - greatest(l.start_at, s.start_at)) / 60
                          / nullif(CASE WHEN e.equipment_id = 'WSH-01' THEN e.batch_time_min / nullif(e.batch_qty, 0) ELSE e.std_cycle_min END, 0))
             FILTER (WHERE r.reason_group = 'FAILURE' AND l.state_code IN ('DOWN', 'IDLE')
                       AND least(coalesce(l.end_at, 'infinity'), app_now(), s.end_at) - greatest(l.start_at, s.start_at) >= interval '5 minutes'), 0)::numeric, 1) AS loss_qty,
       -- 순간 정지 = 고장 그룹 사유로 5분 안 된 정지 (화면 손실 줄 "순간 정지 N건 M분", 시연 서버 short_stops와 같음 — 2026-10-24)
       count(*) FILTER (WHERE r.reason_group = 'FAILURE' AND l.state_code <> 'RUN'
                          AND least(coalesce(l.end_at, 'infinity'), app_now(), s.end_at) - greatest(l.start_at, s.start_at) < interval '5 minutes')::int AS short_count,
       coalesce(round(sum(extract(epoch FROM least(coalesce(l.end_at, 'infinity'), app_now(), s.end_at) - greatest(l.start_at, s.start_at)) / 60)
             FILTER (WHERE r.reason_group = 'FAILURE' AND l.state_code <> 'RUN'
                       AND least(coalesce(l.end_at, 'infinity'), app_now(), s.end_at) - greatest(l.start_at, s.start_at) < interval '5 minutes')::numeric, 0), 0)::int AS short_min
  FROM shift s
  JOIN equipment_state_log l ON l.start_at < least(s.end_at, app_now()) AND coalesce(l.end_at, 'infinity') > s.start_at
  JOIN equipment e USING (equipment_id)
  LEFT JOIN downtime_reason r ON r.reason_code = coalesce(l.reason_code, l.reason_suggested_code)
 WHERE s.shift_id = :shift_id
 GROUP BY l.equipment_id;

-- 설비별 지금 상태의 사유(사람이 넣은 것이 없으면 제안 사유)·이름
-- name: equipment_reason_now
SELECT DISTINCT ON (l.equipment_id) l.equipment_id, coalesce(l.reason_code, l.reason_suggested_code) AS reason_code, r.reason_name
  FROM equipment_state_log l LEFT JOIN downtime_reason r ON r.reason_code = coalesce(l.reason_code, l.reason_suggested_code)
 WHERE l.start_at <= app_now()
 ORDER BY l.equipment_id, l.start_at DESC;

-- 오늘(주간 시작부터) OP-50 합격 수 = 완제품으로 나간 수
-- name: done_today
SELECT coalesce(sum(o.gq + o.rq), 0)::int AS done_today
  FROM operation_report o JOIN shift s USING (shift_id)
 WHERE o.process_code = 'OP-50' AND o.end_at <= app_now()
   AND s.work_date = (SELECT work_date FROM shift WHERE start_at <= app_now() ORDER BY start_at DESC LIMIT 1);

-- 마지막 측정값 24개 (CMM 카드)
-- name: last_measure
SELECT lot_no, part_seq, item_seq, position, measured_value, judgement, measured_at
  FROM inspection_result WHERE measured_value IS NOT NULL AND measured_at <= app_now()
 ORDER BY measured_at DESC, result_id DESC LIMIT 24;

-- 실시간 구간 병목 바뀜 (화면 알림 "병목 이동"의 재료 — 시각은 DB 기록 그대로)
-- name: bottleneck_since
SELECT b.bottleneck_log_id, b.changed_at, b.new_process_code AS process_code, b.cause_code, b.prev_process_code
  FROM bottleneck_log b WHERE b.changed_at >= CAST(:since AS timestamptz) AND b.changed_at <= app_now() ORDER BY b.changed_at;

-- 다시 보기: 구간 안 병목 (구간 시작 바로 앞 1줄 포함 — 처음 병목을 알도록)
-- name: replay_bottleneck
(SELECT changed_at, new_process_code AS process_code, cause_code, prev_process_code FROM bottleneck_log
  WHERE changed_at < CAST(:from AS timestamptz) ORDER BY changed_at DESC LIMIT 1)
UNION ALL
(SELECT changed_at, new_process_code, cause_code, prev_process_code FROM bottleneck_log
  WHERE changed_at >= CAST(:from AS timestamptz) AND changed_at < CAST(:to AS timestamptz) ORDER BY changed_at)
ORDER BY changed_at;

-- 다시 보기: 완제품이 나온 시각 (OP-50 실적 줄의 끝 시각 × 합격 수)
-- name: replay_done
SELECT end_at, (gq + rq)::int AS qty FROM operation_report
 WHERE process_code = 'OP-50' AND end_at >= CAST(:from AS timestamptz) AND end_at < CAST(:to AS timestamptz) AND gq + rq > 0
 ORDER BY end_at;
