'use client';
// SCR-06 다시 보기 — 지난 시간대를 3D 라인 뷰에서 블랙박스처럼 재생 (새 데이터 없음, API-LINE-06 기록을 시각 순서로).
// 3D에는 실시간 대신 그 시각의 상태·재공·병목을 넣는다 (ctx.setReplay). 센서는 10/1 실시간 기록만 (9월 센서 CSV는 생성 안 됨).
import { useEffect, useMemo, useRef, useState } from 'react';
import { BTN, useApp } from './ctx';
import { CAUSE_KO, LAYOUT, STATE_VIEW, WIP_NAME, stateOf } from './data';
import { EQS, SIM, hms, md, simIso, useFetch, type Eq } from './live';
import { ALARMS } from './model';
import { Spark } from './Eve';

interface Rp {
  from: string; to: string; step_min: number;
  states: Record<Eq, { start_at: string; end_at: string; state_code: string; reason_code: string | null; warn_marker: boolean; alarm_event_id: number | null }[]>;
  wip: ({ at: string; SOAK: number } & Record<string, number | string>)[]; bottleneck: { at: string; process_code: string; cause_code: string }[];
  alarms: { alarm_event_id: number; equipment_id: Eq; alarm_code: string; severity: string; occurred_at: string; cleared_at: string | null }[];
  sensors: Record<string, ({ at: string } & Record<string, number>)[]>; done: string[]; sensor_note: string;
}
const COL: Record<string, string> = { RUN: '#1fbf63', IDLE: '#b8c0c8', SETUP: '#3b82f6', DOWN: '#e5484d', MAINT: '#6b7580', BLOCKED: '#e8954a' };
const toLocalInput = (iso: string) => iso.slice(0, 16);
const fromLocalInput = (v: string) => `${v}:00+09:00`;

