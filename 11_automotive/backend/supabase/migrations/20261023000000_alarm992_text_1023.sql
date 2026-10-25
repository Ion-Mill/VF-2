-- =====================================================================
-- 2026-10-23 알람 992 문구 — 이미 올린 mom-db에 바뀐 부분만 (글 3곳, 표·열은 그대로)
--   왜: 시연 S1 충돌이 108 → 994 → 992 세 건에서 정지 등급 992 한 건으로 바뀌어, 992 카드가 "바로 앞의 108·994"에 기대지 않게 고쳤다.
--   같은 내용이 원본에 있다: 생성기/masters/alarm_master.csv(992 쉬운 설명·연쇄 순서), 가상사내문서 DOC-03 §2.1 ★1 →
--   db/seed/50_alarm_check_steps.sql, db/seed/10_code_labels.sql (처음부터 만들 때는 이쪽으로 충분하다).
-- 스키마 주인(postgres)으로 한 번 (두 번 돌려도 같은 결과). 공용 mom-db에는 팀이 정한 한 사람이 올린다 (docs/05_결정기록.md).
-- 되돌리기: 아래 UPDATE의 글을 이전 값으로 (이전 글은 git 기록의 위 원본 파일에 있다).
-- =====================================================================
SET client_min_messages = warning;

UPDATE alarm_master
   SET easy_desc  = '서보 앰프가 모터에 너무 큰 전류가 흐르는 것을 감지했다. 공구 파손·무거운 절삭·충돌이 원인일 수 있다. 축 부하가 갑자기 오른 뒤에 뜨면 충돌을 먼저 의심한다',
       chain_rule = NULL
 WHERE alarm_code = '992';

UPDATE alarm_check_step
   SET step_text = '축을 움직이지 말고 알람 이력과 축 부하를 본다. 축 부하가 급하게 올랐으면 충돌 신호 (앞에 108·994가 있었다면 더 확실)'
 WHERE alarm_code = '992' AND seq = 1 AND step_kind = 'OPR';

UPDATE code_label
   SET name_ko = '충돌 의심 (메인, 고장) — VF2-01 992 충돌, 의심 로트(예시 LOT-2609-041-1) 보류'
 WHERE code_group = 'alarm_event.scenario_code' AND code = 'S1';
