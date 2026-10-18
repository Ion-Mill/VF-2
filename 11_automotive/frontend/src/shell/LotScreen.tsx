'use client';
// SCR-19 로트 추적 — 원자재 로트 → 공정 실적 → 알람 → 검사 → 완제품 입고 → 출하. 보류·해제 = API-LOT-02 (시뮬레이터: 보류하면 그 로트와 다음 2개 전수 검사).
// 화면 구조 (사용자 시안 2026-10-16): [번호로 찾기 + 원자재→생산 로트 + 고른 로트 강조 + 결정 필요] · [설비별 시간표] · [수량 | 보류·해제·폐기]
import { useEffect, useState } from 'react';
import { PAGE, useApp } from './ctx';
import { api, hm, md, tsOf, useFetch, usePersist } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;
const STATUS: Record<string, string> = { IN_PROCESS: '생산 중', WAIT_INSPECTION: '검사 대기', WAIT_JUDGEMENT: '판정 대기', HOLD_REVIEW: '보류 검토', ON_HOLD: '보류', PASSED: '합격', RELEASED: '해제', SCRAPPED: '폐기' };
const DECIDE = ['ON_HOLD', 'HOLD_REVIEW', 'WAIT_JUDGEMENT']; // 반장·관리자가 결정해야 하는 상태
const EQS: [string, string][] = [['SAW-01', 'OP-10 절단'], ['MIL-01', 'OP-20 황삭'], ['VF2-01', 'OP-30 정밀 가공'], ['VF2-02', 'OP-30 정밀 가공'], ['WSH-01', 'OP-40 디버링·세척'], ['CMM-01', 'OP-50 측정']];
const box = 'rounded-2xl border border-slate-300 bg-white p-5';
const chip = 'inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-[14px]';

