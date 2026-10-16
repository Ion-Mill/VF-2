"""답 문지기 시험 (ANSWER_GATE_V17, 2026-10-14 시급한 문제 1 "지어낸 답", 사용자 결정 D1·D2).

D1: 문서 길(1차·2차 문지기)의 답 종류 표에 부품번호·기본값을 더한다 — 봉인 비교 세트 CMP30의 CMP-022 "절삭유 필터 새로 사려면 부품번호가 뭐야?"를
    Qwen·Claude 세 모델 모두 "품목 코드 CS-CFLT" 줄로 답했다(부품번호 꼴 NN-NNNN을 보는 검사가 알람 카드 길에만 있었음).
D2: 낱말 겹침 문턱 0.2 → 0.1 — 모든 평가 기록에서 이 검사가 거부한 문항 27개는 전부 답이 있는 질문이었다(CMP-002 "노랗게 깜빡이면" ↔ "황색 점멸").
AI 서버는 부르지 않는다(chat_json을 가짜로 끼움).
"""
import re

import pytest

from backend.eval import run_eval as R
from backend.llm.client import LlmUnavailable
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import followup_v2 as FU2

Q_PART = "절삭유 필터 새로 사려면 부품번호가 뭐야?"
LINES_NO_PART = ["CS-CFLT — 품목: 절삭유 필터 · 언제 쓰나: 6개월 필터 청소 때 교체 · 차감량: 1개 · 안전 재고: 2개"]
LINES_WITH_PART = ["페라이트 필터(P/N 64-1252)가 있는지 본다"]


def _mode(monkeypatch, name):
    for k, v in R.MODES[name].items():
        monkeypatch.setenv(k, v)


def test_modes_add_only_their_switches():
    assert R._BASE["ANSWER_GATE_V17"] == "0"
    a, g, v = R.MODES["step20"], R.MODES["step20-gate"], R.MODES["step20-v17"]
    assert {k for k in g if g[k] != a[k]} == {"ANSWER_GATE_V17"}
    assert {k for k in v if v[k] != a[k]} == {"WRITE_RULES_V17", "ANSWER_GATE_V17"}
    assert all(R.MODES[m]["ANSWER_GATE_V17"] == "0" for m in R.MODES if m not in ("step20-gate", "step20-v17"))


@pytest.mark.parametrize("fn", ["first_gate_type_ok_v6", "answer_type_ok"], ids=["1차 문지기", "2차 문지기"])
def test_part_number_question_needs_a_part_number_in_the_lines(monkeypatch, fn):
    f = getattr(A, fn)
    text = " / ".join(LINES_NO_PART)
    _mode(monkeypatch, "step20")
    assert f(Q_PART, text) is True                                           # 예전: 부품번호 꼴을 안 본다 (CMP-022가 샌 구멍)
    _mode(monkeypatch, "step20-gate")
    assert f(Q_PART, text) is False                                          # 고침: 줄에 NN-NNNN 꼴이 없으면 거부
    assert f("페라이트 필터 부품번호가 몇 번이에요?", " / ".join(LINES_WITH_PART)) is True   # 있으면 통과
    assert f("공기 필터 P/N이 뭐예요?", "공기 필터 — Haas P/N 58-1391") is True
    assert f("필터 교체 주기가 뭐야?", text) is True                          # 부품번호를 묻지 않는 질문은 그대로
    assert f("PNG 파일 이름이 뭐야?", text) is True                           # "PN"이 든 다른 낱말은 부품번호 질문이 아니다


def test_default_value_question_needs_the_word_in_the_lines(monkeypatch):
    q = "Setting 15 기본값이 뭐예요?"
    _mode(monkeypatch, "step20-gate")
    assert A.answer_type_ok(q, "Setting 15 — 설명: 단위") is False
    assert A.answer_type_ok(q, "Setting 15 — 기본값: 3") is True
    _mode(monkeypatch, "step20")
    assert A.answer_type_ok(q, "Setting 15 — 설명: 단위") is True


def test_min_overlap_threshold_depends_on_the_switch(monkeypatch):
    _mode(monkeypatch, "step20")
    assert A.tier2_min_overlap() == 0.2
    _mode(monkeypatch, "step20-gate")
    assert A.tier2_min_overlap() == 0.1
    monkeypatch.setattr(A, "TIER2_MIN_OVERLAP", 0.05)   # 측정 도구가 문턱을 더 낮춰도 따른다 (min)
    assert A.tier2_min_overlap() == 0.05


# ── 끝에서 끝 (가짜 LLM): 구어체 질문의 맞는 답이 문턱 때문에 죽지 않는다 (CMP-002) ──
Q_YELLOW = "낮근무 때 설비 위 표시등이 노랗게 깜빡이면 무슨 뜻이에요?"


def _run(monkeypatch, mode):
    _mode(monkeypatch, mode)
    line = next(t for ch in load_corpus() for t in A.plain_lines(ch) if "황색 점멸 = 공구 만료" in t)

    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        user = messages[-1]["content"]
        if name == "route":
            return {"kind": "doc", "intents": [], "equipment": [], "period": "none", "shift": "none",
                    "search_queries": ["작업 표시등 황색 점멸", "표시등 상태 확인"], "doc_question": ""}
        if name == "select":
            by_id = {m.group(1): m.group(2) for m in re.finditer(r"^(L\d+): (.*)$", user, re.M)}
            ids = [i for i, t in by_id.items() if "황색 점멸 = 공구 만료" in t][:1]
            return {"answerable": bool(ids), "line_ids": ids, "lead": "황색 점멸은 공구 만료"}
        if name == "verify":
            return {"answers": True, "missing": ""}
        raise LlmUnavailable("이 시험은 모르는 작업")

    monkeypatch.setattr(A.jobs, "chat_json", fake)
    monkeypatch.setattr(FU2, "chat_json", fake)
    return A.answer(Q_YELLOW, "OPR"), line


def test_colloquial_question_is_answered_only_with_the_gate(monkeypatch):
    a, line = _run(monkeypatch, "step20")
    assert a["status"] == "문서에 없음"                       # 예전: 낱말 겹침 1/7 < 0.2
    a, _ = _run(monkeypatch, "step20-gate")
    assert a["status"] == "답변" and "공구 만료" in a["conclusion"]
