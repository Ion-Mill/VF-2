'use client';
// UI설계서 2.1 [11] AI 비서 사이드바 · [15] 이브 아이콘 · [16] 이브 말풍선, SCR-07 알림 탭, SCR-10 채팅·채팅 기록.
// 채팅 = API-AST-02. 외부 LLM(Claude) 연결을 켜지 않았으면 서버의 "규칙 답"(조회 도구 + 사내 문서 검색)을 쓰고, 답마다 "규칙 답" 표시.
// 겉모양 = mom-assistant-widget (로봇 버튼 · 아이콘 메뉴 · 우측 어두운 창 · 알림 토스트). 위젯 JS는 innerHTML로 그려 React 탭을 못 담아서 CSS만 쓰고 틀을 여기로 옮김.
import { Fragment, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, api, md, simIso, useLocal } from './live';
import { askAssistant, backendChatEnabled } from './assistantApi';
import { LEVEL_VIEW, alarmTitle, hhmm, sevText, type AlertRec, type Level, type Notice } from './model';
import { rankOfAlert, rankOfNotice } from './Briefing';
import RobotIcon from './RobotIcon';
import EveThinking from './EveThinking';
import { canStartNewChat, currentChat, makeNewChatMark, realRows, withNewChat } from './chatLog';
import { carryAlarm } from './carry';

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
// 작은 자리(토스트·창 머리·브리핑·3D 띠)의 이브 = 얼굴만 (헬멧째 시안, 사용자 선택 2026-10-19). 몸 전체를 줄이면 눈이 점이 돼서 표정이 안 보임.
// 표정: 평소 ^ ^ · 새 소식 반짝 눈 · 주의 주황 반쯤 감은 눈 · 긴급 빨강 > < (3D 모델의 눈 모양을 평면으로). 이브 버튼(58px)은 3D 전신 그대로
export type EveFace = 'happy' | 'news' | 'warn' | 'alarm';
export function Robot({ face = 'happy', size }: { face?: EveFace; size: number }) {
  const c = face === 'warn' ? '#FFB020' : face === 'alarm' ? '#FF5A52' : '#B79CFF';
  const eye = (x: number, s: 1 | -1) =>
    face === 'happy' ? <path d={`M${x - 5} 37.5Q${x} 29.5 ${x + 5} 37.5`} fill="none" stroke={c} strokeWidth="2.9" strokeLinecap="round" />
    : face === 'news' ? <><ellipse cx={x} cy={35} rx={3.4} ry={4.8} fill={c} /><circle cx={x + 1.3} cy={33.2} r={1.1} fill="#fff" /></>
    : face === 'warn' ? <path d={`M${x - 4.6} 34.4H${x + 4.6}V35.8Q${x} 40 ${x - 4.6} 35.8Z`} fill={c} transform={`rotate(${-8 * s} ${x} 35)`} />
    : <path d={`M${x + 3.8 * s} 31L${x - 3.4 * s} 35L${x + 3.8 * s} 39`} fill="none" stroke={c} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />;
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" style={{ display: 'block', flexShrink: 0 }}>
      <rect x="4" y="28" width="5" height="12" rx="2.5" fill="#C9D0C6" />
      <rect x="55" y="28" width="5" height="12" rx="2.5" fill="#C9D0C6" />
      <ellipse cx="32" cy="34" rx="25" ry="22" fill="#F6F7F8" stroke="#C3C8CE" strokeWidth="1.2" />
      <path d="M12 25Q32 14 52 25" fill="none" stroke="#D9DDE2" strokeWidth="1.2" />
      <rect x="13.5" y="24" width="37" height="21" rx="10.5" fill="#05070A" />
      <path d="M18 27.5Q26 25.5 34 26.5" fill="none" stroke="#fff" strokeOpacity=".22" strokeWidth="2" strokeLinecap="round" />
      <g style={{ filter: `drop-shadow(0 0 1.6px ${c})` }}>{eye(25, -1)}{eye(39, 1)}</g>
      {(face === 'happy' || face === 'news') && <><ellipse cx="17.5" cy="47" rx="3.1" ry="1.5" fill="#FF8FB0" opacity=".6" /><ellipse cx="46.5" cy="47" rx="3.1" ry="1.5" fill="#FF8FB0" opacity=".6" /></>}
    </svg>
  );
}

