// 알람 답 리치 카드 (채팅 탭 이브 말풍선) — 카드 안쪽은 Tailwind만 쓴다(.ma-* 변수 없음). 모양은 디자인 묶음 "알람 답변 리치 카드"(2026-10-19)를 따른다.
// 글자는 parseAlarmAnswer가 읽은 덩어리 목록을 순서대로 그릴 뿐 더하거나 빼지 않는다(cardPlainText와 같은 순서·같은 글자).
// 역할 알약 글자("작업자"/"보전")는 항상 그려서 색에만 기대지 않는다. "[가상]" 꼬리표는 지우지 않고 칩으로 그린다.
import { Fragment, useId, useState, type ReactNode } from 'react';
import type { AlarmAnswerCardProps, AlarmCardPart } from './parseAlarmAnswer';
import { ANSWER_BOX, HEADING, WRAP } from './bubbleBox';   // 말풍선 박스·소제목 클래스는 bubbleBox.ts 한 곳에서 정한다 (일반 답·질문·기록 항목과 같은 모양)

const Chip = ({ children }: { children: ReactNode }) =>
  <span className="mx-0.5 inline-block whitespace-nowrap rounded-full bg-slate-100 px-2 py-px align-middle text-[12px] font-medium text-slate-600">{children}</span>;
const H = ({ children, id }: { children: ReactNode; id: string }) =>
  <h3 id={id} className={HEADING}>{children}</h3>;

/** 글 속 "[가상]"·"[가상 운영 데이터]"를 칩으로 (나머지는 글자 그대로) */
const TAG = /(\[가상(?: 운영 데이터)?\])/;
const Inline = ({ text }: { text: string }) => (
  <>{text.split(TAG).map((s, i) => (i % 2 ? <Chip key={i}>{s.slice(1, -1)}</Chip> : <Fragment key={i}>{s}</Fragment>))}</>
);
const Paras = ({ paras, className = '' }: { paras: string[]; className?: string }) => (
  <>{paras.map((t, i) => <p key={i} className={`m-0 ${className}`}><Inline text={t} /></p>)}</>
);

function Part({ p, id, viewerRole }: { p: AlarmCardPart; id: string; viewerRole: 'operator' | 'maintenance' }) {
  switch (p.kind) {
    case 'desc':
      return (
        <section aria-labelledby={id} className="flex flex-col gap-2">
          <H id={id}><Inline text={p.title} /></H>
          <Paras paras={p.paras} />
        </section>
      );
    case 'steps':
      return (
        <section aria-labelledby={p.title ? id : undefined} className="flex flex-col gap-3">
          {p.title && <H id={id}><Inline text={p.title} /></H>}
          <ol className="m-0 flex list-none flex-col gap-3 p-0">
            {p.steps.map((s, i) => {
              const mine = s.role === viewerRole;
              return (
                <li key={i} className="flex items-start gap-2">
                  <span aria-label={`${s.no}단계`} className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-semibold ${s.no.length > 2 ? 'text-[12px]' : 'text-[15px]'} ${mine ? 'bg-violet-600 text-white' : 'bg-white text-slate-800 shadow-sm'}`}>{s.no}</span>
                  <p className="m-0 min-w-0 flex-1">
                    <span className={`mr-1.5 inline-block whitespace-nowrap rounded-lg px-2 py-0.5 text-[13px] font-semibold ${mine ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'}`}>{s.label}</span>
                    <Inline text={s.text} />
                  </p>
                </li>
              );
            })}
          </ol>
        </section>
      );
    case 'section':
      return (
        <section aria-labelledby={id} className="flex flex-col gap-2">
          <H id={id}><Inline text={p.title} /></H>
          <Paras paras={p.paras} className="text-[15px] text-slate-800" />
        </section>
      );
    case 'ops':
      return <p className="m-0">이 알람은 최근 <b>7일 {p.count7}번, 30일 {p.count30}번</b> 났습니다{p.virtual && <Chip>가상 운영 데이터</Chip>}</p>;
    case 'caution':
      return (
        <aside role="note" className="flex flex-col gap-1 rounded-2xl border border-orange-200 bg-orange-100 px-4 py-3 text-[15px]">
          <b className="text-orange-800">{p.title}</b>
          <Paras paras={p.paras} className="text-slate-800" />
        </aside>
      );
    default:
      return <div className="flex flex-col gap-2"><Paras paras={p.paras} className="text-[14px] text-slate-800" /></div>;
  }
}

/** 출처 — 일반 답 말풍선과 같은 밑줄 버튼. 가로 간격은 그대로(gap-x-1), 줄이 바뀔 때만 조금 넓힌다(gap-y-2). "출처"를 누르면 접고 편다(처음에는 펼침). */
function Sources({ sources }: { sources: AlarmAnswerCardProps['sources'] }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="flex flex-wrap items-baseline gap-x-1 gap-y-2 text-[12px]">
      <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-600">
        {open ? '▾ 출처:' : '▸ 출처'}
      </button>
      {open && sources.map((s, i) => (
        <button key={i} type="button" onClick={s.onClick} className="underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-600">
          {s.label} {s.docNo}{s.rev ? ` ${s.rev}` : ''} §{s.section}
        </button>
      ))}
    </div>
  );
}

export function AlarmAnswerCard({ parts, sources, viewerRole = 'operator' }: AlarmAnswerCardProps) {
  const uid = useId();   // 채팅에 알람 답이 여러 개 있어도 aria-labelledby id가 겹치지 않게
  return (
    <div className={`flex flex-col gap-3 whitespace-normal ${WRAP}`}>
      <div className={`flex flex-col gap-4 ${ANSWER_BOX}`}>
        {parts.map((p, i) => <Part key={i} p={p} id={`${uid}-${i}`} viewerRole={viewerRole} />)}
      </div>
      {sources.length > 0 && <Sources sources={sources} />}
    </div>
  );
}
