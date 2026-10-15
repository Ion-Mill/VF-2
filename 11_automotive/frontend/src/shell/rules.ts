// 알림 규칙 (notification_rule.csv 25종, DOC-07 10장) — 알릴지·중요도·보고 순위·받는 역할은 프로그램 규칙이 정한다 (FR-AST-02-14).
// 알람 발생(ALARM_STOP·WARN·GUIDE)은 알람 기록(AlertRec)으로, 나머지는 여기서 Notice로 만든다.
// 같은 조건이면 id가 같아서 한 번만 생긴다. 조건이 풀리면(공구 교체·재고 보충·정비 끝·보고서 확정) 자동 처리된다.
import { CAUSE_KO, ID_OF, MACHINES, WIP_NAME, type Role } from './data';
import type { Eq, SimEvent, Twin } from './live';
import { SIM, md, simIso, tsOf } from './live';
import type { AlertRec, Level, Notice } from './model';
import { USERS } from './model';
import type { WorkOrder } from './workflow';

export const RULE_NAME: Record<string, string> = {
  REPEAT_ALARM: '반복 알람 (1단계)', REPEAT_ALARM_2: '반복 알람 2단계', CAUSE_CHECK_REQUEST: '원인 점검 요청', TARGET_RISK: '목표 미달 위험',
  BOTTLENECK_MOVE: '병목 발생·이동', WIP_WARN: '재공 경고', LOT_DUE_RISK: '로트 납기 지연 위험', STOCK_LOW: '재고 부족', PM_DUE_SOON: '예방 정비 기한 하루 전',
  PM_OVERDUE: '예방 정비 기한 넘김', TOOL_LIFE_90: '공구 수명', APPROVAL_WAIT_30M: '승인 대기', APPROVAL_WAIT_2H: '승인 대기 2시간', WO_ASSIGNED: '작업지시서 배정',
  WO_DRAFT_READY: '작업지시서 초안 검토', DAILY_REPORT_PENDING: '일일 보고서 확정 요청', DOC_REVISED: '문서 수정', SPC_OUT: '관리도 이상',
  SHIFT_REPORT_PENDING: '교대 보고서 확정 요청', CMM_FILE_ERROR: 'CMM 결과 파일 오류', CMM_JUDGE_MISMATCH: 'CMM 판정 불일치', CMM_NO_RESULT: 'CMM 결과 미수신',
  ALARM_STOP: '알람 발생 (정지)', ALARM_WARN: '알람 발생 (주의)', ALARM_GUIDE: '알람 발생 (조작 안내)',
};
// 보고 순위 (gen/reports.py RANK와 같음): 2 생산 위험 / 3 주의 / 4 참고
const RANK_OF: Record<string, string> = {
  TARGET_RISK: '2', BOTTLENECK_MOVE: '2', WIP_WARN: '2', LOT_DUE_RISK: '2', REPEAT_ALARM_2: '3', CAUSE_CHECK_REQUEST: '3', REPEAT_ALARM: '3',
  SPC_OUT: '3', TOOL_LIFE_90: '3', PM_OVERDUE: '3', STOCK_LOW: '3', APPROVAL_WAIT_2H: '3', CMM_FILE_ERROR: '3', CMM_JUDGE_MISMATCH: '3', CMM_NO_RESULT: '3',
  ALARM_GUIDE: '4', PM_DUE_SOON: '4', APPROVAL_WAIT_30M: '4', WO_ASSIGNED: '4', WO_DRAFT_READY: '4', DAILY_REPORT_PENDING: '4', SHIFT_REPORT_PENDING: '4', DOC_REVISED: '4',
};
const LEVEL_OF: Record<string, Level> = { URGENT: '긴급', CAUTION: '주의', INFO: '참고' };
const levelRule = (r: string): Level => (RANK_OF[r] === '4' ? '참고' : '주의');

const mk = (rule: string, key: string, text: string, roles: Role[], extra: Partial<Notice> = {}): Notice => ({
  id: `${rule}:${key}`, rule, ruleName: RULE_NAME[rule] ?? rule, level: levelRule(rule), rank: RANK_OF[rule] ?? '3', at: simIso(), ts: SIM.now(),
  text, roles, delivery: ['WO_ASSIGNED', 'WO_DRAFT_READY', 'APPROVAL_WAIT_30M', 'APPROVAL_WAIT_2H', 'SHIFT_REPORT_PENDING', 'DAILY_REPORT_PENDING', 'DOC_REVISED'].includes(rule) ? 'BUBBLE' : 'LIST',
  handled: false, ...extra,
});

