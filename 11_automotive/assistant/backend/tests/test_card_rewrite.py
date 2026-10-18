"""채팅 알람 카드 해요체 다시 쓰기(CARD_REWRITE) 시험 (2026-10-18, A2). 진짜 `claude`·네트워크·DB를 부르지 않는다(가짜 실행기).

배경: 알람 번호가 있는 질문은 프로그램이 카드(설명 문장 + ★ 점검 순서)를 원문 그대로 조립해 Claude를 거치지 않아, Claude가 쓴 다른 답과 말투가 달랐다.
채팅(외부 Claude 요청)에서만 Claude가 해요체로 다시 쓰되, 안전 때문에 하나라도 걸리면 원문 카드 그대로(fail closed)여야 한다.
지키는 것: ① 정상: 해요체로 바뀌고 ★ 번호·역할 표시·줄 수·숫자·영문 이름·[가상 운영 데이터] 줄·주의 문구가 그대로
② 걸림: 숫자가 바뀜 / 단계 수가 틀림 / 뜻 판정 거부 / 호출 실패 → 원문 카드 그대로 + 이유 기록 ③ 스위치 꺼짐·외부 요청 아님·알람 아닌 질문이면 Claude를 한 번도 안 부름.
"""
import json
import re
from types import SimpleNamespace

import pytest

from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.services import answer as A

SONNET = "claude-sonnet-5-5"
FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "EXTERNAL_LLM_APP": "1", "ASSISTANT_PROVIDER": "claude", "PARSE_V2": "1", "PARSE_V3": "1"}
NUM = re.compile(r"\d+(?:\.\d+)?")


def soft(s: str) -> str:
    """가짜 "해요체": 문장 끝 "…다"를 "…어요"로 (말은 어색해도 숫자·영문·꼬리표·조건 말은 그대로라 검사를 지난다)"""
    return re.sub(r"다(?=[.\s]|$)", "어요", s)


class CardRunner:
    def __init__(self, mode="good"):
        self.mode = mode
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append(props)
        if self.mode == "error":
            return SimpleNamespace(returncode=1, stdout="", stderr="시험: 실행기 오류")
        if props == ("texts",):
            segs = re.findall(r"^\d+\. (.*)$", stdin_text, re.M)
            out = [soft(s) for s in segs]
            if self.mode == "bad_number":
                out = [s.replace("1분", "2분") if "1분" in s else s for s in out]
            if self.mode == "drop_step":
                out = out[:-1]
            so = {"texts": out}
        else:                                                    # ("problem", "same_meaning") — 뜻 판정
            so = {"same_meaning": self.mode != "faith_no", "problem": "" if self.mode != "faith_no" else "시험: 뜻이 다름"}
        res = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(res, ensure_ascii=False), stderr="")


@pytest.fixture
def card(monkeypatch):
    for k, v in FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CARD_REWRITE", "1")
    yield
    CC.use_runner(None)


def ask(q="2075 알람 뭐야", external=True):
    if not external:
        return A.answer(q, "OPR", {})
    with EXT.external_request("claude"):
        return A.answer(q, "OPR", {})


def baseline(monkeypatch):
    """스위치를 끈 원문 카드 (같은 질문)"""
    monkeypatch.setenv("CARD_REWRITE", "0")
    a = ask()
    monkeypatch.setenv("CARD_REWRITE", "1")
    return a


def test_good_rewrite_changes_the_voice_and_keeps_the_structure(card, monkeypatch):
    base = baseline(monkeypatch)
    r = CardRunner("good")
    CC.use_runner(r)
    a = ask()
    assert a["card_rewrite"] == {"applied": True, "reason": None}
    assert a["steps"] != base["steps"] and a["conclusion"] != base["conclusion"]
    assert len(a["steps"]) == len(base["steps"]) == 8
    for old, new in zip(base["steps"], a["steps"]):
        assert re.match(r"^(★?\d+ \([^)]*\) )", new).group(1) == re.match(r"^(★?\d+ \([^)]*\) )", old).group(1)   # ★ 번호·역할 표시 그대로
        assert NUM.findall(old) == NUM.findall(new)                                                                  # 숫자 그대로
    assert "어요" in a["steps"][0] and "어요" in a["conclusion"]
    assert [e["cite"] for e in a["evidence"]] == [e["cite"] for e in base["evidence"]]                               # 출처 그대로
    assert len(r.calls) == 2 and r.calls[0] == ("texts",)                                                            # 다시 쓰기 1번 + 뜻 판정 1번


