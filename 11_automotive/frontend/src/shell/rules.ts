// 알림 규칙 (notification_rule.csv 25종, DOC-07 10장) — 알릴지·중요도·보고 순위·받는 역할은 프로그램 규칙이 정한다 (FR-AST-02-14).
// 알람 발생(ALARM_STOP·WARN·GUIDE)은 알람 기록(AlertRec)으로, 나머지는 여기서 Notice로 만든다.
// 같은 조건이면 id가 같아서 한 번만 생긴다. 조건이 풀리면(공구 교체·재고 보충·정비 끝·보고서 확정) 자동 처리된다.
import { CAUSE_KO, ID_OF, MACHINES, WIP_NAME, type Role } from './data';
import type { Eq, SimEvent, Twin } from './live';
import { SIM, md, simIso, tsOf } from './live';
import type { AlertRec, Level, Notice } from './model';
import { USERS } from './model';
import type { Downtime, SimpleRecord, WorkOrder, WorkRecord } from './workflow';
import { isUnrecordedStop, stopKeyOf } from './workflow';

export const RULE_NAME: Record<string, string> = {
  REPEAT_ALARM: '반복 알람 (1단계)', REPEAT_ALARM_2: '반복 알람 2단계', CAUSE_CHECK_REQUEST: '원인 점검 요청', TARGET_RISK: '목표 미달 위험',
  BOTTLENECK_MOVE: '병목 발생·이동', WIP_WARN: '재공 경고', LOT_DUE_RISK: '로트 납기 지연 위험', STOCK_LOW: '재고 부족', PM_DUE_SOON: '예방 정비 기한 하루 전',
  PM_OVERDUE: '예방 정비 기한 넘김', TOOL_LIFE_90: '공구 수명', APPROVAL_WAIT_30M: '승인 대기', APPROVAL_WAIT_2H: '승인 대기 2시간', WO_ASSIGNED: '작업지시서 배정',
  WO_DRAFT_READY: '작업지시서 초안 검토', WO_APPROVAL_REQUEST: '작업지시서 승인 요청', WR_CONFIRM_PENDING: '작업기록서 확정 전', WR_CHECK_REQUEST: '작업기록서 확인 요청',
  PM_RECORD_CHECK: '예방 정비 실시 기록 확인', DAILY_REPORT_PENDING: '일일 보고서 확정 요청', DOC_REVISED: '문서 수정', SPC_OUT: '관리도 이상',
  SHIFT_REPORT_PENDING: '교대 보고서 확정 요청', CMM_FILE_ERROR: 'CMM 결과 파일 오류', CMM_JUDGE_MISMATCH: 'CMM 판정 불일치', CMM_NO_RESULT: 'CMM 결과 미수신',
  ALARM_STOP: '알람 발생 (정지)', ALARM_WARN: '알람 발생 (주의)', ALARM_GUIDE: '알람 발생 (조작 안내)',
  UNRECORDED_STOP: '기록 없는 정지', AFTER_RECORD_CHECK_WAIT: '사후 기록 확인 대기', // 사후 작업기록 (FR-AST-02-20·21, 2026-10-24)
};
// 보고 순위 (gen/reports.py RANK와 같음): 2 생산 위험 / 3 주의 / 4 참고
const RANK_OF: Record<string, string> = {
  TARGET_RISK: '2', BOTTLENECK_MOVE: '2', WIP_WARN: '2', LOT_DUE_RISK: '2', REPEAT_ALARM_2: '3', CAUSE_CHECK_REQUEST: '3', REPEAT_ALARM: '3',
  SPC_OUT: '3', TOOL_LIFE_90: '3', PM_OVERDUE: '3', STOCK_LOW: '3', APPROVAL_WAIT_2H: '3', CMM_FILE_ERROR: '3', CMM_JUDGE_MISMATCH: '3', CMM_NO_RESULT: '3',
  ALARM_GUIDE: '4', PM_DUE_SOON: '4', APPROVAL_WAIT_30M: '4', WO_ASSIGNED: '4', WO_DRAFT_READY: '4', WO_APPROVAL_REQUEST: '4', WR_CONFIRM_PENDING: '4', WR_CHECK_REQUEST: '4', PM_RECORD_CHECK: '4', DAILY_REPORT_PENDING: '4', SHIFT_REPORT_PENDING: '4', DOC_REVISED: '4', UNRECORDED_STOP: '4', AFTER_RECORD_CHECK_WAIT: '4',
};
const LEVEL_OF: Record<string, Level> = { URGENT: '긴급', CAUTION: '주의', INFO: '참고' };
// 예방 정비 기한 알림은 주 1회 이상 주기 항목만 (매일·교대마다 하는 점검은 교대 점검표로 봄, 생성기 config notifications.pm_alert_cycles)
const PM_ALERT_CYCLES = ['WEEKLY', 'MONTHLY', 'HALF_YEAR', 'YEARLY'];
const levelRule = (r: string): Level => (RANK_OF[r] === '4' ? '참고' : '주의');

