-- =====================================================================
-- 70_realtime.sql — 시뮬레이터(또는 설비 수집기)가 실시간으로 보내는 것 받기
--   fn_state_change      : 설비 상태가 바뀜 → 열린 구간 닫고 새 구간 열기 (R-04 겹침은 EXCLUDE가 막음)
--   fn_report_production : 공정 실적(양품·재작업·불량) 더하기 → OP-30이면 공구 사용 누적 (공구 사용 기록 단위 B)
--   trg_state_log_loss   : 구간이 끝나면 정지 손실 수량 = 구간 길이 ÷ 기준 사이클 (계획 정지는 계산하지 않음)
-- 데이터는 설비 → 플랫폼 한 방향 (FR-AST-COM-11).
-- 재공(wip_log)·센서(sensor_sample)는 단순 INSERT라 app/sql/ingest.sql 에 둔다.
-- =====================================================================

-- 정지 손실 수량 (논리 ERD stop_loss_qty: 구간 길이 ÷ 그 설비 기준 사이클 시간, PLANNED 그룹은 계산 안 함)
-- 생성기가 값을 넣어 적재한 행(INSERT 때 값 있음)은 건드리지 않는다. 끝 시각·사유가 바뀌면 다시 계산한다.
CREATE OR REPLACE FUNCTION trg_state_log_loss() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_cycle numeric; v_group text;
BEGIN
    IF NEW.end_at IS NULL OR NEW.state_code = 'RUN' THEN
        IF NEW.state_code = 'RUN' THEN NEW.stop_loss_qty := NULL; END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'INSERT' AND NEW.stop_loss_qty IS NOT NULL THEN RETURN NEW; END IF;
    IF TG_OP = 'UPDATE' AND OLD.end_at IS NOT DISTINCT FROM NEW.end_at AND OLD.reason_code IS NOT DISTINCT FROM NEW.reason_code
       AND NEW.stop_loss_qty IS NOT NULL THEN
        RETURN NEW;
    END IF;
    SELECT reason_group INTO v_group FROM downtime_reason WHERE reason_code = coalesce(NEW.reason_code, NEW.reason_suggested_code);
    IF v_group = 'PLANNED' OR NEW.state_code = 'MAINT' THEN
        NEW.stop_loss_qty := NULL;
        RETURN NEW;
    END IF;
    SELECT std_cycle_min INTO v_cycle FROM equipment WHERE equipment_id = NEW.equipment_id;
    NEW.stop_loss_qty := round(extract(epoch FROM (NEW.end_at - NEW.start_at)) / 60 / nullif(v_cycle, 0), 2);
    RETURN NEW;
END $$;
SET client_min_messages = warning;
DROP TRIGGER IF EXISTS state_log_loss ON equipment_state_log;
RESET client_min_messages;
CREATE TRIGGER state_log_loss BEFORE INSERT OR UPDATE OF end_at, reason_code, state_code ON equipment_state_log
    FOR EACH ROW EXECUTE FUNCTION trg_state_log_loss();

-- 설비 상태 바뀜. 같은 상태가 이미 열려 있으면 새로 만들지 않고 그 구간 번호를 돌려준다 (중복 전송에 안전).
-- DOWN이면 정지 등급 알람(p_alarm_event_id), MAINT면 예방 정비 기록(p_pm_record_id)이 있어야 한다 (테이블 CHECK).
CREATE OR REPLACE FUNCTION fn_state_change(p_equipment_id text, p_state_code text, p_at timestamptz DEFAULT NULL,
    p_execution text DEFAULT NULL, p_warn_marker boolean DEFAULT false, p_reason_suggested_code text DEFAULT NULL,
    p_alarm_event_id bigint DEFAULT NULL, p_pm_record_id bigint DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at  timestamptz := coalesce(p_at, app_now());
    cur   equipment_state_log%ROWTYPE;
    v_id  bigint;
BEGIN
    SELECT * INTO cur FROM equipment_state_log
     WHERE equipment_id = p_equipment_id AND end_at IS NULL FOR UPDATE;
    IF FOUND THEN
        IF cur.state_code = p_state_code AND cur.alarm_event_id IS NOT DISTINCT FROM p_alarm_event_id
           AND cur.warn_marker = coalesce(p_warn_marker, false) THEN
            RETURN cur.state_log_id;
        END IF;
        IF v_at <= cur.start_at THEN
            RAISE EXCEPTION 'R-04: % 상태 바뀐 시각 %이 지금 구간 시작 %보다 앞', p_equipment_id, v_at, cur.start_at
                USING ERRCODE = '23514';
        END IF;
        UPDATE equipment_state_log SET end_at = v_at WHERE state_log_id = cur.state_log_id;
    END IF;
    INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, warn_marker,
                                     reason_suggested_code, reason_status, alarm_event_id, pm_record_id)
    VALUES (p_equipment_id, p_state_code, CASE WHEN p_state_code IN ('SETUP','MAINT') THEN NULL ELSE p_execution END, v_at,
            coalesce(p_warn_marker, false),
            CASE WHEN p_state_code <> 'RUN' THEN p_reason_suggested_code END,
            CASE WHEN p_state_code <> 'RUN' AND p_reason_suggested_code IS NOT NULL THEN 'SUGGESTED' END,
            p_alarm_event_id, p_pm_record_id)
    RETURNING state_log_id INTO v_id;
    RETURN v_id;
