"""순수 외부 LLM 길의 "부모 조각 → 아래 절 확장" PURE_EXPAND 시험 (2026-10-18, '잠금 표지 순서' 안전 결함 수정).

결함: "잠금 표지 순서가 어떻게 돼?"에 "공통 순서는 문서에 없다"고 틀리게 답했다. 문서(DOC-05 §2.1 작업 전 6단계)에는 있는데 낱말 검색(BM25)에서
§2.1이 66위라 Claude에게 가지 않았기 때문이다 (조각 수를 20개로 늘려도 못 잡는다). 부모 조각(§2 잠금·표지 절차)은 상위 8개에 들어 있다.
수정: 상위 조각에 아래 절이 있으면 그 직계 아래 절을 짧은 것부터 몇 개 같이 준다 (개수·글자 상한 있음). 스위치 PURE_EXPAND, 코드 기본 꺼짐.

진짜 `claude`도 로컬 AI 서버도 부르지 않는다. 지키는 것:
① 기본 꺼짐·값 읽기 ② 켜면 잠금·표지 질문 변형 10개 모두 §2.1(작업 전 6단계)이 Claude에게 가는 조각에 든다 ③ 끄면 지금과 한 글자도 같다(개발용 질문 83개)
④ 켜도 원래 조각의 순서·점수는 그대로이고 더해진 것만 점수 0 ⑤ 어떤 조각이 부모여도 4개·3,000자(2026-10-18 DOC-05 Rev.3에서 2,500자 → 3,000자)를 넘지 않고, 직계 아래 절만 더하며 중복이 없다
⑥ 끝에서 끝: 켜면 Claude에게 보내는 글에 DOC-05 §2.1이 있고, 끄면 지금처럼 없다.
"""
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.rag.chunker import load_corpus
from backend.rag.search import search
from backend.services import answer_store as AS
from backend.services import pure_external as PURE

client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
HERE = Path(__file__).resolve().parent

# 잠금·표지 질문 변형 (수정 계획서 3-2). 사용자가 가장 자연스럽게 묻는 "잠금 표지 순서"류가 실패했다
LOCK_VARIANTS = ["잠금 표지 순서가 어떻게 돼?", "잠금 표지 순서", "잠금표지 순서가 어떻게 돼?", "작업 전 잠금 표지 6단계", "에너지 차단 절차", "LOTO 순서",
                 "정비 전에 전원 차단하고 잠그는 순서", "잠금장치 거는 순서 알려줘", "표지 거는 순서", "작업 후 잠금 풀기 순서"]
# 둘째 원인: "잠금"이 아니라 "잠그는/잠가"로 물으면 부모 §2조차 상위 8개 밖이다(15~112위) — 잠금 낱말 보장(GUARANTEED)이 필요하다
LOCK_VARIANTS_VERB = ["작업 전에 잠그는 순서 알려줘", "작업 전 잠그는 순서", "잠그는 순서", "정비 전 잠금 순서", "설비 정비 전에 뭐부터 잠가?",
                      "전원 차단하고 잠그는 순서 알려줘", "잠금 절차", "자물쇠 거는 순서", "잠금 해제 순서", "잠금장치 설치 순서"]

APP_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "RETRIEVAL": "bm25", "NUM_MATCH": "value", "PARSE_V2": "1", "ROUTE_POLICY": "llm_guarded",
             "DOC_GATE": "tiered", "PARSE_V3": "1", "SPLIT_Q": "1", "PARSE_V4": "1", "PARSE_V5": "1", "PARSE_V6": "1", "PARSE_V7": "1", "FOLLOWUP": "1",
             "PARSE_V8": "1", "FOLLOWUP_V2": "1", "PARSE_V9": "1", "FLOW_V9": "1", "BLOCKS_V2": "1", "PARSE_V10": "1", "FLOW_V10": "1", "BLOCKS_V3": "1",
             "PARSE_V11": "1", "LEAD_V12": "1", "TERM_V13": "1", "EXTERNAL_LLM_APP": "1", "PURE_EXTERNAL": "1"}


