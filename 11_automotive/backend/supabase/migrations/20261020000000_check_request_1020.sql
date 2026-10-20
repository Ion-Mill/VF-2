-- =====================================================================
-- 2026-10-20 정비 탭 확인 요청 반영 (구현_중_수정사항/1020_수정간단내용.md 33장) — 이미 올린 mom-db에 바뀐 부분만
--   1) 일일 보고서 관리자 메모 칸 daily_report.memo + 9월 기록의 "… 관리자 메모: X"를 떼어 옮김 (시연 기준점 복사본도)
--   5) 문서 알림 4종(WO_APPROVAL_REQUEST·WR_CONFIRM_PENDING·WR_CHECK_REQUEST·PM_RECORD_CHECK) + 예방 정비 기한 하루 전을
--      같은 기한 날짜끼리 1건으로 (notification_pm_task, ck_notification_related 완화)
--   2) 보고서 정지 ↔ 작업지시서 연결은 API 쿼리(app/sql/documents.sql report_stops)라 DB 바뀜 없음
-- 같은 내용이 db/ 원본에 있다 (처음부터 만들 때는 build_migration.sh). 스키마 주인(postgres)으로 한 번
-- =====================================================================
SET client_min_messages = warning;

-- ---------- 1. 관리자 메모 칸
ALTER TABLE daily_report ADD COLUMN IF NOT EXISTS memo text;
COMMENT ON COLUMN daily_report.memo IS '관리자 메모 (선택, 2026-10-20). 확정·저장 때 받는다';
-- 일일 보고서 글에서 관리자 메모 떼기 (2026-10-20 정비 탭 확인 요청 1 — daily_report.memo 칸이 생기기 전 글 모양).
--   생성기 9월 기록은 issues_summary 끝에 "… 관리자 메모: X", 시연 서버는 "… / 관리자 메모: X"를 붙였다 (맨 끝 것을 뗀다).
--   반환 {오늘의 문제 글, 메모}. 메모가 없으면 {글 그대로, NULL}. 쓰는 곳: tools/load_generated.py (적재 때)
CREATE OR REPLACE FUNCTION fn_split_memo(p_text text) RETURNS text[]
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN x.g IS NULL THEN ARRAY[p_text, NULL]
                ELSE ARRAY[regexp_replace(x.g[1], '\s*/\s*$', ''), nullif(btrim(x.g[2]), '')] END
      FROM (SELECT regexp_match(p_text, '^(.*\S)\s+관리자 메모:\s*(.*)$') AS g) x;
$$;
-- 9월 기록(생성기)의 메모를 칸으로 옮긴다. 확정된 보고서의 잠금(R-35) 트리거를 건너뛰려고 이 블록 안에서만 replica
-- (글자 모양만 옮김 — 내용·버전은 그대로)
-- (DO 블록 하나 = 한 트랜잭션 — fn_demo_reset처럼 EXECUTE 'SET LOCAL …': Supabase postgres는 SET 문으로만 바꿀 수 있음)
DO $$
BEGIN
    EXECUTE 'SET LOCAL session_replication_role = replica';
    UPDATE daily_report SET issues_summary = (fn_split_memo(issues_summary))[1], memo = (fn_split_memo(issues_summary))[2]
     WHERE memo IS NULL AND (fn_split_memo(issues_summary))[2] IS NOT NULL;
    ALTER TABLE demo_snapshot.daily_report ADD COLUMN IF NOT EXISTS memo text;
    UPDATE demo_snapshot.daily_report SET issues_summary = (fn_split_memo(issues_summary))[1], memo = (fn_split_memo(issues_summary))[2]
     WHERE memo IS NULL AND (fn_split_memo(issues_summary))[2] IS NOT NULL;
    EXECUTE 'SET LOCAL session_replication_role = origin';
END $$;

-- ---------- 5. 알림 ↔ 예방 정비 항목, R-38 완화 (묶은 PM_DUE_SOON)
ALTER TABLE notification DROP CONSTRAINT ck_notification_related;
ALTER TABLE notification ADD CONSTRAINT ck_notification_related CHECK (num_nonnulls(alarm_event_id, equipment_id, lot_no, item_no,
    pm_task_id, tool_id, wo_no, bottleneck_log_id, revision_id, result_id, shift_id, buffer_code, cmm_import_id,
    prev_stage_notification_id) >= 1 OR rule_code = 'PM_DUE_SOON');
