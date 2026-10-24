'use client';
// SCR-13 간이 작업기록 — 주의 등급 알람, OP-30 밖 정지 등급 알람의 짧은 기록. AI 초안이 없다: 사람이 조치를 고르고 확정한다.
// kind 'cause' = 반복 알람 2단계의 원인 점검 기록 (다른 공정, DOC-03 §1.4).
import { LockIcon } from './ui';
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { api, md, simIso } from './live';
import { ALARMS, LEVEL_VIEW, alarmTitle, hhmm, machineLabel, sevText } from './model';
import { ConfirmBox, LOCK, LockChecks, LockHead, SafeTag, SafetyBlock, needsLock, safetySrc } from './Safety';
import { PartsPicker } from './WorkRecordScreen';
import { diff, rev, URGENT, type SimpleRecord } from './workflow';
import { Acts, Band, Chip, DocHead, DocPage, printDoc, RO, Sec, SrcFold, Steps } from './DocKit';

export default function SimpleRecordScreen({ no }: { no: string }) {
  const { srs, putSr, alerts, user, role, back, markAlert, notices, handleNotice, go, toast, reloadInv, openSource, inv } = useApp();
  const rec = srs.find((r) => r.no === no);
  const [v, setV] = useState<SimpleRecord | null>(rec ?? null);
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState('');
  if (!rec || !v) return <div className={PAGE}><div className={CARD}>간이 작업기록이 없습니다 <button onClick={back} className={BTN}>닫기</button></div></div>;
  if (rec.kind === 'after') return <AfterRecord key={rec.no} rec={rec} />;
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
        right={<><Steps list={['입력', '확정']} cur={done ? 1 : 0} />{(role !== 'OPR' || rec.savedBy === user.name || rec.by === user.name) && <button onClick={() => go('revs', `SR:${rec.no}`)} className={BTN}>수정 이력</button>}<button onClick={printDoc} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button></>} />
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

// 사후 기록 (사후작업기록 초안 4.2·4.3, FR-MNT-05-16~22) — 알람 없이 먼저 한 일을 지난 시각으로 적고, 확정하면 반장이 확인해야 끝난다.
// 1차(2026-10-24): 사진·이브 메모 정리·교대 보고서 연결은 아직 없음
const AFTER_ACTS = ['칩·이물 걷어냄', '공구 점검·교체', '조임·청소', '누설·흘림 막음', '설정·조건 바꿈', '기타 → 메모']; // [가상] 알람이 없어 고장 대응 안내 조치 목록 대신 쓰는 일반 조치
function AfterRecord({ rec }: { rec: SimpleRecord }) {
  const { putSr, user, role, back, go, toast, reloadInv, inv } = useApp();
  const [v, setV] = useState<SimpleRecord>(rec);
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState('');
  const done = rec.state === 'confirmed', checked = !!rec.checkedBy;
  const canEdit = (role === 'OPR' || role === 'MNT') && !done;
  const heavy = v.lockDone === true || v.parts.length > 0;     // 잠금·표지를 했거나 부품을 쓴 일은 보전 담당만 확정 (FR-MNT-05-20)
  const who = role === 'MNT' || (role === 'OPR' && !heavy);
  const lockN = v.lock.filter(Boolean).length;
  const start = v.start ?? '', end = v.end ?? '';
  const mins = Math.round((Date.parse(end) - Date.parse(start)) / 60000);
  const [, st0, en0] = (rec.stopKey ?? '').split('|');
  const offStop = !!rec.stopKey && (start < st0 || end > en0);
  const ready = !!v.action && !!v.urgent && v.lockDone !== undefined && (v.lockDone ? lockN === LOCK.length : !!v.lockSkip?.trim()) && mins > 0;
  const written = rec.revisions[0]?.at;                         // 작성 시각 = 처음 저장 (FR-MNT-05-25, 꼬리표 없이 시각만)
  const setSet = <K extends keyof SimpleRecord>(k: K, x: SimpleRecord[K]) => setV((p) => ({ ...p, [k]: x }));
  const setTime = (k: 'start' | 'end', hm: string) => { const base = (k === 'start' ? start : end) || simIso(); setSet(k, `${base.slice(0, 11)}${hm}:00+09:00`); };
  const names = { machine: '설비', start: '작업 시작', end: '작업 끝', urgent: '급했던 이유', urgentText: '이유 한 줄', action: '한 일', memo: '메모', parts: '사용 소모품', lockDone: '잠금·표지', lock: '잠금·표지 체크', lockSkip: '안 한 이유' };
  const cmp = (x: SimpleRecord) => ({ ...x, machine: MACHINES[x.machine].name, urgent: URGENT.find(([c]) => c === x.urgent)?.[1] ?? '', lockDone: x.lockDone === undefined ? '' : x.lockDone ? '했다' : '안 했다',
    parts: x.parts.map((p) => `${inv?.items.find((i) => i.item_no === p.item)?.item_name ?? p.item} ×${p.qty}`), lock: `${x.lock.filter(Boolean).length}/${LOCK.length}` }) as unknown as Record<string, unknown>;
  const changes = diff(cmp(rec), cmp(v), names);
  const save = () => { if (!changes.length) { toast('바뀐 내용 없음'); return; } putSr({ ...v, savedBy: v.savedBy ?? user.name, revisions: rev(rec.revisions, rec.revisions.length ? '수정' : '처음 저장', user.name, role, changes) }); toast(`사후 기록 ${rec.no} 저장`); };
  const doConfirm = async () => {
    putSr({ ...v, state: 'confirmed', by: user.name, revisions: rev(rec.revisions, '확정', user.name, role, changes) });
    for (const p of v.parts) { try { await api('inventory/txns', { role, user_id: user.id, item_no: p.item, txn_type: 'USE', qty: p.qty, memo: `사후 기록 ${rec.no}` }); } catch (e) { toast((e as Error).message); } }
    reloadInv();
    setNote(`확정 · 반장 확인을 기다려요${v.parts.length ? ` · 재고 ${v.parts.length}건 차감` : ''}`);
  };
  const doCheck = () => { putSr({ ...rec, checkedBy: user.name, checkedAt: simIso(), revisions: rev(rec.revisions, '반장 확인', user.name, role) }); setNote('반장 확인 · 끝'); };
  const hm = (iso: string) => iso.slice(11, 16);
  const box = 'h-11 rounded-ctl border border-line px-3 text-card disabled:bg-tile';
  return (
    <DocPage>
      <DocHead title={<>사후 기록 <span className="font-mono">{rec.no}</span></>}
        right={<><Steps list={['입력', '확정', '반장 확인']} cur={checked ? 2 : done ? 1 : 0} />{(role !== 'OPR' || rec.savedBy === user.name || rec.by === user.name) && <button onClick={() => go('revs', `SR:${rec.no}`)} className={BTN}>수정 이력</button>}<button onClick={printDoc} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button></>} />
      <Band tone="warn" title={<>[사후] {MACHINES[v.machine].name} · 작업 <span className="font-mono">{hm(start)}~{hm(end)}</span> ({mins > 0 ? `${mins}분` : '시각 확인'})</>}
        desc="알람 없이 먼저 한 일을 지난 시각으로 적어요. 확정하면 반장이 확인해야 끝나요."
        chips={<>
          <Chip tone="warn">사후</Chip>
          <Chip mono>작업 {md(start)} {hm(start)}~{hm(end)}</Chip>
          <Chip mono>{written ? `작성 ${md(written)} ${hm(written)}` : '작성 전'}</Chip>
          <Chip tone="solid-warn">확정: {heavy ? '보전 담당자' : '작업자 · 보전 담당자'}</Chip>
          <Chip tone={checked ? 'ok' : 'mute'}>{checked ? `반장 확인 · ${rec.checkedBy}` : '반장 확인 필요'}</Chip>
        </>} />
      <Sec title="설비 · 작업 시각">
        <div className="flex flex-wrap items-center gap-3 text-card">
          {rec.stopKey || !canEdit ? <b>{MACHINES[v.machine].name}</b> : (
            <select aria-label="설비" value={v.machine} onChange={(e) => setSet('machine', e.target.value as SimpleRecord['machine'])} className={box}>
              {Object.entries(MACHINES).filter(([, x]) => x.eq).map(([id, x]) => <option key={id} value={id}>{x.name}</option>)}</select>)}
          <label className="flex items-center gap-2">시작 <input type="time" aria-label="작업 시작" disabled={!canEdit} value={hm(start)} onChange={(e) => setTime('start', e.target.value)} className={box} /></label>
          <label className="flex items-center gap-2">끝 <input type="time" aria-label="작업 끝" disabled={!canEdit} value={hm(end)} onChange={(e) => setTime('end', e.target.value)} className={box} /></label>
          {rec.stopKey && <Chip>정지 구간 {hm(st0)}~{hm(en0)}에서 열림</Chip>}
          {offStop && <Chip tone="warn">▲ 정지 구간과 달라요</Chip>}
          {mins <= 0 && <Chip tone="crit">끝이 시작보다 늦어야 해요</Chip>}
        </div>
      </Sec>
      <Sec title="급했던 이유">
        <div className="flex flex-wrap gap-2">{URGENT.map(([c, l]) => (
          <button key={c} disabled={!canEdit} onClick={() => setSet('urgent', c)} aria-pressed={v.urgent === c}
            className={`h-11 rounded-full border px-4 text-card font-semibold ${v.urgent === c ? 'border-ink bg-tile' : 'border-line bg-white text-ink-2'}`}>{l}</button>))}</div>
        <input aria-label="이유 한 줄" disabled={!canEdit} value={v.urgentText ?? ''} onChange={(e) => setSet('urgentText', e.target.value)} placeholder="한 줄 (예: 칩이 감겨 공구가 부러질 것 같았음)" className={`${box} mt-2 w-full`} />
      </Sec>
      <Sec title="한 일">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{AFTER_ACTS.map((o) => (
          <label key={o} className={`flex min-h-[52px] items-center gap-3 rounded-tile border px-3 text-card ${v.action === o ? 'border-ink bg-tile font-semibold' : 'border-line bg-white'} ${canEdit ? 'cursor-pointer' : ''}`}>
            <input type="radio" className="h-5 w-5 accent-ink" disabled={!canEdit} checked={v.action === o} onChange={() => setSet('action', o)} />{o}</label>))}</div>
        <label className="mt-2 block text-small font-semibold text-ink-2">메모<textarea disabled={!canEdit} value={v.memo} onChange={(e) => setSet('memo', e.target.value)} rows={2} placeholder="소리 나서 멈추고 칩 엉킨 거 걷어냄. 공구는 이상 없음" className="mt-1 w-full rounded-ctl border border-line px-3 py-2 text-card font-normal text-ink disabled:bg-tile" /></label>
      </Sec>
      <Sec title="잠금·표지" right={v.lockDone ? <LockHead value={v.lock} onChange={(l) => setSet('lock', l)} disabled={!canEdit} /> : undefined}>
        <div className="flex flex-wrap gap-2">
          {([[true, '했다'], [false, '안 했다']] as const).map(([b, l]) => (
            <button key={l} disabled={!canEdit} onClick={() => setSet('lockDone', b)} aria-pressed={v.lockDone === b}
              className={`h-11 rounded-full border px-4 text-card font-semibold ${v.lockDone === b ? 'border-ink bg-tile' : 'border-line bg-white text-ink-2'}`}>{l}</button>))}
        </div>
        {v.lockDone === true && <div className="mt-2"><LockChecks value={v.lock} onChange={(l) => setSet('lock', l)} disabled={!canEdit} /></div>}
        {v.lockDone === false && (
          <div className="mt-2 rounded-tile border-l-4 border-crit bg-crit-bg px-3 py-2">
            <label className="block text-small font-semibold text-crit">안 한 이유 (꼭 적어요)
              <input aria-label="잠금·표지 안 한 이유" disabled={!canEdit} value={v.lockSkip ?? ''} onChange={(e) => setSet('lockSkip', e.target.value)} placeholder="예: 도어만 열고 손은 안 넣음" className={`${box} mt-1 w-full bg-white font-normal text-ink`} /></label>
          </div>)}
      </Sec>
      <Sec title="사용 소모품" right={<Chip>선택</Chip>}>
        <PartsPicker value={v.parts} onChange={(p) => setSet('parts', p)} disabled={!canEdit} />
      </Sec>
      <Acts>
        {canEdit && <button onClick={save} className={BTN}>저장</button>}
        {canEdit && who && <button disabled={!ready} onClick={() => setConfirm(true)} className={DARK}>확정</button>}
        {canEdit && !who && <Chip>확정: 보전 담당자 (잠금·표지·부품이 있는 일)</Chip>}
        {done && !checked && role === 'SUP' && <button onClick={doCheck} className={DARK}>반장 확인</button>}
        {done && <Chip><LockIcon /> 확정 · {rec.by}</Chip>}
        {!canEdit && !done && RO}
      </Acts>
      {note && <p className="rounded-ctl bg-tile px-3 py-2 text-body font-semibold">{note}</p>}
      {confirm && <ConfirmBox title="사후 기록을 확정할까요?" okLabel="확정" body={`확정하면 반장에게 확인 요청이 가요.${v.lockDone === false ? ' 잠금·표지를 안 한 이유가 빨간 줄로 남아요.' : ''}${v.parts.length ? ' 사용한 소모품은 재고에서 빠집니다.' : ''}`}
        onOk={() => { setConfirm(false); void doConfirm(); }} onCancel={() => setConfirm(false)} />}
    </DocPage>
  );
}