export function LotScreen() {
  const { key, role, user, go, toast, twin } = useApp();
  const [lot, setLot] = useState<string>(key ?? twin?.suspect_lot ?? twin?.equipment['VF2-01'].lot_no ?? '');
  const [q, setQ] = useState('');
  const f = useFetch<{ lots: R[]; suspect_lot: string | null; materials: Record<string, Record<string, string>>; reports: R[]; alarms: R[] }>(`lots?lot=${encodeURIComponent(lot)}`, 10000, [lot]);
  const [scrapOk, setScrapOk] = usePersist<Record<string, string>>('scrapOk', {}, twin?.run_id ?? null);
  const [scrapProp, setScrapProp] = usePersist<Record<string, string>>('scrapProp', {}, twin?.run_id ?? null);
  const [reason, setReason] = useState('');
  const [confirm, setConfirm] = useState<'hold' | 'release' | null>(null);
  const all = f.data?.lots ?? [];
  const L = all.find((x) => x.lot_no === lot);
  const canHold = role === 'SUP' || role === 'MGR';
  const shipped = L?.shipped?.qty ?? 0, ships: R[] = L?.shipped?.shipments ?? [];
  const blocked = !!L && ['ON_HOLD', 'HOLD_REVIEW', 'WAIT_JUDGEMENT', 'SCRAPPED', 'IN_PROCESS', 'WAIT_INSPECTION'].includes(L.status);
  const sameMat = L ? all.filter((x) => x.material_lot_no === L.material_lot_no) : [];
  const decide = canHold ? all.filter((x) => DECIDE.includes(x.status)) : [];
  const fail = L ? (L.gauge_fail_qty ?? L.insp_fail ?? 0) : 0;
  // 처음 열 때 고른 로트가 없으면: 결정이 필요한 로트 → 생산 중 로트 → 마지막 로트
  useEffect(() => { if (!lot && all.length) setLot((all.find((x) => DECIDE.includes(x.status)) ?? [...all].reverse().find((x) => x.status === 'IN_PROCESS') ?? all[all.length - 1]).lot_no); }, [lot, all.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // 번호로 찾기: LOT 그대로 · MAT = 그 원자재의 첫 로트 · SHP = 그 출하에 실린 로트
  const find = (v: string) => {
    const s = v.trim().toUpperCase(); if (!s) return;
    const hit = s.startsWith('MAT') ? all.find((x) => x.material_lot_no === s) : s.startsWith('SHP') ? all.find((x) => (x.shipped?.shipments ?? []).some((h: R) => h.shipment_no === s)) : all.find((x) => x.lot_no === s);
    if (hit) setLot(hit.lot_no); else toast(`${s} — 찾지 못했습니다`);
  };
  const doIt = async (kind: 'hold' | 'release') => {
    try {
      await api(`lots/${lot}/${kind}`, { role, user_id: user.id, reason: kind === 'hold' ? reason : undefined, approver: scrapOk[lot] ?? 'U12' });
      toast(kind === 'hold' ? `${lot} 보류 — 이 로트와 다음 2개 로트 전수 검사` : `${lot} 해제`); setReason(''); f.reload();
    } catch (e) { toast((e as Error).message); }
  };
  const lotChip = (x: R, extra?: string) => {
    const on = x.lot_no === lot, live = x.status === 'IN_PROCESS';
    const wait = x.status === 'WAIT_JUDGEMENT'; // 판정 대기 = 노란 테두리·글자
    return (
      <button key={x.lot_no} onClick={() => setLot(x.lot_no)} className={`${chip} ${on ? 'border-2 bg-[#f3f6ff] font-bold' : live ? 'border-dashed border-slate-400' : wait ? 'bg-[#fffdf5]' : 'bg-white'} ${wait ? '!border-[#9c7400] text-[#9c7400]' : on ? 'border-[#1f5fc4]' : live ? '' : 'border-slate-300'}`}>
        <b className={`font-mono ${wait ? 'text-[#9c7400]' : live ? 'text-[#26303a]' : 'text-[#1f5fc4]'}`}>{x.lot_no}</b><span className={x.status === 'ON_HOLD' ? 'font-bold' : ''}>{STATUS[x.status] ?? x.status}</span>{extra && <span className="text-[12px] text-slate-500">{extra}</span>}
      </button>);
  };

  return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1400px] flex-col gap-4">
        {/* [1] 찾기 · 원자재 → 생산 로트 · 고른 로트 · 결정 필요 */}
        <section className={box}>
          <div className="flex flex-wrap items-center gap-2">
            <b className="text-[15px]">번호로 찾기</b>
            <input list="lots" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && find(q)} placeholder="LOT · MAT · SHP 번호" className="h-11 w-[280px] rounded-lg border border-slate-300 px-3 font-mono text-[15px]" />
            <datalist id="lots">{[...all].reverse().slice(0, 200).map((x) => <option key={x.lot_no} value={x.lot_no}>{STATUS[x.status] ?? x.status}</option>)}</datalist>
            <button onClick={() => find(q)} className="h-11 rounded-lg bg-[#1f5fc4] px-5 text-[15px] font-bold text-white">찾기</button>
            <span className="ml-2 text-[13px] text-slate-500">예시</span>
            {[L?.material_lot_no, all.find((x) => x.shipped?.shipments?.length)?.shipped.shipments[0].shipment_no, all[0]?.lot_no].filter(Boolean).map((v) => (
              <button key={v} onClick={() => { setQ(v); find(v); }} className="h-9 rounded-lg border border-slate-300 bg-white px-3 font-mono text-[13px] text-[#1f5fc4]">{v}</button>))}
          </div>
          {!L ? <p className="mt-4 text-[14px] text-slate-500">로트를 고르세요{f.data ? '' : ' (불러오는 중)'}</p> : (<>
            <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl bg-slate-50 px-4 py-3">
              <b className="mr-1 text-[15px]">원자재 {L.material_lot_no} → 생산 로트</b>
              {sameMat.map((x) => lotChip(x))}
              <span className="text-[12px] text-slate-500">원자재 1 : 생산 로트 {sameMat.length} (DOC-06 §7)</span>
            </div>
            {/* 고른 로트 — 예전 두 번째 박스 내용을 여기 강조해서 보여 줌 */}
            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-200 pt-4">
              <span className="font-mono text-[24px] font-extrabold text-[#1c2530]">{L.lot_no}</span>
              <span className="text-[16px]">작업지시 <b className="font-mono text-[17px]">{L.order_no}</b> · {L.input_shift_id.slice(5).replace('-D', ' 주간').replace('-N', ' 야간').replace('-', '/')}</span>
              <span className="text-[16px]">원자재 <b className="font-mono text-[17px]">{L.material_lot_no}</b></span>
              <span className="text-[15px] text-slate-600">검사 {L.enhanced ? `강화(전수)` : L.plan_mode === 'FULL' ? '전수' : '발췌'}</span>
              {blocked && <span className="ml-auto rounded-xl border-2 border-[#1c2530] px-4 py-2 text-[17px] font-extrabold">🔒 {STATUS[L.status] ?? L.status} · 출하 금지</span>}
            </div>
            {decide.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
                <b className="mr-1 text-[15px]">결정 필요 {decide.length}</b>
                {decide.slice(0, 6).map((x) => (
                  <button key={x.lot_no} onClick={() => setLot(x.lot_no)} className={`${chip} border-2 ${x.status === 'WAIT_JUDGEMENT' ? 'border-[#9c7400] bg-[#fffdf5] text-[#9c7400]' : 'border-[#1c2530] bg-white'}`}>
                    <b className={`font-mono ${x.status === 'WAIT_JUDGEMENT' ? 'text-[#9c7400]' : 'text-[#1f5fc4]'}`}>{x.lot_no}</b><b>{x.status === 'WAIT_JUDGEMENT' ? '판정 대기' : '보류 · 해제 결정'}</b>
                    <span className="text-[12px] text-slate-500">{x.enhanced ? '전수 검사' : '발췌 검사'} {x.process_done?.['OP-50'] ?? 0} / {x.input_qty} 뒤 · 반장</span>
                  </button>))}
              </div>
            )}
          </>)}
        </section>

        {L && (<>
          {/* [2] 설비별 시간표 — 이 로트가 각 설비를 지난 시간 */}
          <Timeline lot={L} reports={f.data?.reports ?? []} alarms={f.data?.alarms ?? []} now={twin?.clock.sim_at} />

          <div className="grid grid-cols-[1.15fr_1fr] gap-4">
            {/* [3] 수량 */}
            <section className={box}>
              <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />수량</h3><button onClick={() => go('quality', lot)} className="h-10 rounded-lg border border-slate-300 bg-white px-4 text-[14px] text-[#1f5fc4]">검사 기록</button></div>
              <QtyRow label="투입" segs={[[L.input_qty, '#4b5563']]} total={L.input_qty} num={`${L.input_qty}`} />
              <QtyRow label="OP-50 판정" segs={[[L.gauge_pass_qty ?? 0, '#4b5563'], [fail, '#c62a2f']]} total={L.input_qty} num={`${(L.gauge_pass_qty ?? 0) + fail} / ${L.input_qty}`} sub={`합격 ${L.gauge_pass_qty ?? 0} · 불합격 ${fail}`} />
              <QtyRow label="완제품 입고" segs={[[L.fg_qty, '#4b5563']]} total={L.input_qty} num={`${L.fg_qty}`} sub={L.on_hold ? `보류 ${L.input_qty - L.scrap_qty}` : undefined} outline={L.on_hold} />
              <QtyRow label="출하" segs={[[shipped, '#4b5563']]} total={L.input_qty} num={`${shipped}`} sub={blocked ? '금지' : ships.map((s) => `${s.shipment_no} ${md(s.shipped_at)}`).join(', ') || undefined} />
            </section>

            {/* [4] 보류 · 해제 · 폐기 */}
            <section className={box}>
              <h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />보류 · 해제 · 폐기 <span className="ml-1 font-mono text-[15px] text-slate-500">{L.lot_no}</span></h3>
              {!canHold ? <p className="mt-3 text-[14px] text-slate-500">보기 전용 (보류·해제·폐기는 반장·관리자)</p> : (<>
                <div className="mt-3 flex flex-wrap items-center gap-2 border-b border-slate-200 pb-4">
                  {!L.on_hold && (<>
                    <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="보류 사유 (필수)" className="h-11 w-[200px] rounded-lg border border-slate-300 px-3 text-[14px]" />
                    <button disabled={!reason.trim() || shipped > 0 || !!L.judged_at} onClick={() => setConfirm('hold')} className="h-11 rounded-lg border border-slate-300 bg-slate-100 px-4 text-[15px] font-bold disabled:text-slate-400">보류{shipped > 0 ? ' — 이미 출하됨' : L.judged_at ? ' — 판정 끝난 로트' : ' — 사유 필수'}</button>
                  </>)}
                  {L.on_hold && <button disabled={!L.judged_at || (L.scrap_qty > 0 && !scrapOk[lot])} onClick={() => setConfirm('release')} className="h-11 rounded-lg border border-slate-300 bg-slate-100 px-4 text-[15px] font-bold disabled:text-slate-400">해제</button>}
                  {L.on_hold && <span className="text-[14px] text-slate-500">해제: {!L.judged_at ? `전수 검사 끝난 뒤 (${L.process_done?.['OP-50'] ?? 0} / ${L.input_qty})` : L.scrap_qty > 0 && !scrapOk[lot] ? '폐기 결재 승인 뒤' : '지금 할 수 있음'}</span>}
                  {L.hold && <span className="w-full text-[13px] text-slate-500">보류 사유: {L.hold.reason} ({userName(L.hold.held_by)} {L.hold.held_at ? hm(L.hold.held_at) : ''}){L.hold.released_at ? ` · 해제 ${userName(L.hold.released_by)} ${hm(L.hold.released_at)}` : ''}</span>}
                </div>
                {L.scrap_qty > 0 ? (
                  <div className="mt-4 flex flex-col items-start gap-2">
                    {role === 'SUP' && <button disabled={!!scrapProp[lot]} onClick={() => setScrapProp((p) => ({ ...p, [lot]: user.id }))} className="h-12 rounded-lg bg-[#1f5fc4] px-5 text-[15px] font-bold text-white disabled:bg-slate-300">폐기 결재 요청 (반장) — {L.lot_no} 불합격 {L.scrap_qty}개{scrapProp[lot] ? ' · 요청함' : ''}</button>}
                    {role === 'MGR' && <button disabled={!scrapProp[lot] || !!scrapOk[lot]} onClick={() => setScrapOk((p) => ({ ...p, [lot]: user.id }))} className="h-12 rounded-lg bg-[#1f5fc4] px-5 text-[15px] font-bold text-white disabled:bg-slate-300">폐기 결재 승인 (관리자) — {L.lot_no} 불합격 {L.scrap_qty}개{!scrapProp[lot] ? ' · 반장 요청 전' : scrapOk[lot] ? ' · 승인함' : ''}</button>}
                    <span className="text-[13px] text-slate-500">결재: 요청 {scrapProp[lot] ? userName(scrapProp[lot]) : '—'} → 승인 {scrapOk[lot] ? userName(scrapOk[lot]) : '—'}</span>
                  </div>
                ) : <p className="mt-4 text-[14px] text-slate-500">폐기할 불합격품 없음</p>}
              </>)}
            </section>
          </div>
        </>)}
      </div>
      {confirm && <ConfirmBox title={confirm === 'hold' ? `${lot}을(를) 보류할까요?` : `${lot}을(를) 해제할까요?`} okLabel={confirm === 'hold' ? '보류' : '해제'}
        body={confirm === 'hold' ? '보류하면 이 로트와 다음 1~2개 로트가 검사 강화(전수)로 바뀝니다. OP-50이 병목이 될 수 있습니다.' : '해제하면 출하할 수 있습니다.'}
        onOk={() => { const k = confirm; setConfirm(null); void doIt(k); }} onCancel={() => setConfirm(null)} />}
    </div>
  );
}

