"""로컬 LLM 연결 시험 — 실제 서버 없이 가짜 서버(httpx.MockTransport)로 본다.

LLM이 틀리거나 죽어도 답은 막히지 않고 기본 문장이 나와야 한다. 알람·절차·조작 요청은 LLM에 보내지 않는다.
"""
import json

import httpx
import pytest

from backend.config import settings
from backend.llm import client as C
from backend.services import answer as A


class FakeLlm:
    """요청을 기록하고, 스키마 이름(phrase/select/route)별로 정해 둔 답을 돌려준다."""

    def __init__(self, **answers):
        self.answers, self.requests = answers, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        body = json.loads(request.content)
        self.requests.append(body)
        name = body["response_format"]["json_schema"]["name"]
        ans = self.answers.get(name)
        if isinstance(ans, Exception):
            raise ans
        if callable(ans):
            ans = ans(body)
        if isinstance(ans, httpx.Response):
            return ans
        msg = {"role": "assistant", "content": json.dumps(ans, ensure_ascii=False)}
        return httpx.Response(200, json={"choices": [{"message": msg, "finish_reason": "stop"}]})

    def names(self):
        return [b["response_format"]["json_schema"]["name"] for b in self.requests]


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_JOBS", "write,route")
    monkeypatch.setenv("LLM_URL", "http://127.0.0.1:8080")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def install(fake):
        C.use_transport(httpx.MockTransport(fake))
        return fake
    yield install
    C.use_transport(None)


STOP_Q = "어제 야간 VF2-01 몇 번 멈췄어?"


