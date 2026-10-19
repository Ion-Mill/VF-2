"""문장 담당 — 프로그램이 만든 '기본 문장' 줄을 읽기 쉬운 한국어로 다듬는다 (지침카드·브리핑·문서 초안, 2026-10-17).

역할 나눔 (요구사항 FR-AST-01-04·FR-MNT-02-07·FR-PRD-02-02): 숫자·순서·개수·안전 서식은 프로그램, LLM은 줄마다 문장만.
  · 입력은 줄 목록 [{id, text}] — 프로그램이 계산한 기본 문장이다. 사람 이름·사용자 ID·계정 정보가 들어 있으면 보내지 않는다(privacy.outbound_guard).
  · 출력도 같은 id·같은 순서·같은 개수의 줄이다. 줄마다 `adapter.check_text`(숫자·번호·꼬리표 양방향 대조, 한글 수사·허락/지시 문구·원문 출처 거부)와
    줄 모양 검사(문장 수 유지, 줄바꿈·마크다운 없음, 길이, 종류별 금지 글자)를 통과해야 한다. 하나라도 틀리면 사유를 붙여 한 번 다시 요청한다.
  · 끝내 실패하면 ComposeFailed — 부른 쪽은 지금의 기본 문장을 그대로 쓴다(자동으로 다른 길로 가지 않는다).
  · 브리핑 항목(`briefing`, 2026-10-19)은 줄 하나가 [분류] 꼬리표 + 본문 + 끝 덧붙임(` · 9/29`·`(기한 09/28)`·`(인계)`)이다. 꼬리표·덧붙임은 프로그램이 정한 것이라
    **코드가 떼어 두고 본문만** 보내 다듬은 본문에 다시 붙인다(지침만으로는 못 지켰다: 2026-10-19 측정). 끝내 검사를 못 통과한 줄은 그 줄만 원문으로 두고
    나머지는 돌려준다(다른 종류는 지금처럼 하나라도 틀리면 전부 실패).
"""
from __future__ import annotations

import difflib
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
TITLE_MAX = 60                  # 작업지시서 제목 길이 (한 줄)


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
                                                       "안전 절차(잠금·표지)는 프로그램이 따로 붙이므로 쓰지 않는다. '말고'·'~하지 않는다'·'금지'·'반드시'처럼 하지 말라거나 꼭 하라는 표현은 원문 그대로 둔다. "
                                                       "원문에 없는 안전 용어(잠금·표지·차단·전원·해제 등)를 새로 쓰지 않는다. 원문 낱말을 되도록 그대로 쓰고 어순과 어미만 다듬는다."),
    "briefing": Kind("교대 시작 브리핑 '먼저 챙길 일'의 보고 항목 본문", "각 줄은 보고 순위 순서대로의 한 항목이다. 항목을 합치거나 순서를 바꾸지 않는다. "
                                                          "줄 앞의 [분류]·기호와 줄 끝의 날짜·괄호 덧붙임은 프로그램이 따로 붙이므로 쓰지 않는다. "
                                                          "한 줄은 한 문장으로, '…입니다'·'…했습니다'·'…됩니다'처럼 끝나는 말로 끝맺고 '~하고'·'~며'·'~인데'처럼 이어지는 말로 끝내지 않는다. "
                                                          "'기한 하루 전'·'기한 넘김'·'처리 안 됨'처럼 상태나 시점을 말하는 낱말은 뜻이 바뀌지 않게 그대로 쓴다('기한 하루 전'을 '기한은 하루 전'으로 바꾸지 않는다). "
                                                          "원문이 이미 읽기 쉬우면 그대로 둔다. 원문 낱말을 되도록 그대로 쓰고 조사와 어미만 다듬는다. 줄 끝에 마침표를 붙이지 않는다."),
}

ITEM_KINDS = frozenset({"briefing"})        # 줄 = [꼬리표] + 본문 + 덧붙임. 본문만 보내고, 틀린 줄만 원문으로 돌려놓는다

