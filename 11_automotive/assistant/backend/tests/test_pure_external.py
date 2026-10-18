"""순수 외부 LLM 연결 PURE_EXTERNAL 시험 (2026-10-15, research_notes/순수외부LLM_연결_20261015.md) — 시험용 복사본 전용.

진짜 `claude`도 로컬 AI 서버도 부르지 않는다 — 가짜 `claude` 실행기(`CC.use_runner`)와 로컬 쪽 가짜 전송(`C.use_transport`)만 쓴다.
지키는 것: ① 끔(기본)이면 지금과 같다 ② 켬이어도 로컬 요청이면 지금과 같다 ③ 켬 + 외부 요청이면 분류 LLM 없이 조각 상위 K개 + 질문으로 Claude 1번
④ 위험한 부탁·권한·화면 설명·불량 원인·이어 묻기는 켬이어도 지금 길 ⑤ PURE_KEEP_SIGNALS=0이면 알람 번호·날짜·설비·운영 낱말 길도 끄고 전부 순수 길,
=1이면 그 신호가 있는 질문은 예전 길 ⑥ 조각 번호 → 출처 변환·"문서에 없음" 모양·직전 대화 1번 ⑦ 실패는 자동 대체 없이 오류 ⑧ 답을 검사하지 않는다 ⑨ STEP_LOG.
"""
import json
import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import settings
from backend.demo_state import get_state
from backend.eval import run_eval as R
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.rag.sanitize import FORBIDDEN
from backend.rag.search import search
from backend.services import answer_store as AS
from backend.services import pure_external as PURE

client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
PURE_PROPS = ("answer", "cited", "insufficient")
Q_DOC = "쿨런트가 뭐야?"
Q_ALARM_DOC = "알람 2075 어떻게 조치해?"      # 알람 번호 + 설명 요청 — 예전 길은 알람 카드 + 문서 줄 고르기(select)
Q_ALARM = "알람 2075가 뭐야?"                  # 알람 번호만(설명 요청 없음) — 예전 길은 알람 카드 (LLM 안 부름)
Q_OPS = "어제 VF2-01 몇 번 멈췄어?"            # 날짜·설비 + 운영 낱말
Q_STOCK = "재고 부족한 거 있어?"               # 운영 낱말만 (설비·날짜 없음)
DANGER = ["알람 108 리셋해 줘", "VF2-01 전원 꺼 줘"]   # 알람 번호·설비가 든 위험한 부탁
# 지금 앱 값과 같은 켜짐 (안전 새로쓰기·DOC_WRITE는 뺌 — 예전 길 비교가 LLM을 덜 부르게)
APP_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "RETRIEVAL": "bm25", "NUM_MATCH": "value", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded",
             "DOC_GATE": "tiered", "PARSE_V3": "1", "SPLIT_Q": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
             "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1",
             "PARSE_V11": "1", "LEAD_V12": "1", "TERM_V13": "1", "EXTERNAL_LLM_APP": "1", "PURE_EXTERNAL": "1"}


class Runner:
    """가짜 `claude` 실행기. 순수 길 스키마(answer·cited·insufficient)에는 payload를 돌려주고(mode에 따라 시간 초과·읽을 수 없는 글),
    그 밖의 스키마는 읽을 수 없는 글을 돌려준다(예전 길의 호출은 실패로 센다). 호출마다 스키마 칸·시스템 지시·사용자 글을 기록한다."""

    def __init__(self, payload=None, mode="ok"):
        self.payload = payload if payload is not None else {"answer": "답이에요.", "cited": ["C1"], "insufficient": False}
        self.mode, self.calls = mode, []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append({"props": props, "system": cmd[cmd.index("--system-prompt") + 1], "user": stdin_text})
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if props == PURE_PROPS and self.mode == "ok":
            out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
                   "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                   "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": self.payload}
            return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")
        return SimpleNamespace(returncode=0, stdout="JSON이 아닌 글", stderr="")

    def pure_calls(self):
        return [c for c in self.calls if c["props"] == PURE_PROPS]

    def route_calls(self):
        return [c for c in self.calls if {"kind", "intents", "period"} <= set(c["props"])]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    get_state().reset()
    AS.clear()
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    local_calls = []

    def local_handler(req):   # 로컬 Qwen 쪽 — 불리면 기록하고 연결 실패로 돌려준다
        local_calls.append(str(req.url))
        raise httpx.ConnectError("시험: 로컬 서버 없음")

    C.use_transport(httpx.MockTransport(local_handler))
    yield local_calls
    C.use_transport(None)
    CC.use_runner(None)
    AS.clear()
    get_state().reset()


