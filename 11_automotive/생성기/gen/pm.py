"""예방 정비 실시 기록 pm_record (설계서 5.12, DOC-04 5장, ERD 5.D.8).

- 달력 항목(on_calendar)마다 9/1 전 '마지막 실시' 기록 1건을 둔다 (다음 기한을 계산할 시작 상태).
- 9월: 매일·매주는 90~95% 제때, 매월은 묶음 정비(MAINT 구간)로, 6개월·1년은 9월에 기한이 오지 않게 둠.
- 시연 S2: VF2-02 축 윤활유(2.3-01)·주축 윤활 탱크(2.3-07)는 9/28·9/29 기한을 넘긴 채 10/1을 맞는다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .common import at
from .flow import MNT_BY_SHIFT, OPR_BY_PROC

COLS = ["pm_record_id", "pm_task_id", "due_date", "done_at", "done_by", "recorded_by", "result", "measured_value",
        "measured_unit", "memo", "status", "current_version"]
PROC = {"SAW-01": "OP-10", "MIL-01": "OP-20", "VF2-01": "OP-30", "VF2-02": "OP-30", "WSH-01": "OP-40", "CMM-01": "OP-50"}


def _add_month(d: date, k: int = 1) -> date:
    y, m = d.year + (d.month - 1 + k) // 12, (d.month - 1 + k) % 12 + 1
    import calendar as _c
    return date(y, m, min(d.day, _c.monthrange(y, m)[1]))


def next_due(d: date, cycle: str) -> date | None:
    return {"DAILY": d + timedelta(days=1), "WEEKLY": d + timedelta(days=7), "MONTHLY": _add_month(d),
            "HALF_YEAR": _add_month(d, 6), "YEARLY": _add_month(d, 12)}.get(cycle)


def build_pm(cfg, cal, masters, rng, maint_done: list[dict]) -> tuple[list[dict], dict[int, int]]:
    r = rng.stream("pm")
    pp = cfg["sim"]["pm_plan"]
    lo, hi = cfg["maintenance"]["on_time_rate"]
    on_time = (lo + hi) / 2
    tasks = [t for t in masters["pm_task"] if t["on_calendar"] == "true" and t["cycle_code"] != "AS_REQUIRED"]
    workdays = list(cal.workdays)
    wset = set(workdays)
    day0, day1 = cal.days[0], cal.days[-1]
    overdue = {k: date.fromisoformat(v) for k, v in pp["overdue_due"].items()}
    month_sessions = {w["window"].equipment_id: w for w in maint_done if w["window"].kind == "PM_MONTHLY"}
    shift_of_day = {(s.work_date, s.shift_type): s for s in cal.shifts}
    day_h, night_h = (int(cfg["shifts"][k]["start"][:2]) for k in ("DAY", "NIGHT"))   # 주간 시작 시·야간 시작 시
    recs: list[dict] = []

    def who(t, d, st="DAY"):
        sh = shift_of_day.get((d, st)) or shift_of_day[(d, "DAY")]
        mnt = MNT_BY_SHIFT[sh.shift_type][0]
        done_by = OPR_BY_PROC[sh.shift_type][PROC[t["equipment_id"]]] if t["default_role"] == "OPR" else mnt
        return done_by, mnt

    def add(t, due, done_at, base=False):
        d = done_at.date()
        st = "NIGHT" if done_at.hour < day_h or done_at.hour >= night_h else "DAY"
        d_sh = d - timedelta(days=1) if done_at.hour < day_h else d
        done_by, mnt = who(t, d_sh, st) if d_sh in wset else (("U02" if t["default_role"] == "OPR" else "U07"), "U07")
        res = "REFILLED" if t["default_item_no"] else "NORMAL"
        mv = mu = None
        if t["pm_task_id"].endswith("2.2-04"):           # 절삭유 농도 (SC538 관리 범위 6.5~8.5% [실제])
            mv, mu = round(float(r.uniform(6.6, 8.2)), 1), "%"
        recs.append({"pm_task_id": t["pm_task_id"], "due_date": due, "done_at": done_at, "done_by": done_by,
                     "recorded_by": mnt, "result": res, "measured_value": mv, "measured_unit": mu,
                     "memo": "기록 시작 전 마지막 실시 (시작 상태)" if base else None, "status": "CONFIRMED",
                     "current_version": 0})

    def work_time(d, hm0, hm1):
        a, b = cal.to_min(at(d, hm0)), cal.to_min(at(d, hm1))
        ms = [m for m in range(a, b) if cal.is_work(m)]
        return cal.to_dt(int(r.choice(ms)))

    for t in tasks:
        cyc, tid, eq = t["cycle_code"], t["pm_task_id"], t["equipment_id"]
        # 시작 상태: 기록 시작일 전 마지막 실시 (시작일 기준 며칠 전)
        if cyc == "DAILY":
            last = day0 - timedelta(days=1)
        elif cyc == "WEEKLY":
            last = day0 - timedelta(days=7) + timedelta(days=int(r.integers(0, 7)))
        elif cyc == "MONTHLY":
            if tid in overdue:
                last = _add_month(overdue[tid], -1)
            elif eq in month_sessions:
                last = _add_month(month_sessions[eq]["window"].due, -1)
            elif eq in pp["vf2_monthly_due"] and isinstance(pp["vf2_monthly_due"][eq], str):   # 정비 구간 없이 기한만 정함 (기록 기간 전에 한 것)
                last = _add_month(date.fromisoformat(pp["vf2_monthly_due"][eq]), -1)
            else:
                last = day0 - timedelta(days=30) + timedelta(days=int(r.integers(0, 28)))
        elif cyc == "HALF_YEAR":
            last = day0 - timedelta(days=144) + timedelta(days=int(r.integers(0, 130)))
        elif cyc == "YEARLY":
            last = day0 - timedelta(days=326) + timedelta(days=int(r.integers(0, 320)))
        elif cyc == "EVERY_8H_USE":
            last = day0 - timedelta(days=1)
        else:
            continue
        add(t, None if cyc == "EVERY_8H_USE" else _add_month(last, 0), at(last, "09:30"), base=True)
        recs[-1]["due_date"] = last
        # 9월
        if cyc == "EVERY_8H_USE":                       # 텀블러 그리스: 교대마다 1번 (설계서 15.5 하루 2회)
            for sh in cal.shifts:
                dt = sh.start + timedelta(minutes=int(r.integers(10, 60)))
                add(t, sh.work_date, dt)
            continue
        if cyc == "MONTHLY" and eq in month_sessions and tid not in overdue:
            w = month_sessions[eq]
            add(t, w["window"].due, cal.to_dt(w["end_m"]))
            w.setdefault("records", []).append(len(recs) - 1)
            continue
        due = next_due(last, cyc)
        while due is not None and due <= day1:
            if tid in overdue and due >= overdue[tid]:
                break                                      # 기한 넘김 (시연 S2)
            dd = due
            while dd not in wset and dd <= day1:        # 기한이 휴무일이면 다음 근무일로 (기록 끝을 넘으면 그만)
                dd += timedelta(days=1)
            if dd > day1:
                break
            if cyc in ("DAILY", "WEEKLY") and r.random() > on_time:
                later = [x for x in workdays if x > dd]
                dd = later[0] if later else dd
            elif cyc == "MONTHLY":
                later = [x for x in workdays if x >= dd]
                dd = later[min(int(r.integers(*pp["monthly_late_days"])), len(later) - 1)]
            if dd > day1:
                break
            hm = ("09:05", "10:30") if t["default_role"] == "OPR" else ("09:30", "12:30")
            done_at = work_time(dd, *hm)
            add(t, due, done_at)
            due = next_due(dd, cyc)
            if cyc == "DAILY" and due <= dd:
                due = dd + timedelta(days=1)
    recs.sort(key=lambda x: (x["done_at"], x["pm_task_id"]))
    for i, x in enumerate(recs, 1):
        x["pm_record_id"] = i
    # MAINT 구간 → 그 묶음의 첫 실시 기록
    maint_ids = {}
    for i, w in enumerate(maint_done):
        if w["window"].kind == "PM_MONTHLY":
            ids = [x["pm_record_id"] for x in recs
                   if x["pm_task_id"] in w["window"].pm_task_ids and x["done_at"] == cal.to_dt(w["end_m"])]
            if ids:
                maint_ids[i] = min(ids)
    return recs, maint_ids
