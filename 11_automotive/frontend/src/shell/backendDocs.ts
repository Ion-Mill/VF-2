'use client';
// 화면 → 백엔드 전환 C2 다음 단계 (2026-10-24 — 팀과 논의/C2_다음단계_계획_20261023.md 1~3묶음).
// 백엔드 모드(NEXT_PUBLIC_MOM_BACKEND=1)에서 작업지시서·작업기록서·간이 기록·알림을 이 브라우저(localStorage) 대신 백엔드에서 읽고 쓴다.
// - 읽기: 목록을 주기적으로 받아 화면이 쓰던 모양(WorkOrder·WorkRecord·SimpleRecord·Notice)으로 바꾼다 — 화면 부품은 그대로.
// - 쓰기: 화면이 putWo·putWr·putSr로 새 값을 넘기면, 지금 값과 비교해 바뀐 것만 백엔드 호출로 바꾼다 (고친 칸 저장 → 담당 → 승인 → 시작 순).
// - 화면이 스스로 만들던 것(작업지시서 초안·규칙 알림)은 App이 백엔드 모드에서 끈다 — DB가 만든다 (계획서 규칙 1·2).
// - 재고 사용(USE)은 백엔드가 작업기록서·간이 기록 확정 때 뺀다 (backendApi.ts inventoryTxn이 USE를 보내지 않음 — 규칙 3).
// - 번호는 DB 번호 그대로 (규칙 5). 아직 저장 안 한 간이 기록만 화면 안 임시 번호(NEW:)를 쓰고, 처음 저장할 때 DB 번호로 바뀐다.
import type { MachineId } from '@/components/types';
import { ID_OF } from './data';
import type { Eq } from './live';
import type { Level, Notice } from './model';
import { USERS, userName } from './model';
import type { SimpleRecord, WoState, WorkOrder, WorkRecord, WrState } from './workflow';
import { backendCall, backendLiveFrom, backendUserId } from './backendApi';

type J = Record<string, any>;
const get = (p: string) => backendCall('GET', p);
const post = (p: string, b: unknown = {}) => backendCall('POST', p, b);
const patch = (p: string, b: unknown) => backendCall('PATCH', p, b);

const WO_STATE: Record<string, WoState> = { AI_DRAFT: 'draft', EDITING: 'editing', APPROVED: 'approved', IN_PROGRESS: 'inprogress', DONE: 'done', CANCELLED: 'cancelled' };
const WR_STATE: Record<string, WrState> = { AI_DRAFT: 'draft', EDITING: 'editing', CONFIRMED: 'confirmed', CHECKED: 'checked' };
const LOTO = ['6.1', '6.2', '6.3', '6.4', '6.5', '6.6', '7.1', '7.2', '7.3'];          // Safety.tsx LOCK 9칸과 같은 순서 (DOC-05 §6·7)
const hm = (iso?: string | null) => (iso ? iso.slice(11, 16) : '');
const machineOf = (eq: string): MachineId => ID_OF[eq as Eq];

export interface Docs { wos: WorkOrder[]; wrs: WorkRecord[]; srs: SimpleRecord[]; notices: Notice[]; handled: Record<string, { by: string; ts: number }> }
let raw: { wos: J[]; wrs: J[]; notices: J[] } = { wos: [], wrs: [], notices: [] };   // 쓰기 때 버전·체크 번호를 찾는 데 쓴다

