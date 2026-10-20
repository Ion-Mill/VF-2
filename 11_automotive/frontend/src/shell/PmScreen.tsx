'use client';
// SCR-23 예방 정비 일정 — DOC-04 항목(pm_task.csv 74줄), 다음 기한(9월 실시 기록 + 주기), 기한 하루 전 ⓘ·넘김 ▲, 잠금·표지 판단(DOC-05).
// [정비 시작]·[정비 끝·실시 기록] = API-PM-02 → 시뮬레이터에 MAINT(정비) 상태로 기록 (설비 조작 버튼이 아니라 기록 버튼).
// 구성 (2026-10-19 정비 탭 구조 수정): 왼쪽 설비 목록 대신 위쪽 칩 탭(전체 장비 | 6대, "지남 ▲n · 오늘 n", [닫기]는 늘 첫 줄 오른쪽).
//   전체 장비 = 숫자 4칸(지남·오늘·이번 주·실시율과 목표선) → 설비별 요약표(누르면 그 설비) → 이번 달 기한 달력(건수 점, 날짜를 누르면 설비별 번호 목록).
//   설비별 = 결론 띠(기한 지남 · 오늘 정비 예정) → 급한 순 묶음(지남·오늘 펼침) → 오늘 실시 기록 ‖ 오른쪽 정비 진행 3단계(고르기 → 시작 → 끝·기록).
//   기한 구분은 화면이 날짜로 센다: 지남 · 오늘 · 이번 주(1~6일 뒤, 내일 포함) · 이번 달(7일 뒤 ~ 이달 말) · 기한 없음. 다음 달 이후는 목록에 없고 숫자만 (2026-10-20). 서버의 DUE_SOON(오늘+내일)은 쓰지 않는다.
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { api, hm, md, SIM, simIso, usePersist } from './live';
import { USERS, userName } from './model';
import { PartsPicker } from './WorkRecordScreen';

