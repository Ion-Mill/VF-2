'use client';
// 이브 채팅(SCR-10)을 실제 백엔드의 비서에 잇는 곳 (API-AST-02). 2026-10-16 추가.
//
//   화면 ──(브라우저가 직접)──▶ 백엔드 POST /api/assistant/chat ──▶ AI 비서 서비스 ──▶ 외부 LLM(Claude)
//
// - 켜는 스위치: 환경변수 NEXT_PUBLIC_MOM_API (백엔드 주소, 예 http://127.0.0.1:8000). **없으면 꺼짐** — 채팅은 지금처럼 시연 서버의 규칙 답(live.ts api())을 쓴다.
//   바꾸면 `npm run dev`를 다시 켠다 (빌드할 때 글자로 박힌다). 백엔드의 MOM_CORS_ORIGINS에 이 화면 주소(localhost:3000)가 있어야 한다.
// - 브라우저가 백엔드를 직접 부르므로 화면 서버(Next) 프록시의 30초 제한을 받지 않는다 (외부 LLM 답은 20초 넘게 걸릴 수 있다).
// - 로그인: 채팅할 때 사용자 ID로 백엔드 /api/auth/login을 해서 토큰을 받는다 (화면 로그인은 그대로 — 거기는 화면 안에서 비교만 한다).
//   토큰은 **메모리에만** 둔다 (새로고침하면 다음 질문에서 조용히 다시 받는다). 시연 비밀번호는 Login.tsx의 DEMO_PW.
// - 실패는 명세대로 "응답 없음" — 옛 규칙 답으로 몰래 바꿔 주지 않는다 (숫자가 엇갈리지 않게).
import { DEMO_PW } from './Login';
import { buildAskContext } from './carry';
import { STATUS_KO } from './assistantStatus';
import { itemKeysOf } from './briefChecks';

export { STATUS_KO };   // 상태 이름 표는 assistantStatus.ts 로 옮겼다 (carry.ts 가 읽는다). 가져다 쓰는 곳은 그대로 여기서 가져온다

export interface AssistantSource { doc_no: string; doc_name: string; rev: string; section: string }
export interface AssistantResult { answer: string; status: string; sources: AssistantSource[]; series?: undefined; chatId?: number }   // series = 옛 규칙 답의 센서 그래프. 새 길에는 없다. chatId = 서버 chat_log 번호 (이어서 물을 때 prev_chat_id로 보낸다)

const BASE = (process.env.NEXT_PUBLIC_MOM_API ?? '').trim().replace(/\/+$/, '');
export const backendChatEnabled = () => BASE !== '';

// 한 질문을 기다리는 최대 시간: 백엔드가 비서를 기다리는 130초 + 여유 10초
export const ASK_TIMEOUT_MS = 140_000;
export const NO_RESPONSE_TEXT = '비서가 지금 답하지 못합니다. 잠시 후 다시 시도해 주세요';

// 화면 이름 → UI설계서 화면 번호 (비서가 "이 화면 설명해 줘"에 쓴다). 모르는 화면은 보내지 않는다.
export const SCREEN_CODE: Record<string, string> = {
  line: 'SCR-04', layout2d: 'SCR-05', replay: 'SCR-06', cards: 'SCR-09', card: 'SCR-09', wo: 'SCR-11', wr: 'SCR-12', sr: 'SCR-13', stops: 'SCR-14',
  shift: 'SCR-15', daily: 'SCR-16', revs: 'SCR-17', docs: 'SCR-18', lots: 'SCR-19', quality: 'SCR-20', inventory: 'SCR-21', tools: 'SCR-22',
  pm: 'SCR-23', idocs: 'SCR-24', settings: 'SCR-25',
};

const tokens = new Map<string, string>();          // 사용자 ID → 토큰 (메모리만)

class Http extends Error { constructor(public status: number) { super(`HTTP ${status}`); } }

