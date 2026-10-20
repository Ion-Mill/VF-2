-- =====================================================================
-- 40_cmm_import.sql — OP-50 측정 결과 파일 자동 기록 (R-78~R-82, DOC-06 Rev.2 §3.6)
-- 파일 읽기(CSV 해석)는 서버(app/domain/cmm_csv.py)가 하고, 해석된 값을 이 함수에 넘긴다.
--   양식 오류(열 빠짐·숫자 아님)로 해석 못 하면 → fn_record_cmm_failure (기록 안 함, 알림)
--   해석되면 → fn_import_cmm (지시와 대조, 판정 다시 계산, 재측정 보관)
-- =====================================================================

CREATE OR REPLACE FUNCTION fn_record_cmm_failure(p_file_name text, p_file_ref text, p_error_kind text,
    p_error_text text, p_header jsonb DEFAULT '{}'::jsonb, p_received_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_id bigint; v_at timestamptz := coalesce(p_received_at, app_now());
BEGIN
    INSERT INTO cmm_import (file_name, received_at, status, error_kind, error_text, original_file_ref,
                            format_version, sample_no_raw, raw_header)
    VALUES (p_file_name, v_at, 'FAILED', p_error_kind, p_error_text, p_file_ref,
            p_header->>'format', p_header->>'sample_no', p_header)
    RETURNING cmm_import_id INTO v_id;
    PERFORM fn_raise_notification('CMM_FILE_ERROR', format('측정 결과 파일을 읽지 못함: %s (%s)', p_file_name, p_error_text),
                                  jsonb_build_object('cmm_import_id', v_id), v_at);
    RETURN v_id;
END $$;

-- p_header (app/domain/cmm_csv.py가 만든 값):
--   {format, cmm_id, program, lot_no, part_seq, sample_no, insp_kind, operator, measured_at,
--    measure_start_at, measure_end_at, room_temp_c, part_temp_c, machine_temp_c, temp_comp, ...그 밖 머리 칸}
-- p_rows: [{item_seq, position, actual, cmm_judgement}]  (position: 빈칸·없음 = 표준, TOP/MID/BOTTOM)
-- 반환: cmm_import_id
CREATE OR REPLACE FUNCTION fn_import_cmm(p_file_name text, p_file_ref text, p_header jsonb, p_rows jsonb,
                                         p_received_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at        timestamptz := coalesce(p_received_at, app_now());
    v_lot       text := p_header->>'lot_no';
    v_part      int  := (p_header->>'part_seq')::int;
    v_kind      text := p_header->>'insp_kind';
    v_measured  timestamptz := coalesce((p_header->>'measure_end_at')::timestamptz, (p_header->>'measured_at')::timestamptz);
    v_product   text;
    v_instr     cmm_instruction%ROWTYPE;
    v_import    bigint;
    v_status    text := 'SUCCESS';
    v_err_kind  text;
    v_err_text  text;
    v_inspector text;
    v_missing   text;
    rw          jsonb;
    it          inspection_item%ROWTYPE;
    v_value     numeric;
    v_judge     text;
    v_cmm       text;
    v_pos       text;
    v_reseq     int;
    v_check     text;
    v_result    bigint;
    v_mismatch  bigint[] := '{}';
BEGIN
    SELECT o.product_code INTO v_product FROM production_lot l JOIN production_order o USING (order_no) WHERE l.lot_no = v_lot;
    IF v_product IS NULL THEN
        -- 없는 로트면 측정값을 기록할 곳이 없다 → 실패
        RETURN fn_record_cmm_failure(p_file_name, p_file_ref, 'LOT_MISMATCH',
            format('결과 파일의 로트 %s가 없음', coalesce(v_lot, '(비어 있음)')), p_header, v_at);
    END IF;

    -- R-78 측정 지시와 같아야 정상
    SELECT * INTO v_instr FROM cmm_instruction
     WHERE lot_no = v_lot AND part_seq = v_part AND insp_kind = v_kind AND status IN ('ISSUED','STARTED')
     ORDER BY issued_at DESC LIMIT 1;
    IF v_instr.instruction_id IS NULL THEN
        v_status := 'NEEDS_CHECK'; v_err_kind := 'LOT_MISMATCH';
        v_err_text := format('지시와 다름: 로트 %s 순번 %s %s에 열린 측정 지시가 없음', v_lot, v_part, v_kind);
    END IF;

    -- 측정자: 측정 시작 때 태블릿에서 확인한 사람 → 파일의 operator (사용자로 있을 때만) → 그 시각 교대의 측정 담당
    --   (OP-50 담당 OPR — 두 번째 담당 공정 포함, P-45 [제안]). 생성기 10/1 결과 파일에는 operator 칸이 없다 (2026-10-14)
    v_inspector := coalesce(v_instr.started_by,
                            (SELECT user_id FROM app_user WHERE user_id = p_header->>'operator' AND role_code = 'OPR'),
                            (SELECT u.user_id FROM app_user u JOIN shift s ON s.shift_type = u.home_shift_type
                              WHERE u.is_active AND u.role_code = 'OPR' AND 'OP-50' IN (u.home_process_code, u.home_process_code_2)
                                AND coalesce(v_measured, v_at) >= s.start_at AND coalesce(v_measured, v_at) < s.end_at + interval '3 hours'
                              ORDER BY s.start_at DESC, (u.home_process_code = 'OP-50') DESC, u.user_id LIMIT 1));
    IF v_inspector IS NULL THEN
        RETURN fn_record_cmm_failure(p_file_name, p_file_ref, 'LOT_MISMATCH',
            '측정자를 알 수 없음 (측정 시작 기록도, 파일의 operator도, 그 교대 측정 담당도 없음)', p_header, v_at);
    END IF;

    -- 불완전: 이 검사 방식에 필요한 3차원 측정기 항목 중 빠진 것 (강화 1번은 3단 위치로 와도 됨)
    SELECT string_agg(i.item_seq::text, ',' ORDER BY i.item_seq) INTO v_missing
      FROM inspection_item i
     WHERE i.product_code = v_product AND i.method = 'CMM' AND (i.in_sampling OR v_kind = 'ENHANCED')
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_rows) r
                        WHERE (r->>'item_seq')::int = i.item_seq);
    IF v_missing IS NOT NULL THEN
        v_status := 'NEEDS_CHECK'; v_err_kind := coalesce(v_err_kind, 'INCOMPLETE');
        v_err_text := concat_ws(' / ', v_err_text, '불완전: 항목 ' || v_missing || ' 없음');
    END IF;

    INSERT INTO cmm_import (file_name, received_at, status, error_kind, error_text, original_file_ref, instrument_id,
                            lot_no, part_seq, insp_kind, program_name_rev, measure_start_at, measure_end_at,
                            machine_temp_c, temp_comp_on, format_version, sample_no_raw, raw_header, instruction_id)
    VALUES (p_file_name, v_at, v_status, v_err_kind, v_err_text, p_file_ref,
            (SELECT equipment_id FROM equipment WHERE equipment_id = p_header->>'cmm_id'),
            v_lot, v_part, v_kind, p_header->>'program',
            (p_header->>'measure_start_at')::timestamptz, coalesce((p_header->>'measure_end_at')::timestamptz, v_measured),
            (p_header->>'machine_temp_c')::numeric, (p_header->>'temp_comp')::boolean,
            p_header->>'format', p_header->>'sample_no', p_header, v_instr.instruction_id)
    RETURNING cmm_import_id INTO v_import;

    FOR rw IN SELECT * FROM jsonb_array_elements(p_rows) LOOP
        SELECT * INTO it FROM inspection_item WHERE product_code = v_product AND item_seq = (rw->>'item_seq')::int;
        IF it.item_seq IS NULL OR it.method <> 'CMM' THEN
            CONTINUE;   -- 3차원 측정기 항목이 아니면 무시 (게이지·외관은 태블릿 버튼)
        END IF;
        v_value := (rw->>'actual')::numeric;
        v_cmm   := rw->>'cmm_judgement';
        v_pos   := nullif(rw->>'position', '');
        -- R-79 플랫폼이 DOC-06 §2 기준으로 다시 계산한 판정
        v_judge := CASE WHEN (it.lsl IS NULL OR v_value >= it.lsl) AND v_value <= it.usl THEN 'PASS' ELSE 'FAIL' END;
        -- R-81 같은 부품·항목·측정 위치가 다시 오면 재측정 순번을 올리고 덮어쓰지 않는다
        SELECT coalesce(max(remeasure_seq), 0) + 1 INTO v_reseq FROM inspection_result
         WHERE lot_no = v_lot AND part_seq = v_part AND item_seq = it.item_seq AND insp_kind = v_kind AND position IS NOT DISTINCT FROM v_pos;
        v_check := CASE WHEN v_status <> 'SUCCESS' OR v_cmm IS DISTINCT FROM v_judge OR v_reseq > 1
                        THEN 'NEEDS_CHECK' ELSE 'NORMAL' END;
        INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value,
            judgement, instrument_id, inspector_id, measured_at, room_temp_c, part_temp_c, temp_comp_used,
            input_method, cmm_import_id, cmm_judgement, check_status, remeasure_seq, use_for_judgement)
        VALUES (v_lot, v_part, v_product, it.item_seq, v_kind, v_pos, v_value, v_judge,
            coalesce((SELECT equipment_id FROM equipment WHERE equipment_id = p_header->>'cmm_id'), 'CMM-01'),
            v_inspector, coalesce(v_measured, v_at),
            (p_header->>'room_temp_c')::numeric, (p_header->>'part_temp_c')::numeric, (p_header->>'temp_comp')::boolean,
            'CMM_AUTO', v_import, v_cmm, v_check, v_reseq,
            -- 판정에 쓰는 값: 그 위치(표준 또는 강화 3단 TOP·MID·BOTTOM)의 첫 측정. 재측정이 오면 반장이 고른다 (R-81)
            v_reseq = 1)
        RETURNING result_id INTO v_result;
        IF v_cmm IS DISTINCT FROM v_judge THEN
            v_mismatch := v_mismatch || v_result;
        END IF;
    END LOOP;

    IF v_instr.instruction_id IS NOT NULL THEN
        UPDATE cmm_instruction SET status = 'DONE', started_at = coalesce(started_at, (p_header->>'measure_start_at')::timestamptz, v_at)
         WHERE instruction_id = v_instr.instruction_id;
        -- 결과가 왔으므로 결과 미수신 알림은 자동 처리
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'CMM_NO_RESULT' AND lot_no = v_lot AND NOT is_processed),
                                v_inspector, v_at);
    END IF;
    IF v_status <> 'SUCCESS' THEN
        PERFORM fn_raise_notification('CMM_FILE_ERROR', format('측정 결과 확인 필요: %s — %s', p_file_name, v_err_text),
                                      jsonb_build_object('cmm_import_id', v_import, 'lot_no', v_lot), v_at);
    END IF;
    IF array_length(v_mismatch, 1) > 0 THEN
        PERFORM fn_raise_notification('CMM_JUDGE_MISMATCH',
            format('CMM 판정 불일치: %s 순번 %s 항목 %s', v_lot, v_part,
                   (SELECT string_agg(item_seq::text, ',') FROM inspection_result WHERE result_id = ANY (v_mismatch))),
            jsonb_build_object('result_id', v_mismatch[1], 'lot_no', v_lot), v_at);
    END IF;
    RETURN v_import;
