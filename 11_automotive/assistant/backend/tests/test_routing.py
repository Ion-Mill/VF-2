"""표지판 시험 (2026-10-10 계획 3단계): 규칙 보강(PARSE_V2), 요청 꼴 안전장치, 화면 알람 문맥, 빠진 항목 되묻기,
LLM 분류의 근거 묶기(ground)·정책(llm_primary·llm_guarded), 한 답 시간 예산. 실제 LLM 서버 없이 본다."""
import time

import httpx
import pytest

from backend.llm import client as C
from backend.llm import deadline as DL
from backend.llm import jobs
from backend.services import answer as A
from backend.services import routing as R
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)


@pytest.fixture
def v2(monkeypatch):
    monkeypatch.setenv("PARSE_V2", "1")


# ---------------------------------------------------------------- 규칙 보강 (PARSE_V2)
def test_time_words_and_negative_cases(v2):
    assert A.parse("간밤에 이호기 몇 번 멈췄냐")["shift"] == "N"
    p = A.parse("간밤에 이호기 몇 번 멈췄냐")
    assert p["equipment"] == ["VF2-02"] and p["start"] == p["end"] == R.REF_DATE.fromordinal(R.REF_DATE.toordinal() - 1)
    assert A.parse("어제 낮 근무 때 실적 알려줘")["shift"] == "D"
    assert A.parse("일호기 밤에 몇 번 섰어?")["equipment"] == ["VF2-01"]
    for q in ("공기 압력 낮음 알람 뜨면?", "공기 압력이 낮은 이유는?", "이송 속도 좀 낮춰 줘"):  # 낮음·낮은·낮춰는 주간이 아니다
        assert A.parse(q)["shift"] is None, q
    assert A.parse("최근 일주일 VF2-02 정지 기록")["start"] == R.REF_DATE.fromordinal(R.REF_DATE.toordinal() - 7)


def test_keyword_misroutes_fixed(v2):
    assert A.parse("보호구는 몇 개월마다 새로 지급해?")["intents"] == []          # "몇 개월" ≠ 생산 "몇 개" (F28)
    assert A.parse("연차 며칠 남았는지 알려줘")["intents"] == []                 # 재고 아님 (F44)
    assert A.parse("돌아가는 기계 만질 때 목장갑 껴도 돼?")["intents"] == []      # 설비 상태 아님 (F03)
    assert A.parse("1호기 지금 돌아가?")["intents"] == ["equipment_status"]
    assert A.parse("1호기 지금 멈춰 있어?")["intents"] == ["equipment_status"]
    assert "alarm_count" not in A.parse("어제 야간 VF2-01 몇 번 멈췄어?")["intents"]  # 알람 없는 "몇 번"은 알람 횟수가 아니다
    assert "alarm_count" in A.parse("이 알람 몇 번 났어?")["intents"]
    assert A.parse("곧 바꿔야 할 공구 있어?")["intents"] == ["tool_life"]
    assert A.parse("모자란 소모품 있어?")["intents"] == ["inventory"]
    assert A.parse("절삭유 얼마나 남았어?")["intents"] == ["inventory"]
    assert A.parse("1호기 평균 수리 시간 알려줘")["intents"] == ["kpi"]


def test_old_rules_unchanged_without_switch():
    assert A.parse("보호구는 몇 개월마다 새로 지급해?")["intents"] == ["production"]  # 예전 동작 그대로 (스위치 꺼짐)
    assert A.parse("간밤에 이호기 몇 번 멈췄냐")["shift"] is None


def test_request_form_guard(v2):
    g = A.human_only("LOT-2609-001-1 보류 풀어줘")
    assert g and g["status"] == "안내" and "반장" in g["conclusion"]
    assert A.human_only("보류 로트는 누가 해제해?") is None                      # 의문사가 있으면 질문
    assert A.human_only("VF2-01 OEE 알려줘") is None                              # 정보 요청
    assert A.human_only("엑셀로 보고서 뽑는 법 알려줘") is None
    assert "조작하지 않습니다" in A.human_only("2호기 이송 속도 좀 낮춰 줘")["conclusion"]
    assert A.human_only("교대 보고서 확정해.")["status"] == "안내"
    assert A.human_only("작업기록서 대신 써 줘")["status"] == "안내"               # 목록에 없는 요청도 일반 안내
    assert A.human_only("교대 보고서 확정해?") is None                             # 물음은 요청이 아니다


def test_request_guard_returns_no_data(v2):
    a = A.answer("LOT-2609-001-1 보류 풀어줘", "SUP")
    assert a["status"] == "안내" and not a["current_data"]


def test_screen_alarm_context_first(monkeypatch):
    ctx = {"screen": "SCR-09", "alarm_key": "2075"}
    old = A.answer("이 알람 몇 번 났어?", "SUP", ctx)
    assert old["status"] == "답변" and "알람 2075" not in old["conclusion"]      # 옛 파서는 화면 알람을 안 쓴다. 번호 없는 "몇 번"은 이제 기간 전체 건수로 답한다 (예전엔 "문서에 없음" 버그, 2026-10-25 AWS 점검 보고)
    monkeypatch.setenv("PARSE_V2", "1")
    a = A.answer("이 알람 몇 번 났어?", "SUP", ctx)
    assert a["status"] == "답변" and "알람 2075" in a["conclusion"] and a["current_data"]


def test_missing_entity_asks_instead_of_not_in_docs(v2, monkeypatch):
    needs = []
    A.ops_answer("SUP", A.parse("OEE 얼마야?"), needs)
    assert needs == ["설비 (예: VF2-01)"]
    monkeypatch.setattr(A, "_doc_part", lambda *a, **k: None)
    out = A.answer("로트 상태 알려줘", "SUP")
    assert out["status"] == "확인 필요" and "로트 번호" in out["conclusion"]


