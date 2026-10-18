'use client';
// SCR-14 정지 사유 입력·확정 — 설비가 RUN이 아닌 구간마다 사유 1개 (구간 = API-LINE-07, 시뮬레이터 상태 기록). OPR·MNT 입력, SUP 확정.
// 추천 = 시뮬레이터가 붙인 사유 코드(정지 원인) 또는 규칙. 막힘 M03·정비 P01은 자동 입력·확정.
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { STATE_VIEW, stateOf } from './data';
import { hm, md, useFetch } from './live';
import { REASONS } from './model';
import { ConfirmBox } from './Safety';
import { suggestReason } from './workflow';

interface Dt { equipment_id: string; state_code: string; start_at: string; end_at: string | null; minutes: number; reason_suggested_code: string | null; alarm_event_id: number | null }

export default function StopsScreen() {
  const { user, role, back, stopReasons, setStopReasons, connected, go, twin } = useApp();
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [machine, setMachine] = useState('');
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [confirm, setConfirm] = useState(false);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const f = useFetch<{ downtimes: Dt[] }>(connected ? 'downtimes' : null, 5000);
  const canEdit = role === 'OPR' || role === 'MNT';
  const rows = (f.data?.downtimes ?? []).map((d) => {
    const k = `${d.equipment_id}|${d.start_at}`, R = stopReasons[k];
    const auto = d.state_code === 'BLOCKED' || d.state_code === 'MAINT';
    const sug = suggestReason(d.state_code, d.reason_suggested_code);
    return { ...d, k, reason: R?.reason ?? (auto ? sug : ''), by: R?.by ?? (auto ? '자동' : undefined), confirmed: R?.confirmed ?? auto, confirmedBy: R?.confirmedBy, sug, auto };
  }).filter((r) => (!onlyOpen || !r.confirmed) && (!machine || r.equipment_id === machine)).sort((a, b) => (a.start_at < b.start_at ? 1 : -1));
  const empty = rows.filter((r) => !r.reason && !draft[r.k]).length;
  const groups = Array.from(new Set(REASONS.map((r) => r.group)));
  // 같은 추천 사유끼리 한 묶음 (사용자 요청 2026-10-16) — 순서는 가장 최근 줄이 있는 묶음부터
  const bundles = new Map<string, typeof rows>();
  rows.forEach((r) => bundles.set(r.sug || '', [...(bundles.get(r.sug || '') ?? []), r]));
  const toggle = (k: string) => setOpen((o) => { const n = new Set(o); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">정지 사유 <span className="text-[14px] font-normal text-[#9a6200]">{empty > 0 ? `▲ 사유 미입력 ${empty}건` : ''}</span> <span className="text-[13px] font-normal text-slate-500">{twin ? `${twin.shift.shift_id} 교대` : ''}</span></h2>
          <button onClick={back} className={BTN}>닫기</button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[14px]">
          <button onClick={() => setOnlyOpen(true)} className={`${BTN} ${onlyOpen ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>미확정</button>
          <button onClick={() => setOnlyOpen(false)} className={`${BTN} ${!onlyOpen ? '!border-[#0f9fbd] !bg-[#e8f6fa]' : ''}`}>전체</button>
          <label>설비 <select value={machine} onChange={(e) => setMachine(e.target.value)} className="h-11 rounded-md border border-slate-300 px-2"><option value="">전체</option>{['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'].map((m) => <option key={m}>{m}</option>)}</select></label>
        </div>
        {!f.data ? <p className="mt-4 text-slate-500">불러오는 중…</p> : rows.length === 0 ? <p className="mt-4 text-slate-500">미확정 정지 구간이 없습니다</p> : (
          <table className="mt-3 w-full text-left text-[14px]">
            {[...bundles].map(([sg, rs]) => {
              const nm = REASONS.find((x) => x.code === sg)?.name ?? '';
              const t0 = rs[rs.length - 1].start_at, same = rs.every((r) => hm(r.start_at) === hm(t0) && md(r.start_at) === md(t0));
              const machines = new Set(rs.map((r) => r.equipment_id)).size;
              const todo = rs.filter((r) => !r.confirmed && (draft[r.k] ?? r.reason) !== sg);
              const pickable = rs.filter((r) => !r.confirmed && r.reason);
              const isOpen = open.has(sg) || rs.length === 1;
              return (
            <tbody key={sg || 'none'} className="border-t-2 border-slate-200">
              {rs.length > 1 && (
                <tr className="cursor-pointer bg-slate-50" onClick={() => toggle(sg)}>
                  <td className="py-2 pl-1 text-[16px] text-slate-500">{isOpen ? '▾' : '▸'}</td>
                  <td colSpan={6} className="py-2 pr-2 text-[15px]">
                    <b>{same ? `${hm(t0)} ` : ''}{sg ? `${sg} ${nm}` : '추천 없음'}</b>
                    <span className="ml-2 text-slate-600">· {same ? `${machines}대 동시 정지` : `${rs.length}건 · 설비 ${machines}대 · ${md(t0)} ${hm(t0)}~${hm(rs[0].start_at)}`}</span>                  </td>
                  <td colSpan={2} className="py-2 pr-2 text-right" onClick={(e) => e.stopPropagation()}>
                    {canEdit && sg && todo.length > 0 && <button onClick={() => setDraft((d) => ({ ...d, ...Object.fromEntries(todo.map((r) => [r.k, sg])) }))} className={`${BTN} !h-10`}>한 번에 받아들이기 ({todo.length})</button>}
                    {role === 'SUP' && pickable.length > 0 && <button onClick={() => setPick((p) => { const n = new Set(p), all = pickable.every((r) => n.has(r.k)); pickable.forEach((r) => (all ? n.delete(r.k) : n.add(r.k))); return n; })} className={`${BTN} !h-10`}>묶음 모두 고르기 ({pickable.length})</button>}
                  </td>
                </tr>)}
              {isOpen && (
                <tr className="text-[12px] text-slate-500">{['', '설비', '구간', '길이', '상태', '사유 (입력)', '추천 (시뮬레이터·규칙)', '입력자', ''].map((h, i) => <th key={i} className={`pr-2 pt-2 pb-1 font-semibold ${i === 0 ? 'border-l-2 border-slate-300' : ''}`}>{h}</th>)}</tr>)}
              {isOpen && rs.map((r) => {
                const v = STATE_VIEW[stateOf({ state_code: r.state_code, warn_marker: false })], cur = draft[r.k] ?? r.reason;
                return (
                  <tr key={r.k} className="border-t border-slate-100 align-middle">
                    <td className="border-l-2 border-slate-300 py-1 pl-3"><input type="checkbox" className="h-5 w-5" aria-label="확정할 줄 고르기" disabled={role !== 'SUP' || r.confirmed || !r.reason} checked={pick.has(r.k)} onChange={() => setPick((p) => { const n = new Set(p); if (n.has(r.k)) n.delete(r.k); else n.add(r.k); return n; })} /></td>
                    <td className="pr-2 font-semibold">{r.equipment_id}</td>
                    <td className="pr-2">{md(r.start_at)} {hm(r.start_at)}~{r.end_at ? hm(r.end_at) : '진행 중'}</td>
                    <td className="pr-2">{r.minutes < 1 ? '1분 미만' : `${r.minutes}분`}{r.state_code === 'IDLE' && r.minutes < 5 ? ' (순간 정지)' : ''}</td>
                    <td className="pr-2" style={{ color: v.color }}>{v.icon} {v.text}</td>
                    <td className="pr-2">
                      <select disabled={!canEdit || r.confirmed} value={cur} onChange={(e) => setDraft((d) => ({ ...d, [r.k]: e.target.value }))} className="h-11 w-[180px] rounded-md border border-slate-300 px-2 disabled:bg-slate-50">
                        <option value="">사유 미입력 ▲</option>
                        {groups.map((g) => <optgroup key={g} label={g}>{REASONS.filter((x) => x.group === g).map((x) => <option key={x.code} value={x.code}>{x.code} {x.name}</option>)}</optgroup>)}
                      </select>
                    </td>
                    <td className="pr-2 text-slate-600">{r.sug ? `${r.sug} ${REASONS.find((x) => x.code === r.sug)?.name ?? ''}` : '—'}
                      {canEdit && r.sug && !r.confirmed && cur !== r.sug && <button onClick={() => setDraft((d) => ({ ...d, [r.k]: r.sug }))} className="ml-1 h-9 rounded border border-slate-300 px-2 text-[12px]">받아들이기</button>}</td>
                    <td className="pr-2 text-slate-600">{r.confirmed ? `확정 (${r.confirmedBy ?? r.by})` : r.by ?? '—'}</td>
                    <td><button onClick={() => go('replay', r.start_at)} className="h-9 rounded border border-slate-300 px-2 text-[12px]">다시 보기</button></td>
                  </tr>
                );
              })}
            </tbody>); })}
          </table>
        )}
        <p className="mt-3 text-[12px] text-slate-500">사유 코드: {groups.map((g) => `${g} ${REASONS.filter((x) => x.group === g).map((x) => x.code).join('·')}`).join(' / ')} (DOC-07 §5.1). 확정한 사유는 교대 보고서 필수 정지 칸에 쓰입니다.</p>
        <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-300 pt-3">
          {canEdit && <button disabled={Object.keys(draft).length === 0} onClick={() => { setStopReasons((p) => ({ ...p, ...Object.fromEntries(Object.entries(draft).map(([k, v]) => [k, { ...(p[k] ?? {}), reason: v, by: user.name }])) })); setDraft({}); }} className={DARK}>저장</button>}
          {role === 'SUP' && <button disabled={pick.size === 0} onClick={() => setConfirm(true)} className={DARK}>고른 줄 확정 ({pick.size})</button>}
          {role === 'MGR' && <span className="text-[14px] text-slate-500">보기 전용입니다.</span>}
        </div>
      </div>
      {confirm && <ConfirmBox title="고른 정지 사유를 확정할까요?" okLabel="확정" body="확정한 사유는 교대 보고서의 필수 정지 칸에 쓰이고, 사람만 확정할 수 있습니다."
        onOk={() => { setStopReasons((p) => ({ ...p, ...Object.fromEntries([...pick].map((k) => [k, { ...(p[k] ?? { reason: rows.find((r) => r.k === k)?.reason ?? '' }), confirmed: true, confirmedBy: user.name }])) })); setPick(new Set()); setConfirm(false); }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}
