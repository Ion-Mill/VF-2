// 채팅 알람 답을 카드(AlarmAnswerCard)용 덩어리 목록으로 읽는다 — React 없는 순수 함수 (tools/alarm_card_check.mjs가 그대로 불러 시험한다).
// 입력 = chat_mapping.to_answer_text 가 만든 글자: 빈 줄로 나뉜 덩어리, "■ 제목" 소제목, "★1 (작업자) …"·"5 (보전) …" 점검 순서 줄,
//   "이 알람은 최근 7일 N번, 30일 M번 났습니다 [가상 운영 데이터]", "주의: …". 소제목 덩어리는 답마다 다르다("문서에서 더 찾은 줄", "운영 기록 [가상]" …).
// 규칙: ① 덩어리는 **원래 순서 그대로** 목록이 된다. 모르는 덩어리도 문단으로 남긴다(지우지 않는다). "■ 알람 설명" 앞의 안내 한 줄(이어받기 "N 알람 기준으로 답해요.")도 메모로 맨 앞에 남는다.
//       ② 알람 답이 아니거나 모르는 모양이면 null → 화면은 지금처럼 평문 말풍선.
//       ③ 닫힌 실패: 끝에서 "카드가 보이는 글자"의 낱말 열이 원래 글자와 같은지 확인하고, 다르거나 예외가 나면 null.
export type AlarmRole = 'operator' | 'maintenance' | 'other';
export interface AlarmStep { no: string; role: AlarmRole; label: string; text: string }
export type AlarmCardPart =
  | { kind: 'desc'; title: string; paras: string[] }
  | { kind: 'steps'; title: string; steps: AlarmStep[] }
  | { kind: 'section'; title: string; paras: string[] }
  | { kind: 'ops'; count7: number; count30: number; virtual: boolean }
  | { kind: 'caution'; title: string; paras: string[] }
  | { kind: 'note'; paras: string[] };
export interface AlarmSource { label: string; docNo: string; rev?: string; section: string; onClick?: () => void }
export interface AlarmAnswerCardProps { parts: AlarmCardPart[]; sources: AlarmSource[]; viewerRole?: 'operator' | 'maintenance' }

const STEP = /^★?\s*(\d+(?:-\d+)?)\s*\(([^)]+)\)\s*(.+)$/;          // ★1 (작업자) 글 · 5 (보전) 글 · ★2-1 (작업자) 글
const OPS = /^이 알람은 최근 7일 (\d+)번, 30일 (\d+)번 났습니다( \[가상 운영 데이터\])?$/;
const CAUTION = /^주의\s*[:：]\s*/;

const roleOf = (label: string): AlarmRole => (label.startsWith('작업자') ? 'operator' : label.startsWith('보전') ? 'maintenance' : 'other');
function readStep(line: string): AlarmStep | null {
  const m = STEP.exec(line);
  return m ? { no: m[1], role: roleOf(m[2].trim()), label: m[2].trim(), text: m[3] } : null;
}

/** 낱말(글자·숫자 연속) 열 — 기호(■ ★ [ ] ( ))는 낱말이 아니라서 스타일로 바뀌어도 같다 */
const words = (s: string): string[] => s.match(/[\p{L}\p{N}]+/gu) ?? [];

/** 카드가 보이는 글자를 그리는 순서대로 이은 것 (AlarmAnswerCard.tsx와 같은 순서·같은 글자 — 컴포넌트를 바꾸면 여기도 바꾼다) */
export function cardPlainText(parts: AlarmCardPart[]): string {
  const out: string[] = [];
  for (const p of parts) {
    if (p.kind === 'desc' || p.kind === 'section' || p.kind === 'caution') out.push(p.title, ...p.paras);
    else if (p.kind === 'steps') { if (p.title) out.push(p.title); for (const s of p.steps) out.push(s.no, s.label, s.text); }
    else if (p.kind === 'ops') out.push(`이 알람은 최근 7일 ${p.count7}번, 30일 ${p.count30}번 났습니다`, ...(p.virtual ? ['가상 운영 데이터'] : []));
    else out.push(...p.paras);
  }
  return out.join('\n');
}

/** 카드로 읽을 수 있는 첫 소제목 — 알람 답만 이 글자를 쓴다(비서 blocks_v2 SECTION_V3·CAUSE_HEAD) */
const CARD_FIRST_TITLES = ['■ 알람 설명', '■ 점검 순서 (사내 문서)', '■ 가능한 원인 (사내 문서)'];

