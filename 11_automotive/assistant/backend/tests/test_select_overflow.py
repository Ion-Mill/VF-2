"""줄 고르기에서 모델이 6개를 넘게 골랐을 때 (2026-10-25, 팀원 로그: line_ids 9개·8개 > 6 → 질문 전체 "응답 없음").

지키는 것
① 개수만 넘친 응답은 클라이언트 단계에서 버리지 않는다 (Claude는 maxItems를 API로 못 막는다 — 받은 뒤 jobs.validate_select가 본다)
② select_lines가 한 번 다시 고르게 한다 (이유에 "N개 > 6")
③ 재질문까지 개수만 넘치면 마지막 응답의 앞 6개로 잇는다. 번호가 후보에 없거나 중복이거나 앞머리가 맞지 않으면 그대로 실패 (오류가 아니라 규칙 답으로)
④ API로 나가는 스키마에는 maxItems·softMaxItems가 없다
실제 Claude·Gemini는 부르지 않는다 (가짜 클라이언트).
"""
import json
from types import SimpleNamespace

import pytest

from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import jobs, schemas
from backend.llm.client import LlmBadOutput
from backend.tests.test_claude_client import MSG, claude, reply  # noqa: F401  (fixture)

LINES = ["가 단계를 확인한다", "나 단계를 확인한다", "다 단계를 확인한다", "라 단계를 확인한다",
         "마 단계를 확인한다", "바 단계를 확인한다", "정렬 값은 25 mm 이다", "사 단계를 확인한다"]
CHUNK = SimpleNamespace(chunk_id="c1")
IDS = [f"L{i}" for i in range(1, 9)]


def _line_fn(_c):
    return list(LINES)


def _head_fn(_c):
    return "DOC-00 시험 문서 §1"


def _out(ids, lead="단계를 확인한다는 내용이에요", answerable=True):
    return {"answerable": answerable, "line_ids": list(ids), "lead": lead}


class Fake:
    """jobs.chat_json 자리에 끼우는 가짜. 부른 메시지를 모은다."""

    def __init__(self, *outs):
        self.outs, self.msgs = list(outs), []

    def __call__(self, messages, schema, name, max_tokens=400, s=None, grammar=None):
        self.msgs.append(messages)
        return self.outs.pop(0)


def run(monkeypatch, *outs, strict=False):
    fake = Fake(*outs)
    monkeypatch.setattr(jobs, "chat_json", fake)
    sel, tr = jobs.select_lines("시험 질문", [CHUNK], _line_fn, _head_fn, strict=strict)
    return sel, tr, fake


# ------------------------------------------------------------------ ① 클라이언트는 개수로 버리지 않는다
def test_schema_keeps_the_soft_limit_but_the_api_never_sees_it():
    sch = schemas.select(IDS)
    assert sch["properties"]["line_ids"].get("softMaxItems") == 6 and "maxItems" not in sch["properties"]["line_ids"]
    sent = json.dumps(CC.prepare_schema(sch))
    assert "maxItems" not in sent and "softMaxItems" not in sent and "minItems" not in sent
    assert "softMaxItems" in json.dumps(sch)                                   # 원래 스키마는 건드리지 않는다


@pytest.mark.parametrize("n", [7, 13])
def test_client_accepts_more_than_six_line_ids(claude, n):
    fake, _ = claude
    ids = [f"L{1 + i % 8}" for i in range(n)]
    fake.replies.append(reply(json.dumps(_out(ids))))
    out = C.chat_json(MSG, schemas.select(IDS), "select", 300)
    assert len(out["line_ids"]) == n


def test_client_still_rejects_unknown_ids_and_other_violations(claude):
    fake, _ = claude
    fake.replies.append(reply(json.dumps(_out(["L99"]))))
    with pytest.raises(LlmBadOutput, match="enum"):
        C.chat_json(MSG, schemas.select(IDS), "select", 300)
    fake.replies.append(reply(json.dumps(_out(["L1"], lead="가" * 200))))
    with pytest.raises(LlmBadOutput, match="글자"):                             # lead maxLength 160은 그대로
        C.chat_json(MSG, schemas.select(IDS), "select", 300)


def test_validate_constraints_ignores_the_soft_limit_but_keeps_hard_ones():
    sch = schemas.select(IDS)
    assert CC.validate_constraints(_out(IDS), sch) is None                      # 8개
    assert CC.validate_constraints(_out(IDS) | {"extra": 1}, sch) is not None   # 모르는 칸은 그대로 거부


