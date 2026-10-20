// 채팅 말풍선·기록 항목의 박스 모양 — 한 군데에서만 정한다 (알람 카드·일반 답·기다리는 글·질문·기록 항목이 같은 둥근 박스).
// 이 창 안에서는 globals.css가 .bg-white·.bg-slate-*·.text-slate-400/500/700 을 덮어쓰므로, 박스 색에는 그 클래스를 쓰지 않는다(bg-white/80·violet 은 안전).
/** 줄바꿈: 한글은 단어 단위로 접고, 긴 영문·번호 한 덩어리가 박스를 넘치지 않게 */
export const WRAP = 'break-keep [overflow-wrap:anywhere]';
/** 답 안의 소제목(h3) — 알람 카드의 "알람 설명"·"점검 순서"와 일반 답의 "■ 제목"이 같은 모양 (2026-10-21) */
export const HEADING = 'm-0 text-[15px] font-bold text-violet-600';
/** 이브의 답 — 알람 카드 바깥 상자와 같다 */
export const ANSWER_BOX = 'rounded-3xl bg-white/80 p-5 text-[16px] leading-relaxed text-slate-900 shadow-sm';
/** 사용자의 질문 — 같은 모양에 보라 톤 + 얇은 테두리, 오른쪽 정렬 (질문 줄은 세로 목록 안이라 self-end) */
export const QUESTION_BOX = `self-end max-w-[82%] rounded-3xl border border-violet-200 bg-violet-100 px-5 py-3 text-[16px] leading-relaxed text-slate-900 shadow-sm whitespace-pre-wrap ${WRAP}`;
/** 채팅 기록 탭의 한 줄 — 답 박스와 같은 흰 바탕, 눌러서 여는 버튼이라 hover·포커스 표시가 있다 */
export const HISTORY_BOX = 'flex min-h-[56px] w-full flex-row items-center justify-between gap-3 rounded-3xl bg-white/80 p-4 text-left text-slate-900 shadow-sm hover:bg-violet-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-600';
