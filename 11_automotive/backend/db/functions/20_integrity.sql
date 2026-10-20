-- =====================================================================
-- 20_integrity.sql — 여러 표를 봐야 하는 규칙 (트리거)
-- 원칙 (docs/02_물리ERD.md 7장):
--   * 한 행 안에서 되는 규칙은 CHECK (schema/), 여러 표를 보는 규칙은 여기 트리거.
--   * "상태가 바뀌는 순간"의 규칙(예: 확정하려면 잠금·표지 9개 체크)은 UPDATE 때만 확인한다.
--     생성기가 이미 확정된 과거 기록을 INSERT로 넣을 때는 순서상 하위 행이 아직 없기 때문이다.
--     그런 기록은 db/checks/validate_loaded_data.sql 의 점검 쿼리로 확인한다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 공통 도우미
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_user_role(p_user_id text) RETURNS text
LANGUAGE sql STABLE AS $$ SELECT role_code FROM app_user WHERE user_id = p_user_id $$;

-- 사람 칸에 정해진 역할만 들어오게 한다 (R-50·R-51). 비서는 app_user가 아니므로 여기서 걸린다
CREATE OR REPLACE FUNCTION fn_require_role(p_user_id text, p_roles text[], p_what text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_role text;
BEGIN
    IF p_user_id IS NULL THEN RETURN; END IF;
    SELECT role_code INTO v_role FROM app_user WHERE user_id = p_user_id AND is_active;
    IF v_role IS NULL THEN
        RAISE EXCEPTION '%: 사용 중인 사용자가 아님 (%)', p_what, p_user_id USING ERRCODE = '23514';
    END IF;
    IF NOT v_role = ANY (p_roles) THEN
        RAISE EXCEPTION '%: % 역할만 할 수 있음 (% = %)', p_what, array_to_string(p_roles, '·'), p_user_id, v_role
            USING ERRCODE = '23514';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_equipment_process(p_equipment_id text) RETURNS text
LANGUAGE sql STABLE AS $$ SELECT process_code FROM equipment WHERE equipment_id = p_equipment_id $$;

-- ---------------------------------------------------------------------
-- 교대 반장은 SUP (5.A.6)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_shift_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.supervisor_user_id, ARRAY['SUP'], 'shift.supervisor_user_id');
    RETURN NEW;
END $$;
CREATE TRIGGER shift_check BEFORE INSERT OR UPDATE OF supervisor_user_id ON shift
    FOR EACH ROW EXECUTE FUNCTION trg_shift_check();

-- ---------------------------------------------------------------------
-- 안전 재고는 MGR만 정한다 (R-58)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_inventory_item_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.safety_stock_set_by, ARRAY['MGR'], 'inventory_item.safety_stock_set_by');
    RETURN NEW;
END $$;
CREATE TRIGGER inventory_item_check BEFORE INSERT OR UPDATE OF safety_stock_set_by ON inventory_item
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_item_check();

-- ---------------------------------------------------------------------
-- R-06a 생산 로트의 원자재 로트는 투입 때 "사용 가능"
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_production_lot_material() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_status text;
BEGIN
    SELECT status INTO v_status FROM raw_material_lot WHERE material_lot_no = NEW.material_lot_no;
    IF v_status IS DISTINCT FROM 'AVAILABLE' THEN
        RAISE EXCEPTION 'R-06a: 원자재 로트 %는 사용 가능 상태가 아님 (%)', NEW.material_lot_no, v_status
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER production_lot_material BEFORE INSERT OR UPDATE OF material_lot_no ON production_lot
    FOR EACH ROW EXECUTE FUNCTION trg_production_lot_material();