// ---------------- 읽기 ----------------
export async function loadDocs(): Promise<Docs> {
  const since = await backendLiveFrom();
  rawLiveFrom = since;
  const [wos, wrs, nt] = await Promise.all([
    get('maint/work-orders?' + new URLSearchParams({ detail: 'true', since })).catch(() => []),
    get('maint/work-records?' + new URLSearchParams({ detail: 'true', since })).catch(() => []),
    get('notifications?status=all&limit=500').catch(() => ({ items: [] })),
  ]);
  raw = { wos, wrs, notices: nt.items ?? [] };
  const recOfWo = new Map<string, string>((wrs as J[]).filter((r) => r.wo_no).map((r) => [r.wo_no, r.record_no]));
  const handled: Docs['handled'] = {};
  for (const r of wrs as J[]) {
    if (r.alarm_event_id && (r.status === 'CONFIRMED' || r.status === 'CHECKED')) handled[`a-${r.alarm_event_id}`] = { by: userName(r.confirmed_by), ts: Date.parse(r.confirmed_at ?? '') || 0 };
  }
  for (const w of wos as J[]) {          // 정식 기록은 작업지시서의 알람으로 처리 (작업기록서에는 알람 번호가 없을 수 있음)
    const r = (wrs as J[]).find((x) => x.wo_no === w.wo_no);
    if (w.alarm_event_id && r && (r.status === 'CONFIRMED' || r.status === 'CHECKED')) handled[`a-${w.alarm_event_id}`] = { by: userName(r.confirmed_by), ts: Date.parse(r.confirmed_at ?? '') || 0 };
  }
  return {
    wos: (wos as J[]).map((w) => woOf(w, recOfWo.get(w.wo_no))),
    wrs: (wrs as J[]).filter((r) => r.record_type === 'FULL').map(wrOf),
    srs: (wrs as J[]).filter((r) => r.record_type === 'SIMPLE').map(srOf),
    notices: (nt.items ?? []).filter((n: J) => !String(n.rule_code).startsWith('ALARM_')).map(noticeOf),   // 알람은 화면이 알람 기록(트윈)으로 따로 보인다
    handled,
  };
}

const woOf = (w: J, recordNo?: string): WorkOrder => ({
  no: w.wo_no, alertId: w.alarm_event_id ? `a-${w.alarm_event_id}` : '', machine: machineOf(w.equipment_id), code: w.alarm_code ?? '',
  created: w.created_at, state: WO_STATE[w.status] ?? 'draft', version: Number(w.current_version ?? 0),
  trigger: String(w.trigger_kind ?? '').includes('REPEAT') ? 'REPEAT_2' : 'STOP_ALARM', lot: w.lot_no ?? null,
  title: w.title ?? '', symptom: w.symptom ?? '', steps: w.steps ?? [], parts: w.parts ?? [], assignee: w.assignee_user_id ?? null,
  edited: [], approvedBy: w.approved_by ? userName(w.approved_by) : undefined, approvedAt: w.approved_at ?? undefined, recordNo,
  revisions: [],                       // 수정 이력은 문서 이력 화면이 백엔드에서 읽는다 (documents/revisions)
});

const checksOf = (r: J) => {
  const c: J[] = r.checks ?? [];
  const lock = LOTO.map((code) => !!c.find((x) => x.check_kind === 'LOTO' && x.loto_step_code === code)?.is_checked);
  const steps = c.filter((x) => x.check_kind === 'STEP').sort((a, b) => a.step_no - b.step_no).map((x) => !!x.is_checked);
  return { lock, steps };
};
const partsOf = (r: J) => (r.parts ?? []).map((p: J) => ({ item: p.item_no, qty: Number(p.qty) }));

const wrOf = (r: J): WorkRecord => {
  const { lock, steps } = checksOf(r);
  return {
    no: r.record_no, woNo: r.wo_no, state: WR_STATE[r.status] ?? 'draft', memo: r.worker_memo ?? '', cause: r.cause ?? '', action: r.action ?? '',
    parts: partsOf(r), stepChecks: steps, lock, start: hm(r.start_at), end: hm(r.end_at), revisions: [], confirmedAt: r.confirmed_at ?? undefined,
  };
};

const srOf = (r: J): SimpleRecord => ({
  no: r.record_no, alertId: r.alarm_event_id ? `a-${r.alarm_event_id}` : '', machine: machineOf(r.equipment_id), kind: r.cause_check_notification_id ? 'cause' : 'alarm',
  state: r.status === 'CONFIRMED' || r.status === 'CHECKED' ? 'confirmed' : 'open', action: r.action ?? '', parts: partsOf(r), lock: checksOf(r).lock,
  memo: r.worker_memo ?? '', by: r.confirmed_by ? userName(r.confirmed_by) : undefined, revisions: [], code: r.alarm_code ?? '',
});

