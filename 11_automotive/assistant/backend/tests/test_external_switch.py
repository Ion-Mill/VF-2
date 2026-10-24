"""앱 외부 LLM 선택 스위치 시험 (2026-10-15, `research_notes/외부LLM_스위치_최종기획서_20261014.md` 6·7절).

진짜 `claude`도 로컬 AI 서버도 부르지 않는다 — 가짜 `claude` 실행기(`CC.use_runner`)와 로컬 쪽 가짜 전송(`C.use_transport`)을 끼운다.
지키는 것: ① 선택이 없으면 한 글자도 안 바뀐다 ② 서버 스위치가 꺼져 있으면 외부로 아무것도 안 나간다 ③ 켜 있으면 요청 안에서만 공급자가 바뀌고 끝나면 되돌아온다
④ 재료를 정하는 단계(route·select·verify) 실패는 오류(자동으로 로컬로 바꾸지 않음) ⑤ 다듬는 단계 실패는 원문으로 답하고 표시 ⑥ 평가 경로의 잠금은 예전 그대로
⑦ 동시 프로세스 상한 ⑧ 외부 호출 0번이면 그렇게 밝힌다(거짓 표시 금지).
"""
import json
import subprocess
import threading
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import settings
from backend.demo_state import get_state
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.llm import schemas
from backend.llm.client import LlmUnavailable

client = TestClient(app_module.app)
H = {"X-Role": "SUP"}
Q_ROUTE = "쿨런트가 뭐야?"                     # 분류(route) 단계를 부르는 질문 (ROUTE_POLICY=llm_guarded)
Q_OPS = "어제 야간 VF2-01 몇 번 멈췄어?"       # 운영 질문 — 규칙으로 처리되고 문장 다듬기(phrase)만 LLM을 부른다 (ROUTE_POLICY=rescue)
Q_ALARM = "552 알람 뜨면 어떻게 해?"           # 알람 번호 질문 — 규칙·카드만, LLM 안 부름
HAIKU = "claude-haiku-5-5"


class Runner:
    """가짜 `claude` 실행기: 호출 수를 세고, mode에 따라 시간 초과를 던지거나 읽을 수 없는 글을 돌려준다."""

    def __init__(self, mode="timeout"):
        self.mode, self.calls = mode, []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        self.calls.append(sorted((sch.get("properties") or {}).keys()))
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        return SimpleNamespace(returncode=0, stdout="JSON이 아닌 글", stderr="")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    get_state().reset()
    for k, v in {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "ROUTE_POLICY": "llm_guarded", "DOC_GATE": "veto", "PARSE_V8": "1",
                 "NUM_MATCH": "value", "EXTERNAL_LLM_APP": "1"}.items():
        monkeypatch.setenv(k, v)
    local_calls = []

    def local_handler(req):   # 로컬 Qwen 쪽 — 불리면 기록하고 연결 실패로 돌려준다
        local_calls.append(str(req.url))
        raise httpx.ConnectError("시험: 로컬 서버 없음")

    C.use_transport(httpx.MockTransport(local_handler))
    yield local_calls
    C.use_transport(None)
    CC.use_runner(None)
    get_state().reset()


def post(q=Q_ROUTE, **extra):
    return client.post("/api/assistant/chat", json={"question": q, **extra}, headers=H)


# ------------------------------------------------------------------ ① 선택이 없으면 그대로
def test_default_request_is_local_and_never_touches_the_external_runner(env):
    runner = Runner()
    CC.use_runner(runner)
    r = post(Q_ALARM)
    assert r.status_code == 200 and "llm" not in r.json() and "external_note" not in r.json()
    r2 = post(Q_ALARM, llm="local")
    assert r2.status_code == 200 and "llm" not in r2.json()
    assert runner.calls == []


# ------------------------------------------------------------------ ② 서버 스위치가 꺼져 있으면 한 글자도 안 나감
def test_claude_choice_is_refused_when_the_server_switch_is_off(monkeypatch, env):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    runner = Runner()
    CC.use_runner(runner)
    r = post(llm="claude")
    assert r.status_code == 503 and r.json()["code"] == "EXTERNAL_LLM_DISABLED" and r.json()["detail"] == {}
    assert runner.calls == [] and env == []


