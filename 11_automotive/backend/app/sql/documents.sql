-- 보고서·문서 버전 (PRD-02·04, AST-03)

-- 교대 보고서. target_qty = 총 목표 (목표 + 이월, R-88 — 생산 칸). 이월이 잠정이면 carry_over_is_provisional
-- name: shift_report
SELECT r.*, s.work_date, s.shift_type, s.start_at, s.end_at, s.supervisor_user_id, s.target_qty AS shift_target_qty, s.carry_over_qty,
       t.carry_over_is_provisional
  FROM shift_report r JOIN shift s USING (shift_id) JOIN v_shift_target t USING (shift_id)
 WHERE r.shift_id = :shift_id;

-- name: shift_report_update
UPDATE shift_report
   SET notable_text = coalesce(CAST(:notable_text AS text), notable_text),
       handover_text = coalesce(CAST(:handover_text AS text), handover_text),
       status = CAST(:status AS varchar), current_version = :version
 WHERE shift_id = :shift_id;

-- name: shift_report_confirm
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = :actor, confirmed_at = app_now()
 WHERE shift_id = :shift_id AND status IN ('AI_DRAFT','EDITING');

-- 일일 보고서. 하루 목표 180 고정,
-- 부족 = 180 − 하루 실적 (다음 날로 넘기지 않음, R-88). 확정 전 교대가 있으면 그 칸은 잠정 (R-72)
-- name: daily_report
SELECT d.*, greatest(0, d.target_qty - d.actual_qty) AS shortfall_qty,
       (SELECT coalesce(jsonb_agg(t.shift_id ORDER BY t.start_at), '[]'::jsonb) FROM v_shift_target t
         WHERE t.work_date = d.work_date AND NOT t.is_report_confirmed) AS provisional_shift_ids
  FROM daily_report d WHERE d.work_date = CAST(:work_date AS date);

-- 보고서의 필수 정지 + 그 정지로 만든 작업지시서 (2026-10-20 정비 탭 확인 요청 2 — 화면이 알람·설비로 추측하던 연결)
--   구간 = 교대(:shift_id) 또는 그 생산일의 두 교대(:work_date). 고장 정지(DOWN, 또는 사유가 고장 그룹)이고 구간 안 길이가
--   5분 이상인 것 (DOC-07 §5.4). 분·손실은 구간 안 부분만 — 손실 = 구간 안 정지 분 ÷ 그 설비 기준 사이클 (fn_failure_loss_qty와 같은 기준)
--   작업지시서 = 정지 알람으로 만든 것(alarm_event_id) 또는 그 알람의 반복 알람 2단계 알림으로 만든 것(trigger_notification_id →
--   알림의 alarm_event_id, 예: MW-0904). 보고서 시점(구간 끝)의 상태 wo_status_at_report: WAITING_APPROVAL 승인 전 /
--   IN_PROGRESS 진행 중(승인 뒤) / DONE 완료 / CANCELLED 취소. 그때 아직 없던 작업지시서는 NULL (지금 상태는 wo_status)
-- name: report_stops
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
), s AS (
    SELECT st.state_log_id, st.equipment_id, st.state_code, coalesce(st.reason_code, st.reason_suggested_code) AS reason_code,
           dr.reason_name, st.start_at, st.end_at, st.alarm_event_id, a.alarm_code, e.std_cycle_min, w.t AS report_at,
           greatest(st.start_at, w.f) AS s_at, least(coalesce(st.end_at, app_now()), w.t) AS e_at
      FROM equipment_state_log st
      JOIN equipment e USING (equipment_id)
      CROSS JOIN w
      LEFT JOIN downtime_reason dr ON dr.reason_code = coalesce(st.reason_code, st.reason_suggested_code)
      LEFT JOIN alarm_event a ON a.alarm_event_id = st.alarm_event_id
     WHERE st.state_code <> 'RUN' AND (st.state_code = 'DOWN' OR dr.reason_group = 'FAILURE')
       AND st.start_at < w.t AND coalesce(st.end_at, 'infinity'::timestamptz) > w.f
)
SELECT s.state_log_id, s.equipment_id, s.state_code, s.reason_code, s.reason_name, s.start_at, s.end_at,
       s.s_at AS from_at, s.e_at AS to_at, round(extract(epoch FROM (s.e_at - s.s_at)) / 60)::int AS minutes,
       round(extract(epoch FROM (s.e_at - s.s_at)) / 60 / nullif(s.std_cycle_min, 0), 1) AS loss_qty, true AS is_estimated,
       s.alarm_event_id, s.alarm_code, wo.wo_no, wo.status AS wo_status,
       CASE WHEN wo.wo_no IS NULL OR wo.created_at > s.report_at THEN NULL
            WHEN wo.cancelled_at <= s.report_at THEN 'CANCELLED'
            WHEN wo.completed_at <= s.report_at THEN 'DONE'
            WHEN wo.approved_at <= s.report_at THEN 'IN_PROGRESS'
            ELSE 'WAITING_APPROVAL' END AS wo_status_at_report
  FROM s
  LEFT JOIN LATERAL (
      SELECT m.wo_no, m.status, m.created_at, m.approved_at, m.completed_at, m.cancelled_at
        FROM maintenance_work_order m
       WHERE s.alarm_event_id IS NOT NULL
         AND (m.alarm_event_id = s.alarm_event_id
              OR m.trigger_notification_id IN (SELECT n.notification_id FROM notification n WHERE n.alarm_event_id = s.alarm_event_id))
       ORDER BY (m.alarm_event_id IS NOT DISTINCT FROM s.alarm_event_id) DESC, m.created_at
       LIMIT 1) wo ON true
 WHERE s.e_at - s.s_at >= interval '5 minutes'
 ORDER BY minutes DESC, loss_qty DESC NULLS LAST, s.s_at;   -- ① 정지 시간 ② 손실 ③ 시작 (R-74, FR-PRD-02-04)

