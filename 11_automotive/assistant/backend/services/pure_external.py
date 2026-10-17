"""순수 외부 LLM 연결 PURE_EXTERNAL (2026-10-15, research_notes/순수외부LLM_연결_20261015.md — 시험용 복사본 전용).

문서 질문 답을 "사내 문서 조각 + 질문 → 외부 Claude 1번 → 그 답을 그대로 보임"으로 바꾼 비교용 길이다.
새로 쓴 글을 버리는 검사(코드 검사·안전 엄격 검사·뜻 판정·재시도), 줄 고르기, 따로 검증, LLM 질문 분류는 이 길에서 쓰지 않는다.
이 모듈은 부품만 담는다(켜졌나 · 찾기 · 요청 글 만들기 · 호출 · 조각 번호 → 출처). 응답 조립은 answer.py의 `_pure_answer_v19`가 한다.
backend.services.answer를 import하지 않는다(answer가 이 모듈을 import하므로 순환을 막는다).

작동 조건: PURE_EXTERNAL=1 이고, 이 요청이 외부 Claude를 고른 요청(config.claude_app)이고, LLM이 켜져 있을 때만.
로컬 Qwen 요청이나 스위치 끔이면 이 모듈은 아무 일도 하지 않는다 — 지금 동작 그대로.
"""
from __future__ import annotations

import re
import time

from backend.config import Settings
from backend.llm import client as C
from backend.llm import external as EXT
from backend.rag.chunker import Chunk, load_corpus
from backend.rag.search import search

JOB = "pure_answer"          # chat_json 작업 이름. llm/external.py MATERIAL_JOBS에 있어 실패하면 오류(EXTERNAL_LLM_UNAVAILABLE)로 끝난다
PREV_Q_MAX = 300             # 직전 질문 글자 수 상한 (요청 글이 한없이 길어지지 않게)
PREV_A_MAX = 1500            # 직전 답 글자 수 상한

# $ref·$defs 없음 (규칙: 스키마에 $ref를 쓰지 않는다). 필수 칸 셋, 모르는 칸 금지
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer", "cited", "insufficient"],
          "properties": {"answer": {"type": "string"},
                         "cited": {"type": "array", "items": {"type": "string"}},
                         "insufficient": {"type": "boolean"}}}

SYSTEM = (
    "너는 자동차 부품 절삭가공 라인의 사내 문서 도우미다. 사용자 메시지의 [사내 문서 조각]에 적힌 내용만으로 [질문]에 답한다.\n"
    "1. 쉬운 한국어로, 되도록 해요체로 답한다. 필요한 만큼만 쓰고 마크다운 기호(**, #, | 등)는 쓰지 않는다.\n"
    "2. 조각에 있는 내용만 쓴다. 조각에 답이 없으면 insufficient를 true로 하고 answer에는 \"문서에 없음\"이라고만 쓴다. "
    "조각에 없는 내용을 짐작이나 일반 상식으로 채우지 않는다.\n"
    "3. 숫자, 알람 기준값, 부품번호, 차단기 번호 같은 값은 조각에 적힌 그대로만 쓴다. 지어내거나 바꾸지 않는다. "
    "조각에 [가상]·[참고]·[제안] 표시가 붙은 값은 그 표시도 함께 알려 준다.\n"
    "4. 설비를 켜라·끄라·리셋하라·설정을 바꾸라고 지시하지 않는다. 사람이 판단하거나 결정할 일은 \"담당자가 확인\"이라고 쓴다.\n"
    "5. 안전·전기 작업 절차는 조각의 내용을 그대로 옮기기만 한다. 순서를 바꾸거나 단계를 빼거나 더하지 않는다.\n"
    "6. 답의 근거로 쓴 조각의 번호(C1, C2 …)를 cited에 넣는다. answer 글 안에는 문서 이름, 문서 번호, 절 번호, 출처를 쓰지 않는다 (출처는 프로그램이 붙인다).\n"
    "7. [바로 앞 대화]가 있으면 질문이 가리키는 말(그거, 방금 것 …)을 푸는 데만 쓴다. 앞 답을 근거로 삼지 말고 조각에서 찾는다."
)

# ---------------------------------------------------------------- 말투 바꾸기 (PURE_STYLE, 2026-10-15 — 시험용 복사본 전용)
# PURE_STYLE=1이면 위의 SYSTEM·SCHEMA 대신 아래 SYSTEM_CHAT·SCHEMA_CHAT을 쓴다: 같은 조각·같은 질문으로, 문서 문장을 옮겨 적는 말투 대신
# "옆자리 선배가 풀어서 설명하는" 말투와 짜임(opening · points · closing)으로 답하게 한다. 이 모듈이 하는 일은 지시문·스키마를 고르고 받은 글의 표시용 손질(번호 접두어 지움 ·
# 빈 항목 버림)을 하는 것뿐이다 — 답 내용을 검사하거나 다시 요청하거나 뜻을 판정하지 않는다(말투와 안전은 지시문이 정한다). 끄면(기본) 위의 SYSTEM·SCHEMA·max_tokens 그대로다.
MAX_TOKENS = 1200            # 기존 말투의 응답 상한 (끔)
MAX_TOKENS_CHAT = 1600       # 새 말투는 항목 목록이 더해져 조금 더 길다

# $ref·$defs 없음, 개수·길이 제약 없음 (외부 호출이 지원하지 않는 제약은 쓰지 않는다). 필수 칸 다섯, 모르는 칸 금지
SCHEMA_CHAT = {"type": "object", "additionalProperties": False, "required": ["opening", "points", "closing", "cited", "insufficient"],
               "properties": {"opening": {"type": "string"},
                              "points": {"type": "array", "items": {"type": "string"}},
                              "closing": {"type": "string"},
                              "cited": {"type": "array", "items": {"type": "string"}},
                              "insufficient": {"type": "boolean"}}}

