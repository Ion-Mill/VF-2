'use client';
// 시연 데이터 서버(tools/sim_server.py, /api/*)와 잇는 곳. API 이름은 API명세서_v1.
// - 실시간 상태(API-LINE-02)와 실시간 사건(API-STR-01)을 1초마다 받는다. 전송 방식(SSE 등)은 [선택 필요: 기술 회의]라 묻는 방식(polling)으로 했다.
// - 시연 모드의 시각은 모두 시뮬레이터 시계 (NFR-DATA-10): SIM.now()
// - 화면에서 만든 문서(작업지시서·작업기록서 등)는 DB가 [선택 필요: 기술 회의]라 이 브라우저(localStorage)에 시연 회차(run_id)별로 남긴다.
import { useCallback, useEffect, useRef, useState } from 'react';
import { BackendErr, backendMode, backendRoute } from './backendApi';

export type Eq = 'SAW-01' | 'MIL-01' | 'VF2-01' | 'VF2-02' | 'WSH-01' | 'CMM-01';
export const EQS: Eq[] = ['SAW-01', 'MIL-01', 'VF2-01', 'VF2-02', 'WSH-01', 'CMM-01'];

export interface AlarmEv { alarm_event_id: number; equipment_id: Eq; alarm_code: string; severity: 'STOP' | 'WARN' | 'GUIDE'; occurred_at: string; cleared_at: string | null; lot_no: string | null; prev_alarm_event_id: number | null; scenario_code: string | null;
  handled_by?: string | null; handled_at?: string | null }   // 백엔드 모드: DB에서 이 알람의 작업기록서가 확정된 사람·시각 (2026-10-25)
export interface ToolRow { tool_id: string; tool_no: string; item_no: string; equipment_id: Eq; usage_pct: number; cum: number; limit: number; per_part: number; left_parts: number | null; warn: boolean }
export interface EqLive {
  state_code: 'RUN' | 'IDLE' | 'SETUP' | 'DOWN' | 'MAINT' | 'BLOCKED'; reason_code: string | null; reason_name: string | null; warn_marker: boolean;
  alarm: AlarmEv | null; since_at: string; minutes: number; lot_no: string | null; parts_in: number; cycle_progress: number | null; slow: boolean;
  shift_actual_qty: number; process_actual_qty: number; process_code: string; stop_min: number; loss_qty: number; std_cycle_min: number;
  tools: ToolRow[]; sensor: Record<string, number> | null;
}
export interface Oee { oee_pct: number | null; availability_pct: number | null; performance_pct: number | null; quality_pct: number | null; apt_min: number; pbt_min: number; pq: number; good_qty: number; warn: string[] }
export interface Production {
  shift_id: string; shift_type: 'DAY' | 'NIGHT'; start_at: string; end_at: string; target_qty: number; carry_over_qty: number; total_target_qty: number;
  actual_qty: number; forecast_qty: number; short_qty: number; rate_per_hour: number; elapsed_work_min: number; left_work_min: number; risk: boolean; risk_line_qty: number;
  hourly: { at: string; cum: number }[]; failure_loss_qty: number; speed_loss_qty: number; loss_qty: number; short_stops: { count: number; minutes: number }; supervisor_user_id: string;
}
export interface OrderRow { order_no: string; order_qty: number; done_qty: number; defect_qty: number; lots: string[]; current_process: string; due_at: string | null; status: string; delay: string | null; started_at: string | null; completed_at: string | null }
export interface Twin {
  run_id: number;
  clock: { sim_at: string; speed: number; paused: boolean; running_event: string | null; buttons_locked: boolean; finished: boolean; can_control?: boolean };
  buttons: Record<string, string | null>;
  shift: { shift_id: string; shift_type: 'DAY' | 'NIGHT'; start_at: string; end_at: string; supervisor_user_id: string };
  equipment: Record<Eq, EqLive>;
  wip: Record<string, number>; soak_qty: number;
  wip_limits: Record<string, { limit: number; warn_over: number | null; warn: boolean }>;
  bottleneck: { process_code: string; cause_code: string; alarm_event_id: number | null; since_at: string | null };
  process: Record<string, { pq: number; good: number; scrap: number }>;
  done_today: number; alarms: AlarmEv[]; holds: { lot_no: string; hold_id: number; judged: boolean; reason: string }[];
  suspect_lot: string | null; running_event: { code: string; equipment_id: Eq } | null;
  last_measure: { lot_no: string; part_seq: number; item_seq: number; position: string | null; measured_value: number; judgement: string; measured_at: string }[];
  production: Production; kpi: { from: string; to: string; by: Record<string, Oee>; mttr_mtbf: Record<Eq, { failures: number; mttr_min: number | null; mtbf_h: number | null; mttr_warn: boolean }> };
  orders: OrderRow[];
}
export interface SimEvent { seq: number; type: string; at?: string; [k: string]: unknown }

export class ApiErr extends Error { constructor(public code: string, msg: string) { super(msg); } }

