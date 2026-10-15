-- =====================================================================
-- 20_report_functions.sql (views 단계에서 만든다 — v_report_items 등 뷰를 쓰므로) — 교대·일일 보고서 AI비서 초안의 "숫자 칸" 만들기 (PRD-02·04, R-12·R-46·R-54·R-72·R-73)
-- 숫자는 프로그램이 계산한다 (FR-AST-COM-05). 문장 칸(특이 사항·오늘의 문제 문장)은 AI 비서 ②가
-- 나중에 같은 버전 안에서 채우거나, 비서가 꺼져 있으면 기본 문구로 둔다.
-- 생성 시각 (R-72, 2026-10-13): 교대 보고서 = 교대 끝(17:00·05:00) + 그 교대 반장에게 확정 요청 알림,
--           일일 보고서 = 그 생산일 야간 교대 보고서가 확정되는 즉시 (trg_shift_report_confirmed), 06:00까지 확정이 없으면
--           06:00 (스케줄러가 부름) + MGR에게 일일 보고서 확정 요청(DAILY_REPORT_PENDING). 교대 보고서가 확정되면 칸을 다시 채운다
-- =====================================================================

-- 보고 항목 목록 글 (6.43 순서, 개수 자르지 않음 — R-73, FR-AST-COM-21)
--   머리 "전체 N건 (안전 a · 긴급 b · 생산 c · 주의 d · 참고 e)" — N = 묶은 뒤 줄 수, 0-1 오래 방치는 주의에 셈
--   순위마다 한 칸. 빈 순위는 "-", 순위 0이 비면 "잠금·표지 중인 설비 없음" (DOC-01 §3.3, DOC-07 §10.5)
CREATE OR REPLACE FUNCTION fn_report_items_text() RETURNS text
LANGUAGE sql STABLE AS $$
    WITH ranks(report_rank, rank_order, rank_name) AS (
        VALUES ('R0', 0, '0 안전'), ('R0_1', 1, '0-1 오래 방치'), ('R1', 2, '1 긴급'), ('R2', 3, '2 생산 위험'),
               ('R3', 4, '3 주의'), ('R4', 5, '4 참고')
    ), lines AS (SELECT * FROM v_report_lines)
    SELECT format('전체 %s건 (안전 %s · 긴급 %s · 생산 %s · 주의 %s · 참고 %s)',
                  (SELECT count(*) FROM lines),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'SAFETY'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'URGENT'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'PRODUCTION'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'CAUTION'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'INFO'))
        || E'\n' || string_agg(
            '[' || k.rank_name || '] ' ||
            coalesce((SELECT string_agg(E'\n- ' || l.title
                                        || CASE WHEN l.member_count > 1 THEN format(' (같은 원인 %s건 묶음)', l.member_count) ELSE '' END,
                                        '' ORDER BY l.rank_group, l.sort_value DESC NULLS LAST, l.occurred_at)
                        FROM lines l WHERE l.report_rank = k.report_rank),
                     CASE WHEN k.report_rank = 'R0' THEN '잠금·표지 중인 설비 없음' ELSE '-' END),
            E'\n' ORDER BY k.rank_order)
      FROM ranks k;
$$;

