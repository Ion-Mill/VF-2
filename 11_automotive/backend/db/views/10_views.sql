-- =====================================================================
-- 10_views.sql — 계산 속성과 화면·비서 조회용 뷰
-- 논리 ERD에서 "계산" 표시가 붙은 속성 중 저장하지 않기로 한 것은 모두 여기서 계산한다
-- (docs/02_물리ERD.md 6장). 시간에 따라 바뀌는 값은 app_now()(시연 시계)를 쓴다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 생산 로트 + 완료 수량(R-05) + 측정할 부품 수(R-09) + 완제품·출하 수량(R-69)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_production_lot AS
SELECT l.lot_no, l.order_no, l.lot_seq, l.input_shift_id, l.material_lot_no, l.input_qty, l.status, l.scrap_qty,
       l.judged_at, o.product_code, o.due_at,
       coalesce(c.completed_qty, 0)                                    AS completed_qty,
       c.op50_done_at,
       fn_lot_expected_complete(l.lot_no)                              AS expected_complete_at,  -- [제안 2026-10-20] functions/35_live_calc.sql
       p.plan_mode, p.enhance_reason, p.judgement AS plan_judgement,
       CASE WHEN p.plan_mode = 'ENHANCED' THEN l.input_qty ELSE 1 + l.input_qty / 5 END AS planned_measure_qty,
       fg.fg_in_qty, fg.passed_at,
       coalesce(sh.shipped_qty, 0)                                     AS shipped_qty,
       coalesce(fg.fg_in_qty, 0) - coalesce(sh.shipped_qty, 0)        AS fg_remaining_qty,
       sh.shipment_nos
  FROM production_lot l
  JOIN production_order o USING (order_no)
  LEFT JOIN inspection_plan p USING (lot_no)
  LEFT JOIN LATERAL (SELECT sum(r.gq + r.rq)::int AS completed_qty, max(r.end_at) AS op50_done_at
                       FROM operation_report r WHERE r.lot_no = l.lot_no AND r.process_code = 'OP-50') c ON true
  LEFT JOIN LATERAL (SELECT sum(t.qty_change)::int AS fg_in_qty, min(t.txn_at) AS passed_at
                       FROM inventory_txn t WHERE t.source_kind = 'LOT_PASS' AND t.fg_lot_no = l.lot_no) fg ON true
  LEFT JOIN LATERAL (SELECT sum(sl.qty)::int AS shipped_qty, string_agg(sl.shipment_no, ',' ORDER BY sl.shipment_no) AS shipment_nos
                       FROM shipment_line sl JOIN shipment s USING (shipment_no)
                      WHERE sl.lot_no = l.lot_no AND s.status <> 'DRAFT') sh ON true;

-- ---------------------------------------------------------------------
-- 병목 구간 (5.B.6): 다음 기록까지가 한 구간. 계획 생산 수 = 구간 ÷ 라인 기준 사이클(3.5분)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_bottleneck_interval AS
SELECT b.*,
       lead(b.changed_at) OVER w                                        AS interval_end_at,
       round((extract(epoch FROM (coalesce(lead(b.changed_at) OVER w, app_now()) - b.changed_at)) / 60
              / (SELECT min(line_base_cycle_min) FROM product WHERE is_active))::numeric, 2) AS planned_qty
  FROM bottleneck_log b
WINDOW w AS (ORDER BY b.changed_at);

-- ---------------------------------------------------------------------
-- 작업지시서 + 계기(여러 값, 6.42) + 승인 대기 분
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_work_order AS
SELECT m.*,
       array_remove(ARRAY[
           CASE WHEN m.alarm_event_id IS NOT NULL THEN 'STOP_ALARM' END,
           CASE WHEN m.trigger_notification_id IS NOT NULL THEN 'REPEAT_STAGE2' END,
           CASE WHEN m.pm_record_id IS NOT NULL THEN 'PM_ABNORMAL' END], NULL)::varchar[] AS trigger_kind,
       CASE WHEN m.status IN ('AI_DRAFT','EDITING')
            THEN round(extract(epoch FROM (app_now() - m.created_at)) / 60) END        AS approval_wait_min,
       -- 13.1 MGR "승인(대리)": 승인자가 MGR이면 반장 대신 승인한 것 (저장 칸 없이 승인자 역할로 계산)
       (SELECT u.role_code = 'MGR' FROM app_user u WHERE u.user_id = m.approved_by)    AS approved_as_proxy
  FROM maintenance_work_order m;

