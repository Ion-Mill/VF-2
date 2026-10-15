-- 2026-10-07 문서 수정 반영: 총 목표·이월 (R-88), 교대 끝 확정 요청 (FR-AST-02-17), 예측·목표 미달 위험 (R-48),
-- 보고 순위 줄 묶기·세는 법 (FR-AST-COM-21), 문서 수정 알림 (FR-AST-03-07), MTTR·MTBF (R-45a)

-- ---------------------------------------------------------------------
-- 1. 이월·총 목표·교대 끝 확정 요청·예측
-- ---------------------------------------------------------------------
BEGIN;
-- 목업: 9/14 주간은 기록이 없다 → 9/14 야간 이월 0. 9/15 야간은 9/15 주간 실적(확정 전)으로 계산 → 잠정
SELECT t.eq((SELECT carry_over_qty || '/' || carry_over_is_provisional FROM v_shift_target WHERE shift_id = '2026-09-14-N'),
            '0/false', 'R-88 주간 기록이 없으면 이월 0 (잠정 아님)');
SELECT t.eq((SELECT carry_over_qty FROM shift WHERE shift_id = '2026-09-15-N'),
            greatest(0, 90 - fn_shift_actual_qty('2026-09-15-D')), 'R-88 야간 이월 = max(0, 90 − 주간 실적)');
SELECT t.ok((SELECT carry_over_is_provisional FROM v_shift_target WHERE shift_id = '2026-09-15-N'),
            '주간 교대 보고서 확정 전 → 이월은 잠정');
SELECT t.throws($$UPDATE shift SET carry_over_qty = 3 WHERE shift_id = '2026-09-15-D'$$, 'ck_shift_carry_over_day',
                'R-88 주간 이월은 늘 0');

INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, supervisor_user_id) VALUES
  ('2026-09-16-D', '2026-09-16', 'DAY',   '2026-09-16 08:00+09', '2026-09-16 17:00+09', 480, 90, 'U10'),
  ('2026-09-16-N', '2026-09-16', 'NIGHT', '2026-09-16 20:00+09', '2026-09-17 05:00+09', 480, 90, 'U11');
INSERT INTO work_day VALUES ('2026-09-17', true, 180);
-- 9/16 주간 OP-50: 08:30~10:30 28개, 11:00~11:50 12개(1개 재작업), 12:30~16:30 47개(+불량 1) → 실적 87
INSERT INTO operation_report (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, end_at, pq, gq, rq, sq) VALUES
  ('LOT-2609-038-1', 'OP-50', 'CMM-01', 'U06', '2026-09-16-D', '2026-09-16 08:30+09', '2026-09-16 10:30+09', 28, 28, 0, 0),
  ('LOT-2609-040-1', 'OP-50', 'CMM-01', 'U06', '2026-09-16-D', '2026-09-16 11:00+09', '2026-09-16 11:50+09', 12, 11, 1, 0),
  ('LOT-2609-041-1', 'OP-50', 'CMM-01', 'U06', '2026-09-16-D', '2026-09-16 12:30+09', '2026-09-16 16:30+09', 48, 47, 0, 1);

-- DOC-07 8장 예: 4시간(240분) 뒤 실적 40개, 최근 1시간 12개(0.2개/분) → 예측 88개, 2개 부족, 위험 아님
SELECT t.freeze('2026-09-16 12:00+09');
SELECT t.eq((SELECT actual_qty || '/' || elapsed_min || '/' || forecast_qty || '/' || shortfall_qty || '/' || is_target_risk
               FROM v_shift_progress WHERE shift_id = '2026-09-16-D'), '40/240.0/88/2/false',
            'R-48 예측 = 40 + 0.2 × 240 = 88 → 2개 부족, 81개 이상이라 위험 아님');
