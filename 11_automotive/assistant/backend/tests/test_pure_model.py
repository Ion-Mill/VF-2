"""순수 길 본 답변 모델 선택 PURE_MODEL 시험 (2026-10-19). 기획: 261003_창민/Haiku_전환_기획_20261019.md

앱 외부 요청(채팅)의 모델은 늘 Sonnet 5.5였다. PURE_MODEL로 **순수 길 본 답변(작업 이름 pure_answer, PURE_RETRY의 두 번째 호출 포함)만** 다른 모델로 부른다.
**코드 기본은 Haiku 5.5**(사용자 결정 2026-10-19): PURE_MODEL 줄이 없으면 `claude-haiku-5-5`, 줄이 있고 비어 있거나(`PURE_MODEL=`) `claude-sonnet-5-5`면 Sonnet(예전 동작).
판정·다시 쓰기·옛 길·compose 같은 나머지 호출은 늘 Sonnet이다. 진짜 `claude`는 부르지 않는다 — 가짜 실행기(`CC.use_runner`)는 명령의 `--model` 값을 읽어 **요청받은 모델 이름으로** 답한다.
시험 공통 고정물(conftest)은 PURE_MODEL을 빈 줄로 고정해 두므로(기존 시험은 Sonnet 모드), 이 파일의 "줄 없음" 시험은 `unset()`으로 환경변수를 지우고 `.env` 읽기도 막는다.
지키는 것: ① 줄 없음 → pure_answer만 Haiku, 나머지 17종 Sonnet ② 빈 줄·Sonnet 명시 → 모든 호출의 명령이 예전과 한 글자도 다르지 않다 ③ 두 번째(넓게 다시 본) 호출도 같은 모델
④ 모르는 이름은 비운 것(Sonnet)으로 보고 호출이 막히지 않는다 ⑤ 평가 경로(MOM_CLAUDE_MODEL)·로컬 요청은 기본값이 Haiku여도 영향이 없다 ⑥ 모델 불일치 검사가 그대로 유효하다
⑦ 이름표(mode)는 Sonnet이면 예전 글자 그대로, Haiku면 실제 모델 이름 ⑧ `.env.example`의 줄은 코드 기본값과 같다.
"""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import config as CFG
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.llm import claude_cli as CLI
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS

client = TestClient(app_module.app)
SONNET, HAIKU, OPUS = "claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"
Q = "자주 뜬다고 쳐 주는 기준이 며칠에 몇 번이야?"       # 신호·안전 낱말이 없는 순수 길 질문 (조각 12개, 30개로 넓히면 34개 — test_pure_retry와 같다)
Q_CARD = "2075 알람 뭐야"                                 # 알람 카드 길 (CARD_REWRITE=1이면 simplify → faith)
PURE_PROPS = ("answer", "cited", "insufficient")
MODE_TAIL = "순수 연결 (검사 없음, 원문 출처 표기 차단만)"
# chat_json을 부르는 작업 이름 전부 (compose_*는 문장 입구 /compose/{kind})
NAMES = ["pure_answer", "simplify", "faith", "pick", "route", "select", "verify", "phrase", "write_answer", "answer_faith", "lead_faith",
         "safe_simplify", "safe_faith", "compose_shift_report", "compose_daily_report", "compose_work_order", "compose_guide_card", "compose_briefing"]
OTHERS = [n for n in NAMES if n != "pure_answer"]
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
MESSAGES = [{"role": "system", "content": "시험 지시문"}, {"role": "user", "content": "시험 질문"}]


def arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


def soft(s: str) -> str:
    return re.sub(r"다(?=[.\s]|$)", "어요", s)   # 가짜 "해요체" — 숫자·영문·꼬리표·조건 말은 그대로라 카드 검사를 지난다


