'use client';
// 문서 7종(지침카드·작업지시서·작업기록서·간이 작업기록·교대·일일 보고서·수정 이력)이 같이 쓰는 모양 부품.
// 결론 띠 → 칸 카드 → 접기 → 출처 순서. 화이트 카드 · 파스텔 블루(2026-10-21) 모양 — 새 화면은 ui.tsx 부품을 쓰고, 이 파일은 옮겨 가며 지운다.
import type { ReactNode } from 'react';
import { PAGE } from './ctx';
import { SecIcon } from './ui';

export type Tone = 'crit' | 'warn' | 'ok' | 'acc' | 'solid-crit' | 'solid-warn' | 'mute';
const CHIP: Record<Tone, string> = {
  crit: 'bg-crit-bg text-crit', warn: 'bg-warn-bg text-warn', ok: 'bg-ok-bg text-ok', acc: 'bg-info-bg text-info',
  'solid-crit': 'bg-crit-bg text-crit', 'solid-warn': 'bg-warn-bg text-warn', mute: 'border border-line bg-white text-ink-2', // 채운 칩 쓰지 않음 (옅은 바탕 태그)
};
export function Chip({ tone = 'mute', mono, field, children }: { tone?: Tone; mono?: boolean; field?: string; children: ReactNode }) {
  return <span data-summary-field={field} className={`inline-flex min-h-[26px] items-center gap-1 whitespace-nowrap rounded-[7px] px-2.5 text-small font-semibold ${CHIP[tone]} ${mono ? 'font-mono' : ''}`}>{children}</span>;
}
export const RO = <Chip>보기 전용</Chip>;

