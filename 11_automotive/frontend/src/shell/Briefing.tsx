'use client';
// SCR-02 교대 시작 브리핑(전체형: SUP·MNT·MGR) / SCR-03 요약형(OPR) — 이브 사이드바 브리핑 탭 (API-AST-01 모양).
// 지난 교대·인계 사항 = 지난 교대 보고서(생성기·서버), 먼저 챙길 일 = 인계 사항 + 지금 처리 안 된 알람·알림 (2.5 보고 순위).
// 보고 항목은 프로그램 목록이다 (순서·건수는 프로그램 몫). 지난 교대 요약은 교대 보고서 문장을 그대로 쓰므로, 비서가 켜져 있으면 비서가 다듬은 문장이 보인다.
// 먼저 챙길 일의 항목 문장은 비서가 다듬은 것이 준비되면 그것을 보이고(순위 묶음별, '비서 정리'), 준비 전·꺼짐·실패·탈락은 프로그램 문구 그대로다. [원문 보기]로 언제나 프로그램 문구를 본다 (2026-10-19). 순서·건수·순위 이름은 프로그램 것이다.
import { useContext, useState } from 'react';
import { useApp } from './ctx';
import { EveSnap, Robot } from './Eve';
import { MACHINES } from './data';
import { SIM, md, type Twin } from './live';
import { useBriefingText } from './assistText';
import { LEVEL_VIEW, RANK_NAME, RANK_ORDER, alarmTitle, hhmm, type AlertRec, type Notice } from './model';

export const lastShiftReport = (reports: Record<string, any>[] | null, twin: Twin | null) =>
  reports && twin ? [...reports].filter((r) => r.shift_id < twin.shift.shift_id).sort((a, b) => (a.shift_id < b.shift_id ? -1 : 1)).pop() ?? null : null;

export const parseHandover = (t: string): { rank: string; name: string; items: string[] }[] =>
  (t || '').split(/ \/ (?=\d(?:-\d)? )/).map((part) => {
    const m = part.trim().match(/^(\d(?:-\d)?) ([^:]+): (.*)$/);
    return m ? { rank: m[1], name: m[2], items: m[3].trim() === '-' ? [] : m[3].split('; ').map((x) => x.trim()) } : null;
  }).filter(Boolean) as { rank: string; name: string; items: string[] }[];

const aText = (a: AlertRec) => `${LEVEL_VIEW[a.level].icon} ${MACHINES[a.machine].name} ${alarmTitle(a.alarm, a.code)} · ${hhmm(a.time)}부터 처리 안 됨`;
const noticeLine = (n: Notice) => `[${n.ruleName}] ${n.text}${n.past ? ` · ${md(n.at)}` : ''}`;
export const rankOfAlert = (a: AlertRec) => (a.level === '긴급' ? '1' : a.level === '주의' ? (SIM.now() - a.ts > 864e5 ? '0-1' : '3') : '4');
export const rankOfNotice = (n: Notice) => (n.level === '주의' && SIM.now() - n.ts > 864e5 ? '0-1' : n.rank);

// 시안 D (사용자 선택 2026-10-18): 흰 종이 한 장 — 진한 결론 띠 → 이상 없음 한 줄 → 오늘 할 일 번호 목록 → 목표 → 근거·확인
type Tone = 'red' | 'amber' | 'soon';
type Todo = { key: string; text: string; sub: string; tag: string; tone: Tone; go: () => void };
const TONE: Record<Tone, { row: string; num: string; tag: string }> = {
  red: { row: 'bg-[#fdeeee] shadow-[inset_4px_0_0_#d23a35]', num: 'border-[#d23a35] text-[#b4282d]', tag: 'bg-[#d23a35] text-white' },
  amber: { row: 'bg-[#fff8e6] shadow-[inset_4px_0_0_#f0b429]', num: 'border-[#f0b429] text-[#8a5a00]', tag: 'bg-[#f0b429] text-[#3d2a00]' },
  soon: { row: '', num: 'border-[#c3c9cf] text-[#5b6570]', tag: 'border border-[#d3d7dc] text-[#4b5560]' },
};
const Sheet = ({ children }: { children: React.ReactNode }) => <div className="flex flex-col overflow-hidden rounded-2xl border border-[#dde1e5] bg-white text-[15px] text-[#1f262e]">{children}</div>;
const Head = ({ meta, children }: { meta: string; children: React.ReactNode }) => { const snap = useContext(EveSnap); return (
  <div className="bg-[#1f262e] px-4 pb-4 pt-3 text-white"><div className="text-[13px] text-[#aab3bd]">{meta}</div>
    <div className="mt-2 flex items-start gap-2.5"><Robot size={30} disc snap={snap} /><p className="m-0 text-[17px] font-extrabold leading-snug text-white [&_b]:text-[#ffc65c]">{children}</p></div></div>); };
