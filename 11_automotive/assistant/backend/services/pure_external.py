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
EXPAND_MAX_CHARS = 3000      # 더하는 아래 절 글자 수 상한 (2026-10-18 DOC-05 Rev.3: §2.1·§2.2 "우리 라인" 칸이 길어져 2.3+2.1+2.2가 2530자가 되어 2500이면 §2.2가 빠졌다. §2.4(2781자)는 3000에서도 안 들어간다)

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


# ---------------------------------------------------------------- PURE_PERIOD (2026-10-18) — 기간 말로 묻는 정비 질문의 거짓 "문서에 없다"를 막는다
# "한 달에 한 번 하는 정비 뭐야?"에서 DOC-04 §2.3 "매월"이 낱말 검색 74~88위로 밀려 Claude에게 가지 않았고 "문서에 없다"는 거짓 답이 나왔다 (측정: 261003_창민/
# 다른문서_놓침_측정_성과_20261018.md). DOC-04의 기간 표는 제목이 "매월·6개월·1년"처럼 한두 낱말뿐이라 현장 말("한 달에 한 번·반기·매년")이 맞을 곳이 없다.
# 제목에 현장 말을 병기해도 그 낱말과 똑같을 때만 듣는다(탐침 16개 중 4개). 그래서 질문에 **기간 낱말**과 **정비 낱말**이 함께 있으면 그 기간의 절 조각을 보장한다
# (PURE_EXPAND=1 안에서, 스위치 PURE_PERIOD). 정규식은 공백을 선택으로 둔다 — 공백을 모두 지우면 "5분 기준"이 "분기"가 된다. 숫자 기간은 앞에 숫자가 없을 때만
# ("2021년"·"16개월"을 "1년"·"6개월"로 읽지 않는다). "2년마다"·"두 달마다"처럼 이 절들이 아닌 기간은 일부러 넣지 않았다.
PERIOD_DOC = "DOC-04"                                   # 예방 정비 기준서
PERIOD_TERMS = {                                        # 절 번호 → 기간 낱말 (정규식, 절 번호 순서가 보장 순서)
    "2.1": r"매일|하루에|하루\s?마다|하루\s?한\s?번|일일\s?점검|교대마다|매\s?교대",
    "2.2": r"매주|주\s?1\s?회|일주일|한\s?주에|주마다|주간\s?점검",
    "2.3": r"매월|매\s?달|월\s?1\s?회|월간|한\s?달(?:에|마다|\s?단위)|(?<!\d)1\s?개월|다달이|(?<!개)월마다|월\s?단위|월별",
    "2.4": r"(?<!\d)3\s?개월|분기|석\s?달|세\s?달|(?<!\d)3\s?달|삼\s?개월",
    "2.5": r"(?<!\d)6\s?개월|반\s?년|반기|여섯\s?달|(?<!\d)6\s?달|육\s?개월",
    "2.6": r"(?<!\d)1\s?년|매\s?년|연간|연\s?1\s?회|일\s?년|한\s?해|해마다|(?<!\d)12\s?개월|열두\s?달|연례|연\s?단위",
    "2.7": r"필요할\s?때|필요하면|필요\s?시|수시|그때그때",
}
PERIOD_RE = {sec: re.compile(pat) for sec, pat in PERIOD_TERMS.items()}
PERIOD_CONTEXT_RE = re.compile(r"정비|점검|교체|청소|보충|윤활|소모품|주기|항목|그리스|필터")      # 함께 있어야 발동 ("매일 몇 시에 퇴근?"에는 발동하지 않는다)


def period_sections(question: str) -> list[str]:
    """질문의 기간 낱말이 가리키는 DOC-04 절 번호들 (절 번호 순서). 정비 낱말이 없으면 빈 목록."""
    q = question.lower()
    if not PERIOD_CONTEXT_RE.search(q):
        return []
    return [sec for sec, rx in PERIOD_RE.items() if rx.search(q)]


