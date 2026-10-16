"""운영 조회 도구 (읽기 전용) — Claude Code가 부르는 MCP 서버 (표준 입출력, 외부 패키지 없음).

FR-MNT-01-04·FR-AST-COM-14: 정해진 조회 도구만, SQL 없음, 설비로 명령 보내지 않음 (FR-AST-COM-11).
채팅 권한: 이 서버를 띄울 때 받은 역할(EVE_ROLE)로 **서버가** 확인한다 (NFR-SEC-05).
  MTTR·센서 추세는 MNT·MGR만. 다른 역할이면 값을 주지 않고 "권한 밖"을 돌려주고 기록(EVE_AUDIT)에 남긴다.

데이터: 생성기 out(과거 30일) + out_realtime(시연)을 이어 붙인 가상 운영 데이터. 모든 답에 is_synthetic: true.
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache

from 설정 import GATED_TOOLS, GEN_OUT, GEN_RT, MASTERS, NOW_OVERRIDE, PERMISSION_MESSAGE

ROLE = os.environ.get("EVE_ROLE", "")
AUDIT = os.environ.get("EVE_AUDIT")

# 같은 번호의 행은 실시간 쪽(나중 것)으로 덮는다
KEYS = {"alarm_event": "alarm_event_id", "equipment_state_log": "state_log_id", "production_lot": "lot_no",
        "pm_record": "pm_record_id", "production_order": "order_no", "inspection_plan": "lot_no",
        "lot_hold": "hold_id", "work_record": "record_no", "maintenance_work_order": "wo_no",
        "shift_report": "shift_id", "shift": "shift_id", "tool_change": "tool_change_id",
        "inventory_txn": "txn_id", "defect_record": "defect_record_id", "operation_report": "op_report_id"}
CYCLE_DAYS = {"DAILY": 1, "WEEKLY": 7, "MONTHLY": 30, "QUARTER": 90, "HALF_YEAR": 182, "YEARLY": 365}
EQUIPMENT_IDS = ["SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01"]


# ---------- 데이터 읽기 ----------

def _read(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=None)
def master(name):
    return _read(MASTERS / f"{name}.csv")


@lru_cache(maxsize=None)
def table(name):
    rows = _read(GEN_OUT / f"{name}.csv") + _read(GEN_RT / f"{name}.csv")
    key = KEYS.get(name)
    if not key:
        return rows
    merged = {}
    for r in rows:
        merged[r[key]] = r
    return list(merged.values())


def ts(text):
    return datetime.fromisoformat(text) if text else None


@lru_cache(maxsize=None)
def now():
    if NOW_OVERRIDE:
        return datetime.fromisoformat(NOW_OVERRIDE)
    manifest = GEN_RT / "manifest.json"
    if manifest.exists():
        return datetime.fromisoformat(json.loads(manifest.read_text(encoding="utf-8"))["now_at"])
    return max(ts(r["start_at"]) for r in table("equipment_state_log"))


def until_now(rows, field):
    n = now()
    return [r for r in rows if r.get(field) and ts(r[field]) <= n]


def alarm_names():
    return {a["alarm_code"]: a for a in master("alarm_master")}


def fmt(dt):
    return dt.isoformat(timespec="minutes") if dt else None


def minutes(a, b):
    return round((b - a).total_seconds() / 60, 1)


def check_equipment(equipment_id, required=False):
    if equipment_id and equipment_id not in EQUIPMENT_IDS:
        raise ValueError(f"없는 설비입니다: {equipment_id}. 설비: {', '.join(EQUIPMENT_IDS)}")
    if required and not equipment_id:
        raise ValueError(f"equipment_id가 필요합니다. 설비: {', '.join(EQUIPMENT_IDS)}")


# ---------- 조회 도구 ----------

def 설비_상태(equipment_id=None):
    check_equipment(equipment_id)
    n, names = now(), alarm_names()
    out = []
    for eq in [equipment_id] if equipment_id else EQUIPMENT_IDS:
        logs = [r for r in until_now(table("equipment_state_log"), "start_at") if r["equipment_id"] == eq]
        cur = max(logs, key=lambda r: ts(r["start_at"])) if logs else None
        active = [a for a in until_now(table("alarm_event"), "occurred_at")
                  if a["equipment_id"] == eq and (not a["cleared_at"] or ts(a["cleared_at"]) > n)]
        out.append({
            "equipment_id": eq,
            "state_code": cur["state_code"] if cur else None,
            "state_since": cur["start_at"] if cur else None,
            "active_alarms": [{"alarm_code": a["alarm_code"], "name_ko": names.get(a["alarm_code"], {}).get("name_ko"),
                               "severity": a["severity_at_event"], "occurred_at": a["occurred_at"],
                               "alarm_event_id": a["alarm_event_id"]} for a in active],
        })
    return {"기준_시각": fmt(n), "설비": out}


def 알람_기록(equipment_id=None, alarm_code=None, start=None, end=None, limit=30):
    check_equipment(equipment_id)
    n, names = now(), alarm_names()
    start_dt = ts(start) if start else n - timedelta(days=7)
    end_dt = min(ts(end), n) if end else n
    rows = [a for a in until_now(table("alarm_event"), "occurred_at")
            if start_dt <= ts(a["occurred_at"]) <= end_dt
            and (not equipment_id or a["equipment_id"] == equipment_id)
            and (not alarm_code or a["alarm_code"] == str(alarm_code))]
    rows.sort(key=lambda a: a["occurred_at"], reverse=True)
    items = []
    for a in rows[: int(limit)]:
        cleared = ts(a["cleared_at"])
        items.append({"alarm_event_id": a["alarm_event_id"], "equipment_id": a["equipment_id"],
                      "alarm_code": a["alarm_code"], "name_ko": names.get(a["alarm_code"], {}).get("name_ko"),
                      "severity": a["severity_at_event"], "occurred_at": a["occurred_at"],
                      "cleared_at": a["cleared_at"] or None,
                      "duration_min": minutes(ts(a["occurred_at"]), cleared) if cleared else None,
                      "lot_no": a["lot_no"] or None})
    by_code = defaultdict(int)
    for a in rows:
        by_code[a["alarm_code"]] += 1
    return {"기간": [fmt(start_dt), fmt(end_dt)], "전체_건수": len(rows), "알람별_건수": dict(by_code),
            "목록(최근순)": items, "목록_잘림": len(rows) > len(items)}


def _down_episodes(equipment_id, days):
    """정지 등급 DOWN 구간 (DOC-07 §2.2·§6.1: 주의 등급 정지(IDLE+▲)는 세지 않음). 붙은 DOWN 행은 한 건."""
    n = now()
    start = n - timedelta(days=days)
    logs = sorted((r for r in until_now(table("equipment_state_log"), "start_at")
                   if r["equipment_id"] == equipment_id and r["state_code"] == "DOWN"),
                  key=lambda r: r["start_at"])
    eps = []
    for r in logs:
        s, e = ts(r["start_at"]), min(ts(r["end_at"]) if r["end_at"] else n, n)
        if e < start:
            continue
        if eps and s <= eps[-1][1]:
            eps[-1][1] = max(eps[-1][1], e)
        else:
            eps.append([max(s, start), e, r.get("alarm_event_id")])
    return start, n, eps


def MTTR(equipment_id, days=30):
    check_equipment(equipment_id, required=True)
    start, n, eps = _down_episodes(equipment_id, int(days))
    ttr = [minutes(s, e) for s, e, _ in eps]
    return {"equipment_id": equipment_id, "기간": [fmt(start), fmt(n)], "고장_횟수_FE": len(eps),
            "수리_시간_TTR_분": ttr,
            "MTTR_분": round(sum(ttr) / len(ttr), 1) if ttr else "—",
            "식": "MTTR = 수리 시간(TTR) 합 ÷ 고장 횟수(FE), 정지 등급 DOWN만 (DOC-07 §6.2)",
            "고장_기록": [{"start": fmt(s), "end": fmt(e), "alarm_event_id": a} for s, e, a in eps]}


def 지표(equipment_id, days=30):
    """MTBF·고장 횟수·상태별 시간. MTTR은 별도 도구(권한)."""
    check_equipment(equipment_id, required=True)
    start, n, eps = _down_episodes(equipment_id, int(days))
    tbf, prev_end = [], start
    for s, e, _ in eps:                      # 기간 시작~첫 고장도 한 간격으로 센다 [제안]
        tbf.append((s - prev_end).total_seconds() / 3600)
        prev_end = e
    state_min = defaultdict(float)
    for r in until_now(table("equipment_state_log"), "start_at"):
        if r["equipment_id"] != equipment_id:
            continue
        s, e = max(ts(r["start_at"]), start), min(ts(r["end_at"]) if r["end_at"] else n, n)
        if e > s:
            state_min[r["state_code"]] += (e - s).total_seconds() / 60
    return {"equipment_id": equipment_id, "기간": [fmt(start), fmt(n)], "고장_횟수_FE": len(eps),
            "MTBF_시간": round(sum(tbf) / len(eps), 1) if eps else "—",
            "MTBF_계산_방법": "고장 간격 시간(TBF) 합 ÷ FE (DOC-07 §6.2). 기간 시작~첫 고장도 한 간격으로 셈 [제안]",
            "상태별_시간_분": {k: round(v) for k, v in sorted(state_min.items())}}


def 생산_실적(shift_id=None, work_date=None):
    if not shift_id and not work_date:
        shifts = until_now(table("shift"), "start_at")
        shift_id = max(shifts, key=lambda r: r["start_at"])["shift_id"]
    out = {}
    if shift_id:
        s = next((r for r in table("shift") if r["shift_id"] == shift_id), None)
        if not s:
            raise ValueError(f"없는 교대입니다: {shift_id} (모양: 2026-09-15-D / -N)")
        rep = next((r for r in table("shift_report") if r["shift_id"] == shift_id), None)
        ops = [r for r in table("operation_report") if r["shift_id"] == shift_id and r["process_code"] == "OP-50"]
        out["교대"] = {"shift_id": shift_id, "target_qty": s["target_qty"], "carry_over_qty": s["carry_over_qty"],
                      "보고서_상태": rep["status"] if rep else "보고서 없음(진행 중)",
                      "actual_qty": rep["actual_qty"] if rep else sum(int(r["gq"] or 0) for r in ops),
                      "defect_qty": rep["defect_qty"] if rep else None,
                      "실적_잠정": not rep or rep["status"] != "CONFIRMED"}
        work_date = work_date or s["work_date"]
    if work_date:
        d = next((r for r in table("daily_report") if r["work_date"] == work_date), None)
        if d:
            out["일일"] = {k: d[k] for k in ("work_date", "status", "target_qty", "actual_qty", "defect_qty",
                                           "oee_pct", "failure_loss_qty", "speed_loss_qty")}
            out["일일"]["손실_수량은_추정"] = True
    return out


def 로트(lot_no):
    lot = next((r for r in table("production_lot") if r["lot_no"] == lot_no), None)
    if not lot:
        raise ValueError(f"없는 로트입니다: {lot_no} (모양: LOT-2609-041-1)")
    plan = next((r for r in table("inspection_plan") if r["lot_no"] == lot_no), None)
    holds = [r for r in table("lot_hold") if r["lot_no"] == lot_no]
    defects = [r for r in table("defect_record") if r["lot_no"] == lot_no]
    return {"lot": {k: lot[k] for k in ("lot_no", "order_no", "input_shift_id", "input_qty", "status", "scrap_qty", "judged_at")},
            "검사": plan and {k: plan[k] for k in ("plan_mode", "enhance_reason", "gauge_pass_qty", "gauge_fail_qty", "judgement", "judged_at")},
            "보류": [{k: h[k] for k in ("hold_id", "trigger_type", "hold_reason", "held_at", "released_at", "result")} for h in holds],
            "불량": [{k: d[k] for k in ("defect_record_id", "process_code", "defect_code", "qty", "disposition", "found_at")} for d in defects]}


def 작업지시(wo_no=None, equipment_id=None):
    check_equipment(equipment_id)
    wos = [w for w in table("maintenance_work_order")
           if (not wo_no or w["wo_no"] == wo_no) and (not equipment_id or w["equipment_id"] == equipment_id)]
    steps = defaultdict(list)
    for s in table("work_order_step"):
        steps[s["wo_no"]].append(f"{s['step_no']}. {s['step_text']} ({s['source_section']})")
    return {"작업지시서": [{**{k: w[k] for k in ("wo_no", "trigger_kind", "equipment_id", "lot_no", "created_at",
                                             "title", "status", "assignee_user_id", "approved_at", "completed_at")},
                          "단계": steps.get(w["wo_no"], [])} for w in wos]}


def 작업기록(equipment_id=None, alarm_code=None, record_no=None, limit=10):
    check_equipment(equipment_id)
    events = {a["alarm_event_id"]: a for a in table("alarm_event")}
    rows = []
    for r in until_now(table("work_record"), "start_at"):
        ev = events.get(r["alarm_event_id"])
        if record_no and r["record_no"] != record_no:
            continue
        if equipment_id and r["equipment_id"] != equipment_id:
            continue
        if alarm_code and (not ev or ev["alarm_code"] != str(alarm_code)):
            continue
        rows.append({"record_no": r["record_no"], "record_type": r["record_type"], "wo_no": r["wo_no"] or None,
                     "equipment_id": r["equipment_id"], "alarm_code": ev["alarm_code"] if ev else None,
                     "cause": r["cause"], "action": r["action"], "start_at": r["start_at"], "end_at": r["end_at"],
                     "repair_min": r["repair_min"], "status": r["status"]})
    rows.sort(key=lambda r: r["start_at"], reverse=True)
    return {"전체_건수": len(rows), "목록(최근순)": rows[: int(limit)]}


def 예방정비_기한(equipment_id=None, days_ahead=7):
    check_equipment(equipment_id)
    n = now()
    last = {}
    for r in until_now(table("pm_record"), "done_at"):
        if r["pm_task_id"] not in last or r["done_at"] > last[r["pm_task_id"]]["done_at"]:
            last[r["pm_task_id"]] = r
    items, no_record = [], []
    for t in master("pm_task"):
        if equipment_id and t["equipment_id"] != equipment_id:
            continue
        cycle = CYCLE_DAYS.get(t["cycle_code"])
        if not cycle:
            continue
        rec = last.get(t["pm_task_id"])
        if not rec:
            no_record.append(t["pm_task_id"])
            continue
        due = ts(rec["done_at"]) + timedelta(days=cycle)
        if due > n + timedelta(days=int(days_ahead)):
            continue
        items.append({"pm_task_id": t["pm_task_id"], "equipment_id": t["equipment_id"], "item_name": t["item_name"],
                      "cycle_code": t["cycle_code"], "doc04_section": f"DOC-04 §{t['doc04_section']}",
                      "마지막_실시": rec["done_at"], "다음_기한": fmt(due),
                      "기한_넘김": due < n, "담당": t["default_role"]})
    items.sort(key=lambda i: i["다음_기한"])
    return {"기준_시각": fmt(n), "다음_기한_계산": "마지막 실시 + 주기 [제안]", "항목": items,
            "실시_기록_없는_항목_수": len(no_record)}


def 공구_수명(equipment_id=None):
    check_equipment(equipment_id)
    n = now()
    types = {t["item_no"]: t for t in master("tool_type")}
    items = {i["item_no"]: i["item_name"] for i in master("inventory_item")}
    out = []
    for tool in master("tool"):
        if equipment_id and tool["equipment_id"] != equipment_id:
            continue
        events = [(ts(u["recorded_at"]), float(u["cum_after"])) for u in table("tool_usage") if u["tool_id"] == tool["tool_id"]]
        events += [(ts(c["changed_at"]), 0.0) for c in table("tool_change") if c["tool_id"] == tool["tool_id"]]
        events = sorted(e for e in events if e[0] <= n)
        cum = events[-1][1] if events else float(tool["cum_usage"] or 0)
        limit = float(types[tool["item_no"]]["life_limit"])
        out.append({"tool_id": tool["tool_id"], "item_name": items.get(tool["item_no"]), "사용량": round(cum, 1),
                    "수명_한계": limit, "단위": types[tool["item_no"]]["usage_unit"],
                    "사용률_pct": round(cum / limit * 100, 1)})
    return {"기준_시각": fmt(n), "공구": out, "참고": "사용률 90% 이상이면 교체 알림 (DOC-07 §9)"}


def 재고(item_no=None, category=None):
    n = now()
    qty = defaultdict(float)
    for t in table("inventory_txn"):
        if ts(t["txn_at"]) <= n:
            qty[t["item_no"]] += float(t["qty_change"])
    out = []
    for i in master("inventory_item"):
        if (item_no and i["item_no"] != item_no) or (category and i["category"] != category):
            continue
        safety = float(i["safety_stock"]) if i["safety_stock"] else None
        out.append({"item_no": i["item_no"], "item_name": i["item_name"], "재고": qty[i["item_no"]], "단위": i["unit"],
                    "안전_재고": safety, "부족": safety is not None and qty[i["item_no"]] < safety})
    return {"기준_시각": fmt(n), "품목": out}


def 출하(days=7):
    n = now()
    rows = [s for s in until_now(table("shipment"), "shipped_at") if ts(s["shipped_at"]) >= n - timedelta(days=int(days))]
    lines = defaultdict(int)
    for l in table("shipment_line"):
        lines[l["shipment_no"]] += int(l["qty"])
    return {"출하": [{"shipment_no": s["shipment_no"], "shipped_at": s["shipped_at"], "customer_code": s["customer_code"],
                    "due_date": s["due_date"], "status": s["status"], "수량": lines[s["shipment_no"]]} for s in rows]}


def 센서_추세(equipment_id, sensor_code=None, minutes_back=60):
    check_equipment(equipment_id, required=True)
    if equipment_id not in ("VF2-01", "VF2-02"):
        return {"equipment_id": equipment_id, "안내": "센서 값은 OP-30(VF2-01, VF2-02)만 기록합니다 (DOC-07 §3)"}
    n = now()
    start = n - timedelta(minutes=int(minutes_back))
    sensors = {s["sensor_code"]: s for s in master("sensor_item")}
    vals = defaultdict(list)
    for r in _read(GEN_RT / "sensor_sample.csv"):
        if r["equipment_id"] == equipment_id and (not sensor_code or r["sensor_code"] == sensor_code):
            t = ts(r["sampled_at"])
            if start <= t <= n:
                vals[r["sensor_code"]].append(float(r["value"]))
    out = []
    for code, v in vals.items():
        s = sensors[code]
        item = {"sensor_code": code, "sensor_name": s["sensor_name"], "단위": s["unit"], "개수": len(v),
                "최소": min(v), "평균": round(sum(v) / len(v), 1), "최대": max(v),
                "정상_범위[참고]": f"{s['normal_min']}~{s['normal_max']} {s['unit']}",
                "정상_범위_벗어남": max(v) > float(s["normal_max"]) or min(v) < float(s["normal_min"])}
        if s["unit"] == "psi":
            item["bar_환산"] = f"최소 약 {min(v) / 14.5:.1f} bar, 최대 약 {max(v) / 14.5:.1f} bar"
        out.append(item)
    return {"equipment_id": equipment_id, "기간": [fmt(start), fmt(n)], "센서": out,
            "주의": "알람 기준값은 문서에 없으므로 말하지 않는다 (DOC-07 §3)"}


def 설비_사양(equipment_id=None):
    check_equipment(equipment_id)
    keep = ("equipment_id", "process_code", "model", "controller", "std_cycle_min", "batch_qty", "batch_time_min",
            "has_sensor", "size_x_mm", "size_y_mm", "size_z_mm")
    return {"설비": [{k: e[k] for k in keep} for e in master("equipment")
                   if not equipment_id or e["equipment_id"] == equipment_id]}


def 알람_코드(alarm_code):
    """알람 번호 정확 일치 (FR-MNT-01-02). 원문 출처 칸(source_ref)은 주지 않는다."""
    a = alarm_names().get(str(alarm_code))
    if not a:
        return {"alarm_code": str(alarm_code), "결과": "알람 코드집(DOC-02)에 없는 번호"}
    guides = [f"{g['doc_no']} {g['section']}" for g in master("alarm_guide_map") if g["alarm_code"] == str(alarm_code)]
    return {k: a[k] for k in ("alarm_code", "process_code", "name_ko", "easy_desc", "severity", "responder",
                              "lockout_level", "chain_rule")} | {"문서_위치": f"DOC-02 {a['doc02_section']}",
                                                                 "고장_대응": guides}


# ---------- MCP 도구 목록 ----------

S = lambda **p: {"type": "object", "properties": p, "additionalProperties": False}
EQ = {"type": "string", "description": "설비 ID: SAW-01, MIL-01, VF2-01, VF2-02, WSH-01, CMM-01"}
# 도구 이름은 영문만 (Claude API 규칙 ^[a-zA-Z0-9_-]{1,64}$). 설명은 한국어.
TOOLS = {
    "equipment_status": (설비_상태, "설비의 지금 상태(RUN/IDLE/BLOCKED/SETUP/DOWN/MAINT)와 떠 있는 알람", S(equipment_id=EQ)),
    "alarm_history": (알람_기록, "알람 발생 기록. 기간 기본값 최근 7일. 몇 번 떴는지, 언제 떴는지",
              S(equipment_id=EQ, alarm_code={"type": "string"}, start={"type": "string", "description": "ISO 시각"},
                end={"type": "string"}, limit={"type": "integer"})),
    "alarm_code": (알람_코드, "알람 번호로 알람 코드집(DOC-02) 항목을 정확히 찾는다", S(alarm_code={"type": "string"})),
    "metrics": (지표, "설비별 MTBF·고장 횟수·상태별 시간 (기본 30일). MTTR은 MTTR 도구", S(equipment_id=EQ, days={"type": "integer"})),
    "mttr": (MTTR, "설비별 MTTR(평균 수리 시간)과 수리 시간 목록 (기본 30일)", S(equipment_id=EQ, days={"type": "integer"})),
    "production": (생산_실적, "교대·일 목표와 실적, 불량, OEE, 손실 수량(추정). 인자가 없으면 지금 교대",
              S(shift_id={"type": "string", "description": "예: 2026-09-15-D (주간) / -N (야간)"},
                work_date={"type": "string", "description": "예: 2026-09-15"})),
    "lot": (로트, "로트 상태·검사 판정·보류·불량", S(lot_no={"type": "string"})),
    "work_order": (작업지시, "정비 작업지시서와 단계", S(wo_no={"type": "string"}, equipment_id=EQ)),
    "work_record": (작업기록, "정비 작업기록(원인·조치·수리 시간)", S(equipment_id=EQ, alarm_code={"type": "string"},
                                                       record_no={"type": "string"}, limit={"type": "integer"})),
    "pm_due": (예방정비_기한, "예방 정비 다음 기한과 기한 넘긴 항목 (기본 7일 앞까지)",
                 S(equipment_id=EQ, days_ahead={"type": "integer"})),
    "tool_life": (공구_수명, "공구별 사용량·수명 한계·사용률", S(equipment_id=EQ)),
    "inventory": (재고, "재고 수량과 안전 재고 부족 여부. category: TOOL, CONSUMABLE 등",
           S(item_no={"type": "string"}, category={"type": "string"})),
    "shipment": (출하, "최근 출하 기록 (기본 7일)", S(days={"type": "integer"})),
    "sensor_trend": (센서_추세, "OP-30 센서 값 최근 N분(기본 60) 최소·평균·최대와 정상 범위",
              S(equipment_id=EQ, sensor_code={"type": "string", "description": "SpindleLoadPct, SpindleMotorTemp, AirPressure, Xload, Yload, Zload, DcVolt"},
                minutes_back={"type": "integer"})),
    "equipment_spec": (설비_사양, "설비 모델·기준 사이클 시간·크기", S(equipment_id=EQ)),
}


def audit(entry):
    if AUDIT:
        with open(AUDIT, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def call_tool(name, args):
    if name not in TOOLS:
        raise ValueError(f"없는 도구: {name}")
    allowed = GATED_TOOLS.get(name)
    if allowed and ROLE not in allowed:                     # 서버가 역할을 먼저 확인 (NFR-SEC-05)
        audit({"tool": name, "args": args, "denied": True})
        return {"status": "권한 밖", "안내": PERMISSION_MESSAGE, "값": None}
    result = TOOLS[name][0](**args)
    audit({"tool": name, "args": args, "denied": False})
    return {"is_synthetic": True, **result}


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        return {"protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}}, "serverInfo": {"name": "eve", "version": "0.1"}}
    if method == "tools/list":
        return {"tools": [{"name": k, "description": d, "inputSchema": s} for k, (_, d, s) in TOOLS.items()]}
    if method == "tools/call":
        p = msg["params"]
        try:
            data = call_tool(p["name"], p.get("arguments") or {})
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
        except Exception as e:  # 도구 오류는 비서에게 문장으로 돌려준다
            return {"content": [{"type": "text", "text": f"오류: {e}"}], "isError": True}
    if method == "ping":
        return {}
    if mid is not None:
        raise LookupError(method)
    return None


def serve():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if "id" not in msg:              # 알림(notifications/...)은 답하지 않는다
            continue
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
        except LookupError:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Method not found"}}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    serve()
