-- 생산: 작업지시·로트·로트 추적·보류 (PRD-03·05, QLT-01 판정)

-- 작업지시 진행 표 (LINE-05, PRD-03): 목표(지시 수량)·완료·불량·로트·지금 공정·납기·지연 여부·상태.
-- shift_id를 주면 그 교대에 로트를 넣었거나 진행 중인 작업지시만
-- name: orders
SELECT o.order_no, o.product_code, o.order_qty, o.created_at, o.due_at, o.status, o.started_at, o.completed_at,
       coalesce(sum(l.completed_qty), 0)::int AS completed_qty, count(l.lot_no)::int AS lot_count,
       string_agg(l.lot_no, ',' ORDER BY l.lot_seq) AS lot_nos,
       (SELECT coalesce(sum(r.sq), 0) FROM operation_report r JOIN production_lot x USING (lot_no)
         WHERE x.order_no = o.order_no)::int AS defect_qty,
       (SELECT r.process_code FROM operation_report r JOIN production_lot x USING (lot_no) JOIN process p USING (process_code)
         WHERE x.order_no = o.order_no ORDER BY p.seq DESC LIMIT 1) AS current_process_code,
       (o.status <> 'CANCELLED' AND coalesce(o.completed_at, app_now()) > o.due_at) AS is_late
  FROM production_order o LEFT JOIN v_production_lot l USING (order_no)
 WHERE (CAST(:status AS text) IS NULL OR o.status = CAST(:status AS text))
   AND (CAST(:shift_id AS text) IS NULL OR o.status = 'IN_PROGRESS'
        OR EXISTS (SELECT 1 FROM production_lot x WHERE x.order_no = o.order_no AND x.input_shift_id = CAST(:shift_id AS text)))
   AND o.created_at >= coalesce(CAST(:from AS timestamptz), '-infinity') AND o.created_at < coalesce(CAST(:to AS timestamptz), 'infinity')
 GROUP BY o.order_no ORDER BY o.created_at DESC LIMIT CAST(:limit AS int);

-- name: lots
SELECT * FROM v_production_lot
 WHERE (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
   AND (CAST(:order_no AS text) IS NULL OR order_no = CAST(:order_no AS text))
 ORDER BY order_no DESC, lot_seq LIMIT CAST(:limit AS int);

-- name: lot
SELECT * FROM v_production_lot WHERE lot_no = :lot_no;

-- name: lot_trace
SELECT lot_no, status, trace FROM v_lot_trace WHERE lot_no = :lot_no;

-- name: lot_hold
SELECT fn_lot_hold(:lot_no, :actor, :trigger_type, :reason, coalesce(CAST(:next_lots AS int), 2), CAST(:alarm_event_id AS bigint),
                   CAST(:tool_id AS text)) AS hold_id;

-- name: lot_release
-- 합격 수량을 비우면 = 로트 완료 수량 (OP-50 양품 + 재작업 — 폐기한 부품은 이미 빠짐)
SELECT fn_lot_release(CAST(:hold_id AS bigint), :actor,
       coalesce(CAST(:pass_qty AS int),
                (SELECT fn_lot_completed_qty(h.lot_no) FROM lot_hold h
                  WHERE h.hold_id = CAST(:hold_id AS bigint))));

-- name: scrap_propose
SELECT fn_lot_scrap_propose(:hold_id, :actor, CAST(:qty AS int));

-- name: scrap_approve
SELECT fn_lot_scrap_approve(:hold_id, :actor);

-- name: lot_judge
SELECT fn_lot_judge(:lot_no) AS result;

-- name: holds
SELECT h.*, l.status AS lot_status FROM lot_hold h JOIN production_lot l USING (lot_no)
 WHERE (CAST(:open_only AS boolean) IS NOT TRUE OR h.result = 'IN_PROGRESS') ORDER BY h.held_at DESC;

-- 지표 (LINE-04) 설비별: 교대 × 설비. 기간을 비우면 오늘(시연 시계). 주의 = OP-30만 가동률 60% 미만·OEE 59% 미만 (DOC-07 10.1)
-- name: kpi_equipment
SELECT k.*, (k.process_code = 'OP-30' AND k.availability_pct < 60) AS is_availability_warn,
       (k.process_code = 'OP-30' AND k.oee_pct < 59) AS is_oee_warn
  FROM v_shift_equipment_kpi k
 WHERE (CAST(:shift_id AS text) IS NULL OR k.shift_id = CAST(:shift_id AS text))
   AND (CAST(:shift_id AS text) IS NOT NULL OR k.work_date BETWEEN coalesce(CAST(:from AS date), CAST(:to AS date), CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date))
                                                AND coalesce(CAST(:to AS date), CAST(:from AS date), CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date)))
   AND (CAST(:equipment_id AS text) IS NULL OR k.equipment_id = CAST(:equipment_id AS text))
 ORDER BY k.work_date, k.shift_type, k.process_code, k.equipment_id;

-- 지표 (LINE-04) 라인: 라인 OEE (OP-30 2대 합, R-44). 주의 = 59% 미만
-- name: kpi_line
SELECT k.*, k.oee_pct < 59 AS is_oee_warn FROM v_shift_line_oee k
 WHERE (CAST(:shift_id AS text) IS NULL OR k.shift_id = CAST(:shift_id AS text))
   AND (CAST(:shift_id AS text) IS NOT NULL OR k.work_date BETWEEN coalesce(CAST(:from AS date), CAST(:to AS date), CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date))
                                                AND coalesce(CAST(:to AS date), CAST(:from AS date), CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date)))
 ORDER BY k.work_date, k.shift_type;

-- 로트의 열린 보류 (LOT-02·03은 로트 번호로 부른다)
-- name: open_hold
SELECT hold_id FROM lot_hold WHERE lot_no = :lot_no AND result = 'IN_PROGRESS';

-- name: stop_ranking
SELECT s.reason_code, r.reason_name, r.reason_group, count(*)::int AS times, round(sum(s.duration_min), 1) AS minutes,
       round(sum(s.stop_loss_qty), 1) AS loss_qty
  FROM equipment_state_log s JOIN downtime_reason r USING (reason_code)
 WHERE s.start_at >= CAST(:from AS timestamptz) AND s.start_at < CAST(:to AS timestamptz) AND r.is_loss
 GROUP BY s.reason_code, r.reason_name, r.reason_group ORDER BY minutes DESC NULLS LAST;
