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

t('카드를 안 열었으면 예전 고정 말풍선 그대로 (역할별 2가지)', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: false, alarmCode: '992' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'MNT', onCard: false }), defaultChips('MNT'));
  assert.equal(defaultChips('OPR')[0], '2075 알람 뭐야');
});
t('카드를 열었어도 번호 모양이 아니면(코드집에 없음 등) 예전 말풍선', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '알람 992' }), defaultChips('OPR'));
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: null }), defaultChips('OPR'));
});
t('작업자: 원인·먼저 할 일·내가 해야 할 일·잠금 표지 — 앞의 셋에 번호가 들어간다', () => {
  assert.deepEqual(suggestChips({ role: 'OPR', onCard: true, alarmCode: '992' }), ['992 원인은', '992 먼저 할 일', '992 내가 해야 할 일', '잠금 표지 순서']);
});
t('보전 담당자는 점검 순서·지난 조치, 반장은 내가 해야 할 일·지난 조치, 관리자는 화면 설명', () => {
  assert.deepEqual(suggestChips({ role: 'MNT', onCard: true, alarmCode: '992' }), ['992 원인은', '992 점검 순서', '992 지난 조치', '잠금 표지 순서']);
  assert.deepEqual(suggestChips({ role: 'SUP', onCard: true, alarmCode: '992' }), ['992 원인은', '992 먼저 할 일', '992 내가 해야 할 일', '992 지난 조치']);
  assert.deepEqual(suggestChips({ role: 'MGR', onCard: true, alarmCode: '992' }), ['992 원인은', '992 먼저 할 일', '992 지난 조치', '이 화면 설명해 줘']);
});
t('소수점 번호는 글자 그대로, 항상 4개', () => {
  const c = suggestChips({ role: 'OPR', onCard: true, alarmCode: '6302.00' });
  assert.equal(c.length, 4); assert.equal(c[0], '6302.00 원인은');
});

console.log(fail === 0 ? '\n모두 통과' : `\n실패 ${fail}개`);
process.exit(fail === 0 ? 0 : 1);
