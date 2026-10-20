'use client';
// SCR-02 교대 시작 브리핑(전체형: SUP·MNT·MGR) / SCR-03 요약형(OPR) — 이브 사이드바 브리핑 탭 (API-AST-01 모양).
// 지난 교대·인계 사항 = 지난 교대 보고서(생성기·서버), 먼저 챙길 일 = 인계 사항 + 지금 처리 안 된 알람·알림 (2.5 보고 순위).
// 보고 항목은 프로그램 목록이다 (순서·건수는 프로그램 몫). 지난 교대 요약은 교대 보고서 문장을 그대로 쓰므로, 비서가 켜져 있으면 비서가 다듬은 문장이 보인다.
// 먼저 챙길 일의 항목 문장은 비서가 다듬은 것이 준비되면 그것을 보이고(순위 묶음별, '비서 정리'), 준비 전·꺼짐·실패·탈락은 프로그램 문구 그대로다. [원문 보기]로 언제나 프로그램 문구를 본다 (팀 2026-10-19, 기본 꺼짐 NEXT_PUBLIC_MOM_BRIEFING_LLM=1). 4b 카드에 붙임 (2026-10-20)
import { useEffect, useRef, useState } from 'react';
import { backendChatEnabled, fetchBriefChecks, saveBriefCheck } from './assistantApi';
import { checkScope, fromServerKeys, serverKey, serverShift, toggleKey } from './briefChecks';
import { useBriefingText } from './assistText';
import { useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, hm, md, simIso, usePersist, type Twin } from './live';
import { LEVEL_VIEW, RANK_NAME, RANK_ORDER, alarmTitle, hhmm, type AlertRec, type Notice } from './model';

export const lastShiftReport = (reports: Record<string, any>[] | null, twin: Twin | null) =>
  reports && twin ? [...reports].filter((r) => r.shift_id < twin.shift.shift_id).sort((a, b) => (a.shift_id < b.shift_id ? -1 : 1)).pop() ?? null : null;

export const parseHandover = (t: string): { rank: string; name: string; items: string[] }[] =>
  (t || '').split(/ \/ (?=\d(?:-\d)? )/).map((part) => {
    const m = part.trim().match(/^(\d(?:-\d)?) ([^:]+): (.*)$/);
    return m ? { rank: m[1], name: m[2], items: m[3].trim() === '-' ? [] : m[3].split('; ').map((x) => x.trim()) } : null;
  }).filter(Boolean) as { rank: string; name: string; items: string[] }[];

const noticeLine = (n: Notice) => `[${n.ruleName}] ${n.text}${n.past ? ` · ${md(n.at)}` : ''}`;
const aText = (a: AlertRec) => `${LEVEL_VIEW[a.level].icon} ${MACHINES[a.machine].name} ${alarmTitle(a.alarm, a.code)} · ${hhmm(a.time)}부터 처리 안 됨`;
export const rankOfAlert = (a: AlertRec) => (a.level === '긴급' ? '1' : a.level === '주의' ? (SIM.now() - a.ts > 864e5 ? '0-1' : '3') : '4');
export const rankOfNotice = (n: Notice) => (n.level === '주의' && SIM.now() - n.ts > 864e5 ? '0-1' : n.rank);

