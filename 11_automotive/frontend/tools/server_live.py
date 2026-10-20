"""실시간 값 계산: 생성기 Realtime 객체 → 화면이 쓰는 JSON (API-LINE-02~05·07, API-TOOL-01, API-INV-01, API-PM-01, API-LINE-06).

계산식은 생성기·사내 문서와 같게 쓴다.
- 목표 대비 실적·예측: UI설계서 SCR-04 [7] (예측 = 실적 + 최근 1시간 속도 × 남은 시간, 시작 1시간 안은 평균 속도)
- OEE·가동률: 생성기 gen/reports.py 일일 보고서와 같은 식 (DOC-07 §6.2 — OP-30 2대, 성능 = 7.0분 × PQ ÷ APT)
- 필수 정지·손실: gen/reports.py Timeline.stops (고장 그룹 F01~F06 5분 이상), 손실 = 정지 분 ÷ 기준 사이클 (추정)
- MTTR·MTBF: DOC-07 §6 (정지 등급 DOWN만, 30일)
"""
from __future__ import annotations

import bisect
from datetime import date, datetime, timedelta

from gen import records as R
from gen import stage4 as S4
from gen.common import fmt_dt

EQS = ["SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01"]
VFS = ("VF2-01", "VF2-02")
PROCS = ["OP-10", "OP-20", "OP-30", "OP-40", "OP-50"]
CYCLE_DAYS = {"DAILY": 1, "WEEKLY": 7, "MONTHLY": 30, "HALF_YEAR": 182, "YEARLY": 365}


def iso(v):
    if isinstance(v, date) and not isinstance(v, datetime):     # 정비 기록 due_date 같은 날짜만 있는 값
        return v.isoformat()
    return fmt_dt(v) if v is not None else None


def draft_defect_sentence(sq: int, held_lot_nos: list[str]) -> str:
    """교대 보고서 특이 사항의 불량 문장. 로트 보류가 있어도 한 문장이다 — 마침표 문장을 둘로 만들면 특이 사항이 6문장이 된다 (요구사항 FR-PRD-02-07은 3~5문장)."""
    return f"불량(폐기) {sq}개" + (f" (로트 보류: {', '.join(held_lot_nos)})" if held_lot_nos else "") + "."


