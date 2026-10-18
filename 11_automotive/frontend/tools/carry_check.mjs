// "직전 알람 이어받기" 신호 함수 시험 — 프레임워크 없이 Node 20으로 돈다 (chat_log_check.mjs 와 같은 방식).
//   실행: node 11_automotive/frontend/tools/carry_check.mjs     (frontend 폴더에서는 node tools/carry_check.mjs)
// src/shell/carry.ts(React 없는 순수 함수)와 그가 읽는 assistantStatus.ts 를 typescript 패키지로 그 자리에서 변환해 불러온다 — 빌드·설치 없음.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const toJs = (name) => ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/' + name, import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const dataUrl = (js) => 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');

const statusUrl = dataUrl(toJs('assistantStatus.ts'));
const carryJs = toJs('carry.ts').replace(/(from\s+)(['"])\.\/assistantStatus\2/, `$1${JSON.stringify(statusUrl)}`);
const { carryAlarm, buildAskContext } = await import(dataUrl(carryJs));
const { STATUS_KO } = await import(statusUrl);

const OK = STATUS_KO.OK;
const row = (q, a = '', status = OK) => ({ q, a, status });
const one = (q, a) => carryAlarm([row(q, a)]);

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

// ---- 질문에서 뽑기: 번호 하나
t('질문에 번호 하나: "2075 알람 뭐야" → 2075', () => { assert.equal(one('2075 알람 뭐야', ''), '2075'); });
t('알람 낱말이 앞에 와도 된다: "알람 2075" → 2075', () => { assert.equal(one('알람 2075', ''), '2075'); });
t('소수점 번호는 글자 그대로: "6302.00 경보 뭐야" → "6302.00"', () => { assert.equal(one('6302.00 경보 뭐야', ''), '6302.00'); });
t('"번"이 끼어도 된다: "992번 알람", "992번 경보" → 992', () => { assert.equal(one('992번 알람', ''), '992'); assert.equal(one('992번 경보 점검 순서', ''), '992'); });
t('"알람번호 254" → 254, 5자리 "25050 알람" → 25050', () => { assert.equal(one('알람번호 254', ''), '254'); assert.equal(one('25050 알람 뭐야', ''), '25050'); });
t('같은 번호가 질문에 두 번 나오면 하나로 센다', () => { assert.equal(one('2075 알람이 2075 알람이야?', ''), '2075'); });

// ---- 질문에 번호가 둘 이상이면 보내지 않는다 (답을 보지도 않는다)
t('질문에 서로 다른 번호 둘: "2075랑 992 알람 차이" → null', () => { assert.equal(one('2075랑 992 알람 차이', ''), null); });
t('"랑·와·하고·쉼표"로 이어진 번호도 함께 센다 → null', () => { for (const q of ['2075와 992 알람 차이', '알람 2075, 992 뭐가 달라', '992 경보하고 2075 경보', '2075/992 알람 비교', '2075랑 992랑 5303 알람']) assert.equal(one(q, ''), null, q); });
t('이어진 말이 없으면 떨어진 숫자는 따라오지 않는다: "2075 알람 5분 뒤 992 에서" → 2075', () => { assert.equal(one('2075 알람 5분 뒤 992 에서', ''), '2075'); });
t('"2075 알람이랑 992 알람 차이" → null',() => { assert.equal(one('2075 알람이랑 992 알람 차이', '알람 5303.00'), null); });
t('질문이 둘이라 null 이면 답에 하나뿐이어도 답으로 넘어가지 않는다', () => { assert.equal(one('2075 알람이랑 992 알람 차이', '알람 6302.00 설명'), null); });

// ---- 질문에 0개 → 답에서
t('질문 0개·답에 하나 → 그 번호', () => { assert.equal(one('원인은?', '2075 알람은 비상정지 입니다.'), '2075'); });
t('질문 0개·답에 소수점 번호 하나 → 글자 그대로', () => { assert.equal(one('이 알람 뭐야', '알람 6302.00 (안전 도어 열림)'), '6302.00'); });
t('질문 0개·답에 같은 번호가 두 번 → 그 번호', () => { assert.equal(one('원인은?', '알람 2075 입니다. 2075 알람이 뜨면 멈춥니다.'), '2075'); });
t('질문 0개·답에 서로 다른 번호 둘 → null', () => { assert.equal(one('원인은?', '2075 알람과 992 알람이 함께 뜹니다.'), null); });
t('질문도 답도 0개 → null', () => { assert.equal(one('원인은?', '확인할 수 없습니다.'), null); });

// ---- 알람 번호가 아닌 숫자
t('"7일 3번"·"30일 10번"·"5분 대기"만 있는 답 → null', () => { assert.equal(one('이건?', '7일 3번 점검하고 30일 10번 기록합니다. 5분 대기하세요.'), null); });
t('알람 낱말과 떨어진 숫자는 번호가 아니다: "알람이 뜨면 100번 눌러" → null', () => { assert.equal(one('이건?', '알람이 뜨면 100번 눌러 주세요'), null); });
t('모양이 맞지 않는 숫자는 번호로 세지 않는다: 두 자리·여섯 자리 이상·소수점 한 자리', () => { assert.equal(one('12 알람', ''), null); assert.equal(one('123456 알람', ''), null); assert.equal(one('6302.0 알람', ''), null); });
t('번호 하나와 시간 숫자가 섞이면 번호만 센다: "알람 992 후 5분 대기, 7일 3번" → 992', () => { assert.equal(one('이건?', '알람 992 후 5분 대기, 7일 3번'), '992'); });

// ---- 마지막 줄만 본다
t('빈 줄 목록 → null', () => { assert.equal(carryAlarm([]), null); });
t('마지막 줄이 정상 답이 아니면 null (문서에 없음·권한 밖·거부·응답 없음)', () => {
  for (const k of ['NOT_IN_DOCS', 'OUT_OF_ROLE', 'REFUSED', 'NO_RESPONSE']) assert.equal(carryAlarm([row('2075 알람 뭐야', '', STATUS_KO[k])]), null, k);
});
t('상태가 비었거나 처음 보는 값이어도 null (표지 줄·옛 기록)', () => { assert.equal(carryAlarm([row('2075 알람 뭐야', '', '')]), null); assert.equal(carryAlarm([row('2075 알람 뭐야', '', 'ok')]), null); });
t('줄이 여러 개여도 마지막 줄만 본다 (앞 줄의 번호는 무시)', () => {
  assert.equal(carryAlarm([row('2075 알람 뭐야'), row('원인은?', '설명')]), null);
  assert.equal(carryAlarm([row('원인은?', '992 알람 설명'), row('992 알람 뭐야')]), '992');
});
t('앞 줄이 비정상이어도 마지막 줄이 정상이면 뽑는다', () => { assert.equal(carryAlarm([row('아무거나', '', STATUS_KO.NOT_IN_DOCS), row('2075 알람 뭐야')]), '2075'); });
t('마지막 줄이 비정상이면 앞 줄이 정상이어도 null', () => { assert.equal(carryAlarm([row('2075 알람 뭐야'), row('왜?', '', STATUS_KO.NO_RESPONSE)]), null); });
t('표지 줄(질문·답·상태가 빈 줄)만 있어도 안전하다', () => { assert.equal(carryAlarm([{ q: '', a: '', status: '' }]), null); });

// ---- buildAskContext
t('빈 입력 → {}', () => { assert.deepEqual(buildAskContext({}), {}); });
t('네 칸 모두 → 네 칸', () => { assert.deepEqual(buildAskContext({ screenCode: 'SCR-04', equipmentId: 'VF2-01', alarmKey: '2075', newChat: true }), { screen: 'SCR-04', equipment_id: 'VF2-01', alarm_key: '2075', new_chat: '1' }); });
t('newChat: false → new_chat 없음', () => { assert.deepEqual(buildAskContext({ screenCode: 'SCR-04', newChat: false }), { screen: 'SCR-04' }); assert.equal('new_chat' in buildAskContext({ newChat: false }), false); });
t('null·빈 글자·undefined 는 칸을 만들지 않는다', () => { assert.deepEqual(buildAskContext({ screenCode: null, equipmentId: '', alarmKey: null, newChat: undefined }), {}); });
t('옵션 없는 옛 호출과 같은 context: 화면·설비 두 칸만', () => { assert.deepEqual(buildAskContext({ screenCode: 'SCR-09', equipmentId: 'VF2-02' }), { screen: 'SCR-09', equipment_id: 'VF2-02' }); });

console.log(fail ? `\n${fail}개 실패` : '\n전부 통과');
process.exit(fail ? 1 : 0);