const mk = (rule: string, key: string, text: string, roles: Role[], extra: Partial<Notice> = {}): Notice => ({
  id: `${rule}:${key}`, rule, ruleName: RULE_NAME[rule] ?? rule, level: levelRule(rule), rank: RANK_OF[rule] ?? '3', at: simIso(), ts: SIM.now(),
  text, roles, delivery: ['WO_ASSIGNED', 'WO_DRAFT_READY', 'WO_APPROVAL_REQUEST', 'WR_CHECK_REQUEST', 'APPROVAL_WAIT_30M', 'APPROVAL_WAIT_2H', 'SHIFT_REPORT_PENDING', 'DAILY_REPORT_PENDING', 'DOC_REVISED', 'AFTER_RECORD_CHECK_WAIT'].includes(rule) ? 'BUBBLE' : 'LIST',
  handled: false, ...extra,
});

// 일일 보고서 초안은 다음 날 새벽에 나와서 raised_at 날짜가 하루 뒤 → 메시지의 "09/30"으로 날짜를 정한다
const dailyKey = (n: Record<string, string>) => {
  const m = n.message.match(/(\d{2})\/(\d{2})/);
  return m ? `${n.raised_at.slice(0, 4)}-${m[1]}-${m[2]}` : (n.shift_id || n.raised_at).slice(0, 10);
};

// 9월 과거 알림 중 10/1 08:00에 처리 안 된 것 (생성기 notification.csv)
export const fromPast = (n: Record<string, string> & { to: string[] }): Notice => {
  const rule = n.rule_code, roles = Array.from(new Set(n.to.map((u) => USERS.find((x) => x.id === u)?.role).filter(Boolean))) as Role[];
  const level = LEVEL_OF[n.importance] ?? '주의';
  const eq = n.equipment_id as Eq;
  return {
    id: `past:${n.notification_id}`, rule, ruleName: RULE_NAME[rule] ?? rule, level, rank: rule === 'ALARM_STOP' ? '1' : RANK_OF[rule] ?? (level === '참고' ? '4' : '3'),
    at: n.raised_at, ts: tsOf(n.raised_at), text: n.message.replace(/^\[[^\]]+\]\s*/, ''), related: n.related_info || undefined,
    machine: eq ? ID_OF[eq] : undefined, roles: roles.length ? roles : ['SUP', 'MGR'], userIds: n.to, delivery: n.rule_code.match(/^(WO_|APPROVAL|DAILY|SHIFT|DOC_)/) ? 'BUBBLE' : 'LIST',
    handled: false, past: true, count: Number(n.repeat_count) || undefined, keys: n.pm_task_id ? [n.pm_task_id] : undefined,
    open: rule === 'DAILY_REPORT_PENDING' ? { screen: 'daily', key: dailyKey(n) } : rule.startsWith('PM_') ? { screen: 'pm' } : rule === 'STOCK_LOW' ? { screen: 'inventory', key: n.item_no || undefined } : rule === 'TOOL_LIFE_90' ? { screen: 'tools' } : undefined,
  };
};

// 9월 미처리 "예방 정비 기한 하루 전" 알림을 같은 기한 날짜끼리 1건으로 묶는다 (FR-AST-02-08, 2026-10-20)
export const groupPmPast = (ns: Notice[]): Notice[] => {
  const groups = new Map<string, Notice[]>();
  const rest = ns.filter((n) => {
    const due = n.rule === 'PM_DUE_SOON' ? n.text.match(/기한 (\d{2}\/\d{2})/)?.[1] : undefined;
    if (!due) return true;
    groups.set(due, [...(groups.get(due) ?? []), n]);
    return false;
  });
  return [...rest, ...[...groups].map(([due, g]) => ({
    ...g[0], id: `past:PM_DUE_SOON:${due}`, text: `기한 ${due} 예방 정비 ${g.length}건`, machine: undefined,
    related: g.map((x) => x.text.replace(/\s*—\s*기한.*$/, '')).join(' · '), keys: g.flatMap((x) => x.keys ?? []),
  }))];
};

