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

-- 의심 로트 제안 (2026-10-20 요구사항 대조 상 5번 — FR-PRD-05-05, API-LOT-01, UI SCR-09 [7]·SCR-19 [3], DOC-06 4.2).
--   ① 정지 등급 알람 때 그 설비에서 가공 중이던 로트 (연쇄 알람이면 첫 알람부터 — 예: 108 → 994 → 992), 알람에 적힌 로트
--   ② 공구 수명(한도)을 넘긴 공구로 가공한 로트
--   제안만 한다 — 알림을 만들지 않고 상태도 바꾸지 않는다 (보류는 반장). 거르기: :alarm_event_id(지침카드), :lot_no(로트 추적),
--   둘 다 비면 :since 뒤 (비우면 7일). 비서는 이 재료로 문장만 쓴다
-- name: suspect_lots
WITH RECURSIVE chain AS (
    SELECT a.alarm_event_id AS root_id, a.alarm_event_id, a.prev_alarm_event_id, a.occurred_at, 0 AS depth
      FROM alarm_event a
     WHERE a.severity_at_event = 'STOP'
       AND (CAST(:alarm_event_id AS bigint) IS NULL OR a.alarm_event_id = CAST(:alarm_event_id AS bigint))
       AND (CAST(:alarm_event_id AS bigint) IS NOT NULL OR CAST(:lot_no AS text) IS NOT NULL
            OR a.occurred_at >= coalesce(CAST(:since AS timestamptz), app_now() - interval '7 days'))
    UNION ALL
    SELECT c.root_id, p.alarm_event_id, p.prev_alarm_event_id, p.occurred_at, c.depth + 1
      FROM chain c JOIN alarm_event p ON p.alarm_event_id = c.prev_alarm_event_id
     WHERE c.depth < 5
), alarm_win AS (
    SELECT a.alarm_event_id, a.alarm_code, a.equipment_id, a.occurred_at, a.lot_no, min(c.occurred_at) AS from_at
      FROM chain c JOIN alarm_event a ON a.alarm_event_id = c.root_id
     GROUP BY a.alarm_event_id, a.alarm_code, a.equipment_id, a.occurred_at, a.lot_no
), cand AS (
    SELECT DISTINCT r.lot_no, 'ALARM' AS kind, w.alarm_event_id, NULL::text AS tool_id, w.occurred_at AS at, 1 AS prio,
           format('정지 등급 알람 %s(%s %s) 때 이 설비에서 가공 중', w.alarm_code, w.equipment_id,
                  to_char(w.occurred_at AT TIME ZONE 'Asia/Seoul', 'MM/DD HH24:MI')) AS reason
      FROM alarm_win w JOIN operation_report r ON r.equipment_id = w.equipment_id
       AND r.start_at <= w.occurred_at AND coalesce(r.end_at, 'infinity'::timestamptz) >= w.from_at
    UNION
    SELECT w.lot_no, 'ALARM', w.alarm_event_id, NULL, w.occurred_at, 2,
           format('정지 등급 알람 %s(%s %s)에 적힌 로트', w.alarm_code, w.equipment_id,
                  to_char(w.occurred_at AT TIME ZONE 'Asia/Seoul', 'MM/DD HH24:MI'))
      FROM alarm_win w WHERE w.lot_no IS NOT NULL
    UNION
    SELECT r.lot_no, 'TOOL', NULL, u.tool_id, u.recorded_at, 1,
           format('공구 %s 수명 %s%% (한도 %s) 넘어 가공', u.tool_id, round(100 * u.cum_after / tt.life_limit), tt.life_limit::float8)
      FROM tool_usage u JOIN tool t USING (tool_id) JOIN tool_type tt ON tt.item_no = t.item_no
      JOIN operation_report r ON r.op_report_id = u.op_report_id
     WHERE u.cum_after > tt.life_limit AND CAST(:alarm_event_id AS bigint) IS NULL
       AND (CAST(:lot_no AS text) IS NOT NULL OR u.recorded_at >= coalesce(CAST(:since AS timestamptz), app_now() - interval '7 days'))
)
SELECT x.* FROM (
    -- 로트·알람(또는 공구)마다 한 줄: 가공 중이던 것이면 그 이유, 아니면 "알람에 적힌 로트"
    SELECT DISTINCT ON (c.lot_no, c.kind, c.alarm_event_id, c.tool_id)
           c.lot_no, c.kind, c.reason, c.alarm_event_id, c.tool_id, c.at, l.status AS lot_status,
           l.status IN ('ON_HOLD','HOLD_REVIEW') AS is_held
      FROM cand c JOIN production_lot l USING (lot_no)
     WHERE CAST(:lot_no AS text) IS NULL OR c.lot_no = CAST(:lot_no AS text)
     ORDER BY c.lot_no, c.kind, c.alarm_event_id, c.tool_id, c.prio
) x
 ORDER BY x.at DESC, x.lot_no;

-- 강화 → 보통 검사 복귀 (R-29, FR-QLT-01-07 — 2026-10-20): 원인 조치 기록 + 강화한 로트 모두 합격일 때만 (DB가 확인), 반장
-- name: resume_normal
SELECT fn_resume_normal(:hold_id, :actor) AS hold_id;

-- name: hold
SELECT h.*, l.status AS lot_status FROM lot_hold h JOIN production_lot l USING (lot_no) WHERE h.hold_id = :hold_id;
