-- 정비: 작업지시서·작업기록서·예방 정비 (MNT-03·04·05)

-- 작업지시서 목록 (MNT-02): 상태, 내 것만(담당 = 나)
-- name: wo_list
SELECT wo_no, equipment_id, alarm_event_id, trigger_kind, title, status, assignee_user_id, approved_by, approved_at,
       created_at, completed_at, approval_wait_min, current_version
  FROM v_work_order
 WHERE (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
   AND (CAST(:assignee AS text) IS NULL OR assignee_user_id = CAST(:assignee AS text))
 ORDER BY created_at DESC LIMIT CAST(:limit AS int);

-- name: wo_get
SELECT * FROM v_work_order WHERE wo_no = :wo_no;

-- name: wo_steps
SELECT step_no, step_text, source_section FROM work_order_step WHERE wo_no = :wo_no ORDER BY step_no;

-- name: wo_parts
SELECT p.item_no, i.item_name, i.unit, p.suggested_qty, i.on_hand_qty FROM work_order_part p JOIN inventory_item i USING (item_no)
 WHERE p.wo_no = :wo_no ORDER BY p.item_no;

-- 작성자(:author)가 비면 AI비서 초안, 있으면 보전 담당자가 직접 (수정 중에서 시작)
-- name: wo_create_draft
SELECT fn_create_work_order_draft(:equipment_id, :title, :symptom, CAST(:alarm_event_id AS bigint),
       CAST(:trigger_notification_id AS bigint), CAST(:pm_record_id AS bigint), CAST(:steps AS jsonb), CAST(:parts AS jsonb),
       CAST(:lot_no AS text), NULL, CAST(:author AS text)) AS wo_no;

-- name: wo_update_content
UPDATE maintenance_work_order
   SET title = coalesce(CAST(:title AS varchar), title), symptom = coalesce(CAST(:symptom AS text), symptom),
       status = CASE WHEN status = 'AI_DRAFT' THEN 'EDITING' ELSE status END, current_version = :version
 WHERE wo_no = :wo_no;

-- name: wo_assign
UPDATE maintenance_work_order SET assignee_user_id = :assignee WHERE wo_no = :wo_no AND status IN ('AI_DRAFT','EDITING');

-- name: wo_approve
UPDATE maintenance_work_order SET status = 'APPROVED', approved_by = :actor, approved_at = app_now()
 WHERE wo_no = :wo_no AND status = 'EDITING';

-- 담당 MNT가 작업지시서를 열면 배정 알림 자동 처리 (6.36 WO_ASSIGNED)
-- name: wo_assigned_seen
SELECT fn_auto_process(ARRAY(SELECT notification_id FROM notification
                              WHERE rule_code = 'WO_ASSIGNED' AND wo_no = :wo_no AND NOT is_processed), :actor) AS processed;

-- name: wo_start
UPDATE maintenance_work_order SET status = 'IN_PROGRESS' WHERE wo_no = :wo_no AND status = 'APPROVED';

-- name: wo_cancel
UPDATE maintenance_work_order SET status = 'CANCELLED', cancelled_by = :actor, cancelled_at = app_now(), cancel_reason = :reason
 WHERE wo_no = :wo_no AND status IN ('AI_DRAFT','EDITING','APPROVED');

-- name: wr_list
SELECT w.record_no, w.record_type, w.wo_no, w.alarm_event_id, a.alarm_code, w.cause_check_notification_id, w.equipment_id, w.status,
       w.confirmed_by, w.confirmed_at, w.checked_by, w.start_at, w.end_at, w.repair_min, w.current_version
  FROM work_record w LEFT JOIN alarm_event a ON a.alarm_event_id = w.alarm_event_id
 WHERE (CAST(:record_type AS text) IS NULL OR w.record_type = CAST(:record_type AS text))
   AND (CAST(:status AS text) IS NULL OR w.status = CAST(:status AS text))
   AND (CAST(:equipment_id AS text) IS NULL OR w.equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:alarm_code AS text) IS NULL OR a.alarm_code = CAST(:alarm_code AS text))
 ORDER BY w.start_at DESC LIMIT CAST(:limit AS int);

-- name: wr_get
SELECT * FROM work_record WHERE record_no = :record_no;

-- name: wr_checks
SELECT check_seq, check_kind, wo_no, step_no, loto_step_code, is_checked, checked_by, checked_at,
       (SELECT name_ko FROM code_label WHERE code_group = 'work_record_check.loto_step_code' AND code = c.loto_step_code) AS loto_title
  FROM work_record_check c WHERE record_no = :record_no ORDER BY check_seq;