def test_unknown_llm_value_is_a_validation_error():
    r = post(llm="gpt")
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"


# ------------------------------------------------------------------ ③ 요청 안에서만 바뀐다
def test_override_changes_settings_only_inside_the_request():
    base = settings()
    assert base.llm_provider == "local" and not base.claude_app and not base.llm_label.startswith("외부")
    with EXT.external_request("claude") as ext:
        s = settings()
        assert ext is not None and EXT.override() == "claude"
        assert s.claude_app and s.llm_provider == "claude" and s.claude_model == HAIKU and s.claude_effort == "medium" and s.claude_via == "api"
        assert s.llm_label == "외부 LLM(Claude Haiku 5.5)" and s.read_s == 60 and s.budget_s == 120 and s.claude_cost_cap_usd == 0
    assert EXT.override() is None and not settings().claude_app and settings().llm_provider == "local"


def test_override_is_ignored_when_the_server_switch_is_off(monkeypatch):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    with EXT.external_request("claude"):
        s = settings()
        assert not s.claude_app and s.llm_provider == "local"


def test_local_choice_creates_no_request_state():
    with EXT.external_request("local") as ext, EXT.external_request(None) as ext2:
        assert ext is None and ext2 is None and EXT.override() is None


# ------------------------------------------------------------------ ④ 재료 단계 실패 = 오류 (자동 로컬 전환 없음)
@pytest.mark.parametrize("mode", ["timeout", "garbage"])
def test_material_stage_failure_ends_with_an_error_and_never_falls_back_to_local(env, mode):
    runner = Runner(mode)
    CC.use_runner(runner)
    r = post(Q_ROUTE, llm="claude")
    j = r.json()
    assert r.status_code == 503 and j["code"] == "EXTERNAL_LLM_UNAVAILABLE", j
    assert j["detail"]["job"] == "route" and j["detail"]["reason"]
    assert len(runner.calls) == 1            # 재요청 없이 바로 끝남
    assert env == []                         # 로컬 Qwen을 부르지 않았다
    assert EXT.override() is None            # 다음 요청에 새지 않는다
    assert post(Q_ALARM).status_code == 200  # 다음(기본) 요청은 멀쩡하다


# ------------------------------------------------------------------ ⑤ 다듬기 단계 실패 = 원문 폴백 + 표시
def test_polish_stage_failure_answers_with_the_original_and_says_so(monkeypatch, env):
    monkeypatch.setenv("LLM_JOBS", "write")
    monkeypatch.setenv("ROUTE_POLICY", "rescue")
    runner = Runner()
    CC.use_runner(runner)
    r = post(Q_OPS, llm="claude")
    j = r.json()
    assert r.status_code == 200, j
    assert j["llm"]["provider"] == "claude" and j["llm"]["label"] == "외부 LLM(Claude Haiku 5.5)" and j["llm"]["calls"] >= 1
    assert j["llm"]["partial_failure"] and "원문" in j["external_note"]
    assert j["conclusion"] and j["status"] == "답변"
    assert env == []


# ------------------------------------------------------------------ ⑧ 외부 호출 0번이면 그렇게 밝힌다
def test_rules_only_answer_reports_zero_external_calls():
    runner = Runner()
    CC.use_runner(runner)
    r = post(Q_ALARM, llm="claude")
    j = r.json()
    assert r.status_code == 200 and j["llm"]["provider"] == "claude" and j["llm"]["calls"] == 0
    assert runner.calls == []


