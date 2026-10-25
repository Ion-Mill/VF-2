"""Claude(Anthropic API) 연결부 시험 (2026-10-14, 점수·비용 비교 실험용). 실제 서버·패키지는 부르지 않고 가짜 클라이언트를 끼운다.

지키는 것: ① 기본(local)은 이 연결부를 건드리지 않는다 ② 잠금·열쇠·기록 경로가 없으면 외부로 나가지 않는다
③ 샘플링·seed 같은 5.5 계열이 거부하는 칸을 보내지 않는다 ④ 지원하지 않는 스키마 제약은 빼고 받은 뒤 코드로 다시 본다
⑤ 비용 상한 ⑥ 기록에 질문·답 글·열쇠가 없다.
"""
import json
import sys
from types import SimpleNamespace

import pytest

from backend.config import settings
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import schemas
from backend.llm.client import LlmBadOutput, LlmUnavailable
from backend.tests.test_llm import llm  # noqa: F401  (fixture)

KEY = "sk-ant-test-0000"   # 가짜 값 — 어디에도 출력되면 안 된다


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


class RateLimitError(Exception):
    status_code = 429


class BadRequestError(Exception):
    status_code = 400
    message = "schema 거절"


class AuthenticationError(Exception):
    status_code = 401


class ServerError(Exception):
    status_code = 503


def reply(text, stop="end_turn", usage=(1000, 500)):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)], stop_reason=stop,
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1], cache_read_input_tokens=0, cache_creation_input_tokens=0))


class Fake:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def claude(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("MOM_CLAUDE_VIA", "api")   # 이 파일은 API 방식 시험 (cli 방식은 test_claude_cli.py)
    monkeypatch.setenv("MOM_CLAUDE_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("MOM_CLAUDE_EFFORT", "low")
    monkeypatch.setenv("MOM_CLAUDE_COST_CAP_USD", "20")
    monkeypatch.setenv("MOM_EXTERNAL_LLM_OK", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "usage_t.jsonl"))
    fake = Fake()
    CC.use_client(fake)
    yield fake, tmp_path
    CC.use_client(None)


MSG = [{"role": "system", "content": "시스템 지시"}, {"role": "user", "content": "질문 글: 992 뜨면?"}]
WRITE = {"answer": "답이에요."}


def call(schema=schemas.WRITE_ANSWER, name="write_answer", max_tokens=400):
    return C.chat_json(MSG, schema, name, max_tokens)


# ------------------------------------------------------------------ 잠금
def test_claude_is_off_without_the_experiment_lock(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.delenv("MOM_EXTERNAL_LLM_OK", raising=False)
    s = settings()
    assert not s.llm_enabled and "외부 LLM 잠금" in s.problem
    assert C.probe(s)["alive"] is False and "잠금" in (C.probe(s)["reason"] or "")


def test_lock_is_read_from_the_process_environment_only(monkeypatch, tmp_path):
    """.env에 적어도 켜지지 않는다 — 잠금은 os.environ에서만 읽는다."""
    import backend.config as cfg
    monkeypatch.setattr(cfg, "_dotenv", lambda: {"MOM_EXTERNAL_LLM_OK": "1", "LLM_PROVIDER": "claude", "LLM_ENABLED": "1"})
    monkeypatch.delenv("MOM_EXTERNAL_LLM_OK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    s = cfg.settings()
    assert s.llm_provider == "claude" and not s.llm_enabled and s.problem


@pytest.mark.parametrize("drop", ["ANTHROPIC_API_KEY", "MOM_USAGE_LEDGER", "MOM_EXTERNAL_LLM_OK"])
def test_gate_needs_key_ledger_and_lock(claude, monkeypatch, drop):
    monkeypatch.delenv(drop, raising=False)
    if drop == "ANTHROPIC_API_KEY":
        import backend.config as cfg
        monkeypatch.setattr(cfg, "_dotenv", lambda: {})
    CC.use_client(None)   # 가짜 클라이언트가 열쇠 없음 검사를 건너뛰지 않게
    with pytest.raises(LlmUnavailable):
        call()


def test_api_key_uses_dotenv_when_the_environment_is_empty(monkeypatch):
    import backend.config as cfg
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cfg, "_dotenv", lambda: {"ANTHROPIC_API_KEY": "sk-ant-from-dotenv"})
    assert cfg.anthropic_api_key() == "sk-ant-from-dotenv"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
    assert cfg.anthropic_api_key() == "sk-ant-from-env"


def test_ledger_name_must_be_usage_jsonl(claude, monkeypatch, tmp_path):
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "other.jsonl"))
    with pytest.raises(LlmUnavailable, match="usage_"):
        call()