async function post(path: string, body: unknown, token?: string, timeoutMs = ASK_TIMEOUT_MS): Promise<any> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(BASE + path, {
      method: 'POST', signal: ctl.signal, cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Http(r.status);
    return await r.json();
  } finally { clearTimeout(timer); }
}

async function tokenFor(userId: string, fresh = false): Promise<string> {
  const have = tokens.get(userId);
  if (have && !fresh) return have;
  const j = await post('/api/auth/login', { user_id: userId, password: DEMO_PW });
  if (typeof j?.access_token !== 'string') throw new Error('토큰 없음');
  tokens.set(userId, j.access_token);
  return j.access_token;
}

export const forgetTokens = () => tokens.clear();

const none = (): AssistantResult => ({ answer: NO_RESPONSE_TEXT, status: STATUS_KO.NO_RESPONSE, sources: [] });

// 백엔드 답의 출처 줄을 화면 모양으로 (문서 번호·절이 없는 줄은 버린다)
const toSources = (v: unknown): AssistantSource[] => Array.isArray(v)
  ? v.filter((s: any) => s && typeof s.doc_no === 'string' && typeof s.section === 'string')
      .map((s: any) => ({ doc_no: s.doc_no, doc_name: String(s.doc_name ?? ''), rev: String(s.rev ?? ''), section: s.section }))
  : [];

/**
 * 백엔드의 비서에게 묻는다. 던지지 않는다 — 어떤 실패든 "응답 없음" 결과로 돌려준다.
 * opts: 직전 알람 이어받기 신호(carry.ts) — alarmKey = 직전 알람 번호, newChat = 새 대화의 첫 질문. 이어받을지는 서버가 정한다.
 *       prevChatId = 이어서 묻는 앞 질문의 chat_id (API-AST-02 prev_chat_id, 기획서 9장 MNT-01 "이어서 묻는다").
 *       서버에 그 번호가 없으면(30일 지나 지워짐·DB 초기화) 404 → 앞 질문 없이 한 번 다시 묻는다.
 */
export async function askAssistant(question: string, userId: string, screen: string | null | undefined, equipmentId?: string | null, opts?: { alarmKey?: string | null; newChat?: boolean; prevChatId?: number | null }): Promise<AssistantResult> {
  const context = buildAskContext({ screenCode: screen ? SCREEN_CODE[screen] : undefined, equipmentId, alarmKey: opts?.alarmKey, newChat: opts?.newChat });
  const ask = async (body: unknown) => {
    try {
      return await post('/api/assistant/chat', body, await tokenFor(userId));
    } catch (e) {
      if (!(e instanceof Http) || e.status !== 401) throw e;            // 토큰이 만료·무효 → 한 번만 다시 로그인해서 재시도
      return await post('/api/assistant/chat', body, await tokenFor(userId, true));
    }
  };
  try {
    const prev = opts?.prevChatId ?? null;
    let j: any;
    try {
      j = await ask(prev === null ? { question, context } : { question, context, prev_chat_id: prev });
    } catch (e) {
      if (prev === null || !(e instanceof Http) || e.status !== 404) throw e;
      j = await ask({ question, context });
    }
    const chatId = typeof j?.chat_id === 'number' ? j.chat_id : undefined;   // 답이 없어도(NO_RESPONSE) 질문은 서버 기록에 남는다
    const status = STATUS_KO[String(j?.status)] ?? STATUS_KO.NO_RESPONSE;
    if (typeof j?.answer !== 'string' || !j.answer.trim()) return { ...none(), chatId };   // 비서가 못 답하면 백엔드는 200 + 답 없음(NO_RESPONSE)을 준다
    if (status === STATUS_KO.NO_RESPONSE) return { ...none(), chatId };
    return { answer: j.answer, status, sources: toSources(j.sources), chatId };
  } catch {
    return none();                                                     // 연결 안 됨·시간 초과·503·로그인 실패 — 이유를 화면에 내보내지 않는다
  }
}