-- ---------------------------------------------------------------------
-- 예방 정비 다음 기한 (R-43): 마지막 실시일 + 주기. 필요할 때·8시간 사용마다는 날짜 기한 없음
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_pm_task_due AS
SELECT t.*, last.done_at AS last_done_at,
       (last.done_at AT TIME ZONE 'Asia/Seoul')::date + CASE t.cycle_code
            WHEN 'DAILY' THEN interval '1 day' WHEN 'WEEKLY' THEN interval '7 days'
            WHEN 'MONTHLY' THEN interval '1 month' WHEN 'HALF_YEAR' THEN interval '6 months'
            WHEN 'YEARLY' THEN interval '1 year' END                    AS next_due_ts,
       ((last.done_at AT TIME ZONE 'Asia/Seoul')::date + CASE t.cycle_code
            WHEN 'DAILY' THEN interval '1 day' WHEN 'WEEKLY' THEN interval '7 days'
            WHEN 'MONTHLY' THEN interval '1 month' WHEN 'HALF_YEAR' THEN interval '6 months'
            WHEN 'YEARLY' THEN interval '1 year' END)::date              AS next_due_date
  FROM pm_task t
  LEFT JOIN LATERAL (SELECT max(r.done_at) AS done_at FROM pm_record r WHERE r.pm_task_id = t.pm_task_id) last ON true;

-- ---------------------------------------------------------------------
-- 공구 수명 (R-40): 사용률 = 누적 ÷ 한도 × 100, 남은 수명 = 100 − 사용률
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tool_life AS
SELECT tl.tool_id, tl.equipment_id, tl.tool_no, tl.item_no, i.item_name, tl.tool_role, tl.cum_usage,
       tt.usage_unit, tt.usage_per_part, tt.life_limit, tl.last_changed_at,
       round(100 * tl.cum_usage / tt.life_limit, 1)                       AS usage_rate_pct,
       round(100 - 100 * tl.cum_usage / tt.life_limit, 1)                 AS remaining_pct,
       floor(greatest(tt.life_limit - tl.cum_usage, 0) / tt.usage_per_part)::int AS parts_left
  FROM tool tl JOIN tool_type tt USING (item_no) JOIN inventory_item i USING (item_no)
 WHERE tl.is_active;

-- ---------------------------------------------------------------------
-- 출하 + 합계 수량·근거 작업지시 (5.E.7 계산)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shipment AS
SELECT s.*, coalesce(x.total_qty, 0) AS total_qty, x.line_count, x.basis_order_nos
  FROM shipment s
  LEFT JOIN LATERAL (
      SELECT sum(sl.qty)::int AS total_qty, count(*)::int AS line_count,
             string_agg(DISTINCT l.order_no, ',') AS basis_order_nos
        FROM shipment_line sl JOIN production_lot l USING (lot_no)
       WHERE sl.shipment_no = s.shipment_no) x ON true;

-- ---------------------------------------------------------------------
-- 검사 결과 + 기준 + 가공 설비 ([제안] 05 결정기록 P-11 — 논리 ERD에는 규칙 번호가 없다. R-88은 이월·총 목표)
--   가공 설비 = 그 로트의 OP-30 공정 실적 설비가 1대뿐이면 그 설비, 2대에 나뉘면 NULL("설비 미상")
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_inspection_result AS
SELECT r.*, i.item_name, i.spec_text, i.nominal, i.lsl, i.usl, i.char_class, i.method,
       (SELECT CASE WHEN count(DISTINCT o.equipment_id) = 1 THEN min(o.equipment_id) END
          FROM operation_report o WHERE o.lot_no = r.lot_no AND o.process_code = 'OP-30') AS machined_equipment_id
  FROM inspection_result r
  JOIN inspection_item i USING (product_code, item_seq);

-- ---------------------------------------------------------------------
-- 재고 현황 (FR-INV-01, R-39)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_inventory_status AS
SELECT i.*,
       i.safety_stock IS NOT NULL AND i.on_hand_qty <= i.safety_stock AS is_low,
       CASE WHEN i.safety_stock > 0 THEN round(i.on_hand_qty / i.safety_stock, 2) END AS stock_ratio
  FROM inventory_item i
 WHERE i.is_active;

