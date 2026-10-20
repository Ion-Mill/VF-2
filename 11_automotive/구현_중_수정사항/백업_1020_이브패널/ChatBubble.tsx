// 채팅 탭의 말풍선(질문 박스 + 답 박스)·기다리는 글·채팅 기록 탭 항목. Eve.tsx에서 옮겨 왔다 — 훅·시계에 기대지 않아 서버 렌더로 시험할 수 있다 (tools/chat_bubble_check.mjs).
import { AlarmAnswerCard } from './AlarmAnswerCard';
import { parseAlarmAnswer } from './parseAlarmAnswer';
import { ANSWER_BOX, HISTORY_BOX, QUESTION_BOX, WRAP } from './bubbleBox';

export interface ChatRow { at: string; q: string; a: string; status: string; sources: { doc_no: string; doc_name: string; rev: string; section: string }[]; series?: Record<string, Record<string, number[]>>; newChat?: boolean; chatId?: number }   // newChat = "여기서부터 새 대화" 표지 줄 (질문·답 없음, chatLog.ts). chatId = 서버 chat_log 번호 (백엔드 비서로 물은 줄만)

/** 질문 박스 → 날짜·상태 줄 → 답 박스(알람 답이면 카드, 아니면 평문 박스) → 출처 줄. meta = "10/1 10:00" 같은 날짜 글자(부르는 쪽이 만든다) */
export function Bubble({ r, meta, openSource, role }: { r: ChatRow; meta: string; openSource: (d: string, s: string) => void; role: string }) {
  const card = parseAlarmAnswer(r.a, r.sources, openSource);   // 알람 답("■ 알람 설명"으로 시작)이고 글자가 하나도 어긋나지 않을 때만 카드, 아니면 null → 평문 (parseAlarmAnswer.ts)
  return (
    <div className="flex flex-col gap-2">
      <div className={QUESTION_BOX}>{r.q}</div>
      <div className="text-[12px] text-slate-500">{meta} · 이브 · {r.status === 'ok' ? '규칙 답' : r.status}</div>
      {card ? <div className="ma-msg-bot"><AlarmAnswerCard {...card} viewerRole={role === 'OPR' ? 'operator' : 'maintenance'} /></div> : (   /* 카드: 보는 사람 역할의 점검 단계만 보라색 (OPR = 작업자 줄, 나머지 = 보전 줄) */
        <div className={ANSWER_BOX}>
          <p className={`ma-msg-bot ${WRAP}`}>{r.a}</p>
          {r.series && Object.entries(r.series).map(([eq, s]) => <div key={eq} className="mt-2 text-[12px]">{eq} 최근 60분: {Object.entries(s).slice(0, 3).map(([k, v]) => <span key={k} className="mr-2">{k} <Spark v={v} /></span>)}</div>)}
        </div>
      )}
      {!card && r.sources.length > 0 && <div className="flex flex-wrap gap-1 text-[12px]">출처: {r.sources.map((s, i) => <button key={i} type="button" onClick={() => openSource(s.doc_no, s.section)} className="underline">{s.doc_name} {s.doc_no} {s.rev} §{s.section}</button>)}</div>}
    </div>
  );
}

/** 답을 기다리는 동안 — 답이 오면 모양이 튀지 않게 같은 답 박스 */
export function Typing() {
  return <div className={ANSWER_BOX}><p className="ma-msg-bot ma-typing">답변을 만드는 중…</p></div>;
}

/** 채팅 기록 탭의 한 줄 (눌러서 그 대화를 채팅에서 다시 연다 — 그래서 버튼) */
export function HistoryItem({ q, when, onOpen }: { q: string; when: string; onOpen: () => void }) {
  return (
    <button type="button" className={HISTORY_BOX} onClick={onOpen}>
      <strong className={`text-[15px] font-bold ${WRAP}`}>{q}</strong>
      <span className="text-[12px] text-slate-600">{when}</span>
    </button>
  );
}

export function Spark({ v, w = 80, h = 18 }: { v: number[]; w?: number; h?: number }) {
  if (v.length < 2) return <span>—</span>;
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
  return <svg width={w} height={h} className="inline align-middle"><polyline fill="none" stroke="#7a52f0" strokeWidth="1.5" points={v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 1 - ((x - lo) / r) * (h - 2)}`).join(' ')} /></svg>;
}
