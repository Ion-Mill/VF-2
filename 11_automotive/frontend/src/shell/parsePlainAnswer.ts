// 일반 답(알람 카드가 아닌 모든 답)의 "■ 제목" 줄을 소제목으로 읽는다 — React 없는 순수 함수 (tools/chat_bubble_check.mjs가 변환해 시험한다).
// 입력 = chat_mapping.to_answer_text 가 만든 글자: 빈 줄로 나뉜 덩어리, 소제목 덩어리의 첫 줄은 "■ 제목", 그 아래는 "1. …" 목록이나 문장.
// 규칙: ① "■ 제목" 줄만 소제목이 된다("■" 앞 공백은 허용, 제목이 비면 소제목이 아니다). 그 밖의 줄은 **글자와 줄바꿈 그대로** 본문에 남는다(지우지 않는다).
//       ② 소제목이 하나도 없으면 null — 화면은 지금처럼 글자 전체를 평문 한 덩어리로 그린다.
//       ③ 닫힌 실패: 끝에서 낱말 열이 원래 글자와 같은지 확인하고, 다르거나 예외가 나면 null. "■" 기호는 낱말이 아니라 스타일로 바뀌어도 같다.
export interface PlainSection { title: string | null; body: string }   // title === null = 첫 소제목 앞의 글(머리 문단)

const HEAD = /^\s*■\s*(\S.*?)\s*$/;
const words = (s: string): string[] => s.match(/[\p{L}\p{N}]+/gu) ?? [];
const trimBlank = (lines: string[]): string => {
  let a = 0, b = lines.length;
  while (a < b && lines[a].trim() === '') a++;
  while (b > a && lines[b - 1].trim() === '') b--;
  return lines.slice(a, b).join('\n');
};

export function parsePlainAnswer(a: string): PlainSection[] | null {
  try {
    if (typeof a !== 'string') return null;
    const lines = a.replace(/\r\n?/g, '\n').split('\n');
    if (!lines.some((l) => HEAD.test(l))) return null;
    const out: PlainSection[] = [];
    let title: string | null = null;
    let buf: string[] = [];
    const flush = () => {
      const body = trimBlank(buf);
      if (title !== null || body !== '') out.push({ title, body });
      buf = [];
    };
    for (const l of lines) {
      const m = HEAD.exec(l);
      if (m) { flush(); title = m[1]; } else buf.push(l);
    }
    flush();
    const x = words(a), y = words(out.flatMap((s) => [s.title ?? '', s.body]).join('\n'));
    if (x.length !== y.length || x.some((w, i) => w !== y[i])) return null;
    return out;
  } catch { return null; }
}
