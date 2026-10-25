'use client';
// 시연 조작판 (UI설계서 2.1 [14], 9.6) — 시연 모드에서만. 사건 버튼 = API-SIM-01, 시계 = API-SIM-02, 처음으로 = API-SIM-03.
// 사건은 누른 때(시연 시계 지금) 시작하고, 시각·숫자는 그때의 계산 값이다 (설계서 7장).
// 보이는 조작은 시연 서버 프로필의 controls (영상용 = 전부, 최종용 = 없음 · 주소 끝 ?dev=1에서만 발표자 [처음으로], 2026-10-25)
import { useState } from 'react';
import { SHIFT_H, hh } from './data';
import { api, useProfile, type Twin } from './live';
import { ConfirmBox } from './Safety';

const EVENTS: [string, string, string][] = [
  ['S1', 'S1 충돌', 'VF2-01 축 부하 급상승 → 992 정지 알람 (작업기록서 확정까지 고장)'],
  ['S3', 'S3 공구', 'VF2-01 T05가 빨리 닳음 → 90% 교체 알림'],
  ['S4', 'S4 공기압', 'VF2-01 공기 압력이 서서히 떨어짐 → 120 (자동 복귀)'],
  ['S6', 'S6 정비', 'VF2-02 예방 정비 90분 → OP-30 1대 가동 → 재공 증가·병목'],
  // S7 선조치 기록은 숨김 — 백엔드 사건 넣기가 S1·S3·S4·S6만 받아 누르면 422 (2026-10-25 사용자 결정)
];
const ALL = ['speed', 'pause', 'skip', 'buttons', 'reset'];
const b = 'h-11 rounded-ctl border border-line px-3 text-small font-semibold hover:bg-tile disabled:text-ink-3';

