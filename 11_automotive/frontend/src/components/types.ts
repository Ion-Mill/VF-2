export type Quality = '자동' | '고품질' | '저사양';

/** 대시보드 외부 설정값 (App.tsx에서 props로 전달) */
export interface DashboardProps {
  /** 렌더 품질: 자동은 처음 4초 FPS를 재서 저사양 전환 */
  quality?: Quality;
  /** 첫 진입 시 시네마틱 오프닝 재생 */
  introOnLoad?: boolean;
  /** 고장/주의 시나리오 */
  scenario?: string;
  showCards?: boolean;
  showFlow?: boolean;
  /** 물류 흐름 속도 배율 */
  flowSpeed?: number;
  autoRotate?: boolean;
}

export type MachineId = 'inf' | 'saw' | 'mil' | 'vf1' | 'vf2' | 'wsh' | 'cmm';
export type MachineStatus = 'RUN' | 'WARN' | 'ALARM' | 'IDLE' | 'SETUP' | 'MAINT' | 'BLOCKED';

/** 실데이터 연동 시 이 형태로 상태를 넣으면 됩니다 (initSim / tick 참고) */
export interface LiveSnapshot {
  st: Record<MachineId, MachineStatus>;
  /** 설비별 [부하%, 공구수명%] */
  m: Partial<Record<MachineId, [number, number]>>;
  wip: { w1: number; w2: number; w3: number; w4: number; fg: number };
  uph: number;
}

/** UI설계서 적용본: 3D가 화면 틀(shell)에 알려 주는 값 */
export interface LineSnapshot {
  st: Record<MachineId, MachineStatus>;
  warn: Partial<Record<MachineId, boolean>>;
  wip: LiveSnapshot['wip'];
  m: LiveSnapshot['m'];
  uph: number;
  hist: { uph: number[]; wip: number[] };
  clock: string;
  sel: MachineId | null;
  view: string;
  vf2Tool: number;
  alarmAt: string;
}