def ids(hits):
    return [c.chunk_id for _, c in hits]


def dev_questions() -> list[str]:
    """개발용 질문(봉인 세트는 일부러 쓰지 않는다 — 튜닝에 쓰지 않는다)."""
    out = []
    for name in ("qa_set.json", "qa_tune_f.json"):
        out += [it["q"] for it in json.loads((HERE / ".." / "eval" / name).read_text(encoding="utf-8"))["items"]]
    return out


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("PURE_EXPAND", "1")


# ------------------------------------------------------------------ ① 설정·기본값
def test_default_is_off_in_code_and_flags_and_parse(monkeypatch):
    monkeypatch.delenv("PURE_EXPAND")
    s = settings()
    assert s.pure_expand is False and s.flags()["pure_expand"] is False
    assert Settings.__dataclass_fields__["pure_expand"].default is False        # 코드 기본값
    for v, want in [("1", True), ("true", True), ("YES", True), ("0", False), ("", False), ("켬", False), ("on", False)]:
        monkeypatch.setenv("PURE_EXPAND", v)
        assert settings().pure_expand is want and settings().flags()["pure_expand"] is want   # 모르는 값·빈 값은 꺼짐(지금 동작)


def test_conftest_pins_it_off_so_a_developer_env_cannot_change_other_tests():
    assert 'setenv("PURE_EXPAND", "0")' in (HERE / "conftest.py").read_text(encoding="utf-8")


def test_env_example_documents_it_with_no_inline_comment():
    text = (HERE / "../../.env.example").read_text(encoding="utf-8")
    assert re.search(r"^PURE_EXPAND=[01]$", text, re.M)


# ------------------------------------------------------------------ ② 결함 재현과 수정: 잠금·표지 질문 변형
@pytest.mark.parametrize("q", LOCK_VARIANTS + LOCK_VARIANTS_VERB)
def test_lock_questions_now_carry_the_work_before_six_steps(q):
    s = settings()
    got = ids(PURE.context(q, s.pure_topk, s))
    assert "DOC-05:2.1" in got, f"{q!r}: 작업 전 6단계(DOC-05 §2.1)가 Claude에게 가는 조각에 없다"
    assert "DOC-05:2.2" in got, f"{q!r}: 작업 후 3단계(DOC-05 §2.2)가 빠졌다"


def test_what_was_broken_is_really_broken_without_expansion():
    """기준선: 확장을 끄면 변형 10개 중 8개에서 §2.1이 상위 8개에 없다 (수정 계획서 3-2와 같다). 동사형 표현은 10개 중 6개에서 부모 §2도 상위 8개 밖이다."""
    missing = [q for q in LOCK_VARIANTS if "DOC-05:2.1" not in ids(search(q, 8))]
    assert len(missing) >= 3     # 2026-10-18 문서 제목 보강("2.1 작업 전 6단계 (잠금·표지를 거는 순서)") 전에는 8개였다. 제목만으로 4개가 나아졌지만 확장은 여전히 필요하다
    no_parent = [q for q in LOCK_VARIANTS_VERB if "DOC-05:2" not in ids(search(q, 8))]
    assert len(no_parent) == 6                                           # 아래 절 확장만으로는 못 고친다 → 잠금 낱말 보장이 필요한 까닭


# ------------------------------------------------------------------ ③ 끄면 지금과 같다
def test_off_is_identical_to_plain_retrieval_for_all_dev_questions(monkeypatch):
    monkeypatch.setenv("PURE_EXPAND", "0")
    s = settings()
    qs = dev_questions() + LOCK_VARIANTS
    assert len(qs) >= 90
    for q in qs:
        assert PURE.context(q, s.pure_topk, s) == PURE.retrieve(q, s.pure_topk), q


