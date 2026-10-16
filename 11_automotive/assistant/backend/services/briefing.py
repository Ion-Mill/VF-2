"""교대 시작 브리핑 (AST-01 `GET /api/assistant/briefing`, UI설계서 SCR-02·03, FR-AST-01-01~07·FR-AST-COM-21, 2026-10-11 멈춤 ④ P3).

- 화면이지 문서가 아니다: 저장·확정·수정 이력이 없다 (FR-AST-01-01). 승인·정비·설비 조작을 하지 않는다.
- 프로그램이 문제를 **전부** 모아 보고 순위대로 정렬한다 — 알림 목록과 같은 묶기·순위(notifications.rank_lines).
  전체 N = 같은 설비·같은 원인을 묶은 뒤 줄 수, 0-1은 "주의"에 센다, 순위 0·0-1·1은 접지 않는다, 빈 순위는 "-".
- 문장은 정해진 기본 문구다(message_source = "기본 문구"). 비서(LLM)는 부르지 않는다 — 비서 문장 다듬기는 화면을 만든 뒤
  따로 스위치로 붙인다. 그래서 비서가 꺼져도 같은 목록·같은 순서다 (FR-AST-02-14, UI설계서 SCR-02 "비서 응답 없음").
- 데이터가 없는 칸은 지어내지 않는다: 잠금·표지 체크 기록, 목표 미달·병목·납기, 품질, 승인 대기, 교대 보고서 확정 요청,
  속도 손실, 이번 교대 실적은 '데이터 없음'·not_built로 밝힌다.
- 칸 이름은 논리 ERD를 따른다: target_qty(교대 목표)·carry_over_qty(이월)·total_target_qty(총 목표)·actual_qty(실적 = GQ + RQ)·
  defect_qty(불량)·failure_loss_qty·speed_loss_qty(손실 추정).
- 총 목표는 지난 교대·이번 교대 모두 규칙(FR-PRD-01-15)대로 센다. 가상 데이터의 교대 보고서 목표 칸에는 이월이 빠져 있어
  (야간도 늘 90) 그 값은 report_target_qty·target_note로 따로 보인다 (불일치 기록, 2026-10-11).
- 전체형(SUP·MNT·MGR)은 알림 받는 사람과 상관없이 모은 문제 전부, 작업자 요약형(OPR·MGR)은 내 공정 것만 5줄.
- 지금 교대만 만든다 [제안]: 알림은 시연 시계 '지금' 기준이라, 다른 교대 번호를 주면 INVALID_STATE.
"""
from __future__ import annotations

from datetime import datetime

from backend.auth.permissions import NotLoggedIn, PermissionDenied, normalize_role, require
from backend.config import targets
from backend.errors import ApiError
from backend.repositories.csv_repo import get_repo
from backend.services import metrics as M
from backend.services import notifications as N
from backend.services import shift_reports as SR
from backend.services import shifts as SH
from backend.services.cite import cite
from backend.services.report_rank import RANKS, SUMMARY_GROUPS

MESSAGE_SOURCE = "기본 문구"
RANK0_LINE = "잠금·표지 중인 설비: 데이터 없음 — 잠금·표지 체크 기록(작업기록서 체크 칸)을 아직 만들지 않았습니다"
NOT_BUILT = [
    "순위 0 잠금·표지 중인 설비 — 체크 기록 데이터 없음",
    "순위 2 목표 미달 위험·병목·로트 납기 지연 — 실시간 생산 흐름이 없어 알림을 만들지 않음",
    "품질(관리도·CMM 판정 불일치·결과 파일 오류·보류·강화 검사 로트) — 권장 기능, 아직 없음",
    "승인 대기 문서·교대 보고서 확정 요청·문서 수정 알림 — 작업지시서·보고서 화면이 없어 아직 없음",
    "지금 DOWN인 설비 — 시연 시각의 설비 상태 기록 없음 (가상 데이터는 9/30까지)",
    "속도 손실·이번 교대 실적 — 데이터 없음",
]
OP_ALARM_KINDS = {"alarm_stop", "alarm_warning"}   # SCR-03 [3] 내 공정 알람 = 처리 안 된 긴급·주의 알람


