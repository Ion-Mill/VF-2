'use client';
// SCR-18 문서함 — 작업지시서·작업기록서·간이 작업기록·교대·일일 보고서를 한곳에서 (9월 기록 + 10/1 화면에서 만든 것).
import { useState } from 'react';
import { CARD, PAGE, useApp } from './ctx';
import { Band } from './ui';
import { docsBand } from './bands';
import { LOCK } from './Safety';
import { MACHINES } from './data';
import { SIM, md, tsOf } from './live';
import { WO_STEPS, minutesSince } from './workflow';

type Tab = '작업지시서' | '작업기록서' | '간이 작업기록' | '교대 보고서' | '일일 보고서';
// 9월 기록의 영어 상태 → 한글
const EN_ST: Record<string, string> = { DONE: '완료', COMPLETED: '완료', IN_PROGRESS: '진행 중', OPEN: '대기', CANCELLED: '취소됨', CONFIRMED: '확정', CHECKED: '확인됨' };
const stTone = (st: string) => (/초안/.test(st) ? 'bg-[#e5effe] text-[#2a55b8]' : /완료|확정|확인됨/.test(st) ? 'bg-ok-bg text-ok' : /진행|수정|작성|승인/.test(st) ? 'bg-[#e6ebff] text-[#3a4ec4]' : /취소/.test(st) ? 'bg-tile text-ink-3' : 'bg-tile text-ink-2');
function Sum({ a, b }: { a: string; b?: string }) {
  return <div className="min-w-0"><div className="truncate font-semibold text-ink">{a}</div>{b && <div className="truncate text-small text-ink-2">{b}</div>}</div>;
}
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

  // [1] 내 할 일 — 역할별. 이브 알림 탭의 문서 알림과 같은 일을 "지금 남은 일"로 모아 본다.
  // 토글로 접어 두고 머리에 개수 칩, ▲ 항목(2시간 넘은 승인 대기·기한 넘김)이 있으면 펼친 채로 시작 (2026-10-20 팀 검토)
  const todo: { text: string; go?: () => void; warn?: boolean }[] = [];
  if (role === 'MNT') {
    wos.filter((w) => w.assignee === user.id && w.state === 'approved').forEach((w) => todo.push({ text: `승인됨 · 작업 시작 전 [${w.no}] ${MACHINES[w.machine].name} ${w.code}`, go: () => openWo(w.no) }));
    wrs.filter((r) => r.state === 'draft' || r.state === 'editing').forEach((r) => todo.push({ text: `ⓘ 작성 중 작업기록서 [${r.no}] 잠금·표지 ${LOCK.length}개 중 ${r.lock.filter(Boolean).length}개`, go: () => openRecord(r.woNo) }));
    (pm?.tasks ?? []).filter((t) => t.state === 'OVERDUE' || t.state === 'DUE_SOON').sort((a, b) => Number(b.state === 'OVERDUE') - Number(a.state === 'OVERDUE')).slice(0, 5).forEach((t) => todo.push({ text: `${t.state === 'OVERDUE' ? '▲ 기한 넘김' : 'ⓘ 기한 임박'} 예방 정비 ${t.equipment_id} ${t.item_name} (${md(t.next_due)})`, go: () => go('pm'), warn: t.state === 'OVERDUE' }));
    (pm?.today_records ?? []).filter((r) => r.status === 'DRAFT').forEach((r) => todo.push({ text: `ⓘ 오늘 예방 정비 (끝남) ${r.pm_task_id} — 실시 기록 확인`, go: () => go('pm') }));
  }
  if (role === 'SUP') {
    wos.filter((w) => w.state === 'draft' || w.state === 'editing').forEach((w) => { const m = minutesSince(w.created); todo.push({ text: `${m >= 120 ? '▲' : 'ⓘ'} 승인 대기 ${m}분 [${w.no}] ${MACHINES[w.machine].name} ${w.code}`, go: () => openWo(w.no), warn: m >= 120 }); });
    wrs.filter((r) => r.state === 'confirmed').forEach((r) => todo.push({ text: `ⓘ 확인 대기 작업기록서 [${r.no}]`, go: () => openRecord(r.woNo) }));
    (shiftReports ?? []).filter((r) => r.status !== 'CONFIRMED' && r.partial === false).forEach((r) => todo.push({ text: `ⓘ 미확정 교대 보고서 ${r.shift_id}`, go: () => go('shift', r.shift_id) }));
  }
  if (role === 'MGR') {
    (dailyReports ?? []).filter((r) => r.status !== 'CONFIRMED').forEach((r) => todo.push({ text: `ⓘ 미확정 일일 보고서 ${r.work_date}`, go: () => go('daily', r.work_date) }));
  }
  const warnN = todo.filter((t) => t.warn).length;
  const has = (s: string) => !text || s.includes(text);
  const pastAl = (aid: string) => history?.alarms.find((a) => a.alarm_event_id === aid);
  type Row = { key: string; cells: React.ReactNode[]; go?: () => void; date: string; warn?: boolean };
  let rows: Row[] = [];
  if (tab === '작업지시서') {
    rows = [
      ...wos.map((w) => ({ key: w.no, date: w.created, warn: (w.state === 'draft' || w.state === 'editing') && minutesSince(w.created) >= 120, go: () => openWo(w.no), st: WO_STEPS.find(([k]) => k === w.state)?.[1] ?? '취소됨', m: MACHINES[w.machine].name, c: w.code, s: `${w.title} ${w.symptom}`, t1: w.title, t2: w.symptom })),
      ...(history?.work_orders ?? []).map((w) => ({ key: w.wo_no, date: w.created_at, st: EN_ST[w.status] ?? w.status, m: w.equipment_id, c: pastAl(w.alarm_event_id)?.alarm_code ?? '—', s: `${w.title} ${w.symptom}`, t1: w.title, t2: w.symptom, go: undefined, warn: false })),
    ].filter((r) => (!machine || r.m === machine) && (!code || r.c.includes(code)) && (!state || r.st === state) && has(r.s))
      .map((r) => ({ key: r.key, date: r.date, go: r.go, warn: r.warn, cells: [r.key, r.m, r.c, md(r.date), r.st, <Sum key="s" a={r.t1} b={r.t2} />] }));
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
      cells: [r.work_date, '라인', '—', md(r.work_date), r.status === 'CONFIRMED' ? '확정' : 'AI비서 초안 (확정 대기)', `실적 ${r.actual_qty} / ${r.target_qty ?? 180} · OEE ${r.oee_pct}%`] }));
  }
  const stateOpts = tab === '작업지시서' ? [...WO_STEPS.map(([, l]) => l), '취소됨'] : tab === '작업기록서' ? Object.values(WR_LABEL) : [];

  const today = rows.filter((r) => r.go), past = rows.filter((r) => !r.go);
  const pill = 'h-9 rounded-full border border-line bg-white px-3 text-small text-ink';
  const table = (list: Row[]) => (
    <table className="mt-2 w-full table-fixed text-left text-body">
      {/* 칸 폭: 글자 한 단계 크게(.fs-up)에 맞춤 — 알람 64px에 "5303.00" 같은 코드가 넘쳐 옆 칸으로 밀렸다 (2026-10-22). 그래도 긴 것은 … */}
      <colgroup><col className="w-[156px]" /><col className="w-[100px]" /><col className="w-[112px]" /><col className="w-[76px]" /><col className="w-[132px]" /><col /></colgroup>
      <thead className="text-small text-ink-2"><tr>{['번호', '설비', '알람', '날짜', '상태', '요약'].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr></thead>
      <tbody>{list.slice(0, 120).map((r, n) => (
        <tr key={r.key} onClick={r.go} className={`${n % 2 ? 'bg-[#f8f9fd]' : ''} ${r.go ? 'cursor-pointer hover:bg-brand-tint' : ''}`}>
          {r.cells.map((c, i) => (
            <td key={i} title={i < 4 && typeof c === 'string' ? c : undefined} className={`px-3 py-2.5 align-top ${i === 0 || i === 2 || i === 3 ? 'font-mono tabular-nums' : ''} ${i === 0 ? 'font-semibold' : ''} ${i === 5 ? 'min-w-0 break-words' : i === 4 ? '' : 'overflow-hidden text-ellipsis whitespace-nowrap'}`}>
              {i === 4 ? <span className={`inline-block rounded-full px-2.5 py-0.5 text-small font-bold ${r.warn ? 'bg-warn-bg text-warn' : stTone(String(c))}`}>{r.warn ? '▲ ' : ''}{c}</span>
                : i === 5 && typeof c === 'string' ? <Sum a={c} /> : c}
            </td>))}
        </tr>))}</tbody>
    </table>
  );

  return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
        {/* 디자인 통일 C안: "내 할 일"을 결론 띠로 (bands.ts docsBand), 목록은 아래 접기 */}
        {(() => { const first = [...todo].sort((a, b) => Number(!!b.warn) - Number(!!a.warn))[0]; return <Band spec={docsBand(todo, rows.length, first?.text.replace(/^[ⓘ▲]\s*/, ''))} onAction={() => first?.go?.()} />; })()}
        {/* [1] 내 할 일 — 토글 + 개수 칩 */}
        <details className="group rounded-card border border-line bg-white">
          <summary className="flex min-h-[48px] cursor-pointer list-none items-center gap-2 px-4 text-body font-bold">
            <span className="text-ink-2 transition group-open:rotate-90">▸</span>내 할 일 전체
            <span className={`rounded-full px-2.5 py-0.5 text-small ${warnN ? 'bg-warn-bg text-warn' : 'bg-tile text-ink-2'}`}>{todo.length}{warnN ? ` · ▲ ${warnN}` : ''}</span>
          </summary>
          <div className="px-4 pb-3">
            {todo.length === 0 ? <p className="text-body text-ink-2">없음</p> : (
              <ul className="flex flex-col gap-1.5">{[...todo].sort((a, b) => Number(!!b.warn) - Number(!!a.warn)).map((t) => (
                <li key={t.text} className={`flex items-center gap-3 rounded-tile px-3 py-2 text-body ${t.warn ? 'bg-warn-bg font-semibold text-warn' : 'bg-tile'}`}>
                  <span className="min-w-0 flex-1">{t.text}</span>
                  {t.go && <button onClick={t.go} className="h-8 shrink-0 rounded-full border border-line bg-white px-4 text-small font-semibold">열기</button>}
                </li>))}</ul>
            )}
          </div>
        </details>

        <div className={CARD.replace('mx-auto max-w-[1100px] ', '')}>
          <h2 className="text-band font-bold">{tab}</h2>
          {/* [2] 필터 — 한 줄 도구 막대 */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {stateOpts.length > 0 && <label className="flex items-center gap-1.5 text-body font-semibold text-ink-2">상태:<select value={state} onChange={(e) => setState(e.target.value)} className={pill}><option value="">전체</option>{stateOpts.map((x) => <option key={x}>{x}</option>)}</select></label>}
            <label className="flex items-center gap-1.5 text-body font-semibold text-ink-2">설비:<select value={machine} onChange={(e) => setMachine(e.target.value)} className={pill}><option value="">전체</option>{['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'].map((m) => <option key={m}>{m}</option>)}</select></label>
            <input aria-label="알람 번호" value={code} onChange={(e) => setCode(e.target.value)} placeholder="알람 번호 (예: 992)" className={`${pill} w-[150px]`} />
            <input aria-label="비슷한 문장 찾기" value={text} onChange={(e) => setText(e.target.value)} placeholder="비슷한 문장 찾기 (예: 케이블)" className={`${pill} w-[220px]`} />
            <span className="ml-auto text-small font-semibold text-ink-2">{rows.length}건</span>
          </div>
          {/* [3] 표 — 오늘 만든 문서 / 지난 기록 */}
          {rows.length === 0 ? <p className="mt-4 text-body text-ink-2">조건에 맞는 문서가 없습니다</p> : (<>
            {today.length > 0 && <>{past.length > 0 && <h3 className="mt-4 text-small font-bold text-ink-2">오늘 만든 문서 · 눌러서 열기</h3>}{table(today)}</>}
            {past.length > 0 && <><h3 className="mt-4 text-small font-bold text-ink-2">지난 기록 (보기만)</h3>{table(past)}</>}
          </>)}
        </div>
      </div>
    </div>
  );
}
