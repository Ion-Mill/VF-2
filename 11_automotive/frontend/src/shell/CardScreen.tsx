'use client';
// SCR-09 지침카드 — 알람 번호로 알람 코드집(DOC-02)·고장 대응 매뉴얼(DOC-03)·안전 작업 기준서(DOC-05)를 규칙으로 찾는다.
// 생산 영향·지난 기록·의심 로트는 시뮬레이터·9월 기록. "먼저 할 일"은 DOC-03 점검 순서의 ★(작업자) 줄 그대로 (비서 응답 없음 모양).
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { LAYOUT, MACHINES } from './data';
import { md, minsSince } from './live';
import { LEVEL_VIEW, alarmTitle, chainOf, hhmm, machineLabel, responsible, sevText, whoText } from './model';
import { SafetyBlock } from './Safety';

export default function CardScreen({ alertId }: { alertId: string }) {
  const { alerts, back, wos, srs, openWo, openSimple, user, history, go, twin, openSource } = useApp();
  const [src, setSrc] = useState(false);
  const alert = alerts.find((x) => x.id === alertId);
  if (!alert) return <div className={PAGE}><div className={CARD}>알람 기록을 찾지 못했습니다 (시연을 처음으로 되돌렸을 수 있음) <button onClick={back} className={BTN}>닫기</button></div></div>;
  const a = alert.alarm, lv = LEVEL_VIEW[alert.level], eq = MACHINES[alert.machine].eq!;
  const op30 = MACHINES[alert.machine].op === 'OP-30';
  const mins = alert.cleared ? Math.round((Date.parse(alert.cleared) - alert.ts) / 60000) : minsSince(alert.time);
  const cyc = LAYOUT.equipment[eq].std_cycle_min ?? (LAYOUT.equipment[eq].batch_time_min ?? 25) / 30;
  const chain = chainOf(alert, alerts);
  const mine = responsible(user, alert.machine);
  const past = (history?.alarms ?? []).filter((x) => x.equipment_id === eq && x.alarm_code === alert.code).slice(-5).reverse();
  const recOf = (aid: string) => history?.work_records.find((r) => r.alarm_event_id === aid);
  const wo = wos.find((w) => w.alertId === alert.id);
  const sr = srs.find((r) => r.alertId === alert.id);
  const src2 = (d: string) => { const m = d.match(/(DOC-\d+|GLOSSARY)\s+§?([\d.]+)/); return m ? <button key={d} onClick={() => openSource(m[1], m[2])} className="underline">{d}</button> : <span key={d}>{d}</span>; };
  const row = (k: string, v: React.ReactNode) => (<div className="grid grid-cols-[120px_1fr] gap-3 border-b border-slate-100 py-2"><dt className="text-[14px] font-bold text-slate-500">{k}</dt><dd className="min-w-0 text-[15px]">{v}</dd></div>);

  return (
    <div className={PAGE}>
      <div className={`${CARD} max-w-[900px]`}>
        <div className="flex items-center justify-between gap-2 border-b-2 pb-2" style={{ borderColor: lv.color }}>
          <h2 className="text-[18px] font-bold" style={{ color: lv.color }}>{lv.icon} 지침카드 · {machineLabel(alert.machine)} · {md(alert.time)} {hhmm(alert.time)} 발생{alert.scenario ? ` · 사건 ${alert.scenario}` : ''}</h2>
          <button onClick={back} className={BTN}>닫기</button>
        </div>
        {!a ? <p className="mt-3 font-semibold">{alert.code} — 알람 코드집에 없음 · 보전 담당자 호출</p> : (
          <dl>
            {row('알람', <b>{alarmTitle(a)}</b>)}
            {row('심각도', <b style={{ color: lv.color }}>{lv.icon} {sevText(a)}{alert.cleared ? ` · 설비 알람 ${hhmm(alert.cleared)} 해제` : ''}</b>)}
            {row('누가', <>{whoText(a)} <span className={`ml-2 rounded px-2 py-0.5 text-[12px] font-bold ${mine ? 'bg-[#ffe1e1] text-[#a01e23]' : 'bg-slate-100 text-slate-600'}`}>{mine ? '처리 책임: 나 (이 설비 담당)' : '처리 책임: 그 설비 OPR·MNT — 나는 [확인]만'}</span></>)}
            {(a.chain || chain.length > 1) && row('연쇄 알람', <>{chain.length > 1 ? <b>{chain.join(' → ')}</b> : null} {a.chain && <span className="text-slate-600">{chain.length > 1 ? ' · ' : ''}규칙: {a.chain}</span>}</>)}
            {row('먼저 할 일', a.steps.length ? <ol className="list-decimal pl-5">{a.steps.map((s) => <li key={s}>{s}</li>)}</ol> : <span className="text-slate-500">DOC-03 해당 절을 봅니다 ({a.doc03.join(' · ') || '없음'})</span>)}
            {row('안전', <SafetyBlock machine={alert.machine} alarm={a} />)}
            {row('생산 영향', <>현재 로트 {alert.lot ? <button onClick={() => go('lots', alert.lot)} className="font-semibold underline">{alert.lot}</button> : '—'} · {alert.cleared ? `정지 ${mins}분` : `${mins}분째`} · 약 {(mins / cyc).toFixed(1)}개 손실 (추정 = 시간 ÷ 기준 사이클 {cyc}분){op30 ? ` · OP-30 1대 → 라인 속도 절반` : ''}</>)}
            {alert.kind === 'alarm' && alert.lot && row('의심 로트 (비서 제안)', <div className="rounded-md border-2 border-dashed border-slate-400 p-2 text-[14px]">┄ 정지 등급 알람 {alert.code}가 뜬 동안 가공된 로트 <b>{alert.lot}</b>입니다. 제안만으로 상태가 바뀌지 않습니다 — 보류는 반장이 로트 추적에서. <button onClick={() => go('lots', alert.lot)} className="ml-1 underline">로트 추적</button> · 출처 <button onClick={() => openSource('DOC-06', '4')} className="underline">DOC-06 §4</button>{twin?.suspect_lot === alert.lot ? ' · (시뮬레이터 의심 로트와 같음)' : ''}</div>)}
            {row('지난 기록', past.length ? (
              <ul className="text-[14px]">{past.map((x) => { const r = recOf(x.alarm_event_id); return <li key={x.alarm_event_id}>{md(x.occurred_at)} {hhmm(x.occurred_at)} · {x.severity_at_event}{r ? ` · ${r.record_no} 원인: ${r.cause || '—'} / 조치: ${r.action || '—'} (${r.repair_min || '—'}분)` : ' · 기록 없음'}</li>; })}</ul>
            ) : '9월 기록 없음')}
          </dl>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {a?.severity === 'STOP' && op30 && <button onClick={() => wo && openWo(wo.no)} disabled={!wo} className={DARK}>{wo ? `작업지시서 ${wo.no} 보기` : '작업지시서 초안 만드는 중'}</button>}
          {a?.severity === 'STOP' && !op30 && <button onClick={() => openSimple(alert.id)} className={DARK}>{sr ? `간이 작업기록 ${sr.no}` : '간이 작업기록 쓰기 — 보전 담당자 확정'}</button>}
          {a?.severity === 'WARN' && <button onClick={() => openSimple(alert.id)} className={DARK}>{sr ? `간이 작업기록 ${sr.no}` : '간이 작업기록 쓰기'}</button>}
          {a?.severity === 'GUIDE' && <span className="text-[14px] text-slate-600">조작 안내 — 작업자가 원인을 고치면(알람 해제) 처리됩니다.</span>}
          <button onClick={() => go('replay', alert.time)} className={BTN}>다시 보기 (발생 시각)</button>
        </div>
        <button onClick={() => setSrc((s) => !s)} className="mt-3 h-11 text-[14px] font-semibold text-slate-600">{src ? '▾' : '▸'} 출처 더보기</button>
        {src && a && (
          <ul className="mt-1 list-disc pl-5 text-[13px] text-slate-600">
            <li>알람·심각도·누가 — 알람 코드집 {src2(a.doc02)}</li>
            {a.doc03.length > 0 && <li>연쇄 알람·먼저 할 일 — 고장 대응 매뉴얼 {a.doc03.map(src2)}</li>}
            <li>안전 — 안전 작업 기준서 {src2(`DOC-05 §${a.severity === 'STOP' ? '7' : '2.4'}`)} (Rev.2)</li>
            <li>생산 영향 — 설비 데이터·지표 정의서 {src2('DOC-07 §5.3')}</li>
          </ul>
        )}
      </div>
    </div>
  );
}
