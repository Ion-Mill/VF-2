"""알람 지침카드 (MNT-02, API-MNT-01 GET /api/maint/guide-card/{alarm_event_id}).

칸은 프로그램, 문장만 비서 (입출력형식 메모 3.2, FR-AST-COM-05):
  [1] 알람 · [2] 심각도 · [3] 누가     ← 알람 코드집 데이터 (masters/alarm_master.csv), 규칙 조회 (FR-MNT-02-02)
  [4] 연쇄 알람                          ← 알람 기록의 앞 알람 연결이 코드집 순서와 맞을 때만 (FR-MNT-02-14)
  [5] 먼저 할 일 3~5줄                   ← **비서** (DOC-03 해당 절 요약, FR-MNT-02-05). 알람 번호마다 한 번 만들어 저장
  [6] 안전                               ← DOC-05 §7 고정 서식 / §2.4 해당 줄 그대로. AI가 쓰지 않음 (FR-MNT-02-07·08)
  [7] 생산 영향 · [8] 지난 기록          ← 운영 기록 (FR-MNT-02-09·10)
  [9] 버튼 · [10] 출처 더보기            ← 규칙 (FR-MNT-02-11·12·13)
비서가 응답하지 않아도 [5] 말고는 모두 나온다. [5]는 DOC-03 점검 순서 표의 작업자(★) 줄로 대신한다 (UI설계서 SCR-09).

실행:
  python 비서_시제품/지침카드.py 358          알람 기록 358번의 카드
  python 비서_시제품/지침카드.py --code 2075  알람 번호의 가장 최근 기록 카드
  python 비서_시제품/지침카드.py --prepare    모든 알람의 "먼저 할 일"을 미리 만듦 (구독 Claude, 몇 분)
"""

import json
import re
import sys
import threading
from datetime import datetime, timedelta

import 비서
import 조회도구 as 운영
from 문서조각 import TABLE_SEP, load_index
from 설정 import DOC_SRC, HERE

SEVERITY = {"STOP": ("정지", "⚠"), "WARN": ("주의", "▲"), "GUIDE": ("조작 안내", "ⓘ")}
RESPONDER = {"MNT": "보전 담당자 호출", "OPR": "작업자 조치 가능"}
DOC05_EQUIPMENT = {"SAW-01": "§3.1", "MIL-01": "§3.2", "VF2-01": "§3.3", "VF2-02": "§3.3",
                   "WSH-01": "§3.5", "CMM-01": "§3.6"}
# 짧은 보충 작업 알람 → DOC-05 §2.4 "작업별 판단 표"의 줄 (그 줄의 첫 칸에 들어 있는 글자)
SHORT_TASK_ROW = {"2075": "알람 2075", "5303.00": "알람 5303", "WSH-02": "세척액 보충·교체"}
LOTO_STEP = re.compile(r"(?<![\d.§])[67]\.[1-6](?!\d)|자물쇠|압력 해제 링")   # 비서 문장에 잠금 단계를 쓰지 않는다

SUMMARY_SYSTEM = """너는 자동차 브래킷 가공 라인의 AI 비서 '이브'다. 알람 지침카드의 "먼저 할 일" 칸만 쓴다.

- 주어진 고장 대응 매뉴얼(DOC-03) 절만 근거로, 알람이 뜬 직후 현장 작업자가 먼저 할 일을 3~5줄로 쓴다.
- 점검 순서 표가 있으면 작업자(★) 줄을 순서대로 우선 쓴다. 보전 담당자의 일이 필요하면 "보전 담당자를 부른다"로 마무리한다.
- 잠금·표지 단계(6.1~7.3), 자물쇠·차단 순서는 쓰지 않는다. 안전 칸에 프로그램이 따로 붙인다.
- 알람 이름, 숫자, 부품 이름은 문서 그대로 쓴다. 문서에 없는 숫자나 일을 만들지 않는다.
- 용어집 표준어를 쓰고, 제조사 매뉴얼 이름·문서 번호·쪽 같은 원문 이름은 쓰지 않는다.
- 한 줄은 한 가지 일, 60자 안팎, "~본다/~한다"처럼 짧게 끝낸다.
- section 칸에는 그 줄의 근거 절(예: §2.1)을 적는다."""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"first_actions": {
        "type": "array", "minItems": 3, "maxItems": 5,
        "items": {"type": "object", "properties": {"text": {"type": "string"}, "section": {"type": "string"}},
                  "required": ["text", "section"], "additionalProperties": False}}},
    "required": ["first_actions"], "additionalProperties": False,
}


# ---------- 공통 ----------