-- 교대 보고서 초안. 이미 있으면 그대로 둔다. 반환: 'CREATED' / 'EXISTS'
CREATE OR REPLACE FUNCTION fn_create_shift_report_draft(p_shift_id text, p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    s shift%ROWTYPE; v_actual int; v_defect int; v_avail jsonb; v_handover text; v_content jsonb;
BEGIN
    -- 이미 있거나, 지워졌어도 버전 기록이 남아 있으면 다시 만들지 않는다 (문서는 지우지 않는 것이 원칙)
    IF EXISTS (SELECT 1 FROM shift_report WHERE shift_id = p_shift_id)
       OR EXISTS (SELECT 1 FROM document_revision WHERE doc_type = 'SHIFT_REPORT' AND doc_key = p_shift_id) THEN
        RETURN 'EXISTS';
    END IF;
    SELECT * INTO STRICT s FROM shift WHERE shift_id = p_shift_id;
    -- R-46 교대 실적 = 그 교대에 OP-50을 마친 GQ + RQ
    v_actual := fn_shift_actual_qty(p_shift_id);
    SELECT coalesce(sum(sq), 0) INTO v_defect FROM operation_report WHERE shift_id = p_shift_id;
    -- 가동률은 OP-30 설비별 2개 값
    SELECT coalesce(jsonb_object_agg(equipment_id, availability_pct), '{}'::jsonb) INTO v_avail
      FROM v_shift_equipment_kpi WHERE shift_id = p_shift_id AND process_code = 'OP-30';
    v_handover := fn_report_items_text();
    -- 생산 칸 목표 = 총 목표 (목표 + 이월, R-88 — FR-PRD-02-02)
    v_content := jsonb_build_object('target_qty', s.target_qty + s.carry_over_qty, 'shift_target_qty', s.target_qty,
                                    'carry_over_qty', s.carry_over_qty, 'actual_qty', v_actual, 'defect_qty', v_defect,
                                    'availability_pct', v_avail, 'handover_text', v_handover);
    INSERT INTO shift_report (shift_id, status, target_qty, actual_qty, defect_qty, availability_pct, notable_text, handover_text,
                              current_version)
    VALUES (p_shift_id, 'AI_DRAFT', s.target_qty + s.carry_over_qty, v_actual, v_defect, v_avail, '(비서 문장 대기)',
            v_handover, 0);
    PERFORM fn_save_revision('SHIFT_REPORT', p_shift_id, 'AI', NULL, NULL, 'AI_DRAFT', v_content, '[]'::jsonb, NULL, v_at);
    -- 교대 보고서 확정 요청 → 그 교대 반장 (FR-AST-02-17, 6.36 SHIFT_REPORT_PENDING — 2026-10-07 최종 검토로 교대 끝).
    -- 확정하면 자동 처리 (trg_shift_report_confirmed). 확정 전 그 교대 값은 쓰는 곳마다 "잠정"
    PERFORM fn_raise_notification('SHIFT_REPORT_PENDING', format('%s 교대 보고서 확정 요청', p_shift_id),
                                  jsonb_build_object('shift_id', p_shift_id), v_at, p_recipients => ARRAY[s.supervisor_user_id]);
    -- 주간이 끝나면 같은 날 야간 이월을 채운다 (야간 시작 전, R-88)
    IF s.shift_type = 'DAY' THEN
        PERFORM fn_refresh_carry_over(s.work_date);
    END IF;
    RETURN 'CREATED';
END $$;

-- 일일 보고서 초안 (야간 교대 보고서 확정 즉시, 늦어도 다음 날 06:00 — R-72). 확정 안 된 교대 칸은 원기록 집계 + "잠정".
-- 반환: 잠정 교대 수 (이미 있으면 0)
--   확정 요청(SHIFT_REPORT_PENDING)은 교대 끝 초안 때 이미 갔다 — 여기서 다시 보내지 않는다 (2026-10-07 최종 검토).
--   교대 초안이 빠져 있으면 여기서 만든다 (그때 확정 요청도 같이 감).
--   하루 목표 = work_day.daily_target_qty (180 고정, 이월을 더하지 않음). 부족 = 180 − 하루 실적 (R-88, 조회 때 계산)
CREATE OR REPLACE FUNCTION fn_create_daily_report_draft(p_work_date date, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    d work_day%ROWTYPE; v_actual int; v_defect int; v_oee numeric; v_fail numeric; v_speed numeric;
    v_start timestamptz; v_end timestamptz; v_pending int := 0; sh record; v_issues text; v_rev bigint;
BEGIN
    SELECT * INTO STRICT d FROM work_day WHERE work_date = p_work_date;
    IF NOT d.is_workday OR EXISTS (SELECT 1 FROM daily_report WHERE work_date = p_work_date)
       OR EXISTS (SELECT 1 FROM document_revision WHERE doc_type = 'DAILY_REPORT' AND doc_key = p_work_date::text) THEN
        RETURN 0;
    END IF;
    FOR sh IN SELECT s.shift_id, s.supervisor_user_id, r.status FROM shift s LEFT JOIN shift_report r USING (shift_id)
               WHERE s.work_date = p_work_date LOOP
        IF sh.status IS NULL THEN
            PERFORM fn_create_shift_report_draft(sh.shift_id, v_at);
        END IF;
        IF coalesce(sh.status, 'AI_DRAFT') NOT IN ('CONFIRMED','REVISED') THEN
            v_pending := v_pending + 1;
        END IF;
    END LOOP;
    -- R-12 교대 보고서 2개 실적 합 (잠정 교대는 원기록 집계로 만든 초안 값)
    SELECT coalesce(sum(r.actual_qty), 0), coalesce(sum(r.defect_qty), 0) INTO v_actual, v_defect
      FROM shift_report r JOIN shift s USING (shift_id) WHERE s.work_date = p_work_date;
    SELECT min(start_at), max(end_at) INTO v_start, v_end FROM shift WHERE work_date = p_work_date;
    -- 라인 OEE (OP-30 2대, 두 교대 합)
    SELECT round(100 * (sum(k.run_min) / nullif(sum(k.planned_time_min), 0))
                     * (sum(e.std_cycle_min * k.pq) / nullif(sum(k.run_min), 0))
                     * (sum(k.gq + k.rq)::numeric / nullif(sum(k.pq), 0)), 2)
      INTO v_oee FROM v_shift_equipment_kpi k JOIN equipment e USING (equipment_id)
     WHERE k.work_date = p_work_date AND k.process_code = 'OP-30';
    -- 고장 손실 = 고장 정지 손실 합, 속도 손실 = 병목 구간 속도 손실 합 (추정 — 일일 보고서는 따로 보인다)
    v_fail := fn_failure_loss_qty(v_start, v_end);
    v_speed := fn_speed_loss_qty(v_start, v_end);
    v_issues := fn_report_items_text();
    INSERT INTO daily_report (work_date, status, target_qty, actual_qty, defect_qty, oee_pct, failure_loss_qty, speed_loss_qty,
                              issues_summary, current_version)
    VALUES (p_work_date, 'AI_DRAFT', coalesce(d.daily_target_qty, 0), v_actual, v_defect, coalesce(v_oee, 0), v_fail, v_speed,
            v_issues || CASE WHEN v_pending > 0 THEN format(E'\n(잠정: 확정 안 된 교대 %s개)', v_pending) ELSE '' END, 0);
    PERFORM fn_save_revision('DAILY_REPORT', p_work_date::text, 'AI', NULL, NULL, 'AI_DRAFT',
        jsonb_build_object('actual_qty', v_actual, 'defect_qty', v_defect, 'oee_pct', v_oee, 'pending_shifts', v_pending),
        '[]'::jsonb, NULL, v_at);
    -- 일일 보고서 확정 요청 → MGR (6.36 DAILY_REPORT_PENDING, 2026-10-13). 가리키는 기록 = 그 보고서의 v0 (근무일 칸이 없어서)
    SELECT revision_id INTO v_rev FROM document_revision
     WHERE doc_type = 'DAILY_REPORT' AND doc_key = p_work_date::text AND version_no = 0;
    PERFORM fn_raise_notification('DAILY_REPORT_PENDING', format('%s 일일 보고서 확정 요청', p_work_date),
                                  jsonb_build_object('revision_id', v_rev), v_at);
    RETURN v_pending;
END $$;

-- 교대 보고서가 확정되면 확정 전 일일 보고서의 그 칸(실적·불량·잠정 표시)을 다시 채우고 수정 이력 1줄 (DOC-01 §3.3, R-72).
-- 이력의 작성자 = 확정한 반장 (AI 작성자는 v0만 — ck_document_revision_ai_v0). 반환: 새 버전 (바뀐 것이 없으면 그대로, 없으면 NULL)
CREATE OR REPLACE FUNCTION fn_refill_daily_report(p_work_date date, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    d daily_report%ROWTYPE; v_actual int; v_defect int; v_pending int; v_issues text; v_ver int;
    v_changes jsonb := '[]'::jsonb;
BEGIN
    SELECT * INTO d FROM daily_report WHERE work_date = p_work_date;
    IF NOT FOUND OR d.status NOT IN ('AI_DRAFT','EDITING') THEN RETURN NULL; END IF;
    SELECT coalesce(sum(r.actual_qty), 0), coalesce(sum(r.defect_qty), 0) INTO v_actual, v_defect
      FROM shift_report r JOIN shift s USING (shift_id) WHERE s.work_date = p_work_date;
    SELECT count(*) INTO v_pending FROM shift s LEFT JOIN shift_report r USING (shift_id)
     WHERE s.work_date = p_work_date AND coalesce(r.status, 'AI_DRAFT') NOT IN ('CONFIRMED','REVISED');
    v_issues := regexp_replace(d.issues_summary, '\n?\(잠정: 확정 안 된 교대 [0-9]+개\)', '', 'g')
                || CASE WHEN v_pending > 0 THEN format(E'\n(잠정: 확정 안 된 교대 %s개)', v_pending) ELSE '' END;
    IF v_actual <> d.actual_qty THEN
        v_changes := v_changes || jsonb_build_object('field', 'actual_qty', 'before', d.actual_qty, 'after', v_actual);
    END IF;
    IF v_defect <> d.defect_qty THEN
        v_changes := v_changes || jsonb_build_object('field', 'defect_qty', 'before', d.defect_qty, 'after', v_defect);
    END IF;
    IF v_issues <> d.issues_summary THEN
        v_changes := v_changes || jsonb_build_object('field', 'issues_summary', 'before', d.issues_summary, 'after', v_issues);
    END IF;
    IF jsonb_array_length(v_changes) = 0 THEN RETURN d.current_version; END IF;
    v_ver := fn_save_revision('DAILY_REPORT', p_work_date::text, 'HUMAN', p_actor, '교대 보고서 확정으로 칸을 다시 채움 (R-72)',
                              d.status, jsonb_build_object('actual_qty', v_actual, 'defect_qty', v_defect,
                                                           'pending_shifts', v_pending), v_changes, NULL, p_at);
    UPDATE daily_report SET actual_qty = v_actual, defect_qty = v_defect, issues_summary = v_issues, current_version = v_ver
     WHERE work_date = p_work_date;
    RETURN v_ver;
END $$;

-- 확정되면 확정 요청 알림 자동 처리 (6.36 SHIFT_REPORT_PENDING).
-- 주간 교대 보고서가 확정되면 그날 야간 이월을 확정 실적으로 다시 계산한다 (R-88, 잠정이 풀림).
-- 일일 보고서가 이미 있으면(확정 전) 그 칸을 다시 채운다 (R-72)
CREATE OR REPLACE FUNCTION trg_shift_report_confirmed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('CONFIRMED','REVISED') AND OLD.status NOT IN ('CONFIRMED','REVISED') THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'SHIFT_REPORT_PENDING' AND shift_id = NEW.shift_id AND NOT is_processed),
                                NEW.confirmed_by, NEW.confirmed_at);
        IF (SELECT shift_type FROM shift WHERE shift_id = NEW.shift_id) = 'DAY' THEN
            PERFORM fn_refresh_carry_over((SELECT work_date FROM shift WHERE shift_id = NEW.shift_id));
        END IF;
        PERFORM fn_refill_daily_report((SELECT work_date FROM shift WHERE shift_id = NEW.shift_id), NEW.confirmed_by,
                                       NEW.confirmed_at);
        -- 야간 교대 보고서가 확정되면 그 생산일 일일 보고서 초안을 바로 만든다 (R-72, 2026-10-13). 이미 있으면 그대로
        IF (SELECT shift_type FROM shift WHERE shift_id = NEW.shift_id) = 'NIGHT' THEN
            PERFORM fn_create_daily_report_draft((SELECT work_date FROM shift WHERE shift_id = NEW.shift_id),
                                                 coalesce(NEW.confirmed_at, app_now()));
        END IF;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER shift_report_confirmed AFTER UPDATE OF status ON shift_report
    FOR EACH ROW EXECUTE FUNCTION trg_shift_report_confirmed();

-- 작업지시서 상태가 바뀔 때 (6.36 처리 표, 2026-10-13):
--   승인·취소 → 승인 대기 알림(APPROVAL_WAIT_*) 자동 처리. 승인 → 담당 MNT에게 "작업지시서 배정"(WO_ASSIGNED)
--   AI비서 초안 → 수정 중(보전 담당자가 저장) → 초안 검토 알림(WO_DRAFT_READY) 자동 처리
--   승인 → 진행 중([작업 시작]) → 배정 알림 자동 처리 (담당 MNT가 작업지시서를 "열면"도 처리 — API-MNT-06 GET)
--   작업지시서를 취소하면 남은 초안 검토·배정 알림도 닫는다
CREATE OR REPLACE FUNCTION trg_work_order_approved() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('APPROVED','CANCELLED') AND OLD.status IN ('AI_DRAFT','EDITING') THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code IN ('APPROVAL_WAIT_30M','APPROVAL_WAIT_2H') AND wo_no = NEW.wo_no AND NOT is_processed),
                                coalesce(NEW.approved_by, NEW.cancelled_by), coalesce(NEW.approved_at, NEW.cancelled_at));
    END IF;
    IF NEW.status = 'APPROVED' AND OLD.status IN ('AI_DRAFT','EDITING') AND NEW.assignee_user_id IS NOT NULL THEN
        PERFORM fn_raise_notification('WO_ASSIGNED', format('작업지시서 %s 배정 (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id),
                                      NEW.approved_at, p_recipients => ARRAY[NEW.assignee_user_id]);
    END IF;
    IF OLD.status = 'AI_DRAFT' AND NEW.status <> 'AI_DRAFT' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_DRAFT_READY' AND wo_no = NEW.wo_no AND NOT is_processed),
                                NULL, app_now());
    END IF;
    IF (NEW.status = 'IN_PROGRESS' AND OLD.status = 'APPROVED') OR NEW.status = 'CANCELLED' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_ASSIGNED' AND wo_no = NEW.wo_no AND NOT is_processed),
                                CASE WHEN NEW.status = 'IN_PROGRESS' THEN NEW.assignee_user_id END, app_now());
    END IF;
    RETURN NULL;
