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
export const EQS = ['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'];
export const PM_ALL = '전체 장비'; // 왼쪽 메뉴의 맨 위 항목 — 6대를 한 달력·한 주간표로 본다
const WD = ['일', '월', '화', '수', '목', '금', '토'];
// 급한 순서 묶음: 0 지남 · 1 임박 · 2 이번 주 · 3 나중 · 4 기록 없음
const BUCKET = ['▲ 기한 지남', 'ⓘ 기한 임박', '이번 주', '나중', '기록 없음 · 교대 점검 등'];

// 전체 장비: [월 달력] 모든 설비의 다음 기한·정비 창 / [주간 일정] 설비 × 요일 표. 보기 전용 (기록은 설비별 화면에서).
export function PmAll() {
  const { pm, role, back } = useApp();
  const [view, setView] = useState<'달력' | '주간 일정'>('달력');
  const [off, setOff] = useState(0); // 달력은 달, 주간은 주 단위로 이동
  const [sel, setSel] = useState<string | null>(null);
  if (role === 'OPR') return <div className={PAGE}><div className={CARD}>예방 정비는 작업자 메뉴에 없습니다. <button onClick={back} className={BTN}>닫기</button></div></div>;
  if (!pm) return <div className={PAGE}><div className={CARD}>불러오는 중… <button onClick={back} className={BTN}>닫기</button></div></div>;
  const today = simIso().slice(0, 10);
  const [ty, tm, td] = today.split('-').map(Number);
  const iso = (y: number, m: number, d: number) => new Date(Date.UTC(y, m, d)).toISOString().slice(0, 10);
  const tasksOn = (d: string) => pm.tasks.filter((t) => (t.next_due && t.next_due.slice(0, 10) === d) || (d === today && t.state === 'OVERDUE')).sort((a, b) => a.equipment_id.localeCompare(b.equipment_id));
  const winsOn = (d: string) => pm.planned_windows.filter((w) => w.start_at.slice(0, 10) === d);
  const tone = (t: R) => (t.state === 'OVERDUE' ? 'font-semibold text-[#9a6200]' : t.state === 'DUE_SOON' ? 'text-[#26303a]' : 'text-slate-600');
  const mark = (t: R) => (t.state === 'OVERDUE' ? '▲ ' : t.state === 'DUE_SOON' ? 'ⓘ ' : '');
  const step = (n: number) => { setOff((o) => o + n); setSel(null); };

  const wkStart = Date.UTC(ty, tm - 1, td) - new Date(Date.UTC(ty, tm - 1, td)).getUTCDay() * 864e5 + off * 7 * 864e5; // 일요일 시작
  const wk = Array.from({ length: 7 }, (_, i) => new Date(wkStart + i * 864e5).toISOString().slice(0, 10));
  const first = new Date(Date.UTC(ty, tm - 1 + off, 1));
  const lead = first.getUTCDay(), len = new Date(Date.UTC(ty, tm + off, 0)).getUTCDate();
  const cells = Array.from({ length: Math.ceil((lead + len) / 7) * 7 }, (_, i) => (i < lead || i >= lead + len ? null : iso(first.getUTCFullYear(), first.getUTCMonth(), i - lead + 1)));
  const title = view === '달력' ? `${first.getUTCFullYear()}년 ${first.getUTCMonth() + 1}월` : `${md(wk[0])} ~ ${md(wk[6])}`;
  const selTasks = sel ? tasksOn(sel) : [], selWins = sel ? winsOn(sel) : [];

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">전체 장비 예방 정비 {view} <span className="text-[14px] font-normal text-slate-500">· {title} · 설비 {EQS.length}대 · 기한이 다음에 오는 날만 표시</span></h2>
          <div className="flex flex-wrap items-center gap-1">
            {(['달력', '주간 일정'] as const).map((v) => <button key={v} onClick={() => { setView(v); setOff(0); setSel(null); }} className={`${BTN} ${view === v ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>{v}</button>)}
            <button onClick={() => step(-1)} className={BTN}>◀</button><button onClick={() => setOff(0)} className={BTN}>오늘</button><button onClick={() => step(1)} className={BTN}>▶</button>
            <button onClick={back} className={BTN}>닫기</button>
          </div>
        </div>
        {view === '달력' ? (<>
          <div className="mt-3 grid grid-cols-7 gap-1 text-center text-[12px] font-semibold text-slate-500">{WD.map((w) => <div key={w}>{w}</div>)}</div>
          <div className="mt-1 grid grid-cols-7 gap-1 text-[11px]">{cells.map((d, i) => {
            if (!d) return <div key={i} />;
            const ts = tasksOn(d), ws = winsOn(d);
            return (
              <button key={d} onClick={() => setSel(d === sel ? null : d)} className={`min-h-[96px] rounded border p-1 text-left align-top ${d === sel ? 'border-[#0f9fbd] bg-[#e8f6fa]' : d === today ? 'border-[#0f9fbd] bg-[#f4fbfd]' : 'border-slate-200 hover:bg-slate-50'}`}>
                <b className="text-[12px]">{Number(d.slice(8))}</b>{ts.length + ws.length > 0 && <span className="ml-1 text-slate-500">{ts.length + ws.length}건</span>}
                {ts.slice(0, 3).map((t) => <div key={t.pm_task_id} className={`truncate ${tone(t)}`}>{mark(t)}{t.equipment_id} {t.item_name}</div>)}
                {ts.length > 3 && <div className="text-slate-500">+{ts.length - 3}건 더</div>}
                {ws.slice(0, 2).map((w) => <div key={w.start_at} className="truncate text-[#4b5a69]">▨ {w.equipment_id} {hm(w.start_at)}~{hm(w.end_at)}</div>)}
              </button>);
          })}</div>
          {sel && (
            <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
              <h3 className="mb-1 font-bold text-slate-500">{md(sel)} ({WD[new Date(sel).getUTCDay()]}) 전체 {selTasks.length + selWins.length}건</h3>
              {selTasks.length + selWins.length === 0 ? <p className="text-slate-500">이 날 기한인 항목이 없습니다.</p> : <ul>
                {selWins.map((w) => <li key={w.start_at} className="text-[#4b5a69]">▨ {w.equipment_id} 정비 {hm(w.start_at)}~{hm(w.end_at)}</li>)}
                {selTasks.map((t) => <li key={t.pm_task_id} className={tone(t)}>{mark(t)}{t.equipment_id} · {t.area} · {t.item_name} ({CYC[t.cycle_code] ?? t.cycle_code})</li>)}
              </ul>}
            </section>)}
        </>) : (
          <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[760px] table-fixed border-collapse text-[12px]">
            <thead><tr><th className="w-[84px] p-1 text-left text-slate-500">설비</th>{wk.map((d) => <th key={d} className={`p-1 font-semibold ${d === today ? 'bg-[#e8f6fa] text-[#0f6f86]' : 'text-slate-500'}`}>{md(d)} ({WD[new Date(d).getUTCDay()]})</th>)}</tr></thead>
            <tbody>{EQS.map((e) => (
              <tr key={e} className="border-t border-slate-200 align-top">
                <th className="p-1 text-left text-[13px]">{e}</th>
                {wk.map((d) => {
                  const ts = tasksOn(d).filter((t) => t.equipment_id === e), ws = winsOn(d).filter((w) => w.equipment_id === e);
                  return (
                    <td key={d} className={`h-[84px] border-l border-slate-100 p-1 ${d === today ? 'bg-[#f4fbfd]' : ''}`}>
                      {ws.map((w) => <div key={w.start_at} className="text-[#4b5a69]">▨ 정비 {hm(w.start_at)}~{hm(w.end_at)}</div>)}
                      {ts.map((t) => <div key={t.pm_task_id} className={tone(t)}>{mark(t)}{t.item_name} <span className="text-slate-400">({CYC[t.cycle_code] ?? t.cycle_code})</span></div>)}
                    </td>);
                })}
              </tr>))}</tbody>
          </table></div>
        )}
        <p className="mt-3 text-[12px] text-slate-500">▲ 기한 지남(오늘 칸에 표시) · ⓘ 기한 임박 · ▨ 계획된 정비 시간. 정비 시작·실시 기록은 왼쪽에서 설비를 골라 하세요.</p>
      </div>
    </div>
  );
}

export function PmScreen() {
  const { pm, reloadPm, role, user, back, toast, twin, reloadInv, key } = useApp();
  const eq = key && EQS.includes(key) ? key : 'VF2-02'; // 설비 고르기는 왼쪽 메뉴 '정비' 아래 (사용자 요청 2026-10-16)
  const [open, setOpen] = useState<Set<number>>(new Set([0, 1]));
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
          <h2 className="text-[19px] font-bold">{eq} 예방 정비 일정 <span className="text-[14px] font-normal text-slate-500">· 제때 실시율 (9월) {pm.on_time_rate_pct ?? '—'}% [참고: NASA RCM 90% 이상 목표]</span></h2>
          <div className="flex flex-wrap items-center gap-1">{(['달력', '목록'] as const).map((v) => <button key={v} onClick={() => setView(v)} className={`${BTN} ${view === v ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>{v}</button>)}<button onClick={back} className={BTN}>닫기</button></div>
        </div>
        {view === '달력' ? (
          <div className="mt-3 grid grid-cols-7 gap-1 text-[13px]">{days.map((d) => (
            <div key={d} className="min-h-[120px] rounded border border-slate-200 p-1"><b>{md(d)}</b>
              {tasks.filter((t) => t.next_due && t.next_due.slice(0, 10) === d || (d === today && t.state === 'OVERDUE')).map((t) => <div key={t.pm_task_id} className={t.state === 'OVERDUE' ? 'font-semibold text-[#9a6200]' : ''}>{t.state === 'OVERDUE' ? '▲ ' : ''}{t.item_name} ({CYC[t.cycle_code]})</div>)}
              {pm.planned_windows.filter((w) => w.equipment_id === eq && w.start_at.slice(0, 10) === d).map((w) => <div key={w.start_at} className="text-[#4b5a69]">▨ 정비 {hm(w.start_at)}~{hm(w.end_at)}</div>)}
            </div>))}</div>
        ) : (
          <table className="mt-3 w-full text-left text-[14px]">
            {BUCKET.map((label, bi) => {
              const week = days[6];
              const rs = tasks.filter((t) => (t.state === 'OVERDUE' ? 0 : t.state === 'DUE_SOON' ? 1 : !t.next_due ? 4 : t.next_due.slice(0, 10) <= week ? 2 : 3) === bi).sort((x, y) => String(x.next_due ?? '').localeCompare(String(y.next_due ?? '')));
              if (!rs.length) return null;
              const isOpen = open.has(bi);
              return (
                <tbody key={bi} className="border-t-2 border-slate-200">
                  <tr className="cursor-pointer bg-slate-50" onClick={() => setOpen((o) => { const n = new Set(o); if (n.has(bi)) n.delete(bi); else n.add(bi); return n; })}>
                    <td className="py-2 pl-1 text-[16px] text-slate-500">{isOpen ? '▾' : '▸'}</td>
                    <td colSpan={6} className={`py-2 text-[15px] font-bold ${bi === 0 ? 'text-[#9a6200]' : ''}`}>{label} <span className="font-normal text-slate-600">{rs.length}건</span></td>
                  </tr>
                  {isOpen && <tr className="text-[12px] text-slate-500">{['', '기한', '부위', '항목', '주기 · 근거', '잠금·표지', '마지막 실시'].map((h, i) => <th key={i} className={`pr-2 pt-2 pb-1 font-semibold ${i === 0 ? 'border-l-2 border-slate-300' : ''}`}>{h}</th>)}</tr>}
                  {isOpen && rs.map((t) => (
                    <tr key={t.pm_task_id} className="border-t border-slate-100">
                      <td className="border-l-2 border-slate-300 py-1.5 pl-3"><input type="checkbox" className="h-5 w-5" disabled={role !== 'MNT'} checked={pick.has(t.pm_task_id)} onChange={() => setPick((p) => { const n = new Set(p); if (n.has(t.pm_task_id)) n.delete(t.pm_task_id); else n.add(t.pm_task_id); return n; })} /></td>
                      <td className={`whitespace-nowrap pr-3 ${t.state === 'OVERDUE' ? 'font-bold text-[#9a6200]' : ''}`}>{t.state === 'OVERDUE' ? `▲ ${Math.max(1, Math.round((SIM.now() - Date.parse(t.next_due)) / 864e5))}일 지남 (${md(t.next_due)})` : t.state === 'DUE_SOON' ? `ⓘ ${md(t.next_due)}` : t.next_due ? md(t.next_due) : '—'}</td>
                      <td className="pr-2 text-slate-600">{t.area}</td><td className="pr-2 font-semibold">{t.item_name}</td>
                      <td className="pr-2 text-slate-600">{CYC[t.cycle_code] ?? t.cycle_code} · §{t.doc04_section}{t.source_tag === 'REAL' ? '' : t.source_tag === 'REFERENCE' ? ' (참고)' : ' (가상)'}</td>
                      <td className="pr-2">{t.lockout_level && t.lockout_level !== 'NONE' ? `🔒 ${LOCK[t.lockout_level] ?? t.lockout_level}` : ''}</td>
                      <td className="pr-2 text-[13px] text-slate-600">{t.last?.done_at ? `${md(t.last.done_at)} ${userName(t.last.by)}${t.last.live ? ' (오늘)' : ''}` : '—'}</td>
                    </tr>))}
                </tbody>);
            })}
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
