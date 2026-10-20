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
