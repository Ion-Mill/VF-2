// 브리핑 "먼저 챙길 일" 비서 정리 스위치 시험 — 프레임워크 없이 Node 20으로 돈다 (alarm_text_check.mjs 와 같은 방식).
//   실행: node 11_automotive/frontend/tools/briefing_switch_check.mjs     (frontend 폴더에서는 node tools/briefing_switch_check.mjs)
// src/shell/briefingSwitch.ts(의존 없는 순수 함수)를 typescript 패키지로 그 자리에서 변환해 불러온다 — 빌드·설치 없음.
// 지키는 것: ① 꺼짐(기본)이면 키가 '' 라서 useBriefingText 가 비서를 한 번도 묻지 않는다 ② 켜짐이면 키가 예전 코드와 글자까지 같다(되돌릴 수 있음).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const toJs = (name) => ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/' + name, import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { briefingLlmOn, briefingAskKey } = await import('data:text/javascript;base64,' + Buffer.from(toJs('briefingSwitch.ts')).toString('base64'));

// 스위치를 넣기 전 assistText.ts useBriefingText 의 키 식을 그대로 옮긴 것
const legacyKey = (shift, groups) => (shift && groups.length ? JSON.stringify([shift, groups]) : '');

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };
const groups = [{ rank: '3', lines: ['[재고 부족] 축 윤활유 재고 3.6L — 안전 재고 4L 이하'] }, { rank: '4', lines: ['[예방 정비 기한 하루 전] VF2-01 절삭유 양 점검 — 기한 10/3'] }];

t('환경변수가 없거나 1이 아니면 꺼짐', () => { for (const v of [undefined, '', '0', 'true', 'on', ' 1']) assert.equal(briefingLlmOn(v), false, String(v)); });
t('환경변수가 1이면 켜짐', () => { assert.equal(briefingLlmOn('1'), true); });
t('꺼짐이면 줄이 있어도 키가 빈 글 — 비서를 묻지 않는다', () => { assert.equal(briefingAskKey(false, '2026-10-01-D', groups), ''); });
t('켜짐이면 예전 코드와 같은 키', () => { assert.equal(briefingAskKey(true, '2026-10-01-D', groups), legacyKey('2026-10-01-D', groups)); });
t('켜져도 교대가 없거나 줄이 없으면 빈 글', () => {
  assert.equal(briefingAskKey(true, undefined, groups), '');
  assert.equal(briefingAskKey(true, '2026-10-01-D', []), '');
});

if (fail) { console.log(`\n${fail}개 실패`); process.exit(1); }
console.log('\n전부 통과');
