"""순수 외부 LLM 말투 바꾸기 PURE_STYLE 시험 (2026-10-15) — 시험용 복사본 전용.

진짜 `claude`도 로컬 AI 서버도 부르지 않는다 — 가짜 `claude` 실행기(`CC.use_runner`)와 로컬 쪽 가짜 전송(`C.use_transport`)만 쓴다.
`test_pure_external.py`(끔 = 지금 동작이 그대로임을 보이는 회귀 보증)는 고치지 않았고, 이 파일은 켬(PURE_STYLE=1)에서 바뀌는 것과
끔에서 바뀌지 않는 것을 본다.

지키는 것: ① 기본 꺼짐·flags·값 읽기·기본값 다섯 곳 고정 ② 끔이면 요청의 지시문·스키마·max_tokens·요청 글이 지금과 글자까지 같음
③ 켬이면 새 지시문·스키마(opening·points·closing·cited·insufficient) ④ 운영 안내 줄(12번)은 PURE_KEEP_SIGNALS=0일 때만 ⑤ points 있음/없음에 따른 화면 칸 조립과 conclusion
⑥ points 번호 접두어 지움·문자열 아닌 항목 버림 ⑦ insufficient: 상태 "문서에 없음" + Claude가 쓴 opening ⑧ 검색 결과 없음: 호출 0번 + 짧은 해요체
⑨ 실패·빈 opening은 503 (자동 대체 없음) ⑩ 코드 검사가 여전히 없음 ⑪ 저작권 차단 유지 ⑫ 끝 안전 문구 불변 ⑬ STEP_LOG.
"""
import hashlib
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
from backend import config as CFG
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.eval import run_eval as R
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.rag.sanitize import FORBIDDEN
from backend.rag.search import search
from backend.services import answer as ANS
from backend.services import answer_store as AS
from backend.services import pure_external as PURE

client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
PURE_PROPS = ("answer", "cited", "insufficient")                                    # 기존 말투(끔)의 스키마 칸
STYLE_PROPS = ("cited", "closing", "insufficient", "opening", "points")           # 새 말투(켬)의 스키마 칸
Q_DOC = "쿨런트가 뭐야?"
Q_ALARM = "알람 2075가 왜 자꾸 떠?"
Q_OPS = "어제 VF2-01 몇 번 멈췄어?"
Q_SAFETY = "고전압 대기는 어떻게 해?"
DANGER = ["알람 108 리셋해 줘", "VF2-01 전원 꺼 줘"]
OPS_NOTE = "운영 기록(정지 횟수, 생산량, 재고 수량, 알람이 난 이력, 지금 설비 상태)을 조회하지 못한다"   # 지시문 12번 줄의 한 구절
# 끔의 지시문·스키마가 지금과 글자까지 같은지는 고치기 전 복사본(B_backend_pre_style)에서 잰 지문으로 고정한다
OLD_SYSTEM_SHA = "c584363806f98db65ecd3bdd80cfa998c5f508f1eae69b2ac31df4d860fe4cb6"
OLD_SCHEMA_SHA = "735ba9d8246da54c68c494d00d2e54c5d70319e3a500c0885a0a03aca8641cfb"
APP_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "RETRIEVAL": "bm25", "NUM_MATCH": "value", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded",
             "DOC_GATE": "tiered", "PARSE_V3": "1", "SPLIT_Q": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
             "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1",
             "PARSE_V11": "1", "LEAD_V12": "1", "TERM_V13": "1", "EXTERNAL_LLM_APP": "1", "PURE_EXTERNAL": "1", "PURE_STYLE": "1"}


def chat(opening="쿨런트는 절삭유예요.", points=(), closing="", cited=("C1",), insufficient=False) -> dict:
    """새 말투(켬)의 Claude 답 payload."""
    return {"opening": opening, "points": list(points), "closing": closing, "cited": list(cited), "insufficient": insufficient}


OLD_PAYLOAD = {"answer": "옛 말투 답이에요.", "cited": ["C1"], "insufficient": False}


