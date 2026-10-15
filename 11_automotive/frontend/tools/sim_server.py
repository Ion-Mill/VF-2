"""시연 데이터 서버 — 생성기 실시간 모드(10/1)와 과거 기록(9월)을 화면에 내준다.

API명세서_v1 2.9 "생성기와 잇는 방법" [제안] 그대로: 서버가 Realtime 객체를 만들고 실제 시간마다 tick(초)를 부른다.
서버 방식(프레임워크·DB)은 [선택 필요: 기술 회의] — 여기서는 Python 표준 라이브러리만 쓴다 (생성기 가상환경 그대로).

실행 (데이터적용본 폴더에서):
  ..\\생성기\\.venv\\Scripts\\python tools\\sim_server.py        → http://127.0.0.1:8765
화면(npm run dev)은 next.config.mjs rewrites로 /api/* 를 이 서버에 넘긴다.
"""
from __future__ import annotations

import io
import json
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # 11_automotive
GEN = ROOT / "생성기"
sys.path.insert(0, str(GEN))
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from gen.common import KST, fmt_dt, load_config, load_masters  # noqa: E402
from gen.realtime import Realtime  # noqa: E402
from server_assistant import answer  # noqa: E402
from server_live import Live, iso  # noqa: E402
from server_past import Past  # noqa: E402

PORT = 8765
TICK_SEC = 0.25
NO_STREAM = {"sensor"}                      # 센서는 /api/line/twin 의 equipment[].sensor 로 (1분마다 2건이라 흐름에서 뺌)


class ApiError(Exception):
    def __init__(self, status, code, message, detail=None):
        super().__init__(message)
        self.status, self.code, self.message, self.detail = status, code, message, detail or {}


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.cfg = load_config()
        self.M = load_masters(self.cfg)
        print("과거 기록 읽는 중 …")
        self.P = Past(ROOT)
        data = HERE / "data.json"
        self.alarms = json.loads(data.read_text(encoding="utf-8"))["alarms"] if data.exists() else {}
        print("실시간 모드 준비 중 (10/1 08:00, 약 2초) …")
        self.rt = Realtime(self.cfg, self.M)
        self.live = Live(self.rt, self.P)
        self.run_id = 1
        self.seq = 0
        self.buf: list[dict] = []
        self.reports: dict[str, dict] = {}       # 교대 보고서 사람 수정·확정 (API-RPT-02·03·04)
        self.daily: dict[str, dict] = {}         # 일일 보고서 확정 (API-RPT-05)
        self.revs: list[dict] = []               # 10/1에 생긴 문서 버전 (SCR-17)
        self.ships: list[dict] = []              # 10/1 출하 기록 (API-INV-04)
        self.pm_open: dict[str, dict] = {}       # [정비 시작]한 설비
        # 알림 규칙 값 (SCR-25 [2], DOC-07 10장) — 바꾸면 화면 규칙 엔진이 이 값을 쓴다
        self.rule_values = {"repeat_days": 7, "repeat_count": 3, "burst": "1분 안 3번 이상", "flood": "10분 10건 / 5건",
                            "target_risk_pct": 90, "repeat2_days": 7}
        self.settings_log: list[dict] = []
        self.connected_at = time.time()
        self._push(self.rt.events)

    def _push(self, evs):
        for e in evs:
            if e["type"] in NO_STREAM:
                continue
            self.seq += 1
            self.buf.append({"seq": self.seq, **json.loads(json.dumps(e, ensure_ascii=False, default=str))})
        if len(self.buf) > 5000:
            del self.buf[: len(self.buf) - 5000]

    def tick(self, dt):
        with self.lock:
            n0 = len(self.rt.events)
            self.rt.tick(dt)
            self._push(self.rt.events[n0:])

    def reset(self):
        with self.lock:
            n0 = len(self.rt.events)
            self.rt.reset()
            self.live = Live(self.rt, self.P)
            self.run_id += 1
            self.reports.clear()
            self.daily.clear()
            self.revs.clear()
            self.ships.clear()
            self.pm_open.clear()
            self._push(self.rt.events[n0:] if len(self.rt.events) > n0 else self.rt.events)


S: State | None = None


def ticker():
    last = time.monotonic()
    while True:
        time.sleep(TICK_SEC)
        now = time.monotonic()
        try:
            S.tick(now - last)
        except Exception:
            traceback.print_exc()
        last = now


def sim_min(q: dict, key: str, default: int) -> int:
    v = (q.get(key) or [None])[0]
    if not v:
        return default
    return S.rt.sim.cal.to_min(datetime.fromisoformat(v).astimezone(KST))


