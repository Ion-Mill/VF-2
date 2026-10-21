'use client';
// SCR-21 재고 — 13품목(공구 5·소모품 6·원자재 1·완제품 1), 관리 역할, 거래 기록, 입고·실사 조정(API-INV-02), 출하 등록(API-INV-04). 발주 버튼 없음.
// 화면 구조 (사용자 시안 2026-10-16): [재고] [출하 등록] 탭. 출하 등록 = 이번 출하/지난 출하 · 단계(로트 고르기→수량→출하 전 확인→확정) · 합격 로트 카드(−/+) · 출하 요약
import { LockIcon } from './ui';
import { useEffect, useRef, useState } from 'react';
import { BTN, DARK, PAGE, useApp } from './ctx';
import { Band, BandSkeleton, Skeleton, Tabs } from './ui';
import { inventoryBand } from './bands';
import { api, hm, md, useFetch, usePersist } from './live';
import { ROLE_NAME, userName } from './model';
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
const box = 'rounded-card border border-line bg-white p-5';
const tabBtn = (on: boolean) => `h-14 rounded-tile border px-7 text-band font-bold ${on ? 'border-ink bg-ink text-white' : 'border-line bg-white text-ink'}`;
// 할 일 버튼 — 누른 것(열린 입력 칸)만 파란색
const todo = (on: boolean) => `h-11 rounded-tile border px-4 text-card font-bold disabled:text-ink-3 ${on ? 'border-ink bg-ink text-white' : 'border-line bg-white text-ink'}`;

