"""고장 대응 절차 질문 라우팅(PURE_FAULT) 시험 (2026-10-18). 기획: 261003_창민/고장대응_질문_라우팅_기획_20261018.md

"툴 수명 다 됐다고 뜨는데 예비 날이 없어. 어떻게 해?"·"지멘스 밀이 멈췄어. 내가 다시 돌려도 돼?"처럼 **증상을 말하고 무엇을 해야 하는지** 묻는 질문은
운영 낱말(수명·재고·정지·로트 …)이 있다는 이유로 기존 길(운영 조회)로 가서 엉뚱한 운영 목록을 받았다(DOC-03 점검표 기존 길 15개 중 14개).
스위치 PURE_FAULT=1이면 신호가 운영 낱말(intents)뿐이고, 행동을 묻는 표지가 있고, 데이터를 묻는 말이 없는 질문을 문서 길로 보낸다.
문서에 없으면(또는 호출이 실패하면) 원래 기존 길로 되돌린다. 알람 번호·설비·날짜·로트 번호가 있으면 절대 안 바뀐다. 끄면 PURE_RULE만 있을 때와 같다.
이 시험은 적중률 숫자를 박지 않는다 — 판정 사례·알람/설비/로트/날짜 불변·끄면 동일·되돌리기·재시도만 본다.
"""
from __future__ import annotations

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
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS, cfg as _cfg

HERE = Path(__file__).resolve().parent
client = TestClient(app_module.app)
SONNET = "claude-sonnet-5-5"
PROPS = ("answer", "cited", "insufficient")


def cfg(monkeypatch, fault="1", rule="1", **kw) -> Settings:
    monkeypatch.setenv("PURE_FAULT", fault)
    monkeypatch.setenv("PURE_RULE", rule)
    return _cfg(monkeypatch, **kw)


# 양성: 운영 낱말뿐이고 행동을 묻는 말이 있고 데이터를 묻는 말이 없는 고장 대응 질문 (DOC-03 점검표 기존 길 15개 + 독립 은행에서 본 모양)
POSITIVE = [
    "툴 수명 다 됐다고 뜨는데 대신 쓸 예비 날이 없어. 어떻게 해?",
    "주축 모터 열 올랐다고 정지 알림 떴는데 일단 뭐 해?",
    "이번 로트 돌리다 공구 하중 때문에 멈췄어. 어떻게 풀고 이어서 돌려?",
    "지멘스 밀이 축이 지령보다 뒤처졌다고 멈췄어. 내가 다시 돌려도 돼?",
    "그 기름 부족하다는데 뭘 넣어야 해?",
    "톱 레일 기름 모자라다고 떴어. 기름통이 어디 있어?",
    "재고에서 꺼낸 새 톱날 달 때 고정 볼트는 몇 ft-lbs로 조여?",
    "수리가 아직 안 끝났는데 그 사이에 또 떴어. 재발이라고 알림이 나가?",
    "윤활유 정비 기한을 놓치고 경고도 그냥 두면 뭐가 문제야?",
    "윤활 압력이 안 잡힌다고 정지됐어. 일단 가공 다시 시작해도 되나?",
    "모터 쪽에서 합선 났다고 떠서 정지됐는데, 그냥 리셋 누르고 다시 돌려도 돼요?",
    "출하 날인데 보류 걸린 로트가 남아 있어. 이거 같이 내보내도 되는 거야?",
    "기름 모자라다고 떠서 채웠는데 또 떠. 계속 이래도 정상이야?",
    "톱 윤활유 보충하면 재고에서 자동으로 빠지는 거야?",
    "서브프로그램을 못 찾는다고 떠서 멈췄어. 파일 이름은 어떻게 써야 해?",
    "주축이 너무 뜨거워서 멈췄어요. 팬이 도는지는 어떻게 확인해요?",
]
# 음성: 데이터 조회(현황·목록·개수·남은 양·이력·누가 했나·시각)·특정 대상을 가리키는 말·행동 표지 없음·너무 짧음 — 규칙이 참이면 안 된다 (신호는 운영 낱말뿐)
NEGATIVE = [
    "기름 모자라다고 떴는데 재고 몇 개 남았어?",
    "정지 걸린 설비 어디야?",
    "재고 부족한 오일 뭐 있어?",
    "교체해야 하는 공구 몇 개야?",
    "툴 수명 얼마나 남았어?",
    "공구 수명 현황 알려줘",
    "지난주 정비 이력 보여줘",
    "어제 정지 몇 번 났어?",
    "이 로트 누가 검사했어?",
    "이 재고 써도 되는지 알려줘",
    "어느 로트부터 검사해야 돼?",
    "정비 기한 지난 항목 목록",
    "재고 어떻게 돼?",
    "재고 왜 이래?",
    "윤활유 재고 지금 얼마나 있어?",
    "정지 사유 통계 보여줘",
]
# 신호가 운영 낱말뿐이 아니면(알람 번호·설비·로트 번호·날짜) 행동을 묻는 말이 있어도 절대 안 바뀐다
OTHER_SIGNALS = [
    "알람 2075 떴는데 어떻게 해?",
    "VF2-01 정지 걸렸는데 어떻게 해?",
    "LOT-2609-041-1 보류 걸렸는데 어떻게 해야 돼?",
    "어제 정지 걸렸는데 어떻게 해야 돼?",
    "9월 12일에 공구 수명 다 됐는데 어떻게 해?",
]


