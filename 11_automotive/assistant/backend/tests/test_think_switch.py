"""Qwen "깊게 생각" 버튼 시험 (2026-10-15, 사용자 결정 — 생각 예산 6,000토큰, 요청 단위·기본 꺼짐).

진짜 AI 서버는 부르지 않는다 — 로컬 쪽 가짜 전송(`C.use_transport`)이 요청 본문을 기록하고 정해진 답을 돌려준다.
지키는 것: ① 버튼을 안 누르면 요청 본문이 예전과 한 글자도 다르지 않다 ② 누른 요청만 생각을 켠다(예산 6,000, max_tokens에 더함)
③ 문법(GBNF) 길은 켜지 않는다 ④ 서버 스위치가 꺼져 있으면 아무것도 안 바뀐다 ⑤ 6000 말고는 켜지지 않는다
⑥ 켜진 요청만 시간 예산이 늘어난다 ⑦ 실패·시간 초과는 세되 차단기를 건드리지 않는다 ⑧ 깊은 생각은 동시에 하나만 받고 자리는 반드시 돌려준다.
"""
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import settings
from backend.demo_state import get_state
from backend.llm import client as C
from backend.llm import schemas
from backend.llm import think as THINK
from backend.llm.client import LlmBadOutput, LlmUnavailable

client = TestClient(app_module.app)
H = {"X-Role": "SUP"}
MSGS = [{"role": "system", "content": "시스템 지시"}, {"role": "user", "content": "질문 글"}]
FAITH = {"faithful": True, "problem": ""}
Q_DOC = "쿨런트가 뭐야?"                 # 분류(route)를 부르는 질문 (ROUTE_POLICY=llm_guarded)
Q_ALARM = "552 알람 뜨면 어떻게 해?"     # 규칙·카드만, LLM 안 부름


def completion(content=None, reasoning="", finish="stop", raw_content=None):
    msg = {"role": "assistant", "content": raw_content if raw_content is not None else json.dumps(content or FAITH, ensure_ascii=False)}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return {"choices": [{"message": msg, "finish_reason": finish}], "usage": {"completion_tokens": 50}}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    get_state().reset()
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("THINK_APP", "1")
    seen: list[dict] = []
    state = {"mode": "ok", "raw": None}

    def handler(req):
        if not req.content:                  # /api/health의 연결 확인(GET /health) — 본문이 없다, 요청 기록에 넣지 않는다
            return httpx.Response(200, json={"status": "ok"})
        body = json.loads(req.content)
        seen.append(body)
        if state["mode"] == "timeout":
            raise httpx.ReadTimeout("시험: 시간 초과")
        thinking = (body.get("chat_template_kwargs") or {}).get("enable_thinking")
        return httpx.Response(200, json=completion(reasoning="Thinking Process: 1. Analyze ..." if thinking else "", raw_content=state["raw"]))

    C.use_transport(httpx.MockTransport(handler))
    yield seen, state
    C.use_transport(None)
    assert not THINK.busy()                  # 어떤 시험이 끝나도 깊은 생각 자리가 남아 있으면 안 된다


def post(q=Q_ALARM, **extra):
    return client.post("/api/assistant/chat", json={"question": q, **extra}, headers=H)


# ------------------------------------------------------------------ ① 안 누르면 그대로
def test_off_request_body_is_unchanged(env):
    seen, _ = env
    assert C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120) == FAITH
    b = seen[0]
    assert b["chat_template_kwargs"] == {"enable_thinking": False} and "thinking_budget_tokens" not in b and b["max_tokens"] == 120


def test_off_request_with_a_reasoning_reply_is_still_rejected(env):
    _, state = env
    state["mode"] = "ok"
    C.use_transport(httpx.MockTransport(lambda req: httpx.Response(200, json=completion(reasoning="생각이 섞여 나옴"))))
    with pytest.raises(LlmBadOutput, match="생각 글이 섞임"):   # 예전 동작 그대로 — 끈 요청에서는 생각 글이 있으면 거부
        C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120)