def test_unknown_model_is_refused(claude, monkeypatch):
    monkeypatch.setenv("MOM_CLAUDE_MODEL", "claude-opus-4-1")
    with pytest.raises(LlmUnavailable, match="알 수 없는 모델"):
        call()


def test_local_provider_never_touches_the_claude_client(monkeypatch, llm):
    """기본(local)은 Claude 연결부를 부르지 않고, 요청 본문은 예전 그대로다(생각 끔·온도 0·seed·response_format)."""
    from backend.tests.test_llm import FakeLlm
    monkeypatch.setattr(CC, "chat_json_claude", lambda *a, **k: (_ for _ in ()).throw(AssertionError("local에서 불림")))
    monkeypatch.setenv("LLM_PROVIDER", "local")
    fake = llm(FakeLlm(t={"a": 1}))
    assert C.chat_json([{"role": "user", "content": "x"}], {"type": "object"}, "t") == {"a": 1}
    body = fake.requests[0]
    assert body["chat_template_kwargs"] == {"enable_thinking": False} and body["temperature"] == 0 and body["seed"] == 7
    assert "response_format" in body and "output_config" not in body and "cache_prompt" not in body


def test_label_and_model_name_follow_the_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "local")
    assert settings().llm_label == "로컬 LLM" and settings().llm_model_name == settings().llm_model
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("MOM_CLAUDE_MODEL", "claude-haiku-5-5")
    assert "외부 LLM" in settings().llm_label and settings().llm_model_name == "claude-haiku-5-5"


def test_key_never_appears_in_flags_health_or_probe(claude):
    s = settings()
    blob = json.dumps({"flags": s.flags(), "probe": C.probe(s), "repr": repr(s)}, ensure_ascii=False)
    assert KEY not in blob and "sk-ant" not in blob and "ANTHROPIC" not in blob


# ------------------------------------------------------------------ 요청 모양
def test_request_has_no_sampling_or_local_server_fields(claude):
    fake, _ = claude
    fake.replies.append(reply(json.dumps(WRITE)))
    assert call() == WRITE
    kw = fake.calls[0]
    for bad in ("temperature", "top_p", "top_k", "seed", "presence_penalty", "chat_template_kwargs", "cache_prompt",
                "response_format", "grammar", "thinking", "fallbacks", "tool_choice"):
        assert bad not in kw, bad
    assert kw["model"] == "claude-opus-5-5"
    assert kw["system"] == "시스템 지시" and kw["messages"] == [{"role": "user", "content": "질문 글: 992 뜨면?"}]
    assert kw["max_tokens"] >= CC.MIN_MAX_TOKENS
    fmt = kw["output_config"]["format"]
    assert fmt["type"] == "json_schema" and kw["output_config"]["effort"] == "low"
    assert "maxLength" not in json.dumps(fmt["schema"]) and "minLength" not in json.dumps(fmt["schema"])
    assert fmt["schema"]["additionalProperties"] is False and fmt["schema"]["required"] == ["answer"]


def test_prepare_schema_keeps_enum_and_drops_unsupported_constraints():
    sch = schemas.select(["L1", "L2"])
    out = CC.prepare_schema(sch)
    txt = json.dumps(out)
    assert "maxItems" not in txt and "maxLength" not in txt
    assert out["properties"]["line_ids"]["items"]["enum"] == ["L1", "L2"] and out["additionalProperties"] is False
    assert "maxItems" in json.dumps(sch)   # 원래 스키마는 건드리지 않는다


def test_grammar_argument_is_accepted_and_ignored(claude):
    fake, _ = claude
    fake.replies.append(reply(json.dumps(WRITE)))
    assert C.chat_json(MSG, schemas.WRITE_ANSWER, "write_answer", 400, grammar="root ::= x") == WRITE
    assert "grammar" not in fake.calls[0]


