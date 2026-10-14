"""5단계 ③: 알림 과거 기록 (논리 ERD 5.H.5·5.H.6, 6.36 알림 종류·처리 표, DOC-07 10장).

9월 기록에서 규칙(notification_rule 25종)이 냈을 알림을 다시 만든다. 문장은 기본 문구(message_source = DEFAULT) —
과거 기록이라 비서 문장은 만들지 않는다. 처리 여부는 6.36 "알림 종류별 처리" 표대로:
자동 = 그 알림이 요구한 기록이 생긴 때 (작업기록 확정, 공구 교체, 정비 실시, 승인, 보고서 확정 …), 사람 = 책임 역할이 [처리].
9/30 끝에 남는 것 (10/1 브리핑 재료): 2075 반복 알람 1단계, 9/30 일일 보고서 확정 요청, 축 윤활유 정비 기한 넘김,
공구 T05 90%, 안전 재고 아래 품목.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from .flow import MNT_BY_SHIFT, OPR_BY_PROC
from .reports import CAUSE_KO

COLS = {
    "notification": ["notification_id", "rule_code", "importance", "raised_at", "message", "related_info", "message_source",
                     "repeat_count", "is_flood", "is_processed", "process_kind", "processed_by", "process_memo",
                     "processed_at", "alarm_event_id", "equipment_id", "lot_no", "item_no", "pm_task_id", "tool_id", "wo_no",
                     "bottleneck_log_id", "revision_id", "result_id", "shift_id", "buffer_code", "cmm_import_id",
                     "prev_stage_notification_id", "repeat_stage_status"],
    "notification_recipient": ["notification_id", "user_id", "popup_sound", "read_at"],
}
CAUSE_NO = {"C1": "①", "C2": "②", "C3": "③"}
# 반복 알람 1단계 조치 계획 한 줄 (설계서 5.8 사례 ②) — 그 밖의 알람은 틀 문장 [가상]
PLAN_MEMO = {"108": "엔드밀·페이스밀 인서트 상태 확인 후 교체, 이송 조정 (DOC-03 §2.6 ★2·★3)"}


class Builder:
    def __init__(self, cfg, sim, masters, rng, ctx):
        self.cfg, self.sim, self.M, self.ctx = cfg, sim, masters, ctx
        self.cal = sim.cal
        self.N = self.cal.n_min
        self.r = rng.stream("notify")
        self.rule = {x["rule_code"]: x for x in masters["notification_rule"]}
        self.alarm_name = {x["alarm_code"]: x["name_ko"] for x in masters["alarm_master"]}
        self.guide = {}
        for g in masters["alarm_guide_map"]:
            if g["doc_no"] == "DOC-03":
                self.guide.setdefault(g["alarm_code"], g["section"])
        self.rows: list[dict] = []
        work = np.array([self.cal.is_work(m) for m in range(self.N)], dtype=bool)
        idx = np.where(work)[0]
        self._work_idx = idx

    # ---------- 작은 도구 ----------
    def m(self, dt: datetime) -> int:
        return self.cal.to_min(dt)

    def nx(self, m: int) -> int:
        """m 이후 첫 근무 분 (없으면 N)."""
        i = np.searchsorted(self._work_idx, m)
        return int(self._work_idx[i]) if i < len(self._work_idx) else self.N

    def staff(self, m: int) -> dict:
        sh = self.cal.shift_or_near(m)
        return {"shift": sh, "opr": OPR_BY_PROC[sh.shift_type], "mnt": MNT_BY_SHIFT[sh.shift_type], "sup": sh.supervisor}

    def manual(self, m: int, lo=None, hi=None) -> int:
        """사람이 [처리]한 분: 그 뒤 첫 근무 분 + lo~hi분 [가상]."""
        if lo is None:
            lo, hi = self.cfg["notifications"]["manual_process_after_min"]
            hi += 1
        return self.nx(m) + int(self.r.integers(lo, hi))

    def add(self, rule, m, message, *, related=None, done=None, kind=None, by=None, memo=None, to=(), **fk):
        if m is None or m >= self.N or m < 0:
            return None
        rl = self.rule[rule]
        row = {"rule_code": rule, "importance": rl["importance"], "_m": m, "message": message, "related_info": related,
               "message_source": "DEFAULT", "repeat_count": 1, "is_flood": False, "process_memo": memo, **fk}
        if done is not None and done < self.N:
            row.update({"is_processed": True, "process_kind": kind, "processed_by": by, "_pm": max(done, m)})
        else:
            row.update({"is_processed": False, "process_kind": None, "processed_by": None, "_pm": None})
        row["_to"] = list(dict.fromkeys(u for u in to if u))
        self.rows.append(row)
        return row

    # ---------- 알람 ----------
    def alarms(self):
        sim, mnt = self.sim, self.ctx["mnt"]
        prev = {e["id"]: e.get("prev") for e in sim.alarm_events}
        rec_of = {}
        for w in mnt["work_record"]:
            a = w["alarm_event_id"]
            while a:
                rec_of.setdefault(a, w)
                a = prev.get(a)
        for e in sim.alarm_events:
            m, eq, code, sev = e["occurred_m"], e["equipment_id"], e["alarm_code"], e["severity"]
            st = self.staff(m)
            proc = sim.mach[eq].proc
            name = self.alarm_name.get(code, code)
            rec = rec_of.get(e["id"])
            sec = self.guide.get(code)
            rel = f"지침카드 DOC-03 {sec}" if sec else None
            if sev == "STOP":
                to = list(st["opr"].values()) + st["mnt"] + [st["sup"]] + (["U12"] if st["shift"].shift_type == "DAY" else [])
                self.add("ALARM_STOP", m, f"[긴급] {eq} 알람 {code} {name} — 설비 정지", related=rel,
                         done=self.m(rec["confirmed_at"]) if rec else None, kind="AUTO",
                         by=rec["confirmed_by"] if rec else None, to=to, alarm_event_id=e["id"], equipment_id=eq)
            elif sev == "WARN":
                self.add("ALARM_WARN", m, f"[주의] {eq} 알람 {code} {name}", related=rel,
                         done=self.m(rec["confirmed_at"]) if rec else None, kind="AUTO",
                         by=rec["confirmed_by"] if rec else None, to=[st["opr"][proc]] + st["mnt"],
                         alarm_event_id=e["id"], equipment_id=eq)
            else:
                done = e["cleared_m"] if e["cleared_m"] is not None else m + int(self.r.integers(1, 11))
                self.add("ALARM_GUIDE", m, f"{eq} 알람 {code} {name} (조작 안내)", related=rel, done=done,
                         kind="MANUAL", by=st["opr"][proc], to=[st["opr"][proc]], alarm_event_id=e["id"], equipment_id=eq)

    # ---------- 반복 알람 1·2단계 (DOC-07 10.2·10.4, ERD 6.54) ----------
    def repeats(self):
        sim, cfg = self.sim, self.cfg["notifications"]
        win = 7 * 24 * 60
        left_open = {(x["equipment_id"], x["alarm_code"]) for x in cfg["stage1_left_open"]}
        rel_pm = cfg["repeat_related_pm_section"]
        recs = self.ctx["mnt"]["work_record"]
        wos = self.ctx["mnt"]["maintenance_work_order"]
        pairs = {}
        for e in sim.alarm_events:
            if e["severity"] in cfg["repeat_counts_severity"]:  # 조작 안내 등급은 세지 않음 (설계서 5.8 "주의 알람을 흩뜨린다")
                pairs.setdefault((e["equipment_id"], e["alarm_code"]), []).append(e)
        for (eq, code), evs in sorted(pairs.items()):
            stage, cur, closed_m = 0, None, None
            for i, e in enumerate(evs):
                m = e["occurred_m"]
                if stage == 0:
                    n7 = sum(1 for x in evs[:i + 1] if m - x["occurred_m"] <= win)
                    if n7 < 3:
                        continue
                    st = self.staff(m)
                    past = [w["record_no"] for w in recs if w["alarm_event_id"] in {x["id"] for x in evs[:i]}][-2:]
                    sec = self.guide.get(code, "")
                    rel = f"지난 조치 {', '.join(past) or '없음'} · 근거 DOC-03 {sec}"
                    if code in rel_pm:
                        tasks = [t["pm_task_id"] for t in self.M["pm_task"] if t["equipment_id"] == eq
                                 and t["doc04_section"] == rel_pm[code] and t["pm_task_id"] in self.ctx["overdue"]]
                        if tasks:
                            rel += " · 관련 정비 " + ", ".join(f"{t} (기한 {self.ctx['overdue'][t]:%m/%d})" for t in tasks)
                    open_ = (eq, code) in left_open
                    done = None if open_ else self.manual(m, 30, 91)
                    by = st["mnt"][0]
                    memo = None if open_ else PLAN_MEMO.get(code, f"DOC-03 {sec} ★ 점검 줄대로 점검·조치 (담당 {by})")
                    cur = self.add("REPEAT_ALARM", m, f"[반복] {eq} 알람 {code} {self.alarm_name.get(code, code)} — 7일 안 {n7}번",
                                   related=rel, done=done, kind="MANUAL", by=by, memo=memo, to=st["mnt"] + [st["sup"]],
                                   alarm_event_id=e["id"], equipment_id=eq)
                    cur["repeat_stage_status"] = "S1_OPEN" if open_ else "S1_CLOSED"
                    stage, closed_m = 1, (None if open_ else done)
                elif closed_m is not None and closed_m <= m <= closed_m + win:
                    # 조치 계획(또는 원인 점검) 뒤 7일 안 재발 → 2단계
                    st = self.staff(m)
                    wo = next((w for w in wos if w["trigger_kind"] == "REPEAT_STAGE2" and w["equipment_id"] == eq
                               and abs(self.m(w["created_at"]) - m) <= 5), None)
                    wr = next((w for w in recs if wo and w["wo_no"] == wo["wo_no"]), None)
                    done = self.m(wr["confirmed_at"]) if wr else None
                    proc = sim.mach[eq].proc
                    rel = (f"1단계 조치 계획: {cur['process_memo']} · 그 뒤 발생 {sim.cal.to_dt(m):%m/%d %H:%M}"
                           + (f" · 원인 점검 작업지시서 {wo['wo_no']} AI비서 초안" if wo else ""))
                    n2 = self.add("REPEAT_ALARM_2", m, f"[반복 2단계] {eq} 알람 {code} — 지난 조치 효과 없음", related=rel,
                                  done=done, kind="AUTO", by=wr["confirmed_by"] if wr else None, to=st["mnt"] + [st["sup"]],
                                  alarm_event_id=e["id"], equipment_id=eq)
                    n2["_prev"] = cur
                    n2["repeat_stage_status"] = "S2_CHECKED" if done is not None else "S2_OPEN"
                    cur["repeat_stage_status"] = "ESCALATED"
                    if wo:
                        wo["_trigger"] = n2
                    if proc != "OP-30":
                        cc = self.add("CAUSE_CHECK_REQUEST", m, f"{eq} 알람 {code} 원인 점검 요청", related="DOC-03 §3",
                                      to=st["mnt"], alarm_event_id=e["id"], equipment_id=eq)
                        if cc:
                            cc["_prev"] = n2
                    cur, closed_m = n2, done
                elif closed_m is not None and m > closed_m + win:
                    if cur["repeat_stage_status"] in ("S1_CLOSED", "S2_CHECKED"):
                        cur["repeat_stage_status"] = "EFFECTIVE"
                    stage, cur, closed_m = 0, None, None
            if cur is not None and closed_m is not None and closed_m + win < self.N:
                if cur["repeat_stage_status"] in ("S1_CLOSED", "S2_CHECKED"):
                    cur["repeat_stage_status"] = "EFFECTIVE"         # 7일 동안 재발 없음 → 효과 확인

    # ---------- 공구·재고·정비 ----------
    def tools(self):
        sim = self.sim
        changes = sorted(sim.tool_changes, key=lambda c: c["changed_m"])
        start = [(t["tool_id"], 0) for t in self.M["tool"]
                 if float(t["cum_usage"]) / float({x["item_no"]: x for x in self.M["tool_type"]}[t["item_no"]]["life_limit"]) >= 0.9]
        for tid, m in start + list(sim.tool90):
            ch = next((c for c in changes if c["tool_id"] == tid and c["changed_m"] >= m), None)
            st = self.staff(m)
            eq = tid.rsplit("-", 1)[0]
            self.add("TOOL_LIFE_90", m, f"[공구] {tid} 사용률 90% — 교체 준비", related="DOC-07 9장 · DOC-01 §7",
                     done=ch["changed_m"] if ch else None, kind="AUTO", by=ch["changed_by"] if ch else None,
                     to=[st["opr"]["OP-30"], st["sup"]], tool_id=tid, equipment_id=eq)

    def stock(self):
        items = {x["item_no"]: x for x in self.M["inventory_item"]}
        keep_low = set(self.cfg["inventory"]["below_safety_at_month_end"])
        t0 = self.cal.to_dt(0)
        for it, x in items.items():
            if not x["safety_stock"]:
                continue
            safe = float(x["safety_stock"])
            tx = sorted([t for t in self.ctx["inv"] if t["item_no"] == it], key=lambda t: (t["txn_at"], t["txn_id"]))
            q = sum(t["qty_change"] for t in tx if t["txn_at"] <= t0)
            events, low_m = [], (0 if q <= safe else None)
            for t in tx:
                if t["txn_at"] <= t0:
                    continue
                q += t["qty_change"]
                mm = self.m(t["txn_at"])
                if low_m is None and q <= safe:
                    low_m = mm
                elif low_m is not None and q > safe:
                    events.append((low_m, mm, t["txn_by"]))
                    low_m = None
            if low_m is not None:
                events.append((low_m, None, None))
            for a, b, by in events:
                st = self.staff(a)
                owner = st["sup"] if x["owner_role"] == "SUP" else st["mnt"][0]
                kind, memo = "AUTO", None
                if b is None and it not in keep_low:
                    # 쓰지 않아 안전 재고 수준에 머문 품목: MGR이 확인하고 처리 (6.36 "자동 또는 사람")
                    b, by, kind, memo = self.manual(a, 60, 181), "U12", "MANUAL", "이번 달 쓸 계획 없음 — 다음 정기 주문 때 확인"
                self.add("STOCK_LOW", a, f"[재고] {x['item_name']} 재고가 안전 재고({x['safety_stock']}) 이하",
                         related=f"관리 역할 {x['owner_role']}", done=b, kind=kind, by=by, memo=memo, to=[owner, "U12"],
                         item_no=it)

    def pm(self):
        tasks = {t["pm_task_id"]: t for t in self.M["pm_task"]}
        eq_proc = {eq: mc.proc for eq, mc in self.sim.mach.items()}
        day0 = self.cal.days[0]
        due_list = []
        for p in self.ctx["pm_rows"]:
            t = tasks[p["pm_task_id"]]
            if t["cycle_code"] in self.cfg["notifications"]["pm_alert_cycles"] and p["due_date"] and p["due_date"] >= day0 and not p["memo"]:
                due_list.append((p["pm_task_id"], p["due_date"], p))
        for tid, due in self.ctx["overdue"].items():
            due_list.append((tid, due, None))
        tz = self.cal.to_dt(0).tzinfo
        for tid, due, p in due_list:
            t = tasks[tid]
            done = self.m(p["done_at"]) if p else None
            by = p["recorded_by"] if p else None
            for rule, day, txt in (("PM_DUE_SOON", due - timedelta(days=1), "기한 하루 전"),
                                   ("PM_OVERDUE", due + timedelta(days=1), "기한 넘김")):
                at = self.m(datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz))
                if rule == "PM_DUE_SOON":
                    at = self.m(datetime(day.year, day.month, day.day, 8, 0, tzinfo=tz))
                if at < 0 or (done is not None and done <= at):
                    continue
                st = self.staff(at)
                who = st["opr"][eq_proc[t["equipment_id"]]] if t["default_role"] == "OPR" else st["mnt"][0]
                self.add(rule, at, f"[정비] {t['equipment_id']} {t['item_name']} — {txt} (기한 {due:%m/%d})",
                         related=f"DOC-04 {t['doc04_section']}", done=done, kind="AUTO", by=by, to=[who, st["sup"]],
                         pm_task_id=tid, equipment_id=t["equipment_id"])

    # ---------- 생산 ----------
    def bottleneck(self):
        for x in self.ctx["bn"]:
            m = x["_m"]
            st = self.staff(m)
            c = x["cause_code"]
            rel = f"DOC-07 §7.5 원인 {CAUSE_NO[c]} 조치 줄" if c in CAUSE_NO else ("DOC-03 고장 대응" if c == "FAILURE" else None)
            self.add("BOTTLENECK_MOVE", m, f"[병목] {x['prev_process_code']} → {x['new_process_code']} ({CAUSE_KO[c]})",
                     related=rel, done=self.manual(m), kind="MANUAL", by=self.staff(self.nx(m))["sup"], to=[st["sup"]],
                     bottleneck_log_id=x["bottleneck_log_id"])

    def wip(self):
        for b in self.M["wip_buffer"]:
            if b["warn_enabled"] != "true" or not b["warn_over_qty"]:
                continue
            warn = int(b["warn_over_qty"])
            arr = self.sim.wip_min[b["buffer_code"]]
            above = arr[:self.N] > warn
            starts = np.where(above & ~np.concatenate([[False], above[:-1]]))[0]
            seen = set()
            for m in starts:
                m = int(m)
                st = self.staff(m)
                if st["shift"].shift_id in seen:
                    continue                                   # 재공 위치마다 교대에 처음 1번 (그 뒤는 화면 숫자 주황만) [가상]
                seen.add(st["shift"].shift_id)
                done = self.manual(m)
                lim = b["limit_qty"]
                txt = (f"재공 {int(arr[m])}개 — 한도 {lim} 도달, 앞 공정 막힘" if int(arr[m]) >= int(lim)
                       else f"재공 {int(arr[m])}개 — 경고 기준 {warn}개 초과")
                self.add("WIP_WARN", m, f"[재공] {b['buffer_code']} {txt}", related="DOC-07 §7.2",
                         done=done, kind="MANUAL", by=self.staff(self.nx(m))["sup"], to=[st["sup"]],
                         buffer_code=b["buffer_code"])

    def target(self):
        """목표 미달 위험 (DOC-07 8장): 예측 실적 < 총 목표의 90%. 교대마다 처음 걸린 때 1건."""
        good = np.array(sorted(p.start["done"] for p in self.sim.finished
                               if not (p.defect and p.defect[2] == "SCRAP")))
        cal = self.cal
        for sh in cal.shifts:
            a, b = cal.to_min(sh.start), cal.to_min(sh.end)
            total = sh.target_qty + sh.carry_over_qty
            elapsed = 0
            for m in range(a, b):
                if not cal.is_work(m):
                    continue
                elapsed += 1
                if elapsed <= self.cfg["notifications"]["target_risk_from_min"]:
                    continue                                   # 시작 직후 1시간은 예측이 흔들림 → 알림은 그 뒤부터 [가상]
                actual = int(np.searchsorted(good, m, "right") - np.searchsorted(good, a))
                if elapsed < 60:
                    rate = actual / elapsed
                else:
                    rate = int(np.searchsorted(good, m, "right") - np.searchsorted(good, m - 60, "right")) / 60
                pred = actual + rate * (sh.planned_min - elapsed)
                if pred < 0.9 * total:
                    self.add("TARGET_RISK", m, f"[목표] {sh.shift_id} 예측 실적 {pred:.0f}개 < 총 목표 {total}개의 90%",
                             related=f"지금 {actual}개 / 남은 시간 {sh.planned_min - elapsed}분", done=self.manual(m),
                             kind="MANUAL", by=sh.supervisor, to=[sh.supervisor], shift_id=sh.shift_id)
                    break

    def lot_due(self):
        heads = {h["shipment_no"]: h for h in self.ctx["ship_heads"]}
        holds = {h["lot"].lot_no: h for h in self.sim.holds_log}
        tz = self.cal.to_dt(0).tzinfo
        for ln in self.ctx["ship_lines"]:
            h = heads[ln["shipment_no"]]
            if h["shipped_at"].date() <= h["due_date"]:
                continue
            hd = holds.get(ln["lot_no"])
            m = hd["held_m"] if hd else self.m(datetime(h["due_date"].year, h["due_date"].month, h["due_date"].day, 8, 0, tzinfo=tz))
            st = self.staff(m)
            self.add("LOT_DUE_RISK", m, f"[납기] {ln['lot_no']} 예상 완료가 납기 {h['due_date']:%m/%d}보다 늦음",
                     related="보류 로트 — 판정 뒤 출하" if hd else None, done=self.manual(m), kind="MANUAL",
                     by=self.staff(self.nx(m))["sup"], to=[st["sup"], "U12"], lot_no=ln["lot_no"])

    # ---------- 문서 ----------
    def documents(self, reps, rev_info, revs):
        mnt = self.ctx["mnt"]
        for w in mnt["maintenance_work_order"]:
            c, ap = self.m(w["created_at"]), self.m(w["approved_at"])
            self.add("WO_DRAFT_READY", c, f"[문서] 작업지시서 {w['wo_no']} AI비서 초안 — 검토해 주세요",
                     done=self.m(rev_info["wo_saved"][w["wo_no"]]), kind="AUTO", by=w["assignee_user_id"],
                     to=[w["assignee_user_id"]], wo_no=w["wo_no"], equipment_id=w["equipment_id"])
            for rule, wait in (("APPROVAL_WAIT_30M", 30), ("APPROVAL_WAIT_2H", 120)):
                if ap - c >= wait:
                    self.add(rule, c + wait, f"[문서] 작업지시서 {w['wo_no']} 승인 대기 {wait}분 넘음", done=ap,
                             kind="AUTO", by=w["approved_by"], to=[w["approved_by"]], wo_no=w["wo_no"])
            self.add("WO_ASSIGNED", ap, f"[문서] 작업지시서 {w['wo_no']}이 승인되어 배정됨",
                     done=ap + int(self.r.integers(1, 6)), kind="AUTO", by=w["assignee_user_id"],
                     to=[w["assignee_user_id"]], wo_no=w["wo_no"], equipment_id=w["equipment_id"])
        for s in reps["shift_report"]:
            sh = reps["meta"][s["shift_id"]]["shift"]
            first_conf = s["confirmed_at"]                    # 확정 뒤 고친 보고서도 처음 확정 때 처리됨
            self.add("SHIFT_REPORT_PENDING", self.m(sh.end), f"[문서] {s['shift_id']} 교대 보고서 AI비서 초안 — 확정해 주세요",
                     done=self.m(first_conf) if first_conf else None, kind="AUTO", by=s["confirmed_by"],
                     to=[sh.supervisor], shift_id=s["shift_id"])
        for d in reps["daily_report"]:
            done = self.m(d["confirmed_at"]) if d["confirmed_at"] else None
            self.add("DAILY_REPORT_PENDING", self.m(d["_created_at"]),
                     f"[문서] {d['work_date']:%m/%d} 일일 보고서 AI비서 초안 — 확정해 주세요", done=done, kind="AUTO",
                     by="U12" if done is not None else None, to=["U12"], revision_id=d["_rev0"])
        for x in rev_info["revised"]:
            m = self.m(x["at"])
            self.add("DOC_REVISED", m, f"[문서] 확정된 교대 보고서 {x['doc_key']}가 사유와 함께 고쳐짐",
                     done=self.manual(m, 10, 121), kind="AUTO", by="U12", to=["U12"], revision_id=x["revision_id"])

    # ---------- 품질 ----------
    def spc(self, insp):
        """관리도 이상 (DOC-06 5.3): I-MR, 한계 = x̄ ± 3·MR̄/1.128 (9월 측정값으로), 점 1개가 한계 밖."""
        by_item = {}
        for x in insp:
            if x["input_method"] != "CMM_AUTO" or x["position"] not in (None, "MID") or x["remeasure_seq"] != 1:
                continue
            by_item.setdefault(x["item_seq"], []).append(x)
        for seq, xs in sorted(by_item.items()):
            xs.sort(key=lambda x: (x["measured_at"], x["result_id"]))
            v = np.array([float(x["measured_value"]) for x in xs])
            if len(v) < 50:
                continue                                     # 50개 미만은 판정하지 않음 (DOC-06 §5.2)
            mr = np.abs(np.diff(v)).mean()
            ucl, lcl = v.mean() + 3 * mr / 1.128, v.mean() - 3 * mr / 1.128
            for i, x in enumerate(xs):
                if lcl <= v[i] <= ucl:
                    continue
                m = self.m(x["measured_at"])
                nxt = xs[i + 1] if i + 1 < len(xs) else None
                st = self.staff(m)
                self.add("SPC_OUT", m, f"[품질] 항목 {seq} 측정값 {v[i]} — 관리 한계({lcl:.3f}~{ucl:.3f}) 밖",
                         related="DOC-06 5.3 — 다음 부품 바로 측정", done=self.m(nxt["measured_at"]) if nxt else None,
                         kind="AUTO", by=nxt["inspector_id"] if nxt else None, to=[st["sup"]], result_id=x["result_id"],
                         lot_no=x["lot_no"])

    def open_at(self, m: int) -> list[dict]:
        return [x for x in self.rows if x["_m"] <= m and (x["_pm"] is None or x["_pm"] > m)]

    # ---------- 마무리 ----------
    def finish(self):
        order = list(self.rule)
        self.rows.sort(key=lambda x: (x["_m"], order.index(x["rule_code"])))
        cal = self.cal
        out, rec = [], []
        for i, x in enumerate(self.rows, 1):
            x["notification_id"] = i
        for x in self.rows:
            x["raised_at"] = cal.to_dt(x["_m"])
            x["processed_at"] = cal.to_dt(x["_pm"]) if x["_pm"] is not None else None
            if "_prev" in x:
                x["prev_stage_notification_id"] = x["_prev"]["notification_id"]
            out.append(x)
            for u in x["_to"]:
                if x["_pm"] is not None and x["processed_by"] == u:
                    read = x["_pm"] - int(self.r.integers(0, 3))
                else:
                    read = self.nx(x["_m"]) + int(self.r.integers(0, 16))
                read = max(read, x["_m"])
                rec.append({"notification_id": x["notification_id"], "user_id": u,
                            "popup_sound": x["rule_code"] == "ALARM_STOP",
                            "read_at": cal.to_dt(read) if read < self.N else None})
        for w in self.ctx["mnt"]["maintenance_work_order"]:
            if "_trigger" in w:
                w["trigger_notification_id"] = w.pop("_trigger")["notification_id"]
        return out, rec


def start(cfg, sim, masters, rng, ctx, insp) -> Builder:
    """운영 알림 (보고서보다 먼저 — 교대 보고서 인계 사항이 '그 시각에 처리 안 된 알림'을 씀)."""
    b = Builder(cfg, sim, masters, rng, ctx)
    b.alarms()
    b.repeats()
    b.tools()
    b.stock()
    b.pm()
    b.bottleneck()
    b.wip()
    b.target()
    b.lot_due()
    b.spc(insp)
    ctx["open_at"] = b.open_at
    return b


def finish(b: Builder, reps, rev_info, revs):
    """문서 알림 (보고서·버전 뒤) + 번호 매기기."""
    b.documents(reps, rev_info, revs)
    return b.finish()