// 9월 과거 알림 중 10/1 08:00에 처리 안 된 것 (생성기 notification.csv)
export const fromPast = (n: Record<string, string> & { to: string[] }): Notice => {
  const rule = n.rule_code, roles = Array.from(new Set(n.to.map((u) => USERS.find((x) => x.id === u)?.role).filter(Boolean))) as Role[];
  const level = LEVEL_OF[n.importance] ?? '주의';
  const eq = n.equipment_id as Eq;
  return {
    id: `past:${n.notification_id}`, rule, ruleName: RULE_NAME[rule] ?? rule, level, rank: rule === 'ALARM_STOP' ? '1' : RANK_OF[rule] ?? (level === '참고' ? '4' : '3'),
    at: n.raised_at, ts: tsOf(n.raised_at), text: n.message.replace(/^\[[^\]]+\]\s*/, ''), related: n.related_info || undefined,
    machine: eq ? ID_OF[eq] : undefined, roles: roles.length ? roles : ['SUP', 'MGR'], userIds: n.to, delivery: n.rule_code.match(/^(WO_|APPROVAL|DAILY|SHIFT|DOC_)/) ? 'BUBBLE' : 'LIST',
    handled: false, past: true, count: Number(n.repeat_count) || undefined,
    open: rule === 'DAILY_REPORT_PENDING' ? { screen: 'daily', key: (n.shift_id || n.raised_at).slice(0, 10) } : rule.startsWith('PM_') ? { screen: 'pm' } : rule === 'STOCK_LOW' ? { screen: 'inventory' } : rule === 'TOOL_LIFE_90' ? { screen: 'tools' } : undefined,
  };
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
  twin: Twin | null; inv: { items: { item_no: string; item_name: string; stock_qty: number; safety_stock: number; unit: string; owner_role: string; low: boolean }[] } | null;
  pm: { tasks: { pm_task_id: string; equipment_id: string; item_name: string; next_due: string | null; state: string | null }[] } | null;
  wos: WorkOrder[]; shiftReports: { shift_id: string; status: string }[] | null; dailyReports: { work_date: string; status: string }[] | null;
  cmm: { imports: { cmm_import_id: number; status: string; error_text: string | null; file_name: string; received_at: string; lot_no: string }[] } | null;
  quality: { items: { item_seq: string; item_name: string; out?: number[]; n: number }[] } | null;
  alerts: AlertRec[]; pastAlarms: { equipment_id: string; alarm_code: string; occurred_at: string }[]; notices: Notice[];
  rules: { repeat_days: number; repeat_count: number; target_risk_pct: number; repeat2_days: number };
}

