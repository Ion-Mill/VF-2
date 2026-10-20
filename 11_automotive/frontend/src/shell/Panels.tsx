'use client';
// SCR-04·05 하단 (페이지구조 v3): 왼쪽 생산현황 [7]~[9] · 오른쪽 작업지시 진행 [11] (보전 담당은 정비 현황), 설비를 누르면 오른쪽이 그 설비 [6]. 값 = 시연 데이터 서버.
// field = SCR-26 현장 보기: 설비를 눌렀을 때 그 설비 [6]만 — 지금 알람·지침카드를 맨 위에 크게, 나머지는 작게. 생산 지표·작업지시 표는 SCR-04에만.
import { useEffect, useState } from 'react';
import type { MachineId } from '@/components/types';
import { useApp } from './ctx';
import { ID_OF, MACHINES, STATE_VIEW, stateOf } from './data';
import { hm, md, type Eq, type OrderRow, type Production } from './live';
import { alarmTitle, type AlertRec } from './model';

const AMBER = '#9a6200';
const lbl = 'text-[14px] text-slate-500';
const num = 'font-mono font-bold tabular-nums';

function useSize<T extends HTMLElement>() { // 칸이 나중에 그려져도 잡히게 콜백 ref
  const [el, setEl] = useState<T | null>(null), [sz, setSz] = useState({ w: 0, h: 0 });
  useEffect(() => { if (!el) return; const ro = new ResizeObserver(([e]) => setSz({ w: e.contentRect.width, h: e.contentRect.height })); ro.observe(el); return () => ro.disconnect(); }, [el]);
  return [setEl, sz] as const;
}

function Bar({ pct, color = '#4b5a69' }: { pct: number; color?: string }) {
  return <div className="h-2 w-full rounded-full bg-slate-200"><div className="h-2 rounded-full" style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: `linear-gradient(180deg,rgba(255,255,255,.5),rgba(255,255,255,0) 55%,rgba(0,0,0,.12)), ${color}`, boxShadow: `0 0 6px ${color}66` }} /></div>;
}