def guarantee_period(question: str, hits: list[tuple[float, Chunk]]) -> list[tuple[float, Chunk]]:
    """질문의 기간에 해당하는 DOC-04 절 조각이 상위 조각에 없으면 맨 앞에 더한다 (점수 0.0 = 검색 점수가 아니라는 표시). 이미 있거나 기간이 없으면 목록을 그대로 돌려준다."""
    secs = period_sections(question)
    if not secs:
        return hits
    corpus = load_corpus()
    have = {c.chunk_id for _, c in hits}
    add = []
    for sec in secs:
        anchor = next((c for c in corpus if c.doc_id == PERIOD_DOC and c.section == sec), None)
        if anchor is not None and anchor.chunk_id not in have:
            add.append((0.0, anchor))
    return add + list(hits) if add else hits


# ---------------------------------------------------------------- PURE_RULE (2026-10-18) — 운영 낱말이 든 규칙 질문을 문서 길로
# "소모품 재고는 누가 관리해?"·"홀드 걸린 로트도 내보낼 수 있어?"는 로트·재고 낱말 때문에 규칙 해석이 운영 조회(intents)로 읽어 기존 길로 간다. 그러면 규칙을 묻는 질문이
# 재고 부족 목록이나 "로트 번호를 알려 주세요"를 받는다 (측정 261003_창민/DOC06_놓침_측정_성과_20261018.md: DOC-06 기존 길 10개 중 문서 답 2개, DOC-04 11개 중 5개).
# 신호가 **운영 낱말(intents)뿐**이고, **지금 상태를 묻는 말이 없고**, **규칙·정책 낱말이 있을 때만** 문서 길로 보낸다. 정밀도가 우선이라 낱말을 보수적으로 둔다:
# 번호(로트·작업지시)·설비 이름·날짜·알람이 있으면 진짜 조회일 가능성이 높아 항상 기존 길이고, 문서 길이 "문서에 없음"이면 answer()가 원래 기존 길로 되돌린다.
RULE_WHY = "신호가 운영 낱말뿐인 규칙·정책 질문 — 문서 질문으로 보고 순수 길로 (PURE_RULE=1, 문서에 없으면 기존 길로 되돌림)"
RULE_MIN_LEN = 10                        # 공백·부호를 뺀 글자 수가 이보다 짧은 질문("재고 왜 이래?")은 조회로 본다
RULE_PAST = (r"(?:았|었|였|했|됐|왔|갔|봤|썼|췄|떴|겼|렸|났|랐|찼|쳤|졌|혔|냈|줬)"
             r"(?:어|어요|죠|지|나요|나\?|습니까|음|대|냐|는지|다|네|\b)")      # 과거형 — 끝맺음이 바뀌어도("했나요·했는지·했대") 지나간 일을 묻는 말
RULE_LIVE_RE = re.compile(                                              # 지금·지난 실제 데이터를 묻는 말 (하나라도 있으면 규칙 질문이 아니다)
    r"지금|현재|오늘|어제|그제|엊그제|내일|이번\s?(?:주|달|교대|분기|월)|저번|지난\s?(?:주|달|교대|밤|번|분기)|최근|방금|아까|요즘|금주|금월|올해|작년|"
    r"\d+\s?(?:일|주|개월|달)\s?(?:전|동안|간)|현황|이력|내역|목록|리스트|통계|추이|추세|"
    r"몇\s?(?:건|대|명)|남았|남은|남아|부족한|부족해|넘긴|넘은|밀린|늦은|지연|"
    r"진행\s?중|하는\s?중|대기\s?중|기다리는|것\s?같|걸려\s?있|떠\s?있|와\s?있|" + RULE_PAST + r"|"
    r"(?:^|\s)(?:이|그|저)\s?(?:로트|재고|소모품|부품|설비|공구|작업지시|정비|건|알람)|"                                     # 지시어: 특정 대상을 가리키면 조회
    r"보여\s?줘|보여\s?주세요|찾아\s?줘|찾아\s?주세요|조회|확인해\s?줘|확인해\s?주세요|확인할\s?수\s?있|"                      # 조회 동사
    r"(?:한|된|인|안\s?한|안\s?된|못\s?한)\s?(?:로트|재고|품목|항목|정비|부품|공구|소모품|거|것)\b")                            # 관계절로 대상을 거르는 말 ("합격한 로트")
