"""로컬 임베딩 서버(llama-server --embedding, OpenAI 호환 /v1/embeddings) 호출 (NFR-SEC-08: 루프백만).

모델은 bge-m3(시작, 2026-10-08 결정) → 4단계에서 KURE-v1과 비교해 정한다. 벡터는 길이 1로 맞춰 돌려준다.
"""
from __future__ import annotations

import math
import time

import httpx

from backend.config import Settings, settings

BATCH = 16
_down_until: dict[str, float] = {}
_transport: httpx.BaseTransport | None = None


class EmbedUnavailable(RuntimeError):
    pass


def use_transport(t: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = t
    _down_until.clear()


def embed(texts: list[str], s: Settings | None = None) -> list[list[float]]:
    s = s or settings()
    if s.problem:
        raise EmbedUnavailable(s.problem)
    if _down_until.get(s.embed_url, 0) > time.monotonic():
        raise EmbedUnavailable("차단기: 최근 연결 실패")
    headers = {"Authorization": f"Bearer {s.api_key}"} if s.api_key else {}
    out: list[list[float]] = []
    with httpx.Client(base_url=s.embed_url, transport=_transport, trust_env=False,
                      timeout=httpx.Timeout(max(s.read_s, 30), connect=s.connect_s)) as c:
        for i in range(0, len(texts), BATCH):
            try:
                r = c.post("/v1/embeddings", json={"model": s.embed_model, "input": texts[i:i + BATCH]}, headers=headers)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                _down_until[s.embed_url] = time.monotonic() + 30
                raise EmbedUnavailable(type(e).__name__) from e
            except httpx.TimeoutException as e:
                raise EmbedUnavailable("응답 시간 초과") from e
            if r.status_code != 200:
                raise EmbedUnavailable(f"HTTP {r.status_code}")
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            for d in data:
                v = d["embedding"]
                n = math.sqrt(sum(x * x for x in v)) or 1.0
                out.append([x / n for x in v])
    if len(out) != len(texts):
        raise EmbedUnavailable("벡터 수가 글 수와 다름")
    return out
