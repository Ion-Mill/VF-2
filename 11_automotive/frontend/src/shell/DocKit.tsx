'use client';
// 문서 7종(지침카드·작업지시서·작업기록서·간이 작업기록·교대·일일 보고서·수정 이력)이 같이 쓰는 모양 부품.
// 결론 띠 → 칸 카드 → 접기 → 출처 순서. 색·굵기로만 강조한다 (디자인 통일은 팀 작업 뒤 — 2026-10-20 시안 기준).
import type { ReactNode } from 'react';
import { PAGE } from './ctx';

export type Tone = 'crit' | 'warn' | 'ok' | 'acc' | 'solid-crit' | 'solid-warn' | 'mute';
const CHIP: Record<Tone, string> = {
  crit: 'bg-[#fbe6e6] text-[#c22a2f]', warn: 'bg-[#fff1d1] text-[#8f5a00]', ok: 'bg-[#e0f2e8] text-[#127a46]', acc: 'bg-[#e3f3f7] text-[#0d7a93]',
  'solid-crit': 'bg-[#c22a2f] text-white', 'solid-warn': 'bg-[#8f5a00] text-white', mute: 'border border-slate-300 bg-slate-50 text-slate-600',
};
export function Chip({ tone = 'mute', mono, children }: { tone?: Tone; mono?: boolean; children: ReactNode }) {
  return <span className={`inline-flex min-h-[26px] items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[12.5px] font-semibold ${CHIP[tone]} ${mono ? 'font-mono' : ''}`}>{children}</span>;
}
export const RO = <Chip>보기 전용</Chip>;

// 문서 한 장의 틀
export function DocPage({ children, width = 920 }: { children: ReactNode; width?: number }) {
  return <div className={PAGE}><div className="mx-auto flex flex-col gap-3" style={{ maxWidth: width }}>{children}</div></div>;
}
export function DocHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <h2 className="text-[20px] font-bold">{title}</h2>
      {sub && <span className="text-[13px] text-slate-500">{sub}</span>}
      {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}
