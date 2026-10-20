"""짧은 후속 질문의 이어짐 판단 CONTINUE_LLM (2026-10-21, 261003_창민/이어짐_LLM판단_기획_20261021.md).

"M6 탭 재고는 얼마나 부족해?" 바로 뒤의 "공기 필터는?"은 새 글에 의도 낱말이 없어 문서 길로 갔다. 규칙으로는 "같은 질문 틀에 대상만 바뀜"을 알 수 없어
**이어지는지만 LLM(Haiku)이 판단**하고, 이어지면 완성된 질문 한 문장으로 바꿔 평소 규칙 길로 푼다. 숫자·답은 LLM이 아니라 프로그램이 계산한다.
밖으로 나가는 것은 앞 질문과 새 글 두 줄뿐이다 (앞 답의 내용·숫자·DB 값·작업기록·사용자 정보는 보내지 않는다. 이름·계정은 호출 직전 가려진다).
이 모듈은 answer.py를 import하지 않는다(answer가 이 모듈을 import한다). 판단이 안 서거나 실패하면 None — 부른 쪽이 지금 동작 그대로 간다.
"""
from __future__ import annotations

import re

from backend.config import Settings
from backend.llm import client as C
from backend.services import pure_external as PURE

JOB = "continue"            # 작업 이름 (llm/claude_client.CONTINUE_JOB과 같은 글자). 재료 단계가 아니라 실패해도 오류로 끝나지 않는다
MAX_TOKENS = 200
MAX_CHARS = 20              # 새 글 길이 상한 (공백 뺀 글자 수) — 짧은 후속 질문만
MAX_WORDS = 4               # 새 글 낱말 수 상한
MAX_REWRITE = 80            # 완성된 질문 글자 수 상한

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["continues", "question"],
          "properties": {"continues": {"type": "boolean"}, "question": {"type": "string"}}}

SYSTEM = (
    "너는 사내 채팅의 이어 묻기 판정기다. [앞 질문]과 [새 글]만 보고 판정한다.\n"
    "1. 새 글이 앞 질문이 묻던 것과 같은 종류의 질문을 대상만 바꿔 이어 묻는 짧은 말이면 continues를 true로 하고, "
    "question에 새 글의 대상을 앞 질문의 틀에 넣은 완성된 질문 한 문장을 쓴다.\n"
    "2. 앞 질문과 상관없는 새 질문이거나, 다른 것을 묻거나, 조금이라도 확실하지 않으면 continues를 false로 하고 question은 \"\"로 둔다.\n"
    "3. question에는 [앞 질문]과 [새 글]에 있는 낱말만 쓴다. 새 낱말·숫자·번호·이름·설비를 만들어 넣지 않는다. 답을 쓰지 않는다.\n"
    "예) 앞 질문: M6 탭 재고는 얼마나 부족해? / 새 글: 공기 필터는? → true, 공기 필터 재고는 얼마나 부족해?\n"
    "예) 앞 질문: M6 탭 재고는 얼마나 부족해? / 새 글: 공기 필터는 얼마마다 갈아? → false\n"
    "예) 앞 질문: M6 탭 재고는 얼마나 부족해? / 새 글: 안전 재고가 뭐야? → false"
)

_WORD = re.compile(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣.\-]*")

# 안전 목록(PURE.SAFETY_TERMS)에는 안전 절차를 불러내려고 넓게 잡은 품목·설비 이름도 들어 있다("주축 윤활유는?"이 "주축"에 걸려 판단 호출이 막혔다, 2026-10-21 시연 테스트).
# 이어짐 판단의 관문은 그 이름 낱말만 뺀 나머지(절차·위험 낱말: 잠금·표지·고전압·전기·차단·안전·위험·전원 …)로 막는다. 목록을 새로 베끼지 않고 SAFETY_TERMS에서 빼므로
# 안전 목록에 낱말이 더해지면 여기서도 자동으로 막힌다(안전 쪽으로 실패). 안전 목록과 안전 길 자체는 바꾸지 않는다 — 이어서 푼 질문은 평소처럼 안전 길을 다시 거친다.
ITEM_NAME_TERMS = ("알루미늄 칩", "칩 치", "톱", "절단", "콜드쏘", "밀링", "머시닝", "세척", "측정기", "프로브", "바렐", "주축", "절삭유")


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def blocked_by_safety(question: str) -> bool:
    """안전 절차·위험 낱말이 있어 이어짐 판단(LLM)을 부르지 않을 질문인가 — 품목·설비 이름 낱말(ITEM_NAME_TERMS)은 세지 않는다."""
    q = (question or "").upper()
    return any(w.upper() in q for w in PURE.SAFETY_TERMS if w not in ITEM_NAME_TERMS)


def candidate(question: str, p: dict, prev: dict | None, s: Settings) -> bool:
    """이 질문에 이어짐 판단을 부를 조건 — 전부 만족해야 한다 (기획 3장 1번). 하나라도 아니면 지금 동작 그대로."""
    if not (s.continue_llm and s.claude_app and s.llm_enabled):
        return False
    if not prev or prev.get("status") != "답변" or not (prev.get("question") or "").strip():
        return False
    q = (question or "").strip()
    if not q or len(_squash(q)) > MAX_CHARS or len(q.split()) > MAX_WORDS:
        return False
    if PURE.has_signals(p) or blocked_by_safety(q):   # 알람·설비·날짜·로트·운영 낱말이나 안전 절차·위험 낱말이 있으면 기존 길이 처리한다
        return False
    return True


def grounded(rewritten: str, prev_question: str, question: str) -> bool:
    """완성된 질문이 앞 질문과 새 글에 있는 말로만 만들어졌나 — 2글자 이상 낱말은 모두 두 글 안에 글자로 들어 있어야 하고, 숫자도 그렇다.
    LLM이 낱말·숫자·번호·설비를 몰래 더했으면 거부한다."""
    r = (rewritten or "").strip()
    if not r or len(r) > MAX_REWRITE:
        return False
    source = _squash(prev_question + " " + question)
    for tok in _WORD.findall(r):
        if len(tok) >= 2 and _squash(tok) not in source:
            return False
    return all(d in source for d in re.findall(r"\d+", r))


def judge(question: str, prev_question: str, s: Settings) -> str | None:
    """Claude(Haiku) 1번 — 이어지면 완성된 질문, 아니면(또는 호출 실패·형식 오류) None. 앞 질문과 새 글 두 줄만 보낸다."""
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"[앞 질문]\n{prev_question.strip()[:PURE.PREV_Q_MAX]}\n\n[새 글]\n{question.strip()}"}]
    try:
        out = C.chat_json(messages, SCHEMA, JOB, MAX_TOKENS, s)
    except Exception:   # noqa: BLE001 — 연결·시간 초과·형식 오류·시간 예산 부족: 판단 못 했으니 지금 동작으로 간다
        return None
    if not isinstance(out, dict) or out.get("continues") is not True:
        return None
    rewritten = str(out.get("question") or "").strip()
    if not grounded(rewritten, prev_question, question):
        return None
    if _squash(rewritten) == _squash(question):   # 새 글 그대로면 이어받은 것이 아니다
        return None
    return rewritten


def note(prev_question: str, rewritten: str) -> str:
    pq = prev_question if len(prev_question) <= 40 else prev_question[:40] + "…"
    return f"앞서 물으신 '{pq}'에 이어 '{rewritten}'로 이해했어요."
