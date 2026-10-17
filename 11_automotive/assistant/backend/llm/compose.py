"""문장 담당 — 프로그램이 만든 '기본 문장' 줄을 읽기 쉬운 한국어로 다듬는다 (지침카드·브리핑·문서 초안, 2026-10-17).

역할 나눔 (요구사항 FR-AST-01-04·FR-MNT-02-07·FR-PRD-02-02): 숫자·순서·개수·안전 서식은 프로그램, LLM은 줄마다 문장만.
  · 입력은 줄 목록 [{id, text}] — 프로그램이 계산한 기본 문장이다. 사람 이름·사용자 ID·계정 정보가 들어 있으면 보내지 않는다(privacy.outbound_guard).
  · 출력도 같은 id·같은 순서·같은 개수의 줄이다. 줄마다 `adapter.check_text`(숫자·번호·꼬리표 양방향 대조, 한글 수사·허락/지시 문구·원문 출처 거부)와
    줄 모양 검사(문장 수 유지, 줄바꿈·마크다운 없음, 길이, 종류별 금지 글자)를 통과해야 한다. 하나라도 틀리면 사유를 붙여 한 번 다시 요청한다.
  · 끝내 실패하면 ComposeFailed — 부른 쪽은 지금의 기본 문장을 그대로 쓴다(자동으로 다른 길로 가지 않는다).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from backend.llm import adapter, numbers
from backend.llm import client as LC
from backend.llm import prompts
from backend.privacy import outbound_guard as OG

log = logging.getLogger("assistant")

MAX_LINES = 40
MAX_IN_CHARS = 600
TRIES = 2                       # 첫 요청 + 사유를 붙인 다시 요청 1번


class ComposeFailed(Exception):
    """다듬은 줄을 쓸 수 없다 — 까닭은 서버 로그에만 남긴다(응답에는 싣지 않는다)."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


@dataclass(frozen=True)
class Kind:
    label: str                        # 지시문에 쓰는 이름
    rules: str                        # 종류별 추가 지시
    forbid: tuple[str, ...] = ()      # 줄 안에 있으면 거부하는 글자
    max_chars: int = 600


KINDS: dict[str, Kind] = {
    "shift_report": Kind("교대 보고서의 '특이 사항' 문단을 이루는 문장", "각 줄은 한 문단의 앞뒤로 이어지는 문장이다. 줄마다 문장 수를 그대로 둔다."),
    "daily_report": Kind("일일 보고서 '오늘의 문제'의 번호 항목", "각 줄은 번호 목록의 한 항목이다. 콜론(:)과 ' / '(앞뒤 공백 있는 빗금)을 쓰지 않는다.",
                         forbid=(":", " / ")),
    "work_order": Kind("작업지시서의 제목과 증상", "title 줄은 한 줄짜리 제목(60자 안)이고, symptom 줄은 증상 설명이다. 원인을 새로 만들지 않는다.", max_chars=300),
    "guide_card": Kind("알람 지침카드의 '먼저 할 일' 점검 단계", "각 줄은 점검 순서의 한 단계다. 단계의 순서와 개수를 바꾸지 않고, 점검과 무관한 안내를 더하지 않는다. "
                                                       "안전 절차(잠금·표지)는 프로그램이 따로 붙이므로 쓰지 않는다."),
    "briefing": Kind("교대 시작 브리핑의 보고 항목", "각 줄은 보고 순위 순서대로의 한 항목이다. 항목을 합치거나 순서를 바꾸지 않는다."),
}

_MARKDOWN = re.compile(r"[*#`]|^\s*[-•]\s|^\s*\d+[.)]\s", re.M)
_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> int:
    return len([x for x in _SENT.split(text.strip()) if x])


def system_prompt(kind: str) -> str:
    k = KINDS[kind]
    rules = (f"아래 '기본 문장' 줄들은 프로그램이 계산해 만든 {k.label}이다. 줄마다 현장 사람이 읽기 쉬운 한국어로 다듬어 같은 id의 text 칸에 쓴다.\n"
             "- 줄의 id·순서·개수는 그대로. 줄을 합치거나 나누거나 빼지 않는다.\n"
             "- 숫자·단위·날짜·시각·설비 이름·기록 번호·알람 번호는 하나도 바꾸거나 빼거나 새로 더하지 않는다. 숫자는 아라비아 숫자 그대로 쓴다.\n"
             "- '(추정)', '[가상]', '잠정', '없음' 같은 꼬리표와 계산식을 지우지 않는다.\n"
             "- 원인·허락·지시·판단을 새로 만들지 않는다. 사람 이름을 쓰지 않는다. 길게 늘이지 않는다.\n"
             "- 줄마다 입력과 같은 개수의 문장으로 쓴다. 줄바꿈·목록 기호·마크다운을 쓰지 않는다.\n"
             f"- {k.rules}")
    return prompts.COMMON + "\n" + rules


