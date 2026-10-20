-- =====================================================================
-- 60_ingest.sql — 설비 쪽 사건 받기와 AI비서 초안 저장
--   fn_ingest_alarm            : 시뮬레이터(또는 실제 설비 수집기)가 알람 1건을 보낼 때
--   fn_create_work_order_draft : AI 비서 ②가 만든 작업지시서 초안(정해진 JSON 칸)을 저장할 때
--   fn_issue_cmm_instruction   : OP-50 측정 지시 (R-78, FR-QLT-01-15)
-- 데이터는 설비 → 플랫폼 한 방향 (FR-AST-COM-11). 이 함수들은 설비에 아무것도 보내지 않는다.
-- =====================================================================

-- 알람 1건 받기: 기록 → 등급별 알림(R-38) → 반복 알람 판정(R-70). 반환: alarm_event_id
-- 받는 사람 (6.36, 2026-10-13 팀 회의):
--   정지(ALARM_STOP) = 사용 중인 전원 — 긴급 팝업은 로그인한 사람 화면에 뜬다 (실시간 채널). 처리 책임은 그 설비 OPR·MNT
--   주의(ALARM_WARN) = 그 공정 작업자(담당 공정 두 칸) + 보전 담당자 / 조작 안내(ALARM_GUIDE) = 그 공정 작업자
CREATE OR REPLACE FUNCTION fn_ingest_alarm(p_equipment_id text, p_alarm_code text, p_occurred_at timestamptz DEFAULT NULL,
    p_lot_no text DEFAULT NULL, p_prev_alarm_event_id bigint DEFAULT NULL, p_is_injected boolean DEFAULT false,
    p_scenario_code text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at  timestamptz := coalesce(p_occurred_at, app_now());
    m     alarm_master%ROWTYPE;
    v_id  bigint;
    v_proc text := fn_equipment_process(p_equipment_id);
    v_rule text;
    v_recipients text[];
BEGIN
    SELECT * INTO m FROM alarm_master WHERE alarm_code = p_alarm_code;
    IF NOT FOUND THEN RAISE EXCEPTION '알람 코드집에 없는 알람 %', p_alarm_code USING ERRCODE = '23503'; END IF;
    INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at, lot_no, prev_alarm_event_id, is_injected, scenario_code)
    VALUES (p_equipment_id, p_alarm_code, m.severity, v_at, p_lot_no, p_prev_alarm_event_id, p_is_injected, p_scenario_code)
    RETURNING alarm_event_id INTO v_id;
    v_rule := CASE m.severity WHEN 'STOP' THEN 'ALARM_STOP' WHEN 'WARN' THEN 'ALARM_WARN' ELSE 'ALARM_GUIDE' END;
    SELECT array_agg(user_id) INTO v_recipients FROM app_user
     WHERE is_active AND (m.severity = 'STOP'
                          OR (role_code = 'OPR' AND (v_proc IN (home_process_code, home_process_code_2) OR home_process_code IS NULL))
                          OR (role_code = 'MNT' AND m.severity = 'WARN'));
    PERFORM fn_raise_notification(v_rule, format('%s 알람 %s (%s)', p_equipment_id, p_alarm_code, m.name_ko),
                                  jsonb_build_object('alarm_event_id', v_id, 'equipment_id', p_equipment_id, 'lot_no', p_lot_no),
                                  v_at, p_recipients => v_recipients);
    IF m.severity <> 'GUIDE' THEN
        PERFORM fn_check_repeat_alarm(v_id);
    END IF;
    RETURN v_id;
END $$;