-- ---------------------------------------------------------------------
-- 알림 ↔ 예방 정비 항목 [물리 추가, 2026-10-20 정비 탭 확인 요청 5] — 여러 항목을 1건으로 묶는 알림의 관련 항목
--   PM_DUE_SOON  예방 정비 기한 하루 전: 같은 기한 날짜끼리 1건 (묶인 항목이 모두 끝나거나 기한을 넘기면 자동 처리)
--   PM_RECORD_CHECK  예방 정비 실시 기록 확인: 설비마다 1건, 초안 실시 기록의 항목 (묶인 기록이 모두 확정되면 자동 처리)
-- ---------------------------------------------------------------------
CREATE TABLE notification_pm_task (
    notification_id  bigint      NOT NULL REFERENCES notification ON DELETE CASCADE,
    pm_task_id       varchar(30) NOT NULL REFERENCES pm_task,
    PRIMARY KEY (notification_id, pm_task_id)
);
CREATE INDEX ix_notification_pm_task_task ON notification_pm_task (pm_task_id);
-- 권한·잠그기 (db/roles.sql·supabase/sql/lockdown.sql과 같게)
GRANT SELECT, INSERT, UPDATE, DELETE ON notification_pm_task TO mom_app;
GRANT SELECT ON notification_pm_task TO mom_ai_ro;
ALTER TABLE notification_pm_task ENABLE ROW LEVEL SECURITY;
CREATE POLICY mom_app_all ON notification_pm_task TO mom_app USING (true) WITH CHECK (true);
CREATE POLICY mom_ai_ro_read ON notification_pm_task FOR SELECT TO mom_ai_ro USING (true);
-- 시연 기준점(SIM-03): 새 표도 복사본에 두고 되돌리기 목록에 넣는다 (안 넣으면 되돌릴 때 notification을 비우지 못함)
CREATE TABLE IF NOT EXISTS demo_snapshot.notification_pm_task AS SELECT * FROM public.notification_pm_task;
UPDATE demo_snapshot.meta SET tables = array_append(tables, 'notification_pm_task') WHERE NOT ('notification_pm_task' = ANY (tables));

