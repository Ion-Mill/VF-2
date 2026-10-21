"""정비 이력 안내 + 답 분량 지시문 (2026-10-21, 기획 `정비이력_안내_답분량_기획_20261021`).

시연 2차 결과: `지난주 정비 이력 보여줘`가 "문서에 없음"(운영 기록 질문인데 규칙 낱말에 "이력"이 없어 문서 길로 감, 작업기록 도구는 날짜 범위 없이 최근 20건만 준다),
순수 길 답이 묻지 않은 계산식·예시까지 붙임. Claude는 부르지 않는다 (규칙 안내와 지시문 글만 본다).
"""
from __future__ import annotations

import pytest

from backend.services import answer as A
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LLM_ENABLED", "0")


@pytest.mark.parametrize("q", ["지난주 정비 이력 보여줘", "어제 수리 이력 알려줘", "9/29 작업 이력 확인해 줘", "오늘 정비 이력 있었어?"])
def test_dated_history_lookup_is_caught(q):
    assert A.history_unread_v25(q, A.parse(q)), q


@pytest.mark.parametrize("q", [
    "정비 이력은 어디에 남겨?",            # 날짜 없는 문서 질문
    "정비 이력은 얼마 동안 보관해?",
    "2075 지난 조치는 뭐였어?",            # 알람 번호 + 운영 의도(작업기록)
    "어제 야간 VF2-01 몇 번 멈췄어?",      # 운영 의도(정지)
    "지난주 알람 이력 보여줘",              # '정비·수리·작업 이력'이 아니다
])
def test_other_questions_not_caught(q):
    assert not A.history_unread_v25(q, A.parse(q)), q


def test_history_answer_is_rule_note_without_claude():
    a = A.answer("지난주 정비 이력 보여줘", "SUP", {"screen": "SCR-04"})
    assert a["status"] == "확인 필요" and a["mode"] == "규칙"
    assert "SCR-12" in a["conclusion"] and "SCR-23" in a["conclusion"] and "문서에 없음" not in a["conclusion"]


def test_ask_only_note_keeps_old_clauses_and_adds_scope_rules():
    n = PURE.ASK_ONLY_NOTE
    assert "묻는 것에만 답한다" in n and "3개 이내" in n and "안전 경고" in n and "[가상]" in n   # 이전 지시문(test_ask_only)의 핵심 조각
    assert "첫 문장이 질문에 직접 답하게" in n and "어긋나지 않게" in n
    assert "계산식·예시" in n and "묻지 않으면 쓰지 않는다" in n