RULE_MARK_RE = re.compile(                                              # 규칙·정책을 묻는 말 (하나는 있어야 한다). 약한 낱말(어느 로트·종류·차이·승인 필요·결정형 "~도 돼?")은 일부러 뺐다
    r"누가|누구\s?(?:권한|승인|책임|몫)|누구(?:한테|에게)|"
    r"(?:기준|규칙|규정|원칙|방식|방법|절차|순서|조건|정책)(?:이|은|는|을|를)?\s?(?:뭐|뭔|무엇|어떻게|어떤|어때|있|알려|정해|따라)|"
    r"(?:방식|방법|절차|순서|기준)(?:으로|대로|에\s?따라)|"
    r"목표(?:가|는)?\s?(?:얼마|몇)|권한이\s?(?:있|필요)|"
    r"왜\s.*(?:아니|않|못|안\s|필요|해야|하는\s?거|하는지)|"
    r"어떻게\s?(?:해야|하면|처리|계산|판정|구해|정해|바꿔|관리|기록|입력|넣어|빼|써|세|재)|(?:뭘로|무엇으로)\s?(?:세|재|계산|구)|정확히\s?(?:어떤|어떻게|뭘)|"
    r"수\s?있(?:어|나|는지)|되나|안\s?돼|해야\s?(?:해|하나)|하면\s?(?:돼|되)|거\s?맞|맞는\s?거|"
    r"몇\s?(?:%|퍼센트|개마다|번마다|분마다|시간마다|로트까지|순위)|얼마마다|언제까지|언제부터|몇\s?(?:달|주|일|개월|시간)에\s?한\s?번|보통\s?(?:몇|얼마|어떻게)|"
    r"수\s?있는[^?？]{0,15}(?:뭐뭐|종류|상태)|무슨\s?(?:종류|뜻|의미)|뜻이|의미가|형식이|양식이|어떤\s?(?:모양|형식|식|방식|수량)|"
    r"알림이\s?(?:가\s?[?？]|가나|가요|가는|간다)|기능이\s?있|들어가|포함(?:돼|되|해)|차감(?:돼|되나|되는|이)|자동으로\s?(?:차감|빠)|"
    r"어느\s?(?:것|쪽)부터|어느\s?(?:공정|시점|단계|시간대|때)|안전\s?재고(?:는|가)?\s?(?:몇|얼마)|(?:로|으로)\s?관리해|관리\s?(?:하나|해야)|지나면|"
    r"(?:이면|하면|할\s?때|일\s?때|라면)[^?？]{0,25}?어떻게\s?(?:되|돼|처리|해)|정해\s?(?:뒀|놨|져|둔|두었)|정의|차이가\s?뭐|뭐가\s?달라")
# 문서 길 지시문에만 더하는 한 줄: 운영 기록을 묻는 질문이 문서의 느슨한 조각으로 그럴듯하게 답되지 않고 "문서에 없음"(→ 기존 길로 되돌림)이 되게 한다
RULE_OPS_NOTE = ("[추가 규칙] 이 질문이 지금·과거의 실제 운영 기록(재고 수량, 로트 상태, 알림 내역, 정지 횟수, 누가 했는지 등 일어난 일)을 묻는 것이면 "
                 "사내 문서로는 답할 수 없다. 규칙·기준·절차를 묻는 것이 아니면 insufficient를 true로 하고 answer에는 \"문서에 없음\"이라고만 쓴다.")

