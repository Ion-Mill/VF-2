const { chromium } = require('playwright');
(async () => {
  for (const headless of [true, false]) {
    const b = await chromium.launch({ channel: 'msedge', headless, args: ['--enable-gpu-rasterization', '--ignore-gpu-blocklist'] });
    const c = await b.newContext({ viewport: { width: 1920, height: 1080 } });
    const p = await c.newPage();
    await p.goto('http://localhost:3000'); await p.waitForTimeout(1500);
    await p.getByRole('button', { name: /아이디/ }).click(); await p.getByRole('button', { name: '작업자 주간 2', exact: true }).click();
    await p.getByRole('button', { name: '로그인', exact: true }).click(); await p.waitForTimeout(5000);
    const fps = await p.evaluate(() => new Promise((res) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 > 4000) res(n / 4); else requestAnimationFrame(f); }; requestAnimationFrame(f); }));
    console.log(headless ? 'headless' : 'headed  ', 'fps ≈', fps.toFixed(1));
    await b.close();
  }
})();
