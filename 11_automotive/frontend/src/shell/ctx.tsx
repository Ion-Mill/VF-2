'use client';
// 화면들이 같이 쓰는 앱 상태 (App.tsx가 채운다). 화면 이동·문서 열기·알림 처리도 여기로.
import { createContext, useContext } from 'react';
import type { MachineId } from '@/components/types';
import type { Role } from './data';
import type { Twin } from './live';
import type { AlertRec, Notice, UserRec } from './model';
import type { SimpleRecord, StopReason, WorkOrder, WorkRecord } from './workflow';

export type Screen = 'line' | 'layout2d' | 'field' | 'card' | 'wo' | 'wr' | 'sr' | 'stops' | 'docs' | 'replay' | 'shift' | 'daily' | 'revs'
  | 'lots' | 'quality' | 'inventory' | 'tools' | 'pm' | 'idocs' | 'settings';

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
  stopReasons: Record<string, StopReason>; setStopReasons: (f: (p: Record<string, StopReason>) => Record<string, StopReason>) => void;
  addNotice: (n: Notice) => void; handleNotice: (id: string, plan?: string) => void; markAlert: (ids: string[], by: string) => void;
  screen: Screen; key: string | null; go: (s: Screen, key?: string | null) => void; back: () => void;
  openCard: (alertId: string) => void; openWo: (no: string) => void; openRecord: (woNo: string) => void; openSimple: (alertId: string, kind?: 'alarm' | 'cause') => void;
  openSource: (doc: string, section: string) => void; openReplay: (atIso: string) => void;
  selectMachine: (m: MachineId) => void; selected: MachineId | null;
  toast: (msg: string) => void; settings: Settings; setSettings: (f: (s: Settings) => Settings) => void;
  inv: Inv | null; reloadInv: () => void; history: History | null;
  pm: { tasks: Record<string, any>[]; on_time_rate_pct: number | null; planned_windows: Record<string, string>[]; today_records: Record<string, any>[] } | null; reloadPm: () => void;
  shiftReports: Record<string, any>[] | null; dailyReports: Record<string, any>[] | null; reloadReports: () => void;
  rules: { repeat_days: number; repeat_count: number; target_risk_pct: number; repeat2_days: number; burst: string; flood: string };
  restoreMachine: (m: MachineId) => Promise<void>;
  setReplay: (frame: unknown | null) => void;
}

export const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('AppCtx 없음');
  return c;
};

// 공통 버튼 모양 (터치 크기 44px 이상, 2.4)
export const BTN = 'h-11 rounded-md border border-slate-300 bg-white px-4 text-[14px] font-semibold hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-white';
export const DARK = 'h-11 rounded-md bg-[#1c2530] px-4 text-[14px] font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300';
export const PAGE = 'absolute inset-0 overflow-y-auto bg-[#e9ecef] p-4';
export const CARD = 'mx-auto max-w-[1100px] rounded-lg border border-slate-300 bg-white p-4';
