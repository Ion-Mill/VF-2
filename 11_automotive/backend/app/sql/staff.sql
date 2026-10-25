-- =====================================================================
-- 직원 관리 (SCR-27, API-USR-01~05, 2026-10-25) — app/routers/staff.py · app/services/staff.py
-- 업무 기록은 새로 쌓지 않는다 (FR-USR-01-10): 기존 표의 "누가" 칸을 사람별로 모은다. 채팅 기록(chat_log)은 읽지 않는다
-- =====================================================================

-- 직원 명단 (비밀번호 해시는 내보내지 않음). 사용 중지된 직원은 include_inactive일 때만 (맨 뒤)
-- name: users
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active, last_login_at
  FROM app_user
 WHERE is_active OR CAST(:include_inactive AS boolean)
 ORDER BY is_active DESC, user_id;

-- 로그인한 누구나 보는 직원 목록 (GET /api/users): 이름·역할·담당 교대·공정·사용 중만 — 마지막 로그인·숫자·기록은 없음
-- name: users_public
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active
  FROM app_user ORDER BY user_id;

-- name: user
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active, last_login_at
  FROM app_user WHERE user_id = :user_id;

-- 고치기 전에 그 직원 행을 잠근다 (두 사람이 같은 직원을 함께 고칠 때 앞 사람 것을 덮지 않게)
-- name: user_lock
SELECT user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active
  FROM app_user WHERE user_id = :user_id FOR UPDATE;

-- name: user_ids
SELECT user_id FROM app_user;

-- 사용 중인 관리자 (MGR이 0명이 되는 변경을 막는다)
-- name: active_mgr_ids
SELECT user_id FROM app_user WHERE is_active AND role_code = 'MGR';

-- 직원 추가 (API-USR-04). 비밀번호는 서버가 scrypt로 바꾼 해시만 (NFR-SEC-06·07)
-- name: user_insert
INSERT INTO app_user (user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active, password_hash)
VALUES (:user_id, :user_name, :role_code, CAST(:home_shift_type AS varchar), CAST(:home_process_code AS varchar),
        CAST(:home_process_code_2 AS varchar), true, :password_hash)
RETURNING user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active;

-- 직원 고치기 (API-USR-03·05, SET-03): 칸 전부를 서버가 확인한 값으로. 비밀번호 해시는 새로 정할 때만
-- name: user_set
UPDATE app_user
   SET user_name = :user_name, role_code = :role_code, home_shift_type = CAST(:home_shift_type AS varchar),
       home_process_code = CAST(:home_process_code AS varchar), home_process_code_2 = CAST(:home_process_code_2 AS varchar),
       is_active = CAST(:is_active AS boolean), password_hash = coalesce(CAST(:password_hash AS text), password_hash)
 WHERE user_id = :user_id
RETURNING user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, is_active;

-- 저장한 수정 이력 번호 (fn_save_revision은 버전만 돌려준다)
-- name: revision_id
SELECT revision_id FROM document_revision
 WHERE doc_type = 'APP_USER' AND doc_key = :user_id AND version_no = CAST(:version_no AS int);

-- 지금 교대 (지금 근무 = 그 교대 안이고 담당 교대가 같음, FR-USR-01-01). 교대 사이면 바로 앞 교대 + is_on = false
-- name: current_shift
SELECT shift_id, shift_type, (start_at <= app_now() AND app_now() < end_at) AS is_on
  FROM shift WHERE start_at <= app_now() ORDER BY start_at DESC LIMIT 1;

-- 기간 "기록 전체"(all)의 시작 = 첫 교대 시작
-- name: data_start
SELECT least(min(start_at), app_now()) AS at FROM shift;