-- 휴식 12:00~13:00 (팀 결정 2026-10-08): 13:00에도 지난 계획 시간 240분, 최근 계획 60분 = 11:00~12:00 → 예측 그대로 88
SELECT t.freeze('2026-09-16 13:00+09');
SELECT t.eq((SELECT elapsed_min || '/' || last_hour_qty || '/' || forecast_qty FROM v_shift_progress WHERE shift_id = '2026-09-16-D'),
            '240.0/12/88', '휴식 1시간은 지난 계획 시간·최근 1시간 속도에서 뺀다');
SELECT t.eq((SELECT to_char(break_start_at AT TIME ZONE 'Asia/Seoul', 'MM-DD HH24:MI') FROM v_shift_progress
              WHERE shift_id = '2026-09-16-N'), '09-17 00:00', '야간 휴식 00:00~01:00');
SELECT t.freeze('2026-09-16 12:00+09');
SELECT fn_run_time_rules(10);
SELECT t.ok(NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TARGET_RISK' AND shift_id = '2026-09-16-D'),
            '예측 88 ≥ 90 × 90% → 목표 미달 알림 없음');
SELECT t.eq((SELECT sum(qty)::int || '/' || max(cum_qty) FROM (
                SELECT h.hour_start, coalesce(sum(o.gq + o.rq), 0) AS qty,
                       sum(coalesce(sum(o.gq + o.rq), 0)) OVER (ORDER BY h.hour_start) AS cum_qty
                  FROM generate_series('2026-09-16 08:00+09'::timestamptz, '2026-09-16 12:00+09', interval '1 hour') h(hour_start)
                  LEFT JOIN operation_report o ON o.shift_id = '2026-09-16-D' AND o.process_code = 'OP-50'
                        AND o.end_at > h.hour_start AND o.end_at <= h.hour_start + interval '1 hour' AND o.end_at <= app_now()
                 GROUP BY h.hour_start) x), '40/40', '시간대별 실적 누계 = 지금 실적 (그래프 재료)');

-- 17:00 주간 끝: 교대 보고서 초안 + 그 교대 반장에게 확정 요청 + 야간 이월 3 (잠정)
SELECT t.freeze('2026-09-16 17:00+09');
SELECT t.eq(fn_create_shift_report_draft('2026-09-16-D'), 'CREATED', '주간 교대 보고서 초안');
SELECT t.eq((SELECT target_qty || '/' || actual_qty || '/' || defect_qty FROM shift_report WHERE shift_id = '2026-09-16-D'), '90/87/1',
            '주간 보고서 생산 칸: 총 목표 90 (주간 이월 0) / 실적 87 / 불량 1');
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'SHIFT_REPORT_PENDING' AND n.shift_id = '2026-09-16-D'), 'U10',
            'FR-AST-02-17 교대 끝에 그 교대 반장에게 확정 요청');
SELECT t.eq((SELECT carry_over_qty || '/' || total_target_qty || '/' || carry_over_is_provisional FROM v_shift_target
              WHERE shift_id = '2026-09-16-N'), '3/93/true', 'R-88 주간 87 → 야간 이월 3, 총 목표 93 (확정 전이라 잠정)');
SELECT t.ok((SELECT handover_text LIKE '전체 %건 (안전 % · 긴급 % · 생산 % · 주의 % · 참고 %)%' AND handover_text LIKE '%[2 생산 위험] %'
              FROM shift_report WHERE shift_id = '2026-09-16-D'), '인계 사항 = 머리 + 순위별 칸');
-- 반장이 확정 → 확정 요청 자동 처리, 이월 잠정이 풀림
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U10', confirmed_at = app_now() WHERE shift_id = '2026-09-16-D';
SELECT t.ok((SELECT is_processed AND process_kind = 'AUTO' FROM notification
              WHERE rule_code = 'SHIFT_REPORT_PENDING' AND shift_id = '2026-09-16-D'), '확정하면 확정 요청 자동 처리');
SELECT t.eq((SELECT carry_over_qty || '/' || carry_over_is_provisional FROM v_shift_target WHERE shift_id = '2026-09-16-N'),
            '3/false', '주간 확정 → 이월 다시 계산, 잠정 아님');

