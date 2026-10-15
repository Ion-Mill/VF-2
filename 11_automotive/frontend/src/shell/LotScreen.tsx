'use client';
// SCR-19 로트 추적 — 원자재 로트 → 공정 실적 → 알람 → 검사 → 완제품 입고 → 출하. 보류·해제 = API-LOT-02 (시뮬레이터: 보류하면 그 로트와 다음 2개 전수 검사).
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { api, hm, md, useFetch, usePersist } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

const STATUS: Record<string, string> = { IN_PROCESS: '생산 중', WAIT_INSPECTION: '검사 대기', WAIT_JUDGEMENT: '판정 대기', HOLD_REVIEW: '▲ 보류 검토', ON_HOLD: '🔒 보류', PASSED: '합격 (출하 가능)', RELEASED: '해제 (출하 가능)', SCRAPPED: '폐기' };
const PROCS = ['OP-10', 'OP-20', 'OP-30', 'OP-40', 'OP-50'];

export function LotScreen() {
  const { key, back, role, user, go, toast, twin } = useApp();
  const [lot, setLot] = useState<string>(key ?? twin?.suspect_lot ?? twin?.equipment['VF2-01'].lot_no ?? '');
  const f = useFetch<{ lots: Record<string, any>[]; suspect_lot: string | null; materials: Record<string, Record<string, string>>; reports: Record<string, any>[]; alarms: Record<string, any>[] }>(`lots?lot=${encodeURIComponent(lot)}`, 10000, [lot]);
  const [scrapOk, setScrapOk] = usePersist<Record<string, string>>('scrapOk', {}, twin?.run_id ?? null);
  const [scrapProp, setScrapProp] = usePersist<Record<string, string>>('scrapProp', {}, twin?.run_id ?? null);
  const [reason, setReason] = useState('');
  const [confirm, setConfirm] = useState<'hold' | 'release' | null>(null);
  const L = f.data?.lots.find((x) => x.lot_no === lot);
  const all = f.data?.lots ?? [];
  const canHold = role === 'SUP' || role === 'MGR';
  const shipped = L?.shipped?.qty ?? 0, ships = L?.shipped?.shipments ?? [];
  const mat = L ? f.data?.materials[L.material_lot_no] : null;
  const rel = L ? [['같은 원자재', all.filter((x) => x.material_lot_no === L.material_lot_no && x.lot_no !== lot)], ['같은 교대', all.filter((x) => x.input_shift_id === L.input_shift_id && x.lot_no !== lot)], ['같은 작업지시', all.filter((x) => x.order_no === L.order_no && x.lot_no !== lot)]] as [string, Record<string, any>[]][] : [];
  const blocked = L && ['ON_HOLD', 'HOLD_REVIEW', 'WAIT_JUDGEMENT', 'SCRAPPED', 'IN_PROCESS', 'WAIT_INSPECTION'].includes(L.status);
  const doIt = async (kind: 'hold' | 'release') => {
    try {
      await api(`lots/${lot}/${kind}`, { role, user_id: user.id, reason: kind === 'hold' ? reason : undefined, approver: scrapOk[lot] ?? 'U12' });
      toast(kind === 'hold' ? `${lot} 보류 — 이 로트와 다음 2개 로트 전수 검사` : `${lot} 해제`); setReason(''); f.reload();
    } catch (e) { toast((e as Error).message); }
  };

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">로트 추적</h2>
          <div className="flex items-center gap-2">
            <input list="lots" value={lot} onChange={(e) => setLot(e.target.value)} className="h-11 w-[220px] rounded-md border border-slate-300 px-2 text-[14px]" placeholder="LOT-2609-127-1" />
            <datalist id="lots">{[...all].reverse().slice(0, 200).map((x) => <option key={x.lot_no} value={x.lot_no}>{STATUS[x.status] ?? x.status}</option>)}</datalist>
            <button onClick={back} className={BTN}>닫기</button>
          </div>
        </div>
        {!L ? <p className="mt-3 text-[14px] text-slate-500">로트를 고르세요{f.data ? '' : ' (불러오는 중)'}</p> : (<>
          <div className="mt-2 text-[15px]">작업지시 {L.order_no} · 투입 교대 {L.input_shift_id} · 투입 {L.input_qty}개 · 검사 방식 {L.enhanced ? `강화 (전수, ${L.enhance_reason ?? ''})` : L.plan_mode === 'FULL' ? '전수' : '발췌'}</div>
          <section className="mt-3 overflow-x-auto border-t border-slate-200 pt-3">
            <h3 className="mb-1 text-[14px] font-bold text-slate-500">한 줄 이력</h3>
            <div className="flex min-w-max items-start gap-2 text-[13px]">
              <div className="rounded border border-slate-300 p-2"><b>{L.material_lot_no}</b><br />원자재 로트{mat ? <><br />입고 {mat.received_date} · 성적서 {mat.supplier_cert_no}</> : null}</div>
              {PROCS.map((pc) => { const rs = (f.data?.reports ?? []).filter((x) => x.process_code === pc); const al = (f.data?.alarms ?? []).filter((a) => rs.some((x) => x.equipment_id === a.equipment_id));
                return (<div key={pc} className="flex items-start gap-2"><span className="pt-3">▶</span><div className="rounded border border-slate-300 p-2"><b>{pc}</b> {rs.map((x) => x.equipment_id).filter((v, i, a) => a.indexOf(v) === i).join('·') || '—'}<br />{rs.length ? `${hm(rs[0].start_at)}~${hm(rs[rs.length - 1].end_at)} · ${userName(rs[0].worker_user_id)}` : (L.process_done?.[pc] ?? 0) ? `${L.process_done[pc]}개 지남` : '아직'}
                  <br />{rs.length ? `양품 ${rs.reduce((s, x) => s + x.gq + x.rq, 0)} · 폐기 ${rs.reduce((s, x) => s + x.sq, 0)}` : ''}{al.map((a) => <div key={a.alarm_event_id} className={a.severity === 'STOP' ? 'font-bold text-[#c62a2f]' : 'text-[#9a6200]'}>{a.severity === 'STOP' ? '⚠' : '▲'}{a.alarm_code} {hm(a.occurred_at)}</div>)}</div></div>);
              })}
              <span className="pt-3">▶</span><div className="rounded border border-slate-300 p-2"><b>{STATUS[L.status] ?? L.status}</b>{L.judged_at ? <><br />판정 {md(L.judged_at)} {hm(L.judged_at)}</> : null}<br />{L.gauge_pass_qty != null ? `게이지 합격 ${L.gauge_pass_qty} · 불합격 ${L.gauge_fail_qty}` : ''}</div>
              <span className="pt-3">▶</span><div className="rounded border border-slate-300 p-2"><b>완제품 입고</b><br />{L.fg_qty}개</div>
              <span className="pt-3">▶</span><div className="rounded border border-slate-300 p-2"><b>출하</b> {blocked ? '(금지)' : ''}<br />{ships.length ? ships.map((s: Record<string, string>) => <div key={s.shipment_no}>{s.shipment_no} {s.customer_code} {md(s.shipped_at)}</div>) : '아직'}</div>
            </div>
          </section>
          {(f.data?.suspect_lot === lot || (f.data?.alarms ?? []).some((a) => a.severity === 'STOP')) && (
            <section className="mt-3 rounded-md border-2 border-dashed border-slate-400 p-2 text-[14px]">┄ 의심 로트 제안 (비서) · 정지 등급 알람 {(f.data?.alarms ?? []).filter((a) => a.severity === 'STOP').map((a) => a.alarm_code).join('·')}이 뜬 동안 가공된 로트입니다. 제안만으로 상태가 바뀌지 않습니다. 출처: DOC-06 §4.2</section>
          )}
          <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
            <h3 className="mb-1 font-bold text-slate-500">상태</h3>
            생산 중 → 검사 대기 → (판정 대기) → 합격(출하 가능) / 보류 검토 / 보류 → 해제 / 폐기 → 출하됨<br />
            지금: <b>{STATUS[L.status] ?? L.status}</b>{blocked ? ' · 출하 금지' : ''}{L.hold ? ` · 보류 사유: ${L.hold.reason} (${userName(L.hold.held_by)} ${L.hold.held_at ? hm(L.hold.held_at) : ''})` : ''}{L.hold?.released_at ? ` · 해제 ${userName(L.hold.released_by)} ${hm(L.hold.released_at)}` : ''}
          </section>
          <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]"><b className="text-slate-500">검사 결과</b> 측정 불합격 {L.insp_fail} · 폐기 {L.scrap_qty} <button onClick={() => go('quality', lot)} className={BTN}>검사 기록</button></section>
          <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]"><b className="text-slate-500">관련 로트</b> {rel.map(([k, v]) => <span key={k} className="mr-3">{k}: {v.length ? v.slice(0, 4).map((x) => <button key={x.lot_no} onClick={() => setLot(x.lot_no)} className="mr-1 underline">{x.lot_no}</button>) : '없음'}</span>)}</section>
          <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]"><b className="text-slate-500">수량</b> 투입 {L.input_qty} · 완료 {L.fg_qty} (OP-50 양품 + 재작업 양품) · 출하 {shipped} · 남은 {Math.max(0, L.fg_qty - shipped)}</section>
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-300 pt-3">
            {canHold && !L.on_hold && (<><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="보류 사유 (필수)" className="h-11 w-[260px] rounded-md border border-slate-300 px-2" />
              <button disabled={!reason.trim() || shipped > 0 || !!L.judged_at} onClick={() => setConfirm('hold')} className={DARK}>보류{shipped > 0 ? ` — 이미 출하됨 (${ships[0]?.shipment_no})` : L.judged_at ? ' — 판정 끝난 로트' : ''}</button></>)}
            {canHold && L.on_hold && <button disabled={!L.judged_at || (L.scrap_qty > 0 && !scrapOk[lot])} onClick={() => setConfirm('release')} className={DARK}>해제{!L.judged_at ? ' — 전수 검사 중' : L.scrap_qty > 0 && !scrapOk[lot] ? ' — 폐기 승인 필요' : ''}</button>}
            {role === 'SUP' && L.scrap_qty > 0 && !scrapProp[lot] && <button onClick={() => setScrapProp((p) => ({ ...p, [lot]: user.id }))} className={BTN}>폐기 제안 ({L.scrap_qty}개)</button>}
            {role === 'MGR' && L.scrap_qty > 0 && !scrapOk[lot] && <button disabled={!scrapProp[lot]} onClick={() => setScrapOk((p) => ({ ...p, [lot]: user.id }))} className={BTN}>폐기 승인{!scrapProp[lot] ? ' — 반장 제안 전' : ''}</button>}
            {scrapOk[lot] && <span className="text-[13px]">폐기 승인 {userName(scrapOk[lot])}</span>}
            {!canHold && <span className="text-[14px] text-slate-500">보기 전용 (보류·해제는 반장·관리자)</span>}
          </div>
        </>)}
      </div>
      {confirm && <ConfirmBox title={confirm === 'hold' ? `${lot}을(를) 보류할까요?` : `${lot}을(를) 해제할까요?`} okLabel={confirm === 'hold' ? '보류' : '해제'}
        body={confirm === 'hold' ? '보류하면 이 로트와 다음 1~2개 로트가 검사 강화(전수)로 바뀝니다. OP-50이 병목이 될 수 있습니다.' : '해제하면 출하할 수 있습니다.'}
        onOk={() => { const k = confirm; setConfirm(null); void doIt(k); }} onCancel={() => setConfirm(null)} />}
    </div>
  );
}
