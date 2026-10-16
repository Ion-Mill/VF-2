"""전부 보고·보고 순위 (DOC-07 §10.5, FR-AST-COM-21).

프로그램이 문제를 전부 모아 순위대로 정렬한다. 비서는 순서를 바꾸거나 빼지 않는다.
전체 N = 같은 설비·같은 원인을 묶은 뒤의 항목 수 (요구사항 기준, 2026-10-07 사용자 결정).
"""
from __future__ import annotations

from dataclasses import dataclass, field

RANKS = [("0", "안전"), ("0-1", "오래 방치"), ("1", "긴급"), ("2", "생산 위험"), ("3", "주의"), ("4", "참고")]
RANK_ORDER = {r: i for i, (r, _) in enumerate(RANKS)}
NEVER_FOLD = {"0", "0-1", "1"}
# 같은 순위 안의 하위 순서(①~⑤)는 순위 2(목표 미달 → 병목 → 납기)·3(반복 2단계 → 1단계 → 주의 알람 → …)에만 있다
# (DOC-07 §10.5, ai-operations-assistant 4.3절). 0-1은 "처리 안 된 시간이 긴 순"이고 나머지는 발생 시각이 이른 순이다.
# 2026-10-11 P2: 전에는 모든 순위에 하위 순서를 먼저 써서 0-1 줄이 원래 알림 종류 순으로 섞였다
SUB_ORDER_RANKS = {"2", "3"}
# 머리 "전체 N건 (안전 · 긴급 · 생산 위험 · 주의 · 참고)": 0-1(오래 방치)은 "주의"에 센다 (UI설계서 2.5)
SUMMARY_GROUPS = [("안전", {"0"}), ("긴급", {"1"}), ("생산", {"2"}), ("주의", {"0-1", "3"}), ("참고", {"4"})]


@dataclass
class Item:
    item_id: str
    rank: str
    title: str
    occurred_at: str
    group_key: str = ""          # 같은 설비·같은 원인이면 같은 키 → 한 줄로 묶음
    sub_order: int = 0            # 같은 순위 안 묶음 순서 (순위 3의 ①~⑤ 등)
    sort_value: float = 0.0       # 같은 묶음 안 정렬 값 (클수록 앞)
    records: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)


@dataclass
class Line:
    rank: str
    rank_name: str
    title: str
    items: list[Item]
    folded: bool = False

    @property
    def original_count(self) -> int:
        return len(self.items)


def _line_key(l: Line) -> tuple:
    top = l.items[0]
    sub = top.sub_order if l.rank in SUB_ORDER_RANKS else 0
    return (RANK_ORDER[l.rank], sub, -top.sort_value, top.occurred_at)


def rank_report(items: list[Item]) -> dict:
    groups: dict[str, list[Item]] = {}
    order: list[str] = []
    for it in items:
        key = it.group_key or it.item_id
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(it)
    lines = []
    for key in order:
        members = sorted(groups[key], key=lambda i: (RANK_ORDER[i.rank], i.occurred_at))
        top = members[0]
        lines.append(Line(top.rank, dict(RANKS)[top.rank], top.title, members, folded=top.rank not in NEVER_FOLD))
    lines.sort(key=_line_key)
    counts = {name: sum(1 for l in lines if l.rank in ranks) for name, ranks in SUMMARY_GROUPS}
    by_rank = {r: [l for l in lines if l.rank == r] for r, _ in RANKS}
    return {"total": len(lines), "counts": counts, "lines": lines, "by_rank": by_rank}
