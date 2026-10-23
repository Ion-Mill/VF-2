-- 품질: 검사 결과·CMM 자동 기록·Cpk (QLT-01)

-- name: results
SELECT result_id, lot_no, part_seq, item_seq, item_name, spec_text, insp_kind, position, measured_value, judgement, cmm_judgement,
       is_judgement_mismatch, instrument_id, inspector_id, measured_at, room_temp_c, part_temp_c, is_temp_flag, temp_comp_used,
       input_method, cmm_import_id, check_status, checked_by, checked_at, remeasure_seq, use_for_judgement, entered_by,
       machined_equipment_id
  FROM v_inspection_result WHERE lot_no = :lot_no ORDER BY part_seq, item_seq, position, remeasure_seq;

-- name: instruction_issue
SELECT fn_issue_cmm_instruction(:lot_no, :part_seq, coalesce(CAST(:first AS boolean), false)) AS instruction_id;

-- name: instruction_get
SELECT instruction_id, lot_no, part_seq, insp_kind, status FROM cmm_instruction WHERE instruction_id = :instruction_id;

-- name: instruction_start
UPDATE cmm_instruction SET status = 'STARTED', started_at = app_now(), started_by = :actor
 WHERE instruction_id = :instruction_id AND status = 'ISSUED'
RETURNING instruction_id, lot_no, part_seq, insp_kind, enhance_reason;

-- name: instructions_open
SELECT instruction_id, lot_no, part_seq, insp_kind, enhance_reason, issued_at, started_at, started_by, status
  FROM cmm_instruction WHERE status IN ('ISSUED','STARTED') ORDER BY issued_at;

-- name: imports
SELECT cmm_import_id, file_name, received_at, status, error_kind, error_text, original_file_ref, instrument_id, lot_no, part_seq,
       insp_kind, program_name_rev, measure_start_at, measure_end_at, format_version, sample_no_raw, instruction_id,
       (SELECT count(*) FROM inspection_result r WHERE r.cmm_import_id = c.cmm_import_id)::int AS result_count
  FROM cmm_import c
 WHERE (CAST(:problem_only AS boolean) IS NOT TRUE OR status <> 'SUCCESS')
 ORDER BY received_at DESC LIMIT CAST(:limit AS int);

-- name: import_exists
SELECT count(*)::int AS n FROM cmm_import WHERE file_name = :file_name OR file_name LIKE :file_name || '#%';

-- name: import_cmm
SELECT fn_import_cmm(:file_name, :file_ref, CAST(:header AS jsonb), CAST(:rows AS jsonb)) AS cmm_import_id;

-- name: import_failure
SELECT fn_record_cmm_failure(:file_name, :file_ref, :error_kind, :error_text, CAST(:header AS jsonb)) AS cmm_import_id;

-- name: check_measurement
SELECT fn_check_measurement(:result_id, :actor, :use_for_judgement);

-- 게이지(6번)·외관(7번) 태블릿 버튼 (FR-QLT-01-20)
-- name: tablet_result
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, judgement, instrument_id, inspector_id,
                               measured_at, input_method, check_status, use_for_judgement)
SELECT l.lot_no, :part_seq, o.product_code, :item_seq, :insp_kind, NULL, :judgement, 'CMM-01', :actor, app_now(), 'TABLET', 'NORMAL', true
  FROM production_lot l JOIN production_order o USING (order_no) WHERE l.lot_no = :lot_no
RETURNING result_id;

-- Cpk (FR-QLT-01-08): 개별값 관리도(I-MR) 방식 σ = 평균 이동 범위 ÷ 1.128. 50개 미만이면 "계산 중"
-- 설비별(가공 설비)은 참고용 — 판정·전수 전환은 전체 설비 값 (가공 설비 = 05 결정기록 P-11)
-- 표본 = 지금 시각까지 **최근 측정값 50개** (DOC-06 §5.1 ④, 관리도 점과 같은 범위 — 2026-10-23, 전에는 전체 값). DB fn_item_cpk와 같은 식
-- name: cpk
WITH recent AS (
    SELECT r.measured_value AS x, r.measured_at, r.result_id
      FROM v_inspection_result r
     WHERE r.product_code = :product_code AND r.item_seq = :item_seq AND r.use_for_judgement AND r.measured_value IS NOT NULL
       AND r.measured_at <= app_now()
       AND (CAST(:equipment_id AS text) IS NULL OR r.machined_equipment_id = CAST(:equipment_id AS text))
     ORDER BY r.measured_at DESC, r.result_id DESC LIMIT 50
), v AS (
    SELECT x, measured_at, result_id, x - lag(x) OVER (ORDER BY measured_at, result_id) AS mr FROM recent
)
SELECT i.item_seq, i.item_name, i.lsl, i.usl, i.cpk_min, i.is_full_check_by_cpk, count(v.x)::int AS n, avg(v.x) AS mean,
       avg(abs(v.mr)) / 1.128 AS sigma,
       CASE WHEN count(v.x) < 50 THEN NULL
            ELSE least(coalesce((i.usl - avg(v.x)), 'Infinity'::numeric), coalesce((avg(v.x) - i.lsl), 'Infinity'::numeric))
                 / nullif(3 * avg(abs(v.mr)) / 1.128, 0) END AS cpk,
       count(v.x) < 50 AS is_calculating
  FROM inspection_item i LEFT JOIN v ON true
 WHERE i.product_code = :product_code AND i.item_seq = :item_seq
 GROUP BY i.item_seq, i.item_name, i.lsl, i.usl, i.cpk_min, i.is_full_check_by_cpk;

