"""362 말풍선 질문의 경로 수정 (2026-10-21, 기획 `시연_362질문_경로수정_기획_20261021`).

시연 362 말풍선 12턴을 규칙 길에 돌려 보니 4턴이 문서 답 대신 알람 카드·작업지시 목록으로 갔다: "공구…사용률"(조회 낱말 없음), 알람과 함께 묻는 손실 종류·보고서 포함·작업지시서 필요 질문
(알람 번호·"이 알람"·날짜 때문에 규칙 질문 분류가 진짜 조회로 거절). Claude·공용 DB는 부르지 않는다 (길 판정과 가짜 백엔드).
"""
from __future__ import annotations

import pytest

from backend.config import settings
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    for k, v in {"PURE_KEEP_SIGNALS": "1", "PURE_EXPAND": "1", "PURE_SAFETY": "1", "PURE_PERIOD": "1", "PURE_RULE": "1", "PURE_FAULT": "1",
                 "PURE_FAULTDOC": "1", "PURE_RULE_WIDE": "1"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LLM_ENABLED", "1")


def scope(q):
    with EXT.external_request("claude"):
        s = settings()
        p = A.parse(q)
        return A.pure_scope_v19(p, s, q)


POLICY = ["이 362는 고장으로 잃은 거야, 느려서 잃은 거야?", "오늘 VF2-01 362는 9/30 일일 보고서에 있어?", "이 알람으로 수리 작업지시서를 써야 해?",
          "오늘 362 사건은 교대 보고서에 들어가?"]
NOT_POLICY = ["VF2-01 362는 지금까지 몇 번 떴어?", "오늘 일일 보고서에 들어간 알람 몇 개야?", "LOT-2609-041-1 작업지시서 써야 해?", "362 뜨면 뭐부터 해?",
              "오늘 VF2-01 고장 손실 몇 개야?"]


@pytest.mark.parametrize("q", POLICY)
def test_alarm_policy_question_goes_to_doc_route(q):
    assert scope(q) == PURE.POLICY_WHY


@pytest.mark.parametrize("q", NOT_POLICY)
def test_data_questions_are_not_policy_route(q):
    assert scope(q) != PURE.POLICY_WHY


def test_tool_usage_wording_is_tool_life_lookup():
    assert "tool_life" in A.parse("VF2-01에서 362가 난 공구가 뭐야? 사용률은?")["intents"]
    assert "tool_life" not in A.parse("공구 사용률은 어떻게 계산해?")["intents"]   # 뜻·계산 질문은 지금처럼 문서 길


def test_tool_usage_question_answers_tool_list_not_alarm_card(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "0")
    a = A.answer("VF2-01에서 362가 난 공구가 뭐야? 사용률은?", "OPR", {"screen": "SCR-04"})
    assert a["status"] == "답변" and "공구 수명" in a["conclusion"] and "알람 설명" not in a["conclusion"]
