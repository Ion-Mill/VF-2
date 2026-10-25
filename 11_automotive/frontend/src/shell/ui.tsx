'use client';
// 화이트 카드 · 파스텔 블루 (2026-10-21, 디자인 통일 C안을 바꿈) — 모든 화면이 같이 쓰는 부품. DocKit.tsx를 넓힌 것.
// 규칙: 카드는 흰색 + 얇은 선 + 아주 옅은 그림자, 색은 아이콘 칸 · 태그에만, 고른 것 = 옅은 파랑, 꽉 찬 파랑 = 주 버튼.
// 화면 뼈대: <Page> 안에 <PageHead> → <Band> 1개 → <Sec> 카드들(필요하면 <Fold>로 접기).
// 색 · 글자 · 모서리는 tailwind.config.ts 토큰 이름만 쓴다. 규칙: 캔버스 "C안 규칙 1~4", 구현명세서.md
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { useState } from 'react';
import type { BandSpec, BandTone } from './bands';

// ---------- 화면 틀 ----------
/** 목록 · 현황 = 꽉 채움(최대 1440), 문서 한 장(보고서 · 작업지시서 · 작업기록서 · 지침카드) = doc → 가운데 960 */
export function Page({ doc, children }: { doc?: boolean; children: ReactNode }) {
  return (
    <div className="absolute inset-0 overflow-y-auto bg-ground p-4">
      <div className={`mx-auto flex flex-col gap-4 ${doc ? 'max-w-[960px]' : 'max-w-[1440px]'}`}>{children}</div>
    </div>
  );
}

/** 뒤로가기 동그란 ← (시안 A, 사용자 선택 2026-10-23) — 바로 전 화면, 기록이 없으면 홈 (App.tsx back) */
export function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label="뒤로" title="뒤로"
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line bg-white text-ink shadow-[0_1px_3px_rgba(27,42,65,.08)] hover:border-brand-line hover:text-brand-ink">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
    </button>
  );
}

/** 화면 머리 (통일안, 사용자 선택 2026-10-24): [←] · 작은 묶음 이름 → 제목 26 굵게 → 부제 한 줄 · 오른쪽 = 같은 묶음 탭 또는 화면 전체 버튼.
 *  글자는 px로 고정 — 재고 · 문서 묶음의 .fs-up(글자 한 단계 크게)이 머리까지 키우지 않게 */
export function PageHead({ title, sub, right, onBack, group }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; onBack?: () => void; group?: ReactNode }) {
  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-2 pt-2">
      {onBack && <BackButton onClick={onBack} />}
      <div className="min-w-0">
        {group && <div className="flex items-center gap-1.5 text-[14px] font-semibold text-ink-2">{group}</div>}
        <h2 className="text-[26px] font-bold leading-tight tracking-[-.02em] text-ink">{title}</h2>
        {sub && <div className="mt-0.5 text-[15px] text-ink-2">{sub}</div>}</div>
      {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

// ---------- 카드 머리 아이콘 ----------
// 제목 낱말로 아이콘을 고른다 (화면마다 아이콘을 넘기지 않아도 되게). 모르는 제목 = 목록 아이콘
const ICON: Record<string, string> = {
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', box: '<path d="M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8"/>',
  cal: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>', list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  ruler: '<path d="M3 17 17 3l4 4L7 21zM7 13l2 2M10 10l2 2M13 7l2 2"/>', chart: '<path d="M3 3v18h18M7 15l4-4 3 3 5-6"/>',
  alert: '<path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>',
  hist: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/>', check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  doc: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5M9 13h6M9 17h6"/>', bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21h4"/>',
  line: '<path d="M2 20h20M4 20V9l5 3V9l5 3V5h6v15"/>', shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>', user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"/>',
};
const ICON_WORD: [string, string][] = [['시간표', 'clock'], ['타임라인', 'clock'], ['달력', 'cal'], ['기한', 'cal'], ['일정', 'cal'], ['지도', 'grid'], ['공차', 'ruler'], ['측정', 'ruler'], ['관리도', 'chart'], ['추이', 'chart'], ['그래프', 'chart'], ['불량', 'alert'], ['알람', 'alert'], ['고장', 'alert'], ['공구', 'tool'], ['정비', 'tool'], ['조치', 'tool'], ['이력', 'hist'], ['기록', 'hist'], ['할 일', 'check'], ['확인', 'check'], ['점검', 'check'], ['판정', 'check'], ['재고', 'box'], ['수량', 'box'], ['완제품', 'box'], ['입고', 'box'], ['출하', 'box'], ['부품', 'box'], ['보류', 'lock'], ['폐기', 'lock'], ['안전', 'shield'], ['강화', 'shield'], ['잠금', 'shield'], ['문서', 'doc'], ['보고', 'doc'], ['작업지시', 'doc'], ['출처', 'doc'], ['지침', 'bell'], ['알림', 'bell'], ['라인', 'line'], ['생산', 'line'], ['설비', 'gear'], ['사용자', 'user'], ['담당', 'user'], ['인계', 'user']];
const textOf = (n: ReactNode): string => (typeof n === 'string' || typeof n === 'number' ? String(n) : Array.isArray(n) ? n.map(textOf).join('')
  : n && typeof n === 'object' && 'props' in n ? textOf((n as { props: { children?: ReactNode } }).props.children) : '');
/** 카드 제목 앞 옅은 파랑 아이콘 칸 (36 · 모서리 10) */
export function SecIcon({ title, size = 36 }: { title: ReactNode; size?: number }) {
  const t = textOf(title), k = (ICON_WORD.find(([w]) => t.includes(w)) ?? ['', 'list'])[1];
  return (
    <span className="inline-flex shrink-0 items-center justify-center rounded-ctl bg-brand-tint text-brand" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={size / 2} height={size / 2} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: ICON[k] }} />
    </span>
  );
}

