"""가상 사내 문서(가상사내문서/*.md) → doc_chunk (AI 비서 검색용 조각, 논리 ERD 5.G.6).

쓰는 법:
    python tools/load_docs.py <11_automotive 폴더> --psql "psql -d mom" [--dry-run] [--no-sync-rev]

하는 일:
 1. internal_doc(기준 정보 8행 — 생성기 masters/internal_doc.csv)의 file_ref 로 문서 파일을 찾는다.
 2. 문서 표지의 개정(Rev.N (날짜))을 읽는다. internal_doc 의 current_rev 와 다르면 문서 파일을 따른다
    (current_rev·rev_date 를 고치고 알려 준다 — 최신 문서가 기준. --no-sync-rev 면 고치지 않고 멈춤).
 3. 제목(##·###)마다 조각 1개: section = "§2.1" (번호 없는 제목은 제목 글자), chunk_text = "문서 이름 > 위 제목 > 제목" + 본문.
    · "원문 대응표" 절은 만들지 않는다 (D-03 — 비서는 원문 출처를 인용하지 않음)
    · 표지(첫 ## 앞)는 만들지 않는다. 본문이 4,000자를 넘으면 빈 줄에서 나눈다 (같은 section, 순서대로)
    나누는 방법·임베딩은 [선택 필요: 기술 회의] — 이것은 "절 단위" 기본안이다. embedding 칸은 db/later 에서 더한다.
 4. 그 문서의 이전 조각을 지우고 새로 넣는다 (개정되면 다시 만든다, FR-MNT-01-10). 한 트랜잭션.
 5. 시연 기준점(SIM-03)이 있으면 다시 만든다 — 기준점에 조각이 없으면 "처음으로" 때 조각이 지워지므로.
    시연 도중에는 --no-snapshot (그때 상태가 기준점이 되지 않게)
표준 라이브러리 + psql만 쓴다.
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile

MAX_CHARS = 4000
HEAD_RE = re.compile(r"^(#{2,4})\s+(.*)$")
NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
REV_RE = re.compile(r"Rev\.(\d+)\s*\(?(\d{4}-\d{2}-\d{2})?")
SKIP_TITLES = ("원문 대응표",)


def psql_rows(psql, sql):
    out = subprocess.run(shlex.split(psql) + ["-X", "-AtF", "\t", "-c", sql], check=True, capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    return [line.split("\t") for line in out.splitlines() if line]


def cover_rev(text: str):
    """표지(첫 ## 앞)의 개정: ('Rev.11', '2026-10-14')"""
    head = text.split("\n## ", 1)[0]
    for line in head.splitlines():
        if "개정" in line:
            m = REV_RE.search(line)
            if m:
                return f"Rev.{m.group(1)}", m.group(2)
    return None, None


def sections(text: str, doc_name: str):
    """제목 트리를 따라 (section, chunk_text) 목록. 위 제목 경로를 본문 앞에 붙인다"""
    out, parents, cur_title, cur_level, body = [], [], None, 0, []

    def emit(path_titles, title, content):
        content = content.strip()
        if not content or any(s in t for t in path_titles + [title] for s in SKIP_TITLES):
            return
        m = NUM_RE.match(title)
        section = ("§" + m.group(1)) if m else title
        path = " > ".join([doc_name] + path_titles + [title])
        parts, buf = [], ""
        for para in re.split(r"\n\s*\n", content):
            if buf and len(buf) + len(para) + 2 > MAX_CHARS:
                parts.append(buf)
                buf = para
            else:
                buf = f"{buf}\n\n{para}" if buf else para
        parts.append(buf)
        for i, p in enumerate(parts, 1):
            tag = f" ({i}/{len(parts)})" if len(parts) > 1 else ""
            out.append((section[:20], f"{path}{tag}\n\n{p}"))

    for line in text.splitlines():
        m = HEAD_RE.match(line)
        if m:
            if cur_title is not None:
                emit([t for _, t in parents], cur_title, "\n".join(body))
                parents = [(lv, t) for lv, t in parents if lv < cur_level] + [(cur_level, cur_title)]
            level = len(m.group(1))
            parents = [(lv, t) for lv, t in parents if lv < level]
            cur_title, cur_level, body = m.group(2).strip(), level, []
            continue
        if cur_title is not None:
            body.append(line)
    if cur_title is not None:
        emit([t for _, t in parents], cur_title, "\n".join(body))
    return out


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base_dir", help="11_automotive 폴더 (internal_doc.file_ref 의 기준)")
    ap.add_argument("--psql", default="psql -d mom")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-sync-rev", action="store_true", help="문서 개정이 internal_doc 과 다르면 고치지 않고 멈춤")
    ap.add_argument("--no-snapshot", action="store_true", help="시연 기준점을 다시 만들지 않음")
    a = ap.parse_args()

    docs = psql_rows(a.psql, "SELECT doc_no, doc_name, current_rev, file_ref FROM internal_doc ORDER BY doc_no")
    if not docs:
        sys.exit("internal_doc 이 비어 있음 — 먼저 기준 정보(생성기 masters)를 넣는다 (tools/load_generated.py)")
    lines = ["\\set ON_ERROR_STOP 1", "BEGIN;"]
    total, problems = 0, []
    for doc_no, doc_name, rev, file_ref in docs:
        path = os.path.join(a.base_dir, file_ref)
        if not os.path.exists(path):
            problems.append(f"{doc_no}: 파일 없음 {path}")
            continue
        text = open(path, encoding="utf-8-sig").read()
        file_rev, file_date = cover_rev(text)
        if file_rev and file_rev != rev:
            msg = f"{doc_no}: internal_doc {rev} ≠ 문서 표지 {file_rev} ({file_date}) → 문서를 따름"
            if a.no_sync_rev:
                problems.append(msg)
                continue
            print("  " + msg)
            lines.append(f"UPDATE internal_doc SET current_rev = {q(file_rev)}"
                         + (f", rev_date = DATE {q(file_date)}" if file_date else "") + f" WHERE doc_no = {q(doc_no)};")
            rev = file_rev
        chunks = sections(text, f"{doc_name} ({doc_no})")
        total += len(chunks)
        print(f"  {doc_no} {rev}: 조각 {len(chunks)}개")
        lines.append(f"DELETE FROM doc_chunk WHERE doc_no = {q(doc_no)};")
        for section, body in chunks:
            lines.append(f"INSERT INTO doc_chunk (doc_no, doc_rev, section, chunk_text, built_at) "
                         f"VALUES ({q(doc_no)}, {q(rev)}, {q(section)}, {q(body)}, now());")
    if problems:
        print("멈춤:\n  " + "\n  ".join(problems))
        sys.exit(2)
    if not a.no_snapshot:
        # 기준점에서 문서 표만 바꾼다 — 전부 다시 찍으면 적재 뒤 붙인 실시간 기록(--realtime)까지 기준점에 들어감 (2026-10-25)
        lines.append("SELECT fn_demo_snapshot_refresh(ARRAY['internal_doc', 'doc_chunk']);")
    lines.append("COMMIT;")
    if a.dry_run:
        print(f"(dry-run) 조각 {total}개")
        return
    # newline="\n": Windows에서 \n이 \r\n으로 바뀌어 조각 본문에 들어가지 않게 (어느 OS에서 넣어도 같은 조각)
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8", newline="\n") as tf:
        tf.write("\n".join(lines) + "\n")
    r = subprocess.run(shlex.split(a.psql) + ["-X", "-q", "-f", tf.name], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    os.unlink(tf.name)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        sys.exit("넣기 실패 — 되돌림")
    print(f"사내 문서 조각 {total}개 넣음")


if __name__ == "__main__":
    main()