def runner(**kw) -> Runner:
    r = Runner(**kw)
    CC.use_runner(r)
    return r


def post(q, role="SUP", **extra):
    return client.post("/api/assistant/chat", json={"question": q, **extra}, headers={"X-Role": role})


def user_chunks(text: str) -> list[tuple[int, str]]:
    """요청 글의 [C1] … 머리 줄들 (번호, 머리 글)."""
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"^\[C(\d+)\] (.+)$", text, re.M)]


# ------------------------------------------------------------------ 설정·기본값
def test_defaults_flags_and_parse(monkeypatch):
    monkeypatch.delenv("PURE_EXTERNAL")   # conftest가 "0"을 고정하고 APP_FLAGS가 "1"로 덮었다 — 아예 없으면 기본은 꺼짐
    for k in ("PURE_KEEP_SIGNALS", "PURE_TOPK"):
        monkeypatch.delenv(k, raising=False)
    s = settings()
    assert (s.pure_external, s.pure_keep_signals, s.pure_topk) == (False, False, 8)
    f = s.flags()
    assert f["pure_external"] is False and f["pure_keep_signals"] is False and f["pure_topk"] == 8
    for v, want in [("1", True), ("true", True), ("YES", True), ("0", False), ("", False), ("켬", False), ("on", False)]:
        monkeypatch.setenv("PURE_EXTERNAL", v)
        monkeypatch.setenv("PURE_KEEP_SIGNALS", v)
        assert settings().pure_external is want and settings().pure_keep_signals is want   # 모르는 값·빈 값은 꺼짐(지금 동작)
    for v, want in [("8", 8), ("3", 3), ("0", 1), ("-4", 1), ("99", 60), ("61", 60), ("60", 60), ("30", 30), ("20", 20), ("1", 1), ("많이", 8), ("", 8), (" 5 ", 5)]:
        monkeypatch.setenv("PURE_TOPK", v)
        assert settings().pure_topk == want   # 1~60으로 제한, 정수가 아니면 8


def test_defaults_are_pinned_in_the_five_places():
    assert R._BASE["PURE_EXTERNAL"] == "0" and R._BASE["PURE_KEEP_SIGNALS"] == "0" and R._BASE["PURE_TOPK"] == "8"   # run_eval 모든 모드
    assert all(env["PURE_EXTERNAL"] == "0" for env in R.MODES.values())
    here = Path(__file__).resolve().parent
    for rel in ("../eval/route_eval.py", "test_fallback_snapshot.py"):   # 분류 시험·스냅숏 만들기 명령
        text = (here / rel).read_text(encoding="utf-8")
        assert '"PURE_EXTERNAL": "0"' in text and '"PURE_KEEP_SIGNALS": "0"' in text and '"PURE_TOPK": "8"' in text, rel
    conftest = (here / "conftest.py").read_text(encoding="utf-8")   # 시험 고정물 (이 시험의 autouse 고정물이 켬 값으로 덮기 전의 기본)
    assert 'setenv("PURE_EXTERNAL", "0")' in conftest and 'setenv("PURE_KEEP_SIGNALS", "0")' in conftest and 'setenv("PURE_TOPK", "8")' in conftest


def test_pure_enabled_needs_switch_external_request_and_llm(monkeypatch):
    assert not PURE.enabled(settings())                                   # 요청 밖: 외부 요청이 아니다
    with EXT.external_request("claude"):
        assert PURE.enabled(settings())
        monkeypatch.setenv("PURE_EXTERNAL", "0")
        assert not PURE.enabled(settings())                               # 스위치 끔
        monkeypatch.setenv("PURE_EXTERNAL", "1")
        monkeypatch.setenv("LLM_ENABLED", "0")
        assert not PURE.enabled(settings())                               # LLM 꺼짐
        monkeypatch.setenv("LLM_ENABLED", "1")
        monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
        assert not PURE.enabled(settings())                               # 서버 외부 스위치 꺼짐 → 요청 선택이 무시된다
    with EXT.external_request("local"):
        assert not PURE.enabled(settings())