-- ---------------------------------------------------------------------
-- R-24a 로트 상태는 6.8 순서로만 (UPDATE 때)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_production_lot_status() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
    IF NEW.status = OLD.status THEN RETURN NEW; END IF;
    -- 생성기 10/1 기록이 9월 끝 로트를 덮어쓸 때(적재)는 이미 지나간 상태 흐름의 마지막 값이 온다 — 단계 확인은 운영 중에만
    IF current_setting('app.loading', true) = 'on' THEN RETURN NEW; END IF;
    ok := CASE OLD.status
        WHEN 'IN_PROCESS'      THEN NEW.status IN ('WAIT_INSPECTION','ON_HOLD')
        WHEN 'WAIT_INSPECTION' THEN NEW.status IN ('WAIT_JUDGEMENT','HOLD_REVIEW','PASSED','ON_HOLD')
        WHEN 'WAIT_JUDGEMENT'  THEN NEW.status IN ('PASSED','HOLD_REVIEW','ON_HOLD')
        WHEN 'HOLD_REVIEW'     THEN NEW.status IN ('ON_HOLD','PASSED')
        WHEN 'ON_HOLD'         THEN NEW.status IN ('RELEASED','SCRAPPED')
        WHEN 'RELEASED'        THEN NEW.status IN ('PASSED')
        ELSE false END;
    IF NOT ok THEN
        RAISE EXCEPTION 'R-24a: 로트 % 상태를 %에서 %로 바꿀 수 없음', NEW.lot_no, OLD.status, NEW.status
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER production_lot_status BEFORE UPDATE OF status ON production_lot
    FOR EACH ROW EXECUTE FUNCTION trg_production_lot_status();

-- ---------------------------------------------------------------------
-- R-13 재공은 한도 이하
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_wip_log_limit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_limit int;
BEGIN
    SELECT limit_qty INTO v_limit FROM wip_buffer WHERE buffer_code = NEW.buffer_code;
    IF NEW.wip_qty > v_limit THEN
        RAISE EXCEPTION 'R-13: % 재공 %개가 한도 %개를 넘음', NEW.buffer_code, NEW.wip_qty, v_limit USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER wip_log_limit BEFORE INSERT OR UPDATE ON wip_log
    FOR EACH ROW EXECUTE FUNCTION trg_wip_log_limit();

-- ---------------------------------------------------------------------
-- R-24 알람은 그 알람의 적용 공정 설비에서만 난다
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_alarm_event_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_alarm_process text;
BEGIN
    SELECT process_code INTO v_alarm_process FROM alarm_master WHERE alarm_code = NEW.alarm_code;
    IF v_alarm_process IS DISTINCT FROM fn_equipment_process(NEW.equipment_id) THEN
        RAISE EXCEPTION 'R-24: 알람 %는 % 공정 알람인데 설비 %에서 남', NEW.alarm_code, v_alarm_process, NEW.equipment_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER alarm_event_check BEFORE INSERT OR UPDATE OF alarm_code, equipment_id ON alarm_event
    FOR EACH ROW EXECUTE FUNCTION trg_alarm_event_check();

-- ---------------------------------------------------------------------
-- 설비 상태 구간: R-01·R-22 DOWN = 정지 등급 알람(같은 설비), R-21 사유 확정 = SUP
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_state_log_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sev text; v_eq text;
BEGIN
    IF NEW.alarm_event_id IS NOT NULL THEN
        SELECT severity_at_event, equipment_id INTO v_sev, v_eq FROM alarm_event WHERE alarm_event_id = NEW.alarm_event_id;
        IF v_eq <> NEW.equipment_id THEN
            RAISE EXCEPTION '상태 구간의 알람 %는 다른 설비(%) 알람', NEW.alarm_event_id, v_eq USING ERRCODE = '23514';
        END IF;
        IF NEW.state_code = 'DOWN' AND v_sev <> 'STOP' THEN
            RAISE EXCEPTION 'R-22: DOWN은 정지 등급 알람만 (알람 % 등급 %)', NEW.alarm_event_id, v_sev USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM fn_require_role(NEW.reason_confirmed_by, ARRAY['SUP'], 'R-21 정지 사유 확정');
    PERFORM fn_require_role(NEW.reason_entered_by, ARRAY['OPR','MNT','SUP'], '정지 사유 입력');
    RETURN NEW;
END $$;
CREATE TRIGGER state_log_check BEFORE INSERT OR UPDATE ON equipment_state_log
    FOR EACH ROW EXECUTE FUNCTION trg_state_log_check();