-- ---------------------------------------------------------------------
-- 잠금·표지 중인 설비 (R-53): 6.4 체크 뒤 7.3 체크 전
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_lock_status AS
SELECT w.equipment_id, w.record_no, c64.checked_at AS locked_since, c64.checked_by AS locked_by
  FROM work_record w
  JOIN work_record_check c64 ON c64.record_no = w.record_no AND c64.loto_step_code = '6.4' AND c64.is_checked
 WHERE NOT EXISTS (SELECT 1 FROM work_record_check c73
                    WHERE c73.record_no = w.record_no AND c73.loto_step_code = '7.3' AND c73.is_checked);

-- ---------------------------------------------------------------------
-- 설비 지금 상태 (3D·현장 보기·하단 패널)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_equipment_now AS
SELECT e.equipment_id, e.process_code, e.model,
       st.state_code, st.start_at AS state_since, st.warn_marker, st.reason_code, st.reason_status,
       round(extract(epoch FROM (app_now() - st.start_at)) / 60, 1) AS state_minutes,
       al.alarm_event_id AS open_alarm_event_id, al.alarm_code AS open_alarm_code, al.severity_at_event AS open_alarm_severity,
       lk.record_no AS lock_record_no, lk.locked_since,
       cur.lot_no AS current_lot_no,
       st.alarm_event_id AS state_alarm_event_id          -- DOWN 구간을 만든 정지 등급 알람 (R-22)
  FROM equipment e
  LEFT JOIN LATERAL (SELECT * FROM equipment_state_log s WHERE s.equipment_id = e.equipment_id
                      ORDER BY s.start_at DESC LIMIT 1) st ON true
  LEFT JOIN LATERAL (SELECT a.* FROM alarm_event a WHERE a.equipment_id = e.equipment_id AND a.cleared_at IS NULL
                      ORDER BY a.occurred_at DESC LIMIT 1) al ON true
  LEFT JOIN LATERAL (SELECT * FROM v_lock_status v WHERE v.equipment_id = e.equipment_id
                      ORDER BY v.locked_since LIMIT 1) lk ON true
  LEFT JOIN LATERAL (SELECT o.lot_no FROM operation_report o WHERE o.equipment_id = e.equipment_id
                      ORDER BY o.start_at DESC LIMIT 1) cur ON true
 WHERE e.is_active;

