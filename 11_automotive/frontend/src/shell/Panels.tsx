'use client';
// SCR-04·05 하단 패널 (Claude Design 시안 2026-10-15): 윗줄 지표 [7]~[10] · 아래 시간대별 실적 [7] · 작업지시 진행 [11] · 설비 [6]. 값 = 시연 데이터 서버 (API-LINE-02~05).
// field = SCR-26 현장 보기: 설비를 눌렀을 때 그 설비 [6]만 — 지금 알람·지침카드를 맨 위에 크게, 나머지는 작게. 생산 지표·작업지시 표는 SCR-04에만.
import { useState } from 'react';
import type { MachineId } from '@/components/types';
import { useApp } from './ctx';
import { CAUSE_KO, ID_OF, MACHINES, STATE_VIEW, WIP_NAME, stateOf } from './data';
import { hm, md, useFetch, type Eq, type OrderRow, type Production } from './live';
import { alarmTitle, type AlertRec } from './model';

const AMBER = '#9a6200';
const cell = 'flex min-w-0 flex-col justify-center border-r border-slate-200 px-5 py-3';
const lbl = 'text-[14px] text-slate-500';
const num = 'font-mono font-bold tabular-nums';
const obtn = 'h-12 flex-1 rounded-lg border border-slate-300 bg-white text-[15px] font-semibold hover:bg-slate-50';

function Bar({ pct, color = '#4b5a69' }: { pct: number; color?: string }) {
  return <div className="h-1.5 w-full rounded bg-slate-200"><div className="h-1.5 rounded" style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: color }} /></div>;
}

