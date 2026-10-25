// 시연영상 자동 촬영 v4 (시연영상_스크립트.md 5장 + 2026-10-25 수정사항). 실행: node tools/record.js   (서버 4개가 켜져 있어야 함: 시연영상/로컬DB/start_video_local.ps1)
// 결과: work/raw/*.webm (화면만, 소리·자막 없음) + work/timeline.json (나레이션 시작 시각·자를 구간·시계 흐름 구간)
// v4: 박스는 화면 요소를 따라가고(overlay.js boxTrack) 대상이 사라지면 같이 사라진다 · 박스 밖은 기본으로 어둡게 · 커서는 박스 옆으로
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const WORK = path.join(ROOT, 'work');
const RAW = path.join(WORK, 'raw');
const LINES = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(WORK, 'lines.json'), 'utf8')).map((x) => [x.id, x]));
const GAP = 0.3;                               // 나레이션 줄 사이 쉼 (초)
const LEAD = 0.1, BOX_MIN = 1.5, BOX_MOVE_MIN = 1.0;   // 박스는 낱말보다 0.1초 먼저 / 줄 끝에서 지울 때 최소 1.5초 / 다른 곳으로 옮길 때 앞 박스 최소 1.0초
const APP = 'http://localhost:3000', SIM = 'http://127.0.0.1:8765/api/';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- 시연 서버(시계) 제어: 화면에 안 보여도 되는 곳에서만 쓴다 ----------
const api = async (method, p, body) => (await fetch(SIM + p, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })).json();
const clock = () => api('GET', 'sim/clock');
const setClock = (b) => api('POST', 'sim/clock', b);
const hhmm = (c) => c.sim_at.slice(11, 16);
async function until(fn, timeout = 60000, every = 250) { const t0 = Date.now(); for (;;) { const v = await fn(); if (v) return v; if (Date.now() - t0 > timeout) throw new Error('until: 시간 초과 — ' + fn.toString().slice(0, 80)); await sleep(every); } }

