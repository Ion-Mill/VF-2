'use client';
// SCR-17 수정 이력 — 버전 목록 + 바뀐 부분(− 빼기 / + 더하기), [프로그램]·[AI]·[수정] 꼬리표 (색만으로 구분하지 않음).
// 대상: 작업지시서·작업기록서(간이 포함)·교대·일일 보고서·사내 문서·예방 정비 실시 기록·출하 기록. 9월 = document_revision.csv, 10/1 = 화면 기록.
import { useState } from 'react';
import { BTN, CARD, PAGE, useApp } from './ctx';
import { hm, md, useFetch } from './live';
import { userName } from './model';
import type { Revision } from './workflow';

const TYPE: Record<string, string> = { WO: '정비 작업지시서', WR: '작업기록서', SR: '간이 작업기록', SHIFT: '교대 보고서', DAILY: '일일 보고서', MAINT_WO: '정비 작업지시서', WORK_RECORD: '작업기록서', QUICK_RECORD: '간이 작업기록', SHIFT_REPORT: '교대 보고서', DAILY_REPORT: '일일 보고서', PM_RECORD: '예방 정비 실시 기록', SHIPMENT: '출하 기록', INTERNAL_DOC: '사내 문서' };
const SRV: Record<string, string> = { SHIFT: 'SHIFT_REPORT', DAILY: 'DAILY_REPORT' };

