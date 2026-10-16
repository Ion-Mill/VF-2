"""LLM 연결 오류 시험 (2026-10-10 23:52 — 시험용 복사본 평가가 RemoteProtocolError로 멈춘 뒤).

llama-server(cpp-httplib)는 쉬는 연결을 5초 뒤 닫고(`Keep-Alive: timeout=5`), httpx 기본 연결 유지도 5초라
막 닫힌 연결에 요청을 보내면 "Server disconnected without sending a response."가 난다 (encode/httpx discussion #2056).
- 연결 유지를 서버보다 짧게 둔다.
- 이 오류는 새 연결로 한 번만 다시 보낸다. 두 번 나면 LlmUnavailable(부른 쪽이 기본 문장을 씀).
- 그 밖의 연결 오류도 앱을 멈추지 않고 LlmUnavailable로 알린다 (규칙 3.4).
"""
import httpx
import pytest

from backend.llm import client as C
from backend.llm.client import LlmUnavailable, chat_json
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)

MSG = [{"role": "user", "content": "x"}]


def test_keepalive_shorter_than_server():
    assert C.KEEPALIVE_S < 5   # 서버 keep-alive 5초보다 짧아야 경합이 없다


def test_remote_protocol_error_is_retried_once(llm):  # noqa: F811
    calls = []

    def flaky(body):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return {"a": 1}
    llm(FakeLlm(t=flaky))
    assert chat_json(MSG, {"type": "object"}, "t") == {"a": 1}
    assert len(calls) == 2


def test_remote_protocol_error_twice_is_unavailable(llm):  # noqa: F811
    fake = llm(FakeLlm(t=httpx.RemoteProtocolError("Server disconnected without sending a response.")))
    with pytest.raises(LlmUnavailable, match="연결 끊김"):
        chat_json(MSG, {"type": "object"}, "t")
    assert len(fake.requests) == 2      # 한 번만 다시 보낸다


@pytest.mark.parametrize("exc", [httpx.ReadError("boom"), httpx.WriteError("boom"), httpx.LocalProtocolError("boom")])
def test_other_transport_errors_do_not_crash(llm, exc):  # noqa: F811
    fake = llm(FakeLlm(t=exc))
    with pytest.raises(LlmUnavailable):
        chat_json(MSG, {"type": "object"}, "t")
    assert len(fake.requests) == 1      # 다시 보내지 않는다


def test_answer_falls_back_when_server_disconnects(llm, monkeypatch):  # noqa: F811
    """앱 흐름에서도 멈추지 않고 기본 문장으로 답한다 (예전: 예외가 그대로 올라가 평가·화면이 멈춤)."""
    from backend.services import answer as A
    monkeypatch.setenv("PARSE_V2", "1")
    monkeypatch.setenv("PARSE_V3", "1")
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("DOC_GATE", "tiered")
    monkeypatch.setenv("SPLIT_Q", "1")
    llm(FakeLlm(route=httpx.RemoteProtocolError("x"), select=httpx.RemoteProtocolError("x"), verify=httpx.RemoteProtocolError("x"),
                phrase=httpx.RemoteProtocolError("x")))
    a = A.answer("어제 야간 VF2-01 몇 번 멈췄어?", "SUP")
    assert a["status"] == "답변" and a["current_data"]
    assert any((t.get("reason") or "").startswith("LLM 오류: 연결 끊김") for t in a.get("llm_trace") or []), a.get("llm_trace")
