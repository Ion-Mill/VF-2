// 교대 보고서 화면의 표시 규칙 (SCR-15) — 순수 함수라 화면 코드와 시험이 같은 파일을 쓴다 (2026-10-19).

export const NO_LOCKOUT = '잠금·표지 중인 설비 없음';

type HandoverGroup = { rank: string; name: string; items: string[] };

// [8] 인계 사항 머리의 "전체 N건" = 실제 항목 수.
// 순위 0의 "잠금·표지 중인 설비 없음"은 건수가 0일 때 보이는 문장이지 항목이 아니라서 세지 않는다 (브리핑 Briefing.tsx와 같은 규칙).
export const handoverCount = (hand: HandoverGroup[]): number =>
  hand.reduce((s, g) => s + g.items.filter((t) => !t.startsWith(NO_LOCKOUT)).length, 0);

// [7] 특이 사항 머리글. 서버가 비서가 다듬은 글에만 notable_source: 'ASSISTANT'를 붙인다(저장·확정으로 문장이 바뀌면 지움).
// 비서 글이고 아직 초안(AI_DRAFT)이면 "AI비서 초안", 그 밖에는 기존 글자.
export const notableHead = (r: { status?: string; notable_source?: string }): string =>
  r.notable_source === 'ASSISTANT' && r.status === 'AI_DRAFT'
    ? '[7] 특이 사항 (AI비서 초안 — 프로그램이 쓴 초안을 비서가 다듬은 문장)'
    : '[7] 특이 사항 (프로그램이 쓴 초안 — 비서가 켜져 있으면 비서가 다듬은 문장)';
