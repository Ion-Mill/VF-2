-- 알람·설비 상태·지침카드 재료 (MNT-02, PRD-01)

-- name: ingest
SELECT fn_ingest_alarm(:equipment_id, :alarm_code, CAST(:occurred_at AS timestamptz), CAST(:lot_no AS text),
                       CAST(:prev_alarm_event_id AS bigint), coalesce(CAST(:is_injected AS boolean), false),
                       CAST(:scenario_code AS text)) AS alarm_event_id;

-- name: clear
UPDATE alarm_event SET cleared_at = coalesce(CAST(:cleared_at AS timestamptz), app_now())
 WHERE alarm_event_id = :alarm_event_id AND cleared_at IS NULL;

-- handled_by·handled_at = 이 알람의 작업기록서(직접 또는 작업지시서를 거쳐)가 확정·확인된 사람·시각 (2026-10-25).
--   화면이 작업기록서를 못 읽는 역할(작업자)이나 기록서보다 트윈을 먼저 받은 때에도 이미 처리된 알람을 긴급으로 띄우지 않게
-- name: list
SELECT a.alarm_event_id, a.equipment_id, a.alarm_code, m.name_ko, a.severity_at_event, a.occurred_at, a.cleared_at, a.lot_no,
       a.prev_alarm_event_id, a.is_injected, a.scenario_code, h.confirmed_by AS handled_by, h.confirmed_at AS handled_at
  FROM alarm_event a JOIN alarm_master m USING (alarm_code)
  LEFT JOIN LATERAL (SELECT r.confirmed_by, r.confirmed_at FROM work_record r LEFT JOIN maintenance_work_order w ON w.wo_no = r.wo_no
                      WHERE r.status IN ('CONFIRMED', 'CHECKED') AND (r.alarm_event_id = a.alarm_event_id OR w.alarm_event_id = a.alarm_event_id)
                      ORDER BY r.confirmed_at LIMIT 1) h ON true
 WHERE a.occurred_at >= CAST(:from AS timestamptz) AND a.occurred_at < CAST(:to AS timestamptz)
   AND (CAST(:equipment_id AS text) IS NULL OR a.equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:alarm_code AS text) IS NULL OR a.alarm_code = CAST(:alarm_code AS text))
 ORDER BY a.occurred_at DESC LIMIT CAST(:limit AS int);

-- name: get
SELECT a.*, m.name_ko, m.name_en, m.easy_desc, m.responder, m.responder_note, m.lockout_level, m.chain_rule, m.doc02_section
  FROM alarm_event a JOIN alarm_master m USING (alarm_code) WHERE a.alarm_event_id = :alarm_event_id;

-- 지침카드 재료 (FR-MNT-02): 알람 번호로 코드집을 정확히 찾고(FR-MNT-02-02), 고장 대응 절·차단 지점·지난 기록을 붙인다.
-- 원문 출처(source_ref)는 내보내지 않는다 (R-85)
-- name: guide_card
SELECT a.alarm_event_id, a.equipment_id, a.alarm_code, a.severity_at_event, a.occurred_at, a.lot_no,
       m.name_ko, m.name_en, m.easy_desc, m.responder, m.responder_note, m.lockout_level, m.chain_rule,
       -- 연쇄 알람 (2026-10-20): 앞 알람 번호와 그 알람 (예: 108 → 994 → 992에서 992의 앞 = 994)
       a.prev_alarm_event_id,
       (SELECT jsonb_build_object('alarm_event_id', p.alarm_event_id, 'alarm_code', p.alarm_code, 'occurred_at', p.occurred_at,
                                  'severity', p.severity_at_event)
          FROM alarm_event p WHERE p.alarm_event_id = a.prev_alarm_event_id) AS prev_alarm,
       -- 이 알람의 작업지시서 ([작업지시서 열기] 버튼, 2026-10-20). 없으면 NULL
       (SELECT jsonb_build_object('wo_no', o.wo_no, 'status', o.status, 'assignee_user_id', o.assignee_user_id)
          FROM maintenance_work_order o WHERE o.alarm_event_id = a.alarm_event_id) AS work_order,
       'DOC-02 ' || m.doc02_section AS code_source,
       (SELECT coalesce(jsonb_agg(jsonb_build_object('doc_no', g.doc_no, 'doc_name', d.doc_name, 'section', g.section) ORDER BY g.seq), '[]')
          FROM alarm_guide_map g JOIN internal_doc d USING (doc_no) WHERE g.alarm_code = a.alarm_code) AS guide_sections,
       (SELECT coalesce(jsonb_agg(jsonb_build_object('id', i.isolation_point_id, 'name', i.point_name, 'energy', i.energy_type,
                                                     'location', i.location, 'lock_method', i.lock_method) ORDER BY i.seq), '[]')
          FROM isolation_point i WHERE i.equipment_id = a.equipment_id) AS isolation_points,
       (SELECT jsonb_build_object('record_no', w.record_no, 'action', w.action, 'confirmed_at', w.confirmed_at)
          FROM work_record w JOIN alarm_event x ON x.alarm_event_id = w.alarm_event_id
         WHERE x.equipment_id = a.equipment_id AND x.alarm_code = a.alarm_code AND w.status IN ('CONFIRMED','CHECKED')
         ORDER BY w.confirmed_at DESC LIMIT 1) AS last_record,
       (SELECT jsonb_build_object('state_code', s.state_code, 'since', s.start_at,
                                  'minutes', round(extract(epoch FROM (app_now() - s.start_at)) / 60, 1),
                                  'loss_qty_est', round(extract(epoch FROM (app_now() - s.start_at)) / 60 / nullif(e.std_cycle_min, 0), 1))
          FROM equipment_state_log s JOIN equipment e USING (equipment_id)
         WHERE s.alarm_event_id = a.alarm_event_id) AS production_impact,
       (SELECT 'DOC-05 ' || current_rev FROM internal_doc WHERE doc_no = 'DOC-05') AS safety_block_doc_rev
  FROM alarm_event a JOIN alarm_master m USING (alarm_code) WHERE a.alarm_event_id = :alarm_event_id;

