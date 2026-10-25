'use client';
// SCR-15 교대 보고서 / SCR-16 일일 보고서 — 숫자는 프로그램(서버가 시뮬레이터 상태 기록으로 계산), 문장은 비서 자리(기본은 생성기·서버의 틀 문장 = 프로그램 초안. 시연 서버가 MOM_LLM_COMPOSE=1이면 끝난 교대의 문장을 비서가 다듬은 것으로 바꿔 보낸다).
// 저장·확정·확정 후 수정 = API-RPT-02~05 (해당 교대 SUP / MGR). 확정 후 수정은 사유 필수 → 관리자에게 수정 알림.
// 시안(2026-10-20): 숫자 칸 → 필수 정지/병목 → 로트·정비 → 특이 사항(다른 칸과 겹치는 문장은 숨김) → 인계 사항(순위 칩).
// 일일: 생산 숫자 → 오늘의 문제(문제 → 생산 피해 → 처리) → 알람 → 자세히(접음) → 관리자 메모.
import { LockIcon } from './ui';
import { useState, type ReactNode } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { CAUSE_KO, MACHINES } from './data';
import { RANK_NAME, RANK_ORDER, userName } from './model';
import { api, hm, md, simIso, useFetch } from './live';
import { parseHandover } from './Briefing';
import { NO_LOCKOUT, handoverCount } from './reportLabels';
import { ConfirmBox } from './Safety';
import { WO_STEPS } from './workflow';
import { Acts, Bar, Chip, DocHead, DocPage, Fold, InfoRow, Kpi, RankRow, ReportLine, ReportLines, RO, Sec, Steps, type Tone } from './DocKit';

const ST: Record<string, string> = { AI_DRAFT: 'AI비서 초안', EDITING: '수정 중', CONFIRMED: '확정' };
// 9월 기록의 영어 상태 → 한글
const EN_ST: Record<string, string> = { DONE: '완료', COMPLETED: '완료', IN_PROGRESS: '진행 중', OPEN: '대기', APPROVED: '승인', CANCELLED: '취소됨', CONFIRMED: '확정', CHECKED: '확인됨' };
const woLabel = (s: string) => WO_STEPS.find(([k]) => k === s)?.[1] ?? (s === 'cancelled' ? '취소됨' : s);
const stTone = (l: string): Tone => (/완료|처리|확정|확인/.test(l) ? 'ok' : /진행|승인/.test(l) ? 'acc' : 'mute');
const stChip = (l: string) => <Chip tone={stTone(l)}>{stTone(l) === 'ok' ? '✓ ' : stTone(l) === 'acc' ? '● ' : ''}{l}</Chip>;
const docBtn = (label: string, onClick?: () => void) => (onClick ? <button key={label} onClick={onClick} className="h-9 rounded-ctl border border-line bg-white px-3 font-mono text-small font-semibold hover:bg-tile">{label}</button> : <Chip key={label} mono>{label}</Chip>);
// 한 줄: 상태 → 설비·알람 → 내용 → 문서
const MRow = ({ st, eq, tx, docs }: { st: ReactNode; eq: string; tx: ReactNode; docs: ReactNode }) => (
  <div className="grid grid-cols-1 items-center gap-2 border-t border-dashed border-line py-2 text-body first:border-t-0 sm:grid-cols-[96px_minmax(0,1fr)_auto]">
    <span>{st}</span><span className="flex min-w-0 items-center gap-2"><Chip mono>{eq}</Chip><span className="line-clamp-2 min-w-0" title={typeof tx === 'string' ? tx : undefined}>{tx}</span></span><span className="flex flex-wrap gap-1.5">{docs}</span>
  </div>
);
const countChips = (labels: string[]) => Object.entries(labels.reduce((m: Record<string, number>, l) => { m[l] = (m[l] ?? 0) + 1; return m; }, {})).map(([l, n]) => <Chip key={l} tone={stTone(l)}>{l} {n}</Chip>);

