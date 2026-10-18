"""DOC-06(검사 기준서) 놓침 해결 시험 (2026-10-18). 기획: 261003_창민/DOC06_놓침_해결_기획_20261018.md

측정에서 정답 조각이 Claude에게 가지 않았던 별명·말투 변형 질문(점검표 62/75)과, 그것을 푸는 문서 쪽 처방(용어집 별칭 + DOC-06 제목에 현장 말 병기, 개정 Rev.4)을 지킨다.
적중률 숫자는 박지 않는다 — 옛 놓침 질문이 다시 놓치지 않는지, 절 구조·핵심 숫자·개정 표시가 맞는지만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.config import DOCS_DIR
from backend.eval import doc_recall as DR
from backend.rag import search as RS
from backend.rag.chunker import load_corpus
from backend.tests.test_doc_recall import cfg, key_of

DOC = "DOC-06"
CHUNKS = [c for c in load_corpus() if c.doc_id == DOC]
BY_KEY = {key_of(c): c for c in CHUNKS}
TITLE = {c.section: c.title for c in CHUNKS}

# 점검표 질문 중 처방 전에 정답 조각이 Claude에게 가지 않았던 것 (측정 2026-10-18). 키는 점검표와 같다.
FIXED = [
    ("첫 물건은 누가 재고 누가 확인해?", "3.1"), ("빡세게 하던 검사는 언제 평소로 돌아가?", "3.3"), ("부품 하나 재는 데 시간이 얼마나 걸려?", "3.4"),
    ("홀드 걸고 나서 해야 하는 일을 순서대로 알려줘", "4.2"), ("데이터가 모자랄 때는 화면에 뭐라고 떠?", "5.2"), ("세척하자마자 바로 재면 어떻게 돼?", "6.1:1"),
    ("봉 한 개에서 부품이 몇 개 나와?", "9.1:1"), ("부품이 150인데 왜 152로 잘라?", "9.1:1"),
]
# 처방으로도 못 푼 것 — 질문어가 너무 일반적이라 낱말 사전으로 못 잡는다 (성과 문서 한계). 나중에 풀리면 조용히 XPASS.
STILL_MISSED = [
    ("검사를 어떤 식으로 나눠서 해?", "3"), ("전부 다 재면 라인이 왜 막혀?", "3.4"), ("측정기가 합격이라는데 시스템은 불합격이면 어느 쪽을 믿어?", "3.6:2"),
    ("로트가 가질 수 있는 상태가 뭐뭐 있어?", "4.1"), ("기준에 못 미치면 그 항목은 어떻게 검사해?", "5.2"),
]


def test_the_former_misses_are_in_the_check_table():
    table = {it["q"]: it["sec"] for it in DR.load_items(DOC)}
    for q, sec in FIXED + STILL_MISSED:
        assert table.get(q) == sec, q


@pytest.mark.parametrize("q, sec", FIXED, ids=[f"§{s}" for _, s in FIXED])
def test_former_misses_now_reach_their_chunk(monkeypatch, q, sec):
    s = cfg(monkeypatch)
    it = next(i for i in DR.load_items(DOC) if i["q"] == q)
    assert DR.reached(q, DOC, DR.accepted(it), s), f"정답 {sec}가 Claude 조각에 없다: {q} (낱말 검색 순위 {DR.rank_of(q, DOC, DR.accepted(it))})"


@pytest.mark.xfail(strict=False, reason="질문어가 너무 일반적이라 낱말 사전으로 못 잡는다 (DOC06_놓침_해결_성과 한계)")
@pytest.mark.parametrize("q, sec", STILL_MISSED, ids=[f"§{s}" for _, s in STILL_MISSED])
def test_generic_questions_that_are_still_missed(monkeypatch, q, sec):
    s = cfg(monkeypatch)
    it = next(i for i in DR.load_items(DOC) if i["q"] == q)
    assert DR.reached(q, DOC, DR.accepted(it), s)


# ------------------------------------------------------------------ 문서 쪽 처방
HEAD_WORDS = {"3.1": "첫 물건", "3.2": "샘플링", "3.3": "빡세게", "3.4": "부품 하나 재는", "4.2": "홀드", "5.2": "데이터가 모자랄 때", "6.1": "세척 직후 바로 재면", "9.1": "봉 한 개에서"}
ORIGINAL = {"3.1": "초품 검사", "3.2": "보통 (발췌", "3.3": "검사 강화 (전수", "3.4": "검사 시간 [가상]", "4.2": "의심 로트와 보류 순서", "5.2": "Cpk 기준과 미달 시 조치",
            "6.1": "측정 전 온도 맞춤 시간 계산", "9.1": "봉재 단면, OP-10 절단 길이와 OP-20·30 가공 여유 계산"}


@pytest.mark.parametrize("sec, word", sorted(HEAD_WORDS.items()))
def test_headings_carry_the_field_words(sec, word):
    assert word in TITLE[sec], f"§{sec} 제목에 현장 말 \"{word}\" 병기가 없다: {TITLE[sec]}"


@pytest.mark.parametrize("sec, orig", sorted(ORIGINAL.items()))
def test_original_heading_words_stay_in_front_so_references_still_match(sec, orig):
    assert TITLE[sec].startswith(orig), (sec, TITLE[sec])


def test_chunk_structure_did_not_change():
    assert sorted(BY_KEY) == sorted(["1", "2", "3", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6:1", "3.6:2", "4.1", "4.2", "4.3", "5.1", "5.2", "5.3", "6", "6.1:1", "6.1:2",
                                      "7", "8.1", "8.2", "9", "9.1:1", "9.1:2"])


def test_numbers_that_the_answers_depend_on_are_still_in_their_chunks():
    t = {k: c.text for k, c in BY_KEY.items()}
    assert "2.5분/개" in t["3.4"] and "0.5분/개" in t["3.4"] and "5.0분/개" in t["3.4"]
    assert "1.67" in t["5.2"] and "1.33" in t["5.2"] and "계산 중" in t["5.2"]
    assert "50개" in t["5.1"]
    assert "5개마다 1개" in t["3.2"] and "36개 로트면 8개" in t["3.2"]
    assert "23개" in t["9.1:1"] and "152.0" in t["9"] and "152.0 mm" in t["9.1:1"]
    assert "20 ℃" in t["6"] and "90분" in t["6"] and "140분" in t["6"]
    assert "선입선출" in t["4.3"]


# ------------------------------------------------------------------ 용어집 별칭
ALIASES = {"첫 물건": "초품", "샘플링": "발췌 검사", "랜덤 검사": "발췌 검사", "빡세게 하는 검사": "검사 강화", "라인이 막혀": "병목", "막힘": "병목"}


@pytest.mark.parametrize("alt, std", sorted(ALIASES.items()))
def test_glossary_maps_the_field_word_to_the_standard_word(alt, std):
    assert RS.synonyms().get(alt) == std


def test_existing_glossary_aliases_are_untouched():
    syn = RS.synonyms()
    assert syn.get("홀드") == "로트 보류" and syn.get("첫물") == "초품" and syn.get("전량 검사") == "전수 검사" and syn.get("발취 검사") == "발췌 검사"


# ------------------------------------------------------------------ 개정 표시
def _lines(name: str) -> list[str]:
    return (Path(DOCS_DIR) / name).read_text(encoding="utf-8").splitlines()


def test_doc06_cover_and_revision_log_end_with_rev4_and_approval():
    cover = next(l for l in _lines("DOC-06_검사기준서.md")[:12] if l.startswith("| 개정 |"))
    assert "Rev.4 (2026-10-18)" in cover
    rows = [l for l in _lines("DOC-06_검사기준서.md") if re.match(r"\| Rev\.\d \|", l)]
    names = [r.split("|")[1].strip() for r in rows]
    assert names[:2] == ["Rev.0", "Rev.1"] and names[-1] == "Rev.4"      # 옛 줄은 그대로 두고 맨 끝에만 더한다
    assert "2026-10-18" in rows[-1] and rows[-1].rstrip().endswith("| MGR |")
    assert "Rev.2" in rows[-1] and "Rev.3" in rows[-1]                     # 팀 기록의 Rev.2·Rev.3이 이 표에 없던 틈을 적는다
    assert {c.revision for c in CHUNKS} <= {"Rev.4", "Rev.4 (2026-10-18)"}


def test_glossary_header_and_revision_log_end_with_rev5_and_approval():
    head = "\n".join(_lines("00_용어집.md")[:4])
    assert "Rev.5 (2026-10-18)" in head
    rows = [l for l in _lines("00_용어집.md") if re.match(r"\| Rev\.\d \|", l)]
    assert rows[-1].startswith("| Rev.5 | 2026-10-18 |") and rows[-1].rstrip().endswith("| MGR |")