// 사건(API-STR-01)으로 생기는 알림: 공구 수명 90%, 병목 발생·이동
export const fromEvents = (evs: SimEvent[]): Notice[] => {
  const out: Notice[] = [];
  evs.forEach((e) => {
    if (e.type === 'tool_life') {
      const tid = String(e.tool_id), eq = tid.slice(0, 6) as Eq;
      out.push(mk('TOOL_LIFE_90', `${tid}:${e.at}`, `${tid} 사용률 ${e.usage_pct}% — 교체 준비 (90% 이상)`, ['OPR', 'MNT', 'SUP'], { machine: ID_OF[eq], at: String(e.at), ts: tsOf(String(e.at)), open: { screen: 'tools' }, related: 'DOC-07 §9 공구 수명' }));
    }
    if (e.type === 'bottleneck_changed' && !(e.process_code === 'OP-30' && e.cause_code === 'BASE')) {
      out.push(mk('BOTTLENECK_MOVE', String(e.at), `병목 ${e.prev_process_code} → ${e.process_code} · ${CAUSE_KO[String(e.cause_code)] ?? e.cause_code}`, ['SUP', 'MGR'], { at: String(e.at), ts: tsOf(String(e.at)), related: 'DOC-07 §7.5 병목 원인별 조치' }));
    }
  });
  return out;
};

export interface RuleCtx {
  twin: Twin | null; inv: { items: { item_no: string; item_name: string; stock_qty: number; safety_stock: number; unit: string; owner_role: string; low: boolean; low_at_start?: boolean }[] } | null;
  pm: { tasks: { pm_task_id: string; equipment_id: string; item_name: string; cycle_code: string; next_due: string | null; state: string | null }[]; today_records?: { pm_record_id?: string; pm_task_id: string; status: string }[] } | null;
  wos: WorkOrder[]; wrs: WorkRecord[]; shiftReports: { shift_id: string; status: string }[] | null; dailyReports: { work_date: string; status: string }[] | null;
  cmm: { imports: { cmm_import_id: number; status: string; error_text: string | null; file_name: string; received_at: string; lot_no: string }[] } | null;
  quality: { items: { item_seq: string; item_name: string; out?: number[]; n: number; values?: { at: string; v: number }[] }[]; live_from?: string } | null;
  alerts: AlertRec[]; pastAlarms: { equipment_id: string; alarm_code: string; occurred_at: string }[]; notices: Notice[];
  rules: { repeat_days: number; repeat_count: number; target_risk_pct: number; repeat2_days: number };
  downtimes: Downtime[] | null; srs: SimpleRecord[];
}