class Live:
    """Realtime 하나를 감싸 계산을 나눠 둔다. 모든 함수는 서버 잠금 안에서 부른다."""

    def __init__(self, rt, past):
        self.rt, self.P = rt, past
        self.reason_name = {d["reason_code"]: d["reason_name"] for d in rt.M["downtime_reason"]}
        self.fail = {d["reason_code"] for d in rt.M["downtime_reason"] if d["reason_group"] == "FAILURE"}
        self._done = (0, [])

    # ---------- 작은 도구 ----------
    @property
    def sim(self):
        return self.rt.sim

    def lm(self) -> int:
        """마지막으로 계산이 끝난 분 (배열 읽기용)."""
        return self.rt.m - 1

    def to_dt(self, m):
        return self.sim.cal.to_dt(m)

    def shift(self):
        cal, m = self.sim.cal, min(self.rt.m, self.rt.end_m - 1)     # 시연 끝(10/2 08:00)에서도 마지막 교대
        return cal.shift_at(m) or cal.shift_or_near(m)

    def done_ms(self) -> list[int]:
        fin = self.sim.finished
        if self._done[0] != len(fin):
            self._done = (len(fin), sorted(p.start["done"] for p in fin))
        return self._done[1]

    def done_between(self, a, b) -> int:
        d = self.done_ms()
        return bisect.bisect_left(d, b) - bisect.bisect_left(d, a)

    def work_min(self, a, b) -> int:
        cal = self.sim.cal
        return sum(1 for x in range(a, b) if cal.is_work(x))

    def runs(self, eq, a, b):
        """[a, b) 안의 상태 구간 (시작, 끝, 상태 묶음)."""
        rs = self.sim.mach[eq].state_runs
        out = []
        for k, (s, st) in enumerate(rs):
            e = rs[k + 1][0] if k + 1 < len(rs) else self.rt.m
            if e <= a or s >= b:
                continue
            out.append((max(s, a), min(e, b), st))
        return out

    def per_part(self, eq):
        mc = self.sim.mach[eq]
        return mc.base / 30 if eq == "WSH-01" else mc.base

    def alarm(self, aid):
        if not aid:
            return None
        ev = self.sim.alarm_events[aid - 1]
        return ev if ev["id"] == aid else next((e for e in self.sim.alarm_events if e["id"] == aid), None)

    def alarm_json(self, e):
        return {"alarm_event_id": e["id"], "equipment_id": e["equipment_id"], "alarm_code": e["alarm_code"],
                "severity": e["severity"], "occurred_at": iso(self.to_dt(e["occurred_m"])),
                "cleared_at": iso(self.to_dt(e["cleared_m"])) if e["cleared_m"] is not None else None,
                "lot_no": e.get("lot_no"), "prev_alarm_event_id": e.get("prev"), "scenario_code": e.get("scenario")}

    def stops(self, a, b):
        """필수 정지 (DOC-07 §5.4)."""
        out = []
        for eq in EQS:
            for s, e, st in self.runs(eq, a, b):
                if st and st[1] in self.fail and st[0] in ("DOWN", "IDLE") and e - s >= 5:
                    out.append({"equipment_id": eq, "reason_code": st[1], "reason_name": self.reason_name.get(st[1], st[1]),
                                "start_at": iso(self.to_dt(s)), "end_at": iso(self.to_dt(e)), "minutes": e - s,
                                "alarm_event_id": st[3], "loss_qty": round((e - s) / self.per_part(eq), 1), "is_estimated": True})
        out.sort(key=lambda x: (-x["minutes"], x["start_at"]))
        return out

    def losses(self, a, b):
        """손실 = 고장 손실(필수 정지 ÷ 기준 사이클) + 속도 손실(병목 원인 ①②③ 구간: 계획 ÷ 3.5분 − 완료 − 고장 손실) — gen/reports.py 일일 보고서와 같은 식."""
        fl = sum(x["loss_qty"] for x in self.stops(a, b))
        spd = 0.0
        rows = self.rt.past_bn + self.rt.bn_rows
        for k, r in enumerate(rows):
            if r["cause"] not in ("C1", "C2", "C3"):
                continue
            s0, e0 = max(r["m"], a), min(rows[k + 1]["m"] if k + 1 < len(rows) else b, b)
            if e0 > s0:
                fl_i = sum(x["minutes"] / self.per_part(x["equipment_id"]) for x in self.stops(s0, e0))
                spd += max(0.0, self.work_min(s0, e0) / 3.5 - self.done_between(s0, e0) - fl_i)
        return fl, spd

    # ---------- 생산 (API-LINE-03) ----------
    def production(self):
        sh, m, cal = self.shift(), self.rt.m, self.sim.cal
        a, e = cal.to_min(sh.start), cal.to_min(sh.end)
        now = min(max(m, a), e)
        actual = self.done_between(a, now)
        elapsed, left = self.work_min(a, now), self.work_min(now, e)
        tgt = getattr(self, "target_override", None) or sh.target_qty  # 설정(SCR-25)에서 바꾼 교대 목표
        total = tgt + sh.carry_over_qty
        if elapsed >= 60:
            k, x = 0, now
            while k < 60 and x > a:
                x -= 1
                k += 1 if cal.is_work(x) else 0
            rate = self.done_between(x, now) / 60.0
        else:
            rate = actual / elapsed if elapsed else 0.0
        forecast = round(actual + rate * left)
        hourly = []
        t = sh.start
        while t <= self.to_dt(now):
            hourly.append({"at": iso(t), "cum": self.done_between(a, cal.to_min(t))})
            t += timedelta(hours=1)
        if hourly and hourly[-1]["at"] != iso(self.to_dt(now)):
            hourly.append({"at": iso(self.to_dt(now)), "cum": actual})
        fl, spd = self.losses(a, now)
        return {"shift_id": sh.shift_id, "shift_type": sh.shift_type, "start_at": iso(sh.start), "end_at": iso(sh.end),
                "failure_loss_qty": round(fl, 1), "speed_loss_qty": round(spd, 1), "loss_qty": round(fl + spd, 1),
                "short_stops": {"count": sum(1 for eq in EQS for s, e, st in self.runs(eq, a, now) if st and st[1] in self.fail and e - s < 5),
                                "minutes": sum(e - s for eq in EQS for s, e, st in self.runs(eq, a, now) if st and st[1] in self.fail and e - s < 5)},
                "supervisor_user_id": sh.supervisor, "target_qty": tgt, "carry_over_qty": sh.carry_over_qty,
                "total_target_qty": total, "actual_qty": actual, "forecast_qty": forecast, "short_qty": max(0, total - forecast),
                "rate_per_hour": round(rate * 60, 1), "elapsed_work_min": elapsed, "left_work_min": left,
                "risk": elapsed >= 60 and forecast < 0.9 * total, "risk_line_qty": round(0.9 * total, 1),
                "hourly": hourly, "is_estimated": True}

    # ---------- 지표 (API-LINE-04) ----------
    def kpi(self, a=None, b=None):
        sh, cal = self.shift(), self.sim.cal
        a = cal.to_min(sh.start) if a is None else a
        b = min(self.rt.m, cal.to_min(sh.end)) if b is None else b
        planned = self.work_min(a, b)
        reps = [x for x in self.sim.reports.values() if x["process_code"] == "OP-30" and a <= x["end_m"] < b]
        out = {}
        for eq in VFS:
            run = sum(e - s for s, e, st in self.runs(eq, a, b) if st and st[0] == "RUN")
            maint = sum(e - s for s, e, st in self.runs(eq, a, b) if st and st[0] == "MAINT")
            pbt = planned - maint
            r = [x for x in reps if x["equipment_id"] == eq]
            pq, good = sum(x["pq"] for x in r), sum(x["gq"] + x["rq"] for x in r)
            out[eq] = self._oee(run, pbt, pq, good)
        run = sum(sum(e - s for s, e, st in self.runs(eq, a, b) if st and st[0] == "RUN") for eq in VFS)
        pq, good = sum(x["pq"] for x in reps), sum(x["gq"] + x["rq"] for x in reps)
        out["LINE"] = self._oee(run, 2 * planned, pq, good)
        for k, v in out.items():
            v["warn"] = [w for w, bad in (("가동률", k != "LINE" and v["availability_pct"] is not None and v["availability_pct"] < 60),
                                          ("OEE", v["oee_pct"] is not None and v["oee_pct"] < 59)) if bad]
        return {"from": iso(self.to_dt(a)), "to": iso(self.to_dt(b)), "by": out, "mttr_mtbf": self.mttr()}

    @staticmethod
    def _oee(apt, pbt, pq, good):
        av = apt / pbt if pbt > 0 else None
        pe = 7.0 * pq / apt if apt else None
        qu = good / pq if pq else None
        oee = av * pe * qu if None not in (av, pe, qu) else None
        p = lambda x: round(x * 100, 1) if x is not None else None
        return {"oee_pct": p(oee), "availability_pct": p(av), "performance_pct": p(pe), "quality_pct": p(qu),
                "apt_min": apt, "pbt_min": pbt, "pq": pq, "good_qty": good}

    def mttr(self, days=30):
        b = self.rt.m
        a = max(0, b - days * 24 * 60)
        out = {}
        for eq in EQS:
            downs = [(s, e) for s, e, st in self.runs(eq, a, b) if st and st[0] == "DOWN" and st[3]
                     and (self.alarm(st[3]) or {}).get("severity") == "STOP"]
            run = sum(e - s for s, e, st in self.runs(eq, a, b) if st and st[0] == "RUN")
            n = len(downs)
            out[eq] = {"failures": n, "mttr_min": round(sum(e - s for s, e in downs) / n, 1) if n else None,
                       "mtbf_h": round(run / 60 / n, 1) if n else None, "mttr_warn": bool(n and sum(e - s for s, e in downs) / n > 120)}
        return out

    # ---------- 3D·하단 패널 (API-LINE-02) ----------
    def twin(self):
        sim, rt, m, lm = self.sim, self.rt, self.rt.m, self.lm()
        sh = self.shift()
        a = sim.cal.to_min(sh.start)
        reps = [x for x in sim.reports.values() if x["shift_id"] == sh.shift_id]
        by_proc = {p: {"pq": 0, "good": 0, "scrap": 0} for p in PROCS}
        by_eq = {eq: 0 for eq in EQS}
        for x in reps:
            by_proc[x["process_code"]]["pq"] += x["pq"]
            by_proc[x["process_code"]]["good"] += x["gq"] + x["rq"]
            by_proc[x["process_code"]]["scrap"] += x["sq"]
            by_eq[x["equipment_id"]] += x["pq"]
        eqs, fstops = {}, self.stops(a, m)
        for eq in EQS:
            mc = sim.mach[eq]
            st = mc.cur_state or ("IDLE", None, False, None, None)
            since = mc.state_runs[-1][0] if mc.state_runs else m
            al = self.alarm(st[3])
            stop_min = sum(e - s for s, e, x in self.runs(eq, a, m) if x and x[0] in ("DOWN", "IDLE", "BLOCKED", "SETUP"))
            cyc = None
            if mc.cur and mc.rem > 0:
                base = float(rt.cfg["cycle"]["wsh_batch"]["minutes"]) if eq == "WSH-01" else mc.base
                cyc = max(0.0, min(1.0, 1 - mc.rem / base))
            lot = mc.cur[0].lot.lot_no if mc.cur else (mc.last_lot.lot_no if mc.last_lot else None)
            eqs[eq] = {
                "state_code": st[0], "reason_code": st[1], "reason_name": self.reason_name.get(st[1]) if st[1] else None,
                "warn_marker": bool(st[2]), "alarm": self.alarm_json(al) if al else None,
                "since_at": iso(self.to_dt(since)), "minutes": m - since, "lot_no": lot, "parts_in": len(mc.cur),
                "cycle_progress": cyc, "slow": bool(mc.slow),
                "shift_actual_qty": by_eq[eq], "process_actual_qty": by_proc[mc.proc]["pq"], "process_code": mc.proc,
                "stop_min": stop_min, "loss_qty": round(sum(x["loss_qty"] for x in fstops if x["equipment_id"] == eq), 1), "is_estimated": True,  # 라인 손실과 같은 식 (고장 그룹 5분 이상)
                "std_cycle_min": (mc.base if eq != "WSH-01" else float(rt.cfg["cycle"]["wsh_batch"]["minutes"])),
                "tools": [self.tool_json(t, eq) for t in mc.tools.values()],
                "sensor": rt.sensors[eq].last if eq in rt.sensors else None,
            }
        wip = {k: int(v[lm]) for k, v in sim.wip_min.items()}
        bn = rt.judge.cur
        bn_since = (rt.bn_rows[-1]["m"] if rt.bn_rows else (rt.past_bn[-1]["m"] if rt.past_bn else None))
        alarms = [self.alarm_json(e) for e in sim.alarm_events if e["id"] > rt.past["alarm_event"]]
        holds = [{"lot_no": l.lot_no, "hold_id": (l.hold or {}).get("hold_id"), "judged": l.judged_m is not None,
                  "reason": (l.hold or {}).get("reason")} for l in sim.lots if l.on_hold]
        meas = [r for r in rt.insp_rows if r["measured_value"] is not None][-24:]
        return {
            "clock": rt.clock(), "buttons": rt.button_state(), "run_id": None,
            "shift": {"shift_id": sh.shift_id, "shift_type": sh.shift_type, "start_at": iso(sh.start), "end_at": iso(sh.end),
                      "supervisor_user_id": sh.supervisor},
            "equipment": eqs,
            "wip": wip, "soak_qty": int(sim.soak_min[lm]),
            "wip_limits": {w["buffer_code"]: {"limit": int(w["limit_qty"]), "warn_over": int(w["warn_over_qty"]) if w["warn_over_qty"] else None,
                                              "warn": w["warn_enabled"] == "true"} for w in rt.M["wip_buffer"]},
            "bottleneck": {"process_code": bn[0], "cause_code": bn[1], "alarm_event_id": bn[2],
                           "since_at": iso(self.to_dt(bn_since)) if bn_since is not None else None},
            "process": by_proc,
            "done_today": rt.done_today,
            "alarms": alarms,
            "holds": holds,
            "suspect_lot": rt.suspect_lot(),
            "running_event": ({k: v for k, v in rt.active.items() if k in ("code", "equipment_id")} if rt.active else None),
            "last_measure": [{"lot_no": r["lot_no"], "part_seq": r["part_seq"], "item_seq": r["item_seq"], "position": r["position"],
                              "measured_value": r["measured_value"], "judgement": r["judgement"], "measured_at": iso(r["measured_at"])}
                             for r in meas],
            "is_synthetic": True,
        }

    def tool_json(self, t, eq):
        p = t.cum / t.limit
        return {"tool_id": t.tool_id, "tool_no": t.tool_no, "item_no": t.item_no, "equipment_id": eq,
                "usage_pct": round(p * 100, 1), "cum": round(t.cum, 1), "limit": t.limit, "per_part": t.per,
                "left_parts": max(0, int((t.limit - t.cum) // t.per)) if t.per else None, "warn": p >= 0.9}

    # ---------- 작업지시 진행 (API-LINE-05) ----------
    def orders(self):
        sim, cfg, m = self.sim, self.rt.cfg, self.rt.m
        now = self.to_dt(m)
        objs = {o.order_no: o for o in sim.orders}
        out = []
        for r in R.order_rows(sim, cfg):
            o = objs.get(r["order_no"])
            if r["completed_at"] is not None and r["completed_at"] < now - timedelta(hours=24):
                continue
            lots = o.lots if o else []
            scrap = sum(l.scrap for l in lots)
            procs = []
            for l in lots:
                for p in l.parts:
                    if "done" not in p.start:
                        done = [k for k in PROCS if k in p.start]
                        procs.append(PROCS.index(done[-1]) if done else 0)
            cur = PROCS[min(procs)] if procs else ("—" if r["status"] == "WAITING" else "OP-50")
            finished = o.finished if o else 0
            left_qty = r["order_qty"] - finished
            late = r["due_at"] is not None and r["due_at"] < now and r["status"] != "COMPLETED"
            risk = False
            if not late and r["status"] != "COMPLETED" and r["due_at"] is not None:
                due_m = sim.cal.to_min(r["due_at"])
                # 달력은 10/2 08:00까지만 있다 — 그 뒤는 하루 16시간 근무로 어림 (추정)
                avail = self.work_min(m, min(due_m, sim.cal.n_min)) + max(0, due_m - sim.cal.n_min) * 16 / 24
                risk = left_qty * 3.5 > avail
            out.append({"order_no": r["order_no"], "order_qty": r["order_qty"], "done_qty": finished, "defect_qty": scrap,
                        "lots": [l.lot_no for l in lots], "current_process": cur, "due_at": iso(r["due_at"]),
                        "status": r["status"], "delay": "지연" if late else ("▲ 지연 위험" if risk else None),
                        "started_at": iso(r["started_at"]), "completed_at": iso(r["completed_at"])})
        return out

    # ---------- 로트 (API-LOT-01) ----------
    def lots(self):
        sim = self.sim
        plans = {r["lot_no"]: r for r in S4.inspection_rows(sim)}
        out = []
        for l in sim.lots:
            row = {k: (iso(v) if hasattr(v, "isoformat") and not isinstance(v, str) else v) for k, v in
                   {"lot_no": l.lot_no, "order_no": l.order.order_no, "lot_seq": l.lot_seq, "input_shift_id": l.shift_id,
                    "material_lot_no": l.material_lot_no, "input_qty": l.input_qty, "status": S4.lot_status(sim, l),
                    "scrap_qty": l.scrap, "fg_qty": l.fg_qty, "finished": l.finished, "on_hold": l.on_hold,
                    "enhanced": l.enhanced, "enhance_reason": l.enhance_reason, "insp_fail": l.insp_fail}.items()}
            p = plans.get(l.lot_no)
            if p:
                row["plan_mode"], row["judgement"] = p["plan_mode"], p["judgement"]
                row["gauge_pass_qty"], row["gauge_fail_qty"] = p["gauge_pass_qty"], p["gauge_fail_qty"]
            row["judged_at"] = iso(self.to_dt(l.judged_m)) if l.judged_m is not None else None
            pm = S4.passed_m(l)                 # 완제품으로 들어온 시각: 합격 = 판정, 해제 = 해제 (백엔드 v_production_lot.passed_at과 같음)
            row["passed_at"] = iso(self.to_dt(pm)) if pm is not None else None
            row["first_in_at"] = iso(self.to_dt(min(p0.start["OP-10"] for p0 in l.parts))) if l.parts else None
            row["process_done"] = {k: sum(1 for p0 in l.parts if k in p0.start) for k in PROCS}
            row["process_done"]["DONE"] = sum(1 for p0 in l.parts if "done" in p0.start)
            h = l.hold
            row["hold"] = ({"hold_id": h.get("hold_id"), "trigger": h.get("trigger"), "reason": h.get("reason"),
                            "held_by": h.get("held_by"), "held_at": iso(self.to_dt(h["held_m"])) if h.get("held_m") is not None else None,
                            "released_by": h.get("released_by"),
                            "released_at": iso(self.to_dt(h["released_m"])) if h.get("released_m") is not None else None,
                            "scrap_qty": h.get("scrap_qty")} if h else None)
            out.append(row)
        return out

    # ---------- 재고 (API-INV-01) ----------
    def inventory(self):
        live = self.rt._inventory(None) + list(getattr(self, "extra_txns", []))   # 화면에서 넣은 입고·조정·출하·정비 소모품
        stock = dict(self.P.stock)
        for t in live:
            stock[t["item_no"]] = stock.get(t["item_no"], 0) + float(t["qty_change"])
        held = sum(l.input_qty - l.scrap for l in self.sim.lots if l.on_hold or (l.review_m is not None and l.judged_m is None))
        items = []
        so = getattr(self, "safety_override", {})
        for i in self.rt.M["inventory_item"]:
            s = round(stock.get(i["item_no"], 0.0), 2)
            saf = float(so.get(i["item_no"], i["safety_stock"] or 0))
            s0 = round(self.P.stock.get(i["item_no"], 0.0), 2)        # 10/1 08:00 (9월 끝) 재고 — 그때 이미 부족하면 9월에 알림이 나감
            items.append({"item_no": i["item_no"], "category": i["category"], "item_name": i["item_name"], "unit": i["unit"],
                          "owner_role": i["owner_role"], "safety_stock": saf, "stock_qty": s, "low": saf > 0 and s <= saf,
                          "low_at_start": saf > 0 and s0 <= saf})
        txns = [{**{k: (iso(v) if hasattr(v, "isoformat") and not isinstance(v, str) else v) for k, v in t.items()}} for t in live]
        return {"items": items, "held_lot_qty": held, "live_txns": txns}

    # ---------- 공구 (API-TOOL-01) ----------
    def tools(self):
        sim, N = self.sim, self.rt.N
        tools = [self.tool_json(t, eq) for eq, mc in sim.mach.items() for t in mc.tools.values()]
        ch = [{"tool_id": c["tool_id"], "changed_at": iso(self.to_dt(c["changed_m"])), "changed_by": c["changed_by"],
               "cum_before": round(c["cum_before"], 1), "change_reason": c["change_reason"]}
              for c in sim.tool_changes if c["changed_m"] >= N]
        return {"tools": tools, "changes_today": ch}

    # ---------- 예방 정비 (API-PM-01) ----------
    def pm(self):
        rt = self.rt
        today = self.to_dt(rt.m).date()
        last = dict(self.P.pm_last)
        for r in rt.pm_rows:
            last[r["pm_task_id"]] = {"done_at": iso(r["done_at"]), "due_date": str(r["due_date"]), "status": r["status"], "live": True}
        overdue = rt.cfg["sim"]["pm_plan"]["overdue_due"]
        plan_due = rt.cfg["sim"]["pm_plan"]["vf2_monthly_due"]
        out = []
        for t in rt.M["pm_task"]:
            cyc = CYCLE_DAYS.get(t["cycle_code"])
            l = last.get(t["pm_task_id"])
            due = None
            if t["pm_task_id"] in overdue and not (l and l.get("live")):
                due = overdue[t["pm_task_id"]]
            elif cyc and l and l.get("done_at"):
                due = str(date.fromisoformat(l["done_at"][:10]) + timedelta(days=cyc))
            elif t["cycle_code"] == "MONTHLY" and t["equipment_id"] in plan_due:
                v = plan_due[t["equipment_id"]]
                due = v if isinstance(v, str) else v[-1]
            state = None
            if due:
                d = due[:10]
                state = "OVERDUE" if d < str(today) else ("DUE_SOON" if d <= str(today + timedelta(days=1)) else "OK")
            out.append({**t, "last": l, "next_due": due, "state": state})
        done_on_time = [x for x in self.P.pm_rows if x["done_at"] and x["due_date"] and x["done_at"][:10] <= x["due_date"][:10]]
        rate = round(len(done_on_time) / len(self.P.pm_rows) * 100, 1) if self.P.pm_rows else None
        windows = [{"equipment_id": w.equipment_id, "start_at": iso(self.to_dt(w.start_m)), "end_at": iso(self.to_dt(w.end_m)),
                    "kind": w.kind if hasattr(w, "kind") else None} for w in self.sim.maint if w.end_m >= rt.m]
        return {"tasks": out, "on_time_rate_pct": rate, "planned_windows": windows,
                "today_records": [{**{k: (iso(v) if hasattr(v, "isoformat") and not isinstance(v, str) else v) for k, v in r.items()}}
                                  for r in rt.pm_rows]}

    # ---------- 다시 보기 (API-LINE-06) ----------
    def replay(self, a: int, b: int):
        sim, rt = self.sim, self.rt
        b = min(b, rt.m)
        a = max(0, min(a, b - 1))
        states = {eq: [{"start_at": iso(self.to_dt(s)), "end_at": iso(self.to_dt(e)), "state_code": st[0] if st else None,
                        "reason_code": st[1] if st else None, "warn_marker": bool(st and st[2]),
                        "alarm_event_id": st[3] if st else None} for s, e, st in self.runs(eq, a, b)] for eq in EQS}
        step = max(1, (b - a) // 600)
        wip = [{"at": iso(self.to_dt(x)), **{k: int(v[x]) for k, v in sim.wip_min.items()}, "SOAK": int(sim.soak_min[x])}
               for x in range(a, b, step)]
        bns = [r for r in rt.past_bn + rt.bn_rows if a <= r["m"] < b]
        prev = [r for r in rt.past_bn + rt.bn_rows if r["m"] < a]
        bn = [{"at": iso(self.to_dt(r["m"])), "process_code": r["new"], "cause_code": r["cause"], "prev_process_code": r["prev"]}
              for r in (prev[-1:] + bns)]
        alarms = [self.alarm_json(e) for e in sim.alarm_events if a <= e["occurred_m"] < b]
        sensors = {eq: [{"at": iso(self.to_dt(x)), **v} for x, v in sorted(rt.sensor_min[eq].items()) if a <= x < b and (x - a) % step == 0]
                   for eq in rt.sensor_min}
        done = [iso(self.to_dt(d)) for d in self.done_ms() if a <= d < b]
        return {"from": iso(self.to_dt(a)), "to": iso(self.to_dt(b)), "step_min": step, "states": states, "wip": wip,
                "bottleneck": bn, "alarms": alarms, "sensors": sensors, "done": done,
                "sensor_note": "센서는 10/1 실시간 기록만 있음 (9월 센서 CSV는 생성기 generate.py 실행 때만 생김)"}

    # ---------- 교대 보고서 초안 (API-RPT-01, 10/1) ----------
    def shift_draft(self, shift_id):
        sim, cal = self.sim, self.sim.cal
        sh = next((s for s in cal.shifts if s.shift_id == shift_id), None)
        if sh is None:
            return None
        a, e = cal.to_min(sh.start), cal.to_min(sh.end)
        b = min(e, self.rt.m)
        if b <= a:
            return None
        actual = self.done_between(a, b)
        total = sh.target_qty + sh.carry_over_qty
        stops = self.stops(a, b)
        sq = sum(x["sq"] for x in sim.reports.values() if x["shift_id"] == shift_id)
        al = [x for x in sim.alarm_events if a <= x["occurred_m"] < b]
        warn = [x for x in al if x["severity"] == "WARN"]
        stop = [x for x in al if x["severity"] == "STOP"]
        bns = [r for r in self.rt.bn_rows if a <= r["m"] < b and r["cause"] != "BASE"]
        held = [h for h in sim.holds_log if h.get("held_m") is not None and a <= h["held_m"] < b]
        cause = {"C1": "원인 ① 사이클 시간 증가 (공구 마모)", "C2": "원인 ② OP-30 1대만 가동", "C3": "원인 ③ 검사 강화", "FAILURE": "고장", "BASE": "기준 병목"}
        s1 = f"실적 {actual}개 / 총 목표 {total}개 ({actual - total:+d}개)."
        s2 = (f"필수 정지 {len(stops)}건, 합계 {sum(x['minutes'] for x in stops)}분 — 가장 긴 것 {stops[0]['equipment_id']} "
              f"{stops[0]['reason_name']} {stops[0]['minutes']}분 (고장 손실 약 {stops[0]['loss_qty']}개, 추정).") if stops else "필수 정지(고장 그룹 5분 이상) 없음."
        s3 = ("병목: " + ", ".join(f"{self.to_dt(r['m']):%H:%M} {r['new']} {cause.get(r['cause'], r['cause'])}" for r in bns) + ".") if bns else "병목은 기준 병목(OP-30) 그대로."
        s4 = draft_defect_sentence(sq, [h["lot"].lot_no for h in held])
        s5 = (f"주의 알람 {len(warn)}건 ({', '.join(sorted({x['alarm_code'] for x in warn}))})" if warn else "주의 알람 없음") + (f", 정지 등급 알람 {len(stop)}건." if stop else ".")
        kp = self.kpi(a, b)["by"]
        open_ = []
        for eq in EQS:
            st = sim.mach[eq].cur_state
            if st and st[0] == "DOWN":
                open_.append(f"{eq} 고장 중 ({self.reason_name.get(st[1], st[1])})")
        handover = " / ".join(["0 안전: 잠금·표지 중인 설비 없음", "0-1 오래 방치: -", "1 긴급: " + ("; ".join(open_) or "-"),
                               "2 생산 위험: " + ("; ".join(f"병목 {r['new']} {cause.get(r['cause'])}" for r in bns[-1:]) or "-"),
                               "3 주의: " + ("; ".join([f"보류 로트 {l.lot_no}" for l in sim.lots if l.on_hold]) or "-"), "4 참고: -"])
        return {"shift_id": shift_id, "status": "AI_DRAFT", "target_qty": total, "actual_qty": actual, "defect_qty": sq,
                "notable_text": " ".join([s1, s2, s3, s4, s5]), "handover_text": handover, "confirmed_by": None, "confirmed_at": None,
                "current_version": 0, "availability": {eq: kp[eq]["availability_pct"] for eq in VFS}, "stops": stops,
                "lots": sorted({x["lot_no"] for x in sim.reports.values() if x["shift_id"] == shift_id}),
                "bottleneck": [{"at": iso(self.to_dt(r["m"])), "process_code": r["new"], "cause_code": r["cause"]} for r in bns],
                "partial": b < e, "is_synthetic": True}
