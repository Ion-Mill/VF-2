// 비서 답의 상태 이름 (React·네트워크 없음 → carry.ts 와 tools/carry_check.mjs 가 그대로 불러 쓴다).
// assistantApi.ts 에서 옮겨 왔다 — carry.ts 가 이 표를 읽고, assistantApi.ts 는 carry.ts 를 부르므로, 한쪽이 다른 쪽을 부르는 고리가 되지 않게 따로 뒀다. assistantApi.ts 가 그대로 다시 내보낸다.

// 백엔드 상태 코드 → 화면에 보이는 말 (API명세서 AST-02: ok / 문서에 없음 / 거부 / 권한 밖 / 응답 없음). 표에 없는 값은 "응답 없음"으로 — 원문을 내보내지 않는다.
export const STATUS_KO: Record<string, string> = { OK: '답변', NOT_IN_DOCS: '문서에 없음', OUT_OF_ROLE: '권한 밖', REFUSED: '거부', NO_RESPONSE: '응답 없음' };
