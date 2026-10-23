// 디자인 통일 C안 — 화면별 결론 띠를 고르는 함수 (캔버스 "C안 규칙 3"). React 없는 순수 함수라 node로 시험한다 (bands_check.mjs).
// 원칙: 한 화면에 띠 1개. 여러 경우가 겹치면 긴급 → 주의 → AI비서 초안 → 할 일 → 정상 순서로 가장 앞의 것.
//       보고서 화면은 UI설계서 2.5 보고 순위(0 안전 → 0-1 오래 방치 → 1 긴급 → 2 생산 위험 → 3 주의 → 4 참고) 첫 항목.
//       첫 줄(title) = "무엇이 · 어떤 상태" + 숫자 하나, 30자 안쪽. 둘째 줄(desc) = 왜 / 먼저 할 일. 버튼(action)은 1개.
//       문장은 프로그램이 화면 값으로 만든다. 비서가 다듬은 문장이면 desc 끝에 "· 비서 정리" (UI설계서 2.6).
// 입력은 화면이 이미 가진 값을 그대로 넘기는 작은 모양 — 각 함수 위 주석에 어디서 오는지 적었다.
import { fmtElapsed, fmtFrac, fmtNum, fmtPct, fmtQty } from './format';

export type BandTone = 'crit' | 'warn' | 'draft' | 'todo' | 'ok';
export interface BandSpec {
  tone: BandTone;
  title: string;          // 첫 줄 (기호는 Band 부품이 붙임: ⚠ ▲ ⓘ)
  desc?: string;          // 둘째 줄
  chips?: string[];       // 근거 숫자 · 기록 번호, 4개 넘으면 "외 N건"
  action?: string;        // 먼저 할 일 버튼 글자 (없으면 버튼 없음)
  actionLock?: boolean;   // 확정 · 승인 버튼 = 자물쇠
  draftLabel?: string;    // tone = draft일 때 칩 글자 (기본 "AI비서 초안")
}

export const TONE_ORDER: BandTone[] = ['crit', 'warn', 'draft', 'todo', 'ok'];
/** 후보 중 TONE_ORDER가 가장 앞인 것 하나. 같은 색이면 먼저 넣은 것 */
export const pickBand = (cands: (BandSpec | null | undefined | false | 0)[]): BandSpec | null => {
  const xs = cands.filter((c): c is BandSpec => !!c);
  if (!xs.length) return null;
  return xs.reduce((a, b) => (TONE_ORDER.indexOf(b.tone) < TONE_ORDER.indexOf(a.tone) ? b : a));
};

// ---------------------------------------------------------------- 재고 (InventoryScreen)
// items = inv.items ({ item_name, unit, stock_qty, safety_stock, low }), pendingInspect = 입고 검사 대기 건수
export interface InvItem { item_name: string; unit: string; stock_qty: number; safety_stock: number; low: boolean }
export function inventoryBand(items: InvItem[], pendingInspect = 0): BandSpec {
  const zero = items.filter((i) => i.stock_qty <= 0);
  const low = items.filter((i) => i.low || i.stock_qty < i.safety_stock).sort((a, b) => a.stock_qty / a.safety_stock - b.stock_qty / b.safety_stock);
  const lowText = (i: InvItem) => `${i.item_name} ${fmtFrac(i.stock_qty, i.safety_stock)} ${i.unit}`;
  return pickBand([
    zero.length && { tone: 'crit', title: `재고 0 품목 ${zero.length}개`, desc: zero.map((i) => i.item_name).join(' · '), action: '입고 등록' },
    low.length && { tone: 'warn', title: `안전 재고 이하 ${low.length}품목`, desc: `${low.slice(0, 2).map(lowText).join(' · ')}${low.length > 2 ? ` 외 ${low.length - 2}품목` : ''}`, action: '입고 등록' },
    pendingInspect > 0 && { tone: 'todo', title: `입고 검사 대기 ${pendingInspect}건`, action: '입고 검사' },
    { tone: 'ok', title: `${items.length}품목 모두 안전 재고 위` },
  ])!;
}