// 특이 사항 문장 나누기: 다른 칸(생산·필수 정지·병목·불량·로트)과 겹치는 프로그램 문장은 숨기고, 알람 수는 칩, 나머지(반장 메모)는 점 목록
function splitNotable(t: string) {
  const ss = String(t ?? '').split(/(?<=[.。])\s+/).map((s) => s.replace(/[.。]$/, '').trim()).filter(Boolean);
  const dup = /^(실적 \d|필수 정지 \d|병목:|불량|로트 보류:)/;
  const alarm = /^(주의|정지 등급|조작 안내)[^,]*알람 \d+건/;
  const order = (c: string) => (/^정지/.test(c) ? 0 : /^주의/.test(c) ? 1 : 2);
  const chips = ss.filter((s) => alarm.test(s)).flatMap((s) => s.split(/,\s*(?=(?:주의|정지 등급|조작 안내)[^,]*알람)/)).sort((a, b) => order(a) - order(b));
  return { chips, memo: ss.filter((s) => !dup.test(s) && !alarm.test(s)) };
}

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
    // 바뀐 칸이 있을 때만 새 버전 (2026-10-20)
    if (action !== 'confirm' && edit && edit.n === r.notable_text && edit.h === r.handover_text) { toast('바뀐 내용 없음'); return; }
    try {
      await api(`reports/shift/${sid}/${action}`, { role, user_id: user.id, version: ver, notable_text: edit?.n ?? r.notable_text, handover_text: edit?.h ?? r.handover_text, reason: action === 'revise' ? reason : undefined });
      if (action === 'revise') addNotice({ id: `DOC_REVISED:SHIFT:${sid}:${ver + 1}`, rule: 'DOC_REVISED', ruleName: '문서 수정', level: '참고', rank: '4', at: simIso(), ts: Date.now(), text: `교대 보고서 ${sid} 확정 후 수정 — ${reason} (${user.name})`, roles: ['MGR'], delivery: 'BUBBLE', handled: false, open: { screen: 'shift', key: sid } });
      toast(action === 'confirm' ? `교대 보고서 ${sid} 확정 — 잠김${sid.endsWith('-N') ? ' · 일일 보고서 초안이 생깁니다' : ''}` : '저장됨');
      setEdit(null); setReason(''); f.reload(); reloadReports();
    } catch (e) { toast((e as Error).message); }
  };
  const target = Number(r.target_qty), actual = Number(r.actual_qty), pct = target ? Math.round((actual / target) * 1000) / 10 : 0;
  const stopMin = stops.reduce((s, x) => s + Number(x.minutes ?? 0), 0);
  const bn: Record<string, string>[] = r.bottleneck ?? [];

  // 정비 줄: 오늘 화면에서 만든 작업지시서 · 확정된 간이 작업기록 · 9월 기록
  const rows: { label: string; node: ReactNode }[] = [];
  myWos.forEach((w) => { const wr = wrs.find((x) => x.woNo === w.no); const l = woLabel(w.state); rows.push({ label: l, node: <MRow key={w.no} st={stChip(l)} eq={`${MACHINES[w.machine].name} · ${w.code}`} tx={wr?.action || w.title} docs={<>{docBtn(w.no, () => openWo(w.no))}{wr && docBtn(wr.no, () => openRecord(w.no))}</>} /> }); });
  srs.filter((s) => s.state === 'confirmed').forEach((s) => rows.push({ label: '처리', node: <MRow key={s.no} st={stChip('처리')} eq={`${MACHINES[s.machine].name} · ${s.code}`} tx={s.action} docs={docBtn(s.no, () => go('sr', s.no))} /> }));
  pastWos.forEach((w) => { const rec = pastRecs.find((x) => x.wo_no === w.wo_no); const l = EN_ST[w.status] ?? w.status; const code = history?.alarms.find((x) => x.alarm_event_id === w.alarm_event_id)?.alarm_code; rows.push({ label: l, node: <MRow key={w.wo_no} st={stChip(l)} eq={`${w.equipment_id}${code ? ` · ${code}` : ''}`} tx={rec ? <>{rec.action}{rec.repair_min ? <> · <b className="font-mono">{rec.repair_min}</b>분</> : null}</> : w.title} docs={<>{docBtn(w.wo_no)}{rec && docBtn(rec.record_no)}</>} /> }); });
  pastRecs.filter((x) => !pastWos.some((w) => w.wo_no === x.wo_no)).forEach((x) => rows.push({ label: '처리', node: <MRow key={x.record_no} st={stChip('처리')} eq={x.equipment_id} tx={x.action} docs={docBtn(`${x.record_type === 'QUICK' ? '간이 ' : ''}${x.record_no}`)} /> }));

  const nt = splitNotable(r.notable_text);
  // 인계 사항: 순위 6개를 항상 보이고 비면 "없음" (안전의 "잠금·표지 중인 설비 없음"도 "없음"으로, 2026-10-20)
  const RANK_TONE: Record<string, Tone> = { '0': 'crit', '0-1': 'warn', '1': 'solid-crit', '2': 'warn', '3': 'mute', '4': 'mute' };
  const handOf = (k: string) => (hand.find((g) => g.rank === k)?.items ?? []).filter((x) => !x.startsWith(NO_LOCKOUT));

  return (
    <DocPage width={1100}>
      <DocHead title="교대 보고서" sub={`${md(sid)} ${sid.endsWith('-D') ? '주간' : '야간'}${r.start_at ? ` · ${hm(r.start_at)}~${hm(r.end_at)}` : ''}`}
        right={<Steps list={['AI_DRAFT', 'EDITING', 'CONFIRMED'].map((s) => `${ST[s]}${r.status === s ? ` v${ver}` : ''}`)} cur={['AI_DRAFT', 'EDITING', 'CONFIRMED'].indexOf(r.status)} />} />
      <InfoRow right={<>
        <select aria-label="교대" value={sid} onChange={(e) => go('shift', e.target.value)} className="h-11 rounded-ctl border border-line bg-white px-2 text-body">{[...(shiftReports ?? [])].reverse().map((x) => <option key={x.shift_id}>{x.shift_id}</option>)}</select>
        <button onClick={() => go('revs', `SHIFT:${sid}`)} className={BTN}>수정 이력</button><button onClick={() => window.print()} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button>
      </>}>
        {confirmed ? <Chip tone="ok"><LockIcon /> 확정 {userName(r.confirmed_by)} {r.confirmed_at ? `${md(r.confirmed_at)} ${hm(r.confirmed_at)}` : ''}</Chip> : <span className="font-semibold text-ink-2">ⓘ 확정 전</span>}
        {r.partial && <Chip tone="acc">교대 진행 중</Chip>}
      </InfoRow>

      <Sec title="생산" right={<Chip tone={pct < 90 ? 'warn' : 'ok'}>목표 대비 {pct}%</Chip>}>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
            <Kpi label="실적" value={actual} unit="개" tone="main" />
            <Kpi label="총 목표" value={target} unit="개" />
            <Kpi label={actual >= target ? '초과' : '남은 수량'} value={Math.abs(target - actual)} unit="개" tone={actual >= target ? 'ok' : 'bad'} />
            <Kpi label="불량" value={r.defect_qty} unit="개" />
          </div>
          <div><Bar pct={pct} outline /><div className="mt-1 text-small text-ink-2">목표 대비 <b className="font-mono text-ink">{pct}%</b></div></div>
          <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 text-small text-ink-2"><b className="text-ink">가동률</b>
            {['VF2-01', 'VF2-02'].map((m) => <span key={m}>{m} <b className="ml-1 font-mono text-title font-semibold text-ink">{r.availability?.[m] ?? '—'}</b>%</span>)}</div>
        </div>
      </Sec>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Sec title="필수 정지" right={<Chip tone={stops.length ? 'crit' : 'ok'}>{stops.length}건 · {stopMin}분</Chip>}>
          {stops.length ? stops.map((s, i) => { const w = myWos.find((x) => x.alertId === `a-${s.alarm_event_id}`) ?? null; const pw = pastWos.find((x) => x.alarm_event_id && x.alarm_event_id === String(s.alarm_event_id)) ?? pastWos.find((x) => x.equipment_id === s.equipment_id && x.created_at >= s.start_at && x.created_at <= s.end_at); return (
            <div key={i} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-t border-dashed border-line py-2 text-body first:border-t-0">
              <span className="font-mono text-band font-semibold text-crit">{s.minutes}<small className="ml-0.5 font-sans text-small font-normal text-ink-2">분</small></span>
              <span><b>{s.equipment_id}</b> · {s.reason_code} {s.reason_name}<div className="text-small text-ink-2">{hm(s.start_at)}~{hm(s.end_at)} · 손실 약 {s.loss_qty}개 (추정)</div></span>
              {w ? docBtn(w.no, () => openWo(w.no)) : pw ? docBtn(pw.wo_no) : <span className="text-ink-3">—</span>}
            </div>); }) : <span className="text-body text-ink-2">없음</span>}
        </Sec>
        <Sec title="병목" right={bn.length ? <Chip tone="warn">{bn.length}번 바뀜</Chip> : undefined}>
          {bn.length ? bn.map((b) => <div key={b.at} className="grid grid-cols-[52px_minmax(0,1fr)] gap-3 border-t border-dashed border-line py-2 text-body first:border-t-0"><span className="font-mono">{hm(b.at)}</span><span><b>{b.process_code}</b> · {CAUSE_KO[b.cause_code] ?? b.cause_code}</span></div>)
            : <span className="text-body text-ink-2">기준 병목(OP-30) 그대로</span>}
        </Sec>
      </div>
      <Sec title="로트" right={<Chip>{(r.lots ?? []).length}개</Chip>}>
        {(r.lots ?? []).length ? <div className="flex flex-wrap gap-1.5">{(r.lots as string[]).map((l) => <button key={l} onClick={() => go('lots', l)}><Chip mono>{l}</Chip></button>)}</div> : <span className="text-body text-ink-2">없음</span>}
      </Sec>
      <Sec title="정비" right={rows.length ? countChips(rows.map((x) => x.label)) : undefined}>
        {rows.length ? rows.map((x) => x.node) : <span className="text-body text-ink-2">없음</span>}
      </Sec>
      {/* 비서가 다듬은 글이고 아직 초안이면 "AI비서 초안" (reportLabels notableHead와 같은 조건, 팀원 2026-10-19) */}
      <Sec title="특이 사항" right={r.notable_source === 'ASSISTANT' && r.status === 'AI_DRAFT' ? <Chip tone="acc">AI비서 초안</Chip> : undefined}>
        {edit ? <textarea aria-label="특이 사항" value={edit.n} onChange={(e) => setEdit({ ...edit, n: e.target.value })} rows={5} className="w-full rounded-ctl border border-line p-2 text-card" /> : (
          <div className="flex flex-col gap-2">
            {nt.chips.length > 0 && <div className="flex flex-wrap gap-1.5">{nt.chips.map((c) => <Chip key={c} tone={/^정지/.test(c) ? 'crit' : /^주의/.test(c) ? 'warn' : 'mute'}>{/^정지/.test(c) ? '⚠ ' : /^주의/.test(c) ? '▲ ' : ''}{c}</Chip>)}</div>}
            {nt.memo.length > 0 ? <ul className="list-disc pl-5 text-card">{nt.memo.map((m) => <li key={m}>{m}</li>)}</ul> : nt.chips.length === 0 && <span className="text-body text-ink-2">없음</span>}
          </div>
        )}
      </Sec>
      <Sec title="인계 사항" right={<Chip>전체 {handoverCount(hand)}건</Chip>}>
        {edit ? <textarea aria-label="인계 사항" value={edit.h} onChange={(e) => setEdit({ ...edit, h: e.target.value })} rows={4} className="w-full rounded-ctl border border-line p-2 text-body" /> : (
          <div>{RANK_ORDER.map((k) => { const xs = handOf(k); return <RankRow key={k} left={<Chip tone={RANK_TONE[k]}>{RANK_NAME[k]}</Chip>}>{xs.length ? <ReportLines items={xs} /> : <span className="text-body text-ink-2">없음</span>}</RankRow>; })}
          </div>
        )}
      </Sec>
      {(confirmed && edit) && <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="확정 후 수정 사유 (필수)" className="h-11 w-full rounded-ctl border border-[#e8954a] bg-white px-3" />}
      <Acts>
        {mineShift && !edit && <button onClick={() => setEdit({ n: r.notable_text, h: r.handover_text })} className={BTN}>{confirmed ? '확정 후 수정' : '고치기'}</button>}
        {mineShift && edit && <button onClick={() => setEdit(null)} className={BTN}>그만 고치기</button>}
        {mineShift && edit && !confirmed && <button onClick={() => send('save')} className={BTN}>저장</button>}
        {mineShift && !confirmed && <button onClick={() => setConfirm('confirm')} className={DARK}>확정</button>}
        {mineShift && edit && confirmed && <button disabled={!reason.trim()} onClick={() => send('revise')} className={DARK}>수정 저장 (새 버전)</button>}
        {!mineShift && RO}
      </Acts>
      {confirm && <ConfirmBox title="교대 보고서를 확정할까요?" okLabel="확정" body="확정하면 잠깁니다. 고치려면 사유가 필요합니다." onOk={() => { setConfirm(null); void send('confirm'); }} onCancel={() => setConfirm(null)} />}
    </DocPage>
  );
}