const LEVEL: Record<string, Level> = { URGENT: '긴급', CAUTION: '주의', INFO: '참고' };
const RANK: Record<string, string> = { R0: '0', R0_1: '0-1', R1: '1', R2: '2', R3: '3', R4: '4' };
const noticeOf = (n: J): Notice => {
  const rule = String(n.rule_code);
  const me = USERS.find((u) => u.id === backendUserId());
  const wr = n.doc_type === 'WORK_RECORD' ? raw.wrs.find((r) => r.record_no === n.doc_key) : null;
  const open = n.wo_no ? { screen: 'wo', key: n.wo_no }
    : wr ? (wr.record_type === 'FULL' ? { screen: 'wr', key: wr.wo_no } : { screen: 'sr', key: wr.record_no })
    : rule === 'SHIFT_REPORT_PENDING' ? { screen: 'shift', key: n.shift_id ?? n.doc_key }
    : rule === 'DAILY_REPORT_PENDING' ? { screen: 'daily', key: n.doc_key ?? undefined }
    : rule.startsWith('PM_') ? { screen: 'pm' }
    : rule === 'STOCK_LOW' ? { screen: 'inventory', key: n.item_no ?? undefined }
    : rule === 'TOOL_LIFE_90' ? { screen: 'tools' }
    : rule.startsWith('CMM_') || rule === 'SPC_OUT' ? { screen: 'quality' }
    : rule === 'LOT_DUE_RISK' ? { screen: 'lots' }
    : n.doc_type === 'SHIFT_REPORT' ? { screen: 'shift', key: n.doc_key }
    : n.doc_type === 'DAILY_REPORT' ? { screen: 'daily', key: n.doc_key }
    : n.doc_type === 'PM_RECORD' ? { screen: 'pm' }
    : n.doc_type === 'SHIPMENT' ? { screen: 'inventory' }
    : undefined;
  return {
    id: `n:${n.notification_id}`, rule, ruleName: n.rule_name ?? rule, level: LEVEL[n.importance] ?? '주의', rank: RANK[n.report_rank ?? n.rule_rank] ?? '3',
    at: n.raised_at, ts: Date.parse(n.raised_at), text: String(n.message ?? '').replace(/^\[[^\]]+\]\s*/, ''), related: n.related_info ?? undefined,
    machine: n.equipment_id ? machineOf(n.equipment_id) : undefined, roles: me ? [me.role] : ['SUP', 'MGR'],   // 백엔드가 이미 이 사용자 몫만 준다
    delivery: n.delivery_kind === 'BUBBLE' ? 'BUBBLE' : 'LIST', handled: !!n.is_processed, handledBy: n.processed_by ? userName(n.processed_by) : undefined,
    handledAt: n.processed_at ?? undefined, plan: n.process_memo ?? undefined, past: n.raised_at < (rawLiveFrom ?? ''), open,
    count: Number(n.repeat_count) > 1 ? Number(n.repeat_count) : undefined, keys: n.pm_task_ids ?? undefined,
  };
};
let rawLiveFrom: string | null = null;      // 실시간 구간 시작 — 그 앞 알림은 "9월에 넘어온 것"(past)

// ---------------- 쓰기 ----------------
const woRaw = (no: string) => raw.wos.find((w) => w.wo_no === no);
const wrRaw = (no: string) => raw.wrs.find((r) => r.record_no === no);
const lastReason = (revs: { reason?: string }[]) => revs[revs.length - 1]?.reason;

/** 작업지시서 저장 (SCR-11): 고친 칸(제목·증상·작업 순서) → 담당 지정 → 승인 → 작업 시작. 완료는 작업기록서 확정 때 DB가 한다 */
export async function saveWo(prev: WorkOrder, next: WorkOrder): Promise<void> {
  const r = woRaw(prev.no);
  let version = Number(r?.current_version ?? prev.version);
  const changes: J = {};
  if (next.title !== prev.title) changes.title = next.title;
  if (next.symptom !== prev.symptom) changes.symptom = next.symptom;
  if (JSON.stringify(next.steps) !== JSON.stringify(prev.steps)) changes.steps = next.steps;
  if (Object.keys(changes).length) {
    const out = await patch(`maint/work-orders/${prev.no}`, { version, changes, reason: lastReason(next.revisions) ?? null });
    version = Number(out.version_no ?? version + 1);
  }
  if (next.assignee !== prev.assignee && next.assignee) await post(`maint/work-orders/${prev.no}/assign`, { mnt_user_id: next.assignee });
  if (next.state === 'approved' && (prev.state === 'draft' || prev.state === 'editing')) await post(`maint/work-orders/${prev.no}/approve`, { version });
  if (next.state === 'inprogress' && prev.state === 'approved') await post(`maint/work-orders/${prev.no}/start`);
}

