'use client';
// SCR-02 교대 시작 브리핑(전체형: SUP·MNT·MGR) / SCR-03 요약형(OPR) — 이브 사이드바 브리핑 탭 (API-AST-01 모양).
// 지난 교대·인계 사항 = 지난 교대 보고서(생성기·서버), 먼저 챙길 일 = 인계 사항 + 지금 처리 안 된 알람·알림 (2.5 보고 순위).
// 보고 항목은 프로그램 목록이다 (순서·건수는 프로그램 몫). 지난 교대 요약은 교대 보고서 문장을 그대로 쓰므로, 비서가 켜져 있으면 비서가 다듬은 문장이 보인다.
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

export default function Briefing() {
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
  const pmLine = pmToday.length ? pmToday.map((t) => `${t.equipment_id} ${t.item_name}(${t.state === 'OVERDUE' ? '▲ 기한 넘김' : '기한 임박'})`).join(' · ') : '없음';
  const btn = 'h-9 shrink-0 rounded-md border border-slate-300 px-3 text-[12px] font-semibold';

  if (user.role === 'OPR') {
    const mine = open.filter((a) => user.procs.includes(MACHINES[a.machine].op)).sort((a, b) => rankOfAlert(a).localeCompare(rankOfAlert(b)) || a.ts - b.ts);
    const tools = Object.values(twin.equipment).filter((e) => user.procs.includes(e.process_code)).flatMap((e) => e.tools).filter((t) => t.warn);
    return (
      <div className="flex flex-col gap-3 text-[14px]">
        <h3 className="text-[16px] font-bold">{head} · {user.procs.join('·')}</h3>
        <p>🔒 잠금·표지 중인 설비 <b>{lockout.length ? lockout.join(' · ') + ' — 잠금 중, 전원을 넣지 마세요' : '없음'}</b></p>
        <p>지난 교대 <b>양품 {last ? Number(last.actual_qty) - Number(last.defect_qty) : '—'}개</b> {last && <button onClick={() => go('shift', last.shift_id)} className="ml-1 underline">교대 보고서 {last.shift_id.slice(5)}</button>}</p>
        <div>내 공정 알람 (처리 안 됨) — 전체 {mine.length}건
          {mine.length === 0 ? <span className="text-slate-500"> 없음</span> : (
            <ul className="mt-1 flex flex-col gap-1">{mine.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2"><span>{aText(a)}</span><button onClick={() => openCard(a.id)} className={btn}>지침카드</button></li>))}</ul>
          )}
        </div>
        <p>공구 교체 <b>{!user.procs.includes('OP-30') ? '해당 없음 (OP-30 담당만)' : tools.length ? tools.map((t) => `${t.tool_id} ${t.usage_pct}%`).join(' · ') + ' — 교체 준비' : '없음'}</b></p>
        <p>이번 교대 <b>총 {p.total_target_qty}개</b> (목표 {p.target_qty} + 이월 {p.carry_over_qty}) · 예방 정비 <b>{pmLine}</b></p>
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
      <h3 className="text-[16px] font-bold">{head}</h3>
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
          <li>예방 정비 {pmLine}</li>
          {wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled').length > 0 && <li>진행 중 작업지시서 {wos.filter((w) => w.state !== 'done' && w.state !== 'cancelled').map((w) => w.no).join(' · ')}</li>}
        </ul>
      </section>
      <button onClick={() => go('stops')} className="h-11 self-start rounded-md border border-slate-300 px-3 text-[13px] font-semibold">정지 사유 입력 화면</button>
    </div>
  );
}
