'use client';
// SCR-13 간이 작업기록 — 주의 등급 알람, OP-30 밖 정지 등급 알람의 짧은 기록. AI 초안이 없다: 사람이 조치를 고르고 확정한다.
// kind 'cause' = 반복 알람 2단계의 원인 점검 기록 (다른 공정, DOC-03 §1.4).
import { LockIcon } from './ui';
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { api, md } from './live';
import { ALARMS, LEVEL_VIEW, alarmTitle, hhmm, machineLabel, sevText } from './model';
import { ConfirmBox, LOCK, LockChecks, LockHead, SafeTag, SafetyBlock, needsLock, safetySrc } from './Safety';
import { PartsPicker } from './WorkRecordScreen';
import { diff, rev, type SimpleRecord } from './workflow';
import { Acts, Band, Chip, DocHead, DocPage, RO, Sec, SrcFold, Steps } from './DocKit';

export default function SimpleRecordScreen({ no }: { no: string }) {
  const { srs, putSr, alerts, user, role, back, markAlert, notices, handleNotice, go, toast, reloadInv, openSource, inv } = useApp();
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
  // 긴 조치 글 "이름: 순서 → 순서"(예: 6302.00 톱날 교체)는 칸엔 이름만, 고르면 아래에 번호 순서로 (사용자 요청 2026-10-22). 저장 값은 전체 글 그대로
  const split = (o: string) => { const i = o.indexOf(':'); return i > 0 && o.includes('→') ? { name: o.slice(0, i), steps: o.slice(i + 1).split('→').map((s) => s.trim()) } : null; };
  const picked = split(v.action);
  const lv = alert ? LEVEL_VIEW[alert.level] : LEVEL_VIEW['주의'];
  const names = { action: '조치', memo: '메모', parts: '사용 소모품', lock: '잠금·표지' };
  // 수정 이력에 읽을 수 있는 값으로 (소모품 = 이름 ×수량, 잠금·표지 = n/9). 바뀐 칸이 있을 때만 저장 (2026-10-20)
  const cmp = (x: SimpleRecord) => ({ ...x, parts: x.parts.map((p) => `${inv?.items.find((i) => i.item_no === p.item)?.item_name ?? p.item} ×${p.qty}`), lock: `${x.lock.filter(Boolean).length}/${LOCK.length}` }) as unknown as Record<string, unknown>;
  const changes = diff(cmp(rec), cmp(v), names);
  const setLock = (l: boolean[]) => setV((p) => (p ? { ...p, lock: l } : p));
  const src = (d: string) => { const m = d.match(/(DOC-\d+)\s+§?([\d.]+)/); return m ? <button key={d} onClick={() => openSource(m[1], m[2])} className="underline">{d}</button> : <span key={d}>{d}</span>; };

  const doConfirm = async () => {
    putSr({ ...v, state: 'confirmed', by: user.name, revisions: rev(rec.revisions, '확정', user.name, role, changes) });
    for (const p of v.parts) { try { await api('inventory/txns', { role, user_id: user.id, item_no: p.item, txn_type: 'USE', qty: p.qty, memo: `간이 작업기록 ${rec.no}` }); } catch (e) { toast((e as Error).message); } }
    if (alert) markAlert([alert.id], `${user.name} (간이 ${rec.no})`);
    if (cause) notices.filter((n) => n.rule === 'CAUSE_CHECK_REQUEST' && n.machine === rec.machine && !n.handled).forEach((n) => handleNotice(n.id, v.action));
    reloadInv();
    setNote(`처리됨 · ${MACHINES[rec.machine].name} 알람 ${rec.code}${v.parts.length ? ` · 재고 ${v.parts.length}건 차감` : ''}`);
  };

  // 시안(2026-10-20): 결론 띠 → 큰 선택 칸 → 안전(필요하면 잠금·표지 체크) → 소모품·메모는 접음
  const tone = alert?.level === '긴급' ? 'crit' : alert?.level === '참고' ? 'mute' : 'warn';
  return (
    <DocPage>
      <DocHead title={<>{cause ? '원인 점검 간이 기록' : '간이 작업기록'} <span className="font-mono">{rec.no}</span></>}
        right={<><Steps list={['입력', '확정']} cur={done ? 1 : 0} />{(role !== 'OPR' || rec.savedBy === user.name || rec.by === user.name) && <button onClick={() => go('revs', `SR:${rec.no}`)} className={BTN}>수정 이력</button>}<button onClick={back} className={BTN}>닫기</button></>} />
      <Band tone={tone}
        title={<><span style={{ color: lv.color }}>{lv.icon} {a ? sevText(a) : ''}</span> · {MACHINES[rec.machine].name} · 알람 <span className="font-mono" style={{ color: lv.color }}>{rec.code}</span> {a ? a.nameKo.replace(/\(.*\)/, '') : alarmTitle(a, rec.code)}</>}
        desc={a?.easy}
        chips={<>
          {alert && <Chip mono>{md(alert.time)} {hhmm(alert.time)} 발생</Chip>}
          <Chip tone={tone === 'crit' ? 'solid-crit' : 'solid-warn'}>처리: {cause || other ? '보전 담당자' : '작업자 · 보전 담당자'}</Chip>
          {cause && <Chip tone="warn">반복 알람 2단계 · 원인 점검</Chip>}
          {alert?.lot && <Chip mono>로트 {alert.lot}</Chip>}
          <Chip>{machineLabel(rec.machine)}</Chip>
        </>} />
      <Sec title={cause ? '한 일 고르기' : '한 조치 고르기'}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{options.map((o) => (
          <label key={o} className={`flex min-h-[52px] items-center gap-3 rounded-tile border px-3 text-card ${v.action === o ? 'border-ink bg-tile font-semibold' : 'border-line bg-white'} ${canEdit ? 'cursor-pointer' : ''}`}>
            <input type="radio" className="h-5 w-5 accent-ink" disabled={!canEdit} checked={v.action === o} onChange={() => setV((p) => (p ? { ...p, action: o } : p))} />{split(o)?.name ?? o}
            {split(o) && <span className="ml-auto rounded-full bg-tile px-2.5 py-0.5 text-small font-semibold text-ink-2">{split(o)!.steps.length}단계</span>}</label>))}</div>
        {picked && (
          <div className="mt-3 rounded-tile border border-line px-4 py-3">
            <div className="mb-2 text-small font-semibold text-ink-2">{picked.name} 순서</div>
            <ol className="flex flex-col gap-2">{picked.steps.map((s, i) => (
              <li key={i} className="flex items-start gap-2.5 text-card"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-tile text-small font-bold">{i + 1}</span>{s}</li>))}</ol>
          </div>
        )}
      </Sec>
      {!cause && a && <Sec title="안전" right={a.severity === 'STOP' ? SafeTag : undefined}><SafetyBlock machine={rec.machine} alarm={a} /></Sec>}
      {lockOn && <Sec title="잠금·표지 체크" right={<LockHead value={v.lock} onChange={setLock} disabled={!canEdit} />}><LockChecks value={v.lock} onChange={setLock} disabled={!canEdit} /></Sec>}
      <Sec title="사용 소모품 · 메모" right={<Chip>선택</Chip>}>
        <div className="flex flex-col gap-2.5">
          <PartsPicker value={v.parts} onChange={(p) => setV((x) => (x ? { ...x, parts: p } : x))} disabled={!canEdit} />
          <label className="text-small font-semibold text-ink-2">메모<textarea disabled={!canEdit} value={v.memo} onChange={(e) => setV((p) => (p ? { ...p, memo: e.target.value } : p))} rows={2} className="mt-1 w-full rounded-ctl border border-line px-3 py-2 text-card font-normal text-ink disabled:bg-tile" /></label>
        </div>
      </Sec>
      {a && <SrcFold>
        {cause ? <li>원인 점검 — 고장 대응 매뉴얼 {src('DOC-03 §1.4')} 반복 알람 2단계</li> : a.doc03.length > 0 && <li>조치 목록 — 고장 대응 매뉴얼 {a.doc03.map(src)}</li>}
        <li>알람 — 알람 코드집 {src(a.doc02)}</li>
        {!cause && safetySrc(rec.machine, a, openSource)}
      </SrcFold>}
      <Acts>
        {canEdit && <button onClick={() => { if (!changes.length) { toast('바뀐 내용 없음'); return; } putSr({ ...v, savedBy: v.savedBy ?? user.name, revisions: rev(rec.revisions, rec.revisions.length ? '수정' : '처음 저장', user.name, role, changes) }); }} className={BTN}>저장</button>}
        {canEdit && who && <button disabled={!v.action || (lockOn && lockN < LOCK.length)} onClick={() => setConfirm(true)} className={DARK}>확정</button>}
        {canEdit && !who && <Chip>확정: 보전 담당자</Chip>}
        {done && <Chip><LockIcon /> 확정 · {rec.by}</Chip>}
        {!canEdit && !done && RO}
      </Acts>
      {note && <p className="rounded-ctl bg-tile px-3 py-2 text-body font-semibold">{note}</p>}
      {confirm && <ConfirmBox title="간이 작업기록을 확정할까요?" okLabel="확정" body={`확정하면 이 알람이 처리됩니다. 사용한 소모품은 재고에서 빠집니다.`}
        onOk={() => { setConfirm(false); void doConfirm(); }} onCancel={() => setConfirm(false)} />}
    </DocPage>
  );
}