# ------------------------------------------------------------------ ④ 켜도 원래 조각은 그대로, 더해진 것만 점수 0
def test_on_keeps_original_hits_order_and_scores_and_marks_added_ones():
    s = settings()
    for q in dev_questions() + LOCK_VARIANTS:
        base = PURE.retrieve(q, s.pure_topk)
        got = PURE.context(q, s.pure_topk, s)
        base_ids = ids(base)
        kept = [(sc, c) for sc, c in got if c.chunk_id in set(base_ids)]
        assert kept == base, q                                           # 원래 조각: 같은 순서·같은 점수
        added = [(sc, c) for sc, c in got if c.chunk_id not in set(base_ids)]
        assert all(sc == 0.0 for sc, _ in added), q                      # 더해진 조각: 검색 점수가 아니라는 표시
        anchors = [c for _, c in added if c.chunk_id == "DOC-05:2"]       # 잠금 낱말이 있어 보장한 부모 조각 (아래 절 상한과 따로 센다)
        kids = [c for _, c in added if c.chunk_id != "DOC-05:2"]
        assert len(anchors) <= 1, q
        assert len(kids) <= PURE.EXPAND_MAX_CHUNKS and sum(len(c.text) for c in kids) <= PURE.EXPAND_MAX_CHARS, q


def test_added_chunks_follow_their_parent_in_document_order():
    s = settings()
    got = ids(PURE.context("잠금 표지 순서", s.pure_topk, s))
    i = got.index("DOC-05:2")
    nxt = got[i + 1:i + 3]
    assert nxt and all(x.startswith("DOC-05:2.") for x in nxt)           # 부모 바로 뒤에 아래 절
    assert len(got) == len(set(got))


# ------------------------------------------------------------------ ⑤ 어떤 조각이 부모여도 상한과 직계 규칙을 지킨다
def test_expand_respects_caps_direct_children_and_no_duplicates_for_every_chunk():
    corpus = load_corpus()
    assert len(corpus) > 100
    for parent in corpus:
        out = PURE.expand([(7.0, parent)])
        assert out[0] == (7.0, parent), parent.chunk_id                  # 부모가 맨 앞, 점수 그대로
        added = [c for _, c in out[1:]]
        assert len(added) <= PURE.EXPAND_MAX_CHUNKS, parent.chunk_id
        assert sum(len(c.text) for c in added) <= PURE.EXPAND_MAX_CHARS, parent.chunk_id
        assert len({c.chunk_id for _, c in out}) == len(out), parent.chunk_id
        for c in added:
            assert c.doc_id == parent.doc_id and c.section.startswith(parent.section + "."), (parent.chunk_id, c.chunk_id)
            assert "." not in c.section[len(parent.section) + 1:], (parent.chunk_id, c.chunk_id)   # 손자 절은 안 더한다
        if not any(x.doc_id == parent.doc_id and x.section.startswith(parent.section + ".") for x in corpus):
            assert added == [], parent.chunk_id                          # 아래 절이 없으면 아무것도 안 더한다


def test_expand_skips_children_already_present_and_takes_short_ones_first():
    corpus = {c.chunk_id: c for c in load_corpus()}
    parent, c21, c22 = corpus["DOC-05:2"], corpus["DOC-05:2.1"], corpus["DOC-05:2.2"]
    out = PURE.expand([(9.0, parent), (5.0, c22)])
    got = ids(out)
    assert got.count("DOC-05:2.2") == 1                                   # 이미 있는 조각은 건너뜀
    assert "DOC-05:2.1" in got
    kids = [corpus[k] for k in ("DOC-05:2.1", "DOC-05:2.3", "DOC-05:2.4") if k in corpus]
    first = min(kids, key=lambda c: len(c.text))
    assert first.chunk_id in got                                          # 가장 짧은 아래 절은 반드시 들어간다
    assert c21.chunk_id in got


# ------------------------------------------------------------------ ⑥ 끝에서 끝: Claude에게 보내는 글
class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        self.calls.append({"props": tuple(sorted((sch.get("properties") or {}).keys())), "user": stdin_text})
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}},
               "structured_output": {"answer": "답이에요.", "cited": ["C1"], "insufficient": False}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