// ---------------------------------------------------------------- 공구 수명 (ToolsScreen) — 보기 전용이라 버튼 없음
// tools = f.data.tools ({ equipment_id, tool_no, usage_pct, warn }) + label(공구 이름, 화면이 MASTERS로 붙임)
export interface ToolRow { equipment_id: string; tool_no: string; label: string; usage_pct: number; warn: boolean }
export function toolsBand(tools: ToolRow[], limitPct = 90): BandSpec {
  const s = [...tools].sort((a, b) => b.usage_pct - a.usage_pct);
  const full = s.filter((t) => t.usage_pct >= 100), near = s.filter((t) => t.warn || t.usage_pct >= limitPct);
  const name = (t: ToolRow) => `${t.equipment_id} ${t.tool_no} ${t.label} ${fmtPct(t.usage_pct)}`;
  return pickBand([
    full.length && { tone: 'crit', title: `수명 한도 도달 ${full.length}개 — ${full[0].equipment_id} ${full[0].tool_no}`, desc: '교체는 작업자 · 보전 담당' },
    near.length && { tone: 'warn', title: `교체 준비 ${near.length}개 — ${near[0].equipment_id} ${near[0].tool_no}`, desc: `${near[0].label} ${fmtPct(near[0].usage_pct)} · 기준 ${limitPct}%` },
    { tone: 'ok', title: `교체 준비 기준(${limitPct}%) 넘은 공구 없음`, desc: s[0] ? `가장 많이 쓴 공구: ${name(s[0])}` : undefined },
  ])!;
}

// ---------------------------------------------------------------- 예방 정비 (PmScreen 전체 장비)
// counts = PmScreen countOf(pm.tasks) 결과, overEqs = 기한 지남 설비(급한 순), onTime = pm.on_time_rate_pct, target = 90
export function pmBand(counts: { over: number; soon: number; week: number }, overEqs: string[], onTime: number | null, target = 90): BandSpec {
  const rate = onTime == null ? '' : `9월 실시율 ${fmtPct(onTime)} (목표 ${target}%)`;
  return pickBand([
    counts.over > 0 && { tone: 'warn', title: `기한 지남 ${counts.over}건 — ${overEqs[0] ?? ''} 먼저`, desc: [counts.soon ? `오늘 ${counts.soon}건` : '', rate].filter(Boolean).join(' · '), action: overEqs[0] ? `${overEqs[0]} 보기` : undefined },
    counts.soon > 0 && { tone: 'todo', title: `오늘 기한 ${counts.soon}건`, desc: rate || undefined },
    { tone: 'ok', title: `기한 지남 없음 · 이번 주 ${counts.week}건`, desc: rate || undefined },
  ])!;
}

// ---------------------------------------------------------------- 로트 추적 (LotScreen) — 고른 로트 하나
// lot = f.data.lots에서 고른 것 ({ lot_no, status, order_no, material_lot_no, input_qty }), judged = OP-50 판정 수, decide = DECIDE 상태 로트 수(반장 · 관리자)
export const LOT_STATUS: Record<string, string> = { IN_PROCESS: '생산 중', WAIT_INSPECTION: '검사 대기', WAIT_JUDGEMENT: '판정 대기', HOLD_REVIEW: '보류 검토', ON_HOLD: '보류', PASSED: '합격', RELEASED: '해제', SCRAPPED: '폐기' };
export interface LotIn { lot_no: string; status: string; order_no?: string; material_lot_no?: string; input_qty: number; enhanced?: boolean; suspect?: boolean }
export function lotBand(lot: LotIn | null, judged: number, decide: number, failQty = 0): BandSpec {
  if (!lot) return { tone: 'todo', title: '로트를 고르세요', desc: 'LOT · MAT · SHP 번호로 찾거나 위 목록에서 고르기' };
  const st = LOT_STATUS[lot.status] ?? lot.status;
  const chips = [lot.order_no, lot.material_lot_no].filter(Boolean) as string[];
  const judgedTxt = `OP-50 판정 ${fmtFrac(judged, lot.input_qty)}`;
  const done = ['PASSED', 'RELEASED'].includes(lot.status); // 판정 끝난 로트의 불합격 = 그 개수만 폐기, 로트는 합격
  return pickBand([
    (lot.status === 'SCRAPPED' || (failQty > 0 && !done) || lot.suspect) && { tone: 'crit', title: `${lot.lot_no} ${lot.suspect ? '의심 로트' : failQty > 0 ? `불합격 ${failQty}개` : st}`, desc: judgedTxt, chips, action: '검사 기록' },
    ['WAIT_JUDGEMENT', 'HOLD_REVIEW', 'ON_HOLD'].includes(lot.status) && { tone: 'warn', title: `${lot.lot_no} ${st} — 출하 금지`, desc: `${judgedTxt}${decide ? ` · 결정 필요 ${decide}건 (반장)` : ''}`, chips, action: '검사 기록' },
    lot.enhanced && !done && { tone: 'warn', title: `${lot.lot_no} 강화 검사 중`, desc: judgedTxt, chips },
    done && { tone: 'ok', title: `${lot.lot_no} ${st} — 출하 가능`, desc: `${judgedTxt}${failQty ? ` · 불합격 ${failQty}개 따로 폐기` : ''}`, chips },
    !done && { tone: 'todo', title: `${lot.lot_no} ${st}`, desc: judgedTxt, chips },
  ])!;
}

