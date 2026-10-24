"""실시간 모드: 10/1 08:00부터 9/30 끝 상태를 이어받아 1분씩 돌린다 (설계서 4장·7장, API-SIM-01·02·03).

- 무작위 알람 없음. 사건은 버튼(inject: S1·S3·S4·S6)으로만 넣는다 (scenarios/사건버튼.json).
- 사람이 하는 일은 시뮬레이터가 대신하지 않는다: 로트 보류·해제, 공구 교체 기록, 작업기록서 확정(고장 복귀).
  화면(서버)이 hold_lot · release_lot · record_tool_change · confirm_work_record 를 부른다.
- 측정기(CMM-01)가 부품을 잴 때마다 결과 파일(CSV)을 공유 폴더 흉내 폴더에 떨어뜨린다 (설계서 5.15 [제안]).
- 시계: 배속(180·60·10·1), 일시정지·다시 시작, 지금 → 17:00(주간 끝) 또는 20:00(야간 시작) 넘기기, 처음으로 되돌리기. 사건 알람이 뜨면 ×10으로 감속.
- 서버·화면 연결 방식은 [선택 필요: 기술 회의]. tick()이 돌려주는 사건 = 실시간 사건(API-STR-01).
- 같은 seed + 같은 조작 순서 = 같은 결과 (리허설용).
"""
from __future__ import annotations

import csv
import io
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from . import quality as Q
from . import records as R
from . import stage4 as S4
from .calendar import extend_calendar
from .common import KST, ROOT, Out, _cell, at, fmt_dt, load_config, load_masters
from .flow import MNT_BY_SHIFT, OPR_BY_PROC, Hold
from .past import run_once, search_t05
from .pm import PROC, next_due
from .plan import MaintWindow, PlannedAlarm

MTC = {"RUN": "ACTIVE", "IDLE": "READY", "BLOCKED": "READY", "DOWN": "STOPPED", "SETUP": None, "MAINT": None}
SENSORS = ["SpindleLoadPct", "SpindleMotorTemp", "AirPressure", "Xload", "Yload", "Zload", "DcVolt"]
NOISE = {"SpindleLoadPct": 4.0, "Xload": 3.0, "Yload": 3.0, "Zload": 3.0, "AirPressure": 0.3,
         "SpindleMotorTemp": 0.05, "DcVolt": 1.0}
MS_PER_MIN = 60_000


class SensorLive:
    """VF-2 센서 1분 평균 (과거 기록 build_sensors와 같은 모양). 사건 때는 override 값으로 바꾼다."""

    def __init__(self, sim, eq: str, rng):
        self.eq, self.r = eq, rng
        mc = sim.mach[eq]
        runs = mc.state_runs + [[sim.cal.n_min, None]]
        run = np.zeros(sim.cal.n_min, dtype=bool)
        for (a, st), (b, _) in zip(runs[:-1], runs[1:]):
            if st and st[0] == "RUN":
                run[a:b] = True
        t = 30.0                                  # 모터 온도: 지난 5시간 상태로 데움 (1차 지연, 20분)
        for m in range(max(0, len(run) - 300), len(run)):
            t += ((40.0 if run[m] else 28.5) - t) / 20.0
        self.temp = t
        self.last = {}

    def step(self, running: bool, slow: bool, override: dict | None = None) -> dict:
        r = self.r
        self.temp += ((40.0 if running else 28.5) - self.temp) / 20.0
        if running:
            spl = float(np.clip(r.lognormal(np.log(38), 0.35) * (1.15 if slow else 1.0), 0, 185))
            ax = [float(np.clip(r.normal(22, 8), 0, 65)) for _ in range(3)]
        else:
            spl = float(np.clip(r.normal(1.0, 0.6), 0, 3))
            ax = [float(np.clip(r.normal(1, 0.5), 0, 3)) for _ in range(3)]
        v = [spl, self.temp + float(r.normal(0, 0.3)), float(np.clip(r.normal(105.3, 1.5), 100, 110)), *ax,
             float(np.clip(r.normal(317, 3), 300, 330))]
        out = {k: round(x, 1) for k, x in zip(SENSORS, v)}
        for k, x in (override or {}).items():
            out[k] = round(float(x), 1)
        self.last = out
        return out


