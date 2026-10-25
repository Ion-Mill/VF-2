"""사내 문서 검색 (표준 라이브러리 BM25 + 한국어 음절 2-gram + 용어집 동의어 확장).

검색기 인터페이스(search)는 나중에 pgvector·로컬 임베딩 구현으로 바꿀 수 있게 둔다.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from backend.rag.chunker import Chunk, glossary_text, load_corpus

K1, B = 1.4, 0.75
STOP = set("은 는 이 가 을 를 에 의 도 로 와 과 뭐 어떻게 무엇 해 해야 하나 하나요 돼 되나 뜨면 떠 있어 알려줘 알려 줘 좀".split())


def tokens(text: str) -> list[str]:
    text = text.lower()
    out = []
    for word in re.findall(r"[0-9a-z][0-9a-z.\-]*|[가-힣]+", text):
        if word in STOP:
            continue
        if re.match(r"[가-힣]", word):
            out.append(word)
            out.extend(word[i:i + 2] for i in range(len(word) - 1))
        else:
            out.append(word)
    return out


@lru_cache(maxsize=1)
def synonyms() -> dict[str, str]:
    """용어집 표의 '쓰지 않는 말'·'영어' → '표준어'."""
    text = glossary_text()      # 로컬 파일 또는 (DOCS_SOURCE=db) 공용 DB 조각 — chunker.glossary_text
    syn = {}
    header = None
    for line in text.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if header is None:
            header = cells
            continue
        if "표준어" not in header:
            continue
        std = re.sub(r"\*|\(.*?\)", "", cells[header.index("표준어")]).strip()
        if not std or std == "—":
            continue
        for col in ("쓰지 않는 말", "영어"):
            if col in header:
                for alt in re.split(r"[,/·]", cells[header.index(col)]):
                    alt = re.sub(r"\*|\(.*?\)|[\"“”]", "", alt).strip().lower()
                    if alt and alt != "—" and len(alt) >= 2:
                        syn[alt] = std
    return syn


def expand(query: str) -> str:
    q = query.lower()
    extra = [std for alt, std in synonyms().items() if alt in q]
    return query + (" " + " ".join(extra) if extra else "")


class Bm25Index:
    def __init__(self, chunks: tuple[Chunk, ...]):
        self.chunks = chunks
        self.docs = [Counter(tokens(f"{c.title} {c.title} {c.doc_name} {c.text}")) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / max(len(self.lengths), 1)
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[float, Chunk]]:
        q = tokens(expand(query))
        scores = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf.get(t, 0) * tf * (K1 + 1) / (tf + K1 * (1 - B + B * self.lengths[i] / self.avg))
            if s > 0:
                scores.append((s, self.chunks[i]))
        scores.sort(key=lambda x: (-x[0], x[1].chunk_id))
        return scores[:k]


@lru_cache(maxsize=1)
def index() -> Bm25Index:
    return Bm25Index(load_corpus())


def search(query: str, k: int = 5) -> list[tuple[float, Chunk]]:
    return index().search(query, k)


def scores(query: str) -> dict[str, float]:
    """모든 조각의 BM25 점수 (하이브리드에서 벡터로만 찾은 조각도 같은 문턱으로 보기 위해)."""
    return {c.chunk_id: s for s, c in index().search(query, len(index().chunks))}