// ---------------------------------------------------------------- 검사 기록 (QualityScreen) — 고른 로트
// states = QualityScreen partState 결과 배열, sel = 고른 순번, next = 다음 입력 글자("M6 입력" 등), cmmErr = 30일 CMM 결과 파일 오류 중 안 끝난 것
export function qualityBand(lotNo: string, states: string[], opts: { sel?: number | null; selText?: string; next?: string; cmmErr?: number; enhanced?: boolean }): BandSpec {
  const n = (k: string) => states.filter((s) => s === k).length;
  const measured = n('pass') + n('warn') + n('fail') + n('none');
  const head = `${lotNo} 측정 ${fmtFrac(measured, states.length)}`;
  return pickBand([
    n('fail') > 0 && { tone: 'crit', title: `${head} — 불합격 ${n('fail')}`, desc: '재측정 · 보류 검토', action: opts.next },
    (opts.cmmErr ?? 0) > 0 && { tone: 'crit', title: `CMM 결과 파일 오류 ${opts.cmmErr}건`, desc: '수동 입력이 필요해요' },
    (n('warn') > 0 || opts.enhanced) && { tone: 'warn', title: `${head} — 주의 ${n('warn')}`, desc: opts.enhanced ? '강화 검사 중' : '관리 한계(3σ) 밖 · M6 불합격', action: opts.next },
    { tone: 'ok', title: `${head} — 불합격 0`, desc: opts.selText, action: opts.next },
  ])!;
}

// ---------------------------------------------------------------- 공정 능력 · 불량 (QualityScreen cap)
// items = qs.data.items ({ item_name, cpk, cpk_min }), n = 측정값 수, defect = { qty, total } (9/1 ~ 오늘)
export function capBand(items: { item_name: string; cpk: number | null; cpk_min: number }[], n: number, defect: { qty: number; total: number }): BandSpec {
  const rate = `불량률 ${fmtPct((defect.qty / Math.max(1, defect.total)) * 100)} (${fmtFrac(defect.qty, defect.total)})`;
  if (n < 50) return { tone: 'todo', title: `Cpk 계산 중 (${n} / 50)`, desc: rate };
  const low = items.filter((i) => i.cpk != null && i.cpk < i.cpk_min).sort((a, b) => (a.cpk! - a.cpk_min) - (b.cpk! - b.cpk_min));
  return low.length
    ? { tone: 'warn', title: `Cpk 기준 미달 ${low.length}항목 — ${low[0].item_name} ${fmtNum(low[0].cpk, 2)}`, desc: `기준 ${fmtNum(low[0].cpk_min, 2)} · ${rate}`, action: '관리도 보기' }
    : { tone: 'ok', title: `Cpk ${items.length}항목 모두 기준 이상`, desc: rate };
}