type R = Record<string, any>;
const CYC: Record<string, [string, number | null]> = { DAILY: ['매일', 1], WEEKLY: ['매주', 7], MONTHLY: ['매월', 30], HALF_YEAR: ['6개월', 182], YEARLY: ['1년', 365], EVERY_8H_USE: ['8시간 사용마다', null], AS_REQUIRED: ['필요할 때', null] };
const LOCK: Record<string, [string, number]> = { FULL: ['§2 전부', 4], TWO_POINT: ['보충용 2점 잠금', 3], ONE_POINT: ['1점 잠금', 2], PLUG: ['플러그 뽑기', 1], UNPLUG: ['플러그 뽑기', 1], NONE: ['', 0] };
const RESULT: Record<string, string> = { NORMAL: '정상', REFILLED: '보충함', ABNORMAL: '이상' };
export const EQS = ['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'];
export const PM_ALL = '전체 장비';
const PROC: Record<string, string> = { 'SAW-01': 'OP-10 절단', 'MIL-01': 'OP-20 밀링', 'VF2-01': 'OP-30 머시닝 1호기', 'VF2-02': 'OP-30 머시닝 2호기', 'WSH-01': 'OP-40 세척', 'CMM-01': 'OP-50 측정' };
const WD = ['일', '월', '화', '수', '목', '금', '토'];
const GOAL_PCT = 90; // [참고: NASA RCM 90% 이상 목표]
type Bk = 'over' | 'soon' | 'week' | 'month' | 'next' | 'none';
const BUCKETS: [Bk, string, string][] = [['over', '▲ 기한 지남', '먼저 하세요'], ['soon', '오늘', ''], ['week', '이번 주', '1~6일 뒤'], ['month', '이번 달', '7일 뒤 ~ 이달 말'], ['none', '작업자 교대 점검 · 필요할 때', '기한 없음']];
const CHIP = 'inline-flex h-6 items-center whitespace-nowrap rounded-full px-2 text-[12px] font-semibold';
const AMBER = 'text-[#9a6200]';
// 섹션 머리줄 카드: 왼쪽 세로 막대 + 제목, 오른쪽에 그 섹션의 한 줄 요약(칩·범례). 본문(표·달력·목록)은 아래에 따로 테두리 상자로
function SecHead({ title, right }: { title: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
      <span className="h-5 w-1 shrink-0 rounded-full bg-[#0f6f86]" aria-hidden />
      <h3 className="text-[16px] font-bold">{title}</h3>
      {right && <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

const dayNum = (s: string) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 864e5;
const today = () => simIso().slice(0, 10);
const diffDays = (s: string) => dayNum(s.slice(0, 10)) - dayNum(today());
// 급한 순 묶음 ('soon' = 오늘): 지남은 서버 판정(OVERDUE) 또는 지난 날짜, 그 밖은 다음 기한까지 남은 날 (0 = 오늘, 1~6 = 이번 주)
const bucketOf = (t: R): Bk => {
  if (t.state === 'OVERDUE') return 'over';
  if (!t.next_due) return 'none';
  const d = diffDays(t.next_due);
  return d < 0 ? 'over' : d === 0 ? 'soon' : d <= 6 ? 'week' : String(t.next_due).slice(0, 7) === today().slice(0, 7) ? 'month' : 'next';
};
const countOf = (ts: R[]) => { const c: Record<Bk, number> = { over: 0, soon: 0, week: 0, month: 0, next: 0, none: 0 }; ts.forEach((t) => { c[bucketOf(t)] += 1; }); return c; };
const windowsOf = (pm: { planned_windows: R[] }, eq: string) => pm.planned_windows.filter((w) => w.equipment_id === eq).sort((a, b) => String(a.start_at).localeCompare(String(b.start_at)));
const winText = (w: R) => `${w.start_at.slice(0, 10) === today() ? '오늘' : md(w.start_at)} ${hm(w.start_at)}~${hm(w.end_at)}`;
// 정비 예정까지 남은 시간 (시연 시계 기준)
const untilText = (w: R) => {
  const now = SIM.now(), a = Date.parse(w.start_at), b = Date.parse(w.end_at), m = Math.round((b - a) / 60000);
  return now < a ? `${Math.round((a - now) / 60000)}분 뒤 시작 · ${m}분 정지` : now < b ? `정비 중 · ${Math.round((b - now) / 60000)}분 남음` : '정비 예정 시간 지남';
};

// 메뉴 "예방 정비" — 위쪽 칩 탭 + 전체 장비 / 설비별
export function PmPage() {
  const { pm, role, back, key, go } = useApp();
  if (role === 'OPR') return <div className={PAGE}><div className={CARD}>예방 정비는 작업자 메뉴에 없습니다 (작업자가 한 항목도 보전 담당자가 기록). <button onClick={back} className={BTN}>닫기</button></div></div>;
  if (!pm) return <div className={PAGE}><div className={CARD}>불러오는 중… <button onClick={back} className={BTN}>닫기</button></div></div>;
  const tab = key && EQS.includes(key) ? key : PM_ALL;
  return (
    <div className={PAGE}>
      <div className={`${CARD} flex !max-w-[1240px] flex-col gap-4`}>
        {/* <nav>로 감싸지 않는다 — globals.css의 메뉴 레일 규칙(nav .bg-[#1c2530])이 고른 칩의 글자를 숨긴다 */}
        {/* [전체 장비] | [설비 6대 — 넘치면 이 묶음만 줄바꿈] [닫기 — 늘 첫 줄 오른쪽] */}
        <div className="flex items-start gap-2">
          <div className="flex min-w-0 flex-1 items-start gap-2" role="tablist" aria-label="설비">
            {(() => {
              const chip = (e: string) => {
                const c = countOf(e === PM_ALL ? pm.tasks : pm.tasks.filter((t) => t.equipment_id === e)), on = tab === e;
                return (
                  <button key={e} role="tab" aria-selected={on} onClick={() => go('pm', e)} className={`flex h-11 shrink-0 items-center gap-2 rounded-full border px-4 text-[15px] font-semibold ${on ? 'border-[#1c2530] bg-[#1c2530] text-white' : 'border-slate-300 bg-white hover:border-[#0f9fbd]'}`}>
                    <span className={e === PM_ALL ? '' : 'font-mono'}>{e}</span>
                    {c.over > 0 && <span className="rounded-full bg-[#fff1d1] px-2 text-[12px] text-[#9a6200]">지남 ▲{c.over}</span>}
                    {c.soon > 0 && <span className={`rounded-full px-2 text-[12px] ${on ? 'bg-white/20' : 'bg-slate-100 text-slate-600'}`}>오늘 {c.soon}</span>}
                  </button>
                );
              };
              return (<>
                {chip(PM_ALL)}
                <span className="mx-1 w-px shrink-0 self-stretch bg-slate-300" aria-hidden />
                <div className="flex min-w-0 flex-1 flex-wrap gap-2">{EQS.map(chip)}</div>
              </>);
            })()}
          </div>
          <button onClick={back} className={`${BTN} shrink-0`}>닫기</button>
        </div>
        {tab === PM_ALL ? <PmAll /> : <PmScreen eq={tab} />}
      </div>
    </div>
  );
}

// 전체 장비: 숫자 4칸 + 설비별 요약표 + 이번 달 기한 달력. 보기 전용 (기록은 설비별 탭에서).
export function PmAll() {
  const { pm, go } = useApp();
  const [sel, setSel] = useState<string>(today());
  if (!pm) return null;
  const c = countOf(pm.tasks), rate = pm.on_time_rate_pct;
  const overEqs = [...new Set(pm.tasks.filter((t) => bucketOf(t) === 'over').map((t) => t.equipment_id))];
  const kpis: { l: string; v: string | number; u: string; s: string; main?: boolean }[] = [
    { l: '기한 지남', v: c.over, u: '건', s: c.over ? `${overEqs.join(' · ')} · 먼저 하세요` : '없음', main: true },
    { l: '오늘 기한', v: c.soon, u: '건', s: `설비 ${new Set(pm.tasks.filter((t) => bucketOf(t) === 'soon').map((t) => t.equipment_id)).size}대` },
    { l: '이번 주 (1~6일 뒤)', v: c.week, u: '건', s: `이번 달 ${c.month}건 · 기한 없음 ${c.none}건 · 다음 달 이후 ${c.next}건` },
  ];
  // 이번 달 기한 달력 (다음 기한만 — 실시하면 그 뒤 기한이 새로 생긴다). 기한 지남은 오늘 칸에 모은다
  const t0 = today(), y = +t0.slice(0, 4), m = +t0.slice(5, 7), lead = new Date(Date.UTC(y, m - 1, 1)).getUTCDay(), len = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const iso = (d: number) => `${t0.slice(0, 8)}${String(d).padStart(2, '0')}`;
  const dueOn = (d: string) => [...(d === t0 ? pm.tasks.filter((t) => bucketOf(t) === 'over') : []), ...pm.tasks.filter((t) => t.next_due && t.next_due.slice(0, 10) === d && bucketOf(t) !== 'over')];
  const selList = dueOn(sel);
  const DOT = { over: 'bg-[#9a6200] text-white', today: 'bg-[#fff1d1] text-[#9a6200] border border-[#e0b46a]', due: 'bg-slate-100 text-slate-600 border border-slate-300' };

  return (<>
    <section className="grid grid-cols-2 gap-6 lg:grid-cols-[repeat(4,minmax(0,250px))] lg:justify-between" aria-label="전체 장비 숫자">
      {kpis.map((k) => (
        <div key={k.l} className={`rounded-lg border p-3 ${k.main ? 'border-transparent bg-[#0f6f86] text-white' : 'border-slate-200'}`}>
          <div className={`text-[13px] ${k.main ? 'text-white/85' : 'text-slate-500'}`}>{k.l}</div>
          <div className="font-mono text-[32px] font-bold leading-tight">{k.v}<span className={`ml-1 text-[14px] font-normal ${k.main ? 'text-white/85' : 'text-slate-500'}`}>{k.u}</span></div>
          <div className={`text-[12px] ${k.main ? 'text-white/85' : 'text-slate-500'}`}>{k.s}</div>
        </div>
      ))}
      <div className="rounded-lg border border-slate-200 p-3">
        <div className="text-[13px] text-slate-500">실시율 · 9월</div>
        <div className={`font-mono text-[32px] font-bold leading-tight ${rate !== null && rate < GOAL_PCT ? AMBER : ''}`}>{rate ?? '—'}<span className="ml-1 text-[14px] font-normal text-slate-500">%</span></div>
        <div className="relative my-1.5 h-2.5 rounded-full bg-slate-200" role="img" aria-label={`실시율 ${rate ?? '—'}%, 목표 ${GOAL_PCT}%`}>
          <i className="absolute inset-y-0 left-0 rounded-full bg-[#d98a1e]" style={{ width: `${rate ?? 0}%` }} />
          <b className="absolute -inset-y-1 w-0.5 rounded bg-[#1c2530]" style={{ left: `${GOAL_PCT}%` }} />
        </div>
        <div className="text-[12px] text-slate-500">{rate !== null && rate < GOAL_PCT ? <>목표 {GOAL_PCT}%까지 <b className={AMBER}>{(GOAL_PCT - rate).toFixed(1)}%</b> 부족</> : `목표 ${GOAL_PCT}%`}</div>
      </div>
    </section>

    <section className="flex flex-col gap-2" aria-label="설비별 요약">
      <SecHead title="설비별 요약" right={overEqs.length
        ? <span className={`${CHIP} bg-[#fff1d1] text-[#9a6200]`}>지남 {overEqs.length}대</span>
        : <span className={`${CHIP} bg-[#e0f2e8] text-[#127a46]`}>지남 없음</span>} />
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <div className="grid min-w-[760px] grid-cols-[150px_repeat(5,minmax(64px,1fr))_minmax(170px,1.6fr)_24px] gap-2 bg-slate-50 px-3 py-2 text-[12px] font-semibold text-slate-500">
          <span>설비</span><span>▲ 지남</span><span>오늘</span><span>이번 주</span><span>이번 달</span><span>기한 없음</span><span>정비 예정</span><span />
        </div>
        {EQS.map((e) => {
          const k = countOf(pm.tasks.filter((t) => t.equipment_id === e)), w = windowsOf(pm, e)[0];
          const n = (v: number, cls = '') => <span className={`font-mono text-[16px] ${v ? `font-bold ${cls}` : 'text-slate-400'}`}>{v || '–'}</span>;
          return (
            <button key={e} onClick={() => go('pm', e)} className="grid min-h-[52px] w-full min-w-[760px] grid-cols-[150px_repeat(5,minmax(64px,1fr))_minmax(170px,1.6fr)_24px] items-center gap-2 border-t border-slate-200 px-3 py-2 text-left hover:bg-slate-50">
              <span><b className="block font-mono text-[15px]">{e}</b><span className="text-[12px] text-slate-500">{PROC[e]}</span></span>
              {n(k.over, AMBER)}{n(k.soon)}{n(k.week)}{n(k.month)}{n(k.none)}
              <span className={w ? 'text-[13px] font-semibold' : 'text-slate-400'}>{w ? `▨ ${winText(w)}` : '–'}</span>
              <span className="text-slate-400" aria-hidden>›</span>
            </button>
          );
        })}
      </div>
    </section>

    <section className="flex flex-col gap-2" aria-label="이번 달 기한 달력">
      <SecHead title={`${m}월 기한 달력`} right={
        <span className="flex flex-wrap gap-3 text-[12px] text-slate-600"><span><i className={`mr-1 inline-block h-2.5 w-2.5 rounded-full ${DOT.over}`} />기한 지남</span><span><i className={`mr-1 inline-block h-2.5 w-2.5 rounded-full ${DOT.today}`} />오늘</span><span><i className={`mr-1 inline-block h-2.5 w-2.5 rounded-full ${DOT.due}`} />마감 기한</span></span>} />
      <div className="overflow-x-auto rounded-lg border border-slate-200 p-2">
        <div className="grid min-w-[620px] grid-cols-7 gap-1">
          {WD.map((w) => <div key={w} className="text-center text-[12px] font-semibold text-slate-500">{w}</div>)}
          {Array.from({ length: lead }, (_, i) => <div key={`b${i}`} />)}
          {Array.from({ length: len }, (_, i) => {
            const d = iso(i + 1), dd = dayNum(d) - dayNum(t0), ts = dueOn(d);
            const over = ts.filter((t) => bucketOf(t) === 'over').length, soon = dd === 0 ? ts.length - over : 0, later = dd > 0 ? ts.length : 0;
            return (
              <button key={d} onClick={() => setSel(d)} aria-pressed={sel === d} aria-label={`${m}월 ${i + 1}일 기한 ${ts.length}건`}
                className={`flex min-h-[72px] flex-col gap-1 rounded-md border p-1.5 text-left ${sel === d ? 'border-[#0f9fbd] bg-[#e8f6fa]' : dd === 0 ? 'border-2 border-[#0f9fbd]' : dd < 0 ? 'border-slate-200 bg-slate-50 text-slate-400' : 'border-slate-200 hover:border-[#0f9fbd]'}`}>
                <b className="font-mono text-[13px]">{i + 1}</b>
                <span className="flex flex-wrap gap-1 font-mono text-[11px] font-semibold">
                  {over > 0 && <span className={`rounded-full px-1.5 ${DOT.over}`}>▲{over}</span>}
                  {soon > 0 && <span className={`rounded-full px-1.5 ${DOT.today}`}>{soon}</span>}
                  {later > 0 && <span className={`rounded-full px-1.5 ${DOT.due}`}>{later}</span>}
                </span>
              </button>
            );
          })}
        </div>
        <div className="mt-2 border-t border-slate-200 pt-2 text-[14px]">
          <b>{md(sel)} ({WD[new Date(dayNum(sel) * 864e5).getUTCDay()]}) 기한 {selList.length}건</b>
          {selList.length === 0 ? <p className="text-slate-500">이날 기한인 항목이 없습니다.</p> : (
            // 설비마다 번호 목록 (번호마다 줄바꿈, 화면 폭에 따라 여러 열). 번호 동그라미 = 달력 숫자 칩과 같은 색
            <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-x-8 gap-y-4">{EQS.map((e) => [e, selList.filter((t) => t.equipment_id === e)] as const).filter(([, l]) => l.length).map(([e, l]) => (
              <div key={e} className="flex flex-col gap-1.5">
                <span className={`${CHIP} w-fit bg-slate-100 font-mono text-slate-700`}>{e}</span>
                <ol className="flex flex-col gap-1">{l.map((t, i) => {
                  const ov = bucketOf(t) === 'over';
                  return (
                    <li key={t.pm_task_id} className="flex items-start gap-2">
                      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-semibold ${ov ? DOT.over : sel === t0 ? DOT.today : DOT.due}`}>{i + 1}</span>
                      <span className={ov ? `font-semibold ${AMBER}` : ''}>{ov ? '▲ ' : ''}{t.item_name}</span>
                    </li>);
                })}</ol>
              </div>))}
            </div>)}
        </div>
      </div>
    </section>
  </>);
}

// 설비별: 결론 띠 + 급한 순 묶음 + 오늘 실시 기록 ‖ 오른쪽 정비 진행 3단계 (기록은 MNT만)
export function PmScreen({ eq }: { eq: string }) {
  const { pm, reloadPm, role, user, toast, twin, reloadInv } = useApp();
  const [open, setOpen] = useState<Set<Bk>>(new Set(['over', 'soon']));
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [doneBy, setDoneBy] = useState(user.id);
  const [parts, setParts] = useState<{ item: string; qty: number }[]>([]);
  const [mins, setMins] = useState(60);
  const [ok, setOk] = usePersist<Record<string, string>>('pmOk', {}, twin?.run_id ?? null);
  if (!pm) return null;
  const tasks = pm.tasks.filter((t) => t.equipment_id === eq), c = countOf(tasks);
  const isMaint = twin?.equipment[eq as 'VF2-01']?.state_code === 'MAINT';
  const w = windowsOf(pm, eq)[0];
  const canDo = role === 'MNT';
  const call = async (path: string, body: R, msg: string) => { try { await api(path, { role, user_id: user.id, equipment_id: eq, ...body }); toast(msg); reloadPm(); reloadInv(); } catch (e) { toast((e as Error).message); } };
  const lockNeed = tasks.filter((t) => (bucketOf(t) === 'over' || bucketOf(t) === 'soon') && (LOCK[t.lockout_level]?.[1] ?? 0) > 0).length;
  const picked = tasks.filter((t) => pick.has(t.pm_task_id));
  const topLock = picked.reduce((a, t) => ((LOCK[t.lockout_level]?.[1] ?? 0) > (LOCK[a]?.[1] ?? 0) ? t.lockout_level : a), 'NONE' as string);
  const step = isMaint ? 3 : picked.length ? 2 : 1;
  const recs = pm.today_records.filter((r) => String(r.pm_task_id).includes(eq));
  const nameOfTask = (id: string) => pm.tasks.find((t) => t.pm_task_id === id)?.item_name ?? id;

  const dueCell = (t: R) => {
    if (!t.next_due) return <span className="text-slate-400">—<small className="block text-[12px]">기한 없음</small></span>;
    const d = diffDays(t.next_due);
    if (bucketOf(t) === 'over') return <span className={`font-bold ${AMBER}`}>▲ <span className="font-mono">{Math.max(1, -d)}</span>일 지남<small className="block text-[12px] font-normal text-slate-500">기한 {md(t.next_due)}</small></span>;
    return <span className="font-semibold">{d <= 0 ? '오늘' : d === 1 ? '내일' : <span className="font-mono">{md(t.next_due)}</span>}<small className="block text-[12px] font-normal text-slate-500">{d <= 1 ? md(t.next_due) : `${d}일 뒤`}</small></span>;
  };
  const lastCell = (t: R) => {
    if (!t.last?.done_at) return <span className="text-[12px] text-slate-400">기록 없음</span>;
    const d = -diffDays(t.last.done_at);
    return <span className="text-[12px] leading-snug text-slate-500"><b className="font-mono text-[13px] text-slate-800">{d <= 0 ? `오늘 ${hm(t.last.done_at)}` : md(t.last.done_at)}</b>{d > 0 ? ` · ${d}일 전` : ''}<br />{userName(t.last.by)}</span>;
  };
  const stepCls = (n: number) => (step > n ? 'bg-[#13804a] text-white' : step === n ? 'bg-[#0f6f86] text-white' : 'border border-slate-300 bg-white text-slate-400');

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-w-0 flex-col gap-3">
        {/* 결론 띠 */}
        <section className={`grid gap-x-6 gap-y-2 rounded-xl border px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] ${c.over ? 'border-[#ecd08f] bg-[#fff6e0]' : 'border-[#bfe0cb] bg-[#eef8f2]'}`}>
          <div className="min-w-0">
            <div className="text-[20px] font-bold leading-snug">
              <span className="font-mono">{eq}</span> · {c.over ? <>기한 지남 <span className={`font-mono ${AMBER}`}>{c.over}</span>건</> : <span className="text-[#13804a]">기한 지난 항목 없음</span>}
              {w && <> · {winText(w).startsWith('오늘') ? '오늘 ' : `${md(w.start_at)} `}<span className="font-mono">{hm(w.start_at)}~{hm(w.end_at)}</span> 정비 예정</>}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <span className={`${CHIP} bg-white text-slate-600`}>{PROC[eq]}</span>
              {isMaint ? <span className={`${CHIP} bg-[#0f6f86] text-white`}>▨ 지금 정비 중</span> : w && <span className={`${CHIP} bg-[#e8f6fa] text-[#0f6f86]`}>▨ {untilText(w)}</span>}
              {lockNeed > 0 && <span className={`${CHIP} border border-slate-400 bg-white text-slate-700`}>🔒 지남·오늘 중 잠금·표지 필요 {lockNeed}건</span>}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-x-5">
            {([['오늘', c.soon], ['이번 주', c.week], ['이번 달', c.month]] as const).map(([l, v]) => <div key={l}><div className="text-[12px] text-slate-500">{l}</div><b className="font-mono text-[24px]">{v}</b><span className="ml-0.5 text-[13px] text-slate-500">건</span></div>)}
            {c.next > 0 && <div className="col-span-3 text-[12px] text-slate-500">다음 달 이후 <b className="font-mono">{c.next}</b>건</div>}
          </div>
        </section>

        {/* 급한 순 묶음 */}
        {BUCKETS.map(([k, label, hint]) => {
          const rs = tasks.filter((t) => bucketOf(t) === k).sort((a, b) => String(a.next_due ?? '').localeCompare(String(b.next_due ?? '')) || String(a.doc04_section).localeCompare(String(b.doc04_section)));
          if (!rs.length) return null;
          const isOpen = open.has(k);
          return (
            <section key={k} className={`rounded-lg border ${k === 'over' ? 'border-[#e8c98a]' : 'border-slate-200'}`}>
              <button onClick={() => setOpen((o) => { const n = new Set(o); if (n.has(k)) n.delete(k); else n.add(k); return n; })} aria-expanded={isOpen} className="flex min-h-[48px] w-full flex-wrap items-center gap-x-3 px-3 py-2 text-left">
                <span className="w-4 text-slate-500">{isOpen ? '▾' : '▸'}</span>
                <b className={`text-[15px] ${k === 'over' ? AMBER : ''}`}>{label}</b><span className="font-mono text-slate-500">{rs.length}건</span>
                {hint && <span className="ml-auto text-[12px] text-slate-500">{hint}</span>}
              </button>
              {isOpen && <ul>{rs.map((t) => {
                const lk = LOCK[t.lockout_level]?.[0], on = pick.has(t.pm_task_id);
                return (
                  <li key={t.pm_task_id} className={`grid items-center gap-x-3 gap-y-1 border-t border-slate-100 px-3 py-2 ${canDo ? 'grid-cols-[28px_minmax(170px,1.5fr)_120px_minmax(0,1.5fr)_140px]' : 'grid-cols-[minmax(170px,1.5fr)_120px_minmax(0,1.5fr)_140px]'} ${on ? 'bg-[#e8f6fa]' : ''}`}>
                    {canDo && <input type="checkbox" className="h-5 w-5" aria-label={`${t.item_name} 고르기`} disabled={isMaint} checked={on} onChange={() => setPick((p) => { const n = new Set(p); if (n.has(t.pm_task_id)) n.delete(t.pm_task_id); else n.add(t.pm_task_id); return n; })} />}
                    <span className="min-w-0"><b className="block text-[15px] leading-snug">{t.item_name}</b><span className="text-[12px] text-slate-500">{t.area}</span></span>
                    {dueCell(t)}
                    <span className="flex flex-wrap gap-1">
                      <span className={`${CHIP} bg-slate-100 text-slate-600`}>{CYC[t.cycle_code]?.[0] ?? t.cycle_code} · §{t.doc04_section}{t.source_tag === 'REFERENCE' ? ' (참고)' : t.source_tag === 'REAL' ? '' : ' (가상)'}</span>
                      {lk && <span className={`${CHIP} border bg-white ${t.lockout_level === 'FULL' ? 'border-slate-700 font-bold text-slate-800' : 'border-slate-300 text-slate-700'}`}>🔒 {lk}</span>}
                      <span className={`${CHIP} ${t.default_role === 'MNT' ? 'bg-slate-100 text-slate-600' : 'bg-[#e8f6fa] text-[#0f6f86]'}`}>{t.default_role === 'MNT' ? '보전' : '작업자'}</span>
                    </span>
                    {lastCell(t)}
                  </li>);
              })}</ul>}
            </section>
          );
        })}

        {/* 오늘 실시 기록 */}
        <section className="flex flex-col gap-2" aria-label="오늘 실시 기록">
          <SecHead title="오늘 실시 기록" right={<>
            {recs.some((r) => r.status === 'DRAFT' && !ok[String(r.pm_record_id)]) && <span className={`${CHIP} bg-[#fff1d1] text-[#9a6200]`}>확인 필요 {recs.filter((r) => r.status === 'DRAFT' && !ok[String(r.pm_record_id)]).length}</span>}
            <span className={`${CHIP} bg-white text-slate-600`}>{recs.length}건</span>
          </>} />
          <div className="rounded-lg border border-slate-200 px-3 py-2">
          {recs.length === 0 ? <p className="text-[14px] text-slate-500">오늘 이 설비에서 한 정비가 아직 없습니다</p> : <ul>{recs.map((r) => {
            const k = String(r.pm_record_id), draft = r.status === 'DRAFT' && !ok[k];
            return (
              <li key={k} className="grid grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-3 border-t border-dashed border-slate-200 py-1.5 text-[14px] first:border-t-0">
                <span className="font-mono font-semibold">{hm(r.done_at)}</span>
                <span className="min-w-0">{nameOfTask(r.pm_task_id)}<span className="block text-[12px] text-slate-500">{userName(r.done_by)} · 결과 {RESULT[r.result] ?? r.result}{r.memo ? ` · ${r.memo}` : ''}</span></span>
                <span className="flex items-center gap-2">
                  {draft ? <span className={`${CHIP} bg-[#fff1d1] text-[#9a6200]`}>확인 필요</span> : <span className={`${CHIP} bg-[#e0f2e8] text-[#127a46]`}>✓ {ok[k] ? `확인됨 (${userName(ok[k])})` : '확정'}</span>}
                  {canDo && draft && <button onClick={() => setOk((o) => ({ ...o, [k]: user.id }))} className="h-9 rounded border border-slate-300 px-2 text-[12px]">확인</button>}
                </span>
              </li>);
          })}</ul>}
          </div>
        </section>
      </div>

      {/* 오른쪽 정비 진행 3단계 */}
      <aside className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 lg:sticky lg:top-0" aria-label="정비 진행">
        <h3 className="text-[16px] font-bold">정비 진행 <span className="font-mono text-[13px] font-normal text-slate-500">{eq}</span></h3>
        {!canDo ? (<>
          <span className={`${CHIP} w-fit bg-slate-200 text-slate-600`}>보기 전용</span>
          <p className="text-[13px] text-slate-500">정비 시작·끝과 실시 기록은 보전 담당자가 합니다.</p>
          {w && <div className="rounded-lg border border-slate-200 bg-white p-2"><div className="text-[12px] text-slate-500">정비 예정</div><b>▨ {winText(w)} · {untilText(w)}</b></div>}
        </>) : (<>
          <div className="grid grid-cols-[28px_1fr] gap-2">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full font-mono text-[13px] font-bold ${stepCls(1)}`}>{step > 1 ? '✓' : '1'}</span>
            <div className="flex min-w-0 flex-col gap-1.5"><b className="text-[14px]">항목 고르기 · {picked.length}개</b>
              {picked.length ? (<>
                <ul className="list-disc pl-4 text-[13px]">{picked.slice(0, 4).map((t) => <li key={t.pm_task_id}>{t.item_name}</li>)}{picked.length > 4 && <li>외 {picked.length - 4}개</li>}</ul>
                <div className="rounded-lg border border-slate-300 bg-white p-2"><div className="text-[12px] text-slate-500">필요한 잠금·표지 (고른 것 중 가장 높은 수준)</div><b className="text-[15px]">{topLock !== 'NONE' ? `🔒 ${LOCK[topLock]?.[0] ?? topLock}` : '필요 없음'}</b></div>
                {picked.some((t) => t.default_role === 'OPR') && <p className="text-[12px] text-slate-500">작업자 항목 {picked.filter((t) => t.default_role === 'OPR').length}개 포함 — 실시자를 그 작업자로 고르면 기록자({user.name})는 따로 남습니다</p>}
                {!isMaint && <button onClick={() => setPick(new Set())} className="h-9 w-fit rounded-md border border-dashed border-slate-400 px-3 text-[13px]">고른 것 모두 풀기</button>}
              </>) : <p className="text-[13px] text-slate-500">왼쪽 목록에서 할 항목을 고르세요. 지남·오늘 항목부터 보입니다.</p>}
            </div>
          </div>
          <div className="grid grid-cols-[28px_1fr] gap-2">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full font-mono text-[13px] font-bold ${stepCls(2)}`}>{step > 2 ? '✓' : '2'}</span>
            <div className="flex flex-col gap-1.5"><b className="text-[14px]">정비 시작</b>
              {isMaint ? <p className="rounded-lg border border-[#0f9fbd] bg-white p-2 text-[13px]">▨ 지금 정비 중 — 설비 상태가 정비로 기록되고 고장으로 세지 않습니다</p> : (<>
                <label className="flex items-center gap-2 text-[13px]">예상 <input type="number" min={5} step={5} value={mins} onChange={(e) => setMins(Number(e.target.value) || 60)} className="h-10 w-20 rounded border border-slate-300 bg-white px-2" />분</label>
                <button disabled={picked.length === 0} onClick={() => call('maint/pm-start', { minutes: mins, pm_task_ids: [...pick] }, `${eq} 정비 시작 — 설비 상태 정비(MAINT), 고장으로 세지 않음`)} className={DARK}>정비 시작</button>
              </>)}
            </div>
          </div>
          <div className="grid grid-cols-[28px_1fr] gap-2">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full font-mono text-[13px] font-bold ${stepCls(3)}`}>3</span>
            <div className="flex min-w-0 flex-col gap-1.5"><b className="text-[14px]">정비 끝 · 실시 기록</b>
              <label className="flex items-center gap-2 text-[13px]">실시자 <select value={doneBy} onChange={(e) => setDoneBy(e.target.value)} className="h-10 min-w-0 flex-1 rounded border border-slate-300 bg-white">{USERS.filter((u) => u.role === 'MNT' || u.role === 'OPR').map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
              <PartsPicker value={parts} onChange={setParts} />
              <button disabled={!isMaint && pick.size === 0} onClick={() => { void call('maint/pm-end', { pm_task_ids: [...pick], done_by: doneBy, items: parts.map((p) => ({ item_no: p.item, qty: p.qty })) }, `${eq} 정비 끝 · 실시 기록 ${pick.size}건 · 소모품 차감`); setPick(new Set()); setParts([]); }} className={DARK}>정비 끝 · 실시 기록{pick.size ? ` (${pick.size})` : ''}</button>
            </div>
          </div>
        </>)}
      </aside>
    </div>
  );
}
