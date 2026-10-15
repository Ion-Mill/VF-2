'use client';
// 화면 틀(UI설계서 2.1)과 화면 이동 — 데이터적용본. 값은 모두 시연 데이터 서버(생성기 실시간 모드 10/1 + 과거 기록 9월)에서 온다.
// 3D 장면(FactoryDashboard)은 로그인한 뒤 한 번만 만들고, 실시간(또는 다시 보기) 값을 applyLive로 넣는다.
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MachineId } from '@/components/types';
import { ID_OF, LAYOUT, LEGEND, MACHINES, MENU, ROLES, ROLE_COL, type Role } from './data';
import { Ctx, DEFAULT_SETTINGS, type AppCtx, type History, type Inv, type Screen, type Settings } from './ctx';
import { api, md, simIso, tsOf, useFetch, useLive, useLocal, usePersist, type SimEvent } from './live';
import { ALARMS, ROLE_NAME, SHIFT_NAME, USERS, homeScreen, levelOfSev, type AlertRec, type Notice, type UserRec } from './model';
import { derive, fromEvents, fromPast, repeatOf, type RuleCtx } from './rules';
import { LOCK } from './Safety';
import { nextNo, pad, rev, type SimpleRecord, type StopReason, type WorkOrder, type WorkRecord } from './workflow';
import { Eve, type EveTab } from './Eve';
import Briefing from './Briefing';
import CardScreen from './CardScreen';
import DocBox from './DocBox';
import FieldStrip from './FieldStrip';
import Layout2D from './Layout2D';
import Login from './Login';
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
import { PmScreen } from './PmScreen';
import { DocsScreen, SourcePopup } from './DocsScreen';
import { SettingsScreen } from './SettingsScreen';

const FactoryDashboard: any = dynamic(() => import('@/components/FactoryDashboard'), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center gap-2 bg-[#e9ecef]"><div className="h-3 w-48 animate-pulse rounded bg-slate-300" /><span className="text-[13px] text-slate-500">3D 불러오는 중…</span></div>,
});