# ------------------------------------------------------------------ ① 끔(기본) = 지금과 같다
def test_off_external_request_still_goes_through_route_first(monkeypatch):
    monkeypatch.setenv("PURE_EXTERNAL", "0")
    rn = runner()
    r = post(Q_DOC, llm="claude")
    j = r.json()
    assert r.status_code == 503 and j["code"] == "EXTERNAL_LLM_UNAVAILABLE" and j["detail"]["job"] == "route"   # 지금 동작: 분류 LLM이 첫 호출
    assert rn.pure_calls() == [] and len(rn.route_calls()) == 1


# ------------------------------------------------------------------ ② 켬이어도 로컬 요청이면 지금과 같다
@pytest.mark.parametrize("q", [Q_DOC, Q_ALARM, Q_OPS, Q_STOCK])
def test_on_but_local_request_is_identical_to_off(monkeypatch, env, q):
    rn = runner()
    C.use_transport(httpx.MockTransport(lambda req: httpx.Response(500)))   # 로컬 서버 오류(HTTP 500): 연결 실패와 달리 차단기를 켜지 않아 세 번이 같은 조건이다
    monkeypatch.setenv("PURE_EXTERNAL", "0")
    a = post(q).json()
    monkeypatch.setenv("PURE_EXTERNAL", "1")
    b = post(q, llm="local").json()
    c = post(q).json()
    for x in (a, b, c):
        x.pop("answer_id", None)
        for t in x.get("llm_trace") or []:
            t.pop("ms", None)                                              # 걸린 시간만 매번 다르다
    assert a == b == c and "llm" not in a                                  # 답 전체가 한 글자도 다르지 않다
    assert rn.calls == []                                                  # 외부 실행기는 한 번도 안 불렸다


# ------------------------------------------------------------------ ③ 켬 + 외부 요청 + 문서 질문
def test_pure_doc_question_calls_claude_once_with_top_k_chunks(env):
    rn = runner()
    r = post(Q_DOC, llm="claude")
    j = r.json()
    assert r.status_code == 200, j
    assert len(rn.calls) == 1 and rn.route_calls() == [] and len(rn.pure_calls()) == 1   # 분류 LLM 없음, 순수 호출 정확히 1번
    assert env == []                                                                      # 로컬 Qwen은 한 번도 안 불렸다
    expected = search(Q_DOC, 8)                                                           # 원래 질문 그대로 검색한 상위 8개
    got = user_chunks(rn.calls[0]["user"])
    assert [n for n, _ in got] == list(range(1, len(expected) + 1)) and len(got) == 8
    assert [h for _, h in got] == [f"{c.cite} {c.title}" for _, c in expected]
    for (_, c) in expected:
        assert c.text in rn.calls[0]["user"]                                              # 조각 본문 전부
    assert rn.calls[0]["user"].rstrip().endswith("[질문]\n" + Q_DOC)
    assert "[바로 앞 대화]" not in rn.calls[0]["user"]                                      # 앞 답이 없으면 질문만
    assert FORBIDDEN.search(rn.calls[0]["user"]) is None and FORBIDDEN.search(rn.calls[0]["system"]) is None   # 원문 이름·번호 0건(sanitize를 거친 조각)
    assert j["llm"]["calls"] == 1 and j["llm"]["provider"] == "claude"


def test_system_prompt_has_the_required_instructions():
    sy = PURE.SYSTEM
    for must in ("조각에 있는 내용만", "문서에 없음", "insufficient", "지어내", "리셋", "담당자가 확인", "그대로 옮기기만", "cited", "출처를 쓰지 않는다", "해요체"):
        assert must in sy, must
    assert "$ref" not in json.dumps(PURE.SCHEMA) and "$defs" not in json.dumps(PURE.SCHEMA)


@pytest.mark.parametrize("k, want", [("3", 3), ("1", 1), ("20", 20), ("30", 30)])
def test_topk_setting_changes_the_chunk_count(monkeypatch, k, want):
    monkeypatch.setenv("PURE_TOPK", k)
    rn = runner()
    assert post(Q_DOC, llm="claude").status_code == 200
    assert len(user_chunks(rn.calls[0]["user"])) == min(want, len(search(Q_DOC, 60)))


