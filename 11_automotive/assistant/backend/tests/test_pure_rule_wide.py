"""PURE_RULE_WIDE (2026-10-18, 기획 규칙질문_라우팅_넓히기): 규칙 낱말이 없는 규칙 질문도 문서 길로 보낸다 — 대신 **조회 말투**를 데이터 질문으로 거른다.

`PURE_RULE`은 규칙을 묻는 낱말 목록(RULE_MARK_RE)에 걸린 질문만 문서 길로 보내 재현율이 낮았다(독립 은행 35%, 조정용 은행의 대상 구역 44%).
규칙 질문의 말투는 다양한 반면("~는 반장이 해?", "~이야, 아니면 ~야?", "~인가요?") 운영 조회의 말투는 좁다(몇 개·있어?·알려줘·목록·모자란·중에 …).
그래서 양성 표지를 풀고 음성 표지(데이터 거름)를 강화한다. 틀려도 문서 길이 "문서에 없음"이면 원래 기존 길로 되돌아온다(PURE_RULE과 같은 장치).
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
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS, cfg as _cfg

HERE = Path(__file__).resolve().parent
client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"


@pytest.fixture(autouse=True)
def parser_flags(monkeypatch):
    """conftest는 파서 보강 스위치(PARSE_V*)를 0으로 고정한다. 규칙 질문 판정은 실제 실행과 같은 파서 위에서 봐야 하므로 이 파일의 모든 시험에 권장 파서 스위치를 먼저 깐다."""
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)


def cfg(monkeypatch, wide="1", rule="0", **kw) -> Settings:
    monkeypatch.setenv("PURE_RULE_WIDE", wide)
    monkeypatch.setenv("PURE_RULE", rule)
    return _cfg(monkeypatch, **kw)


# 양성: 규칙 낱말(누가·기준이 뭐야·수 있어? …)이 없는 문서 규칙 질문 — PURE_RULE만 켜면 기존 길로 가던 모양
WIDE_POSITIVE = [
    "출하 로트 확정은 반장이 해?", "재고 입고는 사람이 직접 입력해?", "새 로트 첫 물건은 초품 검사야?", "로트 폐기 승인은 반장이야, 관리자야?",
    "세척액 같은 건 소모품 재고 품목인가요?", "공구 교체하면 공구 재고에서 몇 개 빠져?", "Cpk 측정값 모자라면 로트에 뭐라고 떠?",
    "완제품 재고에도 안전 재고 알림이 있나요?", "그리스는 재고에서 그램으로 빠져?", "절삭유 보충하면 원액 재고에서 얼마가 빠져?",
    "측정 중에 온도 기울기 알람 뜨면 로트 측정 계속해도 돼?",
]
# 음성: 조회 말투 — 규칙 낱말이 없어도 데이터 질문이다 (개수·존재 확인·알려줘·부분 집합·부족/초과 상태·괜찮은지·어느 것·나간 거)
WIDE_OPS = [
    "보류 걸린 로트 몇 개예요?", "검사 강화 걸린 로트 있나요?", "소모품 재고 알려줘", "정비 소모품 중에 재고 모자란 것만 뽑아주세요",
    "정비 기한 지난 항목 담당이 누구야?", "공구 재고 부족 알림 나간 거 있어?", "주축 윤활유 재고는 괜찮은가요?",
    "합격 판정이 난 로트 중에 아직 출하 안 된 건 몇 개야?", "안 돌고 있는 설비 있어? 가동 멈춘 거 말이야.", "로트 정해진 개수 채웠어?",
    "절삭유 필터 재고 몇 개야?", "홀드 걸린 로트 몇 개예요?", "수명 90% 넘어서 교체 알림 뜬 공구 있어?", "승인 받아야 하는 로트 알려줘",
    "원자재 로트 중에 입고 검사 통과한 게 어느 거야?", "재고가 제일 많은 소모품이 뭐예요?",
]


def wide(q, monkeypatch=None):
    return PURE.rule_question_wide(q, A.parse(q))


@pytest.mark.parametrize("q", WIDE_POSITIVE, ids=[f"P{i}" for i in range(len(WIDE_POSITIVE))])
def test_rule_questions_without_a_rule_word_are_detected(q):
    assert wide(q)


@pytest.mark.parametrize("q", WIDE_OPS, ids=[f"O{i}" for i in range(len(WIDE_OPS))])
def test_lookup_phrasing_is_data_even_without_a_rule_word(q):
    assert not wide(q)


def test_most_of_the_positives_were_missed_by_the_narrow_rule():
    """넓히는 까닭: 좁은 규칙(PURE_RULE)은 이 질문 대부분을 놓친다 (놓치지 않는 질문이 있어도 넓은 규칙은 그것을 포함한다)."""
    missed = [q for q in WIDE_POSITIVE if not PURE.rule_question(q, A.parse(q))]
    assert len(missed) >= 8, missed


def test_the_wide_rule_includes_everything_the_narrow_rule_accepts():
    bank = json.loads((HERE / "route_bank_cases.json").read_text(encoding="utf-8"))
    lost = [q for q in bank["rule"] if PURE.rule_question(q, A.parse(q)) and not wide(q)]
    assert lost == [], lost


@pytest.mark.parametrize("extra", ["LOT-2609-041-1", "어제", "VF2-01", "2075 알람", "9월 15일"])
def test_a_number_date_equipment_or_alarm_always_keeps_the_old_path(extra):
    for q in WIDE_POSITIVE[:4]:
        assert not wide(f"{extra} {q}")


def test_short_questions_and_questions_about_now_are_lookups():
    for q in ("재고 왜 이래?", "재고 가져가도 돼?", "지금 재고 입고는 사람이 직접 입력해?", "현재 로트 확정은 반장이 해?", "이 로트 폐기 승인은 반장이야?"):
        assert not wide(q), q


def test_no_signal_means_not_applicable():
    for q in ("사내 체육대회 언제야?", "회식은 어디서 해?", "VF-2 주축 모터 정격 전류는 몇 A야?"):
        assert not wide(q)


def test_a_rule_feature_question_is_not_a_lookup_even_though_it_asks_whether_something_exists():
    """"있나요?"는 존재 확인(데이터)이지만 알림·기능·기준이 있는지 묻는 말은 규칙 질문이다."""
    assert wide("완제품 재고에도 안전 재고 알림이 있나요?")
    assert not wide("안전 재고 밑으로 내려간 소모품 있나요?")


def test_during_is_not_a_subset():
    """"측정 중에"(하는 동안)는 "로트 중에"(부분 집합)와 다르다."""
    assert wide("측정 중에 온도 기울기 알람 뜨면 로트 측정 계속해도 돼?")
    assert not wide("검사 대기 로트 중에 보류 걸린 게 있어?")


def test_conditional_shortage_is_a_rule_but_a_shortage_state_is_data():
    assert wide("Cpk 측정값 모자라면 로트에 뭐라고 떠?")
    assert not wide("재고 모자란 소모품 알려줘")


# ------------------------------------------------------------------ 독립 질문 은행 회귀 (조정용 은행 — 조정에 쓴 것이라 증거가 아니라 회귀 방어용)
BANK = json.loads((HERE / "rule_wide_bank_cases.json").read_text(encoding="utf-8"))


def test_bank_every_operational_question_stays_out_of_the_document_route():
    flipped = [q for q in BANK["ops"] if wide(q)]
    assert flipped == [], flipped


def test_bank_every_old_operational_question_stays_out_of_the_document_route():
    old = json.loads((HERE / "route_bank_cases.json").read_text(encoding="utf-8"))
    flipped = [q for q in old["ops"] if wide(q)]
    assert flipped == [], flipped


def test_bank_rule_questions_that_were_rescued_stay_rescued():
    lost = [q for q in BANK["rule"] if not wide(q)]
    assert lost == [] and len(BANK["rule"]) >= 30


# ------------------------------------------------------------------ 스위치와 pure_scope_v19
def test_default_is_off_in_code_flags_and_conftest(monkeypatch):
    assert Settings.__dataclass_fields__["pure_rule_wide"].default is False
    monkeypatch.delenv("PURE_RULE_WIDE", raising=False)
    assert settings().pure_rule_wide is False
    for v in ("", "0", "no", "xx"):
        monkeypatch.setenv("PURE_RULE_WIDE", v)
        assert settings().pure_rule_wide is False
    monkeypatch.setenv("PURE_RULE_WIDE", "1")
    assert settings().pure_rule_wide is True and settings().flags()["pure_rule_wide"] is True


def test_conftest_pins_it_off_so_a_developer_env_cannot_change_other_tests():
    assert os.environ["PURE_RULE_WIDE"] == "0"


def test_example_file_turns_it_on_with_a_comment_line_above_and_no_inline_comment():
    lines = (HERE / ".." / ".." / ".env.example").read_text(encoding="utf-8").splitlines()
    i = lines.index("PURE_RULE_WIDE=1")
    assert lines[i - 1].startswith("#") and "규칙" in lines[i - 1]


@pytest.mark.parametrize("q", WIDE_POSITIVE, ids=[f"P{i}" for i in range(len(WIDE_POSITIVE))])
def test_on_sends_these_to_the_pure_path_and_off_keeps_the_old_path(monkeypatch, q):
    s_on = cfg(monkeypatch)
    p = A.parse(q)
    assert A.pure_scope_v19(p, s_on, q) == PURE.RULE_WHY
    assert A.pure_scope_v19(p, cfg(monkeypatch, wide="0"), q) is None


def test_wide_works_without_the_narrow_switch_and_the_narrow_one_is_unchanged(monkeypatch):
    q = "출하 로트 확정은 반장이 해?"
    assert A.pure_scope_v19(A.parse(q), cfg(monkeypatch, wide="1", rule="0"), q) == PURE.RULE_WHY
    narrow_only = cfg(monkeypatch, wide="0", rule="1")
    assert A.pure_scope_v19(A.parse(q), narrow_only, q) is None            # 좁은 규칙만 켜면 이 질문은 여전히 기존 길
    q2 = "정비에 쓰는 소모품 재고는 누가 관리해?"
    assert A.pure_scope_v19(A.parse(q2), narrow_only, q2) == PURE.RULE_WHY


def test_on_changes_the_route_only_for_rule_questions(monkeypatch):
    """켜도 규칙 질문이 아닌 질문(운영·알람·설비·날짜·개발용 문서 질문)의 길은 하나도 안 바뀐다."""
    qs = list(WIDE_OPS) + list(BANK["ops"]) + ["VF2-01 지금 상태 어때?", "2075 알람 어떻게 해?", "어제 야간에 몇 번 멈췄어?", "SAW-01 정비 전에 어디를 차단해?", "톱 정비 전에 뭘 잠가?"]
    for name in ("qa_set.json", "qa_tune_f.json"):
        qs += [it["q"] for it in json.loads((HERE / ".." / "eval" / name).read_text(encoding="utf-8"))["items"]]
    s_on, s_off = cfg(monkeypatch), cfg(monkeypatch, wide="0")
    for q in qs:
        p = A.parse(q)
        on, off = A.pure_scope_v19(p, s_on, q), A.pure_scope_v19(p, s_off, q)
        if on != off:
            assert on == PURE.RULE_WHY and off is None and PURE.rule_question_wide(q, p), q


def test_keep_signals_off_is_unaffected(monkeypatch):
    s = cfg(monkeypatch, keep="0")
    for q in WIDE_POSITIVE[:5]:
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


class FailRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout="", stderr="시험: 호출 실패")


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


def _fixture(make):
    @pytest.fixture
    def f(monkeypatch):
        r = make()
        _setup(monkeypatch, r)
        yield r
        CC.use_runner(None)
        C.use_transport(None)
        AS.clear()
        get_state().reset()
    return f


e2e = _fixture(Runner)
e2e_unsure = _fixture(lambda: Runner(insufficient=True))
e2e_fail = _fixture(FailRunner)


def ask(q):
    return client.post("/api/assistant/chat", json={"question": q, "llm": "claude"}, headers={"X-Role": "SUP"})


def pure_calls(runner):
    return [c for c in runner.calls if c.get("props") == ("answer", "cited", "insufficient")]


Q = "재고 입고는 사람이 직접 입력해?"          # 규칙 낱말 없는 규칙 질문 (끝에서 끝 시험은 문서 제목 병기와 무관한 말을 쓴다)


def test_end_to_end_on_answers_it_from_the_documents(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE_WIDE", "1")
    r = ask(Q).json()
    assert len(pure_calls(e2e)) == 1
    assert r["status"] == "답변" and r["conclusion"] == "문서 답이에요."
    assert "순수 외부 LLM" in (r.get("route") or {}).get("source", "")


def test_end_to_end_off_keeps_the_old_path_for_the_same_question(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE_WIDE", "0")
    r = ask(Q).json()
    assert len(pure_calls(e2e)) == 0
    assert r["conclusion"] != "문서 답이에요."


def test_when_the_document_path_finds_nothing_the_answer_is_exactly_the_old_one(e2e_unsure, monkeypatch):
    """되돌리기: 문서 길이 "문서에 없음"이면 끈 것과 같은 답(상태·본문)이 나온다. 늘어나는 것은 Claude 호출 1회뿐."""
    monkeypatch.setenv("PURE_RULE_WIDE", "0")
    off = ask(Q).json()
    n_off = len(pure_calls(e2e_unsure))
    AS.clear()
    monkeypatch.setenv("PURE_RULE_WIDE", "1")
    on = ask(Q).json()
    assert len(pure_calls(e2e_unsure)) == n_off + 1
    assert (on["status"], on["conclusion"]) == (off["status"], off["conclusion"])
    assert on.get("route") == off.get("route") and on["status"] != "문서에 없음"


def test_operational_questions_never_call_claude_for_routing_when_on(e2e, monkeypatch):
    monkeypatch.setenv("PURE_RULE_WIDE", "1")
    for q in ("보류 걸린 로트 몇 개예요?", "소모품 재고 알려줘", "VF2-01 지금 상태 어때?", "2075 알람 어떻게 해?"):
        ask(q)
    assert len(pure_calls(e2e)) == 0


def test_the_wide_route_prompt_carries_the_operations_note(e2e, monkeypatch):
    """이 경로는 PURE_RULE과 같은 지시문 한 줄(운영 기록을 묻는 것이면 insufficient)을 단다 — 잘못 보낸 조회가 문서 답으로 끝나지 않게."""
    monkeypatch.setenv("PURE_RULE_WIDE", "1")
    ask(Q)
    assert PURE.RULE_OPS_NOTE in pure_calls(e2e)[0]["system"]


def test_when_the_claude_call_fails_it_is_answered_by_the_old_path(e2e_fail, monkeypatch):
    monkeypatch.setenv("PURE_RULE_WIDE", "1")
    on = ask(Q)
    monkeypatch.setenv("PURE_RULE_WIDE", "0")
    AS.clear()
    off = ask(Q)
    assert on.status_code == off.status_code == 200
    assert on.json()["conclusion"] == off.json()["conclusion"]
