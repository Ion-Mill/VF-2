'use client';
// SCR-08 긴급 알림 팝업 — 정지 등급 알람이 뜨면 로그인한 모든 사용자의 화면 중앙에 (어느 화면에 있든). 현장 보기에서는 크게.
// 처리 책임은 그 설비 OPR·MNT, 다른 사람은 [확인]으로 닫기만 (9.9). 경고음은 [확인]으로만 끈다 (긴급은 소리 끄기 설정과 상관없음).
// 닫을 때 쌓여 있던 다른 긴급 알람은 이어서 뜨되 소리 없이 (sound=false, App이 정함 — 사용자 요청 2026-10-22)
// 모양 (사용자 요청 2026-10-21): 이전 팝업 내용 그대로(굵은 빨간 테두리 · 빨간 제목 · 연한 빨강 칸 한 줄 · [지침카드] [닫기]),
// 글꼴·버튼만 화이트 카드 테마(Pretendard · 주 버튼 파랑 · 닫기 흰 바탕 선), 가로는 이전보다 넓게.
import { useEffect } from 'react';
import { MACHINES } from './data';
import { hhmm, type AlertRec } from './model';

export default function Popup({ alert, others, big, sound = true, onCard, onAck }: { alert: AlertRec; others: number; big: boolean; sound?: boolean; onCard: () => void; onAck: () => void }) {
  useEffect(() => {
    if (!sound) return;
    let ctx: AudioContext | null = null, t: ReturnType<typeof setInterval> | null = null;
    try {
      ctx = new AudioContext();
      const beep = () => { if (!ctx) return; const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = 880; g.gain.value = 0.08; o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.25); };
      beep(); t = setInterval(beep, 1200);
    } catch { /* 소리를 못 내도 팝업은 뜬다 */ }
    return () => { if (t) clearInterval(t); ctx?.close().catch(() => undefined); };
  }, [alert.id, sound]);

  // 페이지구조 v3 4장: 화면 중앙, 내용은 한 줄 (설비 · 알람 이름 · 시각), [지침카드] [닫기]. 닫아도 알림 탭에 처리 안 됨으로 남는다
  const a = alert.alarm, m = MACHINES[alert.machine];
  const t = big ? 'text-num' : 'text-band', bt = big ? 'h-[72px] px-12 text-title' : 'h-12 px-8 text-card';
  return (
    <div role="alertdialog" aria-label="긴급 알림" className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 p-4">
      <div className={`flex w-full flex-col gap-4 rounded-pop border-4 border-crit bg-white p-6 shadow-card ${big ? 'max-w-[1100px] gap-6 p-10' : 'max-w-[720px]'}`}>
        <b className={`${big ? 'text-tablet' : 'text-title'} font-bold tracking-[-.02em] text-crit`}>⚠ 긴급·정지 알림</b>
        <div className={`rounded-card bg-crit-bg px-5 py-4 font-bold text-ink ${t}`}>
          {m.name} · {alert.code} {a ? a.nameKo : '(알람 코드집에 없음)'} · {hhmm(alert.time)}
          {others > 0 && <div className="mt-1 text-body font-semibold text-[#a01e23]">외 긴급 {others}건 — 이브 알림에 있습니다</div>}
        </div>
        <div className="flex items-center justify-between gap-3">
          <button onClick={onCard} autoFocus className={`${bt} rounded-ctl bg-brand font-semibold text-white outline-none hover:bg-brand-ink focus-visible:ring-[3px] focus-visible:ring-brand-line`}>지침카드</button>
          <button onClick={onAck} className={`${bt} rounded-ctl border border-line bg-white font-semibold text-ink outline-none hover:bg-tile focus-visible:ring-[3px] focus-visible:ring-brand-line`}>닫기</button>
        </div>
      </div>
    </div>
  );
}
