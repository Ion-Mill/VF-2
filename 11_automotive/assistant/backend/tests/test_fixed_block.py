"""채팅 고정 서식 병기(FIXED_BLOCK) 시험 (2026-10-18, A2b). 진짜 `claude`·네트워크·DB를 부르지 않는다(가짜 실행기).

배경: 채팅 "잠금·표지·순서" 답은 6+3단계를 Claude가 풀어 썼고 프로그램이 붙인 원문 블록이 없었으며 번호가 1~6, 1~3으로 바뀌었다(FR-AST-COM-13).
사용자 결정(2026-10-18): 채팅에서만 풀어 써도 되지만 **원문 블록을 병기**하고, 순서 전체를 물었는데 풀이가 단계를 빠뜨리거나 없는 번호를 쓰면 풀이를 버리고 블록만 보인다.
지키는 것: ① 질문에 맞는 서식 선택(걸기·풀기·고전압·보호구, 무관한 질문은 없음) ② 블록 글자는 templates.py 상수 그대로 ③ 풀이 검사(없는 번호·빠진 단계·순서)
④ 끝에서 끝: Claude에게 공식 번호·이름이 가고, 블록이 답 아래에 붙고, 풀이가 어긋나면 블록만 남음 ⑤ 스위치 꺼짐이면 아무것도 안 바뀜.
"""
import json
import re
from types import SimpleNamespace

import pytest

from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.safety import fixed_block as FB
from backend.safety import templates as T
from backend.services import answer as A
from backend.chat_mapping import to_answer_text
from backend.tests.test_pure_expand import APP_FLAGS

SONNET = "claude-sonnet-5-5"


# ---------------------------------------------------------------- ① 선택
@pytest.mark.parametrize("q,keys", [
    ("잠금 표지 순서가 어떻게 돼?", ["before6", "after3"]),
    ("작업 전에 잠그는 순서 알려줘", ["before6"]),
    ("정비 전에 먼저 뭘 잠가?", ["before6"]),
    ("잠금 풀 때 순서 알려줘", ["after3"]),
    ("작업 끝나고 자물쇠 제거 어떻게 해?", ["after3"]),
    ("잠금 6단계랑 해제 3단계 모두 알려주세요", ["before6", "after3"]),
    ("제어반 열기 전에 고전압 몇 분 기다려?", ["high_voltage"]),
    ("보호구 뭐 써야 돼?", ["ppe"]),
    ("회전체 다룰 때 면장갑 써도 돼?", ["ppe"]),
    ("정비 전 잠금 순서랑 고전압 대기 알려줘", ["before6", "high_voltage"]),
])
def test_blocks_chosen_for_questions_that_ask_for_the_fixed_format(q, keys):
    assert FB.select(q) == keys, q


@pytest.mark.parametrize("q", ["쿨런트가 뭐야?", "2075 알람 뭐야", "보호구 지급 신청은 어디서 해?", "장갑 재고 얼마나 남았어?", "로트 보류하면 누가 풀어?", "소음 구역은 어디야?"])
def test_unrelated_questions_get_no_block(q):
    assert FB.select(q) == [], q


def test_at_most_two_blocks():
    assert len(FB.select("잠금 순서랑 고전압 대기랑 보호구 다 알려줘")) <= 2


# ---------------------------------------------------------------- ② 블록 글자는 templates.py 상수 그대로
def test_block_text_is_the_templates_constants_verbatim():
    lines = FB.lines(["before6", "after3", "high_voltage", "ppe"])
    for code, name in T.BEFORE + T.AFTER:
        assert f"{code} {name}" in lines
    for ln in T.HIGH_VOLTAGE + T.PPE + [T.HIGH_VOLTAGE_HEAD, T.BASIS, T.SOURCE]:
        assert ln in lines
    blocks = FB.blocks(["before6"])
    assert blocks[0] == {"kind": "section", "text": T.TITLE} and "AI 작성 아님" in T.TITLE
    assert [b["text"] for b in blocks[1:]] == FB.lines(["before6"])
    assert FB.blocks([]) == [] and FB.lines([]) == []


# ---------------------------------------------------------------- ③ 풀이 검사
FULL_BEFORE = "작업 전에는 " + " → ".join(f"{c} {n}" for c, n in T.BEFORE) + " 순서로 해요."


def test_full_sequence_question_requires_every_step_in_order():
    keys = ["before6"]
    assert FB.wants_full("작업 전에 잠그는 순서 알려줘", keys) is True
    assert FB.check_answer(FULL_BEFORE, keys, True) is None
    assert "빠진 단계" in FB.check_answer("6.1 준비, 6.2 정지, 6.3 차단 순서예요.", keys, True)
    shuffled = "6.2 정지 → 6.1 준비 → 6.3 → 6.4 → 6.5 → 6.6"
    assert FB.check_answer(shuffled, keys, True) == "단계 순서가 다름"