-- 작업지시서 AI비서 초안 저장 (R-02·R-33·R-71). 반환: wo_no
-- p_steps = [{"step_text": "...", "source_section": "DOC-03 §2.1"}], p_parts = [{"item_no": "CS-WLUB", "qty": 1}]
-- 고정 서식 블록(잠금·표지 6+3단계·고전압·보호구)은 AI가 쓰지 않는다: safety_block_doc_rev로 붙었다는 표시만 (R-33)
CREATE OR REPLACE FUNCTION fn_create_work_order_draft(p_equipment_id text, p_title text, p_symptom text,
    p_alarm_event_id bigint DEFAULT NULL, p_trigger_notification_id bigint DEFAULT NULL, p_pm_record_id bigint DEFAULT NULL,
    p_steps jsonb DEFAULT '[]'::jsonb, p_parts jsonb DEFAULT '[]'::jsonb, p_lot_no text DEFAULT NULL, p_at timestamptz DEFAULT NULL,
    p_author text DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_wo text;
    v_doc05 text;
    -- p_author 가 없으면 AI비서 초안(AI_DRAFT, v0 = AI), 있으면 보전 담당자가 직접 만든 것(EDITING, v0 = HUMAN)
    v_status text := CASE WHEN p_author IS NULL THEN 'AI_DRAFT' ELSE 'EDITING' END;
BEGIN
    PERFORM fn_require_role(p_author, ARRAY['MNT'], '작업지시서 작성');
    -- 정지 등급 알람과 2단계가 겹치면 작업지시서 1개 (R-71): 이미 이 알람의 작업지시서가 있으면 계기만 더한다
    IF p_alarm_event_id IS NOT NULL THEN
        SELECT wo_no INTO v_wo FROM maintenance_work_order WHERE alarm_event_id = p_alarm_event_id;
    END IF;
    IF v_wo IS NULL AND p_trigger_notification_id IS NOT NULL THEN
        SELECT m.wo_no INTO v_wo FROM maintenance_work_order m JOIN notification n ON n.alarm_event_id = m.alarm_event_id
         WHERE n.notification_id = p_trigger_notification_id;
    END IF;
    IF v_wo IS NOT NULL THEN
        UPDATE maintenance_work_order SET trigger_notification_id = coalesce(trigger_notification_id, p_trigger_notification_id)
         WHERE wo_no = v_wo;
        INSERT INTO work_order_step (wo_no, step_no, step_text, source_section)
        SELECT v_wo, (SELECT coalesce(max(step_no), 0) FROM work_order_step WHERE wo_no = v_wo) + ord, s->>'step_text', s->>'source_section'
          FROM jsonb_array_elements(p_steps) WITH ORDINALITY AS x(s, ord);
        RETURN v_wo;
    END IF;
    SELECT 'DOC-05 ' || current_rev INTO v_doc05 FROM internal_doc WHERE doc_no = 'DOC-05';
    v_wo := fn_next_doc_no('MW', v_at);
    INSERT INTO maintenance_work_order (wo_no, alarm_event_id, pm_record_id, trigger_notification_id, equipment_id, lot_no, created_at,
                                        title, symptom, status, safety_block_doc_rev, has_high_voltage_notice, current_version)
    VALUES (v_wo, p_alarm_event_id, p_pm_record_id, p_trigger_notification_id, p_equipment_id, p_lot_no, v_at,
            p_title, p_symptom, v_status, coalesce(v_doc05, 'DOC-05'), fn_equipment_process(p_equipment_id) = 'OP-30', 0);
    INSERT INTO work_order_step (wo_no, step_no, step_text, source_section)
    SELECT v_wo, ord, s->>'step_text', s->>'source_section' FROM jsonb_array_elements(p_steps) WITH ORDINALITY AS x(s, ord);
    INSERT INTO work_order_part (wo_no, item_no, suggested_qty)
    SELECT v_wo, p->>'item_no', (p->>'qty')::numeric FROM jsonb_array_elements(p_parts) p;
    PERFORM fn_save_revision('WORK_ORDER', v_wo, CASE WHEN p_author IS NULL THEN 'AI' ELSE 'HUMAN' END, p_author, NULL, v_status,
        jsonb_build_object('title', p_title, 'symptom', p_symptom, 'steps', p_steps, 'parts', p_parts), '[]'::jsonb, NULL, v_at);
    RETURN v_wo;
END $$;

-- 측정 지시 (R-78, FR-QLT-01-15): 로트의 검사 방식으로 검사 구분을 정한다. 반환: instruction_id
CREATE OR REPLACE FUNCTION fn_issue_cmm_instruction(p_lot_no text, p_part_seq int, p_first boolean DEFAULT false,
                                                    p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE p inspection_plan%ROWTYPE; v_kind text; v_id bigint;
BEGIN
    PERFORM fn_create_inspection_plan(p_lot_no);
    SELECT * INTO p FROM inspection_plan WHERE lot_no = p_lot_no;
    v_kind := CASE WHEN p.plan_mode = 'ENHANCED' THEN 'ENHANCED' WHEN p_first THEN 'FIRST' ELSE 'SAMPLE' END;
    IF v_kind = 'SAMPLE' AND NOT (p_part_seq = 1 OR p_part_seq % 5 = 0) THEN
        RAISE EXCEPTION 'R-09: 발췌 로트의 측정 부품은 1번과 5의 배수 (요청 %)', p_part_seq USING ERRCODE = '23514';
    END IF;
    INSERT INTO cmm_instruction (lot_no, part_seq, insp_kind, enhance_reason, issued_at)
    VALUES (p_lot_no, p_part_seq, v_kind, CASE WHEN v_kind = 'ENHANCED' THEN p.enhance_reason END, coalesce(p_at, app_now()))
    RETURNING instruction_id INTO v_id;
    RETURN v_id;
END $$;

-- 일일 보고서 글에서 관리자 메모 떼기 (2026-10-20 정비 탭 확인 요청 1 — daily_report.memo 칸이 생기기 전 글 모양).
--   생성기 9월 기록은 issues_summary 끝에 "… 관리자 메모: X", 시연 서버는 "… / 관리자 메모: X"를 붙였다 (맨 끝 것을 뗀다).
--   반환 {오늘의 문제 글, 메모}. 메모가 없으면 {글 그대로, NULL}. 쓰는 곳: tools/load_generated.py (적재 때)
CREATE OR REPLACE FUNCTION fn_split_memo(p_text text) RETURNS text[]
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN x.g IS NULL THEN ARRAY[p_text, NULL]
                ELSE ARRAY[regexp_replace(x.g[1], '\s*/\s*$', ''), nullif(btrim(x.g[2]), '')] END
      FROM (SELECT regexp_match(p_text, '^(.*\S)\s+관리자 메모:\s*(.*)$') AS g) x;
$$;
