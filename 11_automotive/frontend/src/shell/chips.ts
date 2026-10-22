// 채팅 첫머리 선택 말풍선(추천 질문, 최대 6개) — 순수 함수 (React 없음 → tools/chips_check.mjs 로 시험).
//
// 지침카드(또는 문서 > 지침카드 목록)를 연 채 이브 채팅을 열면, 그 알람 번호와 내 역할로 "지금 물어볼 만한" 질문을 만든다 (LLM 없이 프로그램이 정한 틀).
// 질문마다 알람 번호를 글자로 넣는다 — 서버가 "그 번호"를 규칙으로 바로 알아보므로 앞 대화에 기대지 않는다.
// 횟수("최근 몇 번 났어?")·지난 조치 말풍선은 어느 역할에도 두지 않는다 (2026-10-22). 채팅에 직접 적으면 예전의 조회 답은 그대로다.
// 작업자·반장 고정 말풍선의 "어제 주간 교대 보고서 작성됐어?"도 뺐다 (2026-10-22). 보전·관리자 고정 말풍선에는 원래 없었다.
// 작업자 고정 말풍선에서는 "병목 원인"·"확정 안 된 교대 보고서 있어?"도 어느 화면에서나 뺐다 (2026-10-22). 반장은 그 둘을 둔다. 보전에서는 보고서 확정 버튼을 빼고, 관리자는 둔다.
// "이 화면 설명해 줘"는 정보판 글자를 보내는 화면에서만 넣는다 (2026-10-22). 그 밖 화면에는 버튼이 없다.
// 누구에게나 같은 고정 문구(2075 알람 뭐야·잠금 표지 순서)는 뺐다 (사용자 지시 2026-10-21). 카드를 안 열었으면 역할별 고정 말풍선. 문구는 assistant/backend/tests/test_chip_routes.py 가 이 파일에서 읽어 규칙 길로 풀리는지 본다.

export const SCREEN_EXPLAIN = '이 화면 설명해 줘';
// 화면 이름(Eve의 screen). 정보판: line=SCR-04, card·cards=SCR-09, daily=SCR-16.
const EXPLAIN_SCREENS = new Set(['line', 'card', 'cards', 'daily']);

function withExplain(chips: string[], screen: string | null | undefined, at: number): string[] {
  if (!EXPLAIN_SCREENS.has(screen ?? '')) return chips;
  const out = chips.slice();
  out.splice(at, 0, SCREEN_EXPLAIN);
  return out;
}

/** 카드를 열지 않았을 때(또는 알람 번호를 모를 때)의 역할별 고정 말풍선. screen 이 정보판 화면일 때만 설명 버튼을 넣는다. */
export function defaultChips(role: string, screen?: string | null): string[] {
  if (role === 'OPR') return withExplain([], screen, 0);
  if (role === 'MNT') return withExplain(['VF2-01 MTTR 알려줘', 'VF2-01 센서 추세'], screen, 2);
  if (role === 'MGR') return withExplain(['VF2-01 MTTR 알려줘', 'VF2-01 센서 추세', '확정 안 된 교대 보고서 있어?'], screen, 2);
  return withExplain(['병목 원인', '확정 안 된 교대 보고서 있어?'], screen, 0);
}

// 알람 번호 모양: 3~5자리, 소수점 두 자리가 붙을 수 있다 (carry.ts 와 같은 모양). 그 밖의 글자는 말풍선 질문에 넣지 않는다
const CODE = /^\d{3,5}(?:\.\d{2})?$/;

/** role = OPR/SUP/MNT/MGR, onCard = 지금 화면이 지침카드(또는 지침카드 목록), alarmCode = 그 카드(목록이면 맨 위)의 알람 번호, screen = 지금 화면 이름 */
export function suggestChips(o: { role: string; onCard: boolean; alarmCode?: string | null; screen?: string | null }): string[] {
  const code = (o.alarmCode ?? '').trim();
  if (!o.onCard || !CODE.test(code)) return defaultChips(o.role, o.screen);
  const base = o.role === 'MNT'
    ? [`${code} 원인은`, `${code} 점검 순서`, '고전압 대기는 몇 분 기다려야 해?']
    : o.role === 'MGR'
      ? [`${code} 원인은`, `${code} 먼저 할 일`]
      : [`${code} 원인은`, `${code} 먼저 할 일`, `${code} 내가 해야 할 일`];
  return withExplain(base, o.screen, base.length);
}
