"""짧은 후속 질문의 이어짐 판단 CONTINUE_LLM (2026-10-21) 최소 시험 — 진짜 Claude·네트워크·DB를 부르지 않는다 (LLM 호출은 가짜).

사용자 지시: 시험은 최소화하고 진짜 Claude 확인은 사용자가 직접 한다. 그래서 여기서는 ① 부를 조건 ② 완성된 질문의 낱말·숫자 대조 ③ 판단 결과 처리
④ 이어 푼 답과 안내 줄을 확인하고, 스위치가 꺼져 있으면 아무것도 부르지 않는 것을 단정한다.
"""
import pytest

from backend.chat_mapping import to_answer_text
from backend.config import settings
from backend.llm import client as C
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import continuation as CONT
from backend.tests.test_alarm_causes import APP_ON
from backend.tests.test_ask_only_stage1 import real_like  # noqa: F401  (fixture: 실제 DB 모양 재고·작업기록)

PREV = {"question": "M6 탭 재고는 얼마나 부족해?", "status": "답변", "conclusion": "M6 탭 6개, 안전 재고 8개보다 2개 부족해요."}


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")
    monkeypatch.setenv("CONTINUE_LLM", "1")


def _s():
    return settings()


def _cand(q, prev=PREV, switch="1", monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv("CONTINUE_LLM", switch)
    with EXT.external_request("claude"):
        return CONT.candidate(q, A.parse(q), prev, settings())


def fake_llm(monkeypatch, reply):
    """연결 부품을 가짜로 — 이어짐 판단 작업만 reply(dict 또는 예외)를 돌려주고 나머지 작업(다듬기 …)은 없는 척한다. 부른 작업 이름을 모은다."""
    calls = []

    def chat_json(messages, schema, name, max_tokens=400, s=None, grammar=None):
        calls.append((name, messages))
        if name != CONT.JOB:
            raise C.LlmUnavailable("시험: 이 작업은 가짜가 없다")
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(C, "chat_json", chat_json)
    return calls


# ---------------------------------------------------------------- 부를 조건
def test_candidate_only_when_every_condition_holds(monkeypatch):
    assert _cand("공기 필터는?", monkeypatch=monkeypatch) is True
    assert _cand("공기 필터는?", switch="0", monkeypatch=monkeypatch) is False                       # 스위치 꺼짐 = 지금 동작
    assert _cand("공기 필터는?", prev=None) is False                                                   # 앞 답 없음
    assert _cand("공기 필터는?", prev={**PREV, "status": "확인 필요"}) is False                        # 앞 답이 정상 답이 아님
    assert _cand("공기 필터는 얼마마다 교체하고 누가 그 기록을 남기고 재고는 어디서 빠지는지 알려줘") is False   # 짧은 글이 아님
    assert _cand("2075는?") is False and _cand("VF2-02는?") is False                                  # 알람·설비 신호는 기존 길
    assert _cand("잠금은 어떻게 해?") is False                                                         # 안전 낱말은 기존 안전 길


# ---------------------------------------------------------------- 완성된 질문 대조
@pytest.mark.parametrize("rewritten,ok", [
    ("공기 필터 재고는 얼마나 부족해?", True),
    ("공기 필터 재고는 얼마나 부족해? VF2-01", False),           # 몰래 더한 설비
    ("공기 필터 재고는 얼마나 3개 부족해?", False),               # 몰래 더한 숫자
    ("공기 필터 교체 주기는 얼마나 부족해?", False),              # 몰래 더한 낱말(교체·주기)
    ("", False),
])
def test_rewritten_question_must_use_only_words_from_the_two_texts(rewritten, ok):
    assert CONT.grounded(rewritten, PREV["question"], "공기 필터는?") is ok


# ---------------------------------------------------------------- 판단 결과
def test_judge_sends_two_lines_and_accepts_only_grounded_continuation(monkeypatch):
    calls = fake_llm(monkeypatch, {"continues": True, "question": "공기 필터 재고는 얼마나 부족해?"})
    with EXT.external_request("claude"):
        assert CONT.judge("공기 필터는?", PREV["question"], _s()) == "공기 필터 재고는 얼마나 부족해?"
    (name, messages), = calls
    user = [m["content"] for m in messages if m["role"] == "user"]
    assert name == CONT.JOB and user == ["[앞 질문]\nM6 탭 재고는 얼마나 부족해?\n\n[새 글]\n공기 필터는?"]   # 보내는 것은 두 줄뿐


@pytest.mark.parametrize("reply", [{"continues": False, "question": ""}, {"continues": True, "question": "공기 필터 교체 주기는 언제야?"},
                                   {"continues": True, "question": "공기 필터는?"}, {"continues": "yes", "question": "공기 필터 재고는?"},
                                   C.LlmUnavailable("시간 초과"), C.LlmBadOutput("형식 오류")])
def test_judge_gives_up_quietly_on_no_or_unsafe_or_failed(monkeypatch, reply):
    fake_llm(monkeypatch, reply)
    with EXT.external_request("claude"):
        assert CONT.judge("공기 필터는?", PREV["question"], _s()) is None


# ---------------------------------------------------------------- 이어서 푼 답
def test_continuation_answers_the_completed_question_and_says_so(real_like, monkeypatch):  # noqa: F811
    calls = fake_llm(monkeypatch, {"continues": True, "question": "공기 필터 재고는 얼마나 부족해?"})
    with EXT.external_request("claude"):
        a = A.answer("공기 필터는?", "MNT", {}, prev=PREV)
    assert a["question"] == "공기 필터는?" and a["status"] == "답변"
    shown = to_answer_text(a)                                                                           # 화면에 보이는 글(블록을 푼 것)
    assert "공기 필터 2개, 안전 재고 2개 — 같아서 부족분은 0이에요" in shown
    note = "앞서 물으신 'M6 탭 재고는 얼마나 부족해?'에 이어 '공기 필터 재고는 얼마나 부족해?'로 이해했어요."
    assert shown.count(note) == 1 and a["conclusion"].endswith(note)
    assert [n for n, _ in calls].count(CONT.JOB) == 1
    assert a["_followup"]["question"] == "공기 필터 재고는 얼마나 부족해?"                                   # 다음 이어 묻기는 완성된 질문을 기준으로


def test_switch_off_never_calls_the_judge(real_like, monkeypatch):  # noqa: F811
    monkeypatch.setenv("CONTINUE_LLM", "0")
    calls = fake_llm(monkeypatch, {"continues": True, "question": "공기 필터 재고는 얼마나 부족해?"})
    with EXT.external_request("claude"):
        assert not CONT.candidate("공기 필터는?", A.parse("공기 필터는?"), PREV, settings())
        try:
            A.answer("공기 필터는?", "MNT", {}, prev=PREV)
        except Exception:   # noqa: BLE001 — 꺼져 있으면 지금처럼 문서 길로 간다(가짜 LLM이 그 작업을 못 해 실패해도 상관없다). 여기서는 판단이 안 불렸다는 것만 본다
            pass
    assert CONT.JOB not in [n for n, _ in calls]
