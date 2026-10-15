-- =====================================================================
-- 85_access.sql — 역할별 권한을 DB에서도 한 번 더 (기획서 13.2, API명세서 INV-02)
--   · 원자재 로트는 원자재 품목만. 입고 거래는 품목 관리 역할만(R-77, 20_integrity)이라
--     MNT가 자기 관리 품목(정비 소모품)을 "원자재 로트"로 등록할 수 있던 틈을 막는다.
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_raw_material_lot_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_cat text;
BEGIN
    SELECT category INTO v_cat FROM inventory_item WHERE item_no = NEW.item_no;
    IF v_cat IS DISTINCT FROM 'MATERIAL' THEN
        RAISE EXCEPTION '원자재 로트에는 원자재 품목만 (% 은 %)', NEW.item_no, coalesce(v_cat, '없는 품목')
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
SET client_min_messages = warning;
DROP TRIGGER IF EXISTS raw_material_lot_item ON raw_material_lot;
RESET client_min_messages;
CREATE TRIGGER raw_material_lot_item BEFORE INSERT OR UPDATE OF item_no ON raw_material_lot
    FOR EACH ROW EXECUTE FUNCTION trg_raw_material_lot_item();
