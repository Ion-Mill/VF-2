'use client';
// SCR-09 지침카드 — 알람 번호로 알람 코드집(DOC-02)·고장 대응 매뉴얼(DOC-03)·안전 작업 기준서(DOC-05)를 규칙으로 찾는다.
// 생산 영향·지난 기록·의심 로트는 시뮬레이터·9월 기록. "먼저 할 일"은 비서 정리가 준비되면 그것을 본문으로 보이고 DOC-03 점검 순서의 ★(작업자) 줄 원문은 "원문 보기"에 둔다 (2026-10-19, UI설계서 SCR-09 [5]). 준비 전·실패·꺼짐이면 ★ 줄 원문 그대로 (비서 응답 없음 모양).
import { useState } from 'react';
import { BTN, CARD, DARK, PAGE, useApp } from './ctx';
import { LAYOUT, MACHINES } from './data';
import { md, minsSince } from './live';
import { LEVEL_VIEW, alarmTitle, chainOf, hhmm, responsible, sevText } from './model';
import { SafeTag, SafetyBlock, safetySrc } from './Safety';
import { Band, Chip, DocHead, DocPage, Fold, Kpi, NumList, Sec, SrcFold } from './DocKit';
import { useGuideCardText } from './assistText';
import { Band as CBand } from './ui';
import { cardsBand } from './bands';

const SEV_KO: Record<string, string> = { STOP: '정지', WARN: '주의', GUIDE: '조작 안내' };

