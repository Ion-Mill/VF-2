-- 알림·브리핑·보고 순위 (AST-01·02, 6.36·6.43)

-- 알림 목록 (NTF-01): 받은 알림 (MGR은 전부). 처리 상태(open/processed/all)·중요도·설비로 거르고, 최근 순 또는 보고 순위 순.
-- 보고 순위: 24시간 넘게 처리 안 된 주의 알림은 0-1 (DOC-07 §10.5). 카드 칸: ×N 묶음(repeat_count), 폭주(is_flood),
-- 관련 정보 한 줄(related_info), 처리할 역할(processor_roles), 전달 방식(delivery_kind — POPUP 팝업 / BUBBLE 말풍선 / LIST 목록,
-- 2026-10-13). 칸(:kind): fault = 고장·확인 알림(팝업·목록), doc = 문서 알림(말풍선). 문서 알림은 열 문서(doc_type·doc_key)
-- name: mine
WITH x AS (
    SELECT n.notification_id, n.rule_code, r.rule_name, n.importance, n.raised_at, n.message, n.related_info, n.message_source,
           n.repeat_count, n.is_flood, n.is_processed, n.process_kind, n.processed_by, n.processed_at, n.process_memo,
           n.alarm_event_id, n.equipment_id, n.lot_no, n.item_no, n.pm_task_id, n.tool_id, n.wo_no, n.bottleneck_log_id,
           n.revision_id, n.result_id, n.shift_id, n.buffer_code, n.cmm_import_id, n.repeat_stage_status,
           r.process_mode, r.processor_roles, r.rank_group, r.delivery_kind, nr.popup_sound, nr.read_at,
           CASE WHEN n.wo_no IS NOT NULL AND r.delivery_kind = 'BUBBLE' THEN 'WORK_ORDER'
                WHEN n.rule_code = 'SHIFT_REPORT_PENDING' THEN 'SHIFT_REPORT' ELSE v.doc_type END AS doc_type,
           CASE WHEN n.wo_no IS NOT NULL AND r.delivery_kind = 'BUBBLE' THEN n.wo_no
                WHEN n.rule_code = 'SHIFT_REPORT_PENDING' THEN n.shift_id ELSE v.doc_key END AS doc_key,
           (NOT n.is_processed AND n.importance = 'CAUTION' AND n.raised_at < app_now() - interval '24 hours') AS is_stale,
           r.report_rank AS rule_rank
      FROM notification n JOIN notification_rule r USING (rule_code)
      LEFT JOIN notification_recipient nr ON nr.notification_id = n.notification_id AND nr.user_id = :user_id
      LEFT JOIN document_revision v ON v.revision_id = n.revision_id
     WHERE (nr.user_id IS NOT NULL OR CAST(:all_visible AS boolean))
       AND (CAST(:kind AS text) IS NULL OR (CAST(:kind AS text) = 'doc') = (r.delivery_kind = 'BUBBLE'))
       AND (CAST(:status AS text) = 'all' OR (CAST(:status AS text) = 'processed') = n.is_processed)
       AND (CAST(:importance AS text) IS NULL OR n.importance = CAST(:importance AS text))
       AND (CAST(:equipment_id AS text) IS NULL OR n.equipment_id = CAST(:equipment_id AS text))
), y AS (
    SELECT x.*, CASE WHEN x.is_stale THEN 'R0_1' ELSE x.rule_rank END AS report_rank,
           CASE WHEN x.is_stale THEN 1 ELSE CASE x.rule_rank WHEN 'R1' THEN 2 WHEN 'R2' THEN 3 WHEN 'R3' THEN 4 ELSE 5 END END
               AS rank_order
      FROM x
)
SELECT y.* FROM y
 ORDER BY CASE WHEN CAST(:sort AS text) = 'rank' THEN y.rank_order ELSE 0 END,
          CASE WHEN CAST(:sort AS text) = 'rank' THEN y.rank_group ELSE 0 END,
          CASE WHEN CAST(:sort AS text) = 'rank' THEN extract(epoch FROM y.raised_at) ELSE -extract(epoch FROM y.raised_at) END
 LIMIT CAST(:limit AS int);

-- name: get
SELECT n.*, r.rule_name, r.process_mode, r.processor_roles, r.delivery_kind FROM notification n JOIN notification_rule r USING (rule_code)
 WHERE n.notification_id = :notification_id;

-- name: process
SELECT fn_process_notification(:notification_id, :actor, CAST(:memo AS text));

-- 읽음 표시. 문서 수정 알림(DOC_REVISED)은 받은 사람이 열면 처리된다 (6.36 처리 표)
-- 긴급 팝업 확인 (NTF-04): 소리 끔·읽음. 처리는 아님 (받는 사람 본인만)
-- name: ack
UPDATE notification_recipient SET popup_sound = false, read_at = coalesce(read_at, app_now())
 WHERE notification_id = :notification_id AND user_id = :user_id;

-- name: read
WITH r AS (
    UPDATE notification_recipient SET read_at = coalesce(read_at, app_now())
     WHERE notification_id = :notification_id AND user_id = :user_id
    RETURNING notification_id
)
SELECT (SELECT count(*) FROM r)::int AS updated,
       fn_auto_process(ARRAY(SELECT n.notification_id FROM notification n JOIN r USING (notification_id)
                              WHERE n.rule_code = 'DOC_REVISED'), :user_id) AS processed;