END $$;

-- 공정 실적 더하기 (같은 로트·공정·설비·교대면 한 행에 더함 — ux_operation_report).
-- 생산 수량 = 양품 + 재작업 + 불량 (R-19). OP-30이면 이번에 더한 부품 수만큼 공구 사용을 누적한다.
CREATE OR REPLACE FUNCTION fn_report_production(p_lot_no text, p_equipment_id text, p_worker text, p_gq int, p_rq int DEFAULT 0,
    p_sq int DEFAULT 0, p_at timestamptz DEFAULT NULL, p_shift_id text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at    timestamptz := coalesce(p_at, app_now());
    v_proc  text := fn_equipment_process(p_equipment_id);
    v_shift text := p_shift_id;
    v_id    bigint;
    v_pq    int := coalesce(p_gq, 0) + coalesce(p_rq, 0) + coalesce(p_sq, 0);
BEGIN
    IF v_pq <= 0 THEN RAISE EXCEPTION '실적 수량이 0' USING ERRCODE = '22023'; END IF;
    IF v_shift IS NULL THEN
        SELECT shift_id INTO v_shift FROM shift WHERE start_at <= v_at AND end_at > v_at;
        IF v_shift IS NULL THEN
            RAISE EXCEPTION '% 시각에 해당하는 교대가 없음 (휴식·교대 사이 실적)', v_at USING ERRCODE = '23514';
        END IF;
    END IF;
    INSERT INTO operation_report AS r (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, pq, gq, rq, sq)
    VALUES (p_lot_no, v_proc, p_equipment_id, p_worker, v_shift, v_at, v_pq, coalesce(p_gq, 0), coalesce(p_rq, 0), coalesce(p_sq, 0))
    ON CONFLICT (lot_no, process_code, equipment_id, shift_id) DO UPDATE
       SET pq = r.pq + EXCLUDED.pq, gq = r.gq + EXCLUDED.gq, rq = r.rq + EXCLUDED.rq, sq = r.sq + EXCLUDED.sq,
           end_at = greatest(coalesce(r.end_at, r.start_at + interval '1 second'), v_at)
    RETURNING op_report_id INTO v_id;
    IF v_proc = 'OP-30' THEN
        PERFORM fn_add_tool_usage(v_id, v_pq, v_at);
    END IF;
    RETURN v_id;
END $$;

-- 작업지시 만들기 (시뮬레이터·생성기 쪽 계획). 번호 PO-YYMM-NNN
CREATE OR REPLACE FUNCTION fn_create_order(p_product_code text, p_order_qty int, p_due_at timestamptz,
    p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); v_no text;
BEGIN
    v_no := fn_next_doc_no('PO', v_at);
    INSERT INTO production_order (order_no, product_code, order_qty, created_at, due_at)
    VALUES (v_no, p_product_code, p_order_qty, v_at, p_due_at);
    RETURN v_no;
END $$;

-- 로트 투입 (OP-10 시작): 로트 번호 = LOT-<작업지시 몸통>-<순번>, 투입 교대 = 그 시각의 교대,
-- 원자재 사용 거래(부품 1개 = 원자재 1단위 [제안]), 검사 방식(보통/강화, R-28), 작업지시 → 생산 중.
-- 원자재 로트가 사용 가능이 아니면 트리거가 막는다 (R-06a). 투입 합이 작업지시 수량을 넘으면 막는다 (R-08).
CREATE OR REPLACE FUNCTION fn_start_lot(p_order_no text, p_material_lot_no text, p_input_qty int,
    p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    o production_order%ROWTYPE; v_seq int; v_lot text; v_shift text; v_item text; v_used int;
BEGIN
    SELECT * INTO o FROM production_order WHERE order_no = p_order_no FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '작업지시 % 없음', p_order_no USING ERRCODE = '23503'; END IF;
    IF o.status NOT IN ('WAITING','IN_PROGRESS') THEN
        RAISE EXCEPTION '작업지시 %는 투입할 수 없는 상태 (%)', p_order_no, o.status USING ERRCODE = '23514';
    END IF;
    SELECT coalesce(sum(input_qty), 0) INTO v_used FROM production_lot WHERE order_no = p_order_no;
    IF v_used + p_input_qty > o.order_qty THEN
        RAISE EXCEPTION 'R-08: 투입 합 %가 작업지시 수량 %를 넘음', v_used + p_input_qty, o.order_qty USING ERRCODE = '23514';
    END IF;
    SELECT shift_id INTO v_shift FROM shift WHERE start_at <= v_at AND end_at > v_at;
    IF v_shift IS NULL THEN RAISE EXCEPTION '% 시각에 교대가 없음 — 투입 불가', v_at USING ERRCODE = '23514'; END IF;
    SELECT coalesce(max(lot_seq), 0) + 1 INTO v_seq FROM production_lot WHERE order_no = p_order_no;
    v_lot := 'LOT-' || substr(p_order_no, 4) || '-' || v_seq;
    INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty)
    VALUES (v_lot, p_order_no, v_seq, v_shift, p_material_lot_no, p_input_qty);
    SELECT material_item_no INTO v_item FROM product WHERE product_code = o.product_code;
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, lot_no)
    VALUES (v_item, 'USE', -p_input_qty, v_at, 'LOT_INPUT', v_lot);
    PERFORM fn_check_stock(v_item, NULL, v_at);
    PERFORM fn_create_inspection_plan(v_lot);
    IF o.status = 'WAITING' THEN
        UPDATE production_order SET status = 'IN_PROGRESS', started_at = v_at WHERE order_no = p_order_no;
    END IF;
    RETURN v_lot;