# ------------------------------------------------------------------ ② 누른 요청만 켠다
def test_deep_request_turns_thinking_on_and_discards_the_thinking_text(env):
    seen, _ = env
    with THINK.think_request(6000) as tk:
        assert settings().think_budget == 6000
        assert C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120) == FAITH   # 응답에 생각 글이 있어도 받아들이고 버린다
    b = seen[0]
    assert b["chat_template_kwargs"] == {"enable_thinking": True} and b["thinking_budget_tokens"] == 6000 and b["max_tokens"] == 120 + 6000
    assert (tk.calls, tk.failures) == (1, 0)
    assert THINK.override() == 0 and settings().think_budget == 0          # 요청이 끝나면 되돌아온다


# ------------------------------------------------------------------ ③ 문법 길은 켜지 않는다
def test_grammar_call_never_thinks(env):
    seen, state = env
    state["raw"] = json.dumps({"answer": "답이에요."}, ensure_ascii=False)
    with THINK.think_request(6000) as tk:
        assert C.chat_json(MSGS, schemas.WRITE_ANSWER, "write_answer", 400, grammar="root ::= x") == {"answer": "답이에요."}
    b = seen[0]
    assert b["chat_template_kwargs"] == {"enable_thinking": False} and "thinking_budget_tokens" not in b and b["max_tokens"] == 400
    assert tk.calls == 0


# ------------------------------------------------------------------ ④ 서버 스위치가 꺼져 있으면
def test_server_switch_off_ignores_the_request_state(monkeypatch, env):
    seen, _ = env
    monkeypatch.setenv("THINK_APP", "0")
    with THINK.think_request(6000) as tk:
        assert settings().think_budget == 0
        C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120)
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False} and "thinking_budget_tokens" not in seen[0]
    assert tk.calls == 0


# ------------------------------------------------------------------ ⑤ 6000 말고는 안 켜진다
def test_only_6000_turns_it_on():
    for v in (None, 0, 1234, 12000, 6001):
        with THINK.think_request(v) as tk:
            assert tk is None and settings().think_budget == 0 and THINK.override() == 0


# ------------------------------------------------------------------ ⑥ 시간 예산은 켜진 요청만
def test_time_budgets_are_raised_only_inside_a_deep_request():
    base = settings()
    assert base.think_budget == 0
    with THINK.think_request(6000):
        s = settings()
        assert s.read_s >= 180 and s.budget_s >= 900 and s.read_s > base.read_s and s.budget_s > base.budget_s
    after = settings()
    assert (after.read_s, after.budget_s) == (base.read_s, base.budget_s)


# ------------------------------------------------------------------ ⑦ 실패는 세고 차단기는 건드리지 않는다
def test_timeouts_in_a_deep_request_are_counted_but_do_not_trip_the_breaker(env):
    seen, state = env
    state["mode"] = "timeout"
    with THINK.think_request(6000) as tk:
        for _ in range(3):   # 일반 요청이면 연속 2번에서 차단기가 걸리는 횟수
            with pytest.raises(LlmUnavailable, match="시간 초과"):
                C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120)
    assert (tk.calls, tk.failures) == (3, 3)
    assert C._down_until.get(settings().llm_url, 0) <= time.monotonic()      # 다른 사람의 질문까지 막지 않는다
    state["mode"] = "ok"
    assert C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120) == FAITH


def test_bad_output_in_a_deep_request_is_counted(env):
    _, state = env
    state["raw"] = "JSON이 아닌 글"
    with THINK.think_request(6000) as tk:
        with pytest.raises(LlmBadOutput, match="JSON 아님"):
            C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120)
    assert (tk.calls, tk.failures) == (1, 1)


def test_a_think_tag_in_the_body_is_still_rejected_in_a_deep_request(env):
    _, state = env
    state["raw"] = "<think>섞임</think>" + json.dumps(FAITH)
    with THINK.think_request(6000):
        with pytest.raises(LlmBadOutput, match="생각 글이 섞임"):
            C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120)


