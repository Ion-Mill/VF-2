-- =====================================================================
-- 86_qr.sql — QR 찍은 기록 (2026-10-13 가정 "재고·로트는 QR로 관리" [제안])
--   · qr_scan은 추가만 한다 (고치기·지우기 금지 — 수불대장과 같은 규칙)
--   · 출하 줄마다 QR 확인 여부: fn_ship_qr_unchecked(출하 번호) = 아직 안 찍은 로트 목록
-- =====================================================================
SET client_min_messages = warning;
DROP TRIGGER IF EXISTS qr_scan_append_only ON qr_scan;
RESET client_min_messages;
CREATE TRIGGER qr_scan_append_only BEFORE UPDATE OR DELETE ON qr_scan
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();

CREATE OR REPLACE FUNCTION fn_ship_qr_unchecked(p_shipment_no text) RETURNS text[]
LANGUAGE sql STABLE AS $$
    SELECT coalesce(array_agg(sl.lot_no ORDER BY sl.lot_passed_at, sl.lot_no), '{}')
      FROM shipment_line sl
     WHERE sl.shipment_no = p_shipment_no
       AND NOT EXISTS (SELECT 1 FROM qr_scan q
                        WHERE q.purpose = 'SHIP_CHECK' AND q.result = 'OK'
                          AND q.shipment_no = sl.shipment_no AND q.ref_no = sl.lot_no);
$$;
