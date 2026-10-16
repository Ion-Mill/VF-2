"""이어 묻기 시험 (FOLLOWUP, 2026-10-12 사용자 결정 "3번까지" — research_notes/로컬 LLM 연결/앞단개선6_계획_20261012.md 3.1·3.3절).
감지·되묻기, 앞 답 기록, 쉽게·짧게 다시 쓰기(가짜 LLM), 안전·절차 글은 보내지 않음, 실패하면 원문 그대로(fail closed),
서버 기억(answer_store)과 API 칸을 본다. 실제 LLM 서버 없이."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (가짜 LLM 고정물)


@pytest.fixture
def fu(monkeypatch):
    for k in ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP"):
        monkeypatch.setenv(k, "1")
    AS.clear()
    yield
    AS.clear()


EV = {"cite": "예방 정비 기준서 DOC-04 §2.3", "doc_id": "DOC-04", "doc_name": "예방 정비 기준서", "revision": "Rev.1",
      "section": "2.3", "title": "외함", "snippet": "웨이 커버"}
LINE = "CS-GRS — 품목: 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) · 언제 쓰나: 웨이 커버 매월, 필터 교체 전에 바른다"


def prev_doc(**kw):
    rec = {"question": "웨이 커버 윤활할 때 쓰는 그리스 이름이 뭐예요?", "role": "SUP", "context": {}, "status": "답변",
           "conclusion": "문서에서 찾은 관련 내용입니다: " + LINE, "steps": [], "evidence": [EV], "current_data": [],
           "related": None, "caution": "근거 안내이며 실행 지시가 아닙니다.", "data_label": None, "is_synthetic": False, "links": [],
           "doc_lines": [LINE], "ops_texts": [], "alarm": False, "procedure": False, "future": False}
    rec.update(kw)
    return rec


def ask(q, prev=None, ctx=None):
    return A.answer(q, "SUP", ctx, prev=prev)


# ---------------------------------------------------------------- 감지
@pytest.mark.parametrize("q,kind", [("방금내용 더 쉽게 설명해", "simple"), ("방금 내용 더 쉽게 설명해", "simple"),
                                    ("위 내용 요약해 줘", "short"), ("더 쉽게 설명해 줘", "simple"), ("그거 다시 말해 줘", "again"),
                                    ("한 번 더 말해 줘", "again"), ("방금 거 쉽게 풀어서 말해 줘", "simple"), ("더 자세히 알려 줘", "detail"),
                                    ("요약해 줘", "short")])
def test_followup_detected(fu, q, kind):
    assert A.followup_kind(q) == kind, q


@pytest.mark.parametrize("q", ["개방금지 표지는 언제 붙여?", "작업지시서 요약 칸에는 뭘 써?", "요약 보고서는 누가 확정해?",
                               "아까워서 그래", "그거 다시 켜도 돼?", "VF2-01 다시 켜 줘", "OEE 설명해 줘", "방금 떴던 알람 뭐야?",
                               "다시 시작하려면 뭐 해?"])
def test_not_followup(fu, q):
    assert A.followup_kind(q) is None, q


def test_subject_words_must_come_from_previous_answer(fu):
    assert A.followup_kind("방금 그리스 얘기 쉽게 설명해", "웨이 커버 그리스 Mobil") == "simple"
    assert A.followup_kind("방금 그리스 얘기 쉽게 설명해", "") is None          # 앞 답이 없으면 새 질문
    assert A.followup_kind("방금 절삭유 얘기 쉽게 설명해", "웨이 커버 그리스") is None   # 앞 답에 없는 주제


def test_screen_alarm_this_keeps_screen_behaviour(fu):
    a = ask("이거 더 쉽게 설명해 줘", ctx={"screen": "SCR-09", "alarm_key": "2075"})
    assert a["status"] == "답변" and "2075" in a["conclusion"] and "followup" not in a


def test_permission_and_control_still_refused(fu):
    assert ask("VF2-01 다시 켜 줘")["status"] == "안내"
    assert ask("방금 거 승인해 줘")["status"] == "안내"


# ---------------------------------------------------------------- 앞 답 없음·거절 뒤·자세히
def test_no_previous_answer_asks_back(fu):
    a = ask("방금내용 더 쉽게 설명해")
    assert a["status"] == "확인 필요" and "앞 답을 이어받지 못합니다" in a["conclusion"]
    assert a["followup"]["reason"] == "앞 답 없음"


@pytest.mark.parametrize("status", ["안내", "문서에 없음", "확인 필요", "근거 없음"])
def test_followup_after_non_answer_repeats_same_status(fu, status):
    p = prev_doc(status=status, conclusion=f"{status} — 앞 답", evidence=[], doc_lines=[])
    a = ask("방금 내용 쉽게 설명해", prev=p)
    assert a["status"] == status and a["conclusion"] == p["conclusion"]


def test_detail_asks_back(fu):
    a = ask("더 자세히 알려 줘", prev=prev_doc())
    assert a["status"] == "확인 필요" and a["followup"]["kind"] == "detail"


def test_again_doc_repeats_verbatim(fu):
    p = prev_doc()
    a = ask("그거 다시 말해 줘", prev=p)
    assert a["status"] == "답변" and a["conclusion"] == p["conclusion"] and a["evidence"] == [EV]


def test_again_ops_queries_fresh(fu):
    first = ask("VF2-02 MTTR 얼마야?")
    assert first["status"] == "답변" and first["current_data"]
    a = ask("그거 다시 말해 줘", prev=first["_followup"])
    assert a["status"] == "답변" and a["current_data"] and a["followup"]["reason"] == "운영 조회 다시"
    assert a["_followup"]["question"] == "VF2-02 MTTR 얼마야?"   # 기록은 앞 질문으로 남는다


# ---------------------------------------------------------------- 쉽게 다시 쓰기 (가짜 LLM)
def _fake(texts, same=True):
    return FakeLlm(simplify={"texts": texts}, faith={"same_meaning": same, "problem": "" if same else "조건이 바뀜"})


def test_rewrite_success_keeps_sources_and_shows_original(fu, llm):  # noqa: F811
    good = "CS-GRS는 그리스예요 (Mobil Grease XHP 222, 14 oz 카트리지). 웨이 커버에 매월, 필터 교체 전에 발라요"
    fake = llm(_fake([good]))
    p = prev_doc()
    a = ask("방금내용 더 쉽게 설명해", prev=p)
    assert a["status"] == "답변" and a["followup"]["rewritten"], a["conclusion"]
    assert a["conclusion"].startswith(A.FU_LEAD["simple"]) and good in a["conclusion"]
    assert a["steps"] == ["원문 — " + LINE]                                     # 원문 줄도 함께
    assert a["evidence"] == [EV] and a["caution"] == p["caution"] and a["is_synthetic"] is False
    assert fake.names() == ["simplify", "faith"]
    assert set(t["job"] for t in a["llm_trace"]) <= set(A.JOB_KO)
    assert "쉽게 다시 쓰기" in a["mode"]


@pytest.mark.parametrize("bad,why", [
    ("CS-GRS 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) · 웨이 커버 매월, 필터 교체 뒤에 바른다", "조건 말 바뀜(전에→뒤에)"),
    ("CS-GRS 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) · 웨이 커버 매월 30분 바른다, 필터 교체 전에", "새 숫자"),
    ("CS-GRS 그리스 (Mobil Grease XHP 2, 14 oz 카트리지) · 웨이 커버 매월, 필터 교체 전에", "숫자 바뀜"),
    ("CS-GRS 그리스 (Shell Gadus 222, 14 oz 카트리지) · 웨이 커버 매월, 필터 교체 전에", "제품 이름 바뀜"),
    ("CS-GRS 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) · DOC-04 §2.3 웨이 커버 매월, 필터 교체 전에", "출처 표기"),
])
def test_rewrite_rejected_falls_back_to_original(fu, llm, bad, why):  # noqa: F811
    llm(_fake([bad]))
    p = prev_doc()
    a = ask("방금 내용 쉽게 설명해", prev=p)
    assert a["status"] == "답변" and not a["followup"]["rewritten"], why
    assert a["conclusion"].endswith(p["conclusion"]) and "원문 그대로" in a["conclusion"]


def test_faith_false_or_llm_error_falls_back(fu, llm):  # noqa: F811
    good = "CS-GRS 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) · 웨이 커버 매월, 필터 교체 전에 바른다"
    llm(_fake([good], same=False))
    assert not ask("방금 내용 쉽게 설명해", prev=prev_doc())["followup"]["rewritten"]
    # 검사 LLM 오류도 거부 (fail closed). 처음에는 가짜 서버가 RuntimeError를 던지게 했는데, 실제 연결에서는 그런 오류가 나지 않고
    # client가 httpx 오류·5xx를 LlmUnavailable로 바꾼다 — 시험 가정이 틀린 것이라 서버 오류 응답(500)으로 바꿈 (2026-10-12)
    import httpx
    llm(FakeLlm(simplify={"texts": [good]}, faith=httpx.Response(500, json={"error": "죽음"})))
    assert not ask("방금 내용 쉽게 설명해", prev=prev_doc())["followup"]["rewritten"]


def test_strict_words_and_markers():
    from backend.llm import jobs
    src = "재공 20개 이상이면 경고 [가상], 반드시 반장에게 알린다"
    assert jobs.check_rewrite("재공이 20개를 넘으면 경고 [가상], 반장에게 알린다", src)[1]          # 이상·반드시 빠짐
    assert jobs.check_rewrite("재공이 20개 이상이면 경고예요, 반드시 반장에게 알려요", src)[1]       # [가상] 빠짐
    assert jobs.check_rewrite("재공이 20개 이상이면 경고 [가상]. 반드시 반장에게 알려요", src)[1] is None


# ---------------------------------------------------------------- 안전·절차 글은 LLM에 보내지 않는다
@pytest.mark.parametrize("kw", [dict(alarm=True), dict(steps=["★1 (작업자) 알람 이력을 본다"]), dict(procedure=True),
                                dict(evidence=[{**EV, "doc_id": "DOC-05", "section": "2"}]),
                                dict(evidence=[{**EV, "doc_id": "DOC-03", "section": "2.1"}])])
def test_safety_and_procedure_answers_are_not_sent(fu, llm, kw):  # noqa: F811
    fake = llm(_fake(["바뀐 글"]))
    p = prev_doc(**kw)
    a = ask("방금 내용 쉽게 설명해", prev=p)
    assert fake.requests == [] and not a["followup"]["rewritten"] and a["conclusion"].endswith(p["conclusion"])


def test_safety_word_lines_stay_verbatim(fu, llm):  # noqa: F811
    safe = "외함 — 웨이 커버 점검·윤활 · 잠금·표지: ○"
    fake = llm(_fake(["CS-GRS는 그리스예요 (Mobil Grease XHP 222, 14 oz 카트리지). 웨이 커버 매월, 필터 교체 전에 발라요"]))
    a = ask("방금 내용 쉽게 설명해", prev=prev_doc(doc_lines=[safe, LINE]))
    assert a["followup"]["rewritten"] and "(원문 그대로) " + safe in a["conclusion"]
    sent = json.dumps(fake.requests[0], ensure_ascii=False)
    assert "잠금·표지" not in sent                                             # 안전 낱말 줄은 요청에 실리지 않는다


def test_llm_off_shows_original(fu):
    p = prev_doc()
    a = ask("방금 내용 쉽게 설명해", prev=p)
    assert not a["followup"]["rewritten"] and "로컬 LLM이 켜져 있을 때만" in a["conclusion"]


def test_chained_followup_uses_root(fu, llm):  # noqa: F811
    llm(_fake(["CS-GRS는 그리스예요 (Mobil Grease XHP 222, 14 oz 카트리지). 웨이 커버 매월, 필터 교체 전에 발라요"]))
    p = prev_doc()
    a = ask("방금 내용 쉽게 설명해", prev=p)
    assert a["_followup"] is p                                                 # 바꿔 쓴 글이 아니라 처음 답을 기억한다


# ---------------------------------------------------------------- 서버 기억·API
def test_store_ttl_owner_and_lru(fu, monkeypatch):
    aid = AS.put({"x": 1}, "SUP-01", "SUP", now=1000.0)
    assert AS.get(aid, "SUP-01", "SUP", now=1001.0) == {"x": 1}
    assert AS.get(aid, "SUP-02", "SUP", now=1001.0) is None                   # 남의 답
    assert AS.get(aid, "SUP-01", "MNT", now=1001.0) is None                   # 다른 역할
    assert AS.get(aid, "SUP-01", "SUP", now=1000.0 + AS.TTL_S + 1) is None    # 만료
    assert AS.get("bad id!", "SUP-01", "SUP") is None
    monkeypatch.setattr(AS, "MAX_ITEMS", 3)
    ids = [AS.put({"n": i}, "", "SUP") for i in range(4)]
    assert AS.get(ids[0], "", "SUP") is None and AS.get(ids[3], "", "SUP") == {"n": 3}


def test_api_answer_id_and_followup(fu):
    c = TestClient(app)
    h = {"X-Role": "SUP", "X-User": "SUP-01"}
    r1 = c.post("/api/assistant/chat", json={"question": "VF2-02 MTTR 얼마야?"}, headers=h).json()
    assert r1["answer_id"] and "_followup" not in r1
    r2 = c.post("/api/assistant/chat", json={"question": "그거 다시 말해 줘", "prev_answer_id": r1["answer_id"]}, headers=h).json()
    assert r2["status"] == "답변" and r2["followup"]["kind"] == "again"
    other = c.post("/api/assistant/chat", json={"question": "그거 다시 말해 줘", "prev_answer_id": r1["answer_id"]},
                   headers={"X-Role": "SUP", "X-User": "SUP-02"}).json()
    assert other["status"] == "확인 필요"                                       # 남의 답은 꺼내지 않는다
    bad = c.post("/api/assistant/chat", json={"question": "그거 다시 말해 줘", "prev_answer_id": "짧음"}, headers=h)
    assert bad.status_code == 422 and bad.json()["code"] == "VALIDATION"
    c.post("/api/sim/reset", headers={"X-Role": "MGR"})
    assert AS.size() == 0                                                     # 시연 초기화 때 비운다


def test_switch_off_no_answer_id(monkeypatch):
    c = TestClient(app)
    r = c.post("/api/assistant/chat", json={"question": "VF2-02 MTTR 얼마야?"}, headers={"X-Role": "SUP"}).json()
    assert "answer_id" not in r and "followup" not in r


def test_seen_guard_items_still_refused_with_followup(fu):
    from backend.tests.test_parse_v5 import _seen_items
    guards = [it for it in _seen_items() if it.get("type") == "guard"]
    assert len(guards) >= 30
    bad = [it["q"] for it in guards if ask(it["q"])["status"] != "안내"]
    assert not bad, bad[:5]


def test_time_budget_respected(fu, llm):  # noqa: F811
    def slow(_body):
        time.sleep(0.01)
        return {"texts": ["x"]}
    llm(FakeLlm(simplify=slow, faith={"same_meaning": True, "problem": ""}))
    a = ask("방금 내용 쉽게 설명해", prev=prev_doc())
    assert not a["followup"]["rewritten"]                                     # 검사 실패("x"는 숫자·이름이 빠짐) → 원문