class Echo:
    """가짜 `claude` 실행기: 명령의 --model을 읽어 modelUsage에 **그 이름으로** 답한다(answer_as를 주면 늘 그 이름으로 답해 불일치를 만든다).
    스키마 칸으로 호출 종류를 가린다: 순수 길(answer·cited·insufficient)은 first/second("answer"·"insufficient")대로, 다시 쓰기(texts)는 해요체로, 뜻 판정은 통과, 그 밖은 {"ok": true}."""

    def __init__(self, first="answer", second="answer", answer_as=None):
        self.cmds, self.first, self.second, self.answer_as = [], first, second, answer_as

    def __call__(self, cmd, stdin_text, timeout):
        self.cmds.append(list(cmd))
        props = tuple(sorted((json.loads(arg(cmd, "--json-schema")).get("properties") or {}).keys()))
        if props == PURE_PROPS:
            wide = PURE.RETRY_NOTE in arg(cmd, "--system-prompt")
            insufficient = (self.second if wide else self.first) == "insufficient"
            n = max([int(x) for x in re.findall(r"\[C(\d+)\]", stdin_text)] or [0])
            so = {"answer": "넓게 본 답" if wide else "처음 답", "cited": [] if insufficient else [f"C{n}"], "insufficient": insufficient}
        elif props == ("texts",):
            so = {"texts": [soft(x) for x in re.findall(r"^\d+\. (.*)$", stdin_text, re.M)]}
        elif "same_meaning" in props:
            so = {"same_meaning": True, "problem": ""}
        else:
            so = {"ok": True}
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {(self.answer_as or arg(cmd, "--model")): {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")

    def models(self, props=None):
        """받은 명령들의 --model (props를 주면 그 스키마 칸의 호출만)."""
        return [arg(c, "--model") for c in self.cmds if props is None or tuple(sorted(json.loads(arg(c, "--json-schema"))["properties"])) == props]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    get_state().reset()
    AS.clear()
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")

    def no_local(req):   # 로컬 Qwen 쪽 — 불리면 연결 실패
        raise httpx.ConnectError("시험: 로컬 서버 없음")
    C.use_transport(httpx.MockTransport(no_local))
    yield
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def unset(monkeypatch):
    """PURE_MODEL 줄이 **없는** 상태: 환경변수를 지우고(conftest가 빈 줄로 고정해 둠) .env 읽기도 막는다 (코드 기본값이 적용된다)."""
    monkeypatch.delenv("PURE_MODEL", raising=False)
    monkeypatch.setattr(CFG, "_dotenv", lambda: {})


def call(name, runner):
    """외부 Claude 요청 안에서 chat_json 한 번 (실제 입구 그대로). 받은 명령은 runner.cmds[-1]."""
    CC.use_runner(runner)
    with EXT.external_request("claude"):
        return C.chat_json(MESSAGES, SCHEMA, name, 50)


def expected_cmd(model, effort="medium"):
    """지금(키 없던 때)의 명령 — build_cmd가 만드는 모양을 그대로 (CC._call_cli와 같은 이진 파일 식)."""
    return CLI.build_cmd(CLI.find_bin() or Path("claude"), model, effort, MESSAGES[0]["content"], CC.prepare_schema(SCHEMA))


def chat(monkeypatch, runner, model="", retry="0", **env):
    """채팅(순수 길) 한 번: /api/assistant/chat에 llm=claude. 말투·형식 스위치는 꺼짐(지금 글자). model=None이면 PURE_MODEL 줄 없음(코드 기본값)."""
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXPAND", "1")
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    if model is None:
        unset(monkeypatch)
    else:
        monkeypatch.setenv("PURE_MODEL", model)
    monkeypatch.setenv("PURE_RETRY", retry)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    CC.use_runner(runner)
    return client.post("/api/assistant/chat", json={"question": Q, "llm": "claude"}, headers={"X-Role": "SUP"})


# ------------------------------------------------------------------ 설정
def test_code_default_is_haiku_when_there_is_no_line_and_sonnet_when_the_line_is_empty(monkeypatch):
    assert CFG.PURE_MODEL_DEFAULT == HAIKU
    assert Settings.__dataclass_fields__["pure_model"].default == ""     # Settings를 직접 만드는 코드는 예전 동작(Sonnet)을 그대로 받는다
    unset(monkeypatch)                                                   # 줄 없음 + .env 없음 → 기본값 Haiku
    assert settings().pure_model == HAIKU and settings().flags()["pure_model"] == HAIKU
    monkeypatch.setenv("PURE_MODEL", "")                                 # 빈 줄 → Sonnet
    assert settings().pure_model == "" and settings().flags()["pure_model"] == ""
    monkeypatch.setenv("PURE_MODEL", SONNET)
    assert settings().pure_model == SONNET and settings().flags()["pure_model"] == SONNET
    monkeypatch.setenv("PURE_MODEL", HAIKU)
    assert settings().pure_model == HAIKU and settings().flags()["pure_model"] == HAIKU


@pytest.mark.parametrize("raw, want", [
    (HAIKU, HAIKU), (SONNET, SONNET), (OPUS, OPUS),
    ("  Claude-Haiku-5-5  ", HAIKU), ("CLAUDE-HAIKU-5-5", HAIKU),                                   # 앞뒤 공백·대소문자는 정리한 뒤 비교한다
    ("", ""), ("   ", ""), ("claude-haiku", ""), ("haiku", ""), ("foo", ""), ("claude-haiku-5", ""), ("claude-haiku-5-5x", ""),
    ("claude-haiku-5-5 claude-sonnet-5-5", ""), ("claude-haiku-4-5", ""), ("gpt-4", "")])        # 오타·가격표에 없는 이름은 비운 것으로
def test_value_is_trimmed_lowercased_and_unknown_names_become_empty(monkeypatch, raw, want):
    monkeypatch.setenv("PURE_MODEL", raw)
    assert settings().pure_model == want


@pytest.mark.parametrize("dotenv, want", [
    ({}, HAIKU),                                   # .env에 줄이 없다 -> 기본값 Haiku
    ({"MOM_BACKEND_URL": "http://x"}, HAIKU),      # 다른 줄만 있다 -> 기본값 Haiku
    ({"PURE_MODEL": HAIKU}, HAIKU),
    ({"PURE_MODEL": ""}, ""),                      # `PURE_MODEL=` -> 비운 줄 -> Sonnet
    ({"PURE_MODEL": SONNET}, SONNET),
    ({"PURE_MODEL": "haiku"}, "")])                # 오타 -> 비움(Sonnet)
def test_dotenv_line_is_read_and_a_missing_line_differs_from_an_empty_one(monkeypatch, dotenv, want):
    monkeypatch.delenv("PURE_MODEL")
    monkeypatch.setattr(CFG, "_dotenv", lambda: dict(dotenv))
    assert settings().pure_model == want


def test_allowed_names_match_the_price_table_and_the_job_name_matches():
    assert set(CFG.CLAUDE_MODEL_NAMES) == set(CC.PRICES)                # 두 곳(순환 import를 피해 따로 둠)이 어긋나면 PURE_MODEL이 거르거나 막는다
    assert CC.PURE_ANSWER_JOB == PURE.JOB == "pure_answer"
    assert all(n in CC.PRICES for n in (SONNET, HAIKU)) and CFG.CLAUDE_MODEL_NAMES[HAIKU] == "Claude Haiku 5.5" and CFG.CLAUDE_MODEL_NAMES[SONNET] == "Claude Sonnet 5.5"


def test_env_example_line_equals_the_code_default_with_its_comment_on_the_line_above():
    lines = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8").splitlines()
    mine = [l for l in lines if l.startswith("PURE_MODEL=")]
    assert mine == [f"PURE_MODEL={CFG.PURE_MODEL_DEFAULT}"]             # 예시 줄 = 코드 기본값 (복사해 쓴 .env도 같은 모델)
    i = lines.index(mine[0])
    assert lines[i - 1].startswith("#") and "PURE_MODEL=" in lines[i - 1] and "130" in lines[i - 1] and "Sonnet" in lines[i - 1]   # 윗줄 설명: 비우면 Sonnet, 대기 130초. 값 옆 `#`은 test_env_example이 막는다
    assert CFG._pure_model(mine[0].split("=", 1)[1]) == HAIKU


# ------------------------------------------------------------------ ① 빈 줄·Sonnet 명시면 모든 호출의 명령이 예전과 같다
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("value", ["", SONNET])
def test_empty_line_or_explicit_sonnet_leaves_every_call_exactly_as_it_was(monkeypatch, name, value):
    monkeypatch.setenv("PURE_MODEL", value)
    r = Echo()
    assert call(name, r) == {"ok": True}
    assert r.cmds == [expected_cmd(SONNET)]                             # 명령 전체가 같다 (--model claude-sonnet-5-5, --effort medium)
    assert arg(r.cmds[0], "--model") == SONNET and arg(r.cmds[0], "--effort") == "medium"


# ------------------------------------------------------------------ ② 줄 없음(기본)·Haiku 명시면 pure_answer만 Haiku, 같은 요청 안의 나머지는 Sonnet
@pytest.mark.parametrize("how", ["no_line", "explicit"])
def test_haiku_changes_only_the_model_value_of_pure_answer(monkeypatch, how):
    if how == "no_line":
        unset(monkeypatch)                                              # PURE_MODEL 줄이 없다 = 코드 기본값
    else:
        monkeypatch.setenv("PURE_MODEL", HAIKU)
    r = Echo()
    call("pure_answer", r)
    assert r.cmds == [expected_cmd(HAIKU)]                              # --model 값 하나만 다르다 (노력은 medium 그대로)
    assert arg(r.cmds[0], "--effort") == "medium"
    for name in OTHERS:
        r = Echo()
        call(name, r)
        assert r.cmds == [expected_cmd(SONNET)], name                   # 나머지 17종은 한 글자도 안 바뀐다


def test_one_request_mixes_the_two_models(monkeypatch):
    unset(monkeypatch)                                                  # 기본값만으로 섞인다
    r = Echo()
    CC.use_runner(r)
    with EXT.external_request("claude"):
        s = settings()
        for name in NAMES:
            C.chat_json(MESSAGES, SCHEMA, name, 50, s)                  # 같은 설정 하나로 부른다
        assert s.claude_model == SONNET and s.pure_model == HAIKU       # 설정 자체는 바뀌지 않는다 (복사본만 바꿔 쓴다)
    assert [arg(c, "--model") for c in r.cmds] == [HAIKU] + [SONNET] * len(OTHERS)


def test_explicit_sonnet_is_the_same_as_an_empty_line_and_not_the_same_as_no_line(monkeypatch):
    commands = {}
    for how in ("sonnet", "empty", "no_line"):
        if how == "no_line":
            unset(monkeypatch)
        else:
            monkeypatch.setenv("PURE_MODEL", SONNET if how == "sonnet" else "")
        r = Echo()
        call("pure_answer", r)
        commands[how] = r.cmds
    assert commands["sonnet"] == commands["empty"] == [expected_cmd(SONNET)]   # D10: 명시·빈 줄 = 예전 명령 그대로
    assert commands["no_line"] == [expected_cmd(HAIKU)]                       # D9: 줄이 없을 때만 Haiku


@pytest.mark.parametrize("bad", ["claude-haiku", "haiku", "foo", "claude-haiku-5", "Haiku 5.5"])
def test_unknown_names_do_not_block_any_call(monkeypatch, bad):
    monkeypatch.setenv("PURE_MODEL", bad)
    with EXT.external_request("claude"):
        assert settings().pure_model == "" and CC.gate_problem(settings()) is None     # "알 수 없는 모델"로 막히지 않는다
    for name in NAMES:
        r = Echo()
        assert call(name, r) == {"ok": True} and r.cmds == [expected_cmd(SONNET)], name


def test_usage_rows_carry_the_model_that_was_asked_for(monkeypatch):
    rows = []
    monkeypatch.setattr(CC, "_write_row", lambda row, usd: rows.append(row))
    unset(monkeypatch)
    for name in ("pure_answer", "faith"):
        call(name, Echo())
    assert [(r["job"], r["model"], r["models"]) for r in rows] == [("pure_answer", HAIKU, [HAIKU]), ("faith", SONNET, [SONNET])]   # 기록·환산 비용도 같은 모델


# ------------------------------------------------------------------ 끝에서 끝 (/chat)
@pytest.mark.parametrize("model", [None, HAIKU])                       # 줄 없음(코드 기본값) · 명시
def test_chat_pure_answer_asks_haiku_and_the_label_says_so(monkeypatch, model):
    r = Echo()
    resp = chat(monkeypatch, r, model)
    j = resp.json()
    assert resp.status_code == 200 and j["status"] == "답변" and j["conclusion"] == "처음 답"
    assert r.models() == [HAIKU] and arg(r.cmds[0], "--effort") == "medium"
    assert j["mode"] == f"외부 LLM(Claude Haiku 5.5) · {MODE_TAIL}"
    sonnet_cmd = Echo()
    chat(monkeypatch, sonnet_cmd, "")
    swapped = [HAIKU if x == SONNET else x for x in sonnet_cmd.cmds[0]]
    assert swapped == r.cmds[0]                                         # 같은 질문의 명령이 --model 값 하나만 다르다 (지시문·스키마·사용자 글 모두 같다)


@pytest.mark.parametrize("model", ["", SONNET])                         # 빈 줄 · Sonnet 명시
def test_chat_with_an_empty_line_or_sonnet_keeps_todays_label_and_sonnet(monkeypatch, model):
    r = Echo()
    j = chat(monkeypatch, r, model).json()
    assert r.models() == [SONNET]
    assert j["mode"] == f"외부 LLM(Claude Sonnet 5.5) · {MODE_TAIL}"    # 지금 글자 그대로 (test_pure_external과 같은 문장)


def test_chat_retry_second_call_uses_the_same_model(monkeypatch):
    r = Echo(first="insufficient", second="answer")
    j = chat(monkeypatch, r, None, retry="1").json()                    # 줄 없음(기본값)
    assert len(r.cmds) == 2 and r.models() == [HAIKU, HAIKU]            # 넓게 다시 본 호출도 pure_answer라 같은 모델
    assert [arg(c, "--effort") for c in r.cmds] == ["medium", "medium"]
    assert PURE.RETRY_NOTE in arg(r.cmds[1], "--system-prompt") and j["conclusion"] == "넓게 본 답"
    assert j["mode"].startswith("외부 LLM(Claude Haiku 5.5) · 순수 연결") and "넓게 다시 봄" in j["mode"]


def test_chat_retry_with_an_empty_line_stays_sonnet_twice(monkeypatch):
    r = Echo(first="insufficient", second="answer")
    j = chat(monkeypatch, r, "", retry="1").json()
    assert r.models() == [SONNET, SONNET] and j["mode"].startswith("외부 LLM(Claude Sonnet 5.5) · 순수 연결")


def test_card_rewrite_calls_stay_sonnet_while_the_key_is_on(monkeypatch):
    for k, v in {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "ASSISTANT_PROVIDER": "claude", "PARSE_V2": "1", "PARSE_V3": "1", "CARD_REWRITE": "1"}.items():
        monkeypatch.setenv(k, v)
    unset(monkeypatch)                                                  # 줄 없음 = 기본값 Haiku가 켜진 상태
    r = Echo()
    CC.use_runner(r)
    with EXT.external_request("claude"):
        a = A.answer(Q_CARD, "OPR", {})
    assert a["card_rewrite"] == {"applied": True, "reason": None}       # 실제 코드 길: 다시 쓰기(simplify) 뒤 뜻 판정(faith)이 모두 지났다
    assert len(r.cmds) == 2 and r.models() == [SONNET, SONNET]          # 안전 판정자 faith도 Sonnet


def test_old_route_call_stays_sonnet_while_the_key_is_on(monkeypatch):
    # 순수 길을 끈 외부 요청의 첫 호출은 분류(route) — 키가 있어도 Sonnet이다 (실행기가 {"ok": true}를 돌려줘 분류는 실패 → 503, 호출 명령만 본다)
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXTERNAL", "0")
    unset(monkeypatch)
    r = Echo()
    CC.use_runner(r)
    resp = client.post("/api/assistant/chat", json={"question": "쿨런트가 뭐야?", "llm": "claude"}, headers={"X-Role": "SUP"})
    assert resp.status_code == 503 and resp.json()["detail"]["job"] == "route"
    assert r.models() == [SONNET]


# ------------------------------------------------------------------ ⑤ 평가 경로는 영향이 없다
@pytest.mark.parametrize("eval_model, pure", [(OPUS, None), (SONNET, None), (OPUS, HAIKU), (HAIKU, SONNET), (SONNET, HAIKU)])   # None = 줄 없음(기본값 Haiku)
def test_evaluation_path_ignores_the_key(monkeypatch, tmp_path, eval_model, pure):
    for k, v in {"LLM_PROVIDER": "claude", "LLM_ENABLED": "1", "EXTERNAL_LLM_APP": "0", "MOM_CLAUDE_MODEL": eval_model,
                 "MOM_EXTERNAL_LLM_OK": "1", "MOM_USAGE_LEDGER": str(tmp_path / "usage_t.jsonl")}.items():
        monkeypatch.setenv(k, v)
    if pure is None:
        unset(monkeypatch)
    else:
        monkeypatch.setenv("PURE_MODEL", pure)
    s = settings()
    assert not s.claude_app and s.claude_model == eval_model and s.pure_label == s.llm_label == "외부 LLM(Claude, 실험)"   # 앱 요청이 아니면 이름표도 그대로
    r = Echo()
    CC.use_runner(r)
    assert C.chat_json(MESSAGES, SCHEMA, "pure_answer", 50) == {"ok": True}
    assert r.models() == [eval_model]                                   # PURE_MODEL이 아니라 MOM_CLAUDE_MODEL을 따른다


@pytest.mark.parametrize("how", ["no_line", "explicit"])
def test_local_request_ignores_the_key(monkeypatch, how):
    if how == "no_line":
        unset(monkeypatch)
    else:
        monkeypatch.setenv("PURE_MODEL", HAIKU)
    s = settings()                                                       # 외부 요청 밖: 로컬
    assert not s.claude_app and s.llm_label == "로컬 LLM" and s.pure_label == "로컬 LLM"


# ------------------------------------------------------------------ ⑥ 모델 불일치 검사는 그대로 유효하다
def test_a_different_model_answering_a_haiku_request_is_a_failure(monkeypatch):
    unset(monkeypatch)                                                  # 기본값 Haiku를 요청
    with pytest.raises(EXT.ExternalLlmFailure) as e:                    # pure_answer는 재료 단계라 실패하면 오류로 끝난다
        call("pure_answer", Echo(answer_as=SONNET))
    assert "요청 모델과 다른 모델이 답함" in e.value.reason
    assert call("simplify", Echo(answer_as=SONNET)) == {"ok": True}     # Sonnet을 요청한 호출에는 Sonnet이 답하는 것이 맞다


def test_chat_fails_when_haiku_is_asked_by_default_and_only_sonnet_answers(monkeypatch):
    resp = chat(monkeypatch, Echo(answer_as=SONNET), None)
    assert resp.status_code == 503 and resp.json()["code"] == "EXTERNAL_LLM_UNAVAILABLE" and resp.json()["detail"]["job"] == "pure_answer"


def test_chat_fails_when_sonnet_is_asked_and_only_haiku_answers(monkeypatch):
    resp = chat(monkeypatch, Echo(answer_as=HAIKU), "")
    assert resp.status_code == 503 and resp.json()["detail"]["job"] == "pure_answer"


def test_a_background_model_next_to_the_requested_one_is_fine(monkeypatch):
    class Both(Echo):
        def __call__(self, cmd, stdin_text, timeout):
            r = super().__call__(cmd, stdin_text, timeout)
            d = json.loads(r.stdout)
            d["modelUsage"] = {SONNET: {"inputTokens": 1}, arg(cmd, "--model"): {"inputTokens": 10}}   # 요청 모델 + 곁에서 쓴 다른 모델 (test_claude_cli와 같은 약속)
            return SimpleNamespace(returncode=0, stdout=json.dumps(d), stderr="")
    monkeypatch.setenv("PURE_MODEL", HAIKU)
    assert call("pure_answer", Both()) == {"ok": True}


# ------------------------------------------------------------------ ⑦ 이름표
def test_pure_label_follows_the_model_actually_asked_for(monkeypatch):
    with EXT.external_request("claude"):
        s = settings()
        assert s.pure_label == s.llm_label == "외부 LLM(Claude Sonnet 5.5)"                         # 빈 줄(시험 기본): 글자가 예전과 같다
        unset(monkeypatch)
        s = settings()
        assert s.pure_label == "외부 LLM(Claude Haiku 5.5)" and s.llm_label == "외부 LLM(Claude Sonnet 5.5)"   # 줄 없음 = 기본값 Haiku
        monkeypatch.setenv("PURE_MODEL", SONNET)
        assert settings().pure_label == settings().llm_label == "외부 LLM(Claude Sonnet 5.5)"
        monkeypatch.setenv("PURE_MODEL", HAIKU)
        s = settings()
        assert s.pure_label == "외부 LLM(Claude Haiku 5.5)" and s.llm_label == "외부 LLM(Claude Sonnet 5.5)"   # 전역 이름표(/health·단계 로그)는 안 바꾼다
        monkeypatch.setenv("PURE_MODEL", OPUS)
        assert settings().pure_label == "외부 LLM(Claude Opus 5.5)"
        monkeypatch.setenv("PURE_MODEL", "foo")
        assert settings().pure_label == "외부 LLM(Claude Sonnet 5.5)"                                # 모르는 이름은 비운 것으로
    odd = dataclasses.replace(settings(), claude_app=True, pure_model="claude-x-1")                    # 손으로 만든 설정: 표에 없으면 ID 그대로
    assert odd.pure_label == "외부 LLM(claude-x-1)"