// 문서 한 장의 틀 — data-print: [인쇄] 때 이 틀만 종이에 남김 (globals.css @media print)
export function DocPage({ children, width = 960 }: { children: ReactNode; width?: number }) {
  return <div className={PAGE} data-print><div className="mx-auto flex flex-col gap-3" style={{ maxWidth: width }}>{children}</div></div>;
}
// [인쇄]: 문서를 폭 1000px(화면과 같은 칸 배치)로 놓고 A4 한 장(여백 10mm = 718 × 1047px)에 들어갈 배율을 재서 globals.css --print-zoom에 넣는다.
// 한 장에 넣으려면 55%보다 작아져야 하면 글자가 너무 작으니 폭만 맞추고 여러 장으로 (2026-10-23)
const PRINT_W = 1000, PAPER_W = 718, PAPER_H = 1047, MIN_ZOOM = 0.55;
export function printDoc() {
  const el = document.querySelector<HTMLElement>('[data-print] > div');
  if (el) {
    const old = el.style.cssText;
    el.style.maxWidth = 'none'; el.style.width = `${PRINT_W}px`;
    const h = el.scrollHeight * 1.03; // 쪽 나눔·글꼴 오차 여유
    el.style.cssText = old;
    const fit = Math.min(PAPER_W / PRINT_W, PAPER_H / h);
    document.documentElement.style.setProperty('--print-zoom', String(fit >= MIN_ZOOM ? fit : PAPER_W / PRINT_W));
  }
  window.print();
}
// printOnly: 제목 · 설명이 화면 머리(PageHead)와 겹치는 문서 — 화면에선 숨기고 인쇄(미리보기)에서만 보임. right는 늘 보임
export function DocHead({ title, sub, right, printOnly }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; printOnly?: boolean }) {
  return (
    <div className="flex flex-wrap items-end gap-x-3 gap-y-2 pt-2">
      <div className={`min-w-0 ${printOnly ? 'hidden print:block' : ''}`}><h2 className="text-[26px] font-bold leading-tight tracking-[-.02em]">{title}</h2>
        {sub && <div className="mt-0.5 text-small text-ink-2">{sub}</div>}</div>
      {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}
// 상태 단계 알약 (지금 단계 = 진하게)
export function Steps({ list, cur }: { list: string[]; cur: number }) {
  return <span className="flex flex-wrap gap-1">{list.map((s, i) => <span key={s} className={`rounded-full px-3 py-1 text-small ${i === cur ? 'bg-brand-tint font-bold text-brand-ink' : i < cur ? 'bg-track text-ink-2' : 'border border-line text-ink-2'}`}>{s}</span>)}</span>;
}
export function InfoRow({ children, right }: { children?: ReactNode; right?: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2 text-body">{children}{right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}</div>;
}
// 결론 띠 = 머리 카드: 흰 카드 + 왼쪽 상태 아이콘 칸(색은 여기만) + 핵심 한 줄 + 설명 + 칩 + 버튼
const BAND: Record<'crit' | 'warn' | 'ok' | 'mute', [string, string]> = {
  crit: ['bg-crit-bg text-crit', '⚠'], warn: ['bg-warn-bg text-warn', '▲'], ok: ['bg-ok-bg text-ok', '✓'], mute: ['bg-info-bg text-info', 'ⓘ'],
};
export function Band({ tone, title, desc, chips, children }: { tone: keyof typeof BAND; title: ReactNode; desc?: ReactNode; chips?: ReactNode; children?: ReactNode }) {
  return (
    <section className="flex items-start gap-4 rounded-card border border-line bg-white p-6 shadow-card">
      <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-ctl text-[20px] font-bold ${BAND[tone][0]}`} aria-hidden="true">{BAND[tone][1]}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="text-[22px] font-bold leading-snug tracking-[-.02em]">{title}</div>
        {desc && <div className="text-card text-ink-2">{desc}</div>}
        {chips && <div className="flex flex-wrap items-center gap-1.5">{chips}</div>}
        {children}
      </div>
    </section>
  );
}
// 칸 카드: 제목 + 오른쪽 칩 + 내용
export function Sec({ title, right, children, field }: { title: ReactNode; right?: ReactNode; children?: ReactNode; field?: string }) {
  return (
    <section className="rounded-card border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-center gap-2.5 px-5 py-4"><SecIcon title={title} /><h3 className="text-card font-bold" data-summary-field={field}>{title}</h3>{right && <div className="ml-auto flex flex-wrap items-center gap-1.5">{right}</div>}</div>
      {children !== undefined && children !== null && children !== false && <div className="px-5 pb-5">{children}</div>}
    </section>
  );
}
export function Fold({ summary, children, open }: { summary: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group rounded-card border border-line bg-white shadow-card">
      <summary className="flex min-h-[48px] cursor-pointer list-none items-center gap-2 px-5 text-body font-semibold text-info hover:bg-tile"><span className="transition group-open:rotate-90">▸</span>{summary}</summary>
      <div className="px-5 pb-5 text-body">{children}</div>
    </details>
  );
}
export function Kpi({ label, value, unit, sub, tone, field }: { label: ReactNode; value: ReactNode; unit?: ReactNode; sub?: ReactNode; tone?: 'main' | 'bad' | 'warn' | 'ok'; field?: string }) {
  return (
    <div data-summary-field={field} className="flex min-w-0 flex-col rounded-tile border border-line bg-white px-4 py-3">{/* 흰 칸 + 선 (main도 같은 칸, 강조는 결론 띠) */}
      <span className="text-small text-ink-2">{label}</span>
      <span className={`font-mono text-num font-bold tabular-nums ${tone === 'bad' ? 'text-crit' : tone === 'warn' ? 'text-warn' : tone === 'ok' ? 'text-ok' : 'text-ink'}`}>{value}{unit && <small className="ml-1 font-sans text-body font-normal text-ink-2">{unit}</small>}</span>
      {sub && <span className="text-small text-ink-2">{sub}</span>}
    </div>
  );
}
export function Bar({ pct, tone, outline }: { pct: number; tone?: 'ok'; outline?: boolean }) {
  return <div className={`h-1.5 rounded-[3px] bg-track ${outline ? 'box-content border border-line' : ''}`}><div className={`h-full rounded-[3px] ${tone === 'ok' ? 'bg-ok' : 'bg-brand-line'}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>;
}
// 번호 목록 (큰 번호 동그라미)
export function NumList({ items, start = 1, big }: { items: string[]; start?: number; big?: boolean }) {
  return (
    <ol className="flex flex-col gap-2">{items.map((s, i) => (
      <li key={i} className={`grid grid-cols-[30px_minmax(0,1fr)] items-start gap-3 ${big ? 'text-card' : 'text-card'}`}>
        <span className={`flex h-[28px] w-[28px] items-center justify-center rounded-full font-mono text-body font-bold ${big ? 'bg-brand-tint text-brand-ink' : 'border border-line bg-white text-ink'}`}>{start + i}</span>
        <span className="pt-0.5 leading-relaxed">{s}</span>
      </li>))}</ol>
  );
}
// 맨 아래 버튼 줄
export function Acts({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line pt-3">{children}</div>;
}
export function SrcFold({ children }: { children: ReactNode }) {
  return <Fold summary="출처"><ul className="list-disc pl-5 text-small text-ink-2">{children}</ul></Fold>;
}

// 보고서 글 한 줄(인계 사항·오늘의 문제): 서버 글의 정해진 모양만 칩·강조로 바꾸고, 모양이 안 맞는 줄(사람이 고친 줄)은 쓴 그대로
const NUM = /(LOT-\d{4}-\d{3}-\d|MW-\d{4})/;
function plain(x: string) {
  return x.split(NUM).map((p, i) => (NUM.test(p) ? <Chip key={i} mono>{p}</Chip> : p.includes('지난 조치 효과 없음')
    ? <span key={i}>{p.split('지난 조치 효과 없음').map((q, k) => <span key={k}>{k > 0 && <b className="text-crit">지난 조치 효과 없음</b>}{q}</span>)}</span> : <span key={i}>{p}</span>));
}
const LB = 'min-w-[64px] text-small text-ink-2';
export function ReportLine({ text }: { text: string }) {
  let m: RegExpMatchArray | null;
  const row = (c: ReactNode) => <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body">{c}</div>;
  if ((m = text.match(/^(\S+) 알람 (\d+) — (.*)$/))) return row(<><Chip mono>{m[1]} · {m[2]}</Chip><b className="text-crit">{m[3]}</b></>);
  if ((m = text.match(/^(.*?) 재고가 (안전 재고\(\d+\) 이하) \((.*)\)$/))) return row(<><Chip>{m[1]}</Chip><b className="text-warn">{m[2]}</b><span className="text-small text-ink-2">{m[3]}</span></>);
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
      {Object.entries(tails).map(([t, xs]) => <div key={t} className="flex flex-col gap-1"><span className="text-small text-ink-2">{t}</span><div className="flex flex-wrap gap-1.5">{xs.map((x) => <Chip key={x}>{x}</Chip>)}</div></div>)}
      {rest.map((x) => <ReportLine key={x} text={x} />)}
    </div>
  );
}
// 순위 한 줄: 왼쪽 순위 칩, 오른쪽 내용
export function RankRow({ left, children }: { left: ReactNode; children: ReactNode }) {
  return <div className="grid grid-cols-1 items-start gap-2 border-t border-dashed border-line py-2.5 first:border-t-0 sm:grid-cols-[150px_minmax(0,1fr)]"><span className="flex flex-wrap gap-1">{left}</span><div className="min-w-0">{children}</div></div>;
}