# ------------------------------------------------------------------ 앱 입구
def test_chat_without_the_button_has_no_think_field_and_keeps_thinking_off(env):
    seen, _ = env
    for extra in ({}, {"think": 0}):
        r = post(**extra)
        assert r.status_code == 200 and "think" not in r.json()
    assert all((b.get("chat_template_kwargs") or {}).get("enable_thinking") is False for b in seen)


def test_chat_refused_when_the_server_switch_is_off(monkeypatch, env):
    seen, _ = env
    monkeypatch.setenv("THINK_APP", "0")
    r = post(think=6000)
    assert r.status_code == 503 and r.json()["code"] == "THINK_DISABLED" and seen == []


@pytest.mark.parametrize("bad", [12000, 1, 600, "깊게"])
def test_chat_rejects_other_values(bad):
    r = post(think=bad)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"


def test_chat_with_the_button_reports_how_many_calls_thought(monkeypatch, env):
    seen, _ = env
    for k, v in {"LLM_JOBS": "write,route", "ROUTE_POLICY": "llm_guarded", "DOC_GATE": "veto", "PARSE_V8": "1", "NUM_MATCH": "value"}.items():
        monkeypatch.setenv(k, v)
    r = post(Q_DOC, think=6000)
    j = r.json()
    assert r.status_code == 200, j
    assert j["think"]["budget"] == 6000 and j["think"]["calls"] >= 1
    assert any((b["chat_template_kwargs"] or {}).get("enable_thinking") for b in seen)
    assert all(not (b["chat_template_kwargs"] or {}).get("enable_thinking") for b in seen if "grammar" in b)   # 문법 길은 늘 생각 끔
    r2 = post(Q_ALARM, think=6000)    # 규칙·카드만으로 답한 질문 — 생각을 쓴 호출 0번이라고 사실대로 밝힌다
    assert r2.status_code == 200 and r2.json()["think"] == {"budget": 6000, "calls": 0, "failures": 0}


def test_only_one_deep_request_at_a_time(env):
    seen, _ = env
    assert THINK.try_acquire()                  # 다른 깊은 생각이 돌고 있는 상태
    try:
        r = post(think=6000)
        assert r.status_code == 503 and r.json()["code"] == "THINK_BUSY" and seen == []
        r2 = post()                             # 버튼을 안 누른 질문은 막히지 않는다
        assert r2.status_code == 200
        h = client.get("/api/health").json()
        assert h["think"]["busy"] is True
    finally:
        THINK.release()
    assert post(think=6000).status_code == 200  # 자리가 나면 다시 받는다


def test_the_slot_is_released_when_answering_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("시험: 답을 만들다 멈춤")

    monkeypatch.setattr(app_module, "answer", boom)
    r = post(think=6000)
    assert r.status_code == 503 and r.json()["code"] == "ASSISTANT_UNAVAILABLE"
    assert not THINK.busy() and THINK.override() == 0     # 오류 뒤에도 자리·요청 상태가 새지 않는다


def test_claude_choice_ignores_the_button(monkeypatch):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    r = post(llm="claude", think=6000)
    assert r.status_code == 503 and r.json()["code"] == "EXTERNAL_LLM_DISABLED" and not THINK.busy()


# ------------------------------------------------------------------ 상태 표시
def test_health_reports_the_think_switch(monkeypatch):
    h = client.get("/api/health").json()
    assert h["think"] == {"server_switch": True, "budget": 6000, "busy": False}
    assert h["llm_status"]["flags"]["think_app"] is True and h["llm_status"]["flags"]["think_budget"] == 0
    monkeypatch.setenv("THINK_APP", "0")
    h2 = client.get("/api/health").json()
    assert h2["think"]["server_switch"] is False and h2["llm_status"]["flags"]["think_app"] is False