class Runner:
    """가짜 `claude` 실행기. 스키마 칸이 새 말투(opening·points·closing·cited·insufficient)면 payload를, 기존 말투(answer·cited·insufficient)면 old_payload를 돌려준다
    (mode에 따라 시간 초과·읽을 수 없는 글). 호출마다 스키마·시스템 지시·사용자 글을 기록한다."""

    def __init__(self, payload=None, mode="ok", old_payload=None):
        self.payload = payload if payload is not None else chat()
        self.old_payload = old_payload if old_payload is not None else OLD_PAYLOAD
        self.mode, self.calls = mode, []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append({"props": props, "schema": sch, "system": cmd[cmd.index("--system-prompt") + 1], "user": stdin_text})
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if props in (PURE_PROPS, STYLE_PROPS) and self.mode == "ok":
            out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
                   "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                   "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": self.payload if props == STYLE_PROPS else self.old_payload}
            return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")
        return SimpleNamespace(returncode=0, stdout="JSON이 아닌 글", stderr="")

    def style_calls(self):
        return [c for c in self.calls if c["props"] == STYLE_PROPS]

    def old_calls(self):
        return [c for c in self.calls if c["props"] == PURE_PROPS]


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


def spy_chat_json(monkeypatch) -> list[dict]:
    """chat_json 호출의 (messages, schema, name, max_tokens)를 기록하고 진짜 chat_json(가짜 실행기를 부름)에 넘긴다."""
    seen, real = [], C.chat_json

    def spy(messages, schema, name, max_tokens=400, s=None, grammar=None):
        seen.append({"messages": messages, "schema": schema, "name": name, "max_tokens": max_tokens})
        return real(messages, schema, name, max_tokens, s, grammar)

    monkeypatch.setattr(C, "chat_json", spy)
    return seen


def post(q, role="SUP", **extra):
    return client.post("/api/assistant/chat", json={"question": q, **extra}, headers={"X-Role": role})


def user_chunks(text: str) -> list[tuple[int, str]]:
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"^\[C(\d+)\] (.+)$", text, re.M)]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ ① 설정·기본값
def test_defaults_flags_and_parse(monkeypatch):
    monkeypatch.delenv("PURE_STYLE")   # conftest가 "0"을 고정하고 이 파일의 고정물이 "1"로 덮었다 — 아예 없으면 기본은 꺼짐
    monkeypatch.setattr(CFG, "_dotenv", lambda: {})   # 복사본 루트의 .env(앱 스위치)가 있어도 "코드 기본값"을 본다 (.env를 읽지 않음)
    s = settings()
    assert s.pure_style is False and s.flags()["pure_style"] is False
    assert Settings.__dataclass_fields__["pure_style"].default is False   # 코드 기본값
    for v, want in [("1", True), ("true", True), ("YES", True), (" 1 ", True), ("0", False), ("", False), ("켬", False), ("on", False), ("2", False)]:
        monkeypatch.setenv("PURE_STYLE", v)
        assert settings().pure_style is want and settings().flags()["pure_style"] is want   # 모르는 값·빈 값은 꺼짐(지금 말투)


def test_default_is_pinned_in_the_five_places():
    assert R._BASE["PURE_STYLE"] == "0"                                  # run_eval 모든 모드
    assert all(env["PURE_STYLE"] == "0" for env in R.MODES.values())
    here = Path(__file__).resolve().parent
    route_eval = (here / "../eval/route_eval.py").read_text(encoding="utf-8")
    assert route_eval.count('"PURE_STYLE"') == 2 and '"PURE_STYLE": "0"' in route_eval   # 분류 시험: 환경 보관 목록 + 기본 고정, 두 곳
    assert '"PURE_STYLE": "0"' in (here / "test_fallback_snapshot.py").read_text(encoding="utf-8")   # 스냅숏 만들기 명령
    assert 'setenv("PURE_STYLE", "0")' in (here / "conftest.py").read_text(encoding="utf-8")        # 시험 고정물
    assert "pure_style: bool = False" in (here / "../config.py").read_text(encoding="utf-8")          # config 코드 기본값


# ------------------------------------------------------------------ ② 끔 = 요청이 지금과 글자까지 같다
def test_off_request_is_identical_to_the_current_one(monkeypatch):
    monkeypatch.setenv("PURE_STYLE", "0")
    assert sha(PURE.SYSTEM) == OLD_SYSTEM_SHA                                                                   # 고치기 전 복사본에서 잰 지문
    assert sha(json.dumps(PURE.SCHEMA, sort_keys=True, ensure_ascii=False)) == OLD_SCHEMA_SHA
    s = settings()
    assert PURE.system_for(s) is PURE.SYSTEM and PURE.schema_for(s) is PURE.SCHEMA                              # 같은 객체
    seen = spy_chat_json(monkeypatch)
    rn = runner()
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["conclusion"] == OLD_PAYLOAD["answer"] and j["blocks"][0] == {"kind": "lead", "text": OLD_PAYLOAD["answer"], "written": True}
    assert len(seen) == 1 and seen[0]["name"] == "pure_answer" and seen[0]["max_tokens"] == 1200                # max_tokens 그대로
    assert seen[0]["schema"] is PURE.SCHEMA
    chunks = [c for _, c in search(Q_DOC, 8)]
    assert seen[0]["messages"] == PURE.build_messages(Q_DOC, chunks, None)                                      # 시스템 + 사용자 글 전체가 기본 인자 호출과 같다
    assert seen[0]["messages"][0] == {"role": "system", "content": PURE.SYSTEM}
    assert [c["props"] for c in rn.calls] == [PURE_PROPS] and rn.calls[0]["system"] == PURE.SYSTEM             # 가짜 실행기가 받은 지시문·스키마 칸도 그대로
    assert rn.calls[0]["schema"] == PURE.SCHEMA


