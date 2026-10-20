'use client';
// 화면 틀(UI설계서 2.1)과 화면 이동 — 데이터적용본. 값은 모두 시연 데이터 서버(생성기 실시간 모드 10/1 + 과거 기록 9월)에서 온다.
// 3D 장면(FactoryDashboard)은 로그인한 뒤 한 번만 만들고, 실시간(또는 다시 보기) 값을 applyLive로 넣는다.
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MachineId } from '@/components/types';
import { ID_OF, LAYOUT, LEGEND, MACHINES, type Role } from './data';
import { Ctx, DEFAULT_SETTINGS, type AppCtx, type History, type Inv, type Screen, type Settings } from './ctx';
import { api, md, SIM, simIso, tsOf, useFetch, useLive, useLocal, usePersist, type SimEvent } from './live';
import { askGuideCard } from './assistText';
import { ALARMS, SHIFT_NAME, USERS, homeScreen, levelOfSev, type AlertRec, type Notice, type UserRec } from './model';
import { derive, fromEvents, fromPast, repeatOf, type RuleCtx } from './rules';
import { LOCK } from './Safety';
import { nextNo, pad, rev, type SimpleRecord, type StopReason, type WorkOrder, type WorkRecord } from './workflow';
import { Eve, Robot, type EveTab } from './Eve';
import Briefing from './Briefing';
import CardScreen, { CardList } from './CardScreen';
import DocBox from './DocBox';
import FieldStrip from './FieldStrip';
import Layout2D from './Layout2D';
import Login from './Login';
import Logo from './Logo';
import Panels from './Panels';
import Popup from './Popup';
import SimPanel from './SimPanel';
import SimpleRecordScreen from './SimpleRecordScreen';
import StopsScreen from './StopsScreen';
import WorkOrderScreen from './WorkOrderScreen';
import WorkRecordScreen from './WorkRecordScreen';
import { ReplayScreen } from './ReplayScreen';
import { DailyReportScreen, ShiftReportScreen } from './Reports';
import { RevisionsScreen } from './Revisions';
import { LotScreen } from './LotScreen';
import { QualityScreen } from './QualityScreen';
import { InventoryScreen } from './InventoryScreen';
import { ToolsScreen } from './ToolsScreen';
import { EQS, PM_ALL, PmAll, PmScreen } from './PmScreen';
import { DocsScreen, SourcePopup } from './DocsScreen';
import { SettingsScreen } from './SettingsScreen';

const FactoryDashboard: any = dynamic(() => import('@/components/FactoryDashboard'), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center gap-2 bg-[#e9ecef]"><div className="h-3 w-48 animate-pulse rounded bg-slate-300" /><span className="text-[13px] text-slate-500">3D 불러오는 중…</span></div>,
});

const TITLE: Record<Screen, string> = {
  line: '3D 라인 뷰', layout2d: '3D 라인 뷰 · 2D 배치도', field: '현장 모니터', cards: '지침카드', card: '지침카드', wo: '정비 작업지시서', wr: '작업기록서', sr: '간이 작업기록',
  stops: '정지 사유', docs: '문서함', replay: '다시 보기', shift: '교대 보고서', daily: '일일 보고서', revs: '수정 이력', lots: '로트 추적', quality: '검사 기록',
  inventory: '재고', tools: '공구 수명', pm: '예방 정비 일정', idocs: '사내 문서', settings: '설정',
};
// 메뉴 (페이지구조 v3 5.1). 권한 없는 페이지는 흐리게 (N3) — 열 수 있는 역할 목록, 없으면 전원
const MENU_V3: [string, Screen | 'home', Role[]?][] = [
  ['홈', 'home'], ['지침카드', 'cards'], ['문서함', 'docs'], ['로트 추적', 'lots'], ['품질', 'quality', ['OPR', 'SUP', 'MGR']], ['재고', 'inventory'], ['공구 수명', 'tools'],
  ['예방 정비', 'pm', ['MNT', 'SUP', 'MGR']], ['정지 사유', 'stops'], ['다시 보기', 'replay'], ['현장 모니터', 'field'], ['설정', 'settings', ['MGR']],
];
// 문서함 카테고리 (v3 문서함 8개) — 고르면 오른쪽에 그 화면. 문서 하나를 열어도 문서함 안에 보임
const DOC_CATS: [string, Screen, string | null, Role[]?][] = [
  ['작업지시서', 'docs', '작업지시서'], ['작업기록서', 'docs', '작업기록서', ['MNT', 'SUP', 'MGR']], ['간이 작업기록', 'docs', '간이 작업기록'],
  ['교대 보고서', 'docs', '교대 보고서'], ['일일 보고서', 'docs', '일일 보고서', ['MNT', 'SUP', 'MGR']],
  ['수정 이력', 'revs', null], ['사내 문서', 'idocs', null],
];
const DOC_OF: Partial<Record<Screen, string>> = { wo: '작업지시서', wr: '작업기록서', sr: '간이 작업기록', shift: '교대 보고서', daily: '일일 보고서', revs: '수정 이력', idocs: '사내 문서' };
// 품질 카테고리 — 문서함과 같은 모양(왼쪽 목록 + 오른쪽 화면). 품질 화면이 늘면 여기에 한 줄씩 더한다
const QUAL_CATS: [string, Screen, string | null][] = [['검사 기록', 'quality', null]];
const QUAL_OF: Partial<Record<Screen, string>> = { quality: '검사 기록' };
const SCREENS: Screen[] = ['line', 'layout2d', 'field', 'cards', 'card', 'wo', 'wr', 'sr', 'stops', 'docs', 'replay', 'shift', 'daily', 'revs', 'lots', 'quality', 'inventory', 'tools', 'pm', 'idocs', 'settings'];
const urlOf = (s: Screen, k: string | null) => (s === 'line' ? '/' : `/${s}`) + (k ? `?k=${encodeURIComponent(k)}` : '');
function screenFromUrl(role: Role): [Screen, string | null] {
  if (typeof window === 'undefined') return [homeScreen(role), null];
  const p = location.pathname.replace(/^\/+|\/+$/g, '') as Screen;
  const lock = MENU_V3.find(([, s2]) => s2 === p)?.[2]; // 권한 없는 화면 주소로 들어오면 홈
  if (!SCREENS.includes(p) || (lock && !lock.includes(role))) return [homeScreen(role), null];
  return [p, new URLSearchParams(location.search).get('k')];
}
// 현장 화면 공정 묶음 = 작업자 1명의 담당 구역 (app_user.csv home_process_code, 사용자 선택 2026-10-19)
const ZONES: [string, string[], MachineId[]][] = [['1·2공정', ['OP-10', 'OP-20'], ['saw', 'mil']], ['3공정', ['OP-30'], ['vf1', 'vf2']], ['4·5공정', ['OP-40', 'OP-50'], ['wsh', 'cmm']]];
// 왼쪽 메뉴 묶음 (사용자 요청 2026-10-19): 홈 / 생산(로트·현장) / 정비(정지·재생·예방 정비) / 품질 / 재고(공구) / 문서(+지침카드, 2026-10-20) / 설정.
// 묶음 안 화면은 상단 바 가운데 탭으로 바꾼다. related = 그 묶음에서 열리는 다른 화면
const GROUPS: { label: string; subs: [string, Screen, Role[]?, (string | null)?][]; related?: Screen[] }[] = [
  { label: '홈', subs: [['3D 라인', 'line']], related: ['layout2d'] },
  { label: '생산', subs: [['로트 추적', 'lots'], ['현장 모니터', 'field']] },
  { label: '정비', subs: [['정지 사유', 'stops'], ['다시 보기', 'replay'], ['예방 정비', 'pm', ['MNT', 'SUP', 'MGR']]] },
  { label: '품질', subs: [['검사 기록', 'quality', ['OPR', 'SUP', 'MGR']]] },
  { label: '재고', subs: [['재고', 'inventory'], ['공구 수명', 'tools']] },
  { label: '문서', subs: [...DOC_CATS.map(([n, s2, k2, roles]) => [n, s2, roles, k2] as [string, Screen, Role[]?, (string | null)?]), ['지침카드', 'cards']], related: ['docs', 'wo', 'wr', 'sr', 'shift', 'daily', 'revs', 'idocs', 'card'] }, // 지침카드는 정비에서 문서로 옮김 (사용자 요청 2026-10-20)
  { label: '설정', subs: [['설정', 'settings', ['MGR']]] },
];
const btn = 'h-11 rounded-md border border-slate-300 bg-white px-3 text-[14px] font-semibold hover:bg-slate-50';

