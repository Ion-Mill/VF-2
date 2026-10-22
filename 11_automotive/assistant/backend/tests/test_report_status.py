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


def ask(q, role="OPR"):
    a = A.answer(q, role, {"new_chat": "1"})
    a.pop("_followup", None)
    return a


def test_confirmed_shift_report_is_answered_from_the_production_tool():
    """교대 보고서는 production 도구의 확정 여부로 프로그램이 답한다 (가짜 백엔드는 날짜와 상관없이 같은 두 교대를 준다 — 주간 확정·야간 미확정)."""
    a = ask("어제 주간 교대 보고서 작성됐어?")
    assert a["status"] == "답변" and a["mode"].startswith("규칙") and "주간 교대 보고서는 확정됐어요" in a["conclusion"]
    assert "10월 20일" not in a["conclusion"] and a["is_synthetic"] and a["current_data"][0]["tool"] == "생산 실적 조회"
    assert "구분해 읽지 못해요" not in a["conclusion"]     # 확정이면 덧붙일 말이 없다


def test_unconfirmed_shift_report_says_so_and_does_not_claim_it_is_missing():
    a = ask("9월 30일 야간 교대보고서 작성됐어?")
    assert a["status"] == "답변" and "야간 교대 보고서는 아직 확정되지 않았어요" in a["conclusion"]
    assert "구분해 읽지 못해요" in a["conclusion"] and "SCR-15" in a["conclusion"]


def test_both_shifts_of_a_day_are_listed():
    c = ask("9월 30일 교대보고서 작성됐어?")["conclusion"]
    assert "주간 교대 보고서는 확정됐어요" in c and "야간 교대 보고서는 아직 확정되지 않았어요" in c


def test_no_date_is_asked_back_and_today_is_not_ended_yet():
    a = ask("교대 보고서 작성됐어?")
    assert a["status"] == "안내" and "어느 날짜" in a["conclusion"]
    b = ask("오늘 주간 교대 보고서 확정됐어?")
    assert b["status"] == "답변" and "아직 없어요" in b["conclusion"] and "17시" in b["conclusion"]


def test_daily_report_still_points_to_scr16_because_no_tool_reads_it():
    a = ask("일일 보고서 확정됐어?", "SUP")
    assert a["status"] == "확인 필요" and "SCR-16" in a["conclusion"] and "일일 보고서가 작성" in a["conclusion"]


# ---- 확정 안 된 교대 보고서 목록 (2026-10-21 "작성안된 교대 보고서있어?")
@pytest.mark.parametrize("q", ["작성안된 교대 보고서있어?", "확정 안 된 교대 보고서 있어?", "아직 확정 안 된 교대 보고서 알려줘", "미확정 교대 보고서 목록", "남은 교대 보고서 몇 개야?"])
def test_pending_list_questions_are_caught(q):
    p = A.parse(q)
    assert A.pending_reports_v34(q, p), q


@pytest.mark.parametrize("q", ["교대 보고서 언제 확정해?", "교대 보고서 누가 확정해?", "어제 주간 교대 보고서 작성됐어?", "일일 보고서 확정 안 된 거 있어?", "교대 보고서 요약해줘"])
def test_other_report_questions_are_not_the_pending_list(q):
    assert not A.pending_reports_v34(q, A.parse(q)), q


def test_pending_list_names_the_unconfirmed_shifts_from_the_production_tool():
    a = ask("작성안된 교대 보고서있어?")
    assert a["status"] == "답변" and a["mode"].startswith("규칙") and a["is_synthetic"]
    assert "아직 확정되지 않은 것이 1개" in a["conclusion"] and "9/29 야간" in a["conclusion"] and "SCR-15" in a["conclusion"]
    assert "받은 조각" not in a["conclusion"]
