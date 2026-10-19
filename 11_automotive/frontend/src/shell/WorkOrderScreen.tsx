'use client';
// SCR-11 정비 작업지시서 — OP-30 정지 등급 알람 1건(또는 반복 알람 2단계) = 작업지시서 1건이 프로그램 초안으로 이미 있다.
// 초안은 지침카드·DOC-03 점검 순서(보전 줄)·DOC-05에서 규칙으로 만든다 ("프로그램 초안"). 비서가 켜져 있으면 제목·증상을 비서가 다듬고 "AI비서 초안"으로 바뀐다.
import { useEffect, useRef, useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { md, minsSince, simIso } from './live';
import { ALARMS, SAFETY, USERS, hhmm, machineLabel, userName } from './model';
import { SafetyBlock, ConfirmBox } from './Safety';
import { WO_STEPS, diff, rev, type WorkOrder } from './workflow';


export default function WorkOrderScreen({ no }: { no: string }) {
  const { wos, putWo, user, role, back, openRecord, addNotice, history, inv, go, openSource, alerts } = useApp();
  const wo = wos.find((w) => w.no === no);
  const [title, setTitle] = useState(wo?.title ?? '');
  const [symptom, setSymptom] = useState(wo?.symptom ?? '');
  const [steps, setSteps] = useState((wo?.steps ?? []).join('\n'));
  // 비서가 제목·증상을 다듬어 넣으면(wo가 바뀜) 사람이 아직 손대지 않은 칸만 따라 바꾼다 — 손댄 칸은 그대로 둔다
  const synced = useRef({ title: wo?.title ?? '', symptom: wo?.symptom ?? '' });
  useEffect(() => {
    if (!wo) return;
    // 비교할 옛 값과 새 값은 setState를 부르기 전에 잡아 둔다 — 갱신 함수는 그리는 단계에서 나중에 돌 수 있어, 그때는 synced.current가 이미 새 값이라 비교가 어긋난다
    if (wo.title !== synced.current.title) { const before = synced.current.title, next = wo.title; setTitle((t) => (t === before ? next : t)); synced.current.title = next; }
    if (wo.symptom !== synced.current.symptom) { const before = synced.current.symptom, next = wo.symptom; setSymptom((s) => (s === before ? next : s)); synced.current.symptom = next; }
  }, [wo?.title, wo?.symptom]); // eslint-disable-line react-hooks/exhaustive-deps
  const [confirm, setConfirm] = useState<'approve' | 'cancel' | 'revise' | null>(null);
  const [reason, setReason] = useState('');
  const [reviseOpen, setReviseOpen] = useState(false);
  const [src, setSrc] = useState(false);
  if (!wo) return <div className={PAGE}><div className={CARD}>작업지시서가 없습니다 <button onClick={back} className={BTN}>닫기</button></div></div>;
  const a = ALARMS[wo.code], alert = alerts.find((x) => x.id === wo.alertId);
  const locked = wo.state !== 'draft' && wo.state !== 'editing';
  const editable = (!locked && role === 'MNT') || (reviseOpen && (role === 'MNT' || role === 'SUP'));
  const wait = minsSince(wo.created);
  const mnts = USERS.filter((u) => u.role === 'MNT');
  const isAssignee = wo.assignee === user.id;
  const humanEdited = new Set(wo.revisions.filter((r) => r.byRole !== 'PROGRAM').flatMap((r) => r.changes.map((c) => c.field)));
  const eq = MACHINES[wo.machine].eq!;
  const similar = (history?.work_orders ?? []).filter((w) => w.equipment_id === eq && (history?.alarms.find((x) => x.alarm_event_id === w.alarm_event_id)?.alarm_code === wo.code));
  const recOf = (woNo: string) => history?.work_records.find((r) => r.wo_no === woNo);
  const stockOf = (no2: string) => inv?.items.find((i) => i.item_no === no2);

  const save = (kind: string, rsn?: string) => {
    const next = { title, symptom, steps: steps.split('\n').map((s) => s.trim()).filter(Boolean) };
    const ch = diff(wo as unknown as Record<string, unknown>, next, { title: '제목', symptom: '증상', steps: '작업 순서' });
    const w: WorkOrder = { ...wo, ...next, state: locked ? wo.state : 'editing', version: wo.version + 1, edited: [...wo.edited, ...ch.map((c) => `${c.field} — ${user.name} ${hhmm(simIso())}`)], revisions: rev(wo.revisions, kind, user.name, role, ch, rsn) };
    putWo(w);
    if (rsn) addNotice({ id: `DOC_REVISED:${wo.no}:${w.version}`, rule: 'DOC_REVISED', ruleName: '문서 수정', level: '참고', rank: '4', at: simIso(), ts: Date.now(), text: `작업지시서 ${wo.no} 확정 후 수정 — ${rsn} (${user.name})`, roles: ['MGR'], delivery: 'BUBBLE', handled: false, open: { screen: 'wo', key: wo.no } });
    setReviseOpen(false); setReason('');
  };
  const idx = WO_STEPS.findIndex(([k]) => k === wo.state);
  const hl = (f: string) => (humanEdited.has(f) ? 'border-[#0f9fbd] bg-[#f0fafc]' : '');
  const tag = (f: string) => <span className={`ml-1 rounded px-1 text-[11px] font-bold ${humanEdited.has(f) ? 'bg-[#e8f6fa] text-[#0f6f86]' : 'bg-slate-100 text-slate-600'}`}>{humanEdited.has(f) ? '[수정]' : '[프로그램]'}</span>;
  const sec = (head: string, body: React.ReactNode) => (<section className="border-t border-slate-200 py-3"><h3 className="mb-1 text-[14px] font-bold text-slate-500">{head}</h3>{body}</section>);

  return (
    <div className={PAGE}>
      <div className={`mx-auto max-w-[920px] rounded-lg bg-white p-4 ${locked ? 'border border-slate-300' : 'border-2 border-dashed border-slate-400'}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">정비 작업지시서 {wo.no}</h2>
          <div className="flex gap-2"><button onClick={() => go('revs', `WO:${wo.no}`)} className={BTN}>수정 이력 (v{wo.version})</button><button onClick={() => window.print()} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button></div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1 text-[14px]" aria-label="상태">
          {wo.state === 'cancelled' ? <b className="text-[#c62a2f]">취소됨</b> : WO_STEPS.map(([k, label], i) => (
            <span key={k} className={`rounded-full px-3 py-1 ${i === idx ? 'bg-[#1c2530] font-bold text-white' : i < idx ? 'bg-slate-200' : 'border border-slate-300 text-slate-500'}`}>{k === 'draft' ? `${label} v0` : k === 'editing' && i === idx ? `${label} v${wo.version}` : label}</span>
          ))}
          {!locked && wo.state !== 'cancelled' && <span className={wait >= 120 ? 'font-bold text-[#9a6200]' : 'text-slate-600'}>{wait >= 120 ? '▲' : wait >= 30 ? 'ⓘ' : ''} 승인 대기 {wait}분</span>}
        </div>

        {sec('자동 칸', (
          <div className="text-[15px]">번호 {wo.no} · 설비 {machineLabel(wo.machine)} · 알람 {wo.code} · 로트 {wo.lot ? <button onClick={() => go('lots', wo.lot)} className="underline">{wo.lot}</button> : '—'} · 발생 {md(wo.created)} {hhmm(wo.created)}{alert?.cleared ? ` · 설비 알람 ${hhmm(alert.cleared)} 해제` : ''}<br />
            계기 <b className="text-[#c62a2f]">{wo.trigger === 'REPEAT_2' ? '▲ 반복 알람 2단계 (원인 점검)' : '⚠ 정지 등급 알람'}</b>
          </div>
        ))}
        {sec(`제목 · 증상 (${wo.llm ? 'AI비서 초안' : '프로그램 초안'})`, (
          <div className="flex flex-col gap-2">
            <label className="text-[14px] font-semibold">제목{tag('제목')}<input disabled={!editable} value={title} onChange={(e) => setTitle(e.target.value)} className={`mt-1 h-11 w-full rounded-md border border-slate-300 px-3 text-[15px] font-normal disabled:bg-slate-50 ${hl('제목')}`} /></label>
            <label className="text-[14px] font-semibold">증상{tag('증상')}<textarea disabled={!editable} value={symptom} onChange={(e) => setSymptom(e.target.value)} rows={2} className={`mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-[15px] font-normal disabled:bg-slate-50 ${hl('증상')}`} /></label>
          </div>
        ))}
        {sec('작업 순서 (DOC-03 점검 순서의 보전 줄)', (
          <><div className="mb-1 text-[12px]">{tag('작업 순서')}</div>
            <textarea disabled={!editable} value={steps} onChange={(e) => setSteps(e.target.value)} rows={Math.max(3, steps.split('\n').length)} className={`w-full rounded-md border border-slate-300 px-3 py-2 text-[15px] disabled:bg-slate-50 ${hl('작업 순서')}`} aria-label="작업 순서, 한 줄에 한 단계" /></>
        ))}
        {sec('차단 지점 · 저장 에너지 (DOC-05 §3)', <div className="text-[14px]">{SAFETY[eq].points.join(' · ')}<br />저장 에너지: {SAFETY[eq].energy.join(' · ')}</div>)}
        {sec('안전', a ? <SafetyBlock machine={wo.machine} alarm={a} /> : null)}
        {sec('비슷한 과거 작업 (9월, 같은 설비·같은 알람)', similar.length ? (
          <ul className="text-[14px]">{similar.map((w) => { const r = recOf(w.wo_no); return <li key={w.wo_no}>{w.wo_no} · {md(w.created_at)} · {w.title}{r ? ` → ${r.record_no} 원인: ${r.cause} / 조치: ${r.action} (${r.repair_min}분)` : ''}</li>; })}</ul>
        ) : <span className="text-[14px] text-slate-600">기록 없음</span>)}
        {sec('예상 부품 · 공구 (9월 같은 알람 작업기록서에 쓴 것)', wo.parts.length ? (
          <ul className="text-[14px]">{wo.parts.map((p) => { const s = stockOf(p); return <li key={p}>{s?.item_name ?? p} — 지금 재고 {s?.stock_qty ?? '—'}{s?.unit} (안전 재고 {s?.safety_stock}){s?.low ? ' ▲ 부족' : ''}</li>; })}</ul>
        ) : <span className="text-[14px] text-slate-500">제안 없음 (9월 같은 알람 기록에 쓴 부품 없음)</span>)}
        {sec('담당자', role === 'SUP' && !locked ? (
          <select value={wo.assignee ?? ''} onChange={(e) => putWo({ ...wo, assignee: e.target.value || null, revisions: rev(wo.revisions, '담당 지정', user.name, role, [{ field: '담당자', before: userName(wo.assignee), after: userName(e.target.value) }]) })} className="h-11 rounded-md border border-slate-300 px-3 text-[15px]">
            <option value="">보전 담당자 고르기</option>{mnts.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.shift === 'DAY' ? '주간' : '야간'})</option>)}
          </select>
        ) : <span className="text-[15px]">{wo.assignee ? userName(wo.assignee) : '아직 지정 안 됨 (반장만 지정)'}{wo.approvedBy ? ` · 승인 ${wo.approvedBy} ${hhmm(wo.approvedAt ?? '')}` : ''}</span>)}

        {reviseOpen && (
          <div className="mt-2 rounded-md border border-[#e8954a] bg-[#fff8ef] p-2 text-[14px]">확정 후 수정 — 위 칸을 고친 뒤 사유를 쓰세요 (새 버전, 관리자에게 수정 알림)
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="수정 사유 (필수)" className="mt-1 h-11 w-full rounded-md border border-slate-300 px-2" />
          </div>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-300 pt-3">
          {role === 'MNT' && !locked && <button onClick={() => save('수정')} className={DARK}>저장</button>}
          {role === 'SUP' && !locked && <button disabled={!wo.assignee} onClick={() => setConfirm('approve')} className={DARK}>승인</button>}
          {role === 'SUP' && !locked && !wo.assignee && <span className="text-[13px] text-[#9a6200]">담당자를 먼저 지정하세요</span>}
          {role === 'MGR' && !locked && <><button disabled={!wo.assignee} onClick={() => setConfirm('approve')} className={DARK}>대리 승인</button><button onClick={() => setConfirm('cancel')} className={BTN}>취소</button></>}
          {role === 'MNT' && isAssignee && wo.state === 'approved' && <button onClick={() => putWo({ ...wo, state: 'inprogress', revisions: rev(wo.revisions, '작업 시작', user.name, role) })} className={DARK}>작업 시작</button>}
          {role === 'MNT' && isAssignee && (wo.state === 'approved' || wo.state === 'inprogress') && <button onClick={() => openRecord(wo.no)} className={BTN}>작업기록서 쓰기</button>}
          {wo.recordNo && <button onClick={() => openRecord(wo.no)} className={BTN}>작업기록서 {wo.recordNo} 보기</button>}
          {locked && wo.state !== 'cancelled' && (role === 'MNT' || role === 'SUP') && !reviseOpen && <button onClick={() => setReviseOpen(true)} className={BTN}>확정 후 수정 (사유 필수)</button>}
          {reviseOpen && <button disabled={!reason.trim()} onClick={() => setConfirm('revise')} className={DARK}>수정 저장</button>}
          {locked && wo.state !== 'cancelled' && !reviseOpen && <span className="text-[13px] text-slate-500">🔒 승인 뒤 내용 잠김</span>}
        </div>
        <button onClick={() => setSrc((s) => !s)} className="mt-3 h-11 text-[14px] font-semibold text-slate-600">{src ? '▾' : '▸'} 출처 더보기</button>
        {src && a && (
          <ul className="mt-1 list-disc pl-5 text-[13px] text-slate-600">
            <li>증상 — 지침카드 · 알람 코드집 <button onClick={() => openSource('DOC-02', a.doc02.replace('DOC-02 ', ''))} className="underline">{a.doc02}</button></li>
            <li>작업 순서 — 고장 대응 매뉴얼 {a.doc03.map((d) => { const m = d.match(/(DOC-\d+)\s+§?([\d.]+)/); return <button key={d} onClick={() => m && openSource(m[1], m[2])} className="mr-1 underline">{d}</button>; })} 점검 순서(보전 줄)</li>
            <li>차단 지점·저장 에너지 — 안전 작업 기준서 <button onClick={() => openSource('DOC-05', '3')} className="underline">DOC-05 §3</button></li>
            {wo.trigger === 'REPEAT_2' && <li>계기 — <button onClick={() => openSource('DOC-03', '1.4')} className="underline">DOC-03 §1.4 반복 알람 2단계</button></li>}
          </ul>
        )}
      </div>
      {confirm && (
        <ConfirmBox title={confirm === 'approve' ? '작업지시서를 승인할까요?' : confirm === 'cancel' ? '작업지시서를 취소할까요?' : '확정 후 수정을 저장할까요?'}
          body={confirm === 'approve' ? '승인하면 내용이 잠기고 담당 보전 담당자에게 "작업지시서 배정" 알림이 갑니다.' : confirm === 'cancel' ? '취소하면 되돌릴 수 없습니다.' : `새 버전 v${wo.version + 1}이 생기고 관리자에게 수정 알림이 갑니다. 사유: ${reason}`}
          okLabel={confirm === 'approve' ? '승인' : confirm === 'cancel' ? '취소하기' : '저장'}
          onOk={() => {
            if (confirm === 'approve') {
              putWo({ ...wo, state: 'approved', approvedBy: user.name, approvedAt: simIso(), revisions: rev(wo.revisions, role === 'MGR' ? '대리 승인' : '승인', user.name, role) });
              if (wo.assignee) addNotice({ id: `WO_ASSIGNED:${wo.no}`, rule: 'WO_ASSIGNED', ruleName: '작업지시서 배정', level: '참고', rank: '4', at: simIso(), ts: Date.now(), text: `작업지시서 ${wo.no}가 배정됐어요`, roles: ['MNT'], userIds: [wo.assignee], delivery: 'BUBBLE', handled: false, open: { screen: 'wo', key: wo.no } });
            } else if (confirm === 'cancel') putWo({ ...wo, state: 'cancelled', revisions: rev(wo.revisions, '취소', user.name, role) });
            else save('확정 후 수정', reason);
            setConfirm(null);
          }} onCancel={() => setConfirm(null)} />
      )}
    </div>
  );
}
