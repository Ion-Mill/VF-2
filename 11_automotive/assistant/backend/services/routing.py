"""질문 분류 — 표지판 (2026-10-10 계획 3단계 C, 스위치 ROUTE_POLICY).

- rescue (예전): 낱말 규칙이 아무것도 못 찾은 질문만 LLM이 분류한다 (answer.py 안의 예전 경로).
- llm_primary: LLM이 정해진 메뉴(kind·의도·설비·기간·교대) 안에서 주 분류를 맡는다. 실패·형식 오류·시간 초과면 규칙.
- llm_guarded: llm_primary와 같되, LLM이 none인데 규칙이 근거 있는 의도(의도 낱말 + 설비·날짜·로트·알람 중 하나)를
  찾았으면 규칙을 쓴다.
규칙 결과는 LLM에게 힌트로 준다. LLM이 말한 설비·기간·교대는 질문 글에 근거 낱말이 있을 때만 쓰고(ground),
규칙이 찾은 날짜·설비·로트·알람 번호가 LLM보다 우선한다. 알람·절차·안전·사람만 할 일 질문은 LLM에 보내지 않는다(answer.py).
업계 근거: 규칙은 힌트·안전은 결정적으로, LLM은 정해진 메뉴 안의 주 분류기 (개선안_업계표준_조사_20261010.md 2절).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from backend.config import REFERENCE_AT, Settings
from backend.llm import jobs
from backend.services import sim_clock
from backend.services import steplog as SL

REF_DATE = date.fromisoformat(REFERENCE_AT[:10])
# 운영 질문에 붙으면 문서 설명도 함께 찾는 낱말 (answer.py doc_like와 같음)
DOC_WORDS = ("왜", "어떻게", "방법", "순서", "기준", "정의", "범위")

# LLM이 말한 값을 쓰려면 질문 글에 있어야 하는 근거 낱말
PERIOD_WORDS = {
    "today": re.compile(r"오늘|금일"),
    "yesterday": re.compile(r"어제|어젯|간밤|전날|지난\s*밤"),
    "last_shift": re.compile(r"(?:지난|전|앞|직전|이전)\s*교대"),
    "recent_7": re.compile(r"최근\s*(?:7일|일주일|1주일|한\s*주)|일주일|1주일|지난\s*주|이번\s*주"),
    "recent_30": re.compile(r"최근\s*(?:30일|한\s*달)|한\s*달|이번\s*달|지난\s*달|9월\s*(?:전체|내내|한\s*달)"),
}
SHIFT_WORDS = {"N": re.compile(r"야간|밤|새벽"), "D": re.compile(r"주간|낮(?!음|은|춰|추|아|게|다)")}
EQUIP_WORDS = {
    "VF2-01": re.compile(r"VF2-01|1\s*호기|일호기|1번\s*(?:기계|설비)", re.I),
    "VF2-02": re.compile(r"VF2-02|2\s*호기|이호기|2번\s*(?:기계|설비)", re.I),
    "SAW-01": re.compile(r"SAW-01|절단기|톱", re.I),
    "MIL-01": re.compile(r"MIL-01|황삭", re.I),
    "WSH-01": re.compile(r"WSH-01|세척기", re.I),
    "CMM-01": re.compile(r"CMM-01|CMM|측정기", re.I),
}


@dataclass
class Route:
    kind: str                         # doc | ops | mixed | none | action
    intents: list[str]
    equipment: list[str]
    start: date | None
    end: date | None
    shift: str | None
    queries: list[str] = field(default_factory=list)   # 검색에만 쓰는 바꿔 쓴 검색어 (LLM)
    source: str = "규칙"
    trace: dict | None = None
    doc_question: str = ""                             # 섞인 질문의 문서 쪽 질문 글 (SPLIT_Q, LLM) — 맨 끝 (위치 인자 순서 유지)

    def apply(self, p: dict) -> dict:
        """parse() 결과 꼴로 바꾼다 (ops_answer가 읽는 칸). 운영 조회는 kind가 ops·mixed일 때만."""
        return dict(p, intents=list(self.intents) if self.kind in ("ops", "mixed") else [],
                    equipment=list(self.equipment), start=self.start, end=self.end, shift=self.shift)


def rule_route(p: dict, question: str) -> Route:
    kind = ("mixed" if any(w in question for w in DOC_WORDS) else "ops") if p["intents"] else "doc"
    return Route(kind, list(p["intents"]), list(p["equipment"]), p["start"], p["end"], p["shift"])


def _period_dates(period: str) -> tuple[date | None, date | None, str | None]:
    """기간 이름 → (시작, 끝, 정해지는 교대). 날짜는 코드가 정한다 (merge_route와 같은 뜻). 시계가 없으면 10/1·9/30 야간."""
    return sim_clock.named_period(period)


def strong_rules(p: dict) -> bool:
    """규칙의 의도에 질문 글의 근거(설비·날짜·로트·작업지시·알람)가 함께 있나."""
    return bool(p["intents"]) and bool(p["equipment"] or p["start"] or p.get("lot") or p.get("order") or p["alarms"])


def ground(llm: dict, question: str, p: dict) -> Route:
    """LLM 분류를 질문 글의 근거로 거른다. 규칙이 찾은 값이 늘 우선한다."""
    equipment = list(p["equipment"]) or [e for e in llm["equipment"] if EQUIP_WORDS[e].search(question)]
    start, end, shift = p["start"], p["end"], p["shift"]
    if start is None and llm["period"] != "none" and PERIOD_WORDS.get(llm["period"]) and PERIOD_WORDS[llm["period"]].search(question):
        start, end, per_shift = _period_dates(llm["period"])
        shift = shift or per_shift
    if shift is None and llm["shift"] in SHIFT_WORDS and SHIFT_WORDS[llm["shift"]].search(question):
        shift = llm["shift"]
    kind = llm["kind"]
    intents = list(llm["intents"]) if kind in ("ops", "mixed") else []
    return Route(kind, intents, equipment, start, end, shift, list(llm.get("search_queries") or []), "로컬 LLM",
                 doc_question=llm.get("doc_question") or "")


def decide_route(question: str, p: dict, s: Settings) -> Route:
    """질문 분류. 돌려준 Route.trace는 LLM을 불렀을 때만 있다 (평가·로그용)."""
    rules = rule_route(p, question)
    if s.route_policy not in ("llm_primary", "llm_guarded") or not s.job("route"):
        return rules
    route_job = jobs.route_v3 if s.split_q else jobs.route_v2
    hint = {"kind": rules.kind, "intents": rules.intents}
    if s.split_q and rules.intents and not strong_rules(p):
        # 규칙 근거가 약하면(의도 낱말만 있고 설비·날짜·로트·작업지시·알람이 없으면) 힌트를 주지 않는다 —
        # "MTBF 우리말로 뭐라고 해"(kpi), "작업지시 바뀌면 준비하는 데 얼마나 걸려?"(work_orders)에서 LLM이 틀린 힌트를 따라감 (2026-10-10 E001·C02)
        hint = {"kind": "모름", "intents": []}
    if SL.on():   # STEP_LOG 2단계: 낱말 규칙이 정한 분류와 LLM에 실제로 준 힌트 (근거가 약한 규칙은 힌트로 주지 않는다)
        SL.step("2 질문 분류 준비", 규칙분류={"kind": rules.kind, "intents": rules.intents}, LLM에준힌트=hint, 작업=getattr(route_job, "__name__", "route"))
    got, tr = route_job(question, hint)
    if got is None:
        rules.trace, rules.source = tr, "규칙 (LLM 분류 실패)"
        return rules
    g = ground(got, question, p)
    g.trace = tr
    if s.route_policy == "llm_guarded" and g.kind == "none" and strong_rules(p):
        rules.trace, rules.source = tr, "규칙 (LLM none, 규칙 근거 있음)"
        return rules
    if g.kind == "action" and not (s.parse_v2 and s.parse_v3):  # 예전: 요청 꼴 안전장치에 걸리지 않으면 조작 요청으로 단정하지 않음
        g.kind, g.intents = "doc", []
    return g