# ------------------------------------------------------------------ ③ 모든 호출 종류가 외부 경로로 간다 (수용 기준 3)
def test_every_job_kind_goes_to_the_external_runner_when_chosen(env):
    seen = []

    def run(cmd, stdin_text, timeout):   # 성공 응답 — 스키마에 맞는 값을 돌려준다
        props = sorted((json.loads(cmd[cmd.index("--json-schema") + 1]).get("properties") or {}).keys())
        seen.append(props)
        payload = {"faithful": True, "problem": ""} if "faithful" in props else {"answer": "답이에요."}
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1, "total_cost_usd": 0.01,
               "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {HAIKU: {"inputTokens": 10}}, "structured_output": payload}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")

    CC.use_runner(run)
    msgs = [{"role": "system", "content": "시스템 지시"}, {"role": "user", "content": "질문 글"}]
    with EXT.external_request("claude") as ext:
        judged = C.chat_json(msgs, schemas.ANSWER_FAITH, "answer_faith", 120)                                  # 뜻 판정(JSON 스키마 길)
        written = C.chat_json(msgs, schemas.WRITE_ANSWER, "write_answer", 400, grammar="root ::= x")          # 새 글 쓰기(문법 길 — 외부에서는 문법을 안 보내고 사후 검사가 막는다)
    assert judged == {"faithful": True, "problem": ""} and written == {"answer": "답이에요."}
    assert len(seen) == 2 and ext.calls == 2 and ext.failures == [] and env == []   # 로컬 Qwen은 한 번도 안 불렸다
    assert all("grammar" not in " ".join(x) for x in seen)


# ------------------------------------------------------------------ ⑥ 평가 경로의 잠금은 예전 그대로
def test_evaluation_path_still_requires_its_locks(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    for k in ("MOM_EXTERNAL_LLM_OK", "MOM_USAGE_LEDGER"):
        monkeypatch.delenv(k, raising=False)
    CC.use_runner(Runner())
    assert "잠금" in CC.gate_problem(settings())
    monkeypatch.setenv("MOM_EXTERNAL_LLM_OK", "1")
    assert "사용량 기록 경로" in CC.gate_problem(settings())
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "usage_t.jsonl"))
    monkeypatch.setenv("MOM_CLAUDE_MODEL", "claude-opus-5-5")
    assert CC.gate_problem(settings()) is None


def test_app_path_needs_no_env_lock_or_ledger():
    CC.use_runner(Runner())
    with EXT.external_request("claude"):
        assert CC.gate_problem(settings()) is None


# ------------------------------------------------------------------ ⑦ 동시 프로세스 상한
def test_process_cap_refuses_the_extra_call(monkeypatch):
    monkeypatch.setenv("EXTERNAL_PROC_LIMIT", "1")
    s = settings()
    assert s.proc_limit == 1
    with CC._proc_slot(s, 1.0):
        with pytest.raises(LlmUnavailable, match="동시 처리 한도"):
            with CC._proc_slot(s, 0.2):
                pass
    with CC._proc_slot(s, 0.2):   # 자리가 나면 다시 들어간다
        pass


def test_process_cap_is_released_even_when_the_run_fails(monkeypatch):
    monkeypatch.setenv("EXTERNAL_PROC_LIMIT", "1")
    CC.use_runner(Runner())
    with EXT.external_request("claude") as ext:
        for _ in range(3):   # 상한 1인데 3번 연달아 실패해도 자리가 새지 않는다
            with pytest.raises(LlmUnavailable):
                CC.chat_json_claude([{"role": "user", "content": "x"}], {"type": "object", "properties": {}, "additionalProperties": False}, "phrase", 50)
        assert ext.calls == 3 and len(ext.failures) == 3


# ------------------------------------------------------------------ 상태 표시 (/api/health)
def test_health_reports_the_external_switch(monkeypatch):
    CC.use_runner(Runner())
    h = client.get("/api/health").json()
    ex = h["external_llm"]
    assert ex["server_switch"] is True and ex["available"] is True and ex["model"] == HAIKU and ex["label"] == "외부 LLM(Claude Haiku 5.5)"
    assert ex["effort"] == "medium" and ex["proc_limit"] == 8 and set(ex["counters"]) >= {"calls", "usd_est"}
    assert h["llm_status"]["flags"]["external_app"] is True
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    h2 = client.get("/api/health").json()
    assert h2["external_llm"]["server_switch"] is False and h2["external_llm"]["available"] is False and "model" not in h2["external_llm"]
    assert h2["llm_status"]["flags"]["external_app"] is False
