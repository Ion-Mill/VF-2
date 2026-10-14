"""4단계 파생 기록: 검사 방식, 로트 보류, 재고 거래, 출하, 병목 기록, 센서 값 (설계서 5.9·5.14·5.15·5.18·5.20).

시간 흐름(flow.py)이 만든 로트 판정·보류 결과를 ERD 칸 모양으로 옮기고, 재고·출하·병목·센서를 계산한다.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np

from .common import KST, at
from .flow import MNT_BY_SHIFT, OPR_BY_PROC, Sim

COLS = {
    "inspection_plan": ["lot_no", "plan_mode", "enhance_reason", "hold_id", "gauge_pass_qty", "gauge_fail_qty",
                        "judgement", "judged_at"],
    "lot_hold": ["hold_id", "lot_no", "trigger_type", "related_alarm_event_id", "related_tool_id", "hold_reason",
                 "held_by", "held_at", "enhanced_next_lots", "released_by", "released_at", "scrap_proposed_qty",
                 "scrap_proposed_by", "scrap_approved_by", "scrap_approved_at", "normal_resumed_by",
                 "normal_resumed_at", "result"],
    "inventory_txn": ["txn_id", "item_no", "txn_type", "qty_change", "txn_at", "txn_by", "source_kind",
                      "work_record_no", "work_record_item_no", "pm_record_id", "tool_change_id", "lot_no",
                      "material_lot_no", "fg_lot_no", "shipment_no", "ship_lot_no", "memo"],
    "shipment": ["shipment_no", "shipped_at", "customer_code", "due_date", "confirmed_by", "status",
                 "fifo_skip_reason", "memo", "current_version"],
    "shipment_line": ["shipment_no", "lot_no", "qty", "lot_passed_at"],
    "bottleneck_log": ["bottleneck_log_id", "changed_at", "prev_process_code", "new_process_code", "cause_code",
                       "alarm_event_id", "actual_qty", "failure_loss_qty"],
    "sensor_sample": ["equipment_id", "sensor_code", "sampled_at", "value", "interval_type"],
}


def lot_status(sim: Sim, lot) -> str:
    """6.8 로트 상태. 9/30 끝 기준 (HOLD_REVIEW·SCRAPPED는 9월 데이터에 없음)."""
    if lot.released_m is not None:
        return "RELEASED"
    if lot.on_hold:
        return "ON_HOLD"
    if lot.judged_m is not None:
        return "PASSED"
    if lot.review_m is not None:
        return "HOLD_REVIEW"                     # 측정 불합격, 반장 보류 전 (DOC-06 §4.1)
    arrived = all("arr50" in p.start or "done" in p.start for p in lot.parts)
    if not sim._lot_closed(lot) or not arrived:
        return "IN_PROCESS"
    gauge_left = any(not p.measured and "done" not in p.start for p in lot.parts)
    return "WAIT_INSPECTION" if gauge_left else "WAIT_JUDGEMENT"


def lot_rows(sim: Sim) -> list[dict]:
    cal = sim.cal
    return [{"lot_no": l.lot_no, "order_no": l.order.order_no, "lot_seq": l.lot_seq, "input_shift_id": l.shift_id,
             "material_lot_no": l.material_lot_no, "input_qty": l.input_qty, "status": lot_status(sim, l),
             "scrap_qty": l.scrap or None, "judged_at": cal.to_dt(l.judged_m) if l.judged_m is not None else None}
            for l in sim.lots]


def passed_m(lot):
    """완제품으로 들어온 시각: 합격 = 판정 시각, 해제 = 해제 시각."""
    if lot.released_m is not None:
        return lot.released_m
    if lot.judged_m is not None and not lot.on_hold:
        return lot.judged_m
    return None


def held_at(lot, m: int) -> bool:
    """m분에 보류 중이었나 (보류 로트 자신만)."""
    h = lot.hold
    return bool(h and h["lot"] is lot and h["held_m"] <= m and (h.get("released_m") is None or m < h["released_m"]))


def hold_label(lot, m: int) -> str:
    h = lot.hold
    if h.get("scrap_approved_m") is not None and lot.judged_m is not None and lot.judged_m <= m < h["scrap_approved_m"]:
        return "보류 (폐기 승인 대기)"
    return "보류"


def inspection_rows(sim: Sim) -> list[dict]:
    cal = sim.cal
    rows = []
    for lot in sim.lots:
        rows.append({"lot_no": lot.lot_no, "plan_mode": "ENHANCED" if lot.enhanced else "NORMAL",
                     "enhance_reason": lot.enhance_reason, "hold_id": lot.hold["hold_id"] if lot.hold else None,
                     "gauge_pass_qty": lot.gauge_pass, "gauge_fail_qty": lot.gauge_fail,
                     "judgement": (("HOLD_REVIEW" if lot.insp_fail else "PASS") if lot.judged_m is not None
                                   else None),
                     "judged_at": cal.to_dt(lot.judged_m) if lot.judged_m is not None else None})
    return rows


def hold_rows(sim: Sim) -> list[dict]:
    cal = sim.cal
    dt = lambda m: cal.to_dt(m) if m is not None else None
    tool_of = {}
    rows = []
    for h in sim.holds_log:
        rows.append({"hold_id": h["hold_id"], "lot_no": h["lot"].lot_no, "trigger_type": h["trigger"],
                     "related_alarm_event_id": h["alarm_id"], "related_tool_id": h["tool_id"],
                     "hold_reason": h["reason"], "held_by": h["held_by"], "held_at": dt(h["held_m"]),
                     "enhanced_next_lots": h["next"], "released_by": h.get("released_by"),
                     "released_at": dt(h.get("released_m")), "scrap_proposed_qty": h.get("scrap_qty"),
                     "scrap_proposed_by": h.get("scrap_by"), "scrap_approved_by": h.get("scrap_approved_by"),
                     "scrap_approved_at": dt(h.get("scrap_approved_m")), "normal_resumed_by": h.get("resumed_by"),
                     "normal_resumed_at": dt(h.get("resumed_m")),
                     "result": "RELEASED" if h.get("released_m") is not None else "IN_PROGRESS"})
    return rows


# ---------- 출하 (설계서 5.20) ----------

def build_shipments(cfg, sim: Sim, order_due: dict[str, date]):
    cal = sim.cal
    ship_hm = cfg["shipment"]["time"]
    first = date.fromisoformat(cfg["shipment"]["first_date"])
    remaining = {lot.lot_no: lot.fg_qty for lot in sim.lots}
    shipped = set()
    heads, lines = [], []
    for d in cal.workdays:
        if d < first:
            continue
        t = cal.to_min(at(d, ship_hm))
        due_lots = [l for l in sim.lots if order_due[l.order.order_no] == d]
        late_lots = [l for l in sim.lots if order_due[l.order.order_no] < d and l.lot_no not in shipped]
        ok = lambda l: passed_m(l) is not None and passed_m(l) <= t and remaining[l.lot_no] > 0
        pick = sorted([l for l in due_lots + late_lots if ok(l) and l.lot_no not in shipped],
                      key=lambda l: (passed_m(l), l.lot_no))
        if not pick:
            continue
        left_out = [l for l in due_lots if not ok(l) and l.fg_qty > 0 and l.lot_no not in shipped]
        no = f"SHP-2609-{len(heads) + 1:03d}"
        memo = []
        if left_out:
            memo.append("부분 출하: " + ", ".join(
                f"{l.lot_no} {hold_label(l, t) if held_at(l, t) else '판정 대기'}"
                for l in left_out) + " — 뺌")
        late = [l for l in pick if order_due[l.order.order_no] < d]
        if late:
            memo.append("늦은 출하 (납기 지남): " + ", ".join(l.lot_no for l in late))
        # FIFO 확인: 이 출하보다 먼저 합격했는데 남아 있는(보류 아님) 로트
        last_pass = max(passed_m(l) for l in pick)
        skipped = [l for l in sim.lots if l.lot_no not in shipped and l not in pick and passed_m(l) is not None
                   and passed_m(l) < last_pass and remaining[l.lot_no] > 0]
        heads.append({"shipment_no": no, "shipped_at": cal.to_dt(t), "customer_code": cfg["shipment"]["customer"],
                      "due_date": d, "confirmed_by": "U10", "status": "CONFIRMED",
                      "fifo_skip_reason": ("먼저 합격한 " + ", ".join(l.lot_no for l in skipped[:5]) +
                                           (" 등" if len(skipped) > 5 else "") + "은 납기가 더 늦어 그 납기일에 출하")
                      if skipped else None,
                      "memo": " / ".join(memo) or None, "current_version": 0})
        for l in pick:
            lines.append({"shipment_no": no, "lot_no": l.lot_no, "qty": remaining[l.lot_no],
                          "lot_passed_at": cal.to_dt(passed_m(l)), "_m": t})
            shipped.add(l.lot_no)
            remaining[l.lot_no] = 0
    return heads, lines, remaining


# ---------- 재고 거래 (설계서 5.14·15.5) ----------

PACK = {"CS-COOL": 20.0, "CS-WLUB": 3.78, "CS-SLUB": 3.79}      # 판매 단위 (DOC-04 4.1·4.2·4.4)


def build_inventory(cfg, sim: Sim, masters, rng, pm_rows, mnt, ship_lines, ship_heads):
    r = rng.stream("inventory")
    cal = sim.cal
    items = {x["item_no"]: x for x in masters["inventory_item"]}
    tt = {x["item_no"]: int(x["deduct_qty_per_change"]) for x in masters["tool_type"]}
    titem = {x["tool_id"]: x["item_no"] for x in masters["tool"]}
    owner_user = {"SUP": "U10", "MNT": "U07"}
    tx = []

    def add(item, kind, q, m_or_dt, by, src, **kw):
        when = cal.to_dt(m_or_dt) if isinstance(m_or_dt, int) else m_or_dt
        tx.append(dict({"item_no": item, "txn_type": kind, "qty_change": round(q, 3), "txn_at": when,
                        "txn_by": by, "source_kind": src}, **kw))

    # 사용: 공구 교체 (충돌로 부러진 공구는 작업기록서 사용 부품으로 뺌 — 두 번 빼지 않음)
    tc_ids = sorted(sim.tool_changes, key=lambda c: (c["changed_m"], c["tool_id"]))
    for i, c in enumerate(tc_ids, 1):
        if c["change_reason"] == "BROKEN":
            continue
        it = titem[c["tool_id"]]
        add(it, "USE", -tt[it], c["changed_m"], c["changed_by"], "TOOL_CHANGE", tool_change_id=i)
    # 사용: 작업기록서 사용 부품
    wr = {w["record_no"]: w for w in mnt["work_record"]}
    for p in mnt["work_record_part"]:
        w = wr[p["record_no"]]
        add(p["item_no"], "USE", -float(p["qty"]), w["confirmed_at"], w["confirmed_by"], "WORK_RECORD",
            work_record_no=p["record_no"], work_record_item_no=p["item_no"])
    # 사용: 예방 정비 소모품 (절삭유는 보충량 × 약 3%, DOC-04 4.2)
    task_item = {t["pm_task_id"]: t["default_item_no"] for t in masters["pm_task"]}
    for p in pm_rows:
        it = task_item.get(p["pm_task_id"])
        if not it or p["result"] != "REFILLED" or p["memo"]:
            continue
        tid = p["pm_task_id"]
        if it == "CS-COOL":
            q = 208 * 0.10 * 0.03 * 6 if tid.endswith("2.2-03") else float(r.uniform(0.2, 0.5))
        elif it == "CS-WLUB":
            q = float(r.uniform(0.5, 0.9))
        elif it == "CS-SLUB":
            q = float(r.uniform(0.2, 0.3))
        else:
            continue          # 그리스: 카트리지를 새로 끼울 때만 1개 (9월에는 한 카트리지로 충분 — DOC-04 4.5)
        add(it, "USE", -round(q, 2), p["done_at"], p["recorded_by"], "PM_RECORD", pm_record_id=p["pm_record_id"])
    # 원자재: 입고·로트 투입
    for ml in sim.materials:
        add("RM-6061", "IN", ml.received_qty, at(ml.received_date, "09:00"), "U10", "MATERIAL_RECEIPT",
            material_lot_no=ml.material_lot_no)
    for lot in sim.lots:
        first = min(p.start["OP-10"] for p in lot.parts)
        add("RM-6061", "USE", -lot.input_qty, first, None, "LOT_INPUT", lot_no=lot.lot_no)
    # 완제품: 합격 입고·출하
    for lot in sim.lots:
        pm = passed_m(lot)
        if pm is not None and lot.fg_qty > 0:
            add("FG-BRK-A100", "FG_IN", lot.fg_qty, pm, None, "LOT_PASS", fg_lot_no=lot.lot_no)
    for ln in ship_lines:
        add("FG-BRK-A100", "SHIP_OUT", -ln["qty"], ln["_m"], "U10", "SHIPMENT", shipment_no=ln["shipment_no"],
            ship_lot_no=ln["lot_no"])

    # 시작 재고 (공구·소모품): 안전 재고 + 1주 사용량 (기준정보_목록 6장 결정 3)
    used = {}
    for t in tx:
        if t["txn_type"] == "USE" and t["item_no"] in items and items[t["item_no"]]["category"] in ("TOOL", "CONSUMABLE"):
            used[t["item_no"]] = used.get(t["item_no"], 0.0) - t["qty_change"]
    week = lambda it: used.get(it, 0.0) * 6 / len(cal.workdays)
    start_dt = datetime(2026, 8, 31, 9, 0, tzinfo=KST)
    for it, x in items.items():
        if x["category"] not in ("TOOL", "CONSUMABLE"):
            continue
        q = float(x["safety_stock"]) + week(it)
        q = math.ceil(q) if x["unit"] == "개" else round(math.ceil(q * 10) / 10, 1)
        add(it, "IN", q, start_dt, owner_user[x["owner_role"]], "RECEIPT", memo="9/1 시작 재고 (안전 재고 + 1주 사용량)")
    # 주 1회 입고 (월요일): 시작 재고 수준까지 채움. 9월 말 축 윤활유·M6 탭은 안전 재고 아래 (설계서 5.14 시연용)
    wd = cfg["inventory"]["tool_consumable_receipt_weekday"]
    mondays = [d for d in cal.workdays if d.strftime("%a").upper()[:3] == wd and d > cal.workdays[0]]
    below = set(cfg["inventory"]["below_safety_at_month_end"])
    for d in mondays:
        when = at(d, "09:00")
        for it, x in items.items():
            if x["category"] not in ("TOOL", "CONSUMABLE") or it == "CS-WLUB":
                continue
            bal = sum(t["qty_change"] for t in tx if t["item_no"] == it and t["txn_at"] < when)
            target = float(x["safety_stock"]) + week(it)
            if it == "TL-TAP6":
                q = cfg["inventory"]["m6_tap_qty_per_receipt"]
                if d == mondays[-1]:          # 마지막 입고를 줄여 월말에 안전 재고 아래로
                    rest = sum(-t["qty_change"] for t in tx if t["item_no"] == it and t["txn_type"] == "USE"
                               and t["txn_at"] >= when)
                    q = max(0, int(float(x["safety_stock"]) - 2 - bal + rest))
            else:
                need = target - bal
                if need <= 0:
                    continue
                q = math.ceil(need / PACK[it]) * PACK[it] if it in PACK else math.ceil(need)
            if q > 0:
                add(it, "IN", q, when, owner_user[x["owner_role"]], "RECEIPT")
    # 월말 실사 조정 (9/30): 공구·소모품·원자재 1~2건, 완제품 0~1건
    end = at(cal.days[-1], "16:00")
    cands = [it for it, x in items.items() if x["category"] in ("TOOL",) and it not in below]
    for it in r.choice(cands, int(r.integers(1, 3)), replace=False):
        add(str(it), "ADJUST", float(r.choice([-1, 1])), end, "U10", "STOCKTAKE", memo="월말 실사 차이 (장부보다 1개 다름)")
    if r.random() < 0.5:
        bal = sum(t["qty_change"] for t in tx if t["item_no"] == "FG-BRK-A100")
        q = -1 if bal >= 1 else 1
        add("FG-BRK-A100", "ADJUST", float(q), end, "U10", "STOCKTAKE", memo="월말 실사 차이 (완제품 1개)")
    tx.sort(key=lambda t: (t["txn_at"], t["item_no"], t["source_kind"]))
    for i, t in enumerate(tx, 1):
        t["txn_id"] = i
    return tx


# ---------- 병목 기록 (설계서 5.18, DOC-07 §7.3·7.4) ----------

FRONT = {"OP-20": "WIP-10-20", "OP-30": "WIP-20-30", "OP-50": "WIP-40-50"}     # 바로 앞 재공 (OP-40 앞은 판단 제외 ⑤)
UP = {"OP-30": ["MIL-01"], "OP-50": ["WSH-01"], "OP-20": ["SAW-01"]}
PRIO = {"FAILURE": 3, "C2": 2, "C1": 1, "C3": 1, "BASE": 0}         # 같은 때 여럿이면: 고장 > 1대 가동 > 나머지
DOWN_EQ = {"OP-30": ["WSH-01"], "OP-20": ["VF2-01", "VF2-02"], "OP-50": []}


def state_arrays(sim: Sim) -> dict[str, list]:
    n = sim.cal.n_min
    out = {}
    for eq, mc in sim.mach.items():
        arr = [None] * n
        runs = mc.state_runs + [[n, None]]
        for (a, st), (b, _) in zip(runs[:-1], runs[1:]):
            arr[a:b] = [st] * (b - a)
        out[eq] = arr
    return out


class BottleneckJudge:
    """1분마다 DOC-07 7.3 규칙을 적용한다 (2026-10-13 해석, 1013 기록 5장).
    과거 기록(build_bottleneck)과 실시간 모드(realtime.py)가 **같은 코드**를 쓴다 (설계서 9장 "생성기 = 플랫폼 규칙").

    - 원인을 알 수 있는 상태(고장 DOWN, ① 사이클 증가 구간, ② VF-2 1대 정비·긴 셋업, ③ 검사 강화)가 있을 때,
      규칙 ①②(앞 재공 30분 증가 + 앞 공정 BLOCKED 또는 뒤 공정 IDLE)가 맞으면 그 공정·원인으로 들어간다.
      고장은 DOWN이 되면 바로 들어간다.
    - 앞 재공이 한도에 차 있고 앞 공정이 BLOCKED면 더 늘 수 없으므로 "늘었다"로 본다.
    - 들어간 뒤에는 그 원인이 끝날 때까지 유지 (재공이 잠깐 줄어도 왔다 갔다 하지 않게). 더 센 원인
      (고장 > VF-2 1대 가동 > 사이클 증가·검사 강화)이 생기면 바뀐다.
    - 여럿이면 앞 재공이 가장 많은 공정 (③). 없으면 기준 병목 OP-30 (BASE, ④).
    - 기준 병목 OP-30 → OP-30 원인 ①처럼 공정이 같아도 **원인이 바뀌면 한 줄** 남긴다.
    """

    def __init__(self, cfg, sim: Sim):
        self.sim, self.cal = sim, sim.cal
        self.W = cfg["bottleneck"]["window_min"]
        self.long_setup = cfg["bottleneck"].get("long_setup_min", 30)
        self.setup_len = {"VF2-01": 0, "VF2-02": 0}
        self.cur = ("OP-30", "BASE", None)

    def _f(self, p, m):
        w = self.sim.wip_min
        if p == "OP-50":                          # OP-50 앞 = 재공 상자 + 온도 맞춤 선반
            return int(w["WIP-40-50"][m]) + int(self.sim.soak_min[m])
        return int(w[FRONT[p]][m])

    def _rule(self, p, m, st):
        up = any(st[e] and st[e][0] == "BLOCKED" for e in UP[p])
        full = p != "OP-50" and self._f(p, m) >= self.sim.buf[FRONT[p]].limit and up   # 한도에 차서 더 늘 수 없음
        if m < self.W or not (self._f(p, m) > self._f(p, m - self.W) or full):
            return False
        dn = any(st[e] and st[e][0] == "IDLE" and st[e][1] == "M02" for e in DOWN_EQ[p])
        return up or dn or p == "OP-50"           # OP-50은 뒤 공정이 없어 앞 재공(선반 포함) 증가만 본다

    def observe(self, m: int, st: dict, slow: dict, enh: bool):
        """m분이 끝난 뒤의 상태(st: 설비 → 상태 묶음), 원인 ① 구간 여부, 검사 강화 중 여부.
        병목이 바뀌면 {"m", "prev", "new", "cause", "alarm"}, 아니면 None."""
        for eq in self.setup_len:
            s_ = st[eq]
            self.setup_len[eq] = self.setup_len[eq] + 1 if s_ and s_[0] == "SETUP" and s_[1] != "S04" else 0
        if not self.cal.is_work(m):
            return None
        active = []                               # (공정, 원인, 알람) — 지금 원인 상태가 있는 것
        for eq, p in (("MIL-01", "OP-20"), ("VF2-01", "OP-30"), ("VF2-02", "OP-30"), ("CMM-01", "OP-50")):
            s_ = st[eq]
            if s_ and s_[0] == "DOWN":
                active.append((p, "FAILURE", s_[3]))
        for eq in ("VF2-01", "VF2-02"):
            s_ = st[eq]
            if s_ and (s_[0] == "MAINT" or self.setup_len[eq] >= self.long_setup):
                active.append(("OP-30", "C2", None))
            if slow[eq]:
                active.append(("OP-30", "C1", None))
        if enh:
            active.append(("OP-50", "C3", None))
        cur = self.cur
        cands = []
        for p, c, aid in dict.fromkeys(active):
            if (p, c, aid) == cur or c == "FAILURE" or self._rule(p, m, st):
                cands.append((self._f(p, m), p, c, aid))
        new = ("OP-30", "BASE", None)
        if cands:
            top = max(PRIO[c] for _, _, c, _ in cands)
            if any((p, c, aid) == cur for _, p, c, aid in cands) and PRIO[cur[1]] >= top:
                new = cur                         # 지금 병목 원인이 이어지는 동안 유지 (더 센 원인이 생기면 바뀜)
            else:
                _, p, c, aid = max([x for x in cands if PRIO[x[2]] == top], key=lambda x: x[0])
                new = (p, c, aid)
        if new == cur:
            return None
        self.cur = new
        return {"m": m, "prev": cur[0], "new": new[0], "cause": new[1], "alarm": new[2]}


def live_enhanced(sim: Sim) -> bool:
    """지금 검사 강화 중인 로트가 OP-50에 와 있나 (실시간 모드용, build_bottleneck의 enh와 같은 뜻)."""
    return any(l.enhanced and l.judged_m is None and any("arr50" in p.start for p in l.parts) for l in sim.lots)


def judge_past(cfg, sim: Sim, states: dict[str, list], n: int | None = None):
    """과거 기록 0 ~ n분을 판단기에 넣는다. (판단기, 바뀐 줄 목록)."""
    n = sim.cal.n_min if n is None else n
    slow = {eq: np.zeros(n, dtype=bool) for eq in ("VF2-01", "VF2-02")}
    for eq, sp in sim.slow_spans.items():
        if eq in slow:
            for a, b in sp:
                slow[eq][a:(b if b is not None else n)] = True
    enh = np.zeros(n, dtype=bool)
    for l in sim.lots:
        ms = [p.start["arr50"] for p in l.parts if "arr50" in p.start]
        if l.enhanced and ms:
            # 강화는 보류한 때부터 (그 전에 OP-50에 온 부품이 있어도). 실시간 live_enhanced와 같은 뜻
            a0 = max(min(ms), l.hold["held_m"] if l.hold else 0)
            enh[a0:(l.judged_m if l.judged_m is not None else n)] = True
    j = BottleneckJudge(cfg, sim)
    rows = []
    eqs = list(sim.mach)
    for m in range(n):
        r = j.observe(m, {eq: states[eq][m] for eq in eqs}, {eq: bool(slow[eq][m]) for eq in slow}, bool(enh[m]))
        if r:
            rows.append(r)
    return j, rows


def bottleneck_rows(sim: Sim, rows: list[dict], n: int, id_start: int = 1) -> list[dict]:
    """바뀐 줄에 구간 실적·고장 손실 (DOC-07 5.3)을 붙여 ERD 칸 모양으로."""
    cal = sim.cal
    done = np.array(sorted(p.start["done"] for p in sim.finished))
    fail_codes = {d["reason_code"] for d in sim.M["downtime_reason"] if d["reason_group"] == "FAILURE"}
    per_part = {eq: (mc.base / 30 if eq == "WSH-01" else mc.base) for eq, mc in sim.mach.items()}
    out = []
    for k, rw in enumerate(rows):
        a = rw["m"]
        b = rows[k + 1]["m"] if k + 1 < len(rows) else n
        actual = int(((done >= a) & (done < b)).sum())
        fl = 0.0
        for eq, mc in sim.mach.items():
            runs = mc.state_runs + [[n, None]]
            for (s0, st), (s1, _) in zip(runs[:-1], runs[1:]):
                if st[1] in fail_codes and st[0] in ("DOWN", "IDLE"):
                    ov = min(s1, b) - max(s0, a)
                    if ov > 0 and s1 - s0 >= 5:
                        fl += ov / per_part[eq]
        out.append({"bottleneck_log_id": id_start + k, "changed_at": cal.to_dt(a), "prev_process_code": rw["prev"],
                    "new_process_code": rw["new"], "cause_code": rw["cause"], "alarm_event_id": rw["alarm"],
                    "actual_qty": actual, "failure_loss_qty": round(fl, 1), "_m": a})
    return out


def build_bottleneck(cfg, sim: Sim, states: dict[str, list]):
    _, rows = judge_past(cfg, sim, states)
    return bottleneck_rows(sim, rows, sim.cal.n_min)


# ---------- 재공 기록 (설계서 5.19: 평소 5분, 사건 전후 30분은 1분) ----------

def event_centers(sim: Sim, bn_rows) -> list[int]:
    c = [e["occurred_m"] for e in sim.alarm_events if e["severity"] in ("WARN", "STOP")]
    return sorted(c + [b["_m"] for b in bn_rows])


def wip_rows(cfg, sim: Sim, centers: list[int]) -> list[dict]:
    cal = sim.cal
    n = cal.n_min
    win = cfg["record_interval"]["around_event_window_min"]
    one = np.zeros(n, dtype=bool)
    for c in centers:
        one[max(0, c - win):min(n, c + win + 1)] = True
    rows = []
    for m in range(n):
        if not (m % cfg["record_interval"]["wip_min"] == 0 or one[m]):
            continue
        ts = cal.to_dt(m)
        kind = "MIN1" if one[m] else "MIN5"
        for code, arr in sim.wip_min.items():
            rows.append({"buffer_code": code, "logged_at": ts, "wip_qty": int(arr[m]),
                         "soak_shelf_qty": int(sim.soak_min[m]) if code == "WIP-40-50" else None,
                         "interval_type": kind})
    return rows


# ---------- 센서 값 (설계서 5.9·5.19, DOC-07 3장) ----------

def build_sensors(cfg, sim: Sim, rng, bottleneck_rows):
    """1분 평균 (평소) + 1초 (정지·주의 등급 알람과 OP-30 병목 기록 앞뒤 30분, 2026-10-13 A안).
    정상 범위는 sensor_item [참고]. 알람 기준값은 만들지 않고, 알람 앞 몇 분에 값이 움직이게 한다."""
    cal = sim.cal
    win = cfg["record_interval"]["around_event_window_min"]
    rows = []
    sensors = ["SpindleLoadPct", "SpindleMotorTemp", "AirPressure", "Xload", "Yload", "Zload", "DcVolt"]
    alarms = [e for e in sim.alarm_events if e["equipment_id"] in ("VF2-01", "VF2-02") and e["severity"] in ("WARN", "STOP")]
    for eq in ("VF2-01", "VF2-02"):
        r = rng.stream(f"sensor-{eq}")
        mc = sim.mach[eq]
        n = cal.n_min
        run = np.zeros(n, dtype=bool)
        runs = mc.state_runs + [[n, None]]
        for (a, st), (b, _) in zip(runs[:-1], runs[1:]):
            if st[0] == "RUN":
                run[a:b] = True
        slow = np.zeros(n, dtype=bool)
        for a, b in sim.slow_spans.get(eq, []):
            slow[a:b] = True
        # 1분 값
        spl = np.where(run, np.clip(r.lognormal(np.log(38), 0.35, n) * np.where(slow, 1.15, 1.0), 0, 185),
                       np.clip(r.normal(1.0, 0.6, n), 0, 3))
        temp = np.empty(n)
        t = 30.0
        for m in range(n):
            target = 40.0 if run[m] else 28.5
            t += (target - t) / 20.0
            temp[m] = t
        temp += r.normal(0, 0.3, n)
        air = np.clip(r.normal(105.3, 1.5, n), 100, 110)
        ax = {a: np.where(run, np.clip(r.normal(22, 8, n), 0, 65), np.clip(r.normal(1, 0.5, n), 0, 3))
              for a in ("Xload", "Yload", "Zload")}
        dc = np.clip(r.normal(317, 3, n), 300, 330)
        # 알람 앞: 공기 압력 서서히 하락(120), 주축 부하 상승(174), 온도 상승(254), 축 부하 급상승(108·994·992)
        for e in alarms:
            if e["equipment_id"] != eq:
                continue
            m0 = e["occurred_m"]
            if e["alarm_code"] == "120":
                k = int(r.integers(20, 31))
                air[max(0, m0 - k):m0 + 1] = np.linspace(air[max(0, m0 - k)], 79.0, m0 + 1 - max(0, m0 - k))
            elif e["alarm_code"] == "174":
                spl[max(0, m0 - 8):m0 + 1] = np.linspace(60, 180, m0 + 1 - max(0, m0 - 8))
            elif e["alarm_code"] == "254":
                temp[max(0, m0 - 30):m0 + 1] = np.linspace(temp[max(0, m0 - 30)], 55.0, m0 + 1 - max(0, m0 - 30))
            elif e["alarm_code"] in ("108", "994", "992"):
                for a in ("Xload", "Yload", "Zload"):
                    ax[a][max(0, m0 - 3):m0 + 1] = np.linspace(40, 115 if a != "Zload" else 90, m0 + 1 - max(0, m0 - 3))
        vals = {"SpindleLoadPct": spl, "SpindleMotorTemp": temp, "AirPressure": air, "DcVolt": dc, **ax}
        # 1초 구간
        centers = [e["occurred_m"] for e in alarms if e["equipment_id"] == eq]
        centers += [b["_m"] for b in bottleneck_rows
                    if b["new_process_code"] == "OP-30" and b["cause_code"] in ("C1", "C2", "FAILURE")]
        sec = np.zeros(n, dtype=bool)
        for c in centers:
            sec[max(0, c - win):min(n, c + win)] = True
        for m in range(n):
            if sec[m]:
                continue
            ts = cal.to_dt(m)
            for s in sensors:
                rows.append((eq, s, ts, round(float(vals[s][m]), 1), "MIN1_AVG"))
        idx = np.flatnonzero(sec)
        for m in idx:
            base = cal.to_dt(int(m))
            nxt = int(m) + 1 if int(m) + 1 < n else int(m)
            for s in sensors:
                v0, v1 = float(vals[s][m]), float(vals[s][nxt])
                noise = {"SpindleLoadPct": 4.0, "Xload": 3.0, "Yload": 3.0, "Zload": 3.0, "AirPressure": 0.3,
                         "SpindleMotorTemp": 0.05, "DcVolt": 1.0}[s]
                seq = np.linspace(v0, v1, 60, endpoint=False) + r.normal(0, noise, 60)
                if not run[m] and s in ("SpindleLoadPct", "Xload", "Yload", "Zload"):
                    seq = np.clip(seq, 0, 3)
                if s == "AirPressure" and min(v0, v1) >= 100:      # 평소 범위 100~110 psi 안 (알람 120 앞 하락 구간만 밖)
                    seq = np.clip(seq, 100, 110)
                for k in range(60):
                    rows.append((eq, s, base + timedelta(seconds=k), round(float(seq[k]), 1), "SEC1"))
    return rows