const TITLE: Record<Screen, string> = {
  line: '3D 라인 뷰', layout2d: '3D 라인 뷰 · 2D 배치도', field: '현장 보기 · BRK-A100 라인', card: '지침카드', wo: '정비 작업지시서', wr: '작업기록서', sr: '간이 작업기록',
  stops: '정지 사유', docs: '문서함', replay: '다시 보기', shift: '교대 보고서', daily: '일일 보고서', revs: '수정 이력', lots: '로트 추적', quality: '검사 기록',
  inventory: '재고', tools: '공구 수명', pm: '예방 정비 일정', idocs: '사내 문서', settings: '설정',
};
const MENU_SCREEN: Record<string, Screen> = {
  '현장 보기': 'field', '3D 라인 뷰': 'line', '다시 보기': 'replay', '문서함': 'docs', '정지 사유': 'stops', '로트 추적': 'lots', '검사 기록': 'quality',
  '재고': 'inventory', '공구 수명': 'tools', '예방 정비': 'pm', '사내 문서': 'idocs', '설정': 'settings',
};
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
  const [screen, setScreen] = useState<Screen>(homeScreen(role));
  const [key, setKey] = useState<string | null>(null);
  const hist2 = useRef<[Screen, string | null][]>([]);
  const go = useCallback((s: Screen, k: string | null = null) => { hist2.current.push([screen, key]); setScreen(s); setKey(k); setMenu(false); setDemo(false); }, [screen, key]);
  const back = () => { const p = hist2.current.pop(); if (p) { setScreen(p[0]); setKey(p[1]); } else setScreen(homeScreen(role)); };
  useEffect(() => { setScreen(homeScreen(role)); setSide(null); setMenu(false); hist2.current = []; }, [user.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const [menu, setMenu] = useState(false);
  const [demo, setDemo] = useState(false);
  const [setOpen, setSetOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [side, setSide] = useState<EveTab | null>(null);
  const closeSide = useCallback(() => setSide(null), []);
  const [source, setSource] = useState<[string, string] | null>(null);
  const [toastMsg, setToast] = useState('');
  const toast = useCallback((m: string) => { setToast(m); setTimeout(() => setToast(''), 4500); }, []);

  // 현장 보기 자동 복귀 (SCR-26 — 시간 [선택 필요: 기술 회의], 화면 설정에서 바꿈)
  const lastAct = useRef(Date.now());
  useEffect(() => {
    const touch = () => { lastAct.current = Date.now(); };
    window.addEventListener('pointerdown', touch); window.addEventListener('keydown', touch);
    const t = setInterval(() => {
      if (role === 'OPR' && screen !== 'field' && settings.autoReturnSec > 0 && Date.now() - lastAct.current > settings.autoReturnSec * 1000) { setScreen('field'); setSide(null); }
    }, 2000);
    return () => { window.removeEventListener('pointerdown', touch); window.removeEventListener('keydown', touch); clearInterval(t); };
  }, [role, screen, settings.autoReturnSec]);

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
    selectMachine: (m) => { api3d()?.select(m); setSnapSel(m); }, selected: snapSel,
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
  const docBubbles = myNotices.filter((n) => n.delivery === 'BUBBLE' && !n.handled);
  const briefBubble = !!twin && seenBrief[user.id] !== twin.shift.shift_id; // 교대 시작 뒤 첫 로그인 때 (9.9)
  const bubbleText = side ? null : docBubbles.length > 1 ? `확정·검토할 문서 ${docBubbles.length}건` : docBubbles[0]?.text ?? (briefBubble ? '이번 교대 브리핑이 준비됐어요' : null);
  const onBubble = () => {
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
  // 하단 패널: 펼침 = 윗줄 지표 + 아래 3칸, 접기 = 윗줄 지표만 (172px)
  // 현장 보기 = 설비 하나만 낮게 (3D를 크게 — SCR-26)
  const style: Record<string, string> = { '--panelH': screen === 'field' ? '260px' : panelOpen ? 'clamp(420px,50vh,620px)' : '173px' };
  if (settings.fontScale) { style['--fs-big'] = `${bigPx}px`; style['--fs-body'] = `${bodyPx}px`; }
  const show3D = screen === 'line' || screen === 'field' || screen === 'replay';
  const fieldSel = screen === 'field' && !!snapSel;
  const stagePos = screen === 'field' ? { left: 0, top: 0, right: 360, bottom: fieldSel ? 'var(--panelH)' : 0 } : screen === 'replay' ? { left: 0, top: 44, right: 0, bottom: 'var(--panelH)' } : { left: 0, top: 0, right: 0, bottom: 'var(--panelH)' };


  return (
    <Ctx.Provider value={ctx}>
      <div className={`flex h-screen flex-col bg-[#e9ecef] text-[#26303a] ${settings.fontScale ? 'fs-scaled' : ''}`} style={style as React.CSSProperties}>
        {/* 상단 바 [1]~[4],[7],[8],[14] */}
        <header className="relative z-20 flex h-[52px] shrink-0 items-center gap-2 border-b border-slate-300 bg-white px-3">
          <button onClick={() => setMenu((m) => !m)} className={btn} aria-label="메뉴">≡ 메뉴</button>
          {screen !== 'line' && <h1 className="truncate text-[16px] font-bold">{TITLE[screen]}</h1>}
          {/* 교대 이름 + 시연 날짜·시각 (크게) */}
          <span className={`flex items-baseline gap-2 whitespace-nowrap ${connected ? 'text-[#1f2933]' : 'text-slate-400'}`}>
            {twin ? (<>
              <span className="rounded bg-slate-100 px-2 py-0.5 text-[14px] font-semibold text-slate-600">{SHIFT_NAME[twin.shift.shift_type]}</span>
              <b className="font-mono text-[22px] tabular-nums">{md(twin.clock.sim_at)}</b>
              <b className="font-mono text-[26px] tabular-nums">{twin.clock.sim_at.slice(11, 16)}</b>
            </>) : <b className="font-mono text-[22px]">--:--</b>}
          </span>
          {twin && <span className="whitespace-nowrap rounded bg-slate-100 px-2 py-1 text-[12px] font-bold text-slate-600">시연 ×{twin.clock.speed}{twin.clock.paused ? ' · ⏸ 일시정지' : ''}{twin.clock.running_event ? ` · 사건 ${twin.clock.running_event}` : ''}</span>}
          <div className="relative ml-auto">
            <button onClick={() => { setSetOpen((s) => !s); setDemo(false); }} className={btn}>화면 설정</button>
            {setOpen && <SettingsPopover settings={settings} setSettings={setSettings} api3d={api3d} bigPx={bigPx} bodyPx={bodyPx} />}
          </div>
          <div className="relative">
            <button onClick={() => { setDemo((d) => !d); setSetOpen(false); }} className={btn}>시연 ▾</button>
            {demo && <SimPanel twin={twin} refresh={live.refresh} toast={toast} api3d={api3d} onClose={() => setDemo(false)} />}
          </div>
          <button onClick={() => setUser(null)} title="누르면 로그아웃" className="whitespace-nowrap text-[13px] font-semibold hover:underline">
            {ROLE_NAME[role]}({role}) {user.name}{user.procs.length ? ` · ${user.procs.join('·')}` : ''}
          </button>
        </header>

        {menu && (
          <nav className="absolute left-0 top-[52px] z-30 w-[250px] border-r border-slate-300 bg-white py-2 shadow-lg">
            {MENU.filter((m) => m[ROLE_COL[role]] !== '—').map((m) => {
              const s: Screen = m[0].startsWith('홈') ? homeScreen(role) : MENU_SCREEN[m[0]];
              return (
                <button key={m[0]} onClick={() => { go(s); setMenu(false); }} className="flex h-11 w-full items-center justify-between px-4 text-left text-[14px] font-bold hover:bg-slate-100">
                  <span>{m[0]}</span><span className="text-[11px] font-normal text-slate-500">{m[ROLE_COL[role]]}</span>
                </button>
              );
            })}
          </nav>
        )}

        {/* 연결 끊김 띠 (2.8) · 3D 실패 띠 · 긴급 알림 띠 [9] */}
        {!connected && (
          <div className="flex h-10 shrink-0 items-center gap-2 bg-[#4b5a69] px-4 text-[14px] font-semibold text-white">
            ⚠ 연결 끊김 — 마지막 갱신 {live.lastOk ? live.lastOk.slice(11, 16) : '없음'} · 시연 데이터 서버(tools/sim_server.py)를 켜 주세요. 숫자는 회색, 3D 설비는 "기록 없음"
          </div>
        )}
        {fail3d && <div className="flex h-10 shrink-0 items-center gap-2 bg-[#fff1cc] px-4 text-[14px] font-semibold text-[#7a4b00]">▲ {fail3d} — 2D 배치도로 바꿨습니다 <button onClick={() => { setFail3d(null); go('line'); }} className="ml-2 underline">3D 다시 보기</button></div>}
        {band && (
          <button onClick={() => openCard(band.id)} className="flex h-10 shrink-0 items-center gap-2 bg-[#ffe1e1] px-4 text-left text-[14px] font-semibold text-[#a01e23]">
            <span>⚠ 긴급</span><span>{MACHINES[band.machine].name}</span><span className="font-normal">{band.alarm ? `${band.code} ${band.alarm.nameKo}` : `${band.code} (알람 코드집에 없음)`} · {band.time.slice(11, 16)} →</span>
          </button>
        )}

        <div className={`relative min-h-0 flex-1 overflow-hidden ${connected ? '' : 'grayscale-[0.6]'}`}>
          <div className="absolute" style={{ ...stagePos, visibility: show3D ? 'visible' : 'hidden', pointerEvents: show3D ? 'auto' : 'none' }}>
            <FactoryDashboard embedded dataMode layout={LAYOUT} quality="자동" introOnLoad={false} showCards={settings.cards} alarmText={alarmText} cardText={cardText}
              cmmCard={cmmCard} bigTags={screen === 'field'} scenario="정상 가동" onReady={onReady}
              onSnapshot={(s: { sel: MachineId | null }) => setSnapSel(s.sel)} onSelect={(id: MachineId) => setSnapSel(id)}
              onFail={(why: string) => { setFail3d(why); setScreen('layout2d'); }} />
            {show3D && screen !== 'replay' && (
              <>
                <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2">
                  <button onClick={() => go('layout2d')} className={`${btn} pointer-events-auto`}>2D 배치도로</button>
                  <div className="pointer-events-auto flex gap-1 rounded-md bg-white/80 p-1">
                    <button onClick={() => { api3d()?.setView('front'); setSnapSel(null); }} className={btn}>전체</button>
                    {screen === 'line' && <button onClick={() => api3d()?.setView('op30')} className={btn}>OP-30</button>}
                    {screen === 'line' && <button onClick={() => api3d()?.setView('top')} className={btn}>위</button>}
                    <button onClick={() => api3d()?.nav('zoom', 0.85)} className={btn} aria-label="확대">+</button>
                    <button onClick={() => api3d()?.nav('zoom', 1.18)} className={btn} aria-label="축소">−</button>
                  </div>
                </div>
                <div className="pointer-events-none absolute bottom-2 left-3 text-[12px] text-slate-700">설비 클릭(탭) = 확대 · 스크롤(두 손가락) = 확대/축소 · 끌기 = 각도 · 호버 = 반응 없음</div>
              </>
            )}
          </div>

          {screen === 'layout2d' && <Layout2D />}
          {(screen === 'line' || screen === 'layout2d' || fieldSel) && (
            <div className={`absolute bottom-0 left-0 ${screen === 'field' ? 'right-[360px]' : 'right-0'} h-[var(--panelH)] border-t border-slate-300`}><Panels open={panelOpen} onToggle={() => setPanelOpen((o) => !o)} field={screen === 'field'} /></div>
          )}
          {screen === 'field' && <div className="absolute bottom-0 right-0 top-0 w-[360px]"><FieldStrip onBriefing={() => { setSeenBrief((s) => ({ ...s, [user.id]: twin?.shift.shift_id ?? '' })); setSide('브리핑'); }} /></div>}
          {screen === 'replay' && <ReplayScreen />}
          {screen === 'card' && key && <CardScreen alertId={key} />}
          {screen === 'wo' && key && <WorkOrderScreen no={key} />}
          {screen === 'wr' && key && <WorkRecordScreen woNo={key} />}
          {screen === 'sr' && key && <SimpleRecordScreen no={key} />}
          {screen === 'stops' && <StopsScreen />}
          {screen === 'docs' && <DocBox />}
          {screen === 'shift' && <ShiftReportScreen />}
          {screen === 'daily' && <DailyReportScreen />}
          {screen === 'revs' && <RevisionsScreen />}
          {screen === 'lots' && <LotScreen />}
          {screen === 'quality' && <QualityScreen />}
          {screen === 'inventory' && <InventoryScreen />}
          {screen === 'tools' && <ToolsScreen />}
          {screen === 'pm' && <PmScreen />}
          {screen === 'idocs' && <DocsScreen />}
          {screen === 'settings' && <SettingsScreen />}
        </div>

        {/* 범례 [12] — 항상 보이고 접을 수 없다 */}
        <footer className="flex h-[38px] shrink-0 items-center gap-4 overflow-x-auto border-t border-slate-300 bg-white px-3 text-[13px]">
          <b>범례</b>
          {LEGEND.map((l) => <span key={l.text} className="whitespace-nowrap"><span style={{ color: l.color }}>{l.icon}</span> {l.text}</span>)}
          <span className="ml-auto whitespace-nowrap text-slate-600">알림: <b className="text-[#c62a2f]">⚠ 긴급</b> │ <b className="text-[#9a6200]">▲ 주의</b> │ ⓘ 참고</span>
        </footer>

        <Eve tab={side} onClose={closeSide} brief={<Briefing />} onNotice={openNotice} bubble={bubbleText} onBubble={onBubble}
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
      <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5" checked={settings.fontScale} onChange={() => S('fontScale', !settings.fontScale)} /> 계산한 크기로 현장 보기 글자 키우기</label>
      <div className="flex items-center gap-2">현장 보기 자동 복귀 <input type="number" value={settings.autoReturnSec} onChange={(e) => S('autoReturnSec', Number(e.target.value) || 0)} className="h-11 w-20 rounded border border-slate-300 px-2" />초 <span className="text-[11px] text-slate-500">(OPR, 0 = 끔 · [가상])</span></div>
    </div>
  );
}
