"""번호 붙은 절차 표 채우기 시험 (TABLE_FILL_V18, 2026-10-15, 사용자 승인 계획 "전원 켜기 표 1·6번 빠짐").

앱 화면: "VF2-01 전원을 켜고 원점 복귀할 때 사람이 조심할 게 뭐야?"에 DOC-01 §4.3 ①의 6줄 표 중 2~5번만 나왔다. 줄 고르기(LLM)가 일부만 골랐고
다른 단계는 줄을 빼지 않았다. 시동 절차를 말없이 일부만 보이지 않도록, 검사를 다 지난 뒤 보일 줄에서만 같은 표의 나머지 줄을 문서 순서로 채운다.
AI 서버는 부르지 않는다(chat_json을 가짜로 끼움). 실제 사내 문서 조각을 쓴다.
"""
import dataclasses
import re

import pytest

from backend.eval import run_eval as R
from backend.llm.client import LlmUnavailable
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import followup_v2 as FU2

Q = "VF2-01 전원을 켜고 원점 복귀할 때 사람이 조심할 게 뭐야?"
CHUNK_ID = "DOC-01:4.3:1"


def _mode(monkeypatch, name="step20-gate", fill="1"):
    for k, v in R.MODES[name].items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("TABLE_FILL_V18", fill)


@pytest.fixture(scope="module")
def chunk():
    return next(c for c in load_corpus() if c.chunk_id == CHUNK_ID)


@pytest.fixture(scope="module")
def rows(chunk):
    """① 전원 켜기와 원점 복귀 표의 6줄 (plain_lines 7~12번째)."""
    got = [t for t in A.plain_lines(chunk) if re.match(r"^[1-6] — 할 일: ", t)][:6]
    assert len(got) == 6 and got[0].startswith("1 — 할 일: 화면에 ") and got[5].startswith("6 — 할 일: 운전하려면 ")
    return got


def test_default_is_off_and_pinned():
    assert R._BASE["TABLE_FILL_V18"] == "0"
    assert all(R.MODES[m]["TABLE_FILL_V18"] == "0" for m in R.MODES)
    assert A.settings().table_fill_v18 is False and A.table_fill_on() is False


def test_off_changes_nothing(monkeypatch, chunk, rows):
    _mode(monkeypatch, fill="0")
    assert A.table_fill_v18(rows[1:5], [chunk] * 4) is None


def test_the_numbered_tables_of_the_chunk_are_found_in_document_order(chunk, rows):
    tables = A.numbered_tables_v18(chunk)
    first = next(v for v in tables.values() if v and v[0].startswith("1 — 할 일: 화면에 "))
    assert first == rows                                 # 6줄, 문서 순서, plain_lines와 같은 글
    assert all(2 <= len(v) <= A.MAX_TABLE_ROWS for v in tables.values())


def test_missing_first_and_last_rows_are_filled(monkeypatch, chunk, rows):
    _mode(monkeypatch)
    got = A.table_fill_v18(rows[1:5], [chunk] * 4)       # 화면에서 본 꼴: 2~5번만 골랐다
    assert got is not None
    lines, chs = got
    assert lines == rows and chs == [chunk] * 6          # 1~6번이 문서 순서로, 줄마다 같은 조각


def test_a_single_selected_row_fills_the_whole_table(monkeypatch, chunk, rows):
    _mode(monkeypatch)
    lines, chs = A.table_fill_v18([rows[4]], [chunk])    # 5번(주의 줄)만 골라도 절차 전체가 나온다
    assert lines == rows and len(chs) == 6


def test_other_lines_keep_their_place_and_the_table_is_inserted_once(monkeypatch, chunk, rows):
    _mode(monkeypatch)
    plain = A.plain_lines(chunk)
    other_before = next(t for t in plain if t.startswith("외곽 정삭") or "하는 일" in t)   # 표 밖(또는 번호 없는 표) 줄
    other_after = next(t for t in plain if "20분 워밍업" in t)
    lines, chs = A.table_fill_v18([other_before, rows[2], other_after, rows[4]], [chunk] * 4)
    assert lines == [other_before] + rows + [other_after]    # 5번이 뒤에 또 있어도 표는 한 번만
    assert len(chs) == len(lines)


def test_nothing_to_do_returns_none(monkeypatch, chunk, rows):
    _mode(monkeypatch)
    assert A.table_fill_v18(rows, [chunk] * 6) is None   # 이미 6줄 다 있다
    no_number = next(t for t in A.plain_lines(chunk) if t.startswith("설비 · "))   # 번호 없는 표(항목|내용|근거)의 줄
    assert A.table_fill_v18([no_number], [chunk]) is None
    assert A.table_fill_v18([], []) is None
    assert A.table_fill_v18(rows[1:3], [chunk]) is None  # 줄과 조각의 길이가 다르면 건드리지 않는다


