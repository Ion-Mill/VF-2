"""문서 검색 벡터 저장소 = PostgreSQL + pgvector (기술 규칙 [제안], 2026-10-08 사용자 결정: 지금 설치).

- 접속 정보는 .env의 DATABASE_URL (값은 화면·로그에 내지 않는다).
- psycopg는 쓸 때만 불러온다. 없거나 DB가 꺼져 있으면 VectorUnavailable → 검색은 BM25만 쓴다.
- 벡터는 pgvector 글자 꼴('[0.1,0.2,…]')로 넘긴다(파이썬 pgvector 패키지 없이).
- 조각이 200개 안팎이라(2026-10-11 195개) 근사 색인(HNSW) 없이 정확 검색한다 [제안].
"""
from __future__ import annotations

from typing import Protocol

DIM = 1024  # bge-m3·KURE-v1 벡터 길이


class VectorUnavailable(RuntimeError):
    pass


class VectorStore(Protocol):
    def corpus_hash(self, model: str) -> str | None: ...
    def replace(self, model: str, rows: list[dict], corpus_hash: str) -> dict: ...
    def search(self, model: str, vec: list[float], k: int) -> list[tuple[str, float]]: ...


def _lit(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS doc_chunk (
  chunk_id text NOT NULL, model_name text NOT NULL, doc_id text NOT NULL, doc_name text NOT NULL, revision text NOT NULL,
  section text NOT NULL, title text NOT NULL, text text NOT NULL, file_hash text NOT NULL,
  embedding vector({DIM}) NOT NULL, indexed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (chunk_id, model_name));
CREATE TABLE IF NOT EXISTS doc_index_log (
  id serial PRIMARY KEY, model_name text NOT NULL, at timestamptz NOT NULL DEFAULT now(),
  chunks int NOT NULL, prev_chunks int, corpus_hash text NOT NULL, prev_corpus_hash text);
"""


class PgVectorStore:
    def __init__(self, dsn: str | None):
        if not dsn:
            raise VectorUnavailable("DATABASE_URL 없음")
        try:
            import psycopg  # noqa: PLC0415 — 설치 승인 전에는 없을 수 있다
        except ImportError as e:
            raise VectorUnavailable("psycopg 미설치") from e
        self._psycopg, self._dsn = psycopg, dsn
        with self._conn() as c:
            c.execute(SCHEMA)

    def _conn(self):
        try:
            return self._psycopg.connect(self._dsn, connect_timeout=2, autocommit=False)
        except self._psycopg.Error as e:
            raise VectorUnavailable(f"DB 연결 실패: {type(e).__name__}") from e

    def corpus_hash(self, model: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT corpus_hash FROM doc_index_log WHERE model_name=%s ORDER BY id DESC LIMIT 1", (model,)).fetchone()
        return row[0] if row else None

    def replace(self, model: str, rows: list[dict], corpus_hash: str) -> dict:
        """한 번에 바꾼다(트랜잭션). 이전 판 조각 수·해시를 기록에 남긴다 — 조용히 덮어쓰지 않는다."""
        with self._conn() as c:
            prev = c.execute("SELECT count(*) FROM doc_chunk WHERE model_name=%s", (model,)).fetchone()[0]
            prev_hash = c.execute("SELECT corpus_hash FROM doc_index_log WHERE model_name=%s ORDER BY id DESC LIMIT 1",
                                  (model,)).fetchone()
            c.execute("DELETE FROM doc_chunk WHERE model_name=%s", (model,))
            with c.cursor() as cur:
                cur.executemany(
                    "INSERT INTO doc_chunk (chunk_id, model_name, doc_id, doc_name, revision, section, title, text, file_hash, embedding)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                    [(r["chunk_id"], model, r["doc_id"], r["doc_name"], r["revision"], r["section"], r["title"], r["text"],
                      r["file_hash"], _lit(r["embedding"])) for r in rows])
            c.execute("INSERT INTO doc_index_log (model_name, chunks, prev_chunks, corpus_hash, prev_corpus_hash) VALUES (%s,%s,%s,%s,%s)",
                      (model, len(rows), prev, corpus_hash, prev_hash[0] if prev_hash else None))
            c.commit()
        return {"model": model, "chunks": len(rows), "prev_chunks": prev, "prev_corpus_hash": prev_hash[0] if prev_hash else None}

    def search(self, model: str, vec: list[float], k: int) -> list[tuple[str, float]]:
        lit = _lit(vec)
        with self._conn() as c:
            rows = c.execute("SELECT chunk_id, 1 - (embedding <=> %s::vector) FROM doc_chunk WHERE model_name=%s "
                             "ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s", (lit, model, lit, k)).fetchall()
        return [(r[0], float(r[1])) for r in rows]


class MemoryStore:
    """시험용 저장소 (같은 인터페이스). 운영에서는 쓰지 않는다."""

    def __init__(self):
        self.rows: dict[str, list[dict]] = {}
        self.hashes: dict[str, str] = {}
        self.log: list[dict] = []

    def corpus_hash(self, model):
        return self.hashes.get(model)

    def replace(self, model, rows, corpus_hash):
        rec = {"model": model, "chunks": len(rows), "prev_chunks": len(self.rows.get(model, [])), "prev_corpus_hash": self.hashes.get(model)}
        self.rows[model], self.hashes[model] = rows, corpus_hash
        self.log.append(rec)
        return rec

    def search(self, model, vec, k):
        scored = [(r["chunk_id"], sum(a * b for a, b in zip(vec, r["embedding"]))) for r in self.rows.get(model, [])]
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:k]
