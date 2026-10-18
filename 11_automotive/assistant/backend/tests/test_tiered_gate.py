"""문지기 시험 (2026-10-10 계획 4단계, DOC_GATE=veto·tiered). 실제 LLM 서버 없이 가짜 서버로 본다.

- veto: AI 줄 고르기가 "찾은 글로 답할 수 없다"고 하면 낱말 결과로 답하지 않는다.
- tiered: 낱말 문지기가 막은 문서 질문을 바꿔 쓴 검색어로 다시 찾고, 엄격한 고르기 + 따로 검증 + 코드 검사를 모두 통과할 때만
  원문 줄 그대로(앞머리 없이) 보인다. 하나라도 실패하면 문서에 없음.
- 절차 질문은 LLM에 보내지 않고, LLM을 끄면 예전과 같다.
"""
import re

import pytest

from backend.services import answer as A
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)

GLOVE_Q = "돌아가는 기계 만질 때 목장갑 껴도 돼?"   # 조정 세트 F03 꼴: "목장갑"이 사내 문서에 없어 낱말 문지기가 막는다


def _route(**kw):
    out = {"kind": "doc", "intents": [], "equipment": [], "period": "none", "shift": "none", "search_queries": []}
    out.update(kw)
    return out


def pick(word):
    """후보 줄 가운데 word가 든 줄을 고르는 가짜 줄 고르기."""
    def f(body):
        user = body["messages"][-1]["content"]
        ids = [m.group(1) for m in re.finditer(r"^(L\d+): (.*)$", user, re.M) if word in m.group(2)]
        return {"answerable": bool(ids), "line_ids": ids[:2], "lead": "앞머리는 이 단계에서 쓰지 않는다"}
    return f


@pytest.fixture
def gate(monkeypatch):
    def set_(doc_gate):
        monkeypatch.setenv("PARSE_V2", "1")
        monkeypatch.setenv("NUM_MATCH", "value")
        monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
        monkeypatch.setenv("DOC_GATE", doc_gate)
    return set_


def test_blocked_by_lexical_gate_first():
    assert A.unknown_terms(GLOVE_Q) and A._doc_search(GLOVE_Q) is None


def test_tier2_answers_with_verbatim_lines(llm, gate):  # noqa: F811
    gate("tiered")
    fake = llm(FakeLlm(route=_route(search_queries=["회전 기계 면장갑 착용 금지"]), select=pick("면장갑"),
                       verify={"answers": True, "missing": ""}))
    a = A.answer(GLOVE_Q, "SUP")
    assert a["status"] == "답변" and a["conclusion"].startswith(A.TIER2_PREFIX), a["conclusion"]
    assert "면장갑" in a["conclusion"] and "앞머리" not in a["conclusion"]          # 원문 줄만, AI 앞머리 없음
    assert any(e["cite"].startswith("안전 작업 기준서 DOC-05 §5") for e in a["evidence"]), a["evidence"]
    assert fake.names() == ["route", "select", "verify"] and "따로 검증" in a["mode"]
    assert a["retrieval"]["basis"] == "llm_relaxed"


def test_tier2_rejected_when_verify_says_no(llm, gate):  # noqa: F811
    gate("tiered")
    llm(FakeLlm(route=_route(search_queries=["회전 기계 면장갑 착용 금지"]), select=pick("면장갑"),
                verify={"answers": False, "missing": "목장갑"}))
    assert A.answer(GLOVE_Q, "SUP")["status"] == "문서에 없음"


def test_tier2_rejected_when_select_finds_nothing(llm, gate):  # noqa: F811
    gate("tiered")
    fake = llm(FakeLlm(route=_route(), select={"answerable": False, "line_ids": [], "lead": ""}, verify={"answers": True, "missing": ""}))
    assert A.answer(GLOVE_Q, "SUP")["status"] == "문서에 없음"
    assert "verify" not in fake.names()


def test_tier2_only_for_doc_kinds(llm, gate):  # noqa: F811
    gate("tiered")
    fake = llm(FakeLlm(route=_route(kind="none"), select=pick("면장갑"), verify={"answers": True, "missing": ""}))
    assert A.answer(GLOVE_Q, "SUP")["status"] == "문서에 없음"
    assert fake.names() == ["route"]


