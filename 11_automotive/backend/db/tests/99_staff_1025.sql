-- 2026-10-25 직원 관리 (API-USR-01~05): 수정 이력의 문서 종류 APP_USER, 직원 상태 ACTIVE/INACTIVE, 권한 STAFF(MGR만)
BEGIN;
SELECT t.freeze('2026-09-15 13:00+09');

-- ① 문서 상태: 사용 중 = ACTIVE, 사용 중지 = INACTIVE, 없는 직원 = NULL
SELECT t.eq(fn_doc_status('APP_USER', 'U02'), 'ACTIVE', '사용 중 직원 = ACTIVE');
UPDATE app_user SET is_active = false WHERE user_id = 'U05';
SELECT t.eq(fn_doc_status('APP_USER', 'U05'), 'INACTIVE', '사용 중지 직원 = INACTIVE');
SELECT t.ok(fn_doc_status('APP_USER', 'U99') IS NULL, '없는 직원은 상태 없음');

-- ② 수정 이력: 사람 저장 v0 → v1, 잠기는 상태가 없어 사유 없이도 저장, 바뀐 칸 전·후
SELECT t.eq(fn_save_revision('APP_USER', 'U02', 'HUMAN', 'U12', NULL, 'ACTIVE', '{"user_id":"U02"}'::jsonb,
            '[{"field":"home_shift_type","before":"DAY","after":"NIGHT"}]'::jsonb), 0, '첫 배치 바꾸기 = v0');
SELECT t.eq(fn_save_revision('APP_USER', 'U02', 'HUMAN', 'U12', '야간 보강', 'ACTIVE', '{"user_id":"U02"}'::jsonb,
            '[{"field":"password","before":null,"after":"비밀번호 바꿈"}]'::jsonb), 1, '두 번째 = v1');
SELECT t.eq((SELECT count(*) FROM document_revision_change c JOIN document_revision r USING (revision_id)
              WHERE r.doc_type = 'APP_USER' AND r.doc_key = 'U02')::int, 2, '바뀐 칸 2줄');
SELECT t.throws($$INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, status_after, content_snapshot)
                  VALUES ('USER', 'U02', 9, 'HUMAN', 'U12', now(), 'ACTIVE', '{}')$$, 'document_revision_doc_type_check', '다른 종류 이름은 막힘');

-- ③ 권한: STAFF 보기·바꾸기는 MGR만
SELECT t.eq((SELECT string_agg(role_code || ':' || action, ',' ORDER BY role_code, action) FROM role_permission WHERE target = 'STAFF'),
            'MGR:EDIT,MGR:VIEW', 'STAFF = MGR만 (보기·바꾸기)');
SELECT t.eq((SELECT name_ko FROM code_label WHERE code_group = 'document_revision.doc_type' AND code = 'APP_USER'),
            '직원 배치 (직원 관리, 2026-10-25)', '코드 이름');

-- ④ 두 번째 담당 공정은 작업자만 (DB 제약 — 서버가 역할을 바꿀 때 먼저 비운다)
SELECT t.throws($$UPDATE app_user SET role_code = 'MNT' WHERE user_id = 'U01' AND home_process_code_2 IS NOT NULL$$,
                'ck_app_user_process_2', '두 번째 공정이 있는 작업자를 바로 보전으로 바꾸면 막힘');
ROLLBACK;