export function ReplayScreen() {
  const { key, back, setReplay, twin } = useApp();
  const center = key ?? simIso(SIM.now() - 30 * 60000);
  const [from, setFrom] = useState(toLocalInput(simIso(Date.parse(center) - 15 * 60000)));
  const [to, setTo] = useState(toLocalInput(simIso(Math.min(SIM.now(), Date.parse(center) + 30 * 60000))));
  const q = `replay?from=${encodeURIComponent(fromLocalInput(from))}&to=${encodeURIComponent(fromLocalInput(to))}`;
  const { data, err } = useFetch<Rp>(q, 0, [q]);
  const [t, setT] = useState<number>(Date.parse(center));
  const [play, setPlay] = useState(false);
  const [speed, setSpeed] = useState(20);
  const last = useRef(Date.now());
  const t0 = data ? Date.parse(data.from) : 0, t1 = data ? Date.parse(data.to) : 1;

  useEffect(() => { if (data) setT((x) => Math.min(Math.max(x, t0), t1)); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!play) return;
    last.current = Date.now();
    const id = setInterval(() => { const n = Date.now(); setT((x) => { const y = x + (n - last.current) * speed; if (y >= t1) { setPlay(false); return t1; } return y; }); last.current = n; }, 100);
    return () => clearInterval(id);
  }, [play, speed, t1]);
  useEffect(() => () => setReplay(null), [setReplay]);

  // 그 시각의 상태 → 3D (applyLive 모양)
  const frame = useMemo(() => {
    if (!data) return null;
    const at = (list: { start_at: string; end_at: string }[]) => list.find((r) => Date.parse(r.start_at) <= t && t < Date.parse(r.end_at)) ?? list[list.length - 1];
    const equipment: Record<string, unknown> = {};
    EQS.forEach((eq) => {
      const r = at(data.states[eq] ?? []) as Rp['states'][Eq][number] | undefined;
      const al = data.alarms.find((a) => a.equipment_id === eq && Date.parse(a.occurred_at) <= t && (!a.cleared_at || t < Date.parse(a.cleared_at)));
      equipment[eq] = { state_code: r?.state_code ?? 'IDLE', warn_marker: !!r?.warn_marker, reason_code: r?.reason_code, alarm: al ? { ...al, cleared_at: null } : null, tools: [], sensor: null, parts_in: r?.state_code === 'RUN' ? 1 : 0,
        std_cycle_min: LAYOUT.equipment[eq].std_cycle_min ?? LAYOUT.equipment[eq].batch_time_min ?? 1, minutes: 0 };
    });
    const w = [...data.wip].reverse().find((x) => Date.parse(x.at) <= t) ?? data.wip[0];
    const bn = [...data.bottleneck].reverse().find((x) => Date.parse(x.at) <= t);
    return { replay: true, clock: { sim_at: simIso(t), speed: speed, paused: !play }, equipment, wip: w ? Object.fromEntries(Object.entries(w).filter(([k]) => k.startsWith('WIP'))) : {}, soak_qty: w?.SOAK ?? 0,
      wip_limits: twin?.wip_limits ?? {}, bottleneck: bn ? { process_code: bn.process_code, cause_code: bn.cause_code } : null, done_today: data.done.filter((d) => Date.parse(d) <= t).length, production: { rate_per_hour: 0 } };
  }, [data, t, speed, play, twin?.wip_limits]);
  useEffect(() => { setReplay(frame); }, [frame, setReplay]);

  const pct = (iso: string) => ((Date.parse(iso) - t0) / (t1 - t0)) * 100;
  const sensorAt = (eq: string) => (data?.sensors[eq] ?? []).filter((x) => Date.parse(x.at) <= t).slice(-30);
  const wNow = frame?.wip ?? {};
  const alarmsNow = (data?.alarms ?? []).filter((a) => Date.parse(a.occurred_at) <= t && (!a.cleared_at || t < Date.parse(a.cleared_at)));

  return (
    <>
      <div className="absolute inset-x-0 top-0 z-10 flex h-[44px] items-center gap-3 bg-[#1c2530] px-3 text-[14px] font-semibold text-white">
        <span>◀ 다시 보기 중 · {md(simIso(t))} {hms(simIso(t))} (실시간 아님) ▶</span>
        <span className="ml-auto flex items-center gap-1 text-[13px] font-normal">
          <input type="datetime-local" value={from} min="2026-09-01T08:00" onChange={(e) => setFrom(e.target.value)} className="h-9 rounded px-1 text-[#26303a]" />~
          <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} className="h-9 rounded px-1 text-[#26303a]" />
        </span>
        <button onClick={() => { setReplay(null); back(); }} className="h-9 rounded-md bg-white px-3 text-[13px] font-bold text-[#1c2530]">실시간으로 돌아가기</button>
      </div>
      <div className="absolute bottom-0 left-0 right-0 h-[var(--panelH)] overflow-y-auto border-t border-slate-300 bg-white p-3 text-[13px]">
        {err && <p className="text-[#c62a2f]">{err} (한 번에 24시간까지)</p>}
        {!data ? <p className="text-slate-500">기록 불러오는 중…</p> : (<>
          <div className="relative mb-1 h-5 text-[11px] text-slate-500"><span className="absolute left-0">{md(data.from)} {data.from.slice(11, 16)}</span><span className="absolute right-0">{data.to.slice(11, 16)}</span></div>
          {EQS.map((eq) => (
            <div key={eq} className="flex items-center gap-2"><span className="w-[60px] shrink-0 font-semibold">{eq}</span>
              <div className="relative h-4 flex-1 overflow-hidden rounded bg-slate-100">
                {(data.states[eq] ?? []).map((r, i) => <div key={i} title={`${r.state_code} ${r.reason_code ?? ''} ${r.start_at.slice(11, 16)}~${r.end_at.slice(11, 16)}`} className="absolute top-0 h-full" style={{ left: `${pct(r.start_at)}%`, width: `${Math.max(0.2, pct(r.end_at) - pct(r.start_at))}%`, background: r.warn_marker ? '#f0a500' : COL[r.state_code] ?? '#ccc' }} />)}
              </div>
            </div>
          ))}
          <div className="relative mt-1 h-6">
            {data.alarms.map((a) => <button key={a.alarm_event_id} onClick={() => setT(Date.parse(a.occurred_at))} title={`${a.equipment_id} ${a.alarm_code}`} className="absolute -translate-x-1/2 text-[13px] font-bold" style={{ left: `${pct(a.occurred_at)}%`, color: a.severity === 'STOP' ? '#c62a2f' : '#9a6200' }}>{a.severity === 'STOP' ? '⚠' : '▲'}</button>)}
            {data.bottleneck.map((b) => <button key={b.at} onClick={() => setT(Math.max(t0, Date.parse(b.at)))} title={`병목 ${b.process_code} ${CAUSE_KO[b.cause_code] ?? ''}`} className="absolute -translate-x-1/2 text-[12px] text-[#b45309]" style={{ left: `${Math.max(0, pct(b.at))}%` }}>◆</button>)}
          </div>
          <input type="range" min={t0} max={t1} step={1000} value={t} onChange={(e) => { setT(Number(e.target.value)); setPlay(false); }} className="w-full" aria-label="시간 막대" />
          <div className="flex flex-wrap items-center gap-2">
            속도 {[1, 20, 60].map((s) => <button key={s} onClick={() => setSpeed(s)} className={`${BTN} ${speed === s ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>×{s}</button>)}
            <button onClick={() => setT((x) => Math.max(t0, x - 10000))} className={BTN}>⏮ 10초 전</button>
            <button onClick={() => setPlay((p) => !p)} className={BTN}>{play ? '⏸ 멈춤' : '▶ 재생'}</button>
            <span className="text-slate-600">재공 {Object.entries(wNow).map(([c, n]) => `${WIP_NAME[c] ?? c} ${n}`).join(' · ')} · 병목 {frame?.bottleneck?.process_code ?? '—'}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-4">
            {['VF2-01', 'VF2-02'].map((eq) => { const s = sensorAt(eq); return <span key={eq}>{eq} 축 부하 X <Spark v={s.map((x) => x.Xload)} /> 주축 부하 <Spark v={s.map((x) => x.SpindleLoadPct)} /> 공기 <Spark v={s.map((x) => x.AirPressure)} /></span>; })}
            <span>알람 {alarmsNow.length ? alarmsNow.map((a) => `${a.equipment_id} ${a.alarm_code} ${ALARMS[a.alarm_code]?.nameKo ?? ''}`).join(' · ') : '없음'}</span>
            {EQS.map((eq) => { const st = stateOf((frame?.equipment as Record<string, { state_code: string; warn_marker: boolean }>)?.[eq]); return <span key={eq} style={{ color: STATE_VIEW[st].color }}>{eq} {STATE_VIEW[st].icon} {STATE_VIEW[st].text}</span>; })}
          </div>
          <p className="mt-1 text-[11px] text-slate-500">{data.sensor_note} · 기록 {data.step_min}분 간격</p>
        </>)}
      </div>
    </>
  );
}