// 이브 브리핑 G안 (사용자 선택 2026-10-20, 캔버스 'MOM 비서AI 플로팅 시안' 7번 페이지): 맨 위 작게 = 이번 교대 목표 · 지난 교대, 나머지 = '먼저 챙길 일' 체크박스.
// 할 일 목록·순서·비서 정리·바로가기는 전(시안 4b)과 같음. 4b 카드·타임라인 코드는 구현_중_수정사항/백업_1020_이브패널/Briefing.tsx
type Tone = 'red' | 'amber' | 'soon';
type Todo = { key: string; text: string; sub: string; tag: string; tone: Tone; go: () => void };
type Summary = {
  shift: string; asOf: string; target: number; carry: number; orders: number; pm: number;
  last: { label: string; good: number | null; target: number; defect: number; confirmed: boolean } | null;
};
const TAG_COLOR: Record<Tone, string> = { red: 'text-[#b4282d]', amber: 'text-[#9a5b00]', soon: 'text-[#6b6683]' };
const SUM_BOX = 'flex min-w-0 flex-col gap-0.5 rounded-2xl border border-[#e4def8] bg-[#ffffff] px-3.5 py-2.5';
const SUM_LABEL = 'whitespace-nowrap text-[12.5px] font-bold text-[#6b6683]';
const SUM_NOTE = 'text-[12.5px] leading-snug text-[#4b4766]';
type CheckBase = { userId: string; shiftId: string; runId: number | null };
function Board({ todos, sum, lockout, footSrc, onDone, onOpenLast, aiNote, check }: { todos: Todo[]; sum: Summary; lockout: string[]; footSrc: string; onDone?: () => void; onOpenLast?: () => void; aiNote?: React.ReactNode; check: CheckBase }) {
  // 체크 저장 (2026-10-20): 이 브라우저(시연 회차별)에 늘 남기고, 백엔드가 있으면 같이 보낸다. 열 때 서버 값이 오면 서버 것을 따른다 (briefChecks.ts)
  const { userId, shiftId, runId } = check;
  const scope = checkScope(userId, shiftId);
  const [store, setStore] = usePersist<Record<string, string[]>>('briefChecks', {}, runId);
  const done = store[scope] ?? [];
  const touched = useRef(false); // 이 창에서 이미 눌렀으면 늦게 온 서버 값으로 덮지 않는다
  useEffect(() => {
    touched.current = false;
    if (!backendChatEnabled() || runId === null) return;
    let live = true;
    fetchBriefChecks(userId, serverShift(runId, shiftId)).then((keys) => {
      if (!live || touched.current || keys === null) return;
      setStore((s) => ({ ...s, [scope]: fromServerKeys(runId, keys) }));
    });
    return () => { live = false; };
  }, [userId, shiftId, runId]); // eslint-disable-line react-hooks/exhaustive-deps
  const isDone = (t: Todo) => done.includes(t.key);
  const open = todos.filter((t) => !isDone(t)), fin = todos.filter(isDone);
  const red = open.filter((t) => t.tone === 'red').length, amber = open.filter((t) => t.tone === 'amber').length;
  const toggle = (k: string) => {
    touched.current = true;
    const turnOn = !done.includes(k);
    setStore((s) => ({ ...s, [scope]: toggleKey(s[scope] ?? [], k) }));
    void saveBriefCheck(userId, serverShift(runId, shiftId), serverKey(runId, k), turnOn); // 서버 저장은 실패해도 조용히 (브라우저에는 남음)
  };
  return (
    <div className="flex flex-col gap-2.5 text-[#1f1b33]">
      <p className="m-0 px-0.5 text-[13.5px] text-[#6b6683]"><b className="text-[#1f1b33]">{sum.shift}</b> · <span className="font-mono">{sum.asOf}</span> 기준</p>
      <div className="grid grid-cols-2 gap-2">
        <div className={SUM_BOX}>
          <span className={SUM_LABEL}>이번 교대 목표</span>
          <b className="font-mono text-[18px] leading-tight">{sum.target}개</b>
          <span className={SUM_NOTE}>이월 {sum.carry} · 작업지시 {sum.orders}<br />예방 정비 {sum.pm}</span>
        </div>
        <div className={SUM_BOX}>
          <span className={SUM_LABEL}>지난 교대{sum.last && ` · ${sum.last.label}`}</span>
          {sum.last ? (<>
            <span className="flex items-center gap-1.5"><b className="font-mono text-[18px] leading-tight">{sum.last.good ?? '—'} / {sum.last.target}</b><span className="whitespace-nowrap rounded-md bg-[#f0edf9] px-1.5 text-[11.5px] font-bold text-[#4b4766]">{sum.last.confirmed ? '확정' : '잠정'}</span></span>
            <span className={SUM_NOTE}>양품 · 불량 {sum.last.defect}<br />{onOpenLast && <button onClick={onOpenLast} className="font-semibold text-[#5a3bc8] underline">보고서 열기</button>}</span>
          </>) : <span className={SUM_NOTE}>보고서 없음</span>}
        </div>
      </div>
      {lockout.length > 0 && <div className="rounded-2xl bg-[#fdecec] px-4 py-2.5 text-[14px] font-extrabold text-[#b4282d]">🔒 {lockout.join(' · ')} 잠금 중 — 전원을 넣지 마세요</div>}
      <div className="flex flex-wrap items-baseline gap-x-2 px-0.5 pt-1.5">
        <h3 className="m-0 text-[19px] font-extrabold">먼저 챙길 일 {open.length}</h3>
        <span className="text-[13.5px] text-[#6b6683]">긴급 {red} · 주의 {amber} · 끝낸 일 {fin.length}</span>
      </div>
      {todos.length === 0 && <div className="rounded-2xl bg-[#ffffff] px-5 py-6 text-center text-[15px] font-bold text-[#1f7a45]">✓ 오늘 챙길 일이 없어요</div>}
      {[...open, ...fin].map((t) => {
        const d = isDone(t);
        return (
          <div key={t.key} className={`flex items-center gap-2 rounded-2xl border border-[#e4def8] pr-2.5 ${d ? 'bg-[#efedf5]' : 'bg-[#ffffff]'}`}>
            <label className="flex min-h-[64px] min-w-0 flex-1 cursor-pointer items-center gap-3.5 py-2 pl-3.5 pr-1">
              <input type="checkbox" checked={d} onChange={() => toggle(t.key)} className="h-[26px] w-[26px] shrink-0 accent-[#26303a]" />
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className={`text-[16px] font-extrabold leading-snug ${d ? 'text-[#8a879a] line-through' : ''}`}>{t.text}</span>
                <span className="text-[13px] leading-snug text-[#6b6683]"><b className={d ? '' : TAG_COLOR[t.tone]}>{t.tag}</b>{t.sub.startsWith(`${t.tag} · `) ? t.sub.slice(t.tag.length) : ` · ${t.sub}`}</span>
              </span>
            </label>
            {!d && <button onClick={t.go} className="h-11 shrink-0 rounded-xl border border-[#26303a] bg-[#ffffff] px-3.5 text-[15px] font-extrabold text-[#1f1b33] hover:bg-[#f3f1fb]">보기</button>}
          </div>
        );
      })}
      <div className="flex flex-col gap-2.5 pt-1"><span className="px-1 text-[12.5px] text-[#6b6683]">{aiNote}근거 · {footSrc}{done.length ? ` · 체크 ${done.length}건 저장됨` : ''}</span>
        {onDone && <button onClick={onDone} className="h-12 w-full rounded-full bg-[#26303a] text-[16px] font-extrabold text-white">확인했어요</button>}</div>
    </div>
  );
}
const shiftName = (id: string) => `${md(id)} ${id.endsWith('-N') ? '야간' : '주간'}`;
const summaryOf = (twin: Twin, last: Record<string, any> | null, good: number | null, pmCount: number): Summary => ({
  shift: `${md(twin.shift.start_at)} ${twin.shift.shift_type === 'NIGHT' ? '야간' : '주간'} ${hm(twin.shift.start_at)}–${hm(twin.shift.end_at)}`,
  asOf: hm(simIso()),
  target: twin.production.total_target_qty, carry: twin.production.carry_over_qty,
  orders: twin.orders.filter((o) => o.status !== 'COMPLETED').length, pm: pmCount,
  last: last ? { label: shiftName(String(last.shift_id)), good, target: Number(last.target_qty), defect: Number(last.defect_qty), confirmed: last.status === 'CONFIRMED' } : null,
});
const doIt = (t: string) => (/[기다]$/.test(t) ? t : `${t}하기`); // 할 일은 동사로 끝나게

