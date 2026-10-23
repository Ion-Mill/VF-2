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

const cells = (l: string) => l.trim().replace(/^\||\|$/g, '').split('|').map((x) => x.trim());

// 표지 표(문서 번호·개정·승인·구분) → { 항목: 내용 } — 문서 머리 칩에 씀 (시안 B)
function coverOf(text = '') {
  const m: Record<string, string> = {};
  for (const l of text.split('\n')) if (l.trim().startsWith('|')) { const c = cells(l); if (c.length >= 2) m[c[0]] = c[1].replace(/\*\*/g, ''); }
  return m;
}

const TAG = 'rounded-md px-2.5 py-0.5 text-[0.88em] font-semibold';
// "**정지** / 보전 담당자 — **잠금·표지 필요** (…)" → 심각도 · 누가 · 잠금 색 태그 (시안 B)
function SevTags({ text, q }: { text: string; q: string }) {
  const [main, ...rest] = text.split(' — ');
  const m = main.match(/^\*\*([^*]+)\*\*\s*(?:\/\s*([\s\S]*))?$/);
  if (!m) return null;
  const [who, ...more] = (m[2] ?? '').split('. ');
  const note = [...more, ...rest].join(' — ').replace(/\*\*/g, '').trim();
  const sev = m[1] === '정지' ? 'bg-crit-bg text-crit' : m[1] === '주의' ? 'bg-warn-bg text-warn' : 'bg-tile text-ink-2';
  const lock = /잠금·표지 필요/.test(note) ? 'bg-warn-bg text-warn' : 'bg-tile text-ink-2';
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      <span className={`${TAG} ${sev}`}>심각도 {mark(m[1], q)}</span>
      {who.trim() && <span className={`${TAG} bg-tile text-ink`}>누가 {mark(who.trim(), q)}</span>}
      {note && <span className={`${TAG} ${lock}`}>{mark(note, q)}</span>}
    </div>
  );
}