export function RevisionsScreen() {
  const { key, wos, wrs, srs, back, role, user, go } = useApp();
  const [kind, id] = (key ?? ':').split(':');
  const all = useFetch<{ revisions: Record<string, any>[]; changes: Record<string, Record<string, string>[]> }>('documents/revisions');
  const one = useFetch<Record<string, any>>(kind === 'SHIFT' ? `reports/shift/${id}` : kind === 'DAILY' ? `reports/daily/${id}` : null, 0, [key]);
  const [sel, setSel] = useState(0);

  let revs: Revision[] = [];
  if (kind === 'WO') revs = wos.find((w) => w.no === id)?.revisions ?? [];
  if (kind === 'WR') revs = wrs.find((w) => w.no === id)?.revisions ?? [];
  if (kind === 'SR') revs = srs.find((w) => w.no === id)?.revisions ?? [];
  if (SRV[kind] && one.data) {
    const ch = one.data.changes ?? {};
    revs = (one.data.revisions ?? []).map((x: Record<string, any>) => ({
      v: Number(x.version_no), kind: x.author_kind === 'AI' ? 'AI비서 초안' : x.status_after === 'CONFIRMED' ? (x.reason ? '확정 후 수정' : '확정') : '수정',
      by: x.author_kind === 'AI' ? '비서' : userName(x.author_user_id), byRole: x.author_kind === 'AI' ? 'PROGRAM' : 'SUP', at: x.created_at, reason: x.reason || undefined,
      changes: (x.changes ?? ch[x.revision_id] ?? []).map((c: Record<string, string>) => ({ field: c.field_name, before: c.before_value ?? '', after: c.after_value ?? '' })),
    }));
  }
  const ownOnly = role === 'OPR' && kind !== 'SR'; // OPR은 자기 문서(간이 작업기록)만 (FR-AST-03-08)
  const ownSr = kind === 'SR' && srs.find((w) => w.no === id);
  const blocked = role === 'OPR' && (ownOnly || (ownSr && ownSr.savedBy !== user.name && ownSr.by !== user.name));
  const cur = revs[Math.min(sel, revs.length - 1)];

  if (!kind) {
    const list = [...(all.data?.revisions ?? [])].reverse();
    return (
      <div className={PAGE}><div className={CARD}>
        <div className="flex items-center justify-between"><h2 className="text-[19px] font-bold">수정 이력 — 모든 문서 (최근)</h2><button onClick={back} className={BTN}>닫기</button></div>
        <table className="mt-3 w-full text-left text-[14px]"><thead className="text-slate-500"><tr><th>시각</th><th>문서</th><th>번호</th><th>버전</th><th>누가</th><th>사유</th></tr></thead>
          <tbody>{list.slice(0, 150).map((x) => <tr key={x.revision_id} onClick={() => SRV.SHIFT === x.doc_type ? go('revs', `SHIFT:${x.doc_key}`) : x.doc_type === 'DAILY_REPORT' ? go('revs', `DAILY:${x.doc_key}`) : undefined} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
            <td>{md(x.created_at)} {hm(x.created_at)}</td><td>{TYPE[x.doc_type] ?? x.doc_type}</td><td>{x.doc_key}</td><td>v{x.version_no}</td><td>{x.author_kind === 'AI' ? '비서' : userName(x.author_user_id)}</td><td>{x.reason}</td></tr>)}</tbody></table>
      </div></div>
    );
  }
  return (
    <div className={PAGE}>
      <div className={CARD}>
        <div className="flex items-center justify-between"><h2 className="text-[19px] font-bold">수정 이력 — {TYPE[kind]} {id}</h2><button onClick={back} className={BTN}>닫기</button></div>
        {blocked ? <p className="mt-3 text-[14px]">작업자는 자기가 쓴 문서의 이력만 볼 수 있습니다.</p> : revs.length === 0 ? <p className="mt-3 text-[14px] text-slate-500">아직 버전이 없습니다 (저장하면 생깁니다).</p> : (
          <div className="mt-3 grid grid-cols-[320px_1fr] gap-4">
            <ul className="flex flex-col gap-1 border-r border-slate-200 pr-3">
              {revs.map((r, i) => (
                <li key={i}><button onClick={() => setSel(i)} className={`w-full rounded-md px-2 py-2 text-left text-[14px] ${i === sel ? 'bg-[#e8f6fa] font-bold' : 'hover:bg-slate-50'}`}>
                  v{r.v} · {r.kind} · {hm(r.at)} · {r.by} {r.byRole !== 'PROGRAM' ? `(${r.byRole})` : ''}
                  {r.reason && <div className="text-[12px] font-normal text-slate-600">사유: {r.reason}</div>}
                  {/확정|승인|확인/.test(r.kind) && <div className="text-[12px] font-normal">🔒 {r.kind} {r.by} {md(r.at)} {hm(r.at)}</div>}
                </button></li>
              ))}
            </ul>
            <div>
              <h3 className="text-[14px] font-bold text-slate-500">바뀐 부분 (v{cur.v > 0 ? cur.v - 1 : 0} → v{cur.v})</h3>
              {cur.changes.length === 0 ? <p className="text-[14px] text-slate-500">{cur.v === 0 ? '처음 버전 (프로그램 초안 또는 처음 저장)' : '칸 변경 없음 (상태만 바뀜)'}{revs.every((r) => r.byRole === 'PROGRAM') ? ' — 아직 사람이 고치지 않았습니다' : ''}</p> : (
                <ul className="flex flex-col gap-2 text-[14px]">{cur.changes.map((c, i) => (
                  <li key={i} className="rounded border border-slate-200 p-2"><b>{c.field}</b>
                    <div className="text-[#a01e23]">− {c.before || '(없음)'} <span className="rounded bg-slate-100 px-1 text-[11px] text-slate-600">{i === 0 && revs[0]?.byRole === 'PROGRAM' ? '[프로그램]' : '[이전]'}</span></div>
                    <div className="text-[#155a33]">+ {c.after || '(없음)'} <span className="rounded bg-[#e8f6fa] px-1 text-[11px] text-[#5a3bc8]">[수정] {cur.by}</span></div>
                  </li>))}</ul>
              )}
              <p className="mt-2 text-[12px] text-slate-500">범례: [프로그램]·[AI] = 비서·프로그램이 쓴 부분 · [수정] = 사람. 되돌리기 버튼은 없습니다 (FR-AST-COM-12).</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