// ---------------------------------------------------------------- 지침카드 목록 · 한 장 (CardScreen)
// alerts = ctx.alerts ({ machine 이름, code, name, kind, handled, minutes, responsible, first })
export interface CardIn { machine: string; code: string; name: string; kind: 'alarm' | 'warn' | 'guide'; handled: boolean; minutes: number; responsible?: string; first?: string; src?: string; handledBy?: string; handledAt?: string }
export function cardsBand(alerts: CardIn[]): BandSpec {
  const open = alerts.filter((a) => !a.handled && a.kind !== 'guide').sort((a, b) => Number(b.kind === 'alarm') - Number(a.kind === 'alarm') || b.minutes - a.minutes);
  if (!open.length) return { tone: 'ok', title: '처리할 카드 없음' };
  const a = open[0];
  return { tone: a.kind === 'alarm' ? 'crit' : 'warn', title: `처리 필요 ${open.length}건 — ${a.machine} · ${a.code} ${a.name}`, desc: `${a.responsible ? `처리 책임: ${a.responsible} · ` : ''}${fmtElapsed(a.minutes)}`, action: '열기' };
}
export function cardBand(a: CardIn): BandSpec {
  if (a.handled) return { tone: 'ok', title: `${a.machine} · ${a.code} ${a.name} — 처리됨`, desc: [a.handledBy, a.handledAt].filter(Boolean).join(' · ') || undefined };
  return { tone: a.kind === 'alarm' ? 'crit' : 'warn', title: `${a.machine} · ${a.code} ${a.name} · ${fmtElapsed(a.minutes)}`, desc: [a.first ? `먼저: ${a.first}` : '', a.src ? `근거 ${a.src}` : ''].filter(Boolean).join(' · ') || undefined };
  // 버튼은 띠에 두지 않음 — 지침카드의 다음 단계 버튼 그대로 (안전 고정 서식 블록 위에 두지 않게)
}

// ---------------------------------------------------------------- 교대 보고서 (Reports ShiftReportScreen)
// r = reports/shift/{id} ({ status, actual_qty, target_qty, defect_qty }), hand = parseHandover 결과 [{ rank, items }], mandatoryStops = 필수 정지 건수
export const RANK_ORDER = ['0', '0-1', '1', '2', '3', '4'];
export const RANK_NAME: Record<string, string> = { '0': '안전', '0-1': '오래 방치', '1': '긴급', '2': '생산 위험', '3': '주의', '4': '참고' };
const RANK_TONE: Record<string, BandTone> = { '0': 'crit', '0-1': 'warn', '1': 'crit', '2': 'warn', '3': 'warn', '4': 'todo' };
export const NO_LOCKOUT_PREFIX = '잠금·표지 중인 설비 없음';
export function shiftBand(r: { status: string; actual_qty: number; target_qty: number; defect_qty?: number }, hand: { rank: string; items: string[] }[], mandatoryStops: number, confirmedText?: string): BandSpec {
  const pct = r.target_qty ? (r.actual_qty / r.target_qty) * 100 : null;
  const prod = `실적 ${fmtFrac(r.actual_qty, r.target_qty)} (${fmtPct(pct)}) · ${mandatoryStops ? `필수 정지 ${mandatoryStops}건` : '필수 정지 없음'}`;
  if (r.status !== 'CONFIRMED') return { tone: 'draft', title: '교대 보고서 — 확정 대기', desc: prod, action: '확정', actionLock: true };
  for (const k of RANK_ORDER.slice(0, 4)) { // 0 · 0-1 · 1 · 2 (3 주의 · 4 참고는 띠에 안 올림)
    const xs = (hand.find((g) => g.rank === k)?.items ?? []).filter((x) => !x.startsWith(NO_LOCKOUT_PREFIX));
    if (xs.length) return { tone: RANK_TONE[k], title: `인계 ${RANK_NAME[k]} ${xs.length}건 — ${xs[0].slice(0, 30)}`, desc: prod };
  }
  return pct != null && pct < 100
    ? { tone: 'warn', title: `실적 ${fmtFrac(r.actual_qty, r.target_qty)} — 목표 ${r.target_qty - r.actual_qty}개 모자람`, desc: prod }
    : { tone: 'ok', title: prod, desc: confirmedText };
}

