"""직원 관리 (SCR-27, API-USR-01~03, 2026-10-23) — 시연 서버 쪽 계산.

- 업무 기록은 새로 쌓지 않는다 (FR-USR-01-10): 9월 기록(생성기 out/ CSV)과 10/1 실시간 기록의 "누가" 칸을 사람별로 모은다.
  측정값 확인·수동 입력(inspection_result.checked_by·entered_by)은 생성기가 비워 두어 9월 기록에 없다.
- 채팅 기록(chat_log)은 읽지 않는다. 순위·점수는 만들지 않는다 (FR-USR-01-11).
- 배치(담당 교대·담당 공정)를 바꾸면 덮어쓴 값만 따로 들고, 사람마다 수정 이력(APP_USER)을 남긴다 (FR-USR-01-04·05).
"""
from __future__ import annotations

from datetime import datetime, timedelta

PROCS = ["OP-10", "OP-20", "OP-30", "OP-40", "OP-50"]
# 역할별 숫자 4칸 (요구사항 FR-USR-01-07): (이름, 단위, 세는 방법) — 세는 방법 = 일 종류 건수 또는 ("sum", 종류, 칸)
KPIS = {
    "OPR": [("생산 수량", "개", ("sum", "prod", "pq")), ("양품률", "%", ("rate", "prod")), ("공구 교체", "번", "tool"), ("정지 사유 입력", "건", "reason_in")],
    "MNT": [("맡은 작업지시", "건", "wo_assign"), ("작업기록 확정", "건", "wr_confirm"), ("수리 시간 합계", "분", ("sum", "wr_confirm", "min")), ("예방 정비 실시", "건", "pm_done")],
    "SUP": [("작업지시 승인", "건", "wo_approve"), ("정지 사유 확정", "건", "reason_ok"), ("교대 보고서 확정", "건", "shift_ok"), ("로트 보류", "건", "hold")],
    "MGR": [("일일 보고서 확정", "건", "daily_ok"), ("폐기 승인", "건", "scrap_ok"), ("설정 변경", "건", "setting"), ("문서 수정", "건", "doc_edit")],
}
DOC_KO = {"WORK_ORDER": "작업지시서", "WORK_RECORD": "작업기록서", "SHIFT_REPORT": "교대 보고서", "DAILY_REPORT": "일일 보고서",
          "INTERNAL_DOC": "사내 문서", "PM_RECORD": "예방 정비 기록", "SHIPMENT": "출하 기록", "APP_USER": "직원 배치"}
TXN_KO = {"IN": "입고", "USE": "사용", "ADJUST": "실사 조정", "SHIP": "출하", "FG_IN": "완제품 입고"}


def _t(v):
    if not v:
        return None
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))


def _ev(out, who, at, kind, text, screen=None, key=None, **n):
    at = _t(at)
    if who and at:
        out.append({"user": who, "at": at, "kind": kind, "text": text, "screen": screen, "key": key, **n})


