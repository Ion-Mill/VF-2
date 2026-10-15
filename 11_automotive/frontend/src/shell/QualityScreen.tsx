'use client';
// SCR-20 검사 기록·불량 집계 — OP-50 측정값은 결과 파일(CSV)을 읽어 자동 기록 (서버: 9월 inspection_result + 10/1 실시간 측정).
// 사람은 확인만: 로트 바코드·본인 확인, M6 게이지·외관 버튼, (자동이 안 될 때만) 수동 입력, 재측정 값 고르기·반장 확인.
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { MASTERS } from './data';
import { hm, md, simIso, useFetch, usePersist } from './live';
import { userName } from './model';

type R = Record<string, any>;
const judge = (it: R | undefined, v: number | null) => {
  if (!it || v == null || isNaN(v)) return null;
  const lsl = it.lsl === '' ? null : Number(it.lsl), usl = it.usl === '' ? null : Number(it.usl);
  return (lsl == null || v >= lsl) && (usl == null || v <= usl) ? 'PASS' : 'FAIL';
};

export function QualityScreen() {
  const { key, back, role, user, twin, toast } = useApp();
  const items = MASTERS.inspection_items as R[], defs = MASTERS.defect_codes as R[];
  const [lot, setLot] = useState(key ?? twin?.equipment['CMM-01'].lot_no ?? '');
  const res = useFetch<{ results: R[]; plan: R | null }>(lot ? `inspection/results?lot=${encodeURIComponent(lot)}` : null, 8000, [lot]);
  const cmm = useFetch<{ imports: R[]; errors_30d: R[]; counts: R }>('inspection/cmm-imports', 15000);
  const qs = useFetch<{ defects: { defect_code: string; qty: number }[]; items: R[]; today_defects: R[] }>('quality/summary', 30000);
  const run = twin?.run_id ?? null;
  const [manual, setManual] = usePersist<R[]>('qManual', [], run);
  const [gv, setGv] = usePersist<Record<string, string>>('qGauge', {}, run); // `${lot}|${seq}|6` → PASS/FAIL, |7 → PASS or 코드
  const [picked, setPicked] = usePersist<Record<string, number>>('qPick', {}, run);
  const [checked, setChecked] = usePersist<Record<string, string>>('qCheck', {}, run);
  const [bar, setBar] = useState(''); const [me, setMe] = useState(false);
  const [itemSel, setItemSel] = useState('1');
  const [mi, setMi] = useState({ seq: '', item: '1', v: '' });
  const rows = [...(res.data?.results ?? []), ...manual.filter((m) => m.lot_no === lot)];
  const seqs = Array.from(new Set(rows.map((r) => Number(r.part_seq)))).sort((a, b) => a - b);
  const cur = twin?.equipment['CMM-01'];
  const plan = res.data?.plan;
  const isOpr = role === 'OPR', isSup = role === 'SUP';
  const cpk = qs.data?.items.find((x) => String(x.item_seq) === itemSel);
  const fails = rows.filter((r) => (r.use_for_judgement === true || r.use_for_judgement === 'true') && (judge(items.find((i) => String(i.item_seq) === String(r.item_seq)), r.measured_value === '' ? null : Number(r.measured_value)) ?? r.judgement) === 'FAIL').length;

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">검사 기록 <span className="text-[14px] font-normal text-slate-500">· OP-50 평소 약 0.9분/개 → 강화 5.0분/개</span></h2>
          <div className="flex gap-2"><input value={lot} onChange={(e) => setLot(e.target.value)} className="h-11 w-[220px] rounded-md border border-slate-300 px-2" /><button onClick={back} className={BTN}>닫기</button></div>
        </div>
        <div className="mt-1 text-[15px]">검사 방식: <b>{plan ? (plan.plan_mode === 'ENHANCED' || plan.enhance_reason ? `강화 (전수 + 항목 확대) · 사유 ${plan.enhance_reason}` : plan.plan_mode === 'FULL' ? '전수' : '발췌 (첫 부품 + 5개마다 1개)') : '10/1 로트 (측정 진행 중)'}</b>{plan?.judgement ? ` · 판정 ${plan.judgement} ${md(plan.judged_at)} ${hm(plan.judged_at)}` : ''}</div>

        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">[2] 측정 시작 확인 (OPR · OP-50 태블릿)</h3>
          측정 지시: 로트 <b>{cur?.lot_no ?? '—'}</b> · CMM-01 {cur?.state_code === 'RUN' ? '● 측정 중 → 결과 대기 (자동)' : cur?.state_code ?? '—'}
          {isOpr && <div className="mt-1 flex flex-wrap items-center gap-2"><input value={bar} onChange={(e) => setBar(e.target.value)} placeholder="로트 바코드 찍기" className="h-11 rounded-md border border-slate-300 px-2" />
            {bar && <span className={bar === cur?.lot_no ? 'font-bold text-[#13994f]' : 'font-bold text-[#c62a2f]'}>{bar === cur?.lot_no ? '✓ 일치' : '✕ 다름 — 측정 지시와 다른 로트'}</span>}
            <button onClick={() => setMe(true)} className={BTN}>본인 확인{me ? ' ✓' : ''}</button>{me && <span>측정자: {user.name} (로그인)</span>}</div>}
        </section>

        <section className="mt-3 border-t border-slate-200 pt-3">
          <h3 className="mb-1 text-[14px] font-bold text-slate-500">[3] 측정 결과 (CMM 자동 입력) — 부품 {seqs.length}개 · 측정 불합격 {fails}</h3>
          {rows.length === 0 ? <p className="text-[14px] text-slate-500">측정 전</p> : (
            <div className="max-h-[360px] overflow-y-auto"><table className="w-full text-left text-[13px]">
              <thead className="sticky top-0 bg-white text-slate-500"><tr>{['순번', '항목', '기준', '측정값', '판정(플랫폼/측정기)', '입력', '시각', '방', '부품', '확인'].map((h) => <th key={h} className="pr-2 font-semibold">{h}</th>)}</tr></thead>
              <tbody>{rows.filter((r) => r.position === '' || r.position == null || r.position === 'MID').slice(-200).map((r, i) => {
                const it = items.find((x) => String(x.item_seq) === String(r.item_seq)), v = r.measured_value === '' || r.measured_value == null ? null : Number(r.measured_value);
                const pj = judge(it, v), pt = r.part_temp_c === '' || r.part_temp_c == null ? null : Number(r.part_temp_c), mis = pj && r.cmm_judgement && pj !== r.cmm_judgement;
                const rk = `${lot}|${r.part_seq}|${r.item_seq}`, re = Number(r.remeasure_seq) > 1 || rows.some((x) => x.part_seq === r.part_seq && x.item_seq === r.item_seq && Number(x.remeasure_seq) > 1);
                return (
                  <tr key={i} className={`border-t border-slate-100 ${pj === 'FAIL' ? 'bg-[#fff0f0]' : ''}`}>
                    <td>{r.part_seq}{re ? ` (재${r.remeasure_seq})` : ''}</td><td>{it?.item_name ?? r.item_seq}{it?.char_class === 'SPECIAL' ? ' ★' : ''}</td><td>{it?.spec_text}</td><td>{v ?? '—'}</td>
                    <td>{pj ? (pj === 'PASS' ? '합격' : '불합격') : r.judgement === 'PASS' ? '합격' : r.judgement === 'FAIL' ? '불합격' : '—'}{r.cmm_judgement ? ` / ${r.cmm_judgement === 'PASS' ? '합격' : '불합격'}` : ''}{mis ? ' ▲ 불일치' : ''}</td>
                    <td>{r.input_method === 'CMM_AUTO' || r.cmm_import_id ? '자동' : r.input_method === 'MANUAL' ? '수동' : '사람 (버튼)'}</td><td>{hm(r.measured_at)}</td><td>{r.room_temp_c || '—'}</td>
                    <td className={pt != null && (pt < 16 || pt > 26) ? 'font-bold text-[#9a6200]' : ''}>{pt ?? '—'}{pt != null && (pt < 16 || pt > 26) ? ' ▲ 온도 확인' : ''}</td>
                    <td>{checked[rk] ? `반장 확인 (${userName(checked[rk])})` : r.check_status === 'NORMAL' ? '정상' : <>▲ 확인 필요 {isSup && <button onClick={() => setChecked((c) => ({ ...c, [rk]: user.id }))} className="ml-1 rounded border border-slate-300 px-1">확인</button>}</>}
                      {re && isSup && <button onClick={() => setPicked((p) => ({ ...p, [rk]: Number(r.remeasure_seq) }))} className="ml-1 rounded border border-slate-300 px-1">{picked[rk] === Number(r.remeasure_seq) ? '판정에 씀 ✓' : '이 값 쓰기'}</button>}</td>
                  </tr>);
              })}</tbody></table></div>
          )}
          {/* [3'] 사람 칸: M6 게이지(항목 6)·외관(항목 7) */}
          <div className="mt-2 text-[14px]"><b>M6 게이지 · 외관</b> (측정하지 않은 부품, 태블릿 버튼)
            <div className="mt-1 flex flex-wrap gap-2">{(seqs.length ? seqs : [1]).slice(-6).map((s) => {
              const k6 = `${lot}|${s}|6`, k7 = `${lot}|${s}|7`;
              return (<div key={s} className="rounded border border-slate-200 p-1">순번 {s}:
                {(['PASS', 'FAIL'] as const).map((x) => <button key={x} disabled={!isOpr} onClick={() => setGv((g) => ({ ...g, [k6]: x }))} className={`ml-1 h-10 rounded border px-2 ${gv[k6] === x ? 'border-[#0f9fbd] bg-[#e8f6fa]' : 'border-slate-300'}`}>M6 {x === 'PASS' ? '통과' : '불합격'}</button>)}
                <button disabled={!isOpr} onClick={() => setGv((g) => ({ ...g, [k7]: 'PASS' }))} className={`ml-1 h-10 rounded border px-2 ${gv[k7] === 'PASS' ? 'border-[#0f9fbd] bg-[#e8f6fa]' : 'border-slate-300'}`}>외관 합격</button>
                <select disabled={!isOpr} value={gv[k7] && gv[k7] !== 'PASS' ? gv[k7] : ''} onChange={(e) => setGv((g) => ({ ...g, [k7]: e.target.value }))} className="ml-1 h-10 rounded border border-slate-300"><option value="">외관 불합격 + 코드</option>{defs.filter((d) => d.defect_code.startsWith('SUR') || d.defect_code.startsWith('VIS') || d.defect_code.startsWith('BUR')).map((d) => <option key={d.defect_code} value={d.defect_code}>{d.defect_code} {d.defect_name}</option>)}</select>
              </div>);
            })}</div>
          </div>
        </section>

        <section className="mt-3 border-t border-slate-200 pt-3 text-[13px]">
          <h3 className="mb-1 text-[14px] font-bold text-slate-500">[3a] 결과 파일 (가져오기 기록) — 9월 {cmm.data?.counts.past ?? '—'}건 · 오늘 {cmm.data?.counts.today ?? '—'}건 · 9월 오류 {cmm.data?.errors_30d.length ?? 0}건</h3>
          <ul className="max-h-[160px] overflow-y-auto">{(cmm.data?.imports ?? []).slice(0, 20).map((x) => <li key={x.cmm_import_id} className={x.status !== 'SUCCESS' ? 'font-semibold text-[#9a6200]' : ''}>{md(x.received_at)} {hm(x.received_at)} {x.file_name} · {x.status === 'SUCCESS' ? '성공' : `▲ ${x.status} ${x.error_text ?? ''}`}{x.status !== 'SUCCESS' && isSup ? <button onClick={() => toast('다시 읽기 — 원본 파일은 남아 있습니다 (시연: 같은 결과)')} className="ml-1 rounded border border-slate-300 px-1">다시 읽기</button> : null}</li>)}</ul>
        </section>
        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">[3c] 수동 입력 (자동 입력이 안 될 때만 · "수동" 표시 + SUP 확인)</h3>
          {isOpr ? <div className="flex flex-wrap items-center gap-2">순번 <input value={mi.seq} onChange={(e) => setMi({ ...mi, seq: e.target.value })} className="h-11 w-16 rounded border border-slate-300 px-1" />
            항목 <select value={mi.item} onChange={(e) => setMi({ ...mi, item: e.target.value })} className="h-11 rounded border border-slate-300">{items.filter((i) => i.method === 'CMM').map((i) => <option key={i.item_seq} value={i.item_seq}>{i.item_name}</option>)}</select>
            값 <input value={mi.v} onChange={(e) => setMi({ ...mi, v: e.target.value })} className="h-11 w-24 rounded border border-slate-300 px-1" />
            <button disabled={!mi.seq || !mi.v} onClick={() => { setManual((l) => [...l, { lot_no: lot, part_seq: Number(mi.seq), item_seq: Number(mi.item), measured_value: Number(mi.v), measured_at: simIso(), input_method: 'MANUAL', entered_by: user.id, check_status: 'CHECK', use_for_judgement: false, remeasure_seq: 1 }]); setMi({ seq: '', item: mi.item, v: '' }); }} className={DARK}>수동 저장</button></div>
            : <span className="text-slate-500">작업자(OPR)만 입력, 반장이 위 표에서 확인</span>}
        </section>
        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">[3d] 로트 판정 · [4] 강화 상태</h3>
          측정 {seqs.length}개 · 불합격 {fails} → {fails > 0 ? <b className="text-[#9a6200]">▲ 보류 검토 (남은 부품 전수)</b> : plan?.judgement ? plan.judgement : '판정 전 (모두 잰 뒤)'}
          {plan?.enhance_reason && <div className="mt-1">강화: {plan.enhance_reason} · 보통으로 돌아오기: ☑ 원인 조치 완료 / {plan.judgement === 'PASS' ? '☑' : '☐'} 강화 로트 모두 합격 {isSup && <button disabled={plan.judgement !== 'PASS'} onClick={() => toast('반장 확인 — 보통 검사로 돌아감')} className={BTN}>확인</button>}</div>}
        </section>
        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">[5] 공정능력 (Cpk, I-MR) · [6] 관리도</h3>
          <table className="w-full text-left text-[13px]"><thead className="text-slate-500"><tr><th>항목</th><th>기준</th><th>n</th><th>Cpk</th><th>평균</th><th>관리 한계</th></tr></thead>
            <tbody>{(qs.data?.items ?? []).filter((x) => x.lsl !== '' || x.usl !== '').map((x) => (
              <tr key={x.item_seq} onClick={() => setItemSel(String(x.item_seq))} className={`cursor-pointer border-t border-slate-100 ${String(x.item_seq) === itemSel ? 'bg-[#e8f6fa]' : ''}`}>
                <td>{x.item_name}{x.char_class === 'SPECIAL' ? ' ★' : ''}</td><td>{x.cpk_min}</td><td>{x.n}</td>
                <td className={x.cpk != null && x.cpk < Number(x.cpk_min) ? 'font-bold text-[#9a6200]' : ''}>{x.cpk ?? `계산 중 (${x.n}/50)`}{x.cpk != null && x.cpk < Number(x.cpk_min) ? ' ▲ 전수 측정으로' : ''}</td><td>{x.mean ?? '—'}</td><td>{x.lcl != null ? `${x.lcl} ~ ${x.ucl}` : '—'}</td></tr>))}</tbody></table>
          {cpk && <IMR it={cpk} />}
        </section>
        <section className="mt-3 border-t border-slate-200 pt-3 text-[14px]">
          <h3 className="mb-1 font-bold text-slate-500">[7] 불량 집계 (9월 + 10/1, 불량 코드별 · DOC-06 8장)</h3>
          <div className="flex flex-wrap gap-3">{(qs.data?.defects ?? []).map((d) => <span key={d.defect_code}>{d.defect_code} {defs.find((x) => x.defect_code === d.defect_code)?.defect_name} <b>{d.qty}</b></span>)}</div>
          {(qs.data?.today_defects ?? []).length > 0 && <p className="mt-1">오늘: {(qs.data?.today_defects ?? []).map((d) => `${d.lot_no} ${d.defect_code} ${d.qty}`).join(' · ')}</p>}
        </section>
      </div>
    </div>
  );
}

