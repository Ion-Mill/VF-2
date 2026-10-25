// 화면 → 백엔드 전환(C2) 대조 — 같은 시각에 시연 서버가 주는 값과 backendApi.ts(백엔드 → 화면 모양)가 주는 값을 칸마다 비교한다.
//   실행 (frontend 폴더에서, 두 서버가 켜진 채로 — 시연 서버는 일시정지해 두면 숫자가 그대로 맞는지 보기 쉽다):
//     node tools/backend_adapter_check.mjs [시연서버=http://127.0.0.1:8765] [백엔드=http://127.0.0.1:8000] [사용자=U10] [주소…]
//   백엔드는 그 시연 서버의 DB 중계를 받는 DB여야 한다 (같은 공장). 시연 계정 비밀번호 0000 (Login.tsx DEMO_PW).
//   나오는 것: 주소마다 ① 시연 서버에만 있는 칸(화면이 못 받는 칸) ② 백엔드에만 있는 칸 ③ 값이 다른 칸(숫자는 차이) — 읽기만, 아무것도 바꾸지 않는다.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const [SIM = 'http://127.0.0.1:8765', API = 'http://127.0.0.1:8000', USER = 'U10', ...only] = process.argv.slice(2);
process.env.NEXT_PUBLIC_MOM_API = API;
process.env.NEXT_PUBLIC_MOM_BACKEND = '1';

const src = (n) => readFileSync(fileURLToPath(new URL('../src/shell/' + n, import.meta.url)), 'utf8');
const toJs = (code) => ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const url = (js) => 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');
const genUrl = url(toJs(src('generated.ts')));
const dataUrl = url(toJs(src('data.ts')).replace(/from ['"]\.\/generated['"]/, `from '${genUrl}'`));
const B = await import(url(toJs(src('backendApi.ts').replace(/^'use client';/, '')).replace(/from ['"]\.\/data['"]/, `from '${dataUrl}'`)));

await B.backendLogin(USER, '0000');
const simGet = async (p) => { const r = await fetch(`${SIM}/api/${p}`); return r.json(); };

const PATHS = only.length ? only : ['line/twin', 'stream/events?after=0', 'replay?from=2026-10-01T08:00:00%2B09:00&to=2026-10-01T08:40:00%2B09:00'];
const type = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v);
const IGNORE = new Set(['is_synthetic', 'live_from', 'seq', 'run_id', 'since_at', 'cycle_progress', 'slow', 'buttons']);

function diff(a, b, path, out) {
  const ta = type(a), tb = type(b);
  if (ta !== tb) { if (!(ta === 'null' || tb === 'null')) out.push(['타입', path, `${ta} ≠ ${tb}`]); else out.push(['값', path, `${JSON.stringify(a)?.slice(0, 60)} | ${JSON.stringify(b)?.slice(0, 60)}`]); return; }
  if (ta === 'object') {
    for (const k of Object.keys(a)) { if (IGNORE.has(k)) continue; if (!(k in b)) out.push(['시연에만', `${path}.${k}`, '']); else diff(a[k], b[k], `${path}.${k}`, out); }
    for (const k of Object.keys(b)) if (!(k in a) && !IGNORE.has(k)) out.push(['백엔드에만', `${path}.${k}`, '']);
  } else if (ta === 'array') {
    if (a.length !== b.length) out.push(['개수', path, `${a.length} | ${b.length}`]);
    for (let i = 0; i < Math.min(a.length, b.length, 3); i++) diff(a[i], b[i], `${path}[${i}]`, out);
  } else if (a !== b) {
    out.push(['값', path, ta === 'number' ? `${a} | ${b} (차이 ${Math.round((b - a) * 10) / 10})` : `${String(a).slice(0, 50)} | ${String(b).slice(0, 50)}`]);
  }
}

let total = 0;
for (const p of PATHS) {
  const [s, b] = await Promise.all([simGet(p), B.backendRoute(p)]);
  const out = [];
  diff(s, b, p.split('?')[0], out);
  total += out.length;
  console.log(`\n== ${p}  (다른 곳 ${out.length})`);
  for (const [k, where, what] of out.slice(0, 80)) console.log(`  ${k.padEnd(5)} ${where}  ${what}`);
  if (out.length > 80) console.log(`  … ${out.length - 80}개 더`);
}
console.log(`\n다른 곳 합계 ${total} (같아야 하는 것: 칸 이름·타입. 숫자는 계산식 차이를 봄)`);
