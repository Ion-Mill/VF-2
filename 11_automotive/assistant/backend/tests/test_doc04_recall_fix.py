"""DOC-04(예방 정비 기준서) 놓침 해결 시험 (2026-10-18). 기획: 261003_창민/DOC04_놓침_해결_기획_20261018.md

측정에서 정답 절이 Claude에게 가지 않았던 질문 7개(점검표 59/66)와, 그것을 푸는 문서 쪽 처방(제목에 현장 말 병기, 개정 Rev.2)을 지킨다.
이 시험은 적중률 숫자를 박지 않는다 — 옛 놓침 질문이 다시 놓치지 않는지, 문서의 구조(절 번호·절 수)와 개정 표시가 맞는지만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.config import DOCS_DIR
from backend.eval import doc_recall as DR
from backend.rag.chunker import load_corpus
from backend.tests.test_doc_recall import cfg

DOC = "DOC-04"
DOC04 = [c for c in load_corpus() if c.doc_id == DOC]
TITLE = {c.section: c.title for c in DOC04}

# (질문, 정답 절 — 점검표와 같다). 측정(2026-10-18)에서 정답 절이 Claude 조각에 없었던 질문들.
FORMER_MISSES = [
    ("매달 하는 정비 목록 알려줘", "2.3"),
    ("반년마다 해야 하는 정비가 뭐야?", "2.5"),
    ("1년에 한 번 하는 정비는 뭐가 있어?", "2.6"),
    ("황삭 설비는 정비 항목이 따로 있어?", "3.2"),
    ("측정기가 정확한지 어떻게 확인해?", "3.4"),
    ("절삭유 풀 때 몇 %로 맞춰?", "4.2"),
    ("고장 난 뒤에 고치는 건 이 문서 말고 어디 봐야 해?", "1"),
]


def test_the_former_misses_are_the_ones_in_the_check_table():
    table = {it["q"]: it["sec"] for it in DR.load_items(DOC)}
    for q, sec in FORMER_MISSES:
        assert table.get(q) == sec, q


@pytest.mark.parametrize("q, sec", FORMER_MISSES, ids=[f"§{s}" for _, s in FORMER_MISSES])
def test_former_misses_now_reach_their_section(monkeypatch, q, sec):
    s = cfg(monkeypatch)
    assert DR.reached(q, DOC, {sec}, s), f"정답 절 §{sec}가 Claude 조각에 없다: {q} (낱말 검색 순위 {DR.rank_of(q, DOC, {sec})})"


# ------------------------------------------------------------------ 문서 쪽 처방
ALIASES = {"2.3": "매달", "2.4": "분기", "2.5": "반년", "2.6": "1년에 한 번", "3.2": "황삭", "3.4": "정확도", "4.2": "풀 때"}


@pytest.mark.parametrize("sec, word", sorted(ALIASES.items()))
def test_headings_carry_the_field_word(sec, word):
    assert word in TITLE[sec], f"§{sec} 제목에 현장 말 \"{word}\" 병기가 없다: {TITLE[sec]}"


def test_original_heading_words_are_kept_so_references_still_match():
    """병기만 했다 — 원래 제목 낱말은 그대로 앞에 있다 (다른 문서·시험이 "§2.3 매월"로 부른다)."""
    for sec, orig in {"2.3": "매월", "2.4": "3개월", "2.5": "6개월", "2.6": "1년", "3.2": "OP-20 머시닝센터 (MIL-01)",
                      "3.4": "OP-50 3차원 측정기 (CMM-01)", "4.2": "절삭유 (CS-COOL)"}.items():
        assert TITLE[sec].startswith(orig), (sec, TITLE[sec])


def test_section_structure_did_not_change():
    assert sorted(TITLE, key=lambda x: [int(p) for p in x.split(".")]) == [
        "1", "2", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "3", "3.1", "3.2", "3.3", "3.4", "4", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "5"]


def test_numbers_that_the_answers_depend_on_are_still_in_their_sections():
    text = {c.section: c.text for c in DOC04}
    assert "7.0%" in text["4.2"] and "6.5~8.5%" in text["4.2"] and "약 3%" in text["4.2"]
    assert "1.4" in text["4.2"] and "208 L" in text["4.2"]
    for item in ("공기 퍼지 솔레노이드 청소", "주축 드로바 힘 측정", "공기 필터 교체"):
        assert item in text["2.6"]


# ------------------------------------------------------------------ 개정 표시
def _doc_lines() -> list[str]:
    return (Path(DOCS_DIR) / "DOC-04_예방정비기준서.md").read_text(encoding="utf-8").splitlines()


def test_cover_revision_and_chunk_revision_agree_on_rev2():
    cover = next(l for l in _doc_lines()[:12] if l.startswith("| 개정 |"))
    assert "Rev.2 (2026-10-18)" in cover
    assert {c.revision for c in DOC04} <= {"Rev.2", "Rev.2 (2026-10-18)"}


def test_revision_log_ends_with_rev2_row_and_approval():
    rows = [l for l in _doc_lines() if re.match(r"\| Rev\.\d \|", l)]
    assert [r.split("|")[1].strip() for r in rows] == ["Rev.0", "Rev.1", "Rev.2"]
    last = rows[-1]
    assert "2026-10-18" in last and last.rstrip().endswith("| MGR |")
