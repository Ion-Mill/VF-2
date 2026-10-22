"""순수 외부 LLM 묶음 목록 형식 PURE_LAYOUT 시험 (2026-10-16) — 시험용 복사본 전용.

진짜 `claude`도 로컬 AI 서버도 부르지 않는다 — 가짜 `claude` 실행기(`CC.use_runner`)와 로컬 쪽 가짜 전송(`C.use_transport`)만 쓴다.
`test_pure_external.py`·`test_pure_style.py`(끔 = 지금 동작이 그대로임을 보이는 회귀 보증)는 고치지 않았고, 이 파일은 켬(PURE_STYLE=1 + PURE_LAYOUT=1)에서 바뀌는 것과
PURE_LAYOUT=0이면 PURE_STYLE=1의 지금 동작이 글자까지 같음을 본다.

지키는 것: ① 기본 꺼짐·flags·값 읽기·기본값 다섯 곳 고정 ② PURE_LAYOUT=0이면 PURE_STYLE=1의 지시문·스키마·max_tokens(1600)·응답 모양이 지금과 같고, PURE_STYLE=0이면 PURE_LAYOUT=1이어도 원래 말투
③ 켬이면 새 지시문·스키마(sections·cited·insufficient, 묶음 title·text·items) ④ 운영 안내 줄(13번)은 PURE_KEEP_SIGNALS=0일 때만 ⑤ 묶음 → 화면 블록 조립(section·ops·lead·text·원문 줄)과 conclusion
⑥ 번호 접두어 지움·빈 묶음 버림·모양 이상 버림 ⑦ insufficient: 상태 "문서에 없음" + Claude가 쓴 글 ⑧ 실패·빈 답은 503, 검색 결과 없음은 호출 0번 ⑨ 코드 검사가 여전히 없음 ⑩ 저작권 차단 유지
⑪ 끝 안전 문구 불변 ⑫ 이어 묻기 기억 ⑬ STEP_LOG.
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
PURE_PROPS = ("answer", "cited", "insufficient")                                    # 기존 말투(PURE_STYLE=0)의 스키마 칸
STYLE_PROPS = ("cited", "closing", "insufficient", "opening", "points")           # PURE_STYLE=1 (PURE_LAYOUT=0)의 스키마 칸
LAYOUT_PROPS = ("cited", "insufficient", "sections")                              # PURE_STYLE=1 + PURE_LAYOUT=1의 스키마 칸
Q_DOC = "쿨런트가 뭐야?"
Q_ALARM = "알람 2075가 왜 자꾸 떠?"
Q_OPS = "어제 VF2-01 몇 번 멈췄어?"
Q_SAFETY = "고전압 대기는 어떻게 해?"
DANGER = ["알람 108 리셋해 줘", "VF2-01 전원 꺼 줘"]
OPS_NOTE = "운영 기록(정지 횟수, 생산량, 재고 수량, 알람이 난 이력, 지금 설비 상태)을 조회하지 못한다"   # 지시문 13번 줄의 한 구절
OLD_EXAMPLES = ("아래 이유부터 의심해 볼 수 있어요", "실제 원인은 담당자가 확인해요", "문서에 나온 이유는 크게 세 가지예요")   # 예전 완성 문장 예시 — 새 지시문에 없어야 한다
# PURE_LAYOUT=0일 때 PURE_STYLE=1의 지시문이 지금 채팅 지시문과 글자까지 같은지 지문으로 고정한다. 2026-10-22에 일부만 못 찾은 문장을 바꾸며 지문을 다시 쟀다.
OLD_SYSTEM_CHAT_SHA = "d56cf8b15e643326e8dee5af0e9bc5ef02e051f562f32f5d83d1c0b9630a1b76"
OLD_SYSTEM_CHAT_KEEP_SHA = "370e85d9bc13b265a7078d5c1c8f3b20207a20d4ecba712c60844bdabb8e0cc9"
OLD_SCHEMA_CHAT_SHA = "9a4add607928da84f4c7660f75cd9bd9c63f57e8e728fd471bb7f5e0c0551488"
OLD_SYSTEM_SHA = "a8e9b819ceecb1122cf3ae68b6e4067bfb1f6cc8601ed845ee43cc36b4b3a53b"
OLD_SCHEMA_SHA = "735ba9d8246da54c68c494d00d2e54c5d70319e3a500c0885a0a03aca8641cfb"
APP_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "RETRIEVAL": "bm25", "NUM_MATCH": "value", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded",
             "DOC_GATE": "tiered", "PARSE_V3": "1", "SPLIT_Q": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
             "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1",
             "PARSE_V11": "1", "LEAD_V12": "1", "TERM_V13": "1", "EXTERNAL_LLM_APP": "1", "PURE_EXTERNAL": "1", "PURE_STYLE": "1", "PURE_LAYOUT": "1"}


def sec(title="", text="", items=()) -> dict:
    return {"title": title, "text": text, "items": list(items)}


def lay(sections=None, cited=("C1",), insufficient=False) -> dict:
    """묶음 목록 형식(켬)의 Claude 답 payload."""
    if sections is None:
        sections = [sec(text="쿨런트는 절삭유예요.")]
    return {"sections": sections, "cited": list(cited), "insufficient": insufficient}


STYLE_PAYLOAD = {"opening": "쿨런트는 절삭유예요.", "points": [], "closing": "", "cited": ["C1"], "insufficient": False}
OLD_PAYLOAD = {"answer": "옛 말투 답이에요.", "cited": ["C1"], "insufficient": False}


class Runner:
    """가짜 `claude` 실행기. 스키마 칸으로 어느 형식인지 알아보고 그 형식의 payload를 돌려준다 (mode에 따라 시간 초과·읽을 수 없는 글).
    호출마다 스키마·시스템 지시·사용자 글을 기록한다."""

    def __init__(self, payload=None, mode="ok"):
        self.payload = payload if payload is not None else lay()
        self.mode, self.calls = mode, []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append({"props": props, "schema": sch, "system": cmd[cmd.index("--system-prompt") + 1], "user": stdin_text})
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if props in (PURE_PROPS, STYLE_PROPS, LAYOUT_PROPS) and self.mode == "ok":
            body = {LAYOUT_PROPS: self.payload, STYLE_PROPS: STYLE_PAYLOAD, PURE_PROPS: OLD_PAYLOAD}[props]
            out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
                   "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                   "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": body}
            return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")
        return SimpleNamespace(returncode=0, stdout="JSON이 아닌 글", stderr="")

    def of(self, props):
        return [c for c in self.calls if c["props"] == props]


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


def kinds(blocks) -> list[str]:
    return [b["kind"] for b in blocks]


# 2075 모양의 5묶음: 결론 text / 소제목 + items / 소제목 + items / text / text
SECS_2075 = [
    sec(text="2075는 윤활유가 비었다는 알람이에요."),
    sec(title="의심해 볼 이유", items=["윤활유 통이 비었어요", "펌프가 안 돌아요", "배관이 새요"]),
    sec(title="먼저 확인할 것", items=["윤활유 통을 봐요", "펌프 소리를 들어요"]),
    sec(text="그래도 안 풀리면 보전 담당자에게 알려요."),
    sec(text="실제 원인은 담당자가 확인해요."),
]
JOINED_2075 = ("2075는 윤활유가 비었다는 알람이에요. 의심해 볼 이유: 1) 윤활유 통이 비었어요 2) 펌프가 안 돌아요 3) 배관이 새요 "
               "먼저 확인할 것: 1) 윤활유 통을 봐요 2) 펌프 소리를 들어요 그래도 안 풀리면 보전 담당자에게 알려요. 실제 원인은 담당자가 확인해요.")


# ------------------------------------------------------------------ ① 설정·기본값
def test_defaults_flags_and_parse(monkeypatch):
    monkeypatch.delenv("PURE_LAYOUT")   # 이 파일의 고정물이 "1"로 덮었다 — 아예 없으면 기본은 꺼짐
    monkeypatch.setattr(CFG, "_dotenv", lambda: {})   # 복사본 루트의 .env(앱 스위치)가 있어도 "코드 기본값"을 본다 (.env를 읽지 않음)
    s = settings()
    assert s.pure_layout is False and s.flags()["pure_layout"] is False
    assert Settings.__dataclass_fields__["pure_layout"].default is False   # 코드 기본값
    for v, want in [("1", True), ("true", True), ("YES", True), (" 1 ", True), ("0", False), ("", False), ("켬", False), ("on", False), ("2", False)]:
        monkeypatch.setenv("PURE_LAYOUT", v)
        assert settings().pure_layout is want and settings().flags()["pure_layout"] is want   # 모르는 값·빈 값은 꺼짐


def test_default_is_pinned_in_the_five_places():
    assert R._BASE["PURE_LAYOUT"] == "0"                                  # run_eval 모든 모드
    assert all(env["PURE_LAYOUT"] == "0" for env in R.MODES.values())
    here = Path(__file__).resolve().parent
    route_eval = (here / "../eval/route_eval.py").read_text(encoding="utf-8")
    assert route_eval.count('"PURE_LAYOUT"') == 2 and '"PURE_LAYOUT": "0"' in route_eval   # 분류 시험: 환경 보관 목록 + 기본 고정, 두 곳
    assert '"PURE_LAYOUT": "0"' in (here / "test_fallback_snapshot.py").read_text(encoding="utf-8")   # 스냅숏 만들기 명령
    assert 'setenv("PURE_LAYOUT", "0")' in (here / "conftest.py").read_text(encoding="utf-8")        # 시험 고정물
    assert "pure_layout: bool = False" in (here / "../config.py").read_text(encoding="utf-8")          # config 코드 기본값


# ------------------------------------------------------------------ ② PURE_LAYOUT=0 (또는 PURE_STYLE=0)이면 지금과 글자까지 같다
def test_layout_off_keeps_the_current_style_request_and_answer(monkeypatch):
    monkeypatch.setenv("PURE_LAYOUT", "0")
    assert sha(PURE.SYSTEM_CHAT) == OLD_SYSTEM_CHAT_SHA and sha(PURE.SYSTEM_CHAT_KEEP) == OLD_SYSTEM_CHAT_KEEP_SHA   # 고치기 전 복사본에서 잰 지문
    assert sha(json.dumps(PURE.SCHEMA_CHAT, sort_keys=True, ensure_ascii=False)) == OLD_SCHEMA_CHAT_SHA
    s = settings()
    assert PURE.system_for(s) is PURE.SYSTEM_CHAT and PURE.schema_for(s) is PURE.SCHEMA_CHAT                  # 같은 객체
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    assert PURE.system_for(settings()) is PURE.SYSTEM_CHAT_KEEP
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "0")
    seen = spy_chat_json(monkeypatch)
    rn = runner()
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["conclusion"] == STYLE_PAYLOAD["opening"] and j["blocks"][0] == {"kind": "lead", "text": "쿨런트는 절삭유예요.", "written": True}
    assert len(seen) == 1 and seen[0]["name"] == "pure_answer" and seen[0]["max_tokens"] == 1600                # max_tokens 그대로
    assert seen[0]["schema"] is PURE.SCHEMA_CHAT and seen[0]["messages"][0] == {"role": "system", "content": PURE.SYSTEM_CHAT}
    assert [c["props"] for c in rn.calls] == [STYLE_PROPS] and rn.calls[0]["system"] == PURE.SYSTEM_CHAT         # 가짜 실행기가 받은 지시문·스키마 칸도 그대로
    assert "sections" not in rn.calls[0]["schema"]["properties"]


def test_layout_off_response_has_no_layout_keys(monkeypatch):
    monkeypatch.setenv("PURE_LAYOUT", "0")
    runner()
    with EXT.external_request("claude"):   # 외부 Claude를 고른 요청 안에서만 settings()가 외부 공급자 값을 준다
        ask = PURE.ask(Q_DOC, [c for _, c in search(Q_DOC, 3)], None, settings())
    assert ask["style"] is True and "layout" not in ask and "sections" not in ask and {"opening", "points", "closing"} <= set(ask)   # 응답 모양(키)도 그대로


def test_style_off_ignores_layout_on(monkeypatch):
    monkeypatch.setenv("PURE_STYLE", "0")   # PURE_LAYOUT=1이어도 말투 바꾸기가 꺼져 있으면 원래 말투
    assert sha(PURE.SYSTEM) == OLD_SYSTEM_SHA and sha(json.dumps(PURE.SCHEMA, sort_keys=True, ensure_ascii=False)) == OLD_SCHEMA_SHA
    s = settings()
    assert s.pure_layout is True and PURE.system_for(s) is PURE.SYSTEM and PURE.schema_for(s) is PURE.SCHEMA
    seen = spy_chat_json(monkeypatch)
    rn = runner()
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["conclusion"] == OLD_PAYLOAD["answer"] and j["blocks"][0] == {"kind": "lead", "text": OLD_PAYLOAD["answer"], "written": True}
    assert len(seen) == 1 and seen[0]["max_tokens"] == 1200 and seen[0]["schema"] is PURE.SCHEMA
    assert [c["props"] for c in rn.calls] == [PURE_PROPS] and rn.calls[0]["system"] == PURE.SYSTEM
    chunks = [c for _, c in search(Q_DOC, 8)]
    assert seen[0]["messages"] == PURE.build_messages(Q_DOC, chunks, None)


# ------------------------------------------------------------------ ③ 켬: 새 지시문·스키마
def test_layout_on_sends_the_new_system_prompt_and_schema(monkeypatch, env):
    seen = spy_chat_json(monkeypatch)
    rn = runner()
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 200, r.json()
    assert [c["props"] for c in rn.calls] == [LAYOUT_PROPS] and env == []                                       # 새 칸 셋, 호출 1번, 로컬 Qwen 0번
    call, sch = rn.calls[0], rn.calls[0]["schema"]
    assert sorted(sch["required"]) == sorted(LAYOUT_PROPS) and sch["additionalProperties"] is False
    sub = sch["properties"]["sections"]
    assert sub["type"] == "array" and sub["items"]["type"] == "object" and sub["items"]["additionalProperties"] is False
    assert sorted(sub["items"]["required"]) == ["items", "text", "title"] and sorted(sub["items"]["properties"]) == ["items", "text", "title"]   # 묶음 칸 셋 모두 필수
    assert sub["items"]["properties"]["items"] == {"type": "array", "items": {"type": "string"}}
    assert sub["items"]["properties"]["title"] == {"type": "string"} and sub["items"]["properties"]["text"] == {"type": "string"}
    assert sch["properties"]["cited"] == {"type": "array", "items": {"type": "string"}} and sch["properties"]["insufficient"] == {"type": "boolean"}
    dumped = json.dumps(sch)
    for bad in ("$ref", "$defs", "minItems", "maxItems", "minLength", "maxLength", "pattern", "enum"):
        assert bad not in dumped, bad                                                                           # 개수·길이 제약·$ref 없음
    assert seen[0]["max_tokens"] == PURE.MAX_TOKENS_LAYOUT == 1800 and seen[0]["schema"] is PURE.SCHEMA_LAYOUT
    sy = call["system"]
    assert sy == PURE.SYSTEM_LAYOUT == PURE.system_for(settings())
    for must in ("sections", "소제목", "한 문장", "섞지", "예시의 글자", "모두 가상 사내 문서", "문서에는 없지만 일반적으로는", "담당자가 확인해요", "cited",
                 "쓰지 않는다", "새 의무를 만들지 않는다", "해요체", "insufficient", "title", "text", "items", "옆자리 선배가 질문한 사람에게 직접 설명해 주듯이 말한다.",
                 "글 안에는 문서 이름, 문서 번호, 절 번호를 쓰지 않는다(프로그램이 붙인다).", "순서를 바꾸거나 단계를 빼거나 더하지 않는다."):
        assert must in sy, must
    for n in range(1, 18):
        if n != 13:
            assert re.search(rf"^{n}\. ", sy, re.M), n                                                          # 1~17번 줄이 모두 있다 (13번은 아래 ④)
    for bad in OLD_EXAMPLES:
        assert bad not in sy, bad                                                                               # 예전 완성 문장 예시 복사 방지
    for old_field in ("opening", "points", "closing"):
        assert old_field not in sy, old_field                                                                   # 이전 형식의 칸 이름이 남아 있지 않다
    assert FORBIDDEN.search(sy) is None and "$ref" not in sy                                                    # 지시문에 원문 이름·번호 없음
    u = call["user"]
    assert [n for n, _ in user_chunks(u)] == list(range(1, 9)) and u.rstrip().endswith("[질문]\n" + Q_DOC)      # 사용자 글(조각·질문)은 PURE_STYLE=1과 같은 꼴
    assert seen[0]["messages"][0]["content"] == sy


# ------------------------------------------------------------------ ④ 운영 안내 줄은 PURE_KEEP_SIGNALS=0일 때만
def test_ops_note_only_when_keep_signals_is_off(monkeypatch):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "0")
    on0 = PURE.system_for(settings())
    assert on0 == PURE.SYSTEM_LAYOUT and OPS_NOTE in on0 and re.search(r"^13\. 이 연결은", on0, re.M)
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    on1 = PURE.system_for(settings())
    assert on1 == PURE.SYSTEM_LAYOUT_KEEP and OPS_NOTE not in on1 and not re.search(r"^13\. ", on1, re.M)   # 번호는 다시 매기지 않는다 (12 다음이 14)
    assert re.search(r"^12\. ", on1, re.M) and re.search(r"^14\. ", on1, re.M)
    for must in ("14. 설비를 켜라", "15. 안전·전기 작업 절차", "16. cited에는", "17. [바로 앞 대화]가 있으면"):   # 나머지 줄은 두 판 모두 같다
        assert must in on0 and must in on1
    assert on0.replace(PURE._LAYOUT_OPS + "\n", "") == on1                                                       # 차이는 13번 줄 하나뿐
    monkeypatch.setenv("PURE_STYLE", "0")
    assert PURE.system_for(settings()) is PURE.SYSTEM                                                            # 말투 끔이면 PURE_LAYOUT·PURE_KEEP_SIGNALS와 상관없이 옛 지시문


def test_ops_note_end_to_end_with_keep_signals(monkeypatch):
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    rn = runner()
    assert post(Q_DOC, llm="claude").status_code == 200                                                          # 신호가 없는 질문은 keep=1이어도 순수 길
    assert rn.calls[0]["system"] == PURE.SYSTEM_LAYOUT_KEEP and OPS_NOTE not in rn.calls[0]["system"]
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "0")
    assert post(Q_OPS, llm="claude").status_code == 200                                                          # keep=0은 운영 질문도 순수 길 — 13번 줄 포함
    assert rn.calls[1]["system"] == PURE.SYSTEM_LAYOUT and OPS_NOTE in rn.calls[1]["system"]


# ------------------------------------------------------------------ ⑤ 묶음 → 화면 블록 조립, conclusion
def test_five_sections_make_lead_section_ops_section_ops_text_text_then_original_lines():
    runner(payload=lay(SECS_2075))
    j = post(Q_ALARM, llm="claude").json()
    first = search(Q_ALARM, 8)[0][1]
    assert j["status"] == "답변" and j["written"] is True and j["evidence"][0]["cite"] == first.cite
    b = j["blocks"]
    assert kinds(b[:7]) == ["lead", "section", "ops", "section", "ops", "text", "text"]                         # 첫 문단만 lead, 나머지 한 문장은 text
    assert b[0] == {"kind": "lead", "text": "2075는 윤활유가 비었다는 알람이에요.", "written": True}
    assert b[1] == {"kind": "section", "text": "의심해 볼 이유"}
    assert b[2] == {"kind": "ops", "head": "", "items": ["윤활유 통이 비었어요", "펌프가 안 돌아요", "배관이 새요"], "source": None}   # text가 비면 head는 ""
    assert b[3] == {"kind": "section", "text": "먼저 확인할 것"}
    assert b[4] == {"kind": "ops", "head": "", "items": ["윤활유 통을 봐요", "펌프 소리를 들어요"], "source": None}
    assert b[5] == {"kind": "text", "text": "그래도 안 풀리면 보전 담당자에게 알려요."} and b[6] == {"kind": "text", "text": "실제 원인은 담당자가 확인해요."}
    rest = b[7:]
    assert rest and all(x["kind"] == "line" and x["orig"] is True and x["cite"]["cite"] == first.cite for x in rest)   # 원문 줄은 그대로 뒤에 붙어 [원문 보기]로 접힌다
    assert j["conclusion"] == JOINED_2075 == PURE.join_layout(PURE.compose_layout({"sections": SECS_2075}))
    assert j["steps"] == [] and j["current_data"] == [] and j["is_synthetic"] is False                             # 알람 카드·운영 조회는 여전히 없다


def test_a_section_with_text_and_items_makes_an_ops_block_with_that_head():
    runner(payload=lay([sec(title="이유", text="이유가 둘이에요.", items=["하나", "둘"]), sec(text="끝이에요.")]))
    j = post(Q_DOC, llm="claude").json()
    b = j["blocks"]
    assert b[0] == {"kind": "section", "text": "이유"} and b[1] == {"kind": "ops", "head": "이유가 둘이에요.", "items": ["하나", "둘"], "source": None}
    assert b[2] == {"kind": "lead", "text": "끝이에요.", "written": True}                                          # 맨 처음 나오는 한 문장 본문 하나가 lead
    assert j["conclusion"] == "이유: 이유가 둘이에요. 1) 하나 2) 둘 끝이에요."


def test_only_a_conclusion_section_is_a_lead_only_answer():
    runner(payload=lay([sec(text="쿨런트는 절삭유예요.")]))
    j = post(Q_DOC, llm="claude").json()
    assert j["blocks"][0] == {"kind": "lead", "text": "쿨런트는 절삭유예요.", "written": True} and set(kinds(j["blocks"][1:])) == {"line"}
    assert j["conclusion"] == "쿨런트는 절삭유예요."


def test_items_without_a_conclusion_section_have_no_lead_and_an_empty_head():
    runner(payload=lay([sec(title="이유", items=["하나", "둘"])]))
    j = post(Q_DOC, llm="claude").json()
    assert j["blocks"][:2] == [{"kind": "section", "text": "이유"}, {"kind": "ops", "head": "", "items": ["하나", "둘"], "source": None}]
    assert "lead" not in kinds(j["blocks"]) and j["written"] is True and j["conclusion"] == "이유: 1) 하나 2) 둘"


def test_a_title_only_section_is_a_heading_block():
    runner(payload=lay([sec(text="결론이에요."), sec(title="따로 제목만")]))
    j = post(Q_DOC, llm="claude").json()
    assert kinds(j["blocks"][:2]) == ["lead", "section"] and j["blocks"][1]["text"] == "따로 제목만" and j["conclusion"] == "결론이에요. 따로 제목만:"


def test_no_cited_number_keeps_the_answer_without_written_and_original_lines():
    runner(payload=lay([sec(text="그냥 답이에요."), sec(title="이유", items=["하나", "둘"]), sec(text="끝이에요.")], cited=[]))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["evidence"] == [] and "written" not in j and j["mode"].endswith("근거 조각 번호 없음")
    assert j["blocks"] == [{"kind": "lead", "text": "그냥 답이에요."}, {"kind": "section", "text": "이유"},
                           {"kind": "ops", "head": "", "items": ["하나", "둘"], "source": None}, {"kind": "text", "text": "끝이에요."}]
    assert j["caution"] is None                                                                                    # 근거 조각이 없으면 lead에 written도 없고 주의 문구도 없다


# ------------------------------------------------------------------ ⑥ 번호 접두어 지움 · 빈 묶음 버림 · 모양 이상 버림
def test_compose_layout_tidies_items_and_drops_empty_or_odd_sections():
    raw = {"sections": [
        {"title": "  이유  ", "text": " 둘이에요. ", "items": ["1. 하나", None, 3, {"a": 1}, ["x"], "", "  ", "둘째, 둘", "(3) 셋", True, "① 넷", "1.5배로 올려요"]},
        {"title": "", "text": "", "items": []},                       # 모두 비면 버림
        {"title": " ", "text": None, "items": ["", None, "  "]},       # 손질하면 모두 비므로 버림
        "문자열 묶음", 5, None, ["리스트 묶음"],                         # dict가 아니면 버림
        {"title": 7, "text": ["a"], "items": "목록 아님"},               # 문자열이 아닌 칸은 ""로, 목록이 아니면 []로 → 모두 비므로 버림
        {"title": "제목만", "text": "", "items": []},
        {"title": "", "text": "본문만", "items": []},
    ]}
    assert PURE.compose_layout(raw) == [
        {"title": "이유", "text": "둘이에요.", "items": ["하나", "둘", "셋", "넷", "1.5배로 올려요"]},
        {"title": "제목만", "text": "", "items": []},
        {"title": "", "text": "본문만", "items": []},
    ]
    for odd in ({}, {"sections": None}, {"sections": "목록 아님"}, {"sections": {"title": "a"}}, {"sections": 5}, {"sections": []}):
        assert PURE.compose_layout(odd) == []


def test_join_layout_rule():
    secs = [sec(text="가"), sec(title="나", items=["다", "라"]), sec(title="마", text="바", items=["사"]), sec(title="아"), sec(), sec(text="자")]
    assert PURE.join_layout(secs) == "가 나: 1) 다 2) 라 마: 바 1) 사 아: 자"
    assert PURE.join_layout([]) == "" and PURE.join_layout([sec(items=["하나"])]) == "1) 하나"


def test_prefixed_and_odd_items_become_clean_numbered_items_end_to_end():
    runner(payload=lay([sec(text="이유예요."), sec(title="이유", items=["1. 첫 이유", "2) 둘째 이유", "③ 셋째 이유", None, 7, "", "넷째 이유"])]))
    j = post(Q_DOC, llm="claude").json()
    ops = next(x for x in j["blocks"] if x["kind"] == "ops")
    assert ops["items"] == ["첫 이유", "둘째 이유", "셋째 이유", "넷째 이유"]                                          # 화면이 번호를 붙이므로 접두어는 지워졌다
    assert j["conclusion"] == "이유예요. 이유: 1) 첫 이유 2) 둘째 이유 3) 셋째 이유 4) 넷째 이유"


def test_empty_sections_in_the_middle_are_dropped_end_to_end():
    runner(payload=lay([sec(text="결론이에요."), sec(), sec(title="이유", items=["하나", "", "둘"]), sec(title=" ", text=" ", items=[" "])]))
    j = post(Q_DOC, llm="claude").json()
    assert kinds(j["blocks"][:3]) == ["lead", "section", "ops"] and j["blocks"][2]["items"] == ["하나", "둘"]
    assert j["blocks"][3]["kind"] == "line" and j["conclusion"] == "결론이에요. 이유: 1) 하나 2) 둘"


def test_odd_shapes_that_the_schema_check_lets_through_are_dropped_and_an_empty_result_is_503():
    runner(payload=lay(["문자열 묶음", 5, None, sec(text="진짜 묶음이에요.")]))                                       # dict가 아닌 묶음은 버려도 남는 묶음이 있으면 그대로 답한다
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["conclusion"] == "진짜 묶음이에요." and j["blocks"][0]["kind"] == "lead"
    for secs in ("목록 아님", [], ["문자열만", 5, None], [sec()], [sec(title=" ", text="  ", items=["", None])]):
        runner(payload=lay(secs))
        r = post(Q_DOC, llm="claude")
        assert r.status_code == 503 and r.json()["code"] == "EXTERNAL_LLM_UNAVAILABLE" and r.json()["detail"] == {"job": "pure_answer", "reason": "빈 답"}, secs


# ------------------------------------------------------------------ ⑦ insufficient: 문서에 없음 + Claude가 쓴 글
def test_insufficient_shows_the_texts_claude_wrote():
    runner(payload=lay([sec(text="사내 문서에는 그 알람의 기준값이 없어요."), sec(title="이유", items=["안 보여요"]), sec(text="알람 번호를 다시 확인해 보세요.")],
                       cited=["C1", "C2"], insufficient=True))
    j = post(Q_DOC, llm="claude").json()
    want = "사내 문서에는 그 알람의 기준값이 없어요. 알람 번호를 다시 확인해 보세요."
    assert j["status"] == "문서에 없음" and j["conclusion"] == want and j["conclusion"] != ANS.PURE_NO_DOC_V19      # 고정 문구가 아니라 Claude가 쓴 글 (소제목·목록은 쓰지 않음)
    assert j["evidence"] == [] and "written" not in j and not j.get("blocks") and j["caution"] is None             # 근거·원문 줄·블록·주의 문구 없음
    assert j["mode"].endswith("순수 연결 (검사 없음, 원문 출처 표기 차단만)") and j["llm"]["calls"] == 1 and j["retrieval"]["pure"] is True


def test_insufficient_with_no_text_uses_a_short_fixed_sentence_not_a_failure():
    for secs in ([], [sec(title="이유", items=["하나"])], [sec(text="   ")]):
        runner(payload=lay(secs, insufficient=True))
        r = post(Q_DOC, llm="claude")
        j = r.json()
        assert r.status_code == 200 and j["status"] == "문서에 없음" and j["conclusion"] == PURE.NO_OPENING_CHAT, secs
    assert PURE.NO_OPENING_CHAT.endswith("요.") and "합니다" not in PURE.NO_OPENING_CHAT


def test_insufficient_ask_result_is_one_section_of_the_joined_texts():
    runner(payload=lay([sec(text="가요."), sec(text="나요.")], insufficient=True))
    with EXT.external_request("claude"):
        got = PURE.ask(Q_DOC, [c for _, c in search(Q_DOC, 3)], None, settings())
    assert got["insufficient"] is True and got["answer"] == "가요. 나요." and got["sections"] == [sec(text="가요. 나요.")] and got["layout"] is True


# ------------------------------------------------------------------ ⑧ 실패·빈 답 → 503 (자동 대체 없음), 검색 결과 없음 → 호출 0번
@pytest.mark.parametrize("mode", ["timeout", "garbage"])
def test_external_failure_ends_with_an_error_and_never_falls_back(env, mode):
    rn = runner(mode=mode)
    r = post(Q_DOC, llm="claude")
    j = r.json()
    assert r.status_code == 503 and j["code"] == "EXTERNAL_LLM_UNAVAILABLE", j
    assert j["detail"]["job"] == "pure_answer" and j["detail"]["reason"]
    assert len(rn.calls) == 1 and env == []                                      # 재요청도 로컬·다른 길로의 대체도 없다 (PURE_STYLE=1 형식이나 끔 길로 되돌아가지도 않는다)
    assert EXT.override() is None and post(Q_DOC).status_code == 200            # 다음(기본) 요청은 멀쩡하다


def test_payload_missing_a_required_field_is_a_failure():
    runner(payload={"sections": [sec(text="답이에요.")], "cited": ["C1"]})                                          # insufficient 칸 없음
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"]["job"] == "pure_answer"
    runner(payload=lay([{"title": "", "text": "항목 칸이 없는 묶음이에요."}]))                                         # 묶음 칸 items 없음 (묶음 칸 셋은 모두 필수)
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"]["job"] == "pure_answer"


def test_no_search_hit_does_not_call_claude_and_says_it_briefly():
    rn = runner()
    j = post("zzqqxxvv", llm="claude").json()
    assert j["status"] == "문서에 없음" and rn.calls == [] and j["llm"]["calls"] == 0 and "검색 결과가 없어" in j["mode"]
    assert j["conclusion"] == ANS.PURE_NO_DOC_CHAT_V19 == "사내 문서에서 관련 내용을 찾지 못했어요. 쓰신 낱말을 바꿔서 다시 물어봐 주세요."


# ------------------------------------------------------------------ ⑨ 코드 검사가 여전히 없다
def test_no_checks_are_applied_to_the_answer_the_prompt_is_what_prevents_them():
    # 주의: 아래 문장들은 지시문(14·8번 등)이 막으려는 것이다. 지시문이 막는 것이지 코드가 막는 것이 아니다 — 이 시험은 "코드 검사가 새로 생기지 않았다"만 확인한다.
    # 지시·허락 꼴, 한글 수사, 지어낸 숫자, "~해야 한다"가 그대로 나가는 것은 이 방식의 알려진 한계다.
    bad_text = "공구를 바로 교체하세요. 그냥 리셋해도 돼요. 세 번 확인하세요."
    bad_items = ["온도는 135도예요", "작업자가 속도를 조정해야 합니다", "전원을 끄고 켜도 됩니다"]
    bad_last = "피드 레이트(Feed Rate)를 올리면 돼요."
    rn = runner(payload=lay([sec(text=bad_text), sec(title="이유", items=bad_items), sec(text=bad_last)]))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "답변" and j["blocks"][0] == {"kind": "lead", "text": bad_text, "written": True}
    assert j["blocks"][2] == {"kind": "ops", "head": "", "items": bad_items, "source": None} and j["blocks"][3] == {"kind": "text", "text": bad_last}
    assert j["conclusion"] == f"{bad_text} 이유: 1) {bad_items[0]} 2) {bad_items[1]} 3) {bad_items[2]} {bad_last}"
    assert len(rn.calls) == 1                                                                                      # 뜻 판정·재시도 호출도 없다


# ------------------------------------------------------------------ ⑩ 저작권 차단은 유지 (title · text · items · insufficient 어디에 있어도)
@pytest.mark.parametrize("secs", [
    [sec(title="RD0080 표")],
    [sec(text="RD0080 표를 보세요.")],
    [sec(text="주기예요."), sec(title="이유", items=["하나", "RD0080 3개월 항목", "셋"])],
    [sec(text="주기예요."), sec(text="TG0125 문서를 따라요.")],
    [sec(text="주기예요."), sec(title="이유", text="TG0125를 봐요.", items=["하나"])],
])
def test_only_the_copyright_block_remains(secs):
    runner(payload=lay(secs))
    j = post(Q_DOC, llm="claude").json()
    dumped = json.dumps(j, ensure_ascii=False)
    assert j["status"] == "확인 필요" and "원문 출처 표기" in j["conclusion"] and "RD0080" not in dumped and "TG0125" not in dumped   # sanitize.FORBIDDEN이 잡는 꼴(RD·TG·AD·ID 번호·URL …)


def test_copyright_block_also_covers_the_insufficient_text():
    runner(payload=lay([sec(text="RD0080에도 없어요.")], insufficient=True))
    j = post(Q_DOC, llm="claude").json()
    assert j["status"] == "확인 필요" and "원문 출처 표기" in j["conclusion"] and "RD0080" not in json.dumps(j, ensure_ascii=False)


# ------------------------------------------------------------------ ⑪ 끝 안전 문구 불변
def test_closing_caution_strings_and_conditions_are_unchanged():
    assert ANS.PURE_CAUTION_V19 == "근거 안내이며 실행 지시가 아닙니다."
    assert ANS.PURE_CAUTION_SAFETY_V19 == ("근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, "
                                           "전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.")
    runner(payload=lay(SECS_2075))
    assert post(Q_DOC, llm="claude").json()["caution"] == ANS.PURE_CAUTION_V19                                    # 합니다체 그대로 (알려진 한계)
    runner(payload=lay([sec(text="고전압 대기는 5분이에요.")]))
    safe = post(Q_SAFETY, llm="claude").json()
    assert safe["status"] == "답변" and safe["caution"] == ANS.PURE_CAUTION_SAFETY_V19                              # 안전 낱말이 있으면 안전 문구
    runner(payload=lay([sec(text="근거 없는 답이에요.")], cited=[]))
    assert post(Q_DOC, llm="claude").json()["caution"] is None                                                     # 근거 조각이 없으면 문구도 없음


# ------------------------------------------------------------------ ⑫ 이어 묻기 기억
def test_conclusion_is_what_followups_remember_and_what_the_next_question_sees():
    rn = runner(payload=lay([sec(text="결론이에요."), sec(title="이유", items=["하나", "둘", "셋"]), sec(text="끝이에요.")]))
    first = post(Q_DOC, llm="claude").json()
    joined = "결론이에요. 이유: 1) 하나 2) 둘 3) 셋 끝이에요."
    rec = AS.get(first["answer_id"], "", "SUP")
    assert first["conclusion"] == joined and rec["conclusion"] == joined and rec["doc_lead"] == "" and rec["doc_lines"]   # 이어 묻기 기억 = 이은 글, 검사 안 지난 앞머리 없음
    rn.payload = lay([sec(text="둘째 답이에요.")])
    q2 = "스핀들 워밍업은 몇 분 해?"
    second = post(q2, llm="claude", prev_answer_id=first["answer_id"]).json()
    u = rn.calls[1]["user"]
    assert second["status"] == "답변" and u.count("[바로 앞 대화]") == 1 and "앞 답: " + joined in u and u.rstrip().endswith("[질문]\n" + q2)


# ------------------------------------------------------------------ 다른 길은 그대로
@pytest.mark.parametrize("q", [Q_DOC, Q_ALARM, Q_OPS])
def test_layout_on_but_local_request_is_identical_to_layout_off(monkeypatch, q):
    rn = runner()
    C.use_transport(httpx.MockTransport(lambda req: httpx.Response(500)))   # 로컬 서버 오류(HTTP 500): 세 번이 같은 조건이다
    monkeypatch.setenv("PURE_LAYOUT", "0")
    a = post(q).json()
    monkeypatch.setenv("PURE_LAYOUT", "1")
    b = post(q, llm="local").json()
    c = post(q).json()
    for x in (a, b, c):
        x.pop("answer_id", None)
        for t in x.get("llm_trace") or []:
            t.pop("ms", None)
    assert a == b == c and "llm" not in a and rn.calls == []


def test_layout_on_but_pure_off_still_goes_through_route_first(monkeypatch):
    monkeypatch.setenv("PURE_EXTERNAL", "0")
    rn = runner()
    r = post(Q_DOC, llm="claude")
    assert r.status_code == 503 and r.json()["detail"]["job"] == "route"   # 순수 길이 꺼져 있으면 분류(route)부터 가고, 형식 스위치는 아무 일도 안 한다
    assert rn.of(LAYOUT_PROPS) == [] and rn.of(STYLE_PROPS) == [] and rn.of(PURE_PROPS) == []


@pytest.mark.parametrize("q", DANGER)
def test_dangerous_requests_are_still_refused_before_the_pure_path(q):
    rn = runner()
    j = post(q, llm="claude").json()
    assert j["status"] == "안내" and j["mode"] == "규칙" and rn.calls == [] and j["llm"]["calls"] == 0


def test_layout_on_signals_still_go_to_the_pure_path(env):
    rn = runner()
    for q in (Q_ALARM, Q_OPS):
        j = post(q, llm="claude").json()
        assert j["status"] == "답변" and j["steps"] == [] and j["current_data"] == [] and "순수 연결" in j["mode"]
    assert [c["props"] for c in rn.calls] == [LAYOUT_PROPS, LAYOUT_PROPS] and env == []


# ------------------------------------------------------------------ ⑬ STEP_LOG (읽기만)
def _rec():
    files = list(Path(os.environ["STEP_LOG_DIR"]).glob("steps_*.jsonl"))
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf-8").splitlines()[-1]), files[0].read_text(encoding="utf-8")


def test_step_log_records_the_layout_shape(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    runner(payload=lay([sec(text="결론이에요."), sec(title="이유", items=["하나", "둘", "셋"]), sec(title="확인", items=["넷", "다섯"]), sec(text="끝이에요.")],
                       cited=["C1", "C77"]))
    j = post(Q_DOC, llm="claude").json()
    rec, raw = _rec()
    assert j["step_log_id"]
    names = [s["단계"] for s in rec["단계"]]
    order = [names.index(x) for x in ("1 규칙 판정", "2 질문 분류", "3 찾기", "순수 호출 결과", "출처 변환", "순수 짜임")]
    assert order == sorted(order) and "알람 카드" not in names and "운영 조회" not in names and "4 줄 고르기" not in names
    shape = next(s for s in rec["단계"] if s["단계"] == "순수 짜임")
    assert shape["말투바꾸기"] is True and shape["배치"] == "묶음" and shape["묶음수"] == 4 and shape["소제목수"] == 2 and shape["목록항목수"] == [0, 3, 2, 0]
    assert shape["충분하지않음"] is False
    res = next(s for s in rec["단계"] if s["단계"] == "순수 호출 결과")
    assert res["답"] == "결론이에요. 이유: 1) 하나 2) 둘 3) 셋 확인: 1) 넷 2) 다섯 끝이에요." and res["받은인용"] == ["C1", "C77"] and res["충분하지않음"] is False
    assert next(s for s in rec["단계"] if s["단계"] == "출처 변환")["버린항목"] == ["C77"]
    assert "[사내 문서 조각]" not in raw and PURE.SYSTEM_LAYOUT not in raw                                         # 보낸 글 전체는 남기지 않는다 (글자 수만)


def test_step_log_layout_off_keeps_the_current_style_shape(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    monkeypatch.setenv("PURE_LAYOUT", "0")
    runner()
    assert post(Q_DOC, llm="claude").status_code == 200
    rec, _ = _rec()
    shape = next(s for s in rec["단계"] if s["단계"] == "순수 짜임")
    assert set(shape) >= {"말투바꾸기", "항목수", "마무리있음", "머리글자수", "충분하지않음"} and not ({"배치", "묶음수", "소제목수", "목록항목수"} & set(shape))   # 모양 그대로


def test_step_log_off_writes_nothing_with_layout_on():
    runner()
    j = post(Q_DOC, llm="claude").json()
    assert "step_log_id" not in j and not Path(os.environ["STEP_LOG_DIR"]).exists()


def test_step_log_records_the_insufficient_layout_shape(monkeypatch):
    monkeypatch.setenv("STEP_LOG", "1")
    runner(payload=lay([sec(text="문서에 답이 없어요."), sec(title="이유", items=["하나"])], insufficient=True))
    assert post(Q_DOC, llm="claude").status_code == 200
    rec, _ = _rec()
    shape = next(s for s in rec["단계"] if s["단계"] == "순수 짜임")
    assert shape["충분하지않음"] is True and shape["배치"] == "묶음" and shape["묶음수"] == 1 and shape["소제목수"] == 0 and shape["목록항목수"] == [0]   # 줄여진 한 묶음
