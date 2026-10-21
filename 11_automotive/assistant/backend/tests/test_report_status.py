"""보고서 작성·확정 여부 질문 (2026-10-21 시연 시험) 최소 시험 — 진짜 Claude·네트워크·DB를 부르지 않는다 (가짜 백엔드·LLM 끔).

문제: "어제 주간 교대 보고서 작성됐어?"를 문서 길이 받아 "받은 조각에서는 못 찾았다 + 만들어지는 흐름"을 말하고, "어제"를 실제 달력(10월 20일)으로 지어냈다.
지키는 것: 작성·확정 여부는 채팅이 아직 못 읽는 DB 사실이므로 규칙이 그렇게 알리고(Claude 호출 없음, 규칙이 읽은 날짜만 말함) 보고서 화면을 안내한다.
"언제 만들어져?"·"누가 확정해?" 같은 문서 질문은 그대로 문서 길로 간다.
"""
import pytest

from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")


def parsed(q):
    p = A.parse(q)
    return p, A.report_status_unread_v32(q, p)


@pytest.mark.parametrize("q", ["어제 주간 교대 보고서 작성됐어?", "9월 30일 교대보고서 작성됐어?", "오늘 일일 보고서 확정됐어?", "교대 보고서 올라왔어?", "어제 야간 교대 보고서 확정 됐나요"])
def test_status_questions_are_caught(q):
    assert parsed(q)[1], q


@pytest.mark.parametrize("q", ["교대 보고서는 언제 만들어져?", "교대 보고서 누가 확정해?", "교대 보고서 어떻게 확정해?", "일일 보고서 요약해 줘", "2075 알람이 교대 보고서에 들어가?", "작성 기준이 뭐야?"])
def test_document_questions_are_not_caught(q):
    assert not parsed(q)[1], q


def test_answer_is_a_rule_note_with_the_date_the_rule_read():
    a = A.answer("어제 주간 교대 보고서 작성됐어?", "OPR", {"new_chat": "1"})
    a.pop("_followup", None)
    assert a["status"] == "확인 필요" and a["mode"] == "규칙"
    assert "9/30 주간 교대 보고서" in a["conclusion"] and "SCR-15" in a["conclusion"] and "10월 20일" not in a["conclusion"]


def test_daily_report_points_to_scr16_and_no_date_is_not_invented():
    a = A.answer("일일 보고서 확정됐어?", "SUP", {"new_chat": "1"})
    a.pop("_followup", None)
    assert a["status"] == "확인 필요" and "SCR-16" in a["conclusion"] and "일일 보고서가 작성" in a["conclusion"]
