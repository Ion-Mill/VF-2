-- AI 비서 조회 도구 14개 (FR-MNT-01-04, FR-AST-COM-14: 정해진 조회 도구만, SQL 직접 실행 없음)
-- 3D 라인 뷰에서 뺀 MTTR·MTBF·센서 추세·설비 사양·정지 원인 순위는 비서 질문으로 본다 (2026-10-07 팀 UI 검토)
-- 읽기 전용 계정(ai_ro)으로 돌린다. 숫자는 여기서 계산하고 비서는 문장만 쓴다 (FR-AST-COM-05)

-- name: equipment_status
SELECT equipment_id, process_code, state_code, state_since, state_minutes, warn_marker, open_alarm_code, open_alarm_severity,
       lock_record_no IS NOT NULL AS is_locked, current_lot_no
  FROM v_equipment_now WHERE CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text);

-- name: alarms
SELECT a.equipment_id, a.alarm_code, m.name_ko, a.severity_at_event, count(*)::int AS times, min(a.occurred_at) AS first_at,
       max(a.occurred_at) AS last_at,
       round(sum(extract(epoch FROM (coalesce(s.end_at, app_now()) - s.start_at)) / 60) FILTER (WHERE s.state_code = 'DOWN'), 1) AS down_min
  FROM alarm_event a JOIN alarm_master m USING (alarm_code)
  LEFT JOIN equipment_state_log s ON s.alarm_event_id = a.alarm_event_id
 WHERE a.occurred_at >= CAST(:from AS timestamptz) AND a.occurred_at < CAST(:to AS timestamptz)
   AND (CAST(:equipment_id AS text) IS NULL OR a.equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:alarm_code AS text) IS NULL OR a.alarm_code = CAST(:alarm_code AS text))
 GROUP BY a.equipment_id, a.alarm_code, m.name_ko, a.severity_at_event ORDER BY times DESC;

-- name: kpi
SELECT shift_id, equipment_id, availability_pct, performance_pct, quality_pct, oee_pct, run_min, down_min, maint_min, pbt_min, pq, gq, rq, sq
  FROM v_shift_equipment_kpi
 WHERE work_date BETWEEN CAST(:from_date AS date) AND CAST(:to_date AS date)
   AND (CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:shift_type AS text) IS NULL OR shift_type = CAST(:shift_type AS text))
 ORDER BY shift_id, equipment_id;

-- 교대별 총 목표(목표 + 이월, R-88)·실적·예측·손실. 하루 목표는 180 고정 — 하루 부족 = 180 − 두 교대 실적 합
-- name: production
SELECT p.shift_id, p.shift_type, p.target_qty, p.carry_over_qty, p.total_target_qty, p.carry_over_is_provisional,
       p.actual_qty, p.defect_qty, p.forecast_qty, p.shortfall_qty, p.is_target_risk, p.is_report_confirmed,
       p.failure_loss_qty, p.speed_loss_qty, p.loss_qty, d.daily_target_qty,
       (SELECT string_agg(DISTINCT l.order_no, ',') FROM production_lot l WHERE l.input_shift_id = p.shift_id) AS order_nos
  FROM v_shift_progress p JOIN work_day d USING (work_date)
 WHERE p.work_date BETWEEN CAST(:from_date AS date) AND CAST(:to_date AS date) ORDER BY p.start_at;

-- name: lot
SELECT l.lot_no, l.status, l.input_qty, l.completed_qty, l.plan_mode, l.passed_at, l.shipped_qty, l.shipment_nos, t.trace
  FROM v_production_lot l JOIN v_lot_trace t USING (lot_no) WHERE l.lot_no = :lot_no;

-- name: work_orders
SELECT wo_no, equipment_id, trigger_kind, title, status, assignee_user_id, created_at, approval_wait_min
  FROM v_work_order
 WHERE (CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:open_only AS boolean) IS NOT TRUE OR status NOT IN ('DONE','CANCELLED'))
 ORDER BY created_at DESC LIMIT 20;

