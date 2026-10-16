"""거부 시험 묶음 만들기 (2026-10-10 계획 1단계).

이미 본 세트의 none 문항 + 조정 세트 F의 insufficient·none 문항을 한 파일(qa_abstain_pool.json)로 모은다.
2차 문지기·분류를 조정할 때 "지어낸 답 0건"을 이 묶음으로 확인한다. 원래 세트가 바뀌면 다시 만든다.
실행: python backend/eval/build_abstain_pool.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ["qa_set", "qa_holdout", "qa_holdout_b", "qa_holdout_c", "qa_holdout_d", "qa_holdout_e", "qa_holdout_e2",
           "qa_holdout_e3", "qa_holdout_e4", "qa_holdout_e5", "qa_holdout_e6", "qa_holdout_e7", "qa_holdout_e8", "qa_holdout_e9",
           "qa_holdout_cmp30", "qa_tune_f"]   # E8·E9: 2026-10-13, CMP30: 2026-10-14
# E·E2: 2026-10-10, E3·E4: 2026-10-11, E5·E6·E7: 2026-10-12 공개 뒤 추가. 이어 묻기 문항(type followup)은 홀로 물으면 뜻이 없어 넣지 않는다


def build() -> dict:
    items = []
    for name in SOURCES:
        for it in json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))["items"]:
            if it["type"] in ("none", "insufficient"):
                items.append({**it, "id": f"{name.removeprefix('qa_')}:{it['id']}"})
    return {"_about": "거부 시험 묶음 (2026-10-10, build_abstain_pool.py로 만든 파생 파일 — 손으로 고치지 않는다). "
                      "이미 본 세트의 none·insufficient + 조정 세트 F의 insufficient·none. 모두 거부(문서에 없음·근거 없음·확인 필요)가 정답이고, "
                      "답하면 지어낸 답(hallucinated)으로 센다. 원래 세트: " + ", ".join(SOURCES),
            "items": items}


if __name__ == "__main__":
    out = build()
    (HERE / "qa_abstain_pool.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(out["items"]), "문항")
