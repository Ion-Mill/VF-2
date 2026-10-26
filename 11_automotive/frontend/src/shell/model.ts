// 화면들이 같이 쓰는 값: 알람 기록(시뮬레이터 알람 이벤트), 알림(규칙), 사용자, 알람 코드집 정리.
import type { MachineId } from '@/components/types';
import { GENERATED } from './generated';
import { MACHINES, type Role } from './data';

export interface AlarmRec {
  code: string; process: string; nameKo: string; nameEn: string; easy: string;
  severity: 'STOP' | 'WARN' | 'GUIDE'; responder: string; note: string; lockout: string;
  chain: string; doc02: string; doc03: string[]; steps: string[]; symptom: string; maint: string[]; actions: string[];
}
export interface InvItem { no: string; name: string; unit: string; owner: string; safety: number; stock: number }
export interface UserRec { id: string; name: string; role: Role; shift: 'DAY' | 'NIGHT'; procs: string[] }
export interface ShortRow { work: string; judge: string; todo: string }

export const ALARMS = GENERATED.alarms as unknown as Record<string, AlarmRec>;
export const USERS = GENERATED.users as unknown as UserRec[];
export const SAFETY = GENERATED.safety as unknown as Record<string, { points: string[]; energy: string[] }>;
export const SHORT = GENERATED.short as unknown as Record<string, ShortRow>;
export const BLOCK = GENERATED.block as unknown as string[];
export const INVENTORY = GENERATED.inventory as unknown as InvItem[];
export const REASONS = GENERATED.reasons as unknown as { group: string; code: string; name: string }[];
// 직원 관리에서 바꾼 배치(서버 /api/users)를 화면의 사용자 목록에 덮어쓴다 — 로그인한 사용자도 같은 객체라 브리핑·담당 공정 알림이 바로 바뀐다 (FR-USR-01-06)
// 백엔드 /api/users·직원 추가 응답은 이름·역할도 준다 → 직원 관리에서 새로 만든 직원(U13…)을 목록에 더하고 이름·역할도 맞춘다 (2026-10-25). 담당 공정 없음 = null
export const applyAssignments = (rows: { user_id: string; user_name?: string; role_code?: string; home_shift_type: string | null; home_process_code: string | null; home_process_code_2: string | null }[]) => {
  for (const r of rows) {
    const procs = [r.home_process_code, r.home_process_code_2].filter(Boolean) as string[];
    const u = USERS.find((x) => x.id === r.user_id);
    if (!u) { if (r.user_name && r.role_code) USERS.push({ id: r.user_id, name: r.user_name, role: r.role_code as Role, shift: (r.home_shift_type ?? 'DAY') as UserRec['shift'], procs }); continue; }
    if (r.user_name) u.name = r.user_name;
    if (r.role_code) u.role = r.role_code as Role;
    if (r.home_shift_type) u.shift = r.home_shift_type as UserRec['shift'];
    u.procs = procs;
  }
};
/** 백엔드 로그인 응답 → 화면 로그인 사용자 (목록에도 넣거나 덮어써서 이름 표시·담당 공정 알림이 같은 객체를 본다) */
export const userFromLogin = (j: { user_id: string; user_name: string; role_code: string; process_codes?: string[]; shift_type?: string | null }): UserRec => {
  const p = j.process_codes ?? [];
  applyAssignments([{ user_id: j.user_id, user_name: j.user_name, role_code: j.role_code, home_shift_type: j.shift_type ?? null, home_process_code: p[0] ?? null, home_process_code_2: p[1] ?? null }]);
  return USERS.find((u) => u.id === j.user_id)!;
};
export const userName = (id?: string | null) => USERS.find((u) => u.id === id)?.name ?? id ?? '—';

export const ROLE_NAME: Record<Role, string> = { OPR: '현장 작업자', MNT: '보전 담당자', SUP: '라인 반장', MGR: '공장 관리자' };
export const SHIFT_NAME = { DAY: '주간', NIGHT: '야간' } as const;

