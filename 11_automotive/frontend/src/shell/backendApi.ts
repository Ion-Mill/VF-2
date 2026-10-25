'use client';
// 화면 → 백엔드 전환 (C2, 2026-10-23 — 기획서 12.1 "화면은 백엔드만", 팀과 논의/비서_시뮬레이터_DB_연결_논의_20261017.md 3장 C2).
//
//   **기본 켜짐 (2026-10-24, 사용자 결정 "지금 기본값을 백엔드로")** — 끄려면 NEXT_PUBLIC_MOM_BACKEND=0 (예전처럼 시연 서버 sim_server.py 직접).
//   백엔드 주소: NEXT_PUBLIC_MOM_API가 있으면 그 주소를 브라우저가 직접(CORS 필요), 없으면 같은 주소 /api — 화면 서버(next.config.mjs)가
//   백엔드(MOM_BACKEND_URL, 기본 http://127.0.0.1:8000)로 넘긴다. 배포(같은 주소 아래 /api)도 이 길.
//   화면 ──▶ 백엔드(FastAPI) ──▶ DB.   시뮬레이터(가짜 공장)는 DB 중계로 DB에 쓰고, 시연 조작은 백엔드가 시뮬레이터에 넘긴다 (backend/app/services/sim_link.py).
//
// live.ts api()가 시연 서버 주소 이름(line/twin, lots …) 그대로 여기로 넘기면, 백엔드 API를 불러 화면이 쓰던 모양으로 바꿔 돌려준다.
// 그래서 화면 부품은 고치지 않는다. 바꾸는 규칙은 아래 함수마다 적었다. 이 단계에서 아직 화면 안(localStorage)에 두는 것:
// 작업지시서·작업기록서·간이 기록·알림 처리·화면 알림 규칙(rules.ts) — 재료는 백엔드 값으로 판단한다 (다음 단계에서 서버 알림·문서로).
// 로그인: 화면 로그인 때 백엔드 /api/auth/login 으로 토큰을 받아 메모리에만 둔다 (새로 고침하면 다시 로그인).
import { LAYOUT, MASTERS } from './data';
import type { Eq } from './live';

const BASE = (process.env.NEXT_PUBLIC_MOM_API ?? '').trim().replace(/\/+$/, '');
export const backendMode = () => process.env.NEXT_PUBLIC_MOM_BACKEND !== '0';

export class BackendErr extends Error { constructor(public code: string, msg: string, public status = 0) { super(msg); } }

const EQS: Eq[] = ['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'];
type J = Record<string, any>;

// ---------------- 로그인 ----------------
let session: { userId: string; token: string } | null = null;

export async function backendLogin(userId: string, password: string): Promise<void> {
  const r = await fetch(BASE + '/api/auth/login', { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, password }) })
    .catch(() => { throw new BackendErr('CONNECTION', '백엔드 서버에 연결하지 못했습니다'); });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || typeof j.access_token !== 'string') throw new BackendErr(j.code ?? 'UNAUTHORIZED', j.message ?? '아이디 또는 비밀번호가 맞지 않습니다', r.status);
  session = { userId, token: j.access_token };
  resetDerived();
}
export function backendLogout() { session = null; resetDerived(); }
/** 이 사용자의 화면 로그인 토큰 (이브 채팅이 같이 쓴다, assistantApi.ts) */
export const backendToken = (userId: string) => (session?.userId === userId ? session.token : null);

