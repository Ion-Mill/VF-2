'use client';
// 홈 = 3D 라인 전체 화면 위 흰 유리판 (사용자 시안 3a, 2026-10-20 — 글꼴·색은 디자인 통일 C안 토큰).
// 배치 = 시안 C로 확정 (사용자 선택 2026-10-20): 아래 정보판 한 장(왼쪽 생산·예측·OEE, 오른쪽 작업지시) + 설비를 누르면·보전 담당이면 오른쪽 위 카드.
// 질문은 이브 버튼 옆 작은 채팅창(Eve.tsx), 브리핑은 이브 창 브리핑 탭. 숫자는 모두 시연 데이터 서버 값.
import { useState } from 'react';
import { useApp } from './ctx';
import { MACHINES, STATE_VIEW, stateOf } from './data';
import type { OrderRow } from './live';
import { alarmTitle } from './model';
import { fmtFrac, fmtPct } from './format';
import Panels from './Panels';

/** 유리판 모양 — 3D 위에 뜨는 칸(위 바 · 범례 · 홈 칸)만 쓴다. 다른 화면 카드는 ui.tsx Sec(흰 평면) */
export const GLASS = 'border border-white/70 bg-white/[.86] shadow-[0_10px_30px_rgba(28,37,48,.13)] backdrop-blur-xl';
const isDone = (o: OrderRow) => o.status === 'COMPLETED' || o.status === 'DONE';
// 정보판 칸 이름 앞 파스텔 아이콘 칸 (화이트 카드 테마를 홈에도, 사용자 요청 2026-10-22 — 바탕은 유리 그대로). 색은 파랑 계열만, 상태색과 안 겹치게
const KI: Record<string, [string, string]> = {
  생산: ['bg-brand-tint text-brand', '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5"/>'],
  예측: ['bg-op5 text-op5-i', '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>'],
  OEE: ['bg-op3 text-op3-i', '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m12 18 4-6"/>'],
  가동률: ['bg-op1 text-op1-i', '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>'],
  성능: ['bg-brand-tint text-brand', '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>'],
  양품률: ['bg-op5 text-op5-i', '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'],
  손실: ['bg-op4 text-op4-i', '<path d="m3 7 6 6 4-4 8 8"/><path d="M15 17h6v-6"/>'],
  작업지시: ['bg-op1 text-op1-i', '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>'],
};
const KIco = ({ k, size = 28 }: { k: string; size?: number }) => (
  <span className={`inline-flex shrink-0 items-center justify-center ${size < 28 ? 'rounded-[6px] max-[1500px]:hidden' : 'rounded-[8px]'} ${KI[k][0]}`} style={{ width: size, height: size }} aria-hidden="true">
    <svg width={size * 0.54} height={size * 0.54} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: KI[k][1] }} />
  </span>);
const LB = 'flex items-center gap-2 text-[16px] text-ink-2';