END $$;

-- 로트가 OP-50에 도착 → 검사 대기 (6.8: 생산 중 → 검사 대기만)
CREATE OR REPLACE FUNCTION fn_lot_to_inspection(p_lot_no text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE production_lot SET status = 'WAIT_INSPECTION' WHERE lot_no = p_lot_no AND status = 'IN_PROCESS';
    IF NOT FOUND THEN
        RAISE EXCEPTION '로트 %는 생산 중이 아님 — 검사 대기로 바꿀 수 없음', p_lot_no USING ERRCODE = '23514';
    END IF;
END $$;

-- 근무일·교대 만들기 (시연 10/1부터 — 생성기 9월 기록에는 9/30까지만 있다). 이미 있으면 그대로. 반환: 새로 만든 교대 수
-- 값은 가장 최근 근무일을 본뜬다 (주간 08:00~17:00·야간 20:00~05:00, 계획 시간·목표·반장, 하루 목표 180 — 설계서 5.2).
-- 야간 이월(carry_over_qty)은 0으로 두고 주간이 끝나면 fn_refresh_carry_over가 채운다 (R-88). 휴무일 지정은 MGR이 work_day에서
CREATE OR REPLACE FUNCTION fn_ensure_work_day(p_date date) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE tpl date; n int := 0;
BEGIN
    SELECT max(work_date) INTO tpl FROM work_day WHERE is_workday AND work_date < p_date
       AND EXISTS (SELECT 1 FROM shift s WHERE s.work_date = work_day.work_date);
    IF tpl IS NULL THEN RETURN 0; END IF;
    INSERT INTO work_day (work_date, is_workday, daily_target_qty)
    SELECT p_date, true, daily_target_qty FROM work_day WHERE work_date = tpl
    ON CONFLICT (work_date) DO NOTHING;
    IF NOT (SELECT is_workday FROM work_day WHERE work_date = p_date) THEN RETURN 0; END IF;
    WITH ins AS (
        INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, carry_over_qty,
                           supervisor_user_id)
        SELECT to_char(p_date, 'YYYY-MM-DD') || '-' || left(s.shift_type, 1), p_date, s.shift_type,
               s.start_at + (p_date - tpl) * interval '1 day', s.end_at + (p_date - tpl) * interval '1 day',
               s.planned_time_min, s.target_qty, 0, s.supervisor_user_id
          FROM shift s WHERE s.work_date = tpl
        ON CONFLICT DO NOTHING RETURNING 1)
    SELECT count(*) INTO n FROM ins;
    RETURN n;
END $$;
COMMENT ON FUNCTION fn_ensure_work_day(date) IS '근무일·교대 2개를 가장 최근 근무일을 본떠 만든다 (적재 뒤 10/1, 스케줄러가 오늘·내일)';
