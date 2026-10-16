"""반복 알람 1·2단계 판정 (DOC-07 §10.4). 단계는 규칙이 정하고 비서는 문장만 쓴다."""
from __future__ import annotations

from datetime import datetime, timedelta


def bundle(times: list[datetime], window_min: int = 1, count: int = 3) -> list[datetime]:
    """같은 설비·같은 알람이 1분 안에 3번 이상이면 1건으로 묶는다 (DOC-07 §10.2)."""
    times = sorted(times)
    out, i = [], 0
    while i < len(times):
        j = i
        while j + 1 < len(times) and times[j + 1] - times[i] <= timedelta(minutes=window_min):
            j += 1
        if j - i + 1 >= count:
            out.append(times[i])
            i = j + 1
        else:
            out.append(times[i])
            i += 1
    return out


def stage1_at(times: list[datetime], window_days: int = 7, count: int = 3) -> datetime | None:
    """7일 안에 3번 이상이 처음 채워진 시각."""
    times = bundle(times)
    for i in range(len(times)):
        window = [t for t in times[: i + 1] if times[i] - t < timedelta(days=window_days)]
        if len(window) >= count:
            return times[i]
    return None


def stage2_at(times: list[datetime], plan_at: datetime | None, in_progress: list[tuple[datetime, datetime]] = (),
              window_days: int = 7) -> datetime | None:
    """조치 계획 저장 뒤 7일 안에 다시 1번이라도 나면 2단계. 조치 작업이 진행 중일 때 난 알람은 세지 않는다."""
    if plan_at is None:
        return None
    for t in bundle(times):
        if plan_at < t <= plan_at + timedelta(days=window_days):
            if any(a <= t <= b for a, b in in_progress):
                continue
            return t
    return None