export default function Panels({ field = false, ids }: { field?: boolean; ids?: MachineId[] }) {
  const { twin, alerts, wos, selected, go, openCard, openWo, user, selectMachine, pm } = useApp();
  const [why, setWhy] = useState<string | null>(null);
  const [showDone, setShowDone] = useState(false); // 작업지시 완료 줄 접기 (훅이라 아래 return들보다 위)
  // 이브 창이 열려 아래 칸 전체가 좁아지면 (한 칸 560px 미만) 시안 A: 왼쪽 = 생산현황 위·OEE 아래로 쌓기, 오른쪽 = 작업지시 두 줄 목록 (사용자 선택 2026-10-19). 훅이라 아래 return들보다 위
  const [rootBox, rootSz] = useSize<HTMLDivElement>(); const narrow = rootSz.w > 0 && rootSz.w < 1150;
  const tight = rootSz.h > 0 && rootSz.h < 330; // 아래 칸이 낮으면 OEE 칸을 납작하게 (막대 빼고 여백 줄임) — 칸 밖으로 튀어나가지 않게
  // "정지 사유 미입력" 줄은 뺐다 (2026-10-19 정지 사유 화면 삭제 — 사유는 시스템이 붙인다)
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
  const kp = isOp30 && selected ? k[eq] : k.LINE;
  const wo = wos.find((w) => w.machine === selId && w.state !== 'done' && w.state !== 'cancelled');
  const proc = twin.process[E.process_code] ?? { pq: 0 };
  const done = p.actual_qty >= p.total_target_qty;
  const toggle = (w: string) => setWhy(why === w ? null : w);
  // 진행 중·대기 먼저, 완료는 뒤 (스크롤)
  const orders = [...twin.orders].sort((a, b) => Number(isDone(a)) - Number(isDone(b)));
  // [6] 설비 칸 (SCR-04와 현장 보기가 같이 씀 — 현재 알람 줄은 화면마다 따로)
  const rows = (<>
    <dt className="text-slate-500">현재 로트</dt><dd>{E.lot_no ? <button onClick={() => go('lots', E.lot_no)} className="font-mono font-semibold text-[#5a3bc8] underline">{E.lot_no}</button> : '—'}</dd>
    <dt className="text-slate-500">교대 실적/목표</dt><dd>{E.process_code} <b className={num}>{proc.pq}</b> / <b className={num}>{p.total_target_qty}</b> <span className="text-slate-500">{isOp30 ? `(2대 합, 이 설비 ${E.shift_actual_qty})` : ''}</span></dd>
    <dt className="text-slate-500">오늘 정지</dt><dd><b className={num}>{E.stop_min}</b>분 <span className="text-slate-500">대기·막힘·준비 포함 · 고장 손실 약 {E.loss_qty}개</span></dd>

    {isOp30 && (<>
      <dt className="text-slate-500">공구 수명</dt>
      <dd className="flex flex-wrap gap-x-3 gap-y-1">{E.tools.map((t) => (
        <span key={t.tool_id} className="w-[88px]" style={{ color: t.warn ? AMBER : undefined }}>
          <span className="flex justify-between font-mono text-[13px]"><span>{t.tool_no}</span><b>{t.usage_pct}%{t.warn ? ' ▲' : ''}</b></span><Bar pct={t.usage_pct} color={t.warn ? '#e0a040' : '#4b5a69'} />
        </span>))}</dd>
      <dt className="text-slate-500">진행 중 작업지시서</dt><dd>{wo ? <button onClick={() => openWo(wo.no)} className="font-semibold text-[#5a3bc8] underline">{wo.no} {wo.code}</button> : '없음'}</dd>
    </>)}
    {E.sensor && (user.role === 'MNT' || user.role === 'MGR') && (<>
      <dt className="text-slate-500">센서 (1분 평균)</dt><dd className="text-[14px]">주축 부하 {E.sensor.SpindleLoadPct}% · 모터 {E.sensor.SpindleMotorTemp}℃ · 공기 {E.sensor.AirPressure} psi ({(E.sensor.AirPressure * 0.0689476).toFixed(2)} bar)</dd>
    </>)}
  </>);
  const tone = !cur ? '' : cur.level === '긴급' ? 'border-[#e8a0a2] bg-[#fdeeee] text-[#c62a2f]' : cur.level === '주의' ? 'border-[#ecd28e] bg-[#fff8e6] text-[#7a4e00]' : 'border-slate-200 bg-slate-50';
  const mark = (a: AlertRec) => (a.level === '긴급' ? '⚠' : a.level === '주의' ? '▲' : 'ⓘ');

  // 현장 보기 공정 묶음 버튼 (사용자 선택 2026-10-19): 담당 설비 2대를 반씩 — 알람 난 칸만 빨강·노랑 테두리
  if (field && ids && ids.length > 1) return (
    <div className="grid h-full grid-cols-2 gap-3 bg-[#eef1f4] p-3 text-[#26303a]">{ids.map((id) => {
      const q = MACHINES[id].eq!, Q = twin.equipment[q], v = STATE_VIEW[stateOf(Q)];
      const a = [...alerts].reverse().find((x) => x.machine === id && !x.handled);
      const pq = (twin.process[Q.process_code] ?? { pq: 0 }).pq;
      const ring = !a ? 'border-slate-200' : a.level === '긴급' ? 'border-2 border-[#d23a35] shadow-[0_0_0_3px_rgba(229,72,77,.18)]' : 'border-2 border-[#e0a100] shadow-[0_0_0_3px_rgba(240,180,41,.2)]';
      return (
        <section key={id} className={`flex min-h-0 min-w-0 flex-col gap-2 rounded-2xl border bg-white px-4 py-3 ${ring}`}>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => selectMachine(id)} className="font-mono text-[22px] font-bold hover:underline">{MACHINES[id].name}</button>
            <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[13px]">{MACHINES[id].op}</span>
            <span className="rounded-full border border-slate-300 px-2.5 py-0.5 text-[15px] font-bold" style={{ color: v.color }}>{v.icon} {v.text} · {Q.minutes}분째</span>
          </div>
          {a ? (
            <div className={`flex items-center gap-2 rounded-xl px-3 py-2 ${a.level === '긴급' ? 'bg-[#fdeeee] text-[#b4282d]' : 'bg-[#fff8e6] text-[#7a4e00]'}`}>
              <b className="min-w-0 flex-1 truncate text-[16px]">{mark(a)} {alarmTitle(a.alarm, a.code)}</b>
              <button onClick={() => openCard(a.id)} className="h-9 shrink-0 rounded-full bg-[#1f2933] px-3 text-[14px] font-bold text-white">지침카드 →</button>
            </div>
          ) : <div className="rounded-xl bg-slate-50 px-3 py-2 text-[16px] font-semibold text-slate-500">지금 알람 없음</div>}
          <dl className="grid grid-cols-[120px_1fr] gap-x-2 gap-y-1 text-[15px]">
            <dt className="text-slate-500">현재 로트</dt><dd className="truncate">{Q.lot_no ? <button onClick={() => go('lots', Q.lot_no)} className="font-mono font-semibold text-[#5a3bc8] underline">{Q.lot_no}</button> : '—'}</dd>
            <dt className="text-slate-500">교대 실적/목표</dt><dd><b className={num}>{pq}</b> / <b className={num}>{p.total_target_qty}</b>{MACHINES[id].op === 'OP-30' && <span className="text-slate-500"> (2대 합, 이 설비 {Q.shift_actual_qty})</span>}</dd>
            <dt className="text-slate-500">오늘 정지</dt><dd><b className={num}>{Q.stop_min}</b>분</dd>
          </dl>
        </section>);
    })}</div>
  );

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

  // 오른쪽: 설비를 누르면 그 설비 정보 (닫으면 원래 칸, 페이지구조 v3 N9-C). 원래 칸은 계정마다 다름 (3.1)
  const right = selected && selected !== 'inf' ? 'eq' : user.role === 'MNT' ? 'maint' : 'orders';
  const myOrders = user.role === 'OPR' ? orders.filter((o) => user.procs.includes(o.current_process)) : user.role === 'MGR' ? [...orders].sort((a, b) => Number(!a.delay) - Number(!b.delay)) : orders;
  const openFaults = [...alerts].filter((a) => !a.handled && a.kind !== 'guide').reverse();
  const pmSoon = (pm?.tasks ?? []).filter((t) => t.state === 'OVERDUE' || t.state === 'DUE_SOON');
  const stopMax = Math.max(1, ...Object.values(twin.equipment).map((e) => e.stop_min));
  const sec = 'flex min-h-0 flex-col rounded-3xl border border-slate-200 bg-white p-4 shadow-xl';

  // 생산현황·OEE 조각 (넓을 때는 한 칸 안에, 좁을 때는 두 칸으로 나눠 씀)
  const shiftTag = <span className="text-[14px] font-normal text-slate-500">({p.shift_type === 'DAY' ? '주간' : '야간'})</span>; // 교대 시각·범례 줄은 뺌 (사용자 요청 2026-10-19)
  // 생산 숫자는 그래프 칸 안 위쪽에 (사용자 요청 2026-10-20, 시안: 큰 숫자 + 오른쪽 위 예측 알약 → 아래 그래프). 진행 막대는 그래프가 대신함
  const ahead = p.forecast_qty >= p.total_target_qty;
  const pill = done ? ['달성', '#5a3bc8', '#f0ebff'] : p.risk ? [`예측 ${p.forecast_qty} · ▲ 미달 위험`, AMBER, '#fff4e0'] : [`예측 ${p.forecast_qty} · ${ahead ? '목표 넘김 예상' : '진행 중'}`, ahead ? '#1f7a45' : '#4b5a69', ahead ? '#e6f6ec' : '#eef1f4'];
  const graphBox = (noTargetText: boolean) => (
    <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-slate-200 p-2">
      <button onClick={() => toggle('p')} className="flex shrink-0 items-start justify-between gap-2 px-1 text-left">
        <div className="whitespace-nowrap"><span className={`${num} text-[34px] leading-none`}>{p.actual_qty}</span><span className="font-mono text-[22px] text-slate-500"> / {p.total_target_qty}</span><span className="text-[16px] text-slate-500"> 개</span></div>
        <span className="truncate rounded-full px-2.5 py-1 text-[12.5px] font-bold" style={{ color: pill[1], background: pill[2] }}>{pill[0]}</span>
      </button>
      <div className="min-h-0 flex-1"><Graph p={p} noTargetText={noTargetText} /></div>
    </div>
  );
  // OEE: 세 지표 이름·숫자를 크고 진하게 (사용자 요청 2026-10-19 — 작은 회색 글자가 안 읽혀서)
  // 넓을 때는 손실도 네 번째 칸으로 (따로 한 줄이면 카드 아래가 잘려서, 2026-10-19). 네 칸 모두 같은 글꼴: 이름 = 본문 14px, 숫자 = 고정폭 20px, 단위 '개'는 숫자 바로 옆
  const tile = `flex min-w-0 flex-col rounded-lg bg-slate-50 px-3 text-left ${tight ? 'gap-1 py-1.5' : 'gap-1.5 py-2'}`;
  const tileName = 'whitespace-nowrap text-[14px] font-semibold text-slate-600';
  const tileNum = `${num} whitespace-nowrap text-[20px] leading-none`;
  const oeeTiles = (withLoss: boolean) => (
    <div className={`grid ${withLoss ? 'grid-cols-4' : 'grid-cols-3'} gap-2`}>
      {([['가동률', kp.availability_pct, kp.warn.includes('가동률')], ['성능', kp.performance_pct, false], ['양품률', kp.quality_pct, false]] as const).map(([t, v, w]) => (
        <button key={t} onClick={() => toggle('k')} className={tile}>
          <span className={tileName}>{t}</span>
          <b className={tileNum} style={{ color: w ? AMBER : '#26303a' }}>{v ?? '—'}{w ? ' ▲' : ''}</b>
          {!tight && <Bar pct={v ?? 0} color={w ? AMBER : '#4b5a69'} />}
        </button>))}
      {withLoss && (
        <button onClick={() => toggle('l')} className={tile}>
          <span className={tileName}>손실 <span className="font-normal text-slate-500">추정</span></span>
          <b className={tileNum} style={{ color: '#26303a' }}>{Math.round(p.loss_qty)}<span className={`${tileName} ml-1 font-sans`}>개</span></b>
          {!tight && <div className="h-2" />}
        </button>)}
    </div>
  );
  const oeeHead = <div className="flex items-baseline justify-between"><span className="text-[15px] font-semibold text-slate-600">OEE <span className="text-[13px] font-normal text-slate-500">{isOp30 && selected ? eq : '라인'}</span></span><span className={`${num} ${tight ? 'text-[24px]' : 'text-[28px]'} leading-none`} style={{ color: kp.warn.includes('OEE') ? AMBER : undefined }}>{kp.oee_pct ?? '—'}%{kp.warn.includes('OEE') ? ' ▲' : ''}</span></div>;
  const whyBox = (keys: string[]) => why && keys.includes(why) && (
    <p className="mt-2 shrink-0 rounded bg-slate-50 px-3 py-2 text-[12px]">
      {why === 'p' && <>예측 {p.forecast_qty}개 = 실적 {p.actual_qty} + 최근 1시간 속도 {p.rate_per_hour}개/시 × 남은 {Math.round(p.left_work_min)}분 (추정). 예측이 총 목표의 90%({p.risk_line_qty}개) 미만이면 ▲ — DOC-07 §8</>}
      {why === 'k' && <>가동률 = 가동 {kp.apt_min}분 ÷ 계획 {kp.pbt_min}분 · 성능 = 7.0분 × 생산 {kp.pq}개 ÷ 가동 {kp.apt_min}분 · 양품률 = 양품 {kp.good_qty} ÷ 생산 {kp.pq} (DOC-07 §6.2)</>}
      {why === 'l' && <>고장 손실 {p.failure_loss_qty}개 + 속도 손실 {p.speed_loss_qty}개. 순간 정지 {p.short_stops.count}건 {p.short_stops.minutes}분</>}
    </p>
  );

  return (
    <div ref={rootBox} className="grid h-full grid-cols-2 gap-4 text-[#26303a]">
      {narrow ? (
        /* 좁을 때 왼쪽: 생산현황(그래프 + 생산 숫자) 위, OEE 아래 */
        <div className="grid min-h-0 min-w-0 grid-rows-[minmax(0,1fr)_auto] gap-4">
          <section className={sec}>
            <div className="mb-1"><b className="text-[17px]">생산현황 {shiftTag}</b></div>
            {graphBox(true)}
            {whyBox(['p'])}
          </section>
          <section className={`${sec} justify-center`}>{/* 좁을 때 OEE는 한 줄: 왼쪽 OEE %·손실, 오른쪽 세 지표 — 생산현황 그래프 높이를 남기려고 */}
            <div className="flex items-center gap-4">
              <div className="flex shrink-0 flex-col gap-1">
                <button onClick={() => toggle('k')} className="text-left"><span className="text-[15px] font-semibold text-slate-600">OEE <span className="text-[13px] font-normal text-slate-500">{isOp30 && selected ? eq : '라인'}</span></span>
                  <div className={`${num} text-[30px] leading-tight`} style={{ color: kp.warn.includes('OEE') ? AMBER : undefined }}>{kp.oee_pct ?? '—'}%{kp.warn.includes('OEE') ? ' ▲' : ''}</div></button>
                <button onClick={() => toggle('l')} className="whitespace-nowrap text-left text-[14px] font-semibold text-slate-600">손실 약 <b className={`${num} text-[18px] text-[#26303a]`}>{Math.round(p.loss_qty)}</b>개</button>
              </div>
              <div className="min-w-0 flex-1">{oeeTiles(false)}</div>
            </div>
            {whyBox(['k', 'l'])}
          </section>
        </div>
      ) : (
      /* 넓을 때 왼쪽: 생산현황 전부 */
      <section className={sec}>
        <div className="mb-2"><b className="text-[17px]">생산현황 {shiftTag}</b></div>
        <div className="grid min-h-0 flex-1 grid-cols-[1fr_1.25fr] gap-4">
          <div className="flex min-h-0 min-w-0 flex-col">{graphBox(false)}</div>
          <div className="flex min-h-0 min-w-0 flex-col justify-center gap-2">
            <div className="flex flex-col gap-2"><button onClick={() => toggle('k')} className="text-left">{oeeHead}</button>{oeeTiles(true)}</div>
          </div>
        </div>
        {whyBox(['p', 'k', 'l'])}
      </section>
      )}

      {/* 오른쪽 */}
      <section className={sec}>
        {right === 'eq' && (<>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <b className="font-mono text-[20px]">{MACHINES[selId].name}</b>
            <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[13px]">{MACHINES[selId].op}</span>
            <span className="rounded-full border border-slate-300 px-3 py-0.5 text-[14px] font-semibold" style={{ color: sv.color }}>{sv.icon} {sv.text} · {E.minutes}분째</span>
            <button onClick={() => selectMachine(null)} className="ml-auto h-10 rounded-md border border-slate-300 px-3 text-[14px] font-semibold hover:bg-slate-50">닫기 ✕</button>
          </div>
          {cur && (
            <div className={`mb-2 flex items-center justify-between rounded-lg border px-4 py-2 ${tone}`}>
              <b className="text-[15px]">{mark(cur)} {alarmTitle(cur.alarm, cur.code)}</b>
              <button onClick={() => openCard(cur.id)} className="h-10 rounded-md border border-slate-300 bg-white px-4 text-[14px] font-semibold text-[#26303a] hover:bg-slate-50">지침카드 →</button>
            </div>
          )}
          <dl className="grid min-h-0 flex-1 grid-cols-[150px_1fr] content-start gap-x-3 gap-y-1.5 overflow-y-auto text-[14px]">
            {!cur && <><dt className="text-slate-500">현재 알람</dt><dd>없음</dd></>}
            {rows}
          </dl>
        </>)}

        {right === 'orders' && (<>
          <div className="mb-2 flex items-baseline justify-between"><b className="text-[17px]">작업지시 진행{user.role === 'OPR' ? ` · 내 공정 (${user.procs.join('·')})` : ''}</b>
            <span className="truncate pl-2 text-[12px] text-slate-500">{user.role === 'MGR' ? '납기 위험 먼저 · ' : ''}{narrow ? '누르면 로트 화면' : '행을 누르면 로트 화면'}</span></div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {myOrders.length === 0 ? <p className="p-2 text-slate-500">지금 내 공정에 있는 작업지시가 없습니다.</p> : (
              narrow ? (
              <div className="flex flex-col">
                {myOrders.filter((o) => !isDone(o)).map((o) => <OrderLi key={o.order_no} o={o} onClick={() => go('lots', o.lots[o.lots.length - 1] ?? null)} />)}
                {myOrders.some(isDone) && <button onClick={() => setShowDone((v) => !v)} className="w-full py-2 text-left text-[13px] font-semibold text-slate-500 hover:bg-slate-50">{showDone ? '▴ 완료 접기' : `▾ 완료 ${myOrders.filter(isDone).length}건 보기`}</button>}
                {showDone && myOrders.filter(isDone).map((o) => <OrderLi key={o.order_no} o={o} onClick={() => go('lots', o.lots[o.lots.length - 1] ?? null)} />)}
              </div>
              ) :
              <table className="w-full text-left text-[14px]">
                <thead className="sticky top-0 bg-slate-50 text-[13px] text-slate-500"><tr>{['작업지시', '진행 (완료/목표)', '공정', '납기', '상태'].map((h) => <th key={h} className="px-2 py-2 font-semibold">{h}</th>)}</tr></thead>
                <tbody>
                  {myOrders.filter((o) => !isDone(o)).map((o) => <OrderTr key={o.order_no} o={o} onClick={() => go('lots', o.lots[o.lots.length - 1] ?? null)} />)}
                  {myOrders.some(isDone) && <tr><td colSpan={5}><button onClick={() => setShowDone((v) => !v)} className="w-full py-2 text-left text-[13px] font-semibold text-slate-500 hover:bg-slate-50">{showDone ? '▴ 완료 접기' : `▾ 완료 ${myOrders.filter(isDone).length}건 보기`}</button></td></tr>}
                  {showDone && myOrders.filter(isDone).map((o) => <OrderTr key={o.order_no} o={o} onClick={() => go('lots', o.lots[o.lots.length - 1] ?? null)} />)}
                </tbody>
              </table>
            )}
          </div>
        </>)}

        {right === 'maint' && (<>
          <b className="mb-2 text-[17px]">정비 현황</b>
          <div className="grid min-h-0 flex-1 grid-cols-3 gap-3 text-[14px]">
            <div className="flex min-h-0 flex-col">
              <span className={lbl}>처리 안 된 고장 알람 <b className="text-[#26303a]">{openFaults.length}</b></span>
              <ul className="mt-1 min-h-0 flex-1 overflow-y-auto">{openFaults.slice(0, 20).map((a) => (
                <li key={a.id}><button onClick={() => openCard(a.id)} className="w-full border-l-4 py-1 pl-2 text-left hover:bg-slate-50" style={{ borderColor: a.level === '긴급' ? '#c62a2f' : a.level === '주의' ? '#e0892a' : '#94a3b8' }}>
                  <b>{MACHINES[a.machine].name} {a.code}</b> <span className="text-slate-500">{hm(a.time)}</span><div className="truncate text-[12px] text-slate-600">{alarmTitle(a.alarm, a.code)}</div>
                </button></li>))}{openFaults.length === 0 && <li className="text-slate-500">없음</li>}</ul>
            </div>
            <div className="flex min-h-0 flex-col">
              <span className={lbl}>오늘 정지 (분)</span>
              <ul className="mt-1 flex flex-col gap-1.5">{Object.entries(twin.equipment).map(([id, e]) => (
                <li key={id} className="grid grid-cols-[62px_1fr_40px] items-center gap-2"><span className="font-mono text-[13px]">{id}</span><Bar pct={(e.stop_min / stopMax) * 100} color={e.state_code === 'DOWN' ? '#c62a2f' : '#4b5a69'} /><b className={`${num} text-right`}>{e.stop_min}</b></li>))}</ul>
            </div>
            <div className="flex min-h-0 flex-col">
              <span className={lbl}>예방 정비 기한 임박 <b className="text-[#26303a]">{pmSoon.length}</b></span>
              <ul className="mt-1 min-h-0 flex-1 overflow-y-auto">{pmSoon.slice(0, 12).map((t, i) => (
                <li key={i}><button onClick={() => go('pm')} className="w-full py-1 text-left hover:bg-slate-50">
                  <b style={{ color: t.state === 'OVERDUE' ? AMBER : undefined }}>{t.state === 'OVERDUE' ? '▲ 기한 넘김' : 'ⓘ 임박'}</b> {t.equipment_id}<div className="truncate text-[12px] text-slate-600">{t.item_name} · {md(t.next_due)}</div>
                </button></li>))}{pmSoon.length === 0 && <li className="text-slate-500">없음</li>}</ul>
            </div>
          </div>
        </>)}
      </section>
    </div>
  );
}

