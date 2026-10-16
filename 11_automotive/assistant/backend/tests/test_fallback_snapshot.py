"""LLM을 끈 상태의 답이 바뀌지 않았는지 본다 (LLM·의미 검색을 붙여도 끄면 지금 동작 그대로여야 한다 — 되돌리기 보장).

질문은 이미 본 평가 세트(조정용 48 + 예전 검증 22·18 + 봉인 시험 E 100·E2 100 — 둘 다 2026-10-10 판단 뒤 공개)만 쓴다.
기본 문장 쪽 규칙을 일부러 바꿨으면 스냅숏을 다시 만든다 (모든 스위치를 기본값으로 둔다 — .env가 LLM을 켜 두었어도):
  python -m backend.tests.test_fallback_snapshot
"""
import json
from pathlib import Path

from backend.services.answer import answer

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots" / "fallback_answers.json"
SETS = ("qa_set.json", "qa_holdout.json", "qa_holdout_b.json", "qa_holdout_e.json", "qa_holdout_e2.json",
        "qa_holdout_e3.json", "qa_holdout_e4.json", "qa_holdout_e5.json", "qa_holdout_e6.json",
        "qa_holdout_e7.json", "qa_holdout_e8.json", "qa_holdout_e9.json",
        "qa_holdout_cmp30.json")  # E3·E4: 2026-10-11, E5·E6·E7: 2026-10-12, E8·E9: 2026-10-13, CMP30: 2026-10-14 공개 뒤 추가


def _questions():
    out = []
    for s in SETS:
        # 이어 묻기 문항(2026-10-12)은 앞 질문만 넣는다 — 뒷 질문("방금 거 쉽게")은 홀로 물으면 뜻이 없고 글이 겹친다
        for it in json.loads((HERE.parent / "eval" / s).read_text(encoding="utf-8"))["items"]:
            q = it["prev"]["q"] if it.get("type") == "followup" else it["q"]
            if q not in out:
                out.append(q)
    return out


def _shape(a):
    return {"status": a["status"], "conclusion": a["conclusion"], "steps": a["steps"], "related": a["related"],
            "caution": a["caution"], "cites": [e["cite"] for e in a["evidence"]],
            "data": [{k: d[k] for k in ("tool", "range")} for d in a["current_data"]]}


def test_answers_with_llm_off_match_snapshot():
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    qs = _questions()
    assert set(snap) == set(qs), "질문 목록이 바뀌었다 — 스냅숏을 다시 만든다"
    diff = [q for q in qs if _shape(answer(q, "SUP")) != snap[q]]
    assert not diff, diff[:5]


if __name__ == "__main__":
    import os
    os.environ.update({"LLM_ENABLED": "0", "LLM_JOBS": "write", "RETRIEVAL": "bm25", "NUM_MATCH": "token", "PARSE_V2": "0",
                       "ROUTE_POLICY": "rescue", "DOC_GATE": "lexical", "PARSE_V3": "0", "SPLIT_Q": "0",
                       "PARSE_V4": "0", "CAND_ORDER": "rank", "LLM_CACHE_PROMPT": "1",
                       "PARSE_V5": "0", "PARSE_V6": "0",
                       "PARSE_V7": "0", "FOLLOWUP": "0",
                       "PARSE_V8": "0", "FOLLOWUP_V2": "0",
                       "PARSE_V9": "0", "FLOW_V9": "0", "BLOCKS_V2": "0",
                       "PARSE_V10": "0", "FLOW_V10": "0", "BLOCKS_V3": "0", "DOC_WRITE": "0", "PARSE_V11": "0", "LEAD_V12": "0", "TERM_V13": "0",
                       "SAFE_WRITE_CARD": "0", "SAFE_WRITE_DOC": "0", "SAFE_WRITE_PROC": "0", "SAFE_WRITE_WORDS": "0",
                       "LLM_PROVIDER": "local", "WRITE_SHOTS": "0", "WRITE_TITLES": "0", "WRITE_RULES_V17": "0", "ANSWER_GATE_V17": "0",
                       "EXTERNAL_LLM_APP": "0", "EXTERNAL_PROC_LIMIT": "8", "THINK_APP": "0", "TABLE_FILL_V18": "0", "STEP_LOG": "0"})  # conftest와 같은 기본스위치 (4차 PARSE_V5·5차 PARSE_V6 2026-10-11, 6차 PARSE_V7·FOLLOWUP·7차 PARSE_V8·FOLLOWUP_V2·8차 PARSE_V9·FLOW_V9·BLOCKS_V2 2026-10-12, 9차 PARSE_V10·FLOW_V10·BLOCKS_V3 2026-10-13 추가)
    # (PARSE_V3·SPLIT_Q도 꺼야 한다 — .env가 켜 두면 스냅숏이 새 동작을 담는다. 2026-10-10 step5 적용 때 빠진 것을 찾아 넣음)
    SNAP.parent.mkdir(exist_ok=True)
    SNAP.write_text(json.dumps({q: _shape(answer(q, "SUP")) for q in _questions()}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("스냅숏", SNAP, len(_questions()), "문항")
