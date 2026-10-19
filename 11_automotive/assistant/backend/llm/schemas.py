"""LLM 출력 JSON 칸 (NFR-AIQ-09). 모두 펼친 스키마다 — `$ref`/`$defs`를 쓰면 llama.cpp가 강제를 조용히 끈다(#21228).

서버가 스키마를 강제하더라도 코드에서 다시 검사한다(adapter.check_text, jobs.validate_*).
"""
from __future__ import annotations

from backend.tools.query_tools import EQUIPMENT

INTENTS = ["stops", "production", "inventory", "tool_life", "kpi", "lots", "work_orders", "pm_due", "work_records",
           "alarm_count", "equipment_status", "sensor_trend"]
PERIODS = ["none", "today", "yesterday", "last_shift", "recent_7", "recent_30"]


def phrase(draft_len: int) -> dict:
    """운영 답 다듬기: 결론 한 칸."""
    return {"type": "object", "additionalProperties": False, "required": ["conclusion"],
            "properties": {"conclusion": {"type": "string", "minLength": 1, "maxLength": max(600, int(draft_len * 1.5) + 100)}}}


def select(line_ids: list[str]) -> dict:
    """문서 답 고르기: 후보 줄 번호만 고르고, 앞머리 한 문장을 쓴다. 줄 글은 프로그램이 원문 그대로 옮긴다."""
    return {"type": "object", "additionalProperties": False, "required": ["answerable", "line_ids", "lead"],
            "properties": {"answerable": {"type": "boolean"},
                           "line_ids": {"type": "array", "maxItems": 6, "items": {"type": "string", "enum": line_ids}},
                           "lead": {"type": "string", "maxLength": 160}}}


ROUTE = {"type": "object", "additionalProperties": False, "required": ["kind", "intents", "equipment", "period", "shift"],
         "properties": {"kind": {"type": "string", "enum": ["doc", "ops", "mixed", "none"]},
                        "intents": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": INTENTS}},
                        "equipment": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": sorted(EQUIPMENT)}},
                        "period": {"type": "string", "enum": PERIODS},
                        "shift": {"type": "string", "enum": ["none", "D", "N"]}}}


# ---------------------------------------------------------------- 2026-10-10 계획 3·4단계
KINDS_V2 = ["doc", "ops", "mixed", "none", "action"]

# 분류 v2: kind에 action(시키는 요청), 검색에만 쓰는 바꿔 쓴 검색어(search_queries)를 더했다. 펼친 꼴 그대로
ROUTE_V2 = {"type": "object", "additionalProperties": False,
            "required": ["kind", "intents", "equipment", "period", "shift", "search_queries"],
            "properties": {"kind": {"type": "string", "enum": KINDS_V2},
                           "intents": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": INTENTS}},
                           "equipment": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": sorted(EQUIPMENT)}},
                           "period": {"type": "string", "enum": PERIODS},
                           "shift": {"type": "string", "enum": ["none", "D", "N"]},
                           "search_queries": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 40}}}}

# 따로 검증 (2차 문지기): 고른 줄만 보고 질문에 답할 수 있나
VERIFY = {"type": "object", "additionalProperties": False, "required": ["answers", "missing"],
          "properties": {"answers": {"type": "boolean"}, "missing": {"type": "string", "maxLength": 80}}}


def simplify(n: int, total_len: int) -> dict:
    """이어 묻기 (2026-10-12): 앞 답의 글 조각 n개를 같은 순서로 하나씩 쉽게·짧게 다시 쓴 글."""
    return {"type": "object", "additionalProperties": False, "required": ["texts"],
            "properties": {"texts": {"type": "array", "minItems": n, "maxItems": n,
                                     "items": {"type": "string", "minLength": 1, "maxLength": max(300, int(total_len * 1.6) + 80)}}}}


def simplify_v2(n: int, total_len: int, term_ids: list[str]) -> dict:
    """이어 묻기 2판 (7차 FOLLOWUP_V2): 자리표({{n}})를 품은 조각 n개를 쉽게 다시 쓴 글 + 풀이할 낱말 번호(T1… 3개 이하)."""
    terms = ({"type": "array", "maxItems": 3, "items": {"type": "string", "enum": term_ids}} if term_ids
             else {"type": "array", "maxItems": 0, "items": {"type": "string"}})
    return {"type": "object", "additionalProperties": False, "required": ["texts", "terms"],
            "properties": {"texts": {"type": "array", "minItems": n, "maxItems": n,
                                     "items": {"type": "string", "minLength": 1, "maxLength": max(300, int(total_len * 1.6) + 80)}},
                           "terms": terms}}


def pick_units(unit_ids: list[str]) -> dict:
    """이어 묻기 2판 "짧게": 남길 조각 번호 (1개 이상, 전체보다 적게)."""
    return {"type": "object", "additionalProperties": False, "required": ["keep"],
            "properties": {"keep": {"type": "array", "minItems": 1, "maxItems": max(1, len(unit_ids) - 1),
                                    "items": {"type": "string", "enum": unit_ids}}}}


# 바꿔 쓴 글 검사 (이어 묻기): 원문과 뜻이 같은가
FAITH = {"type": "object", "additionalProperties": False, "required": ["same_meaning", "problem"],
         "properties": {"same_meaning": {"type": "boolean"}, "problem": {"type": "string", "maxLength": 80}}}

# 10차 DOC_WRITE (2026-10-13): 문서 답을 찾은 줄로 새로 쓴 글(자리표 품음) + 따로 판정
WRITE_ANSWER = {"type": "object", "additionalProperties": False, "required": ["answer"],
                "properties": {"answer": {"type": "string", "minLength": 1, "maxLength": 300}}}
ANSWER_FAITH = {"type": "object", "additionalProperties": False, "required": ["faithful", "problem"],
                "properties": {"faithful": {"type": "boolean"}, "problem": {"type": "string", "maxLength": 80}}}


# 분류 v3 (SPLIT_Q, 2026-10-10 2차): 섞인 질문의 문서 쪽 질문 글. 문서 검색·줄 고르기·따로 검증은 이 글로 한다
ROUTE_V3 = {**ROUTE_V2, "required": ROUTE_V2["required"] + ["doc_question"],
            "properties": {**ROUTE_V2["properties"], "doc_question": {"type": "string", "maxLength": 80}}}
