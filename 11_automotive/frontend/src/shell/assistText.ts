// 비서(외부 LLM)가 다듬은 문장을 시연 서버에 묻는다 (2026-10-17). 시연 서버가 MOM_LLM_COMPOSE=1이 아니거나 비서가 꺼져 있거나 실패하면
// 늘 {ready:false}라서 화면은 원문(프로그램 문장) 그대로다. 준비되면 지침카드는 비서 정리를 본문으로 보이되 원문을 "원문 보기"에 남긴다 (2026-10-19). 묻는 쪽이 기다리지 않는다.
// 브리핑 "먼저 챙길 일"도 같은 방식이다 (2026-10-19): 순위 묶음마다 준비된 것부터 바꿔 끼우고, [원문 보기]로 프로그램 문구를 언제나 볼 수 있다.
import { useEffect, useState } from 'react';
import { api } from './live';

/** 알람 지침카드 '먼저 할 일'(DOC-03 ★ 줄)을 비서가 쉽게 풀어 쓴 줄을 묻는다. 알람이 뜰 때 한 번 불러 두면 카드가 열릴 때는 준비돼 있다. */
export function askGuideCard(code: string, steps: string[]) {
  return api<{ ready: boolean; lines?: string[] }>('assist/guide-card-text', { code, steps });
}

/** 카드 "먼저 할 일"에 쓸 '비서 정리' 줄. 준비될 때까지 4초마다 최대 30번 묻고, 끝내 안 되면 null(원문만 보임). */
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

/** 브리핑 "먼저 챙길 일"의 항목 줄을 순위 묶음별로 묻는다. 안전(순위 0) 줄은 보내지 않는다. 준비된 묶음부터 받아 간다. */
export type BriefGroup = { rank: string; lines: string[] };
export function askBriefing(shift: string, groups: BriefGroup[]) {
  return api<{ ready: boolean; groups: { rank: string; ready: boolean; lines?: string[] }[] }>('assist/briefing-text', { shift, groups });
}

/** 브리핑 "먼저 챙길 일"에 쓸 '비서 정리' 줄: {순위: 줄들}. 준비된 묶음만 들어 있고(나머지·꺼짐·실패는 원문 그대로),
 *  지금 화면의 원문 줄과 똑같은 묶음에서 온 것만 돌려준다 — 알람이 바뀌었는데 옛 문장이 남지 않게. 준비될 때까지 4초마다 최대 30번 묻는다. */
export function useBriefingText(shift: string | undefined, groups: BriefGroup[]): Record<string, string[]> {
  const [done, setDone] = useState<Record<string, { key: string; lines: string[] }>>({});
  const sig = shift && groups.length ? JSON.stringify([shift, groups]) : '';
  useEffect(() => {
    if (!sig) return;
    let alive = true;
    let n = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const again = () => { if (alive && ++n < 30) timer = setTimeout(ask, 4000); };
    const ask = () => {
      askBriefing(shift!, groups)
        .then((r) => {
          if (!alive) return;
          setDone((prev) => {
            const next = { ...prev };
            for (const g of r.groups) {
              const src = groups.find((x) => x.rank === g.rank);
              if (g.ready && g.lines && src && g.lines.length === src.lines.length) next[g.rank] = { key: src.lines.join('\n'), lines: g.lines };
            }
            return next;
          });
          if (!r.ready) again();
        })
        .catch(again);
    };
    ask();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps
  const out: Record<string, string[]> = {};
  for (const g of groups) { const d = done[g.rank]; if (d && d.key === g.lines.join('\n')) out[g.rank] = d.lines; }
  return out;
}
