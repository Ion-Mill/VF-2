'use client';
// SCR-12 작업기록서 — 작업지시서를 보고 실제로 한 일을 적는다. 확정 → 작업지시서 완료, 설비 복귀(시뮬레이터 confirm_work_record),
// 사용 부품 재고 차감(서버 거래 기록), MTTR 다시 계산(서버가 시뮬레이터 상태 기록으로).
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { api, hm, md, simIso } from './live';
import { machineLabel } from './model';
import { ConfirmBox, LOCK, LockChecks } from './Safety';
import { diff, rev, type WorkRecord } from './workflow';

const STATUS: [WorkRecord['state'], string][] = [['draft', '초안'], ['editing', '수정 중'], ['confirmed', '확정 (MNT)'], ['checked', '확인 (SUP)']];

// [비서로 정리] 대신 규칙 정리: 문장을 원인·조치로, 재고 품목 이름이 나오면 사용 부품으로 (LLM 연결 전)
const organize = (memo: string, items: { item_no: string; item_name: string }[]) => {
  const ss = memo.split(/[.\n。]|(?<=다)\s/).map((s) => s.trim()).filter(Boolean);
  const isAct = (s: string) => /(교체|조임|조였|청소|보충|채움|채웠|바꿈|바꿨|정렬|재설정|복구|닦|교정|재시작|조정)/.test(s);
  const cause = ss.filter((s) => !isAct(s) || /(원인|때문|불량|마모|끼임|파손|느슨)/.test(s)).join('. ');
  const action = ss.filter(isAct).join('. ');
  const parts = items.filter((i) => memo.includes(i.item_name.split(' ')[0])).map((i) => ({ item: i.item_no, qty: 1 }));
  return { cause, action, parts };
};