-- 보고 순위 화면 줄 (FR-AST-COM-21): 같은 설비·같은 원인은 한 줄(member_count·members), 개수를 자르지 않음.
-- 머리의 "전체 N건"과 순위별 건수는 이 줄 수로 센다 (count_bucket — 0-1 오래 방치는 주의)
-- name: report_lines
SELECT line_key, report_rank, rank_order, rank_group, count_bucket, item_kind, notification_id, rule_code, equipment_id,
       process_code, lot_no, title, occurred_at, member_count, members
  FROM v_report_lines ORDER BY rank_order, rank_group, sort_value DESC NULLS LAST, occurred_at;

-- 브리핑 "지난 교대" (FR-AST-01-03 ① 양품·손실 ② 설명 ③ 나머지). 확정 전이면 잠정 (FR-AST-02-17).
-- 주간이면 야간으로 넘긴 이월, 야간이면 그날 하루 부족(180 − 하루 실적, 다음 날로 넘기지 않음 — R-88)
-- (shift_id를 주면 그 교대의 앞 교대)
-- name: briefing_prev_shift
SELECT p.shift_id, p.work_date, p.shift_type, p.total_target_qty, p.actual_qty AS good_qty, p.defect_qty,
       p.failure_loss_qty, p.speed_loss_qty, p.loss_qty, p.loss_is_estimated, NOT p.is_report_confirmed AS is_provisional,
       (SELECT count(*) FROM equipment_state_log st
         WHERE st.state_code = 'DOWN' AND st.start_at >= p.start_at AND st.start_at < p.end_at)::int AS failure_stops,
       CASE WHEN p.shift_type = 'DAY'
            THEN (SELECT n.carry_over_qty FROM shift n WHERE n.work_date = p.work_date AND n.shift_type = 'NIGHT') END
                                                                                                AS carried_over_qty,
       CASE WHEN p.shift_type = 'NIGHT'
            THEN greatest(0, d.daily_target_qty - (SELECT sum(x.actual_qty) FROM v_shift_progress x
                                                     WHERE x.work_date = p.work_date))::int END AS day_shortfall_qty
  FROM v_shift_progress p JOIN work_day d USING (work_date)
 WHERE p.end_at <= coalesce((SELECT s.start_at FROM shift s WHERE s.shift_id = CAST(:shift_id AS text)), app_now())
 ORDER BY p.end_at DESC LIMIT 1;

-- 브리핑 "이번 교대" (FR-AST-01-03 ① 총 N개 (목표 90 + 이월 N) ② 작업지시·로트 ③ 예방 정비).
-- shift_id, 비우면 지금 교대, 교대 사이면 다음에 시작할 교대. 작업자 요약형은 담당 공정(두 칸) 설비의 예방 정비만 (:process_codes 쉼표)
-- name: briefing_this_shift
SELECT p.shift_id, p.work_date, p.shift_type, p.start_at, p.end_at, p.target_qty, p.carry_over_qty, p.total_target_qty,
       p.carry_over_is_provisional,
       (SELECT string_agg(o.order_no, ',' ORDER BY o.order_no) FROM production_order o
         WHERE o.status IN ('WAITING','IN_PROGRESS'))                                          AS open_order_nos,
       (SELECT string_agg(l.lot_no, ',' ORDER BY l.lot_no) FROM production_lot l
         WHERE l.input_shift_id = p.shift_id)                                                  AS lot_nos,
       (SELECT coalesce(jsonb_agg(jsonb_build_object('pm_task_id', d.pm_task_id, 'equipment_id', d.equipment_id,
                                                     'item_name', d.item_name, 'next_due_date', d.next_due_date)
                                  ORDER BY d.next_due_date, d.equipment_id), '[]'::jsonb)
          FROM v_pm_task_due d JOIN equipment e USING (equipment_id)
         WHERE d.is_active AND d.on_calendar AND d.next_due_date <= CAST(p.start_at AT TIME ZONE 'Asia/Seoul' AS date)
           AND (CAST(:process_codes AS text) IS NULL
                OR e.process_code = ANY (string_to_array(CAST(:process_codes AS text), ','))))  AS pm_due
  FROM v_shift_progress p
 WHERE (CAST(:shift_id AS text) IS NULL AND p.end_at > app_now()) OR p.shift_id = CAST(:shift_id AS text)
 ORDER BY p.start_at LIMIT 1;

-- name: rules
SELECT rule_code, rule_name, condition_text, importance, is_enabled, process_mode, processor_roles, recipient_roles,
       report_rank, rank_group, updated_by, updated_at FROM notification_rule ORDER BY report_rank, rank_group, rule_code;

-- name: rule_update
UPDATE notification_rule SET is_enabled = coalesce(CAST(:is_enabled AS boolean), is_enabled),
       condition_text = coalesce(CAST(:condition_text AS text), condition_text),
       updated_by = :actor, updated_at = app_now()
 WHERE rule_code = :rule_code;

-- 비서 문장으로 바꾸기 (규칙이 정한 알림의 문장만 — 알릴지 말지는 바꾸지 않음, R-38)
-- name: set_message
UPDATE notification SET message = :message, message_source = 'ASSISTANT' WHERE notification_id = :notification_id;

-- 이 사용자가 받은 알림인가 (알림 1건 보기·읽음 — NTF-01·02 "자기 역할분 / 받는 사람", MGR은 전부 보기, 실시간 알림 거르기)
-- name: is_recipient
SELECT EXISTS (SELECT 1 FROM notification_recipient WHERE notification_id = :notification_id AND user_id = :user_id);