def test_response_shape_matches_the_written_answer_the_screen_already_draws():
    runner(payload={"answer": "쿨런트는 절삭유예요.", "cited": ["C1"], "insufficient": False})
    j = post(Q_DOC, llm="claude").json()
    first = search(Q_DOC, 8)[0][1]
    assert j["status"] == "답변" and j["conclusion"] == "쿨런트는 절삭유예요." and j["written"] is True
    assert j["mode"] == "외부 LLM(Claude Sonnet 5.5) · 순수 연결 (검사 없음, 원문 출처 표기 차단만)"
    assert [e["cite"] for e in j["evidence"]] == [first.cite] and j["evidence"][0]["doc_no"] == first.doc_id and j["evidence"][0]["rev"] == first.revision
    assert j["steps"] == [] and j["current_data"] == [] and j["data_label"] is None and j["is_synthetic"] is False and j["related"] is None
    assert j["caution"] == "근거 안내이며 실행 지시가 아닙니다."
    b = j["blocks"]
    assert b[0] == {"kind": "lead", "text": "쿨런트는 절삭유예요.", "written": True}            # 화면: "AI가 문서를 보고 쓴 답 · 원문 아래"
    lines = [x for x in b[1:]]
    assert lines and all(x["kind"] == "line" and x["orig"] is True and x["cite"]["cite"] == first.cite for x in lines)   # 원문 줄은 [원문 보기]로 접힌다
    assert j["retrieval"]["pure"] is True and j["retrieval"]["top_k"] == 8 and j["retrieval"]["dense_used"] is False
    assert j["llm_trace"][0]["job"] == "pure_answer" and j["llm_trace"][0]["used"] is True
    assert j["route"]["kind"] == "doc" and "순수" in j["route"]["source"]


# ------------------------------------------------------------------ ④ 위험한 부탁은 켬이어도 거절 (두 PURE_KEEP_SIGNALS 값 모두)
@pytest.mark.parametrize("keep", ["0", "1"])
@pytest.mark.parametrize("q", DANGER)
def test_dangerous_requests_are_refused_before_the_pure_path(monkeypatch, keep, q):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", keep)
    rn = runner()
    j = post(q, llm="claude").json()
    assert j["status"] == "안내" and j["mode"] == "규칙" and ("바꾸지 않습니다" in j["conclusion"] or "조작하지 않습니다" in j["conclusion"])
    assert rn.calls == [] and j["llm"]["calls"] == 0 and j["evidence"] == []   # 순수 호출도 분류도 없다 — 거절이 먼저


# ------------------------------------------------------------------ ⑤ (a) PURE_KEEP_SIGNALS=0: 알람·날짜·설비·운영 길을 모두 끄고 순수 길
@pytest.mark.parametrize("q", [Q_ALARM_DOC, Q_ALARM, Q_OPS, Q_STOCK])
def test_signals_off_sends_alarm_ops_and_stock_questions_to_the_pure_path(env, q):
    rn = runner()
    j = post(q, llm="claude").json()
    assert j["status"] == "답변"
    assert [c["props"] for c in rn.calls] == [PURE_PROPS]                 # 순수 호출 1번뿐: route도 줄 고르기도 알람 카드의 LLM도 없다
    assert j["steps"] == [] and j["current_data"] == [] and j["data_label"] is None and j["is_synthetic"] is False   # 알람 카드·운영 조회 없음
    assert "순수 연결" in j["mode"] and j["route"]["source"].startswith("순수") and env == []


def test_signals_off_ignores_the_screen_alarm_context():
    rn = runner()
    j = post("이 알람 점검 순서 알려줘", llm="claude", context={"screen": "SCR-10", "alarm_key": "2075"}).json()
    assert [c["props"] for c in rn.calls] == [PURE_PROPS] and j["steps"] == [] and j["parsed"]["alarms"] == []   # 화면 알람 맥락으로 알람을 정하지 않는다


