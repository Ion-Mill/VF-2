"""시간 흐름 전에 정하는 계획: 원자재 입고, 알람 계획, 예방 정비 계획 (설계서 5.4·5.8·5.12).

계획은 '언제 무엇이 일어날지'만 정한다. 실제 기록은 시간 흐름(flow.py)이 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .calendar import Calendar
from .common import KST, WEEKDAY, at


# ---------- 원자재 로트 (설계서 5.4) ----------

@dataclass
class MaterialLot:
    material_lot_no: str
    received_date: date
    received_qty: int
    remaining: int
    supplier_cert_no: str
    heat_batch_no: str


def plan_material(cfg: dict, cal: Calendar, rng) -> list[MaterialLot]:
    """9/1 시작 재고 = 안전 재고 200 + 1주 사용량 1,080 = 1,280개분 (기준정보_목록 6장 결정 3).
    8월 마지막 주에 받은 로트 4개로 둔다. 가장 오래된 로트는 받은 수량을 200개분으로 둔다
    (8월 투입 기록이 없으므로, 재고 거래의 9/1 시작 재고 = 받은 수량 합 = 1,280이 되게)."""
    m = cfg["material"]
    qty = m["qty_per_receipt"]
    lots: list[MaterialLot] = []
    r = rng.stream("material")
    start_rows = [(date(2026, 8, 21), 200), (date(2026, 8, 24), qty), (date(2026, 8, 26), qty), (date(2026, 8, 28), qty)]
    for i, (d, rem) in enumerate(start_rows, 10):
        lots.append(MaterialLot(f"MAT-2608-{i:02d}", d, rem, rem, f"SC-{d:%y%m%d}-{int(r.integers(100, 999))}",
                                f"H{d:%y%m%d}{chr(65 + int(r.integers(0, 6)))}"))
    days = {WEEKDAY[w] for w in m["receipt_weekdays"]}
    k = 1
    for d in cal.days:
        if d.weekday() in days and d in set(cal.workdays):
            lots.append(MaterialLot(f"MAT-2609-{k:02d}", d, qty, qty, f"SC-{d:%y%m%d}-{int(r.integers(100, 999))}",
                                    f"H{d:%y%m%d}{chr(65 + int(r.integers(0, 6)))}"))
            k += 1
    return lots


# ---------- 알람 계획 (설계서 5.8, 15.2) ----------

@dataclass
class PlannedAlarm:
    m: int                       # 계획 분 (설비가 가공 중일 때 실제로 남)
    equipment_id: str
    code: str
    severity: str
    force: bool = False          # 가공 중이 아니어도 그 분에 남 (반복 알람 사례)
    chain: list[tuple[str, int]] = field(default_factory=list)   # 충돌 연쇄: [(코드, 앞 알람과 간격 분)]
    case: str = ""               # 반복 알람 사례 id
    prev_event: int | None = None   # 충돌 연쇄에서 앞 알람 이벤트 번호


def _work_minutes(cal: Calendar, d0: date, d1: date, shift_type: str | None = None) -> list[int]:
    out = []
    for sh in cal.shifts:
        if d0 <= sh.work_date <= d1 and (shift_type is None or sh.shift_type == shift_type):
            a, b = cal.to_min(sh.start), cal.to_min(sh.end)
            out += [m for m in range(a, b) if cal.is_work(m)]
    return out


def plan_alarms(cfg: dict, cal: Calendar, masters: dict, rng) -> list[PlannedAlarm]:
    a, sim = cfg["alarms"], cfg["sim"]
    r = rng.stream("alarms")
    sev = {x["alarm_code"]: x["severity"] for x in masters["alarm_master"]}
    plan: list[PlannedAlarm] = []
    day0, day1 = cal.days[0], cal.days[-1]
    W = 7 * 24 * 60

    def count_near(eq, code, m):
        return [p.m for p in plan if p.equipment_id == eq and p.code == code and abs(p.m - m) < W]

    def ok_cap(eq, code, m, cap=2):
        """같은 설비·같은 알람이 어느 7일 창에서도 cap번을 넘지 않게 (우연한 반복 막기)."""
        ms = sorted(count_near(eq, code, m) + [m])
        for i in range(len(ms)):
            if sum(1 for x in ms if ms[i] <= x < ms[i] + W) > cap:
                return False
        return True

    # 반복 알람 사례 ① VF2-02 2075 (9월 초 1번 + 마지막 주 3번, 세 번째 9/29 23:12)
    for c in a["repeat_cases"]:
        if c["id"] == "case1_S2":
            ew = _work_minutes(cal, date.fromisoformat(c["early_window"][0]), date.fromisoformat(c["early_window"][1]))
            plan.append(PlannedAlarm(int(r.choice(ew)), c["equipment"], c["alarm"], sev[c["alarm"]], True, case=c["id"]))
            third = cal.to_min(datetime.fromisoformat(c["last_week_three"]["third_at"]).replace(tzinfo=KST))
            lw = [m for m in _work_minutes(cal, date.fromisoformat(c["last_week_three"]["window_start"]), date(2026, 9, 28))
                  if third - W + 60 < m < third - 6 * 60]
            for m in sorted(r.choice(lw, 2, replace=False)):
                plan.append(PlannedAlarm(int(m), c["equipment"], c["alarm"], sev[c["alarm"]], True, case=c["id"]))
            plan.append(PlannedAlarm(third, c["equipment"], c["alarm"], sev[c["alarm"]], True, case=c["id"]))
        elif c["id"] == "case2_stage2":
            for d, st in c["occurrences"]:
                ms = _work_minutes(cal, date.fromisoformat(d), date.fromisoformat(d), st)
                ms = ms[60:-90]          # 교대 시작·끝 근처는 피함
                plan.append(PlannedAlarm(int(r.choice(ms)), c["equipment"], c["alarm"], sev[c["alarm"]], True, case=c["id"]))

    # 충돌 연쇄 1건 (108 → 994 → 992), 정지 등급 한 건으로 셈
    cc = sim["crash_chain"]
    cw = _work_minutes(cal, date.fromisoformat(cc["window"][0]), date.fromisoformat(cc["window"][1]), "DAY")
    g1, g2 = (int(r.integers(cc["gap_min"][0], cc["gap_min"][1] + 1)) for _ in range(2))
    plan.append(PlannedAlarm(int(r.choice(cw)), cc["equipment"], "108", "WARN",
                             chain=[("994", g1), ("992", g2)], case="crash"))

    vf = ["VF2-01", "VF2-02"]
    op30 = a["op30_per_vf2"]
    # 정지 등급: VF-2 1대당 30일 2~4건 (충돌 포함). 992·994는 충돌 연쇄에서만
    stop_codes = [c for c in op30["STOP"]["codes"] if c not in ("992", "994")]
    all_work = _work_minutes(cal, day0, day1)
    for eq in vf:
        n = int(r.integers(op30["STOP"]["per_30_days"][0], op30["STOP"]["per_30_days"][1] + 1))
        if eq == cc["equipment"]:
            n -= 1
        for code in r.choice(stop_codes, n, replace=False):
            plan.append(PlannedAlarm(int(r.choice(all_work)), eq, str(code), "STOP"))

    # 주의 등급: 하루 0~2건, 362는 공구 한도에서만, VF2-02의 108·2075는 사례에서만
    for eq in vf:
        codes = sim["warn_random_codes"][eq]
        for d in cal.workdays:
            ms = _work_minutes(cal, d, d)
            for _ in range(int(r.integers(op30["WARN"]["per_day"][0], op30["WARN"]["per_day"][1] + 1))):
                m = int(r.choice(ms))
                for code in r.permutation(codes):
                    if ok_cap(eq, str(code), m):
                        plan.append(PlannedAlarm(m, eq, str(code), "WARN"))
                        break

    # 조작 안내: 하루 3~8건 (같은 알람이 7일에 3번 넘게 나도 조작 안내는 반복 알람 규칙과 무관하게 흔함)
    for eq in vf:
        for d in cal.workdays:
            ms = _work_minutes(cal, d, d)
            for _ in range(int(r.integers(op30["GUIDE"]["per_day"][0], op30["GUIDE"]["per_day"][1] + 1))):
                plan.append(PlannedAlarm(int(r.choice(ms)), eq, str(r.choice(op30["GUIDE"]["codes"])), "GUIDE"))

    # 다른 공정 (공정당 2개, 30일 빈도)
    eq_of = {x["equipment_id"]: x["process_code"] for x in masters["equipment"]}
    proc_eq = {}
    for e, p in eq_of.items():
        proc_eq.setdefault(p, e)
    am = {x["alarm_code"]: x for x in masters["alarm_master"]}
    for code, spec in a["other_process_30_days"].items():
        eq = proc_eq[am[code]["process_code"]]
        n = int(r.integers(spec["count"][0], spec["count"][1] + 1))
        tries = 0
        while n > 0 and tries < 200:
            tries += 1
            m = int(r.choice(all_work))
            if ok_cap(eq, code, m):
                plan.append(PlannedAlarm(m, eq, code, sev[code]))
                n -= 1
    plan.sort(key=lambda p: (p.m, p.equipment_id, p.code))
    return plan


# ---------- 예방 정비 계획 (설계서 5.12, DOC-04) ----------

@dataclass
class MaintWindow:
    equipment_id: str
    start_m: int
    end_m: int
    kind: str                  # PM_MONTHLY / CAUSE_CHECK
    pm_task_ids: list[str]
    due: date | None = None    # 매월 묶음의 기한 (실시 기록 due_date)


def _day_minutes(cal: Calendar, d: date, hm0: str, hm1: str) -> list[int]:
    a, b = cal.to_min(at(d, hm0)), cal.to_min(at(d, hm1))
    return [m for m in range(a, b) if cal.is_work(m)]


def plan_maint(cfg: dict, cal: Calendar, masters: dict, rng) -> list[MaintWindow]:
    """MAINT 구간: VF2-01 매월 묶음 1회 + 반복 알람 사례 ② 원인 점검 1회 (원인 ② 병목)."""
    r = rng.stream("maint")
    pp = cfg["sim"]["pm_plan"]
    wins: list[MaintWindow] = []
    tasks = [t for t in masters["pm_task"] if t["on_calendar"] == "true"]
    # VF2-01 매월 묶음
    lo, hi = (date.fromisoformat(x) for x in pp["vf2_monthly_due"]["VF2-01"])
    cand = [d for d in cal.workdays if lo <= d <= hi]
    due = cand[int(r.integers(0, len(cand)))]
    late = int(r.integers(pp["monthly_late_days"][0], pp["monthly_late_days"][1] + 1))
    later = [d for d in cal.workdays if d >= due]
    done_day = later[min(late, len(later) - 1)]
    ms = _day_minutes(cal, done_day, *pp["maint_start_window"])
    s = int(r.choice(ms))
    dur = int(r.integers(pp["monthly_session_min"][0], pp["monthly_session_min"][1] + 1))
    ids = [t["pm_task_id"] for t in tasks if t["equipment_id"] == "VF2-01" and t["cycle_code"] == "MONTHLY"]
    wins.append(MaintWindow("VF2-01", s, s + dur, "PM_MONTHLY", ids, due))
    # VF2-02 매월 묶음: 9/1에 함 → 다음 기한 10/1 (시연 S6). 기한을 넘긴 2개(9/28·9/29)는 8월 말에 따로 했던 항목
    overdue = set(pp["overdue_due"])
    d1 = date.fromisoformat(pp["vf2_monthly_due"]["VF2-02"])
    d0 = date(d1.year, d1.month - 1, d1.day) if d1.month > 1 else date(d1.year - 1, 12, d1.day)
    ms = _day_minutes(cal, d0, *pp["maint_start_window"])
    s = int(r.choice(ms))
    dur = int(r.integers(pp["monthly_session_min"][0], pp["monthly_session_min"][1] + 1))
    ids = [t["pm_task_id"] for t in tasks if t["equipment_id"] == "VF2-02" and t["cycle_code"] == "MONTHLY"
           and t["pm_task_id"] not in overdue]
    wins.append(MaintWindow("VF2-02", s, s + dur, "PM_MONTHLY", ids, d0))
    # 반복 알람 사례 ② 원인 점검 (9/15 주간, 수리 시간 범위 30~180분 안)
    c2 = next(c for c in cfg["alarms"]["repeat_cases"] if c["id"] == "case2_stage2")
    d = date.fromisoformat(c2["cause_check"][0])
    ms = _day_minutes(cal, d, "09:00", "11:00")
    s = int(r.choice(ms))
    dur = int(r.integers(60, 121))
    wins.append(MaintWindow(c2["equipment"], s, s + dur, "CAUSE_CHECK", []))
    return wins