def test_build_messages_default_system_is_unchanged():
    chunks = [c for _, c in search(Q_DOC, 3)]
    prev = {"question": "앞 질문", "conclusion": "앞 답"}
    m = PURE.build_messages(Q_DOC, chunks, prev)
    assert m[0] == {"role": "system", "content": PURE.SYSTEM}
    assert PURE.build_messages(Q_DOC, chunks, prev, PURE.SYSTEM) == m
    m2 = PURE.build_messages(Q_DOC, chunks, prev, PURE.SYSTEM_CHAT)
    assert m2[0]["content"] == PURE.SYSTEM_CHAT and m2[1] == m[1]                                               # 사용자 글은 말투와 상관없이 같다


# ------------------------------------------------------------------ ③ 켬: 새 지시문·스키마
def test_style_on_sends_the_new_system_prompt_and_schema(monkeypatch, env):
    seen = spy_chat_json(monkeypatch)
    rn = runner()
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 200, r.json()
    assert len(rn.calls) == 1 and [c["props"] for c in rn.calls] == [STYLE_PROPS] and env == []                 # 새 칸 다섯, 호출 1번, 로컬 Qwen 0번
    call, sch = rn.calls[0], rn.calls[0]["schema"]
    assert sch["required"] and sorted(sch["required"]) == sorted(STYLE_PROPS) and sch["additionalProperties"] is False
    assert sch["properties"]["points"] == {"type": "array", "items": {"type": "string"}}
    dumped = json.dumps(sch)
    for bad in ("$ref", "$defs", "minItems", "maxItems", "minLength", "maxLength", "pattern", "enum"):
        assert bad not in dumped, bad                                                                           # 개수·길이 제약·$ref 없음
    assert seen[0]["max_tokens"] == 1600 and seen[0]["schema"] is PURE.SCHEMA_CHAT
    sy = call["system"]
    assert sy == PURE.SYSTEM_CHAT == PURE.system_for(settings())
    for must in ("해요체", "opening", "points", "closing", "문서에는 없지만 일반적으로는", "하세요", "해도 돼요", "담당자가 확인해요", "cited", "쓰지 않는다",
                 "insufficient", "옆자리 선배가 질문한 사람에게 직접 설명해 주듯이 말한다.", "문서 문장을 그대로 옮겨 적지 말고",
                 "순서를 바꾸거나 단계를 빼거나 더하지 않는다.", "글 안에는 문서 이름, 문서 번호, 절 번호를 쓰지 않는다(프로그램이 붙인다).",
                 "설비를 켜라·꺼라·리셋하라·설정을 바꾸라고 지시하지 않고, \"~하세요\", \"~해도 돼요\" 같은 지시·허락 꼴을 쓰지 않는다."):
        assert must in sy, must
    for n in range(1, 17):
        if n != 12:
            assert re.search(rf"^{n}\. ", sy, re.M), n                                                          # 1~16번 줄이 모두 있다 (12번은 아래 ④)
    assert FORBIDDEN.search(sy) is None                                                                         # 지시문에 원문 이름·번호 없음
    assert "$ref" not in sy
    u = call["user"]
    assert [n for n, _ in user_chunks(u)] == list(range(1, 9)) and u.rstrip().endswith("[질문]\n" + Q_DOC)      # 사용자 글(조각·질문)은 끔과 같은 꼴
    assert seen[0]["messages"][0]["content"] == sy