(async () => {
  fs.mkdirSync(RAW, { recursive: true });
  for (const f of fs.readdirSync(RAW)) fs.unlinkSync(path.join(RAW, f));
  await api('POST', 'sim/reset', {});
  await setClock({ speed: 60 });          // 장면 1~2는 ×60 (하단 패널 수치가 의미 있는 값이 되도록 약 10:00까지 흐름, 영상용 프로필은 10/24 09:00에 시작)

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: RAW, size: { width: 1920, height: 1080 } } });
  // 커서 그림 + 덧그림
  const hot = JSON.parse(fs.readFileSync(path.join(ROOT, '커서시안', 'hotspot.json'), 'utf8')).idle;
  const b64 = (n) => 'data:image/png;base64,' + fs.readFileSync(path.join(ROOT, '커서시안', n)).toString('base64');
  const ovSrc = fs.readFileSync(path.join(__dirname, 'overlay.js'), 'utf8')
    .replace('__IDLE__', b64('이브커서_idle_512.png')).replace('__CLICK__', b64('이브커서_click_512.png'))
    .replace('__HX__', (hot.x * 60 / 512).toFixed(1)).replace('__HY__', (hot.y * 60 / 512).toFixed(1));
  await ctx.addInitScript({ content: ovSrc });
  const page = await ctx.newPage();
  const T0 = Date.now();
  const now = () => (Date.now() - T0) / 1000;
  const events = [];
  let cur = { x: 1500, y: 950 };
  let curUser = null;

  // ---------- 커서 ----------
  async function moveTo(x, y, ms = 650) {
    // 커서 이동은 화면 안에서 시간 기준으로 부드럽게 (3D가 무거워도 느려지지 않게), 실제 마우스는 도착 지점으로 한 번만 옮긴다
    await page.evaluate(([sx, sy, x, y, ms]) => new Promise((res) => {
      const o = window.__ov, t0 = performance.now(), cx = (sx + x) / 2 + (sy - y) * 0.12, cy = (sy + y) / 2 + (x - sx) * 0.12;
      const f = (now) => { const t = Math.min(1, (now - t0) / ms), e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        o.place((1 - e) * (1 - e) * sx + 2 * (1 - e) * e * cx + e * e * x, (1 - e) * (1 - e) * sy + 2 * (1 - e) * e * cy + e * e * y);
        if (t < 1) requestAnimationFrame(f); else res(); };
      requestAnimationFrame(f);
    }), [cur.x, cur.y, x, y, ms]);
    await page.mouse.move(x, y); cur = { x, y };
  }
  async function clickAt(x, y, ms = 650) {
    await moveTo(x, y, ms); await sleep(180);
    await page.evaluate(() => window.__ov && window.__ov.press(true));
    await page.mouse.down(); await sleep(110); await page.mouse.up();
    await page.evaluate(() => window.__ov && window.__ov.press(false));
    await sleep(220);
  }
  async function center(loc) { await loc.scrollIntoViewIfNeeded(); const r = await loc.boundingBox(); if (!r) throw new Error('boundingBox 없음'); return { x: r.x + r.width / 2, y: r.y + r.height / 2, r }; }
  async function clickEl(loc, ms = 650) { loc = loc.first(); await loc.waitFor({ state: 'visible', timeout: 20000 }); const c = await center(loc); await clickAt(c.x, c.y, ms); }
  async function hoverEl(loc, ms = 600) { loc = loc.first(); await loc.waitFor({ state: 'visible', timeout: 20000 }); const c = await center(loc); await moveTo(c.x, c.y, ms); }
  // 박스 옆으로: 내용을 가리지 않게 박스 오른쪽 바깥(자리가 없으면 오른쪽 끝 안쪽)에 커서를 둔다
  async function hoverBeside(loc, ms = 600) {
    loc = loc.first(); await loc.waitFor({ state: 'visible', timeout: 20000 }); const r = await loc.boundingBox(); if (!r) return;
    const x = r.x + r.width + 40 < 1880 ? r.x + r.width + 40 : r.x + r.width - 26;
    await moveTo(x, r.y + r.height / 2, ms);
  }

  // ---------- 강조 박스 (낱말 시각에 맞춤) ----------
  let curStep = null, boxOnAt = -99;
  const boxVisible = () => page.evaluate(() => !!(window.__ov && window.__ov.visible())).catch(() => false);
  async function waitKw(k) {
    const vis = await boxVisible();
    const minAt = vis ? boxOnAt + BOX_MOVE_MIN : -99;           // 앞 박스가 떠 있으면 최소 1.0초 뒤에 옮긴다
    if (k == null || !curStep) { const d = minAt - now(); if (d > 0) await sleep(d * 1000); return; }
    const kw = curStep.L.kw[k]; if (!kw) throw new Error(curStep.L.id + ': kw ' + k + ' 없음');
    const target = Math.max(curStep.t0 + kw.s - LEAD, minAt), d = target - now();
    if (d > 0) await sleep(d * 1000);
    else if (d < -0.35) console.warn(`  ! 박스가 낱말보다 ${(-d).toFixed(1)}초 늦음: ${curStep.L.id} kw${k} (${kw.k})`);
  }
  async function stable(loc, tries = 30) {                       // 스크롤·화면 이동이 끝나 위치가 멈출 때까지
    let prev = '', same = 0;
    for (let i = 0; i < tries; i++) {
      const r = await loc.boundingBox().catch(() => null); const key = r ? [r.x, r.y, r.width, r.height].map(Math.round).join(',') : '';
      if (key && key === prev) { if (++same >= 2) return; } else same = 0; prev = key; await sleep(120);
    }
  }
  async function boxEl(loc, { pad = 8, dim = true, k = null, scroll = true, center = false } = {}) {
    try {
      loc = loc.first(); await loc.waitFor({ state: 'visible', timeout: 8000 });
      if (center) { await loc.evaluate((el) => el.scrollIntoView({ block: 'center', behavior: 'smooth' })); await sleep(700); } else if (scroll) await loc.scrollIntoViewIfNeeded();
      await stable(loc);
      await waitKw(k);
      await loc.evaluate((el, [p, d]) => window.__ov.boxTrack(el, p, d), [pad, dim]); boxOnAt = now();
    } catch (e) { console.warn('  ! 박스 대상 못 찾음 (건너뜀):', String(loc).slice(0, 90)); }
  }
  async function boxRect(x, y, w, h, dim = true, k = null) { await waitKw(k); await page.evaluate(([a, b, c, d, e]) => window.__ov.box(a, b, c, d, e), [x, y, w, h, dim]); boxOnAt = now(); }
  async function unbox() {
    if (await boxVisible()) { const r = boxOnAt + BOX_MIN - now(); if (r > 0) await sleep(r * 1000); }
    await page.evaluate(() => window.__ov && window.__ov.hide()); boxOnAt = -99;
  }
  // 3D 화면 이동 = 오른쪽 버튼 드래그 (왼쪽 버튼은 돌리기). x0 → x1 로 끌면 화면은 그 반대로 흘러간다
  async function pan(x0, x1, ms, y = 560) {
    await page.mouse.move(x0, y); await page.mouse.down({ button: 'right' });
    const n = 24;
    for (let i = 1; i <= n; i++) { await page.mouse.move(x0 + (x1 - x0) * i / n, y); await sleep(Math.max(0, ms / n - 20)); }
    await page.mouse.up({ button: 'right' }); cur = { x: x1, y };
  }
  async function wheel(dy, ms = 600) { const n = 6; for (let i = 0; i < n; i++) { await page.mouse.wheel(0, dy / n); await sleep(ms / n); } }

  // ---------- 타임라인 ----------
  // step: 나레이션 한 줄. 줄이 끝날 때까지(박스는 마지막 박스 뒤 최소 1.5초까지) 화면을 둔다.
  async function step(id, fn) {
    const L = LINES[id]; const t0 = now(); events.push({ type: 'say', id, t: t0, dur: L.dur });
    curStep = { L, t0 }; boxOnAt = -99;
    console.log(`[${t0.toFixed(1)}s] ${id}`);
    await fn();
    const rest = L.dur + GAP - (now() - t0); if (rest > 0) await sleep(rest * 1000);
    await unbox(); curStep = null;
  }
  // cutSeg: 영상에서 통째로 자를 구간 (계정 전환, 첫 화면 준비, 알림 처리). 줄과 줄 사이에서만 쓴다
  async function cutSeg(why, fn) { const t0 = now(); console.log(`[${t0.toFixed(1)}s] 자르기: ${why}`); await fn(); events.push({ type: 'cut', t0, t1: now(), why }); }
  // flow: 시연 시계가 흐르는 구간 (편집에서 ×4로 짧게 보여 줌)
  async function flow(why, fn) { const t0 = now(); console.log(`[${t0.toFixed(1)}s] 시계 흐름: ${why}`); await fn(); const t1 = now(); if (t1 - t0 > 0.5) events.push({ type: 'flow', t0, t1, why }); }

  // ---------- 공통 동작 ----------
  const btn = (name, opt = {}) => page.getByRole('button', { name, exact: true, ...opt });
  async function closeEmergencyPopup() {
    const t = page.getByText(/긴급·정지 알림/);
    if (await t.first().isVisible().catch(() => false)) await clickEl(btn('닫기').last(), 550);
  }
  async function closeSidebar() { const x = page.locator('button[aria-label="창 닫기"]'); if (await x.first().isVisible().catch(() => false)) await clickEl(x, 500); }
  // 말풍선은 한 번에 하나만 보인다 — 원하는 말풍선이 아닌 것은 [나중에]로 치우며 기다린다
  async function waitBubble(part, timeout = 60000) {
    const t0 = Date.now();
    const want = () => page.locator('[role=status]', { hasText: part }).getByRole('button', { name: '열기', exact: true }).first();
    while (Date.now() - t0 < timeout) {
      if (await want().isVisible().catch(() => false)) return;
      const later = page.locator('[role=status]').filter({ hasNotText: part }).getByRole('button', { name: '나중에', exact: true }).first();
      if (await later.isVisible().catch(() => false)) await later.click().catch(() => {});
      await sleep(1200);
    }
    throw new Error('말풍선을 못 찾음: ' + String(part));
  }
  async function openBubble(part, timeout = 60000) {
    await waitBubble(part, timeout);
    await clickEl(page.locator('[role=status]', { hasText: part }).getByRole('button', { name: '열기', exact: true }), 600);
  }
  // 계정 전환 = 새로 로그인 (사용자 메뉴로 바꾸면 이미 도착한 알림이 말풍선으로 다시 뜨지 않는다. 이 구간은 영상에서 자른다)
  async function switchTo(name) {
    await page.goto(APP); await sleep(1500);
    await clickEl(page.getByRole('button', { name: /아이디/ }), 500);
    await clickEl(page.getByRole('button', { name, exact: true }), 400); curUser = name;
    await page.getByPlaceholder(/비밀번호/).fill('0000').catch(() => {});
    await clickEl(btn('로그인'), 450);
    await page.locator('button[aria-label="축소"]').first().waitFor({ state: 'visible', timeout: 30000 }); await sleep(2500);
  }
  async function openMenu(top, sub) { await clickEl(page.getByText(`${top}▾`, { exact: true }), 550); await clickEl(page.getByText(sub, { exact: true }), 450); }
  const openProduction = (sub) => openMenu('생산', sub);
  async function fieldWholeLine() { await clickEl(btn('전체').first(), 500); await clickEl(page.locator('button[aria-label="축소"]'), 350); await clickEl(page.locator('button[aria-label="축소"]'), 350); }
  const simPanelOpen = async () => { await clickEl(btn('시연'), 550); await sleep(300); };
  const simPanelClose = async () => { await clickEl(page.locator('div.absolute', { hasText: '사건 버튼' }).getByRole('button', { name: '닫기', exact: true }), 450); };
  // 362 주의 알림 처리: 이브 → 알림 → 그 알림 → [처리 완료] (영상에서는 자른다)
  async function clearWarning362() {
    await clickEl(page.locator('button[aria-label^="이브 메뉴 열기"]'), 500);
    await clickEl(page.locator('.ma-menu-item').filter({ has: page.locator('.ma-menu-label', { hasText: /^알림$/ }) }), 450);
    await clickEl(page.getByText('VF2-01 362 공구 수명 한계 도달').first(), 450);
    await clickEl(btn('처리 완료'), 450); await sleep(1200);
    await closeSidebar(); await sleep(600);
  }
  const card = (name) => page.getByRole('heading', { name, exact: true }).first().locator('xpath=ancestor::*[contains(@class,"rounded")][1]');

  let failed = null;
  try {
    // ===================== 장면 1 : 3D 현장 =====================
    await cutSeg('첫 화면 준비', async () => { await page.goto(APP); await sleep(1200); await moveTo(960, 520, 300); });
    // 로그인은 말없이 (제목 카드가 로그인 화면으로 녹아든 뒤 바로 보이도록)
    await clickEl(page.getByRole('button', { name: /아이디/ }), 600);
    await clickEl(page.getByRole('button', { name: '작업자 주간 2', exact: true }), 450); curUser = '작업자 주간 2';
    await page.getByPlaceholder(/비밀번호/).fill('0000').catch(() => {});
    await clickEl(btn('로그인'), 500);
    await page.locator('button[aria-label="축소"]').first().waitFor({ state: 'visible', timeout: 30000 }); await sleep(2200);
    await step('s1a', async () => { await moveTo(960, 520, 900); });                       // 박스 없음
    // 말없이: 확대 → 왼쪽 끝(투입대)으로 이동해 두고, 줄이 시작되면 오른쪽(측정)으로 천천히 보여 준다
    await clickEl(page.locator('button[aria-label="확대"]'), 450); await clickEl(page.locator('button[aria-label="확대"]'), 350); await sleep(1500);
    await pan(300, 1700, 900); await pan(300, 1700, 900); await pan(1700, 700, 700); await sleep(500);
    await step('s1b', async () => { await moveTo(960, 560, 400); await pan(1700, 520, Math.max(2500, LINES.s1b.dur * 1000 - 900)); });
    await clickEl(btn('전체').first(), 600); await sleep(2800);                           // 전체 보기로 돌아와 멈출 때까지
    await step('s1c', async () => { await boxRect(325, 312, 1497, 100, true, 0); await moveTo(1000, 520, 900); });
    await clickEl(btn('위').first(), 600); await sleep(3200);                              // [위]로 옮긴 뒤 멈춘 다음에 박스
    await step('s1d', async () => { await boxRect(285, 560, 1580, 74, true, 0); await moveTo(960, 690, 900); });
    await clickEl(btn('전체').first(), 550); await sleep(1500);
    await step('s1e', async () => {
      for (const [i, k] of ['생산', '예측', 'OEE'].entries()) { const f = page.locator(`[data-summary-field="${k}"]`); await boxEl(f.first(), { pad: 6, k: i }); await hoverBeside(f, 600); }
    });
    await step('s1f', async () => { await unbox(); await moveTo(960, 520, 900); });

    // ===================== 장면 2 : 브리핑 → 시간 흐름 =====================
    await step('s2a', async () => {
      const bub = page.locator('[role=status]', { hasText: '이번 교대 브리핑' });
      await boxEl(bub, { pad: 6, k: 0 }); await openBubble('이번 교대 브리핑');
      await boxEl(page.getByText('이번 교대 목표', { exact: true }).locator('xpath=..'), { pad: 6, k: 1 });
      await boxEl(page.getByText(/^지난 교대/).first().locator('xpath=..'), { pad: 6, k: 2 });
    });
    await step('s2b', async () => {
      const list = page.getByRole('heading', { name: /먼저 챙길 일/ }).first().locator('xpath=ancestor::*[count(.//input[contains(@class,"ma-check")]) >= 3][1]');
      await boxEl(list, { pad: 8, k: 0 });
    });
    await step('s2c', async () => {
      const t05 = page.locator('label:has(input.ma-check)', { hasText: 'T05' }).first().locator('xpath=..');
      const oil = page.locator('label:has(input.ma-check)', { hasText: '윤활유 저장소' }).first().locator('xpath=..');
      await boxEl(t05, { pad: 4, k: 0 }); await hoverBeside(t05, 500);
      await boxEl(oil, { pad: 4, k: 1 }); await hoverBeside(oil, 500);
    });
    await closeSidebar(); await simPanelOpen();
    await step('s2d', async () => { await boxEl(btn('×180'), { pad: 6, k: 0 }); await clickEl(btn('×180'), 550); await simPanelClose(); });
    await flow('시간 흐름 (×180)', async () => {
      await unbox(); await setClock({ speed: 180 }); await until(async () => hhmm(await clock()) >= '10:44', 90000);
      await setClock({ speed: 60 });
      await until(async () => (await (await fetch(SIM + 'line/twin')).json()).alarms.some((a) => a.alarm_code === '362'), 60000);
      await setClock({ speed: 1 });
      await page.locator('[role=status]', { hasText: '362' }).first().waitFor({ state: 'visible', timeout: 15000 });
    });

    // ===================== 장면 3 : 362 선제 알림 · 지침카드 =====================
    const band362 = () => page.locator('[role=status]', { hasText: '362' }).first();
    await step('s3a', async () => { await boxEl(band362(), { pad: 6, k: 0 }); await moveTo(900, 230, 800); });
    await step('s3b', async () => { const g = band362().getByRole('button', { name: '지침카드', exact: true }); await boxEl(g, { pad: 6, k: 0 }); await hoverEl(g, 700); });
    await step('s3c', async () => {
      await unbox();
      await clickEl(band362().getByRole('button', { name: '지침카드', exact: true }), 500);
      await page.getByRole('heading', { name: '먼저 할 일', exact: true }).first().waitFor(); await sleep(700);
    });
    await step('s3d', async () => {
      // 자막이 가리지 않게 "생산 영향" 칸을 화면 위쪽으로 올려 놓고 박스를 친다
      const eff = card('생산 영향');
      await eff.evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'smooth' })); await sleep(900);
      await boxEl(eff, { pad: 6, k: 0, scroll: false });
      const lot = page.getByText(/^LOT-2610/).first(); await boxEl(lot, { pad: 8, k: 2 }); await hoverBeside(lot, 600);
    });
    await step('s3e', async () => { await unbox(); await clickEl(btn('닫기').first(), 650); });
    // 362 알림을 처리해 VF2-01 주의 표시를 없앤다 — 영상에서는 이 구간을 자른다 (충돌 뒤 "정상 복귀"가 정상으로 보이게)
    await cutSeg('362 알림 처리', clearWarning362);
    await flow('다음 사건을 누를 수 있을 때까지 (×60)', async () => {
      await setClock({ speed: 60 }); await until(async () => !(await clock()).buttons.S1, 60000); await setClock({ speed: 1 });
    });

    // ===================== 장면 4 : S1 충돌 =====================
    await simPanelOpen();
    await step('s4a', async () => {
      const s1 = page.getByRole('button', { name: /^S1 충돌/ });
      await boxEl(s1, { pad: 6, k: 0 }); await sleep(300); await clickEl(s1, 600);
      await simPanelClose();
    });
    await flow('충돌 → 정지 알람 (×180)', async () => {
      await setClock({ speed: 180 });
      await page.getByText(/긴급·정지 알림/).waitFor({ state: 'visible', timeout: 60000 }); await sleep(300);
    });
    await step('s4b', async () => { await moveTo(960, 780, 800); });                      // 긴급 팝업은 박스 없이
    await clickEl(btn('닫기').last(), 600); await sleep(900);
    await openProduction('현장 모니터'); await sleep(900); await fieldWholeLine(); await sleep(1800);      // 다음 줄(병목·재공)을 말하기 전에 현장 모니터를 열어 둔다
    await step('s4c', async () => {
      await setClock({ speed: 60 });
      await boxRect(822, 398, 162, 76, true, 0);                                         // 병목이 옮겨 온 VF2-01 카드
      await boxRect(668, 688, 170, 58, true, 1);                                         // 앞 공정이 한도에 막힌 WIP-2 재공
    });
    await setClock({ speed: 1 }); await clickEl(btn('홈'), 600); await sleep(1200);
    await step('s4d', async () => {
      const strip = page.locator('[role=status]', { hasText: '992' }).first();
      await boxEl(strip, { pad: 6, k: 0 }); await clickEl(strip.getByRole('button', { name: '지침카드', exact: true }), 600);
      await page.getByRole('heading', { name: '먼저 할 일', exact: true }).first().waitFor();
      await boxEl(page.getByText(/원인|가능한 원인/).first(), { pad: 10, k: 1 });          // "원인은 …" 낱말에 맞춰 원인 칸을 일찍 잡는다
    });
    await step('s4e', async () => {
      await boxEl(page.getByText(/축 부하가 갑자기 오른 뒤에 뜨면/).first(), { pad: 10, k: 0 });
      await boxEl(page.getByText(/알람 이력과 축 부하를 봐|알람 이력과 축 부하를 본다/).first(), { pad: 10, k: 1 });
    });
    await step('s4f', async () => {
      const lot = page.getByText(/^LOT-2610/).first(), spd = page.getByText(/라인 속도 절반/).first();
      await boxEl(lot, { pad: 8, k: 0 }); await boxEl(spd, { pad: 8, k: 1 });
    });
    await clickEl(btn('닫기').first(), 650);
    await cutSeg('계정 전환 → 보전 담당 1', async () => { await switchTo('보전 담당 1'); await closeEmergencyPopup(); await sleep(500); });

    // ===================== 장면 5 : 작업지시서 · 질문 =====================
    await step('a5', async () => { await sleep(300); });
    await step('s5a', async () => {
      const b = page.locator('[role=status]', { hasText: /작업지시서 초안/ }); await boxEl(b, { pad: 6, k: 0 }); await sleep(900);
      await clickEl(b.getByRole('button', { name: '열기', exact: true }), 600);
      await page.getByText(/정비 작업지시서 MW-/).first().waitFor(); await sleep(600);
    });
    // 말없이: 고칠 곳을 고쳐 저장해 둔다 (줄은 증상·점검 순서·안전 단계 박스, 이어서 수정 이력을 말한다)
    { const ta = page.locator('textarea').first(); await clickEl(ta, 600); await page.keyboard.press('Control+End'); await page.keyboard.type(' 충돌 의심, 잠금·표지 후 점검.', { delay: 30 }); await clickEl(btn('저장'), 550); await sleep(500); }
    await step('s5b', async () => {
      await boxEl(page.locator('textarea').first(), { pad: 8, k: 0 });
      await boxEl(card('작업 순서'), { pad: 4, k: 1 });
      await boxEl(card('안전'), { pad: 4, k: 2, center: true });
      const h = page.getByRole('button', { name: /^수정 이력/ });
      await boxEl(h, { pad: 6, k: 3 }); await clickEl(h, 600); await sleep(900);
      // 수정 이력 화면에서는 고친 내용(v1)을 보여 준다
      const v1 = page.getByText(/v1\s*·\s*수정/).first();
      if (await v1.waitFor({ state: 'visible', timeout: 4000 }).then(() => true, () => false)) { await boxEl(v1, { pad: 6 }); await clickEl(v1, 600); await sleep(1800); }
      else console.warn('  ! 수정 이력에서 v1 줄을 못 찾음');
      await unbox(); await page.goBack(); await sleep(900);
    });
    await step('s5c', async () => {
      await setClock({ paused: true });
      await clickEl(page.locator('button[aria-label^="이브 메뉴 열기"]'), 600);
      await clickEl(page.locator('.ma-menu-item').filter({ has: page.locator('.ma-menu-label', { hasText: /^채팅$/ }) }), 500);
      const inp = page.locator('#ma-input'); await clickEl(inp, 500);                     // 입력란에는 박스를 치지 않는다
      await page.keyboard.type('모터 케이블 저항은 어떻게 재?', { delay: 70 }); await sleep(400); await page.keyboard.press('Enter');
    });
    await step('s5d', async () => { await unbox(); await page.locator('button', { hasText: '출처' }).first().waitFor({ state: 'visible', timeout: 90000 }); await sleep(800); });
    await step('s5e', async () => {
      await setClock({ paused: false }); await setClock({ speed: 1 });
      const tg = page.locator('button', { hasText: '출처' }).first(); await boxEl(tg, { pad: 8, k: 0 }); await clickEl(tg, 600); await sleep(300);
      const link = page.locator('button', { hasText: /DOC-03 Rev\.1/ }).first(); await boxEl(link, { pad: 8, k: 1 }); await clickEl(link, 600);
      await page.getByText('가능한 원인', { exact: true }).first().waitFor({ timeout: 15000 }).catch(() => {});
    });
    await step('s5f', async () => {
      // 출처 팝업을 열어 둔 채 잠금·표지와 안전 문구가 어디 있는지 보여 준다
      await sleep(600);
      const lock = page.getByText(/잠금·표지 필요/).first(); await boxEl(lock, { pad: 8, k: 0 });
      const hv = page.getByText(/고전압/).first(); await boxEl(hv, { pad: 8, k: 1 });
      await sleep(1200);
    });
    await clickEl(page.getByRole('button', { name: /닫기 → 원래 화면/ }), 650); await sleep(500);
    await closeSidebar();
    await cutSeg('계정 전환 → 반장 주간', async () => { await switchTo('반장 주간'); await closeEmergencyPopup(); await sleep(400); });

    // ===================== 장면 6 : 승인 → 작업기록 → 확정 → 복귀 =====================
    await step('a6', async () => { await sleep(300); });
    await step('s6a', async () => {
      const b = page.locator('[role=status]', { hasText: /승인 요청|승인해 주세요/ }); await boxEl(b, { pad: 6, k: 0 }); await sleep(700);
      await clickEl(b.getByRole('button', { name: '열기', exact: true }), 600);
      await btn('승인').first().waitFor({ timeout: 15000 });
    });
    await step('s6b', async () => {
      await boxEl(btn('승인').first(), { pad: 8, k: 0 }); await sleep(500); await clickEl(btn('승인').first(), 550); await unbox();
      await sleep(1600);                                                                   // "승인할까요?" 확인창이 읽히게 조금 더 둔다
      await clickEl(btn('승인').last(), 550); await sleep(900);
    });
    await cutSeg('계정 전환 → 보전 담당 1', async () => { await switchTo('보전 담당 1'); await sleep(300); });
    await step('a6c', async () => {
      const bb = page.locator('[role=status]', { hasText: /작업지시서.*배정|배정됐어요/ }); await bb.first().waitFor({ state: 'visible', timeout: 20000 });
      await sleep(2200);                                                                   // 배정 말풍선이 보이게 둔다
      await openBubble(/작업지시서.*배정|배정됐어요/); await btn('작업 시작').waitFor({ timeout: 15000 });
      const start = btn('작업 시작'); await hoverEl(start, 500); await sleep(1200);          // 작업 시작 버튼을 조금 더 보여 준다
    });
    await step('s6c', async () => {
      await clickEl(btn('작업 시작'), 450);
      const memo = page.getByPlaceholder(/예: 서보 케이블/); await boxEl(memo, { pad: 8, k: 0 });
    });
    // 말없이: 메모를 적고 [채우기] — 비서가 정리하는 몇 초는 편집에서 줄인다
    { const memo = page.getByPlaceholder(/예: 서보 케이블/); await clickEl(memo, 400);
      await page.keyboard.type('서보 케이블 커넥터 느슨함이 원인. 커넥터 다시 조임. 엔드밀 교체.', { delay: 22 });
      await clickEl(btn('메모로 원인·조치 채우기'), 500); await sleep(4500); }
    await step('s6c2', async () => {
      // 원인·조치 칸과 사용 부품·공구 칸을 큰 박스 하나로
      const both = page.getByRole('heading', { name: /원인|조치/ }).first().locator('xpath=ancestor::*[contains(@class,"rounded")][1]');
      await boxEl(both, { pad: 10, k: 0 }); await sleep(600);
    });
    await step('s6d', async () => {
      await setClock({ speed: 1 });
      await boxEl(page.getByRole('heading', { name: '수행 단계 체크', exact: true }), { pad: 8, k: 0 });
      const rows = page.locator('label:has(input[type=checkbox])');
      for (let i = 0; i < 2; i++) { await clickEl(rows.nth(i), 200); }
      await clickEl(btn('모두 체크'), 350);
      await boxEl(btn('확정').first(), { pad: 8, k: 1 }); await sleep(300); await clickEl(btn('확정').first(), 550); await unbox();
    });
    await clickEl(btn('확정').last(), 550); await sleep(500); await setClock({ paused: true });
    await openProduction('현장 모니터'); await sleep(900); await fieldWholeLine(); await sleep(1500);
    await step('s6e', async () => {
      await setClock({ paused: false }); await setClock({ speed: 60 });
      await boxRect(822, 398, 162, 76, true, 0);
      await flow('설비 복귀 (×60)', async () => {
        await until(async () => (await (await fetch(SIM + 'line/twin')).json()).equipment['VF2-01'].state_code === 'RUN', 40000);
        await sleep(1200); await setClock({ speed: 1 });
      });
    });
    // 쓴 부품은 재고에서 빠진다 → 재고 화면의 "오늘 사용"과 거래 기록을 보여 준다
    await openMenu('재고', '재고'); await sleep(1200);
    await step('s6g', async () => {
      const used = page.getByText(/오늘 사용/).first();
      await boxEl(used, { pad: 10, k: 0 }); await hoverBeside(used, 500);
      const tx = page.getByRole('heading', { name: '거래 기록', exact: true }).first().locator('xpath=ancestor::*[contains(@class,"rounded")][1]');
      await boxEl(tx, { pad: 6, k: 1 }); await sleep(600);
    });
    await clickEl(page.getByText('홈', { exact: true }).first(), 600);
    await cutSeg('계정 전환 → 반장 주간', async () => { await switchTo('반장 주간'); await sleep(300); });
    await step('a6f', async () => { const b = page.locator('[role=status]', { hasText: /작업기록서.*(확인|확정)|확정됨 — 확인해/ }); await boxEl(b, { pad: 6 }); });
    await step('s6f', async () => {
      const b = page.locator('[role=status]', { hasText: /작업기록서.*(확인|확정)|확정됨 — 확인해/ });
      await clickEl(b.getByRole('button', { name: '열기', exact: true }), 600);
      await boxEl(btn('확인').first(), { pad: 8, k: 0 }); await sleep(300); await clickEl(btn('확인').first(), 550);
    });

    // ===================== 장면 7 : 교대 보고서 · 일일 보고서 =====================
    await clickEl(page.getByText('홈', { exact: true }).first(), 600); await sleep(500); await simPanelOpen();
    await step('s7a', async () => {
      const b18 = btn(/^1[78]:00으로$/), b21 = btn(/^2[01]:00으로$/);    // 화면 담당이 버튼 글을 18:00·21:00으로 고치기 전에는 17:00·20:00
      await boxEl(b18, { pad: 6, k: 0 }); await clickEl(b18, 450);
      await boxEl(b21, { pad: 6, k: 1 }); await clickEl(b21, 450); await simPanelClose();
    });
    await waitBubble(/교대 보고서/);                                                       // 스케줄러가 초안을 만들 때까지 (이 기다림은 편집에서 줄인다)
    await step('s7a2', async () => {
      const bub = page.locator('[role=status]', { hasText: /교대 보고서/ });
      await boxEl(bub, { pad: 6, k: 0 }); await openBubble(/교대 보고서/);
      await page.getByRole('heading', { name: '교대 보고서', exact: true }).first().waitFor(); await sleep(400);
    });
    await step('s7b', async () => {
      await boxEl(card('생산'), { pad: 4, k: 0 });
      await boxEl(card('필수 정지'), { pad: 4, k: 1 });
      await boxEl(card('정비'), { pad: 4, k: 2 });
      await boxEl(card('인계 사항'), { pad: 4, k: 3 });
    });
    await step('s7c', async () => {
      const c = btn('확정').first(); await boxEl(c, { pad: 8, k: 0 }); await sleep(300); await clickEl(c, 550); await unbox();
      await clickEl(btn('확정').last(), 550); await sleep(500);
    });
    await cutSeg('계정 전환 → 공장 관리자', async () => { await switchTo('공장 관리자'); await sleep(300); });
    await step('a7', async () => { await sleep(300); });
    await step('s7d', async () => {
      await openBubble('일일 보고서'); await page.getByRole('heading', { name: '일일 보고서', exact: true }).first().waitFor(); await sleep(500);
    });
    await step('s7d2', async () => {                                                      // 실적·불량·OEE (하루 생산 칸 전체)
      const nums = page.getByText('하루 생산', { exact: true }).first().locator('xpath=ancestor::*[contains(@class,"rounded")][1]');
      await boxEl(nums, { pad: 6, k: 0 }); await hoverBeside(nums, 500);
    });
    await step('s7d3', async () => {                                                      // 오늘의 문제, 재고 부족
      const prob = page.getByText('오늘의 문제', { exact: true }).first().locator('xpath=ancestor::*[contains(@class,"rounded")][1]');
      await boxEl(prob, { pad: 6, k: 0 });
      const low = page.getByText('재고 부족', { exact: true }).first().locator('xpath=ancestor::*[contains(@class,"rounded")][1]');
      await boxEl(low, { pad: 6, k: 1 });
    });
    await step('s7e', async () => {
      await unbox(); await wheel(500, 600); await sleep(200); await wheel(500, 600);
      const c = btn('확정').first(); await boxEl(c, { pad: 8, k: 0 }); await sleep(300); await clickEl(c, 550); await unbox();
      await clickEl(btn('확정').last(), 550);
    });
    await step('s7z', async () => { await sleep(300); });
    await sleep(1500);
  } catch (e) {
    failed = e;
    console.error('실패:', e.message);
    await page.screenshot({ path: path.join(WORK, 'fail.png') }).catch(() => {});
  }

  const total = now();
  fs.writeFileSync(path.join(WORK, 'timeline.json'), JSON.stringify({ total, events, failed: failed ? String(failed.message) : null }, null, 1));
  const vpath = await page.video().path();
  await ctx.close(); await browser.close();
  const out = path.join(RAW, 'raw.webm'); fs.renameSync(vpath, out);
  console.log(failed ? '--- 실패로 끝남 ---' : '--- 촬영 끝 ---', `원본 ${total.toFixed(1)}초`, out);
})();
