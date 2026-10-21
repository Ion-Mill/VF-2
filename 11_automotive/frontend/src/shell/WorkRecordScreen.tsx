'use client';
// SCR-12 작업기록서 — 작업지시서를 보고 실제로 한 일을 적는다. 확정 → 작업지시서 완료, 설비 복귀(시뮬레이터 confirm_work_record),
// 사용 부품 재고 차감(서버 거래 기록), MTTR 다시 계산(서버가 시뮬레이터 상태 기록으로).
// 2026-10-20부터 따로 된 화면이 아니라 작업지시서 화면 아래 칸(WorkRecordPanel)으로 보인다.
import { LockIcon } from './ui';
import { useState } from 'react';
import { BTN, DARK, useApp } from './ctx';
import { MACHINES } from './data';
import { api, hm, md, simIso } from './live';
import { ALARMS } from './model';
import { ConfirmBox, LOCK, LockChecks, LockHead } from './Safety';
import { diff, rev, type WorkRecord } from './workflow';
import { Acts, Band, Bar, Chip, DocHead, Fold, Kpi, RO, Sec, SrcFold, Steps } from './DocKit';

const STATUS: [WorkRecord['state'], string][] = [['draft', '초안'], ['editing', '수정 중'], ['confirmed', '확정 (보전)'], ['checked', '확인 (반장)']];

// [비서로 정리] 대신 규칙 정리: 문장을 원인·조치로, 재고 품목 이름이 나오면 사용 부품으로 (LLM 연결 전)
const organize = (memo: string, items: { item_no: string; item_name: string }[]) => {
  const ss = memo.split(/[.\n。]|(?<=다)\s/).map((s) => s.trim()).filter(Boolean);
  const isAct = (s: string) => /(교체|조임|조였|청소|보충|채움|채웠|바꿈|바꿨|정렬|재설정|복구|닦|교정|재시작|조정)/.test(s);
  const cause = ss.filter((s) => !isAct(s) || /(원인|때문|불량|마모|끼임|파손|느슨)/.test(s)).join('. ');
  const action = ss.filter(isAct).join('. ');
  const parts = items.filter((i) => memo.includes(i.item_name.split(' ')[0])).map((i) => ({ item: i.item_no, qty: 1 }));
  return { cause, action, parts };
};

