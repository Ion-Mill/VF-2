-- 2026-10-24 (PR #142, 구현_중_수정사항/1023_수정간단내용.md 11장 — 사용자 결정 "추천안대로")
-- ① 진행 중인 교대의 계획 가동 시간 = 지금까지 지난 근무 분(휴식 제외) − 정비 (끝난 교대는 480분 − 정비 그대로, R-44)
--    v_shift_equipment_kpi 맨 끝에 planned_so_far_min 칸을 더하고 계획 시간·가동률·OEE를 이 값으로. v_shift_line_oee도 (칸 이름·타입 그대로)
-- ② Cpk 표본 = 최근 측정값 50개 (DOC-06 §5.1 ④, 관리도 점과 같은 범위, R-30) — fn_item_cpk (Cpk 미달 → 전수 규칙이 쓰는 것)
-- 원본: backend/db/views/10_views.sql, backend/db/views/30_live_rules.sql (같은 글자). fn_work_minutes는 이미 있음 (20261020 p1c)
--
-- 되돌리기: 아래 "되돌리기" 블록 (2026-10-24 공용 mom-db에서 읽은 바뀌기 전 정의). planned_so_far_min 칸은 뷰를 DROP 해야 빠지므로
--   되돌릴 때는 v_shift_line_oee → v_shift_equipment_kpi 순으로 DROP VIEW 뒤 두 뷰를 옛 정의로 CREATE (다른 뷰는 이 두 뷰를 읽지 않음)

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

CREATE OR REPLACE FUNCTION fn_item_cpk(p_product_code text, p_item_seq int, OUT n int, OUT cpk numeric)
LANGUAGE sql STABLE AS $$
    -- 최근 측정값 50개 (DOC-06 §5.1 ④ "특성마다 최근 측정값 50개", 관리도 점과 같은 범위 — 2026-10-23, 전에는 전체 값)
    WITH recent AS (
        SELECT r.measured_value AS x, r.measured_at, r.result_id
          FROM v_inspection_result r
         WHERE r.product_code = p_product_code AND r.item_seq = p_item_seq AND r.use_for_judgement AND r.measured_value IS NOT NULL
           AND r.measured_at <= app_now()
         ORDER BY r.measured_at DESC, r.result_id DESC LIMIT 50
    ), v AS (
        SELECT x, x - lag(x) OVER (ORDER BY measured_at, result_id) AS mr FROM recent
    )
    SELECT count(v.x)::int,
           CASE WHEN count(v.x) < 50 THEN NULL
                ELSE least(coalesce(i.usl - avg(v.x), 'Infinity'::numeric), coalesce(avg(v.x) - i.lsl, 'Infinity'::numeric))
                     / nullif(3 * avg(abs(v.mr)) / 1.128, 0) END
      FROM inspection_item i LEFT JOIN v ON true
     WHERE i.product_code = p_product_code AND i.item_seq = p_item_seq
     GROUP BY i.lsl, i.usl;
$$;

-- ---------------- 되돌리기 (2026-10-24 공용 mom-db에서 읽은 바뀌기 전 정의 — 필요할 때만 주석을 풀어 실행) ----------------
-- DROP VIEW v_shift_line_oee;
-- DROP VIEW v_shift_equipment_kpi;
-- CREATE VIEW v_shift_equipment_kpi AS  -- = 20261020 p2a_views 정의: pbt_min·availability·oee의 분모가 s.planned_time_min − maint_min
--   (backend/db/views/10_views.sql 의 git 2026-10-23 이전 판: git show b8aa51a:11_automotive/backend/db/views/10_views.sql)
-- CREATE VIEW v_shift_line_oee AS        -- = 같은 판: line_pbt_min = sum(k.planned_time_min), 분모도 sum(k.planned_time_min)
-- CREATE OR REPLACE FUNCTION fn_item_cpk -- = 같은 판 30_live_rules.sql: WITH v AS (전체 측정값) — 최근 50개 제한 없음
--   (git show b8aa51a:11_automotive/backend/db/views/30_live_rules.sql)
-- 되돌린 뒤 GRANT: 뷰는 GRANT SELECT ON ALL TABLES 때 받은 권한이 사라지므로 backend/db/roles.sql 의 GRANT SELECT 두 줄을 다시 (mom_app, mom_ai_ro)