// 상태로 판단하는 알림 (켜질 조건, 풀릴 조건)
export function derive(c: RuleCtx): { add: Notice[]; resolve: string[] } {
  const add: Notice[] = [], resolve: string[] = [], t = c.twin, now = SIM.now();
  if (t) {
    const sid = t.shift.shift_id;
    // 재공 경고 — 재공 위치마다 교대에 처음 1번 (WIP-20-30은 한도 30 도달, WIP-30-40 제외, DOC-07 §10.1)
    Object.entries(t.wip).forEach(([code, n]) => {
      const L = t.wip_limits[code];
      if (L?.warn && L.warn_over != null && n > L.warn_over) add.push(mk('WIP_WARN', `${code}:${sid}`, `${WIP_NAME[code]}(${code}) 재공 ${n}개 — 경고 기준 ${L.warn_over}개 초과 (한도 ${L.limit})`, ['SUP', 'MGR'], { related: 'DOC-07 §7.2' }));
    });
    // 목표 미달 위험 — 교대 시작 60분 뒤부터, 교대에 처음 1번
    const p = t.production;
    if (p.elapsed_work_min >= 60 && p.forecast_qty < (p.total_target_qty * c.rules.target_risk_pct) / 100)
      add.push(mk('TARGET_RISK', sid, `이 속도면 총 목표 ${p.total_target_qty}개보다 ${p.short_qty}개 부족 (예측 ${p.forecast_qty}개, 추정)`, ['SUP', 'MGR'], { related: 'DOC-07 §8' }));
    // 로트 납기 지연 위험
    t.orders.filter((o) => o.delay === '▲ 지연 위험').forEach((o) => add.push(mk('LOT_DUE_RISK', o.order_no, `${o.order_no} 납기 ${md(o.due_at)} — 남은 ${o.order_qty - o.done_qty}개, 지금 속도로는 늦을 수 있음 (추정)`, ['SUP', 'MGR'], { open: { screen: 'lots' } })));
    // 공구 수명 90% — 사건 알림이 놓쳤을 때도 (교체하면 자동 처리)
    Object.values(t.equipment).flatMap((e) => e.tools).forEach((tl) => {
      const open = c.notices.filter((n) => n.rule === 'TOOL_LIFE_90' && !n.handled && n.text.startsWith(tl.tool_id));
      if (tl.usage_pct < 90) open.forEach((n) => resolve.push(n.id));
    });
  }
  // 재고 부족 (재고 ≤ 안전 재고, 받는 사람 = 관리 역할 + MGR). 보충되면 자동 처리
  // 10/1 08:00에 이미 부족한 품목은 9월에 알렸으므로(미처리분은 fromPast) 다시 내지 않는다 — 새로 부족해질 때만 (gen/notify.py와 같음)
  c.inv?.items.forEach((i) => {
    const id = `STOCK_LOW:${i.item_no}`;
    if (i.low && i.safety_stock > 0) { if (!i.low_at_start) add.push(mk('STOCK_LOW', i.item_no, `${i.item_name} 재고 ${i.stock_qty}${i.unit} — 안전 재고 ${i.safety_stock}${i.unit} 이하`, [i.owner_role as Role, 'MGR'], { open: { screen: 'inventory', key: i.item_no } })); }
    else { resolve.push(id); c.notices.filter((n) => n.past && n.rule === 'STOCK_LOW' && !n.handled && n.text.includes(i.item_name)).forEach((n) => resolve.push(n.id)); }
  });
  // 예방 정비 기한 하루 전 / 넘김 (주 1회 이상 주기 항목만). 9월에 같은 항목으로 이미 알렸으면 다시 내지 않는다
  // 하루 전은 같은 기한 날짜끼리 1건으로 묶는다 (FR-AST-02-08, 2026-10-20). 묶인 항목이 모두 끝나거나(OK) 기한을 넘기면 자동 처리
  const today = simIso().slice(0, 10);
  const samePm = (n: Notice, x: { equipment_id: string; item_name: string }) => n.machine === ID_OF[x.equipment_id as Eq] && n.text.includes(x.item_name);
  const pmTasks = c.pm?.tasks.filter((x) => PM_ALERT_CYCLES.includes(x.cycle_code)) ?? [];
  const pastKeys = new Set(c.notices.filter((n) => n.past && n.rule === 'PM_DUE_SOON').flatMap((n) => n.keys ?? []));
  const soon = new Map<string, typeof pmTasks>();
  pmTasks.forEach((x) => {
    if (x.state === 'OVERDUE') {
      // 9월 알림이 늦게 들어오면(로그인 직후) 먼저 낸 것이 겹쳐 남으므로 풀어 둔다 (2026-10-20)
      if (c.notices.some((n) => n.past && n.rule === 'PM_OVERDUE' && samePm(n, x))) resolve.push(`PM_OVERDUE:${x.pm_task_id}`);
      else add.push(mk('PM_OVERDUE', x.pm_task_id, `${x.equipment_id} ${x.item_name} — 기한 ${md(x.next_due)} 넘김`, ['MNT', 'SUP'], { machine: ID_OF[x.equipment_id as Eq], open: { screen: 'pm' } }));
    }
    // 하루 전에만 (기한 당일 항목은 전날 08:00에 이미 알림)
    else if (x.state === 'DUE_SOON' && (x.next_due ?? '').slice(0, 10) > today && !pastKeys.has(x.pm_task_id)) {
      const d = (x.next_due ?? '').slice(0, 10);
      soon.set(d, [...(soon.get(d) ?? []), x]);
    }
    if (x.state === 'OK') {
      resolve.push(`PM_OVERDUE:${x.pm_task_id}`);
      c.notices.filter((n) => n.past && n.rule === 'PM_OVERDUE' && !n.handled && n.text.includes(x.item_name) && n.machine === ID_OF[x.equipment_id as Eq]).forEach((n) => resolve.push(n.id));
    }
  });
  soon.forEach((xs, d) => add.push(mk('PM_DUE_SOON', d, `기한 ${md(d)} (내일) 예방 정비 ${xs.length}건`, ['MNT'], { open: { screen: 'pm' }, keys: xs.map((x) => x.pm_task_id), related: xs.map((x) => `${x.equipment_id} ${x.item_name}`).join(' · ') })));
  // 묶음(하루 전): 묶인 항목 중 아직 하루 전 상태인 것이 없으면 풀림
  const stillSoon = new Set(pmTasks.filter((x) => x.state === 'DUE_SOON').map((x) => x.pm_task_id));
  c.notices.filter((n) => n.rule === 'PM_DUE_SOON' && !n.handled && n.keys?.length && n.keys.every((k) => !stillSoon.has(k))).forEach((n) => resolve.push(n.id));
  // 묶기 전(항목마다 1건) 방식으로 이미 쌓인 알림은 묶음 알림으로 바뀌었으므로 풀어 둔다 (시연 진행 중에 코드가 바뀐 경우)
  c.notices.filter((n) => n.rule === 'PM_DUE_SOON' && !n.handled && (n.past ? !n.id.startsWith('past:PM_DUE_SOON:') : !n.keys)).forEach((n) => resolve.push(n.id));
  // 예방 정비 실시 기록 확인 (오늘 끝난 정비의 실시 기록이 초안이면 → 보전). 설비마다 1건으로 묶고, 묶인 기록이 모두 확정되면 풀림
  const recs = c.pm?.today_records ?? [], eqOf = (r: { pm_task_id: string }) => r.pm_task_id.match(/^PM-([A-Z0-9]+-\d{2})-/)?.[1] ?? r.pm_task_id;
  const drafts = new Map<string, string[]>();
  recs.filter((r) => r.status === 'DRAFT').forEach((r) => drafts.set(eqOf(r), [...(drafts.get(eqOf(r)) ?? []), r.pm_task_id]));
  drafts.forEach((ids, eq) => add.push(mk('PM_RECORD_CHECK', `${eq}:${today}`, `${eq} 예방 정비 ${ids.length}건 끝남 — 실시 기록 확인`, ['MNT'], { machine: ID_OF[eq as Eq], open: { screen: 'pm' }, keys: ids })));
  c.notices.filter((n) => n.rule === 'PM_RECORD_CHECK' && !n.handled && !drafts.has(n.id.split(':')[1])).forEach((n) => resolve.push(n.id));
  // 작업지시서 승인 대기 30분 ⓘ / 2시간 ▲ (SUP, 말풍선)
  c.wos.filter((w) => w.state === 'draft' || w.state === 'editing').forEach((w) => {
    const m = (now - tsOf(w.created)) / 60000;
    if (m >= 30) add.push(mk('APPROVAL_WAIT_30M', w.no, `작업지시서 ${w.no} 승인 대기 30분 넘음`, ['SUP'], { open: { screen: 'wo', key: w.no } }));
    if (m >= 120) add.push(mk('APPROVAL_WAIT_2H', w.no, `작업지시서 ${w.no} 승인 대기 2시간 넘음`, ['SUP', 'MGR'], { level: '주의', open: { screen: 'wo', key: w.no } }));
  });
  c.wos.filter((w) => !(w.state === 'draft' || w.state === 'editing')).forEach((w) => { resolve.push(`APPROVAL_WAIT_30M:${w.no}`, `APPROVAL_WAIT_2H:${w.no}`, `WO_APPROVAL_REQUEST:${w.no}`); });
  // 작업지시서 승인 요청 (초안이 생기면 바로 SUP, 말풍선) — 승인 대기 30분이 뜨면 그쪽으로 넘어가 풀림 (2026-10-20)
  c.wos.filter((w) => w.state === 'draft' || w.state === 'editing').forEach((w) => {
    if ((now - tsOf(w.created)) / 60000 < 30) add.push(mk('WO_APPROVAL_REQUEST', w.no, `작업지시서 ${w.no} 승인해 주세요`, ['SUP'], { open: { screen: 'wo', key: w.no }, at: w.created, ts: tsOf(w.created) }));
    else resolve.push(`WO_APPROVAL_REQUEST:${w.no}`);
  });
  // 작업기록서 확정 전 (담당 MNT, 알림 탭만) / 확인 요청 (SUP, 말풍선) — 확정·확인하면 풀림 (2026-10-20)
  c.wrs.forEach((r) => {
    const w = c.wos.find((x) => x.no === r.woNo);
    if (r.state === 'draft' || r.state === 'editing') add.push(mk('WR_CONFIRM_PENDING', r.no, `작업기록서 ${r.no} 확정 전 (작업지시서 ${r.woNo})`, ['MNT'], { userIds: w?.assignee ? [w.assignee] : undefined, open: { screen: 'wr', key: r.woNo } }));
    else resolve.push(`WR_CONFIRM_PENDING:${r.no}`);
    if (r.state === 'confirmed') add.push(mk('WR_CHECK_REQUEST', r.no, `작업기록서 ${r.no} 확정됨 — 확인해 주세요`, ['SUP'], { open: { screen: 'wr', key: r.woNo } }));
    if (r.state === 'checked') resolve.push(`WR_CHECK_REQUEST:${r.no}`);
  });
  // 교대 보고서 확정 요청 (교대 끝 AI비서 초안 → 그 교대 SUP) / 일일 보고서 확정 요청 (MGR)
  c.shiftReports?.forEach((r) => {
    if (r.status === 'CONFIRMED') resolve.push(`SHIFT_REPORT_PENDING:${r.shift_id}`);
    else if (t && r.shift_id !== t.shift.shift_id && (r as { partial?: boolean }).partial === false)
      add.push(mk('SHIFT_REPORT_PENDING', r.shift_id, `교대 보고서 초안을 썼어요. 확인하고 확정해 주세요 (${r.shift_id})`, ['SUP'], { open: { screen: 'shift', key: r.shift_id } }));
  });
  c.dailyReports?.forEach((r) => {
    if (r.status === 'CONFIRMED') { resolve.push(`DAILY_REPORT_PENDING:${r.work_date}`); c.notices.filter((n) => n.rule === 'DAILY_REPORT_PENDING' && n.open?.key === r.work_date).forEach((n) => resolve.push(n.id)); }
    else if (c.notices.some((n) => n.rule === 'DAILY_REPORT_PENDING' && n.open?.key === r.work_date && n.past)) resolve.push(`DAILY_REPORT_PENDING:${r.work_date}`); // 9월 알림과 겹치면 풀어 둔다
    else add.push(mk('DAILY_REPORT_PENDING', r.work_date, `${md(r.work_date)} 일일 보고서를 확정해 주세요`, ['MGR'], { open: { screen: 'daily', key: r.work_date } }));
  });
  // CMM 결과 파일 오류·판정 불일치
  c.cmm?.imports.forEach((x) => {
    if (x.status === 'FAILED' || x.status === 'ERROR') add.push(mk('CMM_FILE_ERROR', String(x.cmm_import_id), `결과 파일 ${x.file_name} 읽기 실패 — ${x.error_text ?? ''} (원본 보관, 기록 안 함)`, ['SUP', 'OPR'], { open: { screen: 'quality' } }));
    if (x.status === 'CHECK') add.push(mk('CMM_JUDGE_MISMATCH', String(x.cmm_import_id), `결과 파일 ${x.file_name} 확인 필요 — ${x.error_text ?? ''}`, ['SUP'], { open: { screen: 'quality' } }));
  });
  // 관리도 이상 (I-MR ±3σ 밖)
  // 10/1 측정점만 (9월 점은 생성기 9월 알림이 이미 판단). 키 = 마지막 이상 점의 측정 시각 (최근 50개 창이 밀려도 같은 점은 1건)
  const from = c.quality?.live_from ?? '';
  c.quality?.items.forEach((it) => {
    const out = (it.out ?? []).filter((i) => !it.values || it.values[i].at >= from);
    if (out.length) add.push(mk('SPC_OUT', `${it.item_seq}:${it.values?.[out[out.length - 1]].at ?? `${it.n}:${out[out.length - 1]}`}`, `${it.item_name} 관리도 ±3σ 밖 점 ${out.length}개 — 다음 부품 바로 측정`, ['SUP'], { open: { screen: 'quality' } }));
  });
  // 기록 없는 정지 (FR-AST-02-20): 사후 기록을 저장하면(확정 전이라도) 처리됨. 교대 끝 1시간 전 주의로 올리기는 2차
  (c.downtimes ?? []).filter(isUnrecordedStop).forEach((d) => {
    const key = stopKeyOf(d), eq = d.equipment_id as Eq, m = ID_OF[eq];
    if (c.srs.some((r) => r.kind === 'after' && r.stopKey === key && r.revisions.length)) { resolve.push(`UNRECORDED_STOP:${key}`); return; }
    if (m) add.push(mk('UNRECORDED_STOP', key, `${eq} ${d.start_at.slice(11, 16)}~${d.end_at!.slice(11, 16)} (${d.minutes}분) 정지, 기록이 없어요 — 사후 기록을 써 주세요`, ['OPR', 'MNT', 'SUP'],
      { machine: m, open: { screen: 'after', key } }));
  });
  // 사후 기록 확인 대기 (FR-AST-02-21): 사후 기록이 확정되면 반장에게, 반장이 확인하면 처리됨
  c.srs.filter((r) => r.kind === 'after' && r.state === 'confirmed').forEach((r) => {
    if (r.checkedBy) resolve.push(`AFTER_RECORD_CHECK_WAIT:${r.no}`);
    else add.push(mk('AFTER_RECORD_CHECK_WAIT', r.no, `사후 기록 ${r.no} (${MACHINES[r.machine].name} ${r.start?.slice(11, 16) ?? ''}~${r.end?.slice(11, 16) ?? ''}) 확인해 주세요`, ['SUP'], { machine: r.machine, open: { screen: 'sr', key: r.no } }));
  });
  return { add, resolve };
}

