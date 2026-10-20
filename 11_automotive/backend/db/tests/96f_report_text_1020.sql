-- 2026-10-20 요구사항 대조 중 (구현_중_수정사항 1020 36장): 인계 사항·오늘의 문제 글을 생성기·화면 모양으로,
-- 인계 사항에 진행 중 작업지시서 (FR-PRD-02-08)
BEGIN;
SELECT t.freeze('2026-09-15 12:00+09');

-- ---------- 인계 사항: "0 안전: … / 0-1 오래 방치: … / 1 긴급: … / 2 생산 위험: … / 3 주의: … / 4 참고: …"
SELECT t.ok(fn_report_items_text() ~ '^0 안전: .* / 0-1 오래 방치: .* / 1 긴급: .* / 2 생산 위험: .* / 3 주의: .* / 4 참고: .*$',
            '여섯 칸이 순위 순으로 ( / 로 나눔)');
INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at) VALUES ('VF2-01', '994', 'STOP', '2026-09-15 10:50+09')
RETURNING alarm_event_id AS a994 \gset
INSERT INTO maintenance_work_order (wo_no, alarm_event_id, equipment_id, title, symptom, status, created_at, safety_block_doc_rev,
                                    has_high_voltage_notice, current_version)
VALUES ('MW-9960', :a994, 'VF2-01', '(시험) 진행 중', '(시험)', 'AI_DRAFT', '2026-09-15 11:00+09', 'DOC-05 Rev.1', false, 0);
SELECT t.ok(split_part(split_part(fn_report_items_text(), ' / 3 주의: ', 2), ' / 4 참고: ', 1) LIKE '%진행 중 작업지시서 MW-0901 (VF2-01); 진행 중 작업지시서 MW-9960 (VF2-01)%',
            '진행 중 작업지시서는 주의 칸 (FR-PRD-02-08)');
SELECT t.eq((SELECT count(*)::int FROM v_report_lines WHERE item_kind = 'WO' AND title LIKE '%MW-9960%'), 1, '작업지시서마다 한 줄 (같은 설비 MW-0901과 따로)');

-- ---------- 오늘의 문제: "전체 N건 (안전 a · 긴급 b · 생산 c · 주의 d · 참고 e): 1) [긴급] … / 2) …", 번호 = 1부터, N = 항목 수
SELECT fn_daily_issues_text('2026-09-14') AS iss \gset
SELECT t.ok(:'iss' ~ '^전체 [0-9]+건( \(안전 [0-9]+ · 긴급 [0-9]+ · 생산 [0-9]+ · 주의 [0-9]+ · 참고 [0-9]+\): 1\) \[(안전|긴급|생산|주의|참고)\] .*)?$',
            '머리 + 번호 붙은 항목');
SELECT t.eq(CASE WHEN :'iss' = '전체 0건' THEN 0 ELSE
              (SELECT count(*)::int FROM unnest(string_to_array(substr(:'iss', strpos(:'iss', '): ') + 3), ' / ')) x) END,
            substring(:'iss' FROM '^전체 ([0-9]+)건')::int, '머리의 N = 항목 수');
SELECT t.ok(fn_daily_issues_text('2027-01-01') NOT SIMILAR TO '%\[(긴급|생산)\]%', '교대가 없는 날 = 그날 생긴 일 없음 (지금 남은 일만)');
ROLLBACK;
