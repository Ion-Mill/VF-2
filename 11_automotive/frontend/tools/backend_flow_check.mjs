// 화면 → 백엔드 흐름 점검 (2026-10-24) — 화면이 쓰는 코드(backendApi.ts·backendDocs.ts) 그대로 백엔드를 불러
// ① 역할 4개로 화면이 읽는 주소를 모두 읽고 ② 시연 대본 S1(충돌 → 고장 → 작업지시서 → 작업기록서 → 복귀)을 끝까지 돌린다.
//
//   실행 (frontend 폴더에서, 백엔드·시연 서버(DB 중계 켜짐)가 켜진 채로):
//     node tools/backend_flow_check.mjs [백엔드=http://127.0.0.1:8000] [--read-only]
//   ⚠ --read-only 가 아니면 **DB에 쓴다**(시연 [처음으로] → S1 → 작업지시서·기록 확정). 공용 DB에서는 시연 진행자만, 시연 중에는 돌리지 않는다.
//   시연 계정 비밀번호 0000 (Login.tsx DEMO_PW). 끝에 실패 수를 찍고 실패가 있으면 종료 코드 1.
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

const args = process.argv.slice(2);
const READ_ONLY = args.includes('--read-only');
const API = args.find((a) => !a.startsWith('--')) ?? 'http://127.0.0.1:8000';
process.env.NEXT_PUBLIC_MOM_API = API;
process.env.NEXT_PUBLIC_MOM_BACKEND = '1';

