// UI설계서_최종본 2.2(메뉴)·2.3(상태 표시) 표와 공장 배치(데이터). 숫자는 시연 데이터 서버·생성기 기준 정보에서 온다.
import type { MachineId } from '@/components/types';
import { GENERATED } from './generated';
import type { Eq } from './live';

export type Role = 'OPR' | 'MNT' | 'SUP' | 'MGR';
export const ROLES: Record<Role, string> = { OPR: '작업자(OPR)', MNT: '정비(MNT)', SUP: '반장(SUP)', MGR: '관리자(MGR)' };

// [메뉴, 화면, OPR, MNT, SUP, MGR] — ○ 보임 / 보기 읽기만 / — 없음 (2.2)
export const MENU: [string, string, string, string, string, string][] = [
  ['홈 (역할별 첫 화면)', 'SCR-04', '○', '○', '○', '○'],
  ['현장 보기', 'SCR-26', '○', '○', '○', '보기'],
  ['3D 라인 뷰', 'SCR-04', '○', '○', '○', '○'],
  ['다시 보기', 'SCR-06', '○', '○', '○', '○'],
  ['문서함', 'SCR-18', '보기', '○', '○', '○'],
  ['정지 사유', 'SCR-14', '입력', '입력', '확정', '보기'],
  ['로트 추적', 'SCR-19', '보기', '보기', '○', '○'],
  ['검사 기록', 'SCR-20', '○', '—', '○', '보기'],
  ['재고', 'SCR-21', '○', '○', '○', '○'],
  ['공구 수명', 'SCR-22', '○', '○', '보기', '보기'],
  ['예방 정비', 'SCR-23', '—', '○', '보기', '보기'],
  ['사내 문서', 'SCR-24', '보기', '보기', '보기', '보기'],
  ['설정', 'SCR-25', '—', '—', '—', '○'],
];
export const ROLE_COL: Record<Role, number> = { OPR: 2, MNT: 3, SUP: 4, MGR: 5 };

export const MACHINES: Record<MachineId, { name: string; op: string; eq?: Eq }> = {
  inf: { name: 'INF-01', op: '투입 대' },
  saw: { name: 'SAW-01', op: 'OP-10', eq: 'SAW-01' },
  mil: { name: 'MIL-01', op: 'OP-20', eq: 'MIL-01' },
  vf1: { name: 'VF2-01', op: 'OP-30', eq: 'VF2-01' },
  vf2: { name: 'VF2-02', op: 'OP-30', eq: 'VF2-02' },
  wsh: { name: 'WSH-01', op: 'OP-40', eq: 'WSH-01' },
  cmm: { name: 'CMM-01', op: 'OP-50', eq: 'CMM-01' },
};
export const ID_OF: Record<Eq, MachineId> = { 'SAW-01': 'saw', 'MIL-01': 'mil', 'VF2-01': 'vf1', 'VF2-02': 'vf2', 'WSH-01': 'wsh', 'CMM-01': 'cmm' };
export const LINE6: MachineId[] = ['saw', 'mil', 'vf1', 'vf2', 'wsh', 'cmm'];

// 3D 장면의 상태 색을 그대로 쓴다 (사용자 결정 — 원본 색). 모양·글자를 같이 붙인다 (설계서 2.3 규칙 1).
export const STATE_VIEW = {
  RUN: { text: '가공', icon: '●', color: '#13994f' },
  IDLE: { text: '대기', icon: '○', color: '#4b5a69' },
  SETUP: { text: '준비', icon: '🔧', color: '#1f5fc4' },
  WARN: { text: '가공 · 주의', icon: '▲', color: '#9a6200' },
  ALARM: { text: '고장', icon: '⚠', color: '#c62a2f' },
  MAINT: { text: '정비', icon: '▨', color: '#4b5a69' },
  BLOCKED: { text: '막힘', icon: '⛔', color: '#b45309' },
  NODATA: { text: '기록 없음', icon: '□', color: '#4b5a69' },
} as const;
export type StateKey = keyof typeof STATE_VIEW;
// 시뮬레이터 상태 코드 → 화면 상태 (DOWN = 고장, 주의 표시 = 가공 · 주의)
export const stateOf = (s: { state_code: string; warn_marker: boolean } | undefined | null): StateKey =>
  !s ? 'NODATA' : s.state_code === 'DOWN' ? 'ALARM' : s.state_code === 'RUN' && s.warn_marker ? 'WARN' : (s.state_code as StateKey);

export const LEGEND: { icon: string; text: string; color: string }[] = [
  { icon: '●', text: '가공', color: '#1fbf63' },
  { icon: '○', text: '대기', color: '#8a97a4' },
  { icon: '🔧', text: '준비', color: '#3b82f6' },
  { icon: '▨', text: '정비', color: '#6b7580' },
  { icon: '⚠', text: '고장', color: '#e5484d' },
  { icon: '⛔', text: '막힘', color: '#e8954a' },
  { icon: '▲', text: '주의 알람', color: '#f0a500' },
  { icon: '■', text: '재공 주황', color: '#e8954a' },
  { icon: '▭', text: '병목', color: '#e8954a' },
  { icon: '□', text: '기록 없음', color: '#8a97a4' },
];

export const CAUSE_KO: Record<string, string> = { C1: '원인 ① 사이클 시간 증가 (공구 마모)', C2: '원인 ② OP-30 1대만 가동', C3: '원인 ③ 검사 강화', FAILURE: '고장', BASE: '기준 병목' };
export const WIP_NAME: Record<string, string> = { 'WIP-10-20': 'WIP-1', 'WIP-20-30': 'WIP-2', 'WIP-30-40': 'WIP-3', 'WIP-40-50': 'WIP-4' };

// 2D 배치도(SCR-05)·3D 실제 크기 배치 — 생성기 masters/equipment.csv · layout_object.csv · plant_layout.csv (mm)
export const LAYOUT = GENERATED.layout as unknown as {
  plant: { width_x_mm: number; depth_y_mm: number; ceiling_z_mm: number; aisle_width_mm: number; work_band_mm: number; equipment_gap_mm: number };
  equipment: Record<Eq, { process: string; model: string; size: number[]; center: number[]; facing: string; tag: string; ref: string; std_cycle_min: number | null; batch_qty: number | null; batch_time_min: number | null }>;
  objects: Record<string, { kind: string; name: string; x: number[]; y: number[]; h: number | null; tag: string; buffer: string | null }>;
  wip: Record<string, { from: string; to: string; limit: number; warn_over: number | null; warn: boolean }>;
};
export const MASTERS = GENERATED.masters as unknown as Record<string, Record<string, string>[]> & { product: Record<string, string> };