-- ---------------------------------------------------------------------
-- 보고 순위 (6.43, R-73 "전부 보고·정해진 순서") — 브리핑·교대 보고서 인계·일일 보고서 "오늘의 문제"
-- 개수를 자르지 않는다. 정렬: rank_order → rank_group → sort_value(큰 순) → occurred_at(이른 순)
-- v_report_items = 모은 항목 하나하나, v_report_lines = 같은 설비·같은 원인을 한 줄로 묶은 화면 줄 (아래)
-- group_key: 같은 설비·같은 원인 = 같은 설비 + 같은 알람 번호 (알람·반복 알람 1·2단계·원인 점검 요청·DOWN 설비),
--   여기에 관련 예방 정비(기본 소모품)·재고 부족을 알람 ↔ 재고 품목 연결(alarm_related_item)로 붙인다 (R-89)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_report_items AS
WITH now_ AS (SELECT app_now() AS t),
open_n AS (
    SELECT n.*, r.report_rank, r.rank_group, r.rule_name,
           a.alarm_code, coalesce(n.equipment_id, a.equipment_id) AS alarm_equipment,
           pt.equipment_id AS pm_equipment, pt.default_item_no AS pm_item,
           CASE WHEN n.rule_code = 'STOCK_LOW' THEN n.item_no END AS stock_item
      FROM notification n JOIN notification_rule r USING (rule_code)
      LEFT JOIN alarm_event a ON a.alarm_event_id = n.alarm_event_id
      LEFT JOIN pm_task pt ON pt.pm_task_id = n.pm_task_id
     WHERE NOT n.is_processed
), base AS (
-- 0 안전: 잠금·표지 중인 설비
SELECT 'R0'::text AS report_rank, 0 AS rank_order, 0 AS rank_group, 'LOCK'::text AS item_kind,
       NULL::bigint AS notification_id, NULL::text AS rule_code, v.equipment_id, NULL::text AS lot_no,
       '잠금·표지 중: ' || v.equipment_id AS title, v.locked_since AS occurred_at, NULL::numeric AS sort_value,
       NULL::text AS alarm_equipment, NULL::text AS alarm_code, NULL::text AS pm_equipment, NULL::text AS pm_item,
       NULL::text AS stock_item
  FROM v_lock_status v
UNION ALL
-- 0-1 오래 방치: 24시간 넘게 처리 안 된 주의 알림 (건수는 "주의"에 센다)
SELECT 'R0_1', 1, 0, 'NOTIFICATION', n.notification_id, n.rule_code, n.equipment_id, n.lot_no,
       n.message, n.raised_at, extract(epoch FROM (now_.t - n.raised_at)) / 3600,
       n.alarm_equipment, n.alarm_code, n.pm_equipment, n.pm_item, n.stock_item
  FROM open_n n, now_
 WHERE n.importance = 'CAUTION' AND n.raised_at < now_.t - interval '24 hours'
UNION ALL
-- 1·2·3·4 순위의 알림 (0-1로 올라간 것은 빼고)
SELECT n.report_rank, CASE n.report_rank WHEN 'R1' THEN 2 WHEN 'R2' THEN 3 WHEN 'R3' THEN 4 ELSE 5 END,
       n.rank_group, 'NOTIFICATION', n.notification_id, n.rule_code, n.equipment_id, n.lot_no,
       n.message, n.raised_at, n.repeat_count::numeric,
       n.alarm_equipment, n.alarm_code, n.pm_equipment, n.pm_item, n.stock_item
  FROM open_n n, now_
 WHERE NOT (n.importance = 'CAUTION' AND n.raised_at < now_.t - interval '24 hours')
UNION ALL
-- 1 긴급: 지금 DOWN인 설비 (같은 설비·같은 알람의 정지 알람 알림이 있으면 그 줄로 묶인다)
SELECT 'R1', 2, 0, 'DOWN', NULL, NULL, e.equipment_id, e.current_lot_no,
       '고장 정지 중: ' || e.equipment_id, e.state_since, e.state_minutes,
       e.equipment_id, coalesce(sa.alarm_code, e.open_alarm_code), NULL, NULL, NULL
  FROM v_equipment_now e
  LEFT JOIN alarm_event sa ON sa.alarm_event_id = e.state_alarm_event_id
 WHERE e.state_code = 'DOWN'
UNION ALL
-- 3 주의 ③ 품질: 보류·보류 검토 로트
SELECT 'R3', 4, 30, 'LOT', NULL, NULL, NULL, l.lot_no,
       CASE l.status WHEN 'ON_HOLD' THEN '보류 로트: ' ELSE '보류 검토 로트: ' END || l.lot_no,
       coalesce(h.held_at, l.judged_at), NULL, NULL, NULL, NULL, NULL, NULL
  FROM production_lot l
  LEFT JOIN lot_hold h ON h.lot_no = l.lot_no AND h.result = 'IN_PROGRESS'
 WHERE l.status IN ('ON_HOLD','HOLD_REVIEW')
UNION ALL
-- 3 주의 ③ 품질: 강화 검사 중인 로트 (보류 로트의 다음 1~2개, 판정 전 — FR-PRD-02-08 인계 사항)
SELECT 'R3', 4, 30, 'LOT', NULL, NULL, NULL, l.lot_no, '강화 검사 로트: ' || l.lot_no,
       h.held_at, NULL, NULL, NULL, NULL, NULL, NULL
  FROM production_lot l
  JOIN inspection_plan p USING (lot_no)
  LEFT JOIN lot_hold h ON h.hold_id = p.hold_id
 WHERE p.plan_mode = 'ENHANCED' AND p.enhance_reason = 'NEXT_LOT'
   AND l.status IN ('IN_PROCESS','WAIT_INSPECTION','WAIT_JUDGEMENT')
UNION ALL
-- 3 주의: 진행 중 작업지시서 (FR-PRD-02-08 "진행 중 작업지시", 2026-10-20 — 생성기 인계 사항과 같은 자리: 주의 칸 맨 뒤)
SELECT 'R3', 4, 80, 'WO', NULL, NULL, m.equipment_id, NULL, format('진행 중 작업지시서 %s (%s)', m.wo_no, m.equipment_id),
       m.created_at, NULL, NULL, NULL, NULL, NULL, NULL
  FROM maintenance_work_order m
 WHERE m.status NOT IN ('DONE','CANCELLED')
)
-- 같은 원인 (group_key): ① 알람이 있는 항목 = 설비|알람 번호 ② 예방 정비 알림 = 그 설비의 관련 알람 줄이 있으면 그 줄
--   (alarm_related_item: 알람 ↔ 정비 항목의 기본 소모품), 없으면 설비|item:소모품 ③ 재고 부족 = 관련 알람 줄 → 같은 소모품의
--   예방 정비 줄 순. 예: 2075 반복 알람 + 축 윤활유 점검 기한 넘김 + 축 윤활유 재고 부족 → 한 줄 (DOC-07 §10.5, DOC-04 5장)
SELECT b.report_rank, b.rank_order, b.rank_group, b.item_kind, b.notification_id, b.rule_code, b.equipment_id, b.lot_no,
       b.title, b.occurred_at, b.sort_value,
       CASE
         WHEN b.alarm_code IS NOT NULL THEN b.alarm_equipment || '|' || b.alarm_code
         WHEN b.pm_item IS NOT NULL THEN coalesce(
             (SELECT min(a.alarm_equipment || '|' || a.alarm_code) FROM base a
                JOIN alarm_related_item r ON r.alarm_code = a.alarm_code
               WHERE a.alarm_equipment = b.pm_equipment AND r.item_no = b.pm_item),
             b.pm_equipment || '|item:' || b.pm_item)
         WHEN b.stock_item IS NOT NULL THEN coalesce(
             (SELECT min(a.alarm_equipment || '|' || a.alarm_code) FROM base a
                JOIN alarm_related_item r ON r.alarm_code = a.alarm_code WHERE r.item_no = b.stock_item),
             (SELECT min(x.pm_equipment || '|item:' || x.pm_item) FROM base x WHERE x.pm_item = b.stock_item))
         WHEN b.item_kind = 'WO' THEN 'WO:' || b.title                 -- 작업지시서마다 한 줄 (같은 설비 여러 장도 따로)
       END AS group_key
  FROM base b;