# ------------------------------------------------------------------ 받은 뒤 다시 검사
def test_constraints_stripped_from_the_schema_are_checked_after_receiving(claude):
    fake, _ = claude
    fake.replies.append(reply(json.dumps({"answer": "가" * 400})))                       # maxLength 300 위반
    with pytest.raises(LlmBadOutput, match="스키마 제약 위반"):
        call()
    fake.replies.append(reply(json.dumps({"answered": True})))
    with pytest.raises(LlmBadOutput):
        call()
    sel = schemas.select(["L1", "L2"])
    fake.replies.append(reply(json.dumps({"answerable": True, "line_ids": ["L1", "L2", "L1", "L2", "L1", "L2", "L1"], "lead": "x"})))
    with pytest.raises(LlmBadOutput, match="항목"):                                      # maxItems 6 위반
        call(sel, "select")
    fake.replies.append(reply(json.dumps({"answerable": True, "line_ids": ["L9"], "lead": "x"})))
    with pytest.raises(LlmBadOutput, match="enum"):
        call(sel, "select")
    fake.replies.append(reply(json.dumps({"answerable": True, "line_ids": ["L2"], "lead": "요약"})))
    assert call(sel, "select")["line_ids"] == ["L2"]


@pytest.mark.parametrize("stop,why", [("refusal", "거절"), ("max_tokens", "길이 초과")])
def test_refusal_and_truncation_are_bad_output(claude, stop, why):
    fake, _ = claude
    fake.replies.append(reply("{}", stop=stop))
    with pytest.raises(LlmBadOutput, match=why):
        call()


def test_non_json_and_non_object_are_bad_output(claude):
    fake, _ = claude
    fake.replies += [reply("그냥 글"), reply("[1]"), reply("")]
    for _ in range(3):
        with pytest.raises(LlmBadOutput):
            call()


# ------------------------------------------------------------------ 오류 매핑·차단기
@pytest.mark.parametrize("exc,kind,text", [
    (RateLimitError("x"), LlmUnavailable, "429"), (BadRequestError("x"), LlmBadOutput, "요청 거절 400"),
    (AuthenticationError("x"), LlmUnavailable, "인증"), (ServerError("x"), LlmUnavailable, "503"),
    (APIConnectionError("x"), LlmUnavailable, "연결 실패"), (APITimeoutError("x"), LlmUnavailable, "시간 초과")])
def test_sdk_errors_map_to_the_same_exceptions_as_the_local_client(claude, exc, kind, text):
    fake, _ = claude
    fake.replies.append(exc)
    with pytest.raises(kind, match=text):
        call()


def test_breaker_opens_after_a_connection_failure(claude):
    fake, _ = claude
    fake.replies.append(APIConnectionError("x"))
    with pytest.raises(LlmUnavailable, match="연결 실패"):
        call()
    with pytest.raises(LlmUnavailable, match="차단기"):
        call()
    assert len(fake.calls) == 1   # 두 번째는 부르지 않았다


def test_missing_package_is_unavailable_not_a_crash(claude, monkeypatch):
    CC.use_client(None)
    monkeypatch.setitem(sys.modules, "anthropic", None)   # import anthropic → ImportError
    with pytest.raises(LlmUnavailable, match="패키지 없음"):
        call()


# ------------------------------------------------------------------ 사용량·비용
def test_cost_math_matches_the_price_table():
    assert CC.cost_usd("claude-opus-5-5", 1000, 500) == pytest.approx(0.014)
    assert CC.cost_usd("claude-sonnet-5-5", 1_000_000, 0) == pytest.approx(2.0)
    assert CC.cost_usd("claude-haiku-5-5", 0, 1_000_000) == pytest.approx(0.5)


def test_ledger_has_tokens_and_cost_but_no_text_or_key(claude):
    fake, tmp = claude
    fake.replies.append(reply(json.dumps({"answer": "비밀 답 글입니다"}), usage=(2000, 300)))
    call(name="write_answer")
    raw = (tmp / "usage_t.jsonl").read_text(encoding="utf-8")
    row = json.loads(raw.splitlines()[0])
    assert row["job"] == "write_answer" and row["in"] == 2000 and row["out"] == 300 and row["model"] == "claude-opus-5-5"
    assert row["usd"] == pytest.approx(round(CC.cost_usd("claude-opus-5-5", 2000, 300), 6))
    assert "992" not in raw and "비밀 답 글" not in raw and KEY not in raw and "질문" not in raw
    s = CC.ledger_summary()
    assert s["calls"] == 1 and s["in_tokens"] == 2000 and s["by_job"]["write_answer"]["calls"] == 1