-- name: daily_report_update
UPDATE daily_report SET issues_summary = coalesce(CAST(:issues_summary AS text), issues_summary),
       memo = CASE WHEN CAST(:memo_given AS boolean) THEN CAST(:memo AS text) ELSE memo END,
       status = CAST(:status AS varchar), current_version = :version
 WHERE work_date = CAST(:work_date AS date);

-- 잠정 칸(확정 안 된 교대 보고서)이 있으면 MGR [확정] 불가 (R-72). 관리자 메모(선택)를 같이 받는다 — 비우면 있던 메모 그대로
--   (2026-10-20 정비 탭 확인 요청 1: 전에는 확정 API가 memo를 버렸다)
-- name: daily_report_confirm
UPDATE daily_report d SET status = 'CONFIRMED', confirmed_by = :actor, confirmed_at = app_now(),
       memo = coalesce(nullif(btrim(CAST(:memo AS text)), ''), d.memo)
 WHERE d.work_date = CAST(:work_date AS date) AND d.status IN ('AI_DRAFT','EDITING')
   AND NOT EXISTS (SELECT 1 FROM shift s LEFT JOIN shift_report r USING (shift_id)
                    WHERE s.work_date = d.work_date AND coalesce(r.status, 'AI_DRAFT') NOT IN ('CONFIRMED','REVISED'));

-- name: pm_record_get
SELECT * FROM pm_record WHERE pm_record_id = :pm_record_id;

-- name: pm_record_update
UPDATE pm_record SET result = coalesce(CAST(:result AS varchar), result),
       measured_value = coalesce(CAST(:measured_value AS numeric), measured_value),
       measured_unit = coalesce(CAST(:measured_unit AS varchar), measured_unit), memo = coalesce(CAST(:memo AS text), memo),
       status = CAST(:status AS varchar), current_version = :version
 WHERE pm_record_id = :pm_record_id;

-- name: shipment_update
UPDATE shipment SET memo = coalesce(CAST(:memo AS text), memo), status = CAST(:status AS varchar), current_version = :version
 WHERE shipment_no = :shipment_no;

-- name: save_revision
SELECT fn_save_revision(:doc_type, :doc_key, :author_kind, CAST(:author AS text), CAST(:reason AS text), :status_after,
                        CAST(:content AS jsonb), CAST(:changes AS jsonb)) AS version_no;