export type Level = '긴급' | '주의' | '참고';
// 알람 이벤트 1건 = 알람 기록 1건 (SCR-07·08·09). 처리 = 작업기록서·간이 작업기록 확정 (사람), 해제 = 설비 쪽 알람이 꺼짐 (cleared)
export interface AlertRec {
  id: string; eventId: number; prevId: number | null; machine: MachineId; code: string;
  kind: 'alarm' | 'warn' | 'guide'; level: Level; alarm: AlarmRec | null;
  time: string; ts: number; cleared: string | null; lot: string | null; scenario: string | null;
  handled: boolean; handledTs?: number; handledBy?: string;
}
export const levelOfSev = (s: string): Level => (s === 'STOP' ? '긴급' : s === 'WARN' ? '주의' : '참고');
export const LEVEL_VIEW: Record<Level, { icon: string; color: string }> = {
  긴급: { icon: '⚠', color: '#c62a2f' }, 주의: { icon: '▲', color: '#9a6200' }, 참고: { icon: 'ⓘ', color: '#4b5a69' },
};
// 2.5 보고 순위: 0 안전 · 0-1 오래 방치(24시간 넘은 주의) · 1 긴급 · 2 생산 위험 · 3 주의 · 4 참고
export const RANK_ORDER = ['0', '0-1', '1', '2', '3', '4'];
export const RANK_NAME: Record<string, string> = { '0': '안전', '0-1': '오래 방치', '1': '긴급', '2': '생산 위험', '3': '주의', '4': '참고' };
export const RANK: Record<Level, number> = { 긴급: 1, 주의: 3, 참고: 4 };

// 알람이 아닌 알림 (규칙 25종, notification_rule.csv) — 전달 방식 ②목록(LIST) ③문서(BUBBLE)
export interface Notice {
  id: string; rule: string; ruleName: string; level: Level; rank: string; at: string; ts: number;
  text: string; related?: string; machine?: MachineId; roles: Role[]; userIds?: string[]; delivery: 'LIST' | 'BUBBLE';
  handled: boolean; handledBy?: string; handledAt?: string; plan?: string; past?: boolean;
  open?: { screen: string; key?: string }; stage?: 1 | 2; count?: number;
  keys?: string[]; // 묶음 알림의 항목 id (예방 정비 하루 전 = pm_task_id들, 2026-10-20)
}

export const whoText = (a: AlarmRec) => (a.responder === 'MNT' ? '보전 담당자 호출' : '작업자 조치 가능') + (a.note ? ` (${a.note})` : '');
export const sevText = (a: AlarmRec) => (a.severity === 'STOP' ? '정지' : a.severity === 'WARN' ? '주의' : '조작 안내');
export const alarmTitle = (a: AlarmRec | null, code?: string) => (a ? `${a.code}  ${a.nameKo}` : code ? `${code} (알람 코드집에 없음)` : '알람 코드집에 없는 알람입니다');
export const hhmm = (t: string) => (t.length > 8 ? t.slice(11, 16) : t.slice(0, 5));
export const machineLabel = (m: MachineId) => `${MACHINES[m].name} (${MACHINES[m].op})`;
export const docLabel = (s: string) => s.replace(/^DOC-0?(\d)/, 'DOC-0$1');

// 연쇄 알람 (108 → 994 → 992): 알람 이벤트의 앞 알람 번호를 따라간다 (R-06)
export const chainOf = (a: AlertRec, all: AlertRec[]): string[] => {
  const out = [a.code]; let p = a.prevId, guard = 0;
  while (p && guard++ < 6) { const x = all.find((y) => y.eventId === p); if (!x) break; out.unshift(x.code); p = x.prevId; }
  return out;
};
// 처리 책임: 그 설비의 OPR(담당 공정) · MNT (9.9) — 다른 사람은 [확인]으로 닫기만
export const responsible = (u: UserRec, m: MachineId) => u.role === 'MNT' || (u.role === 'OPR' && u.procs.includes(MACHINES[m].op));

// 첫 화면 (4.1): OPR = 현장 보기, 나머지 = 3D 라인 뷰
// 모든 계정 첫 화면 = 메인 (페이지구조 v3 N7 — 현장 모니터는 메뉴 페이지)
export const homeScreen = (_r: Role) => 'line' as const;