def source(index, field, doc_no, section):
    c = index.get((doc_no, section))
    if not c:
        return None
    return {"field": field, "doc_name": c["doc_name"], "doc_no": doc_no, "rev": c["rev"], "section": section}


def alarm_events():
    return {e["alarm_event_id"]: e for e in 운영.until_now(운영.table("alarm_event"), "occurred_at")}


def guide_sections(alarm_code):
    rows = sorted((g for g in 운영.master("alarm_guide_map") if g["alarm_code"] == alarm_code), key=lambda g: int(g["seq"]))
    return [(g["doc_no"], g["section"]) for g in rows]


# ---------- [5] 먼저 할 일 (비서) ----------

SUMMARY_FILE = HERE / "지침카드_먼저할일.json"   # git에 올려 팀이 같이 쓰고 검토한다
_summary_lock = threading.Lock()


def load_summaries():
    if not SUMMARY_FILE.exists():
        return {}
    return json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))


def save_summary(alarm_code, entry):
    with _summary_lock:
        data = load_summaries()
        data[alarm_code] = entry
        ordered = {k: data[k] for k in sorted(data)}
        SUMMARY_FILE.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def worker_rows(text):
    """비서가 응답하지 않을 때: DOC-03 점검 순서 표의 작업자(★) 줄 그대로."""
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("★"):
            rows.append(cells[2].replace("**", ""))
    return rows[:5]


def make_summary(alarm, sections, index):
    texts = [f"[{d} {s}] {index[(d, s)]['title']}\n{index[(d, s)]['text']}" for d, s in sections if (d, s) in index]
    allowed = {s for _, s in sections}
    prompt = (f"[알람] {alarm['alarm_code']} {alarm['name_ko']} / 심각도 {SEVERITY[alarm['severity']][0]} / "
              f"누가 {RESPONDER.get(alarm['responder'], alarm['responder'])}\n\n" + "\n\n".join(texts))
    feedback = None
    for _ in range(2):                                   # 처음 + 다시 요청 1번
        try:
            out = 비서.call_claude(prompt + (f"\n\n[앞 답을 고쳐야 할 점] {feedback}" if feedback else ""),
                                  SUMMARY_SYSTEM, SUMMARY_SCHEMA)
        except Exception as e:
            feedback = None
            last_error = str(e)
            continue
        items, problems = [], []
        for a in out["first_actions"]:
            sec = a["section"].strip()
            sec = sec if sec.startswith("§") else f"§{sec}"
            if sec not in allowed:
                problems.append(f"근거 절이 아님: {a['section']} (쓸 수 있는 절: {', '.join(sorted(allowed))})")
            if LOTO_STEP.search(a["text"]):
                problems.append(f"잠금 단계를 다시 씀: {a['text']}")
            if 비서.ORIGINAL_SOURCE.search(a["text"]):
                problems.append(f"원문 이름: {a['text']}")
            items.append({"text": a["text"].strip(), "section": sec})
        if not 3 <= len(items) <= 5:
            problems.append(f"줄 수가 {len(items)}개 (3~5줄이어야 함)")
        if not problems:
            return items, "ai", None
        feedback = " / ".join(problems)
        last_error = feedback
    # 비서 응답 없음·검사 실패 → 점검 순서 표의 작업자 줄 그대로 [제안]
    d, s = sections[0]
    rows = worker_rows(index[(d, s)]["text"]) if (d, s) in index else []
    items = [{"text": r, "section": s} for r in rows] or [{"text": f"고장 대응 매뉴얼 {d} {s}를 보고 보전 담당자를 부른다", "section": s}]
    return items, "program", f"비서 응답 없음 — 점검 순서 표의 작업자 줄을 그대로 보입니다 ({last_error[:120]})"


def first_actions(alarm, index, generate=True):
    sections = guide_sections(alarm["alarm_code"])
    if not sections:
        return {"items": [], "made_by": "program", "note": "고장 대응 매뉴얼에 연결된 절이 없습니다"}
    # 근거 절과 개정 — DOC-03이 개정되면 키가 달라져 새로 만든다
    key = " ".join(f"{d} {index[(d, s)]['rev'] if (d, s) in index else '?'} {s}" for d, s in sections)
    saved = load_summaries().get(alarm["alarm_code"])
    if saved and saved["source_key"] == key:
        return {"items": saved["first_actions"], "made_by": saved["made_by"], "note": None}
    if not generate:
        return None
    items, made_by, note = make_summary(alarm, sections, index)
    if made_by == "ai":                                  # 비서가 만든 것만 저장한다 (대체 줄은 다음에 다시 시도)
        save_summary(alarm["alarm_code"], {"source_key": key, "made_by": made_by,
                                           "created_at": datetime.now().isoformat(timespec="seconds"),
                                           "first_actions": items})
    return {"items": items, "made_by": made_by, "note": note}