function readParts(a: string): AlarmCardPart[] | null {
  const chunks = a.replace(/\r\n?/g, '\n').split(/\n[ \t]*\n/).map((c) => c.split('\n').map((l) => l.trim()).filter(Boolean)).filter((l) => l.length > 0);
  // 알람 답의 첫 소제목 "■ 알람 설명"(blocks_v2 SECTION_V3["card"]) 앞에는 소제목 없는 안내 덩어리가 올 수 있다 — 직전 알람을 이어받으면 비서가
  // 맨 앞에 "N 알람 기준으로 답해요." 한 줄을 붙인다(answer.py _with_ctx_note). 그 앞 덩어리는 메모로 맨 앞에 남기고(지우지 않는다) 카드는 그대로 그린다.
  // 2026-10-21 질문대로 답하기: 묻는 칸만 남긴 알람 답은 첫 덩어리가 "점검 순서"나 "가능한 원인"이다 — 알람 카드 전용 소제목이라 이것들도 카드로 읽는다
  // (안 그러면 평문으로 떨어져 번호 동그라미·역할 알약·사용자별 강조가 빠졌다). 점검 순서 줄이 모르는 꼴이면 아래에서 그대로 포기하고, 끝의 낱말 열 검사도 그대로다.
  const first = chunks.findIndex((l) => l[0].startsWith('■'));
  if (first < 0 || first > 2 || !CARD_FIRST_TITLES.includes(chunks[first][0])) return null;
  const parts: AlarmCardPart[] = [];
  const lead = chunks.slice(0, first);
  if (lead.length > 0) {
    if (lead.some((lines) => lines.some((l) => l.startsWith('■')))) return null;
    parts.push({ kind: 'note', paras: lead.flat() });
  }
  for (const lines of chunks.slice(first)) {
    if (lines[0].startsWith('■')) {
      const title = lines[0].replace(/^■\s*/, '');
      const body = lines.slice(1);
      if (!title || body.some((l) => l.startsWith('■'))) return null;                  // 덩어리 가운데 또 소제목 → 모르는 모양
      if (title === '알람 설명') parts.push({ kind: 'desc', title, paras: body });
      else if (/^점검 순서/.test(title)) {
        const steps = body.map(readStep);
        if (steps.length === 0 || steps.some((s) => s === null)) return null;         // 점검 순서 줄이 한 줄이라도 모르는 꼴이면 카드를 포기한다
        parts.push({ kind: 'steps', title, steps: steps as AlarmStep[] });
      } else parts.push({ kind: 'section', title, paras: body });
      continue;
    }
    if (lines.some((l) => l.startsWith('■'))) return null;
    const joined = lines.join('\n');
    const ops = OPS.exec(joined);
    if (ops) { parts.push({ kind: 'ops', count7: +ops[1], count30: +ops[2], virtual: !!ops[3] }); continue; }
    if (CAUTION.test(lines[0])) { parts.push({ kind: 'caution', title: '주의', paras: [lines[0].replace(CAUTION, ''), ...lines.slice(1)].filter(Boolean) }); continue; }
    const steps = lines.map(readStep);
    if (steps.every((s) => s !== null)) { parts.push({ kind: 'steps', title: '', steps: steps as AlarmStep[] }); continue; }
    const last = parts[parts.length - 1];
    if (last && (last.kind === 'desc' || last.kind === 'section' || last.kind === 'note')) last.paras.push(...lines);   // 소제목 없이 이어지는 덩어리는 앞 덩어리의 문단
    else parts.push({ kind: 'note', paras: lines });
  }
  return parts;
}

export function parseAlarmAnswer(a: string, sources: { doc_no: string; doc_name: string; rev?: string; section: string }[], openSource: (d: string, s: string) => void): AlarmAnswerCardProps | null {
  try {
    if (typeof a !== 'string') return null;
    const parts = readParts(a);
    if (!parts) return null;
    const x = words(a), y = words(cardPlainText(parts));
    if (x.length !== y.length || x.some((w, i) => w !== y[i])) return null;             // 닫힌 실패: 글자가 하나라도 다르면 평문
    return {
      parts,
      sources: (sources ?? []).map((s) => ({ label: s.doc_name, docNo: s.doc_no, rev: s.rev, section: s.section, onClick: () => openSource(s.doc_no, s.section) })),
    };
  } catch { return null; }
}