-- name: revisions
SELECT r.revision_id, r.version_no, r.author_kind, r.author_user_id, u.user_name AS author_name, r.created_at, r.reason,
       r.status_after, r.internal_doc_rev,
       (SELECT count(*) FROM document_revision_change c WHERE c.revision_id = r.revision_id)::int AS changed_fields
  FROM document_revision r LEFT JOIN app_user u ON u.user_id = r.author_user_id
 WHERE r.doc_type = :doc_type AND r.doc_key = :doc_key
   AND (CAST(:own_user AS text) IS NULL OR r.author_user_id = CAST(:own_user AS text))
 ORDER BY r.version_no;

-- name: revision
SELECT r.*, (SELECT coalesce(jsonb_agg(jsonb_build_object('field', c.field_name, 'before', c.before_value, 'after', c.after_value)
                                       ORDER BY c.field_name), '[]')
               FROM document_revision_change c WHERE c.revision_id = r.revision_id) AS changes
  FROM document_revision r WHERE r.revision_id = :revision_id;

-- name: internal_docs
SELECT doc_no, doc_kind, doc_name, current_rev, rev_date, status, approved_by, approved_at, is_search_target, file_ref
  FROM internal_doc ORDER BY doc_no;

-- name: internal_doc
SELECT * FROM internal_doc WHERE doc_no = :doc_no;

-- 문서의 지금 버전 (CONFLICT_VERSION 확인, API명세서 1장)
-- name: current_version
SELECT CASE CAST(:doc_type AS text)
         WHEN 'WORK_ORDER'   THEN (SELECT current_version FROM maintenance_work_order WHERE wo_no = CAST(:doc_key AS text))
         WHEN 'WORK_RECORD'  THEN (SELECT current_version FROM work_record WHERE record_no = CAST(:doc_key AS text))
         WHEN 'SHIFT_REPORT' THEN (SELECT current_version FROM shift_report WHERE shift_id = CAST(:doc_key AS text))
         WHEN 'DAILY_REPORT' THEN (SELECT current_version FROM daily_report WHERE work_date::text = CAST(:doc_key AS text))
         WHEN 'PM_RECORD'    THEN (SELECT current_version FROM pm_record WHERE pm_record_id::text = CAST(:doc_key AS text))
         WHEN 'SHIPMENT'     THEN (SELECT current_version FROM shipment WHERE shipment_no = CAST(:doc_key AS text))
       END AS current_version;