@pytest.mark.parametrize("mode,why", [("bad_number", "숫자"), ("drop_step", "항목"), ("faith_no", "뜻"), ("error", "")])
def test_any_failed_check_keeps_the_original_card(card, monkeypatch, mode, why):
    base = baseline(monkeypatch)
    CC.use_runner(CardRunner(mode))
    a = ask()
    assert a["steps"] == base["steps"] and a["conclusion"] == base["conclusion"]          # 원문 카드 그대로
    assert a["card_rewrite"]["applied"] is False and a["card_rewrite"]["reason"], a["card_rewrite"]
    if why:
        assert why in a["card_rewrite"]["reason"], a["card_rewrite"]


def test_switch_off_never_calls_claude(card, monkeypatch):
    monkeypatch.setenv("CARD_REWRITE", "0")
    r = CardRunner("good")
    CC.use_runner(r)
    a = ask()
    assert r.calls == [] and "card_rewrite" not in a


def test_not_an_external_request_never_calls_claude(card):
    r = CardRunner("good")
    CC.use_runner(r)
    a = ask(external=False)
    assert r.calls == [] and "card_rewrite" not in a                                      # 지침카드 화면 등 채팅 밖 길은 그대로


def test_non_alarm_question_never_calls_the_card_rewriter(card, monkeypatch):
    called = []
    monkeypatch.setattr(A, "_rewrite_alarm_card", lambda a, memo: called.append(1) or a)
    monkeypatch.setenv("LLM_JOBS", "write")               # 다른 Claude 작업(분류·고르기)이 이 시험을 흐리지 않게
    CC.use_runner(CardRunner("good"))
    with EXT.external_request("claude"):
        try:
            A.answer("쿨런트가 뭐야?", "OPR", {})
        except EXT.ExternalLlmFailure:
            pass
    assert called == []


def test_rewritten_card_is_what_a_follow_up_short_shows(card, monkeypatch):
    """이어 묻기 "짧게"는 알람 카드 문장을 프로그램이 다시 보인다 — 그 문장이 화면에 보인 (다시 쓴) 문장과 같아야 한다"""
    from backend.tests.test_pure_expand import APP_FLAGS          # 이어 묻기가 켜진 앱 설정 전체 (FOLLOWUP·PARSE_V8·FLOW_V10 …)
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXTERNAL", "0")                      # 알람 카드 길(규칙)로 간다
    CC.use_runner(CardRunner("good"))
    a = ask()
    rec = a["_followup"]
    assert rec["alarm_card"] and "어요" in rec["alarm_card"] and rec["alarm_card"] in a["conclusion"]


def test_a_prohibition_that_gets_weaker_is_rejected():
    """감사에서 나온 사례: "축을 움직이지 말고 …"가 "축을 움직이지 않고 …"로 약해졌다 — 금지 지시(말고·말 것·마세요)는 줄어들면 안 된다"""
    from backend.llm import jobs
    src = "축을 움직이지 말고 알람 이력을 본다"
    assert jobs.check_rewrite("축을 움직이지 않고 알람 이력을 봐요", src)[1] == "빠진 조건 말: 말고"
    assert jobs.check_rewrite("축을 움직이지 말고 알람 이력을 봐요", src)[1] is None
    assert jobs.check_rewrite("공구를 빼지 마세요", "공구를 빼지 말 것")[1] == "빠진 조건 말: 말 것"
