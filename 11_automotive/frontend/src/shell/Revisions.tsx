'use client';
// SCR-17 수정 이력 — 버전 목록 + 바뀐 부분(− 빼기 / + 더하기), 비서·프로그램 / 사람 꼬리표 (색만으로 구분하지 않음).
// 대상: 작업지시서·작업기록서(간이 포함)·교대·일일 보고서·사내 문서·예방 정비 실시 기록·출하 기록. 9월 = document_revision.csv, 10/1 = 화면 기록.
// 시안(2026-10-20): 왼쪽 버전 타임라인, 오른쪽 바뀐 부분 카드. 모든 문서 보기는 문서 종류 칩으로 거른다.
import { Band as CBand, LockIcon } from './ui';
import { revsBand } from './bands';
import { useState } from 'react';
import { BTN, useApp } from './ctx';
import { hm, md, useFetch } from './live';
import { userName } from './model';
import type { Revision } from './workflow';
import { Chip, DocHead, DocPage, printDoc, Sec } from './DocKit';

const TYPE: Record<string, string> = { WO: '정비 작업지시서', WR: '작업기록서', SR: '간이 작업기록', SHIFT: '교대 보고서', DAILY: '일일 보고서', MAINT_WO: '정비 작업지시서', WORK_RECORD: '작업기록서', QUICK_RECORD: '간이 작업기록', SHIFT_REPORT: '교대 보고서', DAILY_REPORT: '일일 보고서', PM_RECORD: '예방 정비 실시 기록', SHIPMENT: '출하 기록', INTERNAL_DOC: '사내 문서', APP_USER: '직원 배치' };
const SRV: Record<string, string> = { SHIFT: 'SHIFT_REPORT', DAILY: 'DAILY_REPORT' };
// 서버가 고친 칸은 칸 이름이 영어로 온다 (backend/app/services/documents.py fields) → 한글로 (9월 기록은 이미 한글, 2026-10-20)
const FIELD: Record<string, string> = { notable_text: '특이 사항', handover_text: '인계 사항', issues_summary: '오늘의 문제', title: '제목', symptom: '증상', cause: '원인', action: '조치', worker_memo: '작업자 메모', end_at: '끝난 시각', repair_min: '수리 시간', result: '결과', measured_value: '측정값', measured_unit: '단위', memo: '메모', home_shift_type: '담당 교대', home_process_code: '담당 공정', home_process_code_2: '두 번째 담당 공정' };
const blocked = (msg: string) => <div className="flex flex-col items-center gap-1 rounded-card border border-dashed border-line bg-white px-4 py-8 text-center"><LockIcon size={28} /><b>{msg}</b></div>;

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
      <DocPage width={1440}>
        <div className="flex justify-end gap-2 pt-2"><button onClick={printDoc} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button></div>{/* 제목은 화면 머리에 있어 뺌 */}
        {role !== 'OPR' && <CBand spec={revsBand(list[0] && { at: `${md(list[0].created_at)} ${hm(list[0].created_at)}`, doc: TYPE[list[0].doc_type] ?? list[0].doc_type, no: list[0].doc_key, who: list[0].author_kind === 'AI' ? '비서' : userName(list[0].author_user_id), ver: `v${list[0].version_no}` })} />}{/* 디자인 통일 C안: 결론 띠 (bands.ts revsBand) */}
        {role === 'OPR' ? blocked('작업자는 자기가 쓴 간이 작업기록의 이력만 볼 수 있습니다') : (<>
          <div className="flex flex-wrap gap-1.5">{['', ...types].map((t) => <button key={t || '전체'} onClick={() => setType(t)} className={`h-9 rounded-full border px-3 text-small font-semibold ${type === t ? 'border-brand-line bg-brand-tint text-brand-ink' : 'border-line bg-white'}`}>{t || '전체'}</button>)}</div>
          <div className="overflow-x-auto rounded-card border border-line bg-white">
            <table className="w-full min-w-[640px] text-left text-body"><thead className="text-small text-ink-2"><tr>{['시각', '문서', '번호', '버전', '누가', '사유'].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr></thead>
              <tbody>{shown.slice(0, 150).map((x) => <tr key={x.revision_id} onClick={() => SRV.SHIFT === x.doc_type ? go('revs', `SHIFT:${x.doc_key}`) : x.doc_type === 'DAILY_REPORT' ? go('revs', `DAILY:${x.doc_key}`) : undefined} className="cursor-pointer border-t border-line-soft hover:bg-tile">
                <td className="px-3 py-2 font-mono">{md(x.created_at)} {hm(x.created_at)}</td><td className="px-3 py-2">{TYPE[x.doc_type] ?? x.doc_type}</td><td className="px-3 py-2 font-mono">{x.doc_key}</td><td className="px-3 py-2 font-mono">v{x.version_no}</td>
                <td className="px-3 py-2">{x.author_kind === 'AI' ? <Chip tone="acc">비서</Chip> : <Chip>{userName(x.author_user_id)}</Chip>}</td><td className="px-3 py-2">{x.reason || <span className="text-ink-3">—</span>}</td></tr>)}</tbody></table>
          </div>
        </>)}
      </DocPage>
    );
  }
  return (
    <DocPage width={1100}>
      <DocHead title="수정 이력" sub={`${TYPE[kind]} ${id}`} right={<><button onClick={() => go('revs', null)} className={BTN}>모든 문서 보기</button><button onClick={printDoc} className={BTN}>인쇄</button><button onClick={back} className={BTN}>닫기</button></>} />
      {isBlocked ? blocked('작업자는 자기가 쓴 간이 작업기록의 이력만 볼 수 있습니다') : revs.length === 0 ? <Sec title="버전 없음"><span className="text-body text-ink-2">저장하면 생깁니다</span></Sec> : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[300px_minmax(0,1fr)] print:grid-cols-[300px_minmax(0,1fr)]">
          <ol className="flex flex-col gap-1.5">
            {revs.map((r, i) => (
              <li key={i}><button onClick={() => setSel(i)} aria-pressed={i === sel} className={`flex w-full flex-col gap-1 rounded-tile border px-3 py-2 text-left text-body ${i === sel ? 'border-ink bg-tile' : 'border-line bg-white hover:bg-tile'}`}>
                <b>v{r.v} · {r.kind}{/확정|승인|확인/.test(r.kind) ? <> <LockIcon /></> : ''}</b>
                <span className="text-small text-ink-2">{r.by} · {md(r.at)} {hm(r.at)}</span>
                {r.reason && <span className="text-small">사유: {r.reason}</span>}
                {r.changes.length > 0 && <span><Chip tone="acc">{r.changes.length}칸 바뀜</Chip></span>}
              </button></li>
            ))}
          </ol>
          <Sec title={cur.v === 0 ? '처음 버전' : `바뀐 부분 v${cur.v - 1} → v${cur.v}`} right={who(cur)}>
            {cur.changes.length === 0 ? (cur.v === 0 ? null : <span className="text-body text-ink-2">칸 변경 없음 (상태만 바뀜)</span>) : (
              <ul className="flex flex-col gap-2 text-body">{cur.changes.map((c, i) => (
                <li key={i} className="rounded-tile border border-line p-3"><b>{c.field}</b>
                  {c.before && <div className="mt-1 text-crit">− {c.before}</div>}
                  <div className="mt-1 rounded bg-ok-bg px-2 py-1 text-ok">+ {c.after || '(없음)'}</div>
                </li>))}</ul>
            )}
          </Sec>
        </div>
      )}
    </DocPage>
  );
}