def test_tier2_code_checks(llm, gate, monkeypatch):  # noqa: F811
    gate("tiered")
    monkeypatch.setattr(A, "_doc_search", lambda q: None)   # 1차에서 막혔다고 두고 2차만 본다
    llm(FakeLlm(route=_route(search_queries=["주축 정비 1년"]), select=pick("주축"), verify={"answers": True, "missing": ""}))
    a = A.answer("VF-2 스핀들 교체 비용 얼마야?", "SUP")
    assert a["status"] == "문서에 없음"                       # 비용을 묻는데 고른 줄에 금액이 없다 (답 종류 낱말 검사)
    assert A.answer_type_ok("절삭유 목표 농도는 몇 퍼센트야?", "목표 7.0% (굴절계 약 5.0)")
    assert not A.answer_type_ok("반장 시작 회의는 몇 분 동안 해?", "② 반장 시작 회의")
    assert not A.answer_type_ok("측정실 습도는 몇 퍼센트로 맞춰?", "측정실 온도 20 ℃")
    assert A.answer_type_ok("수상한 로트 보류할지는 누가 결정해?", "보류 여부 결정 · 누가: 반장 (SUP)")


def test_veto_uses_llm_judgement(llm, monkeypatch):  # noqa: F811
    q = "필수 정지가 뭐야?"   # 낱말 문지기를 통과하는 질문
    monkeypatch.setenv("LLM_JOBS", "write")
    llm(FakeLlm(select={"answerable": False, "line_ids": [], "lead": ""}))
    assert A.answer(q, "SUP")["status"] == "답변"                 # 예전(lexical): AI가 못 고르면 낱말 결과로 답함
    monkeypatch.setenv("DOC_GATE", "veto")
    assert A.answer(q, "SUP")["status"] == "문서에 없음"          # veto: AI 판단을 따른다


def test_procedure_questions_never_go_to_llm(llm, gate):  # noqa: F811
    gate("tiered")
    fake = llm(FakeLlm(route=_route(), select=pick("잠금"), verify={"answers": True, "missing": ""}))
    a = A.answer("잠금·표지 작업 전 6단계 순서 알려줘", "SUP")
    assert a["status"] == "답변" and fake.names() == []


@pytest.mark.parametrize("q", [GLOVE_Q, "필수 정지가 뭐야?", "VF-2 스핀들 교체 비용 얼마야?", "어제 야간 VF2-01 몇 번 멈췄어?"])
def test_llm_off_tiered_equals_lexical(monkeypatch, q):
    monkeypatch.setenv("PARSE_V2", "1")
    shape = lambda a: (a["status"], a["conclusion"], [e["cite"] for e in a["evidence"]])  # noqa: E731
    monkeypatch.setenv("DOC_GATE", "lexical")
    before = shape(A.answer(q, "SUP"))
    monkeypatch.setenv("DOC_GATE", "tiered")
    assert shape(A.answer(q, "SUP")) == before


def test_veto_mode_verifies_tier1_answers(llm, monkeypatch):  # noqa: F811
    q = "필수 정지가 뭐야?"
    monkeypatch.setenv("LLM_JOBS", "write")
    monkeypatch.setenv("DOC_GATE", "veto")
    fake = llm(FakeLlm(select=pick("필수 정지"), verify={"answers": False, "missing": "정의"}))
    assert A.answer(q, "SUP")["status"] == "문서에 없음"                      # 고른 줄을 따로 검증해 "답 못 함"이면 거부 (F25 꼴)
    assert fake.names() == ["select", "verify"]
    llm(FakeLlm(select=pick("필수 정지"), verify={"answers": True, "missing": ""}))
    assert A.answer(q, "SUP")["status"] == "답변"


def test_veto_mode_llm_error_is_not_a_veto(llm, monkeypatch):  # noqa: F811
    import httpx
    q = "필수 정지가 뭐야?"
    monkeypatch.setenv("LLM_JOBS", "write")
    monkeypatch.setenv("DOC_GATE", "veto")
    llm(FakeLlm(select=pick("필수 정지"), verify=httpx.Response(500)))
    assert A.answer(q, "SUP")["status"] == "답변"                             # AI 서버 오류는 거부로 치지 않는다
