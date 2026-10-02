"""공통 경로와 도구. 원본 문서(docs/, data/)는 읽기만 한다."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = ROOT / "data"
OUT = ROOT / "analysis" / "outputs"
TEXT = ROOT / "analysis" / "text"          # 00_extract_text.py 가 만든 PDF 글자 추출본
OUT.mkdir(parents=True, exist_ok=True)


def pdf_pages(rel):
    """docs/ 아래 PDF 의 쪽별 글자 목록. 00_extract_text.py 를 먼저 돌려야 한다."""
    p = TEXT / (str(rel).replace("\\", "/").replace("/", "__") + ".json")
    return json.loads(p.read_text(encoding="utf-8"))


def html_text(path):
    t = Path(path).read_text(encoding="utf-8", errors="ignore")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def find_all(pages, pattern, width=160, flags=re.I):
    """쪽 목록에서 정규식을 찾아 (쪽 번호, 앞뒤 글) 목록으로 돌려준다."""
    hits = []
    for i, t in enumerate(pages):
        flat = " ".join(t.split())
        for m in re.finditer(pattern, flat, flags):
            hits.append((i + 1, flat[max(0, m.start() - width): m.end() + width]))
    return hits


def save_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