// 상태로 판단하는 알림 (켜질 조건, 풀릴 조건)
export function derive(c: RuleCtx): { add: Notice[]; resolve: string[] } {
  const add: Notice[] = [], resolve: string[] = [], t = c.twin, now = SIM.now();
  const pastKey = new Set(c.notices.filter((n) => n.past && !n.handled).map((n) => `${n.rule}|${n.related ?? ''}|${n.text}`));
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
  c.inv?.items.forEach((i) => {
    const id = `STOCK_LOW:${i.item_no}`;
    if (i.low && i.safety_stock > 0) { if (!pastKey.has(`STOCK_LOW||${i.item_name}`)) add.push(mk('STOCK_LOW', i.item_no, `${i.item_name} 재고 ${i.stock_qty}${i.unit} — 안전 재고 ${i.safety_stock}${i.unit} 이하`, [i.owner_role as Role, 'MGR'], { open: { screen: 'inventory' } })); }
    else { resolve.push(id); c.notices.filter((n) => n.past && n.rule === 'STOCK_LOW' && !n.handled && n.text.includes(i.item_name)).forEach((n) => resolve.push(n.id)); }
  });
  // 예방 정비 기한 하루 전 / 넘김
  c.pm?.tasks.forEach((x) => {
    if (x.state === 'OVERDUE') add.push(mk('PM_OVERDUE', x.pm_task_id, `${x.equipment_id} ${x.item_name} — 기한 ${md(x.next_due)} 넘김`, ['MNT', 'SUP'], { machine: ID_OF[x.equipment_id as Eq], open: { screen: 'pm' } }));
    else if (x.state === 'DUE_SOON') add.push(mk('PM_DUE_SOON', `${x.pm_task_id}:${x.next_due}`, `${x.equipment_id} ${x.item_name} — 기한 ${md(x.next_due)}`, ['MNT'], { machine: ID_OF[x.equipment_id as Eq], open: { screen: 'pm' } }));
    if (x.state === 'OK') {
      resolve.push(`PM_OVERDUE:${x.pm_task_id}`);
      c.notices.filter((n) => n.past && n.rule.startsWith('PM_') && !n.handled && n.text.includes(x.item_name) && n.machine === ID_OF[x.equipment_id as Eq]).forEach((n) => resolve.push(n.id));
    }
  });
  // 작업지시서 승인 대기 30분 ⓘ / 2시간 ▲ (SUP, 말풍선)
  c.wos.filter((w) => w.state === 'draft' || w.state === 'editing').forEach((w) => {
    const m = (now - tsOf(w.created)) / 60000;
    if (m >= 30) add.push(mk('APPROVAL_WAIT_30M', w.no, `작업지시서 ${w.no} 승인 대기 30분 넘음`, ['SUP'], { open: { screen: 'wo', key: w.no } }));
    if (m >= 120) add.push(mk('APPROVAL_WAIT_2H', w.no, `작업지시서 ${w.no} 승인 대기 2시간 넘음`, ['SUP', 'MGR'], { level: '주의', open: { screen: 'wo', key: w.no } }));
  });
  c.wos.filter((w) => !(w.state === 'draft' || w.state === 'editing')).forEach((w) => { resolve.push(`APPROVAL_WAIT_30M:${w.no}`, `APPROVAL_WAIT_2H:${w.no}`); });
  // 교대 보고서 확정 요청 (교대 끝 AI비서 초안 → 그 교대 SUP) / 일일 보고서 확정 요청 (MGR)
  c.shiftReports?.forEach((r) => {
    if (r.status === 'CONFIRMED') resolve.push(`SHIFT_REPORT_PENDING:${r.shift_id}`);
    else if (t && r.shift_id !== t.shift.shift_id && (r as { partial?: boolean }).partial === false)
      add.push(mk('SHIFT_REPORT_PENDING', r.shift_id, `교대 보고서 초안을 썼어요. 확인하고 확정해 주세요 (${r.shift_id})`, ['SUP'], { open: { screen: 'shift', key: r.shift_id } }));
  });
  c.dailyReports?.forEach((r) => {
    if (r.status === 'CONFIRMED') { resolve.push(`DAILY_REPORT_PENDING:${r.work_date}`); c.notices.filter((n) => n.rule === 'DAILY_REPORT_PENDING' && n.open?.key === r.work_date).forEach((n) => resolve.push(n.id)); }
    else if (!c.notices.some((n) => n.rule === 'DAILY_REPORT_PENDING' && n.open?.key === r.work_date && n.past))
      add.push(mk('DAILY_REPORT_PENDING', r.work_date, `${md(r.work_date)} 일일 보고서를 확정해 주세요`, ['MGR'], { open: { screen: 'daily', key: r.work_date } }));
  });
  // CMM 결과 파일 오류·판정 불일치
  c.cmm?.imports.forEach((x) => {
    if (x.status === 'FAILED' || x.status === 'ERROR') add.push(mk('CMM_FILE_ERROR', String(x.cmm_import_id), `결과 파일 ${x.file_name} 읽기 실패 — ${x.error_text ?? ''} (원본 보관, 기록 안 함)`, ['SUP', 'OPR'], { open: { screen: 'quality' } }));
    if (x.status === 'CHECK') add.push(mk('CMM_JUDGE_MISMATCH', String(x.cmm_import_id), `결과 파일 ${x.file_name} 확인 필요 — ${x.error_text ?? ''}`, ['SUP'], { open: { screen: 'quality' } }));
  });
  // 관리도 이상 (I-MR ±3σ 밖)
  c.quality?.items.forEach((it) => { if (it.out && it.out.length) add.push(mk('SPC_OUT', `${it.item_seq}:${it.n}:${it.out[it.out.length - 1]}`, `${it.item_name} 관리도 ±3σ 밖 점 ${it.out.length}개 — 다음 부품 바로 측정`, ['SUP'], { open: { screen: 'quality' } })); });
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