-- ---------------------------------------------------------------------
-- 공구는 OP-30 설비에만 (5.E.2), 공구 교체는 OPR·MNT (13.2)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_tool_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF fn_equipment_process(NEW.equipment_id) <> 'OP-30' THEN
        RAISE EXCEPTION '공구는 OP-30 설비에만 (%)', NEW.equipment_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tool_check BEFORE INSERT OR UPDATE OF equipment_id ON tool
    FOR EACH ROW EXECUTE FUNCTION trg_tool_check();

CREATE OR REPLACE FUNCTION trg_tool_change_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.changed_by, ARRAY['OPR','MNT'], '공구 교체 기록');
    RETURN NEW;
END $$;
CREATE TRIGGER tool_change_check BEFORE INSERT OR UPDATE ON tool_change
    FOR EACH ROW EXECUTE FUNCTION trg_tool_change_check();

-- ---------------------------------------------------------------------
-- 로트 보류·해제·폐기의 사람 (R-27, 5.B.7): 보류·해제 SUP·MGR, 폐기 제안 SUP, 폐기 승인 MGR, 보통 복귀 SUP
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_lot_hold_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.held_by, ARRAY['SUP','MGR'], '로트 보류');
    PERFORM fn_require_role(NEW.released_by, ARRAY['SUP','MGR'], '로트 해제');
    PERFORM fn_require_role(NEW.scrap_proposed_by, ARRAY['SUP'], '폐기 제안');
    PERFORM fn_require_role(NEW.scrap_approved_by, ARRAY['MGR'], '폐기 승인');
    PERFORM fn_require_role(NEW.normal_resumed_by, ARRAY['SUP'], '보통 검사 복귀');
    RETURN NEW;
END $$;
CREATE TRIGGER lot_hold_check BEFORE INSERT OR UPDATE ON lot_hold
    FOR EACH ROW EXECUTE FUNCTION trg_lot_hold_check();

-- ---------------------------------------------------------------------
-- 예방 정비 기록 저장은 MNT (5.D.8)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_pm_record_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.recorded_by, ARRAY['MNT'], '예방 정비 기록 저장');
    RETURN NEW;
END $$;
CREATE TRIGGER pm_record_check BEFORE INSERT OR UPDATE OF recorded_by ON pm_record
    FOR EACH ROW EXECUTE FUNCTION trg_pm_record_check();

-- ---------------------------------------------------------------------
-- 정비 작업지시서 (5.D.1, R-02·R-31a·R-71, 6.13)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_work_order_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sev text; v_eq text; v_rule text; ok boolean;
BEGIN
    IF fn_equipment_process(NEW.equipment_id) <> 'OP-30' THEN
        RAISE EXCEPTION 'R-02: 작업지시서는 OP-30 설비만 (%)', NEW.equipment_id USING ERRCODE = '23514';
    END IF;
    IF NEW.alarm_event_id IS NOT NULL THEN
        SELECT severity_at_event, equipment_id INTO v_sev, v_eq FROM alarm_event WHERE alarm_event_id = NEW.alarm_event_id;
        IF v_sev <> 'STOP' OR v_eq <> NEW.equipment_id THEN
            RAISE EXCEPTION 'R-02: 작업지시서 알람은 같은 설비의 정지 등급이어야 함 (알람 %: %·%)',
                NEW.alarm_event_id, v_eq, v_sev USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.trigger_notification_id IS NOT NULL THEN
        SELECT rule_code INTO v_rule FROM notification WHERE notification_id = NEW.trigger_notification_id;
        IF v_rule IS NOT NULL AND v_rule <> 'REPEAT_ALARM_2' THEN
            RAISE EXCEPTION 'R-71: 계기 알림은 반복 알람 2단계여야 함 (%)', v_rule USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM fn_require_role(NEW.assignee_user_id, ARRAY['MNT'], '작업지시서 담당');
    PERFORM fn_require_role(NEW.approved_by, ARRAY['SUP','MGR'], '작업지시서 승인');
    PERFORM fn_require_role(NEW.cancelled_by, ARRAY['MGR'], '작업지시서 취소');
    IF TG_OP = 'UPDATE' AND NEW.status <> OLD.status THEN
        ok := CASE OLD.status
            WHEN 'AI_DRAFT'    THEN NEW.status IN ('EDITING','CANCELLED')
            WHEN 'EDITING'     THEN NEW.status IN ('APPROVED','CANCELLED')
            WHEN 'APPROVED'    THEN NEW.status IN ('IN_PROGRESS','CANCELLED')
            WHEN 'IN_PROGRESS' THEN NEW.status IN ('DONE')
            ELSE false END;
        IF NOT ok THEN
            RAISE EXCEPTION '6.13: 작업지시서 % 상태를 %에서 %로 바꿀 수 없음', NEW.wo_no, OLD.status, NEW.status
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER work_order_check BEFORE INSERT OR UPDATE ON maintenance_work_order
    FOR EACH ROW EXECUTE FUNCTION trg_work_order_check();