# PURE_FAULT=1 (2026-10-18, 기획 고장대응_질문_라우팅): "툴 수명 다 됐다고 뜨는데 예비 날이 없어. 어떻게 해?"·"지멘스 밀이 멈췄어. 내가 다시 돌려도 돼?"처럼 증상을 말하고 **무엇을 해야 하는지** 묻는 질문은
# 운영 낱말(수명·재고·정지·로트 …)이 있다는 이유로 기존 길(운영 조회)로 가서 엉뚱한 운영 목록을 받았다. PURE_RULE은 규칙 낱말이 필요하고 과거형·지시어를 거절해 이 모양을 못 잡는다.
# 조건: 신호가 운영 낱말(intents)뿐 · 10자 이상 · **행동을 묻는 표지**(어떻게 확인/해, 뭐부터, 해도 돼, 어떤 값으로 …)가 있거나 증상 서술과 함께 약한 표지(어디 있어, 정상이야 …)가 있음 ·
# **데이터를 묻는 말**(몇 개·목록·현황·이력·누가 했나·남았나·"이 로트" 지시어 …)이 없음. 증상 서술(떴어·멈췄어)은 거절 사유가 아니다. 문서 길이 "문서에 없음"이면 기존 길로 되돌린다(PURE_RULE과 같다).
FAULT_WHY = "신호가 운영 낱말뿐인 고장 대응 절차 질문 — 문서 질문으로 보고 순수 길로 (PURE_FAULT=1, 문서에 없으면 기존 길로 되돌림)"
FAULT_STRONG_RE = re.compile(
    r"어떻게\s?(?:확인|조치|처리|대처|대응|해결|풀|고쳐|하|해|써|채|넣|맞춰|바꿔|돌려|이어|복구|리셋|점검|교체|보충|빼|끄|켜|눌러|열어|닫아|설정|입력|기록|만들|올려|내려|꺼내|달|조여|맞추|판단|구분|찾|살려|막|재|측정|보|읽)|"
    r"(?:뭐|뭘|무엇을?|무얼)\s?(?:부터|먼저|확인|해야|하면|봐야|보면|점검|조치|써야|넣어야|누르|해\b|해요|하나|하죠|할까|보라|하라|보는|하는)|(?:뭐|뭘)\s?\S{0,5}(?:봐|돌려|눌러|열어|넣어|써|해)\s?[?？]?|"
    r"(?:확인|점검|조치|준비|체크)\s?(?:할|해야\s?할|해야\s?하는)\s?(?:게|거|것|건|사항|내용)?\s?(?:뭐|뭔|무엇|있)|"
    r"(?:해도|써도|돌려도|눌러도|켜도|꺼도|풀어도|열어도|닫아도|내보내도|보내도|넘겨도|계속해도|시작해도|만져도|움직여도|건드려도|해제해도|리셋해도|무시해도|이어서\s?해도|나와도|올라가도|내려가도)\s?(?:돼|되|괜찮|상관)|"
    r"(?:하면|보면|누르면|만지면|건드리면|움직이면|돌리면|열면)\s?안\s?(?:돼|되는)|(?:안\s?되는|하면\s?안\s?되는)\s?(?:거지|거야|거죠|건가)|"
    r"어떤\s?\S{1,8}(?:으로|로)\s?(?:채|넣|써|해야|맞춰|교체|바꿔|보충)|어떤\s?(?:값|숫자|키|버튼|순서|걸로)|얼마까지|"
    r"누가\s?(?:정하|조치|처리|확인|해야|하는|해결|보|풀|받)|(?:내가|작업자가|반장이|보전이)\s?\S{0,8}(?:정하는|하는|처리하는|조치하는)\s?(?:거야|거예요|건가|거죠)|"
    r"(?:어야|아야|해야)\s?(?:돼|되|해|하나|하는\s?거|하는지|할까)|(?:이래도|그래도)\s?(?:정상|괜찮|돼)|"
    r"(?:방법|절차|순서)\s?(?:알려|좀\s?알려|이\s?뭐|가\s?뭐)|(?:어디서|어디를)\s?(?:확인|봐|보|열|넣|찾)|순서대로|단계별로|"
    r"뭐가\s?문제|알림이\s?나가(?:요|나|는지|\?|？)|자동(?:으로)?\s?(?:차감|빠지|빠져|들어가|생성|만들어|알림|전환)|"
    r"거(?:야|예요|에요|죠)\s?[,，]\s?[^?？]{1,25}거(?:야|예요|에요|죠)\s?[?？]|"
    r"몇\s?(?:ft-?lbs?|psi|bar|mm|cm|kg|N·?m|Nm|rpm|V\b|도\b|℃|초|분)")
