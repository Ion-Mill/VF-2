"""사내 문서 §절 출처 꼬리표 (UI설계서 6.7, D-03). 원문 출처는 넣지 않는다."""
from __future__ import annotations

import re

from backend.rag.chunker import Chunk, load_corpus


def chunk(doc_id: str, sec: str) -> Chunk | None:
    return next((c for c in load_corpus() if c.doc_id == doc_id and c.section == sec), None)


def evidence(c: Chunk, snippet: str = "") -> dict:
    # doc_no·rev = API명세서 공통 규칙의 출처 칸 이름 {doc_name, doc_no, rev, section} (2026-10-11 P1).
    # 화면이 옮겨 갈 때까지 옛 칸(doc_id·revision)도 둔다. 원문 출처 칸은 없다 (D-03)
    plain = re.sub(r"\s+", " ", re.sub(r"[|#*]", " ", c.text)).strip()
    return {"cite": c.cite, "doc_id": c.doc_id, "doc_name": c.doc_name, "revision": c.revision, "section": c.section,
            "title": c.title, "snippet": snippet or plain[:160], "doc_no": c.doc_id, "rev": c.revision}


def cite(doc_id: str, sec: str) -> dict | None:
    c = chunk(doc_id, sec)
    return evidence(c) if c else None


def parse_refs(text: str) -> list[dict]:
    """'DOC-03 §2.11', 'DOC-03 §1.4 · §2.6' 같은 글에서 출처 꼬리표를 만든다. 없는 절은 버린다."""
    out, doc = [], None
    for m in re.finditer(r"(DOC-0\d)|§(\d+(?:\.\d+)*)", text or ""):
        if m.group(1):
            doc = m.group(1)
        elif doc:
            ev = cite(doc, m.group(2))
            if ev and ev not in out:
                out.append(ev)
    return out
