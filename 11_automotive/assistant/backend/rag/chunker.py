"""사내 문서(용어집 + DOC-01~07, 개정 번호는 문서마다 다름 — 2026-10-07 현행판)를 §절 단위 검색 조각으로 나눈다 (FR-MNT-01-10).

조각 메타데이터 = 문서 번호·문서 이름·개정·절 번호·절 제목·파일 해시. 원문 출처는 넣지 않고,
원문 대응표·원문 판·개정 기록 절은 뺀다. 긴 절은 줄 경계에서 나눈다.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.config import DOCS_DIR, EXPECTED_DOC_FILES
from backend.rag.sanitize import sanitize

# 용어집 §1 "쓰는 규칙"은 문서 작성자용 규칙. DOC-03 §1.2 "쓰는 원문 판"은 원문 문서 이름·장 번호 표라 원문 대응표처럼 뺀다
# (2026-10-11, 문서 보기는 이미 숨김 — doc_view.HIDE_TITLES. 조각 196 → 195)
SKIP_TITLES = ("원문 대응표", "개정 기록", "목차", "쓰는 규칙", "원문 판")
MAX_CHARS = 3500  # 한 절의 표가 둘로 잘리지 않게 (예: DOC-07 §9 "수명 90% → 교체 알림" 행)


class CorpusError(RuntimeError):
    pass


def _split_long(body: str) -> list[str]:
    """MAX_CHARS보다 긴 절은 줄 경계에서 나눈다 (2026-10-11). 글자 수로 자르면 표 줄·낱말이 갈렸다
    (DOC-06 §9.1 "두께·폭 공|차" — 원문 이름 고침으로 글자 수가 1자 줄자 자르는 자리가 밀렸다).
    한 줄이 MAX_CHARS보다 길 때만 글자 수로 자른다."""
    parts, rest = [], body
    while len(rest) > MAX_CHARS:
        cut = rest.rfind("\n", 0, MAX_CHARS + 1)
        if cut <= 0:
            cut = MAX_CHARS
        parts.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    parts.append(rest)
    return parts


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    doc_name: str
    revision: str
    section: str
    title: str
    text: str
    file_hash: str

    @property
    def cite(self) -> str:
        return f"{self.doc_name} {self.doc_id} §{self.section}" if self.doc_id != "GLOSSARY" else f"용어집 §{self.section}"


def normalize_md(raw: str) -> str:
    """마크다운 서식 정리 도구를 거친 파일도 원래 서식과 같은 글로 읽는다 (2026-10-14 `DOC-05` 사건: 편집기가 표 칸 공백을 맞추고(57KB → 115KB)
    밑줄에 `\\`를 붙여 `| 문서 이름 | …` 줄을 못 찾고 앱이 코퍼스를 읽지 못했다). 표 줄의 가운데 공백 여러 칸은 한 칸으로, `\\_`는 `_`로.
    파일 지문(file_hash)은 원본 글자로 재므로 파일이 바뀐 것은 여전히 알 수 있다. 사내 문서 원본은 고치지 않는다."""
    out = []
    for line in raw.replace("\\_", "_").split("\n"):
        if line.lstrip().startswith("|"):
            if re.fullmatch(r"\s*\|[\s:\-|]+\|\s*", line):
                line = re.sub(r"-{3,}", "---", line)   # 표 구분선의 줄 길이도 칸 너비에 맞춰 늘어난다
            line = re.sub(r"(?<=\S)[ \t]{2,}", " ", line)
        out.append(line)
    return "\n".join(out)


def _doc_meta(path: Path, text: str) -> tuple[str, str, str]:
    if path.name.startswith("00_"):
        rev = re.search(r"개정:\s*\**(Rev\.\d+ \([\d-]+\))", text)
        return "GLOSSARY", "용어집", rev.group(1) if rev else "확인 필요"
    doc_id = re.match(r"(DOC-\d{2})", path.name).group(1)
    name = re.search(r"\| 문서 이름 \| (.+?) \|", text).group(1).strip()
    rev = re.search(r"\| 개정 \| \**(Rev\.\d+ \([\d-]+\))", text)
    return doc_id, name, rev.group(1) if rev else "확인 필요"


HEADING = re.compile(r"^(#{2,3}) (\d+(?:\.\d+)*)\.?\s+(.*)$")


def chunk_file(path: Path) -> list[Chunk]:
    raw_file = path.read_text(encoding="utf-8")
    file_hash = hashlib.sha256(raw_file.encode("utf-8")).hexdigest()[:16]
    raw = normalize_md(raw_file)   # 서식만 바뀐 파일도 같은 글로 (지문은 원본 글자로 잼)
    doc_id, doc_name, rev = _doc_meta(path, raw)
    chunks, cur, buf, parent_skip = [], None, [], False

    def flush():
        if cur is None:
            return
        level, sec, title = cur
        if any(t in title for t in SKIP_TITLES) or parent_skip:
            return
        body = sanitize("\n".join(buf))
        if len(re.sub(r"[\s|\-:#]", "", body)) < 20:
            return
        parts = _split_long(body)
        for n, part in enumerate(parts, 1):
            cid = f"{doc_id}:{sec}" + (f":{n}" if len(parts) > 1 else "")
            chunks.append(Chunk(cid, doc_id, doc_name, rev, sec, sanitize(title), part, file_hash))

    for line in raw.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            level, sec, title = len(m.group(1)), m.group(2), m.group(3).strip()
            if level == 2:
                parent_skip = any(t in title for t in SKIP_TITLES)
            cur, buf = (level, sec, title), []
        elif cur is not None:
            buf.append(line)
    flush()
    return chunks


def _load_files(docs_dir: Path) -> tuple[Chunk, ...]:
    if not docs_dir.exists():
        raise CorpusError(f"경로 없음·확인 필요: {docs_dir}")
    files = sorted(p for p in docs_dir.glob("*.md") if p.name.startswith(("00_", "DOC-")))
    if len(files) != EXPECTED_DOC_FILES:
        raise CorpusError(f"사내 문서 파일 수가 {len(files)}개다 (기대 {EXPECTED_DOC_FILES}개) — 색인을 멈춘다")
    out = []
    for f in files:
        out.extend(chunk_file(f))
    return tuple(out)


# 사내 문서를 어디서 읽었나 (DOCS_SOURCE, 2026-10-25): 기본 files = 로컬 파일. db = 백엔드 GET /api/assistant/docs (공용 DB 읽기 전용).
# DB가 안 되면 로컬 파일로 돌아가고 이유(예외 종류 이름만)를 남긴다 — /health가 보여 준다. 프로세스가 시작될 때 한 번만 시도한다(캐시)
_SRC: dict = {"source": "files"}


def corpus_source() -> dict:
    """/health용: {"source": "files"|"db", "fallback": 이유 또는 없음, "revisions": {문서: 개정}} (db일 때만 개정 표시)"""
    return {k: v for k, v in _SRC.items() if k != "glossary"}      # 용어집 글은 /health에 싣지 않는다


def _load_db() -> tuple[Chunk, ...]:
    from backend import config as C
    from backend.rag import db_corpus as D          # 늦게 import — 순환 import를 피한다
    base, key = C.docs_backend()
    payload = D.fetch(base, key)
    chunks = D.build_chunks(payload, EXPECTED_DOC_FILES)
    _SRC.clear()
    # via: 문서를 가져온 백엔드가 운영 데이터와 같은 것인가(main_backend) 문서만 따로 정한 것인가(docs_backend). 주소는 싣지 않는다
    _SRC.update({"source": "db", "via": "docs_backend" if C.docs_backend()[0] != C.docs_backend_main() else "main_backend",
                 "glossary": D.glossary_text(payload),
                 "revisions": {str(d["doc_no"]): D._rev_label(d) for d in payload["docs"]}})
    return chunks


@lru_cache(maxsize=1)
def load_corpus(docs_dir: Path = DOCS_DIR) -> tuple[Chunk, ...]:
    from backend.config import docs_source
    if docs_dir == DOCS_DIR and docs_source() == "db":
        try:
            return _load_db()
        except Exception as e:                       # 안쪽 사정(주소·키·본문)은 싣지 않는다 — 종류 이름만
            _SRC.clear()
            _SRC.update({"source": "files", "fallback": type(e).__name__ + (f": {e}" if isinstance(e, CorpusError) else "")})
    return _load_files(docs_dir)


def glossary_text() -> str:
    """용어집 글 (search.synonyms가 동의어 표를 읽는다): DOCS_SOURCE=db이고 DB에서 읽었으면 DB 조각에서, 아니면 로컬 파일."""
    from backend.config import docs_source
    if docs_source() == "db":
        load_corpus()                                # DB 모드면 여기서 한 번 읽는다 (이미 읽었으면 캐시)
        if _SRC.get("source") == "db":
            return _SRC["glossary"]
    return (DOCS_DIR / "00_용어집.md").read_text(encoding="utf-8")


def section(doc_id: str, sec: str) -> list[Chunk]:
    return [c for c in load_corpus() if c.doc_id == doc_id and (c.section == sec or c.section.startswith(sec + "."))]