export default function Briefing({ onDone }: { onDone?: () => void }) {
  const { user, twin, alerts, openCard, go, shiftReports, pm } = useApp();
  if (!twin) return <p className="text-slate-500">데이터 없음 (연결 끊김) — 브리핑을 만들 수 없습니다.</p>;
  const last = lastShiftReport(shiftReports, twin);
  const open = alerts.filter((a) => !a.handled);
  const lockout = Object.entries(twin.equipment).filter(([, e]) => e.state_code === 'MAINT').map(([k]) => k);
  const p = twin.production;
  const pmToday = (pm?.tasks ?? []).filter((t) => t.state === 'OVERDUE' || t.state === 'DUE_SOON').filter((t) => t.cycle_code !== 'DAILY');
  const pmSorted = [...pmToday].sort((a, b) => (a.state === b.state ? 0 : a.state === 'OVERDUE' ? -1 : 1));
  const pmTodos: Todo[] = pmSorted.map((t, i) => ({ key: `pm:${t.pm_task_id ?? i}`, text: doIt(t.item_name), sub: `${t.equipment_id} · 예방 정비`, tag: t.state === 'OVERDUE' ? '▲ 기한 넘김' : '임박', tone: t.state === 'OVERDUE' ? 'amber' : 'soon', go: () => go('pm', t.equipment_id) }));
  const good = last ? Number(last.actual_qty) - Number(last.defect_qty) : null;
  const alarmTodo = (a: AlertRec): Todo => ({ key: a.id, text: `${a.alarm?.nameKo.replace(/\s*\([A-Z0-9 ._/-]+\)/, '') ?? a.code} 대응하기`, sub: `${MACHINES[a.machine].name} · 알람 ${a.code} · ${hhmm(a.time)}부터`, tag: a.level === '긴급' ? '긴급' : '▲ 주의', tone: a.level === '긴급' ? 'red' : 'amber', go: () => openCard(a.id) });

  if (user.role === 'OPR') {
    const mine = open.filter((a) => user.procs.includes(MACHINES[a.machine].op)).sort((a, b) => rankOfAlert(a).localeCompare(rankOfAlert(b)) || a.ts - b.ts);
    const tools = Object.values(twin.equipment).filter((e) => user.procs.includes(e.process_code)).flatMap((e) => e.tools).filter((t) => t.warn);
    const todos: Todo[] = [
      ...mine.map(alarmTodo),
      ...tools.map((t, i): Todo => ({ key: `tool${i}`, text: `${t.tool_id} 공구 교체 준비하기`, sub: `수명 ${t.usage_pct}%`, tag: '▲ 공구', tone: 'amber', go: () => go('tools') })),
      ...pmTodos,
    ];
    return <Board todos={todos} sum={summaryOf(twin, last, good, pmTodos.length)} lockout={lockout} footSrc={`교대 보고서 ${last?.shift_id ?? '없음'} · 예방 정비 일정 · 알람 기록`} onDone={onDone} onOpenLast={last ? () => go('shift', last.shift_id) : undefined} check={{ userId: user.id, shiftId: twin.shift.shift_id, runId: twin.run_id }} />;
  }

  return <FullBrief v={{ twin, last, open, lockout, p, pmTodos, good, alarmTodo }} onDone={onDone} />;
}

