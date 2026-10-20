// 채팅 탭의 "새 채팅" — 지금 대화를 가르는 순수 함수 (React 없음 → tools/chat_log_check.mjs 로 시험).
//
// 채팅 기록(`chat:<사용자>`, 30일 보관, FR-MNT-01-01·NFR-DATA-13)은 **지우지 않는다**. 새 채팅을 누르면 기록 끝에 "여기서부터 새 대화" 표지 줄(질문·답이 빈 줄)만 더한다.
//  - 지금 대화 = 마지막 표지 뒤의 줄.            → 채팅 탭은 이것만 보인다.
//  - 질문·답이 있는 줄 = 표지를 뺀 줄.            → 채팅 기록 탭·"그날 대화 다시 보기"는 이것을 쓴다.
// 시각으로 가르지 않는다: 시연 시계가 멈추면(SIM.paused) 줄의 시각이 모두 같아질 수 있다. 표지 줄의 자리로 가른다.

/** 채팅 기록의 한 줄에서 표지 여부만 본다 (Eve.tsx의 ChatRow가 이 모양을 포함한다) */
export interface NewChatFlag { newChat?: boolean }

/** 질문·답이 비고 표지만 있는 줄을 만든다. 줄의 나머지 칸은 ChatRow 모양과 같게 채운다 */
export function makeNewChatMark(at: string): { at: string; q: string; a: string; status: string; sources: never[]; newChat: true } {
  return { at, q: '', a: '', status: '', sources: [], newChat: true };
}

const isMark = (r: NewChatFlag) => r.newChat === true;

/** 지금 대화: 마지막 표지 뒤의 줄. 표지가 없으면(옛 기록) 전체 */
export function currentChat<T extends NewChatFlag>(log: readonly T[]): T[] {
  let i = log.length - 1;
  while (i >= 0 && !isMark(log[i])) i--;
  return log.slice(i + 1);
}

/** 질문·답이 있는 줄만 (표지는 뺀다). 순서는 그대로 */
export function realRows<T extends NewChatFlag>(log: readonly T[]): T[] {
  return log.filter((r) => !isMark(r));
}

/**
 * [새 채팅] 버튼을 켤 때인가.
 * - 지금 대화에 줄이 있으면 켠다.
 * - 채팅 기록에서 열어 보는 중(viewingPast)이면 지금 대화가 비어 있어도 켠다 — 보기에서 빠져나와 빈 새 대화로 가야 하므로.
 * - 그 밖에(지금 대화가 비어 있음)는 끈다 — 비울 게 없고, 표지가 쌓이지 않게.
 */
export function canStartNewChat(log: readonly NewChatFlag[], viewingPast: boolean): boolean {
  return viewingPast || currentChat(log).length > 0;
}

/**
 * 새 채팅을 시작한 기록. 기록의 줄은 한 줄도 줄이지 않고 표지 하나만 끝에 더한다.
 * 맨 끝이 이미 표지면(지금 대화가 비어 있음) 더하지 않고 같은 배열을 돌려준다 — 두 번 눌러도 표지는 하나.
 * 원본 배열은 바꾸지 않는다.
 */
export function withNewChat<T extends NewChatFlag>(log: T[], mark: T, viewingPast: boolean): T[] {
  const last = log[log.length - 1];
  if (last && isMark(last)) return log;
  if (!canStartNewChat(log, viewingPast)) return log;
  return [...log, mark];
}

// ---------- 서버 채팅 기록과 합치기 (API-AST-02 GET, FR-MNT-01-01 "채팅 기록 탭에서 본인 것을 다시 본다") ----------
// 질문·답은 서버 chat_log에 사용자별로 저장된다. 이 브라우저 기록(위)은 그 사본 — 다른 PC·브라우저에서 물은 것은 서버에만 있다.

/** 서버 번호가 붙을 수 있는 줄 (Eve.tsx의 ChatRow·assistantApi.ts의 ServerChatRow가 이 모양을 포함한다) */
export interface LoggedRow extends NewChatFlag { at: string; q: string; a: string; chatId?: number }

/**
 * 채팅 기록 탭에 보일 줄 = 이 브라우저의 질문·답 줄 + 서버에만 있는 줄. 오래된 것부터 (시각이 같으면 이 브라우저 줄 먼저, 그다음 서버 순서).
 * - chat_id가 같은 줄은 이 브라우저 것을 쓴다 (화면에서 본 시각 그대로).
 * - chat_id가 없는 옛 브라우저 줄(이 기능 전)은 질문·답 글자가 같은 서버 줄 하나와 같은 것으로 본다 — 두 번 보이지 않게.
 * 표지 줄은 빠진다. 원본 배열은 바꾸지 않는다.
 */
export function mergeServerLog<T extends LoggedRow>(local: readonly T[], server: readonly T[]): T[] {
  const mine = realRows(local);
  const ids = new Set(mine.flatMap((r) => (typeof r.chatId === 'number' ? [r.chatId] : [])));
  const old = mine.filter((r) => typeof r.chatId !== 'number').map((r) => r.q + '\u0000' + r.a);
  const extra = server.filter((r) => {
    if (typeof r.chatId === 'number' && ids.has(r.chatId)) return false;
    const k = old.indexOf(r.q + '\u0000' + r.a);
    if (k < 0) return true;
    old.splice(k, 1);
    return false;
  });
  return [...mine, ...extra].map((r, i) => ({ r, i })).sort((x, y) => (Date.parse(x.r.at) - Date.parse(y.r.at)) || (x.i - y.i)).map((x) => x.r);
}

/** 이어서 물을 앞 질문의 서버 번호: 보이는 대화에서 번호가 있는 마지막 줄. 없으면 null (새 대화로 묻는다) */
export function lastChatId(rows: readonly LoggedRow[]): number | null {
  for (let i = rows.length - 1; i >= 0; i--) { const id = rows[i].chatId; if (typeof id === 'number') return id; }
  return null;
}