# ---------- [6] 안전 (고정 서식, AI 작성 아님) ----------

def doc05_text():
    return (DOC_SRC / "DOC-05_안전작업기준서.md").read_text(encoding="utf-8")


def fixed_block(equipment_id, index):
    """DOC-05 §7 블록을 그대로 쓰고 { } 칸만 채운다. OP-30이 아니면 고전압 줄 대신 '§3 저장 에너지 확인'."""
    sec7 = doc05_text().split("## 7.")[1].split("## 8.")[0]
    block = sec7.split("```")[1].strip("\n")
    points = [p for p in 운영.master("isolation_point") if p["equipment_id"] == equipment_id]
    points.sort(key=lambda p: int(p["seq"]))
    energy = []
    chunk = index.get(("DOC-05", DOC05_EQUIPMENT.get(equipment_id, "")))
    if chunk:
        in_table = False
        for line in chunk["text"].splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == "저장 에너지":
                in_table = True
                continue
            if in_table and line.startswith("|") and not TABLE_SEP.match(line):
                energy.append(cells[0])
            elif in_table and not line.startswith("|"):
                in_table = False
    block = (block.replace("{설비 ID}", equipment_id)
             .replace("{§3 차단 지점 목록}", ", ".join(f"{p['isolation_point_id']} {p['point_name']}" for p in points) or "—")
             .replace("{§3 저장 에너지 목록}", ", ".join(energy) or "—"))
    if equipment_id not in ("VF2-01", "VF2-02"):
        block = re.sub(r"\[고전압 대기\].*?DOC-05 §4\.1\)\n", "[저장 에너지]\n □ §3 저장 에너지 확인\n", block, flags=re.S)
    return block


def short_task_row(alarm_code, index):
    """DOC-05 §2.4 작업별 판단 표의 해당 줄 — 작업 · 판단 · 할 일 칸 그대로 (원문 근거 칸은 빼고)."""
    key = SHORT_TASK_ROW.get(alarm_code)
    chunk = index.get(("DOC-05", "§2.4"))
    if not key or not chunk:
        return None
    for line in chunk["text"].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and key in cells[0]:
            return f"{cells[0].replace('**', '')} — {cells[3].replace('**', '')}\n{cells[4].replace('**', '')}"
    return None


def safety(alarm, equipment_id, index):
    sev, level = alarm["severity"], alarm["lockout_level"]
    if sev == "GUIDE":
        return {"kind": "해당 없음", "text": "이 알람은 안전 작업 기준서 적용 대상이 아닙니다 (DOC-05 §1)"}, \
            source(index, "안전", "DOC-05", "§1")
    if level == "FULL":
        return {"kind": "고정 서식 (DOC-05 §7 · AI 작성 아님)", "text": fixed_block(equipment_id, index)}, \
            source(index, "안전", "DOC-05", "§7")
    row = short_task_row(alarm["alarm_code"], index)
    if row:
        return {"kind": "짧은 작업 판단 (DOC-05 §2.4 해당 줄 그대로 · AI 작성 아님)", "text": row}, \
            source(index, "안전", "DOC-05", "§2.4")
    return {"kind": "잠금·표지 필요 없음",
            "text": f"잠금·표지 필요 없음 — 알람 코드집 DOC-02 {alarm['doc02_section']} 기준"}, \
        source(index, "안전", "DOC-02", alarm["doc02_section"])


# ---------- [4] 연쇄 · [7] 생산 영향 · [8] 지난 기록 · [9] 버튼 ----------

def chain(ev, alarm, events):
    rule = alarm["chain_rule"]
    if not rule or not ev:
        return None
    codes = re.findall(r"[\w.-]+", rule.split("(")[0])
    message = rule.split("(", 1)[1].rstrip(")") if "(" in rule else ""
    seq, e = [ev["alarm_code"]], ev
    while e.get("prev_alarm_event_id") and e["prev_alarm_event_id"] in events and len(seq) < len(codes):
        e = events[e["prev_alarm_event_id"]]
        seq.insert(0, e["alarm_code"])
    if seq != codes:                                     # 문서에 적힌 순서와 맞을 때만 (FR-MNT-02-14)
        return None
    return {"sequence": " → ".join(codes), "message": message}


