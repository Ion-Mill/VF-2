'use client';
// 화면들이 같이 쓰는 앱 상태 (App.tsx가 채운다). 화면 이동·문서 열기·알림 처리도 여기로.
import { createContext, useContext } from 'react';
import type { MachineId } from '@/components/types';
import type { Role } from './data';
import type { Twin } from './live';
import type { AlertRec, Notice, UserRec } from './model';
import type { SimpleRecord, WorkOrder, WorkRecord } from './workflow';

export type Screen = 'line' | 'layout2d' | 'field' | 'cards' | 'card' | 'wo' | 'wr' | 'sr' | 'docs' | 'replay' | 'shift' | 'daily' | 'revs'
  | 'lots' | 'quality' | 'qcap' | 'inventory' | 'tools' | 'pm' | 'idocs' | 'staff' | 'settings';

export interface Settings { bloom: boolean; sound: boolean; cards: boolean; monitorInch: number; distanceM: number; fontScale: boolean; autoReturnSec: number }
export const DEFAULT_SETTINGS: Settings = { bloom: true, sound: true, cards: false, monitorInch: 55, distanceM: 3, fontScale: false, autoReturnSec: 90 };

export interface Inv { items: { item_no: string; category: string; item_name: string; unit: string; owner_role: string; safety_stock: number; stock_qty: number; low: boolean }[]; held_lot_qty: number; live_txns: Record<string, unknown>[]; past_txns: Record<string, string>[] }
export interface History {
  work_orders: Record<string, string>[]; steps: Record<string, Record<string, string>[]>; work_records: Record<string, string>[];
  checks: Record<string, Record<string, string>[]>; parts: Record<string, Record<string, string>[]>; alarms: Record<string, string>[];
}

export interface AppCtx {
  user: UserRec; role: Role; setUser: (u: UserRec | null) => void;
  twin: Twin | null; connected: boolean; lastOk: string | null;
  alerts: AlertRec[]; notices: Notice[]; myNotices: Notice[];
  wos: WorkOrder[]; wrs: WorkRecord[]; srs: SimpleRecord[];
  putWo: (w: WorkOrder) => void; putWr: (w: WorkRecord) => void; putSr: (r: SimpleRecord) => void;
  addNotice: (n: Notice) => void; handleNotice: (id: string, plan?: string) => void; markAlert: (ids: string[], by: string) => void;
  screen: Screen; key: string | null; go: (s: Screen, key?: string | null) => void; back: () => void;
  openCard: (alertId: string) => void; openWo: (no: string) => void; openRecord: (woNo: string, nav?: boolean) => void; openSimple: (alertId: string, kind?: 'alarm' | 'cause') => void; openAfter: (stopKey?: string) => void;
  openSource: (doc: string, section: string) => void; openReplay: (atIso: string) => void;
  selectMachine: (m: MachineId | null) => void; selected: MachineId | null;
  toast: (msg: string) => void; settings: Settings; setSettings: (f: (s: Settings) => Settings) => void;
  inv: Inv | null; reloadInv: () => void; history: History | null;
  pm: { tasks: Record<string, any>[]; on_time_rate_pct: number | null; planned_windows: Record<string, string>[]; today_records: Record<string, any>[] } | null; reloadPm: () => void;
  shiftReports: Record<string, any>[] | null; dailyReports: Record<string, any>[] | null; reloadReports: () => void;
  rules: { repeat_days: number; repeat_count: number; target_risk_pct: number; repeat2_days: number; burst: string; flood: string };
  restoreMachine: (m: MachineId) => Promise<void>;
  setReplay: (frame: unknown | null) => void;
  bandOff: string[]; // 홈 알림 띠에서 X로 닫은 주의 알람 id
  eve: boolean; // 이브 창 열림 (화면 폭 444px 줄어듦)
}

export const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('AppCtx 없음');
  return c;
};

// 공통 버튼 모양 (터치 크기 44px 이상, 2.4)
// 디자인 통일 C안 (2026-10-20): 값만 먼저 토큰으로 — 화면을 ui.tsx 부품(Btn·Page·Sec)으로 바꾸면서 지운다
export const BTN = 'h-11 rounded-ctl border border-line bg-white px-4 text-body font-semibold text-ink hover:bg-tile disabled:cursor-not-allowed disabled:bg-track disabled:text-bar disabled:hover:bg-track';
export const DARK = 'h-11 rounded-ctl bg-brand px-4 text-body font-semibold text-white hover:bg-brand-ink disabled:cursor-not-allowed disabled:bg-track disabled:text-bar';
export const PAGE = 'absolute inset-0 overflow-y-auto bg-ground p-4 [scrollbar-gutter:stable]'; // 스크롤바 자리를 늘 비워 둠 — 긴 화면 · 짧은 화면 카드 폭이 10px씩 달라지지 않게 (2026-10-25)
export const CARD = 'rounded-card border border-line bg-white p-4 shadow-card';
