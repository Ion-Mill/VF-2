"""알람 이어받기 ALARM_CHAIN (2026-10-21, 992 시연 시험) 최소 시험 — 진짜 Claude·네트워크·DB를 부르지 않는다 (가짜 백엔드·LLM 끔).

문제: 화면이 alarm_key를 안 보내면 "992 원인은" 다음의 "뭘해야해?"·"먼저할일은"·"나는 뭘해야해?"가 알람 번호 신호가 없어 순수 길로 가
엉뚱한 조각(993)을 받고 "문서에 없음"이 되었다. 지키는 것: ① 바로 앞 정상 답이 한 알람 이야기면 대상 없는 짧은 질문이 그 알람 카드로 풀린다
② 이어받은 번호는 기록에 남아 그다음 질문도 잇는다 ③ 자기 대상이 있는 질문·앞 답이 알람이 아닌 경우·스위치 꺼짐은 지금 동작 ④ "나는/내가 …"는 내 역할 단계만.
"""
import pytest

from backend.config import settings
from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("ASK_ONLY", "1")
    monkeypatch.setenv("ALARM_CHAIN", "1")


def ask(q, role="OPR", prev=None, ctx=None):
    ctx = ctx if ctx is not None else ({"new_chat": "1"} if prev is None else {})
    a = A.answer(q, role, ctx, prev=prev)
    rec = a.pop("_followup", None)
    return a, rec


def test_switch_defaults_off(monkeypatch):
    monkeypatch.delenv("ALARM_CHAIN", raising=False)
    assert settings().alarm_chain is False


def test_prev_alarm_comes_from_the_previous_question_or_the_carried_key():
    assert A.prev_alarm_v31({"status": "답변", "question": "992 원인은", "context": {}}) == "992"
    assert A.prev_alarm_v31({"status": "답변", "question": "원인은", "context": {"alarm_key": "2075"}}) == "2075"
    assert A.prev_alarm_v31({"status": "문서에 없음", "question": "992 원인은", "context": {}}) == ""     # 앞 답이 정상 답이 아니면 안 잇는다
    assert A.prev_alarm_v31({"status": "답변", "question": "992랑 2075 알람 차이", "context": {}}) == ""   # 번호가 둘이면 안 잇는다
    assert A.prev_alarm_v31(None) == ""


def test_short_followups_after_an_alarm_answer_stay_on_that_alarm_card():
    a1, rec = ask("992 원인은")
    assert a1["status"] == "답변" and "992" not in a1["conclusion"]   # 실제 답처럼 원인 줄만 있고 번호가 없다 — 화면의 이어받기(carry.ts)가 번호를 못 뽑던 경우
    for q in ("뭘해야해?", "먼저할일은"):
        a, rec2 = ask(q, prev=rec)
        assert a["status"] == "답변" and a["conclusion"].startswith("992 알람 기준으로 답해요."), (q, a["conclusion"][:80])
        assert any(e.get("doc_id") == "DOC-03" for e in a["evidence"]), q
        assert rec2["context"].get("alarm_key") == "992", q     # 다음 질문도 잇는다
        rec = rec2


def test_chain_continues_through_a_third_question():
    _, rec = ask("992 원인은")
    _, rec = ask("뭘해야해?", prev=rec)
    a, _ = ask("나는 뭘해야해?", prev=rec)
    assert a["status"] == "답변" and a["conclusion"].startswith("992 알람 기준으로 답해요.")


@pytest.mark.parametrize("q", ["잠금 표지 순서가 어떻게 돼?", "VF2-01 워밍업 먼저 해야 돼?", "아까 알람 원인은?"])
def test_questions_with_their_own_subject_are_not_chained(q):
    _, rec = ask("992 원인은")
    a, _ = ask(q, prev=rec)
    assert not a["conclusion"].startswith("992 알람 기준으로 답해요.")


def test_not_chained_when_the_previous_answer_was_not_about_an_alarm():
    _, rec = ask("잠금 표지 순서가 어떻게 돼?")
    a, _ = ask("뭘해야해?", prev=rec)
    assert "알람 기준으로 답해요" not in a["conclusion"]


def test_off_keeps_todays_behavior(monkeypatch):
    monkeypatch.setenv("ALARM_CHAIN", "0")
    _, rec = ask("992 원인은")
    a, _ = ask("뭘해야해?", prev=rec)
    assert "알람 기준으로 답해요" not in a["conclusion"]


@pytest.mark.parametrize("role,keep,drop", [("OPR", "(작업자)", "(보전)"), ("MNT", "(보전)", "(작업자)"), ("SUP", "(작업자)", "(보전)"), ("MGR", "(작업자)", "(보전)")])
def test_i_questions_show_only_my_roles_steps(role, keep, drop):
    _, rec = ask("992 원인은", role)
    a, _ = ask("나는 뭘해야해?", role, prev=rec)
    assert a["status"] == "답변" and a["steps"] and all(keep in x and drop not in x for x in a["steps"]), (role, a["steps"])
    assert "처리 책임은 보전 담당자" in a["conclusion"]
    if role in ("SUP", "MGR"):
        assert "따로 없어요" in a["conclusion"]     # 반장·관리자 단계는 문서에 없으니 지어내지 않고 밝힌다


def test_own_role_filter_needs_the_i_word_and_the_switch(monkeypatch):
    _, rec = ask("992 원인은", "OPR")
    a, _ = ask("뭘해야해?", "OPR", prev=rec)
    assert len(a["steps"]) == 8                      # "나는"이 없으면 점검 순서 전체
    monkeypatch.setenv("ALARM_CHAIN", "0")
    b, _ = ask("992 내가 해야 할 일은?", "OPR")
    assert "내 역할" not in b["conclusion"]           # 스위치 꺼짐 = 지금 동작