-- 문서함 (DOC-01, SCR-18): 문서 6종을 한 목록으로. 보기 권한은 서버가 종류별로 거른다 (13.1).
-- is_todo = 내 할 일: 승인 대기 작업지시서(SUP·MGR) / 내가 담당인 진행 작업지시서·수정 중 작업기록(MNT·OPR) /
--   확정 뒤 반장 확인 대기 작업기록서(SUP) / 내 교대 보고서 확정 대기(SUP) / 일일 보고서 확정 대기(MGR) /
--   내가 쓴 수정 중 정비 기록 / 출하 초안(SUP)
-- name: inbox
WITH docs AS (
    SELECT 'WORK_ORDER' AS doc_type, w.wo_no AS doc_key, w.title, w.status, w.equipment_id, w.created_at AS base_at,
           (w.status IN ('AI_DRAFT','EDITING') AND CAST(:role AS text) IN ('SUP','MGR'))
           OR (w.status IN ('APPROVED','IN_PROGRESS') AND w.assignee_user_id = CAST(:user_id AS text)) AS is_todo
      FROM maintenance_work_order w
    UNION ALL
    SELECT 'WORK_RECORD', r.record_no, coalesce(r.action, r.cause, r.record_no), r.status, r.equipment_id, r.start_at,
           (r.status IN ('AI_DRAFT','EDITING') AND CAST(:role AS text) IN ('MNT','OPR'))
           OR (r.status = 'CONFIRMED' AND r.record_type = 'FULL' AND CAST(:role AS text) = 'SUP')
      FROM work_record r
    UNION ALL
    SELECT 'SHIFT_REPORT', r.shift_id, r.shift_id || ' 교대 보고서', r.status, NULL, s.end_at,
           r.status IN ('AI_DRAFT','EDITING') AND s.supervisor_user_id = CAST(:user_id AS text)
      FROM shift_report r JOIN shift s USING (shift_id)
    UNION ALL
    SELECT 'DAILY_REPORT', d.work_date::text, d.work_date::text || ' 일일 보고서', d.status, NULL,
           coalesce((SELECT max(s.end_at) FROM shift s WHERE s.work_date = d.work_date) + interval '1 hour',
                    (d.work_date + 1)::timestamp AT TIME ZONE 'Asia/Seoul' + interval '6 hours'),   -- 늦어도 = 야간 끝 + 1시간
           d.status IN ('AI_DRAFT','EDITING') AND CAST(:role AS text) = 'MGR'
      FROM daily_report d
    UNION ALL
    SELECT 'PM_RECORD', p.pm_record_id::text, t.item_name, p.status, t.equipment_id, p.done_at,
           p.status = 'DRAFT' AND p.recorded_by = CAST(:user_id AS text)
      FROM pm_record p JOIN pm_task t USING (pm_task_id)
    UNION ALL
    SELECT 'SHIPMENT', s.shipment_no, s.customer_code || ' 출하 (납기 ' || s.due_date || ')', s.status, NULL,
           coalesce(s.shipped_at, s.due_date::timestamp AT TIME ZONE 'Asia/Seoul'),
           s.status = 'DRAFT' AND CAST(:role AS text) = 'SUP'
      FROM shipment s
)
SELECT d.doc_type, d.doc_key, d.title, d.status, d.equipment_id, d.is_todo,
       coalesce(v.updated_at, d.base_at) AS updated_at, v.current_version
  FROM docs d
  LEFT JOIN LATERAL (SELECT max(r.created_at) AS updated_at, max(r.version_no) AS current_version FROM document_revision r
                      WHERE r.doc_type = d.doc_type AND r.doc_key = d.doc_key) v ON true
 WHERE (CAST(:doc_type AS text) IS NULL OR d.doc_type = CAST(:doc_type AS text))
   AND (CAST(:status AS text) IS NULL OR d.status = CAST(:status AS text))
   AND (CAST(:todo_only AS boolean) IS NOT TRUE OR d.is_todo)
 ORDER BY d.is_todo DESC, coalesce(v.updated_at, d.base_at) DESC NULLS LAST
 LIMIT CAST(:limit AS int);

-- 출처 요약 카드·팝업 (DOCS-01, R-85): 사내 문서 이름·번호·개정·절 + 그 절 앞 2~3줄(card) 또는 본문(full).
-- 절 표기는 "§2.11"과 "2.11" 둘 다 받는다. 원문 출처는 내보내지 않는다
-- name: doc_section
SELECT d.doc_no, d.doc_name, d.current_rev AS rev, c.section,
       split_part(string_agg(c.chunk_text, E'\n' ORDER BY c.chunk_id), E'\n', 1) AS section_title,
       string_agg(c.chunk_text, E'\n' ORDER BY c.chunk_id) AS body
  FROM internal_doc d JOIN doc_chunk c ON c.doc_no = d.doc_no AND c.doc_rev = d.current_rev
 WHERE d.doc_no = :doc_no AND c.section IN (CAST(:section AS text), '§' || CAST(:section AS text))
 GROUP BY d.doc_no, d.doc_name, d.current_rev, c.section;

-- 사내 문서 개정 승인 (DOCS-02, R-52): 새 현행판 = 그 개정. 승인자는 MGR (트리거 R-36). 문서 수정 알림은 fn_save_revision
-- name: internal_doc_approve
UPDATE internal_doc SET current_rev = :rev, rev_date = CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date), status = 'APPROVED',
       approved_by = :actor, approved_at = app_now()
 WHERE doc_no = :doc_no AND (status = 'PENDING' OR current_rev <> :rev);