function IMR({ it }: { it: R }) {
  const v: { at: string; v: number }[] = it.values ?? [];
  if (v.length < 2) return <p className="mt-2 text-[13px] text-slate-500">관리도: 측정값이 부족합니다</p>;
  const W = 640, H = 120, xs = v.map((x) => x.v), lo = Math.min(...xs, it.lcl ?? Infinity), hi = Math.max(...xs, it.ucl ?? -Infinity), r = hi - lo || 1;
  const y = (n: number) => H - 8 - ((n - lo) / r) * (H - 16), x = (i: number) => 10 + (i / (v.length - 1)) * (W - 20);
  const out = new Set<number>(it.out ?? []);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full max-w-[680px]" role="img" aria-label={`${it.item_name} 관리도`}>
      {it.ucl != null && <><line x1="0" x2={W} y1={y(it.ucl)} y2={y(it.ucl)} stroke="#e8954a" strokeDasharray="4 3" /><line x1="0" x2={W} y1={y(it.lcl)} y2={y(it.lcl)} stroke="#e8954a" strokeDasharray="4 3" /><line x1="0" x2={W} y1={y(it.mean)} y2={y(it.mean)} stroke="#8a97a4" /></>}
      <polyline fill="none" stroke="#0f9fbd" strokeWidth="1.5" points={xs.map((n, i) => `${x(i)},${y(n)}`).join(' ')} />
      {xs.map((n, i) => <circle key={i} cx={x(i)} cy={y(n)} r={out.has(i) ? 4 : 2} fill={out.has(i) ? '#c62a2f' : '#0f9fbd'} />)}
      <text x={W - 4} y={12} fontSize="10" textAnchor="end" fill="#56616c">{it.item_name} · 최근 {v.length}개 · ±3σ 밖 {out.size}개{out.size ? ' ▲ 다음 부품 바로 측정' : ''}</text>
    </svg>
  );
}