// ---------------------------------------------------------------- 일일 보고서 (Reports DailyReportScreen)
export function dailyBand(r: { status: string; work_date: string; actual_qty: number; target_qty: number; oee_pct: number | null }, canConfirm: boolean, firstIssue?: string): BandSpec {
  const sum = `실적 ${fmtFrac(r.actual_qty, r.target_qty)} · OEE ${fmtPct(r.oee_pct)}`;
  const d = `${Number(r.work_date.slice(5, 7))}/${Number(r.work_date.slice(8, 10))}`;
  if (r.status !== 'CONFIRMED') return { tone: 'draft', title: `${d} 일일 보고서 — 확정 대기`, desc: sum, action: canConfirm ? '확정' : undefined, actionLock: true };
  return firstIssue ? { tone: 'warn', title: firstIssue.slice(0, 30), desc: sum } : { tone: 'ok', title: sum };
}

// ---------------------------------------------------------------- 문서함 목록 (DocBox) — 지금 "내 할 일" 접기를 띠로
export function docsBand(todos: { text: string }[], kindCount: number, firstName?: string): BandSpec {
  return todos.length
    ? { tone: 'todo', title: `확정 · 검토할 문서 ${todos.length}건`, desc: firstName ? `가장 오래된 것: ${firstName}` : todos[0].text, action: '첫 문서 열기' }
    : { tone: 'ok', title: `처리할 문서 없음 · 이 종류 ${fmtNum(kindCount)}건` };
}

// ---------------------------------------------------------------- 작업지시서 한 장 (WorkOrderScreen) — WoState = draft | editing | approved | inprogress | done | cancelled
export function woBand(w: { no: string; state: string; title: string; assigneeName?: string; steps: number; recordNo?: string }, canApprove: boolean): BandSpec {
  switch (w.state) {
    case 'draft': case 'editing': return { tone: 'draft', title: `${w.no} ${w.title}`, desc: '승인하면 담당 보전에게 갑니다', action: canApprove ? '승인' : undefined, actionLock: true, draftLabel: w.state === 'draft' ? 'AI비서 초안' : '수정 중' };
    case 'approved': return { tone: 'todo', title: `${w.no} 승인됨 — 작업 대기`, desc: `${w.assigneeName ?? '담당 미정'} · 작업 순서 ${w.steps}단계` };
    case 'inprogress': return { tone: 'todo', title: `${w.no} 진행 중`, desc: `${w.assigneeName ?? ''} · 작업 순서 ${w.steps}단계` };
    case 'done': return { tone: 'ok', title: `${w.no} 완료 — ${w.title}`, desc: w.recordNo ? `작업기록서 ${w.recordNo}` : undefined };
    default: return { tone: 'todo', title: `${w.no} 취소됨`, desc: w.title };
  }
}

// ---------------------------------------------------------------- 작업기록서 · 간이 작업기록 (WorkRecordScreen · SimpleRecordScreen)
// lock = 잠금·표지 체크 배열, state = WrState(draft | editing | confirmed | checked) 또는 간이 open | confirmed
export function recordBand(no: string, state: string, lock: boolean[], confirmedText?: string): BandSpec {
  const done = lock.filter(Boolean).length;
  if (state === 'confirmed' || state === 'checked') return { tone: 'ok', title: `${no} 확정`, desc: confirmedText };
  if (done < lock.length) return { tone: 'warn', title: `잠금 · 표지 체크 ${fmtFrac(done, lock.length)} — 확정하려면 ${lock.length - done}개 남았어요`, action: '체크로 가기' };
  return state === 'draft' ? { tone: 'draft', title: `${no} 작성 중`, desc: '확정하면 잠깁니다', action: '확정', actionLock: true } : { tone: 'todo', title: `${no} 확정할 수 있어요`, action: '확정', actionLock: true };
}

// ---------------------------------------------------------------- 다시 보기 (ReplayScreen) — 고른 시각
export function replayBand(atText: string, alarms: { level: '긴급' | '주의' | '참고'; text: string }[], running: number, total: number, fgQty: number, events: number): BandSpec {
  const desc = `가동 ${fmtFrac(running, total)}대 · 완제품 ${fmtQty(fgQty, '개')} · 사건 ${events}건`;
  const crit = alarms.find((a) => a.level === '긴급'), warn = alarms.find((a) => a.level === '주의');
  return crit ? { tone: 'crit', title: `${atText} — ${crit.text}`, desc } : warn ? { tone: 'warn', title: `${atText} — ${warn.text}`, desc } : { tone: 'ok', title: `${atText} — 켜진 알람 없음`, desc };
}