export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  if (backendMode()) {
    // 화면 → 백엔드 전환 (C2, 2026-10-23): 스위치가 켜져 있으면 같은 주소 이름을 백엔드로 (backendApi.ts)
    try { return await backendRoute(path, body) as T; } catch (e) { if (e instanceof BackendErr) throw new ApiErr(e.code, e.message); throw e; }
  }
  let r: Response;
  try {
    r = await fetch('/api/' + path, body === undefined ? { cache: 'no-store' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch {
    throw new ApiErr('CONNECTION', '시연 데이터 서버에 연결하지 못했습니다');
  }
  const j = await r.json().catch(() => ({ code: 'SERVER', message: '응답을 읽지 못했습니다' }));
  if (!r.ok) throw new ApiErr(j.code ?? 'SERVER', j.message ?? '서버 오류');
  return j as T;
}

// 시연 시계 — 마지막으로 받은 시뮬레이터 시각 + 그 뒤 흐른 실제 시간 × 배속
export const SIM = {
  at: 0, real: 0, speed: 60, paused: true,
  now(): number { return this.at ? this.at + (this.paused ? 0 : (Date.now() - this.real) * this.speed) : Date.now(); },
};
export const tsOf = (iso: string | null | undefined) => (iso ? Date.parse(iso) : NaN);
export const hm = (iso: string | null | undefined) => (iso ? iso.slice(11, 16) : '--:--');
export const hms = (iso: string | null | undefined) => (iso ? iso.slice(11, 19) : '--:--:--');
export const md = (iso: string | null | undefined) => (iso ? `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}` : '');
export const simIso = (ms = SIM.now()) => {
  const d = new Date(ms + 9 * 3600e3); // +09:00
  return d.toISOString().slice(0, 19) + '+09:00';
};
export const minsSince = (iso: string | null | undefined) => (iso ? Math.max(0, Math.floor((SIM.now() - Date.parse(iso)) / 60000)) : 0);

export function useLive() {
  const [twin, setTwin] = useState<Twin | null>(null);
  const [connected, setConnected] = useState(true); // 첫 응답 전에 '연결 끊김' 띠가 번쩍이지 않게 — 3번 연속 실패해야 끊김
  const [lastOk, setLastOk] = useState<string | null>(null);
  const seq = useRef(0);
  const run = useRef<number | null>(null);
  const subs = useRef(new Set<(e: SimEvent[]) => void>());
  const fails = useRef(0);
  const busy = useRef(false);

  const pull = useCallback(async () => {
    if (busy.current) return; // 서버가 잠깐 느릴 때 1초마다 요청이 쌓이지 않게
    busy.current = true;
    try {
      const t = await api<Twin>('line/twin');
      SIM.at = Date.parse(t.clock.sim_at); SIM.real = Date.now(); SIM.speed = t.clock.speed; SIM.paused = t.clock.paused;
      if (run.current !== null && run.current !== t.run_id) seq.current = 0; // 처음으로 되돌림
      run.current = t.run_id;
      const ev = await api<{ seq: number; events: SimEvent[] }>(`stream/events?after=${seq.current}`);
      seq.current = ev.seq;
      if (ev.events.length) subs.current.forEach((f) => f(ev.events));
      setTwin(t); setConnected(true); setLastOk(t.clock.sim_at); fails.current = 0;
    } catch {
      fails.current += 1;
      if (fails.current >= 3) setConnected(false); // 3번 연속 실패 = 연결 끊김 (2.8)
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    pull();
    const t = setInterval(pull, 1000);
    return () => clearInterval(t);
  }, [pull]);

  const onEvents = useCallback((f: (e: SimEvent[]) => void) => { subs.current.add(f); return () => { subs.current.delete(f); }; }, []);
  return { twin, connected, lastOk, refresh: pull, onEvents };
}

// 이 브라우저에 남기는 상태 (시연 회차별). shortcut: DB 대신 localStorage — 기술 회의에서 DB가 정해지면 API로 바꾼다
export function usePersist<T>(key: string, init: T, runId: number | null): [T, (v: T | ((p: T) => T)) => void] {
  const full = `brk-data:${runId ?? 0}:${key}`;
  const [v, setV] = useState<T>(init);
  const loaded = useRef<string | null>(null);
  useEffect(() => {
    if (runId === null || loaded.current === full) return;
    loaded.current = full;
    try { const s = localStorage.getItem(full); setV(s ? JSON.parse(s) : init); } catch { setV(init); }
  }, [full, runId]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = useCallback((x: T | ((p: T) => T)) => {
    setV((p) => {
      const n = typeof x === 'function' ? (x as (p: T) => T)(p) : x;
      try { localStorage.setItem(full, JSON.stringify(n)); } catch { /* 저장 못 해도 화면은 계속 */ }
      return n;
    });
  }, [full]);
  return [v, set];
}

// 회차와 상관없이 남기는 값 (화면 설정·채팅 기록 30일)
export function useLocal<T>(key: string, init: T): [T, (v: T | ((p: T) => T)) => void] {
  const full = `brk-data:${key}`;
  const [v, setV] = useState<T>(init);
  useEffect(() => { try { const s = localStorage.getItem(full); if (s) setV(JSON.parse(s)); } catch { /* 없음 */ } }, [full]);
  const set = useCallback((x: T | ((p: T) => T)) => {
    setV((p) => { const n = typeof x === 'function' ? (x as (p: T) => T)(p) : x; try { localStorage.setItem(full, JSON.stringify(n)); } catch { /* 없음 */ } return n; });
  }, [full]);
  return [v, set];
}

// 한 번 받아 두는 조회 (화면이 열릴 때·주기적으로)
export function useFetch<T>(path: string | null, every = 0, deps: unknown[] = []): { data: T | null; err: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    if (!path) return;
    api<T>(path).then((d) => { setData(d); setErr(null); }).catch((e: Error) => setErr(e.message));
  }, [path]);
  useEffect(() => {
    load();
    if (!every) return;
    const t = setInterval(load, every);
    return () => clearInterval(t);
  }, [load, every, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, err, reload: load };
}
