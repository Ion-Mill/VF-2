-- =====================================================================
-- 10_clock_numbering.sql — 시연 시계와 업무 번호
-- =====================================================================

-- ---------------------------------------------------------------------
-- app_now(): 업무 시각. REAL이면 now(), SIM이면 기준점 + (지난 실제 시간 × 배속)
-- 한 트랜잭션 안에서는 같은 값 (now()가 트랜잭션 시작 시각이므로)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_now() RETURNS timestamptz
LANGUAGE sql STABLE AS $$
    SELECT CASE
             WHEN c.mode = 'REAL' THEN now()
             WHEN c.is_paused THEN c.sim_anchor
             ELSE c.sim_anchor + (now() - c.real_anchor) * c.speed
           END
    FROM sim_clock c WHERE c.id = 1;
$$;
COMMENT ON FUNCTION app_now() IS '업무 시각 (시연 시계). 업무 칼럼(occurred_at 등)에는 now() 대신 이것을 쓴다';

-- 시연 시계 바꾸기: 모드·시각·배속. p_sim_at을 비우면 지금 시연 시각을 이어 간다
CREATE OR REPLACE FUNCTION fn_sim_set(p_mode text, p_sim_at timestamptz DEFAULT NULL,
                                      p_speed numeric DEFAULT NULL, p_paused boolean DEFAULT NULL)
RETURNS timestamptz LANGUAGE plpgsql AS $$
DECLARE
    v_now_sim timestamptz := app_now();
BEGIN
    IF p_mode NOT IN ('REAL','SIM') THEN
        RAISE EXCEPTION 'mode는 REAL 또는 SIM' USING ERRCODE = '22023';
    END IF;
    UPDATE sim_clock
       SET mode        = p_mode,
           real_anchor = now(),
           sim_anchor  = coalesce(p_sim_at, v_now_sim),
           speed       = coalesce(p_speed, speed),
           is_paused   = coalesce(p_paused, is_paused),
           updated_at  = now()
     WHERE id = 1;
    RETURN app_now();
END $$;
COMMENT ON FUNCTION fn_sim_set(text, timestamptz, numeric, boolean) IS
    '시연 시계 설정. 예: 다음 날 06:00으로 건너뛰기 = fn_sim_set(''SIM'', ''2026-09-16 06:00+09'')';

-- ---------------------------------------------------------------------
-- 업무 번호 (doc_number_seq). 월은 한국 시간 기준. 동시에 불러도 겹치지 않는다 (행 잠금)
--   번호 모양은 논리 ERD 5장 (생성기와 같음):
--   fn_next_doc_no('PO',  t)    → PO-2609-001      fn_next_doc_no('SHP', t) → SHP-2609-001
--   fn_next_doc_no('MAT', t, 2) → MAT-2609-01
--   fn_next_doc_no('MW',  t)    → MW-0901 (월 + 두 자리)   'MR' → MR-0901, 'MR-S' → MR-S-0901  (설계서 5.11)
--   카운터 칸(yymm)은 모두 연월(YYMM) — 월 + 두 자리 번호도 해가 바뀌면 따로 센다
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_next_doc_no(p_prefix text, p_at timestamptz, p_width int DEFAULT 3)
RETURNS text LANGUAGE sql AS $$
    INSERT INTO doc_number_seq AS s (prefix, yymm, last_no)
    VALUES (p_prefix, to_char(p_at AT TIME ZONE 'Asia/Seoul', 'YYMM'), 1)
    ON CONFLICT (prefix, yymm) DO UPDATE SET last_no = s.last_no + 1
    RETURNING CASE WHEN s.prefix IN ('MW','MR','MR-S')
                   THEN s.prefix || '-' || substr(s.yymm, 3, 2) || lpad(s.last_no::text, 2, '0')
                   ELSE s.prefix || '-' || s.yymm || '-' || lpad(s.last_no::text, p_width, '0') END;
$$;

-- 생성기 데이터를 넣은 뒤 카운터를 이미 있는 번호의 최대값에 맞춘다 (안 하면 시연 중 번호가 겹친다)
CREATE OR REPLACE FUNCTION fn_sync_doc_numbers() RETURNS TABLE (prefix text, yymm text, last_no int)
LANGUAGE sql AS $$
    WITH nums AS (
        SELECT 'PO'   AS p, substr(order_no, 4, 4) AS ym, substr(order_no, 9)::int AS n FROM production_order
        UNION ALL SELECT 'SHP',  substr(shipment_no, 5, 4), substr(shipment_no, 10)::int FROM shipment
        -- MW-0901 / MR-0901 / MR-S-0901: 번호에 해가 없어 만든 시각의 해(한국 시간)를 붙인다
        UNION ALL SELECT 'MW',   to_char(created_at AT TIME ZONE 'Asia/Seoul', 'YY') || substr(wo_no, 4, 2), substr(wo_no, 6)::int
                    FROM maintenance_work_order
        UNION ALL SELECT 'MR',   to_char(start_at AT TIME ZONE 'Asia/Seoul', 'YY') || substr(record_no, 4, 2), substr(record_no, 6)::int
                    FROM work_record WHERE record_type = 'FULL'
        UNION ALL SELECT 'MR-S', to_char(start_at AT TIME ZONE 'Asia/Seoul', 'YY') || substr(record_no, 6, 2), substr(record_no, 8)::int
                    FROM work_record WHERE record_type = 'SIMPLE'
        UNION ALL SELECT 'MAT',  substr(material_lot_no, 5, 4), substr(material_lot_no, 10)::int FROM raw_material_lot
    ), mx AS (
        SELECT p, ym, max(n) AS n FROM nums GROUP BY p, ym
    )
    INSERT INTO doc_number_seq AS s (prefix, yymm, last_no)
    SELECT p, ym, n FROM mx
    ON CONFLICT (prefix, yymm) DO UPDATE SET last_no = greatest(s.last_no, EXCLUDED.last_no)
    RETURNING s.prefix::text, s.yymm::text, s.last_no;
$$;