_CSV = {}


def read_csv_once(name):
    if name not in _CSV:
        from server_past import read
        _CSV[name] = read(GEN / "out" / f"{name}.csv")
    return _CSV[name]


def user_name(uid):
    u = S.P.users.get(uid or "")
    return u["user_name"] if u else uid


# ---------- API ----------
def route(method: str, path: str, q: dict, body: dict):
    rt, live, P = S.rt, S.live, S.P
    parts = [unquote(p) for p in path.strip("/").split("/")]
    if parts[:1] != ["api"]:
        raise ApiError(404, "NOT_FOUND", "없는 주소")
    p = parts[1:]
    with S.lock:
        n0 = len(rt.events)
        try:
            return _route(method, p, q, body, rt, live, P)
        finally:
            if len(rt.events) > n0:
                S._push(rt.events[n0:])


def _route(method, p, q, body, rt, live, P):
    key = "/".join(p)
    # 시연 시계·사건 버튼 (API-SIM-01~03)
    if key == "health":
        return {"ok": True, "run_id": S.run_id, "clock": rt.clock()}
    if key == "sim/clock":
        if method == "POST":
            try:
                if "speed" in body:
                    rt.set_speed(int(body["speed"]))
                if body.get("paused") is True:
                    rt.pause()
                if body.get("paused") is False:
                    rt.resume()
                if body.get("skip"):
                    rt.skip(body["skip"])
            except ValueError as e:
                raise ApiError(409, "INVALID_STATE", str(e))
        return {**rt.clock(), "buttons": rt.button_state(), "run_id": S.run_id}
    if key == "sim/inject" and method == "POST":
        try:
            ev = rt.inject(body.get("scenario_code", ""))
        except ValueError as e:
            raise ApiError(409, "INVALID_STATE", str(e))
        return {"event": {k: v for k, v in ev.items() if k in ("code", "equipment_id", "start_m")}, "started_at": fmt_dt(rt.now())}
    if key == "sim/reset" and method == "POST":
        S.reset()
        return {"run_id": S.run_id, **S.rt.clock()}
    # 실시간 흐름 (API-STR-01) — 전송 방식은 [선택 필요], 여기서는 화면이 뒤 번호를 주고 물어보는 방식
    if key == "stream/events":
        after = int((q.get("after") or ["0"])[0])
        return {"run_id": S.run_id, "seq": S.seq, "events": [e for e in S.buf if e["seq"] > after][-800:]}
    # 3D 라인 뷰·생산 (API-LINE-01~07)
    if key == "line/twin":
        t = live.twin()
        t["run_id"] = S.run_id
        t["production"] = live.production()
        t["kpi"] = live.kpi()
        t["orders"] = live.orders()
        return t
    if key == "production/target":
        return live.production()
    if key == "kpi":
        return live.kpi(sim_min(q, "from", None) if q.get("from") else None, sim_min(q, "to", None) if q.get("to") else None)
    if key == "production/orders":
        return {"orders": live.orders()}
    if key == "replay":
        b = sim_min(q, "to", rt.m)
        a = sim_min(q, "from", b - 120)
        if b - a > 24 * 60:
            raise ApiError(400, "VALIDATION", "다시 보기는 한 번에 24시간까지")
        return live.replay(a, b)
    if key == "downtimes":
        a = sim_min(q, "from", rt.sim.cal.to_min(live.shift().start))
        out = []
        for eq in ("SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01"):
            for s, e, st in live.runs(eq, a, rt.m):
                if st and st[0] != "RUN":
                    out.append({"equipment_id": eq, "state_code": st[0], "start_at": iso(live.to_dt(s)),
                                "end_at": iso(live.to_dt(e)) if e < rt.m else None, "minutes": e - s,
                                "reason_suggested_code": st[1], "alarm_event_id": st[3]})
        return {"downtimes": out}
    # 알림 (과거 미처리 → 10/1 시작 상태)
    if key == "notifications/past-open":
        return {"notifications": P.open_notifications(fmt_dt(rt.sim.cal.to_dt(rt.N)))}
    if key == "notifications/rules":
        return {"rules": P.rules}
    # 비서 (API-AST-02), 사내 문서 (API-DOCS-01)
    if key == "assistant/chat" and method == "POST":
        return answer(body.get("question", ""), body.get("role", "OPR"), body.get("context") or {}, live, P, S.alarms)
    if key == "internal-docs":
        return {"docs": [{k: d[k] for k in ("doc_no", "doc_name", "rev", "rev_date")} | {"sections": [{"section": s["section"], "title": s["title"], "level": s["level"]} for s in d["sections"]]}
                         for d in P.docs.values()]}
    if key == "internal-docs/search":
        return {"hits": P.search((q.get("q") or [""])[0], 8)}
    if len(p) == 2 and p[0] == "internal-docs":
        if p[1] not in P.docs:
            raise ApiError(404, "NOT_FOUND", "없는 사내 문서")
        return P.docs[p[1]]
    if len(p) == 4 and p[0] == "internal-docs" and p[2] == "sections":
        hit = P.doc_section(p[1], p[3])
        if not hit:
            raise ApiError(404, "NOT_FOUND", "없는 절")
        d, s = hit
        view = (q.get("view") or ["card"])[0]
        from server_past import snippet
        return {"doc_no": d["doc_no"], "doc_name": d["doc_name"], "rev": d["rev"], "section": s["section"], "title": s["title"],
                "text": snippet(s["text"]) if view == "card" else s["text"]}
    # 정비 (API-MNT-11 시연 연결, API-PM-01)
    if key == "maint/work-records/confirm" and method == "POST":
        try:
            rt.confirm_work_record(body.get("equipment_id", "VF2-01"), by=body.get("by", "U07"))
        except ValueError as e:
            raise ApiError(409, "INVALID_STATE", str(e))
        return {"ok": True}
    if key == "maint/pm-schedule":
        return live.pm()
    if key == "maint/history":
        return {"work_orders": P.work_orders, "steps": P.wo_steps, "work_records": P.work_records, "checks": P.wr_checks,
                "parts": P.wr_parts, "alarms": P.alarms}
    # 보고서 (API-RPT-01~05)
    if key == "reports/shift":
        live_ids = [s.shift_id for s in rt.sim.cal.shifts if s.work_date >= rt.sim.cal.to_dt(rt.N).date()]
        rows = []
        for r in P.shift_reports:
            rows.append({**r, **({} if r["shift_id"] not in S.reports else S.reports[r["shift_id"]])})
        for sid in live_ids:
            d = S.reports.get(sid) or live.shift_draft(sid)
            if d:
                rows.append({k: v for k, v in d.items() if k not in ("stops",)})
        return {"reports": rows}
    if len(p) >= 3 and p[:2] == ["reports", "shift"]:
        sid = p[2]
        cur = S.reports.get(sid) or next((dict(r) for r in P.shift_reports if r["shift_id"] == sid), None) or live.shift_draft(sid)
        if cur is None:
            raise ApiError(404, "NOT_FOUND", "없는 교대")
        if method == "GET":
            # 숫자 칸(가동률·필수 정지·로트·병목)은 시뮬레이터 상태 기록으로 다시 계산 (9월도 같은 식) — 문장 칸은 보고서 그대로
            comp = live.shift_draft(sid) or {}
            extra = {k: comp.get(k) for k in ("availability", "stops", "lots", "bottleneck", "partial")}
            sh = next((s for s in rt.sim.cal.shifts if s.shift_id == sid), None)
            if sh:
                extra.update({"start_at": iso(sh.start), "end_at": iso(sh.end), "supervisor_user_id": sh.supervisor, "shift_type": sh.shift_type})
            return {**cur, **extra, "revisions": [x for x in P.revisions if x["doc_type"] == "SHIFT_REPORT" and x["doc_key"] == sid] + [x for x in S.revs if x["doc_key"] == sid],
                    "changes": {x["revision_id"]: P.rev_changes.get(x["revision_id"], []) for x in P.revisions if x["doc_type"] == "SHIFT_REPORT" and x["doc_key"] == sid}}
        role = body.get("role")
        if role not in ("SUP", "MGR"):
            raise ApiError(403, "FORBIDDEN", "교대 보고서는 그 교대 반장만 고칠 수 있어요")
        if int(body.get("version", -1)) != int(cur.get("current_version") or 0):
            raise ApiError(409, "CONFLICT_VERSION", "다른 사람이 먼저 고쳤어요. 다시 열어 주세요")
        action = p[3] if len(p) > 3 else "save"
        if cur.get("status") == "CONFIRMED" and action != "revise":
            raise ApiError(409, "INVALID_STATE", "확정된 보고서예요. 고치려면 사유와 함께 확정 후 수정")
        if action == "revise" and not body.get("reason"):
            raise ApiError(400, "VALIDATION", "확정 후 수정에는 사유가 필요해요")
        changes = []
        for f in ("notable_text", "handover_text"):
            if f in body and body[f] != cur.get(f):
                changes.append({"field_name": f, "before_value": cur.get(f), "after_value": body[f]})
                cur[f] = body[f]
        ver = int(cur.get("current_version") or 0) + 1
        cur["current_version"] = ver
        if action == "confirm":
            cur["status"], cur["confirmed_by"], cur["confirmed_at"] = "CONFIRMED", body.get("user_id"), fmt_dt(rt.now())
        elif action == "revise":
            cur["status"] = "CONFIRMED"
        else:
            cur["status"] = "EDITING" if cur.get("status") in ("AI_DRAFT", "EDITING") else cur.get("status")
        S.reports[sid] = cur
        S.revs.append({"revision_id": f"L{len(S.revs) + 1}", "doc_type": "SHIFT_REPORT", "doc_key": sid, "version_no": ver,
                       "author_kind": "USER", "author_user_id": body.get("user_id"), "created_at": fmt_dt(rt.now()),
                       "reason": body.get("reason"), "status_after": cur["status"], "changes": changes})
        return cur
    if key == "reports/daily":
        rows = [{**r, **S.daily.get(r["work_date"], {})} for r in P.daily_reports]
        ld = live_daily("2026-10-01")
        if ld:
            rows.append({**ld, **S.daily.get(ld["work_date"], {})})
        return {"reports": rows}
    if len(p) >= 3 and p[:2] == ["reports", "daily"]:
        d = p[2]
        cur = next((dict(r) for r in P.daily_reports if r["work_date"] == d), None) or live_daily(d)
        if cur is None:
            raise ApiError(404, "NOT_FOUND", "없는 날짜")
        cur.update(S.daily.get(d, {}))
        if method == "GET":
            cal = rt.sim.cal
            day = next((s for s in cal.shifts if s.shift_id == f"{d}-D"), None)
            night = next((s for s in cal.shifts if s.shift_id == f"{d}-N"), None)
            comp = {}
            if day and night:
                a, b = cal.to_min(day.start), min(cal.to_min(night.end), rt.m)
                comp = {"stops": live.stops(a, b), "kpi": live.kpi(a, b)["by"], "range": [iso(day.start), iso(night.end)],
                        "alarms": [live.alarm_json(e) for e in rt.sim.alarm_events if a <= e["occurred_m"] < b]}
            return {**cur, **comp, "revisions": [x for x in P.revisions if x["doc_type"] == "DAILY_REPORT" and x["doc_key"] == d] + [x for x in S.revs if x["doc_key"] == d],
                    "changes": {x["revision_id"]: P.rev_changes.get(x["revision_id"], []) for x in P.revisions if x["doc_type"] == "DAILY_REPORT" and x["doc_key"] == d}}
        if body.get("role") != "MGR":
            raise ApiError(403, "FORBIDDEN", "일일 보고서 확정은 관리자만")
        upd = {"status": "CONFIRMED", "confirmed_by": body.get("user_id"), "confirmed_at": fmt_dt(rt.now()),
               "current_version": int(cur.get("current_version") or 0) + 1}
        if body.get("memo"):
            upd["issues_summary"] = cur["issues_summary"] + " / 관리자 메모: " + body["memo"]
        S.daily[d] = upd
        S.revs.append({"revision_id": f"L{len(S.revs) + 1}", "doc_type": "DAILY_REPORT", "doc_key": d, "version_no": upd["current_version"],
                       "author_kind": "USER", "author_user_id": body.get("user_id"), "created_at": upd["confirmed_at"], "reason": None,
                       "status_after": "CONFIRMED", "changes": []})
        return {**cur, **upd}
    if key == "documents/revisions":
        return {"revisions": P.revisions[-200:] + S.revs, "changes": {k: v for k, v in P.rev_changes.items()}}
    # 로트·품질 (API-LOT-01~02, API-QLT-01·04·05)
    if key == "lots":
        ship = {}
        for s in [{**x, "lines": P.ship_lines.get(x["shipment_no"], [])} for x in P.shipments] + S.ships:
            for x in s["lines"]:
                d = ship.setdefault(x["lot_no"], {"qty": 0, "shipments": []})
                d["qty"] += int(x["qty"])
                d["shipments"].append({"shipment_no": s["shipment_no"], "customer_code": s["customer_code"], "shipped_at": s["shipped_at"]})
        lots = live.lots()
        for l in lots:
            l["shipped"] = ship.get(l["lot_no"], {"qty": 0, "shipments": []})
        mats = {m["material_lot_no"]: m for m in read_csv_once("raw_material_lot")}
        return {"lots": lots, "suspect_lot": rt.suspect_lot(), "past_holds": P.holds, "materials": mats,
                "reports": [{k: x[k] for k in ("lot_no", "process_code", "equipment_id", "worker_user_id", "shift_id", "start_m", "end_m", "pq", "gq", "rq", "sq")}
                            | {"start_at": iso(rt.sim.cal.to_dt(x["start_m"])), "end_at": iso(rt.sim.cal.to_dt(x["end_m"] + 1))} for x in rt.sim.reports.values()
                            if x["lot_no"] == (q.get("lot") or [""])[0]],
                "alarms": [live.alarm_json(e) for e in rt.sim.alarm_events if e.get("lot_no") == (q.get("lot") or [""])[0]]}
    if len(p) == 3 and p[0] == "lots" and p[2] in ("hold", "release") and method == "POST":
        if body.get("role") not in ("SUP", "MGR"):
            raise ApiError(403, "FORBIDDEN", "로트 보류·해제는 반장·관리자만")
        try:
            if p[2] == "hold":
                rt.hold_lot(p[1], by=body.get("user_id", "U10"), reason=body.get("reason") or None)
            else:
                rt.release_lot(p[1], by=body.get("user_id", "U10"), approver=body.get("approver", "U12"))
        except ValueError as e:
            raise ApiError(409, "INVALID_STATE", str(e))
        return {"ok": True}
    if key == "inspection/results":
        lot = (q.get("lot") or [""])[0]
        rows = [dict(r) for r in P.insp.get(lot, [])] + [{k: (iso(v) if hasattr(v, "isoformat") and not isinstance(v, str) else v) for k, v in r.items()}
                                                         for r in rt.insp_rows if r["lot_no"] == lot]
        return {"lot_no": lot, "results": rows, "plan": P.plans.get(lot)}
    if key == "inspection/cmm-imports":
        live_rows = [{k: (iso(v) if hasattr(v, "isoformat") and not isinstance(v, str) else v) for k, v in r.items()} for r in rt.cmm_rows]
        return {"imports": (P.cmm[-60:] + live_rows)[::-1][:80], "errors_30d": [r for r in P.cmm if r["status"] != "SUCCESS"],
                "counts": {"past": len(P.cmm), "today": len(live_rows)}}
    if key == "quality/summary":
        return quality_summary(P, rt)
    # 재고·출하·공구 (API-INV-01·04, API-TOOL-01·02)
    if key == "inventory":
        return {**live.inventory(), "past_txns": P.inv_txns[-80:]}
    if key == "shipments" and method == "GET":
        return {"shipments": [{**s, "lines": P.ship_lines.get(s["shipment_no"], [])} for s in P.shipments] + S.ships}
    if key == "tools":
        return {**live.tools(), "past_changes": P.tool_changes[-40:]}
    if len(p) == 3 and p[0] == "tools" and p[2] == "change" and method == "POST":
        if body.get("role") not in ("OPR", "MNT"):
            raise ApiError(403, "FORBIDDEN", "공구 교체 기록은 작업자·보전 담당자만")
        try:
            rt.record_tool_change(p[1], by=body.get("user_id"))
        except ValueError as e:
            raise ApiError(409, "INVALID_STATE", str(e))
        return {"ok": True}
    if key == "inventory/txns" and method == "POST":
        # API-INV-02 입고·실사 조정 — 그 품목의 관리 역할만 (정비 소모품 MNT / 공구·원자재·완제품 SUP)
        item = next((i for i in rt.M["inventory_item"] if i["item_no"] == body.get("item_no")), None)
        if not item:
            raise ApiError(400, "VALIDATION", "없는 품목")
        use = body.get("txn_type") == "USE"   # 사용 기록(작업기록서·간이 기록·정비)은 기록을 쓴 MNT·OPR, 입고·조정은 관리 역할만
        if (use and body.get("role") not in ("MNT", "OPR")) or (not use and body.get("role") != item["owner_role"]):
            raise ApiError(403, "FORBIDDEN", f"이 품목은 {item['owner_role']}가 관리해요" if not use else "사용 기록은 작업자·보전 담당자만")
        q = float(body.get("qty") or 0)
        if use:
            q = -abs(q)
        if not q or (body.get("txn_type") == "IN" and q < 0):
            raise ApiError(400, "VALIDATION", "수량을 넣어 주세요")
        if body.get("txn_type") == "ADJUST" and not body.get("memo"):
            raise ApiError(400, "VALIDATION", "실사 조정에는 사유가 필요해요")
        live.extra_txns = getattr(live, "extra_txns", []) + [{"item_no": item["item_no"], "txn_type": body.get("txn_type", "IN"), "qty_change": q,
                                                             "txn_at": fmt_dt(rt.now()), "txn_by": body.get("user_id"), "source_kind": "SCREEN", "memo": body.get("memo")}]
        return {"ok": True}
    if key == "shipments" and method == "POST":
        # API-INV-04 출하 등록·확정 (SUP) — 합격·해제 로트만, 남은 수량 이하, FIFO가 아니면 사유
        if body.get("role") != "SUP":
            raise ApiError(403, "FORBIDDEN", "출하 등록은 반장만")
        lots = {l.lot_no: l for l in rt.sim.lots}
        shipped = {}
        for s in P.shipments:
            for x in P.ship_lines.get(s["shipment_no"], []):
                shipped[x["lot_no"]] = shipped.get(x["lot_no"], 0) + int(x["qty"])
        for s in S.ships:
            for x in s["lines"]:
                shipped[x["lot_no"]] = shipped.get(x["lot_no"], 0) + int(x["qty"])
        from gen import stage4 as S4
        lines = []
        for x in body.get("lines") or []:
            l = lots.get(x["lot_no"])
            if not l or S4.lot_status(rt.sim, l) not in ("PASSED", "RELEASED"):
                raise ApiError(409, "INVALID_STATE", f"{x['lot_no']}은(는) 합격·해제 로트가 아니라 출하할 수 없어요")
            if int(x["qty"]) > l.fg_qty - shipped.get(l.lot_no, 0):
                raise ApiError(409, "INVALID_STATE", f"{x['lot_no']} 남은 수량보다 많아요")
            lines.append({"lot_no": l.lot_no, "qty": int(x["qty"])})
        if not lines:
            raise ApiError(400, "VALIDATION", "로트 줄이 없어요")
        no = f"SHP-2610-{len(S.ships) + 1:03d}"
        sh = {"shipment_no": no, "shipped_at": fmt_dt(rt.now()), "customer_code": body.get("customer_code", "CUST-01"), "due_date": body.get("due_date"),
              "confirmed_by": body.get("user_id"), "status": "CONFIRMED", "fifo_skip_reason": body.get("fifo_skip_reason") or None, "memo": body.get("memo"),
              "current_version": 0, "lines": lines}
        S.ships.append(sh)
        live.extra_txns = getattr(live, "extra_txns", []) + [{"item_no": "FG-BRK-A100", "txn_type": "SHIP", "qty_change": -sum(x["qty"] for x in lines),
                                                             "txn_at": sh["shipped_at"], "txn_by": body.get("user_id"), "source_kind": "SHIPMENT", "shipment_no": no}]
        return sh
    if key == "maint/pm-start" and method == "POST":
        # API-PM-02 [정비 시작] — 그 설비가 MAINT(정비)로 기록된다. 고장으로 세지 않는다 (기록 버튼, 설비 조작 아님)
        if body.get("role") != "MNT":
            raise ApiError(403, "FORBIDDEN", "예방 정비 기록은 보전 담당자만")
        from datetime import date as _d
        from gen.plan import MaintWindow
        eq = body.get("equipment_id")
        if eq not in rt.sim.mach:
            raise ApiError(400, "VALIDATION", "없는 설비")
        w = MaintWindow(eq, rt.m, rt.m + int(body.get("minutes") or 60), "PM_SCREEN", body.get("pm_task_ids") or [], _d.fromisoformat(fmt_dt(rt.now())[:10]))
        rt.sim.maint.append(w)
        rt.sim.maint.sort(key=lambda x: x.start_m)
        S.pm_open[eq] = {"window": w, "tasks": body.get("pm_task_ids") or [], "by": body.get("user_id"), "start_at": fmt_dt(rt.now())}
        return {"ok": True}
    if key == "maint/pm-end" and method == "POST":
        if body.get("role") != "MNT":
            raise ApiError(403, "FORBIDDEN", "예방 정비 기록은 보전 담당자만")
        eq = body.get("equipment_id")
        op = S.pm_open.pop(eq, None)
        mc = rt.sim.mach.get(eq)
        if mc:
            for h in mc.holds:
                if h.kind == "MAINT":
                    h.end = rt.m
                    if h.maint_ref:
                        h.maint_ref["end_m"] = rt.m
        for tid in body.get("pm_task_ids") or (op["tasks"] if op else []):
            rt.pm_rows.append({"pm_record_id": f"L{len(rt.pm_rows) + 1}", "pm_task_id": tid, "due_date": fmt_dt(rt.now())[:10], "done_at": rt.now(),
                               "done_by": body.get("done_by") or body.get("user_id"), "recorded_by": body.get("user_id"), "result": body.get("result", "NORMAL"),
                               "measured_value": None, "measured_unit": None, "memo": body.get("memo") or "화면 실시 기록", "status": "CONFIRMED", "current_version": 0})
        for it in body.get("items") or []:
            live.extra_txns = getattr(live, "extra_txns", []) + [{"item_no": it["item_no"], "txn_type": "USE", "qty_change": -abs(float(it["qty"])),
                                                                 "txn_at": fmt_dt(rt.now()), "txn_by": body.get("user_id"), "source_kind": "PM_RECORD"}]
        return {"ok": True}
    if key == "settings" and method == "GET":
        return {"targets": {"shift": getattr(live, "target_override", None) or 90, "daily": 180}, "safety": getattr(live, "safety_override", {}),
                "rules": S.rule_values, "log": S.settings_log}
    if key == "settings" and method == "POST":
        if body.get("role") != "MGR":
            raise ApiError(403, "FORBIDDEN", "설정은 관리자만")
        if "shift_target" in body:
            live.target_override = int(body["shift_target"])
        if "safety" in body:
            live.safety_override = {**getattr(live, "safety_override", {}), **{k: float(v) for k, v in body["safety"].items()}}
        if "rules" in body:
            S.rule_values.update(body["rules"])
        S.settings_log.append({"at": fmt_dt(rt.now()), "by": body.get("user_id"), "what": {k: v for k, v in body.items() if k not in ("role", "user_id")}})
        return {"ok": True}
    if key == "users":
        return {"users": list(P.users.values())}
    raise ApiError(404, "NOT_FOUND", f"없는 주소: {key}")