-- 화면 줄 (FR-AST-COM-21): 같은 group_key는 한 줄로 묶어 가장 높은 순위 항목 자리에 둔다. 묶인 줄은 1건
--   (전체 N = 줄 수). member_count = 묶인 항목 수, members = 묶인 항목 전부 (자세히 펼칠 때)
CREATE OR REPLACE VIEW v_report_lines AS
WITH k AS (
    SELECT i.*, coalesce(i.group_key, i.item_kind || ':' || coalesce(i.notification_id::text, i.equipment_id, i.lot_no)) AS line_key
      FROM v_report_items i
), r AS (
    SELECT k.*,
           row_number() OVER (PARTITION BY line_key
                              ORDER BY rank_order, rank_group, sort_value DESC NULLS LAST, occurred_at) AS rn,
           count(*) OVER (PARTITION BY line_key) AS member_count
      FROM k
)
SELECT r.line_key, r.report_rank, r.rank_order, r.rank_group, r.item_kind, r.notification_id, r.rule_code,
       r.equipment_id, (SELECT e.process_code FROM equipment e WHERE e.equipment_id = r.equipment_id) AS process_code,
       r.lot_no, r.title, r.occurred_at, r.sort_value, r.member_count::int AS member_count,
       CASE r.report_rank WHEN 'R0' THEN 'SAFETY' WHEN 'R1' THEN 'URGENT' WHEN 'R2' THEN 'PRODUCTION'
                          WHEN 'R4' THEN 'INFO' ELSE 'CAUTION' END AS count_bucket,   -- 0-1은 주의에 센다
       (SELECT jsonb_agg(jsonb_build_object('item_kind', m.item_kind, 'report_rank', m.report_rank,
                         'notification_id', m.notification_id, 'rule_code', m.rule_code, 'title', m.title,
                         'occurred_at', m.occurred_at)
                         ORDER BY m.rank_order, m.rank_group, m.sort_value DESC NULLS LAST, m.occurred_at)
          FROM k m WHERE m.line_key = r.line_key) AS members
  FROM r WHERE r.rn = 1;