def production_impact(ev, alarm, equipment_id):
    if not ev:
        return None
    n = 운영.now()
    stops = [r for r in 운영.table("equipment_state_log")
             if r["alarm_event_id"] == ev["alarm_event_id"] and 운영.ts(r["start_at"]) <= n]
    stop_min, ongoing = 0.0, False
    for r in stops:
        end = 운영.ts(r["end_at"]) if r["end_at"] else n
        if end > n:
            end, ongoing = n, True
        stop_min += (end - 운영.ts(r["start_at"])).total_seconds() / 60
    eq = next(e for e in 운영.master("equipment") if e["equipment_id"] == equipment_id)
    cycle = float(eq["std_cycle_min"]) if eq["std_cycle_min"] else float(eq["batch_time_min"]) / float(eq["batch_qty"])
    loss = round(stop_min / cycle) if stop_min else 0          # DOC-07 §5.3 고장 손실 수량 (추정)
    holds = [h["lot_no"] for h in 운영.table("lot_hold") if h["related_alarm_event_id"] == ev["alarm_event_id"]]
    if stops:
        loss_text = f"약 {loss}개 손실(추정)" if loss else "손실 1개 미만(추정)"
        text = f"정지 {stop_min:.0f}분{'째' if ongoing else ''} · {loss_text}"
    else:
        text = "설비 멈춤 기록 없음"
    return {"lot_no": ev["lot_no"] or None, "stop_min": round(stop_min), "ongoing": ongoing,
            "loss_qty": loss, "is_estimated": True, "text": text, "suspect_lots": holds}


def past_record(ev, alarm, equipment_id, events):
    if not ev:
        return {"line": "기록 없음", "record_no": None, "repeat_stage": None}
    t = 운영.ts(ev["occurred_at"])
    same = sorted((e for e in events.values() if e["equipment_id"] == equipment_id
                   and e["alarm_code"] == ev["alarm_code"] and 운영.ts(e["occurred_at"]) < t),
                  key=lambda e: e["occurred_at"])
    week_start = (t - timedelta(days=t.weekday())).replace(hour=0, minute=0, second=0)
    this_week = sum(1 for e in same if 운영.ts(e["occurred_at"]) >= week_start) + 1
    stage = None
    for nt in 운영.table("notification"):
        if nt["rule_code"] in ("REPEAT_ALARM", "REPEAT_ALARM_2") and nt["alarm_event_id"] in events:
            e = events[nt["alarm_event_id"]]
            raised = 운영.ts(nt["raised_at"])
            if (e["equipment_id"] == equipment_id and e["alarm_code"] == ev["alarm_code"]
                    and t - timedelta(days=7) <= raised <= t + timedelta(minutes=1)):
                stage = ("반복 알람 2단계 — 지난 조치 효과 없음, 원인 점검 중" if nt["rule_code"] == "REPEAT_ALARM_2"
                         else stage or "반복 알람 1단계")
    if not same:
        return {"line": "기록 없음", "record_no": None, "repeat_stage": stage}
    last = same[-1]
    rec = next((r for r in 운영.table("work_record") if r["alarm_event_id"] == last["alarm_event_id"]), None)
    when = 운영.ts(last["occurred_at"]).strftime("%m/%d")
    line = (f"이번 주 {this_week}번째" if this_week > 1 else f"이번 주 처음 (지난번 {when})")
    line += f", 지난번 원인: {rec['cause']}" if rec and rec["cause"] else ", 지난번 원인 기록 없음"
    return {"line": line, "record_no": rec["record_no"] if rec else None, "repeat_stage": stage,
            "this_week_count": this_week}


def buttons(ev, alarm):
    sev, op30 = alarm["severity"], alarm["process_code"] == "OP-30"
    if sev == "STOP" and op30:
        wo = ev and next((w for w in 운영.table("maintenance_work_order") if w["alarm_event_id"] == ev["alarm_event_id"]), None)
        flow = "지침카드 → 작업지시서 → 작업기록서"
        btn = ({"label": f"작업지시서 보기 — AI비서 초안 {wo['wo_no']} 이미 만들어짐", "target": "SCR-11", "wo_no": wo["wo_no"]}
               if wo else {"label": "작업지시서 보기 (초안 없음)", "target": "SCR-11", "wo_no": None})
        return [btn], flow
    if sev == "STOP":
        return [{"label": "간이 작업기록 쓰기 — 보전 담당자 확정", "target": "SCR-13"}], "지침카드 → 간이 작업기록"
    if sev == "WARN":
        return [{"label": "간이 작업기록 쓰기", "target": "SCR-13"}], "지침카드 → 간이 작업기록"
    return [], "지침카드만"


# ---------- 카드 ----------

