"""5단계 ③: 교대·일일 보고서와 문서 수정 이력 (설계서 5.16, 논리 ERD 5.G.1~5.G.4, DOC-07 §5·§6·§10.5).

- 숫자 칸은 9월 기록에서 계산한다 (DOC-07 계산식). 특이 사항·인계·오늘의 문제 문장은 기획서·문서 내용을 바탕으로 한
  틀 문장 [가상] — 실제 AI비서 초안 문장은 AI 담당이 바꿀 수 있다.
- 과거 문서는 모두 확정. 예외: 9/30 일일 보고서는 AI비서 초안 v0 (확정 대기, 시연 MGR 말풍선).
- 수정 이력: AI비서 초안 문서(작업지시서·정식 작업기록서·교대·일일 보고서)는 약 60%가 사람이 1~2곳 고친 버전을 가진다.
  사람이 처음 쓰는 문서(간이 작업기록·예방 정비 기록·출하 기록)는 v0 = 사람이 처음 저장한 것.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from .common import fmt_dt
from .flow import MNT_BY_SHIFT, OPR_BY_PROC

SHIFT_COLS = ["shift_id", "status", "target_qty", "actual_qty", "defect_qty", "notable_text", "handover_text",
              "confirmed_by", "confirmed_at", "current_version"]
DAILY_COLS = ["work_date", "status", "target_qty", "actual_qty", "defect_qty", "oee_pct", "failure_loss_qty",
              "speed_loss_qty", "issues_summary", "confirmed_by", "confirmed_at", "current_version"]
REV_COLS = ["revision_id", "doc_type", "doc_key", "version_no", "author_kind", "author_user_id", "created_at", "reason",
            "status_after", "content_snapshot", "internal_doc_rev"]
CHG_COLS = ["revision_id", "field_name", "before_value", "after_value"]
CAUSE_KO = {"C1": "원인 ① 사이클 시간 증가 (공구 마모)", "C2": "원인 ② OP-30 1대만 가동", "C3": "원인 ③ 검사 강화",
            "FAILURE": "고장", "BASE": "기준 병목"}

# 사람이 고친 곳 (설계서 5.16 "특이 사항 문장, 원인 표현 등") — 틀 문장 [가상]
EDIT_NOTE = ["현장 확인: VF-2 절삭유 거품이 조금 있음, 다음 교대 확인 바람.", "초품 검사 이상 없음.",
             "MIL-01 칩이 많이 쌓여 교대 끝에 청소함.", "공구 대차 정리함.", "세척기 세척액 보충함."]
EDIT_HAND = ["VF2-02 공기 배관 물 빼기 확인", "다음 교대 첫 작업지시 순서 확인", "측정실 온도 맞춤 선반 정리"]
EDIT_DAILY = ["관리자 메모: 내일 오전 정비 일정 확인.", "관리자 메모: 보류 로트 처리 결과 공유 바람.",
              "관리자 메모: 공구 재고 주문 확인."]


class Timeline:
    """9월 기록을 시각으로 찾아보는 도구 (보고서·알림 공용)."""

    def __init__(self, cfg, sim, masters, ctx):
        self.cfg, self.sim, self.M, self.ctx = cfg, sim, masters, ctx
        self.cal = sim.cal
        self.reason_name = {d["reason_code"]: d["reason_name"] for d in masters["downtime_reason"]}
        self.fail = {d["reason_code"] for d in masters["downtime_reason"] if d["reason_group"] == "FAILURE"}
        self.per_part = {eq: (mc.base / 30 if eq == "WSH-01" else mc.base) for eq, mc in sim.mach.items()}
        self.runs = {}
        for eq, mc in sim.mach.items():
            rs = mc.state_runs + [[self.cal.n_min, None]]
            self.runs[eq] = [(a, b, st) for (a, st), (b, _) in zip(rs[:-1], rs[1:])]
        # 공구 사용률 시간표: (분, 누적) — 사용 기록과 교체(0)
        self.tool_tl = {}
        for (tid, _), u in sim.tool_usage.items():
            self.tool_tl.setdefault(tid, []).append((u["m"], 1, u["cum_after"]))
        for c in sim.tool_changes:
            self.tool_tl.setdefault(c["tool_id"], []).append((c["changed_m"], 2, 0.0))
        for v in self.tool_tl.values():
            v.sort()
        self.tool_limit = {t["tool_id"]: float({x["item_no"]: x for x in masters["tool_type"]}[t["item_no"]]["life_limit"])
                           for t in masters["tool"]}
        self.items = {i["item_no"]: i for i in masters["inventory_item"]}
        self.inv = sorted(ctx["inv"], key=lambda t: (t["txn_at"], t["txn_id"]))
        self.done_m = sorted(p.start["done"] for p in sim.finished)

    def m(self, dt: datetime) -> int:
        return self.cal.to_min(dt)

    def work_minutes(self, a: int, b: int) -> int:
        return sum(1 for m in range(a, b) if self.cal.is_work(m))

    def stops(self, a: int, b: int) -> list[dict]:
        """필수 정지: 고장 그룹(F01~F06) 5분 이상 정지 전부, 정지 시간 긴 순 (DOC-07 §5.4)."""
        out = []
        for eq, rs in self.runs.items():
            for s, e, st in rs:
                if st and st[1] in self.fail and st[0] in ("DOWN", "IDLE") and e - s >= 5:
                    ov = min(e, b) - max(s, a)
                    if ov > 0:
                        out.append({"equipment_id": eq, "reason": st[1], "reason_name": self.reason_name[st[1]],
                                    "start": max(s, a), "end": min(e, b), "minutes": ov, "alarm_id": st[3],
                                    # 손실도 구간 안 분으로 (2026-10-20 — 전에는 정지 전체 길이라 9/14 VF2-02가 11.6개, 백엔드·시연 서버는 5.7개)
                                    "loss": round(ov / self.per_part[eq], 1)})
        out.sort(key=lambda x: (-x["minutes"], -x["loss"], x["start"]))
        return out

    def run_min(self, eq: str, a: int, b: int, kind: str = "RUN") -> int:
        return sum(max(0, min(e, b) - max(s, a)) for s, e, st in self.runs[eq] if st and st[0] == kind)

    def tool_pct(self, tid: str, m: int) -> float:
        cum = None
        for t, _, v in self.tool_tl.get(tid, []):
            if t > m:
                break
            cum = v
        if cum is None:
            cum = float(next(x["cum_usage"] for x in self.M["tool"] if x["tool_id"] == tid))
        return cum / self.tool_limit[tid]

    def stock(self, item: str, dt: datetime) -> float:
        return sum(t["qty_change"] for t in self.inv if t["item_no"] == item and t["txn_at"] <= dt)

    def done_between(self, a: int, b: int) -> int:
        import bisect
        return bisect.bisect_left(self.done_m, b) - bisect.bisect_left(self.done_m, a)


def _snap(d: dict) -> str:
    return json.dumps({k: (fmt_dt(v) if isinstance(v, datetime) else (str(v) if hasattr(v, "isoformat") else v))
                       for k, v in d.items()}, ensure_ascii=False)


def build_reports(cfg, sim, masters, rng, ctx):
    """돌려주는 값: dict(shift_report, daily_report, items_at(시각) 함수용 정보)."""
    r = rng.stream("reports")
    tl = Timeline(cfg, sim, masters, ctx)
    cal = sim.cal
    sq = {}
    for rep in sim.reports.values():
        sq[rep["shift_id"]] = sq.get(rep["shift_id"], 0) + rep["sq"]
    holds = sim.holds_log
    bn = ctx["bn"]
    alarms = sim.alarm_events
    shifts, sr_meta = [], {}
    for sh in cal.shifts:
        a, b = cal.to_min(sh.start), cal.to_min(sh.end)
        target = sh.target_qty + sh.carry_over_qty
        stops = tl.stops(a, b)
        avail = {}
        for eq in ("VF2-01", "VF2-02"):
            pbt = sh.planned_min - tl.run_min(eq, a, b, "MAINT")
            avail[eq] = round(tl.run_min(eq, a, b) / pbt * 100, 1) if pbt > 0 else None
        bn_in = [x for x in bn if a <= x["_m"] < b and x["cause_code"] != "BASE"]
        warn = [e for e in alarms if a <= e["occurred_m"] < b and e["severity"] == "WARN"]
        stop_al = [e for e in alarms if a <= e["occurred_m"] < b and e["severity"] == "STOP"]
        held = [h for h in holds if a <= h["held_m"] < b]
        s1 = f"실적 {sh.actual_qty}개 / 총 목표 {target}개 ({sh.actual_qty - target:+d}개)."
        if stops:
            top = stops[0]
            s2 = (f"필수 정지 {len(stops)}건, 합계 {sum(x['minutes'] for x in stops)}분 — 가장 긴 것 {top['equipment_id']} "
                  f"{top['reason_name']} {top['minutes']}분 (고장 손실 약 {top['loss']}개, 추정).")
        else:
            s2 = "필수 정지(고장 그룹 5분 이상) 없음."
        s3 = ("병목: " + ", ".join(f"{cal.to_dt(x['_m']):%H:%M} {x['new_process_code']} {CAUSE_KO[x['cause_code']]}"
                                  for x in bn_in) + ".") if bn_in else "병목은 기준 병목(OP-30) 그대로."
        s4 = f"불량(폐기) {sq.get(sh.shift_id, 0)}개." + (" 로트 보류: " + ", ".join(h["lot"].lot_no for h in held) + "."
                                                       if held else "")
        s5 = (f"주의 알람 {len(warn)}건 ({', '.join(sorted({e['alarm_code'] for e in warn}))})" if warn else "주의 알람 없음") + \
             (f", 정지 등급 알람 {len(stop_al)}건." if stop_al else ".")
        notable = " ".join([s1, s2, s3, s4, s5])
        handover = handover_text(tl, sim, b - 1, ctx)
        shifts.append({"shift_id": sh.shift_id, "status": "CONFIRMED", "target_qty": target, "actual_qty": sh.actual_qty,
                       "defect_qty": sq.get(sh.shift_id, 0), "notable_text": notable, "handover_text": handover,
                       "confirmed_by": sh.supervisor, "confirmed_at": None, "current_version": 0})
        # 확정 시각 [가상]: 주간 17:00 뒤 5~30분 ("퇴근 전"), 야간 05:00~06:00 (설계서 5.16)
        lo, hi = (5, 31) if sh.shift_type == "DAY" else (5, 56)
        shifts[-1]["confirmed_at"] = sh.end + timedelta(minutes=int(r.integers(lo, hi)))
        sr_meta[sh.shift_id] = {"draft_at": sh.end, "availability": avail, "stops": stops, "shift": sh}
    # 일일 보고서
    daily = []
    by_id = {x["shift_id"]: x for x in shifts}
    end_day = cal.workdays[-1]
    ds_min = int(cfg["shifts"]["DAY"]["start"][:2]) * 60 + int(cfg["shifts"]["DAY"]["start"][3:5])
    mgr_window = (ds_min + 30, ds_min + 120)          # 일일 보고서 확정 시간대: 주간 시작 30분~2시간 뒤
    for d in cal.workdays:
        day = by_id[f"{d.isoformat()}-D"]
        night = by_id[f"{d.isoformat()}-N"]
        dsh, nsh = sr_meta[day["shift_id"]]["shift"], sr_meta[night["shift_id"]]["shift"]
        a, b = cal.to_min(dsh.start), cal.to_min(nsh.end)
        created = night["confirmed_at"]
        # 라인 OEE = OP-30 2대를 한 작업장으로 (DOC-07 §6.2)
        apt = sum(tl.run_min(eq, a, b) for eq in ("VF2-01", "VF2-02"))
        pbt = 2 * (dsh.planned_min + nsh.planned_min)       # 라인 PBT = 480분 × 2대, 한 대의 예방 정비는 빼지 않음
        reps = [x for x in sim.reports.values() if x["process_code"] == "OP-30" and x["shift_id"] in (dsh.shift_id, nsh.shift_id)]
        pq = sum(x["pq"] for x in reps)
        good = sum(x["gq"] + x["rq"] for x in reps)
        oee = (apt / pbt) * (7.0 * pq / apt if apt else 0) * (good / pq if pq else 0) * 100 if pbt else 0
        stops = tl.stops(a, b)
        fl = round(sum(x["loss"] for x in stops), 1)
        spd = 0.0
        for k, x in enumerate(bn):
            if x["cause_code"] not in ("C1", "C2", "C3"):
                continue
            s0 = max(x["_m"], a)
            e0 = min(bn[k + 1]["_m"] if k + 1 < len(bn) else cal.n_min, b)
            if e0 <= s0:
                continue
            planned = tl.work_minutes(s0, e0) / 3.5
            fl_i = sum(st["minutes"] / tl.per_part[st["equipment_id"]] for st in tl.stops(s0, e0))
            spd += max(0.0, planned - tl.done_between(s0, e0) - fl_i)
        issues = issues_text(tl, sim, a, b, ctx, stops, [day, night])
        is_last = d == end_day
        conf_at = None
        if not is_last:
            nd = created.date()
            while nd not in set(cal.workdays) and nd <= end_day:
                nd += timedelta(days=1)
            mm = int(r.integers(*mgr_window))
            conf_at = datetime(nd.year, nd.month, nd.day, mm // 60, mm % 60, tzinfo=created.tzinfo)
        daily.append({"work_date": d, "status": "AI_DRAFT" if is_last else "CONFIRMED", "target_qty": 180,
                      "actual_qty": day["actual_qty"] + night["actual_qty"],
                      "defect_qty": day["defect_qty"] + night["defect_qty"], "oee_pct": round(oee, 1),
                      "failure_loss_qty": fl, "speed_loss_qty": round(spd, 1), "issues_summary": issues,
                      "confirmed_by": None if is_last else "U12", "confirmed_at": conf_at, "current_version": 0,
                      "_created_at": created})
    return {"shift_report": shifts, "daily_report": daily, "meta": sr_meta, "timeline": tl}


# 보고 순위 6.43: 처리 안 된 알림이 들어가는 칸과 묶음 순서 (순위 3 안: 반복 → 주의 알람 → 품질 → 설비 멈출 수 있는 것 → 승인)
RANK = {"TARGET_RISK": ("R2", 0), "BOTTLENECK_MOVE": ("R2", 1), "WIP_WARN": ("R2", 1), "LOT_DUE_RISK": ("R2", 2),
        "REPEAT_ALARM_2": ("R3", 0), "CAUSE_CHECK_REQUEST": ("R3", 0), "REPEAT_ALARM": ("R3", 1), "ALARM_WARN": ("R3", 2),
        "SPC_OUT": ("R3", 3), "TOOL_LIFE_90": ("R3", 5), "PM_OVERDUE": ("R3", 6), "STOCK_LOW": ("R3", 7),
        "APPROVAL_WAIT_2H": ("R3", 8), "ALARM_GUIDE": ("R4", 0), "PM_DUE_SOON": ("R4", 1), "APPROVAL_WAIT_30M": ("R4", 2)}


def _open_items(tl: Timeline, sim, m: int, ctx) -> dict[str, list[str]]:
    """그 시각에 남아 있는 일 (보고 순위 6.43 순서). 알림은 그 시각까지 처리 안 된 것 (ctx["open_at"])."""
    cal = sim.cal
    dt = cal.to_dt(m)
    out = {"R01": [], "R1": [], "R2": [], "R3": [], "R4": []}
    for eq, rs in tl.runs.items():
        for s, e, st in rs:
            if s <= m < e and st and st[0] == "DOWN":
                out["R1"].append(f"{eq} 고장 중 ({tl.reason_name.get(st[1], st[1])})")
    r3 = []
    for x in ctx["open_at"](m):
        if x["rule_code"] not in RANK:
            continue
        rank, grp = RANK[x["rule_code"]]
        text = x["message"].split("] ", 1)[-1]
        if x["importance"] == "CAUTION" and m - x["_m"] > 24 * 60:
            out["R01"].append(text + " (24시간 넘게 처리 안 됨)")      # 0-1 오래 방치
        elif rank == "R3":
            r3.append((grp, x["_m"], text))
        else:
            out[rank].append(text)
    for h in sim.holds_log:
        if h["held_m"] <= m and (h.get("released_m") is None or m < h["released_m"]):
            r3.append((4, h["held_m"], f"보류 로트 {h['lot'].lot_no}"))
    enh = [l.lot_no for l in sim.lots if l.enhanced and l.hold and l.hold["held_m"] <= m
           and (l.judged_m is None or m < l.judged_m)]
    if enh:
        r3.append((4, m, "강화 검사 중 로트 " + ", ".join(enh)))
    for w in ctx["mnt"]["maintenance_work_order"]:
        if w["created_at"] <= dt and (w["completed_at"] is None or dt < w["completed_at"]):
            r3.append((8, m, f"진행 중 작업지시서 {w['wo_no']} ({w['equipment_id']})"))
    out["R3"] = [t for _, _, t in sorted(r3)]
    return out


def handover_text(tl, sim, m, ctx) -> str:
    items = _open_items(tl, sim, m, ctx)
    parts = ["0 안전: 잠금·표지 중인 설비 없음"]
    for k, label in (("R01", "0-1 오래 방치"), ("R1", "1 긴급"), ("R2", "2 생산 위험"), ("R3", "3 주의"), ("R4", "4 참고")):
        parts.append(f"{label}: " + ("; ".join(items[k]) if items[k] else "-"))
    return " / ".join(parts)


def issues_text(tl, sim, a, b, ctx, stops, shift_rows) -> str:
    """오늘의 문제 (전체 N건): 프로그램이 모은 순서(6.43) 그대로 문장으로."""
    cal = sim.cal
    items = []
    for x in stops:
        if x["reason"].startswith("F") and x["alarm_id"] and any(
                e["id"] == x["alarm_id"] and e["severity"] == "STOP" for e in sim.alarm_events):
            items.append(f"[긴급] {x['equipment_id']} 고장 {x['minutes']}분 ({x['reason_name']}, 고장 손실 약 {x['loss']}개)")
    for s in shift_rows:
        if s["actual_qty"] < s["target_qty"] * 0.9:
            items.append(f"[생산] {s['shift_id']} 실적 {s['actual_qty']}개 — 목표 {s['target_qty']}개의 90% 아래")
    for x in ctx["bn"]:
        if a <= x["_m"] < b and x["cause_code"] in ("C1", "C2", "C3"):
            items.append(f"[생산] {cal.to_dt(x['_m']):%H:%M} 병목 {x['new_process_code']} — {CAUSE_KO[x['cause_code']]}")
    for h in sim.holds_log:
        if a <= h["held_m"] < b:
            items.append(f"[주의] 로트 보류 {h['lot'].lot_no} — {h['reason']}")
    warn = [e for e in sim.alarm_events if a <= e["occurred_m"] < b and e["severity"] == "WARN"]
    if warn:
        items.append(f"[주의] 주의 등급 알람 {len(warn)}건 ({', '.join(sorted({e['alarm_code'] for e in warn}))})")
    left = _open_items(tl, sim, b - 1, ctx)                   # 하루 끝에 남은 주의 일 (오래 방치 포함)
    seen = {t for t in items}
    for t in left["R01"] + left["R3"]:
        if not any(t.split(" (")[0] in x for x in seen):
            items.append(f"[주의] {t}")
    guide = [e for e in sim.alarm_events if a <= e["occurred_m"] < b and e["severity"] == "GUIDE"]
    if guide:
        items.append(f"[참고] 조작 안내 알람 {len(guide)}건")
    if not items:
        return "전체 0건"
    cnt = {k: sum(1 for t in items if t.startswith(f"[{k}]")) for k in ("긴급", "생산", "주의", "참고")}
    head = f"전체 {len(items)}건 (" + " · ".join(f"{k} {v}" for k, v in cnt.items()) + ")"
    return head + ": " + " / ".join(f"{i + 1}) {t}" for i, t in enumerate(items))


def build_revisions(cfg, sim, masters, rng, ctx, reps):
    """문서 버전과 바뀐 칸. 문서 행의 current_version도 맞춘다 (돌려주는 값: revision 줄, change 줄, 추가 정보)."""
    r = rng.stream("revisions")
    cal = sim.cal
    share = cfg["reports"].get("revised_share", 0.6)
    revs, chg = [], []
    info = {"wo_saved": {}, "revised": []}

    def add(doc_type, key, ver, kind, who, at, status, content, reason=None, changes=()):
        rid = len(revs) + 1
        revs.append({"revision_id": rid, "doc_type": doc_type, "doc_key": key, "version_no": ver, "author_kind": kind,
                     "author_user_id": who, "created_at": at, "reason": reason, "status_after": status,
                     "content_snapshot": _snap(content), "internal_doc_rev": None})
        for f, before, after in changes:
            chg.append({"revision_id": rid, "field_name": f, "before_value": before, "after_value": after})
        return rid

    # 작업지시서: v0 AI 초안 → v1 담당 MNT가 고쳐 저장 (승인 전 꼭 저장, 6.13)
    for w in ctx["mnt"]["maintenance_work_order"]:
        v0 = {k: w[k] for k in ("wo_no", "title", "symptom", "equipment_id", "lot_no")}
        add("WORK_ORDER", w["wo_no"], 0, "AI", None, w["created_at"], "AI_DRAFT", v0)
        save = min(w["created_at"] + timedelta(minutes=int(r.integers(3, 16))), w["approved_at"] - timedelta(minutes=1))
        after = w["symptom"] + " (현장 확인: 알람 이력과 같음)"
        add("WORK_ORDER", w["wo_no"], 1, "HUMAN", w["assignee_user_id"], save, "EDITING", dict(v0, symptom=after),
            changes=[("증상", w["symptom"], after)])
        w["current_version"] = 1
        info["wo_saved"][w["wo_no"]] = save
    # 작업기록서: 정식은 AI 초안 → 약 60% MNT가 고침, 간이는 사람이 처음 저장
    for x in ctx["mnt"]["work_record"]:
        base = {k: x[k] for k in ("record_no", "cause", "action", "worker_memo", "repair_min")}
        if x["record_type"] == "FULL":
            add("WORK_RECORD", x["record_no"], 0, "AI", None, x["end_at"], "AI_DRAFT", base)
            if r.random() < share:
                c2 = "확인 결과: " + x["cause"]
                a2 = x["action"] + " 조치 뒤 시운전 10분 이상 없음."
                add("WORK_RECORD", x["record_no"], 1, "HUMAN", x["confirmed_by"], x["confirmed_at"], "CONFIRMED",
                    dict(base, cause=c2, action=a2), changes=[("원인", x["cause"], c2), ("조치", x["action"], a2)])
                x["cause"], x["action"], x["current_version"] = c2, a2, 1
        else:
            add("WORK_RECORD", x["record_no"], 0, "HUMAN", x["confirmed_by"], x["confirmed_at"], "CONFIRMED", base)
    # 교대 보고서
    for s in reps["shift_report"]:
        meta = reps["meta"][s["shift_id"]]
        v0 = {k: s[k] for k in ("shift_id", "target_qty", "actual_qty", "defect_qty", "notable_text", "handover_text")}
        v0["availability_pct"] = meta["availability"]
        v0["mandatory_stops"] = [{k: (fmt_dt(cal.to_dt(st[k])) if k in ("start", "end") else st[k])
                                  for k in ("equipment_id", "reason", "start", "end", "minutes", "loss")} for st in meta["stops"]]
        add("SHIFT_REPORT", s["shift_id"], 0, "AI", None, meta["draft_at"], "AI_DRAFT", v0)
        if r.random() < share:
            n2 = s["notable_text"] + " " + str(r.choice(EDIT_NOTE))
            changes = [("특이 사항", s["notable_text"], n2)]
            v1 = dict(v0, notable_text=n2)
            if r.random() < 0.3:
                h2 = s["handover_text"] + " / 추가: " + str(r.choice(EDIT_HAND))
                changes.append(("인계 사항", s["handover_text"], h2))
                v1["handover_text"] = h2
                s["handover_text"] = h2
            add("SHIFT_REPORT", s["shift_id"], 1, "HUMAN", s["confirmed_by"], s["confirmed_at"], "CONFIRMED", v1,
                changes=changes)
            s["notable_text"], s["current_version"] = n2, 1
    # 확정 뒤 고친 예 1건 (사유 필수, REVISED — FR-AST-03-06): 정지가 있던 주간 교대 보고서
    cand = [s for s in reps["shift_report"] if reps["meta"][s["shift_id"]]["stops"] and s["shift_id"].endswith("-D")]
    if cand:
        s = cand[0]
        ver = s["current_version"] + 1
        before = s["notable_text"]
        after = before + " (정정: 정지 원인은 작업기록서 확정 내용과 같음)"
        at = s["confirmed_at"] + timedelta(hours=16)
        rid = add("SHIFT_REPORT", s["shift_id"], ver, "HUMAN", s["confirmed_by"], at, "REVISED",
                  {"shift_id": s["shift_id"], "notable_text": after},
                  reason="정지 원인 표현을 작업기록서 확정 내용에 맞춤", changes=[("특이 사항", before, after)])
        s["notable_text"], s["current_version"], s["status"] = after, ver, "REVISED"
        info["revised"].append({"revision_id": rid, "at": at, "doc_type": "SHIFT_REPORT", "doc_key": s["shift_id"]})
    # 일일 보고서 (9/30은 v0 그대로)
    for dly in reps["daily_report"]:
        key = dly["work_date"].isoformat()
        v0 = {k: (str(v) if k == "work_date" else v) for k, v in dly.items() if not k.startswith("_")
              and k not in ("status", "confirmed_by", "confirmed_at", "current_version")}
        rid0 = add("DAILY_REPORT", key, 0, "AI", None, dly["_created_at"], "AI_DRAFT", v0)
        dly["_rev0"] = rid0
        if dly["status"] == "CONFIRMED" and r.random() < share:
            i2 = dly["issues_summary"] + " " + str(r.choice(EDIT_DAILY))
            add("DAILY_REPORT", key, 1, "HUMAN", "U12", dly["confirmed_at"], "CONFIRMED", dict(v0, issues_summary=i2),
                changes=[("오늘의 문제", dly["issues_summary"], i2)])
            dly["issues_summary"], dly["current_version"] = i2, 1
    # 예방 정비 기록·출하 기록: v0 = 사람이 처음 저장
    for p in ctx["pm_rows"]:
        add("PM_RECORD", str(p["pm_record_id"]), 0, "HUMAN", p["recorded_by"], p["done_at"], p["status"],
            {k: p[k] for k in ("pm_task_id", "due_date", "done_at", "result", "measured_value", "memo")})
    for sh in ctx["ship_heads"]:
        add("SHIPMENT", sh["shipment_no"], 0, "HUMAN", sh["confirmed_by"], sh["shipped_at"], "CONFIRMED",
            {k: sh[k] for k in ("shipment_no", "due_date", "customer_code", "memo", "fifo_skip_reason")})
    return revs, chg, info
