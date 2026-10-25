"""화면 요약 (PURE_SCREEN_SUMMARY, 2026-10-21).

보이는 글자 전부가 아니라 화면이 이미 모아 둔 정보판 글자만 Claude에 한 번 보내고, 받은 문장은 앞뒤 공백만 다듬어 그대로 보인다.
고정 문구·숫자 대조·다시 묻기는 하지 않는다. 스위치가 꺼져 있거나 정보판 글자가 없으면 이 모듈은 부르지 않는다 (answer.py가 지금 고정 문구를 그대로 쓴다).
"""
from __future__ import annotations

import re

from backend.llm import client as C
from backend.llm import external as EXT
from backend.llm.claude_client import SCREEN_SUMMARY_JOB

JOB = SCREEN_SUMMARY_JOB
MAX_CHARS = 6000
MAX_TOKENS = 900

# 칩 문구와 같은 뜻만. 알람 번호·"뭐부터"·잠금·위험·권한 질문은 이 길로 보내지 않는다.
_SCREEN_RE = re.compile(
    r"(?:이|지금|현재)\s*(?:화면|페이지).*(?:설명|요약|정리|뭐야|뭐지|뭔지)|여기.*(?:뭐가|뭐\s*떠|요약)"
)
_BLOCK_RE = re.compile(r"\d{3,4}|뭐부터|잠금|표지|위험|권한")

SYSTEM = """너는 자동차 부품 절삭가공 라인 운영 화면을 설명하는 비서다.
아래 [화면 글자]는 사용자가 지금 보고 있는 화면의 정보판에서 가져온 글이다.
사용자의 질문에 답하되, 이 글에 있는 내용만 쓴다. 정보판에 적힌 숫자는 빠뜨리지 않는다.

규칙
1. 화면 글자에 없는 숫자·이름·원인·조치는 쓰지 않는다. 모르면 "화면에는 나와 있지 않습니다"라고 한다.
2. 숫자는 화면에 적힌 그대로 옮긴다. 계산하거나 반올림하거나 합치지 않는다.
3. 판정(고장이다, 위험하다, 괜찮다)과 지시(이렇게 하세요)는 하지 않는다. 화면이 말하는 것만 전한다.
4. "[안전 작업 칸 — 요약하지 않음]"이 있으면 "안전 작업 칸이 있습니다"라고만 말한다. 안전 문구를 지어내거나 풀어 쓰지 않는다.
5. "[가상]" 표시가 있는 내용은 가상 데이터라는 점을 빼먹지 않는다.
6. 보이는 줄이나 같은 항목을 세어 새 숫자를 만들지 않는다. 화면에 그 숫자가 글자로 있을 때만 쓴다.
7. [화면]에 적힌 SCR- 번호는 답에 쓰지 않는다.
8. 칸 이름이 다른 줄은 서로 다른 항목이다. 한 문장으로 잇지 않는다.
9. 화면 설명만 쓴다. 질문 밖에 다른 질문이나 링크·버튼 안내를 덧붙이지 않는다.

모양
- 첫 문장: 이 화면이 무엇인지 한 줄. 문장이 끝나면 줄을 바꾼다.
- 다음: 지금 눈에 띄는 것 3~5줄. 심각도가 높은 것, 숫자가 큰 것부터. 줄마다 "• "로 시작한다.
- 쉬운 말로, 옆자리 선배가 풀어서 말하듯 쓴다. 마크다운 제목·굵은 글씨는 쓰지 않는다."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}


def is_screen_question(question: str) -> bool:
    """화면을 설명해 달라는 말인가. 알람 번호·절차·안전·권한 질문은 아니다."""
    q = (question or "").strip()
    return bool(_SCREEN_RE.search(q)) and not _BLOCK_RE.search(q)


def tighten(text: str) -> str:
    """연속 공백·빈 줄을 줄이고 6000자에서 자른다."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in (text or "").replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    seen: set[str] = set()
    blank = 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 1 and out:
                out.append("")
            continue
        blank = 0
        if ln in seen:
            continue
        seen.add(ln)
        out.append(ln)
    s = "\n".join(out).strip()
    if len(s) > MAX_CHARS:
        s = s[:MAX_CHARS].rstrip() + "\n(이하 생략)"
    return s


def summarize(question: str, screen_code: str, screen_text: str, s) -> str:
    """정보판 글자 + 질문 → Claude 1번 → 답 문장. 빈 답·호출 실패는 ExternalLlmFailure."""
    screen = tighten(screen_text)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"[화면]\n{screen_code}\n\n[화면 글자]\n{screen}\n\n[질문]\n{question}"},
    ]
    try:
        raw = C.chat_json(messages, SCHEMA, JOB, MAX_TOKENS, s)
    except EXT.ExternalLlmFailure:
        raise
    except (C.LlmUnavailable, C.LlmBadOutput) as e:
        EXT.note_failure(JOB, str(e))
        raise EXT.ExternalLlmFailure(JOB, str(e)) from e
    answer = str((raw or {}).get("answer") or "").strip()
    if not answer:
        EXT.note_failure(JOB, "빈 답")
        raise EXT.ExternalLlmFailure(JOB, "빈 답")
    return answer
