// 채팅 말풍선·기록 항목 박스 시험 — 프레임워크 없이 Node 20으로 돈다.
//   실행: node 11_automotive/frontend/tools/chat_bubble_check.mjs     (frontend 폴더에서는 node tools/chat_bubble_check.mjs)
// src/shell 의 bubbleBox.ts · parseAlarmAnswer.ts · AlarmAnswerCard.tsx · ChatBubble.tsx 를 typescript 패키지로 임시 폴더에 변환하고(그 안의 node_modules 는 이 폴더의 것을
// 가리키는 연결), react-dom/server 로 **실제 컴포넌트를 그려** 박스를 확인한다. 끝나면 임시 폴더를 지운다. 빌드·설치 없음.
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, rmdirSync, symlinkSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const front = fileURLToPath(new URL('..', import.meta.url));
const shell = path.join(front, 'src/shell');
const req = createRequire(pathToFileURL(path.join(front, 'package.json')));
const ts = req('typescript');
const dir = mkdtempSync(path.join(tmpdir(), 'chat_bubble_check_'));
const link = path.join(dir, 'node_modules');
symlinkSync(path.join(front, 'node_modules'), link, 'junction');
const emit = (file, jsx) => writeFileSync(path.join(dir, file.replace(/\.tsx?$/, '.mjs')),
  ts.transpileModule(readFileSync(path.join(shell, file), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, ...(jsx ? { jsx: ts.JsxEmit.ReactJSX } : {}) } })
    .outputText.replace(/from '\.\/(\w+)'/g, "from './$1.mjs'"));
for (const f of ['bubbleBox.ts', 'parseAlarmAnswer.ts', 'parsePlainAnswer.ts']) emit(f, false);
for (const f of ['AlarmAnswerCard.tsx', 'ChatBubble.tsx']) emit(f, true);
const imp = (n) => import(pathToFileURL(path.join(dir, n + '.mjs')).href);
const Box = await imp('bubbleBox');
const { parsePlainAnswer } = await imp('parsePlainAnswer');
const { Bubble, Typing, HistoryItem } = await imp('ChatBubble');
const React = (await import(pathToFileURL(req.resolve('react')).href)).default;
const rs = await import(pathToFileURL(req.resolve('react-dom/server')).href);
const render = (el) => (rs.renderToStaticMarkup ?? rs.default.renderToStaticMarkup)(el);
const eveSource = readFileSync(path.join(shell, 'Eve.tsx'), 'utf8');