FAULT_WEAK_RE = re.compile(r"어디\s?(?:있|에\s?있)|안\s?(?:나와|나오나|돼|되나|열려|켜져|읽혀|잡혀|올라가)\s?[?？]\s*$|정상이야|이상\s?없어")
FAULT_SYMPTOM_RE = re.compile(r"모자라|떴|뜨는|뜨고|떠서|안\s?(?:읽|잡|돼|되|켜|열|나)|멈췄|멈추|정지|걸렸|났|나서|꺼졌|막혔|샌다|새는|과열|경고|에러|고장|깜빡|울려|울리")
FAULT_DATA_HARD_RE = re.compile(
    r"몇\s?(?:개|건|대|명)|목록|리스트|현황|이력|내역|통계|추이|추세|집계|보여\s?줘|보여\s?주세요|찾아\s?줘|조회|"
    r"(?:누가|언제|몇\s?시)\s?\S{0,10}(?:했|바꿨|나왔|났|입력했|검사했|확인했|처리했|교체했|넣었|뺐|걸었|받았)|"
    r"(?:지금|현재)\s?(?:상태|몇|얼마|어디|누가|뭐가)|(?:오늘|이번\s?주|이번\s?달|어제)\s?(?:몇|얼마|뭐|어떤|점검|해야)|"
    r"어떻게\s?(?:됐|돼\s?가|되고|되어|됐나)|얼마나\s?(?:남|있|썼|걸렸)|얼마\s?(?:남|있)|"
    r"(?:^|\s)(?:이|그|저)\s?(?:로트|재고|소모품|부품|설비|공구|작업지시|정비|건|알람)|어느\s?(?:로트|설비|공구|재고|품목|정비|항목)")
FAULT_DATA_SOFT_RE = re.compile(r"남았|남은|남아|부족한|넘긴|넘은|밀린|늦은|지연")           # 질문 마지막 문장에만 건다 (앞 문장은 증상 서술일 수 있다)


def _last_sentence(q):
    parts = [x.strip() for x in re.split(r"(?<=[.?!？])\s+", q.strip()) if x.strip()]
    return parts[-1] if parts else q


# PURE_RETRY=1 (2026-10-18, 기획 못찾음_넓게다시보기): 정답 조각이 검색 9~50위라 상위 조각에 못 들면 Claude가 \"조각에 답이 없다\"(insufficient)고 하고, 비서는 그것을 \"문서에 없음\"으로 내보냈다
# (못 찾음을 없음으로 말함). ① 첫 호출이 insufficient이면 상위 PURE_RETRY_TOPK개 조각으로 한 번 더 묻는다 — 그 두 번째 호출의 지시문에만 RETRY_NOTE를 더한다.
# ② 첫 호출 지시문에는 PARTIAL_NOTE를 더한다 — 일부만 조각에 있을 때 없는 부분을 \"문서에 없다\"고 단정하지 않고 \"받은 조각에서는 찾지 못했다\"고 말하게 한다. 둘 다 지시문 한 줄이고 답 내용을 검사하지 않는다.
RETRY_NOTE = ("[넓게 다시 본 조각] 처음 받은 조각에서 답을 찾지 못해, 질문과 관련 있을 수 있는 조각을 더 넓게 가져왔다. 이 중에 답이 있으면 그 조각만 근거로 답하고 인용한다. "
              "이 조각들에서도 답이 없으면 insufficient를 true로 한다. 조각에 없는 내용은 지어내지 않는다.")
PARTIAL_NOTE = ("[추가 규칙] 받은 조각에서 찾지 못한 부분을 밝힐 때는 \"문서에 없다\"고 단정하지 말고 \"받은 조각에서는 찾지 못했다\"고 쓴다.")


def rule_question(question: str, p: dict) -> bool:
    """신호가 운영 낱말(intents)뿐인 규칙·정책 질문인가 (PURE_RULE). 번호·설비·날짜·알람이 있거나 신호가 아예 없으면 False(앞은 진짜 조회, 뒤는 이미 순수 길)."""
    if not p.get("intents"):
        return False
    if p.get("alarms") or p.get("equipment") or p.get("start") or p.get("end") or p.get("lot") or p.get("order"):
        return False
    q = question.strip()
    if len(re.sub(r"[\s?？!.~,]", "", q)) < RULE_MIN_LEN:
        return False
    return bool(RULE_MARK_RE.search(q)) and not RULE_LIVE_RE.search(q)


