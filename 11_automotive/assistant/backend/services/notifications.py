"""AST-02 알림 (UI설계서 2.5·SCR-07, DOC-07 §10). 알릴지·중요도·보고 순위·받는 사람·처리 방식은 규칙이 정한다.

비서(LLM)는 알림 문장만 쓸 수 있다. 이 서비스의 알림 API는 기본 문구를 준다 (2.5 "비서가 꺼져도 알림은 기본 문구로").
시연 화면 알림 탭의 알람 상세 본문은 화면이 만든 기본 문장을 외부 Claude(`POST /compose/alarm_notice`, llm/compose.py)가 다듬는다 (2026-10-19, 실패하면 기본 문장 그대로).
비서는 알림을 처리하지 않는다 (FR-AST-COM-10). 처리는 아래 표의 사람만 한다.

이번 묶음에서 만들지 않는 알림 (원천 데이터·화면이 다음 묶음·범위 밖): 목표 미달·병목·납기(실시간 생산 흐름 없음),
승인 대기(묶음 B 작업지시서), 교대 보고서 확정 요청(묶음 C), 문서 수정(묶음 B), 관리도·CMM(범위 밖).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.auth.permissions import NotLoggedIn, PermissionDenied, normalize_role, require
from backend.config import DATA_LABEL, REFERENCE_AT
from backend.demo_state import DemoState
from backend.repositories.csv_repo import get_repo
from backend.services import metrics as M
from backend.services.cite import parse_refs
from backend.services.report_rank import Item, rank_report
from backend.tools import query_tools as T

# 알림 종류표 (UI설계서 SCR-07 "알림 종류별 받는 사람과 처리", 보고 순위 2.5). sub = 순위 3 안의 ①~⑤ 순서
KINDS = {
    "alarm_stop": {"label": "알람 발생 — 정지", "importance": "긴급", "rank": "1", "sub": 0,
                   "receivers": {"OPR", "MNT", "SUP"}, "process_roles": set(),
                   "auto": {"OP-30": "처리: 작업기록서 확정 때 자동", "other": "처리: 간이 작업기록 확정 때 자동"}},
    "alarm_warning": {"label": "알람 발생 — 주의", "importance": "주의", "rank": "3", "sub": 2,
                      "receivers": {"OPR", "MNT", "SUP"}, "process_roles": set(), "auto": "처리: 간이 작업기록 확정 때 자동"},
    "alarm_guide": {"label": "알람 발생 — 조작 안내", "importance": "참고", "rank": "4", "sub": 0,
                    "receivers": {"OPR"}, "process_roles": {"OPR", "SUP"}, "auto": None},
    "repeat_2": {"label": "반복 알람 2단계", "importance": "주의", "rank": "3", "sub": 0,
                 "receivers": {"MNT", "SUP"}, "process_roles": set(), "auto": "처리: 원인 점검 작업기록서 확정 때 자동"},
    "repeat_1": {"label": "반복 알람 1단계", "importance": "주의", "rank": "3", "sub": 1,
                 "receivers": {"MNT", "SUP"}, "process_roles": {"MNT", "SUP"}, "auto": None, "needs_plan": True},
    "tool_90": {"label": "공구 수명 90%", "importance": "주의", "rank": "3", "sub": 4,
                "receivers": {"OPR", "MNT"}, "process_roles": set(), "auto": "처리: 공구 교체 기록 때 자동"},
    "pm_overdue": {"label": "예방 정비 기한 넘김", "importance": "주의", "rank": "3", "sub": 4,
                   "receivers": {"MNT"}, "process_roles": set(), "auto": "처리: 실시 기록 저장 때 자동"},
    "inventory_short": {"label": "재고 부족", "importance": "주의", "rank": "3", "sub": 4,
                        "receivers": {"MGR"}, "process_roles": {"MGR"}, "auto": "입고 등록으로 안전 재고를 넘으면 자동"},
    "pm_due_tomorrow": {"label": "예방 정비 하루 전", "importance": "참고", "rank": "4", "sub": 0,
                        "receivers": {"MNT"}, "process_roles": set(), "auto": "처리: 실시 기록 저장 때 자동"},
}
SEVERITY_KIND = {"STOP": "alarm_stop", "WARNING": "alarm_warning", "GUIDE": "alarm_guide"}
SEVERITY_KO = {"STOP": "정지", "WARNING": "주의", "GUIDE": "조작 안내"}
HISTORY_DAYS = 7          # "전체" 탭에 보이는 처리된 알림 기간 [제안]
BUNDLE_WINDOW = timedelta(minutes=1)   # 1분 안 3번 이상 → 한 장 (DOC-07 §10.2)
BUNDLE_COUNT = 3
STORM_ON, STORM_OFF, STORM_WINDOW = 10, 5, timedelta(minutes=10)  # 10분 10건 넘으면 시작, 5건 아래면 풀림 [제안]
LONG_OPEN = timedelta(hours=24)  # 24시간 넘은 주의 알림 → 순위 0-1
VIRTUAL_RULE = "가상 규칙"
PLAN_MAX = 200


class NotFound(LookupError):
    pass


class ProcessError(ValueError):
    pass


class InvalidState(ProcessError):
    """지금 상태에서 처리할 수 없음 (이미 처리, 사람이 처리하지 않는 알림) → API 오류 INVALID_STATE (2026-10-11 P4)."""


class InvalidInput(ProcessError):
    """보낸 값이 틀림 (조치 계획 없음·너무 김) → API 오류 VALIDATION (2026-10-11 P4)."""


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def alarm_key(a: dict) -> str:
    key = f"{a['axis']}.{a['code']}" if a.get("axis") else a["code"]
    return f"{key}.{a['sub']}" if a.get("sub") and not a["code"].endswith(a["sub"]) else key


def bundle_groups(rows: list[dict]) -> list[list[dict]]:
    """같은 설비·같은 알람(축 포함)이 1분 안에 3번 이상이면 한 묶음. 나머지는 1건씩."""
    by_key: dict[tuple, list[dict]] = {}
    for a in sorted(rows, key=lambda r: r["occurred_at"]):
        by_key.setdefault((a["equipment_id"], alarm_key(a)), []).append(a)
    out = []
    for items in by_key.values():
        i = 0
        while i < len(items):
            j = i
            t0 = _dt(items[i]["occurred_at"])
            while j + 1 < len(items) and _dt(items[j + 1]["occurred_at"]) - t0 <= BUNDLE_WINDOW:
                j += 1
            if j - i + 1 >= BUNDLE_COUNT:
                out.append(items[i:j + 1])
                i = j + 1
            else:
                out.append([items[i]])
                i += 1
    return out


def storm_state(times: list[datetime], now: datetime, active_before: bool) -> bool:
    n = sum(1 for t in times if now - STORM_WINDOW < t <= now)
    return n > STORM_ON or (active_before and n >= STORM_OFF)


@dataclass
class Viewer:
    role: str
    user_id: str
    processes: set[str]


def viewer(state: DemoState, role: str, user_id: str | None) -> Viewer:
    r = normalize_role(role)   # 역할 없음·모름 → NotLoggedIn (UNAUTHORIZED)
    require(r, "view_alerts")  # 모니터링 계정(MON)은 MGR 홈 요약·SCR-16만 본다 (UI설계서 SCR-01) → FORBIDDEN
    u = state.user(user_id) if user_id else None
    if user_id and (u is None or u["role"] != r):
        raise NotLoggedIn()    # 사용자와 역할이 다름 → UNAUTHORIZED (2026-10-11 P4)
    procs = set(u["assigned_process"].split(";")) - {""} if u else set()
    return Viewer(r, user_id or "", procs)


def _base(nid, kind, at, **kw) -> dict:
    k = KINDS[kind]
    return {"id": nid, "kind": kind, "kind_label": k["label"], "importance": k["importance"], "rank": k["rank"],
            "sub": k["sub"], "occurred_at": at, "receivers": sorted(k["receivers"]), "process_roles": sorted(k["process_roles"]),
            "auto_text": k["auto"] if isinstance(k["auto"], str) or k["auto"] is None else None,
            "needs_plan": bool(k.get("needs_plan")), "equipment_id": "", "process": "", "title": "", "sentence": "",
            "related": "", "records": [], "evidence": [], "links": [], "bundle": [], "over_24h": False,
            "rule_tag": None, "alarm_event_id": None, "group_key": nid, "data_label": DATA_LABEL,
            "is_synthetic": True, **kw}  # 알림은 가상 운영 기록에서 만든다 (API명세서 공통 규칙, 2026-10-11 P1)


def _alarm_notes(state: DemoState, now: datetime) -> list[dict]:
    rows = state.alarms()
    master = {a["code"]: a for a in get_repo().master("alarm_master")}
    eqs = state.equipment()
    keep = [a for a in rows if _dt(a["occurred_at"]) <= now and
            (a["processed"] == "false" or now - _dt(a["occurred_at"]) <= timedelta(days=HISTORY_DAYS))]
    out = []
    for grp in bundle_groups(keep):
        a = grp[-1]
        kind = SEVERITY_KIND.get(a["severity"], "alarm_warning")
        k = KINDS[kind]
        key = alarm_key(a)
        proc = a["process"] or eqs.get(a["equipment_id"], {}).get("process", "")
        n = _base(f"N-{a['alarm_event_id']}", kind, a["occurred_at"], equipment_id=a["equipment_id"], process=proc,
                  alarm_event_id=a["alarm_event_id"], group_key=f"{a['equipment_id']}:{a['alarm_code']}")
        if kind == "alarm_stop":
            n["auto_text"] = k["auto"]["OP-30" if proc == "OP-30" else "other"]
        m = master.get(a["alarm_code"], {})
        n["title"] = f"알람 {key} {a['name_ko'] or m.get('name_ko', '')}".strip()
        n["sentence"] = f"{a['equipment_id']} 알람 {key} ({SEVERITY_KO.get(a['severity'], a['severity'])})"
        if len(grp) > 1:
            n["bundle"] = [g["occurred_at"] for g in grp]
        # 관련 정보 한 줄: 같은 설비 바로 앞 1분 안 알람 (연쇄)
        t = _dt(a["occurred_at"])
        prev = [p for p in rows if p["equipment_id"] == a["equipment_id"] and p is not a and p not in grp
                and timedelta(0) <= t - _dt(p["occurred_at"]) <= BUNDLE_WINDOW]
        if prev:
            n["related"] = "관련: 바로 앞 " + "·".join(p["code"] for p in sorted(prev, key=lambda x: x["occurred_at"])) + " (1분 안)"
        else:
            week = [p for p in rows if p["equipment_id"] == a["equipment_id"] and p["alarm_code"] == a["alarm_code"]
                    and timedelta(0) <= t - _dt(p["occurred_at"]) < timedelta(days=7)]
            if len(week) > 1:
                n["related"] = f"관련: 이 설비에서 최근 7일 {len(week)}번째"
        n["evidence"] = parse_refs(m.get("doc02_section", ""))
        n["links"] = [{"label": "지침카드", "screen": "SCR-09", "target": a["alarm_event_id"], "enabled": True}]
        if kind == "alarm_stop" and proc == "OP-30":
            n["links"].append({"label": "작업지시서", "screen": "SCR-11", "target": a["work_order_id"], "enabled": False,
                               "reason": "작업지시서 화면은 다음 묶음(B)에서 연결합니다"})
        if a["processed"] == "true":
            n["processed"] = {"by": "기록", "at": a["processed_at"], "auto": True}
        out.append(n)
    return out


def _other_notes(state: DemoState, now: datetime) -> list[dict]:
    repo = get_repo()
    out = []
    ref = REFERENCE_AT  # 공구·재고·하루 전 알림은 기준 시각에 생긴 것으로 둔다 (시연 시계가 흘러도 바뀌지 않게)
    # 반복 알람 (DOC-07 §10.4, DOC-03 §1.4)
    for r in repo.table("repeat_alarm"):
        if r["status"] in ("효과 확인", "2단계로 올림"):
            continue
        kind = "repeat_2" if r["stage"] == "2" else "repeat_1"
        n = _base(f"N-{r['repeat_id']}", kind, r["triggered_at"], equipment_id=r["equipment_id"],
                  group_key=f"{r['equipment_id']}:{r['alarm_code']}", rule_tag=VIRTUAL_RULE)
        n["process"] = state.equipment()[r["equipment_id"]]["process"]
        n["title"] = (f"반복 알람 2단계 {r['alarm_code']} — 지난 조치 효과 없음" if kind == "repeat_2"
                      else f"반복 알람 {r['alarm_code']} (7일 안 3번째)")
        n["sentence"] = f"{r['equipment_id']} 알람 {r['alarm_code']}이 7일 안에 3번 났습니다 (반복 알람 {r['stage']}단계)."
        recs = T.work_records("MGR", r["equipment_id"], r["alarm_code"])["rows"][-2:]
        n["records"] = [w["work_record_id"] for w in recs]
        n["related"] = "관련: 지난 조치" if n["records"] else "관련: 지난 조치 기록 없음"
        refs = r["doc_section"] + (" §1.4" if kind == "repeat_2" else "")
        n["evidence"] = parse_refs(refs)
        last = r["event_ids"].split(";")[-1]
        n["alarm_event_id"] = last
        n["links"] = [{"label": "지침카드", "screen": "SCR-09", "target": last, "enabled": True}]
        if r["plan_at"]:
            n["processed"] = {"by": r["plan_by"], "at": r["plan_at"], "plan": r["action_plan"], "auto": False}
        out.append(n)
    # 공구 수명 90% (DOC-07 §9, 가상 규칙)
    for t in T.tool_life("MGR", min_pct=90)["rows"]:
        n = _base(f"N-TOOL-{t['equipment_id']}-{t['tool_no']}", "tool_90", ref, equipment_id=t["equipment_id"],
                  rule_tag=VIRTUAL_RULE)
        n["process"] = state.equipment()[t["equipment_id"]]["process"]
        n["title"] = f"공구 수명 {t['usage_pct']}% — {t['tool_no']} {t['tool_name']}"
        n["sentence"] = f"{t['equipment_id']} {t['tool_no']} {t['tool_name']} 사용 {float(t['used']):g}/{t['limit']} ({t['usage_pct']}%)."
        n["evidence"] = parse_refs("DOC-07 §9")
        n["links"] = [{"label": "공구 수명", "screen": "SCR-22", "enabled": False, "reason": "공구 수명 화면은 이번 범위 밖입니다"}]
        out.append(n)
    # 예방 정비 기한 넘김 / 하루 전 (DOC-04, DOC-07 §10)
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    for p in repo.table("pm_schedule"):
        if p["overdue"] == "true":
            kind = "pm_overdue"
        elif p["next_due"][:10] == tomorrow:
            kind = "pm_due_tomorrow"
        else:
            continue
        # 기한 넘김 알림은 기한 다음 날 시작, 하루 전 알림은 기준 시각에 생긴다
        at = ((_dt(p["next_due"][:10] + "T08:00:00+09:00") + timedelta(days=1)).isoformat() if kind == "pm_overdue" else ref)
        n = _base(f"N-PM-{p['equipment_id']}-{p['pm_item_id']}", kind, at,
                  equipment_id=p["equipment_id"], rule_tag=VIRTUAL_RULE)
        n["process"] = state.equipment()[p["equipment_id"]]["process"]
        n["title"] = f"{KINDS[kind]['label']} — {p['item']}"
        n["sentence"] = f"{p['equipment_id']} {p['item']} ({p['frequency']}, 기한 {p['next_due'][:10]})"
        n["evidence"] = parse_refs(p["doc_section"])
        n["links"] = [{"label": "예방 정비", "screen": "SCR-23", "enabled": False, "reason": "예방 정비 화면은 이번 범위 밖입니다"}]
        out.append(n)
    # 재고 부족 (재고 ≤ 안전 재고, 완제품은 부족 알림 없음)
    for i in repo.table("inventory_state"):
        if i["short"] != "true" or i["item_id"].startswith("FG-"):
            continue
        n = _base(f"N-INV-{i['item_id']}", "inventory_short", ref, rule_tag=VIRTUAL_RULE)
        n["receivers"] = sorted({i["owner_role"], "MGR"})
        n["title"] = f"재고 부족 — {i['name']}"
        n["sentence"] = f"{i['name']} {float(i['on_hand']):g}{i['unit']} (안전 재고 {i['safety_stock']}{i['unit']}) · 관리 {i['owner_role']}"
        n["evidence"] = parse_refs("DOC-07 §10.2")
        n["links"] = [{"label": "재고", "screen": "SCR-21", "enabled": False, "reason": "재고 화면은 이번 범위 밖입니다"}]
        out.append(n)
    return out


def all_notifications(state: DemoState) -> list[dict]:
    now = state.now
    notes = _alarm_notes(state, now) + _other_notes(state, now)
    for n in notes:
        mem = state.processed.get(n["id"])
        if mem:
            n["processed"] = mem
        n.setdefault("processed", None)
        if n["importance"] == "주의" and not n["processed"] and now - _dt(n["occurred_at"]) > LONG_OPEN:
            n["over_24h"] = True
            n["rank"] = "0-1"
    return notes


def visible(n: dict, v: Viewer) -> bool:
    if v.role == "MGR":
        return True
    if v.role not in n["receivers"]:
        return False
    if v.role == "OPR" and n["process"] and v.processes and n["process"] not in v.processes:
        return False
    return True


def rank_lines(open_notes: list[dict]) -> dict:
    """처리 안 된 알림을 보고 순위 줄로 (같은 설비·같은 원인 묶기, 전체 N = 묶은 뒤 줄 수). 알림 목록과 브리핑이 같이 쓴다
    (2026-10-11 P3에서 이름을 공개로 바꿈 — 전에는 _report)."""
    items = [Item(n["id"], n["rank"], n["title"], n["occurred_at"], group_key=n["group_key"], sub_order=n["sub"],
                  sort_value=(_dt(n["occurred_at"]).timestamp() * -1 if n["rank"] == "0-1" else 0)) for n in open_notes]
    rep = rank_report(items)
    lines = [{"rank": l.rank, "rank_name": l.rank_name, "title": l.title, "ids": [i.item_id for i in l.items],
              "count": l.original_count, "folded": l.folded} for l in rep["lines"]]
    return {"total": rep["total"], "counts": rep["counts"], "lines": lines}


def open_for(state: DemoState, v: Viewer | None) -> list[dict]:
    """처리 안 된 알림 중 이 사람이 볼 것(v가 None이면 받는 사람으로 거르지 않고 전부). 상태를 바꾸지 않는다(listing은 폭주 상태를
    고친다) — 브리핑이 쓴다 (2026-10-11 P3). 전체형 브리핑은 받는 사람과 상관없이 프로그램이 모은 문제 전부를 보인다(FR-AST-01-02)."""
    with state.lock:
        return [n for n in all_notifications(state) if (v is None or visible(n, v)) and not n["processed"]]


def listing(state: DemoState, role: str, user_id: str | None) -> dict:
    v = viewer(state, role, user_id)
    with state.lock:
        notes = [n for n in all_notifications(state) if visible(n, v)]
        now = state.now
        alarm_times = [_dt(n["occurred_at"]) for n in notes if n["alarm_event_id"] and n["kind"].startswith("alarm")]
        state.storm = storm_state(alarm_times, now, state.storm)
        recent = [n for n in notes if n["kind"] == "alarm_stop" and now - STORM_WINDOW < _dt(n["occurred_at"]) <= now]
        storm = {"active": state.storm, "count_10min": sum(1 for t in alarm_times if now - STORM_WINDOW < t <= now),
                 "urgent_count": len(recent), "latest_urgent": max(recent, key=lambda n: n["occurred_at"])["id"] if recent else None}
    for n in notes:
        n["can_process"] = (not n["processed"]) and v.role in n["process_roles"]
    open_notes = [n for n in notes if not n["processed"]]
    notes.sort(key=lambda n: n["occurred_at"], reverse=True)
    return {"as_of": now.isoformat(), "data_label": DATA_LABEL, "is_synthetic": True, "notifications": notes, "report": rank_lines(open_notes),
            "storm": storm, "unprocessed": len(open_notes), "urgent_open": sum(1 for n in open_notes if n["importance"] == "긴급"),
            "history_days": HISTORY_DAYS,
            "not_built": "목표 미달·병목·납기·승인 대기·문서 수정·교대 보고서 확정 요청·품질 알림은 다음 묶음 또는 범위 밖이라 아직 만들지 않습니다"}


def process(state: DemoState, nid: str, role: str, user_id: str | None, plan: str = "") -> dict:
    v = viewer(state, role, user_id)
    with state.lock:
        n = next((x for x in all_notifications(state) if x["id"] == nid), None)
        if n is None or not visible(n, v):
            raise NotFound(nid)
        if n["processed"]:
            raise InvalidState("이미 처리된 알림입니다")
        if v.role not in n["process_roles"]:
            if n["auto_text"] and not n["process_roles"]:
                raise InvalidState(f"이 알림은 사람이 [처리]를 누르지 않습니다 — {n['auto_text']}")
            raise PermissionDenied()
        plan = (plan or "").strip()
        if n["needs_plan"] and not plan:
            raise InvalidInput("조치 계획 한 줄을 적어야 처리됩니다")
        if len(plan) > PLAN_MAX:
            raise InvalidInput(f"조치 계획은 {PLAN_MAX}자 안으로 적습니다")
        rec = {"by": v.user_id or v.role, "role": v.role, "at": state.now.isoformat(), "plan": plan or None, "auto": False}
        state.processed[nid] = rec
        # 실시간 사건 이름은 명세 꼴(STR-01 `notification` — 알림 생김·처리됨)로, 무엇이 바뀌었는지는 change 칸에 (2026-10-11 P4)
        state.emit("notification", {"change": "processed", "id": nid, "processed": rec})
        return {"id": nid, "processed": rec, "is_synthetic": True}


def created_events(state: DemoState, rows: list[dict]) -> None:
    """사건을 넣은 뒤 SSE 이벤트를 남긴다. 긴급(정지)은 해당 설비 OPR·MNT에게 팝업 (UI설계서 2.5·SCR-08)."""
    notes = {n["alarm_event_id"]: n for n in all_notifications(state) if n["alarm_event_id"]}
    master = {m["code"]: m for m in get_repo().master("alarm_master")}
    for a in rows:
        n = notes.get(a["alarm_event_id"])
        if not n:
            continue
        state.emit("notification", {"change": "created", "id": n["id"], "importance": n["importance"], "title": n["title"]},
                   roles=set(n["receivers"]) | {"MGR"})
        if n["kind"] == "alarm_stop":
            state.emit("urgent_popup", {"id": n["id"], "alarm_event_id": a["alarm_event_id"], "equipment_id": a["equipment_id"],
                                        "process": n["process"], "key": alarm_key(a), "name_ko": a["name_ko"],
                                        "who": master.get(a["alarm_code"], {}).get("who", "확인 필요"),
                                        "occurred_at": a["occurred_at"]},
                       users=state.popup_targets(a["equipment_id"], _dt(a["occurred_at"])))