-- name: wr_parts
SELECT p.item_no, i.item_name, i.unit, p.qty, p.proposed_by_kind FROM work_record_part p JOIN inventory_item i USING (item_no)
 WHERE p.record_no = :record_no;

-- 작업기록서 만들기 (작업지시서 1건 = 작업기록서 1건). 잠금·표지 9단계 + 작업 순서 체크칸을 함께 만든다
-- name: wr_create_full
WITH wo AS (SELECT * FROM maintenance_work_order WHERE wo_no = :wo_no),
ins AS (
    INSERT INTO work_record (record_no, record_type, wo_no, alarm_event_id, equipment_id, lot_no, cause, action, worker_memo,
                             start_at, safety_block_required, status, current_version)
    SELECT fn_next_doc_no('MR', app_now()), 'FULL', wo.wo_no, wo.alarm_event_id, wo.equipment_id, wo.lot_no,
           CAST(:cause AS text), coalesce(CAST(:action AS text), ''), CAST(:worker_memo AS text),
           coalesce(CAST(:start_at AS timestamptz), app_now()), true, CAST(:status AS varchar), 0
      FROM wo RETURNING record_no, wo_no),
loto AS (
    INSERT INTO work_record_check (record_no, check_seq, check_kind, loto_step_code)
    SELECT ins.record_no, ord, 'LOTO', s FROM ins,
           unnest(ARRAY['6.1','6.2','6.3','6.4','6.5','6.6','7.1','7.2','7.3']) WITH ORDINALITY AS x(s, ord)
    RETURNING 1),
steps AS (
    INSERT INTO work_record_check (record_no, check_seq, check_kind, wo_no, step_no)
    SELECT ins.record_no, 9 + st.step_no, 'STEP', st.wo_no, st.step_no FROM ins JOIN work_order_step st USING (wo_no)
    RETURNING 1)
SELECT record_no, (SELECT count(*) FROM loto) + (SELECT count(*) FROM steps) AS checks FROM ins;

-- 간이 작업기록 (주의 등급 알람·다른 공정 알람·다른 공정 원인 점검 요청). AI비서 초안 없음 — 사람이 처음 저장
-- name: wr_create_simple
INSERT INTO work_record (record_no, record_type, alarm_event_id, cause_check_notification_id, equipment_id, lot_no, action,
                         worker_memo, start_at, safety_block_required, status, current_version)
VALUES (fn_next_doc_no('MR-S', app_now()), 'SIMPLE', CAST(:alarm_event_id AS bigint), CAST(:cause_check_notification_id AS bigint),
        :equipment_id, CAST(:lot_no AS text), :action, CAST(:worker_memo AS text), coalesce(CAST(:start_at AS timestamptz), app_now()),
        :safety_block_required, 'EDITING', 0)
RETURNING record_no, safety_block_required;

-- name: wr_add_loto
INSERT INTO work_record_check (record_no, check_seq, check_kind, loto_step_code)
SELECT :record_no, ord, 'LOTO', s FROM unnest(ARRAY['6.1','6.2','6.3','6.4','6.5','6.6','7.1','7.2','7.3']) WITH ORDINALITY AS x(s, ord)
ON CONFLICT DO NOTHING;

-- name: wr_update_content
UPDATE work_record
   SET cause = coalesce(CAST(:cause AS text), cause), action = coalesce(CAST(:action AS text), action),
       worker_memo = coalesce(CAST(:worker_memo AS text), worker_memo),
       end_at = coalesce(CAST(:end_at AS timestamptz), end_at), repair_min = coalesce(CAST(:repair_min AS numeric), repair_min),
       status = CASE WHEN status = 'AI_DRAFT' THEN 'EDITING' WHEN status = 'CHECKED' THEN 'CONFIRMED' ELSE status END,
       checked_by = CASE WHEN status = 'CHECKED' THEN NULL ELSE checked_by END,
       checked_at = CASE WHEN status = 'CHECKED' THEN NULL ELSE checked_at END,
       current_version = :version
 WHERE record_no = :record_no;

-- name: wr_set_part
INSERT INTO work_record_part (record_no, item_no, qty, proposed_by_kind) VALUES (:record_no, :item_no, :qty, :proposed_by_kind)
ON CONFLICT (record_no, item_no) DO UPDATE SET qty = EXCLUDED.qty, proposed_by_kind = EXCLUDED.proposed_by_kind;

