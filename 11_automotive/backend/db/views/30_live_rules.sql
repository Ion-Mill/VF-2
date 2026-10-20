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