def _row(table: str, key: str, value: str) -> dict | None:
    return next((r for r in get_repo().table(table) if r[key] == value), None)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _sources(*secs: str) -> list[dict]:
    return [c for c in (cite("DOC-07", s) for s in secs) if c]


def _counts_text(total: int, counts: dict) -> str:
    return f"전체 {total}건 (" + " · ".join(f"{name} {counts[name] if counts[name] else '-'}" for name, _ in SUMMARY_GROUPS) + ")"


def _priorities(notes: list[dict]) -> dict:
    rep = N.rank_lines(notes)
    by_id = {n["id"]: n for n in notes}
    items = []
    for line in rep["lines"]:
        members = [by_id[i] for i in line["ids"]]
        top = members[0]
        items.append({
            "rank": line["rank"], "rank_name": line["rank_name"], "title": line["title"], "count": line["count"],
            "folded": line["folded"], "occurred_at": top["occurred_at"], "equipment_id": top["equipment_id"],
            "process": top["process"], "sentence": top["sentence"], "related": top["related"],
            "records": sorted({rec for m in members for rec in m["records"]}),        # 기록 번호 링크 (FR-AST-01-05)
            "links": top["links"], "evidence": top["evidence"], "notification_ids": line["ids"],
            "over_24h": any(m["over_24h"] for m in members), "rule_tag": top["rule_tag"], "is_synthetic": True,
        })
    ranks = []
    for r, name in RANKS:
        mine = [it for it in items if it["rank"] == r]
        row = {"rank": r, "rank_name": name, "count": len(mine), "count_text": str(len(mine)) if mine else "-",
               "items": [it["notification_ids"][0] for it in mine]}
        if r == "0":
            row.update(data_status="데이터 없음", line=RANK0_LINE)
        if r == "2" and not mine:
            row.update(data_status="만들지 않음", line="생산 위험(목표 미달·병목·납기) 알림은 아직 만들지 않았습니다")
        ranks.append(row)
    return {"total": rep["total"], "counts": rep["counts"], "header": _counts_text(rep["total"], rep["counts"]),
            "ranks": ranks, "items": items, "not_built": NOT_BUILT}


def _tool_text(n: dict) -> str:
    """공구 수명 알림 제목 "공구 수명 92% — T05 M6 탭" → "VF2-01 T05 M6 탭 92%" (SCR-03 [4])."""
    head, _, tool = n["title"].partition(" — ")
    return f"{n['equipment_id']} {tool} {head.removeprefix('공구 수명 ')}".strip()


def _alarm_text(items: list[dict]) -> str:
    """SCR-03 [3] 내 공정 알람 한 줄 — 개수를 자르지 않는다 (전부 보고, FR-AST-COM-21)."""
    if not items:
        return "없음"
    each = "; ".join(f"{it['equipment_id']} {it['title']}" + (f" ({it['count']}건 묶음)" if it["count"] > 1 else "")
                     + (" · 24시간 넘게 처리 안 됨" if it["over_24h"] else "") for it in items)
    return f"전체 {len(items)}건 — {each}"


def _stops_text(row: dict) -> str:
    ids = [s for s in (row["required_stop_ids"] or "").split(";") if s]
    by_eq: dict[str, list[float]] = {}
    for sid in ids:
        d = _row("downtime", "downtime_id", sid)
        if d:
            by_eq.setdefault(d["equipment_id"], []).append(float(d["minutes"]))
    if not ids:
        return "필수 정지(고장 5분 이상) 없음"
    parts = [f"{eq} {len(m)}번 {sum(m):g}분" for eq, m in sorted(by_eq.items())]
    return f"필수 정지 {len(ids)}번 {float(row['required_stop_min']):g}분 ({', '.join(parts)}) → 고장 손실 약 {row['loss_qty_est']}개 (추정)"


