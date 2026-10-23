'use client';
// SCR-24 사내 문서 보기 — DOC-01~07 + 용어집 (가상사내문서/*.md, API-DOCS-01). 출처를 누르면 팝업 창으로 그 절을 열고 강조. 원문 열기 버튼은 없다 (D-04).
// 3단 리더 (왼쪽 문서·목차, 가운데 본문) + 위 줄 검색·글자 크기·출처 켜기 (2026-10-23 시안 A+C)
import { useEffect, useRef, useState } from 'react';
import { BTN, CARD, PAGE, useApp } from './ctx';
import { useFetch } from './live';

type Sec = { section: string; title: string; level: number; text?: string };
type Doc = { doc_no: string; doc_name: string; rev: string; rev_date: string; sections: Sec[] };

const SRC = /\s*\[(실제|참고|가상|제안|선택 필요)[^\]]*\]/g;      // 줄 안 출처 표시 — 출처 끔이면 숨김
const SRC_COL = /^(출처|원문|근거)$/;                               // 출처만 담은 표 칸 ("근거 수준"은 남김)
const SIZES = [['기본', 'text-body'], ['크게', 'text-[18px]'], ['아주 크게', 'text-band']] as const;   // 16 · 18 · 20px
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// 찾는 말에 형광 칠
function mark(s: string, q: string): React.ReactNode {
  if (!q) return s;
  return s.split(new RegExp(`(${esc(q)})`, 'gi')).map((p, i) => (i % 2 ? <mark key={i} className="rounded bg-warn-bg px-0.5 text-ink">{p}</mark> : p));
}

// 아주 작은 마크다운 그리기: 표·목록·굵게·문단 (사내 문서 안의 [실제]/[참고] 출처는 src일 때만 보임)
function Md({ text, q, src }: { text: string; q: string; src: boolean }) {
  const lines = text.split('\n'), out: React.ReactNode[] = [];
  const inline = (raw: string) => {
    const s = src ? raw : raw.replace(SRC, '');
    return s.split(/(\*\*[^*]+\*\*)/).map((p, i) => (p.startsWith('**') ? <b key={i}>{mark(p.slice(2, -2), q)}</b> : <span key={i}>{mark(p, q)}</span>));
  };
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { const c = lines[i].trim().replace(/^\||\|$/g, '').split('|').map((x) => x.trim()); if (!c.every((x) => /^:?-+:?$/.test(x))) rows.push(c); i++; }
      i--;
      const keep = rows[0].map((h, j) => src || !SRC_COL.test(h) ? j : -1).filter((j) => j >= 0);
      out.push(<div key={i} className="my-2 overflow-x-auto"><table className="w-full border-collapse text-[0.94em]"><tbody>{rows.map((r, k) => <tr key={k} className={k === 0 ? 'bg-tile font-semibold' : 'border-t border-line-soft'}>{keep.map((j) => <td key={j} className="border border-line-soft px-2 py-1 align-top">{inline(r[j] ?? '')}</td>)}</tr>)}</tbody></table></div>);
    } else if (/^\s*[-*] /.test(l)) out.push(<li key={i} className="ml-5 list-disc">{inline(l.replace(/^\s*[-*] /, ''))}</li>);
    else if (l.trim().startsWith('```')) { const b: string[] = []; i++; while (i < lines.length && !lines[i].trim().startsWith('```')) b.push(lines[i++]); out.push(<pre key={i} className="my-2 overflow-x-auto rounded bg-tile p-2 text-[0.94em]">{b.join('\n')}</pre>); }
    else if (l.trim()) out.push(<p key={i} className="my-1">{inline(l)}</p>);
  }
  return <div className="leading-relaxed">{out}</div>;
}

const label = (s: Sec) => `${/^\d/.test(s.section) ? `§${s.section} ` : ''}${s.title}`;