def messages(kind: str, lines: list[dict], feedback: str | None = None) -> list[dict]:
    user = "기본 문장 줄:\n" + "\n".join(f"{l['id']}: {l['text']}" for l in lines)
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}. 이 점을 고쳐 모든 줄을 다시 쓴다."
    return [{"role": "system", "content": system_prompt(kind)}, {"role": "user", "content": user}]


def schema(ids: list[str], max_chars: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["lines"],
            "properties": {"lines": {"type": "array", "minItems": len(ids), "maxItems": len(ids),
                                     "items": {"type": "object", "additionalProperties": False, "required": ["id", "text"],
                                               "properties": {"id": {"type": "string", "enum": ids},
                                                              "text": {"type": "string", "minLength": 1, "maxLength": max_chars}}}}}}


def _line_problem(kind: str, src: str, text: str) -> str | None:
    k = KINDS[kind]
    if "\n" in text or "\r" in text:
        return "줄바꿈"
    if _MARKDOWN.search(text):
        return "마크다운·목록 기호"
    for bad in k.forbid:
        if bad in text:
            return f"금지 글자 '{bad.strip() or bad}'"
    if len(text) > min(k.max_chars, int(len(src) * 1.6) + 60):
        return "너무 김"
    if sentences(text) != sentences(src):
        return f"문장 수 {sentences(src)}개를 {sentences(text)}개로 바꿈"
    text2 = numbers.tidy(adapter.tidy(text, src), src)
    reason = adapter.check_text(text2, src, num_match="value")
    if reason:
        return reason
    if OG.scrub_text(text2)[1]:
        return "사람 이름·계정 정보"
    return None


def check(kind: str, draft: list[dict], out: dict) -> tuple[list[dict] | None, str | None]:
    """모델이 돌려준 {lines:[{id,text}]}를 검사한다. 통과하면 (다듬은 줄, None), 아니면 (None, 사유 한 문장)."""
    got = out.get("lines")
    if not isinstance(got, list) or [g.get("id") if isinstance(g, dict) else None for g in got] != [d["id"] for d in draft]:
        return None, "줄의 id·순서·개수가 입력과 다름"
    cleaned, problems = [], []
    for d, g in zip(draft, got):
        text = adapter.tidy(str(g.get("text", "")).strip(), d["text"])
        text = numbers.tidy(text, d["text"])
        why = _line_problem(kind, d["text"], text)
        if why:
            problems.append(f"{d['id']}: {why}")
        cleaned.append({"id": d["id"], "text": text})
    if problems:
        return None, "; ".join(problems[:4])
    return cleaned, None


def compose(kind: str, draft: list[dict]) -> dict:
    """기본 문장 줄을 다듬는다. 돌려주는 값: {"lines": [{id,text}], "tries": n}. 못 쓰면 ComposeFailed."""
    if kind not in KINDS:
        raise ComposeFailed("알 수 없는 종류")
    ids = [d["id"] for d in draft]
    if not draft or len(draft) > MAX_LINES or len(set(ids)) != len(ids):
        raise ComposeFailed("줄 목록 모양")
    try:
        OG.assert_clean([d["text"] for d in draft])        # 사람 이름·ID·계정 정보가 든 재료는 가려서 보내지 않고 아예 보내지 않는다
    except OG.OutboundBlocked as e:
        raise ComposeFailed(str(e)) from e
    sch = schema(ids, KINDS[kind].max_chars)
    feedback, why = None, "시도 없음"
    for n in range(1, TRIES + 1):
        try:
            out = LC.chat_json(messages(kind, draft, feedback), sch, f"compose_{kind}", 1500)
        except LC.LlmBadOutput as e:      # 응답은 왔지만 형식이 틀림(줄 수·칸 모자람 등) — 사유를 붙여 한 번 다시 요청한다
            lines, why = None, f"형식 오류: {e}"
            feedback = why
            log.info("문장 형식 거부(%s, %d번째): %s", kind, n, why)
            continue
        except Exception as e:  # noqa: BLE001 — 연결·시간·차단기·외부 실패는 다시 해도 소용없다(안쪽 사정은 로그에만)
            raise ComposeFailed(f"LLM 호출 실패: {type(e).__name__}: {e}") from e
        lines, why = check(kind, draft, out)
        if lines is not None:
            return {"lines": lines, "tries": n}
        feedback = why
        log.info("문장 검사 거부(%s, %d번째): %s", kind, n, why)
    raise ComposeFailed(f"검사 통과 못 함: {why}")