_KEEP_MARKERS = re.compile(r"말고|말 것|하지 말|마라|지 않|금지|절대|반드시|꼭 ")        # 지침카드: 하지 말라/꼭 하라는 표현은 줄어들면 뜻이 바뀐다
_SAFETY_WORDS = ("잠금", "표지", "차단", "전원", "해제", "LOTO")
SIMILARITY_MIN = 0.5                                                                   # 지침카드: 원문과 글자가 이만큼은 겹쳐야 한다(뜻을 바꿔 쓰지 못하게)
_MARKDOWN = re.compile(r"\*\*|`|^\s*#{1,6}\s|^\s*[-•*]\s|^\s*\d+[.)]\s", re.M)          # 굵게(**)·백틱·줄 머리의 제목/목록 기호. 설비 이름의 "#1"은 정상 글자다
_SENT = re.compile(r"(?<=[.!?])\s+")
_TAG = re.compile(r"^\[[^\]\s]{1,8}\]")
_ITEM_HEAD = re.compile(r"^(?:(?:\[[^\]]+\]|[^\w\s\[(]+)\s+)*")                  # 줄 앞: [분류] 꼬리표·▲ ⓘ ⚠ 🔒 같은 기호 (뒤에 공백)
_ITEM_PAREN = re.compile(r"\s*\([^()]*\)\s*$")                                  # 줄 끝의 (괄호 덧붙임)
_ITEM_DOT = re.compile(r"\s+[·/]\s+(?:(?!\s[·/]\s).)*$")                                      # 줄 끝의 ' · 9/29'·' / 추가: …' 덧붙임
_BAD_END = re.compile(r"(하고|했고|되고|됐고|이고|하며|했으며|되며|됐으며|이며|으며|했는데|하는데|인데|지만|했지만|해서|돼서|되어서|있고|없고|있으며|없으며)$")


def split_item(text: str) -> tuple[str, str, str]:
    """브리핑 항목 한 줄을 (앞 꼬리표·기호, 본문, 끝 덧붙임)으로 나눈다. 셋을 이으면 원래 줄이다. 본문이 비면 줄 전체를 본문으로 둔다."""
    head = _ITEM_HEAD.match(text).group(0)
    rest = text[len(head):]
    body, prev = rest, None
    while prev != body:
        prev = body
        body = _ITEM_PAREN.sub("", body)
        body = _ITEM_DOT.sub("", body)
    body = body.rstrip()
    tail = rest[len(body):]
    if len(body.strip()) < 2:
        return "", text, ""
    return head, body, tail


def _dangling_end(src_body: str, text: str) -> bool:
    return bool(_BAD_END.search(text.rstrip(". "))) and not _BAD_END.search(src_body.rstrip(". "))


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


def _guide_problem(src: str, text: str) -> str | None:
    """알람 지침카드 '먼저 할 일' 줄 전용 — 점검 순서의 뜻이 바뀌지 않았는지 본다 (숫자·번호는 adapter.check_text가 따로 본다)."""
    lost = [m for m in sorted(set(_KEEP_MARKERS.findall(src))) if text.count(m) < src.count(m)]
    if lost:
        return "하지 말라/꼭 하라는 표현이 빠짐: " + ", ".join(lost)
    new = [w for w in _SAFETY_WORDS if w in text and w not in src]
    if new:
        return "원문에 없는 안전 용어: " + ", ".join(new)
    if difflib.SequenceMatcher(None, src, text).ratio() < SIMILARITY_MIN:
        return "원문과 너무 다르게 바꿔 씀"
    return None


def _line_problem(kind: str, src: str, text: str, line_id: str = "") -> str | None:
    k = KINDS[kind]
    if "\n" in text or "\r" in text:
        return "줄바꿈"
    if _MARKDOWN.search(text) and not _MARKDOWN.search(src):      # 원문에 이미 있던 모양은 문제 삼지 않는다
        return "마크다운·목록 기호"
    for bad in k.forbid:
        if bad in text:
            return f"금지 글자 '{bad.strip() or bad}'"
    if len(text) > min(k.max_chars, int(len(src) * 1.6) + 60):
        return "너무 김"
    if kind == "work_order" and line_id == "title" and len(text) > TITLE_MAX:     # 작업지시서 제목은 한 줄 입력칸이다
        return f"제목이 {TITLE_MAX}자를 넘음"
    if sentences(text) != sentences(src):
        return f"문장 수 {sentences(src)}개를 {sentences(text)}개로 바꿈"
    if src.rstrip()[-1:] in ".!?" and text.rstrip()[-1:] not in ".!?":      # 화면이 마침표 뒤 공백으로 문장을 쪼개 쓴다 — 끝 부호를 지키지 않으면 문장이 붙는다
        return "문장 끝 부호(.) 빠짐"
    tag = _TAG.match(src)
    if tag and not text.startswith(tag.group(0)):                              # 앞머리 [긴급]·[생산] 같은 분류 꼬리표
        return f"앞머리 꼬리표 {tag.group(0)} 빠짐"
    text2 = numbers.tidy(adapter.tidy(text, src), src)
    if kind == "guide_card":
        g = _guide_problem(src, text2)
        if g:
            return g
    if kind in ITEM_KINDS:                                                       # 브리핑 본문: 끝맺음·너무 다른 글을 거른다 (꼬리표·덧붙임은 코드가 따로 지킨다)
        if _dangling_end(src, text2):
            return "문장이 끝나지 않음(이어지는 말로 끝남)"
        if difflib.SequenceMatcher(None, src, text2).ratio() < SIMILARITY_MIN:
            return "원문과 너무 다르게 바꿔 씀"
    reason = adapter.check_text(text2, src, num_match="value")
    if reason:
        return reason
    if OG.scrub_text(text2)[1]:
        return "사람 이름·계정 정보"
    return None


