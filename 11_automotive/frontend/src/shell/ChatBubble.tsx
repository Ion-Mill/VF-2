// 채팅 탭의 말풍선(질문 박스 + 답 박스)·기다리는 글·채팅 기록 탭 항목. Eve.tsx에서 옮겨 왔다 — 훅·시계에 기대지 않아 서버 렌더로 시험할 수 있다 (tools/chat_bubble_check.mjs).
import { useId, useState } from 'react';
import { AlarmAnswerCard } from './AlarmAnswerCard';
import { parseAlarmAnswer } from './parseAlarmAnswer';
import { parsePlainAnswer, type PlainSection } from './parsePlainAnswer';
import { ANSWER_BOX, HEADING, HISTORY_BOX, QUESTION_BOX, WRAP } from './bubbleBox';

export interface ChatRow { at: string; q: string; a: string; status: string; sources: { doc_no: string; doc_name: string; rev: string; section: string }[]; series?: Record<string, Record<string, number[]>>; newChat?: boolean; chatId?: number; prevChatId?: number | null; pending?: boolean; sentAt?: number }   // newChat = "여기서부터 새 대화" 표지 줄 (질문·답 없음, chatLog.ts). chatId = 서버 chat_log 번호 (백엔드 비서로 물은 줄만). pending = 보냈지만 답이 아직 안 온 줄(질문만 보임, sentAt = 보낸 시각 ms — 새로고침에 끊겨도 되살린다, chatLog.ts)

/** 채팅 답 아래에 프로그램이 그대로 붙이는 안전 고정 서식의 소제목 (비서 safety/templates.py TITLE). 이 덩어리는 처음에 접어 둔다 — 글자는 지우지 않고 제목 줄을 눌러 펼친다 */
export const FIXED_TITLE = '안전 작업 (고정 서식';
/** 접는 글 = 소제목 아래 첫 문단(서식 줄·근거·출처). 빈 줄 뒤의 글("주의: 근거 안내이며 실행 지시가 아닙니다 …")은 접지 않고 늘 보인다 */
export function splitFixedBody(body: string): { fold: string; rest: string } {
  const m = /\n[ \t]*\n/.exec(body);
  return m ? { fold: body.slice(0, m.index), rest: body.slice(m.index + m[0].length) } : { fold: body, rest: '' };
}

/** 접는 안전 고정 서식 — 제목 줄(알람 카드·일반 답 소제목과 같은 보라색)이 버튼, ▸ 접힘 / ▾ 펼침. defaultOpen은 시험용 */
export function FixedFold({ title, fold, rest, defaultOpen = false }: { title: string; fold: string; rest: string; defaultOpen?: boolean }) {
  const uid = useId();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section aria-labelledby={`${uid}-h`} className="flex flex-col gap-2">
      <h3 id={`${uid}-h`} className={HEADING}>
        <button type="button" aria-expanded={open} aria-controls={`${uid}-b`} onClick={() => setOpen((v) => !v)} className="cursor-pointer text-left font-bold focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-600">
          {open ? '▾ ' : '▸ '}{title}
        </button>
      </h3>
      <div id={`${uid}-b`} hidden={!open} className="flex flex-col gap-2">{open && fold !== '' && <p className={`ma-msg-bot ${WRAP}`}>{fold}</p>}</div>
      {rest !== '' && <p className={`ma-msg-bot ${WRAP}`}>{rest}</p>}
    </section>
  );
}

/** 일반 답의 "■ 제목" 덩어리 — 제목은 알람 카드와 같은 보라색 굵은 소제목(■ 기호는 그리지 않는다), 아래 글은 줄바꿈 그대로. 안전 고정 서식 덩어리는 접는다(FixedFold) */
function PlainAnswer({ sections }: { sections: PlainSection[] }) {
  const uid = useId();
  return (
    <div className="flex flex-col gap-4">
      {sections.map((s, i) => s.title === null
        ? <p key={i} className={`ma-msg-bot ${WRAP}`}>{s.body}</p>
        : s.title.startsWith(FIXED_TITLE)
        ? <FixedFold key={i} title={s.title} {...splitFixedBody(s.body)} />
        : (
          <section key={i} aria-labelledby={`${uid}-${i}`} className="flex flex-col gap-2">
            <h3 id={`${uid}-${i}`} className={HEADING}>{s.title}</h3>
            {s.body !== '' && <p className={`ma-msg-bot ${WRAP}`}>{s.body}</p>}
          </section>
        ))}
    </div>
  );
}

/** 질문 박스 → 날짜·상태 줄 → 답 박스(알람 답이면 카드, "■ 제목"이 있으면 제목+글, 아니면 평문 박스) → 출처 줄. meta = "10/1 10:00" 같은 날짜 글자(부르는 쪽이 만든다) */
export function Bubble({ r, meta, openSource, role }: { r: ChatRow; meta: string; openSource: (d: string, s: string) => void; role: string }) {
  if (r.pending) return <div className="flex flex-col gap-2"><div className={QUESTION_BOX}>{r.q}</div></div>;   // 답이 아직 안 온 줄: 질문만 (아래에 "생각 중"이 이어진다)
  const card = parseAlarmAnswer(r.a, r.sources, openSource);   // 알람 답("■ 알람 설명"으로 시작)이고 글자가 하나도 어긋나지 않을 때만 카드, 아니면 null → 평문 (parseAlarmAnswer.ts)
  const plain = card ? null : parsePlainAnswer(r.a);            // 카드가 아닌 답의 "■ 제목" 줄 → 소제목 (없으면 null → 예전과 같은 평문 한 덩어리, parsePlainAnswer.ts)
  return (
    <div className="flex flex-col gap-2">
      <div className={QUESTION_BOX}>{r.q}</div>
      <div className="text-[12px] text-slate-500">{meta} · 이브 · {r.status === 'ok' ? '규칙 답' : r.status}</div>
      {card ? <div className="ma-msg-bot"><AlarmAnswerCard {...card} viewerRole={role === 'OPR' ? 'operator' : 'maintenance'} /></div> : (   /* 카드: 보는 사람 역할의 점검 단계만 보라색 (OPR = 작업자 줄, 나머지 = 보전 줄) */
        <div className={ANSWER_BOX}>
          {plain ? <PlainAnswer sections={plain} /> : <p className={`ma-msg-bot ${WRAP}`}>{r.a}</p>}
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

/** 채팅 기록 탭의 한 줄 (눌러서 그 대화를 채팅에서 다시 연다 — 그래서 버튼). G안: 왼쪽 질문 · 오른쪽 시각 (2026-10-20) */
export function HistoryItem({ q, when, onOpen }: { q: string; when: string; onOpen: () => void }) {
  return (
    <button type="button" className={HISTORY_BOX} onClick={onOpen}>
      <strong className={`min-w-0 flex-1 text-[16px] font-bold leading-snug ${WRAP}`}>{q}</strong>
      <span className="shrink-0 font-mono text-[14px] text-slate-600">{when}</span>
    </button>
  );
}

export function Spark({ v, w = 80, h = 18 }: { v: number[]; w?: number; h?: number }) {
  if (v.length < 2) return <span>—</span>;
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
  return <svg width={w} height={h} className="inline align-middle"><polyline fill="none" stroke="#7a52f0" strokeWidth="1.5" points={v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 1 - ((x - lo) / r) * (h - 2)}`).join(' ')} /></svg>;
}
