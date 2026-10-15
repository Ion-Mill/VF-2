"""역할별 권한 판단 (role_permission 표, 기획서 13.1·13.2). DB 없이 시험할 수 있게 순수 로직으로 둔다."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Grant:
    role_code: str
    target: str
    action: str
    scope: str


class PermissionTable:
    def __init__(self, rows: Iterable[dict | Grant]):
        self._grants: dict[tuple[str, str, str], str] = {}
        for r in rows:
            g = r if isinstance(r, Grant) else Grant(r["role_code"], r["target"], r["action"], r["scope"])
            self._grants[(g.role_code, g.target, g.action)] = g.scope

    def scope(self, role_code: str, target: str, action: str) -> str | None:
        """허용이면 범위(ALL/OWN/SUMMARY/PROXY/OWNED_ITEMS), 아니면 None."""
        return self._grants.get((role_code, target, action))

    def allows(self, role_code: str, target: str, action: str) -> bool:
        return self.scope(role_code, target, action) is not None

    def any_of(self, role_code: str, *pairs: tuple[str, str]) -> bool:
        return any(self.allows(role_code, t, a) for t, a in pairs)

    def targets(self, role_code: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for (role, target, action) in self._grants:
            if role == role_code:
                out.setdefault(target, []).append(action)
        return {k: sorted(v) for k, v in sorted(out.items())}


# 문서 종류 → 보기 권한 대상 (13.1). 작업기록서는 정식(WORK_RECORD) / 간이(WORK_RECORD_SIMPLE, 번호 MR-S-…)로 나눈다
DOC_VIEW_TARGET = {"SHIFT_REPORT": "SHIFT_REPORT", "DAILY_REPORT": "DAILY_REPORT", "WORK_ORDER": "WORK_ORDER",
                   "PM_RECORD": "PM_RECORD", "SHIPMENT": "SHIPMENT", "INTERNAL_DOC": "INTERNAL_DOC"}
SIMPLE_RECORD_PREFIX = "MR-S-"


def doc_viewable(table: PermissionTable, role_code: str, doc_type: str | None, doc_key: str | None) -> bool:
    """이 역할이 이 문서를 볼 수 있나 (문서함·수정 이력·실시간 document_changed가 같은 규칙을 쓴다)"""
    if doc_type == "WORK_RECORD":
        return table.allows(role_code, "WORK_RECORD", "VIEW") or (
            table.allows(role_code, "WORK_RECORD_SIMPLE", "VIEW") and (doc_key or "").startswith(SIMPLE_RECORD_PREFIX))
    target = DOC_VIEW_TARGET.get(doc_type or "")
    return target is not None and table.allows(role_code, target, "VIEW")
