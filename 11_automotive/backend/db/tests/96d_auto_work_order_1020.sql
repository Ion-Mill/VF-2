-- 2026-10-20 상 3번 (구현_중_수정사항 1020 36장): OP-30 정지 등급 알람·반복 알람 2단계 → 작업지시서 초안 자동 (FR-MNT-03-01)
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');
INSERT INTO alarm_guide_map (alarm_code, seq, doc_no, section) VALUES ('254', 1, 'DOC-03', '2.9'), ('992', 1, 'DOC-03', '2.1')
ON CONFLICT DO NOTHING;
SELECT count(*) AS n254 FROM alarm_check_step WHERE alarm_code = '254' AND step_kind IN ('OPR','MNT') \gset
SELECT count(*) AS m254 FROM alarm_check_step WHERE alarm_code = '254' AND step_kind = 'MNT' \gset

-- ① OP-30 정지 등급(254) → 초안: 제목·증상(DOC-03 첫 문장)·작업 순서(★ 작업자 줄 + 보전 줄)·담당(주간 MNT)·알림
SELECT fn_ingest_alarm('VF2-02', '254', '2026-09-15 13:00+09', 'LOT-2609-041-1') AS a1 \gset
SELECT wo_no AS wo FROM maintenance_work_order WHERE alarm_event_id = :a1 \gset
SELECT t.eq((SELECT status || '/' || title || '/' || coalesce(assignee_user_id, '-') || '/' || lot_no FROM maintenance_work_order WHERE wo_no = :'wo'),
            'AI_DRAFT/VF2-02 알람 254 (' || (SELECT btrim(regexp_replace(name_ko, '\(.*\)', '')) FROM alarm_master WHERE alarm_code = '254')
            || ') 점검/U07/LOT-2609-041-1', '정지 등급 알람 → AI비서 초안, 담당 = 그 교대(주간) 보전 담당자');
SELECT t.eq((SELECT symptom FROM maintenance_work_order WHERE wo_no = :'wo'),
            (SELECT step_text FROM alarm_check_step WHERE alarm_code = '254' AND step_kind = 'SYMPTOM'), '증상 = DOC-03 첫 문장');
SELECT t.eq((SELECT count(*) FROM work_order_step WHERE wo_no = :'wo')::int, :n254::int, '작업 순서 = ★ 작업자 줄 + 보전 줄 전체');
SELECT t.eq((SELECT string_agg(DISTINCT source_section, ',') FROM work_order_step WHERE wo_no = :'wo'), 'DOC-03 §2.9', '출처 = 그 알람의 DOC-03 절');
SELECT t.eq((SELECT string_agg(rule_code, ',' ORDER BY rule_code) FROM notification WHERE wo_no = :'wo'),
            'WO_APPROVAL_REQUEST,WO_DRAFT_READY', '초안 검토(MNT)·승인 요청(SUP) 알림');
-- 설비에 진행 중인 작업지시서가 있으면(VF2-01 MW-0901) 새로 만들지 않음
SELECT fn_ingest_alarm('VF2-01', '992', '2026-09-15 13:01+09') AS a2 \gset
SELECT t.eq((SELECT count(*) FROM maintenance_work_order WHERE alarm_event_id = :a2)::int, 0, '그 설비에 진행 중 작업지시서가 있으면 만들지 않음');
-- 다른 공정 정지 등급은 작업지시서를 만들지 않음 (지침카드 + 간이 작업기록, FR-MNT-03-01)
SELECT fn_ingest_alarm('SAW-01', '6302.00', '2026-09-15 13:02+09') AS a3 \gset
SELECT t.eq((SELECT count(*) FROM maintenance_work_order WHERE alarm_event_id = :a3)::int, 0, '다른 공정은 만들지 않음');

-- ② 반복 알람 2단계 → 같은 알람의 초안이 있으면 계기만 더하고 보전 줄을 덧붙임 (R-71 겹치면 1개)
INSERT INTO notification (rule_code, importance, raised_at, message, alarm_event_id, equipment_id, prev_stage_notification_id, repeat_stage_status)
VALUES ('REPEAT_ALARM_2', 'CAUTION', app_now(), '2단계', :a1, 'VF2-02', (SELECT max(notification_id) FROM notification), 'S2_OPEN')
RETURNING notification_id AS n2 \gset
SELECT t.eq(fn_auto_work_order_draft(:a1, 'REPEAT_2', :n2), :'wo', '2단계 계기 → 같은 작업지시서');
SELECT t.eq((SELECT array_to_string(trigger_kind, ',') FROM v_work_order WHERE wo_no = :'wo'), 'STOP_ALARM,REPEAT_STAGE2', '계기 2개');
SELECT t.eq((SELECT count(*) FROM work_order_step WHERE wo_no = :'wo')::int, (:n254 + :m254)::int, '원인 점검(보전 줄)을 덧붙임');

-- 다른 절을 가리키는 줄("§2.1 점검 2~3와 같다")은 그 절의 줄로 풀고 출처를 붙인다 (문서 문장은 그대로)
INSERT INTO alarm_check_step (alarm_code, seq, step_kind, step_text) VALUES ('994', 90, 'MNT', '막힘 점검은 §2.1 점검 2~3와 같다');
UPDATE maintenance_work_order SET status = 'CANCELLED', cancelled_by = 'U12', cancelled_at = app_now(), cancel_reason = '시험' WHERE wo_no = :'wo';
SELECT fn_ingest_alarm('VF2-02', '994', '2026-09-15 13:10+09') AS a4 \gset
SELECT t.eq((SELECT string_agg(step_text, ' | ' ORDER BY step_no) FROM work_order_step s JOIN maintenance_work_order m USING (wo_no)
              WHERE m.alarm_event_id = :a4 AND step_text LIKE '%(§2.1 점검%'),
            (SELECT string_agg(x || format(' (§2.1 점검 %s)', n), ' | ' ORDER BY n) FROM (
               SELECT step_text AS x, row_number() OVER (ORDER BY seq) AS n FROM alarm_check_step
                WHERE alarm_code = '992' AND step_kind IN ('OPR','MNT')) y WHERE n BETWEEN 2 AND 3),
            '참조 줄 → §2.1의 점검 2·3 문장 + (§2.1 점검 n)');

-- 끄기: app.auto_work_order = off
SET LOCAL app.auto_work_order = 'off';
SELECT fn_ingest_alarm('VF2-02', '992', '2026-09-15 13:20+09') AS a5 \gset
SELECT t.eq((SELECT count(*) FROM maintenance_work_order WHERE alarm_event_id = :a5)::int, 0, '설정으로 끌 수 있음');
ROLLBACK;
