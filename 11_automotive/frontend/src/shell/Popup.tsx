'use client';
// SCR-08 긴급 알림 팝업 — 정지 등급 알람이 뜨면 로그인한 모든 사용자의 화면 중앙에 (어느 화면에 있든). 현장 보기에서는 크게.
// 처리 책임은 그 설비 OPR·MNT, 다른 사람은 [확인]으로 닫기만 (9.9). 경고음은 [확인]으로만 끈다 (긴급은 소리 끄기 설정과 상관없음).
import { useEffect } from 'react';
import { MACHINES } from './data';
import { hhmm, type AlertRec } from './model';

export default function Popup({ alert, others, big, onCard, onAck }: { alert: AlertRec; others: number; big: boolean; sound?: boolean; onCard: () => void; onAck: () => void }) {
  useEffect(() => {
    let ctx: AudioContext | null = null, t: ReturnType<typeof setInterval> | null = null;
    try {
      ctx = new AudioContext();
      const beep = () => { if (!ctx) return; const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = 880; g.gain.value = 0.08; o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.25); };
      beep(); t = setInterval(beep, 1200);
    } catch { /* 소리를 못 내도 팝업은 뜬다 */ }
    return () => { if (t) clearInterval(t); ctx?.close().catch(() => undefined); };
  }, [alert.id]);

  // 페이지구조 v3 4장: 화면 중앙, 내용은 한 줄 (설비 · 알람 이름 · 시각), [지침카드] [닫기]. 닫아도 알림 탭에 처리 안 됨으로 남는다
  const a = alert.alarm, m = MACHINES[alert.machine];
  const t = big ? 'text-[30px]' : 'text-[18px]', bt = big ? 'h-[72px] px-10 text-[24px]' : 'h-12 px-6 text-[16px]';
  return (
    <div role="alertdialog" aria-label="긴급 알림" className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4">
      <div className={`flex w-full flex-col gap-4 rounded-3xl border-4 border-[#c62a2f] bg-white p-6 shadow-2xl ${big ? 'max-w-[1000px]' : 'max-w-[520px]'}`}>
        <b className={`${big ? 'text-[36px]' : 'text-[20px]'} text-[#c62a2f]`}>⚠ 긴급·정지 알림</b>
        <div className={`rounded-2xl bg-[#fdeeee] px-5 py-4 font-bold ${t}`}>
          {m.name} · {alert.code} {a ? a.nameKo : '(알람 코드집에 없음)'} · {hhmm(alert.time)}
          {others > 0 && <div className="mt-1 text-[14px] font-semibold text-[#a01e23]">외 긴급 {others}건 — 이브 알림에 있습니다</div>}
        </div>
        <div className="flex items-center justify-between gap-3">
          <button onClick={onCard} className={`${bt} rounded-full bg-[#1c2530] font-bold text-white hover:bg-black`}>지침카드</button>
          <button onClick={onAck} className={`${bt} rounded-full border-2 border-slate-400 font-bold hover:bg-slate-50`}>닫기</button>
        </div>
      </div>
    </div>
  );
}