// 작업지시서 화면 아래에 붙는 "작업 기록" 칸 (2026-10-20 팀 검토: 작업지시서 → 작업기록서를 한 화면으로). 데이터는 작업기록서 한 건으로 따로 남는다.
// 승인 뒤 담당 보전 담당자가 [작업 시작]을 누르면 생긴다. 메뉴·알림에서 작업기록서를 열면 작업지시서 화면이 열리고 여기로 내려온다.
export function WorkRecordPanel({ woNo }: { woNo: string }) {
  const { wos, wrs, putWr, putWo, user, role, inv, alerts, markAlert, restoreMachine, history, go, twin, toast, reloadInv, openSource } = useApp();
  const wo = wos.find((w) => w.no === woNo), wr = wrs.find((r) => r.woNo === woNo);
  const alert = alerts.find((a) => a.id === wo?.alertId);
  const [v, setV] = useState<WorkRecord | null>(wr ? { ...wr, start: wr.start || (alert ? hm(alert.time) : ''), end: wr.end } : null);
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState('');
  if (!wo || !wr || !v) return null;
  const done = wr.state === 'confirmed' || wr.state === 'checked';
  const canEdit = role === 'MNT' && !done;
  const lockN = v.lock.filter(Boolean).length;
  const set = <K extends keyof WorkRecord>(k: K, x: WorkRecord[K]) => setV((p) => (p ? { ...p, [k]: x } : p));
  const mins = v.start && v.end ? Math.round((Date.parse(`1970-01-01T${v.end}:00`) - Date.parse(`1970-01-01T${v.start}:00`)) / 60000) : null;
  const idx = STATUS.findIndex(([k]) => k === wr.state);
  const eq = MACHINES[wo.machine].eq!;
  const same = (history?.work_records ?? []).filter((r) => r.equipment_id === eq && history?.alarms.find((x) => x.alarm_event_id === r.alarm_event_id)?.alarm_code === wo.code);
  const mttr = twin?.kpi.mttr_mtbf[eq];
  const names = { memo: '작업자 메모', cause: '원인', action: '조치', parts: '사용 부품', stepChecks: '수행 단계', lock: '잠금·표지', start: '시작', end: '끝' };
  // 수정 이력에 읽을 수 있는 값으로 (부품 = 이름 ×수량, 체크 = n/전체)
  const cmp = (x: WorkRecord) => ({ ...x, parts: x.parts.map((p) => `${inv?.items.find((i) => i.item_no === p.item)?.item_name ?? p.item} ×${p.qty}`), lock: `${x.lock.filter(Boolean).length}/${LOCK.length}`, stepChecks: `${x.stepChecks.filter(Boolean).length}/${x.stepChecks.length}` }) as unknown as Record<string, unknown>;
  const changes = diff(cmp(wr), cmp(v), names);
  const input = 'h-11 rounded-ctl border border-line px-3 text-card disabled:bg-tile';
  const lockAll = lockN >= LOCK.length;
  const stepN = v.stepChecks.filter(Boolean).length;
  const a = ALARMS[wo.code];

  const doConfirm = async () => {
    const final: WorkRecord = { ...v, state: 'confirmed', confirmedAt: simIso(), end: v.end || hm(simIso()), revisions: rev(wr.revisions, '확정', user.name, role, changes) };
    putWr(final); putWo({ ...wo, state: 'done' });
    // 사용 부품 → 재고 차감 (작업기록서 확정 순간, FR-MNT-05-09)
    const used: string[] = [];
    for (const p of v.parts) {
      try { await api('inventory/txns', { role, user_id: user.id, item_no: p.item, txn_type: 'USE', qty: -Math.abs(p.qty), memo: `작업기록서 ${wr.no}` }); used.push(`${inv?.items.find((i) => i.item_no === p.item)?.item_name ?? p.item} −${p.qty}`); }
      catch (e) { toast((e as Error).message); }
    }
    // 처리 = 작업기록서 확정 → 그 알람과 연쇄 알람 모두 처리됨
    let first = alert; while (first?.prevId) { const p = alerts.find((x) => x.eventId === first!.prevId); if (!p) break; first = p; }
    const ids = alerts.filter((x) => x.machine === wo.machine && !x.handled && x.kind !== 'guide' && x.ts >= (first?.ts ?? 0)).map((x) => x.id);
    markAlert(ids, `${user.name} (작업기록서 ${wr.no})`);
    await restoreMachine(wo.machine);
    reloadInv();
    setNote(`확정 — MTTR 다시 계산 · 재고 ${used.length ? used.join(', ') : '차감 없음'} · ${MACHINES[wo.machine].name} 복귀`);
  };
  // 바뀐 칸이 있을 때만 새 버전 (2026-10-20)
  const save = () => {
    if (!changes.length) { toast('바뀐 내용 없음'); return; }
    putWr({ ...v, state: 'editing', revisions: rev(wr.revisions, wr.revisions.length ? '수정' : '처음 저장', user.name, role, changes) });
  };

  // 확정 조건 띠(잠금·표지 · 수행 단계 · 수리 시간) → 원인·조치·부품 → 수행 단계 체크 → 잠금·표지 체크(모두 체크)
  return (
    <div id="work-record" className="flex scroll-mt-4 flex-col gap-3 border-t-4 border-ink pt-4">
      <DocHead title={<>작업 기록 <span className="font-mono">{wr.no}</span></>}
        right={<><Steps list={STATUS.map(([, l]) => l)} cur={idx} /><button onClick={() => go('revs', `WR:${wr.no}`)} className={BTN}>수정 이력</button><button onClick={() => alert && go('replay', alert.time)} className={BTN}>▶ 다시 보기 (고장 직전)</button></>} />

      <Band tone={done ? 'mute' : lockAll ? 'ok' : 'warn'} title={done ? <><LockIcon /> 확정됨{wr.state === 'checked' ? ' · 반장 확인' : ''}</> : lockAll ? '확정할 수 있어요' : '아직 확정할 수 없어요'}>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5"><Kpi label="잠금·표지 (확정 조건)" value={lockN} unit={`/ ${LOCK.length}${lockAll ? ' ✓' : ''}`} tone={lockAll ? 'ok' : undefined} /><Bar pct={(lockN / LOCK.length) * 100} tone={lockAll ? 'ok' : undefined} /></div>
          <div className="flex flex-col gap-1.5"><Kpi label="수행 단계" value={stepN} unit={`/ ${wo.steps.length}`} /><Bar pct={wo.steps.length ? (stepN / wo.steps.length) * 100 : 0} /></div>
          <Kpi label="수리 시간" value={mins === null || mins < 0 ? '—' : mins} unit="분" sub={<>{v.start || '—'} ~ {v.end || '—'}{mttr ? ` · MTTR(30일) ${mttr.mttr_min ?? '—'}분${mttr.mttr_warn ? ' ▲' : ''}` : ''}</>} />
        </div>
      </Band>

      <Sec title="원인 · 조치 · 사용 부품">
        <div className="flex flex-col gap-2.5">
          <label className="text-small font-semibold text-ink-2">작업자 메모<textarea disabled={!canEdit} value={v.memo} onChange={(e) => set('memo', e.target.value)} rows={2} placeholder="예: 서보 케이블 커넥터 느슨함 원인. 커넥터 다시 조임. 축 윤활유 보충" className="mt-1 w-full rounded-ctl border border-line px-3 py-2 text-card font-normal text-ink disabled:bg-tile" /></label>
          {canEdit && <div><button disabled={!v.memo.trim()} onClick={() => { const o = organize(v.memo, inv?.items ?? []); setV((p) => p ? { ...p, cause: o.cause || p.cause, action: o.action || p.action, parts: o.parts.length ? o.parts : p.parts, aiFields: ['원인', '조치', '사용 부품'] } : p); }} className={BTN}>메모로 원인·조치 채우기</button></div>}
          <label className="text-small font-semibold text-ink-2">원인<input disabled={!canEdit} value={v.cause} onChange={(e) => set('cause', e.target.value)} className={`mt-1 w-full ${input} font-normal text-ink`} /></label>
          <label className="text-small font-semibold text-ink-2">조치<input disabled={!canEdit} value={v.action} onChange={(e) => set('action', e.target.value)} className={`mt-1 w-full ${input} font-normal text-ink`} /></label>
          <PartsPicker value={v.parts} onChange={(p) => set('parts', p)} disabled={!canEdit} />
        </div>
      </Sec>
      <Sec title="수행 단계 체크" right={<Chip tone={stepN === wo.steps.length ? 'ok' : 'acc'}>{stepN} / {wo.steps.length}</Chip>}>
        <div className="flex flex-col">{wo.steps.map((s, i) => (
          <label key={s} className="grid min-h-[44px] grid-cols-[22px_28px_minmax(0,1fr)] items-center gap-2 rounded-tile px-1 text-body hover:bg-tile">
            <input type="checkbox" className="h-5 w-5 accent-ink" disabled={!canEdit} checked={!!v.stepChecks[i]} onChange={() => set('stepChecks', v.stepChecks.map((c, k) => (k === i ? !c : c)))} />
            <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full border border-line font-mono text-small font-bold">{i + 1}</span>
            <span className={v.stepChecks[i] ? 'text-ink-2 line-through' : ''}>{s}</span>
          </label>))}</div>
      </Sec>
      <Sec title="잠금·표지 체크" right={<LockHead value={v.lock} onChange={(l) => set('lock', l)} disabled={!canEdit} />}>
        <LockChecks value={v.lock} onChange={(l) => set('lock', l)} disabled={!canEdit} />
      </Sec>
      <Sec title="시각">
        <div className="flex flex-wrap items-center gap-3 text-body">시작 <input type="time" disabled={!canEdit} value={v.start} onChange={(e) => set('start', e.target.value)} className={input} />
          끝 <input type="time" disabled={!canEdit} value={v.end} onChange={(e) => set('end', e.target.value)} className={input} />
          {canEdit && <button onClick={() => set('end', hm(simIso()))} className={BTN}>지금</button>}
          {mttr && <span className="text-ink-2">{eq} 고장 {mttr.failures}건 (30일)</span>}
        </div>
      </Sec>
      <Fold summary={`같은 사례 — 9월 ${eq} · 알람 ${wo.code}`}>
        {same.length ? <ul className="flex flex-col gap-1">{same.map((r) => <li key={r.record_no}><span className="font-mono">{r.record_no}</span> · {md(r.start_at)} · 원인 {r.cause} · 조치 {r.action} · {r.repair_min}분</li>)}</ul> : <span className="text-ink-2">없음</span>}
      </Fold>
      <SrcFold>
        <li>수행 단계 — 작업지시서 {wo.no}{a ? ` (고장 대응 매뉴얼 ${a.doc03.join(' · ')})` : ''}</li>
        <li>잠금·표지 — 안전 작업 기준서 <button onClick={() => openSource('DOC-05', '7')} className="underline">DOC-05 §7</button></li>
      </SrcFold>

      <Acts>
        {role === 'MNT' && !done && (<>
          <button onClick={save} className={BTN}>저장</button>
          <button disabled={!lockAll} onClick={() => setConfirm(true)} className={DARK}>확정</button>
        </>)}
        {role === 'SUP' && !done && <><Chip tone="warn">확정 전</Chip><button disabled className={DARK}>확인</button></>}
        {role === 'SUP' && wr.state === 'confirmed' && <button onClick={() => putWr({ ...wr, state: 'checked', revisions: rev(wr.revisions, '확인', user.name, role) })} className={DARK}>확인</button>}
        {(role === 'OPR' || role === 'MGR' || (role === 'MNT' && done)) && RO}
      </Acts>
      {note && <p className="rounded-ctl bg-tile px-3 py-2 text-body font-semibold">{note}</p>}
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
    <div className="text-body">
      <div className="mb-1 text-small font-semibold text-ink-2">사용 부품·공구</div>
      {value.map((p, i) => (
        <div key={i} className="mb-1 flex items-center gap-2">
          <select disabled={disabled} value={p.item} onChange={(e) => onChange(value.map((x, k) => (k === i ? { ...x, item: e.target.value } : x)))} className="h-11 rounded-ctl border border-line px-2 disabled:bg-tile">
            {items.map((it) => <option key={it.item_no} value={it.item_no}>{it.item_name} (재고 {it.stock_qty}{it.unit}{it.low ? ' ▲' : ''})</option>)}
          </select>
          <input type="number" min={0.1} step={0.1} disabled={disabled} value={p.qty} onChange={(e) => onChange(value.map((x, k) => (k === i ? { ...x, qty: Math.max(0.1, Number(e.target.value) || 1) } : x)))} className="h-11 w-20 rounded-ctl border border-line px-2 disabled:bg-tile" />
          {!disabled && <button onClick={() => onChange(value.filter((_, k) => k !== i))} className="h-11 rounded-ctl border border-line px-3">빼기</button>}
        </div>
      ))}
      {!disabled && items.length > 0 && <button onClick={() => onChange([...value, { item: items[0].item_no, qty: 1 }])} className="h-11 rounded-ctl border border-dashed border-line px-3 font-semibold">+ 부품 추가</button>}
    </div>
  );
}
