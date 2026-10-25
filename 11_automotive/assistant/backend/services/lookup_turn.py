"""수량·설비 상태 조회를 도구로 요청하는 길 (2026-10-23).

외부 Claude 채팅에서만 켜진다. 비교 1번·2번을 나누지 않는다.
뜻이 안 정해지면 LLM이 질문만 한다. 조회 요청이 온 뒤에만 설비·기간을 보고 이미 있는 조회를 실행한다.
위 문장은 LLM, 아래 `원문 보기`는 프로그램 원문이다. 달력 날짜는 쓰지 않고 기간 말은 시연 서버 시계로 계산한다. 시계를 못 읽으면 `REFERENCE_AT`다.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from backend.config import REFERENCE_AT
from backend.llm import client as C
from backend.llm import external as EXT
from backend.safety import fixed_block as FB
from backend.services import sim_clock

DECIDE_JOB = "lookup_decide"
WRITE_JOB = "lookup_write"
TURNS = 5
SIX = ("SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01")
LOOKUP_INTENTS = frozenset({
    "production", "inventory", "alarm_count", "kpi", "tool_life", "stops", "equipment_status", "pm_due",
})
NEED_EQUIPMENT = frozenset({"equipment_status", "pm_due", "stops", "mttr"})
ONCE = frozenset({"production", "inventory"})

_NAMES = {
    "생산": "production", "production": "production",
    "oee": "oee", "설비종합효율": "oee",
    "mttr": "mttr",
    "공구수명": "tool_life", "toollife": "tool_life", "tool_life": "tool_life",
    "알람횟수": "alarm_count", "alarmcount": "alarm_count", "alarm_count": "alarm_count",
    "정지횟수": "stops", "정지": "stops", "stops": "stops",
    "재고": "inventory", "inventory": "inventory",
    "가동상태": "equipment_status", "equipmentstatus": "equipment_status", "equipment_status": "equipment_status",
    "정비기한": "pm_due", "pmdue": "pm_due", "pm_due": "pm_due",
}
_INTENT = {
    "production": "production", "oee": "kpi", "mttr": "kpi", "tool_life": "tool_life",
    "alarm_count": "alarm_count", "stops": "stops", "inventory": "inventory",
    "equipment_status": "equipment_status", "pm_due": "pm_due",
}
_CALENDAR = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s*월\s*\d{1,2}\s*일|(?<!\d)\d{1,2}/\d{1,2}(?!\d)")
_EQ = re.compile(r"(?<![A-Za-z0-9])(?:SAW|MIL|VF2|WSH|CMM)-\d{2}(?![A-Za-z0-9])", re.I)
_ALL = re.compile(r"모든\s*설비")
_FOLLOW = re.compile(r"그건|그것|그거|고장\s*만|가동\s*상태|정비\s*기한|모든\s*설비")
_ONLY_EQ = re.compile(r"^\s*(?:SAW|MIL|VF2|WSH|CMM)-\d{2}\s*[.!?]*\s*$", re.I)
_CODE = re.compile(r"(?<![0-9])(\d{3,5})(?![0-9])")
_ORIG = re.compile(r"\n*■\s*원문 보기\b[\s\S]*\Z")
_SAFE = re.compile(r"\n*■\s*안전 작업 \(고정 서식[\s\S]*\Z")

SCHEMA_DECIDE = {
    "type": "object", "additionalProperties": False, "required": ["question", "lookups"],
    "properties": {
        "question": {"type": "string"},
        "lookups": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "equipment", "kind", "period"],
            "properties": {
                "name": {"type": "string"}, "equipment": {"type": "string"},
                "kind": {"type": "string"}, "period": {"type": "string"},
            },
        }},
    },
}
SCHEMA_WRITE = {
    "type": "object", "additionalProperties": False, "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
}

_DECIDE_SYSTEM = """너는 자동차 부품 절삭가공 라인의 비서다.
최근 대화를 읽고, 답이 정해지면 조회를 요청한다. 받은 자료에 없어 추측해야 하면 숫자를 만들지 말고 무엇이 빠졌는지 질문한다.
한 턴에는 질문과 조회 중 하나만 한다. 뜻이 안 정해지면 question에 질문만 쓰고 lookups는 빈 배열로 둔다. 뜻이 정해지면 question은 빈 문자열이다.
조회 name은 생산, OEE, MTTR, 공구 수명, 알람 횟수, 정지 횟수, 재고, 가동 상태, 정비 기한만 쓴다. 새 조회는 만들지 않는다.
equipment는 설비 이름(SAW-01, MIL-01, VF2-01, VF2-02, WSH-01, CMM-01), 모든 설비, 또는 빈 문자열이다. 모든설비는 모든 설비와 같고, 가동상태는 가동 상태와 같다.
period는 어제·오늘·지난 N일·이번 교대·직전 교대·이번 달·10월 같은 기간 말이다. 10월 23일처럼 일까지 적은 달력 날짜는 쓰지 않는다. 이번 말에 기간이 없어도 앞 대화의 기간 말을 period에 넣는다.
kind는 고장·알람 번호처럼 종류를 좁히는 말이다. 없으면 빈 문자열이다. 재고는 품목이 있으면 kind에 그 품목 이름만 넣고, 품목이 없으면 kind를 비운다. 한 질문에 조회가 둘이면 lookups에 둘 다 넣는다.
재고처럼 설비 없이 되는 조회는 equipment를 비운다. 가동 상태·정비 기한·정지 횟수·MTTR은 설비 이름이 없으면 조회하지 말고 설비 이름을 질문한다.
알람 횟수는 알람 번호나 설비 이름이 없어도 조회한다 (기간 안 전체 건수). 번호가 없다고 되묻지 않고, 설비를 말하지 않았으면 equipment는 모든 설비로 둔다.
앞 대화의 숫자는 어떤 질문인지 푸는 데만 쓰고, 그 숫자를 답으로 다시 말하지 않는다. 마크다운 기호는 쓰지 않는다."""

_WRITE_SYSTEM = """이번 조회 결과의 숫자만 말한다. 결과에 없는 숫자는 만들지 않는다. 앞 대화의 숫자도 이번 결과에 없으면 다시 말하지 않는다.
해요체로 짧게 풀어 쓴다. 문장이 끝나면 줄을 바꾼다. 조회 문장을 그대로 베끼지 않는다. 알람 건수 원문의 첫 줄에 합계('알람 N건', 뒤에 설비별 건수가 괄호로 있을 수 있다)가 있으면 첫 문장에 그 합계를 말하고 설비별 건수를 이어 말한다 (합계는 원문의 숫자를 그대로 쓰고 직접 더하지 않는다). 재고 원문에 부족 수량이 있으면 그 숫자를 마지막에 말한다. 원문에 없는 부족 수량은 계산해 만들지 않는다. 마크다운 기호는 쓰지 않는다."""

_ASK_SYSTEM = """조회는 실행하지 않았다. 빠진 것(설비 이름 또는 알람 번호)만 질문한다. 문장이 끝나면 줄을 바꾼다. 숫자를 만들지 않는다. 마크다운 기호는 쓰지 않는다."""


def live(s) -> bool:
    """외부 Claude 채팅인가. 비교 스위치와 상관없이 이 길을 쓴다. 시험의 기본(LLM 꺼짐)은 아니다."""
    return bool(getattr(s, "claude_app", False) and getattr(s, "llm_enabled", False))


def upper_sentence(text: str) -> str:
    """저장된 답에서 아래 원문(원문 보기·안전 고정 서식)을 뺀 위 문장."""
    out = _SAFE.sub("", _ORIG.sub("", text or ""))
    return out.strip()


def history_turns(history: list | None, n: int = TURNS) -> list[dict]:
    """최근 n턴. 사용자 질문과 위에 보인 문장만."""
    out = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        q = str(row.get("question") or "").strip()
        a = upper_sentence(str(row.get("answer") or row.get("conclusion") or ""))
        if q or a:
            out.append({"question": q, "answer": a})
    return out[-n:]


def _history_block(turns: list[dict]) -> str:
    if not turns:
        return ""
    lines = ["[최근 대화]"]
    for t in turns:
        lines.append("질문: " + t["question"])
        lines.append("답: " + t["answer"])
    return "\n".join(lines)


def canonical(name: str) -> str | None:
    return _NAMES.get(re.sub(r"[\s_]+", "", (name or "")).lower())


def period_window(period: str) -> tuple[date | None, date | None, str | None]:
    """기간 말만 계산한다. LLM이 적은 달력 날짜는 지운 뒤의 말에만 맞춘다. 시연 시계가 있으면 그 날짜·근무, 없으면 REFERENCE_AT."""
    text = _CALENDAR.sub(" ", period or "")
    shift = "N" if re.search(r"야간|간밤|어젯밤", text) else ("D" if "주간" in text else None)
    live = sim_clock.current()
    ref = live.at.date() if live else date.fromisoformat(REFERENCE_AT[:10])
    if live is not None and sim_clock.PREV_SHIFT.search(text):
        prev = sim_clock.previous_open()
        return (prev[0], prev[0], prev[1]) if prev else (None, None, shift)
    if live is not None and sim_clock.CUR_SHIFT.search(text):
        cur = sim_clock.current_kind()
        return (cur[0], cur[0], cur[1]) if cur else (None, None, shift)
    if re.search(r"어제|어젯|간밤|전날", text):
        day = ref - timedelta(days=1)
        return day, day, shift
    if "오늘" in text:
        return ref, ref, shift
    m = re.search(r"(?:최근|지난)\s*(\d+)\s*일", text)
    if m:
        n = int(m.group(1))
        end = ref - timedelta(days=1)
        start = end - timedelta(days=max(n, 1) - 1)
        return start, end, shift
    # 달 말 (2026-10-25 AWS 점검 보고): "이번 달"·"10월"은 그 달 중 운영 기록이 있는 기간 (시계 없음이면 9월만 — 예전 동작). 일까지 적은 달력 날짜는 위 _CALENDAR가 이미 지웠다
    from backend.services.answer import month_in_data_period
    if re.search(r"이번\s*달|이번달|금월", text):
        got = month_in_data_period(ref.month)
        if got is not None:
            return got[0], got[1], shift
    m = re.search(r"(?<!\d)(\d{1,2})\s*월", text)
    if m and 1 <= int(m.group(1)) <= 12:
        got = month_in_data_period(int(m.group(1)))
        if got is not None:
            return got[0], got[1], shift
    return None, None, shift


def equipment_scope(text: str) -> list[str] | None:
    """빈 문자열은 설비를 정하지 않은 것이다. `모든 설비`·`모든설비`는 여섯 대다."""
    raw = text or ""
    if _ALL.search(raw):
        return list(SIX)
    ids: list[str] = []
    for m in _EQ.finditer(raw):
        eq = m.group(0).upper()
        if eq in SIX and eq not in ids:
            ids.append(eq)
    return ids or None


def _lookup_question(text: str) -> bool:
    from backend.services.answer import parse
    if FB.select(text or ""):
        return False
    intents = set(parse(text or "").get("intents") or [])
    return bool(intents) and intents <= LOOKUP_INTENTS


def applies(question: str, p: dict, s, history: list | None) -> bool:
    """이 질문을 도구 조회·안전 순서 길로 보낼지. 화면 설명·센서 추세·문서 질문은 아니다."""
    if not live(s):
        return False
    intents = set(p.get("intents") or [])
    if "sensor_trend" in intents:
        return False
    if FB.select(question or ""):
        return True
    if intents and intents <= LOOKUP_INTENTS:
        return True
    turns = history_turns(history)
    if not turns or not _lookup_question(turns[-1]["question"]):
        return False
    q = question or ""
    return bool(_FOLLOW.search(q) or _ONLY_EQ.match(q) or _ALL.fullmatch(q.strip()))


def question_only(raw: dict) -> str | None:
    """질문이 있으면 그 문장(조회가 같이 있어도). 조회만 있으면 None. 둘 다 없으면 빈 문자열."""
    if not isinstance(raw, dict):
        return ""
    q = str(raw.get("question") or "").strip()
    lookups = raw.get("lookups") if isinstance(raw.get("lookups"), list) else []
    if q:
        return q
    if not lookups:
        return ""
    return None


def prepare(lookups: list) -> tuple[list[dict], list[str]]:
    """조회 요청을 실행 목록과, 설비·번호가 없어 실행하지 않을 이름으로 나눈다."""
    ready, blocked = [], []
    for item in lookups or []:
        if not isinstance(item, dict):
            continue
        name = canonical(str(item.get("name") or ""))
        if not name:
            continue
        scope = equipment_scope(str(item.get("equipment") or ""))
        kind = str(item.get("kind") or "").strip()
        if name in NEED_EQUIPMENT and not scope:
            blocked.append(name)
            continue
        # 알람 번호가 없는 알람 건수 질문("어제 알람 몇 건이야/몇 번 떴어?")은 막지 않는다 — 기간 안 알람 전체 건수를 설비별로 더해 답한다 (2026-10-25 AWS 점검 보고. 전에는 설비·번호를 되물었다)
        if name == "oee" and not scope:
            blocked.append(name)
            continue
        period = str(item.get("period") or "")
        start, end, shift = period_window(period)
        outside = None
        if start is None:     # "9월"처럼 달 이름을 말했는데 그 달이 운영 기록 밖이면, 기본 기간(다른 달)을 조용히 대신 쓰지 않고 기록 밖이라고 알린다
            mm = re.search(r"(?<!\d)(\d{1,2})\s*월", _CALENDAR.sub(" ", period))
            if mm and 1 <= int(mm.group(1)) <= 12:
                outside = f"{int(mm.group(1))}월"
        ready.append({"name": name, "equipment": scope, "kind": kind, "start": start, "end": end, "shift": shift, "outside": outside})
    return ready, blocked


def _alarm_code(kind: str) -> str | None:
    m = _CODE.search(kind or "")
    return m.group(1) if m else None


def _one(role: str, item: dict, eq: str | None, user_question: str) -> tuple[list[str], list[dict]]:
    from backend.services.answer import ops_answer
    name = item["name"]
    intent = _INTENT[name]
    raw = user_question or ""
    if name == "stops" and "고장" in (item.get("kind") or "") and "고장 손실" not in raw:
        raw = (raw + " 고장 손실 몇 개").strip()
    if name == "inventory":
        # 재고는 사용자 문장을 다시 읽지 않는다. 종류 칸이 비면 일반 재고, 있으면 그 이름만 품목이다.
        kind = str(item.get("kind") or "").strip()
        raw = f"{kind} 재고" if kind else "재고"
    alarms = []
    if intent == "alarm_count":
        code = _alarm_code(item.get("kind") or "")
        alarms = [{"control": "", "axis": "", "code": code, "sub": ""}] if code else []      # 번호가 없으면 비워 둔다 → ops_answer가 기간 안 전체 건수로 답한다
    p = {
        "intents": [intent],
        "equipment": [eq] if eq else [],
        "start": item["start"], "end": item["end"], "shift": item["shift"],
        "alarms": alarms, "raw": raw, "lot": None, "order": None,
    }
    if name == "equipment_status" and eq:
        p["status_ids"] = [eq]
    elif name == "equipment_status" and item["equipment"]:
        p["status_ids"] = list(item["equipment"])
    texts, data, _ = ops_answer(role, p)
    return texts, data


def execute(role: str, ready: list[dict], user_question: str = "") -> tuple[list[str], list[dict]]:
    """이미 있는 조회만 실행한다. 생산·재고는 설비 없이 한 번, 모든 설비는 여섯 대를 각각 조회한다."""
    texts, data = [], []
    seen_status_all = False
    for item in ready:
        if item.get("outside"):
            from backend.services.answer import period_text
            texts.append(f"확인 필요 — 물으신 기간({item['outside']})은 가상 데이터 기간({period_text()}) 밖이라 운영 기록이 없습니다.")
            continue
        if item["name"] in ONCE or not item["equipment"]:
            targets = [None]
        elif item["name"] == "alarm_count" and len(item["equipment"]) >= len(SIX):
            targets = [None]      # 모든 설비의 알람 건수는 한 번 조회해 합계 줄(총 N건 + 설비별)을 만든다 — 여섯 줄로 나누면 합계를 아무도 말하지 못한다 (2026-10-25)
        elif item["name"] == "equipment_status" and item["equipment"] and len(item["equipment"]) > 1:
            if seen_status_all:
                continue
            seen_status_all = True
            targets = [None]
        else:
            targets = list(item["equipment"])
        for eq in targets:
            got, rows = _one(role, item, eq, user_question)
            texts.extend(got)
            data.extend(rows)
    return texts, data


def _call(messages: list[dict], schema: dict, job: str, s) -> dict:
    try:
        return C.chat_json(messages, schema, job, 1600, s)
    except EXT.ExternalLlmFailure:
        raise
    except Exception as e:  # noqa: BLE001 — 호출 실패는 예외 메시지만 올리고 요청 본문은 남기지 않는다
        EXT.note_failure(job, str(e))
        raise EXT.ExternalLlmFailure(job, str(e)) from e


def _user(question: str, turns: list[dict], extra: str = "") -> str:
    parts = [p for p in (_history_block(turns), "[질문]\n" + question, extra) if p]
    return "\n\n".join(parts)


def decide(question: str, turns: list[dict], s) -> dict:
    messages = [
        {"role": "system", "content": _DECIDE_SYSTEM},
        {"role": "user", "content": _user(question, turns)},
    ]
    return _call(messages, SCHEMA_DECIDE, DECIDE_JOB, s)


def write_answer(question: str, turns: list[dict], originals: list[str], s) -> str:
    extra = "[이번 조회 결과]\n" + "\n".join(originals)
    messages = [
        {"role": "system", "content": _WRITE_SYSTEM},
        {"role": "user", "content": _user(question, turns, extra)},
    ]
    raw = _call(messages, SCHEMA_WRITE, WRITE_JOB, s)
    text = str(raw.get("answer") or "").strip()
    if not text:
        raise EXT.ExternalLlmFailure(WRITE_JOB, "빈 답")
    return text


def ask_missing(question: str, turns: list[dict], blocked: list[str], s) -> str:
    extra = "실행하지 않은 조회: " + ", ".join(blocked) + ". 설비 이름이나 알람 번호가 빠졌다."
    messages = [
        {"role": "system", "content": _ASK_SYSTEM},
        {"role": "user", "content": _user(question, turns, extra)},
    ]
    raw = _call(messages, SCHEMA_WRITE, DECIDE_JOB, s)
    text = str(raw.get("answer") or "").strip()
    if not text:
        raise EXT.ExternalLlmFailure(DECIDE_JOB, "빈 답")
    return text


def _question_answer(base: dict, text: str) -> dict:
    return {**base, "status": "답변", "mode": "조회 도구 (LLM 질문만, 조회 없음)",
            "conclusion": text, "blocks": [{"kind": "lead", "text": text}]}


def _with_original(base: dict, lead: str, originals: list[str], data: list[dict]) -> dict:
    from backend.config import DATA_LABEL
    body = "\n".join(x for x in originals if x)
    blocks = [{"kind": "lead", "text": lead}, {"kind": "section", "text": "원문 보기"}, {"kind": "text", "text": body}]
    meta = [{k: d.get(k) for k in ("tool", "range", "as_of", "label", "is_synthetic")} for d in data if isinstance(d, dict)]
    return {**base, "status": "답변", "mode": "조회 도구 (위 LLM · 아래 원문)",
            "conclusion": lead, "blocks": blocks, "current_data": meta,
            "data_label": DATA_LABEL if data else None, "is_synthetic": bool(data)}


def safety_turn(question: str, base: dict, s, history: list | None) -> dict:
    """안전 순서. 위는 LLM 설명, 아래는 DOC-05 고정 서식. 위 글을 서식에 맞추지 않는다."""
    from backend.services import pure_external as PURE
    from backend.services.answer import PURE_CAUTION_SAFETY_V19
    keys = FB.select(question)
    hits = PURE.context(question, s.pure_topk, s)
    chunks = [c for _, c in hits]
    note = FB.reference_note(keys)
    got = PURE.ask(question, chunks, None, s, fixed_note=note, history=history_turns(history))
    lead = PURE.scrub_labels(str(got.get("answer") or "").strip())
    if not lead:
        raise EXT.ExternalLlmFailure(PURE.JOB, "빈 답")
    blocks = [{"kind": "lead", "text": lead}] + FB.blocks(keys)
    return {**base, "status": "답변", "mode": "안전 순서 (위 LLM · 아래 고정 서식)",
            "conclusion": lead, "blocks": blocks, "caution": PURE_CAUTION_SAFETY_V19,
            "fixed_block": {"keys": keys, "fallback": False}}


def run(question: str, role: str, p: dict, base: dict, s, history: list | None, memo: dict) -> dict:
    if FB.select(question or ""):
        return safety_turn(question, base, s, history)
    turns = history_turns(history)
    raw = decide(question, turns, s)
    asked = question_only(raw)
    if asked is not None:
        if not asked:
            raise EXT.ExternalLlmFailure(DECIDE_JOB, "빈 답")
        return _question_answer(base, asked)
    ready, blocked = prepare(raw.get("lookups") or [])
    if blocked and not ready:
        return _question_answer(base, ask_missing(question, turns, blocked, s))
    if not ready:
        raise EXT.ExternalLlmFailure(DECIDE_JOB, "실행할 조회가 없음")
    texts, data = execute(role, ready, question)
    memo["ops_texts"] = list(texts)
    lead = write_answer(question, turns, texts, s)
    if blocked:
        lead = lead.rstrip() + " " + ask_missing(question, turns, blocked, s)
    return _with_original(base, lead, texts, data)