class Realtime:
    def __init__(self, cfg: dict | None = None, masters: dict | None = None, drop_dir: Path | None = None):
        self.cfg = cfg or load_config()
        self.M = masters or load_masters(self.cfg)
        self.rt = self.cfg["realtime"]
        self.scen = json.load(io.open(ROOT / self.rt["scenarios_dir"] / self.rt["event_file"], encoding="utf-8"))
        # 측정 결과 파일 폴더. 시연 데이터 서버는 저장소 밖 폴더를 넘긴다 (out_realtime/cmm_drop은 리허설 결과라 커밋됨)
        self.drop_dir = drop_dir or ROOT / self.rt["out_dir"] / self.rt["cmm_drop_dir"]
        self.force = self._t05_force()
        self.past = json.load(io.open(ROOT / self.cfg["run"]["out_dir"] / "manifest.json", encoding="utf-8"))["rows"]
        self.reset(log=False)

    # ---------- 준비 ----------
    def _t05_force(self):
        """generate.py가 찾은 T05 교체 시각을 쓴다 (같은 seed·설정일 때). 없으면 다시 찾는다."""
        p = ROOT / self.cfg["run"]["out_dir"] / "manifest.json"
        if p.exists():
            man = json.load(io.open(p, encoding="utf-8"))
            if man.get("seed") == self.cfg["run"]["seed"] and "t05_force_m" in man:
                return man["t05_force_m"]
        return search_t05(self.cfg, self.M)[2]

    def reset(self, log: bool = True):
        """처음으로 되돌리기 (API-SIM-03): 과거 30일을 같은 seed로 다시 돌려 10/1 08:00 상태를 만든다 (약 1초)."""
        sim, rng = run_once(self.cfg, self.M, force_t05_m=self.force, finish=False)
        self.N = sim.cal.n_min                                   # 10/1 08:00 분 번호
        states = S4.state_arrays(sim)
        self.judge, self.past_bn = S4.judge_past(self.cfg, sim, states)
        extend_calendar(sim.cal, self.cfg, days=1)               # 10/1 주간·야간 (10/2 08:00까지)
        sim.grow()
        # 10/1: 사람이 하는 일을 시뮬레이터가 대신하지 않음, 우연히 한도까지 가는 공구 없음
        sim.auto_holds = False
        sim.sim = dict(sim.sim, tool_limit_alarm_share=0.0)
        sim.limit362 = {}                                        # 9월의 "7일에 2번" 제한은 무작위 생성용
        rt_tools = rng.stream("rt-tools")
        lo, hi = sim.sim["tool_change_point_pct"]
        wait = self.rt["wait_human_tool"]
        for mc in sim.mach.values():
            for t in mc.tools.values():
                if t.tool_id == wait:
                    t.change_pt = None                           # 사람이 교체할 때까지 기다림, 안 하면 한도 → 362
                elif t.change_pt is None or t.change_pt > 1.0:
                    t.change_pt = float(rt_tools.uniform(lo, hi)) / 100.0
        self.sim, self.rng = sim, rng
        self.rr = rng.stream("rt-events")
        self.rp = rng.stream("rt-preview")                       # 알림 미리보기 버튼 (사건 버튼 난수와 따로)
        self.fix_plan: list[dict] = []                           # 미리보기 '정비': 고장 뒤 보전 담당이 수리 정비로 들어갈 차례
        self.m = self.N                                          # 다음에 돌릴 분
        self.ms = 0                                              # 다음 분까지 쌓인 시뮬레이터 밀리초
        self.speed = self.rt["default_speed"]
        self.paused = False
        self.events: list[dict] = []
        self.bn_rows: list[dict] = []
        self.sensor_min: dict[str, dict[int, dict]] = {"VF2-01": {}, "VF2-02": {}}
        self.sensors = {eq: SensorLive(sim, eq, rng.stream(f"rt-sensor-{eq}")) for eq in ("VF2-01", "VF2-02")}
        self.effects: list[dict] = []                           # 사건 때 센서 모양 {eq, sensor, m0, m1, v0, v1}
        self.prev_state = {eq: mc.cur_state for eq, mc in sim.mach.items()}
        self.prev_alarm = len(sim.alarm_events)
        self.prev_meas = len(sim.measure_log)
        self.prev_wip = None
        self.done_today = 0
        self.tool_pct = {t.tool_id: t.cum / t.limit for mc in sim.mach.values() for t in mc.tools.values()}
        self.active: dict | None = None                         # 진행 중 사건
        self.event_log: list[dict] = []
        self.measurer = Q.Measurer(self.cfg, self.M, rng.stream("measure"), sim.cal, rng.stream("rt-measure"))
        self.insp_rows, self.cmm_rows, self.fail_rid = [], [], {}
        self.pm_rows: list[dict] = []
        self.pm_inv: list[dict] = []
        self.pm_rng = rng.stream("rt-pm")
        self.pm_plan = self._plan_routine_pm()
        if self.drop_dir.exists():
            shutil.rmtree(self.drop_dir)
        self.drop_dir.mkdir(parents=True, exist_ok=True)
        if log:
            self.ops.append({"op": "reset", "sim_at": fmt_dt(self.now())})
        else:
            self.ops = [{"op": "start", "sim_at": fmt_dt(self.now())}]
        self._emit("sim_clock", reason="reset" if log else "start")

    # ---------- 시계 (API-SIM-02) ----------
    def now(self) -> datetime:
        return self.sim.cal.to_dt(self.m)

    @property
    def end_m(self) -> int:
        return self.sim.cal.n_min

    def button_state(self) -> dict:
        """버튼마다 누를 수 있나와 이유 (설계서 7장: 대상 설비 가공 중일 때만, 진행 중 사건이 있으면 잠금)."""
        out = {}
        for code in self.rt["buttons"]:
            eq = self.scen[code]["equipment_id"]
            if self.active:
                out[code] = "진행 중 사건 있음"
            elif self.sim.mach[eq].cur_state is None or self.sim.mach[eq].cur_state[0] != "RUN":
                out[code] = "대상 설비 가공 중 아님"
            else:
                out[code] = None
        return out

    def clock(self) -> dict:
        return {"sim_at": fmt_dt(self.now()), "speed": self.speed, "paused": self.paused,
                "running_event": self.active["code"] if self.active else None,
                "buttons_locked": self.active is not None, "finished": self.m >= self.end_m}

    def set_speed(self, x: int):
        if x not in self.rt["speeds"]:
            raise ValueError(f"배속은 {self.rt['speeds']} 중 하나")
        self.speed = x
        self._op("speed", value=x)

    def pause(self):
        self.paused = True
        self._op("pause")

    def resume(self):
        self.paused = False
        self._op("resume")

    def skip(self, to: str = "TODAY_17:00"):
        """지금 → 오늘 17:00(주간 끝) 또는 20:00(야간 시작). 그 사이를 빠르게 만든다. 그 시각이 지났으면 시계는 그대로."""
        if to not in self.rt["skip_targets"]:
            raise ValueError(f"넘기기는 {self.rt['skip_targets']}만")
        hour = {"TODAY_17:00": 17, "TODAY_20:00": 20}.get(to)
        if hour is None:
            raise ValueError(f"넘기기는 {self.rt['skip_targets']}만")
        day = self.sim.cal.shift_or_near(self.m).work_date
        target = self.sim.cal.to_min(datetime(day.year, day.month, day.day, hour, 0, tzinfo=KST))
        start = self.now()
        out = []
        while self.m < min(target, self.end_m):
            out += self._minute()
        self.ms = 0
        self._op("skip", to=to, from_at=fmt_dt(start))
        return out

    def tick(self, real_sec: float) -> list[dict]:
        """실제 시간 real_sec초가 흘렀다. 배속만큼 시뮬레이터 분을 돌리고 그동안 생긴 사건을 돌려준다."""
        if self.paused or self.m >= self.end_m:
            return []
        self.ms += int(round(real_sec * 1000)) * self.speed
        out = []
        while self.ms >= MS_PER_MIN and self.m < self.end_m:
            self.ms -= MS_PER_MIN
            out += self._minute()
        if self.m >= self.end_m and not self.paused:
            self.paused = True
            out += self._emit("sim_clock", reason="end")
        return out

    # ---------- 사건 버튼 (API-SIM-01) ----------
    def inject(self, code: str) -> dict:
        """사건 버튼. 누를 수 없으면 ValueError(이유). 돌려주는 값: 사건 정보."""
        if code not in self.rt["buttons"]:
            raise ValueError(f"사건 버튼은 {self.rt['buttons']} 중 하나")
        why = self.button_state()[code]
        if why:
            raise ValueError(why)
        sim, m, sc = self.sim, self.m, self.scen[code]
        eq = sc["equipment_id"]
        mc = sim.mach[eq]
        ev = {"code": code, "equipment_id": eq, "start_m": m, "alarm_ids": []}
        if code == "S1":                                        # 축 부하 급상승 → 108 → 994 → 992 → DOWN
            ramp = sc["ramp_min"]
            g1, g2 = (int(self.rr.integers(sc["gap_min"][0], sc["gap_min"][1] + 1)) for _ in range(2))
            self._plan_alarm(PlannedAlarm(m + ramp, eq, sc["alarms"][0], "WARN", True,
                                          chain=[(sc["alarms"][1], g1), (sc["alarms"][2], g2)], case="crash"))
            sim.wait_confirm.add(eq)
            for k, peak in sc["axis_peak_pct"].items():
                v0 = self.sensors[eq].last.get(k, 22.0)
                self.effects.append({"eq": eq, "sensor": k, "m0": m, "m1": m + ramp, "v0": v0, "v1": peak})
        elif code == "S3":                                      # T05가 평소보다 빨리 닳음
            t = next(t for t in mc.tools.values() if t.tool_id == sc["tool_id"])
            ev["tool_id"], ev["base_per"] = t.tool_id, t.per
            t.per = t.per * sc["wear_factor"]
            t.change_pt = None                                   # 교체 기록이 없으면 한도 → 362
            ev["changes_before"] = sum(1 for c in sim.tool_changes if c["tool_id"] == t.tool_id)
        elif code == "S4":                                      # 공기 압력이 서서히 떨어짐 → 120
            k = int(self.rr.integers(sc["decline_min"][0], sc["decline_min"][1] + 1))
            self._plan_alarm(PlannedAlarm(m + k, eq, sc["alarm"], "WARN", True))
            v0 = self.sensors[eq].last.get("AirPressure", 105.3)
            self.effects.append({"eq": eq, "sensor": "AirPressure", "m0": m, "m1": m + k, "v0": v0, "v1": sc["end_psi"]})
        elif code == "S6":                                      # VF2-02 예방 정비 90분 (계획 정비, 알람 없음)
            tasks = [t["pm_task_id"] for t in self.M["pm_task"] if t["equipment_id"] == eq
                     and t["cycle_code"] == "MONTHLY" and t["on_calendar"] == "true"]
            w = MaintWindow(eq, m, m + sc["maint_min"], "PM_MONTHLY", tasks, date.fromisoformat(sc["due_date"]))
            sim.maint.append(w)
            sim.maint.sort(key=lambda x: x.start_m)
            ev["window"] = w
        elif code == "S7":                                      # 알람 없이 작업자가 멈춤 (사유 없음) → 화면의 '기록 없는 정지' → 선조치 기록
            mc.holds.appendleft(Hold("IDLE", None, end=m + sc["idle_min"], wall=True))
            ev["end_plan_m"] = m + sc["idle_min"]
        self.active = ev
        self.event_log.append(ev)
        self._op("inject", scenario_code=code, equipment_id=eq)
        self._emit("event_started", at=fmt_dt(self.now()), scenario_code=code, equipment_id=eq, name=sc["name"])
        return {k: v for k, v in ev.items() if k != "window"}

    # ---------- 알림 미리보기 버튼 (화면 담당 확인용, 2026-10-21) ----------
    PREVIEW_EQ = {"OP-10": ["SAW-01"], "OP-20": ["MIL-01"], "OP-30": ["VF2-01", "VF2-02"], "OP-40": ["WSH-01"], "OP-50": ["CMM-01"]}

    def fire(self, kind: str) -> dict:
        """지금 분에 알람 하나를 일으킨다. warn = 주의 아무거나, stop = 고장(정지 등급) 아무거나, air = 120 공기압,
        maint = 고장 3분 뒤 보전 담당이 수리 정비(MAINT 20~40분, 사유는 그 고장)로 들어감. 누를 수 없으면 ValueError(이유)."""
        if kind not in ("warn", "stop", "air", "maint"):
            raise ValueError("kind는 warn·stop·air·maint 중 하나")
        if self.paused or self.m >= self.end_m:
            raise ValueError("시연이 멈춰 있습니다 — [시연 ▾]에서 다시 돌리세요")
        if not self.sim.cal.is_work(self.m):                    # 휴식·휴무 분에는 설비가 서 있어 알람이 근무 재개 때까지 밀린다
            raise ValueError("지금은 휴식·휴무 시간이라 알람이 바로 나지 않습니다 — 근무 시간에 다시 누르거나 [시연 ▾]에서 넘기세요")
        sev = "WARN" if kind in ("warn", "air") else "STOP"
        pool = [a for a in self.M["alarm_master"] if a["severity"] == sev] if kind != "air" else             [a for a in self.M["alarm_master"] if a["alarm_code"] == "120"]
        up = lambda e: self.sim.mach[e].cur_state[0] != "DOWN"   # 이미 고장 난 설비는 피한다 (정비가 그 고장 뒤로 밀림)
        pool = [x for x in pool if any(up(e) for e in self.PREVIEW_EQ[x["process_code"]])] or pool
        a = pool[int(self.rp.integers(len(pool)))]
        eqs = [e for e in self.PREVIEW_EQ[a["process_code"]] if up(e)] or self.PREVIEW_EQ[a["process_code"]]
        eq = eqs[int(self.rp.integers(len(eqs)))]
        self._plan_alarm(PlannedAlarm(self.m, eq, a["alarm_code"], sev, True))
        if kind == "maint":
            self.fix_plan.append({"eq": eq, "at": self.m + 3, "dur": int(self.rp.integers(20, 41)), "until": self.m + 60})
        self._op("preview", kind=kind, alarm_code=a["alarm_code"], equipment_id=eq)
        return {"kind": kind, "alarm_code": a["alarm_code"], "name_ko": a["name_ko"], "equipment_id": eq, "at": fmt_dt(self.now())}

    def _fix_to_maint(self, m: int):
        """미리보기 '정비': 고장(DOWN)을 끝내고(알람 해제) 같은 분에 수리 정비(MAINT)를 시작한다."""
        for f in list(self.fix_plan):
            mc = self.sim.mach[f["eq"]]
            if m < f["at"]:
                continue
            if mc.holds and mc.holds[0].kind == "DOWN":
                h = mc.holds[0]
                h.end = m                                        # 고장 끝(알람 해제) → 같은 분에 수리 정비, 사유는 그 고장 그대로
                mc.holds.insert(1, Hold("MAINT", h.reason, end=m + f["dur"], wall=True))
                self.fix_plan.remove(f)
            elif m >= f["until"]:
                self.fix_plan.remove(f)                          # 알람이 끝내 안 났으면 버림

    def _plan_alarm(self, p: PlannedAlarm):
        q = self.sim.alarm_plan[p.equipment_id]
        i = 0
        while i < len(q) and q[i].m <= p.m:
            i += 1
        q.insert(i, p)

    def _end_event(self, how: str):
        ev = self.active
        ev["end_m"] = self.m
        self.active = None
        self._emit("event_ended", at=fmt_dt(self.sim.cal.to_dt(self.m)), scenario_code=ev["code"],
                   equipment_id=ev["equipment_id"], how=how)

    def _watch_event(self, m: int):
        ev, sim = self.active, self.sim
        if ev is None:
            return
        mc = sim.mach[ev["equipment_id"]]
        if ev["code"] == "S1":
            crash = [a for a in sim.alarm_events if a["id"] in ev["alarm_ids"] and a["alarm_code"] == "992"]
            if crash and crash[0]["cleared_m"] is not None and mc.cur_state[0] != "DOWN":
                sim.wait_confirm.discard(ev["equipment_id"])
                self._end_event("작업기록서 확정 → 복귀")
        elif ev["code"] == "S3":
            n = sum(1 for c in sim.tool_changes if c["tool_id"] == ev["tool_id"])
            if n > ev["changes_before"]:
                t = next(t for t in mc.tools.values() if t.tool_id == ev["tool_id"])
                t.per = ev["base_per"]
                last = [c for c in sim.tool_changes if c["tool_id"] == ev["tool_id"]][-1]
                self._end_event("한도 → 362 → 시뮬레이터 교체" if last["change_reason"] == "ALARM_362" else "공구 교체 기록")
        elif ev["code"] == "S4":
            a = [x for x in sim.alarm_events if x["id"] in ev["alarm_ids"]]
            if a and a[0]["cleared_m"] is not None:
                self._end_event("자동 복귀")
        elif ev["code"] == "S6":
            done = [r for r in sim.maint_done if r["window"] is ev["window"]]
            if done and done[0]["end_m"] <= m:
                self._pm_records(done[0])
                self._end_event("정비 끝 → 자동 복귀")
        elif ev["code"] == "S7":
            if m >= ev["end_plan_m"]:
                self._end_event("작업자가 다시 돌림")

    def _pm_records(self, rec: dict):
        """S6 정비 실시 기록 (DRAFT — MNT가 화면에서 확인)과 소모품 사용 (설계서 7장 S6, DOC-04 4.1·4.4)."""
        cal, w = self.sim.cal, rec["window"]
        done_at = cal.to_dt(rec["end_m"])
        sh = cal.shift_or_near(rec["end_m"])
        mnt = "U07" if sh.shift_type == "DAY" else "U09"
        overdue = {k: date.fromisoformat(v) for k, v in self.cfg["sim"]["pm_plan"]["overdue_due"].items()}
        items = {t["pm_task_id"]: t for t in self.M["pm_task"]}
        base = self.past["pm_record"]
        first = None
        for tid in w.pm_task_ids:
            t = items[tid]
            rid = base + len(self.pm_rows) + 1
            first = first or rid
            self.pm_rows.append({"pm_record_id": rid, "pm_task_id": tid, "due_date": overdue.get(tid, w.due),
                                 "done_at": done_at, "done_by": mnt, "recorded_by": mnt,
                                 "result": "REFILLED" if t["default_item_no"] else "NORMAL", "measured_value": None,
                                 "measured_unit": None, "memo": "10/1 시연 S6 정비" + (" — 기한 넘긴 항목 보충 (S2 해결)"
                                                                                  if tid in overdue else ""),
                                 "status": "DRAFT", "current_version": 0})
            q = {"CS-WLUB": self.rr.uniform(0.5, 0.9), "CS-SLUB": self.rr.uniform(0.2, 0.3)}.get(t["default_item_no"])
            if q is not None:
                self.pm_inv.append({"item_no": t["default_item_no"], "txn_type": "USE", "qty_change": -round(float(q), 2),
                                    "txn_at": done_at, "txn_by": mnt, "source_kind": "PM_RECORD", "pm_record_id": rid})
        rec["pm_record_id"] = first

    def _plan_routine_pm(self) -> list[tuple[int, str, date]]:
        """10/1이 기한인 매일·매주 점검을 9월처럼 그날 오전에 한다 (gen/pm.py와 같은 시간대: 작업자 08:05~09:30, 보전 08:30~11:30).
        안 하면 10/2 00:00에 "기한 넘김"이 된다. 매월 항목은 S6 정비, 기한 넘긴 2개(S2)는 시연 장면이라 뺀다."""
        last: dict[str, str] = {}
        with io.open(ROOT / self.cfg["run"]["out_dir"] / "pm_record.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["done_at"]:
                    last[r["pm_task_id"]] = max(last.get(r["pm_task_id"], ""), r["done_at"][:10])
        cal = self.sim.cal
        day = cal.to_dt(self.N).date()
        overdue = self.cfg["sim"]["pm_plan"]["overdue_due"]
        plan = []
        for t in self.M["pm_task"]:
            tid = t["pm_task_id"]
            if t["on_calendar"] != "true" or t["cycle_code"] not in ("DAILY", "WEEKLY") or tid in overdue or tid not in last:
                continue
            due = next_due(date.fromisoformat(last[tid]), t["cycle_code"])
            if due > day:
                continue
            hm = ("08:05", "09:30") if t["default_role"] == "OPR" else ("08:30", "11:30")
            ms = [m for m in range(cal.to_min(at(day, hm[0])), cal.to_min(at(day, hm[1]))) if cal.is_work(m)]
            plan.append((int(self.pm_rng.choice(ms)), tid, due))
        return sorted(plan)

    def _routine_pm(self, m: int, tid: str, due: date):
        t = next(x for x in self.M["pm_task"] if x["pm_task_id"] == tid)
        cal = self.sim.cal
        sh = cal.shift_or_near(m)
        mnt = MNT_BY_SHIFT[sh.shift_type][0]
        by = OPR_BY_PROC[sh.shift_type][PROC[t["equipment_id"]]] if t["default_role"] == "OPR" else mnt
        mv = mu = None
        if tid.endswith("2.2-04"):                               # 절삭유 농도 (gen/pm.py와 같음)
            mv, mu = round(float(self.pm_rng.uniform(6.6, 8.2)), 1), "%"
        rid = self.past["pm_record"] + len(self.pm_rows) + 1
        done_at = cal.to_dt(m)
        self.pm_rows.append({"pm_record_id": rid, "pm_task_id": tid, "due_date": due, "done_at": done_at, "done_by": by,
                             "recorded_by": mnt, "result": "REFILLED" if t["default_item_no"] else "NORMAL",
                             "measured_value": mv, "measured_unit": mu, "memo": None, "status": "CONFIRMED", "current_version": 0})
        if t["default_item_no"] == "CS-COOL":                    # 절삭유 보충 (gen/stage4.py와 같음, DOC-04 4.2)
            q = 208 * 0.10 * 0.03 * 6 if tid.endswith("2.2-03") else float(self.pm_rng.uniform(0.2, 0.5))
            self.pm_inv.append({"item_no": "CS-COOL", "txn_type": "USE", "qty_change": -round(q, 2), "txn_at": done_at,
                                "txn_by": mnt, "source_kind": "PM_RECORD", "pm_record_id": rid})

    # ---------- 화면 조작 받기 ----------
    def suspect_lot(self) -> str | None:
        """S1 충돌(992) 때 가공 중이던 로트 (비서가 보류를 제안하는 의심 로트)."""
        for ev in reversed(self.event_log):
            if ev["code"] == "S1":
                a = [x for x in self.sim.alarm_events if x["id"] in ev["alarm_ids"] and x["alarm_code"] == "992"]
                if a:
                    return a[0]["lot_no"]
        return None

    def _lot(self, lot_no: str):
        for l in self.sim.lots:
            if l.lot_no == lot_no:
                return l
        raise ValueError(f"로트 없음: {lot_no}")

    def hold_lot(self, lot_no: str, by: str = "U10", reason: str | None = None, next_lots: int | None = None):
        """반장이 로트를 보류 (FR-PRD-05). 그 로트와 다음 1~2개 로트를 검사 강화로 (DOC-06 §3.3)."""
        lot = self._lot(lot_no)
        if lot.on_hold:
            raise ValueError("이미 보류된 로트")
        if lot.judged_m is not None:
            raise ValueError("이미 판정된 로트 (출하했으면 보류할 수 없음)")
        crash = self.suspect_lot() == lot_no
        alarm_id = None
        if crash:
            ev = [e for e in self.event_log if e["code"] == "S1"][-1]
            alarm_id = [x for x in self.sim.alarm_events if x["id"] in ev["alarm_ids"] and x["alarm_code"] == "992"][0]["id"]
        trigger = "AI_SUSPECT" if crash else ("INSPECTION_FAIL" if lot.review_m is not None else "SUPERVISOR")
        self.sim.pending_holds.append({
            "at": self.m, "lot": lot, "alarm_id": alarm_id, "tool_id": None, "trigger": trigger, "held_by": by,
            "next": next_lots if next_lots is not None else 2,
            "reason": reason or ("충돌 의심(108 → 994 → 992) 때 가공 중이던 로트 — 비서 의심 로트 제안" if crash
                                 else "반장 보류")})
        self._op("hold_lot", lot_no=lot_no, by=by, trigger=trigger)

    def release_lot(self, lot_no: str, by: str = "U10", approver: str = "U12"):
        """전수 검사로 판정이 끝난 보류 로트를 반장이 해제. 폐기가 있으면 관리자 승인을 같이 남김 (DOC-06 §4.1)."""
        lot = self._lot(lot_no)
        if not lot.on_hold:
            raise ValueError("보류 중인 로트가 아님")
        if lot.judged_m is None:
            raise ValueError("아직 판정 전 (전수 검사 중)")
        h = lot.hold
        if lot.scrap:
            h["scrap_qty"], h["scrap_by"], h["scrap_approved_by"], h["scrap_approved_m"] = lot.scrap, by, approver, self.m
        self.sim._release(lot, self.m)
        h["released_by"] = by
        self._op("release_lot", lot_no=lot_no, by=by)

    def record_tool_change(self, tool_id: str, by: str | None = None):
        """작업자가 화면에서 공구 교체를 기록 → 그 공구 사용량 0, SETUP 3~8분 (API-TOOL-02)."""
        for mc in self.sim.mach.values():
            for t in mc.tools.values():
                if t.tool_id == tool_id:
                    self.sim._tool_change(self.m, mc, t, "LIFE_90" if t.cum / t.limit >= 0.9 else "OTHER")
                    if by:
                        self.sim.tool_changes[-1]["changed_by"] = by
                    self.tool_pct[tool_id] = 0.0
                    self._op("tool_change", tool_id=tool_id, by=by)
                    return
        raise ValueError(f"공구 없음: {tool_id}")

    def confirm_work_record(self, equipment_id: str = "VF2-01", by: str = "U07"):
        """작업기록서 [확정](수리 완료) → 고장 설비 복귀 (설계서 7장 S1, API-MNT-11)."""
        mc = self.sim.mach[equipment_id]
        for h in mc.holds:
            if h.kind == "DOWN" and h.wall and h.end >= 10 ** 9:
                h.end = self.m
                self._op("confirm_work_record", equipment_id=equipment_id, by=by)
                return
        raise ValueError("작업기록서 확정을 기다리는 고장이 없음")

    # ---------- 1분 ----------
    def _override(self, eq: str, m: int) -> dict:
        out = {}
        for e in self.effects:
            if e["eq"] == eq and e["m0"] <= m <= e["m1"]:
                f = (m - e["m0"]) / max(1, e["m1"] - e["m0"])
                out[e["sensor"]] = e["v0"] + (e["v1"] - e["v0"]) * f
        return out

    def _minute(self) -> list[dict]:
        sim, m = self.sim, self.m
        n0 = len(self.events)
        if self.fix_plan:
            self._fix_to_maint(m)
        sim.step(m)
        cal = sim.cal
        t = fmt_dt(cal.to_dt(m))
        for eq, mc in sim.mach.items():                          # 설비 상태
            st = mc.cur_state
            if st != self.prev_state[eq]:
                self._emit("state_changed", at=t, equipment_id=eq, state=st[0], reason=st[1],
                           warn=bool(st[2]), alarm_event_id=st[3], mtconnect_execution=MTC.get(st[0]))
                self.prev_state[eq] = st
        for e in sim.alarm_events[self.prev_alarm:]:            # 알람 (사건 버튼·교체 안 한 공구 한도에서만)
            if self.active and e["equipment_id"] == self.active["equipment_id"]:
                e["scenario"] = self.active["code"]
                self.active["alarm_ids"].append(e["id"])
            self._emit("alarm", at=t, alarm_event_id=e["id"], equipment_id=e["equipment_id"],
                       alarm_code=e["alarm_code"], severity=e["severity"], scenario_code=e.get("scenario"))
            if e["severity"] in ("WARN", "STOP") and self.speed > self.rt["auto_slowdown_to"]:
                self.speed = self.rt["auto_slowdown_to"]          # 자동 감속 (설계서 4장)
                self._emit("sim_clock", reason="auto_slowdown", speed=self.speed)
        self.prev_alarm = len(sim.alarm_events)
        for mc in sim.mach.values():                            # 공구 사용률 90% 넘음 → 교체 알림 재료 (DOC-07 §9)
            for tl in mc.tools.values():
                p = tl.cum / tl.limit
                if self.tool_pct.get(tl.tool_id, 0) < 0.9 <= p:
                    self._emit("tool_life", at=t, tool_id=tl.tool_id, usage_pct=round(p * 100, 1))
                self.tool_pct[tl.tool_id] = p
        wip = {k: int(v[m]) for k, v in sim.wip_min.items()}     # 재공
        wip["SOAK"] = int(sim.soak_min[m])
        if wip != self.prev_wip:
            self._emit("wip_changed", at=t, wip=wip)
            self.prev_wip = wip
        done = [p for p in sim.finished[-12:] if p.start.get("done") == m]   # OP-50 완료 (MTConnect PartCount)
        if done:
            self.done_today += len(done)
            self._emit("part_count", at=t, equipment_id="CMM-01", added=len(done), count=self.done_today)
        for ev in sim.measure_log[self.prev_meas:]:             # 측정 → 결과 파일을 공유 폴더 흉내 폴더에
            self._measured(ev)
        self.prev_meas = len(sim.measure_log)
        st = {eq: mc.cur_state for eq, mc in sim.mach.items()}  # 병목 (과거 기록과 같은 판단기)
        slow = {eq: sim.mach[eq].slow for eq in ("VF2-01", "VF2-02")}
        r = self.judge.observe(m, st, slow, S4.live_enhanced(sim))
        if r:
            self.bn_rows.append(r)
            self._emit("bottleneck_changed", at=t, process_code=r["new"], cause_code=r["cause"],
                       prev_process_code=r["prev"], alarm_event_id=r["alarm"])
        for eq, sl in self.sensors.items():                      # 센서 1분 평균 (사건 때 모양을 덮어씀)
            v = sl.step(st[eq][0] == "RUN", slow[eq], self._override(eq, m))
            self.sensor_min[eq][m] = v
            self._emit("sensor", at=t, equipment_id=eq, values=v)
        sh = cal.shift_at(m)
        if sh is not None and cal.to_min(sh.end) == m + 1:       # 교대 끝 (교대 보고서 AI비서 초안은 서버)
            self._emit("shift_end", at=fmt_dt(sh.end), shift_id=sh.shift_id)
        while self.pm_plan and self.pm_plan[0][0] <= m:       # 일상 점검 실시 기록
            self._routine_pm(*self.pm_plan.pop(0))
        self._watch_event(m)
        self.m += 1
        return self.events[n0:]

    def _measured(self, ev: dict):
        rid0 = self.past["inspection_result"] + len(self.insp_rows) + 1
        iid = self.past["cmm_import"] + len(self.cmm_rows) + 1
        rows, imp, frid = self.measurer.measure(ev, rid0, iid)
        self.insp_rows += rows
        self.cmm_rows.append(imp)
        if frid is not None and ev["part"].pid not in self.fail_rid:
            self.fail_rid[ev["part"].pid] = frid
        frows = self.measurer.file_rows(rows, imp)
        tmp = self.drop_dir / (imp["file_name"] + ".tmp")        # 다 쓴 뒤 이름 바꿈 (다 쓴 파일만 읽게, CMM 조사 5.1)
        with io.open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\r\n")
            w.writerow(Q.FILE_COLS)
            for x in frows:
                w.writerow([_cell(x[c]) for c in Q.FILE_COLS])
        tmp.replace(self.drop_dir / imp["file_name"])
        self._emit("cmm_file", at=fmt_dt(imp["measure_end_at"]), file_name=imp["file_name"], lot_no=imp["lot_no"],
                   part_seq=imp["part_seq"], insp_kind=imp["insp_kind"])

    def _emit(self, kind: str, **kw) -> list[dict]:
        ev = {"type": kind, **kw}
        if kind == "sim_clock":
            ev.update(self.clock())
        self.events.append(ev)
        return [ev]

    def _op(self, op: str, **kw):
        self.ops.append({"op": op, "sim_at": fmt_dt(self.now()), **kw})
        self._emit("sim_clock", reason=op)

    # ---------- 대본 (리허설) ----------
    def _do(self, s: dict):
        op = s["op"]
        if op == "speed":
            self.set_speed(int(s["value"]))
        elif op == "pause":
            self.pause()
        elif op == "resume":
            self.resume()
        elif op == "skip":
            self.skip(s.get("to", "TODAY_17:00"))
        elif op == "reset":
            self.reset()
        elif op == "inject":
            self.inject(s["code"])
        elif op == "hold_suspect":
            lot = self.suspect_lot()
            if lot is None:
                raise ValueError("의심 로트 없음 (S1 992 전)")
            self.hold_lot(lot, by=s.get("by", "U10"))
        elif op == "hold_lot":
            self.hold_lot(s["lot_no"], by=s.get("by", "U10"))
        elif op == "release_held":
            held = [l for l in self.sim.lots if l.on_hold]
            if not held:
                raise ValueError("보류 중인 로트 없음")
            self.release_lot(held[0].lot_no, by=s.get("by", "U10"))
        elif op == "tool_change":
            self.record_tool_change(s["tool_id"], by=s.get("by"))
        elif op == "confirm_work_record":
            self.confirm_work_record(s.get("equipment_id", "VF2-01"), by=s.get("by", "U07"))
        else:
            raise ValueError(f"모르는 조작: {op}")

    def play(self, script: dict) -> None:
        """대본: [{"wait_real_sec": 실제 초, "op": ..., "retry_real_sec": 실제 초}] 를 기다리지 않고 돌린다.
        retry_real_sec가 있으면 조작이 안 될 때(설비 가공 중 아님 등) 1초씩 흘려 보내며 다시 시도한다."""
        for s in script["steps"]:
            w = float(s.get("wait_real_sec", 0))
            while w > 0:                                         # 1초씩 (실제 서버의 갱신 주기와 비슷하게)
                self.tick(min(1.0, w))
                w -= 1.0
            if s["op"] == "end":
                break
            left = float(s.get("retry_real_sec", 0))
            while True:
                try:
                    self._do(s)
                    break
                except ValueError as e:
                    if left <= 0:
                        self.ops.append({"op": "failed", "sim_at": fmt_dt(self.now()), "step": s["op"], "why": str(e)})
                        break
                    self.tick(1.0)
                    left -= 1.0

    # ---------- 기록 내보내기 ----------
    def export(self, out_dir: Path | None = None) -> dict:
        """10/1 08:00 ~ 지금 기록을 ERD 칸 모양 CSV로 (번호는 과거 기록 뒤에 이어 붙임). DB에는 추가·덮어쓰기."""
        cfg, sim, N, now_m, past = self.cfg, self.sim, self.N, self.m, self.past
        out = Out(cfg)
        out.dir = Path(out_dir) if out_dir else ROOT / self.rt["out_dir"]
        out.dir.mkdir(exist_ok=True)
        out.clear()
        cal = sim.cal
        maint_pm = {id(r): r.get("pm_record_id") for r in sim.maint_done}
        # 설비 상태: 10/1 08:00에 걸친 구간은 08:00부터. 아직 안 끝난 구간은 end_at 비움
        rows = []
        for eq, mc in sim.mach.items():
            runs = [r for r in mc.state_runs if r[0] < now_m]
            for k, (a, st) in enumerate(runs):
                b = runs[k + 1][0] if k + 1 < len(runs) else None
                if b is not None and b <= N:
                    continue
                a = max(a, N)
                state, reason, warn, aid, mref = st
                pm_id = maint_pm.get(id(sim.maint_done[mref])) if mref is not None else None
                rows.append({"equipment_id": eq, "state_code": state, "mtconnect_execution": R.MTC.get(state),
                             "start_at": cal.to_dt(a), "end_at": cal.to_dt(b) if b is not None else None,
                             "warn_marker": bool(warn), "alarm_event_id": aid, "pm_record_id": pm_id,
                             "reason_suggested_code": reason if state != "RUN" else None,
                             "reason_status": "SUGGESTED" if state != "RUN" else None})
        rows.sort(key=lambda r: (r["start_at"], r["equipment_id"]))
        for i, r in enumerate(rows, past["equipment_state_log"] + 1):
            r["state_log_id"] = i
        out.write("equipment_state_log", R.COLS["equipment_state_log"], rows)
        # 알람: 사건 버튼으로 생긴 것은 is_injected·scenario_code
        new_al = [e for e in sim.alarm_events if e["id"] > past["alarm_event"]]
        arows = [r for r in R.alarm_rows(sim) if r["alarm_event_id"] > past["alarm_event"]]
        for r, e in zip(arows, new_al):
            r["is_injected"] = e.get("scenario") is not None
            r["scenario_code"] = e.get("scenario")
        out.write("alarm_event", R.COLS["alarm_event"], arows)
        # 재공: 5분 (알람·병목 앞뒤 30분 1분)
        centers = [e["occurred_m"] for e in new_al if e["severity"] in ("WARN", "STOP")] + [r["m"] for r in self.bn_rows]
        win = cfg["record_interval"]["around_event_window_min"]
        wrows = []
        for m in range(N, now_m):
            one = any(abs(m - c) <= win for c in centers)
            if not (m % cfg["record_interval"]["wip_min"] == 0 or one):
                continue
            for code, arr in sim.wip_min.items():
                wrows.append({"buffer_code": code, "logged_at": cal.to_dt(m), "wip_qty": int(arr[m]),
                              "soak_shelf_qty": int(sim.soak_min[m]) if code == "WIP-40-50" else None,
                              "interval_type": "MIN1" if one else "MIN5"})
        out.write("wip_log", R.COLS["wip_log"], wrows)
        # 공정 실적: 10/1 교대 것만 (번호 이어 붙임)
        reps = sorted([(k, v) for k, v in sim.reports.items() if v["start_m"] >= N or k[3] >= "2026-10-01"],
                      key=lambda kv: (kv[1]["start_m"], kv[1]["equipment_id"], kv[1]["lot_no"]))
        rep_ids, orows = {}, []
        for i, (key, r) in enumerate(reps, past["operation_report"] + 1):
            rep_ids[key] = i
            orows.append({"op_report_id": i, "lot_no": r["lot_no"], "process_code": r["process_code"],
                          "equipment_id": r["equipment_id"], "worker_user_id": r["worker_user_id"],
                          "shift_id": r["shift_id"], "start_at": cal.to_dt(r["start_m"]),
                          "end_at": cal.to_dt(r["end_m"] + 1), "pq": r["pq"], "gq": r["gq"], "rq": r["rq"], "sq": r["sq"]})
        out.write("operation_report", R.COLS["operation_report"], orows)
        usage = [{"tool_id": tid, "op_report_id": rep_ids[key], "parts_qty": u["parts"], "usage_qty": round(u["usage"], 3),
                  "cum_after": round(u["cum_after"], 3), "recorded_at": cal.to_dt(u["m"])}
                 for (tid, key), u in sim.tool_usage.items() if key in rep_ids]
        out.write("tool_usage", R.COLS["tool_usage"], usage, sort_key=lambda x: (x["op_report_id"], x["tool_id"]))
        tc = sorted(sim.tool_changes, key=lambda c: (c["changed_m"], c["tool_id"]))
        crows = [{"tool_change_id": i, "tool_id": c["tool_id"], "changed_at": cal.to_dt(c["changed_m"]),
                  "changed_by": c["changed_by"], "cum_before": round(c["cum_before"], 3), "change_reason": c["change_reason"],
                  "related_alarm_event_id": c["related_alarm_event_id"]}
                 for i, c in enumerate(tc, 1) if c["changed_m"] >= N]
        out.write("tool_change", R.COLS["tool_change"], crows)
        # 작업지시·로트·검사 방식: 10/1 08:00에 열려 있던 것 + 새로 생긴 것 (DB에는 덮어쓰기)
        orders = [o for o in R.order_rows(sim, cfg)
                  if o["created_at"] >= cal.to_dt(N) or o["completed_at"] is None or o["completed_at"] >= cal.to_dt(N)]
        out.write("production_order", R.COLS["production_order"], orders)
        lots = [l for l in S4.lot_rows(sim) if l["status"] not in ("PASSED", "RELEASED")
                or (l["judged_at"] is not None and l["judged_at"] >= cal.to_dt(N))]
        out.write("production_lot", R.COLS["production_lot"], lots)
        keep = {l["lot_no"] for l in lots}
        out.write("inspection_plan", S4.COLS["inspection_plan"], [r for r in S4.inspection_rows(sim) if r["lot_no"] in keep])
        out.write("lot_hold", S4.COLS["lot_hold"], [r for r in S4.hold_rows(sim) if r["hold_id"] > past["lot_hold"]
                                                     or r["result"] == "IN_PROGRESS"])
        # 측정값·결과 파일 가져오기·불량
        out.write("inspection_result", Q.COLS["inspection_result"], self.insp_rows)
        out.write("cmm_import", Q.COLS["cmm_import"], self.cmm_rows)
        drows = [r for r in R.defect_rows(sim, self.fail_rid) if r["found_at"] >= cal.to_dt(N)]
        for i, r in enumerate(drows, past["defect_record"] + 1):
            r["defect_record_id"] = i
        out.write("defect_record", R.COLS["defect_record"], drows)
        # 예방 정비 기록 (S6)·재고 거래
        out.write("pm_record", ["pm_record_id", "pm_task_id", "due_date", "done_at", "done_by", "recorded_by", "result",
                                "measured_value", "measured_unit", "memo", "status", "current_version"], self.pm_rows)
        out.write("inventory_txn", S4.COLS["inventory_txn"], self._inventory(rep_ids))
        # 병목 기록
        out.write("bottleneck_log", S4.COLS["bottleneck_log"],
                  S4.bottleneck_rows(sim, self.bn_rows, now_m, id_start=past["bottleneck_log"] + 1))
        # 센서: 1분 평균, 주의·정지 등급 알람 앞뒤 30분은 5초 (A안)
        out.write_tuples("sensor_sample", S4.COLS["sensor_sample"], self._sensor_rows(new_al, now_m))
        # 사건·조작 기록
        with io.open(out.dir / "events.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
        with io.open(out.dir / "run_log.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for o in self.ops:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        man = {"mode": "realtime", "seed": cfg["run"]["seed"], "start_at": fmt_dt(cal.to_dt(N)),
               "now_at": fmt_dt(self.now()), "speed": self.speed, "paused": self.paused,
               "ops": len(self.ops), "events": len(self.events),
               "scenario_events": [{"code": e["code"], "start_at": fmt_dt(cal.to_dt(e["start_m"])),
                                    "end_at": fmt_dt(cal.to_dt(e["end_m"])) if e.get("end_m") is not None else None}
                                   for e in self.event_log],
               "cmm_drop_files": len(list(self.drop_dir.glob("*.csv"))),
               "rows": dict(sorted(out.counts.items())),
               "id_after_past": {k: past[k] for k in ("equipment_state_log", "operation_report", "bottleneck_log",
                                                      "alarm_event", "tool_change", "inspection_result", "cmm_import",
                                                      "defect_record", "pm_record", "inventory_txn", "lot_hold")}}
        with io.open(out.dir / "manifest.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return man

    def _inventory(self, rep_ids) -> list[dict]:
        """10/1 재고 거래: 공구 교체(충돌로 부러진 공구 빼고), 정비 소모품(S6), 원자재 로트 투입, 완제품 합격 입고."""
        sim, cal, N = self.sim, self.sim.cal, self.N
        tt = {x["item_no"]: int(x["deduct_qty_per_change"]) for x in self.M["tool_type"]}
        titem = {x["tool_id"]: x["item_no"] for x in self.M["tool"]}
        tx = []
        tc = sorted(sim.tool_changes, key=lambda c: (c["changed_m"], c["tool_id"]))
        for i, c in enumerate(tc, 1):
            if c["changed_m"] >= N and c["change_reason"] != "BROKEN":
                it = titem[c["tool_id"]]
                tx.append({"item_no": it, "txn_type": "USE", "qty_change": -tt[it], "txn_at": cal.to_dt(c["changed_m"]),
                           "txn_by": c["changed_by"], "source_kind": "TOOL_CHANGE", "tool_change_id": i})
        tx += list(self.pm_inv)
        for lot in sim.lots:
            first = min(p.start["OP-10"] for p in lot.parts)
            if first >= N:
                tx.append({"item_no": "RM-6061", "txn_type": "USE", "qty_change": -lot.input_qty,
                           "txn_at": cal.to_dt(first), "txn_by": None, "source_kind": "LOT_INPUT", "lot_no": lot.lot_no})
            pm = S4.passed_m(lot)
            if pm is not None and pm >= N and lot.fg_qty > 0:
                tx.append({"item_no": "FG-BRK-A100", "txn_type": "FG_IN", "qty_change": lot.fg_qty, "txn_at": cal.to_dt(pm),
                           "txn_by": None, "source_kind": "LOT_PASS", "fg_lot_no": lot.lot_no})
        tx.sort(key=lambda t: (t["txn_at"], t["item_no"], t["source_kind"]))
        for i, t in enumerate(tx, self.past["inventory_txn"] + 1):
            t["txn_id"] = i
        return tx

    def _sensor_rows(self, alarms: list[dict], now_m: int) -> list[tuple]:
        cal = self.sim.cal
        win = self.cfg["record_interval"]["around_event_window_min"]
        step, code = S4.sec_step(self.cfg)
        per = 60 // step
        rows = []
        r = self.rng.stream("rt-sensor-sec")
        for eq, mins in self.sensor_min.items():
            sec = set()
            for e in alarms:
                if e["equipment_id"] == eq and e["severity"] in ("WARN", "STOP"):
                    sec |= set(range(max(self.N, e["occurred_m"] - win), min(now_m, e["occurred_m"] + win)))
            for m in sorted(mins):
                v = mins[m]
                if m not in sec:
                    rows += [(eq, k, cal.to_dt(m), v[k], "MIN1_AVG") for k in SENSORS]
                    continue
                nxt = mins.get(m + 1, v)
                for k in SENSORS:
                    seq = np.linspace(v[k], nxt[k], per, endpoint=False) + r.normal(0, NOISE[k], per)
                    if k == "AirPressure" and min(v[k], nxt[k]) >= 100:
                        seq = np.clip(seq, 100, 110)
                    if k in ("SpindleLoadPct", "Xload", "Yload", "Zload"):
                        seq = np.clip(seq, 0, None)
                    base = cal.to_dt(m)
                    rows += [(eq, k, base + timedelta(seconds=s * step), round(float(seq[s]), 1), code) for s in range(per)]
        return rows


def load_script(name: str) -> dict:
    p = ROOT / load_config()["realtime"]["scenarios_dir"] / name
    return json.load(io.open(p, encoding="utf-8"))