// 시안(2026-10-20): 결론 띠 → 먼저 할 일(큰 번호) → 보전 단계(펼침) → 생산 영향 숫자 → 안전 고정 서식. 지난 기록(표)·출처는 접음.
export default function CardScreen({ alertId }: { alertId: string }) {
  const { alerts, back, wos, srs, openWo, openSimple, user, history, go, openSource } = useApp();
  const alert = alerts.find((x) => x.id === alertId);
  const guideText = useGuideCardText(alert?.code, alert?.alarm?.steps); // 비서가 쉬운 말로 다듬은 "먼저 할 일" (없으면 null). 훅이라 아래 early return보다 위
  if (!alert) return <div className={PAGE}><div className={CARD}>알람 기록을 찾지 못했습니다 (시연을 처음으로 되돌렸을 수 있음) <button onClick={back} className={BTN}>닫기</button></div></div>;
  const a = alert.alarm, lv = LEVEL_VIEW[alert.level], eq = MACHINES[alert.machine].eq!;
  const op30 = MACHINES[alert.machine].op === 'OP-30';
  const mins = alert.cleared ? Math.round((Date.parse(alert.cleared) - alert.ts) / 60000) : minsSince(alert.time);
  const cyc = LAYOUT.equipment[eq].std_cycle_min ?? (LAYOUT.equipment[eq].batch_time_min ?? 25) / 30;
  const chain = chainOf(alert, alerts);
  const mine = responsible(user, alert.machine);
  const past = (history?.alarms ?? []).filter((x) => x.equipment_id === eq && x.alarm_code === alert.code).slice(-5).reverse();
  const recOf = (aid: string) => history?.work_records.find((r) => r.alarm_event_id === aid);
  // 같은 설비에 끝나지 않은 작업지시서가 있으면 새 초안을 안 만든다(App.tsx createWo 조건) — 그 작업지시서로 연결 (안 그러면 "만드는 중"에 영원히 멈춤, 2026-10-22)
  const wo = wos.find((w) => w.alertId === alert.id) ?? wos.find((w) => w.machine === alert.machine && w.state !== 'done' && w.state !== 'cancelled');
  const sr = srs.find((r) => r.alertId === alert.id);
  const src2 = (d: string) => { const m = d.match(/(DOC-\d+|GLOSSARY)\s+§?([\d.]+)/); return m ? <button key={d} onClick={() => openSource(m[1], m[2])} className="underline">{d}</button> : <span key={d}>{d}</span>; };
  const tone = alert.level === '긴급' ? 'crit' : alert.level === '주의' ? 'warn' : 'mute';
  const assisted = a && a.steps.length ? guideText : null; // 비서 정리가 준비된 때만 본문으로 (줄 수가 원문과 같은 것만 훅이 돌려준다), 원문은 접어 둔다 (팀원 2026-10-19)
  const rule = a?.chain.match(/\(([^)]+)\)/)?.[1];

  return (
    <DocPage width={900}>
      <DocHead title="지침카드" sub={`${md(alert.time)} ${hhmm(alert.time)} 발생${alert.scenario ? ` · 사건 ${alert.scenario}` : ''}`} right={<button onClick={back} className={BTN}>닫기</button>} />
      {!a ? <Band tone="crit" title={<>{alert.code} — 알람 코드집에 없음</>} chips={<Chip tone="solid-crit">보전 담당자 호출</Chip>} /> : (<>
        <Band tone={tone}
          title={<><span style={{ color: lv.color }}>{lv.icon} {sevText(a)}</span> · {MACHINES[alert.machine].name} · 알람 <span className="font-mono" style={{ color: lv.color }}>{a.code}</span> {a.nameKo.replace(/\(.*\)/, '')} · <span className="font-mono">{mins}</span>분{alert.cleared ? '' : '째'}</>}
          desc={a.easy}
          chips={<>
            <Chip tone={a.severity === 'STOP' ? 'solid-crit' : a.severity === 'WARN' ? 'solid-warn' : 'mute'}>{mine ? '처리 책임: 나' : `처리 책임: ${a.responder === 'MNT' ? '보전 담당자' : '그 설비 작업자'}`}</Chip>
            {chain.length > 1 && <Chip tone="crit">연쇄 {chain.join(' → ')}{rule ? ` · ${rule}` : ''}</Chip>}
            {alert.lot && <button onClick={() => go('lots', alert.lot)}><Chip mono>로트 {alert.lot}</Chip></button>}
            {a.severity === 'STOP' && op30 && <Chip tone="warn">OP-30 1대 → 라인 속도 절반</Chip>}
            {alert.cleared && <Chip tone="ok">설비 알람 {hhmm(alert.cleared)} 해제</Chip>}
          </>}>
          <div className="flex flex-wrap gap-2">
            {a.severity === 'STOP' && op30 && <button onClick={() => wo && openWo(wo.no)} disabled={!wo} className={DARK}>{wo ? `작업지시서 ${wo.no} 보기 →` : '작업지시서 초안 만드는 중'}</button>}
            {a.severity === 'STOP' && !op30 && <button onClick={() => openSimple(alert.id)} className={DARK}>{sr ? `간이 작업기록 ${sr.no} →` : '간이 작업기록 쓰기 →'}</button>}
            {a.severity === 'WARN' && <button onClick={() => openSimple(alert.id)} className={DARK}>{sr ? `간이 작업기록 ${sr.no} →` : '간이 작업기록 쓰기 →'}</button>}
            <button onClick={() => go('replay', alert.time)} className={BTN}>▶ 다시 보기 (발생 시각)</button>
          </div>
        </Band>
        <Sec title="먼저 할 일" right={a.steps.length ? <>{assisted && <Chip tone="acc">비서 정리</Chip>}<Chip tone="acc">작업자 {a.steps.length}단계</Chip></> : undefined}>
          {assisted ? (
            <div className="flex flex-col gap-2">
              <NumList items={assisted} big />
              <p className="text-small text-ink-2">비서(외부 LLM)가 쉬운 말로 다듬은 글입니다. 원문과 다르면 원문(DOC-03)을 따릅니다.</p>
              <details className="text-body"><summary className="cursor-pointer font-semibold text-ink-2">원문(DOC-03) 보기</summary><div className="mt-2 rounded-tile border border-line p-3"><NumList items={a.steps} /></div></details>
            </div>
          ) : a.steps.length ? <NumList items={a.steps} big /> : <span className="text-body text-ink-2">{a.doc03.join(' · ') || '해당 절 없음'}</span>}
        </Sec>
        {a.maint.length > 0 && <Sec title="보전 담당자 단계" right={<Chip>보전 {a.maint.length}단계</Chip>}><NumList items={a.maint} start={a.steps.length + 1} /></Sec>}
        <Sec title="생산 영향" right={<Chip>추정</Chip>}>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            <Kpi label="정지" value={mins} unit={alert.cleared ? '분' : '분째'} sub={`${hhmm(alert.time)}부터`} />
            <Kpi label="손실 (추정)" value={`약 ${(mins / cyc).toFixed(1)}`} unit="개" sub={`${mins}분 ÷ 기준 사이클 ${cyc}분`} />
            <Kpi label="가공 중이던 로트" value={<span className="text-band">{alert.lot ?? '—'}</span>} sub={alert.kind === 'alarm' && alert.lot ? '의심 로트 제안' : undefined} />
          </div>
        </Sec>
        <Sec title="안전" right={a.severity === 'STOP' ? SafeTag : undefined}><SafetyBlock machine={alert.machine} alarm={a} /></Sec>
        <Fold summary={`지난 기록 — 9월 ${eq} · 알람 ${alert.code}`}>
          {past.length ? (
            <div className="overflow-x-auto"><table className="w-full min-w-[620px] table-fixed text-left text-body">
              <colgroup><col className="w-[132px]" /><col className="w-[72px]" /><col className="w-[112px]" /><col /><col /><col className="w-[96px]" /></colgroup>{/* 폭 = 글자 한 단계 크게(.fs-up)에 맞춤 (2026-10-22) */}
              <thead className="text-small text-ink-2"><tr>{['날짜·시각', '등급', '기록 번호', '원인', '조치', '수리 시간'].map((h) => <th key={h} className="border-b border-line px-2 py-1.5 font-semibold">{h}</th>)}</tr></thead>
              <tbody>{past.map((x) => { const r = recOf(x.alarm_event_id); const clamp = 'line-clamp-2'; return (
                <tr key={x.alarm_event_id} className="border-b border-line-soft align-top">
                  <td className="whitespace-nowrap px-2 py-2 font-mono">{md(x.occurred_at)} {hhmm(x.occurred_at)}</td>
                  <td className="px-2 py-2">{SEV_KO[x.severity_at_event] ?? x.severity_at_event}</td>
                  <td className="px-2 py-2 font-mono">{r?.record_no ?? '—'}</td>
                  <td className="px-2 py-2"><span className={clamp} title={r?.cause}>{r?.cause || '—'}</span></td>
                  <td className="px-2 py-2"><span className={clamp} title={r?.action}>{r?.action || '—'}</span></td>
                  <td className="px-2 py-2">{r?.repair_min ? <><b className="font-mono text-band">{r.repair_min}</b><span className="ml-0.5 text-ink-2">분</span></> : '—'}</td>
                </tr>); })}</tbody>
            </table></div>
          ) : <span className="text-ink-2">없음</span>}
        </Fold>
        <SrcFold>
          <li>알람·심각도·누가 — 알람 코드집 {src2(a.doc02)}</li>
          {a.doc03.length > 0 && <li>연쇄 알람·먼저 할 일 — 고장 대응 매뉴얼 {a.doc03.map(src2)}</li>}
          {safetySrc(alert.machine, a, openSource)}
          <li>생산 영향 — 설비 데이터·지표 정의서 {src2('DOC-07 §5.3')}</li>
          {alert.kind === 'alarm' && alert.lot && <li>의심 로트 — {src2('DOC-06 §4')}</li>}
        </SrcFold>
      </>)}
    </DocPage>
  );
}