def past_events(P, read_csv) -> list[dict]:
    """9월 기록 (한 번만 만들어 둔다)."""
    out: list[dict] = []
    for r in read_csv("operation_report"):
        _ev(out, r["worker_user_id"], r["start_at"], "prod", f"{r['process_code']} 실적 {r['pq']}개 · {r['lot_no']}", "lots", r["lot_no"],
            pq=int(r["pq"] or 0), gq=int(r["gq"] or 0))
    for r in read_csv("equipment_state_log"):
        what = f"{r['equipment_id']} {r['reason_code'] or r['reason_suggested_code']}"
        _ev(out, r["reason_entered_by"], r["start_at"], "reason_in", f"정지 사유 입력 · {what}")
        _ev(out, r["reason_confirmed_by"], r["reason_confirmed_at"], "reason_ok", f"정지 사유 확정 · {what}")
    for r in P.tool_changes:
        _ev(out, r["changed_by"], r["changed_at"], "tool", f"공구 교체 · {r['tool_id']}", "tools", r["tool_id"][:6])
    for r in P.work_orders:
        _ev(out, r["assignee_user_id"], r["created_at"], "wo_assign", f"작업지시서 담당 · {r['wo_no']} {r['equipment_id']}", "docs", "작업지시서")
        _ev(out, r["approved_by"], r["approved_at"], "wo_approve", f"작업지시서 승인 · {r['wo_no']}", "docs", "작업지시서")
    for r in P.work_records:
        name = "간이 작업기록" if r["record_type"] != "FULL" else "작업기록서"
        _ev(out, r["confirmed_by"], r["confirmed_at"], "wr_confirm", f"{name} 확정 · {r['record_no']} {r['equipment_id']}", "docs", name,
            min=int(float(r["repair_min"] or 0)))
        _ev(out, r["checked_by"], r["checked_at"], "wr_check", f"{name} 확인 · {r['record_no']}", "docs", name)
    for r in P.pm_rows:
        _ev(out, r["done_by"], r["done_at"], "pm_done", f"예방 정비 실시 · {r['pm_task_id']}", "pm")
        if r["recorded_by"] != r["done_by"]:
            _ev(out, r["recorded_by"], r["done_at"], "pm_rec", f"예방 정비 기록 · {r['pm_task_id']}", "pm")
    for r in P.defects:
        _ev(out, r["recorded_by"], r["found_at"], "defect", f"불량 기록 · {r['lot_no']} {r['defect_code']} {r['qty']}개", "quality", r["lot_no"])
    for r in P.holds:
        _ev(out, r["held_by"], r["held_at"], "hold", f"로트 보류 · {r['lot_no']}", "lots", r["lot_no"])
        _ev(out, r["released_by"], r["released_at"], "release", f"로트 해제 · {r['lot_no']}", "lots", r["lot_no"])
        _ev(out, r["scrap_approved_by"], r["scrap_approved_at"], "scrap_ok", f"폐기 승인 · {r['lot_no']} {r['scrap_proposed_qty']}개", "lots", r["lot_no"])
    for r in P.inv_txns:
        _ev(out, r["txn_by"], r["txn_at"], "inv", f"재고 {TXN_KO.get(r['txn_type'], r['txn_type'])} · {r['item_no']} {r['qty_change']}", "inventory")
    for r in P.shipments:
        _ev(out, r["confirmed_by"], r["shipped_at"], "ship", f"출하 확인 · {r['shipment_no']}", "inventory")
    for r in P.shift_reports:
        _ev(out, r["confirmed_by"], r["confirmed_at"], "shift_ok", f"교대 보고서 확정 · {r['shift_id']}", "shift", r["shift_id"])
    for r in P.daily_reports:
        _ev(out, r["confirmed_by"], r["confirmed_at"], "daily_ok", f"일일 보고서 확정 · {r['work_date']}", "daily", r["work_date"])
    for r in P.revisions:
        if r["author_kind"] != "AI":
            _ev(out, r["author_user_id"], r["created_at"], "doc_edit", f"문서 수정 · {DOC_KO.get(r['doc_type'], r['doc_type'])} {r['doc_key']} v{r['version_no']}", "revs")
    return out