// 서버는 완료를 COMPLETED와 DONE 두 가지로 보낸다
const isDone = (o: OrderRow) => o.status === 'COMPLETED' || o.status === 'DONE';

// 작업지시 상태 글자·색 (표 줄과 좁을 때 목록 줄이 같이 씀)
function orderLook(o: OrderRow) {
  const doneAll = isDone(o);
  const [txt, cls] = o.delay ? [o.delay, 'bg-[#fff3d6] text-[#7a4e00]'] : doneAll ? ['완료', 'bg-[#e6f6ec] text-[#13994f]'] : o.status === 'IN_PROGRESS' ? ['생산 중', 'bg-[#e6f6fa] text-[#5a3bc8]'] : o.status === 'WAITING' ? ['대기', 'bg-slate-100 text-slate-600'] : [o.status, 'bg-slate-100 text-slate-600'];
  return { txt, cls, color: doneAll ? '#22a35a' : o.delay ? '#e0a040' : '#3d4a5c' };
}

// 좁을 때 작업지시 한 건 = 두 줄 (윗줄 번호·상태, 아랫줄 진행·공정·납기). 번호·공정은 줄바꿈 안 함
function OrderLi({ o, onClick }: { o: OrderRow; onClick: () => void }) {
  const { txt, cls, color } = orderLook(o);
  return (
    <button onClick={onClick} className="w-full border-b border-slate-100 px-1 py-2 text-left hover:bg-slate-50">
      <div className="flex items-center gap-2 whitespace-nowrap"><span className="font-mono text-[15px] font-semibold">{o.order_no}</span><span className={`ml-auto rounded-md px-2 py-0.5 text-[13px] font-semibold ${cls}`}>{txt}</span></div>
      <div className="mt-1 flex items-center gap-2 whitespace-nowrap text-[13px] text-slate-500">
        <div className="min-w-[48px] flex-1"><Bar pct={(o.done_qty / Math.max(o.order_qty, 1)) * 100} color={color} /></div>
        <span className="font-mono text-[#26303a]">{o.done_qty}/{o.order_qty}</span>· <span className="font-mono">{o.current_process}</span>· 납기 <span className="font-mono">{md(o.due_at)}</span>
      </div>
    </button>
  );
}

