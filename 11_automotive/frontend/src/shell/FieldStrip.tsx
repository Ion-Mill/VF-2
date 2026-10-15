'use client';
// SCR-26 현장 보기의 오른쪽 띠: [3] 브리핑 5줄(교대 내내) + [4] 처리 안 된 알람 (담당 공정, 보고 순위, 4줄 넘으면 "외 N건").
import { useState } from 'react';
import { useApp } from './ctx';
import { MACHINES, stateOf } from './data';
import { SIM, md } from './live';
import { LEVEL_VIEW, RANK, alarmTitle, hhmm } from './model';
import { lastShiftReport } from './Briefing';

const MAX_LINES = 4;

export default function FieldStrip({ onBriefing }: { onBriefing: () => void }) {
  const { twin, alerts, user, openCard, shiftReports, pm, settings } = useApp();
  const [all, setAll] = useState(false);
  const mine = alerts.filter((a) => !a.handled && (user.procs.length === 0 || user.procs.includes(MACHINES[a.machine].op)) && a.level !== '참고');
  const day = 864e5;
  const rankOf = (a: typeof mine[number]) => (a.level === '주의' && SIM.now() - a.ts > day ? 0.5 : RANK[a.level]); // 24시간 넘은 주의 = 0-1
  const sorted = [...mine].sort((a, b) => rankOf(a) - rankOf(b) || a.ts - b.ts);
  const shown = all ? sorted : sorted.length > MAX_LINES ? sorted.slice(0, MAX_LINES - 1) : sorted;
  const rest = sorted.length - shown.length;

  const eqs = twin ? Object.entries(twin.equipment) : [];
  const lockout = eqs.filter(([, e]) => e.state_code === 'MAINT').map(([k]) => k);
  const last = lastShiftReport(shiftReports, twin);
  const tools = eqs.filter(([, e]) => user.procs.includes(e.process_code)).flatMap(([, e]) => e.tools).filter((t) => t.warn);
  const pmToday = (pm?.tasks ?? []).filter((t) => (t.state === 'OVERDUE' || t.state === 'DUE_SOON') && t.cycle_code !== 'DAILY');
  const fs = settings.fontScale ? { fontSize: 'var(--fs-body)' } : undefined;

  return (
    <aside className="flex h-full w-[360px] flex-col border-l border-slate-300 bg-white text-[15px]" style={fs}>
      <section className="border-b border-slate-200 p-3">
        <h2 className="mb-2 text-[13px] font-bold text-slate-500">브리핑 5줄 · {twin ? `${twin.shift.shift_type === 'DAY' ? '주간' : '야간'} ${md(twin.clock.sim_at)}` : '기록 없음'}</h2>
        {!twin ? <p className="text-slate-400">없음 (연결 끊김)</p> : (
          <ul className="flex flex-col gap-1.5">
            <li>🔒 잠금·표지 <b>{lockout.length ? lockout.join(' · ') + ' (정비 중 — 전원 넣지 마세요)' : '없음'}</b></li>
            <li>지난 교대 양품 <b>{last ? `${Number(last.actual_qty) - Number(last.defect_qty)}개` : '없음'}</b> {last && <span className="text-[12px] text-slate-500">({last.shift_id.slice(5)})</span>}</li>
            <li>내 공정 알람 <b>{mine.length}건</b></li>
            <li>공구 수명 90% 이상 <b>{tools.length ? tools.map((t) => `${t.tool_id} ${t.usage_pct}% ▲`).join(' · ') : '없음'}</b></li>
            <li>이번 교대 총 <b>{twin.production.total_target_qty}개</b> · 예방 정비 <b>{pmToday.length ? `${pmToday[0].equipment_id} ${pmToday[0].item_name}${pmToday.length > 1 ? ` 외 ${pmToday.length - 1}` : ''}` : '없음'}</b></li>
          </ul>
        )}
        <button onClick={onBriefing} className="mt-2 h-11 rounded-md border border-slate-300 px-3 text-[14px] font-semibold hover:bg-slate-50">브리핑 크게</button>
      </section>

      <section className="min-h-0 flex-1 overflow-y-auto p-3">
        <h2 className="mb-2 text-[13px] font-bold text-slate-500">처리 안 된 알람 · 전체 {sorted.length}건 {user.procs.length ? `(${user.procs.join('·')})` : ''}</h2>
        {sorted.length === 0 ? <p className="text-slate-400">처리 안 된 알람 없음</p> : (
          <ul className="flex flex-col gap-2">
            {shown.map((a) => {
              const old = a.level === '주의' && SIM.now() - a.ts > day;
              const st = twin ? stateOf(twin.equipment[MACHINES[a.machine].eq!]) : 'NODATA';
              return (
                <li key={a.id} className="rounded-lg border border-slate-300 p-2">
                  <div className="font-bold" style={{ color: LEVEL_VIEW[a.level].color }}>{LEVEL_VIEW[a.level].icon} {a.level} · {MACHINES[a.machine].name} {old && <span className="ml-1 rounded bg-[#fff1cc] px-1 text-[11px] text-[#7a4b00]">24시간 넘음</span>}</div>
                  <div>{alarmTitle(a.alarm, a.code)} <span className="text-slate-500">{hhmm(a.time)}{a.cleared ? ' · 설비 알람 해제됨' : ''}</span> <span className="text-[12px] text-slate-500">({st})</span></div>
                  <button onClick={() => openCard(a.id)} className="mt-1 h-11 rounded-md border border-slate-300 px-3 text-[14px] font-semibold hover:bg-slate-50">지침카드</button>
                </li>
              );
            })}
            {rest > 0 && <li><button onClick={() => setAll(true)} className="h-11 w-full rounded-md border border-dashed border-slate-400 text-[14px] font-semibold">외 {rest}건 (전부 펼치기)</button></li>}
          </ul>
        )}
      </section>
      <div className="h-[72px] shrink-0" aria-hidden />
    </aside>
  );
}
