"""시연 서버 시계와 근무 시간 (2026-10-25).

GET /api/health의 clock.sim_at과 profile.shifts를 읽는다. 읽기 전용이고 시연 서버를 새로 켜지 않는다.
둘 중 하나라도 없으면 None — 부른 쪽은 REFERENCE_AT(2026-10-01)와 옛 근무(08:00~17:00 / 20:00~05:00)를 쓴다.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from backend.services.shifts import kind_at, prev_open

KST = timezone(timedelta(hours=9))
TIMEOUT_S = 2.0
_CACHE_S = 5.0
_OLD_HOURS = ("08:00", "17:00", "20:00", "05:00")
PREV_SHIFT = re.compile(r"(?:직전|지난|이전|(?<![가-힣])전|(?<![가-힣])앞)\s*교대")
CUR_SHIFT = re.compile(r"(?:이번|지금|현재|현|오늘)\s*교대")
_cache: tuple[float, Clock | None] | None = None


@dataclass(frozen=True)
class Clock:
    at: datetime
    day_start: int
    day_end: int
    night_start: int
    night_end: int
    history_start: date | None = None      # 운영 기록이 시작된 날 (profile.history_start). 없으면 기준 시각의 날짜


def _minutes(text: object) -> int | None:
    if not isinstance(text, str) or len(text) < 4 or ":" not in text:
        return None
    hour, minute = text.split(":", 1)
    if not hour.isdigit() or not minute.isdigit():
        return None
    h, m = int(hour), int(minute)
    if h > 24 or m > 59:
        return None
    return h * 60 + m


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_health(doc: object) -> Clock | None:
    """시계 시각과 주간·야간 시작·끝이 모두 있을 때만 Clock. 옛 서버(profile 없음)는 None."""
    if not isinstance(doc, dict):
        return None
    clock = doc.get("clock")
    sim_at = clock.get("sim_at") if isinstance(clock, dict) else None
    profile = doc.get("profile")
    shifts = profile.get("shifts") if isinstance(profile, dict) else None
    if not isinstance(sim_at, str) or not isinstance(shifts, dict):
        return None
    day = shifts.get("DAY") if isinstance(shifts.get("DAY"), dict) else None
    night = shifts.get("NIGHT") if isinstance(shifts.get("NIGHT"), dict) else None
    if day is None or night is None:
        return None
    day_start, day_end = _minutes(day.get("start")), _minutes(day.get("end"))
    night_start, night_end = _minutes(night.get("start")), _minutes(night.get("end"))
    if None in (day_start, day_end, night_start, night_end):
        return None
    if not (0 <= day_start < day_end <= night_start < 24 * 60 and 0 <= night_end <= day_start):
        return None
    try:
        at = datetime.fromisoformat(sim_at)
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=KST)
    hs = profile.get("history_start") if isinstance(profile, dict) else None
    try:
        history_start = date.fromisoformat(hs[:10]) if isinstance(hs, str) else None
    except ValueError:
        history_start = None
    return Clock(at.astimezone(KST), day_start, day_end, night_start, night_end, history_start)


def fetch(url: str) -> Clock | None:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=TIMEOUT_S) as r:  # noqa: S310 — 주소는 서버 설정에서만 온다
            return parse_health(json.loads(r.read().decode("utf-8")))
    except Exception:  # noqa: BLE001 — 연결·시간 초과·형식 오류면 옛 날짜로 간다
        return None


def current() -> Clock | None:
    """시연 서버 시계. 몇 초 안에는 같은 값을 다시 쓴다. 실패도 같이 기억해 질문마다 기다리지 않는다."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_S:
        return _cache[1]
    from backend.config import settings

    got = fetch(settings().sim_server_url)
    _cache = (now, got)
    return got


def anchor_date() -> date:
    """오늘. 시계가 없으면 REFERENCE_AT의 날짜."""
    live = current()
    if live is None:
        from backend.config import REFERENCE_AT

        return date.fromisoformat(REFERENCE_AT[:10])
    return live.at.date()


def _old_reference_day() -> date:
    from backend.config import REFERENCE_AT

    return date.fromisoformat(REFERENCE_AT[:10])


def data_period() -> tuple[date, date]:
    """운영 기록이 있는 기간 (처음, 마지막). 시계가 있으면 profile.history_start(없으면 기준 시각의 날짜)부터 오늘까지,
    시계가 없으면 옛 9월 데이터 기간 9/1~9/30 (옛 시연 서버·시험). 2026-10-25: 공용 DB가 10월 데이터로 바뀌었는데 비서가 9월만 알았다."""
    live = current()
    if live is None:
        return date(2026, 9, 1), date(2026, 9, 30)
    return (live.history_start or _old_reference_day()), live.at.date()


def default_end() -> date:
    """기간을 말하지 않은 조회의 끝: 데이터가 있는 마지막 끝난 날 = 어제(시계 없음: 옛 9/30 = 기준 시각 전날). 어제가 기록 시작 전이면 시작일."""
    live = current()
    if live is None:
        return date(2026, 9, 30)
    start, _ = data_period()
    return max(live.at.date() - timedelta(days=1), start)


def default_range(days: int = 30) -> tuple[date, date]:
    """기간을 말하지 않은 조회의 기본 기간: default_end()까지 days일, 기록 시작 전으로는 가지 않는다."""
    end = default_end()
    return max(end - timedelta(days=days - 1), data_period()[0]), end


def hour_words() -> tuple[str, str, str, str]:
    """(주간 시작, 주간 끝, 야간 시작, 야간 끝). 시계가 없으면 08:00, 17:00, 20:00, 05:00."""
    live = current()
    if live is None:
        return _OLD_HOURS
    return (_hhmm(live.day_start), _hhmm(live.day_end), _hhmm(live.night_start), _hhmm(live.night_end))


def current_kind() -> tuple[date, str] | None:
    live = current()
    if live is None:
        return None
    return kind_at(live.at, live.day_start, live.night_start)


def previous_open() -> tuple[date, str] | None:
    cur = current_kind()
    if cur is None:
        return None
    return prev_open(*cur)


def named_period(name: str) -> tuple[date | None, date | None, str | None]:
    """today·yesterday·last_shift·recent_7·recent_30. 시계가 없으면 10/1과 9/30 야간."""
    ref = anchor_date()
    y = ref - timedelta(days=1)
    if name == "today":
        return ref, ref, None
    if name == "yesterday":
        return y, y, None
    if name == "last_shift":
        prev = previous_open()
        if prev is None:
            return y, y, "N"
        return prev[0], prev[0], prev[1]
    if name == "recent_7":
        return ref - timedelta(days=7), y, None
    if name == "recent_30":
        return ref - timedelta(days=30), y, None
    return None, None, None