_CHAT_HEAD = """
너는 자동차 부품 절삭가공 라인에서 일하는 사람의 질문에 답하는 사내 문서 도우미다. [사내 문서 조각]에 적힌 내용만 근거로 [질문]에 답한다.
옆자리 선배가 질문한 사람에게 직접 설명해 주듯이 말한다. 문서 문장을 그대로 옮겨 적지 말고, 질문이 알고 싶은 것에 맞춰 이해한 대로 풀어서 말한다.

[말투와 짜임]
1. 해요체로 쓴다("~예요", "~해요"). "~합니다"와 섞지 않는다. 쉬운 낱말로, 한 문장에 한 가지만 담는다.
2. opening: 질문에 바로 답하는 결론을 1~2문장으로 쓴다. "문서에 나온 것은", "문서에 따르면"처럼 문서를 주어로 삼아 시작하지 않는다.
3. points: 이유·확인할 것·순서가 셋 이상이면 한 항목에 한 가지씩 나눠 담는다(화면이 번호 목록으로 보여 주므로 항목 안에 번호, "첫째", 기호를 쓰지 않는다). 둘 이하이면 비워 두고 opening에 쓴다. 한 항목은 1~2문장.
4. closing: 꼭 필요한 주의나 이어서 알아 두면 좋은 것만 0~2문장으로 쓴다. 없으면 빈 문자열.
5. 알람 번호를 물으면 opening의 첫 문장은 그 알람이 어떤 알람인지(이름·뜻)부터 조각에 있는 대로 말한다. 조각에 이름이나 뜻이 없으면 지어내지 않는다.
6. 처음 보는 사람이 모를 용어는 조각에 풀이가 있을 때만 한 구절로 풀어 준다. 풀이가 없으면 용어만 쓰고 뜻을 짐작해 붙이지 않는다.
7. 마크다운 기호(**, #, |, -)와 이모지는 쓰지 않는다.

[근거]
8. 사실은 조각에 있는 것만 쓴다. 숫자, 기준값, 부품번호, 차단기 번호는 조각에 적힌 그대로 쓰고 지어내거나 바꾸지 않는다.
9. 조각의 [가상]·[참고]·[제안] 표시는 해당 문장에 말로 녹인다("팀이 정한 가상 기준이에요", "가상 데이터예요"). "표시가 붙은 내용이에요"처럼 표시 자체를 설명하지 않는다. 시연 시나리오 번호 같은 문서 속 내부 용어는 질문이 직접 묻지 않으면 쓰지 않는다.
10. 조각에 없는 부분은 "문서에는 없어요"라고 구분해서 말한다. 일반 상식을 덧붙일 때는 closing에서 "문서에는 없지만 일반적으로는"으로 시작하는 한 문장까지만 쓴다. 숫자, 기준값, 부품, 작업 절차는 일반 상식으로도 말하지 않는다.
11. 답의 일부만 조각에 있으면 있는 부분을 답하고 없는 부분을 closing에서 밝힌다. 답이 전혀 없으면 insufficient를 true로 하고 opening에 이유와 다음에 해 볼 일을 해요체 1~3문장으로 쓴다(points는 빈 배열, closing은 빈 문자열). "문서에 없음"이라고 시작하지 않아도 된다.
""".strip()

# 12번 줄은 PURE_KEEP_SIGNALS=0(운영 길이 꺼져 이 연결이 운영 기록을 못 조회하는 경우)일 때만 넣는다. =1이면 운영 질문은 기존 길로 가므로 이 줄이 필요 없다
_CHAT_OPS = (
    "12. 이 연결은 설비 운영 기록(정지 횟수, 생산량, 재고 수량, 알람이 난 이력, 지금 설비 상태)을 조회하지 못한다. "
    "그런 질문이면 사내 문서에는 없고 여기서는 조회가 안 된다고 말하고, 운영 기록은 운영 조회가 되는 일반 비서 화면에서 물어보라고 안내한다."
)

_CHAT_TAIL = """
[사람이 할 일]
13. 설비를 켜라·꺼라·리셋하라·설정을 바꾸라고 지시하지 않고, "~하세요", "~해도 돼요" 같은 지시·허락 꼴을 쓰지 않는다. 사람이 판단하거나 결정할 일은 누가 하는지 밝혀서 "담당자가 확인해요"처럼 쓴다.
14. 안전·전기 작업 절차는 조각의 순서와 단계를 그대로 말한다. 순서를 바꾸거나 단계를 빼거나 더하지 않는다. 순서 있는 절차는 points에 모두 담는다.

[출처]
15. cited에는 근거로 쓴 조각 번호(C1, C2 …)만 넣는다. 글 안에는 문서 이름, 문서 번호, 절 번호를 쓰지 않는다(프로그램이 붙인다).
16. [바로 앞 대화]가 있으면 질문이 가리키는 말(그거, 방금 것 …)을 푸는 데만 쓴다. 앞 답을 근거로 삼지 말고 조각에서 찾는다.

[모양 예시 — 내용은 사실이 아니라 모양만 본다]
나쁜 예: "문서에 나온 이유는 크게 세 가지예요. 첫째, … 둘째, … 셋째, …"
좋은 예: opening "○○는 △△일 때 뜨는 알람이에요. 자꾸 뜬다면 아래 이유부터 의심해 볼 수 있어요." / points ["…", "…", "…"] / closing "실제 원인은 담당자가 확인해요."
""".strip()


def _chat_system(with_ops_note: bool) -> str:
    return "\n".join([_CHAT_HEAD] + ([_CHAT_OPS] if with_ops_note else []) + ["", _CHAT_TAIL])