// 메뉴 "지침카드" — 전체 지침카드 목록, 누르면 그 지침카드 (페이지구조 v3 Q28)
// 연표 모양 (2026-10-20 팀 검토): 날짜 머리 → 왼쪽 세로선의 시각 점(등급 색) → 오른쪽 카드. 기본 = 처리 필요한 것만 · 최신순
const WD = ['일', '월', '화', '수', '목', '금', '토'];
export function CardList() {
  const { alerts, go, openCard } = useApp();
  const [mach, setMach] = useState('');
  const [lv, setLv] = useState('');
  const [all, setAll] = useState(false);
  const [asc, setAsc] = useState(false);
  const open = alerts.filter((a) => !a.handled).length;
  const list = alerts.filter((a) => (all || !a.handled) && (!mach || a.machine === mach) && (!lv || a.level === lv)).sort((x, y) => (asc ? x.ts - y.ts : y.ts - x.ts));
  const days: [string, typeof list][] = [];
  list.forEach((a) => { const d = a.time.slice(0, 10); const g = days.find(([k]) => k === d); if (g) g[1].push(a); else days.push([d, [a]]); });
  const wd = (d: string) => WD[new Date(Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10))).getUTCDay()];
  // 글자 한 단계 크게 = 문서 묶음 전체에 붙는 .fs-up (globals.css, 2026-10-22). 여기선 높이 · 여백만
  const sel = 'h-11 rounded-full border border-line bg-white px-4 text-small';
  const seg = (on: boolean) => `h-11 px-5 text-small font-semibold ${on ? 'bg-brand-tint text-brand-ink' : 'bg-white'}`;
  return (
    <DocPage width={1440}>
      {(() => { // 디자인 통일 C안: 결론 띠 1개 (bands.ts cardsBand) — 처리 안 된 것 중 정지 등급 먼저
        const cin = alerts.filter((a) => a.kind !== 'guide').map((a) => ({ id: a.id, machine: MACHINES[a.machine].name, code: a.code, name: (a.alarm?.nameKo ?? '').replace(/\s*\([A-Z0-9 ._/-]+\)/, ''), kind: a.kind, handled: a.handled, minutes: minsSince(a.time), responsible: a.alarm?.responder === 'MNT' ? '보전' : '작업자', first: a.alarm?.steps[0] }));
        const top = cin.filter((x) => !x.handled).sort((x, y) => Number(y.kind === 'alarm') - Number(x.kind === 'alarm') || y.minutes - x.minutes)[0];
        return <CBand spec={cardsBand(cin)} onAction={() => top && openCard(top.id)} />;
      })()}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-full border border-line"><button onClick={() => setAll(false)} className={seg(!all)}>처리 필요 {open}</button><button onClick={() => setAll(true)} className={seg(all)}>전체 {alerts.length}</button></div>
        <button onClick={() => setAsc((v) => !v)} className={sel} aria-label="정렬 바꾸기">{asc ? '오래된순' : '최신순'} ⇅</button>
        <select aria-label="설비" value={mach} onChange={(e) => setMach(e.target.value)} className={sel}><option value="">설비 전체</option>{Object.entries(MACHINES).filter(([, m]) => m.eq).map(([k, m]) => <option key={k} value={k}>{m.name}</option>)}</select>
        <select aria-label="등급" value={lv} onChange={(e) => setLv(e.target.value)} className={sel}><option value="">등급 전체</option>{['긴급', '주의', '참고'].map((l) => <option key={l}>{l}</option>)}</select>
      </div>
      {list.length === 0 ? <div className="flex min-h-[55vh] items-center justify-center"><div className="rounded-card border border-line bg-white px-8 py-6 text-card text-ink-2">{all ? '지침카드가 없습니다' : '처리할 지침카드가 없습니다'}</div></div> : days.map(([d, as]) => (
        <section key={d} className="flex flex-col gap-2">
          <h3 className="text-card font-bold">{md(d)} <span className="text-body font-semibold text-ink-2">({wd(d)})</span></h3>
          <ol className="relative ml-[72px] flex flex-col gap-3 border-l-2 border-line py-1 pl-5">
            {as.map((a) => {
              const v = LEVEL_VIEW[a.level], who = a.alarm?.responder === 'MNT' ? '보전' : '작업자';
              const col = a.handled ? '#94a3b8' : v.color; // 처리됨 = 회색 줄 (2026-10-20)
              return (
                <li key={a.id} className="relative">
                  <span className="absolute -left-[102px] top-[17px] w-[62px] text-right font-mono text-small text-ink-2">{hhmm(a.time)}</span>
                  <span className="absolute -left-[29px] top-[21px] h-4 w-4 rounded-full border-2 border-white" style={{ background: col }} aria-hidden />
                  <button onClick={() => go('card', a.id)} className={`flex w-full flex-wrap items-center gap-x-4 gap-y-1.5 rounded-tile border px-5 py-3.5 text-left ${a.handled ? 'border-line-soft bg-tile text-ink-3 hover:bg-track' : 'border-line bg-white hover:bg-tile'}`}>
                    <b className="text-card" style={{ color: col }}>{v.icon} {MACHINES[a.machine].name} · {a.code}</b>
                    <span className="min-w-0 flex-1 truncate text-card font-semibold">{a.alarm ? a.alarm.nameKo.replace(/\(.*\)/, '') : alarmTitle(a.alarm, a.code)}</span>
                    <span className="flex flex-wrap gap-2 [&>span]:min-h-8 [&>span]:px-3">
                      <Chip tone={a.handled ? 'mute' : a.level === '긴급' ? 'solid-crit' : a.level === '주의' ? 'warn' : 'mute'}>처리 책임: {who}</Chip>
                      {a.handled ? <Chip>✓ 처리됨</Chip> : <Chip mono>{minsSince(a.time)}분째</Chip>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </DocPage>
  );
}