END $$;

-- 반장 확인 (R-81·R-79): 확인 필요 값을 확인하고, 재측정이 있으면 판정에 쓸 값을 고른다
CREATE OR REPLACE FUNCTION fn_check_measurement(p_result_id bigint, p_actor text, p_use_for_judgement boolean,
                                                p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE r inspection_result%ROWTYPE; v_at timestamptz := coalesce(p_at, app_now());
BEGIN
    SELECT * INTO r FROM inspection_result WHERE result_id = p_result_id FOR UPDATE;
    PERFORM fn_require_role(p_actor, ARRAY['SUP'], '측정값 반장 확인');
    IF p_use_for_judgement THEN
        -- 같은 부품·항목·측정 위치의 다른 값은 판정에서 뺀다 (하나만 참, R-81). 강화 검사 3단(TOP·MID·BOTTOM)은 위치마다 따로
        UPDATE inspection_result SET use_for_judgement = false
         WHERE lot_no = r.lot_no AND part_seq = r.part_seq AND item_seq = r.item_seq
           AND position IS NOT DISTINCT FROM r.position AND result_id <> p_result_id;
    END IF;
    UPDATE inspection_result SET check_status = 'CHECKED', checked_by = p_actor, checked_at = v_at,
                                 use_for_judgement = p_use_for_judgement
     WHERE result_id = p_result_id;
    PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                   WHERE rule_code = 'CMM_JUDGE_MISMATCH' AND result_id = p_result_id AND NOT is_processed),
                            p_actor, v_at);
END $$;
