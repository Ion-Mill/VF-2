// 화면 정보판 글자 모으기 — Node에서 typescript를 그대로 불러 확인한다.
//   실행: node tools/screen_text_check.mjs   (frontend 폴더)
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

function loadTypeScript() {
  const candidates = [
    new URL('../package.json', import.meta.url),
    new URL('../../../../../../11_automotive/frontend/package.json', import.meta.url),
  ];
  for (const pkg of candidates) {
    if (existsSync(pkg)) {
      try { return createRequire(fileURLToPath(pkg))('typescript'); } catch { /* 다음 후보 */ }
    }
  }
  throw new Error('typescript 패키지를 찾지 못했습니다. frontend/node_modules가 있는 쪽에서 실행하세요.');
}
const ts = loadTypeScript();

const js = ts.transpileModule(readFileSync(fileURLToPath(new URL('../src/shell/screenText.ts', import.meta.url)), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { isScreenQuestion, joinPanels, collectScreenText } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

function el(text, attrs = {}, kids = []) {
  const node = {
    attrs, kids, text,
    cloneNode() {
      const c = el(text, { ...attrs }, kids.map((k) => k.cloneNode()));
      c.kids.forEach((k) => { k.parentNode = c; });
      return c;
    },
    querySelectorAll(sel) {
      const out = [];
      const walk = (n) => {
        if (sel.includes('data-summary-skip') && n.attrs.skip) out.push(n);
        if (sel.includes('data-summary-field') && n.attrs.field != null) out.push(n);
        const want = sel.match(/"([^"]*)"/);
        if (want && n.attrs.panel === want[1]) out.push(n);
        n.kids.forEach(walk);
      };
      this.kids.forEach(walk);
      return out;
    },
    getAttribute(name) {
      if (name === 'data-summary-field') return this.attrs.field ?? null;
      if (name === 'aria-label') return this.attrs.aria ?? null;
      return null;
    },
    hasAttribute(name) {
      if (name === 'data-summary-skip') return !!this.attrs.skip;
      if (name === 'data-summary-field') return this.attrs.field != null;
      if (name === 'aria-label') return this.attrs.aria != null;
      return false;
    },
    nodeType: 1,
    get childNodes() {
      const nodes = this.text ? [{ nodeType: 3, textContent: this.text }] : [];
      return [...nodes, ...this.kids];
    },
    get textContent() { return [this.text, ...this.kids.map((k) => k.textContent)].filter((s) => s).join('\n'); },
  };
  node.removeChild = (c) => { node.kids = node.kids.filter((k) => k !== c); };
  kids.forEach((k) => { k.parentNode = node; });
  return node;
}

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n')[0]); } };

t('화면 설명 세 마디는 잡고, 알람·안전 질문은 안 잡는다', () => {
  assert.equal(isScreenQuestion('이 화면 설명해 줘'), true);
  assert.equal(isScreenQuestion('이 화면 요약해 줘'), true);
  assert.equal(isScreenQuestion('여기 뭐가 떠 있어?'), true);
  assert.equal(isScreenQuestion('992 뜨면 뭐부터 봐?'), false);
  assert.equal(isScreenQuestion('2075 알람 뭐야'), false);
  assert.equal(isScreenQuestion('잠금·표지는 내가 지금 해?'), false);
});

t('같은 줄은 한 번만, 안전 칸은 한 줄 표시로 바꾼다', () => {
  const text = joinPanels([{ text: '생산\n102\n102', skipped: false }, { text: '잠금·표지 체크', skipped: true }]);
  assert.equal(text.includes('102\n102'), false);
  assert.ok(text.includes('[안전 작업 칸 — 요약하지 않음]'));
  assert.equal(text.includes('잠금·표지 체크'), false);
});

t('지금 화면 번호의 정보판만 모으고, 그 안의 안전 칸은 뺀다', () => {
  const root = el('', {}, [
    el('생산', { panel: 'SCR-04' }, [el('102'), el('고정 서식', { skip: true })]),
    el('하루 생산', { panel: 'SCR-16' }, [el('184개')]),
  ]);
  const line = collectScreenText('SCR-04', root);
  assert.ok(line.includes('생산') && line.includes('102'));
  assert.equal(line.includes('184개'), false);
  assert.equal(line.includes('고정 서식'), false);
  assert.ok(line.includes('[안전 작업 칸 — 요약하지 않음]'));
});

t('작업지시는 번호와 수량을 한 칸으로 잇지 않는다', () => {
  const root = el('', {}, [
    el('', { panel: 'SCR-04' }, [
      el('', { field: '라인 현황' }),
      el('생산', { field: '생산' }, [el('13'), el('/'), el('90')]),
      el('예측', { field: '예측' }, [el('13'), el('↘', { aria: '목표 미달 예상' })]),
      el('OEE', { field: 'OEE' }, [el('42.8'), el('%')]),
      el('손실', { field: '손실' }, [el('5'), el('개')]),
      el('작업지시 진행', { field: '작업지시 진행' }),
      el('OP-10 · OP-20', { field: '담당 공정' }),
      el('전체 ›', { field: '작업지시 전체 보기' }),
      el('', { field: '작업지시' }, [el('PO-2609-127'), el('41 / 60'), el('진행 중')]),
      el('', { field: '작업지시' }, [el('PO-2609-128'), el('0 / 31'), el('진행 중')]),
      el('고정 서식', { skip: true }),
    ]),
  ]);
  const line = collectScreenText('SCR-04', root);
  assert.ok(line.startsWith('라인 현황'));
  assert.ok(line.includes('생산 13/90'));
  assert.ok(line.includes('예측 13 ↘ 목표 미달 예상'));
  assert.ok(line.includes('OEE 42.8%'));
  assert.ok(line.includes('손실 5 개'));
  assert.ok(line.includes('작업지시 진행'));
  assert.ok(line.includes('담당 공정 OP-10 · OP-20'));
  assert.ok(line.includes('작업지시 전체 보기 전체 ›'));
  assert.equal(line.includes('OP-10 · OP-20 전체'), false);
  assert.equal(line.includes('오른쪽'), false);
  assert.ok(line.includes('작업지시 PO-2609-127, 41 / 60, 진행 중'));
  assert.ok(line.includes('작업지시 PO-2609-128, 0 / 31, 진행 중'));
  assert.equal(line.includes('12741'), false);
  assert.equal(line.includes('1280'), false);
  assert.equal(line.includes('고정 서식'), false);
});

t('지침카드는 알람 번호와 경과, 생산 영향 칸을 한 줄로 붙이지 않는다', () => {
  const root = el('', {}, [
    el('', { panel: 'SCR-09' }, [
      el('', { field: '지침카드' }),
      el('', { field: '결론' }, [el('⚠ 정지'), el('·'), el('VF2-01'), el('· 알람'), el('994'), el('증폭기 과부하'), el('·'), el('37'), el('분째')]),
      el('서보 앰프에 높은 부하가 오래 걸렸다.', { field: '설명' }),
      el('처리 책임: 보전 담당자', { field: '처리 책임: 보전 담당자' }),
      el('연쇄 108 → 994', { field: '연쇄 108 → 994' }),
      el('로트 LOT-2609-127-1', { field: '로트 LOT-2609-127-1' }),
      el('OP-30 1대 → 라인 속도 절반', { field: '속도' }),
      el('작업지시서 MW-0950 보기 →', { field: '작업지시서 MW-0950 보기 →' }),
    ]),
    el('', { panel: 'SCR-09' }, [
      el('생산 영향', { field: '생산 영향' }),
      el('추정', { field: '추정' }),
      el('정지', { field: '정지' }, [el('37'), el('분째'), el('08:53부터')]),
      el('손실 (추정)', { field: '손실 (추정)' }, [el('약 5.3'), el('개'), el('37분 ÷ 기준 사이클 7분')]),
      el('가공 중이던 로트', { field: '가공 중이던 로트' }, [el('LOT-2609-127-1'), el('의심 로트 제안')]),
    ]),
  ]);
  const line = collectScreenText('SCR-09', root);
  assert.ok(line.startsWith('지침카드'));
  assert.ok(line.includes('결론 ⚠ 정지 · VF2-01 · 알람 994 증폭기 과부하 · 37 분째'));
  assert.ok(line.includes('속도 OP-30 1대 → 라인 속도 절반'));
  assert.equal(line.includes('생산 영향 OP-30'), false);
  assert.ok(line.includes('설명 서보 앰프에 높은 부하가 오래 걸렸다.'));
  assert.ok(line.includes('처리 책임: 보전 담당자'));
  assert.equal(line.includes('처리 책임 처리 책임'), false);
  assert.ok(line.includes('정지 37 분째 08:53부터'));
  assert.ok(line.includes('손실 (추정) 약 5.3 개 37분 ÷ 기준 사이클 7분'));
  assert.ok(line.includes('가공 중이던 로트 LOT-2609-127-1 의심 로트 제안'));
  assert.equal(line.includes('99437'), false);
  assert.equal(line.includes('375.3'), false);
});

t('일일보고 하루 생산은 칸마다 이름을 붙인다', () => {
  const root = el('', {}, [
    el('', { panel: 'SCR-16' }, [
      el('하루 생산', { field: '하루 생산' }),
      el('목표 대비', { field: '목표 대비' }, [el('102.2'), el('%')]),
      el('실적', { field: '실적' }, [el('184'), el('개'), el('목표 180개')]),
      el('주간 / 야간', { field: '주간 / 야간' }),
      el('주간', { field: '주간' }, [el('90')]),
      el('야간', { field: '야간' }, [el('94')]),
      el('초과', { field: '초과' }, [el('4'), el('개')]),
      el('불량', { field: '불량' }, [el('1'), el('개')]),
      el('OEE (라인)', { field: 'OEE (라인)' }, [el('67.8'), el('%')]),
    ]),
  ]);
  const line = collectScreenText('SCR-16', root);
  assert.ok(line.includes('목표 대비 102.2%'));
  assert.ok(line.includes('실적 184 개 목표 180개'));
  assert.ok(line.includes('주간 90'));
  assert.ok(line.includes('야간 94'));
  assert.equal(line.includes('9094'), false);
  assert.ok(line.includes('초과 4 개'));
  assert.ok(line.includes('불량 1 개'));
  assert.ok(line.includes('OEE (라인) 67.8%'));
  assert.equal(line.includes('184180'), false);
});

if (fail) { console.log('실패 ' + fail); process.exit(1); }
console.log('화면 글자 모으기 확인 끝');
