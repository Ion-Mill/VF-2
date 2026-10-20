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

CREATE OR REPLACE FUNCTION fn_bottleneck_cause_ko(p_cause text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE p_cause WHEN 'C1' THEN '원인 ① 사이클 시간 증가 (공구 마모)' WHEN 'C2' THEN '원인 ② OP-30 1대만 가동'
                        WHEN 'C3' THEN '원인 ③ 검사 강화' WHEN 'C4' THEN '원인 ④ 묶음 대기' WHEN 'FAILURE' THEN '고장'
                        WHEN 'BASE' THEN '기준 병목' ELSE p_cause END;
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