def test_a_table_longer_than_the_limit_is_left_alone(monkeypatch):
    _mode(monkeypatch)
    body = ["| # | 할 일 |", "|---|---|"] + [f"| {n} | {n}번째로 하는 일을 한다 |" for n in range(1, A.MAX_TABLE_ROWS + 2)]
    c = dataclasses.replace(next(c for c in load_corpus() if c.doc_id == "DOC-01"), chunk_id="X:1", text="\n".join(body))
    t = A.plain_lines(c)[3]
    assert A.numbered_tables_v18(c) == {}                # 13줄 > 12줄이라 대상이 아니다 (줄이는 일이 아니라 늘리는 일이라 그대로)
    assert A.table_fill_v18([t], [c]) is None


def test_tables_that_are_not_numbered_one_to_n_are_left_alone(monkeypatch):
    _mode(monkeypatch)
    for first in (["1", "3", "4"], ["2", "3", "4"], ["가", "나", "다"], ["1", "1", "2"]):
        body = ["| # | 할 일 |", "|---|---|"] + [f"| {f} | {i}번째로 하는 일을 한다 |" for i, f in enumerate(first, 1)]
        c = dataclasses.replace(next(c for c in load_corpus() if c.doc_id == "DOC-01"), chunk_id="X:2", text="\n".join(body))
        assert A.numbered_tables_v18(c) == {}, first


@pytest.mark.parametrize("doc", ["DOC-03", "DOC-05"])
def test_incident_and_safety_documents_are_not_touched(monkeypatch, doc):
    _mode(monkeypatch)
    for c in load_corpus():
        if c.doc_id == doc:
            tables = A.numbered_tables_v18(c)
            for rows_ in tables.values():
                assert A.table_fill_v18(rows_[1:2], [c]) is None   # 번호 붙은 표여도 이 문서 줄은 건드리지 않는다 (이미 규칙이 처리)
    assert any(c.doc_id == doc for c in load_corpus())


def test_the_filled_lines_have_source_cites_one_to_one(monkeypatch, chunk, rows):
    _mode(monkeypatch)
    lines, chs = A.table_fill_v18(rows[1:5], [chunk] * 4)
    cites = [A._line_cite(ch) for ch in chs]
    assert len(cites) == len(lines) and {c["doc_id"] for c in cites} == {"DOC-01"} and {c["section"] for c in cites} == {chunk.section}


# ── 끝에서 끝 (가짜 LLM): 줄 고르기가 2~5번만 골라도 화면 답에는 6줄이 모두 나온다 ──
def _run(monkeypatch, fill):
    _mode(monkeypatch, "step20-gate", fill)
    plain = A.plain_lines(next(c for c in load_corpus() if c.chunk_id == CHUNK_ID))
    picked = [t for t in plain if re.match(r"^[2-5] — 할 일: ", t)][:4]
    assert len(picked) == 4

    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        user = messages[-1]["content"]
        if name == "route":
            return {"kind": "doc", "intents": [], "equipment": [], "period": "none", "shift": "none",
                    "search_queries": ["전원 켜기 원점 복귀 주의", "POWER UP 원점 복귀"], "doc_question": ""}
        if name == "select":
            by_id = {m.group(1): m.group(2) for m in re.finditer(r"^(L\d+): (.*)$", user, re.M)}
            ids = [i for i, t in by_id.items() if t in picked]
            return {"answerable": bool(ids), "line_ids": ids[:6], "lead": "원점 복귀 전 순서와 주의"}
        if name == "verify":
            return {"answers": True, "missing": ""}
        raise LlmUnavailable("이 시험은 모르는 작업")

    monkeypatch.setattr(A.jobs, "chat_json", fake)
    monkeypatch.setattr(FU2, "chat_json", fake)
    return A.answer(Q, "OPR"), picked


def test_end_to_end_partial_pick_is_completed_only_with_the_switch(monkeypatch):
    a, picked = _run(monkeypatch, "0")
    assert a["status"] == "답변"
    shown = [n for n in range(1, 7) if re.search(rf"(?<![0-9]){n} — 할 일: ", a["conclusion"])]
    assert shown == [2, 3, 4, 5]                          # 스위치를 끄면 예전과 같다 (화면에서 본 꼴)
    a, _ = _run(monkeypatch, "1")
    assert a["status"] == "답변"
    shown = [n for n in range(1, 7) if re.search(rf"(?<![0-9]){n} — 할 일: ", a["conclusion"])]
    assert shown == [1, 2, 3, 4, 5, 6]                    # 켜면 6줄이 문서 순서로
    assert a["conclusion"].index("1 — 할 일: ") < a["conclusion"].index("6 — 할 일: ")
    assert "POWER UP" in a["conclusion"] and "화면에 " in a["conclusion"] and "HANDLE JOG" in a["conclusion"]   # 1번(POWER ON)과 6번(CYCLE START)