# ------------------------------------------------------------------ ④ 운영 안내 줄은 PURE_KEEP_SIGNALS=0일 때만
def test_ops_note_only_when_keep_signals_is_off(monkeypatch):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "0")
    on0 = PURE.system_for(settings())
    assert on0 == PURE.SYSTEM_CHAT and OPS_NOTE in on0 and re.search(r"^12\. 이 연결은", on0, re.M)
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    on1 = PURE.system_for(settings())
    assert on1 == PURE.SYSTEM_CHAT_KEEP and OPS_NOTE not in on1 and not re.search(r"^12\. ", on1, re.M)
    for must in ("13. 설비를 켜라", "14. 안전·전기 작업 절차", "15. cited에는", "16. [바로 앞 대화]가 있으면"):   # 나머지 줄은 두 판 모두 같다
        assert must in on0 and must in on1
    assert on0.replace(PURE._CHAT_OPS + "\n", "") == on1                                                         # 차이는 12번 줄 하나뿐
    monkeypatch.setenv("PURE_STYLE", "0")
    assert PURE.system_for(settings()) is PURE.SYSTEM                                                            # 끔이면 PURE_KEEP_SIGNALS와 상관없이 옛 지시문


def test_ops_note_end_to_end_with_keep_signals(monkeypatch):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    rn = runner()
    assert post(Q_DOC, llm="claude").status_code == 200                                                          # 신호가 없는 질문은 keep=1이어도 순수 길
    assert rn.calls[0]["system"] == PURE.SYSTEM_CHAT_KEEP and OPS_NOTE not in rn.calls[0]["system"]
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "0")
    assert post(Q_OPS, llm="claude").status_code == 200                                                          # keep=0은 운영 질문도 순수 길 — 12번 줄 포함
    assert rn.calls[1]["system"] == PURE.SYSTEM_CHAT and OPS_NOTE in rn.calls[1]["system"]


# ------------------------------------------------------------------ ⑤ points 있음/없음 → 화면 칸 조립, conclusion
def test_points_make_an_ops_block_then_closing_text_then_original_lines():
    runner(payload=chat(opening="2075는 윤활유가 비었다는 알람이에요.", points=["윤활유 통을 봐요", "펌프가 도는지 봐요", "배관이 새는지 봐요"],
                        closing="실제 원인은 담당자가 확인해요."))
    j = post(Q_ALARM, llm="claude").json()
    first = search(Q_ALARM, 8)[0][1]
    assert j["status"] == "답변" and j["written"] is True and j["evidence"][0]["cite"] == first.cite
    b = j["blocks"]
    assert b[0] == {"kind": "ops", "head": "2075는 윤활유가 비었다는 알람이에요.", "items": ["윤활유 통을 봐요", "펌프가 도는지 봐요", "배관이 새는지 봐요"], "source": None}
    assert b[1] == {"kind": "text", "text": "실제 원인은 담당자가 확인해요."}
    rest = b[2:]
    assert rest and all(x["kind"] == "line" and x["orig"] is True and x["cite"]["cite"] == first.cite for x in rest)   # 원문 줄은 그대로 뒤에 붙어 [원문 보기]로 접힌다
    assert j["conclusion"] == "2075는 윤활유가 비었다는 알람이에요.\n1) 윤활유 통을 봐요\n2) 펌프가 도는지 봐요\n3) 배관이 새는지 봐요\n실제 원인은 담당자가 확인해요."
    assert j["steps"] == [] and j["current_data"] == [] and j["is_synthetic"] is False                             # 알람 카드·운영 조회는 여전히 없다


def test_no_points_make_a_lead_block():
    runner(payload=chat(opening="쿨런트는 절삭유예요.", closing="문서에는 없지만 일반적으로는 농도를 자주 봐야 해요."))
    j = post(Q_DOC, llm="claude").json()
    b = j["blocks"]
    assert b[0] == {"kind": "lead", "text": "쿨런트는 절삭유예요.", "written": True}
    assert b[1] == {"kind": "text", "text": "문서에는 없지만 일반적으로는 농도를 자주 봐야 해요."} and all(x["kind"] == "line" and x["orig"] is True for x in b[2:])
    assert j["conclusion"] == "쿨런트는 절삭유예요.\n문서에는 없지만 일반적으로는 농도를 자주 봐야 해요."


def test_no_points_no_closing_is_a_lead_only_answer():
    runner(payload=chat(opening="쿨런트는 절삭유예요."))
    j = post(Q_DOC, llm="claude").json()
    assert j["blocks"][0] == {"kind": "lead", "text": "쿨런트는 절삭유예요.", "written": True} and [x["kind"] for x in j["blocks"][1:]] == ["line"] * (len(j["blocks"]) - 1)
    assert j["conclusion"] == "쿨런트는 절삭유예요."


