-- =====================================================================
-- 30_workflows.sql — 업무 트랜잭션 함수
-- 여러 표를 한꺼번에 바꿔야 하는 일(출하 확정·로트 합격·공구 교체·작업기록서 확정·알림 …)을
-- DB 함수 하나로 묶었다. 서버(app/)는 권한을 먼저 보고 이 함수를 부른다.
-- 함수 안에서도 "사람·역할" 규칙을 다시 확인한다 (NFR-SEC-05, 비서·다른 경로로 들어와도 막힘).
-- 시각 인자를 비우면 app_now() (시연 시계).
-- =====================================================================

-- =====================================================================
-- 1. 알림 (R-38: 규칙이 정하고 비서는 문장만)
-- =====================================================================

-- 알림 1건 만들기. p_refs = {"alarm_event_id": 1, "equipment_id": "VF2-01", ...}
-- 받는 사람: p_recipients가 비면 규칙의 recipient_roles 역할 사용자 전원
-- 묶기 (DOC-07 10.2): 같은 규칙·같은 설비·같은 알람 번호가 1분 안에 3번째부터는 새 알림 없이 repeat_count만 올린다
-- 폭주 (DOC-07 10.3): 최근 10분 긴급·주의 알림이 10건을 넘으면 is_flood
CREATE OR REPLACE FUNCTION fn_raise_notification(
    p_rule text, p_message text, p_refs jsonb DEFAULT '{}'::jsonb, p_at timestamptz DEFAULT NULL,
    p_related_info text DEFAULT NULL, p_message_source text DEFAULT 'DEFAULT',
    p_repeat_stage text DEFAULT NULL, p_prev_stage bigint DEFAULT NULL, p_recipients text[] DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at    timestamptz := coalesce(p_at, app_now());
    r       notification_rule%ROWTYPE;
    v_id    bigint;
    v_alarm text;
    v_same  int;
    v_flood int;
BEGIN
    SELECT * INTO r FROM notification_rule WHERE rule_code = p_rule;
    IF NOT FOUND THEN RAISE EXCEPTION '알림 규칙 % 없음', p_rule USING ERRCODE = '23503'; END IF;
    IF NOT r.is_enabled THEN RETURN NULL; END IF;

    -- 묶기: 알람 알림만
    IF p_rule IN ('ALARM_STOP','ALARM_WARN','ALARM_GUIDE') AND p_refs ? 'alarm_event_id' THEN
        SELECT alarm_code INTO v_alarm FROM alarm_event WHERE alarm_event_id = (p_refs->>'alarm_event_id')::bigint;
        SELECT count(*) INTO v_same FROM alarm_event
         WHERE equipment_id = p_refs->>'equipment_id' AND alarm_code = v_alarm
           AND occurred_at > v_at - interval '1 minute' AND occurred_at <= v_at;
        IF v_same >= 3 THEN
            UPDATE notification n SET repeat_count = n.repeat_count + 1
             WHERE n.notification_id = (
                SELECT n2.notification_id FROM notification n2 JOIN alarm_event a USING (alarm_event_id)
                 WHERE n2.rule_code = p_rule AND n2.equipment_id = p_refs->>'equipment_id' AND a.alarm_code = v_alarm
                   AND n2.raised_at > v_at - interval '1 minute' AND NOT n2.is_processed
                 ORDER BY n2.raised_at DESC LIMIT 1)
            RETURNING n.notification_id INTO v_id;
            IF v_id IS NOT NULL THEN RETURN v_id; END IF;
        END IF;
    END IF;

    SELECT count(*) INTO v_flood FROM notification
     WHERE importance IN ('URGENT','CAUTION') AND raised_at > v_at - interval '10 minutes' AND raised_at <= v_at;

    INSERT INTO notification (rule_code, importance, raised_at, message, related_info, message_source, is_flood,
        alarm_event_id, equipment_id, lot_no, item_no, pm_task_id, tool_id, wo_no, bottleneck_log_id,
        revision_id, result_id, shift_id, buffer_code, cmm_import_id, prev_stage_notification_id,
        repeat_stage_status)
    VALUES (p_rule, r.importance, v_at, p_message, p_related_info, p_message_source, v_flood >= 10,
        (p_refs->>'alarm_event_id')::bigint, p_refs->>'equipment_id', p_refs->>'lot_no', p_refs->>'item_no',
        p_refs->>'pm_task_id', p_refs->>'tool_id', p_refs->>'wo_no', (p_refs->>'bottleneck_log_id')::bigint,
        (p_refs->>'revision_id')::bigint, (p_refs->>'result_id')::bigint, p_refs->>'shift_id',
        p_refs->>'buffer_code', (p_refs->>'cmm_import_id')::bigint, p_prev_stage, p_repeat_stage)
    RETURNING notification_id INTO v_id;

    INSERT INTO notification_recipient (notification_id, user_id, popup_sound)
    SELECT v_id, u.user_id, r.importance = 'URGENT'
      FROM app_user u
     WHERE u.is_active AND (CASE WHEN p_recipients IS NOT NULL THEN u.user_id = ANY (p_recipients)
                                 ELSE u.role_code = ANY (r.recipient_roles) END)
    ON CONFLICT DO NOTHING;
    RETURN v_id;
END $$;

-- 사람이 [처리] (6.36 "알림 종류별 처리" 표). 반복 알람 1단계는 조치 계획 한 줄 필수 → 1단계 닫힘
CREATE OR REPLACE FUNCTION fn_process_notification(p_id bigint, p_actor text, p_memo text DEFAULT NULL,
                                                   p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    n notification%ROWTYPE; r notification_rule%ROWTYPE;
BEGIN
    SELECT * INTO n FROM notification WHERE notification_id = p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '알림 % 없음', p_id USING ERRCODE = '23503'; END IF;
    IF n.is_processed THEN RAISE EXCEPTION '알림 %는 이미 처리됨', p_id USING ERRCODE = '23514'; END IF;
    SELECT * INTO r FROM notification_rule WHERE rule_code = n.rule_code;
    IF r.process_mode = 'AUTO' THEN
        RAISE EXCEPTION '% 알림은 기록이 생기면 자동 처리됨 (사람 처리 없음)', n.rule_code USING ERRCODE = '23514';
    END IF;
    PERFORM fn_require_role(p_actor, r.processor_roles, n.rule_code || ' 알림 처리');
    UPDATE notification
       SET is_processed = true, process_kind = 'MANUAL', processed_by = p_actor, process_memo = p_memo,
           processed_at = v_at,
           repeat_stage_status = CASE WHEN rule_code = 'REPEAT_ALARM' THEN 'S1_CLOSED' ELSE repeat_stage_status END,
           effect_check_due_at = CASE WHEN rule_code = 'REPEAT_ALARM' THEN v_at + interval '7 days' ELSE effect_check_due_at END
     WHERE notification_id = p_id;
END $$;

-- 기록이 생겨서 저절로 처리 (process_kind = AUTO, 처리자 = 그 기록을 남긴 사람)
CREATE OR REPLACE FUNCTION fn_auto_process(p_ids bigint[], p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE sql AS $$
    WITH u AS (
        UPDATE notification SET is_processed = true, process_kind = 'AUTO', processed_by = p_actor,
               processed_at = coalesce(p_at, app_now())
         WHERE notification_id = ANY (p_ids) AND NOT is_processed
        RETURNING 1)
    SELECT count(*)::int FROM u;
$$;

-- 재고 부족 확인 (R-39): 안전 재고 이하면 알림(없을 때만), 넘으면 열린 알림 자동 처리. 완제품은 대상 아님
CREATE OR REPLACE FUNCTION fn_check_stock(p_item_no text, p_actor text DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE i inventory_item%ROWTYPE; v_open bigint[];
BEGIN
    SELECT * INTO i FROM inventory_item WHERE item_no = p_item_no;
    IF i.safety_stock IS NULL THEN RETURN; END IF;
    SELECT array_agg(notification_id) INTO v_open FROM notification
     WHERE rule_code = 'STOCK_LOW' AND item_no = p_item_no AND NOT is_processed;
    IF i.on_hand_qty <= i.safety_stock THEN
        IF v_open IS NULL THEN
            PERFORM fn_raise_notification('STOCK_LOW',
                format('%s 재고 %s%s — 안전 재고 %s 이하', i.item_name, i.on_hand_qty::float8, i.unit, i.safety_stock::float8),
                jsonb_build_object('item_no', p_item_no), p_at,
                p_recipients => (SELECT array_agg(user_id) FROM app_user
                                  WHERE is_active AND role_code IN (i.owner_role, 'MGR')));
        END IF;
    ELSIF v_open IS NOT NULL THEN
        PERFORM fn_auto_process(v_open, p_actor, p_at);
    END IF;
END $$;

-- =====================================================================
-- 2. 문서 버전 (R-35, FR-AST-03)
-- =====================================================================

-- 문서의 지금 상태 (doc_type + doc_key 다형 참조를 여기서 확인)
CREATE OR REPLACE FUNCTION fn_doc_status(p_doc_type text, p_doc_key text) RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE v text;
BEGIN
    CASE p_doc_type
        WHEN 'WORK_ORDER'   THEN SELECT status INTO v FROM maintenance_work_order WHERE wo_no = p_doc_key;
        WHEN 'WORK_RECORD'  THEN SELECT status INTO v FROM work_record WHERE record_no = p_doc_key;
        WHEN 'SHIFT_REPORT' THEN SELECT status INTO v FROM shift_report WHERE shift_id = p_doc_key;
        WHEN 'DAILY_REPORT' THEN SELECT status INTO v FROM daily_report WHERE work_date = p_doc_key::date;
        WHEN 'INTERNAL_DOC' THEN SELECT status INTO v FROM internal_doc WHERE doc_no = p_doc_key;
        WHEN 'PM_RECORD'    THEN SELECT status INTO v FROM pm_record WHERE pm_record_id = p_doc_key::bigint;
        WHEN 'SHIPMENT'     THEN SELECT status INTO v FROM shipment WHERE shipment_no = p_doc_key;
        ELSE RAISE EXCEPTION '문서 종류 % 없음', p_doc_type USING ERRCODE = '22023';
    END CASE;
    RETURN v;
END $$;

-- 새 버전 저장. 문서 본문(각 표)은 서버가 같은 트랜잭션에서 current_version과 함께 고친다.
-- p_changes = [{"field": "특이 사항", "before": "...", "after": "..."}]
-- 반환: 새 version_no
CREATE OR REPLACE FUNCTION fn_save_revision(
    p_doc_type text, p_doc_key text, p_author_kind text, p_author text, p_reason text,
    p_status_after text, p_content jsonb, p_changes jsonb DEFAULT '[]'::jsonb,
    p_internal_doc_rev text DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_status text := fn_doc_status(p_doc_type, p_doc_key);
    v_next   int;
    v_rev    bigint;
    v_locked boolean;
    v_roles  text[];
    v_to     text[];
BEGIN
    IF v_status IS NULL AND NOT EXISTS (SELECT 1 FROM document_revision WHERE doc_type = p_doc_type AND doc_key = p_doc_key) THEN
        -- 첫 버전(v0)은 문서 행보다 먼저 저장될 수 있다 (같은 트랜잭션)
        NULL;
    END IF;
    SELECT coalesce(max(version_no) + 1, 0) INTO v_next FROM document_revision
     WHERE doc_type = p_doc_type AND doc_key = p_doc_key;
    v_locked := v_status = ANY (CASE p_doc_type
        WHEN 'WORK_ORDER'  THEN ARRAY['APPROVED','IN_PROGRESS','DONE','CANCELLED']
        WHEN 'WORK_RECORD' THEN ARRAY['CONFIRMED','CHECKED']
        WHEN 'INTERNAL_DOC' THEN ARRAY['APPROVED']
        ELSE ARRAY['CONFIRMED','REVISED'] END);
    IF v_locked THEN
        IF btrim(coalesce(p_reason, '')) = '' THEN
            RAISE EXCEPTION 'R-35: 확정된 문서(% %)를 고치려면 사유 필수', p_doc_type, p_doc_key USING ERRCODE = '23514';
        END IF;
        -- 확정 뒤 수정은 그 문서의 확정 권한자만 (R-35)
        v_roles := CASE p_doc_type
            WHEN 'SHIFT_REPORT' THEN ARRAY['SUP'] WHEN 'DAILY_REPORT' THEN ARRAY['MGR']
            WHEN 'WORK_RECORD'  THEN ARRAY['MNT','OPR'] WHEN 'WORK_ORDER' THEN ARRAY['MNT','SUP','MGR']
            WHEN 'PM_RECORD'    THEN ARRAY['MNT'] WHEN 'SHIPMENT' THEN ARRAY['SUP']
            WHEN 'INTERNAL_DOC' THEN ARRAY['MGR'] END;
        PERFORM fn_require_role(p_author, v_roles, 'R-35 확정 뒤 수정 (' || p_doc_type || ')');
        IF p_doc_type = 'SHIFT_REPORT' AND p_author <> (SELECT supervisor_user_id FROM shift WHERE shift_id = p_doc_key) THEN
            RAISE EXCEPTION 'R-35: 교대 보고서 확정 뒤 수정은 그 교대 반장만' USING ERRCODE = '23514';
        END IF;
    END IF;
    INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, reason,
                                   status_after, content_snapshot, internal_doc_rev)
    VALUES (p_doc_type, p_doc_key, v_next, p_author_kind, p_author, coalesce(p_at, app_now()), p_reason,
            p_status_after, p_content, p_internal_doc_rev)
    RETURNING revision_id INTO v_rev;
    INSERT INTO document_revision_change (revision_id, field_name, before_value, after_value)
    SELECT v_rev, c->>'field', c->>'before', c->>'after' FROM jsonb_array_elements(p_changes) c;
    -- 문서 수정 알림 (FR-AST-03-07, DOC-07 10.2, 6.36 DOC_REVISED): 확정된 문서를 사유와 함께 고치면
    --   작업지시서 → 담당 보전원, 교대·일일 보고서 → 관리자(MGR), 사내 문서 개정 → 관련 역할 전체. 고친 사람 본인은 뺀다
    IF v_locked THEN
        IF p_doc_type = 'WORK_ORDER' THEN
            SELECT array_remove(ARRAY[assignee_user_id], NULL) INTO v_to FROM maintenance_work_order WHERE wo_no = p_doc_key;
        ELSIF p_doc_type IN ('SHIFT_REPORT','DAILY_REPORT') THEN
            SELECT array_agg(user_id) INTO v_to FROM app_user WHERE is_active AND role_code = 'MGR';
        ELSIF p_doc_type = 'INTERNAL_DOC' THEN
            SELECT array_agg(user_id) INTO v_to FROM app_user WHERE is_active;
        END IF;
        v_to := array_remove(v_to, p_author);
        IF cardinality(v_to) > 0 THEN
            PERFORM fn_raise_notification('DOC_REVISED',
                format('%s %s 수정 (v%s): %s', CASE p_doc_type WHEN 'WORK_ORDER' THEN '작업지시서'
                           WHEN 'SHIFT_REPORT' THEN '교대 보고서' WHEN 'DAILY_REPORT' THEN '일일 보고서' ELSE '사내 문서' END,
                       p_doc_key, v_next, p_reason),
                jsonb_build_object('revision_id', v_rev), p_at, p_recipients => v_to);
        END IF;
    END IF;
    RETURN v_next;
END $$;

-- =====================================================================
-- 3. 로트·검사 (R-25~R-29, R-67~R-69, R-79·R-81)
-- =====================================================================

-- 로트 완료 수량 (R-05): OP-50 공정 실적의 양품 + 재작업
CREATE OR REPLACE FUNCTION fn_lot_completed_qty(p_lot_no text) RETURNS int
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(gq + rq), 0)::int FROM operation_report WHERE lot_no = p_lot_no AND process_code = 'OP-50';
$$;

-- 검사 방식 만들기 (로트를 처음 넣을 때). 열린 보류의 "다음 1~2개 로트"면 강화 (R-28)
CREATE OR REPLACE FUNCTION fn_create_inspection_plan(p_lot_no text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_hold bigint; v_mode text;
BEGIN
    SELECT plan_mode INTO v_mode FROM inspection_plan WHERE lot_no = p_lot_no;
    IF FOUND THEN RETURN v_mode; END IF;
    SELECT h.hold_id INTO v_hold FROM lot_hold h
     WHERE h.lot_no <> p_lot_no
       AND (SELECT count(*) FROM inspection_plan p WHERE p.hold_id = h.hold_id AND p.enhance_reason = 'NEXT_LOT')
           < h.enhanced_next_lots
     ORDER BY h.held_at DESC LIMIT 1;
    IF v_hold IS NOT NULL THEN
        INSERT INTO inspection_plan (lot_no, plan_mode, enhance_reason, hold_id) VALUES (p_lot_no, 'ENHANCED', 'NEXT_LOT', v_hold);
        RETURN 'ENHANCED';
    END IF;
    INSERT INTO inspection_plan (lot_no, plan_mode) VALUES (p_lot_no, 'NORMAL');
    RETURN 'NORMAL';
END $$;

-- 측정할 부품 순번 (R-09): 보통 = 1번과 5의 배수, 강화 = 전부
CREATE OR REPLACE FUNCTION fn_planned_parts(p_lot_no text) RETURNS SETOF int
LANGUAGE sql STABLE AS $$
    SELECT g FROM production_lot l
      JOIN inspection_plan p USING (lot_no)
      CROSS JOIN LATERAL generate_series(1, l.input_qty) g
     WHERE l.lot_no = p_lot_no AND (p.plan_mode = 'ENHANCED' OR g = 1 OR g % 5 = 0);
$$;

-- 로트 보류 (R-27·R-28, FR-PRD-05-06·07). 사람만 (SUP·MGR) — 비서는 제안까지
CREATE OR REPLACE FUNCTION fn_lot_hold(p_lot_no text, p_actor text, p_trigger text, p_reason text,
    p_next_lots int DEFAULT 2, p_alarm_event_id bigint DEFAULT NULL, p_tool_id text DEFAULT NULL,
    p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); v_hold bigint;
BEGIN
    PERFORM 1 FROM production_lot WHERE lot_no = p_lot_no FOR UPDATE;
    IF EXISTS (SELECT 1 FROM shipment_line sl JOIN shipment s USING (shipment_no)
                WHERE sl.lot_no = p_lot_no AND s.status <> 'DRAFT') THEN
        RAISE EXCEPTION '6.8: 이미 출하한 로트 %는 보류할 수 없음', p_lot_no USING ERRCODE = '23514';
    END IF;
    INSERT INTO lot_hold (lot_no, trigger_type, related_alarm_event_id, related_tool_id, hold_reason, held_by, held_at,
                          enhanced_next_lots)
    VALUES (p_lot_no, p_trigger, p_alarm_event_id, p_tool_id, p_reason, p_actor, v_at, p_next_lots)
    RETURNING hold_id INTO v_hold;
    UPDATE production_lot SET status = 'ON_HOLD' WHERE lot_no = p_lot_no;   -- 순서 확인은 트리거
    INSERT INTO inspection_plan (lot_no, plan_mode, enhance_reason, hold_id)
    VALUES (p_lot_no, 'ENHANCED', 'HOLD_LOT', v_hold)
    ON CONFLICT (lot_no) DO UPDATE SET plan_mode = 'ENHANCED', enhance_reason = 'HOLD_LOT', hold_id = v_hold;
    RETURN v_hold;
END $$;

-- 로트 합격 (R-69 ①): 합격 수량(로트 완료 수량)이 완제품 합격 입고 1건으로
CREATE OR REPLACE FUNCTION fn_lot_pass(p_lot_no text, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    l production_lot%ROWTYPE; v_qty int; v_fg text;
BEGIN
    SELECT * INTO l FROM production_lot WHERE lot_no = p_lot_no FOR UPDATE;
    UPDATE production_lot SET status = 'PASSED', judged_at = coalesce(judged_at, v_at) WHERE lot_no = p_lot_no;
    UPDATE inspection_plan SET judgement = 'PASS', judged_at = v_at WHERE lot_no = p_lot_no;
    IF EXISTS (SELECT 1 FROM inventory_txn WHERE source_kind = 'LOT_PASS' AND fg_lot_no = p_lot_no) THEN
        RETURN 0;   -- 해제 때 이미 입고됨 (해제 → 합격)
    END IF;
    v_qty := fn_lot_completed_qty(p_lot_no);   -- 완료 = OP-50 양품 + 재작업 (폐기한 부품은 이미 빠짐)
    SELECT item_no INTO STRICT v_fg FROM inventory_item WHERE category = 'FINISHED';
    IF v_qty > 0 THEN
        INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, fg_lot_no)
        VALUES (v_fg, 'FG_IN', v_qty, v_at, 'LOT_PASS', p_lot_no);
    END IF;
    RETURN v_qty;
END $$;

-- 로트 판정 (R-25·R-27): 측정할 부품을 모두 쟀고 확인 필요 값이 없을 때만.
-- 반환: 'PASS' / 'HOLD_REVIEW' / 'NOT_READY'
CREATE OR REPLACE FUNCTION fn_lot_judge(p_lot_no text, p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    l production_lot%ROWTYPE; p inspection_plan%ROWTYPE; v_missing int; v_fail boolean;
BEGIN
    SELECT * INTO l FROM production_lot WHERE lot_no = p_lot_no FOR UPDATE;
    IF l.status NOT IN ('WAIT_INSPECTION','WAIT_JUDGEMENT') THEN
        RAISE EXCEPTION '로트 %는 판정할 상태가 아님 (%)', p_lot_no, l.status USING ERRCODE = '23514';
    END IF;
    PERFORM fn_create_inspection_plan(p_lot_no);
    SELECT * INTO p FROM inspection_plan WHERE lot_no = p_lot_no;
    IF EXISTS (SELECT 1 FROM inspection_result WHERE lot_no = p_lot_no AND check_status = 'NEEDS_CHECK') THEN
        RETURN 'NOT_READY';
    END IF;
    SELECT count(*) INTO v_missing
      FROM fn_planned_parts(p_lot_no) part
     CROSS JOIN inspection_item i
     WHERE i.product_code = (SELECT product_code FROM production_order WHERE order_no = l.order_no)
       AND i.method = 'CMM' AND i.in_sampling
       AND NOT EXISTS (SELECT 1 FROM inspection_result r
                        WHERE r.lot_no = p_lot_no AND r.part_seq = part AND r.item_seq = i.item_seq AND r.use_for_judgement);
    IF v_missing > 0 THEN
        IF l.status = 'WAIT_INSPECTION' THEN
            UPDATE production_lot SET status = 'WAIT_JUDGEMENT' WHERE lot_no = p_lot_no;
        END IF;
        RETURN 'NOT_READY';
    END IF;
    v_fail := EXISTS (SELECT 1 FROM inspection_result WHERE lot_no = p_lot_no AND use_for_judgement AND judgement = 'FAIL')
              OR EXISTS (SELECT 1 FROM inspection_result WHERE lot_no = p_lot_no AND input_method = 'TABLET' AND judgement = 'FAIL')
              OR coalesce(p.gauge_fail_qty, 0) > 0;
    IF v_fail THEN
        UPDATE production_lot SET status = 'HOLD_REVIEW', judged_at = v_at WHERE lot_no = p_lot_no;
        UPDATE inspection_plan SET judgement = 'HOLD_REVIEW', judged_at = v_at WHERE lot_no = p_lot_no;
        RETURN 'HOLD_REVIEW';
    END IF;
    PERFORM fn_lot_pass(p_lot_no, v_at);
    RETURN 'PASS';
END $$;

-- 로트 해제 (R-69 ②): 전수 검사로 고른 합격 수량만 완제품으로
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

-- 출하 확정 (R-67 합격 로트만, R-68 FIFO, 출하 출고 거래). 반환: 로트 줄 수
CREATE OR REPLACE FUNCTION fn_confirm_shipment(p_shipment_no text, p_actor text, p_fifo_skip_reason text DEFAULT NULL,
                                               p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at  timestamptz := coalesce(p_at, app_now());
    s shipment%ROWTYPE; ln record; v_fg text; v_n int := 0; v_maxkey text; v_skipped text;
BEGIN
    SELECT * INTO s FROM shipment WHERE shipment_no = p_shipment_no FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '출하 % 없음', p_shipment_no USING ERRCODE = '23503'; END IF;
    IF s.status <> 'DRAFT' THEN RAISE EXCEPTION '출하 %는 작성 중이 아님 (%)', p_shipment_no, s.status USING ERRCODE = '23514'; END IF;
    PERFORM fn_require_role(p_actor, ARRAY['SUP'], '출하 확정');
    SELECT item_no INTO STRICT v_fg FROM inventory_item WHERE category = 'FINISHED';

    FOR ln IN
        SELECT sl.lot_no, sl.qty, l.status,
               (SELECT t.txn_at FROM inventory_txn t WHERE t.source_kind = 'LOT_PASS' AND t.fg_lot_no = sl.lot_no) AS passed_at,
               (SELECT coalesce(sum(t.qty_change), 0) FROM inventory_txn t
                 WHERE t.item_no = v_fg AND (t.fg_lot_no = sl.lot_no OR t.ship_lot_no = sl.lot_no)) AS remaining
          FROM shipment_line sl JOIN production_lot l USING (lot_no)
         WHERE sl.shipment_no = p_shipment_no
         FOR UPDATE OF l
    LOOP
        v_n := v_n + 1;
        IF ln.status NOT IN ('PASSED','RELEASED') OR ln.passed_at IS NULL THEN
            RAISE EXCEPTION 'R-67: 로트 %는 출하할 수 없음 (상태 %)', ln.lot_no, ln.status USING ERRCODE = '23514';
        END IF;
        IF v_at <= ln.passed_at THEN
            RAISE EXCEPTION 'R-67: 출하 시각이 로트 % 합격 시각보다 빠름', ln.lot_no USING ERRCODE = '23514';
        END IF;
        IF ln.qty > ln.remaining THEN
            RAISE EXCEPTION 'R-67: 로트 % 출하 수량 %가 남은 완제품 %보다 많음', ln.lot_no, ln.qty, ln.remaining
                USING ERRCODE = '23514';
        END IF;
        UPDATE shipment_line SET lot_passed_at = ln.passed_at WHERE shipment_no = p_shipment_no AND lot_no = ln.lot_no;
    END LOOP;
    IF v_n = 0 THEN RAISE EXCEPTION '출하 %에 로트 줄이 없음', p_shipment_no USING ERRCODE = '23514'; END IF;

    -- R-68 FIFO: 이번 출하에서 가장 늦게 합격한 로트보다 먼저 합격했는데 빠진 로트(남은 수량 > 0)가 있으면 사유 필수
    -- 순서 = 합격 날짜(한국 시간) → 로트 번호
    SELECT max(to_char(sl.lot_passed_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD') || '|' || sl.lot_no) INTO v_maxkey
      FROM shipment_line sl WHERE sl.shipment_no = p_shipment_no;
    SELECT string_agg(c.lot_no, ', ' ORDER BY c.lot_no) INTO v_skipped
      FROM (SELECT l.lot_no, t.txn_at,
                   (SELECT coalesce(sum(x.qty_change), 0) FROM inventory_txn x
                     WHERE x.item_no = v_fg AND (x.fg_lot_no = l.lot_no OR x.ship_lot_no = l.lot_no)) AS remaining
              FROM production_lot l
              JOIN inventory_txn t ON t.source_kind = 'LOT_PASS' AND t.fg_lot_no = l.lot_no
             WHERE l.status IN ('PASSED','RELEASED')
               AND l.lot_no NOT IN (SELECT lot_no FROM shipment_line WHERE shipment_no = p_shipment_no)) c
     WHERE c.remaining > 0
       AND to_char(c.txn_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD') || '|' || c.lot_no < v_maxkey;
    IF v_skipped IS NOT NULL AND btrim(coalesce(p_fifo_skip_reason, '')) = '' THEN
        RAISE EXCEPTION 'R-68: 먼저 합격한 로트(%)를 두고 나중 로트를 고름 — FIFO 건너뜀 사유 필수', v_skipped
            USING ERRCODE = '23514';
    END IF;

    UPDATE shipment SET status = 'CONFIRMED', confirmed_by = p_actor, shipped_at = v_at,
                        fifo_skip_reason = CASE WHEN v_skipped IS NOT NULL THEN p_fifo_skip_reason END
     WHERE shipment_no = p_shipment_no;
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, shipment_no, ship_lot_no)
    SELECT v_fg, 'SHIP_OUT', -sl.qty, v_at, p_actor, 'SHIPMENT', sl.shipment_no, sl.lot_no
      FROM shipment_line sl WHERE sl.shipment_no = p_shipment_no;
    RETURN v_n;
END $$;

-- =====================================================================
-- 4. 공구 (R-10·R-40·R-41)
-- =====================================================================

-- 공정 실적에 부품 수만큼 공구 사용량을 더한다 (공구 사용 기록 B안: 교체가 끼면 구간을 나눔)
CREATE OR REPLACE FUNCTION fn_add_tool_usage(p_op_report_id bigint, p_parts_qty int, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    op operation_report%ROWTYPE; t record; cur tool_usage%ROWTYPE; v_change tool_change%ROWTYPE;
    v_usage numeric; v_new_cum numeric; v_n int := 0;
BEGIN
    SELECT * INTO op FROM operation_report WHERE op_report_id = p_op_report_id;
    IF op.process_code <> 'OP-30' THEN RETURN 0; END IF;
    FOR t IN SELECT tl.tool_id, tl.cum_usage, tt.usage_per_part, tt.life_limit
               FROM tool tl JOIN tool_type tt USING (item_no)
              WHERE tl.equipment_id = op.equipment_id AND tl.tool_role = 'IN_USE' AND tl.is_active
              FOR UPDATE OF tl
    LOOP
        v_usage := p_parts_qty * t.usage_per_part;
        v_new_cum := t.cum_usage + v_usage;
        SELECT * INTO v_change FROM tool_change
         WHERE tool_id = t.tool_id AND changed_at >= op.start_at AND changed_at <= v_at
         ORDER BY changed_at DESC LIMIT 1;
        SELECT * INTO cur FROM tool_usage WHERE tool_id = t.tool_id AND op_report_id = p_op_report_id
         ORDER BY seg DESC LIMIT 1;
        IF cur.seg IS NULL THEN
            INSERT INTO tool_usage VALUES (t.tool_id, p_op_report_id, 1, p_parts_qty, v_usage, v_new_cum, v_change.tool_change_id, v_at);
        ELSIF v_change.tool_change_id IS NOT NULL AND cur.tool_change_id IS DISTINCT FROM v_change.tool_change_id
              AND v_change.changed_at > cur.recorded_at THEN
            INSERT INTO tool_usage VALUES (t.tool_id, p_op_report_id, cur.seg + 1, p_parts_qty, v_usage, v_new_cum, v_change.tool_change_id, v_at);
        ELSE
            UPDATE tool_usage SET parts_qty = parts_qty + p_parts_qty, usage_qty = usage_qty + v_usage,
                                  cum_after = v_new_cum, recorded_at = v_at
             WHERE tool_id = t.tool_id AND op_report_id = p_op_report_id AND seg = cur.seg;
        END IF;
        UPDATE tool SET cum_usage = v_new_cum WHERE tool_id = t.tool_id;
        -- R-40 사용률 90%를 넘는 순간 교체 알림 (열린 것이 없을 때만)
        IF v_new_cum >= 0.9 * t.life_limit AND t.cum_usage < 0.9 * t.life_limit
           AND NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TOOL_LIFE_90' AND tool_id = t.tool_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('TOOL_LIFE_90',
                format('%s 공구 수명 %s%% — 교체 준비', t.tool_id, round(100 * v_new_cum / t.life_limit)),
                jsonb_build_object('tool_id', t.tool_id, 'equipment_id', op.equipment_id), v_at);
        END IF;
        v_n := v_n + 1;
    END LOOP;
    RETURN v_n;
END $$;

-- 공구 교체: 교체 기록 + 누적 0 + 재고 차감(페이스밀 5개) + 수명 알림 자동 처리
CREATE OR REPLACE FUNCTION fn_tool_change(p_tool_id text, p_actor text, p_reason text,
                                          p_alarm_event_id bigint DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now()); t record; v_id bigint; v_open bigint[];
BEGIN
    SELECT tl.*, tt.deduct_qty_per_change INTO t FROM tool tl JOIN tool_type tt USING (item_no)
     WHERE tl.tool_id = p_tool_id FOR UPDATE OF tl;
    IF NOT FOUND THEN RAISE EXCEPTION '공구 % 없음', p_tool_id USING ERRCODE = '23503'; END IF;
    INSERT INTO tool_change (tool_id, changed_at, changed_by, cum_before, change_reason, related_alarm_event_id)
    VALUES (p_tool_id, v_at, p_actor, t.cum_usage, p_reason, p_alarm_event_id)
    RETURNING tool_change_id INTO v_id;
    UPDATE tool SET cum_usage = 0, last_changed_at = v_at WHERE tool_id = p_tool_id;
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, tool_change_id)
    VALUES (t.item_no, 'USE', -t.deduct_qty_per_change, v_at, p_actor, 'TOOL_CHANGE', v_id);
    SELECT array_agg(notification_id) INTO v_open FROM notification
     WHERE rule_code = 'TOOL_LIFE_90' AND tool_id = p_tool_id AND NOT is_processed;
    IF v_open IS NOT NULL THEN PERFORM fn_auto_process(v_open, p_actor, v_at); END IF;
    PERFORM fn_check_stock(t.item_no, p_actor, v_at);
    RETURN v_id;
END $$;

-- =====================================================================
-- 5. 정비 (R-02·R-32·R-34·R-70·R-71)
-- =====================================================================

-- 작업기록 확정: 잠금·표지·역할 확인(트리거) → 사용 부품 재고 차감 → 작업지시서 완료 → 알림 자동 처리
CREATE OR REPLACE FUNCTION fn_confirm_work_record(p_record_no text, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    w work_record%ROWTYPE; v_alarm bigint; v_ids bigint[]; v_stage bigint; p record;
BEGIN
    SELECT * INTO w FROM work_record WHERE record_no = p_record_no FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '작업기록 % 없음', p_record_no USING ERRCODE = '23503'; END IF;
    IF w.status NOT IN ('AI_DRAFT','EDITING') THEN
        RAISE EXCEPTION '작업기록 %는 확정할 상태가 아님 (%)', p_record_no, w.status USING ERRCODE = '23514';
    END IF;
    UPDATE work_record
       SET status = 'CONFIRMED', confirmed_by = p_actor, confirmed_at = v_at, end_at = coalesce(end_at, v_at),
           repair_min = coalesce(repair_min, round(extract(epoch FROM (coalesce(end_at, v_at) - start_at)) / 60, 2))
     WHERE record_no = p_record_no;

    -- R-34 사용 부품만큼 재고 사용 거래
    FOR p IN SELECT * FROM work_record_part WHERE record_no = p_record_no LOOP
        INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, work_record_no, work_record_item_no)
        VALUES (p.item_no, 'USE', -p.qty, v_at, p_actor, 'WORK_RECORD', p_record_no, p.item_no);
        PERFORM fn_check_stock(p.item_no, p_actor, v_at);
    END LOOP;

    v_alarm := w.alarm_event_id;
    IF w.record_type = 'FULL' THEN
        -- 작업지시서 완료 계기 = 짝 작업기록서 확정 (6.13)
        UPDATE maintenance_work_order SET status = 'DONE', completed_at = v_at WHERE wo_no = w.wo_no
        RETURNING coalesce(v_alarm, alarm_event_id), trigger_notification_id INTO v_alarm, v_stage;
        IF v_stage IS NOT NULL THEN
            UPDATE notification SET repeat_stage_status = 'S2_CHECKED', effect_check_due_at = v_at + interval '7 days'
             WHERE notification_id = v_stage;
            PERFORM fn_auto_process(ARRAY[v_stage], p_actor, v_at);
        END IF;
    END IF;
    -- 알람 알림 자동 처리 (6.36: ALARM_STOP·ALARM_WARN)
    IF v_alarm IS NOT NULL THEN
        SELECT array_agg(notification_id) INTO v_ids FROM notification
         WHERE alarm_event_id = v_alarm AND rule_code IN ('ALARM_STOP','ALARM_WARN') AND NOT is_processed;
        IF v_ids IS NOT NULL THEN PERFORM fn_auto_process(v_ids, p_actor, v_at); END IF;
    END IF;
    -- 다른 공정 원인 점검 간이 기록 → 원인 점검 요청·2단계 알림 처리 (R-70)
    IF w.cause_check_notification_id IS NOT NULL THEN
        SELECT prev_stage_notification_id INTO v_stage FROM notification WHERE notification_id = w.cause_check_notification_id;
        PERFORM fn_auto_process(ARRAY[w.cause_check_notification_id], p_actor, v_at);
        IF v_stage IS NOT NULL THEN
            UPDATE notification SET repeat_stage_status = 'S2_CHECKED', effect_check_due_at = v_at + interval '7 days'
             WHERE notification_id = v_stage;
            PERFORM fn_auto_process(ARRAY[v_stage], p_actor, v_at);
        END IF;
    END IF;
END $$;

-- 반복 알람 판정 (R-70): 알람 1건이 들어온 뒤 부른다. 반환: 'NONE' / 'STAGE1' / 'STAGE2'
--   1단계 = 같은 설비·같은 알람 7일 안 3번 이상 (조치 진행 중인 알람은 빼고 센다 — 1분 묶음은 1번)
--   2단계 = 1단계 닫힘(조치 계획 저장) 뒤 7일 안에 다시 남
-- 문장(message)은 기본 문구. 비서 문장은 AI 비서 ②가 나중에 고친다 (message_source = ASSISTANT)
CREATE OR REPLACE FUNCTION fn_check_repeat_alarm(p_alarm_event_id bigint) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    a alarm_event%ROWTYPE; v_cnt int; v_prev notification%ROWTYPE; v_id bigint; v_proc text;
BEGIN
    SELECT * INTO a FROM alarm_event WHERE alarm_event_id = p_alarm_event_id;
    -- 이미 열린 1·2단계가 있으면 새로 만들지 않는다 (재발로 2단계가 될지만 본다)
    SELECT n.* INTO v_prev FROM notification n JOIN alarm_event e USING (alarm_event_id)
     WHERE n.rule_code IN ('REPEAT_ALARM','REPEAT_ALARM_2') AND e.equipment_id = a.equipment_id
       AND e.alarm_code = a.alarm_code AND n.repeat_stage_status IN ('S1_CLOSED','S2_CHECKED','S1_OPEN','S2_OPEN')
     ORDER BY n.raised_at DESC LIMIT 1;
    IF v_prev.notification_id IS NOT NULL THEN
        IF v_prev.repeat_stage_status IN ('S1_OPEN','S2_OPEN') THEN RETURN 'NONE'; END IF;
        IF a.occurred_at <= v_prev.effect_check_due_at THEN
            UPDATE notification SET repeat_stage_status = 'ESCALATED' WHERE notification_id = v_prev.notification_id;
            v_id := fn_raise_notification('REPEAT_ALARM_2',
                format('%s 알람 %s — 지난 조치 효과 없음 (조치 뒤 7일 안 재발)', a.equipment_id, a.alarm_code),
                jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id),
                a.occurred_at, p_repeat_stage => 'S2_OPEN', p_prev_stage => v_prev.notification_id);
            v_proc := fn_equipment_process(a.equipment_id);
            IF v_proc = 'OP-30' THEN
                -- OP-30 2단계 → 원인 점검 작업지시서 초안 자동 (FR-MNT-03-01 ②, 2026-10-20)
                PERFORM fn_auto_work_order_draft(a.alarm_event_id, 'REPEAT_2', v_id);
            ELSE
                -- 다른 공정: 작업지시서 없이 MNT에게 원인 점검 요청 (R-71)
                PERFORM fn_raise_notification('CAUSE_CHECK_REQUEST',
                    format('%s 알람 %s 원인 점검 요청', a.equipment_id, a.alarm_code),
                    jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id),
                    a.occurred_at, p_prev_stage => v_id);
            END IF;
            RETURN 'STAGE2';
        END IF;
        UPDATE notification SET repeat_stage_status = 'EFFECTIVE'
         WHERE notification_id = v_prev.notification_id AND repeat_stage_status IN ('S1_CLOSED','S2_CHECKED');
    END IF;
    SELECT count(DISTINCT date_trunc('minute', e.occurred_at)) INTO v_cnt FROM alarm_event e
     WHERE e.equipment_id = a.equipment_id AND e.alarm_code = a.alarm_code
       AND e.occurred_at > a.occurred_at - interval '7 days' AND e.occurred_at <= a.occurred_at
       AND NOT EXISTS (SELECT 1 FROM work_record w WHERE w.alarm_event_id = e.alarm_event_id AND w.status IN ('AI_DRAFT','EDITING')
                         AND w.alarm_event_id <> a.alarm_event_id);
    IF v_cnt >= 3 THEN
        PERFORM fn_raise_notification('REPEAT_ALARM',
            format('%s 알람 %s 7일 안 %s번', a.equipment_id, a.alarm_code, v_cnt),
            jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id),
            a.occurred_at, p_repeat_stage => 'S1_OPEN');
        RETURN 'STAGE1';
    END IF;
    RETURN 'NONE';
END $$;

-- =====================================================================
-- 6. 교대 목표 이월·총 목표 (R-46·R-88, DOC-07 §4.1 — 2026-10-07 팀 UI 검토)
--   이월은 같은 생산일 주간 → 야간만: 야간 carry_over_qty = max(0, 주간 목표 − 주간 실적). 주간은 늘 0.
--   총 목표 = target_qty + carry_over_qty. 하루 목표(work_day.daily_target_qty 180)는 고정 — 이월을 더하지 않고,
--   야간이 못 채운 수량은 다음 날로 넘기지 않고 그날 부족(180 − 하루 실적)으로 남는다.
-- =====================================================================

-- R-46 교대 실적 = 그 교대에 OP-50을 마친 GQ + RQ (원기록 집계)
CREATE OR REPLACE FUNCTION fn_shift_actual_qty(p_shift_id text) RETURNS int
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(gq + rq), 0)::int FROM operation_report WHERE shift_id = p_shift_id AND process_code = 'OP-50';
$$;

-- 그 생산일 야간 이월을 다시 계산한다. 반환: 야간 이월 값 (그날 야간 교대가 없으면 NULL)
--   주간 실적 = 주간 교대 보고서가 확정됐으면 그 실적, 아니면 원기록 집계 (이때 이월은 "잠정" — v_shift_target)
--   주간 기록(교대 보고서도 공정 실적도)이 없으면 0
-- 부르는 곳: 주간 교대 보고서 초안(17:00, 야간 시작 전), 주간 교대 보고서 확정(다시 계산), 스케줄러(지금 야간),
--           생성기 데이터 적재 뒤(tools/load_generated.py)
CREATE OR REPLACE FUNCTION fn_refresh_carry_over(p_work_date date) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE
    d shift%ROWTYPE; v_night shift%ROWTYPE; v_confirmed int; v_carry int := 0;
BEGIN
    SELECT * INTO v_night FROM shift WHERE work_date = p_work_date AND shift_type = 'NIGHT';
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO d FROM shift WHERE work_date = p_work_date AND shift_type = 'DAY';
    IF FOUND AND (EXISTS (SELECT 1 FROM shift_report r WHERE r.shift_id = d.shift_id)
                  OR EXISTS (SELECT 1 FROM operation_report o WHERE o.shift_id = d.shift_id)) THEN
        SELECT r.actual_qty INTO v_confirmed FROM shift_report r
         WHERE r.shift_id = d.shift_id AND r.status IN ('CONFIRMED','REVISED');
        v_carry := greatest(0, d.target_qty - coalesce(v_confirmed, fn_shift_actual_qty(d.shift_id)));
    END IF;
    UPDATE shift SET carry_over_qty = v_carry WHERE shift_id = v_night.shift_id AND carry_over_qty <> v_carry;
    -- 아직 확정 전인 야간 교대 보고서 초안의 총 목표(프로그램 칸)도 맞춘다. 확정된 보고서는 고치지 않는다 (R-35)
    UPDATE shift_report SET target_qty = v_night.target_qty + v_carry
     WHERE shift_id = v_night.shift_id AND status IN ('AI_DRAFT','EDITING') AND target_qty <> v_night.target_qty + v_carry;
    RETURN v_carry;
END $$;

-- 고장 손실 수량 (추정, R-47·DOC-07 5.3): [p_from, p_to) 안에서 시작한 고장 정지 구간(정지 사유 FAILURE 그룹, 또는 DOWN)의
-- 정지 손실 합. 아직 끝나지 않은 구간은 p_to까지의 길이 ÷ 그 설비 기준 사이클로 센다 (3D 라인 뷰 "지금까지 손실")
CREATE OR REPLACE FUNCTION fn_failure_loss_qty(p_from timestamptz, p_to timestamptz) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(round(sum(CASE WHEN st.end_at IS NULL OR st.end_at > p_to
                                   THEN extract(epoch FROM (p_to - st.start_at)) / 60 / nullif(e.std_cycle_min, 0)
                                   ELSE st.stop_loss_qty END), 2), 0)
      FROM equipment_state_log st
      JOIN equipment e USING (equipment_id)
      LEFT JOIN downtime_reason dr ON dr.reason_code = coalesce(st.reason_code, st.reason_suggested_code)
     WHERE st.state_code <> 'RUN' AND (st.state_code = 'DOWN' OR dr.reason_group = 'FAILURE')
       AND st.start_at >= p_from AND st.start_at < p_to;
$$;

-- 속도 손실 수량 (추정, R-47): [p_from, p_to) 안에서 바뀐 병목 구간의 속도 손실 합 (구간이 끝날 때 저장된 값)
--   2026-10-20: 구간이 끝날 때 trg_bottleneck_live(views/30_live_rules.sql)가 값을 채운다 (전에는 채우는 곳이 없어 실시간은 늘 0).
--   지금 열려 있는 구간(마지막 기록)은 그때까지를 바로 계산해 더한다 (fn_interval_losses, functions/35_live_calc.sql)
CREATE OR REPLACE FUNCTION fn_speed_loss_qty(p_from timestamptz, p_to timestamptz) RETURNS numeric
LANGUAGE plpgsql STABLE AS $$
DECLARE v_closed numeric; o bottleneck_log%ROWTYPE; v_open numeric := 0; v_end timestamptz := least(p_to, app_now());
BEGIN
    SELECT coalesce(sum(b.speed_loss_qty), 0) INTO v_closed FROM bottleneck_log b
     WHERE b.changed_at >= p_from AND b.changed_at < p_to
       AND EXISTS (SELECT 1 FROM bottleneck_log n WHERE n.changed_at > b.changed_at);
    SELECT * INTO o FROM bottleneck_log WHERE changed_at <= app_now() ORDER BY changed_at DESC LIMIT 1;
    IF FOUND AND o.cause_code IN ('C1','C2','C3') AND o.changed_at < p_to AND v_end > greatest(o.changed_at, p_from) THEN
        v_open := (fn_interval_losses(greatest(o.changed_at, p_from), v_end, o.cause_code)).speed_loss_qty;
    END IF;
    RETURN v_closed + coalesce(v_open, 0);
END $$;

-- =====================================================================
-- 7. 알람 관련 재고 품목 (alarm_related_item, 논리 ERD 5.C.8·R-89) — 보고 순위 같은 원인 묶기
--   사내 문서에 적힌 연결만. 알람 코드집·재고 품목은 생성기·목업이 넣으므로, 있는 코드만 넣고 여러 번 불러도 된다.
--   부르는 곳: 시드(seed/40), 목업(dev/10), 생성기 적재 뒤(tools/load_generated.py). 반환: 새로 넣은 줄 수
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_seed_alarm_related_items() RETURNS int
LANGUAGE sql AS $$
    WITH ins AS (
        INSERT INTO alarm_related_item (alarm_code, item_no, relation_note, source_section)
        SELECT v.alarm_code, v.item_no, v.note, v.src
          FROM (VALUES
            ('2075', 'CS-WLUB', '축 윤활유 저장소가 비면 나는 알람 — 탱크를 채운다 (매월 윤활유 저장소 양 점검·보충)',
             '알람 코드집 DOC-02 §4.11, 예방 정비 기준서 DOC-04 §4.1'),
            ('2073', 'CS-WLUB', '축 윤활 압력 감지 불능 — 윤활유 탱크를 먼저 본다. 2075를 두면 2073으로 이어짐',
             '알람 코드집 DOC-02 §4.10, 예방 정비 기준서 DOC-04 §4.1'),
            ('805',  'CS-SLUB', '주축 윤활 부족 — 주축 윤활유 저장소 양이 적음 (매월 탱크 양 점검 때 보충)',
             '예방 정비 기준서 DOC-04 §4.4')
          ) AS v(alarm_code, item_no, note, src)
         WHERE EXISTS (SELECT 1 FROM alarm_master m WHERE m.alarm_code = v.alarm_code)
           AND EXISTS (SELECT 1 FROM inventory_item i WHERE i.item_no = v.item_no)
        ON CONFLICT (alarm_code, item_no) DO NOTHING
        RETURNING 1)
    SELECT count(*)::int FROM ins;
$$;

-- 불량을 폐기로 처분하면 로트 폐기 수량을 더한다 (production_lot.scrap_qty = 폐기한 부품 수, 생성기와 같은 뜻).
-- 로트 전체 폐기(보류 → 폐기 승인)는 fn_lot_scrap_approve가 따로 채운다. 대량 적재 중에는 CSV 값을 그대로 둔다
CREATE OR REPLACE FUNCTION trg_defect_scrap() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.disposition = 'SCRAP' AND current_setting('app.loading', true) IS DISTINCT FROM 'on' THEN
        UPDATE production_lot SET scrap_qty = least(input_qty, scrap_qty + NEW.qty) WHERE lot_no = NEW.lot_no;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER defect_scrap AFTER INSERT ON defect_record FOR EACH ROW EXECUTE FUNCTION trg_defect_scrap();

-- 생성기 적재 뒤 "지금 상태" 칸 맞추기 (tools/load_generated.py가 부름). 기준 정보 CSV(masters)는 9/1 시작 상태라서
--   공구 누적 사용량·마지막 교체 시각 = 마지막 사용·교체 기록 (R-10, T05 9/30 끝 90% — 1014 수정사항 3.1)
-- 반환: 고친 공구 수
CREATE OR REPLACE FUNCTION fn_sync_after_load() RETURNS int LANGUAGE plpgsql AS $$
DECLARE n int;
BEGIN
    WITH last_use AS (
        SELECT DISTINCT ON (tool_id) tool_id, cum_after, recorded_at FROM tool_usage ORDER BY tool_id, recorded_at DESC, seg DESC
    ), last_change AS (
        SELECT tool_id, max(changed_at) AS changed_at FROM tool_change GROUP BY tool_id
    ), u AS (
        UPDATE tool t SET cum_usage = CASE WHEN c.changed_at IS NOT NULL AND (lu.recorded_at IS NULL OR lu.recorded_at < c.changed_at)
                                           THEN 0 ELSE coalesce(lu.cum_after, t.cum_usage) END,
                          last_changed_at = coalesce(c.changed_at, t.last_changed_at)
          FROM tool t2 LEFT JOIN last_use lu USING (tool_id) LEFT JOIN last_change c USING (tool_id)
         WHERE t.tool_id = t2.tool_id AND (lu.tool_id IS NOT NULL OR c.tool_id IS NOT NULL)
        RETURNING 1)
    SELECT count(*) INTO n FROM u;
    -- 10/1 실시간 기록의 예방 정비 기록(작성 중 DRAFT)은 문서 버전이 없다 → 사람이 처음 저장한 v0을 남긴다 (R-35)
    INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, reason, status_after,
                                   content_snapshot)
    SELECT 'PM_RECORD', p.pm_record_id::text, 0, 'HUMAN', p.recorded_by, p.done_at, NULL, p.status,
           jsonb_build_object('pm_task_id', p.pm_task_id, 'result', p.result, 'memo', p.memo)
      FROM pm_record p
     WHERE p.current_version = 0
       AND NOT EXISTS (SELECT 1 FROM document_revision r WHERE r.doc_type = 'PM_RECORD' AND r.doc_key = p.pm_record_id::text);
    -- 교대 보고서가 아직 없는 날(10/1 실시간)의 야간 이월 (R-88)
    PERFORM fn_refresh_carry_over(w.work_date) FROM work_day w
     WHERE EXISTS (SELECT 1 FROM shift s WHERE s.work_date = w.work_date)
       AND NOT EXISTS (SELECT 1 FROM shift s JOIN shift_report r USING (shift_id) WHERE s.work_date = w.work_date);
    RETURN n;
END $$;