# PURE_RULE_WIDE=1 (2026-10-18, 기획 규칙질문_라우팅_넓히기): PURE_RULE은 규칙을 묻는 낱말(RULE_MARK_RE)이 있어야 문서 길로 보내 재현율이 낮았다(조정용 은행의 대상 구역 44%, 독립 은행 35%).
# 규칙 질문의 말투는 다양한 반면("~는 반장이 해?", "~이야, 아니면 ~야?", "~인가요?") 운영 조회의 말투는 좁다(몇 개·있어?·알려줘·모자란·중에 …). 그래서 양성 표지를 풀고
# 음성 표지(조회 말투)를 강화한다: 신호가 운영 낱말뿐 · 10자 이상 · 지금 상태를 묻는 말(RULE_LIVE_RE)이 없고 · 규칙 낱말이 있거나(= 좁은 규칙 그대로 받는다) 조회 말투(RULE_WIDE_DATA_RE)가 없음.
# 틀려도 비용은 작다: 문서 길이 "문서에 없음"이면 기존 길로 되돌아온다(RULE_OPS_NOTE + 되돌리기, PURE_RULE과 같은 장치라 RULE_WHY를 그대로 쓴다).
RULE_WIDE_DATA_RE = re.compile(
    r"몇\s?(?:개|건|대|명|번|종|종류)(?:이|가)?\s?(?:야|예요|에요|인가요|나요|죠|지|고|입니까|있|남|[?？]\s*$)|"       # 개수를 묻는 끝맺음 ("몇 개 빠져?"는 수량 규칙이라 거르지 않는다)
    r"알려\s?(?:줘|주세요|줄래|줄\s?수|주라|주실)|뽑아|골라|꺼내|추려|걸러|봐\s?(?:줘|주세요)|훑어|"                    # 조회 동사
    r"(?:로트|재고|소모품|부품|공구|설비|정비|항목|알림|품목|것|거|건|들)\s?중(?:에|에서|의)|"                         # 부분 집합 ("측정 중에"는 하는 동안이라 거르지 않는다)
    r"제일|가장|젤\s|보다\s|"                                                                                      # 최상급·비교
    r"모자란|모자라(?!면|다면)|부족한|부족(?!하면|하다면|해지면)|초과한|넘은|넘긴|넘어서|밑으로|"                      # 부족·초과 상태 ("모자라면"은 조건이라 거르지 않는다)
    r"(?:이하|미만|초과)인\s?(?:것|거|건|로트|재고|항목|소모품|공구|부품)|지난\s|지나서|지났|늦은|늦게|오래된|밀린|"
    r"괜찮(?:은가요|아\s?[?？]|나요|은지)|문제\s?없|이상\s?없|정상(?:이야|인가요|이에요|인지)\s?[?？]|맞는지\s?(?:봐|확인)|"   # 상태 확인
    r"어느\s?(?:로트|건|거|항목|쪽|품목|공구|설비|소모품|재고|정비)|어떤\s?(?:로트|건|거|항목|품목|공구|설비|소모품|상태)|"   # 특정 대상 고르기
    r"누구(?:야|예요|에요|인가요|지)\s?[?？]?\s*$|화면|숫자랑|수치랑|왜\s?(?:이렇게|이래|이런|저래|저렇게)|"
    r"올라온|올라와|나간\s?거|나간\s?적|뜬\s?거|걸린\s?거|걸려\s?있|떠\s?있|생긴\s?거|바뀐\s?거|된\s?거|난\s?거|한\s?거|안\s?된\s?거|안\s?한\s?거|"   # 사건·상태로 대상을 고르는 말
    r"웠(?:어|나|니|는지|죠)|뤘(?:어|나|니)")                                                                        # RULE_PAST에 없는 과거형 ("채웠어?")