def test_points_without_closing_have_no_text_block():
    runner(payload=chat(opening="이유가 둘이에요.", points=["하나", "둘", "셋"]))
    j = post(Q_DOC, llm="claude").json()
    assert j["blocks"][0]["kind"] == "ops" and j["blocks"][1]["kind"] == "line" and j["conclusion"] == "이유가 둘이에요.\n1) 하나\n2) 둘\n3) 셋"


def test_no_cited_number_keeps_the_answer_without_written_and_original_lines():
    runner(payload=chat(opening="그냥 답이에요.", points=["하나", "둘"], closing="끝이에요.", cited=[]))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["evidence"] == [] and "written" not in j and j["mode"].endswith("근거 조각 번호 없음")
    assert j["blocks"] == [{"kind": "ops", "head": "그냥 답이에요.", "items": ["하나", "둘"], "source": None}, {"kind": "text", "text": "끝이에요."}]
    j2 = None
    runner(payload=chat(opening="이것도 그냥 답이에요.", cited=[]))
    j2 = post(Q_DOC, llm="claude").json()
    assert j2["blocks"] == [{"kind": "lead", "text": "이것도 그냥 답이에요."}] and j2["caution"] is None                 # 근거 조각이 없으면 lead에 written도 없고 주의 문구도 없다


def test_conclusion_is_what_followups_remember_and_what_the_next_question_sees():
    rn = runner(payload=chat(opening="결론이에요.", points=["하나", "둘", "셋"], closing="끝이에요."))
    first = post(Q_DOC, llm="claude").json()
    joined = "결론이에요.\n1) 하나\n2) 둘\n3) 셋\n끝이에요."
    rec = AS.get(first["answer_id"], "", "SUP")
    assert rec["conclusion"] == joined and rec["doc_lead"] == "" and rec["doc_lines"]                              # 이어 묻기 기억 = 이은 글, 검사 안 지난 앞머리 없음
    rn.payload = chat(opening="둘째 답이에요.")
    q2 = "스핀들 워밍업은 몇 분 해?"
    second = post(q2, llm="claude", prev_answer_id=first["answer_id"]).json()
    u = rn.calls[1]["user"]
    assert second["status"] == "답변" and u.count("[바로 앞 대화]") == 1 and "앞 답: " + joined in u and u.rstrip().endswith("[질문]\n" + q2)


# ------------------------------------------------------------------ ⑥ 번호 접두어 지움 · 문자열 아닌 항목 버림 · 빈 항목 버림
@pytest.mark.parametrize("raw, want", [
    ("1. 속도를 봐요", "속도를 봐요"), ("1) 확인해요", "확인해요"), ("(2) 확인해요", "확인해요"), ("[3] 확인해요", "확인해요"), ("① 확인해요", "확인해요"),
    ("⑩ 확인해요", "확인해요"), ("첫째, 확인해요", "확인해요"), ("둘째, 확인해요", "확인해요"), ("  4.  공구를 봐요 ", "공구를 봐요"), ("10. 열 번째예요", "열 번째예요"),
    ("1.5배로 올려요", "1.5배로 올려요"), ("2번 축을 봐요", "2번 축을 봐요"), ("10분 기다려요", "10분 기다려요"), ("첫째 줄을 봐요", "첫째 줄을 봐요"),
    ("3. 2.5V를 재요", "2.5V를 재요"), ("그냥 문장이에요", "그냥 문장이에요"), ("1. ", ""), ("   ", ""), ("①", ""),
])
def test_point_number_prefix_is_removed_only_for_display(raw, want):
    assert PURE._tidy_point(raw) == want


def test_compose_drops_non_strings_and_blank_items_and_trims():
    c = PURE.compose({"opening": "  결론이에요.  ", "points": ["1. 하나", None, 3, {"a": 1}, ["x"], "", "  ", "둘째, 둘", "(3) 셋", True], "closing": " 끝 "})
    assert c == {"opening": "결론이에요.", "points": ["하나", "둘", "셋"], "closing": "끝"}
    assert PURE.compose({"opening": 5, "points": "목록 아님", "closing": None}) == {"opening": "", "points": [], "closing": ""}
    assert PURE.join_conclusion("가", ["나", "다"], "라") == "가\n1) 나\n2) 다\n라" and PURE.join_conclusion("가", [], "") == "가" and PURE.join_conclusion("", ["나"], "다") == "1) 나\n다"