-- 야간 21:30 (시작 90분 뒤) 실적 0 → 예측 0 < 93 × 90% = 83.7 → 목표 미달 위험 1번
SELECT t.freeze('2026-09-16 21:30+09');
SELECT fn_run_time_rules(10);
SELECT t.ok((SELECT message LIKE '%총 목표 93%' FROM notification WHERE rule_code = 'TARGET_RISK' AND shift_id = '2026-09-16-N'),
            'FR-AST-02-04 목표 미달 위험은 총 목표(90 + 이월 3) 기준');
SELECT fn_run_time_rules(10);
SELECT t.eq((SELECT count(*)::int FROM notification WHERE rule_code = 'TARGET_RISK' AND shift_id = '2026-09-16-N'), 1,
            '목표 미달 위험은 교대마다 1번');

-- 05:00 야간 끝: 야간 보고서 목표 = 총 목표 93, 확정 요청은 야간 반장
SELECT t.freeze('2026-09-17 05:00+09');
SELECT fn_create_shift_report_draft('2026-09-16-N');
SELECT t.eq((SELECT target_qty FROM shift_report WHERE shift_id = '2026-09-16-N'), 93, 'FR-PRD-02-02 야간 보고서 목표 = 90 + 이월 3');
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'SHIFT_REPORT_PENDING' AND n.shift_id = '2026-09-16-N'), 'U11', '야간 확정 요청 → 야간 반장');

-- 06:00 일일 보고서: 하루 목표 180 고정 (이월을 더하지 않음), 확정 요청을 또 보내지 않음
SELECT t.freeze('2026-09-17 06:00+09');
SELECT t.eq(fn_create_daily_report_draft('2026-09-16'), 1, '야간 보고서 확정 전 → 잠정 1개');
SELECT t.eq((SELECT target_qty || '/' || actual_qty FROM daily_report WHERE work_date = '2026-09-16'), '180/87',
            'R-88 하루 목표 180 고정 (총 목표 합 183이 아님)');
SELECT t.eq((SELECT count(*)::int FROM notification WHERE rule_code = 'SHIFT_REPORT_PENDING' AND shift_id LIKE '2026-09-16-%'), 2,
            '일일 보고서 초안은 확정 요청을 다시 보내지 않음 (교대마다 1건)');

-- 확정된 보고서를 사유와 함께 고치면 관리자에게 문서 수정 알림 (FR-AST-03-07)
SELECT fn_save_revision('SHIFT_REPORT', '2026-09-16-D', 'HUMAN', 'U10', '특이 사항 오타', 'REVISED', '{}'::jsonb);
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'DOC_REVISED'), 'U12', '보고서 수정 → 관리자');
ROLLBACK;

-- 주간 실적이 목표 이상이면 이월 0
BEGIN;
INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, supervisor_user_id) VALUES
  ('2026-09-16-D', '2026-09-16', 'DAY',   '2026-09-16 08:00+09', '2026-09-16 17:00+09', 480, 90, 'U10'),
  ('2026-09-16-N', '2026-09-16', 'NIGHT', '2026-09-16 20:00+09', '2026-09-17 05:00+09', 480, 90, 'U11');
INSERT INTO operation_report (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, end_at, pq, gq, rq, sq) VALUES
  ('LOT-2609-038-1', 'OP-50', 'CMM-01', 'U06', '2026-09-16-D', '2026-09-16 08:30+09', '2026-09-16 16:30+09', 95, 95, 0, 0);
SELECT t.eq(fn_refresh_carry_over('2026-09-16'), 0, 'R-88 주간 95 ≥ 90 → 이월 0');
SELECT t.eq(fn_refresh_carry_over('2026-09-17'), NULL::int, '야간 교대가 없는 날은 NULL');
ROLLBACK;