export function Eve({ tab, onPick, onClose, badges, bubble, onBubble, brief, onNotice }: {
  tab: EveTab | null; onPick: (t: EveTab) => void; onClose: () => void; badges: Partial<Record<EveTab, number>>;
  bubble: string | null; onBubble: () => void; brief: React.ReactNode; onNotice: (n: Notice) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [later, setLater] = useState<string | null>(null); // [나중에] 누른 말풍선 — 글이 바뀌면 다시 뜸
  const [gl, setGl] = useState(true);
  const [focus, setFocus] = useState<string | null>(null);
  const [slot, setSlot] = useState<HTMLElement | null>(null);   // 머리줄의 [새 채팅] 자리 — 상태를 가진 Chat이 여기에 버튼을 그린다 (createPortal)
  const closed = !tab && !menu;
  const toast = closed && bubble && bubble !== later ? bubble : null;
  const total = badges['알림'] ?? 0;
  const pick = (t: EveTab) => { setMenu(false); setFocus(null); onPick(t); };
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
            <Robot face={toast.startsWith('⚠') ? 'alarm' : 'news'} size={36} />
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
            <Robot size={30} />
            <strong className="ma-panel-title">이브</strong>
            {tab === '채팅' && <span ref={setSlot} className="flex shrink-0 items-center" />}
            <button type="button" className="ma-icon-btn" onClick={onClose} aria-label="창 닫기"><Icon d={['M6 6l12 12M18 6L6 18']} /></button>
          </header>
          <div className="ma-tabs" role="tablist" aria-label="이브 메뉴">
            {EVE_TABS.map((t) => <button key={t} type="button" role="tab" className="ma-tab" aria-selected={tab === t} onClick={() => { setFocus(null); onPick(t); }}>{t}{badge(t, 'ma-tab-badge')}</button>)}
          </div>
          {tab === '채팅' ? <Chat focus={focus} headerSlot={slot} onNewChat={() => setFocus(null)} /> : (
            <div className="ma-body text-[14px] leading-relaxed" role="tabpanel">
              {tab === '채팅 기록' ? <ChatLog onOpen={(at) => { setFocus(at); onPick('채팅'); }} /> : <div className="ma-pad">{tab === '브리핑' ? brief : <AlertsTab onNotice={onNotice} />}</div>}
            </div>
          )}
        </aside>
      )}
      <button type="button" className="ma-fab" aria-expanded={!closed} onClick={() => (tab ? onClose() : setMenu((m) => !m))}
        aria-label={closed ? `이브 메뉴 열기${total ? `, 새 소식 ${total}건` : ''}` : '이브 닫기'}>
        {gl ? <RobotIcon mode={toast ? 1 : 0} size={58} onFail={() => setGl(false)} /> : <Robot face={toast ? 'news' : 'happy'} size={44} />}
        {closed && total > 0 && <span className="ma-fab-badge" aria-hidden="true">{total}</span>}
      </button>
    </div>
  );
}

