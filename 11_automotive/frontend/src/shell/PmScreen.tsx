'use client';
// SCR-23 예방 정비 일정 — DOC-04 항목(pm_task.csv 74줄), 다음 기한(9월 실시 기록 + 주기), 기한 하루 전 ⓘ·넘김 ▲, 잠금·표지 판단(DOC-05).
// [정비 시작]·[정비 끝·실시 기록] = API-PM-02 → 시뮬레이터에 MAINT(정비) 상태로 기록 (설비 조작 버튼이 아니라 기록 버튼).
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { api, hm, md, SIM, simIso, usePersist } from './live';
import { USERS, userName } from './model';
import { PartsPicker } from './WorkRecordScreen';

type R = Record<string, any>;
const CYC: Record<string, string> = { DAILY: '매일', WEEKLY: '매주', MONTHLY: '매월', HALF_YEAR: '6개월', YEARLY: '1년', EVERY_8H_USE: '8시간 사용마다', AS_REQUIRED: '필요할 때' };
const LOCK: Record<string, string> = { FULL: '§2 전부', TWO_POINT: '보충용 2점 잠금', ONE_POINT: '1점 잠금', PLUG: '플러그 뽑기', NONE: '없음' };
const EQS = ['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'];

export function PmScreen() {
  const { pm, reloadPm, role, user, back, toast, twin, reloadInv } = useApp();
  const [eq, setEq] = useState('VF2-02');
  const [view, setView] = useState<'달력' | '목록'>('목록');
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [doneBy, setDoneBy] = useState(user.id);
  const [parts, setParts] = useState<{ item: string; qty: number }[]>([]);
  const [mins, setMins] = useState(60);
  const [ok, setOk] = usePersist<Record<string, string>>('pmOk', {}, twin?.run_id ?? null);
  if (role === 'OPR') return <div className={PAGE}><div className={CARD}>예방 정비는 작업자 메뉴에 없습니다 (작업자가 한 항목도 보전 담당자가 기록). <button onClick={back} className={BTN}>닫기</button></div></div>;
  if (!pm) return <div className={PAGE}><div className={CARD}>불러오는 중… <button onClick={back} className={BTN}>닫기</button></div></div>;
  const tasks = pm.tasks.filter((t) => t.equipment_id === eq);
  const isMaint = twin?.equipment[eq as 'VF2-01']?.state_code === 'MAINT';
  const today = simIso().slice(0, 10);
  const days = Array.from({ length: 7 }, (_, i) => simIso(SIM.now() + i * 864e5).slice(0, 10));
  const call = async (path: string, body: R, msg: string) => { try { await api(path, { role, user_id: user.id, equipment_id: eq, ...body }); toast(msg); reloadPm(); reloadInv(); } catch (e) { toast((e as Error).message); } };

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">예방 정비 일정 <span className="text-[14px] font-normal text-slate-500">· 제때 실시율 (9월) {pm.on_time_rate_pct ?? '—'}% [참고: NASA RCM 90% 이상 목표]</span></h2>
          <div className="flex flex-wrap gap-1">{EQS.map((e) => <button key={e} onClick={() => setEq(e)} className={`${BTN} ${eq === e ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>{e}</button>)}
            {(['달력', '목록'] as const).map((v) => <button key={v} onClick={() => setView(v)} className={`${BTN} ${view === v ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>{v}</button>)}<button onClick={back} className={BTN}>닫기</button></div>
        </div>
        {view === '달력' ? (
          <div className="mt-3 grid grid-cols-7 gap-1 text-[13px]">{days.map((d) => (
            <div key={d} className="min-h-[120px] rounded border border-slate-200 p-1"><b>{md(d)}</b>
              {tasks.filter((t) => t.next_due && t.next_due.slice(0, 10) === d || (d === today && t.state === 'OVERDUE')).map((t) => <div key={t.pm_task_id} className={t.state === 'OVERDUE' ? 'font-semibold text-[#9a6200]' : ''}>{t.state === 'OVERDUE' ? '▲ ' : ''}{t.item_name} ({CYC[t.cycle_code]})</div>)}
              {pm.planned_windows.filter((w) => w.equipment_id === eq && w.start_at.slice(0, 10) === d).map((w) => <div key={w.start_at} className="text-[#4b5a69]">▨ 정비 {hm(w.start_at)}~{hm(w.end_at)}</div>)}
            </div>))}</div>
        ) : (
          <table className="mt-3 w-full text-left text-[14px]">
            <thead className="text-slate-500"><tr>{['', '부위', '항목', '주기', '근거', '다음 기한', '상태', '잠금·표지', '마지막 실시'].map((h, i) => <th key={i} className="pr-2 font-semibold">{h}</th>)}</tr></thead>
            <tbody>{tasks.map((t) => (
              <tr key={t.pm_task_id} className="border-t border-slate-100">
                <td><input type="checkbox" className="h-5 w-5" disabled={role !== 'MNT'} checked={pick.has(t.pm_task_id)} onChange={() => setPick((p) => { const n = new Set(p); if (n.has(t.pm_task_id)) n.delete(t.pm_task_id); else n.add(t.pm_task_id); return n; })} /></td>
                <td className="pr-2">{t.area}</td><td className="pr-2">{t.item_name}</td><td className="pr-2">{CYC[t.cycle_code] ?? t.cycle_code}</td><td className="pr-2">[{t.source_tag === 'REAL' ? '실제' : t.source_tag === 'REFERENCE' ? '참고' : '가상'}] DOC-04 §{t.doc04_section}</td>
                <td className="pr-2">{t.next_due ? md(t.next_due) : '—'}</td>
                <td className={`pr-2 ${t.state === 'OVERDUE' ? 'font-bold text-[#9a6200]' : ''}`}>{t.state === 'OVERDUE' ? `▲ ${Math.max(1, Math.round((SIM.now() - Date.parse(t.next_due)) / 864e5))}일 지남` : t.state === 'DUE_SOON' ? 'ⓘ 기한 임박' : '—'}</td>
                <td className="pr-2">{LOCK[t.lockout_level] ?? t.lockout_level}</td><td className="pr-2 text-[13px] text-slate-600">{t.last?.done_at ? `${md(t.last.done_at)} ${userName(t.last.by)}${t.last.live ? ' (오늘)' : ''}` : '—'}</td>
              </tr>))}</tbody>
          </table>
        )}
        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">[4] 정비 시작 · 정비 끝 · 실시 기록 (MNT만) {isMaint ? '— ▨ 지금 정비 중' : ''}</h3>
          {role === 'MNT' ? (<div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">고른 항목 {pick.size}개 · 예상 <input type="number" value={mins} onChange={(e) => setMins(Number(e.target.value) || 60)} className="h-11 w-20 rounded border border-slate-300 px-1" />분
              <button disabled={isMaint} onClick={() => call('maint/pm-start', { minutes: mins, pm_task_ids: [...pick] }, `${eq} 정비 시작 — 설비 상태 정비(MAINT), 고장으로 세지 않음`)} className={DARK}>정비 시작</button></div>
            <div className="flex flex-wrap items-center gap-2">실시자 <select value={doneBy} onChange={(e) => setDoneBy(e.target.value)} className="h-11 rounded border border-slate-300">{USERS.filter((u) => u.role === 'MNT' || u.role === 'OPR').map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select> <span className="text-[12px] text-slate-500">(작업자가 한 항목이면 그 OPR을 고름 — 기록자 {user.name}은 따로 남음)</span></div>
            <PartsPicker value={parts} onChange={setParts} />
            <div><button disabled={!isMaint && pick.size === 0} onClick={() => { void call('maint/pm-end', { pm_task_ids: [...pick], done_by: doneBy, items: parts.map((p) => ({ item_no: p.item, qty: p.qty })) }, `${eq} 정비 끝 · 실시 기록 ${pick.size}건 · 소모품 차감`); setPick(new Set()); setParts([]); }} className={DARK}>정비 끝 · 실시 기록</button></div>
          </div>) : <span className="text-slate-500">보기 전용 (SUP·MGR)</span>}
        </section>
        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">오늘 실시 기록 (시뮬레이터 S6 정비는 초안 DRAFT → MNT 확인)</h3>
          {pm.today_records.length === 0 ? <p className="text-slate-500">없음</p> : <ul>{pm.today_records.map((r, i) => {
            const k = String(r.pm_record_id);
            return <li key={i} className="flex flex-wrap items-center gap-2">{r.pm_task_id} · {md(r.done_at)} {hm(r.done_at)} · {userName(r.done_by)} · {r.result} · {r.memo} · {ok[k] ? `확인됨 (${userName(ok[k])})` : r.status}
              {role === 'MNT' && !ok[k] && r.status === 'DRAFT' && <button onClick={() => setOk((o) => ({ ...o, [k]: user.id }))} className="h-9 rounded border border-slate-300 px-2 text-[12px]">확인</button>}</li>;
          })}</ul>}
        </section>
      </div>
    </div>
  );
}