-- 사람별 업무 기록 (FR-USR-01-08·10). kind = 숫자 4칸 세는 이름 (app/domain/staff.py KPIS),
-- screen·key = 화면이 여는 곳 (시연 서버 server_staff.py와 같은 이름). 기간 [from, to], user_id를 비우면 모두. 최신이 위
-- 설정 변경(setting)은 설정 표에 "누가" 칸이 없어 접근 기록(access_log, 성공한 설정 바꾸기)에서 — 접근 기록은 실제 시각이라
-- 시연 시계가 실제 시각과 다르면 기간에 들지 않을 수 있다. 직원 고치기는 수정 이력(문서 수정)으로 센다
-- name: events
WITH ev (user_id, at, kind, text, screen, key, pq, gq, minutes) AS (
    SELECT worker_user_id, start_at, 'prod', format('%s 실적 %s개 · %s', process_code, pq, lot_no), 'lots', lot_no,
           pq, gq, NULL::numeric
      FROM operation_report
    UNION ALL
    SELECT reason_entered_by, start_at, 'reason_in',
           format('정지 사유 입력 · %s %s', equipment_id, coalesce(reason_code, reason_suggested_code)), NULL, NULL, NULL, NULL, NULL
      FROM equipment_state_log
    UNION ALL
    SELECT reason_confirmed_by, reason_confirmed_at, 'reason_ok',
           format('정지 사유 확정 · %s %s', equipment_id, coalesce(reason_code, reason_suggested_code)), NULL, NULL, NULL, NULL, NULL
      FROM equipment_state_log
    UNION ALL
    SELECT changed_by, changed_at, 'tool', format('공구 교체 · %s', tool_id), 'tools', left(tool_id, 6), NULL, NULL, NULL
      FROM tool_change
    UNION ALL
    SELECT assignee_user_id, created_at, 'wo_assign', format('작업지시서 담당 · %s %s', wo_no, equipment_id), 'docs', '작업지시서',
           NULL, NULL, NULL
      FROM maintenance_work_order
    UNION ALL
    SELECT approved_by, approved_at, 'wo_approve', format('작업지시서 승인 · %s', wo_no), 'docs', '작업지시서', NULL, NULL, NULL
      FROM maintenance_work_order
    UNION ALL
    SELECT confirmed_by, confirmed_at, 'wr_confirm',
           format('%s 확정 · %s %s', CASE WHEN record_type = 'FULL' THEN '작업기록서' ELSE '간이 작업기록' END, record_no, equipment_id),
           'docs', CASE WHEN record_type = 'FULL' THEN '작업기록서' ELSE '간이 작업기록' END, NULL, NULL, repair_min
      FROM work_record
    UNION ALL
    SELECT checked_by, checked_at, 'wr_check',
           format('%s 확인 · %s', CASE WHEN record_type = 'FULL' THEN '작업기록서' ELSE '간이 작업기록' END, record_no),
           'docs', CASE WHEN record_type = 'FULL' THEN '작업기록서' ELSE '간이 작업기록' END, NULL, NULL, NULL
      FROM work_record
    UNION ALL
    SELECT done_by, done_at, 'pm_done', format('예방 정비 실시 · %s', pm_task_id), 'pm', NULL, NULL, NULL, NULL
      FROM pm_record
    UNION ALL
    SELECT recorded_by, done_at, 'pm_rec', format('예방 정비 기록 · %s', pm_task_id), 'pm', NULL, NULL, NULL, NULL
      FROM pm_record WHERE recorded_by IS DISTINCT FROM done_by
    UNION ALL
    SELECT checked_by, checked_at, 'insp_check', format('측정값 확인 · %s %s번', lot_no, item_seq), 'quality', lot_no,
           NULL, NULL, NULL
      FROM inspection_result
    UNION ALL
    SELECT entered_by, measured_at, 'insp_entry', format('측정값 입력 · %s %s번', lot_no, item_seq), 'quality', lot_no,
           NULL, NULL, NULL
      FROM inspection_result
    UNION ALL
    SELECT recorded_by, found_at, 'defect', format('불량 기록 · %s %s %s개', lot_no, defect_code, qty), 'quality', lot_no,
           NULL, NULL, NULL
      FROM defect_record
    UNION ALL
    SELECT held_by, held_at, 'hold', format('로트 보류 · %s', lot_no), 'lots', lot_no, NULL, NULL, NULL
      FROM lot_hold
    UNION ALL
    SELECT released_by, released_at, 'release', format('로트 해제 · %s', lot_no), 'lots', lot_no, NULL, NULL, NULL
      FROM lot_hold
    UNION ALL
    SELECT scrap_approved_by, scrap_approved_at, 'scrap_ok', format('폐기 승인 · %s %s개', lot_no, scrap_proposed_qty), 'lots', lot_no,
           NULL, NULL, NULL
      FROM lot_hold
    UNION ALL
    SELECT txn_by, txn_at, 'inv',
           format('재고 %s · %s %s', CASE txn_type WHEN 'IN' THEN '입고' WHEN 'USE' THEN '사용' WHEN 'ADJUST' THEN '실사 조정'
                                                 WHEN 'FG_IN' THEN '완제품 입고' WHEN 'SHIP_OUT' THEN '출하' ELSE txn_type END,
                  item_no, trim_scale(qty_change)), 'inventory', NULL, NULL, NULL, NULL
      FROM inventory_txn
    UNION ALL
    SELECT confirmed_by, shipped_at, 'ship', format('출하 확인 · %s', shipment_no), 'inventory', NULL, NULL, NULL, NULL
      FROM shipment
    UNION ALL
    SELECT confirmed_by, confirmed_at, 'shift_ok', format('교대 보고서 확정 · %s', shift_id), 'shift', shift_id, NULL, NULL, NULL
      FROM shift_report
    UNION ALL
    SELECT confirmed_by, confirmed_at, 'daily_ok', format('일일 보고서 확정 · %s', work_date), 'daily', work_date::text,
           NULL, NULL, NULL
      FROM daily_report
    UNION ALL
    SELECT author_user_id, created_at, 'doc_edit',
           format('문서 수정 · %s %s v%s', CASE doc_type WHEN 'WORK_ORDER' THEN '작업지시서' WHEN 'WORK_RECORD' THEN '작업기록서'
                      WHEN 'SHIFT_REPORT' THEN '교대 보고서' WHEN 'DAILY_REPORT' THEN '일일 보고서' WHEN 'INTERNAL_DOC' THEN '사내 문서'
                      WHEN 'PM_RECORD' THEN '예방 정비 기록' WHEN 'SHIPMENT' THEN '출하 기록' WHEN 'APP_USER' THEN '직원 배치'
                      ELSE doc_type END, doc_key, version_no), 'revs', NULL, NULL, NULL, NULL
      FROM document_revision WHERE author_kind = 'HUMAN'
    UNION ALL
    SELECT user_id, at, 'setting',
           format('설정 변경 · %s', CASE WHEN path LIKE '/api/settings/targets%' THEN '목표 수량'
                                        WHEN path LIKE '/api/settings/notification-rules%' THEN '알림 규칙'
                                        ELSE '안전 재고' END), 'settings', NULL, NULL, NULL, NULL
      FROM access_log
     WHERE action = 'API' AND method IN ('POST','PUT','PATCH','DELETE') AND status_code < 400
       AND (path LIKE '/api/settings/targets%' OR path LIKE '/api/settings/notification-rules%'
            OR path LIKE '/api/inventory/items/%/safety-stock')
)
SELECT user_id, at, kind, text, screen, key, pq, gq, minutes
  FROM ev
 WHERE user_id IS NOT NULL AND at >= CAST(:from AS timestamptz) AND at <= CAST(:to AS timestamptz)
   AND (CAST(:user_id AS text) IS NULL OR user_id = CAST(:user_id AS text))
 ORDER BY at DESC, kind;