def test_cost_cap_stops_further_calls_and_counts_other_ledger_files(claude, monkeypatch):
    fake, tmp = claude
    (tmp / "usage_earlier.jsonl").write_text(json.dumps({"usd": 19.99}) + "\n", encoding="utf-8")   # 앞선 실행이 쓴 돈
    monkeypatch.setenv("MOM_CLAUDE_COST_CAP_USD", "20")
    fake.replies += [reply(json.dumps(WRITE), usage=(2000, 100)), reply(json.dumps(WRITE))]
    call()                                   # 19.99 + 0.01(= 2000·4 + 100·20)/1e6 → 상한 20.00 에 닿음
    with pytest.raises(LlmUnavailable, match="비용 상한"):
        call()
    assert len(fake.calls) == 1


def test_llm_trace_style_failure_does_not_write_a_ledger_row_when_the_call_never_happened(claude):
    fake, tmp = claude
    fake.replies.append(RateLimitError("x"))
    with pytest.raises(LlmUnavailable):
        call()
    assert not (tmp / "usage_t.jsonl").exists()


# ------------------------------------------------------------------ Claude 실패 한 번 → Gemini 한 번 (2026-10-24). 네트워크·진짜 열쇠 없음
GEMINI_KEY = "gemini-test-key-zzzz"
MARKER = "UNIQUE_BODY_MARKER"
_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer"], "properties": {"answer": {"type": "string"}}}


def _gemini_env(monkeypatch, tmp_path):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_JOBS", "write")
    monkeypatch.setenv("FOLLOWUP_V2", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "usage_t.jsonl"))
    monkeypatch.setattr(CC, "_call_api", lambda *a, **k: (_ for _ in ()).throw(LlmUnavailable("응답 시간 초과")))
    monkeypatch.setattr("backend.llm.gemini_client.time.sleep", lambda *_a, **_k: None)


def _install_gemini(payload):
    seen = []

    def transport(url, body, headers, timeout):
        seen.append((url, body, headers, timeout))
        if isinstance(payload, Exception):
            raise payload
        return payload

    G = __import__("backend.llm.gemini_client", fromlist=["use_transport"])
    G.use_transport(transport)
    return seen, G


def _ok(obj):
    raw = json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": "생각 과정", "thought": True}, {"text": json.dumps(obj, ensure_ascii=False)}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4}}, ensure_ascii=False).encode()
    return 200, raw


def test_claude_success_does_not_call_gemini(monkeypatch, tmp_path):
    from backend.llm import external as EXT
    _gemini_env(monkeypatch, tmp_path)
    monkeypatch.setattr(CC, "_call_api", lambda *a, **k: {"answer": "claude"})
    seen, G = _install_gemini(_ok({"answer": "gemini"}))
    try:
        with EXT.external_request("claude"):
            out = CC.chat_json_claude([{"role": "user", "content": MARKER}], _SCHEMA, "pure_answer", 100)
    finally:
        G.use_transport(None)
    assert out == {"answer": "claude"} and seen == []


def test_claude_failure_uses_one_gemini_json(monkeypatch, tmp_path):
    from backend.llm import external as EXT
    _gemini_env(monkeypatch, tmp_path)
    seen, G = _install_gemini(_ok({"answer": "대체 답"}))
    try:
        with EXT.external_request("claude") as ext:
            out = CC.chat_json_claude([{"role": "system", "content": "지시"}, {"role": "user", "content": MARKER}], _SCHEMA, "pure_answer", 100)
            assert ext.material_failure() is None
    finally:
        G.use_transport(None)
    assert out == {"answer": "대체 답"} and len(seen) == 1
    url, body, headers, timeout = seen[0]
    assert url.endswith("/models/gemini-3.8-flash:generateContent")
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "medium"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert headers["x-goog-api-key"] == GEMINI_KEY and timeout == 20
    raw = (tmp_path / "usage_t.jsonl").read_text(encoding="utf-8")
    row = json.loads(raw.splitlines()[-1])
    assert row["model"] == "gemini-3.8-flash" and row["effort"] == "medium" and row["via"] == "api"
    assert GEMINI_KEY not in raw and MARKER not in raw and "생각 과정" not in raw