-- 간이 작업기록에 잠금·표지 9단계가 필요한 알람인가 (R-32·33, DOC-05 §2.4·§7): 잠금 수준 FULL·TWO_POINT
CREATE OR REPLACE FUNCTION fn_simple_record_needs_loto(p_alarm_event_id bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT m.lockout_level IN ('FULL','TWO_POINT')
                       FROM alarm_event a JOIN alarm_master m USING (alarm_code)
                      WHERE a.alarm_event_id = p_alarm_event_id), false);
$$;

-- ---------------------------------------------------------------------
-- 작업기록서 (5.D.4, R-32, 6.15)
--   확정자: 작업기록서 = MNT / 간이: 주의 등급 = OPR·MNT, 다른 공정 정지 등급 = MNT, 원인 점검 = MNT
--   확인자 = SUP
--   확정 순간(UPDATE로 CONFIRMED가 될 때): 잠금·표지가 필요한 기록은 9단계 모두 체크 (R-32)
--   간이 작업기록의 잠금·표지 필요 여부는 DB가 정한다 (2026-10-20, R-32·33, FR-MNT-05-15, NFR-SAFE-02·03): 알람 코드집의
--   잠금 수준이 전체 잠금(FULL — 다른 공정 정지 등급) 또는 보충용 2점 잠금(TWO_POINT — 예: 2075, DOC-05 §2.4)이면 화면이
--   보낸 값과 상관없이 참. 한 번 참이면 거짓으로 못 바꾼다. 생성기 적재(app.loading)는 9월 기록 그대로 둔다
-- ---------------------------------------------------------------------
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
CREATE TRIGGER work_record_check BEFORE INSERT OR UPDATE ON work_record
    FOR EACH ROW EXECUTE FUNCTION trg_work_record_check();

-- ---------------------------------------------------------------------
-- 보고서·출하 확정자 (R-36, 13.1)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_shift_report_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sup text;
BEGIN
    IF NEW.confirmed_by IS NOT NULL THEN
        SELECT supervisor_user_id INTO v_sup FROM shift WHERE shift_id = NEW.shift_id;
        IF NEW.confirmed_by <> v_sup THEN
            RAISE EXCEPTION 'R-36: 교대 보고서는 그 교대 반장(%)만 확정 (%)', v_sup, NEW.confirmed_by USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER shift_report_check BEFORE INSERT OR UPDATE OF confirmed_by ON shift_report
    FOR EACH ROW EXECUTE FUNCTION trg_shift_report_check();

CREATE OR REPLACE FUNCTION trg_daily_report_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.confirmed_by, ARRAY['MGR'], 'R-36 일일 보고서 확정');
    RETURN NEW;
END $$;
CREATE TRIGGER daily_report_check BEFORE INSERT OR UPDATE OF confirmed_by ON daily_report
    FOR EACH ROW EXECUTE FUNCTION trg_daily_report_check();

CREATE OR REPLACE FUNCTION trg_shipment_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.confirmed_by, ARRAY['SUP'], '출하 확정');
    RETURN NEW;
END $$;
CREATE TRIGGER shipment_check BEFORE INSERT OR UPDATE OF confirmed_by ON shipment
    FOR EACH ROW EXECUTE FUNCTION trg_shipment_check();

-- ---------------------------------------------------------------------
-- 검사 결과: 측정자 = OPR, 반장 확인 = SUP (5.F.4)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_inspection_result_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.inspector_id, ARRAY['OPR'], '측정자');
    PERFORM fn_require_role(NEW.checked_by, ARRAY['SUP'], '측정값 반장 확인');
    RETURN NEW;