-- name: same_cases
SELECT w.record_no, w.record_type, a.alarm_event_id, a.occurred_at, w.cause, w.action, w.repair_min, w.confirmed_at
  FROM work_record w JOIN alarm_event a ON a.alarm_event_id = w.alarm_event_id
 WHERE a.alarm_code = :alarm_code AND (CAST(:equipment_id AS text) IS NULL OR a.equipment_id = CAST(:equipment_id AS text))
   AND w.status IN ('CONFIRMED','CHECKED')
 ORDER BY a.occurred_at DESC LIMIT 20;

-- 정지 구간 목록 + 비서 추천 사유 (LINE-07): 기간 또는 교대(shift_id), 설비, 미확정만
-- name: state_logs
SELECT l.state_log_id, l.equipment_id, l.state_code, l.mtconnect_execution, l.start_at, l.end_at, l.duration_min, l.warn_marker,
       l.reason_suggested_code, l.reason_code, l.reason_status, l.reason_entered_by, l.reason_confirmed_by, l.reason_confirmed_at,
       l.alarm_event_id, l.pm_record_id, l.stop_loss_qty
  FROM equipment_state_log l
  LEFT JOIN shift s ON s.shift_id = CAST(:shift_id AS text)
 WHERE l.start_at < coalesce(s.end_at, CAST(:to AS timestamptz))
   AND coalesce(l.end_at, 'infinity') > coalesce(s.start_at, CAST(:from AS timestamptz))
   AND (CAST(:shift_id AS text) IS NULL OR s.shift_id IS NOT NULL)
   AND (CAST(:equipment_id AS text) IS NULL OR l.equipment_id = CAST(:equipment_id AS text))
   AND (CAST(:pending_only AS boolean) IS NOT TRUE OR (l.state_code <> 'RUN' AND l.reason_status IS DISTINCT FROM 'CONFIRMED'))
 ORDER BY l.start_at;

-- name: state_log_get
SELECT state_log_id, equipment_id, state_code, start_at, end_at, duration_min, reason_suggested_code, reason_code, reason_status,
       reason_entered_by, reason_confirmed_by, reason_confirmed_at, stop_loss_qty
  FROM equipment_state_log WHERE state_log_id = :state_log_id;

-- name: reason_input
UPDATE equipment_state_log SET reason_code = :reason_code, reason_status = 'ENTERED', reason_entered_by = :actor
 WHERE state_log_id = :state_log_id AND state_code <> 'RUN' AND reason_status IS DISTINCT FROM 'CONFIRMED';

-- name: reason_confirm
UPDATE equipment_state_log
   SET reason_code = coalesce(CAST(:reason_code AS varchar), reason_code), reason_status = 'CONFIRMED',
       reason_confirmed_by = :actor, reason_confirmed_at = app_now()
 WHERE state_log_id = :state_log_id AND state_code <> 'RUN';
