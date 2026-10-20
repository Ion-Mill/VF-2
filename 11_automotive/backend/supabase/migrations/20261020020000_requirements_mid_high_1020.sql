-- =====================================================================
-- 2026-10-20 요구사항 대조 상·중 보강 (구현_중_수정사항/1020_수정간단내용.md 36장) — 이미 올린 mom-db(35장까지)에 바뀐 것만
--   상: 실시간 알림(병목 이동·재공 경고·관리도 이상·납기 위험)과 속도 손실, OP-30 정지·반복 2단계 작업지시서 초안 자동,
--       보고서 칸, 의심 로트 (API 쿼리)
--   중: 알림 1분 묶기·폭주 해제, 재고 거래 → 재고 부족, CMM 파일 오류 처리, 반복 알람 2단계·효과 확인, 예방 정비 알림 받는 사람,
--       인계 사항·오늘의 문제 글 모양, 진행 중 작업지시서, 정비 시작·끝, 강화 → 보통, Cpk 미달 전수 측정
-- 같은 내용이 db/ 원본에 있다 (문장 단위로 a4ae023과 비교해 만든 것). 스키마 주인(postgres)으로 한 번
-- =====================================================================
SET client_min_messages = warning;

-- ---------------------------------------------------------------- db/schema/70_documents.sql
-- 알람 점검 순서 [물리 추가, 2026-10-20 — 작업지시서 초안 자동 생성 FR-MNT-03-01·05, 1018 §23 "점검 순서를 DB로"]
--   DOC-03 머리말 "점검 순서"를 줄마다: SYMPTOM 증상 첫 문장 / OPR ★ 작업자 줄 / MNT 보전 줄. 문서 문장 그대로.
--   시드 db/seed/50_alarm_check_steps.sql (tools/gen_alarm_steps.py가 화면 도구 data.json에서 만듦). 알람 코드집은 시드보다
--   늦게(생성기 적재) 들어오므로 외래 키를 걸지 않는다 — 알람 번호로 찾는 문서 기준 표
CREATE TABLE alarm_check_step (
    alarm_code  varchar(20) NOT NULL,
    seq         smallint    NOT NULL CHECK (seq >= 0),
    step_kind   varchar(7)  NOT NULL CHECK (step_kind IN ('SYMPTOM','OPR','MNT')),
    step_text   text        NOT NULL,
    PRIMARY KEY (alarm_code, seq)
);


-- ---------------------------------------------------------------- db/functions/20_integrity.sql
-- 재고가 움직이면 그 품목의 재고 부족을 다시 본다 (R-39, FR-AST-02-07·FR-INV-01-07 — 2026-10-20). 전에는 작업기록서 확정·공구
--   교체·실사 API만 불러, 예방 정비 확정의 소모품 차감으로 줄어도 재고 부족 알림이 안 떴다. 이름 순서상 inventory_txn_apply 뒤에 돈다
CREATE OR REPLACE FUNCTION trg_inventory_txn_stock() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    PERFORM fn_check_stock(NEW.item_no, NEW.txn_by, NEW.txn_at);
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS inventory_txn_stock ON inventory_txn;
CREATE TRIGGER inventory_txn_stock AFTER INSERT ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_txn_stock();


