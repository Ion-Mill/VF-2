"""LLM 어댑터 경계 (NFR-AIQ-09, NFR-SEC-08).

비서는 로컬 LLM(Qwen3.5-9B, 2026-10-08 사용자 결정)으로 돈다. 어떤 어댑터든 정해진 JSON 칸으로만 받고,
검사를 통과하지 못하면 거부하고 프로그램이 만든 기본 문장(draft)을 쓴다. LLM이 실패해도 답은 막히지 않는다.

검사 (2026-10-08 강화 — 예전에는 facts 전체의 숫자와 비교해 틀린 숫자도 통과했다):
- 숫자·기록 번호는 기본 문장과 **양방향**으로 맞아야 한다: 기본 문장의 것은 모두 있어야 하고(빠짐 금지), 새것은 없어야 한다(지어냄 금지).
  스위치 NUM_MATCH=value(2026-10-10)면 글자 대신 값으로 비교한다(numbers.py: 세는 말 묶음·물리 단위 유지, 날짜·번호 통째).
- 한글 수사("세 번"), 허락·지시 문구("해도 됩니다", "리셋하세요"), 원문 출처 표기는 거부한다.
- 주의 문구(caution)·관련 줄(related)은 LLM 칸이 아니다. 늘 프로그램 값을 쓴다.
"""
from __future__ import annotations

import json
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Protocol

from pydantic import BaseModel, ValidationError

from backend.config import settings
from backend.llm import numbers
from backend.rag.sanitize import FORBIDDEN


class AnswerFields(BaseModel):
    conclusion: str
    related: str | None = None
    caution: str | None = None


class LlmOutput(BaseModel):
    """LLM이 채우는 칸은 결론 하나뿐이다."""
    conclusion: str


class LlmAdapter(Protocol):
    name: str

    def write(self, facts: dict, feedback: str | None = None) -> str: ...


class FallbackAdapter:
    """LLM 없이 프로그램이 만든 문장을 그대로 JSON 칸에 넣는다."""
    name = "기본 문장 (로컬 LLM 미연결)"

    def write(self, facts: dict, feedback: str | None = None) -> str:
        return json.dumps({"conclusion": facts["draft_conclusion"]}, ensure_ascii=False)


UNIT = r"(?:번|개|건|분|시간|일|대|명|줄|단계|차례|%|℃|mm|psi|bar|kW|A|V)"
NUM_TOKEN = re.compile(rf"(\d+(?:\.\d+)?)\s*({UNIT})?")
# MR-…, PO-…, LOT-…, VF2-01, DOC-03. 뒤에 조사("VF2-01은")가 붙어도 잡도록 \b 대신 영숫자 경계만 본다
ID_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{1,4}-[0-9A-Z]{2,}(?:-[0-9A-Z]+)*(?![A-Za-z0-9])")
KO_NUM = re.compile(r"(?<![가-힣])(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서른|마흔|쉰)\s*(?:번|개|건|분|시간|대|명|줄|차례|가지)")
DENY = re.compile(r"해도\s*(?:됩니다|돼요?|괜찮)|괜찮습니다|안전합니다|문제\s*없습니다"
                  r"|(?:리셋|재기동|재시작|올리|켜|끄|바꾸|무시|건너뛰|해제)하?(?:세요|십시오)")


MARKERS = ("[가상]", "추정", "잠정", "가상 규칙", "데이터 없음", "없음")


def _norm(n: str) -> str:
    try:
        return format(Decimal(n).normalize(), "f")
    except InvalidOperation:
        return n


def tokens(text: str) -> set[str]:
    """숫자(+단위)와 기록 번호. "65.60%"와 "65.6%"는 같게 본다."""
    out = {f"{_norm(m.group(1))}{m.group(2) or ''}" for m in NUM_TOKEN.finditer(text or "")}
    return out | set(ID_TOKEN.findall(text or ""))


SPACED_UNIT = re.compile(rf"(\d+(?:\.\d+)?)\s+({UNIT})")


def tidy(text: str, source: str) -> str:
    """LLM이 숫자와 단위 사이에 넣은 띄어쓰기("2 단계", "7 일")를 원문이 붙여 쓴 경우에만 붙인다. 내용은 바꾸지 않는다."""
    return SPACED_UNIT.sub(lambda m: m.group(1) + m.group(2) if m.group(1) + m.group(2) in source else m.group(0), text or "")


# 4차 (PARSE_V5, L5): 기본 문장의 "설비 N번" 짝("VF2-01 3번")은 다듬은 문장에도 조사만 붙은 꼴로 남아야 한다.
# 양방향 숫자 검사는 "VF2-01 5번, VF2-02 3번"처럼 값을 맞바꿔도 통과하고, "VF2-01에서 알람 254가 3번"처럼 짝이 흩어져도 통과했다 (E3-093)
PAIR_V5 = re.compile(r"(?<![A-Za-z0-9-])([A-Z][A-Z0-9]*-\d+)\s+(\d+)번")
PARTICLE_V5 = r"\s*(?:은|는|이|가|도|:|으로|로)?\s*"   # 채점기 run_eval.PARTICLE과 같다


