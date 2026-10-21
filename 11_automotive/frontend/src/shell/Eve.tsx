'use client';
// UI설계서 2.1 [11] AI 비서 사이드바 · [15] 이브 아이콘 · [16] 이브 말풍선, SCR-07 알림 탭, SCR-10 채팅·채팅 기록.
// 채팅 = API-AST-02. 외부 LLM(Claude) 연결을 켜지 않았으면 서버의 "규칙 답"(조회 도구 + 사내 문서 검색)을 쓰고, 답마다 "규칙 답" 표시.
// 겉모양 = mom-assistant-widget (로봇 버튼 · 아이콘 메뉴 · 우측 창 · 알림 토스트). 탭 내용 배치는 2026-10-20 사용자 선택: 브리핑·채팅 기록 G안, 알림 = 팀원 시안 C(시간 흐름), 채팅 첫 화면 = 팀원 새 채팅 시안(3D 이브). 위젯 JS는 innerHTML로 그려 React 탭을 못 담아서 CSS만 쓰고 틀을 여기로 옮김.
import { Fragment, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, api, md, simIso, useLocal } from './live';
import { VOICE_OFF, VoiceFail, askAssistant, backendChatEnabled, fetchChatLog, fetchVoiceStatus, transcribeAudio, type VoiceStatus } from './assistantApi';
import { micSupported, useMic, voiceMessage } from './voiceInput';
import { LEVEL_VIEW, alarmTitle, hhmm, type AlertRec, type Level, type Notice } from './model';
import { alarmSentence } from './alarmText';
import { useAlarmText } from './assistText';
import { rankOfAlert, rankOfNotice } from './Briefing';
import RobotIcon from './RobotIcon';
import EveThinking from './EveThinking';
import { PENDING_GIVEUP_MS, canStartNewChat, currentChat, isFocusRow, lastChatId, makeNewChatMark, mergeServerLog, resolvePending, sessionOf, settlePending, withNewChat, type FocusRef } from './chatLog';
import { carryAlarm } from './carry';
import { suggestChips } from './chips';
import { Bubble, HistoryItem, Spark, Typing, type ChatRow } from './ChatBubble';

export { Spark };   // 옛 가져오기 경로 유지 (Spark는 ChatBubble.tsx로 옮겼다)

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

