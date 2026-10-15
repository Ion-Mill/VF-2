'use client';
// 안전 칸 공통 부품: DOC-05 §7 고정 서식 블록(6.5), 짧은 작업 줄(§2.4), 잠금·표지 체크 9칸, 확인 상자.
import type { ReactNode } from 'react';
import type { MachineId } from '@/components/types';
import { MACHINES } from './data';
import { BLOCK, SAFETY, SHORT, type AlarmRec } from './model';

// 블록의 체크칸 9개 (6.1~6.6, 7.1~7.3) — KOSHA 원문 제목 그대로
export const LOCK = BLOCK.filter((l) => /^\s*□ [67]\.\d/.test(l)).map((l) => l.replace(/^\s*□ /, '').trim());

export const shortRow = (a: AlarmRec) => SHORT[a.code.split('.')[0]];
// 잠금·표지 체크가 필요한가: 정지 등급(안전 블록이 붙는 설비) 또는 §2.4 줄이 있는 주의 알람
export const needsLock = (a: AlarmRec | null, m: MachineId) =>
  !!a && ((a.severity === 'STOP' && !!SAFETY[MACHINES[m].name]) || (a.severity === 'WARN' && !!shortRow(a)));

export function SafetyBlock({ machine, alarm }: { machine: MachineId; alarm: AlarmRec }) {
  const name = MACHINES[machine].name, sf = SAFETY[name];
  if (alarm.severity === 'STOP' && sf) {
    const op30 = MACHINES[machine].op === 'OP-30';
    let text = BLOCK.join('\n')
      .replace('{설비 ID}', name).replace('{§3 차단 지점 목록}', sf.points.join(' · ')).replace('{§3 저장 에너지 목록}', sf.energy.join(' · '));
    if (!op30) text = text.replace(/\[고전압 대기\][^\n]*\n[^\n]*\n[^\n]*\n/, '[저장 에너지]\n □ §3 저장 에너지 확인\n');
    return (
      <div>
        <div className="mb-1 text-[12px] font-bold text-slate-600">🔒 고정 서식 · AI 작성 아님 · 지울 수 없음</div>
        <pre className="max-w-full overflow-x-auto whitespace-pre-wrap rounded-md border border-slate-300 bg-slate-50 p-3 font-mono text-[12px] leading-relaxed">{text}</pre>
      </div>
    );
  }
  if (alarm.severity === 'WARN') {
    const row = shortRow(alarm);
    return row ? (
      <div className="rounded-md border border-slate-300 bg-slate-50 p-3 text-[13px]">
        <div className="mb-1 text-[12px] font-bold text-slate-600">🔒 짧은 작업 판단 (DOC-05 §2.4 해당 줄 그대로 · AI 작성 아님)</div>
        <div className="font-semibold">{row.work} — {row.judge}</div>
        <div>{row.todo}</div>
      </div>
    ) : <p className="text-[13px] text-slate-600">DOC-05 §2.4에 이 알람의 짧은 작업 줄이 없습니다 (§2 해당 없음)</p>;
  }
  return <p className="text-[13px] text-slate-600">이 알람은 안전 작업 기준서 적용 대상이 아닙니다 (DOC-05 §1)</p>;
}

// 잠금·표지 체크 9칸 (눌리는 체크칸). 9개가 다 체크돼야 확정할 수 있다.
export function LockChecks({ value, onChange, disabled }: { value: boolean[]; onChange: (v: boolean[]) => void; disabled?: boolean }) {
  const n = value.filter(Boolean).length;
  return (
    <div>
      <div className="mb-1 text-[12px] font-bold text-slate-600">잠금·표지 체크 (DOC-05 §7 블록 그대로) — 9개 중 {n}개</div>
      <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-3">
        {LOCK.map((l, i) => (
          <label key={l} className="flex min-h-[44px] items-center gap-2 text-[13px]">
            <input type="checkbox" className="h-5 w-5" disabled={disabled} checked={!!value[i]}
              onChange={() => onChange(value.map((v, k) => (k === i ? !v : v)))} />
            {l}
          </label>
        ))}
      </div>
    </div>
  );
}

// 승인·확정·취소처럼 되돌리기 어려운 버튼은 확인 상자를 거친다 (2.4)
export function ConfirmBox({ title, body, okLabel, onOk, onCancel }: { title: string; body: ReactNode; okLabel: string; onOk: () => void; onCancel: () => void }) {
  return (
    <div role="dialog" aria-label={title} className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-[420px] rounded-xl bg-white p-5 shadow-2xl">
        <h3 className="text-[16px] font-bold">{title}</h3>
        <div className="mt-2 text-[14px] text-slate-700">{body}</div>
        <div className="mt-4 flex justify-end gap-3">
          <button onClick={onCancel} className="h-12 rounded-md border border-slate-300 px-5 font-semibold">돌아가기</button>
          <button onClick={onOk} className="h-12 rounded-md bg-[#1c2530] px-5 font-bold text-white">{okLabel}</button>
        </div>
      </div>
    </div>
  );
}
