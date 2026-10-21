// 선택 말풍선(chips.ts) 시험 — 프레임워크 없이 Node 20으로 돈다 (carry_check.mjs 와 같은 방식).
//   실행: node 11_automotive/frontend/tools/chips_check.mjs     (frontend 폴더에서는 node tools/chips_check.mjs)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const js = ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/chips.ts', import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { suggestChips, defaultChips } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

t('카드를 안 열었으면 역할별 고정 말풍선 (작업자·반장 / 보전·관리자 두 가지), 2075·잠금 표지 고정 문구는 없다', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: false, alarmCode: '992' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'MNT', onCard: false }), defaultChips('MNT'));
  assert.equal(defaultChips('OPR').length, 4); assert.equal(defaultChips('MNT').length, 4); assert.deepEqual(defaultChips('SUP'), defaultChips('OPR')); assert.ok(defaultChips('MGR').includes('확정 안 된 교대 보고서 있어?'));
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) for (const x of [...defaultChips(role), ...suggestChips({ role, onCard: true, alarmCode: '992' })]) assert.ok(!x.includes('2075') && x !== '잠금 표지 순서', role + ': ' + x);
});
t('카드를 열었어도 번호 모양이 아니면(코드집에 없음 등) 고정 말풍선', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '알람 992' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: null }), defaultChips('OPR'));
});
t('역할마다 5개 이하(최대 6), 중복 없음, 번호 질문은 모두 번호로 시작', () => {
  for (const role of ['OPR', 'SUP', 'MNT', 'MGR']) {
    const c = suggestChips({ role, onCard: true, alarmCode: '992' });
    assert.ok(c.length >= 4 && c.length <= 6, role); assert.equal(new Set(c).size, c.length, role); assert.equal(c[0], '992 원인은', role);
  }
});
t('작업자는 지난 조치를 못 본다(정식 작업기록 권한) → 말풍선에 없다. 보전·반장·관리자는 있다', () => {
  assert.ok(!suggestChips({ role: 'OPR', onCard: true, alarmCode: '992' }).some((x) => x.includes('지난 조치')));
  for (const role of ['MNT', 'SUP', 'MGR']) assert.ok(suggestChips({ role, onCard: true, alarmCode: '992' }).includes('992 지난 조치'), role);
});
t('"내가 해야 할 일"은 작업자·반장만, 보전은 점검 순서', () => {
  assert.ok(suggestChips({ role: 'OPR', onCard: true, alarmCode: '992' }).includes('992 내가 해야 할 일'));
  assert.ok(suggestChips({ role: 'SUP', onCard: true, alarmCode: '992' }).includes('992 내가 해야 할 일'));
  assert.ok(suggestChips({ role: 'MNT', onCard: true, alarmCode: '992' }).includes('992 점검 순서'));
});
t('소수점 번호는 글자 그대로', () => {
  assert.equal(suggestChips({ role: 'OPR', onCard: true, alarmCode: '6302.00' })[0], '6302.00 원인은');
});

console.log(fail === 0 ? '\n모두 통과' : `\n실패 ${fail}개`);
process.exit(fail === 0 ? 0 : 1);