export default function Panels({ open = true, onToggle, field = false }: { open?: boolean; onToggle?: () => void; field?: boolean }) {
  const { twin, alerts, wos, stopReasons, selected, go, openCard, openWo, user, connected, selectMachine } = useApp();
  const [why, setWhy] = useState<string | null>(null);
  const dt = useFetch<{ downtimes: { equipment_id: string; start_at: string; state_code: string; minutes: number }[] }>(connected ? 'downtimes' : null, 10000);
  if (!twin) return <div className="flex h-full items-center gap-3 bg-white p-4 text-[14px] text-slate-500"><div className="h-3 w-40 animate-pulse rounded bg-slate-200" />데이터를 기다리는 중 (연결 끊김이면 위 띠를 보세요)</div>;
  const p = twin.production, k = twin.kpi.by;
  // 처음 열면 SUP는 병목 공정, OPR은 담당 공정 (SCR-04 [6])
  const bnEq = Object.entries(twin.equipment).find(([, e]) => e.process_code === twin.bottleneck.process_code)?.[0];
  const myEq = Object.entries(twin.equipment).find(([, e]) => user.procs.includes(e.process_code))?.[0];
  const pick = (user.role === 'OPR' ? myEq : bnEq) as Eq | undefined;
  const selId: MachineId = selected && selected !== 'inf' ? selected : pick ? ID_OF[pick] : 'vf1';
  const eq = MACHINES[selId].eq!, E = twin.equipment[eq], sv = STATE_VIEW[stateOf(E)];
  const isOp30 = MACHINES[selId].op === 'OP-30';
  const cur: AlertRec | undefined = [...alerts].reverse().find((a) => a.machine === selId && !a.handled);
  const noReason = (dt.data?.downtimes ?? []).filter((d) => d.equipment_id === eq && !['RUN', 'BLOCKED', 'MAINT'].includes(d.state_code) && !stopReasons[`${d.equipment_id}|${d.start_at}`]?.reason).length;
  const kp = isOp30 && selected ? k[eq] : k.LINE;
  const wo = wos.find((w) => w.machine === selId && w.state !== 'done' && w.state !== 'cancelled');
  const proc = twin.process[E.process_code] ?? { pq: 0 };
  const done = p.actual_qty >= p.total_target_qty;
  const scale = Math.max(p.total_target_qty, p.actual_qty, 1);
  const toggle = (w: string) => setWhy(why === w ? null : w);
  // 진행 중·대기 먼저, 완료는 뒤 (스크롤)
  const orders = [...twin.orders].sort((a, b) => Number(isDone(a)) - Number(isDone(b)));
  // [6] 설비 칸 (SCR-04와 현장 보기가 같이 씀 — 현재 알람 줄은 화면마다 따로)
  const rows = (<>
    <dt className="text-slate-500">현재 로트</dt><dd>{E.lot_no ? <button onClick={() => go('lots', E.lot_no)} className="font-mono font-semibold text-[#0f6f86] underline">{E.lot_no}</button> : '—'}</dd>
    <dt className="text-slate-500">교대 실적/목표</dt><dd>{E.process_code} <b className={num}>{proc.pq}</b> / <b className={num}>{p.total_target_qty}</b> <span className="text-slate-500">{isOp30 ? `(2대 합, 이 설비 ${E.shift_actual_qty})` : ''}</span></dd>
    <dt className="text-slate-500">오늘 정지</dt><dd><b className={num}>{E.stop_min}</b>분 <span className="text-slate-500">대기·막힘·준비 포함 · 고장 손실 약 {E.loss_qty}개</span></dd>
    <dt className="text-slate-500">정지 사유 미입력</dt><dd><b className={num} style={{ color: noReason ? AMBER : undefined }}>{noReason}</b>건 {noReason > 0 && !field && <button onClick={() => go('stops')} className="ml-1 text-[#0f6f86] underline">정지 사유 입력 →</button>}</dd>
    {isOp30 && (<>
      <dt className="text-slate-500">공구 수명</dt>
      <dd className="flex flex-wrap gap-x-3 gap-y-1">{E.tools.map((t) => (
        <span key={t.tool_id} className="w-[88px]" style={{ color: t.warn ? AMBER : undefined }}>
          <span className="flex justify-between font-mono text-[13px]"><span>{t.tool_no}</span><b>{t.usage_pct}%{t.warn ? ' ▲' : ''}</b></span><Bar pct={t.usage_pct} color={t.warn ? '#e0a040' : '#4b5a69'} />
        </span>))}</dd>
      <dt className="text-slate-500">진행 중 작업지시서</dt><dd>{wo ? <button onClick={() => openWo(wo.no)} className="font-semibold text-[#0f6f86] underline">{wo.no} {wo.code}</button> : '없음'}</dd>
    </>)}
    {E.sensor && (user.role === 'MNT' || user.role === 'MGR') && (<>
      <dt className="text-slate-500">센서 (1분 평균)</dt><dd className="text-[14px]">주축 부하 {E.sensor.SpindleLoadPct}% · 모터 {E.sensor.SpindleMotorTemp}℃ · 공기 {E.sensor.AirPressure} psi ({(E.sensor.AirPressure * 0.0689476).toFixed(2)} bar)</dd>
    </>)}
  </>);
  const tone = !cur ? '' : cur.level === '긴급' ? 'border-[#e8a0a2] bg-[#fdeeee] text-[#c62a2f]' : cur.level === '주의' ? 'border-[#ecd28e] bg-[#fff8e6] text-[#7a4e00]' : 'border-slate-200 bg-slate-50';
  const mark = (a: AlertRec) => (a.level === '긴급' ? '⚠' : a.level === '주의' ? '▲' : 'ⓘ');

  // SCR-26 현장 보기: 멀리서 보는 큰 모니터 — 알람이 먼저, 입력 버튼 없음 (입력은 현장 태블릿)
  if (field) return (
    <div className="flex h-full gap-5 bg-white p-4 text-[17px] text-[#26303a]">
      <section className="flex w-[46%] min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <b className="font-mono text-[26px]">{MACHINES[selId].name}</b>
          <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[14px]">{MACHINES[selId].op}</span>
          <span className="rounded-full border border-slate-300 px-3 py-0.5 text-[17px] font-bold" style={{ color: sv.color }}>{sv.icon} {sv.text} · {E.minutes}분째</span>
        </div>
        {cur ? (
          <div className={`flex min-h-0 flex-1 flex-col justify-center gap-3 rounded-xl border-2 px-5 py-3 ${tone}`}>
            <div className="text-[14px] font-semibold opacity-80">지금 알람 · {cur.level} · {hm(cur.time)}부터 · 알람 {cur.code}</div>
            <b className="text-[26px] leading-tight">{mark(cur)} {alarmTitle(cur.alarm, cur.code)}</b>
            <button onClick={() => openCard(cur.id)} className="h-14 rounded-lg bg-[#1f2933] text-[18px] font-bold text-white hover:bg-black">지침카드 보기 →</button>
          </div>
        ) : (
          <div className="flex flex-1 items-center rounded-xl border border-slate-200 bg-slate-50 px-5 text-[20px] font-semibold text-slate-600">지금 알람 없음</div>
        )}
      </section>
      <dl className="grid min-h-0 flex-1 grid-cols-[150px_1fr] content-start gap-x-3 gap-y-2 overflow-y-auto border-l border-slate-200 pl-5 text-[16px]">{rows}</dl>
    </div>
  );

  return (
    <div className="flex h-full flex-col bg-white text-[#26303a]">
      {/* 윗줄 지표 */}
      <div className="grid h-[172px] shrink-0 grid-cols-[1.35fr_0.9fr_1.15fr_0.65fr_1fr_1.6fr_auto] border-b border-slate-200">
        {/* [7] 실적 / 총 목표 */}
        <button onClick={() => toggle('p')} className={`${cell} text-left`}>
          <div className="flex justify-between"><span className={lbl}>실적 / 총 목표</span>
            <b className={`text-[14px] ${done || p.risk ? '' : 'text-slate-500'}`} style={{ color: done ? '#13994f' : p.risk ? AMBER : undefined }}>{done ? '달성' : p.risk ? '▲ 미달 위험' : '진행 중'}</b></div>
          <div className="my-1"><span className={`${num} text-[38px]`}>{p.actual_qty}</span><span className="font-mono text-[24px] text-slate-500"> / {p.total_target_qty}</span><span className="text-[18px] text-slate-500"> 개</span></div>
          <div className="relative"><Bar pct={(p.actual_qty / scale) * 100} color="#0f9fbd" /><div className="absolute -top-1 h-3.5 w-0.5 bg-slate-800" style={{ left: `${(p.total_target_qty / scale) * 100}%` }} /></div>
          <div className="mt-2 text-[13px] text-slate-500">목표 {p.target_qty} + 이월 {p.carry_over_qty} · {p.shift_type === 'DAY' ? '주간' : '야간'} {hm(p.start_at)}~{hm(p.end_at)}</div>
        </button>
        {/* 예측 */}
        <button onClick={() => toggle('p')} className={`${cell} gap-2 text-left`}>
          <div className="flex items-baseline justify-between"><span className={lbl}>예측</span><span><span className={`${num} text-[28px]`}>{p.forecast_qty}</span><span className="text-slate-500">개</span></span></div>
          {p.short_qty > 0 && <div className="flex items-baseline justify-between"><span className={lbl}>부족</span><span style={{ color: AMBER }}><span className={`${num} text-[28px]`}>{p.short_qty}</span>개</span></div>}
          <div className="flex items-baseline justify-between"><span className={lbl}>시간당</span><span><span className={`${num} text-[28px]`}>{p.rate_per_hour}</span><span className="text-slate-500">개</span></span></div>
          <span className="text-[13px] text-slate-500">추정</span>
        </button>
        {/* [8] OEE — 처음 = 라인, OP-30 설비를 누르면 그 설비 */}
        <button onClick={() => toggle('k')} className={`${cell} gap-1.5 text-left`}>
          <div className="flex items-baseline justify-between"><span className={lbl}>OEE</span><span className={`${num} text-[32px]`} style={{ color: kp.warn.includes('OEE') ? AMBER : undefined }}>{kp.oee_pct ?? '—'}%{kp.warn.includes('OEE') ? ' ▲' : ''}</span></div>
          {([['가동률', kp.availability_pct, kp.warn.includes('가동률')], ['성능', kp.performance_pct, false], ['양품률', kp.quality_pct, false]] as const).map(([t, v, w]) => (
            <div key={t} className="grid grid-cols-[52px_1fr_64px] items-center gap-2 text-[14px]">
              <span className="text-slate-500">{t}</span><Bar pct={v ?? 0} color={w ? AMBER : '#4b5a69'} /><span className={`${num} text-right text-[15px]`} style={{ color: w ? AMBER : undefined }}>{v ?? '—'}%{w ? '▲' : ''}</span>
            </div>))}
          <span className="text-[12px] text-slate-500">{isOp30 && selected ? eq : '라인 (OP-30 2대 합)'} · 이번 교대</span>
        </button>
        {/* [9] 손실 */}
        <button onClick={() => toggle('l')} className={`${cell} text-left`}>
          <span className={lbl}>손실</span>
          <div className="my-1"><span className="text-[22px]">약 </span><span className={`${num} text-[30px]`}>{Math.round(p.loss_qty)}</span><span className="text-slate-500">개</span></div>
          <span className="text-[13px] text-slate-500">추정</span>
        </button>
        {/* [10] 병목 */}
        <div className={cell}>
          <span className={lbl}>병목</span>
          <div className={`${num} my-2 w-fit rounded-md border-2 border-dashed border-slate-800 px-3 py-1 text-[22px]`}>{twin.bottleneck.process_code}</div>
          <span className="text-[13px] text-slate-500">{CAUSE_KO[twin.bottleneck.cause_code] ?? twin.bottleneck.cause_code}{twin.bottleneck.since_at ? ` · ${md(twin.bottleneck.since_at)} ${hm(twin.bottleneck.since_at)}부터` : ''}</span>
        </div>
        {/* 재공 (흐름 순) */}
        <div className={`${cell} justify-start`}>
          <span className={`${lbl} mb-2`}>재공 (흐름 순)</span>
          <div className="flex flex-wrap items-center gap-1.5">
            {Object.entries(twin.wip).map(([c, n], i) => {
              const L = twin.wip_limits[c]; const o = !!(L?.warn && L.warn_over != null && n > L.warn_over);
              return (<span key={c} className="flex items-center gap-1.5">{i > 0 && <span className="text-slate-400">›</span>}
                <span className={`rounded-md border px-2.5 py-1 font-mono ${o ? 'border-[#e0a040] bg-[#fff8ec]' : 'border-slate-200'}`}>
                  <span className="block text-[12px] text-slate-500">{WIP_NAME[c]}</span><span className={`${num} text-[20px]`} style={{ color: o ? '#b45309' : undefined }}>{n}{o ? ' ■' : ''}</span>
                </span></span>);
            })}
            <span className="ml-1 rounded-md border border-slate-200 px-2.5 py-1"><span className="block text-[12px] text-slate-500">선반</span><span className={`${num} text-[20px]`}>{twin.soak_qty}</span></span>
          </div>
        </div>
        {onToggle && <button onClick={onToggle} className="flex w-16 flex-col items-center justify-center gap-1 text-[13px] text-slate-600 hover:bg-slate-50"><span>{open ? '▾' : '▴'}</span>{open ? '접기' : '펴기'}</button>}
      </div>

      {why && (
        <p className="shrink-0 border-b border-slate-200 bg-slate-50 px-5 py-2 text-[13px]">
          {why === 'p' && <>예측 = 실적 {p.actual_qty} + 최근 1시간 속도 {p.rate_per_hour}개/시 × 남은 {Math.round(p.left_work_min)}분 (추정, 시작 1시간 안은 평균 속도). 예측이 총 목표의 90%({p.risk_line_qty}개) 미만이면 ▲ — DOC-07 §8</>}
          {why === 'k' && <>가동률 = 가동 {kp.apt_min}분 ÷ 계획 {kp.pbt_min}분 · 성능 = 7.0분 × 생산 {kp.pq}개 ÷ 가동 {kp.apt_min}분 · 양품률 = 양품 {kp.good_qty} ÷ 생산 {kp.pq} (DOC-07 §6.2). 주의: 가동률 60% 미만(OP-30 설비별)·OEE 59% 미만</>}
          {why === 'l' && <>고장 손실 {p.failure_loss_qty}개 (필수 정지 시간 ÷ 기준 사이클) + 속도 손실 {p.speed_loss_qty}개 (병목 구간). 순간 정지 {p.short_stops.count}건 {p.short_stops.minutes}분. 나눈 값은 교대 보고서 [4]·[5]</>}
        </p>
      )}

      {open && (
        <div className="grid min-h-0 flex-1 grid-cols-[1fr_1.45fr_1.6fr]">
          {/* 시간대별 실적 */}
          <section className="flex min-h-0 flex-col border-r border-slate-200 p-4">
            <div className="mb-2 flex items-baseline justify-between"><b className="text-[17px]">시간대별 실적</b>
              <span className="text-[12px] text-slate-500"><span className="text-[#0f9fbd]">━</span> 실적 <b>┅</b> 예측 <span className="text-slate-400">┈</span> 총 목표</span></div>
            <div className="min-h-0 flex-1 rounded-lg border border-slate-200 p-2"><Graph p={p} /></div>
          </section>

          {/* [11] 작업지시 진행 */}
          <section className="flex min-h-0 flex-col border-r border-slate-200 p-4">
            <div className="mb-2 flex items-baseline justify-between"><b className="text-[17px]">작업지시 진행</b><span className="text-[12px] text-slate-500">행을 누르면 로트 화면</span></div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <table className="w-full text-left text-[14px]">
                <thead className="sticky top-0 bg-slate-50 text-[13px] text-slate-500"><tr>{['작업지시', '진행 (완료/목표)', '공정', '납기', '상태'].map((h) => <th key={h} className="px-2 py-2 font-semibold">{h}</th>)}</tr></thead>
                <tbody>{orders.map((o) => <OrderTr key={o.order_no} o={o} onClick={() => go('lots', o.lots[o.lots.length - 1] ?? null)} />)}</tbody>
              </table>
            </div>
          </section>

          {/* [6] 설비 */}
          <section className="flex min-h-0 flex-col p-4 text-[15px]">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <b className="font-mono text-[22px]">{MACHINES[selId].name}</b>
              <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[13px]">{MACHINES[selId].op}</span>
              <span className="rounded-full border border-slate-300 px-3 py-0.5 text-[14px] font-semibold" style={{ color: sv.color }}>{sv.icon} {sv.text} {E.state_code} · {E.minutes}분째</span>
              {!selected && <span className="ml-auto text-[12px] text-slate-500">처음 열면 {user.role === 'OPR' ? '담당 공정' : '병목 공정'}</span>}
            </div>
            {cur && (
              <div className={`mb-3 flex items-center justify-between rounded-lg border px-4 py-2 ${tone}`}>
                <b className="text-[16px]">{mark(cur)} {alarmTitle(cur.alarm, cur.code)}</b>
                <button onClick={() => openCard(cur.id)} className="h-10 rounded-md border border-slate-300 bg-white px-4 text-[14px] font-semibold text-[#26303a] hover:bg-slate-50">지침카드 →</button>
              </div>
            )}
            <dl className="grid min-h-0 flex-1 grid-cols-[170px_1fr] content-start gap-x-3 gap-y-1.5 overflow-y-auto">
              {!cur && <><dt className="text-slate-500">현재 알람</dt><dd>없음</dd></>}
              {rows}
            </dl>
            <div className="mt-3 flex shrink-0 gap-3">
              <button onClick={() => go('stops')} className={obtn}>정지 사유</button>
              {isOp30 && <button onClick={() => go('tools', eq)} className={obtn}>공구 수명</button>}
              <button onClick={() => selectMachine(selId)} className="h-12 flex-1 rounded-lg bg-[#1f2933] text-[15px] font-semibold text-white hover:bg-black">설비 상세</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

// 서버는 완료를 COMPLETED와 DONE 두 가지로 보낸다
const isDone = (o: OrderRow) => o.status === 'COMPLETED' || o.status === 'DONE';

function OrderTr({ o, onClick }: { o: OrderRow; onClick: () => void }) {
  const doneAll = isDone(o);
  const [txt, cls] = o.delay ? [o.delay, 'bg-[#fff3d6] text-[#7a4e00]'] : doneAll ? ['완료', 'bg-[#e6f6ec] text-[#13994f]'] : o.status === 'IN_PROGRESS' ? ['생산 중', 'bg-[#e6f6fa] text-[#0f6f86]'] : o.status === 'WAITING' ? ['대기', 'bg-slate-100 text-slate-600'] : [o.status, 'bg-slate-100 text-slate-600'];
  const color = doneAll ? '#22a35a' : o.delay ? '#e0a040' : '#0f9fbd';
  return (
    <tr onClick={onClick} className="cursor-pointer border-b border-slate-100 hover:bg-slate-50">
      <td className="px-2 py-1.5"><div className="font-mono font-semibold">{o.order_no}</div><div className="text-[12px] text-slate-500">로트 {o.lots.map((l) => l.slice(-2)).join(',') || '—'} · 불량 {o.defect_qty}</div></td>
      <td className="px-2 py-1.5"><div className="flex items-center gap-2"><div className="w-24"><Bar pct={(o.done_qty / Math.max(o.order_qty, 1)) * 100} color={color} /></div><span className="font-mono">{o.done_qty}/{o.order_qty}</span></div></td>
      <td className="px-2 py-1.5 font-mono">{o.current_process}</td>
      <td className="px-2 py-1.5 font-mono">{md(o.due_at)}</td>
      <td className="px-2 py-1.5"><span className={`whitespace-nowrap rounded-md px-2 py-0.5 text-[13px] font-semibold ${cls}`}>{txt}</span></td>
    </tr>
  );
}

// [7] 시간대별 실적 그래프 (총 목표선 · 실적 곡선 · 예측 점선 · 2시간 눈금) — 교대 9시간
function Graph({ p }: { p: Production }) {
  const W = 440, H = 240, L = 6, B = 22, t0 = Date.parse(p.start_at), t1 = Date.parse(p.end_at);
  // 1.15 = 위쪽 글자 여백
  const max = Math.max(p.total_target_qty, p.forecast_qty, p.actual_qty, 1) * 1.15;
  const x = (t: number) => L + ((t - t0) / (t1 - t0)) * (W - L * 2), y = (v: number) => (H - B) - (v / max) * (H - B - 4);
  const pts = p.hourly.map((h) => `${x(Date.parse(h.at)).toFixed(1)},${y(h.cum).toFixed(1)}`);
  const last = p.hourly[p.hourly.length - 1];
  const ticks: number[] = []; for (let t = t0; t <= t1; t += 2 * 3600e3) ticks.push(t);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="시간대별 실적 그래프">
      {[0.25, 0.5, 0.75].map((f) => <line key={f} x1={L} x2={W - L} y1={(H - B) * f} y2={(H - B) * f} stroke="#eef1f4" />)}
      <line x1={L} x2={W - L} y1={y(p.total_target_qty)} y2={y(p.total_target_qty)} stroke="#56616c" strokeDasharray="2 3" />
      <text x={L + 2} y={y(p.total_target_qty) - 5} fontSize="13" fill="#56616c">총 목표 {p.total_target_qty}</text>
      {pts.length > 1 && <polygon points={`${pts[0].split(',')[0]},${H - B} ${pts.join(' ')} ${pts[pts.length - 1].split(',')[0]},${H - B}`} fill="#0f9fbd" opacity="0.08" />}
      <polyline points={pts.join(' ')} fill="none" stroke="#0f9fbd" strokeWidth="2.5" />
      {last && <line x1={x(Date.parse(last.at))} y1={y(last.cum)} x2={W - L} y2={y(p.forecast_qty)} stroke="#4b5a69" strokeDasharray="5 4" strokeWidth="2" />}
      {last && <text x={x(Date.parse(last.at))} y={y(last.cum) - 8} fontSize="14" fontWeight="700" textAnchor="middle" fill="#0f6f86">{last.cum}</text>}
      {last && <text x={W - L} y={y(p.forecast_qty) + 16} fontSize="12" textAnchor="end" fill="#4b5a69">예측 {p.forecast_qty}</text>}
      {/* 시각 글자는 시연 시각 문자열 기준 (Date 시간대 변환 안 함) */}
      {ticks.map((t, i) => <text key={t} x={x(t)} y={H - 4} fontSize="12" textAnchor={i === 0 ? 'start' : 'middle'} fill="#8a97a4">{String((Number(p.start_at.slice(11, 13)) + i * 2) % 24).padStart(2, '0')}{p.start_at.slice(13, 16)}</text>)}
    </svg>
  );
}