// 상태 단계 알약 (지금 단계 = 진하게)
export function Steps({ list, cur }: { list: string[]; cur: number }) {
  return <span className="flex flex-wrap gap-1">{list.map((s, i) => <span key={s} className={`rounded-full px-3 py-1 text-[13px] ${i === cur ? 'bg-[#1c2530] font-bold text-white' : i < cur ? 'bg-slate-200 text-slate-600' : 'border border-slate-300 text-slate-500'}`}>{s}</span>)}</span>;
}
export function InfoRow({ children, right }: { children?: ReactNode; right?: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2 text-[14px]">{children}{right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}</div>;
}
// 결론 띠: 이 문서의 핵심 한 줄 + 설명 + 칩 + 버튼
const BAND: Record<'crit' | 'warn' | 'ok' | 'mute', string> = {
  crit: 'border-[#e8b4b5] bg-[#fbe6e6]', warn: 'border-[#ecd29a] bg-[#fff6e0]', ok: 'border-transparent bg-[#e0f2e8]', mute: 'border-slate-300 bg-white',
};
export function Band({ tone, title, desc, chips, children }: { tone: keyof typeof BAND; title: ReactNode; desc?: ReactNode; chips?: ReactNode; children?: ReactNode }) {
  return (
    <section className={`flex flex-col gap-2 rounded-2xl border p-4 ${BAND[tone]}`}>
      <div className="text-[18px] font-bold leading-snug">{title}</div>
      {desc && <div className="text-[15px] leading-relaxed text-[#26303a]">{desc}</div>}
      {chips && <div className="flex flex-wrap items-center gap-1.5">{chips}</div>}
      {children}
    </section>
  );
}
// 칸 카드: 제목 + 오른쪽 칩 + 내용
export function Sec({ title, right, children }: { title: ReactNode; right?: ReactNode; children?: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-300 bg-white">
      <div className="flex flex-wrap items-center gap-2 px-4 py-3"><h3 className="text-[15px] font-bold">{title}</h3>{right && <div className="ml-auto flex flex-wrap items-center gap-1.5">{right}</div>}</div>
      {children !== undefined && children !== null && children !== false && <div className="px-4 pb-4">{children}</div>}
    </section>
  );
}
export function Fold({ summary, children, open }: { summary: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group rounded-2xl border border-slate-300 bg-white">
      <summary className="flex min-h-[48px] cursor-pointer list-none items-center gap-2 px-4 text-[14px] font-semibold text-slate-600"><span className="transition group-open:rotate-90">▸</span>{summary}</summary>
      <div className="px-4 pb-4 text-[14px]">{children}</div>
    </details>
  );
}
export function Kpi({ label, value, unit, sub, tone }: { label: ReactNode; value: ReactNode; unit?: ReactNode; sub?: ReactNode; tone?: 'main' | 'bad' | 'ok' }) {
  return (
    <div className={`flex min-w-0 flex-col rounded-xl border px-3 py-2 ${tone === 'main' ? 'border-transparent bg-[#0d7a93] text-white' : 'border-slate-300 bg-white'}`}>
      <span className={`text-[12.5px] ${tone === 'main' ? 'text-white/85' : 'text-slate-500'}`}>{label}</span>
      <span className={`font-mono text-[28px] font-semibold leading-tight tabular-nums ${tone === 'bad' ? 'text-[#c22a2f]' : tone === 'ok' ? 'text-[#127a46]' : ''}`}>{value}{unit && <small className={`ml-1 font-sans text-[13px] font-medium ${tone === 'main' ? 'text-white/85' : 'text-slate-500'}`}>{unit}</small>}</span>
      {sub && <span className={`text-[12px] ${tone === 'main' ? 'text-white/85' : 'text-slate-500'}`}>{sub}</span>}
    </div>
  );
}
export function Bar({ pct, tone, outline }: { pct: number; tone?: 'ok'; outline?: boolean }) {
  return <div className={`h-2.5 rounded-full bg-[#e6eaed] ${outline ? 'box-content border border-slate-400' : ''}`}><div className={`h-full rounded-full ${tone === 'ok' ? 'bg-[#127a46]' : 'bg-[#0d7a93]'}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>;
}
// 번호 목록 (큰 번호 동그라미)
export function NumList({ items, start = 1, big }: { items: string[]; start?: number; big?: boolean }) {
  return (
    <ol className="flex flex-col gap-2">{items.map((s, i) => (
      <li key={i} className={`grid grid-cols-[30px_minmax(0,1fr)] items-start gap-3 ${big ? 'text-[16px]' : 'text-[15px]'}`}>
        <span className={`flex h-[28px] w-[28px] items-center justify-center rounded-full font-mono text-[14px] font-bold ${big ? 'bg-[#0d7a93] text-white' : 'border border-slate-300 bg-white text-slate-700'}`}>{start + i}</span>
        <span className="pt-0.5 leading-relaxed">{s}</span>
      </li>))}</ol>
  );
}
// 맨 아래 버튼 줄
export function Acts({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-300 pt-3">{children}</div>;
}
export function SrcFold({ children }: { children: ReactNode }) {
  return <Fold summary="출처"><ul className="list-disc pl-5 text-[13px] text-slate-600">{children}</ul></Fold>;
}

// 보고서 글 한 줄(인계 사항·오늘의 문제): 서버 글의 정해진 모양만 칩·강조로 바꾸고, 모양이 안 맞는 줄(사람이 고친 줄)은 쓴 그대로
const NUM = /(LOT-\d{4}-\d{3}-\d|MW-\d{4})/;
function plain(x: string) {
  return x.split(NUM).map((p, i) => (NUM.test(p) ? <Chip key={i} mono>{p}</Chip> : p.includes('지난 조치 효과 없음')
    ? <span key={i}>{p.split('지난 조치 효과 없음').map((q, k) => <span key={k}>{k > 0 && <b className="text-[#c22a2f]">지난 조치 효과 없음</b>}{q}</span>)}</span> : <span key={i}>{p}</span>));
}
const LB = 'min-w-[64px] text-[13px] text-slate-500';
export function ReportLine({ text }: { text: string }) {
  let m: RegExpMatchArray | null;
  const row = (c: ReactNode) => <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px]">{c}</div>;
  if ((m = text.match(/^(\S+) 알람 (\d+) — (.*)$/))) return row(<><Chip mono>{m[1]} · {m[2]}</Chip><b className="text-[#c22a2f]">{m[3]}</b></>);
  if ((m = text.match(/^(.*?) 재고가 (안전 재고\(\d+\) 이하) \((.*)\)$/))) return row(<><Chip>{m[1]}</Chip><b className="text-[#8f5a00]">{m[2]}</b><span className="text-[12.5px] text-slate-500">{m[3]}</span></>);
  if ((m = text.match(/^(.*?)\s*로트 (LOT-[\d-]+(?:, LOT-[\d-]+)*)$/))) return row(<><span className={LB}>{m[1].replace(/ 중$/, '')}</span>{m[2].split(', ').map((l) => <Chip key={l} mono>{l}</Chip>)}</>);
  if ((m = text.match(/^(.*?) 작업지시서 (MW-\d+) \((.*)\)$/))) return row(<><span className={LB}>{m[1]}</span><Chip mono>{m[2]}</Chip><span>{m[3]}</span></>);
  return row(<span>{plain(text)}</span>);
}
// 같은 꼬리(" — 기한 하루 전 (기한 09/15)")가 붙은 줄은 꼬리를 한 번만 적고 앞부분만 칩으로
export function ReportLines({ items }: { items: string[] }) {
  const tails: Record<string, string[]> = {};
  items.forEach((x) => { const m = x.match(/^(.*) — (기한 .*)$/); if (m) (tails[m[2]] = tails[m[2]] ?? []).push(m[1]); });
  const rest = items.filter((x) => !/ — 기한 /.test(x));
  return (
    <div className="flex flex-col gap-1.5">
      {Object.entries(tails).map(([t, xs]) => <div key={t} className="flex flex-col gap-1"><span className="text-[13px] text-slate-500">{t}</span><div className="flex flex-wrap gap-1.5">{xs.map((x) => <Chip key={x}>{x}</Chip>)}</div></div>)}
      {rest.map((x) => <ReportLine key={x} text={x} />)}
    </div>
  );
}
// 순위 한 줄: 왼쪽 순위 칩, 오른쪽 내용
export function RankRow({ left, children }: { left: ReactNode; children: ReactNode }) {
  return <div className="grid grid-cols-1 items-start gap-2 border-t border-dashed border-slate-300 py-2.5 first:border-t-0 sm:grid-cols-[150px_minmax(0,1fr)]"><span className="flex flex-wrap gap-1">{left}</span><div className="min-w-0">{children}</div></div>;
}
