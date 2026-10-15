-- 시험 도우미 (시험용 DB에만 만든다). t.ok / t.eq / t.throws
CREATE SCHEMA IF NOT EXISTS t;

CREATE OR REPLACE FUNCTION t.ok(cond boolean, msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF cond IS NOT TRUE THEN RAISE EXCEPTION 'FAIL: %', msg; END IF;
    RAISE NOTICE 'ok - %', msg;
END $$;

CREATE OR REPLACE FUNCTION t.eq(got anyelement, expected anyelement, msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF got IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'FAIL: % (got %, expected %)', msg, got, expected;
    END IF;
    RAISE NOTICE 'ok - % (= %)', msg, got;
END $$;

-- p_sql을 실행하면 오류가 나야 하고, 오류 글에 p_pattern이 들어 있어야 한다 (대소문자 무시)
CREATE OR REPLACE FUNCTION t.throws(p_sql text, p_pattern text, msg text) RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_err text;
BEGIN
    BEGIN
        EXECUTE p_sql;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_err = MESSAGE_TEXT;
        IF v_err ILIKE '%' || p_pattern || '%' THEN
            RAISE NOTICE 'ok - % (막힘: %)', msg, left(v_err, 90);
            RETURN;
        END IF;
        RAISE EXCEPTION 'FAIL: % — 다른 오류: %', msg, v_err;
    END;
    RAISE EXCEPTION 'FAIL: % — 오류가 나야 하는데 통과함', msg;
END $$;

-- 시연 시계 고정 (시험이 시각에 흔들리지 않게)
CREATE OR REPLACE FUNCTION t.freeze(p_at timestamptz) RETURNS void LANGUAGE sql AS $$
    SELECT fn_sim_set('SIM', p_at, 1, true);
$$;
