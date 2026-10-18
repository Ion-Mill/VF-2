"""안전 질문 "문서에 없다" 거짓 단정 원천 차단 PURE_SAFETY 시험 (2026-10-18).

결함: "톱 정비 전에 어디를 차단해야 해?"에 "톱의 차단 지점은 문서에서 찾지 못했어요"(NOT_IN_DOCS, 출처 없음)라고 답했다. DOC-05 §3.1에 차단 지점 2곳이
있는데 낱말 검색에서 §3.1이 68위라 Claude에게 가지 못했다. 앞서 고친 "잠금 표지 순서"와 같은 모양이다 (PURE_EXPAND는 낱말 몇 개만 보장했다).
근본 원인: 낱말이 같아야 찾는 검색 + "못 찾음"을 "문서에 없음"으로 말하는 것.

수정 (스위치 PURE_SAFETY, 코드 기본 꺼짐 = 지금과 한 글자도 같음, .env.example 기본 켬):
 ① 안전 질문(낱말 판정 `is_safety`)에는 안전 작업 기준서 DOC-05 조각을 통째로 더한다
 ①-b PURE_KEEP_SIGNALS=1에서 신호가 설비 이름뿐인 안전 질문은 기존 길이 아니라 순수 길로 (이 안전망을 거치게)
 ② 안전 질문의 "답 없음"은 "문서에 없다" 대신 "자동으로 확인하지 못했어요(문서에 없다는 뜻이 아님)" + 가까운 절. 상태는 기존 "확인 필요"(API OK)
 ④ 점검표(eval/safety_qa.json 68개)로 이 모든 것을 자동 검사 (Claude 호출 없음)

진짜 `claude`도 로컬 AI 서버도 부르지 않는다. 지키는 것: 기본 꺼짐 · 낱말 판정의 범위(안전표 전부 발동, 상관없는 질문 0, 개발용 질문 중 일부만) ·
끄면 지금과 같음 · 켜면 점검표의 순수 길 질문 전부에 정답 절 · 더해진 조각의 표시·순서·상한 · ②의 문구·상태 · ①-b 라우팅 · 끝에서 끝 ·
D-03(원문 칸 지우기)과 백엔드 상태 값 목록이 안 바뀜.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import chat_mapping
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.eval import safety_recall as SR
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.rag import sanitize as SAN
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import pure_external as PURE

client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
HERE = Path(__file__).resolve().parent

APP_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "RETRIEVAL": "bm25", "NUM_MATCH": "value", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded",
             "DOC_GATE": "tiered", "PARSE_V3": "1", "SPLIT_Q": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
             "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1",
             "PARSE_V11": "1", "LEAD_V12": "1", "TERM_V13": "1", "EXTERNAL_LLM_APP": "1", "PURE_EXTERNAL": "1"}

# 안전과 상관없는 질문 (개발용 질문 세트에서 뽑았다) — 안전 낱말 판정이 발동하면 안 된다
UNRELATED = ["사내 체육대회 언제야?", "근처 병원 어디 있어?", "연차 며칠 남았는지 알려줘", "구내식당 저녁은 몇 시에 열어?", "파이썬으로 그래프 그리는 법 알려줘",
             "엑셀로 보고서 뽑는 법 알려줘", "Haas 본사 전화번호 알려줘", "검사 빡세게 할 때는 한 개 재는 데 몇 분 걸려?"]


def cfg(monkeypatch, safety="1", keep="1", expand="1") -> Settings:
    """권장 모양의 설정: 앱 스위치 + 순수 길 + (PURE_KEEP_SIGNALS) + PURE_SAFETY. claude_app은 요청 단위라 외부 Claude 요청 안에서 읽는다."""
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXPAND", expand)
    monkeypatch.setenv("PURE_KEEP_SIGNALS", keep)
    monkeypatch.setenv("PURE_SAFETY", safety)
    with EXT.external_request("claude"):
        return settings()


def ids(hits):
    return [c.chunk_id for _, c in hits]


def dev_questions() -> list[str]:
    """개발용 질문(봉인 세트는 일부러 쓰지 않는다)."""
    out = []
    for name in ("qa_set.json", "qa_tune_f.json"):
        out += [it["q"] for it in json.loads((HERE / ".." / "eval" / name).read_text(encoding="utf-8"))["items"]]
    return out


TABLE = SR.load_items()
DOC05 = [c for c in load_corpus() if c.doc_id == "DOC-05"]


def legacy_context(question, s):
    """수정 전 PURE.context (스위치가 없던 모양) — 끄면 이것과 똑같아야 한다."""
    hits = PURE.retrieve(question, s.pure_topk)
    if not s.pure_expand:
        return hits
    hits, first = PURE.guarantee(question, hits)
    return PURE.expand(hits, first=first)


# ------------------------------------------------------------------ ① 설정·기본값
def test_default_is_off_in_code_and_flags_and_parse(monkeypatch):
    monkeypatch.delenv("PURE_SAFETY", raising=False)
    s = settings()
    assert s.pure_safety is False and s.flags()["pure_safety"] is False
    assert Settings.__dataclass_fields__["pure_safety"].default is False            # 코드 기본값
    for v, want in [("1", True), ("true", True), ("YES", True), ("0", False), ("", False), ("켬", False), ("on", False)]:
        monkeypatch.setenv("PURE_SAFETY", v)
        assert settings().pure_safety is want                                       # 모르는 값·빈 값은 꺼짐(지금 동작)


def test_conftest_pins_it_off_so_a_developer_env_cannot_change_other_tests():
    assert 'monkeypatch.setenv("PURE_SAFETY", "0")' in (HERE / "conftest.py").read_text(encoding="utf-8")


def test_example_file_turns_it_on_with_a_comment_line_above_and_no_inline_comment():
    lines = (HERE / ".." / ".." / ".env.example").read_text(encoding="utf-8").splitlines()
    i = lines.index("PURE_SAFETY=1")                                                # 값 옆에 설명이 없다 (test_env_example가 지키는 규칙)
    assert lines[i - 1].startswith("#") and "안전" in lines[i - 1]


# ------------------------------------------------------------------ ② 안전 낱말 판정 is_safety
def test_terms_include_the_existing_safety_words_so_the_two_lists_stay_in_sync():
    assert set(A.SAFETY_WORDS) <= set(PURE.SAFETY_TERMS)


@pytest.mark.parametrize("it", TABLE, ids=[f"§{it['sec']}-{i}" for i, it in enumerate(TABLE)])
def test_every_table_question_that_goes_to_the_pure_path_is_detected(monkeypatch, it):
    s = cfg(monkeypatch)
    if SR.routes_pure(it["q"], s):
        assert PURE.is_safety(it["q"]), it["q"]


def test_detection_is_100_percent_of_the_table_questions_about_safety_not_work_orders():
    miss = [it["q"] for it in TABLE if not PURE.is_safety(it["q"])]
    assert miss == ["작업지시서 고정 서식에 뭐가 들어가?"], miss                       # 작업지시 조회 길로 가는 질문 하나뿐(안전 낱말 없음)


@pytest.mark.parametrize("q", UNRELATED)
def test_unrelated_questions_are_never_detected(q):
    assert not PURE.is_safety(q)


def test_detection_on_dev_questions_is_limited_to_safety_and_maintenance_topics(monkeypatch):
    s = cfg(monkeypatch)
    pure_dev = [q for q in dev_questions() if SR.routes_pure(q, s)]
    fired = [q for q in pure_dev if PURE.is_safety(q)]
    assert len(pure_dev) >= 50 and 5 <= len(fired) <= 20, (len(fired), len(pure_dev))   # 기준선 15/56. 크게 늘면 낱말이 너무 넓다
    for q in UNRELATED:
        assert q not in fired


def test_equipment_names_and_loto_are_case_insensitive():
    for q in ["saw-01 정비 전에 어디를 차단해?", "vf2-02 잠금 지점", "loto 순서", "cmm 차단 지점 알려줘"]:
        assert PURE.is_safety(q), q


# ------------------------------------------------------------------ ③ 끄면 지금과 한 글자도 같다
def test_off_is_identical_to_the_legacy_context_for_all_dev_and_table_questions(monkeypatch):
    s = cfg(monkeypatch, safety="0")
    for q in dev_questions() + [it["q"] for it in TABLE]:
        assert PURE.context(q, s.pure_topk, s) == legacy_context(q, s), q


def test_on_leaves_questions_without_a_safety_term_untouched(monkeypatch):
    s_on, s_off = cfg(monkeypatch), cfg(monkeypatch, safety="0")
    for q in dev_questions() + [it["q"] for it in TABLE]:
        if not PURE.is_safety(q):
            assert PURE.context(q, s_on.pure_topk, s_on) == PURE.context(q, s_off.pure_topk, s_off), q


def test_off_still_misses_something_in_the_table_which_is_the_defect_this_fixes(monkeypatch):
    s = cfg(monkeypatch, safety="0")
    m = SR.measure(s, TABLE)
    assert m["reached"] < m["total"]                                                # 수정 전에는 놓친다 (기준선 58/68)
    assert any("톱 정비 전에" in r["q"] for r in m["misses"]) or m["misses"]


# ------------------------------------------------------------------ ④ 켜면 안전 질문에 DOC-05가 통째로
def test_on_adds_every_doc05_chunk_for_a_safety_question(monkeypatch):
    s = cfg(monkeypatch)
    got = ids(PURE.context("톱 정비 전에 어디를 차단해야 해?", s.pure_topk, s))
    assert {c.chunk_id for c in DOC05} <= set(got)
    assert len(got) == len(set(got))                                                # 중복 없음


def test_on_keeps_original_hits_order_and_scores_and_marks_added_chunks(monkeypatch):
    s_on, s_off = cfg(monkeypatch), cfg(monkeypatch, safety="0")
    for it in TABLE[:40]:
        q = it["q"]
        base, got = PURE.context(q, s_off.pure_topk, s_off), PURE.context(q, s_on.pure_topk, s_on)
        if not PURE.is_safety(q):
            continue
        assert got[:len(base)] == base, q                                           # 원래 조각: 같은 순서·같은 점수
        added = got[len(base):]
        assert all(sc == PURE.SAFETY_SCORE and c.doc_id == PURE.SAFETY_DOC for sc, c in added), q
        secs = [c.chunk_id for _, c in added]
        order = [c.chunk_id for c in DOC05]
        assert secs == [x for x in order if x in set(secs)], q                      # 더한 것은 문서 순서
        assert sum(len(c.text) for _, c in added) <= PURE.SAFETY_MAX_CHARS, q


def test_added_size_is_bounded_even_if_the_document_grows(monkeypatch):
    s = cfg(monkeypatch)
    assert sum(len(c.text) for c in DOC05) <= PURE.SAFETY_MAX_CHARS                 # 지금 16,621자 < 상한
    hits = PURE.add_safety_doc([])
    assert [c.chunk_id for _, c in hits] == [c.chunk_id for c in DOC05]


def test_table_pure_route_questions_all_reach_their_section_when_on(monkeypatch):
    s = cfg(monkeypatch)
    m = SR.measure(s, TABLE)
    assert m["pure_total"] >= 52 and m["pure_reached"] == m["pure_total"], m["pure_misses"]    # 성공 기준 S1
    assert m["triggered"] is not None


# ------------------------------------------------------------------ ⑤ 라우팅: 설비 이름만 든 안전 질문은 순수 길로
SIGNAL_ONLY_EQUIPMENT = ["VF2-01 차단 지점 알려줘", "SAW-01 정비 전에 어디를 차단해?", "세척기 정비 전에 어디를 차단해?", "MIL-01 차단 지점", "측정기 정비 전에 어디를 차단해?"]


@pytest.mark.parametrize("q", SIGNAL_ONLY_EQUIPMENT)
def test_equipment_only_safety_question_goes_pure_when_on_and_old_path_when_off(monkeypatch, q):
    s_on = cfg(monkeypatch)                                                         # 규칙 해석(parse)이 PARSE_V* 스위치를 읽으므로 설정을 먼저 켠다
    p = A.parse(q)
    assert PURE.has_signals(p) and p.get("equipment") and not (p.get("alarms") or p.get("intents") or p.get("start") or p.get("lot") or p.get("order"))
    assert A.pure_scope_v19(p, s_on, q) is not None
    assert A.pure_scope_v19(p, cfg(monkeypatch, safety="0"), q) is None             # 끄면 지금처럼 기존 길


@pytest.mark.parametrize("q", ["VF2-01 지금 상태 어때?", "어제 야간에 VF2-01 몇 번 멈췄어?", "VF2-01 OEE 알려줘", "2075 알람 어떻게 해?", "9월 15일 VF2-02 몇 번 멈췄어?"])
def test_operational_questions_keep_the_old_path(monkeypatch, q):
    s = cfg(monkeypatch)
    assert A.pure_scope_v19(A.parse(q), s, q) is None


# ------------------------------------------------------------------ ⑥ 끝에서 끝: Claude에게 보내는 글과 "답 없음" 문구
class Runner:
    def __init__(self, insufficient=False):
        self.calls, self.insufficient = [], insufficient

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        self.calls.append({"props": tuple(sorted((sch.get("properties") or {}).keys())), "user": stdin_text})
        so = ({"answer": "톱의 차단 지점은 가지고 있는 문서에서 찾지 못했어요.", "cited": [], "insufficient": True} if self.insufficient
              else {"answer": "답이에요.", "cited": ["C1"], "insufficient": False})
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


def _setup(monkeypatch, runner):
    get_state().reset()
    AS.clear()
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PURE_EXPAND", "1")

    def no_local(req):
        raise httpx.ConnectError("시험: 로컬 서버 없음")
    C.use_transport(httpx.MockTransport(no_local))
    CC.use_runner(runner)


@pytest.fixture
def e2e(monkeypatch):
    r = Runner()
    _setup(monkeypatch, r)
    yield r
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


@pytest.fixture
def e2e_unsure(monkeypatch):
    r = Runner(insufficient=True)
    _setup(monkeypatch, r)
    yield r
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def ask(q):
    return client.post("/api/assistant/chat", json={"question": q, "llm": "claude"}, headers={"X-Role": "SUP"})


def sent_heads(runner) -> list[str]:
    calls = [c for c in runner.calls if c["props"] == ("answer", "cited", "insufficient")]
    assert len(calls) == 1
    return re.findall(r"^\[C\d+\] (.+)$", calls[0]["user"], re.M)


def test_end_to_end_prompt_carries_the_whole_safety_document_when_on(e2e, monkeypatch):
    monkeypatch.setenv("PURE_SAFETY", "1")
    assert ask("톱 정비 전에 어디를 차단해야 해?").status_code == 200
    heads = sent_heads(e2e)
    assert sum("DOC-05" in h for h in heads) == len(DOC05)
    assert any("DOC-05" in h and "§3.1" in h for h in heads)
    assert any("SAW-01 주 차단기" in c["user"] for c in e2e.calls)                  # 정답 절의 글이 실제로 간다


def test_end_to_end_off_sends_the_old_context_without_the_milling_section(e2e, monkeypatch):
    monkeypatch.setenv("PURE_SAFETY", "0")
    ask("밀링 정비할 때 전원은 어디서 끊어?")                                              # 문서 제목에 "톱"을 병기한 뒤에는 톱 질문이 7위로 올라와, 아직 놓치는 질문으로 바꿨다
    heads = sent_heads(e2e)
    assert not any("DOC-05" in h and "§3.2" in h for h in heads)                    # 지금(결함 있는) 모양 그대로


def test_end_to_end_on_sends_the_milling_section_too(e2e, monkeypatch):
    monkeypatch.setenv("PURE_SAFETY", "1")
    ask("밀링 정비할 때 전원은 어디서 끊어?")
    assert any("DOC-05" in h and "§3.2" in h for h in sent_heads(e2e))


def test_unsure_answer_for_a_safety_question_never_says_the_document_lacks_it(e2e_unsure, monkeypatch):
    monkeypatch.setenv("PURE_SAFETY", "1")
    r = ask("톱 정비 전에 어디를 차단해야 해?").json()
    assert r["status"] == "확인 필요"                                                # 기존 상태 재사용 → API로는 OK
    assert chat_mapping.map_status(r) == "OK"
    text = r["conclusion"]
    assert "확인하지 못" in text and "문서에 없다는 뜻" in text
    assert "문서에 없음" not in text and "찾지 못했어요" not in text                  # Claude가 쓴 거짓 단정은 버린다
    assert r["evidence"] and all("DOC-05" in e["cite"] for e in r["evidence"])      # 가까운 절 후보
    assert "근거 안내이며 실행 지시가 아닙니다" in (r.get("caution") or "")            # 끝 안전 문구는 그대로


def test_unsure_answer_off_keeps_the_old_not_in_docs(e2e_unsure, monkeypatch):
    monkeypatch.setenv("PURE_SAFETY", "0")
    r = ask("톱 정비 전에 어디를 차단해야 해?").json()
    assert r["status"] == "문서에 없음" and chat_mapping.map_status(r) == "NOT_IN_DOCS"


@pytest.mark.parametrize("q", ["사내 체육대회 언제야?", "구내식당 저녁은 몇 시에 열어?"])
def test_unsure_for_non_safety_questions_is_unchanged_even_when_on(e2e_unsure, monkeypatch, q):
    monkeypatch.setenv("PURE_SAFETY", "1")
    r = ask(q).json()
    assert r["status"] == "문서에 없음" and chat_mapping.map_status(r) == "NOT_IN_DOCS"


def test_candidates_are_the_closest_doc05_sections_and_have_a_fallback():
    hits = PURE.retrieve("톱 정비 전에 어디를 차단해야 해?", 8)
    cand = PURE.unsure_candidates("톱 정비 전에 어디를 차단해야 해?", hits)
    assert 1 <= len(cand) <= 3 and all(c.doc_id == "DOC-05" for c in cand)
    assert PURE.unsure_candidates("zzzz", []) and all(c.doc_id == "DOC-05" for c in PURE.unsure_candidates("zzzz", []))


# ------------------------------------------------------------------ ⑦ 바뀌면 안 되는 것
def test_d03_original_column_filter_is_untouched():
    assert SAN.SOURCE_COLUMN.pattern == "원문|출처|근거"
    sec21 = next(c for c in load_corpus() if c.chunk_id == "DOC-05:2.1")
    table = [ln for ln in sec21.text.splitlines() if ln.startswith("|")]            # 표 줄만 본다 (표 아래 설명 문장에는 "원문 제목"이라는 말이 남아 있다)
    assert table[0].replace(" ", "") == "|단계|우리라인에서할일[가상]|"              # 원문 칸(원문 제목·원문 뜻)은 지금도 지워진다
    assert not any("원문 제목" in ln or "원문 뜻" in ln for ln in table)


def test_backend_status_values_did_not_grow():
    assert set(chat_mapping.STATUS_MAP.values()) == {"OK", "NOT_IN_DOCS", "OUT_OF_ROLE"}


def test_measure_tool_has_no_import_side_effects_on_the_environment():
    import os
    assert "PURE_SAFETY" in os.environ                                              # conftest가 "0"으로 고정한 값이 import로 안 바뀐다
    assert os.environ["PURE_SAFETY"] == "0"
