'use client';
// SCR-21 재고 — 13품목(공구 5·소모품 6·원자재 1·완제품 1), 관리 역할, 거래 기록, 입고·실사 조정(API-INV-02), 출하 등록(API-INV-04). 발주 버튼 없음.
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MASTERS } from './data';
import { api, hm, md, useFetch } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;
const CAT: Record<string, string> = { TOOL: '공구', CONSUMABLE: '소모품', MAINT: '소모품', SUPPLY: '소모품', RAW: '원자재', FG: '완제품' };
const TXN: Record<string, string> = { IN: '입고', USE: '사용', ADJUST: '조정', FG_IN: '합격 입고', SHIP: '출하', RECEIVE: '입고' };

export function InventoryScreen() {
  const { inv, reloadInv, role, user, back, go, toast } = useApp();
  const [low, setLow] = useState(false);
  const [cat, setCat] = useState('');
  const [form, setForm] = useState<{ item: string; type: 'IN' | 'ADJUST'; qty: string; memo: string } | null>(null);
  const [rules, setRules] = useState(false);
  const lots = useFetch<{ lots: R[] }>(role === 'SUP' ? 'lots' : null, 0, []);
  const ships = useFetch<{ shipments: R[] }>('shipments', 20000);
  const [ship, setShip] = useState<Record<string, number>>({});
  const [fifoWhy, setFifoWhy] = useState(''); const [memo, setMemo] = useState('');
  const [confirm, setConfirm] = useState(false);
  if (!inv) return <div className={PAGE}><div className={CARD}>재고를 불러오는 중… <button onClick={back} className={BTN}>닫기</button></div></div>;
  const items = inv.items.filter((i) => (!low || i.low) && (!cat || (CAT[i.category] ?? i.category) === cat));
  const txns: R[] = [...inv.live_txns.map((t) => ({ ...t, live: true })), ...[...inv.past_txns].reverse()].slice(0, 60);
  const name = (no: string) => inv.items.find((i) => i.item_no === no)?.item_name ?? no;
  const avail = (lots.data?.lots ?? []).filter((l) => (l.status === 'PASSED' || l.status === 'RELEASED') && l.fg_qty - (l.shipped?.qty ?? 0) > 0).sort((a, b) => (a.judged_at < b.judged_at ? -1 : 1));
  const chosen = Object.entries(ship).filter(([, q]) => q > 0);
  const fifo = chosen.every(([lot]) => avail.findIndex((l) => l.lot_no === lot) <= Math.max(...chosen.map(([x]) => avail.findIndex((l) => l.lot_no === x))) && avail.slice(0, avail.findIndex((l) => l.lot_no === lot)).every((l) => ship[l.lot_no] === l.fg_qty - (l.shipped?.qty ?? 0)));
  const enough = chosen.every(([lot, q]) => { const l = avail.find((x) => x.lot_no === lot); return !!l && q <= l.fg_qty - (l.shipped?.qty ?? 0); });
  const can = chosen.length > 0 && enough && (fifo || fifoWhy.trim());

  const save = async () => {
    if (!form) return;
    try { await api('inventory/txns', { role, user_id: user.id, item_no: form.item, txn_type: form.type, qty: Number(form.qty), memo: form.memo }); toast(`${name(form.item)} ${form.type === 'IN' ? '입고' : '조정'} ${form.qty}`); setForm(null); reloadInv(); }
    catch (e) { toast((e as Error).message); }
  };
  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">재고</h2>
          <div className="flex flex-wrap gap-1">
            <button onClick={() => setLow(true)} className={`${BTN} ${low ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>부족만</button><button onClick={() => setLow(false)} className={`${BTN} ${!low ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>전체</button>
            {['공구', '소모품', '원자재', '완제품'].map((c) => <button key={c} onClick={() => setCat(cat === c ? '' : c)} className={`${BTN} ${cat === c ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>{c}</button>)}
            <button onClick={back} className={BTN}>닫기</button>
          </div>
        </div>
        <table className="mt-3 w-full text-left text-[14px]">
          <thead className="text-slate-500"><tr>{['품목 번호 [가상]', '품목', '종류', '단위', '지금', '안전 재고', '관리 역할', '상태', ''].map((h) => <th key={h} className="pr-2 font-semibold">{h}</th>)}</tr></thead>
          <tbody>{items.map((i) => (
            <tr key={i.item_no} className="border-t border-slate-100">
              <td className="pr-2">{i.item_no}</td><td className="pr-2">{i.item_name}</td><td className="pr-2">{CAT[i.category] ?? i.category}</td><td className="pr-2">{i.unit}</td><td className="pr-2 font-semibold">{i.stock_qty}</td>
              <td className="pr-2">{i.category === 'FG' ? '—' : i.safety_stock}</td><td className="pr-2">{i.owner_role}</td>
              <td className={`pr-2 ${i.low ? 'font-bold text-[#9a6200]' : ''}`}>{i.category === 'FG' ? `보류 수량 ${inv.held_lot_qty} (재고에 안 넣음)` : i.low ? '▲ 부족' : ''}</td>
              <td>{role === i.owner_role && <button onClick={() => setForm({ item: i.item_no, type: 'IN', qty: '', memo: '' })} className="h-9 rounded border border-slate-300 px-2 text-[12px]">입고·조정</button>}</td>
            </tr>))}</tbody>
        </table>
        {form && (
          <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-slate-300 p-2 text-[14px]">{name(form.item)}
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as 'IN' | 'ADJUST' })} className="h-11 rounded border border-slate-300"><option value="IN">입고 등록</option><option value="ADJUST">실사·조정 (±)</option></select>
            수량 <input value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })} className="h-11 w-24 rounded border border-slate-300 px-1" />
            <input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} placeholder={form.type === 'ADJUST' ? '조정 사유 (필수)' : '원자재면 원자재 로트·성적서 번호'} className="h-11 w-[260px] rounded border border-slate-300 px-1" />
            <button onClick={save} className={DARK}>저장</button><button onClick={() => setForm(null)} className={BTN}>취소</button>
          </div>
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          {role === 'OPR' && <button onClick={() => go('tools')} className={BTN}>공구 사용 기록 (공구 교체)</button>}
          {role === 'MGR' && <button onClick={() => go('settings', '안전 재고')} className={BTN}>안전 재고 설정</button>}
          <button onClick={() => setRules((r) => !r)} className={BTN}>{rules ? '▾' : '▸'} 차감 규칙 보기</button>
        </div>
        {rules && <ul className="mt-1 list-disc pl-5 text-[13px]">{(MASTERS.tool_types as R[]).map((t) => <li key={t.item_no}>{name(t.item_no)} — 공구 교체 1회 = {t.deduct_qty_per_change}개 (수명 한도 {t.life_limit} {t.usage_unit === 'HOLES' ? '구멍' : '분'} {t.limit_basis.slice(0, 4)})</li>)}<li>원자재 6061-T6 봉재 — 로트 투입 때 투입 수량만큼 자동</li><li>완제품 — 로트 합격·해제 때 합격 수량 입고, 출하 확정 때 출고</li></ul>}

        <section className="mt-3 border-t border-slate-200 pt-3">
          <h3 className="mb-1 text-[14px] font-bold text-slate-500">거래 기록 (오늘 + 9월 최근)</h3>
          <ul className="max-h-[220px] overflow-y-auto text-[13px]">{txns.map((t, i) => (
            <li key={i} className={t.live ? 'font-semibold' : 'text-slate-600'}>{md(t.txn_at)} {hm(t.txn_at)} · {TXN[t.txn_type] ?? t.txn_type} · {name(t.item_no)} {Number(t.qty_change) > 0 ? '+' : ''}{t.qty_change} · {t.source_kind}{t.lot_no ? ` ${t.lot_no}` : ''}{t.fg_lot_no ? ` ${t.fg_lot_no}` : ''}{t.shipment_no ? ` ${t.shipment_no}` : ''}{t.memo ? ` · ${t.memo}` : ''}{t.txn_by ? ` · ${userName(t.txn_by)}` : ''}</li>))}</ul>
        </section>

        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">출하 기록 · 출하 등록 (SUP)</h3>
          <ul className="max-h-[120px] overflow-y-auto text-[13px]">{[...(ships.data?.shipments ?? [])].reverse().slice(0, 12).map((s) => <li key={s.shipment_no}>{s.shipment_no} · {md(s.shipped_at)} {hm(s.shipped_at)} · {s.customer_code} 가상 고객사 · {s.lines.reduce((n: number, x: R) => n + Number(x.qty), 0)}개 ({s.lines.length}로트){s.memo ? ` · ${s.memo}` : ''}</li>)}</ul>
          {role === 'SUP' && (<div className="mt-2 rounded-md border border-slate-300 p-2">
            출하 번호 (자동) · 출하처 CUST-01 가상 고객사 · 로트 줄 (합격·해제 로트만, 먼저 합격한 순서)
            {avail.length === 0 ? <p className="text-slate-500">출하할 수 있는 합격 로트가 없습니다</p> : (
              <table className="mt-1 w-full text-left text-[13px]"><tbody>{avail.slice(0, 10).map((l) => (
                <tr key={l.lot_no}><td>{l.lot_no}</td><td>합격 {md(l.judged_at)} {hm(l.judged_at)}</td><td>남은 {l.fg_qty - (l.shipped?.qty ?? 0)}개</td>
                  <td>출하 <input type="number" min={0} value={ship[l.lot_no] ?? ''} onChange={(e) => setShip({ ...ship, [l.lot_no]: Number(e.target.value) })} className="h-10 w-20 rounded border border-slate-300 px-1" /></td></tr>))}</tbody></table>
            )}
            <div className="mt-1">출하 수량 합 <b>{chosen.reduce((n, [, q]) => n + q, 0)}</b> · ☑ 모든 로트 합격 · {enough ? '☑' : '☐'} 남은 수량 ≥ 출하 · {fifo ? '☑ 먼저 합격한 로트부터' : <>☐ 먼저 합격한 로트부터 아님 → 사유 <input value={fifoWhy} onChange={(e) => setFifoWhy(e.target.value)} className="h-10 rounded border border-slate-300 px-1" /></>}</div>
            <div className="mt-1 flex items-center gap-2">비고 <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="부분 출하·늦은 출하 사유" className="h-10 flex-1 rounded border border-slate-300 px-1" /><button disabled={!can} onClick={() => setConfirm(true)} className={DARK}>확정</button></div>
          </div>)}
        </section>
      </div>
      {confirm && <ConfirmBox title="출하를 확정할까요?" okLabel="출하 확정" body={`${chosen.map(([l, q]) => `${l} ${q}개`).join(', ')} — 확정하면 완제품 재고에서 빠지고, 고치려면 사유가 필요합니다.`}
        onOk={async () => { setConfirm(false); try { const r = await api<R>('shipments', { role, user_id: user.id, customer_code: 'CUST-01', lines: chosen.map(([lot_no, qty]) => ({ lot_no, qty })), fifo_skip_reason: fifo ? null : fifoWhy, memo }); toast(`출하 ${r.shipment_no} 확정`); setShip({}); ships.reload(); lots.reload(); reloadInv(); } catch (e) { toast((e as Error).message); } }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}
