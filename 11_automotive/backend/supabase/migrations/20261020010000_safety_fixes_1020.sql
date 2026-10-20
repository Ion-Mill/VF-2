-- =====================================================================
-- 2026-10-20 시연 안전·버그 고침 (구현_중_수정사항/1020_수정간단내용.md 35장) — 이미 올린 mom-db에 바뀐 함수만 (표 구조 그대로)
--   1) 간이 작업기록 잠금·표지: 알람 잠금 수준 FULL·TWO_POINT면 DB가 safety_block_required = 참 (R-32·33)
--   3) 측정값 반장 확인: 같은 부품·항목·위치의 다른 값만 판정에서 뺌 (R-81)
--   4) 일부 폐기: 승인해도 보류는 열린 채 폐기 수량만, 해제는 폐기 승인 뒤 (1013 7장)
--   5) 예방 정비 기한 하루 전·넘김 알림은 주 1회 이상 주기만
--   (2 문서함 예방 정비 할 일은 API 쿼리 app/sql/documents.sql — DB 바뀜 없음)
-- 같은 내용이 db/ 원본에 있다. 스키마 주인(postgres)으로 한 번
-- =====================================================================
SET client_min_messages = warning;

-- 간이 작업기록에 잠금·표지 9단계가 필요한 알람인가 (R-32·33, DOC-05 §2.4·§7): 잠금 수준 FULL·TWO_POINT
CREATE OR REPLACE FUNCTION fn_simple_record_needs_loto(p_alarm_event_id bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT m.lockout_level IN ('FULL','TWO_POINT')
                       FROM alarm_event a JOIN alarm_master m USING (alarm_code)
                      WHERE a.alarm_event_id = p_alarm_event_id), false);
$$;

CREATE OR REPLACE FUNCTION trg_work_record_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sev text; v_proc text; v_roles text[]; v_loto int; v_wo_eq text;
BEGIN
    IF current_setting('app.loading', true) IS DISTINCT FROM 'on' THEN
        IF TG_OP = 'INSERT' AND NEW.record_type = 'SIMPLE' AND NEW.alarm_event_id IS NOT NULL
           AND fn_simple_record_needs_loto(NEW.alarm_event_id) THEN
            NEW.safety_block_required := true;
        ELSIF TG_OP = 'UPDATE' AND OLD.safety_block_required AND NOT NEW.safety_block_required THEN
            NEW.safety_block_required := true;
        END IF;
    END IF;
    IF NEW.wo_no IS NOT NULL THEN
        SELECT equipment_id INTO v_wo_eq FROM maintenance_work_order WHERE wo_no = NEW.wo_no;
        IF v_wo_eq <> NEW.equipment_id THEN
            RAISE EXCEPTION '작업기록서 설비(%)가 작업지시서 설비(%)와 다름', NEW.equipment_id, v_wo_eq USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.confirmed_by IS NOT NULL THEN
        IF NEW.record_type = 'FULL' OR NEW.cause_check_notification_id IS NOT NULL THEN
            v_roles := ARRAY['MNT'];
        ELSE
            SELECT a.severity_at_event, e.process_code INTO v_sev, v_proc
              FROM alarm_event a JOIN equipment e USING (equipment_id) WHERE a.alarm_event_id = NEW.alarm_event_id;
            v_roles := CASE WHEN v_sev = 'STOP' THEN ARRAY['MNT'] ELSE ARRAY['OPR','MNT'] END;
        END IF;
        PERFORM fn_require_role(NEW.confirmed_by, v_roles, '작업기록 확정');
    END IF;
    PERFORM fn_require_role(NEW.checked_by, ARRAY['SUP'], '작업기록서 확인');
    IF TG_OP = 'UPDATE' AND NEW.status = 'CONFIRMED' AND OLD.status IN ('AI_DRAFT','EDITING')
       AND NEW.safety_block_required THEN
        SELECT count(*) INTO v_loto FROM work_record_check
         WHERE record_no = NEW.record_no AND check_kind = 'LOTO' AND is_checked;
        IF v_loto < 9 THEN
            RAISE EXCEPTION 'R-32: 잠금·표지 9단계 중 %단계만 체크됨 — 확정할 수 없음 (%)', v_loto, NEW.record_no
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION fn_check_measurement(p_result_id bigint, p_actor text, p_use_for_judgement boolean,
                                                p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE r inspection_result%ROWTYPE; v_at timestamptz := coalesce(p_at, app_now());
BEGIN
    SELECT * INTO r FROM inspection_result WHERE result_id = p_result_id FOR UPDATE;
    PERFORM fn_require_role(p_actor, ARRAY['SUP'], '측정값 반장 확인');
    IF p_use_for_judgement THEN
        -- 같은 부품·항목·측정 위치의 다른 값은 판정에서 뺀다 (하나만 참, R-81). 강화 검사 3단(TOP·MID·BOTTOM)은 위치마다 따로
        UPDATE inspection_result SET use_for_judgement = false
         WHERE lot_no = r.lot_no AND part_seq = r.part_seq AND item_seq = r.item_seq
           AND position IS NOT DISTINCT FROM r.position AND result_id <> p_result_id;
    END IF;
    UPDATE inspection_result SET check_status = 'CHECKED', checked_by = p_actor, checked_at = v_at,
                                 use_for_judgement = p_use_for_judgement
     WHERE result_id = p_result_id;
    PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                   WHERE rule_code = 'CMM_JUDGE_MISMATCH' AND result_id = p_result_id AND NOT is_processed),
                            p_actor, v_at);
