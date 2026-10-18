"""평가 세트 검사 (2026-10-10 계획 1단계). 봉인 시험 E를 만드는 작성자가 0 오류가 될 때까지 쓴다.

실행: python backend/eval/validate_set.py <세트 경로> [--quiet] [--quota doc=35,ops=20,...]
- 형식: id 중복 없음, 종류, 질문, 문서 문항의 출처·필수 낱말, 운영 문항의 정답 계산, 문맥·역할 칸
- 출처 절이 사내 문서(검색 조각)에 실제로 있는지, 필수 낱말 묶음마다 하나 이상이 인용한 절 본문에 그대로 있는지
- 세트 안 중복과 이미 본 세트와의 비슷한 문항(글자 2개 묶음 자카드 ≥ 0.6)
--quiet: 숫자와 오류 코드·문항 번호만 출력한다(구현자는 이것만 본다 — 질문·답 글을 출력하지 않음).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.rag.chunker import load_corpus  # noqa: E402

TYPES = {"doc", "ops", "mixed", "none", "insufficient", "guard", "followup"}  # followup: 이어 묻기 (2026-10-12)
FOLLOW_EXPECT = {"rewrite", "abstain", "refuse"}
ROLES = {"OPR", "MNT", "SUP", "MGR"}
SCREENS = {"SCR-07", "SCR-09", "SCR-10", "SCR-24"}
SEEN_SETS = ["qa_set.json", "qa_holdout.json", "qa_holdout_b.json", "qa_holdout_c.json", "qa_holdout_d.json",
             "qa_holdout_e.json", "qa_holdout_e2.json", "qa_holdout_e3.json", "qa_holdout_e4.json", "qa_holdout_e5.json",
             "qa_holdout_e6.json", "qa_holdout_e7.json", "qa_holdout_e8.json", "qa_holdout_e9.json", "qa_holdout_cmp30.json",
             "qa_route.json", "qa_tune_f.json", "qa_followup.json"]   # E8: 2026-10-13 판정 뒤 공개, E9: 2026-10-13 9차 판정 뒤 공개, CMP30: 2026-10-14 Qwen↔Claude 비교 판단 뒤 공개
# E·E2는 2026-10-10, E3·E4는 2026-10-11, E5·E6·E7은 2026-10-12 판단 뒤 공개 (본 세트). qa_followup은 이어 묻기 조정 세트 (2026-10-12)
SRC = re.compile(r"^(GLOSSARY|DOC-0[1-7]) §(\d+(?:\.\d+)*)$")


def bigrams(q: str) -> set[str]:
    t = re.sub(r"\s+", "", q.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def section_text(doc_id: str, sec: str) -> str:
    return "\n".join(c.title + "\n" + c.text for c in load_corpus()
                     if c.doc_id == doc_id and (c.section == sec or c.section.startswith(sec + ".")))


def key_text(it: dict) -> str:
    """겹침 검사에 쓰는 글: 이어 묻기 문항은 뒷 질문("방금 거 쉽게")이 서로 비슷하므로 앞 질문으로 본다 (2026-10-12)."""
    p = it.get("prev")
    return p.get("q", "") if it.get("type") == "followup" and isinstance(p, dict) else it.get("q", "")


def check(path: Path, quota: dict[str, int]) -> tuple[list[tuple[str, str, str]], dict]:
    from run_eval import expected  # 운영 정답 계산 (CSV에서 따로 계산)
    errs: list[tuple[str, str, str]] = []  # (오류 코드, 문항 번호, 자세한 내용 — quiet에서는 숨김)
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return [("E00", "-", "items 목록이 없다")], {}
    ids = Counter(it.get("id") for it in items)
    for i, n in ids.items():
        if n > 1:
            errs.append(("E01", str(i), "id 중복"))
    for it in items:
        iid = str(it.get("id"))
        t = it.get("type")
        if t not in TYPES:
            errs.append(("E02", iid, f"종류 {t}"))
            continue
        if not isinstance(it.get("q"), str) or len(it["q"].strip()) < 4:
            errs.append(("E03", iid, "질문이 비었거나 너무 짧다"))
        if "role" in it and it["role"] not in ROLES:
            errs.append(("E04", iid, f"역할 {it['role']}"))
        ctx = it.get("context")
        if ctx is not None:
            if not isinstance(ctx, dict) or (ctx.get("screen") and ctx["screen"] not in SCREENS):
                errs.append(("E05", iid, f"문맥 {ctx}"))
        if t == "followup":  # 이어 묻기: 앞 질문(prev)과 기대(expect)가 있어야 한다
            p = it.get("prev")
            if not isinstance(p, dict) or not isinstance(p.get("q"), str) or len(p["q"].strip()) < 4:
                errs.append(("E06", iid, "앞 질문(prev.q)이 없거나 너무 짧다"))
            elif ("role" in p and p["role"] not in ROLES) or (p.get("context") is not None and (
                    not isinstance(p["context"], dict) or (p["context"].get("screen") and p["context"]["screen"] not in SCREENS))):
                errs.append(("E06", iid, "앞 질문의 역할·문맥"))
            if it.get("expect") not in FOLLOW_EXPECT:
                errs.append(("E07", iid, f"기대 {it.get('expect')}"))
            # 운영 답을 이어 묻는 문항(출처 없음)은 필수 낱말(운영 값)만 둔다 — 값은 앞 답과 같은 조회에서 나온다
            if it.get("expect") == "rewrite" and not it.get("sources") and not it.get("must"):
                errs.append(("E13", iid, "필수 낱말 없음"))
        if t in ("doc", "mixed") or (t == "followup" and it.get("expect") == "rewrite" and it.get("sources")):
            srcs = it.get("sources") or []
            must = it.get("must") or []
            if not srcs:
                errs.append(("E10", iid, "출처 없음"))
            texts = []
            for s in srcs:
                m = SRC.match(s)
                if not m:
                    errs.append(("E11", iid, f"출처 꼴 {s}"))
                    continue
                body = section_text(m.group(1), m.group(2))
                if not body:
                    errs.append(("E12", iid, f"사내 문서에 없는 절 {s}"))
                texts.append(body)
            if not must and not it.get("keywords"):
                errs.append(("E13", iid, "필수 낱말 없음"))
            joined = "\n".join(texts)
            for g in must:
                if not isinstance(g, list) or not g or not any(isinstance(a, str) and a and a in joined for a in g):
                    errs.append(("E14", iid, f"필수 낱말 묶음 {g}이 인용 절 본문에 없다"))
            for k in it.get("keywords", []):
                if k not in joined:
                    errs.append(("E14", iid, f"필수 낱말 {k}이 인용 절 본문에 없다"))
        if t in ("ops", "mixed"):
            try:
                exp = expected(it["check"], it.get("args", {}))
                if not exp or not all(isinstance(e, str) and e for e in exp):
                    errs.append(("E20", iid, f"운영 정답이 비었다 {it.get('check')}"))
            except Exception as e:  # noqa: BLE001
                errs.append(("E21", iid, f"운영 정답 계산 실패 {type(e).__name__}: {e}"))
        if (t in ("none", "insufficient", "guard") or (t == "followup" and it.get("expect") in ("abstain", "refuse"))) \
                and (it.get("sources") or it.get("must")):
            errs.append(("E30", iid, "거부·안내 문항에 출처·필수 낱말이 있다"))
    # 세트 안 중복 · 이미 본 세트와 비슷한 문항
    grams = [(str(it.get("id")), bigrams(key_text(it))) for it in items]
    for a in range(len(grams)):
        for b in range(a + 1, len(grams)):
            if jaccard(grams[a][1], grams[b][1]) >= 0.8:
                errs.append(("E40", f"{grams[a][0]}~{grams[b][0]}", "세트 안 거의 같은 문항"))
    here = Path(__file__).resolve().parent
    for name in SEEN_SETS:
        f = here / name
        if not f.exists() or f.resolve() == path.resolve():
            continue
        for old in json.loads(f.read_text(encoding="utf-8")).get("items", []):
            og = bigrams(key_text(old))
            for iid, g in grams:
                if jaccard(g, og) >= 0.6:
                    errs.append(("E41", iid, f"이미 본 세트({name})와 비슷함"))
    counts = dict(Counter(it.get("type") for it in items))
    counts["context"] = sum(1 for it in items if it.get("context"))
    for t, n in quota.items():
        if counts.get(t, 0) < n:
            errs.append(("E50", t, f"수량 부족 {counts.get(t, 0)} < {n}"))
    return errs, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--quota", default="")
    a = ap.parse_args()
    quota = {k: int(v) for k, v in (x.split("=") for x in a.quota.split(",") if x)}
    errs, counts = check(Path(a.path), quota)
    print("수량:", json.dumps(counts, ensure_ascii=False))
    print("오류:", len(errs))
    for code, iid, detail in errs:
        print(f"  {code} {iid}" if a.quiet else f"  {code} {iid} {detail}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
