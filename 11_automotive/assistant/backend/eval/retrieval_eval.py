"""검색만 따로 잰다: 정답 §절이 상위 1·5개 안에 드는 비율 (recall@1·@5). 답 문장과 떼어 본다 (현업 평가 방식).

실행: python backend/eval/retrieval_eval.py qa_set.json [qa_holdout_d.json …] [--model bge-m3]
- bm25 / dense / hybrid(RRF) 세 순위를 같은 문항으로 비교한다. 문서 질문(doc·mixed)만 센다.
- dense·hybrid는 임베딩 서버(EMBED_URL)와 pgvector(DATABASE_URL)가 있어야 한다. 없으면 그 칸은 None.
- 결과: backend/eval/history/retrieval_<세트들>_<모델>_<시각>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.rag import dense as D  # noqa: E402
from backend.rag.search import search  # noqa: E402

HERE = Path(__file__).resolve().parent


def hit(chunks, sources, k):
    got = [f"{c.doc_id} §{c.section}" for c in chunks[:k]]
    return any(any(g == s or g.startswith(s + ".") for g in got) for s in sources)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--model", default=None)
    ap.add_argument("--embed-url", default=None)
    ap.add_argument("--store", choices=["pg", "memory"], default="pg",
                    help="memory = DB 없이 메모리에서 같은 코사인 정확 검색 (pgvector 설치 전 모델 비교용)")
    args = ap.parse_args()
    if args.model:
        os.environ["EMBED_MODEL"] = args.model
    if args.embed_url:
        os.environ["EMBED_URL"] = args.embed_url
    if args.store == "memory":
        from backend.rag.vector_store import MemoryStore
        D.use_store(MemoryStore())
    items = []
    for f in args.sets:
        items += [dict(it, set=Path(f).stem) for it in json.loads((HERE / f).read_text(encoding="utf-8"))["items"]
                  if it["type"] in ("doc", "mixed")]
    rows = []
    dense_ok = True
    for it in items:
        bm = [c for _, c in search(it["q"], 15)]
        dn = D.dense_search(it["q"], 15) if dense_ok else None
        if dn is None:
            dense_ok = False
        dv = [c for _, c in dn] if dn else None
        hy = D.rrf(bm, dv) if dv else None
        rows.append({"id": it["id"], "set": it["set"], "q": it["q"], "sources": it["sources"],
                     **{f"{name}@{k}": (hit(r, it["sources"], k) if r is not None else None)
                        for name, r in (("bm25", bm), ("dense", dv), ("hybrid", hy)) for k in (1, 5)},
                     "bm25_top": [f"{c.doc_id} §{c.section}" for c in bm[:3]],
                     "dense_top": [f"{c.doc_id} §{c.section}" for c in dv[:3]] if dv else None})

    def rate(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(100 * sum(vals) / len(vals), 1) if vals else None

    model = os.environ.get("EMBED_MODEL", "bge-m3")
    summary = {"sets": args.sets, "model": model, "store": args.store, "questions": len(rows), "run_at": datetime.now().isoformat(timespec="seconds"),
               **{f"{n}@{k}": rate(f"{n}@{k}") for n in ("bm25", "dense", "hybrid") for k in (1, 5)},
               "dense_error": D.dense_last_error()}
    hist = HERE / "history"
    hist.mkdir(exist_ok=True)
    name = "+".join(Path(s).stem for s in args.sets)
    (hist / f"retrieval_{name}_{model}_{datetime.now():%Y%m%d-%H%M%S}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