def _targets_for(state, sid: str) -> dict:
    """교대 총 목표 = 교대 목표 + 이월 (FR-PRD-01-15). 이월은 야간만, 같은 생산일 주간 교대 보고서의 실적으로 센다.
    주간 보고서가 미확정이면 이월도 잠정이다 (UI설계서 SCR-02 경고). 브리핑의 지난 교대·이번 교대가 같은 계산을 쓴다."""
    t = targets()
    kind = SH.kind_of(sid)
    day_actual, prov = None, False
    if kind == "N":
        day = SH.day_shift_of(sid)
        drow = _row("shift_report", "shift_id", day)
        if drow:
            day_actual = int(drow["output"])
            prov = SR.current(state, day)["is_provisional"]
    carry = M.carry_over_qty(kind, day_actual, t["shift"])
    return {"target_qty": t["shift"], "carry_over_qty": carry, "total_target_qty": t["shift"] + carry,
            "daily_target_qty": t["day"], "day_actual_qty": day_actual, "carry_over_is_provisional": prov}


def _last_shift(state, sid: str) -> dict:
    prev = SH.prev_shift(sid)
    row = _row("shift_report", "shift_id", prev)
    base = {"shift_id": SH.to_spec(prev), "shift_key": prev, "shift_name": SH.name_of(prev), "is_synthetic": True,
            "speed_loss_qty": None, "evidence": _sources("4.3", "5.3", "5.4")}
    if row is None:
        return {**base, "data_status": "데이터 없음", "is_provisional": None,
                "lines": [f"{SH.name_of(prev)} 교대 보고서 없음 (데이터 없음)", "-", "-"], "records": []}
    cur = SR.current(state, prev)
    prov = cur["is_provisional"]
    tg = _targets_for(state, prev)
    actual, defect, report_target = int(row["output"]), int(row["scrap"]), int(row["target"])
    total = tg["total_target_qty"]
    tag = " (잠정 — 교대 보고서 미확정)" if prov else ""
    target_text = f"총 목표 {total}개" + (" (이월 잠정)" if tg["carry_over_is_provisional"] else "") + f" 대비 {actual - total:+d}개"
    if SH.kind_of(prev) == "D":
        day_note = f"이번 야간 이월 {M.carry_over_qty('N', actual, tg['target_qty'])}개"
    elif tg["day_actual_qty"] is None:
        day_note = "하루 실적: 그날 주간 교대 보고서 없음"
    else:   # 야간이 못 채운 수량은 다음 날로 넘기지 않고 그날 하루 부족으로 남는다 (FR-PRD-01-15)
        day_total, daily = tg["day_actual_qty"] + actual, tg["daily_target_qty"]
        day_note = f"하루 {day_total} / {daily}개" + (f" ({daily - day_total}개 부족 — 다음 날로 넘기지 않음)" if day_total < daily else "")
    lines = [
        f"양품 {actual}개 · 고장 손실 약 {row['loss_qty_est']}개 (추정, 속도 손실은 데이터 없음){tag}",
        f"{_stops_text(row)} · {target_text} · {day_note}",
        f"불량 {defect}개 · 순간 정지 {row['micro_stop_count']}번 {float(row['micro_stop_min']):g}분 · 교대 보고서 {row['report_id']} {cur['status']}",
    ]
    out = {**base, "report_id": row["report_id"], "status": cur["status"], "is_provisional": prov, **tg,
           "report_target_qty": report_target, "actual_qty": actual, "defect_qty": defect,
           "failure_loss_qty": int(row["loss_qty_est"]),
           "required_stop_ids": [s for s in (row["required_stop_ids"] or "").split(";") if s],
           "required_stop_min": float(row["required_stop_min"]), "micro_stop_count": int(row["micro_stop_count"]),
           "micro_stop_min": float(row["micro_stop_min"]), "lines": lines, "records": [row["report_id"]]}
    if report_target != total:   # 가상 데이터의 교대 보고서 목표 칸에는 이월이 빠져 있다 (불일치 기록, 2026-10-11)
        out["target_note"] = f"교대 보고서의 목표 칸은 {report_target}개 — 이월이 빠진 값이라 규칙(FR-PRD-01-15)대로 다시 셈"
    return out


