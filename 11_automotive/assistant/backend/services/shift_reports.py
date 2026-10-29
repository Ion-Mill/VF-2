"""교대 보고서 상태와 확정 (API명세서 RPT-03, FR-PRD-02-11, 2026-10-11 멈춤 ③ P4).

- 가상 데이터의 교대 보고서(52개)는 모두 '확정'이다. 초안·확정 변화는 시연 상태(DemoState.reports)에 겹쳐 둔다.
- 교대 끝(17:00·05:00)에 서버가 초안을 만드는 일(API명세서 4장, FR-PRD-02-01)은 아직 없다. 시연·시험은 draft()로 초안을 만든다.
- 확정은 그 교대 반장만(교대 달력 `sup`), 확정자는 X-User, 보낸 version이 지금 버전과 같아야 한다.
"""
from __future__ import annotations

from backend.auth.permissions import NotLoggedIn, PermissionDenied, normalize_role
from backend.errors import ApiError
from backend.repositories.csv_repo import get_repo
from backend.services import revisions as R
from backend.services.shifts import to_internal, to_spec


def _row(sid: str) -> dict | None:
    return next((r for r in get_repo().table("shift_report") if r["shift_id"] == sid), None)


def _shift(sid: str) -> dict | None:
    return next((s for s in get_repo().table("calendar_shift") if s["shift_id"] == sid), None)


def current(state, shift_id: str) -> dict:
    sid = to_internal(shift_id)
    row = _row(sid)
    if row is None:
        raise ApiError("NOT_FOUND", "교대 보고서가 없습니다", {"shift_id": shift_id})
    doc = state.reports.get(sid)
    base = {"shift_id": to_spec(sid), "shift_key": sid, "report_id": row["report_id"], "is_synthetic": True}
    if doc is None:  # 겹친 기록이 없으면 가상 데이터 그대로
        return {**base, "status": row["status"], "version": 0, "confirmed_by": row["confirmed_by"],
                "confirmed_at": row["confirmed_at"], "is_provisional": row["status"] != "확정"}
    return {**base, "status": "확정" if doc.is_confirmed else doc.current.label, "version": doc.current.version,
            "confirmed_by": doc.confirmed_by, "confirmed_at": doc.confirmed_at, "is_provisional": not doc.is_confirmed}


def draft(state, shift_id: str) -> dict:
    """교대 보고서를 'AI비서 초안'(v0, 미확정 = 잠정)으로 둔다 — 시연·시험용. 서버의 17:00·05:00 초안 만들기는 아직 없다."""
    sid = to_internal(shift_id)
    row = _row(sid)
    if row is None:
        raise ApiError("NOT_FOUND", "교대 보고서가 없습니다", {"shift_id": shift_id})
    with state.lock:
        state.reports[sid] = R.create("교대 보고서", row["report_id"], {"output": row["output"], "good": row["good"],
                                                                        "scrap": row["scrap"]}, row["draft_at"])
    return current(state, sid)


def confirm(state, shift_id: str, user_id: str, role: str, version: int | None) -> dict:
    r = normalize_role(role)                       # 역할 머리말 없음·모름 → UNAUTHORIZED
    u = state.user(user_id) if user_id else None
    if u is None or u["role"] != r:                # 확정자 = X-User, 역할이 같아야 한다
        raise NotLoggedIn()
    if r != "SUP":                                 # OPR·MNT·MGR → FORBIDDEN (MGR도 교대 보고서는 확정하지 않는다)
        raise PermissionDenied()
    sid = to_internal(shift_id)
    cur = current(state, sid)                      # 없는 보고서 → NOT_FOUND
    sh = _shift(sid)
    if sh is None or sh["sup"] != user_id:         # 다른 교대 반장 → FORBIDDEN (2026-10-11 P2)
        raise PermissionDenied()
    if cur["status"] == "확정":
        raise ApiError("INVALID_STATE", "이미 확정된 교대 보고서입니다 (확정 뒤 수정 RPT-04는 아직 없음)",
                       {"shift_id": cur["shift_id"], "confirmed_by": cur["confirmed_by"]})
    if version is None or version != cur["version"]:
        raise ApiError("CONFLICT_VERSION", detail={"shift_id": cur["shift_id"], "current_version": cur["version"],
                                                    "sent_version": version})
    with state.lock:
        R.confirm(state.reports[sid], user_id, r, state.now.isoformat())
    return current(state, sid)
