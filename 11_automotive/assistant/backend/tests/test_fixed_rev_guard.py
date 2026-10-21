"""고정 서식의 문서 개정 표시가 사내 문서와 어긋나지 않게 막는다 (2026-10-21, 하드코딩 점검).

안전 고정 서식의 출처 줄("출처: DOC-05 안전 작업 기준서 Rev.3 …")은 코드 상수(`safety/templates.py`)이고, 화면 쪽 `generated.ts`에도 같은 글자가 복사돼 있다.
DOC-05가 개정(Rev.4 …)되면 이 글자가 옛 개정을 가리키게 된다 — 블록 본문은 시험이 DOC-05 §7과 대조하지만 개정 번호는 따로 막지 않았다.
이 시험은 코드·생성 파일에 적힌 "DOC-05 … Rev.N"이 사내 문서 표지의 개정과 같은지 본다. 어긋나면 `safety/templates.py`와 `frontend/tools/build_data.py`를 돌려 맞춘다
(사내 문서 수정 규칙: 개정 표시를 글자로 쓰는 곳은 저장소 전체에서 찾아 같이 맞춘다).
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.rag.chunker import load_corpus

REV = re.compile(r"DOC-05 안전 작업 기준서 Rev\.(\d+)")
ROOT = Path(__file__).resolve().parents[3]          # 11_automotive


def doc05_rev() -> str:
    c = next(c for c in load_corpus() if c.doc_id == "DOC-05")
    m = re.match(r"Rev\.(\d+)", c.revision)
    assert m, c.revision
    return m.group(1)


def test_templates_rev_matches_doc05():
    src = (ROOT / "assistant" / "backend" / "safety" / "templates.py").read_text(encoding="utf-8")
    found = REV.findall(src)
    assert found, "templates.py에 DOC-05 개정 표시가 없다 — 이 시험을 고쳐야 한다"
    assert set(found) == {doc05_rev()}, f"templates.py의 개정 {sorted(set(found))} ≠ DOC-05 표지 Rev.{doc05_rev()} — safety/templates.py를 맞춘다"


def test_frontend_generated_rev_matches_doc05():
    gen = ROOT / "frontend" / "src" / "shell" / "generated.ts"
    if not gen.exists():
        return
    found = REV.findall(gen.read_text(encoding="utf-8"))
    assert found, "generated.ts에 DOC-05 개정 표시가 없다 — 이 시험을 고쳐야 한다"
    assert set(found) == {doc05_rev()}, f"generated.ts의 개정 {sorted(set(found))} ≠ DOC-05 표지 Rev.{doc05_rev()} — frontend/tools/build_data.py로 다시 만든다"
