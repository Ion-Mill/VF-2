'use client';
// SCR-17 수정 이력 — 버전 목록 + 바뀐 부분(− 빼기 / + 더하기), 비서·프로그램 / 사람 꼬리표 (색만으로 구분하지 않음).
// 대상: 작업지시서·작업기록서(간이 포함)·교대·일일 보고서·사내 문서·예방 정비 실시 기록·출하 기록. 9월 = document_revision.csv, 10/1 = 화면 기록.
// 시안(2026-10-20): 왼쪽 버전 타임라인, 오른쪽 바뀐 부분 카드. 모든 문서 보기는 문서 종류 칩으로 거른다.
import { useState } from 'react';
import { BTN, useApp } from './ctx';
import { hm, md, useFetch } from './live';
import { userName } from './model';
import type { Revision } from './workflow';
import { Chip, DocHead, DocPage, Sec } from './DocKit';

const TYPE: Record<string, string> = { WO: '정비 작업지시서', WR: '작업기록서', SR: '간이 작업기록', SHIFT: '교대 보고서', DAILY: '일일 보고서', MAINT_WO: '정비 작업지시서', WORK_RECORD: '작업기록서', QUICK_RECORD: '간이 작업기록', SHIFT_REPORT: '교대 보고서', DAILY_REPORT: '일일 보고서', PM_RECORD: '예방 정비 실시 기록', SHIPMENT: '출하 기록', INTERNAL_DOC: '사내 문서' };
const SRV: Record<string, string> = { SHIFT: 'SHIFT_REPORT', DAILY: 'DAILY_REPORT' };
// 서버가 고친 칸은 칸 이름이 영어로 온다 (backend/app/services/documents.py fields) → 한글로 (9월 기록은 이미 한글, 2026-10-20)
const FIELD: Record<string, string> = { notable_text: '특이 사항', handover_text: '인계 사항', issues_summary: '오늘의 문제', title: '제목', symptom: '증상', cause: '원인', action: '조치', worker_memo: '작업자 메모', end_at: '끝난 시각', repair_min: '수리 시간', result: '결과', measured_value: '측정값', measured_unit: '단위', memo: '메모' };
const blocked = (msg: string) => <div className="flex flex-col items-center gap-1 rounded-2xl border border-dashed border-slate-400 bg-white px-4 py-8 text-center"><span className="text-[28px]">🔒</span><b>{msg}</b></div>;