def build(ev=None, alarm_code=None, generate=True):
    index = load_index()
    events = alarm_events()
    code = ev["alarm_code"] if ev else alarm_code
    alarm = 운영.alarm_names().get(code)
    equipment_id = ev["equipment_id"] if ev else None
    head = {"alarm_event_id": ev["alarm_event_id"] if ev else None, "equipment_id": equipment_id,
            "occurred_at": ev["occurred_at"] if ev else None, "cleared_at": (ev["cleared_at"] or None) if ev else None,
            "card_status": "준비됨", "is_synthetic": True}
    if not alarm:                                         # 코드집에 없는 알람 → [1]만 (UI설계서 SCR-09 데이터 없음)
        return {**head, "alarm": {"code": code, "name_ko": None, "name_en": None},
                "notice": "알람 코드집에 없음 — 보전 담당자 호출", "sources": []}
    if not equipment_id:                                  # 기록 없이 번호만: 공정의 첫 설비로 안전 칸을 채운다
        equipment_id = next(e["equipment_id"] for e in 운영.master("equipment") if e["process_code"] == alarm["process_code"])
    label, icon = SEVERITY[alarm["severity"]]
    fa = first_actions(alarm, index, generate)
    safe, safe_src = safety(alarm, equipment_id, index)
    btns, flow = buttons(ev, alarm)
    ch = chain(ev, alarm, events)
    doc03 = guide_sections(code)
    sources = [source(index, "알람", "DOC-02", alarm["doc02_section"]),
               source(index, "심각도", "DOC-02", "§2"), source(index, "누가", "DOC-02", "§3")]
    if ch and doc03:
        sources.append(source(index, "연쇄 알람", *doc03[0]))
    for d, s in dict.fromkeys((("DOC-03", i["section"]) for i in (fa or {}).get("items", []))):
        sources.append(source(index, "먼저 할 일", d, s))
    sources.append(safe_src)
    return {**head, "equipment_id": equipment_id, "process_code": alarm["process_code"],
            "alarm": {"code": code, "name_ko": alarm["name_ko"], "name_en": alarm["name_en"]},
            "severity": {"code": alarm["severity"], "label": label, "icon": icon},
            "responder": {"code": alarm["responder"], "label": RESPONDER.get(alarm["responder"]),
                          "note": alarm["responder_note"] or None},
            "chain": ch, "first_actions": fa, "safety": safe,
            "production_impact": production_impact(ev, alarm, equipment_id),
            "past_record": past_record(ev, alarm, equipment_id, events),
            "buttons": btns, "doc_flow": flow, "sources": [s for s in sources if s]}


def card_for_event(alarm_event_id, generate=True):
    ev = alarm_events().get(str(alarm_event_id))
    if not ev:
        raise 비서.ApiError("NOT_FOUND", "없는 알람 기록입니다.", 404, {"alarm_event_id": alarm_event_id})
    return build(ev, generate=generate)


def card_for_code(alarm_code, generate=True):
    """시험용: 그 알람 번호의 가장 최근 기록으로 카드를 만든다. 기록이 없으면 번호만으로."""
    evs = [e for e in alarm_events().values() if e["alarm_code"] == alarm_code]
    ev = max(evs, key=lambda e: e["occurred_at"]) if evs else None
    return build(ev, alarm_code=alarm_code, generate=generate)


def recent_events(limit=40):
    names = 운영.alarm_names()
    evs = sorted(alarm_events().values(), key=lambda e: e["occurred_at"], reverse=True)[:limit]
    return {"items": [{"alarm_event_id": e["alarm_event_id"], "equipment_id": e["equipment_id"], "alarm_code": e["alarm_code"],
                       "name_ko": names.get(e["alarm_code"], {}).get("name_ko"), "severity": e["severity_at_event"],
                       "occurred_at": e["occurred_at"], "scenario_code": e.get("scenario_code") or None} for e in evs]}


def prepare_all():
    """모든 알람의 '먼저 할 일'을 미리 만든다 (알람이 뜨면 카드가 바로 준비되도록, FR-MNT-02-01)."""
    index = load_index()
    for alarm in 운영.master("alarm_master"):
        t = datetime.now()
        fa = first_actions(alarm, index)
        print(f"{alarm['alarm_code']:13} {fa['made_by']:7} {len(fa['items'])}줄  {(datetime.now() - t).seconds}초"
              + (f"  ← {fa['note']}" if fa.get("note") else ""), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args[:1] == ["--prepare"]:
        prepare_all()
    elif args[:1] == ["--code"]:
        print(json.dumps(card_for_code(args[1]), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(card_for_event(args[0] if args else "358"), ensure_ascii=False, indent=2))
