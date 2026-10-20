-- 2026-10-13~14 팀 결정 반영 (구현_중_수정사항 1013·1014): 알림 전달 방식·새 알림 3종, 일일 보고서 생성 시점(R-72),
-- 병목 기록 규칙, 근무일 만들기, 채팅 기록 30일
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');

-- 전달 방식 (6.36 아래): 긴급 = 팝업, 문서 알림 6종 = 말풍선, 나머지 = 목록
SELECT t.eq((SELECT string_agg(rule_code, ',' ORDER BY rule_code) FROM notification_rule WHERE delivery_kind = 'BUBBLE'),
            'APPROVAL_WAIT_2H,APPROVAL_WAIT_30M,DAILY_REPORT_PENDING,DOC_REVISED,SHIFT_REPORT_PENDING,WO_APPROVAL_REQUEST,WO_ASSIGNED,WO_DRAFT_READY,WR_CHECK_REQUEST',
            '말풍선 = 문서 알림 6종 (승인 대기 2개 포함 7규칙) + 2026-10-20 승인 요청·작업기록서 확인 요청');
SELECT t.eq((SELECT string_agg(rule_code, ',') FROM notification_rule WHERE delivery_kind = 'POPUP'), 'ALARM_STOP', '팝업 = 정지 알람만');
SELECT t.eq((SELECT count(*) FROM notification_rule)::int, 29, '알림 규칙 29행 (2026-10-20 문서 알림 4종 추가)');

-- 작업지시서 AI비서 초안 → 그 설비 MNT에게 초안 검토 (WO_DRAFT_READY)
SELECT fn_ingest_alarm('VF2-02', '254', '2026-09-15 13:00+09', 'LOT-2609-041-1') AS a \gset
SELECT fn_create_work_order_draft('VF2-02', '알람 254 점검', '주축 모터 과열', p_alarm_event_id => :a) AS wo \gset
SELECT t.eq((SELECT string_agg(r.user_id, ',' ORDER BY r.user_id) FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'WO_DRAFT_READY' AND n.wo_no = :'wo'), 'U07,U08,U09', '초안 검토 → 보전 담당자');
-- 보전 담당자가 저장(수정 중) → 자동 처리
UPDATE maintenance_work_order SET status = 'EDITING', assignee_user_id = 'U08' WHERE wo_no = :'wo';
SELECT t.ok((SELECT bool_and(is_processed) FROM notification WHERE rule_code = 'WO_DRAFT_READY' AND wo_no = :'wo'),
            '저장하면 초안 검토 알림 처리');
-- 승인 → 담당 MNT에게 배정 알림 (WO_ASSIGNED, FR-MNT-03-14). [작업 시작]이면 처리
UPDATE maintenance_work_order SET status = 'APPROVED', approved_by = 'U10', approved_at = app_now() WHERE wo_no = :'wo';
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              WHERE n.rule_code = 'WO_ASSIGNED' AND n.wo_no = :'wo'), 'U08', '배정 알림 → 담당 MNT만');
UPDATE maintenance_work_order SET status = 'IN_PROGRESS' WHERE wo_no = :'wo';
SELECT t.eq((SELECT processed_by FROM notification WHERE rule_code = 'WO_ASSIGNED' AND wo_no = :'wo'), 'U08',
            '작업 시작 → 배정 알림 처리 (담당 MNT)');

-- R-72: 야간 교대 보고서를 확정하는 즉시 일일 보고서 초안 + MGR에게 확정 요청 (DAILY_REPORT_PENDING)
SELECT t.freeze('2026-09-16 05:20+09');
SELECT fn_create_shift_report_draft('2026-09-15-D', '2026-09-15 17:00+09');
SELECT fn_create_shift_report_draft('2026-09-15-N', '2026-09-16 05:00+09');
SELECT t.ok(NOT EXISTS (SELECT 1 FROM daily_report WHERE work_date = '2026-09-15'), '야간 확정 전에는 일일 보고서 없음');
UPDATE shift_report SET status = 'CONFIRMED', confirmed_by = 'U11', confirmed_at = '2026-09-16 05:20+09' WHERE shift_id = '2026-09-15-N';
SELECT t.ok(EXISTS (SELECT 1 FROM daily_report WHERE work_date = '2026-09-15' AND status = 'AI_DRAFT'),
            '야간 확정 즉시 일일 보고서 AI비서 초안');
SELECT t.eq((SELECT string_agg(r.user_id, ',') FROM notification n JOIN notification_recipient r USING (notification_id)
              JOIN document_revision v ON v.revision_id = n.revision_id
              WHERE n.rule_code = 'DAILY_REPORT_PENDING' AND v.doc_key = '2026-09-15'), 'U12', '확정 요청 → MGR');
SELECT t.eq((SELECT count(*) FROM daily_report WHERE work_date = '2026-09-15')::int, 1, '생산일마다 1개');
-- 06:00 스케줄러가 다시 불러도 그대로 (이미 있음)
SELECT t.eq(fn_create_daily_report_draft('2026-09-15', '2026-09-16 06:00+09'), 0, '06:00에는 다시 만들지 않음');

-- 병목 기록: 공정 또는 원인이 바뀔 때만 한 줄 (5.B.6, 2026-10-13)
INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code)
VALUES ('2026-09-17 09:00+09', NULL, 'OP-30', 'BASE'), ('2026-09-17 10:00+09', 'OP-30', 'OP-30', 'C1');
SELECT t.throws($$INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code)
                  VALUES ('2026-09-17 11:00+09', 'OP-30', 'OP-30', 'C1')$$, '공정·원인이 같음', '앞 줄과 같은 공정·원인은 거절');
SELECT t.throws($$INSERT INTO bottleneck_log (changed_at, prev_process_code, new_process_code, cause_code)
                  VALUES ('2026-09-17 11:00+09', 'OP-20', 'OP-40', 'C2')$$, '이전 병목', '이전 병목 = 앞 줄의 새 병목');

-- 근무일·교대 만들기 (시연 10/1 — 가장 최근 근무일을 본뜸)
SELECT t.eq(fn_ensure_work_day('2026-09-17'), 2, '주간·야간 2개');
SELECT t.eq((SELECT string_agg(shift_id || ' ' || to_char(start_at AT TIME ZONE 'Asia/Seoul', 'HH24:MI') || ' ' || supervisor_user_id, ',' ORDER BY start_at)
               FROM shift WHERE work_date = '2026-09-17'), '2026-09-17-D 08:00 U10,2026-09-17-N 20:00 U11', '시각·반장도 같게');
SELECT t.eq(fn_ensure_work_day('2026-09-17'), 0, '이미 있으면 그대로');

-- 채팅 기록: 본인 것, 30일 지나면 삭제 (6.53 #18)
INSERT INTO chat_log (user_id, asked_at, question, answer, status) VALUES
  ('U02', '2026-08-01 10:00+09', '오래된 질문', '답', 'OK'),
  ('U02', '2026-09-16 05:00+09', '어제 VF2-01 MTTR?', '이 정보(MTTR)는 보전 담당자·관리자만 볼 수 있습니다', 'OUT_OF_ROLE');
SELECT t.throws($$INSERT INTO chat_log (user_id, asked_at, question, status) VALUES ('U02', now(), '질문', 'OK')$$,
                'ck_chat_log_answer', '응답 없음이 아니면 답 필수');
SELECT t.eq(fn_purge_chat_log('2026-09-16 06:00+09'), 1, '30일 지난 1건 삭제');
SELECT t.eq((SELECT count(*) FROM chat_log WHERE user_id = 'U02')::int, 1, '30일 안 기록은 남음');
ROLLBACK;