@pytest.fixture
def e2e(monkeypatch):
    get_state().reset()
    AS.clear()
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)

    def no_local(req):
        raise httpx.ConnectError("시험: 로컬 서버 없음")
    C.use_transport(httpx.MockTransport(no_local))
    r = Runner()
    CC.use_runner(r)
    yield r
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def sent_chunk_heads(runner) -> list[str]:
    calls = [c for c in runner.calls if c["props"] == ("answer", "cited", "insufficient")]
    assert len(calls) == 1
    return re.findall(r"^\[C\d+\] (.+)$", calls[0]["user"], re.M)


def ask(q):
    return client.post("/api/assistant/chat", json={"question": q, "llm": "claude"}, headers={"X-Role": "SUP"})


def test_end_to_end_the_prompt_now_contains_the_pre_work_steps(e2e):
    r = ask("잠금 표지 순서가 어떻게 돼?")
    assert r.status_code == 200
    heads = sent_chunk_heads(e2e)
    assert any("DOC-05" in h and "§2.1" in h for h in heads), heads
    assert any("해당 설비의 §3 표를 연다" in c["user"] for c in e2e.calls)       # 6.1 단계 글이 실제로 간다
    assert len(heads) <= 8 + PURE.EXPAND_MAX_CHUNKS


def test_end_to_end_off_sends_exactly_the_old_top_eight(e2e, monkeypatch):
    monkeypatch.setenv("PURE_EXPAND", "0")
    ask("잠금 표지 순서가 어떻게 돼?")
    heads = sent_chunk_heads(e2e)
    assert len(heads) == 8 and not any("§2.1" in h and "DOC-05" in h for h in heads)     # 지금(결함 있는) 모양 그대로


# ------------------------------------------------------------------ ⑦ 잠금 낱말 보장 (둘째 원인)
def has_lock_term(q: str) -> bool:
    return any(w in q.lower() for w in PURE.LOCK_TERMS)


def test_guarantee_anchor_exists_in_the_corpus_and_its_children_hold_the_before_and_after_steps():
    """절 번호를 코드에 박았으므로, 문서가 바뀌면 여기서 알려 준다."""
    corpus = load_corpus()
    for terms, doc_id, section in PURE.GUARANTEED:
        anchor = [c for c in corpus if c.doc_id == doc_id and c.section == section]
        assert len(anchor) == 1, (doc_id, section)
        kids = {c.title for c in PURE._children(anchor[0], corpus)}
        assert any(k.startswith("작업 전 6단계") for k in kids) and any(k.startswith("작업 후 3단계") for k in kids), kids   # 제목 뒤에 현장 말 병기가 붙어도(2026-10-18) 같은 절이다


def test_questions_without_lock_terms_are_untouched_by_the_guarantee():
    qs = [q for q in dev_questions() if not has_lock_term(q)]
    assert len(qs) > 70
    for q in qs:
        hits = PURE.retrieve(q, 8)
        assert PURE.guarantee(q, hits) == (hits, set()), q                # 목록 그대로, 우선 확장 대상 없음


def test_guarantee_puts_the_anchor_first_once_and_only_when_missing():
    hits = PURE.retrieve("작업 전에 잠그는 순서 알려줘", 8)
    assert "DOC-05:2" not in ids(hits)                                    # 결함: 부모조차 상위 8개 밖
    out, first = PURE.guarantee("작업 전에 잠그는 순서 알려줘", hits)
    assert first == {"DOC-05:2"} and ids(out)[0] == "DOC-05:2" and out[0][0] == 0.0 and out[1:] == hits
    hits2 = PURE.retrieve("잠금 표지 순서", 8)                            # 이미 상위에 있으면 더하지 않는다(우선 확장 표시만)
    assert "DOC-05:2" in ids(hits2)
    out2, first2 = PURE.guarantee("잠금 표지 순서", hits2)
    assert out2 == hits2 and first2 == {"DOC-05:2"}


