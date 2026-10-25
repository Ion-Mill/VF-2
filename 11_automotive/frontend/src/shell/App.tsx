'use client';
// 화면 틀(UI설계서 2.1)과 화면 이동 — 데이터적용본. 값은 모두 시연 데이터 서버(생성기 실시간 모드 10/1 + 과거 기록 9월)에서 온다.
// 3D 장면(FactoryDashboard)은 로그인한 뒤 한 번만 만들고, 실시간(또는 다시 보기) 값을 applyLive로 넣는다.
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MachineId } from '@/components/types';
import { ID_OF, LAYOUT, LEGEND, MACHINES, type Role } from './data';
import { Ctx, DEFAULT_SETTINGS, type AppCtx, type History, type Inv, type Screen, type Settings } from './ctx';
import { api, md, SIM, simIso, tsOf, useFetch, useLive, useLocal, usePersist, type SimEvent } from './live';
import { backendLogout, backendMode } from './backendApi';
import { causeNoticeId, createRecord, loadDocs, openWoSeen, resolveNotice, saveSr, saveWo, saveWr, type Docs } from './backendDocs';
import { askGuideCard } from './assistText';
import { ALARMS, ROLE_NAME, SHIFT_NAME, USERS, homeScreen, levelOfSev, userName, type AlarmRec, type AlertRec, type Notice, type UserRec } from './model';
import { derive, fromEvents, fromPast, groupPmPast, repeatOf, type RuleCtx } from './rules';
import { LOCK } from './Safety';
import { nextNo, pad, rev, type SimpleRecord, type WorkOrder, type WorkRecord } from './workflow';
import { Eve, Robot, type EveTab } from './Eve';
import Briefing from './Briefing';
import CardScreen, { CardList } from './CardScreen';
import DocBox from './DocBox';
import Layout2D from './Layout2D';
import Login from './Login';
import Logo from './Logo';
import Panels from './Panels';
import HomeHud, { GLASS } from './HomeHud';
import { LockIcon, PageHead } from './ui';
import Popup from './Popup';
import SimPanel from './SimPanel';
import SimpleRecordScreen from './SimpleRecordScreen';
import WorkOrderScreen from './WorkOrderScreen';
import { ReplayScreen } from './ReplayScreen';
import { DailyReportScreen, ShiftReportScreen } from './Reports';
import { RevisionsScreen } from './Revisions';
import { LotScreen } from './LotScreen';
import { QualityScreen } from './QualityScreen';
import { InventoryScreen } from './InventoryScreen';
import { ToolsScreen } from './ToolsScreen';
import { PmPage } from './PmScreen';
import { DocsScreen, SourcePopup } from './DocsScreen';
import { SettingsScreen } from './SettingsScreen';

const FactoryDashboard: any = dynamic(() => import('@/components/FactoryDashboard'), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center gap-2 bg-ground"><div className="h-3 w-48 animate-pulse rounded bg-line" /><span className="text-small text-ink-2">3D 불러오는 중…</span></div>,
});