# ------------------------------------------------------------------ ⑤ (b) PURE_KEEP_SIGNALS=1: 신호가 있는 질문은 예전 길, 없는 질문만 순수 길
def test_keep_signals_on_sends_signal_questions_to_the_old_paths(monkeypatch, env):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    rn = runner()
    a = post(Q_ALARM, llm="claude").json()                                    # 알람 카드 (LLM을 부르지 않는 예전 길)
    assert a["status"] == "답변" and len(a["steps"]) > 0 and any(e["doc_id"] in ("DOC-02", "DOC-03") for e in a["evidence"]) and "순수" not in a["mode"]
    assert rn.calls == []
    o = post(Q_OPS, llm="claude").json()                                      # 운영 조회 (+ 문장 다듬기 호출은 가짜가 실패 → 기본 문장)
    assert o["status"] == "답변" and len(o["current_data"]) > 0 and o["is_synthetic"] is True and "순수" not in o["mode"]
    st = post(Q_STOCK, llm="claude").json()                                   # 운영 낱말만 있어도 신호로 본다
    assert st["status"] == "답변" and len(st["current_data"]) > 0 and "순수" not in st["mode"]
    assert rn.pure_calls() == [] and rn.route_calls() == []                    # 분류 LLM은 순수 방식에서 어느 길에도 부르지 않는다
    r = post(Q_ALARM_DOC, llm="claude")                                       # 알람 + 설명 요청: 예전 길은 문서 줄 고르기(select)를 먼저 부른다
    assert rn.pure_calls() == [] and rn.route_calls() == [] and rn.calls and rn.calls[-1]["props"] == ("answerable", "lead", "line_ids")
    assert r.status_code == 503 and r.json()["detail"]["job"] == "select"
    n = len(rn.calls)
    d = post(Q_DOC, llm="claude").json()                                      # 신호가 하나도 없는 질문은 순수 길
    assert d["status"] == "답변" and "순수 연결" in d["mode"] and len(rn.calls) == n + 1 and len(rn.pure_calls()) == 1


# ------------------------------------------------------------------ ⑤ (d) 권한·화면 설명·불량 원인·이어 묻기는 두 값 모두 지금 그대로
@pytest.mark.parametrize("keep", ["0", "1"])
def test_permission_screen_help_defect_and_followup_are_unchanged(monkeypatch, keep):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", keep)
    rn = runner()
    r = post(Q_DOC, role="MON", llm="claude")
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN" and rn.calls == []                         # 권한
    h = client.post("/api/assistant/chat", json={"question": "이 화면 설명해 줘", "context": {"screen": "SCR-10"}, "llm": "claude"}, headers={"X-Role": "SUP"}).json()
    assert h["status"] == "안내" and "화면 안내" in h["mode"] and rn.calls == []                                # 화면 설명
    d = post("불량 원인이 뭐야?", llm="claude").json()
    assert d["status"] == "근거 없음" and rn.calls == []                                                       # 불량 원인 거절
    first = post(Q_DOC, llm="claude").json()
    assert first["status"] == "답변" and len(rn.pure_calls()) == 1
    again = post("방금 내용 다시 보여줘", llm="claude", prev_answer_id=first["answer_id"]).json()               # 이어 묻기 감지·처리는 지금 길 그대로
    assert again["followup"]["kind"] == "again" and again["mode"].startswith("규칙 (이어 묻기") and again["conclusion"] == first["conclusion"]
    assert len(rn.pure_calls()) == 1 and rn.route_calls() == []                                              # 새 순수 호출 없음


# ------------------------------------------------------------------ ⑥ "문서에 없음" 모양 · 조각 번호 → 출처
def test_insufficient_gives_the_not_in_documents_shape():
    runner(payload={"answer": "문서에 없음", "cited": ["C1", "C2"], "insufficient": True})
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "문서에 없음" and j["conclusion"].startswith("문서에 없음") and j["evidence"] == [] and "written" not in j
    assert j["mode"].endswith("순수 연결 (검사 없음, 원문 출처 표기 차단만)") and j["llm"]["calls"] == 1