/** 작업지시서를 열 때 (담당 보전 담당자가 열면 백엔드가 "작업지시서 배정" 알림을 처리한다 — 1건 조회의 몫) */
export const openWoSeen = (no: string) => get(`maint/work-orders/${no}`).catch(() => undefined);

/** 정식 작업기록서 만들기 ([작업 시작] 뒤 — 잠금·표지 9칸·작업 순서 체크칸이 같이 생긴다) */
export const createRecord = (woNo: string) => post('maint/work-records', { wo_no: woNo });

const checkDiff = (r: J | undefined, prevLock: boolean[], nextLock: boolean[], prevSteps?: boolean[], nextSteps?: boolean[]) => {
  const c: J[] = r?.checks ?? [];
  const out: { check_seq: number; is_checked: boolean }[] = [];
  LOTO.forEach((code, i) => {
    if (!!prevLock[i] === !!nextLock[i]) return;
    const row = c.find((x) => x.check_kind === 'LOTO' && x.loto_step_code === code);
    if (row) out.push({ check_seq: row.check_seq, is_checked: !!nextLock[i] });
  });
  const steps = c.filter((x) => x.check_kind === 'STEP').sort((a, b) => a.step_no - b.step_no);
  (nextSteps ?? []).forEach((v, i) => { if (!!v !== !!(prevSteps ?? [])[i] && steps[i]) out.push({ check_seq: steps[i].check_seq, is_checked: !!v }); });
  return out;
};
const partDiff = (prev: { item: string; qty: number }[], next: { item: string; qty: number }[]) =>
  next.filter((p) => prev.find((x) => x.item === p.item)?.qty !== p.qty && p.qty > 0).map((p) => ({ item_no: p.item, qty: p.qty }));

/** 끝 시각 "HH:MM" → 그 기록 시작 날짜의 시각 (자정을 넘기면 다음 날).
 *  시작은 초까지 있고 화면 끝 칸은 분까지라, 같은 분에 끝내면 끝 < 시작이 된다 → 시작 시각으로 맞춘다 (DB ck_work_record_time, 2026-10-24) */
const endAt = (r: J | undefined, hhmm: string) => {
  if (!hhmm || !r?.start_at) return undefined;
  const d = new Date(`${String(r.start_at).slice(0, 10)}T${hhmm}:00+09:00`);
  if (hhmm < String(r.start_at).slice(11, 16)) d.setDate(d.getDate() + 1);
  const start = new Date(new Date(String(r.start_at)).getTime() + 1);     // +1ms: DB 시작 시각은 마이크로초까지라 밀리초로 자르면 끝 < 시작
  return (d < start ? start : d).toISOString();
};

/** 작업기록서 저장·확정·확인 (SCR-12): 칸·체크·부품을 한 번에 저장(PATCH) → 확정(재고 차감·작업지시서 완료·알람 처리는 DB) → 반장 확인 */
export async function saveWr(prev: WorkRecord, next: WorkRecord): Promise<void> {
  const r = wrRaw(prev.no);
  let version = Number(r?.current_version ?? 0);
  const changes: J = {};
  if (next.cause !== prev.cause) changes.cause = next.cause;
  if (next.action !== prev.action) changes.action = next.action;
  if (next.memo !== prev.memo) changes.worker_memo = next.memo;
  if (next.end && next.end !== prev.end) changes.end_at = endAt(r, next.end);
  const checks = checkDiff(r, prev.lock, next.lock, prev.stepChecks, next.stepChecks);
  const parts = partDiff(prev.parts, next.parts);
  if (Object.keys(changes).length || checks.length || parts.length) {
    const locked = prev.state === 'confirmed' || prev.state === 'checked';
    const out = await patch(`maint/work-records/${prev.no}`, { version, changes, checks, parts, reason: locked ? lastReason(next.revisions) ?? null : null });
    version = Number(out.current_version ?? version);
  }
  if (next.state === 'confirmed' && (prev.state === 'draft' || prev.state === 'editing')) await post(`maint/work-records/${prev.no}/confirm`, { version });
  if (next.state === 'checked' && prev.state === 'confirmed') await post(`maint/work-records/${prev.no}/check`);
}