function DocView({ docNo, section, onClose }: { docNo: string; section?: string; onClose?: () => void }) {
  const { go } = useApp();
  const list = useFetch<{ docs: Doc[] }>('internal-docs');
  const [cur, setCur] = useState(docNo);
  const [q, setQ] = useState('');
  const [size, setSize] = useState(0);
  const [src, setSrc] = useState(false);
  const [at, setAt] = useState<Sec | null>(null);
  const d = useFetch<Doc>(`internal-docs/${cur}`, 0, [cur]);
  const refs = useRef(new Map<Sec, HTMLDivElement>());
  const target = cur === docNo ? section?.replace(/^§/, '') : undefined;
  const hit = d.data?.sections.find((s) => s.section === target) ?? d.data?.sections.find((s) => target && s.section.startsWith(target + '.'));
  const needle = q.trim().toLowerCase();
  const shown = (d.data?.sections ?? []).filter((s) => !needle || `${s.title}\n${s.text ?? ''}`.toLowerCase().includes(needle));
  const toc = shown.filter((s) => s.level >= 2 && s.level <= 3);
  const jump = (s: Sec) => { setAt(s); refs.current.get(s)?.scrollIntoView({ block: 'start' }); };   // 문서가 길어 부드러운 스크롤은 1초 넘게 걸림
  useEffect(() => { if (hit) { setAt(hit); refs.current.get(hit)?.scrollIntoView({ block: 'start' }); } }, [hit, d.data]);
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line-soft pb-2">
        <label className="flex h-11 min-w-[220px] flex-1 items-center gap-2 rounded-ctl border border-line px-3">
          <span aria-hidden="true" className="text-ink-3">⌕</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && setQ('')} placeholder="이 문서에서 찾기 (예: 992, 잠금)" aria-label="이 문서에서 찾기" className="h-full min-w-0 flex-1 bg-transparent text-body outline-none" />
          {q && <button onClick={() => setQ('')} aria-label="찾기 지우기" className="text-small text-ink-2">✕</button>}
        </label>
        <div role="group" aria-label="글자 크기" className="flex h-11 overflow-hidden rounded-ctl border border-line">
          {SIZES.map(([name, cls], k) => <button key={name} onClick={() => setSize(k)} aria-pressed={size === k} className={`px-3 font-semibold ${cls}${size === k ? 'bg-brand-tint text-brand-ink' : 'text-ink-2 hover:bg-tile'}`}>가<span className="sr-only">{name}</span></button>)}
        </div>
        <button onClick={() => setSrc((v) => !v)} aria-pressed={src} className={`${BTN} ${src ? 'border-brand bg-brand-tint text-brand-ink' : ''}`}>출처 {src ? '켬' : '끔'}</button>
        {onClose && <button onClick={onClose} className={`${BTN} ml-auto`}>✕ 닫기 → 원래 화면</button>}
      </div>
      <div className="flex min-h-0 flex-1 gap-3 pt-2">
        <nav aria-label="문서와 목차" className="w-[230px] shrink-0 overflow-y-auto border-r border-line-soft pr-2 text-small max-[900px]:hidden">
          <div className="mb-1 text-ink-3">문서</div>
          {(list.data?.docs ?? []).map((x) => <button key={x.doc_no} onClick={() => { setCur(x.doc_no); setAt(null); }} className={`block min-h-10 w-full rounded-ctl px-2 py-1 text-left ${x.doc_no === cur ? 'bg-brand-tint font-semibold text-brand-ink' : 'text-ink-2 hover:bg-tile'}`}>{x.doc_no === 'GLOSSARY' ? '00 용어집' : `${x.doc_no} ${x.doc_name}`}</button>)}
          <div className="mb-1 mt-3 text-ink-3">목차{needle && ` · ${shown.length}곳`}</div>
          {toc.map((s) => <button key={s.section + s.title} onClick={() => jump(s)} className={`block min-h-9 w-full py-1 pr-1 text-left ${s.level >= 3 ? 'pl-5' : 'pl-2 font-semibold'} ${s === at ? 'border-l-4 border-brand text-ink' : 'text-ink-2 hover:text-ink'}`}>{mark(label(s), needle && q.trim())}</button>)}
        </nav>
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto pr-2">
          {!d.data ? <p className="p-3 text-ink-2">불러오는 중…</p> : (
            <div className={`mx-auto max-w-[880px] ${SIZES[size][1]}`}>
              <div className="border-b border-line-soft pb-2 text-small text-ink-2"><b className="text-ink">{d.data.doc_no} {d.data.doc_name}</b> · {d.data.rev} ({d.data.rev_date}) · 승인 MGR · <span className="rounded bg-tile px-1">가상 사내 문서</span>
                <button onClick={() => go('revs')} className="ml-2 underline">수정 이력</button> · 개정 승인 대기 없음</div>
              {target && !hit && <p className="mt-2 text-warn">이 절이 없습니다 (개정으로 바뀌었을 수 있음) — 최신 {d.data.rev}</p>}
              {needle && !shown.length && <p className="mt-3 text-ink-2">이 문서에 "{q.trim()}"이(가) 없습니다. 왼쪽에서 다른 문서를 골라 보세요.</p>}
              {shown.map((s) => (
                <div key={s.section + s.title} ref={(el) => { if (el) refs.current.set(s, el); else refs.current.delete(s); }} className={`mt-4 scroll-mt-2 ${s === hit ? 'rounded-ctl border-l-4 border-brand bg-brand-tint p-2' : ''}`}>
                  <div className={s.level <= 2 ? 'text-[1.25em] font-bold' : 'text-[1.08em] font-bold'}>{mark(label(s), needle && q.trim())}</div>
                  {s.text && <Md text={s.text} q={needle && q.trim()} src={src} />}
                </div>))}
            </div>)}
        </div>
      </div>
    </div>
  );
}

export function SourcePopup({ doc, section, onClose }: { doc: string; section: string; onClose: () => void }) {
  return (
    <div role="dialog" aria-label="사내 문서" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6">
      <div className="h-[86vh] w-full max-w-[1200px] rounded-tile bg-white p-4 shadow-2xl"><DocView docNo={doc} section={section} onClose={onClose} /></div>
    </div>
  );
}

export function DocsScreen() {
  const { back } = useApp();
  return (
    <div className={PAGE}>
      <div className={`${CARD} h-[calc(100%-8px)]`}>
        <div className="mb-2 flex justify-end"><button onClick={back} className={BTN}>닫기</button></div>
        <div className="h-[calc(100%-56px)]"><DocView docNo="DOC-01" /></div>
      </div>
    </div>
  );
}
