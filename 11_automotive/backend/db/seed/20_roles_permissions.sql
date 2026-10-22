-- =====================================================================
-- 역할 (6.37)과 역할별 권한 (기획서 13.1 문서별·13.2 기능별 → role_permission)
-- target 이름 [제안]. 서버(app/security.py require())가 이 표로 막는다 (NFR-SEC-05).
-- MGR은 모든 기능·문서 조회 (R-76) — 맨 아래에서 VIEW를 한꺼번에 넣는다.
-- =====================================================================
INSERT INTO role (role_code, role_name) VALUES
  ('OPR', '현장 작업자'), ('MNT', '보전 담당자'), ('SUP', '라인 반장'), ('MGR', '공장 관리자')
ON CONFLICT (role_code) DO UPDATE SET role_name = EXCLUDED.role_name;

DELETE FROM role_permission;
INSERT INTO role_permission (role_code, target, action, scope) VALUES
-- ---- 13.1 문서별 ----
  ('OPR','GUIDE_CARD','VIEW','ALL'), ('MNT','GUIDE_CARD','VIEW','ALL'), ('SUP','GUIDE_CARD','VIEW','ALL'),
  ('OPR','WORK_ORDER','VIEW','ALL'),
  ('MNT','WORK_ORDER','VIEW','ALL'), ('MNT','WORK_ORDER','CREATE','ALL'), ('MNT','WORK_ORDER','EDIT','ALL'),
  ('SUP','WORK_ORDER','VIEW','ALL'), ('SUP','WORK_ORDER','ASSIGN','ALL'), ('SUP','WORK_ORDER','APPROVE','ALL'),
  -- 작업지시서 승인은 반장만. 관리자 대리 승인·취소는 두지 않음. 보기는 아래 R-76 VIEW.
  -- 작업기록서 (정식)
  ('MNT','WORK_RECORD','VIEW','ALL'), ('MNT','WORK_RECORD','CREATE','ALL'), ('MNT','WORK_RECORD','EDIT','ALL'),
  ('MNT','WORK_RECORD','CONFIRM','ALL'),
  ('SUP','WORK_RECORD','VIEW','ALL'), ('SUP','WORK_RECORD','CHECK','ALL'),
  -- 간이 작업기록: OPR은 주의 등급만 확정 (다른 공정 정지 등급·원인 점검은 MNT — DB 트리거가 다시 확인)
  ('OPR','WORK_RECORD_SIMPLE','VIEW','ALL'), ('OPR','WORK_RECORD_SIMPLE','CREATE','ALL'),
  ('OPR','WORK_RECORD_SIMPLE','EDIT','ALL'), ('OPR','WORK_RECORD_SIMPLE','CONFIRM','ALL'),
  ('MNT','WORK_RECORD_SIMPLE','VIEW','ALL'), ('MNT','WORK_RECORD_SIMPLE','CREATE','ALL'),
  ('MNT','WORK_RECORD_SIMPLE','EDIT','ALL'), ('MNT','WORK_RECORD_SIMPLE','CONFIRM','ALL'),
  ('SUP','WORK_RECORD_SIMPLE','VIEW','ALL'),
  -- 예방 정비 실시 기록 (OPR 없음 — 13.1 "—", 작업자가 한 항목은 MNT가 실시자로 골라 기록)
  ('MNT','PM_RECORD','VIEW','ALL'), ('MNT','PM_RECORD','CREATE','ALL'), ('MNT','PM_RECORD','EDIT','ALL'),
  ('MNT','PM_RECORD','CONFIRM','ALL'),
  ('SUP','PM_RECORD','VIEW','ALL'),
  -- 교대 보고서
  ('OPR','SHIFT_REPORT','VIEW','ALL'), ('MNT','SHIFT_REPORT','VIEW','ALL'),
  ('SUP','SHIFT_REPORT','VIEW','ALL'), ('SUP','SHIFT_REPORT','EDIT','ALL'), ('SUP','SHIFT_REPORT','CONFIRM','ALL'),
  -- 일일 보고서 (OPR 없음)
  ('MNT','DAILY_REPORT','VIEW','ALL'), ('SUP','DAILY_REPORT','VIEW','ALL'),
  ('MGR','DAILY_REPORT','EDIT','ALL'), ('MGR','DAILY_REPORT','CONFIRM','ALL'),
  -- 출하 기록
  ('OPR','SHIPMENT','VIEW','ALL'), ('MNT','SHIPMENT','VIEW','ALL'),
  ('SUP','SHIPMENT','VIEW','ALL'), ('SUP','SHIPMENT','CREATE','ALL'), ('SUP','SHIPMENT','EDIT','ALL'),
  ('SUP','SHIPMENT','CONFIRM','ALL'),
  -- 사내 문서 세트
  ('OPR','INTERNAL_DOC','VIEW','ALL'), ('MNT','INTERNAL_DOC','VIEW','ALL'), ('SUP','INTERNAL_DOC','VIEW','ALL'),
  ('MGR','INTERNAL_DOC','APPROVE','ALL'),
  -- 수정 이력 (OPR은 자기 문서만)
  ('OPR','REVISION_HISTORY','VIEW','OWN'), ('MNT','REVISION_HISTORY','VIEW','ALL'), ('SUP','REVISION_HISTORY','VIEW','ALL'),
