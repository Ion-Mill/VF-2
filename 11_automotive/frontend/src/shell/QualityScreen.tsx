'use client';
// SCR-20 검사 기록·불량 집계 — OP-50 측정값은 결과 파일(CSV)을 읽어 자동 기록 (서버: 9월 inspection_result + 10/1 실시간 측정).
// 사람은 확인만: 로트 바코드·본인 확인, M6 게이지·외관 버튼, (자동이 안 될 때만) 수동 입력, 재측정 값 고르기·반장 확인.
// 화면 구조 (사용자 시안 2026-10-16): 로트 줄 · 한눈에 보기(부품 모식도·부품 지도·공차 안 위치) · 측정 시작/결과 · 결과 파일 · 재측정 · 수동 입력 · 검사 강화 · Cpk · 관리도 · 불량 집계
import { LockIcon, SecIcon } from './ui';
import { useEffect, useState } from 'react';
import { PAGE, useApp } from './ctx';
import { Band as CBand } from './ui';
import { capBand, qualityBand } from './bands';
import { MASTERS } from './data';
import { hm, md, simIso, useFetch, usePersist } from './live';
import { userName } from './model';
import { ConfirmBox } from './Safety';

type R = Record<string, any>;
const num = (v: unknown) => (v === '' || v == null || isNaN(Number(v)) ? null : Number(v));
const judge = (it: R | undefined, v: number | null) => {
  if (!it || v == null) return null;
  const lsl = num(it.lsl), usl = num(it.usl);
  return (lsl == null || v >= lsl) && (usl == null || v <= usl) ? 'PASS' : 'FAIL';
};
const STATUS: Record<string, string> = { IN_PROCESS: '생산 중', WAIT_INSPECTION: '검사 대기', WAIT_JUDGEMENT: '판정 대기', HOLD_REVIEW: '보류 검토', ON_HOLD: '보류', PASSED: '합격', RELEASED: '해제', SCRAPPED: '폐기' };
const POS: Record<string, string> = { TOP: '위', MID: '중간', BOT: '아래', BOTTOM: '아래' };
const SHORT: Record<string, string> = { '1': '◆ Ø45 H7', '2': '전체 길이', '8': '폭', '3': '두께', '4': '구멍 간 거리', '5': '평면도' };
const ORDER = ['1', '2', '8', '3', '4', '5'];
// 측정 항목 6가지 색 (모식도 치수선·이름표·공차 칸이 같은 색). 빨강·노랑은 불합격·주의에 쓰므로 뺌 (사용자 요청 2026-10-19)
const ITEM_COLOR: Record<string, { line: string; bg: string; text: string }> = {
  '1': { line: '#2563eb', bg: '#e8efff', text: '#1d4ed8' }, // Ø45 파랑
  '2': { line: '#1e3a8a', bg: '#e8edf8', text: '#1e3a8a' }, // 길이 남색 (C안 3.1: 주황은 이상 상태에만)
  '8': { line: '#0d9488', bg: '#e2f6f3', text: '#0f766e' }, // 폭 청록
  '3': { line: '#5b8cf0', bg: '#e5effe', text: '#2a55b8' }, // 두께 보라
  '4': { line: '#db2777', bg: '#fde8f2', text: '#be185d' }, // 구멍 간 분홍
  '5': { line: '#65a30d', bg: '#eef7e1', text: '#4d7c0f' }, // 평면도 연두
  M6: { line: '#64748b', bg: '#f1f5f9', text: '#334155' }, // M6 게이지 (작업자 확인) 회색
};
const box = 'rounded-card border border-line bg-white p-5 shadow-card';
const H3 = ({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) => (
  <div className="flex flex-wrap items-center gap-3"><h3 className="flex items-center gap-2 text-card font-bold">{children}</h3>{right && <div className="ml-auto flex items-center gap-3">{right}</div>}</div>);

export function QualityScreen({ cap = false }: { cap?: boolean }) { // cap: 공정 능력·불량 화면 (qcap)
  const { key, role, user, twin, toast, go, wrs, eve } = useApp(); // eve: 이브 창 열림 — 결과 파일 높이를 수동 입력 끝까지로
  const items = MASTERS.inspection_items as R[], defs = MASTERS.defect_codes as R[];
  const cmmItems = items.filter((i) => i.method === 'CMM');
  const [lot, setLot] = useState(key ?? twin?.equipment['CMM-01'].lot_no ?? '');
  const res = useFetch<{ results: R[]; plan: R | null }>(lot ? `inspection/results?lot=${encodeURIComponent(lot)}` : null, 8000, [lot]);
  const lotsF = useFetch<{ lots: R[]; past_holds?: R[] }>(`lots?lot=${encodeURIComponent(lot)}`, 15000, [lot]);
  const cmm = useFetch<{ imports: R[]; errors_30d: R[]; counts: R }>('inspection/cmm-imports', 15000);
  const qs = useFetch<{ defects: { defect_code: string; qty: number }[]; items: R[]; today_defects: R[] }>('quality/summary', 30000);
  const run = twin?.run_id ?? null;
  const [manual, setManual] = usePersist<R[]>('qManual', [], run);
  const [gv, setGv] = usePersist<Record<string, string>>('qGauge', {}, run); // `${lot}|${seq}|6` → PASS/FAIL, |7 → PASS or 코드
  const [picked, setPicked] = usePersist<Record<string, number>>('qPick', {}, run);
  const [backOk, setBackOk] = usePersist<Record<string, string>>('qBack', {}, run);
  const [bar, setBar] = useState(''); const [me, setMe] = useState(false);
  const [seqSel, setSeqSel] = useState<number | null>(null);
  const [itemSel, setItemSel] = useState('1');
  const [ptSel, setPtSel] = useState<number | null>(null);
  const [mi, setMi] = useState({ item: '1', v: '' });
  const [confirmBack, setConfirmBack] = useState(false);
  const [zoom, setZoom] = useState(false); // 부품 모식도 크게 보기 팝업
  const isOpr = role === 'OPR', isSup = role === 'SUP' || role === 'MGR';

  const allLots = lotsF.data?.lots ?? [];
  const L = allLots.find((x) => x.lot_no === lot);
  // 측정기가 쉬고 있어 측정 지시 로트가 없으면: 가장 최근 결과 파일의 로트 → OP-50을 지난 가장 최근 로트
  useEffect(() => {
    if (lot) return;
    const fromFile = String(cmm.data?.imports?.[0]?.file_name ?? '').match(/LOT-\d{4}-\d{3}-\d/)?.[0]; // 가장 최근 결과 파일의 로트
    const last = fromFile ?? [...allLots].reverse().find((x) => Number(x.process_done?.['OP-50'] ?? 0) > 0)?.lot_no;
    if (last) setLot(last);
  }, [lot, allLots.length, cmm.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const plan = res.data?.plan;
  const rows = [...(res.data?.results ?? []), ...manual.filter((m) => m.lot_no === lot)];
  const qItem = (seq: string) => qs.data?.items.find((x) => String(x.item_seq) === seq);
  const used = (r: R) => r.use_for_judgement === true || r.use_for_judgement === 'true';
  const mainRow = (seq: number, item: string) => { const rs = rows.filter((r) => Number(r.part_seq) === seq && String(r.item_seq) === item && (r.position == null || r.position === '' || r.position === 'MID')); return rs.find((r) => picked[`${lot}|${seq}|${item}`] === Number(r.remeasure_seq)) ?? rs.find(used) ?? rs[rs.length - 1]; };
  const seqs = Array.from(new Set(rows.map((r) => Number(r.part_seq)))).sort((a, b) => a - b);
  const total = Math.max(L?.input_qty ?? 0, seqs[seqs.length - 1] ?? 0);
  const cur = twin?.equipment['CMM-01'];
  const measuringSeq = cur?.state_code === 'RUN' && cur.lot_no === lot ? (seqs[seqs.length - 1] ?? 0) + 1 : null;
  const cmmWarn = (seq: number) => cmmItems.some((it) => { const r = mainRow(seq, String(it.item_seq)), q = qItem(String(it.item_seq)), v = r ? num(r.measured_value) : null; return q?.ucl != null && v != null && (v > q.ucl || v < q.lcl); });
  // 부품마다: 불합격 / 관리 한계(3σ) 밖·M6 불합격(주의) / 합격 / 기록 없음
  const partState = (seq: number) => {
    const rs = cmmItems.map((it) => ({ it, r: mainRow(seq, String(it.item_seq)) })).filter((x) => x.r);
    if (!rs.length) return seqs.includes(seq) ? 'none' : seq === measuringSeq ? 'measuring' : 'wait';
    if (rs.some(({ it, r }) => (judge(it, num(r!.measured_value)) ?? r!.judgement) === 'FAIL')) return 'fail';
    if (cmmWarn(seq)) return 'warn';
    return gv[`${lot}|${seq}|6`] === 'FAIL' ? 'warn' : 'pass'; // M6 게이지 불합격(작업자 확인)은 측정 부품에서 주의 등급으로만 표시 (사용자 요청 2026-10-19)
  };
  const states = Array.from({ length: total }, (_, i) => partState(i + 1));
  const mapRows = Math.max(4, Math.ceil(total / 15)); // 부품 지도 줄 수 (최대 60개 = 4줄)
  const cnt = (k: string) => states.filter((s) => s === k).length;
  const passN = cnt('pass') + cnt('warn'), failN = cnt('fail'), noneN = cnt('none'), measured = passN + failN + noneN;
  const sel = seqSel ?? [...seqs].reverse().find((s) => states[s - 1] === 'warn' || states[s - 1] === 'fail') ?? seqs[seqs.length - 1] ?? null;
  const selRow1 = sel ? mainRow(sel, '1') : undefined;
  const remeasure = Array.from(new Set(rows.filter((r) => Number(r.remeasure_seq) > 1).map((r) => `${r.part_seq}|${r.item_seq}`))).map((k) => k.split('|'));
  const enhancedLots = allLots.filter((x) => x.enhanced && !['PASSED', 'RELEASED', 'SCRAPPED'].includes(x.status) || (x.enhanced && x.lot_no === lot));
  const causeDone = wrs.some((w) => w.state === 'confirmed' || w.state === 'checked');
  const allPass = enhancedLots.length > 0 && enhancedLots.every((x) => x.judgement === 'PASS');
  // 지금 강화 중인 로트가 없으면 최근 강화 기록(시연 데이터 9월의 보류 → 강화 → 보통 복귀)을 보여 줌 (사용자 요청 2026-10-19)
  const enhPast = enhancedLots.length === 0, enhRows = enhPast ? allLots.filter((x) => x.enhanced).slice(-6) : enhancedLots;
  const lastHold = [...(lotsF.data?.past_holds ?? [])].filter((h) => h.normal_resumed_at).pop();
  const fileOf = (x: R) => { const m = String(x.file_name ?? '').match(/(LOT-\d{4}-\d{3}-\d)_(\d{3})/); return m ? `${m[1].slice(-5)} · ${Number(m[2])}` : x.file_name; };
  const todayFiles = (cmm.data?.imports ?? []).filter((x) => String(x.received_at).startsWith('2026-10-01')).slice(0, 12);

  // ===== 작업자(OPR) 태블릿 화면 (사용자 시안 2026-10-16): 단계 표시 · 게이지/외관 큰 버튼 · CMM 결과 · 로트 진행 · 다음 부품 =====
  if (isOpr) {
    const k6 = `${lot}|${sel}|6`, k7 = `${lot}|${sel}|7`, done6 = !!gv[k6], done7 = !!gv[k7], started = me || bar === cur?.lot_no;
    const cmmAt = sel ? selRow1?.measured_at : null, nextSeq = measuringSeq ?? (sel ? sel + 1 : null);
    const last = !!nextSeq && nextSeq > total; // 로트의 마지막 부품이면 "다음 순번"이 없음
    const missing = states.map((st0, i) => (st0 === 'none' ? i + 1 : 0)).filter(Boolean);
    const verdict = !done6 || !done7 ? '입력 기다림' : states[(sel ?? 1) - 1] === 'fail' || gv[k6] === 'FAIL' || gv[k7] !== 'PASS' ? '불합격' : '합격';
    const steps: [string, string, boolean][] = [['측정 시작 확인', started ? '확인함' : '바코드·본인 확인', started], ['CMM 측정', cmmAt ? `결과 ${hm(cmmAt)}` : '결과 대기', !!cmmAt], ['게이지 · 외관', 'M6 · 외관', done6 && done7], ['다음 부품', last ? '마지막 부품' : nextSeq ? `순번 ${nextSeq}` : '—', false]];
    const curStep = !started ? 0 : !cmmAt ? 1 : !(done6 && done7) ? 2 : 3;
    const big = (on: boolean, bad?: boolean) => `h-24 rounded-tile border-2 text-num font-bold ${on ? (bad ? 'border-crit bg-crit-bg text-crit' : 'border-ok bg-ok-bg text-ok') : 'border-line bg-white text-ink'}`; // 누르기 전 둘 다 중립 회색 · 누르면 합격 초록 / 불합격 빨강 (보라색은 누르는 것 표시라 판정에 안 씀)
    return (
      <div className={PAGE}>
        <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
          <section className={`${box} grid grid-cols-4 gap-2 !p-3`}>{steps.map(([t, sub, ok], i) => (
            <div key={t} className={`flex items-center gap-3 rounded-tile px-3 py-2 ${i === curStep ? 'bg-brand-tint' : ''}`}>
              <span className={`flex h-11 w-11 items-center justify-center rounded-full text-band font-bold ${ok ? 'bg-brand-tint text-brand-ink' : i === curStep ? 'bg-brand text-white' : 'border-2 border-line text-ink-2'}`}>{ok ? '✓' : i + 1}</span>
              <div><div className="text-band font-bold">{t}</div><div className="text-body text-ink-2">{sub}</div></div></div>))}
          </section>
          {!started && (
            <section className={`${box} flex flex-wrap items-center gap-3`}>
              <b className="text-card">측정 시작 확인</b>
              <input value={bar} onChange={(e) => setBar(e.target.value)} placeholder="로트 바코드 찍기" className="h-12 w-[240px] rounded-tile border border-line px-3 text-card" />
              {bar && <span className={bar === cur?.lot_no ? 'font-bold text-ok' : 'font-bold text-crit'}>{bar === cur?.lot_no ? '✓ 일치' : `✕ 측정 지시는 ${cur?.lot_no ?? '—'}`}</span>}
              <button onClick={() => setMe(true)} className="h-12 rounded-tile border border-line bg-white px-4 text-card font-bold">본인 확인 ({user.name})</button>
            </section>
          )}
          <div className="grid grid-cols-[1.45fr_1fr] gap-4">
            <section className={box}>
              <div className="flex flex-wrap items-baseline gap-4"><span className="text-tablet font-bold">순번 {sel ?? '—'}</span><span className="font-mono text-title text-ink-2">{lot}</span>{L?.enhanced && <span className="rounded-full border border-warn-mark bg-warn-bg px-3 py-1 text-band font-bold text-warn">▲ 강화</span>}</div>
              <div className="mt-4 text-band font-bold">M6 나사 게이지</div>
              <div className="mt-2 grid grid-cols-2 gap-4"><button disabled={!sel} onClick={() => setGv((g) => ({ ...g, [k6]: 'PASS' }))} className={big(gv[k6] === 'PASS')}>합격</button><button disabled={!sel} onClick={() => setGv((g) => ({ ...g, [k6]: 'FAIL' }))} className={big(gv[k6] === 'FAIL', true)}>불합격</button></div>
              <div className="mt-5 text-band font-bold">외관</div>
              <div className="mt-2 grid grid-cols-2 gap-4"><button disabled={!sel} onClick={() => setGv((g) => ({ ...g, [k7]: 'PASS' }))} className={big(gv[k7] === 'PASS')}>합격</button><button disabled={!sel} onClick={() => setGv((g) => ({ ...g, [k7]: g[k7] && g[k7] !== 'PASS' ? g[k7] : 'FAIL' }))} className={big(!!gv[k7] && gv[k7] !== 'PASS', true)}>불합격</button></div>
              {gv[k7] && gv[k7] !== 'PASS' && <select value={gv[k7] === 'FAIL' ? '' : gv[k7]} onChange={(e) => setGv((g) => ({ ...g, [k7]: e.target.value || 'FAIL' }))} className="mt-2 h-12 w-full rounded-tile border border-line px-2 text-card"><option value="">불량 코드 고르기</option>{defs.filter((d) => /^(SUR|VIS|BUR)/.test(d.defect_code)).map((d) => <option key={d.defect_code} value={d.defect_code}>{d.defect_code} {d.defect_name}</option>)}</select>}
              <div className="mt-5 rounded-tile border border-line bg-white px-5 py-4 text-band">부품 판정 <b className={verdict === '불합격' ? 'text-crit' : ''}>{verdict}</b></div>
            </section>
            <section className={box}>
              <div className="text-title font-bold">CMM 결과 <span className="text-card font-normal text-ink-2">자동 · {cmmAt ? hm(cmmAt) : '대기'}</span></div>
              <div className="mt-3 flex flex-col gap-2">{ORDER.map((k) => { const it = items.find((x) => String(x.item_seq) === k), r = sel ? mainRow(sel, k) : undefined, v = r ? num(r.measured_value) : null, q = qItem(k);
                const pj = judge(it, v), out = q?.ucl != null && v != null && (v > q.ucl || v < q.lcl);
                return <div key={k} className={`flex items-center justify-between rounded-tile border px-4 py-2.5 ${pj === 'FAIL' ? 'border-crit-line bg-crit-bg' : out ? 'border-warn-line bg-warn-bg' : 'border-line-soft'}`}><span className="text-band font-bold">{SHORT[k]}</span><span className="flex items-center gap-4"><b className="font-mono text-title">{v == null ? '—' : k === '4' && v >= 0 ? `+${v}` : v}</b><span className={`w-5 text-band ${pj === 'FAIL' ? 'text-crit' : out ? 'text-warn' : ''}`}>{v == null ? '' : pj === 'FAIL' ? '✕' : out ? '▲' : '✓'}</span></span></div>; })}</div>
              <div className="mt-4 text-band font-bold">로트 진행 <span className="font-mono font-normal text-ink-2">{measured} / {total}</span></div>
              <div className="mt-2 grid grid-cols-10 gap-1">{states.map((st0, i) => { const n = i + 1; return <button key={n} disabled={st0 === 'wait'} onClick={() => setSeqSel(n)} className={`relative h-9 rounded-ctl border text-body font-bold ${st0 === 'fail' ? 'border-crit-line bg-crit-bg text-crit' : st0 === 'measuring' ? 'border-brand-line bg-brand-tint text-brand' : st0 === 'none' ? 'border-dashed border-line bg-white' : st0 === 'wait' ? 'border-transparent bg-tile text-ink-2' : 'border-line bg-white'} ${n === sel ? '!border-2 !border-brand' : ''}`}>{n}{st0 === 'measuring' && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-brand" />}</button>; })}</div>
              {missing.length > 0 && (
                <div className="mt-4 rounded-tile border border-warn-line bg-warn-bg p-3">
                  <div className="flex items-center justify-between gap-2"><b className="text-band text-warn">▲ 순번 {missing[0]} 측정값 없음</b><button onClick={() => setSeqSel(missing[0])} className="h-11 rounded-tile border-2 border-brand bg-white px-4 text-card font-bold text-brand">수동 입력</button></div>
                  {sel === missing[0] && <div className="mt-2 flex flex-wrap items-center gap-2"><select value={mi.item} onChange={(e) => setMi({ ...mi, item: e.target.value })} className="h-11 rounded-tile border border-line">{cmmItems.map((i) => <option key={i.item_seq} value={i.item_seq}>{i.item_name}</option>)}</select>
                    <input value={mi.v} onChange={(e) => setMi({ ...mi, v: e.target.value })} placeholder="값" className="h-11 w-28 rounded-tile border border-line px-2" />
                    <button disabled={!mi.v} onClick={() => { setManual((l) => [...l, { lot_no: lot, part_seq: sel, item_seq: Number(mi.item), measured_value: Number(mi.v), measured_at: simIso(), input_method: 'MANUAL', entered_by: user.id, check_status: 'CHECK', use_for_judgement: false, remeasure_seq: 1 }]); setMi({ ...mi, v: '' }); toast(`순번 ${sel} 수동 저장 — 반장 확인 필요`); }} className="h-11 rounded-tile bg-brand px-4 font-bold text-white hover:bg-brand-ink disabled:bg-line">저장</button></div>}
                </div>)}
            </section>
          </div>
          <section className={`${box} flex flex-wrap items-center gap-4`}>
            <span className="flex items-center gap-2 text-band"><span className="h-3.5 w-3.5 rounded-full bg-brand shadow-[0_0_0_5px_#e5effe]" />{last ? '마지막 부품이에요 — 이 로트 측정 끝' : nextSeq ? `다음 순번 ${nextSeq}` : '다음 부품 없음'}{measuringSeq ? ' · CMM 측정 중' : ''}</span>
            <div className="ml-auto text-right"><button disabled={!(done6 && done7) || !nextSeq || nextSeq > total} onClick={() => setSeqSel(nextSeq)} className="h-16 rounded-tile bg-brand px-10 text-title font-bold text-white disabled:bg-track disabled:text-ink-2">다음 부품</button>
              {!(done6 && done7) && <div className="mt-1 text-body text-ink-2">M6 · 외관 입력 필요</div>}</div>
          </section>
        </div>
      </div>
    );
  }

  const capSections = (<>
        {/* 공정능력 Cpk */}
        <section className={box}>
          <H3>공정능력 Cpk</H3>
          <div className="mt-3 grid grid-cols-6 gap-3">{ORDER.map((k) => { const q = qItem(k); if (!q) return null; const low = q.cpk != null && q.cpk < Number(q.cpk_min); return (
            <button key={k} onClick={() => setItemSel(k)} className={`rounded-tile border border-t-4 bg-[#f6f8fd] p-3 text-left ${itemSel === k ? 'border-brand' : 'border-line-soft border-t-brand'}`}>
              <div className="text-small font-bold">{q.item_name}</div>
              <div className={`mt-1 font-mono text-num font-bold ${low ? 'text-[#b45309]' : ''}`}>{q.cpk ?? '—'}</div>
              <div className="text-small text-ink-2">기준 {q.cpk_min}{low ? ' ▲ 미달' : ''}</div></button>); })}</div>
        </section>

        {/* 관리도 */}
        <section className={box}>
          <H3>관리도 — {items.find((x) => String(x.item_seq) === itemSel)?.item_name} <span className="text-small font-normal text-ink-2">OP-30 정밀 가공 · 공차 {qItem(itemSel)?.lsl || '—'} ~ {qItem(itemSel)?.usl || '—'}</span></H3>
          <div className="mt-3 flex flex-wrap gap-2">{ORDER.map((k) => <button key={k} onClick={() => { setItemSel(k); setPtSel(null); }} className={`h-10 rounded-tile border px-3 text-body font-bold ${itemSel === k ? 'border-brand-line bg-brand-tint text-brand-ink' : 'border-line bg-white text-ink'}`}>{SHORT[k]}</button>)}</div>
          {qItem(itemSel) && <IMR it={qItem(itemSel)!} sel={ptSel} onSel={setPtSel} />}
        </section>

        {/* 불량 집계 — 불량 코드별 + 불량률 */}
        <DefectBox defects={qs.data?.defects ?? []} defs={defs} lots={allLots} />
  </>);
  const tolGrid = (<>
    <div className="mt-3 text-card font-bold">공차 안 위치 · 순번 {sel ?? '—'}</div>
    <div className="mt-2 grid grid-cols-3 gap-2">{ORDER.map((k) => { const it = items.find((x) => String(x.item_seq) === k); const r = sel ? mainRow(sel, k) : undefined; return it ? <TolBar key={k} card it={it} q={qItem(k)} v={r ? num(r.measured_value) : null} /> : null; })}</div>
  </>);
  // 품질 하위 화면: 검사 기록(로트 단위) | 공정 능력·불량(공장 전체 지표: Cpk·관리도·불량 집계). 고르는 곳은 왼쪽 메뉴 옆 목록 (사용자 요청 2026-10-19)
  if (cap) return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
        {/* 디자인 통일 C안: 결론 띠 (bands.ts capBand) — Cpk 미달 항목 · 불량률 */}
        {(() => { const its = (qs.data?.items ?? []).filter((x) => x.cpk != null).map((x) => ({ item_name: String(x.item_name), cpk: Number(x.cpk), cpk_min: Number(x.cpk_min) })); const n = Math.min(...(qs.data?.items ?? []).filter((x) => x.cpk != null).map((x) => Number(x.n ?? 0)), 9999); /* Cpk를 내는 항목(CMM)만 — M6·외관은 측정값 없음 */ const dq = (qs.data?.defects ?? []).reduce((s, d) => s + d.qty, 0); const tot = allLots.reduce((s, l) => s + Number(l.input_qty ?? 0), 0);
          return <CBand spec={capBand(its, n === 9999 ? 0 : n, { qty: dq, total: Math.max(tot, dq) })} />; })()}
        <p className="text-small text-ink-2">로트 하나가 아니라 9/1 ~ 10/1 측정값 전체로 본 공장의 공정 능력과 불량입니다.</p>
        {capSections}
      </div>
    </div>);

  return (
    <div className={PAGE}>
      <div className="mx-auto flex max-w-[1440px] flex-col gap-3">
        {/* 디자인 통일 C안: 결론 띠 (bands.ts qualityBand) — 고른 로트의 측정 수 · 불합격 · 주의 */}
        <CBand spec={qualityBand(lot, states, { sel, enhanced: enhancedLots.some((x) => x.lot_no === lot && !enhPast) })} />
        {/* 로트 줄 */}
        <section className={`${box} flex flex-wrap items-center gap-4`}>
          <b className="text-card">로트</b>
          <input list="qlots" value={lot} onChange={(e) => { setLot(e.target.value); setSeqSel(null); }} className="h-12 w-[230px] rounded-tile border border-line px-3 font-mono text-band font-bold" />
          <datalist id="qlots">{[...allLots].reverse().slice(0, 200).map((x) => <option key={x.lot_no} value={x.lot_no}>{STATUS[x.status] ?? x.status}</option>)}</datalist>
          <span className="text-card text-ink-2">검사 방식 <b className="text-ink">{plan?.plan_mode === 'ENHANCED' || plan?.enhance_reason || L?.enhanced ? '강화' : plan?.plan_mode === 'FULL' ? '전수' : '발췌'}</b>{plan?.enhance_reason || L?.enhance_reason ? ` · 사유 ${plan?.enhance_reason || L?.enhance_reason}` : ''}</span>
          {twin?.bottleneck?.process_code && <span className="rounded-tile border-2 border-[#e8954a] px-3 py-1 text-body font-bold text-[#b45309]">병목 {twin.bottleneck.process_code}</span>}
          <div className="ml-auto flex items-center gap-2">
            {L && ['ON_HOLD', 'HOLD_REVIEW', 'WAIT_JUDGEMENT', 'IN_PROCESS', 'WAIT_INSPECTION'].includes(L.status) && <span className="rounded-tile border-2 border-ink px-4 py-2 text-card font-bold"><LockIcon /> {STATUS[L.status]} · 출하 금지</span>}
            <button onClick={() => go('lots', lot)} className="h-11 rounded-tile border border-line bg-white px-4 text-body text-brand">로트 추적</button>
          </div>
        </section>

        {/* 한눈에 보기 */}
        <section className={box}>
          <H3 right={<>
            <span className="text-body">측정 <b className="font-mono text-title">{measured} / {total}</b></span>
            <div className="h-2.5 w-28 overflow-hidden rounded-full bg-track"><div className="h-full bg-brand" style={{ width: `${total ? (measured / total) * 100 : 0}%` }} /></div>
            <span className="text-body">합격 <b className="text-band">{passN}</b></span><span className="text-body text-crit">불합격 <b className="text-band">{failN}</b></span><span className="text-body">기록 없음 {noneN}</span><span className="text-body">남은 <b className="text-band">{Math.max(0, total - measured)}</b></span>
          </>}>한눈에 보기 — {lot || '로트를 고르세요'}</H3>
          {/* 측정값이 아직 없어도 로트가 있으면 부품 지도를 보여 줌 — 처음 고른 로트(측정기 지시 로트)는 발췌 부품이 온도 맞춤 중이라 값이 없을 수 있음 (사용자 요청 2026-10-21) */}
          {!rows.length && <p className="mt-4 text-body text-ink-2">{!res.data ? '불러오는 중' : total ? `아직 CMM 측정값 없음 — 발췌 부품은 세척 뒤 90분 온도 맞춤을 마치면 측정해요${L ? ` (OP-50 통과 ${L.process_done?.['OP-50'] ?? 0} / ${total})` : ''}` : '측정 기록 없음'}</p>}
          {!total ? null : (
            <div className={`mt-4 grid gap-6 ${eve ? 'grid-cols-1' : 'grid-cols-[1fr_1fr]'}`}>
              {/* 왼쪽: 모식도(작게) + 공차 안 위치 3×2. 오른쪽: 부품 지도 15×4 (사용자 요청 2026-10-19) */}
              <div>
                <div className="mb-1 flex items-center gap-2 text-card font-bold">부품 모식도 · 순번 {sel ?? '—'} <span className="rounded border border-line px-1.5 text-small font-normal text-ink-2">모식도</span></div>
                <button type="button" disabled={!sel} onClick={() => setZoom(true)} aria-label={`순번 ${sel} 모식도 크게 보기`} className="block w-full max-w-[520px] cursor-zoom-in rounded-tile border border-line-soft bg-tile p-1 hover:border-brand-line">
                  <PartSketch rows={rows} seq={sel} mainRow={mainRow} items={items} qItem={qItem} m6={sel ? gv[`${lot}|${sel}|6`] : undefined} />
                </button>
                {eve && tolGrid}
              </div>
              <div className="flex flex-col">{/* 부품 지도 칸이 왼쪽 모식도 높이만큼 늘어나 번호가 커짐 (사용자 요청 2026-10-19) */}
                <div className="text-card font-bold">부품 지도</div>
                {/* 로트는 최대 60개 → 15×4 칸을 늘 깔고 남은 높이를 4줄이 나눠 씀. 로트 수보다 뒤 칸은 연한 번호의 빈칸 — 60까지 번호 채움 (사용자 요청 2026-10-19) */}
                <div className="mt-2 grid flex-1 grid-cols-[repeat(15,minmax(0,1fr))] gap-1" style={{ gridTemplateRows: `repeat(${mapRows}, minmax(38px, 1fr))` }}>{states.map((s, i) => {
                  const n = i + 1, on = n === sel;
                  const cls = s === 'fail' ? 'border-crit-line bg-crit-bg text-crit' : s === 'warn' ? 'border-warn-line bg-warn-bg text-warn' : s === 'measuring' ? 'border-brand-line bg-brand-tint text-brand' : s === 'none' ? 'border-dashed border-line bg-white text-ink-2' : s === 'wait' ? 'border-transparent bg-tile text-ink-3' : 'border-line bg-white';
                  return <button key={n} disabled={s === 'wait'} onClick={() => { setSeqSel(n); setZoom(true); }} className={`relative rounded-ctl border text-card font-bold ${cls} ${on ? '!border-2 !border-ink' : ''}`}>
                    {n}{s === 'measuring' && <span className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-brand" />}</button>;
                })}{Array.from({ length: mapRows * 15 - states.length }, (_, i) => <span key={`e${i}`} title="이 로트에 없는 순번" className="flex items-center justify-center rounded-ctl border border-dashed border-line-soft text-card font-bold text-ink-3">{states.length + i + 1}</span>)}</div>
                <div className="mt-2 flex flex-wrap gap-3 text-small text-ink-2"><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded border border-line bg-white align-middle" />합격</span><span className="text-crit"><i className="mr-1 inline-block h-2.5 w-2.5 rounded bg-crit-bg align-middle ring-1 ring-crit-line" />불합격</span><span className="text-warn"><i className="mr-1 inline-block h-2.5 w-2.5 rounded bg-warn-bg align-middle ring-1 ring-warn-line" />주의 (3σ 밖 · M6 불합격)</span><span className="text-brand">● 측정 중</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded border border-dashed border-line align-middle" />기록 없음</span><span>회색 대기</span><span className="text-ink-3">연한 점선 = 이 로트에 없는 순번</span></div>
                {sel && <div className="mt-3 rounded-tile border border-line bg-white px-3 py-2 text-body">순번 {sel} · {states[sel - 1] === 'fail' ? '불합격' : states[sel - 1] === 'none' ? '기록 없음' : '합격'}{selRow1 ? ` · Ø45 ${num(selRow1.measured_value)} · ${hm(selRow1.measured_at)}` : ''}{cmmWarn(sel) && <b className="text-warn"> ▲ 관리도 3σ 밖</b>}
                  <span className="ml-1">· M6 {gv[`${lot}|${sel}|6`] === 'PASS' ? '합격' : gv[`${lot}|${sel}|6`] === 'FAIL' ? <b className="text-warn">▲ 불합격 (주의)</b> : '입력 전'} <span className="text-small text-ink-2">(작업자 게이지)</span></span></div>}
              </div>
              {!eve && <div className="col-span-2">{tolGrid}</div>}{/* 이브 닫힘: 공차 칸을 아래 한 줄 전체에 좌·가운데·우 2개씩 (사용자 요청 2026-10-19) */}
            </div>
          )}
        </section>
        {zoom && sel && <PartZoom seq={sel} total={total} states={states} onSeq={(n) => setSeqSel(n)} onClose={() => setZoom(false)}>
          <PartSketch rows={rows} seq={sel} mainRow={mainRow} items={items} qItem={qItem} m6={gv[`${lot}|${sel}|6`]} />
          <div className="mt-3 grid grid-cols-3 gap-2">{ORDER.map((k) => { const it = items.find((x) => String(x.item_seq) === k); const r = mainRow(sel, k); return it ? <TolBar key={k} card it={it} q={qItem(k)} v={r ? num(r.measured_value) : null} /> : null; })}</div>
        </PartZoom>}

        {/* 측정 시작 확인 · 측정 결과 */}
        <div className="grid grid-cols-[1fr_2fr] gap-4">
          <section className={box}>
            <H3>측정 시작 확인</H3>
            <div className="mt-3 text-card">측정 지시 <b>{cur?.lot_no ?? '—'}</b>{measuringSeq ? <> · <b>순번 {measuringSeq}</b></> : ''}{L?.enhanced ? ' · 강화' : ''}</div>
            {isOpr ? (<div className="mt-2 flex flex-col gap-2 text-body">
              <div className="flex items-center gap-2"><input value={bar} onChange={(e) => setBar(e.target.value)} placeholder="로트 바코드 찍기" className="h-10 w-[180px] rounded-tile border border-line px-2" />{bar && <span className={bar === cur?.lot_no ? 'font-bold text-ok' : 'font-bold text-crit'}>{bar === cur?.lot_no ? '✓ 로트 바코드 일치' : '✕ 다른 로트'}</span>}</div>
              <button onClick={() => setMe(true)} className="h-10 w-fit rounded-tile border border-line bg-white px-3">{me ? `✓ 본인 확인 ${user.name}` : '본인 확인'}</button>
            </div>) : <p className="mt-2 text-small text-ink-2">바코드·본인 확인은 OP-50 작업자 태블릿</p>}
            <div className="mt-3 inline-flex rounded-full bg-brand-tint px-3 py-1.5 text-body font-bold text-brand">● CMM-01 {cur?.state_code === 'RUN' ? '측정 중 → 결과 대기' : STATUS[cur?.state_code ?? ''] ?? (cur?.state_code === 'IDLE' ? '대기' : cur?.state_code ?? '—')}</div>
          </section>
          <section className={box}>
            <H3 right={<span className="rounded-full bg-tile px-3 py-1 text-small">부품 판정: {sel && gv[`${lot}|${sel}|6`] && gv[`${lot}|${sel}|7`] ? '입력 끝' : 'M6·외관 입력 기다림'}</span>}>측정 결과 — 순번 {sel ?? '—'}</H3>
            <div className="mt-2 border-b border-line-soft pb-3 text-body">확인 상태 <b>{selRow1?.check_status === 'NORMAL' ? '정상' : selRow1 ? '확인 필요' : '—'}</b> · 부품 <b className="font-mono">{selRow1?.part_temp_c ?? '—'} ℃</b> · 방 <span className="font-mono">{selRow1?.room_temp_c ?? '—'} ℃</span></div>
            {sel && ([['6', 'M6 나사 게이지'], ['7', '외관']] as const).map(([k, label]) => { const kk = `${lot}|${sel}|${k}`; return (
              <div key={k} className="mt-3 grid grid-cols-[140px_1fr] items-center gap-3 text-body"><b>{label}</b>
                <div className="flex flex-wrap items-center gap-2">{gv[kk] ? <span className="font-bold">{gv[kk] === 'PASS' ? '합격' : gv[kk] === 'FAIL' ? '불합격' : `불합격 · ${gv[kk]}`}</span> : <span className="text-ink-2">입력 전</span>}
                  {isOpr && (k === '6' ? (['PASS', 'FAIL'] as const).map((x) => <button key={x} onClick={() => setGv((g) => ({ ...g, [kk]: x }))} className="h-9 rounded-tile border border-line bg-white px-3">{x === 'PASS' ? '합격' : '불합격'}</button>)
                    : <><button onClick={() => setGv((g) => ({ ...g, [kk]: 'PASS' }))} className="h-9 rounded-tile border border-line bg-white px-3">합격</button><select value={gv[kk] && gv[kk] !== 'PASS' ? gv[kk] : ''} onChange={(e) => setGv((g) => ({ ...g, [kk]: e.target.value }))} className="h-9 rounded-tile border border-line"><option value="">불합격 + 코드</option>{defs.filter((d) => /^(SUR|VIS|BUR)/.test(d.defect_code)).map((d) => <option key={d.defect_code} value={d.defect_code}>{d.defect_code} {d.defect_name}</option>)}</select></>)}</div>
              </div>); })}
          </section>
        </div>

        {/* 결과 파일 · 재측정 · 수동 입력 */}
        <div className="grid grid-cols-[1.6fr_1fr] items-stretch gap-4">{/* 결과 파일 높이 = 오른쪽(재측정·수동 입력) 끝까지 (사용자 요청 2026-10-19) */}
          <section className={`${box} flex flex-col`}>
            <H3><span className="whitespace-nowrap">결과 파일 (가져오기 기록)</span> <span className="text-body font-normal text-ink-2">— 9월 {cmm.data?.counts.past ?? '—'}건 · 오늘 {cmm.data?.counts.today ?? '—'}건 · 9월 오류 {cmm.data?.errors_30d.length ?? 0}건</span></H3>
            {/* 이브 열림: [contain:size]로 표 높이가 칸 높이를 늘리지 않게 → 오른쪽(재측정·수동 입력) 끝에 맞춰 자르고 안에서 스크롤 */}
            <div className="mt-3 min-h-[130px] flex-1 overflow-y-auto [contain:size]">
            <table className="w-full text-left text-body">
              <thead className="sticky top-0 bg-brand-tint text-small text-ink-2"><tr><th className="px-2 py-2">받은 시각</th><th className="px-2">로트 · 순번</th><th className="px-2">상태</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{todayFiles.map((x) => (
                <tr key={x.cmm_import_id}><td className="px-2 py-2.5 font-mono">{hm(x.received_at)}</td><td className="px-2 font-mono">{fileOf(x)}</td>
                  <td className="px-2">{x.status === 'SUCCESS' ? '성공' : <span className="flex flex-wrap items-center gap-2"><b className="text-crit">✕ 실패 {x.error_text ? `(${x.error_text})` : ''}</b>{isSup && <button onClick={() => toast('다시 읽기 — 원본 파일은 남아 있습니다 (시연: 같은 결과)')} className="h-8 rounded-tile border border-line bg-white px-2 text-small">다시 읽기</button>}</span>}</td></tr>))}
                {todayFiles.length === 0 && <tr><td colSpan={3} className="py-3 text-ink-2">오늘 받은 결과 파일 없음</td></tr>}</tbody>
            </table>
            </div>
          </section>
          <div className="flex flex-col gap-4">
            <section className={box}>
              <H3>재측정{remeasure.length ? ` — 순번 ${remeasure[0][0]}` : ''}</H3>
              {remeasure.length === 0 ? <p className="mt-2 text-body text-ink-2">재측정한 부품 없음</p> : remeasure.slice(0, 3).map(([s, it]) => {
                const rs = rows.filter((r) => String(r.part_seq) === s && String(r.item_seq) === it && (r.position == null || r.position === '' || r.position === 'MID')), k = `${lot}|${s}|${it}`;
                return (<div key={k} className="mt-2"><div className="text-small text-ink-2">순번 {s} · {SHORT[it] ?? it}</div>
                  <div className="mt-1 grid grid-cols-2 gap-2">{rs.map((r) => { const pj = judge(items.find((x) => String(x.item_seq) === it), num(r.measured_value)); const on = picked[k] === Number(r.remeasure_seq);
                    return <button key={r.remeasure_seq} disabled={!isSup} onClick={() => setPicked((p) => ({ ...p, [k]: Number(r.remeasure_seq) }))} className={`rounded-tile border px-3 py-2 text-left font-mono text-small text-brand ${on ? 'border-2 border-brand' : 'border-line'}`}><b className="font-sans">{Number(r.remeasure_seq) > 1 ? `재측정 ${Number(r.remeasure_seq) - 1}` : '처음'}</b><br />{num(r.measured_value)} · {hm(r.measured_at)} · {pj === 'PASS' ? '합격' : '불합격'}</button>; })}</div>
                  <div className="mt-1 text-small">{picked[k] ? `판정에 쓸 값: ${picked[k] > 1 ? `재측정 ${picked[k] - 1}` : '처음'}` : '고르기 전 · 확인 필요'}</div></div>);
              })}
            </section>
            <section className={box}>
              <H3>수동 입력{sel ? ` — 순번 ${sel}` : ''}</H3>
              {isOpr && sel ? (<div className="mt-2 flex flex-wrap items-center gap-2 text-body">
                <select value={mi.item} onChange={(e) => setMi({ ...mi, item: e.target.value })} className="h-10 rounded-tile border border-line">{cmmItems.map((i) => <option key={i.item_seq} value={i.item_seq}>{i.item_name}</option>)}</select>
                <input value={mi.v} onChange={(e) => setMi({ ...mi, v: e.target.value })} placeholder="값" className="h-10 w-24 rounded-tile border border-line px-2" />
                <button disabled={!mi.v} onClick={() => { setManual((l) => [...l, { lot_no: lot, part_seq: sel, item_seq: Number(mi.item), measured_value: Number(mi.v), measured_at: simIso(), input_method: 'MANUAL', entered_by: user.id, check_status: 'CHECK', use_for_judgement: false, remeasure_seq: 1 }]); setMi({ ...mi, v: '' }); toast(`순번 ${sel} 수동 저장 — 반장 확인 필요`); }} className="h-10 rounded-tile bg-brand px-4 font-bold text-white hover:bg-brand-ink disabled:bg-line">수동 저장</button>
              </div>) : <p className="mt-2 text-body text-ink-2">{isOpr ? '부품 지도에서 순번을 고르세요' : '입력 대기 (OP-50 작업자) · 반장이 확인'}</p>}
            </section>
          </div>
        </div>

        {/* 검사 강화 */}
        <section className={box}>
          <H3>검사 강화 {enhPast && <span className="text-body font-normal text-ink-2">— 지금 강화 중인 로트 없음</span>}</H3>
          {/* 고른 로트가 강화·보류와 상관없으면 그 로트 기준으로 먼저 말하고, 9월 보류 기록은 접어 둠 — 어느 로트를 쳐도 "보류"가 보이던 것 고침 (사용자 요청 2026-10-21) */}
          {enhPast && <p className="mt-2 text-body"><b className="font-mono">{lot || '—'}</b> — 보통 검사 ({plan?.plan_mode === 'FULL' ? '전수' : '발췌'}) · 강화 · 보류 없음{L ? ` · ${STATUS[L.status] ?? L.status}` : ''}</p>}
          <details open={!enhPast} className="mt-3">
          {enhPast && <summary className="cursor-pointer text-body text-ink-2">참고: 최근 강화 기록 (시연 데이터 9월 · 이 로트와 별개)</summary>}
          <div className="mt-3 grid grid-cols-[1.6fr_1fr] gap-6">
            <table className="w-full text-left text-body">
              <thead className="bg-brand-tint text-small text-ink-2"><tr><th className="px-2 py-2">로트</th><th className="px-2">왜 강화</th><th className="px-2">상태</th><th className="px-2 text-right">측정한 부품 / 로트</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{enhRows.map((x) => (
                <tr key={x.lot_no}><td className="px-2 py-2.5 font-mono font-bold">{x.lot_no}</td>
                  <td className="px-2">{x.enhance_reason === 'HOLD_LOT' ? '보류 로트 · 남은 부품 전수' : x.enhance_reason === 'NEXT_LOT' ? '보류 다음 로트' : x.enhance_reason ?? '—'}</td>
                  <td className="px-2">{x.on_hold ? <><LockIcon /> </> : ''}<b>{STATUS[x.status] ?? x.status}</b>{x.status === 'IN_PROCESS' ? ` (${Object.entries(x.process_done ?? {}).filter(([k, v]) => k !== 'DONE' && Number(v) > 0).map(([k]) => k).pop() ?? 'OP-10'})` : ''}</td>
                  <td className="px-2 text-right font-mono">{x.process_done?.['OP-50'] ?? 0} / {x.input_qty}</td></tr>))}
                {enhRows.length === 0 && <tr><td colSpan={4} className="py-3 text-ink-2">검사 강화 기록 없음</td></tr>}</tbody>
            </table>
            <div className="text-body">
              <b>보통으로 돌아오기</b>
              {enhPast ? (lastHold ? (
                <div className="mt-2 rounded-tile border border-line bg-white px-3 py-2 leading-relaxed">
                  <div className="text-small text-ink-2">최근 기록</div>
                  <div><b className="font-mono">{lastHold.lot_no}</b> 보류 · {md(lastHold.held_at)} {hm(lastHold.held_at)}</div>
                  <div className="text-small text-ink-2">{String(lastHold.hold_reason ?? '').split(' — ')[0]}</div>
                  <div>→ 다음 로트 {lastHold.enhanced_next_lots}개 강화</div>
                  <div>→ <b>보통 복귀</b> {lastHold.normal_resumed_at ? `${md(lastHold.normal_resumed_at)} ${hm(lastHold.normal_resumed_at)} · ${userName(lastHold.normal_resumed_by)}` : '—'}</div>
                </div>) : <p className="mt-2 text-ink-2">기록 없음</p>) : (<>
              <div className="mt-2 flex items-start gap-2"><input type="checkbox" readOnly checked={causeDone} className="mt-1 h-4 w-4" /><div>원인 조치 완료<div className="text-small text-ink-2">작업기록서 확정 {causeDone ? '있음' : '없음'}</div></div></div>
              <div className="mt-2 flex items-start gap-2"><input type="checkbox" readOnly checked={allPass} className="mt-1 h-4 w-4" /><div>강화 로트 모두 합격<div className="text-small text-ink-2">판정 끝 {enhancedLots.filter((x) => x.judgement).length} / {enhancedLots.length}</div></div></div>
              <button disabled={!isSup || !causeDone || !allPass || !!backOk[lot]} onClick={() => setConfirmBack(true)} className="mt-3 h-10 rounded-tile border border-line bg-tile px-4 font-bold disabled:text-ink-3">{backOk[lot] ? '확인함' : '확인'}</button>
              <div className="mt-1 text-small text-ink-2">조건 {Number(causeDone) + Number(allPass)} / 2</div></>)}
            </div>
          </div>
          </details>
        </section>

      </div>
      {confirmBack && <ConfirmBox title="보통 검사로 돌아갈까요?" okLabel="확인" body="원인 조치와 강화 로트 합격을 확인했습니다. 다음 로트부터 발췌 검사로 돌아갑니다."
        onOk={() => { setBackOk((b) => ({ ...b, [lot]: user.id })); setConfirmBack(false); toast('반장 확인 — 보통 검사로 돌아감'); }} onCancel={() => setConfirmBack(false)} />}
    </div>
  );
}

// 부품 모식도 크게 보기 — 부품 지도·모식도를 누르면 뜸. ‹ › 로 앞뒤 부품, Esc·바깥 누르면 닫힘
function PartZoom({ seq, total, states, onSeq, onClose, children }: { seq: number; total: number; states: string[]; onSeq: (n: number) => void; onClose: () => void; children: React.ReactNode }) {
  const step = (d: number) => { let n = seq + d; while (n >= 1 && n <= total && states[n - 1] === 'wait') n += d; if (n >= 1 && n <= total) onSeq(n); };
  useEffect(() => { const f = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); if (e.key === 'ArrowLeft') step(-1); if (e.key === 'ArrowRight') step(1); }; window.addEventListener('keydown', f); return () => window.removeEventListener('keydown', f); });
  const st = states[seq - 1];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={`순번 ${seq} 부품 모식도`} onClick={(e) => e.stopPropagation()} className="max-h-[94vh] w-[min(920px,94vw)] overflow-y-auto rounded-card bg-white p-5 shadow-2xl">
        <div className="flex items-center gap-3">
          <b className="text-title">순번 {seq}</b>
          <span className={`rounded-full px-3 py-0.5 text-body font-bold ${st === 'fail' ? 'bg-crit-bg text-crit' : st === 'warn' ? 'bg-warn-bg text-warn' : st === 'none' ? 'bg-tile text-ink-2' : 'bg-brand-tint text-brand'}`}>{st === 'fail' ? '불합격' : st === 'warn' ? '▲ 주의' : st === 'none' ? '기록 없음' : st === 'measuring' ? '측정 중' : '합격'}</span>
          <div className="ml-auto flex gap-2">
            <button onClick={() => step(-1)} disabled={seq <= 1} className="h-11 w-11 rounded-tile border border-line text-title disabled:text-ink-3" aria-label="앞 부품">‹</button>
            <button onClick={() => step(1)} disabled={seq >= total} className="h-11 w-11 rounded-tile border border-line text-title disabled:text-ink-3" aria-label="다음 부품">›</button>
            <button onClick={onClose} className="h-11 rounded-tile border border-line bg-white px-5 text-card font-bold text-ink hover:border-brand-line">닫기</button>
          </div>
        </div>
        <div className="mt-3 rounded-tile border border-line-soft bg-tile p-2">{children}</div>
      </div>
    </div>);
}

// 공차 안 위치 — 공차(실선) · 관리 한계(점선) 안에서 값 위치. card = 3×2 칸용 세로 모양 (사용자 요청 2026-10-19)
function TolBar({ it, q, v, card }: { it: R; q?: R; v: number | null; card?: boolean }) {
  const lsl = num(it.lsl), usl = num(it.usl)!, lo = lsl ?? 0, span = usl - lo || 1, pad = span * 0.18;
  const pos = (n: number) => `${Math.min(100, Math.max(0, ((n - (lo - pad)) / (span + pad * 2)) * 100))}%`;
  const pj = judge(it, v), out = q?.ucl != null && v != null && (v > q.ucl || v < q.lcl);
  const k = String(it.item_seq), c = ITEM_COLOR[k];
  const bar = (
    <div className={`relative h-3 rounded ${card ? 'bg-white shadow-[inset_0_0_0_1px_rgba(15,23,42,.18)]' : 'bg-brand-tint'}`}>{/* 카드는 파스텔 바탕이라 흰 막대 + 얇은 선으로 구분 (2026-10-25) */}
      {lsl != null && <span className="absolute -top-1 h-5 w-[2px] bg-ink" style={{ left: pos(lsl) }} />}<span className="absolute -top-1 h-5 w-[2px] bg-ink" style={{ left: pos(usl) }} />
      {q?.ucl != null && <><span className="absolute top-0 h-3 border-l border-dashed border-slate-500" style={{ left: pos(q.ucl) }} />{lsl != null && <span className="absolute top-0 h-3 border-l border-dashed border-slate-500" style={{ left: pos(q.lcl) }} />}</>}
      {v != null && <span className={`absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white ${pj === 'FAIL' ? 'bg-crit' : out ? 'bg-warn-mark' : 'bg-ink'}`} style={{ left: pos(v) }} />}
    </div>);
  const note = pj === 'FAIL' ? <span className="text-small font-bold text-crit">공차 밖</span> : out ? <span className="text-small font-bold text-warn">관리 한계 밖</span> : null;
  const range = <span className="font-mono text-small text-ink-2">{lsl != null ? `${lsl}~${usl}` : `${usl} 이하`}</span>;
  if (card) return (
    <div className="rounded-tile border-2 px-3 py-2" style={{ borderColor: c?.line ?? '#cbd5e1', background: c?.bg ?? '#fff' }}>
      <div className="flex items-baseline justify-between gap-2"><b className="whitespace-nowrap text-body" style={{ color: c?.text }}>{SHORT[k] ?? it.item_name}</b><span className="flex items-baseline gap-2">{note}<b className="font-mono text-card">{v == null ? '—' : k === '4' && v >= 0 ? `+${v}` : v}</b></span></div>
      <div className="mt-2">{bar}</div>
      {/* 공차 하한·상한을 검은 공차선 바로 밑에 (사용자 요청 2026-10-19) */}
      <div className="relative mt-1 h-4 font-mono text-small font-semibold text-ink-2">
        {lsl != null && <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: pos(lsl) }}>{it.lsl}</span>}
        <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: pos(usl) }}>{it.usl}</span>
      </div>
    </div>);
  return (
    <div className="grid grid-cols-[110px_1fr_90px] items-center gap-3 border-b border-line-soft py-2">
      <div><b className="text-body" style={{ color: c?.text }}>{SHORT[k] ?? it.item_name}</b><div>{range}</div></div>
      {bar}
      <div className="text-right"><b className="font-mono text-card">{v ?? '—'}</b>{note && <div>{note}</div>}</div>
    </div>);
}