END $$;
CREATE TRIGGER inspection_result_check BEFORE INSERT OR UPDATE OF inspector_id, checked_by ON inspection_result
    FOR EACH ROW EXECUTE FUNCTION trg_inspection_result_check();

-- ---------------------------------------------------------------------
-- 설정은 MGR (R-58, NFR-SEC-04)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_notification_rule_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.updated_by, ARRAY['MGR'], '알림 규칙 설정');
    RETURN NEW;
END $$;
CREATE TRIGGER notification_rule_check BEFORE INSERT OR UPDATE ON notification_rule
    FOR EACH ROW EXECUTE FUNCTION trg_notification_rule_check();

CREATE OR REPLACE FUNCTION trg_internal_doc_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.approved_by, ARRAY['MGR'], '사내 문서 개정 승인');
    RETURN NEW;
END $$;
CREATE TRIGGER internal_doc_check BEFORE INSERT OR UPDATE OF approved_by ON internal_doc
    FOR EACH ROW EXECUTE FUNCTION trg_internal_doc_check();

-- ---------------------------------------------------------------------
-- 입출고 거래
--   (1) 기록자: 입고 등록·월말 실사 = 그 품목의 관리 역할 (R-77), 로트 합격 입고 = 시스템(비움)
--   (2) 들어오면 재고 수량에 더한다 → 음수면 inventory_item CHECK가 막는다 (R-11)
--   (3) 거래는 고치지 않는다. 지우기는 보관 기간 작업만 (세션 설정 app.allow_purge = on)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_inventory_txn_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_owner text;
BEGIN
    IF NEW.source_kind IN ('RECEIPT','STOCKTAKE','MATERIAL_RECEIPT') THEN
        SELECT owner_role INTO v_owner FROM inventory_item WHERE item_no = NEW.item_no;
        IF NEW.txn_by IS NULL THEN
            RAISE EXCEPTION 'R-77: 입고·실사 거래는 기록자 필수' USING ERRCODE = '23514';
        END IF;
        PERFORM fn_require_role(NEW.txn_by, ARRAY[v_owner], 'R-77 품목 관리 역할 (' || NEW.item_no || ')');
    ELSIF NEW.source_kind = 'LOT_PASS' AND NEW.txn_by IS NOT NULL THEN
        RAISE EXCEPTION '로트 합격 입고는 시스템 거래 (txn_by 비움)' USING ERRCODE = '23514';
    ELSIF NEW.source_kind = 'SHIPMENT' THEN
        PERFORM fn_require_role(NEW.txn_by, ARRAY['SUP'], '출하 출고');
    ELSIF NEW.source_kind = 'TOOL_CHANGE' THEN
        PERFORM fn_require_role(NEW.txn_by, ARRAY['OPR','MNT'], '공구 사용');
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER inventory_txn_check BEFORE INSERT ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_txn_check();

CREATE OR REPLACE FUNCTION trg_inventory_txn_apply() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE inventory_item SET on_hand_qty = on_hand_qty + NEW.qty_change WHERE item_no = NEW.item_no;
    RETURN NULL;
EXCEPTION WHEN check_violation THEN
    RAISE EXCEPTION 'R-11: % 재고가 음수가 됨 (거래 %)', NEW.item_no, NEW.qty_change USING ERRCODE = '23514';
END $$;
CREATE TRIGGER inventory_txn_apply AFTER INSERT ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_txn_apply();

-- 재고가 움직이면 그 품목의 재고 부족을 다시 본다 (R-39, FR-AST-02-07·FR-INV-01-07 — 2026-10-20). 전에는 작업기록서 확정·공구
--   교체·실사 API만 불러, 예방 정비 확정의 소모품 차감으로 줄어도 재고 부족 알림이 안 떴다. 이름 순서상 inventory_txn_apply 뒤에 돈다
CREATE OR REPLACE FUNCTION trg_inventory_txn_stock() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    PERFORM fn_check_stock(NEW.item_no, NEW.txn_by, NEW.txn_at);
    RETURN NULL;
