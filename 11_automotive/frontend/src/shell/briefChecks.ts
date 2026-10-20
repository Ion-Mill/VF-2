// 브리핑 "먼저 챙길 일" 체크 저장의 순수 함수 (2026-10-20). 의존이 없어서 tools/brief_checks_check.mjs 가 Node로 그대로 시험한다.
// 체크는 ① 이 브라우저(localStorage, 시연 회차별 — live.ts usePersist)에 늘 남기고 ② 백엔드가 켜져 있으면(NEXT_PUBLIC_MOM_API) 같이 보낸다
// (POST·GET /api/assistant/briefing/checks). 백엔드 표가 없거나 꺼져 있으면 ①만으로 계속 동작한다.
// 백엔드는 항목 글자의 뜻을 모른다. 시연 "처음으로" 뒤 같은 교대 번호로 옛 체크가 되살아나지 않게 서버 글자 앞에 시연 회차 r<run_id>/ 를 붙인다.

export const SHIFT_MAX = 40;   // 백엔드 briefing_check.shift_id 길이
export const KEY_MAX = 120;    // 백엔드 briefing_check.item_key 길이

const clip = (s: string, n: number) => (s.length > n ? s.slice(0, n) : s);

/** 이 브라우저 저장소의 칸 이름: 사용자 + 교대 */
export const checkScope = (userId: string, shiftId: string) => `${userId}/${shiftId}`;

/** 서버로 보내는 교대 글자 */
export const serverShift = (runId: number | null, shiftId: string) => clip(`r${runId ?? 0}/${shiftId}`, SHIFT_MAX);
/** 서버로 보내는 항목 글자 */
export const serverKey = (runId: number | null, key: string) => clip(`r${runId ?? 0}/${key}`, KEY_MAX);

/** 서버가 돌려준 항목 글자 → 화면 항목 글자. 이 시연 회차(r<run_id>/)의 것만, 앞 글자를 떼고 돌려준다 */
export const fromServerKeys = (runId: number | null, keys: unknown): string[] => {
  const prefix = `r${runId ?? 0}/`;
  return Array.isArray(keys) ? keys.filter((k): k is string => typeof k === 'string' && k.startsWith(prefix) && k.length > prefix.length).map((k) => k.slice(prefix.length)) : [];
};

/** 체크 바꾸기: 있으면 빼고 없으면 더한다 (원래 목록은 안 건드림) */
export const toggleKey = (list: string[], key: string): string[] => (list.includes(key) ? list.filter((x) => x !== key) : [...list, key]);

/** 서버 목록 응답({items:[{item_key}]})에서 항목 글자만. 모양이 다르면 null (= 서버 값을 쓰지 않는다) */
export const itemKeysOf = (j: unknown): string[] | null => {
  const items = (j as { items?: unknown } | null)?.items;
  return Array.isArray(items) ? items.map((i) => (i as { item_key?: unknown })?.item_key).filter((k): k is string => typeof k === 'string') : null;
};
