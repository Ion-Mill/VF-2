'use client';
// 안전 칸 공통 부품: DOC-05 §7 고정 서식 블록(6.5), 짧은 작업 줄(§2.4), 잠금·표지 체크 9칸, 확인 상자.
// 고정 서식은 글자를 바꾸지 않고 묶음(작업 전·고전압 대기·보호구·작업 후)과 칩으로만 나눠 보인다.
// 묶음 부제·근거·출처 줄은 화면 본문에서 빼고 출처 토글로 (원문 출처는 표시하지 않음 — FR-MNT-01-07, NFR-COPY-02).
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import type { MachineId } from '@/components/types';
import { MACHINES } from './data';
import { BLOCK, SAFETY, SHORT, type AlarmRec } from './model';
import { Chip } from './DocKit';
import { LockIcon } from './ui';

// 블록의 체크칸 9개 (6.1~6.6, 7.1~7.3) — KOSHA 원문 제목 그대로
export const LOCK = BLOCK.filter((l) => /^\s*□ [67]\.\d/.test(l)).map((l) => l.replace(/^\s*□ /, '').trim());

export const shortRow = (a: AlarmRec) => SHORT[a.code.split('.')[0]];
// 잠금·표지 체크가 필요한가: 정지 등급(안전 블록이 붙는 설비) 또는 §2.4 줄이 있는 주의 알람
export const needsLock = (a: AlarmRec | null, m: MachineId) =>
  !!a && ((a.severity === 'STOP' && !!SAFETY[MACHINES[m].name]) || (a.severity === 'WARN' && !!shortRow(a)));

// 블록 → 묶음 [{이름, 줄}] (부제·주석·근거 줄은 뺀다)
function blockGroups(op30: boolean) {
  const out: { name: string; items: string[] }[] = [];
  BLOCK.forEach((line) => {
    const t = line.trim();
    if (t.startsWith('[')) out.push({ name: t.replace(/^\[([^\]]+)\].*$/, '$1'), items: [] });
    else if (t.startsWith('□') && out.length) out[out.length - 1].items.push(t.replace(/^□\s*/, ''));
  });
  // OP-30 밖 설비는 고전압 대기 대신 저장 에너지 확인 (기존 규칙 그대로)
  return op30 ? out : out.map((g) => (g.name === '고전압 대기' ? { name: '저장 에너지', items: ['§3 저장 에너지 확인'] } : g));
}
export const SafeTag = <Chip tone="warn"><LockIcon /> 고정 서식</Chip>;