def _draft(q):
    """LLM을 끈 답 (기본 문장)."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("LLM_ENABLED", "0")
        return A.answer(q, "SUP")["conclusion"]


# ---------------------------------------------------------------- 다듬기 (운영 답)
def test_phrase_used_when_numbers_kept(llm):
    draft = _draft(STOP_Q)
    nice = "정리하면 " + draft
    fake = llm(FakeLlm(phrase={"conclusion": nice}))
    a = A.answer(STOP_Q, "SUP")
    assert a["conclusion"] == nice and "로컬 LLM" in a["mode"] and "문장 다듬기" in a["mode"]
    assert fake.names() == ["phrase"]
    body = fake.requests[0]
    assert body["chat_template_kwargs"] == {"enable_thinking": False} and body["temperature"] == 0
    assert "$ref" not in json.dumps(body) and len(json.dumps(body["response_format"])) < 16_000


def test_phrase_with_changed_number_falls_back_to_draft(llm):
    draft = _draft(STOP_Q)
    fake = llm(FakeLlm(phrase={"conclusion": draft.replace("8번", "9번")}))
    a = A.answer(STOP_Q, "SUP")
    assert a["conclusion"] == draft and "쓰지 않음" in a["mode"]
    assert len(fake.requests) == 2  # 사유를 붙여 한 번 더 요청
    assert "거부" in fake.requests[1]["messages"][-1]["content"]


@pytest.mark.parametrize("bad", [
    httpx.Response(200, json={"choices": [{"message": {"content": "{\"conclusion\": \"x\"}"}, "finish_reason": "length"}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": "{\"conclusion\": \"x\"}", "reasoning_content": "생각 중"}, "finish_reason": "stop"}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": "JSON 아님"}, "finish_reason": "stop"}]}),
    httpx.Response(500, text="err"),
])
def test_bad_server_output_never_blocks_answer(llm, bad):
    draft = _draft(STOP_Q)
    llm(FakeLlm(phrase=bad))
    a = A.answer(STOP_Q, "SUP")
    assert a["status"] == "답변" and a["conclusion"] == draft


def test_timeout_and_breaker(llm):
    draft = _draft(STOP_Q)
    fake = llm(FakeLlm(phrase=httpx.ConnectError("down")))
    assert A.answer(STOP_Q, "SUP")["conclusion"] == draft
    n = len(fake.requests)
    assert A.answer(STOP_Q, "SUP")["conclusion"] == draft
    assert len(fake.requests) == n  # 차단기: 30초 안에는 서버를 다시 부르지 않는다
    fake2 = llm(FakeLlm(phrase=httpx.ReadTimeout("slow")))
    assert A.answer(STOP_Q, "SUP")["conclusion"] == draft and fake2.requests


def test_llm_caution_is_ignored(llm):
    q = "552 차단기는 바로 리셋해도 돼?"
    off = _draft(q)
    fake = llm(FakeLlm(phrase={"conclusion": "x", "caution": "안전합니다"}))
    a = A.answer(q, "SUP")
    assert a["conclusion"] == off and "안전합니다" not in json.dumps(a, ensure_ascii=False)
    assert "phrase" not in fake.names()  # 알람 답은 다듬기에 보내지 않는다


# ---------------------------------------------------------------- 보내지 않는 질문
@pytest.mark.parametrize("q", ["552 알람 뜨면 뭐부터 봐?", "잠금·표지 작업 전 6단계 순서 알려줘", "1호기 전원 꺼 줘", "불량 원인이 뭐야?"])
def test_alarm_procedure_and_control_questions_send_nothing(llm, q):
    fake = llm(FakeLlm())
    A.answer(q, "SUP")
    assert fake.requests == []


# ---------------------------------------------------------------- 고르기 (문서 답)
DOC_Q = "공기 필터는 언제 바꿔?"


def _offered(q):
    got = A._doc_search(q)
    from backend.llm.jobs import offer
    return got, offer(got["candidates"], A.plain_lines)


def test_select_copies_chosen_lines_verbatim(llm):
    got, offered = _offered(DOC_Q)
    pick = next(i for i, c, t in offered if "공기 필터" in t)
    text = next(t for i, c, t in offered if i == pick)
    fake = llm(FakeLlm(select={"answerable": True, "line_ids": [pick], "lead": "공기 필터 교체 주기입니다."}))
    a = A.answer(DOC_Q, "SUP")
    assert a["conclusion"] == "공기 필터 교체 주기입니다. " + text
    assert "줄 고르기" in a["mode"] and fake.names() == ["select"]
    chunk = next(c for i, c, t in offered if i == pick)
    assert a["evidence"][0]["cite"] == chunk.cite


@pytest.mark.parametrize("bad", [
    {"answerable": True, "line_ids": ["L999"], "lead": ""},             # 없는 줄 번호
    {"answerable": True, "line_ids": ["L1"], "lead": "3년마다 바꿉니다"},  # 고른 줄에 없는 숫자
    {"answerable": True, "line_ids": ["L1"], "lead": "DOC-04 §4.3 참고"},  # 출처는 LLM이 쓰지 않는다
    {"answerable": False, "line_ids": [], "lead": ""},
])
def test_select_rejections_fall_back(llm, bad):
    off = _draft(DOC_Q)
    llm(FakeLlm(select=bad))
    a = A.answer(DOC_Q, "SUP")
    assert a["conclusion"] == off and a["status"] == "답변"


# ---------------------------------------------------------------- 분류 (낱말 규칙이 못 알아들었을 때만)
def test_route_rescue_turns_period_name_into_dates(llm, monkeypatch):
    monkeypatch.setattr(A, "_doc_search", lambda q: None)
    fake = llm(FakeLlm(route={"kind": "ops", "intents": ["stops"], "equipment": ["VF2-01"], "period": "yesterday", "shift": "N"},
                       phrase=lambda body: {"conclusion": body["messages"][-1]["content"].split("기본 문장:\n", 1)[1]}))
    a = A.answer("일호기 간밤에 쉰 거 정리해 줘", "SUP")
    assert a["conclusion"].startswith("2026-09-30 야간 VF2-01 정지 전체 8번")
    assert fake.names()[0] == "route" and "질문 분류" in a["mode"]


def test_route_none_stays_not_in_docs(llm, monkeypatch):
    monkeypatch.setattr(A, "_doc_search", lambda q: None)
    llm(FakeLlm(route={"kind": "none", "intents": [], "equipment": [], "period": "none", "shift": "none"}))
    assert A.answer("회사 버스 시간표 알려줘", "SUP")["status"] == "문서에 없음"


def test_route_not_called_when_rules_understand(llm):
    fake = llm(FakeLlm(phrase=lambda body: {"conclusion": body["messages"][-1]["content"].split("기본 문장:\n", 1)[1]}))
    A.answer(STOP_Q, "SUP")
    assert "route" not in fake.names()


# ---------------------------------------------------------------- 설정·상태
def test_non_loopback_url_disables_llm(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_URL", "http://10.0.0.5:8080")
    s = settings()
    assert not s.llm_enabled and "루프백" in s.problem


def test_probe_reports_alive(llm):
    llm(FakeLlm())
    C._probe_cache.clear()
    assert C.probe()["alive"] is True
