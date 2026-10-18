"""문서별 놓침 측정 도구 (2026-10-18) — Claude를 부르지 않고, 현장 말 질문이 Claude에게 가는 조각에 정답 절을 담는지 문서별로 잰다.

왜: 안전 기준서(DOC-05)에서 "톱 정비 전에 어디를 차단해야 해?"가 정답 절이 검색 68위라 Claude에게 가지 못해 "문서에 없다"고 답했다
(`safety_recall.py`). 다른 문서에도 같은 모양의 놓침이 있는지 같은 방법으로 먼저 재 본다. **측정만 한다** — 비서 동작·검색·문서를 바꾸지 않고,
적중률로 통과·실패를 가르지도 않는다(문서가 바뀌면 값이 달라진다). 기획: 261003_창민/다른문서_놓침_측정_기획_20261018.md.

점검표: `eval/doc_qa/<문서>.json` (`q`·`doc`·`sec`, 정답으로 같이 인정하는 절은 `also`). 정답 키는 절 번호("3.6") 또는, 3,500자 넘어 쪼개진 절은 조각 키("3.6:2"). DOC-05는 옛 점검표 `eval/safety_qa.json`을 그대로 쓴다.
봉인한 보류 질문은 저장소 밖 파일을 `--table`로 줘서 처방을 확정한 뒤 한 번만 돌린다.

쓰는 법 (assistant 폴더, PYTHONUTF8=1):
  .\\.venv\\Scripts\\python.exe backend\\eval\\doc_recall.py --doc DOC-04
  .\\.venv\\Scripts\\python.exe backend\\eval\\doc_recall.py --doc DOC-04 --table 보류질문.json     # 봉인 보류 질문 (한 번만)
  .\\.venv\\Scripts\\python.exe backend\\eval\\doc_recall.py --doc DOC-04 --json 결과.json          # 줄마다 순위·원인을 파일로 남긴다
  $env:PURE_SAFETY='0'; ...                                                                       # 안전망을 끈 값

출력: ① 정답 절이 Claude 조각에 있는 비율(전체 / 실제 순수 길로 가는 질문) ② 검색 순위 띠(1-8 · 9-20 · 21-50 · 51+ · 점수 0) ③ 놓친 질문(순위·원인·대신 위에 있던 조각)
④ 설비 이름 때문에 기존 길로 가는 질문 수 ⑤ 안전 낱말 발동 비율. "Claude 조각"은 비서가 실제로 보내는 조각이다(상위 PURE_TOPK + 확장 + 안전 문서 통째).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # assistant/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings                      # noqa: E402
from backend.eval import safety_recall as SR             # noqa: E402
from backend.llm import external as EXT                  # noqa: E402
from backend.rag import search as RS                     # noqa: E402
from backend.services import pure_external as PURE       # noqa: E402

QA_DIR = HERE / "doc_qa"
LEGACY = {"DOC-05": HERE / "safety_qa.json"}             # 옛 점검표는 그 자리에 두고 새 도구가 그대로 읽는다
BANDS = ("1-8", "9-20", "21-50", "51+", "점수 0")
CAUSES = ("점수 0", "2글자 조각만 겹침", "경쟁 조각이 더 높음")
apply_recommended_env = SR.apply_recommended_env         # 명령으로 돌릴 때만 부른다 (import만으로는 환경을 바꾸지 않는다)


# ------------------------------------------------------------------ 점검표
def available() -> list[str]:
    return sorted({p.stem for p in QA_DIR.glob("DOC-*.json")} | set(LEGACY))


def table_path(doc: str) -> Path:
    p = QA_DIR / f"{doc}.json"
    if p.exists():
        return p
    if doc in LEGACY:
        return LEGACY[doc]
    raise FileNotFoundError(f"{doc} 점검표가 없다 (eval/doc_qa/{doc}.json)")


def load_table(path: Path | str) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["items"]


def load_items(doc: str) -> list[dict]:
    return load_table(table_path(doc))


def accepted(item: dict) -> set[str]:
    """정답으로 인정하는 키: 정답 키 + 같이 인정하는 키(also). 키는 절 번호("3.6" = 그 절의 모든 조각) 또는 조각 키("3.6:2" = 쪼개진 절의 그 조각만)."""
    return {item["sec"], *item.get("also", [])}


def key_of(chunk) -> str:
    """조각 키: 절 번호. 3,500자 넘어 쪼개진 절은 뒤에 순번("3.6:1"·"3.6:2") — chunk_id에서 문서 번호를 뺀 것."""
    return chunk.chunk_id.split(":", 1)[1]


def is_target(chunk, doc: str, keys: set[str]) -> bool:
    """이 조각이 정답인가: 같은 문서이고, 절 키에 들거나(쪼개진 절이면 모든 조각) 조각 키에 든다."""
    return chunk.doc_id == doc and (chunk.section in keys or key_of(chunk) in keys)


# ------------------------------------------------------------------ 순위·길·원인
def band(rank: int | None) -> str:
    if rank is None:
        return "점수 0"
    return "1-8" if rank <= 8 else "9-20" if rank <= 20 else "21-50" if rank <= 50 else "51+"


def _full_ranking(question: str):
    idx = RS.index()
    return idx.search(question, len(idx.chunks))


def rank_of(question: str, doc: str, secs: set[str]) -> int | None:
    """낱말 검색(BM25 + 용어집 동의어) 전체 순위에서 정답 절 중 가장 높은 조각의 순위 (1부터). 점수가 0이라 순위에 없으면 None."""
    for i, (_, c) in enumerate(_full_ranking(question), 1):
        if is_target(c, doc, secs):
            return i
    return None


def reached(question: str, doc: str, secs: set[str], s) -> bool:
    """비서가 실제로 Claude에게 보내는 조각(상위 k + 확장 + 안전 문서)에 정답 절이 있나."""
    return any(is_target(c, doc, secs) for _, c in PURE.context(question, s.pure_topk, s))


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[0-9a-z][0-9a-z.\-]*|[가-힣]+", text.lower()) if w not in RS.STOP]


def overlap(question: str, doc: str, secs: set[str]) -> tuple[list[str], bool]:
    """질문과 정답 조각의 겹침: (질문 낱말 중 정답 조각 낱말에 통째로 있는 것, 통째 낱말은 없고 두 글자 조각만 겹치는가). 동의어 확장 뒤의 질문으로 본다."""
    cands = [c for c in RS.index().chunks if is_target(c, doc, secs)]
    have: set[str] = set()
    for c in cands:
        have |= set(RS.tokens(f"{c.title} {c.title} {c.doc_name} {c.text}"))
    q = RS.expand(question)
    whole = [w for w in dict.fromkeys(_words(q)) if w in have]
    bigram = any(t in have for w in _words(q) if re.match(r"[가-힣]", w) for t in RS.tokens(w) if len(t) == 2 and t != w)
    return whole, bool(bigram)


def cause(rank: int | None, shared: list[str], shares_bigram: bool) -> str:
    """놓친 까닭 (결정적 규칙): 겹치는 낱말이 없으면 점수 0 / 통째 낱말은 안 겹치고 두 글자 조각만 겹치면 활용형·조사·합성어 차이 / 통째 낱말이 겹치는데도 놓쳤으면 경쟁 조각."""
    if shared:
        return "경쟁 조각이 더 높음"
    if shares_bigram:
        return "2글자 조각만 겹침"
    return "점수 0"


def measure(doc: str, s=None, items: list[dict] | None = None) -> dict:
    s = s or settings()
    items = items if items is not None else load_items(doc)
    detect = getattr(PURE, "is_safety", None)
    rows = []
    for it in items:
        q, secs = it["q"], accepted(it)
        full = _full_ranking(q)
        rank = next((i for i, (_, c) in enumerate(full, 1) if is_target(c, doc, secs)), None)
        hit = reached(q, doc, secs, s)
        shared, bigram = overlap(q, doc, secs)
        rows.append({"q": q, "sec": it["sec"], "also": sorted(secs - {it["sec"]}), "pure": SR.routes_pure(q, s), "reached": hit, "rank": rank, "band": band(rank),
                     "top1": full[0][1].chunk_id if full else "", "shared": shared, "cause": cause(rank, shared, bigram),
                     "triggered": (detect(q) if detect else None)})
    pure = [r for r in rows if r["pure"]]
    return {"doc": doc, "total": len(rows), "reached": sum(r["reached"] for r in rows), "misses": [r for r in rows if not r["reached"]],
            "pure_total": len(pure), "pure_reached": sum(r["reached"] for r in pure), "pure_misses": [r for r in pure if not r["reached"]],
            "old_route": [r for r in rows if not r["pure"]],
            "bands": dict(Counter(r["band"] for r in rows)), "miss_bands": dict(Counter(r["band"] for r in rows if not r["reached"])),
            "causes": dict(Counter(r["cause"] for r in rows if not r["reached"])),
            "triggered": None if detect is None else sum(bool(r["triggered"]) for r in rows),
            "pure_triggered": None if detect is None else sum(bool(r["triggered"]) for r in pure), "rows": rows}


# ------------------------------------------------------------------ 명령
def _pct(a: int, b: int) -> str:
    return f"{a}/{b} = {a * 100 // max(b, 1)}%"


def report(m: dict, s, label: str) -> None:
    print(f"문서: {m['doc']} ({label})  설정: PURE_SAFETY={getattr(s, 'pure_safety', '(스위치 없음)')} PURE_PERIOD={getattr(s, 'pure_period', '(스위치 없음)')} PURE_RULE={getattr(s, 'pure_rule', '(스위치 없음)')} PURE_FAULT={getattr(s, 'pure_fault', '(스위치 없음)')} PURE_FAULTDOC={getattr(s, 'pure_faultdoc', '(스위치 없음)')} PURE_EXPAND={s.pure_expand} PURE_KEEP_SIGNALS={s.pure_keep_signals} TOPK={s.pure_topk}")
    print(f"[①] 정답 절이 Claude 조각에 있는 질문: 전체 {_pct(m['reached'], m['total'])} | 실제 순수 길로 가는 질문 {_pct(m['pure_reached'], m['pure_total'])}")
    order = {b: m["bands"].get(b, 0) for b in BANDS}
    print("[②] 낱말 검색 순위 띠 (안전 문서 통째 추가 전): " + " | ".join(f"{b} {n}" for b, n in order.items()))
    if m["misses"]:
        print("     놓친 질문의 띠: " + " | ".join(f"{b} {m['miss_bands'].get(b, 0)}" for b in BANDS) + "   원인: " + " | ".join(f"{c} {m['causes'].get(c, 0)}" for c in CAUSES))
    for r in m["misses"]:
        print(f"[③] 놓침 §{r['sec']:<4} {r['band']:<5} {('%d위' % r['rank']) if r['rank'] else '순위 없음':<6} {r['cause']:<10} 대신 위: {r['top1']:<10} "
              f"겹친 낱말 {','.join(r['shared']) or '-'}{'' if r['pure'] else '  (기존 길)'}  | {r['q']}")
    print(f"[④] 설비·운영 신호 때문에 기존 길로 가는 질문: {len(m['old_route'])}개")
    if m["triggered"] is not None:
        print(f"[⑤] 안전 낱말 발동: 전체 {_pct(m['triggered'], m['total'])} | 순수 길 질문 {_pct(m['pure_triggered'], m['pure_total'])}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="문서별 놓침 측정 (Claude 호출 없음)")
    ap.add_argument("--doc", required=True, help="문서 번호 (예: DOC-04)")
    ap.add_argument("--table", help="점검표 대신 쓸 파일 (봉인 보류 질문)")
    ap.add_argument("--json", help="줄마다 순위·원인을 이 파일로 남긴다")
    a = ap.parse_args(argv)
    apply_recommended_env()
    with EXT.external_request("claude"):                  # claude_app은 요청 단위다 — 외부 Claude를 고른 요청 안에서 설정을 읽어야 순수 길 판정이 맞다
        s = settings()
        m = measure(a.doc, s, load_table(a.table) if a.table else None)
    report(m, s, "보류 질문" if a.table else "점검표")
    if a.json:
        Path(a.json).write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"줄별 결과: {a.json}")


if __name__ == "__main__":
    main()