def test_cited_numbers_become_real_sources_and_unknown_ones_are_dropped():
    payload = {"answer": "답입니다 (DOC-03 §9 에도 있어요).", "cited": ["C2", "C99", "DOC-03 §9", "c1", "C2", "[C3]", "0", "없음", 4], "insufficient": False}
    runner(payload=payload)
    j = post(Q_DOC, llm="claude").json()
    top = [c for _, c in search(Q_DOC, 8)]
    assert [e["cite"] for e in j["evidence"]] == [top[1].cite, top[0].cite, top[2].cite]       # 입력 순서·겹침 하나로·모르는 번호와 모델이 쓴 출처 글은 버림
    assert [(e["doc_id"], e["section"]) for e in j["evidence"]] == [(top[1].doc_id, top[1].section), (top[0].doc_id, top[0].section), (top[2].doc_id, top[2].section)]
    assert j["conclusion"] == payload["answer"]                                                 # 답 글은 손대지 않는다 (모델이 쓴 문서 이름·번호를 프로그램이 바꾸지 않음)
    lines = [b for b in j["blocks"] if b["kind"] == "line"]
    assert {b["cite"]["cite"] for b in lines} == {top[1].cite, top[0].cite, top[2].cite}


def test_no_cited_number_keeps_the_answer_with_empty_sources_and_says_so():
    runner(payload={"answer": "그냥 답이에요.", "cited": [], "insufficient": False})
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["conclusion"] == "그냥 답이에요." and j["evidence"] == [] and "written" not in j
    assert j["mode"].endswith("근거 조각 번호 없음") and [b["kind"] for b in j["blocks"]] == ["lead"]


# ------------------------------------------------------------------ ⑦ 직전 대화는 1번만
def test_previous_question_and_answer_are_passed_once():
    rn = runner(payload={"answer": "첫 답이에요.", "cited": ["C1"], "insufficient": False})
    first = post(Q_DOC, llm="claude").json()
    assert "[바로 앞 대화]" not in rn.calls[0]["user"] and first["answer_id"]
    rn.payload = {"answer": "둘째 답이에요.", "cited": ["C1"], "insufficient": False}
    q2 = "스핀들 워밍업은 몇 분 해?"
    second = post(q2, llm="claude", prev_answer_id=first["answer_id"]).json()
    assert second["status"] == "답변" and len(rn.pure_calls()) == 2
    u = rn.calls[1]["user"]
    assert u.count("[바로 앞 대화]") == 1 and "앞 질문: " + Q_DOC in u and "앞 답: 첫 답이에요." in u
    assert u.index("[바로 앞 대화]") < u.index("[사내 문서 조각]") < u.index("[질문]") and u.rstrip().endswith("[질문]\n" + q2)
    third = post("윤활유는 얼마마다 보충해?", llm="claude", prev_answer_id=second["answer_id"]).json()   # 앞의 앞은 넘기지 않는다 — 바로 앞 하나뿐
    u3 = rn.calls[2]["user"]
    assert third["status"] == "답변" and u3.count("앞 질문: ") == 1 and "앞 질문: " + q2 in u3 and "앞 질문: " + Q_DOC not in u3 and "첫 답이에요." not in u3


def test_pure_answer_is_stored_like_other_answers_for_followups():
    runner()
    j = post(Q_DOC, llm="claude").json()
    assert AS.size() == 1 and j["answer_id"]
    rec = AS.get(j["answer_id"], "", "SUP")
    assert rec["question"] == Q_DOC and rec["conclusion"] == "답이에요." and rec["status"] == "답변" and rec["doc_lead"] == ""   # 검사 안 지난 글은 "검사 지난 앞머리"로 남기지 않는다
    assert rec["doc_lines"] and rec["evidence"] and rec["alarm"] is False and rec["current_data"] == []


# ------------------------------------------------------------------ ⑧ 외부 호출 실패는 자동 대체 없이 오류
@pytest.mark.parametrize("mode", ["timeout", "garbage"])
def test_external_failure_ends_with_an_error_and_never_falls_back(env, mode):
    rn = runner(mode=mode)
    r = post(Q_DOC, llm="claude")
    j = r.json()
    assert r.status_code == 503 and j["code"] == "EXTERNAL_LLM_UNAVAILABLE", j
    assert j["detail"]["job"] == "pure_answer" and j["detail"]["reason"]
    assert len(rn.calls) == 1 and env == []                                  # 재요청도 로컬·다른 길로의 대체도 없다
    assert EXT.override() is None and post(Q_DOC).status_code == 200         # 다음(기본) 요청은 멀쩡하다


def test_an_empty_answer_is_a_format_error_not_a_blank_screen():
    runner(payload={"answer": "   ", "cited": ["C1"], "insufficient": False})
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"] == {"job": "pure_answer", "reason": "빈 답"}


