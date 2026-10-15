'use client';
// UI설계서 2.1 [11] AI 비서 사이드바 · [15] 이브 아이콘 · [16] 이브 말풍선, SCR-07 알림 탭, SCR-10 채팅·채팅 기록.
// 채팅 = API-AST-02. 로컬 LLM이 [선택 필요: 기술 회의]라 서버의 "규칙 답"(조회 도구 + 사내 문서 검색)을 쓰고, 답마다 "규칙 답" 표시.
// 겉모양 = mom-assistant-widget (로봇 버튼 · 아이콘 메뉴 · 우측 어두운 창 · 알림 토스트). 위젯 JS는 innerHTML로 그려 React 탭을 못 담아서 CSS만 쓰고 틀을 여기로 옮김.
import { Fragment, useEffect, useRef, useState } from 'react';
import { useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, api, md, simIso, useLocal } from './live';
import { LEVEL_VIEW, alarmTitle, hhmm, sevText, type AlertRec, type Level, type Notice } from './model';
import { rankOfAlert, rankOfNotice } from './Briefing';
import RobotIcon from './RobotIcon';

export type EveTab = '브리핑' | '알림' | '채팅' | '채팅 기록';
export const EVE_TABS: EveTab[] = ['브리핑', '알림', '채팅', '채팅 기록'];
const TAB_ICON: Record<EveTab, string[]> = {
  브리핑: ['M6 3h12v18H6z', 'M9 8h6M9 12h6M9 16h4'],
  알림: ['M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2z', 'M10 20a2 2 0 0 0 4 0'],
  채팅: ['M4 5h16v11H9l-5 4z'],
  '채팅 기록': ['M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0', 'M12 7v5l3 2'],
};
// 어두운 창 위 수준 글자색 (위젯 .ma-tone-*)
const TONE: Record<Level, string> = { 긴급: '#FF8A7E', 주의: '#FFC46B', 참고: '#A9C2FF' };

const Icon = ({ d, size = 18, w = 2 }: { d: string[]; size?: number; w?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d.map((p) => <path key={p} d={p} />)}</svg>
);
// SVG 로봇 = WebGL이 안 될 때·3D 로봇 사진(snap)이 아직 없을 때
function Robot({ alert, size, disc, snap }: { alert?: boolean; size: number; disc?: boolean; snap?: string | null }) {
  const pad = disc ? Math.round(size * 0.16) : 0;
  if (snap) return (
    <span style={{ position: 'relative', display: 'block', width: size, height: size, flexShrink: 0 }}>
      {disc && <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: '#1A1F23' }} />}
      <img src={snap} alt="" style={{ position: 'absolute', inset: pad / 2, width: size - pad, height: size - pad }} />
    </span>
  );
  const eye = (cx: number) => (alert ? <circle cx={cx} cy={32.5} r={4.5} fill="#FFB020" /> : <rect x={cx - 2.8} y={28} width={5.6} height={9} rx={2.8} fill="#C8F03C" />);
  return (
    <span style={{ position: 'relative', display: 'block', width: size, height: size, flexShrink: 0 }}>
      {disc && <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: '#1A1F23' }} />}
      <svg viewBox="0 0 64 64" aria-hidden="true" style={{ position: 'absolute', inset: pad, width: size - pad * 2, height: size - pad * 2 }}>
        <line x1="32" y1="8" x2="32" y2="15" stroke="#C9D0C6" strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="32" cy="7" r="3.4" fill="#C8F03C" />
        <rect x="5" y="28" width="6.5" height="14" rx="2.6" fill="#C9D0C6" />
        <rect x="52.5" y="28" width="6.5" height="14" rx="2.6" fill="#C9D0C6" />
        <rect x="9" y="15" width="46" height="39" rx="13" fill="#F2F4EF" />
        <rect x="15" y="23.5" width="34" height="18" rx="9" fill="#14181B" />
        <rect x="27" y="46.5" width="10" height="2.6" rx="1.3" fill="#C9D0C6" />
        {eye(24.5)}{eye(39.5)}
      </svg>
    </span>
  );
}

