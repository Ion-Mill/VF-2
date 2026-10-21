'use client';
// 알림 모션 미리보기 바 (사용자 요청 2026-10-21): [시연] 옆 [알림 미리보기]를 누르면 위 바 아래로 펼쳐진다.
// 누르면 그 알림 모션이 바로 나온다 — 화면 안에서만 흉내 내고 시연 서버·알림 목록·시계는 건드리지 않는다.
import { ALARMS, type AlertRec } from './model';

export type Preview = { popup: null | 'mid' | 'big'; bubble: null | 'crit' | 'news'; glow: null | 'crit' | 'warn'; n: number };
export const NO_PREVIEW: Preview = { popup: null, bubble: null, glow: null, n: 0 };
export const PREVIEW_BUBBLE = { crit: '⚠ 긴급 · VF2-01 992 축 과전류 · 10:20', news: '작업지시서 초안을 썼어요. 검토해 주세요' } as const;
// 미리보기용 긴급 알림 1건 (VF2-01 992) — 알람 코드집에 있는 이름을 쓴다
export const previewAlert = (): AlertRec => ({
  id: 'preview', eventId: 0, prevId: null, machine: 'vf1', code: '992', kind: 'alarm', level: '긴급', alarm: ALARMS['992'] ?? null,
  time: '2026-10-01T10:20:00', ts: 0, cleared: null, lot: null, scenario: 'S1', handled: false,
});

const ITEMS: { label: string; sub: string; on: (p: Preview) => boolean; set: (p: Preview) => Preview }[] = [
  { label: '긴급 팝업', sub: '화면 중앙 + 경고음', on: (p) => p.popup === 'mid', set: (p) => ({ ...p, popup: p.popup === 'mid' ? null : 'mid' }) },
  { label: '현장 큰 팝업', sub: '현장 보기용 큰 크기', on: (p) => p.popup === 'big', set: (p) => ({ ...p, popup: p.popup === 'big' ? null : 'big' }) },
  { label: '말풍선 · 긴급', sub: '빨강 > < 눈 + 이브 버튼 반응', on: (p) => p.bubble === 'crit', set: (p) => ({ ...p, bubble: p.bubble === 'crit' ? null : 'crit', n: p.n + 1 }) },
  { label: '말풍선 · 새 소식', sub: '반짝 눈 (문서·브리핑)', on: (p) => p.bubble === 'news', set: (p) => ({ ...p, bubble: p.bubble === 'news' ? null : 'news', n: p.n + 1 }) },
  { label: '테두리 빛 · 긴급', sub: '홈 3D 가장자리 빨강', on: (p) => p.glow === 'crit', set: (p) => ({ ...p, glow: p.glow === 'crit' ? null : 'crit' }) },
  { label: '테두리 빛 · 주의', sub: '홈 3D 가장자리 주황', on: (p) => p.glow === 'warn', set: (p) => ({ ...p, glow: p.glow === 'warn' ? null : 'warn' }) },
];

export default function PreviewBar({ pv, setPv, glass, onChange }: { pv: Preview; setPv: (f: (p: Preview) => Preview) => void; glass: string; onChange: (p: Preview) => void }) {
  const any = !!(pv.popup || pv.bubble || pv.glow);
  return (
    <div className={`absolute left-4 right-4 top-[84px] z-30 flex flex-wrap items-center gap-2 rounded-stage px-4 py-3 ${glass}`} role="toolbar" aria-label="알림 모션 미리보기">
      <b className="mr-1 text-card">알림 모션 미리보기</b>
      {ITEMS.map((it) => {
        const on = it.on(pv);
        return (
          <button key={it.label} aria-pressed={on} onClick={() => { const n = it.set(pv); setPv(() => n); onChange(n); }}
            className={`flex min-h-[48px] flex-col items-start rounded-tile border px-3 py-1 text-left ${on ? 'border-ink bg-ink text-white' : 'border-line bg-white/80 hover:bg-white'}`}>
            <span className="text-small font-bold">{it.label}</span>
            <span className={`text-small ${on ? 'text-white/70' : 'text-ink-3'}`}>{it.sub}</span>
          </button>
        );
      })}
      <button disabled={!any} onClick={() => { setPv(() => NO_PREVIEW); onChange(NO_PREVIEW); }} className="h-12 rounded-tile border border-line bg-white/80 px-4 text-small font-bold hover:bg-white disabled:text-ink-3">모두 끄기</button>
      <span className="ml-auto text-small text-ink-2">흉내만 냅니다 — 알림 목록·시연 데이터는 그대로</span>
    </div>
  );
}
