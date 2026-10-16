"""가상 사내 문서(md 원본) → 비서 검색용 사본 + 절 단위 조각 목록.

AI비서_사내문서_입출력형식.md 2.2 규칙을 따른다.
  1. 절(##, ###) 단위로 자르고 문서 이름·번호·개정·절 번호·제목을 붙인다
  2. 표는 자르지 않는다 (절 안에 통째로 들어감)
  3. "원문 대응표" 절은 뺀다
  4. 본문 안의 원문 출처 줄(`| 원문 | ...`)을 뺀다. md 원본은 그대로 둔다
  5. 링크 주소는 지우고 글자만 남긴다
  6. [실제]/[가상] 표시는 남긴다 (콜론 뒤 원문 이름만 지움)
  7. 용어집도 같은 방법으로 넣는다
  8. md를 고치면 이 스크립트를 다시 돌린다 (사본은 손으로 고치지 않는다)

실행: python 비서_시제품/문서조각.py
"""

import json
import re
import sys

from 설정 import DOC_SRC, INDEX_FILE, SEARCH_DIR

HEADING = re.compile(r"^(#{2,3})\s+(.*)$")
SECTION_NO = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
SOURCE_ROW = re.compile(r"^\|\s*원문\s*\|")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
TAG_DETAIL = re.compile(r"\[(실제|참고|가상|제안|선택 필요)[^\]]+\]")   # [실제: …], [가상 도면: …] → [실제]
ARROW_SOURCE = re.compile(r"\s*←[^|]*")                               # 표 칸의 "← 원문 이름"
TABLE_SEP = re.compile(r"^\|\s*:?-{3,}")                                # 표 구분줄 |---| 또는 | ------ |
FILE_PATH = re.compile(r"`[^`]*(?:/|\.(?:pdf|png|jpe?g|html?|xml|csv|txt|json|zip|md))[^`]*`")


def read_meta(path, lines):
    """표지에서 문서 번호·이름·개정을 읽는다."""
    text = "\n".join(lines[:15])
    if path.name.startswith("00_"):
        rev = re.search(r"개정:\s*\*\*(Rev\.\d+)", text)
        return {"doc_no": "GLOSSARY", "doc_name": "용어집", "rev": rev.group(1) if rev else ""}
    cell = lambda key: re.search(rf"^\|\s*{key}\s*\|\s*([^|]+?)\s*\|", text, re.M)
    return {
        "doc_no": cell("문서 번호").group(1),
        "doc_name": cell("문서 이름").group(1),
        "rev": re.search(r"Rev\.\d+", cell("개정").group(1)).group(0),
    }


def clean(line):
    line = LINK.sub(r"\1", line)
    line = TAG_DETAIL.sub(r"[\1]", line)
    line = ARROW_SOURCE.sub(" ", line)
    line = FILE_PATH.sub("", line)
    return line


def build_doc(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = read_meta(path, lines)
    out = [f"# {meta['doc_name']} ({meta['doc_no']}, {meta['rev']}) — 비서 검색용 사본, 원문 출처 뺌", ""]
    chunks, current, skip_level = [], None, None

    def close():
        if current and "".join(current["body"]).strip():
            body = "\n".join(current["body"]).strip()
            body_lines = current["body"]
            preview = [l for i, l in enumerate(body_lines)          # 표 머리줄·구분줄은 요약 카드에서 뺀다
                       if l.strip() and not TABLE_SEP.match(l)
                       and not (i + 1 < len(body_lines) and TABLE_SEP.match(body_lines[i + 1]))][:3]
            chunks.append({**meta, "section": current["section"], "title": current["title"],
                           "file": path.name, "line": current["line"], "text": body,
                           "preview": "\n".join(preview)})

    for raw in lines[1:]:
        m = HEADING.match(raw)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            if skip_level is not None and level > skip_level:
                continue
            skip_level = None
            close()
            current = None
            if "원문 대응표" in title:          # 규칙 3
                skip_level = level
                continue
            num = SECTION_NO.match(title)
            section = f"§{num.group(1)}" if num else title
            title_only = num.group(2) if num else title
            out.append(f"{m.group(1)} [{meta['doc_no']} {section}] {title_only}")
            current = {"section": section, "title": title_only, "line": len(out), "body": []}
            continue
        if skip_level is not None or current is None:
            continue
        if SOURCE_ROW.match(raw):                  # 규칙 4
            continue
        line = clean(raw)
        out.append(line)
        current["body"].append(line)
    close()
    return meta, "\n".join(out) + "\n", chunks


def main():
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    for old in SEARCH_DIR.iterdir():               # 사본은 매번 새로 만든다 (규칙 8)
        old.unlink()
    all_chunks, docs = [], []
    for path in sorted(DOC_SRC.glob("*.md")):
        meta, text, chunks = build_doc(path)
        (SEARCH_DIR / path.name).write_text(text, encoding="utf-8")
        all_chunks += chunks
        docs.append({**meta, "file": path.name, "chunks": len(chunks)})
    with INDEX_FILE.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    for d in docs:
        print(f"{d['doc_no']:9} {d['rev']:7} {d['doc_name']:16} 조각 {d['chunks']}개")
    print(f"합계 {len(all_chunks)}개 → {SEARCH_DIR}")


def load_index():
    """조각 목록을 (doc_no, section) → 조각 사전으로 읽는다. 없으면 먼저 만든다."""
    if not INDEX_FILE.exists():
        main()
    index = {}
    for line in INDEX_FILE.read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        index[(c["doc_no"], c["section"])] = c
    return index


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
