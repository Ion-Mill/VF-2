'use client';
// SCR-08 긴급 알림 팝업 — 정지 등급 알람이 뜨면 로그인한 모든 사용자의 화면 중앙에 (어느 화면에 있든). 현장 보기에서는 크게.
// 처리 책임은 그 설비 OPR·MNT, 다른 사람은 [확인]으로 닫기만 (9.9). 경고음은 [확인]으로만 끈다 (긴급은 소리 끄기 설정과 상관없음).
import { useEffect } from 'react';
import { useApp } from './ctx';
import { LINE6, MACHINES } from './data';
import { chainOf, hhmm, responsible, whoText, type AlertRec } from './model';

export default function Popup({ alert, others, big, onCard, onAck }: { alert: AlertRec; others: number; big: boolean; sound?: boolean; onCard: () => void; onAck: () => void }) {
  const { user, alerts } = useApp();
  useEffect(() => {
    let ctx: AudioContext | null = null, t: ReturnType<typeof setInterval> | null = null;
    try {
      ctx = new AudioContext();
      const beep = () => { if (!ctx) return; const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = 880; g.gain.value = 0.08; o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.25); };
      beep(); t = setInterval(beep, 1200);
    } catch { /* 소리를 못 내도 팝업은 뜬다 */ }
    return () => { if (t) clearInterval(t); ctx?.close().catch(() => undefined); };
  }, [alert.id]);

  const a = alert.alarm, m = MACHINES[alert.machine], mine = responsible(user, alert.machine), chain = chainOf(alert, alerts);
  return (
    <div role="alertdialog" aria-label="긴급 알림" className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4">
      <div className={`flex w-full flex-col gap-3 rounded-xl border-4 border-[#c62a2f] bg-white p-5 shadow-2xl ${big ? 'h-[86vh] max-w-[1200px]' : 'max-w-[600px]'}`}>
        <div className="flex items-center justify-between">
          <b className={`${big ? 'text-[34px]' : 'text-[19px]'} text-[#c62a2f]`}>⚠ 긴급 · 정지 등급 알람</b>
          <span className="text-[13px] text-slate-600">🔊 소리 남 · {hhmm(alert.time)}</span>
        </div>
        <div className={`${big ? 'text-[28px]' : 'text-[16px]'} leading-snug`}>
          <div className={`${big ? 'text-[46px]' : 'text-[22px]'} font-extrabold`}>{m.name} ({m.op}) &nbsp;{alert.code}</div>
          <div className="font-semibold">{a ? a.nameKo : '알람 코드집에 없는 알람입니다'}</div>
          {chain.length > 1 && <div className="font-semibold text-[#a01e23]">연쇄 알람 {chain.join(' → ')}</div>}
          <div className="mt-1">{a ? whoText(a) : '보전 담당자 호출'}</div>
          <div className={`mt-2 rounded-md px-3 py-2 font-bold ${mine ? 'bg-[#ffe1e1] text-[#a01e23]' : 'bg-slate-100 text-slate-700'}`}>
            {mine ? '처리 책임: 나 (이 설비 담당) — 지침카드를 따라 조치하세요' : '처리 책임: 그 설비 작업자·보전 담당자 — [확인]으로 닫기만 합니다 (처리 아님)'}
          </div>
        </div>
        {big && (
          <div className="flex gap-2 text-[20px] font-bold" aria-label="설비 위치">
            {LINE6.map((id) => <span key={id} className={`rounded-md border-2 px-3 py-2 ${id === alert.machine ? 'border-[#c62a2f] bg-[#ffe1e1] text-[#c62a2f]' : 'border-slate-300 text-slate-500'}`}>{MACHINES[id].name}{id === alert.machine ? ' ⚠' : ''}</span>)}
          </div>
        )}
        {others > 0 && <div className="text-[14px] font-semibold text-[#c62a2f]">외 긴급 {others}건 (알림 탭에 전부 있습니다)</div>}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
          <button onClick={onCard} className={`${big ? 'h-[76px] px-8 text-[26px]' : 'h-12 px-5 text-[16px]'} rounded-md bg-[#1c2530] font-bold text-white`}>지침카드 열기</button>
          <button onClick={onAck} className={`${big ? 'h-[76px] px-8 text-[26px]' : 'h-12 px-5 text-[16px]'} rounded-md border-2 border-slate-400 font-bold`}>확인 (소리 끄기)</button>
        </div>
      </div>
    </div>
  );
}