-- ---------- 5. 알림 규칙 4종 (db/seed/30_notification_rules.sql) + 코드 이름 (db/seed/11_code_labels_physical.sql)
INSERT INTO notification_rule (rule_code, rule_name, condition_text, importance, delivery_kind, process_mode, processor_roles,
                               recipient_roles, report_rank, rank_group) VALUES
  ('WO_APPROVAL_REQUEST', '작업지시서 승인 요청', '작업지시서 초안이 생길 때 → 반장. 승인·취소, 또는 승인 대기 30분 알림이 뜨면 자동 처리', 'INFO', 'BUBBLE', 'AUTO', '{}', '{SUP}', 'R4', 0),
  ('WR_CONFIRM_PENDING', '작업기록서 확정 전', '작업기록서(작업지시서 짝)가 생길 때(초안·수정 중) → 그 작업지시서 담당 MNT. 확정하면 자동 처리', 'INFO', 'LIST', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('WR_CHECK_REQUEST', '작업기록서 확인 요청', '보전 담당자가 작업기록서를 확정할 때 → 반장. 반장이 [확인]하면 자동 처리', 'INFO', 'BUBBLE', 'AUTO', '{}', '{SUP}', 'R4', 0),
  ('PM_RECORD_CHECK', '예방 정비 실시 기록 확인', '예방 정비 실시 기록이 초안으로 생길 때 → MNT (설비마다 1건으로 묶음). 묶인 기록이 모두 확정되면 자동 처리', 'INFO', 'LIST', 'AUTO', '{}', '{MNT}', 'R4', 0)
ON CONFLICT (rule_code) DO NOTHING;
UPDATE notification_rule SET condition_text = '기한 하루 전 (주 1회 이상 주기 항목만 — 매일·교대 점검은 점검표). 같은 기한 날짜끼리 1건으로 묶음 — 묶인 항목이 모두 끝나거나 기한을 넘기면 자동 처리' WHERE rule_code = 'PM_DUE_SOON';
INSERT INTO code_label (code_group, code, name_ko, sort_order, source_ref) VALUES
  ('notification_rule.rule_code', 'WO_APPROVAL_REQUEST', '작업지시서 승인 요청 (2026-10-20)', 26, '물리 추가'),
  ('notification_rule.rule_code', 'WR_CONFIRM_PENDING', '작업기록서 확정 전 (2026-10-20)', 27, '물리 추가'),
  ('notification_rule.rule_code', 'WR_CHECK_REQUEST', '작업기록서 확인 요청 (2026-10-20)', 28, '물리 추가'),
  ('notification_rule.rule_code', 'PM_RECORD_CHECK', '예방 정비 실시 기록 확인 (2026-10-20)', 29, '물리 추가')
ON CONFLICT (code_group, code) DO UPDATE SET name_ko = EXCLUDED.name_ko, sort_order = EXCLUDED.sort_order;

-- ---------- 5. 알림을 만들고 닫는 함수·트리거 (db/views/20_report_functions.sql)
-- 작업지시서 상태가 바뀔 때 (6.36 처리 표, 2026-10-13):
--   승인·취소 → 승인 대기 알림(APPROVAL_WAIT_*) 자동 처리. 승인 → 담당 MNT에게 "작업지시서 배정"(WO_ASSIGNED)
--   AI비서 초안 → 수정 중(보전 담당자가 저장) → 초안 검토 알림(WO_DRAFT_READY) 자동 처리
--   승인 → 진행 중([작업 시작]) → 배정 알림 자동 처리 (담당 MNT가 작업지시서를 "열면"도 처리 — API-MNT-06 GET)
--   작업지시서를 취소하면 남은 초안 검토·배정 알림도 닫는다
--   승인·취소 → 승인 요청 알림(WO_APPROVAL_REQUEST, 2026-10-20)도 자동 처리
CREATE OR REPLACE FUNCTION trg_work_order_approved() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('APPROVED','CANCELLED') AND OLD.status IN ('AI_DRAFT','EDITING') THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code IN ('APPROVAL_WAIT_30M','APPROVAL_WAIT_2H','WO_APPROVAL_REQUEST')
                                         AND wo_no = NEW.wo_no AND NOT is_processed),
                                coalesce(NEW.approved_by, NEW.cancelled_by), coalesce(NEW.approved_at, NEW.cancelled_at));
    END IF;
    IF NEW.status = 'APPROVED' AND OLD.status IN ('AI_DRAFT','EDITING') AND NEW.assignee_user_id IS NOT NULL THEN
        PERFORM fn_raise_notification('WO_ASSIGNED', format('작업지시서 %s 배정 (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id),
                                      NEW.approved_at, p_recipients => ARRAY[NEW.assignee_user_id]);
    END IF;
    IF OLD.status = 'AI_DRAFT' AND NEW.status <> 'AI_DRAFT' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_DRAFT_READY' AND wo_no = NEW.wo_no AND NOT is_processed),
                                NULL, app_now());
    END IF;
    IF (NEW.status = 'IN_PROGRESS' AND OLD.status = 'APPROVED') OR NEW.status = 'CANCELLED' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_ASSIGNED' AND wo_no = NEW.wo_no AND NOT is_processed),
                                CASE WHEN NEW.status = 'IN_PROGRESS' THEN NEW.assignee_user_id END, app_now());
    END IF;
    RETURN NULL;
END $$;

