'use client';
// SCR-27 직원 관리 (관리자만, 2026-10-23, 요구사항 USR-01) — 명단 · 배치표(배치 바꾸기) · 직원 상세(숫자 4칸 · 최근 업무).
// 서버 = 시연 서버 /api/staff (API-USR-01~03, server_staff.py). 업무 기록은 새로 쌓지 않고 기록의 "누가" 칸을 모은 것.
// 화면에서 만든 10/1 작업지시서·작업기록서·간이 작업기록(브라우저 저장)은 서버에 없어서 여기서 수정 기록(revisions)으로 더한다.
// 근거: 화면시안/재기획/직원관리_페이지구성_초안.md, UI설계서 SCR-27
import { useState } from 'react';
import { BTN, PAGE, useApp } from './ctx';
import { Band, Btn, Chip, Empty, FIELD, Kpi, Modal, Sec, Skeleton, Tabs, TABLE, TD, TH, ROW_GO, GO_MARK } from './ui';
import { staffBand } from './bands';
import { DocHead, DocPage, printDoc } from './DocKit';
import { MASTERS } from './data';
import { api, hm, md, useFetch } from './live';
import { applyAssignments, ROLE_NAME } from './model';
import { fmtNum } from './format';
import type { Role } from './data';
import type { Screen } from './ctx';
import type { Revision } from './workflow';

interface Kp { label: string; value: number | null; unit: string }
interface U { user_id: string; user_name: string; role_code: Role; home_shift_type: 'DAY' | 'NIGHT'; home_process_code: string; home_process_code_2: string; on_shift?: boolean; kpis?: Kp[] }
interface StaffRes { period: string; from: string; to: string; shift: { shift_type: 'DAY' | 'NIGHT'; on: boolean }; users: U[] }
interface Item { at: string; text: string; screen: Screen | null; key: string | null }

const PERIODS = [{ key: 'today', label: '오늘' }, { key: '7d', label: '7일' }, { key: '30d', label: '30일' }, { key: 'sep', label: '9월 전체' }];
const PROCS = (MASTERS.processes ?? []).map((p) => [p.process_code, p.process_name]);
const SHIFT_KO = { DAY: '주간', NIGHT: '야간' } as const;
const procsOf = (u: { home_process_code: string; home_process_code_2: string }) => [u.home_process_code, u.home_process_code_2].filter(Boolean);
const inRange = (at: string | undefined, from: string) => !!at && Date.parse(at) >= Date.parse(from);

// 화면에서 만든 문서의 수정 기록 중 그 사람이 한 것 (기간 안) → 최근 업무 줄 + 숫자 칸 더하기
function localWork(name: string, uid: string, from: string, docs: { wos: { no: string; assignee: string | null; created: string; approvedBy?: string; approvedAt?: string; revisions: Revision[] }[]; wrs: { no: string; woNo: string; revisions: Revision[] }[]; srs: { no: string; revisions: Revision[] }[] }) {
  const items: Item[] = [];
  const mine = (rs: Revision[]) => rs.filter((r) => r.by === name && r.byRole !== 'PROGRAM' && inRange(r.at, from));
  docs.wos.forEach((w) => mine(w.revisions).forEach((r) => items.push({ at: r.at, text: `작업지시서 ${r.kind} · ${w.no}`, screen: 'wo', key: w.no })));
  docs.wrs.forEach((w) => mine(w.revisions).forEach((r) => items.push({ at: r.at, text: `작업기록서 ${r.kind} · ${w.no}`, screen: 'wr', key: w.woNo })));
  docs.srs.forEach((s) => mine(s.revisions).forEach((r) => items.push({ at: r.at, text: `간이 작업기록 ${r.kind} · ${s.no}`, screen: 'sr', key: s.no })));
  const add: Record<string, number> = {
    '맡은 작업지시': docs.wos.filter((w) => w.assignee === uid && inRange(w.created, from)).length,
    '작업지시 승인': docs.wos.filter((w) => w.approvedBy === name && inRange(w.approvedAt, from)).length,
    '작업기록 확정': items.filter((x) => x.screen !== 'wo' && x.text.includes(' 확정 ·')).length,
  };
  return { items, add };
}
const withLocal = (k: Kp[] | undefined, add: Record<string, number>) => (k ?? []).map((x) => (add[x.label] ? { ...x, value: (x.value ?? 0) + add[x.label] } : x));
const kpText = (k: Kp) => (k.value == null ? `${k.label} —` : `${k.label} ${fmtNum(k.value)}${k.unit}`);

