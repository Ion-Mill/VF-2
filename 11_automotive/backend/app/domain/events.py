"""DB 알림(mom_events) → 실시간 사건 이름 (API명세서 3장). DB 없이 도는 순수 로직.

DB 트리거(trg_notify_event)는 {table, op, id, equipment_id, importance, doc_type, status}만 보낸다 (내용 없음 — 화면이 권한
있는 API로 다시 읽는다). 느린 화면·다시 연결은 {"table": "*", "op": "RESYNC"} → connection 사건 (화면이 전부 다시 부름).
"""
from __future__ import annotations

from .permissions import PermissionTable, doc_viewable

TABLE_EVENTS = {
    "equipment_state_log": ("state_changed",),
    "wip_log": ("wip_changed",),
    "bottleneck_log": ("bottleneck_changed",),
    "alarm_event": ("alarm",),
    "document_revision": ("document_changed",),
    "work_record": ("kpi_updated", "document_changed"),    # 작업기록서 확정 → MTTR 등 다시 계산 (MNT-11)
}


def event_names(payload: dict) -> list[str]:
    table, op = payload.get("table"), payload.get("op")
    if op == "RESYNC":
        return ["connection"]
    if table == "notification":
        urgent = op == "INSERT" and payload.get("importance") == "URGENT"
        return ["urgent_popup", "notification"] if urgent else ["notification"]
    return list(TABLE_EVENTS.get(table, ("change",)))


# 역할별로 거르기 (기획서 13장, NFR-SEC-05). 사건에는 내용이 없지만, 볼 수 없는 것의 신호(특히 긴급 팝업)도 보내지 않는다
LIVE_VIEW = (("LINE_VIEW", "VIEW"), ("FIELD_VIEW", "VIEW"))
LIVE_EVENTS = {"state_changed", "wip_changed", "bottleneck_changed", "alarm", "change"}


def visible_events(payload: dict, role_code: str, table: PermissionTable, received: bool = False) -> list[str]:
    """이 사용자에게 보낼 사건 이름. received = 이 알림을 받은 사람인가 (알림 사건일 때만 의미 있음)
      · 알림: 받은 사람만. MGR은 모든 알림 목록이 바뀐 것은 받지만 긴급 팝업은 자기가 받은 것만
      · 문서: 그 문서를 볼 수 있는 역할만 (문서함과 같은 규칙) / 지표: KPI 보기 / 라인 상태: 3D 라인 뷰·현장 보기
    """
    names = event_names(payload)
    if payload.get("op") == "RESYNC":
        return names
    if payload.get("table") == "notification":
        if not table.allows(role_code, "NOTIFICATION", "VIEW"):
            return []
        if received:
            return names
        return ["notification"] if role_code == "MGR" else []
    doc_type = "WORK_RECORD" if payload.get("table") == "work_record" else payload.get("doc_type")
    out = []
    for name in names:
        if name in LIVE_EVENTS:
            ok = table.any_of(role_code, *LIVE_VIEW)
        elif name == "kpi_updated":
            ok = table.allows(role_code, "KPI", "VIEW")
        elif name == "document_changed":
            ok = doc_viewable(table, role_code, doc_type, payload.get("id"))
        else:
            ok = True
        if ok:
            out.append(name)
    return out