// ---------- SCR-07 알림 탭 (페이지구조 v3 2.4): 고장·확인 알림과 문서 알림을 한 목록에. 누르면 목록 대신 상세 ----------
type Item = { kind: 'a'; a: AlertRec; n: number } | { kind: 'n'; x: Notice };
// 왼쪽 띠 색: 긴급 빨강 · 주의 주황 · 참고 회색 (Q7)
const BAR: Record<Level, string> = { 긴급: '#E5484D', 주의: '#F5A524', 참고: '#8B98A5' };
const idOf = (it: Item) => (it.kind === 'a' ? it.a.id : it.x.id);
function AlertsTab({ onNotice }: { onNotice: (n: Notice) => void }) {
  const { alerts, myNotices, role, openCard, selectMachine, go, handleNotice, markAlert, openSource, user } = useApp();
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);
  const [plan, setPlan] = useState('');

  // 짧은 반복 묶기: 같은 설비·같은 알람 1분 안 → ×N (DOC-07 10.2)
  const grouped: Item[] = [];
  [...alerts].sort((a, b) => a.ts - b.ts).forEach((a) => {
    const g = grouped.find((x) => x.kind === 'a' && x.a.machine === a.machine && x.a.code === a.code && a.ts - x.a.ts <= 60000 && x.a.handled === a.handled) as { kind: 'a'; a: AlertRec; n: number } | undefined;
    if (g) g.n += 1; else grouped.push({ kind: 'a', a, n: 1 });
  });
  const all: Item[] = [...grouped, ...myNotices.map((x) => ({ kind: 'n' as const, x }))];
  const handledOf = (it: Item) => (it.kind === 'a' ? it.a.handled : it.x.handled);
  const tsOfI = (it: Item) => (it.kind === 'a' ? it.a.ts : it.x.ts);
  const items = all.filter((it) => !onlyOpen || !handledOf(it)).sort((a, b) => tsOfI(b) - tsOfI(a));
  // 알림 폭주: 10분 안 10건 넘으면 띠 (DOC-07 10.3)
  const recent = alerts.filter((a) => SIM.now() - a.ts < 600000).length;
  const chip = (on: boolean) => `h-9 whitespace-nowrap rounded-full border px-3 text-[12px] font-semibold ${on ? 'border-[#B79CFF] bg-[#B79CFF] text-[#1A1F23]' : 'border-slate-300'}`;
  const ab = 'h-11 rounded-full border border-slate-300 px-4 text-[14px] font-semibold hover:bg-slate-50 disabled:text-slate-400';
  const title = (it: Item) => (it.kind === 'a' ? `${MACHINES[it.a.machine].name} ${alarmTitle(it.a.alarm, it.a.code)}${it.n > 1 ? ` ×${it.n}` : ''}` : it.x.ruleName);
  const level = (it: Item) => (it.kind === 'a' ? it.a.level : it.x.level);
  const at = (it: Item) => (it.kind === 'a' ? it.a.time : it.x.at);

  const cur = openId ? all.find((it) => idOf(it) === openId) : undefined;
  if (cur) {
    const lv = level(cur), done = handledOf(cur);
    return (
      <div className="flex flex-col gap-3">
        <button onClick={() => { setOpenId(null); setPlan(''); }} className="w-fit text-[13px] font-semibold underline">← 목록</button>
        <div className="rounded-xl border-l-[6px] bg-white/5 p-3" style={{ borderColor: BAR[lv] }}>
          <div className="text-[12px] font-semibold" style={{ color: TONE[lv] }}>{LEVEL_VIEW[lv].icon} {lv} · {md(at(cur))} {hhmm(at(cur))} · {done ? '처리됨' : '처리 안 됨'}</div>
          <b className="mt-1 block text-[17px] leading-snug">{title(cur)}</b>
          {cur.kind === 'a' ? (<>
            <p className="mt-2">{MACHINES[cur.a.machine].name}({MACHINES[cur.a.machine].op})에서 알람 {cur.a.code}{cur.a.alarm ? ` — ${sevText(cur.a.alarm)}` : ' — 알람 코드집에 없음, 보전 담당자 호출'}.{cur.a.scenario ? ` 사건 ${cur.a.scenario}.` : ''}{cur.a.lot ? ` 로트 ${cur.a.lot}.` : ''}{cur.a.cleared ? ` 설비 알람 ${hhmm(cur.a.cleared)} 해제.` : ''}</p>
            {cur.a.alarm && <p className="mt-1 text-[12px] text-slate-500">관련: <button onClick={() => openSource('DOC-02', cur.a.alarm!.doc02.replace('DOC-02 ', ''))} className="underline">{cur.a.alarm.doc02}</button></p>}
          </>) : (<>
            <p className="mt-2">{cur.x.text}{cur.x.past && <span className="ml-1 text-[11px] text-slate-500">(9월 기록)</span>}</p>
            {cur.x.related && <p className="mt-1 text-[12px] text-slate-500">관련: {cur.x.related}</p>}
            {cur.x.plan && <p className="mt-1 text-[12px]">조치 계획: {cur.x.plan}</p>}
          </>)}
        </div>
        <div className="flex flex-wrap gap-2">
          {cur.kind === 'a' && <button onClick={() => openCard(cur.a.id)} className={ab}>지침카드 열기</button>}
          {cur.kind === 'a' && <button onClick={() => { go('line'); selectMachine(cur.a.machine); }} className={ab}>3D에서 보기</button>}
          {cur.kind === 'a' && !done && <button onClick={() => markAlert([cur.a.id], user.name)} className={ab}>처리 완료</button>}
          {cur.kind === 'n' && cur.x.open && <button onClick={() => onNotice(cur.x)} className={ab}>문서 열기</button>}
          {cur.kind === 'n' && !done && (role === 'MGR' || cur.x.roles.includes(role)) && (<>
            {cur.x.rule === 'REPEAT_ALARM' && <input value={plan} onChange={(e) => setPlan(e.target.value)} placeholder="조치 계획 (필수)" className="h-11 min-w-0 flex-1 rounded-full border border-slate-300 px-4 text-[13px]" />}
            <button disabled={cur.x.rule === 'REPEAT_ALARM' && !plan.trim()} onClick={() => handleNotice(cur.x.id, cur.x.rule === 'REPEAT_ALARM' ? plan : undefined)} className={ab}>처리 완료</button>
          </>)}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        <button onClick={() => setOnlyOpen(true)} className={chip(onlyOpen)}>처리 안 됨 {all.filter((it) => !handledOf(it)).length}</button>
        <button onClick={() => setOnlyOpen(false)} className={chip(!onlyOpen)}>전체</button>
      </div>
      {recent > 10 && <div className="rounded-md bg-[#fff1cc] p-2 text-[13px] font-semibold text-[#7a4b00]">▲ 알림 폭주 — 10분 안 알람 {recent}건</div>}
      {items.length === 0 ? <p className="ma-empty">처리 안 된 알림이 없습니다.</p> : (
        <ul className="flex flex-col gap-2">
          {items.slice(0, 150).map((it) => (
            <li key={idOf(it)}>
              <button onClick={() => setOpenId(idOf(it))} className="flex w-full flex-col rounded-xl border-l-[6px] bg-white/5 px-3 py-2 text-left hover:bg-white/10" style={{ borderColor: BAR[level(it)] }}>
                <span className="flex items-baseline justify-between gap-2"><b className="truncate">{title(it)}</b><span className="shrink-0 text-[12px] text-slate-500">{hhmm(at(it))}</span></span>
                <span className="text-[12px] text-slate-500">{level(it)}{it.kind === 'n' ? ' · 문서·확인 알림' : ` · 알람 ${it.a.code}`}{handledOf(it) ? ' · 처리됨' : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------- SCR-10 채팅 ----------
interface ChatRow { at: string; q: string; a: string; status: string; sources: { doc_no: string; doc_name: string; rev: string; section: string }[]; series?: Record<string, Record<string, number[]>>; newChat?: boolean }   // newChat = "여기서부터 새 대화" 표지 줄 (질문·답 없음, chatLog.ts)
function Chat({ focus, headerSlot, onNewChat }: { focus: string | null; headerSlot: HTMLElement | null; onNewChat: () => void }) {
  const { user, role, screen, selected, openSource } = useApp();
  const [log, setLog] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const send = async (text = q) => {
    if (!text.trim()) return;
    // 직전 알람 이어받기 신호 (carry.ts): 이 질문의 줄을 로그에 더하기 전의 지금 대화로 계산한다. 이어받을지는 서버가 정한다.
    // 채팅 기록에서 열어 본 과거 대화를 보는 중이면 이어받지 않고 새 대화로 보낸다.
    const cur = currentChat(log);
    const alarmKey = focus ? null : carryAlarm(cur);
    const newChat = focus ? true : cur.length === 0;
    setBusy(true); setQ('');
    let row: ChatRow;
    try {
      const r = backendChatEnabled()   // NEXT_PUBLIC_MOM_API가 있으면 백엔드의 비서(외부 LLM)로 — assistantApi.ts. 없으면 옛 길(시연 서버의 규칙 답)
        ? await askAssistant(text, user.id, screen, selected ? MACHINES[selected].eq : null, { alarmKey, newChat })
        : await api<{ answer: string; status: string; sources: ChatRow['sources']; series?: ChatRow['series'] }>('assistant/chat', { question: text, role, user_id: user.id, context: { screen, equipment_id: selected ? MACHINES[selected].eq : null } });
      row = { at: simIso(), q: text, a: r.answer, status: r.status, sources: r.sources ?? [], series: r.series };
    } catch (e) { row = { at: simIso(), q: text, a: '비서 응답 없음 — ' + (e as Error).message, status: '응답 없음', sources: [] }; }
    // 채팅 기록 30일 (FR-MNT-01-01, NFR-DATA-13)
    setLog((l) => [...l.filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5), row]);
    setBusy(false);
  };
  // [새 채팅]: 기록은 한 줄도 지우지 않고 "여기서부터 새 대화" 표지 줄만 더한다 → 채팅 탭은 표지 뒤 줄만 보이고, 이전 대화는 채팅 기록 탭에 그대로 있다 (chatLog.ts)
  const canNew = !busy && canStartNewChat(log, !!focus);   // 답을 기다리는 중에는 끈다 (늦게 온 답이 새 대화에 끼지 않게)
  const startNew = () => { if (!canNew) return; const m = makeNewChatMark(simIso()); setLog((l) => withNewChat(l, m, !!focus)); setQ(''); onNewChat(); input.current?.focus(); };
  // 채팅 기록에서 열면 그 대화가 있는 날 대화 전부, 아니면 지금 대화의 최근 12개
  const today = focus ? realRows(log).filter((x) => md(x.at) === md(focus)) : currentChat(log).slice(-12);
  const ex = role === 'MNT' || role === 'MGR' ? ['VF2-01 MTTR 알려줘', 'VF2-01 센서 추세', '2075 알람 뭐야', '이 화면 설명해 줘'] : ['2075 알람 뭐야', '잠금 표지 순서', '이 화면 설명해 줘', '병목 원인'];
  const body = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = focus && body.current?.querySelector(`[data-at="${focus}"]`);
    if (el) el.scrollIntoView({ block: 'center' }); else if (body.current) body.current.scrollTop = body.current.scrollHeight;
  }, [log.length, busy, focus]);
  return (
    <>
      {headerSlot && createPortal(
        <button type="button" onClick={startNew} disabled={!canNew} aria-label="새 채팅 시작" title="지금 대화를 비우고 새로 시작합니다. 이전 대화는 채팅 기록에 남습니다."
          className="inline-flex h-9 items-center gap-1 rounded-full border border-white/25 px-3 text-[12px] font-bold text-[color:var(--ma-panel-fg)] hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--ma-lime)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent">
          <Icon d={['M12 5v14M5 12h14']} size={15} w={2.4} />새 채팅
        </button>, headerSlot)}
      <div ref={body} className="ma-body text-[14px]" role="tabpanel">
        <div className="ma-pad" aria-live="polite">
          <p className="text-[11px] text-slate-500">{backendChatEnabled() ? '외부 LLM(Claude)이 사내 문서와 정해진 운영 조회 결과로 답합니다. 알람 카드·점검 순서 같은 안전 답은 채팅에서 AI가 쉽게 풀어 쓰며, 잠금·표지 순서처럼 정해진 고정 서식은 풀이 아래에 문서 그대로 함께 붙습니다(풀이가 어긋나면 풀이는 버리고 고정 서식만 보입니다). 알람 카드 화면에서는 문서 원문이 기준이고, 비서가 쉽게 풀어 쓴 문장이 카드 아래에 참고용으로 따로 붙을 수 있으며 그때 점검 순서 문장이 외부로 전송됩니다. 질문과 문서 조각이 외부로 전송됩니다(지금은 가상 데이터).' : '규칙 답 — 외부 LLM(비서) 연결을 켜지 않아 프로그램 숫자와 사내 문서 절을 그대로 보입니다.'} 지금 화면·고른 설비({selected ? MACHINES[selected].name : '없음'})가 질문 배경으로 갑니다.</p>
          {today.length === 0 && !busy && <p className="ma-empty">라인 상황, 알람, 사내 문서 등 무엇이든 물어보세요.</p>}
          {today.map((r, i) => <div key={i} data-at={r.at} className={r.at === focus ? 'rounded-lg ring-2 ring-[#B79CFF]' : ''}><Bubble r={r} openSource={openSource} /></div>)}
          {busy && <EveThinking />}
        </div>
      </div>
      <form className="ma-compose" onSubmit={(e) => { e.preventDefault(); if (!busy) send(); }}>
        <div className="mb-2 flex flex-wrap gap-1">{ex.map((x) => <button key={x} type="button" disabled={busy} onClick={() => send(x)} className="h-9 rounded-full border border-slate-300 px-3 text-[12px]">{x}</button>)}</div>
        <div className="ma-compose-box">
          <label className="ma-sr" htmlFor="ma-input">이브에게 질문</label>
          <input id="ma-input" ref={input} className="ma-input" autoFocus autoComplete="off" value={q} onChange={(e) => setQ(e.target.value)} placeholder="질문 (예: 992 알람 점검 순서)" />
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
  return <svg width={w} height={h} className="inline align-middle"><polyline fill="none" stroke="#7a52f0" strokeWidth="1.5" points={v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 1 - ((x - lo) / r) * (h - 2)}`).join(' ')} /></svg>;
}
function ChatLog({ onOpen }: { onOpen: (at: string) => void }) {
  const { user } = useApp();
  const [log] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const keep = realRows(log).filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5).reverse();
  return (
    <div className="ma-history">
      <p className="ma-history-group">내 채팅 기록 — 30일 보관 · 누르면 채팅에서 다시 엶</p>
      {keep.length === 0 ? <p className="ma-empty">저장된 대화가 없습니다.</p> : keep.map((r, i) => (
        <Fragment key={i}>
          {(i === 0 || md(keep[i - 1].at) !== md(r.at)) && <p className="ma-history-group">{md(r.at)}</p>}
          <button type="button" className="ma-history-item" onClick={() => onOpen(r.at)}>
            <strong>{r.q}</strong><span>{md(r.at)} {hhmm(r.at)}</span>
          </button>
        </Fragment>
      ))}
    </div>
  );
}