export function StaffScreen() {
  const { key, role } = useApp();
  const [period, setPeriod] = useState('7d');
  if (role !== 'MGR') return <div className={PAGE}><Empty title="직원 관리는 관리자만 열 수 있어요" /></div>;
  return key ? <StaffDetail uid={key} period={period} setPeriod={setPeriod} /> : <StaffMain period={period} setPeriod={setPeriod} />;
}

function StaffMain({ period, setPeriod }: { period: string; setPeriod: (p: string) => void }) {
  const { role, user, go, toast, wos, wrs, srs } = useApp();
  const f = useFetch<StaffRes>(`staff?role=${role}&period=${period}`, 15000, [period]);
  const [tab, setTab] = useState('list');
  const [roleF, setRoleF] = useState('all');
  const [shiftF, setShiftF] = useState('all');
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState<Record<string, { shift: 'DAY' | 'NIGHT'; procs: string[] }>>({});
  const [pick, setPick] = useState<{ row: string; role: Role; shift: 'DAY' | 'NIGHT' } | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [reason, setReason] = useState('');
  if (!f.data) return <div className={PAGE}>{f.err ? <Empty title="불러오지 못했어요" desc={f.err} /> : <Skeleton />}</div>;

  const d = f.data;
  const cur = (u: U) => draft[u.user_id] ?? { shift: u.home_shift_type, procs: procsOf(u) };
  // 배치표 칸 = 그 교대에서 그 공정을 맡은 사람 (공정 5줄 · 보전 · 반장). 주의는 공정 담당 0명일 때만 (FR-USR-01-03)
  const rows: [string, string, Role][] = [...PROCS.map(([c, n]) => [c, `${c} ${n}`, 'OPR'] as [string, string, Role]), ['보전', '보전', 'MNT'], ['반장', '반장', 'SUP']];
  const cell = (row: string, r: Role, s: 'DAY' | 'NIGHT') => d.users.filter((u) => u.role_code === r && cur(u).shift === s && (r !== 'OPR' || cur(u).procs.includes(row)));
  const empty = rows.filter(([, , r]) => r === 'OPR').flatMap(([c]) => (['DAY', 'NIGHT'] as const).filter((s) => !cell(c, 'OPR', s).length).map((s) => `${SHIFT_KO[s]} ${c}`));
  const changed = d.users.filter((u) => draft[u.user_id] && (draft[u.user_id].shift !== u.home_shift_type || draft[u.user_id].procs.join() !== procsOf(u).join()));
  const onShift = d.users.filter((u) => u.on_shift).length;

  // 칸의 사람 목록에서 누르기: 작업자 = 그 공정 넣기/빼기(다른 교대면 그 사람이 이 교대로 옮김), 보전·반장 = 이 교대로 옮기기
  const toggle = (u: U) => {
    if (!pick) return;
    const c = cur(u);
    if (pick.role !== 'OPR') {
      if (c.shift === pick.shift) return toast('다른 교대 칸에서 이 교대로 옮겨 주세요');
      return setDraft((x) => ({ ...x, [u.user_id]: { ...c, shift: pick.shift } }));
    }
    if (c.shift === pick.shift && c.procs.includes(pick.row)) return setDraft((x) => ({ ...x, [u.user_id]: { ...c, procs: c.procs.filter((p) => p !== pick.row) } }));
    if (c.procs.length >= 2 && !c.procs.includes(pick.row)) return toast(`${u.user_name}: 담당 공정은 2개까지예요 — 먼저 하나를 빼 주세요`);
    setDraft((x) => ({ ...x, [u.user_id]: { shift: pick.shift, procs: c.procs.includes(pick.row) ? c.procs : [...c.procs, pick.row] } }));
  };
  const stopEdit = () => { setEdit(false); setDraft({}); setPick(null); setReason(''); };
  const save = async () => {
    setConfirm(false);
    try {
      const r = await api<{ users: (U & { home_shift_type: string })[] }>('staff/assignments', { role, user_id: user.id, reason: reason.trim() || undefined,
        changes: changed.map((u) => ({ user_id: u.user_id, home_shift_type: draft[u.user_id].shift, procs: draft[u.user_id].procs })) });
      applyAssignments(r.users);
      toast(`${changed.length}명 배치를 바꿨어요 — 수정 이력에 "직원 배치"로 남았어요`);
      stopEdit(); f.reload();
    } catch (e) { toast((e as Error).message); }   // 실패해도 고친 칸은 그대로 둔다 (다시 저장)
  };
  const desc = (u: U) => {
    const a = { shift: u.home_shift_type, procs: procsOf(u) }, b = draft[u.user_id];
    return [a.shift !== b.shift && `교대 ${SHIFT_KO[a.shift]} → ${SHIFT_KO[b.shift]}`, u.role_code === 'OPR' && a.procs.join() !== b.procs.join() && `담당 공정 ${a.procs.join('·') || '없음'} → ${b.procs.join('·') || '없음'}`].filter(Boolean).join(', ');
  };

  const shown = d.users.filter((u) => (roleF === 'all' || u.role_code === roleF) && (shiftF === 'all' || u.home_shift_type === shiftF));
  return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
        <Band spec={staffBand(onShift, d.shift.on ? SHIFT_KO[d.shift.shift_type] : null, edit ? [] : empty)} onAction={() => { setTab('board'); setEdit(true); }} />
        <div className="flex flex-wrap items-center gap-2">
          <Tabs label="직원 관리" value={tab} onChange={(t) => { setTab(t); if (t === 'list') stopEdit(); }} items={[{ key: 'list', label: '명단', count: d.users.length }, { key: 'board', label: '배치표', warn: empty.length }]} />
          {tab === 'list' && <>
            <Tabs label="역할" value={roleF} onChange={setRoleF} items={[{ key: 'all', label: '전체' }, ...(['OPR', 'MNT', 'SUP', 'MGR'] as Role[]).map((r) => ({ key: r, label: ROLE_NAME[r].replace('현장 ', '').replace('라인 ', '').replace('공장 ', '') }))]} />
            <Tabs label="교대" value={shiftF} onChange={setShiftF} items={[{ key: 'all', label: '전체' }, { key: 'DAY', label: '주간' }, { key: 'NIGHT', label: '야간' }]} />
          </>}
          <div className="ml-auto flex items-center gap-2"><span className="text-small text-ink-2">기간</span><Tabs label="기간" value={period} onChange={setPeriod} items={PERIODS} /></div>
        </div>

        {tab === 'list' ? (
          <Sec title="직원 명단" sub={`${md(d.from)} ${hm(d.from)} ~ ${md(d.to)} ${hm(d.to)} 기록 · 순위·점수 없음`}>
            <table className={TABLE}>
              <thead><tr>{['이름', '역할', '교대', '담당 공정', '지금', '기간 안 처리', ''].map((h) => <th key={h} className={TH}>{h}</th>)}</tr></thead>
              <tbody>{shown.map((u) => {
                const k = withLocal(u.kpis, localWork(u.user_name, u.user_id, d.from, { wos, wrs, srs }).add);
                return (
                  <tr key={u.user_id} className={ROW_GO} onClick={() => go('staff', u.user_id)}>
                    <td className={`${TD} font-semibold`}>{u.user_name}</td><td className={TD}>{ROLE_NAME[u.role_code]}</td><td className={TD}>{SHIFT_KO[u.home_shift_type]}</td>
                    <td className={`${TD} font-mono`}>{procsOf(u).join('·') || '—'}</td>
                    <td className={TD}>{u.on_shift ? <Chip tone="ok">● 근무</Chip> : <span className="text-ink-3">휴무</span>}</td>
                    <td className={`${TD} text-ink-2`}>{k.slice(0, 2).map(kpText).join(' · ')}</td><td className={TD}>{GO_MARK}</td>
                  </tr>);
              })}</tbody>
            </table>
          </Sec>
        ) : (
          <Sec title="담당 배치표" sub={edit ? '칸을 누르고 넣을 사람을 고르세요' : '이름을 누르면 직원 상세'}
            right={edit ? <><Btn onClick={stopEdit}>취소</Btn><Btn kind="primary" disabled={!changed.length} onClick={() => setConfirm(true)}>저장 {changed.length ? `(${changed.length}명)` : ''}</Btn></> : <Btn onClick={() => setEdit(true)}>배치 바꾸기</Btn>}>
            <table className={TABLE}>
              <thead><tr><th className={`${TH} w-[180px]`}></th><th className={TH}>주간</th><th className={TH}>야간</th></tr></thead>
              <tbody>{rows.map(([row, label, r]) => (
                <tr key={row}>
                  <td className={`${TD} font-semibold`}>{label}</td>
                  {(['DAY', 'NIGHT'] as const).map((s) => {
                    const ppl = cell(row, r, s), on = pick?.row === row && pick.shift === s;
                    return (
                      <td key={s} className={`${TD} ${edit ? 'cursor-pointer hover:bg-tile' : ''} ${on ? 'bg-brand-tint' : ''}`} onClick={() => edit && setPick({ row, role: r, shift: s })}>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {ppl.map((u) => edit ? <Chip key={u.user_id} tone={draft[u.user_id] ? 'info' : 'outline'}>{u.user_name}</Chip>
                            : <button key={u.user_id} onClick={() => go('staff', u.user_id)} className="text-body font-semibold text-ink underline-offset-2 hover:underline">{u.user_name}</button>)}
                          {!ppl.length && (r === 'OPR' ? <Chip tone="warn">▲ 담당 없음</Chip> : <span className="text-ink-3">—</span>)}
                        </div>
                      </td>);
                  })}
                </tr>))}</tbody>
            </table>
            {edit && pick && (
              <div className="mt-3 rounded-tile border border-brand-line bg-white p-3">
                <div className="mb-2 text-body font-bold">{pick.row} · {SHIFT_KO[pick.shift]} — {pick.role === 'OPR' ? '누르면 넣기·빼기 (한 사람 담당 공정 2개까지)' : '누르면 이 교대로 옮기기'}</div>
                <div className="flex flex-wrap gap-2">{d.users.filter((u) => u.role_code === pick.role).map((u) => {
                  const c = cur(u), inCell = c.shift === pick.shift && (pick.role !== 'OPR' || c.procs.includes(pick.row));
                  return <button key={u.user_id} onClick={() => toggle(u)} aria-pressed={inCell} className={`${BTN} ${inCell ? '!border-brand !bg-brand-tint !text-brand-ink' : ''}`}>{inCell ? '✓ ' : ''}{u.user_name} <span className="text-small font-normal text-ink-2">{SHIFT_KO[c.shift]}{pick.role === 'OPR' ? ` · ${c.procs.join('·') || '없음'}` : ''}</span></button>;
                })}</div>
              </div>
            )}
          </Sec>
        )}
      </div>
      {confirm && (
        <Modal title="배치를 바꿀까요?" onClose={() => setConfirm(false)} footer={<><Btn onClick={() => setConfirm(false)}>취소</Btn><span className="ml-auto" /><Btn kind="dark" onClick={save}>바꾸기</Btn></>}>
          <ul className="mb-2 flex flex-col gap-1 text-ink">{changed.map((u) => <li key={u.user_id}><b>{u.user_name}</b> — {desc(u)}</li>)}</ul>
          {empty.length > 0 && <p className="mb-2 font-semibold text-warn">▲ 바꾸면 {empty.join(' · ')} 담당이 없어요</p>}
          <label className="flex flex-col gap-1 text-body text-ink">사유 (선택)<input value={reason} onChange={(e) => setReason(e.target.value)} className={FIELD} placeholder="예: 야간 OP-30 인원 보강" /></label>
          <p className="mt-2 text-small">저장하면 바로 적용돼요. 담당 공정이 바뀐 작업자의 브리핑·담당 공정 알림도 바로 바뀌고, 수정 이력에 &quot;직원 배치&quot;로 남아요.</p>
        </Modal>
      )}
    </div>
  );
}