export function SafetyBlock({ machine, alarm }: { machine: MachineId; alarm: AlarmRec }) {
  const name = MACHINES[machine].name, sf = SAFETY[name];
  if (alarm.severity === 'STOP' && sf) {
    const line = (k: string, v: ReactNode) => <div className="flex flex-wrap items-center gap-1.5 text-small"><b className="min-w-[72px] font-semibold text-ink-2">{k}</b>{v}</div>;
    return (
      <div className="flex flex-col gap-2.5">
        {line('설비', <Chip mono>{name}</Chip>)}
        {line('차단 지점', sf.points.map((p) => <Chip key={p} mono>{p}</Chip>))}
        {line('저장 에너지', sf.energy.map((p) => <Chip key={p}>{p}</Chip>))}
        {/* 왼쪽 열 = 순서대로 하는 일(작업 전 → 작업 후), 오른쪽 열 = 조건이 맞을 때마다 지키는 일(고전압 대기·보호구) — 2026-10-20 팀 검토. 두 열 높이를 맞춘다(작은 카드가 늘어남) */}
        {(() => {
          const gs = blockGroups(MACHINES[machine].op === 'OP-30');
          const card = (g: { name: string; items: string[] }) => (
            <div key={g.name} className="flex-1 rounded-tile border border-line px-3 py-2.5">
              <b className="text-body">{g.name}</b>
              <ul className="mt-1 flex flex-col gap-1">{g.items.map((x) => <li key={x} className="grid grid-cols-[14px_minmax(0,1fr)] gap-2 text-body leading-snug"><span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-400" />{x}</li>)}</ul>
            </div>
          );
          const seq = gs.filter((g) => g.name.startsWith('작업')), rest = gs.filter((g) => !g.name.startsWith('작업'));
          return <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2"><div className="flex flex-col gap-2.5">{seq.map(card)}</div><div className="flex flex-col gap-2.5">{rest.map(card)}</div></div>;
        })()}
      </div>
    );
  }
  if (alarm.severity === 'WARN') {
    const row = shortRow(alarm);
    return row ? (
      <div className="flex flex-col gap-1 text-body">
        <div className="flex flex-wrap items-center gap-1.5"><Chip tone="warn">{row.work}</Chip><b>{row.judge}</b></div>
        <div>{row.todo}</div>
      </div>
    ) : <Chip tone="ok">잠금·표지 필요 없음</Chip>;
  }
  return <Chip>안전 작업 기준서 적용 대상 아님</Chip>;
}
// 출처 토글에 넣을 안전 줄 (사내 문서 이름·번호·§절만)
export function safetySrc(machine: MachineId, alarm: AlarmRec, open: (doc: string, sec: string) => void): ReactNode {
  const b = (doc: string, s: string) => <button onClick={() => open(doc, s)} className="underline">{doc} §{s}</button>;
  if (alarm.severity === 'STOP' && SAFETY[MACHINES[machine].name]) {
    return <li>안전 — 안전 작업 기준서 {b('DOC-05', '7')} 고정 서식{MACHINES[machine].op === 'OP-30' ? <> · 고전압 대기는 VF2-01·VF2-02 제어반 작업 때 ({b('DOC-05', '4.1')})</> : null}</li>;
  }
  if (alarm.severity === 'WARN') return <li>잠금·표지 판단 — 안전 작업 기준서 {b('DOC-05', '2.4')}{shortRow(alarm) ? '' : ' (이 알람의 짧은 작업 줄 없음)'}</li>;
  return <li>안전 — 안전 작업 기준서 {b('DOC-05', '1')} (적용 대상 아님)</li>;
}

// 잠금·표지 체크 9칸 (작업 전 6 / 작업 후 3). 9개가 다 체크돼야 확정할 수 있다.
export function LockChecks({ value, onChange, disabled }: { value: boolean[]; onChange: (v: boolean[]) => void; disabled?: boolean }) {
  const group = (name: string, pre: string) => (
    <div className="flex flex-col gap-0.5">
      <b className="px-1 text-small text-ink-2">{name}</b>
      {LOCK.map((l, i) => [l, i] as const).filter(([l]) => l.startsWith(pre)).map(([l, i]) => (
        <label key={l} className="flex min-h-[44px] items-center gap-2 rounded-tile px-1 text-body hover:bg-tile">
          <input type="checkbox" className="h-5 w-5 accent-ok" disabled={disabled} checked={!!value[i]} onChange={() => onChange(value.map((v, k) => (k === i ? !v : v)))} />
          <span className={value[i] ? 'text-ink-2' : ''}>{l}</span>
        </label>
      ))}
    </div>
  );
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{group('작업 전', '6.')}{group('작업 후', '7.')}</div>;
}
// 잠금·표지 칸 제목 오른쪽: 체크 수 + [모두 체크] (시연용 — 한 번에 9칸)
export function LockHead({ value, onChange, disabled }: { value: boolean[]; onChange: (v: boolean[]) => void; disabled?: boolean }) {
  const n = value.filter(Boolean).length, all = n >= LOCK.length;
  return (<>
    <Chip tone={all ? 'ok' : 'warn'}>{n} / {LOCK.length}{all ? ' ✓' : ''}</Chip>
    {!disabled && !all && <button onClick={() => onChange(LOCK.map(() => true))} className="h-9 rounded-ctl border border-line bg-white px-3 text-small font-semibold hover:bg-tile">모두 체크</button>}
  </>);
}

// 승인·확정·취소처럼 되돌리기 어려운 버튼은 확인 상자를 거친다 (2.4)
export function ConfirmBox({ title, body, okLabel, onOk, onCancel }: { title: string; body: ReactNode; okLabel: string; onOk: () => void; onCancel: () => void }) {
  // body로 빼서 띄운다 (2026-10-22): 유리 효과(backdrop-filter) 위 바 안의 [시연 ▾] 처음으로 등에서 fixed가 바 기준이 돼 위에 붙어 잘리던 것
  return createPortal(
    <div role="dialog" aria-label={title} className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-[420px] rounded-tile bg-white p-5 shadow-2xl">
        <h3 className="text-card font-bold">{title}</h3>
        <div className="mt-2 text-body text-ink">{body}</div>
        <div className="mt-4 flex justify-end gap-3">
          <button onClick={onCancel} className="h-12 rounded-ctl border border-line px-5 font-semibold">돌아가기</button>
          <button onClick={onOk} className="h-12 rounded-ctl bg-brand px-5 font-bold text-white hover:bg-brand-ink">{okLabel}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
