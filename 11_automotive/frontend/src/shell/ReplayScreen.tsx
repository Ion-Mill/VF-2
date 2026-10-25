"use client";
// SCR-06 다시 보기 — 지난 시간대를 블랙박스처럼 재생 (새 데이터 없음, API-LINE-06 기록을 시각 순서로).
// 3D에는 실시간 대신 그 시각의 상태·재공·병목을 넣는다 (ctx.setReplay). 센서는 10/1 실시간 기록만 (9월 센서 CSV는 생성 안 됨).
// 구성 (2026-10-19 정비 탭 구조 수정): "그 시각" 결론 띠(시각 · 무슨 일 · 완제품 · 가동) → 왼쪽 사건 목록 | 오른쪽 그 시각 라인(설비 카드 + 재공) + 타임라인(시각으로 가기 · 사건 표시 · 상태 띠 · 굵기 · 재생).
// 다이얼·[실시간] 버튼은 뺐다. 다른 화면으로 가면 3D는 실시간으로 돌아온다(아래 setReplay(null)).
import { SecIcon, ToneTag } from './ui';
import { useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "./ctx";
import { CAUSE_KO, LAYOUT, SHIFT_H, STATE_VIEW, hh, stateOf } from "./data";
import { EQS, SIM, hm, md, simIso, useFetch, type Eq } from "./live";
import { ALARMS } from "./model";

interface Seg {
  start_at: string;
  end_at: string;
  state_code: string;
  reason_code: string | null;
  warn_marker: boolean;
  alarm_event_id: number | null;
}
interface Al {
  alarm_event_id: number;
  equipment_id: Eq;
  alarm_code: string;
  severity: string;
  occurred_at: string;
  cleared_at: string | null;
  lot_no?: string | null;
  prev_alarm_event_id?: number | null;
}
interface Rp {
  from: string;
  to: string;
  step_min: number;
  states: Record<Eq, Seg[]>;
  wip: ({ at: string; SOAK: number } & Record<string, number | string>)[];
  bottleneck: {
    at: string;
    process_code: string;
    cause_code: string;
    prev_process_code?: string;
  }[];
  alarms: Al[];
  sensors: Record<string, ({ at: string } & Record<string, number>)[]>;
  done: string[];
  sensor_note: string;
}
// 사건 목록 한 줄 = 1줄(아이콘 · 설비 또는 사건 이름) + 2줄(알람 코드 · 이름 등)
interface Ev {
  at: number;
  kind: "STOP" | "WARN" | "GUIDE" | "OK" | "BN";
  head: string;
  sub: string;
  chain: boolean;
}

// 타임라인 = 15분 칸 지도 + 남색 농담 (사용자 선택 2026-10-25, 시안 C-1 — 전: 파스텔 막대가 얇고 조각이 잘아 읽기 어려웠다):
// 정상 흐름(가공 진한 남색 · 준비 옅은 남색 · 대기 · 휴식)은 한 계열로 물러나고, 막힘 주황 · 정비 보라 · 고장 빨강만 튄다.
// 3D 아래 공통 범례(data.ts LEGEND)와는 다르다. 설비 카드 글자 · 아이콘(ST_INK)은 앱 공용 상태 색 그대로 (2026-10-22)
const ST_COLOR: Record<string, string> = {
  RUN: "#2e4a7d",
  IDLE: "#eef2f7",
  SETUP: "#8aa3cf",
  BLOCKED: "#f0a830",
  MAINT: "#9b8ae0",
  DOWN: "#d0283d",
  REST: "#dde3ec",
};
// tailwind.config.ts 토큰과 같은 값: ok(가공) · brand(준비) · warn(막힘 · 주의) · crit(고장) · 회색(대기 · 정비 — data.ts STATE_VIEW와 같이)
const ST_INK: Record<string, { ink: string; tile: string }> = {
  RUN: { ink: "#157a4f", tile: "#e6f6ef" },
  IDLE: { ink: "#56667d", tile: "#eef2f7" },
  SETUP: { ink: "#2a55b8", tile: "#e5effe" },
  BLOCKED: { ink: "#a35a0c", tile: "#fff3e3" },
  MAINT: { ink: "#56667d", tile: "#eef2f7" },
  DOWN: { ink: "#c23042", tile: "#fdecee" },
  WARN: { ink: "#a35a0c", tile: "#fff3e3" },
};
const ST_KO: Record<string, string> = { RUN: "가공", IDLE: "대기", SETUP: "준비", BLOCKED: "막힘", MAINT: "정비", DOWN: "고장", REST: "휴식" };
const LEG: [string, string][] = ["RUN", "SETUP", "IDLE", "REST", "BLOCKED", "MAINT", "DOWN"].map((k) => [ST_KO[k], ST_COLOR[k]]);
// 15분 칸: 고장 · 정비 · 막힘이 2분 넘게 있으면 그 상태(짧은 고장이 묻히지 않게), 아니면 가장 오래 있던 상태
const CELL_MS = 15 * 60000, PROBLEM = ["DOWN", "MAINT", "BLOCKED"];
type StateRow = { state_code: string; reason_code: string | null; start_at: string; end_at: string };
function cellsOf(rows: StateRow[], t0: number, t1: number) {
  const out: { a: number; b: number; key: string; mins: [string, number][] }[] = [];
  for (let a = t0; a < t1; a += CELL_MS) {
    const b = Math.min(t1, a + CELL_MS), tot: Record<string, number> = {};
    rows.forEach((r) => {
      const o = Math.min(b, Date.parse(r.end_at)) - Math.max(a, Date.parse(r.start_at));
      if (o > 0) { const k = r.state_code === "IDLE" && r.reason_code === "P02" ? "REST" : ST_COLOR[r.state_code] ? r.state_code : "IDLE"; tot[k] = (tot[k] ?? 0) + o; }
    });
    const mins = Object.entries(tot).sort((x, y) => y[1] - x[1]);
    if (!mins.length) continue;
    const key = PROBLEM.find((k) => (tot[k] ?? 0) >= 2 * 60000) ?? mins[0][0];
    out.push({ a, b, key, mins: mins.map(([k, ms]) => [k, Math.round(ms / 60000)]) });
  }
  return out;
}
const EV_VIEW: Record<Ev["kind"], { icon: string; color: string }> = {
  STOP: { icon: "!", color: "#c62a2f" },
  WARN: { icon: "▲", color: "#b07400" },
  GUIDE: { icon: "i", color: "#8a97a4" },
  OK: { icon: "✓", color: "#13994f" },
  BN: { icon: "◆", color: "#2a55b8" },
};
const EV_RANK: Record<Ev["kind"], number> = {
  STOP: 0,
  WARN: 1,
  GUIDE: 2,
  OK: 3,
  BN: 4,
};
const SPEEDS: [number, string][] = [
  [60, "1분"],
  [300, "5분"],
  [900, "15분"],
]; // 1초에 지나가는 시연 시간
const WIPS: [string, number][] = [
  ["WIP-10-20", 1],
  ["WIP-20-30", 2],
  ["WIP-30-40", 4],
  ["WIP-40-50", 5],
]; // [재공, 왼쪽 카드 번호] — 칩은 두 카드 사이
const alarmName = (code: string) => ALARMS[code]?.nameKo ?? "";
const toLocalInput = (iso: string) => iso.slice(0, 16);
const fromLocalInput = (v: string) => `${v}:00+09:00`;
// 그 시각이 속한 교대 = 불러올 기록 범위 (주간 09:00~18:00, 야간 18:00~다음 날 06:00, 06:00~09:00은 앞 야간에 붙임 — SHIFT_H). 지금보다 뒤는 자른다
function shiftOf(ms: number): { a: number; b: number; label: string } {
  const iso = simIso(ms),
    d = iso.slice(0, 10),
    h = Number(iso.slice(11, 13));
  const { dayStart: ds, dayEnd: de, nightEnd: ne } = SHIFT_H;
  const at = (day: string, h: number) =>
    Date.parse(`${day}T${hh(h)}:00:00+09:00`);
  const prev = simIso(at(d, 12) - 864e5).slice(0, 10);
  const [a, b, label] =
    h >= ds && h < de
      ? [at(d, ds), at(d, de), "주간"]
      : h >= de
        ? [at(d, de), at(d, de) + (24 - de + ne) * 36e5, "야간"]
        : [at(prev, de), at(d, ds), "야간"];
  return { a, b: Math.max(a + 60000, Math.min(b, SIM.now())), label };
}
const LANE_PX = 40; // 막대 굵기 최대값 (자리가 모자라면 같이 얇아짐)

export function ReplayScreen() {
  const { key, setReplay, twin } = useApp();
  const center = key ?? simIso(SIM.now() - 30 * 60000);
  const sh0 = shiftOf(Date.parse(center));
  const [from, setFrom] = useState(toLocalInput(simIso(sh0.a)));
  const [to, setTo] = useState(toLocalInput(simIso(sh0.b)));
  const q = `replay?from=${encodeURIComponent(fromLocalInput(from))}&to=${encodeURIComponent(fromLocalInput(to))}`;
  const { data, err } = useFetch<Rp>(q, 0, [q]);
  const [t, setT] = useState<number>(Date.parse(center));
  const [play, setPlay] = useState(false);
  const [speed, setSpeed] = useState(60);
  const [jumpOpen, setJumpOpen] = useState(false);
  const [draft, setDraft] = useState({
    d: center.slice(0, 10),
    tm: center.slice(11, 16),
  });
  const last = useRef(Date.now());
  const t0 = data ? Date.parse(data.from) : 0,
    t1 = data ? Date.parse(data.to) : 1;

  // 그 시각으로 가기: 다른 교대면 그 교대 기록을 불러오고, 같은 교대면 커서만 옮긴다
  const goTo = (ms: number) => {
    const x = Math.min(ms, SIM.now()),
      sh = shiftOf(x);
    if (!data || x < t0 || x > t1) {
      setFrom(toLocalInput(simIso(sh.a)));
      setTo(toLocalInput(simIso(sh.b)));
    }
    setPlay(false);
    setT(x);
  };
  // 시연 시계(SIM)를 받기 전에 열리면 교대가 실제 시계로 잡힌다 → 처음 받았을 때 한 번 다시 잡는다 (들고 들어온 시각이 있으면 그대로)
  const synced = useRef(SIM.at !== 0);
  useEffect(() => {
    if (synced.current || !twin) return;
    synced.current = true;
    if (key) return;
    const c = SIM.now() - 30 * 60000,
      sh = shiftOf(c);
    setFrom(toLocalInput(simIso(sh.a)));
    setTo(toLocalInput(simIso(sh.b)));
    setT(c);
  }, [twin, key]);
  useEffect(() => {
    if (data) setT((x) => Math.min(Math.max(x, t0), t1));
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!play) return;
    last.current = Date.now();
    const id = setInterval(() => {
      const n = Date.now();
      setT((x) => {
        const y = x + (n - last.current) * speed;
        if (y >= t1) {
          setPlay(false);
          return t1;
        }
        return y;
      });
      last.current = n;
    }, 100);
    return () => clearInterval(id);
  }, [play, speed, t1]);
  useEffect(() => () => setReplay(null), [setReplay]);

  const segAt = (eq: Eq, x: number) =>
    (data?.states[eq] ?? []).find(
      (r) => Date.parse(r.start_at) <= x && x < Date.parse(r.end_at),
    );
  const alarmsAt = (x: number) =>
    (data?.alarms ?? []).filter(
      (a) =>
        Date.parse(a.occurred_at) <= x &&
        (!a.cleared_at || x < Date.parse(a.cleared_at)),
    );
  const byId = useMemo(
    () => new Map((data?.alarms ?? []).map((a) => [a.alarm_event_id, a])),
    [data],
  );

  // 그 시각의 상태 → 3D (applyLive 모양)
  const frame = useMemo(() => {
    if (!data) return null;
    const at = (list: { start_at: string; end_at: string }[]) =>
      list.find(
        (r) => Date.parse(r.start_at) <= t && t < Date.parse(r.end_at),
      ) ?? list[list.length - 1];
    const equipment: Record<string, unknown> = {};
    EQS.forEach((eq) => {
      const r = at(data.states[eq] ?? []) as Seg | undefined;
      const al = data.alarms.find(
        (a) =>
          a.equipment_id === eq &&
          Date.parse(a.occurred_at) <= t &&
          (!a.cleared_at || t < Date.parse(a.cleared_at)),
      );
      equipment[eq] = {
        state_code: r?.state_code ?? "IDLE",
        warn_marker: !!r?.warn_marker,
        reason_code: r?.reason_code,
        alarm: al ? { ...al, cleared_at: null } : null,
        tools: [],
        sensor: null,
        parts_in: r?.state_code === "RUN" ? 1 : 0,
        std_cycle_min:
          LAYOUT.equipment[eq].std_cycle_min ??
          LAYOUT.equipment[eq].batch_time_min ??
          1,
        minutes: 0,
      };
    });
    const w =
      [...data.wip].reverse().find((x) => Date.parse(x.at) <= t) ?? data.wip[0];
    const bn = [...data.bottleneck]
      .reverse()
      .find((x) => Date.parse(x.at) <= t);
    return {
      replay: true,
      clock: { sim_at: simIso(t), speed, paused: !play },
      equipment,
      wip: w
        ? Object.fromEntries(
            Object.entries(w).filter(([k]) => k.startsWith("WIP")),
          )
        : {},
      soak_qty: w?.SOAK ?? 0,
      wip_limits: twin?.wip_limits ?? {},
      bottleneck: bn
        ? { process_code: bn.process_code, cause_code: bn.cause_code }
        : null,
      done_today: data.done.filter((d) => Date.parse(d) <= t).length,
      production: { rate_per_hour: 0 },
    };
  }, [data, t, speed, play, twin?.wip_limits]);
  useEffect(() => {
    setReplay(frame);
  }, [frame, setReplay]);

  // 사건 목록: 알람 · 정지 알람 해제(복구) · 병목 변화 — 시각 순
  const events = useMemo<Ev[]>(() => {
    if (!data) return [];
    const out: Ev[] = [];
    data.alarms.forEach((a) => {
      const prev = a.prev_alarm_event_id
        ? byId.get(a.prev_alarm_event_id)
        : undefined;
      const dur = a.cleared_at
        ? Math.round(
            (Date.parse(a.cleared_at) - Date.parse(a.occurred_at)) / 60000,
          )
        : null;
      const kind = (
        a.severity === "STOP" || a.severity === "WARN" ? a.severity : "GUIDE"
      ) as Ev["kind"];
      out.push({
        at: Date.parse(a.occurred_at),
        kind,
        chain: !!prev,
        head: a.equipment_id,
        sub: `${a.alarm_code} ${alarmName(a.alarm_code)}${dur !== null ? ` · ${dur}분` : " · 해제 안 됨"}`,
      });
      const child = data.alarms.some(
        (b) => b.prev_alarm_event_id === a.alarm_event_id,
      );
      if (
        a.severity === "STOP" &&
        !child &&
        a.cleared_at &&
        Date.parse(a.cleared_at) <= t1
      ) {
        const dn = (data.states[a.equipment_id] ?? []).find(
          (s) =>
            s.state_code === "DOWN" &&
            Date.parse(s.start_at) <= Date.parse(a.cleared_at!) &&
            Date.parse(a.cleared_at!) <= Date.parse(s.end_at),
        );
        out.push({
          at: Date.parse(a.cleared_at),
          kind: "OK",
          chain: false,
          head: a.equipment_id,
          sub: dn
            ? `알람 해제 · 고장 ${Math.round((Date.parse(dn.end_at) - Date.parse(dn.start_at)) / 60000)}분`
            : "알람 해제",
        });
      }
    });
    data.bottleneck
      .filter((b) => Date.parse(b.at) >= t0)
      .forEach((b) =>
        out.push({
          at: Date.parse(b.at),
          kind: "BN",
          chain: false,
          head: "병목 변화",
          sub: `${b.prev_process_code && b.prev_process_code !== b.process_code ? `${b.prev_process_code} → ${b.process_code}` : b.process_code} · ${CAUSE_KO[b.cause_code] ?? b.cause_code}`,
        }),
      );
    return out.sort((a, b) => a.at - b.at || EV_RANK[a.kind] - EV_RANK[b.kind]);
  }, [data, byId, t0, t1]);
  const curEv = events.reduce((c, e, i) => (e.at <= t + 500 ? i : c), -1);
  const listRef = useRef<HTMLOListElement>(null);
  const [openEv, setOpenEv] = useState<string | null>(null); // 펼친 사건 (누르면 잘린 둘째 줄을 다 보임, 다시 누르면 접음 — 2026-10-25)
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(
      '[aria-current="true"]',
    );
    if (el && listRef.current)
      listRef.current.scrollTop = Math.max(
        0,
        el.offsetTop - listRef.current.clientHeight / 2,
      );
  }, [curEv]);
  const jump = (x: number) => {
    setPlay(false);
    setT(Math.min(t1, Math.max(t0, x)));
  };

  // 결론 띠: 그 시각 무슨 일이 몇 분째
  const act = alarmsAt(t);
  const stop = act
    .filter((a) => a.severity === "STOP")
    .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))[0];
  const warn = act.filter((a) => a.severity === "WARN")[0];
  const chainOf = (a: Al) => {
    const c: string[] = [];
    let x: Al | undefined = a;
    while (x) {
      c.unshift(x.alarm_code);
      x = x.prev_alarm_event_id ? byId.get(x.prev_alarm_event_id) : undefined;
    }
    return c;
  };
  const sinceMin = (a: Al) => {
    const s = segAt(a.equipment_id, t),
      first =
        s && s.state_code === "DOWN"
          ? Date.parse(s.start_at)
          : Date.parse(a.occurred_at);
    return Math.max(0, Math.round((t - first) / 60000));
  };
  const runNow = EQS.filter((eq) => segAt(eq, t)?.state_code === "RUN").length;
  const tone = stop ? "crit" : warn ? "warn" : "ok";
  // 결론 띠 = 흰 카드 + 왼쪽 상태 태그 (화이트 카드 · 파스텔 블루, 2026-10-21 — 색은 태그에만)
  const TONE_WORD: Record<string, string> = { crit: "정지", warn: "주의", ok: "정상" };
  const KEY: Record<string, string> = {
    crit: "text-crit",
    warn: "text-warn",
    ok: "text-ok",
  };
  const chip =
    "inline-flex h-6 items-center whitespace-nowrap rounded-full px-2 text-small font-semibold";

  const pct = (ms: number) => ((ms - t0) / (t1 - t0)) * 100;
  const cells = useMemo(() => (data ? Object.fromEntries(EQS.map((eq) => [eq, cellsOf((data.states[eq] ?? []) as StateRow[], t0, t1)])) : {}), [data, t0, t1]);
  const barRef = useRef<HTMLDivElement>(null);
  const seek = (e: React.PointerEvent) => {
    const r = barRef.current?.getBoundingClientRect();
    if (r) jump(t0 + ((e.clientX - r.left) / r.width) * (t1 - t0));
  };
  const ticks: number[] = [];
  if (data) {
    const step = t1 - t0 > 12 * 36e5 ? 2 * 36e5 : 36e5;
    for (let h = Math.ceil(t0 / step) * step; h <= t1; h += step) ticks.push(h);
  }
  const box = "rounded-card border border-line bg-white shadow-card";

  return (
    <div className="absolute bottom-3 left-4 right-4 top-3 mx-auto flex max-w-[1440px] flex-col gap-3 overflow-hidden text-small">{/* 다른 화면과 같은 폭 1440 가운데 */}
      {/* 결론 띠: 시각 · 무슨 일 · 완제품 · 가동 */}
      <section
        className="grid shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-6 gap-y-2 rounded-card border border-line bg-white px-5 py-3 shadow-card"
        aria-live="polite"
      >
        <div className="flex items-center gap-3">
          <ToneTag tone={tone}>{TONE_WORD[tone]}</ToneTag>
          <span className="font-mono text-band font-bold">
            {md(simIso(t))} {hm(simIso(t))}
          </span>
        </div>
        <div className="min-w-0">
          <div className="text-band font-bold">
            {stop ? (
              <>
                <span className={KEY.crit}>{stop.equipment_id}</span> 알람{" "}
                <span className={`font-mono ${KEY.crit}`}>
                  {stop.alarm_code}
                </span>
                로 멈춘 지{" "}
                <span className={`font-mono ${KEY.crit}`}>
                  {sinceMin(stop)}
                </span>
                분째
              </>
            ) : warn ? (
              <>
                <span className={KEY.warn}>{warn.equipment_id}</span> 주의 알람{" "}
                <span className={`font-mono ${KEY.warn}`}>
                  {warn.alarm_code}
                </span>{" "}
                ·{" "}
                <span className="font-mono">
                  {Math.max(
                    0,
                    Math.round((t - Date.parse(warn.occurred_at)) / 60000),
                  )}
                </span>
                분째
              </>
            ) : (
              <span className={KEY.ok}>켜진 알람 없음</span>
            )}
          </div>
          {(stop || warn) && (
            <div className="mt-1 flex flex-wrap gap-1.5">
              {stop && (
                <>
                  <span className={`${chip} bg-crit text-white`}>
                    ⚠ {alarmName(stop.alarm_code)}
                  </span>
                  {chainOf(stop).length > 1 && (
                    <span className={`${chip} bg-white text-crit`}>
                      연쇄 {chainOf(stop).join(" → ")}
                    </span>
                  )}
                  {stop.lot_no && (
                    <span className={`${chip} bg-white text-ink-2`}>
                      로트 {stop.lot_no}
                    </span>
                  )}
                </>
              )}
              {!stop && warn && (
                <span className={`${chip} bg-warn text-white`}>
                  ▲ {alarmName(warn.alarm_code)}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-x-12 pr-4">
          <div className="flex flex-col gap-1">
            <span className="text-ink-2">완제품</span>
            <span>
              <b className="font-mono text-num leading-tight">
                {frame?.done_today ?? 0}
              </b>
              <span className="ml-1.5 text-ink-2">개</span>
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-ink-2">가동</span>
            <span>
              <b className="font-mono text-num leading-tight">{runNow}</b>
              <span className="ml-1.5 text-ink-2">/ {EQS.length}대</span>
            </span>
          </div>
        </div>
      </section>

      {/* 세로로 남는 공간은 이 줄이 다 차지한다(타임라인이 늘어남). 화면 스크롤 없음: 줄 높이 = 남은 화면, 타임라인 막대가 줄어 맞춘다 → 사건 목록 = 오른쪽 두 칸 높이 */}
      <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)] gap-3">
        {/* 사건 목록 (왼쪽, 높이 = 오른쪽 두 칸 — 안쪽을 absolute로 두어 목록 길이가 줄 높이를 키우지 않게) */}
        <aside className={`${box} relative`} aria-label="사건 목록">
          <div className="absolute inset-0 flex flex-col">
            <div className="flex items-baseline gap-2 px-4 pb-2 pt-3">
              <h3 className="flex items-center gap-2.5 text-card font-bold"><SecIcon title="사건 목록" size={32} />사건 목록</h3>
              <span className="text-ink-2">{events.length}건</span>
            </div>
            <ol
              ref={listRef}
              className="relative min-h-0 flex-1 overflow-y-auto border-t border-line-soft p-2"
            >
              {!data && (
                <li className="p-2 text-ink-2">기록 불러오는 중…</li>
              )}
              {data && events.length === 0 && (
                <li className="p-2 text-ink-2">
                  이 구간에는 알람·병목 변화가 없습니다
                </li>
              )}
              {events.map((e, i) => { const id = `${e.at}-${i}`, open = openEv === id; return (
                <li key={id} className={e.chain ? "pl-3" : ""}>
                  <button
                    onClick={() => { jump(e.at); setOpenEv(open ? null : id); }}
                    aria-current={i === curEv}
                    aria-expanded={open}
                    className={`grid w-full grid-cols-[42px_minmax(0,1fr)] items-start gap-2 rounded-tile border p-2 text-left ${i === curEv ? "border-[#9fd3e0] bg-tile" : "border-transparent hover:bg-tile"}`}
                  >
                    <span className="font-mono font-semibold leading-5">
                      {hm(simIso(e.at))}
                    </span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        <span
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-small font-bold text-white"
                          style={{ background: EV_VIEW[e.kind].color }}
                        >
                          {EV_VIEW[e.kind].icon}
                        </span>
                        <b
                          className={`text-body ${e.kind === "BN" ? "" : "font-mono"} ${e.at < t - 500 && i !== curEv ? "font-normal text-ink-2" : ""}`}
                        >
                          {e.head}
                        </b>
                      </span>
                      <span
                        className={`mt-0.5 block pl-[26px] text-small font-normal text-ink ${open ? "whitespace-normal break-words" : "truncate"}`}
                        title={open ? undefined : e.sub}
                      >
                        {e.sub}
                      </span>
                    </span>
                  </button>
                </li>
              ); })}
            </ol>
          </div>
        </aside>

        <div className="flex min-h-0 min-w-0 flex-col gap-3">
          {/* 그 시각 라인 */}
          <section
            className={`${box} shrink-0 px-5 pb-4 pt-3 [--g:10px] xl:[--g:24px]`}
            aria-label="그 시각 라인"
          >
            <h3 className="flex items-center gap-2.5 text-card font-bold"><SecIcon title="그 시각 라인" size={32} />그 시각 라인</h3>
            <div className="mt-4 grid grid-cols-6 gap-[var(--g)]">
              {EQS.map((eq) => {
                const s = segAt(eq, t),
                  al = act
                    .filter((a) => a.equipment_id === eq)
                    .sort(
                      (a, b) =>
                        (a.severity === "STOP" ? -1 : 1) -
                          (b.severity === "STOP" ? -1 : 1) ||
                        Date.parse(b.occurred_at) - Date.parse(a.occurred_at),
                    )[0]; // 정지 등급 먼저, 같으면 가장 최근 알람
                const st = stateOf(s),
                  down = al?.severity === "STOP" || st === "ALARM",
                  wn = !down && (al?.severity === "WARN" || st === "WARN"),
                  run = !down && !wn && st === "RUN";
                const v = down
                  ? STATE_VIEW.ALARM
                  : wn
                    ? STATE_VIEW.WARN
                    : STATE_VIEW[st];
                const k = down ? "DOWN" : wn ? "WARN" : st,
                  tone = ST_INK[k] ?? ST_INK.IDLE,
                  mins = s ? Math.max(0, Math.round((t - Date.parse(s.start_at)) / 60000)) : null;
                return (
                  <div
                    key={eq}
                    className={`relative flex min-h-[136px] min-w-0 flex-col gap-3 rounded-card bg-gradient-to-b from-white to-[#f7faff] p-4 shadow-[inset_0_1px_0_#fff,0_1px_2px_rgba(27,42,65,.05),0_12px_26px_-16px_rgba(27,42,65,.32)] ${/* 테두리로 상태 (J안, 사용자 선택 2026-10-25): 평소엔 얇게, 막힘 · 주의 · 고장은 굵게, 고장은 맥박 */
                      down ? "rp-ring border-[3px] border-[#d8394b]" : wn || st === "BLOCKED" ? "border-[3px] border-[#d9822b] !shadow-[0_0_0_4px_rgba(217,130,43,.22)]" : st === "RUN" ? "border-2 border-[#1f9d63] !shadow-[0_0_0_3px_rgba(31,157,99,.14)]" : st === "SETUP" ? "border-2 border-[#3d6fe0] !shadow-[0_0_0_3px_rgba(61,111,224,.14)]" : "border border-line"}`}
                  >
                    {(down || wn) && (
                      <span
                        className={`absolute -top-3 right-3 whitespace-nowrap rounded-[7px] px-2 py-0.5 text-[13px] font-bold text-white ${down ? "bg-crit" : "bg-warn"}`}
                      >
                        {down ? "그 시각 알람" : "주의"}
                      </span>
                    )}
                    <b className={`max-w-full truncate font-mono text-card ${run || down || wn ? "text-ink" : "text-ink-2"}`}>{eq}</b>
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-tile text-[18px] font-bold" style={{ background: tone.tile, color: tone.ink }} aria-hidden="true">
                        {v.icon}
                      </span>
                      <div className="min-w-0">
                        <div className="truncate text-band font-bold leading-tight" style={{ color: tone.ink }}>
                          {wn ? "주의" : v.text}
                        </div>
                        {al && (
                          <div className="truncate font-mono text-small font-semibold" style={{ color: tone.ink }} title={alarmName(al.alarm_code)}>
                            알람 {al.alarm_code}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="mt-auto flex items-baseline justify-between gap-2 border-t border-line-soft pt-2 text-small text-ink-2">
                      <span>이 상태</span>
                      {mins != null && <span><b className="font-mono text-card text-ink">{mins}</b>분째</span>}
                    </div>
                  </div>
                );
              })}
            </div>
            {/* 재공: 공정 사이 칩 (개수 / 한도) — 두 카드 사이 틈(--g)의 가운데 */}
            <div className="relative mt-3 h-11">
              <div className="absolute inset-x-[4%] top-1/2 h-1 -translate-y-1/2 rounded-full bg-track" />
              {WIPS.map(([k, col], i) => {
                const n = Number(
                    frame?.wip?.[k as keyof typeof frame.wip] ?? 0,
                  ),
                  W = LAYOUT.wip[k],
                  L = W?.limit,
                  over = !!(L && n > L),
                  warm =
                    !over &&
                    !!(W?.warn && W.warn_over != null && n > W.warn_over);
                return (
                  <div
                    key={k}
                    className={`absolute top-0 -translate-x-1/2 rounded-tile border bg-white px-3 py-0.5 text-center ${over ? "border-crit" : warm ? "border-warn-mark bg-[#fffaf0]" : "border-line"}`}
                    style={{
                      left: `calc(${col} * (100% + var(--g)) / 6 - var(--g) / 2)`,
                    }}
                    title={`${LAYOUT.wip[k]?.from ?? ""} → ${LAYOUT.wip[k]?.to ?? ""} 사이 재공`}
                  >
                    <b
                      className="font-mono text-card"
                      style={{
                        color: over ? "#c62a2f" : warm ? "#9a6200" : undefined,
                      }}
                    >
                      {n}
                    </b>
                    <span className="text-ink-3">/{L ?? "—"}</span>
                    <div className="text-small leading-tight text-ink-2">
                      재공-{i + 1}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* 타임라인 */}
          <section
            className={`${box} flex min-h-0 flex-1 flex-col px-4 py-3`}
            aria-label="타임라인"
          >
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="flex items-center gap-2.5 text-card font-bold"><SecIcon title="타임라인" size={32} />타임라인</h3>
              {/* 시각으로 가기: 날짜·시각만 고른다. 불러오는 범위는 그 시각이 속한 교대 (shiftOf) */}
              <div className="relative">
                <button
                  onClick={() => {
                    const c = simIso(t);
                    setDraft({ d: c.slice(0, 10), tm: c.slice(11, 16) });
                    setJumpOpen((o) => !o);
                  }}
                  aria-expanded={jumpOpen}
                  aria-label={`시각으로 가기, 지금 ${hm(simIso(t))}`}
                  title="시각으로 가기"
                  className="flex h-8 items-center gap-2 rounded-full border border-line bg-tile px-3 text-small font-semibold hover:border-brand"
                >
                  <span aria-hidden>🕘</span>
                  <span className="font-mono">{hm(simIso(t))}</span>
                  <span className="text-ink-3" aria-hidden>
                    ▾
                  </span>
                </button>
                {jumpOpen && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      goTo(Date.parse(`${draft.d}T${draft.tm}:00+09:00`));
                      setJumpOpen(false);
                    }}
                    className="absolute left-0 top-10 z-20 flex w-[300px] flex-col gap-2.5 rounded-tile border border-line-soft bg-white p-3.5 shadow-xl"
                    role="dialog"
                    aria-label="이동할 시각"
                  >
                    <div className="grid grid-cols-[1fr_120px] gap-2">
                      <input
                        type="date"
                        aria-label="날짜"
                        value={draft.d}
                        min="2026-09-01"
                        max={simIso().slice(0, 10)}
                        onChange={(e) =>
                          setDraft((x) => ({ ...x, d: e.target.value }))
                        }
                        className="h-9 w-full rounded-ctl border border-line px-2"
                      />
                      <input
                        type="time"
                        aria-label="시각"
                        value={draft.tm}
                        onChange={(e) =>
                          setDraft((x) => ({ ...x, tm: e.target.value }))
                        }
                        className="h-9 w-full rounded-ctl border border-line px-2"
                      />
                    </div>
                    <span className="text-small text-ink-2">
                      그 시각이 속한 교대(주간 {hh(SHIFT_H.dayStart)}~{hh(SHIFT_H.dayEnd)}시 · 야간 {hh(SHIFT_H.dayEnd)}~{hh(SHIFT_H.nightEnd)}시) 기록을
                      불러옵니다
                    </span>
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setJumpOpen(false)}
                        className="h-8 rounded-ctl border border-line px-3"
                      >
                        취소
                      </button>
                      <button
                        type="submit"
                        disabled={!draft.d || !draft.tm}
                        className="h-8 rounded-ctl bg-brand px-3 font-semibold text-white hover:bg-brand-ink disabled:bg-line"
                      >
                        이동
                      </button>
                    </div>
                  </form>
                )}
              </div>
              <span className="ml-auto flex items-center gap-2">
                <button
                  onClick={() => {
                    if (t >= t1) setT(t0);
                    setPlay((p) => !p);
                  }}
                  className="h-8 rounded-full border border-line bg-white px-3 font-bold"
                >
                  {play ? "⏸ 멈춤" : "▶ 재생"}
                </button>
                {/* 배속: 한 묶음 안에 "1초에" + 1분 | 5분 | 15분 */}
                <span
                  className="flex h-8 items-center rounded-full border border-line bg-tile p-0.5"
                  role="group"
                  aria-label="재생 속도"
                >
                  <span className="px-2.5 text-small text-ink-2">
                    1초에
                  </span>
                  {SPEEDS.map(([v, l]) => (
                    <button
                      key={v}
                      onClick={() => setSpeed(v)}
                      aria-pressed={speed === v}
                      className={`h-7 rounded-full px-3 text-small ${speed === v ? "bg-brand-tint font-semibold text-brand-ink" : "text-ink hover:bg-white"}`}
                    >
                      {l}
                    </button>
                  ))}
                </span>
              </span>
            </div>
            {err && <p className="text-crit">{err}</p>}
            {!data ? (
              <p className="mt-2 text-ink-2">기록 불러오는 중…</p>
            ) : (
              // 화면에 맞추기: 두 열은 같은 짜임(사건 줄 h-6 · 막대 6줄 · 시간 눈금 h-4)이라 줄어도 줄이 맞는다.
              // 막대는 LANE_PX가 최대이고, 세로 자리가 모자라면 같이 얇아진다(최소 6px) — 화면 전체 스크롤 없음
              <div
                className="mt-2 grid min-h-0 flex-1 grid-cols-[64px_minmax(0,1fr)] gap-x-2 outline-none"
                tabIndex={0}
                role="slider"
                aria-label="다시 볼 시각"
                aria-valuemin={t0}
                aria-valuemax={t1}
                aria-valuenow={Math.round(t)}
                aria-valuetext={hm(simIso(t))}
                onKeyDown={(e) => {
                  const d = (e.shiftKey ? 10 : 1) * 60000;
                  if (e.key === "ArrowRight") {
                    e.preventDefault();
                    jump(t + d);
                  }
                  if (e.key === "ArrowLeft") {
                    e.preventDefault();
                    jump(t - d);
                  }
                }}
              >
                <div className="flex min-h-0 flex-col justify-center font-mono text-small">
                  <div className="h-6 shrink-0" />
                  <div className="flex min-h-0 flex-col gap-1.5">
                    {EQS.map((eq) => (
                      <span
                        key={eq}
                        className="flex min-h-[6px] items-center overflow-hidden"
                        style={{ height: LANE_PX }}
                      >
                        {eq}
                      </span>
                    ))}
                  </div>
                  <div className="h-4 shrink-0" />
                </div>
                <div className="flex min-h-0 flex-col justify-center">
                  <div className="relative h-6 shrink-0">
                    {events
                      .filter((e) => e.kind !== "OK" && !e.chain)
                      .map((e, i) => (
                        <button
                          key={i}
                          onClick={() => jump(e.at)}
                          title={`${hm(simIso(e.at))} ${e.head} · ${e.sub}`}
                          aria-label={`${hm(simIso(e.at))} ${e.head} ${e.sub}로 가기`}
                          className={`absolute -translate-x-1/2 border-2 border-white text-small font-bold text-white ${e.kind === "BN" ? "top-1 h-3.5 w-3.5 rotate-45 rounded" : e.kind === "GUIDE" ? "top-1 h-3.5 w-3.5 rounded-full" : "top-0 h-5 w-5 rounded-full"}`}
                          style={{
                            left: `${pct(e.at)}%`,
                            background: EV_VIEW[e.kind].color,
                          }}
                        >
                          {e.kind === "STOP" || e.kind === "WARN"
                            ? EV_VIEW[e.kind].icon
                            : ""}
                        </button>
                      ))}
                  </div>
                  <div
                    ref={barRef}
                    className="relative flex min-h-0 cursor-pointer touch-none flex-col gap-1.5"
                    onPointerDown={(e) => {
                      e.currentTarget.setPointerCapture(e.pointerId);
                      seek(e);
                    }}
                    onPointerMove={(e) => {
                      if (e.buttons) seek(e);
                    }}
                  >
                    {EQS.map((eq) => (
                      <div
                        key={eq}
                        className="relative min-h-[6px] overflow-hidden"
                        style={{ height: LANE_PX }}
                      >
                        {(cells[eq] ?? []).map((c) => (
                          <div
                            key={c.a}
                            title={`${eq} ${hm(simIso(c.a))}~${hm(simIso(c.b))} ${ST_KO[c.key]} (${c.mins.map(([k, m]) => `${ST_KO[k]} ${m}분`).join(" · ")})`}
                            className="absolute top-0 h-full rounded-[3px]"
                            style={{
                              left: `calc(${pct(c.a)}% + 1px)`,
                              width: `calc(${pct(c.b) - pct(c.a)}% - 2px)`,
                              background: ST_COLOR[c.key],
                            }}
                          />
                        ))}
                      </div>
                    ))}
                    <div
                      className="pointer-events-none absolute -top-7 bottom-0 w-[2px] -translate-x-1/2 bg-ink"
                      style={{ left: `${pct(t)}%` }}
                    >
                      <span className="absolute -left-[5px] -top-1 h-3 w-3 rounded-full bg-ink" />
                    </div>
                  </div>
                  <div className="relative h-4 shrink-0 font-mono text-small text-ink-2">
                    {ticks.map((h) => (
                      <span
                        key={h}
                        className="absolute -translate-x-1/2"
                        style={{ left: `${pct(h)}%` }}
                      >
                        {simIso(h).slice(11, 13)}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 pl-[72px] text-small text-ink-2">
              {LEG.map(([k, bg]) => (
                <span key={k} className="flex items-center gap-1">
                  <i
                    className="inline-block h-2.5 w-4 rounded"
                    style={{ background: bg }}
                  />
                  {k}
                </span>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
