'use client';
// SCR-15 교대 보고서 / SCR-16 일일 보고서 — 숫자는 프로그램(서버가 시뮬레이터 상태 기록으로 계산), 문장은 비서 자리(기본은 생성기·서버의 틀 문장 = 프로그램 초안. 시연 서버가 MOM_LLM_COMPOSE=1이면 끝난 교대의 문장을 비서가 다듬은 것으로 바꿔 보낸다).
// 저장·확정·확정 후 수정 = API-RPT-02~05 (해당 교대 SUP / MGR). 확정 후 수정은 사유 필수 → 관리자에게 수정 알림.
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { RANK_NAME, RANK_ORDER, userName } from './model';
import { api, hm, md, simIso, useFetch } from './live';
import { CAUSE_KO } from './data';
import { parseHandover } from './Briefing';
import { handoverCount, notableHead } from './reportLabels';
import { ConfirmBox } from './Safety';

const ST: Record<string, string> = { AI_DRAFT: 'AI비서 초안', EDITING: '수정 중', CONFIRMED: '확정' };
const sec = (head: string, body: React.ReactNode) => (<section className="border-t border-slate-200 py-3"><h3 className="mb-1 text-[14px] font-bold text-slate-500">{head}</h3>{body}</section>);

export function ShiftReportScreen() {
  const { key, shiftReports, back, user, role, go, wos, wrs, srs, history, toast, reloadReports, addNotice, openWo, openRecord, twin } = useApp();
  const sid = key ?? [...(shiftReports ?? [])].filter((r) => !twin || r.shift_id < twin.shift.shift_id).map((r) => r.shift_id).sort().pop() ?? '';
  const f = useFetch<Record<string, any>>(sid ? `reports/shift/${sid}` : null, 0, [sid]);
  const [edit, setEdit] = useState<{ n: string; h: string } | null>(null);
  const [reason, setReason] = useState('');
  const [confirm, setConfirm] = useState<'confirm' | null>(null);
  const r = f.data;
  if (!r) return <div className={PAGE}><div className={CARD}>{f.err ?? 'AI비서 초안을 만드는 중…'} <button onClick={back} className={BTN}>닫기</button></div></div>;
  const mineShift = role === 'SUP' && (r.shift_type ? user.shift === r.shift_type : true);
  const confirmed = r.status === 'CONFIRMED';
  const ver = Number(r.current_version ?? 0);
  const stops: Record<string, any>[] = r.stops ?? [];
  const inShift = (iso?: string) => !!iso && r.start_at && iso >= r.start_at && iso < r.end_at;
  const myWos = wos.filter((w) => inShift(w.created)), pastWos = (history?.work_orders ?? []).filter((w) => inShift(w.created_at));
  const pastRecs = (history?.work_records ?? []).filter((x) => inShift(x.start_at));
  const hand = parseHandover(edit?.h ?? r.handover_text ?? '');
  const send = async (action: 'save' | 'confirm' | 'revise') => {
    try {
      await api(`reports/shift/${sid}/${action}`, { role, user_id: user.id, version: ver, notable_text: edit?.n ?? r.notable_text, handover_text: edit?.h ?? r.handover_text, reason: action === 'revise' ? reason : undefined });
      if (action === 'revise') addNotice({ id: `DOC_REVISED:SHIFT:${sid}:${ver + 1}`, rule: 'DOC_REVISED', ruleName: '문서 수정', level: '참고', rank: '4', at: simIso(), ts: Date.now(), text: `교대 보고서 ${sid} 확정 후 수정 — ${reason} (${user.name})`, roles: ['MGR'], delivery: 'BUBBLE', handled: false, open: { screen: 'shift', key: sid } });
      toast(action === 'confirm' ? `교대 보고서 ${sid} 확정 — 잠김${sid.endsWith('-N') ? ' · 일일 보고서 초안이 생깁니다' : ''}` : '저장됨');
      setEdit(null); setReason(''); f.reload(); reloadReports();
    } catch (e) { toast((e as Error).message); }
  };

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">교대 보고서 — {md(sid)} {sid.endsWith('-D') ? '주간' : '야간'} ({sid})</h2>
          <div className="flex gap-2">
            <select value={sid} onChange={(e) => go('shift', e.target.value)} className="h-11 rounded-md border border-slate-300 px-2 text-[14px]">{[...(shiftReports ?? [])].reverse().map((x) => <option key={x.shift_id}>{x.shift_id}</option>)}</select>
            <button onClick={() => go('revs', `SHIFT:${sid}`)} className={BTN}>수정 이력</button><button onClick={() => window.print()} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[14px]">
          {['AI_DRAFT', 'EDITING', 'CONFIRMED'].map((s) => <span key={s} className={`rounded-full px-3 py-1 ${r.status === s ? 'bg-[#1c2530] font-bold text-white' : 'border border-slate-300 text-slate-500'}`}>{ST[s]}{r.status === s ? ` v${ver}` : ''}</span>)}
          {confirmed ? <span>🔒 확정 {userName(r.confirmed_by)} {r.confirmed_at ? `${md(r.confirmed_at)} ${hm(r.confirmed_at)}` : ''}</span> : <span className="font-semibold text-[#4b5a69]">ⓘ 확정 전 — 이 교대 값은 다른 화면에서 잠정{r.partial ? ' (교대 진행 중)' : ''}</span>}
        </div>
        {sec('[2] 생산', <div className="text-[15px]">총 목표 {r.target_qty} · 실적 {r.actual_qty} ({Number(r.actual_qty) - Number(r.target_qty) >= 0 ? '+' : ''}{Number(r.actual_qty) - Number(r.target_qty)}) · 불량 {r.defect_qty} · 가동률 VF2-01 {r.availability?.['VF2-01'] ?? '—'}% / VF2-02 {r.availability?.['VF2-02'] ?? '—'}%</div>)}
        {sec('[3] 로트', (r.lots ?? []).length ? <div className="flex flex-wrap gap-1">{(r.lots as string[]).map((l) => <button key={l} onClick={() => go('lots', l)} className="h-9 rounded border border-slate-300 px-2 text-[13px]">{l}</button>)}</div> : '없음')}
        {sec(`[4] 필수 정지 — 전체 ${stops.length}건 (고장 그룹 F01~F06 · 5분 이상 · 정지 시간 긴 순)`, stops.length ? (
          <table className="w-full text-left text-[14px]"><thead className="text-slate-500"><tr><th>설비</th><th>원인</th><th>시간</th><th>손실 수량</th><th>문서</th></tr></thead>
            <tbody>{stops.map((s, i) => { const w = myWos.find((x) => x.alertId === `a-${s.alarm_event_id}`) ?? null; const pw = pastWos.find((x) => x.alarm_event_id === String(s.alarm_event_id)); return (
              <tr key={i} className="border-t border-slate-100"><td>{s.equipment_id}</td><td>{s.reason_code} {s.reason_name}</td><td>{s.minutes}분 ({hm(s.start_at)}~{hm(s.end_at)})</td><td>약 {s.loss_qty}개 (추정)</td>
                <td>{w ? <button onClick={() => openWo(w.no)} className="underline">{w.no}</button> : pw ? pw.wo_no : '—'}</td></tr>); })}</tbody></table>
        ) : '없음')}
        {sec('[5] 병목', (r.bottleneck ?? []).length ? <ul>{(r.bottleneck as Record<string, string>[]).map((b) => <li key={b.at}>{hm(b.at)} {b.process_code} {CAUSE_KO[b.cause_code] ?? b.cause_code}</li>)}</ul> : '기준 병목(OP-30) 그대로')}
        {sec('[6] 정비', <ul className="text-[14px]">
          {myWos.map((w) => <li key={w.no}><button onClick={() => openWo(w.no)} className="underline">{w.no}</button> → {wrs.find((x) => x.woNo === w.no) ? <button onClick={() => openRecord(w.no)} className="underline">{wrs.find((x) => x.woNo === w.no)!.no}</button> : '작업기록서 없음'} · 알람 {w.code} · {wrs.find((x) => x.woNo === w.no)?.action || '—'}</li>)}
          {srs.filter((s) => s.state === 'confirmed').map((s) => <li key={s.no}>간이 {s.no} {s.code} · {s.action}</li>)}
          {pastWos.map((w) => <li key={w.wo_no}>{w.wo_no} {w.title}</li>)}
          {pastRecs.map((x) => <li key={x.record_no}>{x.record_no} ({x.record_type === 'QUICK' ? '간이' : '정식'}) {x.equipment_id} · {x.action}</li>)}
          {myWos.length + pastWos.length + pastRecs.length === 0 && <li>없음</li>}
        </ul>)}
        {sec(notableHead(r), edit ? <textarea value={edit.n} onChange={(e) => setEdit({ ...edit, n: e.target.value })} rows={5} className="w-full rounded-md border border-slate-300 p-2 text-[15px]" /> : <p className="text-[15px]">{r.notable_text}</p>)}
        {sec(`[8] 인계 사항 — 전체 ${handoverCount(hand)}건 (2.5 보고 순위 순, 잠금·표지 맨 위)`, edit ? <textarea value={edit.h} onChange={(e) => setEdit({ ...edit, h: e.target.value })} rows={4} className="w-full rounded-md border border-slate-300 p-2 text-[14px]" /> : (
          <ul className="text-[14px]">{RANK_ORDER.map((k) => { const g = hand.find((x) => x.rank === k); return <li key={k}><b>{k} {RANK_NAME[k]}</b> {g && g.items.length ? g.items.join('; ') : k === '0' ? (g?.name ?? '잠금·표지 중인 설비 없음') : '-'}</li>; })}</ul>
        ))}
        {(confirmed && edit) && <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="확정 후 수정 사유 (필수)" className="mb-2 h-11 w-full rounded-md border border-[#e8954a] px-2" />}
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-300 pt-3">
          {mineShift && !edit && <button onClick={() => setEdit({ n: r.notable_text, h: r.handover_text })} className={BTN}>{confirmed ? '확정 후 수정' : '고치기'}</button>}
          {mineShift && edit && !confirmed && <button onClick={() => send('save')} className={BTN}>저장</button>}
          {mineShift && !confirmed && <button onClick={() => setConfirm('confirm')} className={DARK}>확정</button>}
          {mineShift && edit && confirmed && <button disabled={!reason.trim()} onClick={() => send('revise')} className={DARK}>수정 저장 (새 버전)</button>}
          {!mineShift && <span className="text-[14px] text-slate-500">{role === 'SUP' ? '해당 교대 반장만 고치고 확정합니다.' : '보기 전용입니다.'}</span>}
        </div>
      </div>
      {confirm && <ConfirmBox title="교대 보고서를 확정할까요?" okLabel="확정" body="확정하면 잠깁니다. 고치려면 사유가 필요합니다." onOk={() => { setConfirm(null); void send('confirm'); }} onCancel={() => setConfirm(null)} />}
    </div>
  );
}

