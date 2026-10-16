"""분류(표지판) 시험 (2026-10-10 계획 1·3단계). qa_route.json으로 분류 정책을 비교한다.

실행: python backend/eval/route_eval.py [--split dev|pool|all] [--policies rules_v1,rules_v2,llm_primary,llm_guarded] [--show]
- rules_v1 = 예전 낱말 규칙 (PARSE_V2=0), rules_v2 = 보강한 규칙 (PARSE_V2=1),
  llm_primary·llm_guarded = 보강한 규칙을 힌트로 LLM이 분류 (ROUTE_POLICY, LLM_JOBS에 route).
- 보고: kind 혼동표, 의도별 P/R/F1, 설비·기간·교대 정확도(정답이 ops·mixed인 문항), 완전 일치율, none 정밀도,
  LLM 출력 형식 오류율, 지연.
- 정책 고르기 규칙(사전등록 4절): dev에서 none 정밀도가 규칙 이상(규칙이 none을 내지 않으면 ≥ 0.9), 5문항 이상인 의도의
  F1이 규칙(rules_v2)보다 0.05 넘게 떨어지지 않음, 형식 오류 ≤ 5%를 모두 지키는 정책 중 완전 일치율이 가장 높은 것.
결과: backend/eval/history/route_<split>_<시각>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.services import answer as A  # noqa: E402
from backend.services import routing as R  # noqa: E402

KINDS = ["doc", "ops", "mixed", "none", "action"]
POLICY_ENV = {
    "rules_v1": {"LLM_ENABLED": "0", "PARSE_V2": "0", "ROUTE_POLICY": "rescue"},
    "rules_v2": {"LLM_ENABLED": "0", "PARSE_V2": "1", "ROUTE_POLICY": "rescue"},
    "llm_primary": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "ROUTE_POLICY": "llm_primary"},
    "llm_guarded": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded"},
    "rules_v3": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v3": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "ROUTE_POLICY": "llm_guarded"},
    # 3차 (2026-10-10, 봉인 시험 E3): 규칙 보강 3차
    "rules_v4": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v4": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "PARSE_V4": "1", "ROUTE_POLICY": "llm_guarded"},
    # 4차 (2026-10-11, 봉인 시험 E4): 규칙 보강 4차
    "rules_v5": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "PARSE_V5": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v5": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "PARSE_V4": "1", "PARSE_V5": "1", "ROUTE_POLICY": "llm_guarded"},
    # 5차 (2026-10-11, 봉인 시험 E5): 규칙 보강 5차
    "rules_v6": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1",
                 "ROUTE_POLICY": "rescue"},
    "llm_guarded_v6": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "ROUTE_POLICY": "llm_guarded"},
    # 6차 (2026-10-12, 봉인 시험 E6): 규칙 보강 6차 + 이어 묻기 (분류만 보므로 이어 묻기는 앞 답 없이)
    "rules_v7": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1",
                 "PARSE_V7": "1", "FOLLOWUP": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v7": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
                       "ROUTE_POLICY": "llm_guarded"},
    # 7차 (2026-10-12, 봉인 시험 E7): 안전·결함 고침 + 이어 묻기가 실제로 일하게
    "rules_v8": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1",
                 "PARSE_V7": "1", "FOLLOWUP": "1", "PARSE_V8": "1", "FOLLOWUP_V2": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v8": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
                       "PARSE_V8": "1", "FOLLOWUP_V2": "1", "ROUTE_POLICY": "llm_guarded"},
    # 8차 (2026-10-12, 봉인 시험 E8): 규칙 보강 8차 + 흐름 바꾸기 + 줄 목록 칸 2판
    "rules_v9": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1",
                 "PARSE_V7": "1", "FOLLOWUP": "1", "PARSE_V8": "1", "FOLLOWUP_V2": "1",
                 "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v9": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                       "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
                       "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1",
                       "ROUTE_POLICY": "llm_guarded"},
    # 9차 (2026-10-13, 봉인 시험 E9): 띄어쓰기 + 섞인 알람 질문·알람 짧게 + 줄 목록 칸 3판
    "rules_v10": {"LLM_ENABLED": "0", "PARSE_V2": "1", "PARSE_V3": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1",
                  "PARSE_V7": "1", "FOLLOWUP": "1", "PARSE_V8": "1", "FOLLOWUP_V2": "1",
                  "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1",
                  "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1", "ROUTE_POLICY": "rescue"},
    "llm_guarded_v10": {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "PARSE_V2": "1", "PARSE_V3": "1", "SPLIT_Q": "1",
                        "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
                        "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1",
                        "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1", "ROUTE_POLICY": "llm_guarded"},
}


def predict(q: str) -> tuple[dict, float, dict | None]:
    """지금 환경 변수의 정책으로 질문 하나를 분류한다. answer()와 같은 앞단(안전장치 → 알람 → 분류)을 쓴다."""
    s = settings()
    t0 = time.perf_counter()
    if A.human_only(q):
        return {"kind": "action", "intents": [], "equipment": [], "start": None, "end": None, "shift": None}, 0.0, None
    p = A.parse(q)
    p["raw"] = q
    if A.use_llm_route(q, p, s):
        r = R.decide_route(q, p, s)
    else:
        r = R.rule_route(p, q)
    ms = (time.perf_counter() - t0) * 1000
    return {"kind": r.kind, "intents": sorted(r.intents) if r.kind in ("ops", "mixed") else [], "equipment": sorted(r.equipment),
            "start": r.start.isoformat() if isinstance(r.start, date) else None,
            "end": r.end.isoformat() if isinstance(r.end, date) else None, "shift": r.shift}, ms, r.trace


def grade(gold: dict, got: dict) -> dict:
    ops = gold["kind"] in ("ops", "mixed")
    out = {"kind": got["kind"] == gold["kind"]}
    if ops:
        out["intents"] = sorted(got["intents"]) == sorted(gold["intents"])
        out["equipment"] = sorted(got["equipment"]) == sorted(gold["equipment"])
        out["period"] = (got["start"], got["end"]) == (gold["start"], gold["end"])
        out["shift"] = got["shift"] == gold["shift"]
    out["exact"] = all(out.values())
    return out


def prf(pairs: list[tuple[set, set]], label: str) -> dict:
    tp = sum(1 for g, p in pairs if label in g and label in p)
    fp = sum(1 for g, p in pairs if label not in g and label in p)
    fn = sum(1 for g, p in pairs if label in g and label not in p)
    pr = tp / (tp + fp) if tp + fp else None
    rc = tp / (tp + fn) if tp + fn else None
    f1 = 2 * pr * rc / (pr + rc) if pr and rc else (0.0 if (tp + fp) or (tp + fn) else None)
    return {"n_gold": tp + fn, "p": round(pr, 3) if pr is not None else None, "r": round(rc, 3) if rc is not None else None,
            "f1": round(f1, 3) if f1 is not None else None}


def run_policy(items: list[dict], policy: str) -> dict:
    keep = {k: os.environ.get(k) for k in ("LLM_ENABLED", "LLM_JOBS", "PARSE_V2", "ROUTE_POLICY", "NUM_MATCH", "DOC_GATE", "RETRIEVAL",
                                           "PARSE_V3", "SPLIT_Q", "PARSE_V4", "CAND_ORDER", "LLM_CACHE_PROMPT", "PARSE_V5",
                                           "PARSE_V6", "PARSE_V7", "FOLLOWUP", "PARSE_V8", "FOLLOWUP_V2",
                                           "PARSE_V9", "FLOW_V9", "BLOCKS_V2", "PARSE_V10", "FLOW_V10", "BLOCKS_V3",
                                           "DOC_WRITE", "PARSE_V11", "LEAD_V12", "TERM_V13",
                                           "SAFE_WRITE_CARD", "SAFE_WRITE_DOC", "SAFE_WRITE_PROC", "SAFE_WRITE_WORDS",
                                           "LLM_PROVIDER", "WRITE_SHOTS", "WRITE_TITLES", "WRITE_RULES_V17", "ANSWER_GATE_V17",
                                           "EXTERNAL_LLM_APP", "EXTERNAL_PROC_LIMIT", "THINK_APP", "TABLE_FILL_V18", "STEP_LOG")}
    os.environ.update({"NUM_MATCH": "token", "DOC_GATE": "lexical", "RETRIEVAL": "bm25", "LLM_JOBS": "write",
                       "PARSE_V3": "0", "SPLIT_Q": "0", "PARSE_V4": "0", "CAND_ORDER": "rank", "LLM_CACHE_PROMPT": "1",
                       "PARSE_V5": "0", "PARSE_V6": "0", "PARSE_V7": "0", "FOLLOWUP": "0", "PARSE_V8": "0", "FOLLOWUP_V2": "0",
                       "PARSE_V9": "0", "FLOW_V9": "0", "BLOCKS_V2": "0", "PARSE_V10": "0", "FLOW_V10": "0", "BLOCKS_V3": "0",
                       "DOC_WRITE": "0", "PARSE_V11": "0", "LEAD_V12": "0", "TERM_V13": "0",
                       "SAFE_WRITE_CARD": "0", "SAFE_WRITE_DOC": "0", "SAFE_WRITE_PROC": "0", "SAFE_WRITE_WORDS": "0",
                       "LLM_PROVIDER": "local", "WRITE_SHOTS": "0", "WRITE_TITLES": "0", "WRITE_RULES_V17": "0", "ANSWER_GATE_V17": "0",
                       "EXTERNAL_LLM_APP": "0", "EXTERNAL_PROC_LIMIT": "8", "THINK_APP": "0", "TABLE_FILL_V18": "0", "STEP_LOG": "0", **POLICY_ENV[policy]})
    try:
        rows, conf, pairs, lat, bad, calls = [], Counter(), [], [], 0, 0
        for it in items:
            got, ms, tr = predict(it["q"])
            if tr:
                calls += 1
                lat.append(tr.get("ms") or ms)
                if tr.get("reason") and not tr.get("used"):
                    bad += tr["reason"].startswith(("형식", "값 오류", "LLM 오류"))
            g = grade(it, got)
            conf[(it["kind"], got["kind"])] += 1
            pairs.append((set(it["intents"]), set(got["intents"])))
            rows.append({"id": it["id"], "q": it["q"], "gold": {k: it[k] for k in ("kind", "intents", "equipment", "start", "end", "shift")},
                         "got": got, **g, "trace": tr})
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    n = len(rows)
    ops_rows = [r for r in rows if r["gold"]["kind"] in ("ops", "mixed")]
    none_pred = [r for r in rows if r["got"]["kind"] == "none"]
    intents = sorted({i for it in items for i in it["intents"]})
    lat.sort()
    return {
        "policy": policy, "n": n,
        "exact": round(100 * sum(r["exact"] for r in rows) / n, 1),
        "kind_acc": round(100 * sum(r["kind"] for r in rows) / n, 1),
        "ops_fields": {k: round(100 * sum(r[k] for r in ops_rows) / len(ops_rows), 1) for k in ("intents", "equipment", "period", "shift")} if ops_rows else {},
        "none_precision": round(sum(1 for r in none_pred if r["gold"]["kind"] == "none") / len(none_pred), 3) if none_pred else None,
        "none_predicted": len(none_pred),
        "intent_prf": {i: prf(pairs, i) for i in intents},
        "confusion": {f"{g}->{p}": c for (g, p), c in sorted(conf.items())},
        "llm_calls": calls, "format_error_rate": round(100 * bad / calls, 1) if calls else None,
        "latency_ms_p50": round(lat[len(lat) // 2]) if lat else None,
        "latency_ms_p95": round(lat[min(len(lat) - 1, int(0.95 * (len(lat) - 1) + 0.5))]) if lat else None,
        "_rows": rows,
    }


def choose(results: dict) -> tuple[str | None, list[str]]:
    """사전등록 4절의 정책 고르기 규칙."""
    base = results.get("rules_v2")
    notes, ok = [], []
    for pol in ("llm_primary", "llm_guarded"):
        r = results.get(pol)
        if not r or not base:
            continue
        why = []
        if base["none_predicted"]:
            if r["none_precision"] is not None and r["none_precision"] < base["none_precision"]:
                why.append(f"none 정밀도 {r['none_precision']} < 규칙 {base['none_precision']}")
        elif r["none_precision"] is not None and r["none_precision"] < 0.9:
            why.append(f"none 정밀도 {r['none_precision']} < 0.9")
        for i, b in base["intent_prf"].items():
            if b["n_gold"] >= 5 and b["f1"] is not None and (r["intent_prf"][i]["f1"] or 0) < b["f1"] - 0.05:
                why.append(f"{i} F1 {r['intent_prf'][i]['f1']} < 규칙 {b['f1']} − 0.05")
        if r["format_error_rate"] is not None and r["format_error_rate"] > 5:
            why.append(f"형식 오류 {r['format_error_rate']}% > 5%")
        if why:
            notes.append(f"{pol}: 탈락 — " + "; ".join(why))
        else:
            ok.append(pol)
            notes.append(f"{pol}: 통과 (완전 일치 {r['exact']}%)")
    # 완전 일치율이 같으면 더 보수적인 llm_guarded (LLM이 none이어도 근거 있는 규칙 의도를 지킨다) — 2026-10-10 dev에서 동률
    best = max(ok, key=lambda p: (results[p]["exact"], p == "llm_guarded")) if ok else None
    return best, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "pool", "all"])
    ap.add_argument("--policies", default="rules_v1,rules_v2,llm_primary,llm_guarded")
    ap.add_argument("--show", action="store_true", help="틀린 문항을 보인다 (보이는 조정 세트라 괜찮음)")
    a = ap.parse_args()
    data = json.loads((HERE / "qa_route.json").read_text(encoding="utf-8"))
    items = [it for it in data["items"] if a.split == "all" or it["split"] == a.split]
    results = {p: run_policy(items, p) for p in a.policies.split(",") if p}
    best, notes = choose(results)
    stamp = datetime.now()
    out = {"split": a.split, "run_at": stamp.isoformat(timespec="seconds"), "chosen": best, "notes": notes, "results": results}
    hist = HERE / "history"
    hist.mkdir(exist_ok=True)
    (hist / f"route_{a.split}_{stamp:%Y%m%d-%H%M%S}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for p, r in results.items():
        print(json.dumps({k: v for k, v in r.items() if k != "_rows"}, ensure_ascii=False))
        if a.show:
            for row in r["_rows"]:
                if not row["exact"]:
                    print("   X", row["id"], row["q"], "| 정답", row["gold"], "| 받음", row["got"])
    print("고른 정책:", best)
    for n in notes:
        print(" ", n)


if __name__ == "__main__":
    main()
