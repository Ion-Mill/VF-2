'use client';
// 디자인 통일 C안 (2026-10-20) — 모든 화면이 같이 쓰는 부품. DocKit.tsx를 넓힌 것.
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
      <div className={`mx-auto flex flex-col gap-3 ${doc ? 'max-w-[960px]' : 'max-w-[1440px]'}`}>{children}</div>
    </div>
  );
}

/** 화면 머리: 제목 20 · 부제 13 · 오른쪽 = 화면 전체 버튼(맨 끝 [닫기]) 또는 큰 갈래 탭 */
export function PageHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-2">
      <h2 className="text-title font-bold text-ink">{title}</h2>
      {sub && <span className="text-small text-ink-2">{sub}</span>}
      {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

// ---------- 결론 띠 ----------
const BAND: Record<BandTone, string> = {
  crit: 'border border-crit-line bg-crit-bg',
  warn: 'border border-warn-line bg-warn-bg',
  ok: 'border border-ok-line bg-ok-bg',
  todo: 'border border-line bg-white',
  draft: 'border-[1.5px] border-dashed border-ink-3 bg-white',
};
const BAND_ICON: Record<BandTone, string> = { crit: '⚠ ', warn: '▲ ', ok: '', todo: 'ⓘ ', draft: '' };

/** 결론 띠: 화면마다 1개, 화면 머리 바로 아래. 내용은 bands.ts가 만든 BandSpec 그대로 */
export function Band({ spec, onAction, actionDisabled }: { spec: BandSpec; onAction?: () => void; actionDisabled?: boolean }) {
  return (
    <section className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card px-4 py-3.5 ${BAND[spec.tone]}`}>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          {spec.tone === 'draft' && <Chip tone="ai">{spec.draftLabel ?? 'AI비서 초안'}</Chip>}
          <span className="text-band font-bold text-ink">{BAND_ICON[spec.tone]}{spec.title}</span>
        </div>
        {spec.desc && <div className="text-card text-ink-2">{spec.desc}</div>}
        {!!spec.chips?.length && <div className="flex flex-wrap gap-1.5">{spec.chips.slice(0, 4).map((c) => <Chip key={c} tone="outline">{c}</Chip>)}{spec.chips.length > 4 && <Chip tone="outline">외 {spec.chips.length - 4}건</Chip>}</div>}
      </div>
      {spec.action && onAction && <Btn kind="dark" lock={spec.actionLock} onClick={onAction} disabled={actionDisabled}>{spec.action}</Btn>}
    </section>
  );
}

/** 불러오는 중에는 띠 자리도 먼저 그린다 (늦게 떠서 화면이 밀리지 않게) */
export function BandSkeleton() {
  return <div className="flex h-[76px] flex-col justify-center gap-2 rounded-card border border-line bg-white px-4"><div className="h-4 w-1/2 rounded bg-track" /><div className="h-3 w-1/3 rounded bg-line-soft" /></div>;
}

// ---------- 칸 카드 · 접기 ----------
/** 흰 카드 · 선 1px · 모서리 16 · 그림자 없음 · 제목 15 굵게(표시 없음) + 오른쪽 칩. empty면 카드째 접고 제목 옆에 "없음" */
export function Sec({ title, sub, right, empty, children }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; empty?: boolean; children?: ReactNode }) {
  return (
    <section className="rounded-card border border-line bg-white">
      <div className="flex min-h-12 flex-wrap items-center gap-2 px-4 py-3">
        <h3 className="text-card font-bold text-ink">{title}</h3>
        {sub && <span className="text-small text-ink-2">{sub}</span>}
        {empty && <span className="text-body text-ink-2">없음</span>}
        {right && <div className="ml-auto flex flex-wrap items-center gap-1.5">{right}</div>}
      </div>
      {!empty && children != null && children !== false && <div className="px-4 pb-4">{children}</div>}
    </section>
  );
}

/** 접기 줄: 카드 맨 아래, 높이 44. 무엇이 몇 개 숨었는지 적는다 ("나머지 5건", "WSH-01 · CMM-01") */
export function Fold({ summary, defaultOpen = false, children }: { summary: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="-mx-4 -mb-4 mt-3 border-t border-line-soft">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex h-11 w-full items-center gap-2 px-4 text-left text-body font-semibold text-info hover:bg-tile">
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>{summary} {open ? '접기' : '펼치기'}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ---------- 버튼 · 입력 ----------
type BtnKind = 'primary' | 'normal' | 'dark';
const BTN: Record<BtnKind, string> = {
  primary: 'bg-brand text-white hover:bg-brand-ink',                // 화면 안 입력과 짝인 버튼 (찾기 · 저장)
  normal: 'border border-line bg-white text-ink hover:bg-tile',     // 대부분 (보류 · 폐기도 + 확인 상자)
  dark: 'bg-ink text-white hover:bg-black',                         // 결론 띠의 할 일 · 확정 · 승인
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
/** 회색 알약 틀 안에 칸, 선택 = 차콜 (왼쪽 메뉴 · 이브 창 탭과 같은 색). 칸 40 + 틀 4 = 44. 이상 건수는 ▲ + 숫자 */
export function Tabs({ items, value, onChange, label }: { items: TabItem[]; value: string; onChange: (k: string) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex flex-wrap gap-0.5 rounded-full bg-track p-1">
      {items.map((t) => {
        const on = t.key === value;
        return (
          <button key={t.key} role="tab" aria-selected={on} type="button" onClick={() => onChange(t.key)}
            className={`flex h-10 items-center gap-1.5 rounded-full px-4 text-body font-semibold ${on ? 'bg-ink text-white' : 'text-ink hover:bg-white/60'}`}>
            {t.label}{t.count != null && <span>{t.count}</span>}
            {!!t.warn && <span className={on ? 'text-warn-ondark' : 'text-warn'}>▲ {t.warn}</span>}
          </button>
        );
      })}
    </div>
  );
}

// ---------- 숫자 칸 ----------
/** 회색 칸 · 테두리 없음 · 모서리 12 · 이름 13 → 값 28 → 단위 14 → 기준 13. 강조 칸 없음(강조는 결론 띠). 기준을 넘을 때만 tone */
export function Kpi({ label, value, unit, sub, tone }: { label: ReactNode; value: ReactNode; unit?: string; sub?: ReactNode; tone?: 'warn' | 'crit' }) {
  const c = tone === 'crit' ? 'text-crit' : tone === 'warn' ? 'text-warn' : '';
  return (
    <div className="rounded-tile bg-tile px-3 py-2.5">
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
  ai: 'bg-brand-tint text-brand-ink', outline: 'border border-line bg-white text-info',
  record: 'rounded-md border border-brand-line bg-white font-mono text-brand-ink', // 기록 번호 꼬리표 (누르면 그 기록)
};
/** 높이 26 · 13/600 · 알약. 기호(⚠ ▲ ⓘ)를 넣을 때는 글자도 같이 */
export function Chip({ tone = 'outline', children }: { tone?: ChipTone; children: ReactNode }) {
  return <span className={`inline-flex h-[26px] items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-small font-semibold ${CHIP[tone]}`}>{children}</span>;
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
/** 높이 6 · 모서리 3 · 정상 회색 · 주의 노랑 · 긴급 빨강 · 고른 것 바이올렛 · 기준선(mark %) 차콜 2px */
export function Bar({ pct, tone = 'normal', mark }: { pct: number; tone?: 'normal' | 'warn' | 'crit' | 'pick'; mark?: number }) {
  const c = { normal: 'bg-bar', warn: 'bg-warn-mark', crit: 'bg-crit', pick: 'bg-brand' }[tone];
  return (
    <div className="relative h-1.5 rounded-[3px] bg-track" role="presentation">
      <div className={`h-1.5 rounded-[3px] ${c}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
      {mark != null && <div className="absolute -top-[3px] h-3 w-0.5 bg-ink" style={{ left: `${mark}%` }} />}
    </div>
  );
}

// ---------- 표 ----------
/** 표 공통 클래스: 머리 회색 띠 13 굵게 · 줄 48 이상 · 줄무늬 없음 · 숫자 열 오른쪽(TD_NUM) · 누르면 열리는 줄은 ROW_GO + 끝에 › */
export const TABLE = 'w-full border-collapse overflow-hidden rounded-tile border border-line text-body';
export const TH = 'bg-info-bg px-3 py-2.5 text-left text-small font-bold text-ink-2';
export const TD = 'h-12 border-t border-line-soft px-3 align-middle';
export const TD_NUM = `${TD} text-right font-mono`;
export const ROW_GO = 'cursor-pointer hover:bg-brand-tint';
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
      <div className="flex w-full max-w-[480px] flex-col gap-3 rounded-pop border border-line bg-white p-5 shadow-[0_20px_50px_rgba(30,30,50,0.18)]">
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
