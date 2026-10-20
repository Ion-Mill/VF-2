"""질문대로 답하기 2단계 ASK_ONLY (2026-10-21) 최소 시험 — 진짜 Claude·네트워크·DB를 부르지 않는다 (가짜 백엔드·LLM 끔).

사용자 지시: ① 알람 기본 카드 제거(묻는 칸만) ② 모호한 질문 되묻기 ③ 문서 답 길이 줄이기를 진행하고, 시험은 최소화·진짜 Claude 확인은 사용자가 직접 한다.
지키는 것: 뜻만 → 설명 덩어리만(출처 DOC-02), 대처·점검만 → 점검 순서만(출처 DOC-03), 둘 다 → 카드 전체, 횟수 → 조회만(카드 없음),
번호뿐 → 되묻기, 품목 이름뿐 → 되묻기(용어 OEE는 아님), 스위치 꺼짐 → 지금 동작(카드 전체), 지시문 덩어리는 스위치 켬 + 묶음 목록일 때만.
"""
import pytest

from backend.chat_mapping import to_answer_text
from backend.config import settings
from backend.llm import client as C
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import pure_external as PURE
from backend.tests.test_alarm_causes import APP_ON
from backend.tests.test_ask_only_stage1 import real_like  # noqa: F401  (fixture: 실제 DB 모양 재고·작업기록)

CARD = ("■ 알람 설명", "■ 점검 순서", "■ 가능한 원인", "최근 7일")


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("ASK_ONLY", "1")


def ask(q):
    a = A.answer(q, "MNT", {"new_chat": "1"})
    a.pop("_followup", None)
    return a, to_answer_text(a)


def secs(t):
    return {c for c in CARD if c in t}


def test_meaning_only_keeps_the_description_and_its_source(real_like):  # noqa: F811
    a, t = ask("2075가 뭐야?")
    assert secs(t) == {"■ 알람 설명"} and "(작업자)" not in t and "주의:" in t
    assert {e["doc_id"] for e in a["evidence"]} == {"DOC-02"}


def test_what_to_do_only_keeps_the_steps_and_their_source(real_like):  # noqa: F811
    a, t = ask("992 뜨면 뭐부터 해?")
    assert secs(t) == {"■ 점검 순서"} and "■ 알람 설명" not in t
    assert {e["doc_id"] for e in a["evidence"]} == {"DOC-03"}


def test_asking_both_keeps_the_whole_card(real_like):  # noqa: F811
    _, t = ask("2075 알람 설명하고 점검 순서 알려줘")
    assert {"■ 알람 설명", "■ 점검 순서"} <= secs(t)


def test_count_question_answers_the_lookup_without_the_card(real_like):  # noqa: F811
    a, t = ask("2075 몇 번 났어?")
    assert not (secs(t) - {"최근 7일"}) and "VF2-01" in t and a["steps"] == []


@pytest.mark.parametrize("q", ["2075는?", "2075 알람", "2075가?"])
def test_number_only_alarm_question_is_asked_back_not_answered_with_the_card(real_like, q):  # noqa: F811
    a, t = ask(q)
    assert a["status"] == "안내" and "알람 2075" in t and "무엇이 궁금하세요?" in t and not secs(t)
    assert "'2075가 뭐야?'" in t and "'2075 지난 조치'" in t                   # 바로 복사해 쓸 수 있는 예시


def test_item_name_only_is_asked_back_but_a_term_or_a_full_question_is_not(real_like):  # noqa: F811
    for q in ("공기 필터는?", "탭은?", "주축 윤활유는?"):
        a, t = ask(q)
        assert a["status"] == "안내" and "무엇이 궁금하세요?" in t, q
    assert "공기 필터의 무엇이 궁금하세요?" in ask("공기 필터는?")[1]
    for q in ("OEE는?", "공기 필터 재고는 얼마나 부족해?", "공기 필터 재고는?"):
        assert "무엇이 궁금하세요?" not in ask(q)[1], q


def test_switch_off_keeps_todays_full_card(real_like, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ASK_ONLY", "0")
    _, t = ask("2075가 뭐야?")
    assert {"■ 알람 설명", "■ 점검 순서"} <= secs(t)
    assert "무엇이 궁금하세요?" not in ask("2075는?")[1] and "무엇이 궁금하세요?" not in ask("공기 필터는?")[1]


def test_answer_scope_note_is_added_to_the_prompt_only_when_the_switch_and_layout_are_on(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")
    seen = []
    real_build = PURE.build_messages
    monkeypatch.setattr(PURE, "build_messages", lambda q, ch, prev, system: seen.append(system) or real_build(q, ch, prev, system))

    def boom(*a, **k):
        raise C.LlmUnavailable("시험: 호출하지 않는다")
    monkeypatch.setattr(C, "chat_json", boom)

    def system(ask_only, layout):
        monkeypatch.setenv("ASK_ONLY", ask_only)
        monkeypatch.setenv("PURE_STYLE", "1")
        monkeypatch.setenv("PURE_LAYOUT", layout)
        seen.clear()
        with EXT.external_request("claude"):
            with pytest.raises(Exception):
                PURE.ask("공기 필터는 얼마마다 갈아?", [], None, settings())
        return seen[0]

    on = system("1", "1")
    assert PURE.ASK_ONLY_NOTE in on and "묻는 것에만 답한다" in on and "3개 이내" in on and "안전 경고" in on
    assert PURE.ASK_ONLY_NOTE not in system("0", "1")      # 스위치 꺼짐: 지시문 그대로
    assert PURE.ASK_ONLY_NOTE not in system("1", "0")      # 묶음 목록 형식이 아니면 더하지 않는다