type FullView = { twin: Twin; last: Record<string, any> | null; open: AlertRec[]; lockout: string[]; p: Twin['production']; pmTodos: Todo[]; good: number | null; alarmTodo: (a: AlertRec) => Todo };

// 전체형 (SUP·MNT·MGR): 먼저 챙길 일 = 0 안전 → 순위대로 지금 알람·알림 + 인계 사항(지난 교대 보고서) → 예방 정비. 비서 정리 훅을 부르려고 따로 뺐다
function FullBrief({ v, onDone }: { v: FullView; onDone?: () => void }) {
  const { user, myNotices, notices, go } = useApp();
  const { twin, last, open, lockout, pmTodos, good, alarmTodo } = v;
  const base = last ? parseHandover(last.handover_text) : [];
  const shown = myNotices.filter((x) => !x.handled && x.delivery === 'LIST');
  // 겹치는 줄 빼기 (2026-10-20): 인계 사항 중 ① 지금 알림으로 보이거나 이미 처리된 알림과 같은 줄 ② 기한이 지난 "기한 하루 전" 줄,
  // 예방 정비 일정 중 ③ 지금 예방 정비 알림으로 보이는 항목. 같은 일이 알림·인계·일정으로 서너 번 나오던 것
  const same = (t: string) => { const s = t.replace(/\s*\(24시간 넘게 처리 안 됨\)$/, '').trim(); return notices.some((n) => (n.handled || shown.includes(n)) && n.text.trim() === s); };
  const today = simIso().slice(0, 10);
  const staleSoon = (t: string) => { const m = t.match(/기한 하루 전 \(기한 (\d{2})\/(\d{2})\)/); return !!m && `${today.slice(0, 4)}-${m[1]}-${m[2]}` < today; };
  const pmShown = new Set(shown.filter((n) => n.rule.startsWith('PM_')).flatMap((n) => n.keys ?? (n.rule === 'PM_OVERDUE' ? [n.id.slice('PM_OVERDUE:'.length)] : [])));
  const groups = RANK_ORDER.map((rank) => ({ rank,
    a: open.filter((x) => rankOfAlert(x) === rank),
    n: shown.filter((x) => rankOfNotice(x) === rank),
    base: (base.find((g) => g.rank === rank)?.items ?? []).flatMap((t) => t.split(/ \/ (?=추가: )/)) // 맨 끝 "/ 추가: …"가 앞 줄에 붙어 오므로 떼어 따로 둔다
      .filter((t) => !t.startsWith('잠금·표지 중인 설비 없음') && !same(t) && !staleSoon(t)) }));
  // 비서 정리: 순위 묶음별 항목 줄 (알람 → 알림 → 인계, 팀 원문 모양 그대로). 안전(순위 0)은 보내지 않는다
  const aiGroups = groups.filter((g) => g.rank !== '0').map((g) => ({ rank: g.rank, lines: [...g.a.map(aText), ...g.n.map(noticeLine), ...g.base] })).filter((g) => g.lines.length);
  const ai = useBriefingText(twin.shift.shift_id, aiGroups);
  const [raw, setRaw] = useState(false);
  const hasAi = aiGroups.some((g) => ai[g.rank]?.some((t, i) => t !== g.lines[i])); // 원문과 다른 비서 정리가 하나라도 있을 때만 꼬리표·전환 버튼
  const pick = (rank: string, i: number, orig: string, mine: string) => { const t = ai[rank]?.[i]; return !raw && t && t !== orig ? t : mine; }; // 비서 문장이 있으면 카드 제목으로, 없으면 4b 짧은 문구
  const todos: Todo[] = [];
  groups.forEach(({ rank, a: as, n: ns, base: bs }) => {
    if (rank === '0' && lockout.length) todos.push({ key: 'lock', text: `잠금·표지 ${lockout.join(' · ')} 확인하기`, sub: '정비 중 · 전원 넣지 않기', tag: '안전', tone: 'red', go: () => go('line') });
    as.forEach((a, i) => { const t = alarmTodo(a); todos.push({ ...t, text: pick(rank, i, aText(a), t.text) }); });
    ns.forEach((n, i) => todos.push({ key: n.id, text: pick(rank, as.length + i, noticeLine(n), n.text), sub: `${n.ruleName}${n.past ? ` · ${md(n.at)}` : ''}`, tag: n.level === '긴급' ? '긴급' : n.level === '주의' ? '▲ 주의' : '참고', tone: n.level === '긴급' ? 'red' : n.level === '주의' ? 'amber' : 'soon', go: () => (n.open ? go(n.open.screen as Parameters<typeof go>[0], n.open.key ?? null) : go('line')) }));
    bs.forEach((t, i) => todos.push({ key: `ho${rank}-${i}`, text: pick(rank, as.length + ns.length + i, t, t), sub: `인계 · ${RANK_NAME[rank]} · 교대 보고서 ${last?.shift_id ?? ''}`, tag: '인계', tone: 'soon', go: () => last && go('shift', last.shift_id) }));
  });
  todos.push(...pmTodos.filter((t) => !pmShown.has(t.key.slice('pm:'.length))));
  return (
    <Board todos={todos} sum={summaryOf(twin, last, good, pmTodos.length)} lockout={lockout} footSrc={`교대 보고서 ${last?.shift_id ?? '없음'} · 알람·알림 기록 · 예방 정비 일정 (순서 = 2.5 보고 순위)`} onDone={onDone}
      onOpenLast={last ? () => go('shift', last.shift_id) : undefined} check={{ userId: user.id, shiftId: twin.shift.shift_id, runId: twin.run_id }}
      aiNote={hasAi && <><b>{raw ? '원문' : '비서 정리'}</b> <button onClick={() => setRaw((x) => !x)} title="프로그램 문구와 비서가 다듬은 문장을 바꿔 봅니다" className="underline">{raw ? '비서 정리 보기' : '원문 보기'}</button> · </>} />
  );
}