def test_prefixed_and_odd_points_become_clean_numbered_items_end_to_end():
    runner(payload=chat(opening="이유예요.", points=["1. 첫 이유", "2) 둘째 이유", "③ 셋째 이유", None, 7, "", "넷째 이유"], closing=""))
    j = post(Q_DOC, llm="claude").json()
    assert j["blocks"][0]["items"] == ["첫 이유", "둘째 이유", "셋째 이유", "넷째 이유"]                              # 화면이 번호를 붙이므로 접두어는 지워졌다
    assert j["conclusion"] == "이유예요.\n1) 첫 이유\n2) 둘째 이유\n3) 셋째 이유\n4) 넷째 이유"


# ------------------------------------------------------------------ ⑦ insufficient: 문서에 없음 + Claude가 쓴 opening
def test_insufficient_shows_the_opening_claude_wrote():
    op = "사내 문서에는 그 알람의 기준값이 없어요. 알람 번호를 다시 확인해 보세요."
    runner(payload=chat(opening=op, points=[], closing="", cited=["C1", "C2"], insufficient=True))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "문서에 없음" and j["conclusion"] == op and j["conclusion"] != ANS.PURE_NO_DOC_V19      # 고정 문구가 아니라 Claude가 쓴 글
    assert j["evidence"] == [] and "written" not in j and not j.get("blocks") and j["caution"] is None             # 근거·원문 줄·블록·주의 문구 없음
    assert j["mode"].endswith("순수 연결 (검사 없음, 원문 출처 표기 차단만)") and j["llm"]["calls"] == 1 and j["retrieval"]["pure"] is True


def test_insufficient_ignores_points_and_closing_and_keeps_only_the_opening():
    runner(payload=chat(opening="문서에 답이 없어요.", points=["하나", "둘"], closing="이건 안 보여요.", insufficient=True))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "문서에 없음" and j["conclusion"] == "문서에 답이 없어요."


def test_insufficient_with_empty_opening_uses_a_short_fixed_sentence_not_a_failure():
    runner(payload=chat(opening="   ", insufficient=True))
    r = post(Q_DOC, llm="claude")
    j = r.json()
    assert r.status_code == 200 and j["status"] == "문서에 없음" and j["conclusion"] == PURE.NO_OPENING_CHAT
    assert PURE.NO_OPENING_CHAT.endswith("요.") and "합니다" not in PURE.NO_OPENING_CHAT


# ------------------------------------------------------------------ ⑧ 검색 결과 없음: 호출 0번 + 짧은 해요체 (끔은 고정 문구 그대로)
def test_no_search_hit_does_not_call_claude_and_says_it_briefly():
    rn = runner()
    j = post("zzqqxxvv", llm="claude").json()
    assert j["status"] == "문서에 없음" and rn.calls == [] and j["llm"]["calls"] == 0 and "검색 결과가 없어" in j["mode"]
    assert j["conclusion"] == ANS.PURE_NO_DOC_CHAT_V19 == "사내 문서에서 관련 내용을 찾지 못했어요. 쓰신 낱말을 바꿔서 다시 물어봐 주세요."


def test_no_search_hit_with_style_off_keeps_the_old_fixed_sentence(monkeypatch):
    monkeypatch.setenv("PURE_STYLE", "0")
    rn = runner()
    j = post("zzqqxxvv", llm="claude").json()
    assert rn.calls == [] and j["conclusion"] == ANS.PURE_NO_DOC_V19 and j["conclusion"].startswith("문서에 없음 — ")


# ------------------------------------------------------------------ ⑨ 실패·빈 opening → 503, 자동 대체 없음
@pytest.mark.parametrize("mode", ["timeout", "garbage"])
def test_external_failure_ends_with_an_error_and_never_falls_back(env, mode):
    rn = runner(mode=mode)
    r = post(Q_DOC, llm="claude")
    j = r.json()
    assert r.status_code == 503 and j["code"] == "EXTERNAL_LLM_UNAVAILABLE", j
    assert j["detail"]["job"] == "pure_answer" and j["detail"]["reason"]
    assert len(rn.calls) == 1 and env == []                                      # 재요청도 로컬·다른 길로의 대체도 없다 (끔 길로 되돌아가지도 않는다)
    assert EXT.override() is None and post(Q_DOC).status_code == 200            # 다음(기본) 요청은 멀쩡하다


@pytest.mark.parametrize("opening", ["   ", "", 5, None])
def test_an_empty_or_odd_opening_is_a_format_error_not_a_blank_screen(opening):
    runner(payload=chat(opening=opening, points=["하나", "둘", "셋"], closing="끝이에요."))
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"] == {"job": "pure_answer", "reason": "빈 답"}              # points가 있어도 opening이 비면 빈 답