def live_events(S, rt) -> list[dict]:
    """10/1 시연 중에 생긴 것 (부를 때마다 새로). 9월 기록과 겹치지 않게 10/1 08:00(rt.N) 뒤만."""
    out: list[dict] = []
    cal = rt.sim.cal
    for r in rt.sim.reports.values():
        if r["start_m"] >= rt.N and r.get("worker_user_id"):
            _ev(out, r["worker_user_id"], cal.to_dt(r["start_m"]), "prod", f"{r['process_code']} 실적 {r['pq']}개 · {r['lot_no']}", "lots", r["lot_no"],
                pq=int(r["pq"] or 0), gq=int(r["gq"] or 0))
    for r in rt.sim.tool_changes:
        if r["changed_m"] >= rt.N:
            _ev(out, r["changed_by"], cal.to_dt(r["changed_m"]), "tool", f"공구 교체 · {r['tool_id']}", "tools", r["tool_id"][:6])
    for r in rt.pm_rows:
        _ev(out, r["done_by"], r["done_at"], "pm_done", f"예방 정비 실시 · {r['pm_task_id']}", "pm")
    for l in rt.sim.lots:
        h = l.hold
        if h and h.get("held_m", -1) >= rt.N and h.get("lot") is l:
            _ev(out, h.get("held_by"), cal.to_dt(h["held_m"]), "hold", f"로트 보류 · {l.lot_no}", "lots", l.lot_no)
            if h.get("scrap_approved_by") and h.get("scrap_approved_m") is not None:
                _ev(out, h["scrap_approved_by"], cal.to_dt(h["scrap_approved_m"]), "scrap_ok", f"폐기 승인 · {l.lot_no}", "lots", l.lot_no)
    for r in S.revs:
        _ev(out, r.get("author_user_id"), r["created_at"], "doc_edit", f"문서 수정 · {DOC_KO.get(r['doc_type'], r['doc_type'])} {r['doc_key']} v{r['version_no']}", "revs")
    for d, r in S.daily.items():
        _ev(out, r.get("confirmed_by"), r.get("confirmed_at"), "daily_ok", f"일일 보고서 확정 · {d}", "daily", d)
    for sid, r in S.reports.items():
        if r.get("status") == "CONFIRMED":
            _ev(out, r.get("confirmed_by"), r.get("confirmed_at"), "shift_ok", f"교대 보고서 확정 · {sid}", "shift", sid)
    for r in S.ships:
        _ev(out, r.get("confirmed_by"), r["shipped_at"], "ship", f"출하 확인 · {r['shipment_no']}", "inventory")
    for r in S.settings_log:
        _ev(out, r.get("by"), r["at"], "setting", "설정 변경 · " + ", ".join(r.get("what", {}).keys()), "settings")
    return out


def period_range(period: str, now: datetime) -> tuple[datetime, datetime]:
    """오늘 · 7일 · 30일 · 9월 전체 (처음 값 7일, FR-USR-01-09). 끝 = 지금(시연 시계)."""
    if period == "sep":
        return datetime(2026, 9, 1, tzinfo=now.tzinfo), datetime(2026, 10, 1, tzinfo=now.tzinfo)
    if period == "all":   # 기록 전체 = 첫 교대부터 (화면 버튼 "기록 전체", 백엔드와 같은 값 2026-10-25). 생성기 기록은 9/1보다 앞서지 않는다
        return datetime(2026, 9, 1, tzinfo=now.tzinfo), now
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    days = {"30d": 30}.get(period, 7)
    return now - timedelta(days=days), now


def kpis(role: str, evs: list[dict]) -> list[dict]:
    """역할별 숫자 4칸. 평균은 쓰지 않고 합계만 (양품률만 비율)."""
    out = []
    for label, unit, how in KPIS.get(role, []):
        if isinstance(how, str):
            v = sum(1 for e in evs if e["kind"] == how)
        elif how[0] == "sum":
            v = sum(e.get(how[2], 0) for e in evs if e["kind"] == how[1])
        else:
            pq = sum(e.get("pq", 0) for e in evs if e["kind"] == how[1])
            v = round(sum(e.get("gq", 0) for e in evs if e["kind"] == how[1]) * 100 / pq, 1) if pq else None
        out.append({"label": label, "value": v, "unit": unit})
    return out


def users_now(P, assign: dict) -> list[dict]:
    """직원 명단에 배치 바꾼 값을 덮어쓴 것."""
    return [{**u, **assign.get(uid, {})} for uid, u in P.users.items()]


