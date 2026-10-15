'use client';
// SCR-13 간이 작업기록 — 주의 등급 알람, OP-30 밖 정지 등급 알람의 짧은 기록. AI 초안이 없다: 사람이 조치를 고르고 확정한다.
// kind 'cause' = 반복 알람 2단계의 원인 점검 기록 (다른 공정, DOC-03 §1.4).
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { api, md } from './live';
import { ALARMS, LEVEL_VIEW, alarmTitle, hhmm, machineLabel, sevText } from './model';
import { ConfirmBox, LOCK, LockChecks, SafetyBlock, needsLock } from './Safety';
import { PartsPicker } from './WorkRecordScreen';
import { diff, rev, type SimpleRecord } from './workflow';

export default function SimpleRecordScreen({ no }: { no: string }) {
  const { srs, putSr, alerts, user, role, back, markAlert, notices, handleNotice, go, toast, reloadInv, openSource } = useApp();
  const rec = srs.find((r) => r.no === no);
  const [v, setV] = useState<SimpleRecord | null>(rec ?? null);
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState('');
  if (!rec || !v) return <div className={PAGE}><div className={CARD}>간이 작업기록이 없습니다 <button onClick={back} className={BTN}>닫기</button></div></div>;
  const alert = alerts.find((a) => a.id === rec.alertId);
  const a = alert?.alarm ?? ALARMS[rec.code] ?? null;
  const cause = rec.kind === 'cause';
  const other = a?.severity === 'STOP';
  const who = cause ? role === 'MNT' : a?.severity === 'WARN' ? role === 'OPR' || role === 'MNT' : role === 'MNT';
  const done = rec.state === 'confirmed';
  const canEdit = (role === 'OPR' || role === 'MNT') && !done;
  const lockOn = !cause && needsLock(a, rec.machine);
  const lockN = v.lock.filter(Boolean).length;
  const options = cause ? ['원인을 찾아 고침 (부품 교체·조임·청소)', '설정·조건을 바꿈 (재발 방지)', '원인 못 찾음 → 작업지시서 요청', '기타 → 메모'] : [...(a?.actions ?? []), '기타 → 메모'];
  const lv = alert ? LEVEL_VIEW[alert.level] : LEVEL_VIEW['주의'];
  const names = { action: '조치', memo: '메모', parts: '사용 소모품' };
  const sec = (head: string, body: React.ReactNode) => (<section className="border-t border-slate-200 py-3"><h3 className="mb-1 text-[14px] font-bold text-slate-500">{head}</h3>{body}</section>);

  const doConfirm = async () => {
    putSr({ ...v, state: 'confirmed', by: user.name, revisions: rev(rec.revisions, '확정', user.name, role, diff(rec as unknown as Record<string, unknown>, v as unknown as Record<string, unknown>, names)) });
    for (const p of v.parts) { try { await api('inventory/txns', { role, user_id: user.id, item_no: p.item, txn_type: 'USE', qty: p.qty, memo: `간이 작업기록 ${rec.no}` }); } catch (e) { toast((e as Error).message); } }
    if (alert) markAlert([alert.id], `${user.name} (간이 ${rec.no})`);
    if (cause) notices.filter((n) => n.rule === 'CAUSE_CHECK_REQUEST' && n.machine === rec.machine && !n.handled).forEach((n) => handleNotice(n.id, v.action));
    reloadInv();
    setNote(`처리됨 · ${MACHINES[rec.machine].name} 알람 ${rec.code}${v.parts.length ? ` · 재고 ${v.parts.length}건 차감` : ''}`);
  };

  return (
    <div className={PAGE}>
      <div className={`${CARD} max-w-[920px]`}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">{cause ? '원인 점검 간이 기록' : '간이 작업기록'} {rec.no}</h2>
          <div className="flex gap-2">{(role !== 'OPR' || rec.savedBy === user.name || rec.by === user.name) && <button onClick={() => go('revs', `SR:${rec.no}`)} className={BTN}>수정 이력</button>}<button onClick={back} className={BTN}>닫기</button></div>
        </div>
        {sec('자동 칸', <div className="text-[15px]">설비 {machineLabel(rec.machine)} · 알람 {alarmTitle(a, rec.code)} (<b style={{ color: lv.color }}>{lv.icon} {a ? sevText(a) : ''}</b>) · 로트 {alert?.lot ?? '—'} · {alert ? `${md(alert.time)} ${hhmm(alert.time)}` : ''}{cause ? ' · 계기: 반복 알람 2단계' : ''}</div>)}
        {cause && sec('원인 점검 (DOC-03 §1.4)', <p className="text-[14px]">지난 조치 계획 뒤에도 같은 알람이 다시 떴습니다. 원인을 점검하고 한 일을 고르세요. <button onClick={() => openSource('DOC-03', '1.4')} className="underline">DOC-03 §1.4</button></p>)}
        {sec(cause ? '한 일 고르기' : `한 조치 고르기 (${a?.doc03[0] ?? 'DOC-03'}의 조치에서)`, (
          <div className="flex flex-col">{options.map((o) => (
            <label key={o} className="flex min-h-[44px] items-center gap-2 text-[15px]"><input type="radio" className="h-5 w-5" disabled={!canEdit} checked={v.action === o} onChange={() => setV((p) => (p ? { ...p, action: o } : p))} />{o}</label>))}</div>
        ))}
        {sec('사용 소모품', <PartsPicker value={v.parts} onChange={(p) => setV((x) => (x ? { ...x, parts: p } : x))} disabled={!canEdit} />)}
        {!cause && sec('안전', <div className="flex flex-col gap-3">{a && <SafetyBlock machine={rec.machine} alarm={a} />}{lockOn && <LockChecks value={v.lock} onChange={(l) => setV((p) => (p ? { ...p, lock: l } : p))} disabled={!canEdit} />}</div>)}
        {sec('메모', <textarea disabled={!canEdit} value={v.memo} onChange={(e) => setV((p) => (p ? { ...p, memo: e.target.value } : p))} rows={2} className="w-full rounded-md border border-slate-300 px-3 py-2 text-[15px] disabled:bg-slate-50" />)}
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-300 pt-3">
          {canEdit && <button onClick={() => putSr({ ...v, savedBy: v.savedBy ?? user.name, revisions: rev(rec.revisions, rec.revisions.length ? '수정' : '처음 저장', user.name, role, diff(rec as unknown as Record<string, unknown>, v as unknown as Record<string, unknown>, names)) })} className={BTN}>저장{other && role === 'OPR' ? ' (입력만)' : ''}</button>}
          {canEdit && who && <button disabled={!v.action || (lockOn && lockN < LOCK.length)} onClick={() => setConfirm(true)} className={DARK}>확정{!v.action ? ' — 한 조치를 고르세요' : lockOn && lockN < LOCK.length ? ` — 잠금·표지 ${LOCK.length}개 중 ${lockN}개` : ''}</button>}
          {canEdit && !who && <span className="text-[14px] text-slate-500">이 기록은 보전 담당자(MNT)만 확정합니다 — 입력만 저장할 수 있습니다.</span>}
          {done && <span className="text-[14px] text-slate-600">🔒 확정됨 ({rec.by})</span>}
          {!canEdit && !done && <span className="text-[14px] text-slate-500">{role === 'SUP' || role === 'MGR' ? '보기 전용입니다.' : ''}</span>}
        </div>
        {note && <p className="mt-3 rounded-md bg-[#e8f6fa] px-3 py-2 text-[14px] font-semibold">{note}</p>}
      </div>
      {confirm && <ConfirmBox title="간이 작업기록을 확정할까요?" okLabel="확정" body={`확정하면 이 알람이 처리됩니다. 사용한 소모품은 재고에서 빠집니다.`}
        onOk={() => { setConfirm(false); void doConfirm(); }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}
