"""같은 세트를 두 방식으로 돌린 기록을 문항끼리 짝지어 비교한다 (2026-10-10 계획 1단계).

실행: python backend/eval/compare_runs.py <기록 A.json> <기록 B.json> [--blind]
- 둘 다 맞음 / A만 맞음 / B만 맞음 / 둘 다 틀림, 정확도 차이(B−A) ± 짝 표준오차, McNemar 정확 p(양쪽)
- 지어낸 답(none·insufficient에 답함) 수, 지연 p95를 함께 보인다.
- 새 시험은 난이도가 달라 다른 세트의 점수와 바로 비교하지 않는다 — 같은 세트 안의 짝 차이만 본다(Anthropic 2024-11-19).
--blind: 숫자만 출력한다(문항 번호·질문 글을 내지 않음).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"summary": d["summary"], "by_id": {r["id"]: r for r in d["results"]}}


def mcnemar_exact(b: int, c: int) -> float:
    """불일치 쌍 b, c에 대한 양쪽 정확 이항 검정 p."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(a: dict, b: dict, allow_unknown_data: bool = False, require_same_runtime: bool = False) -> dict:
    if a["summary"].get("set_sha256") and b["summary"].get("set_sha256") and a["summary"]["set_sha256"] != b["summary"]["set_sha256"]:
        raise SystemExit("세트가 다르다 (set_sha256 불일치) — 같은 세트끼리만 짝지어 비교한다")
    # 가상 데이터가 다르면 운영 질문의 정답이 달라진다 (2026-10-10 데이터 다시 만듦). 지문이 없는 옛 기록은 거부하고,
    # --allow-unknown-data를 줄 때만 "알 수 없음"으로 비교한다
    da, db = a["summary"].get("data_sha256"), b["summary"].get("data_sha256")
    if da and db and da != db:
        raise SystemExit("가상 데이터가 다르다 (data_sha256 불일치) — 같은 데이터로 돌린 기록끼리만 비교한다")
    if not (da and db) and not allow_unknown_data:
        raise SystemExit("데이터 지문(data_sha256)이 없는 기록이 있다 — 옛 기록을 비교하려면 --allow-unknown-data")
    data_same = True if da and db else "알 수 없음 (옛 기록에 데이터 지문 없음 — 2026-10-10 전 기록)"
    # 섞어 찾기 기록끼리는 뜻 검색 저장소(memory·pg)가 같아야 한다 — 색인이 달라 후보가 달라진다 (2026-10-11, root-cause-guards 10절).
    # 한쪽이 낱말 검색(bm25)이면 저장소를 쓰지 않으므로 비교해도 된다
    ea, eb = a["summary"].get("env") or {}, b["summary"].get("env") or {}
    if ea.get("RETRIEVAL") == "hybrid" and eb.get("RETRIEVAL") == "hybrid" and a["summary"].get("store") != b["summary"].get("store"):
        raise SystemExit("뜻 검색 저장소가 다르다 (store 불일치) — 섞어 찾기 기록은 같은 저장소(memory·pg)끼리만 비교한다")
    if require_same_runtime:  # 흔들림 짝: 같은 코드·같은 설정이어야 바뀐 문항을 흔들림으로 볼 수 있다
        for key in ("runtime_sha256", "assets_sha256", "env"):
            if not a["summary"].get(key) or a["summary"].get(key) != b["summary"].get(key):
                raise SystemExit(f"흔들림 짝이 아니다 ({key}가 없거나 다름)")
    ids = sorted(set(a["by_id"]) & set(b["by_id"]))
    both = only_a = only_b = neither = 0
    diffs = []
    changed = []
    for i in ids:
        ca, cb = bool(a["by_id"][i]["correct"]), bool(b["by_id"][i]["correct"])
        both += ca and cb
        neither += (not ca) and (not cb)
        only_a += ca and not cb
        only_b += cb and not ca
        diffs.append(int(cb) - int(ca))
        if ca != cb:
            changed.append((i, "O→X" if ca else "X→O", a["by_id"][i].get("q", "")))
    n = len(ids)
    mean = sum(diffs) / n if n else 0.0
    sd = (sum((d - mean) ** 2 for d in diffs) / (n - 1)) ** 0.5 if n > 1 else 0.0
    fab = lambda r: sum(1 for x in r["by_id"].values() if x.get("fabricated"))  # noqa: E731
    return {
        "n": n, "A": a["summary"].get("mode"), "B": b["summary"].get("mode"),
        "acc_A": round(100 * (both + only_a) / n, 1) if n else None, "acc_B": round(100 * (both + only_b) / n, 1) if n else None,
        "both": both, "only_A": only_a, "only_B": only_b, "neither": neither,
        "diff_B_minus_A": round(100 * mean, 1), "paired_se": round(100 * sd / n ** 0.5, 1) if n > 1 else None,
        "mcnemar_p": round(mcnemar_exact(only_a, only_b), 4),
        "fabricated_A": fab(a), "fabricated_B": fab(b),
        # B에서만 지어낸 답 (A에서는 거부했던 문항) — E3 안전 기준 S1 "후보에서만 지어낸 답 0"
        "fabricated_only_B": sum(1 for i in ids if b["by_id"][i].get("fabricated") and not a["by_id"][i].get("fabricated")),
        "answered_wrong_A": a["summary"].get("answered_wrong"), "answered_wrong_B": b["summary"].get("answered_wrong"),
        "p95_A": a["summary"].get("latency_ms_p95"), "p95_B": b["summary"].get("latency_ms_p95"),
        "data_same": data_same,
        "_changed": changed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--allow-unknown-data", action="store_true", help="데이터 지문이 없는 옛 기록(2026-10-10 전)도 비교한다")
    ap.add_argument("--require-same-runtime", action="store_true", help="흔들림 짝: 코드·자산·설정이 같아야 한다")
    args = ap.parse_args()
    r = compare(load(args.a), load(args.b), allow_unknown_data=args.allow_unknown_data, require_same_runtime=args.require_same_runtime)
    changed = r.pop("_changed")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if not args.blind:
        for i, how, q in changed:
            print(" ", i, how, q)


if __name__ == "__main__":
    main()
