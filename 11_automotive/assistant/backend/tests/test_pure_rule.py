"""문서 질문 라우팅(PURE_RULE) 시험 (2026-10-18). 기획: 261003_창민/문서질문_라우팅_기획_20261018.md

"소모품 재고는 누가 관리해?"·"홀드 걸린 로트도 내보낼 수 있어?"처럼 운영 낱말(로트·재고·정비 기한·알림)이 든 **규칙 질문**이 기존 길(운영 조회)로 가서
문서 답을 못 받던 문제(DOC-06 기존 길 10개 중 문서 답 2개, DOC-04 11개 중 5개). 신호가 운영 낱말(intents)뿐이고 지금 상태를 묻는 말이 없고 규칙 낱말이 있으면
문서 길로 보내고, 문서 길이 "문서에 없음"이면 원래 기존 길로 되돌린다. 스위치 PURE_RULE(코드 기본 꺼짐).
이 시험은 적중률 숫자를 박지 않는다 — 판정·번호/설비/날짜/알람이 있으면 절대 안 바뀜·끄면 동일·되돌리기만 본다.
"""
from __future__ import annotations

import json
import os
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
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS, cfg as _cfg

HERE = Path(__file__).resolve().parent
client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"


def cfg(monkeypatch, rule="1", **kw) -> Settings:
    monkeypatch.setenv("PURE_RULE", rule)
    return _cfg(monkeypatch, **kw)


# 양성: 측정(2026-10-18)에서 기존 길로 가서 문서 답을 못 받던 규칙 질문 21개 (DOC-06 10 + DOC-04 11)
POSITIVE = [
    "긴 정지 뒤에 다시 돌릴 때는 어떤 방식으로 검사해?", "첫 물건은 누가 재고 누가 확인해?", "공구 마모가 원인이면 다음 몇 로트까지 더 꼼꼼히 봐?",
    "36개 로트를 평소 방식으로 재면 합쳐서 몇 분이야?", "로트가 가질 수 있는 상태가 뭐뭐 있어?", "의심 가는 로트는 누가 골라서 알려 줘?",
    "문제 난 로트랑 같은 설비·같은 교대에서 나온 다른 로트도 확인해야 해?", "홀드 걸린 로트도 내보낼 수 있어?", "여러 로트가 쌓여 있으면 어느 것부터 내보내?",
    "완제품 재고가 모자랄 때 알려 주는 기능이 있어?",
    "예방 정비 제때 실시율 목표가 얼마야?", "정비에 쓰는 소모품 재고는 누가 관리해?", "정비 소모품 안전 재고는 누가 정해?", "소모품 재고 실사는 얼마마다 해?",
    "그리스 안전 재고는 몇 개야?", "그리스는 재고에서 어떻게 빼?", "세척액은 왜 재고 품목이 아니야?", "톱 가이드 레일 오일은 재고로 관리해?",
    "머시닝센터 윤활유는 재고에 들어가?", "정비 기한이 지나면 알림이 가?", "예방 정비 항목 코드는 어떤 모양이야?",
]
# 음성: 지금·과거의 실제 데이터를 묻는 질문 — 문서 길로 가면 안 된다 (신호는 운영 낱말뿐)
OPS = [
    "재고 부족한 거 있어?", "지금 재고 얼마나 남았어?", "그리스 재고 몇 개 남았어?", "기한 넘긴 정비 있어?", "지금 보류된 로트 있어?", "이번 주 불량 몇 건이야?",
    "보류된 로트 몇 개야?", "누가 이 로트 검사했어?", "누가 어제 점검했어?", "오늘 점검해야 할 정비 알려줘", "최근 출하한 로트 목록 보여줘", "이번 교대 로트 몇 개 만들었어?",
    "안전 재고 미만인 소모품 알려줘", "정비 기한 지난 항목 목록", "알림 온 거 있어?", "공구 수명 얼마나 남았어?", "지금 검사 대기 로트 있어?", "합격한 로트 수 알려줘",
    "폐기된 로트가 있었어?", "소모품 재고 현황", "입고된 원자재 로트 이력", "로트 지연된 거 있어?", "정비 알림 왜 안 왔어?", "방금 보류된 로트 뭐야?",
]


@pytest.mark.parametrize("q", POSITIVE, ids=[f"P{i}" for i in range(len(POSITIVE))])
def test_rule_questions_with_only_operation_words_are_detected(monkeypatch, q):
    cfg(monkeypatch)                                      # 규칙 해석(parse)이 PARSE_V* 스위치를 읽으므로 먼저 켠다
    p = A.parse(q)
    assert p.get("intents") and not (p.get("alarms") or p.get("equipment") or p.get("start") or p.get("lot") or p.get("order")), p   # 신호는 운영 낱말뿐
    assert PURE.rule_question(q, p), q


