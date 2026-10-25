// 사용: node tools/shot.js <html 경로> <png 경로>  — 1920x1080 으로 찍는다 (이 PC의 Edge 사용)
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const path = require('path');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto(pathToFileURL(path.resolve(process.argv[2])).href);
  await p.waitForTimeout(500);
  await p.screenshot({ path: process.argv[3] });
  await b.close();
})();