const OkLine = ({ ok, right }: { ok: string[]; right?: string }) => (ok.length ? (
  <div className="flex items-center gap-2 border-b border-[#e3e6ea] bg-[#effaf3] px-4 py-2.5 text-[14px] font-bold text-[#1f7a45]">✓ {ok.join('·')} 이상 없음{right && <small className="ml-auto text-[12.5px] font-medium text-[#2f6b4a]">{right}</small>}</div>) : null);
const H = ({ t, n }: { t: string; n?: React.ReactNode }) => <div className="flex items-baseline justify-between px-4 pb-1.5 pt-3.5 text-[13px] font-extrabold text-[#4b5560]"><span>{t}</span><span>{n}</span></div>;
function TodoList({ items }: { items: Todo[] }) {
  const [all, setAll] = useState(false);
  if (!items.length) return <p className="m-0 px-4 pb-2 text-[14px] text-[#4b5560]">오늘 챙길 일이 없어요.</p>;
  const urgent = items.filter((t) => t.tone !== 'soon'), soon = items.filter((t) => t.tone === 'soon');
  const shown = [...urgent, ...(all ? soon : soon.slice(0, 2))], rest = soon.length - Math.min(2, soon.length);
  return (<>
    <ol className="m-0 list-none p-0">{shown.map((t, i) => (
      <li key={t.key}><button onClick={t.go} className={`grid w-full grid-cols-[26px_1fr_auto] items-center gap-2.5 px-4 py-2.5 text-left ${i ? 'border-t border-[#eef0f2]' : ''} ${TONE[t.tone].row}`}>
        <span className={`flex h-6 w-6 items-center justify-center rounded-full border-2 text-[12px] font-extrabold ${TONE[t.tone].num}`}>{i + 1}</span>
        <span className="leading-snug">{t.text}<span className="mt-0.5 block text-[12.5px] font-semibold text-[#5b6570]">{t.sub}</span></span>
        <span className={`whitespace-nowrap rounded-md px-2 py-0.5 text-[12px] font-extrabold ${TONE[t.tone].tag}`}>{t.tag}</span></button></li>))}</ol>
    {rest > 0 && <button onClick={() => setAll((x) => !x)} className="border-t border-[#eef0f2] px-4 py-2.5 text-left text-[14px] font-bold text-[#1f5fc4]">{all ? '접기 ▴' : `임박 ${rest}건 더 보기 ▸`}</button>}
  </>);
}
const Goal = ({ p }: { p: Twin['production'] }) => (
  <div className="flex items-baseline gap-1.5 px-4 pb-3.5 pt-1 text-[15px] text-[#4b5560]"><b className="font-mono text-[26px] text-[#1f262e]">{p.total_target_qty}</b>개 <span className="text-[13px]">(목표 {p.target_qty} + 이월 {p.carry_over_qty})</span></div>);
const Foot = ({ src, onDone }: { src: string; onDone?: () => void }) => (
  <div className="flex flex-col gap-2.5 border-t border-[#eef0f2] px-4 pb-4 pt-3"><span className="text-[13px] text-[#5b6570]">근거 · {src}</span>
    {onDone && <button onClick={onDone} className="h-12 w-full rounded-full bg-[#1c232b] text-[16px] font-extrabold text-white">확인했어요</button>}</div>);
const doIt = (t: string) => (/[기다]$/.test(t) ? t : `${t}하기`); // 할 일은 동사로 끝나게