@pytest.mark.parametrize("q", POSITIVE, ids=[f"P{i}" for i in range(len(POSITIVE))])
def test_procedure_questions_with_only_operation_words_are_detected(monkeypatch, q):
    cfg(monkeypatch)
    p = A.parse(q)
    assert p.get("intents") and not (p.get("alarms") or p.get("equipment") or p.get("start") or p.get("lot") or p.get("order")), p
    assert PURE.fault_question(q, p), q


@pytest.mark.parametrize("q", NEGATIVE, ids=[f"N{i}" for i in range(len(NEGATIVE))])
def test_data_questions_are_not_detected(monkeypatch, q):
    cfg(monkeypatch)
    assert not PURE.fault_question(q, A.parse(q)), q


@pytest.mark.parametrize("q", OTHER_SIGNALS, ids=[f"S{i}" for i in range(len(OTHER_SIGNALS))])
def test_alarm_number_equipment_lot_and_date_questions_never_change(monkeypatch, q):
    s = cfg(monkeypatch)
    p = A.parse(q)
    assert not PURE.fault_question(q, p)
    assert A.pure_scope_v19(p, s, q) is None                 # 기존 길(알람 카드·운영 조회) 그대로


def test_a_question_with_no_signal_is_not_a_fault_question_it_is_already_the_pure_route(monkeypatch):
    s = cfg(monkeypatch)
    q = "사내 체육대회 누가 정해?"
    assert not PURE.fault_question(q, A.parse(q))
    assert A.pure_scope_v19(A.parse(q), s, q)                # 신호가 없으면 원래 순수 길


# ------------------------------------------------------------------ 범위 판정 (스위치)
def test_scope_gives_the_fault_reason_only_when_the_switch_is_on(monkeypatch):
    q = POSITIVE[0]
    s_on = cfg(monkeypatch, fault="1")
    assert A.pure_scope_v19(A.parse(q), s_on, q) == PURE.FAULT_WHY
    s_off = cfg(monkeypatch, fault="0")
    assert A.pure_scope_v19(A.parse(q), s_off, q) is None


def test_the_rule_question_route_wins_and_is_unchanged(monkeypatch):
    s = cfg(monkeypatch, fault="1")
    q = "정비 기한이 지나면 알림이 가?"                      # PURE_RULE이 먼저 가져가는 질문
    assert A.pure_scope_v19(A.parse(q), s, q) == PURE.RULE_WHY


def test_pure_rule_alone_does_not_route_fault_questions(monkeypatch):
    s = cfg(monkeypatch, fault="0", rule="1")
    for q in POSITIVE[:6]:
        assert A.pure_scope_v19(A.parse(q), s, q) is None


def test_negatives_stay_on_the_old_path_with_the_switch_on(monkeypatch):
    s = cfg(monkeypatch)
    for q in NEGATIVE + OTHER_SIGNALS:
        p = A.parse(q)
        if not PURE.has_signals(p):               # 규칙이 신호를 하나도 못 찾은 질문은 원래 순수 길이다(이 규칙과 무관)
            continue
        assert A.pure_scope_v19(p, s, q) is None, q