-- ---------------------------------------------------------------------
-- 2. 보고 순위 줄 (FR-AST-COM-21): 같은 설비·같은 원인 한 줄 = 1건, 0-1은 주의에 셈, 빈 순위 "-"
-- ---------------------------------------------------------------------
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
-- VF2-01은 992 정지로 DOWN + 정지 알람 알림 → 한 줄 (긴급)
SELECT fn_raise_notification('ALARM_STOP', 'VF2-01 알람 992', '{"alarm_event_id": 3, "equipment_id": "VF2-01"}', '2026-09-15 10:58+09');
SELECT t.eq((SELECT report_rank || '/' || member_count FROM v_report_lines WHERE line_key = 'VF2-01|992'), 'R1/2',
            '지금 DOWN + 정지 알람 알림 = 긴급 한 줄 (2건 묶음)');
-- VF2-02 2075 세 번 → 주의 알람 3 + 반복 알람 1단계 = 한 줄
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:00+09');
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:10+09');
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:20+09');
SELECT t.eq((SELECT rule_code || '/' || member_count || '/' || count_bucket FROM v_report_lines WHERE line_key = 'VF2-02|2075'),
            'REPEAT_ALARM/4/CAUTION', '같은 설비·같은 알람은 한 줄 (반복 알람 1단계가 줄 머리)');
-- 24시간 넘게 처리 안 된 주의 알림 → 0-1, 건수는 "주의"
SELECT fn_raise_notification('ALARM_WARN', 'VF2-01 알람 108', '{"alarm_event_id": 1, "equipment_id": "VF2-01"}', '2026-09-14 12:00+09');
SELECT t.eq((SELECT report_rank || '/' || count_bucket FROM v_report_lines WHERE line_key = 'VF2-01|108'), 'R0_1/CAUTION',
            '0-1 오래 방치는 주의에 센다');
SELECT t.eq((SELECT count(*)::int FROM v_report_lines), (SELECT count(DISTINCT coalesce(group_key, item_kind || ':' ||
                coalesce(notification_id::text, equipment_id, lot_no)))::int FROM v_report_items), '전체 N = 묶은 뒤 줄 수');
SELECT t.ok(fn_report_items_text() LIKE format('전체 %s건 (안전 %s · %%', (SELECT count(*) FROM v_report_lines),
                                               (SELECT count(*) FROM v_report_lines WHERE count_bucket = 'SAFETY')),
            '머리 N = 줄 수, 안전 = 순위 0만');
SELECT t.ok(fn_report_items_text() LIKE '%[0 안전] ' || E'\n' || '- 잠금·표지 중: VF2-01%', '순위 0: 잠금·표지 중인 VF2-01이 맨 위');
SELECT t.ok(fn_report_items_text() LIKE '%[2 생산 위험] -%', '빈 순위는 "-"');
SELECT t.ok(fn_report_items_text() LIKE '%(같은 원인 4건 묶음)%', '묶인 줄 표시');
ROLLBACK;

-- 순위 0이 비면 "잠금·표지 중인 설비 없음" (안전 확인 문장 그대로)
BEGIN;
UPDATE work_record_check SET is_checked = true, checked_by = 'U07', checked_at = '2026-09-15 12:30+09'
 WHERE record_no = 'MR-0901' AND loto_step_code IN ('7.1','7.2','7.3');
SELECT t.ok(fn_report_items_text() LIKE '%[0 안전] 잠금·표지 중인 설비 없음%', '빈 순위 0 = "잠금·표지 중인 설비 없음"');
ROLLBACK;