// 부품 모식도 — 실제 형상이 아니라 측정 위치 안내용 그림. 측정 항목 6가지를 색으로 나눔 (치수선·이름표·공차 칸이 같은 색)
// M6 나사는 작업자가 게이지로 확인한 합격·불합격 (숫자 없음)
function PartSketch({ rows, seq, mainRow, items, qItem, m6 }: { rows: R[]; seq: number | null; mainRow: (s: number, i: string) => R | undefined; items: R[]; qItem: (k: string) => R | undefined; m6?: string }) {
  const val = (i: string) => (seq ? num(mainRow(seq, i)?.measured_value) : null);
  const pos = (p: string) => (seq ? num(rows.find((r) => Number(r.part_seq) === seq && String(r.item_seq) === '1' && r.position === p)?.measured_value) : null);
  // 윗면 평행사변형 A(150,190)·B(410,88)·C(530,136)·D(270,236): 길이 150 mm → A→B, 폭 55 mm → A→D. 두께 12 mm → 아래로 28
  const FACE = `matrix(${260 / 150} ${-102 / 150} ${120 / 55} ${46 / 55} 150 190)`, DEPTH = 28;
  const P = (u: number, v: number) => [150 + (u * 260) / 150 + (v * 120) / 55, 190 - (u * 102) / 150 + (v * 46) / 55];
  const HOLE = [32, 27.5], M6: [number, number][] = [[128, 14], [128, 41]]; // 폭 가운데 Ø45, 쪽마다 5 mm 살 (DOC-06 §2 8번). 길이 방향 자리는 도면에 없어 [모식도] 값
  const hc = P(HOLE[0], HOLE[1]), m6a = P(...M6[0]), m6b = P(...M6[1]), hl = P(HOLE[0] - 22.5, HOLE[1]), hr = P(HOLE[0] + 22.5, HOLE[1]), flat = P(92, 44);
  const tw = (t: string) => [...t].reduce((n, ch) => n + (ch >= 'ᄀ' ? 16.5 : 9.8), 0) + 18;
  const state = (k: string) => { const it = items.find((x) => String(x.item_seq) === k), v = val(k), q = qItem(k); if (v == null) return ''; if (judge(it, v) === 'FAIL') return 'fail'; return q?.ucl != null && (v > q.ucl || v < q.lcl) ? 'warn' : ''; };
  // 이름표: x,y = 왼쪽 위. 글자 굵게, 항목 색 테두리·바탕. 불합격 ✕ 빨강, 관리 한계 밖 ▲
  const tag = (k: string, x: number, y: number, label: string, value: string, sub?: string) => {
    const c = ITEM_COLOR[k] ?? { line: '#94a3b8', bg: '#fff', text: '#475569' }, st = k === 'M6' ? (m6 === 'FAIL' ? 'warn' : '') : state(k);
    const mark = st === 'fail' ? '✕ ' : st === 'warn' ? '▲ ' : '', w = tw(mark + label + ' ' + value);
    return <g key={k}><rect x={x} y={y} width={w} height={30} rx="7" fill={st === 'fail' ? '#fdeeee' : c.bg} stroke={st === 'fail' ? '#c62a2f' : c.line} strokeWidth="2.5" />
      <text x={x + 9} y={y + 21} fontSize="16" fontWeight="800" fill={st === 'fail' ? '#c62a2f' : st === 'warn' ? '#8a6d00' : c.text}>{mark}{label} <tspan fill="#1c2530" fontFamily="monospace">{value}</tspan></text>
      {sub && <text x={x + 4} y={y + 46} fontSize="13" fontWeight="700" fill="#475569">{sub}</text>}</g>;
  };
  const lead = (k: string, x1: number, y1: number, x2: number, y2: number) => <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={ITEM_COLOR[k]?.line ?? '#94a3b8'} strokeWidth="2" />;
  const dim = (k: string, x1: number, y1: number, x2: number, y2: number, tick: [number, number]) => <g stroke={ITEM_COLOR[k].line} strokeWidth="2.5">
    <line x1={x1} y1={y1} x2={x2} y2={y2} /><line x1={x1 - tick[0]} y1={y1 - tick[1]} x2={x1 + tick[0]} y2={y1 + tick[1]} /><line x1={x2 - tick[0]} y1={y2 - tick[1]} x2={x2 + tick[0]} y2={y2 + tick[1]} /></g>;
  const fmt = (k: string) => { const v = val(k); return v == null ? '—' : k === '4' && v >= 0 ? `+${v}` : String(v); };
  const t1 = pos('TOP'), b1 = pos('BOT') ?? pos('BOTTOM');
  return (
    <svg viewBox="0 0 600 320" className="w-full">
      <polygon points="150,190 410,88 530,136 270,236" fill="#c9d3e0" stroke="#5b6b80" strokeWidth="1.5" />
      <polygon points="150,190 270,236 270,264 150,218" fill="#9fb0c6" stroke="#5b6b80" strokeWidth="1.5" />
      <polygon points="270,236 530,136 530,164 270,264" fill="#b3c1d4" stroke="#5b6b80" strokeWidth="1.5" />
      {/* 구멍은 윗면 좌표(mm)로 그린 뒤 윗면 기울기(FACE)대로 옮김. 관통 구멍이라 아래 구멍(두께 아래)이 비쳐 보임 */}
      <defs><clipPath id="ps-hole"><circle cx={HOLE[0]} cy={HOLE[1]} r={22.5} transform={FACE} /></clipPath></defs>
      <circle cx={HOLE[0]} cy={HOLE[1]} r={22.5} transform={FACE} fill="#7f90a6" stroke="#5b6b80" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      <g clipPath="url(#ps-hole)"><circle cx={HOLE[0]} cy={HOLE[1]} r={22.5} transform={`translate(0 ${DEPTH}) ${FACE}`} fill="#f6f8fc" /></g>
      {M6.map(([u, v]) => <circle key={v} cx={u} cy={v} r={3.5} transform={FACE} fill="#5b6b80" />)}
      {/* 치수선 — 항목 색 */}
      <line x1={hl[0]} y1={hl[1]} x2={hr[0]} y2={hr[1]} stroke={ITEM_COLOR['1'].line} strokeWidth="3" />
      <line x1={hc[0]} y1={hc[1]} x2={m6a[0]} y2={m6a[1]} stroke={ITEM_COLOR['4'].line} strokeWidth="2.5" strokeDasharray="6 4" />
      {dim('2', 270, 278, 530, 178, [3, 8])}{dim('8', 140, 228, 260, 274, [7, -3])}{dim('3', 140, 190, 140, 218, [6, 0])}
      <polygon points={`${flat[0] - 14},${flat[1] + 6} ${flat[0] + 6},${flat[1] - 2} ${flat[0] + 16},${flat[1] + 2} ${flat[0] - 4},${flat[1] + 10}`} fill="none" stroke={ITEM_COLOR['5'].line} strokeWidth="2.5" />
      {/* 이름표 + 끌어낸 선 */}
      {lead('1', 150, 128, hl[0] + 6, hl[1] - 4)}{tag('1', 8, 98, 'Ø45', fmt('1'), t1 != null || b1 != null ? `위 ${t1 ?? '—'} · 아래 ${b1 ?? '—'}` : undefined)}
      {lead('4', 330, 52, (hc[0] + m6a[0]) / 2, (hc[1] + m6a[1]) / 2)}{tag('4', 250, 24, '구멍 간', fmt('4'))}
      {lead('5', 470, 64, flat[0] + 4, flat[1])}{tag('5', 430, 36, '평면도', fmt('5'))}
      {tag('3', 6, 190, '두께', fmt('3'))}
      {lead('8', 120, 284, 200, 252)}{tag('8', 40, 282, '폭', fmt('8'))}
      {tag('2', 380, 256, '길이', fmt('2'))}
      {lead('M6', 466, 112, m6b[0] + 4, m6b[1] - 2)}{tag('M6', 466, 96, 'M6', m6 === 'PASS' ? '합격' : m6 === 'FAIL' ? '불합격' : '—')}
    </svg>);
}