export default function WorkRecordScreen({ woNo }: { woNo: string }) {
  const { wos, wrs, putWr, putWo, user, role, back, inv, alerts, markAlert, restoreMachine, history, go, twin, toast, reloadInv } = useApp();
  const wo = wos.find((w) => w.no === woNo), wr = wrs.find((r) => r.woNo === woNo);
  const alert = alerts.find((a) => a.id === wo?.alertId);
  const [v, setV] = useState<WorkRecord | null>(wr ? { ...wr, start: wr.start || (alert ? hm(alert.time) : ''), end: wr.end } : null);
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState('');
  if (!wo || !wr || !v) return <div className={PAGE}><div className={CARD}>작업기록서가 없습니다 <button onClick={back} className={BTN}>닫기</button></div></div>;
  const done = wr.state === 'confirmed' || wr.state === 'checked';
  const canEdit = role === 'MNT' && !done;
  const lockN = v.lock.filter(Boolean).length;
  const set = <K extends keyof WorkRecord>(k: K, x: WorkRecord[K]) => setV((p) => (p ? { ...p, [k]: x } : p));
  const mins = v.start && v.end ? Math.round((Date.parse(`1970-01-01T${v.end}:00`) - Date.parse(`1970-01-01T${v.start}:00`)) / 60000) : null;
  const idx = STATUS.findIndex(([k]) => k === wr.state);
  const eq = MACHINES[wo.machine].eq!;
  const same = (history?.work_records ?? []).filter((r) => r.equipment_id === eq && history?.alarms.find((x) => x.alarm_event_id === r.alarm_event_id)?.alarm_code === wo.code);
  const mttr = twin?.kpi.mttr_mtbf[eq];
  const names = { memo: '작업자 메모', cause: '원인', action: '조치', parts: '사용 부품', start: '시작', end: '끝' };
  const sec = (head: string, body: React.ReactNode) => (<section className="border-t border-slate-200 py-3"><h3 className="mb-1 text-[14px] font-bold text-slate-500">{head}</h3>{body}</section>);
  const input = 'h-11 rounded-md border border-slate-300 px-3 text-[15px] disabled:bg-slate-50';

  const doConfirm = async () => {
    const final: WorkRecord = { ...v, state: 'confirmed', confirmedAt: simIso(), end: v.end || hm(simIso()), revisions: rev(wr.revisions, '확정', user.name, role, diff(wr as unknown as Record<string, unknown>, v as unknown as Record<string, unknown>, names)) };
    putWr(final); putWo({ ...wo, state: 'done' });
    // 사용 부품 → 재고 차감 (작업기록서 확정 순간, FR-MNT-05-09)
    const used: string[] = [];
    for (const p of v.parts) {
      try { await api('inventory/txns', { role, user_id: user.id, item_no: p.item, txn_type: 'USE', qty: -Math.abs(p.qty), memo: `작업기록서 ${wr.no}` }); used.push(`${inv?.items.find((i) => i.item_no === p.item)?.item_name ?? p.item} −${p.qty}`); }
      catch (e) { toast((e as Error).message); }
    }
    // 처리 = 작업기록서 확정 → 그 알람과 연쇄 알람 모두 처리됨
    let first = alert; while (first?.prevId) { const p = alerts.find((x) => x.eventId === first!.prevId); if (!p) break; first = p; }
    const ids = alerts.filter((a) => a.machine === wo.machine && !a.handled && a.kind !== 'guide' && a.ts >= (first?.ts ?? 0)).map((a) => a.id);
    markAlert(ids, `${user.name} (작업기록서 ${wr.no})`);
    await restoreMachine(wo.machine);
    reloadInv();
    setNote(`확정 — MTTR 다시 계산 · 재고 ${used.length ? used.join(', ') : '차감 없음'} · ${MACHINES[wo.machine].name} 복귀`);
  };

  return (
    <div className={PAGE}>
      <div className={`${CARD} max-w-[920px]`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">작업기록서 {wr.no} <span className="text-[14px] font-normal text-slate-500">← 작업지시서 {wo.no}</span></h2>
          <div className="flex gap-2"><button onClick={() => go('revs', `WR:${wr.no}`)} className={BTN}>수정 이력</button><button onClick={() => alert && go('replay', alert.time)} className={BTN}>다시 보기 (고장 직전)</button><button onClick={back} className={BTN}>닫기</button></div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1 text-[14px]">{STATUS.map(([k, label], i) => <span key={k} className={`rounded-full px-3 py-1 ${i === idx ? 'bg-[#1c2530] font-bold text-white' : i < idx ? 'bg-slate-200' : 'border border-slate-300 text-slate-500'}`}>{label}</span>)}</div>

        {sec('자동 칸', <div className="text-[15px]">작업지시서 {wo.no} · 설비 {machineLabel(wo.machine)} · 알람 {wo.code} · 로트 {wo.lot ?? '—'} · 발생 {md(wo.created)} {hm(wo.created)}</div>)}
        {sec('작업자 메모', (
          <div className="flex flex-col gap-2">
            <textarea disabled={!canEdit} value={v.memo} onChange={(e) => set('memo', e.target.value)} rows={3} placeholder="한 일을 대충 적어도 됩니다 (예: 서보 케이블 커넥터 느슨함 원인. 커넥터 다시 조임. 축 윤활유 보충)" className="w-full rounded-md border border-slate-300 px-3 py-2 text-[15px] disabled:bg-slate-50" />
            <div><button disabled={!canEdit || !v.memo.trim()} onClick={() => { const o = organize(v.memo, inv?.items ?? []); setV((p) => p ? { ...p, cause: o.cause || p.cause, action: o.action || p.action, parts: o.parts.length ? o.parts : p.parts, aiFields: ['원인', '조치', '사용 부품'] } : p); }} className={BTN}>비서로 정리 (프로그램 정리 — 로컬 LLM 연결 전)</button></div>
          </div>
        ))}
        {sec('원인 · 조치 · 사용 부품', (
          <div className="flex flex-col gap-2">
            <label className="text-[14px] font-semibold">원인 {v.aiFields?.includes('원인') && <span className="rounded bg-slate-100 px-1 text-[11px]">[프로그램 정리]</span>}<input disabled={!canEdit} value={v.cause} onChange={(e) => set('cause', e.target.value)} className={`mt-1 w-full ${input} font-normal`} /></label>
            <label className="text-[14px] font-semibold">조치 {v.aiFields?.includes('조치') && <span className="rounded bg-slate-100 px-1 text-[11px]">[프로그램 정리]</span>}<input disabled={!canEdit} value={v.action} onChange={(e) => set('action', e.target.value)} className={`mt-1 w-full ${input} font-normal`} /></label>
            <PartsPicker value={v.parts} onChange={(p) => set('parts', p)} disabled={!canEdit} />
          </div>
        ))}
        {sec('수행 단계 체크 (작업지시서의 작업 순서)', <div className="flex flex-col">{wo.steps.map((s, i) => (
          <label key={s} className="flex min-h-[44px] items-center gap-2 text-[14px]"><input type="checkbox" className="h-5 w-5" disabled={!canEdit} checked={!!v.stepChecks[i]} onChange={() => set('stepChecks', v.stepChecks.map((c, k) => (k === i ? !c : c)))} />{i + 1}. {s}</label>))}</div>)}
        {sec('잠금·표지 체크', <LockChecks value={v.lock} onChange={(l) => set('lock', l)} disabled={!canEdit} />)}
        {sec('시각 (시연 시계)', (
          <div className="flex flex-wrap items-center gap-3 text-[14px]">시작 <input type="time" disabled={!canEdit} value={v.start} onChange={(e) => set('start', e.target.value)} className={input} />
            끝 <input type="time" disabled={!canEdit} value={v.end} onChange={(e) => set('end', e.target.value)} className={input} />
            {canEdit && <button onClick={() => set('end', hm(simIso()))} className={BTN}>지금</button>}
            <span>수리 시간 {mins === null || mins < 0 ? '○○' : mins}분</span>
            {mttr && <span className="text-slate-600">· {eq} MTTR(30일) {mttr.mttr_min ?? '—'}분{mttr.mttr_warn ? ' ▲' : ''} · 고장 {mttr.failures}건</span>}
          </div>
        ))}
        {sec('같은 사례 (9월, 같은 설비·같은 알람)', same.length ? <ul className="text-[14px]">{same.map((r) => <li key={r.record_no}>{r.record_no} · {md(r.start_at)} · 원인 {r.cause} · 조치 {r.action} · {r.repair_min}분</li>)}</ul> : <span className="text-[14px] text-slate-600">같은 사례 없음</span>)}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-300 pt-3">
          {role === 'MNT' && !done && (<>
            <button onClick={() => putWr({ ...v, state: 'editing', revisions: rev(wr.revisions, wr.revisions.length ? '수정' : '처음 저장', user.name, role, diff(wr as unknown as Record<string, unknown>, v as unknown as Record<string, unknown>, names)) })} className={BTN}>저장</button>
            <button disabled={lockN < LOCK.length} onClick={() => setConfirm(true)} className={DARK}>확정{lockN < LOCK.length ? ` — 잠금·표지 ${LOCK.length}개 중 ${lockN}개` : ''}</button>
          </>)}
          {role === 'SUP' && wr.state === 'confirmed' && <button onClick={() => putWr({ ...wr, state: 'checked', revisions: rev(wr.revisions, '확인', user.name, role) })} className={DARK}>확인</button>}
          {done && <span className="text-[14px] text-slate-600">🔒 확정됨 — 고치려면 새 버전 + 사유 (수정 이력)</span>}
        </div>
        {note && <p className="mt-3 rounded-md bg-[#e8f6fa] px-3 py-2 text-[14px] font-semibold">{note}</p>}
      </div>
      {confirm && <ConfirmBox title="작업기록서를 확정할까요?" okLabel="확정" body="확정하면 내용이 잠기고, 짝 작업지시서가 완료로 바뀌고, 설비가 복귀하고(시뮬레이터), 사용한 부품이 재고에서 빠집니다."
        onOk={() => { setConfirm(false); void doConfirm(); }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}

// 사용 부품·공구는 재고 품목에서만 고른다 (직접 입력 칸 없음) — 지금 재고는 서버 값
export function PartsPicker({ value, onChange, disabled }: { value: { item: string; qty: number }[]; onChange: (v: { item: string; qty: number }[]) => void; disabled?: boolean }) {
  const { inv } = useApp();
  const items = (inv?.items ?? []).filter((i) => i.category !== 'FG' && i.category !== 'RAW');
  return (
    <div className="text-[14px]">
      <div className="mb-1 font-semibold">사용 부품·공구 <span className="font-normal text-slate-500">(재고 품목에서 고르기)</span></div>
      {value.map((p, i) => (
        <div key={i} className="mb-1 flex items-center gap-2">
          <select disabled={disabled} value={p.item} onChange={(e) => onChange(value.map((x, k) => (k === i ? { ...x, item: e.target.value } : x)))} className="h-11 rounded-md border border-slate-300 px-2 disabled:bg-slate-50">
            {items.map((it) => <option key={it.item_no} value={it.item_no}>{it.item_name} (재고 {it.stock_qty}{it.unit}{it.low ? ' ▲' : ''})</option>)}
          </select>
          <input type="number" min={0.1} step={0.1} disabled={disabled} value={p.qty} onChange={(e) => onChange(value.map((x, k) => (k === i ? { ...x, qty: Math.max(0.1, Number(e.target.value) || 1) } : x)))} className="h-11 w-20 rounded-md border border-slate-300 px-2 disabled:bg-slate-50" />
          {!disabled && <button onClick={() => onChange(value.filter((_, k) => k !== i))} className="h-11 rounded-md border border-slate-300 px-3">빼기</button>}
        </div>
      ))}
      {!disabled && items.length > 0 && <button onClick={() => onChange([...value, { item: items[0].item_no, qty: 1 }])} className="h-11 rounded-md border border-dashed border-slate-400 px-3 font-semibold">+ 부품 추가</button>}
    </div>
  );
}