-- name: internal_doc_save_revision
SELECT fn_save_revision('INTERNAL_DOC', :doc_no, 'HUMAN', :actor, :reason, 'APPROVED', CAST(:content AS jsonb), CAST(:changes AS jsonb),
                        :rev) AS version_no;

-- 그 교대 반장 (RPT-02~04 "그 교대 S", R-36). 저장·확정·확정 후 수정 모두 이 사람만
-- name: shift_supervisor
SELECT supervisor_user_id FROM shift WHERE shift_id = :shift_id;

-- ---------------------------------------------------------------------
-- 보고서 칸 (2026-10-20 요구사항 대조 상 4번 — FR-PRD-02-03~06, FR-PRD-04-02~07). 교대(:shift_id) 또는 그 생산일(:work_date) 구간.
-- 저장 칸이 아니라 원기록으로 그때그때 계산한다 (보고서 숫자 = 원기록, FR-PRD-02-12). 쓰는 곳: GET /api/reports/shift·daily
-- ---------------------------------------------------------------------

-- 순간 정지 한 줄 (R-74): 필수 정지와 같은 고장 정지 중 구간 안 5분 미만 — 건수·합계 분
-- name: report_micro_stops
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
), s AS (
    SELECT extract(epoch FROM (least(coalesce(st.end_at, app_now()), w.t) - greatest(st.start_at, w.f))) / 60 AS mins
      FROM equipment_state_log st CROSS JOIN w
      LEFT JOIN downtime_reason dr ON dr.reason_code = coalesce(st.reason_code, st.reason_suggested_code)
     WHERE st.state_code <> 'RUN' AND (st.state_code = 'DOWN' OR dr.reason_group = 'FAILURE')
       AND st.start_at < w.t AND coalesce(st.end_at, 'infinity'::timestamptz) > w.f
)
SELECT count(*) FILTER (WHERE mins > 0 AND mins < 5)::int AS count,
       round(coalesce(sum(mins) FILTER (WHERE mins > 0 AND mins < 5), 0), 1) AS minutes
  FROM s;

-- 로트 칸 (FR-PRD-02-03·04-06): 구간에 만든(투입 교대) · 완료(OP-50 끝) · 진행 · 보류 · 판정 대기 · 출하 가능 로트, 구간 출하 번호
-- name: report_lots
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
)
SELECT v.lot_no, v.order_no, v.status, v.input_shift_id, v.input_qty, v.completed_qty, v.scrap_qty, v.op50_done_at, v.passed_at,
       v.input_shift_id = ANY (w.shifts)                                        AS made_here,
       coalesce(v.op50_done_at >= w.f AND v.op50_done_at < w.t, false)          AS completed_here,
       v.status = 'IN_PROCESS'                                                  AS in_progress,
       v.status IN ('ON_HOLD','HOLD_REVIEW')                                    AS held,
       v.status IN ('WAIT_INSPECTION','WAIT_JUDGEMENT')                         AS waiting_judgement,
       v.status IN ('PASSED','RELEASED') AND v.fg_remaining_qty > 0              AS shippable,
       (SELECT string_agg(DISTINCT s.shipment_no, ',') FROM shipment_line sl JOIN shipment s USING (shipment_no)
         WHERE sl.lot_no = v.lot_no AND s.status <> 'DRAFT' AND s.shipped_at >= w.f AND s.shipped_at < w.t) AS shipped_here
  FROM v_production_lot v CROSS JOIN w
 WHERE v.input_shift_id = ANY (w.shifts)
    OR (v.op50_done_at >= w.f AND v.op50_done_at < w.t)
    OR EXISTS (SELECT 1 FROM operation_report r WHERE r.lot_no = v.lot_no AND r.start_at < w.t
                 AND coalesce(r.end_at, 'infinity'::timestamptz) > w.f)
    OR EXISTS (SELECT 1 FROM lot_hold h WHERE h.lot_no = v.lot_no AND h.held_at < w.t
                 AND coalesce(h.released_at, h.scrap_approved_at, 'infinity'::timestamptz) >= w.f)
 ORDER BY v.lot_no;

