"""고장 낱말이면 DOC-03을 통째로 붙이기(PURE_FAULTDOC) 시험 (2026-10-18). 기획: 261003_창민/고장낱말_DOC03_통째붙이기_기획_20261018.md

DOC-03(고장 대응 매뉴얼)을 현장 말로 물으면 정답 절이 낱말 검색 상위 8개 밖(대개 21위 밖)에 있어서 Claude가 보지 못한다(점검표 73/90).
스위치 PURE_FAULTDOC=1이면 질문에 고장 낱말(알람·경고·떴어·멈췄어·정지·고장·에러·과열·누설 …)이 있을 때 DOC-03 조각을 통째로(문서 순서, 상한 FAULTDOC_MAX_CHARS) 더한다.
PURE_SAFETY가 DOC-05를 통째로 붙이는 것과 같은 방식이다. 이 시험은 적중률 숫자를 박지 않는다 — 발동 판정·더해지는 조각·끄면 동일·인용 변환만 본다.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.rag.chunker import load_corpus
from backend.services import answer_store as AS
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS, cfg as _cfg

client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
PROPS = ("answer", "cited", "insufficient")
D03 = [c for c in load_corpus() if c.doc_id == "DOC-03"]
Q = "화면에 문 열렸다고 뜨는데 어떻게 해?"                 # 신호가 없는 순수 길 질문, 고장 낱말("뜨는데")이 있다


def cfg(monkeypatch, faultdoc="1", **kw) -> Settings:
    monkeypatch.setenv("PURE_FAULTDOC", faultdoc)
    return _cfg(monkeypatch, **kw)


WITH_FAULT_WORDS = [
    "화면에 문 열렸다고 뜨는데 어떻게 해?", "공구 수명 다 됐다고 알람이 떴어", "설비가 갑자기 멈췄어요", "에러가 났는데 리셋 눌러도 돼?", "주축이 과열이라고 나와요",
    "윤활유 모자라다고 경고가 떴어", "누설이 의심되면 어떻게 봐?", "정지 걸렸을 때 먼저 뭘 해?", "고장 났을 땐 누가 와?", "기계가 꺼졌어. 다시 켜도 돼?",
]
WITHOUT_FAULT_WORDS = [
    "사내 체육대회 누가 정해?", "초품 검사는 누가 해?", "원자재 성적서는 뭘 대조해?", "예방 정비 항목 코드는 어떻게 만들어?", "검사 강화는 몇 개 로트까지 해?",
    "그리스 안전 재고는 몇 개야?", "교대 보고서는 언제 확정해?", "공구 수명 90%는 무슨 뜻이야?",
]


@pytest.mark.parametrize("q", WITH_FAULT_WORDS, ids=[f"F{i}" for i in range(len(WITH_FAULT_WORDS))])
def test_fault_words_are_detected(q):
    assert PURE.is_fault_text(q), q


@pytest.mark.parametrize("q", WITHOUT_FAULT_WORDS, ids=[f"N{i}" for i in range(len(WITHOUT_FAULT_WORDS))])
def test_questions_without_fault_words_are_not_detected(q):
    assert not PURE.is_fault_text(q), q


# ------------------------------------------------------------------ add_fault_doc
def test_add_fault_doc_adds_only_the_missing_doc03_chunks_in_document_order():
    hits = PURE.retrieve("공구 수명 알람", 8)
    out = PURE.add_fault_doc(hits)
    assert out[:len(hits)] == hits                                           # 원래 조각의 순서·점수는 그대로
    added = out[len(hits):]
    have = {c.chunk_id for _, c in hits}
    want = [c for c in D03 if c.chunk_id not in have]
    assert [c.chunk_id for _, c in added] == [c.chunk_id for c in want]       # DOC-03의 없던 조각만, 문서 순서
    assert {sc for sc, _ in added} == {PURE.FAULTDOC_SCORE}                    # 검색 점수가 아니라는 표시
    assert sum(len(c.text) for _, c in added) <= PURE.FAULTDOC_MAX_CHARS


def test_add_fault_doc_respects_the_character_cap(monkeypatch):
    monkeypatch.setattr(PURE, "FAULTDOC_MAX_CHARS", 5000)
    out = PURE.add_fault_doc([])
    assert out and sum(len(c.text) for _, c in out) <= 5000
    assert len(out) < len(D03)


def test_the_whole_of_doc03_fits_under_the_default_cap():
    assert sum(len(c.text) for c in D03) <= PURE.FAULTDOC_MAX_CHARS, "문서가 커져 상한을 넘었다 — 상한을 올릴지 정하라"


def test_the_added_marker_differs_from_the_other_markers():
    assert len({PURE.FAULTDOC_SCORE, PURE.SAFETY_SCORE, 0.0}) == 3


# ------------------------------------------------------------------ context()
def test_off_is_exactly_what_it_was(monkeypatch):
    s0 = cfg(monkeypatch, faultdoc="0")
    base = [c.chunk_id for _, c in PURE.context(Q, s0.pure_topk, s0)]
    s1 = cfg(monkeypatch, faultdoc="1")
    on = [c.chunk_id for _, c in PURE.context(Q, s1.pure_topk, s1)]
    assert on[:len(base)] == base                                            # 켜도 앞부분은 같다
    assert not (set(c.chunk_id for c in D03) <= set(base))                   # 꺼진 쪽은 DOC-03이 통째로 들어 있지 않다(전제)


def test_on_with_fault_words_puts_every_doc03_chunk_into_the_context(monkeypatch):
    s = cfg(monkeypatch)
    ids = {c.chunk_id for _, c in PURE.context(Q, s.pure_topk, s)}
    assert {c.chunk_id for c in D03} <= ids


def test_on_without_fault_words_changes_nothing(monkeypatch):
    for q in WITHOUT_FAULT_WORDS:
        s0 = cfg(monkeypatch, faultdoc="0")
        a = [c.chunk_id for _, c in PURE.context(q, s0.pure_topk, s0)]
        s1 = cfg(monkeypatch, faultdoc="1")
        b = [c.chunk_id for _, c in PURE.context(q, s1.pure_topk, s1)]
        assert a == b, q


def test_with_safety_both_documents_are_added(monkeypatch):
    s = cfg(monkeypatch, safety="1")
    q = "톱 정비 전에 알람이 떴는데 어디를 차단해야 해?"
    docs = {c.doc_id for _, c in PURE.context(q, s.pure_topk, s)}
    assert {"DOC-03", "DOC-05"} <= docs
    ids = {c.chunk_id for _, c in PURE.context(q, s.pure_topk, s)}
    assert {c.chunk_id for c in D03} <= ids


def test_the_wide_retry_context_keeps_the_added_chunks(monkeypatch):
    s = cfg(monkeypatch)
    narrow = {c.chunk_id for _, c in PURE.context(Q, s.pure_topk, s)}
    wide = {c.chunk_id for _, c in PURE.context(Q, 30, s)}
    assert narrow <= wide or {c.chunk_id for c in D03} <= wide


# ------------------------------------------------------------------ 설정
def test_default_is_off_and_env_is_read(monkeypatch):
    assert Settings.__dataclass_fields__["pure_faultdoc"].default is False
    monkeypatch.delenv("PURE_FAULTDOC", raising=False)
    assert settings().pure_faultdoc is False                                # 시험 기본(conftest)도 꺼짐
    for raw, want in (("1", True), ("true", True), ("0", False), ("", False), ("아무거나", False)):
        monkeypatch.setenv("PURE_FAULTDOC", raw)
        assert settings().pure_faultdoc is want


# ------------------------------------------------------------------ 끝에서 끝 (가짜 Claude 실행기)
class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        n = max([int(x) for x in re.findall(r"\[C(\d+)\]", stdin_text)] or [1])
        self.calls.append({"props": tuple(sorted((sch.get("properties") or {}).keys())), "user": stdin_text, "n": n})
        so = {"answer": "문서 답이에요.", "cited": [f"C{n}"], "insufficient": False}        # 마지막 조각을 인용한다
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


@pytest.fixture
def run(monkeypatch):
    def _run(q=Q, **env):
        get_state().reset()
        AS.clear()
        for k, v in APP_FLAGS.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("PURE_EXPAND", "1")
        monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        r = Runner()

        def no_local(req):
            raise httpx.ConnectError("시험: 로컬 서버 없음")
        C.use_transport(httpx.MockTransport(no_local))
        CC.use_runner(r)
        return client.post("/api/assistant/chat", json={"question": q, "llm": "claude"}, headers={"X-Role": "SUP"}), r
    yield _run
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def test_end_to_end_on_sends_the_whole_document_and_the_citation_resolves_to_it(run):
    resp, r = run(PURE_FAULTDOC="1")
    assert resp.status_code == 200 and len(r.calls) == 1
    user = r.calls[0]["user"]
    assert all(c.title in user for c in D03)                                  # DOC-03의 모든 조각이 요청 글에 있다
    evid = {(e["doc_id"], e["section"]) for e in resp.json()["evidence"]}
    assert any(d == "DOC-03" for d, _ in evid)                                # 마지막(더해진) 조각을 인용 → DOC-03 출처로 변환


def test_end_to_end_off_does_not_send_the_whole_document(run):
    resp, r = run(PURE_FAULTDOC="0")
    user = r.calls[0]["user"]
    assert not all(c.title in user for c in D03)


def test_end_to_end_off_request_is_identical_to_the_default(run, monkeypatch):
    _, r_off = run(PURE_FAULTDOC="0")
    _, r_unset = run(PURE_FAULTDOC="")                                         # 모르는 값·빈 값도 꺼짐
    assert r_off.calls[0]["user"] == r_unset.calls[0]["user"]
