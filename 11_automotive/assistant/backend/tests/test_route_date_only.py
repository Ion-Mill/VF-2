"""날짜뿐인 질문의 길 정하기 + 속도 손실 안내 (2026-10-21, 기획 `날짜뿐_질문_길정하기_기획_20261021`).

시연 시험에서 "T05가 90%면 오늘 교체해야 해?"의 "오늘"이 날짜 신호로 잡혀 옛 문서 길(상위 3조각)로 갔고, 정답 조각(DOC-01 §7.2, 검색 6위)을 놓쳐
거짓 "문서에 없음"이 나왔다. 날짜뿐인 질문은 신호 없는 질문과 같은 순수 길로 간다. 또 "속도 손실" 개수는 채팅이 아직 못 읽는데 "문서에 없음"이라 해서
문서에 정의가 없는 것처럼 오해를 줬다. Claude는 부르지 않는다 (길 판정과 규칙 안내만).
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


def scope(question: str):
    with EXT.external_request("claude"):
        s = settings()
        p = A.parse(question)
        return A.pure_scope_v19(p, s, question)


DATE_ONLY = [
    "T05가 90%면 오늘 교체해야 해?",
    "오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘.",
    "오늘 교대 속도 손실은 몇 개야?",
]
WITH_INTENT = ["오늘 VF2-01 몇 번 멈췄어?", "어제 야간 VF2-01 몇 번 멈췄어?", "오늘 생산 몇 개야?", "2075 지난 조치는?"]


@pytest.mark.parametrize("q", DATE_ONLY)
def test_date_only_detected(q):
    p = A.parse(q)
    assert PURE.has_signals(p) and PURE.date_only(p, q)   # has_signals는 그대로(날짜도 신호) — 순수 길 분류만 날짜뿐을 거른다


@pytest.mark.parametrize("q", WITH_INTENT)
def test_with_intent_not_date_only(q):
    assert not PURE.date_only(A.parse(q), q)


@pytest.mark.parametrize("q", DATE_ONLY)
def test_date_only_goes_pure_route(q):
    assert scope(q)   # 옛 문서 길(None)이 아니라 순수 길 사유


@pytest.mark.parametrize("q", WITH_INTENT)
def test_with_intent_keeps_old_route(q):
    assert scope(q) is None   # 의도·알람·설비가 있는 질문은 기존 길(운영 조회·알람 카드) 그대로


def test_speed_loss_unread_note():
    for q in ("오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘.", "오늘 교대 속도 손실은 몇 개야?", "느려서 잃은 개수만 알려 줘"):
        assert A.speed_loss_unread_v24(q, A.parse(q)), q


def test_speed_loss_question_about_meaning_not_caught():
    for q in ("속도 손실이 뭐야?", "속도 손실은 어떻게 계산해?", "인계 사항에서 잠금·표지가 맨 위인 이유는 뭐야?"):
        assert not A.speed_loss_unread_v24(q, A.parse(q)), q


def test_speed_loss_with_ops_intent_not_caught():
    q = "어제 야간 VF2-01 몇 번 멈췄고 속도 손실은 몇 개야?"
    assert A.parse(q)["intents"] and not A.speed_loss_unread_v24(q, A.parse(q))


def test_speed_loss_answer_is_rule_note_without_claude(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "0")
    a = A.answer("오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘.", "MNT", {"screen": "SCR-04"})
    assert a["status"] == "확인 필요" and a["mode"] == "규칙"
    assert "SCR-15" in a["conclusion"] and "문서에 없음" not in a["conclusion"]


def test_date_plus_record_noun_keeps_old_route():
    q = "지난주 정비 이력 보여줘"   # 기록을 찾는 조회 꼴 — 기존 시험(test_pure_fault)이 지키는 옛 길
    assert not PURE.date_only(A.parse(q), q)
    assert scope(q) is None
