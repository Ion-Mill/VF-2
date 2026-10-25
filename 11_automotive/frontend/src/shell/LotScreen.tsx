'use client';
// SCR-19 로트 추적 — 원자재 로트 → 공정 실적 → 알람 → 검사 → 완제품 입고 → 출하. 보류·해제 = API-LOT-02 (시뮬레이터: 보류하면 그 로트와 다음 2개 전수 검사).
// 화면 구조 (화이트 카드 · 파스텔 블루, 사용자 선택 2026-10-21 — design_handoff_lot_trace/화이트카드_파스텔블루.html). 제목 · 설명 줄은 App.tsx PageHead
//   [머리 카드: 상태 태그 + 출하 여부 태그 · 큰 로트 번호 · 회색 사실 한 줄 · 공정 길(다 끝나면 한 줄 띠)] · [번호로 찾기 + 원자재→생산 로트 + 결정 필요] · [설비별 시간표] · [수량 | 보류·해제·폐기]
// 카드는 흰색, 색은 아이콘 칸 · 태그에만. 공정 색 op1~op5 = 파랑 계열 안에서 번갈아 (tailwind.config.ts).
import { LockIcon, TONE_TAG } from './ui';
import { lotBand } from './bands';
import { useEffect, useState, type ReactNode } from 'react';
import { PAGE, useApp } from './ctx';
import { api, hm, md, tsOf, useFetch, usePersist } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;
const STATUS: Record<string, string> = { IN_PROCESS: '생산 중', WAIT_INSPECTION: '검사 대기', WAIT_JUDGEMENT: '판정 대기', HOLD_REVIEW: '보류 검토', ON_HOLD: '보류', PASSED: '합격', RELEASED: '해제', SCRAPPED: '폐기' };
const DECIDE = ['ON_HOLD', 'HOLD_REVIEW', 'WAIT_JUDGEMENT']; // 반장·관리자가 결정해야 하는 상태
// 공정 = [코드, 설비, 이름, 색 이름(op1~op5), 아이콘]
const OPS: [string, string, string, string, string][] = [
  ['OP-10', 'SAW-01', '절단', 'op1', '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>'],
  ['OP-20', 'MIL-01', '황삭', 'op2', '<path d="M12 2v6M8 8h8l-1 6H9zM10 14v6M14 14v6"/>'],
  ['OP-30', 'VF2-01/02', '정밀 가공', 'op3', '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"/>'],
  ['OP-40', 'WSH-01', '디버링·세척', 'op4', '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>'],
  ['OP-50', 'CMM-01', '측정', 'op5', '<path d="M3 17 17 3l4 4L7 21zM7 13l2 2M10 10l2 2M13 7l2 2"/>'],
];
const EQS: [string, number][] = [['SAW-01', 0], ['MIL-01', 1], ['VF2-01', 2], ['VF2-02', 2], ['WSH-01', 3], ['CMM-01', 4]]; // [설비, OPS 순번]
// 공정 색 클래스 (tailwind가 찾을 수 있게 글자 그대로)
const OPC: Record<string, { tile: string; bar: string; job: string }> = {
  op1: { tile: 'bg-op1 text-op1-i', bar: 'bg-op1-i', job: 'bg-op1-b text-op1-t' },
  op2: { tile: 'bg-op2 text-op2-i', bar: 'bg-op2-i', job: 'bg-op2-b text-op2-t' },
  op3: { tile: 'bg-op3 text-op3-i', bar: 'bg-op3-i', job: 'bg-op3-b text-op3-t' },
  op4: { tile: 'bg-op4 text-op4-i', bar: 'bg-op4-i', job: 'bg-op4-b text-op4-t' },
  op5: { tile: 'bg-op5 text-op5-i', bar: 'bg-op5-i', job: 'bg-op5-b text-op5-t' },
};
const card = 'rounded-card border border-line bg-white p-6 shadow-card';
const tag = 'inline-flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded-[7px] px-2.5 text-small font-semibold';
const big = 'inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-tile px-[18px] text-band font-bold';
const Svg = ({ d, size = 18 }: { d: string; size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" dangerouslySetInnerHTML={{ __html: d }} />;
const Ico = ({ c, d, sm }: { c: string; d: string; sm?: boolean }) => <span className={`inline-flex shrink-0 items-center justify-center ${sm ? 'h-7 w-7 rounded-[8px]' : 'h-11 w-11 rounded-tile'} ${OPC[c].tile}`}><Svg d={d} size={sm ? 15 : 20} /></span>;
const CardHead = ({ d, title, sub, right }: { d: string; title: string; sub?: string; right?: ReactNode }) => (
  <div className="mb-4 flex flex-wrap items-center gap-3">
    <span className="inline-flex h-9 w-9 items-center justify-center rounded-ctl bg-brand-tint text-brand"><Svg d={d} /></span>
    <h3 className="text-[18px] font-bold">{title}</h3>{sub && <span className="font-mono text-small text-ink-3">{sub}</span>}
    {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
  </div>);
const D_CLOCK = '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', D_BOX = '<path d="M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8"/>', D_LOCK = '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>';
const DONE = ['PASSED', 'RELEASED', 'SCRAPPED']; // 계보에서 '끝남' 묶음 — 나머지(생산 중 · 검사/판정 대기 · 보류)는 '진행 중' 묶음 위로 (2026-10-22)
const dotOf = (s: string) => (['PASSED', 'RELEASED'].includes(s) ? 'bg-ok-dot' : s === 'WAIT_JUDGEMENT' ? 'bg-warn-mark' : s === 'IN_PROCESS' ? 'bg-brand' : 'bg-ink-3');

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
  const matLive = sameMat.filter((x) => !DONE.includes(x.status)), matDone = sameMat.filter((x) => DONE.includes(x.status));
  const decide = canHold ? all.filter((x) => DECIDE.includes(x.status)) : [];
  const fail = L ? (L.gauge_fail_qty ?? L.insp_fail ?? 0) : 0;
  const now = twin?.clock.sim_at;
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
  // 계보 칩: 점 바로 옆에 상태 글자(합격 포함, 사용자 요청 2026-10-22) → 로트 번호. 보고 있는 로트 = 파랑 테두리 + "보는 중"
  // small = '끝남' 묶음: 작고 흐리게 (상태 글자는 그대로)
  const lotChip = (x: R, small?: boolean) => {
    const on = x.lot_no === lot, live = x.status === 'IN_PROCESS', wait = x.status === 'WAIT_JUDGEMENT';
    return (
      <button key={x.lot_no} onClick={() => setLot(x.lot_no)} aria-pressed={on} title={STATUS[x.status] ?? x.status}
        className={`inline-flex items-center gap-2 border ${small && !on ? 'h-8 rounded-ctl px-2.5 text-small text-ink-2' : 'h-10 rounded-tile px-3 text-body'} ${on ? 'border-brand bg-brand-tint font-bold text-brand-ink shadow-[inset_0_0_0_1px_#3d6fe0]' : wait ? 'border-warn-line bg-warn-bg text-warn' : live ? 'border-dashed border-line bg-white hover:border-brand-line' : 'border-line bg-white hover:border-brand-line'}`}>
        <span className={`inline-flex items-center gap-1.5 text-small ${small && !on ? 'font-medium text-ink-3' : 'font-semibold'}`}><i className={`h-2 w-2 rounded-full ${dotOf(x.status)}`} />{STATUS[x.status] ?? x.status}</span><b className="font-mono font-semibold">{x.lot_no}</b>
        {on && <span className="rounded-md bg-white px-1.5 text-[12px] font-semibold text-brand-ink">보는 중</span>}
      </button>);
  };

  // 머리 카드 — 결론 판단은 lotBand 그대로 (의심 · 불합격 · 판정 대기 · 강화 · 합격)
  const band = lotBand(L ? { lot_no: L.lot_no, status: L.status, order_no: L.order_no, material_lot_no: L.material_lot_no, input_qty: Number(L.input_qty ?? 0), enhanced: !!L.enhanced, suspect: (f.data?.suspect_lot ?? twin?.suspect_lot) === L.lot_no } : null, Number(L?.process_done?.['OP-50'] ?? 0), decide.length, Number(fail) || 0);
  const word = L ? STATUS[L.status] ?? L.status : '';
  const extra = L ? band.title.slice(L.lot_no.length + 1).replace(/ — .*$/, '') : ''; // 띠 제목에서 로트 번호·출하 문구를 뺀 것 (불합격 N개 · 의심 로트 · 강화 검사 중)
  const allDone = !!L && OPS.every(([op]) => Number(L.process_done?.[op] ?? 0) >= Math.max(1, Number(L.input_qty ?? 0)));
  const shift = L ? String(L.input_shift_id ?? '').slice(5).replace('-D', ' 주간').replace('-N', ' 야간').replace('-', '/') : '';
  const fact = (k: string, v: ReactNode) => <span className="whitespace-nowrap"><span className="mr-1.5 text-ink-3">{k}</span>{v}</span>;

  return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-4">
        {/* [0] 머리 카드: 결론 = 상태 + 출하 여부 두 개만 크게, 나머지는 회색 글자 */}
        {!L ? <section className={card}><p className="text-body text-ink-2">{band.title} — {band.desc}{f.data ? '' : ' (불러오는 중)'}</p></section> : (
          <section className={card}>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`${big} ${TONE_TAG[band.tone]}`}>
                {L.status === 'IN_PROCESS' ? <span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full rounded-full bg-current opacity-60 motion-safe:animate-ping" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-current" /></span> : <span className="h-2.5 w-2.5 rounded-full bg-current" />}
                {word}
              </span>
              {extra && extra !== word && <span className={`${tag} ${band.tone === 'crit' ? 'bg-crit-bg text-crit' : 'bg-warn-bg text-warn'}`}>{band.tone === 'crit' ? '⚠' : '▲'} {extra}</span>}
              <div className="ml-auto flex items-center gap-3">
                {now && <span className="flex items-center gap-1.5 text-small text-ink-3"><i className="h-2 w-2 rounded-full bg-ok-dot" />실시간, {md(now)} {hm(now)} 기준</span>}
                {blocked ? <span className={`${big} bg-white text-warn shadow-[inset_0_0_0_1.5px_currentColor]`}><LockIcon size={16} /> 출하 금지</span>
                  : <span className={`${big} bg-white text-ok shadow-[inset_0_0_0_1.5px_currentColor]`}><span className="h-2.5 w-2.5 rounded-full bg-ok-dot" />출하 가능</span>}
              </div>
            </div>
            <h1 className="mt-4 font-mono text-[42px] font-bold leading-tight tracking-[-.03em] text-ink">{L.lot_no}</h1>
            <p className="mt-1 flex flex-wrap gap-x-6 gap-y-1 text-small text-ink-2">
              {L.order_no && fact('작업지시', <span className="font-mono">{L.order_no}</span>)}
              {L.material_lot_no && fact('원자재', <span className="font-mono">{L.material_lot_no}</span>)}
              {shift && fact('투입', shift)}
              {band.desc && <span>{band.desc}</span>}
            </p>
            {/* 공정 길: 다 끝난 로트는 한 줄 띠, 진행 중이면 다섯 칸 (진행 중 막대만 빛이 지나감) */}
            {allDone ? (
              <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-tile border border-line px-4 py-3">
                <span className={`${tag} bg-ok-bg text-ok`}><i className="h-2 w-2 rounded-full bg-ok-dot" />공정 5단계 모두 완료</span>
                <ol className="flex flex-wrap items-center gap-y-2">
                  {OPS.map(([op, , name, c, d], i) => <li key={op} className="flex items-center whitespace-nowrap text-body font-semibold">{i > 0 && <span className="mx-3 h-0.5 w-6 bg-[repeating-linear-gradient(90deg,#cbdcfb_0_4px,transparent_4px_7px)]" />}<Ico c={c} d={d} sm /><span className="ml-2">{name}</span><span className="ml-1.5 font-mono text-[13px] font-normal text-ink-3">{op}</span></li>)}
                </ol>
              </div>
            ) : (
              <div className="mt-6 grid grid-cols-5 gap-3 max-[900px]:grid-cols-[repeat(5,minmax(160px,1fr))] max-[900px]:overflow-x-auto">
                {OPS.map(([op, eq, name, c, d]) => {
                  const n = Number(L.process_done?.[op] ?? 0), tot = Math.max(1, Number(L.input_qty ?? 0)), done = n >= tot;
                  return (
                    <div key={op} className="flex min-w-0 flex-col gap-3 rounded-tile border border-line bg-white p-4">
                      <div className="flex items-center gap-2.5"><Ico c={c} d={d} /><div className="min-w-0"><div className="truncate text-card font-bold">{name}</div><div className="truncate font-mono text-[13px] text-ink-3">{op} · {eq}</div></div></div>
                      <div className="flex items-center justify-between gap-2">
                        <span className={`${tag} ${done ? OPC[c].job : n > 0 ? 'bg-brand-tint text-brand-ink' : 'bg-info-bg text-info'}`}>{done ? '완료' : n > 0 ? <span className="font-mono">{n} / {tot}</span> : '대기'}</span>
                        {done && <span className="font-mono text-small text-ink-3">{n}개</span>}
                      </div>
                      <div className="h-[5px] overflow-hidden rounded-full bg-track"><div className={`relative h-full rounded-full opacity-60 ${OPC[c].bar} ${n > 0 && !done ? 'bar-shine' : ''}`} style={{ width: `${Math.min(100, (n / tot) * 100)}%` }} /></div>
                    </div>);
                })}
              </div>
            )}
          </section>
        )}

        {/* [1] 찾기 · 원자재 → 생산 로트 · 결정 필요 */}
        <section className={card}>
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <svg className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
              <input list="lots" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && find(q)} placeholder="로트 · 원자재 · 출하 번호로 찾기" aria-label="로트 · 원자재 · 출하 번호" className="h-12 w-[340px] max-w-full rounded-tile border border-line bg-white pl-11 pr-3 font-mono text-body focus:border-brand-line focus:outline-none focus:ring-[3px] focus:ring-brand-tint" />
            </div>
            <datalist id="lots">{[...all].reverse().slice(0, 200).map((x) => <option key={x.lot_no} value={x.lot_no}>{STATUS[x.status] ?? x.status}</option>)}</datalist>
            <button onClick={() => find(q)} className="h-12 rounded-tile bg-brand px-6 text-body font-bold text-white hover:bg-brand-ink">찾기</button>
            <span className="ml-2 text-small text-ink-3">예시</span>
            {[L?.material_lot_no, all.find((x) => x.shipped?.shipments?.length)?.shipped.shipments[0].shipment_no, all[0]?.lot_no].filter(Boolean).map((v) => (
              <button key={v} onClick={() => { setQ(v); find(v); }} className="h-9 rounded-ctl border border-line bg-white px-3 font-mono text-small text-ink-2 hover:border-brand-line hover:text-brand-ink">{v}</button>))}
            {L && <button onClick={() => go('quality', lot)} className="ml-auto h-10 rounded-ctl border border-line bg-white px-4 text-body text-ink hover:border-brand-line hover:text-brand-ink">검사 {L.enhanced ? '강화(전수)' : L.plan_mode === 'FULL' ? '전수' : '발췌'} · 검사 기록 보기</button>}
          </div>
          {L && (<>
            <div className="mt-5 flex flex-wrap items-start gap-2 border-t border-line-soft pt-5">
              <div className="mr-1 flex items-center gap-2.5 rounded-tile border border-line py-1.5 pl-1.5 pr-4"><span className="inline-flex h-8 w-8 items-center justify-center rounded-[9px] bg-brand-tint text-brand"><Svg d='<path d="M4 7h16M4 12h16M4 17h16"/>' size={16} /></span><div className="leading-tight"><div className="text-[13px] text-ink-3">원자재</div><b className="font-mono text-body">{L.material_lot_no}</b></div></div>
              <span className="mt-[25px] h-0.5 w-5 bg-line" aria-hidden="true" />
              {/* 진행 중(봐야 할 것) 위 · 끝남 아래 작게 (사용자 선택 2026-10-22) */}
              <div className="flex min-w-0 flex-1 flex-col gap-2.5">
                {matLive.length > 0 && <div className="flex items-start gap-2"><span className="w-[76px] shrink-0 pt-2.5 text-small font-semibold text-ink-2">진행 중 {matLive.length}</span><div className="flex min-w-0 flex-wrap gap-2">{matLive.map((x) => lotChip(x))}</div></div>}
                {matDone.length > 0 && <div className="flex items-start gap-2"><span className="w-[76px] shrink-0 pt-1.5 text-small font-semibold text-ink-3">끝남 {matDone.length}</span><div className="flex min-w-0 flex-wrap gap-1.5">{matDone.map((x) => lotChip(x, true))}</div></div>}
              </div>
            </div>
            <div className="mt-2.5 text-small text-ink-3">같은 원자재에서 나온 생산 로트 {sameMat.length}개 (DOC-06 §7)</div>
            {decide.length > 0 && (
              <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-line-soft pt-5">
                <span className={`${tag} mr-1 bg-warn-bg text-warn`}>결정 필요 {decide.length}</span>
                {decide.slice(0, 6).map((x) => (
                  <button key={x.lot_no} onClick={() => setLot(x.lot_no)} className="inline-flex h-10 items-center gap-2 rounded-tile border border-line bg-white px-3 text-body hover:border-brand-line">
                    <b className="font-mono font-semibold">{x.lot_no}</b><span className={`${tag} ${x.status === 'WAIT_JUDGEMENT' ? 'bg-warn-bg text-warn' : 'bg-info-bg text-info'}`}>{x.status === 'WAIT_JUDGEMENT' ? '판정 대기' : '보류 · 해제 결정'}</span>
                    <span className="text-small text-ink-3">{x.enhanced ? '전수 검사' : '발췌 검사'} {x.process_done?.['OP-50'] ?? 0} / {x.input_qty} 뒤 · 반장</span>
                  </button>))}
              </div>
            )}
          </>)}
        </section>

        {L && (<>
          {/* [2] 설비별 시간표 — 이 로트가 각 설비를 지난 시간 */}
          <Timeline lot={L} reports={f.data?.reports ?? []} alarms={f.data?.alarms ?? []} now={now} />

          <div className="grid grid-cols-[1.15fr_1fr] gap-4 max-[1100px]:grid-cols-1">
            {/* [3] 수량 */}
            <section className={card}>
              <CardHead d={D_BOX} title="수량" right={<button onClick={() => go('quality', lot)} className="h-9 rounded-ctl border border-line bg-white px-3 text-small font-semibold text-ink-2 hover:border-brand-line hover:text-brand-ink">검사 기록 보기</button>} />
              <QtyRow icon='<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>' label="투입" tone="input" segs={[[L.input_qty, '']]} total={L.input_qty} num={`${L.input_qty}`} />
              <QtyRow icon='<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>' label="OP-50 판정" tone="judge" segs={[[L.gauge_pass_qty ?? 0, ''], [fail, 'bg-crit']]} total={L.input_qty} num={`${(L.gauge_pass_qty ?? 0) + fail} / ${L.input_qty}`} sub={`합격 ${L.gauge_pass_qty ?? 0}, 불합격 ${fail}`} />
              <QtyRow icon='<path d="M3 9h18l-2-5H5zM5 9v11h14V9M9 20v-6h6v6"/>' label="완제품 입고" segs={[[L.fg_qty, '']]} total={L.input_qty} num={`${L.fg_qty}`} sub={L.on_hold ? `보류 ${L.input_qty - L.scrap_qty}` : undefined} outline={L.on_hold} />
              <QtyRow icon='<path d="M3 6h11v10H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>' label="출하" tone="ship" segs={[[shipped, '']]} total={L.input_qty} num={`${shipped}`} sub={blocked ? '출하 금지' : ships.map((s) => `${s.shipment_no} ${md(s.shipped_at)}`).join(', ') || undefined} />
            </section>

            {/* [4] 보류 · 해제 · 폐기 */}
            <section className={card}>
              <CardHead d={D_LOCK} title="보류 · 해제 · 폐기" sub={L.lot_no} />
              {!canHold ? <p className="text-body text-ink-2">보기 전용 (보류·해제·폐기는 반장·관리자)</p> : (<>
                <div className="flex flex-wrap items-center gap-2 border-b border-line-soft pb-4">
                  {!L.on_hold && (<>
                    <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="보류 사유 (필수)" aria-label="보류 사유" className="h-11 w-[220px] rounded-tile border border-line bg-white px-3 text-body focus:border-brand-line focus:outline-none focus:ring-[3px] focus:ring-brand-tint" />
                    <button disabled={!reason.trim() || shipped > 0 || !!L.judged_at} onClick={() => setConfirm('hold')} className="h-11 rounded-tile border border-line bg-white px-4 text-body font-bold text-ink hover:border-brand-line disabled:text-ink-3 disabled:hover:border-line">보류{shipped > 0 ? ' — 이미 출하됨' : L.judged_at ? ' — 판정 끝난 로트' : ' — 사유 필수'}</button>
                  </>)}
                  {L.on_hold && <button disabled={!L.judged_at || (L.scrap_qty > 0 && !scrapOk[lot])} onClick={() => setConfirm('release')} className="h-11 rounded-tile border border-line bg-white px-4 text-body font-bold text-ink hover:border-brand-line disabled:text-ink-3">해제</button>}
                  {L.on_hold && <span className="text-body text-ink-2">해제: {!L.judged_at ? `전수 검사 끝난 뒤 (${L.process_done?.['OP-50'] ?? 0} / ${L.input_qty})` : L.scrap_qty > 0 && !scrapOk[lot] ? '폐기 결재 승인 뒤' : '지금 할 수 있음'}</span>}
                  {L.hold && <span className="w-full text-small text-ink-2">보류 사유: {L.hold.reason} ({userName(L.hold.held_by)} {L.hold.held_at ? hm(L.hold.held_at) : ''}){L.hold.released_at ? ` · 해제 ${userName(L.hold.released_by)} ${hm(L.hold.released_at)}` : ''}</span>}
                </div>
                {L.scrap_qty > 0 ? (
                  <div className="mt-4 flex flex-col items-start gap-2">
                    {role === 'SUP' && <button disabled={!!scrapProp[lot]} onClick={() => setScrapProp((p) => ({ ...p, [lot]: user.id }))} className="h-12 rounded-tile bg-brand px-5 text-body font-bold text-white hover:bg-brand-ink disabled:bg-track disabled:text-bar">불합격 {L.scrap_qty}개 폐기 결재 요청 (반장){scrapProp[lot] ? ' · 요청함' : ''}</button>}
                    {role === 'MGR' && <button disabled={!scrapProp[lot] || !!scrapOk[lot]} onClick={() => setScrapOk((p) => ({ ...p, [lot]: user.id }))} className="h-12 rounded-tile bg-brand px-5 text-body font-bold text-white hover:bg-brand-ink disabled:bg-track disabled:text-bar">불합격 {L.scrap_qty}개 폐기 결재 승인 (관리자){!scrapProp[lot] ? ' · 반장 요청 전' : scrapOk[lot] ? ' · 승인함' : ''}</button>}
                    <span className="text-small text-ink-2">결재: 요청 {scrapProp[lot] ? userName(scrapProp[lot]) : '—'} → 승인 {scrapOk[lot] ? userName(scrapOk[lot]) : '—'}</span>
                  </div>
                ) : <p className="mt-4 text-body text-ink-2">폐기할 불합격품이 없습니다.</p>}
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

// 수량 한 줄: 아이콘 칸 + 이름(줄바꿈 없음) | 옅은 파랑 막대(불합격 = 빨강) | 숫자
// 단계마다 색 (2026-10-24): [막대, 아이콘 칸 바탕, 아이콘] — 테마 공정·상태 색 계열, 막대는 한 단계 옅은 파스텔
const QTY_TONE = { input: ['bg-[#a9b6c8]', 'bg-op4', 'text-op4-i'], judge: ['bg-[#7fd3a4]', 'bg-ok-bg', 'text-ok'], fg: ['bg-[#8fb0f0]', 'bg-brand-tint', 'text-brand'], ship: ['bg-[#7cc6d4]', 'bg-op1', 'text-op1-i'] } as const; // 막대는 파스텔 (사용자 요청 2026-10-24)
function QtyRow({ icon, label, segs, total, num, sub, outline, tone = 'fg' }: { icon: string; label: string; segs: [number, string][]; total: number; num: string; sub?: string; outline?: boolean; tone?: keyof typeof QTY_TONE }) {
  const [bar, tileBg, tileFg] = QTY_TONE[tone];
  return (
    <div className="grid grid-cols-[168px_1fr_112px] items-center gap-4 border-t border-line-soft py-3">
      <span className="flex items-center gap-2.5 whitespace-nowrap text-body font-semibold"><span className={`inline-flex h-8 w-8 items-center justify-center rounded-[9px] ${tileBg} ${tileFg}`}><Svg d={icon} size={16} /></span>{label}</span>
      <div className={`flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-track ${outline ? 'outline outline-2 outline-offset-2 outline-ink' : ''}`}>{segs.filter(([n]) => n > 0).map(([n, c], i) => <div key={i} className={`h-full ${c || bar}`} style={{ width: `${(n / Math.max(total, 1)) * 100}%` }} />)}</div>
      <div className="text-right"><b className="font-mono text-band">{num}</b>{sub && <div className="text-[13px] text-ink-3">{sub}</div>}</div>
    </div>);
}

// 설비별 시간표 — 이 로트의 공정 실적(공정 색 막대) · 알람(빨간 핀 + 이름표, 옅은 빨간 구간) · 보류 시각(점선) · 지금(남색 선)
function Timeline({ lot, reports, alarms, now }: { lot: R; reports: R[]; alarms: R[]; now?: string }) {
  const [openAl, setOpenAl] = useState<string | null>(null); // 묶인 알람 이름표("알람 2건")를 눌러 펼친 것
  const nowT = now ? tsOf(now) : NaN;
  const live = ['IN_PROCESS', 'WAIT_INSPECTION', 'WAIT_JUDGEMENT', 'HOLD_REVIEW', 'ON_HOLD'].includes(lot.status); // 끝난 로트는 지금까지 늘리지 않음
  const ts = [...reports.flatMap((r) => [tsOf(r.start_at), tsOf(r.end_at)]), ...(lot.hold?.held_at ? [tsOf(lot.hold.held_at)] : [])].filter(Number.isFinite);
  if (!ts.length) return <section className={card}><CardHead d={D_CLOCK} title="설비별 시간표" sub={lot.lot_no} /><p className="text-body text-ink-2">아직 공정 실적이 없습니다.</p></section>;
  const h = 3600e3, t0 = Math.floor(Math.min(...ts) / h) * h, t1 = Math.ceil(Math.max(...ts, live && Number.isFinite(nowT) ? nowT : 0) / h) * h;
  const x = (t: number) => `${((t - t0) / (t1 - t0)) * 100}%`, w = (a: number, b: number) => `${(Math.max(0, b - a) / (t1 - t0)) * 100}%`;
  // 눈금 간격은 기간에 맞춰 1·2·3·6·12·24시간 중 하나 (눈금 10개 안팎) — 며칠짜리 로트에서 글자가 겹치지 않게
  const step = ([1, 2, 3, 6, 12, 24].find((k) => (t1 - t0) / (k * h) <= 10) ?? 24) * h;
  const ticks: number[] = []; for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) ticks.push(t);
  const held = lot.hold?.held_at ? tsOf(lot.hold.held_at) : NaN;
  // 알람 표시 (사용자 선택 2026-10-22, 1·3·4안): 폭과 상관없는 빨간 핀 + 진한 빨강 이름표 + 시각 줄 빨간 눈금.
  // 이름표가 겹치지 않게 같은 설비에서 시작이 전체 기간의 4% 안으로 붙은 알람은 "알람 N건" 하나로 묶고, 누르면 펼침
  const shown = alarms.filter((a) => EQS.some(([eq]) => eq === a.equipment_id) && tsOf(a.occurred_at) <= t1);
  const label = (a: R) => `${a.severity === 'STOP' ? '고장' : '알람'} ${a.alarm_code}`;
  const groupsOf = (eq: string) => shown.filter((a) => a.equipment_id === eq).sort((a, b) => tsOf(a.occurred_at) - tsOf(b.occurred_at))
    .reduce<R[][]>((g, a) => { const lastG = g[g.length - 1]; if (lastG && tsOf(a.occurred_at) - tsOf(lastG[lastG.length - 1].occurred_at) < (t1 - t0) * 0.04) lastG.push(a); else g.push([a]); return g; }, []);
  return (
    <section className={card}>
      <CardHead d={D_CLOCK} title="설비별 시간표" sub={lot.lot_no} right={<>
        <span className={`${tag} bg-crit text-white`}>! 알람 {shown.length}건</span>
        {Number.isFinite(held) && <span className="flex items-center gap-1.5 text-small text-ink-2"><i className="inline-block h-3.5 w-0 border-l-2 border-dashed border-ink" />보류</span>}
        <span className="flex items-center gap-1.5 text-small text-ink-2"><i className="inline-block h-3.5 w-[2px] bg-ink" />지금</span></>} />
      <div className="overflow-x-auto">
        <div className="flex min-w-[860px]">
          <div className="w-[176px] shrink-0 pt-7">{EQS.map(([eq, oi]) => { const [op, , name, c, d] = OPS[oi]; return <div key={eq} className="flex h-14 items-center gap-2.5 border-t border-line-soft"><Ico c={c} d={d} sm /><div className="leading-tight"><b className="font-mono text-body">{eq}</b><div className="text-[13px] text-ink-3">{op} {name}</div></div></div>; })}</div>
          <div className="relative min-w-0 flex-1">
            <div className="relative h-7 text-[13px] text-ink-3">{ticks.map((t, i) => <span key={t} className="absolute font-mono" style={{ left: x(t), transform: i === ticks.length - 1 ? 'translateX(-100%)' : i ? 'translateX(-50%)' : undefined }}>{(i === 0 || new Date(t + 9 * h).getUTCHours() < step / h) ? `${md(new Date(t + 9 * h).toISOString())} ` : ''}{new Date(t + 9 * h).toISOString().slice(11, 16)}</span>)}
              {shown.map((a) => <i key={a.alarm_event_id} className="absolute bottom-0 h-0 w-0 -translate-x-1/2 border-x-[5px] border-t-[7px] border-x-transparent border-t-crit" style={{ left: x(tsOf(a.occurred_at)) }} title={`${hm(a.occurred_at)} ${label(a)}`} />)}</div>
            {ticks.map((t) => <div key={t} className="pointer-events-none absolute bottom-0 top-7 w-px bg-line-soft" style={{ left: x(t) }} />)}
            {EQS.map(([eq, oi]) => (
              <div key={eq} className="relative h-14 border-t border-line-soft">
                {reports.filter((r) => r.equipment_id === eq).map((r, i) => { const s0 = tsOf(r.start_at), e = tsOf(r.end_at); return <div key={i} className={`absolute top-1/2 h-8 -translate-y-1/2 overflow-hidden whitespace-nowrap rounded-[8px] px-2.5 font-mono text-small font-semibold leading-8 ${OPC[OPS[oi][3]].job}`} style={{ left: x(s0), width: w(s0, e), minWidth: 6 }} title={`${hm(r.start_at)}~${hm(r.end_at)} · 양품 ${r.gq + r.rq} · 폐기 ${r.sq}`}>{r.pq}개</div>; })}
                {/* 알람은 막대 위에 겹쳐 그린다 (막대에 가려지지 않게) */}
                {shown.filter((a) => a.equipment_id === eq).map((a) => { const s0 = tsOf(a.occurred_at), e = a.cleared_at ? tsOf(a.cleared_at) : nowT; return <div key={a.alarm_event_id} className="pointer-events-none absolute inset-y-0 z-[1] bg-crit/10" style={{ left: x(s0), width: w(s0, e) }}><i className="absolute inset-y-0 left-0 w-[3px] -translate-x-1/2 bg-crit" /></div>; })}
                {groupsOf(eq).map((g) => { const k = `${eq}-${g[0].alarm_event_id}`, pos = (tsOf(g[0].occurred_at) - t0) / (t1 - t0), right = pos > 0.85, open = openAl === k;
                  return <div key={k} className="absolute top-0.5 z-[3]" style={{ left: x(tsOf(g[0].occurred_at)), transform: right ? 'translateX(-100%)' : undefined }}>
                    <button type="button" onClick={() => g.length > 1 && setOpenAl(open ? null : k)} title={g.map((a) => `${hm(a.occurred_at)} ${label(a)}`).join(' · ')}
                      className={`flex h-5 items-center gap-1 whitespace-nowrap rounded-[5px] bg-crit pl-0.5 pr-1.5 text-[12px] font-bold text-white shadow-[0_2px_6px_-2px_rgba(194,48,66,.6)] ${g.length > 1 ? 'cursor-pointer hover:brightness-110' : 'cursor-default'}`}>
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white text-[11px] text-crit">!</span>{g.length > 1 ? `알람 ${g.length}건 ${open ? '▴' : '▾'}` : label(g[0])}</button>
                    {open && <div className={`absolute top-6 min-w-[150px] rounded-tile border border-crit-line bg-white py-1 shadow-card ${right ? 'right-0' : 'left-0'}`}>{g.map((a) => <div key={a.alarm_event_id} className="flex items-center gap-2 whitespace-nowrap px-3 py-1 text-small"><span className="font-mono text-ink-2">{hm(a.occurred_at)}</span><b className="text-crit">{label(a)}</b></div>)}</div>}
                  </div>; })}
              </div>))}
            {Number.isFinite(held) && <div className="pointer-events-none absolute bottom-0 top-7 z-[2] border-l-2 border-dashed border-ink" style={{ left: x(held) }}><span className="absolute -top-7 -translate-x-1/2 whitespace-nowrap rounded-md border border-line bg-white px-2 text-small font-semibold"><LockIcon /> 보류 {hm(lot.hold.held_at)}</span></div>}
            {Number.isFinite(nowT) && nowT <= t1 && <div className="pointer-events-none absolute bottom-0 top-7 z-[2] w-[2px] bg-ink" style={{ left: x(nowT) }}><span className="absolute -top-7 right-0 whitespace-nowrap rounded-md bg-ink px-2.5 font-mono text-small font-bold text-white">지금 {hm(now!)}</span></div>}
          </div>
        </div>
      </div>
    </section>
  );
}