# ------------------------------------------------------------------ 회귀 사례 (기존 운영 질문 은행 + 튜닝 은행)
def _cases(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def test_known_operations_questions_never_take_the_fault_route(monkeypatch):
    """PURE_RULE 때 모은 운영 질문 256개와 튜닝 은행의 운영(O)·알람 번호(A) 질문 110개 중 하나도 고장 대응 경로(PURE_FAULT)로 가면 안 된다."""
    s = cfg(monkeypatch)
    qs = _cases("route_bank_cases.json")["ops"] + _cases("fault_bank_cases.json")["O"] + _cases("fault_bank_cases.json")["A"]
    assert len(qs) >= 350
    bad = [q for q in qs if A.pure_scope_v19(A.parse(q), s, q) == PURE.FAULT_WHY]
    assert not bad, bad


def test_the_fault_questions_the_rule_catches_stay_caught(monkeypatch):
    s = cfg(monkeypatch)
    qs = _cases("fault_bank_cases.json")["F_caught"]
    assert len(qs) >= 15
    lost = [q for q in qs if A.pure_scope_v19(A.parse(q), s, q) not in (PURE.FAULT_WHY, PURE.RULE_WHY)]       # 규칙 질문 경로(PURE_RULE)가 먼저 가져가는 것도 문서 길이다
    assert not lost, lost


# ------------------------------------------------------------------ 설정
def test_default_is_off_and_env_is_read(monkeypatch):
    assert Settings.__dataclass_fields__["pure_fault"].default is False
    monkeypatch.delenv("PURE_FAULT", raising=False)
    assert settings().pure_fault is False                    # 시험 기본(conftest)도 꺼짐
    for raw, want in (("1", True), ("true", True), ("0", False), ("", False), ("아무거나", False)):
        monkeypatch.setenv("PURE_FAULT", raw)
        assert settings().pure_fault is want


def test_the_ops_note_is_added_for_the_fault_route_too(monkeypatch):
    s = cfg(monkeypatch)
    seen = []
    monkeypatch.setattr(C, "chat_json", lambda messages, schema, job, max_tokens, st: seen.append(messages[0]["content"]) or {"answer": "x", "cited": [], "insufficient": True})
    chunks = [c for _, c in PURE.retrieve("수명", 2)]
    PURE.ask(POSITIVE[0], chunks, None, s, ops_note=True)
    assert PURE.RULE_OPS_NOTE in seen[0]


# ------------------------------------------------------------------ 끝에서 끝 (가짜 Claude 실행기)
class Runner:
    """mode: "answer" · "insufficient" · "fail". 두 번째(넓게 다시 본) 호출은 second로 정한다."""

    def __init__(self, first="answer", second="answer"):
        self.calls, self.first, self.second = [], first, second

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        system = cmd[cmd.index("--system-prompt") + 1] if "--system-prompt" in cmd else ""
        wide = PURE.RETRY_NOTE in system
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append({"wide": wide, "system": system, "props": props, "user": stdin_text})
        mode = self.second if wide else self.first
        if mode == "fail":
            return SimpleNamespace(returncode=1, stdout="", stderr="시험: 실패")
        ins = mode == "insufficient"
        n = max([int(x) for x in re.findall(r"\[C(\d+)\]", stdin_text)] or [1])
        so = {"answer": "문서에 없음" if ins else "문서 답이에요.", "cited": [] if ins else [f"C{n}" if wide else "C1"], "insufficient": ins}
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


def pure_calls(r):
    return [c for c in r.calls if c["props"] == PROPS]


@pytest.fixture
def run(monkeypatch):
    """run(first, second, q=Q, **env) -> (응답, 실행기). env로 PURE_FAULT·PURE_RETRY 등을 바꾼다."""
    def _run(first="answer", second="answer", q=POSITIVE[0], **env):
        get_state().reset()
        AS.clear()
        for k, v in APP_FLAGS.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("PURE_EXPAND", "1")
        monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
        monkeypatch.setenv("PURE_RULE", "1")
        monkeypatch.setenv("PURE_FAULT", "1")
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        r = Runner(first, second)

        def no_local(req):
            raise httpx.ConnectError("시험: 로컬 서버 없음")
        C.use_transport(httpx.MockTransport(no_local))
        CC.use_runner(r)
        return client.post("/api/assistant/chat", json={"question": q, "llm": "claude"}, headers={"X-Role": "SUP"}), r
    yield _run
    CC.use_runner(None)
    C.use_transport(None)
    AS.clear()
    get_state().reset()


def test_end_to_end_on_answers_a_fault_question_from_the_documents(run):
    resp, r = run(first="answer")
    body = resp.json()
    assert len(pure_calls(r)) == 1                                              # 문서 길로 Claude를 한 번 불렀다
    assert body["status"] == "답변" and body["conclusion"] == "문서 답이에요."
    assert "순수 외부 LLM" in (body.get("route") or {}).get("source", "")
    assert PURE.RULE_OPS_NOTE in pure_calls(r)[0]["system"]                       # 운영 기록이면 insufficient 한 줄


def test_end_to_end_off_keeps_the_old_path(run):
    resp, r = run(PURE_FAULT="0")
    assert resp.status_code == 200 and len(pure_calls(r)) == 0
    assert resp.json().get("conclusion") != "문서 답이에요."


def test_when_the_document_path_finds_nothing_the_answer_is_exactly_the_old_one(run):
    off, _ = run(first="insufficient", second="insufficient", PURE_FAULT="0", PURE_RETRY="0")
    off_status, off_concl = off.json()["status"], off.json()["conclusion"]
    on, r = run(first="insufficient", second="insufficient", PURE_RETRY="0")
    assert on.status_code == off.status_code == 200
    assert (on.json()["status"], on.json()["conclusion"]) == (off_status, off_concl)         # 되돌리기: 끈 것과 같은 답
    assert len(pure_calls(r)) == 1                                                            # 늘어나는 것은 Claude 호출 1회뿐


def test_when_the_claude_call_fails_a_fault_routed_question_is_answered_by_the_old_path(run):
    off, _ = run(first="answer", PURE_FAULT="0")
    on, r = run(first="fail")
    assert on.status_code == off.status_code == 200
    assert (on.json()["status"], on.json()["conclusion"]) == (off.json()["status"], off.json()["conclusion"])


def test_the_fault_route_never_retries_it_falls_back_at_once(run):
    """진짜 Claude 측정(2026-10-18): 고장 대응 질문 30개에서 재시도가 걸린 적이 없고, 잘못 보낸 운영 질문에서는 재시도가 어정쩡한 문서 답을 만들어 되돌리기를 막았다 — 이 경로는 재시도 없이 바로 되돌린다."""
    off, _ = run(first="answer", PURE_FAULT="0", PURE_RETRY="0")
    on, r = run(first="insufficient", second="answer", PURE_RETRY="1")
    assert len(pure_calls(r)) == 1 and not any(c["wide"] for c in r.calls)
    assert (on.json()["status"], on.json()["conclusion"]) == (off.json()["status"], off.json()["conclusion"])      # 곧바로 기존 길 답


def test_the_rule_route_still_never_retries(run):
    resp, r = run(first="insufficient", q="정비 기한이 지나면 알림이 가?", PURE_RETRY="1")
    assert len(pure_calls(r)) == 1 and not any(c["wide"] for c in r.calls)


def test_a_safety_word_in_a_misrouted_operations_question_does_not_block_the_fallback(run):
    """"안전 재고"·"톱"·"차단기" 같은 안전 낱말이 든 운영 질문이 잘못 이 경로로 와도 "자동으로 확인하지 못했어요" 안전 안내가 아니라 원래 기존 길 답을 받는다."""
    q = "톱 레일 기름 모자라다고 떴어. 기름통이 어디 있어?"
    off, _ = run(first="answer", q=q, PURE_FAULT="0", PURE_SAFETY="1")
    on, r = run(first="insufficient", q=q, PURE_SAFETY="1")
    assert len(pure_calls(r)) == 1
    assert on.status_code == off.status_code == 200
    assert "자동으로 확인하지 못했어요" not in (on.json().get("conclusion") or "")
    assert (on.json()["status"], on.json()["conclusion"]) == (off.json()["status"], off.json()["conclusion"])
