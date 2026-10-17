// 비서(외부 LLM)가 다듬은 문장을 시연 서버에 묻는다 (2026-10-17). 시연 서버가 MOM_LLM_COMPOSE=1이 아니거나 비서가 꺼져 있거나 실패하면
// 늘 {ready:false}라서 화면에는 아무것도 더해지지 않는다 — 원문(프로그램 문장)은 언제나 그대로 보인다. 묻는 쪽이 기다리지 않는다.
import { useEffect, useState } from 'react';
import { api } from './live';

/** 알람 지침카드 '먼저 할 일'(DOC-03 ★ 줄)을 비서가 쉽게 풀어 쓴 줄을 묻는다. 알람이 뜰 때 한 번 불러 두면 카드가 열릴 때는 준비돼 있다. */
export function askGuideCard(code: string, steps: string[]) {
  return api<{ ready: boolean; lines?: string[] }>('assist/guide-card-text', { code, steps });
}

/** 카드에 붙일 '비서 풀이' 줄. 준비될 때까지 4초마다 최대 30번 묻고, 끝내 안 되면 null(아무것도 안 보임). */
export function useGuideCardText(code: string | undefined, steps: string[] | undefined): string[] | null {
  const [lines, setLines] = useState<string[] | null>(null);
  const key = code && steps && steps.length ? `${code}|${steps.join('\n')}` : '';
  useEffect(() => {
    setLines(null);
    if (!key) return;
    let alive = true;
    let n = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const again = () => { if (alive && ++n < 30) timer = setTimeout(ask, 4000); };
    const ask = () => {
      askGuideCard(code!, steps!)
        .then((r) => { if (!alive) return; if (r.ready && r.lines && r.lines.length === steps!.length) setLines(r.lines); else again(); })
        .catch(again);
    };
    ask();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return lines;
}
