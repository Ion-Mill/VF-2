"""Claude Code CLI 방식 시험 (2026-10-14, API 키 대신 이 PC의 구독 로그인). 진짜 `claude`는 부르지 않고 가짜 실행기를 끼운다.

지키는 것: ① 명령줄이 "순수 LLM 호출"(도구·MCP·스킬·설정·세션 저장 끔, --bare 아님)이다 ② 자식 환경에서 CLAUDE*·ANTHROPIC*가 빠진다
③ 요청 모델과 다른 모델이 답하면 실패 ④ 한도 오류는 LlmUnavailable, 연속 3번이면 멈춘다 ⑤ 기록에 글 내용이 없다 ⑥ 실행 파일 찾기.
"""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.config import ROOT, settings
from backend.llm import claude_cli as CLI
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import schemas
from backend.llm.client import LlmBadOutput, LlmUnavailable

SYSTEM = "시스템 지시: JSON으로만 답한다."
MSG = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "질문 글: 992 뜨면?"}]
OPUS = "claude-opus-5-5"


def result(payload=None, model=OPUS, usd=0.0123, text=None, **extra):
    d = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 4000, "duration_api_ms": 2500, "num_turns": 1,
         "total_cost_usd": usd, "usage": {"input_tokens": 1500, "output_tokens": 220, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 0},
         "modelUsage": {model: {"inputTokens": 1500}}}
    if payload is not None:
        d["structured_output"] = payload
    if text is not None:
        d["result"] = text
    d.update(extra)
    return d