async function call(method: string, path: string, body?: unknown): Promise<any> {
  if (!session) throw new BackendErr('UNAUTHORIZED', '로그인이 필요합니다', 401);
  let r: Response;
  try {
    r = await fetch(BASE + '/api/' + path, {
      method, cache: 'no-store',
      headers: { Authorization: `Bearer ${session.token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new BackendErr('CONNECTION', '백엔드 서버에 연결하지 못했습니다');
  }
  const j = await r.json().catch(() => ({ code: 'SERVER', message: '응답을 읽지 못했습니다' }));
  if (!r.ok) throw new BackendErr(j.code ?? 'SERVER', j.message ?? '서버 오류', r.status);
  return j;
}
const get = (path: string) => call('GET', path);
const post = (path: string, body: unknown = {}) => call('POST', path, body);
const qs = (o: Record<string, string | number | boolean | null | undefined>) =>
  Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&');

// ---------------- 공통 바꾸기 ----------------
const num = (v: unknown) => (v === null || v === undefined || v === '' ? null : Number(v));
const floor = (v: unknown) => Math.floor(Number(v ?? 0));
/** 백엔드 알람 줄 → 화면 AlarmEv (severity_at_event → severity) */
export const alarmEv = (a: J) => ({
  alarm_event_id: Number(a.alarm_event_id), equipment_id: a.equipment_id as Eq, alarm_code: String(a.alarm_code),
  severity: (a.severity_at_event ?? a.severity) as 'STOP' | 'WARN' | 'GUIDE', occurred_at: a.occurred_at, cleared_at: a.cleared_at ?? null,
  lot_no: a.lot_no ?? null, prev_alarm_event_id: num(a.prev_alarm_event_id), scenario_code: a.scenario_code ?? null,
});
const stdCycle = (eq: Eq) => {
  const e = LAYOUT.equipment[eq];
  return e?.std_cycle_min ?? e?.batch_time_min ?? 7;
};
const oee = (k: J | undefined, warnAvail: boolean) => {
  if (!k) return { oee_pct: null, availability_pct: null, performance_pct: null, quality_pct: null, apt_min: 0, pbt_min: 0, pq: 0, good_qty: 0, warn: [] as string[] };
  const warn: string[] = [];
  if (warnAvail && (k.is_availability_warn ?? (k.availability_pct != null && k.availability_pct < 60))) warn.push('가동률');
  if (k.is_oee_warn ?? (k.oee_pct != null && k.oee_pct < 59)) warn.push('OEE');
  return {
    oee_pct: num(k.oee_pct), availability_pct: num(k.availability_pct), performance_pct: num(k.performance_pct), quality_pct: num(k.quality_pct),
    apt_min: Number(k.run_min ?? 0), pbt_min: Number(k.pbt_min ?? k.line_pbt_min ?? 0), pq: Number(k.pq ?? 0), good_qty: Number(k.good_qty ?? (Number(k.gq ?? 0) + Number(k.rq ?? 0))), warn,
  };
};

// ---------------- 실시간 트윈 (API-LINE-02, 1초마다) ----------------
let lastTwin: J | null = null;            // 사건 만들기·다른 조회가 같이 쓴다

async function twin(): Promise<J> {
  const b = await get('line/twin?full=true');
  const sim: J = b.sim ?? {};
  const now: string = sim.sim_at ?? b.now;
  const alarms = [...(b.alarms ?? [])].map(alarmEv).sort((x, y) => (x.occurred_at < y.occurred_at ? -1 : x.occurred_at > y.occurred_at ? 1 : x.alarm_event_id - y.alarm_event_id));
  const byId = new Map(alarms.map((a) => [a.alarm_event_id, a]));
  const kEq = new Map<string, J>((b.kpi_equipment ?? []).map((k: J) => [k.equipment_id, k]));
  const process: Record<string, { pq: number; good: number; scrap: number }> = {};
  for (const p of ['OP-10', 'OP-20', 'OP-30', 'OP-40', 'OP-50']) process[p] = { pq: 0, good: 0, scrap: 0 };
  for (const k of b.kpi_equipment ?? []) {
    const p = process[k.process_code] ?? (process[k.process_code] = { pq: 0, good: 0, scrap: 0 });
    p.pq += Number(k.pq ?? 0); p.good += Number(k.gq ?? 0) + Number(k.rq ?? 0); p.scrap += Number(k.sq ?? 0);
  }
  const equipment: J = {};
  for (const e of b.equipment ?? []) {
    const eq = e.equipment_id as Eq;
    const st = (b.stops ?? []).find((x: J) => x.equipment_id === eq);
    const rs = (b.reasons ?? []).find((x: J) => x.equipment_id === eq);
    const aid = num(e.state_alarm_event_id) ?? num(e.open_alarm_event_id);
    const sens = (b.sensors ?? []).filter((x: J) => x.equipment_id === eq);
    equipment[eq] = {
      state_code: e.state_code, reason_code: rs?.reason_code ?? e.reason_code ?? null, reason_name: rs?.reason_name ?? null, warn_marker: !!e.warn_marker,
      alarm: aid != null ? byId.get(aid) ?? null : null, since_at: e.state_since, minutes: floor(e.state_minutes), lot_no: e.current_lot_no ?? null,
      parts_in: e.state_code === 'RUN' || e.state_code === 'DOWN' ? 1 : 0, cycle_progress: null, slow: false,   // 시뮬레이터 안쪽 값 — DB에는 없어 상태로 어림 (가공 중 고장도 부품은 안에)
      shift_actual_qty: Number(kEq.get(eq)?.pq ?? 0), process_actual_qty: process[e.process_code]?.pq ?? 0, process_code: e.process_code,
      stop_min: Number(st?.stop_min ?? 0), loss_qty: Number(st?.loss_qty ?? 0), is_estimated: true, std_cycle_min: stdCycle(eq),
      tools: (b.tools ?? []).filter((t: J) => t.equipment_id === eq).sort((x: J, y: J) => (x.tool_id < y.tool_id ? -1 : 1)).map(toolRow),
      sensor: sens.length ? Object.fromEntries(sens.map((x: J) => [x.sensor_code, Number(x.value)])) : null,
    };
  }
  const s: J = b.shift ?? {};
  const wip: Record<string, number> = {}, wipLimits: J = {};
  let soak = 0;
  for (const w of b.wip ?? []) {
    wip[w.buffer_code] = Number(w.wip_qty ?? 0);
    wipLimits[w.buffer_code] = { limit: Number(w.limit_qty), warn_over: num(w.warn_over_qty), warn: !!w.warn_enabled };
    if (w.soak_shelf_qty != null) soak = Number(w.soak_shelf_qty);
  }
  const total = Number(s.total_target_qty ?? 0), elapsed = Number(s.elapsed_min ?? 0);
  const hourly = [{ at: s.start_at, cum: 0 }, ...(b.hourly ?? []).map((h: J) => ({ at: (h.hour_end < now ? h.hour_end : now), cum: Number(h.cum_qty ?? 0) }))];
  const rel: J = {};
  for (const r of b.reliability ?? []) rel[r.equipment_id] = { failures: Number(r.failure_count ?? 0), mttr_min: num(r.mttr_min), mtbf_h: num(r.mtbf_hours), mttr_warn: !!r.is_mttr_warn };
  const out = {
    run_id: Number(sim.run_id ?? 1),
    clock: { sim_at: now, speed: Number(sim.speed ?? 1), paused: !!sim.paused, running_event: sim.running_event ?? null, buttons_locked: !!sim.buttons_locked, finished: !!sim.finished, can_control: b.sim_control !== false },
    buttons: sim.buttons ?? {},
    shift: { shift_id: s.shift_id, shift_type: s.shift_type, start_at: s.start_at, end_at: s.end_at, supervisor_user_id: s.supervisor_user_id },
    equipment, wip, soak_qty: soak, wip_limits: wipLimits,
    bottleneck: { process_code: b.bottleneck?.process_code ?? 'OP-30', cause_code: b.bottleneck?.cause_code ?? 'BASE', alarm_event_id: null, since_at: b.bottleneck?.changed_at ?? null },
    process, done_today: Number(b.done_today ?? 0), alarms, holds: [],
    suspect_lot: (b.suspect_lots ?? [])[0]?.lot_no ?? null,
    // 진행 중 사건의 설비 = 그 사건 알람이 난 설비 (시뮬레이터 시계에는 사건 이름만)
    running_event: sim.running_event ? { code: String(sim.running_event), equipment_id: [...alarms].reverse().find((a) => a.scenario_code === sim.running_event)?.equipment_id ?? null } : null,
    last_measure: [...(b.last_measure ?? [])].reverse().map((r: J) => ({ ...r, measured_value: Number(r.measured_value) })),
    production: {
      shift_id: s.shift_id, shift_type: s.shift_type, start_at: s.start_at, end_at: s.end_at, target_qty: Number(s.target_qty ?? 0), carry_over_qty: Number(s.carry_over_qty ?? 0),
      total_target_qty: total, actual_qty: Number(s.actual_qty ?? 0), forecast_qty: Number(s.forecast_qty ?? 0), short_qty: Number(s.shortfall_qty ?? 0),
      rate_per_hour: Math.round(Number(s.rate_per_min ?? 0) * 600) / 10, elapsed_work_min: elapsed, left_work_min: Number(s.remaining_min ?? 0),
      risk: !!s.is_target_risk && elapsed >= 60, risk_line_qty: Math.round(0.9 * total * 10) / 10, hourly,
      failure_loss_qty: Number(s.failure_loss_qty ?? 0), speed_loss_qty: Number(s.speed_loss_qty ?? 0), loss_qty: Number(s.loss_qty ?? 0),
      short_stops: {   // 고장 그룹 5분 미만 정지 (백엔드 line.shift_equipment_stops short_count·short_min, 2026-10-24)
        count: (b.stops ?? []).reduce((n: number, x: J) => n + Number(x.short_count ?? 0), 0),
        minutes: (b.stops ?? []).reduce((n: number, x: J) => n + Number(x.short_min ?? 0), 0),
      }, supervisor_user_id: s.supervisor_user_id, is_estimated: true,
    },
    kpi: {
      from: s.start_at, to: now,
      by: { 'VF2-01': oee(kEq.get('VF2-01'), true), 'VF2-02': oee(kEq.get('VF2-02'), true), LINE: oee(lineOee(b), false) },
      mttr_mtbf: rel,
    },
    orders: orders(b.orders ?? [], now),
    live_from: b.live_from,
  };
  lastTwin = { ...out, _tools: b.tools ?? [], _bn: b.bottleneck_log ?? [] };
  return out;
}

const lineOee = (b: J) => {
  const l = b.line_oee;
  if (!l) return undefined;
  const good = (b.kpi_equipment ?? []).filter((k: J) => k.process_code === 'OP-30').reduce((n: number, k: J) => n + Number(k.gq ?? 0) + Number(k.rq ?? 0), 0);
  return { ...l, good_qty: good };
};

const toolRow = (t: J) => ({
  tool_id: t.tool_id, tool_no: t.tool_no, item_no: t.item_no, equipment_id: t.equipment_id as Eq, usage_pct: Number(t.usage_rate_pct ?? 0),
  cum: Number(t.cum_usage ?? 0), limit: Number(t.life_limit ?? 0), per_part: Number(t.usage_per_part ?? 0), left_parts: num(t.parts_left),
  warn: Number(t.usage_rate_pct ?? 0) >= 90,
});

/** 작업지시 진행 (API-LINE-05). 시연 서버처럼 끝난 지 24시간 넘은 것은 빼고, 오래된 것부터.
 *  지연 위험(▲)은 남은 수량 × 3.5분 > 납기까지 근무 분(하루 16시간으로 어림) — 시연 서버와 같은 어림 (추정) */
function orders(rows: J[], now: string) {
  const t = Date.parse(now);
  return rows
    .filter((o) => !(o.completed_at && Date.parse(o.completed_at) < t - 24 * 3600e3) && o.status !== 'CANCELLED')
    .sort((a, b) => (a.order_no < b.order_no ? -1 : 1))
    .map((o) => {
      const done = Number(o.completed_qty ?? 0), left = Number(o.order_qty ?? 0) - done;
      const late = o.status !== 'COMPLETED' && o.due_at && Date.parse(o.due_at) < t;
      const risk = !late && o.status !== 'COMPLETED' && o.due_at && left * 3.5 > ((Date.parse(o.due_at) - t) / 60000) * (16 / 24);
      return {
        order_no: o.order_no, order_qty: Number(o.order_qty ?? 0), done_qty: done, defect_qty: Number(o.defect_qty ?? 0),
        lots: o.lot_nos ? String(o.lot_nos).split(',') : [], current_process: o.current_process_code ?? (o.status === 'WAITING' ? '—' : 'OP-50'),
        due_at: o.due_at, status: o.status, delay: late ? '지연' : risk ? '▲ 지연 위험' : null, started_at: o.started_at ?? null, completed_at: o.completed_at ?? null,
      };
    });
}

// ---------------- 실시간 사건 (API-STR-01) ----------------
// 화면이 쓰는 사건은 둘뿐(rules.ts fromEvents): 공구 수명 90%(tool_life)·병목 바뀜(bottleneck_changed).
// 병목은 DB 병목 기록 그대로(시각도 그대로), 공구는 트윈을 받을 때마다 90%를 넘은 공구를 사건으로 만든다.
// 백엔드 SSE는 DB 중계가 넣는 줄(설비 상태·알람)에는 오지 않아(app.loading) 1초 조회를 그대로 쓴다.
let seq = 0;
let sent = new Set<string>();
let toolSeen = new Map<string, number>();
let evRun: number | null = null;
function resetDerived() { seq = 0; sent = new Set(); toolSeen = new Map(); evRun = null; lastTwin = null; }

async function events(after: number): Promise<J> {
  const t = lastTwin ?? (await twin(), lastTwin);
  if (!t) return { run_id: 1, seq: 0, events: [] };
  if (evRun !== null && evRun !== t.run_id) { seq = 0; sent = new Set(); toolSeen = new Map(); }  // [처음으로] — 화면도 seq를 0으로 되돌린다
  evRun = t.run_id;
  const out: J[] = [];
  const push = (key: string, e: J) => { if (!sent.has(key)) { sent.add(key); out.push({ seq: ++seq, ...e }); } };
  for (const r of t._bn as J[]) {
    push(`bn:${r.bottleneck_log_id}`, { type: 'bottleneck_changed', at: r.changed_at, process_code: r.process_code, cause_code: r.cause_code, prev_process_code: r.prev_process_code });
  }
  for (const tl of t._tools as J[]) {
    const pct = Number(tl.usage_rate_pct ?? 0), before = toolSeen.get(tl.tool_id);
    toolSeen.set(tl.tool_id, pct);
    if (pct >= 90 && before !== undefined && before < 90) {
      // 시연 서버처럼 90%를 넘는 그때만 (처음 받을 때 이미 넘은 공구는 화면 규칙 rules.ts가 트윈 값으로 판단)
      const at = t.clock.sim_at;
      push(`tool:${tl.tool_id}:${at}`, { type: 'tool_life', at, tool_id: tl.tool_id, usage_pct: pct });
    }
  }
  return { run_id: t.run_id, seq, events: after > seq ? [] : out };
}

// ---------------- 다시 보기 (API-LINE-06) ----------------
async function replay(q: URLSearchParams): Promise<J> {
  const b = await get('replay?' + qs({ from: q.get('from'), to: q.get('to') }));
  const to: string = b.to, from: string = b.from;
  const clip = (x: string) => (x < from ? from : x > to ? to : x);
  const states: J = Object.fromEntries(EQS.map((e) => [e, [] as J[]]));
  for (const s of b.states ?? []) {
    (states[s.equipment_id] ??= []).push({
      start_at: clip(s.start_at), end_at: clip(s.end_at ?? to), state_code: s.state_code, reason_code: s.reason_code ?? s.reason_suggested_code ?? null,
      warn_marker: !!s.warn_marker, alarm_event_id: num(s.alarm_event_id),
    });
  }
  const wipAt = new Map<string, J>();
  for (const w of b.wip ?? []) {
    const r = wipAt.get(w.logged_at) ?? { at: w.logged_at };
    r[w.buffer_code] = Number(w.wip_qty ?? 0);
    if (w.soak_shelf_qty != null) r.SOAK = Number(w.soak_shelf_qty);
    wipAt.set(w.logged_at, r);
  }
  const done: string[] = [];
  for (const d of b.done ?? []) for (let i = 0; i < Number(d.qty ?? 0); i++) done.push(d.end_at);
  return {
    from, to, step_min: 1, states, wip: [...wipAt.values()].sort((x, y) => (x.at < y.at ? -1 : 1)),
    bottleneck: (b.bottleneck ?? []).map((r: J) => ({ at: r.changed_at, process_code: r.process_code, cause_code: r.cause_code, prev_process_code: r.prev_process_code })),
    alarms: [...(b.alarms ?? [])].map(alarmEv).reverse(), sensors: {}, done,
  };
}

/** 실시간 구간 시작 (10/1 08:00). 트윈을 아직 안 받았으면 먼저 받는다 (화면을 트윈보다 먼저 열 때) */
async function liveFrom(): Promise<string> {
  if (!lastTwin) await twin();
  return lastTwin?.live_from ?? '9999';
}

// ---------------- 보고서·문서 (API-RPT-01~05, DOC-02) ----------------
// 시연 서버는 9월 기록을 CSV 글자 그대로 줬다 — 화면이 번호를 글자로 비교하는 곳이 있어(예 Reports.tsx alarm_event_id === String(…)) 과거 줄은 글자로 맞춘다
const csvRow = (r: J) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v)]));
const FIELD_ORDER = ['증상', '원인', '조치', '특이 사항', '인계 사항', '오늘의 문제'];     // 바뀐 칸 순서 = 생성기·시연 서버 순서 (문서 화면 칸 순서)
// 백엔드가 새로 남기는 버전은 칸 이름이 영어 키 — 9월 기록(생성기)처럼 한국어 칸 이름으로 보인다
const FIELD_KO: Record<string, string> = { notable_text: '특이 사항', handover_text: '인계 사항', issues_summary: '오늘의 문제', memo: '관리자 메모', symptom: '증상', cause: '원인', action: '조치', title: '제목' };
const fieldKo = (c: J) => ({ ...c, field_name: FIELD_KO[c.field_name] ?? c.field_name });
const byField = (a: J, b: J) => (FIELD_ORDER.indexOf(a.field_name) - FIELD_ORDER.indexOf(b.field_name)) || (a.field_name < b.field_name ? -1 : 1);
const forbiddenAsEmpty = <T,>(p: Promise<T>, empty: T) => p.catch((e) => { if (e instanceof BackendErr && e.status === 403) return empty; throw e; });

async function docRevisions(docType: string, key: string) {
  const revs: J[] = await forbiddenAsEmpty(get(`documents/${docType}/${encodeURIComponent(key)}/revisions`), []);
  const changes: J = {};
  await Promise.all(revs.map(async (r) => {
    const d = await get(`documents/revisions/${r.revision_id}`).catch(() => null);
    changes[String(r.revision_id)] = (d?.changes ?? []).map((c: J) => fieldKo({ revision_id: String(r.revision_id), field_name: c.field, before_value: c.before, after_value: c.after })).sort(byField);
  }));
  return { revisions: revs.map((r) => ({ ...r, revision_id: String(r.revision_id), doc_type: docType, doc_key: key })), changes };
}

async function shiftReport(sid: string) {
  const r = await get(`reports/shift/${encodeURIComponent(sid)}`);
  let av = r.availability_pct;
  if (typeof av === 'string') { try { av = JSON.parse(av); } catch { av = null; } }
  return {
    ...r, availability: av ?? {}, lots: (r.lots ?? []).map((l: J) => (typeof l === 'string' ? l : l.lot_no)),
    // 병목: 기준 병목(OP-30 BASE)은 빼고 바뀐 것만 (시연 서버 보고서와 같음)
    bottleneck: (r.bottleneck ?? []).filter((b: J) => b.cause_code !== 'BASE').map((b: J) => ({ ...b, at: b.at ?? b.from_at })),
    partial: !!r.in_progress,      // 진행 중인 교대 = 저장하지 않는 미리보기 (백엔드 preview, 2026-10-24)
    ...(await docRevisions('SHIFT_REPORT', sid)),
  };
}

/** 교대 보고서 저장·확정·확정 후 수정 — 시연 서버는 한 번에 했고, 백엔드는 [고친 칸 저장(PATCH)] → [확정] 두 걸음 */
async function shiftReportAction(sid: string, action: string, b: J) {
  const cur = await get(`reports/shift/${encodeURIComponent(sid)}`);
  if (cur.preview) throw new BackendErr('INVALID_STATE', cur.in_progress ? '교대가 끝나면 보고서 초안이 생겨 저장·확정할 수 있어요 (지금은 진행 중 미리보기)' : '보고서 초안을 만드는 중이에요 — 잠시 뒤 다시 눌러 주세요', 409);
  const changes: J = {};
  for (const f of ['notable_text', 'handover_text']) if (f in b && (b[f] ?? '') !== (cur[f] ?? '')) changes[f] = b[f];
  let version = Number(b.version ?? cur.current_version ?? 0);
  if (action === 'revise') {
    await post(`reports/shift/${encodeURIComponent(sid)}/revise`, { reason: b.reason, changes, version });
  } else {
    if (Object.keys(changes).length) {
      const r = await call('PATCH', `reports/shift/${encodeURIComponent(sid)}`, { version, changes });
      version = Number(r.version_no ?? r.current_version ?? version + 1);
    }
    if (action === 'confirm') await post(`reports/shift/${encodeURIComponent(sid)}/confirm`, { version });
  }
  return shiftReport(sid);
}

async function dailyReport(d: string) {
  const r = await get(`reports/daily/${d}`);
  const list: J[] = await get('reports/shift').catch(() => []);
  const day = list.find((x) => x.shift_id === `${d}-D`), night = list.find((x) => x.shift_id === `${d}-N`);
  const range = [day?.start_at ?? `${d}T08:00:00+09:00`, night?.end_at ?? day?.end_at ?? null];
  const alarms = range[1] ? (await forbiddenAsEmpty(get('alarms?' + qs({ from: range[0], to: range[1], limit: 1000 })), [])).map(alarmEv).reverse() : [];
  return { ...r, range, alarms, ...(await docRevisions('DAILY_REPORT', d)) };
}

async function dailyConfirm(d: string, b: J) {
  const cur = await get(`reports/daily/${d}`);
  await post(`reports/daily/${d}/confirm`, { version: Number(cur.current_version ?? 0), ...(String(b.memo ?? '').trim() ? { memo: String(b.memo).trim() } : {}) });
  return dailyReport(d);
}

// ---------------- 알림·정비·사내 문서 ----------------
/** 9월에 처리 안 된 채 넘어온 알림 (10/1 시작 상태) — 백엔드 알림함은 이미 이 사용자 몫만 준다 */
async function pastOpen() {
  const n = await get('notifications?status=open');
  const from = await liveFrom();
  const me = session?.userId ?? '';
  return {
    notifications: (n.items ?? []).filter((x: J) => x.raised_at < from).map((x: J) => ({
      ...csvRow({ notification_id: x.notification_id, rule_code: x.rule_code, importance: x.importance, raised_at: x.raised_at, message: x.message,
        related_info: x.related_info, equipment_id: x.equipment_id, repeat_count: x.repeat_count, pm_task_id: x.pm_task_id, item_no: x.item_no,
        alarm_event_id: x.alarm_event_id, is_processed: x.is_processed, processed_at: x.processed_at }),
      to: [me],
    })),
  };
}

async function maintHistory() {
  const h = await get('maint/history');
  const grp = (g: J) => Object.fromEntries(Object.entries(g ?? {}).map(([k, rows]) => [k, (rows as J[]).map(csvRow)]));
  return { work_orders: (h.work_orders ?? []).map(csvRow), steps: grp(h.steps), work_records: (h.work_records ?? []).map(csvRow), checks: grp(h.checks), parts: grp(h.parts), alarms: (h.alarms ?? []).map(csvRow) };
}

async function pmSchedule() {
  const p = await get('maint/pm-schedule');
  const line = (p.on_time ?? []).find((r: J) => r.equipment_id === null);
  const order = new Map<string, number>(((MASTERS as unknown as J).pm_tasks ?? []).map((t: J, i: number) => [t.pm_task_id, i]));   // 기준 정보 순서 (시연 서버와 같음)
  const at = (id: string) => order.get(id) ?? 1e9;
  return {
    tasks: [...(p.items ?? [])].sort((a: J, b: J) => at(a.pm_task_id) - at(b.pm_task_id)).map((t: J) => {
      const od = num(t.days_overdue);
      return { ...t, next_due: t.next_due_date ?? null, last: t.last_done_at ? { done_at: t.last_done_at, by: t.last_done_by ?? null, status: t.last_status ?? null, due_date: t.last_due_date ?? null } : null,
        state: t.next_due_date == null ? null : od! > 0 ? 'OVERDUE' : od! >= -1 ? 'DUE_SOON' : 'OK' };
    }),
    on_time_rate_pct: num(line?.on_time_pct),
    planned_windows: (p.open_windows ?? []).map((w: J) => ({ equipment_id: w.equipment_id, start_at: w.start_at, end_at: w.end_at, kind: w.kind })),
    today_records: (p.today_records ?? []).map((r: J) => ({ ...r, pm_record_id: String(r.pm_record_id) })),
  };
}

const internalDocs = async () => ({ docs: (await get('internal-docs')).map((d: J) => ({ doc_no: d.doc_no, doc_name: d.doc_name, rev: d.current_rev, rev_date: d.rev_date, sections: [] })) });
const internalDoc = async (no: string) => { const d = await get(`internal-docs/${encodeURIComponent(no)}?sections=true`); return { doc_no: d.doc_no, doc_name: d.doc_name, rev: d.current_rev, rev_date: d.rev_date, sections: d.sections ?? [] }; };

// ---------------- 로트·품질 (API-LOT-01·02, QLT) ----------------
async function lots(q: URLSearchParams) {
  const lot = q.get('lot') ?? '';
  const r = await get('lots/screen?' + qs({ lot }));
  return {
    lots: (r.lots ?? []).map((l: J) => {
      const pd: J = { 'OP-10': 0, 'OP-20': 0, 'OP-30': 0, 'OP-40': 0, 'OP-50': 0, ...(l.process_done ?? {}) };
      pd.DONE = pd['OP-50'];
      return {
        lot_no: l.lot_no, order_no: l.order_no, lot_seq: l.lot_seq, input_shift_id: l.input_shift_id, material_lot_no: l.material_lot_no, input_qty: Number(l.input_qty ?? 0),
        status: l.status, scrap_qty: Number(l.scrap_qty ?? 0), fg_qty: Number(l.fg_in_qty ?? 0), finished: Number(l.completed_qty ?? 0), on_hold: l.status === 'ON_HOLD',
        enhanced: l.plan_mode === 'ENHANCED', enhance_reason: l.enhance_reason ?? null, insp_fail: Number(l.gauge_fail_qty ?? 0),
        plan_mode: l.plan_mode ?? null, judgement: l.plan_judgement ?? null, gauge_pass_qty: num(l.gauge_pass_qty), gauge_fail_qty: num(l.gauge_fail_qty),
        judged_at: l.judged_at ?? null, passed_at: l.passed_at ?? null, first_in_at: l.first_in_at ?? null, process_done: pd,
        hold: l.hold ? { ...l.hold, hold_id: num(l.hold.hold_id) } : null,
        shipped: { qty: Number(l.shipped_qty ?? 0), shipments: (l.shipments ?? []).map((s: J) => ({ shipment_no: s.shipment_no, customer_code: s.customer_code, shipped_at: s.shipped_at })) },
      };
    }),
    suspect_lot: lastTwin?.suspect_lot ?? null,
    past_holds: (r.past_holds ?? []).map(csvRow),
    materials: Object.fromEntries((r.materials ?? []).map((m: J) => [m.material_lot_no, csvRow(m)])),
    reports: (r.reports ?? []).map((x: J) => ({ ...x, pq: Number(x.pq), gq: Number(x.gq), rq: Number(x.rq), sq: Number(x.sq) })),
    alarms: (r.alarms ?? []).map(alarmEv),
  };
}

async function inspection(q: URLSearchParams) {
  const lot = q.get('lot') ?? '';
  const [rows, l] = await Promise.all([get('inspection/results?' + qs({ lot_no: lot })), get(`lots/${encodeURIComponent(lot)}`).catch(() => null)]);
  return { lot_no: lot, results: rows, plan: l ? { plan_mode: l.plan_mode ?? l.lot?.plan_mode ?? null, enhance_reason: l.enhance_reason ?? l.lot?.enhance_reason ?? null } : null };
}

async function cmmImports() {
  const rows: J[] = (await get('inspection/cmm-imports?limit=5000')).map((r: J) => ({ ...r, status: r.status === 'NEEDS_CHECK' ? 'CHECK' : r.status }));
  const from = await liveFrom();
  const live = rows.filter((r) => r.received_at >= from), past = rows.filter((r) => r.received_at < from);     // 둘 다 새 것부터
  // 시연 서버와 같게: 오늘 것 전부 + 그 앞 60개, 새 것부터 80개까지
  return { imports: [...live, ...past.slice(0, 60)].slice(0, 80), errors_30d: past.filter((r) => r.status !== 'SUCCESS').reverse(), counts: { past: past.length, today: live.length } };
}

/** 공정 능력·관리도 (QLT-04·05): 관리 한계 = 평균 ± 3σ, 표본 50개가 안 되면 한계 없음(시연 서버와 같음). out = 한계 밖 점 번호 */
async function qualitySummary() {
  const r = await get('quality/summary?' + qs({ from: '2026-01-01T00:00:00+09:00', points: 50 }));
  const M = MASTERS as unknown as J;
  const got = new Map<string, J>((r.items ?? []).map((it: J) => [String(it.item_seq), it]));
  return {
    defects: (r.defects ?? []).map((d: J) => ({ defect_code: d.defect_code, qty: Number(d.qty ?? 0) })),
    defect_codes: M.defect_codes ?? [],            // 불량 코드 기준 정보 전부 (시연 서버와 같음)
    // 검사 항목 기준 정보 전부(게이지·외관처럼 측정값이 없는 항목은 n = 0) + 백엔드가 계산한 값
    items: (M.inspection_items ?? []).map((mi: J) => ({ ...mi, ...(got.get(String(mi.item_seq)) ?? {}) })).map((it: J) => {
      const c: J = it.cpk ?? {};
      const values = (it.chart ?? []).map((p: J) => ({ at: p.measured_at, v: Number(p.x) }));
      const ok = Number(c.n ?? 0) >= 50 && c.mean != null && c.sigma != null;
      const ucl = ok ? Number(c.mean) + 3 * Number(c.sigma) : null, lcl = ok ? Number(c.mean) - 3 * Number(c.sigma) : null;
      return { ...Object.fromEntries(Object.entries(it).filter(([k]) => k !== 'cpk' && k !== 'chart')), item_seq: String(it.item_seq), item_name: it.item_name, n: Number(c.n ?? 0), cpk: num(c.cpk), cpk_min: num(c.cpk_min), mean: num(c.mean), ucl, lcl,
        lsl: num(it.lsl), usl: num(it.usl), values, out: ok ? values.flatMap((p: J, i: number) => (p.v > ucl! || p.v < lcl! ? [i] : [])) : [] };
    }),
    live_from: await liveFrom(),
  };
}

// ---------------- 재고·출하·공구·설정 (API-INV, TOOL, SET) ----------------
const txnRow = (t: J) => ({ ...t, qty_change: Number(t.qty_change ?? 0) });   // 거래 이름은 DB 그대로 (SHIP_OUT 등 — 화면이 둘 다 읽음)

async function inventory() {
  const r = await get('inventory/screen');
  const order = new Map<string, number>(((MASTERS as unknown as J).items ?? []).map((m: J, k: number) => [m.item_no, k]));   // 기준 정보 순서
  const items = [...(r.items ?? [])].sort((a: J, b: J) => (order.get(a.item_no) ?? 99) - (order.get(b.item_no) ?? 99)).map((i: J) => {
    const saf = Number(i.safety_stock ?? 0), stock = Number(i.on_hand_qty ?? i.stock_qty ?? 0);
    return { item_no: i.item_no, category: i.category, item_name: i.item_name, unit: i.unit, owner_role: i.owner_role, safety_stock: saf, stock_qty: stock,
      low: i.is_low ?? (saf > 0 && stock <= saf), low_at_start: saf > 0 && Number(i.stock_at_start ?? 0) <= saf };
  });
  const fg = (r.items ?? []).find((i: J) => i.category === 'FINISHED');
  return { items, held_lot_qty: Number(fg?.held_qty ?? 0), live_txns: (r.live_txns ?? []).map(txnRow), past_txns: (r.past_txns ?? []).map((t: J) => csvRow(txnRow(t))) };
}

/** 입고·실사 조정 (API-INV-02). 사용(USE)은 백엔드가 작업기록서·예방 정비 확정 때 스스로 빼므로 여기서는 보내지 않는다 (두 번 빠지지 않게) */
async function inventoryTxn(b: J) {
  if (b.txn_type === 'USE') return { ok: true, skipped: 'USE는 확정 때 백엔드가 뺀다' };
  return post('inventory/txns', { item_no: b.item_no, kind: b.txn_type === 'ADJUST' ? 'ADJUST' : 'RECEIPT', qty: Number(b.qty), reason: b.memo || null });
}

async function shipments() {
  const rows: J[] = await get('shipments?lines=true&limit=500');
  return { shipments: rows.sort((a, b) => (a.shipped_at < b.shipped_at ? -1 : 1)).map((s) => ({ ...s, lines: (s.lines ?? []).map((x: J) => ({ ...x, qty: Number(x.qty) })) })) };
}

/** 출하 등록·확정 (API-INV-04, SUP) — 백엔드는 납기가 꼭 있어야 해서 비우면 오늘 */
async function shipmentCreate(b: J) {
  const due = b.due_date || String(lastTwin?.clock?.sim_at ?? new Date().toISOString()).slice(0, 10);
  const r = await post('shipments', { customer_code: b.customer_code ?? 'CUST-01', due_date: due, memo: b.memo || null, fifo_skip_reason: b.fifo_skip_reason || null,
    lines: (b.lines ?? []).map((x: J) => ({ lot_no: x.lot_no, qty: Number(x.qty) })), confirm: true });
  return { ...r, lines: b.lines ?? [] };
}

async function tools() {
  const [list, ch] = await Promise.all([get('tools'), get('tools/changes')]);
  return { tools: list.sort((a: J, b: J) => (a.tool_id < b.tool_id ? -1 : 1)).map(toolRow), changes_today: ch.changes_today ?? [], past_changes: (ch.past_changes ?? []).map(csvRow) };
}

// 알림 규칙 값(반복 기준 등)은 백엔드에 숫자 칸이 아직 없다 [선택 필요] — 이 브라우저 메모리에만 (시연 서버도 서버 메모리였다)
let ruleValues: J = { repeat_days: 7, repeat_count: 3, burst: '1분 안 3번 이상', flood: '10분 10건 / 5건', target_risk_pct: 90, repeat2_days: 7 };
const settingsLog: J[] = [];
async function settings() {
  return { targets: { shift: Number(lastTwin?.production?.target_qty ?? 90), daily: 180 }, safety: {}, rules: ruleValues, log: settingsLog };
}
async function settingsSave(b: J) {
  if (b.shift_target != null) await call('PATCH', 'settings/targets', { shift_target_qty: Number(b.shift_target) });   // 아직 시작 안 한 교대부터 (백엔드 규칙)
  for (const [item, v] of Object.entries(b.safety ?? {})) await call('PATCH', `inventory/items/${encodeURIComponent(item)}/safety-stock`, { safety_stock: Number(v) });
  if (b.rules) ruleValues = { ...ruleValues, ...b.rules };
  settingsLog.push({ at: lastTwin?.clock?.sim_at ?? new Date().toISOString(), by: session?.userId, what: Object.fromEntries(Object.entries(b).filter(([k]) => k !== 'role' && k !== 'user_id')) });
  return { ok: true };
}

// ---------------- 길 찾기 ----------------
type Handler = (q: URLSearchParams, body: J, parts: string[]) => Promise<unknown>;
const GET: [RegExp, Handler][] = [
  [/^line\/twin$/, () => twin()],
  [/^stream\/events$/, (q) => events(Number(q.get('after') ?? 0))],
  [/^replay$/, (q) => replay(q)],
  [/^sim\/clock$/, () => get('sim/clock')],
  [/^health$/, () => get('sim/clock').then((c) => ({ ok: true, run_id: c.run_id, clock: c }))],
  // 보고서·문서
  [/^reports\/shift$/, async () => ({ reports: (await get('reports/shift')).map((r: J) => ({ ...r, partial: !!r.in_progress })) })],
  [/^reports\/shift\/([^/]+)$/, (_q, _b, p) => shiftReport(decodeURIComponent(p[1]))],
  [/^reports\/daily$/, async () => ({ reports: await forbiddenAsEmpty(get('reports/daily'), [] as J[]) })],
  [/^reports\/daily\/([^/]+)$/, (_q, _b, p) => dailyReport(p[1])],
  // 작업지시서·작업기록서·간이 기록 한 건의 수정 이력 (SCR-17, 2026-10-24 — 백엔드 모드에서 화면 안 revisions 대신 DB 버전)
  [/^documents\/doc\/(WORK_ORDER|WORK_RECORD)\/([^/]+)$/, (_q, _b, p) => docRevisions(p[1], decodeURIComponent(p[2]))],
  [/^documents\/revisions$/, async () => {
    const r = await forbiddenAsEmpty(get('documents/revisions?limit=200'), { revisions: [], changes: {} } as J);
    return { revisions: (r.revisions ?? []).map((x: J) => ({ ...x, revision_id: String(x.revision_id) })),
      changes: Object.fromEntries(Object.entries(r.changes ?? {}).map(([k, v]) => [k, (v as J[]).map(csvRow).map(fieldKo).sort(byField)])) };
  }],
  // 알림·정비·사내 문서
  [/^notifications\/past-open$/, () => pastOpen()],
  [/^notifications\/rules$/, async () => ({ rules: [] })],
  [/^maint\/history$/, () => maintHistory()],
  [/^maint\/pm-schedule$/, () => pmSchedule()],
  [/^internal-docs$/, () => internalDocs()],
  [/^internal-docs\/([^/]+)$/, (_q, _b, p) => internalDoc(decodeURIComponent(p[1]))],
  [/^users$/, async () => ({ users: [] })],
  // 로트·품질
  [/^lots$/, (q) => lots(q)],
  [/^inspection\/results$/, (q) => inspection(q)],
  [/^inspection\/cmm-imports$/, () => cmmImports()],
  [/^quality\/summary$/, () => qualitySummary()],
  // 재고·출하·공구·설정
  [/^inventory$/, () => inventory()],
  [/^shipments$/, () => shipments()],
  [/^tools$/, () => tools()],
  [/^settings$/, () => settings()],
];
const POST: [RegExp, Handler][] = [
  // 시연 조작 (API-SIM-01~03) — 백엔드가 시뮬레이터에 넘긴다
  [/^sim\/clock$/, (_q, b) => post('sim/clock', b)],
  [/^sim\/inject$/, (_q, b) => post('sim/inject', { scenario_code: b.scenario_code })],
  [/^sim\/reset$/, () => post('sim/reset').then((r) => { resetDerived(); return r; })],
  [/^sim\/fire$/, (_q, b) => post('sim/fire', { kind: b.kind })],
  // 시뮬레이터가 주인인 기록 — 백엔드가 권한 확인 뒤 시뮬레이터에 넘기고, DB에는 중계로 들어온다
  [/^maint\/work-records\/confirm$/, (_q, b) => post('sim/work-record-confirmed', { equipment_id: b.equipment_id })],
  [/^maint\/pm-start$/, (_q, b) => post('sim/pm-start', { equipment_id: b.equipment_id, minutes: b.minutes, pm_task_ids: b.pm_task_ids ?? [] })],
  [/^maint\/pm-end$/, (_q, b) => post('sim/pm-end', { equipment_id: b.equipment_id, pm_task_ids: b.pm_task_ids ?? [], done_by: b.done_by, result: b.result, memo: b.memo, items: b.items ?? [] })],
  [/^lots\/([^/]+)\/hold$/, (_q, b, p) => post(`lots/${p[1]}/hold`, { reason: b.reason || '반장 보류' })],
  [/^lots\/([^/]+)\/release$/, (_q, b, p) => post(`lots/${p[1]}/release`, { approver: b.approver ?? null })],
  [/^tools\/([^/]+)\/change$/, (_q, _b, p) => post(`tools/${p[1]}/change`, { reason: toolReason(p[1]) })],
  // DB가 주인인 기록 — 백엔드가 쓴다
  [/^reports\/shift\/([^/]+)\/(save|confirm|revise)$/, (_q, b, p) => shiftReportAction(decodeURIComponent(p[1]), p[2], b)],
  [/^reports\/daily\/([^/]+)\/confirm$/, (_q, b, p) => dailyConfirm(p[1], b)],
  [/^inventory\/txns$/, (_q, b) => inventoryTxn(b)],
  [/^shipments$/, (_q, b) => shipmentCreate(b)],
  [/^settings$/, (_q, b) => settingsSave(b)],
  // 비서가 다듬은 문장 (2026-10-24): 백엔드가 시연 서버의 llm_compose에 묻는다 (기다리지 않음). 없거나 실패면 준비 안 됨 → 화면은 기본 문장
  [/^assist\/([a-z-]+)$/, (_q, b, p) => post(`assist/${p[1]}`, b).catch(() => ({ ready: false }))],
];

/** 공구 교체 사유 (백엔드 필수 칸): 사용률 90% 이상 → LIFE_90, 그 설비에 362·174 알람이 열려 있으면 그 알람, 나머지 OTHER */
function toolReason(toolId: string): string {
  const t = lastTwin;
  const eq = toolId.slice(0, 6);
  const open = (t?.alarms as J[] | undefined)?.filter((a) => a.equipment_id === eq && !a.cleared_at).map((a) => a.alarm_code) ?? [];
  if (open.includes('362')) return 'ALARM_362';
  if (open.includes('174')) return 'ALARM_174';
  const tl = (t?._tools as J[] | undefined)?.find((x) => x.tool_id === toolId);
  return tl && Number(tl.usage_rate_pct ?? 0) >= 90 ? 'LIFE_90' : 'OTHER';
}

/** live.ts api()가 부른다: 시연 서버 주소 이름 → 백엔드 */
export async function backendRoute(path: string, body?: unknown): Promise<any> {
  const [p, query = ''] = path.split('?');
  const q = new URLSearchParams(query);
  const table = body === undefined ? GET : POST;
  for (const [re, h] of table) {
    const m = p.match(re);
    if (m) return h(q, (body ?? {}) as J, m as unknown as string[]);
  }
  throw new BackendErr('NOT_SUPPORTED', `백엔드 연결에 아직 없는 화면 기능이에요 (${body === undefined ? 'GET' : 'POST'} ${p})`, 404);
}

// backendDocs.ts(작업지시서·작업기록서·간이 기록·알림)가 같은 로그인으로 부르는 문
export const backendCall = (method: string, path: string, body?: unknown) => call(method, path, body);
export const backendLiveFrom = () => liveFrom();
export const backendUserId = () => session?.userId ?? null;

export const _test = { twin, events, replay, orders, toolReason, resetDerived, setSession: (s: typeof session) => { session = s; } };
