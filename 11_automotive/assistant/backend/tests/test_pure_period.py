"""기간 낱말 보장(PURE_PERIOD) 시험 (2026-10-18). 기획: 261003_창민/DOC04_놓침_해결_기획_20261018.md 부록 A

"한 달에 한 번 하는 정비 뭐야?"처럼 기간을 현장 말로 물으면 DOC-04의 기간 표(§2.3 "매월" …)가 낱말 검색 순위 74~88위로 밀려 Claude에게 가지 않고
"문서에 없다"는 거짓 답이 나온다. 질문에 기간 낱말과 정비 낱말이 함께 있으면 그 기간의 DOC-04 절 조각을 보장한다 (PURE_EXPAND=1 안에서, 별도 스위치 PURE_PERIOD).
이 시험은 적중률 숫자를 박지 않는다 — 판정·보장·끄면 동일·오발동 없음만 본다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.config import Settings, settings
from backend.eval import doc_recall as DR
from backend.llm import external as EXT
from backend.rag.chunker import load_corpus
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import cfg as _cfg

HERE = Path(__file__).resolve().parent
CORPUS = load_corpus()
BY_ID = {c.chunk_id: c for c in CORPUS}


def cfg(monkeypatch, period="1", **kw) -> Settings:
    monkeypatch.setenv("PURE_PERIOD", period)
    return _cfg(monkeypatch, **kw)


# 기간 낱말 판정 표: (질문, 기대하는 절). 처방 뒤에 쓴 탐침 16개 중 15개 + 기존 놓침 질문 + 현장에서 나올 법한 다른 말
CASES = [
    ("매달 하는 정비 목록 알려줘", ["2.3"]), ("반년마다 해야 하는 정비가 뭐야?", ["2.5"]), ("1년에 한 번 하는 정비는 뭐가 있어?", ["2.6"]),
    ("하루에 한 번 하는 점검이 뭐야?", ["2.1"]), ("주 1회 점검 항목 알려줘", ["2.2"]), ("일주일에 한 번 하는 정비는?", ["2.2"]),
    ("한 달에 한 번 하는 정비 뭐야?", ["2.3"]), ("월 1회 정비 목록 알려줘", ["2.3"]), ("월간 점검 항목은?", ["2.3"]),
    ("석 달에 한 번 하는 점검 있어?", ["2.4"]), ("분기마다 하는 정비 있어?", ["2.4"]),
    ("6개월에 한 번 하는 정비는?", ["2.5"]), ("반기 점검 항목 알려줘", ["2.5"]),
    ("매년 하는 정비 뭐야?", ["2.6"]), ("연간 정비 항목 알려줘", ["2.6"]), ("일 년에 한 번 하는 정비는?", ["2.6"]),
    ("수시로 하는 정비는 뭐야?", ["2.7"]), ("필요하면 하는 정비가 뭐가 있어?", ["2.7"]),
    ("한달에 한번 하는 정비 알려줘", ["2.3"]),
    ("매 달 점검 항목이 뭐야?", ["2.3"]),                  # 띄어쓰기 변형도 잡는다
    ("다달이 하는 점검이 뭐야?", ["2.3"]), ("월마다 하는 정비는?", ["2.3"]), ("월 단위로 하는 정비 목록", ["2.3"]), ("월별 점검 항목 알려줘", ["2.3"]),
    ("한 달 단위로 하는 정비 목록", ["2.3"]), ("연례 점검 항목이 있어?", ["2.6"]), ("연 단위 정비 항목은?", ["2.6"]),   # 탐침 B를 본 뒤 사전에 더한 말 (B의 독립 증거 아님)
    ("6개월마다 하는 점검 알려줘", ["2.5"]), ("2개월마다 점검할 게 있어?", []),                      # "개월마다"의 "월마다"를 매월로 읽지 않는다
    ("3개월마다 점검할 게 있어?", ["2.4"]), ("매월 하는 정비와 6개월마다 하는 점검 알려줘", ["2.3", "2.5"]),   # 기간이 둘이면 둘 다, 절 번호 순서
]
# 발동하면 안 되는 질문: 기간만 있거나 정비 낱말만 있거나 둘 다 없다
NEGATIVE = ["사내 체육대회 언제야?", "근처 병원 어디 있어?", "연차 며칠 남았는지 알려줘", "구내식당 저녁은 몇 시에 열어?", "파이썬으로 그래프 그리는 법 알려줘",
            "엑셀로 보고서 뽑는 법 알려줘", "Haas 본사 전화번호 알려줘", "검사 빡세게 할 때는 한 개 재는 데 몇 분 걸려?",
            "매일 몇 시에 퇴근해?", "지난달 OEE 알려줘", "2021년 이후 입사자 몇 명이야?", "월간 생산 보고서 보여줘", "13개월 전 알람 이력 알려줘",
            "정비 작업지시서는 어디서 만들어?", "예방 정비가 뭐야?", "점검표가 뭐야?"]


@pytest.mark.parametrize("q, secs", CASES, ids=[str(i) for i in range(len(CASES))])
def test_period_sections_are_detected_in_section_order(q, secs):
    assert PURE.period_sections(q) == secs, q


@pytest.mark.parametrize("q", NEGATIVE)
def test_period_is_not_detected_without_both_a_period_word_and_a_maintenance_word(q):
    assert PURE.period_sections(q) == [], q


def test_words_are_matched_with_optional_spaces_not_by_deleting_all_spaces():
    """"5분 기준으로 점검" 같은 말이 "분기"로 읽히면 안 된다."""
    for q in ("5분 기준으로 점검 항목 알려줘", "이 정비는 한 번 더 해야 해?", "하루 종일 점검해?"):
        assert PURE.period_sections(q) == [], q


def test_every_two_month_style_word_is_not_read_as_monthly():
    """"두 달마다"·"2년마다"는 매월·1년이 아니다."""
    for q in ("두 달마다 하는 정비 있어?", "2년마다 교체하는 부품 알려줘", "세 달마다 하는 점검 알려줘"):
        assert "2.3" not in PURE.period_sections(q) and "2.6" not in PURE.period_sections(q), q
    assert PURE.period_sections("세 달마다 하는 점검 알려줘") == ["2.4"]


def test_digit_periods_do_not_match_inside_longer_numbers():
    for q in ("2021년 정비 기록 알려줘", "11개월 점검 이력", "16개월 교체한 부품", "23개월 정비 항목"):
        assert PURE.period_sections(q) == [], q


def test_the_anchors_exist_in_the_corpus_and_titles_still_name_their_period():
    """절 번호를 코드에 박았으므로, 문서가 바뀌면 여기서 알려 준다."""
    want = {"2.1": "매일", "2.2": "매주", "2.3": "매월", "2.4": "3개월", "2.5": "6개월", "2.6": "1년", "2.7": "필요할 때"}
    assert set(PURE.PERIOD_TERMS) == set(want)
    for sec, title in want.items():
        c = BY_ID[f"{PURE.PERIOD_DOC}:{sec}"]
        assert c.title.startswith(title), (sec, c.title)


# ------------------------------------------------------------------ 보장 동작
def test_guarantee_puts_the_anchor_first_once_and_only_when_missing():
    q = "한 달에 한 번 하는 정비 뭐야?"
    hits = PURE.retrieve(q, 8)
    assert "DOC-04:2.3" not in [c.chunk_id for _, c in hits]                         # 결함: 검색 74~88위
    out = PURE.guarantee_period(q, hits)
    assert [c.chunk_id for _, c in out][0] == "DOC-04:2.3" and out[0][0] == 0.0 and out[1:] == hits


def test_guarantee_leaves_the_list_alone_when_the_anchor_is_already_there_or_no_period():
    q = "매월 점검 항목은?"                                                         # 문서 낱말 그대로면 3위로 이미 상위에 있다 (같은 뜻의 "매월 하는 정비 알려줘"는 8위 밖)
    hits = PURE.retrieve(q, 8)
    assert "DOC-04:2.3" in [c.chunk_id for _, c in hits]
    assert PURE.guarantee_period(q, hits) == hits
    h2 = PURE.retrieve("톱 정비 전에 어디를 차단해?", 8)
    assert PURE.guarantee_period("톱 정비 전에 어디를 차단해?", h2) == h2


def test_two_periods_add_two_anchors_in_section_order_each_once():
    q = "매월 하는 정비와 6개월마다 하는 점검 알려줘"
    hits = PURE.retrieve(q, 8)
    out = PURE.guarantee_period(q, hits)
    got = [c.chunk_id for _, c in out]
    assert len(got) == len(set(got))
    added = [i for i in ("DOC-04:2.3", "DOC-04:2.5") if i not in [c.chunk_id for _, c in hits]]
    assert got[:len(added)] == added


# ------------------------------------------------------------------ 스위치와 context
def test_default_is_off_in_code_flags_and_conftest(monkeypatch):
    assert Settings.__dataclass_fields__["pure_period"].default is False
    monkeypatch.delenv("PURE_PERIOD", raising=False)
    assert settings().pure_period is False
    for v in ("", "0", "no", "xx"):
        monkeypatch.setenv("PURE_PERIOD", v)
        assert settings().pure_period is False
    monkeypatch.setenv("PURE_PERIOD", "1")
    assert settings().pure_period is True and settings().flags()["pure_period"] is True


def test_conftest_pins_it_off_so_a_developer_env_cannot_change_other_tests():
    assert os.environ["PURE_PERIOD"] == "0"


def test_example_file_turns_it_on_with_a_comment_line_above_and_no_inline_comment():
    lines = (HERE / ".." / ".." / ".env.example").read_text(encoding="utf-8").splitlines()
    i = lines.index("PURE_PERIOD=1")
    assert lines[i - 1].startswith("#") and "기간" in lines[i - 1]


def test_context_adds_the_anchor_when_on(monkeypatch):
    s = cfg(monkeypatch)
    q = "한 달에 한 번 하는 정비 뭐야?"
    assert "DOC-04:2.3" in [c.chunk_id for _, c in PURE.context(q, s.pure_topk, s)]


def test_off_is_identical_to_the_legacy_context_for_dev_table_and_probe_questions(monkeypatch):
    """PURE_PERIOD=0이면 이 수정 이전 PURE.context(검색 → 잠금 보장 → 확장)와 한 글자도 같다."""
    s = cfg(monkeypatch, period="0")
    qs = [q for q, _ in CASES] + NEGATIVE + [it["q"] for it in DR.load_items("DOC-04")] + [it["q"] for it in DR.load_items("DOC-05")]
    for q in qs:
        hits = PURE.retrieve(q, s.pure_topk)
        hits, first = PURE.guarantee(q, hits)
        legacy = PURE.expand(hits, first=first)
        if s.pure_safety and PURE.is_safety(q):
            legacy = PURE.add_safety_doc(legacy)
        assert PURE.context(q, s.pure_topk, s) == legacy, q


def test_on_needs_expand_on_too(monkeypatch):
    s = cfg(monkeypatch, expand="0")
    q = "한 달에 한 번 하는 정비 뭐야?"
    assert PURE.context(q, s.pure_topk, s) == PURE.retrieve(q, s.pure_topk)


def test_on_never_removes_or_reorders_anything_other_questions_got(monkeypatch):
    """켜도 기간×정비 낱말이 없는 질문은 끈 것과 똑같다 (개발용·점검표·안전 점검표·상관없는 질문 전부)."""
    qs = NEGATIVE + [it["q"] for it in DR.load_items("DOC-05")]
    s_on = cfg(monkeypatch, period="1")
    on = {q: PURE.context(q, s_on.pure_topk, s_on) for q in qs if not PURE.period_sections(q)}
    s_off = cfg(monkeypatch, period="0")
    for q, got in on.items():
        assert got == PURE.context(q, s_off.pure_topk, s_off), q


def test_added_size_is_bounded_to_one_section_per_period(monkeypatch):
    s_on = cfg(monkeypatch, period="1")
    s_off = cfg(monkeypatch, period="0")
    longest = max(len(BY_ID[f"DOC-04:{sec}"].text) for sec in PURE.PERIOD_TERMS)
    for q, secs in CASES:
        if not secs:
            continue
        more = sum(len(c.text) for _, c in PURE.context(q, s_on.pure_topk, s_on)) - sum(len(c.text) for _, c in PURE.context(q, s_off.pure_topk, s_off))
        assert 0 <= more <= longest * len(secs), (q, more)


# ------------------------------------------------------------------ 켜면 기간 질문이 정답 절에 닿는다
REACH = [(q, secs) for q, secs in CASES if secs]


@pytest.mark.parametrize("q, secs", REACH, ids=[str(i) for i in range(len(REACH))])
def test_with_it_on_every_period_question_reaches_its_section(monkeypatch, q, secs):
    s = cfg(monkeypatch)
    for sec in secs:
        assert DR.reached(q, "DOC-04", {sec}, s), (q, sec, DR.rank_of(q, "DOC-04", {sec}))


def test_the_reach_tool_reports_the_switch(monkeypatch, capsys):
    s = cfg(monkeypatch)
    m = DR.measure("DOC-04", s)
    DR.report(m, s, "시험")
    assert "PURE_PERIOD=True" in capsys.readouterr().out


def test_recommended_env_for_the_tools_includes_the_switch(monkeypatch):
    monkeypatch.delenv("PURE_PERIOD", raising=False)
    DR.apply_recommended_env()
    assert os.environ["PURE_PERIOD"] == "1"
    monkeypatch.delenv("PURE_PERIOD", raising=False)
