"""② 달력과 교대 (설계서 5.2·5.3, ERD 5.A.5 work_day·5.A.6 shift).

시간은 '분 번호'로 다룬다: T0 = 2026-09-01 00:00 KST 부터 1분마다 1씩.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .common import KST, WEEKDAY, at, daterange


@dataclass
class Shift:
    shift_id: str
    work_date: date
    shift_type: str          # DAY / NIGHT
    start: datetime
    end: datetime
    brk: tuple[datetime, datetime]
    supervisor: str
    target_qty: int
    planned_min: int
    carry_over_qty: int = 0
    actual_qty: int = 0      # 그 교대 OP-50 GQ + RQ (시간 흐름 뒤 채움)


@dataclass
class Calendar:
    t0: datetime
    t_end: datetime                       # 과거 기록 끝 (10/1 08:00)
    days: list[date]
    workdays: list[date]
    shifts: list[Shift]
    minute_shift: list[int] = field(default_factory=list)   # 분 번호 → shifts 번호, 일하는 분이 아니면 -1
    minute_break: list[bool] = field(default_factory=list)  # 분 번호 → 휴식 중

    def to_min(self, t: datetime) -> int:
        return int((t - self.t0).total_seconds() // 60)

    def to_dt(self, m: int) -> datetime:
        return self.t0 + timedelta(minutes=m)

    @property
    def n_min(self) -> int:
        return self.to_min(self.t_end)

    def shift_at(self, m: int) -> Shift | None:
        i = self.minute_shift[m] if 0 <= m < self.n_min else -1
        return self.shifts[i] if i >= 0 else None

    def shift_or_near(self, m: int) -> Shift:
        """일하는 분이 아니면 직전(없으면 직후) 교대 — 교대 밖 기록의 담당자를 고를 때."""
        for k in range(m, -1, -1):
            if self.minute_shift[k] >= 0:
                return self.shifts[self.minute_shift[k]]
        for k in range(m, self.n_min):
            if self.minute_shift[k] >= 0:
                return self.shifts[self.minute_shift[k]]
        raise ValueError("교대가 없음")

    def is_work(self, m: int) -> bool:
        return 0 <= m < self.n_min and self.minute_shift[m] >= 0 and not self.minute_break[m]


def build_calendar(cfg: dict) -> Calendar:
    p, s, tg = cfg["period"], cfg["shifts"], cfg["targets"]
    start, end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
    closed = {WEEKDAY[w] for w in p["closed_weekdays"]}
    closed_dates = {date.fromisoformat(x) for x in p["closed_dates"]}
    days = list(daterange(start, end))
    workdays = [d for d in days if d.weekday() not in closed and d not in closed_dates]
    assert len(workdays) == p["work_days"], (len(workdays), p["work_days"])

    sup = {"DAY": "U10", "NIGHT": "U11"}      # app_user.csv: 반장 주간 U10, 반장 야간 U11
    shifts: list[Shift] = []
    for d in workdays:
        for st in ("DAY", "NIGHT"):
            c = s[st]
            st_at = at(d, c["start"])
            en_at = at(d, c["end"])
            if en_at <= st_at:
                en_at += timedelta(days=1)
            b0, b1 = at(d, c["break"][0]), at(d, c["break"][1])
            if b0 < st_at:
                b0 += timedelta(days=1)
                b1 += timedelta(days=1)
            shifts.append(Shift(
                shift_id=f"{d.isoformat()}-{'D' if st == 'DAY' else 'N'}", work_date=d, shift_type=st,
                start=st_at, end=en_at, brk=(b0, b1), supervisor=sup[st],
                target_qty=tg["shift_target"], planned_min=s["planned_minutes"]))
    assert len(shifts) == 2 * len(workdays)

    t0 = datetime(start.year, start.month, start.day, tzinfo=KST)
    t_end = at(end + timedelta(days=1), cfg["realtime"]["start"][11:16])   # 10/1 08:00
    cal = Calendar(t0=t0, t_end=t_end, days=days, workdays=workdays, shifts=shifts)
    n = cal.n_min
    cal.minute_shift = [-1] * n
    cal.minute_break = [False] * n
    for i, sh in enumerate(shifts):
        a, b = cal.to_min(sh.start), cal.to_min(sh.end)
        for m in range(max(a, 0), min(b, n)):
            cal.minute_shift[m] = i
        for m in range(cal.to_min(sh.brk[0]), cal.to_min(sh.brk[1])):
            if 0 <= m < n:
                cal.minute_break[m] = True
        work = sum(1 for m in range(a, b) if not cal.minute_break[m])
        assert work == sh.planned_min, (sh.shift_id, work)   # 480분 = 9시간 − 휴식 1시간
    return cal


def extend_calendar(cal: Calendar, cfg: dict, days: int = 1) -> Calendar:
    """실시간 모드: 과거 기록 끝(10/1 08:00) 뒤로 근무일 days개(10/1 주간·야간)를 더한다. 같은 객체를 고친다."""
    s, tg = cfg["shifts"], cfg["targets"]
    sup = {"DAY": "U10", "NIGHT": "U11"}
    d = cal.days[-1]
    added = []
    while len(added) < days:
        d += timedelta(days=1)
        cal.days.append(d)
        if d.weekday() in {WEEKDAY[w] for w in cfg["period"]["closed_weekdays"]}:
            continue
        cal.workdays.append(d)
        added.append(d)
        for st in ("DAY", "NIGHT"):
            c = s[st]
            st_at, en_at = at(d, c["start"]), at(d, c["end"])
            if en_at <= st_at:
                en_at += timedelta(days=1)
            b0, b1 = at(d, c["break"][0]), at(d, c["break"][1])
            if b0 < st_at:
                b0 += timedelta(days=1)
                b1 += timedelta(days=1)
            cal.shifts.append(Shift(
                shift_id=f"{d.isoformat()}-{'D' if st == 'DAY' else 'N'}", work_date=d, shift_type=st,
                start=st_at, end=en_at, brk=(b0, b1), supervisor=sup[st],
                target_qty=tg["shift_target"], planned_min=s["planned_minutes"]))
    old = cal.n_min
    cal.t_end = at(d + timedelta(days=1), cfg["realtime"]["start"][11:16])
    n = cal.n_min
    cal.minute_shift += [-1] * (n - old)
    cal.minute_break += [False] * (n - old)
    for i, sh in enumerate(cal.shifts):
        if sh.work_date not in added:
            continue
        for m in range(cal.to_min(sh.start), min(cal.to_min(sh.end), n)):
            cal.minute_shift[m] = i
        for m in range(cal.to_min(sh.brk[0]), cal.to_min(sh.brk[1])):
            if 0 <= m < n:
                cal.minute_break[m] = True
    return cal


def work_day_rows(cal: Calendar, cfg: dict) -> list[dict]:
    wd = set(cal.workdays)
    return [{"work_date": d, "is_workday": d in wd,
             "daily_target_qty": cfg["targets"]["daily_target"] if d in wd else None} for d in cal.days]


def shift_rows(cal: Calendar) -> list[dict]:
    return [{"shift_id": s.shift_id, "work_date": s.work_date, "shift_type": s.shift_type,
             "start_at": s.start, "end_at": s.end, "planned_time_min": s.planned_min,
             "target_qty": s.target_qty, "carry_over_qty": s.carry_over_qty,
             "supervisor_user_id": s.supervisor} for s in cal.shifts]


WORK_DAY_COLS = ["work_date", "is_workday", "daily_target_qty"]
SHIFT_COLS = ["shift_id", "work_date", "shift_type", "start_at", "end_at", "planned_time_min",
              "target_qty", "carry_over_qty", "supervisor_user_id"]