-- 작업지시서 AI비서 초안이 생기면 → 그 설비 MNT에게 "작업지시서 초안 검토" (6.36 WO_DRAFT_READY, 2026-10-13).
-- 받는 사람 = 보전 담당자 전원 (긴급 알림 처리 책임 MNT와 같은 사람 — 설비별 담당 MNT 칸이 없어 MNT 전원 [제안])
-- 초안(AI비서 초안·수정 중)이 생기면 반장에게 "작업지시서 승인 요청"도 (WO_APPROVAL_REQUEST, 2026-10-20 정비 탭 확인 요청 5).
--   승인·취소하면(trg_work_order_approved), 또는 승인 대기 30분 알림이 뜨면(fn_run_time_rules) 자동 처리 — 그 뒤는 승인 대기 알림이 맡는다
CREATE OR REPLACE FUNCTION trg_work_order_draft_ready() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    IF NEW.status = 'AI_DRAFT' THEN
        PERFORM fn_raise_notification('WO_DRAFT_READY', format('작업지시서 초안 검토: %s (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id), NEW.created_at);
    END IF;
    IF NEW.status IN ('AI_DRAFT','EDITING') THEN
        PERFORM fn_raise_notification('WO_APPROVAL_REQUEST', format('작업지시서 %s 승인해 주세요 (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id), NEW.created_at);
    END IF;
    RETURN NULL;
END $$;

-- ---------------------------------------------------------------------
-- 문서 알림 4종·예방 정비 하루 전 묶기 (2026-10-20 정비 탭 확인 요청 5 — 화면 규칙 frontend/src/shell/rules.ts와 같은 뜻)
-- ---------------------------------------------------------------------

-- 작업기록서(작업지시서 짝, FULL) 알림:
--   생김(AI비서 초안·수정 중) → 그 작업지시서 담당 MNT에게 "확정 전"(WR_CONFIRM_PENDING, 알림 탭만). 담당이 없으면 MNT 전원
--   확정 → 확정 전 알림 자동 처리 + 반장에게 "확인 요청"(WR_CHECK_REQUEST, 말풍선). 확인 뒤 고쳐서 다시 확정 전 상태가 되면 다시 요청
--   반장 [확인](CHECKED) → 확인 요청 자동 처리. 간이 작업기록(SIMPLE)은 확인 단계가 없어 알리지 않는다
CREATE OR REPLACE FUNCTION trg_work_record_doc_alert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_assignee text;
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' OR NEW.record_type <> 'FULL' THEN RETURN NULL; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status IN ('AI_DRAFT','EDITING') THEN
            SELECT assignee_user_id INTO v_assignee FROM maintenance_work_order WHERE wo_no = NEW.wo_no;
            PERFORM fn_raise_notification('WR_CONFIRM_PENDING',
                format('작업기록서 %s 확정 전 (작업지시서 %s)', NEW.record_no, NEW.wo_no),
                jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id), NULL,
                p_recipients => CASE WHEN v_assignee IS NOT NULL THEN ARRAY[v_assignee] END);
        END IF;
        RETURN NULL;
    END IF;
    IF NEW.status = 'CONFIRMED' AND OLD.status IS DISTINCT FROM 'CONFIRMED' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WR_CONFIRM_PENDING' AND wo_no = NEW.wo_no AND NOT is_processed),
                                NEW.confirmed_by, NEW.confirmed_at);
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'WR_CHECK_REQUEST' AND wo_no = NEW.wo_no AND NOT is_processed) THEN
            PERFORM fn_raise_notification('WR_CHECK_REQUEST',
                format('작업기록서 %s 확정됨 — 확인해 주세요 (작업지시서 %s)', NEW.record_no, NEW.wo_no),
                jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id), NULL);
        END IF;
    ELSIF NEW.status = 'CHECKED' AND OLD.status IS DISTINCT FROM 'CHECKED' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WR_CHECK_REQUEST' AND wo_no = NEW.wo_no AND NOT is_processed),
                                NEW.checked_by, NEW.checked_at);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER work_record_doc_alert AFTER INSERT OR UPDATE OF status ON work_record
    FOR EACH ROW EXECUTE FUNCTION trg_work_record_doc_alert();