-- ---------------------------------------------------------------------
-- 교대 × 설비 지표 (R-44·R-45, DOC-07 6장)
--   PBT = 계획 가동 시간 − 그 설비 MAINT 시간 / A = RUN ÷ PBT / E = 기준 사이클 × PQ ÷ RUN / QBR = (GQ+RQ) ÷ PQ
--   상태 구간은 교대 시간 창으로 잘라서 센다. 진행 중 구간의 끝은 app_now()
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_equipment_kpi AS
WITH seg AS (
    SELECT s.shift_id, st.equipment_id, st.state_code,
           extract(epoch FROM (least(coalesce(st.end_at, app_now()), s.end_at) - greatest(st.start_at, s.start_at))) / 60 AS minutes
      FROM shift s
      JOIN equipment_state_log st ON st.start_at < s.end_at AND coalesce(st.end_at, 'infinity'::timestamptz) > s.start_at
), t AS (
    SELECT shift_id, equipment_id,
           sum(minutes) FILTER (WHERE state_code = 'RUN')   AS run_min,
           sum(minutes) FILTER (WHERE state_code = 'MAINT') AS maint_min,
           sum(minutes) FILTER (WHERE state_code = 'DOWN')  AS down_min
      FROM seg WHERE minutes > 0 GROUP BY 1, 2
), q AS (
    SELECT shift_id, equipment_id, sum(pq) AS pq, sum(gq) AS gq, sum(rq) AS rq, sum(sq) AS sq
      FROM operation_report GROUP BY 1, 2
)
-- 계획 가동 시간 (R-44): 끝난 교대 = 480분 − 정비. **진행 중인 교대 = 지금까지 지난 근무 분(휴식 제외) − 정비** (2026-10-23 —
--   교대 중간에 480분 전체로 나누면 가동률·OEE가 교대 초반에 0에 가깝게 보여서. 끝난 교대·보고서 값은 그대로). 시작 전 교대 = 0
SELECT s.shift_id, s.work_date, s.shift_type, e.equipment_id, e.process_code,
       s.planned_time_min,
       round(p.plan_min - coalesce(t.maint_min, 0), 2)                             AS pbt_min,
       round(coalesce(t.run_min, 0), 2) AS run_min, round(coalesce(t.down_min, 0), 2) AS down_min,
       round(coalesce(t.maint_min, 0), 2) AS maint_min,
       coalesce(q.pq, 0) AS pq, coalesce(q.gq, 0) AS gq, coalesce(q.rq, 0) AS rq, coalesce(q.sq, 0) AS sq,
       round(100 * coalesce(t.run_min, 0) / nullif(p.plan_min - coalesce(t.maint_min, 0), 0), 1) AS availability_pct,
       round(100 * e.std_cycle_min * q.pq / nullif(t.run_min, 0), 1)               AS performance_pct,
       round(100 * (q.gq + q.rq)::numeric / nullif(q.pq, 0), 1)                    AS quality_pct,
       round(100 * (coalesce(t.run_min, 0) / nullif(p.plan_min - coalesce(t.maint_min, 0), 0))
                 * (e.std_cycle_min * q.pq / nullif(t.run_min, 0))
                 * ((q.gq + q.rq)::numeric / nullif(q.pq, 0)), 1)                  AS oee_pct,
       round(p.plan_min, 2)                                                        AS planned_so_far_min
  FROM shift s
 CROSS JOIN LATERAL (SELECT CASE WHEN app_now() >= s.end_at THEN s.planned_time_min::numeric
                                 WHEN app_now() <= s.start_at THEN 0::numeric
                                 ELSE least(s.planned_time_min, fn_work_minutes(s.start_at, app_now())) END AS plan_min) p
 CROSS JOIN equipment e
  LEFT JOIN t ON t.shift_id = s.shift_id AND t.equipment_id = e.equipment_id
  LEFT JOIN q ON q.shift_id = s.shift_id AND q.equipment_id = e.equipment_id
 WHERE e.is_active;

-- 라인 OEE (R-44: OP-30 2대 합, 계획 가동 시간 = 480분 × 2대 — 한 대의 예방 정비는 빼지 않음. 진행 중 교대는 지금까지 지난 근무 분 × 2대)
CREATE OR REPLACE VIEW v_shift_line_oee AS
SELECT k.shift_id, k.work_date, k.shift_type,
       round(sum(k.planned_so_far_min))::bigint AS line_pbt_min, sum(k.run_min) AS run_min, sum(k.pq) AS pq,
       round(100 * sum(k.run_min) / nullif(sum(k.planned_so_far_min), 0), 1) AS availability_pct,
       round(100 * sum(e.std_cycle_min * k.pq) / nullif(sum(k.run_min), 0), 1) AS performance_pct,
       round(100 * sum(k.gq + k.rq)::numeric / nullif(sum(k.pq), 0), 1) AS quality_pct,
       round(100 * (sum(k.run_min) / nullif(sum(k.planned_so_far_min), 0))
                 * (sum(e.std_cycle_min * k.pq) / nullif(sum(k.run_min), 0))
                 * (sum(k.gq + k.rq)::numeric / nullif(sum(k.pq), 0)), 1) AS oee_pct
  FROM v_shift_equipment_kpi k JOIN equipment e USING (equipment_id)
 WHERE k.process_code = 'OP-30'
 GROUP BY k.shift_id, k.work_date, k.shift_type;