export function Eve({ tab, onPick, onClose, badges, bubble, onBubble, brief, onNotice }: {
  tab: EveTab | null; onPick: (t: EveTab) => void; onClose: () => void; badges: Partial<Record<EveTab, number>>;
  bubble: string | null; onBubble: () => void; brief: React.ReactNode; onNotice: (n: Notice) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [later, setLater] = useState<string | null>(null); // [나중에] 누른 말풍선 — 글이 바뀌면 다시 뜸
  const [gl, setGl] = useState(true), [snap, setSnap] = useState<string | null>(null);
  const closed = !tab && !menu;
  const toast = closed && bubble && bubble !== later ? bubble : null;
  const total = EVE_TABS.reduce((s, t) => s + (badges[t] ?? 0), 0);
  const pick = (t: EveTab) => { setMenu(false); onPick(t); };
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { setMenu(false); onClose(); } };
    document.addEventListener('keydown', k);
    return () => document.removeEventListener('keydown', k);
  }, [onClose]);
  const badge = (t: EveTab, cls: string) => (badges[t] ? <span className={cls} aria-label={`새 소식 ${badges[t]}건`}>{badges[t]}</span> : null);

  return (
    <div className={`ma-root${tab ? ' is-panel' : ''}`}>
      {toast && (
        <div className="ma-toast ma-rise" role="status">
          <button type="button" className="ma-toast-main" onClick={onBubble}>
            <Robot alert size={36} disc snap={snap} />
            <span className="ma-toast-text"><span className="ma-toast-time ma-mono">이브</span><strong className="ma-toast-title">{toast}</strong></span>
          </button>
          <div className="ma-actions">
            <button type="button" className="ma-btn ma-btn-primary" onClick={onBubble}>열기</button>
            <button type="button" className="ma-btn ma-btn-ghost" onClick={() => setLater(toast)}>나중에</button>
          </div>
        </div>
      )}
      {menu && !tab && (
        <div className="ma-menu" role="menu" aria-label="이브 메뉴">
          {EVE_TABS.map((t, i) => (
            <button key={t} type="button" role="menuitem" className="ma-menu-item ma-rise" style={{ animationDelay: `${i * 50}ms` }} onClick={() => pick(t)}>
              <span className="ma-menu-label">{t}</span>
              <span className="ma-menu-icon"><Icon d={TAB_ICON[t]} size={20} />{badge(t, 'ma-menu-badge')}</span>
            </button>
          ))}
        </div>
      )}
      {tab && (
        <aside className="ma-panel ma-side" aria-label="이브">
          <header className="ma-panel-head">
            <Robot size={30} disc snap={snap} />
            <strong className="ma-panel-title">이브 · {tab}</strong>
            <button type="button" className="ma-icon-btn" onClick={onClose} aria-label="창 닫기"><Icon d={['M6 6l12 12M18 6L6 18']} /></button>
          </header>
          <div className="ma-tabs" role="tablist" aria-label="이브 메뉴">
            {EVE_TABS.map((t) => <button key={t} type="button" role="tab" className="ma-tab" aria-selected={tab === t} onClick={() => onPick(t)}>{t}{badge(t, 'ma-tab-badge')}</button>)}
          </div>
          {tab === '채팅' ? <Chat /> : (
            <div className="ma-body text-[14px] leading-relaxed" role="tabpanel">
              {tab === '채팅 기록' ? <ChatLog /> : <div className="ma-pad">{tab === '브리핑' ? brief : <AlertsTab onNotice={onNotice} />}</div>}
            </div>
          )}
        </aside>
      )}
      <button type="button" className="ma-fab" aria-expanded={!closed} onClick={() => (tab ? onClose() : setMenu((m) => !m))}
        aria-label={closed ? `이브 메뉴 열기${total ? `, 새 소식 ${total}건` : ''}` : '이브 닫기'}>
        {gl ? <RobotIcon mode={toast ? 1 : 0} size={58} onSnap={setSnap} onFail={() => setGl(false)} /> : <Robot alert={!!toast} size={44} />}
        {closed && total > 0 && <span className="ma-fab-badge" aria-hidden="true">{total}</span>}
      </button>
    </div>
  );
}