// 최종용 발표자 [처음으로]: 시연 서버에 직접, 발표자 키는 누를 때 입력받아 이 요청에만 싣는다 (화면 코드·저장소에 두지 않음)
async function presenterReset(key: string) {
  const r = await fetch('/sim-api/sim/reset', { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json', 'X-Presenter-Key': key }, body: '{}' });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.message ?? `처음으로 실패 (${r.status})`);
}

export default function SimPanel({ twin, refresh, toast, api3d, onClose }: { twin: Twin | null; refresh: () => void; toast: (m: string) => void; api3d: () => any; onClose: () => void }) {
  const [reset, setReset] = useState(false);
  const [key, setKey] = useState('');
  const [fx, setFx] = useState<Record<string, boolean>>({});
  const prof = useProfile();
  const ctl = prof?.controls ?? ALL;            // 프로필을 못 읽으면 예전처럼 전부
  const has = (k: string) => ctl.includes(k);
  const dev = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('dev') === '1';
  const devReset = !has('reset') && dev;
  const call = async (path: string, body: unknown, ok: string) => {
    try { await api(path, body); toast(ok); refresh(); } catch (e) { toast((e as Error).message); }
  };
  const c = twin?.clock;
  const locked = c?.can_control === false;      // 시연 조작은 진행자만 (백엔드 MOM_SIM_CONTROL_USERS, 2026-10-24)
  // 교대가 끝난 뒤(18:00~21:00, 06:00~09:00)는 휴무(계획 정지) — 설비가 다 서 있어 배속을 바꿔도 3D가 안 움직인다
  const off = !!twin && !!c && c.sim_at >= twin.shift.end_at;
  const dayEnd = prof?.shifts.DAY.end ?? `${hh(SHIFT_H.dayEnd)}:00`, nightStart = prof?.shifts.NIGHT.start ?? `${hh(SHIFT_H.nightStart)}:00`;
  // 넘기기 이름은 시각 대신 TODAY_DAY_END · TODAY_NIGHT_START (생성기 realtime.py, 2026-10-24)
  const skipTo = twin?.shift.shift_type === 'DAY' ? (off ? { to: 'TODAY_NIGHT_START', at: nightStart, ok: '야간 교대 시작' } : { to: 'TODAY_DAY_END', at: dayEnd, ok: '남은 주간 교대를 만듦' }) : null;
  const clockCtl = has('speed') || has('pause') || has('skip') || has('reset');
  const fxs = ctl.length ? ([['night', '야간'], ['explode', '분해 보기'], ['holo', '홀로그램'], ['heat', '열화상'], ['flow', '흐름선']] as const) : [];   // 최종용은 제품 투어만 (오프닝은 로그인해 들어올 때 저절로, 2026-10-25)
  const toggle = (k: string) => { const n = !fx[k]; setFx({ ...fx, [k]: n }); api3d()?.setState((s: any) => (k === 'night' || k === 'explode' ? { [k]: n } : { layers: { ...s.layers, [k]: n } })); };
  return (
    <div className="absolute right-0 top-[48px] z-30 w-[400px] rounded-tile border border-line bg-white p-3 text-small shadow-lg">
      <div className="mb-1 flex items-center justify-between"><b>{has('buttons') ? '사건 버튼' : '3D 연출'}</b><button onClick={onClose} className="h-8 px-2 text-small">닫기</button></div>
      {ctl.length > 0 && !twin && <p className="text-ink-2">시연 데이터 서버에 연결되지 않았습니다.</p>}
      {has('buttons') && <div className="flex flex-col gap-1">
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
      </div>}
      {clockCtl && <>
        <div className="mt-3 border-t border-line-soft pt-2 font-bold">시연 시계 {c ? `· ${c.sim_at.slice(11, 16)} ×${c.speed}${c.paused ? ' ⏸' : ''}` : ''}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {has('speed') && [180, 60, 10, 1].map((s) => <button key={s} disabled={!twin || locked} onClick={() => call('sim/clock', { speed: s }, `배속 ×${s}`)} className={`${b} ${c?.speed === s ? 'border-brand bg-tile' : ''}`}>×{s}</button>)}
          {has('pause') && <button disabled={!twin || locked} onClick={() => call('sim/clock', { paused: !c?.paused }, c?.paused ? '다시 시작' : '일시정지 — 3D 움직임도 멈춤')} className={b}>{c?.paused ? '▶ 다시 시작' : '⏸ 일시정지'}</button>}
          {has('skip') && <button disabled={!skipTo || locked} onClick={() => skipTo && call('sim/clock', { skip: skipTo.to }, `${skipTo.at}으로 넘김 — ${skipTo.ok}`)} className={b}>{skipTo ? `${skipTo.at}으로` : '넘기기 없음'}</button>}
          {has('reset') && <button disabled={!twin || locked} onClick={() => setReset(true)} className={b}>처음으로</button>}
        </div>
        {locked && <p className="mt-1 rounded bg-tile px-2 py-1 text-small font-semibold text-ink-2">시연 조작(사건·시계·처음으로)은 진행자만 할 수 있습니다. 모두가 같은 공장을 봅니다.</p>}
        {off && <p className="mt-1 rounded bg-warn-bg px-2 py-1 text-small font-semibold text-[#7a4b00]">{skipTo ? `휴무 (야간 ${skipTo.at} 시작)` : '휴무'} — 설비가 모두 서 있어 배속을 바꿔도 라인이 움직이지 않습니다. {skipTo && has('skip') ? `[${skipTo.at}으로]를 누르면 바로 시작합니다.` : '[처음으로]를 누르세요.'}</p>}
        {has('speed') && <p className="mt-1 text-small text-ink-2">사건 알람이 뜨면 시뮬레이터가 스스로 ×10으로 감속합니다 (API-SIM-02). 다음 날 아침으로 넘기기는 없음.</p>}
      </>}
      {devReset && <>
        <div className="mt-3 border-t border-line-soft pt-2 font-bold">발표자 · 처음으로</div>
        <div className="mt-1 flex gap-1">
          <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="발표자 키" aria-label="발표자 키" autoComplete="off" className="h-11 min-w-0 flex-1 rounded-ctl border border-line px-3" />
          <button disabled={!key} onClick={() => setReset(true)} className={b}>처음으로</button>
        </div>
      </>}
      <div className={`mb-1 border-line-soft font-bold ${ctl.length || devReset ? 'mt-3 border-t pt-2' : ''}`}>원본 3D 연출 (설계서에 없음)</div>
      <div className="flex flex-wrap gap-1">
        <button onClick={() => { onClose(); api3d()?.startTour(); }} className={b}>제품 투어</button>
        {fxs.map(([k, l]) => (
          <button key={k} onClick={() => toggle(k)} className={`${b} ${fx[k] ? '!border-brand !bg-brand text-white' : ''}`}>{l}</button>
        ))}
      </div>
      {reset && <ConfirmBox title="시연을 처음으로 되돌릴까요?" okLabel="처음으로" body={devReset ? '시각은 그대로 두고, 화면에서 사람이 한 조작(문서·알림 처리)을 지웁니다. 모두의 화면이 새 회차로 바뀝니다.' : '시연 시작 시각(앞 기록이 끝난 상태)으로 돌아갑니다. 이 회차에 화면에서 만든 문서·알림 처리는 새 회차로 바뀌어 보이지 않습니다.'}
        onOk={() => {
          setReset(false);
          if (!devReset) { call('sim/reset', {}, '처음으로 — 시연 시작 시각'); return; }
          presenterReset(key).then(() => { setKey(''); toast('처음으로 — 사람 조작을 지움'); refresh(); }).catch((e: Error) => toast(e.message));
        }} onCancel={() => setReset(false)} />}
    </div>
  );
}
