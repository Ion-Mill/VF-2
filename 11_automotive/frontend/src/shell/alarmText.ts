// 알림 탭 알람 상세의 본문 문장 (프로그램이 만든 기본 문장, 2026-10-19). 비서(외부 LLM)가 다듬을 때 보내는 원문이자 [원문 보기]로 보이는 문장이다.
// React·데이터에 기대지 않는 순수 함수 — 시험: tools/alarm_text_check.mjs (예전 Eve.tsx 상세 본문과 글자 하나까지 같은지 대조한다).
export interface AlarmSentenceIn {
  name: string;                 // 설비 이름 (VF2-01)
  op: string;                   // 공정 (OP-30)
  code: string;                 // 알람 번호
  severity: 'STOP' | 'WARN' | 'GUIDE' | null;   // 알람 코드집의 심각도. 코드집에 없으면 null
  scenario: string | null;      // 사건 코드 (S1 …)
  lot: string | null;
  cleared: string | null;       // 설비 알람이 해제된 시각 "HH:MM" (해제 전이면 null)
}

export const alarmSentence = (a: AlarmSentenceIn): string =>
  `${a.name}(${a.op})에서 알람 ${a.code}` +
  (a.severity ? ` — ${a.severity === 'STOP' ? '정지' : a.severity === 'WARN' ? '주의' : '조작 안내'}` : ' — 알람 코드집에 없음, 보전 담당자 호출') + '.' +
  (a.scenario ? ` 사건 ${a.scenario}.` : '') +
  (a.lot ? ` 로트 ${a.lot}.` : '') +
  (a.cleared ? ` 설비 알람 ${a.cleared} 해제.` : '');