END $$;
CREATE TRIGGER inventory_txn_stock AFTER INSERT ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_txn_stock();

-- 추가만 하는 표 (수불대장·문서 버전·접속 기록)
CREATE OR REPLACE FUNCTION trg_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.allow_purge', true) = 'on' THEN
        RETURN OLD;   -- 보관 기간 작업 (db/functions/40_retention.sql)
    END IF;
    RAISE EXCEPTION '%은(는) 추가만 할 수 있음 (%)', TG_TABLE_NAME, TG_OP USING ERRCODE = '42501';
END $$;
CREATE TRIGGER inventory_txn_append_only BEFORE UPDATE OR DELETE ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();
CREATE TRIGGER document_revision_append_only BEFORE UPDATE OR DELETE ON document_revision
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();
CREATE TRIGGER document_revision_change_append_only BEFORE UPDATE OR DELETE ON document_revision_change
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();
CREATE TRIGGER access_log_append_only BEFORE UPDATE OR DELETE ON access_log
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();

-- ---------------------------------------------------------------------
-- R-35 확정된 문서는 잠긴다 — 확정 뒤 내용을 바꾸려면
--   ① current_version을 1 올리고 ② 그 버전의 document_revision(사유 있음)이 먼저 있어야 한다.
-- 워크플로 칸(상태·확정자·시각 등)만 바뀌는 것은 허용한다.
-- 인자: TG_ARGV[0] 문서 종류, [1] 키 칼럼, [2] 잠긴 상태들(쉼표), [3] 내용 비교에서 뺄 칼럼들(쉼표)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_doc_lock() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_locked  text[] := string_to_array(TG_ARGV[2], ',');
    v_exempt  text[] := string_to_array(TG_ARGV[3], ',') || ARRAY['current_version'];
    v_old     jsonb := to_jsonb(OLD) - v_exempt;
    v_new     jsonb := to_jsonb(NEW) - v_exempt;
    v_key     text  := to_jsonb(NEW) ->> TG_ARGV[1];
    v_reason  text;
BEGIN
    IF NOT (OLD.status = ANY (v_locked)) OR v_old = v_new THEN
        RETURN NEW;
    END IF;
    IF NEW.current_version <> OLD.current_version + 1 THEN
        RAISE EXCEPTION 'R-35: 확정된 %(%)는 새 버전으로만 고칠 수 있음 (current_version % → %)',
            TG_ARGV[0], v_key, OLD.current_version, NEW.current_version USING ERRCODE = '23514';
    END IF;
    SELECT reason INTO v_reason FROM document_revision
     WHERE doc_type = TG_ARGV[0] AND doc_key = v_key AND version_no = NEW.current_version;
    IF btrim(coalesce(v_reason, '')) = '' THEN
        RAISE EXCEPTION 'R-35: 확정 뒤 수정은 사유가 있는 문서 버전(v%)이 먼저 있어야 함 (% %)',
            NEW.current_version, TG_ARGV[0], v_key USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER shift_report_lock BEFORE UPDATE ON shift_report FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('SHIFT_REPORT', 'shift_id', 'CONFIRMED,REVISED', 'status,confirmed_by,confirmed_at');
CREATE TRIGGER daily_report_lock BEFORE UPDATE ON daily_report FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('DAILY_REPORT', 'work_date', 'CONFIRMED,REVISED', 'status,confirmed_by,confirmed_at');
CREATE TRIGGER work_record_lock BEFORE UPDATE ON work_record FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('WORK_RECORD', 'record_no', 'CONFIRMED,CHECKED', 'status,confirmed_by,confirmed_at,checked_by,checked_at');
CREATE TRIGGER work_order_lock BEFORE UPDATE ON maintenance_work_order FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('WORK_ORDER', 'wo_no', 'APPROVED,IN_PROGRESS,DONE,CANCELLED',
        'status,approved_by,approved_at,cancelled_by,cancelled_at,cancel_reason,completed_at,trigger_notification_id');