SYSTEM_CHAT = _chat_system(True)        # PURE_KEEP_SIGNALS=0 (기본): 운영 기록 조회 안내 줄(12번) 포함
SYSTEM_CHAT_KEEP = _chat_system(False)  # PURE_KEEP_SIGNALS=1: 12번 줄 없음 (번호는 그대로 둔다)

# ---------------------------------------------------------------- 묶음 목록 형식 (PURE_LAYOUT, 2026-10-16 — 시험용 복사본 전용, PURE_STYLE=1일 때만 뜻이 있다)
# PURE_STYLE=1 + PURE_LAYOUT=1이면 위의 SYSTEM_CHAT·SCHEMA_CHAT(opening·points·closing) 대신 아래 SYSTEM_LAYOUT·SCHEMA_LAYOUT을 쓴다: 답을 sections(묶음 목록)로 받는다.
# 묶음 하나 = title(소제목) · text(한 문장) · items(목록). 서로 다른 말(이유 · 확인할 것 · 다음 단계 · 경고 · 담당자 안내)을 묶음으로 나눠 담게 하고, 서버(answer.py)가 묶음마다 화면 블록을 만든다.
# 이 모듈이 하는 일은 지시문·스키마를 고르고 받은 글의 표시용 손질(번호 접두어 지움 · 빈 항목·빈 묶음 버림)을 하는 것뿐이다 — 답 내용을 검사하거나 다시 요청하거나 뜻을 판정하지 않는다.
# 끄면(기본) PURE_STYLE=1의 지시문·스키마·max_tokens(1600)·응답 모양이 한 글자도 바뀌지 않는다.
MAX_TOKENS_LAYOUT = 1800     # 묶음마다 title·text·items 칸이 더해져 PURE_STYLE=1(1600)보다 조금 더 길다

# $ref·$defs 없음, 개수·길이 제약 없음 (외부 호출이 지원하지 않는 제약은 쓰지 않는다). 최상위 필수 칸 셋, 묶음 필수 칸 셋, 모르는 칸 금지
SCHEMA_LAYOUT = {"type": "object", "additionalProperties": False, "required": ["sections", "cited", "insufficient"],
                 "properties": {"sections": {"type": "array",
                                             "items": {"type": "object", "additionalProperties": False, "required": ["title", "text", "items"],
                                                       "properties": {"title": {"type": "string"},
                                                                      "text": {"type": "string"},
                                                                      "items": {"type": "array", "items": {"type": "string"}}}}},
                                "cited": {"type": "array", "items": {"type": "string"}},
                                "insufficient": {"type": "boolean"}}}

_LAYOUT_HEAD = """
너는 자동차 부품 절삭가공 라인에서 일하는 사람의 질문에 답하는 사내 문서 도우미다. [사내 문서 조각]에 적힌 내용만 근거로 [질문]에 답한다.
옆자리 선배가 질문한 사람에게 직접 설명해 주듯이 말한다. 문서 문장을 그대로 옮겨 적지 말고, 질문이 알고 싶은 것에 맞춰 이해한 대로 풀어서 말한다.

[답의 짜임] 답은 sections(묶음 목록)로 낸다. 화면은 묶음을 위에서 아래로 하나씩 그린다.
1. 묶음 하나는 title(소제목), text(한 문장), items(목록)로 이루어진다. 쓸 것이 없는 칸은 title과 text는 "", items는 []로 둔다.
2. 첫 묶음은 title "", text에 질문에 바로 답하는 결론 한 문장, items []로 쓴다. "문서에 나온 것은", "문서에 따르면"처럼 문서를 주어로 삼아 시작하지 않는다. 알람 번호를 물으면 이 문장이 그 알람의 이름·뜻이다(조각에 있는 대로, 이름이나 뜻이 없으면 지어내지 않는다).
3. 이유·확인할 것·순서가 둘 이상이면 소제목(10자 안팎의 짧은 이름)을 단 묶음의 items에 한 항목에 한 가지씩 담는다. 화면이 번호를 붙이므로 항목 안에 번호, "첫째", 기호를 쓰지 않는다. 한 항목은 한 문장이고, 같은 말을 되풀이하거나 부연하지 않는다. 부연이 꼭 필요하면 다음 묶음의 text로 보낸다.
4. 서로 성격이 다른 말은 묶음을 나눈다. 이유(왜 그런가), 확인할 것, 그래도 해결되지 않을 때의 다음 단계, 경고, 담당자 안내를 같은 목록이나 같은 text에 섞지 않는다.
5. text는 한 문장이다. 경고나 안내가 둘이면 text만 있는 묶음 둘로 나눈다. 꼭 필요한 말만 쓰고 묶음은 되도록 5개 이내로 한다.

[말투]
6. 해요체로 쓴다("~예요", "~해요"). "~합니다"와 섞지 않는다. 쉬운 낱말로 쓴다.
7. 처음 보는 사람이 모를 용어는 조각에 풀이가 있을 때만 한 구절로 풀어 준다. 풀이가 없으면 용어만 쓰고 뜻을 짐작해 붙이지 않는다.
8. 마크다운 기호(**, #, |, -)와 이모지는 쓰지 않는다.

[근거]
9. 사실은 조각에 있는 것만 쓴다. 숫자, 기준값, 부품번호, 차단기 번호는 조각에 적힌 그대로 쓰고 지어내거나 바꾸지 않는다. 조각이 어떤 조건 아래에서만 하는 일이라고 말하면 그 조건을 빼지 않는다.
10. 조각의 [가상]·[참고]·[제안] 표시는 해당 문장에 말로 반드시 녹인다. 조각에서 [가상]이 붙은 기준·규칙·값(기간, 횟수, 비율, 팀이 정한 절차 등)을 말할 때는 그 문장 안에서 "팀이 정한 가상 기준이에요"처럼 밝힌다. 표시가 소제목이나 줄 끝에 붙어 있으면 그 아래·그 줄의 내용 모두에 적용된다. "표시가 붙은 내용이에요"처럼 표시 자체를 설명하지 않는다. 시연 시나리오 번호 같은 문서 속 내부 용어는 질문이 직접 묻지 않으면 쓰지 않는다.
11. 조각에 없는 부분은 "문서에는 없어요"라고 구분해서 말한다. 일반 상식을 덧붙일 때는 text만 있는 마지막 묶음에서 "문서에는 없지만 일반적으로는"으로 시작하는 한 문장까지만 쓴다. 숫자, 기준값, 부품, 작업 절차는 일반 상식으로도 말하지 않는다.
12. 답의 일부만 조각에 있으면 있는 부분을 답하고 없는 부분을 text만 있는 묶음으로 밝힌다. 답이 전혀 없으면 insufficient를 true로 하고 첫 묶음 text에 이유와 다음에 해 볼 일을 해요체 1~3문장으로 쓴다(나머지 묶음은 쓰지 않는다). "문서에 없음"이라고 시작하지 않아도 된다.
""".strip()