def live_daily(d):
    """10/1 일일 보고서 AI비서 초안: 야간 교대 보고서가 확정되면 그 즉시, 아니면 다음 날 06:00 (UI설계서 4.3, FR-PRD-04-01)."""
    rt, live = S.rt, S.live
    cal = rt.sim.cal
    day = next((s for s in cal.shifts if s.shift_id == f"{d}-D"), None)
    night = next((s for s in cal.shifts if s.shift_id == f"{d}-N"), None)
    if not day or not night or d < fmt_dt(cal.to_dt(rt.N))[:10]:
        return None
    nrep = S.reports.get(night.shift_id, {})
    six = night.end.replace(hour=6, minute=0)
    if not (nrep.get("status") == "CONFIRMED" or rt.now() >= six):
        return None
    a, b = cal.to_min(day.start), min(cal.to_min(night.end), rt.m)
    dr, nr = live.shift_draft(day.shift_id) or {}, live.shift_draft(night.shift_id) or {}
    fl, spd = live.losses(a, b)
    stops = live.stops(a, b)
    al = [e for e in rt.sim.alarm_events if a <= e["occurred_m"] < b]
    items = [f"[긴급] {x['equipment_id']} 고장 {x['minutes']}분 ({x['reason_name']}, 고장 손실 약 {x['loss_qty']}개)" for x in stops if any(e["id"] == x["alarm_event_id"] and e["severity"] == "STOP" for e in al)]
    items += [f"[생산] {s['shift_id']} 실적 {s['actual_qty']}개 — 목표 {s['target_qty']}개의 90% 아래" for s in (dr, nr) if s and s["actual_qty"] < s["target_qty"] * 0.9]
    items += [f"[생산] 병목 {x['process_code']} — {x['cause_code']}" for s in (dr, nr) if s for x in s.get("bottleneck", [])]
    w = [e for e in al if e["severity"] == "WARN"]
    if w:
        items.append(f"[주의] 주의 등급 알람 {len(w)}건 ({', '.join(sorted({e['alarm_code'] for e in w}))})")
    items += [f"[주의] 보류 로트 {l.lot_no}" for l in rt.sim.lots if l.on_hold]
    cnt = {k: sum(1 for t in items if t.startswith(f"[{k}]")) for k in ("긴급", "생산", "주의", "참고")}
    issues = (f"전체 {len(items)}건 (" + " · ".join(f"{k} {v}" for k, v in cnt.items()) + "): " + " / ".join(f"{i + 1}) {t}" for i, t in enumerate(items))) if items else "전체 0건"
    k = live.kpi(a, b)["by"]["LINE"]
    return {"work_date": d, "status": "AI_DRAFT", "target_qty": 180, "actual_qty": (dr.get("actual_qty") or 0) + (nr.get("actual_qty") or 0),
            "defect_qty": (dr.get("defect_qty") or 0) + (nr.get("defect_qty") or 0), "oee_pct": k["oee_pct"], "failure_loss_qty": round(fl, 1),
            "speed_loss_qty": round(spd, 1), "issues_summary": issues, "confirmed_by": None, "confirmed_at": None, "current_version": 0,
            "created_by": "야간 교대 보고서 확정 즉시" if nrep.get("status") == "CONFIRMED" else "06:00 (야간 미확정)"}


