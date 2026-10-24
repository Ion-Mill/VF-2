"""시연 서버 시계가 있을 때만 오늘·근무를 그 시계로 계산한다 (2026-10-25). Claude·네트워크·공용 DB는 부르지 않는다."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from backend.services import answer as A
from backend.services import lookup_turn as LT
from backend.services import routing as R
from backend.services import sim_clock
from backend.services.shifts import kind_at
from backend.tools import query_tools as T

KST = timezone(timedelta(hours=9))
DAY = 9 * 60
NIGHT = 21 * 60


def _clock(iso: str):
    got = sim_clock.parse_health({
        "clock": {"sim_at": iso},
        "profile": {"shifts": {"DAY": {"start": "09:00", "end": "18:00"}, "NIGHT": {"start": "21:00", "end": "06:00"}}},
    })
    assert got is not None
    return got


def _use(monkeypatch, iso: str):
    monkeypatch.setattr(sim_clock, "current", lambda: _clock(iso))


def test_missing_clock_keeps_october_first():
    assert sim_clock.parse_health({"ok": True, "clock": {"sim_at": "2026-10-26T17:00:00+09:00"}}) is None
    assert sim_clock.parse_health({"clock": {"sim_at": "2026-10-26T17:00:00+09:00"}, "profile": {}}) is None
    assert LT.period_window("오늘") == (date(2026, 10, 1), date(2026, 10, 1), None)
    assert A.parse("오늘 충돌 어땠어")["start"] == date(2026, 10, 1)
    assert R._period_dates("last_shift") == (date(2026, 9, 30), date(2026, 9, 30), "N")


def test_october_26_at_17_is_day_and_previous_is_saturday_night(monkeypatch):
    _use(monkeypatch, "2026-10-26T17:00:00+09:00")
    assert LT.period_window("오늘") == (date(2026, 10, 26), date(2026, 10, 26), None)
    assert LT.period_window("이번 교대") == (date(2026, 10, 26), date(2026, 10, 26), "D")
    assert LT.period_window("직전 교대") == (date(2026, 10, 24), date(2026, 10, 24), "N")
    assert A.parse("오늘 충돌 어땠어")["start"] == date(2026, 10, 26)
    assert A.parse("직전 교대 보고서")["start"] == date(2026, 10, 24)
    assert A.parse("직전 교대 보고서")["shift"] == "N"
    assert T.current_shift("MNT") == (date(2026, 10, 26), "D")
    assert R._period_dates("last_shift") == (date(2026, 10, 24), date(2026, 10, 24), "N")
    start, end = T._windows(date(2026, 10, 26), date(2026, 10, 26), "D")[0]
    assert start.startswith("2026-10-26T09:00:00") and end.startswith("2026-10-26T18:00:00")
    text = A.daily_report_inclusion_answer_v29({}, "오늘 362는 9/30 일일 보고서에 있어?")["conclusion"]
    assert "주간(09:00~18:00)" in text and "야간(21:00~다음 날 06:00)" in text


def test_october_24_at_09_is_today(monkeypatch):
    _use(monkeypatch, "2026-10-24T09:00:00+09:00")
    assert LT.period_window("오늘") == (date(2026, 10, 24), date(2026, 10, 24), None)
    assert A.parse("오늘 생산 몇 개야")["start"] == date(2026, 10, 24)


def test_gap_hours_belong_to_the_shift_that_just_ended():
    assert kind_at(datetime(2026, 10, 26, 18, tzinfo=KST), DAY, NIGHT) == (date(2026, 10, 26), "D")
    assert kind_at(datetime(2026, 10, 26, 21, tzinfo=KST), DAY, NIGHT) == (date(2026, 10, 26), "N")
    assert kind_at(datetime(2026, 10, 26, 6, tzinfo=KST), DAY, NIGHT) == (date(2026, 10, 25), "N")
    assert kind_at(datetime(2026, 10, 26, 9, tzinfo=KST), DAY, NIGHT) == (date(2026, 10, 26), "D")