def board(users: list[dict]) -> tuple[list[dict], list[str]]:
    """배치표 줄(공정 5 · 보전 · 반장) × 주간·야간 칸, 담당 0명인 공정 칸 이름 (주의는 공정만, FR-USR-01-03)."""
    rows, empty = [], []
    for p in PROCS:
        cells = {s: [u["user_id"] for u in users if u["role_code"] == "OPR" and p in (u["home_process_code"], u["home_process_code_2"]) and u["home_shift_type"] == s]
                 for s in ("DAY", "NIGHT")}
        rows.append({"row": p, "role": "OPR", "cells": cells})
        empty += [f"{'주간' if s == 'DAY' else '야간'} {p}" for s, ids in cells.items() if not ids]
    for row, role in (("보전", "MNT"), ("반장", "SUP")):
        rows.append({"row": row, "role": role, "cells": {s: [u["user_id"] for u in users if u["role_code"] == role and u["home_shift_type"] == s] for s in ("DAY", "NIGHT")}})
    return rows, empty


def check_change(u: dict, c: dict) -> dict:
    """한 사람의 배치 바꾸기 값 확인 → 바꿀 칸만. 역할·사용 중은 바꾸지 않는다 (FR-USR-01-11). 틀리면 ValueError."""
    shift = c.get("home_shift_type", u["home_shift_type"])
    if shift not in ("DAY", "NIGHT"):
        raise ValueError(f"{u['user_name']}: 교대는 주간·야간만")
    procs = [p for p in (c["procs"] if "procs" in c else [u["home_process_code"], u["home_process_code_2"]]) if p]
    if u["role_code"] != "OPR" and procs:
        raise ValueError(f"{u['user_name']}: 담당 공정은 작업자만")
    if len(procs) > 2 or len(set(procs)) != len(procs) or any(p not in PROCS for p in procs):
        raise ValueError(f"{u['user_name']}: 담당 공정은 OP-10~50 중 2개까지")
    return {"home_shift_type": shift, "home_process_code": procs[0] if procs else "", "home_process_code_2": procs[1] if len(procs) > 1 else ""}


if __name__ == "__main__":
    # 작은 자체 시험: python -I server_staff.py
    u = {"user_name": "작업자 야간 1", "role_code": "OPR", "home_shift_type": "NIGHT", "home_process_code": "OP-10", "home_process_code_2": "OP-20"}
    assert check_change(u, {"procs": ["OP-10", "OP-30"]})["home_process_code_2"] == "OP-30"
    for bad in ({"procs": ["OP-10", "OP-20", "OP-30"]}, {"procs": ["OP-90"]}, {"home_shift_type": "EVE"}):
        try:
            check_change(u, bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    try:
        check_change({**u, "role_code": "MNT", "home_process_code": "", "home_process_code_2": ""}, {"procs": ["OP-10"]})
        raise AssertionError("MNT 공정")
    except ValueError:
        pass
    users = [{"user_id": "A", **u}, {"user_id": "B", **u, "home_shift_type": "DAY", "home_process_code": "OP-30", "home_process_code_2": ""}]
    rows, empty = board(users)
    assert rows[0]["cells"]["NIGHT"] == ["A"] and "주간 OP-10" in empty and "야간 OP-30" in empty and "주간 OP-30" not in empty
    ev = [{"kind": "prod", "pq": 10, "gq": 9}, {"kind": "prod", "pq": 10, "gq": 10}, {"kind": "tool"}]
    k = {x["label"]: x["value"] for x in kpis("OPR", ev)}
    assert k == {"생산 수량": 20, "양품률": 95.0, "공구 교체": 1, "정지 사유 입력": 0}, k
    from datetime import timezone
    now = datetime(2026, 10, 1, 10, 0, tzinfo=timezone(timedelta(hours=9)))
    assert period_range("7d", now)[0].day == 24 and period_range("today", now)[0].hour == 0 and period_range("sep", now)[1].month == 10
    assert period_range("all", now) == (datetime(2026, 9, 1, tzinfo=now.tzinfo), now)
    print("server_staff 자체 시험 통과")