// ---------------------------------------------------------------- 현장 모니터 (작업자 태블릿, 구역별)
// eqs = 구역 설비 ({ name, state_code, alarm?: { level, text }, bottleneck })
export function fieldBand(zone: string, eqs: { name: string; state_code: string; alarm?: { level: '긴급' | '주의'; text: string }; bottleneck?: boolean }[]): BandSpec {
  const down = eqs.find((e) => e.state_code === 'DOWN' || e.state_code === 'BLOCKED' || e.alarm?.level === '긴급');
  const warn = eqs.find((e) => e.alarm?.level === '주의');
  const rest = (x?: { name: string }) => eqs.filter((e) => e !== x).map((e) => `${e.name} ${e.state_code === 'RUN' ? '가공 중' : '대기'}${e.bottleneck ? ' · 병목' : ''}`).join(' · ');
  if (down) return { tone: 'crit', title: `${zone} · ${down.name} ${down.state_code === 'BLOCKED' ? '막힘' : '고장'}${down.alarm ? ` — ${down.alarm.text}` : ''}`, desc: rest(down), action: '지침카드' };
  if (warn) return { tone: 'warn', title: `${zone} · ${warn.name} 주의 — ${warn.alarm!.text}`, desc: rest(warn), action: '지침카드' };
  return { tone: 'ok', title: `${zone} ${eqs.filter((e) => e.state_code === 'RUN').length}대 가공 중 · 알람 없음` };
}

// ---------------------------------------------------------------- 수정 이력 · 사내 문서 · 설정 (정보 띠)
export const revsBand = (last?: { at: string; doc: string; no: string; who: string; ver: string }): BandSpec =>
  last ? { tone: 'todo', title: `최근 수정 — ${last.at} ${last.doc} ${last.no}`, desc: `${last.who} · ${last.ver}` } : { tone: 'todo', title: '수정 기록 없음' };
export const idocBand = (d: { no: string; name: string; rev: string; approver: string; pending: number }): BandSpec =>
  d.pending ? { tone: 'todo', title: `개정 승인 대기 ${d.pending}건 — ${d.no}`, action: '승인', actionLock: true } : { tone: 'todo', title: `${d.no} ${d.name} · ${d.rev}`, desc: `승인 ${d.approver} · 개정 승인 대기 없음` };
export const settingsBand = (rules: { repeat_days: number; repeat_count: number; target_risk_pct: number }, unsaved: number): BandSpec =>
  unsaved ? { tone: 'todo', title: `저장하지 않은 변경 ${unsaved}개`, action: '저장' } : { tone: 'todo', title: `알림 기준 — 반복 알람 ${rules.repeat_days}일 안 ${rules.repeat_count}번 · 목표 미달 위험 ${rules.target_risk_pct}%`, desc: '바꾸면 다음 계산부터 적용' };

// ---------------------------------------------------------------- 직원 관리 (StaffScreen, SCR-27)
// onShift = 지금 근무 인원(서버 users[].on_shift), shiftName = "주간"·"야간"·null(근무 교대 없음), empty = 담당 0명 공정 칸 ("야간 OP-30"). 주의는 공정 담당 0명일 때만 (FR-USR-01-03)
export function staffBand(onShift: number, shiftName: string | null, empty: string[]): BandSpec {
  if (empty.length) return { tone: 'warn', title: `${empty[0]} 담당이 없어요${empty.length > 1 ? ` 외 ${empty.length - 1}칸` : ''}`, desc: '배치표에서 담당을 넣어 주세요', chips: empty, action: '배치 바꾸기' };
  return { tone: 'ok', title: shiftName ? `지금 ${shiftName} 근무 ${onShift}명 · 담당 없는 공정 없음` : '지금 근무 중인 교대 없음 · 담당 없는 공정 없음' };
}