const A230 = "■ 알람 설명\n알람 230 도어 열림(DOOR OPEN) 심각도는 조작 안내, 조치는 작업자입니다.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 알람 번호·이름을 본다\n★2 (작업자) 아래 표의 \"볼 곳\"을 확인해 고친다\n★2-1 (작업자) 알람 230 — 볼 곳: 도어 · 고치는 법: 도어 장치에 고장이나 걸림이 없는지 보고 닫는다\n★3 (작업자) [RESET] 후 다시 시작한다. 같은 알람이 되풀이되면 반장에게 알린다.\n\n이 알람은 최근 7일 0번, 30일 0번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 230 알람 뭐야
const PLAIN = "6.1 · ① 해당 설비의 §3 표를 연다 (차단 지점, 저장 에너지) ② 작업지시서에 적힌 차단 지점과 맞는지 본다 ③ 해당 작업자(OPR)와 반장에게 \"정비로 정지한다\"고 알린다 (5.9 \"문서화된 방법으로 알려야\") ④ 정지하기 전에 에너지의 크기, 형태, 위험 정도, 관리 방법을 알고 있어야 한다\n6.2 · ① 가공 중이면 사이클을 멈추고 주축·축·톱날이 완전히 멈춘 것을 눈으로 본다 ② 제어기 전원을 끈다 (Haas: [POWER OFF])\n6.3 · §3의 차단 지점을 순서대로 끈다: 주 차단기 OFF → 공압 주 밸브 닫음 → (해당되면) 공급 쪽 분전반 차단기 OFF. 제조사는 \"기계로 가는 모든 전원을 공급원에서\" 끄라고 한다\n6.4 · ① 차단 지점마다 내 자물쇠를 건다 ② 표지를 자물쇠에 묶는다 ③ 일하는 사람이 여러 명이면 §2.3 ④ 각각의 차단장치에 단다. 잠금장치는 \"안전\" 또는 \"오프(Off)\" 상태를 계속 유지시키는 수단이다\n6.5 · §3의 \"저장 에너지\" 칸대로: 고전압 대기(§4), 공압 잔압 빼기, 주축 헤드 받치기, 회전체 멈춤 확인, 세척조 식히기. 법 제92조 ④ \"미리 방출\". 남은 에너지는 방출·분리·제한하거나 안전한 상태로 두고, 다시 쌓일 수 있으면 작업이 끝날 때까지 계속 확인한다\n6.6 · ① 전기: 교류 검전기로 들어오는 선 전부를 확인 ② 공압: 압력계가 0인지 ③ 기동 버튼을 눌러 켜지지 않는지 본 뒤 다시 정지 위치로 둔다 ④ 작업을 시작하기 전에 승인작업자가 에너지가 차단되었는지 확인한다\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 안전 작업 순서 알려줘
const T05 = "아니요, 90%가 뜨면 바로 멈추고 바꾸는 것이 아니에요. 가공 중인 사이클이 끝난 뒤나 다음 셋업 때 교체하는 것이 문서의 기준이에요.\n\n■ 90%의 뜻\n1. T05의 90%는 공구 수명 사용률이라, 한도의 90%를 쓰고 남은 수명이 10%라는 뜻이에요.\n2. 화면에는 교체 알림으로 뜨고, 교대 시작 브리핑에도 '공구 수명 90% 이상'으로 올라와요.\n3. 이 90% 기준은 팀이 정한 가상 기준이고, 비율의 근거는 문서에 없어요.\n\n■ 교체할 때 지킬 것\n1. 교체는 프로그램을 중단하지 않은 상태, 곧 사이클이 끝난 뒤에 해요.\n2. 교체 순서와 교체 기록은 작업자(OPR)가 해요.\n\n■ 80~90% 구간과 90% 이후\n1. 수명 80~90% 구간에서 교체를 앞당길지는 반장(SUP)이 판단해요.\n2. 의심 로트를 보류할지는 반장이 판단해요.\n\n주의: 근거 안내이며 실행 지시가 아닙니다.";   // 실제 답: T05 공구 90%는 교체 알림이야 (시연 #1 턴 3)
const STOCK = "재고 부족\n1. 공기 필터 2개 (안전 재고 2.0)\n2. 축 윤활유 3.6L (안전 재고 4.0)";   // 실제 답: 조회 답 — 머리 줄에 ■가 없다 (비서가 붙이면 그때 소제목이 된다)
const STEPS992 = "■ 점검 순서 (사내 문서)\n★1 (작업자) 축을 움직이지 말고 알람 이력을 봐요. 바로 앞에 108·994(과부하)가 있으면 충돌 신호예요.\n★2 (작업자) 도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 봐요.\n★3 (작업자) 외함·주축·공구·고정구에 손상이 있는지 봐요 (손상 = 충돌 징후).\n★4 (작업자) 공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 불러요.\n5 (보전) 잠금·표지 후, 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 봐요.\n6 (보전) 충돌이 확인되면 볼스크류 커플링 정렬도 봐요 (§2.5 점검 8).\n7 (보전) 서보 모터 케이블이 오염·끼임 없는지, 모터 쪽 커넥터에 절삭유 오염이 없는지 보고 아래 표대로 저항을 재요.\n8 (보전) 이송을 낮춰 MDI로 해당 축을 움직이는 시험을 해요. 어떤 이송에서도 알람이 뜨면 서보 앰프 문제예요.\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 992 뜨면 뭐부터 해? (점검 순서만 남김)
const SOURCES = [{"doc_name": "알람 코드집", "doc_no": "DOC-02", "rev": "Rev.1 (2026-10-07)", "section": "4.11"}, {"doc_name": "고장 대응 매뉴얼", "doc_no": "DOC-03", "rev": "Rev.1 (2026-10-07)", "section": "2.11"}];
const AT = '2026-10-01T10:00:00+09:00';
const row = (q, a, extra = {}) => ({ at: AT, q, a, status: 'ok', sources: [], ...extra });
const bubble = (r, role = 'OPR') => render(React.createElement(Bubble, { r, meta: '10/1 10:00', openSource: () => {}, role }));

