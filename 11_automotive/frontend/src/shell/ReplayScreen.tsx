'use client';
// SCR-06 다시 보기 — 지난 시간대를 3D 라인 뷰에서 블랙박스처럼 재생 (새 데이터 없음, API-LINE-06 기록을 시각 순서로).
// 3D에는 실시간 대신 그 시각의 상태·재공·병목을 넣는다 (ctx.setReplay). 센서는 10/1 실시간 기록만 (9월 센서 CSV는 생성 안 됨).
import { useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from './ctx';
import { LAYOUT, STATE_VIEW, WIP_NAME, stateOf } from './data';
import { EQS, SIM, hms, md, simIso, useFetch, type Eq } from './live';
import { ALARMS, REASONS } from './model';

interface Rp {
  from: string; to: string; step_min: number;
  states: Record<Eq, { start_at: string; end_at: string; state_code: string; reason_code: string | null; warn_marker: boolean; alarm_event_id: number | null }[]>;
  wip: ({ at: string; SOAK: number } & Record<string, number | string>)[]; bottleneck: { at: string; process_code: string; cause_code: string }[];
  alarms: { alarm_event_id: number; equipment_id: Eq; alarm_code: string; severity: string; occurred_at: string; cleared_at: string | null }[];
  sensors: Record<string, ({ at: string } & Record<string, number>)[]>; done: string[]; sensor_note: string;
}
const DIAL = 3 * 36e5;
const HATCH = 'repeating-linear-gradient(45deg,#cfd4da 0 3px,#f3f4f6 3px 6px)';
// 시안 색: 가공 연녹 · 정지 회색 · 고장 빨강 · 휴식(P02) 빗금
const segBg = (r: { state_code: string; reason_code: string | null }) => (r.state_code === 'RUN' ? '#bfe3cb' : r.state_code === 'DOWN' ? '#d23a35' : r.reason_code === 'P02' ? HATCH : '#9aa3ad');
const LEG: [string, string][] = [['가공', '#bfe3cb'], ['정지', '#9aa3ad'], ['고장', '#d23a35'], ['휴식', HATCH]];
const toLocalInput = (iso: string) => iso.slice(0, 16);
const fromLocalInput = (v: string) => `${v}:00+09:00`;

export function ReplayScreen() {
  const { key, back, setReplay, twin } = useApp();
  const center = key ?? simIso(SIM.now() - 30 * 60000);
  const day8 = Date.parse(`${center.slice(0, 10)}T08:00:00+09:00`), f0 = Date.parse(center) >= day8 ? day8 : Date.parse(center) - 3 * 36e5;
  const [from, setFrom] = useState(toLocalInput(simIso(f0)));
  const [to, setTo] = useState(toLocalInput(simIso(Math.min(SIM.now(), f0 + 12 * 36e5))));
  const q = `replay?from=${encodeURIComponent(fromLocalInput(from))}&to=${encodeURIComponent(fromLocalInput(to))}`;
  const { data, err } = useFetch<Rp>(q, 0, [q]);
  const [t, setT] = useState<number>(Date.parse(center));
  const [play, setPlay] = useState(false);
  const speed = 60;
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

  const pct = (ms: number) => ((ms - t0) / (t1 - t0)) * 100;
  const clampT = (x: number) => Math.min(t1, Math.max(t0, x));
  // 다이얼: 한 바퀴 = 3시간 (시안 2026-10-17)
  const dialC = useRef<{ cx: number; cy: number; a: number } | null>(null);
  const ang = (e: React.PointerEvent, c: { cx: number; cy: number }) => Math.atan2(e.clientY - c.cy, e.clientX - c.cx);
  const dialA = (((t - t0) % DIAL) / DIAL) * 2 * Math.PI - Math.PI / 2;
  const barRef = useRef<HTMLDivElement>(null);
  const seek = (e: React.PointerEvent) => { const r = barRef.current?.getBoundingClientRect(); if (r) { setPlay(false); setT(clampT(t0 + ((e.clientX - r.left) / r.width) * (t1 - t0))); } };
  const ticks: number[] = [];
  if (data) { const step = t1 - t0 > 12 * 36e5 ? 2 * 36e5 : 36e5; for (let h = Math.ceil(t0 / step) * step; h <= t1; h += step) ticks.push(h); }
  const stopMin = data ? Math.round(EQS.reduce((n, eq) => n + (data.states[eq] ?? []).filter((r) => r.state_code !== 'RUN').reduce((m, r) => m + Math.max(0, Math.min(Date.parse(r.end_at), t) - Math.max(Date.parse(r.start_at), t0)), 0), 0) / 60000) : 0;
  const runNow = EQS.filter((eq) => (frame?.equipment as Record<string, { state_code: string }>)?.[eq]?.state_code === 'RUN').length;
  const alarmsNow = (data?.alarms ?? []).filter((a) => Date.parse(a.occurred_at) <= t && (!a.cleared_at || t < Date.parse(a.cleared_at)));
  const box = 'rounded-3xl border border-[#e6e3f0] bg-white shadow-xl';
  const cards = EQS.map((eq) => {
    const e = (frame?.equipment as Record<string, { state_code: string; warn_marker: boolean; reason_code?: string | null; alarm?: { alarm_code: string } | null }>)?.[eq];
    const st = stateOf(e), hot = st === 'ALARM' || st === 'WARN' || !!e?.alarm;
    const sub = e?.alarm ? `${e.alarm.alarm_code} ${ALARMS[e.alarm.alarm_code]?.nameKo ?? ''}` : e?.reason_code ? `${e.reason_code} ${REASONS.find((x) => x.code === e.reason_code)?.name ?? ''}` : '';
    return { eq, st, v: STATE_VIEW[st], hot, sub };
  });
  const hotI = cards.findIndex((c) => c.hot), focusX = hotI < 0 ? 50 : ((hotI + 0.5) / cards.length) * 100;

  return (
    <>
      {/* 재생 중에는 3D 대신 카드 라인 (사용자 요청 2026-10-17) */}
      <div className="absolute bottom-[calc(var(--panelH)+24px)] left-[220px] right-3 top-[76px] flex flex-col overflow-hidden rounded-3xl border border-[#c4c8cd] px-6 py-4" style={{ background: `radial-gradient(ellipse 38% 60% at ${focusX}% 55%, #eceef0 0%, #c3c7cc 55%, #adb2b8 100%)` }}>
        <div className="flex items-center gap-3">
          <h3 className="text-[17px] font-bold text-[#2a323b]">라인 상태</h3>
          <span className="text-[13px] text-[#4b5560]">표면 재질이 곧 상태 · 회전광 = 가공 · 달아오름 = 주의 · 무광 = 정지</span>
          <span className="ml-auto flex items-center gap-1 text-[13px]">
            <span className="mr-2 text-[#4b5560]">다시 보기 <b className="font-mono">{md(simIso(t))} {hms(simIso(t))}</b></span>
            <input type="datetime-local" value={from} min="2026-09-01T08:00" onChange={(e) => setFrom(e.target.value)} className="h-8 rounded-full border border-white/70 bg-white/60 px-2" />~
            <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} className="h-8 rounded-full border border-white/70 bg-white/60 px-2" />
          </span>
        </div>
        <div className="relative my-auto">
          <div className="grid grid-cols-6 gap-4">
            {cards.map(({ eq, st, v, hot, sub }) => {
              const run = st === 'RUN' && !hot, red = st === 'ALARM';
              // 시안 재질: 무광 반투명 · 가공 = 흐르는 빛 · 주의 = 달아오른 금색 · 고장 = 붉게 달아오름
              const bg = hot ? (red ? 'linear-gradient(170deg,#fff3f1 0%,#f6c9c2 45%,#dc6b5e 100%)' : 'linear-gradient(170deg,#fdf7ec 0%,#f6e0b6 45%,#e0a656 100%)') : run ? 'radial-gradient(ellipse 22% 55% at 50% 58%, rgba(255,255,255,.95), rgba(255,255,255,0) 70%), conic-gradient(from 210deg at 50% 50%, #f6f7f8, #d6d9dd, #f8f9fa, #cdd1d6, #eef0f2, #f6f7f8), linear-gradient(180deg,#f7f8f9,#dcdfe3)' : 'linear-gradient(180deg,rgba(255,255,255,.3),rgba(255,255,255,.12))';
              const ink = hot || run ? '#26303a' : '#9aa1a9', stateInk = hot ? (red ? '#a3201c' : '#9a5a00') : run ? '#1f8a4c' : '#9aa1a9', bar = hot ? (red ? '#c62a2f' : '#d98a1e') : run ? '#2f9e5b' : '';
              return (
                <div key={eq} className={`relative flex h-[clamp(170px,26vh,250px)] flex-col justify-between rounded-[22px] p-4 transition-transform ${hot ? 'z-10 -translate-y-3 scale-[1.08] border-2 border-[#3d4a5c]' : 'border border-white/50'}`}
                  style={{ background: bg, boxShadow: hot ? '0 22px 44px rgba(110,72,20,.35), inset 0 1px 0 rgba(255,255,255,.9)' : run ? '0 8px 16px rgba(60,66,74,.18), inset 0 1px 0 #fff' : '0 4px 0 rgba(80,86,94,.16), inset 0 1px 0 rgba(255,255,255,.55)' }}>
                  <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-[20px]">
                    {hot && <span className="absolute -inset-y-1/4 left-[15%] w-1/2 rotate-[25deg] bg-gradient-to-r from-transparent via-white/55 to-transparent" />}
                    {run && <span className="rp-sheen absolute -inset-y-1/4 w-1/3 bg-gradient-to-r from-transparent via-white/60 to-transparent" />}
                  </div>
                  {hot && <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-[#3d4a5c] px-3 py-1 text-[12px] font-bold text-white shadow">그 시각 알람 ↓</span>}
                  <div className="relative"><b className="font-mono text-[19px]" style={{ color: ink }}>{eq}</b><div className="text-[14px]" style={{ color: hot || run ? '#5b6570' : '#a8aeb5' }}>{LAYOUT.equipment[eq].process}</div></div>
                  <div className="relative"><div className="text-[clamp(24px,2.6vw,32px)] font-bold" style={{ color: stateInk }}>{v.text}</div><div className="truncate text-[13px]" style={{ color: hot || run ? '#3b4450' : '#a8aeb5' }}>{sub}</div></div>
                  {bar && <span className="absolute inset-x-4 bottom-0 h-1.5 rounded-full" style={{ background: bar }} />}
                </div>);
            })}
          </div>
          {/* 재공: 공정 사이 칩 */}
          <div className="relative mt-7 h-12">
            <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full shadow-[0_1px_2px_rgba(0,0,0,.15)]" style={{ background: 'linear-gradient(#ffffff,#dfe3e7)' }} />
            {([['WIP-10-20', 1], ['WIP-20-30', 2], ['WIP-30-40', 4], ['WIP-40-50', 5]] as [string, number][]).map(([k, col]) => { const n = Number(frame?.wip?.[k as keyof typeof frame.wip] ?? 0), W = LAYOUT.wip[k], L = W?.limit, warm = !!(W?.warn && W.warn_over != null && n > W.warn_over); return (
              <div key={k} className={`absolute top-0 -translate-x-1/2 rounded-xl border px-3 py-1 text-center shadow-sm backdrop-blur-sm ${warm ? 'border-[#f0d9b0]' : 'border-white/60'}`} style={{ left: `${(col / 6) * 100}%`, background: warm ? '#fffaf0' : 'rgba(255,255,255,.4)' }}>
                <b className="font-mono text-[18px]" style={{ color: L && n > L ? '#c62a2f' : warm ? '#9a6200' : '#c09a66' }}>{n}</b><span className="text-[13px] text-[#b0b6bd]">/{L ?? '—'}</span><div className="text-[11px] text-[#a3a9b0]">{WIP_NAME[k] ?? k}</div></div>); })}
          </div>
          <div className="mt-2 text-center text-[13px] font-semibold text-[#4b5560]">OP-30 2대 병렬{frame?.bottleneck ? ` · 병목 ${frame.bottleneck.process_code}` : ''}</div>
        </div>
      </div>
      <div className="absolute bottom-3 left-[220px] right-3 grid h-[var(--panelH)] grid-cols-[210px_1fr_250px] gap-3 text-[13px]">
        {/* 다이얼 + 재생 */}
        <section className={`${box} flex flex-col items-center justify-center gap-3`}>
          <svg width="150" height="150" viewBox="-75 -75 150 150" className="cursor-grab touch-none select-none active:cursor-grabbing" aria-label="시간 다이얼 (한 바퀴 3시간)"
            onPointerDown={(e) => { const r = e.currentTarget.getBoundingClientRect(), c = { cx: r.left + r.width / 2, cy: r.top + r.height / 2, a: 0 }; c.a = ang(e, c); dialC.current = c; e.currentTarget.setPointerCapture(e.pointerId); setPlay(false); }}
            onPointerMove={(e) => { const c = dialC.current; if (!c || !data) return; const a = ang(e, c); let d = a - c.a; if (d > Math.PI) d -= 2 * Math.PI; if (d < -Math.PI) d += 2 * Math.PI; c.a = a; setT((x) => clampT(x + (d / (2 * Math.PI)) * DIAL)); }}
            onPointerUp={() => { dialC.current = null; }}>
            <defs><radialGradient id="dialG" cx="35%" cy="30%"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#d9dde3" /></radialGradient></defs>
            {Array.from({ length: 72 }, (_, i) => { const a = (i / 72) * 2 * Math.PI; return <line key={i} x1={Math.cos(a) * 60} y1={Math.sin(a) * 60} x2={Math.cos(a) * 72} y2={Math.sin(a) * 72} stroke="#b9c0c9" strokeWidth={1.5} />; })}
            <circle r="56" fill="url(#dialG)" stroke="#e3e6ea" />
            <circle cx={Math.cos(dialA) * 40} cy={Math.sin(dialA) * 40} r="5" fill="#3d4a5c" />
          </svg>
          <div className="flex gap-2">
            <button onClick={() => { if (t >= t1) setT(t0); setPlay((p) => !p); }} className="h-9 rounded-full border border-slate-300 bg-white px-4 font-bold">{play ? '⏸ 멈춤' : '▶ 재생'}</button>
            <button onClick={() => { setReplay(null); back(); }} className="h-9 rounded-full bg-[#2f9e5b] px-4 font-bold text-white">실시간</button>
          </div>
        </section>

        {/* 시간 되감기 막대 */}
        <section className={`${box} flex min-w-0 flex-col px-5 py-3`}>
          <div className="flex items-baseline justify-between"><h3 className="text-[16px] font-bold">시간 되감기</h3><span className="text-slate-500">다이얼 한 바퀴 = 3시간 · 막대를 끌어도 됩니다</span></div>
          {err && <p className="text-[#c62a2f]">{err} (한 번에 24시간까지)</p>}
          {!data ? <p className="mt-2 text-slate-500">기록 불러오는 중…</p> : (<>
            <div className="mt-2 flex"><span className="w-[72px] shrink-0" /><div className="relative h-4 flex-1 font-mono text-[12px] text-slate-500">{ticks.map((h) => <span key={h} className="absolute -translate-x-1/2" style={{ left: `${pct(h)}%` }}>{simIso(h).slice(11, 13)}</span>)}</div></div>
            <div className="flex min-h-0 flex-1">
              <div className="flex w-[72px] shrink-0 flex-col justify-around font-mono text-[12px]">{EQS.map((eq) => <span key={eq}>{eq}</span>)}</div>
              <div ref={barRef} className="relative flex flex-1 cursor-pointer touch-none flex-col justify-around" onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); seek(e); }} onPointerMove={(e) => { if (e.buttons) seek(e); }}>
                {EQS.map((eq) => (
                  <div key={eq} className="relative h-3.5 overflow-hidden rounded-sm bg-slate-100">
                    {(data.states[eq] ?? []).map((r, i) => <div key={i} title={`${r.state_code} ${r.reason_code ?? ''} ${r.start_at.slice(11, 16)}~${r.end_at.slice(11, 16)}`} className="absolute top-0 h-full" style={{ left: `${pct(Date.parse(r.start_at))}%`, width: `${Math.max(0.2, pct(Date.parse(r.end_at)) - pct(Date.parse(r.start_at)))}%`, background: segBg(r) }} />)}
                  </div>))}
                <div className="pointer-events-none absolute -top-3 bottom-0 w-[2px] -translate-x-1/2 bg-[#1c2530]" style={{ left: `${pct(t)}%` }}><span className="absolute -left-[5px] -top-1 h-3 w-3 rounded-full bg-[#1c2530]" /></div>
              </div>
            </div>
            <div className="mt-2 flex gap-4 pl-[72px] text-[12px] text-slate-600">{LEG.map(([k, bg]) => <span key={k} className="flex items-center gap-1"><i className="inline-block h-2.5 w-4 rounded-sm" style={{ background: bg }} />{k}</span>)}</div>
          </>)}
        </section>

        {/* 그 시각 요약 */}
        <section className={`${box} flex flex-col justify-between p-4`}>
          <div className="grid grid-cols-3 gap-2">
            <div><div className="text-slate-500">생산</div><b className="font-mono text-[26px]">{frame?.done_today ?? 0}</b></div>
            <div><div className="text-slate-500">누적 정지</div><b className="font-mono text-[26px]">{stopMin}</b><span className="text-slate-500">분</span></div>
            <div><div className="text-slate-500">가동</div><b className="font-mono text-[26px]">{runNow}</b><span className="text-slate-500">/{EQS.length}</span></div>
          </div>
          <div className="border-t border-slate-200 pt-2"><div className="text-slate-500">그 시각 알람</div>{alarmsNow.length ? alarmsNow.map((a) => <div key={a.alarm_event_id} className="font-semibold text-[#c62a2f]">{a.equipment_id} {a.alarm_code} {ALARMS[a.alarm_code]?.nameKo ?? ''}</div>) : <div>없음</div>}</div>
          {data && <p className="text-[11px] text-slate-400">{data.sensor_note} · 기록 {data.step_min}분 간격</p>}
        </section>
      </div>
    </>
  );
}