-- name: work_records
SELECT w.record_no, w.record_type, w.equipment_id, a.alarm_code, w.cause, w.action, w.repair_min, w.confirmed_at
  FROM work_record w LEFT JOIN alarm_event a ON a.alarm_event_id = w.alarm_event_id
 WHERE w.status IN ('CONFIRMED','CHECKED')
   AND (CAST(:equipment_id AS text) IS NULL OR w.equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:alarm_code AS text) IS NULL OR a.alarm_code = CAST(:alarm_code AS text))
 ORDER BY w.confirmed_at DESC LIMIT 20;

-- name: pm_due
SELECT pm_task_id, equipment_id, item_name, cycle_code, last_done_at, next_due_date,
       (CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) - next_due_date) AS days_overdue
  FROM v_pm_task_due
 WHERE is_active AND next_due_date IS NOT NULL
   AND next_due_date <= CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) + CAST(:within_days AS int)
   AND (CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text))
 ORDER BY next_due_date;

-- name: tool_life
SELECT tool_id, equipment_id, tool_no, item_name, usage_unit, cum_usage, life_limit, usage_rate_pct, remaining_pct, parts_left
  FROM v_tool_life WHERE CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text)
 ORDER BY usage_rate_pct DESC;

-- name: inventory
SELECT item_no, item_name, category, unit, on_hand_qty, safety_stock, is_low,
       (SELECT coalesce(sum(-t.qty_change), 0) FROM inventory_txn t
         WHERE t.item_no = v.item_no AND t.txn_type = 'SHIP_OUT' AND t.txn_at >= app_now() - interval '7 days') AS shipped_7d
  FROM v_inventory_status v WHERE CAST(:item_no AS text) IS NULL OR item_no = CAST(:item_no AS text) ORDER BY item_no;

-- MTTR·MTBF 최근 30일 (R-45a, DOC-07 6.2). 고장 0건이면 NULL("—"). MTTR 120분 초과 = 주의 (DOC-07 10.1)
-- name: reliability
SELECT equipment_id, process_code, failure_count, down_min, mttr_min, mtbf_hours, is_mttr_warn
  FROM v_equipment_reliability_30d
 WHERE CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text)
 ORDER BY equipment_id;

-- 정지 원인 순위 (손실 정지만, 계획 정지 제외 — 교대 보고서 필수 정지 칸과 같은 기준) — 3D에서 뺀 정지 원인 순위
-- name: stop_reasons
SELECT s.equipment_id, s.reason_code, r.reason_name, r.reason_group, count(*)::int AS times,
       round(sum(extract(epoch FROM (coalesce(s.end_at, app_now()) - s.start_at)) / 60), 1) AS minutes,
       round(sum(s.stop_loss_qty), 1) AS loss_qty
  FROM equipment_state_log s JOIN downtime_reason r ON r.reason_code = coalesce(s.reason_code, s.reason_suggested_code)
 WHERE s.start_at >= CAST(:from AS timestamptz) AND s.start_at < CAST(:to AS timestamptz) AND r.is_loss
   AND (CAST(:equipment_id AS text) IS NULL OR s.equipment_id = CAST(:equipment_id AS text))
 GROUP BY s.equipment_id, s.reason_code, r.reason_name, r.reason_group ORDER BY minutes DESC NULLS LAST;

-- OP-30 센서 추세 (FR-PRD-01-14): 최근 N분(기본 60) 최소·평균·최대 + 정상 범위 [참고]. 알람 기준값은 없다 (DOC-07 3장)
-- name: sensor_trend
SELECT s.equipment_id, s.sensor_code, i.sensor_name, i.unit, count(*)::int AS samples,
       round(min(s.value)::numeric, 2) AS min_value, round(avg(s.value)::numeric, 2) AS avg_value,
       round(max(s.value)::numeric, 2) AS max_value,
       (array_agg(s.value ORDER BY s.sampled_at DESC))[1] AS last_value, max(s.sampled_at) AS last_at,
       i.normal_min, i.normal_max, 'REFERENCE' AS normal_range_tag,
       min(s.value) < i.normal_min OR max(s.value) > i.normal_max AS is_out_of_normal
  FROM sensor_sample s JOIN sensor_item i USING (sensor_code)
 WHERE s.equipment_id = :equipment_id
   AND s.sampled_at > app_now() - make_interval(mins => coalesce(CAST(:minutes AS int), 60)) AND s.sampled_at <= app_now()
   AND (CAST(:sensor_code AS text) IS NULL OR s.sensor_code = CAST(:sensor_code AS text))
 GROUP BY s.equipment_id, s.sensor_code, i.sensor_name, i.unit, i.normal_min, i.normal_max
 ORDER BY s.sensor_code;