# ---------------------------------------------------------------- LLM 분류 (근거 묶기·정책)
def _llm_out(**kw):
    out = {"kind": "doc", "intents": [], "equipment": [], "period": "none", "shift": "none", "search_queries": []}
    out.update(kw)
    return out


def test_ground_keeps_rules_and_needs_words(v2):
    p = A.parse("1호기 어제 몇 번 섰어?")
    r = R.ground(_llm_out(kind="ops", intents=["stops"], equipment=["VF2-02"], period="recent_7", shift="N"), "1호기 어제 몇 번 섰어?", p)
    assert r.equipment == ["VF2-01"] and r.start == p["start"] and r.shift is None   # 규칙 값이 우선, 근거 없는 교대는 버림
    q = "곧 바꿔야 할 공구 있어?"
    r = R.ground(_llm_out(kind="ops", intents=["tool_life"], equipment=["CMM-01"], period="yesterday"), q, A.parse(q))
    assert r.equipment == [] and r.start is None                                       # 질문에 근거 낱말이 없으면 쓰지 않는다
    q = "절단기 어제 몇 번 섰어?"
    r = R.ground(_llm_out(kind="ops", intents=["stops"], equipment=["SAW-01"], period="yesterday"), q, A.parse(q))
    assert r.equipment == ["SAW-01"]


def test_validate_route_v2():
    q = "필수 정지가 뭐야?"
    assert jobs.validate_route_v2(_llm_out(kind="maybe"), q)[1] == "값 오류"
    assert jobs.validate_route_v2(_llm_out(kind="ops"), q)[1].startswith("값 오류")      # 운영인데 의도 없음
    got, _ = jobs.validate_route_v2(_llm_out(search_queries=["필수 정지 정의", "고장 5분 이상 정지", "DOC-07 §5.4"]), q)
    assert got["search_queries"] == ["필수 정지 정의"]                                    # 새 숫자·출처 표기 검색어는 버림
    got, _ = jobs.validate_route_v2(_llm_out(kind="none", search_queries=["점심"]), q)
    assert got["search_queries"] == []


@pytest.mark.parametrize("policy,expect", [("llm_guarded", "규칙"), ("llm_primary", "로컬 LLM")])
def test_policy_when_llm_says_none(llm, v2, monkeypatch, policy, expect):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", policy)
    llm(FakeLlm(route=_llm_out(kind="none")))
    q = "어제 야간 VF2-01 몇 번 멈췄어?"   # 규칙이 근거 있는 의도(정지 + 설비 + 날짜)를 찾음
    r = R.decide_route(q, A.parse(q), A.settings())
    assert r.source.startswith(expect)


def test_route_failure_falls_back_to_rules(llm, v2, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    llm(FakeLlm(route={"kind": "ops"}))   # 칸이 빠진 답
    q = "곧 바꿔야 할 공구 있어?"
    r = R.decide_route(q, A.parse(q), A.settings())
    assert r.source.startswith("규칙") and r.intents == ["tool_life"] and r.trace["reason"] == "형식 오류"


def test_llm_route_not_called_for_alarm_procedure_safety(llm, v2, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    fake = llm(FakeLlm(route=_llm_out()))
    for q in ("992 뜨면 뭐부터 봐?", "잠금·표지 작업 전 6단계 순서 알려줘", "고전압 대기는 몇 분이야?"):
        A.answer(q, "SUP")
    assert "route" not in fake.names()


def test_llm_route_clears_keyword_misroute(llm, v2, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    fake = llm(FakeLlm(route=_llm_out(kind="doc", search_queries=["작업지시서 승인 반장"])))
    a = A.answer("작업지시서는 누가 승인해?", "SUP")
    assert "route" in fake.names() and not a["current_data"]          # 규칙은 작업지시 조회로 보냈지만 LLM이 문서 질문으로 고침
    assert a["route"]["kind"] == "doc"


# ---------------------------------------------------------------- 한 답 시간 예산
def test_deadline_skips_calls_when_budget_spent(llm):  # noqa: F811
    fake = llm(FakeLlm(phrase={"conclusion": "x"}))
    with DL.answer_deadline(1.0):
        with pytest.raises(C.LlmUnavailable, match="시간 예산"):
            C.chat_json([{"role": "user", "content": "q"}], {"type": "object"}, "phrase")
    assert fake.requests == []


def test_two_timeouts_open_breaker(llm, monkeypatch):  # noqa: F811
    calls = []

    def slow(request):
        calls.append(1)
        raise httpx.ReadTimeout("느림", request=request)
    llm(slow)
    for _ in range(2):
        with pytest.raises(C.LlmUnavailable, match="시간 초과"):
            C.chat_json([{"role": "user", "content": "q"}], {"type": "object"}, "phrase")
    with pytest.raises(C.LlmUnavailable, match="차단기"):
        C.chat_json([{"role": "user", "content": "q"}], {"type": "object"}, "phrase")
    assert len(calls) == 2


def test_answer_stays_within_budget(llm, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LLM_BUDGET_S", "3")

    def slow_phrase(body):
        time.sleep(1.2)
        return {"conclusion": "다듬은 문장"}
    llm(FakeLlm(phrase=slow_phrase))
    t0 = time.monotonic()
    a = A.answer("어제 야간 VF2-01 몇 번 멈췄어?", "SUP")
    assert time.monotonic() - t0 < 3.5 and a["status"] == "답변"