def test_a_payload_missing_a_required_field_is_a_failure():
    runner(payload={"opening": "답이에요.", "cited": ["C1"], "insufficient": False})                              # points·closing 칸 없음
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"]["job"] == "pure_answer"


# ------------------------------------------------------------------ ⑩ 코드 검사가 여전히 없다
def test_no_checks_are_applied_to_the_answer_the_prompt_is_what_prevents_them():
    # 주의: 아래 문장들은 지시문(13·8번 등)이 막으려는 것이다. 코드가 막는 것이 아니다 — 이 시험은 "코드 검사가 새로 생기지 않았다"만 확인한다.
    # 지시·허락 꼴, 한글 수사, 지어낸 숫자, "~해야 한다"가 그대로 나가는 것은 이 방식의 알려진 한계다.
    bad_open = "공구를 바로 교체하세요. 그냥 리셋해도 돼요. 세 번 확인하세요."
    bad_pts = ["온도는 135도예요", "작업자가 속도를 조정해야 합니다", "전원을 끄고 켜도 됩니다"]
    bad_close = "피드 레이트(Feed Rate)를 올리면 돼요."
    rn = runner(payload=chat(opening=bad_open, points=bad_pts, closing=bad_close))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["blocks"][0] == {"kind": "ops", "head": bad_open, "items": bad_pts, "source": None}
    assert j["blocks"][1] == {"kind": "text", "text": bad_close} and j["conclusion"] == f"{bad_open}\n1) {bad_pts[0]}\n2) {bad_pts[1]}\n3) {bad_pts[2]}\n{bad_close}"
    assert len(rn.calls) == 1                                                                                      # 뜻 판정·재시도 호출도 없다


# ------------------------------------------------------------------ ⑪ 저작권 차단은 유지
@pytest.mark.parametrize("payload", [
    chat(opening="RD0080 표를 보세요."),
    chat(opening="주기예요.", points=["하나", "RD0080 3개월 항목", "셋"]),
    chat(opening="주기예요.", closing="TG0125 문서를 따라요."),
])
def test_only_the_copyright_block_remains(payload):
    runner(payload=payload)
    j = post(Q_DOC, llm="claude").json()
    dumped = json.dumps(j, ensure_ascii=False)
    assert j["status"] == "확인 필요" and "원문 출처 표기" in j["conclusion"] and "RD0080" not in dumped and "TG0125" not in dumped   # sanitize.FORBIDDEN이 잡는 꼴(RD·TG·AD·ID 번호·URL …)


def test_copyright_block_also_covers_the_insufficient_opening():
    runner(payload=chat(opening="RD0080에도 없어요.", insufficient=True))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "확인 필요" and "원문 출처 표기" in j["conclusion"] and "RD0080" not in json.dumps(j, ensure_ascii=False)


# ------------------------------------------------------------------ ⑫ 끝 안전 문구 불변
def test_closing_caution_strings_and_conditions_are_unchanged():
    assert ANS.PURE_CAUTION_V19 == "근거 안내이며 실행 지시가 아닙니다."
    assert ANS.PURE_CAUTION_SAFETY_V19 == ("근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, "
                                           "전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.")
    runner(payload=chat(opening="쿨런트는 절삭유예요.", points=["하나", "둘", "셋"], closing="끝이에요."))
    assert post(Q_DOC, llm="claude").json()["caution"] == ANS.PURE_CAUTION_V19                                    # 합니다체 그대로 (알려진 한계)
    runner(payload=chat(opening="고전압 대기는 5분이에요."))
    safe = post(Q_SAFETY, llm="claude").json()
    assert safe["status"] == "답변" and safe["caution"] == ANS.PURE_CAUTION_SAFETY_V19                              # 안전 낱말이 있으면 안전 문구
    runner(payload=chat(opening="근거 없는 답이에요.", cited=[]))
    assert post(Q_DOC, llm="claude").json()["caution"] is None                                                     # 근거 조각이 없으면 문구도 없음


# ------------------------------------------------------------------ 다른 길은 그대로
@pytest.mark.parametrize("q", [Q_DOC, Q_ALARM, Q_OPS])
def test_style_on_but_local_request_is_identical_to_style_off(monkeypatch, q):
    rn = runner()
    C.use_transport(httpx.MockTransport(lambda req: httpx.Response(500)))   # 로컬 서버 오류(HTTP 500): 세 번이 같은 조건이다
    monkeypatch.setenv("PURE_STYLE", "0")
    a = post(q).json()
    monkeypatch.setenv("PURE_STYLE", "1")
    b = post(q, llm="local").json()
    c = post(q).json()
    for x in (a, b, c):
        x.pop("answer_id", None)
        for t in x.get("llm_trace") or []:
            t.pop("ms", None)
    assert a == b == c and "llm" not in a and rn.calls == []