-- 설비 사양 (3D 하단 패널에서 뺀 크기 꼬리표 — 2026-10-07 팀 UI 검토). 크기 근거 REAL/REFERENCE/VIRTUAL
-- name: equipment_spec
SELECT e.equipment_id, e.process_code, p.process_name, e.model, e.controller, e.std_cycle_min, e.batch_qty, e.batch_time_min,
       e.size_x_mm, e.size_y_mm, e.size_z_mm, e.size_source_tag, e.ref_model, e.has_sensor
  FROM equipment e JOIN process p USING (process_code)
 WHERE e.is_active AND (CAST(:equipment_id AS text) IS NULL OR e.equipment_id = CAST(:equipment_id AS text))
 ORDER BY p.seq, e.equipment_id;

-- ---------------------------------------------------------------------
-- AI 비서 채팅 기록 (chat_log, 5.G.7 — 2026-10-13). 본인 것만, 30일 안
-- ---------------------------------------------------------------------
-- name: chat_insert
INSERT INTO chat_log (user_id, asked_at, screen_context, question, answer, sources, status, prev_chat_id)
VALUES (:user_id, app_now(), CAST(:screen_context AS jsonb), :question, CAST(:answer AS text), CAST(:sources AS jsonb),
        :status, CAST(:prev_chat_id AS bigint))
RETURNING chat_id;

-- name: chat_list
SELECT chat_id, asked_at, screen_context, question, answer, sources, status, prev_chat_id
  FROM chat_log
 WHERE user_id = :user_id AND asked_at >= app_now() - interval '30 days'
   AND (CAST(:since AS timestamptz) IS NULL OR asked_at > CAST(:since AS timestamptz))
 ORDER BY asked_at DESC, chat_id DESC LIMIT CAST(:limit AS int);

-- name: chat_get
SELECT chat_id, asked_at, screen_context, question, answer, sources, status, prev_chat_id
  FROM chat_log WHERE chat_id = :chat_id AND user_id = :user_id AND asked_at >= app_now() - interval '30 days';

-- 이어서 물을 때 앞 질문·답 (가장 최근부터 :turns개, 본인 것만)
-- name: chat_thread
WITH RECURSIVE t AS (
    SELECT c.*, 1 AS depth FROM chat_log c WHERE c.chat_id = :chat_id AND c.user_id = :user_id
    UNION ALL
    SELECT c.*, t.depth + 1 FROM chat_log c JOIN t ON c.chat_id = t.prev_chat_id
     WHERE c.user_id = :user_id AND t.depth < CAST(:turns AS int)
)
SELECT chat_id, asked_at, question, answer, status FROM t ORDER BY depth;

-- 비서 서비스가 시작할 때 한 번 읽는 사내 문서 (2026-10-25, 비서 DOCS_SOURCE=db). 현행 개정의 조각만, 읽기 전용 계정으로
-- 문서 목록: 번호·이름·현행 개정·개정일 (비서의 조각 메타데이터 "Rev.N (날짜)"를 만드는 재료)
-- name: doc_corpus_docs
SELECT doc_no, doc_name, current_rev, rev_date FROM internal_doc ORDER BY doc_no;

-- name: doc_corpus_chunks
SELECT c.doc_no, c.doc_rev, c.section, c.chunk_text, c.chunk_id
  FROM doc_chunk c JOIN internal_doc d ON d.doc_no = c.doc_no AND c.doc_rev = d.current_rev
 ORDER BY c.doc_no, c.chunk_id;