// ---------- 결론 띠 = 머리 카드 ----------
// 흰 카드 위에 큰 상태 태그(색은 여기만) → 굵은 결론 한 줄 → 회색 설명 → 근거 칩, 오른쪽에 주 버튼(꽉 찬 파랑) 하나
export const TONE_TAG: Record<BandTone, string> = {
  crit: 'bg-crit-bg text-crit', warn: 'bg-warn-bg text-warn', ok: 'bg-ok-bg text-ok', todo: 'bg-brand-tint text-brand-ink', draft: 'bg-brand-tint text-brand-ink',
};
const TONE_WORD: Record<BandTone, string> = { crit: '긴급', warn: '주의', ok: '정상', todo: '할 일', draft: 'AI비서 초안' };
/** 큰 상태 태그 (높이 40 · 17 굵게 · 점) */
export function ToneTag({ tone, children }: { tone: BandTone; children: ReactNode }) {
  return <span className={`inline-flex h-10 w-fit items-center gap-2 whitespace-nowrap rounded-ctl px-4 text-card font-bold ${TONE_TAG[tone]}`}><i className="h-2.5 w-2.5 rounded-full bg-current" />{children}</span>;
}

/** 결론 띠: 화면마다 1개, 화면 머리 바로 아래. 내용은 bands.ts가 만든 BandSpec 그대로 */
export function Band({ spec, onAction, actionDisabled }: { spec: BandSpec; onAction?: () => void; actionDisabled?: boolean }) {
  return (
    <section className={`flex flex-wrap items-start gap-x-6 gap-y-3 rounded-card border bg-white p-6 shadow-card ${spec.tone === 'draft' ? 'border-dashed border-ink-3' : 'border-line'}`}>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <ToneTag tone={spec.tone}>{spec.tone === 'draft' ? spec.draftLabel ?? TONE_WORD.draft : TONE_WORD[spec.tone]}</ToneTag>
        <span className="mt-1 text-[24px] font-bold leading-snug tracking-[-.02em] text-ink">{spec.title}</span>
        {spec.desc && <div className="text-card text-ink-2">{spec.desc}</div>}
        {!!spec.chips?.length && <div className="flex flex-wrap gap-1.5">{spec.chips.slice(0, 4).map((c) => <Chip key={c} tone="outline">{c}</Chip>)}{spec.chips.length > 4 && <Chip tone="outline">외 {spec.chips.length - 4}건</Chip>}</div>}
      </div>
      {spec.action && onAction && <Btn kind="primary" lock={spec.actionLock} onClick={onAction} disabled={actionDisabled}>{spec.action}</Btn>}
    </section>
  );
}

