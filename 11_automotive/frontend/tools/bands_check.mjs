// 결론 띠 함수 시험 — 프레임워크 없이 Node 20 (briefing_switch_check.mjs 와 같은 방식).
//   실행: node tools/bands_check.mjs   (frontend 폴더에서)
// src/shell/bands.ts · format.ts(의존 없는 순수 함수)를 typescript 패키지로 그 자리에서 변환해 불러온다.
// 시험 값은 10/1 시연 데이터 화면(공장 관리자, 오전)에서 실제로 보인 값.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const toJs = (name) => ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/' + name, import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const dataUrl = (js) => 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');
const fmtUrl = dataUrl(toJs('format.ts'));
const F = await import(fmtUrl);
const B = await import(dataUrl(toJs('bands.ts').replace(/from ['"]\.\/format['"]/, `from '${fmtUrl}'`)));

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

// ---- format
t('쉼표 · 단위 · % 1자리 · 분수', () => {
  assert.equal(F.fmtNum(1057), '1,057'); assert.equal(F.fmtQty(3.6, 'L'), '3.6 L'); assert.equal(F.fmtQty(400, '구멍'), '400 구멍');
  assert.equal(F.fmtPct(80), '80.0%'); assert.equal(F.fmtPct(104.444), '104.4%'); assert.equal(F.fmtPct(null), '—'); assert.equal(F.fmtFrac(47, 60), '47 / 60');
});
t('날짜 앞 0 없음 · 요일 · 경과', () => {
  assert.equal(F.fmtDate('2026-09-28T00:00:00+09:00'), '9/28'); assert.equal(F.fmtDate('2026-10-01', true), '10/1 (목)');
  assert.equal(F.fmtElapsed(13), '13분째'); assert.equal(F.fmtElapsed(99), '1시간 39분째'); assert.equal(F.fmtElapsed(120), '2시간째'); assert.equal(F.fmtElapsed(176), '2시간 56분째');
});

// ---- pickBand
t('겹치면 긴급 → 주의 → 초안 → 할 일 → 정상', () => {
  const b = B.pickBand([{ tone: 'ok', title: 'a' }, { tone: 'todo', title: 'b' }, { tone: 'warn', title: 'c' }, { tone: 'draft', title: 'd' }, 0, null]);
  assert.equal(b.title, 'c');
});

// ---- 재고 (10/1 10:53 화면)
const inv = [
  ['엔드밀 Ø10', '개', 15, 9], ['드릴 Ø5.0', '개', 8, 5], ['M6 탭', '개', 5, 8], ['보링바 인서트', '개', 5, 4], ['페이스밀 인서트', '개', 18, 14],
  ['축 윤활유', 'L', 3.6, 4], ['절삭유 원액', 'L', 31.3, 20], ['절삭유 필터', '개', 2, 2], ['공기 필터', '개', 2, 2], ['주축 윤활유', 'L', 7.6, 4], ['그리스', '개', 2, 2],
  ['6061-T6 봉재', '개분', 1057, 200], ['BRK-A100', '개', 175, 0],
].map(([item_name, unit, stock_qty, safety_stock]) => ({ item_name, unit, stock_qty, safety_stock, low: stock_qty <= safety_stock && safety_stock > 0 }));
t('재고: 안전 재고 이하 5품목, 가장 모자란 M6 탭 먼저', () => {
  const b = B.inventoryBand(inv, 0);
  assert.equal(b.tone, 'warn'); assert.equal(b.title, '안전 재고 이하 5품목');
  assert.equal(b.desc, 'M6 탭 5 / 8 개 · 축 윤활유 3.6 / 4 L 외 3품목'); assert.equal(b.action, '입고 등록');
});
t('재고: 다 넉넉하면 정상, 0이면 긴급', () => {
  assert.equal(B.inventoryBand(inv.map((i) => ({ ...i, stock_qty: i.safety_stock * 2 + 1, low: false })), 0).tone, 'ok');
  assert.equal(B.inventoryBand([{ ...inv[2], stock_qty: 0 }], 0).tone, 'crit');
});

// ---- 공구 (10:58 화면: 가장 많이 쓴 VF2-02 T05 80%)
t('공구: 90% 넘은 공구 없으면 정상 + 가장 많이 쓴 공구', () => {
  const b = B.toolsBand([{ equipment_id: 'VF2-02', tool_no: 'T05', label: 'M6 탭', usage_pct: 80, warn: false }, { equipment_id: 'VF2-01', tool_no: 'T03', label: '보링바 인서트', usage_pct: 73.2, warn: false }]);
  assert.equal(b.tone, 'ok'); assert.equal(b.desc, '가장 많이 쓴 공구: VF2-02 T05 M6 탭 80.0%'); assert.equal(b.action, undefined);
});
t('공구: 90% 넘으면 주의', () => { assert.equal(B.toolsBand([{ equipment_id: 'VF2-01', tool_no: 'T02', label: '엔드밀 Ø10', usage_pct: 95, warn: true }]).tone, 'warn'); });

// ---- 예방 정비 (12:00 화면)
t('예방 정비: 기한 지남 2건 — VF2-02 먼저', () => {
  const b = B.pmBand({ over: 2, soon: 6, week: 15 }, ['VF2-02'], 85.3);
  assert.equal(b.title, '기한 지남 2건 — VF2-02 먼저'); assert.equal(b.desc, '오늘 6건 · 9월 실시율 85.3% (목표 90%)'); assert.equal(b.action, 'VF2-02 보기');
});

// ---- 로트 (11:03 화면)
t('로트: 판정 대기 — 출하 금지', () => {
  const b = B.lotBand({ lot_no: 'LOT-2609-127-1', status: 'WAIT_JUDGEMENT', order_no: 'PO-2609-127', material_lot_no: 'MAT-2609-10', input_qty: 60 }, 47, 1);
  assert.equal(b.tone, 'warn'); assert.equal(b.title, 'LOT-2609-127-1 판정 대기 — 출하 금지'); assert.equal(b.desc, 'OP-50 판정 47 / 60 · 결정 필요 1건 (반장)');
  assert.deepEqual(b.chips, ['PO-2609-127', 'MAT-2609-10']);
});
t('로트: 합격 = 출하 가능, 안 고르면 할 일', () => {
  assert.equal(B.lotBand({ lot_no: 'L', status: 'PASSED', input_qty: 60 }, 60, 0).title, 'L 합격 — 출하 가능');
  assert.equal(B.lotBand(null, 0, 0).tone, 'todo');
  // 합격 로트에 불합격 1개 = 그 1개만 폐기, 띠는 빨강 아님 (LOT-2609-001-1 화면)
  const p = B.lotBand({ lot_no: 'L', status: 'PASSED', input_qty: 50 }, 50, 0, 1);
  assert.equal(p.tone, 'ok'); assert.equal(p.desc, 'OP-50 판정 50 / 50 · 불합격 1개 따로 폐기');
  assert.equal(B.lotBand({ lot_no: 'L', status: 'WAIT_JUDGEMENT', input_qty: 50 }, 50, 0, 1).tone, 'crit');
});

// ---- 검사 기록 (10:26 화면: 측정 9 / 60, 불합격 0)
t('검사 기록: 불합격 0이면 정상', () => {
  const states = [...Array(9).fill('pass'), ...Array(51).fill('wait')];
  const b = B.qualityBand('LOT-2609-127-1', states, { next: 'M6 입력' });
  assert.equal(b.tone, 'ok'); assert.equal(b.title, 'LOT-2609-127-1 측정 9 / 60 — 불합격 0');
});
t('검사 기록: 불합격이 있으면 긴급', () => { assert.equal(B.qualityBand('L', ['pass', 'fail', 'wait'], {}).tone, 'crit'); });

// ---- 공정 능력 (10:46 화면)
t('공정 능력: Cpk 미달 1항목 + 불량률', () => {
  const items = [{ item_name: '부싱 압입 구멍 지름', cpk: 1.66, cpk_min: 1.67 }, { item_name: '전체 길이', cpk: 2.13, cpk_min: 1.33 }, { item_name: '두께', cpk: 1.78, cpk_min: 1.33 }];
  const b = B.capBand(items, 60, { qty: 44, total: 4902 });
  assert.equal(b.tone, 'warn'); assert.equal(b.title, 'Cpk 기준 미달 1항목 — 부싱 압입 구멍 지름 1.66'); assert.equal(b.desc, '기준 1.67 · 불량률 0.9% (44 / 4,902)');
});
t('공정 능력: 50개 미만이면 계산 중', () => { assert.equal(B.capBand([], 12, { qty: 0, total: 12 }).title, 'Cpk 계산 중 (12 / 50)'); });

// ---- 지침카드 (11:34 화면)
const card = { machine: 'VF2-01', code: '362', name: '공구 수명 한계 도달', kind: 'warn', handled: false, minutes: 99, responsible: '작업자', first: '만료된 공구를 검사하고 필요하면 바꾼다', src: 'DOC-03 §2.13' };
t('지침카드 목록: 처리 필요 1건', () => {
  const b = B.cardsBand([card]);
  assert.equal(b.tone, 'warn'); assert.equal(b.title, '처리 필요 1건 — VF2-01 · 362 공구 수명 한계 도달'); assert.equal(b.desc, '처리 책임: 작업자 · 1시간 39분째');
});
t('지침카드: 정지 등급이 주의보다 먼저, 다 처리되면 정상', () => {
  assert.equal(B.cardsBand([card, { ...card, code: '992', kind: 'alarm', minutes: 3 }]).title.includes('992'), true);
  assert.equal(B.cardsBand([{ ...card, handled: true }]).tone, 'ok');
});
t('지침카드 한 장: 띠에 버튼 없음', () => { const b = B.cardBand(card); assert.equal(b.action, undefined); assert.equal(b.desc, '먼저: 만료된 공구를 검사하고 필요하면 바꾼다 · 근거 DOC-03 §2.13'); });

// ---- 교대 보고서 (9/30 야간)
const hand = [{ rank: '0', items: ['잠금·표지 중인 설비 없음'] }, { rank: '0-1', items: ['VF2-02 윤활유 저장소 양 점검·보충', 'VF2-02 주축 윤활 탱크 양 점검', 'VF2-02 알람 2075 7일 안 3번', 'M6 탭 안전 재고(8) 이하', '축 윤활유 안전 재고(4) 이하'] }, { rank: '3', items: ['VF2-01-T05 사용률 90% — 교체 준비'] }];
t('교대 보고서: 보고 순위 첫 항목(오래 방치 5건), 안전 "없음" 줄은 안 셈', () => {
  const b = B.shiftBand({ status: 'CONFIRMED', actual_qty: 94, target_qty: 90 }, hand, 0);
  assert.equal(b.tone, 'warn'); assert.equal(b.title, '인계 오래 방치 5건 — VF2-02 윤활유 저장소 양 점검·보충'); assert.equal(b.desc, '실적 94 / 90 (104.4%) · 필수 정지 없음');
});
t('교대 보고서: 미확정이면 초안 띠 + [확정]', () => { const b = B.shiftBand({ status: 'DRAFT', actual_qty: 41, target_qty: 90 }, [], 0); assert.equal(b.tone, 'draft'); assert.equal(b.actionLock, true); });
t('교대 보고서: 인계가 비고 목표 넘으면 정상', () => { assert.equal(B.shiftBand({ status: 'CONFIRMED', actual_qty: 94, target_qty: 90 }, [], 0).tone, 'ok'); });

// ---- 일일 · 문서함 · 작업지시서 · 작업기록서
t('일일 보고서: 9/30 확정 대기 (관리자만 버튼)', () => {
  const b = B.dailyBand({ status: 'DRAFT', work_date: '2026-09-30', actual_qty: 184, target_qty: 180, oee_pct: 67.8 }, true);
  assert.equal(b.title, '9/30 일일 보고서 — 확정 대기'); assert.equal(b.desc, '실적 184 / 180 · OEE 67.8%'); assert.equal(b.action, '확정');
  assert.equal(B.dailyBand({ status: 'DRAFT', work_date: '2026-09-30', actual_qty: 1, target_qty: 1, oee_pct: 1 }, false).action, undefined);
});
t('문서함: 할 일 2건 / 없으면 정상', () => {
  assert.equal(B.docsBand([{ text: 'a' }, { text: 'b' }], 53, '9/30 일일 보고서 (AI비서 초안)').title, '확정 · 검토할 문서 2건');
  assert.equal(B.docsBand([], 53).title, '처리할 문서 없음 · 이 종류 53건');
});
t('작업지시서: 상태별 띠', () => {
  assert.equal(B.woBand({ no: 'MW-0950', state: 'draft', title: 'x', steps: 5 }, true).tone, 'draft');
  assert.equal(B.woBand({ no: 'MW-0904', state: 'done', title: 'VF2-02 알람 108 반복 원인 점검', steps: 3 }, false).title, 'MW-0904 완료 — VF2-02 알람 108 반복 원인 점검');
});
t('작업기록서: 잠금·표지 7 / 9 이면 주의', () => {
  const b = B.recordBand('MR-0950', 'editing', [true, true, true, true, true, true, true, false, false]);
  assert.equal(b.tone, 'warn'); assert.equal(b.title, '잠금 · 표지 체크 7 / 9 — 확정하려면 2개 남았어요');
});

// ---- 다시 보기 · 현장 · 설정
t('다시 보기: 알람 없으면 정상', () => { const b = B.replayBand('10/1 11:34', [], 3, 6, 37, 1); assert.equal(b.title, '10/1 11:34 — 켜진 알람 없음'); assert.equal(b.desc, '가동 3 / 6대 · 완제품 37 개 · 사건 1건'); });
t('현장 모니터: 고장이 주의보다 먼저', () => {
  const b = B.fieldBand('3공정', [{ name: 'VF2-01', state_code: 'RUN', alarm: { level: '주의', text: '공구 수명 한계 도달' } }, { name: 'VF2-02', state_code: 'DOWN' }]);
  assert.equal(b.tone, 'crit');
});
t('설정: 기본 알림 기준 문장', () => { assert.equal(B.settingsBand({ repeat_days: 7, repeat_count: 3, target_risk_pct: 90 }, 0).title, '알림 기준 — 반복 알람 7일 안 3번 · 목표 미달 위험 90%'); });
t('직원 관리: 빈 공정이면 주의, 없으면 근무 인원', () => {
  const w = B.staffBand(6, '주간', ['야간 OP-20', '야간 OP-30']);
  assert.equal(w.tone, 'warn'); assert.equal(w.title, '야간 OP-20 담당이 없어요 외 1칸');
  assert.equal(B.staffBand(6, '주간', []).title, '지금 주간 근무 6명 · 담당 없는 공정 없음');
  assert.equal(B.staffBand(0, null, []).title, '지금 근무 중인 교대 없음 · 담당 없는 공정 없음');
});

if (fail) { console.log(`\n${fail}개 실패`); process.exit(1); }
console.log('\n전부 통과');
