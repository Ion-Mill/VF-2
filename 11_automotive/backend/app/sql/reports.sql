-- 스케줄러가 부르는 것: 보고서 초안·시간 규칙 알림·보관 기간 보고 (PRD-02·04, DOC-07 10.2, NFR-DATA-04)

-- 교대가 끝나면(주간 17:00·야간 05:00) 그 교대 보고서 AI비서 초안 (이미 있으면 'EXISTS')
-- name: shift_draft
SELECT fn_create_shift_report_draft(:shift_id) AS result;

-- 06:00 전날 일일 보고서 초안. 반환: 확정 안 된 교대 수 (잠정)
-- name: daily_draft
SELECT fn_create_daily_report_draft(CAST(:work_date AS date)) AS pending_shifts;

-- 오늘·내일 근무일과 교대가 없으면 가장 최근 근무일을 본떠 만든다 (시연이 10/2로 넘어가도 교대가 있게)
-- name: ensure_days
SELECT fn_ensure_work_day(CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date))
     + fn_ensure_work_day(CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) + 1) AS created;

-- name: time_rules
SELECT fn_run_time_rules(CAST(:cmm_wait_min AS int)) AS created;

-- 끝난 지 하루가 안 된 교대 중 보고서(버전 포함)가 아직 없는 것 → 교대 보고서 초안 대상 (주간 17:00·야간 05:00)
-- name: ended_shifts
SELECT s.shift_id FROM shift s
 WHERE s.end_at <= app_now() AND s.end_at > app_now() - interval '1 day'
   AND NOT EXISTS (SELECT 1 FROM shift_report r WHERE r.shift_id = s.shift_id)
   AND NOT EXISTS (SELECT 1 FROM document_revision v WHERE v.doc_type = 'SHIFT_REPORT' AND v.doc_key = s.shift_id)
 ORDER BY s.end_at;

-- 06:00이 지났는데 전날 일일 보고서가 없으면 그 날짜 (야간 교대는 다음 날 05:00에 끝남)
-- name: daily_due
SELECT d.work_date FROM (
    SELECT CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS date) - 1 AS work_date,
           CAST(app_now() AT TIME ZONE 'Asia/Seoul' AS time) >= time '06:00' AS after_six) d
 WHERE d.after_six AND EXISTS (SELECT 1 FROM shift s WHERE s.work_date = d.work_date)
   AND NOT EXISTS (SELECT 1 FROM daily_report r WHERE r.work_date = d.work_date)
   AND NOT EXISTS (SELECT 1 FROM document_revision v WHERE v.doc_type = 'DAILY_REPORT' AND v.doc_key = d.work_date::text);

-- name: retention
SELECT * FROM fn_retention_report(app_now());

-- AI 비서 채팅 기록 30일 지난 것 지우기 (6.53 #18)
-- name: purge_chat
SELECT fn_purge_chat_log(app_now()) AS purged;