// I-MR 관리도 — 공차(실선) · 관리 한계(점선) · 중심선, 점을 누르면 아래에 값
function IMR({ it, sel, onSel }: { it: R; sel: number | null; onSel: (i: number | null) => void }) {
  const v: { at: string; v: number }[] = it.values ?? [];
  if (v.length < 2) return <p className="mt-3 text-small text-ink-2">관리도: 측정값이 부족합니다</p>;
  const W = 1100, H = 230, L0 = 60, R0 = 120, xs = v.map((x) => x.v), usl = num(it.usl), lsl = num(it.lsl);
  const lo = Math.min(...xs, lsl ?? Infinity, it.lcl ?? Infinity), hi = Math.max(...xs, usl ?? -Infinity, it.ucl ?? -Infinity), r = hi - lo || 1;
  const y = (n: number) => H - 14 - ((n - lo) / r) * (H - 28), x = (i: number) => L0 + (i / (v.length - 1)) * (W - L0 - R0);
  const mr = xs.slice(1).map((n, i) => Math.abs(n - xs[i])), mrBar = mr.reduce((s, n) => s + n, 0) / mr.length, mrU = mrBar * 3.267, MH = 110, my = (n: number) => MH - 10 - (n / (Math.max(...mr, mrU) || 1)) * (MH - 20);
  const st = (n: number) => ((usl != null && n > usl) || (lsl != null && n < lsl) ? 'fail' : it.ucl != null && (n > it.ucl || n < it.lcl) ? 'warn' : 'ok');
  const lab = (yy: number, t: string) => <text x={W - R0 + 8} y={yy + 4} fontSize="12" fill="#1c2530">{t}</text>;
  const k = sel ?? v.length - 1, p = v[k];
  return (<div className="mt-3">
    <div className="flex flex-wrap gap-4 text-small text-ink-2"><span>● 정상</span><span className="text-warn">▲ 관리 한계(3σ) 밖 {xs.filter((n) => st(n) === 'warn').length}</span><span className="text-crit">✕ 불합격(공차 밖) {xs.filter((n) => st(n) === 'fail').length}</span><span>— 공차 USL·LSL</span><span>- - 관리 한계 UCL·LCL</span><span>— 중심선 CL</span></div>
    <div className="mt-2 text-small font-bold">I — 개별값</div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      {usl != null && <><line x1={L0} x2={W - R0} y1={y(usl)} y2={y(usl)} stroke="#1c2530" strokeWidth="1.5" />{lab(y(usl), `USL ${usl}`)}</>}
      {lsl != null && <><line x1={L0} x2={W - R0} y1={y(lsl)} y2={y(lsl)} stroke="#1c2530" strokeWidth="1.5" />{lab(y(lsl), `LSL ${lsl}`)}</>}
      {it.ucl != null && <><line x1={L0} x2={W - R0} y1={y(it.ucl)} y2={y(it.ucl)} stroke="#1c2530" strokeDasharray="5 4" />{lab(y(it.ucl), `UCL ${it.ucl}`)}<line x1={L0} x2={W - R0} y1={y(it.lcl)} y2={y(it.lcl)} stroke="#1c2530" strokeDasharray="5 4" />{lab(y(it.lcl), `LCL ${it.lcl}`)}<line x1={L0} x2={W - R0} y1={y(it.mean)} y2={y(it.mean)} stroke="#94a3b8" />{lab(y(it.mean), `CL ${it.mean}`)}</>}
      <polyline fill="none" stroke="#cbdcfb" strokeWidth="1.5" points={xs.map((n, i) => `${x(i)},${y(n)}`).join(' ')} />
      {xs.map((n, i) => { const s = st(n); return <g key={i} onClick={() => onSel(i)} className="cursor-pointer">{s === 'warn' ? <polygon points={`${x(i)},${y(n) - 7} ${x(i) - 7},${y(n) + 5} ${x(i) + 7},${y(n) + 5}`} fill="#e0b000" stroke="#8a6d00" /> : <circle cx={x(i)} cy={y(n)} r={s === 'fail' ? 6 : 4.5} fill={s === 'fail' ? '#c62a2f' : '#3d6fe0'} stroke={i === k ? '#1c2530' : 'none'} strokeWidth="2" />}</g>; })}
    </svg>
    <div className="text-small font-bold">MR — 이동 범위</div>
    <svg viewBox={`0 0 ${W} ${MH}`} className="w-full">
      <line x1={L0} x2={W - R0} y1={my(mrU)} y2={my(mrU)} stroke="#1c2530" strokeDasharray="5 4" />{lab(my(mrU), `UCL ${mrU.toFixed(4)}`)}
      <line x1={L0} x2={W - R0} y1={my(mrBar)} y2={my(mrBar)} stroke="#94a3b8" />{lab(my(mrBar), `MR ${mrBar.toFixed(4)}`)}
      <polyline fill="none" stroke="#3d6fe0" strokeWidth="1.5" points={mr.map((n, i) => `${x(i + 1)},${my(n)}`).join(' ')} />
      {[0, Math.floor(v.length / 3), Math.floor((v.length * 2) / 3), v.length - 1].map((i) => <text key={i} x={x(i)} y={MH} fontSize="11" textAnchor="middle" fill="#64748b">{hm(v[i].at)}</text>)}
    </svg>
    {p && <div className="mt-2 rounded-tile border border-line bg-white px-4 py-2 text-body">고른 점 · {md(p.at)} {hm(p.at)} · <b className="font-mono">{p.v}</b> · {st(p.v) === 'fail' ? '불합격' : '합격'}{st(p.v) === 'warn' ? ' · 관리 한계(3σ) 밖' : ''}{k > 0 ? ` · MR ${mr[k - 1].toFixed(4)}` : ''}</div>}
  </div>);
}