// ---- 화면 코드 불러오기 (TS → JS, 임시 폴더) ----
const dir = mkdtempSync(join(tmpdir(), 'mom-flow-'));
for (const n of ['generated', 'data', 'model', 'backendApi', 'backendDocs']) {
  const src = readFileSync(fileURLToPath(new URL(`../src/shell/${n}.ts`, import.meta.url)), 'utf8').replace(/^'use client';/, '');
  const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, verbatimModuleSyntax: false } }).outputText
    .replace(/from ['"]\.\/(\w+)['"]/g, "from './$1.mjs'");
  writeFileSync(join(dir, `${n}.mjs`), js);
}
const B = await import(pathToFileURL(join(dir, 'backendApi.mjs')).href);
const D = await import(pathToFileURL(join(dir, 'backendDocs.mjs')).href);

let fail = 0;
const ok = (msg) => console.log(`  ✓ ${msg}`);
const bad = (msg) => { fail += 1; console.log(`  ✗ ${msg}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const as = async (u) => { await B.backendLogin(u, '0000'); };
async function waitFor(what, fn, ms = 90000) {
  const t0 = Date.now();
  for (;;) {
    const v = await fn().catch(() => null);
    if (v) return v;
    if (Date.now() - t0 > ms) { bad(`${what} — ${ms / 1000}초 안에 안 됨`); return null; }
    await sleep(1500);
  }
}

// ---- ① 읽기: 화면이 부르는 주소 전부 × 역할 4개 ----
console.log(`\n① 읽기 (${API})`);
const USERS = { OPR: 'U01', MNT: 'U07', SUP: 'U10', MGR: 'U12' };
await as('U10');
const tw0 = await B.backendRoute('line/twin');
const sid = tw0.shift?.shift_id;
const anyLot = (await B.backendRoute('lots')).lots?.at(-1)?.lot_no;
// 날짜는 데이터에서 (2026-10-25 — 9월 데이터·최종용·영상용 어느 것이든): 가장 최근 일일 보고서, 지금 교대 시작부터 30분 재생
const dl = await B.backendRoute('reports/daily');
const lastDay = (Array.isArray(dl) ? dl : dl.reports ?? []).map((d) => String(d.work_date ?? '')).filter(Boolean).sort().at(-1);
const r0 = new Date(tw0.shift?.start_at ?? Date.now()), r1 = new Date(r0.getTime() + 30 * 60000);
const enc = (d) => encodeURIComponent(d.toISOString());
const READS = ['line/twin', 'stream/events?after=0', `replay?from=${enc(r0)}&to=${enc(r1)}`,
  'reports/shift', `reports/shift/${sid}`, 'reports/daily', `reports/daily/${lastDay}`, 'documents/revisions', 'notifications/past-open',
  'notifications/rules', 'maint/history', 'maint/pm-schedule', 'internal-docs', 'internal-docs/DOC-03', 'users', 'lots', `lots?lot=${anyLot}`,
  `inspection/results?lot=${anyLot}`, 'inspection/cmm-imports', 'quality/summary', 'inventory', 'shipments', 'tools', 'settings'];
for (const [role, u] of Object.entries(USERS)) {
  await as(u);
  const errs = [];
  for (const p of READS) {
    try { await B.backendRoute(p); } catch (e) { if (!(role === 'OPR' && /reports\/daily\//.test(p) && e.status === 403)) errs.push(`${p} → ${e.status ?? ''} ${e.code ?? ''} ${e.message}`); }
  }
  try { const d = await D.loadDocs(); if (!Array.isArray(d.wos) || !Array.isArray(d.notices)) errs.push('loadDocs 모양'); } catch (e) { errs.push(`loadDocs → ${e.message}`); }
  if (errs.length) errs.forEach((x) => bad(`${role} ${x}`)); else ok(`${role}(${u}) 주소 ${READS.length}개 + 문서·알림 목록`);
}

if (READ_ONLY) { console.log(`\n실패 ${fail}`); process.exit(fail ? 1 : 0); }

// ---- ② 시연 대본 S1: 충돌 → 고장 → 작업지시서(DB 초안) → 승인 → 작업 → 작업기록서 확정 → 반장 확인 → 설비 복귀 ----
console.log('\n② 시연 대본 S1 (DB에 씀)');
await as('U10');
await B.backendRoute('sim/reset', {});
// 기준점 = 그날 첫 교대 시작 (옛 9월 데이터 08:00, 영상용·최종용 09:00 — 2026-10-25 시각을 박지 않음)
await waitFor('[처음으로] 뒤 DB가 교대 시작으로', async () => {
  const t = await B.backendRoute('line/twin');
  const st = t.shift?.start_at, at = t.clock?.sim_at;
  return st && at && new Date(at) - new Date(st) <= 20 * 60000 && (t.alarms ?? []).length === 0 ? t : null;   // 영상용은 ×60으로 흘러 20분 여유
}, 60000) && ok('[처음으로] — 시뮬레이터·DB 함께 교대 시작');
const before = await D.loadDocs();
await B.backendRoute('sim/clock', { speed: 60 });
// S1은 VF2-01이 가공 중일 때만 걸린다 (아니면 409 INVALID_STATE "대상 설비 가공 중 아님")
await waitFor('S1 시작 (VF2-01 가공 중)', () => B.backendRoute('sim/inject', { scenario_code: 'S1' }).then(() => true).catch((e) => {
  if (e.code === 'INVALID_STATE') return null; throw e;
}), 120000) && ok('S1 시작 (배속 ×60)');

// 고장이 DB에 들어오고(중계), DB가 작업지시서 초안을 만든다
const twDown = await waitFor('VF2-01 고장(DOWN)·알람 992가 DB에', async () => {
  const t = await B.backendRoute('line/twin');
  return t.equipment?.['VF2-01']?.state_code === 'DOWN' && (t.alarms ?? []).some((a) => a.alarm_code === '992') ? t : null;
}, 180000);
if (twDown) ok(`VF2-01 DOWN, 알람 ${(twDown.alarms ?? []).map((a) => a.alarm_code).join('·')}`);
const docs1 = await waitFor('DB가 만든 작업지시서 초안', async () => {
  const d = await D.loadDocs();
  return d.wos.some((w) => !before.wos.some((x) => x.no === w.no)) ? d : null;
}, 60000);
const wo = docs1?.wos.find((w) => !before.wos.some((x) => x.no === w.no));
if (wo) ok(`작업지시서 ${wo.no} (${wo.state}) 알람 ${wo.code} 단계 ${wo.steps.length}`);
if (docs1 && docs1.wos.filter((w) => !before.wos.some((x) => x.no === w.no)).length !== 1) bad(`새 작업지시서가 ${docs1.wos.filter((w) => !before.wos.some((x) => x.no === w.no)).length}장 (1장이어야 함)`);
const urgent = docs1?.notices.filter((n) => !n.past && !n.handled) ?? [];
ok(`반장 미처리 알림 ${urgent.length}건: ${[...new Set(urgent.map((n) => n.rule))].join(', ')}`);

if (wo) {
  // 보전(담당): 초안 고치기 → 반장: 담당 확인·승인 (권한: 고치기 = MNT, 배정·승인 = SUP — db/seed/20_roles_permissions.sql)
  try {
    await as('U07');
    let d = await D.loadDocs(); let w = d.wos.find((x) => x.no === wo.no);
    await D.saveWo(w, { ...w, title: w.title + ' (보전 확인)', revisions: [{ reason: '제목 보충' }] });
    await as('U10');
    d = await D.loadDocs(); w = d.wos.find((x) => x.no === wo.no);
    if (!w.assignee) await D.saveWo(w, { ...w, assignee: 'U07' });
    d = await D.loadDocs(); w = d.wos.find((x) => x.no === wo.no);
    await D.saveWo(w, { ...w, state: 'approved' });
    d = await D.loadDocs(); w = d.wos.find((x) => x.no === wo.no);
    w?.state === 'approved' && w.assignee === 'U07' && /보전 확인/.test(w.title) ? ok(`보전 수정 → 반장 승인 → ${w.state} v${w.version} 담당 ${w.assignee}`) : bad(`승인 뒤 상태 ${w?.state} 담당 ${w?.assignee} 제목 ${w?.title}`);
  } catch (e) { bad(`작업지시서 고치기·승인 ${e.status ?? ''} ${e.message}`); }

  // 보전: 열기 → 작업 시작 → 작업기록서 만들기 → 칸·잠금 9칸·단계 체크 → 확정 → 설비 복귀
  await as('U07');
  try {
    const mine = (await D.loadDocs()).notices.filter((n) => n.rule === 'WO_ASSIGNED' && !n.handled);
    mine.length ? ok(`보전 U07에게 배정 알림 ${mine.length}건`) : bad('보전 U07에게 배정 알림 없음');
    await D.openWoSeen(wo.no);
    let d = await D.loadDocs(); let w = d.wos.find((x) => x.no === wo.no);
    await D.saveWo(w, { ...w, state: 'inprogress' });
    await D.createRecord(wo.no);
    d = await D.loadDocs(); w = d.wos.find((x) => x.no === wo.no);
    const r = d.wrs.find((x) => x.woNo === wo.no);
    if (!r) throw new Error('작업기록서가 안 생김');
    ok(`작업 시작 → ${w.state}, 작업기록서 ${r.no} (잠금 ${r.lock.length}칸·단계 ${r.stepChecks.length}칸)`);
    const tw = await B.backendRoute('line/twin');
    const end = tw.clock.sim_at.slice(11, 16);
    await D.saveWr(r, { ...r, cause: '공구 간섭으로 충돌', action: '스핀들·공구 점검, T05 교체', memo: '흐름 점검', end, lock: r.lock.map(() => true), stepChecks: r.stepChecks.map(() => true), parts: [] });
    d = await D.loadDocs(); let r2 = d.wrs.find((x) => x.no === r.no);
    r2.lock.every(Boolean) && r2.cause ? ok(`작업기록서 저장 (원인·조치·잠금 9칸 모두)`) : bad(`작업기록서 저장 뒤 잠금 ${r2.lock.filter(Boolean).length}/9 원인 "${r2.cause}"`);
    await D.saveWr(r2, { ...r2, state: 'confirmed' });
    d = await D.loadDocs(); r2 = d.wrs.find((x) => x.no === r.no); w = d.wos.find((x) => x.no === wo.no);
    r2.state === 'confirmed' && w.state === 'done' ? ok(`작업기록서 확정 → 작업지시서 ${w.state}`) : bad(`확정 뒤 기록 ${r2.state} 지시서 ${w.state}`);
    await B.backendRoute('maint/work-records/confirm', { equipment_id: 'VF2-01' });
    const up = await waitFor('VF2-01 복귀(RUN·SETUP·IDLE)', async () => {
      const t = await B.backendRoute('line/twin');
      return t.equipment?.['VF2-01']?.state_code !== 'DOWN' ? t : null;
    }, 60000);
    if (up) ok(`VF2-01 복귀 → ${up.equipment['VF2-01'].state_code}`);
    const h = d.handled[`a-${wo.alertId.slice(2)}`] ?? d.handled[wo.alertId];
    h ? ok(`알람 ${wo.code} 처리 표시 (${h.by})`) : bad('작업기록서 확정 뒤 알람 처리 표시 없음');
  } catch (e) { bad(`보전 흐름 ${e.status ?? ''} ${e.code ?? ''} ${e.message}`); }

  // 수정 이력 (SCR-17): 작업지시서·작업기록서 버전이 DB에서 (2026-10-24)
  try {
    const rw = await B.backendRoute(`documents/doc/WORK_ORDER/${wo.no}`);
    const rr = (await D.loadDocs()).wrs.find((x) => x.woNo === wo.no);
    const rv = rr ? await B.backendRoute(`documents/doc/WORK_RECORD/${rr.no}`) : { revisions: [] };
    const nch = Object.values(rw.changes ?? {}).reduce((n, v) => n + v.length, 0);
    rw.revisions.length >= 2 && rv.revisions.length >= 1 ? ok(`수정 이력: 작업지시서 ${rw.revisions.length}버전(바뀐 칸 ${nch}) · 작업기록서 ${rv.revisions.length}버전`) : bad(`수정 이력 작업지시서 ${rw.revisions.length} 작업기록서 ${rv.revisions.length}`);
  } catch (e) { bad(`수정 이력 ${e.status ?? ''} ${e.message}`); }

  // 반장 확인
  await as('U10');
  try {
    const d = await D.loadDocs(); const r = d.wrs.find((x) => x.woNo === wo.no);
    await D.saveWr(r, { ...r, state: 'checked' });
    const r2 = (await D.loadDocs()).wrs.find((x) => x.no === r.no);
    r2.state === 'checked' ? ok('반장 확인 → checked') : bad(`반장 확인 뒤 ${r2.state}`);
  } catch (e) { bad(`반장 확인 ${e.status ?? ''} ${e.message}`); }
}

// 간이 기록 (경고·조작 안내 알람에 작업자가 남김) — 처음 저장 때 DB 번호
await as('U01');
try {
  // S1은 정지 알람(992) 한 건뿐이라(2026-10-23) 경고 알람이 없으면 S4(공기 압력 저하 → 120)를 걸고 기다린다 (2026-10-25)
  const warn = async () => ((await B.backendRoute('line/twin')).alarms ?? []).find((a) => a.severity !== 'STOP');
  let al = await warn();
  if (!al) {
    await as('U10');
    await waitFor('S4 시작 (VF2-01 가공 중)', () => B.backendRoute('sim/inject', { scenario_code: 'S4' }).then(() => true).catch((e) => {
      if (e.code === 'INVALID_STATE') return null; throw e;
    }), 180000);
    await as('U01');
    al = await waitFor('S4 경고 알람', warn, 300000);   // 알람 앞뒤 5초 센서로 중계가 몇 분 걸릴 수 있음
  }
  if (!al) throw new Error('경고 알람 없음');
  const machine = Object.entries((await import(pathToFileURL(join(dir, 'data.mjs')).href)).ID_OF).find(([eq]) => eq === al.equipment_id)?.[1];
  const draft = { no: `NEW:a-${al.alarm_event_id}:alarm`, alertId: `a-${al.alarm_event_id}`, machine, kind: 'alarm', code: al.alarm_code, state: 'open', action: '', parts: [], lock: Array(9).fill(false), memo: '', revisions: [] };
  const no = await D.saveSr(draft, { ...draft, action: '칩 제거 후 재시작', memo: '흐름 점검' });
  let d = await D.loadDocs(); let s = d.srs.find((x) => x.no === no);
  s ? ok(`간이 기록 ${no} 만듦 (알람 ${al.alarm_code})`) : bad(`간이 기록 ${no}가 목록에 없음`);
  await D.saveSr(s, { ...s, state: 'confirmed' });
  d = await D.loadDocs(); s = d.srs.find((x) => x.no === no);
  s?.state === 'confirmed' ? ok('간이 기록 확정') : bad(`간이 기록 확정 뒤 ${s?.state}`);
} catch (e) { bad(`간이 기록 ${e.status ?? ''} ${e.code ?? ''} ${e.message}`); }

// 알림 처리 (손으로 처리하는 알림 하나)
await as('U10');
try {
  const d = await D.loadDocs();
  const n = d.notices.find((x) => !x.handled && !['CAUSE_CHECK_REQUEST'].includes(x.rule));
  if (!n) ok('처리할 알림 없음 (건너뜀)');
  else {
    try {
      await D.resolveNotice(n.id, n.rule === 'REPEAT_ALARM' ? '다음 교대 전 원인 점검' : undefined);
      const n2 = (await D.loadDocs()).notices.find((x) => x.id === n.id);
      n2?.handled ? ok(`알림 ${n.rule} 처리`) : bad(`알림 ${n.rule} 처리 뒤에도 미처리`);
    } catch (e) { /자동/.test(e.message) || e.code === 'INVALID_STATE' ? ok(`알림 ${n.rule}은 자동 처리 규칙 — 손 처리 거절(정상)`) : bad(`알림 처리 ${e.status ?? ''} ${e.message}`); }
  }
} catch (e) { bad(`알림 ${e.message}`); }

// 화면의 나머지 쓰기 (DB가 주인): 입고·설정은 되돌릴 수 있는 것만 가볍게
try {
  const inv = await B.backendRoute('inventory');
  const item = inv.items?.[0]?.item_no ?? 'CS-WLUB';
  await as('U10');
  await B.backendRoute('inventory/txns', { item_no: item, txn_type: 'RECEIPT', qty: 1, memo: '흐름 점검' }).then(() => ok(`입고 1 (${item})`)).catch((e) => (e.status === 403 ? ok('입고는 다른 역할 몫(403)') : bad(`입고 ${e.status} ${e.message}`)));
} catch (e) { bad(`재고 ${e.message}`); }

console.log(`\n실패 ${fail}`);
process.exit(fail ? 1 : 0);
