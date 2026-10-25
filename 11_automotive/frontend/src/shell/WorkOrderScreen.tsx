'use client';
// SCR-11 정비 작업지시서 — OP-30 정지 등급 알람 1건(또는 반복 알람 2단계) = 작업지시서 1건이 프로그램 초안으로 이미 있다.
// 초안은 지침카드·DOC-03 점검 순서(보전 줄)·DOC-05에서 규칙으로 만든다 ("프로그램 초안"). 비서가 켜져 있으면 제목·증상을 비서가 다듬고 "AI비서 초안"으로 바뀐다.
// 시안(2026-10-20): 진행 알약·승인 대기 → 결론 띠(제목·증상) → 담당자·승인 → 작업 순서 → 안전. 담당자는 그 교대 보전 담당자로 미리 채워져 있다(App createWo).
// 승인 뒤 담당 보전 담당자가 [작업 시작]을 누르면 같은 화면 아래에 작업 기록 칸(WorkRecordPanel)이 열린다 — 작업기록서를 따로 여는 화면 이동을 줄임 (2026-10-20 팀 검토).
import { LockIcon } from './ui';
import { useEffect, useRef, useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { md, minsSince, simIso } from './live';
import { ALARMS, USERS, hhmm, machineLabel, userName } from './model';
import { ConfirmBox, SafeTag, SafetyBlock, safetySrc } from './Safety';
import { WO_STEPS, diff, rev, type WorkOrder } from './workflow';
import { Acts, Band, Chip, DocHead, DocPage, Fold, InfoRow, NumList, printDoc, RO, Sec, SrcFold, Steps } from './DocKit';
import { WorkRecordPanel } from './WorkRecordScreen';

export default function WorkOrderScreen({ no, focusRecord }: { no: string; focusRecord?: boolean }) {
  const { wos, wrs, putWo, user, role, back, openRecord, addNotice, history, inv, go, openSource, alerts, toast } = useApp();
  const wo = wos.find((w) => w.no === no);
  const wr = wrs.find((r) => r.woNo === no);
  // 작업기록서를 열었거나 [작업 시작]을 누르면 작업 기록 칸으로 내려간다
  const [scrollTo, setScrollTo] = useState(!!focusRecord);
  useEffect(() => {
    if (!scrollTo || !wr) return;
    const t = setTimeout(() => { document.getElementById('work-record')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); setScrollTo(false); }, 150);
    return () => clearTimeout(t);
  }, [scrollTo, wr?.no]); // eslint-disable-line react-hooks/exhaustive-deps
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
  const [confirm, setConfirm] = useState<'approve' | 'revise' | null>(null);
  const [reason, setReason] = useState('');
  const [reviseOpen, setReviseOpen] = useState(false);
  if (!wo) return <div className={PAGE}><div className={CARD}>작업지시서가 없습니다 <button onClick={back} className={BTN}>닫기</button></div></div>;
  const a = ALARMS[wo.code], alert = alerts.find((x) => x.id === wo.alertId);
  const locked = wo.state !== 'draft' && wo.state !== 'editing';
  const editable = (!locked && role === 'MNT') || (reviseOpen && (role === 'MNT' || role === 'SUP'));
  const wait = minsSince(wo.created);
  const mnts = USERS.filter((u) => u.role === 'MNT');
  const isAssignee = wo.assignee === user.id;
  const eq = MACHINES[wo.machine].eq!;
  const similar = (history?.work_orders ?? []).filter((w) => w.equipment_id === eq && (history?.alarms.find((x) => x.alarm_event_id === w.alarm_event_id)?.alarm_code === wo.code));
  const recOf = (woNo: string) => history?.work_records.find((r) => r.wo_no === woNo);
  const stockOf = (no2: string) => inv?.items.find((i) => i.item_no === no2);
  const repeat = wo.trigger === 'REPEAT_2';

  const save = (kind: string, rsn?: string) => {
    const next = { title, symptom, steps: steps.split('\n').map((s) => s.trim()).filter(Boolean) };
    const ch = diff(wo as unknown as Record<string, unknown>, next, { title: '제목', symptom: '증상', steps: '작업 순서' });
    if (!ch.length) { toast('바뀐 내용 없음'); return; } // 바뀐 칸이 있을 때만 새 버전 (2026-10-20)
    const w: WorkOrder = { ...wo, ...next, state: locked ? wo.state : 'editing', version: wo.version + 1, edited: [...wo.edited, ...ch.map((c) => `${c.field} — ${user.name} ${hhmm(simIso())}`)], revisions: rev(wo.revisions, kind, user.name, role, ch, rsn) };
    putWo(w);
    if (rsn) addNotice({ id: `DOC_REVISED:${wo.no}:${w.version}`, rule: 'DOC_REVISED', ruleName: '문서 수정', level: '참고', rank: '4', at: simIso(), ts: Date.now(), text: `작업지시서 ${wo.no} 확정 후 수정 — ${rsn} (${user.name})`, roles: ['MGR'], delivery: 'BUBBLE', handled: false, open: { screen: 'wo', key: wo.no } });
    setReviseOpen(false); setReason('');
  };
  const idx = WO_STEPS.findIndex(([k]) => k === wo.state);
  const field = 'w-full rounded-ctl border border-line bg-white px-3 text-card font-normal';
  const stepList = steps.split('\n').map((s) => s.trim()).filter(Boolean);

  return (
    <DocPage>
      <DocHead title={<>정비 작업지시서 <span className="font-mono">{wo.no}</span></>}
        right={wo.state === 'cancelled' ? <Chip tone="crit">취소됨</Chip> : <Steps list={WO_STEPS.map(([k, label]) => (k === 'draft' ? `${label} v0` :k === 'editing' && k === wo.state ? `${label} v${wo.version}` : label))} cur={idx} />} />
      <InfoRow right={<><button onClick={() => go('revs', `WO:${wo.no}`)} className={BTN}>수정 이력 v{wo.version}</button><button onClick={printDoc} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button></>}>
        {!locked && wo.state !== 'cancelled' && <Chip tone={wait >= 120 ? 'warn' : 'mute'}>{wait >= 120 ? '▲ ' : wait >= 30 ? 'ⓘ ' : ''}승인 대기 {wait}분</Chip>}
        {locked && wo.state !== 'cancelled' && !reviseOpen && <Chip><LockIcon /> 잠김</Chip>}
      </InfoRow>

      <Band tone={repeat ? 'warn' : 'crit'}
        title={editable ? <input aria-label="제목" value={title} onChange={(e) => setTitle(e.target.value)} className={`${field} h-11 font-bold`} /> : title}
        desc={editable ? <textarea aria-label="증상" value={symptom} onChange={(e) => setSymptom(e.target.value)} rows={2} className={`${field} py-2`} /> : symptom}
        chips={<>
          <Chip tone={repeat ? 'solid-warn' : 'solid-crit'}>{repeat ? '▲ 계기: 반복 알람 2단계' : '⚠ 계기: 정지 등급 알람'}</Chip>
          <Chip>{machineLabel(wo.machine)}</Chip>
          <Chip mono>알람 {wo.code}</Chip>
          {wo.lot && <button onClick={() => go('lots', wo.lot)}><Chip mono>로트 {wo.lot}</Chip></button>}
          <Chip mono>발생 {md(wo.created)} {hhmm(wo.created)}</Chip>
          {alert?.cleared && <Chip tone="ok">설비 알람 {hhmm(alert.cleared)} 해제</Chip>}
        </>} />

      <Sec title="담당자 · 승인" right={wo.approvedBy ? <Chip tone="ok">승인 {wo.approvedBy} {hhmm(wo.approvedAt ?? '')}</Chip> : undefined}>
        <div className="flex flex-wrap items-center gap-2">
          {role === 'SUP' && !locked ? (<>
            <select aria-label="담당 보전 담당자" value={wo.assignee ?? ''} onChange={(e) => putWo({ ...wo, assignee: e.target.value || null, revisions: rev(wo.revisions, '담당 지정', user.name, role, [{ field: '담당자', before: userName(wo.assignee), after: userName(e.target.value) }]) })} className="h-11 rounded-ctl border border-line px-3 text-card">
              <option value="">보전 담당자 고르기</option>{mnts.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.shift === 'DAY' ? '주간' : '야간'})</option>)}
            </select>
            <button disabled={!wo.assignee} onClick={() => setConfirm('approve')} className={DARK}>승인</button>
          </>) : <span className="text-card font-semibold">{wo.assignee ? userName(wo.assignee) : '아직 지정 안 됨'}</span>}
          {role === 'MNT' && isAssignee && wo.state === 'approved' && <button onClick={() => { putWo({ ...wo, state: 'inprogress', revisions: rev(wo.revisions, '작업 시작', user.name, role) }); openRecord(wo.no, false); setScrollTo(true); }} className={DARK}>작업 시작</button>}
          {role === 'MNT' && isAssignee && wo.state === 'inprogress' && !wr && <button onClick={() => { openRecord(wo.no, false); setScrollTo(true); }} className={DARK}>작업 기록 열기</button>}
          {wr && <button onClick={() => setScrollTo(true)} className={BTN}>작업 기록 {wr.no} ↓</button>}
        </div>
      </Sec>

      <Sec title="작업 순서" right={<Chip tone="acc">{stepList.length}단계</Chip>}>
        {editable ? <textarea aria-label="작업 순서, 한 줄에 한 단계" value={steps} onChange={(e) => setSteps(e.target.value)} rows={Math.max(3, steps.split('\n').length)} className={`${field} py-2`} />
          : <NumList items={stepList} />}
      </Sec>
      <Sec title="안전" right={a?.severity === 'STOP' ? SafeTag : undefined}>{a ? <SafetyBlock machine={wo.machine} alarm={a} /> : null}</Sec>
      <Sec title="예상 부품 · 공구">
        {wo.parts.length ? <div className="flex flex-wrap gap-1.5">{wo.parts.map((p) => { const s = stockOf(p); return <Chip key={p} tone={s?.low ? 'warn' : 'ok'}>{s?.item_name ?? p} · 재고 {s?.stock_qty ?? '—'}{s?.unit ?? ''} (안전 {s?.safety_stock ?? '—'}){s?.low ? ' ▲' : ''}</Chip>; })}</div>
          : <span className="text-body text-ink-2">없음</span>}
      </Sec>
      <Fold summary={`비슷한 과거 작업 — ${eq} · 알람 ${wo.code}`}>
        {similar.length ? <ul className="flex flex-col gap-1">{similar.map((w) => { const r = recOf(w.wo_no); return <li key={w.wo_no}><span className="font-mono">{w.wo_no}</span> · {md(w.created_at)} · {w.title}{r ? ` → ${r.record_no} 원인: ${r.cause} / 조치: ${r.action} (${r.repair_min}분)` : ''}</li>; })}</ul>
          : <span className="text-ink-2">같은 설비·같은 알람 작업지시서 없음</span>}
      </Fold>
      {a && <SrcFold>
        <li>증상 — 지침카드 · 알람 코드집 <button onClick={() => openSource('DOC-02', a.doc02.replace('DOC-02 ', ''))} className="underline">{a.doc02}</button></li>
        <li>작업 순서 — 고장 대응 매뉴얼 {a.doc03.map((d) => { const m = d.match(/(DOC-\d+)\s+§?([\d.]+)/); return <button key={d} onClick={() => m && openSource(m[1], m[2])} className="mr-1 underline">{d}</button>; })} 점검 순서(보전 줄)</li>
        <li>차단 지점·저장 에너지 — 안전 작업 기준서 <button onClick={() => openSource('DOC-05', '3')} className="underline">DOC-05 §3</button></li>
        {safetySrc(wo.machine, a, openSource)}
        {repeat && <li>계기 — <button onClick={() => openSource('DOC-03', '1.4')} className="underline">DOC-03 §1.4 반복 알람 2단계</button></li>}
      </SrcFold>}

      {reviseOpen && <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="확정 후 수정 사유 (필수)" className="h-11 w-full rounded-ctl border border-[#e8954a] bg-white px-3" />}
      <Acts>
        {role === 'MNT' && !locked && <button onClick={() => save('수정')} className={DARK}>저장</button>}
        {locked && wo.state !== 'cancelled' && (role === 'MNT' || role === 'SUP') && !reviseOpen && <button onClick={() => setReviseOpen(true)} className={BTN}>확정 후 수정</button>}
        {reviseOpen && <button disabled={!reason.trim()} onClick={() => setConfirm('revise')} className={DARK}>수정 저장</button>}
        {(role === 'OPR' || (role === 'SUP' && locked && !reviseOpen) || (role === 'MGR' && locked)) && RO}
      </Acts>
      {confirm && (
        <ConfirmBox title={confirm === 'approve' ? '작업지시서를 승인할까요?' : '확정 후 수정을 저장할까요?'}
          body={confirm === 'approve' ? `승인하면 내용이 잠기고 ${userName(wo.assignee)}에게 "작업지시서 배정" 알림이 갑니다.` : `새 버전 v${wo.version + 1}이 생기고 관리자에게 수정 알림이 갑니다. 사유: ${reason}`}
          okLabel={confirm === 'approve' ? '승인' : '저장'}
          onOk={() => {
            if (confirm === 'approve') {
              putWo({ ...wo, state: 'approved', approvedBy: user.name, approvedAt: simIso(), revisions: rev(wo.revisions, '승인', user.name, role) });
              if (wo.assignee) addNotice({ id: `WO_ASSIGNED:${wo.no}`, rule: 'WO_ASSIGNED', ruleName: '작업지시서 배정', level: '참고', rank: '4', at: simIso(), ts: Date.now(), text: `작업지시서 ${wo.no}가 배정됐어요`, roles: ['MNT'], userIds: [wo.assignee], delivery: 'BUBBLE', handled: false, open: { screen: 'wo', key: wo.no } });
            } else save('확정 후 수정', reason);
            setConfirm(null);
          }} onCancel={() => setConfirm(null)} />
      )}
      {wr && <WorkRecordPanel woNo={wo.no} />}
    </DocPage>
  );
}