export default function HomeHud() {
  const { twin, alerts, user, selected, selectMachine, go, openCard, bandOff } = useApp();
  const [why, setWhy] = useState<'oee' | 'loss' | null>(null);
  const [pmFold, setPmFold] = useState(false); // 정비 현황 접기 (사용자 요청 2026-10-22)
  const [more, setMore] = useState(false); // 아래 정보판 펼침 = 자세한 판(생산현황 그래프 · OEE · 손실 · 작업지시 표/설비) — 사용자 요청 2026-10-20
  if (!twin) return null;
  const p = twin.production, kp = twin.kpi.by.LINE;
  const ahead = p.forecast_qty >= p.total_target_qty;
  const fTone = ahead ? 'text-ok' : p.risk ? 'text-warn' : 'text-ink';
  const open = alerts.filter((a) => !a.handled && a.kind !== 'guide');
  const orders = (user.role === 'OPR' ? twin.orders.filter((o) => user.procs.includes(o.current_process)) : twin.orders).filter((o) => !isDone(o))
    .sort((a, b) => Number(b.status === 'IN_PROGRESS') - Number(a.status === 'IN_PROGRESS'));

  const whyText = why === 'oee'
    ? <>가동률 = 가동 {kp.apt_min}분 ÷ 계획 {kp.pbt_min}분 · 성능 = 7.0분 × 생산 {kp.pq}개 ÷ 가동 {kp.apt_min}분 · 양품률 = 양품 {kp.good_qty} ÷ 생산 {kp.pq} (DOC-07 §6.2){kp.oee_pct == null ? ' — 생산 기록이 쌓이면 계산돼요' : ''}</>
    : <>손실 {Math.round(p.loss_qty)}개 = 고장(멈춤) <b className="text-crit">{Math.round(p.failure_loss_qty)}개</b> + 속도(느림) <b className="text-warn">{Math.round(p.speed_loss_qty)}개</b> · 순간 정지 {p.short_stops.count}건 {p.short_stops.minutes}분 (추정)</>;
  const band = alerts.some((a) => !a.handled && a.level !== '참고' && !(a.level === '주의' && bandOff.includes(a.id))); // App 이브 알림 띠(top 92, 높이 56)가 있으면 그 아래로 (2026-10-22)
  const sideCard = (selected && selected !== 'inf') || user.role === 'MNT'; // 오른쪽 위 카드: 설비를 눌렀을 때 · 보전 담당 (작업지시는 아래 정보판)

  return (<>
    {/* 펼친 판: 예전 하단 패널(Panels) — 요약 정보판과 같은 자리·폭(이브 채팅창 앞까지), 높이만 조금 더 (사용자 요청 2026-10-20 "너무 커, 이 범위 안에"). [접기]는 판 위 오른쪽에 떠서 높이를 안 씀 */}
    {more && (
      <div className="pointer-events-auto absolute bottom-[70px] left-5 right-[470px] z-10" style={{ height: 'min(380px, calc(100vh - 330px))' }}>
        <button onClick={() => setMore(false)} aria-expanded="true" className={`absolute -top-[52px] right-0 h-11 rounded-full px-5 text-body font-semibold text-ink ${GLASS}`}>접기 ▾</button>
        <Panels />
      </div>
    )}
    {/* 아래 정보판 한 장 — 왼쪽 "얼마나"(생산·예측·OEE), 오른쪽 "무엇을"(작업지시). 3D 위쪽 2/3과 라인 양 끝을 비움 */}
    {!more && (
      <div className="pointer-events-auto absolute bottom-[70px] left-5 right-[470px] z-10 flex flex-col gap-2">
        <div className="flex items-end gap-2">
          {why ? <div className={`min-w-0 flex-1 rounded-card px-4 py-2.5 text-body text-ink ${GLASS}`}>{whyText}</div> : <span className="flex-1" />}
          <button onClick={() => { setMore(true); setWhy(null); }} aria-expanded="false" className={`h-11 shrink-0 rounded-full px-5 text-body font-semibold text-ink ${GLASS}`}>자세히 ▴</button>
        </div>
        <section className={`grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] rounded-stage ${GLASS}`} aria-label="생산 현황과 작업지시">
          <div className="flex min-w-0 flex-col justify-center gap-3 px-8 py-5">
            {/* 시안 B (사용자 선택 2026-10-21): 생산·예측·OEE 한 줄 칸 3개 + 아래 작은 칸 4개, 칸마다 윗줄 이름 · 아랫줄 숫자 */}
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)] gap-3">
              <span className="flex flex-col gap-1.5 rounded-card border border-line bg-white px-4 py-3"><span className={LB}><KIco k="생산" />생산</span><span className="flex items-baseline gap-1.5 whitespace-nowrap"><b className="font-mono text-[40px] leading-none text-ink">{p.actual_qty}</b><span className="font-mono text-[24px] text-ink-2">/{p.total_target_qty}</span></span></span>
              <span className="flex flex-col gap-1.5 rounded-card border border-line bg-white px-4 py-3" title={`예측 = 실적 + 최근 1시간 속도 ${p.rate_per_hour}개/시 × 남은 ${Math.round(p.left_work_min)}분 (추정, DOC-07 §8)`}><span className={LB}><KIco k="예측" />예측</span><span className="flex items-baseline gap-1.5 whitespace-nowrap"><b className={`font-mono text-[40px] leading-none ${fTone}`}>{p.forecast_qty}</b><span className={`text-[27px] font-bold ${fTone}`} aria-label={ahead ? '목표 넘김 예상' : '목표 미달 예상'}>{ahead ? '↗' : '↘'}</span></span></span>
              <button onClick={() => setWhy(why === 'oee' ? null : 'oee')} className="flex flex-col gap-1.5 rounded-card border border-line bg-white px-4 py-3 text-left hover:bg-tile"><span className={LB}><KIco k="OEE" />OEE</span><span className="flex items-baseline gap-1.5 whitespace-nowrap"><b className={`font-mono text-[40px] leading-none ${kp.warn.includes('OEE') ? 'text-warn' : 'text-ink'}`}>{kp.oee_pct == null ? '—' : kp.oee_pct.toFixed(1)}</b><span className="text-[24px] font-bold text-ink">%</span></span></button>
            </div>
            <button onClick={() => setWhy(why === 'loss' ? null : 'loss')} className="grid grid-cols-4 gap-2.5 text-left">
              {([['가동률', kp.availability_pct], ['성능', kp.performance_pct], ['양품률', kp.quality_pct]] as const).map(([k, x]) => <span key={k} className="flex min-w-0 flex-col gap-1 rounded-card border border-line bg-white px-3.5 py-2.5"><span className={LB}><KIco k={k} size={22} />{k}</span><b className="font-mono text-[24px] leading-tight text-ink">{x == null ? '—' : fmtPct(x)}</b></span>)}
              <span className="flex min-w-0 flex-col gap-1 rounded-card border border-line bg-white px-3.5 py-2.5"><span className={LB}><KIco k="손실" size={22} />손실</span><span><b className="font-mono text-[24px] leading-tight text-ink">{Math.round(p.loss_qty)}</b><span className="text-[18px] text-ink"> 개</span></span></span>
            </button>
          </div>
          <div className="flex min-w-0 flex-col gap-2 border-l border-line-soft px-7 py-4">
            <div className="flex items-center gap-2.5"><KIco k="작업지시" /><h3 className="text-[22px] font-bold text-ink">작업지시 진행</h3>{user.role === 'OPR' && <span className="font-mono text-[16px] text-ink-2">{user.procs.join(' · ')}</span>}<button onClick={() => go('lots')} className="ml-auto text-[16px] font-semibold text-brand-ink hover:text-brand">전체 ›</button></div>
            {orders.length === 0 ? <p className="py-1 text-[18px] text-ink-2">지금 진행 중인 작업지시가 없어요.</p> : orders.slice(0, 3).map((o) => {
              const run = o.status === 'IN_PROGRESS', [txt, tone] = o.delay ? [o.delay, 'bg-warn-bg text-warn'] : run ? ['진행 중', 'bg-ok-bg text-ok'] : ['대기', 'border border-line bg-white font-medium text-ink-2'];
              return (
                <button key={o.order_no} onClick={() => go('lots', o.lots[o.lots.length - 1] ?? null)} className="grid grid-cols-[auto_minmax(40px,1fr)_auto_auto] items-center gap-4 rounded-tile px-1.5 py-2 text-left hover:bg-white/70">
                  <b className="font-mono text-[20px] text-ink">{o.order_no}</b>
                  <div className="h-2.5 rounded-[5px] bg-track"><div className="h-2.5 rounded-[5px] bg-brand" style={{ width: `${Math.min(100, (o.done_qty / Math.max(1, o.order_qty)) * 100)}%` }} /></div>
                  <span className="font-mono text-[20px] font-bold text-ink">{fmtFrac(o.done_qty, o.order_qty)}</span>
                  <span className={`inline-flex h-[30px] items-center gap-1.5 justify-self-end whitespace-nowrap rounded-[8px] px-[11px] text-[15px] font-semibold ${tone}`}>{(o.delay || run) && <i className="h-[7px] w-[7px] rounded-full bg-current" />}{txt}</span>
                </button>);
            })}
          </div>
        </section>
      </div>
    )}

    {/* 오른쪽 위 카드: 설비를 누르면 그 설비, 보전 담당은 정비 현황 */}
    {sideCard && !more && <section className={`pointer-events-auto absolute right-5 ${band ? 'top-[160px]' : 'top-[92px]'} z-10 flex max-h-[calc(100%-260px)] w-[440px] flex-col rounded-stage p-5 ${GLASS}`}>
      {selected && selected !== 'inf' ? <MachineCard id={selected} onClose={() => selectMachine(null)} /> : user.role === 'MNT' ? (<>
        <div className={`flex items-baseline justify-between ${pmFold ? '' : 'mb-3'}`}><button onClick={() => setPmFold((f) => !f)} aria-expanded={!pmFold} className="flex items-baseline gap-2 text-band font-bold text-ink">정비 현황{pmFold && open.length > 0 && <span className="text-body font-semibold text-ink-2">{open.length}건</span>}<span className="text-[13px] text-ink-2">{pmFold ? '▸' : '▾'}</span></button><button onClick={() => go('pm')} className="text-body text-ink-2 hover:text-ink">예방 정비 ›</button></div>
        {!pmFold && <div className="min-h-0 overflow-y-auto">
          {open.length === 0 ? <p className="py-2 text-card text-ink-2">처리 안 된 고장 알람이 없어요.</p> : open.slice(0, 6).map((a) => (
            <button key={a.id} onClick={() => openCard(a.id)} className="mb-2 w-full rounded-card bg-white/70 px-4 py-3 text-left hover:bg-white">
              <div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${a.level === '긴급' ? 'bg-crit' : a.level === '주의' ? 'bg-warn-mark' : 'bg-bar'}`} />
                <b className="font-mono text-card text-ink">{MACHINES[a.machine].name} {a.code}</b><span className="ml-auto font-mono text-body text-ink-2">{a.time.slice(11, 16)}</span></div>
              <div className="mt-1 truncate text-body text-ink-2">{alarmTitle(a.alarm, a.code)}</div>
            </button>))}
        </div>}
      </>) : null}
    </section>}

  </>);
}

function MachineCard({ id, onClose }: { id: keyof typeof MACHINES; onClose: () => void }) {
  const { twin, alerts, openCard, go } = useApp();
  const E = twin && MACHINES[id].eq ? twin.equipment[MACHINES[id].eq!] : null;
  if (!twin || !E) return <p className="text-card text-ink-2">이 설비는 기록이 없어요.</p>;
  const v = STATE_VIEW[stateOf(E)], pq = (twin.process[E.process_code] ?? { pq: 0 }).pq;
  const cur = [...alerts].reverse().find((a) => a.machine === id && !a.handled);
  const row = 'flex items-baseline justify-between gap-3 border-b border-line-soft py-2 text-card';
  return (<>
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <b className="font-mono text-title text-ink">{MACHINES[id].name}</b><span className="rounded-ctl bg-tile px-2 py-0.5 font-mono text-body">{MACHINES[id].op}</span>
      <span className="text-card font-bold" style={{ color: v.color }}>{v.icon} {v.text} · {E.minutes}분째</span>
      <button onClick={onClose} className="ml-auto h-9 rounded-full px-3 text-body text-ink-2 hover:bg-tile">닫기</button>
    </div>
    {cur && (
      <div className={`mb-2 flex items-center gap-2 rounded-card px-4 py-3 ${cur.level === '긴급' ? 'bg-crit-bg text-crit' : 'bg-warn-bg text-warn'}`}>
        <b className="min-w-0 flex-1 truncate text-card">{alarmTitle(cur.alarm, cur.code)}</b>
        <button onClick={() => openCard(cur.id)} className="h-10 shrink-0 rounded-ctl bg-ink px-4 text-body font-semibold text-white">지침카드</button>
      </div>)}
    <div className={row}><span className="text-ink-2">현재 로트</span>{E.lot_no ? <button onClick={() => go('lots', E.lot_no)} className="font-mono font-semibold text-brand-ink underline">{E.lot_no}</button> : '—'}</div>
    <div className={row}><span className="text-ink-2">교대 실적 / 목표</span><span><b className="font-mono">{pq}</b> / {twin.production.total_target_qty}</span></div>
    <div className={row}><span className="text-ink-2">오늘 정지</span><span><b className="font-mono">{E.stop_min}</b>분</span></div>
  </>);
}