export function InventoryScreen() {
  const { key, inv, reloadInv, role, user, back, go, toast, twin, eve } = useApp(); // eve: 이브 창이 열려 좁을 때 배치 바꿈 · key: 재고 부족 알림에서 온 품목 번호
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
  const formRef = useRef<HTMLDivElement>(null), inRef = useRef<HTMLDivElement>(null);
  // 입고 등록 열기 — 알림·결론 띠 [입고 등록]에서 와도 입력 칸이 아래에 있어 안 보이던 것 고침: 품목을 미리 고르고 입력 칸으로 내려감 (사용자 요청 2026-10-21)
  const openIn = (itemNo?: string) => {
    if (!inv) return;
    const mine = inv.items.filter((i) => i.owner_role === role && !isFG(i));
    const it = inv.items.find((i) => i.item_no === itemNo);
    if (it && it.owner_role !== role) { toast(`${it.item_name} 입고 등록은 ${(ROLE_NAME as Record<string, string>)[it.owner_role] ?? it.owner_role} 담당이에요`); return; }
    const low = [...mine].filter((i) => i.low).sort((a, b) => a.stock_qty / Math.max(1, a.safety_stock) - b.stock_qty / Math.max(1, b.safety_stock))[0];
    const pick = it ?? low ?? mine[0];
    if (!pick) { toast('이 역할이 입고 등록하는 품목이 없어요'); return; }
    setTab('stock'); setForm({ item: pick.item_no, type: 'IN', qty: '', memo: '' });
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  };
  const ready = !!inv;
  useEffect(() => { if (ready && key && inv!.items.some((i) => i.item_no === key)) openIn(key); }, [key, ready]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!inv) return <div className={PAGE}><div className="flex flex-col gap-3"><BandSkeleton /><Skeleton /></div></div>; // C안: 불러오는 중에 [닫기] 없음

  const lowN = inv.items.filter((i) => i.low).length;
  // 최신이 위 — 오늘 기록(live_txns)은 오래된 것부터 와서 거꾸로 보이고, 화면에서 넣은 기록은 끝에 붙던 것 고침 (사용자 요청 2026-10-21)
  const txns: R[] = [...inv.live_txns.map((t) => ({ ...t, live: true }) as R), ...(inv.past_txns as R[])]
    .sort((a, b) => String(b.txn_at).localeCompare(String(a.txn_at)) || Number(b.txn_id ?? 0) - Number(a.txn_id ?? 0)).slice(0, 60);
  // 오늘(10/1 08:00 뒤) 품목별로 쓴 양 — 한눈에 보기에 지금 재고와 함께 보임 (사용자 요청 2026-10-21)
  const usedToday: Record<string, number> = {};
  inv.live_txns.forEach((t) => { const q = Number(t.qty_change); if (q < 0 && t.txn_type !== 'SHIP' && t.txn_type !== 'ADJUST') usedToday[String(t.item_no)] = (usedToday[String(t.item_no)] ?? 0) - q; });
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
      <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
        {/* 디자인 통일 C안: 큰 갈래 = Tabs(차콜 선택) · 재고 탭은 결론 띠 1개 (bands.ts inventoryBand) */}
        <div><Tabs label="재고 화면" value={tab} onChange={(k) => setTab(k as 'stock' | 'ship')} items={[{ key: 'stock', label: '재고', warn: lowN }, { key: 'ship', label: chosen.length > 0 ? '출하 등록 · 작성 중' : '출하 등록' }]} /></div>
        {tab === 'stock' && (() => { const spec = inventoryBand(inv.items, pendingIn.length); return <Band spec={spec} onAction={() => (spec.action === '입고 검사' ? inRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }) : openIn())} />; })()}

        {tab === 'stock' ? (<>
          {/* 한눈에 보기 */}
          <section className={box}>
            <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-card font-bold">한눈에 보기</h3><span className="rounded-full border border-line px-3 py-1 text-small">입고 검사 대기 {pendingIn.length}</span></div>
            <div className="mt-3 flex flex-wrap gap-2">{(['전체', ...GROUPS.map((g) => g[0])] as string[]).map((g) => { const its = g === '전체' ? inv.items : inv.items.filter((i) => groupOf(i) === g), lw = its.filter((i) => i.low).length; return (
              <button key={g} onClick={() => setCat(g === '전체' ? '' : g)} className={`flex h-11 items-center gap-2 rounded-tile border px-4 text-card font-bold ${(cat || '전체') === g ? 'border-ink bg-ink text-white' : 'border-line bg-white text-ink'}`}>{g} <span className="font-normal">{its.length}</span>{lw > 0 && <span className="rounded-full border border-warn-mark bg-warn-bg px-2 text-small text-warn">▲ {lw}</span>}</button>); })}</div>
            <div className={`mt-4 grid gap-8 ${eve ? 'grid-cols-1' : 'grid-cols-[1.45fr_1fr]'}`}>
              <div>
                <div className="flex items-center gap-4 text-small"><b className="text-card">재고 여유</b><span><i className="mr-1 inline-block h-2 w-5 rounded bg-info" />지금</span><span><i className="mr-1 inline-block h-3 w-[2px] bg-ink" />안전 재고</span></div>
                {GROUPS.filter(([g]) => g !== '완제품' && (!cat || cat === g)).map(([g, note]) => { const its = inv.items.filter((i) => groupOf(i) === g); if (!its.length) return null; return (
                  <div key={g} className="mt-4">
                    <div className="text-body"><b className="text-card">{g}</b> <span className="ml-1 text-small text-ink-2">{note}{g === '원자재' && pendingIn.length ? ` · 입고 검사 대기 ${pendingIn.reduce((n, t) => n + Number(t.qty_change), 0)} (재고에 안 넣음)` : ''}</span></div>
                    <div className={`mt-2 grid gap-2 ${g === '원자재' ? 'grid-cols-1' : 'grid-cols-2'}`}>{its.map((i) => { const mx = Math.max(i.stock_qty, i.safety_stock * 2, 1); return (
                      <div key={i.item_no} className={`grid grid-cols-[120px_1fr_auto] items-center gap-3 rounded-tile border px-3 py-2.5 ${i.low ? 'border-warn-line bg-warn-bg' : 'border-line-soft bg-white'}`}>
                        <span className="truncate text-body">{i.low && <span className="text-warn">▲ </span>}{i.item_name}</span>
                        <div className="relative h-2.5 rounded bg-tile"><div className="h-full rounded" style={{ width: `${(i.stock_qty / mx) * 100}%`, background: i.low ? '#e0b000' : '#4b5563' }} /><span className="absolute -top-1.5 h-[22px] w-[2px] bg-ink" style={{ left: `${(i.safety_stock / mx) * 100}%` }} /></div>
                        <span className="whitespace-nowrap text-right"><b className="font-mono text-card">{Math.round(i.stock_qty * 10) / 10}</b> <span className="font-mono text-small text-ink-2">/ {i.safety_stock} {i.unit}</span>
                          {usedToday[i.item_no] ? <span className="block font-mono text-small text-ink-2">오늘 사용 −{Math.round(usedToday[i.item_no] * 100) / 100}</span> : null}</span>
                      </div>); })}</div>
                  </div>); })}
              </div>
              {(!cat || cat === '완제품') && fgItem && (
                <div className={eve ? 'border-t border-line-soft pt-4' : ''}>
                  <b className="text-card">완제품 {fgItem.item_name.replace(' 완제품', '')}</b>
                  <div className={eve ? 'grid grid-cols-2 gap-x-8' : ''}>{/* 이브 열림: 4줄을 2칸씩 */}
                  {([['지금', fgNow, '#4b5563', false], ['이번 출하', -total, '', true], ['출하 뒤', Math.max(0, fgNow - total), '#4b5563', false], ['보류', heldQty, '', false]] as [string, number, string, boolean][]).map(([k, v, c, dash]) => (
                    <div key={k} className="mt-3 grid grid-cols-[80px_1fr_56px] items-center gap-3 text-body"><span>{k === '보류' && <LockIcon />} {k}</span>
                      <div className="relative h-5 rounded bg-tile">{dash ? <div className="absolute inset-y-0 right-0 rounded border border-dashed border-slate-500" style={{ width: `${fgNow ? (total / fgNow) * 100 : 0}%` }} /> : c ? <div className="h-full rounded" style={{ width: `${fgNow ? (Math.max(0, v) / fgNow) * 100 : 0}%`, background: c }} /> : <div className="h-full w-5 rounded border-2 border-ink" />}</div>
                      <b className="text-right font-mono text-band">{v}</b></div>))}
                  </div>
                </div>)}
            </div>
          </section>

          <div className="grid grid-cols-[1.6fr_1fr] items-start gap-4">
            {/* 거래 기록 */}
            <section className={box}>
              <h3 className="flex items-center gap-2 text-card font-bold">거래 기록</h3>
              <ul className="mt-3 max-h-[300px] divide-y divide-slate-100 overflow-y-auto border-t border-line-soft text-body">{txns.map((t, i) => { const ref = t.lot_no || t.fg_lot_no; const q = Number(t.qty_change); return (
                <li key={i} className="grid grid-cols-[90px_80px_1fr_70px] items-center gap-2 py-2.5">
                  <span className={`font-mono ${t.live ? '' : 'text-ink-2'}`}>{t.live ? '' : `${md(t.txn_at)} `}{hm(t.txn_at)}</span><b>{TXN[t.txn_type] ?? t.txn_type}</b>
                  <span className="min-w-0 truncate">{name(t.item_no)} {ref ? <button onClick={() => go('lots', ref)} className="rounded border border-brand-line px-1.5 font-mono text-small text-brand underline">{ref}</button> : t.shipment_no ? <span className="rounded border border-line px-1.5 font-mono text-small">{t.shipment_no}</span> : t.memo ? <span className="rounded border border-line px-1.5 text-small">{t.memo}</span> : null}</span>
                  <b className="text-right font-mono">{q > 0 ? '+' : ''}{Math.round(q * 100) / 100}</b>
                </li>); })}</ul>
            </section>

            {/* 할 일 */}
            <section className={box}>
              <h3 className="flex items-center gap-2 text-card font-bold">할 일</h3>
              {/* 누른 버튼(열린 입력 칸)만 파란색 — 출하 등록이 늘 파래서 눌린 것처럼 보이던 것을 고침 (사용자 요청 2026-10-20) */}
              <div className="mt-3 flex flex-wrap gap-2 border-b border-line-soft pb-4">
                <button disabled={!myItems.length} onClick={() => openIn()} className={todo(form?.type === 'IN')}>입고 등록</button>
                <button disabled={!myItems.length} onClick={() => setForm({ item: myItems[0]?.item_no ?? '', type: 'ADJUST', qty: '', memo: '' })} className={todo(form?.type === 'ADJUST')}>실사·조정</button>
                <button onClick={() => setTab('ship')} className={todo(false)}>출하 등록</button>
              </div>
              {form && (
                <div ref={formRef} className="mt-3 flex scroll-mt-24 flex-col gap-2 rounded-tile border border-line p-3 text-body">
                  <b>{form.type === 'IN' ? '입고 등록' : '실사·조정 (±)'}</b>
                  <select value={form.item} onChange={(e) => setForm({ ...form, item: e.target.value })} className="h-10 rounded-tile border border-line">{myItems.map((i) => <option key={i.item_no} value={i.item_no}>{i.item_name}</option>)}</select>
                  <input value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })} placeholder="수량" className="h-10 rounded-tile border border-line px-2" />
                  <input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} placeholder={form.type === 'ADJUST' ? '조정 사유 (필수)' : '원자재면 원자재 로트·성적서 번호'} className="h-10 rounded-tile border border-line px-2" />
                  <div className="flex gap-2"><button onClick={save} className={DARK}>저장</button><button onClick={() => setForm(null)} className={BTN}>취소</button></div>
                </div>)}
              <div ref={inRef} className="mt-4 text-card font-bold">원자재 입고 검사</div>
              {pendingIn.length === 0 ? <p className="mt-2 text-body text-ink-2">검사할 원자재 입고 없음</p> : (() => { const t = pendingIn[0], k = String(t.txn_id ?? t.txn_at), c = inCheck[k] ?? [];
                return (<div className="mt-2">
                  <div className="text-body"><b className="font-mono">{String(t.memo || t.lot_no || '원자재 입고')}</b> · {Number(t.qty_change)}{rmItem?.unit ?? ''} · {hm(t.txn_at)}</div>
                  <div className="mt-2 flex flex-col gap-2">{IN_CHECKS.map(([title, sub], j) => (
                    <label key={title} className="flex cursor-pointer items-start gap-3 rounded-tile border border-line-soft bg-white px-3 py-2"><input type="checkbox" disabled={role !== 'SUP'} checked={!!c[j]} onChange={() => setInCheck((m) => { const a = [...(m[k] ?? [])]; a[j] = !a[j]; return { ...m, [k]: a }; })} className="mt-1 h-5 w-5" />
                      <span><b className="text-body">{title}</b><span className="block text-small text-ink-2">{sub}</span></span></label>))}</div>
                  <div className="mt-3 flex items-center gap-2"><span className="text-body">확인 {c.filter(Boolean).length} / {IN_CHECKS.length}</span>
                    <button disabled={role !== 'SUP'} onClick={() => { setInDone((m) => ({ ...m, [k]: 'HOLD' })); toast('원자재 입고 보류'); }} className="ml-auto h-11 rounded-tile border border-line bg-white px-4 font-bold text-brand disabled:text-ink-3">입고 보류</button>
                    <button disabled={role !== 'SUP' || c.filter(Boolean).length < IN_CHECKS.length} onClick={() => { setInDone((m) => ({ ...m, [k]: 'OK' })); toast('원자재 사용 가능'); }} className="h-11 rounded-tile bg-brand px-4 font-bold text-white disabled:bg-track disabled:text-ink-2">사용 가능</button></div>
                  <p className="mt-2 text-small text-ink-2">사용 가능은 {IN_CHECKS.length}가지를 모두 확인해야 누를 수 있습니다. 하나라도 맞지 않으면 입고 보류.</p>
                </div>); })()}
            </section>
          </div>
        </>) : (<>
          <div className="flex gap-3">
            <button onClick={() => setShipTab('now')} className={`h-12 rounded-tile border px-5 text-card font-bold ${shipTab === 'now' ? 'border-ink bg-ink text-white' : 'border-line bg-white text-ink'}`}>이번 출하 {nextNo}</button>
            <button onClick={() => setShipTab('past')} className={`h-12 rounded-tile border px-5 text-card font-bold ${shipTab === 'past' ? 'border-ink bg-ink text-white' : 'border-line bg-white text-ink'}`}>지난 출하 {shipList.length}</button>
          </div>

          {shipTab === 'past' ? (() => {
            const list = [...shipList].reverse(), cur = list.find((s) => s.shipment_no === pastSel) ?? list[0];
            const sum = (s: R) => s.lines.reduce((n: number, x: R) => n + Number(x.qty), 0);
            return (
              <div className="grid grid-cols-[1fr_1.4fr] items-start gap-4">
                <section className={box}>
                  <h3 className="text-card font-bold">지난 출하</h3>
                  <div className="mt-3 flex max-h-[560px] flex-col gap-2 overflow-y-auto">{list.map((s) => (
                    <button key={s.shipment_no} onClick={() => setPastSel(s.shipment_no)} className={`grid items-center rounded-tile border text-left ${eve ? 'grid-cols-[62px_1fr_auto] gap-2 px-3 py-2.5' : 'grid-cols-[150px_1fr_60px] gap-3 px-4 py-3'} ${s.shipment_no === cur?.shipment_no ? 'border-brand-line bg-[#f4f0ff]' : 'border-line-soft bg-white'}`}>
                      {/* 이브 열림: SHP / -2610 / -001 세 줄로 접어 폭을 줄이고 수량을 당겨 옴 */}
                      {eve
                        ? <b className="font-mono text-body leading-tight">{String(s.shipment_no).split('-').map((p, i) => <span key={i} className="block">{i ? `-${p}` : p}</span>)}</b>
                        : <b className="font-mono text-card">{s.shipment_no}</b>}
                      <span className="min-w-0 text-card"><span className="whitespace-nowrap">{md(s.shipped_at)} {hm(s.shipped_at)}</span> · <span className="whitespace-nowrap">{s.customer_code}</span><span className="block text-small text-ink-2">{s.status === 'CONFIRMED' ? '확정' : s.status} · 로트 {s.lines.length}</span></span>
                      <b className={`text-right font-mono ${eve ? 'pr-1 text-title' : 'text-band'}`}>{sum(s)}</b>
                    </button>))}</div>
                </section>
                {cur && (
                  <section className={box}>
                    <div className="flex items-center justify-between"><h3 className="text-card font-bold">출하 <span className="font-mono">{cur.shipment_no}</span></h3>{cur.status === 'CONFIRMED' && <span className="rounded-tile border-2 border-ink px-3 py-1 text-card font-bold"><LockIcon /> 확정</span>}</div>
                    <div className="mt-3 grid grid-cols-3 gap-4 text-card">
                      <div><div className="text-small text-ink-2">출하 일시</div>{md(cur.shipped_at)} {hm(cur.shipped_at)}</div>
                      <div><div className="text-small text-ink-2">출하처</div>{cur.customer_code}</div>
                      <div><div className="text-small text-ink-2">확인자</div>{cur.confirmed_by ? userName(cur.confirmed_by) : '—'}</div>
                      <div className="col-span-3"><div className="text-small text-ink-2">비고</div>{cur.fifo_skip_reason || cur.memo || '—'}</div>
                    </div>
                    {/* 이브 열림: 출하 로트 표를 줄임 — 합격 칸을 빼고 줄 간격·글자를 줄임 */}
                    <table className={`w-full text-left ${eve ? 'mt-3 text-body' : 'mt-4 text-card'}`}>
                      <thead className="border-b border-line-soft text-small text-ink-2"><tr><th className={eve ? 'py-1.5' : 'py-2'}>로트</th>{!eve && <th>합격</th>}<th className="text-right">수량</th></tr></thead>
                      <tbody className="divide-y divide-slate-100">{cur.lines.map((x: R) => (
                        <tr key={x.lot_no}><td className={eve ? 'py-1.5' : 'py-2.5'}><button onClick={() => go('lots', x.lot_no)} className="font-mono text-brand underline">{x.lot_no}</button></td>{!eve && <td className="font-mono">{x.lot_passed_at ? `${md(x.lot_passed_at)} ${hm(x.lot_passed_at)}` : '—'}</td>}<td className="text-right font-mono font-bold">{x.qty}</td></tr>))}</tbody>
                    </table>
                    <div className="mt-2 border-t border-line-soft pt-2 text-right text-card">합 <b className="font-mono text-band">{sum(cur)}</b> 개</div>
                    <div className="mt-4 text-card font-bold">버전</div>
                    <div className="mt-1 grid grid-cols-[50px_160px_1fr] text-card"><b className="font-mono">v{cur.current_version || 0}</b><span>{cur.confirmed_by ? userName(cur.confirmed_by) : '—'}</span><span>확정 {md(cur.shipped_at)} {hm(cur.shipped_at)}</span></div>
                  </section>)}
              </div>);
          })() : (<>
            {/* 단계 */}
            <section className={`${box} grid grid-cols-4 gap-2 !p-3`}>{([['로트 고르기', `합격 로트 ${avail.length}`], ['수량', `로트 ${chosen.length} · ${total}개`], ['출하 전 확인', `${okN} / 3`], ['확정', '확인 상자']] as const).map(([t, sub], i) => {
              const n = i + 1, done = n < step, on = n === step;
              return <div key={t} className={`flex items-center gap-3 rounded-tile border px-3 py-2 ${on ? 'border-brand-line bg-brand-tint' : 'border-line-soft'}`}>
                <span className={`flex h-10 w-10 items-center justify-center rounded-full font-bold ${done ? 'bg-ink text-white' : on ? 'bg-brand text-white' : 'border-2 border-line text-ink-2'}`}>{done ? '✓' : n}</span>
                <div><div className="text-band font-bold">{t}</div><div className="text-small text-ink-2">{sub}</div></div></div>;
            })}</section>

            <div className="grid grid-cols-[1.6fr_1fr] items-start gap-4">
              {/* 합격 로트 */}
              <section className={box}>
                <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-card font-bold">합격 로트</h3>
                  {role === 'SUP' && <button onClick={() => { setShip(Object.fromEntries(avail.filter((l) => (dueOf(l) ?? '0000').slice(0, 10) <= today).map((l) => [l.lot_no, left(l)]))); setReview(false); }} className="h-11 rounded-tile border border-line bg-white px-4 text-body text-brand disabled:text-ink-3">오늘 납기 전부 채우기</button>}</div>
                {avail.length === 0 ? <p className="mt-3 text-body text-ink-2">출하할 수 있는 합격 로트가 없습니다</p> : (
                  <div className="mt-3 grid grid-cols-2 gap-3">{avail.slice(0, 12).map((l) => { const q = ship[l.lot_no] ?? 0, mx = left(l), due = dueOf(l); return (
                    <div key={l.lot_no} className={`flex gap-3 rounded-tile border p-3 ${eve ? 'flex-col items-stretch' : 'items-center'} ${q > 0 ? 'border-brand-line bg-tile' : 'border-line-soft bg-white'}`}>{/* 이브 열림: 로트 번호 → 설명 → −0+ 위에서 아래로 */}
                      <div className="min-w-0 flex-1"><button onClick={() => go('lots', l.lot_no)} className="whitespace-nowrap font-mono text-card font-bold text-brand underline">{l.lot_no}</button>
                        <div className="text-small text-ink-2">합격 {md(l.passed_at)} {hm(l.passed_at)} · 납기 {due ? md(due) : '—'} · 남은 {mx}</div>{q === mx && q > 0 && <div className="text-small text-ink-2">전부</div>}</div>
                      {role === 'SUP' && (
                      <div className={`flex h-12 items-center overflow-hidden rounded-tile border border-line bg-white ${eve ? 'w-full' : ''}`}>
                        <button disabled={role !== 'SUP'} onClick={() => setQ(l.lot_no, q - 1, mx)} className="h-full w-11 shrink-0 text-title">−</button>
                        <input disabled={role !== 'SUP'} value={q} onChange={(e) => setQ(l.lot_no, Number(e.target.value) || 0, mx)} className={`h-full min-w-0 border-x border-line-soft text-center font-mono text-band font-bold ${eve ? 'flex-1' : 'w-14'}`} />
                        <button disabled={role !== 'SUP'} onClick={() => setQ(l.lot_no, q + 1, mx)} className="h-full w-11 shrink-0 text-title">+</button></div>
                      )}
                    </div>); })}</div>
                )}
                {held.slice(0, 3).map((l) => <div key={l.lot_no} className="mt-3 rounded-tile border border-dashed border-line bg-tile px-4 py-3 text-card"><LockIcon /> <button onClick={() => go('lots', l.lot_no)} className="font-mono font-bold text-brand underline">{l.lot_no}</button> <b>보류</b> {l.input_qty} · 출하 불가</div>)}
              </section>

              {/* 출하 요약 */}
              <section className={box}>
                <div className="flex items-center justify-between gap-2"><h3 className="flex items-center gap-2 whitespace-nowrap text-card font-bold"><span className="h-2.5 w-2.5 shrink-0 rounded-full bg-brand" />출하 <span className="font-mono">{nextNo}</span></h3><span className="shrink-0 whitespace-nowrap rounded-tile border border-line px-3 py-1 text-body">{chosen.length ? '작성 중' : '비어 있음'}</span></div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-body">
                  <div><div className="text-small text-ink-2">출하처</div>CUST-01</div>
                  <div><div className="text-small text-ink-2">출하 일시</div>확정 때 기록</div>
                  <div className="col-span-2"><div className="text-small text-ink-2">근거 작업지시 · 납기</div>{orders.length ? `${orders[0]}${orders.length > 1 ? `~${String(orders[orders.length - 1]).slice(-3)}` : ''}` : '—'}</div>
                </div>
                <div className="mt-3 border-t border-line-soft pt-3 text-card">출하 수량 합 <b className="font-mono text-tablet">{total}</b> 개 · 로트 {chosen.length}</div>
                <div className="mt-2 grid grid-cols-[60px_1fr_50px] items-center gap-3 text-body">
                  <span>지금</span><div className="h-5 rounded bg-info" /><b className="text-right font-mono">{fgNow}</b>
                  <span>출하 뒤</span><div className="h-5 overflow-hidden rounded border border-dashed border-line"><div className="h-full bg-info" style={{ width: `${fgNow ? (Math.max(0, fgNow - total) / fgNow) * 100 : 0}%` }} /></div><b className="text-right font-mono">{Math.max(0, fgNow - total)}</b>
                </div>
                <div className={`mt-4 flex flex-col gap-2 text-card ${review ? 'rounded-tile bg-tile p-3' : ''}`}>
                  <label className="flex items-center gap-2"><input type="checkbox" readOnly checked={chosen.length > 0} className="h-4 w-4" />모든 로트 합격 (해제 포함)</label>
                  <label className="flex items-center gap-2"><input type="checkbox" readOnly checked={chosen.length > 0 && enough} className="h-4 w-4" />로트 남은 수량 ≥ 출하 수량</label>
                  <label className="flex items-center gap-2"><input type="checkbox" readOnly checked={chosen.length > 0 && fifo} className="h-4 w-4" />선입선출</label>
                  {chosen.length > 0 && !fifo && <input value={fifoWhy} onChange={(e) => setFifoWhy(e.target.value)} placeholder="먼저 합격한 로트부터가 아닌 사유 (필수)" className="h-10 rounded-tile border border-line px-2 text-body" />}
                  <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="비고 (부분 출하·늦은 출하 사유)" className="h-10 rounded-tile border border-line px-2 text-body" />
                </div>
                <div className="mt-4 flex justify-end">
                  {!review
                    ? <button disabled={chosen.length === 0} onClick={() => setReview(true)} className="h-14 rounded-tile bg-brand px-6 text-band font-bold text-white disabled:bg-line">다음 · 출하 전 확인</button>
                    : <button disabled={!can} onClick={() => setConfirm(true)} className="h-14 rounded-tile bg-brand px-6 text-band font-bold text-white disabled:bg-line">출하 확정</button>}
                </div>
                {role !== 'SUP' && <p className="mt-2 text-right text-small text-ink-2">출하 등록은 반장</p>}
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
