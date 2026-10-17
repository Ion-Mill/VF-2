"""문서별 놓침 측정 도구(eval/doc_recall.py)와 DOC-04 점검표(eval/doc_qa/DOC-04.json) 시험 (2026-10-18).

기획: 261003_창민/다른문서_놓침_측정_기획_20261018.md. 이 시험이 지키는 것:
  - 점검표가 올바르다 (조각 번호가 문서에 있다, 질문 중복·빈 칸 없음, 조각마다 3개, 문서 이름표·제목을 베끼지 않았다, 문서 코드를 쓰지 않았다)
  - 도구는 결정적이다 (같은 설정이면 같은 값), Claude·백엔드·DB를 부르지 않는다, import만으로 환경을 바꾸지 않는다
  - DOC-05는 옛 도구(safety_recall)와 같은 값이 나온다
  - 적중률 숫자는 박지 않는다 (측정 단계의 값이고 문서가 바뀌면 달라진다)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from backend.config import Settings, settings
from backend.eval import doc_recall as DR
from backend.eval import safety_recall as SR
from backend.llm import client as C
from backend.llm import external as EXT
from backend.rag import search as RS
from backend.rag.chunker import load_corpus
from backend.services import pure_external as PURE

HERE = Path(__file__).resolve().parent
QA_DIR = HERE.parent / "eval" / "doc_qa"

APP_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "RETRIEVAL": "bm25", "NUM_MATCH": "value", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded",
             "DOC_GATE": "tiered", "PARSE_V3": "1", "SPLIT_Q": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
             "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1",
             "PARSE_V11": "1", "LEAD_V12": "1", "TERM_V13": "1", "EXTERNAL_LLM_APP": "1", "PURE_EXTERNAL": "1"}


def cfg(monkeypatch, safety="1", keep="1", expand="1") -> Settings:
    """권장 모양의 설정 (test_pure_safety.cfg와 같다). claude_app은 요청 단위라 외부 Claude 요청 안에서 읽는다."""
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXPAND", expand)
    monkeypatch.setenv("PURE_KEEP_SIGNALS", keep)
    monkeypatch.setenv("PURE_SAFETY", safety)
    with EXT.external_request("claude"):
        return settings()


CORPUS = load_corpus()
def key_of(c) -> str:
    """조각 키: 절 번호, 3,500자 넘어 쪼개진 절은 "3.6:2"처럼 뒤에 순번 (chunk_id에서 문서 번호를 뺀 것)."""
    return c.chunk_id.split(":", 1)[1]


# 점검표의 정답 키는 절 번호("3.6" = 그 절의 모든 조각) 또는 조각 키("3.6:2" = 그 조각만)
SECTIONS = {(c.doc_id, c.section): c for c in CORPUS}                   # 절 키 -> (쪼개졌으면 첫 조각)
KEYS = {(c.doc_id, key_of(c)): c for c in CORPUS}                      # 조각 키 -> 조각
VALID = {**SECTIONS, **KEYS}
DOC_TABLES = sorted(p.stem for p in QA_DIR.glob("DOC-*.json"))


def _norm(x: str) -> str:
    return re.sub(r"\s+", "", x)


# ------------------------------------------------------------------ ① 점검표가 올바르다
def test_there_is_a_doc04_table():
    assert "DOC-04" in DOC_TABLES
    assert "DOC-04" in DR.available()


def test_there_is_a_doc03_table_with_ninety_questions_over_thirty_chunks():
    """고장 대응 매뉴얼(DOC-03) 점검표 (2026-10-18, 측정만): 조각 30개 × 3 = 90개. 보류 질문 16개는 저장소 밖에 봉인한다."""
    assert "DOC-03" in DOC_TABLES and "DOC-03" in DR.available()
    assert sum(1 for c in CORPUS if c.doc_id == "DOC-03") == 30
    assert len(DR.load_items("DOC-03")) == 90


@pytest.mark.parametrize("doc", DOC_TABLES)
def test_table_items_are_complete_and_point_at_real_sections(doc):
    items = DR.load_items(doc)
    assert items
    for it in items:
        assert it["q"].strip() and it["doc"] == doc and it["sec"].strip()
        assert (doc, it["sec"]) in VALID, f"{doc} §{it['sec']} 조각이 문서에 없다 (문서가 바뀌었나?): {it['q']}"
        for a in it.get("also", []):
            assert (doc, a) in VALID, f"{doc} also §{a} 조각이 문서에 없다: {it['q']}"
            assert a != it["sec"]


@pytest.mark.parametrize("doc", DOC_TABLES)
def test_no_duplicate_questions(doc):
    qs = [_norm(it["q"]) for it in DR.load_items(doc)]
    assert len(qs) == len(set(qs))


@pytest.mark.parametrize("doc", DOC_TABLES)
def test_every_chunk_of_the_document_has_exactly_three_questions(doc):
    """기획 4장 2단계: 조각마다 질문 3개. 문서에 절이 늘면 이 시험이 점검표를 더하라고 알려 준다."""
    want = sorted(key_of(c) for c in CORPUS if c.doc_id == doc)            # 쪼개진 절은 조각마다 3개
    got = [it["sec"] for it in DR.load_items(doc)]
    assert sorted(set(got)) == want
    assert all(got.count(s) == 3 for s in want)


@pytest.mark.parametrize("doc", DOC_TABLES)
def test_questions_do_not_copy_the_section_title(doc):
    """제목을 그대로 베끼면 현장 말을 잰 게 아니다 (4글자 이상 제목만 본다 — "매일"·"필터" 같은 짧은 제목은 현장 말과 같다)."""
    for it in DR.load_items(doc):
        t = _norm(VALID[(doc, it["sec"])].title)
        if len(t) >= 4:
            assert t not in _norm(it["q"]), f"제목을 베꼈다: {it['q']} / {t}"


@pytest.mark.parametrize("doc", DOC_TABLES)
def test_questions_use_field_words_not_document_codes(doc):
    """현장 사람은 CS-COOL·OP-30·PM-… 같은 문서 속 코드로 묻지 않는다 (VF-2 같은 설비 이름은 현장 말이다)."""
    for it in DR.load_items(doc):
        assert not re.search(r"(?<![A-Za-z0-9])(?:CS|OP|PM|DOC|FR|NFR)-[A-Z0-9]+", it["q"]), f"문서 코드가 질문에 있다: {it['q']}"


def test_the_repo_has_no_sealed_holdout_file_and_notes_say_so():
    """보류 질문은 저장소 밖에 봉인한다 (처방을 확정한 뒤 한 번만 쓴다). 저장소에는 점검표만 있다."""
    names = sorted(p.name for p in QA_DIR.iterdir())
    assert all(re.fullmatch(r"DOC-\d{2}\.json", n) for n in names), names
    for doc in DOC_TABLES:
        note = json.loads((QA_DIR / f"{doc}.json").read_text(encoding="utf-8")).get("note", "")
        assert "봉인" in note


# ------------------------------------------------------------------ 조각 키 (쪼개진 절)
SPLIT = [c for c in CORPUS if c.doc_id == "DOC-06" and c.chunk_id.count(":") == 2]


def test_split_sections_have_part_keys_and_unsplit_sections_keep_the_section_number():
    keys = {key_of(c) for c in CORPUS if c.doc_id == "DOC-06"}
    assert {"3.6:1", "3.6:2", "6.1:1", "6.1:2", "9.1:1", "9.1:2"} <= keys and "3.6" not in keys and "4.2" in keys
    assert {key_of(c) for c in CORPUS if c.doc_id == "DOC-04"} == {c.section for c in CORPUS if c.doc_id == "DOC-04"}   # DOC-04는 쪼개진 절이 없다 — 키가 절 번호 그대로


def test_is_target_section_key_covers_every_part_and_part_key_only_that_part():
    parts = [c for c in SPLIT if c.section == "3.6"]
    assert len(parts) == 2
    assert all(DR.is_target(c, "DOC-06", {"3.6"}) for c in parts)                  # 절 키 = 모든 조각
    assert [DR.is_target(c, "DOC-06", {"3.6:2"}) for c in parts] == [False, True]  # 조각 키 = 그 조각만
    assert not DR.is_target(parts[0], "DOC-05", {"3.6"})                           # 문서가 다르면 아니다
    assert not DR.is_target(parts[0], "DOC-06", {"3.7"})


def test_rank_of_a_part_key_is_the_rank_of_that_part_not_of_the_section():
    q = "측정기 판정이랑 플랫폼 판정이 다르면 어느 걸 써?"
    ids = [c.chunk_id for _, c in RS.search(q, len(CORPUS))]
    r1, r2 = DR.rank_of(q, "DOC-06", {"3.6:1"}), DR.rank_of(q, "DOC-06", {"3.6:2"})
    assert r1 == (ids.index("DOC-06:3.6:1") + 1 if "DOC-06:3.6:1" in ids else None)
    assert r2 == (ids.index("DOC-06:3.6:2") + 1 if "DOC-06:3.6:2" in ids else None)
    sec = DR.rank_of(q, "DOC-06", {"3.6"})
    assert sec == min(x for x in (r1, r2) if x is not None)                        # 절 키는 두 조각 중 높은 쪽


def test_reached_by_part_key_does_not_count_the_other_part(monkeypatch):
    s = cfg(monkeypatch, safety="0", expand="0")                                    # 순위 8위 안만으로 따진다
    q = "측정기 판정이랑 플랫폼 판정이 다르면 어느 걸 써?"
    hits = [c.chunk_id for _, c in PURE.context(q, s.pure_topk, s)]
    for part in ("3.6:1", "3.6:2"):
        assert DR.reached(q, "DOC-06", {part}, s) == (f"DOC-06:{part}" in hits)
    assert DR.reached(q, "DOC-06", {"3.6"}, s) == any(h.startswith("DOC-06:3.6") for h in hits)


# ------------------------------------------------------------------ ② 도구가 결정적이고 부작용이 없다
def test_measure_is_deterministic(monkeypatch):
    s = cfg(monkeypatch)
    a, b = DR.measure("DOC-04", s), DR.measure("DOC-04", s)
    assert a == b


def test_measure_never_calls_claude_or_the_backend(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("측정 도구가 LLM을 불렀다")
    monkeypatch.setattr(C, "chat_json", boom)
    s = cfg(monkeypatch)
    m = DR.measure("DOC-04", s)
    assert m["total"] == len(DR.load_items("DOC-04"))


def test_import_does_not_change_the_environment():
    assert os.environ["PURE_SAFETY"] == "0"            # conftest가 고정한 값이 import로 안 바뀐다


def test_apply_recommended_env_only_sets_defaults(monkeypatch):
    monkeypatch.setenv("PURE_TOPK", "5")
    DR.apply_recommended_env()
    assert os.environ["PURE_TOPK"] == "5"              # 이미 정해진 값은 그대로 둔다
    monkeypatch.delenv("PURE_TOPK", raising=False)


# ------------------------------------------------------------------ ③ 순위·띠·길
@pytest.mark.parametrize("rank, band", [(1, "1-8"), (8, "1-8"), (9, "9-20"), (20, "9-20"), (21, "21-50"), (50, "21-50"), (51, "51+"), (400, "51+"), (None, "점수 0")])
def test_rank_bands(rank, band):
    assert DR.band(rank) == band


def test_rank_matches_the_plain_bm25_order():
    q = "절삭유 풀 때 몇 %로 맞춰?"
    full = RS.search(q, len(CORPUS))
    first = next(i for i, (_, c) in enumerate(full, 1) if c.doc_id == "DOC-04" and c.section == "4.2")
    assert DR.rank_of(q, "DOC-04", {"4.2"}) == first


def test_rank_is_none_when_the_answer_chunk_scores_zero():
    assert DR.rank_of("zzzzqqqq", "DOC-04", {"4.2"}) is None


def test_rank_uses_the_best_accepted_section():
    q = "그리스는 어디어디에 발라야 해?"
    best = min(DR.rank_of(q, "DOC-04", {s}) or 10**9 for s in ("2.3", "4.5"))
    assert DR.rank_of(q, "DOC-04", {"2.3", "4.5"}) == best


def test_with_expand_and_safety_off_reaching_is_exactly_top_k(monkeypatch):
    s = cfg(monkeypatch, safety="0", expand="0")
    for it in DR.load_items("DOC-04"):
        r = DR.rank_of(it["q"], "DOC-04", DR.accepted(it))
        assert DR.reached(it["q"], "DOC-04", DR.accepted(it), s) == (r is not None and r <= s.pure_topk), it["q"]


def test_with_safety_and_expand_on_reaching_is_never_worse_than_top_k(monkeypatch):
    s = cfg(monkeypatch)
    for it in DR.load_items("DOC-04"):
        r = DR.rank_of(it["q"], "DOC-04", DR.accepted(it))
        if r is not None and r <= s.pure_topk:
            assert DR.reached(it["q"], "DOC-04", DR.accepted(it), s), it["q"]


def test_accepted_includes_also():
    assert DR.accepted({"q": "x", "doc": "DOC-04", "sec": "2.3", "also": ["4.5"]}) == {"2.3", "4.5"}
    assert DR.accepted({"q": "x", "doc": "DOC-04", "sec": "2.3"}) == {"2.3"}


# ------------------------------------------------------------------ ④ 보고 모양
def test_measure_report_shape(monkeypatch):
    s = cfg(monkeypatch)
    m = DR.measure("DOC-04", s)
    assert m["doc"] == "DOC-04"
    assert m["total"] == len(m["rows"]) == 66
    assert 0 <= m["reached"] <= m["total"] and 0 <= m["pure_reached"] <= m["pure_total"] <= m["total"]
    assert len(m["misses"]) == m["total"] - m["reached"]
    assert sum(m["bands"].values()) == m["total"]
    assert set(m["bands"]) <= {"1-8", "9-20", "21-50", "51+", "점수 0"}
    assert len(m["old_route"]) == m["total"] - m["pure_total"]
    for r in m["misses"]:
        assert {"q", "sec", "rank", "band", "top1", "pure", "shared", "cause"} <= set(r)
        assert r["cause"] in DR.CAUSES


def test_a_miss_is_labelled_with_the_chunk_that_beat_it(monkeypatch):
    s = cfg(monkeypatch, safety="0", expand="0")
    m = DR.measure("DOC-04", s)
    for r in m["misses"]:
        assert r["top1"]                                 # 정답 대신 위에 있던 조각 (점수가 있는 한)
        assert r["top1"] != f"DOC-04:{r['sec']}" or r["rank"] == 1


def test_cause_labels_are_a_closed_list():
    assert DR.CAUSES == ("점수 0", "2글자 조각만 겹침", "경쟁 조각이 더 높음")


def test_cause_rules_on_hand_made_cases():
    assert DR.cause(None, [], False) == "점수 0"                    # 질문과 정답 조각이 낱말 하나도 안 겹친다
    assert DR.cause(30, [], True) == "2글자 조각만 겹침"            # 통째 낱말은 안 겹치고 두 글자 조각만 겹친다 (활용형·조사·합성어 차이)
    assert DR.cause(12, ["절삭유"], True) == "경쟁 조각이 더 높음"  # 통째 낱말이 겹치는데 다른 조각이 더 높다


def test_doc05_matches_the_old_safety_tool(monkeypatch):
    """DOC-05 점검표(safety_qa.json, 68개)는 그대로 두고 새 도구가 같은 값을 낸다 (기획 S2)."""
    s = cfg(monkeypatch)
    old, new = SR.measure(s), DR.measure("DOC-05", s)
    assert new["total"] == old["total"] == 68
    assert new["reached"] == old["reached"]
    assert new["pure_total"] == old["pure_total"] and new["pure_reached"] == old["pure_reached"]
    assert [r["q"] for r in new["misses"]] == [r["q"] for r in old["misses"]]


def test_measure_accepts_a_table_given_by_path(tmp_path, monkeypatch):
    """봉인 보류 질문은 저장소 밖 파일로 한 번만 돌린다 (--table)."""
    p = tmp_path / "hold.json"
    p.write_text(json.dumps({"items": [{"q": "절삭유 풀 때 몇 %로 맞춰?", "doc": "DOC-04", "sec": "4.2"}]}, ensure_ascii=False), encoding="utf-8")
    s = cfg(monkeypatch)
    m = DR.measure("DOC-04", s, items=DR.load_table(p))
    assert m["total"] == 1


def test_no_threshold_is_hardcoded_in_the_tool_source():
    """적중률 숫자로 통과·실패를 가르는 코드가 도구에 없다 (보고만 한다)."""
    src = (HERE.parent / "eval" / "doc_recall.py").read_text(encoding="utf-8")
    assert "sys.exit" not in src and "raise SystemExit" not in src
