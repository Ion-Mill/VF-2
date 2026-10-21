// 채팅 첫머리 선택 말풍선(추천 질문) — 순수 함수 (React 없음 → tools/chips_check.mjs 로 시험).
//
// 지침카드를 열어 둔 채 이브 채팅을 열면, 그 카드의 알람 번호와 내 역할로 "지금 물어볼 만한" 질문을 만든다 (LLM 없이 프로그램이 정한 틀).
// 질문마다 알람 번호를 글자로 넣는다 — 서버가 "그 번호"를 규칙으로 바로 알아보므로 앞 대화에 기대지 않는다. 카드를 열지 않았으면 예전 고정 말풍선 그대로.

/** 카드를 열지 않았을 때(또는 알람 번호를 모를 때)의 예전 고정 말풍선 */
export function defaultChips(role: string): string[] {
  return role === 'MNT' || role === 'MGR'
    ? ['VF2-01 MTTR 알려줘', 'VF2-01 센서 추세', '2075 알람 뭐야', '이 화면 설명해 줘']
    : ['2075 알람 뭐야', '잠금 표지 순서', '이 화면 설명해 줘', '병목 원인'];
}

// 알람 번호 모양: 3~5자리, 소수점 두 자리가 붙을 수 있다 (carry.ts 와 같은 모양). 그 밖의 글자는 말풍선 질문에 넣지 않는다
const CODE = /^\d{3,5}(?:\.\d{2})?$/;

/** role = OPR/SUP/MNT/MGR, onCard = 지금 화면이 지침카드, alarmCode = 그 카드의 알람 번호 */
export function suggestChips(o: { role: string; onCard: boolean; alarmCode?: string | null }): string[] {
  const code = (o.alarmCode ?? '').trim();
  if (!o.onCard || !CODE.test(code)) return defaultChips(o.role);
  switch (o.role) {
    case 'MNT': return [`${code} 원인은`, `${code} 점검 순서`, `${code} 지난 조치`, '잠금 표지 순서'];
    case 'SUP': return [`${code} 원인은`, `${code} 먼저 할 일`, `${code} 내가 해야 할 일`, `${code} 지난 조치`];
    case 'MGR': return [`${code} 원인은`, `${code} 먼저 할 일`, `${code} 지난 조치`, '이 화면 설명해 줘'];
    default: return [`${code} 원인은`, `${code} 먼저 할 일`, `${code} 내가 해야 할 일`, '잠금 표지 순서'];
  }
}