def test_no_search_hit_does_not_call_claude():
    rn = runner()
    j = post("zzqqxxvv", llm="claude").json()
    assert j["status"] == "문서에 없음" and rn.calls == [] and j["llm"]["calls"] == 0 and "검색 결과가 없어" in j["mode"]


# ------------------------------------------------------------------ ⑨ 답을 검사하지 않는다
def test_no_checks_are_applied_to_the_answer():
    bad = "공구를 바로 교체하세요. 그냥 리셋해도 돼요. 세 번 확인하세요. 온도는 135도예요. 작업자가 속도를 조정해야 합니다."
    rn = runner(payload={"answer": bad, "cited": ["C1"], "insufficient": False})
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["conclusion"] == bad and j["blocks"][0]["text"] == bad   # 허락·지시 꼴·한글 수사·지어낸 숫자·"~해야 한다" — 그대로 나간다
    assert len(rn.calls) == 1                                                                    # 뜻 판정·재시도 호출도 없다


def test_only_the_copyright_block_remains():
    runner(payload={"answer": "RD0080 표를 보세요.", "cited": ["C1"], "insufficient": False})
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "확인 필요" and "원문 출처 표기" in j["conclusion"] and "RD0080" not in json.dumps(j, ensure_ascii=False)


# ------------------------------------------------------------------ ⑩ STEP_LOG (읽기만)
def test_step_log_off_writes_nothing():
    runner()
    j = post(Q_DOC, llm="claude").json()
    assert "step_log_id" not in j and not Path(os.environ["STEP_LOG_DIR"]).exists()


def test_step_log_on_records_the_pure_steps(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    runner(payload={"answer": "쿨런트는 절삭유예요.", "cited": ["C1", "C77"], "insufficient": False})
    j = post(Q_DOC, llm="claude").json()
    files = list(Path(os.environ["STEP_LOG_DIR"]).glob("steps_*.jsonl"))
    assert j["step_log_id"] and len(files) == 1
    rec = json.loads(files[0].read_text(encoding="utf-8").splitlines()[-1])
    names = [s["단계"] for s in rec["단계"]]
    order = [names.index(x) for x in ("1 규칙 판정", "2 질문 분류", "3 찾기", "순수 호출 결과", "출처 변환")]
    assert order == sorted(order) and "알람 카드" not in names and "운영 조회" not in names and "4 줄 고르기" not in names   # 순수 길의 단계 순서, 다른 길의 단계는 없다
    assert rec["최종"]["단계"] == "12 최종" and rec["최종"]["꼬리표"][0].startswith("외부 LLM") and "AI가 문서를 보고 쓴 답 · 원문 아래" in rec["최종"]["꼬리표"]
    step3 = next(s for s in rec["단계"] if s["단계"] == "3 찾기")
    assert step3["길"] == "순수 외부 LLM" and step3["조각수"] == 8 and len(step3["상위"]) == 8 and "점수" in step3["상위"][0]
    conv = next(s for s in rec["단계"] if s["단계"] == "출처 변환")
    assert len(conv["변환"]) == 1 and conv["버린항목"] == ["C77"]
    res = next(s for s in rec["단계"] if s["단계"] == "순수 호출 결과")
    assert res["답"] == "쿨런트는 절삭유예요." and res["받은인용"] == ["C1", "C77"] and res["충분하지않음"] is False
    call = rec["LLM호출"][0]
    assert call["작업"] == "pure_answer" and call["구분"] == "재료" and call["결과"] == "성공" and call["받은JSON"]["cited"] == ["C1", "C77"] and call["보낸글자수"] > 1000
    raw = files[0].read_text(encoding="utf-8")
    assert "[사내 문서 조각]" not in raw and PURE.SYSTEM not in raw                                   # 보낸 글 전체는 남기지 않는다 (글자 수만)


def test_step_log_records_a_failed_pure_call(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    runner(mode="timeout")
    assert post(Q_DOC, llm="claude").status_code == 503
    rec = json.loads(next(Path(os.environ["STEP_LOG_DIR"]).glob("steps_*.jsonl")).read_text(encoding="utf-8").splitlines()[-1])
    assert rec["LLM호출"][0]["작업"] == "pure_answer" and rec["LLM호출"][0]["결과"] == "실패" and rec["최종"]["오류"]["작업"] == "pure_answer"