@pytest.mark.parametrize("q", OPS, ids=[f"O{i}" for i in range(len(OPS))])
def test_questions_about_current_or_past_data_are_not_rule_questions(monkeypatch, q):
    cfg(monkeypatch)
    assert not PURE.rule_question(q, A.parse(q)), q


@pytest.mark.parametrize("extra", ["LOT-2609-041-1", "어제", "VF2-01", "2075 알람", "9월 15일"])
def test_a_number_date_equipment_or_alarm_always_keeps_the_old_path(monkeypatch, extra):
    """번호·날짜·설비 이름·알람이 있으면 규칙 낱말이 있어도 진짜 조회일 가능성이 높아 그대로 기존 길."""
    cfg(monkeypatch)
    for q in POSITIVE:
        qq = f"{extra} {q}"
        assert not PURE.rule_question(qq, A.parse(qq)), qq


def test_no_signal_means_not_applicable(monkeypatch):
    cfg(monkeypatch)
    q = "사내 체육대회 누가 정해?"
    assert not PURE.rule_question(q, A.parse(q))          # 신호가 없으면 이미 순수 길이라 이 함수의 일이 아니다


# ------------------------------------------------------------------ 독립 질문 은행 회귀 (분류 코드를 안 보고 쓴 질문)
BANK = json.loads((HERE / "route_bank_cases.json").read_text(encoding="utf-8"))


def test_bank_every_operational_question_stays_out_of_the_document_route(monkeypatch):
    """운영 조회 질문 90개(독립 은행 1번째 판): 하나도 규칙 질문으로 읽히면 안 된다 (정밀도 우선 — 잘못 보내면 해롭다)."""
    cfg(monkeypatch)
    flipped = [q for q in BANK["ops"] if PURE.rule_question(q, A.parse(q))]
    assert flipped == [], flipped


def test_bank_rule_questions_that_were_rescued_stay_rescued(monkeypatch):
    cfg(monkeypatch)
    lost = [q for q in BANK["rule"] if not PURE.rule_question(q, A.parse(q))]
    assert lost == [] and len(BANK["rule"]) >= 10


# ------------------------------------------------------------------ 스위치와 pure_scope_v19
def test_default_is_off_in_code_flags_and_conftest(monkeypatch):
    assert Settings.__dataclass_fields__["pure_rule"].default is False
    monkeypatch.delenv("PURE_RULE", raising=False)
    assert settings().pure_rule is False
    for v in ("", "0", "no", "xx"):
        monkeypatch.setenv("PURE_RULE", v)
        assert settings().pure_rule is False
    monkeypatch.setenv("PURE_RULE", "1")
    assert settings().pure_rule is True and settings().flags()["pure_rule"] is True


def test_conftest_pins_it_off_so_a_developer_env_cannot_change_other_tests():
    assert os.environ["PURE_RULE"] == "0"


def test_example_file_turns_it_on_with_a_comment_line_above_and_no_inline_comment():
    lines = (HERE / ".." / ".." / ".env.example").read_text(encoding="utf-8").splitlines()
    i = lines.index("PURE_RULE=1")
    assert lines[i - 1].startswith("#") and "규칙" in lines[i - 1]


@pytest.mark.parametrize("q", POSITIVE, ids=[f"P{i}" for i in range(len(POSITIVE))])
def test_on_sends_rule_questions_to_the_pure_path_and_off_keeps_the_old_path(monkeypatch, q):
    s_on = cfg(monkeypatch)
    p = A.parse(q)
    assert A.pure_scope_v19(p, s_on, q) == PURE.RULE_WHY
    assert A.pure_scope_v19(p, cfg(monkeypatch, rule="0"), q) is None


def test_on_changes_the_route_only_for_rule_questions(monkeypatch):
    """켜도 규칙 질문이 아닌 질문(운영·알람·설비·날짜·개발용 문서 질문)의 길은 하나도 안 바뀐다."""
    qs = list(OPS) + list(POSITIVE) + ["VF2-01 지금 상태 어때?", "2075 알람 어떻게 해?", "어제 야간에 몇 번 멈췄어?", "SAW-01 정비 전에 어디를 차단해?", "톱 정비 전에 어디를 차단해야 해?"]
    for name in ("qa_set.json", "qa_tune_f.json"):
        qs += [it["q"] for it in json.loads((HERE / ".." / "eval" / name).read_text(encoding="utf-8"))["items"]]
    s_on, s_off = cfg(monkeypatch), cfg(monkeypatch, rule="0")
    for q in qs:
        p = A.parse(q)
        on, off = A.pure_scope_v19(p, s_on, q), A.pure_scope_v19(p, s_off, q)
        if on != off:
            assert on == PURE.RULE_WHY and off is None and PURE.rule_question(q, p), q


