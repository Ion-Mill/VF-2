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

export interface AssistantSource { doc_no: string; doc_name: string; rev: string; section: string }
export interface AssistantResult { answer: string; status: string; sources: AssistantSource[]; series?: undefined }   // series = 옛 규칙 답의 센서 그래프. 새 길에는 없다

const BASE = (process.env.NEXT_PUBLIC_MOM_API ?? '').trim().replace(/\/+$/, '');
export const backendChatEnabled = () => BASE !== '';

// 한 질문을 기다리는 최대 시간: 백엔드가 비서를 기다리는 130초 + 여유 10초
export const ASK_TIMEOUT_MS = 140_000;
export const NO_RESPONSE_TEXT = '비서가 지금 답하지 못합니다. 잠시 후 다시 시도해 주세요';

// 백엔드 상태 코드 → 화면에 보이는 말 (API명세서 AST-02: ok / 문서에 없음 / 거부 / 권한 밖 / 응답 없음). 표에 없는 값은 "응답 없음"으로 — 원문을 내보내지 않는다.
export const STATUS_KO: Record<string, string> = { OK: '답변', NOT_IN_DOCS: '문서에 없음', OUT_OF_ROLE: '권한 밖', REFUSED: '거부', NO_RESPONSE: '응답 없음' };

// 화면 이름 → UI설계서 화면 번호 (비서가 "이 화면 설명해 줘"에 쓴다). 모르는 화면은 보내지 않는다.
export const SCREEN_CODE: Record<string, string> = {
  line: 'SCR-04', layout2d: 'SCR-05', replay: 'SCR-06', cards: 'SCR-09', card: 'SCR-09', wo: 'SCR-11', wr: 'SCR-12', sr: 'SCR-13', stops: 'SCR-14',
  shift: 'SCR-15', daily: 'SCR-16', revs: 'SCR-17', docs: 'SCR-18', lots: 'SCR-19', quality: 'SCR-20', inventory: 'SCR-21', tools: 'SCR-22',
  pm: 'SCR-23', idocs: 'SCR-24', settings: 'SCR-25',
};

const tokens = new Map<string, string>();          // 사용자 ID → 토큰 (메모리만)

class Http extends Error { constructor(public status: number) { super(`HTTP ${status}`); } }

async function post(path: string, body: unknown, token?: string): Promise<any> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ASK_TIMEOUT_MS);
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

/** 백엔드의 비서에게 묻는다. 던지지 않는다 — 어떤 실패든 "응답 없음" 결과로 돌려준다. */
export async function askAssistant(question: string, userId: string, screen: string | null | undefined, equipmentId?: string | null): Promise<AssistantResult> {
  const context: Record<string, string> = {};
  const code = screen ? SCREEN_CODE[screen] : undefined;
  if (code) context.screen = code;
  if (equipmentId) context.equipment_id = equipmentId;
  const body = { question, context };
  try {
    let j: any;
    try {
      j = await post('/api/assistant/chat', body, await tokenFor(userId));
    } catch (e) {
      if (!(e instanceof Http) || e.status !== 401) throw e;            // 토큰이 만료·무효 → 한 번만 다시 로그인해서 재시도
      j = await post('/api/assistant/chat', body, await tokenFor(userId, true));
    }
    const status = STATUS_KO[String(j?.status)] ?? STATUS_KO.NO_RESPONSE;
    if (typeof j?.answer !== 'string' || !j.answer.trim()) return none();   // 비서가 못 답하면 백엔드는 200 + 답 없음(NO_RESPONSE)을 준다
    if (status === STATUS_KO.NO_RESPONSE) return none();
    const sources: AssistantSource[] = Array.isArray(j.sources)
      ? j.sources.filter((s: any) => s && typeof s.doc_no === 'string' && typeof s.section === 'string')
          .map((s: any) => ({ doc_no: s.doc_no, doc_name: String(s.doc_name ?? ''), rev: String(s.rev ?? ''), section: s.section }))
      : [];
    return { answer: j.answer, status, sources };
  } catch {
    return none();                                                     // 연결 안 됨·시간 초과·503·로그인 실패 — 이유를 화면에 내보내지 않는다
  }
}