export default function Briefing({ onDone }: { onDone?: () => void }) {
  const { user, twin, alerts, myNotices, openCard, go, shiftReports, pm, wos } = useApp();
  if (!twin) return <p className="text-slate-500">데이터 없음 (연결 끊김) — 브리핑을 만들 수 없습니다.</p>;
  const last = lastShiftReport(shiftReports, twin);
  const open = alerts.filter((a) => !a.handled);
  const lockout = Object.entries(twin.equipment).filter(([, e]) => e.state_code === 'MAINT').map(([k]) => k);
  const p = twin.production;
  // 제목 = 그 계정에 브리핑할 내용 (페이지구조 v3 N1). 내용은 아직 이 앱 브리핑 그대로 (임시, Q6)
  const title = { OPR: '교대 시작 브리핑 · 내 공정', MNT: '교대 시작 브리핑 · 정비', SUP: '교대 시작 브리핑', MGR: '일일 보고서 브리핑' }[user.role];
  const head = `${title} — ${md(twin.shift.start_at)} ${twin.shift.shift_type === 'DAY' ? '주간' : '야간'} (${twin.shift.start_at.slice(11, 16)}~${twin.shift.end_at.slice(11, 16)})`;
  const pmToday = (pm?.tasks ?? []).filter((t) => t.state === 'OVERDUE' || t.state === 'DUE_SOON').filter((t) => t.cycle_code !== 'DAILY');
  const pmSorted = [...pmToday].sort((a, b) => (a.state === b.state ? 0 : a.state === 'OVERDUE' ? -1 : 1));
  const pmOver = pmToday.filter((t) => t.state === 'OVERDUE').length;
  const pmTodos: Todo[] = pmSorted.map((t, i) => ({ key: `pm${i}`, text: doIt(t.item_name), sub: `${t.equipment_id} · 예방 정비`, tag: t.state === 'OVERDUE' ? '▲ 기한 넘김' : '임박', tone: t.state === 'OVERDUE' ? 'amber' : 'soon', go: () => go('pm', t.equipment_id) }));
  const meta = `${md(twin.shift.start_at)} ${twin.shift.shift_type === 'DAY' ? '주간' : '야간'} ${twin.shift.start_at.slice(11, 16)}~${twin.shift.end_at.slice(11, 16)}`;
  const good = last ? Number(last.actual_qty) - Number(last.defect_qty) : null;

  if (user.role === 'OPR') {
    const mine = open.filter((a) => user.procs.includes(MACHINES[a.machine].op)).sort((a, b) => rankOfAlert(a).localeCompare(rankOfAlert(b)) || a.ts - b.ts);
    const tools = Object.values(twin.equipment).filter((e) => user.procs.includes(e.process_code)).flatMap((e) => e.tools).filter((t) => t.warn);
    const todos: Todo[] = [
      ...mine.map((a): Todo => ({ key: a.id, text: `${a.alarm?.nameKo.replace(/\s*\([A-Z0-9 ._/-]+\)/, '') ?? a.code} 대응하기`, sub: `${MACHINES[a.machine].name} · 알람 ${a.code} · ${hhmm(a.time)}부터`, tag: a.level, tone: a.level === '긴급' ? 'red' : 'amber', go: () => openCard(a.id) })),
      ...tools.map((t, i): Todo => ({ key: `tool${i}`, text: `${t.tool_id} 공구 교체 준비하기`, sub: `수명 ${t.usage_pct}%`, tag: '공구', tone: 'amber', go: () => go('tools') })),
      ...pmTodos,
    ];
    const ok = [lockout.length ? '' : '잠금', mine.length ? '' : '알람', tools.length ? '' : '공구'].filter(Boolean);
    return (
      <Sheet>
        <Head meta={`${meta} · 내 공정 ${user.procs.join('·')}`}>{mine.length ? <>내 공정 알람 <b>{mine.length}건</b>부터 처리해 주세요. </> : pmOver ? <>오늘은 <b>기한 넘긴 정비 {pmOver}건</b>부터 챙겨 주세요. </> : <>먼저 챙길 급한 일은 없어요. </>}목표는 {p.total_target_qty}개예요.</Head>
        {lockout.length > 0 && <div className="bg-[#fdecec] px-4 py-2.5 text-[15px] font-extrabold text-[#b4282d]">🔒 {lockout.join(' · ')} 잠금 중 — 전원을 넣지 마세요</div>}
        <OkLine ok={ok} right={good == null ? undefined : `지난 교대 양품 ${good}개`} />
        <H t="오늘 할 일 · 위에서부터" n={`${todos.length}건`} />
        <TodoList items={todos} />
        <H t="이번 교대 목표" />
        <Goal p={p} />
        <Foot src={`교대 보고서 ${last?.shift_id ?? '없음'} · 예방 정비 일정 · 알람 기록`} onDone={onDone} />
      </Sheet>
    );
  }

  return <FullBrief v={{ twin, last, open, lockout, p, pmOver, pmCount: pmToday.length, pmTodos, good, head }} onDone={onDone} />;
}

