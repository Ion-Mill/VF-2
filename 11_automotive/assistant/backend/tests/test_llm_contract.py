"""실제 로컬 서버 계약 시험 — 서버가 없으면 건너뛴다 (보통 시험에서는 늘 건너뜀).

실행: LLM_CONTRACT=1 LLM_ENABLED=1 python -m pytest backend/tests/test_llm_contract.py -q
보는 것: 생각(thinking) 모드가 꺼졌는지, JSON 스키마를 지키는지, 응답 시간, 임베딩 길이 1024·단위 벡터.
"""
import json
import math
import os
import time

import httpx
import pytest

from backend.config import settings

pytestmark = pytest.mark.skipif(os.environ.get("LLM_CONTRACT") != "1", reason="실제 서버 계약 시험은 LLM_CONTRACT=1일 때만")


@pytest.fixture(autouse=True)
def _llm_on(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "1")


def _alive(url):
    try:
        return httpx.get(f"{url}/health", timeout=1, trust_env=False).status_code == 200
    except httpx.HTTPError:
        return False


def test_chat_json_schema_no_thinking():
    from backend.llm import prompts, schemas
    from backend.llm.client import chat_json
    s = settings()
    if not _alive(s.llm_url):
        pytest.skip("LLM 서버 없음")
    draft = "2026-09-30 야간 VF2-01 정지 전체 8번 169분, 고장 손실 약 0개(추정)"
    t0 = time.monotonic()
    out = chat_json(prompts.phrase(draft), schemas.phrase(len(draft)), "phrase", 300)
    assert set(out) == {"conclusion"} and isinstance(out["conclusion"], str)
    assert time.monotonic() - t0 < s.read_s


def test_embeddings_shape():
    from backend.rag.embed import embed
    s = settings()
    if not _alive(s.embed_url):
        pytest.skip("임베딩 서버 없음")
    v = embed(["축 윤활유 보충", "공기 필터 교체"])
    assert len(v) == 2 and all(len(x) == 1024 for x in v)
    assert all(abs(math.sqrt(sum(a * a for a in x)) - 1) < 1e-3 for x in v)
    assert json.dumps(v)  # 숫자만
