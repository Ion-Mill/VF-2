-- =====================================================================
-- 2026-10-25 직원 관리 (API-USR-01~05) — 이미 올린 mom-db에 바뀐 부분만 (표·열은 그대로)
--   ① document_revision.doc_type에 APP_USER(직원 배치·정보) — 배치·정보를 바꾸면 사람마다 수정 이력 (FR-USR-01-05)
--   ② fn_doc_status('APP_USER', user_id) = ACTIVE / INACTIVE — fn_save_revision이 이 종류를 받게
--   ③ 권한 STAFF: 바꾸기(EDIT)·보기(VIEW) 모두 MGR만 (NFR-SEC-04) — 수정 이력의 APP_USER 보기도 이 권한
--   ④ 코드 이름 document_revision.doc_type APP_USER = "직원 배치"
-- 원본: db/schema/70_documents.sql, db/functions/30_workflows.sql, db/seed/20_roles_permissions.sql,
--   db/seed/11_code_labels_physical.sql (처음부터 만들 때는 원본으로 충분하다).
-- 스키마 주인(postgres)으로 한 번 (두 번 돌려도 같은 결과). 공용 mom-db에는 팀이 정한 한 사람이 올린다 (docs/05_결정기록.md).
-- 올리기 전: 백엔드의 직원 관리 저장(USR-03~05·SET-03 고치기)이 "문서 종류 APP_USER 없음"으로 실패한다. 조회(USR-01·02)는 된다.
-- 되돌리기: APP_USER 수정 이력이 없을 때만 — 아래 ①의 목록에서 'APP_USER'를 빼고 다시 걸고, fn_doc_status는
--   20261014000000 마이그레이션의 정의를 다시 실행, role_permission에서 target = 'STAFF' 두 줄, code_label에서 그 한 줄을 지운다.
-- =====================================================================
SET client_min_messages = warning;

-- ① 문서 종류 CHECK 넓히기 (처음 만들 때 이름 = document_revision_doc_type_check)
DO $$
DECLARE c text;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
              WHERE conrelid = 'public.document_revision'::regclass AND contype = 'c'
                AND pg_get_constraintdef(oid) LIKE '%doc_type%' AND pg_get_constraintdef(oid) LIKE '%SHIPMENT%' LOOP
        EXECUTE format('ALTER TABLE public.document_revision DROP CONSTRAINT %I', c);
    END LOOP;
END $$;
ALTER TABLE document_revision ADD CONSTRAINT document_revision_doc_type_check CHECK (doc_type IN
    ('WORK_ORDER','WORK_RECORD','SHIFT_REPORT','DAILY_REPORT','INTERNAL_DOC','PM_RECORD','SHIPMENT','APP_USER'));

-- ② 문서의 지금 상태
CREATE OR REPLACE FUNCTION fn_doc_status(p_doc_type text, p_doc_key text) RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE v text;
BEGIN
    CASE p_doc_type
        WHEN 'WORK_ORDER'   THEN SELECT status INTO v FROM maintenance_work_order WHERE wo_no = p_doc_key;
        WHEN 'WORK_RECORD'  THEN SELECT status INTO v FROM work_record WHERE record_no = p_doc_key;
        WHEN 'SHIFT_REPORT' THEN SELECT status INTO v FROM shift_report WHERE shift_id = p_doc_key;
        WHEN 'DAILY_REPORT' THEN SELECT status INTO v FROM daily_report WHERE work_date = p_doc_key::date;
        WHEN 'INTERNAL_DOC' THEN SELECT status INTO v FROM internal_doc WHERE doc_no = p_doc_key;
        WHEN 'PM_RECORD'    THEN SELECT status INTO v FROM pm_record WHERE pm_record_id = p_doc_key::bigint;
        WHEN 'SHIPMENT'     THEN SELECT status INTO v FROM shipment WHERE shipment_no = p_doc_key;
        -- 직원 배치·정보 (2026-10-25, API-USR-03~05): 잠기는 상태가 없어 사유 없이 고친다
        WHEN 'APP_USER'     THEN SELECT CASE WHEN is_active THEN 'ACTIVE' ELSE 'INACTIVE' END INTO v
                                   FROM app_user WHERE user_id = p_doc_key;
        ELSE RAISE EXCEPTION '문서 종류 % 없음', p_doc_type USING ERRCODE = '22023';
    END CASE;
    RETURN v;
END $$;

-- ③ 권한 (앱 서버는 권한표를 60초 기억한다 — 올린 뒤 1분 안에 반영)
INSERT INTO role_permission (role_code, target, action, scope) VALUES
  ('MGR','STAFF','EDIT','ALL'), ('MGR','STAFF','VIEW','ALL')
ON CONFLICT DO NOTHING;

-- ④ 코드 이름
INSERT INTO code_label (code_group, code, name_ko, sort_order, source_ref) VALUES
  ('document_revision.doc_type', 'APP_USER', '직원 배치 (직원 관리, 2026-10-25)', 8, 'FR-USR-01-05')
ON CONFLICT (code_group, code) DO UPDATE SET name_ko = EXCLUDED.name_ko, sort_order = EXCLUDED.sort_order;