END $$;

CREATE OR REPLACE FUNCTION fn_lot_release(p_hold_id bigint, p_actor text, p_pass_qty int, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); h lot_hold%ROWTYPE; v_fg text;
BEGIN
    SELECT * INTO h FROM lot_hold WHERE hold_id = p_hold_id FOR UPDATE;
    IF h.result <> 'IN_PROGRESS' THEN RAISE EXCEPTION '보류 %는 이미 끝남 (%)', p_hold_id, h.result USING ERRCODE = '23514'; END IF;
    -- 폐기 제안이 있으면 관리자 승인 뒤에 해제 (1013 7장: 반장 폐기 제안 → 관리자 승인 → 반장 해제, 2026-10-20)
    IF h.scrap_proposed_by IS NOT NULL AND h.scrap_approved_by IS NULL THEN
        RAISE EXCEPTION '보류 %는 폐기 승인 대기 — 관리자가 폐기를 승인한 뒤 해제', p_hold_id USING ERRCODE = '23514';
    END IF;
    -- [제안] 해제 = 전수 검사로 골라낸 합격품을 출하 가능으로 (6.8). 합격 0개면 해제가 아니라 폐기로 간다
    IF coalesce(p_pass_qty, 0) <= 0 THEN
        RAISE EXCEPTION '해제 합격 수량은 1개 이상 (로트 % 완료 수량 %) — 전부 불량이면 폐기, 생산 중이면 검사 뒤 해제',
            h.lot_no, fn_lot_completed_qty(h.lot_no) USING ERRCODE = '23514';
    END IF;
    IF p_pass_qty > fn_lot_completed_qty(h.lot_no) THEN   -- 완료 수량(GQ + RQ)은 폐기(SQ)를 이미 뺀 값
        RAISE EXCEPTION '해제 합격 수량 %가 로트 완료 수량보다 많음', p_pass_qty USING ERRCODE = '23514';
    END IF;
    UPDATE lot_hold SET result = 'RELEASED', released_by = p_actor, released_at = v_at, released_pass_qty = p_pass_qty
     WHERE hold_id = p_hold_id;
    UPDATE production_lot SET status = 'RELEASED' WHERE lot_no = h.lot_no;
    SELECT item_no INTO STRICT v_fg FROM inventory_item WHERE category = 'FINISHED';
    IF p_pass_qty > 0 THEN
        INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, fg_lot_no)
        VALUES (v_fg, 'FG_IN', p_pass_qty, v_at, 'LOT_PASS', h.lot_no);
    END IF;