-- 병목 칸 (FR-PRD-02-05): 구간에 걸친 병목 구간 — 공정·원인·시간(구간 안), 속도 손실(구간 안, 추정), DOC-07 §7.5 조치 줄
-- name: report_bottleneck
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
), b AS (
    SELECT bl.*, lead(bl.changed_at) OVER (ORDER BY bl.changed_at) AS next_at FROM bottleneck_log bl
)
SELECT b.bottleneck_log_id, b.new_process_code AS process_code, b.cause_code, fn_bottleneck_cause_ko(b.cause_code) AS cause_name,
       greatest(b.changed_at, w.f) AS from_at, least(coalesce(b.next_at, app_now()), w.t) AS to_at,
       round(extract(epoch FROM (least(coalesce(b.next_at, app_now()), w.t) - greatest(b.changed_at, w.f))) / 60)::int AS minutes,
       (fn_interval_losses(greatest(b.changed_at, w.f), least(coalesce(b.next_at, app_now()), w.t), b.cause_code)).speed_loss_qty,
       true AS is_estimated, fn_bottleneck_action_line(b.cause_code) AS action_line
  FROM b CROSS JOIN w
 WHERE b.changed_at < w.t AND coalesce(b.next_at, 'infinity'::timestamptz) > w.f
   AND least(coalesce(b.next_at, app_now()), w.t) > greatest(b.changed_at, w.f)
 ORDER BY from_at;

-- 정비 칸 (FR-PRD-02-06·04-05): 구간에 만들었거나 구간 동안 열려 있던 작업지시서 + 짝 작업기록서, 구간에 시작한 간이 작업기록.
--   상태는 보고서 시점(구간 끝) 기준 (report_stops와 같은 규칙)
-- name: report_maintenance
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
)
SELECT 'WORK_ORDER' AS kind, m.wo_no, m.equipment_id, a.alarm_code, m.title,
       CASE WHEN m.cancelled_at <= w.t THEN 'CANCELLED' WHEN m.completed_at <= w.t THEN 'DONE'
            WHEN m.approved_at <= w.t THEN 'IN_PROGRESS' ELSE 'WAITING_APPROVAL' END AS status_at_report,
       r.record_no, r.status AS record_status, r.cause, r.action, m.created_at AS at
  FROM maintenance_work_order m CROSS JOIN w
  LEFT JOIN alarm_event a ON a.alarm_event_id = m.alarm_event_id
  LEFT JOIN work_record r ON r.wo_no = m.wo_no
 WHERE m.created_at < w.t AND coalesce(m.completed_at, m.cancelled_at, 'infinity'::timestamptz) >= w.f
UNION ALL
SELECT 'SIMPLE_RECORD', NULL, r.equipment_id, a.alarm_code, NULL, r.status, r.record_no, r.status, r.cause, r.action, r.start_at
  FROM work_record r CROSS JOIN w
  LEFT JOIN alarm_event a ON a.alarm_event_id = r.alarm_event_id
 WHERE r.record_type = 'SIMPLE' AND r.start_at >= w.f AND r.start_at < w.t
 ORDER BY at;

-- 그날 MTTR (FR-PRD-04-05): 구간 안에서 시작한 정지 등급 DOWN의 분 평균 (DOC-07 §6, 고장 0건이면 NULL = "—")
-- name: report_mttr
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
)
SELECT count(*)::int AS failures,
       round(avg(extract(epoch FROM (coalesce(st.end_at, app_now()) - st.start_at)) / 60), 1) AS mttr_min
  FROM equipment_state_log st CROSS JOIN w
 WHERE st.state_code = 'DOWN' AND st.start_at >= w.f AND st.start_at < w.t;

