// 직원 관리 백엔드 길 확인 (2026-10-25) — 서버 없이 fetch를 가로채 backendApi.ts가 부르는 주소·방법·본문과 401 처리를 본다.
//   실행 (frontend 폴더에서): node tools/backend_staff_check.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import ts from 'typescript';

process.env.NEXT_PUBLIC_MOM_API = 'http://api.test';
process.env.NEXT_PUBLIC_MOM_BACKEND = '1';
const src = (n) => readFileSync(fileURLToPath(new URL('../src/shell/' + n, import.meta.url)), 'utf8');
const toJs = (code) => ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const url = (js) => 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');
const genUrl = url(toJs(src('generated.ts')));
const dataUrl = url(toJs(src('data.ts')).replace(/from ['"]\.\/generated['"]/, `from '${genUrl}'`));
const B = await import(url(toJs(src('backendApi.ts').replace(/^'use client';/, '')).replace(/from ['"]\.\/data['"]/, `from '${dataUrl}'`)));

const calls = [];
let status = 200;
globalThis.fetch = async (u, o = {}) => {
  calls.push({ u: String(u), m: o.method ?? 'GET', b: o.body ? JSON.parse(o.body) : undefined });
  const login = String(u).endsWith('/api/auth/login');
  const body = login ? { access_token: 't', user_id: 'U13', user_name: '새직원', role_code: 'OPR', process_codes: ['OP-30'], shift_type: 'NIGHT' } : { ok: true };
  return { ok: status < 400, status, json: async () => (status === 401 ? { code: 'UNAUTHORIZED', message: '로그인이 필요합니다' } : body) };
};
let fired = 0;
globalThis.window = { dispatchEvent: (e) => { if (e.type === B.UNAUTHORIZED_EVENT) fired++; } };
const last = () => calls[calls.length - 1];

// 로그인은 사용자 정보를 돌려준다 (박힌 목록에 없는 새 직원도)
const j = await B.backendLogin('u13', 'password1');
assert.equal(j.user_name, '새직원'); assert.equal(B.backendUserId(), 'U13');

await B.backendRoute('staff?role=MGR&period=all');
assert.equal(last().u, 'http://api.test/api/staff?period=all');                      // role은 빼고
await B.backendRoute('staff?role=MGR&period=7d&include_inactive=true');
assert.equal(last().u, 'http://api.test/api/staff?period=7d&include_inactive=true');
await B.backendRoute('staff/U02/activity?role=MGR&period=30d');
assert.equal(last().u, 'http://api.test/api/staff/U02/activity?period=30d');
await B.backendRoute('users');
assert.equal(last().u, 'http://api.test/api/users');

await B.backendRoute('staff/assignments', { role: 'MGR', user_id: 'U12', reason: 'r', changes: [{ user_id: 'U02', home_shift_type: 'NIGHT', procs: ['OP-30'] }] });
assert.deepEqual([last().m, last().u, last().b], ['PATCH', 'http://api.test/api/staff/assignments', { changes: [{ user_id: 'U02', home_shift_type: 'NIGHT', procs: ['OP-30'] }], reason: 'r' }]);
await B.backendRoute('staff', { user_name: 'a', role_code: 'MNT', home_shift_type: 'DAY', password: 'password1' });
assert.deepEqual([last().m, last().u], ['POST', 'http://api.test/api/staff']);
await B.backendRoute('staff/U13', { is_active: false });
assert.deepEqual([last().m, last().u, last().b], ['PATCH', 'http://api.test/api/staff/U13', { is_active: false }]);

// 401 → 토큰 버림 + 로그인 화면으로 보내는 알림
status = 401;
await assert.rejects(B.backendRoute('users'), (e) => e.status === 401);
assert.equal(fired, 1); assert.equal(B.backendUserId(), null);

console.log('backend_staff_check 통과');
