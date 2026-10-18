"""SCR-24 사내 문서 보기용 본문 (UI설계서 SCR-24, 2026-10-07 사용자 결정: 원문 출처는 가리고 표시).

UI설계서 2.7은 "팝업은 사내 문서 본문을 그대로 보인다"지만, 규칙 D-03("Haas 원문 출처는 화면 어디에도 표시하지 않는다")이
더 엄격하므로 화면용 본문에서는 원문 대응표·원문 판 절과 본문 속 원문 문서번호·Rev·URL·쪽·KOSHA 지침 번호를 뺀다.
원문 문서 이름("Haas 알람 목록" 등)은 "제조사 …"로 바꿔 보인다 (sanitize.HAAS_DOC, 2026-10-11 — 검색 조각과 같은 규칙).
사내 문서 원본 파일은 고치지 않는다 (사람의 근거 추적용).
"""
from __future__ import annotations

import re
from functools import lru_cache

from backend.config import DOCS_DIR
from backend.rag.chunker import HEADING, _doc_meta, load_corpus, normalize_md
from backend.rag.sanitize import FORBIDDEN, sanitize

HIDE_TITLES = ("원문 대응표", "원문 판")
HIDDEN_NOTE = "원문 출처는 화면에 표시하지 않습니다 — 사내 문서 원본 파일에서 확인합니다 (2026-10-06 회의 D-03)"
PRE = [
    (re.compile(r"^\s*(?:\*\*)?(?:원문|출처)(?:\*\*)?\s*:.*$|^\s*\*\*근거:\*\*.*$", re.M), ""),  # "**원문:** …", "출처: …", "**근거:** …" 줄
    (re.compile(r"KOSHA\s*(?:GUIDE\s*)?B-M-\d+-\d{4}"), "KOSHA 지침"),       # 지침 번호만 뺀다 (뒤의 "6장"은 남김)
    # "(Haas …)" 괄호를 통째로 지우던 줄은 뺐다 (2026-10-11): 부품번호 "(Haas P/N 58-1391 …)"·서비스 "(Haas HFO 등)"·
    # 버튼 "(Haas: [POWER OFF])"까지 지웠다. 괄호 속 원문 이름은 sanitize의 HAAS_DOC가 지운다 (검색 조각과 같은 규칙)
    (re.compile(r"`?[^\s`|]*__\d{8}__[^\s`|]*`?"), ""),                      # 수집 파일 이름 조각
    (re.compile(r"\[(실제|참고|가상|제안):[^\]]*\]"), r"[\1]"),
]
LINK = re.compile(r"\[([^\]]+)\]\((?!#)[^)]*\)")  # 다른 파일 링크는 글자만 남김


def _files() -> dict[str, object]:
    out = {}
    for p in sorted(DOCS_DIR.glob("*.md")):
        if p.name.startswith(("00_", "DOC-")):
            doc_id, _, _ = _doc_meta(p, normalize_md(p.read_text(encoding="utf-8")))   # 서식만 바뀐 파일도 읽는다 (2026-10-14 DOC-05)
            out[doc_id] = p
    return out


def clean(text: str) -> str:
    for pat, rep in PRE:
        text = pat.sub(rep, text)
    text = LINK.sub(r"\1", text)
    text = sanitize(text)
    return re.sub(r"\n{3,}", "\n\n", text)


@lru_cache(maxsize=16)
def doc_body(doc_id: str) -> dict | None:
    load_corpus()  # 파일 수 점검 (8개가 아니면 CorpusError)
    path = _files().get(doc_id.upper())
    if path is None:
        return None
    raw = normalize_md(path.read_text(encoding="utf-8"))   # 검색 조각과 같은 글로 읽는다 (2026-10-14 DOC-05 서식 정리)
    did, name, rev = _doc_meta(path, raw)
    approved = re.search(r"승인\s*(?:\|)?\s*:?\s*([^|\n/]+)", raw)
    sections, cur, buf, hidden, skip_parent = [], None, [], 0, False

    def flush():
        nonlocal hidden
        if cur is None:
            return
        level, sec, title = cur
        if skip_parent or any(t in title for t in HIDE_TITLES):
            hidden += 1
            sections.append({"section": sec, "title": clean(title), "level": level, "text": HIDDEN_NOTE, "hidden": True})
            return
        sections.append({"section": sec, "title": clean(title), "level": level, "text": clean("\n".join(buf)), "hidden": False})

    for line in raw.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            cur = (len(m.group(1)), m.group(2), m.group(3).strip())
            if cur[0] == 2:
                skip_parent = any(t in cur[2] for t in HIDE_TITLES)
            buf = []
        elif cur is not None:
            buf.append(line)
    flush()
    body = {"doc_id": did, "doc_name": name, "revision": rev, "approved": (approved.group(1).strip(" *") if approved else "확인 필요"),
            "label": "가상 사내 문서", "sections": sections, "hidden_sections": hidden, "hidden_note": HIDDEN_NOTE}
    leaks = [s["section"] for s in sections if FORBIDDEN.search(s["text"] + s["title"])]
    if leaks:  # 원문 출처가 남으면 그 절은 내보내지 않는다
        for s in sections:
            if s["section"] in leaks:
                s.update(text=HIDDEN_NOTE, hidden=True)
    return body


def doc_list() -> list[dict]:
    out = []
    for doc_id in _files():
        b = doc_body(doc_id)
        out.append({k: b[k] for k in ("doc_id", "doc_name", "revision", "approved", "label")} | {"sections": len(b["sections"])})
    return out