/** 불러오는 중에는 띠 자리도 먼저 그린다 (늦게 떠서 화면이 밀리지 않게) */
export function BandSkeleton() {
  return <div className="flex h-[132px] flex-col justify-center gap-3 rounded-card border border-line bg-white px-6 shadow-card"><div className="h-8 w-24 rounded-ctl bg-track" /><div className="h-5 w-1/2 rounded bg-track" /><div className="h-3 w-1/3 rounded bg-line-soft" /></div>;
}

// ---------- 칸 카드 · 접기 ----------
/** 흰 카드 · 선 1px · 모서리 16 · 아주 옅은 그림자 · 제목 앞 아이콘 칸 + 제목 17 굵게 + 오른쪽 칩. empty면 카드째 접고 제목 옆에 "없음" */
export function Sec({ title, sub, right, empty, children }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; empty?: boolean; children?: ReactNode }) {
  return (
    <section className="rounded-card border border-line bg-white shadow-card">
      <div className="flex min-h-12 flex-wrap items-center gap-2.5 px-5 py-4">
        <SecIcon title={title} />
        <h3 className="text-card font-bold text-ink">{title}</h3>
        {sub && <span className="text-small text-ink-2">{sub}</span>}
        {empty && <span className="text-body text-ink-2">없음</span>}
        {right && <div className="ml-auto flex flex-wrap items-center gap-1.5">{right}</div>}
      </div>
      {!empty && children != null && children !== false && <div className="px-5 pb-5">{children}</div>}
    </section>
  );
}