RULE_WIDE_EXIST_RE = re.compile(r"있(?:어|나|니|는지|을까|는\s?게|는\s?거)\s?(?:요)?\s?[?？]|있나요|있어요|있습니까|없어\s?[?？]|없나요")   # 존재 확인 = 조회
RULE_WIDE_FEATURE_RE = re.compile(r"(?:알림|기능|기준|규칙|규정|원칙|절차|방법|권한|제한|조건|예외|옵션|설정|표시|문구|메시지|양식|형식|단계|순서|제외|면제)(?:이|가|도|은|는|란)?\s?(?:따로|별도|특별히|있)")   # "알림이 있나요?"는 기능·기준을 묻는 규칙 질문


def rule_question_wide(question: str, p: dict) -> bool:
    """신호가 운영 낱말(intents)뿐이고 조회 말투가 아닌 질문인가 (PURE_RULE_WIDE). 좁은 규칙(rule_question)이 받는 질문을 포함한다.
    번호·설비·날짜·알람이 있거나 신호가 아예 없으면 False(앞은 진짜 조회, 뒤는 이미 순수 길)."""
    if not p.get("intents"):
        return False
    if p.get("alarms") or p.get("equipment") or p.get("start") or p.get("end") or p.get("lot") or p.get("order"):
        return False
    q = question.strip()
    if len(re.sub(r"[\s?？!.~,]", "", q)) < RULE_MIN_LEN:
        return False
    if RULE_LIVE_RE.search(q):
        return False
    if RULE_MARK_RE.search(q):
        return True
    if RULE_WIDE_DATA_RE.search(q):
        return False
    if RULE_WIDE_EXIST_RE.search(q) and not RULE_WIDE_FEATURE_RE.search(q):
        return False
    return True


def fault_question(question: str, p: dict) -> bool:
    """신호가 운영 낱말(intents)뿐인 고장 대응 절차 질문인가 (PURE_FAULT). 번호·설비·날짜·로트·작업지시·알람이 있거나 신호가 아예 없으면 False(앞은 진짜 조회·알람 카드, 뒤는 이미 순수 길)."""
    if not p.get("intents"):
        return False
    if p.get("alarms") or p.get("equipment") or p.get("start") or p.get("end") or p.get("lot") or p.get("order"):
        return False
    q = question.strip()
    if len(re.sub(r"[\s?？!.~,]", "", q)) < RULE_MIN_LEN:
        return False
    if FAULT_DATA_HARD_RE.search(q) or FAULT_DATA_SOFT_RE.search(_last_sentence(q)):
        return False
    return bool(FAULT_STRONG_RE.search(q)) or bool(FAULT_WEAK_RE.search(q) and FAULT_SYMPTOM_RE.search(q))



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

# PURE_FAULTDOC=1 (2026-10-18, 기획 고장낱말_DOC03_통째붙이기): DOC-03(고장 대응 매뉴얼)을 현장 말로 물으면 정답 절이 낱말 검색 상위 8개 밖(대개 21위 밖)에 있어 Claude가 보지 못한다(점검표 73/90).
# 질문에 고장 낱말(알람·경고·떴어·멈췄어·정지·고장·에러·과열·누설 …)이 있으면 DOC-03 조각을 통째로(문서 순서, 상한 FAULTDOC_MAX_CHARS) 더한다 — PURE_SAFETY가 DOC-05를 통째로 붙이는 것과 같은 방식.
# 발동은 낱말로만 한다(검색 순위로 발동하면 상관없는 질문에도 번진다 — PURE_SAFETY 실험). 다른 문서 질문에는 거의 안 번진다(점검표 1~4%).
FAULTDOC = "DOC-03"              # 고장 대응 매뉴얼
FAULTDOC_SCORE = -2.0            # 통째로 더한 조각의 표시: 검색 점수가 아니다 (0.0은 PURE_EXPAND, -1.0은 PURE_SAFETY)
FAULTDOC_MAX_CHARS = 30000       # 통째로 더하는 글자 수 상한 (지금 DOC-03은 27,897자 — 문서가 커져도 프롬프트가 폭증하지 않게)
FAULTDOC_TERMS = re.compile(r"알람|경고|떴|뜨는|뜨고|떠서|멈췄|멈춰|멈추|정지|고장|에러|오류|안 켜|꺼졌|과열|누설|모자라|걸렸|안 읽|안 잡|안 풀|다시 돌려|리셋")