END $$;

-- 작업지시서 AI비서 초안이 생기면 → 그 설비 MNT에게 "작업지시서 초안 검토" (6.36 WO_DRAFT_READY, 2026-10-13).
-- 받는 사람 = 보전 담당자 전원 (긴급 알림 처리 책임 MNT와 같은 사람 — 설비별 담당 MNT 칸이 없어 MNT 전원 [제안])
CREATE OR REPLACE FUNCTION trg_work_order_draft_ready() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'AI_DRAFT' AND current_setting('app.loading', true) IS DISTINCT FROM 'on' THEN
        PERFORM fn_raise_notification('WO_DRAFT_READY', format('작업지시서 초안 검토: %s (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id), NEW.created_at);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER work_order_draft_ready AFTER INSERT ON maintenance_work_order
    FOR EACH ROW EXECUTE FUNCTION trg_work_order_draft_ready();

-- 일일 보고서를 MGR이 확정하면 확정 요청 알림 자동 처리 (6.36 DAILY_REPORT_PENDING)
CREATE OR REPLACE FUNCTION trg_daily_report_confirmed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('CONFIRMED','REVISED') AND OLD.status NOT IN ('CONFIRMED','REVISED') THEN
        PERFORM fn_auto_process(ARRAY(SELECT n.notification_id FROM notification n
                                        JOIN document_revision v ON v.revision_id = n.revision_id
                                       WHERE n.rule_code = 'DAILY_REPORT_PENDING' AND v.doc_type = 'DAILY_REPORT'
                                         AND v.doc_key = NEW.work_date::text AND NOT n.is_processed),
                                NEW.confirmed_by, NEW.confirmed_at);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER daily_report_confirmed AFTER UPDATE OF status ON daily_report
    FOR EACH ROW EXECUTE FUNCTION trg_daily_report_confirmed();
CREATE TRIGGER work_order_approved AFTER UPDATE OF status ON maintenance_work_order
    FOR EACH ROW EXECUTE FUNCTION trg_work_order_approved();

-- 스케줄러가 몇 분마다 부르는 시간 규칙 알림 (승인 대기·예방 정비 기한·CMM 결과 미수신·목표 미달 위험) + 지금 야간 이월. 반환: 새 알림 수
CREATE OR REPLACE FUNCTION fn_run_time_rules(p_cmm_wait_min int DEFAULT 10, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_today date := (v_at AT TIME ZONE 'Asia/Seoul')::date;
    v_n int := 0; r record;
BEGIN
    -- 승인 대기 30분(참고)·2시간(주의) — DOC-07 10.2
    FOR r IN SELECT wo_no, equipment_id, created_at FROM maintenance_work_order
              WHERE status IN ('AI_DRAFT','EDITING') AND created_at <= v_at - interval '30 minutes' LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_30M' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_30M', format('작업지시서 %s 승인 대기 30분', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
        IF r.created_at <= v_at - interval '2 hours'
           AND NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_2H' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_2H', format('작업지시서 %s 승인 대기 2시간', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 예방 정비 기한 하루 전(참고)·넘김(주의) — 달력에 있는 항목만
    FOR r IN SELECT pm_task_id, equipment_id, item_name, next_due_date FROM v_pm_task_due
              WHERE is_active AND on_calendar AND next_due_date IS NOT NULL AND next_due_date <= v_today + 1 LOOP
        IF r.next_due_date = v_today + 1 AND NOT EXISTS (SELECT 1 FROM notification
                WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id = r.pm_task_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('PM_DUE_SOON', format('%s 예방 정비 내일: %s', r.equipment_id, r.item_name),
                                          jsonb_build_object('pm_task_id', r.pm_task_id, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        ELSIF r.next_due_date < v_today AND NOT EXISTS (SELECT 1 FROM notification
                WHERE rule_code = 'PM_OVERDUE' AND pm_task_id = r.pm_task_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('PM_OVERDUE', format('%s 예방 정비 기한 넘김: %s', r.equipment_id, r.item_name),
                                          jsonb_build_object('pm_task_id', r.pm_task_id, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- CMM 결과 미수신 (대기 시간은 [선택 필요: 기술 회의])
    FOR r IN SELECT instruction_id, lot_no, part_seq FROM cmm_instruction
              WHERE status = 'STARTED' AND started_at < v_at - make_interval(mins => p_cmm_wait_min) LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CMM_NO_RESULT' AND lot_no = r.lot_no AND NOT is_processed) THEN
            PERFORM fn_raise_notification('CMM_NO_RESULT', format('측정 결과 미수신: %s 순번 %s', r.lot_no, r.part_seq),
                                          jsonb_build_object('lot_no', r.lot_no, 'equipment_id', 'CMM-01'), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 지금 야간 교대의 이월 (R-88). 주간 초안·확정 때 채우지만, 적재한 데이터·늦은 확정에 대비해 다시 맞춘다
    PERFORM fn_refresh_carry_over(work_date) FROM shift WHERE shift_type = 'NIGHT' AND start_at <= v_at AND end_at > v_at;
    -- 목표 미달 위험 (R-48·R-88, FR-AST-02-04): 지금 교대의 예측 < 총 목표(목표 + 이월) × 90% → 반장. 교대마다 1번.
    --   교대 시작 1시간 뒤부터 본다 [제안] — 시작 직후는 첫 부품이 OP-50에 닿기 전이라 예측이 0에 가깝다 (DOC-07 8장)
    FOR r IN SELECT shift_id, forecast_qty, total_target_qty, shortfall_qty, carry_over_qty FROM v_shift_progress
              WHERE start_at <= v_at AND end_at > v_at AND elapsed_min >= 60 AND is_target_risk LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TARGET_RISK' AND shift_id = r.shift_id) THEN
            PERFORM fn_raise_notification('TARGET_RISK',
                format('목표 미달 위험: 이 속도면 목표보다 %s개 부족 (예측 %s / 총 목표 %s)', r.shortfall_qty, r.forecast_qty,
                       r.total_target_qty),
                jsonb_build_object('shift_id', r.shift_id), v_at,
                p_related_info => format('총 목표 = 목표 %s + 이월 %s (DOC-07 §4.1·8장)', r.total_target_qty - r.carry_over_qty,
                                         r.carry_over_qty));
            v_n := v_n + 1;
        END IF;
    END LOOP;
    RETURN v_n;
END $$;
