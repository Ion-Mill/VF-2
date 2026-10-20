// 알림 탭 알람 상세 본문 문장 함수 시험 — 프레임워크 없이 Node 20으로 돈다 (carry_check.mjs 와 같은 방식).
//   실행: node 11_automotive/frontend/tools/alarm_text_check.mjs     (frontend 폴더에서는 node tools/alarm_text_check.mjs)
// src/shell/alarmText.ts(의존 없는 순수 함수)를 typescript 패키지로 그 자리에서 변환해 불러온다 — 빌드·설치 없음.
// 지키는 것: 이 함수의 결과가 비서 연결 전의 Eve.tsx 상세 본문(JSX 조각 이어 붙이기)과 글자 하나까지 같다 → 비서가 꺼져 있거나 실패해도 화면 글자가 그대로다.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const toJs = (name) => ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/' + name, import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { alarmSentence } = await import('data:text/javascript;base64,' + Buffer.from(toJs('alarmText.ts')).toString('base64'));

// 비서 연결 전 Eve.tsx 171행의 표현을 그대로 옮긴 것 (sevText·hhmm 포함). JSX 글자 `{a}.{b}`는 사이에 아무것도 안 넣고 이어 붙인다.
const sevText = (s) => (s === 'STOP' ? '정지' : s === 'WARN' ? '주의' : '조작 안내');
const legacy = ({ name, op, code, severity, scenario, lot, cleared }) =>
  `${name}(${op})에서 알람 ${code}${severity ? ` — ${sevText(severity)}` : ' — 알람 코드집에 없음, 보전 담당자 호출'}.${scenario ? ` 사건 ${scenario}.` : ''}${lot ? ` 로트 ${lot}.` : ''}${cleared ? ` 설비 알람 ${cleared} 해제.` : ''}`;

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };
const base = { name: 'VF2-01', op: 'OP-30', code: '992', severity: 'STOP', scenario: null, lot: null, cleared: null };

t('가장 짧은 문장: 설비·공정·번호·심각도만', () => { assert.equal(alarmSentence(base), 'VF2-01(OP-30)에서 알람 992 — 정지.'); });
t('사건·로트·해제가 모두 있으면 이 순서로 이어진다', () => {
  assert.equal(alarmSentence({ ...base, scenario: 'S1', lot: 'LOT-2610-001-1', cleared: '09:20' }), 'VF2-01(OP-30)에서 알람 992 — 정지. 사건 S1. 로트 LOT-2610-001-1. 설비 알람 09:20 해제.');
});
t('심각도 세 가지 낱말: 정지 / 주의 / 조작 안내', () => {
  assert.equal(alarmSentence({ ...base, severity: 'STOP' }), 'VF2-01(OP-30)에서 알람 992 — 정지.');
  assert.equal(alarmSentence({ ...base, severity: 'WARN' }), 'VF2-01(OP-30)에서 알람 992 — 주의.');
  assert.equal(alarmSentence({ ...base, severity: 'GUIDE' }), 'VF2-01(OP-30)에서 알람 992 — 조작 안내.');
});
t('알람 코드집에 없으면 "알람 코드집에 없음, 보전 담당자 호출"', () => {
  assert.equal(alarmSentence({ ...base, code: '9999', severity: null, lot: 'LOT-2610-001-1' }), 'VF2-01(OP-30)에서 알람 9999 — 알람 코드집에 없음, 보전 담당자 호출. 로트 LOT-2610-001-1.');
});
t('빈 문자열 사건·로트(생성기 과거 기록)는 없는 것으로 본다', () => { assert.equal(alarmSentence({ ...base, scenario: '', lot: '' }), 'VF2-01(OP-30)에서 알람 992 — 정지.'); });
t('영문 섞인 알람 번호·소수점 번호도 그대로', () => {
  assert.equal(alarmSentence({ ...base, code: 'TempComp-202', severity: 'WARN' }), 'VF2-01(OP-30)에서 알람 TempComp-202 — 주의.');
  assert.equal(alarmSentence({ ...base, code: '6302.00', severity: 'GUIDE' }), 'VF2-01(OP-30)에서 알람 6302.00 — 조작 안내.');
});
t('예전 화면 문장과 모든 조합에서 글자가 같다 (설비 6 × 심각도 4 × 사건 2 × 로트 2 × 해제 2 = 192가지)', () => {
  let n = 0;
  for (const [name, op] of [['SAW-01', 'OP-10'], ['MIL-01', 'OP-20'], ['VF2-01', 'OP-30'], ['VF2-02', 'OP-30'], ['WSH-01', 'OP-40'], ['CMM-01', 'OP-50']])
    for (const severity of ['STOP', 'WARN', 'GUIDE', null])
      for (const scenario of [null, 'S4'])
        for (const lot of [null, 'LOT-2609-127-1'])
          for (const cleared of [null, '17:03']) {
            const a = { name, op, code: '2075', severity, scenario, lot, cleared };
            assert.equal(alarmSentence(a), legacy(a)); n++;
          }
  assert.equal(n, 192);
});

if (fail) { console.log(`\n${fail}개 실패`); process.exit(1); }
console.log('\n전부 통과');
