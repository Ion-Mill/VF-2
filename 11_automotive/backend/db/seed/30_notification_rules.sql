-- =====================================================================
-- 알림 규칙 처음 값 25행 (논리 ERD 6.36, 2026-10-13: WO_ASSIGNED·WO_DRAFT_READY·DAILY_REPORT_PENDING 추가)
--   규칙 코드·이름·조건·중요도·전달 방식 = 생성기 masters/notification_rule.csv 와 같은 글 (생성기 적재 때 그대로 덮어씀)
--   + 처리 방법(6.36 처리 표) + 받는 역할 + 보고 순위(6.43) — 물리 추가 칸
-- 기준 숫자는 DOC-07 10장 값만 (condition_text). 바꾸는 사람은 MGR (설정 화면)
-- 전달 방식 (2026-10-13): POPUP = ALARM_STOP 긴급 팝업 (받는 사람 = 로그인한 전원, 처리 책임은 그 설비 OPR·MNT) /
--   BUBBLE = 문서 알림 6종 (이브 말풍선) / LIST = 나머지 (이브 아이콘 숫자·사이드바 알림 탭)
-- rank_group: 같은 순위 안 묶음 순서 (6.43 순위 3의 ①~⑤ = 10~50, 순위 2 = 목표 미달 10·병목 20·납기 30)
-- =====================================================================
INSERT INTO notification_rule (rule_code, rule_name, condition_text, importance, delivery_kind, process_mode, processor_roles,
                               recipient_roles, report_rank, rank_group) VALUES
  ('ALARM_STOP', '알람 발생 (정지)', '정지 등급 알람 발생 → 로그인한 전원에게 중앙 팝업 (처리 책임은 그 설비 OPR·MNT)', 'URGENT', 'POPUP', 'AUTO', '{}', '{OPR,MNT,SUP,MGR}', 'R1', 0),
  ('ALARM_WARN', '알람 발생 (주의)', '주의 등급 알람 발생', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,MNT}', 'R3', 20),
  ('ALARM_GUIDE', '알람 발생 (조작 안내)', '조작 안내 등급 알람 발생', 'INFO', 'LIST', 'MANUAL', '{OPR,SUP}', '{OPR}', 'R4', 0),
  ('REPEAT_ALARM', '반복 알람 (1단계)', '같은 설비·같은 알람(주의·정지 등급)이 7일 안에 3번 이상 → MNT·SUP', 'CAUTION', 'LIST', 'MANUAL', '{MNT,SUP}', '{MNT,SUP}', 'R3', 11),
  ('REPEAT_ALARM_2', '반복 알람 2단계 (지난 조치 효과 없음)', '1단계 조치 계획을 저장한 뒤 7일 안에 같은 설비·같은 알람이 다시 남 → MNT·SUP', 'CAUTION', 'LIST', 'AUTO', '{}', '{MNT,SUP}', 'R3', 10),
  ('CAUSE_CHECK_REQUEST', '원인 점검 요청 (다른 공정)', '다른 공정의 반복 알람 2단계 → MNT에게 원인 점검 요청', 'CAUTION', 'LIST', 'AUTO', '{}', '{MNT}', 'R3', 10),
  ('TARGET_RISK', '목표 미달 위험', '예측 실적 < 총 목표(목표 + 이월)의 90%. 교대 시작 1시간 뒤부터 판단, 교대에 처음 1번', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 10),
  ('BOTTLENECK_MOVE', '병목 발생·이동', '병목 공정(또는 원인)이 바뀜. 관련 정보 = DOC-07 §7.5의 해당 원인 조치 줄', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 20),
  ('WIP_WARN', '재공 경고', '공정 사이 재공이 경고 기준(wip_buffer.warn_over_qty) 초과 — 20개, WIP-20-30은 한도 30 도달(OP-20 막힘). WIP-30-40 제외. 재공 위치마다 교대에 처음 1번', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 20),
  ('LOT_DUE_RISK', '로트 납기 지연 위험', '로트 예상 완료 시각 > 납기', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 30),
  ('STOCK_LOW', '재고 부족', '재고 수량 ≤ 안전 재고 → 그 품목의 관리 역할 + MGR', 'CAUTION', 'LIST', 'BOTH', '{MGR}', '{MGR}', 'R3', 40),
  ('PM_DUE_SOON', '예방 정비 기한 하루 전', '기한 하루 전 (주 1회 이상 주기 항목만 — 매일·교대 점검은 점검표)', 'INFO', 'LIST', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('PM_OVERDUE', '예방 정비 기한 넘김', '기한 넘김 (주 1회 이상 주기 항목만)', 'CAUTION', 'LIST', 'AUTO', '{}', '{MNT}', 'R3', 40),
  ('TOOL_LIFE_90', '공구 수명', '사용률 90%', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,MNT}', 'R3', 40),
  ('APPROVAL_WAIT_30M', '승인 대기', '작업지시서 승인 대기 30분 이상', 'INFO', 'BUBBLE', 'AUTO', '{}', '{SUP}', 'R4', 0),
  ('APPROVAL_WAIT_2H', '승인 대기', '작업지시서 승인 대기 2시간 이상', 'CAUTION', 'BUBBLE', 'AUTO', '{}', '{SUP}', 'R3', 50),
  ('WO_ASSIGNED', '작업지시서 배정', '작업지시서가 승인됨 → 담당 MNT', 'INFO', 'BUBBLE', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('WO_DRAFT_READY', '작업지시서 초안 검토', '작업지시서 AI비서 초안이 생길 때 → 그 설비 MNT', 'INFO', 'BUBBLE', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('DAILY_REPORT_PENDING', '일일 보고서 확정 요청', '일일 보고서 AI비서 초안이 생길 때 (야간 교대 보고서 확정 즉시, 늦어도 06:00) → MGR', 'INFO', 'BUBBLE', 'AUTO', '{}', '{MGR}', 'R4', 0),
  ('DOC_REVISED', '문서 수정', '작업지시서 수정 → 담당 보전원, 보고서 수정 → 관리자, 사내 문서 개정 → 관련 역할 전체', 'INFO', 'BUBBLE', 'AUTO', '{}', '{}', 'R4', 0),
  ('SPC_OUT', '관리도 이상', '점 1개가 +3σ 위 또는 −3σ 아래 → 반장', 'CAUTION', 'LIST', 'AUTO', '{}', '{SUP}', 'R3', 30),
  ('SHIFT_REPORT_PENDING', '교대 보고서 확정 요청', '교대 끝(주간 17:00, 야간 05:00) 교대 보고서 AI비서 초안이 생길 때 → 그 교대 반장', 'INFO', 'BUBBLE', 'AUTO', '{}', '{}', 'R4', 0),
  ('CMM_FILE_ERROR', 'CMM 결과 파일 오류', '결과 파일을 읽지 못함 또는 확인 필요 → 작업자·반장', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,SUP}', 'R3', 30),
  ('CMM_JUDGE_MISMATCH', 'CMM 판정 불일치', '측정기 판정 ≠ 플랫폼 판정 → 반장', 'CAUTION', 'LIST', 'AUTO', '{}', '{SUP}', 'R3', 30),
  ('CMM_NO_RESULT', 'CMM 결과 미수신', '측정 시작 뒤 정한 시간 안에 결과 파일이 오지 않음 → 작업자·반장 (시간은 [선택 필요: 기술 회의])', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,SUP}', 'R3', 30)
ON CONFLICT (rule_code) DO UPDATE SET rule_name = EXCLUDED.rule_name, condition_text = EXCLUDED.condition_text,
    importance = EXCLUDED.importance, delivery_kind = EXCLUDED.delivery_kind, process_mode = EXCLUDED.process_mode,
    processor_roles = EXCLUDED.processor_roles, recipient_roles = EXCLUDED.recipient_roles, report_rank = EXCLUDED.report_rank,
    rank_group = EXCLUDED.rank_group;