/** 서버에 저장된 내 채팅 기록 한 줄 (API-AST-02 GET → 채팅 기록 탭의 ChatRow 모양) */
export interface ServerChatRow { at: string; q: string; a: string; status: string; sources: AssistantSource[]; chatId: number; prevChatId?: number }   // prevChatId = 이 질문이 이어 물은 앞 질문 번호 (chat_log.prev_chat_id, 없으면 새 대화의 첫 질문)

const kst = (iso: string) => new Date(Date.parse(iso) + 9 * 3600e3).toISOString().slice(0, 19) + '+09:00';   // 화면 시각 글자와 같은 모양 (live.ts simIso)

/**
 * 내 채팅 기록을 서버에서 받는다 (GET /api/assistant/chat — 본인 것만, 30일 안). 오래된 것부터.
 * 다른 PC·브라우저에서 물은 것도 여기서 보인다 (FR-MNT-01-01). 실패하면 null — 화면은 이 브라우저 기록만 보인다.
 */
export async function fetchChatLog(userId: string): Promise<ServerChatRow[] | null> {
  const get = async (token: string) => {
    const r = await fetch(BASE + '/api/assistant/chat?limit=500', { cache: 'no-store', headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Http(r.status);
    return r.json();
  };
  try {
    let j: any;
    try { j = await get(await tokenFor(userId)); } catch (e) {
      if (!(e instanceof Http) || e.status !== 401) throw e;
      j = await get(await tokenFor(userId, true));
    }
    if (!Array.isArray(j)) return null;
    return j.filter((x: any) => typeof x?.chat_id === 'number' && typeof x.asked_at === 'string' && typeof x.question === 'string')
      .map((x: any): ServerChatRow => {
        const status = STATUS_KO[String(x.status)] ?? STATUS_KO.NO_RESPONSE;
        const ok = typeof x.answer === 'string' && x.answer.trim() !== '' && status !== STATUS_KO.NO_RESPONSE;
        return { at: kst(x.asked_at), q: x.question, a: ok ? x.answer : NO_RESPONSE_TEXT, status: ok ? status : STATUS_KO.NO_RESPONSE, sources: ok ? toSources(x.sources) : [], chatId: x.chat_id, ...(typeof x.prev_chat_id === 'number' ? { prevChatId: x.prev_chat_id } : {}) };
      })
      .reverse();
  } catch {
    return null;
  }
}

// ---------------- 브리핑 "먼저 챙길 일" 체크 (2026-10-20) ----------------
// 체크를 서버에도 남겨 다른 PC·브라우저에서도 보이게 한다 (GET·POST /api/assistant/briefing/checks, 본인 것만). 던지지 않는다 —
// 백엔드가 꺼져 있거나 표가 아직 없으면(500) null·false를 돌려주고, 화면은 이 브라우저 저장만으로 계속 동작한다. 체크는 개인 메모일 뿐이라 알림·알람 처리와 무관하다.
const CHECK_TIMEOUT_MS = 8_000;

async function withToken<T>(userId: string, run: (token: string) => Promise<T>): Promise<T> {
  try { return await run(await tokenFor(userId)); } catch (e) {
    if (!(e instanceof Http) || e.status !== 401) throw e;              // 토큰 만료·무효 → 한 번만 다시 로그인해서 재시도
    return await run(await tokenFor(userId, true));
  }
}

// ---------------- 채팅 음성 입력 (2026-10-20) ----------------
// 마이크로 말한 소리를 백엔드(POST /api/assistant/transcribe)가 사내 서버의 비서에게 넘겨 글자로 바꾼다. 글자는 입력창에 채우기만 하고 보내는 것은 사용자가 한다.
// 소리는 저장되지 않는다. 던지는 것은 VoiceFail 하나뿐 — reason 은 voiceInput.voiceMessage 가 쉬운 문장으로 바꾼다.
const VOICE_TIMEOUT_MS = 50_000;      // 백엔드가 비서를 기다리는 45초 + 여유 (녹음 최대 60초까지 늘릴 수 있어서, 2026-10-20)

export interface VoiceStatus { enabled: boolean; maxSeconds: number }
export const VOICE_OFF: VoiceStatus = { enabled: false, maxSeconds: 20 };

export class VoiceFail extends Error { constructor(public reason: string) { super(reason); } }

/** 마이크 버튼을 보일지 (서버의 음성 스위치). 백엔드 비서가 꺼져 있거나 실패하면 꺼짐 — 버튼만 안 보인다 */
export async function fetchVoiceStatus(userId: string): Promise<VoiceStatus> {
  if (!backendChatEnabled()) return VOICE_OFF;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), CHECK_TIMEOUT_MS);
  try {
    const j = await withToken(userId, async (token) => {
      const r = await fetch(`${BASE}/api/assistant/voice`, { cache: 'no-store', signal: ctl.signal, headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Http(r.status);
      return r.json();
    });
    const max = Number(j?.max_seconds);
    return { enabled: j?.enabled === true, maxSeconds: Number.isFinite(max) && max >= 3 ? max : VOICE_OFF.maxSeconds };
  } catch { return VOICE_OFF; } finally { clearTimeout(timer); }
}

/** 녹음한 소리를 글자로. text 가 비면 reason(too_short·no_speech·…)이 까닭이다. 실패하면 VoiceFail */
export async function transcribeAudio(userId: string, audio: Blob): Promise<{ text: string; reason: string | null }> {
  if (!backendChatEnabled()) throw new VoiceFail('VOICE_OFF');
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), VOICE_TIMEOUT_MS);
  try {
    const j = await withToken(userId, async (token) => {
      const r = await fetch(`${BASE}/api/assistant/transcribe`, {
        method: 'POST', cache: 'no-store', signal: ctl.signal, body: audio,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': audio.type || 'application/octet-stream' },
      });
      if (r.status === 401) throw new Http(401);
      if (!r.ok) {
        let reason = `HTTP_${r.status}`;
        try { const b = await r.json(); reason = String(b?.detail?.reason ?? b?.code ?? reason); } catch { /* 본문 없음 */ }
        throw new VoiceFail(reason);
      }
      return r.json();
    });
    if (typeof j?.text !== 'string') throw new VoiceFail('FORMAT');
    return { text: j.text.trim(), reason: typeof j.reason === 'string' ? j.reason : null };
  } catch (e) {
    if (e instanceof VoiceFail) throw e;
    if (e instanceof DOMException && e.name === 'AbortError') throw new VoiceFail('VOICE_TIMEOUT');
    throw new VoiceFail('NETWORK');
  } finally { clearTimeout(timer); }
}

/** 서버에 저장된 내 체크 항목 글자들 (shift = briefChecks.serverShift). 실패·모양 이상이면 null */
export async function fetchBriefChecks(userId: string, shift: string): Promise<string[] | null> {
  if (!backendChatEnabled()) return null;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), CHECK_TIMEOUT_MS);
  try {
    const j = await withToken(userId, async (token) => {
      const r = await fetch(`${BASE}/api/assistant/briefing/checks?shift_id=${encodeURIComponent(shift)}`, { cache: 'no-store', signal: ctl.signal, headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Http(r.status);
      return r.json();
    });
    return itemKeysOf(j);
  } catch { return null; } finally { clearTimeout(timer); }
}

/** 체크 한 칸을 서버에 남긴다 (checked=false면 푼다). 성공 여부만 돌려준다 */
export async function saveBriefCheck(userId: string, shift: string, itemKey: string, checked: boolean): Promise<boolean> {
  if (!backendChatEnabled()) return false;
  try {
    await withToken(userId, (token) => post('/api/assistant/briefing/checks', { shift_id: shift, item_key: itemKey, checked }, token, CHECK_TIMEOUT_MS));
    return true;
  } catch { return false; }
}
