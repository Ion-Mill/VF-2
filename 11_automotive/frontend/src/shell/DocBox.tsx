'use client';
// SCR-18 문서함 — 작업지시서·작업기록서·간이 작업기록·교대·일일 보고서를 한곳에서 (9월 기록 + 10/1 화면에서 만든 것).
import { useState } from 'react';
import { BTN, CARD, PAGE, useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, md, tsOf } from './live';
import { LOCK } from './Safety';
import { WO_STEPS, minutesSince } from './workflow';

type Tab = '작업지시서' | '작업기록서' | '간이 작업기록' | '교대 보고서' | '일일 보고서';
const WR_LABEL = { draft: '초안', editing: '수정 중', confirmed: '확정', checked: '확인됨' } as const;

export default function DocBox() {
  const { user, role, wos, wrs, srs, alerts, openWo, openRecord, go, history, shiftReports, dailyReports, pm, key } = useApp();
  // 카테고리는 왼쪽 문서함 목록에서 고른다 (App, 페이지구조 v3) — 화면 키 = 카테고리 이름
  const tab: Tab = (['작업지시서', '작업기록서', '간이 작업기록', '교대 보고서', '일일 보고서'] as string[]).includes(key ?? '') ? (key as Tab) : '작업지시서';
  const [machine, setMachine] = useState('');
  const [code, setCode] = useState('');
  const [state, setState] = useState('');
  const [text, setText] = useState('');
  const old = (iso?: string | null) => !!iso && SIM.now() - tsOf(iso) > 864e5;

  // [1] 내 할 일 — 역할별
  const todo: { text: string; go?: () => void; warn?: boolean }[] = [];
  if (role === 'MNT') {
    wos.filter((w) => w.assignee === user.id && w.state === 'approved').forEach((w) => todo.push({ text: `▲ 승인됨 · 작업 시작 전 [${w.no}] ${MACHINES[w.machine].name} ${w.code}`, go: () => openWo(w.no), warn: true }));
    wrs.filter((r) => r.state === 'draft' || r.state === 'editing').forEach((r) => todo.push({ text: `ⓘ 작성 중 작업기록서 [${r.no}] 잠금·표지 ${LOCK.length}개 중 ${r.lock.filter(Boolean).length}개`, go: () => openRecord(r.woNo) }));
    (pm?.tasks ?? []).filter((t) => t.state === 'OVERDUE' || t.state === 'DUE_SOON').slice(0, 5).forEach((t) => todo.push({ text: `${t.state === 'OVERDUE' ? '▲ 기한 넘김' : 'ⓘ 기한 임박'} 예방 정비 ${t.equipment_id} ${t.item_name} (${md(t.next_due)})`, go: () => go('pm'), warn: t.state === 'OVERDUE' }));
    (pm?.today_records ?? []).filter((r) => r.status === 'DRAFT').forEach((r) => todo.push({ text: `ⓘ 오늘 예방 정비 (끝남) ${r.pm_task_id} — 실시 기록 확인`, go: () => go('pm') }));
  }
  if (role === 'SUP') {
    wos.filter((w) => w.state === 'draft' || w.state === 'editing').forEach((w) => { const m = minutesSince(w.created); todo.push({ text: `${m >= 120 ? '▲' : 'ⓘ'} 승인 대기 ${m}분 [${w.no}] ${MACHINES[w.machine].name} ${w.code}`, go: () => openWo(w.no), warn: m >= 120 }); });
    wrs.filter((r) => r.state === 'confirmed').forEach((r) => todo.push({ text: `ⓘ 확인 대기 작업기록서 [${r.no}]`, go: () => openRecord(r.woNo) }));
    (shiftReports ?? []).filter((r) => r.status !== 'CONFIRMED' && r.partial === false).forEach((r) => todo.push({ text: `ⓘ 미확정 교대 보고서 ${r.shift_id}`, go: () => go('shift', r.shift_id) }));
  }
  if (role === 'MGR') {
    (dailyReports ?? []).filter((r) => r.status !== 'CONFIRMED').forEach((r) => todo.push({ text: `ⓘ 미확정 일일 보고서 ${r.work_date}`, go: () => go('daily', r.work_date) }));
    todo.push({ text: 'ⓘ 사내 문서 개정 승인 대기 — 없음' });
  }

  const has = (s: string) => !text || s.includes(text);
  const pastAl = (aid: string) => history?.alarms.find((a) => a.alarm_event_id === aid);
  type Row = { key: string; cells: React.ReactNode[]; go?: () => void; date: string; warn?: boolean };
  let rows: Row[] = [];
  if (tab === '작업지시서') {
    rows = [
      ...wos.map((w) => ({ key: w.no, date: w.created, warn: (w.state === 'draft' || w.state === 'editing') && minutesSince(w.created) >= 120, go: () => openWo(w.no), st: WO_STEPS.find(([k]) => k === w.state)?.[1] ?? '취소됨', m: MACHINES[w.machine].name, c: w.code, s: `${w.title} ${w.symptom}` })),
      ...(history?.work_orders ?? []).map((w) => ({ key: w.wo_no, date: w.created_at, st: w.status === 'COMPLETED' ? '완료' : w.status, m: w.equipment_id, c: pastAl(w.alarm_event_id)?.alarm_code ?? '—', s: `${w.title} ${w.symptom}`, go: undefined, warn: false })),
    ].filter((r) => (!machine || r.m === machine) && (!code || r.c.includes(code)) && (!state || r.st === state) && has(r.s))
      .map((r) => ({ key: r.key, date: r.date, go: r.go, warn: r.warn, cells: [r.key, r.m, r.c, md(r.date), r.st, r.s.slice(0, 50)] }));
  } else if (tab === '작업기록서') {
    rows = [
      ...wrs.map((r) => { const w = wos.find((x) => x.no === r.woNo); return { key: r.no, date: w?.created ?? '', go: () => openRecord(r.woNo), st: WR_LABEL[r.state], m: w ? MACHINES[w.machine].name : '—', c: w?.code ?? '—', s: `${r.cause} ${r.action} ${r.memo}` }; }),
      ...(history?.work_records ?? []).map((r) => ({ key: r.record_no, date: r.start_at, go: undefined, st: r.status === 'CONFIRMED' ? '확정' : r.status === 'CHECKED' ? '확인됨' : r.status, m: r.equipment_id, c: pastAl(r.alarm_event_id)?.alarm_code ?? (r.record_type === 'QUICK' ? '간이' : '—'), s: `${r.cause} ${r.action} ${r.worker_memo}` })),
    ].filter((r) => (!machine || r.m === machine) && (!code || r.c.includes(code)) && (!state || r.st === state) && has(r.s))
      .map((r) => ({ key: r.key, date: r.date, go: r.go, cells: [r.key, r.m, r.c, md(r.date), r.st, `원인: ${r.s.slice(0, 40)}`] }));
  } else if (tab === '간이 작업기록') {
    rows = srs.filter((r) => role !== 'OPR' || r.savedBy === user.name || r.by === user.name || r.revisions.some((x) => x.by === user.name) || r.state === 'open')
      .map((r) => { const a = alerts.find((x) => x.id === r.alertId); return { r, a }; })
      .filter(({ r }) => (!machine || MACHINES[r.machine].name === machine) && (!code || r.code.includes(code)) && has(`${r.action} ${r.memo}`))
      .map(({ r, a }) => ({ key: r.no, date: a?.time ?? '', go: () => go('sr', r.no), cells: [r.no, MACHINES[r.machine].name, r.code, md(a?.time), r.state === 'open' ? '작성 중' : '확정', `${r.kind === 'cause' ? '[원인 점검] ' : ''}${r.action || '—'}`] }));
  } else if (tab === '교대 보고서') {
    rows = [...(shiftReports ?? [])].reverse().filter((r) => has(String(r.notable_text))).map((r) => ({ key: r.shift_id, date: r.shift_id, warn: r.status !== 'CONFIRMED' && r.partial === false && old(r.end_at), go: () => go('shift', r.shift_id),
      cells: [r.shift_id, '라인', '—', md(r.shift_id), r.status === 'CONFIRMED' ? '확정' : r.status === 'AI_DRAFT' ? 'AI비서 초안' : '수정 중', `실적 ${r.actual_qty} / 총 목표 ${r.target_qty} · 불량 ${r.defect_qty}`] }));
  } else {
    rows = [...(dailyReports ?? [])].reverse().filter((r) => has(String(r.issues_summary))).map((r) => ({ key: r.work_date, date: r.work_date, go: () => go('daily', r.work_date),
      cells: [r.work_date, '라인', '—', md(r.work_date), r.status === 'CONFIRMED' ? '확정' : 'AI비서 초안 (확정 대기)', `실적 ${r.actual_qty} / 180 · OEE ${r.oee_pct}%`] }));
  }
  const stateOpts = tab === '작업지시서' ? [...WO_STEPS.map(([, l]) => l), '취소됨'] : tab === '작업기록서' ? Object.values(WR_LABEL) : [];
  const sel = 'h-11 rounded-md border border-slate-300 px-2 text-[14px]';

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <h2 className="text-[19px] font-bold">{tab}</h2>
        <section className="mt-3 border-t border-slate-200 pt-3">
          <h3 className="mb-1 text-[14px] font-bold text-slate-500">내 할 일</h3>
          {todo.length === 0 ? <p className="text-[14px] text-slate-500">없음</p> : (
            <ul className="flex flex-col gap-1">{todo.map((t) => (
              <li key={t.text} className={`flex items-center justify-between gap-2 text-[14px] ${t.warn ? 'font-semibold text-[#9a6200]' : ''}`}><span>{t.text}</span>{t.go && <button onClick={t.go} className="h-10 shrink-0 rounded-md border border-slate-300 px-3 text-[13px] font-semibold hover:bg-slate-50">열기</button>}</li>))}</ul>
          )}
        </section>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[14px]">
          {stateOpts.length > 0 && <>상태 <select value={state} onChange={(e) => setState(e.target.value)} className={sel}><option value="">전체</option>{stateOpts.map((s) => <option key={s}>{s}</option>)}</select></>}
          설비 <select value={machine} onChange={(e) => setMachine(e.target.value)} className={sel}><option value="">전체</option>{['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'].map((m) => <option key={m}>{m}</option>)}</select>
          알람 번호 <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="992" className={`${sel} w-[110px]`} />
          비슷한 문장 찾기 <input value={text} onChange={(e) => setText(e.target.value)} placeholder="케이블" className={`${sel} w-[160px]`} />
        </div>
        {rows.length === 0 ? <p className="mt-3 text-[14px] text-slate-500">조건에 맞는 문서가 없습니다</p> : (
          <table className="mt-3 w-full text-left text-[14px]">
            <thead className="text-slate-500"><tr>{['번호', '설비', '알람', '날짜', '상태', '요약'].map((h) => <th key={h} className="pr-3 font-semibold">{h}</th>)}</tr></thead>
            <tbody>{rows.slice(0, 120).map((r) => (
              <tr key={r.key} onClick={r.go} className={`border-t border-slate-100 ${r.go ? 'cursor-pointer hover:bg-slate-50' : 'text-slate-600'} ${r.warn ? 'font-semibold text-[#9a6200]' : ''}`}>
                {r.cells.map((c, i) => <td key={i} className="py-2 pr-3">{i === 4 && r.warn ? <>▲ {c}</> : c}</td>)}
              </tr>))}</tbody>
          </table>
        )}
        <p className="mt-2 text-[12px] text-slate-500">회색 줄 = 9월 기록(생성기, 보기만). 오늘 만든 문서는 눌러서 엽니다.</p>
      </div>
    </div>
  );
}