def test_style_on_but_pure_off_still_goes_through_route_first(monkeypatch):
    monkeypatch.setenv("PURE_EXTERNAL", "0")
    rn = runner()
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"]["job"] == "route" and rn.style_calls() == [] and rn.old_calls() == []   # 순수 길이 꺼져 있으면 말투 스위치는 아무 일도 안 한다


@pytest.mark.parametrize("q", DANGER)
def test_dangerous_requests_are_still_refused_before_the_pure_path(q):
    rn = runner()
    j = post(q, llm="claude").json()
    assert j["status"] == "안내" and j["mode"] == "규칙" and rn.calls == [] and j["llm"]["calls"] == 0


def test_style_on_signals_still_go_to_the_pure_path(env):
    rn = runner()
    for q in (Q_ALARM, Q_OPS):
        j = post(q, llm="claude").json()
        assert j["status"] == "답변" and j["steps"] == [] and j["current_data"] == [] and "순수 연결" in j["mode"]
    assert [c["props"] for c in rn.calls] == [STYLE_PROPS, STYLE_PROPS] and env == []


# ------------------------------------------------------------------ ⑬ STEP_LOG (읽기만)
def _rec():
    files = list(Path(os.environ["STEP_LOG_DIR"]).glob("steps_*.jsonl"))
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf-8").splitlines()[-1]), files[0].read_text(encoding="utf-8")


def test_step_log_records_the_shape_when_style_is_on(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    runner(payload=chat(opening="결론이에요.", points=["하나", "둘", "셋"], closing="끝이에요.", cited=["C1", "C77"]))
    j = post(Q_DOC, llm="claude").json()
    rec, raw = _rec()
    assert j["step_log_id"]
    names = [s["단계"] for s in rec["단계"]]
    order = [names.index(x) for x in ("1 규칙 판정", "2 질문 분류", "3 찾기", "순수 호출 결과", "출처 변환", "순수 짜임")]
    assert order == sorted(order) and "알람 카드" not in names and "운영 조회" not in names and "4 줄 고르기" not in names
    shape = next(s for s in rec["단계"] if s["단계"] == "순수 짜임")
    assert shape["말투바꾸기"] is True and shape["항목수"] == 3 and shape["마무리있음"] is True and shape["머리글자수"] == len("결론이에요.") and shape["충분하지않음"] is False
    res = next(s for s in rec["단계"] if s["단계"] == "순수 호출 결과")
    assert res["답"] == "결론이에요.\n1) 하나\n2) 둘\n3) 셋\n끝이에요." and res["받은인용"] == ["C1", "C77"] and res["충분하지않음"] is False
    assert next(s for s in rec["단계"] if s["단계"] == "출처 변환")["버린항목"] == ["C77"]
    assert "[사내 문서 조각]" not in raw and PURE.SYSTEM_CHAT not in raw                                          # 보낸 글 전체는 남기지 않는다 (글자 수만)


def test_step_log_has_no_shape_line_when_style_is_off(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    monkeypatch.setenv("PURE_STYLE", "0")
    runner()
    assert post(Q_DOC, llm="claude").status_code == 200
    rec, _ = _rec()
    names = [s["단계"] for s in rec["단계"]]
    assert "순수 짜임" not in names and "순수 호출 결과" in names                                                     # 끔의 기록 모양은 지금과 같다
    res = next(s for s in rec["단계"] if s["단계"] == "순수 호출 결과")
    assert res["답"] == OLD_PAYLOAD["answer"] and set(res) >= {"보낸글자수", "ms", "충분하지않음", "답", "받은인용"}


def test_step_log_off_writes_nothing_with_style_on():
    runner()
    j = post(Q_DOC, llm="claude").json()
    assert "step_log_id" not in j and not Path(os.environ["STEP_LOG_DIR"]).exists()


def test_step_log_records_the_insufficient_shape(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    runner(payload=chat(opening="문서에 답이 없어요.", insufficient=True))
    assert post(Q_DOC, llm="claude").status_code == 200
    rec, _ = _rec()
    shape = next(s for s in rec["단계"] if s["단계"] == "순수 짜임")
    assert shape["충분하지않음"] is True and shape["항목수"] == 0 and shape["마무리있음"] is False