def test_keep_signals_off_is_unaffected(monkeypatch):
    s = cfg(monkeypatch, keep="0")
    for q in POSITIVE[:5]:
        assert A.pure_scope_v19(A.parse(q), s, q) != PURE.RULE_WHY                    # 이미 전부 순수 길


# ------------------------------------------------------------------ 끝에서 끝 (가짜 Claude 실행기)
class Runner:
    def __init__(self, insufficient=False):
        self.calls, self.insufficient = [], insufficient

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        system = cmd[cmd.index("--system-prompt") + 1] if "--system-prompt" in cmd else ""
        self.calls.append({"props": tuple(sorted((sch.get("properties") or {}).keys())), "user": stdin_text, "system": system})
        so = ({"answer": "가지고 있는 문서에서 찾지 못했어요.", "cited": [], "insufficient": True} if self.insufficient
              else {"answer": "문서 답이에요.", "cited": ["C1"], "insufficient": False})
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
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")

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


def pure_calls(runner):
    return [c for c in runner.calls if c["props"] == ("answer", "cited", "insufficient")]


# 끝에서 끝 시험의 질문은 문서 제목 병기와 무관한 것을 쓴다: "홀드"는 DOC-06 §4.2 제목에 병기돼(Rev.4, 2026-10-18) 끈 상태의 기존 길에서도 문서 후보가 잡히고,
# 그러면 기존 길이 "줄 고르기"를 시험용 가짜 Claude에게 시켜 스키마가 안 맞아 오류가 난다 (문서 제목이 바뀔 때마다 이 시험이 흔들리지 않게 한다).
def test_end_to_end_on_answers_a_rule_question_from_the_documents(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE", "1")
    r = ask("정비 기한이 지나면 알림이 가?").json()
    assert len(pure_calls(e2e)) == 1                                              # 문서 길로 Claude를 한 번 불렀다
    assert r["status"] == "답변" and r["conclusion"] == "문서 답이에요."
    assert "순수 외부 LLM" in (r.get("route") or {}).get("source", "")


def test_end_to_end_off_keeps_the_old_path_for_the_same_question(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE", "0")
    r = ask("정비 기한이 지나면 알림이 가?").json()
    assert len(pure_calls(e2e)) == 0
    assert r["conclusion"] != "문서 답이에요."


def test_when_the_document_path_finds_nothing_the_answer_is_exactly_the_old_one(e2e_unsure, monkeypatch):
    """되돌리기: 문서 길이 "문서에 없음"이면 끈 것과 같은 답(상태·본문)이 나온다. 늘어나는 것은 Claude 호출 1회뿐."""
    q = "정비 기한이 지나면 알림이 가?"
    monkeypatch.setenv("PURE_RULE", "0")
    off = ask(q).json()
    n_off = len(pure_calls(e2e_unsure))
    AS.clear()
    monkeypatch.setenv("PURE_RULE", "1")
    on = ask(q).json()
    assert len(pure_calls(e2e_unsure)) == n_off + 1                               # 문서 길을 한 번 시도했다
    assert (on["status"], on["conclusion"]) == (off["status"], off["conclusion"])
    assert on.get("route") == off.get("route") and on["status"] != "문서에 없음"       # 되돌려서 원래 기존 길 답


def test_unrelated_questions_that_find_nothing_stay_not_in_docs_when_on(e2e_unsure, monkeypatch):
    monkeypatch.setenv("PURE_RULE", "1")
    r = ask("사내 체육대회 언제야?").json()
    assert r["status"] == "문서에 없음"                                             # 신호 없는 질문은 이미 순수 길 — 되돌리지 않는다


def test_operational_questions_never_call_claude_for_routing_when_on(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE", "1")
    for q in ("재고 부족한 거 있어?", "VF2-01 지금 상태 어때?", "2075 알람 어떻게 해?"):
        ask(q)
    assert len(pure_calls(e2e)) == 0


# ------------------------------------------------------------------ 독립 리뷰(2026-10-18)가 짚은 것: 지시문 한 줄·호출 실패·안전 겹침·짧은 질문
class FailRunner:
    """Claude 호출이 항상 실패한다 (returncode 1)."""
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append(stdin_text)
        return SimpleNamespace(returncode=1, stdout="", stderr="시험: 실패")


@pytest.fixture
def e2e_fail(monkeypatch):
    r = FailRunner()
    _setup(monkeypatch, r)
    yield r
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def test_the_rule_route_prompt_carries_the_operations_note_and_other_routes_do_not(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE", "1")
    ask("정비 기한이 지나면 알림이 가?")
    ask("사내 체육대회 누가 정해?")                                              # 신호가 없는 질문 — 원래 순수 길
    calls = [c for c in e2e.calls if c["props"] == ("answer", "cited", "insufficient")]
    assert len(calls) == 2
    assert PURE.RULE_OPS_NOTE in calls[0]["system"]                               # 규칙 질문 라우팅으로 온 질문: 운영 기록이면 insufficient
    assert PURE.RULE_OPS_NOTE not in calls[1]["system"]                           # 그렇지 않은 순수 길 질문: 지시문이 지금과 같다


def test_ask_adds_the_note_to_the_system_prompt_only_when_asked(monkeypatch):
    s = cfg(monkeypatch)
    seen = []
    monkeypatch.setattr(C, "chat_json", lambda messages, schema, job, max_tokens, st: seen.append(messages[0]["content"]) or {"answer": "x", "cited": [], "insufficient": True})
    chunks = [c for _, c in PURE.retrieve("재고", 2)]
    PURE.ask("재고는 누가 관리해?", chunks, None, s, ops_note=True)
    PURE.ask("재고는 누가 관리해?", chunks, None, s)
    assert PURE.RULE_OPS_NOTE in seen[0] and PURE.RULE_OPS_NOTE not in seen[1]


def test_when_the_claude_call_fails_a_rule_routed_question_is_answered_by_the_old_path(e2e_fail, monkeypatch):
    """PURE_RULE는 규칙 질문일 수도 있다는 추측으로 보낸 호출이다 — 그 호출이 실패해도 예전에 답이 나오던 질문이 오류(503)가 되면 안 된다."""
    q = "정비 기한이 지나면 알림이 가?"
    monkeypatch.setenv("PURE_RULE", "0")
    off = ask(q)
    monkeypatch.setenv("PURE_RULE", "1")
    on = ask(q)
    assert on.status_code == off.status_code == 200
    assert (on.json()["status"], on.json()["conclusion"]) == (off.json()["status"], off.json()["conclusion"])


def test_a_failed_call_on_an_ordinary_document_question_still_ends_as_an_error(e2e_fail, monkeypatch):
    """규칙 질문 라우팅이 아닌 순수 길의 실패는 지금처럼 오류다 (자동으로 다른 길로 돌아가지 않는다는 원칙)."""
    monkeypatch.setenv("PURE_RULE", "1")
    r = ask("사내 체육대회 누가 정해?")
    assert r.status_code == 503


def test_safety_words_in_a_rule_question_do_not_hide_the_fallback(monkeypatch):
    """"안전 재고"의 "안전"이 안전 질문으로 읽혀 "확인 필요 + DOC-05 후보" 안내가 나가면 되돌리기(상태 "문서에 없음")가 안 된다 — 규칙 질문 경로에서는 안전 안내를 건너뛴다."""
    q = "정비 소모품 안전 재고는 누가 정해?"
    s = cfg(monkeypatch, safety="1")
    assert PURE.is_safety(q) and PURE.rule_question(q, A.parse(q))
    monkeypatch.setattr(PURE, "ask", lambda question, chunks, prev, st, ops_note=False: {"answer": "문서에 없음", "insufficient": True, "cited_raw": [], "ms": 1, "sent_chars": 1})
    with EXT.external_request("claude"):
        s = settings()
        as_rule = A._pure_answer_v19(q, A.parse(q), {}, s, {}, None, PURE.RULE_WHY)
        as_pure = A._pure_answer_v19(q, A.parse(q), {}, s, {}, None, "순수 길")
    assert as_rule["status"] == "문서에 없음"                                       # 되돌리기가 알아볼 수 있는 상태
    assert as_pure["status"] == "확인 필요"                                          # 일반 순수 길의 안전 질문은 지금처럼 "자동으로 확인하지 못함"


@pytest.mark.parametrize("q", ["재고 왜 이래?", "재고 가져가도 돼?", "로트 출하 가능해?", "재고 보충해야 돼?", "로트 합격 맞아?", "재고 어떻게 세?"])
def test_terse_questions_are_treated_as_lookups(monkeypatch, q):
    cfg(monkeypatch)
    assert not PURE.rule_question(q, A.parse(q))


@pytest.mark.parametrize("q", ["이 로트 누가 검사했나요?", "누가 이 로트 검사했습니까?", "이 로트 누가 검사했지?", "누가 재고를 가져갔는지 알려줘", "왜 재고가 빠졌어?", "누가 이 로트 끝냈어?", "누가 로트 승인했나요"])
def test_past_tense_in_any_ending_means_it_asks_what_happened(monkeypatch, q):
    cfg(monkeypatch)
    assert not PURE.rule_question(q, A.parse(q))