def test_a_range_mention_up_front_does_not_break_the_order_check():
    # 진짜 Claude가 쓴 꼴: 머리말에 "6.1~6.6, 7.1~7.3"을 먼저 말하고 본문에서 차례대로 푼다 (처음 나온 자리만 보면 6.6이 6.2보다 앞이라 틀리게 버려졌다)
    both = ["before6", "after3"]
    head = "걸 때 작업 전 6단계(6.1~6.6), 풀 때 작업 후 3단계(7.1~7.3) 순서로 해요. "
    body = " ".join(f"{c} {n}에서는 해요." for c, n in T.BEFORE + T.AFTER)
    assert FB.check_answer(head + body, both, True) is None
    reversed_body = " ".join(f"{c} {n}에서는 해요." for c, n in reversed(T.BEFORE + T.AFTER))
    assert FB.check_answer(head + reversed_body, both, True) == "단계 순서가 다름"      # 범위 말이 앞에 있어도 본문이 거꾸로면 어긋남
    assert "빠진 단계" in FB.check_answer(head + body.replace("6.4", "그 단계"), both, True)


def test_a_step_that_is_not_in_the_document_is_rejected_even_for_a_partial_question():
    assert "없는 단계 번호" in FB.check_answer("7.4 단계에서 자물쇠를 풀어요.", ["after3"], False)
    assert FB.check_answer("7.3 단계에서 내 자물쇠만 내가 떼요.", ["after3"], False) is None
    # 단위가 붙은 값(6.9 bar, 7.5 mm)은 단계 번호가 아니다 — 정당한 풀이를 "없는 단계 번호"로 버리지 않는다
    assert FB.check_answer("공압 잔압을 빼서 압력계가 0이 되면 100 psi(약 6.9 bar)도 남지 않은 거예요.", ["before6"], False) is None
    assert FB.check_answer("두께 7.5 mm 이하인 칩은 6.5 단계에서 치워요.", ["before6"], False) is None


def test_partial_question_does_not_demand_the_full_sequence():
    assert FB.wants_full("사람이 없는데 자물쇠 제거 어떻게 해?", ["after3"]) is False
    assert FB.wants_full("검전기는 어느 선에 대고 확인해?", ["before6"]) is False
    assert FB.check_answer("관리자 지시로 반장이 떼요.", ["after3"], False) is None


# ---------------------------------------------------------------- ④ 끝에서 끝 (가짜 Claude)
class Runner:
    def __init__(self, answer):
        self.answer, self.systems, self.calls = answer, [], 0

    def __call__(self, cmd, stdin_text, timeout):
        self.calls += 1
        self.systems.append(cmd[cmd.index("--system-prompt") + 1])
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}},
               "structured_output": {"answer": self.answer, "cited": ["C1"], "insufficient": False}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


@pytest.fixture
def pure(monkeypatch):
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "1")
    monkeypatch.setenv("FIXED_BLOCK", "1")
    yield
    CC.use_runner(None)


def ask(q):
    with EXT.external_request("claude"):
        return A.answer(q, "SUP", {})


def test_block_is_attached_below_the_explanation_and_claude_gets_the_official_names(pure):
    r = Runner(FULL_BEFORE)
    CC.use_runner(r)
    a = ask("작업 전에 잠그는 순서 알려줘")
    text = to_answer_text(a)
    assert a["fixed_block"] == {"keys": ["before6"], "fallback": None}
    assert FULL_BEFORE in text                                              # Claude의 풀이는 그대로 보이고
    assert T.TITLE in text and f"{T.BEFORE[0][0]} {T.BEFORE[0][1]}" in text    # 그 아래에 고정 서식이 붙는다
    assert text.index(FULL_BEFORE) < text.index(T.TITLE)
    assert all(f"{c} {n}" in r.systems[0] for c, n in T.BEFORE)             # Claude에게 공식 번호·이름이 간다


def test_a_bad_explanation_is_replaced_by_the_block_only(pure):
    CC.use_runner(Runner("먼저 전원을 끄고 자물쇠를 걸어요. 마지막에 확인해요."))   # 단계 번호가 하나도 없는 풀이
    a = ask("작업 전에 잠그는 순서 알려줘")
    text = to_answer_text(a)
    assert a["fixed_block"]["fallback"].startswith("빠진 단계")
    assert FB.FALLBACK_LEAD in text and "자물쇠를 걸어요" not in text         # 풀이는 버려진다
    assert f"{T.BEFORE[-1][0]} {T.BEFORE[-1][1]}" in text                    # 블록은 그대로


def test_a_made_up_step_number_is_rejected(pure):
    CC.use_runner(Runner("7.4 단계에서 자물쇠를 풀어요."))
    a = ask("작업 후 자물쇠 제거 어떻게 해?")
    assert a["fixed_block"]["fallback"].startswith("없는 단계 번호")
    assert "7.4" not in to_answer_text(a)


def test_switch_off_changes_nothing(pure, monkeypatch):
    monkeypatch.setenv("FIXED_BLOCK", "0")
    r = Runner(FULL_BEFORE)
    CC.use_runner(r)
    a = ask("작업 전에 잠그는 순서 알려줘")
    assert "fixed_block" not in a and T.TITLE not in to_answer_text(a)
    assert "6.1 " + T.BEFORE[0][1] not in r.systems[0]


def test_non_safety_question_never_gets_a_block(pure):
    CC.use_runner(Runner("쿨런트는 절삭유예요."))
    a = ask("쿨런트가 뭐야?")
    assert "fixed_block" not in a
    assert re.search(r"고정 서식", to_answer_text(a)) is None