/** 간이 기록 저장·확정 (SCR-13). 아직 DB에 없는 것(번호 NEW:)은 처음 저장 때 만든다 — 만든 DB 번호를 돌려준다 */
export async function saveSr(prev: SimpleRecord, next: SimpleRecord, causeNoticeId?: number): Promise<string> {
  let no = prev.no;
  if (no.startsWith('NEW:')) {
    const eq = Object.entries(ID_OF).find(([, m]) => m === prev.machine)?.[0];
    const made = await post('maint/quick-records', {
      equipment_id: eq, action: next.action || '조치 기록', alarm_event_id: prev.alertId ? Number(prev.alertId.slice(2)) : null,
      cause_check_notification_id: prev.kind === 'cause' ? causeNoticeId ?? null : null, worker_memo: next.memo || null,
    });
    no = made.record_no;
    raw.wrs = [...raw.wrs, ...(await get('maint/work-records?' + new URLSearchParams({ detail: 'true', record_type: 'SIMPLE' })).catch(() => [])).filter((x: J) => x.record_no === no)];
    prev = { ...prev, no, action: next.action || '조치 기록', memo: next.memo, lock: prev.lock.map(() => false), parts: [] };
  }
  const r = wrRaw(no);
  let version = Number(r?.current_version ?? 0);
  const changes: J = {};
  if (next.action !== prev.action && next.action) changes.action = next.action;
  if (next.memo !== prev.memo) changes.worker_memo = next.memo;
  const checks = checkDiff(r, prev.lock, next.lock);
  const parts = partDiff(prev.parts, next.parts);
  if (Object.keys(changes).length || checks.length || parts.length) {
    const out = await patch(`maint/work-records/${no}`, { version, changes, checks, parts });
    version = Number(out.current_version ?? version);
  }
  if (next.state === 'confirmed' && prev.state !== 'confirmed') await post(`maint/quick-records/${no}/confirm`, { version });
  return no;
}

/** 알림 처리 (NTF-03). 반복 알람은 조치 계획이 필요하다. 자동으로만 처리되는 알림이면 백엔드가 거절한다 */
export async function resolveNotice(id: string, plan?: string): Promise<void> {
  if (!id.startsWith('n:')) return;
  const n = raw.notices.find((x) => String(x.notification_id) === id.slice(2));
  if (n?.is_processed) return;
  if (n?.rule_code === 'CAUSE_CHECK_REQUEST') return;   // 간이 기록(원인 점검)을 확정하면 DB가 처리한다 — 화면이 확정 직후 부르는 것은 건너뜀
  // 자동 처리 규칙(처리 기록이 생기거나 조건이 풀리면 DB가 처리)은 손으로 처리하지 않는다 — 백엔드가 거절한다
  if (n?.process_mode === 'AUTO') throw new Error('이 알림은 해당 기록을 확정하거나 조건이 풀리면 자동으로 처리돼요');
  await post(`notifications/${id.slice(2)}/resolve`, { action_plan: plan ?? null, memo: plan ?? null });
}

/** 원인 점검 요청 알림 번호 (간이 기록 "원인 점검"을 만들 때 잇는다) */
export const causeNoticeId = (machine: MachineId): number | undefined => {
  const eq = Object.entries(ID_OF).find(([, m]) => m === machine)?.[0];
  const n = raw.notices.filter((x) => x.rule_code === 'CAUSE_CHECK_REQUEST' && x.equipment_id === eq && !x.is_processed).pop();
  return n ? Number(n.notification_id) : undefined;
};