# 13번 줄은 PURE_KEEP_SIGNALS=0(운영 길이 꺼져 이 연결이 운영 기록을 못 조회하는 경우)일 때만 넣는다. =1이면 운영 질문은 기존 길로 가므로 이 줄이 필요 없다 (번호는 다시 매기지 않는다)
_LAYOUT_OPS = (
    "13. 이 연결은 설비 운영 기록(정지 횟수, 생산량, 재고 수량, 알람이 난 이력, 지금 설비 상태)을 조회하지 못한다. "
    "그런 질문이면 사내 문서에는 없고 여기서는 조회가 안 된다고 말하고, 운영 기록은 운영 조회가 되는 일반 비서 화면에서 물어보라고 안내한다."
)

_LAYOUT_TAIL = """
[사람이 할 일]
14. 설비를 켜라·꺼라·리셋하라·설정을 바꾸라고 지시하지 않고, "~하세요", "~해도 돼요" 같은 지시·허락 꼴을 쓰지 않는다. "~해야 해요"처럼 의무로 말하는 것도 조각이 그렇게 말한 내용(필요하다, 한다, 금지한다 등)일 때만 쓰고 새 의무를 만들지 않는다. 사람이 판단하거나 결정할 일은 누가 하는지 밝혀서 "담당자가 확인해요"처럼 쓴다.
15. 안전·전기 작업 절차는 조각의 순서와 단계를 그대로 말한다. 순서를 바꾸거나 단계를 빼거나 더하지 않는다. 순서 있는 절차는 소제목을 단 묶음의 items에 모두 담는다.

[출처]
16. cited에는 근거로 쓴 조각 번호(C1, C2 …)만 넣는다. 글 안에는 문서 이름, 문서 번호, 절 번호를 쓰지 않는다(프로그램이 붙인다).
17. [바로 앞 대화]가 있으면 질문이 가리키는 말(그거, 방금 것 …)을 푸는 데만 쓴다. 앞 답을 근거로 삼지 말고 조각에서 찾는다.

[모양 예시 — 칸의 모양만 보여 준다. 예시의 글자를 답에 쓰지 않는다]
sections: [
  {"title": "", "text": "(질문에 바로 답하는 결론 한 문장)", "items": []},
  {"title": "(짧은 소제목)", "text": "", "items": ["(한 문장)", "(한 문장)"]},
  {"title": "(짧은 소제목)", "text": "", "items": ["(한 문장)", "(한 문장)"]},
  {"title": "", "text": "(경고나 주의 한 문장)", "items": []},
  {"title": "", "text": "(담당자 안내 한 문장)", "items": []}
]
""".strip()


def _layout_system(with_ops_note: bool) -> str:
    return "\n".join([_LAYOUT_HEAD] + ([_LAYOUT_OPS] if with_ops_note else []) + ["", _LAYOUT_TAIL])


SYSTEM_LAYOUT = _layout_system(True)        # PURE_KEEP_SIGNALS=0 (기본): 운영 기록 조회 안내 줄(13번) 포함
SYSTEM_LAYOUT_KEEP = _layout_system(False)  # PURE_KEEP_SIGNALS=1: 13번 줄 없음 (번호는 그대로 둔다)

# 문서 없음(insufficient)인데 Claude가 opening을 비워 보낸 경우에만 쓰는 짧은 고정 문구 (실패로 치지 않는다)
NO_OPENING_CHAT = "사내 문서에서 질문에 답할 근거를 찾지 못했어요. 쓰신 낱말을 바꿔서 다시 물어봐 주세요."

# points 항목 앞의 번호("1."·"1)"·"(1)"·"①"·"첫째,")는 화면이 번호 목록으로 그리므로 표시용으로만 지운다. "1.5배"처럼 숫자가 이어지는 꼴은 지우지 않는다
_NUM_PREFIX = re.compile(r"^\s*(?:[(\[]?\d{1,2}\s*[.)\]](?![0-9])|[①-⑳]|(?:첫째|둘째|셋째|넷째|다섯째|여섯째|일곱째|여덟째|아홉째|열째)\s*[,，])\s*")

_CITE_NO = re.compile(r"^\s*\[?\s*[Cc]?\s*(\d{1,3})\s*\]?\s*$")


def system_for(s: Settings) -> str:
    """이 요청에 쓸 시스템 지시문. 말투 바꾸기 끔이면 지금 SYSTEM 그대로(같은 객체). 묶음 목록 형식(PURE_LAYOUT)은 말투 바꾸기 켬일 때만 뜻이 있고, 끔이면 SYSTEM_CHAT 계열 그대로."""
    if not s.pure_style:
        return SYSTEM
    if s.pure_layout:
        return SYSTEM_LAYOUT_KEEP if s.pure_keep_signals else SYSTEM_LAYOUT
    return SYSTEM_CHAT_KEEP if s.pure_keep_signals else SYSTEM_CHAT


