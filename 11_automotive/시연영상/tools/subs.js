// 자막을 줄마다 한 장짜리 그림(PNG)으로 만든다: 띠 하나(반투명 검정, 둥근 모서리) + 흰 글자, 키워드는 글자색만 노랑.
// 실행: node tools/subs.js   → work/subs/<id>.png + work/subs/index.json ({id: {w, h}})
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const WORK = path.join(ROOT, 'work');
const OUT = path.join(WORK, 'subs');
const FONT = 'file:///' + path.resolve(ROOT, '..', 'frontend/node_modules/pretendard/dist/web/static/woff2/Pretendard-SemiBold.woff2').replace(/\\/g, '/');
const lines = JSON.parse(fs.readFileSync(path.join(WORK, 'lines.json'), 'utf8'));
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function html(L) {
  const txt = L.sub;
  const mark = new Array(txt.length).fill(false);           // 키워드 글자 표시 (첫 번째로 나오는 곳만)
  for (const w of L.hl) { const i = txt.indexOf(w); if (i >= 0) for (let k = i; k < i + w.length; k++) mark[k] = true; }
  let body = '', on = false;
  for (let i = 0; i < txt.length; i++) {
    const c = txt[i];
    if (c === '\n') { if (on) { body += '</span>'; on = false; } body += '<br>'; continue; }
    if (mark[i] && !on) { body += '<span class="k">'; on = true; }
    if (!mark[i] && on) { body += '</span>'; on = false; }
    body += esc(c);
  }
  if (on) body += '</span>';
  return `<!doctype html><meta charset="utf-8"><style>
    @font-face{font-family:P;font-weight:600;src:url('${FONT}') format('woff2')}
    html,body{margin:0;background:transparent}
    #b{display:inline-block;padding:16px 38px 18px;border-radius:20px;background:rgba(8,12,20,.66);color:#fff;
       font:600 42px/1.45 P,'Malgun Gothic',sans-serif;letter-spacing:-.02em;text-align:center;white-space:nowrap}
    .k{color:#ffd84a}
  </style><div id="b">${body}</div>`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 400 }, deviceScaleFactor: 1 })).newPage();
  const index = {};
  for (const L of lines) {
    await page.setContent(html(L)); await page.evaluate(() => document.fonts.ready);
    const el = page.locator('#b');
    await el.screenshot({ path: path.join(OUT, L.id + '.png'), omitBackground: true });
    const r = await el.boundingBox(); index[L.id] = { w: Math.round(r.width), h: Math.round(r.height) };
  }
  fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(index, null, 1));
  await browser.close();
  console.log('자막 그림', Object.keys(index).length, '장 →', OUT);
})().catch((e) => { console.error(e); process.exit(1); });
