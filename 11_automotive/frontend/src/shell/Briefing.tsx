'use client';
// SCR-02 교대 시작 브리핑(전체형: SUP·MNT·MGR) / SCR-03 요약형(OPR) — 이브 사이드바 브리핑 탭 (API-AST-01 모양).
// 지난 교대·인계 사항 = 지난 교대 보고서(생성기·서버), 먼저 챙길 일 = 인계 사항 + 지금 처리 안 된 알람·알림 (2.5 보고 순위).
// 보고 항목은 프로그램 목록이다 (순서·건수는 프로그램 몫). 지난 교대 요약은 교대 보고서 문장을 그대로 쓰므로, 비서가 켜져 있으면 비서가 다듬은 문장이 보인다.
import { useContext, useState } from 'react';
import { useApp } from './ctx';
import { EveSnap, Robot } from './Eve';
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

// 시안 B (사용자 선택 2026-10-18): 이브 한 줄 결론 → 상태 칩 → 급한 순서 목록 → 목표 카드 → 근거·확인
const Say = ({ children }: { children: React.ReactNode }) => { const snap = useContext(EveSnap); return (
  <div className="flex items-start gap-2.5 rounded-2xl border border-[#e1e4e8] bg-white p-3"><Robot size={30} disc snap={snap} /><p className="m-0 text-[15px] font-semibold leading-snug">{children}</p></div>); };
const Chips = ({ items }: { items: [string, string, boolean][] }) => (
  <div className="grid grid-cols-4 gap-1.5">{items.map(([k, v, on]) => <div key={k} className="rounded-xl border border-[#e1e4e8] bg-white px-2 py-1.5 text-[11px] leading-tight text-slate-500">{k}<b className={`mt-0.5 block text-[14px] ${on ? 'text-[#26303a]' : 'font-semibold text-slate-400'}`}>{v}</b></div>)}</div>);
const Sec = ({ t, n }: { t: string; n?: React.ReactNode }) => <div className="flex justify-between text-[12px] font-extrabold tracking-wide text-slate-500"><span>{t}</span><span>{n}</span></div>;
const Goal = ({ p }: { p: Twin['production'] }) => (
  <div className="grid grid-cols-3 gap-1.5">{([['생산 목표', p.target_qty], ['이월', p.carry_over_qty], ['총', p.total_target_qty]] as [string, number][]).map(([k, v]) => <div key={k} className="rounded-xl border border-[#e1e4e8] bg-white px-2.5 py-1.5 text-[11px] text-slate-500">{k}<b className="block font-mono text-[19px] text-[#26303a]">{v}</b></div>)}</div>);
