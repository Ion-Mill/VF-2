-- 보고서·문서 버전 (PRD-02·04, AST-03)

-- 교대 보고서. target_qty = 총 목표 (목표 + 이월, R-88 — 생산 칸). 이월이 잠정이면 carry_over_is_provisional
-- name: shift_report
SELECT r.*, s.work_date, s.shift_type, s.supervisor_user_id, s.target_qty AS shift_target_qty, s.carry_over_qty,
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

-- name: daily_report_update
UPDATE daily_report SET issues_summary = coalesce(CAST(:issues_summary AS text), issues_summary),
       status = CAST(:status AS varchar), current_version = :version
 WHERE work_date = CAST(:work_date AS date);

-- 잠정 칸(확정 안 된 교대 보고서)이 있으면 MGR [확정] 불가 (R-72)
-- name: daily_report_confirm
UPDATE daily_report d SET status = 'CONFIRMED', confirmed_by = :actor, confirmed_at = app_now()
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
           (d.work_date + 1)::timestamp AT TIME ZONE 'Asia/Seoul' + interval '6 hours',
           d.status IN ('AI_DRAFT','EDITING') AND CAST(:role AS text) = 'MGR'
      FROM daily_report d
    UNION ALL
    SELECT 'PM_RECORD', p.pm_record_id::text, t.item_name, p.status, t.equipment_id, p.done_at,
           p.status = 'EDITING' AND p.recorded_by = CAST(:user_id AS text)
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
