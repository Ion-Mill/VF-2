"""교대 보고서 표시 정리 시험 (2026-10-19) — 실제 비서·Claude를 부르지 않는다.

실행 (frontend/ 폴더에서):  ..\\데이터생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
지키는 것: ① 특이 사항의 불량 문장은 로트 보류가 있어도 한 문장이라 5문장이 유지된다 (요구사항 FR-PRD-02-07은 3~5문장)
② 비서가 다듬은 글에만 notable_source 표시가 붙는다 — 화면 머리글이 "AI비서 초안"으로 바뀌는 근거. 진행 중·사람이 고친·확정된 보고서와 원본 dict에는 안 붙는다.
"""
import io
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from llm_compose import Composer, sentences  # noqa: E402

DRAFT = ["실적 87개 / 총 목표 90개 (-3개).", "병목은 기준 병목(OP-30) 그대로."]


class Fake:
    """비서 post 가짜: 줄마다 '다듬음: '을 붙여 돌려준다."""

    def __init__(self):
        self.calls = []

    def __call__(self, kind, lines):
        self.calls.append(kind)
        return {"lines": [{"id": l["id"], "text": "다듬음: " + l["text"]} for l in lines]}


def _modules(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())          # sim_server가 불러올 때 표준 출력을 바꾸므로, buffer가 없는 것으로 막는다
    import sim_server as SS
    import server_live as SL
    return SS, SL


@pytest.mark.parametrize("sq,lots", [(0, []), (3, ["LOT-2609-129-1"]), (1, ["LOT-2609-129-1", "LOT-2609-130-1"]), (12, ["A", "B", "C"])])
def test_defect_sentence_is_one_sentence_with_or_without_hold(monkeypatch, sq, lots):
    _, SL = _modules(monkeypatch)
    s = SL.draft_defect_sentence(sq, lots)
    assert len(sentences(s)) == 1 and s.endswith(".")
    assert s.startswith(f"불량(폐기) {sq}개")
    assert all(l in s for l in lots)


def test_defect_sentence_without_hold_is_unchanged(monkeypatch):
    _, SL = _modules(monkeypatch)
    assert SL.draft_defect_sentence(0, []) == "불량(폐기) 0개."          # 보류가 없을 때의 글은 예전과 똑같다


def test_notable_text_stays_five_sentences_with_hold(monkeypatch):
    _, SL = _modules(monkeypatch)
    parts = ["실적 58개 / 총 목표 90개 (-32개).", "필수 정지(고장 그룹 5분 이상) 없음.", "병목은 기준 병목(OP-30) 그대로.",
             SL.draft_defect_sentence(0, ["LOT-2609-129-1"]), "주의 알람 1건 (362)."]
    assert len(sentences(" ".join(parts))) == 5


def test_only_assistant_text_gets_the_source_mark(monkeypatch):
    SS, _ = _modules(monkeypatch)
    fake = Fake()
    monkeypatch.setattr(SS, "COMPOSER", Composer(run_id=lambda: 1, post=fake, enabled=True))
    base = {"shift_id": "2026-10-01-D", "status": "AI_DRAFT", "partial": False, "notable_text": " ".join(DRAFT), "current_version": 0}
    assert "notable_source" not in SS.shift_with_llm(base)                # 준비 전: 프로그램 초안 그대로, 표시 없음
    SS.COMPOSER.wait_idle()
    got = SS.shift_with_llm(base)
    assert got["notable_source"] == "ASSISTANT" and got["notable_text"].startswith("다듬음: ")
    assert "notable_source" not in base                                    # 원본 dict는 안 바뀐다
    for untouched in ({**base, "partial": True}, {**base, "status": "EDITING"}, {**base, "status": "CONFIRMED"}):
        assert "notable_source" not in SS.shift_with_llm(untouched)       # 진행 중·사람이 고친·확정된 보고서에는 안 붙는다


def test_failed_compose_leaves_the_draft_without_mark(monkeypatch):
    SS, _ = _modules(monkeypatch)

    def boom(kind, lines):
        raise RuntimeError("비서 실패")

    monkeypatch.setattr(SS, "COMPOSER", Composer(run_id=lambda: 1, post=boom, enabled=True))
    base = {"shift_id": "2026-10-01-D", "status": "AI_DRAFT", "partial": False, "notable_text": " ".join(DRAFT), "current_version": 0}
    SS.shift_with_llm(base)
    SS.COMPOSER.wait_idle()
    assert SS.shift_with_llm(base) == base                                 # 실패면 기본 문장 그대로, 표시 없음