def _this_shift(state, sid: str) -> dict:
    tg = _targets_for(state, sid)
    start, end = SH.window(sid)
    orders = [o for o in get_repo().table("production_order") if o["start_shift"] == sid]
    lots = [l for l in get_repo().table("production_lot") if l["shift_id"] == sid]
    pm = sorted((p for p in get_repo().table("pm_schedule")
                 if p["frequency"] == "계획" and "T" in p["next_due"] and start <= _dt(p["next_due"]) < end),
                key=lambda p: p["next_due"])
    line1 = (f"총 {tg['total_target_qty']}개 (목표 {tg['target_qty']} + 이월 {tg['carry_over_qty']})"
             + (" — 이월 잠정 (주간 교대 보고서 미확정)" if tg["carry_over_is_provisional"] else ""))
    if orders:
        each = ", ".join(o["order_id"] + " " + o["qty"] + "개" for o in orders)
        order_text = f"작업지시 {each} (이번 교대 {len(orders)}건)"
    else:
        order_text = "이번 교대에 시작하는 작업지시 없음"
    lot_text = f"로트 {len(lots)}개" if lots else "진행 중 로트: 데이터 없음 (가상 데이터는 9/30까지)"
    pm_text = ("예방 정비 " + ", ".join(f"{p['next_due'][11:16]} {p['equipment_id']} {p['item']}" for p in pm)) if pm else "이번 교대 예방 정비 계획 없음"
    return {"shift_id": SH.to_spec(sid), "shift_key": sid, "shift_name": SH.name_of(sid), "is_synthetic": True, **tg,
            "actual_qty": None, "actual_note": "이번 교대 실적은 생산 화면(3D 라인 뷰) 범위 — 데이터 없음",
            "production_orders": [{k: o[k] for k in ("order_id", "product", "qty", "due_date", "status")} for o in orders],
            "lots": [l["lot_id"] for l in lots],
            "pm_tasks": [{"pm_item_id": p["pm_item_id"], "equipment_id": p["equipment_id"], "item": p["item"],
                          "at": p["next_due"], "doc_section": p["doc_section"]} for p in pm],
            "lines": [line1, f"{order_text} · {lot_text}", pm_text],
            "records": [o["order_id"] for o in orders], "evidence": _sources("4.1", "8")}