def is_fault_text(question: str) -> bool:
    """고장·알람·이상 낱말이 든 질문인가 — 낱말만 본다. 이 판정이 켜져야 DOC-03을 통째로 준다 (PURE_FAULTDOC)."""
    return bool(FAULTDOC_TERMS.search(question))


def add_fault_doc(hits: list[tuple[float, Chunk]]) -> list[tuple[float, Chunk]]:
    """검색 결과 뒤에 DOC-03 조각 중 아직 없는 것을 문서 순서로 더한다 (점수 FAULTDOC_SCORE, 상한 FAULTDOC_MAX_CHARS). 원래 조각의 순서·점수는 그대로."""
    have = {c.chunk_id for _, c in hits}
    out = list(hits)
    chars = 0
    for c in load_corpus():
        if c.doc_id != FAULTDOC or c.chunk_id in have:
            continue
        if chars + len(c.text) > FAULTDOC_MAX_CHARS:
            break
        out.append((FAULTDOC_SCORE, c))
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
    """Claude에 줄 조각: 낱말 검색 상위 k개 (+ PURE_EXPAND=1이면 잠금 낱말 질문의 부모 조각 보장 + 아래 절) (+ PURE_PERIOD=1이면 기간·정비 낱말 질문에 DOC-04 해당 기간 절) (+ PURE_SAFETY=1이면 안전 질문에 DOC-05 통째로).
    둘 다 끄면 retrieve()와 똑같다."""
    hits = retrieve(question, k)
    if s.pure_expand:
        hits, first = guarantee(question, hits)
        hits = expand(hits, first=first)
        if s.pure_period:
            hits = guarantee_period(question, hits)
    if s.pure_safety and is_safety(question):
        hits = add_safety_doc(hits)
    if getattr(s, "pure_faultdoc", False) and is_fault_text(question):   # PURE_FAULTDOC=1: 고장 낱말이 있으면 DOC-03을 통째로
        hits = add_fault_doc(hits)
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


def ask(question: str, chunks: list[Chunk], prev: dict | None, s: Settings, ops_note: bool = False, retry_note: bool = False, fixed_note: str | None = None) -> dict:
    """외부 Claude 1번 호출. 돌려주는 값: {"answer", "insufficient", "cited_raw"(받은 그대로), "raw"(받은 JSON), "ms", "sent_chars"}.
    연결·시간 초과·형식 오류·빈 답은 ExternalLlmFailure로 올린다 — 자동으로 로컬·다른 길로 돌아가지 않는다(앱 입구가 EXTERNAL_LLM_UNAVAILABLE로 끝냄).
    PURE_STYLE=1이면 새 지시문·스키마·max_tokens로 부르고 "answer"는 `opening 1) … 2) … closing`을 이은 글이며, "style": True와 "opening"·"points"·"closing" 부품이 더해진다
    (insufficient면 points·closing은 비우고 opening 한 문장만 — opening이 비어 있으면 짧은 고정 문구). 끔이면 위 계약 그대로(키도 늘지 않는다).
    PURE_STYLE=1 + PURE_LAYOUT=1이면 새 지시문·스키마(sections)·max_tokens(MAX_TOKENS_LAYOUT)로 부르고 "answer"는 `join_layout` 글이며, "style": True·"layout": True와 "sections" 부품이 더해진다
    (opening·points·closing 키는 만들지 않는다. insufficient면 sections는 모든 묶음 text를 이은 한 묶음 — 글이 없으면 짧은 고정 문구)."""
    style = bool(s.pure_style)
    layout = style and bool(s.pure_layout)
    messages = build_messages(question, chunks, prev, system_for(s) + ("\n\n" + RULE_OPS_NOTE if ops_note else "")   # ops_note: PURE_RULE로 문서 길에 온 질문에만
                              + ("\n\n" + PARTIAL_NOTE if s.pure_retry else "") + ("\n\n" + RETRY_NOTE if retry_note else "") + ("\n\n" + fixed_note if fixed_note else ""))   # PURE_RETRY=1: 첫 호출에 한 줄, 넓게 다시 본 호출에 한 줄 더
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