function QtyRow({ label, segs, total, num, sub, outline }: { label: string; segs: [number, string][]; total: number; num: string; sub?: string; outline?: boolean }) {
  return (
    <div className="mt-4 grid grid-cols-[110px_1fr_110px] items-center gap-4">
      <b className="text-[15px]">{label}</b>
      <div className={`flex h-7 overflow-hidden rounded bg-slate-100 ${outline ? 'border-2 border-[#1c2530]' : ''}`}>{segs.map(([n, c], i) => <div key={i} style={{ width: `${(Math.max(0, n) / Math.max(total, 1)) * 100}%`, background: c }} />)}</div>
      <div className="text-right"><b className="font-mono text-[19px]">{num}</b>{sub && <div className="text-[12px] text-slate-500">{sub}</div>}</div>
    </div>);
}

// 설비별 시간표 — 이 로트의 공정 실적(막대) · 알람(빨간 구간) · 보류 시각(점선) · 지금(파란 선)
function Timeline({ lot, reports, alarms, now }: { lot: R; reports: R[]; alarms: R[]; now?: string }) {
  const nowT = now ? tsOf(now) : NaN;
  const live = ['IN_PROCESS', 'WAIT_INSPECTION', 'WAIT_JUDGEMENT', 'HOLD_REVIEW', 'ON_HOLD'].includes(lot.status); // 끝난 로트는 지금까지 늘리지 않음
  const ts = [...reports.flatMap((r) => [tsOf(r.start_at), tsOf(r.end_at)]), ...(lot.hold?.held_at ? [tsOf(lot.hold.held_at)] : [])].filter(Number.isFinite);
  if (!ts.length) return <section className={box}><h3 className="text-[17px] font-bold">설비별 시간표 — {lot.lot_no}</h3><p className="mt-3 text-[14px] text-slate-500">아직 공정 실적 없음</p></section>;
  const h = 3600e3, t0 = Math.floor(Math.min(...ts) / h) * h, t1 = Math.ceil(Math.max(...ts, live && Number.isFinite(nowT) ? nowT : 0) / h) * h;
  const x = (t: number) => `${((t - t0) / (t1 - t0)) * 100}%`, w = (a: number, b: number) => `${(Math.max(0, b - a) / (t1 - t0)) * 100}%`;
  // 눈금 간격은 기간에 맞춰 1·2·3·6·12·24시간 중 하나 (눈금 10개 안팎) — 며칠짜리 로트에서 글자가 겹치지 않게
  const step = ([1, 2, 3, 6, 12, 24].find((k) => (t1 - t0) / (k * h) <= 10) ?? 24) * h;
  const ticks: number[] = []; for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) ticks.push(t);
  const held = lot.hold?.held_at ? tsOf(lot.hold.held_at) : NaN;
  return (
    <section className={box}>
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />설비별 시간표 — {lot.lot_no}</h3>
        <div className="ml-auto flex gap-4 text-[13px] text-slate-600"><span><i className="mr-1 inline-block h-2.5 w-5 rounded-sm bg-[#1f5fc4]" />이 로트</span><span><i className="mr-1 inline-block h-2.5 w-5 bg-[#f6dede]" />알람</span><span><i className="mr-1 inline-block h-3 w-0 border-l-2 border-dashed border-[#1c2530]" />보류</span><span><i className="mr-1 inline-block h-3 w-[2px] bg-[#1f5fc4]" />지금</span></div>
      </div>
      <div className="mt-4 flex">
        <div className="w-[150px] shrink-0 pt-6">{EQS.map(([eq, op]) => <div key={eq} className="flex h-14 flex-col justify-center border-t border-slate-100"><b className="text-[15px]">{eq}</b><span className="text-[12px] text-slate-500">{op}</span></div>)}</div>
        <div className="relative min-w-0 flex-1">
          <div className="relative h-6 text-[12px] text-slate-500">{ticks.map((t, i) => <span key={t} className="absolute font-mono" style={{ left: x(t), transform: i === ticks.length - 1 ? 'translateX(-100%)' : i ? 'translateX(-50%)' : undefined }}>{(i === 0 || new Date(t + 9 * h).getUTCHours() < step / h) ? `${md(new Date(t + 9 * h).toISOString())} ` : ''}{new Date(t + 9 * h).toISOString().slice(11, 16)}</span>)}</div>
          {ticks.map((t) => <div key={t} className="pointer-events-none absolute bottom-0 top-6 w-px bg-[#eef0f3]" style={{ left: x(t) }} />)}
          {EQS.map(([eq]) => (
            <div key={eq} className="relative h-14 border-t border-slate-100">
              {alarms.filter((a) => a.equipment_id === eq).map((a) => { const s0 = tsOf(a.occurred_at), e = a.cleared_at ? tsOf(a.cleared_at) : nowT; return <div key={a.alarm_event_id} className="absolute top-0 h-full border-t-2 border-[#c62a2f] bg-[#f6dede]" style={{ left: x(s0), width: w(s0, e) }} title={`알람 ${a.alarm_code}`}>{(e - s0) / (t1 - t0) > 0.05 && <span className="absolute bottom-0.5 left-1 whitespace-nowrap text-[11px] text-[#c62a2f]">{a.severity === 'STOP' ? '고장' : '알람'} {a.alarm_code}</span>}</div>; })}
              {reports.filter((r) => r.equipment_id === eq).map((r, i) => { const s0 = tsOf(r.start_at), e = tsOf(r.end_at); return <div key={i} className="absolute top-1/2 h-7 -translate-y-1/2 overflow-hidden whitespace-nowrap rounded bg-[#1f5fc4] px-2 text-[12px] font-bold leading-7 text-white" style={{ left: x(s0), width: w(s0, e), minWidth: 6 }} title={`${hm(r.start_at)}~${hm(r.end_at)} · 양품 ${r.gq + r.rq} · 폐기 ${r.sq}`}>{lot.lot_no.slice(-5)} · {r.pq}개</div>; })}
            </div>))}
          {Number.isFinite(held) && <div className="pointer-events-none absolute bottom-0 top-6 border-l-2 border-dashed border-[#1c2530]" style={{ left: x(held) }}><span className="absolute -top-6 -translate-x-1/2 whitespace-nowrap rounded-full border border-[#1c2530] bg-white px-2 text-[11px] font-bold">🔒 보류 {hm(lot.hold.held_at)}</span></div>}
          {Number.isFinite(nowT) && nowT <= t1 && <div className="pointer-events-none absolute bottom-0 top-6 w-[2px] bg-[#1f5fc4]" style={{ left: x(nowT) }} />}
        </div>
      </div>
    </section>
  );
}
