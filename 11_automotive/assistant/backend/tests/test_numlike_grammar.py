"""10차 보강 (2026-10-14, 사용자 결정 "숫자 모양 전부 · 스위치 없이 바로 고침"): 쓰는 순간 문법이 숫자 모양 글자를 막는지.

복사본 시험 "OEE 예시" 질문에서 새로 쓴 답 "PQ는 ①, GQ는 ③"이 문법·코드 검사·따로 판정을 모두 지났다. 문법 글에는 글자가 아니라
역슬래시-u 꼴의 범위가 들어간다 — 이 파일은 그 범위를 읽어 글자가 범위 안에 있는지 본다.
"""
import re

import pytest

from backend.services import followup_v2 as FU2

BS = chr(92)                                    # 역슬래시 (이 파일에 역슬래시를 직접 쓰지 않으려고)
RANGE = re.compile(re.escape(BS) + "u([0-9A-F]{4})(?:-" + re.escape(BS) + "u([0-9A-F]{4}))?")


def _blocked(grammar: str) -> list[tuple[int, int]]:
    cls = grammar.split("content ::= ( [^", 1)[1].split("]", 1)[0]
    return [(int(a, 16), int(b or a, 16)) for a, b in RANGE.findall(cls)]


@pytest.mark.parametrize("ch", ["①", "⑳", "⑴", "⒈", "⓪", "❶", "㈠", "㉠", "ⓐ", "Ⅰ", "ⅷ", "１", "²", "₂", "¼", "٣"])
def test_grammar_blocks_numlike_char(ch):
    assert any(a <= ord(ch) <= b for a, b in _blocked(FU2.answer_grammar_v11(3)))


@pytest.mark.parametrize("ch", ["가", "한", "·", "—", "℃", "°", "§", "%"])
def test_grammar_keeps_other_chars(ch):
    assert not any(a <= ord(ch) <= b for a, b in _blocked(FU2.answer_grammar_v11(3)))


def test_grammar_keeps_ascii_rules_and_placeholders():
    g = FU2.answer_grammar_v11(3)
    assert "[^0-9A-Za-z{}" in g and '"{{" ( "1" | "2" | "3" ) "}}"' in g
    assert g.count("[^") == 1