END $$;

-- 폐기: SUP 제안 → MGR 승인 (R-27, FR-PRD-05-08)
--   일부 폐기(제안 수량 < 로트 투입 수량, 2026-10-20): 승인해도 보류는 열린 채 폐기 수량만 남기고, 반장이 나머지를 해제한다
--   (1013 7장 — 9월 LOT-2609-056-2 등). 전부 폐기(제안 수량 ≥ 투입 수량 또는 비어 있음)면 보류·로트 모두 폐기로 닫는다
CREATE OR REPLACE FUNCTION fn_lot_scrap_propose(p_hold_id bigint, p_actor text, p_qty int) RETURNS void
LANGUAGE sql AS $$
    UPDATE lot_hold SET scrap_proposed_by = p_actor, scrap_proposed_qty = p_qty WHERE hold_id = p_hold_id AND result = 'IN_PROGRESS';
$$;
CREATE OR REPLACE FUNCTION fn_lot_scrap_approve(p_hold_id bigint, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE h lot_hold%ROWTYPE; v_at timestamptz := coalesce(p_at, app_now());
BEGIN
    SELECT * INTO h FROM lot_hold WHERE hold_id = p_hold_id FOR UPDATE;
    IF h.result <> 'IN_PROGRESS' OR h.scrap_proposed_by IS NULL THEN
        RAISE EXCEPTION '폐기 승인은 반장의 폐기 제안이 있는 열린 보류만' USING ERRCODE = '23514';
    END IF;
    IF h.scrap_proposed_qty IS NOT NULL AND h.scrap_proposed_qty < (SELECT input_qty FROM production_lot WHERE lot_no = h.lot_no) THEN
        UPDATE lot_hold SET scrap_approved_by = p_actor, scrap_approved_at = v_at WHERE hold_id = p_hold_id;
        UPDATE production_lot SET scrap_qty = h.scrap_proposed_qty WHERE lot_no = h.lot_no;
    ELSE
        UPDATE lot_hold SET result = 'SCRAPPED', scrap_approved_by = p_actor, scrap_approved_at = v_at WHERE hold_id = p_hold_id;
        UPDATE production_lot SET status = 'SCRAPPED', scrap_qty = least(input_qty, coalesce(h.scrap_proposed_qty, input_qty))
         WHERE lot_no = h.lot_no;
    END IF;
END $$;

-- 예방 정비 기한 하루 전 알림 (참고, MNT): 내일이 기한인 항목(달력에 있는 것)을 같은 기한 날짜끼리 1건으로 묶는다.
--   이미 열린 하루 전 알림에 든 항목은 빼고, 같은 날짜의 열린 묶음이 있으면 거기에 더한다 (건수·항목 목록 다시 씀).
--   문장 "기한 10/02 (내일) 예방 정비 4건", 관련 정보 = "설비 항목 · …". 반환: 새로 만든 알림 수
CREATE OR REPLACE FUNCTION fn_raise_pm_due_soon(p_at timestamptz DEFAULT NULL) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_due date := (v_at AT TIME ZONE 'Asia/Seoul')::date + 1;
    v_tasks text[]; v_id bigint; v_new int := 0; v_cnt int; v_items text;
BEGIN
    SELECT array_agg(d.pm_task_id ORDER BY d.equipment_id, d.pm_task_id) INTO v_tasks
      FROM v_pm_task_due d
     WHERE d.is_active AND d.on_calendar AND d.cycle_code IN ('WEEKLY','MONTHLY','HALF_YEAR','YEARLY')   -- 주 1회 이상만
       AND d.next_due_date = v_due
       AND NOT EXISTS (SELECT 1 FROM notification n
                        WHERE n.rule_code = 'PM_DUE_SOON' AND NOT n.is_processed
                          AND (n.pm_task_id = d.pm_task_id
                               OR EXISTS (SELECT 1 FROM notification_pm_task l
                                           WHERE l.notification_id = n.notification_id AND l.pm_task_id = d.pm_task_id)));
    IF v_tasks IS NULL THEN RETURN 0; END IF;
    SELECT notification_id INTO v_id FROM notification
     WHERE rule_code = 'PM_DUE_SOON' AND NOT is_processed AND pm_task_id IS NULL
       AND (raised_at AT TIME ZONE 'Asia/Seoul')::date + 1 = v_due
     ORDER BY raised_at LIMIT 1;
    IF v_id IS NULL THEN
        SELECT count(*), string_agg(equipment_id || ' ' || item_name, ' · ' ORDER BY equipment_id, pm_task_id) INTO v_cnt, v_items
          FROM pm_task WHERE pm_task_id = ANY (v_tasks);
        v_id := fn_raise_notification('PM_DUE_SOON', format('기한 %s (내일) 예방 정비 %s건', to_char(v_due, 'MM/DD'), v_cnt),
                                      '{}'::jsonb, v_at, p_related_info => v_items);
        IF v_id IS NULL THEN RETURN 0; END IF;          -- 규칙이 꺼져 있음
        v_new := 1;
    END IF;
    INSERT INTO notification_pm_task (notification_id, pm_task_id) SELECT v_id, unnest(v_tasks) ON CONFLICT DO NOTHING;
    IF v_new = 0 THEN
        SELECT count(*), string_agg(t.equipment_id || ' ' || t.item_name, ' · ' ORDER BY t.equipment_id, t.pm_task_id)
          INTO v_cnt, v_items
          FROM notification_pm_task l JOIN pm_task t USING (pm_task_id) WHERE l.notification_id = v_id;
        UPDATE notification SET message = format('기한 %s (내일) 예방 정비 %s건', to_char(v_due, 'MM/DD'), v_cnt),
               related_info = v_items
         WHERE notification_id = v_id;
    END IF;
    RETURN v_new;
END $$;

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
        -- 승인 대기 30분이 되면 승인 요청 알림은 그쪽으로 넘어가 닫힌다 (2026-10-20)
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_APPROVAL_REQUEST' AND wo_no = r.wo_no AND NOT is_processed),
                                NULL, v_at);
        IF r.created_at <= v_at - interval '2 hours'
           AND NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_2H' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_2H', format('작업지시서 %s 승인 대기 2시간', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 예방 정비 기한 하루 전(참고)·넘김(주의) — 달력에 있는 주 1회 이상 주기 항목만 (매일·교대 점검은 점검표, 2026-10-20 고침)
    --   하루 전은 같은 기한 날짜끼리 1건으로 묶는다 (2026-10-20 정비 탭 확인 요청 5, FR-AST-02-08) → fn_raise_pm_due_soon.
    --   묶인 항목이 모두 끝나거나 기한을 넘기면 자동 처리 (fn_close_pm_due_soon — 항목마다 1건이던 9월 알림도 같은 규칙)
    PERFORM fn_close_pm_due_soon(NULL, v_at);
    v_n := v_n + fn_raise_pm_due_soon(v_at);
    FOR r IN SELECT pm_task_id, equipment_id, item_name, next_due_date FROM v_pm_task_due
              WHERE is_active AND on_calendar AND cycle_code IN ('WEEKLY','MONTHLY','HALF_YEAR','YEARLY')
                AND next_due_date IS NOT NULL AND next_due_date < v_today LOOP
        IF NOT EXISTS (SELECT 1 FROM notification
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

-- 새 함수 권한 (db/roles.sql: PUBLIC 실행 금지, 앱 계정·비서 읽기 계정은 필요한 것만)
REVOKE EXECUTE ON FUNCTION fn_simple_record_needs_loto(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fn_simple_record_needs_loto(bigint) TO mom_app;
