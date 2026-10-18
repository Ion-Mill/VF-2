"""넓게 다시 보기(PURE_RETRY) 시험 (2026-10-18). 기획: 261003_창민/못찾음_넓게다시보기_기획_20261018.md

순수 길은 낱말 검색 상위 조각만 Claude에게 보내고, Claude가 "조각에 답이 없다"(insufficient)고 하면 그대로 "문서에 없음"으로 내보냈다.
정답 조각이 9~50위에 있어 못 보낸 것(검색 한계)을 없는 것(문서 사실)으로 말한 것이다. 스위치 PURE_RETRY=1이면 첫 호출이 insufficient일 때
같은 질문에 상위 PURE_RETRY_TOPK(기본 30)개 조각을 보내 한 번 더 묻고, 그래도 없을 때만 "문서에 없음"으로 끝낸다.
첫 호출 지시문에는 "조각에 없는 부분을 문서에 없다고 단정하지 않는다"는 한 줄이 더해진다.
이 시험은 가짜 Claude 실행기만 쓴다(진짜 호출 0) — 답의 질은 보지 않고 호출 수·요청 글·상태·제외 길·끄면 동일만 본다.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS, cfg as _cfg

client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
Q = "자주 뜬다고 쳐 주는 기준이 며칠에 몇 번이야?"       # 신호·안전 낱말이 없는 순수 길 질문 (조각 12개, 30개로 넓히면 34개)
PROPS = ("answer", "cited", "insufficient")


def cfg(monkeypatch, retry="1", **kw) -> Settings:
    monkeypatch.setenv("PURE_RETRY", retry)
    return _cfg(monkeypatch, **kw)


class Seq:
    """가짜 Claude 실행기: 첫 호출·넓게 다시 본 호출(시스템 지시문에 RETRY_NOTE가 있음)의 결과를 각각 정한다.
    mode: "answer"(마지막 조각을 인용해 답) · "insufficient" · "fail"(실행기 실패). 받은 요청은 calls에 쌓는다."""

    def __init__(self, first="answer", second="answer"):
        self.calls, self.first, self.second = [], first, second

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        system = cmd[cmd.index("--system-prompt") + 1] if "--system-prompt" in cmd else ""
        wide = PURE.RETRY_NOTE in system
        n = max([int(x) for x in re.findall(r"\[C(\d+)\]", stdin_text)] or [0])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append({"wide": wide, "system": system, "user": stdin_text, "n": n, "props": props})
        mode = self.second if wide else self.first
        if mode == "fail":
            return SimpleNamespace(returncode=1, stdout="", stderr="시험: 실패")
        insufficient = mode == "insufficient"
        text = ("넓게 봐도 없음" if wide else "처음엔 없음") if insufficient else ("넓게 본 답" if wide else "처음 답")
        cited = [] if insufficient else [f"C{n}"]         # 마지막 조각을 인용한다 — 넓힌 조각이 출처로 바뀌는지 보인다
        if "sections" in props:
            so = {"sections": [{"title": "", "text": text, "items": []}], "cited": cited, "insufficient": insufficient}
        else:
            so = {"answer": text, "cited": cited, "insufficient": insufficient}
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


def _setup(monkeypatch, runner, **env):
    get_state().reset()
    AS.clear()
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXPAND", "1")
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    def no_local(req):
        raise httpx.ConnectError("시험: 로컬 서버 없음")
    C.use_transport(httpx.MockTransport(no_local))
    CC.use_runner(runner)


@pytest.fixture
def run(monkeypatch):
    """run(first, second, retry="1", q=Q, **env) -> (응답, 실행기)."""
    def _run(first="answer", second="answer", retry="1", q=Q, **env):
        monkeypatch.setenv("PURE_RETRY", retry)
        r = Seq(first, second)
        _setup(monkeypatch, r, **env)
        resp = client.post("/api/assistant/chat", json={"question": q, "llm": "claude"}, headers={"X-Role": "SUP"})
        return resp, r
    yield _run
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def pure_calls(runner):
    return [c for c in runner.calls if c["props"] == PROPS or "sections" in c["props"]]


def expected_first(monkeypatch, q=Q, retry="0"):
    """스위치를 끈 지금 동작의 첫 호출 요청 글 (시스템 지시문, 사용자 글)."""
    s = cfg(monkeypatch, retry=retry)
    with EXT.external_request("claude"):
        s = settings()
        chunks = [c for _, c in PURE.context(q, s.pure_topk, s)]
        msgs = PURE.build_messages(q, chunks, None, PURE.system_for(s))
    return msgs[0]["content"], msgs[1]["content"]


# ------------------------------------------------------------------ 설정
def test_defaults_are_off_and_thirty(monkeypatch):
    f = Settings.__dataclass_fields__
    assert f["pure_retry"].default is False and f["pure_retry_topk"].default == 30
    monkeypatch.delenv("PURE_RETRY", raising=False)
    monkeypatch.delenv("PURE_RETRY_TOPK", raising=False)
    assert settings().pure_retry is False                      # 시험 기본(conftest)도 꺼짐
    assert settings().pure_retry_topk == 30


@pytest.mark.parametrize("raw, want", [("1", True), ("true", True), ("yes", True), ("0", False), ("", False), ("아무거나", False)])
def test_switch_reads_the_environment(monkeypatch, raw, want):
    monkeypatch.setenv("PURE_RETRY", raw)
    assert settings().pure_retry is want


@pytest.mark.parametrize("raw, want", [("30", 30), ("40", 40), ("5", 9), ("500", 60), ("x", 30), ("", 30)])
def test_topk_is_clamped_to_a_range_wider_than_the_first_call(monkeypatch, raw, want):
    monkeypatch.setenv("PURE_RETRY_TOPK", raw)
    assert settings().pure_retry_topk == want


def test_the_notes_say_what_they_should():
    assert "insufficient" in PURE.RETRY_NOTE and "넓게" in PURE.RETRY_NOTE
    assert "단정" in PURE.PARTIAL_NOTE and "찾지 못" in PURE.PARTIAL_NOTE


# ------------------------------------------------------------------ 끝에서 끝
def test_off_sends_exactly_todays_request_and_never_retries(run, monkeypatch):
    resp, r = run(first="insufficient", retry="0")
    sys0, user0 = expected_first(monkeypatch)
    assert resp.status_code == 200 and len(r.calls) == 1
    assert r.calls[0]["system"] == sys0 and r.calls[0]["user"] == user0         # 끄면 요청 글이 한 글자도 다르지 않다
    assert PURE.PARTIAL_NOTE not in sys0 and PURE.RETRY_NOTE not in sys0
    assert resp.json()["status"] == "문서에 없음" and resp.json()["conclusion"] == A.PURE_NO_DOC_V19      # 말투 바꾸기 끔: 고정 문구


def test_on_and_the_first_call_answers_means_one_call_and_only_one_line_differs(run, monkeypatch):
    resp, r = run(first="answer")
    sys0, user0 = expected_first(monkeypatch)
    assert resp.status_code == 200 and len(r.calls) == 1 and not r.calls[0]["wide"]
    assert r.calls[0]["system"] == sys0 + "\n\n" + PURE.PARTIAL_NOTE             # 지시문 한 줄만 더해진다
    assert r.calls[0]["user"] == user0                                            # 조각·질문은 같다
    assert resp.json()["status"] == "답변" and resp.json()["conclusion"] == "처음 답"


def test_on_and_the_first_call_finds_nothing_asks_again_with_more_chunks(run):
    resp, r = run(first="insufficient", second="answer")
    assert resp.status_code == 200 and len(r.calls) == 2
    first, second = r.calls
    assert not first["wide"] and second["wide"]
    assert second["n"] > first["n"] >= 1                                          # 두 번째는 조각이 더 많다
    assert PURE.RETRY_NOTE in second["system"] and PURE.RETRY_NOTE not in first["system"]
    assert PURE.PARTIAL_NOTE in first["system"] and PURE.PARTIAL_NOTE in second["system"]
    body = resp.json()
    assert body["status"] == "답변" and body["conclusion"] == "넓게 본 답"


def test_the_answer_cites_a_chunk_that_only_the_wide_look_had(run, monkeypatch):
    resp, r = run(first="insufficient", second="answer")
    first, second = r.calls
    s = cfg(monkeypatch)
    with EXT.external_request("claude"):
        s = settings()
        wide = [c for _, c in PURE.context(Q, s.pure_retry_topk, s)]
        narrow = {c.chunk_id for _, c in PURE.context(Q, s.pure_topk, s)}
    cited = wide[second["n"] - 1]
    assert cited.chunk_id not in narrow                                           # 첫 호출에는 없던 조각을 인용했다
    ev = {(e["doc_id"], e["section"]) for e in resp.json()["evidence"]}
    assert (cited.doc_id, cited.section) in ev


def test_when_the_wide_look_also_finds_nothing_the_answer_is_no_document(run):
    resp, r = run(first="insufficient", second="insufficient")
    assert resp.status_code == 200 and len(r.calls) == 2
    assert resp.json()["status"] == "문서에 없음" and resp.json()["conclusion"] == A.PURE_NO_DOC_V19


def test_with_the_chat_layout_the_no_document_sentence_is_the_wide_looks(run):
    resp, r = run(first="insufficient", second="insufficient", PURE_STYLE="1", PURE_LAYOUT="1")
    assert len(r.calls) == 2
    assert resp.json()["status"] == "문서에 없음" and resp.json()["conclusion"] == "넓게 봐도 없음"      # 넓게 본 뒤의 문장(Claude가 쓴 이유)


def test_a_failed_second_call_keeps_the_first_result_and_is_not_an_error(run):
    resp, r = run(first="insufficient", second="fail")
    assert resp.status_code == 200 and len(r.calls) == 2                          # 재시도가 오류(503)를 새로 만들지 않는다
    assert resp.json()["status"] == "문서에 없음" and resp.json()["conclusion"] == A.PURE_NO_DOC_V19


def test_with_the_chat_layout_a_failed_second_call_keeps_the_first_sentence(run):
    resp, r = run(first="insufficient", second="fail", PURE_STYLE="1", PURE_LAYOUT="1")
    assert resp.status_code == 200 and len(r.calls) == 2
    assert resp.json()["status"] == "문서에 없음" and resp.json()["conclusion"] == "처음엔 없음"     # 첫 호출 문장 그대로


def test_a_failed_first_call_is_still_an_error(run):
    resp, r = run(first="fail")
    assert resp.status_code == 503 and len(r.calls) == 1                          # 첫 호출 실패는 지금처럼 오류 — 재시도는 insufficient일 때만


def test_the_rule_route_never_retries(run):
    resp, r = run(first="insufficient", q="정비 기한이 지나면 알림이 가?", PURE_RULE="1")
    assert len(pure_calls(r)) == 1 and not any(c["wide"] for c in r.calls)       # 문서에 없음이면 원래 운영 조회로 되돌리는 길이라 지연만 늘린다


def test_a_safety_question_never_retries(run):
    resp, r = run(first="insufficient", q="톱 정비 전에 어디를 차단해야 해?", PURE_SAFETY="1")
    assert len(r.calls) == 1 and not r.calls[0]["wide"]                           # 안전 문서를 통째로 받고 "자동으로 확인하지 못함"으로 끝난다
    assert resp.json()["status"] == "확인 필요"


def test_no_second_call_when_widening_adds_no_new_chunk(run, monkeypatch):
    fixed = PURE.context(Q, 8, cfg(monkeypatch))
    monkeypatch.setattr(PURE, "context", lambda question, k, s: fixed)
    resp, r = run(first="insufficient")
    assert len(r.calls) == 1 and resp.json()["status"] == "문서에 없음"


def test_the_layout_schema_retries_too(run):
    resp, r = run(first="insufficient", second="answer", PURE_STYLE="1", PURE_LAYOUT="1")
    assert resp.status_code == 200 and len(r.calls) == 2 and r.calls[1]["wide"]
    assert resp.json()["status"] == "답변"


# ------------------------------------------------------------------ ask()
def test_ask_adds_the_notes_only_when_asked(monkeypatch):
    s = cfg(monkeypatch)
    seen = []
    monkeypatch.setattr(C, "chat_json", lambda messages, schema, job, max_tokens, st: seen.append(messages[0]["content"]) or {"answer": "x", "cited": [], "insufficient": True})
    chunks = [c for _, c in PURE.retrieve("기준", 2)]
    PURE.ask("기준은?", chunks, None, s)
    PURE.ask("기준은?", chunks, None, s, retry_note=True)
    s_off = cfg(monkeypatch, retry="0")
    PURE.ask("기준은?", chunks, None, s_off)
    assert PURE.PARTIAL_NOTE in seen[0] and PURE.RETRY_NOTE not in seen[0]
    assert PURE.PARTIAL_NOTE in seen[1] and PURE.RETRY_NOTE in seen[1]
    assert PURE.PARTIAL_NOTE not in seen[2] and PURE.RETRY_NOTE not in seen[2]    # 끄면 지금 지시문 그대로