def build(state, role: str, user_id: str | None, shift_id: str | None = None, view: str | None = None,
          process: str | None = None) -> dict:
    r = normalize_role(role)                                      # 역할 없음·모름 → UNAUTHORIZED
    u = state.user(user_id) if user_id else None
    if user_id and (u is None or u["role"] != r):
        raise NotLoggedIn()
    view = (view or ("operator" if r == "OPR" else "full")).lower()
    if view not in ("full", "operator"):
        raise ApiError("VALIDATION", "view는 full 또는 operator입니다", {"view": view})
    require(r, "view_briefing_full" if view == "full" else "view_briefing_operator")   # → FORBIDDEN
    now = state.now
    cur = SH.shift_id_of(now)
    sid = SH.to_internal(shift_id) if shift_id else cur
    if sid != cur:
        raise ApiError("INVALID_STATE", "브리핑은 지금 교대만 만듭니다 (지난 교대는 교대 보고서에서 봅니다)",
                       {"shift_id": SH.to_spec(sid), "current_shift_id": SH.to_spec(cur)})
    v = N.viewer(state, r, user_id)
    # 전체형(SUP·MNT·MGR)은 알림 받는 사람과 상관없이 프로그램이 모은 문제 전부 (FR-AST-01-02·04, SCR-02 그림의 T05 줄).
    # 작업자형은 그 작업자가 받는 알림 중 내 공정 것만 (SCR-03, FR-AST-01-07)
    notes = N.open_for(state, None if view == "full" else v)
    head = {"shift_id": SH.to_spec(sid), "shift_key": sid, "shift_name": SH.name_of(sid), "as_of": now.isoformat(),
            "view": view, "is_synthetic": True, "message_source": MESSAGE_SOURCE,
            # UI설계서 SCR-02의 "비서 정리 · 순서는 프로그램 규칙" 대신: 지금은 비서 문장이 아니라 기본 문구라 그대로 밝힌다
            "label": "프로그램 목록 · 기본 문구 · 순서는 프로그램 규칙 (보고 순위)"}
    this = _this_shift(state, sid)
    last = _last_shift(state, sid)
    if view == "full":
        return {**head, "priorities": _priorities(notes), "last_shift": last, "this_shift": this,
                "sources": _sources("10.5", "4.1", "4.3", "5.3")}
    # ---------------------------------------------------------- 작업자 요약형 (SCR-03, FR-AST-01-07): 5줄, 내 공정만
    eqs = {e["equipment_id"]: e["process"] for e in get_repo().master("equipment")}
    if process and process not in set(eqs.values()):
        raise ApiError("VALIDATION", "없는 공정입니다", {"process": process})
    if r == "OPR":
        own = {p for p in (u["assigned_process"].split(";") if u else []) if p}
        if not own:   # 담당 공정을 모르면 만들지 않는다 (X-User 없음)
            raise ApiError("VALIDATION", "작업자 요약은 X-User(담당 공정이 있는 작업자)가 필요합니다", {"user": user_id})
        if process and process not in own:
            raise PermissionDenied()                          # 남의 공정 → FORBIDDEN
        procs = {process} if process else own
    else:
        procs = {process} if process else set()               # MGR: 공정을 골라 본다 [제안], 안 고르면 전체 공정

    def in_mine(n: dict) -> bool:
        return not procs or n["process"] in procs

    alarms = N.rank_lines([n for n in notes if n["kind"] in OP_ALARM_KINDS and in_mine(n)])
    by_id = {n["id"]: n for n in notes}
    tools = [by_id[i] for line in N.rank_lines([n for n in notes if n["kind"] == "tool_90" and in_mine(n)])["lines"] for i in line["ids"]]
    pm_mine = [p for p in this["pm_tasks"] if not procs or eqs.get(p["equipment_id"]) in procs]
    alarm_items = [{"rank": l["rank"], "title": l["title"], "count": l["count"], "notification_ids": l["ids"],
                    "equipment_id": by_id[l["ids"][0]]["equipment_id"], "occurred_at": by_id[l["ids"][0]]["occurred_at"],
                    "over_24h": by_id[l["ids"][0]]["over_24h"], "links": by_id[l["ids"][0]]["links"]} for l in alarms["lines"]]
    good = last.get("actual_qty")
    lines = [
        {"no": 1, "label": "잠금·표지 중인 설비", "text": "데이터 없음 (잠금·표지 체크 기록을 아직 만들지 않음)", "data_status": "데이터 없음"},
        {"no": 2, "label": "지난 교대", "text": (f"양품 {good}개" + (" (잠정)" if last.get("is_provisional") else ""))
         if good is not None else "데이터 없음"},
        {"no": 3, "label": "내 공정 알람 (처리 안 됨)", "text": _alarm_text(alarm_items), "items": alarm_items},
        {"no": 4, "label": "공구 교체", "text": ", ".join(_tool_text(t) for t in tools) if tools else "없음",
         "items": [{"equipment_id": t["equipment_id"], "title": t["title"], "notification_id": t["id"]} for t in tools]},
        {"no": 5, "label": "이번 교대", "text": f"총 {this['total_target_qty']}개" + (
            " · " + ", ".join(f"{p['at'][11:16]} {p['equipment_id']} {p['item']}" for p in pm_mine) if pm_mine else " · 예방 정비 없음")},
    ]
    return {**head, "processes": sorted(procs) or ["전체 공정"], "lines": lines,
            "this_shift": {k: this[k] for k in ("total_target_qty", "target_qty", "carry_over_qty", "carry_over_is_provisional")},
            "sources": _sources("10.5", "4.1")}