-- ---------------------------------------------------------------------
-- 3. 문서 수정 알림 받는 사람 (FR-AST-03-07), MTTR·MTBF (R-45a)
-- ---------------------------------------------------------------------
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
-- 승인된 작업지시서를 고치면 담당 보전원에게 (고친 사람 본인은 빼고)
SELECT fn_save_revision('WORK_ORDER', 'MW-0901', 'HUMAN', 'U10', '작업 순서 보완', 'IN_PROGRESS', '{}'::jsonb);
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'DOC_REVISED'), 'U07', '작업지시서 수정 → 담당 보전원');
SELECT fn_save_revision('WORK_ORDER', 'MW-0901', 'HUMAN', 'U07', '부품 수량 고침', 'IN_PROGRESS', '{}'::jsonb);
SELECT t.eq((SELECT count(*)::int FROM notification WHERE rule_code = 'DOC_REVISED'), 1, '담당 보전원이 직접 고치면 알림 없음');
-- 확정 전 문서를 고치는 것은 수정 알림 대상이 아님
SELECT fn_save_revision('WORK_RECORD', 'MR-0901', 'HUMAN', 'U07', NULL, 'EDITING', '{}'::jsonb);
SELECT t.eq((SELECT count(*)::int FROM notification WHERE rule_code = 'DOC_REVISED'), 1, '확정 전 수정은 알림 없음');

-- MTTR·MTBF (30일): VF2-01 정지 등급 DOWN 2번 (10:55~10:57 2분, 10:58~ 지금 13:00까지 122분) → MTTR 62분
SELECT t.eq((SELECT failure_count || '/' || mttr_min || '/' || is_mttr_warn FROM v_equipment_reliability_30d
              WHERE equipment_id = 'VF2-01'), '2/62.0/false', 'R-45a MTTR = DOWN 시간 합 ÷ 고장 횟수');
SELECT t.ok((SELECT mttr_min IS NULL AND mtbf_hours IS NULL FROM v_equipment_reliability_30d WHERE equipment_id = 'VF2-02'),
            '고장 0건이면 MTTR·MTBF 없음 ("—")');
ROLLBACK;

-- ---------------------------------------------------------------------
-- 4. 같은 원인 한 줄 — 알람 ↔ 관련 재고 품목 (alarm_related_item, DOC-07 §10.5 예)
--    2075 반복 알람 + 축 윤활유 점검 기한 넘김 + 축 윤활유 재고 부족 → 한 줄
-- ---------------------------------------------------------------------
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
SELECT t.eq((SELECT item_no FROM alarm_related_item WHERE alarm_code = '2075'), 'CS-WLUB', '목업: 2075 ↔ 축 윤활유');
SELECT t.eq(fn_seed_alarm_related_items(), 0, '여러 번 불러도 같은 줄을 또 넣지 않음');
SELECT fn_raise_notification('PM_OVERDUE', 'VF2-02 예방 정비 기한 넘김: 윤활유 저장소', '{"pm_task_id": "PM-VF2-02-2.3-01", "equipment_id": "VF2-02"}',
                             '2026-09-15 12:30+09');
SELECT fn_raise_notification('STOCK_LOW', '축 윤활유 재고 부족', '{"item_no": "CS-WLUB"}', '2026-09-15 12:40+09');
-- 알람이 없을 때: 정비 기한 + 재고 부족은 같은 소모품으로 한 줄
SELECT t.eq((SELECT member_count FROM v_report_lines WHERE line_key = 'VF2-02|item:CS-WLUB'), 2,
            '정비 기한 넘김 + 같은 소모품 재고 부족 = 한 줄');
-- 2075가 반복되면 셋이 한 줄 (가장 높은 순위 = 반복 알람 1단계가 줄 머리)
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:00+09');
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:10+09');
SELECT fn_ingest_alarm('VF2-02', '2075', '2026-09-15 12:20+09');
SELECT t.eq((SELECT rule_code || '/' || member_count FROM v_report_lines WHERE line_key = 'VF2-02|2075'), 'REPEAT_ALARM/6',
            '알람 3 + 반복 알람 + 정비 기한 넘김 + 재고 부족 = 한 줄 (1건)');
SELECT t.ok(NOT EXISTS (SELECT 1 FROM v_report_lines WHERE line_key = 'VF2-02|item:CS-WLUB'), '따로 남은 줄 없음');
SELECT t.eq((SELECT count(*)::int FROM v_report_lines WHERE rule_code IN ('PM_OVERDUE','STOCK_LOW')), 0,
            '정비·재고 줄은 알람 줄에 묶임');