-- 예방 정비 기한 하루 전 묶음 자동 처리: 열린 PM_DUE_SOON 중 묶인 항목(notification_pm_task + 9월 기록의 pm_task_id)이
--   하나도 "아직 기한 전·당일"이 아니면 처리 — 실시해서 다음 기한이 밀렸거나, 기한을 넘겼거나(그쪽은 PM_OVERDUE가 맡음).
--   알림의 기한 날짜 = 알린 날(한국 날짜) + 1. 반환: 처리한 수
CREATE OR REPLACE FUNCTION fn_close_pm_due_soon(p_actor text DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE sql AS $$
    WITH t AS (SELECT coalesce(p_at, app_now()) AS at),
    open_n AS (
        SELECT n.notification_id, (n.raised_at AT TIME ZONE 'Asia/Seoul')::date + 1 AS due
          FROM notification n WHERE n.rule_code = 'PM_DUE_SOON' AND NOT n.is_processed
    ), members AS (
        SELECT notification_id, pm_task_id FROM notification_pm_task
        UNION
        SELECT notification_id, pm_task_id FROM notification WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id IS NOT NULL
    )
    SELECT fn_auto_process(ARRAY(
        SELECT o.notification_id FROM open_n o, t
         WHERE NOT EXISTS (SELECT 1 FROM members m JOIN v_pm_task_due d USING (pm_task_id)
                            WHERE m.notification_id = o.notification_id AND d.is_active
                              AND d.next_due_date BETWEEN (t.at AT TIME ZONE 'Asia/Seoul')::date AND o.due)),
        p_actor, (SELECT at FROM t));
$$;

-- 예방 정비 기한 하루 전 알림 (참고, MNT): 내일이 기한인 항목(달력에 있는 것)을 같은 기한 날짜끼리 1건으로 묶는다.
--   이미 열린 하루 전 알림에 든 항목은 빼고, 같은 날짜의 열린 묶음이 있으면 거기에 더한다 (건수·항목 목록 다시 씀).
--   문장 "기한 10/02 (내일) 예방 정비 4건", 관련 정보 = "설비 항목 · …". 반환: 새로 만든 알림 수
CREATE OR REPLACE FUNCTION fn_raise_pm_due_soon(p_at timestamptz DEFAULT NULL) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_due date := (v_at AT TIME ZONE 'Asia/Seoul')::date + 1;
    v_tasks text[]; v_id bigint; v_new int := 0; v_cnt int; v_items text;
BEGIN
    SELECT array_agg(d.pm_task_id ORDER BY d.equipment_id, d.pm_task_id) INTO v_tasks
      FROM v_pm_task_due d
     WHERE d.is_active AND d.on_calendar AND d.next_due_date = v_due
       AND NOT EXISTS (SELECT 1 FROM notification n
                        WHERE n.rule_code = 'PM_DUE_SOON' AND NOT n.is_processed
                          AND (n.pm_task_id = d.pm_task_id
                               OR EXISTS (SELECT 1 FROM notification_pm_task l
                                           WHERE l.notification_id = n.notification_id AND l.pm_task_id = d.pm_task_id)));
    IF v_tasks IS NULL THEN RETURN 0; END IF;
    SELECT notification_id INTO v_id FROM notification
     WHERE rule_code = 'PM_DUE_SOON' AND NOT is_processed AND pm_task_id IS NULL
       AND (raised_at AT TIME ZONE 'Asia/Seoul')::date + 1 = v_due
     ORDER BY raised_at LIMIT 1;
    IF v_id IS NULL THEN
        SELECT count(*), string_agg(equipment_id || ' ' || item_name, ' · ' ORDER BY equipment_id, pm_task_id) INTO v_cnt, v_items
          FROM pm_task WHERE pm_task_id = ANY (v_tasks);
        v_id := fn_raise_notification('PM_DUE_SOON', format('기한 %s (내일) 예방 정비 %s건', to_char(v_due, 'MM/DD'), v_cnt),
                                      '{}'::jsonb, v_at, p_related_info => v_items);
        IF v_id IS NULL THEN RETURN 0; END IF;          -- 규칙이 꺼져 있음
        v_new := 1;
    END IF;
    INSERT INTO notification_pm_task (notification_id, pm_task_id) SELECT v_id, unnest(v_tasks) ON CONFLICT DO NOTHING;
    IF v_new = 0 THEN
        SELECT count(*), string_agg(t.equipment_id || ' ' || t.item_name, ' · ' ORDER BY t.equipment_id, t.pm_task_id)
          INTO v_cnt, v_items
          FROM notification_pm_task l JOIN pm_task t USING (pm_task_id) WHERE l.notification_id = v_id;
        UPDATE notification SET message = format('기한 %s (내일) 예방 정비 %s건', to_char(v_due, 'MM/DD'), v_cnt),
               related_info = v_items
         WHERE notification_id = v_id;
    END IF;
    RETURN v_new;
END $$;

-- 예방 정비 실시 기록 알림 (PM_RECORD_CHECK, 참고·알림 탭만, MNT): 실시 기록이 초안으로 생기면 그 설비의 열린 알림 1건에
--   항목을 더한다 (없으면 새로, "VF2-01 예방 정비 2건 끝남 — 실시 기록 확인"). 묶인 항목의 초안 기록이 모두 확정되면 자동 처리.
--   확정되면 예방 정비 기한 하루 전 묶음도 다시 본다 (fn_close_pm_due_soon)
CREATE OR REPLACE FUNCTION trg_pm_record_doc_alert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_eq text; v_id bigint; v_ids bigint[];
BEGIN
    IF current_setting('app.loading', true) IS NOT DISTINCT FROM 'on' THEN RETURN NULL; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'DRAFT' THEN RETURN NULL; END IF;
        SELECT equipment_id INTO v_eq FROM pm_task WHERE pm_task_id = NEW.pm_task_id;
        SELECT notification_id INTO v_id FROM notification
         WHERE rule_code = 'PM_RECORD_CHECK' AND equipment_id = v_eq AND NOT is_processed ORDER BY raised_at DESC LIMIT 1;
        IF v_id IS NULL THEN
            v_id := fn_raise_notification('PM_RECORD_CHECK', format('%s 예방 정비 1건 끝남 — 실시 기록 확인', v_eq),
                                          jsonb_build_object('equipment_id', v_eq), NULL);
            IF v_id IS NULL THEN RETURN NULL; END IF;    -- 규칙이 꺼져 있음
        END IF;
        INSERT INTO notification_pm_task (notification_id, pm_task_id) VALUES (v_id, NEW.pm_task_id) ON CONFLICT DO NOTHING;
        UPDATE notification SET message = format('%s 예방 정비 %s건 끝남 — 실시 기록 확인', v_eq,
                                                 (SELECT count(*) FROM notification_pm_task WHERE notification_id = v_id))
         WHERE notification_id = v_id;
    ELSIF NEW.status = 'CONFIRMED' AND OLD.status = 'DRAFT' THEN
        SELECT array_agg(n.notification_id) INTO v_ids FROM notification n
         WHERE n.rule_code = 'PM_RECORD_CHECK' AND NOT n.is_processed
           AND EXISTS (SELECT 1 FROM notification_pm_task l WHERE l.notification_id = n.notification_id AND l.pm_task_id = NEW.pm_task_id)
           AND NOT EXISTS (SELECT 1 FROM notification_pm_task l JOIN pm_record p USING (pm_task_id)
                            WHERE l.notification_id = n.notification_id AND p.status = 'DRAFT');
        IF v_ids IS NOT NULL THEN PERFORM fn_auto_process(v_ids, NEW.recorded_by); END IF;
        PERFORM fn_close_pm_due_soon(NEW.recorded_by);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER pm_record_doc_alert AFTER INSERT OR UPDATE OF status ON pm_record
    FOR EACH ROW EXECUTE FUNCTION trg_pm_record_doc_alert();

-- 스케줄러가 몇 분마다 부르는 시간 규칙 알림 (승인 대기·예방 정비 기한·CMM 결과 미수신·목표 미달 위험) + 지금 야간 이월. 반환: 새 알림 수
CREATE OR REPLACE FUNCTION fn_run_time_rules(p_cmm_wait_min int DEFAULT 10, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_today date := (v_at AT TIME ZONE 'Asia/Seoul')::date;
    v_n int := 0; r record;
BEGIN
    -- 승인 대기 30분(참고)·2시간(주의) — DOC-07 10.2
    FOR r IN SELECT wo_no, equipment_id, created_at FROM maintenance_work_order
              WHERE status IN ('AI_DRAFT','EDITING') AND created_at <= v_at - interval '30 minutes' LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_30M' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_30M', format('작업지시서 %s 승인 대기 30분', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
        -- 승인 대기 30분이 되면 승인 요청 알림은 그쪽으로 넘어가 닫힌다 (2026-10-20)
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_APPROVAL_REQUEST' AND wo_no = r.wo_no AND NOT is_processed),
                                NULL, v_at);
        IF r.created_at <= v_at - interval '2 hours'
           AND NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_2H' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_2H', format('작업지시서 %s 승인 대기 2시간', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 예방 정비 기한 하루 전(참고)·넘김(주의) — 달력에 있는 항목만
    --   하루 전은 같은 기한 날짜끼리 1건으로 묶는다 (2026-10-20 정비 탭 확인 요청 5, FR-AST-02-08) → fn_raise_pm_due_soon.
    --   묶인 항목이 모두 끝나거나 기한을 넘기면 자동 처리 (fn_close_pm_due_soon — 항목마다 1건이던 9월 알림도 같은 규칙)
    PERFORM fn_close_pm_due_soon(NULL, v_at);
    v_n := v_n + fn_raise_pm_due_soon(v_at);
    FOR r IN SELECT pm_task_id, equipment_id, item_name, next_due_date FROM v_pm_task_due
              WHERE is_active AND on_calendar AND next_due_date IS NOT NULL AND next_due_date < v_today LOOP
        IF NOT EXISTS (SELECT 1 FROM notification
                WHERE rule_code = 'PM_OVERDUE' AND pm_task_id = r.pm_task_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('PM_OVERDUE', format('%s 예방 정비 기한 넘김: %s', r.equipment_id, r.item_name),
                                          jsonb_build_object('pm_task_id', r.pm_task_id, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- CMM 결과 미수신 (대기 시간은 [선택 필요: 기술 회의])
    FOR r IN SELECT instruction_id, lot_no, part_seq FROM cmm_instruction
              WHERE status = 'STARTED' AND started_at < v_at - make_interval(mins => p_cmm_wait_min) LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CMM_NO_RESULT' AND lot_no = r.lot_no AND NOT is_processed) THEN
            PERFORM fn_raise_notification('CMM_NO_RESULT', format('측정 결과 미수신: %s 순번 %s', r.lot_no, r.part_seq),
                                          jsonb_build_object('lot_no', r.lot_no, 'equipment_id', 'CMM-01'), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 지금 야간 교대의 이월 (R-88). 주간 초안·확정 때 채우지만, 적재한 데이터·늦은 확정에 대비해 다시 맞춘다
    PERFORM fn_refresh_carry_over(work_date) FROM shift WHERE shift_type = 'NIGHT' AND start_at <= v_at AND end_at > v_at;
    -- 목표 미달 위험 (R-48·R-88, FR-AST-02-04): 지금 교대의 예측 < 총 목표(목표 + 이월) × 90% → 반장. 교대마다 1번.
    --   교대 시작 1시간 뒤부터 본다 [제안] — 시작 직후는 첫 부품이 OP-50에 닿기 전이라 예측이 0에 가깝다 (DOC-07 8장)
    FOR r IN SELECT shift_id, forecast_qty, total_target_qty, shortfall_qty, carry_over_qty FROM v_shift_progress
              WHERE start_at <= v_at AND end_at > v_at AND elapsed_min >= 60 AND is_target_risk LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TARGET_RISK' AND shift_id = r.shift_id) THEN
            PERFORM fn_raise_notification('TARGET_RISK',
                format('목표 미달 위험: 이 속도면 목표보다 %s개 부족 (예측 %s / 총 목표 %s)', r.shortfall_qty, r.forecast_qty,
                       r.total_target_qty),
                jsonb_build_object('shift_id', r.shift_id), v_at,
                p_related_info => format('총 목표 = 목표 %s + 이월 %s (DOC-07 §4.1·8장)', r.total_target_qty - r.carry_over_qty,
                                         r.carry_over_qty));
            v_n := v_n + 1;
        END IF;
    END LOOP;
    RETURN v_n;
END $$;

-- 새 함수 권한 (db/roles.sql: PUBLIC 실행 금지, 앱 계정만)
REVOKE EXECUTE ON FUNCTION fn_split_memo(text), fn_close_pm_due_soon(text, timestamptz), fn_raise_pm_due_soon(timestamptz),
    trg_work_record_doc_alert(), trg_pm_record_doc_alert() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fn_split_memo(text), fn_close_pm_due_soon(text, timestamptz), fn_raise_pm_due_soon(timestamptz),
    trg_work_record_doc_alert(), trg_pm_record_doc_alert() TO mom_app;