export function Eve({ tab, quick: showQuick, onPick, onClose, badges, bubble, bubbleKey, onBubble, brief, onNotice }: {
  tab: EveTab | null; quick: boolean; onPick: (t: EveTab) => void; onClose: () => void; badges: Partial<Record<EveTab, number>>;
  bubble: string | null; bubbleKey?: number; onBubble: () => void; brief: React.ReactNode; onNotice: (n: Notice) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [later, setLater] = useState<string | null>(null); // [나중에] 누른 말풍선 — 글이 바뀌면 다시 뜸
  useEffect(() => { setLater(null); }, [bubbleKey]);   // 알림 미리보기를 다시 누르면 [나중에]로 숨긴 말풍선도 다시 뜬다
  const [gl, setGl] = useState(true);
  const [focus, setFocus] = useState<FocusRef | null>(null);   // 채팅 기록에서 눌러 연 줄 — 그 줄이 속한 대화만 채팅 탭에 보인다
  const [slot, setSlot] = useState<HTMLElement | null>(null);   // 머리줄의 [새 채팅] 자리 — 상태를 가진 Chat이 여기에 버튼을 그린다 (createPortal)
  const [ask, setAsk] = useState<string | null>(null);          // 이브 버튼 옆 작은 채팅창에서 보낸 질문 — 채팅 탭이 열리면 바로 보낸다
  const [quick, setQuick] = useState('');
  // 이브 버튼 끌어 옮기기 (사용자 요청 2026-10-21): 버튼·작은 채팅창·메뉴·말풍선을 같이 옮긴다. 저장하지 않아 새로 열면 늘 오른쪽 아래 기본 자리
  // shortcut: 창 크기를 줄이면 옮긴 버튼이 화면 밖에 남을 수 있음, 그런 일이 잦으면 resize 때 다시 가둘 것
  const [off, setOff] = useState({ x: 0, y: 0 });
  const drag = useRef<{ px: number; py: number; ox: number; oy: number; l: number; t: number; r: number; b: number; moved: boolean } | null>(null);
  const moved = useRef(false);
  const shift = { translate: `${off.x}px ${off.y}px` } as React.CSSProperties;
  const onDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect(), m = 8;
    drag.current = { px: e.clientX, py: e.clientY, ox: off.x, oy: off.y, l: m - r.left, t: m - r.top, r: innerWidth - m - r.right, b: innerHeight - m - r.bottom, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = drag.current; if (!d) return;
    const dx = e.clientX - d.px, dy = e.clientY - d.py;
    if (!d.moved && Math.hypot(dx, dy) < 6) return;   // 6px 안쪽 흔들림은 그냥 누름
    d.moved = true;
    setOff({ x: d.ox + Math.min(d.r, Math.max(d.l, dx)), y: d.oy + Math.min(d.b, Math.max(d.t, dy)) });
  };
  const onUp = () => { moved.current = !!drag.current?.moved; drag.current = null; };
  const closed = !tab && !menu;
  // 한 번 열린 창은 닫아도 지우지 않고 숨기기만 한다 — 그래야 질문을 보낸 뒤 창을 닫았다 열어도 질문·답이 이어진다 (2026-10-20). 처음 열기 전에는 그리지 않는다
  const [opened, setOpened] = useState(false);
  useEffect(() => { if (tab) setOpened(true); }, [tab]);
  const showPanel = !!tab || opened;
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
        <div className="ma-toast ma-rise" role="status" style={shift}>
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
        <div className="ma-menu" role="menu" aria-label="이브 메뉴" style={shift}>
          {EVE_TABS.map((t, i) => (
            <button key={t} type="button" role="menuitem" className="ma-menu-item ma-rise" style={{ animationDelay: `${i * 50}ms` }} onClick={() => pick(t)}>
              <span className="ma-menu-label">{t}</span>
              <span className="ma-menu-icon"><Icon d={TAB_ICON[t]} size={20} />{badge(t, 'ma-menu-badge')}</span>
            </button>
          ))}
        </div>
      )}
      {showPanel && (
        <aside className="ma-panel ma-side" aria-label="이브" style={tab ? undefined : { display: 'none' }}>
          <header className="ma-panel-head">
            <Robot size={30} />
            <strong className="ma-panel-title">이브</strong>
            {tab === '채팅' && <span ref={setSlot} className="flex shrink-0 items-center" />}
            <button type="button" className="ma-icon-btn" onClick={onClose} aria-label="창 닫기"><Icon d={['M6 6l12 12M18 6L6 18']} /></button>
          </header>
          <div className="ma-tabs" role="tablist" aria-label="이브 메뉴">
            {EVE_TABS.map((t) => <button key={t} type="button" role="tab" className="ma-tab" aria-selected={tab === t} onClick={() => { setFocus(null); onPick(t); }}>{t}{badge(t, 'ma-tab-badge')}</button>)}
          </div>
          {/* 채팅은 다른 탭으로 가도 지우지 않고 숨기기만 한다 — 보낸 질문·기다리는 답·입력 중인 글이 그대로 남는다 (2026-10-20). contents = 보일 때 모양은 그대로 */}
          <div className={tab === '채팅' ? 'contents' : 'hidden'}>
            <Chat active={tab === '채팅'} focus={focus} headerSlot={slot} onNewChat={() => setFocus(null)} ask={ask} onAsked={() => setAsk(null)} />
          </div>
          {tab && tab !== '채팅' && (
            <div className="ma-body text-[14px] leading-relaxed" role="tabpanel">
              {tab === '채팅 기록' ? <ChatLog onOpen={(r) => { setFocus({ at: r.at, q: r.q, ...(typeof r.chatId === 'number' ? { chatId: r.chatId } : {}) }); onPick('채팅'); }} /> : <div className="ma-pad">{tab === '브리핑' ? brief : <AlertsTab onNotice={onNotice} />}</div>}
            </div>
          )}
        </aside>
      )}
      {/* 이브 버튼 왼쪽 작은 채팅창 (사용자 요청 2026-10-20): 늘 꺼내 두고 바로 묻는다. 보내면 이브 창 채팅 탭이 열리며 그 질문을 보냄. 홈에서만 (2026-10-21) */}
      {closed && showQuick && (
        <form className="ma-quick" style={shift} onSubmit={(e) => { e.preventDefault(); const v = quick.trim(); if (!v) return; setQuick(''); setFocus(null); setAsk(v); onPick('채팅'); }}>
          <label htmlFor="ma-quick-in" className="sr-only">이브에게 묻기</label>
          <input id="ma-quick-in" value={quick} onChange={(e) => setQuick(e.target.value)} placeholder="이브에게 물어보세요" autoComplete="off" />
          <button type="submit" disabled={!quick.trim()} aria-label="보내기"><Icon d={['M12 19V5', 'M5 12l7-7 7 7']} size={18} w={2.6} /></button>
        </form>
      )}
      <button type="button" className="ma-fab" aria-expanded={!closed} style={{ ...shift, touchAction: 'none' }} title="끌어서 옮길 수 있어요"
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
        onClick={() => { if (moved.current) { moved.current = false; return; } if (tab) onClose(); else setMenu((m) => !m); }}
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
// 알람 상세 본문 한 문단. 프로그램 문장(alarmText.ts)을 보이다가, 비서가 다듬은 문장이 준비되면 그것으로 바꾸고 [원문 보기]로 프로그램 문장을 언제나 볼 수 있다 (2026-10-19).
// 열린 알림 하나만 비서에게 묻는다. 꺼짐·실패·탈락이면 늘 프로그램 문장 그대로다. 훅은 여기서 부른다 — AlertsTab은 상세를 일찍 return 해서 거기서는 훅을 못 부른다.
function AlarmBody({ a }: { a: AlertRec }) {
  const base = alarmSentence({ name: MACHINES[a.machine].name, op: MACHINES[a.machine].op, code: a.code, severity: a.alarm?.severity ?? null, scenario: a.scenario, lot: a.lot, cleared: a.cleared ? hhmm(a.cleared) : null });
  const ai = useAlarmText(a.id, base);
  const [raw, setRaw] = useState(false);
  const polished = !!ai && ai !== base;   // 비서가 원문 그대로 돌려줬으면 꼬리표·전환 버튼 없이 그대로 둔다
  return (
    <p className="mt-2">
      {polished && !raw && <b className="mr-1 text-[12px] text-slate-500">비서 정리 ·</b>}
      {polished && !raw ? ai : base}
      {polished && <button onClick={() => setRaw((x) => !x)} title="프로그램이 만든 원래 문장과 비서가 다듬은 문장을 바꿔 봅니다" className="ml-2 text-[12px] font-semibold underline">{raw ? '비서 정리 보기' : '원문 보기'}</button>}
    </p>
  );
}
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
        <button onClick={() => { setOpenId(null); setPlan(''); }} className="w-fit text-[18px] font-semibold underline">← 목록</button>
        <div className="rounded-xl border-l-[6px] bg-white/5 p-3" style={{ borderColor: BAR[lv] }}>
          <div className="text-[12px] font-semibold" style={{ color: TONE[lv] }}>{LEVEL_VIEW[lv].icon} {lv} · {md(at(cur))} {hhmm(at(cur))} · {done ? '처리됨' : '처리 안 됨'}</div>
          <b className="mt-1 block text-[17px] leading-snug">{title(cur)}</b>
          {cur.kind === 'a' ? (<>
            <AlarmBody key={cur.a.id} a={cur.a} />
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

  // 목록 = 팀원 알림 시안 C '시간 흐름' (사용자 선택 2026-10-20): 1시간 안 → 1~2시간 전 → 오늘 오후·오전 → 지난 날짜 묶음, 최신이 위.
  // 왼쪽 시각 · 세로 선 위 점(긴급 빨강·주의 주황·참고 회색, BAR) · 오른쪽 카드(처리 안 된 긴급은 분홍). 누르면 위의 상세 그대로. 예전 목록은 구현_중_수정사항/백업_1020_이브패널/Eve.tsx
  const nowMs = SIM.now(), today = md(simIso(nowMs));
  const periodOf = (it: Item) => {
    const ago = nowMs - tsOfI(it), t = at(it);
    if (ago < 3600e3) return '1시간 안';
    if (ago < 7200e3) return '1~2시간 전';
    if (md(t) !== today) return md(t);
    return Number(hhmm(t).slice(0, 2)) < 12 ? '오전' : '오후';
  };
  const groups: { name: string; rows: Item[] }[] = [];
  items.slice(0, 150).forEach((it) => { const p = periodOf(it), g = groups[groups.length - 1]; if (g && g.name === p) g.rows.push(it); else groups.push({ name: p, rows: [it] }); });

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        <button onClick={() => setOnlyOpen(true)} className={chip(onlyOpen)}>처리 안 됨 {all.filter((it) => !handledOf(it)).length}</button>
        <button onClick={() => setOnlyOpen(false)} className={chip(!onlyOpen)}>전체</button>
      </div>
      {recent > 10 && <div className="rounded-md bg-[#fff1cc] p-2 text-[13px] font-semibold text-[#7a4b00]">▲ 알림 폭주 — 10분 안 알람 {recent}건</div>}
      {items.length === 0 ? <p className="ma-empty">처리 안 된 알림이 없습니다.</p> : groups.map((g, gi) => (
        <section key={`${g.name}-${gi}`} aria-label={g.name}>
          <p className="m-0 px-0.5 pb-1 pt-2 text-[13px] font-bold text-slate-500">{g.name}</p>
          <ul className="m-0 flex list-none flex-col p-0">
            {g.rows.map((it, i) => {
              const lv = level(it), done = handledOf(it), hot = lv === '긴급' && !done;
              return (
                <li key={idOf(it)} className="grid grid-cols-[46px_20px_minmax(0,1fr)]">
                  <span className="pr-1 pt-[13px] text-right font-mono text-[13px] font-semibold text-[#4b4766]">{hhmm(at(it))}</span>
                  <span className="relative flex justify-center" aria-hidden="true">
                    {g.rows.length > 1 && <span className="absolute w-0.5 bg-[#ddd5f7]" style={{ top: i === 0 ? 18 : 0, bottom: i === g.rows.length - 1 ? 'calc(100% - 18px)' : 0 }} />}
                    <span className="relative mt-[15px] h-3 w-3 rounded-full" style={{ background: BAR[lv], boxShadow: '0 0 0 3px #f3f1fb' }} />
                  </span>
                  <button onClick={() => setOpenId(idOf(it))} className={`my-1 flex w-full min-w-0 flex-col gap-0.5 rounded-xl border px-3 py-2 text-left ${hot ? 'border-[#f2c4c0] bg-[#fdeeee] hover:bg-[#fbe3e3]' : 'border-[#e4def8] bg-[#ffffff] hover:bg-[#f7f5fd]'}`}>
                    <b className={`truncate text-[15px] ${hot ? 'text-[#c62a2f]' : ''} ${done ? 'font-semibold text-[#6b6683]' : ''}`}>{title(it)}</b>
                    <span className="truncate text-[12.5px] text-slate-500">{lv}{it.kind === 'n' ? ' · 문서·확인 알림' : ` · 알람 ${it.a.code}`}{handledOf(it) ? ' · 처리됨' : ''}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

// ---------- SCR-10 채팅 ----------
// 서버에 저장된 내 채팅 기록 (API-AST-02 GET). 백엔드 비서를 켰을 때만 받는다 — 끄면 이 브라우저 기록만 (옛 길). again이 바뀔 때마다 다시 받는다
function useServerChat(userId: string, again: unknown): ChatRow[] {
  const [rows, setRows] = useState<ChatRow[]>([]);
  useEffect(() => {
    if (!backendChatEnabled()) return;
    let live = true;
    fetchChatLog(userId).then((r) => { if (live && r) setRows(r); });
    return () => { live = false; };
  }, [userId, again]);
  return rows;
}

function Chat({ active, focus, headerSlot, onNewChat, ask, onAsked }: { active: boolean; focus: FocusRef | null; headerSlot: HTMLElement | null; onNewChat: () => void; ask?: string | null; onAsked?: () => void }) {
  const { user, role, screen, selected, openSource, key: screenKey, alerts } = useApp();
  const cardCode = screen === 'card' && screenKey ? alerts.find((x) => x.id === screenKey)?.code ?? null : null;   // 지침카드를 열어 둔 채 채팅하면 그 카드의 알람 번호 (말풍선·alarm_key 에 쓴다)
  const [log, setLog] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const [q, setQ] = useLocal<string>(`chatdraft:${user.id}`, '');   // 쓰다 만 글도 새로고침 뒤에 남긴다 (보내면 비운다)
  const [busy, setBusy] = useState(false);
  const inflight = useRef(new Set<number>());   // 이 화면이 지금 요청을 보내 둔 질문의 sentAt — 새로고침으로 끊긴 대기 줄(여기 없는 것)과 구분한다
  const [found, setFound] = useState(false);   // 답이 왔다 → 이브가 ✓ 를 띄운 뒤 답을 보여 줌 (사용자 요청 2026-10-21)
  const input = useRef<HTMLInputElement>(null);
  // 마이크 (2026-10-20): 서버의 음성 스위치가 켜져 있을 때만 버튼이 보인다. 한 번 누르면 녹음 시작 → 다시 누르면 끝나고 글자로 바꿔 입력창에 **채우기만** 한다 (보내는 것은 사용자가 글자를 보고 직접)
  const [voice, setVoice] = useState<VoiceStatus>(VOICE_OFF);
  const [micOk, setMicOk] = useState(false);          // 이 브라우저·주소에서 마이크를 쓸 수 있나 (https·localhost만) — 서버 렌더와 달라서 마운트 뒤에 정한다
  const [voiceBusy, setVoiceBusy] = useState(false);   // 소리를 글자로 바꾸는 중
  const [voiceNote, setVoiceNote] = useState('');      // 실패·안내 한 줄
  useEffect(() => {
    setMicOk(micSupported());
    if (!backendChatEnabled()) return;
    let live = true;
    fetchVoiceStatus(user.id).then((v) => { if (live) setVoice(v); });
    return () => { live = false; };
  }, [user.id]);
  const activeRef = useRef(active);   // 채팅 탭을 떠난 뒤에 끝난 녹음은 글자로 바꾸지 않고 버린다
  activeRef.current = active;
  const mic = useMic({
    maxSeconds: voice.maxSeconds,
    onError: (m) => setVoiceNote(m),
    onAudio: async (blob) => {
      if (!activeRef.current) return;
      setVoiceBusy(true); setVoiceNote('');
      try {
        const r = await transcribeAudio(user.id, blob);
        if (r.text) { setQ((p) => (p.trim() ? `${p.trim()} ${r.text}` : r.text)); input.current?.focus(); } else setVoiceNote(voiceMessage(r.reason));
      } catch (e) { setVoiceNote(voiceMessage(e instanceof VoiceFail ? e.reason : 'FAILED')); }
      finally { setVoiceBusy(false); }
    },
  });
  // 채팅 탭을 떠나면 숨겨진 채로 녹음이 이어지지 않게 멈추고, 돌아오면 안내 줄을 비우고 입력 칸에 초점을 준다 (예전에는 탭을 옮기면 Chat이 사라져 저절로 끊기고, 열릴 때 autoFocus가 했다)
  useEffect(() => {
    if (!active) { mic.stop(); return; }
    setVoiceNote(''); input.current?.focus();
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps
  const server = useServerChat(user.id, focus ? (focus.chatId ?? focus.at) : null);   // 채팅 기록에서 연 대화가 다른 PC에서 물은 것일 수 있다
  // 채팅 기록에서 열면 눌러 연 줄이 속한 대화만(서버 기록 포함, 앞 질문 번호로 이어진 덩어리), 아니면 지금 대화의 최근 12개
  const today = focus ? sessionOf(mergeServerLog(log, server), log, focus) : currentChat(log).slice(-12);
  const send = async (text = q) => {
    if (!text.trim()) return;
    // 직전 알람 이어받기 신호 (carry.ts): 이 질문의 줄을 로그에 더하기 전의 지금 대화로 계산한다. 이어받을지는 서버가 정한다.
    // 채팅 기록에서 열어 본 과거 대화를 보는 중이면 이어받지 않고 새 대화로 보낸다.
    const cur = currentChat(log);
    const alarmKey = focus ? null : carryAlarm(cur) ?? cardCode;   // 대화에서 이어받을 번호가 없으면("992 원인은" 답엔 번호가 없다) 지금 열어 둔 지침카드의 알람
    const newChat = focus ? true : cur.length === 0;
    // 이어서 묻기 (API-AST-02 prev_chat_id): 보고 있는 대화의 마지막 질문에 잇는다. 새 대화의 첫 질문이면 없음
    const prevChatId = lastChatId(focus ? today : cur);
    // 질문을 보내자마자 대기 줄로 저장한다 — 새로고침해도 질문이 남고(되살리기는 아래 효과), 답이 오면 이 줄이 그 자리에서 진짜 줄로 바뀐다 (chatLog.ts)
    const sentAt = Date.now(), at = simIso();
    const keep30 = (l: ChatRow[]) => l.filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5);   // 채팅 기록 30일 (FR-MNT-01-01, NFR-DATA-13)
    inflight.current.add(sentAt);
    setLog((l) => [...keep30(l), { at, q: text, a: '', status: '', sources: [], pending: true, sentAt, ...(prevChatId !== null ? { prevChatId } : {}) }]);
    setBusy(true); setQ('');
    let row: ChatRow;
    try {
      const r = backendChatEnabled()   // NEXT_PUBLIC_MOM_API가 있으면 백엔드의 비서(외부 LLM)로 — assistantApi.ts. 없으면 옛 길(시연 서버의 규칙 답)
        ? await askAssistant(text, user.id, screen, selected ? MACHINES[selected].eq : null, { alarmKey, newChat, prevChatId })
        : await api<{ answer: string; status: string; sources: ChatRow['sources']; series?: ChatRow['series'] }>('assistant/chat', { question: text, role, user_id: user.id, context: { screen, equipment_id: selected ? MACHINES[selected].eq : null } });
      row = { at, q: text, a: r.answer, status: r.status, sources: r.sources ?? [], series: r.series, ...('chatId' in r && typeof r.chatId === 'number' ? { chatId: r.chatId } : {}), ...(prevChatId !== null ? { prevChatId } : {}) };
    } catch (e) { row = { at, q: text, a: '비서 응답 없음 — ' + (e as Error).message, status: '응답 없음', sources: [], ...(prevChatId !== null ? { prevChatId } : {}) }; }
    setFound(true); await new Promise((r) => setTimeout(r, 1100));   // 답하기 직전 ✓ 를 잠깐 보여 줌 (그동안 대기 줄은 그대로 — 새로고침돼도 되살리기가 처리)
    inflight.current.delete(sentAt);
    setLog((l) => settlePending(keep30(l), sentAt, row));
    setBusy(false); setFound(false);
  };
  // 새로고침으로 요청이 끊긴 대기 줄 되살리기: 서버 기록(백엔드 서버는 손님이 끊겨도 답을 끝까지 기록에 남긴다)에서 같은 질문의 새 답을 찾아 붙이고, 150초가 지나도 없으면 끊겼다고 알린다.
  // 백엔드를 안 쓰는 옛 길은 서버 기록이 없어 바로 알린다. 아래 waiting 동안 새 질문·[새 채팅]은 막는다
  const orphan = log.some((r) => r.pending === true && !inflight.current.has(r.sentAt ?? -1));
  useEffect(() => {
    if (!orphan) return;
    let live = true;
    const via = backendChatEnabled();
    const tick = async () => {
      const server = via ? await fetchChatLog(user.id) : [];
      if (live) setLog((l) => resolvePending(l, server, Date.now(), inflight.current, via ? PENDING_GIVEUP_MS : 0, { a: '연결이 끊겨 답을 받지 못했어요. 다시 질문해 주세요.', status: '응답 없음' }));
    };
    tick();
    const t = setInterval(tick, 4000);
    return () => { live = false; clearInterval(t); };
  }, [orphan, user.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const waiting = busy || orphan;
  // [새 채팅]: 기록은 한 줄도 지우지 않고 "여기서부터 새 대화" 표지 줄만 더한다 → 채팅 탭은 표지 뒤 줄만 보이고, 이전 대화는 채팅 기록 탭에 그대로 있다 (chatLog.ts)
  const canNew = !waiting && canStartNewChat(log, !!focus);   // 답을 기다리는 중에는 끈다 (늦게 온 답이 새 대화에 끼지 않게)
  const startNew = () => { if (!canNew) return; const m = makeNewChatMark(simIso()); setLog((l) => withNewChat(l, m, !!focus)); setQ(''); onNewChat(); input.current?.focus(); };
  const ex = suggestChips({ role, onCard: screen === 'card', alarmCode: cardCode });   // 지침카드를 열었으면 그 알람·내 역할에 맞는 질문, 아니면 예전 고정 말풍선 (chips.ts)
  const body = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ask && !waiting) { onAsked?.(); send(ask); } }, [ask, waiting]); // eslint-disable-line react-hooks/exhaustive-deps -- 작은 채팅창의 질문을 한 번 보냄 (답을 기다리는 중이면 끝난 뒤)
  useEffect(() => {
    const el = focus && body.current?.querySelector('[data-focus="1"]');
    if (el) el.scrollIntoView({ block: 'center' }); else if (body.current) body.current.scrollTop = body.current.scrollHeight;
  }, [log.length, waiting, focus, active]);   // active: 숨겼다 다시 보일 때도 맨 아래(또는 눌러 연 줄)로
  return (
    <>
      {headerSlot && createPortal(
        <button type="button" onClick={startNew} disabled={!canNew} aria-label="새 채팅 시작" title="지금 대화를 비우고 새로 시작합니다. 이전 대화는 채팅 기록에 남습니다."
          className="inline-flex h-9 items-center gap-1 rounded-full border border-white/25 px-3 text-[12px] font-bold text-[color:var(--ma-panel-fg)] hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--ma-lime)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent">
          <Icon d={['M12 5v14M5 12h14']} size={15} w={2.4} />새 채팅
        </button>, headerSlot)}
      <div ref={body} className="ma-body text-[14px]" role="tabpanel">
        <div className="ma-pad min-h-full" aria-live="polite">
          {today.length === 0 && !waiting && <EveHello />}
          {today.map((r, i) => <div key={i} data-at={r.at} {...(isFocusRow(r, focus) ? { 'data-focus': '1' } : {})} className={isFocusRow(r, focus) ? 'rounded-lg ring-2 ring-[#B79CFF]' : ''}><Bubble r={r} meta={`${md(r.at)} ${hhmm(r.at)}`} openSource={openSource} role={role} /></div>)}
          {waiting && <EveThinking found={found} />}
        </div>
      </div>
      <form className="ma-compose" onSubmit={(e) => { e.preventDefault(); if (!waiting) send(); }}>
        <div className="mb-3 flex flex-wrap justify-center gap-1.5">{ex.map((x) => <button key={x} type="button" disabled={waiting} onClick={() => send(x)} className="h-9 rounded-full border border-slate-300 bg-[#ffffff] px-3.5 text-[13px] font-bold hover:bg-[#f7f5fd]">{x}</button>)}</div>
        {voice.enabled && (mic.state === 'recording' || voiceBusy || voiceNote !== '') && (
          <div className="ma-voice-note" role="status">
            {mic.state === 'recording' ? `듣고 있어요… 말이 끝나면 마이크 버튼을 다시 누르세요 (최대 ${Math.round(voice.maxSeconds)}초).` : voiceBusy ? '글자로 바꾸는 중이에요 (길게 말했다면 더 걸려요)…' : voiceNote}
          </div>
        )}
        <div className="ma-compose-box">
          <label className="ma-sr" htmlFor="ma-input">이브에게 질문</label>
          <input id="ma-input" ref={input} className="ma-input" autoFocus autoComplete="off" value={q} onChange={(e) => setQ(e.target.value)} placeholder="질문 (예: 992 알람 점검 순서)" />
          {voice.enabled && (
            <button type="button" className={`ma-mic${mic.state === 'recording' ? ' is-rec' : ''}`} disabled={waiting || voiceBusy || !micOk}
              aria-label={mic.state === 'recording' ? '말하기 끝내기' : '말하기 시작'} aria-pressed={mic.state === 'recording'}
              title={micOk ? (mic.state === 'recording' ? '다시 누르면 녹음이 끝나고 글자로 바뀌어 입력창에 들어갑니다.' : `한 번 누르면 녹음이 시작됩니다. 질문을 말하고 다시 누르면 끝나요 (최대 ${Math.round(voice.maxSeconds)}초).`) : '이 주소에서는 마이크를 쓸 수 없어요. localhost 또는 https 주소로 열어 주세요.'}
              onClick={() => { if (mic.state === 'recording') mic.stop(); else { setVoiceNote(''); mic.start(); } }}>
              <Icon d={['M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3']} w={2.2} />
            </button>
          )}
          <button type="submit" className="ma-send" disabled={waiting} aria-label="보내기"><Icon d={['M12 19V5M5 12l7-7 7 7']} w={2.4} /></button>
        </div>
      </form>
    </>
  );
}

// 채팅 첫 화면 = 팀원 '새 채팅 시안' (사용자 선택 2026-10-20): 가운데 3D 이브(robot3d.js) + 안내 한 줄. WebGL이 안 되면 얼굴 그림
function EveHello() {
  const [gl, setGl] = useState(true);
  return (
    <div className="my-auto flex flex-col items-center gap-4 px-4 py-6 text-center">
      <div className="relative flex h-[150px] w-[150px] items-end justify-center">
        <span aria-hidden="true" className="absolute bottom-0 left-6 right-6 h-5 rounded-full" style={{ background: 'radial-gradient(closest-side, rgba(110,215,235,.5), rgba(110,215,235,0))' }} />
        {gl ? <RobotIcon mode={0} size={150} onFail={() => setGl(false)} /> : <Robot face="happy" size={110} />}
      </div>
      <p className="m-0 text-[17px] font-extrabold leading-relaxed text-[#1f1b33]">라인 상황, 알람, 사내 문서 등<br />무엇이든 물어보세요.</p>
    </div>
  );
}

// 채팅 기록 = G안 (사용자 선택 2026-10-20): 날짜 묶음(오늘·어제) 아래 한 줄 = 질문 + 시각
function ChatLog({ onOpen }: { onOpen: (r: ChatRow) => void }) {
  const { user } = useApp();
  const [log] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const server = useServerChat(user.id, null);   // 탭을 열 때마다 받는다 — 다른 PC·브라우저에서 물은 것도 보인다 (FR-MNT-01-01)
  const keep = mergeServerLog(log, server).filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5).reverse();
  const today = md(simIso()), yday = md(simIso(SIM.now() - 864e5));
  const dayName = (d: string) => (d === today ? `오늘 · ${d}` : d === yday ? `어제 · ${d}` : d);
  return (
    <div className="ma-history gap-2">
      {keep.length === 0 ? <p className="ma-empty">저장된 대화가 없습니다.</p> : keep.map((r, i) => (
        <Fragment key={i}>
          {(i === 0 || md(keep[i - 1].at) !== md(r.at)) && <p className="ma-history-group">{dayName(md(r.at))}</p>}
          <HistoryItem q={r.q} when={hhmm(r.at)} onOpen={() => onOpen(r)} />
        </Fragment>
      ))}
    </div>
  );
}
