"""교대 번호와 시각 (2026-10-11 멈춤 ③ P4, ④ P3에서 넓힘).

- 우리 데이터의 교대 번호는 `SHIFT-260930-D`(가상데이터설계서), API명세서_v1은 `2026-09-30-D`다. API는 둘 다 받는다.
- 서버 안에서는 데이터 꼴(`SHIFT-…`)로 바꿔 쓴다. 꼴이 다르다는 것은 불일치로 기록한다(대조 노트).
- 교대 시각 (가상데이터설계서 5.2 [가상]): 주간 08:00~17:00, 야간 20:00~다음 날 05:00. 교대 사이(05:00~08:00, 17:00~20:00)는
  다음 교대로 본다 (demo_state.shift_of와 같은 기준).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from backend.errors import ApiError

INTERNAL = re.compile(r"SHIFT-(\d{2})(\d{2})(\d{2})-([DN])")
SPEC = re.compile(r"(\d{4})-(\d{2})-(\d{2})-([DN])")
KST = timezone(timedelta(hours=9))


def to_internal(shift_id: str) -> str:
    s = (shift_id or "").strip().upper()
    m = SPEC.fullmatch(s)
    if m:
        return f"SHIFT-{m[1][2:]}{m[2]}{m[3]}-{m[4]}"
    if INTERNAL.fullmatch(s):
        return s
    raise ApiError("VALIDATION", "교대 번호 꼴이 틀렸습니다 (예: 2026-10-01-D)", {"shift_id": shift_id})


def to_spec(internal: str) -> str:
    m = INTERNAL.fullmatch(internal)
    if not m:
        raise ValueError(f"교대 번호 꼴이 아님: {internal}")
    return f"20{m[1]}-{m[2]}-{m[3]}-{m[4]}"


def _parts(sid: str) -> tuple[date, str]:
    m = INTERNAL.fullmatch(sid)
    if not m:
        raise ValueError(f"교대 번호 꼴이 아님: {sid}")
    return date(2000 + int(m[1]), int(m[2]), int(m[3])), m[4]


def _make(d: date, kind: str) -> str:
    return f"SHIFT-{d:%y%m%d}-{kind}"


def shift_id_of(t: datetime) -> str:
    """시각 → 교대 번호. 05:00~17:00 = 그날 주간, 17:00~24:00 = 그날 야간, 00:00~05:00 = **전날** 야간.
    2026-10-11 고침: 전에는 자정 뒤(00:00~05:00)를 그날 야간으로 셌다(demo_state·guide_card) — 야간은 전날 20:00에 시작한다."""
    if t.hour < 5:
        return _make((t - timedelta(days=1)).date(), "N")
    return _make(t.date(), "D" if t.hour < 17 else "N")


def prev_shift(sid: str) -> str:
    """바로 앞 교대: 주간의 앞은 전날 야간, 야간의 앞은 그날 주간."""
    d, kind = _parts(sid)
    return _make(d, "D") if kind == "N" else _make(d - timedelta(days=1), "N")


def day_shift_of(sid: str) -> str:
    """같은 생산일의 주간 교대 (야간 이월을 셀 때 쓴다)."""
    d, _ = _parts(sid)
    return _make(d, "D")


def kind_of(sid: str) -> str:
    return _parts(sid)[1]


def window(sid: str) -> tuple[datetime, datetime]:
    """교대 시작·끝 시각 (KST). 주간 08:00~17:00, 야간 20:00~다음 날 05:00."""
    d, kind = _parts(sid)
    if kind == "D":
        return datetime(d.year, d.month, d.day, 8, tzinfo=KST), datetime(d.year, d.month, d.day, 17, tzinfo=KST)
    n = d + timedelta(days=1)
    return datetime(d.year, d.month, d.day, 20, tzinfo=KST), datetime(n.year, n.month, n.day, 5, tzinfo=KST)


def name_of(sid: str) -> str:
    d, kind = _parts(sid)
    return f"{d.month}월 {d.day}일 {'주간 (08:00~17:00)' if kind == 'D' else '야간 (20:00~05:00)'}"


def kind_at(t: datetime, day_start: int, night_start: int) -> tuple[date, str]:
    """시연 근무(분). [night_start, 24시) = 그날 야간, [day_start, night_start) = 그날 주간(끝난 뒤 빈 시간도 그 주간),
    [0, day_start) = 전날 야간(끝난 뒤 아침 빈 시간도 그 야간). 옛 shift_id_of(5시·17시)는 그대로 둔다."""
    local = t.astimezone(KST) if t.tzinfo else t
    minute = local.hour * 60 + local.minute
    if minute >= night_start:
        return local.date(), "N"
    if minute >= day_start:
        return local.date(), "D"
    return local.date() - timedelta(days=1), "N"


def prev_open(day: date, kind: str) -> tuple[date, str]:
    """바로 앞 근무. 주간의 앞은 전날 야간, 야간의 앞은 그날 주간. 일요일에 시작하는 근무는 건너뛴다."""
    d, k = day, kind
    for _ in range(14):
        if k == "N":
            k = "D"
        else:
            d = d - timedelta(days=1)
            k = "N"
        if d.weekday() != 6:
            return d, k
    return d, k
