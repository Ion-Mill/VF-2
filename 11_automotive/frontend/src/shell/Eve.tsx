'use client';
// UI설계서 2.1 [11] AI 비서 사이드바 · [15] 이브 아이콘 · [16] 이브 말풍선, SCR-07 알림 탭, SCR-10 채팅·채팅 기록.
// 채팅 = API-AST-02. 외부 LLM(Claude) 연결을 켜지 않았으면 서버의 "규칙 답"(조회 도구 + 사내 문서 검색)을 쓰고, 답마다 "규칙 답" 표시.
// 겉모양 = mom-assistant-widget (로봇 버튼 · 아이콘 메뉴 · 우측 창 · 알림 토스트). 탭 내용 배치는 2026-10-20 사용자 선택: 브리핑·채팅 기록 G안, 알림 = 팀원 시안 C(시간 흐름), 채팅 첫 화면 = 팀원 새 채팅 시안(3D 이브). 위젯 JS는 innerHTML로 그려 React 탭을 못 담아서 CSS만 쓰고 틀을 여기로 옮김.
import { Fragment, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useApp } from './ctx';
import { MACHINES } from './data';
import { SIM, api, md, simIso, useLocal } from './live';
import { askAssistant, backendChatEnabled, fetchChatLog } from './assistantApi';
import { LEVEL_VIEW, alarmTitle, hhmm, type AlertRec, type Level, type Notice } from './model';
import { alarmSentence } from './alarmText';
import { useAlarmText } from './assistText';
import { rankOfAlert, rankOfNotice } from './Briefing';
import RobotIcon from './RobotIcon';
import EveThinking from './EveThinking';
import { canStartNewChat, currentChat, lastChatId, makeNewChatMark, mergeServerLog, withNewChat } from './chatLog';
import { carryAlarm } from './carry';
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

function Chat({ focus, headerSlot, onNewChat }: { focus: string | null; headerSlot: HTMLElement | null; onNewChat: () => void }) {
  const { user, role, screen, selected, openSource } = useApp();
  const [log, setLog] = useLocal<ChatRow[]>(`chat:${user.id}`, []);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const server = useServerChat(user.id, focus);   // 채팅 기록에서 연 대화가 다른 PC에서 물은 것일 수 있다
  // 채팅 기록에서 열면 그 대화가 있는 날 대화 전부(서버 기록 포함), 아니면 지금 대화의 최근 12개
  const today = focus ? mergeServerLog(log, server).filter((x) => md(x.at) === md(focus)) : currentChat(log).slice(-12);
  const send = async (text = q) => {
    if (!text.trim()) return;
    // 직전 알람 이어받기 신호 (carry.ts): 이 질문의 줄을 로그에 더하기 전의 지금 대화로 계산한다. 이어받을지는 서버가 정한다.
    // 채팅 기록에서 열어 본 과거 대화를 보는 중이면 이어받지 않고 새 대화로 보낸다.
    const cur = currentChat(log);
    const alarmKey = focus ? null : carryAlarm(cur);
    const newChat = focus ? true : cur.length === 0;
    // 이어서 묻기 (API-AST-02 prev_chat_id): 보고 있는 대화의 마지막 질문에 잇는다. 새 대화의 첫 질문이면 없음
    const prevChatId = lastChatId(focus ? today : cur);
    setBusy(true); setQ('');
    let row: ChatRow;
    try {
      const r = backendChatEnabled()   // NEXT_PUBLIC_MOM_API가 있으면 백엔드의 비서(외부 LLM)로 — assistantApi.ts. 없으면 옛 길(시연 서버의 규칙 답)
        ? await askAssistant(text, user.id, screen, selected ? MACHINES[selected].eq : null, { alarmKey, newChat, prevChatId })
        : await api<{ answer: string; status: string; sources: ChatRow['sources']; series?: ChatRow['series'] }>('assistant/chat', { question: text, role, user_id: user.id, context: { screen, equipment_id: selected ? MACHINES[selected].eq : null } });
      row = { at: simIso(), q: text, a: r.answer, status: r.status, sources: r.sources ?? [], series: r.series, ...('chatId' in r && typeof r.chatId === 'number' ? { chatId: r.chatId } : {}) };
    } catch (e) { row = { at: simIso(), q: text, a: '비서 응답 없음 — ' + (e as Error).message, status: '응답 없음', sources: [] }; }
    // 채팅 기록 30일 (FR-MNT-01-01, NFR-DATA-13)
    setLog((l) => [...l.filter((x) => Date.parse(x.at) > SIM.now() - 30 * 864e5), row]);
    setBusy(false);
  };
  // [새 채팅]: 기록은 한 줄도 지우지 않고 "여기서부터 새 대화" 표지 줄만 더한다 → 채팅 탭은 표지 뒤 줄만 보이고, 이전 대화는 채팅 기록 탭에 그대로 있다 (chatLog.ts)
  const canNew = !busy && canStartNewChat(log, !!focus);   // 답을 기다리는 중에는 끈다 (늦게 온 답이 새 대화에 끼지 않게)
  const startNew = () => { if (!canNew) return; const m = makeNewChatMark(simIso()); setLog((l) => withNewChat(l, m, !!focus)); setQ(''); onNewChat(); input.current?.focus(); };
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
        <div className="ma-pad min-h-full" aria-live="polite">
          {today.length === 0 && !busy && <EveHello />}
          {today.map((r, i) => <div key={i} data-at={r.at} className={r.at === focus ? 'rounded-lg ring-2 ring-[#B79CFF]' : ''}><Bubble r={r} meta={`${md(r.at)} ${hhmm(r.at)}`} openSource={openSource} role={role} /></div>)}
          {busy && <EveThinking />}
        </div>
      </div>
      <form className="ma-compose" onSubmit={(e) => { e.preventDefault(); if (!busy) send(); }}>
        <div className="mb-3 flex flex-wrap justify-center gap-1.5">{ex.map((x) => <button key={x} type="button" disabled={busy} onClick={() => send(x)} className="h-9 rounded-full border border-slate-300 bg-[#ffffff] px-3.5 text-[13px] font-bold hover:bg-[#f7f5fd]">{x}</button>)}</div>
        <div className="ma-compose-box">
          <label className="ma-sr" htmlFor="ma-input">이브에게 질문</label>
          <input id="ma-input" ref={input} className="ma-input" autoFocus autoComplete="off" value={q} onChange={(e) => setQ(e.target.value)} placeholder="질문 (예: 992 알람 점검 순서)" />
          <button type="submit" className="ma-send" disabled={busy} aria-label="보내기"><Icon d={['M12 19V5M5 12l7-7 7 7']} w={2.4} /></button>
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
function ChatLog({ onOpen }: { onOpen: (at: string) => void }) {
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
          <HistoryItem q={r.q} when={hhmm(r.at)} onOpen={() => onOpen(r.at)} />
        </Fragment>
      ))}
    </div>
  );
}