// 아주 작은 마크다운 그리기: 표·목록·굵게·문단 (사내 문서 안의 [실제]/[참고] 출처는 src일 때만 보임)
// 시안 B: 표지 표는 숨기고(머리 칩), "칸·항목 | 내용" 표는 이름표 위 · 내용 아래로 쌓고 심각도 줄은 태그로
function Md({ text, q, src }: { text: string; q: string; src: boolean }) {
  const lines = text.split('\n'), out: React.ReactNode[] = [];
  const clean = (raw: string) => (src ? raw : raw.replace(SRC, '')).replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/\\_/g, '_').trim();   // [이름](경로) 링크는 이름만
  const inline = (raw: string) => clean(raw).split(/(\*\*[^*]+\*\*)/).map((p, i) => (p.startsWith('**') ? <b key={i}>{mark(p.slice(2, -2), q)}</b> : <span key={i}>{mark(p, q)}</span>));
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { const c = cells(lines[i]); if (!c.every((x) => /^:?-+:?$/.test(x))) rows.push(c); i++; }
      i--;
      const head = rows[0], body = rows.slice(1);
      if (!src && body.some((r) => r[0] === '문서 번호')) continue;   // 표지 표 → 문서 머리 칩
      if (/^(칸|항목)$/.test(head[0]) && head[1] === '내용') {
        const val = (r: string[]) => [r[1], ...r.slice(2).filter((_, k) => !head[k + 2])].filter(Boolean).join(' ');   // 머리 없는 칸에 넘친 내용도 합침
        const extra = head.map((h, j) => (j >= 2 && h && (src || !SRC_COL.test(h)) ? j : -1)).filter((j) => j >= 0);
        const sev = body.filter((r) => /^심각도/.test(r[0]) && /^\*\*/.test(clean(val(r))));
        out.push(
          <div key={i} className="my-2">
            {sev.map((r) => <SevTags key={r[0]} text={clean(val(r))} q={q} />)}
            <dl className="m-0 divide-y divide-line-soft">{body.filter((r) => !sev.includes(r)).map((r, k) => (
              <div key={k} className="py-2">
                <dt className="text-[0.85em] font-semibold text-ink-2">{inline(r[0])}</dt>
                <dd className="m-0 [overflow-wrap:anywhere]">{inline(val(r))}{extra.filter((j) => clean(r[j] ?? '')).map((j) => <div key={j} className="text-[0.85em] text-ink-3">{head[j]} · {inline(r[j])}</div>)}</dd>
              </div>))}</dl>
          </div>);
        continue;
      }
      const keep = rows[0].map((h, j) => src || !SRC_COL.test(h) ? j : -1).filter((j) => j >= 0);
      out.push(<div key={i} className="my-2 overflow-x-auto"><table className="w-full border-collapse text-[0.94em]"><tbody>{rows.map((r, k) => <tr key={k} className={k === 0 ? 'bg-tile font-semibold' : 'border-t border-line-soft'}>{keep.map((j) => <td key={j} className="border border-line-soft px-2 py-1 align-top">{inline(r[j] ?? '')}</td>)}</tr>)}</tbody></table></div>);
    } else if (/^\s*[-*] /.test(l)) out.push(<li key={i} className="ml-5 list-disc">{inline(l.replace(/^\s*[-*] /, ''))}</li>);
    else if (l.trim().startsWith('```')) { const b: string[] = []; i++; while (i < lines.length && !lines[i].trim().startsWith('```')) b.push(lines[i++]); out.push(<pre key={i} className="my-2 overflow-x-auto rounded bg-tile p-2 text-[0.94em]">{b.join('\n')}</pre>); }
    else if (/^-{3,}$/.test(l.trim())) out.push(<hr key={i} className="my-3 border-line-soft" />);
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
  const cover = coverOf(d.data?.sections.find((s) => s.text?.includes('| 문서 번호'))?.text);
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
              <div className="flex flex-wrap items-center gap-2 border-b border-line-soft pb-3">
                <h3 className="mr-1 text-[1.3em] font-bold text-ink">{d.data.doc_no} {d.data.doc_name}</h3>
                <span className={`${TAG} bg-brand-tint text-brand-ink`}>{d.data.rev} · {d.data.rev_date}</span>
                <span className={`${TAG} bg-tile text-ink-2`}>승인 {cover['승인'] ?? '공장 관리자 (MGR)'}</span>
                <span className={`${TAG} bg-tile text-ink-2`}>{(cover['구분'] ?? '가상 사내 문서').split(' (')[0]}</span>
                {cover['개정']?.includes(' — ') && <span className="text-small text-ink-2">{cover['개정'].split(' — ')[1]}</span>}
                <span className="text-small text-ink-2"><button onClick={() => go('revs')} className="underline">수정 이력</button> · 개정 승인 대기 없음</span>
              </div>
              {target && !hit && <p className="mt-2 text-warn">이 절이 없습니다 (개정으로 바뀌었을 수 있음) — 최신 {d.data.rev}</p>}
              {needle && !shown.length && <p className="mt-3 text-ink-2">이 문서에 "{q.trim()}"이(가) 없습니다. 왼쪽에서 다른 문서를 골라 보세요.</p>}
              {shown.map((s) => (
                <div key={s.section + s.title} ref={(el) => { if (el) refs.current.set(s, el); else refs.current.delete(s); }} className={`mt-4 scroll-mt-2 ${s === hit ? 'rounded-ctl border-l-4 border-brand bg-brand-tint p-2' : ''}`}>
                  {s.level > 1 && <div className={s.level <= 2 ? 'text-[1.25em] font-bold' : 'text-[1.08em] font-bold'}>{mark(label(s), needle && q.trim())}</div>}{/* 문서 제목(1단계)은 머리 줄에 있음 */}
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
      <div className={`${CARD} mx-auto h-[calc(100%-8px)] max-w-[1440px]`}>{/* 문서 묶음 다른 화면(DocBox·Revisions)과 같은 폭 */}
        <div className="mb-2 flex justify-end"><button onClick={back} className={BTN}>닫기</button></div>
        <div className="h-[calc(100%-56px)]"><DocView docNo="DOC-01" /></div>
      </div>
    </div>
  );
}