export function RevisionsScreen() {
  const { key, wos, wrs, srs, back, role, user, go } = useApp();
  const [kind, id] = (key ?? ':').split(':');
  const all = useFetch<{ revisions: Record<string, any>[]; changes: Record<string, Record<string, string>[]> }>('documents/revisions');
  const one = useFetch<Record<string, any>>(kind === 'SHIFT' ? `reports/shift/${id}` : kind === 'DAILY' ? `reports/daily/${id}` : null, 0, [key]);
  const [sel, setSel] = useState(0);
  const [type, setType] = useState('');

  let revs: Revision[] = [];
  if (kind === 'WO') revs = wos.find((w) => w.no === id)?.revisions ?? [];
  if (kind === 'WR') revs = wrs.find((w) => w.no === id)?.revisions ?? [];
  if (kind === 'SR') revs = srs.find((w) => w.no === id)?.revisions ?? [];
  if (SRV[kind] && one.data) {
    const ch = one.data.changes ?? {};
    revs = (one.data.revisions ?? []).map((x: Record<string, any>) => ({
      v: Number(x.version_no), kind: x.author_kind === 'AI' ? 'AI비서 초안' : x.status_after === 'CONFIRMED' ? (x.reason ? '확정 후 수정' : '확정') : '수정',
      by: x.author_kind === 'AI' ? '비서' : userName(x.author_user_id), byRole: x.author_kind === 'AI' ? 'PROGRAM' : 'SUP', at: x.created_at, reason: x.reason || undefined,
      changes: (x.changes ?? ch[x.revision_id] ?? []).map((c: Record<string, string>) => ({ field: FIELD[c.field_name] ?? c.field_name, before: c.before_value ?? '', after: c.after_value ?? '' })),
    }));
  }
  const ownOnly = role === 'OPR' && kind !== 'SR'; // OPR은 자기 문서(간이 작업기록)만 (FR-AST-03-08)
  const ownSr = kind === 'SR' && srs.find((w) => w.no === id);
  const isBlocked = role === 'OPR' && (ownOnly || (ownSr && ownSr.savedBy !== user.name && ownSr.by !== user.name));
  const cur = revs[Math.min(sel, revs.length - 1)];
  const who = (r: Revision) => (r.byRole === 'PROGRAM' ? <Chip tone="acc">비서·프로그램</Chip> : <Chip tone="ok">{r.by}</Chip>);

  if (!kind) {
    const list = [...(all.data?.revisions ?? [])].reverse();
    const types = [...new Set(list.map((x) => TYPE[x.doc_type] ?? x.doc_type))];
    const shown = list.filter((x) => !type || (TYPE[x.doc_type] ?? x.doc_type) === type);
    return (
      <DocPage width={1100}>
        <DocHead title="수정 이력" sub="모든 문서 · 최근 순" right={<button onClick={back} className={BTN}>닫기</button>} />
        {role === 'OPR' ? blocked('작업자는 자기가 쓴 간이 작업기록의 이력만 볼 수 있습니다') : (<>
          <div className="flex flex-wrap gap-1.5">{['', ...types].map((t) => <button key={t || '전체'} onClick={() => setType(t)} className={`h-9 rounded-full border px-3 text-[13px] font-semibold ${type === t ? 'border-[#1c2530] bg-[#1c2530] text-white' : 'border-slate-300 bg-white'}`}>{t || '전체'}</button>)}</div>
          <div className="overflow-x-auto rounded-2xl border border-slate-300 bg-white">
            <table className="w-full min-w-[640px] text-left text-[14px]"><thead className="text-[12.5px] text-slate-500"><tr>{['시각', '문서', '번호', '버전', '누가', '사유'].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr></thead>
              <tbody>{shown.slice(0, 150).map((x) => <tr key={x.revision_id} onClick={() => SRV.SHIFT === x.doc_type ? go('revs', `SHIFT:${x.doc_key}`) : x.doc_type === 'DAILY_REPORT' ? go('revs', `DAILY:${x.doc_key}`) : undefined} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-2 font-mono">{md(x.created_at)} {hm(x.created_at)}</td><td className="px-3 py-2">{TYPE[x.doc_type] ?? x.doc_type}</td><td className="px-3 py-2 font-mono">{x.doc_key}</td><td className="px-3 py-2 font-mono">v{x.version_no}</td>
                <td className="px-3 py-2">{x.author_kind === 'AI' ? <Chip tone="acc">비서</Chip> : <Chip>{userName(x.author_user_id)}</Chip>}</td><td className="px-3 py-2">{x.reason || <span className="text-slate-400">—</span>}</td></tr>)}</tbody></table>
          </div>
        </>)}
      </DocPage>
    );
  }
  return (
    <DocPage width={1100}>
      <DocHead title="수정 이력" sub={`${TYPE[kind]} ${id}`} right={<><button onClick={() => go('revs', null)} className={BTN}>모든 문서 보기</button><button onClick={back} className={BTN}>닫기</button></>} />
      {isBlocked ? blocked('작업자는 자기가 쓴 간이 작업기록의 이력만 볼 수 있습니다') : revs.length === 0 ? <Sec title="버전 없음"><span className="text-[14px] text-slate-500">저장하면 생깁니다</span></Sec> : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[300px_minmax(0,1fr)]">
          <ol className="flex flex-col gap-1.5">
            {revs.map((r, i) => (
              <li key={i}><button onClick={() => setSel(i)} aria-pressed={i === sel} className={`flex w-full flex-col gap-1 rounded-xl border px-3 py-2 text-left text-[14px] ${i === sel ? 'border-[#0d7a93] bg-[#e3f3f7]' : 'border-slate-300 bg-white hover:bg-slate-50'}`}>
                <b>v{r.v} · {r.kind}{/확정|승인|확인/.test(r.kind) ? ' 🔒' : ''}</b>
                <span className="text-[12.5px] text-slate-500">{r.by} · {md(r.at)} {hm(r.at)}</span>
                {r.reason && <span className="text-[12.5px]">사유: {r.reason}</span>}
                {r.changes.length > 0 && <span><Chip tone="acc">{r.changes.length}칸 바뀜</Chip></span>}
              </button></li>
            ))}
          </ol>
          <Sec title={cur.v === 0 ? '처음 버전' : `바뀐 부분 v${cur.v - 1} → v${cur.v}`} right={who(cur)}>
            {cur.changes.length === 0 ? (cur.v === 0 ? null : <span className="text-[14px] text-slate-500">칸 변경 없음 (상태만 바뀜)</span>) : (
              <ul className="flex flex-col gap-2 text-[14px]">{cur.changes.map((c, i) => (
                <li key={i} className="rounded-xl border border-slate-300 p-3"><b>{c.field}</b>
                  {c.before && <div className="mt-1 text-[#c22a2f]">− {c.before}</div>}
                  <div className="mt-1 rounded bg-[#e0f2e8] px-2 py-1 text-[#127a46]">+ {c.after || '(없음)'}</div>
                </li>))}</ul>
            )}
          </Sec>
        </div>
      )}
    </DocPage>
  );
}
