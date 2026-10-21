// 선택 말풍선(chips.ts) 시험 — 프레임워크 없이 Node 20으로 돈다 (carry_check.mjs 와 같은 방식).
//   실행: node 11_automotive/frontend/tools/chips_check.mjs     (frontend 폴더에서는 node tools/chips_check.mjs)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const js = ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/chips.ts', import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { suggestChips, defaultChips, SCREEN_EXPLAIN } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

t('카드를 안 열었으면 역할별 고정 말풍선, 2075·잠금 표지 고정 문구는 없다', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: false, alarmCode: '992' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'MNT', onCard: false }), defaultChips('MNT'));
  assert.equal(defaultChips('OPR').length, 0); assert.equal(defaultChips('MNT').length, 2); assert.equal(defaultChips('SUP').length, 2);
  assert.ok(defaultChips('SUP').includes('병목 원인') && defaultChips('SUP').includes('확정 안 된 교대 보고서 있어?'));
  assert.ok(!defaultChips('MNT').includes('확정 안 된 교대 보고서 있어?'));
  assert.ok(defaultChips('MGR').includes('확정 안 된 교대 보고서 있어?'));
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) assert.ok(!defaultChips(role, 'line').includes('어제 주간 교대 보고서 작성됐어?'), role);
  assert.ok(!defaultChips('OPR').includes(SCREEN_EXPLAIN) && !defaultChips('MNT').includes(SCREEN_EXPLAIN));
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) for (const x of [...defaultChips(role), ...suggestChips({ role, onCard: true, alarmCode: '992', screen: 'card' })]) assert.ok(!x.includes('2075') && x !== '잠금 표지 순서', role + ': ' + x);
});
t('카드를 열었어도 번호 모양이 아니면(코드집에 없음 등) 고정 말풍선', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '', screen: 'card' }), defaultChips('OPR', 'card'));
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '알람 992', screen: 'card' }), defaultChips('OPR', 'card'));
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: null, screen: 'card' }), defaultChips('OPR', 'card'));
  assert.ok(defaultChips('OPR', 'card').includes(SCREEN_EXPLAIN));
});
t('역할마다 3~6개, 중복 없음, 첫 질문은 그 알람 번호로 시작', () => {
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) {
    const c = suggestChips({ role, onCard: true, alarmCode: '992', screen: 'card' });
    assert.ok(c.length >= 3 && c.length <= 6, role); assert.equal(new Set(c).size, c.length, role); assert.equal(c[0], '992 원인은', role);
  }
});
t('횟수·지난 조치 말풍선은 어느 역할에도 없다', () => {
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) {
    const c = suggestChips({ role, onCard: true, alarmCode: '992', screen: 'card' });
    assert.ok(!c.some((x) => x.includes('지난 조치') || x.includes('최근 몇 번')), role + ': ' + c.join(' | '));
  }
});
t('"내가 해야 할 일"은 작업자·반장만, 보전은 점검 순서', () => {
  assert.ok(suggestChips({ role: 'OPR', onCard: true, alarmCode: '992', screen: 'card' }).includes('992 내가 해야 할 일'));
  assert.ok(suggestChips({ role: 'SUP', onCard: true, alarmCode: '992', screen: 'card' }).includes('992 내가 해야 할 일'));
  assert.ok(suggestChips({ role: 'MNT', onCard: true, alarmCode: '992', screen: 'card' }).includes('992 점검 순서'));
  assert.ok(!suggestChips({ role: 'MGR', onCard: true, alarmCode: '992', screen: 'card' }).includes('내가 해야 할 일'));
});
t('이 화면 설명해 줘는 정보판이 있는 화면에서만 (라인 현황·지침카드·일일 보고)', () => {
  for (const screen of ['line', 'daily', 'card', 'cards']) {
    for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) assert.ok(defaultChips(role, screen).includes(SCREEN_EXPLAIN), role + ' ' + screen);
  }
  for (const screen of ['shift', 'settings', 'wo', 'field', 'stops', 'quality', 'inventory']) {
    for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) {
      assert.ok(!suggestChips({ role, onCard: false, screen }).includes(SCREEN_EXPLAIN), role + ' ' + screen);
    }
  }
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) {
    assert.ok(suggestChips({ role, onCard: true, alarmCode: '992', screen: 'card' }).includes(SCREEN_EXPLAIN), role);
    assert.ok(suggestChips({ role, onCard: true, alarmCode: '992', screen: 'cards' }).includes(SCREEN_EXPLAIN), role);
    assert.ok(!suggestChips({ role, onCard: true, alarmCode: '992' }).includes(SCREEN_EXPLAIN), role);
  }
  assert.equal(defaultChips('OPR', 'line').length, 1);
  assert.equal(defaultChips('MNT', 'daily').length, 3);
  for (const screen of [null, 'line', 'card', 'daily', 'shift']) {
    for (const x of [...defaultChips('OPR', screen), ...suggestChips({ role: 'OPR', onCard: true, alarmCode: '992', screen })]) {
      assert.ok(!x.includes('병목') && !x.includes('확정 안 된'), screen + ': ' + x);
    }
  }
});
t('소수점 번호는 글자 그대로', () => {
  assert.equal(suggestChips({ role: 'OPR', onCard: true, alarmCode: '6302.00' })[0], '6302.00 원인은');
});

console.log(fail === 0 ? '\n모두 통과' : `\n실패 ${fail}개`);
process.exit(fail === 0 ? 0 : 1);
