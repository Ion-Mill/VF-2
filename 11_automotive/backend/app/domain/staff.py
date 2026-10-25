"""직원 관리 (SCR-27, API-USR-01~05, 2026-10-25) — DB 없이 시험할 수 있는 계산·확인. 시연 서버 frontend/tools/server_staff.py와 같은 규칙.

- 업무 기록은 새로 쌓지 않는다 (FR-USR-01-10): 기존 표의 "누가" 칸을 모은 줄(app/sql/staff.sql events)을 센다.
- 채팅 기록은 읽지 않는다. 순위·점수는 만들지 않는다 (FR-USR-01-11).
- 직원 추가·정보 고치기·사용 중지·비밀번호 다시 정하기(USR-04·05)는 1025 백엔드 요청 3장 [제안]. 지우기는 없다 (6.53 USER).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from ..errors import AppError, validation

PROCS = ("OP-10", "OP-20", "OP-30", "OP-40", "OP-50")
ROLES = ("OPR", "MNT", "SUP", "MGR")
SHIFTS = ("DAY", "NIGHT")
USER_ID = re.compile(r"^[A-Za-z0-9_]{2,20}$")     # DB 제약 app_user.user_id와 같음
NAME_MAX = 40                                     # app_user.user_name varchar(40)
PASSWORD_MAX = 128                                # 아주 긴 글로 비밀번호 계산(scrypt)을 오래 붙잡지 않게
FIELDS = ("user_name", "role_code", "home_shift_type", "home_process_code", "home_process_code_2", "is_active")

# 역할별 숫자 4칸 (FR-USR-01-07): (이름, 단위, 세는 방법) — 세는 방법 = 일 종류 건수 또는 ("sum", 종류, 칸) / ("rate", 종류)
KPIS = {
    "OPR": [("생산 수량", "개", ("sum", "prod", "pq")), ("양품률", "%", ("rate", "prod")), ("공구 교체", "번", "tool"),
            ("정지 사유 입력", "건", "reason_in")],
    "MNT": [("맡은 작업지시", "건", "wo_assign"), ("작업기록 확정", "건", "wr_confirm"),
            ("수리 시간 합계", "분", ("sum", "wr_confirm", "minutes")), ("예방 정비 실시", "건", "pm_done")],
    "SUP": [("작업지시 승인", "건", "wo_approve"), ("정지 사유 확정", "건", "reason_ok"), ("교대 보고서 확정", "건", "shift_ok"),
            ("로트 보류", "건", "hold")],
    "MGR": [("일일 보고서 확정", "건", "daily_ok"), ("폐기 승인", "건", "scrap_ok"), ("설정 변경", "건", "setting"),
            ("문서 수정", "건", "doc_edit")],
}


def on(v) -> bool:
    """DB 참/거짓 (psycopg = bool, 시험 psql = 't'/'f')"""
    return v is True or v in ("t", "true")


def _num(v) -> float:
    """DB 숫자 (psycopg = Decimal, 시험 psql = 글자). 비면 0"""
    return float(v) if v not in (None, "") else 0.0


def period_range(period: str, now: datetime, start: datetime | None = None) -> tuple[datetime, datetime]:
    """기간 칩 (FR-USR-01-09, 처음 값 7일). 끝 = 지금(시연 시계).
    today = 오늘 0시부터, 7d·30d = 지금부터 거꾸로, all = 기록 시작(start)부터 (2026-10-25 — 10월 데이터에서 sep가 비어서),
    sep = 9월 전체(9/1~10/1, 옛 값 그대로 받음)"""
    if period == "sep":
        return datetime(2026, 9, 1, tzinfo=now.tzinfo), datetime(2026, 10, 1, tzinfo=now.tzinfo)
    if period == "all":
        return min(start or now, now), now
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    return now - timedelta(days={"30d": 30}.get(period, 7)), now


def kpis(role: str, evs: list[dict]) -> list[dict]:
    """역할별 숫자 4칸. 평균은 쓰지 않고 합계만 (양품률만 비율, 생산이 없으면 null)."""
    out = []
    for label, unit, how in KPIS.get(role, []):
        if isinstance(how, str):
            v = sum(1 for e in evs if e["kind"] == how)
        elif how[0] == "sum":
            v = round(sum(_num(e.get(how[2])) for e in evs if e["kind"] == how[1]), 1)
            v = int(v) if v == int(v) else v
        else:
            pq = sum(_num(e.get("pq")) for e in evs if e["kind"] == how[1])
            v = round(sum(_num(e.get("gq")) for e in evs if e["kind"] == how[1]) * 100 / pq, 1) if pq else None
        out.append({"label": label, "value": v, "unit": unit})
    return out


def procs_of(u: dict) -> list[str]:
    return [p for p in (u.get("home_process_code"), u.get("home_process_code_2")) if p]


def board(users: list[dict]) -> tuple[list[dict], list[str]]:
    """배치표 줄(공정 5 · 보전 · 반장) × 주간·야간 칸 (사용 중인 직원만), 담당 0명인 공정 칸 이름 (주의는 공정만, FR-USR-01-03)."""
    users = [u for u in users if on(u.get("is_active", True))]
    rows, empty = [], []
    for p in PROCS:
        cells = {s: [u["user_id"] for u in users if u["role_code"] == "OPR" and p in procs_of(u) and u["home_shift_type"] == s]
                 for s in SHIFTS}
        rows.append({"row": p, "role": "OPR", "cells": cells})
        empty += [f"{'주간' if s == 'DAY' else '야간'} {p}" for s, ids in cells.items() if not ids]
    for row, role in (("보전", "MNT"), ("반장", "SUP")):
        rows.append({"row": row, "role": role,
                     "cells": {s: [u["user_id"] for u in users if u["role_code"] == role and u["home_shift_type"] == s] for s in SHIFTS}})
    return rows, empty


def _procs(role: str, procs: list, who: str) -> list[str]:
    procs = [str(p).strip() for p in procs if p and str(p).strip()]
    if procs and role != "OPR":
        raise validation(f"{who}: 담당 공정은 작업자(OPR)만", reason="PROCESS_ROLE")
    if len(procs) > 2 or len(set(procs)) != len(procs) or any(p not in PROCS for p in procs):
        raise validation(f"{who}: 담당 공정은 {PROCS[0]}~{PROCS[-1]} 중 서로 다른 2개까지", reason="PROCESS")
    return procs


def _shift(v, role: str, who: str) -> str | None:
    """담당 교대: 주간·야간. 관리자만 비워 둘 수 있다 (배치표에 줄이 없음)"""
    v = v or None
    if v is None and role != "MGR":
        raise validation(f"{who}: 담당 교대가 필요함 (주간 DAY·야간 NIGHT)", reason="SHIFT")
    if v is not None and v not in SHIFTS:
        raise validation(f"{who}: 담당 교대는 주간(DAY)·야간(NIGHT)만", reason="SHIFT")
    return v


def wanted_procs(change: dict, cur: dict) -> list | None:
    """바꿀 담당 공정 목록. procs(목록 — 화면이 보내는 모양) 또는 home_process_code·home_process_code_2(명세 칸, 비우려면 "").
    둘 다 안 보냈으면 None"""
    if change.get("procs") is not None:
        return list(change["procs"])
    if "home_process_code" in change or "home_process_code_2" in change:
        return [change.get("home_process_code", cur.get("home_process_code")),
                change.get("home_process_code_2", cur.get("home_process_code_2"))]
    return None


def _set_procs(new: dict, procs: list[str]) -> None:
    new["home_process_code"], new["home_process_code_2"] = (procs + [None, None])[:2]


def check_assignment(u: dict, change: dict) -> dict:
    """배치 바꾸기 한 사람 (API-USR-03, FR-USR-01-04) → 바뀐 뒤 칸 전부. 역할·사용 여부는 여기서 바꾸지 않는다."""
    who = u["user_name"]
    if not on(u.get("is_active")):
        raise validation(f"{who}: 사용 중지된 직원은 배치를 바꾸지 않음", reason="INACTIVE")
    new = {f: u.get(f) for f in FIELDS}
    new["home_shift_type"] = _shift(change.get("home_shift_type", u.get("home_shift_type")), u["role_code"], who)
    procs = wanted_procs(change, u)
    _set_procs(new, _procs(u["role_code"], procs_of(u) if procs is None else procs, who))
    return new


def check_name(v) -> str:
    name = str(v or "").strip()
    if not 1 <= len(name) <= NAME_MAX:
        raise validation(f"이름은 1~{NAME_MAX}자", reason="NAME")
    return name


def check_password(v, min_length: int) -> str:
    pw = str(v or "")
    if not min_length <= len(pw) <= PASSWORD_MAX:
        raise validation(f"비밀번호는 {min_length}~{PASSWORD_MAX}자", reason="PASSWORD")
    return pw


def check_role(v) -> str:
    if v not in ROLES:
        raise validation("역할은 OPR·MNT·SUP·MGR 중 하나", reason="ROLE")
    return v


def next_user_id(ids) -> str:
    """비운 아이디 = U + 다음 번호 (두 자리 이상, 예: U12 다음 U13)"""
    nums = [int(m.group(1)) for i in ids if (m := re.fullmatch(r"U(\d+)", str(i)))]
    return f"U{max(nums, default=0) + 1:02d}"


def new_user(body: dict, ids, min_length: int) -> dict:
    """직원 추가 (API-USR-04) 값 확인 → 넣을 칸 + password(원문 — 서버가 해시만 저장). 아이디가 이미 있으면 409 DUPLICATE"""
    ids = set(ids)
    uid = str(body.get("user_id") or "").strip() or next_user_id(ids)
    if not USER_ID.fullmatch(uid):
        raise validation("아이디는 영문·숫자·밑줄 2~20자", reason="USER_ID")
    if uid in ids:
        raise AppError(409, "INVALID_STATE", f"이미 있는 아이디: {uid}", {"reason": "DUPLICATE"})
    name, role = check_name(body.get("user_name")), check_role(body.get("role_code"))
    new = {"user_id": uid, "user_name": name, "role_code": role, "home_shift_type": _shift(body.get("home_shift_type"), role, name),
           "is_active": True}
    _set_procs(new, _procs(role, wanted_procs(body, {}) or [], name))
    new["password"] = check_password(body.get("password"), min_length)
    return new


def updated_user(cur: dict, change: dict, actor_id: str, active_mgrs, min_length: int) -> dict:
    """직원 정보 고치기 (API-USR-05, 설정 SET-03) → 바뀐 뒤 칸 전부 + password(새 비밀번호 또는 None).
    change에는 보낸 칸만 (비우려는 공정은 "" 또는 procs []). 역할을 작업자가 아닌 것으로 바꾸면 담당 공정 두 칸을 비운다
    (DB 제약 ck_app_user_process_2). 지금 로그인한 관리자는 자기 자신을 사용 중지하거나 MGR이 아닌 역할로 바꾸지 못하고,
    사용 중인 MGR이 0명이 되는 변경은 거절한다."""
    new = {f: cur.get(f) for f in FIELDS}
    new["is_active"] = on(cur.get("is_active"))
    if change.get("user_name") is not None:
        new["user_name"] = check_name(change["user_name"])
    if change.get("role_code") is not None:
        new["role_code"] = check_role(change["role_code"])
    if change.get("is_active") is not None:
        new["is_active"] = bool(change["is_active"])
    who = new["user_name"]
    new["home_shift_type"] = _shift(change.get("home_shift_type", new["home_shift_type"]), new["role_code"], who)
    procs = wanted_procs(change, cur)
    if procs is None:
        procs = procs_of(cur) if new["role_code"] == "OPR" else []
    _set_procs(new, _procs(new["role_code"], procs, who))
    if cur["user_id"] == actor_id and (not new["is_active"] or new["role_code"] != "MGR"):
        raise validation("자기 자신은 사용 중지하거나 관리자가 아닌 역할로 바꿀 수 없음", reason="SELF")
    mgrs = set(active_mgrs)
    if cur["user_id"] in mgrs and not (new["is_active"] and new["role_code"] == "MGR") and not mgrs - {cur["user_id"]}:
        raise validation("사용 중인 관리자(MGR)가 0명이 됨", reason="LAST_MGR")
    new["password"] = None if change.get("password") is None else check_password(change["password"], min_length)
    return new


def _text(field: str, v) -> str | None:
    if field == "is_active":
        return "true" if on(v) else "false"
    return None if v in (None, "") else str(v)


def diff(cur: dict, new: dict) -> list[dict]:
    """수정 이력 바뀐 칸 (field·before·after 글자). cur가 비면 새 직원 (전 = 모두 없음).
    비밀번호는 값 없이 "비밀번호 바꿈" 한 줄만"""
    def before(f):
        return _text(f, cur.get(f)) if cur else None

    out = [{"field": f, "before": before(f), "after": _text(f, new.get(f))}
           for f in FIELDS if before(f) != _text(f, new.get(f))]
    if new.get("password"):
        out.append({"field": "password", "before": None, "after": "비밀번호 바꿈" if cur else "비밀번호 정함"})
    return out


def public(u: dict) -> dict:
    """응답·수정 이력에 싣는 칸 (비밀번호·해시는 싣지 않음)"""
    return {"user_id": u.get("user_id"), **{f: u.get(f) for f in FIELDS}}
