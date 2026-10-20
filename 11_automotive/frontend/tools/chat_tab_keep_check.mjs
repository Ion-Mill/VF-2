// 이브 창: 다른 탭에 가도 채팅이 지워지지 않는 구조 확인 — 프레임워크 없이 Node 20으로 돈다 (이 화면 폴더에는 시험 도구가 없다).
//   실행: node 11_automotive/frontend/tools/chat_tab_keep_check.mjs     (frontend 폴더에서는 node tools/chat_tab_keep_check.mjs)
// src/shell/Eve.tsx의 글자를 읽어, 채팅을 "탭이 채팅일 때만 그리는" 식으로 되돌리는 변경을 막는다.
// 실제 동작(질문 직후 다른 탭에 다녀와도 질문·답이 남는가)은 브라우저에서 확인한다 — 방법은 수정 메모(1020 파일)에 있다.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const src = readFileSync(fileURLToPath(new URL('../src/shell/Eve.tsx', import.meta.url)), 'utf8');
const lines = src.split(/\r?\n/);

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

const chatUses = lines.map((l, i) => ({ l, n: i + 1 })).filter((x) => /<Chat[\s/>]/.test(x.l));

t('<Chat>은 이브 창 안에서 한 곳에서만 그려진다', () => { assert.equal(chatUses.length, 1); });
t('<Chat>이 탭 삼항식("tab === \'채팅\' ? <Chat")에 들어 있지 않다 (탭을 옮기면 사라지는 옛 모양)', () => {
  assert.ok(!/tab === '채팅' \? <Chat/.test(src));
  assert.ok(!/tab === '채팅' && <Chat/.test(src));
});
t('<Chat>이 active 속성을 받는다', () => { assert.match(chatUses[0].l, /active=\{tab === '채팅'\}/); });
t('<Chat>을 감싼 div가 채팅일 때 contents, 아닐 때 hidden이다', () => {
  const at = chatUses[0].n - 1;                       // 0부터 센 줄 번호 기준, 바로 앞 줄이 감싸는 div
  assert.match(lines[at - 1], /className=\{tab === '채팅' \? 'contents' : 'hidden'\}/);
});
t('채팅이 아닌 탭 내용은 채팅 탭일 때 그려지지 않는다', () => { assert.match(src, /\{tab && tab !== '채팅' && \(/); });
t('숨겨진 동안 끝난 녹음은 글자로 바꾸지 않고 버린다 (onAudio가 active를 본다)', () => { assert.match(src, /if \(!activeRef\.current\) return;/); });
t('채팅 탭을 떠나면 녹음을 멈춘다', () => { assert.match(src, /if \(!active\) \{ mic\.stop\(\); return; \}/); });
t('다시 보일 때 맨 아래로 내린다 (스크롤 효과가 active를 본다)', () => { assert.match(src, /\[log\.length, waiting, focus, active\]/); });

// ---- 창을 닫았다 열어도, 새로고침해도 (2026-10-20 확장)
t('이브 창(<aside>)은 tab에만 묶이지 않고 한 번 열린 뒤에는 계속 그려진다 (showPanel)', () => {
  assert.match(src, /const showPanel = !!tab \|\| opened;/); assert.match(src, /\{showPanel && \(\s*<aside/);
  assert.ok(!/\{tab && \(\s*<aside/.test(src));
});
t('닫혀 있을 때는 display: none으로 숨긴다 (CSS 클래스와 겹치지 않게 인라인 스타일)', () => { assert.match(src, /style=\{tab \? undefined : \{ display: 'none' \}\}/); });
t('열린 적이 있다는 표시(opened)는 tab이 생길 때 켜진다', () => { assert.match(src, /if \(tab\) setOpened\(true\)/); });
t('질문을 보내자마자 대기 줄로 저장하고 답이 오면 settlePending으로 그 자리에서 바꾼다', () => {
  assert.match(src, /pending: true, sentAt/); assert.match(src, /settlePending\(keep30\(l\), sentAt, row\)/);
});
t('끊긴 대기 줄 되살리기(resolvePending)가 있고, 되살리는 동안(waiting) 새 질문을 막는다', () => {
  assert.match(src, /resolvePending\(l, server, Date\.now\(\), inflight\.current/); assert.match(src, /const waiting = busy \|\| orphan;/);
  assert.match(src, /disabled=\{waiting\} aria-label="보내기"/);
});
t('쓰다 만 글은 localStorage(useLocal)에 남긴다', () => { assert.match(src, /useLocal<string>\(`chatdraft:\$\{user\.id\}`, ''\)/); });

console.log(fail ? `\n${fail}개 실패` : '\n전부 통과');
process.exit(fail ? 1 : 0);