CREATE TRIGGER pm_record_lock BEFORE UPDATE ON pm_record FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('PM_RECORD', 'pm_record_id', 'CONFIRMED', 'status');
CREATE TRIGGER shipment_lock BEFORE UPDATE ON shipment FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('SHIPMENT', 'shipment_no', 'CONFIRMED,REVISED', 'status,confirmed_by,shipped_at,fifo_skip_reason');

-- ---------------------------------------------------------------------
-- 알림이 생기거나 처리되면 실시간 채널로 알린다 (SSE: app/routers/stream.py가 LISTEN)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_notify_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- 생성기 대량 적재 중에는 알리지 않는다 (db/load/load_generated.sh가 app.loading=on으로 둔다)
    IF current_setting('app.loading', true) = 'on' THEN RETURN NULL; END IF;
    PERFORM pg_notify('mom_events', json_build_object(
        'table', TG_TABLE_NAME, 'op', TG_OP,
        'id', CASE TG_TABLE_NAME
                WHEN 'notification' THEN (to_jsonb(NEW) ->> 'notification_id')
                WHEN 'equipment_state_log' THEN (to_jsonb(NEW) ->> 'state_log_id')
                WHEN 'alarm_event' THEN (to_jsonb(NEW) ->> 'alarm_event_id')
                WHEN 'wip_log' THEN (to_jsonb(NEW) ->> 'buffer_code')
                WHEN 'bottleneck_log' THEN (to_jsonb(NEW) ->> 'bottleneck_log_id')
                WHEN 'document_revision' THEN (to_jsonb(NEW) ->> 'doc_key')
                WHEN 'work_record' THEN (to_jsonb(NEW) ->> 'record_no')
              END,
        'equipment_id', to_jsonb(NEW) ->> 'equipment_id',
        -- 실시간 사건 이름을 정하는 데 필요한 것만 (API명세서 3장): 알림 중요도(긴급 팝업), 문서 종류, 상태
        'importance', to_jsonb(NEW) ->> 'importance',
        'doc_type', to_jsonb(NEW) ->> 'doc_type',
        'status', to_jsonb(NEW) ->> 'status')::text);
    RETURN NULL;
END $$;
CREATE TRIGGER notification_notify AFTER INSERT OR UPDATE ON notification
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER state_log_notify AFTER INSERT OR UPDATE ON equipment_state_log
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER alarm_event_notify AFTER INSERT ON alarm_event
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
-- 재공·병목·문서 버전·작업기록서 확정(지표 다시 계산) — 화면이 해당 API를 다시 부른다 (API명세서 3장)
CREATE TRIGGER wip_log_notify AFTER INSERT ON wip_log
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER bottleneck_log_notify AFTER INSERT ON bottleneck_log
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER document_revision_notify AFTER INSERT ON document_revision
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER work_record_notify AFTER UPDATE OF status ON work_record
    FOR EACH ROW WHEN (NEW.status IN ('CONFIRMED','CHECKED') AND OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION trg_notify_event();

-- 병목 기록: 바로 앞 줄과 공정 또는 원인이 달라야 한다 (논리 ERD 5.B.6, 2026-10-13). 앞 줄의 새 병목 = 이 줄의 이전 병목
CREATE OR REPLACE FUNCTION trg_bottleneck_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p bottleneck_log%ROWTYPE;
BEGIN
    SELECT * INTO p FROM bottleneck_log WHERE changed_at < NEW.changed_at AND bottleneck_log_id <> NEW.bottleneck_log_id
     ORDER BY changed_at DESC LIMIT 1;
    IF FOUND AND p.new_process_code = NEW.new_process_code AND p.cause_code = NEW.cause_code THEN
        RAISE EXCEPTION '병목 기록: 앞 줄(%)과 공정·원인이 같음 (%·%)', p.changed_at, NEW.new_process_code, NEW.cause_code
            USING ERRCODE = '23514';
    END IF;
    IF FOUND AND NEW.prev_process_code IS DISTINCT FROM p.new_process_code THEN
        RAISE EXCEPTION '병목 기록: 이전 병목(%)이 앞 줄의 새 병목(%)과 다름', NEW.prev_process_code, p.new_process_code
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER bottleneck_changed BEFORE INSERT ON bottleneck_log FOR EACH ROW EXECUTE FUNCTION trg_bottleneck_changed();