function PmList({ tasks, go }: { tasks: Record<string, any>[]; go: (s: 'pm', k?: string) => void }) {
  const [all, setAll] = useState(false);
  if (!tasks.length) return <p className="m-0 text-slate-500">기한 넘김·임박 없음</p>;
  const over = tasks.filter((t) => t.state === 'OVERDUE'), soon = tasks.filter((t) => t.state !== 'OVERDUE');
  const shown = [...over, ...(all ? soon : soon.slice(0, 2))], rest = soon.length - Math.min(2, soon.length);
  return (
    <div className="overflow-hidden rounded-2xl border border-[#e1e4e8] bg-white">
      {shown.map((t, i) => <button key={i} onClick={() => go('pm', t.equipment_id)} className={`grid w-full grid-cols-[58px_1fr_auto] items-center gap-2 px-3 py-2 text-left text-[13px] leading-snug ${i ? 'border-t border-[#eceef1]' : ''} ${t.state === 'OVERDUE' ? 'bg-[#fff7e3]' : ''}`}>
        <span className="font-mono text-[11px] font-bold text-slate-500">{t.equipment_id}</span><span>{t.item_name}</span>
        <span className={`whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-extrabold ${t.state === 'OVERDUE' ? 'bg-[#f0b429] text-[#3d2a00]' : 'bg-[#eef0f3] text-slate-500'}`}>{t.state === 'OVERDUE' ? '▲ 넘김' : '임박'}</span></button>)}
      {rest > 0 && <button onClick={() => setAll((a) => !a)} className="w-full border-t border-[#eceef1] px-3 py-2 text-left text-[13px] font-bold text-[#1f5fc4]">{all ? '접기 ▴' : `임박 ${rest}건 더 보기 ▸`}</button>}
    </div>);
}
const Foot = ({ src, onDone }: { src: string; onDone?: () => void }) => (
  <div className="flex flex-col gap-2 border-t border-[#dfe2e6] pt-3"><span className="text-[11px] text-slate-500">근거 · {src}</span>
    {onDone && <button onClick={onDone} className="h-11 w-full rounded-full bg-[#1c232b] text-[15px] font-extrabold text-white">확인했어요</button>}</div>);

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
  const pmLine = pmToday.length ? pmToday.map((t) => `${t.equipment_id} ${t.item_name}(${t.state === 'OVERDUE' ? '▲ 기한 넘김' : '기한 임박'})`).join(' · ') : '없음';
  const btn = 'h-9 shrink-0 rounded-md border border-slate-300 px-3 text-[12px] font-semibold';

  if (user.role === 'OPR') {
    const mine = open.filter((a) => user.procs.includes(MACHINES[a.machine].op)).sort((a, b) => rankOfAlert(a).localeCompare(rankOfAlert(b)) || a.ts - b.ts);
    const tools = Object.values(twin.equipment).filter((e) => user.procs.includes(e.process_code)).flatMap((e) => e.tools).filter((t) => t.warn);
    const good = last ? Number(last.actual_qty) - Number(last.defect_qty) : null;
    const toolV = !user.procs.includes('OP-30') ? '해당 없음' : tools.length ? tools.map((t) => `${t.tool_id} ${t.usage_pct}%`).join(' · ') : '없음';
    return (
      <div className="flex flex-col gap-3 text-[14px]">
        <span className="font-mono text-[12px] text-slate-500">{md(twin.shift.start_at)} {twin.shift.shift_type === 'DAY' ? '주간' : '야간'} {twin.shift.start_at.slice(11, 16)}~{twin.shift.end_at.slice(11, 16)} · 내 공정 {user.procs.join('·')}</span>
        <Say>{mine.length ? <>내 공정 알람 <b>{mine.length}건</b>부터 처리해 주세요. </> : pmOver ? <>오늘은 <b>기한 넘긴 정비 {pmOver}건</b>부터 챙겨 주세요. 내 공정 알람은 없고, </> : <>먼저 챙길 급한 일은 없어요. </>}목표는 <b>{p.total_target_qty}개</b>예요.</Say>
        {lockout.length > 0 && <p className="m-0 rounded-xl bg-[#fdecec] px-3 py-2 font-bold text-[#b4282d]">🔒 {lockout.join(' · ')} 잠금 중 — 전원을 넣지 마세요</p>}
        <Chips items={[['🔒 잠금·표지', lockout.length ? `${lockout.length}대` : '없음', lockout.length > 0], ['내 공정 알람', `${mine.length}건`, mine.length > 0], ['공구 교체', toolV, tools.length > 0], ['지난 교대 양품', good == null ? '—' : `${good}개`, good != null]]} />
        {mine.length > 0 && (<><Sec t="내 공정 알람 · 처리 안 됨" n={`${mine.length}건`} />
          <div className="overflow-hidden rounded-2xl border border-[#e1e4e8] bg-white">{mine.map((a, i) => <div key={a.id} className={`flex items-center gap-2 px-3 py-2 text-[13px] ${i ? 'border-t border-[#eceef1]' : ''}`}><span className="flex-1">{aText(a)}</span><button onClick={() => openCard(a.id)} className="h-8 shrink-0 rounded-full bg-[#1c232b] px-3 text-[12px] font-bold text-white">지침카드</button></div>)}</div></>)}
        <Sec t="예방 정비 · 급한 순서" n={`${pmToday.length}건`} />
        <PmList tasks={pmSorted} go={go} />
        <Sec t="이번 교대 목표" />
        <Goal p={p} />
        <Foot src={`교대 보고서 ${last?.shift_id ?? '없음'} · 예방 정비 일정 · 알람 기록`} onDone={onDone} />
      </div>
    );
  }

  // 전체형: 먼저 챙길 일 = 인계 사항(지난 교대 보고서) + 지금 알람·알림. 빈 순위는 "-", 0 안전은 늘 맨 위
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

  return (
    <div className="flex flex-col gap-3 text-[14px]">
      <span className="font-mono text-[12px] text-slate-500">{head}</span>
      <Say>{by(['0', '1']) ? <>안전·긴급 <b>{by(['0', '1'])}건</b>부터 챙겨 주세요. </> : pmOver ? <>기한 넘긴 정비 <b>{pmOver}건</b>이 있어요. </> : <>안전·긴급 일은 없어요. </>}먼저 챙길 일은 모두 <b>{total}건</b>, 목표는 <b>{p.total_target_qty}개</b>예요.</Say>
      <Chips items={[['🔒 잠금·표지', lockout.length ? `${lockout.length}대` : '없음', lockout.length > 0], ['긴급 알람', `${by(['1'])}건`, by(['1']) > 0], ['먼저 챙길 일', `${total}건`, total > 0], ['지난 교대 양품', last ? `${Number(last.actual_qty) - Number(last.defect_qty)}개` : '—', !!last]]} />
      <section>
        <h4 className="font-bold">먼저 챙길 일 — 전체 {total}건 <span className="font-normal text-slate-500">(안전 {by(['0'])} · 긴급 {by(['1'])} · 생산 {by(['2'])} · 주의 {by(['0-1', '3'])} · 참고 {by(['4'])})</span></h4>
        <p className="text-[11px] text-slate-500">순서는 프로그램 규칙(2.5 보고 순위). 인계 사항 출처: 교대 보고서 {last?.shift_id ?? '없음'}. 보고 항목은 프로그램 목록 (지난 교대 요약은 비서가 켜져 있으면 비서가 다듬은 문장)</p>
        <ul className="mt-1 flex flex-col gap-1">
          {groups.map((g) => (
            <li key={g.rank}><b>{g.rank} {RANK_NAME[g.rank]}</b>{' '}
              {cnt(g) === 0 ? (g.rank === '0' ? '🔒 잠금·표지 중인 설비 없음' : '-') : (
                <ul className="ml-3 list-disc">
                  {g.safety.map((t) => <li key={t}>{t}</li>)}
                  {g.a.map((a) => <li key={a.id}>{aText(a)} <button onClick={() => openCard(a.id)} className="ml-1 rounded border border-slate-300 px-2 text-[11px] font-semibold">열기</button></li>)}
                  {g.n.map((n) => <li key={n.id}>[{n.ruleName}] {n.text}{n.past ? ` · ${md(n.at)}` : ''}</li>)}
                  {g.base.map((t) => <li key={t}>{t} <span className="text-[11px] text-slate-500">(인계)</span></li>)}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </section>
      <section className="border-t border-slate-200 pt-2">
        <h4 className="font-bold">지난 교대 {last ? `(${last.shift_id})` : ''} {last && <button onClick={() => go('shift', last.shift_id)} className="ml-1 text-[12px] font-normal underline">교대 보고서 열기</button>}</h4>
        {!last ? <p className="text-slate-500">없음</p> : (
          <ul className="list-disc pl-4">
            <li>양품 {Number(last.actual_qty) - Number(last.defect_qty)}개 · 불량 {last.defect_qty}개 · 총 목표 {last.target_qty}개 {last.status !== 'CONFIRMED' && <b className="text-[#9a6200]">ⓘ 잠정 (확정 전)</b>}</li>
            <li>{sentences.slice(1, 3).join(' ')}</li>
            <li>{sentences.slice(3).join(' ')}</li>
          </ul>
        )}
      </section>
      <section className="border-t border-slate-200 pt-2">
        <h4 className="font-bold">이번 교대</h4>
        <ul className="list-disc pl-4">
          <li>총 {p.total_target_qty}개 (목표 {p.target_qty} + 이월 {p.carry_over_qty})</li>
          <li>작업지시 {twin.orders.filter((o) => o.status !== 'COMPLETED').map((o) => `${o.order_no}(${o.status === 'IN_PROGRESS' ? '진행 중' : '대기'}${o.delay ? ' ' + o.delay : ''})`).join(' · ') || '없음'}</li>
          {wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled').length > 0 && <li>진행 중 작업지시서 {wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled').map((w) => w.no).join(' · ')}</li>}
        </ul>
      </section>
      <Sec t="예방 정비 · 급한 순서" n={`${pmToday.length}건`} />
      <PmList tasks={pmSorted} go={go} />
      <Goal p={p} />
      <button onClick={() => go('stops')} className="h-10 self-start rounded-full border border-slate-300 bg-white px-4 text-[13px] font-semibold">정지 사유 입력 화면</button>
      <Foot src={`교대 보고서 ${last?.shift_id ?? '없음'} · 알람·알림 기록 · 예방 정비 일정`} onDone={onDone} />
    </div>
  );
}
