"""문서 버전 모델 (AST-03, ai-operations-assistant 규칙 2.4).

v0 = "AI비서 초안"(AI가 쓰는 4종) 또는 "처음 저장"(사람이 쓰는 3종) → 사람 수정 v1, v2 … → 확정.
확정 뒤 수정은 새 버전과 수정 사유가 필수다. 확정된 버전은 덮어쓰지 않는다. AI는 확정하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.auth.permissions import CONFIRM_ACTION, EDIT_ACTION, PermissionDenied, can, normalize_role

AI_DRAFT_TYPES = {"작업지시서", "작업기록서", "교대 보고서", "일일 보고서"}
TRACKED_TYPES = set(CONFIRM_ACTION)


class RevisionError(ValueError):
    pass


@dataclass
class Version:
    version: int
    label: str
    author: str
    at: str
    content: dict
    reason: str = ""
    changed: dict = field(default_factory=dict)
    ai_fields: tuple = ()


@dataclass
class Document:
    doc_type: str
    doc_id: str
    versions: list[Version] = field(default_factory=list)
    confirmed_by: str = ""
    confirmed_at: str = ""

    @property
    def current(self) -> Version:
        return self.versions[-1]

    @property
    def is_confirmed(self) -> bool:
        return bool(self.confirmed_at)


def create(doc_type: str, doc_id: str, content: dict, at: str, author: str = "AI") -> Document:
    if doc_type not in TRACKED_TYPES:
        raise RevisionError(f"수정 이력 대상이 아닌 문서: {doc_type}")
    ai = author == "AI"
    if ai and doc_type not in AI_DRAFT_TYPES:
        raise RevisionError(f"{doc_type}은 AI비서 초안이 없는 문서다")
    label = "AI비서 초안" if ai else "처음 저장"
    return Document(doc_type, doc_id, [Version(0, label, author, at, dict(content), ai_fields=tuple(content) if ai else ())])


def edit(doc: Document, user: str, role: str, changes: dict, at: str, reason: str = "") -> Version:
    role = normalize_role(role)
    if role not in EDIT_ACTION[doc.doc_type]:
        raise PermissionDenied()
    if doc.is_confirmed and not reason.strip():
        raise RevisionError("확정 뒤 수정은 수정 사유가 필요합니다")
    before = doc.current.content
    changed = {k: {"before": before.get(k), "after": v} for k, v in changes.items() if before.get(k) != v}
    if not changed:
        raise RevisionError("바뀐 칸이 없습니다")
    content = {**before, **changes}
    v = Version(doc.current.version + 1, "확정 뒤 수정" if doc.is_confirmed else "사람 수정", user, at, content, reason, changed,
                tuple(f for f in doc.current.ai_fields if f not in changes))
    doc.versions.append(v)
    if doc.is_confirmed:  # 확정 뒤 고친 문서는 다시 확정받아야 한다
        doc.confirmed_by = doc.confirmed_at = ""
    return v


def confirm(doc: Document, user: str, role: str, at: str) -> None:
    if user == "AI":
        raise PermissionDenied()
    role = normalize_role(role)
    if not can(role, CONFIRM_ACTION[doc.doc_type]):
        raise PermissionDenied()
    doc.confirmed_by, doc.confirmed_at = user, at