export default function App() {
  const [user, setUser] = useState<UserRec | null>(null);
  if (!user) return <Login onLogin={setUser} />;
  return <Frame key="session" user={user} setUser={setUser} />;
}

function Frame({ user, setUser }: { user: UserRec; setUser: (u: UserRec | null) => void }) {
  const live = useLive();
  const { twin, connected } = live;
  const runId = twin?.run_id ?? null;
  const apiRef = useRef<any>(null);
  const api3d = () => apiRef.current;
  const role = user.role;

  // ---------- 이 브라우저에 남기는 문서·알림 (시연 회차별) ----------
  const [wos, setWos] = usePersist<WorkOrder[]>('wos', [], runId);
  const [wrs, setWrs] = usePersist<WorkRecord[]>('wrs', [], runId);
  const [srs, setSrs] = usePersist<SimpleRecord[]>('srs', [], runId);
  const [notices, setNotices] = usePersist<Notice[]>('notices', [], runId);
  const [handledA, setHandledA] = usePersist<Record<string, { by: string; ts: number }>>('handled', {}, runId);
  const [acked, setAcked] = usePersist<Record<string, string[]>>('acked', {}, runId); // 사용자별 긴급 팝업 [확인]
  const [stopReasons, setStopReasons] = usePersist<Record<string, StopReason>>('stops', {}, runId);
  const [settings, setSettings] = useLocal<Settings>('settings', DEFAULT_SETTINGS);
  const [seenBrief, setSeenBrief] = useLocal<Record<string, string>>('briefSeen', {});

  // ---------- 서버에서 가끔 받는 값 ----------
  const pastOpen = useFetch<{ notifications: (Record<string, string> & { to: string[] })[] }>(runId ? 'notifications/past-open' : null, 0, [runId]);
  const hist = useFetch<History>('maint/history');
  const invF = useFetch<Inv>(connected ? 'inventory' : null, 10000);
  const pmF = useFetch<AppCtx['pm']>(connected ? 'maint/pm-schedule' : null, 15000);
  const shiftF = useFetch<{ reports: Record<string, any>[] }>(connected ? 'reports/shift' : null, 10000);
  const dailyF = useFetch<{ reports: Record<string, any>[] }>(connected ? 'reports/daily' : null, 20000);
  const cmmF = useFetch<RuleCtx['cmm']>(connected ? 'inspection/cmm-imports' : null, 15000);
  const qualF = useFetch<RuleCtx['quality']>(connected ? 'quality/summary' : null, 30000);
  const setF = useFetch<{ rules: AppCtx['rules'] }>(connected ? 'settings' : null, 15000);
  const rules = setF.data?.rules ?? { repeat_days: 7, repeat_count: 3, target_risk_pct: 90, repeat2_days: 7, burst: '1분 안 3번 이상', flood: '10분 10건 / 5건' };

  // ---------- 알람 기록 = 시뮬레이터 알람 이벤트 ----------
  const alerts: AlertRec[] = useMemo(() => (twin?.alarms ?? []).map((e) => {
    const id = `a-${e.alarm_event_id}`, h = handledA[id];
    const guideDone = e.severity === 'GUIDE' && !!e.cleared_at; // 조작 안내는 작업자가 고치면(알람 해제) 처리
    return {
      id, eventId: e.alarm_event_id, prevId: e.prev_alarm_event_id, machine: ID_OF[e.equipment_id], code: e.alarm_code,
      kind: e.severity === 'STOP' ? 'alarm' : e.severity === 'WARN' ? 'warn' : 'guide', level: levelOfSev(e.severity), alarm: ALARMS[e.alarm_code] ?? null,
      time: e.occurred_at, ts: tsOf(e.occurred_at), cleared: e.cleared_at, lot: e.lot_no, scenario: e.scenario_code,
      handled: !!h || guideDone, handledTs: h?.ts, handledBy: h?.by ?? (guideDone ? '알람 해제' : undefined),
    } as AlertRec;
  }), [twin?.alarms, handledA]);

  // 새 알람 → OP-30 정지 등급이면 작업지시서 초안 + 문서 알림, 반복 알람 판단
  const seenAlarm = useRef<Set<number>>(new Set());
  const ruleCtx = (): RuleCtx => ({
    twin, inv: invF.data, pm: pmF.data as RuleCtx['pm'], wos, shiftReports: shiftF.data?.reports as RuleCtx['shiftReports'] ?? null,
    dailyReports: dailyF.data?.reports as RuleCtx['dailyReports'] ?? null, cmm: cmmF.data, quality: qualF.data, alerts,
    pastAlarms: (hist.data?.alarms ?? []).map((a) => ({ equipment_id: a.equipment_id, alarm_code: a.alarm_code, occurred_at: a.occurred_at })), notices, rules,
  });
  const addNotices = useCallback((ns: Notice[]) => {
    if (!ns.length) return;
    setNotices((l) => { const have = new Set(l.map((x) => x.id)); const n = ns.filter((x) => !have.has(x.id)); return n.length ? [...l, ...n] : l; });
  }, [setNotices]);
  useEffect(() => { seenAlarm.current = new Set(); }, [runId]);
  useEffect(() => {
    if (!twin || !hist.data) return;
    const fresh = alerts.filter((a) => !seenAlarm.current.has(a.eventId));
    if (!fresh.length) return;
    fresh.forEach((a) => seenAlarm.current.add(a.eventId));
    const add: Notice[] = [];
    fresh.forEach((a) => {
      if (a.alarm?.steps.length && (a.kind === 'alarm' || a.kind === 'warn')) askGuideCard(a.code, a.alarm.steps).catch(() => undefined); // 카드가 열리기 전에 비서가 풀어 쓸 시간을 번다 (2026-10-17, 꺼져 있으면 아무 일도 없음)
      if (a.kind === 'alarm' && MACHINES[a.machine].op === 'OP-30' && a.alarm && !wos.some((w) => w.alertId === a.id)
        && !wos.some((w) => w.machine === a.machine && w.state !== 'done' && w.state !== 'cancelled')) {
        createWo(a, 'STOP_ALARM');
      }
      const r = repeatOf(a, ruleCtx());
      if (r) {
        add.push(r);
        if (r.rule === 'REPEAT_ALARM_2') createWo(a, 'REPEAT_2');
        if (r.rule === 'CAUSE_CHECK_REQUEST') openSimple(a.id, 'cause', false);
      }
    });
    addNotices(add);
  }, [alerts, hist.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const createWo = (a: AlertRec, trigger: WorkOrder['trigger']) => {
    const al = a.alarm!;
    setWos((w) => {
      if (w.some((x) => x.alertId === a.id && x.trigger === trigger)) return w;
      const no = `MW-${pad(950 + w.length)}`;
      const wo: WorkOrder = {
        no, alertId: a.id, machine: a.machine, code: a.code, created: a.time, state: 'draft', version: 0, trigger, lot: a.lot,
        title: trigger === 'REPEAT_2' ? `${MACHINES[a.machine].name} 알람 ${a.code} 반복 — 원인 점검 (2단계)` : `${MACHINES[a.machine].name} 알람 ${a.code} (${al.nameKo.replace(/\(.*\)/, '')}) 점검`,
        symptom: al.symptom + (al.chain ? ` — 연쇄 알람 ${al.chain}` : ''), steps: al.maint.length ? al.maint : al.steps, parts: expectedParts(a.code), assignee: null, edited: [],
        revisions: rev([], '프로그램 초안', '프로그램', 'PROGRAM'),
      };
      addNotices([{ id: `WO_DRAFT_READY:${no}`, rule: 'WO_DRAFT_READY', ruleName: '작업지시서 초안 검토', level: '참고', rank: '4', at: a.time, ts: a.ts, text: '작업지시서 초안을 썼어요. 검토해 주세요', roles: ['MNT'], delivery: 'BUBBLE', handled: false, open: { screen: 'wo', key: no } }]);
      return [...w, wo];
    });
  };
  // 비서가 다듬은 작업지시서 제목·증상 (2026-10-17). 시연 서버가 MOM_LLM_COMPOSE=1로 비서를 부를 때만 채워지고, 꺼져 있거나 실패하면 지금 기본 문장 그대로다.
  // 사람이 손대기 전(처음 버전·이력 1개)의 초안만 바꾸고, 바꿔도 버전은 올리지 않는다. 5초마다 최대 40번만 묻는다 (안 되면 그냥 기본 문장).
  const woAsked = useRef<Record<string, { at: number; n: number }>>({});
  useEffect(() => { woAsked.current = {}; }, [runId]);
  useEffect(() => {
    const timer = setInterval(() => {
      wos.forEach((w) => {
        if (w.state !== 'draft' || w.version !== 0 || w.revisions.length !== 1 || w.llm) return;
        const t = woAsked.current[w.no] ?? { at: 0, n: 0 };
        if (t.n >= 40 || Date.now() - t.at < 5000) return;
        woAsked.current[w.no] = { at: Date.now(), n: t.n + 1 };
        api<{ ready: boolean; title?: string; symptom?: string }>('assist/work-order-text', { no: w.no, title: w.title, symptom: w.symptom })
          .then((r) => {
            if (!r.ready || !r.title || !r.symptom) return;
            setWos((list) => list.map((x) => (x.no === w.no && x.state === 'draft' && x.version === 0 && x.revisions.length === 1 && !x.llm && x.title === w.title && x.symptom === w.symptom
              ? { ...x, title: r.title!, symptom: r.symptom!, llm: true, revisions: x.revisions.map((v, i) => (i === 0 ? { ...v, kind: 'AI비서 초안', by: '비서' } : v)) } : x)));
          })
          .catch(() => undefined);
      });
    }, 3000);
    return () => clearInterval(timer);
  }, [wos]); // eslint-disable-line react-hooks/exhaustive-deps
  // 예상 부품: 9월 같은 알람 작업기록서에 쓴 부품 (C-07, 제안 엔진 대신 기록)
  const expectedParts = (code: string): string[] => {
    const h = hist.data; if (!h) return [];
    const recs = h.work_records.filter((r) => { const al = h.alarms.find((x) => x.alarm_event_id === r.alarm_event_id); return al?.alarm_code === code; });
    return Array.from(new Set(recs.flatMap((r) => (h.parts[r.record_no] ?? []).map((p) => p.item_no))));
  };

  // 사건 → 알림 (공구 수명 90%, 병목 발생·이동)
  useEffect(() => live.onEvents((evs: SimEvent[]) => addNotices(fromEvents(evs))), [live, addNotices]);
  // 9월 미처리 알림 → 10/1 시작 상태
  useEffect(() => { if (pastOpen.data) addNotices(pastOpen.data.notifications.map(fromPast)); }, [pastOpen.data, addNotices]);
  // 상태로 판단하는 알림 (5초마다)
  useEffect(() => {
    if (!twin) return;
    const t = setTimeout(() => {
      const { add, resolve } = derive(ruleCtx());
      addNotices(add);
      if (resolve.length) setNotices((l) => (l.some((x) => resolve.includes(x.id) && !x.handled) ? l.map((x) => (resolve.includes(x.id) && !x.handled ? { ...x, handled: true, handledBy: '조건 풀림 (자동)', handledAt: simIso() } : x)) : l));
    }, 300);
    return () => clearTimeout(t);
  }, [twin?.clock.sim_at, invF.data, pmF.data, shiftF.data, dailyF.data, cmmF.data, qualF.data, wos]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- 3D ----------
  const [replayFrame, setReplay] = useState<unknown | null>(null);
  const [fail3d, setFail3d] = useState<string | null>(null);
  const [folded, setFolded] = useState<string[]>([]); // 왼쪽 메뉴에서 접어 둔 묶음 (사용자 요청 2026-10-19)
  const [snapSel, setSnapSel] = useState<MachineId | null>(null);
  useEffect(() => { const a = api3d(); if (a && a.applyLive) a.applyLive(replayFrame ?? (connected ? twin : null)); }, [twin, connected, replayFrame]);
  const onReady = useCallback((i: any) => { apiRef.current = i; i.applyLive && i.applyLive(null); }, []);
  const cardText = useCallback((mid: MachineId, st: string) => {
    const E = twin && MACHINES[mid].eq ? twin.equipment[MACHINES[mid].eq!] : null;
    if (!E) return '기록 없음';
    if (E.alarm) { const a = ALARMS[E.alarm.alarm_code]; return `${E.alarm.alarm_code} · ${a?.nameKo ?? '알람 코드집에 없음'}`; }
    return E.reason_name ? `${E.reason_code} ${E.reason_name} · ${E.minutes}분째` : st === 'RUN' ? '' : `${E.minutes}분째`;
  }, [twin]);
  const alarmText = useCallback((mid: MachineId) => cardText(mid, 'ALARM'), [cardText]);
  const cmmCard = useMemo(() => {
    if (!twin) return null;
    const it: Record<number, [string, string, string]> = { 1: ['Ø45 H7', '45.000', '+0.025/0'], 2: ['길이', '150.0', '±0.5'], 8: ['폭', '55.0', '±0.3'], 3: ['두께', '12.0', '±0.2'] };
    const rows = Object.entries(it).map(([k, [n, nom]]) => {
      const m = [...twin.last_measure].reverse().find((x) => x.item_seq === Number(k) && (x.position == null || x.position === 'MID'));
      return [n, nom, m ? String(m.measured_value) : '—', m ? (m.judgement === 'PASS' ? '합격' : '불합격') : '—'];
    });
    const today = twin.process['OP-50'];
    return { rows, stats: [['오늘 OP-50', `${today?.pq ?? 0}개`], ['불합격(폐기)', String(today?.scrap ?? 0), (today?.scrap ?? 0) > 0 ? '#c62a2f' : undefined], ['최근 측정', twin.last_measure.length ? twin.last_measure[twin.last_measure.length - 1].lot_no : '—']] };
  }, [twin]);

  // ---------- 화면 이동 ----------
  const [screen, setScreen] = useState<Screen>(() => screenFromUrl(role)[0]);
  const [key, setKey] = useState<string | null>(() => screenFromUrl(role)[1]);
  const hist2 = useRef<[Screen, string | null][]>([]);
  const go = useCallback((s: Screen, k: string | null = null) => { hist2.current.push([screen, key]); setScreen(s); setKey(k); setMenu(false); setDemo(false); }, [screen, key]);
  const back = () => { const p = hist2.current.pop(); if (p) { setScreen(p[0]); setKey(p[1]); } else setScreen(homeScreen(role)); };
  const firstUser = useRef(true);
  useEffect(() => { if (firstUser.current) { firstUser.current = false; return; } setScreen(homeScreen(role)); setKey(null); setSide(null); setMenu(false); hist2.current = []; }, [user.id]); // eslint-disable-line react-hooks/exhaustive-deps
  // 화면마다 주소: / · /inventory · /lots ... (?k= 문서 번호). 3D는 그대로 살아 있음
  useEffect(() => { const u = urlOf(screen, key); if (u !== location.pathname + location.search) history.pushState(null, '', u); }, [screen, key]);
  useEffect(() => {
    const onPop = () => { const [s2, k2] = screenFromUrl(role); setScreen(s2); setKey(k2); };
    window.addEventListener('popstate', onPop); return () => window.removeEventListener('popstate', onPop);
  }, [role]);

  const [menu, setMenu] = useState(false);
  const [demo, setDemo] = useState(false);
  const [setOpen, setSetOpen] = useState(false);
  const [acct, setAcct] = useState(false);
  const [side, setSide] = useState<EveTab | null>(null);
  const [eveI, setEveI] = useState(0);
  const [zone, setZone] = useState<string | null>(null);
  const curGroup = GROUPS.find((g) => g.subs.some(([, s2]) => s2 === screen) || g.related?.includes(screen));
  // 현장 화면에 들어오면 작업자는 자기 담당 구역으로 줌인
  useEffect(() => { if (screen !== 'field') return; const z = role === 'OPR' ? ZONES.find(([, ops]) => ops.some((o) => user.procs.includes(o))) : undefined; if (!z) { setZone(null); return; } const t = setTimeout(() => { setZone(z[0]); api3d()?.frameGroup(z[2]); }, 500); return () => clearTimeout(t); }, [screen]); // eslint-disable-line react-hooks/exhaustive-deps // 3D 카드 이브 띠에서 보고 있는 소식 번호
  const closeSide = useCallback(() => setSide(null), []);
  const [source, setSource] = useState<[string, string] | null>(null);
  const [toastMsg, setToast] = useState('');
  const toast = useCallback((m: string) => { setToast(m); setTimeout(() => setToast(''), 4500); }, []);

  // ---------- 문서 열기 ----------
  const openCard = (id: string) => { setAcked((s) => ({ ...s, [user.id]: [...(s[user.id] ?? []), id] })); go('card', id); };
  const openWo = (no: string) => { setNotices((l) => l.map((x) => ((x.rule === 'WO_ASSIGNED' || x.rule === 'WO_DRAFT_READY') && x.open?.key === no && x.roles.includes(role) && (!x.userIds || x.userIds.includes(user.id)) ? { ...x, handled: true, handledBy: user.name, handledAt: simIso() } : x))); go('wo', no); };
  const openRecord = (woNo: string) => {
    const wo = wos.find((w) => w.no === woNo); if (!wo) return;
    if (!wrs.some((r) => r.woNo === woNo)) {
      const rec: WorkRecord = { no: nextNo('MR', wrs), woNo, state: 'draft', memo: '', cause: '', action: '', parts: [], stepChecks: wo.steps.map(() => false), lock: LOCK.map(() => false), start: '', end: '', revisions: [] };
      setWrs((l) => [...l, rec]); setWos((l) => l.map((x) => (x.no === woNo ? { ...x, recordNo: rec.no } : x)));
    }
    go('wr', woNo);
  };
  function openSimple(alertId: string, kind: 'alarm' | 'cause' = 'alarm', nav = true) {
    const al = alerts.find((x) => x.id === alertId); if (!al) return;
    let no = srs.find((r) => r.alertId === alertId && r.kind === kind)?.no;
    if (!no) {
      no = nextNo('MR-S', srs);
      const r: SimpleRecord = { no, alertId, machine: al.machine, kind, code: al.code, state: 'open', action: '', parts: [], lock: LOCK.map(() => false), memo: '', revisions: [] };
      setSrs((l) => [...l, r]);
    }
    if (nav) go('sr', no);
  }
  const restoreMachine = async (m: MachineId) => {
    const eq = MACHINES[m].eq; if (!eq) return;
    try { await api('maint/work-records/confirm', { equipment_id: eq, by: user.id }); toast(`${eq} 복귀 — 작업기록서 확정 (시뮬레이터)`); }
    catch (e) { if ((e as { code?: string }).code !== 'INVALID_STATE') toast((e as Error).message); }
    live.refresh();
  };

  const myNotices = notices.filter((n) => role === 'MGR' || (n.roles.includes(role) && (!n.userIds || n.userIds.includes(user.id) || n.past)));
  const ctx: AppCtx = {
    user, role, setUser, twin, connected, lastOk: live.lastOk, alerts, notices, myNotices, wos, wrs, srs,
    putWo: (w) => setWos((l) => l.map((x) => (x.no === w.no ? w : x))), putWr: (w) => setWrs((l) => l.map((x) => (x.no === w.no ? w : x))), putSr: (r) => setSrs((l) => l.map((x) => (x.no === r.no ? r : x))),
    stopReasons, setStopReasons,
    addNotice: (n) => addNotices([n]),
    handleNotice: (id, plan) => setNotices((l) => l.map((x) => (x.id === id ? { ...x, handled: true, handledBy: user.name, handledAt: simIso(), plan } : x))),
    markAlert: (ids, by) => setHandledA((h) => ({ ...h, ...Object.fromEntries(ids.map((i) => [i, { by, ts: Date.now() }])) })),
    screen, key, go, back, openCard, openWo, openRecord, openSimple: (id, kind) => openSimple(id, kind ?? 'alarm'),
    openSource: (doc, sec) => setSource([doc, sec]), openReplay: (at) => go('replay', at),
    selectMachine: (m) => { if (m) api3d()?.select(m); else api3d()?.setView('front'); setSnapSel(m); }, selected: snapSel,
    toast, settings, setSettings,
    inv: invF.data, reloadInv: invF.reload, history: hist.data, pm: pmF.data, reloadPm: pmF.reload,
    shiftReports: shiftF.data?.reports ?? null, dailyReports: dailyF.data?.reports ?? null, reloadReports: () => { shiftF.reload(); dailyF.reload(); },
    rules, restoreMachine, setReplay,
  };

  // ---------- 긴급 팝업·말풍선 ----------
  const open = alerts.filter((a) => !a.handled);
  const myAck = new Set(acked[user.id] ?? []);
  const emergencies = open.filter((a) => a.level === '긴급' && !myAck.has(a.id));
  const band = open.find((a) => a.level === '긴급');
  // 3D 카드 안 이브 띠 (사용자 요청 2026-10-18): 처리 안 된 긴급·주의를 긴급부터 — 문장은 알람 코드집(DOC-02·03)으로 만든 규칙 문장
  const eveList = open.filter((a) => a.level !== '참고').sort((a, b) => (a.level === b.level ? b.ts - a.ts : a.level === '긴급' ? -1 : 1));
  const eveCur = eveList.length ? eveList[eveI % eveList.length] : null;
  const eveRgb = !eveCur ? null : eveCur.level === '긴급' ? '229,72,77' : '240,180,41';
  const docBubbles = myNotices.filter((n) => n.delivery === 'BUBBLE' && !n.handled);
  const briefBubble = !!twin && seenBrief[user.id] !== twin.shift.shift_id; // 교대 시작 뒤 첫 로그인 때 (9.9)
  const sysBubble = band && screen !== 'line' ? `⚠ 긴급 · ${MACHINES[band.machine].name} ${band.alarm ? `${band.code} ${band.alarm.nameKo}` : band.code} · ${band.time.slice(11, 16)}` : fail3d ? `3D가 느려서 2D 배치도로 바꿨어요. 열기를 누르면 3D로 돌아가요` : null;
  const bubbleText = side ? null : sysBubble ?? (docBubbles.length > 1 ? `확정·검토할 문서 ${docBubbles.length}건` : docBubbles[0]?.text ?? (briefBubble ? '이번 교대 브리핑이 준비됐어요' : null));
  const onBubble = () => {
    if (band && screen !== 'line') { openCard(band.id); return; }
    if (fail3d) { setFail3d(null); go('line'); return; }
    if (docBubbles.length > 1) { setSide('알림'); return; }
    const d = docBubbles[0];
    if (d?.open) { openNotice(d); return; }
    setSeenBrief((s) => ({ ...s, [user.id]: twin?.shift.shift_id ?? '' })); setSide('브리핑');
  };
  const openNotice = (n: Notice) => {
    const o = n.open; if (!o) return;
    if (o.screen === 'wo' && o.key) openWo(o.key); else go(o.screen as Screen, o.key ?? null);
  };

  // 글자 크기 3단계 (2.4 식: H = D × 0.0058, 픽셀 = H ÷ 한 픽셀 크기) — 화면 설정에서 모니터 크기·거리로 계산해 켠다
  const pxMM = (settings.monitorInch * 25.4 * 0.8716) / (typeof window !== 'undefined' ? window.screen.width || 1920 : 1920);
  const bigPx = Math.round((settings.distanceM * 1000 * 0.0058) / pxMM);
  const bodyPx = Math.round((settings.distanceM * 1000 * 0.00465) / pxMM);
  // 하단: 생산현황 · 작업지시 (v3 3장). 현장 모니터 = 설비 하나만 낮게 (3D를 크게)
  const style: Record<string, string> = { '--panelH': screen === 'field' ? '260px' : 'clamp(270px,34vh,350px)' };
  if (settings.fontScale) { style['--fs-big'] = `${bigPx}px`; style['--fs-body'] = `${bodyPx}px`; }
  const show3D = screen === 'line' || screen === 'field'; // 다시 보기는 3D 대신 카드 라인 (2026-10-17)
  const fieldSel = screen === 'field' && (!!snapSel || !!zone); // 설비를 누르거나 공정 묶음 버튼을 누르면 아래 패널
  const stagePos = screen === 'field' ? { left: 0, top: 0, right: 360, bottom: fieldSel ? 'var(--panelH)' : 0 } : { left: 220, top: screen === 'line' && eveCur ? 128 : 76, right: 12, bottom: 'calc(var(--panelH) + 24px)' }; // 홈: 알람이 있을 때만 이브 띠(76~120)를 3D 카드 바깥 위에 두고 카드는 그 아래부터 — 띠가 천장 표지판을 가리지 않게. 알람이 없으면 띠 없이 3D가 위까지 (2026-10-19)


  return (
    <Ctx.Provider value={ctx}>
      <div className={`relative flex h-screen flex-col overflow-hidden bg-[#e9ecef] text-[#26303a] ${settings.fontScale ? 'fs-scaled' : ''}`} style={{ ...(style as React.CSSProperties), width: side ? 'calc(100% - 444px)' : '100%', transition: 'width .25s ease', marginTop: connected ? 0 : 32, height: connected ? '100vh' : 'calc(100vh - 32px)' }}>{/* 이브 창이 열리면 화면을 왼쪽으로 밀어 자리를 내줌 (사용자 요청 2026-10-19) */}
        {/* 상단 바 (페이지구조 v3 3장): 왼쪽 [≡][주간][날짜][시각] · 오른쪽 계정 [이름 ▾] [시연] [⚙ 화면 설정] */}
        <header className="absolute left-3 right-3 top-3 z-20 flex h-[56px] items-center gap-3 rounded-2xl border border-slate-300 bg-white px-3 shadow-lg">
          <Logo height={24} />
          <span className="whitespace-nowrap text-[15px] text-slate-500">제조운영관리</span>
          <span className={`flex items-baseline gap-2 whitespace-nowrap ${connected ? 'text-[#1f2933]' : 'text-slate-400'}`}>
            {twin ? (<>
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[14px] font-semibold text-slate-600">{twin.clock.sim_at >= twin.shift.end_at ? '휴무' : SHIFT_NAME[twin.shift.shift_type]}</span>
              <b className="font-mono text-[22px] tabular-nums">{md(twin.clock.sim_at)}</b>
              <b className="font-mono text-[26px] tabular-nums">{twin.clock.sim_at.slice(11, 16)}</b>
            </>) : <b className="font-mono text-[22px]">--:--</b>}
          </span>
          <div className="ml-auto flex items-center gap-1 rounded-full border border-slate-300 bg-white p-1">{/* 계정·시연·설정 묶음 (시안 3a) */}
          <div className="relative">
            <button onClick={() => { setAcct((o) => !o); setDemo(false); setSetOpen(false); }} className="flex h-9 items-center gap-1 rounded-full bg-[#ffffff] px-4 text-[14px] font-semibold shadow-sm">
              <span className="font-normal text-slate-500">계정 :</span> {user.name} <span className="text-slate-400">▾</span>
            </button>
            {acct && (
              <div className="absolute right-0 top-[48px] z-30 max-h-[70vh] w-[220px] overflow-y-auto rounded-xl border border-slate-300 bg-white py-1 shadow-lg">
                {USERS.map((u) => <button key={u.id} onClick={() => { setAcct(false); setUser(u); }} className={`flex h-11 w-full items-center px-4 text-left text-[14px] hover:bg-slate-100 ${u.id === user.id ? 'font-bold text-[#5a3bc8]' : ''}`}>{u.name}</button>)}
                <button onClick={() => setUser(null)} className="flex h-11 w-full items-center border-t border-slate-200 px-4 text-left text-[14px] text-slate-500 hover:bg-slate-100">로그아웃</button>
              </div>
            )}
          </div>
          <div className="relative">
            <button onClick={() => { setDemo((d) => !d); setSetOpen(false); setAcct(false); }} className="h-9 rounded-full px-4 text-[14px] font-semibold hover:bg-white/70">시연</button>
            {demo && <SimPanel twin={twin} refresh={live.refresh} toast={toast} api3d={api3d} onClose={() => setDemo(false)} />}
          </div>
          <div className="relative">
            <button onClick={() => { setSetOpen((o) => !o); setDemo(false); setAcct(false); }} className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-white/70" aria-label="화면 설정" title="화면 설정">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
            </button>
            {setOpen && <SettingsPopover settings={settings} setSettings={setSettings} api3d={api3d} bigPx={bigPx} bodyPx={bodyPx} />}
          </div>
          </div>
        </header>

        {!connected && (
          <div className="fixed inset-x-0 top-0 z-[60] flex h-8 items-center justify-center gap-2 bg-[#4b5a69] px-4 text-[14px] font-semibold text-white">
            ⚠ 연결 끊김 — 마지막 갱신 {live.lastOk ? live.lastOk.slice(11, 16) : '없음'} · 시연 데이터 서버(tools/sim_server.py)를 켜 주세요. 숫자는 회색, 3D 설비는 "기록 없음"
          </div>
        )}
        {/* 왼쪽 세로 메뉴 — 항상 보임 (구조 시안) */}
        <nav className="absolute left-3 top-[76px] z-20 flex w-[200px] flex-col overflow-y-auto rounded-3xl border border-slate-300 bg-white p-2 shadow-lg" style={{ maxHeight: 'calc(100vh - 132px)' }}>
          {/* 통합 트리 (사용자 요청 2026-10-19, 시안 7b 모양·색은 그대로): 묶음 이름은 작은 머리글, 세부 화면은 늘 펼쳐 둠 — 세부가 하나뿐인 묶음은 그 자체가 칸, 설정은 맨 아래 */}
          {GROUPS.map((g) => {
            const subs = g.subs.filter(([, , roles]) => !roles || roles.includes(role)), on = g === curGroup, last = g.label === '설정';
            const curDoc = screen === 'docs' ? (key ?? '작업지시서') : DOC_OF[screen];
            if (!subs.length) return null;
            // 큰 묶음 이름은 모두 같은 큰 글씨, 세부 화면은 그보다 작게 (사용자 요청 2026-10-19)
            const HEAD = 'flex h-11 w-full items-center rounded-xl px-3 text-left text-[16px] font-bold';
            const fold = folded.includes(g.label);
            const DOT = "after:ml-auto after:h-1.5 after:w-1.5 after:rounded-full after:bg-[#b79cff] after:content-['']"; // 선택 칸 보라 점 (네온 바이올렛 포인트, 2026-10-19)
            return (
              <div key={g.label} className={last ? 'mt-auto border-t border-slate-200 pt-2' : 'mb-1'}>
                {subs.length === 1
                  ? <button onClick={() => go(subs[0][1], subs[0][3] ?? null)} className={`${HEAD} ${on ? `bg-[#2b3a4a] text-white shadow ${DOT}` : 'text-[#1c2530] hover:bg-[#f3f1fb]'}`}>{g.label}</button>
                  : <>
                  <button onClick={() => setFolded((f) => fold ? f.filter((x) => x !== g.label) : [...f, g.label])} aria-expanded={!fold} className={`${HEAD} text-[#1c2530] hover:bg-[#f3f1fb]`}>
                    {g.label}<span className="ml-auto text-[11px] text-slate-400">{fold ? '▸' : '▾'}</span></button>
                  {!fold && <div className="mb-1 ml-4 flex flex-col gap-0.5 border-l-2 border-slate-200 pl-2">
                    {subs.map(([name, s2, , k2]) => { const sel = s2 === 'cards' ? screen === 'cards' || screen === 'card' : g.label === '문서' ? curDoc === name : screen === s2; return (
                      <button key={name} onClick={() => go(s2, k2 ?? null)} className={`h-8 rounded-lg px-2.5 text-left text-[13px] ${sel ? `flex items-center bg-[#2b3a4a] font-bold text-white shadow ${DOT}` : 'font-medium text-slate-600 hover:bg-[#f3f1fb]'}`}>{name}</button>); })}
                  </div>}</>}
              </div>);
          })}
        </nav>


        {/* 3D 실패·긴급 알림은 이브 말풍선으로, 연결 끊김은 화면 맨 위 띠로 옮김 (2026-10-19) */}

        <div className="flex min-h-0 flex-1 flex-col" style={{ paddingLeft: screen === 'line' || screen === 'replay' ? 0 : 216, paddingTop: screen === 'line' || screen === 'replay' ? 0 : 72 }}>
        {screen !== 'line' && screen !== 'layout2d' && screen !== 'docs' && screen !== 'pm' && !DOC_OF[screen] && !QUAL_OF[screen] && <div className="flex h-11 shrink-0 items-center border-b border-slate-200 bg-white px-4 text-[17px] font-bold">{TITLE[screen]}</div>}
        <div className={`relative min-h-0 flex-1 overflow-hidden ${connected ? '' : 'grayscale-[0.6]'}`}>
          {screen === 'line' && show3D && eveCur && (
            <div className="eve-band absolute z-10 flex h-11 items-center gap-3 rounded-full border-[1.5px] pl-2 pr-1.5 backdrop-blur-sm"
              style={{ left: 220, right: 12, top: 76, ...(eveRgb ? { borderColor: `rgba(${eveRgb},.7)`, background: `linear-gradient(90deg,rgba(${eveRgb},.30) 0%,rgba(${eveRgb},.12) 35%,rgba(255,255,255,.92) 70%)`, boxShadow: `0 0 0 4px rgba(${eveRgb},.18),0 0 26px rgba(${eveRgb},.45)` } : { borderColor: '#d6dade', background: 'rgba(255,255,255,.88)', boxShadow: '0 4px 14px rgba(40,40,50,.12)' }) }}>
              <span role="img" aria-label="이브" className="shrink-0"><Robot size={30} face={!eveCur ? 'happy' : eveCur.level === '긴급' ? 'alarm' : 'warn'} /></span>
              {eveCur ? (<>
                <span className="shrink-0 rounded-full px-2.5 py-0.5 text-[12px] font-extrabold text-white" style={{ background: eveCur.level === '긴급' ? '#d23a35' : '#e0a100' }}>{eveCur.level}</span>
                <span className="min-w-0 flex-1 truncate text-[15px]"><b>{MACHINES[eveCur.machine].name} {(eveCur.alarm?.nameKo ?? '알람').replace(/\s*\([A-Z0-9 ._/-]+\)/, '')}({eveCur.code})</b> {Math.max(1, Math.round((SIM.now() - eveCur.ts) / 60000))}분째예요. {eveCur.alarm?.steps[0] ? `먼저: ${eveCur.alarm.steps[0]}` : eveCur.alarm?.easy ?? '지침카드를 확인해 주세요.'}</span>
                <span className="shrink-0 whitespace-nowrap rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-[12px] text-slate-600" title="알람 코드집으로 만든 문장">근거 · {eveCur.alarm?.doc03[0] ?? 'DOC-02 알람 코드집'}</span>
                {eveList.length > 1 && <button onClick={() => setEveI((i) => i + 1)} className="shrink-0 font-mono text-[12px] text-slate-500 hover:text-slate-800" aria-label="다음 소식">{(eveI % eveList.length) + 1} / {eveList.length} ›</button>}
                <button onClick={() => openCard(eveCur.id)} className="h-8 shrink-0 rounded-full bg-[#1c232b] px-3.5 text-[13px] font-bold text-white">지침카드</button>
              </>) : null}
              <button onClick={() => setSide('채팅')} className="h-8 shrink-0 rounded-full border border-slate-300 bg-white px-3.5 text-[13px] font-bold">이브에게 묻기</button>
            </div>
          )}
          <div className={screen === 'line' || screen === 'replay' ? 'stage-card absolute overflow-hidden rounded-3xl border border-[#e6e3f0]' : 'absolute'} style={{ ...stagePos, visibility: show3D ? 'visible' : 'hidden', opacity: show3D ? 1 : 0, pointerEvents: show3D ? 'auto' : 'none' }}>
            <FactoryDashboard embedded dataMode warnIds={[...new Set(open.filter((a) => a.level === '주의').map((a) => a.machine))]} layout={LAYOUT} quality="자동" introOnLoad={false} showCards={settings.cards} alarmText={alarmText} cardText={cardText}
              cmmCard={cmmCard} bigTags={screen === 'field'} scenario="정상 가동" onReady={onReady}
              onSnapshot={(s: { sel: MachineId | null }) => setSnapSel(s.sel)} onSelect={(id: MachineId) => setSnapSel(id)}
              onFail={(why: string) => { setFail3d(why); setScreen((s0) => (s0 === 'line' ? 'layout2d' : s0)); }} />
            {screen === 'line' && (<>
              {eveRgb && <div className="eve-glow pointer-events-none absolute inset-0 z-[5] rounded-3xl" style={{ boxShadow: `inset 0 0 0 2px rgba(${eveRgb},.55), inset 0 60px 80px -40px rgba(${eveRgb},.35)` }} />}
            </>)}
            {show3D && (
              <>
                {screen === 'field' && (
                  <div className="pointer-events-auto absolute left-3 top-3 z-10 flex gap-1 rounded-full border border-[#e6e3f0] bg-white/90 p-1 shadow-md">
                    {ZONES.map(([name, , ids]) => <button key={name} onClick={() => { setZone(name); setSnapSel(null); api3d()?.frameGroup(ids); }} className={`h-10 rounded-full px-4 text-[15px] font-bold ${zone === name ? 'bg-[#1c232b] text-white' : 'hover:bg-[#f1eefb]'}`}>{name}</button>)}
                    <button onClick={() => { setZone(null); setSnapSel(null); api3d()?.setView('front'); }} className={`h-10 rounded-full px-4 text-[15px] font-bold ${zone === null ? 'bg-[#1c232b] text-white' : 'hover:bg-[#f1eefb]'}`}>전체</button>
                  </div>
                )}
                <div className="pointer-events-auto absolute bottom-3 right-3 flex gap-1 rounded-full border border-[#e6e3f0] bg-white/90 p-1 shadow-md">
                  {(() => { const sb = 'h-8 min-w-9 rounded-full px-3 text-[13px] font-semibold hover:bg-[#f1eefb]'; return (<>
                    <button onClick={() => go('layout2d')} className={sb}>2D</button>
                    <button onClick={() => { api3d()?.setView('front'); setSnapSel(null); }} className={sb}>전체</button>
                    {screen === 'line' && <button onClick={() => api3d()?.setView('top')} className={sb}>위</button>}
                    <button onClick={() => api3d()?.nav('zoom', 0.85)} className={sb} aria-label="확대">+</button>
                    <button onClick={() => api3d()?.nav('zoom', 1.18)} className={sb} aria-label="축소">−</button>
                  </>); })()}
                </div>
              </>
            )}
          </div>

          {screen === 'layout2d' && <Layout2D />}
          {(screen === 'line' || screen === 'layout2d' || fieldSel) && (
            <div className={screen === 'line' ? 'absolute bottom-3 left-[220px] right-3 h-[var(--panelH)]' : `absolute bottom-0 left-0 ${screen === 'field' ? 'right-[360px]' : 'right-0'} h-[var(--panelH)] border-t border-slate-300 bg-[#eef1f4]`}><Panels field={screen === 'field'} ids={screen === 'field' && zone && !snapSel ? ZONES.find((z) => z[0] === zone)?.[2] : undefined} /></div>
          )}
          {screen === 'field' && <div className="absolute bottom-0 right-0 top-0 w-[360px]"><FieldStrip onBriefing={() => { setSeenBrief((s) => ({ ...s, [user.id]: twin?.shift.shift_id ?? '' })); setSide('브리핑'); }} /></div>}
          {screen === 'replay' && <ReplayScreen />}
          {screen === 'cards' && <CardList />}
          {screen === 'card' && key && <CardScreen alertId={key} />}
          {(screen === 'docs' || screen === 'pm' || DOC_OF[screen] || QUAL_OF[screen]) && (() => {
            const isQ = !!QUAL_OF[screen], isPm = screen === 'pm';
            // 예방 정비: 설비 고르기를 문서함 같은 왼쪽 목록으로 (사용자 요청 2026-10-16)
            const cats: [string, Screen, string | null, Role[]?][] = isPm ? [PM_ALL, ...EQS].map((e) => [e, 'pm', e]) : isQ ? QUAL_CATS : DOC_CATS;
            const cur = isPm ? (key && (key === PM_ALL || EQS.includes(key)) ? key : 'VF2-02') : isQ ? QUAL_OF[screen] : screen === 'docs' ? (key ?? '작업지시서') : DOC_OF[screen];
            const pmBadge = (e: string) => { const ts = pmF.data?.tasks.filter((t) => e === PM_ALL || t.equipment_id === e) ?? [], over = ts.filter((t) => t.state === 'OVERDUE').length, soon = ts.filter((t) => t.state === 'DUE_SOON').length; return over || soon ? <span className="float-right text-[13px] font-normal">{over ? <span className="text-[#9a6200]">▲{over}</span> : null}{soon ? <span className="ml-1 text-slate-500">ⓘ{soon}</span> : null}</span> : null; };
            return (
              <div className="absolute inset-0 flex bg-[#e9ecef]">
                {isPm && <aside className="flex w-[200px] shrink-0 flex-col gap-1 overflow-y-auto border-r border-slate-300 bg-white p-2">
                  <b className="px-2 py-2 text-[17px]">{isPm ? '예방 정비' : isQ ? '품질' : '문서함'}</b>
                  {cats.map(([name, s2, k2, roles]) => {
                    const ok = !roles || roles.includes(role);
                    return <button key={name} disabled={!ok} onClick={() => go(s2, k2)} title={ok ? undefined : '이 계정은 볼 수 없습니다'}
                      className={`h-11 rounded-lg px-3 text-left text-[15px] font-semibold disabled:cursor-not-allowed disabled:text-slate-300 ${cur === name ? 'bg-[#e8f6fa] text-[#5a3bc8]' : 'hover:bg-slate-100'}`}>{name}{isPm && pmBadge(name)}</button>;
                  })}
                </aside>}
                <div className="relative min-w-0 flex-1">
                  {screen === 'docs' && <DocBox />}
                  {screen === 'wo' && key && <WorkOrderScreen no={key} />}
                  {screen === 'wr' && key && <WorkRecordScreen woNo={key} />}
                  {screen === 'sr' && key && <SimpleRecordScreen no={key} />}
                  {screen === 'shift' && <ShiftReportScreen />}
                  {screen === 'daily' && <DailyReportScreen />}
                  {screen === 'quality' && <QualityScreen />}
                  {screen === 'revs' && <RevisionsScreen />}
                  {screen === 'idocs' && <DocsScreen />}
                  {isPm && (key === PM_ALL ? <PmAll /> : <PmScreen />)}
                </div>
              </div>
            );
          })()}
          {screen === 'stops' && <StopsScreen />}
          {screen === 'lots' && <LotScreen />}
          {screen === 'inventory' && <InventoryScreen />}
          {screen === 'tools' && <ToolsScreen />}
          {screen === 'settings' && <SettingsScreen />}
        </div>

        {/* 범례 [12] — 항상 보이고 접을 수 없다 */}
        </div>
        <footer className="mx-3 mb-3 flex h-[40px] shrink-0 items-center gap-4 overflow-x-auto rounded-2xl border border-slate-300 bg-white px-4 text-[13px]">
          <b>범례</b>
          {LEGEND.map((l) => <span key={l.text} className="whitespace-nowrap">{l.text === '병목' ? <SnailBadge /> : <span style={{ color: l.color }}>{l.icon}</span>} {l.text}</span>)}
          <span className="ml-auto whitespace-nowrap text-slate-600">알림: <b className="text-[#c62a2f]">⚠ 긴급</b> │ <b className="text-[#9a6200]">▲ 주의</b> │ ⓘ 참고</span>
        </footer>

        <Eve tab={side} onClose={closeSide} brief={<Briefing onDone={() => { setSeenBrief((s0) => ({ ...s0, [user.id]: twin?.shift.shift_id ?? '' })); closeSide(); }} />} onNotice={openNotice} bubble={bubbleText} onBubble={onBubble}
          badges={{ 알림: open.length + myNotices.filter((n) => !n.handled).length, 브리핑: briefBubble ? 1 : 0 }}
          onPick={(t) => { if (t === '브리핑') setSeenBrief((s) => ({ ...s, [user.id]: twin?.shift.shift_id ?? '' })); setSide(t); }} />

        {emergencies[0] && (
          <Popup alert={emergencies[0]} others={emergencies.length - 1} big={screen === 'field'} sound
            onCard={() => openCard(emergencies[0].id)} onAck={() => setAcked((s) => ({ ...s, [user.id]: [...(s[user.id] ?? []), emergencies[0].id] }))} />
        )}
        {source && <SourcePopup doc={source[0]} section={source[1]} onClose={() => setSource(null)} />}
        {toastMsg && <div className="fixed bottom-[100px] left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[#1c2530] px-4 py-3 text-[14px] font-semibold text-white shadow-lg">{toastMsg}</div>}
      </div>
    </Ctx.Provider>
  );
}

// 범례의 병목 표시 = 3D 천장 표지판 모서리의 달팽이 배지와 같은 그림 (FactoryDashboard 병목 배지 경로 그대로)
function SnailBadge() {
  return (
    <svg viewBox="-6.6 -6.2 37.2 37.2" width="17" height="17" className="inline-block align-[-3px]" aria-hidden="true">
      <circle cx="12" cy="12.4" r="17.6" fill="#1c232b" stroke="#b9a8ff" strokeWidth="2" />
      <g fill="none" stroke="#b9a8ff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        {['M3 18h15.5a2.5 2.5 0 0 0 2.5-2.5V13', 'M16.5 12a5.5 5.5 0 1 1-11 0a5.5 5.5 0 1 1 11 0', 'M11 12a2.2 2.2 0 1 1 2.2-2.2', 'M19.5 13 18.5 8.5', 'M21 13l1.4-4.2'].map((d) => <path key={d} d={d} />)}
      </g>
    </svg>);
}

function SettingsPopover({ settings, setSettings, api3d, bigPx, bodyPx }: { settings: Settings; setSettings: (f: (s: Settings) => Settings) => void; api3d: () => any; bigPx: number; bodyPx: number }) {
  const S = (k: keyof Settings, v: Settings[keyof Settings]) => setSettings((s) => ({ ...s, [k]: v }));
  return (
    <div className="absolute right-0 top-[48px] z-30 w-[330px] rounded-lg border border-slate-300 bg-white p-3 text-[13px] shadow-lg">
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={!settings.bloom} onChange={() => { const n = !settings.bloom; S('bloom', n); api3d()?.setState((s: any) => ({ layers: { ...s.layers, bloom: n } })); }} /> 3D 빛 효과 끄기</label>
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={!settings.sound} onChange={() => S('sound', !settings.sound)} /> 소리 끄기 (긴급 경고음은 못 끔)</label>
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={settings.cards} onChange={() => S('cards', !settings.cards)} /> 3D 위 설비 카드·측정 카드 보기 <span className="text-[11px] text-slate-500">(설계서: 3D 위에는 상태·재공·병목만 — 기본 끔)</span></label>
      <div className="mt-2 border-t border-slate-200 pt-2 font-bold">글자 크기 (2.4 계산식 H = D × 0.0058)</div>
      <div className="flex items-center gap-2">모니터 <input type="number" value={settings.monitorInch} onChange={(e) => S('monitorInch', Number(e.target.value) || 55)} className="h-11 w-16 rounded border border-slate-300 px-2" />인치 · 거리 <input type="number" step="0.5" value={settings.distanceM} onChange={(e) => S('distanceM', Number(e.target.value) || 3)} className="h-11 w-16 rounded border border-slate-300 px-2" />m</div>
      <p className="text-[12px] text-slate-500">계산: 큰 숫자 {bigPx}px · 본문 {bodyPx}px (16:9 화면 가정). 값은 [선택 필요: 기술 회의] — 실제 장치에서 자로 재 확인</p>
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={settings.fontScale} onChange={() => S('fontScale', !settings.fontScale)} /> 계산한 크기로 현장 모니터 글자 키우기</label>
    </div>
  );
}
