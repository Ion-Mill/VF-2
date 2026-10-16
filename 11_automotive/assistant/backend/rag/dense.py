"""뜻으로 찾기 (임베딩 + pgvector) 와 하이브리드 순위 (BM25 + 벡터, Reciprocal Rank Fusion).

- 임베딩 글 = "문서 이름 DOC-0n §절 제목" + 본문 (조각 머리를 붙여 짧은 조각도 뜻이 드러나게 — contextual header).
- 조각은 chunker가 원문 출처를 이미 뺀 것만 쓴다 (원문 대응표 절 제외, sanitize 적용).
- 색인은 사내 문서 개정(조각 해시)이 바뀔 때만 다시 만든다. 기록에 이전 판 조각 수를 남긴다.
- 서버·DB가 없으면 None을 돌려주고, 부른 쪽은 BM25만 쓴다.
"""
from __future__ import annotations

import hashlib
import threading

from backend.config import settings
from backend.rag.chunker import Chunk, load_corpus
from backend.rag.embed import EmbedUnavailable, embed
from backend.rag.vector_store import PgVectorStore, VectorStore, VectorUnavailable

RRF_K = 60
_lock = threading.Lock()
_store: VectorStore | None = None
_ready: dict[str, str] = {}   # model → 색인을 확인한 corpus_hash
last_error: str | None = None


def embed_text(c: Chunk) -> str:
    return f"{c.doc_name} {c.doc_id} §{c.section} {c.title}\n{c.text}"


def corpus_hash(chunks=None) -> str:
    h = hashlib.sha256()
    for c in sorted(chunks or load_corpus(), key=lambda c: c.chunk_id):
        h.update(f"{c.chunk_id}|{c.file_hash}|{hashlib.sha256(embed_text(c).encode()).hexdigest()}\n".encode())
    return h.hexdigest()


def use_store(store: VectorStore | None) -> None:
    """시험용: 저장소를 바꿔 끼운다."""
    global _store, last_error
    with _lock:
        _store, last_error = store, None
        _ready.clear()


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = PgVectorStore(settings().database_url)
    return _store


def ensure_index(model: str | None = None, force: bool = False) -> dict:
    """색인이 지금 사내 문서와 같은지 보고, 다르면 다시 만든다."""
    model = model or settings().embed_model
    chunks = load_corpus()
    h = corpus_hash(chunks)
    with _lock:
        store = _get_store()
        if not force and (_ready.get(model) == h or store.corpus_hash(model) == h):
            _ready[model] = h
            return {"model": model, "rebuilt": False, "chunks": len(chunks)}
        vecs = embed([embed_text(c) for c in chunks])
        rows = [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "doc_name": c.doc_name, "revision": c.revision, "section": c.section,
                 "title": c.title, "text": c.text, "file_hash": c.file_hash, "embedding": v} for c, v in zip(chunks, vecs)]
        rec = store.replace(model, rows, h)
        _ready[model] = h
        return {**rec, "rebuilt": True}


def dense_search(query: str, k: int = 15) -> list[tuple[float, Chunk]] | None:
    """(코사인, 조각) 목록. 쓸 수 없으면 None (이유는 last_error)."""
    global last_error
    s = settings()
    try:
        ensure_index(s.embed_model)
        qv = embed([query], s)[0]
        hits = _get_store().search(s.embed_model, qv, k)
    except (EmbedUnavailable, VectorUnavailable) as e:
        last_error = f"{type(e).__name__}: {e}"
        return None
    by_id = {c.chunk_id: c for c in load_corpus()}
    last_error = None
    return [(cos, by_id[cid]) for cid, cos in hits if cid in by_id]


def rrf(*rankings: list[Chunk]) -> list[Chunk]:
    """여러 순위를 합친다: 점수 = Σ 1/(RRF_K + 순위). 같으면 chunk_id 순 (결정적)."""
    score: dict[str, float] = {}
    keep: dict[str, Chunk] = {}
    for ranking in rankings:
        for r, c in enumerate(ranking, start=1):
            score[c.chunk_id] = score.get(c.chunk_id, 0.0) + 1.0 / (RRF_K + r)
            keep[c.chunk_id] = c
    return [keep[i] for i in sorted(score, key=lambda i: (-score[i], i))]


def dense_last_error() -> str | None:
    return last_error


if __name__ == "__main__":  # 색인 만들기: python -m backend.rag.dense [--force]
    import json
    import sys
    print(json.dumps(ensure_index(force="--force" in sys.argv), ensure_ascii=False))
