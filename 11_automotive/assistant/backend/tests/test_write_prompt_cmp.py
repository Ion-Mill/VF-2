"""지시문 후보 시험 (2026-10-14, Qwen ↔ Claude 비교 실험 C단계): WRITE_SHOTS(좋은 답 예시 + 안전 낱말 남기기 한 줄)·WRITE_TITLES(줄의 절 제목).

지키는 것: ① 둘 다 꺼져 있으면 새로 쓰기 지시문이 예전과 한 글자도 다르지 않다 ② 제목은 한글만 남겨 숫자·영문이 답에 옮겨 오지 않게 한다
③ 줄 수와 맞지 않는 제목은 붙이지 않는다 ④ 스위치가 꺼져 있으면 write_doc_answer가 제목·예시를 쓰지 않는다.
"""
import json

import pytest

from backend.llm import prompts
from backend.services import answer as A
from backend.services import followup_v2 as FU2

UNITS = ["{{1}}마다 윤활유 양을 본다.", "덮개는 잠금·표지를 건 뒤에만 연다."]
BASE = prompts.write_answer("윤활유는 얼마나 자주 봐?", UNITS)


def text(msgs):
    return msgs[0]["content"] + "\n" + msgs[1]["content"]


def test_default_prompt_is_unchanged_without_the_switches():
    assert prompts.write_answer("윤활유는 얼마나 자주 봐?", UNITS, None, shots=False, titles=None) == BASE
    assert "좋은 답의 모양 예시" not in text(BASE) and "〈절" not in text(BASE)


def test_shots_add_examples_and_the_keep_safety_words_line():
    t = text(prompts.write_answer("윤활유는 얼마나 자주 봐?", UNITS, shots=True))
    assert "좋은 답의 모양 예시" in t and "[예 1]" in t and "[예 2]" in t and "안전 낱말이나 조건 말" in t
    assert t.startswith(text(BASE).split("\n\n질문:")[0][:40])         # 기본 지시문 뒤에 더한다
    # 예시 안에는 자리표 밖 숫자·영문이 없다 (복사돼도 코드 검사가 거부하는 값을 예시에 두지 않는다)
    ex = prompts.SHOTS_WRITE
    assert not any(ch.isdigit() for ch in ex.replace("{{1}}", "").replace("[예 1]", "").replace("[예 2]", "").replace("1.", "").replace("2.", ""))


def test_titles_are_attached_per_line_and_marked_not_to_copy():
    msgs = prompts.write_answer("윤활유는 얼마나 자주 봐?", UNITS, titles=["윤활 점검", ""])
    t = text(msgs)
    assert "1. {{1}}마다 윤활유 양을 본다.  〈절: 윤활 점검〉" in t and "2. 덮개는 잠금·표지를 건 뒤에만 연다.\n" in t + "\n"
    assert "답에 옮겨 쓰지 않는다" in msgs[0]["content"]
    assert prompts.write_answer("q", UNITS, titles=["하나뿐"]) == prompts.write_answer("q", UNITS)   # 줄 수가 다르면 붙이지 않는다


def test_title_words_keep_hangul_only_and_need_a_match():
    assert FU2.title_words_cmp(["알람 목록 — 2073 축 윤활 (HFO)", "스핀들 과열"], 2) == ["알람 목록 축 윤활", "스핀들 과열"]
    assert FU2.title_words_cmp(["2.11", "ABC"], 2) is None            # 한글이 하나도 없으면 쓰지 않는다
    assert FU2.title_words_cmp(["가", "나"], 3) is None and FU2.title_words_cmp(None, 1) is None


def test_cite_titles_need_one_cite_per_line():
    cites = [{"title": "윤활 점검"}, {"title": ""}]
    assert A._cite_titles(cites, ["a", "b"]) == ["윤활 점검", ""]
    assert A._cite_titles(cites, ["a"]) is None and A._cite_titles([], ["a"]) is None


@pytest.mark.parametrize("shots,titles", [(False, False), (True, False), (False, True), (True, True)])
def test_write_doc_answer_follows_the_switches(monkeypatch, shots, titles):
    monkeypatch.setenv("WRITE_SHOTS", "1" if shots else "0")
    monkeypatch.setenv("WRITE_TITLES", "1" if titles else "0")
    seen = []

    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        seen.append((name, json.dumps(messages, ensure_ascii=False)))
        return {"answer": "윤활유는 {{1}}마다 봐요."} if name == "write_answer" else {"faithful": True, "problem": ""}
    monkeypatch.setattr(FU2, "chat_json", fake)
    lines = ["4시간마다 윤활유 양을 본다.", "덮개는 잠금·표지를 건 뒤에만 연다."]
    FU2.write_doc_answer("윤활유는 얼마나 자주 봐?", lines, titles=["윤활 점검", "윤활 점검"])
    body = next(b for n, b in seen if n == "write_answer")
    assert ("좋은 답의 모양 예시" in body) is shots and ("〈절: 윤활 점검〉" in body) is titles