// 오늘의 문제 글: "전체 14건 (…): 1) [긴급] … / 2) [생산] … 관리자 메모: …"
function splitIssues(t: string) {
  const s = String(t ?? '');
  const mi = s.indexOf('관리자 메모:');
  const body = (mi >= 0 ? s.slice(0, mi) : s).trim(), memo = mi >= 0 ? s.slice(mi + '관리자 메모:'.length).trim() : '';
  const list = body.includes(': ') ? body.slice(body.indexOf(': ') + 2).split(' / ') : [];
  const items = list.map((x) => { const m = x.trim().match(/^\d+\)\s*\[([^\]]+)\]\s*(.*)$/); return m ? { rank: m[1], text: m[2].trim() } : { rank: '', text: x.trim() }; });
  return { items, memo };
}
// 생산 줄 읽기 쉽게: "2026-09-14-D 실적 45개 — 목표 90개의 90% 아래", "15:28 병목 OP-50 — 원인 ③ 검사 강화"
function prodText(x: string): ReactNode {
  let m = x.match(/^\d{4}-\d{2}-\d{2}-(D|N) 실적 (\d+)개 — 목표 (\d+)개의 (.*)$/);
  if (m) return <>{m[1] === 'D' ? '주간' : '야간'} 실적 <b className="font-mono">{m[2]}</b> / {m[3]} · {m[4]}</>;
  m = x.match(/^(\d\d:\d\d) 병목 (\S+) — (.*)$/);
  if (m) return <>병목 <b>{m[2]}</b> · {m[3]} <span className="text-small text-ink-2">{m[1]}~</span></>;
  return <ReportLine text={x} />;
}