/** 접기 줄: 카드 맨 아래, 높이 44. 무엇이 몇 개 숨었는지 적는다 ("나머지 5건", "WSH-01 · CMM-01") */
export function Fold({ summary, defaultOpen = false, children }: { summary: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="-mx-5 -mb-5 mt-3 border-t border-line-soft">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex h-11 w-full items-center gap-2 px-5 text-left text-body font-semibold text-info hover:bg-tile">
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>{summary} {open ? '접기' : '펼치기'}
      </button>
      {open && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}

// ---------- 버튼 · 입력 ----------
type BtnKind = 'primary' | 'normal' | 'dark';
const BTN: Record<BtnKind, string> = {
  primary: 'bg-brand text-white hover:bg-brand-ink',                // 꽉 찬 파랑 = 화면의 주 버튼 (결론 띠의 할 일 · 찾기 · 저장)
  normal: 'border border-line bg-white text-ink hover:border-brand-line hover:text-brand-ink', // 대부분 (보류 · 폐기도 + 확인 상자)
  dark: 'bg-brand text-white hover:bg-brand-ink',                   // 확정 · 승인 (예전 차콜 → 주 버튼과 같은 파랑)
};
/** 높이 44 · 모서리 10 · 14/600. 비활성은 회색 + 옆에 이유 글자(disabledReason) */
export function Btn({ kind = 'normal', lock, disabledReason, className = '', children, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: BtnKind; lock?: boolean; disabledReason?: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <button {...p} className={`inline-flex h-11 shrink-0 items-center gap-1.5 rounded-ctl px-4 text-body font-semibold disabled:cursor-not-allowed disabled:border-transparent disabled:bg-track disabled:text-bar ${BTN[kind]} ${className}`}>
        {lock && <LockIcon />}{children}
      </button>
      {p.disabled && disabledReason && <span className="text-small text-ink-2">{disabledReason}</span>}
    </span>
  );
}
/** 작업자 태블릿 큰 버튼만: 높이 96 · 글자 28 */
export const BIG_BTN = 'h-24 rounded-tile border-2 text-num font-bold';

/** 입력 · 고르기 공통 클래스 (고르기도 알약 아님). 오류면 FIELD_ERR를 더함 */
export const FIELD = 'h-11 rounded-ctl border border-line bg-white px-3 text-body text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none focus:ring-[3px] focus:ring-brand-tint';
export const FIELD_ERR = 'border-crit bg-crit-bg';
export function Field({ label, error, children }: { label: ReactNode; error?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className={`text-body font-bold ${error ? 'text-crit' : 'text-ink'}`}>{error ? '⚠ ' : ''}{label}</span>
      {children}
      {error && <span className="text-small text-crit">{error}</span>}
    </label>
  );
}

// ---------- 탭 ----------
export interface TabItem { key: string; label: ReactNode; count?: number; warn?: number }
/** 흰 틀(선 1px) 안에 칸, 선택 = 옅은 파랑 바탕 + 파랑 글자. 칸 36 + 틀 = 44. 이상 건수는 ▲ + 숫자 */
export function Tabs({ items, value, onChange, label, big }: { items: TabItem[]; value: string; onChange: (k: string) => void; label: string; big?: boolean }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex flex-wrap gap-0.5 rounded-tile border border-line bg-white p-[3px]">
      {items.map((t) => {
        const on = t.key === value;
        return (
          <button key={t.key} role="tab" aria-selected={on} type="button" onClick={() => onChange(t.key)}
            className={`flex items-center gap-1.5 rounded-ctl font-semibold ${big ? 'h-12 px-6 text-card' : 'h-9 px-4 text-body'} ${on ? 'bg-brand text-white' : 'text-ink-2 hover:bg-tile'}`}>
            {t.label}{t.count != null && <span>{t.count}</span>}
            {!!t.warn && <span className={on ? 'text-white' : 'text-warn'}>▲ {t.warn}</span>}
          </button>
        );
      })}
    </div>
  );
}

// ---------- 숫자 칸 ----------
/** 흰 칸 · 선 1px · 모서리 12 · 이름 → 값 → 단위 → 기준. 강조 칸 없음(강조는 결론 띠). 기준을 넘을 때만 tone */
export function Kpi({ label, value, unit, sub, tone }: { label: ReactNode; value: ReactNode; unit?: string; sub?: ReactNode; tone?: 'warn' | 'crit' }) {
  const c = tone === 'crit' ? 'text-crit' : tone === 'warn' ? 'text-warn' : '';
  return (
    <div className="rounded-tile border border-line bg-white px-4 py-3">
      <div className={`text-small ${tone ? `font-bold ${c}` : 'text-ink-2'}`}>{tone === 'crit' ? '⚠ ' : tone === 'warn' ? '▲ ' : ''}{label}</div>
      <div className={`font-mono text-num font-bold ${c || 'text-ink'}`}>{value}{unit && <span className="text-body font-normal text-ink-2"> {unit}</span>}</div>
      {sub && <div className="text-small text-ink-2">{sub}</div>}
    </div>
  );
}

// ---------- 칩 ----------
export type ChipTone = 'crit' | 'warn' | 'ok' | 'info' | 'ai' | 'outline' | 'record';
const CHIP: Record<ChipTone, string> = {
  crit: 'bg-crit-bg text-crit', warn: 'bg-warn-bg text-warn', ok: 'bg-ok-bg text-ok', info: 'bg-info-bg text-info',
  ai: 'bg-brand-tint text-brand-ink', outline: 'border border-line bg-white text-ink-2',
  record: 'rounded-md border border-brand-line bg-white font-mono text-brand-ink', // 기록 번호 꼬리표 (누르면 그 기록)
};
/** 태그: 높이 26 · 13/600 · 모서리 7 (옅은 바탕 + 진한 글자). 기호(⚠ ▲ ⓘ)를 넣을 때는 글자도 같이 */
export function Chip({ tone = 'outline', children }: { tone?: ChipTone; children: ReactNode }) {
  return <span className={`inline-flex h-[26px] items-center gap-1 whitespace-nowrap rounded-[7px] px-2.5 text-small font-semibold ${CHIP[tone]}`}>{children}</span>;
}
/** [가상] · [참고] · [실제] 꼬리표 = 점선 */
export const ValueTag = ({ children }: { children: ReactNode }) => <span className="inline-flex h-[22px] items-center rounded border border-dashed border-ink-3 px-1.5 text-small text-info">{children}</span>;

/** 같은 낱말은 어느 화면에서나 같은 색 ([제안] — 팀 확인 전 기본값) */
export const WORD_TONE: Record<string, ChipTone> = {
  // 문서
  'AI비서 초안': 'ai', '비서 정리': 'ai', '수정 중': 'info', '진행 중': 'info', '취소': 'outline', '확정': 'ok', '승인': 'ok', '완료': 'ok', '확정 늦음': 'warn',
  // 로트 · 품질
  '불합격': 'crit', '폐기': 'crit', '판정 대기': 'warn', '보류 검토': 'warn', '보류': 'warn', '강화': 'warn', '출하 금지': 'warn',
  '합격': 'ok', '해제': 'ok', '생산 중': 'info', '검사 대기': 'info', '측정 중': 'info', '기록 없음': 'info',
  // 재고 · 공구
  '재고 0': 'crit', '안전 재고 이하': 'warn', '교체 준비': 'warn', '입고 검사 합격': 'ok', '입고 검사 대기': 'info',
  // 정비 · 알림
  '긴급': 'crit', '고장': 'crit', '주의': 'warn', '기한 지남': 'warn', '오래 방치': 'warn', '처리됨': 'ok', '정비 끝': 'ok', '참고': 'info', '오늘': 'info', '이번 주': 'info',
};
export const StatusChip = ({ word }: { word: string }) => <Chip tone={WORD_TONE[word] ?? 'outline'}>{WORD_TONE[word] === 'crit' ? '⚠ ' : WORD_TONE[word] === 'warn' ? '▲ ' : ''}{word}</Chip>;

// ---------- 막대 ----------
/** 높이 6 · 모서리 3 · 정상 옅은 파랑 · 주의 노랑 · 긴급 빨강 · 고른 것 파랑 · 기준선(mark %) 남색 2px */
export function Bar({ pct, tone = 'normal', mark }: { pct: number; tone?: 'normal' | 'warn' | 'crit' | 'pick'; mark?: number }) {
  const c = { normal: 'bg-brand-line', warn: 'bg-warn-mark', crit: 'bg-crit', pick: 'bg-brand' }[tone];
  return (
    <div className="relative h-1.5 rounded-[3px] bg-track" role="presentation">
      <div className={`h-1.5 rounded-[3px] ${c}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
      {mark != null && <div className="absolute -top-[3px] h-3 w-0.5 bg-ink" style={{ left: `${mark}%` }} />}
    </div>
  );
}

// ---------- 표 ----------
/** 표 공통 클래스: 흰 머리(아래 선) 흐린 글자 · 줄 48 이상 · 줄무늬 없음 · 숫자 열 오른쪽(TD_NUM) · 누르면 열리는 줄은 ROW_GO + 끝에 › */
export const TABLE = 'w-full border-collapse text-body';
export const TH = 'border-b border-line bg-white px-3 py-2.5 text-left text-small font-semibold text-ink-3';
export const TD = 'h-12 border-t border-line-soft px-3 align-middle';
export const TD_NUM = `${TD} text-right font-mono`;
export const ROW_GO = 'cursor-pointer hover:bg-tile';
export const GO_MARK = <span aria-hidden="true" className="text-ink-3">›</span>;

// ---------- 빈 · 불러오는 중 · 팝업 ----------
export function Empty({ title = '없음', desc }: { title?: string; desc?: string }) {
  return <div className="flex flex-col items-center justify-center gap-0.5 py-6 text-center"><b className="text-body text-ink">{title}</b>{desc && <span className="text-small text-ink-2">{desc}</span>}</div>;
}
/** 칸 모양 회색 막대 + "불러오는 중" — 닫기 버튼 넣지 않음 (UI설계서 2.8) */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-2 rounded-card border border-line bg-white p-4" aria-busy="true">
      {Array.from({ length: lines }, (_, i) => <div key={i} className="h-3 rounded bg-track" style={{ width: `${90 - i * 20}%` }} />)}
      <span className="text-small text-ink-2">불러오는 중</span>
    </div>
  );
}
/** 팝업만 그림자 · 모서리 20 · 제목 20 · ✕ 44. footer = [취소] 왼쪽, [확정] 오른쪽 끝 */
export function Modal({ title, onClose, children, footer }: { title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" role="dialog" aria-modal="true">
      <div className="flex w-full max-w-[480px] flex-col gap-3 rounded-pop border border-line bg-white p-5 shadow-[0_20px_50px_rgba(27,42,65,0.18)]">
        <div className="flex items-center"><h2 className="text-title font-bold">{title}</h2><button type="button" aria-label="닫기" onClick={onClose} className="ml-auto h-11 w-11 rounded-full bg-tile text-[18px]">✕</button></div>
        <div className="text-body text-info">{children}</div>
        {footer && <div className="flex items-center gap-2">{footer}</div>}
      </div>
    </div>
  );
}

// ---------- 아이콘 ----------
/** 잠김 · 확정 — 🔒 이모지 대신 (기기마다 모양이 달라서) */
export function LockIcon({ size = 14 }: { size?: number }) {
  return <svg className="inline-block shrink-0 align-[-2px]" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>;
}
