// "새 채팅" 판정 함수 시험 — 프레임워크 없이 Node 20으로 돈다 (이 화면 폴더에는 시험 도구가 없다).
//   실행: node 11_automotive/frontend/tools/chat_log_check.mjs     (frontend 폴더에서는 node tools/chat_log_check.mjs)
// src/shell/chatLog.ts(React 없는 순수 함수)를 typescript 패키지로 그 자리에서 변환해 불러온다 — 빌드·설치 없음.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const file = fileURLToPath(new URL('../src/shell/chatLog.ts', import.meta.url));
const js = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { currentChat, realRows, canStartNewChat, withNewChat, makeNewChatMark, mergeServerLog, lastChatId } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

const T = '2026-10-01T10:00:00+09:00';
const row = (q, at = T) => ({ at, q, a: '답 ' + q, status: 'ok', sources: [] });
const mark = (at = T) => makeNewChatMark(at);
const qs = (rows) => rows.map((r) => r.q);

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

// ---- 지금 대화 = 마지막 표지 뒤의 줄
t('기록이 비어 있어도 안전하다', () => { assert.deepEqual(currentChat([]), []); assert.deepEqual(realRows([]), []); assert.equal(canStartNewChat([], false), false); });
t('표지가 없으면(옛 기록) 전체가 지금 대화다', () => { assert.deepEqual(qs(currentChat([row('a'), row('b')])), ['a', 'b']); });
t('표지 뒤 줄만 지금 대화다', () => { assert.deepEqual(qs(currentChat([row('a'), row('b'), mark(), row('c')])), ['c']); });
t('표지가 맨 끝이면 지금 대화는 비어 있다', () => { assert.deepEqual(currentChat([row('a'), mark()]), []); });
t('표지가 여러 개면 마지막 표지 뒤', () => { assert.deepEqual(qs(currentChat([row('a'), mark(), row('b'), mark(), row('c'), row('d')])), ['c', 'd']); });
t('시뮬레이터 시계가 멈춰 시각이 모두 같아도 정확하다', () => { assert.deepEqual(qs(currentChat([row('a', T), mark(T), row('b', T)])), ['b']); });

// ---- 질문·답이 있는 줄만 (채팅 기록 탭·하루치 보기)
t('표지는 기록 목록에서 빠지고 순서는 그대로다', () => { assert.deepEqual(qs(realRows([row('a'), mark(), row('b'), mark(), row('c')])), ['a', 'b', 'c']); });
t('표지 줄은 질문·답이 비어 있다', () => { const m = mark(); assert.equal(m.newChat, true); assert.equal(m.q, ''); assert.equal(m.a, ''); assert.deepEqual(m.sources, []); assert.equal(m.at, T); });

// ---- 새 채팅을 시작할 수 있는 때 (버튼이 켜지는 때)
t('지금 대화에 줄이 있으면 켜진다', () => { assert.equal(canStartNewChat([row('a')], false), true); });
t('지금 대화가 비어 있으면 꺼진다 (표지가 쌓이지 않게)', () => { assert.equal(canStartNewChat([row('a'), mark()], false), false); });
t('채팅 기록에서 열어 보는 중이면 비어 있어도 켜진다 (보기에서 빠져나오기)', () => { assert.equal(canStartNewChat([row('a'), mark()], true), true); assert.equal(canStartNewChat([mark()], true), true); });

// ---- 새 채팅을 시작하면: 기록은 한 줄도 안 줄고 표지만 +1
t('시작하면 표지 하나만 더해지고 기록은 줄지 않는다', () => {
  const log = [row('a'), row('b')];
  const next = withNewChat(log, mark(), false);
  assert.equal(next.length, log.length + 1);
  assert.deepEqual(next.slice(0, log.length), log);
  assert.equal(next[next.length - 1].newChat, true);
  assert.equal(log.length, 2, '원본 배열은 바꾸지 않는다');
});
t('두 번 눌러도 표지는 하나다 (중복 방지)', () => {
  const once = withNewChat([row('a')], mark(), false);
  const twice = withNewChat(once, mark(), false);
  assert.equal(twice.filter((r) => r.newChat).length, 1);
  assert.equal(twice, once, '바꿀 게 없으면 같은 배열을 돌려준다');
});
t('맨 끝이 이미 표지면 기록에서 열어 본 중이어도 표지를 더하지 않는다', () => {
  const log = [row('a'), mark()];
  assert.equal(withNewChat(log, mark(), true), log);
});
t('기록에서 열어 본 중이고 지금 대화에 줄이 있으면 표지를 더한다', () => {
  const log = [row('a'), mark(), row('b')];
  assert.equal(withNewChat(log, mark(), true).length, 4);
});
t('시작한 뒤 지금 대화는 비어 있고 새 질문부터 쌓인다', () => {
  const started = withNewChat([row('a'), row('b')], mark(), false);
  assert.deepEqual(currentChat(started), []);
  assert.deepEqual(qs(currentChat([...started, row('c')])), ['c']);
  assert.deepEqual(qs(realRows([...started, row('c')])), ['a', 'b', 'c'], '이전 대화는 기록에 그대로');
});

// ---- 서버 채팅 기록과 합치기 (채팅 기록 탭, API-AST-02 GET)
const T2 = '2026-10-01T11:00:00+09:00';
const srv = (q, chatId, at = T) => ({ ...row(q, at), chatId });
t('서버에만 있는 줄(다른 PC에서 물은 것)이 더해진다', () => { assert.deepEqual(qs(mergeServerLog([row('a', T2)], [srv('b', 7)])), ['b', 'a']); });
t('chat_id가 같은 줄은 한 번만, 이 브라우저 시각으로', () => {
  const m = mergeServerLog([srv('a', 5, T2)], [srv('a', 5, T)]);
  assert.equal(m.length, 1); assert.equal(m[0].at, T2);
});
t('chat_id 없는 옛 브라우저 줄은 질문·답이 같은 서버 줄 하나와 겹친다', () => {
  assert.deepEqual(qs(mergeServerLog([row('a')], [srv('a', 1), srv('a', 2)])), ['a', 'a'], '같은 질문을 두 번 물었으면 하나만 겹친다');
});
t('표지 줄은 빠지고 시각이 같으면 이 브라우저 줄 먼저', () => { assert.deepEqual(qs(mergeServerLog([row('a'), mark(), row('b')], [srv('c', 9)])), ['a', 'b', 'c']); });
t('서버 기록이 비어도(백엔드 꺼짐) 이 브라우저 기록 그대로', () => { assert.deepEqual(qs(mergeServerLog([row('a'), row('b')], [])), ['a', 'b']); });
t('이어서 물을 번호 = 번호 있는 마지막 줄, 없으면 null', () => {
  assert.equal(lastChatId([srv('a', 3), srv('b', 4), row('c')]), 4);
  assert.equal(lastChatId([row('a')]), null);
  assert.equal(lastChatId([]), null);
});

console.log(fail ? `\n${fail}개 실패` : '\n전부 통과');
process.exit(fail ? 1 : 0);
