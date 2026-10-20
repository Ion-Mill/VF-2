'use client';
// SCR-02 교대 시작 브리핑(전체형: SUP·MNT·MGR) / SCR-03 요약형(OPR) — 이브 사이드바 브리핑 탭 (API-AST-01 모양).
// 지난 교대·인계 사항 = 지난 교대 보고서(생성기·서버), 먼저 챙길 일 = 인계 사항 + 지금 처리 안 된 알람·알림 (2.5 보고 순위).
// 보고 항목은 프로그램 목록이다 (순서·건수는 프로그램 몫). 지난 교대 요약은 교대 보고서 문장을 그대로 쓰므로, 비서가 켜져 있으면 비서가 다듬은 문장이 보인다.
import { useState } from 'react';
import { useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, md, type Twin } from './live';
import { LEVEL_VIEW, RANK_NAME, RANK_ORDER, alarmTitle, hhmm, type AlertRec, type Notice } from './model';

export const lastShiftReport = (reports: Record<string, any>[] | null, twin: Twin | null) =>
  reports && twin ? [...reports].filter((r) => r.shift_id < twin.shift.shift_id).sort((a, b) => (a.shift_id < b.shift_id ? -1 : 1)).pop() ?? null : null;

export const parseHandover = (t: string): { rank: string; name: string; items: string[] }[] =>
  (t || '').split(/ \/ (?=\d(?:-\d)? )/).map((part) => {
    const m = part.trim().match(/^(\d(?:-\d)?) ([^:]+): (.*)$/);
    return m ? { rank: m[1], name: m[2], items: m[3].trim() === '-' ? [] : m[3].split('; ').map((x) => x.trim()) } : null;
  }).filter(Boolean) as { rank: string; name: string; items: string[] }[];

const aText = (a: AlertRec) => `${LEVEL_VIEW[a.level].icon} ${MACHINES[a.machine].name} ${alarmTitle(a.alarm, a.code)} · ${hhmm(a.time)}부터 처리 안 됨`;
export const rankOfAlert = (a: AlertRec) => (a.level === '긴급' ? '1' : a.level === '주의' ? (SIM.now() - a.ts > 864e5 ? '0-1' : '3') : '4');
export const rankOfNotice = (n: Notice) => (n.level === '주의' && SIM.now() - n.ts > 864e5 ? '0-1' : n.rank);

// 시안 4b (사용자 선택 2026-10-20): 요약 칸 3개 → 바이올렛 '지금 할 일' 카드(완료했어요 · 방법 보기) → '그다음' 타임라인. 할 일 목록·순서는 전과 같음
type Tone = 'red' | 'amber' | 'soon';
type Todo = { key: string; text: string; sub: string; tag: string; tone: Tone; go: () => void };
const Stat = ({ k, v, tone }: { k: string; v: string; tone?: 'ok' | 'bad' }) => (
  <div className={`flex min-w-0 flex-col gap-1 rounded-2xl px-3.5 py-2.5 ${tone === 'ok' ? 'bg-[#e6f6ec]' : tone === 'bad' ? 'bg-[#fdeeee]' : 'bg-white'}`}>
    <span className={`text-[13px] ${tone === 'ok' ? 'text-[#1f7a45]' : tone === 'bad' ? 'text-[#b4282d]' : 'text-[#6b6683]'}`}>{k}</span>
    <b className={`truncate text-[20px] leading-tight ${tone === 'ok' ? 'text-[#1f7a45]' : tone === 'bad' ? 'text-[#b4282d]' : 'font-mono text-[#1f1b33]'}`}>{v}</b>
  </div>);