function OrderTr({ o, onClick }: { o: OrderRow; onClick: () => void }) {
  const { txt, cls, color } = orderLook(o);
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
// noTargetText: 이브 창이 열려 좁을 때 "총 목표 N" 글자를 뺀다 — 낮은 칸에서 실적 선·알약과 겹쳐서, 목표는 옆 "실적 / 목표"에 있음 (사용자 요청 2026-10-20)
function Graph({ p, noTargetText = false }: { p: Production; noTargetText?: boolean }) {
  const [box, sz] = useSize<HTMLDivElement>();
  // 칸 크기 그대로 그린다 (전에는 최소 160×90이라 이브 창이 열려 칸이 작아지면 테두리 밖으로 튀어나갔음, 2026-10-20)
  return <div ref={box} className="h-full w-full overflow-hidden">{sz.w > 0 && sz.h > 0 && <GraphSvg p={p} W={sz.w} H={sz.h} noTargetText={noTargetText} />}</div>;
}
function GraphSvg({ p, W, H, noTargetText }: { p: Production; W: number; H: number; noTargetText: boolean }) {
  const L = 6, B = 22, t0 = Date.parse(p.start_at), t1 = Date.parse(p.end_at);
  // 1.15 = 위쪽 글자 여백
  const max = Math.max(p.total_target_qty, p.forecast_qty, p.actual_qty, 1) * 1.15;
  const x = (t: number) => L + ((t - t0) / (t1 - t0)) * (W - L * 2), y = (v: number) => (H - B) - (v / max) * (H - B - 4);
  const pts = p.hourly.map((h) => `${x(Date.parse(h.at)).toFixed(1)},${y(h.cum).toFixed(1)}`);
  const last = p.hourly[p.hourly.length - 1];
  const step = W < 300 ? 4 : 2, ticks: number[] = []; for (let t = t0; t <= t1; t += step * 3600e3) ticks.push(t);
  // 실적 숫자 = 마지막 점 왼쪽 보라 알약 (칸이 낮아도 위로 잘리지 않게 칸 안에 가둠, 사용자 요청 2026-10-20). 글자 폭은 어림값
  const ax = last ? x(Date.parse(last.at)) : 0, ay = last ? y(last.cum) : 0, fy = 14; // '예측 N' = 칸 오른쪽 위 고정 (사용자 요청 2026-10-20, 전에는 예측 점선 끝 위)
  const aw = String(last?.cum ?? '').length * 8 + 14, px = Math.max(L, ax - 7 - aw), py = Math.min(H - B - 9, Math.max(10, ay));
  const fx0 = W - L - (30 + String(p.forecast_qty).length * 8);
  // 알약과 '예측 N'이 겹치면 '예측 N'은 알약 아래로, 아래 자리도 없으면(칸이 낮음) 알약 왼쪽으로
  const clash = !!last && px + aw > fx0 - 4 && Math.abs(py - (fy - 5)) < 16, below = py + 23 <= H - B - 4;
  const fyL = !clash ? fy : below ? Math.max(y(p.forecast_qty) + 18, py + 23) : py + 4.5, fxL = clash && !below ? px - 6 : W - L;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="block" role="img" aria-label="시간대별 실적 그래프">
      {[0.25, 0.5, 0.75].map((f) => <line key={f} x1={L} x2={W - L} y1={(H - B) * f} y2={(H - B) * f} stroke="#eef1f4" />)}
      <line x1={L} x2={W - L} y1={y(p.total_target_qty)} y2={y(p.total_target_qty)} stroke="#56616c" strokeDasharray="2 3" />
      {/* 칸이 낮아 목표선이 위 끝에 붙으면 글자 윗부분이 잘려서 선 아래로 내린다 (2026-10-20) */}
      {!noTargetText && <text x={L + 2} y={y(p.total_target_qty) - 5 < 13 ? y(p.total_target_qty) + 14 : y(p.total_target_qty) - 5} fontSize="13" fill="#56616c" stroke="#fff" strokeWidth="3" paintOrder="stroke">총 목표 {p.total_target_qty}</text>}
      {pts.length > 1 && <polygon points={`${pts[0].split(',')[0]},${H - B} ${pts.join(' ')} ${pts[pts.length - 1].split(',')[0]},${H - B}`} fill="#7a52f0" opacity="0.08" />}
      <polyline points={pts.join(' ')} fill="none" stroke="#7a52f0" strokeWidth="2.5" />
      {last && <line x1={x(Date.parse(last.at))} y1={y(last.cum)} x2={W - L} y2={y(p.forecast_qty)} stroke="#4b5a69" strokeDasharray="5 4" strokeWidth="2" />}
      {last && <circle cx={ax} cy={ay} r="3.5" fill="#7a52f0" stroke="#fff" strokeWidth="1.5" />}
      {last && <g><rect x={px} y={py - 9} width={aw} height="18" rx="9" fill="#7a52f0" /><text x={px + aw / 2} y={py + 4.5} fontSize="13" fontWeight="700" textAnchor="middle" fill="#fff">{last.cum}</text></g>}
      {last && <text x={fxL} y={fyL} fontSize="13" fontWeight="600" textAnchor="end" fill="#4b5a69" stroke="#fff" strokeWidth="3" paintOrder="stroke">예측 {p.forecast_qty}</text>}
      {/* 시각 글자는 시연 시각 문자열 기준 (Date 시간대 변환 안 함) */}
      {ticks.map((t, i) => <text key={t} x={x(t)} y={H - 4} fontSize="12" textAnchor={i === 0 ? 'start' : 'middle'} fill="#8a97a4">{String((Number(p.start_at.slice(11, 13)) + i * step) % 24).padStart(2, '0')}{p.start_at.slice(13, 16)}</text>)}
    </svg>
  );
}