-- 알람 칸 (FR-PRD-04-04): 등급별 건수(합 = 그날 알람 수), 반복 알람 1·2단계
-- name: report_alarm_counts
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
)
SELECT count(a.alarm_event_id) FILTER (WHERE a.severity_at_event = 'STOP')::int  AS stop_count,
       count(a.alarm_event_id) FILTER (WHERE a.severity_at_event = 'WARN')::int  AS warn_count,
       count(a.alarm_event_id) FILTER (WHERE a.severity_at_event = 'GUIDE')::int AS guide_count,
       count(a.alarm_event_id)::int AS total,
       (SELECT count(*) FROM notification n WHERE n.rule_code = 'REPEAT_ALARM' AND n.raised_at >= w.f AND n.raised_at < w.t)::int AS repeat_stage1,
       (SELECT count(*) FROM notification n WHERE n.rule_code = 'REPEAT_ALARM_2' AND n.raised_at >= w.f AND n.raised_at < w.t)::int AS repeat_stage2
  FROM w LEFT JOIN alarm_event a ON a.occurred_at >= w.f AND a.occurred_at < w.t
 GROUP BY w.f, w.t;

-- 재고 칸 (FR-PRD-04-07): 품목별 오늘 사용량(사용 거래 합)과 부족 품목(재고 ≤ 안전 재고, 완제품 제외)
-- name: report_inventory_usage
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
)
SELECT i.item_no, i.item_name, i.unit, i.category,
       coalesce(-sum(t.qty_change) FILTER (WHERE t.txn_type = 'USE' AND t.txn_at >= w.f AND t.txn_at < w.t), 0) AS used_qty,
       i.on_hand_qty, i.safety_stock,
       (i.category <> 'FINISHED' AND i.safety_stock IS NOT NULL AND i.on_hand_qty <= i.safety_stock) AS is_low
  FROM inventory_item i CROSS JOIN w
  LEFT JOIN inventory_txn t ON t.item_no = i.item_no
 WHERE i.is_active
 GROUP BY i.item_no, i.item_name, i.unit, i.category, i.on_hand_qty, i.safety_stock, w.f, w.t
HAVING coalesce(-sum(t.qty_change) FILTER (WHERE t.txn_type = 'USE' AND t.txn_at >= w.f AND t.txn_at < w.t), 0) > 0
    OR (i.category <> 'FINISHED' AND i.safety_stock IS NOT NULL AND i.on_hand_qty <= i.safety_stock)
 ORDER BY i.item_no;

-- 완제품 한 줄 (FR-PRD-04-07, R-69 ⑧): 시작 / 입고(합격) / 출하 / 조정 / 종료(= 시작 + 입고 − 출하 ± 조정) / 보류 수량(참고)
-- name: report_fg_line
WITH w AS (
    SELECT min(start_at) AS f, max(end_at) AS t, array_agg(shift_id) AS shifts FROM shift
     WHERE shift_id = CAST(:shift_id AS text) OR work_date = CAST(:work_date AS date)
)
SELECT i.item_no,
       coalesce(sum(t.qty_change) FILTER (WHERE t.txn_at < w.f), 0) AS start_qty,
       coalesce(sum(t.qty_change) FILTER (WHERE t.txn_type = 'FG_IN' AND t.txn_at >= w.f AND t.txn_at < w.t), 0) AS in_qty,
       coalesce(-sum(t.qty_change) FILTER (WHERE t.txn_type = 'SHIP_OUT' AND t.txn_at >= w.f AND t.txn_at < w.t), 0) AS ship_qty,
       coalesce(sum(t.qty_change) FILTER (WHERE t.txn_type = 'ADJUST' AND t.txn_at >= w.f AND t.txn_at < w.t), 0) AS adjust_qty,
       coalesce(sum(t.qty_change) FILTER (WHERE t.txn_at < w.t), 0) AS end_qty,
       (SELECT coalesce(sum(v.completed_qty), 0) FROM v_production_lot v WHERE v.status IN ('ON_HOLD','HOLD_REVIEW')) AS hold_qty
  FROM inventory_item i CROSS JOIN w
  LEFT JOIN inventory_txn t ON t.item_no = i.item_no
 WHERE i.category = 'FINISHED'
 GROUP BY i.item_no, w.f, w.t;

