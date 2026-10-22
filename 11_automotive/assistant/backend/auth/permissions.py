"""역할 권한 (기획서_최종본 13장, UI설계서_최종본 16:00판 읽기 전용 모니터링 계정). 서버에서 검사한다."""
from __future__ import annotations

ROLES = {"OPR", "MNT", "SUP", "MGR", "MON"}

# 행동 → 허용 역할. MGR은 모든 조회가 된다(D-11). MON은 업무 역할이 아닌 조회 전용 계정이다.
PERMISSIONS: dict[str, set[str]] = {
    "chat": {"OPR", "MNT", "SUP", "MGR"},
    "view_doc_section": {"OPR", "MNT", "SUP", "MGR"},
    "view_guide_card": {"OPR", "MNT", "SUP", "MGR"},
    "view_alerts": {"OPR", "MNT", "SUP", "MGR"},           # SCR-07 (MON은 MGR 홈 요약·SCR-16만)
    "view_docs": {"OPR", "MNT", "SUP", "MGR"},             # SCR-24 (전원 보기, MGR 개정 승인)
    "run_demo_scenario": {"OPR", "MNT", "SUP", "MGR"},     # 시연 모드 전용 사건 넣기 [제안] (설비 조작 아님)
    "write_work_order": {"MNT"},
    "approve_work_order": {"SUP"},  # 반장만 (DOC-03 §1.4, DOC-07 §10.4)
    "assign_work_order": {"SUP"},
    "confirm_work_record": {"MNT"},
    "confirm_simple_record_caution": {"OPR", "MNT"},
    "confirm_simple_record_stop_other": {"MNT"},
    "confirm_pm_record": {"MNT"},
    "confirm_shift_report": {"SUP"},
    "confirm_daily_report": {"MGR"},
    "view_daily_report": {"MNT", "SUP", "MGR", "MON"},
    "view_home_summary": {"MGR", "MON"},
    "confirm_shipment": {"SUP"},
    "hold_lot": {"SUP", "MGR"},
    "set_safety_stock": {"MGR"},
    "approve_doc_revision": {"MGR"},
    "view_ops": {"OPR", "MNT", "SUP", "MGR"},
    # 교대 시작 브리핑 (AST-01, UI설계서 SCR-02·03, 2026-10-11 P3): 전체형 = SUP 주 사용자·MNT·MGR 조회, 작업자 요약형 = OPR (MGR 조회)
    "view_briefing_full": {"MNT", "SUP", "MGR"},
    "view_briefing_operator": {"OPR", "MGR"},
}

# 문서 종류별 확정 권한 (기획서 13.1, 수정 이력 대상 7종)
CONFIRM_ACTION = {
    "작업지시서": "approve_work_order",
    "작업기록서": "confirm_work_record",
    "간이 작업기록": "confirm_simple_record_caution",
    "예방 정비 실시 기록": "confirm_pm_record",
    "교대 보고서": "confirm_shift_report",
    "일일 보고서": "confirm_daily_report",
    "출하 기록": "confirm_shipment",
}
EDIT_ACTION = {
    "작업지시서": {"MNT"},
    "작업기록서": {"MNT"},
    "간이 작업기록": {"OPR", "MNT"},
    "예방 정비 실시 기록": {"MNT"},
    "교대 보고서": {"SUP"},
    "일일 보고서": {"MGR"},
    "출하 기록": {"SUP"},
}


class PermissionDenied(Exception):
    message = "권한이 없습니다"


class NotLoggedIn(PermissionDenied):
    """역할 머리말이 없거나 모르는 역할, 또는 사용자와 역할이 다름 → API 오류 UNAUTHORIZED (2026-10-11 P4).
    PermissionDenied를 이어받아, 예전처럼 PermissionDenied로 잡던 곳(비서 답의 권한 상태 등)은 그대로 동작한다."""
    message = "로그인 정보가 없거나 맞지 않습니다"


def normalize_role(role: str | None) -> str:
    r = (role or "").upper()
    if r not in ROLES:
        raise NotLoggedIn()
    return r


def can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, set())


def require(role: str, action: str) -> None:
    if not can(normalize_role(role), action):
        raise PermissionDenied()