// 불량 집계 — 불량 코드별(많은 순) + 불량률
function DefectBox({ defects, defs, lots }: { defects: { defect_code: string; qty: number }[]; defs: R[]; lots: R[] }) {
  const list = [...defects].sort((a, b) => b.qty - a.qty), max = Math.max(1, ...list.map((d) => d.qty));
  const bad = list.reduce((s, d) => s + d.qty, 0), made = lots.reduce((s, l) => s + Number(l.input_qty ?? 0), 0);
  const grade = (d: R | undefined) => (!d ? '—' : String(d.grade_rule ?? '').startsWith('1번') ? '치명/중' : d.grade === 'CRITICAL' ? '치명' : d.grade === 'MAJOR' ? '중' : '경');
  return (
    <section className={box}>
      <H3 right={made ? <span className="text-body">불량률 <b className="font-mono text-title">{((bad / made) * 100).toFixed(2)}%</b> <span className="text-ink-2">({bad} / {made.toLocaleString()})</span></span> : undefined}>불량 집계 — 9/1 ~ 10/1</H3>
      <div className="mt-3 text-body font-bold">불량 코드별 (많은 순)</div>
      <table className="mt-2 w-full text-left text-body">
        <thead className="text-small text-ink-2"><tr className="border-b border-line-soft"><th className="w-[90px] py-2">코드</th><th>이름</th><th className="w-[90px]">등급</th><th className="w-[45%]">개수</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{list.map((d) => { const df = defs.find((x) => x.defect_code === d.defect_code); return (
          <tr key={d.defect_code}><td className="py-2 font-mono">{d.defect_code}</td><td>{df?.defect_name ?? '—'}</td><td>{grade(df)}</td>
            <td><div className="flex items-center gap-2"><div className="h-3.5 rounded bg-info" style={{ width: `${(d.qty / max) * 85}%` }} /><b className="font-mono">{d.qty}</b></div></td></tr>); })}</tbody>
      </table>
    </section>);
}