# ------------------------------------------------------------------ ② 다시 고르게 한다
def test_overflow_reason_is_specific_and_keeps_the_old_prefix():
    offered = jobs.offer([CHUNK], _line_fn)
    sel, reason = jobs.validate_select(_out(IDS[:7]), offered)
    assert sel is None and reason.startswith("줄 번호 오류") and "7개" in reason and "6" in reason


def test_exactly_six_passes_at_once(monkeypatch):
    sel, tr, fake = run(monkeypatch, _out(IDS[:6]))
    assert sel is not None and len(sel["lines"]) == 6 and tr["tries"] == 1 and not tr.get("trimmed")


def test_seven_then_six_is_fixed_by_the_second_ask(monkeypatch):
    sel, tr, fake = run(monkeypatch, _out(IDS[:7]), _out(IDS[:6]))
    assert sel is not None and len(sel["lines"]) == 6 and tr["tries"] == 2 and not tr.get("trimmed")
    second = fake.msgs[1][-1]["content"]
    assert "7개" in second and "6" in second                                    # 재질문에 "몇 개를 골랐고 몇 개 이하로"가 간다


# ------------------------------------------------------------------ ③ 그래도 넘치면 앞 6개
def test_still_over_after_the_second_ask_uses_the_first_six(monkeypatch):
    sel, tr, fake = run(monkeypatch, _out(IDS[:7]), _out(["L8", "L1", "L2", "L3", "L4", "L5", "L6", "L7"]))
    assert tr["tries"] == 2 and len(fake.msgs) == 2                             # 호출은 늘지 않는다
    assert sel is not None and tr["used"] is True and tr["reason"] is None and tr["trimmed"] == 2
    assert len(sel["lines"]) == 6
    assert LINES[5] not in sel["lines"] and LINES[6] not in sel["lines"]       # 모델이 고른 순서의 앞 6개(L8, L1..L5)만 남고 L6·L7은 빠진다
    assert sel["lines"] == [LINES[i] for i in (0, 1, 2, 3, 4, 7)]              # 결과는 문서 순서로 정렬된다


def test_trim_also_works_in_the_strict_gate(monkeypatch):
    sel, tr, fake = run(monkeypatch, _out(IDS[:8]), _out(IDS[:8]), strict=True)
    assert sel is not None and len(sel["lines"]) == 6 and tr["trimmed"] == 2


def test_unknown_id_is_never_trimmed_into_a_pass(monkeypatch):
    sel, tr, _ = run(monkeypatch, _out(IDS[:6] + ["L99"]), _out(IDS[:6] + ["L99"]))
    assert sel is None and tr["reason"].startswith("줄 번호 오류") and not tr.get("trimmed")


def test_duplicate_ids_are_never_trimmed_into_a_pass(monkeypatch):
    dup = ["L1", "L1", "L2", "L3", "L4", "L5", "L6"]
    sel, tr, _ = run(monkeypatch, _out(dup), _out(dup))
    assert sel is None and not tr.get("trimmed")


def test_trim_that_leaves_the_lead_unsupported_falls_back_without_error(monkeypatch):
    lead = "정렬 값은 25 mm로 맞춘다"                                           # 25는 7번째 줄에만 있다 — 앞 6개로 자르면 근거가 사라진다
    sel, tr, _ = run(monkeypatch, _out(IDS[:7], lead), _out(IDS[:7], lead))
    assert sel is None and "숫자" in (tr["reason"] or "")                       # 예외가 아니라 None → 부른 쪽이 규칙 답으로 간다


def test_answerable_false_and_empty_are_unchanged(monkeypatch):
    sel, tr, fake = run(monkeypatch, _out([], answerable=False))
    assert sel is None and tr["reason"].startswith("답할 줄 없음") and len(fake.msgs) == 1


# ------------------------------------------------------------------ 끝에서 끝: 실제 클라이언트 길 (가짜 Claude 응답)
def test_end_to_end_through_the_claude_client_seven_then_nine(claude):
    fake, _ = claude
    fake.replies.append(reply(json.dumps(_out(IDS[:7]))))
    fake.replies.append(reply(json.dumps(_out(IDS[:8]))))
    sel, tr = jobs.select_lines("시험 질문", [CHUNK], _line_fn, _head_fn)
    assert sel is not None and len(sel["lines"]) == 6 and tr["tries"] == 2 and tr["trimmed"] == 2
    assert len(fake.calls) == 2                                                 # 외부 호출은 두 번 그대로