def test_both_failures_keep_the_unavailable_message_and_stop_at_one_gemini(monkeypatch, tmp_path):
    from backend.chat_service import UNAVAILABLE_MESSAGE, Unavailable, _failure_line, _unavailable
    from backend.llm import external as EXT
    _gemini_env(monkeypatch, tmp_path)
    seen, G = _install_gemini(LlmUnavailable("연결 실패"))
    old = CC._down_until
    CC._down_until = 10**12
    try:
        with EXT.external_request("claude"):
            with pytest.raises(EXT.ExternalLlmFailure) as ei:
                CC.chat_json_claude([{"role": "user", "content": MARKER}], _SCHEMA, "lookup_decide", 100)
        assert CC._down_until == 10**12
    finally:
        CC._down_until = old
        G.use_transport(None)
    assert len(seen) == 1
    line = _failure_line(ei.value)
    assert GEMINI_KEY not in line and MARKER not in line and "Gemini" in line
    body = json.loads(_unavailable(None, Unavailable(line)).body)
    assert body["message"] == UNAVAILABLE_MESSAGE + "\n" + "Gemini 호출이 그 밖으로 실패했습니다."


def test_polish_failure_keeps_the_program_sentence(monkeypatch, tmp_path):
    from backend.llm import external as EXT
    from backend.services.answer import _followup_answer
    _gemini_env(monkeypatch, tmp_path)
    seen, G = _install_gemini(LlmUnavailable("응답 시간 초과"))
    prev = {"status": "답변", "conclusion": "프로그램 원문 문장", "doc_lines": ["프로그램 원문 문장"], "ops_texts": [],
            "steps": [], "evidence": [], "current_data": None, "related": [], "caution": None, "data_label": None,
            "is_synthetic": False, "links": [], "alarm": None, "procedure": None, "future": None, "pure": False,
            "question": "q", "context": {}, "blocks": []}
    try:
        with EXT.external_request("claude"):
            out = _followup_answer("simple", "MGR", prev, {"sources": []}, settings(), {})
    finally:
        G.use_transport(None)
    assert len(seen) == 2
    assert out["status"] == "답변" and "프로그램 원문 문장" in out["conclusion"]
    assert "원문 그대로" in out["conclusion"]


def test_cli_runner_does_not_call_gemini(monkeypatch, tmp_path):
    from backend.llm import external as EXT
    _gemini_env(monkeypatch, tmp_path)
    seen, G = _install_gemini(_ok({"answer": "gemini"}))

    def run(cmd, stdin_text, timeout):
        raise OSError("cli")

    CC.use_runner(run)
    try:
        with EXT.external_request("claude"):
            with pytest.raises(LlmUnavailable):
                CC.chat_json_claude([{"role": "user", "content": MARKER}], _SCHEMA, "phrase", 50)
    finally:
        CC.use_runner(None)
        G.use_transport(None)
    assert seen == []


def test_gemini_retries_http_503_once(monkeypatch, tmp_path):
    from backend.llm import external as EXT
    from backend.llm import gemini_client as G
    _gemini_env(monkeypatch, tmp_path)
    waits = []
    monkeypatch.setattr("backend.llm.gemini_client.time.sleep", lambda n: waits.append(n))
    seen = []
    state = {"n": 0}

    def transport(url, body, headers, timeout):
        seen.append((url, body, headers, timeout))
        state["n"] += 1
        if state["n"] == 1:
            raise LlmUnavailable("HTTP 503")
        return _ok({"answer": "다시 받은 답"})

    G.use_transport(transport)
    try:
        with EXT.external_request("claude"):
            out = CC.chat_json_claude([{"role": "user", "content": MARKER}], _SCHEMA, "pure_answer", 100)
    finally:
        G.use_transport(None)
    assert out == {"answer": "다시 받은 답"} and len(seen) == 2 and waits == [G.RETRY_WAIT_S]
    assert seen[0][3] == 20 and seen[1][3] == 20
    assert seen[0][1]["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "medium"


def test_second_503_keeps_the_unavailable_message(monkeypatch, tmp_path):
    from backend.chat_service import UNAVAILABLE_MESSAGE, Unavailable, _failure_line, _unavailable
    from backend.llm import external as EXT
    _gemini_env(monkeypatch, tmp_path)
    seen, G = _install_gemini(LlmUnavailable("HTTP 503"))
    try:
        with EXT.external_request("claude"):
            with pytest.raises(EXT.ExternalLlmFailure) as ei:
                CC.chat_json_claude([{"role": "user", "content": MARKER}], _SCHEMA, "lookup_decide", 100)
    finally:
        G.use_transport(None)
    assert len(seen) == 2
    line = _failure_line(ei.value)
    assert GEMINI_KEY not in line and MARKER not in line
    body = json.loads(_unavailable(None, Unavailable(line)).body)
    assert body["message"] == UNAVAILABLE_MESSAGE + "\n" + "Gemini가 바빠 503을 냈습니다."