def quality_summary(P, rt):
    """불량 코드별 수(9월 + 10/1), 측정 항목별 Cpk·I-MR (최근 50개, DOC-06 §4·§5: 50개 미만이면 계산 중)."""
    from collections import Counter
    from statistics import mean, pstdev
    from gen import records as R
    cnt = Counter()
    for d in P.defects:
        cnt[d["defect_code"]] += int(d["qty"] or 0)
    live_def = [r for r in R.defect_rows(rt.sim) if r["found_at"] >= rt.sim.cal.to_dt(rt.N)]
    for d in live_def:
        cnt[d["defect_code"]] += int(d["qty"] or 0)
    vals = {}
    for rows in P.insp.values():
        for r in rows:
            if r["measured_value"] not in ("", None) and r["use_for_judgement"] == "true" and r["position"] in ("", None, "MID"):
                vals.setdefault(r["item_seq"], []).append((r["measured_at"], float(r["measured_value"])))
    for r in rt.insp_rows:
        if r["measured_value"] is not None and r["use_for_judgement"] and r["position"] in (None, "MID"):
            vals.setdefault(str(r["item_seq"]), []).append((fmt_dt(r["measured_at"]), float(r["measured_value"])))
    items = []
    for it in P.items:
        v = sorted(vals.get(it["item_seq"], []))[-50:]
        xs = [x for _, x in v]
        row = {**it, "n": len(xs), "values": [{"at": a, "v": x} for a, x in v]}
        lsl, usl = (float(it["lsl"]) if it["lsl"] else None), (float(it["usl"]) if it["usl"] else None)
        if len(xs) >= 50 and (lsl is not None or usl is not None):
            mr = [abs(b - a) for a, b in zip(xs, xs[1:])]
            sig = mean(mr) / 1.128 if mr and mean(mr) > 0 else pstdev(xs) or 1e-9
            mu = mean(xs)
            c = [x for x in ((usl - mu) / (3 * sig) if usl is not None else None, (mu - lsl) / (3 * sig) if lsl is not None else None) if x is not None]
            row.update({"mean": round(mu, 4), "sigma": round(sig, 5), "cpk": round(min(c), 2), "ucl": round(mu + 3 * sig, 4), "lcl": round(mu - 3 * sig, 4),
                        "out": [i for i, x in enumerate(xs) if x > mu + 3 * sig or x < mu - 3 * sig]})
        items.append(row)
    return {"defects": [{"defect_code": k, "qty": v} for k, v in cnt.most_common()], "defect_codes": P.defect_codes,
            "items": items, "live_from": fmt_dt(rt.sim.cal.to_dt(rt.N)), "today_defects": [{k: (fmt_dt(v) if hasattr(v, "isoformat") else v) for k, v in d.items()} for d in live_def]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def _do(self, method):
        u = urlparse(self.path)
        body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return self._send(400, {"code": "VALIDATION", "message": "JSON 형식이 틀림 (UTF-8 JSON만 받음)", "detail": {}})
        try:
            self._send(200, route(method, u.path, parse_qs(u.query), body))
        except ApiError as e:
            self._send(e.status, {"code": e.code, "message": e.message, "detail": e.detail})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"code": "SERVER", "message": f"서버 오류: {e}", "detail": {}})

    def do_GET(self):
        self._do("GET")

    def do_POST(self):
        self._do("POST")

    def do_OPTIONS(self):
        self._send(200, {})


def main():
    global S
    S = State()
    threading.Thread(target=ticker, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"준비 끝 — http://127.0.0.1:{PORT}  (시연 시각 {S.rt.clock()['sim_at']}, 배속 ×{S.rt.speed})  Ctrl+C로 끝")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("끝")


if __name__ == "__main__":
    main()