def test_priority_parents_expand_before_higher_ranked_ones_use_up_the_budget():
    corpus = load_corpus()
    kids_of = lambda p: PURE._children(p, corpus)
    big = max(corpus, key=lambda c: len(kids_of(c)))                      # 아래 절이 가장 많은 조각
    sec2 = next(c for c in corpus if c.chunk_id == "DOC-05:2")
    hits = [(9.0, big), (5.0, sec2)]
    with_first = ids(PURE.expand(hits, first={"DOC-05:2"}))
    assert "DOC-05:2.1" in with_first and "DOC-05:2.2" in with_first       # 우선 부모는 예산을 먼저 쓴다
    assert len(with_first) - 2 <= PURE.EXPAND_MAX_CHUNKS


def test_end_to_end_verb_phrasing_reaches_claude_with_the_pre_work_steps(e2e):
    r = ask("작업 전에 잠그는 순서 알려줘")
    assert r.status_code == 200
    heads = sent_chunk_heads(e2e)
    assert any("DOC-05" in h and "§2.1" in h for h in heads), heads
    assert any("해당 설비의 §3 표를 연다" in c["user"] for c in e2e.calls)


def test_end_to_end_verb_phrasing_off_is_the_old_defective_context(e2e, monkeypatch):
    monkeypatch.setenv("PURE_EXPAND", "0")
    # 2026-10-18 DOC-05 Rev.3: §2.1 "우리 라인" 칸이 길어져(원문 뜻 핵심 보강) "작업 전에 잠그는 순서 알려줘"는 확장 없이도 §2.1이 상위 8개에 든다(좋아진 것).
    # 옛 결함을 보여 주는 대조군은 아직 §2.1이 상위 8개 밖인 "잠그는 순서"로 바꿨다
    ask("잠그는 순서")
    heads = sent_chunk_heads(e2e)
    assert len(heads) == 8 and not any("DOC-05" in h and "§2.1" in h for h in heads)


# ------------------------------------------------------------------ ⑧ 안전망: e2e_check.py가 같은 실패를 다음에는 잡는다
def _e2e_module():
    spec = importlib.util.spec_from_file_location("e2e_check_for_test", HERE / ".." / ".." / "e2e_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEFECT_SENTENCES = ["잠금·표지의 전체 단계 순서는 가져온 문서에 없고, 작업별 순서와 기본 규칙만 있어요.",
                    "잠금·표지 전체 단계(6.1~7.3)의 내용은 문서에 없어요.",
                    "작업 전에 잠그는 단계별 순서는 문서에 없어요",
                    "잠금·표지를 거는 앞쪽 단계는 문서에 없고, 작업이 끝난 뒤 푸는 3단계만 있어요.",
                    "모든 설비에 공통인 잠금·표지 단계별 순서는 가지고 있는 문서에 없고, 작업별 순서만 나와 있어요",
                    "일반 설비 전체의 잠금 세부 단계(6.1~7.3)는 이번 문서에 내용이 없어요."]
CORRECT_SENTENCES = ["시험·조정 때문에 잠깐 전원을 넣어야 할 때의 다섯 단계는 문서에 내용이 없어요.",
                     "시험·조정 때문에 잠깐 전원을 넣는 경우의 단계 내용은 문서에는 없어요.",
                     "작업 전 6단계: 1. 해당 설비의 차단 지점과 저장 에너지 표를 열어 작업지시서와 맞는지 보고",
                     "잠금·표지는 작업 전에 여섯 단계로 걸고 작업 후에 세 단계로 푸는데"]


def test_e2e_lock_questions_now_have_a_never_pattern_that_separates_defect_from_correct_answers():
    E = _e2e_module()
    lock = [q for q in E.QUESTIONS if "잠" in q[1]]
    assert len(lock) == 2 and all(q[4] == E.LOCK_NEVER for q in lock)         # 이전에는 never=None이라 틀린 답도 통과했다
    for s in DEFECT_SENTENCES:
        assert re.search(E.LOCK_NEVER, s), s
    for s in CORRECT_SENTENCES:
        assert not re.search(E.LOCK_NEVER, s), s