-- 교대별 비교 (FR-PRD-04-02): 그날 교대의 총 목표·실적·불량·보고서 상태 (확정 전이면 원기록 집계)
-- name: report_shift_compare
SELECT s.shift_id, s.shift_type, s.target_qty + s.carry_over_qty AS total_target_qty,
       coalesce(r.actual_qty, fn_shift_actual_qty(s.shift_id)) AS actual_qty,
       coalesce(r.defect_qty, (SELECT coalesce(sum(o.sq), 0) FROM operation_report o WHERE o.shift_id = s.shift_id))::int AS defect_qty,
       coalesce(r.status, 'AI_DRAFT') AS report_status
  FROM shift s LEFT JOIN shift_report r USING (shift_id)
 WHERE s.work_date = CAST(:work_date AS date)
 ORDER BY s.start_at;

-- ---------- 화면 → 백엔드 전환 C2 (2026-10-23): 목록·이력 한 번에 ----------
-- 시작했지만 아직 초안이 없는 교대(진행 중·막 끝남)도 미리보기 줄로 함께 (preview = true, 2026-10-24 — 화면 → 백엔드 전환).
-- 미리보기는 저장하지 않는다 — 교대가 끝나면 스케줄러가 진짜 초안을 만든다
-- name: shift_report_list
SELECT r.shift_id, r.status, r.current_version, s.work_date, s.shift_type, s.start_at, s.end_at, s.supervisor_user_id,
       false AS preview, false AS in_progress
  FROM shift_report r JOIN shift s USING (shift_id)
UNION ALL
SELECT s.shift_id, 'AI_DRAFT', 0, s.work_date, s.shift_type, s.start_at, s.end_at, s.supervisor_user_id,
       true AS preview, s.end_at > app_now() AS in_progress
  FROM shift s
 WHERE s.start_at <= app_now() AND s.start_at >= app_now() - interval '2 days'
   AND NOT EXISTS (SELECT 1 FROM shift_report r WHERE r.shift_id = s.shift_id)
 ORDER BY start_at;

-- 교대가 시작했나·진행 중인가 (미리보기)
-- name: shift_started
SELECT s.start_at <= app_now() AS started, s.end_at > app_now() AS in_progress FROM shift s WHERE s.shift_id = :shift_id;

-- 교대 구간 알람 등급별 코드 (교대 보고서 특이 사항 문장 — 2026-10-24)
-- name: report_alarm_codes
WITH w AS (SELECT start_at AS f, least(end_at, app_now()) AS t FROM shift WHERE shift_id = :shift_id)
SELECT a.severity_at_event AS severity, count(*)::int AS n, string_agg(DISTINCT a.alarm_code, ', ' ORDER BY a.alarm_code) AS codes
  FROM alarm_event a CROSS JOIN w WHERE a.occurred_at >= w.f AND a.occurred_at < w.t
 GROUP BY a.severity_at_event;

-- 교대 구간에 걸린 로트 보류 (교대 보고서 특이 사항 문장)
-- name: report_holds
SELECT h.lot_no FROM lot_hold h JOIN shift s ON h.held_at >= s.start_at AND h.held_at < s.end_at
 WHERE s.shift_id = :shift_id ORDER BY h.held_at;

-- name: daily_report_list
SELECT work_date, status, current_version FROM daily_report ORDER BY work_date;

-- 최근 문서 버전 (모든 문서). OPR(OWN)은 자기가 고친 것만
-- name: revisions_recent
SELECT r.revision_id, r.doc_type, r.doc_key, r.version_no, r.author_kind, r.author_user_id, r.created_at, r.reason, r.status_after
  FROM document_revision r
 WHERE CAST(:own_user AS text) IS NULL OR r.author_user_id = CAST(:own_user AS text)
 ORDER BY r.revision_id DESC LIMIT CAST(:limit AS int);

-- name: revision_changes_of
SELECT revision_id, field_name, before_value, after_value FROM document_revision_change
 WHERE revision_id = ANY(string_to_array(CAST(:ids AS text), ',')::bigint[]) ORDER BY revision_id;

-- 사내 문서 조각 (절마다 첫 줄 = "문서 > 1. 제목 > 1.1 제목", 긴 절은 (1/3)처럼 나뉨) — 화면 절 목록으로 다시 모은다
-- name: internal_doc_chunks
SELECT section, chunk_text FROM doc_chunk WHERE doc_no = :doc_no ORDER BY chunk_id;
