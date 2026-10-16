"""DOC-07 설비 데이터·지표 정의서(Rev.1)의 계산식. 숫자는 이 모듈만 계산하고 LLM은 계산하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

FAILURE_CODES = {"F01", "F02", "F03", "F04", "F05", "F06"}
OPERATION_CODES = {"O01", "O02", "O03"}
REQUIRED_STOP_MIN = 5  # DOC-07 §2.2·§5.4 순간 정지/고장 정지 경계 [가상]


def round_half_up(x: float, digits: int = 0) -> float:
    q = Decimal(1).scaleb(-digits)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def pct(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return round_half_up(numerator / denominator * 100, 1)


def availability(apt_min: float, pbt_min: float) -> float | None:
    """가동률 A = APT ÷ PBT × 100 (DOC-07 §6.2)."""
    return pct(apt_min, pbt_min)


def performance(pri_min: float, pq: int, apt_min: float) -> float | None:
    """성능 E = PRI × PQ ÷ APT × 100 (DOC-07 §6.2)."""
    return pct(pri_min * pq, apt_min)


def quality_buy_rate(gq: int, rq: int, pq: int) -> float | None:
    """양품률 QBR = (GQ + RQ) ÷ PQ × 100 (DOC-07 §6.2)."""
    return pct(gq + rq, pq)


def oee(a: float | None, e: float | None, q: float | None) -> float | None:
    """OEE = A × E × QBR (DOC-07 §6.2). 입력·출력 모두 %."""
    if a is None or e is None or q is None:
        return None
    return round_half_up(a / 100 * e / 100 * q / 100 * 100, 1)


def oee_from(apt_min: float, pbt_min: float, pri_min: float, pq: int, gq: int, rq: int = 0) -> float | None:
    """OEE를 반올림 전 A·E·QBR로 곱해 계산한다 (표시용으로 반올림한 값끼리 곱하면 0.1%p 어긋날 수 있다).

    DOC-07 §6.2 계산 예: 336/480 × 7.0×46/336 × 45/46 = 65.6%.
    """
    if not pbt_min or not apt_min or not pq:
        return None
    return round_half_up(apt_min / pbt_min * (pri_min * pq / apt_min) * ((gq + rq) / pq) * 100, 1)


def mttr(repair_minutes: list[float]) -> float | None:
    """MTTR = 수리 시간 합 ÷ 고장 횟수 (정지 등급 DOWN만). 고장 0건이면 None("—")."""
    if not repair_minutes:
        return None
    return round_half_up(sum(repair_minutes) / len(repair_minutes), 1)


def mtbf(between_hours: list[float], failure_count: int) -> float | None:
    """MTBF = 고장 간격 시간 합 ÷ 고장 횟수 (DOC-07 §6.2)."""
    if not failure_count:
        return None
    return round_half_up(sum(between_hours) / failure_count, 1)


def loss_qty_estimate(stop_min: float, cycle_min: float) -> int:
    """고장 손실 수량(추정) = 정지 시간 ÷ 기준 사이클 시간 (DOC-07 §5.3). 예: 48 ÷ 7.0 ≈ 7."""
    return int(round_half_up(stop_min / cycle_min, 0))


def forecast_output(current: int, recent_rate_per_min: float, remaining_min: float) -> float:
    """예측 실적 = 현재 실적 + 최근 1시간 생산 속도 × 남은 시간 (DOC-07 §8)."""
    return round_half_up(current + recent_rate_per_min * remaining_min, 1)


def target_risk(forecast: float, target: int, ratio: float = 0.9) -> bool:
    """목표 미달 위험 = 예측 실적 < 교대 목표 × 90% (DOC-07 §8) [가상]."""
    return forecast < target * ratio


def carry_over_qty(shift_kind: str, day_actual: int | None, shift_target: int) -> int:
    """이월 (FR-PRD-01-15, ERD shift.carry_over_qty, 2026-10-11 P3): **야간만** max(0, 교대 목표 − 같은 생산일 주간 실적).
    주간은 늘 0 (앞 근무일 야간의 부족은 넘기지 않는다 — 그날 하루 부족으로 남는다). 주간 기록이 없으면 0.
    예: 주간 실적 87 → 야간 이월 3 (총 목표 93), 주간 실적 90 이상 → 0."""
    if shift_kind != "N" or day_actual is None:
        return 0
    return max(0, int(shift_target) - int(day_actual))


def tool_usage_pct(used: float, limit: float) -> int:
    """공구 수명 사용률 = 누적 사용량 ÷ 한도 × 100, 소수점 버림 (DOC-07 §9)."""
    return int(used / limit * 100)


@dataclass
class Stop:
    stop_id: str
    equipment_id: str
    start: str
    end: str
    minutes: float
    reason_code: str
    cycle_min: float
    alarm_event_id: str = ""

    @property
    def loss_qty(self) -> int:
        return loss_qty_estimate(self.minutes, self.cycle_min)


def required_stops(stops: list[Stop]) -> dict:
    """필수 정지 (DOC-07 §5.4): 고장 그룹 F01~F06이고 5분 이상인 정지 전부.

    정렬: 정지 시간 긴 순 → 손실 수량 큰 순 → 시작 이른 순. 순간 정지(O01~O03)는 건수·합계만.
    소재 대기 M01 등 다른 그룹은 넣지 않는다.
    """
    req = [s for s in stops if s.reason_code in FAILURE_CODES and s.minutes >= REQUIRED_STOP_MIN]
    req.sort(key=lambda s: (-s.minutes, -s.loss_qty, s.start))
    micro = [s for s in stops if s.reason_code in OPERATION_CODES and s.minutes < REQUIRED_STOP_MIN]
    return {
        "items": req,
        "micro_count": len(micro),
        "micro_minutes": round_half_up(sum(s.minutes for s in micro), 1),
    }