-- name: wr_check_item
UPDATE work_record_check SET is_checked = :is_checked,
       checked_by = CASE WHEN :is_checked THEN CAST(:actor AS varchar) END,
       checked_at = CASE WHEN :is_checked THEN app_now() END
 WHERE record_no = :record_no AND check_seq = :check_seq;

-- name: wr_confirm
SELECT fn_confirm_work_record(:record_no, :actor);

-- name: wr_sup_check
UPDATE work_record SET status = 'CHECKED', checked_by = :actor, checked_at = app_now()
 WHERE record_no = :record_no AND record_type = 'FULL' AND status = 'CONFIRMED';

-- name: pm_schedule
SELECT d.pm_task_id, d.equipment_id, d.doc04_section, d.area, d.item_name, d.cycle_code, d.lockout_level, d.default_role,
       d.default_item_no, d.on_calendar, d.source_tag, d.last_done_at, d.next_due_date,
       (CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) - d.next_due_date) AS days_overdue
  FROM v_pm_task_due d
 WHERE d.is_active AND (CAST(:equipment_id AS text) IS NULL OR d.equipment_id = CAST(:equipment_id AS text))
 ORDER BY d.next_due_date NULLS LAST, d.pm_task_id;

-- 제때 실시율 (PM-01, FR-MNT-04-07, DOC-04 실시율 목표 90%): 기간(기본 최근 30일) 안 기한이 온 항목 중 기한 안에 한 것의 비율 (설비별 + 라인 합)
-- name: pm_on_time
-- 2026-10-20: 분모 = 기한이 온 항목 전부 (실시 기록 + 안 한 채 기한이 지난 항목 — 전에는 실시한 것만 세서 안 하면 100%가 됐다).
--   안 한 항목 = 구간 안 기한(v_pm_task_due의 next_due_date)이 지났는데 그 기한 뒤 실시 기록이 없는 정비 항목. 맨 끝 줄 equipment_id NULL = 라인 합
WITH d AS (
    SELECT coalesce(CAST(:from AS date), CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) - 30) AS f,
           coalesce(CAST(:to AS date), CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date)) AS t,
           CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) AS today
), x AS (
    SELECT t.equipment_id, CAST(r.done_at AT TIME ZONE 'Asia/Seoul' AS date) <= r.due_date AS on_time, true AS done
      FROM pm_record r JOIN pm_task t USING (pm_task_id), d
     WHERE r.status IN ('CONFIRMED','REVISED') AND r.due_date BETWEEN d.f AND d.t
    UNION ALL
    SELECT v.equipment_id, false, false
      FROM v_pm_task_due v, d
     WHERE v.is_active AND v.next_due_date BETWEEN d.f AND least(d.t, d.today - 1)
       AND NOT EXISTS (SELECT 1 FROM pm_record r WHERE r.pm_task_id = v.pm_task_id AND r.due_date = v.next_due_date
                         AND r.status IN ('CONFIRMED','REVISED'))
), g AS (
    SELECT equipment_id, count(*) FILTER (WHERE done)::int AS done_count, count(*) FILTER (WHERE NOT done)::int AS missed_count,
           count(*)::int AS due_count, count(*) FILTER (WHERE on_time)::int AS on_time_count
      FROM x WHERE CAST(:equipment_id AS text) IS NULL OR equipment_id = CAST(:equipment_id AS text)
     GROUP BY GROUPING SETS ((equipment_id), ())
)
SELECT equipment_id, done_count, missed_count, due_count, on_time_count,
       round(100.0 * on_time_count / nullif(due_count, 0), 1) AS on_time_pct
  FROM g ORDER BY equipment_id NULLS LAST;

-- name: pm_record_create
INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, measured_value, measured_unit, memo, status, current_version)
VALUES (:pm_task_id, :due_date, coalesce(CAST(:done_at AS timestamptz), app_now()), :done_by, :actor, :result,
        CAST(:measured_value AS numeric), CAST(:measured_unit AS varchar), CAST(:memo AS text), 'DRAFT', 0)
RETURNING pm_record_id;

-- 예방 정비 확정: 상태 확정 + 쓴 소모품 재고 차감 (FR-MNT-04-06) + 기한 알림 자동 처리
-- name: pm_record_confirm
WITH r AS (
    UPDATE pm_record SET status = 'CONFIRMED' WHERE pm_record_id = :pm_record_id AND status = 'DRAFT'
    RETURNING pm_record_id, pm_task_id, recorded_by),
