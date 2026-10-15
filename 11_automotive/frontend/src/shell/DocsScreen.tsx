'use client';
// SCR-24 사내 문서 보기 — DOC-01~07 + 용어집 (가상사내문서/*.md, API-DOCS-01). 출처를 누르면 팝업 창으로 그 절을 열고 강조. 원문 열기 버튼은 없다 (D-04).
import { useEffect, useRef, useState } from 'react';
import { BTN, CARD, PAGE, useApp } from './ctx';
import { useFetch } from './live';

type Doc = { doc_no: string; doc_name: string; rev: string; rev_date: string; sections: { section: string; title: string; level: number; text?: string }[] };

// 아주 작은 마크다운 그리기: 표·목록·굵게·문단 (사내 문서 안의 [실제]/[참고] 출처는 그대로)
function Md({ text }: { text: string }) {
  const lines = text.split('\n'), out: React.ReactNode[] = [];
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*)/).map((p, i) => (p.startsWith('**') ? <b key={i}>{p.slice(2, -2)}</b> : p));
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { const c = lines[i].trim().replace(/^\||\|$/g, '').split('|').map((x) => x.trim()); if (!c.every((x) => /^:?-+:?$/.test(x))) rows.push(c); i++; }
      i--;
      out.push(<table key={i} className="my-2 w-full border-collapse text-[13px]"><tbody>{rows.map((r, k) => <tr key={k} className={k === 0 ? 'bg-slate-100 font-semibold' : 'border-t border-slate-200'}>{r.map((c, j) => <td key={j} className="border border-slate-200 px-2 py-1 align-top">{inline(c)}</td>)}</tr>)}</tbody></table>);
    } else if (/^\s*[-*] /.test(l)) out.push(<li key={i} className="ml-5 list-disc">{inline(l.replace(/^\s*[-*] /, ''))}</li>);
    else if (l.trim().startsWith('```')) { const b: string[] = []; i++; while (i < lines.length && !lines[i].trim().startsWith('```')) b.push(lines[i++]); out.push(<pre key={i} className="my-2 overflow-x-auto rounded bg-slate-50 p-2 text-[12px]">{b.join('\n')}</pre>); }
    else if (l.trim()) out.push(<p key={i} className="my-1">{inline(l)}</p>);
  }
  return <div className="text-[14px] leading-relaxed">{out}</div>;
}

function DocView({ docNo, section, onClose }: { docNo: string; section?: string; onClose?: () => void }) {
  const { go } = useApp();
  const list = useFetch<{ docs: Doc[] }>('internal-docs');
  const [cur, setCur] = useState(docNo);
  const d = useFetch<Doc>(`internal-docs/${cur}`, 0, [cur]);
  const ref = useRef<HTMLDivElement | null>(null);
  const target = cur === docNo ? section?.replace(/^§/, '') : undefined;
  const hit = d.data?.sections.find((s) => s.section === target) ?? d.data?.sections.find((s) => target && s.section.startsWith(target + '.'));
  useEffect(() => { if (hit && ref.current) ref.current.scrollIntoView({ block: 'start' }); }, [hit, d.data]);
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 pb-2">
        {(list.data?.docs ?? []).map((x) => <button key={x.doc_no} onClick={() => setCur(x.doc_no)} className={`h-10 rounded-md border px-2 text-[13px] font-semibold ${x.doc_no === cur ? 'border-[#0f9fbd] bg-[#e8f6fa]' : 'border-slate-300'}`}>{x.doc_no === 'GLOSSARY' ? '00 용어집' : x.doc_no}</button>)}
        {onClose && <button onClick={onClose} className={`${BTN} ml-auto`}>✕ 닫기 → 원래 화면</button>}
      </div>
      {!d.data ? <p className="p-3 text-slate-500">불러오는 중…</p> : (<>
        <div className="border-b border-slate-200 py-2 text-[14px]"><b>{d.data.doc_no} {d.data.doc_name}</b> · {d.data.rev} ({d.data.rev_date}) · 승인 MGR · <span className="rounded bg-slate-100 px-1 text-[12px]">가상 사내 문서</span>
          <button onClick={() => go('revs')} className="ml-2 underline">수정 이력</button> <span className="text-[12px] text-slate-500">· 개정 승인 대기 없음</span></div>
        {target && !hit && <p className="mt-2 text-[14px] text-[#9a6200]">이 절이 없습니다 (개정으로 바뀌었을 수 있음) — 최신 {d.data.rev}</p>}
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          {d.data.sections.map((s) => (
            <div key={s.section + s.title} ref={s === hit ? ref : undefined} className={`mt-3 ${s === hit ? 'rounded-md border-l-4 border-[#0f9fbd] bg-[#f0fafc] p-2' : ''}`}>
              <div className={s.level <= 2 ? 'text-[17px] font-bold' : 'text-[15px] font-bold'}>{/^\d/.test(s.section) ? `§${s.section} ` : ''}{s.title}</div>
              {s.text && <Md text={s.text} />}
            </div>))}
        </div>
      </>)}
    </div>
  );
}

export function SourcePopup({ doc, section, onClose }: { doc: string; section: string; onClose: () => void }) {
  return (
    <div role="dialog" aria-label="사내 문서" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6">
      <div className="h-[86vh] w-full max-w-[1000px] rounded-xl bg-white p-4 shadow-2xl"><DocView docNo={doc} section={section} onClose={onClose} /></div>
    </div>
  );
}

export function DocsScreen() {
  const { back } = useApp();
  return (
    <div className={PAGE}>
      <div className={`${CARD} h-[calc(100%-8px)]`}>
        <div className="mb-2 flex items-center justify-between"><h2 className="text-[19px] font-bold">사내 문서</h2><button onClick={back} className={BTN}>닫기</button></div>
        <div className="h-[calc(100%-56px)]"><DocView docNo="DOC-01" /></div>
      </div>
    </div>
  );
}
