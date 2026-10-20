// 브리핑 "먼저 챙길 일" 체크 저장 시험 — 프레임워크 없이 Node 20으로 돈다 (briefing_switch_check.mjs 와 같은 방식).
//   실행: node 11_automotive/frontend/tools/brief_checks_check.mjs     (frontend 폴더에서는 node tools/brief_checks_check.mjs)
// src/shell/briefChecks.ts(의존 없는 순수 함수)를 typescript 패키지로 그 자리에서 변환해 불러온다 — 빌드·설치 없음.
// 지키는 것: ① 체크 후 닫았다 다시 열어도(저장 → 읽기) 같은 체크가 남는다 ② 사용자·교대·시연 회차가 다르면 서로 안 섞인다
// ③ 서버 글자는 백엔드 길이 제한 안이다 ④ 모양이 틀린 서버 응답은 쓰지 않는다
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const toJs = (name) => ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/' + name, import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { checkScope, serverShift, serverKey, fromServerKeys, toggleKey, itemKeysOf, SHIFT_MAX, KEY_MAX } = await import('data:text/javascript;base64,' + Buffer.from(toJs('briefChecks.ts')).toString('base64'));

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

// 화면이 쓰는 저장소를 흉내: 칸 → 체크한 항목 목록 (usePersist 의 localStorage 와 같은 모양)
const store = {};
const click = (user, shift, key) => { const s = checkScope(user, shift); store[s] = toggleKey(store[s] ?? [], key); };
const open = (user, shift) => store[checkScope(user, shift)] ?? [];

t('체크하면 목록에 더해지고 다시 누르면 빠진다 (원래 목록은 그대로)', () => {
  const a = ['x'];
  assert.deepEqual(toggleKey(a, 'y'), ['x', 'y']);
  assert.deepEqual(toggleKey(['x', 'y'], 'x'), ['y']);
  assert.deepEqual(a, ['x']);
});
t('체크한 뒤 패널을 닫았다 다시 열어도 같은 체크가 남는다 (N/N)', () => {
  const keys = ['lock', 'a-12', 'pm:PM-VF2-01-2.1-01', 'ho3-0'];
  keys.forEach((k) => click('U10', '2026-10-01-D', k));
  const back = open('U10', '2026-10-01-D');
  assert.equal(keys.filter((k) => back.includes(k)).length, keys.length);
});
t('다른 사용자·다른 교대의 체크는 안 보인다', () => {
  assert.deepEqual(open('U08', '2026-10-01-D'), []);
  assert.deepEqual(open('U10', '2026-10-01-N'), []);
});
t('서버 글자: 시연 회차가 다르면 서로 안 섞인다', () => {
  const sent = [serverKey(1, 'lock'), serverKey(1, 'a-12'), serverKey(2, 'lock')];
  assert.deepEqual(fromServerKeys(1, sent), ['lock', 'a-12']);
  assert.deepEqual(fromServerKeys(2, sent), ['lock']);
  assert.deepEqual(fromServerKeys(null, sent), []);                 // 회차를 모르면(null=0) 1·2회차 것은 안 가져온다
});
t('서버 글자는 보낸 것을 그대로 되돌려 읽는다', () => {
  for (const run of [0, 1, 37]) for (const k of ['lock', 'pm:PM-VF2-01-2.1-01', 'ho0-1-2', '한글 항목']) assert.deepEqual(fromServerKeys(run, [serverKey(run, k)]), [k]);
});
t('서버 글자는 백엔드 길이 제한 안이다', () => {
  assert.ok(serverShift(12, '2026-10-01-D').length <= SHIFT_MAX);
  assert.ok(serverKey(12, 'x'.repeat(500)).length <= KEY_MAX);
  assert.ok(serverShift(12, 'y'.repeat(500)).length <= SHIFT_MAX);
});
t('서버 응답: 항목 글자만 뽑고, 모양이 틀리면 null', () => {
  assert.deepEqual(itemKeysOf({ shift_id: 's', items: [{ item_key: 'a', checked_at: 't' }, { item_key: 'b' }] }), ['a', 'b']);
  assert.deepEqual(itemKeysOf({ items: [] }), []);
  for (const bad of [null, undefined, 'x', {}, { items: 'x' }, [], { detail: 'err' }]) assert.equal(itemKeysOf(bad), null, JSON.stringify(bad));
  assert.deepEqual(itemKeysOf({ items: [null, { item_key: 3 }, { item_key: 'ok' }] }), ['ok']);
});
t('서버 응답에 앞 글자가 없는 값·빈 값은 버린다', () => {
  assert.deepEqual(fromServerKeys(1, ['lock', 'r1/', 'r1/ok', 3, null]), ['ok']);
  assert.deepEqual(fromServerKeys(1, 'x'), []);
});

if (fail) { console.log(`\n${fail}개 실패`); process.exit(1); }
console.log('\n전부 통과');