def lost_pairs(text: str, draft: str) -> list[str]:
    """기본 문장의 "ID N번" 짝 가운데 다듬은 문장에 (조사만 붙은 꼴로) 없는 것."""
    return [f"{i} {n}번" for i, n in PAIR_V5.findall(draft or "")
            if not re.search(r"(?<![A-Za-z0-9-])" + re.escape(i) + PARTICLE_V5 + re.escape(n) + r"번", text or "")]


def _pairs_reason(text: str, draft: str) -> str | None:
    s = settings()
    if not (s.parse_v2 and s.parse_v3 and s.parse_v4 and s.parse_v5):
        return None
    lost = lost_pairs(text, draft)
    return ("흩어진 설비·횟수 짝: " + ", ".join(lost[:5])) if lost else None


def check_text(text: str, draft: str, num_match: str | None = None) -> str | None:
    """통과하면 None, 아니면 거부 사유. num_match = token(글자로 비교, 예전) | value(값으로 비교, numbers.py).
    정하지 않으면 스위치 NUM_MATCH를 따른다. PARSE_V5면 숫자 검사 뒤에 "설비 N번" 짝도 본다."""
    if not text or not text.strip():
        return "빈 결론"
    if FORBIDDEN.search(text):
        return "원문 출처 표기"
    if KO_NUM.search(text):
        return "한글 수사"
    if DENY.search(text) and not DENY.search(draft):
        return "허락·지시 문구"
    lost = [m for m in MARKERS if m in draft and text.count(m) < draft.count(m)]
    if lost:  # 가상·추정·잠정 표시를 지우면 안 된다 (규칙 2.2)
        return "빠진 꼬리표: " + ", ".join(lost)
    if (num_match or settings().num_match) == "value":
        missing, new = numbers.two_way(text, draft, same_form=True)
        if missing:
            return "빠진 숫자·번호: " + ", ".join(missing[:5])
        if new:
            return "새 숫자·번호: " + ", ".join(new[:5])
        return _pairs_reason(text, draft)
    want, got = tokens(draft), tokens(text)
    if want - got:
        return "빠진 숫자·번호: " + ", ".join(sorted(want - got)[:5])
    if got - want:
        return "새 숫자·번호: " + ", ".join(sorted(got - want)[:5])
    return _pairs_reason(text, draft)


def parse_output(raw: str) -> tuple[LlmOutput | None, str | None]:
    try:
        return LlmOutput.model_validate(json.loads(raw)), None
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        return None, f"형식 오류: {type(e).__name__}"


def validate(raw: str, facts: dict) -> tuple[AnswerFields | None, str | None]:
    out, err = parse_output(raw)
    if err:
        return None, err
    text = tidy(out.conclusion, facts["draft_conclusion"])
    if settings().num_match == "value":
        text = numbers.tidy(text, facts["draft_conclusion"])
    reason = check_text(text, facts["draft_conclusion"])
    if reason:
        return None, reason
    return AnswerFields(conclusion=text, related=facts.get("draft_related"), caution=facts.get("draft_caution")), None


def write_answer(facts: dict, adapter: LlmAdapter | None = None, retries: int = 1,
                 budget_s: float = 15.0) -> tuple[AnswerFields, str, dict]:
    """결론 문장을 받는다. 실패하면 사유를 붙여 다시 요청하고, 그래도 실패하면 기본 문장을 쓴다.

    돌려주는 trace = {job, used, reason, tries, ms} (평가·로그용, 운영 데이터 내용은 넣지 않는다).
    """
    fb = FallbackAdapter()
    t0 = time.monotonic()
    trace = {"job": "write", "used": False, "reason": "LLM 꺼짐", "tries": 0, "ms": 0}
    if adapter is not None and not isinstance(adapter, FallbackAdapter):
        feedback = None
        for _ in range(retries + 1):
            trace["tries"] += 1
            try:
                raw = adapter.write(facts, feedback)
            except Exception as e:  # LLM 서버 실패는 답을 막지 않는다
                trace["reason"] = f"LLM 오류: {type(e).__name__}"
                break
            fields, reason = validate(raw, facts)
            if fields:
                trace.update(used=True, reason=None, ms=int((time.monotonic() - t0) * 1000))
                return fields, adapter.name, trace
            trace["reason"], feedback = reason, reason
            if time.monotonic() - t0 > budget_s - 5:  # 다시 요청할 시간이 모자라면 기본 문장
                break
    fields, _ = validate(fb.write(facts), facts)
    fields = fields or AnswerFields(conclusion=facts["draft_conclusion"], related=facts.get("draft_related"),
                                    caution=facts.get("draft_caution"))
    trace["ms"] = int((time.monotonic() - t0) * 1000)
    mode = fb.name if not trace["tries"] else f"기본 문장 ({settings().llm_label} 결과를 쓰지 않음: {trace['reason']})"
    return fields, mode, trace
