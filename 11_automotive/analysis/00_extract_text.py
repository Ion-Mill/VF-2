"""docs/ 아래 모든 PDF 의 글자를 쪽별로 뽑아 analysis/text/ 에 저장한다.
필요: pip install pypdf cryptography"""
import json
import sys

from pypdf import PdfReader

from common import DOCS, TEXT

TEXT.mkdir(parents=True, exist_ok=True)
summary = []
for pdf in sorted(DOCS.rglob("*.pdf")):
    rel = pdf.relative_to(DOCS).as_posix()
    out = TEXT / (rel.replace("/", "__") + ".json")
    if out.exists():
        pages = json.loads(out.read_text(encoding="utf-8"))
    else:
        try:
            r = PdfReader(str(pdf))
            if r.is_encrypted:
                r.decrypt("")
            pages = []
            for p in r.pages:
                try:
                    pages.append(p.extract_text() or "")
                except Exception:
                    pages.append("")
        except Exception as e:
            print("FAIL", rel, str(e)[:80], file=sys.stderr)
            continue
        out.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    chars = sum(len(p) for p in pages)
    summary.append({"file": rel, "pages": len(pages), "chars": chars, "mb": round(pdf.stat().st_size / 1e6, 1)})
    print(f"{len(pages):5d}쪽 {chars:9d}자  {rel}")

(TEXT / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print("PDF", len(summary), "개, 총", sum(s["pages"] for s in summary), "쪽")
