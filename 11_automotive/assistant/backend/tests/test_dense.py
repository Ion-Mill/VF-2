"""뜻으로 찾기(임베딩 + 벡터 저장소)·하이브리드 순위 시험 — 가짜 임베딩 서버와 메모리 저장소로 본다."""
import hashlib
import json
import math
from pathlib import Path

import httpx
import pytest

from backend.rag import dense as D
from backend.rag import embed as E
from backend.rag.chunker import load_corpus
from backend.rag.vector_store import MemoryStore, _lit
from backend.services import answer as A

QA = json.loads((Path(__file__).resolve().parents[1] / "eval" / "qa_set.json").read_text(encoding="utf-8"))["items"]


def fake_vec(text: str) -> list[float]:
    """글자 2개 묶음을 해시로 1024칸에 뿌린 벡터 (결정적). 진짜 모델이 아니라 흐름만 본다."""
    v = [0.0] * 1024
    t = text.lower()
    for i in range(len(t) - 1):
        v[int(hashlib.md5(t[i:i + 2].encode()).hexdigest(), 16) % 1024] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeEmbed:
    def __init__(self):
        self.calls = 0

    def __call__(self, request):
        body = json.loads(request.content)
        self.calls += 1
        return httpx.Response(200, json={"data": [{"index": i, "embedding": fake_vec(t)} for i, t in enumerate(body["input"])]})


@pytest.fixture
def hybrid(monkeypatch):
    monkeypatch.setenv("RETRIEVAL", "hybrid")
    monkeypatch.setenv("EMBED_URL", "http://127.0.0.1:8081")
    fake, store = FakeEmbed(), MemoryStore()
    E.use_transport(httpx.MockTransport(fake))
    D.use_store(store)
    yield fake, store
    E.use_transport(None)
    D.use_store(None)


def test_index_built_once_and_logs_previous_count(hybrid):
    fake, store = hybrid
    r1 = D.ensure_index("bge-m3")
    assert r1["rebuilt"] and r1["chunks"] == len(load_corpus()) and r1["prev_chunks"] == 0
    calls = fake.calls
    assert D.ensure_index("bge-m3")["rebuilt"] is False and fake.calls == calls  # 같은 판이면 다시 만들지 않는다
    r3 = D.ensure_index("bge-m3", force=True)
    assert r3["prev_chunks"] == len(load_corpus())  # 이전 판 조각 수를 기록에 남긴다 (조용히 덮어쓰지 않음)


def test_corpus_hash_changes_with_text():
    chunks = list(load_corpus())
    h = D.corpus_hash(chunks)
    from dataclasses import replace
    chunks[0] = replace(chunks[0], text=chunks[0].text + " 개정")
    assert D.corpus_hash(chunks) != h


def test_rrf_is_deterministic():
    c = list(load_corpus())[:4]
    assert D.rrf([c[0], c[1], c[2]], [c[2], c[0], c[3]])[0] == c[0]
    assert D.rrf([c[1]], [c[0]]) == D.rrf([c[1]], [c[0]])  # 같은 점수면 chunk_id 순


def test_embedding_text_has_no_source_marks():
    from backend.rag.sanitize import FORBIDDEN
    assert not [c.chunk_id for c in load_corpus() if FORBIDDEN.search(D.embed_text(c))]
    assert _lit([0.5, -0.25]) == "[0.5000000,-0.2500000]"


def test_hybrid_never_fabricates_on_not_in_docs_questions(hybrid):
    for it in [x for x in QA if x["type"] == "none"]:
        a = A.answer(it["q"], "SUP")
        assert a["status"] != "답변", it["q"]


def test_hybrid_doc_answers_still_cite_internal_docs(hybrid):
    a = A.answer("공기 필터는 언제 바꿔?", "SUP")
    assert a["status"] == "답변" and a["evidence"][0]["doc_id"].startswith(("DOC-", "GLOSSARY"))
    assert a["retrieval"]["mode"] == "hybrid"


def test_hybrid_falls_back_to_bm25_when_embed_server_is_down(monkeypatch):
    monkeypatch.setenv("RETRIEVAL", "hybrid")
    E.use_transport(httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("down"))))
    D.use_store(MemoryStore())
    try:
        a = A.answer("공기 필터는 언제 바꿔?", "SUP")
        with pytest.MonkeyPatch.context() as m:
            m.setenv("RETRIEVAL", "bm25")
            b = A.answer("공기 필터는 언제 바꿔?", "SUP")
        assert a["conclusion"] == b["conclusion"] and "BM25" in a["retrieval"]["reason"]
    finally:
        E.use_transport(None)
        D.use_store(None)