const HERO_TAG: Record<Tone, string> = { red: 'rounded-full bg-[#ff5d5d] px-2.5 py-0.5 text-white', amber: 'text-[#ffc65c]', soon: 'text-white/70' };
function Board({ todos, goal, lockout, footSrc, onDone, children }: { todos: Todo[]; goal: number; lockout: string[]; footSrc: string; onDone?: () => void; children?: React.ReactNode }) {
  const [done, setDone] = useState<string[]>([]); // 이 창에서만 '완료' 표시 (서버에 저장 안 함)
  const left = todos.filter((t) => !done.includes(t.key)), hero = left[0], rest = left.slice(1);
  const urgent = todos.filter((t) => t.tone === 'red').length;
  return (
    <div className="flex flex-col gap-3 text-[#1f1b33]">
      <div className="grid grid-cols-3 gap-2">
        <Stat k="할 일" v={`${left.length}건`} />
        <Stat k="목표" v={`${goal}개`} />
        {lockout.length ? <Stat k="안전" v={`잠금 ${lockout.length}대`} tone="bad" /> : urgent ? <Stat k="안전" v={`긴급 ${urgent}건`} tone="bad" /> : <Stat k="안전" v="이상 없음" tone="ok" />}
      </div>
      {lockout.length > 0 && <div className="rounded-2xl bg-[#fdecec] px-4 py-2.5 text-[14px] font-extrabold text-[#b4282d]">🔒 {lockout.join(' · ')} 잠금 중 — 전원을 넣지 마세요</div>}
      {hero ? (
        <div className="flex flex-col gap-3 rounded-3xl bg-gradient-to-br from-[#5b45d6] to-[#6d4aff] p-5 text-white shadow-[0_14px_30px_rgba(91,69,214,0.35)]">
          <div className="flex items-center justify-between gap-2 text-[14px] font-bold"><span className="text-white/85">지금 할 일 · {todos.length - left.length + 1}/{todos.length}</span><span className={`whitespace-nowrap text-[13px] font-extrabold ${HERO_TAG[hero.tone]}`}>{hero.tag}</span></div>
          <b className="text-[22px] font-extrabold leading-snug">{hero.text}</b>
          <span className="text-[14px] text-white/80">{hero.sub}</span>
          <div className="mt-1 flex gap-2">
            <button onClick={() => setDone((d) => [...d, hero.key])} className="h-12 flex-1 rounded-2xl bg-white text-[16px] font-extrabold text-[#3d2a9e]">완료했어요</button>
            <button onClick={hero.go} className="h-12 rounded-2xl bg-white/20 px-5 text-[15px] font-bold text-white hover:bg-white/30">방법 보기</button>
          </div>
        </div>
      ) : <div className="rounded-3xl bg-white px-5 py-6 text-center text-[15px] font-bold text-[#1f7a45]">✓ 오늘 챙길 일을 모두 마쳤어요</div>}
      {rest.length > 0 && (<>
        <div className="px-1 pt-1 text-[14px] font-bold text-[#4b4766]">그다음</div>
        <ol className="relative m-0 flex list-none flex-col p-0 before:absolute before:bottom-3 before:left-[15px] before:top-3 before:w-px before:bg-[#c9bdf5]">
          {rest.map((t, i) => (
            <li key={t.key}><button onClick={t.go} className="relative grid w-full grid-cols-[32px_1fr_auto] items-center gap-3 rounded-xl py-1.5 pr-2 text-left hover:bg-white/70">
              <span className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-[#9d85ff] bg-[#f3f1fb] font-mono text-[13px] font-bold text-[#3d2a9e]">{todos.length - left.length + i + 2}</span>
              <span className="min-w-0 text-[15px] leading-snug">{t.text}</span>
              {t.tone === 'red' && <span className="whitespace-nowrap text-[12px] font-extrabold text-[#d23a35]">{t.tag}</span>}{/* 시안처럼 목록은 글만, 긴급만 표시 */}
            </button></li>))}
        </ol>
      </>)}
      {children}
      <div className="flex flex-col gap-2.5 pt-1"><span className="px-1 text-[12.5px] text-[#6b6683]">근거 · {footSrc}{done.length ? ` · 이 창에서 완료 ${done.length}건 (저장 안 됨)` : ''}</span>
        {onDone && <button onClick={onDone} className="h-12 w-full rounded-full bg-[#26303a] text-[16px] font-extrabold text-white">확인했어요</button>}</div>
    </div>
  );
}
const Card = ({ t, children }: { t: React.ReactNode; children: React.ReactNode }) => <section className="rounded-2xl bg-white px-4 py-3 text-[14px]"><h4 className="m-0 mb-1 text-[14px] font-extrabold">{t}</h4>{children}</section>;
const doIt = (t: string) => (/[기다]$/.test(t) ? t : `${t}하기`); // 할 일은 동사로 끝나게

export default function Briefing({ onDone }: { onDone?: () => void }) {
  const { user, twin, alerts, myNotices, openCard, go, shiftReports, pm, wos } = useApp();
  if (!twin) return <p className="text-slate-500">데이터 없음 (연결 끊김) — 브리핑을 만들 수 없습니다.</p>;
  const last = lastShiftReport(shiftReports, twin);
  const open = alerts.filter((a) => !a.handled);
  const lockout = Object.entries(twin.equipment).filter(([, e]) => e.state_code === 'MAINT').map(([k]) => k);
  const p = twin.production;
  const pmToday = (pm?.tasks ?? []).filter((t) => t.state === 'OVERDUE' || t.state === 'DUE_SOON').filter((t) => t.cycle_code !== 'DAILY');
  const pmSorted = [...pmToday].sort((a, b) => (a.state === b.state ? 0 : a.state === 'OVERDUE' ? -1 : 1));
  const pmTodos: Todo[] = pmSorted.map((t, i) => ({ key: `pm${i}`, text: doIt(t.item_name), sub: `${t.equipment_id} · 예방 정비`, tag: t.state === 'OVERDUE' ? '▲ 기한 넘김' : '임박', tone: t.state === 'OVERDUE' ? 'amber' : 'soon', go: () => go('pm', t.equipment_id) }));
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
    return <Board todos={todos} goal={p.total_target_qty} lockout={lockout} footSrc={`교대 보고서 ${last?.shift_id ?? '없음'}${good == null ? '' : ` (지난 교대 양품 ${good}개)`} · 예방 정비 일정 · 알람 기록`} onDone={onDone} />;
  }

  // 전체형: 먼저 챙길 일 = 0 안전 → 순위대로 지금 알람·알림 + 인계 사항(지난 교대 보고서) → 예방 정비
  const base = last ? parseHandover(last.handover_text) : [];
  const todos: Todo[] = [];
  RANK_ORDER.forEach((rank) => {
    if (rank === '0' && lockout.length) todos.push({ key: 'lock', text: `잠금·표지 ${lockout.join(' · ')} 확인하기`, sub: '정비 중 · 전원 넣지 않기', tag: '안전', tone: 'red', go: () => go('line') });
    open.filter((x) => rankOfAlert(x) === rank).forEach((a) => todos.push(alarmTodo(a)));
    myNotices.filter((x) => !x.handled && x.delivery === 'LIST' && rankOfNotice(x) === rank).forEach((n) => todos.push({ key: n.id, text: n.text, sub: `${n.ruleName}${n.past ? ` · ${md(n.at)}` : ''}`, tag: n.level === '긴급' ? '긴급' : n.level === '주의' ? '▲ 주의' : '참고', tone: n.level === '긴급' ? 'red' : n.level === '주의' ? 'amber' : 'soon', go: () => (n.open ? go(n.open.screen as Parameters<typeof go>[0], n.open.key ?? null) : go('line')) }));
    (base.find((g) => g.rank === rank)?.items ?? []).filter((t) => !t.startsWith('잠금·표지 중인 설비 없음')).forEach((t, i) => todos.push({ key: `ho${rank}-${i}`, text: t, sub: `인계 · ${RANK_NAME[rank]} · 교대 보고서 ${last?.shift_id ?? ''}`, tag: '인계', tone: 'soon', go: () => last && go('shift', last.shift_id) }));
  });
  todos.push(...pmTodos);
  const notable: string = last?.notable_text ?? '';
  const sentences = notable.split(/(?<=\.)\s+/);
  const liveOrders = twin.orders.filter((o) => o.status !== 'COMPLETED');
  const liveWos = wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled');
  return (
    <Board todos={todos} goal={p.total_target_qty} lockout={lockout} footSrc={`교대 보고서 ${last?.shift_id ?? '없음'} · 알람·알림 기록 · 예방 정비 일정 (순서 = 2.5 보고 순위)`} onDone={onDone}>
      <Card t={<>지난 교대 {last ? `(${last.shift_id})` : ''} {last && <button onClick={() => go('shift', last.shift_id)} className="ml-1 text-[13px] font-normal text-[#5a3bc8] underline">교대 보고서 열기</button>}</>}>
        {!last ? <p className="m-0 text-[#6b6683]">없음</p> : (
          <ul className="m-0 list-disc pl-4 text-[#3d3955]">
            <li>양품 {good}개 · 불량 {last.defect_qty}개 · 총 목표 {last.target_qty}개 {last.status !== 'CONFIRMED' && <b className="text-[#9a6200]">ⓘ 잠정 (확정 전)</b>}</li>
            <li>{sentences.slice(1, 3).join(' ')}</li>
            <li>{sentences.slice(3).join(' ')}</li>
          </ul>)}
      </Card>
      <Card t="이번 교대 작업지시">
        <ul className="m-0 list-disc pl-4 text-[#3d3955]">
          <li>{liveOrders.map((o) => `${o.order_no}(${o.status === 'IN_PROGRESS' ? '진행 중' : '대기'}${o.delay ? ' ' + o.delay : ''})`).join(' · ') || '없음'}</li>
          {liveWos.length > 0 && <li>진행 중 작업지시서 {liveWos.map((w) => w.no).join(' · ')}</li>}
        </ul>
      </Card>
    </Board>
  );
}