def schema_for(s: Settings) -> dict:
    """이 요청에 쓸 JSON 스키마. 말투 바꾸기 끔이면 지금 SCHEMA 그대로(같은 객체). 묶음 목록 형식은 말투 바꾸기 켬일 때만 SCHEMA_LAYOUT."""
    if not s.pure_style:
        return SCHEMA
    return SCHEMA_LAYOUT if s.pure_layout else SCHEMA_CHAT


def _tidy_text(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def _tidy_point(x) -> str:
    """항목 하나의 표시용 손질: 문자열이 아니면 버리고, 앞 번호 접두어를 지우고, 앞뒤 빈칸을 뺀다. 내용은 바꾸지 않는다."""
    if not isinstance(x, str):
        return ""
    return _NUM_PREFIX.sub("", x.strip(), count=1).strip()


def compose(raw: dict) -> dict:
    """받은 JSON의 opening · points · closing을 표시 부품으로. 문자열이 아닌 값·빈 항목은 버리고 번호 접두어를 지운다 (내용 검사가 아니다)."""
    pts = raw.get("points") if isinstance(raw.get("points"), list) else []
    return {"opening": _tidy_text(raw.get("opening")), "points": [t for t in (_tidy_point(x) for x in pts) if t], "closing": _tidy_text(raw.get("closing"))}


def join_conclusion(opening: str, points: list[str], closing: str) -> str:
    """[한 문단으로 보기]·이어 묻기 기억·로그에 쓰는 글: `opening 1) … 2) … closing` (빈 부분은 건너뛴다)."""
    parts = [opening] if opening else []
    if points:
        parts.append(" ".join(f"{i}) {p}" for i, p in enumerate(points, 1)))
    if closing:
        parts.append(closing)
    return " ".join(parts)


def compose_layout(raw: dict) -> list[dict]:
    """받은 JSON의 sections를 표시 부품 `[{"title", "text", "items"}, …]`으로. 리스트가 아니면 빈 목록, dict가 아닌 묶음·문자열이 아닌 항목·빈 항목은 버리고,
    항목 앞 번호 접두어를 지우고, title·text·items가 모두 비면 그 묶음을 버린다 (내용 검사가 아니다)."""
    secs = raw.get("sections") if isinstance(raw.get("sections"), list) else []
    out = []
    for sec in secs:
        if not isinstance(sec, dict):
            continue
        its = sec.get("items") if isinstance(sec.get("items"), list) else []
        one = {"title": _tidy_text(sec.get("title")), "text": _tidy_text(sec.get("text")), "items": [t for t in (_tidy_point(x) for x in its) if t]}
        if one["title"] or one["text"] or one["items"]:
            out.append(one)
    return out


def join_layout(sections: list[dict]) -> str:
    """[한 문단으로 보기]·이어 묻기 기억·로그에 쓰는 글: 묶음마다 `[title:] [text] [1) … 2) …]`을 공백으로 잇고, 묶음끼리도 공백으로 잇는다 (빈 부분은 건너뛴다)."""
    out = []
    for sec in sections:
        parts = [sec["title"] + ":"] if sec["title"] else []
        if sec["text"]:
            parts.append(sec["text"])
        if sec["items"]:
            parts.append(" ".join(f"{i}) {p}" for i, p in enumerate(sec["items"], 1)))
        if parts:
            out.append(" ".join(parts))
    return " ".join(out)


def enabled(s: Settings) -> bool:
    """이 요청이 순수 외부 LLM 방식인가: 스위치 켬 + 외부 Claude를 고른 요청 + LLM 켬. 하나라도 아니면 지금 동작 그대로."""
    return bool(s.pure_external and s.claude_app and s.llm_enabled)


def drops_signals(s: Settings) -> bool:
    """순수 방식이고 신호 길(알람 번호·날짜·설비·운영 낱말)도 끄는가 (PURE_KEEP_SIGNALS=0, 기본)."""
    return enabled(s) and not s.pure_keep_signals


def has_signals(p: dict) -> bool:
    """규칙(parse)이 질문에서 알람 번호·설비·날짜·로트·작업지시·운영 조회 낱말 중 하나라도 찾았나 (PURE_KEEP_SIGNALS=1일 때 기존 길로 보내는 기준)."""
    return bool(p.get("alarms") or p.get("intents") or p.get("equipment") or p.get("start") or p.get("lot") or p.get("order"))


def retrieve(question: str, k: int) -> list[tuple[float, Chunk]]:
    """원래 질문 그대로 낱말 검색(BM25 + 용어집 동의어 확장 — rag/search.py)한 상위 k개 조각. 검색어 바꿔 쓰기·문턱·문지기·순위 바꾸기 없음.
    조각 글은 load_corpus()가 만든 것이라 이미 sanitize(원문 이름·번호 가림)를 거쳤다."""
    return search(question, k)


EXPAND_MAX_CHUNKS = 4        # PURE_EXPAND=1: 확장으로 더하는 아래 절 조각 수 상한 (보장하는 부모 조각은 따로 센다)
EXPAND_MAX_CHARS = 2500      # 더하는 아래 절 글자 수 상한

# "잠금 표지 순서" 결함의 둘째 원인: 사용자는 "잠금 표지"뿐 아니라 "작업 전에 **잠그는** 순서", "뭐부터 **잠가**?"라고도 묻는다.
# 그러면 부모 조각(DOC-05 §2 잠금·표지 절차)조차 상위 8개에 못 들어와서(15~112위) 아래 절 확장만으로는 못 고친다. 그래서 질문에 잠금 낱말이 있으면
# 그 부모 조각을 보장한다 (낱말 목록·절 번호를 코드에 박았다 — 문서가 바뀌면 시험 `test_guarantee_anchor_*`가 알려 준다).
LOCK_TERMS = ("잠금", "잠그", "잠가", "잠궈", "잠겨", "자물쇠", "표지", "loto", "lockout", "tagout", "락아웃")
GUARANTEED = ((LOCK_TERMS, "DOC-05", "2"),)       # (질문에 이 낱말이 하나라도 있으면, 이 문서·절의 조각을 보장한다)


def _children(parent: Chunk, corpus: list[Chunk]) -> list[Chunk]:
    """직계 아래 절 (§2 → §2.1·§2.2 …). 손자 절(§2.1.1)은 아니다. 같은 문서 안에서만, 문서 순서 그대로."""
    prefix = parent.section + "."
    return [c for c in corpus if c.doc_id == parent.doc_id and c.section.startswith(prefix) and "." not in c.section[len(prefix):]]


def guarantee(question: str, hits: list[tuple[float, Chunk]]) -> tuple[list[tuple[float, Chunk]], set[str]]:
    """질문에 잠금 낱말(LOCK_TERMS)이 있는데 보장 대상 부모 조각이 상위 조각에 없으면 맨 앞에 더한다 (점수 0.0 = 검색 점수가 아니라는 표시).
    돌려주는 것: (조각 목록, 우선 확장할 부모 조각 번호들). 이미 있으면 목록은 그대로이고 우선 확장 대상으로만 표시한다."""
    q = question.lower()
    corpus = load_corpus()
    out, first = list(hits), set()
    for terms, doc_id, section in GUARANTEED:
        if not any(t in q for t in terms):
            continue
        anchor = next((c for c in corpus if c.doc_id == doc_id and c.section == section), None)
        if anchor is None:
            continue
        first.add(anchor.chunk_id)
        if anchor.chunk_id not in {c.chunk_id for _, c in out}:
            out.insert(0, (0.0, anchor))
    return out, first


def expand(hits: list[tuple[float, Chunk]], max_chunks: int = EXPAND_MAX_CHUNKS, max_chars: int = EXPAND_MAX_CHARS,
           first: set[str] | frozenset[str] = frozenset()) -> list[tuple[float, Chunk]]:
    """"잠금 표지 순서" 결함의 수정 (PURE_EXPAND=1): 낱말 검색은 부모 조각(예: DOC-05 §2 잠금·표지 절차)은 찾아도, 낱말이 다른 아래 절(§2.1 작업 전 6단계)은 66위로 놓친다.
    그래서 상위 조각에 직계 아래 절이 있으면 이미 있는 것을 뺀 아래 절을 짧은 것부터 더한다 — `first`에 든 부모를 먼저, 그다음 위에서부터 차례로, 전체 합쳐 max_chunks개·max_chars자까지.
    원래 조각의 순서·점수는 그대로이고, 더해진 조각은 그 부모 바로 뒤에 문서 순서로 들어가며 점수는 0.0(검색 점수가 아니라는 표시)이다."""
    corpus = load_corpus()
    have = {c.chunk_id for _, c in hits}
    picks: dict[str, list[Chunk]] = {}
    n = chars = 0
    for c in sorted((c for _, c in hits), key=lambda x: x.chunk_id not in first):      # 우선 부모 먼저, 나머지는 원래 순서 (안정 정렬)
        if n >= max_chunks:
            break
        kids = [k for k in _children(c, corpus) if k.chunk_id not in have]
        sel: set[str] = set()
        for k in sorted(kids, key=lambda x: len(x.text)):                              # 짧은 것부터 (같은 길이면 문서 순서)
            if len(sel) >= max_chunks - n or chars + len(k.text) > max_chars:
                break
            sel.add(k.chunk_id)
            chars += len(k.text)
        picks[c.chunk_id] = [k for k in kids if k.chunk_id in sel]                     # 더하는 것은 문서 순서로
        have |= sel
        n += len(sel)
    out: list[tuple[float, Chunk]] = []
    for score, c in hits:
        out.append((score, c))
        out += [(0.0, k) for k in picks.get(c.chunk_id, [])]
    return out


# ---------------------------------------------------------------- PURE_SAFETY (2026-10-18) — 안전 질문의 거짓 "문서에 없다"를 원천 차단
# "톱 정비 전에 어디를 차단해야 해?"가 DOC-05 §3.1(톱 차단 지점)을 검색 68위로 놓쳐 "문서에서 찾지 못했어요"(NOT_IN_DOCS)가 나왔다. 현장 말("톱")과 문서 말("SAW-01·콜드쏘")이
# 다르면 낱말 검색은 정답 절을 못 올린다. 그리고 "못 찾음"을 "문서에 없음"으로 말하는 것이 진짜 위험이다. 그래서 ① 안전 질문에는 안전 작업 기준서(DOC-05)를 통째로 주고
# ② 그래도 답이 없으면 "문서에 없다"가 아니라 "자동으로 확인하지 못함"이라고 말한다 (answer.py `_pure_unsure_v19`). 발동은 낱말로만 한다 — 검색 순위로 발동하면
# "체육대회·병원" 같은 상관없는 질문에서도 DOC-05가 상위에 올라 발동했다 (2026-10-18 실험).
SAFETY_DOC = "DOC-05"            # 안전 작업 기준서
SAFETY_SCORE = -1.0              # 통째로 더한 조각의 표시: 검색 점수가 아니다 (0.0은 PURE_EXPAND가 쓴다)
SAFETY_MAX_CHARS = 20000         # 통째로 더하는 글자 수 상한 (지금 DOC-05는 16,621자 — 문서가 커져도 프롬프트가 폭증하지 않게)
# answer.SAFETY_WORDS(답 끝 안전 문구를 붙이는 낱말)를 모두 포함해야 한다 (시험이 지킨다). 그 뒤는 현장에서 쓰는 낱말과 일반 안전 낱말.
SAFETY_TERMS = ("잠금", "표지", "고전압", "전기", "저항", "차단", "LOTO", "케이블", "앰프",
                "보호구", "감전", "안전", "위험", "자물쇠", "잠그", "잠가", "잠궈", "차단기", "공압", "압축 공기", "절삭유", "알루미늄 칩", "칩 치",
                "톱", "절단", "콜드쏘", "밀링", "머시닝", "세척", "측정기", "프로브", "바렐", "주축", "제어반", "트립", "에너지",
                "정비 전", "정비할", "정비 시작", "수리 전", "전원", "전압", "도어", "협력업체")
EQUIPMENT_RE = re.compile(r"(?<![A-Za-z0-9])(?:(?:SAW|MIL|VF2|WSH|CMM)-\d{2}|VF-2|CMM)(?![A-Za-z0-9])", re.I)     # 설비 이름 (한글이 바로 붙어도 잡는다)
UNSURE_DEFAULT_SECTIONS = ("2", "3", "5")      # 가까운 절을 못 고를 때: 잠금·표지 절차 / 설비별 차단 지점 / 보호구


def is_safety(question: str) -> bool:
    """안전 질문인가 — 낱말만 본다 (대소문자 무시). 이 판정이 켜져야 DOC-05를 통째로 주고 "자동으로 확인하지 못함" 문구를 쓴다."""
    q = question.upper()
    return any(w.upper() in q for w in SAFETY_TERMS) or bool(EQUIPMENT_RE.search(question))


def add_safety_doc(hits: list[tuple[float, Chunk]]) -> list[tuple[float, Chunk]]:
    """검색 결과 뒤에 DOC-05 조각 중 아직 없는 것을 문서 순서로 더한다 (점수 SAFETY_SCORE, 상한 SAFETY_MAX_CHARS). 원래 조각의 순서·점수는 그대로."""
    have = {c.chunk_id for _, c in hits}
    out = list(hits)
    chars = 0
    for c in load_corpus():
        if c.doc_id != SAFETY_DOC or c.chunk_id in have:
            continue
        if chars + len(c.text) > SAFETY_MAX_CHARS:
            break
        out.append((SAFETY_SCORE, c))
        have.add(c.chunk_id)
        chars += len(c.text)
    return out


def unsure_candidates(question: str, hits: list[tuple[float, Chunk]], n: int = 3) -> list[Chunk]:
    """"자동으로 확인하지 못함" 때 보여 줄 가까운 안전 문서 절 (최대 n개, 중복 없음): 검색 점수가 있는 DOC-05 조각 → 전체 검색 순위의 DOC-05 조각 → 기본 절(§2·§3·§5)."""
    out: list[Chunk] = []

    def take(chunks):
        for c in chunks:
            if c.doc_id == SAFETY_DOC and all(c.chunk_id != x.chunk_id for x in out) and len(out) < n:
                out.append(c)
    take(c for sc, c in hits if sc > 0)
    if len(out) < n:
        take(c for _, c in search(question, 300))
    if len(out) < n:
        take(c for c in load_corpus() if c.doc_id == SAFETY_DOC and c.section in UNSURE_DEFAULT_SECTIONS)
    return out


def context(question: str, k: int, s: Settings) -> list[tuple[float, Chunk]]:
    """Claude에 줄 조각: 낱말 검색 상위 k개 (+ PURE_EXPAND=1이면 잠금 낱말 질문의 부모 조각 보장 + 아래 절) (+ PURE_SAFETY=1이면 안전 질문에 DOC-05 통째로).
    둘 다 끄면 retrieve()와 똑같다."""
    hits = retrieve(question, k)
    if s.pure_expand:
        hits, first = guarantee(question, hits)
        hits = expand(hits, first=first)
    if s.pure_safety and is_safety(question):
        hits = add_safety_doc(hits)
    return hits


def build_messages(question: str, chunks: list[Chunk], prev: dict | None = None, system: str = SYSTEM) -> list[dict]:
    """요청 글: ① 시스템 지시 ② (있으면) 바로 앞 질문·답 1번 ③ 번호 붙인 조각들 ④ 질문. 사용자 메시지 하나.
    system을 안 주면 지금 SYSTEM (PURE_STYLE 끔 = 요청 글이 지금과 한 글자도 다르지 않다)."""
    parts = []
    if prev and prev.get("question") and prev.get("conclusion"):
        pq, pa = str(prev["question"]), str(prev["conclusion"])
        parts.append("[바로 앞 대화]\n앞 질문: " + (pq if len(pq) <= PREV_Q_MAX else pq[:PREV_Q_MAX] + "…")
                     + "\n앞 답: " + (pa if len(pa) <= PREV_A_MAX else pa[:PREV_A_MAX] + "…(이하 생략)"))
    parts.append("[사내 문서 조각]\n" + "\n\n".join(f"[C{i}] {c.cite} {c.title}\n{c.text}" for i, c in enumerate(chunks, 1)))
    parts.append("[질문]\n" + question)
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def ask(question: str, chunks: list[Chunk], prev: dict | None, s: Settings) -> dict:
    """외부 Claude 1번 호출. 돌려주는 값: {"answer", "insufficient", "cited_raw"(받은 그대로), "raw"(받은 JSON), "ms", "sent_chars"}.
    연결·시간 초과·형식 오류·빈 답은 ExternalLlmFailure로 올린다 — 자동으로 로컬·다른 길로 돌아가지 않는다(앱 입구가 EXTERNAL_LLM_UNAVAILABLE로 끝냄).
    PURE_STYLE=1이면 새 지시문·스키마·max_tokens로 부르고 "answer"는 `opening 1) … 2) … closing`을 이은 글이며, "style": True와 "opening"·"points"·"closing" 부품이 더해진다
    (insufficient면 points·closing은 비우고 opening 한 문장만 — opening이 비어 있으면 짧은 고정 문구). 끔이면 위 계약 그대로(키도 늘지 않는다).
    PURE_STYLE=1 + PURE_LAYOUT=1이면 새 지시문·스키마(sections)·max_tokens(MAX_TOKENS_LAYOUT)로 부르고 "answer"는 `join_layout` 글이며, "style": True·"layout": True와 "sections" 부품이 더해진다
    (opening·points·closing 키는 만들지 않는다. insufficient면 sections는 모든 묶음 text를 이은 한 묶음 — 글이 없으면 짧은 고정 문구)."""
    style = bool(s.pure_style)
    layout = style and bool(s.pure_layout)
    messages = build_messages(question, chunks, prev, system_for(s))
    sent = sum(len(m["content"]) for m in messages)
    t0 = time.perf_counter()
    try:
        raw = C.chat_json(messages, schema_for(s), JOB, MAX_TOKENS_LAYOUT if layout else (MAX_TOKENS_CHAT if style else MAX_TOKENS), s)
    except (C.LlmUnavailable, C.LlmBadOutput) as e:   # chat_json_claude가 이미 ExternalLlmFailure로 바꾸는 길이지만, 다른 길로 새지 않게 한 번 더 잡는다
        EXT.note_failure(JOB, str(e))
        raise EXT.ExternalLlmFailure(JOB, str(e)) from e
    ms = int((time.perf_counter() - t0) * 1000)
    if layout:
        return _ask_result_layout(raw, ms, sent)
    if style:
        return _ask_result_chat(raw, ms, sent)
    answer = str(raw.get("answer") or "").strip()
    insufficient = raw.get("insufficient") is True
    if not insufficient and not answer:   # 형식이 틀린 답 (내용 검사가 아니다): 빈 답을 화면에 내보내지 않는다
        EXT.note_failure(JOB, "빈 답")
        raise EXT.ExternalLlmFailure(JOB, "빈 답")
    cited_raw = raw.get("cited") if isinstance(raw.get("cited"), list) else []
    return {"answer": answer, "insufficient": insufficient, "cited_raw": cited_raw, "raw": raw, "ms": ms, "sent_chars": sent}


def _ask_result_chat(raw: dict, ms: int, sent: int) -> dict:
    """PURE_STYLE=1의 받은 JSON → ask()의 돌려줄 값. 형식 검사만 한다: insufficient가 아닌데 opening이 비면 빈 답(실패), insufficient인데 opening이 비면 짧은 고정 문구."""
    insufficient = raw.get("insufficient") is True
    parts = compose(raw)
    if insufficient:   # 답이 없다 — opening(Claude가 쓴 이유와 다음 방법) 한 문장 묶음만 쓴다. points·closing은 쓰지 않는다
        parts = {"opening": parts["opening"] or NO_OPENING_CHAT, "points": [], "closing": ""}
    elif not parts["opening"]:   # 형식이 틀린 답 (내용 검사가 아니다): 빈 답을 화면에 내보내지 않는다
        EXT.note_failure(JOB, "빈 답")
        raise EXT.ExternalLlmFailure(JOB, "빈 답")
    cited_raw = raw.get("cited") if isinstance(raw.get("cited"), list) else []
    return {"answer": join_conclusion(parts["opening"], parts["points"], parts["closing"]), "insufficient": insufficient, "cited_raw": cited_raw,
            "raw": raw, "ms": ms, "sent_chars": sent, "style": True, **parts}


def _ask_result_layout(raw: dict, ms: int, sent: int) -> dict:
    """PURE_STYLE=1 + PURE_LAYOUT=1의 받은 JSON → ask()의 돌려줄 값. 형식 검사만 한다: insufficient가 아닌데 손질한 묶음이 하나도 없으면 빈 답(실패),
    insufficient이면 모든 묶음 text를 이은 한 묶음(글이 없으면 짧은 고정 문구)만 쓴다."""
    insufficient = raw.get("insufficient") is True
    sections = compose_layout(raw)
    if insufficient:   # 답이 없다 — Claude가 쓴 이유와 다음 방법(묶음들의 text)을 한 묶음으로 보인다. 소제목·목록은 쓰지 않는다
        text = " ".join(sec["text"] for sec in sections if sec["text"]) or NO_OPENING_CHAT
        sections = [{"title": "", "text": text, "items": []}]
        answer = text
    elif not sections:   # 형식이 틀린 답 (내용 검사가 아니다): 빈 답을 화면에 내보내지 않는다
        EXT.note_failure(JOB, "빈 답")
        raise EXT.ExternalLlmFailure(JOB, "빈 답")
    else:
        answer = join_layout(sections)
    cited_raw = raw.get("cited") if isinstance(raw.get("cited"), list) else []
    return {"answer": answer, "insufficient": insufficient, "cited_raw": cited_raw, "raw": raw, "ms": ms, "sent_chars": sent,
            "style": True, "layout": True, "sections": sections}


def resolve_cites(cited_raw: list, chunks: list[Chunk]) -> tuple[list[Chunk], list]:
    """Claude가 낸 조각 번호("C2"·"[C3]"·"3")를 실제 조각으로. 모르는 번호·번호가 아닌 글(모델이 쓴 문서 이름·번호)은 버리고 겹침은 하나로.
    출처 글자는 늘 프로그램이 조각에서 만든다 — 모델이 쓴 출처 글자는 쓰지 않는다. (조각 목록, 버린 항목)"""
    out, dropped = [], []
    for x in cited_raw:
        m = _CITE_NO.match(x) if isinstance(x, str) else None
        i = int(m.group(1)) if m else 0
        if 1 <= i <= len(chunks):
            if chunks[i - 1] not in out:
                out.append(chunks[i - 1])
        else:
            dropped.append(x)
    return out, dropped
