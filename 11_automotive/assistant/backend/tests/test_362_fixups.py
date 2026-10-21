"""362 시험 결과 보정 (2026-10-21, 기획 `362_시험결과_보정_기획_20261021`).

사용자가 PR #123 뒤 화면에서 시험한 결과: ① `이 362는 고장으로 잃은 거야, 느려서 잃은 거야?`에 Claude가 DOC-07 §7.4(손실 분류 표)를 받지 못해 "고장 손실로 잡혀요"라고 틀리게 답함
② `오늘 VF2-01 362는 9/30 일일 보고서에 있어?`가 알람 카드만 나옴 ③ `362가 난 공구가 뭐야? 사용률은?`에 알람 카드·점검 순서까지 붙음. Claude·공용 DB는 부르지 않는다 (조각 목록·규칙 답·가짜 백엔드).
"""
from __future__ import annotations

import pytest

from backend import chat_mapping as CM
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
                 "PURE_FAULTDOC": "1", "PURE_RULE_WIDE": "1", "ASK_ONLY": "1"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LLM_ENABLED", "0")


LOSS_KIND = ["이 362는 고장으로 잃은 거야, 느려서 잃은 거야?", "이 알람은 보고서에서 고장 손실이야, 속도 손실이야?", "공구 수명 알람은 고장 손실이야 속도 손실이야?"]


@pytest.mark.parametrize("q", LOSS_KIND)
def test_loss_kind_question_always_gets_doc07_classification_sections(q):
    with EXT.external_request("claude"):
        s = settings()
        ids = {(c.doc_id, c.section) for _, c in PURE.context(q, s.pure_topk, s)}
    assert {("DOC-07", "7.4"), ("DOC-07", "5.3")} <= ids   # 손실 분류 표와 계산식 — 362를 고장 손실로 추론하지 않게 근거를 보장


def test_loss_count_or_other_questions_are_not_loss_kind():
    for q in ("362 뜨면 뭐부터 해?", "오늘 고장 손실 몇 개야?", "공구 교체는 누가 해?"):
        assert not PURE.loss_kind_question(q), q


def test_daily_report_inclusion_is_answered_by_rule_from_production_day():
    a = A.answer("오늘 VF2-01 362는 9/30 일일 보고서에 있어?", "MGR", {"screen": "SCR-04"})
    assert a["status"] == "답변" and a["mode"].startswith("규칙 (일일 보고서")
    t = a["conclusion"]
    assert "9/30 08:00부터 다음 날 05:00" in t and "오늘(10/1) 08:00 이후" in t and "오늘 생산일 보고서" in t
    assert any(e["doc_id"] == "DOC-01" for e in a["evidence"])   # 출처: 생산일 정의(§3)·일일 06:00(§3.3)
    assert "알람 설명" not in CM.to_answer_text(a)


@pytest.mark.parametrize("q", ["9/30 일일 보고서 오늘의 문제 상위만 요약해줘", "일일 보고서는 언제 만들어져?", "손실 전체 줄에서 고장이랑 속도 구분돼?"])
def test_other_report_questions_are_not_taken_by_the_rule(q):
    assert not A.daily_report_inclusion_v29(q, A.parse(q))


@pytest.mark.parametrize("q", ["VF2-01에서 362가 난 공구가 뭐야?", "VF2-01에서 362가 난 공구가 뭐야? 사용률은?"])
def test_tool_question_screen_text_has_tool_list_and_no_alarm_card(q):
    with EXT.external_request("claude"):
        a = A.answer(q, "OPR", {"screen": "SCR-04"})
    text = CM.to_answer_text(a)   # 화면 글 기준 — conclusion만 보면 블록 제목("알람 설명")을 놓친다
    assert "알람 설명" not in text and "점검 순서" not in text
    assert "VF2-01 T" in text
