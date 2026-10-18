// 채팅 탭의 "직전 알람 이어받기" 신호 — 순수 함수 (React 없음 → tools/carry_check.mjs 로 시험).
//
// 알람 하나를 물어 답을 받은 뒤 "원인은?"처럼 대상 없는 질문을 하면, 서버가 그 알람 이야기로 이어받는다. 이어받을지는 **서버가 판정**한다.
// 화면은 요청의 context 에 직전 알람 번호(alarm_key)와 새 대화 신호(new_chat)만 실어 보낸다:
//  - 알람 번호를 정확히 하나로 뽑을 수 있을 때만 보낸다 (둘 이상이거나 없으면 보내지 않는다).
//  - 번호는 "알람"·"경보" 낱말 바로 앞뒤에 붙은 숫자만 센다 ("7일 3번"·"5분 대기"의 숫자는 알람 번호가 아니다).
//    그 번호와 "랑·와·,"로 이어진 번호도 센다 ("2075랑 992 알람"은 두 번호).
import { STATUS_KO } from './assistantStatus';

/** 지금 대화의 한 줄에서 이어받기가 보는 칸 (Eve.tsx 의 ChatRow 가 이 모양을 포함한다) */
export interface CarryRow { q: string; a: string; status: string }

// 번호 모양: 3~5자리 숫자, 소수점 두 자리가 붙을 수 있다 (6302.00, 25050, 992)
const NUM = /^\d{3,5}(?:\.\d{2})?$/;
const BEFORE = /(?:알람|경보)(?:\s{0,2}번호)?\s{0,2}$/;     // 번호 앞: "알람 2075", "알람번호 254"
const AFTER = /^\s{0,2}번?\s{0,2}(?:알람|경보)/;            // 번호 뒤: "2075 알람", "992번 경보"

const JOIN = /^\s{0,2}(?:이?랑|와|과|하고|및|,|\/|·|vs\.?|VS)\s{0,2}$/;   // 번호와 번호 사이: "2075랑 992 알람", "2075, 992 알람"

/** 글에서 알람 번호를 모두 뽑는다 (서로 다른 것만, 나온 순서) */
function alarmNumbers(text: string): string[] {
  // 숫자 덩어리 통째로 본다 → 12345678·6302.005 같은 것은 모양에서 걸러진다
  const toks = [...text.matchAll(/\d+(?:\.\d+)?/g)].filter((m) => NUM.test(m[0])).map((m) => ({ s: m[0], from: m.index ?? 0, to: (m.index ?? 0) + m[0].length }));
  const hit = toks.map((t) => BEFORE.test(text.slice(0, t.from)) || AFTER.test(text.slice(t.to)));
  // "알람" 낱말에 직접 붙지 않아도 "랑·와·,"로 이어진 번호는 같은 묶음이다 → 두 번호를 함께 말한 질문을 한 번호로 오해하지 않는다
  let again = true;
  while (again) {
    again = false;
    for (let i = 0; i + 1 < toks.length; i++) {
      if (hit[i] !== hit[i + 1] && JOIN.test(text.slice(toks[i].to, toks[i + 1].from))) { hit[i] = hit[i + 1] = true; again = true; }
    }
  }
  const out: string[] = [];
  toks.forEach((t, i) => { if (hit[i] && !out.includes(t.s)) out.push(t.s); });
  return out;
}

/**
 * 직전 알람 번호. 지금 대화(currentChat)의 **마지막 줄 하나만** 본다.
 * - 마지막 줄이 정상 답(STATUS_KO.OK)이 아니면(문서에 없음·응답 없음·거부 등) null.
 * - 질문에서 먼저 찾는다: 서로 다른 번호가 정확히 1개면 그 번호, 2개 이상이면 null.
 * - 질문에 없으면 답에서 찾는다: 정확히 1개면 그 번호, 아니면 null.
 * 번호는 글자 그대로 돌려준다 ("6302.00" → "6302.00").
 */
export function carryAlarm(rows: readonly CarryRow[]): string | null {
  const last = rows[rows.length - 1];
  if (!last || last.status !== STATUS_KO.OK) return null;
  const inQ = alarmNumbers(last.q);
  if (inQ.length > 0) return inQ.length === 1 ? inQ[0] : null;
  const inA = alarmNumbers(last.a);
  return inA.length === 1 ? inA[0] : null;
}

/** 비서 요청의 context. 값이 있는 칸만 담는다 (new_chat 은 true 일 때만 "1") */
export function buildAskContext(o: { screenCode?: string | null; equipmentId?: string | null; alarmKey?: string | null; newChat?: boolean }): Record<string, string> {
  const ctx: Record<string, string> = {};
  if (o.screenCode) ctx.screen = o.screenCode;
  if (o.equipmentId) ctx.equipment_id = o.equipmentId;
  if (o.alarmKey) ctx.alarm_key = o.alarmKey;
  if (o.newChat === true) ctx.new_chat = '1';
  return ctx;
}
