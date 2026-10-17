"""안전 기준서(DOC-05) 점검표 측정 도구 (2026-10-18) — Claude를 부르지 않고, 현장 말 질문 68개가 Claude에게 가는 조각에 정답 절을 담는지 잰다.

왜: "톱 정비 전에 어디를 차단해야 해?"가 정답 절(DOC-05 §3.1)이 검색 68위라 Claude에게 가지 못해 "문서에 없다"고 답했다. 같은 놓침을
문서·코드를 바꿀 때마다 자동으로 발견하려는 점검표다. 구현 전후를 **같은 도구**로 재서 기획·성과 문서에 적는다.

쓰는 법 (assistant 폴더, PYTHONUTF8=1):
  .\\.venv\\Scripts\\python.exe backend\\eval\\safety_recall.py                 # 권장 설정(순수 길 켬, 신호는 기존 길)으로 잰다
  $env:PURE_SAFETY='0'; .\\.venv\\Scripts\\python.exe backend\\eval\\safety_recall.py   # 안전망을 끈 값 (스위치가 없는 옛 코드에서도 돈다)

출력: ① 정답 절이 Claude 조각에 있는 비율(전체 / 실제 순수 길로 가는 질문) ② 놓친 질문 ③ 안전 낱말 발동 비율(발동 판정이 있을 때)
④ 설비 이름 때문에 기존 길로 가는 질문 수. PURE_KEEP_SIGNALS=1이면 신호가 있는 질문은 순수 길이 아니라 기존 길(알람 카드·운영 조회)로 간다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # assistant/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings                      # noqa: E402
from backend.llm import external as EXT                  # noqa: E402
from backend.services import answer as A                 # noqa: E402
from backend.services import pure_external as PURE       # noqa: E402


def apply_recommended_env() -> None:
    """명령으로 돌릴 때만 부른다 (import만으로는 환경을 바꾸지 않는다 — 시험이 이 모듈을 import한다)."""
    # 규칙 해석(parse)은 PARSE_V* 같은 스위치에 따라 결과가 달라진다. .env가 없는 곳(작업 폴더 사본·시험)에서도 같은 값이 나오도록
    # 예시 파일의 권장 값(비밀값이 없는 허용 목록 항목만)을 기본으로 깐다. 이미 정해져 있으면(.env·환경변수) 그대로 둔다.
    _SAFE_KEYS = re.compile(r"^(PARSE_V\d+|FLOW_V\d+|BLOCKS_V\d+|LEAD_V\d+|TERM_V\d+|NUM_MATCH|ROUTE_POLICY|DOC_GATE|SPLIT_Q|RETRIEVAL|LLM_JOBS|PURE_TOPK|PURE_EXPAND|PURE_SAFETY|PURE_PERIOD|PURE_RULE)$")
    for _line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        _m = re.match(r"^([A-Z0-9_]+)=(\S*)\s*$", _line.strip())
        if _m and _SAFE_KEYS.match(_m.group(1)):
            os.environ.setdefault(_m.group(1), _m.group(2))
    for k, v in {"PURE_EXTERNAL": "1", "EXTERNAL_LLM_APP": "1", "LLM_ENABLED": "1", "ASSISTANT_PROVIDER": "claude",
                 "PURE_KEEP_SIGNALS": "1", "PURE_EXPAND": "1"}.items():        # 권장 설정(순수 길 켬, 신호는 기존 길). 이미 정해져 있으면 그대로 둔다
        os.environ.setdefault(k, v)


def load_items() -> list[dict]:
    return json.loads((HERE / "safety_qa.json").read_text(encoding="utf-8"))["items"]


def routes_pure(question: str, s) -> bool:
    """이 설정에서 이 질문이 순수 외부 LLM 길로 가나 (PURE_KEEP_SIGNALS=1이면 설비·알람·운영 신호가 있는 질문은 기존 길)."""
    p = A.parse(question)
    try:
        return A.pure_scope_v19(p, s, question) is not None
    except TypeError:                                    # 질문을 받지 않는 옛 함수 모양
        return A.pure_scope_v19(p, s) is not None


def reached(question: str, doc: str, sec: str, s) -> bool:
    return any(c.doc_id == doc and c.section == sec for _, c in PURE.context(question, s.pure_topk, s))


def measure(s=None, items: list[dict] | None = None) -> dict:
    s = s or settings()
    items = items if items is not None else load_items()
    detect = getattr(PURE, "is_safety", None)            # 발동 판정이 없는 옛 코드에서도 돈다
    rows = []
    for it in items:
        q, doc, sec = it["q"], it["doc"], it["sec"]
        rows.append({"q": q, "sec": sec, "pure": routes_pure(q, s), "reached": reached(q, doc, sec, s),
                     "triggered": (detect(q) if detect else None)})
    pure = [r for r in rows if r["pure"]]
    return {"total": len(rows), "reached": sum(r["reached"] for r in rows), "misses": [r for r in rows if not r["reached"]],
            "pure_total": len(pure), "pure_reached": sum(r["reached"] for r in pure), "pure_misses": [r for r in pure if not r["reached"]],
            "old_route": [r for r in rows if not r["pure"]],
            "triggered": None if detect is None else sum(bool(r["triggered"]) for r in rows),
            "pure_triggered": None if detect is None else sum(bool(r["triggered"]) for r in pure), "rows": rows}


def main() -> None:
    apply_recommended_env()
    with EXT.external_request("claude"):                  # claude_app은 요청 단위다 — 외부 Claude를 고른 요청 안에서 설정을 읽어야 순수 길 판정이 맞다
        s = settings()
        m = measure(s)
    pct = lambda a, b: f"{a}/{b} = {a * 100 // max(b, 1)}%"
    print(f"설정: PURE_SAFETY={getattr(s, 'pure_safety', '(스위치 없음)')} PURE_EXPAND={s.pure_expand} PURE_KEEP_SIGNALS={s.pure_keep_signals} TOPK={s.pure_topk}")
    print(f"[①] 정답 절이 Claude 조각에 있는 질문: 전체 {pct(m['reached'], m['total'])} | 실제 순수 길로 가는 질문 {pct(m['pure_reached'], m['pure_total'])}")
    for r in m["misses"]:
        print(f"      놓침 §{r['sec']:<4} {r['q']}" + ("" if r["pure"] else "   (기존 길로 감)"))
    if m["triggered"] is not None:
        print(f"[③] 안전 낱말 발동: 전체 {pct(m['triggered'], m['total'])} | 순수 길 질문 {pct(m['pure_triggered'], m['pure_total'])}")
    print(f"[④] 설비·운영 신호 때문에 기존 길로 가는 질문: {len(m['old_route'])}개")


if __name__ == "__main__":
    main()