use AS (
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, pm_record_id)
    SELECT t.default_item_no, 'USE', -CAST(:used_qty AS numeric), app_now(), r.recorded_by, 'PM_RECORD', r.pm_record_id
      FROM r JOIN pm_task t USING (pm_task_id)
     WHERE t.default_item_no IS NOT NULL AND coalesce(CAST(:used_qty AS numeric), 0) > 0
    RETURNING 1),
done AS (
    SELECT fn_auto_process(ARRAY(SELECT notification_id FROM notification n, r
                                  WHERE n.pm_task_id = r.pm_task_id AND n.rule_code IN ('PM_DUE_SOON','PM_OVERDUE') AND NOT n.is_processed),
                           :actor) AS n)
SELECT (SELECT count(*) FROM r) AS confirmed, (SELECT count(*) FROM use) AS stock_used, (SELECT n FROM done) AS processed;

-- [정비 시작]·[정비 끝 · 실시 기록] (FR-MNT-04-10, API-PM-02 — 2026-10-20): MAINT 구간 = 기록 버튼 사이 (설비로 가는 명령 없음)
-- name: pm_start
SELECT fn_pm_start(:pm_task_id, :actor, CAST(:due_date AS date)) AS pm_record_id;

-- name: pm_end
SELECT fn_pm_end(:pm_record_id, :actor, coalesce(CAST(:result AS text), 'NORMAL'), CAST(:measured_value AS numeric),
                 CAST(:measured_unit AS text), CAST(:memo AS text)) AS state_log_id;

-- name: pm_open_maint
SELECT s.state_log_id, s.equipment_id, s.start_at FROM equipment_state_log s
 WHERE s.pm_record_id = :pm_record_id AND s.state_code = 'MAINT' AND s.end_at IS NULL;

-- 메모 정리(MNT-10)에 넘기는 재료 (2026-10-20): 그 기록의 알람 번호, 사용 부품을 고를 재고 품목(공구·소모품)
-- name: wr_alarm_code
SELECT a.alarm_code FROM work_record w
  LEFT JOIN maintenance_work_order o ON o.wo_no = w.wo_no
  JOIN alarm_event a ON a.alarm_event_id = coalesce(w.alarm_event_id, o.alarm_event_id)
 WHERE w.record_no = :record_no;

-- name: assist_items
SELECT item_no, item_name FROM inventory_item WHERE category IN ('TOOL','CONSUMABLE') AND is_active ORDER BY item_no;

-- ---------- 정비 이력 한 번에 (2026-10-23, 화면 → 백엔드 전환 C2) — 실시간 구간 앞(과거 기록)만: 지침카드 예상 부품·지난 조치 ----------
-- name: history_work_orders
SELECT w.*, array_to_string(v.trigger_kind::text[], '|') AS trigger_kind
  FROM maintenance_work_order w LEFT JOIN v_work_order v USING (wo_no)
 WHERE w.created_at < CAST(:before AS timestamptz) ORDER BY w.wo_no;

-- name: history_steps
SELECT s.* FROM work_order_step s JOIN maintenance_work_order w USING (wo_no)
 WHERE w.created_at < CAST(:before AS timestamptz) ORDER BY s.wo_no, s.step_no;

-- name: history_work_records
SELECT * FROM work_record WHERE start_at < CAST(:before AS timestamptz) ORDER BY record_no;

-- name: history_checks
SELECT c.* FROM work_record_check c JOIN work_record r USING (record_no)
 WHERE r.start_at < CAST(:before AS timestamptz) ORDER BY c.record_no, c.check_seq;

-- name: history_parts
SELECT p.* FROM work_record_part p JOIN work_record r USING (record_no)
 WHERE r.start_at < CAST(:before AS timestamptz) ORDER BY p.record_no, p.item_no;

-- name: history_alarms
SELECT * FROM alarm_event WHERE occurred_at < CAST(:before AS timestamptz) ORDER BY alarm_event_id;

-- 예방 정비 화면: 오늘 기록·지금 열린 정비(MAINT) 구간
-- name: pm_today_records
SELECT r.* FROM pm_record r
 WHERE r.done_at >= date_trunc('day', app_now() AT TIME ZONE 'Asia/Seoul') AT TIME ZONE 'Asia/Seoul' OR r.status = 'DRAFT'
 ORDER BY r.pm_record_id;

-- name: pm_open_windows
SELECT equipment_id, start_at, end_at, 'MAINT' AS kind FROM equipment_state_log
 WHERE state_code = 'MAINT' AND start_at <= app_now() AND coalesce(end_at, 'infinity') > app_now()
 ORDER BY start_at;