-- name: defects
SELECT d.defect_code, c.defect_name, c.grade, sum(d.qty)::int AS qty, count(DISTINCT d.lot_no)::int AS lots
  FROM defect_record d JOIN defect_code c USING (defect_code)
 WHERE d.found_at >= CAST(:from AS timestamptz) AND d.found_at < CAST(:to AS timestamptz)
 GROUP BY d.defect_code, c.defect_name, c.grade ORDER BY qty DESC;

-- name: import_get
SELECT cmm_import_id, file_name, status, error_kind, error_text, lot_no, part_seq, insp_kind, instruction_id,
       (SELECT count(*) FROM inspection_result r WHERE r.cmm_import_id = c.cmm_import_id)::int AS result_count
  FROM cmm_import c WHERE cmm_import_id = :cmm_import_id;

-- 파일을 다른 칸(오류)으로 옮긴 뒤 보관 위치 고치기
-- name: import_set_ref
UPDATE cmm_import SET original_file_ref = :file_ref WHERE cmm_import_id = CAST(:cmm_import_id AS bigint);

-- 3차원 측정기 값 수동 입력 (QLT-02, FR-QLT-01-19, R-81): "수동" 표시, 확인 필요에서 시작, 판정에는 반장이 고른 뒤에만.
-- 플랫폼 판정 = 기준(lsl·usl) 안이면 합격. 같은 부품·항목이 이미 있으면 재측정 순번을 올린다
-- name: manual_result
INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value, judgement,
                               instrument_id, inspector_id, measured_at, input_method, check_status, use_for_judgement,
                               entered_by, remeasure_seq)
SELECT l.lot_no, CAST(:part_seq AS int), o.product_code, CAST(:item_seq AS smallint), CAST(:insp_kind AS varchar), NULL,
       CAST(:measured_value AS numeric),
       CASE WHEN (i.lsl IS NULL OR CAST(:measured_value AS numeric) >= i.lsl)
             AND (i.usl IS NULL OR CAST(:measured_value AS numeric) <= i.usl) THEN 'PASS' ELSE 'FAIL' END,
       'CMM-01', :inspector, app_now(), 'MANUAL', 'NEEDS_CHECK', false, :actor,
       1 + coalesce((SELECT max(x.remeasure_seq) FROM inspection_result x
                      WHERE x.lot_no = l.lot_no AND x.part_seq = CAST(:part_seq AS int) AND x.item_seq = CAST(:item_seq AS smallint)
                        AND x.insp_kind = CAST(:insp_kind AS varchar) AND x.position IS NULL), 0)
  FROM production_lot l JOIN production_order o USING (order_no)
  JOIN inspection_item i ON i.product_code = o.product_code AND i.item_seq = CAST(:item_seq AS smallint)
 WHERE l.lot_no = :lot_no
RETURNING result_id;

-- 관리도·Cpk를 볼 항목 (기준값이 있는 항목). 제품을 비우면 사용 중인 첫 제품
-- name: measurable_items
SELECT i.product_code, i.item_seq, i.item_name, i.lsl, i.usl
  FROM inspection_item i
 WHERE i.product_code = coalesce(CAST(:product_code AS text),
                                 (SELECT p.product_code FROM product p WHERE p.is_active ORDER BY p.product_code LIMIT 1))
   AND (i.lsl IS NOT NULL OR i.usl IS NOT NULL)
 ORDER BY i.item_seq;

-- 관리도 점 (I-MR, FR-QLT-01-10): 기간 안 판정에 쓰는 측정값과 이동 범위. 최근 :limit개
-- name: chart_points
SELECT * FROM (
    SELECT r.result_id, r.lot_no, r.part_seq, r.measured_at, r.measured_value AS x,
           abs(r.measured_value - lag(r.measured_value) OVER (ORDER BY r.measured_at, r.result_id)) AS mr
      FROM inspection_result r
     WHERE r.product_code = :product_code AND r.item_seq = CAST(:item_seq AS smallint) AND r.use_for_judgement
       AND r.measured_value IS NOT NULL
       AND r.measured_at >= CAST(:from AS timestamptz) AND r.measured_at < CAST(:to AS timestamptz)
     ORDER BY r.measured_at DESC, r.result_id DESC LIMIT CAST(:limit AS int)) z
 ORDER BY z.measured_at, z.result_id;

-- 전수 측정 → 보통(발췌) 승인 (DOC-06 §5.2 — 2026-10-20). MGR, Cpk가 기준 이상일 때만 (DB가 확인)
-- name: resume_sampling
SELECT fn_resume_sampling(:product_code, :item_seq, :actor) AS cpk;