-- ---- 13.2 기능별 ----
  ('OPR','FIELD_VIEW','VIEW','ALL'), ('MNT','FIELD_VIEW','VIEW','ALL'), ('SUP','FIELD_VIEW','VIEW','ALL'),
  ('OPR','LINE_VIEW','VIEW','ALL'), ('MNT','LINE_VIEW','VIEW','ALL'), ('SUP','LINE_VIEW','VIEW','ALL'),
  ('OPR','ASSISTANT','INPUT','ALL'), ('MNT','ASSISTANT','INPUT','ALL'), ('SUP','ASSISTANT','INPUT','ALL'),
  ('MGR','ASSISTANT','INPUT','ALL'),
  ('OPR','BRIEFING','VIEW','SUMMARY'), ('MNT','BRIEFING','VIEW','ALL'), ('SUP','BRIEFING','VIEW','ALL'),
  ('OPR','NOTIFICATION','VIEW','ALL'), ('MNT','NOTIFICATION','VIEW','ALL'), ('SUP','NOTIFICATION','VIEW','ALL'),
  ('OPR','DOWNTIME_REASON','VIEW','ALL'), ('OPR','DOWNTIME_REASON','INPUT','ALL'),
  ('MNT','DOWNTIME_REASON','VIEW','ALL'), ('MNT','DOWNTIME_REASON','INPUT','ALL'),
  ('SUP','DOWNTIME_REASON','VIEW','ALL'), ('SUP','DOWNTIME_REASON','CONFIRM','ALL'),
  ('SUP','LOT_TRACE','VIEW','ALL'), ('OPR','LOT_TRACE','VIEW','ALL'), ('MNT','LOT_TRACE','VIEW','ALL'),
  ('SUP','LOT_HOLD','INPUT','ALL'), ('MGR','LOT_HOLD','INPUT','ALL'),
  ('SUP','LOT_SCRAP','CREATE','ALL'), ('MGR','LOT_SCRAP','APPROVE','ALL'),
  ('OPR','INVENTORY','VIEW','ALL'), ('MNT','INVENTORY','VIEW','ALL'), ('SUP','INVENTORY','VIEW','ALL'),
  ('OPR','INV_USE','INPUT','OWNED_ITEMS'), ('MNT','INV_USE','INPUT','ALL'),
  ('MNT','INV_RECEIPT','INPUT','OWNED_ITEMS'), ('SUP','INV_RECEIPT','INPUT','OWNED_ITEMS'),
  ('SUP','MATERIAL_CHECK','INPUT','ALL'),
  ('MGR','SAFETY_STOCK','SETTING','ALL'),
  ('OPR','TOOL_CHANGE','INPUT','ALL'), ('MNT','TOOL_CHANGE','INPUT','ALL'),
  ('OPR','TOOL_LIFE','VIEW','ALL'), ('MNT','TOOL_LIFE','VIEW','ALL'), ('SUP','TOOL_LIFE','VIEW','ALL'),
  -- 예방 정비 일정은 전원 조회 (API명세서 PM-01 "전" — 현장 보기의 기한 넘김 표시)
  ('OPR','PM_SCHEDULE','VIEW','ALL'), ('MNT','PM_SCHEDULE','VIEW','ALL'), ('SUP','PM_SCHEDULE','VIEW','ALL'),
  -- 품질 조회는 전원 (API명세서 QLT-01·04·05 "전"). 입력은 측정 담당 작업자(OP-50 — 처리기가 담당 공정 확인)와 반장
  ('SUP','QUALITY','VIEW','ALL'), ('SUP','QUALITY','CHECK','ALL'), ('OPR','QUALITY','VIEW','ALL'),
  ('OPR','QUALITY','INPUT','ALL'), ('MNT','QUALITY','VIEW','ALL'),
  ('SUP','KPI','VIEW','ALL'), ('MNT','KPI','VIEW','ALL'), ('OPR','KPI','VIEW','ALL'),
  ('MGR','SETTINGS','SETTING','ALL'),
  ('SUP','PRODUCTION','VIEW','ALL'), ('SUP','PRODUCTION','INPUT','ALL'), ('OPR','PRODUCTION','VIEW','ALL'),
  ('OPR','PRODUCTION','INPUT','ALL'), ('MNT','PRODUCTION','VIEW','ALL');

-- R-76 MGR은 모든 기능·문서 조회
INSERT INTO role_permission (role_code, target, action, scope)
SELECT DISTINCT 'MGR', target, 'VIEW', 'ALL' FROM role_permission
ON CONFLICT DO NOTHING;