-- ---------------------------------------------------------------- db/functions/30_workflows.sql
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
-- 묶기 (DOC-07 10.2, FR-AST-02-11 "1분 안 3번 → 알림 1건"): 같은 규칙·같은 설비·같은 알람 번호가 첫 알림 뒤 1분 안에 또 나면
--   새 알림 없이 그 첫 알림의 repeat_count만 올린다 (2026-10-20 — 전에는 3번째부터라 3번이 2건이었다. 알림은 바로 보내야 해서
--   "3번째가 올지" 기다리지 않는다 [제안])
-- 폭주 (DOC-07 10.3, FR-AST-02-12): 최근 10분 긴급·주의가 10건을 넘으면 켜지고 5건 아래로 내려가면 풀린다 (fn_flood_state)
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

    -- 묶기: 알람 알림만 — 1분 안의 첫 알림(같은 설비·같은 알람 번호, 처리 전)에 횟수만 더한다
    IF p_rule IN ('ALARM_STOP','ALARM_WARN','ALARM_GUIDE') AND p_refs ? 'alarm_event_id' THEN
        SELECT alarm_code INTO v_alarm FROM alarm_event WHERE alarm_event_id = (p_refs->>'alarm_event_id')::bigint;
        UPDATE notification n SET repeat_count = n.repeat_count + 1
         WHERE n.notification_id = (
            SELECT n2.notification_id FROM notification n2 JOIN alarm_event a USING (alarm_event_id)
             WHERE n2.rule_code = p_rule AND n2.equipment_id = p_refs->>'equipment_id' AND a.alarm_code = v_alarm
               AND n2.raised_at > v_at - interval '1 minute' AND n2.raised_at <= v_at AND NOT n2.is_processed
             ORDER BY n2.raised_at LIMIT 1)
        RETURNING n.notification_id INTO v_id;
        IF v_id IS NOT NULL THEN RETURN v_id; END IF;
    END IF;

    v_flood := (SELECT CASE WHEN f.active OR (r.importance IN ('URGENT','CAUTION') AND f.count_10min + 1 > 10) THEN 1 ELSE 0 END
                  FROM fn_flood_state(v_at) f);

    INSERT INTO notification (rule_code, importance, raised_at, message, related_info, message_source, is_flood,
        alarm_event_id, equipment_id, lot_no, item_no, pm_task_id, tool_id, wo_no, bottleneck_log_id,
        revision_id, result_id, shift_id, buffer_code, cmm_import_id, prev_stage_notification_id,
        repeat_stage_status)
    VALUES (p_rule, r.importance, v_at, p_message, p_related_info, p_message_source, v_flood = 1,
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

-- 알림 폭주 상태 (DOC-07 10.3, FR-AST-02-12 — 2026-10-20): 최근 10분 긴급·주의 알림 수. 10건을 넘으면 켜지고, 켜진 뒤에는
--   5건 아래로 내려갈 때까지 유지 (그 10분 안에 폭주 표시된 알림이 있으면 켜진 상태로 본다)
CREATE OR REPLACE FUNCTION fn_flood_state(p_at timestamptz DEFAULT NULL, OUT active boolean, OUT count_10min int)
LANGUAGE sql STABLE AS $$
    WITH t AS (SELECT coalesce(p_at, app_now()) AS at),
    c AS (SELECT count(*)::int AS n, bool_or(is_flood) AS any_flood FROM notification, t
           WHERE importance IN ('URGENT','CAUTION') AND raised_at > t.at - interval '10 minutes' AND raised_at <= t.at)
    SELECT c.n > 10 OR (c.n >= 5 AND coalesce(c.any_flood, false)), c.n FROM c;
$$;

-- 검사 방식 만들기 (로트를 처음 넣을 때). 열린 보류의 "다음 1~2개 로트"면 강화 (R-28)
CREATE OR REPLACE FUNCTION fn_create_inspection_plan(p_lot_no text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_hold bigint; v_mode text;
BEGIN
    SELECT plan_mode INTO v_mode FROM inspection_plan WHERE lot_no = p_lot_no;
    IF FOUND THEN RETURN v_mode; END IF;
    SELECT h.hold_id INTO v_hold FROM lot_hold h
     WHERE h.lot_no <> p_lot_no AND h.normal_resumed_at IS NULL          -- 보통으로 돌아간 보류는 빼기 (R-29, 2026-10-20)
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
        -- 조치 작업이 진행 중(같은 설비·같은 알람의 작업지시서가 끝나지 않았거나 작업기록서가 확정 전)일 때 난 알람은 재발로 세지 않는다
        --   (FR-AST-02-18, R-70 — 2026-10-20: 전에는 1단계 셈에만 적용)
        IF EXISTS (SELECT 1 FROM maintenance_work_order o
                     LEFT JOIN notification tn ON tn.notification_id = o.trigger_notification_id
                     JOIN alarm_event e ON e.alarm_event_id = coalesce(o.alarm_event_id, tn.alarm_event_id)
                    WHERE e.equipment_id = a.equipment_id AND e.alarm_code = a.alarm_code AND e.alarm_event_id <> a.alarm_event_id
                      AND o.status NOT IN ('DONE','CANCELLED'))
           OR EXISTS (SELECT 1 FROM work_record w JOIN alarm_event e ON e.alarm_event_id = w.alarm_event_id
                       WHERE e.equipment_id = a.equipment_id AND e.alarm_code = a.alarm_code AND e.alarm_event_id <> a.alarm_event_id
                         AND w.status IN ('AI_DRAFT','EDITING')) THEN
            RETURN 'NONE';
        END IF;
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

-- 속도 손실 수량 (추정, R-47): [p_from, p_to) 안에서 바뀐 병목 구간의 속도 손실 합 (구간이 끝날 때 저장된 값)
--   2026-10-20: 구간이 끝날 때 trg_bottleneck_live(views/30_live_rules.sql)가 값을 채운다 (전에는 채우는 곳이 없어 실시간은 늘 0).
--   지금 열려 있는 구간(마지막 기록)은 그때까지를 바로 계산해 더한다 (fn_interval_losses, functions/35_live_calc.sql)
CREATE OR REPLACE FUNCTION fn_speed_loss_qty(p_from timestamptz, p_to timestamptz) RETURNS numeric
LANGUAGE plpgsql STABLE AS $$
DECLARE v_closed numeric; o bottleneck_log%ROWTYPE; v_open numeric := 0; v_end timestamptz := least(p_to, app_now());
BEGIN
    -- 닫힌 구간: 저장된 값. 저장 값이 없는 구간(생성기 적재 — 적재 중에는 트리거가 쉼)은 같은 식으로 계산 (보고서 병목 칸과 같은 값)
    SELECT coalesce(sum(coalesce(b.speed_loss_qty,
                                 CASE WHEN b.cause_code IN ('C1','C2','C3')
                                      THEN (fn_interval_losses(b.changed_at, b.next_at, b.cause_code)).speed_loss_qty END)), 0)
      INTO v_closed
      FROM (SELECT x.*, (SELECT min(n.changed_at) FROM bottleneck_log n WHERE n.changed_at > x.changed_at) AS next_at
              FROM bottleneck_log x WHERE x.changed_at >= p_from AND x.changed_at < p_to) b
     WHERE b.next_at IS NOT NULL;
    SELECT * INTO o FROM bottleneck_log WHERE changed_at <= app_now() ORDER BY changed_at DESC LIMIT 1;
    IF FOUND AND o.cause_code IN ('C1','C2','C3') AND o.changed_at < p_to AND v_end > greatest(o.changed_at, p_from) THEN
        v_open := (fn_interval_losses(greatest(o.changed_at, p_from), v_end, o.cause_code)).speed_loss_qty;
    END IF;
    RETURN v_closed + coalesce(v_open, 0);
END $$;

-- =====================================================================
-- 2026-10-20 요구사항 대조 중 (구현_중_수정사항 1020 36장)
-- =====================================================================
-- [정비 시작] (FR-MNT-04-10, API-PM-02): 예방 정비 실시 기록(수정 중)을 만들고 그 설비에 MAINT 구간을 연다. 설비로 가는 명령이 아니라
--   기록 버튼이다. 실시 결과는 [정비 끝]에서 적는다 — 그 전까지 결과 칸은 '정상'(NORMAL)으로 둔다 [제안]. 끝나기 전에는
--   "실시 기록 확인" 문서 알림을 내지 않는다 (app.pm_starting). 반환: pm_record_id
CREATE OR REPLACE FUNCTION fn_pm_start(p_pm_task_id text, p_actor text, p_due_date date DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    t pm_task%ROWTYPE; v_due date; v_id bigint; cur equipment_state_log%ROWTYPE;
BEGIN
    SELECT * INTO t FROM pm_task WHERE pm_task_id = p_pm_task_id;
    IF NOT FOUND OR NOT t.is_active THEN
        RAISE EXCEPTION '예방 정비 항목 %이 없거나 쓰지 않음', p_pm_task_id USING ERRCODE = '22023';
    END IF;
    SELECT * INTO cur FROM equipment_state_log WHERE equipment_id = t.equipment_id AND end_at IS NULL;
    IF cur.state_code = 'MAINT' THEN
        RAISE EXCEPTION 'FR-MNT-04-10: %는 이미 정비 중 (구간 %부터)', t.equipment_id, cur.start_at USING ERRCODE = '23514';
    END IF;
    IF cur.state_code = 'DOWN' THEN
        RAISE EXCEPTION 'FR-MNT-04-10: %는 고장 정지 중 — 고장 수리는 작업지시서로', t.equipment_id USING ERRCODE = '23514';
    END IF;
    v_due := coalesce(p_due_date, (SELECT d.next_due_date FROM v_pm_task_due d WHERE d.pm_task_id = p_pm_task_id),
                      (v_at AT TIME ZONE 'Asia/Seoul')::date);
    PERFORM set_config('app.pm_starting', 'on', true);
    INSERT INTO pm_record (pm_task_id, due_date, done_at, done_by, recorded_by, result, status, current_version)
    VALUES (p_pm_task_id, v_due, v_at, p_actor, p_actor, 'NORMAL', 'DRAFT', 0)
    RETURNING pm_record_id INTO v_id;
    PERFORM set_config('app.pm_starting', 'off', true);
    PERFORM fn_state_change(t.equipment_id, 'MAINT', v_at, p_pm_record_id => v_id);
    RETURN v_id;
END $$;

-- [정비 끝 · 실시 기록] (FR-MNT-04-10): MAINT 구간을 닫고(다음 상태는 대기 IDLE — 설비 데이터가 오면 그 값으로 바뀐다),
--   실시 시각(done_at) = 끝난 시각, 결과·측정값·메모를 적는다. 그 뒤 "실시 기록 확인" 문서 알림 (확정은 …/confirm). 반환: state_log_id
CREATE OR REPLACE FUNCTION fn_pm_end(p_pm_record_id bigint, p_actor text, p_result text DEFAULT 'NORMAL',
    p_measured_value numeric DEFAULT NULL, p_measured_unit text DEFAULT NULL, p_memo text DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    r pm_record%ROWTYPE; s equipment_state_log%ROWTYPE; v_id bigint;
BEGIN
    SELECT * INTO r FROM pm_record WHERE pm_record_id = p_pm_record_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '예방 정비 기록 %이 없음', p_pm_record_id USING ERRCODE = '22023'; END IF;
    SELECT * INTO s FROM equipment_state_log WHERE pm_record_id = p_pm_record_id AND state_code = 'MAINT' AND end_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'FR-MNT-04-10: 예방 정비 기록 %의 정비 구간이 열려 있지 않음 ([정비 시작] 먼저)', p_pm_record_id
            USING ERRCODE = '23514';
    END IF;
    v_id := fn_state_change(s.equipment_id, 'IDLE', v_at);
    UPDATE pm_record SET done_at = v_at, done_by = p_actor, recorded_by = p_actor, result = coalesce(p_result, 'NORMAL'),
                         measured_value = p_measured_value, measured_unit = p_measured_unit, memo = p_memo
     WHERE pm_record_id = p_pm_record_id;
    PERFORM fn_raise_pm_record_check(r.pm_task_id);
    RETURN v_id;
END $$;

-- 강화 → 보통 검사 복귀 (R-29, FR-QLT-01-07, DOC-06 3.3): 반장이 확인. 두 조건이 모두 맞을 때만
--   ⓐ 원인 조치 완료: 보류 뒤 확정된 작업기록서(보류의 관련 알람, 또는 그 로트를 가공한 설비) 또는 공구 교체 기록(관련 공구, 또는 그 설비 공구)
--   ⓑ 강화한 로트가 모두 합격: 보류 로트는 해제·폐기로 끝났고, 다음 로트 강화(NEXT_LOT)가 정한 수만큼 생겨 모두 합격
--   보통으로 돌아가면 아직 안 만든 다음 로트는 강화하지 않는다 (fn_create_inspection_plan). 반환: 보류 번호
CREATE OR REPLACE FUNCTION fn_resume_normal(p_hold_id bigint, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    h lot_hold%ROWTYPE; v_eq text[]; v_plans int; v_pass int;
BEGIN
    SELECT * INTO h FROM lot_hold WHERE hold_id = p_hold_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '보류 %이 없음', p_hold_id USING ERRCODE = '22023'; END IF;
    IF h.normal_resumed_at IS NOT NULL THEN
        RAISE EXCEPTION 'R-29: 보류 %은 이미 보통 검사로 돌아감 (%)', p_hold_id, h.normal_resumed_at USING ERRCODE = '23514';
    END IF;
    IF h.result = 'IN_PROGRESS' THEN
        RAISE EXCEPTION 'R-29: 보류 로트 %의 해제·폐기가 먼저', h.lot_no USING ERRCODE = '23514';
    END IF;
    SELECT count(*), count(*) FILTER (WHERE judgement = 'PASS') INTO v_plans, v_pass
      FROM inspection_plan WHERE hold_id = p_hold_id AND enhance_reason = 'NEXT_LOT';
    IF v_plans < h.enhanced_next_lots OR v_pass < v_plans THEN
        RAISE EXCEPTION 'R-29: 강화한 다음 로트가 모두 합격해야 함 (정한 %개 중 생김 %개, 합격 %개)', h.enhanced_next_lots, v_plans, v_pass
            USING ERRCODE = '23514';
    END IF;
    v_eq := ARRAY(SELECT DISTINCT r.equipment_id FROM operation_report r WHERE r.lot_no = h.lot_no
                  UNION SELECT a.equipment_id FROM alarm_event a WHERE a.alarm_event_id = h.related_alarm_event_id
                  UNION SELECT t.equipment_id FROM tool t WHERE t.tool_id = h.related_tool_id);
    IF NOT EXISTS (SELECT 1 FROM work_record w
                    WHERE w.status IN ('CONFIRMED','CHECKED') AND w.confirmed_at >= h.held_at
                      AND (w.alarm_event_id = h.related_alarm_event_id OR w.equipment_id = ANY (v_eq)))
       AND NOT EXISTS (SELECT 1 FROM tool_change c JOIN tool t USING (tool_id)
                        WHERE c.changed_at >= h.held_at AND (c.tool_id = h.related_tool_id OR t.equipment_id = ANY (v_eq))) THEN
        RAISE EXCEPTION 'R-29: 원인 조치 기록(확정된 작업기록서 또는 공구 교체)이 보류 뒤에 있어야 함 (보류 %)', p_hold_id
            USING ERRCODE = '23514';
    END IF;
    UPDATE lot_hold SET normal_resumed_by = p_actor, normal_resumed_at = v_at WHERE hold_id = p_hold_id;   -- SUP 확인은 트리거
    RETURN p_hold_id;
END $$;


-- ---------------------------------------------------------------- db/functions/35_live_calc.sql
-- =====================================================================
-- 35_live_calc.sql — 실시간 계산 도우미 (2026-10-20 요구사항 대조 상·중 보강, 구현_중_수정사항 1020 36장)
--   근무 분: 교대 안 시간 − 휴식 1시간 (주간 12:00~13:00, 야간 00:00~01:00 [가상: 2026-10-08] — v_shift_progress와 같음).
--   교대 사이(17:00~20:00·05:00~08:00)와 근무일 아닌 날은 라인 정지 → 0
--   쓰는 곳: 속도 손실(병목 구간 계획 수), 로트 예상 완료 시각(납기 지연 위험)
-- =====================================================================
-- 교대 하나의 휴식 시작 시각
CREATE OR REPLACE FUNCTION fn_shift_break_start(p_shift_type text, p_work_date date) RETURNS timestamptz
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_shift_type = 'DAY' THEN (p_work_date + time '12:00') AT TIME ZONE 'Asia/Seoul'
                ELSE (p_work_date + 1 + time '00:00') AT TIME ZONE 'Asia/Seoul' END;
$$;

-- [p_from, p_to) 안의 근무 분 (교대 안, 휴식 뺌)
CREATE OR REPLACE FUNCTION fn_work_minutes(p_from timestamptz, p_to timestamptz) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(
             greatest(0, extract(epoch FROM (least(s.end_at, p_to) - greatest(s.start_at, p_from))) / 60)
           - greatest(0, extract(epoch FROM (least(b.b1, p_to, s.end_at) - greatest(b.b0, p_from, s.start_at))) / 60)
           ), 0)::numeric
      FROM shift s
      CROSS JOIN LATERAL (SELECT fn_shift_break_start(s.shift_type, s.work_date) AS b0,
                                 fn_shift_break_start(s.shift_type, s.work_date) + interval '1 hour' AS b1) b
     WHERE s.start_at < p_to AND s.end_at > p_from;
$$;

-- p_from부터 근무 분 p_minutes가 지난 시각. 등록된 교대가 모자라면 NULL (알 수 없음)
CREATE OR REPLACE FUNCTION fn_add_work_minutes(p_from timestamptz, p_minutes numeric) RETURNS timestamptz
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_left numeric := greatest(coalesce(p_minutes, 0), 0);
    s record; v_seg record; v_len numeric;
BEGIN
    IF v_left = 0 THEN RETURN p_from; END IF;
    FOR s IN SELECT shift_type, work_date, start_at, end_at FROM shift WHERE end_at > p_from ORDER BY start_at LOOP
        -- 교대 하나 = 휴식 앞뒤 두 토막
        FOR v_seg IN SELECT * FROM (VALUES
                (greatest(s.start_at, p_from), least(s.end_at, fn_shift_break_start(s.shift_type, s.work_date))),
                (greatest(fn_shift_break_start(s.shift_type, s.work_date) + interval '1 hour', p_from), s.end_at)) x(a, b)
             WHERE x.b > x.a ORDER BY x.a LOOP
            v_len := extract(epoch FROM (v_seg.b - v_seg.a)) / 60;
            IF v_len >= v_left THEN
                RETURN v_seg.a + make_interval(secs => (v_left * 60)::double precision);
            END IF;
            v_left := v_left - v_len;
        END LOOP;
    END LOOP;
    RETURN NULL;
END $$;

-- 로트 예상 완료 시각 [제안: 2026-10-20 — 논리 ERD expected_complete_at "계산 방법 [선택 필요]"을 채움]
--   = 지금 + (이 로트와 그 앞 로트들(로트 번호 순)의 남은 부품 수) × 라인 기준 사이클(3.5분), 근무 시간 위에서.
--   남은 부품 = 투입 − OP-50 완료(양품 + 재작업) − 폐기. 끝난 로트(검사 대기 이후)·보류 로트는 NULL (판정·보류는 예측하지 않음)
CREATE OR REPLACE FUNCTION fn_lot_expected_complete(p_lot_no text) RETURNS timestamptz
LANGUAGE sql STABLE AS $$
    WITH open_lots AS (
        SELECT l.lot_no,
               greatest(0, l.input_qty - coalesce((SELECT sum(r.gq + r.rq) FROM operation_report r
                                                   WHERE r.lot_no = l.lot_no AND r.process_code = 'OP-50'), 0)
                           - coalesce(l.scrap_qty, 0)) AS remain
          FROM production_lot l WHERE l.status = 'IN_PROCESS'
    )
    SELECT CASE WHEN EXISTS (SELECT 1 FROM open_lots WHERE lot_no = p_lot_no)
                THEN fn_add_work_minutes(app_now(),
                        (SELECT sum(remain) FROM open_lots WHERE lot_no <= p_lot_no)
                        * (SELECT min(line_base_cycle_min) FROM product WHERE is_active)) END;
$$;

-- 병목 구간 [p_from, p_to)의 실적·고장 손실·속도 손실 (속도 손실 = 계획 − 실제 − 고장 손실, 원인 ①②③만 — 아니면 0)
--   계획 = 근무 분 ÷ 라인 기준 사이클(3.5분), 실제 = 그 구간에 끝난 OP-50 양품 + 재작업, 고장 손실 = fn_failure_loss_qty
--   (DOC-07 §7.4·기획서 PRD-01-16, 생성기 gen/reports.py·시연 서버 server_live.losses와 같은 식)
CREATE OR REPLACE FUNCTION fn_interval_losses(p_from timestamptz, p_to timestamptz, p_cause text,
    OUT actual_qty numeric, OUT failure_loss_qty numeric, OUT speed_loss_qty numeric)
LANGUAGE sql STABLE AS $$
    SELECT a.v, f.v,
           CASE WHEN p_cause IN ('C1','C2','C3')
                THEN round(greatest(0, fn_work_minutes(p_from, p_to) / (SELECT min(line_base_cycle_min) FROM product WHERE is_active)
                                       - a.v - f.v), 2)
                ELSE 0 END
      FROM (SELECT coalesce(sum(r.gq + r.rq), 0)::numeric AS v FROM operation_report r
             WHERE r.process_code = 'OP-50' AND r.end_at >= p_from AND r.end_at < p_to) a,
           (SELECT fn_failure_loss_qty(p_from, p_to) AS v) f;
$$;

-- (functions 단계로 옮김 — views/20 오늘의 문제 글이 쓴다, 2026-10-20)
CREATE OR REPLACE FUNCTION fn_bottleneck_cause_ko(p_cause text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE p_cause WHEN 'C1' THEN '원인 ① 사이클 시간 증가 (공구 마모)' WHEN 'C2' THEN '원인 ② OP-30 1대만 가동'
                        WHEN 'C3' THEN '원인 ③ 검사 강화' WHEN 'C4' THEN '원인 ④ 묶음 대기' WHEN 'FAILURE' THEN '고장'
                        WHEN 'BASE' THEN '기준 병목' ELSE p_cause END;
$$;


-- ---------------------------------------------------------------- db/functions/60_ingest.sql
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
    -- OP-30 정지 등급 → 작업지시서 초안 자동 (FR-MNT-03-01 ①, 2026-10-20 — views/30_live_rules.sql). 반복 판정보다 먼저:
    --   같은 알람이 2단계가 되면 이 초안에 계기를 더한다 (R-71 "겹치면 1개")
    IF m.severity = 'STOP' AND v_proc = 'OP-30' THEN
        PERFORM fn_auto_work_order_draft(v_id, 'STOP_ALARM');
    END IF;
    IF m.severity <> 'GUIDE' THEN
        PERFORM fn_check_repeat_alarm(v_id);
    END IF;
    RETURN v_id;
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
    -- Cpk 미달로 전수 측정 중인 특성이 있으면(DOC-06 §5.2, is_full_check_by_cpk — 2026-10-20) 발췌 로트도 모든 부품에 지시를 낸다
    IF v_kind = 'SAMPLE' AND NOT (p_part_seq = 1 OR p_part_seq % 5 = 0)
       AND NOT EXISTS (SELECT 1 FROM production_lot l JOIN production_order o USING (order_no)
                         JOIN inspection_item i ON i.product_code = o.product_code
                        WHERE l.lot_no = p_lot_no AND i.is_full_check_by_cpk) THEN
        RAISE EXCEPTION 'R-09: 발췌 로트의 측정 부품은 1번과 5의 배수 (요청 %)', p_part_seq USING ERRCODE = '23514';
    END IF;
    INSERT INTO cmm_instruction (lot_no, part_seq, insp_kind, enhance_reason, issued_at)
    VALUES (p_lot_no, p_part_seq, v_kind, CASE WHEN v_kind = 'ENHANCED' THEN p.enhance_reason END, coalesce(p_at, app_now()))
    RETURNING instruction_id INTO v_id;
    RETURN v_id;
END $$;


-- ---------------------------------------------------------------- db/functions/80_demo_reset.sql
-- =====================================================================
-- 80_demo_reset.sql — 시연 데이터 처음으로 (API명세서 SIM-03, NFR-DATA-10, 2026-10-08)
--   fn_demo_snapshot(): 지금 운영 데이터를 시연 기준점(demo_snapshot 스키마)으로 복사 (목업·생성기 적재 뒤 자동)
--   fn_demo_reset()   : 운영 데이터를 기준점으로 되돌리고 시연 시계를 그때 시각에 멈춰 둔다. 화면에는 RESYNC
-- 대상 = public의 운영 표 전부 (파티션은 부모로). 빼는 것: 설정·계정·코드(role·role_permission·code_label·notification_rule·
--   app_user — 시연 중 바꾼 설정은 남김), 접속 기록(access_log — 감사 기록은 지우지 않음), dataset_info, sim_clock,
--   그리고 이 표들이 가리키는 기준 표(process).
-- 센서 값(sensor_sample, 9월 약 98만 행·DB 약 120MB)은 복사하지 않는다: 추가만 되는 시계열이라 되돌릴 때
--   "기준점 시연 시각 이후 값"만 지운다 — 복사본을 두면 DB가 두 배가 되어 Supabase 무료 한도(500MB)에 가까워진다 (1014 수정사항 7장).
--   센서를 기준점 뒤에 따로 넣어도(--sensor-only) 그대로 남는다.
-- 되돌릴 때는 트리거를 끈 채(session_replication_role = replica) 그대로 채운다 — 재고 수량 같은 계산 값도 복사본 그대로.
-- 이 설정은 슈퍼유저만 바꿀 수 있어 두 함수는 스키마 주인 권한으로 돈다 (Docker의 POSTGRES_USER는 슈퍼유저).
-- =====================================================================
-- 남기는 표가 가리키는 기준 표(예: app_user → process)도 뺀다 — TRUNCATE는 남기는 표의 외래 키를 깨지 못한다
CREATE OR REPLACE FUNCTION fn_demo_tables() RETURNS SETOF text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    -- 남기는 표 + 그 표가 (여러 단계로) 가리키는 기준 표 전부 (예: sensor_sample → sensor_item → alarm_master)
    WITH RECURSIVE keep(oid) AS (
        SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname IN ('role', 'role_permission', 'code_label', 'notification_rule', 'app_user',
                                                      'access_log', 'dataset_info', 'sim_clock', 'sensor_sample', 'sensor_hourly',
                                                      'alarm_check_step')   -- 문서 기준 표 (2026-10-20)
        UNION
        SELECT f.confrelid FROM pg_constraint f JOIN keep k ON f.conrelid = k.oid WHERE f.contype = 'f'
    )
    SELECT c.relname::text
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind IN ('r','p') AND NOT c.relispartition
       AND c.oid NOT IN (SELECT oid FROM keep)
     ORDER BY c.relname;
$$;


-- ---------------------------------------------------------------- db/views/10_views.sql
-- =====================================================================
-- 10_views.sql — 계산 속성과 화면·비서 조회용 뷰
-- 논리 ERD에서 "계산" 표시가 붙은 속성 중 저장하지 않기로 한 것은 모두 여기서 계산한다
-- (docs/02_물리ERD.md 6장). 시간에 따라 바뀌는 값은 app_now()(시연 시계)를 쓴다.
-- =====================================================================
-- ---------------------------------------------------------------------
-- 생산 로트 + 완료 수량(R-05) + 측정할 부품 수(R-09) + 완제품·출하 수량(R-69)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_production_lot AS
SELECT l.lot_no, l.order_no, l.lot_seq, l.input_shift_id, l.material_lot_no, l.input_qty, l.status, l.scrap_qty,
       l.judged_at, o.product_code, o.due_at,
       coalesce(c.completed_qty, 0)                                    AS completed_qty,
       c.op50_done_at,
       fn_lot_expected_complete(l.lot_no)                              AS expected_complete_at,  -- [제안 2026-10-20] functions/35_live_calc.sql
       p.plan_mode, p.enhance_reason, p.judgement AS plan_judgement,
       CASE WHEN p.plan_mode = 'ENHANCED' THEN l.input_qty ELSE 1 + l.input_qty / 5 END AS planned_measure_qty,
       fg.fg_in_qty, fg.passed_at,
       coalesce(sh.shipped_qty, 0)                                     AS shipped_qty,
       coalesce(fg.fg_in_qty, 0) - coalesce(sh.shipped_qty, 0)        AS fg_remaining_qty,
       sh.shipment_nos
  FROM production_lot l
  JOIN production_order o USING (order_no)
  LEFT JOIN inspection_plan p USING (lot_no)
  LEFT JOIN LATERAL (SELECT sum(r.gq + r.rq)::int AS completed_qty, max(r.end_at) AS op50_done_at
                       FROM operation_report r WHERE r.lot_no = l.lot_no AND r.process_code = 'OP-50') c ON true
  LEFT JOIN LATERAL (SELECT sum(t.qty_change)::int AS fg_in_qty, min(t.txn_at) AS passed_at
                       FROM inventory_txn t WHERE t.source_kind = 'LOT_PASS' AND t.fg_lot_no = l.lot_no) fg ON true
  LEFT JOIN LATERAL (SELECT sum(sl.qty)::int AS shipped_qty, string_agg(sl.shipment_no, ',' ORDER BY sl.shipment_no) AS shipment_nos
                       FROM shipment_line sl JOIN shipment s USING (shipment_no)
                      WHERE sl.lot_no = l.lot_no AND s.status <> 'DRAFT') sh ON true;

-- ---------------------------------------------------------------------
-- 보고 순위 (6.43, R-73 "전부 보고·정해진 순서") — 브리핑·교대 보고서 인계·일일 보고서 "오늘의 문제"
-- 개수를 자르지 않는다. 정렬: rank_order → rank_group → sort_value(큰 순) → occurred_at(이른 순)
-- v_report_items = 모은 항목 하나하나, v_report_lines = 같은 설비·같은 원인을 한 줄로 묶은 화면 줄 (아래)
-- group_key: 같은 설비·같은 원인 = 같은 설비 + 같은 알람 번호 (알람·반복 알람 1·2단계·원인 점검 요청·DOWN 설비),
--   여기에 관련 예방 정비(기본 소모품)·재고 부족을 알람 ↔ 재고 품목 연결(alarm_related_item)로 붙인다 (R-89)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_report_items AS
WITH now_ AS (SELECT app_now() AS t),
open_n AS (
    SELECT n.*, r.report_rank, r.rank_group, r.rule_name,
           a.alarm_code, coalesce(n.equipment_id, a.equipment_id) AS alarm_equipment,
           pt.equipment_id AS pm_equipment, pt.default_item_no AS pm_item,
           CASE WHEN n.rule_code = 'STOCK_LOW' THEN n.item_no END AS stock_item
      FROM notification n JOIN notification_rule r USING (rule_code)
      LEFT JOIN alarm_event a ON a.alarm_event_id = n.alarm_event_id
      LEFT JOIN pm_task pt ON pt.pm_task_id = n.pm_task_id
     WHERE NOT n.is_processed
), base AS (
-- 0 안전: 잠금·표지 중인 설비
SELECT 'R0'::text AS report_rank, 0 AS rank_order, 0 AS rank_group, 'LOCK'::text AS item_kind,
       NULL::bigint AS notification_id, NULL::text AS rule_code, v.equipment_id, NULL::text AS lot_no,
       '잠금·표지 중: ' || v.equipment_id AS title, v.locked_since AS occurred_at, NULL::numeric AS sort_value,
       NULL::text AS alarm_equipment, NULL::text AS alarm_code, NULL::text AS pm_equipment, NULL::text AS pm_item,
       NULL::text AS stock_item
  FROM v_lock_status v
UNION ALL
-- 0-1 오래 방치: 24시간 넘게 처리 안 된 주의 알림 (건수는 "주의"에 센다)
SELECT 'R0_1', 1, 0, 'NOTIFICATION', n.notification_id, n.rule_code, n.equipment_id, n.lot_no,
       n.message, n.raised_at, extract(epoch FROM (now_.t - n.raised_at)) / 3600,
       n.alarm_equipment, n.alarm_code, n.pm_equipment, n.pm_item, n.stock_item
  FROM open_n n, now_
 WHERE n.importance = 'CAUTION' AND n.raised_at < now_.t - interval '24 hours'
UNION ALL
-- 1·2·3·4 순위의 알림 (0-1로 올라간 것은 빼고)
SELECT n.report_rank, CASE n.report_rank WHEN 'R1' THEN 2 WHEN 'R2' THEN 3 WHEN 'R3' THEN 4 ELSE 5 END,
       n.rank_group, 'NOTIFICATION', n.notification_id, n.rule_code, n.equipment_id, n.lot_no,
       n.message, n.raised_at, n.repeat_count::numeric,
       n.alarm_equipment, n.alarm_code, n.pm_equipment, n.pm_item, n.stock_item
  FROM open_n n, now_
 WHERE NOT (n.importance = 'CAUTION' AND n.raised_at < now_.t - interval '24 hours')
UNION ALL
-- 1 긴급: 지금 DOWN인 설비 (같은 설비·같은 알람의 정지 알람 알림이 있으면 그 줄로 묶인다)
SELECT 'R1', 2, 0, 'DOWN', NULL, NULL, e.equipment_id, e.current_lot_no,
       '고장 정지 중: ' || e.equipment_id, e.state_since, e.state_minutes,
       e.equipment_id, coalesce(sa.alarm_code, e.open_alarm_code), NULL, NULL, NULL
  FROM v_equipment_now e
  LEFT JOIN alarm_event sa ON sa.alarm_event_id = e.state_alarm_event_id
 WHERE e.state_code = 'DOWN'
UNION ALL
-- 3 주의 ③ 품질: 보류·보류 검토 로트
SELECT 'R3', 4, 30, 'LOT', NULL, NULL, NULL, l.lot_no,
       CASE l.status WHEN 'ON_HOLD' THEN '보류 로트: ' ELSE '보류 검토 로트: ' END || l.lot_no,
       coalesce(h.held_at, l.judged_at), NULL, NULL, NULL, NULL, NULL, NULL
  FROM production_lot l
  LEFT JOIN lot_hold h ON h.lot_no = l.lot_no AND h.result = 'IN_PROGRESS'
 WHERE l.status IN ('ON_HOLD','HOLD_REVIEW')
UNION ALL
-- 3 주의 ③ 품질: 강화 검사 중인 로트 (보류 로트의 다음 1~2개, 판정 전 — FR-PRD-02-08 인계 사항)
SELECT 'R3', 4, 30, 'LOT', NULL, NULL, NULL, l.lot_no, '강화 검사 로트: ' || l.lot_no,
       h.held_at, NULL, NULL, NULL, NULL, NULL, NULL
  FROM production_lot l
  JOIN inspection_plan p USING (lot_no)
  LEFT JOIN lot_hold h ON h.hold_id = p.hold_id
 WHERE p.plan_mode = 'ENHANCED' AND p.enhance_reason = 'NEXT_LOT'
   AND l.status IN ('IN_PROCESS','WAIT_INSPECTION','WAIT_JUDGEMENT')
UNION ALL
-- 3 주의: 진행 중 작업지시서 (FR-PRD-02-08 "진행 중 작업지시", 2026-10-20 — 생성기 인계 사항과 같은 자리: 주의 칸 맨 뒤)
SELECT 'R3', 4, 80, 'WO', NULL, NULL, m.equipment_id, NULL, format('진행 중 작업지시서 %s (%s)', m.wo_no, m.equipment_id),
       m.created_at, NULL, NULL, NULL, NULL, NULL, NULL
  FROM maintenance_work_order m
 WHERE m.status NOT IN ('DONE','CANCELLED')
)
-- 같은 원인 (group_key): ① 알람이 있는 항목 = 설비|알람 번호 ② 예방 정비 알림 = 그 설비의 관련 알람 줄이 있으면 그 줄
--   (alarm_related_item: 알람 ↔ 정비 항목의 기본 소모품), 없으면 설비|item:소모품 ③ 재고 부족 = 관련 알람 줄 → 같은 소모품의
--   예방 정비 줄 순. 예: 2075 반복 알람 + 축 윤활유 점검 기한 넘김 + 축 윤활유 재고 부족 → 한 줄 (DOC-07 §10.5, DOC-04 5장)
SELECT b.report_rank, b.rank_order, b.rank_group, b.item_kind, b.notification_id, b.rule_code, b.equipment_id, b.lot_no,
       b.title, b.occurred_at, b.sort_value,
       CASE
         WHEN b.alarm_code IS NOT NULL THEN b.alarm_equipment || '|' || b.alarm_code
         WHEN b.pm_item IS NOT NULL THEN coalesce(
             (SELECT min(a.alarm_equipment || '|' || a.alarm_code) FROM base a
                JOIN alarm_related_item r ON r.alarm_code = a.alarm_code
               WHERE a.alarm_equipment = b.pm_equipment AND r.item_no = b.pm_item),
             b.pm_equipment || '|item:' || b.pm_item)
         WHEN b.stock_item IS NOT NULL THEN coalesce(
             (SELECT min(a.alarm_equipment || '|' || a.alarm_code) FROM base a
                JOIN alarm_related_item r ON r.alarm_code = a.alarm_code WHERE r.item_no = b.stock_item),
             (SELECT min(x.pm_equipment || '|item:' || x.pm_item) FROM base x WHERE x.pm_item = b.stock_item))
         WHEN b.item_kind = 'WO' THEN 'WO:' || b.title                 -- 작업지시서마다 한 줄 (같은 설비 여러 장도 따로)
       END AS group_key
  FROM base b;


-- ---------------------------------------------------------------- db/views/20_report_functions.sql
-- =====================================================================
-- 20_report_functions.sql (views 단계에서 만든다 — v_report_items 등 뷰를 쓰므로) — 교대·일일 보고서 AI비서 초안의 "숫자 칸" 만들기 (PRD-02·04, R-12·R-46·R-54·R-72·R-73)
-- 숫자는 프로그램이 계산한다 (FR-AST-COM-05). 문장 칸(특이 사항·오늘의 문제 문장)은 AI 비서 ②가
-- 나중에 같은 버전 안에서 채우거나, 비서가 꺼져 있으면 기본 문구로 둔다.
-- 생성 시각 (R-72, 2026-10-13): 교대 보고서 = 교대 끝(17:00·05:00) + 그 교대 반장에게 확정 요청 알림,
--           일일 보고서 = 그 생산일 야간 교대 보고서가 확정되는 즉시 (trg_shift_report_confirmed), 06:00까지 확정이 없으면
--           06:00 (스케줄러가 부름) + MGR에게 일일 보고서 확정 요청(DAILY_REPORT_PENDING). 교대 보고서가 확정되면 칸을 다시 채운다
-- =====================================================================
-- 인계 사항 글 (6.43 순서, 개수 자르지 않음 — R-73, FR-AST-COM-21, FR-PRD-02-08). 생성기(gen/reports.py handover_text)·화면
--   (Briefing.tsx parseHandover)과 같은 모양 (2026-10-20 — 전에는 머리 + 줄바꿈 목록이라 화면이 못 읽었다):
--   "0 안전: … / 0-1 오래 방치: a; b / 1 긴급: - / 2 생산 위험: - / 3 주의: … / 4 참고: -"
--   빈 순위는 "-", 순위 0이 비면 "잠금·표지 중인 설비 없음" (DOC-01 §3.3, DOC-07 §10.5). 머리 "전체 N건 (…)"은 화면이 줄 수로 센다
--   (묶은 뒤 줄 = v_report_lines). 항목 글 속의 "; "·" / "는 칸 구분과 헷갈리지 않게 바꾼다
CREATE OR REPLACE FUNCTION fn_report_item_line(p_title text, p_rank text, p_members int) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT replace(replace(regexp_replace(p_title, '^\[[^]]*\] ', ''), '; ', ', '), ' / ', ' · ')
           || CASE WHEN p_rank = 'R0_1' THEN ' (24시간 넘게 처리 안 됨)' ELSE '' END
           || CASE WHEN p_members > 1 THEN format(' (같은 원인 %s건 묶음)', p_members) ELSE '' END;
$$;

CREATE OR REPLACE FUNCTION fn_report_items_text() RETURNS text
LANGUAGE sql STABLE AS $$
    WITH ranks(report_rank, rank_order, rank_name) AS (
        VALUES ('R0', 0, '0 안전'), ('R0_1', 1, '0-1 오래 방치'), ('R1', 2, '1 긴급'), ('R2', 3, '2 생산 위험'),
               ('R3', 4, '3 주의'), ('R4', 5, '4 참고')
    ), lines AS (SELECT * FROM v_report_lines)
    SELECT string_agg(k.rank_name || ': ' ||
            coalesce((SELECT string_agg(fn_report_item_line(l.title, l.report_rank, l.member_count), '; '
                                        ORDER BY l.rank_group, l.sort_value DESC NULLS LAST, l.occurred_at)
                        FROM lines l WHERE l.report_rank = k.report_rank),
                     CASE WHEN k.report_rank = 'R0' THEN '잠금·표지 중인 설비 없음' ELSE '-' END),
            ' / ' ORDER BY k.rank_order)
      FROM ranks k;
$$;

-- 일일 보고서 "오늘의 문제 (전체 N건)" 글 (FR-PRD-04-08, FR-AST-COM-21 — 2026-10-20). 생성기(gen/reports.py issues_text)·화면
--   (Reports.tsx splitIssues)·시연 서버(split_issues)와 같은 모양:
--   "전체 N건 (안전 a · 긴급 b · 생산 c · 주의 d · 참고 e): 1) [긴급] … / 2) [생산] … / …" (없으면 "전체 0건")
--   그날(그 생산일 교대 구간)에 생긴 문제를 순위 순으로 전부 모은다:
--   [안전] 지금 잠금·표지 중인 설비 / [긴급] 정지 등급 알람이 있는 고장 그룹 5분 이상 정지 (긴 순) / [생산] 교대 실적이 목표 90% 아래,
--   병목 원인 ①~③ / [주의] 그날 보류한 로트, 주의 등급 알람 수, 하루 끝에 남은 주의 일(0-1 포함, 위와 겹치면 뺌) / [참고] 조작 안내 알람 수
CREATE OR REPLACE FUNCTION fn_daily_issues_text(p_work_date date) RETURNS text
LANGUAGE sql STABLE AS $$
    WITH w AS (SELECT min(start_at) AS f, max(end_at) AS t FROM shift WHERE work_date = p_work_date),
    stops AS (
        SELECT st.equipment_id, dr.reason_name, st.start_at,
               round(extract(epoch FROM (least(coalesce(st.end_at, app_now()), w.t) - greatest(st.start_at, w.f))) / 60)::int AS minutes,
               -- 손실 = 보고서 구간 안 정지 분 ÷ 기준 사이클 (report_stops와 같음 — 1020 33장 4번: 생성기는 구간 밖까지 세는 것이 틀림)
               round((extract(epoch FROM (least(coalesce(st.end_at, app_now()), w.t) - greatest(st.start_at, w.f))) / 60
                      / nullif(e.std_cycle_min, 0))::numeric, 1) AS loss
          FROM equipment_state_log st CROSS JOIN w
          JOIN equipment e USING (equipment_id)
          JOIN downtime_reason dr ON dr.reason_code = coalesce(st.reason_code, st.reason_suggested_code)
          JOIN alarm_event a ON a.alarm_event_id = st.alarm_event_id AND a.severity_at_event = 'STOP'
         WHERE dr.reason_group = 'FAILURE' AND st.state_code <> 'RUN'
           AND st.start_at < w.t AND coalesce(st.end_at, 'infinity'::timestamptz) > w.f
           AND coalesce(st.end_at, app_now()) - st.start_at >= interval '5 minutes'
    ), items(bucket, ord, sub, at, txt) AS (
        SELECT '안전', 0, 0, l.occurred_at, fn_report_item_line(l.title, l.report_rank, l.member_count)
          FROM v_report_lines l WHERE l.report_rank = 'R0'
        UNION ALL
        SELECT '긴급', 1, -s.minutes, s.start_at,
               format('%s 고장 %s분 (%s, 고장 손실 약 %s개)', s.equipment_id, s.minutes, s.reason_name, s.loss::float8)
          FROM stops s WHERE s.minutes > 0
        UNION ALL
        SELECT '생산', 2, 0, sh.start_at, format('%s 실적 %s개 — 목표 %s개의 90%% 아래', r.shift_id, r.actual_qty, r.target_qty)
          FROM shift_report r JOIN shift sh USING (shift_id)
         WHERE sh.work_date = p_work_date AND r.actual_qty < r.target_qty * 0.9
        UNION ALL
        SELECT '생산', 2, 1, b.changed_at,
               format('%s 병목 %s — %s', to_char(b.changed_at AT TIME ZONE 'Asia/Seoul', 'HH24:MI'), b.new_process_code,
                      fn_bottleneck_cause_ko(b.cause_code))
          FROM bottleneck_log b CROSS JOIN w
         WHERE b.changed_at >= w.f AND b.changed_at < w.t AND b.cause_code IN ('C1','C2','C3')
        UNION ALL
        SELECT '주의', 3, 0, h.held_at, format('로트 보류 %s — %s', h.lot_no, h.hold_reason)
          FROM lot_hold h CROSS JOIN w WHERE h.held_at >= w.f AND h.held_at < w.t
        UNION ALL
        SELECT '주의', 3, 1, min(a.occurred_at),
               format('주의 등급 알람 %s건 (%s)', count(*), string_agg(DISTINCT a.alarm_code, ', ' ORDER BY a.alarm_code))
          FROM alarm_event a CROSS JOIN w
         WHERE a.occurred_at >= w.f AND a.occurred_at < w.t AND a.severity_at_event = 'WARN'
        HAVING count(*) > 0
        UNION ALL
        SELECT '주의', 3, 2, l.occurred_at, fn_report_item_line(l.title, l.report_rank, l.member_count)
          FROM v_report_lines l
         WHERE l.report_rank IN ('R0_1','R3')
           AND NOT (l.item_kind = 'LOT' AND EXISTS (SELECT 1 FROM lot_hold h, w WHERE h.lot_no = l.lot_no
                                                     AND h.held_at >= w.f AND h.held_at < w.t))
        UNION ALL
        SELECT '참고', 4, 0, min(a.occurred_at), format('조작 안내 알람 %s건', count(*))
          FROM alarm_event a CROSS JOIN w
         WHERE a.occurred_at >= w.f AND a.occurred_at < w.t AND a.severity_at_event = 'GUIDE'
        HAVING count(*) > 0
    ), n AS (SELECT i.*, row_number() OVER (ORDER BY ord, sub, at, txt) AS no FROM items i)
    SELECT CASE WHEN count(*) = 0 THEN '전체 0건' ELSE
           format('전체 %s건 (안전 %s · 긴급 %s · 생산 %s · 주의 %s · 참고 %s): ', count(*),
                  count(*) FILTER (WHERE bucket = '안전'), count(*) FILTER (WHERE bucket = '긴급'),
                  count(*) FILTER (WHERE bucket = '생산'), count(*) FILTER (WHERE bucket = '주의'),
                  count(*) FILTER (WHERE bucket = '참고'))
           || string_agg(format('%s) [%s] %s', no, bucket, replace(txt, ' / ', ' · ')), ' / ' ORDER BY no) END
      FROM n;
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
    PERFORM fn_check_cpk();      -- 교대마다 Cpk → 기준 미달 특성은 전수 측정 (DOC-06 §5.2, 2026-10-20)
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
    v_issues := fn_daily_issues_text(p_work_date);
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
        -- 받는 사람 = MNT + 작업자 담당 항목(DOC-04 매일·매주 일부)이 있으면 그 설비 공정의 작업자 (1015 DOC-04, 2026-10-20)
        v_id := fn_raise_notification('PM_DUE_SOON', format('기한 %s (내일) 예방 정비 %s건', to_char(v_due, 'MM/DD'), v_cnt),
                                      '{}'::jsonb, v_at, p_related_info => v_items,
                                      p_recipients => ARRAY(SELECT u.user_id FROM app_user u WHERE u.is_active AND (u.role_code = 'MNT'
                                          OR (u.role_code = 'OPR' AND EXISTS (SELECT 1 FROM pm_task t WHERE t.pm_task_id = ANY (v_tasks)
                                               AND t.default_role = 'OPR'
                                               AND fn_equipment_process(t.equipment_id) IN (u.home_process_code, u.home_process_code_2))))));
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

-- 예방 정비 실시 기록 알림 (PM_RECORD_CHECK, 참고·알림 탭만, MNT): 실시 기록이 초안으로 생기면 그 설비의 열린 알림 1건에
--   항목을 더한다 (없으면 새로, "VF2-01 예방 정비 2건 끝남 — 실시 기록 확인"). 묶인 항목의 초안 기록이 모두 확정되면 자동 처리.
--   확정되면 예방 정비 기한 하루 전 묶음도 다시 본다 (fn_close_pm_due_soon)
-- 예방 정비 실시 기록 확인 문서 알림 (그 설비의 열린 알림에 항목을 더한다). 실시 기록이 생길 때와 [정비 끝] 때 (2026-10-20 함수로 뺌)
CREATE OR REPLACE FUNCTION fn_raise_pm_record_check(p_pm_task_id text) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_eq text; v_id bigint;
BEGIN
    SELECT equipment_id INTO v_eq FROM pm_task WHERE pm_task_id = p_pm_task_id;
    SELECT notification_id INTO v_id FROM notification
     WHERE rule_code = 'PM_RECORD_CHECK' AND equipment_id = v_eq AND NOT is_processed ORDER BY raised_at DESC LIMIT 1;
    IF v_id IS NULL THEN
        v_id := fn_raise_notification('PM_RECORD_CHECK', format('%s 예방 정비 1건 끝남 — 실시 기록 확인', v_eq),
                                      jsonb_build_object('equipment_id', v_eq), NULL);
        IF v_id IS NULL THEN RETURN NULL; END IF;    -- 규칙이 꺼져 있음
    END IF;
    INSERT INTO notification_pm_task (notification_id, pm_task_id) VALUES (v_id, p_pm_task_id) ON CONFLICT DO NOTHING;
    UPDATE notification SET message = format('%s 예방 정비 %s건 끝남 — 실시 기록 확인', v_eq,
                                             (SELECT count(*) FROM notification_pm_task WHERE notification_id = v_id))
     WHERE notification_id = v_id;
    RETURN v_id;
END $$;

CREATE OR REPLACE FUNCTION trg_pm_record_doc_alert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_ids bigint[];
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    IF TG_OP = 'INSERT' THEN
        -- [정비 시작]이 만든 기록은 정비가 끝날 때(fn_pm_end) 알린다
        IF NEW.status <> 'DRAFT' OR current_setting('app.pm_starting', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
        PERFORM fn_raise_pm_record_check(NEW.pm_task_id);
    ELSIF NEW.status = 'CONFIRMED' AND OLD.status = 'DRAFT' THEN
        SELECT array_agg(n.notification_id) INTO v_ids FROM notification n
         WHERE n.rule_code = 'PM_RECORD_CHECK' AND NOT n.is_processed
           AND EXISTS (SELECT 1 FROM notification_pm_task l WHERE l.notification_id = n.notification_id AND l.pm_task_id = NEW.pm_task_id)
           AND NOT EXISTS (SELECT 1 FROM notification_pm_task l JOIN pm_record p USING (pm_task_id)
                            WHERE l.notification_id = n.notification_id AND p.status = 'DRAFT');
        IF v_ids IS NOT NULL THEN PERFORM fn_auto_process(v_ids, NEW.recorded_by); END IF;
        PERFORM fn_close_pm_due_soon(NEW.recorded_by);
    END IF;
    RETURN NULL;
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
    -- 반복 알람 효과 확인 (FR-AST-02-18·R-70, 2026-10-20): 조치 계획(1단계)·원인 점검 확정(2단계) 뒤 7일 동안 재발이 없으면
    --   "효과 있음"으로 닫는다 (전에는 다음 알람이 와야만 바뀌었다)
    UPDATE notification SET repeat_stage_status = 'EFFECTIVE'
     WHERE repeat_stage_status IN ('S1_CLOSED','S2_CHECKED') AND effect_check_due_at IS NOT NULL AND effect_check_due_at <= v_at;
    -- 로트 납기 지연 위험 (FR-AST-02-06, 2026-10-20 — views/30_live_rules.sql)
    v_n := v_n + fn_raise_lot_due_risk(v_at);
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


-- ---------------------------------------------------------------- db/views/30_live_rules.sql
-- =====================================================================
-- 30_live_rules.sql — 실시간 알림 4종·속도 손실 (2026-10-20 요구사항 대조 상 1·2번, 구현_중_수정사항 1020 36장)
--   전에는 규칙 표(시드)에만 있고 만드는 코드가 없어, 생성기 9월 기록에만 있던 알림:
--     BOTTLENECK_MOVE 병목 발생·이동 (FR-AST-02-05·19, R-49·R-84)   WIP_WARN 재공 경고 (FR-AST-02-05, R-56)
--     SPC_OUT 관리도 이상 (FR-QLT-01-10, R-31)                       LOT_DUE_RISK 로트 납기 지연 위험 (FR-AST-02-06)
--   문장·조건은 생성기 gen/notify.py와 같게. 생성기 적재(app.loading = on) 중에는 만들지 않는다 (9월 기록에 이미 있음)
-- =====================================================================
-- DOC-07 §7.5 병목 원인별 조치 — 알림 관련 정보 한 줄 (비서는 제안만, 사람이 결정 — FR-AST-02-19·FR-AST-COM-10)
CREATE OR REPLACE FUNCTION fn_bottleneck_action_line(p_cause text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE p_cause
      WHEN 'C1' THEN 'DOC-07 §7.5 ① 사이클 시간 증가(공구 마모) — 공구 수명 확인, 90% 이상이면 사이클 끝난 뒤 교체·80~90%면 앞당길지 검토, '
                  || '교체 뒤 초품 검사, 90% 넘긴 뒤 가공 로트는 의심 로트 검토 / 결정: OPR·MNT 교체, SUP 판단'
      WHEN 'C2' THEN 'DOC-07 §7.5 ② OP-30 1대만 가동(예방 정비·긴 셋업) — 끝나는 시각과 손실 안내, 앞 공정 투입 조절 검토(OP-20→30 재공은 비우지 않음), '
                  || '긴 셋업이면 미리 할 일 확인, 예방 정비를 교대 사이로 옮길지 검토 / 결정: SUP, 일정 변경은 MNT·MGR'
      WHEN 'C3' THEN 'DOC-07 §7.5 ③ 검사 강화(OP-50으로 이동) — 보류 로트 판정을 결과 나오는 대로, 강화 범위 확인(공구 원인·교체 기록 있으면 다음 1개, 아니면 2개), '
                  || '보통 검사 복귀 조건 안내 / 결정: SUP 판정·범위, MGR 폐기 승인'
      WHEN 'FAILURE' THEN 'DOC-07 §7.5 고장 — 지침카드·DOC-03 점검 순서, 병목 공정(OP-30) 고장은 수리 우선, 복구 뒤 초품 검사·의심 로트 검토 '
                  || '/ 결정: MNT 수리, SUP 담당 지정·승인, 잠금·표지는 사람만'
      ELSE NULL END;
$$;

-- 병목 기록이 생기면: ① 바로 앞 구간을 닫으며 실적·고장 손실·속도 손실을 채운다 (상 2번, R-47 — 전에는 실시간이 늘 0)
--   ② 병목 발생·이동 알림 (반장, 주의). 원인 ④ 묶음 대기는 병목 판단에서 빠지므로 알림 없음 (DOC-07 §7.5)
CREATE OR REPLACE FUNCTION trg_bottleneck_live() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p bottleneck_log%ROWTYPE; l record;
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    SELECT * INTO p FROM bottleneck_log WHERE changed_at < NEW.changed_at ORDER BY changed_at DESC LIMIT 1;
    IF FOUND THEN
        l := fn_interval_losses(p.changed_at, NEW.changed_at, p.cause_code);
        UPDATE bottleneck_log SET actual_qty = l.actual_qty, failure_loss_qty = l.failure_loss_qty, speed_loss_qty = l.speed_loss_qty
         WHERE bottleneck_log_id = p.bottleneck_log_id;
    END IF;
    IF NEW.cause_code <> 'C4' THEN
        PERFORM fn_raise_notification('BOTTLENECK_MOVE',
            format('[병목] %s → %s (%s)', coalesce(NEW.prev_process_code, '—'), NEW.new_process_code, fn_bottleneck_cause_ko(NEW.cause_code)),
            jsonb_build_object('bottleneck_log_id', NEW.bottleneck_log_id), NEW.changed_at,
            p_related_info => fn_bottleneck_action_line(NEW.cause_code));
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS bottleneck_live ON bottleneck_log;
CREATE TRIGGER bottleneck_live AFTER INSERT ON bottleneck_log FOR EACH ROW EXECUTE FUNCTION trg_bottleneck_live();

-- 재공 경고: 경고 기준(wip_buffer.warn_over_qty, 경고 켠 위치만)을 넘으면 재공 위치마다 교대에 처음 1번 (R-56, 그 뒤는 화면 숫자 주황만)
--   한도에 닿으면 "앞 공정 막힘" 문장 (WIP-20-30 경고 = 한도 30 도달, ERD 2026-10-14)
CREATE OR REPLACE FUNCTION trg_wip_warn() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b wip_buffer%ROWTYPE; s shift%ROWTYPE;
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    SELECT * INTO b FROM wip_buffer WHERE buffer_code = NEW.buffer_code;
    IF NOT b.warn_enabled OR NEW.wip_qty <= b.warn_over_qty THEN RETURN NULL; END IF;
    SELECT * INTO s FROM shift WHERE start_at <= NEW.logged_at AND end_at > NEW.logged_at;
    IF NOT FOUND OR EXISTS (SELECT 1 FROM notification WHERE rule_code = 'WIP_WARN' AND buffer_code = NEW.buffer_code
                                AND raised_at >= s.start_at AND raised_at < s.end_at) THEN
        RETURN NULL;
    END IF;
    PERFORM fn_raise_notification('WIP_WARN',
        format('[재공] %s 재공 %s개 — %s', NEW.buffer_code, NEW.wip_qty,
               CASE WHEN NEW.wip_qty >= b.limit_qty THEN format('한도 %s 도달, 앞 공정 막힘', b.limit_qty)
                    ELSE format('경고 기준 %s개 초과', b.warn_over_qty) END),
        jsonb_build_object('buffer_code', NEW.buffer_code), NEW.logged_at, p_related_info => 'DOC-07 §7.2');
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS wip_warn ON wip_log;
CREATE TRIGGER wip_warn AFTER INSERT ON wip_log FOR EACH ROW EXECUTE FUNCTION trg_wip_warn();

-- 관리도 이상 (DOC-06 5.3, I-MR): 한계 = 평균 ± 3·평균 이동 범위 ÷ 1.128 — 측정기 자동 값, 표준 위치(또는 MID), 첫 측정만,
--   50개 미만 항목은 판정하지 않음 (DOC-06 §5.2). 점 1개가 밖이면 반장에게 주의. 같은 항목의 다음 측정이 오면 자동 처리 ("다음 부품 바로 측정")
CREATE OR REPLACE FUNCTION trg_spc_out() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_n int; v_mean numeric; v_mr numeric; v_ucl numeric; v_lcl numeric;
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' OR NEW.input_method <> 'CMM_AUTO'
       OR coalesce(NEW.position, 'MID') <> 'MID' OR NEW.remeasure_seq <> 1 OR NEW.measured_value IS NULL THEN
        RETURN NULL;
    END IF;
    PERFORM fn_auto_process(ARRAY(SELECT n.notification_id FROM notification n JOIN inspection_result r USING (result_id)
                                   WHERE n.rule_code = 'SPC_OUT' AND NOT n.is_processed AND r.item_seq = NEW.item_seq
                                     AND r.result_id <> NEW.result_id),
                            NEW.inspector_id, NEW.measured_at);
    WITH pts AS (
        SELECT measured_value AS v, measured_value - lag(measured_value) OVER (ORDER BY measured_at, result_id) AS mr
          FROM inspection_result
         WHERE item_seq = NEW.item_seq AND input_method = 'CMM_AUTO' AND coalesce(position, 'MID') = 'MID'
           AND remeasure_seq = 1 AND measured_value IS NOT NULL
    )
    SELECT count(*), avg(v), avg(abs(mr)) INTO v_n, v_mean, v_mr FROM pts;
    IF v_n < 50 OR v_mr IS NULL THEN RETURN NULL; END IF;
    v_ucl := v_mean + 3 * v_mr / 1.128;
    v_lcl := v_mean - 3 * v_mr / 1.128;
    IF NEW.measured_value BETWEEN v_lcl AND v_ucl THEN RETURN NULL; END IF;
    PERFORM fn_raise_notification('SPC_OUT',
        format('[품질] 항목 %s 측정값 %s — 관리 한계(%s~%s) 밖', NEW.item_seq, NEW.measured_value::float8,
               round(v_lcl, 3), round(v_ucl, 3)),
        jsonb_build_object('result_id', NEW.result_id, 'lot_no', NEW.lot_no), NEW.measured_at,
        p_related_info => 'DOC-06 5.3 — 다음 부품 바로 측정');
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS spc_out ON inspection_result;
CREATE TRIGGER spc_out AFTER INSERT ON inspection_result FOR EACH ROW EXECUTE FUNCTION trg_spc_out();

-- 로트 납기 지연 위험 (FR-AST-02-06): 예상 완료 시각(fn_lot_expected_complete) > 작업지시 납기면 반장에게 주의, 로트마다 1번.
--   보류 로트는 예상을 하지 않고, 납기가 24시간 안이면 "보류 로트 — 판정 뒤 출하"로 알린다 [제안] (생성기 9월 늦은 출하 1건과 같은 뜻)
--   fn_run_time_rules(스케줄러)가 부른다. 반환: 새 알림 수
CREATE OR REPLACE FUNCTION fn_raise_lot_due_risk(p_at timestamptz DEFAULT NULL) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); r record; v_n int := 0;
BEGIN
    FOR r IN SELECT l.lot_no, l.status, o.due_at, fn_lot_expected_complete(l.lot_no) AS exp_at
               FROM production_lot l JOIN production_order o USING (order_no)
              WHERE l.status IN ('IN_PROCESS','ON_HOLD','HOLD_REVIEW') AND o.due_at IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM notification n WHERE n.rule_code = 'LOT_DUE_RISK' AND n.lot_no = l.lot_no) LOOP
        IF r.status = 'IN_PROCESS' AND r.exp_at IS NOT NULL AND r.exp_at > r.due_at THEN
            PERFORM fn_raise_notification('LOT_DUE_RISK',
                format('[납기] %s 예상 완료 %s가 납기 %s보다 늦음', r.lot_no, to_char(r.exp_at AT TIME ZONE 'Asia/Seoul', 'MM/DD HH24:MI'),
                       to_char(r.due_at AT TIME ZONE 'Asia/Seoul', 'MM/DD HH24:MI')),
                jsonb_build_object('lot_no', r.lot_no), v_at,
                p_related_info => '예상 = 남은 부품(앞 로트 포함) × 라인 기준 사이클 3.5분, 근무 시간 기준 [제안]');
            v_n := v_n + 1;
        ELSIF r.status IN ('ON_HOLD','HOLD_REVIEW') AND r.due_at <= v_at + interval '24 hours' THEN
            PERFORM fn_raise_notification('LOT_DUE_RISK',
                format('[납기] %s 보류 중 — 납기 %s', r.lot_no, to_char(r.due_at AT TIME ZONE 'Asia/Seoul', 'MM/DD HH24:MI')),
                jsonb_build_object('lot_no', r.lot_no), v_at, p_related_info => '보류 로트 — 판정 뒤 출하');
            v_n := v_n + 1;
        END IF;
    END LOOP;
    RETURN v_n;
END $$;

-- ---------------------------------------------------------------------
-- 작업지시서 초안 자동 생성 (2026-10-20 요구사항 대조 상 3번, FR-MNT-03-01·03·04·05·12, R-71 — 화면 App.tsx createWo와 같은 규칙)
--   계기 ① OP-30 정지 등급 알람 (STOP_ALARM): 그 설비에 끝나지 않은 작업지시서가 없을 때
--      ② OP-30 반복 알람 2단계 (REPEAT_2): 원인 점검 — 같은 알람의 정지 등급 초안이 있으면 거기에 계기를 더함 (fn_create_work_order_draft)
--   제목 = "설비 알람 번호 (이름) 점검" / "설비 알람 번호 반복 — 원인 점검 (2단계)", 증상 = DOC-03 첫 문장 + 연쇄 알람
--   작업 순서 = DOC-03 점검 순서(alarm_check_step): 정지 등급 = ★ 작업자 줄 + 보전 줄, 2단계 = 보전 줄(없으면 작업자 줄).
--      "§2.1 점검 2~5와 같다"처럼 다른 절을 가리키는 줄은 그 절의 줄로 풀고 "(§2.1 점검 n)"을 붙인다 (문서 문장은 그대로)
--   예상 부품 = 9월(지난) 같은 알람 작업기록서에 쓴 부품 (C-07), 담당 = 알람 시각 교대의 보전 담당자
--   AI비서 초안(AI_DRAFT)으로 저장 — 비서가 문장을 다듬는 것은 비서 서비스 몫. 반환: wo_no (만들지 않으면 NULL)
--   끄기: 세션·DB 설정 app.auto_work_order = 'off' (비서 서비스가 초안을 직접 만들게 되면, 또는 초안 API만 시험할 때)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_auto_work_order_draft(p_alarm_event_id bigint, p_trigger text, p_trigger_notification_id bigint DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    a alarm_event%ROWTYPE; m alarm_master%ROWTYPE;
    v_sec text; v_steps jsonb; v_parts jsonb; v_title text; v_symptom text; v_wo text; v_shift text; v_mnt text;
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on'
       OR current_setting('app.auto_work_order', true) IS NOT DISTINCT FROM 'off' THEN RETURN NULL; END IF;
    SELECT * INTO a FROM alarm_event WHERE alarm_event_id = p_alarm_event_id;
    SELECT * INTO m FROM alarm_master WHERE alarm_code = a.alarm_code;
    IF fn_equipment_process(a.equipment_id) <> 'OP-30' THEN RETURN NULL; END IF;
    IF p_trigger = 'STOP_ALARM' AND EXISTS (SELECT 1 FROM maintenance_work_order
                                              WHERE equipment_id = a.equipment_id AND status NOT IN ('DONE','CANCELLED')) THEN
        RETURN NULL;   -- 그 설비에 진행 중인 작업지시서가 있으면 새로 만들지 않는다 (화면과 같음)
    END IF;
    SELECT 'DOC-03 §' || section INTO v_sec FROM alarm_guide_map WHERE alarm_code = a.alarm_code AND doc_no = 'DOC-03' ORDER BY seq LIMIT 1;
    v_sec := coalesce(v_sec, 'DOC-03');
    -- 작업 순서 (참조 줄 풀기)
    WITH base AS (
        SELECT s.seq, s.step_text FROM alarm_check_step s
         WHERE s.alarm_code = a.alarm_code
           AND (CASE WHEN p_trigger = 'REPEAT_2' AND EXISTS (SELECT 1 FROM alarm_check_step x WHERE x.alarm_code = a.alarm_code AND x.step_kind = 'MNT')
                     THEN s.step_kind = 'MNT' ELSE s.step_kind IN ('OPR','MNT') END)
    ), expanded AS (
        SELECT b.seq, 0 AS sub, b.step_text, v_sec AS src
          FROM base b WHERE b.step_text !~ '§\d+\.\d+ 점검 \d+~\d+와 같다$'
        UNION ALL
        SELECT b.seq, r.n, t.step_text || format(' (§%s 점검 %s)', mm.g[1], r.n), 'DOC-03 §' || mm.g[1]
          FROM base b
          CROSS JOIN LATERAL (SELECT regexp_match(b.step_text, '§(\d+\.\d+) 점검 (\d+)~(\d+)와 같다$') AS g) mm
          CROSS JOIN LATERAL generate_series(mm.g[2]::int, mm.g[3]::int) r(n)
          JOIN LATERAL (SELECT s2.step_text FROM alarm_check_step s2
                          JOIN alarm_guide_map gm ON gm.alarm_code = s2.alarm_code AND gm.doc_no = 'DOC-03' AND gm.section = mm.g[1]
                         WHERE s2.step_kind IN ('OPR','MNT') ORDER BY s2.seq OFFSET r.n - 1 LIMIT 1) t ON true
         WHERE mm.g IS NOT NULL
    )
    SELECT coalesce(jsonb_agg(jsonb_build_object('step_text', step_text, 'source_section', src) ORDER BY seq, sub), '[]'::jsonb)
      INTO v_steps FROM expanded;
    -- 예상 부품 = 지난 같은 알람 작업기록서에 쓴 부품
    SELECT coalesce(jsonb_agg(jsonb_build_object('item_no', item_no, 'qty', qty) ORDER BY item_no), '[]'::jsonb) INTO v_parts
      FROM (SELECT p.item_no, max(p.qty) AS qty
              FROM work_record_part p JOIN work_record w USING (record_no)
              LEFT JOIN maintenance_work_order o ON o.wo_no = w.wo_no
              JOIN alarm_event e ON e.alarm_event_id = coalesce(w.alarm_event_id, o.alarm_event_id)
             WHERE e.alarm_code = a.alarm_code AND e.alarm_event_id <> a.alarm_event_id
             GROUP BY p.item_no) x;
    v_title := CASE WHEN p_trigger = 'REPEAT_2' THEN format('%s 알람 %s 반복 — 원인 점검 (2단계)', a.equipment_id, a.alarm_code)
                    ELSE format('%s 알람 %s (%s) 점검', a.equipment_id, a.alarm_code, btrim(regexp_replace(m.name_ko, '\(.*\)', ''))) END;
    v_symptom := coalesce((SELECT step_text FROM alarm_check_step WHERE alarm_code = a.alarm_code AND step_kind = 'SYMPTOM'), m.easy_desc, m.name_ko)
                 || CASE WHEN coalesce(m.chain_rule, '') <> '' THEN ' — 연쇄 알람 ' || m.chain_rule ELSE '' END;
    v_wo := fn_create_work_order_draft(a.equipment_id, v_title, v_symptom,
                p_alarm_event_id => CASE WHEN p_trigger = 'REPEAT_2' THEN NULL ELSE a.alarm_event_id END,
                p_trigger_notification_id => p_trigger_notification_id,
                p_steps => v_steps, p_parts => v_parts, p_lot_no => a.lot_no, p_at => a.occurred_at);
    -- 담당 = 알람 시각 교대의 보전 담당자 (사람이 바꿀 수 있음)
    SELECT shift_type INTO v_shift FROM shift WHERE start_at <= a.occurred_at AND end_at > a.occurred_at;
    v_shift := coalesce(v_shift, CASE WHEN extract(hour FROM a.occurred_at AT TIME ZONE 'Asia/Seoul') BETWEEN 8 AND 16 THEN 'DAY' ELSE 'NIGHT' END);
    SELECT user_id INTO v_mnt FROM app_user WHERE is_active AND role_code = 'MNT' AND home_shift_type = v_shift ORDER BY user_id LIMIT 1;
    UPDATE maintenance_work_order SET assignee_user_id = coalesce(assignee_user_id, v_mnt)
     WHERE wo_no = v_wo AND status = 'AI_DRAFT' AND v_mnt IS NOT NULL;
    RETURN v_wo;
END $$;

-- Cpk 특성 하나 (FR-QLT-01-08, DOC-06 §5.1 I-MR: σ = 평균 이동 범위 ÷ 1.128). 50개 미만이면 cpk NULL ("계산 중").
--   app/sql/quality.sql cpk와 같은 식 (전체 값 — 설비별은 참고용)
CREATE OR REPLACE FUNCTION fn_item_cpk(p_product_code text, p_item_seq int, OUT n int, OUT cpk numeric)
LANGUAGE sql STABLE AS $$
    WITH v AS (
        SELECT r.measured_value AS x, r.measured_value - lag(r.measured_value) OVER (ORDER BY r.measured_at, r.result_id) AS mr
          FROM v_inspection_result r
         WHERE r.product_code = p_product_code AND r.item_seq = p_item_seq AND r.use_for_judgement AND r.measured_value IS NOT NULL
    )
    SELECT count(v.x)::int,
           CASE WHEN count(v.x) < 50 THEN NULL
                ELSE least(coalesce(i.usl - avg(v.x), 'Infinity'::numeric), coalesce(avg(v.x) - i.lsl, 'Infinity'::numeric))
                     / nullif(3 * avg(abs(v.mr)) / 1.128, 0) END
      FROM inspection_item i LEFT JOIN v ON true
     WHERE i.product_code = p_product_code AND i.item_seq = p_item_seq
     GROUP BY i.lsl, i.usl;
$$;

-- Cpk 기준 미달 → 그 특성 전수 측정 (DOC-06 §5.2 "기준을 다시 채울 때까지 유지", 표 540줄 "교대마다 계산"). 교대 보고서 초안 때 부른다.
--   켜기만 한다 — 끄기(보통 발췌로)는 관리자 승인 (fn_resume_sampling). 반환: 새로 전수로 바뀐 특성 수
CREATE OR REPLACE FUNCTION fn_check_cpk() RETURNS int LANGUAGE plpgsql AS $$
DECLARE v_n int;
BEGIN
    UPDATE inspection_item i SET is_full_check_by_cpk = true
     WHERE i.method = 'CMM' AND i.cpk_min IS NOT NULL AND NOT i.is_full_check_by_cpk
       AND (fn_item_cpk(i.product_code, i.item_seq)).cpk < i.cpk_min;
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN v_n;
END $$;

-- 전수 측정 → 보통(발췌) (DOC-06 §5.2 "전수 측정 중 다시 기준 이상 → 관리자 승인 후 보통"). MGR만, Cpk가 기준 이상일 때만
CREATE OR REPLACE FUNCTION fn_resume_sampling(p_product_code text, p_item_seq int, p_actor text) RETURNS numeric
LANGUAGE plpgsql AS $$
DECLARE i inspection_item%ROWTYPE; c record;
BEGIN
    PERFORM fn_require_role(p_actor, ARRAY['MGR'], '전수 측정 → 보통 검사 승인');
    SELECT * INTO i FROM inspection_item WHERE product_code = p_product_code AND item_seq = p_item_seq FOR UPDATE;
    IF NOT FOUND OR NOT i.is_full_check_by_cpk THEN
        RAISE EXCEPTION 'DOC-06 §5.2: 특성 %·%는 전수 측정 중이 아님', p_product_code, p_item_seq USING ERRCODE = '23514';
    END IF;
    c := fn_item_cpk(p_product_code, p_item_seq);
    IF c.cpk IS NULL OR c.cpk < i.cpk_min THEN
        RAISE EXCEPTION 'DOC-06 §5.2: Cpk %가 기준 % 미만 (또는 50개 미만 — 측정 %개)', round(c.cpk, 2), i.cpk_min, c.n
            USING ERRCODE = '23514';
    END IF;
    UPDATE inspection_item SET is_full_check_by_cpk = false WHERE product_code = p_product_code AND item_seq = p_item_seq;
    RETURN round(c.cpk, 2);
END $$;

-- ---------------------------------------------------------------- db/seed/50_alarm_check_steps.sql (그대로)
-- 생성: tools/gen_alarm_steps.py (frontend/tools/data.json ← 가상사내문서 DOC-03). 손으로 고치지 말고 다시 만든다.
-- 알람 점검 순서 (작업지시서 초안 자동 생성, 2026-10-20). SYMPTOM = 증상 첫 문장, OPR = ★ 작업자 줄, MNT = 보전 줄
DELETE FROM alarm_check_step;
INSERT INTO alarm_check_step (alarm_code, seq, step_kind, step_text) VALUES
  ('992', 0, 'SYMPTOM', '서보 앰프가 모터에 너무 큰 전류가 흐르는 것을 감지'),
  ('992', 1, 'OPR', '축을 움직이지 말고 알람 이력을 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호'),
  ('992', 2, 'OPR', '도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다'),
  ('992', 3, 'OPR', '외함·주축·공구·고정구에 손상이 있는지 본다 (손상 = 충돌 징후)'),
  ('992', 4, 'OPR', '공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 부른다'),
  ('992', 5, 'MNT', '잠금·표지 후, 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 본다'),
  ('992', 6, 'MNT', '충돌이 확인되면 볼스크류 커플링 정렬도 본다 (§2.5 점검 8)'),
  ('992', 7, 'MNT', '서보 모터 케이블이 오염·끼임 없는지, 모터 쪽 커넥터에 절삭유 오염이 없는지 보고 아래 표대로 저항을 잰다'),
  ('992', 8, 'MNT', '이송을 낮춰 MDI로 해당 축을 움직이는 시험을 한다. 어떤 이송에서도 알람이 뜨면 서보 앰프 문제'),
  ('994', 0, 'SYMPTOM', '서보 앰프에 높은 부하가 오래 걸렸다'),
  ('994', 1, 'OPR', '알람 이력을 본다. 994 뒤에 992가 이어지면 충돌 신호 → §2.1'),
  ('994', 2, 'OPR', '공구가 무뎌지거나 부서졌는지, 용도에 맞는 공구인지 본다'),
  ('994', 3, 'OPR', '프로그램의 속도·이송이 재료와 공구에 맞는지 확인하고 보전 담당자를 부른다'),
  ('994', 4, 'MNT', '잠금·표지 후 막힘을 직접 확인한다. ① 도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다. ② 외함·주축·공구·고정구에 손상이 있는지 본다 (손상 = 충돌 징후). ③ 공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송이 맞는지 확인한다. ④ 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 본다'),
  ('991', 0, 'SYMPTOM', '서보 앰프 온도가 한계를 넘었다'),
  ('991', 1, 'OPR', '가공을 멈춘 채 앰프가 식을 시간을 준다 (기다리는 시간은 원문에 없음)'),
  ('991', 2, 'OPR', '앞의 축 알람으로 어느 축인지 확인하고, 993이 함께 떴는지 본다 (함께 떴으면 §2.4)'),
  ('991', 3, 'OPR', '프로그램을 조정해 축 부하를 줄일 수 있는지 반장·보전 담당자와 확인한다'),
  ('991', 4, 'MNT', '서보 앰프 냉각 팬이 제대로 도는지 본다'),
  ('991', 5, 'MNT', '팬이 안 돌면 팬 케이블을 분리하고 리드 사이 전압을 잰다. 정상 120 VAC. 전압이 정상이면 팬 불량'),
  ('993', 0, 'SYMPTOM', '단락이 감지됐다'),
  ('993', 1, 'OPR', '앞의 축 알람으로 축을 확인하고, 다시 돌리지 않고 보전 담당자를 부른다'),
  ('993', 2, 'OPR', '잠금·표지, 고전압 대기, AC 전압 검출기로 전원 차단 확인'),
  ('993', 3, 'OPR', '케이블의 오염·손상·굳음, 모터 쪽 커넥터와 앰프 쪽 단자의 헐거움·오염을 본다 (앰프 쪽 케이블은 살살 당겨 본다)'),
  ('993', 4, 'MNT', '모든 단자 연결이 단단히 조여 있는지 본다'),
  ('993', 5, 'MNT', '케이블·모터 저항을 잰다 (§2.1의 표)'),
  ('993', 6, 'MNT', '부위 구분 시험: 모터에서 파워 케이블 분리 → [RESET] → 조그. 103이면 모터 불량, 993이면 케이블 또는 앰프 → 모터·앰프 양쪽에서 분리 → [RESET] → 조그. 993이면 앰프 불량, 103이면 케이블 불량'),
  ('993', 7, 'MNT', '앰프 단락 점검: 전원 끔 → 해당 축 모터 케이블을 앰프에서 분리 → 멀티미터 Ω(가능하면 MΩ) → 접지 나사와 RED·WHT·BLK·HV(+)·HV(-) 단자 사이가 모두 O.L이어야 정상. HV(-)와 WHT·BLK, HV(+)와 RED·WHT·BLK 사이는 MΩ 범위여야 하고 매우 낮으면 앰프 손상'),
  ('103', 0, 'SYMPTOM', '축이 명령된 위치로 가지 못해 오차가 너무 커졌다'),
  ('103', 1, 'OPR', '원점 복귀 중이었는지, 충돌 흔적(§2.1 점검 2~3)이 있는지 본다'),
  ('103', 2, 'OPR', '기계 안의 칩, 공구·공구 홀더의 칩, 무뎌진 공구를 본다'),
  ('103', 3, 'OPR', '프로그램 오류와 속도·이송을 확인하고 보전 담당자를 부른다'),
  ('103', 4, 'MNT', '원점 복귀 중이었으면 홈 스위치 센서 위에 금속 칩이 없는지 본다'),
  ('103', 5, 'MNT', '잠금·표지 후 볼스크류 표면에 얇은 기름막이 있는지 본다. 없으면 윤활 계통의 누설·막힘을 찾는다 (한 축의 누설이 다른 축의 윤활 부족을 만든다)'),
  ('103', 6, 'MNT', '볼너트를 손으로 돌려 걸림·저항을 보고, 볼스크류를 손으로 돌려 지지 베어링을 본다'),
  ('103', 7, 'MNT', '파워 케이블을 점검한다 (§2.1의 표)'),
  ('103', 8, 'MNT', '케이블에 문제가 없을 때만 커플링 정렬을 본다'),
  ('103', 9, 'MNT', '모터 브레이크: I/O 기판 P3·P4·P5 커넥터 다시 꽂기 → 빨강·검정 선 전압: [EMERGENCY STOP] 때 0, [RESET] 뒤 20~30 VDC → 브레이크·파워 커넥터 오염 확인'),
  ('103', 10, 'MNT', '노이즈: 접지선 규격과 제어반까지의 배선, 다른 설비와 전원 공유 여부, 엔코더·접지·고전압 단자 체결, 엔코더 케이블과 X·Y·Z 모터 파워 케이블의 페라이트 필터(P/N 64-1252), 엔코더 케이블을 고전력 케이블과 떼어 배선'),
  ('108', 0, 'SYMPTOM', '축 모터 부하가 몇 초~몇 분 동안 100%를 넘었다'),
  ('108', 1, 'OPR', '알람 이력을 본다. 108 뒤에 994·992가 이어지면 충돌 신호 → 정지 등급처럼 §2.1로 간다'),
  ('108', 2, 'OPR', '공구가 무뎌지거나 부서졌는지 보고, 그렇다면 새 공구·새 인서트로 바꾼다'),
  ('108', 3, 'OPR', '이송·속도를 조정해 축 부하를 줄인 뒤 다시 돌린다'),
  ('108', 4, 'MNT', '반복되면 볼스크류 정렬 확인: 축을 전체 행정으로 조그하며 서보 부하가 일정한지 본다. 일정하지 않으면 원문 정렬 절차를 따른다'),
  ('966', 0, 'SYMPTOM', '메인 프로세서에 내장된 진동 센서가 큰 진동을 감지해 모든 기계 운동이 멈췄다'),
  ('966', 1, 'OPR', '공구가 구부러지거나 손상됐는지 본다. 손상되거나 균형이 맞지 않는 공구는 절대 쓰지 않는다'),
  ('966', 2, 'OPR', '공구 길이를 본다. 가능한 한 짧은 공구를 쓰고, 홀더 밖으로 나온 길이는 공구 지름의 3배를 넘지 않게 한다'),
  ('966', 3, 'OPR', '고정구가 공작물을 잘 받치는지 보고 보전 담당자를 부른다'),
  ('966', 4, 'MNT', '공구를 홀더에 꽂은 채로 균형을 맞춘다. 맞출 수 없으면 균형이 맞는 조립체로 바꾼다'),
  ('966', 5, 'MNT', '잠금·표지 후 공구에 다이얼 인디케이터를 대고 주축을 손으로 돌려 런아웃을 잰다. 0.0003" (0.0076 mm)를 넘으면 안 된다'),
  ('966', 6, 'MNT', '드로바 힘 게이지로 클램프 힘을 잰다 (원문 기준표 참조)'),
  ('966', 7, 'MNT', '구동 벨트(해짐·늘어남·끊김·이 빠짐)와 엔코더 벨트·풀리(세트 스크류 조임)를 본다'),
  ('966', 8, 'MNT', '메인 프로세서 기판 스탠드오프 볼트를 조이고, 제어반 장착 볼트를 풀었다 가볍게 조인 뒤 규정 토크로 조인다'),
  ('966', 9, 'MNT', '위에서 원인이 없으면 진동 분석(베어링)과 주축 균형을 HFO에 맡긴다'),
  ('174', 0, 'SYMPTOM', '이송 중 공구 부하가 사용자가 정한 공구 부하 한계를 넘었다'),
  ('174', 1, 'OPR', '고급 공구 관리(ATM) 탭(현재 명령 아래)에서 공구 부하 한계가 맞게 설정됐는지 본다'),
  ('174', 2, 'OPR', '공구 마모를 보고 필요하면 바꾼다'),
  ('174', 3, 'OPR', '프로그램 오류와 속도·이송을 본다. 이송은 더 보수적으로 조정한다'),
  ('174', 4, 'OPR', '필요하면 주축 공구의 부하 한도를 리셋하고, 알람을 리셋한 뒤 프로그램을 다시 시작한다'),
  ('174', 5, 'MNT', '표면 거칠기 문제가 함께 있으면 주축 점검 보고서의 다른 항목을 모두 한 뒤에만 주축 처짐 시험(예압 확인)을 한다'),
  ('254', 0, 'SYMPTOM', '주축 모터가 과열됐다'),
  ('254', 1, 'OPR', '주축을 멈추고 식힌다 (기다리는 시간은 원문에 없음)'),
  ('254', 2, 'OPR', '무뎌지거나 손상된 공구를 본다'),
  ('254', 3, 'OPR', '프로그램의 평균 부하·부하 주기를 낮출 수 있는지(이송 낮춤, 회전수 조정) 반장·보전 담당자와 확인한다'),
  ('254', 4, 'MNT', '주축을 돌릴 때 주축 외함 위쪽으로 공기가 나가는지 본다'),
  ('254', 5, 'MNT', 'MDI에서 `S50 M03;` 실행 → I/O 기판 P32의 검정·빨강 선 전압 120 VAC 확인. 없으면 I/O 기판 불량'),
  ('254', 6, 'MNT', 'I/O 기판 P39 연결 케이블에 페라이트 필터(P/N 64-1252)가 있는지 본다. 없으면 단다. 온도 값은 DIAGNOSTIC > I/O 탭 아날로그 입력 #9'),
  ('2073', 0, 'SYMPTOM', '축 윤활 압력이 감지되지 않았다'),
  ('2073', 1, 'OPR', '가공을 다시 시작하지 말고 윤활유 저장소가 차 있는지 본다'),
  ('2073', 2, 'OPR', '기계의 공기 압력 게이지와 제어기 게이지 화면의 공기 압력을 보고 보전 담당자를 부른다'),
  ('2073', 3, 'OPR', '솔레노이드를 수동으로 작동시켜 HALO 매니폴드로 공기가 가는지, 솔레노이드~매니폴드 공기 라인에 누설이 없는지 본다'),
  ('2073', 4, 'MNT', '축 윤활 시험(DIAGNOSTIC > MAINTENANCE > LUBE) 중 솔레노이드 전압 120 VAC 확인. 솔레노이드를 커넥터에서 뺀 채로 재지 않는다. 커넥터 위치, 느슨하거나 끊어진 배선, I/O 기판 연결을 본다'),
  ('2073', 5, 'MNT', 'I/O 탭에서 윤활 주기 동안 압력 입력이 1→0→1, 솔레노이드 출력이 0→1→0으로 바뀌는지 본다'),
  ('2073', 6, 'MNT', '압력 스위치: NGC 소프트웨어 100.16.000.1020 이상인지 → 스위치 케이블을 점퍼로 이어 입력이 1→0으로 바뀌면 스위치 정상 → I/O 기판~스위치 도통 → 윤활 주기 중 스위치 저항이 OL→값→OL이면 정상'),
  ('2073', 7, 'MNT', '저장소를 채울 때 바닥 필터가 찌그러져 있으면 보강형 필터(P/N 58-2072A)로 바꾼다'),
  ('2075', 0, 'SYMPTOM', '윤활 압력이 정상보다 빨리 떨어졌다'),
  ('2075', 1, 'OPR', '윤활유 저장소 수위를 본다'),
  ('2075', 2, 'OPR', '보충: 전원 끄기 → 공기 주 밸브 닫기 → 공기·윤활 매니폴드의 압력 해제 밸브 링을 당겨 압력 빼기 → 저장소 분리(너무 꽉 끼면 자동차용 오일 필터 렌치) → 나사산 아래 1/2" (13 mm)까지 채움 → 개스킷이 닿을 때까지 손으로 조인 뒤 3/4 바퀴 더'),
  ('2075', 3, 'OPR', '[DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]로 축 윤활 시험. 알람이 안 뜰 때까지 반복하고, 시험 사이에 최소 1분 기다린다'),
  ('2075', 4, 'OPR', '막 채웠다면 공기가 빠질 때까지 몇 주기 더 뜰 수 있다. 계속 뜨면 보전 담당자를 부른다'),
  ('2075', 5, 'MNT', '저장소 조립체의 체크밸브가 걸리지 않는지, O-링이 제자리인지 본다. 매니폴드와 압력 스위치 주변을 청소한다'),
  ('2075', 6, 'MNT', '매니폴드 누설 시험: 오일 라인을 모두 빼고 포트를 막은 뒤 윤활 주기 → 15초 전에 압력이 떨어지면 매니폴드 누설'),
  ('2075', 7, 'MNT', '라인 하나씩 시험해 누설 라인을 찾고, 해당 축의 매니폴드·트럭·볼너트 연결부를 청소해 누설을 본다'),
  ('2075', 8, 'MNT', '프라이밍(공기 빼기): 저장소를 채움 → 축 라인을 하나씩 빼고 솔레노이드를 수동 작동해 공기 제거 → 다시 꽂고 10초씩 5번, 15초 간격 수동 작동 → 윤활 주기로 재현 여부 확인'),
  ('120', 0, 'SYMPTOM', '기계에 들어오는 압축 공기의 압력이나 유량이 최소 요구치보다 낮다'),
  ('120', 1, 'OPR', '기계의 공기 압력 게이지와 제어기 진단의 Gauges 탭 값을 본다'),
  ('120', 2, 'OPR', '공장 공기 공급(컴프레서, 공급 배관, 주 밸브 열림)을 확인한다. 압력뿐 아니라 유량도 본다'),
  ('120', 3, 'OPR', '레귤레이터가 맞는 압력을 내보내는지 본다'),
  ('120', 4, 'OPR', '계속되면 보전 담당자를 부른다'),
  ('120', 5, 'MNT', '제어기 값과 기계 게이지가 다르면 I/O 탭의 아날로그 값을 보고, 센서 케이블을 흔들 때 값이 바뀌는지 본다 → 센서 교체'),
  ('120', 6, 'MNT', '센서가 오염됐으면 교체한다. 다시 생기지 않게 공급 공기를 깨끗하고 건조하게 유지한다'),
  ('362', 0, 'SYMPTOM', '공구 수명이 다 됐고 대신 쓸 공구가 없다'),
  ('362', 1, 'OPR', '만료된 공구를 검사하고 필요하면 바꾼다'),
  ('362', 2, 'OPR', '공구 오프셋을 업데이트한다'),
  ('362', 3, 'OPR', '고급 공구 관리(ATM) 탭(현재 명령 아래)에서 만료 공구의 사용 계수기를 선택 → [0] → [ENTER]로 수명을 리셋한다'),
  ('552', 0, 'SYMPTOM', '제어반 안 배전 기판의 회로 차단기가 떨어졌다'),
  ('552', 1, 'OPR', '제어반은 열지 않는다. 절삭유 펌프·칩 컨베이어가 칩에 막히거나 걸렸는지 겉으로 보고 보전 담당자를 부른다'),
  ('552', 2, 'OPR', '잠금·표지, 고전압 대기, AC 전압 검출기로 확인한 뒤 제어반을 연다'),
  ('552', 3, 'OPR', 'PSUP 기판에서 어느 차단기가 떨어졌는지 본다. 안 떨어졌으면 점검 8로'),
  ('552', 4, 'MNT', '펌프 결함 점검: 펌프 케이블을 기계에서 분리 → 옴미터로 각 선 단자와 접지 단자 사이(3상 L1·L2·L3+접지, 단상 L1·L2+접지) → 모두 O.L이면 단락 없음. 단락이 나오면 모터 커버를 열고 케이블을 모터에서 분리 → 모터 리드와 접지 사이: 단락이면 펌프 불량, 아니면 케이블 불량'),
  ('552', 5, 'MNT', '단락이 없으면 펌프 걸림을 본다: 펌프 아래 임펠러 캡 분리 → 임펠러를 빼서 청소(강철 임펠러는 왼나사) → 마모·손상·균열 → 펌프 축을 손으로 돌려 자유롭게 도는지(안 돌면 모터 베어링 손상) → 다시 달고 펌프 몸체·캡에 닿지 않는지(심으로 조정)'),
  ('552', 6, 'MNT', '원인을 고친 뒤 차단기를 다시 올리고 알람을 지운다'),
  ('552', 7, 'MNT', '다시 떨어지면 AC 클램프 미터로 돌입 전류와 트립까지 시간, 정상 운전 전류를 재어 원문 표와 비교한다 (원문 값 ±20%)'),
  ('552', 8, 'MNT', '차단기가 안 떨어졌는데 552면 PSUP 기판 고장 대응 안내를 따른다'),
  ('314', 0, 'SYMPTOM', 'M98 또는 G65의 P코드로 부른 서브프로그램이 메모리에 없다'),
  ('314', 1, 'OPR', 'P코드가 부르는 서브프로그램이 메모리에 있는지 본다'),
  ('314', 2, 'OPR', 'FNC로 부를 때는 메인 프로그램과 같은 장치·같은 디렉터리에 있는지 본다'),
  ('314', 3, 'OPR', 'USB에서 하드 드라이브로 옮긴 파일이면 이름이 대문자 O + 소문자 확장자인지 본다 (예: `O1234.nc`)'),
  ('6302.00', 1, 'OPR', '[EMERGENCY STOP] 상태를 확인하고 절단 중인 재료가 톱날에 끼었는지 본다'),
  ('6302.00', 2, 'OPR', '톱날 상태를 본다 (일일 점검 항목)'),
  ('6302.00', 3, 'OPR', '보전 담당자를 부른다'),
  ('5303.00', 1, 'OPR', 'HMI 오른쪽 윤활 캐비닛 안의 윤활유 저장소·펌프를 찾는다'),
  ('5303.00', 2, 'OPR', '수위를 본다'),
  ('5303.00', 3, 'OPR', '지정 윤활유로 보충한다: Haas P/N 93-5656 또는 Mobil Vactra No. 2 (Way Oil 68)'),
  ('25050', 0, 'SYMPTOM', '계산한 실제값과 기계 실제값의 차이가 MD36400 $MA_CONTOUR_TOL보다 커서 프로그램이 취소됐다'),
  ('25050', 1, 'OPR', '알람의 축 이름(%1)을 확인하고 다시 시작하지 않는다'),
  ('25050', 2, 'OPR', '보전 담당자를 부른다'),
  ('25050', 3, 'OPR', '보전: 기계 부분이 원활하게 움직이는지 본다'),
  ('10720', 0, 'SYMPTOM', '축에 프로그램된 경로가 현재 유효한 소프트웨어 리미트 스위치를 넘는다'),
  ('10720', 1, 'OPR', 'NC 프로그램의 위치를 점검·수정한다'),
  ('10720', 2, 'OPR', '현재 프레임의 활성 공작물 오프셋, 오버레이 이동($AA_OFF), DRF, 변환 컴포넌트를 본다'),
  ('WSH-01', 0, 'SYMPTOM', '운전이 멈추고 화면에 알람 아이콘만 켜짐'),
  ('WSH-01', 1, 'OPR', '세척액 수위를 본다'),
  ('WSH-01', 2, 'OPR', '식을 때까지 기다린다'),
  ('WSH-01', 3, 'OPR', '보전 담당자를 부른다'),
  ('WSH-02', 1, 'OPR', '세척액 상태를 본다 (고형물·변색이 보이면 오염)'),
  ('WSH-02', 2, 'OPR', '부하를 넣은 상태에서 수위가 운전 수위선 3/8 inch (1 cm) 안인지 본다'),
  ('WSH-02', 3, 'OPR', '새로 채웠으면 따뜻한 수돗물 + 세척액으로 5~10분 운전해 탈기했는지 본다'),
  ('MP-170', 1, 'OPR', '측정을 멈추고 프로브·스타일러스가 부딪히거나 손상됐는지 본다'),
  ('MP-170', 2, 'OPR', '스타일러스 끝과 기준구의 먼지를 닦는다'),
  ('MP-170', 3, 'OPR', '보전 담당자를 부른다'),
  ('TempComp-202', 1, 'OPR', '측정을 멈추고 측정실 온도가 안정될 때까지 기다린다'),
  ('TempComp-202', 2, 'OPR', '측정실 문·공조 상태를 본다'),
  ('TempComp-202', 3, 'OPR', '공작물의 부품 온도가 16~26 ℃ 안인지 본다 (부품 온도 보정을 쓸 수 없으면 측정실 온도와 차이 2 ℃ 이하, DOC-06 §6)');

-- ---------------------------------------------------------------- db/seed/30_notification_rules.sql (CMM 결과 파일 오류: 반장이 [처리])
--   (설명 글은 9월 데이터 적재 값 그대로 둔다 — 처리 방식만)
UPDATE notification_rule SET process_mode = 'BOTH', processor_roles = '{SUP}' WHERE rule_code = 'CMM_FILE_ERROR';

-- ---------------------------------------------------------------- 권한 (db/roles.sql·supabase/sql/lockdown.sql과 같게)
GRANT SELECT, INSERT, UPDATE, DELETE ON alarm_check_step TO mom_app;
GRANT SELECT ON alarm_check_step TO mom_ai_ro;
ALTER TABLE alarm_check_step ENABLE ROW LEVEL SECURITY;
CREATE POLICY mom_app_all ON alarm_check_step TO mom_app USING (true) WITH CHECK (true);
CREATE POLICY mom_ai_ro_read ON alarm_check_step FOR SELECT TO mom_ai_ro USING (true);
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mom_app;
GRANT EXECUTE ON FUNCTION fn_shift_break_start(text, date), fn_work_minutes(timestamptz, timestamptz),
                          fn_add_work_minutes(timestamptz, numeric), fn_lot_expected_complete(text),
                          fn_interval_losses(timestamptz, timestamptz, text) TO mom_ai_ro;
DO $$
DECLARE v_roles text;
BEGIN
    SELECT string_agg(quote_ident(rolname), ', ') INTO v_roles FROM pg_roles WHERE rolname IN ('anon', 'authenticated');
    IF v_roles IS NOT NULL THEN
        EXECUTE format('REVOKE ALL ON alarm_check_step FROM %s', v_roles);
        EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %s', v_roles);
    END IF;
END $$;
