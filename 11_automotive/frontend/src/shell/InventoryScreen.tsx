'use client';
// SCR-21 재고 — 13품목(공구 5·소모품 6·원자재 1·완제품 1), 관리 역할, 거래 기록, 입고·실사 조정(API-INV-02), 출하 등록(API-INV-04). 발주 버튼 없음.
// 화면 구조 (사용자 시안 2026-10-16): [재고] [출하 등록] 탭. 출하 등록 = 이번 출하/지난 출하 · 단계(로트 고르기→수량→출하 전 확인→확정) · 합격 로트 카드(−/+) · 출하 요약
import { useState } from 'react';
import { BTN, DARK, PAGE, useApp } from './ctx';
import { api, hm, md, useFetch, usePersist } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;
const CAT: Record<string, string> = { TOOL: '공구', CONSUMABLE: '소모품', MAINT: '소모품', SUPPLY: '소모품', RAW: '원자재', MATERIAL: '원자재', FG: '완제품', FINISHED: '완제품' };
const isFG = (i: R) => i.category === 'FG' || i.category === 'FINISHED';
// 한눈에 보기 묶음 — [이름, 설명]
const GROUPS: [string, string][] = [['절삭 공구', 'SUP 관리 · 사용 = 공구 교체 기록 (OPR·MNT)'], ['정비 소모품', 'MNT 관리 · 사용 = 작업기록서·예방 정비'], ['원자재', 'SUP 관리 · 사용 = 로트 투입 때 자동'], ['완제품', '']];
const groupOf = (i: R) => (i.category === 'TOOL' ? '절삭 공구' : i.category === 'RAW' || i.category === 'MATERIAL' ? '원자재' : isFG(i) ? '완제품' : '정비 소모품');
// 원자재 입고 검사 4가지 (6061-T6 봉재) — shortcut: 결과는 브라우저에만 저장, 서버 API 생기면 옮김
const IN_CHECKS: [string, string][] = [['성적서 EN 10204 3.1 받음', '공급사 밀시트'], ['로트 코드 일치', '성적서 히트·배치 번호 = 입고품 표시'], ['성분 범위 안', 'KS D 6763 6061 — Mg 0.80~1.20 · Si 0.40~0.80 · Cu 0.15~0.40 등'], ['기계적 성질 최소값 이상', '압출봉 T6 — 인장 260 · 항복 240 N/mm² · 연신율 10%']];
const TXN: Record<string, string> = { IN: '입고', USE: '사용', ADJUST: '조정', FG_IN: '합격 입고', SHIP: '출하', RECEIVE: '입고' };
const box = 'rounded-2xl border border-slate-300 bg-white p-5';
const tabBtn = (on: boolean) => `h-14 rounded-xl border px-7 text-[18px] font-bold ${on ? 'border-[#1f5fc4] bg-[#1f5fc4] text-white' : 'border-slate-300 bg-white text-[#1f4fa8]'}`;