class FakeRun:
    """CLI 실행기 가짜: 호출을 기록하고 정해 둔 결과(dict → 표준 출력 JSON, 예외 → 던짐, SimpleNamespace → 그대로)를 차례로 돌려준다."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"cmd": cmd, "stdin": stdin_text, "timeout": timeout})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        if isinstance(r, dict):
            return SimpleNamespace(returncode=0, stdout=json.dumps(r, ensure_ascii=False), stderr="")
        return r


@pytest.fixture
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("MOM_CLAUDE_VIA", "cli")
    monkeypatch.setenv("MOM_CLAUDE_MODEL", OPUS)
    monkeypatch.setenv("MOM_CLAUDE_EFFORT", "low")
    monkeypatch.setenv("MOM_CLAUDE_COST_CAP_USD", "20")
    monkeypatch.setenv("MOM_EXTERNAL_LLM_OK", "1")
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "usage_t.jsonl"))
    fake = FakeRun()
    CC.use_runner(fake)
    yield fake, tmp_path
    CC.use_runner(None)


def call(schema=schemas.WRITE_ANSWER, name="write_answer", max_tokens=400):
    return C.chat_json(MSG, schema, name, max_tokens)


def flag_value(cmd, flag):
    return cmd[cmd.index(flag) + 1]


# ------------------------------------------------------------------ 명령줄
def test_command_is_a_plain_llm_call_with_everything_else_off(cli):
    fake, _ = cli
    fake.replies.append(result({"answer": "답이에요."}))
    assert call() == {"answer": "답이에요."}
    cmd, stdin = fake.calls[0]["cmd"], fake.calls[0]["stdin"]
    assert "-p" in cmd and flag_value(cmd, "--output-format") == "json"
    assert flag_value(cmd, "--model") == OPUS and flag_value(cmd, "--effort") == "low"
    assert flag_value(cmd, "--system-prompt") == SYSTEM
    assert flag_value(cmd, "--tools") == "" and flag_value(cmd, "--setting-sources") == ""     # 도구·설정 모두 끔
    for must in ("--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"):
        assert must in cmd
    assert "--bare" not in cmd                                                                  # --bare는 구독 로그인을 읽지 않는다
    for bad in ("--allowedTools", "--dangerously-skip-permissions", "--add-dir", "--mcp-config", "--resume", "--continue", "--fallback-model"):
        assert bad not in cmd
    assert stdin == "질문 글: 992 뜨면?"                                                          # 사용자 글은 stdin, 명령줄에 없음
    assert "992" not in " ".join(cmd)


def test_schema_in_the_command_has_no_unsupported_constraints(cli):
    fake, _ = cli
    fake.replies.append(result({"answerable": True, "line_ids": ["L2"], "lead": "요약"}))
    call(schemas.select(["L1", "L2"]), "select")
    sch = json.loads(flag_value(fake.calls[0]["cmd"], "--json-schema"))
    txt = json.dumps(sch)
    assert "maxItems" not in txt and "maxLength" not in txt
    assert sch["additionalProperties"] is False and sch["properties"]["line_ids"]["items"]["enum"] == ["L1", "L2"]


def test_no_sampling_or_api_only_fields_in_the_command(cli):
    fake, _ = cli
    fake.replies.append(result({"answer": "x"}))
    call()
    joined = " ".join(fake.calls[0]["cmd"])
    for bad in ("temperature", "top_p", "seed", "grammar", "presence", "chat_template", "cache_prompt"):
        assert bad not in joined


def test_read_timeout_follows_the_settings(cli, monkeypatch):
    fake, _ = cli
    monkeypatch.setenv("LLM_READ_S", "60")
    fake.replies.append(result({"answer": "x"}))
    call()
    assert fake.calls[0]["timeout"] == 60


# ------------------------------------------------------------------ 환경
def test_clean_env_drops_claude_and_anthropic_names_and_keeps_the_rest(monkeypatch):
    src = {"PATH": "p", "USERPROFILE": "u", "APPDATA": "a", "CLAUDECODE": "1", "CLAUDE_CODE_MESSAGING_TOKEN": "t", "CLAUDE_EFFORT": "high",
           "claude_lower": "x", "ANTHROPIC_API_KEY": "sk-ant-zzz", "ANTHROPIC_BASE_URL": "u", "MOM_USAGE_LEDGER": "l"}
    out = CLI.clean_env(src)
    assert out == {"PATH": "p", "USERPROFILE": "u", "APPDATA": "a", "MOM_USAGE_LEDGER": "l"}
    assert "CLAUDECODE" in src                                   # 원본은 건드리지 않는다
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-zzz")
    assert "ANTHROPIC_API_KEY" not in CLI.clean_env()           # 구독이 아니라 API 요금이 나가는 것을 막는다


def test_real_runner_passes_a_cleaned_env_and_a_cwd_outside_the_repo(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-zzz")
    monkeypatch.setenv("MOM_CLAUDE_CWD", str(tmp_path / "cwd"))
    CLI.run(["claude", "-p"], "안녕", 5)
    assert not any(k.upper().startswith(("CLAUDE", "ANTHROPIC")) for k in seen["env"])
    cwd = Path(seen["cwd"])
    assert cwd.is_dir() and ROOT not in cwd.parents and cwd != ROOT                              # 저장소의 CLAUDE.md·규칙이 읽히지 않는다
    assert seen["input"] == "안녕" and seen["timeout"] == 5 and seen["capture_output"] is True


def test_default_work_dir_is_outside_the_repo():
    assert ROOT not in CLI.DEFAULT_CWD.parents


# ------------------------------------------------------------------ 결과 읽기
def test_structured_output_is_preferred_and_result_text_is_the_fallback(cli):
    fake, _ = cli
    fake.replies += [result({"answer": "구조화"}, text='{"answer": "글"}'), result(text='{"answer": "글에서"}'),
                     result(text='```json\n{"answer": "울타리"}\n```')]
    assert [call()["answer"] for _ in range(3)] == ["구조화", "글에서", "울타리"]


def test_parse_result_accepts_one_line_and_last_line_and_arrays():
    d = result({"a": 1})
    assert CLI.parse_result(json.dumps(d))["structured_output"] == {"a": 1}
    assert CLI.parse_result("경고 한 줄\n" + json.dumps(d))["total_cost_usd"] == 0.0123
    assert CLI.parse_result(json.dumps([{"type": "system"}, d]))["type"] == "result"
    for bad in ("", "   ", "그냥 글", "[1, 2]"):
        with pytest.raises(ValueError):
            CLI.parse_result(bad)


@pytest.mark.parametrize("d,why", [(result(), "구조화 결과 없음"), (result(text="그냥 문장"), "구조화 결과를 읽지 못함"),
                                   (result({"answer": "가" * 400}), "스키마 제약 위반"), (result({"nope": 1}), "필수 칸 없음")])
def test_unusable_results_are_bad_output(cli, d, why):
    fake, _ = cli
    fake.replies.append(d)
    with pytest.raises(LlmBadOutput, match=why):
        call()


def test_wrong_model_answering_is_a_failure_but_extra_background_model_is_fine(cli):
    fake, _ = cli
    fake.replies.append(result({"answer": "x"}, model="claude-sonnet-5-5"))
    with pytest.raises(LlmBadOutput, match="요청 모델과 다른 모델"):
        call()
    both = result({"answer": "x"})
    both["modelUsage"]["claude-haiku-5-5"] = {"inputTokens": 5}
    fake.replies.append(both)
    assert call() == {"answer": "x"}
    fake.replies.append(result({"answer": "x"}, model=OPUS + "[1m]"))
    assert call() == {"answer": "x"}


# ------------------------------------------------------------------ 오류
def test_process_failures_map_to_the_same_exceptions_as_the_local_client(cli):
    fake, _ = cli
    fake.replies += [subprocess.TimeoutExpired("claude", 60), OSError("없음"),
                     SimpleNamespace(returncode=1, stdout="", stderr="boom"),
                     SimpleNamespace(returncode=0, stdout="그냥 글", stderr=""),
                     result(is_error=True, subtype="error_during_execution", text="뭔가 잘못됨")]
    with pytest.raises(LlmUnavailable, match="시간 초과"):
        call()
    with pytest.raises(LlmUnavailable, match="실행 실패"):
        call()


def test_error_text_hides_key_shapes(cli):
    fake, _ = cli
    fake.replies.append(SimpleNamespace(returncode=1, stdout="", stderr="auth failed for sk-ant-api03-SECRETSECRET"))
    with pytest.raises(LlmBadOutput) as e:
        call()
    assert "SECRETSECRET" not in str(e.value) and "sk-ant-…" in str(e.value)


def test_limit_errors_stop_after_three_in_a_row(cli):
    fake, _ = cli
    limit = result(is_error=True, subtype="error", text="Claude usage limit reached. Your limit will reset at 5pm")
    fake.replies += [limit, limit, limit]
    for i in (1, 2, 3):
        with pytest.raises(LlmUnavailable, match=f"사용 한도·속도 제한 \\({i}/3\\)"):
            call()
    with pytest.raises(LlmUnavailable, match="차단기"):        # 네 번째는 프로세스를 띄우지도 않는다
        call()
    assert len(fake.calls) == 3


def test_a_success_resets_the_limit_counter(cli):
    fake, _ = cli
    limit = result(is_error=True, subtype="error", text="rate limit exceeded")
    fake.replies += [limit, limit, result({"answer": "x"}), limit, limit]
    for _ in range(2):
        with pytest.raises(LlmUnavailable):
            call()
    assert call() == {"answer": "x"}
    for _ in range(2):
        with pytest.raises(LlmUnavailable, match="사용 한도"):
            call()
    assert CC._limit_hits == 2


# ------------------------------------------------------------------ 기록·비용
def test_ledger_row_has_tokens_cost_and_version_but_no_text(cli):
    fake, tmp = cli
    fake.replies.append(result({"answer": "비밀 답 글입니다"}, usd=0.5))
    call(name="write_answer")
    raw = (tmp / "usage_t.jsonl").read_text(encoding="utf-8")
    row = json.loads(raw.splitlines()[0])
    assert row["via"] == "cli" and row["cli"] == "시험" and row["job"] == "write_answer" and row["model"] == OPUS
    assert row["in"] == 1500 and row["out"] == 220 and row["api_ms"] == 2500 and row["usd"] == 0.5 and row["models"] == [OPUS]
    assert "992" not in raw and "비밀 답 글" not in raw and "질문" not in raw and "시스템 지시" not in raw
    s = CC.ledger_summary()
    assert s["via"] == "cli" and s["calls"] == 1 and s["usd_equivalent"] == 0.5 and s["model_ms_p50"] == 2500


def test_cost_falls_back_to_the_price_table_when_the_cli_omits_it(cli):
    fake, tmp = cli
    d = result({"answer": "x"})
    del d["total_cost_usd"]
    fake.replies.append(d)
    call()
    row = json.loads((tmp / "usage_t.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["usd"] == pytest.approx(round(CC.cost_usd(OPUS, 1500, 220, 10, 0), 6))


def test_equivalent_cost_cap_stops_further_calls(cli):
    fake, tmp = cli
    (tmp / "usage_earlier.jsonl").write_text(json.dumps({"usd": 19.9}) + "\n", encoding="utf-8")
    fake.replies += [result({"answer": "x"}, usd=0.2), result({"answer": "x"})]
    call()
    with pytest.raises(LlmUnavailable, match="비용 상한"):
        call()
    assert len(fake.calls) == 1


# ------------------------------------------------------------------ 잠금·실행 파일
def test_cli_gate_needs_lock_ledger_and_a_claude_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("MOM_CLAUDE_VIA", "cli")
    monkeypatch.setenv("MOM_EXTERNAL_LLM_OK", "1")
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "usage_t.jsonl"))
    monkeypatch.setenv("MOM_CLAUDE_BIN", str(tmp_path / "없는파일.exe"))
    CC.use_runner(None)
    assert "실행 파일 없음" in CC.gate_problem(settings())
    assert C.probe(settings())["alive"] is False
    exe = tmp_path / "claude.exe"
    exe.write_text("x")
    monkeypatch.setenv("MOM_CLAUDE_BIN", str(exe))
    assert CC.gate_problem(settings()) is None and C.probe(settings())["alive"] is True
    monkeypatch.delenv("MOM_EXTERNAL_LLM_OK")
    assert "잠금" in CC.gate_problem(settings())


def test_find_bin_prefers_env_then_the_newest_extension(monkeypatch, tmp_path):
    monkeypatch.delenv("MOM_CLAUDE_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for ide, ver in ((".cursor", "2.1.296"), (".cursor", "2.1.1000"), (".vscode", "2.0.9")):
        p = tmp_path / ide / "extensions" / f"anthropic.claude-code-{ver}-win32-x64" / "resources" / "native-binary"
        p.mkdir(parents=True)
        (p / "claude.exe").write_text("x")
    assert "2.1.1000" in str(CLI.find_bin())            # 숫자로 비교한다 (글자 순서면 2.1.296이 이긴다)
    own = tmp_path / "내것.exe"
    own.write_text("x")
    monkeypatch.setenv("MOM_CLAUDE_BIN", str(own))
    assert CLI.find_bin() == own
    monkeypatch.setenv("MOM_CLAUDE_BIN", str(tmp_path / "없음.exe"))
    assert CLI.find_bin() is None                        # 지정했는데 없으면 다른 것으로 슬쩍 바꾸지 않는다


def test_cli_version_and_auth_status_return_only_safe_fields(monkeypatch):
    def fake_run(cmd, **kw):
        if cmd[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout="2.1.296 (Claude Code)\n", stderr="")
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
            {"loggedIn": True, "authMethod": "claude.ai", "email": "a@b.c", "orgName": "조직", "orgId": "x", "subscriptionType": "max"}))
    monkeypatch.setattr(subprocess, "run", fake_run)
    CLI._version_cache.clear()
    assert CLI.cli_version("claude") == "2.1.296 (Claude Code)"
    st = CLI.auth_status("claude")
    assert st == {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "max"}
    assert "email" not in st and "orgName" not in st


# ------------------------------------------------------------------ 진단 칸 길이 (2026-10-14 E0(b): Claude가 missing을 103자로 써서 LLM 오류 10%가 났다)
def test_overlong_diag_field_is_trimmed_and_counted_but_answer_text_is_not(cli):
    fake, tmp = cli
    fake.replies.append(result({"answers": False, "missing": "가" * 103}))
    out = call(schemas.VERIFY, "verify")
    assert out == {"answers": False, "missing": "가" * 80}                   # 문법이 쓰는 순간에 막던 길이와 같은 결과
    s = CC.ledger_summary()
    assert s["calls"] == 1 and s["trimmed_diag_fields"] == 1                # 자른 줄은 호출 수에 들어가지 않는다
    rows = [json.loads(x) for x in (tmp / "usage_t.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r.get("kind") for r in rows] == [None, "trim"] and rows[1]["job"] == "verify"
    fake.replies.append(result({"answer": "가" * 400}))                      # 답으로 나가는 글은 자르지 않고 실패
    with pytest.raises(LlmBadOutput, match="스키마 제약 위반"):
        call()


def test_trim_diag_only_touches_diag_keys():
    sch = {"type": "object", "properties": {"problem": {"type": "string", "maxLength": 5}, "lead": {"type": "string", "maxLength": 5}}}
    out, n = CC.trim_diag({"problem": "abcdefgh", "lead": "abcdefgh"}, sch)
    assert out == {"problem": "abcde", "lead": "abcdefgh"} and n == 1
    assert CC.trim_diag({"problem": 3}, sch) == ({"problem": 3}, 0) and CC.trim_diag([1], sch) == ([1], 0)