def _check_each(kind: str, draft: list[dict], out: dict) -> tuple[list[dict] | None, list[str | None] | str]:
    """줄마다 검사한다. 돌려주는 값: (다듬은 줄, 줄별 사유 — 통과면 None). 줄의 id·순서·개수가 틀리면 (None, 사유 한 문장)."""
    got = out.get("lines")
    if not isinstance(got, list) or [g.get("id") if isinstance(g, dict) else None for g in got] != [d["id"] for d in draft]:
        return None, "줄의 id·순서·개수가 입력과 다름"
    cleaned, whys = [], []
    for d, g in zip(draft, got):
        text = adapter.tidy(str(g.get("text", "")).strip(), d["text"])
        text = numbers.tidy(text, d["text"])
        if kind in ITEM_KINDS and not d["text"].rstrip().endswith("."):      # 항목 줄은 마침표 없이 쓴다 — 붙어 오면 뗀다
            text = text.rstrip().rstrip(".").rstrip()
        why = _line_problem(kind, d["text"], text, d["id"])
        whys.append(f"{d['id']}: {why}" if why else None)
        cleaned.append({"id": d["id"], "text": text})
    return cleaned, whys


def check(kind: str, draft: list[dict], out: dict) -> tuple[list[dict] | None, str | None]:
    """모델이 돌려준 {lines:[{id,text}]}를 검사한다. 통과하면 (다듬은 줄, None), 아니면 (None, 사유 한 문장)."""
    cleaned, whys = _check_each(kind, draft, out)
    if cleaned is None:
        return None, whys
    problems = [w for w in whys if w]
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
    parts = [split_item(d["text"]) for d in draft] if kind in ITEM_KINDS else None
    work = [{"id": d["id"], "text": p[1]} for d, p in zip(draft, parts)] if parts else draft      # 브리핑은 본문만 보낸다

    def whole(lines: list[dict]) -> list[dict]:
        return [{"id": l["id"], "text": p[0] + l["text"] + p[2]} for l, p in zip(lines, parts)] if parts else lines

    try:
        OG.assert_clean([d["text"] for d in work])        # 사람 이름·ID·계정 정보가 든 재료는 가려서 보내지 않고 아예 보내지 않는다
    except OG.OutboundBlocked as e:
        raise ComposeFailed(str(e)) from e
    sch = schema(ids, KINDS[kind].max_chars)
    feedback, why, last_out = None, "시도 없음", None
    for n in range(1, TRIES + 1):
        try:
            out = LC.chat_json(messages(kind, work, feedback), sch, f"compose_{kind}", 1500)
        except LC.LlmBadOutput as e:      # 응답은 왔지만 형식이 틀림(줄 수·칸 모자람 등) — 사유를 붙여 한 번 다시 요청한다
            lines, why = None, f"형식 오류: {e}"
            feedback = why
            log.info("문장 형식 거부(%s, %d번째): %s", kind, n, why)
            continue
        except Exception as e:  # noqa: BLE001 — 연결·시간·차단기·외부 실패는 다시 해도 소용없다(안쪽 사정은 로그에만)
            raise ComposeFailed(f"LLM 호출 실패: {type(e).__name__}: {e}") from e
        lines, why = check(kind, work, out)
        if lines is not None:
            return {"lines": whole(lines), "tries": n}
        feedback = why
        last_out = out
        log.info("문장 검사 거부(%s, %d번째): %s", kind, n, why)
    if kind in ITEM_KINDS and last_out is not None:        # 항목 줄은 틀린 줄만 원문으로 두고 나머지는 돌려준다 (원문 본문은 프로그램이 만든 것이라 늘 안전하다)
        cleaned, whys = _check_each(kind, work, last_out)
        if cleaned is not None:
            fixed = [c if w is None else d for c, d, w in zip(cleaned, work, whys)]
            log.info("문장 일부만 사용(%s): %d줄 중 %d줄은 원문 그대로: %s", kind, len(work), sum(1 for w in whys if w), "; ".join(w for w in whys if w)[:300])
            return {"lines": whole(fixed), "tries": TRIES}
    raise ComposeFailed(f"검사 통과 못 함: {why}")