export function DailyReportScreen() {
  const { key, dailyReports, shiftReports, back, user, role, go, toast, reloadReports, inv, wos, wrs, history, twin, openWo, openRecord } = useApp();
  const pending = (dailyReports ?? []).filter((r) => r.status !== 'CONFIRMED').map((r) => r.work_date).sort();
  const d = key ?? pending[0] ?? (dailyReports ?? []).map((r) => r.work_date).sort().pop() ?? '';
  const f = useFetch<Record<string, any>>(d ? `reports/daily/${d}` : null, 0, [d]);
  const lots = useFetch<{ lots: Record<string, any>[] }>(d ? 'lots' : null, 0, [d]);
  const [memo, setMemo] = useState('');
  const [confirm, setConfirm] = useState(false);
  const r = f.data;
  if (role === 'OPR') return <div className={PAGE}><div className={CARD}><LockIcon /> 이 계정은 볼 수 없는 문서입니다 <button onClick={back} className={BTN}>닫기</button></div></div>;
  if (!r) return <div className={PAGE}><div className={CARD}>{f.err ?? '불러오는 중…'} <button onClick={back} className={BTN}>닫기</button></div></div>;
  const day = (shiftReports ?? []).find((x) => x.shift_id === `${d}-D`), night = (shiftReports ?? []).find((x) => x.shift_id === `${d}-N`);
  const bothConf = day?.status === 'CONFIRMED' && night?.status === 'CONFIRMED';
  const confirmed = r.status === 'CONFIRMED';
  const stops: Record<string, any>[] = r.stops ?? [];
  const al: Record<string, any>[] = r.alarms ?? [];
  const cnt = (s: string) => al.filter((x) => x.severity === s).length;
  const { items, memo: textMemo } = splitIssues(r.issues_summary);
  const savedMemo = String(r.memo ?? '').trim() || textMemo; // DB에서 읽으면 메모가 따로 칸(memo)에 있다 (2026-10-23)
  const inDay = (iso?: string) => !!iso && r.range && iso >= r.range[0] && iso < r.range[1];
  const lotDay = (lots.data?.lots ?? []).filter((l) => inDay(l.judged_at) || l.input_shift_id?.startsWith(d));
  const txns = (inv?.past_txns ?? []).filter((t) => inDay(t.txn_at));
  const prev = (dailyReports ?? []).filter((x) => x.work_date < d && x.status === 'CONFIRMED').map((x) => x.work_date).sort().pop();
  const fg = { start: 0, in: 0, ship: 0, adj: 0 };
  txns.filter((t) => t.item_no === 'FG-BRK-A100').forEach((t) => { const q = Number(t.qty_change); if (t.txn_type === 'FG_IN') fg.in += q; else if (t.txn_type === 'SHIP' || t.txn_type === 'SHIP_OUT') fg.ship -= q; else fg.adj += q; }); // SHIP_OUT = DB 거래 이름 (9월 기록, 2026-10-23)
  // 목표는 서버가 보내는 값(설정에서 바꿀 수 있음), 없을 때만 180. 초과/부족은 칸 이름과 색으로 보이고 숫자에는 기호를 붙이지 않는다 (2026-10-20)
  const target = Number(r.target_qty ?? 180) || 180, actual = Number(r.actual_qty ?? 0) || 0, pct = Math.round((actual / target) * 1000) / 10;
  const rep = Object.entries(al.reduce((m: Record<string, number>, x) => { const k = `${x.equipment_id} ${x.alarm_code}`; m[k] = (m[k] ?? 0) + 1; return m; }, {})).filter(([, n]) => n >= 3);

  // 정지 ↔ 작업지시서: 알람 번호로 먼저, 없으면 같은 설비에서 정지 중에 만든 작업지시서 (반복 알람 2단계처럼 알람 번호가 없는 것)
  const fixOf = (s: Record<string, any>): ReactNode => {
    const w = wos.find((x) => x.alertId === `a-${s.alarm_event_id}`);
    if (w) { const wr = wrs.find((x) => x.woNo === w.no); return <>{stChip(woLabel(w.state))}{docBtn(w.no, () => openWo(w.no))}{wr && docBtn(wr.no, () => openRecord(w.no))}</>; }
    const pw = (history?.work_orders ?? []).find((x) => x.alarm_event_id && x.alarm_event_id === String(s.alarm_event_id))
      ?? (history?.work_orders ?? []).find((x) => x.equipment_id === s.equipment_id && x.created_at >= s.start_at && x.created_at <= s.end_at);
    if (!pw) return <span className="text-small text-ink-2">작업지시서 없음</span>;
    const rec = (history?.work_records ?? []).find((x) => x.wo_no === pw.wo_no);
    return <>{stChip(EN_ST[pw.status] ?? pw.status)}{docBtn(pw.wo_no)}{rec && docBtn(rec.record_no)}</>;
  };
  // 순위 0 안전(잠금·표지 중인 설비)은 맨 위, 접지 않음 (FR-AST-COM-21 — 2026-10-20, 전에는 빠져 안 보였다)
  const safeItems = items.filter((x) => x.rank === '안전');
  const prodItems = items.filter((x) => x.rank === '생산');
  const urgItems = stops.length ? [] : items.filter((x) => x.rank === '긴급');
  const warnItems = items.filter((x) => x.rank === '주의'), refItems = items.filter((x) => x.rank === '참고');
  const probGrid = 'grid grid-cols-[76px_minmax(0,1fr)_76px] items-center gap-x-3 gap-y-1 border-t border-dashed border-line py-2.5 text-body first:border-t-0 md:grid-cols-[76px_minmax(0,1fr)_84px_minmax(0,1.1fr)_40px]';

  return (
    <DocPage width={1100}>
      <DocHead title="일일 보고서" sub={`${md(d)} · 생산일 08:00 ~ 다음 날 05:00`} right={<Steps list={['AI비서 초안', '확정']} cur={confirmed ? 1 : 0} />} />
      <InfoRow right={<>
        <select aria-label="날짜" value={d} onChange={(e) => go('daily', e.target.value)} className="h-11 rounded-ctl border border-line bg-white px-2 text-body">{[...(dailyReports ?? [])].reverse().map((x) => <option key={x.work_date}>{x.work_date}</option>)}</select>
        <button onClick={() => go('revs', `DAILY:${d}`)} className={BTN}>수정 이력</button><button onClick={() => window.print()} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button>
      </>}>
        <button onClick={() => go('shift', `${d}-D`)}><Chip tone={day?.status === 'CONFIRMED' ? 'ok' : 'warn'}>주간 {day?.status === 'CONFIRMED' ? <><LockIcon /> 확정</> : 'ⓘ 미확정'}</Chip></button>
        <button onClick={() => go('shift', `${d}-N`)}><Chip tone={night?.status === 'CONFIRMED' ? 'ok' : 'warn'}>야간 {night?.status === 'CONFIRMED' ? <><LockIcon /> 확정</> : 'ⓘ 미확정'}</Chip></button>
        {confirmed && <Chip tone="ok"><LockIcon /> 확정 {userName(r.confirmed_by)} {r.confirmed_at ? `${md(r.confirmed_at)} ${hm(r.confirmed_at)}` : ''}</Chip>}
        {pending.length > 1 && <Chip tone="warn">확정 대기 {pending.length}개</Chip>}
        {!bothConf && prev && <button onClick={() => go('daily', prev)} className={BTN}>지난 확정본 ({md(prev)})</button>}
      </InfoRow>

      <div className="contents" data-summary-panel="SCR-16">
      <Sec title="하루 생산" field="하루 생산" right={<Chip field="목표 대비" tone={pct < 90 ? 'warn' : 'ok'}>목표 대비 {pct}%</Chip>}>
        <div className="flex flex-col gap-3">
          {(() => {
            const dq = Number(day?.actual_qty ?? 0) || 0, nq = Number(night?.actual_qty ?? 0) || 0, sum = dq + nq;
            const gap = actual >= target ? '초과' : '부족';
            return (
              <div className="grid grid-cols-2 gap-2.5 md:grid-cols-5">
                <Kpi field="실적" label="실적" value={actual} unit="개" sub={`목표 ${target}개`} tone="main" />
                <div className="flex min-w-0 flex-col gap-1.5 rounded-tile border border-line bg-white px-3 py-2">
                  <span data-summary-field="주간 / 야간" className="text-small text-ink-2">주간 / 야간</span>
                  {sum > 0 ? <div className="mt-auto flex h-8 overflow-hidden whitespace-nowrap rounded-tile text-small font-semibold" role="img" aria-label={`주간 ${dq}개, 야간 ${nq}개`}>
                    <span data-summary-field="주간" className="flex min-w-0 items-center bg-brand px-2 text-white" style={{ width: `${(dq / sum) * 100}%` }}>주간 {dq}</span>
                    <span data-summary-field="야간" className="flex min-w-0 items-center bg-tile px-2 text-ink" style={{ width: `${(nq / sum) * 100}%` }}>야간 {nq}{night?.status !== 'CONFIRMED' ? ' (잠정)' : ''}</span>
                  </div> : <span data-summary-field="주간 / 야간" className="text-body text-ink-2">—</span>}
                </div>
                <Kpi field={gap} label={gap} value={Math.abs(target - actual)} unit="개" tone={actual >= target ? 'ok' : 'bad'} />
                <Kpi field="불량" label="불량" value={r.defect_qty} unit="개" />
                <Kpi field="OEE (라인)" label="OEE (라인)" value={r.oee_pct} unit="%" />
              </div>
            );
          })()}
        </div>
      </Sec>
      </div>

      <Sec title="오늘의 문제" right={<><Chip tone="crit">고장 손실 약 {r.failure_loss_qty}개</Chip><Chip tone="warn">속도 손실 약 {r.speed_loss_qty}개</Chip><Chip>추정</Chip></>}>
        <div className="hidden grid-cols-[76px_minmax(0,1fr)_84px_minmax(0,1.1fr)_40px] gap-3 pb-1 text-small text-ink-2 md:grid"><span>문제</span><span /><span className="text-right">생산 피해</span><span>처리</span><span /></div>
        {safeItems.map((x) => <div key={x.text} className={probGrid}><Chip tone="solid-crit"><LockIcon /> 안전</Chip><span className="col-span-2 md:col-span-4"><ReportLine text={x.text} /></span></div>)}
        {[...stops].sort((a, b) => b.loss_qty - a.loss_qty).map((s, i) => (
          <div key={i} className={probGrid}>
            <Chip tone="solid-crit">⚠ 긴급</Chip>
            <span><b>{s.equipment_id}</b> · {s.reason_name} <b className="font-mono">{s.minutes}</b>분 <span className="text-small text-ink-2">{md(s.start_at)} {hm(s.start_at)}</span></span>
            <span className="text-right font-mono text-title font-semibold text-crit">−{s.loss_qty}<small className="ml-0.5 font-sans text-small font-normal text-ink-2">개</small></span>
            <span className="col-span-3 flex flex-wrap items-center gap-1.5 md:col-span-1">{fixOf(s)}</span>
            <button onClick={() => go('replay', s.start_at)} aria-label={`다시 보기 ${md(s.start_at)} ${hm(s.start_at)}`} className="hidden h-9 rounded-ctl border border-line bg-white text-small hover:bg-tile md:block">▶</button>
          </div>))}
        {urgItems.map((x) => <div key={x.text} className={probGrid}><Chip tone="solid-crit">⚠ 긴급</Chip><span className="col-span-2 md:col-span-4"><ReportLine text={x.text} /></span></div>)}
        {prodItems.map((x) => <div key={x.text} className={probGrid}><Chip tone="warn">▲ 생산</Chip><span className="col-span-2 md:col-span-4">{prodText(x.text)}</span></div>)}
        {safeItems.length + stops.length + urgItems.length + prodItems.length === 0 && <span className="text-body text-ink-2">긴급 · 생산 문제 없음</span>}
        {(warnItems.length > 0 || refItems.length > 0) && <div className="mt-2"><Fold summary={`주의 ${warnItems.length}건 · 참고 ${refItems.length}건`}>
          {warnItems.length > 0 && <RankRow left={<Chip>주의</Chip>}><div className="flex flex-col gap-1.5">{warnItems.map((x) => <ReportLine key={x.text} text={x.text} />)}</div></RankRow>}
          {refItems.length > 0 && <RankRow left={<Chip>참고</Chip>}><div className="flex flex-col gap-1.5">{refItems.map((x) => <ReportLine key={x.text} text={x.text} />)}</div></RankRow>}
        </Fold></div>}
      </Sec>

      <Sec title="알람" right={<Chip>합 {al.length}</Chip>}>
        <div className="flex flex-wrap gap-1.5"><Chip tone="crit">⚠ 정지 {cnt('STOP')}</Chip><Chip tone="warn">▲ 주의 {cnt('WARN')}</Chip><Chip>ⓘ 조작 안내 {cnt('GUIDE')}</Chip>{rep.map(([k, n]) => <Chip key={k} tone="warn">반복 {k} ×{n}</Chip>)}</div>
      </Sec>
      <Sec title="로트 · 재고 · 정비">
        <div className="flex flex-col gap-2">
          {[
            ['정비', <>{[...wos.filter((w) => inDay(w.created)).map((w) => w.no), ...wrs.filter((x) => x.confirmedAt && inDay(x.confirmedAt)).map((x) => x.no), ...(history?.work_orders ?? []).filter((w) => inDay(w.created_at)).map((w) => w.wo_no), ...(history?.work_records ?? []).filter((x) => inDay(x.start_at)).map((x) => x.record_no)].map((n) => <Chip key={n} mono>{n}</Chip>)}{twin && Object.entries(twin.kpi.mttr_mtbf).filter(([, v]) => v.mttr_min != null).map(([k, v]) => <Chip key={k}>{k} MTTR {v.mttr_min}분</Chip>)}</>],
            ['로트', <><Chip>완료 {lotDay.filter((l) => l.judged_at).length}</Chip><Chip tone="ok">합격 {lotDay.filter((l) => l.status === 'PASSED' || l.status === 'RELEASED').length}</Chip><Chip>판정 대기 {lotDay.filter((l) => !l.judged_at).length}</Chip>{lotDay.filter((l) => l.on_hold).map((l) => <Chip key={l.lot_no} tone="warn" mono>보류 {l.lot_no}</Chip>)}</>],
            ['오늘 사용', <>{Object.entries(txns.filter((t) => t.txn_type === 'USE').reduce((m: Record<string, number>, t) => { m[t.item_no] = (m[t.item_no] ?? 0) + Number(t.qty_change); return m; }, {})).map(([k, v]) => <Chip key={k}>{inv?.items.find((i) => i.item_no === k)?.item_name ?? k} {v}</Chip>)}</>],
            ['재고 부족', <>{(inv?.items ?? []).filter((i) => i.low).map((i) => <Chip key={i.item_no} tone="warn">{i.item_name} — 안전 재고({i.safety_stock}) 이하</Chip>)}</>],
            ['완제품', <><Chip>BRK-A100 입고(합격) {fg.in}</Chip><Chip>출하 {fg.ship}</Chip><Chip>조정 {fg.adj}</Chip><Chip>보류 수량 {inv?.held_lot_qty ?? '—'}</Chip></>],
          ].map(([k, v]) => <div key={k as string} className="flex flex-wrap items-center gap-1.5"><b className="min-w-[64px] text-small">{k}</b>{v}</div>)}
        </div>
      </Sec>
      {role === 'MGR' && !confirmed ? <Sec title="관리자 메모"><input aria-label="관리자 메모" value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="예: 공구 재고 주문 확인" className="h-11 w-full rounded-ctl border border-line px-3" /></Sec>
        : savedMemo && <Sec title="관리자 메모"><p className="text-card">{savedMemo}</p></Sec>}
      <Acts>
        {role === 'MGR' && !confirmed && <button disabled={!bothConf} onClick={() => setConfirm(true)} className={DARK}>확정</button>}
        {role !== 'MGR' && RO}
      </Acts>
      {confirm && <ConfirmBox title="일일 보고서를 확정할까요?" okLabel="확정" body="확정하면 잠기고 일일 보고서 확정 요청 알림이 자동 처리됩니다."
        onOk={async () => { setConfirm(false); try { await api(`reports/daily/${d}/confirm`, { role, user_id: user.id, memo }); toast('일일 보고서 확정'); f.reload(); reloadReports(); } catch (e) { toast((e as Error).message); } }} onCancel={() => setConfirm(false)} />}
    </DocPage>
  );
}