-- 다른 설비(VF2-01)의 같은 소모품 정비는 VF2-02 알람 줄에 묶이지 않음 (같은 설비만)
INSERT INTO pm_task (pm_task_id, equipment_id, doc04_section, area, item_name, cycle_code, lockout_level, default_role,
                     default_item_no, on_calendar, source_tag)
VALUES ('PM-VF2-01-2.3-01', 'VF2-01', '2.3', '축 윤활', '윤활유 저장소 양 점검·보충 (시험)', 'MONTHLY', 'TWO_POINT', 'MNT', 'CS-WLUB', true, 'REAL');
SELECT fn_raise_notification('PM_OVERDUE', 'VF2-01 예방 정비 기한 넘김', '{"pm_task_id": "PM-VF2-01-2.3-01", "equipment_id": "VF2-01"}',
                             '2026-09-15 12:50+09');
SELECT t.eq((SELECT member_count FROM v_report_lines WHERE line_key = 'VF2-01|item:CS-WLUB'), 1, '다른 설비 정비는 따로');
ROLLBACK;

-- ---------------------------------------------------------------------
-- 5. 일일 보고서 (계속 만든다 — 2026-10-08): 교대 보고서가 확정되면 확정 전 일일 보고서 칸을 다시 채우고 이력 1줄,
--    잠정 칸이 있으면 MGR 확정 불가 (R-72)
-- ---------------------------------------------------------------------
BEGIN;
SELECT t.freeze('2026-09-16 06:00+09');
SELECT t.eq(fn_create_daily_report_draft('2026-09-15'), 2, '9/15 주간·야간 모두 확정 전 → 잠정 2');
SELECT t.ok((SELECT issues_summary LIKE '%(잠정: 확정 안 된 교대 2개)' FROM daily_report WHERE work_date = '2026-09-15'), '잠정 2개 표시');
SELECT t.eq((SELECT count(*)::int FROM daily_report d
              WHERE d.work_date = '2026-09-15' AND NOT EXISTS (SELECT 1 FROM shift s LEFT JOIN shift_report r USING (shift_id)
                    WHERE s.work_date = d.work_date AND coalesce(r.status, 'AI_DRAFT') NOT IN ('CONFIRMED','REVISED'))), 0,
            '잠정 칸이 있으면 확정 조건에 걸림');
UPDATE shift_report SET actual_qty = 86 WHERE shift_id = '2026-09-15-N';
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U11', confirmed_at = app_now() WHERE shift_id = '2026-09-15-N';
SELECT t.ok((SELECT issues_summary LIKE '%(잠정: 확정 안 된 교대 1개)' AND issues_summary NOT LIKE '%교대 2개%'
               FROM daily_report WHERE work_date = '2026-09-15'), '야간 확정 → 잠정 1개로 다시 채움');
SELECT t.eq((SELECT version_no || '/' || author_user_id FROM document_revision
              WHERE doc_type = 'DAILY_REPORT' AND doc_key = '2026-09-15' ORDER BY version_no DESC LIMIT 1), '1/U11',
            '수정 이력 1줄 (작성자 = 확정한 반장)');
SELECT t.eq((SELECT actual_qty FROM daily_report WHERE work_date = '2026-09-15'),
            (SELECT sum(actual_qty)::int FROM shift_report r JOIN shift s USING (shift_id) WHERE s.work_date = '2026-09-15'),
            'R-12 하루 실적 = 교대 보고서 2개 실적 합');
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U10', confirmed_at = app_now() WHERE shift_id = '2026-09-15-D';
SELECT t.ok((SELECT issues_summary NOT LIKE '%잠정%' FROM daily_report WHERE work_date = '2026-09-15'), '둘 다 확정 → 잠정 없음');
UPDATE daily_report SET status = 'CONFIRMED', confirmed_by = 'U12', confirmed_at = app_now() WHERE work_date = '2026-09-15';
SELECT t.eq((SELECT status FROM daily_report WHERE work_date = '2026-09-15'), 'CONFIRMED', '잠정이 없으면 MGR 확정');
ROLLBACK;