export function DailyReportScreen() {
  const { key, dailyReports, shiftReports, back, user, role, go, toast, reloadReports, inv, wos, wrs, history, twin } = useApp();
  const pending = (dailyReports ?? []).filter((r) => r.status !== 'CONFIRMED').map((r) => r.work_date).sort();
  const d = key ?? pending[0] ?? (dailyReports ?? []).map((r) => r.work_date).sort().pop() ?? '';
  const f = useFetch<Record<string, any>>(d ? `reports/daily/${d}` : null, 0, [d]);
  const lots = useFetch<{ lots: Record<string, any>[] }>(d ? 'lots' : null, 0, [d]);
  const [memo, setMemo] = useState('');
  const [confirm, setConfirm] = useState(false);
  const r = f.data;
  if (role === 'OPR') return <div className={PAGE}><div className={CARD}>일일 보고서는 작업자 메뉴에 없습니다. <button onClick={back} className={BTN}>닫기</button></div></div>;
  if (!r) return <div className={PAGE}><div className={CARD}>{f.err ?? '불러오는 중…'} <button onClick={back} className={BTN}>닫기</button></div></div>;
  const day = (shiftReports ?? []).find((x) => x.shift_id === `${d}-D`), night = (shiftReports ?? []).find((x) => x.shift_id === `${d}-N`);
  const bothConf = day?.status === 'CONFIRMED' && night?.status === 'CONFIRMED';
  const stops: Record<string, any>[] = r.stops ?? [];
  const al: Record<string, any>[] = r.alarms ?? [];
  const cnt = (s: string) => al.filter((x) => x.severity === s).length;
  const issues = String(r.issues_summary ?? '');
  const head = issues.split(':')[0], list = issues.includes(': ') ? issues.slice(issues.indexOf(': ') + 2).split(' / ') : [];
  const inDay = (iso?: string) => !!iso && r.range && iso >= r.range[0] && iso < r.range[1];
  const lotDay = (lots.data?.lots ?? []).filter((l) => inDay(l.judged_at) || l.input_shift_id?.startsWith(d));
  const txns = (inv?.past_txns ?? []).filter((t) => inDay(t.txn_at));
  const prev = (dailyReports ?? []).filter((x) => x.work_date < d && x.status === 'CONFIRMED').map((x) => x.work_date).sort().pop();
  const fg = { start: 0, in: 0, ship: 0, adj: 0 };
  txns.filter((t) => t.item_no === 'FG-BRK-A100').forEach((t) => { const q = Number(t.qty_change); if (t.txn_type === 'FG_IN') fg.in += q; else if (t.txn_type === 'SHIP') fg.ship -= q; else fg.adj += q; });

  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[19px] font-bold">일일 보고서 — {md(d)} <span className="text-[13px] font-normal text-slate-500">(생산일 {md(d)} 08:00 ~ 다음 날 05:00{r.created_by ? ` · 생성 ${r.created_by}` : ''})</span></h2>
          <div className="flex gap-2">
            {pending.length > 1 && <span className="self-center text-[13px] font-semibold text-[#9a6200]">확정 대기 {pending.length}개</span>}
            <select value={d} onChange={(e) => go('daily', e.target.value)} className="h-11 rounded-md border border-slate-300 px-2 text-[14px]">{[...(dailyReports ?? [])].reverse().map((x) => <option key={x.work_date}>{x.work_date}</option>)}</select>
            <button onClick={() => go('revs', `DAILY:${d}`)} className={BTN}>수정 이력</button><button onClick={() => window.print()} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[14px]">
          <span className={`rounded-full px-3 py-1 ${r.status === 'CONFIRMED' ? 'border border-slate-300' : 'bg-[#1c2530] font-bold text-white'}`}>{ST[r.status] ?? r.status} v{r.current_version}</span>
          재료: <button onClick={() => go('shift', `${d}-D`)} className="underline">주간 {day?.status === 'CONFIRMED' ? '🔒확정' : 'ⓘ미확정'}</button> · <button onClick={() => go('shift', `${d}-N`)} className="underline">야간 {night?.status === 'CONFIRMED' ? '🔒확정' : 'ⓘ미확정 (잠정)'}</button>
          {!bothConf && prev && <button onClick={() => go('daily', prev)} className={BTN}>지난 확정본 보기 ({md(prev)})</button>}
          {r.status === 'CONFIRMED' && <span>🔒 확정 {userName(r.confirmed_by)} {r.confirmed_at ? `${md(r.confirmed_at)} ${hm(r.confirmed_at)}` : ''}</span>}
        </div>
        {sec('[2] 하루 생산', <div className="text-[15px]">목표 180 · 실적 {r.actual_qty} (부족 −{Math.max(0, 180 - Number(r.actual_qty))}) · 불량 {r.defect_qty} · OEE(라인) {r.oee_pct}% · 주간 {day?.actual_qty ?? '—'} / 야간 {night?.actual_qty ?? '—'}{night?.status !== 'CONFIRMED' ? ' (잠정)' : ''}</div>)}
        {sec(`[3] 손실 (추정) — 고장 손실 약 ${r.failure_loss_qty}개 · 속도 손실 약 ${r.speed_loss_qty}개 · 손실 전체 ${stops.length}건 (큰 순서)`, stops.length ? (
          <ol className="list-decimal pl-5 text-[14px]">{[...stops].sort((a, b) => b.loss_qty - a.loss_qty).map((s, i) => <li key={i}>{s.equipment_id} {s.reason_name} {s.minutes}분 · 약 {s.loss_qty}개 <button onClick={() => go('replay', s.start_at)} className="ml-1 underline">다시 보기</button></li>)}</ol>
        ) : '없음')}
        {sec('[4] 알람', <div className="text-[14px]">정지 {cnt('STOP')} · 주의 {cnt('WARN')} · 조작 안내 {cnt('GUIDE')} (합 {al.length}){(() => { const rep = Object.entries(al.reduce((m: Record<string, number>, x) => { const k = `${x.equipment_id} ${x.alarm_code}`; m[k] = (m[k] ?? 0) + 1; return m; }, {})).filter(([, n]) => n >= 3); return rep.length ? ` · 반복 알람 ${rep.map(([k, n]) => `${k} ×${n}`).join(', ')}` : ''; })()}</div>)}
        {sec('[5] 정비', <div className="text-[14px]">{[...wos.filter((w) => inDay(w.created)).map((w) => w.no), ...wrs.filter((x) => x.confirmedAt && inDay(x.confirmedAt)).map((x) => x.no), ...(history?.work_orders ?? []).filter((w) => inDay(w.created_at)).map((w) => w.wo_no), ...(history?.work_records ?? []).filter((x) => inDay(x.start_at)).map((x) => x.record_no)].join(' · ') || '없음'} · MTTR (30일) {twin ? Object.entries(twin.kpi.mttr_mtbf).filter(([, v]) => v.mttr_min != null).map(([k, v]) => `${k} ${v.mttr_min}분`).join(' · ') || '—' : '—'}</div>)}
        {sec('[6] 로트', <div className="text-[14px]">완료 {lotDay.filter((l) => l.judged_at).length} · 합격(출하 가능) {lotDay.filter((l) => l.status === 'PASSED' || l.status === 'RELEASED').length} · 판정 대기 {lotDay.filter((l) => !l.judged_at).length} · 보류 {lotDay.filter((l) => l.on_hold).map((l) => l.lot_no).join(', ') || '없음'}</div>)}
        {sec('[7] 재고', <div className="text-[14px]">오늘 사용 {Object.entries(txns.filter((t) => t.txn_type === 'USE').reduce((m: Record<string, number>, t) => { m[t.item_no] = (m[t.item_no] ?? 0) + Number(t.qty_change); return m; }, {})).map(([k, v]) => `${inv?.items.find((i) => i.item_no === k)?.item_name ?? k} ${v}`).join(' · ') || '없음'} · 부족: {inv?.items.filter((i) => i.low).map((i) => i.item_name).join(', ') || '없음'}<br />
          완제품 BRK-A100 입고(합격) {fg.in} · 출하 {fg.ship} · 조정 {fg.adj} · 보류 수량 {inv?.held_lot_qty ?? '—'} (재고에 안 넣음)</div>)}
        {sec(`[8] 오늘의 문제 — ${head}`, <ol className="text-[14px]">{list.map((t) => <li key={t}>{t}</li>)}</ol>)}
        {role === 'MGR' && r.status !== 'CONFIRMED' && <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="관리자 메모 (선택)" className="mb-2 h-11 w-full rounded-md border border-slate-300 px-2" />}
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-300 pt-3">
          {role === 'MGR' && r.status !== 'CONFIRMED' && <button disabled={!bothConf} onClick={() => setConfirm(true)} className={DARK}>확정{!bothConf ? ' — 교대 보고서 미확정 (비활성)' : ''}</button>}
          {role !== 'MGR' && <span className="text-[14px] text-slate-500">보기 전용 (확정은 관리자)</span>}
        </div>
      </div>
      {confirm && <ConfirmBox title="일일 보고서를 확정할까요?" okLabel="확정" body="확정하면 잠기고 일일 보고서 확정 요청 알림이 자동 처리됩니다."
        onOk={async () => { setConfirm(false); try { await api(`reports/daily/${d}/confirm`, { role, user_id: user.id, memo }); toast('일일 보고서 확정'); f.reload(); reloadReports(); } catch (e) { toast((e as Error).message); } }} onCancel={() => setConfirm(false)} />}
    </div>
  );
}
