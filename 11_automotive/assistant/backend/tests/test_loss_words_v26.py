"""고장 손실 낱말 인식 + 화면 대조 안내 (2026-10-21, 기획 `손실낱말_화면대조_기획_20261021`).

시연 시험 #13: "고장으로 잃은 개수"가 정지 조회로 읽히지 않아 읽을 수 있는 숫자도 안 나왔고, "화면이랑 같은지"는 Claude가 못 하는 일을 약속했다.
Claude는 부르지 않는다 (낱말 판정과 규칙 안내, 가짜 백엔드).
"""
from __future__ import annotations

import pytest

from backend.services import answer as A
from backend.tests.test_doc_recall import APP_FLAGS


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LLM_ENABLED", "0")


LOSS_ASK = ["오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘.", "VF2-01 지금까지 고장 손실 몇 개야?", "오늘 고장 손실 몇 개야?",
            "어제 야간 고장 손실 개수 알려줘", "고장으로 잃은 수량이 얼마야?", "고장 때문에 잃은 개수는?", "오늘 교대 고장 손실은 얼마야?"]
LOSS_MEANING = ["고장 손실이 뭐야?", "고장 손실 계산식 알려줘", "고장 손실이랑 속도 손실 차이 한 줄로 설명해줘", "속도 손실이 뭐야?",
                "고장 대응 매뉴얼에서 손실 수량은 어떻게 계산해?", "고장이 나면 뭐부터 해?"]
SCREEN_CMP = ["방금 말한 두 개수가 화면이랑 같은지 숫자만 다시 말해 줘.", "화면 숫자랑 네가 말한 값이 맞는지 확인해줘",
              "교대 보고서 숫자하고 같은지 알려줘", "이 개수가 화면 값이랑 일치해?"]
NOT_SCREEN_CMP = ["이 화면 설명해 줘", "교대 보고서 인계 사항은 뭐야?", "VF2-01 OEE는 지금 몇 %야?", "화면에 뜨는 알람은 뭐야?", "숫자만 다시 말해 줘"]


@pytest.mark.parametrize("q", LOSS_ASK)
def test_loss_count_is_stops_intent(q):
    assert "stops" in A.parse(q)["intents"]


@pytest.mark.parametrize("q", LOSS_MEANING)
def test_loss_meaning_is_not_stops_intent(q):
    assert "stops" not in A.parse(q)["intents"]   # 뜻·계산 질문은 지금처럼 문서 길


def test_loss_and_speed_loss_question_reads_stops_then_says_speed_loss_unread():
    a = A.answer(LOSS_ASK[0], "MNT", {"screen": "SCR-15"})
    assert a["status"] == "답변" and "손실 정지" in a["conclusion"]   # 읽을 수 있는 쪽은 프로그램이 계산해 답한다
    assert "속도 손실" in a["conclusion"] and "SCR-15" in a["conclusion"] and "[4]" in a["conclusion"]   # 못 읽는 쪽과 볼 곳, 보고서 [4]와 다를 수 있다는 말


def test_loss_only_question_has_no_speed_loss_tail():
    a = A.answer("오늘 고장 손실 몇 개야?", "MNT", {"screen": "SCR-04"})
    assert a["status"] == "답변" and "속도 손실" not in a["conclusion"]


@pytest.mark.parametrize("q", SCREEN_CMP)
def test_screen_compare_is_rule_note(q):
    assert A.screen_compare_unread_v26(q, A.parse(q))
    a = A.answer(q, "MNT", {"screen": "SCR-15"})
    assert a["status"] == "확인 필요" and a["mode"] == "규칙" and "읽거나 맞춰 보지 못해요" in a["conclusion"]


@pytest.mark.parametrize("q", NOT_SCREEN_CMP)
def test_not_screen_compare_untouched(q):
    assert not A.screen_compare_unread_v26(q, A.parse(q))
