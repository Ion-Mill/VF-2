// SCR-11·12·13·14·17의 문서 기록. 이 브라우저에 시연 회차별로 남는다 (live.ts usePersist).
// 시각은 모두 시뮬레이터 시계 (SIM).
import type { MachineId } from '@/components/types';
import type { Role } from './data';
import { SIM, simIso } from './live';

// 수정 이력 1줄 (SCR-17): v0 = 프로그램 초안(작업지시서) 또는 사람이 처음 저장한 것(간이 기록·정비 기록·출하)
export interface Change { field: string; before: string; after: string }
export interface Revision { v: number; kind: string; by: string; byRole: Role | 'PROGRAM'; at: string; reason?: string; changes: Change[] }
export const rev = (list: Revision[] | undefined, kind: string, by: string, byRole: Role | 'PROGRAM', changes: Change[] = [], reason?: string): Revision[] => {
  const l = list ?? [];
  return [...l, { v: l.length, kind, by, byRole, at: simIso(), reason, changes }];
};
export const diff = (before: Record<string, unknown>, after: Record<string, unknown>, names: Record<string, string>): Change[] =>
  Object.keys(names).filter((k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]))
    .map((k) => ({ field: names[k], before: Array.isArray(before[k]) ? (before[k] as string[]).join(' / ') : String(before[k] ?? ''), after: Array.isArray(after[k]) ? (after[k] as string[]).join(' / ') : String(after[k] ?? '') }));

export type WoState = 'draft' | 'editing' | 'approved' | 'inprogress' | 'done' | 'cancelled';
export const WO_STEPS: [WoState, string][] = [['draft', '초안'], ['editing', '수정 중'], ['approved', '승인'], ['inprogress', '진행 중'], ['done', '완료']];

export interface WorkOrder {
  no: string; alertId: string; machine: MachineId; code: string; created: string; state: WoState; version: number;
  trigger: 'STOP_ALARM' | 'REPEAT_2'; lot: string | null;
  title: string; symptom: string; steps: string[]; parts: string[]; assignee: string | null;
  edited: string[]; approvedBy?: string; approvedAt?: string; recordNo?: string; revisions: Revision[]; llm?: boolean; // 제목·증상을 비서(외부 LLM)가 다듬어 넣었다 (2026-10-17, 시연 서버 MOM_LLM_COMPOSE=1일 때만)
}
export type WrState = 'draft' | 'editing' | 'confirmed' | 'checked';
export interface WorkRecord {
  no: string; woNo: string; state: WrState; memo: string; cause: string; action: string;
  parts: { item: string; qty: number }[]; stepChecks: boolean[]; lock: boolean[]; start: string; end: string;
  revisions: Revision[]; confirmedAt?: string; aiFields?: string[];
}
export interface SimpleRecord {
  no: string; alertId: string; machine: MachineId; kind: 'alarm' | 'cause' | 'after'; state: 'open' | 'confirmed'; action: string; parts: { item: string; qty: number }[];
  lock: boolean[]; memo: string; by?: string; savedBy?: string; revisions: Revision[]; code: string;
  // 선조치 기록 (kind 'after', FR-MNT-05-16~22): 알람 없이 먼저 한 일을 지난 시각으로. alertId·code는 비움
  stopKey?: string; start?: string; end?: string; urgent?: string; urgentText?: string;
  lockDone?: boolean; lockSkip?: string; checkedBy?: string; checkedAt?: string;
}
// 급했던 이유 (논리 ERD 6.55 [가상])
export const URGENT: [string, string][] = [['SAFETY', '안전 위험'], ['SPREAD', '고장 번짐 막기'], ['QUALITY', '품질 이상'], ['OTHER', '그 밖']];
// 기록 없는 정지 (FR-MNT-05-23): 끝난 정지 구간 중 5분 이상 · 알람 없음 · 사유가 비었거나 고장(F) — 키 = 설비|시작|끝
export interface Downtime { equipment_id: string; state_code: string; start_at: string; end_at: string | null; minutes: number; reason_suggested_code: string | null; alarm_event_id: number | null }
export const stopKeyOf = (d: Downtime) => `${d.equipment_id}|${d.start_at}|${d.end_at}`;
export const isUnrecordedStop = (d: Downtime) => !!d.end_at && d.minutes >= 5 && d.alarm_event_id == null && (d.state_code === 'IDLE' || d.state_code === 'DOWN')
  && (!d.reason_suggested_code || d.reason_suggested_code.startsWith('F'));
// SCR-14 정지 구간의 사유 입력 (구간 = 서버 /api/downtimes, 키 = 설비|시작 시각)
export interface StopReason { reason: string; by?: string; confirmed?: boolean; confirmedBy?: string }

// 비서가 아니라 규칙으로 정한 추천 코드 (막힘 → M03, 정비 → P01, 준비 → S02, 대기 → M02, 알람 → 알람 종류). 시뮬레이터가 붙인 사유가 있으면 그것
export const suggestReason = (state: string, simReason?: string | null, alarmCode?: string): string => {
  if (simReason) return simReason;
  if (state === 'BLOCKED') return 'M03';
  if (state === 'MAINT') return 'P01';
  if (state === 'SETUP') return 'S02';
  if (state === 'IDLE') return 'M02';
  if (!alarmCode) return '';
  const c = alarmCode.split('.')[0];
  return ['992', '994', '991', '993', '103', '108'].includes(c) ? 'F01' : ['254', '966'].includes(c) ? 'F02' : ['2073', '2075'].includes(c) ? 'F04' : c === '120' ? 'F05' : '';
};

export const pad = (n: number, w = 4) => String(n).padStart(w, '0');
// 문서 번호는 9월 기록(MW-0901~, MR-0901~) 뒤에 이어 붙인다
export const nextNo = (prefix: string, list: { no: string }[], start = 950) => `${prefix}-${pad(start + list.length)}`;
export const minutesSince = (iso: string) => Math.max(0, Math.floor((SIM.now() - Date.parse(iso)) / 60000));