export function InventoryScreen() {
  const { inv, reloadInv, role, user, back, go, toast, twin, eve } = useApp(); // eve: 이브 창이 열려 좁을 때 배치 바꿈
  const [tab, setTab] = useState<'stock' | 'ship'>('stock');
  const [shipTab, setShipTab] = useState<'now' | 'past'>('now');
  const [cat, setCat] = useState('');
  const [form, setForm] = useState<{ item: string; type: 'IN' | 'ADJUST'; qty: string; memo: string } | null>(null);
  const lots = useFetch<{ lots: R[] }>('lots', 15000, []);
  const ships = useFetch<{ shipments: R[] }>('shipments', 20000);
  const [ship, setShip] = useState<Record<string, number>>({});
  const [fifoWhy, setFifoWhy] = useState(''); const [memo, setMemo] = useState('');
  const [review, setReview] = useState(false); // 3단계 "출하 전 확인"으로 넘어감
  const [confirm, setConfirm] = useState(false);
  const [pastSel, setPastSel] = useState<string | null>(null);
  const [inCheck, setInCheck] = usePersist<Record<string, boolean[]>>('invInCheck', {}, twin?.run_id ?? null);
  const [inDone, setInDone] = usePersist<Record<string, string>>('invInDone', {}, twin?.run_id ?? null);
  if (!inv) return <div className={PAGE}><div className={box}>재고를 불러오는 중… <button onClick={back} className={BTN}>닫기</button></div></div>;

  const lowN = inv.items.filter((i) => i.low).length;
  const txns: R[] = [...inv.live_txns.map((t) => ({ ...t, live: true })), ...[...inv.past_txns].reverse()].slice(0, 60);
  const name = (no: string) => inv.items.find((i) => i.item_no === no)?.item_name ?? no;
  const allLots = lots.data?.lots ?? [];
  const left = (l: R) => l.fg_qty - (l.shipped?.qty ?? 0);
  const avail = allLots.filter((l) => (l.status === 'PASSED' || l.status === 'RELEASED') && left(l) > 0).sort((a, b) => (a.passed_at < b.passed_at ? -1 : 1));
  const held = allLots.filter((l) => l.on_hold || l.status === 'ON_HOLD');
  const dueOf = (l: R) => twin?.orders.find((o) => o.order_no === l.order_no)?.due_at ?? null;
  const today = twin?.clock.sim_at?.slice(0, 10) ?? '2026-10-01';
  const chosen = Object.entries(ship).filter(([, q]) => q > 0);
  const total = chosen.reduce((n, [, q]) => n + q, 0);
  const fifo = chosen.every(([lot]) => avail.slice(0, avail.findIndex((l) => l.lot_no === lot)).every((l) => ship[l.lot_no] === left(l)));
  const enough = chosen.every(([lot, q]) => { const l = avail.find((x) => x.lot_no === lot); return !!l && q <= left(l); });
  const okN = Number(chosen.length > 0) + Number(enough && chosen.length > 0) + Number(chosen.length > 0 && (fifo || !!fifoWhy.trim()));
  const can = role === 'SUP' && chosen.length > 0 && enough && (fifo || fifoWhy.trim());
  const shipList = ships.data?.shipments ?? [];
  const lastNo = shipList.map((s) => String(s.shipment_no)).sort().pop() ?? 'SHP-2609-000';
  const nextNo = lastNo.replace(/(\d+)$/, (m) => String(Number(m) + 1).padStart(m.length, '0'));
  const fgNow = Number(inv.items.find(isFG)?.stock_qty ?? 0);
  const orders = Array.from(new Set(chosen.map(([lot]) => allLots.find((l) => l.lot_no === lot)?.order_no).filter(Boolean))).sort();
  const step = chosen.length === 0 ? 1 : !review ? 2 : 3;
  const fgItem = inv.items.find(isFG), rmItem = inv.items.find((i) => groupOf(i) === '원자재');
  const heldQty = inv.held_lot_qty || held.reduce((n, l) => n + Number(l.input_qty ?? 0), 0);
  const myItems = inv.items.filter((i) => i.owner_role === role && !isFG(i));
  const pendingIn = inv.live_txns.filter((t) => rmItem && t.item_no === rmItem.item_no && Number(t.qty_change) > 0 && (t.txn_type === 'IN' || t.txn_type === 'RECEIVE') && !inDone[String(t.txn_id ?? t.txn_at)]) as R[];
  const setQ = (lot: string, q: number, max: number) => { setShip((s) => ({ ...s, [lot]: Math.max(0, Math.min(max, q)) })); setReview(false); };

  const save = async () => {
    if (!form) return;
    try { await api('inventory/txns', { role, user_id: user.id, item_no: form.item, txn_type: form.type, qty: Number(form.qty), memo: form.memo }); toast(`${name(form.item)} ${form.type === 'IN' ? '입고' : '조정'} ${form.qty}`); setForm(null); reloadInv(); }
    catch (e) { toast((e as Error).message); }
  };

  return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1400px] flex-col gap-4">
        <div className="flex gap-3">
          <button onClick={() => setTab('stock')} className={tabBtn(tab === 'stock')}>재고 {lowN > 0 && <span className="ml-2 rounded-full border border-[#e0b000] bg-[#fff6d6] px-2 py-0.5 text-[13px] text-[#7a5600]">▲ 부족 {lowN}</span>}</button>
          <button onClick={() => setTab('ship')} className={tabBtn(tab === 'ship')}>출하 등록 {chosen.length > 0 && <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-[13px] text-[#1c2530]">작성 중</span>}</button>
        </div>

        {tab === 'stock' ? (<>
          {/* 한눈에 보기 */}
          <section className={box}>
            <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />한눈에 보기</h3><span className="rounded-full border border-slate-400 px-3 py-1 text-[13px]">입고 검사 대기 {pendingIn.length}</span></div>
            <div className="mt-3 flex flex-wrap gap-2">{(['전체', ...GROUPS.map((g) => g[0])] as string[]).map((g) => { const its = g === '전체' ? inv.items : inv.items.filter((i) => groupOf(i) === g), lw = its.filter((i) => i.low).length; return (
              <button key={g} onClick={() => setCat(g === '전체' ? '' : g)} className={`flex h-11 items-center gap-2 rounded-lg border px-4 text-[15px] font-bold ${(cat || '전체') === g ? 'border-[#1f5fc4] bg-[#1f5fc4] text-white' : 'border-slate-300 bg-white text-[#1f4fa8]'}`}>{g} <span className="font-normal">{its.length}</span>{lw > 0 && <span className="rounded-full border border-[#e0b000] bg-[#fff6d6] px-2 text-[12px] text-[#7a5600]">▲ {lw}</span>}</button>); })}</div>
            <div className={`mt-4 grid gap-8 ${eve ? 'grid-cols-1' : 'grid-cols-[1.45fr_1fr]'}`}>
              <div>
                <div className="flex items-center gap-4 text-[13px]"><b className="text-[15px]">재고 여유</b><span><i className="mr-1 inline-block h-2 w-5 rounded-sm bg-[#4b5563]" />지금</span><span><i className="mr-1 inline-block h-3 w-[2px] bg-[#1c2530]" />안전 재고</span></div>
                {GROUPS.filter(([g]) => g !== '완제품' && (!cat || cat === g)).map(([g, note]) => { const its = inv.items.filter((i) => groupOf(i) === g); if (!its.length) return null; return (
                  <div key={g} className="mt-4">
                    <div className="text-[14px]"><b className="text-[15px]">{g}</b> <span className="ml-1 text-[12px] text-slate-500">{note}{g === '원자재' && pendingIn.length ? ` · 입고 검사 대기 ${pendingIn.reduce((n, t) => n + Number(t.qty_change), 0)} (재고에 안 넣음)` : ''}</span></div>
                    <div className={`mt-2 grid gap-2 ${g === '원자재' ? 'grid-cols-1' : 'grid-cols-2'}`}>{its.map((i) => { const mx = Math.max(i.stock_qty, i.safety_stock * 2, 1); return (
                      <div key={i.item_no} className={`grid grid-cols-[120px_1fr_auto] items-center gap-3 rounded-lg border px-3 py-2.5 ${i.low ? 'border-[#ecd47a] bg-[#fdf6dc]' : 'border-slate-200 bg-white'}`}>
                        <span className="truncate text-[14px]">{i.low && <span className="text-[#b8860b]">▲ </span>}{i.item_name}</span>
                        <div className="relative h-2.5 rounded bg-slate-100"><div className="h-full rounded" style={{ width: `${(i.stock_qty / mx) * 100}%`, background: i.low ? '#e0b000' : '#4b5563' }} /><span className="absolute -top-1.5 h-[22px] w-[2px] bg-[#1c2530]" style={{ left: `${(i.safety_stock / mx) * 100}%` }} /></div>
                        <span className="whitespace-nowrap text-right"><b className="font-mono text-[16px]">{Math.round(i.stock_qty * 10) / 10}</b> <span className="font-mono text-[13px] text-slate-500">/ {i.safety_stock} {i.unit}</span></span>
                      </div>); })}</div>
                  </div>); })}
              </div>
              {(!cat || cat === '완제품') && fgItem && (
                <div className={eve ? 'border-t border-slate-200 pt-4' : ''}>
                  <b className="text-[15px]">완제품 {fgItem.item_name.replace(' 완제품', '')}</b>
                  <div className={eve ? 'grid grid-cols-2 gap-x-8' : ''}>{/* 이브 열림: 4줄을 2칸씩 */}
                  {([['지금', fgNow, '#4b5563', false], ['이번 출하', -total, '', true], ['출하 뒤', Math.max(0, fgNow - total), '#4b5563', false], ['🔒 보류', heldQty, '', false]] as [string, number, string, boolean][]).map(([k, v, c, dash]) => (
                    <div key={k} className="mt-3 grid grid-cols-[80px_1fr_56px] items-center gap-3 text-[14px]"><span>{k}</span>
                      <div className="relative h-5 rounded bg-slate-100">{dash ? <div className="absolute inset-y-0 right-0 rounded border border-dashed border-slate-500" style={{ width: `${fgNow ? (total / fgNow) * 100 : 0}%` }} /> : c ? <div className="h-full rounded" style={{ width: `${fgNow ? (Math.max(0, v) / fgNow) * 100 : 0}%`, background: c }} /> : <div className="h-full w-5 rounded border-2 border-[#1c2530]" />}</div>
                      <b className="text-right font-mono text-[17px]">{v}</b></div>))}
                  </div>
                </div>)}
            </div>
          </section>

          <div className="grid grid-cols-[1.6fr_1fr] items-start gap-4">
            {/* 거래 기록 */}
            <section className={box}>
              <h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />거래 기록</h3>
              <ul className="mt-3 max-h-[300px] divide-y divide-slate-100 overflow-y-auto border-t border-slate-200 text-[14px]">{txns.map((t, i) => { const ref = t.lot_no || t.fg_lot_no; const q = Number(t.qty_change); return (
                <li key={i} className="grid grid-cols-[90px_80px_1fr_70px] items-center gap-2 py-2.5">
                  <span className={`font-mono ${t.live ? '' : 'text-slate-500'}`}>{t.live ? '' : `${md(t.txn_at)} `}{hm(t.txn_at)}</span><b>{TXN[t.txn_type] ?? t.txn_type}</b>
                  <span className="min-w-0 truncate">{name(t.item_no)} {ref ? <button onClick={() => go('lots', ref)} className="rounded border border-[#9db6ea] px-1.5 font-mono text-[12px] text-[#1f5fc4] underline">{ref}</button> : t.shipment_no ? <span className="rounded border border-slate-300 px-1.5 font-mono text-[12px]">{t.shipment_no}</span> : t.memo ? <span className="rounded border border-slate-300 px-1.5 text-[12px]">{t.memo}</span> : null}</span>
                  <b className="text-right font-mono">{q > 0 ? '+' : ''}{Math.round(q * 100) / 100}</b>
                </li>); })}</ul>
            </section>

            {/* 할 일 */}
            <section className={box}>
              <h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />할 일</h3>
              <div className="mt-3 flex flex-wrap gap-2 border-b border-slate-200 pb-4">
                <button disabled={!myItems.length} onClick={() => setForm({ item: myItems[0]?.item_no ?? '', type: 'IN', qty: '', memo: '' })} className="h-11 rounded-lg border border-slate-300 bg-white px-4 text-[15px] font-bold text-[#1f4fa8] disabled:text-slate-400">입고 등록</button>
                <button disabled={!myItems.length} onClick={() => setForm({ item: myItems[0]?.item_no ?? '', type: 'ADJUST', qty: '', memo: '' })} className="h-11 rounded-lg border border-slate-300 bg-white px-4 text-[15px] font-bold text-[#1f4fa8] disabled:text-slate-400">실사·조정</button>
                <button onClick={() => setTab('ship')} className="h-11 rounded-lg bg-[#1f5fc4] px-4 text-[15px] font-bold text-white">출하 등록</button>
              </div>
              {form && (
                <div className="mt-3 flex flex-col gap-2 rounded-xl border border-slate-300 p-3 text-[14px]">
                  <b>{form.type === 'IN' ? '입고 등록' : '실사·조정 (±)'}</b>
                  <select value={form.item} onChange={(e) => setForm({ ...form, item: e.target.value })} className="h-10 rounded-lg border border-slate-300">{myItems.map((i) => <option key={i.item_no} value={i.item_no}>{i.item_name}</option>)}</select>
                  <input value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })} placeholder="수량" className="h-10 rounded-lg border border-slate-300 px-2" />
                  <input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} placeholder={form.type === 'ADJUST' ? '조정 사유 (필수)' : '원자재면 원자재 로트·성적서 번호'} className="h-10 rounded-lg border border-slate-300 px-2" />
                  <div className="flex gap-2"><button onClick={save} className={DARK}>저장</button><button onClick={() => setForm(null)} className={BTN}>취소</button></div>
                </div>)}
              <div className="mt-4 text-[15px] font-bold">원자재 입고 검사</div>
              {pendingIn.length === 0 ? <p className="mt-2 text-[14px] text-slate-500">검사할 원자재 입고 없음</p> : (() => { const t = pendingIn[0], k = String(t.txn_id ?? t.txn_at), c = inCheck[k] ?? [];
                return (<div className="mt-2">
                  <div className="text-[14px]"><b className="font-mono">{String(t.memo || t.lot_no || '원자재 입고')}</b> · {Number(t.qty_change)}{rmItem?.unit ?? ''} · {hm(t.txn_at)}</div>
                  <div className="mt-2 flex flex-col gap-2">{IN_CHECKS.map(([title, sub], j) => (
                    <label key={title} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2"><input type="checkbox" disabled={role !== 'SUP'} checked={!!c[j]} onChange={() => setInCheck((m) => { const a = [...(m[k] ?? [])]; a[j] = !a[j]; return { ...m, [k]: a }; })} className="mt-1 h-5 w-5" />
                      <span><b className="text-[14px]">{title}</b><span className="block text-[12px] text-slate-500">{sub}</span></span></label>))}</div>
                  <div className="mt-3 flex items-center gap-2"><span className="text-[14px]">확인 {c.filter(Boolean).length} / {IN_CHECKS.length}</span>
                    <button disabled={role !== 'SUP'} onClick={() => { setInDone((m) => ({ ...m, [k]: 'HOLD' })); toast('원자재 입고 보류'); }} className="ml-auto h-11 rounded-lg border border-slate-300 bg-white px-4 font-bold text-[#1f4fa8] disabled:text-slate-400">입고 보류</button>
                    <button disabled={role !== 'SUP' || c.filter(Boolean).length < IN_CHECKS.length} onClick={() => { setInDone((m) => ({ ...m, [k]: 'OK' })); toast('원자재 사용 가능'); }} className="h-11 rounded-lg bg-[#1f5fc4] px-4 font-bold text-white disabled:bg-slate-200 disabled:text-slate-500">사용 가능</button></div>
                  <p className="mt-2 text-[12px] text-slate-500">사용 가능은 {IN_CHECKS.length}가지를 모두 확인해야 누를 수 있습니다. 하나라도 맞지 않으면 입고 보류.</p>
                </div>); })()}
            </section>
          </div>
        </>) : (<>
          <div className="flex gap-3">
            <button onClick={() => setShipTab('now')} className={`h-12 rounded-lg border px-5 text-[16px] font-bold ${shipTab === 'now' ? 'border-[#1f5fc4] bg-[#1f5fc4] text-white' : 'border-slate-300 bg-white text-[#1f4fa8]'}`}>이번 출하 {nextNo}</button>
            <button onClick={() => setShipTab('past')} className={`h-12 rounded-lg border px-5 text-[16px] font-bold ${shipTab === 'past' ? 'border-[#1f5fc4] bg-[#1f5fc4] text-white' : 'border-slate-300 bg-white text-[#1f4fa8]'}`}>지난 출하 {shipList.length}</button>
          </div>

          {shipTab === 'past' ? (() => {
            const list = [...shipList].reverse(), cur = list.find((s) => s.shipment_no === pastSel) ?? list[0];
            const sum = (s: R) => s.lines.reduce((n: number, x: R) => n + Number(x.qty), 0);
            return (
              <div className="grid grid-cols-[1fr_1.4fr] items-start gap-4">
                <section className={box}>
                  <h3 className="text-[19px] font-bold">지난 출하</h3>
                  <div className="mt-3 flex max-h-[560px] flex-col gap-2 overflow-y-auto">{list.map((s) => (
                    <button key={s.shipment_no} onClick={() => setPastSel(s.shipment_no)} className={`grid items-center rounded-xl border text-left ${eve ? 'grid-cols-[62px_1fr_auto] gap-2 px-3 py-2.5' : 'grid-cols-[150px_1fr_60px] gap-3 px-4 py-3'} ${s.shipment_no === cur?.shipment_no ? 'border-[#9db6ea] bg-[#eef3fd]' : 'border-slate-200 bg-white'}`}>
                      {/* 이브 열림: SHP / -2610 / -001 세 줄로 접어 폭을 줄이고 수량을 당겨 옴 */}
                      {eve
                        ? <b className="font-mono text-[14px] leading-tight">{String(s.shipment_no).split('-').map((p, i) => <span key={i} className="block">{i ? `-${p}` : p}</span>)}</b>
                        : <b className="font-mono text-[16px]">{s.shipment_no}</b>}
                      <span className="min-w-0 text-[15px]"><span className="whitespace-nowrap">{md(s.shipped_at)} {hm(s.shipped_at)}</span> · <span className="whitespace-nowrap">{s.customer_code}</span><span className="block text-[13px] text-slate-500">{s.status === 'CONFIRMED' ? '확정' : s.status} · 로트 {s.lines.length}</span></span>
                      <b className={`text-right font-mono ${eve ? 'pr-1 text-[20px]' : 'text-[18px]'}`}>{sum(s)}</b>
                    </button>))}</div>
                </section>
                {cur && (
                  <section className={box}>
                    <div className="flex items-center justify-between"><h3 className="text-[19px] font-bold">출하 <span className="font-mono">{cur.shipment_no}</span></h3>{cur.status === 'CONFIRMED' && <span className="rounded-lg border-2 border-[#1c2530] px-3 py-1 text-[16px] font-bold">🔒 확정</span>}</div>
                    <div className="mt-3 grid grid-cols-3 gap-4 text-[15px]">
                      <div><div className="text-[13px] text-slate-500">출하 일시</div>{md(cur.shipped_at)} {hm(cur.shipped_at)}</div>
                      <div><div className="text-[13px] text-slate-500">출하처</div>{cur.customer_code}</div>
                      <div><div className="text-[13px] text-slate-500">확인자</div>{cur.confirmed_by ? userName(cur.confirmed_by) : '—'}</div>
                      <div className="col-span-3"><div className="text-[13px] text-slate-500">비고</div>{cur.fifo_skip_reason || cur.memo || '—'}</div>
                    </div>
                    {/* 이브 열림: 출하 로트 표를 줄임 — 합격 칸을 빼고 줄 간격·글자를 줄임 */}
                    <table className={`w-full text-left ${eve ? 'mt-3 text-[14px]' : 'mt-4 text-[15px]'}`}>
                      <thead className="border-b border-slate-200 text-[13px] text-slate-500"><tr><th className={eve ? 'py-1.5' : 'py-2'}>로트</th>{!eve && <th>합격</th>}<th className="text-right">수량</th></tr></thead>
                      <tbody className="divide-y divide-slate-100">{cur.lines.map((x: R) => (
                        <tr key={x.lot_no}><td className={eve ? 'py-1.5' : 'py-2.5'}><button onClick={() => go('lots', x.lot_no)} className="font-mono text-[#1f5fc4] underline">{x.lot_no}</button></td>{!eve && <td className="font-mono">{x.lot_passed_at ? `${md(x.lot_passed_at)} ${hm(x.lot_passed_at)}` : '—'}</td>}<td className="text-right font-mono font-bold">{x.qty}</td></tr>))}</tbody>
                    </table>
                    <div className="mt-2 border-t border-slate-200 pt-2 text-right text-[16px]">합 <b className="font-mono text-[18px]">{sum(cur)}</b> 개</div>
                    <div className="mt-4 text-[15px] font-bold">버전</div>
                    <div className="mt-1 grid grid-cols-[50px_160px_1fr] text-[15px]"><b className="font-mono">v{cur.current_version || 0}</b><span>{cur.confirmed_by ? userName(cur.confirmed_by) : '—'}</span><span>확정 {md(cur.shipped_at)} {hm(cur.shipped_at)}</span></div>
                  </section>)}
              </div>);
          })() : (<>
            {/* 단계 */}
            <section className={`${box} grid grid-cols-4 gap-2 !p-3`}>{([['로트 고르기', `합격 로트 ${avail.length}`], ['수량', `로트 ${chosen.length} · ${total}개`], ['출하 전 확인', `${okN} / 3`], ['확정', '확인 상자']] as const).map(([t, sub], i) => {
              const n = i + 1, done = n < step, on = n === step;
              return <div key={t} className={`flex items-center gap-3 rounded-xl border px-3 py-2 ${on ? 'border-[#9db6ea] bg-[#e8eefb]' : 'border-slate-200'}`}>
                <span className={`flex h-10 w-10 items-center justify-center rounded-full font-bold ${done ? 'bg-[#3d4a5c] text-white' : on ? 'bg-[#1f5fc4] text-white' : 'border-2 border-slate-300 text-slate-500'}`}>{done ? '✓' : n}</span>
                <div><div className="text-[17px] font-bold">{t}</div><div className="text-[13px] text-slate-500">{sub}</div></div></div>;
            })}</section>

            <div className="grid grid-cols-[1.6fr_1fr] items-start gap-4">
              {/* 합격 로트 */}
              <section className={box}>
                <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-[17px] font-bold"><span className="h-2.5 w-2.5 rounded-full bg-[#1f5fc4]" />합격 로트</h3>
                  {role === 'SUP' && <button onClick={() => { setShip(Object.fromEntries(avail.filter((l) => (dueOf(l) ?? '0000').slice(0, 10) <= today).map((l) => [l.lot_no, left(l)]))); setReview(false); }} className="h-11 rounded-lg border border-slate-300 bg-white px-4 text-[14px] text-[#1f5fc4] disabled:text-slate-400">오늘 납기 전부 채우기</button>}</div>
                {avail.length === 0 ? <p className="mt-3 text-[14px] text-slate-500">출하할 수 있는 합격 로트가 없습니다</p> : (
                  <div className="mt-3 grid grid-cols-2 gap-3">{avail.slice(0, 12).map((l) => { const q = ship[l.lot_no] ?? 0, mx = left(l), due = dueOf(l); return (
                    <div key={l.lot_no} className={`flex gap-3 rounded-xl border p-3 ${eve ? 'flex-col items-stretch' : 'items-center'} ${q > 0 ? 'border-[#9db6ea] bg-[#f3f6ff]' : 'border-slate-200 bg-white'}`}>{/* 이브 열림: 로트 번호 → 설명 → −0+ 위에서 아래로 */}
                      <div className="min-w-0 flex-1"><button onClick={() => go('lots', l.lot_no)} className="whitespace-nowrap font-mono text-[16px] font-bold text-[#1f5fc4] underline">{l.lot_no}</button>
                        <div className="text-[13px] text-slate-600">합격 {md(l.passed_at)} {hm(l.passed_at)} · 납기 {due ? md(due) : '—'} · 남은 {mx}</div>{q === mx && q > 0 && <div className="text-[12px] text-slate-500">전부</div>}</div>
                      {role === 'SUP' && (
                      <div className={`flex h-12 items-center overflow-hidden rounded-lg border border-slate-300 bg-white ${eve ? 'w-full' : ''}`}>
                        <button disabled={role !== 'SUP'} onClick={() => setQ(l.lot_no, q - 1, mx)} className="h-full w-11 shrink-0 text-[20px]">−</button>
                        <input disabled={role !== 'SUP'} value={q} onChange={(e) => setQ(l.lot_no, Number(e.target.value) || 0, mx)} className={`h-full min-w-0 border-x border-slate-200 text-center font-mono text-[18px] font-bold ${eve ? 'flex-1' : 'w-14'}`} />
                        <button disabled={role !== 'SUP'} onClick={() => setQ(l.lot_no, q + 1, mx)} className="h-full w-11 shrink-0 text-[20px]">+</button></div>
                      )}
                    </div>); })}</div>
                )}
                {held.slice(0, 3).map((l) => <div key={l.lot_no} className="mt-3 rounded-xl border border-dashed border-slate-400 bg-slate-50 px-4 py-3 text-[15px]">🔒 <button onClick={() => go('lots', l.lot_no)} className="font-mono font-bold text-[#1f5fc4] underline">{l.lot_no}</button> <b>보류</b> {l.input_qty} · 출하 불가</div>)}
              </section>

              {/* 출하 요약 */}
              <section className={box}>
                <div className="flex items-center justify-between gap-2"><h3 className="flex items-center gap-2 whitespace-nowrap text-[17px] font-bold"><span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#1f5fc4]" />출하 <span className="font-mono">{nextNo}</span></h3><span className="shrink-0 whitespace-nowrap rounded-lg border border-slate-300 px-3 py-1 text-[14px]">{chosen.length ? '작성 중' : '비어 있음'}</span></div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-[14px]">
                  <div><div className="text-[12px] text-slate-500">출하처</div>CUST-01</div>
                  <div><div className="text-[12px] text-slate-500">출하 일시</div>확정 때 기록</div>
                  <div className="col-span-2"><div className="text-[12px] text-slate-500">근거 작업지시 · 납기</div>{orders.length ? `${orders[0]}${orders.length > 1 ? `~${String(orders[orders.length - 1]).slice(-3)}` : ''}` : '—'}</div>
                </div>
                <div className="mt-3 border-t border-slate-200 pt-3 text-[15px]">출하 수량 합 <b className="font-mono text-[40px]">{total}</b> 개 · 로트 {chosen.length}</div>
                <div className="mt-2 grid grid-cols-[60px_1fr_50px] items-center gap-3 text-[14px]">
                  <span>지금</span><div className="h-5 rounded bg-[#4b5563]" /><b className="text-right font-mono">{fgNow}</b>
                  <span>출하 뒤</span><div className="h-5 overflow-hidden rounded border border-dashed border-slate-400"><div className="h-full bg-[#4b5563]" style={{ width: `${fgNow ? (Math.max(0, fgNow - total) / fgNow) * 100 : 0}%` }} /></div><b className="text-right font-mono">{Math.max(0, fgNow - total)}</b>
                </div>
                <div className={`mt-4 flex flex-col gap-2 text-[15px] ${review ? 'rounded-xl bg-[#f3f6ff] p-3' : ''}`}>
                  <label className="flex items-center gap-2"><input type="checkbox" readOnly checked={chosen.length > 0} className="h-4 w-4" />모든 로트 합격 (해제 포함)</label>
                  <label className="flex items-center gap-2"><input type="checkbox" readOnly checked={chosen.length > 0 && enough} className="h-4 w-4" />로트 남은 수량 ≥ 출하 수량</label>
                  <label className="flex items-center gap-2"><input type="checkbox" readOnly checked={chosen.length > 0 && fifo} className="h-4 w-4" />선입선출</label>
                  {chosen.length > 0 && !fifo && <input value={fifoWhy} onChange={(e) => setFifoWhy(e.target.value)} placeholder="먼저 합격한 로트부터가 아닌 사유 (필수)" className="h-10 rounded-lg border border-slate-300 px-2 text-[14px]" />}
                  <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="비고 (부분 출하·늦은 출하 사유)" className="h-10 rounded-lg border border-slate-300 px-2 text-[14px]" />
                </div>
                <div className="mt-4 flex justify-end">
                  {!review
                    ? <button disabled={chosen.length === 0} onClick={() => setReview(true)} className="h-14 rounded-xl bg-[#1f5fc4] px-6 text-[18px] font-bold text-white disabled:bg-slate-300">다음 · 출하 전 확인</button>
                    : <button disabled={!can} onClick={() => setConfirm(true)} className="h-14 rounded-xl bg-[#1f5fc4] px-6 text-[18px] font-bold text-white disabled:bg-slate-300">출하 확정</button>}
                </div>
                {role !== 'SUP' && <p className="mt-2 text-right text-[13px] text-slate-500">출하 등록은 반장</p>}
              </section>
            </div>
          </>)}
        </>)}
      </div>
      {confirm && <ConfirmBox title="출하를 확정할까요?" okLabel="출하 확정" body={`${chosen.map(([l, q]) => `${l} ${q}개`).join(', ')} — 확정하면 완제품 재고에서 빠지고, 고치려면 사유가 필요합니다.`}
        onOk={async () => { setConfirm(false); try { const r = await api<R>('shipments', { role, user_id: user.id, customer_code: 'CUST-01', lines: chosen.map(([lot_no, qty]) => ({ lot_no, qty })), fifo_skip_reason: fifo ? null : fifoWhy, memo }); toast(`출하 ${r.shipment_no} 확정`); setShip({}); setReview(false); ships.reload(); lots.reload(); reloadInv(); } catch (e) { toast((e as Error).message); } }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}