function StaffDetail({ uid, period, setPeriod }: { uid: string; period: string; setPeriod: (p: string) => void }) {
  const { role, go, wos, wrs, srs } = useApp();
  const f = useFetch<{ from: string; to: string; user: U; kpis: Kp[]; total: number; items: Item[] }>(`staff/${uid}/activity?role=${role}&period=${period}`, 15000, [period, uid]);
  if (!f.data) return <div className={PAGE}>{f.err ? <Empty title="불러오지 못했어요" desc={f.err} /> : <Skeleton />}</div>;
  const { user: u, from, to } = f.data;
  const loc = localWork(u.user_name, u.user_id, from, { wos, wrs, srs });
  const items = [...loc.items, ...f.data.items].sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  return (
    <DocPage width={1100}>
      <DocHead title={u.user_name} sub={`${ROLE_NAME[u.role_code]} · ${SHIFT_KO[u.home_shift_type]}${procsOf(u).length ? ` · 담당 공정 ${procsOf(u).join('·')}` : ''}`}
        right={<><button onClick={() => go('staff')} className={BTN}>← 직원 관리</button><button onClick={printDoc} className={BTN}>인쇄</button></>} />
      <div className="flex flex-wrap items-center gap-2"><span className="text-small text-ink-2">기간</span><Tabs label="기간" value={period} onChange={setPeriod} items={PERIODS} />
        <span className="text-small text-ink-2">{md(from)} {hm(from)} ~ {md(to)} {hm(to)} · 합계만 (평균·순위 없음)</span></div>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 print:grid-cols-4">{withLocal(f.data.kpis, loc.add).map((k) => <Kpi key={k.label} label={k.label} value={k.value == null ? '—' : fmtNum(k.value)} unit={k.value == null ? undefined : k.unit} />)}</div>
      <Sec title="최근 업무" sub={`${f.data.total + loc.items.length}건${items.length < f.data.total + loc.items.length ? ` 중 최근 ${items.length}건` : ''}`} empty={!items.length}>
        <ul className="flex flex-col">{items.map((x, i) => (
          <li key={i}>
            <button disabled={!x.screen} onClick={() => x.screen && go(x.screen, x.key)} className={`flex min-h-11 w-full items-center gap-3 border-t border-line-soft px-1 text-left text-body first:border-t-0 ${x.screen ? 'hover:bg-tile' : 'cursor-default'}`}>
              <span className="w-[92px] shrink-0 font-mono text-ink-2">{md(x.at)} {hm(x.at)}</span><span className="min-w-0 flex-1">{x.text}</span>{x.screen && GO_MARK}
            </button>
          </li>))}</ul>
      </Sec>
    </DocPage>
  );
}