const TITLE: Record<Screen, string> = {
  line: '3D 라인 뷰', layout2d: '3D 라인 뷰 · 2D 배치도', field: '현장 모니터', cards: '지침카드', card: '지침카드', wo: '정비 작업지시서', wr: '작업기록서', sr: '간이 작업기록',
  docs: '문서함', replay: '다시 보기', shift: '교대 보고서', daily: '일일 보고서', revs: '수정 이력', lots: '로트 추적', quality: '검사 기록', qcap: '공정 능력 · 불량',
  inventory: '재고', tools: '공구 수명', pm: '예방 정비 일정', idocs: '사내 문서', settings: '설정',
};
// 제목 밑 한 줄 설명 (화이트 카드 · 파스텔 블루 목업, 2026-10-21) — 없는 화면은 제목만
const SUB: Partial<Record<Screen, string>> = {
  field: '설비를 누르면 3D 화면 아래에 설비 패널이 열립니다.', cards: '알람마다 나온 지침카드를 처리합니다.', docs: '작업지시서와 기록 문서를 찾아 확인합니다.',
  lots: '원자재부터 출하까지 한 로트가 지나온 길을 봅니다.', quality: '로트별 측정 결과와 부품 지도를 봅니다.', qcap: '측정값 전체로 공정 능력과 불량을 봅니다.',
  inventory: '공구 · 소모품 · 원자재 · 완제품 재고를 봅니다.', tools: '공구별 사용량과 교체 이력을 봅니다.', pm: '설비별 예방 정비 기한과 오늘 할 일을 봅니다.',
  revs: '문서가 언제 누구에 의해 바뀌었는지 봅니다.', idocs: '사내 표준 문서를 찾아 봅니다.', settings: '알림 기준과 기준 값을 바꿉니다.',
};
// 메뉴 (페이지구조 v3 5.1). 권한 없는 페이지는 흐리게 (N3) — 열 수 있는 역할 목록, 없으면 전원
const MENU_V3: [string, Screen | 'home', Role[]?][] = [
  ['홈', 'home'], ['지침카드', 'cards'], ['문서함', 'docs'], ['로트 추적', 'lots'], ['품질', 'quality', ['OPR', 'SUP', 'MGR']], ['공정 능력 · 불량', 'qcap', ['SUP', 'MGR']], ['재고', 'inventory'], ['공구 수명', 'tools'],
  ['예방 정비', 'pm', ['MNT', 'SUP', 'MGR']], ['다시 보기', 'replay'], ['현장 모니터', 'field'], ['설정', 'settings', ['MGR']],
];
// 문서함 카테고리 (v3 문서함 8개) — 고르면 오른쪽에 그 화면. 문서 하나를 열어도 문서함 안에 보임
const DOC_CATS: [string, Screen, string | null, Role[]?][] = [
  ['작업지시서', 'docs', '작업지시서'], ['작업기록서', 'docs', '작업기록서', ['MNT', 'SUP', 'MGR']], ['간이 작업기록', 'docs', '간이 작업기록'],
  ['교대 보고서', 'docs', '교대 보고서'], ['일일 보고서', 'docs', '일일 보고서', ['MNT', 'SUP', 'MGR']],
  ['수정 이력', 'revs', null], ['사내 문서', 'idocs', null],
];
const DOC_OF: Partial<Record<Screen, string>> = { wo: '작업지시서', wr: '작업기록서', sr: '간이 작업기록', shift: '교대 보고서', daily: '일일 보고서', revs: '수정 이력', idocs: '사내 문서' };
// 품질 카테고리 — 문서함과 같은 모양(왼쪽 목록 + 오른쪽 화면). 품질 화면이 늘면 여기에 한 줄씩 더한다
const QUAL_CATS: [string, Screen, string | null][] = [['검사 기록', 'quality', null], ['공정 능력 · 불량', 'qcap', null]];
const QUAL_OF: Partial<Record<Screen, string>> = { quality: '검사 기록', qcap: '공정 능력 · 불량' };
// 작업지시서 담당자 기본값 = 알람이 난 교대의 보전 담당자 (주간 08~17 / 야간). 반장은 필요할 때만 바꾸고 [승인]만 누른다 (2026-10-20 시안)
const shiftMnt = (iso: string) => { const h = Number(iso.slice(11, 13)); const s = h >= 8 && h < 17 ? 'DAY' : 'NIGHT'; return USERS.find((u) => u.role === 'MNT' && u.shift === s)?.id ?? null; };
// 작업지시서 작업 순서 (DOC-03 머리말 "점검 순서"): 정지 등급(OP-30) = 점검 순서 전체(★ 작업자 줄 + 보전 줄), 반복 알람 2단계 = 보전 줄 (9월 기록 MW-0903·0904와 같음).
// "막힘 점검은 §2.1 점검 2~5와 같다"처럼 줄 전체가 다른 절을 가리키면 그 절의 해당 줄로 풀어 넣고 끝에 출처를 붙인다. 사내 문서 문장은 바꾸지 않는다 (2026-10-20)
const fullOrder = (al: AlarmRec) => [...al.steps, ...al.maint];
const expandRefs = (lines: string[]) => lines.flatMap((s) => {
  const m = s.match(/§(\d+\.\d+) 점검 (\d+)~(\d+)와 같다$/);
  const src = m && Object.values(ALARMS).find((x) => x.doc03.includes(`DOC-03 §${m[1]}`));
  return m && src ? fullOrder(src).slice(+m[2] - 1, +m[3]).map((x, i) => `${x} (§${m[1]} 점검 ${+m[2] + i})`) : [s];
});
const woSteps = (al: AlarmRec, trigger: WorkOrder['trigger']) => expandRefs(trigger === 'REPEAT_2' ? (al.maint.length ? al.maint : al.steps) : fullOrder(al));
const SCREENS: Screen[] = ['line', 'layout2d', 'field', 'cards', 'card', 'wo', 'wr', 'sr', 'docs', 'replay', 'shift', 'daily', 'revs', 'lots', 'quality', 'qcap', 'inventory', 'tools', 'pm', 'idocs', 'settings'];
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
// row: true 이면 그 묶음의 하위 탭을 본문 위 가로 한 줄로 보인다 (생산). 위 유리 메뉴 펼침은 그대로다.
const GROUPS: { label: string; row?: boolean; subs: [string, Screen, Role[]?, (string | null)?][]; related?: Screen[] }[] = [
  { label: '홈', subs: [['3D 라인', 'line']], related: ['layout2d'] },
  { label: '생산', row: true, subs: [['로트 추적', 'lots'], ['현장 모니터', 'field']] },
  { label: '정비', subs: [['다시 보기', 'replay'], ['예방 정비', 'pm', ['MNT', 'SUP', 'MGR']]] },
  { label: '품질', subs: [['검사 기록', 'quality', ['OPR', 'SUP', 'MGR']], ['공정 능력 · 불량', 'qcap', ['SUP', 'MGR']]] },
  { label: '재고', subs: [['재고', 'inventory'], ['공구 수명', 'tools']] },
  { label: '문서', subs: [['지침카드', 'cards'], ...DOC_CATS.map(([n, s2, k2, roles]) => [n, s2, roles, k2] as [string, Screen, Role[]?, (string | null)?])], related: ['docs', 'wo', 'wr', 'sr', 'shift', 'daily', 'revs', 'idocs', 'card'] }, // 지침카드는 정비에서 문서로 옮김 (사용자 요청 2026-10-20), 문서 묶음 맨 위 (2026-10-22)
  { label: '설정', subs: [['설정', 'settings', ['MGR']]] },
];
// 위 메뉴 아이콘 (상단바 시안 '아이콘 1', 사용자 선택 2026-10-21): 묶음 이름 → 24칸 선 그림
const NAV_ICON: Record<string, string> = {
  홈: 'M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5M10 21v-6h4v6',
  생산: 'M2 20h20M4 20V9l5 3V9l5 3V5h6v15M8 16h1M13 16h1M17 16h1',
  정비: 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z',
  품질: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0zM8 12l3 3 5-6',
  재고: 'M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',
  문서: 'M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5M9 13h6M9 17h6',
  설정: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1',
};
const btn = 'h-11 rounded-ctl border border-line bg-white px-3 text-body font-semibold hover:bg-tile';

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
  const [wosL, setWos] = usePersist<WorkOrder[]>('wos', [], runId);
  const [wrsL, setWrs] = usePersist<WorkRecord[]>('wrs', [], runId);
  const [srsL, setSrs] = usePersist<SimpleRecord[]>('srs', [], runId);
  const [noticesL, setNotices] = usePersist<Notice[]>('notices', [], runId);
  // 백엔드 모드 (화면 → 백엔드 전환 C2 다음 단계, 2026-10-24 — backendDocs.ts): 작업지시서·작업기록서·간이 기록·알림을 백엔드에서 읽고 쓴다.
  // 화면이 스스로 만들던 작업지시서 초안·규칙 알림은 끈다 (DB가 만든다). 아직 저장 안 한 간이 기록만 화면 안에 잠시 둔다 (번호 NEW:)
  const BM = backendMode();
  const [bdocs, setBdocs] = useState<Docs | null>(null);
  const [draftSrs, setDraftSrs] = useState<SimpleRecord[]>([]);
  const making = useRef<Set<string>>(new Set());                    // 만드는 중인 작업기록서 (작업지시서 번호)
  const saveQ = useRef<Record<string, Promise<unknown> | undefined>>({});          // 문서별 저장 줄
  const reloadDocs = useCallback(() => { if (BM) loadDocs().then(setBdocs).catch(() => undefined); }, [BM]);
  useEffect(() => { if (!BM) return undefined; reloadDocs(); const t = setInterval(reloadDocs, 4000); return () => clearInterval(t); }, [BM, reloadDocs, runId]);
  const wos = BM ? bdocs?.wos ?? [] : wosL;
  const wrs = BM ? bdocs?.wrs ?? [] : wrsL;
  const srs = BM ? [...(bdocs?.srs ?? []), ...draftSrs.filter((d) => !(bdocs?.srs ?? []).some((x) => x.alertId === d.alertId && x.kind === d.kind))] : srsL;
  const notices = BM ? bdocs?.notices ?? [] : noticesL;
  const [handledA, setHandledA] = usePersist<Record<string, { by: string; ts: number }>>('handled', {}, runId);
  const [acked, setAcked] = usePersist<Record<string, string[]>>('acked', {}, runId); // 사용자별 긴급 팝업 [확인]
  const [hushed, setHushed] = useState<string[]>([]); // 팝업을 닫을 때 이미 쌓여 있던 긴급 알람 — 다음 팝업으로 이어 떠도 소리는 안 냄 (사용자 요청 2026-10-22)
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
    // 백엔드 모드는 트윈 알람에 DB의 처리(작업기록서 확정)가 같이 온다 — 작업기록서를 못 읽는 역할도 처리된 알람을 긴급으로 안 띄움 (2026-10-25)
    const id = `a-${e.alarm_event_id}`, h = handledA[id] ?? bdocs?.handled[id] ?? (e.handled_at ? { by: userName(e.handled_by), ts: tsOf(e.handled_at) } : undefined);
    const guideDone = e.severity === 'GUIDE' && !!e.cleared_at; // 조작 안내는 작업자가 고치면(알람 해제) 처리
    return {
      id, eventId: e.alarm_event_id, prevId: e.prev_alarm_event_id, machine: ID_OF[e.equipment_id], code: e.alarm_code,
      kind: e.severity === 'STOP' ? 'alarm' : e.severity === 'WARN' ? 'warn' : 'guide', level: levelOfSev(e.severity), alarm: ALARMS[e.alarm_code] ?? null,
      time: e.occurred_at, ts: tsOf(e.occurred_at), cleared: e.cleared_at, lot: e.lot_no, scenario: e.scenario_code,
      handled: !!h || guideDone, handledTs: h?.ts, handledBy: h?.by ?? (guideDone ? '알람 해제' : undefined),
    } as AlertRec;
  }), [twin?.alarms, handledA, bdocs?.handled]);

  // 새 알람 → OP-30 정지 등급이면 작업지시서 초안 + 문서 알림, 반복 알람 판단
  const seenAlarm = useRef<Set<number>>(new Set());
  const ruleCtx = (): RuleCtx => ({
    twin, inv: invF.data, pm: pmF.data as RuleCtx['pm'], wos, wrs, shiftReports: shiftF.data?.reports as RuleCtx['shiftReports'] ?? null,
    dailyReports: dailyF.data?.reports as RuleCtx['dailyReports'] ?? null, cmm: cmmF.data, quality: qualF.data, alerts,
    pastAlarms: (hist.data?.alarms ?? []).map((a) => ({ equipment_id: a.equipment_id, alarm_code: a.alarm_code, occurred_at: a.occurred_at })), notices, rules,
  });
  const addNotices = useCallback((ns: Notice[]) => {
    if (!ns.length || BM) return;
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
      if (BM) return;                     // 백엔드 모드: 작업지시서 초안·반복 알람 알림·원인 점검 요청은 DB가 만든다
      if (a.kind === 'alarm' && MACHINES[a.machine].op === 'OP-30' && a.alarm) createWo(a, 'STOP_ALARM'); // 같은 설비 열린 작업지시서 검사는 createWo 안에서
      const r = repeatOf(a, ruleCtx());
      if (r) {
        add.push(r);
        if (r.rule === 'REPEAT_ALARM_2') createWo(a, 'REPEAT_2');
        if (r.rule === 'CAUSE_CHECK_REQUEST') openSimple(a.id, 'cause', false);
      }
    });
    addNotices(add);
  }, [alerts, hist.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // 작업 순서 규칙이 바뀌기 전에 만든 초안(사람이 아직 안 고친 v0)은 지금 규칙으로 다시 채운다 (시연 회차 기록에 남아 있던 것, 2026-10-20)
  useEffect(() => {
    setWos((l) => {
      let ch = false;
      const n = l.map((w) => {
        const al = ALARMS[w.code];
        if (w.state !== 'draft' || w.version !== 0 || !al) return w;
        const s = woSteps(al, w.trigger);
        if (JSON.stringify(s) === JSON.stringify(w.steps)) return w;
        ch = true; return { ...w, steps: s };
      });
      return ch ? n : l;
    });
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps
  const createWo = (a: AlertRec, trigger: WorkOrder['trigger']) => {
    const al = a.alarm!;
    setWos((w) => {
      if (w.some((x) => x.alertId === a.id && x.trigger === trigger)) return w;
      // 정지 알람: 같은 설비에 끝나지 않은 작업지시서가 있으면 새로 안 만든다 (연쇄 108 → 994 → 992는 한 건). 저장된 목록을 읽은 뒤의 값(w)으로 봐야
      // 페이지를 새로 열 때 목록을 읽기 전에 검사해서 같은 사건 초안이 여러 개 생기지 않는다 (2026-10-22)
      if (trigger === 'STOP_ALARM' && w.some((x) => x.machine === a.machine && x.state !== 'done' && x.state !== 'cancelled')) return w;
      const no = `MW-${pad(950 + w.length)}`;
      const wo: WorkOrder = {
        no, alertId: a.id, machine: a.machine, code: a.code, created: a.time, state: 'draft', version: 0, trigger, lot: a.lot,
        title: trigger === 'REPEAT_2' ? `${MACHINES[a.machine].name} 알람 ${a.code} 반복 — 원인 점검 (2단계)` : `${MACHINES[a.machine].name} 알람 ${a.code} (${al.nameKo.replace(/\(.*\)/, '')}) 점검`,
        symptom: al.symptom + (al.chain ? ` — 연쇄 알람 ${al.chain}` : ''), steps: woSteps(al, trigger), parts: expectedParts(a.code), assignee: shiftMnt(a.time), edited: [],
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
  useEffect(() => { if (pastOpen.data) addNotices(groupPmPast(pastOpen.data.notifications.map(fromPast))); }, [pastOpen.data, addNotices]);
  // 상태로 판단하는 알림 (5초마다)
  useEffect(() => {
    if (!twin || BM) return;
    const t = setTimeout(() => {
      const { add, resolve } = derive(ruleCtx());
      addNotices(add);
      if (resolve.length) setNotices((l) => (l.some((x) => resolve.includes(x.id) && !x.handled) ? l.map((x) => (resolve.includes(x.id) && !x.handled ? { ...x, handled: true, handledBy: '조건 풀림 (자동)', handledAt: simIso() } : x)) : l));
    }, 300);
    return () => clearTimeout(t);
  }, [twin?.clock.sim_at, invF.data, pmF.data, shiftF.data, dailyF.data, cmmF.data, qualF.data, wos, wrs]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- 3D ----------
  const [replayFrame, setReplay] = useState<unknown | null>(null);
  const [fail3d, setFail3d] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState<string | null>(null); // 위 가로 메뉴에서 펼친 묶음 (시안 3a, 2026-10-20 — 모든 화면)
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
  const go = useCallback((s: Screen, k: string | null = null) => { hist2.current.push([screen, key]); setScreen(s); setKey(k); setMenu(false); setDemo(false); setNavOpen(null); }, [screen, key]);
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
  const [bandOff, setBandOff] = useState<string[]>([]); // 알림 띠에서 닫은 주의 알람 (사용자 요청 2026-10-22, 긴급은 못 닫음)
  const [eveI, setEveI] = useState(0); // 홈 이브 알림 띠에서 보고 있는 알람 번호
  useEffect(() => { setBandOff([]); setEveI(0); }, [runId]); // 시연을 처음으로 되돌리면(새 회차) 닫아 둔 주의 알람을 잊는다 — 알람 번호가 회차마다 같아서 안 지우면 새 알람이 띠에 안 뜬다 (2026-10-23)
  const [zone, setZone] = useState<string | null>(null);
  const curGroup = GROUPS.find((g) => g.subs.some(([, s2]) => s2 === screen) || g.related?.includes(screen));
  const sideRow = !!curGroup?.row; // 가로 메뉴바(row) 묶음: 본문 맨 위 가로 바에 하위 탭을 보인다
  useEffect(() => { // 펼친 메뉴 바깥을 누르거나 Esc면 닫기
    if (!navOpen) return;
    const off = (e: Event) => { if (e instanceof KeyboardEvent ? e.key === 'Escape' : !(e.target as Element).closest?.('[data-nav]')) setNavOpen(null); };
    document.addEventListener('pointerdown', off); document.addEventListener('keydown', off);
    return () => { document.removeEventListener('pointerdown', off); document.removeEventListener('keydown', off); };
  }, [navOpen]);
  // 현장 화면에 들어오면 작업자는 자기 담당 구역으로 줌인
  useEffect(() => { if (screen !== 'field') return; const z = role === 'OPR' ? ZONES.find(([, ops]) => ops.some((o) => user.procs.includes(o))) : undefined; if (!z) { setZone(null); return; } const t = setTimeout(() => { setZone(z[0]); api3d()?.frameGroup(z[2]); }, 500); return () => clearTimeout(t); }, [screen]); // eslint-disable-line react-hooks/exhaustive-deps // 3D 카드 이브 띠에서 보고 있는 소식 번호
  const closeSide = useCallback(() => setSide(null), []);
  const [source, setSource] = useState<[string, string] | null>(null);
  const [toastMsg, setToast] = useState('');
  const toast = useCallback((m: string) => { setToast(m); setTimeout(() => setToast(''), 4500); }, []);

  // ---------- 문서 열기 ----------
  const openCard = (id: string) => { hushAll(); setAcked((s) => ({ ...s, [user.id]: [...(s[user.id] ?? []), id] })); go('card', id); };
  const openWo = (no: string) => { if (BM) { openWoSeen(no).then(reloadDocs); go('wo', no); return; } setNotices((l) => l.map((x) => ((x.rule === 'WO_ASSIGNED' || x.rule === 'WO_DRAFT_READY') && x.open?.key === no && x.roles.includes(role) && (!x.userIds || x.userIds.includes(user.id)) ? { ...x, handled: true, handledBy: user.name, handledAt: simIso() } : x))); go('wo', no); };
  // 작업기록서 = 작업지시서 화면 아래 칸 (2026-10-20). nav=false면 만들기만 하고 화면은 그대로
  const openRecord = (woNo: string, nav = true) => {
    const wo = wos.find((w) => w.no === woNo); if (!wo) return;
    if (BM) {                              // 백엔드가 만든다 (잠금·표지 9칸·작업 순서 체크칸 같이)
      // [작업 시작]은 작업지시서 저장(시작)과 같은 순간에 부른다 → 그 저장이 끝난 뒤 만든다 (같은 지시서 줄). 두 번 눌러도 한 번만
      if (!wrs.some((r) => r.woNo === woNo) && !making.current.has(woNo)) {
        making.current.add(woNo);
        (saveQ.current[`wo:${woNo}`] ?? Promise.resolve()).catch(() => undefined)
          .then(() => createRecord(woNo)).then(reloadDocs).catch((e) => toast((e as Error).message))
          .finally(() => making.current.delete(woNo));
      }
      if (nav) go('wr', woNo);
      return;
    }
    if (!wrs.some((r) => r.woNo === woNo)) {
      const rec: WorkRecord = { no: nextNo('MR', wrs), woNo, state: 'draft', memo: '', cause: '', action: '', parts: [], stepChecks: wo.steps.map(() => false), lock: LOCK.map(() => false), start: '', end: '', revisions: [] };
      setWrs((l) => [...l, rec]); setWos((l) => l.map((x) => (x.no === woNo ? { ...x, recordNo: rec.no } : x)));
    }
    if (nav) go('wr', woNo);
  };
  function openSimple(alertId: string, kind: 'alarm' | 'cause' = 'alarm', nav = true) {
    const al = alerts.find((x) => x.id === alertId); if (!al) return;
    let no = srs.find((r) => r.alertId === alertId && r.kind === kind)?.no;
    if (!no && BM) {                       // 처음 저장할 때 백엔드에 만든다 — 그때까지 임시 번호
      no = `NEW:${alertId}:${kind}`;
      const d: SimpleRecord = { no, alertId, machine: al.machine, kind, code: al.code, state: 'open', action: '', parts: [], lock: LOCK.map(() => false), memo: '', revisions: [] };
      setDraftSrs((l) => [...l.filter((x) => x.no !== d.no), d]);
    }
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

  // 백엔드 모드 저장: 화면은 바로 새 값으로 보이고(낙관적), 백엔드에 저장한 뒤 다시 읽는다. 실패하면 알림 띠로 알리고 다시 읽어 되돌린다
  // 같은 문서의 저장은 줄 세워 하나씩 (앞 저장이 버전을 올리므로 다음 저장 전에 목록을 다시 읽어 최신 버전으로 — CONFLICT_VERSION 막기, 2026-10-24)
  const bSave = (run: () => Promise<unknown>, optimistic: (d: Docs) => Docs, key = '*') => {
    setBdocs((d) => (d ? optimistic(d) : d));
    const before = saveQ.current[key];
    const p = (before ?? Promise.resolve()).catch(() => undefined)
      .then(async () => { if (before) await loadDocs(); return run(); });
    saveQ.current[key] = p;
    p.catch((e) => toast((e as Error).message)).finally(reloadDocs);
    return p;
  };
  const putSrL = (r: SimpleRecord) => setSrs((l) => l.map((x) => (x.no === r.no ? r : x)));
  const bSaveSr = (r: SimpleRecord) => {
    const prev = srs.find((x) => x.no === r.no); if (!prev) return;
    if (r.no.startsWith('NEW:')) setDraftSrs((l) => l.map((x) => (x.no === r.no ? r : x)));
    else setBdocs((d) => (d ? { ...d, srs: d.srs.map((x) => (x.no === r.no ? r : x)) } : d));
    saveSr(prev, r, r.kind === 'cause' ? causeNoticeId(r.machine) : undefined)
      .then((no) => {
        if (no !== r.no) {                 // 처음 저장 — 임시 번호를 DB 번호로 바꾸고 보던 화면도 따라간다
          setDraftSrs((l) => l.filter((x) => x.no !== r.no));
          if (screen === 'sr' && key === r.no) go('sr', no);
        }
      })
      .catch((e) => toast((e as Error).message)).finally(reloadDocs);
  };

  const myNotices = notices.filter((n) => role === 'MGR' || (n.roles.includes(role) && (!n.userIds || n.userIds.includes(user.id) || n.past)));
  const ctx: AppCtx = {
    user, role, setUser, twin, connected, lastOk: live.lastOk, alerts, notices, myNotices, wos, wrs, srs,
    putWo: (w) => { if (BM) { const prev = wos.find((x) => x.no === w.no)!; bSave(() => saveWo(prev, w), (d) => ({ ...d, wos: d.wos.map((x) => (x.no === w.no ? w : x)) }), `wo:${w.no}`); } else setWos((l) => l.map((x) => (x.no === w.no ? w : x))); },
    putWr: (w) => { if (BM) { const prev = wrs.find((x) => x.no === w.no)!; bSave(() => saveWr(prev, w), (d) => ({ ...d, wrs: d.wrs.map((x) => (x.no === w.no ? w : x)) }), `wr:${w.no}`); } else setWrs((l) => l.map((x) => (x.no === w.no ? w : x))); },
    putSr: (r) => (BM ? bSaveSr(r) : putSrL(r)),
    addNotice: (n) => addNotices([n]),
    handleNotice: (id, plan) => (BM ? void bSave(() => resolveNotice(id, plan), (d) => ({ ...d, notices: d.notices.map((x) => (x.id === id ? { ...x, handled: true, handledBy: user.name, plan } : x)) }), `n:${id}`) : setNotices((l) => l.map((x) => (x.id === id ? { ...x, handled: true, handledBy: user.name, handledAt: simIso(), plan } : x)))),
    markAlert: (ids, by) => setHandledA((h) => ({ ...h, ...Object.fromEntries(ids.map((i) => [i, { by, ts: Date.now() }])) })),
    screen, key, go, back, openCard, openWo, openRecord, openSimple: (id, kind) => openSimple(id, kind ?? 'alarm'),
    openSource: (doc, sec) => setSource([doc, sec]), openReplay: (at) => go('replay', at),
    selectMachine: (m) => { if (m) api3d()?.select(m); else api3d()?.setView('front'); setSnapSel(m); }, selected: snapSel,
    toast, settings, setSettings,
    inv: invF.data, reloadInv: invF.reload, history: hist.data, pm: pmF.data, reloadPm: pmF.reload,
    shiftReports: shiftF.data?.reports ?? null, dailyReports: dailyF.data?.reports ?? null, reloadReports: () => { shiftF.reload(); dailyF.reload(); },
    rules, restoreMachine, setReplay,
    bandOff,
    eve: !!side && screen !== 'line', // 이브 창이 열리면 홈 말고는 본문이 창 폭만큼 좁아짐 — 재고·공구·품질 화면이 좁은 배치로 (1안, 2026-10-20)
  };

  // ---------- 긴급 팝업·말풍선 ----------
  const open = alerts.filter((a) => !a.handled);
  const myAck = new Set(acked[user.id] ?? []);
  const emergencies = open.filter((a) => a.level === '긴급' && !myAck.has(a.id));
  const hushAll = () => setHushed((h) => [...h, ...emergencies.map((a) => a.id)]);
  const band = open.find((a) => a.level === '긴급');
  // 3D 카드 안 이브 띠 (사용자 요청 2026-10-18): 처리 안 된 긴급·주의를 긴급부터 — 문장은 알람 코드집(DOC-02·03)으로 만든 규칙 문장
  const eveList = open.filter((a) => a.level !== '참고').sort((a, b) => (a.level === b.level ? b.ts - a.ts : a.level === '긴급' ? -1 : 1));
  const eveCur = eveList[0] ?? null; // 홈 3D 가장자리 빛
  const bandList = eveList.filter((a) => !(a.level === '주의' && bandOff.includes(a.id)));
  const bandCur = bandList.length ? bandList[eveI % bandList.length] : null; // 홈 이브 알림 띠 (2026-10-21 되살림, 처리 안 된 긴급·주의가 있을 때만)
  const glowLevel = eveCur?.level;
  const eveRgb = !glowLevel ? null : glowLevel === '긴급' ? '229,72,77' : '240,180,41';
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
  // 홈 = 3D가 화면 전체, 그 위에 유리판 (시안 3a). 현장 모니터 = 위까지 3D + 아래 설비 패널
  const stagePos = screen === 'field' ? { left: 0, top: 0, right: 0, bottom: fieldSel ? 'var(--panelH)' : 0 } : { left: 0, top: 0, right: 0, bottom: 0 };
  const home = screen === 'line';


  return (
    <Ctx.Provider value={ctx}>
      <div className={`relative flex h-screen flex-col overflow-hidden bg-ground text-ink ${settings.fontScale ? 'fs-scaled' : ''}`} style={{ ...(style as React.CSSProperties), width: '100%', marginTop: connected ? 0 : 32, height: connected ? '100vh' : 'calc(100vh - 32px)' }}>
        {/* 위 유리 바 (시안 3a, 2026-10-20 — 모든 화면, 고른 메뉴 · 교대 칩 = 옅은 파랑 2026-10-22): 로고 · 가로 메뉴(묶음은 눌러 펼침, 권한 없는 칸은 숨김) · 오른쪽 [주간][날짜][시각] [계정 ▾] [시연] [⚙] */}
        <header className={`absolute left-4 right-4 top-3 z-30 flex h-16 items-center gap-2 rounded-stage pl-6 pr-3 ${GLASS}`}>
          <Logo height={26} />
          <nav className="ml-6 flex items-center gap-1 max-[1360px]:ml-2 max-[1360px]:gap-0" aria-label="메뉴" data-nav>
            {GROUPS.map((g) => {
              const subs = g.subs; // 모든 계정에 같은 메뉴 (사용자 요청 2026-10-21) — 권한 없는 칸은 흐리게 두고 눌러도 안 열림 (서버도 거부, NFR-SEC-04)
              const locked = (roles?: Role[]) => !!roles && !roles.includes(role), openSub = (roles: Role[] | undefined, s2: Screen, k2: string | null) => (locked(roles) ? toast(`이 계정(${ROLE_NAME[role]})은 열 수 없는 화면이에요 — ${roles!.map((r) => ROLE_NAME[r]).join('·')} 전용`) : go(s2, k2));
              const on = g === curGroup, curDoc = screen === 'docs' ? (key ?? '작업지시서') : DOC_OF[screen];
              const top = `relative flex h-11 items-center gap-2 whitespace-nowrap rounded-tile px-3.5 text-band max-[1360px]:gap-1.5 max-[1360px]:px-2.5 max-[1360px]:text-card ${on ? 'bg-brand-tint font-bold text-brand-ink' : 'font-semibold text-ink-2 hover:bg-white/70 hover:text-ink'}`;
              const ico = <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={`shrink-0 max-[1200px]:hidden ${on ? 'text-brand' : 'text-ink-3'}`}><path d={NAV_ICON[g.label]} /></svg>;
              if (subs.length === 1) return <button key={g.label} onClick={() => openSub(subs[0][2], subs[0][1], subs[0][3] ?? null)} className={`${top} ${locked(subs[0][2]) ? 'opacity-50' : ''}`} aria-current={on ? 'page' : undefined} aria-disabled={locked(subs[0][2]) || undefined}>{ico}{g.label}</button>;
              return (
                <div key={g.label} className="relative">
                  <button onClick={() => setNavOpen((o) => (o === g.label ? null : g.label))} aria-expanded={navOpen === g.label} className={top}>{ico}{g.label}<span className={`text-small ${on ? 'text-brand' : 'text-ink-3'}`} aria-hidden="true">▾</span></button>
                  {navOpen === g.label && (
                    <div className="absolute left-0 top-[52px] z-40 flex min-w-[210px] flex-col gap-0.5 rounded-card border border-line bg-white p-2 shadow-[0_12px_30px_rgba(28,37,48,.16)]">
                      {subs.map(([name, s2, roles, k2]) => { const lk = locked(roles), sel = s2 === 'cards' ? screen === 'cards' || screen === 'card' : g.label === '문서' ? curDoc === name : screen === s2; return (
                        <button key={name} onClick={() => openSub(roles, s2, k2 ?? null)} aria-disabled={lk || undefined} className={`flex h-11 items-center justify-between gap-3 rounded-tile px-4 text-left text-card ${sel ? 'bg-brand-tint font-bold text-brand-ink' : lk ? 'text-ink-3 hover:bg-tile' : 'text-ink hover:bg-brand-tint'}`}>{name}{lk && <LockIcon />}</button>); })}
                    </div>)}
                </div>);
            })}
          </nav>
          <span className={`ml-auto flex items-center gap-2.5 whitespace-nowrap ${connected ? 'text-ink' : 'text-ink-3'}`}>
            {twin ? (<>
              <span className="rounded-tile bg-brand-tint px-2.5 py-1 text-card font-bold text-brand-ink">{twin.clock.sim_at >= twin.shift.end_at ? '휴무' : SHIFT_NAME[twin.shift.shift_type]}</span>
              <b className="font-mono text-title font-semibold max-[1200px]:hidden">{md(twin.clock.sim_at)}</b>
              <b className="font-mono text-title">{twin.clock.sim_at.slice(11, 16)}</b>
            </>) : <b className="font-mono text-title">--:--</b>}
          </span>
          <div className="ml-3 flex items-center gap-1">{/* 계정·시연·설정 묶음 (시안 3a) */}
          <div className="relative">
            <button onClick={() => { setAcct((o) => !o); setDemo(false); setSetOpen(false); }} className="flex h-11 items-center gap-1.5 whitespace-nowrap rounded-tile px-3 text-card font-semibold hover:bg-white/70">
              {user.name} <span className="text-small text-ink-3" aria-hidden="true">▾</span>
            </button>
            {acct && (
              <div className="absolute right-0 top-[52px] z-30 max-h-[70vh] w-[220px] overflow-y-auto rounded-tile border border-line bg-white py-1 shadow-lg">
                {USERS.map((u) => <button key={u.id} onClick={() => { setAcct(false); setUser(u); }} className={`flex h-11 w-full items-center px-4 text-left text-body hover:bg-tile ${u.id === user.id ? 'font-bold text-brand-ink' : ''}`}>{u.name}</button>)}
                <button onClick={() => { backendLogout(); setUser(null); }} className="flex h-11 w-full items-center border-t border-line-soft px-4 text-left text-body text-ink-2 hover:bg-tile">로그아웃</button>
              </div>
            )}
          </div>
          <div className="relative">
            <button onClick={() => { setDemo((d) => !d); setSetOpen(false); setAcct(false); }} className="h-11 whitespace-nowrap rounded-tile px-3 text-card font-semibold hover:bg-white/70">시연</button>
            {demo && <SimPanel twin={twin} refresh={live.refresh} toast={toast} api3d={api3d} onClose={() => setDemo(false)} />}
          </div>
          <div className="relative">
            <button onClick={() => { setSetOpen((o) => !o); setDemo(false); setAcct(false); }} className="flex h-11 w-11 items-center justify-center rounded-tile hover:bg-white/70" aria-label="화면 설정" title="화면 설정">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
            </button>
            {setOpen && <SettingsPopover settings={settings} setSettings={setSettings} api3d={api3d} bigPx={bigPx} bodyPx={bodyPx} />}
          </div>
          </div>
        </header>

        {!connected && (
          <div className="fixed inset-x-0 top-0 z-[60] flex h-8 items-center justify-center gap-2 bg-ink-2 px-4 text-body font-semibold text-white">
            ⚠ 연결 끊김 — 마지막 갱신 {live.lastOk ? live.lastOk.slice(11, 16) : '없음'} · 시연 데이터 서버(tools/sim_server.py)를 켜 주세요. 숫자는 회색, 3D 설비는 "기록 없음"
          </div>
        )}


        {/* 3D 실패·긴급 알림은 이브 말풍선으로, 연결 끊김은 화면 맨 위 띠로 옮김 (2026-10-19) */}

        {/* 이브 창(1안, 사용자 선택 2026-10-20): 창 모양·자리는 모든 화면 같음(오른쪽, 위 바 아래 ~ 이브 버튼 위). 홈은 3D 위에 뜨고, 다른 화면은 본문이 창 폭(420 + 오른쪽 24 + 간격 12)만큼 비켜 줌 */}
        <div className={`flex min-h-0 flex-1 flex-col ${curGroup?.label === '재고' || curGroup?.label === '문서' ? 'fs-up' : ''}`} style={{ paddingTop: home ? 0 : 88, paddingBottom: screen === 'layout2d' ? 64 : screen === 'field' ? 70 : 0, paddingRight: side && !home ? 456 : 0, transition: 'padding-right .25s ease' }}>
        {/* 화면 머리 (디자인 통일 C안 2장): 회색 제목 띠 대신 PageHead. 생산 묶음은 가로 막대가 제목 자리를 대신한다 */}
        {screen !== 'line' && screen !== 'layout2d' && screen !== 'replay' && !sideRow && <div className="shrink-0 bg-ground px-4 pt-3"><PageHead title={TITLE[screen]} sub={SUB[screen]} /></div>}
        {sideRow && curGroup && (
          <nav aria-label={curGroup.label} className="relative z-10 flex h-12 shrink-0 items-center gap-1.5 border-b border-line bg-white px-3">
            <span className="flex items-center pr-3 text-card font-bold text-ink-2">{curGroup.label}</span>
            {curGroup.subs.map(([name, s2, roles]) => { const ok = !roles || roles.includes(role); const on = screen === s2; return (
              <button key={name} disabled={!ok} onClick={() => go(s2)} title={ok ? undefined : '이 계정은 볼 수 없습니다'}
                className={`flex h-10 items-center rounded-tile px-4 text-card font-bold disabled:cursor-not-allowed disabled:text-ink-3 ${on ? 'bg-brand-tint text-brand-ink' : 'text-ink-2 hover:bg-tile'}`}>{name}</button>); })}
          </nav>
        )}
        <div className={`relative min-h-0 flex-1 overflow-hidden ${connected ? '' : 'grayscale-[0.6]'}`}>
          <div className="absolute overflow-hidden" style={{ ...stagePos, visibility: show3D ? 'visible' : 'hidden', opacity: show3D ? 1 : 0, pointerEvents: show3D ? 'auto' : 'none' }}>
            <FactoryDashboard embedded dataMode warnIds={[...new Set(open.filter((a) => a.level === '주의').map((a) => a.machine))]} layout={LAYOUT} quality="자동" introOnLoad={false} showCards={settings.cards} alarmText={alarmText} cardText={cardText}
              cmmCard={cmmCard} bigTags={screen === 'field'} scenario="정상 가동" onReady={onReady}
              onSnapshot={(s: { sel: MachineId | null }) => setSnapSel(s.sel)} onSelect={(id: MachineId) => setSnapSel(id)}
              onFail={(why: string) => { setFail3d(why); setScreen((s0) => (s0 === 'line' ? 'layout2d' : s0)); }} />
            {screen === 'line' && (<>
              {eveRgb && <div className="eve-glow pointer-events-none absolute inset-0 z-[5]" style={{ boxShadow: `inset 0 0 0 2px rgba(${eveRgb},.55), inset 0 60px 80px -40px rgba(${eveRgb},.35)` }} />}
              {bandCur && (() => { const crit = bandCur.level === '긴급', a = bandCur.alarm; return (
                // 이브 알림 띠 — 10/18 내용 그대로(알람 코드집 규칙 문장), 모양만 화이트 카드 테마 + 긴급 빨강 · 주의 노랑 테두리 (사용자 요청 2026-10-21)
                <div className={`pointer-events-auto absolute left-[400px] right-5 top-[92px] z-10 flex h-14 items-center gap-2.5 rounded-card border-2 bg-white pl-3 pr-2 text-body shadow-card ${crit ? 'border-crit' : 'border-warn-mark'}`} role="status">
                  <Robot size={34} />{/* 이브가 알려 주는 띠 — 얼굴은 이브 창 머리와 같은 그림 (사용자 요청 2026-10-22) */}
                  <span className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-ctl px-3 font-bold ${crit ? 'bg-crit-bg text-crit' : 'bg-warn-bg text-warn'}`}><i className="h-2 w-2 rounded-full bg-current" />{bandCur.level}</span>
                  <span className="min-w-0 flex-1 truncate text-ink-2"><b className="font-bold text-ink">{MACHINES[bandCur.machine].name} {(a?.nameKo ?? '알람').replace(/\s*\([A-Z0-9 ._/-]+\)/, '')}({bandCur.code})</b> {Math.max(1, Math.round((SIM.now() - bandCur.ts) / 60000))}분째예요. {a?.steps[0] ? `먼저: ${a.steps[0]}` : a?.easy ?? '지침카드를 확인해 주세요.'}</span>
                  <span className="inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-ctl border border-line px-2.5 text-small text-ink-2" title="알람 코드집으로 만든 문장">근거 · {a?.doc03[0] ?? 'DOC-02 알람 코드집'}</span>
                  {bandList.length > 1 && <button onClick={() => setEveI((i) => i + 1)} className="shrink-0 px-1 text-small tabular-nums text-ink-3 hover:text-ink" aria-label="다음 알람">{(eveI % bandList.length) + 1} / {bandList.length} ›</button>}
                  <button onClick={() => openCard(bandCur.id)} className="h-10 shrink-0 rounded-ctl bg-brand px-4 font-semibold text-white hover:bg-brand-ink">지침카드</button>
                  <button onClick={() => setSide('채팅')} className="h-10 shrink-0 rounded-ctl border border-line bg-white px-4 font-semibold text-ink hover:bg-tile">이브에게 묻기</button>
                  {!crit && <button onClick={() => setBandOff((s) => [...s, bandCur.id])} aria-label="주의 알림 닫기" title="닫기 (알람은 알림 탭에 남아요)" className="grid h-10 w-10 shrink-0 place-items-center rounded-ctl text-[18px] text-ink-2 hover:bg-tile hover:text-ink">✕</button>}
                </div>
              ); })()}
            </>)}
            {show3D && (
              <>
                {screen === 'field' && (
                  <div className="pointer-events-auto absolute left-3 top-3 z-10 flex gap-1 rounded-full border border-line bg-white/90 p-1 shadow-md">
                    {ZONES.map(([name, , ids]) => <button key={name} onClick={() => { setZone(name); setSnapSel(null); api3d()?.frameGroup(ids); }} className={`h-10 rounded-full px-4 text-card font-bold ${zone === name ? 'bg-brand-tint text-brand-ink' : 'hover:bg-tile'}`}>{name}</button>)}
                    <button onClick={() => { setZone(null); setSnapSel(null); api3d()?.setView('front'); }} className={`h-10 rounded-full px-4 text-card font-bold ${zone === null ? 'bg-brand-tint text-brand-ink' : 'hover:bg-tile'}`}>전체</button>
                  </div>
                )}
                {/* 3D 조작: 홈 = 왼쪽 유리 줄 (시안 3a), 현장 모니터 = 오른쪽 위 확대·축소만 */}
                {home ? (
                <div className="pointer-events-auto absolute left-5 top-[92px] flex flex-row gap-1 rounded-stage border border-line bg-white p-1.5 shadow-card">{/* 홈: 왼쪽 위 가로 줄 (시안 C 확정, 2026-10-20) */}
                  {(() => { const sb = 'h-12 w-14 rounded-card text-card font-semibold text-ink-2 hover:bg-tile'; return (<>
                    <span className="flex h-12 w-14 items-center justify-center rounded-card bg-brand-tint text-card font-bold text-brand-ink" aria-current="true">3D</span>
                    <button onClick={() => go('layout2d')} className={sb}>2D</button>
                    <button onClick={() => { api3d()?.setView('front'); setSnapSel(null); }} className={sb}>전체</button>
                    <button onClick={() => api3d()?.setView('top')} className={sb}>위</button>
                    <button onClick={() => api3d()?.nav('zoom', 0.85)} className={`${sb} text-title`} aria-label="확대">+</button>
                    <button onClick={() => api3d()?.nav('zoom', 1.18)} className={`${sb} text-title`} aria-label="축소">−</button>
                  </>); })()}
                </div>
                ) : screen === 'field' ? (
                  <div className="pointer-events-auto absolute right-3 top-3 z-10 flex gap-1 rounded-full border border-line bg-white/90 p-1 shadow-md">
                    <button onClick={() => api3d()?.nav('zoom', 0.85)} className="h-11 w-11 rounded-full text-[22px] font-bold leading-none hover:bg-brand-tint" aria-label="확대">+</button>
                    <button onClick={() => api3d()?.nav('zoom', 1.18)} className="h-11 w-11 rounded-full text-[22px] font-bold leading-none hover:bg-brand-tint" aria-label="축소">−</button>
                  </div>
                ) : null}
                {home && <HomeHud />}
              </>
            )}
          </div>

          {screen === 'layout2d' && <Layout2D />}
          {(screen === 'layout2d' || fieldSel) && (
            <div className={screen === 'layout2d' ? 'absolute bottom-3 left-4 right-4 h-[var(--panelH)]' : `absolute bottom-0 left-0 right-0 h-[var(--panelH)] border-t border-line bg-ground`}><Panels field={screen === 'field'} ids={screen === 'field' && zone && !snapSel ? ZONES.find((z) => z[0] === zone)?.[2] : undefined} /></div>
          )}          {screen === 'replay' && <ReplayScreen />}
          {screen === 'cards' && <CardList />}
          {screen === 'card' && key && <CardScreen alertId={key} />}
          {(screen === 'docs' || DOC_OF[screen] || QUAL_OF[screen]) && (() => {
            // 문서·품질 하위 항목은 왼쪽 메뉴 묶음에 다 있어 화면 옆 목록은 없음. 예방 정비는 화면 위쪽 칩 탭 (PmScreen.tsx)
            return (
              <div className="absolute inset-0 flex bg-ground">
                <div className="relative min-w-0 flex-1">
                  {screen === 'docs' && <DocBox />}
                  {screen === 'wo' && key && <WorkOrderScreen no={key} />}
                  {screen === 'wr' && key && <WorkOrderScreen key={`wr:${key}`} no={key} focusRecord />}
                  {screen === 'sr' && key && <SimpleRecordScreen no={key} />}
                  {screen === 'shift' && <ShiftReportScreen />}
                  {screen === 'daily' && <DailyReportScreen />}
                  {screen === 'quality' && <QualityScreen />}
                  {screen === 'qcap' && <QualityScreen cap />}
                  {screen === 'revs' && <RevisionsScreen />}
                  {screen === 'idocs' && <DocsScreen />}
                </div>
              </div>
            );
          })()}
          {screen === 'pm' && <PmPage />}
          {screen === 'lots' && <LotScreen />}
          {screen === 'inventory' && <InventoryScreen />}
          {screen === 'tools' && <ToolsScreen />}
          {screen === 'settings' && <SettingsScreen />}
        </div>

        {/* 범례 [12] — 홈 · 2D 배치도 · 현장 모니터에서만 (사용자 요청 2026-10-21), 접을 수 없다 */}
        </div>
        {(home || screen === 'layout2d' || screen === 'field') && <footer className={`absolute bottom-3 left-4 right-4 z-20 flex h-[46px] items-center gap-5 overflow-x-auto rounded-card px-5 text-small text-ink ${GLASS}`}>{/* 3D 위에 뜬 유리 줄 (시안 3a) */}
          {LEGEND.map((l) => <span key={l.text} className="whitespace-nowrap">{l.text === '병목' ? <SnailBadge /> : <span style={{ color: l.color }}>{l.icon}</span>} {l.text}</span>)}
          <span className="ml-auto whitespace-nowrap">알림 <b className="text-crit">⚠ 긴급</b> <b className="ml-2 text-warn">▲ 주의</b> <span className="ml-2">ⓘ 참고</span></span>
        </footer>}

        <Eve tab={side} quick={home} onClose={closeSide} brief={<Briefing />} onNotice={openNotice} bubble={bubbleText} onBubble={onBubble}
          badges={{ 알림: open.length + myNotices.filter((n) => !n.handled).length, 브리핑: briefBubble ? 1 : 0 }}
          onPick={(t) => { if (t === '브리핑') setSeenBrief((s) => ({ ...s, [user.id]: twin?.shift.shift_id ?? '' })); setSide(t); }} />

        {emergencies[0] && (
          <Popup alert={emergencies[0]} others={emergencies.length - 1} big={screen === 'field'} sound={!hushed.includes(emergencies[0].id)}
            onCard={() => openCard(emergencies[0].id)} onAck={() => { hushAll(); setAcked((s) => ({ ...s, [user.id]: [...(s[user.id] ?? []), emergencies[0].id] })); }} />
        )}
        {source && <SourcePopup doc={source[0]} section={source[1]} onClose={() => setSource(null)} />}
        {toastMsg && <div className="fixed bottom-[100px] left-1/2 z-50 -translate-x-1/2 rounded-tile bg-ink px-4 py-3 text-body font-semibold text-white shadow-lg">{toastMsg}</div>}
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
    <div className="absolute right-0 top-[48px] z-30 w-[330px] rounded-tile border border-line bg-white p-3 text-small shadow-lg">
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={!settings.bloom} onChange={() => { const n = !settings.bloom; S('bloom', n); api3d()?.setState((s: any) => ({ layers: { ...s.layers, bloom: n } })); }} /> 3D 빛 효과 끄기</label>
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={!settings.sound} onChange={() => S('sound', !settings.sound)} /> 소리 끄기 (긴급 경고음은 못 끔)</label>
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={settings.cards} onChange={() => S('cards', !settings.cards)} /> 3D 위 설비 카드·측정 카드 보기 <span className="text-small text-ink-2">(설계서: 3D 위에는 상태·재공·병목만 — 기본 끔)</span></label>
      <div className="mt-2 border-t border-line-soft pt-2 font-bold">글자 크기 (2.4 계산식 H = D × 0.0058)</div>
      <div className="flex items-center gap-2">모니터 <input type="number" value={settings.monitorInch} onChange={(e) => S('monitorInch', Number(e.target.value) || 55)} className="h-11 w-16 rounded border border-line px-2" />인치 · 거리 <input type="number" step="0.5" value={settings.distanceM} onChange={(e) => S('distanceM', Number(e.target.value) || 3)} className="h-11 w-16 rounded border border-line px-2" />m</div>
      <p className="text-small text-ink-2">계산: 큰 숫자 {bigPx}px · 본문 {bodyPx}px (16:9 화면 가정). 값은 [선택 필요: 기술 회의] — 실제 장치에서 자로 재 확인</p>
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={settings.fontScale} onChange={() => S('fontScale', !settings.fontScale)} /> 계산한 크기로 현장 모니터 글자 키우기</label>
    </div>
  );
}