// ---------- SCR-07 알림 목록 ----------
type Item = { kind: 'a'; a: AlertRec; n: number } | { kind: 'n'; x: Notice };
function AlertsTab({ onNotice }: { onNotice: (n: Notice) => void }) {
  const { alerts, myNotices, role, openCard, selectMachine, go, handleNotice, openSource, user } = useApp();
  const [col, setCol] = useState<'고장·확인' | '문서'>('고장·확인');
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [lv, setLv] = useState<Level | ''>('');
  const [mach, setMach] = useState('');
  const [byRank, setByRank] = useState(false);
  const [plan, setPlan] = useState<Record<string, string>>({});
  const listN = myNotices.filter((n) => n.delivery === 'LIST'), docN = myNotices.filter((n) => n.delivery === 'BUBBLE');

  // 짧은 반복 묶기: 같은 설비·같은 알람 1분 안 → ×N (DOC-07 10.2)
  const grouped: Item[] = [];
  [...alerts].sort((a, b) => a.ts - b.ts).forEach((a) => {
    const g = grouped.find((x) => x.kind === 'a' && x.a.machine === a.machine && x.a.code === a.code && a.ts - x.a.ts <= 60000 && x.a.handled === a.handled) as { kind: 'a'; a: AlertRec; n: number } | undefined;
    if (g) g.n += 1; else grouped.push({ kind: 'a', a, n: 1 });
  });
  let items: Item[] = [...grouped, ...listN.map((x) => ({ kind: 'n' as const, x }))];
  items = items.filter((it) => {
    const handled = it.kind === 'a' ? it.a.handled : it.x.handled, level = it.kind === 'a' ? it.a.level : it.x.level, m = it.kind === 'a' ? it.a.machine : it.x.machine;
    return (!onlyOpen || !handled) && (!lv || level === lv) && (!mach || m === mach);
  });
  const tsOfI = (it: Item) => (it.kind === 'a' ? it.a.ts : it.x.ts), rk = (it: Item) => (it.kind === 'a' ? rankOfAlert(it.a) : rankOfNotice(it.x));
  items.sort((a, b) => (byRank ? rk(a).localeCompare(rk(b)) || tsOfI(a) - tsOfI(b) : tsOfI(b) - tsOfI(a)));
  // 알림 폭주: 10분 안 10건 넘으면 묶음 1건 (DOC-07 10.3)
  const recent = alerts.filter((a) => SIM.now() - a.ts < 600000).length;
  const openCount = alerts.filter((a) => !a.handled).length + listN.filter((n) => !n.handled).length;
  const chip = (on: boolean) => `h-9 whitespace-nowrap rounded-full border px-3 text-[12px] font-semibold ${on ? 'border-[#C8F03C] bg-[#C8F03C] text-[#1A1F23]' : 'border-slate-300'}`;
  const ab = 'h-10 rounded-md border border-slate-300 px-3 text-[13px] font-semibold hover:bg-slate-50';

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-1">
        <button onClick={() => setCol('고장·확인')} className={chip(col === '고장·확인')}>고장·확인 알림 {openCount}건</button>
        <button onClick={() => setCol('문서')} className={chip(col === '문서')}>문서 알림 {docN.filter((d) => !d.handled).length}건</button>
      </div>
      {col === '문서' ? (
        docN.length === 0 ? <p className="text-slate-400">문서 알림이 없습니다.</p> : (
          <ul className="flex flex-col gap-2">
            {[...docN].sort((a, b) => Number(a.handled) - Number(b.handled) || b.ts - a.ts).map((d) => (
              <li key={d.id} className="rounded-lg border border-slate-300 p-2">
                <div className="flex items-baseline justify-between gap-2"><span className="font-bold" style={{ color: TONE[d.level] }}>{LEVEL_VIEW[d.level].icon} {d.level} · {md(d.at)} {hhmm(d.at)} · {d.ruleName}</span><span className="text-[11px] text-slate-500">{d.handled ? `처리됨 (${d.handledBy})` : '처리 안 됨'}</span></div>
                <div>{d.text}</div>
                {d.open && <button onClick={() => onNotice(d)} className={`${ab} mt-1`}>문서 열기</button>}
              </li>
            ))}
          </ul>
        )
      ) : (<>
        {recent > 10 && <div className="rounded-md bg-[#fff1cc] p-2 text-[13px] font-semibold text-[#7a4b00]">▲ 알림 폭주 — 10분 안 알람 {recent}건 (묶어서 보임)</div>}
        <div className="flex flex-wrap items-center gap-1">
          <button onClick={() => setOnlyOpen(true)} className={chip(onlyOpen)}>처리 안 됨</button>
          <button onClick={() => setOnlyOpen(false)} className={chip(!onlyOpen)}>전체</button>
          {(['긴급', '주의', '참고'] as Level[]).map((l) => <button key={l} onClick={() => setLv(lv === l ? '' : l)} className={chip(lv === l)}>{LEVEL_VIEW[l].icon} {l}</button>)}
          <select value={mach} onChange={(e) => setMach(e.target.value)} className="h-9 rounded-full border border-slate-300 px-2 text-[12px]"><option value="">설비 전체</option>{Object.entries(MACHINES).map(([k, m]) => <option key={k} value={k}>{m.name}</option>)}</select>
        </div>
        <div className="flex items-center gap-1 text-[12px]">정렬
          <button onClick={() => setByRank(false)} className={chip(!byRank)}>최근 순</button>
          <button onClick={() => setByRank(true)} className={chip(byRank)}>보고 순위 순</button>
          <span className="ml-auto text-slate-500">전체 {items.length}건</span>
        </div>
        {items.length === 0 ? <p className="text-slate-400">처리 안 된 알림이 없습니다.</p> : (
          <ul className="flex flex-col gap-2">
            {items.slice(0, 120).map((it) => {
              if (it.kind === 'a') {
                const a = it.a, v = LEVEL_VIEW[a.level], old = a.level === '주의' && !a.handled && SIM.now() - a.ts > 864e5;
                return (
                  <li key={a.id} className="rounded-lg border border-slate-300 p-2">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-bold" style={{ color: TONE[a.level] }}>{v.icon} {a.level} · {hhmm(a.time)} · {MACHINES[a.machine].name} · 알람 {a.code}{a.alarm ? ` (${sevText(a.alarm)})` : ''}{it.n > 1 ? ` ×${it.n} (1분 안)` : ''}</span>
                      <span className="shrink-0 text-[11px] text-slate-500">{a.handled ? `처리됨${a.handledBy ? ` (${a.handledBy})` : ''}` : '처리 안 됨'}</span>
                    </div>
                    <div>{MACHINES[a.machine].name}에서 {alarmTitle(a.alarm, a.code)}{a.scenario ? ` · 사건 ${a.scenario}` : ''}{a.cleared ? ' · 설비 알람 해제됨' : ''}{old && <span className="ml-1 rounded bg-[#fff1cc] px-1 text-[11px] text-[#7a4b00]">24시간 넘음</span>}</div>
                    {a.alarm && <div className="text-[12px] text-slate-500">관련: <button onClick={() => openSource('DOC-02', a.alarm!.doc02.replace('DOC-02 ', ''))} className="underline">{a.alarm.doc02}</button>{a.alarm.doc03[0] && <> · <button onClick={() => { const m = a.alarm!.doc03[0].match(/(DOC-\d+)\s+§?([\d.]+)/); if (m) openSource(m[1], m[2]); }} className="underline">{a.alarm.doc03[0]}</button></>}</div>}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <button onClick={() => openCard(a.id)} className={ab}>지침카드</button>
                      <button onClick={() => { go('line'); selectMachine(a.machine); }} className={ab}>3D 라인 뷰</button>
                      <span className="text-[11px] text-slate-500">{a.kind === 'guide' ? '처리: 작업자가 고치면 (알람 해제)' : '처리: 작업기록서·간이 작업기록 확정 때 자동'}</span>
                    </div>
                  </li>
                );
              }
              const n = it.x, v = LEVEL_VIEW[n.level], old = n.level === '주의' && !n.handled && SIM.now() - n.ts > 864e5;
              const isRepeat = n.rule === 'REPEAT_ALARM';
              const canHandle = !n.handled && (role === 'MGR' || n.roles.includes(role));
              return (
                <li key={n.id} className="rounded-lg border border-slate-300 p-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-bold" style={{ color: TONE[n.level] }}>{v.icon} {n.level} · {md(n.at)} {hhmm(n.at)} · {n.ruleName}{n.count ? ` ×${n.count}` : ''}</span>
                    <span className="shrink-0 text-[11px] text-slate-500">{n.handled ? `처리됨 (${n.handledBy})` : '처리 안 됨'}</span>
                  </div>
                  <div>{n.text}{n.past && <span className="ml-1 text-[11px] text-slate-500">(9월 기록)</span>}{old && <span className="ml-1 rounded bg-[#fff1cc] px-1 text-[11px] text-[#7a4b00]">24시간 넘음</span>}</div>
                  {n.related && <div className="text-[12px] text-slate-500">관련: {n.related}</div>}
                  {n.plan && <div className="text-[12px]">조치 계획: {n.plan}</div>}
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {n.open && <button onClick={() => onNotice(n)} className={ab}>화면 열기</button>}
                    {n.machine && <button onClick={() => { go('line'); selectMachine(n.machine!); }} className={ab}>3D 라인 뷰</button>}
                    {canHandle && isRepeat && <input value={plan[n.id] ?? ''} onChange={(e) => setPlan({ ...plan, [n.id]: e.target.value })} placeholder="조치 계획 (필수)" className="h-10 min-w-0 flex-1 rounded-md border border-slate-300 px-2 text-[13px]" />}
                    {canHandle && <button disabled={isRepeat && !(plan[n.id] ?? '').trim()} onClick={() => handleNotice(n.id, isRepeat ? plan[n.id] : undefined)} className={`${ab} disabled:text-slate-400`}>처리</button>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-[11px] text-slate-500">처리 칸의 역할만 [처리]가 보입니다 ({user.name} · {role}). 알림은 시연 회차마다 이 브라우저에 남습니다.</p>
      </>)}
    </div>
  );
}

// ---------- SCR-10 채팅 ----------
interface ChatRow { at: string; q: string; a: string; status: string; sources: { doc_no: string; doc_name: string; rev: string; section: string }[]; series?: Record<string, Record<string, number[]>> }
function Chat() {
  const { user, role, screen, selected, openSource } = useApp();
  const [log, setLog] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async (text = q) => {
    if (!text.trim()) return;
    setBusy(true); setQ('');
    let row: ChatRow;
    try {
      const r = await api<{ answer: string; status: string; sources: ChatRow['sources']; series?: ChatRow['series'] }>('assistant/chat', { question: text, role, user_id: user.id, context: { screen, equipment_id: selected ? MACHINES[selected].eq : null } });
      row = { at: simIso(), q: text, a: r.answer, status: r.status, sources: r.sources ?? [], series: r.series };
    } catch (e) { row = { at: simIso(), q: text, a: '비서 응답 없음 — ' + (e as Error).message, status: '응답 없음', sources: [] }; }
    // 채팅 기록 30일 (FR-MNT-01-01, NFR-DATA-13)
    setLog((l) => [...l.filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5), row]);
    setBusy(false);
  };
  const today = log.slice(-12);
  const ex = role === 'MNT' || role === 'MGR' ? ['VF2-01 MTTR 알려줘', 'VF2-01 센서 추세', '2075 알람 뭐야', '이 화면 설명해 줘'] : ['2075 알람 뭐야', '잠금 표지 순서', '이 화면 설명해 줘', '병목 원인'];
  const body = useRef<HTMLDivElement>(null);
  useEffect(() => { if (body.current) body.current.scrollTop = body.current.scrollHeight; }, [log.length, busy]);
  return (
    <>
      <div ref={body} className="ma-body text-[14px]" role="tabpanel">
        <div className="ma-pad" aria-live="polite">
          <p className="text-[11px] text-slate-500">규칙 답 — 로컬 LLM 연결 전이라 프로그램 숫자와 사내 문서 절을 그대로 보입니다. 지금 화면·고른 설비({selected ? MACHINES[selected].name : '없음'})가 질문 배경으로 갑니다.</p>
          {today.length === 0 && !busy && <p className="ma-empty">라인 상황, 알람, 사내 문서 등 무엇이든 물어보세요.</p>}
          {today.map((r, i) => <Bubble key={i} r={r} openSource={openSource} />)}
          {busy && <p className="ma-msg-bot ma-typing">답변을 만드는 중…</p>}
        </div>
      </div>
      <form className="ma-compose" onSubmit={(e) => { e.preventDefault(); if (!busy) send(); }}>
        <div className="mb-2 flex flex-wrap gap-1">{ex.map((x) => <button key={x} type="button" disabled={busy} onClick={() => send(x)} className="h-9 rounded-full border border-slate-300 px-3 text-[12px]">{x}</button>)}</div>
        <div className="ma-compose-box">
          <label className="ma-sr" htmlFor="ma-input">이브에게 질문</label>
          <input id="ma-input" className="ma-input" autoFocus autoComplete="off" value={q} onChange={(e) => setQ(e.target.value)} placeholder="질문 (예: 992 알람 점검 순서)" />
          <button type="submit" className="ma-send" disabled={busy} aria-label="보내기"><Icon d={['M12 19V5M5 12l7-7 7 7']} w={2.4} /></button>
        </div>
      </form>
    </>
  );
}
function Bubble({ r, openSource }: { r: ChatRow; openSource: (d: string, s: string) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="ma-msg-user">{r.q}</div>
      <div className="text-[12px] text-slate-500">{md(r.at)} {hhmm(r.at)} · 이브 · {r.status === 'ok' ? '규칙 답' : r.status}</div>
      <p className="ma-msg-bot">{r.a}</p>
      {r.series && Object.entries(r.series).map(([eq, s]) => <div key={eq} className="text-[12px]">{eq} 최근 60분: {Object.entries(s).slice(0, 3).map(([k, v]) => <span key={k} className="mr-2">{k} <Spark v={v} /></span>)}</div>)}
      {r.sources.length > 0 && <div className="flex flex-wrap gap-1 text-[12px]">출처: {r.sources.map((s, i) => <button key={i} type="button" onClick={() => openSource(s.doc_no, s.section)} className="underline">{s.doc_name} {s.doc_no} {s.rev} §{s.section}</button>)}</div>}
    </div>
  );
}
export function Spark({ v, w = 80, h = 18 }: { v: number[]; w?: number; h?: number }) {
  if (v.length < 2) return <span>—</span>;
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
  return <svg width={w} height={h} className="inline align-middle"><polyline fill="none" stroke="#0f9fbd" strokeWidth="1.5" points={v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 1 - ((x - lo) / r) * (h - 2)}`).join(' ')} /></svg>;
}
function ChatLog() {
  const { user, openSource } = useApp();
  const [log] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const [openI, setOpenI] = useState<number | null>(null);
  const keep = log.filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5).reverse();
  return (
    <div className="ma-history">
      <p className="ma-history-group">내 채팅 기록 — 30일 보관, 본인 것만 (이 브라우저)</p>
      {keep.length === 0 ? <p className="ma-empty">저장된 대화가 없습니다.</p> : keep.map((r, i) => (
        <Fragment key={i}>
          {(i === 0 || md(keep[i - 1].at) !== md(r.at)) && <p className="ma-history-group">{md(r.at)}</p>}
          <button type="button" className="ma-history-item" aria-expanded={openI === i} onClick={() => setOpenI(openI === i ? null : i)}>
            <strong>{r.q}</strong><span>{hhmm(r.at)} · {r.status === 'ok' ? '규칙 답' : r.status}</span>
          </button>
          {openI === i && <div className="px-2 pb-3"><Bubble r={r} openSource={openSource} /></div>}
        </Fragment>
      ))}
    </div>
  );
}
