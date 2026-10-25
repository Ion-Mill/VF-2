"""사내 문서를 공용 DB에서 읽기 (DOCS_SOURCE=db, 2026-10-25).

비서는 DB에 직접 붙지 않는다 — 백엔드(8020)의 읽기 전용 `GET /api/assistant/docs`(서비스 키)로 현행 개정의 문서 목록과
조각(doc_chunk)을 한 번 받아, **지금 로컬 파일로 만드는 조각(`chunker.Chunk`)과 같은 모양**으로 다시 만든다.
DB 조각은 4,000자·이동 경로 첫 줄·개정 기록/목차 포함이라 그대로 쓰면 검색·답이 달라진다. 그래서:
  1. 절(문서 번호 + 절 번호)마다 조각을 합치고 첫 줄(`문서 (DOC-01) > 2. 제목 > 2.1 제목 (1/3)`)에서 제목을 뽑는다
  2. 건너뛸 제목(`chunker.SKIP_TITLES`)이 이동 경로에 있으면 뺀다 — 로컬 chunker의 "제목에 있거나 위 ## 제목에 있으면 뺀다"와 같다
  3. 표 서식 정리(`normalize_md`) → `sanitize` → 3,500자 기준 `_split_long`로 다시 나눈다 (chunker.chunk_file의 flush와 같은 순서)
읽기만 한다. 접속 주소·키·본문은 오류 문장에 싣지 않는다 (호출한 쪽이 예외 종류만 기록한다).
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request

from backend.rag.chunker import SKIP_TITLES, Chunk, CorpusError, _split_long, normalize_md
from backend.rag.sanitize import sanitize

TIMEOUT_S = 20.0
_PART = re.compile(r"\s*\(\d+/\d+\)\s*$")
_NUM = re.compile(r"^§?(\d+(?:\.\d+)*)\.?\s+(.*)$")
_SEC = re.compile(r"^\d+(?:\.\d+)*$")


def fetch(base_url: str, key: str, timeout: float = TIMEOUT_S) -> dict:
    """GET {base}/api/assistant/docs — 실패는 CorpusError(종류 이름만)."""
    if not base_url or not key:
        raise CorpusError("MOM_BACKEND_URL·MOM_ASSISTANT_KEY 설정 없음")
    req = urllib.request.Request(base_url.rstrip("/") + "/api/assistant/docs", method="GET", headers={"X-Service-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310 (설정한 내부 주소만)
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise CorpusError(f"HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise CorpusError(type(e).__name__) from None
    if not isinstance(data, dict) or not isinstance(data.get("docs"), list) or not isinstance(data.get("chunks"), list):
        raise CorpusError("응답 형식이 틀림")
    return data


def _rev_label(doc: dict) -> str:
    rev, day = str(doc.get("current_rev") or "").strip(), str(doc.get("rev_date") or "").strip()[:10]
    return f"{rev} ({day})" if rev and day else (rev or "확인 필요")


def _crumbs(chunk_text: str) -> list[str]:
    head = (chunk_text or "").split("\n", 1)[0]
    return [x.strip() for x in head.split(" > ")]


def _body(chunk_text: str) -> str:
    return (chunk_text or "").split("\n", 1)[1] if "\n" in (chunk_text or "") else ""


def build_chunks(payload: dict, expected_docs: int = 8) -> tuple[Chunk, ...]:
    docs = {str(d["doc_no"]): d for d in payload["docs"]}
    if len(docs) != expected_docs:
        raise CorpusError(f"DB의 사내 문서가 {len(docs)}개다 (기대 {expected_docs}개)")
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in payload["chunks"]:                       # 서버가 (문서, chunk_id) 순으로 준다 — 절 안의 순서가 그대로 쓰인다
        doc_no, sec = str(c["doc_no"]), str(c["section"]).lstrip("§")
        if doc_no in docs and _SEC.match(sec):        # 번호 없는 제목은 로컬 chunker도 조각으로 만들지 않는다
            groups.setdefault((doc_no, sec), []).append(c)
    out: list[Chunk] = []
    for (doc_no, sec), parts in groups.items():
        crumbs = _crumbs(parts[0]["chunk_text"])
        titles = [_PART.sub("", x) for x in crumbs[1:]]
        if any(t_skip in t for t in titles for t_skip in SKIP_TITLES):
            continue
        last = titles[-1] if titles else ""
        m = _NUM.match(last)
        title = m.group(2).strip() if m else last
        joined = normalize_md("\n\n".join(_body(p["chunk_text"]).strip("\n") for p in parts))
        body = sanitize(joined)
        if len(re.sub(r"[\s|\-:#]", "", body)) < 20:
            continue
        doc = docs[doc_no]
        digest = hashlib.sha256(("\n".join(p["chunk_text"] for p in parts)).encode("utf-8")).hexdigest()[:16]
        pieces = _split_long(body)
        for n, piece in enumerate(pieces, 1):
            cid = f"{doc_no}:{sec}" + (f":{n}" if len(pieces) > 1 else "")
            out.append(Chunk(cid, doc_no, str(doc["doc_name"]).strip(), _rev_label(doc), sec, sanitize(title), piece, digest))
    return tuple(out)


def glossary_text(payload: dict) -> str:
    """용어집 동의어 표를 읽는 글: 용어집(GLOSSARY) 조각의 본문을 빈 줄로 이어 붙인다 (표 줄은 원문 그대로, sanitize 안 함)."""
    parts = [_body(c["chunk_text"]).strip("\n") for c in payload["chunks"] if str(c["doc_no"]) == "GLOSSARY"]
    return normalize_md("\n\n".join(parts))
