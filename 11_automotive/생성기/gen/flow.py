"""③ 시간 흐름: 1분 단위로 설비 6대가 부품을 처리한다 (설계서 4장 ③, 5.5~5.8·5.13).

만드는 것: 원자재·작업지시·생산 로트, 공정 실적, 설비 상태, 알람, 공구 사용·교체, 재공, 불량.
4단계(2026-10-13): OP-50 검사 방식(보통 발췌 / 강화 전수), 온도 맞춤 선반 90분, 로트 판정·보류·해제 (설계서 5.15·5.18 ③).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from .calendar import Calendar
from .common import at, parse_hm
from .plan import MaterialLot, MaintWindow, PlannedAlarm

EPS = 1e-9
FLOW = [("SAW-01", "OP-10"), ("MIL-01", "OP-20"), ("VF2-01", "OP-30"), ("VF2-02", "OP-30"),
        ("WSH-01", "OP-40"), ("CMM-01", "OP-50")]
OPR_BY_PROC = {"DAY": {"OP-10": "U01", "OP-20": "U01", "OP-30": "U02", "OP-40": "U03", "OP-50": "U03"},
               "NIGHT": {"OP-10": "U04", "OP-20": "U04", "OP-30": "U05", "OP-40": "U06", "OP-50": "U06"}}
MNT_BY_SHIFT = {"DAY": ["U07", "U08"], "NIGHT": ["U09"]}


@dataclass
class Part:
    pid: int
    lot: "Lot"
    idx: int                       # 로트 안 순번 (1부터)
    sampled: bool                  # 발췌 측정 부품 (첫 부품 + 5번째마다, ERD planned_measure_qty = 1 + 투입 ÷ 5의 몫)
    start: dict = field(default_factory=dict)   # 공정 → 시작 분
    boosted: bool = False
    defect: tuple | None = None    # (발견 공정, 불량 코드, 처리)
    measured: bool = False         # OP-50에서 측정기로 잼 (발췌·강화). 아니면 게이지·육안만
    boost_tool: str | None = None  # 평균이 움직인 이유: 사용률 90% 넘은 공구 (가장 많이 쓴 것)
    boost_alarm: bool = False      # 평균이 움직인 이유: 108·충돌 직후
    escaped: bool = False          # 측정하지 않아 못 찾은 치수 불량 (나중에 전수로 찾을 수 있음)


@dataclass
class Order:
    order_no: str
    qty: int
    created_m: int
    cut: int = 0
    started_m: int | None = None
    start_shift_type: str | None = None
    start_work_date: date | None = None
    lots: list = field(default_factory=list)
    cur_lot: "Lot | None" = None
    finished: int = 0              # OP-50 통과 + 폐기
    done_m: int | None = None


@dataclass
class Lot:
    lot_no: str
    order: Order
    lot_seq: int
    shift_id: str
    material_lot_no: str
    input_qty: int = 0
    finished: int = 0
    scrap: int = 0
    parts: list = field(default_factory=list)
    enhanced: bool = False         # 검사 강화 (전수 + 항목 확대)
    enhance_reason: str | None = None
    hold: dict | None = None       # 강화 계기 보류 (보류 로트·다음 로트 모두)
    on_hold: bool = False
    rechecks: int = 0              # 강화로 다시 잴 부품 (이미 게이지로 끝난 부품)
    gauge_pass: int = 0
    gauge_fail: int = 0
    judged_m: int | None = None
    released_m: int | None = None
    fg_qty: int = 0                # 완제품으로 들어간 수 (OP-50 양품 + 재작업)
    review_m: int | None = None    # 측정 불합격으로 "보류 검토"가 된 분 (DOC-06 §4.1)
    insp_fail: int = 0             # 측정 불합격 부품 수


@dataclass
class Hold:
    kind: str                      # SETUP / DOWN / MAINT / IDLE
    reason: str
    left: int = 0                  # 일하는 분 기준 남은 분 (wall=False)
    end: int = 0                   # 벽시계 끝 분 (wall=True)
    wall: bool = False
    warn: bool = False
    alarm_id: int | None = None
    maint_ref: object = None
    on_done: object = None         # 끝날 때 부를 함수


@dataclass
class Tool:
    tool_id: str
    tool_no: str
    item_no: str
    per: float
    limit: float
    cum: float
    change_pt: float | None        # None = 한도까지 감 (알람 362)
    episode: bool = False


class Buffer:
    def __init__(self, code: str, limit: int):
        self.code, self.limit, self.q = code, limit, deque()

    def space(self) -> int:
        return self.limit - len(self.q)


class Machine:
    def __init__(self, eq: str, proc: str, base: float):
        self.eq, self.proc, self.base = eq, proc, base
        self.cur: list[Part] = []
        self.rem = 0.0
        self.out: list[Part] = []          # 다 깎았는데 못 내보낸 부품 (BLOCKED)
        self.holds: deque[Hold] = deque()
        self.last_order: str | None = None
        self.tools: dict[str, Tool] = {}
        self.slow = False                  # 병목 원인 ① 구간
        self.since_alarm = 999
        self.gap = 0.0                     # 부품 교체 대기 남은 분 (O04)
        self.state_runs: list[list] = []   # [시작 분, 상태 묶음]
        self.cur_state = None
        self.last_lot: Lot | None = None
        self.resting = False               # 절단기: 재공이 차서 쉬는 중 (다시 시작 기준까지)


class Sim:
    def __init__(self, cfg, cal: Calendar, masters, rng, materials: list[MaterialLot],
                 alarms: list[PlannedAlarm], maint: list[MaintWindow], force_t05_m: int | None = None):
        self.cfg, self.cal, self.M, self.rng = cfg, cal, masters, rng
        self.sim = cfg["sim"]
        self.r = rng.stream("flow")
        self.rt = rng.stream("tools")
        self.rd = rng.stream("defects")
        self.materials = materials
        self.alarm_plan = {eq: deque([p for p in alarms if p.equipment_id == eq]) for eq, _ in FLOW}
        self.maint = sorted(maint, key=lambda w: w.start_m)
        # 9/30 끝 T05 90% 맞추기: 분 번호, 또는 (분 번호, 셋업 분) — 셋업 분은 설계 범위 3~8분 안에서 고름
        self.force_t05_m, self.force_t05_setup = (force_t05_m if isinstance(force_t05_m, (list, tuple))
                                                  else (force_t05_m, None))
        self.force_t05_done = False
        eqs = {e["equipment_id"]: e for e in masters["equipment"]}
        self.mach = {}
        for eq, proc in FLOW:
            e = eqs[eq]
            base = float(e["std_cycle_min"]) if e["std_cycle_min"] else float(e["batch_time_min"])
            self.mach[eq] = Machine(eq, proc, base)
        wb = {w["buffer_code"]: int(w["limit_qty"]) for w in masters["wip_buffer"]}
        self.buf = {k: Buffer(k, v) for k, v in wb.items()}
        self.finished: list[Part] = []
        tt = {t["item_no"]: t for t in masters["tool_type"]}
        for t in masters["tool"]:
            ty = tt[t["item_no"]]
            self.mach[t["equipment_id"]].tools[t["tool_no"]] = Tool(
                t["tool_id"], t["tool_no"], t["item_no"], float(ty["usage_per_part"]), float(ty["life_limit"]),
                float(t["cum_usage"]), self._new_change_pt(t["tool_id"]))
        self.orders: list[Order] = []
        self.lots: list[Lot] = []
        self.pid = 0
        # 기록
        self.alarm_events: list[dict] = []
        self.tool_changes: list[dict] = []
        self.reports: dict[tuple, dict] = {}
        self.tool_usage: dict[tuple, dict] = {}
        self.defects: dict[tuple, dict] = {}
        self.wip_min = {k: np.zeros(cal.n_min, dtype=np.int16) for k in self.buf}   # 1분마다 재공 수
        self.soak_min = np.zeros(cal.n_min, dtype=np.int16)                          # 1분마다 선반 수
        self.maint_done: list[dict] = []
        self.dropped_alarms: list[PlannedAlarm] = []
        self.cause1 = {}                  # 주 번호 → [목표, 지금까지]
        self.limit362 = {}                # 설비 → [분...]
        self._why = None
        self.vf_done_times = {"VF2-01": [], "VF2-02": []}   # OP-30 부품 시작 분 (끝낸 순서)
        self.soak: list = []               # 온도 맞춤 선반 [(준비되는 분, 도착 분, 부품)]
        self.rechecks: deque = deque()     # 강화로 다시 잴 부품
        self.holds_log: list[dict] = []
        self.pending_holds: list[dict] = []
        self.pending_events: list = []     # (분, 함수)
        self.rh = rng.stream("holds")
        self.measure_log: list[dict] = []
        self.tool90: list[tuple] = []          # (공구, 분): 사용률이 90%를 넘은 때
        # 실시간 모드(10/1)는 사람이 하는 일(보류·해제·고장 수리 확정)을 시뮬레이터가 대신하지 않는다
        self.auto_holds = True               # False면 의심·불합격 로트 보류와 해제를 기다림 (화면 조작)
        self.wait_confirm: set[str] = set()  # 이 설비의 정지 등급 고장은 작업기록서 확정까지 DOWN   # 측정기로 잰 부품 1개 = 1건 (측정값·결과 파일 만들기용, quality.py)
        self.slow_spans: dict[str, list] = {}   # 원인 ① 구간 [시작 분, 끝 분] (병목 기록·센서용)
        self.gap_eq = set(self.sim["part_change_gap"]["equipment"])
        self.rg = rng.stream("part_gap")

    def _part_gap(self) -> float:
        g = self.sim["part_change_gap"]
        sec = float(self.rg.lognormal(np.log(g["median_sec"]), g["lognormal_sigma"]))
        return min(sec, g["max_sec"]) / 60.0

    # ---------- 작은 도구 ----------
    def _tr(self, tool_id: str):
        """공구마다 따로 쓰는 난수 (한 공구를 바꿔도 다른 공구·흐름의 난수 순서가 밀리지 않게)."""
        return self.rng.stream(f"tool-{tool_id}")

    def _new_change_pt(self, tool_id: str) -> float | None:
        lo, hi = self.sim["tool_change_point_pct"]
        r = self._tr(tool_id)
        if r.random() < self.sim["tool_limit_alarm_share"]:
            return None
        return float(r.uniform(lo, hi)) / 100.0

    def _jit(self, base: float) -> float:
        lo, hi = self.cfg["cycle"]["jitter_pct"]
        j = float(self.r.uniform(lo, hi)) / 100.0
        return base * (1.0 + float(self.r.choice([-1, 1])) * float(self.r.uniform(0, j)))

    def _rint(self, lo_hi) -> int:
        return int(self.r.integers(lo_hi[0], lo_hi[1] + 1))

    def _shift(self, m):
        return self.cal.shift_at(m)

    def _wdate(self, m) -> date:
        return self.cal.to_dt(m).date()

    # ---------- 작업지시·로트 (설계서 5.5) ----------
    def _new_order(self, m: int) -> Order:
        o = self.cfg["orders"]
        q = int(np.clip(round(float(self.r.lognormal(np.log(o["qty_median"]), 0.28))), *o["qty_range"]))
        pre = f"PO-{self.cal.shift_or_near(m).work_date:%y%m}-"     # 근무일 연월 (10/1 실시간 → PO-2610-)
        od = Order(f"{pre}{sum(1 for x in self.orders if x.order_no.startswith(pre)) + 1:03d}", q, m)
        self.orders.append(od)
        return od

    def _next_order(self, m: int) -> Order:
        uncut = sum(o.qty - o.cut for o in self.orders)
        while uncut < self.sim["order_backlog_min_qty"]:
            uncut += self._new_order(m).qty
        return next(o for o in self.orders if o.cut < o.qty)

    def _material(self, m: int) -> MaterialLot | None:
        today = self._wdate(m)
        for ml in self.materials:
            if ml.remaining > 0 and ml.received_date <= today:
                return ml
        return None

    def _cut_part(self, m: int, order: Order, ml: MaterialLot) -> Part:
        sh = self._shift(m)
        if order.started_m is None:
            order.started_m, order.start_shift_type, order.start_work_date = m, sh.shift_type, sh.work_date
        key = (sh.shift_id, ml.material_lot_no)
        if order.cur_lot is None or (order.cur_lot.shift_id, order.cur_lot.material_lot_no) != key:
            seq = len(order.lots) + 1
            lot = Lot(f"LOT-{order.order_no[3:]}-{seq}", order, seq, sh.shift_id, ml.material_lot_no)
            order.lots.append(lot)
            order.cur_lot = lot
            self.lots.append(lot)
            if seq > 1:
                self._lot_check(order.lots[-2], m)
            for h in self.holds_log:
                if h.get("need", 0) > 0:
                    self._enhance(lot, h, "NEXT_LOT", m)
                    h["next_lots"].append(lot)
                    h["need"] -= 1
                    break
        lot = order.cur_lot
        lot.input_qty += 1
        order.cut += 1
        ml.remaining -= 1
        self.pid += 1
        part = Part(self.pid, lot, lot.input_qty, lot.input_qty == 1 or lot.input_qty % 5 == 0)
        lot.parts.append(part)
        return part

    # ---------- 기록 ----------
    def _report(self, part: Part, mc: Machine, m: int, kind: str):
        sh = self.cal.shift_or_near(m)
        key = (part.lot.lot_no, mc.proc, mc.eq, sh.shift_id)
        rep = self.reports.get(key)
        if rep is None:
            rep = self.reports[key] = {"lot_no": part.lot.lot_no, "process_code": mc.proc, "equipment_id": mc.eq,
                                       "worker_user_id": OPR_BY_PROC[sh.shift_type][mc.proc], "shift_id": sh.shift_id,
                                       "start_m": part.start[mc.proc], "end_m": m, "pq": 0, "gq": 0, "rq": 0, "sq": 0}
        rep["start_m"] = min(rep["start_m"], part.start[mc.proc])
        rep["end_m"] = max(rep["end_m"], m)
        rep["pq"] += 1
        rep[kind] += 1
        return key

    def _defect(self, part: Part, proc: str, code: str, disp: str, m: int, per_part: bool = False):
        sh = self.cal.shift_or_near(m)
        key = (part.lot.lot_no, proc, code) + ((part.pid,) if per_part else ())
        d = self.defects.get(key)
        if d is None:
            d = self.defects[key] = {"lot_no": part.lot.lot_no, "process_code": proc, "defect_code": code, "qty": 0,
                                     "disposition": disp, "found_m": m, "pid": part.pid if per_part else None,
                                     "recorded_by": OPR_BY_PROC[sh.shift_type][proc]}
        d["qty"] += 1

    def _alarm(self, m: int, mc: Machine, code: str, sev: str, prev: int | None = None) -> dict:
        ev = {"id": len(self.alarm_events) + 1, "equipment_id": mc.eq, "alarm_code": code, "severity": sev,
              "occurred_m": m, "cleared_m": None, "lot_no": (mc.cur[0].lot.lot_no if mc.cur else
                                                             (mc.last_lot.lot_no if mc.last_lot else None)),
              "prev": prev}
        self.alarm_events.append(ev)
        if code in ("992", "108"):
            mc.since_alarm = 0
        return ev

    def _hold_for_alarm(self, m: int, mc: Machine, ev: dict, front=True):
        sev, code = ev["severity"], ev["alarm_code"]
        reason = self.sim["alarm_reason_map"][code]
        if sev == "STOP":
            dur = self._rint([30, 180]) if self.r.random() > 0.05 else self._rint([180, 240])
            h = Hold("DOWN", reason, end=m + dur, wall=True, alarm_id=ev["id"])
        elif sev == "WARN":
            if mc.proc == "OP-30":
                dur = self._rint(self.cfg["alarms"]["op30_per_vf2"]["WARN"]["stop_min"])
            else:
                dur = self._rint(self.cfg["alarms"]["other_process_30_days"][code]["effect_min"])
            h = Hold("IDLE", reason, left=dur, warn=True, alarm_id=ev["id"])
        else:
            if mc.proc == "OP-30":
                dur = self._rint(self.cfg["alarms"]["op30_per_vf2"]["GUIDE"]["idle_min"])
            else:
                dur = self._rint(self.cfg["alarms"]["other_process_30_days"][code]["effect_min"])
            h = Hold("IDLE", reason, left=dur, alarm_id=ev["id"])
        if mc.proc != "OP-30" and sev == "STOP":
            spec = self.cfg["alarms"]["other_process_30_days"][code]["effect_min"]
            h.end = m + self._rint(spec)
        if sev == "STOP" and mc.eq in self.wait_confirm:
            h.end = 10 ** 9                      # 작업기록서 확정(화면)까지 DOWN — 실시간 S1

        def done(mm, ev=ev, mc=mc):
            ev["cleared_m"] = mm
            if code == "992":                    # 충돌로 부러진 엔드밀을 수리 끝에 바꿈 (작업기록서 사용 부품 TL-EM10)
                self._tool_change(mm, mc, mc.tools["T02"], "BROKEN", ev["id"])
            if ev.get("case") == "case2_stage2":
                n = sum(1 for e in self.alarm_events if e.get("case") == "case2_stage2" and e["id"] <= ev["id"])
                if n == 3:                       # 반복 알람 1단계 조치 계획: 엔드밀·페이스밀 인서트 교체 (설계서 5.8)
                    self._tool_change(mm, mc, mc.tools["T02"], "OTHER")
                    self._tool_change(mm, mc, mc.tools["T01"], "OTHER")
            for e in self.alarm_events:          # 연쇄의 앞 알람도 함께 해제
                if e["id"] == ev.get("prev"):
                    e["cleared_m"] = mm
                    if e.get("prev"):
                        for e2 in self.alarm_events:
                            if e2["id"] == e["prev"]:
                                e2["cleared_m"] = mm
        h.on_done = done
        if front:
            mc.holds.appendleft(h)
        else:
            mc.holds.append(h)

    def _tool_change(self, m: int, mc: Machine, tool: Tool, reason: str, alarm_id=None, setup_min=None):
        sh = self.cal.shift_or_near(m)
        self.tool_changes.append({"tool_id": tool.tool_id, "changed_m": m, "changed_by": OPR_BY_PROC[sh.shift_type]["OP-30"],
                                  "cum_before": tool.cum, "change_reason": reason, "related_alarm_event_id": alarm_id})
        if tool.episode:
            mc.slow = False
        tool.cum, tool.episode = 0.0, False
        tool.change_pt = self._new_change_pt(tool.tool_id)
        # 한도까지 가는 공구(362)는 한 설비에 하나만
        if tool.change_pt is None and any(x.change_pt is None for x in mc.tools.values() if x is not tool):
            tool.change_pt = float(self._tr(tool.tool_id).uniform(*self.sim["tool_change_point_pct"])) / 100.0
        lo, hi = self.cfg["states"]["setup_tool_change_min"]
        left = int(self._tr(tool.tool_id).integers(lo, hi + 1))
        mc.holds.append(Hold("SETUP", "S02", left=setup_min if setup_min is not None else left))

    # ---------- 부품 시작 전 확인 (셋업·공구) ----------
    def _pre_start(self, m: int, mc: Machine, part: Part) -> bool:
        """셋업이나 공구 교체가 필요하면 Hold를 넣고 False."""
        if mc.eq in self.sim["order_setup_equipment"] and mc.last_order != part.lot.order.order_no:
            mc.last_order = part.lot.order.order_no
            mc.holds.append(Hold("SETUP", "S01", left=self._rint(self.cfg["states"]["setup_order_change_min"])))
            return False
        if mc.proc != "OP-30":
            return True
        # 마지막 날 VF2-01 T05를 90%로 끝내기 위한 교체 (generate.py가 시각을 정함)
        if mc.eq == "VF2-01" and self.force_t05_m is not None and not self.force_t05_done and m >= self.force_t05_m:
            self.force_t05_done = True
            t = mc.tools["T05"]
            self._tool_change(m, mc, t, "LIFE_90" if t.cum / t.limit >= 0.9 else "OTHER", setup_min=self.force_t05_setup)
            t.change_pt = 2.0                       # 9/30 끝까지 바꾸지 않음
            return False
        week = (m // (7 * 1440))
        for tno in sorted(mc.tools):
            t = mc.tools[tno]
            if t.change_pt is None and t.cum + t.per > t.limit + EPS:
                recent = [x for x in self.limit362.get(mc.eq, []) if m - x < 7 * 1440]
                if len(recent) >= 2:            # 같은 설비 362가 7일에 2번을 넘지 않게: 이번엔 한도 직전에 교체
                    self._tool_change(m, mc, t, "LIFE_90")
                    return False
                ev = self._alarm(m, mc, "362", "WARN")
                if self.auto_holds and not any(x.get("src") == "362" for x in self.pending_holds) and not any(
                        h.get("tool_id") for h in self.holds_log) and mc.last_lot is not None:
                    self.pending_holds.append({"at": m + int(self.rh.integers(10, 41)), "lot": mc.last_lot,
                                               "alarm_id": ev["id"], "tool_id": t.tool_id, "next": 1, "src": "362",
                                               "reason": "공구 수명 한계(362)까지 쓴 공구로 가공한 로트 — 비서 의심 로트 제안"})
                self.limit362.setdefault(mc.eq, []).append(m)
                self._hold_for_alarm(m, mc, ev, front=False)
                self._tool_change(m, mc, t, "ALARM_362", ev["id"])
                return False
            if t.change_pt is not None and t.cum / t.limit >= t.change_pt - EPS:
                self._tool_change(m, mc, t, "LIFE_90")
                return False
            if (tno == self.sim["cause1_tool_no"] and not t.episode and t.cum / t.limit >= 0.80
                    and t.change_pt is not None and t.change_pt < 1.0):
                tgt = self.cause1.setdefault(week, [self._rint(self.sim["cause1_per_week"]), 0])
                if tgt[1] < tgt[0]:
                    tgt[1] += 1
                    t.episode, mc.slow = True, True
                    t.change_pt = float(self._tr(t.tool_id).uniform(0.97, 0.99))
        return True

    # ---------- 1분 ----------
    def _set_state(self, mc: Machine, m: int, st: tuple):
        if st != mc.cur_state:
            mc.state_runs.append([m, st])
            mc.cur_state = st

    def _off_state(self, m: int):
        return ("IDLE", "P02" if self.cal.minute_break[m] and self.cal.minute_shift[m] >= 0 else "P03", False, None, None)

    def _input_buf(self, mc):
        return {"OP-20": "WIP-10-20", "OP-30": "WIP-20-30", "OP-40": "WIP-30-40", "OP-50": "WIP-40-50"}.get(mc.proc)

    def _output_buf(self, mc):
        return {"OP-10": "WIP-10-20", "OP-20": "WIP-20-30", "OP-30": "WIP-30-40", "OP-40": "WIP-40-50"}.get(mc.proc)

    def _complete(self, m: int, mc: Machine, part: Part) -> bool:
        """부품을 다음 자리로 내보낸다. 자리가 없으면 False (BLOCKED)."""
        ob = self._output_buf(mc)
        # OP-30: 불량 결정 (설계서 5.5 불량 규칙)
        if mc.proc == "OP-30" and part.defect is None and "decided" not in part.start:
            part.start["decided"] = 1
            p = self.sim["defect_base_rate"] * (self.sim["defect_boost"] if part.boosted else 1.0)
            if self.rd.random() < p:
                u = self.rd.random()
                if u < 0.8:
                    codes = ["DIM-01", "DIM-02", "DIM-03", "DIM-04", "THR-01", "THR-02", "SUR-01", "SUR-02", "SUR-03"]
                    w = np.array([.15, .15, .10, .10, .15, .05, .15, .05, .10])
                    if not part.boosted:            # 치수 불량은 공구 끝·충돌 직후(평균이 움직일 때)만 [설계서 5.15]
                        w[:4] = 0.0
                    code = str(self.rd.choice(codes, p=w / w.sum()))
                    part.defect = ("OP-50", code, "REWORK" if code.startswith("SUR") else "SCRAP")
                elif u < 0.9:
                    part.defect = ("OP-30", str(self.rd.choice(["DIM-01", "DIM-02", "DIM-03", "THR-01"])), "SCRAP")
                else:
                    part.defect = ("OP-40", "SUR-01", "REWORK")
        if mc.proc == "OP-30" and part.defect and part.defect[0] == "OP-30":
            self._report(part, mc, m, "sq")
            self._defect(part, "OP-30", part.defect[1], "SCRAP", m)
            self._scrap(part, m)
            self._after_vf_part(mc, part, m)
            return True
        if mc.proc == "OP-40":
            part.measured = part.sampled or part.lot.enhanced
            part.start["arr50"] = m
            if part.measured:                   # 측정할 부품: 온도 맞춤 선반 90분 이상 (DOC-06 §6.1)
                self.soak.append([m + self.cfg["quality"]["soak_min"]["sampled_with_comp"], m, part])
                ob = None
        if ob is not None:
            b = self.buf[ob]
            if b.space() <= 0:
                return False
            b.q.append(part)
        if mc.proc == "OP-50":
            if part.start.get("recheck"):        # 강화로 다시 잰 부품: 실적에는 다시 세지 않음
                orig = part.lot.parts[part.idx - 1]
                self._log_measure(orig, part.start["OP-50"], m, True)
                if orig.escaped:                 # 게이지로 지나간 치수 불량을 전수 측정에서 찾음
                    self._found_late(orig, m)
                part.lot.rechecks -= 1
                self._lot_check(part.lot, m)
                return True
            if part.lot.enhanced and not part.measured:   # 게이지로 끝난 뒤 강화가 걸림 → 다시 잼
                self._queue_recheck(part, m)
            dim = bool(part.defect and part.defect[0] == "OP-50" and part.defect[1].startswith("DIM"))
            if part.measured:
                self._log_measure(part, part.start["OP-50"], m, False)
            elif dim:                            # 측정하지 않으면 치수 불량을 못 찾음 (게이지·육안은 통과)
                part.escaped = True
            if not part.measured:
                if part.defect and part.defect[0] == "OP-50" and not dim:
                    part.lot.gauge_fail += 1
                else:
                    part.lot.gauge_pass += 1
            if part.defect and part.defect[0] == "OP-50" and not part.escaped:
                kind = "rq" if part.defect[2] == "REWORK" else "sq"
                self._report(part, mc, m, kind)
                if dim:                          # 측정 불합격: 부품마다 한 줄 (측정값과 연결)
                    self._defect(part, "OP-50", part.defect[1], part.defect[2], m, per_part=True)
                    part.lot.insp_fail += 1
                    self._measure_fail(part, m)
                else:
                    self._defect(part, "OP-50", part.defect[1], part.defect[2], m)
                if kind == "sq":
                    self._scrap(part, m)
                    self._lot_check(part.lot, m)
                    return True
            else:
                self._report(part, mc, m, "gq")
            self.finished.append(part)
            part.lot.finished += 1
            part.lot.fg_qty += 1
            part.lot.order.finished += 1
            part.start["done"] = m
            self._order_check(part.lot.order, m)
            self._lot_check(part.lot, m)
            return True
        if mc.proc == "OP-40" and part.defect and part.defect[0] == "OP-40":
            self._report(part, mc, m, "rq")
            self._defect(part, "OP-40", "SUR-01", "REWORK", m)
        else:
            self._report(part, mc, m, "gq")
        if mc.proc == "OP-30":
            self._after_vf_part(mc, part, m)
        return True

    def _after_vf_part(self, mc: Machine, part: Part, m: int):
        sh = self.cal.shift_or_near(m)
        key = (part.lot.lot_no, mc.proc, mc.eq, sh.shift_id)
        for t in mc.tools.values():
            if t.cum / t.limit < 0.9 <= (t.cum + t.per) / t.limit:
                self.tool90.append((t.tool_id, m))       # 공구 수명 알림(90%) 시각 (알림 만들기용, 5단계 ③)
            t.cum += t.per
            u = self.tool_usage.setdefault((t.tool_id, key), {"parts": 0, "usage": 0.0, "cum_after": 0.0, "m": m})
            u["parts"] += 1
            u["usage"] += t.per
            u["cum_after"] = t.cum
            u["m"] = m
        mc.since_alarm += 1
        self.vf_done_times[mc.eq].append(part.start["OP-30"])

    def _scrap(self, part: Part, m: int):
        part.lot.scrap += 1
        part.lot.order.finished += 1
        part.start["done"] = m
        self._order_check(part.lot.order, m)

    def _order_check(self, o: Order, m: int):
        if o.cut == o.qty and o.finished == o.qty and o.done_m is None:
            o.done_m = m

    def _start_part(self, m: int, mc: Machine) -> bool:
        """다음 부품을 올린다. 올렸으면 True. 셋업이 생기거나 일감이 없으면 False (상태는 self._why)."""
        if mc.proc == "OP-10":
            b1 = self.buf["WIP-10-20"]
            # 재공이 saw_pull_wip_max에 차면 쉬고, saw_restart_wip 이하로 내려가면 다시 이어서 자른다 (1개씩 켰다 껐다 하지 않음)
            if len(b1.q) >= self.sim["saw_pull_wip_max"]:
                mc.resting = True
            elif len(b1.q) <= self.sim["saw_restart_wip"]:
                mc.resting = False
            if mc.resting:
                self._why = ("IDLE", "P03")
                return False
            sh = self._shift(m)
            if sh is not None and self.cal.to_min(sh.end) - m < 3:     # 교대 끝 3분 안엔 새로 자르지 않음 (로트 = 한 교대, 1분 ± 흔들림)
                self._why = ("IDLE", "P03")
                return False
            ml = self._material(m)
            if ml is None:
                self._why = ("IDLE", "M01")
                return False
            order = self._next_order(m)
            if mc.eq in self.sim["order_setup_equipment"] and mc.last_order != order.order_no:
                mc.last_order = order.order_no
                mc.holds.append(Hold("SETUP", "S01", left=self._rint(self.cfg["states"]["setup_order_change_min"])))
                self._why = None
                return False
            part = self._cut_part(m, order, ml)
            mc.cur, mc.rem = [part], self._jit(mc.base)
            part.start[mc.proc] = m
            mc.last_lot = part.lot
            return True
        ib = self.buf[self._input_buf(mc)]
        if mc.proc == "OP-40":
            # 한 번 세척 = 한 로트만, 최대 30개 (로트 추적이 섞이지 않게, 2026-10-13). 48개 로트 → 30 + 18
            if not ib.q:
                self._why = ("IDLE", "M02")
                return False
            cap = self.cfg["cycle"]["wsh_batch"]["qty"]
            lots = list({id(p.lot): p.lot for p in ib.q}.values())  # 먼저 온 로트부터
            waiting = set(id(p) for p in ib.q)

            def ready(lot):
                n = sum(1 for p in ib.q if p.lot is lot)
                if n >= cap:
                    return True
                # 로트의 마지막 부품까지 OP-30을 마쳤으면 30개가 안 돼도 세척
                rest = [p for p in lot.parts if id(p) not in waiting and "OP-40" not in p.start and "done" not in p.start]
                return self._lot_closed(lot) and not rest
            pick = next((l for l in lots if ready(l)), None)
            if pick is None:
                upstream_empty = (len(self.buf["WIP-20-30"].q) == 0 and
                                  all(not self.mach[v].cur and not self.mach[v].out for v in ("VF2-01", "VF2-02")) and
                                  not self.mach["MIL-01"].cur and len(self.buf["WIP-10-20"].q) == 0)
                sh = self._shift(m)
                near_end = sh is not None and self.cal.to_min(sh.end) - m <= self.sim["wsh_partial_batch_last_min"]
                if not ((self.sim["wsh_partial_batch_when_upstream_empty"] and upstream_empty) or near_end):
                    self._why = ("IDLE", "M02")
                    return False
                pick = lots[0]
            mc.cur = [p for p in ib.q if p.lot is pick][:cap]
            took = set(id(p) for p in mc.cur)
            ib.q = deque(p for p in ib.q if id(p) not in took)
            for p in mc.cur:
                p.start[mc.proc] = m
            mc.rem = self._jit(float(self.cfg["cycle"]["wsh_batch"]["minutes"]))
            mc.last_lot = mc.cur[-1].lot
            return True
        if mc.proc == "OP-50":
            return self._start_cmm(m, mc, ib)
        if not ib.q:
            self._why = ("IDLE", "M02")
            return False
        part = ib.q[0]
        if not self._pre_start(m, mc, part):
            self._why = None
            return False
        ib.q.popleft()
        mc.cur = [part]
        part.start[mc.proc] = m
        mc.last_lot = part.lot
        if mc.proc == "OP-50":
            cm = self.cfg["cycle"]["cmm_minutes"]
            mc.rem = self._jit(cm["measure_per_part"] if part.sampled else cm["gauge_per_part"])
        elif mc.proc == "OP-30":
            over = [t for t in mc.tools.values() if t.cum / t.limit >= 0.90]
            part.boost_tool = max(over, key=lambda t: t.cum / t.limit).tool_id if over else None
            part.boost_alarm = mc.since_alarm < self.sim["defect_boost_parts_after_alarm"]
            part.boosted = part.boost_alarm or bool(over)
            base = float(self.r.uniform(*self.sim_cause1_cycle())) if mc.slow else mc.base
            mc.rem = self._jit(base)
        else:
            mc.rem = self._jit(mc.base)
        return True

    def _start_cmm(self, m: int, mc: Machine, ib) -> bool:
        """측정기: 다시 잴 부품 먼저, 그다음 (선반에서 준비된 부품 / 재공 상자 부품) 중 먼저 온 것."""
        cm = self.cfg["cycle"]["cmm_minutes"]
        if self.rechecks:
            part = self.rechecks.popleft()
            t = cm["enhanced_per_part"]
        else:
            ready = [x for x in self.soak if x[0] <= m]
            best = min(ready, key=lambda x: (x[1], x[2].pid)) if ready else None
            head = ib.q[0] if ib.q else None
            if best is None and head is None:
                self._why = ("IDLE", "M02")
                return False
            if head is None or (best is not None and best[1] < head.start["arr50"]):
                self.soak.remove(best)
                part = best[2]
            else:
                part = ib.q.popleft()
            if part.measured:
                t = cm["enhanced_per_part"] if part.lot.enhanced else cm["measure_per_part"]
            else:
                t = cm["gauge_per_part"]
        mc.cur = [part]
        part.start[mc.proc] = m
        mc.last_lot = part.lot
        mc.rem = self._jit(t)
        return True

    # ---------- 로트 판정·보류 (설계서 5.5·5.15, DOC-06 §3.3·§4) ----------
    def _lot_closed(self, lot) -> bool:
        return lot is not lot.order.cur_lot or lot.order.cut == lot.order.qty

    def _lot_check(self, lot, m: int):
        """측정 부품까지 모두 잰 로트를 판정한다. 보류 로트는 판정 뒤 반장이 해제."""
        if lot.judged_m is not None or not self._lot_closed(lot):
            return
        if lot.finished + lot.scrap < lot.input_qty or lot.rechecks > 0:
            return
        if lot.review_m is not None and not lot.on_hold:
            return                               # 보류 검토: 반장 보류를 기다림
        lot.judged_m = m
        if lot.on_hold and self.auto_holds:
            self.pending_events.append((m + int(self.rh.integers(30, 91)), lambda mm, lot=lot: self._release(lot, mm)))
        self._resume_check(m)

    def _mgr_time(self, m: int) -> int:
        """관리자(MGR, 주간 근무)가 폐기 제안을 승인하는 시각: m 뒤 첫 주간 교대의 승인 시각대 (config sim.scrap_approval)."""
        sa = self.sim["scrap_approval"]
        for sh in self.cal.shifts:
            if sh.shift_type != "DAY":
                continue
            lo = self.cal.to_min(at(sh.work_date, sa["review_window"][0]))
            hi = self.cal.to_min(at(sh.work_date, sa["review_window"][1]))
            if hi <= m:
                continue
            return max(m, lo) + int(self.rh.integers(0, max(1, hi - max(m, lo))))
        return self.cal.n_min - 1

    def _release(self, lot, m: int):
        h = lot.hold
        if lot.scrap and h.get("scrap_approved_m") is None:
            # 폐기가 있으면: 반장이 폐기 제안 → 관리자 승인(주간) → 반장 해제 (DOC-06 4.1, 설계서 5.5)
            sa = self.sim["scrap_approval"]
            appr = self._mgr_time(m)
            h["scrap_qty"], h["scrap_by"] = lot.scrap, self.cal.shift_or_near(m).supervisor
            h["scrap_approved_by"], h["scrap_approved_m"] = sa["approver"], appr
            lo, hi = sa["release_after_approval_min"]
            t = appr + int(self.rh.integers(lo, hi + 1))
            self.pending_events.append((t, lambda mm, lot=lot: self._release(lot, mm)))
            return
        lot.released_m, lot.on_hold = m, False
        h["released_m"], h["released_by"] = m, self.cal.shift_or_near(m).supervisor
        self._resume_check(m)

    def _resume_check(self, m: int):
        for h in self.holds_log:
            if h.get("resumed_m") is not None or h.get("released_m") is None:
                continue
            lots = [h["lot"]] + h["next_lots"]
            if all(l.judged_m is not None for l in lots):
                t = max(max(l.judged_m for l in lots), h["released_m"]) + int(self.rh.integers(10, 31))
                h["resumed_m"], h["resumed_by"] = t, self.cal.shift_or_near(min(t, self.cal.n_min - 1)).supervisor

    def _enhance(self, lot, h: dict, reason: str, m: int):
        lot.enhanced, lot.enhance_reason, lot.hold = True, reason, h
        ib = self.buf["WIP-40-50"]
        keep = deque()
        for p in ib.q:                       # 재공 상자의 게이지 부품 → 선반으로 (이미 식었으면 바로 잼)
            if p.lot is lot:
                p.measured = True
                self.soak.append([max(p.start["arr50"] + self.cfg["quality"]["soak_min"]["sampled_with_comp"], m),
                                  p.start["arr50"], p])
            else:
                keep.append(p)
        ib.q = keep
        for p in lot.parts:                  # 이미 게이지로 끝난 부품 → 다시 잼 (온도 맞춤 뒤)
            if "done" in p.start and not p.measured and not (p.defect and p.defect[2] == "SCRAP" and not p.escaped):
                self._queue_recheck(p, m)

    def _log_measure(self, part: Part, start_m: int, end_m: int, recheck: bool):
        self.measure_log.append({"part": part, "lot": part.lot, "start_m": start_m, "end_m": end_m,
                                 "enhanced": part.lot.enhanced, "recheck": recheck, "arr50": part.start.get("arr50")})

    def _queue_recheck(self, part: Part, m: int):
        """게이지로 끝난 부품을 다시 잰다. 세척 뒤 90분 온도 맞춤을 지킨다 (DOC-06 §6.1)."""
        part.lot.rechecks += 1
        arr = part.start.get("arr50", m)
        self.soak.append([max(arr + self.cfg["quality"]["soak_min"]["sampled_with_comp"], m), arr,
                          Part(-1, part.lot, part.idx, True, start={"recheck": 1, "arr50": arr})])
        part.measured = True

    def _found_late(self, orig: Part, m: int):
        """다시 재서 찾은 치수 불량: 양품으로 센 것을 폐기로 바꾼다 (같은 실적 줄 안에서)."""
        lot = orig.lot
        sh = self.cal.shift_or_near(orig.start["done"])
        rep_ = self.reports[(lot.lot_no, "OP-50", "CMM-01", sh.shift_id)]
        rep_["gq"] -= 1
        rep_["sq"] += 1
        orig.escaped = False
        orig.defect = ("OP-50", orig.defect[1], "SCRAP")
        lot.finished -= 1
        lot.fg_qty -= 1
        lot.scrap += 1
        self.finished.remove(orig)
        self._defect(orig, "OP-50", orig.defect[1], "SCRAP", m, per_part=True)
        lot.insp_fail += 1
        self._measure_fail(orig, m)

    def _measure_fail(self, part: Part, m: int):
        """측정 불합격 → 로트 "보류 검토" → 남은 부품 전수 → 반장 보류 (DOC-06 §4.1·§4.2, 계기 = 측정 불합격)."""
        lot = part.lot
        if lot.on_hold or (lot.hold and lot.hold["lot"] is lot) or lot.judged_m is not None:
            return                               # 이미 보류된 로트: 불량만 골라냄
        if any(x["lot"] is lot for x in self.pending_holds):
            return
        lot.review_m = m
        self._enhance(lot, None, None, m)        # 남은 부품 전수 (보류하면 HOLD_LOT로 바뀜)
        if not self.auto_holds:
            return                               # 실시간: 반장이 화면에서 보류
        tool = part.boost_tool
        self.pending_holds.append({
            "at": m + int(self.rh.integers(10, 41)), "lot": lot, "alarm_id": None, "tool_id": tool,
            "next": 1 if tool else 2, "trigger": "INSPECTION_FAIL",
            "reason": f"측정 불합격 ({part.defect[1]}) — 보류 검토 로트, 남은 부품 전수 측정"
                      + (f", 원인 후보 공구 {tool}" if tool else ", 108·충돌 직후 가공")})

    def _apply_holds(self, m: int):
        for ph in [x for x in self.pending_holds if x["at"] <= m]:
            self.pending_holds.remove(ph)
            lot = ph["lot"]
            if lot is None or lot.judged_m is not None or lot.on_hold:
                continue
            h = {"hold_id": len(self.holds_log) + 1, "lot": lot, "trigger": ph.get("trigger", "AI_SUSPECT"),
                 "alarm_id": ph["alarm_id"],
                 "tool_id": ph["tool_id"], "reason": ph["reason"], "held_m": m,
                 "held_by": ph.get("held_by") or self.cal.shift_or_near(m).supervisor, "next": ph["next"],
                 "next_lots": []}
            self.holds_log.append(h)
            lot.on_hold = True
            self._enhance(lot, h, "HOLD_LOT", m)
            i = self.lots.index(lot)
            for l2 in self.lots[i + 1:]:
                if len(h["next_lots"]) >= ph["next"]:
                    break
                if l2.judged_m is None and not l2.enhanced:
                    self._enhance(l2, h, "NEXT_LOT", m)
                    h["next_lots"].append(l2)
            h["need"] = ph["next"] - len(h["next_lots"])     # 아직 안 자른 다음 로트는 생길 때 강화
            self._lot_check(lot, m)

    def sim_cause1_cycle(self):
        return self.cfg["bottleneck"]["cause1_cycle_up"]["vf2_cycle_min"]

    def _fire_alarms(self, m: int, mc: Machine, working: bool):
        q = self.alarm_plan[mc.eq]
        while q and q[0].m <= m:
            p = q[0]
            running = working and mc.cur and not mc.holds and not mc.out
            if not (running or (p.force and working)):
                if m - p.m > 8 * 60:
                    self.dropped_alarms.append(q.popleft())
                    continue
                return
            q.popleft()
            ev = self._alarm(m, mc, p.code, p.severity, prev=p.prev_event)
            ev["case"] = p.case
            if p.chain:
                # 충돌 연쇄 (108 → 994 → 992): 앞 알람은 멈추지 않고, 다음 알람을 계획에 끼워 넣는다.
                # DOWN 구간·작업지시서는 마지막 992에만 붙는다 (1013 기록 4장).
                code, gap = p.chain[0]
                nxt = PlannedAlarm(m + gap, mc.eq, code, "STOP", True, chain=p.chain[1:], case="crash",
                                   prev_event=ev["id"])
                i = 0
                while i < len(q) and q[i].m <= nxt.m:
                    i += 1
                q.insert(i, nxt)
                continue
            self._hold_for_alarm(m, mc, ev)
            if p.code == "992" and p.case == "crash":
                lot = mc.cur[0].lot if mc.cur else mc.last_lot
                if mc.cur and mc.cur[0].defect is None:
                    mc.cur[0].defect = ("OP-50", "DIM-02", "SCRAP")     # 충돌 뒤 위치 틀어짐 (DOC-06 §8.2)
                    mc.cur[0].start["decided"] = 1
                if self.auto_holds:
                    self.pending_holds.append({"at": m + int(self.rh.integers(15, 46)), "lot": lot,
                                               "alarm_id": ev["id"], "tool_id": None, "next": 2,
                                               "reason": "충돌 의심(108 → 994 → 992) 때 가공 중이던 로트 — 비서 의심 로트 제안"})
            return

    def _shift_checks(self, m: int):
        """교대 시작·끝 점검 (DOC-04 2.1): 교대 시작 분과 끝 N분 전에 VF-2 준비 구간을 넣는다."""
        sc = self.sim["shift_check"]
        sh = self.cal.shift_at(m)
        if sh is None:
            return
        a, b = self.cal.to_min(sh.start), self.cal.to_min(sh.end)
        for eq in sc["equipment"]:
            mc = self.mach[eq]
            for at_m, dur in ((a, sc["start_min"]), (b - sc["end_min"], sc["end_min"])):
                if m == at_m:
                    h = Hold("SETUP", sc["reason"], left=dur)
                    if mc.holds and mc.holds[0].wall:
                        mc.holds.insert(1, h)
                    else:
                        mc.holds.appendleft(h)

    def _apply_maint(self, m: int):
        while self.maint and self.maint[0].start_m <= m:
            w = self.maint.pop(0)
            mc = self.mach[w.equipment_id]
            if mc.holds and mc.holds[0].kind == "DOWN":      # 고장 중이면 고친 뒤로 미룸
                dur = w.end_m - w.start_m
                w.start_m = mc.holds[0].end
                w.end_m = w.start_m + dur
                self.maint.append(w)
                self.maint.sort(key=lambda x: x.start_m)
                return
            rec = {"window": w, "start_m": m, "end_m": m + (w.end_m - w.start_m)}
            self.maint_done.append(rec)
            mc.holds.appendleft(Hold("MAINT", "P01", end=rec["end_m"], wall=True, maint_ref=rec))

    def _step_machine(self, m: int, mc: Machine, working: bool):
        # 1) 정지·셋업·정비
        while mc.holds:
            h = mc.holds[0]
            if h.wall:
                if m < h.end:
                    ref = self.maint_done.index(h.maint_ref) if h.maint_ref is not None else None
                    self._set_state(mc, m, (h.kind, h.reason, h.warn, h.alarm_id, ref))
                    return
                mc.holds.popleft()
                if h.on_done:
                    h.on_done(m)
                continue
            if not working:
                self._set_state(mc, m, self._off_state(m))
                return
            if h.left <= 0:
                mc.holds.popleft()
                if h.on_done:
                    h.on_done(m)
                continue
            h.left -= 1
            self._set_state(mc, m, (h.kind, h.reason, h.warn, h.alarm_id, None))
            return
        if not working:
            self._set_state(mc, m, self._off_state(m))
            return
        # 2) 가공
        budget, ran, why, gapped = 1.0, False, None, False
        while True:
            if mc.out:
                while mc.out and self._complete(m, mc, mc.out[0]):
                    mc.out.pop(0)
                if mc.out:
                    why = ("BLOCKED", "M03")
                    break
                if mc.eq in self.gap_eq:            # 다 깎은 부품을 내렸으니 다음 부품 올릴 때까지 대기
                    mc.gap = self._part_gap()
            if mc.gap > EPS and not mc.cur:
                use = min(budget, mc.gap)
                mc.gap -= use
                budget -= use
                gapped = True
                if budget <= EPS:
                    break
            if not mc.cur:
                self._why = None
                if not self._start_part(m, mc):
                    why = self._why
                    break
            use = min(budget, mc.rem)
            mc.rem -= use
            budget -= use
            ran = True
            if mc.rem <= EPS:
                done, mc.cur = mc.cur, []
                mc.out.extend(done)
                continue
            if budget <= EPS:
                break
        if ran:
            self._set_state(mc, m, ("RUN", None, False, None, None))
        elif gapped and why is None and not (mc.holds and mc.holds[0].left > 0):
            self._set_state(mc, m, ("IDLE", self.sim["part_change_gap"]["reason"], False, None, None))
        elif why is None:
            # 셋업이 방금 생김 → 이번 분부터 셋업
            h = mc.holds[0]
            h.left -= 1
            self._set_state(mc, m, (h.kind, h.reason, h.warn, h.alarm_id, None))
        else:
            self._set_state(mc, m, (why[0], why[1], False, None, None))

    def step(self, m: int):
        """1분을 돌린다 (과거 기록 모드는 0분부터 끝까지, 실시간 모드는 10/1 08:00부터 1분씩)."""
        working = self.cal.is_work(m)
        self._apply_maint(m)
        self._apply_holds(m)
        for ev in [e for e in self.pending_events if e[0] <= m]:
            self.pending_events.remove(ev)
            ev[1](m)
        for code, b in self.buf.items():
            self.wip_min[code][m] = len(b.q)
        self.soak_min[m] = len(self.soak)
        order = ["CMM-01", "WSH-01", "VF2-02", "VF2-01", "MIL-01", "SAW-01"] if m % 2 else \
            ["CMM-01", "WSH-01", "VF2-01", "VF2-02", "MIL-01", "SAW-01"]
        self._shift_checks(m)
        for eq in order:
            mc = self.mach[eq]
            self._fire_alarms(m, mc, working)
            self._step_machine(m, mc, working)
            sp = self.slow_spans.setdefault(eq, [])
            if mc.slow and (not sp or sp[-1][1] is not None):
                sp.append([m, None])
            elif not mc.slow and sp and sp[-1][1] is None:
                sp[-1][1] = m

    def grow(self):
        """달력이 늘어난 뒤(실시간 모드) 1분 기록 배열을 늘린다."""
        n = self.cal.n_min
        for k, a in self.wip_min.items():
            if len(a) < n:
                self.wip_min[k] = np.concatenate([a, np.zeros(n - len(a), dtype=a.dtype)])
        if len(self.soak_min) < n:
            self.soak_min = np.concatenate([self.soak_min, np.zeros(n - len(self.soak_min), dtype=self.soak_min.dtype)])

    def run(self, finish: bool = True):
        for m in range(self.cal.n_min):
            self.step(m)
        return self.finish() if finish else self

    def finish(self):
        """과거 기록 끝(10/1 08:00) 정리: 열린 구간을 닫는다. 실시간 모드는 부르지 않는다."""
        cal = self.cal
        for sp in self.slow_spans.values():
            if sp and sp[-1][1] is None:
                sp[-1][1] = cal.n_min
        for mc in self.mach.values():
            for h in list(mc.holds):
                if h.on_done and h.wall and h.end <= cal.n_min:
                    h.on_done(h.end)
        return self