-- ---------------------------------------------------------------------
-- 로트 추적 (PRD-05, FR-PRD-05-01): 원자재 → 공정 5개 → 검사 → 보류 → 출하 한 줄
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_lot_trace AS
SELECT l.lot_no, l.status,
       jsonb_build_object(
         'material', (SELECT jsonb_build_object('material_lot_no', m.material_lot_no, 'received_date', m.received_date,
                                                'supplier_cert_no', m.supplier_cert_no, 'heat_batch_no', m.heat_batch_no)
                        FROM raw_material_lot m WHERE m.material_lot_no = l.material_lot_no),
         'order', (SELECT jsonb_build_object('order_no', o.order_no, 'order_qty', o.order_qty, 'due_at', o.due_at, 'status', o.status)
                     FROM production_order o WHERE o.order_no = l.order_no),
         'operations', (SELECT jsonb_agg(jsonb_build_object('process_code', r.process_code, 'equipment_id', r.equipment_id,
                                         'shift_id', r.shift_id, 'start_at', r.start_at, 'end_at', r.end_at,
                                         'pq', r.pq, 'gq', r.gq, 'rq', r.rq, 'sq', r.sq) ORDER BY p.seq, r.start_at)
                          FROM operation_report r JOIN process p USING (process_code) WHERE r.lot_no = l.lot_no),
         'inspection', (SELECT jsonb_build_object('plan_mode', ip.plan_mode, 'enhance_reason', ip.enhance_reason,
                                                  'judgement', ip.judgement, 'judged_at', ip.judged_at,
                                                  'fail_count', (SELECT count(*) FROM inspection_result x
                                                                  WHERE x.lot_no = l.lot_no AND x.use_for_judgement AND x.judgement = 'FAIL'))
                          FROM inspection_plan ip WHERE ip.lot_no = l.lot_no),
         'holds', (SELECT jsonb_agg(jsonb_build_object('hold_id', h.hold_id, 'trigger_type', h.trigger_type, 'held_at', h.held_at,
                                     'held_by', h.held_by, 'reason', h.hold_reason, 'result', h.result) ORDER BY h.held_at)
                     FROM lot_hold h WHERE h.lot_no = l.lot_no),
         'alarms', (SELECT jsonb_agg(jsonb_build_object('alarm_event_id', a.alarm_event_id, 'alarm_code', a.alarm_code,
                                      'equipment_id', a.equipment_id, 'occurred_at', a.occurred_at) ORDER BY a.occurred_at)
                      FROM alarm_event a WHERE a.lot_no = l.lot_no),
         'shipments', (SELECT jsonb_agg(jsonb_build_object('shipment_no', s.shipment_no, 'shipped_at', s.shipped_at,
                                         'customer_code', s.customer_code, 'qty', sl.qty) ORDER BY s.shipped_at)
                         FROM shipment_line sl JOIN shipment s USING (shipment_no)
                        WHERE sl.lot_no = l.lot_no AND s.status <> 'DRAFT')
       ) AS trace
  FROM production_lot l;

-- ---------------------------------------------------------------------
-- 교대 총 목표 (R-88, DOC-07 §4.1): 총 목표 = 목표 + 이월 (주간은 이월 0)
--   carry_over_is_provisional: 야간 이월이 "잠정" = 같은 날 주간 교대 보고서가 아직 확정 전 (확정되면 다시 계산)
--   is_report_confirmed = false 인 교대의 값을 다른 곳(브리핑·이월·일일 보고서)에서 쓰면 "잠정" (FR-AST-02-17)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_target AS
SELECT s.shift_id, s.work_date, s.shift_type, s.start_at, s.end_at, s.planned_time_min, s.supervisor_user_id,
       s.target_qty, s.carry_over_qty, s.target_qty + s.carry_over_qty AS total_target_qty,
       -- 주간 기록(보고서·공정 실적)이 없으면 이월은 0으로 정해져 잠정이 아니다 (fn_refresh_carry_over와 같은 기준)
       s.shift_type = 'NIGHT'
         AND EXISTS (SELECT 1 FROM shift d WHERE d.work_date = s.work_date AND d.shift_type = 'DAY'
                        AND (EXISTS (SELECT 1 FROM shift_report x WHERE x.shift_id = d.shift_id)
                             OR EXISTS (SELECT 1 FROM operation_report o WHERE o.shift_id = d.shift_id)))
         AND NOT EXISTS (SELECT 1 FROM shift d JOIN shift_report dr USING (shift_id)
                          WHERE d.work_date = s.work_date AND d.shift_type = 'DAY' AND dr.status IN ('CONFIRMED','REVISED'))
                                                                        AS carry_over_is_provisional,
       r.status AS report_status,
       coalesce(r.status IN ('CONFIRMED','REVISED'), false)            AS is_report_confirmed
  FROM shift s
  LEFT JOIN shift_report r USING (shift_id);