/** 답 박스 <div class="ANSWER_BOX"> 의 [시작, 끝) 위치 — 안쪽 div 를 세어 닫는 자리를 찾는다 (정규식으로는 안쪽·바깥을 못 가른다) */
const boxRange = (h) => {
  const start = h.indexOf(`<div class="${Box.ANSWER_BOX}"`);
  if (start < 0) return null;
  let depth = 0, i = start;
  for (const m of h.slice(start).matchAll(/<div\b|<\/div>/g)) { depth += m[0] === '</div>' ? -1 : 1; if (depth === 0) { i = start + m.index + m[0].length; break; } }
  return [start, i];
};
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n').slice(0, 4).join('\n      ')); } };

// ---- 박스 클래스 상수
t('답 박스 상수는 알람 카드 바깥 상자의 클래스 그대로다 (사용자가 가리킨 클래스)', () => {
  assert.equal(Box.ANSWER_BOX, 'rounded-3xl bg-white/80 p-5 text-[16px] leading-relaxed text-slate-900 shadow-sm');
});
t('질문 박스는 같은 모양(rounded-3xl·shadow-sm·16px)에 보라 톤·테두리·오른쪽 정렬', () => {
  for (const c of ['rounded-3xl', 'shadow-sm', 'text-[16px]', 'border', 'border-violet-200', 'bg-violet-100', 'self-end', 'max-w-[82%]']) assert.ok(Box.QUESTION_BOX.split(' ').includes(c), c);
});
t('덮어쓰이는 클래스(bg-white · bg-slate-* · text-slate-400/500/700)는 박스 상수에 없다', () => {
  for (const k of ['ANSWER_BOX', 'QUESTION_BOX', 'HISTORY_BOX']) for (const c of Box[k].split(' ')) assert.ok(!/^(bg-white|bg-slate-\d+|text-slate-(400|500|700))$/.test(c), `${k}: ${c}`);
});

// ---- 질문
t('질문은 질문 박스 안에 있고 옛 클래스(ma-msg-user)가 없다', () => {
  const h = bubble(row('2075 알람 뭐야', '답입니다.'));
  assert.ok(h.includes(`<div class="${Box.QUESTION_BOX}">2075 알람 뭐야</div>`), h.slice(0, 300));
  assert.ok(!h.includes('ma-msg-user'));
});
t('질문의 <, &, 따옴표는 글자 그대로 보이고 태그로 해석되지 않는다', () => {
  const h = bubble(row('<b>x</b> & "y"', '답'));
  assert.ok(h.includes('&lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot;') && !h.includes('<b>x</b>'));
});

// ---- 일반 답
t('알람이 아닌 답은 답 박스 안의 평문이고 박스는 하나', () => {
  const h = bubble(row('안전 작업 순서 알려줘', PLAIN, { sources: SOURCES }));
  assert.equal((h.match(new RegExp(esc(`class="${Box.ANSWER_BOX}"`), 'g')) ?? []).length, 1);
  assert.match(h, new RegExp(`<div class="${esc(Box.ANSWER_BOX)}"><p class="ma-msg-bot ${esc(Box.WRAP)}">6\\.1`));
});
t('출처 줄은 답 박스 밖(아래)에 그대로 있다 (알약이 아닌 글자 "출처:")', () => {
  const h = bubble(row('안전 작업 순서 알려줘', PLAIN, { sources: SOURCES }));
  const [s0, e0] = boxRange(h);
  assert.ok(h.slice(s0, e0).includes('6.1 ·'), '답 글자는 박스 안');
  assert.ok(!h.slice(s0, e0).includes('출처:'), '출처 줄은 박스 안에 없다');
  assert.ok(h.indexOf('출처:') >= e0, '출처 줄은 박스가 닫힌 뒤에 있다');
  assert.match(h, /DOC-02[^<]*Rev\.1[^<]*§4\.11/);
});
t('센서 시계열 줄(series)은 답 박스 안에 있다', () => {
  const h = bubble(row('VF2-01 센서 추세', '최근 60분 값입니다.', { series: { 'VF2-01': { 'load': [1, 2, 3, 2, 5] } }, sources: SOURCES }));
  const [s0, e0] = boxRange(h), box = h.slice(s0, e0);
  assert.ok(box.includes('<svg') && box.includes('VF2-01 최근 60분') && box.includes('최근 60분 값입니다.'), box);
  assert.ok(h.indexOf('출처:') >= e0);
});
t('질문 → 날짜·상태 줄 → 답 순서 (날짜 글자는 부른 쪽이 준 것)', () => {
  const h = bubble(row('q1', '답1'));
  assert.ok(h.indexOf('q1') < h.indexOf('10/1 10:00 · 이브 · 규칙 답') && h.indexOf('10/1 10:00') < h.indexOf('답1'));
  assert.ok(bubble(row('q', 'a', { status: '응답 없음' })).includes('· 이브 · 응답 없음'));
});

