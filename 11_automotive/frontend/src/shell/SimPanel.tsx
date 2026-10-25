'use client';
// 시연 조작판 (UI설계서 2.1 [14], 9.6) — 시연 모드에서만. 사건 버튼 = API-SIM-01, 시계 = API-SIM-02, 처음으로 = API-SIM-03.
// 사건은 누른 때(시연 시계 지금) 시작하고, 시각·숫자는 그때의 계산 값이다 (설계서 7장).
import { useState } from 'react';
import { api, type Twin } from './live';
import { ConfirmBox } from './Safety';

const EVENTS: [string, string, string][] = [
  ['S1', 'S1 충돌', 'VF2-01 축 부하 급상승 → 992 정지 알람 (작업기록서 확정까지 고장)'],
  ['S3', 'S3 공구', 'VF2-01 T05가 빨리 닳음 → 90% 교체 알림'],
  ['S4', 'S4 공기압', 'VF2-01 공기 압력이 서서히 떨어짐 → 120 (자동 복귀)'],
  ['S6', 'S6 정비', 'VF2-02 예방 정비 90분 → OP-30 1대 가동 → 재공 증가·병목'],
];
const b = 'h-11 rounded-ctl border border-line px-3 text-small font-semibold hover:bg-tile disabled:text-ink-3';

export default function SimPanel({ twin, refresh, toast, api3d, onClose }: { twin: Twin | null; refresh: () => void; toast: (m: string) => void; api3d: () => any; onClose: () => void }) {
  const [reset, setReset] = useState(false);
  const [fx, setFx] = useState<Record<string, boolean>>({});
  const call = async (path: string, body: unknown, ok: string) => {
    try { await api(path, body); toast(ok); refresh(); } catch (e) { toast((e as Error).message); }
  };
  const c = twin?.clock;
  const locked = c?.can_control === false;      // 시연 조작은 진행자만 (백엔드 MOM_SIM_CONTROL_USERS, 2026-10-24)
  // 교대가 끝난 뒤(17:00~20:00, 05:00~)는 휴무(계획 정지) — 설비가 다 서 있어 배속을 바꿔도 3D가 안 움직인다
  const off = !!twin && !!c && c.sim_at >= twin.shift.end_at;
  const skipTo = twin?.shift.shift_type === 'DAY' ? (off ? '20:00' : '17:00') : null;
  const toggle = (k: string) => { const n = !fx[k]; setFx({ ...fx, [k]: n }); api3d()?.setState((s: any) => (k === 'night' || k === 'explode' ? { [k]: n } : { layers: { ...s.layers, [k]: n } })); };
  return (
    <div className="absolute right-0 top-[48px] z-30 w-[400px] rounded-tile border border-line bg-white p-3 text-small shadow-lg">
      <div className="mb-1 flex items-center justify-between"><b>사건 버튼</b><button onClick={onClose} className="h-8 px-2 text-small">닫기</button></div>
      {!twin && <p className="text-ink-2">시연 데이터 서버에 연결되지 않았습니다.</p>}
      <div className="flex flex-col gap-1">
        {EVENTS.map(([code, label, sub]) => {
          const why = twin?.buttons[code];
          return (
            <button key={code} disabled={!twin || !!why || locked} onClick={() => call('sim/inject', { scenario_code: code }, `${label} 시작`)}
              className="flex min-h-[48px] flex-col items-start rounded-ctl border border-line px-3 py-1 text-left hover:bg-tile disabled:bg-tile disabled:text-ink-3">
              <span className="font-bold">{label}</span>
              <span className="text-small">{why ? `잠김 — ${why}` : sub}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 border-t border-line-soft pt-2 font-bold">시연 시계 {c ? `· ${c.sim_at.slice(11, 16)} ×${c.speed}${c.paused ? ' ⏸' : ''}` : ''}</div>
      <div className="mt-1 flex flex-wrap gap-1">
        {[180, 60, 10, 1].map((s) => <button key={s} disabled={!twin || locked} onClick={() => call('sim/clock', { speed: s }, `배속 ×${s}`)} className={`${b} ${c?.speed === s ? 'border-brand bg-tile' : ''}`}>×{s}</button>)}
        <button disabled={!twin || locked} onClick={() => call('sim/clock', { paused: !c?.paused }, c?.paused ? '다시 시작' : '일시정지 — 3D 움직임도 멈춤')} className={b}>{c?.paused ? '▶ 다시 시작' : '⏸ 일시정지'}</button>
        <button disabled={!skipTo || locked} onClick={() => call('sim/clock', { skip: `TODAY_${skipTo}` }, skipTo === '17:00' ? '17:00으로 넘김 — 남은 주간 교대를 만듦' : '20:00으로 넘김 — 야간 교대 시작')} className={b}>{skipTo ? `${skipTo}으로` : '넘기기 없음'}</button>
        <button disabled={!twin || locked} onClick={() => setReset(true)} className={b}>처음으로</button>
      </div>
      {locked && <p className="mt-1 rounded bg-tile px-2 py-1 text-small font-semibold text-ink-2">시연 조작(사건·시계·처음으로)은 진행자만 할 수 있습니다. 모두가 같은 공장을 봅니다.</p>}
      {off && <p className="mt-1 rounded bg-warn-bg px-2 py-1 text-small font-semibold text-[#7a4b00]">{skipTo ? '휴무 (야간 20:00 시작)' : '휴무'} — 설비가 모두 서 있어 배속을 바꿔도 라인이 움직이지 않습니다. {skipTo ? '[20:00으로]를 누르면 바로 시작합니다.' : '[처음으로]를 누르세요.'}</p>}
      <p className="mt-1 text-small text-ink-2">사건 알람이 뜨면 시뮬레이터가 스스로 ×10으로 감속합니다 (API-SIM-02). 다음 날 06:00 넘기기는 없음.</p>
      <div className="mb-1 mt-3 border-t border-line-soft pt-2 font-bold">원본 3D 연출 (설계서에 없음)</div>
      <div className="flex flex-wrap gap-1">
        <button onClick={() => { onClose(); api3d()?.startIntro(); }} className={b}>오프닝</button>
        <button onClick={() => { onClose(); api3d()?.startTour(); }} className={b}>제품 투어</button>
        {([['night', '야간'], ['explode', '분해 보기'], ['holo', '홀로그램'], ['heat', '열화상'], ['flow', '흐름선']] as const).map(([k, l]) => (
          <button key={k} onClick={() => toggle(k)} className={`${b} ${fx[k] ? '!border-brand !bg-brand text-white' : ''}`}>{l}</button>
        ))}
      </div>
      {reset && <ConfirmBox title="시연을 처음으로 되돌릴까요?" okLabel="처음으로" body="10/1 08:00(9/30 끝 상태)으로 돌아갑니다. 이 회차에 화면에서 만든 문서·알림 처리는 새 회차로 바뀌어 보이지 않습니다."
        onOk={() => { setReset(false); call('sim/reset', {}, '처음으로 — 10/1 08:00'); }} onCancel={() => setReset(false)} />}
    </div>
  );
}