-- ---------------------------------------------------------------------
-- 교대 진행·예측 (R-48·R-88, DOC-07 8장, FR-PRD-01-15·16, FR-AST-02-04). 지난 교대는 교대 끝 시각 기준 값
--   교대 안 휴식 1시간 [가상: 팀 결정 2026-10-08]: 주간 12:00~13:00, 야간 00:00~01:00 (교대 사이 17:00~20:00·05:00~08:00은
--     라인 정지). 지난 계획 시간 = 교대 시작부터 지난 분 − 그중 휴식 분 (최대 계획 가동 시간) — DOC-07 8장 예 "4시간(240분) 뒤
--     … 남은 240분"과 같음 (12:00 = 휴식 시작)
--   속도 = 최근 계획 60분(휴식이 끼면 그만큼 앞으로 늘린 창)의 실적 ÷ 60, 교대 시작 후 1시간 안은 지금까지 실적 ÷ 지난 계획 시간
--   예측 = 실적 + 속도 × 남은 계획 시간 (반올림한 개수). 부족 = max(0, 총 목표 − 예측)
--   목표 미달 위험 = 예측 < 총 목표 × 90% (총 목표 90이면 81개, 93이면 83.7개)
--   손실(추정) = 고장 손실 + 속도 손실. 3D 라인 뷰는 합 하나, 교대·일일 보고서는 따로 (FR-PRD-01-16)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_progress AS
WITH b0 AS (
    SELECT t.*, least(greatest(app_now(), t.start_at), t.end_at) AS as_of,
           CASE t.shift_type WHEN 'DAY' THEN (t.work_date + time '12:00') AT TIME ZONE 'Asia/Seoul'
                             ELSE (t.work_date + 1 + time '00:00') AT TIME ZONE 'Asia/Seoul' END AS break_start_at
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

-- ---------------------------------------------------------------------
-- MTTR·MTBF (R-45a, DOC-07 6.2) — 설비별 최근 30일. 3D 지표 카드에서 빼고 비서 질문으로 본다 (2026-10-07 UI 검토)
--   고장 = 정지 등급 DOWN만 (R-22). MTTR = DOWN 시간 합 ÷ 고장 횟수 (분)
--   MTBF = 고장 간격(그 기간 RUN 시간) 합 ÷ 고장 횟수 (시간) [제안: ISO 22400 TBF = 가동 시간]. 고장 0건이면 NULL("—")
--   MTTR 주의 = 120분 초과 (DOC-07 10.1)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_equipment_reliability_30d AS
WITH w AS (SELECT app_now() - interval '30 days' AS t0, app_now() AS t1),
seg AS (
    SELECT st.equipment_id, st.state_code,
           extract(epoch FROM (least(coalesce(st.end_at, w.t1), w.t1) - greatest(st.start_at, w.t0))) / 60 AS minutes,
           st.start_at >= w.t0 AS started_in_window
      FROM equipment_state_log st, w
     WHERE st.start_at < w.t1 AND coalesce(st.end_at, 'infinity'::timestamptz) > w.t0
)
SELECT e.equipment_id, e.process_code,
       count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window)::int        AS failure_count,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 1)                      AS down_min,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'RUN'), 1)                       AS run_min,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window)
             / nullif(count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 0), 1) AS mttr_min,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'RUN') / 60
             / nullif(count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 0), 1) AS mtbf_hours,
       coalesce(sum(s.minutes) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window)
             / nullif(count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 0) > 120, false) AS is_mttr_warn
  FROM equipment e
  LEFT JOIN seg s USING (equipment_id)
 WHERE e.is_active
 GROUP BY e.equipment_id, e.process_code;