// 반복 알람 (DOC-07 §10.2·§10.4): 같은 설비·같은 알람이 7일 안 3번 이상 = 1단계. 1단계를 조치 계획과 함께 처리한 뒤 7일 안에 다시 뜨면 2단계
//  → OP-30: 원인 점검 작업지시서 / 다른 공정: 원인 점검 요청 + 간이 원인 점검 기록. 주의·정지 등급만 (조작 안내 제외)
export function repeatOf(a: AlertRec, c: RuleCtx): Notice | null {
  if (a.kind === 'guide') return null;
  const eq = MACHINES[a.machine].eq!, since = a.ts - c.rules.repeat_days * 864e5;
  const n = c.pastAlarms.filter((x) => x.equipment_id === eq && x.alarm_code === a.code && tsOf(x.occurred_at) >= since && tsOf(x.occurred_at) <= a.ts).length
    + c.alerts.filter((x) => x.machine === a.machine && x.code === a.code && x.ts >= since && x.ts <= a.ts).length;
  const prev = c.notices.find((x) => x.rule === 'REPEAT_ALARM' && x.machine === a.machine && x.text.includes(`알람 ${a.code}`) && x.handled && x.plan && tsOf(x.handledAt) >= a.ts - c.rules.repeat2_days * 864e5);
  if (prev) {
    const op30 = MACHINES[a.machine].op === 'OP-30';
    return mk(op30 ? 'REPEAT_ALARM_2' : 'CAUSE_CHECK_REQUEST', `${eq}:${a.code}:${a.eventId}`, `${eq} 알람 ${a.code} — 조치 계획(“${prev.plan}”) 뒤에도 다시 발생 (2단계)${op30 ? ' → 원인 점검 작업지시서' : ' → 원인 점검 간이 기록'}`, ['MNT', 'SUP'], { machine: a.machine, stage: 2, related: 'DOC-03 §1.4 반복 알람 2단계' });
  }
  if (n >= c.rules.repeat_count) return mk('REPEAT_ALARM', `${eq}:${a.code}:${new Date(a.ts).toISOString().slice(0, 10)}`, `${eq} 알람 ${a.code} — ${c.rules.repeat_days}일 안 ${n}번 (반복 알람 1단계, 처리할 때 조치 계획 필수)`, ['MNT', 'SUP'], { machine: a.machine, stage: 1, count: n, related: 'DOC-07 §10.2' });
  return null;
}