type FullView = { twin: Twin; last: Record<string, any> | null; open: AlertRec[]; lockout: string[]; p: Twin['production']; pmOver: number; pmCount: number; pmTodos: Todo[]; good: number | null; head: string };

// 전체형 (SUP·MNT·MGR). 비서 정리 훅을 부르려고 따로 뺐다 (위의 early return 뒤에서는 훅을 못 부른다).
// 먼저 챙길 일 = 인계 사항(지난 교대 보고서) + 지금 알람·알림. 빈 순위는 "-", 0 안전은 늘 맨 위
function FullBrief({ v, onDone }: { v: FullView; onDone?: () => void }) {
  const { myNotices, openCard, go, wos } = useApp();
  const { twin, last, open, lockout, p, pmOver, pmCount, pmTodos, good, head } = v;
  const base = last ? parseHandover(last.handover_text) : [];
  const groups = RANK_ORDER.map((rank) => {
    const b = base.find((g) => g.rank === rank)?.items ?? [];
    const a = open.filter((x) => rankOfAlert(x) === rank);
    const n = myNotices.filter((x) => !x.handled && x.delivery === 'LIST' && rankOfNotice(x) === rank);
    const safety = rank === '0' && lockout.length ? [`🔒 잠금·표지 ${lockout.join(' · ')} (정비 중)`] : [];
    return { rank, base: rank === '0' && lockout.length ? [] : b.filter((t) => !t.startsWith('잠금·표지 중인 설비 없음')), a, n, safety };
  });
  const cnt = (g: typeof groups[number]) => g.base.length + g.a.length + g.n.length + g.safety.length;
  const total = groups.reduce((s, g) => s + cnt(g), 0);
  const by = (rs: string[]) => groups.filter((g) => rs.includes(g.rank)).reduce((s, g) => s + cnt(g), 0);
  const notable: string = last?.notable_text ?? '';
  const sentences = notable.split(/(?<=\.)\s+/);

  // 비서 정리: 순위 묶음별 항목 줄 (화면 순서 = 알람 → 알림 → 인계). 안전(순위 0)은 보내지 않는다. 인계의 "(인계)"는 화면이 따로 붙이는 표시라 줄에 넣지 않는다
  const itemLines = (g: typeof groups[number]) => [...g.a.map(aText), ...g.n.map(noticeLine), ...g.base];
  const aiGroups = groups.filter((g) => g.rank !== '0').map((g) => ({ rank: g.rank, lines: itemLines(g) })).filter((g) => g.lines.length);
  const ai = useBriefingText(twin.shift.shift_id, aiGroups);
  const [raw, setRaw] = useState(false);
  const hasAi = aiGroups.some((g) => ai[g.rank]?.some((t, i) => t !== g.lines[i]));       // 원문과 다른 비서 정리가 하나라도 있을 때만 꼬리표·전환 버튼
  const pick = (g: typeof groups[number], i: number, orig: string) => (!raw && ai[g.rank]?.[i]) || orig;

  return (
    <Sheet>
      <Head meta={head}>{by(['0', '1']) ? <>안전·긴급 <b>{by(['0', '1'])}건</b>부터 챙겨 주세요. </> : pmOver ? <>기한 넘긴 정비 <b>{pmOver}건</b>이 있어요. </> : <>안전·긴급 일은 없어요. </>}먼저 챙길 일은 모두 {total}건, 목표는 {p.total_target_qty}개예요.</Head>
      <OkLine ok={[lockout.length ? '' : '잠금', by(['1']) ? '' : '긴급 알람'].filter(Boolean)} right={good == null ? undefined : `지난 교대 양품 ${good}개`} />
      <div className="flex flex-col gap-3 px-4 py-3 text-[14px]">
      <section>
        <h4 className="m-0 text-[15px] font-extrabold">먼저 챙길 일 — 전체 {total}건 <span className="font-normal text-[#4b5560]">(안전 {by(['0'])} · 긴급 {by(['1'])} · 생산 {by(['2'])} · 주의 {by(['0-1', '3'])} · 참고 {by(['4'])})</span></h4>
        <p className="m-0 mt-1 text-[12.5px] text-[#5b6570]">{hasAi && !raw && <><b>비서 정리</b> · </>}순서는 프로그램 규칙(2.5 보고 순위). 인계 사항 출처: 교대 보고서 {last?.shift_id ?? '없음'}.{hasAi && <button onClick={() => setRaw((x) => !x)} title="프로그램이 만든 원래 문구와 비서가 다듬은 문장을 바꿔 봅니다" className="ml-2 font-semibold underline">{raw ? '비서 정리 보기' : '원문 보기'}</button>}</p>
        <ul className="mt-1 flex flex-col gap-1 pl-0">
          {groups.map((g) => (
            <li key={g.rank} className="list-none"><b>{g.rank} {RANK_NAME[g.rank]}</b>{' '}
              {cnt(g) === 0 ? (g.rank === '0' ? '🔒 잠금·표지 중인 설비 없음' : '-') : (
                <ul className="ml-3 list-disc">
                  {g.safety.map((t) => <li key={t}>{t}</li>)}
                  {g.a.map((a, i) => <li key={a.id}>{pick(g, i, aText(a))} <button onClick={() => openCard(a.id)} className="ml-1 rounded-full bg-[#1c232b] px-2.5 text-[12px] font-bold text-white">열기</button></li>)}
                  {g.n.map((n, i) => <li key={n.id}>{pick(g, g.a.length + i, noticeLine(n))}</li>)}
                  {g.base.map((t, i) => <li key={t}>{pick(g, g.a.length + g.n.length + i, t)} <span className="text-[12px] text-[#5b6570]">(인계)</span></li>)}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </section>
      <section className="border-t border-[#eef0f2] pt-2">
        <h4 className="m-0 text-[15px] font-extrabold">지난 교대 {last ? `(${last.shift_id})` : ''} {last && <button onClick={() => go('shift', last.shift_id)} className="ml-1 text-[13px] font-normal underline">교대 보고서 열기</button>}</h4>
        {!last ? <p className="m-0 text-[#4b5560]">없음</p> : (
          <ul className="list-disc pl-4">
            <li>양품 {good}개 · 불량 {last.defect_qty}개 · 총 목표 {last.target_qty}개 {last.status !== 'CONFIRMED' && <b className="text-[#9a6200]">ⓘ 잠정 (확정 전)</b>}</li>
            <li>{sentences.slice(1, 3).join(' ')}</li>
            <li>{sentences.slice(3).join(' ')}</li>
          </ul>
        )}
      </section>
      <section className="border-t border-[#eef0f2] pt-2">
        <h4 className="m-0 text-[15px] font-extrabold">이번 교대 작업지시</h4>
        <ul className="list-disc pl-4">
          <li>{twin.orders.filter((o) => o.status !== 'COMPLETED').map((o) => `${o.order_no}(${o.status === 'IN_PROGRESS' ? '진행 중' : '대기'}${o.delay ? ' ' + o.delay : ''})`).join(' · ') || '없음'}</li>
          {wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled').length > 0 && <li>진행 중 작업지시서 {wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled').map((w) => w.no).join(' · ')}</li>}
        </ul>
        <button onClick={() => go('stops')} className="mt-2 h-10 rounded-full border border-[#d3d7dc] bg-white px-4 text-[13px] font-semibold">정지 사유 입력 화면</button>
      </section>
      </div>
      <H t="예방 정비 · 급한 순서" n={`${pmCount}건`} />
      <TodoList items={pmTodos} />
      <H t="이번 교대 목표" />
      <Goal p={p} />
      <Foot src={`교대 보고서 ${last?.shift_id ?? '없음'} · 알람·알림 기록 · 예방 정비 일정`} onDone={onDone} />
    </Sheet>
  );
}