// ---- 일반 답의 "■ 제목" (2026-10-21): 제목은 알람 카드와 같은 보라색 굵은 소제목, ■ 기호는 그리지 않는다
t('소제목 클래스 상수는 알람 카드 제목과 같은 문자열이다', () => {
  assert.equal(Box.HEADING, 'm-0 text-[15px] font-bold text-violet-600');
});
t('T05 답: "■ 제목" 3개가 h3 소제목이 되고 ■ 기호는 화면에 없다', () => {
  const h = bubble(row('T05 공구 90%는 교체 알림이야, 바로 바꿔야 해?', T05, { sources: SOURCES }));
  const heads = [...h.matchAll(/<h3 id="[^"]*" class="([^"]*)">([^<]*)<\/h3>/g)];
  assert.deepEqual(heads.map((m) => m[2]), ['90%의 뜻', '교체할 때 지킬 것', '80~90% 구간과 90% 이후']);
  assert.ok(heads.every((m) => m[1] === Box.HEADING));
  assert.ok(!h.includes('■'), '■ 기호가 남아 있다');
});
t('T05 답: 머리 문단·번호 목록·주의 줄이 글자와 줄바꿈 그대로 남는다 (답 박스는 하나)', () => {
  const h = bubble(row('T05 공구 90%는 교체 알림이야, 바로 바꿔야 해?', T05, { sources: SOURCES }));
  assert.equal((h.match(new RegExp(esc(`class="${Box.ANSWER_BOX}"`), 'g')) ?? []).length, 1);
  const [s0, e0] = boxRange(h), box = h.slice(s0, e0);
  assert.ok(box.indexOf('아니요, 90%가 뜨면') < box.indexOf('90%의 뜻'), '머리 문단은 첫 제목 앞');
  for (const s of ['1. T05의 90%는 공구 수명 사용률이라,', '3. 이 90% 기준은 팀이 정한 가상 기준이고,', '2. 교체 순서와 교체 기록은 작업자(OPR)가 해요.', '주의: 근거 안내이며 실행 지시가 아닙니다.']) assert.ok(box.includes(s.replace(/'/g, '&#x27;')) || box.includes(s), s);
  assert.ok(box.includes('1. 교체는 프로그램을 중단하지 않은 상태, 곧 사이클이 끝난 뒤에 해요.\n2. 교체 순서'), '줄바꿈 그대로');
  assert.ok(h.indexOf('출처:') >= e0, '출처 줄은 박스 밖');
});
t('T05 답: 보이는 글자의 낱말 열이 원래와 같다 (글자가 하나도 사라지지 않는다)', () => {
  const h = bubble(row('q', T05));
  const [s0, e0] = boxRange(h);
  const text = h.slice(s0, e0).replace(/<[^>]*>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&');
  const words = (s) => s.match(/[\p{L}\p{N}]+/gu) ?? [];
  assert.deepEqual(words(text), words(T05));
});
t('■가 없는 조회 답(재고)은 예전과 같은 평문 한 덩어리다 (비서가 ■를 붙이기 전까지)', () => {
  const h = bubble(row('축 윤활유 재고', STOCK));
  assert.ok(!h.includes('<h3'));
  assert.match(h, new RegExp(`<div class="${esc(Box.ANSWER_BOX)}"><p class="ma-msg-bot ${esc(Box.WRAP)}">재고 부족\n1\\. 공기 필터`));
});
t('조회 답의 머리 줄에 비서가 ■를 붙이면 그 줄이 소제목이 된다', () => {
  const h = bubble(row('축 윤활유 재고', '■ ' + STOCK));
  assert.match(h, /<h3 id="[^"]*" class="m-0 text-\[15px\] font-bold text-violet-600">재고 부족<\/h3>/);
  assert.ok(!h.includes('■') && h.includes('1. 공기 필터 2개'));
});
t('알람 카드의 제목도 같은 소제목 클래스를 쓴다 (카드는 그대로 카드)', () => {
  const h = bubble(row('230 알람 뭐야', A230, { sources: SOURCES }));
  assert.ok(h.includes(`<h3 id=`) && (h.match(new RegExp(esc(`class="${Box.HEADING}"`), 'g')) ?? []).length >= 2);
  assert.ok(h.includes(`flex flex-col gap-4 ${Box.ANSWER_BOX}`));
});
t('parsePlainAnswer: ■가 없거나 제목이 비었거나 글이 아니면 null (예외 없음)', () => {
  for (const x of ['', '그냥 문장입니다.', '1. 목록\n2. 목록', '■', '■   ', '문장 가운데 ■ 기호는 제목이 아니다', undefined, null, 5, {}]) assert.equal(parsePlainAnswer(x), null, String(x));
});
t('parsePlainAnswer: 머리 문단·소제목·본문을 순서대로 읽고 \\r\\n·앞뒤 빈 줄·제목 앞 공백도 같은 결과', () => {
  const a = parsePlainAnswer('머리\r\n\r\n  ■ 첫째\r\n1. 가\r\n2. 나\r\n\r\n■ 둘째 제목\r\n\r\n\r\n마지막 글\r\n');
  assert.deepEqual(a, [{ title: null, body: '머리' }, { title: '첫째', body: '1. 가\n2. 나' }, { title: '둘째 제목', body: '마지막 글' }]);
});
t('parsePlainAnswer: 본문이 없는 제목과 맨 앞 제목도 남는다 (머리 문단은 만들지 않는다)', () => {
  assert.deepEqual(parsePlainAnswer('■ 하나\n\n■ 둘\n내용'), [{ title: '하나', body: '' }, { title: '둘', body: '내용' }]);
});
t('parsePlainAnswer: 제목 안의 <, &는 글자 그대로 (태그로 해석되지 않는다)', () => {
  const h = bubble(row('q', '■ <b>x</b> & y\n본문'));
  assert.ok(h.includes('&lt;b&gt;x&lt;/b&gt; &amp; y') && !h.includes('<b>x</b>'));
});

// ---- 알람 카드
t('알람 답은 카드이고 답 박스는 하나뿐이다 (겹박스 없음), 카드 박스가 같은 상수를 쓴다', () => {
  const h = bubble(row('230 알람 뭐야', A230, { sources: SOURCES }));
  assert.ok(h.includes('알람 설명') && h.includes('점검 순서 (사내 문서)'));
  assert.equal((h.match(new RegExp(esc(Box.ANSWER_BOX), 'g')) ?? []).length, 1);
  assert.ok(h.includes(`flex flex-col gap-4 ${Box.ANSWER_BOX}`));
  assert.ok(h.includes('aria-expanded="true"') && h.includes('gap-y-2') && h.includes('▾ 출처:'), '출처는 펼친 토글');
  assert.ok(h.includes('>알람 코드집 DOC-02 Rev.1 (2026-10-07) §4.11</button>'), '출처 글자는 밑줄 버튼');
  assert.ok(!h.includes('rounded-2xl bg-white px-4 py-2'), '출처 알약 없음');
});
t('역할: 작업자(OPR)는 작업자 단계가, 보전(MNT)은 보전 단계가 보라색 (230은 작업자 줄만 4개)', () => {
  const n = (role) => (bubble(row('230 알람 뭐야', A230), role).match(/bg-violet-600/g) ?? []).length;
  assert.equal(n('OPR'), 4); assert.equal(n('MNT'), 0);
});

t('점검 순서만 남긴 답도 카드이고 역할 강조가 간다: 작업자(OPR)는 작업자 단계 4개, 보전(MNT)은 보전 단계 4개가 보라색 (2026-10-21)', () => {
  const h = bubble(row('992 뜨면 뭐부터 해?', STEPS992, { sources: SOURCES }), 'OPR');
  assert.ok(h.includes('점검 순서 (사내 문서)'), '점검 순서 제목이 없다: ' + h.slice(0, 400));
  assert.ok(h.includes(`flex flex-col gap-4 ${Box.ANSWER_BOX}`), '카드 상자가 아니다(평문)');
  const n = (role) => (bubble(row('992 뜨면 뭐부터 해?', STEPS992), role).match(/bg-violet-600/g) ?? []).length;
  assert.equal(n('OPR'), 4); assert.equal(n('MNT'), 4);
});

// ---- 기다리는 글
t('"답변을 만드는 중…"도 같은 답 박스다', () => {
  const h = render(React.createElement(Typing));
  assert.ok(h.includes(`<div class="${Box.ANSWER_BOX}">`) && h.includes('답변을 만드는 중…') && h.includes('ma-typing'));
});

// ---- 답이 아직 안 온 줄 (대기 줄)
t('대기 줄은 질문 박스만 그린다 — 답 박스·상태 줄·출처가 없다', () => {
  const h = render(React.createElement(Bubble, { r: { at: '2026-10-01T10:00:00+09:00', q: '아직 답 없는 질문', a: '', status: '', sources: [], pending: true, sentAt: 1 }, meta: '10/1 10:00', openSource: () => {}, role: 'MNT' }));
  assert.ok(h.includes(`<div class="${Box.QUESTION_BOX}">아직 답 없는 질문</div>`), h);
  assert.ok(!h.includes(Box.ANSWER_BOX) && !h.includes('ma-msg-bot') && !h.includes('출처') && !h.includes('10/1 10:00'), h);
});

// ---- 채팅 기록 탭 항목
t('기록 항목은 박스 클래스를 가진 버튼이고 질문·시각이 그대로 보인다', () => {
  const h = render(React.createElement(HistoryItem, { q: '2075 알람 뭐야', when: '10/1 10:00', onOpen: () => {} }));
  assert.ok(h.startsWith(`<button type="button" class="${Box.HISTORY_BOX}">`), h.slice(0, 200));
  assert.ok(h.includes('2075 알람 뭐야') && h.includes('10/1 10:00') && !h.includes('ma-history-item'));
});
t('기록 항목을 누르면 onOpen이 불린다 (버튼 동작 그대로)', () => {
  let n = 0; const el = HistoryItem({ q: 'q', when: 'w', onOpen: () => { n++; } });
  assert.equal(el.type, 'button'); el.props.onClick(); assert.equal(n, 1);
});
t('기록 항목 박스에는 hover(연한 보라)와 포커스 링이 있다', () => { for (const c of ['hover:bg-violet-50', 'focus-visible:outline', 'focus-visible:outline-violet-600', 'min-h-[56px]']) assert.ok(Box.HISTORY_BOX.split(' ').includes(c), c); });

// ---- Eve.tsx 가 이 부품을 쓴다 (훅 때문에 Eve 전체는 서버 렌더로 못 그려서 소스 점검)
// 2026-10-20 이브 디자인(PR #85): 답을 기다리는 동안은 Typing 점 대신 3D 이브 <EveThinking /> (Typing은 ChatBubble에 그대로 — 위 시험)
t('Eve.tsx는 Bubble·EveThinking·HistoryItem을 쓰고 옛 말풍선 클래스·함수를 더 갖지 않는다', () => {
  for (const s of ['<Bubble r={r} meta={', '<EveThinking />', '<HistoryItem q={r.q}', "from './ChatBubble'", 'ma-history gap-2']) assert.ok(eveSource.includes(s), s);
  for (const s of ['ma-msg-user', 'ma-history-item', 'function Bubble(', 'interface ChatRow']) assert.ok(!eveSource.includes(s), '남아 있으면 안 됨: ' + s);
});

link && rmdirSync(link);            // 연결만 지운다 (대상 node_modules 는 그대로)
rmSync(dir, { recursive: true, force: true });
console.log(fail ? `\n실패 ${fail}개` : '\n모두 통과');
process.exit(fail ? 1 : 0);
