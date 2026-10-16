"""OBLIGE_CHECK 시험 (2026-10-15 "해야 할 일 꼴" 코드 검사 끄기 실험, research_notes/OBLIGE_끄기_실험_20261015.md) — 시험용 복사본 전용.
스위치 `OBLIGE_CHECK=0`은 일반 새로 쓰기(safe=False)의 check_answer_v11 안 "~해야 한다" 꼴 검사 하나만 끈다.
앞머리 검사·안전 영역 새로쓰기(safe=True)·안전 점검 순서 다시 쓰기·다른 서술어 검사는 그대로여야 한다. LLM 없이 가짜 chat_json으로 본다."""
import pytest

from backend.config import settings
from backend.eval import run_eval as R
from backend.services import followup_v2 as FU2

LINE = "이송 속도 — 조정은 작업자가 한다"
Q = "이송 속도는 누가 조정해?"
TXT = "이송 속도는 작업자가 조정해야 해요."   # 원문 줄·질문에 없는 "야 해요" 꼴


def test_default_is_on_and_modes_differ_only_by_the_switch():
    assert settings().oblige_check is True                      # conftest가 "1"을 고정 — 기본은 지금 동작
    assert settings().flags()["oblige_check"] is True
    assert R._BASE["OBLIGE_CHECK"] == "1"
    on, off, sonnet = R.MODES["claude-sonnet-med"], R.MODES["claude-sonnet-med-obl0"], R.MODES["claude-sonnet"]
    assert {k for k in off if off[k] != on[k]} == {"OBLIGE_CHECK"} and off["OBLIGE_CHECK"] == "0" and on["OBLIGE_CHECK"] == "1"
    assert {k for k in on if on[k] != sonnet[k]} == {"MOM_CLAUDE_EFFORT"} and on["MOM_CLAUDE_EFFORT"] == "medium"
    assert on["MOM_CLAUDE_MODEL"] == "claude-sonnet-5-5" and on["LLM_PROVIDER"] == "claude"
    assert all(R.MODES[m]["OBLIGE_CHECK"] == "1" for m in R.MODES if m != "claude-sonnet-med-obl0")


@pytest.mark.parametrize("value, want", [("1", True), ("0", False), ("false", False), ("no", False), ("", True), ("켬", True)])
def test_env_parse(monkeypatch, value, want):
    monkeypatch.setenv("OBLIGE_CHECK", value)
    assert settings().oblige_check is want                      # 모르는 값·빈 값은 켜짐(지금 동작)


def test_check_answer_skips_only_the_oblige_check(monkeypatch):
    monkeypatch.setenv("LEAD_V12", "1")
    assert FU2.check_answer_v11(TXT, [LINE], set(), question=Q).startswith("해야 할 일 꼴")                 # 켬 = 예전 그대로
    assert FU2.check_answer_v11(TXT, [LINE], set(), question=Q, oblige=False) is None                      # 이 검사만 건너뜀
    # 다른 검사는 그대로: 허락 꼴·조작 지시·안전 낱말·한글 수사
    # (처음 쓴 기대는 이유 글이 정확히 "허락·지시 문구"라고 가정했다 — "돼요"는 "허락·지시 문구 (허락 꼴)"로 나온다. 시험 가정 오류, 코드 결함 아님)
    assert FU2.check_answer_v11("바로 돌려도 돼요.", [LINE], set(), question=Q, oblige=False).startswith("허락·지시 문구")
    assert FU2.check_answer_v11("공구를 바로 교체하세요.", [LINE], set(), question=Q, oblige=False).startswith("허락·지시 문구")
    assert FU2.check_answer_v11("케이블은 작업자가 한다.", [LINE], set(), question=Q, oblige=False) == "안전 낱말"
    assert FU2.check_answer_v11("세 번 조정해야 해요.", [LINE], set(), question=Q, oblige=False) == "한글 수사"
    # 원문 줄이나 질문에 같은 꼴이 있으면 켠 채로도 통과 (예전 규칙 그대로)
    assert FU2.check_answer_v11(TXT, [LINE + " (조정해야 한다)"], set(), question=Q) is None
    # (처음 쓴 질문 "…조정해야 해?"는 통과하지 않았다 — OBLIGE_V12는 "야 해요·합니다…"만 질문에서 찾고 "야 해?"는 WRITE_RULES_V17의 일이다. 시험 가정 오류, 코드 결함 아님)
    assert FU2.check_answer_v11(TXT, [LINE], set(), question="이송 속도는 누가 조정해야 해요?") is None
    assert FU2.check_answer_v11(TXT, [LINE], set(), question="이송 속도는 누가 조정해야 해?").startswith("해야 할 일 꼴")


def _fake(counter, answer=TXT):
    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        counter[name] = counter.get(name, 0) + 1
        return {"answer": answer} if name == "write_answer" else {"faithful": True, "problem": ""}
    return fake


def test_write_doc_answer_plain_follows_the_switch(monkeypatch):
    monkeypatch.setenv("LEAD_V12", "1")
    n = {}
    monkeypatch.setattr(FU2, "chat_json", _fake(n))
    out, tr = FU2.write_doc_answer(Q, [LINE])                                                   # 켬: 두 번 다 거부 → 새 글 없음
    assert out is None and n["write_answer"] == 2
    assert [r["reason"] for r in tr[0]["rejected"]] == ["해야 할 일 꼴 (원문·질문에 없음)"] * 2
    monkeypatch.setenv("OBLIGE_CHECK", "0")
    n.clear()
    out, tr = FU2.write_doc_answer(Q, [LINE])                                                   # 끔: 첫 시도에 통과
    assert out == TXT and n["write_answer"] == 1 and n["answer_faith"] == 1 and not tr[0]["rejected"]


def test_write_doc_answer_safe_keeps_the_check_even_when_off(monkeypatch):
    monkeypatch.setenv("LEAD_V12", "1")
    monkeypatch.setenv("OBLIGE_CHECK", "0")
    n = {}
    monkeypatch.setattr(FU2, "chat_json", _fake(n))
    out, tr = FU2.write_doc_answer(Q, [LINE], safe=True)                                       # 안전 영역 새로쓰기: 끔이어도 검사가 남음
    assert out is None and n["write_answer"] == 2
    assert tr[0]["rejected"][0]["reason"].startswith("해야 할 일 꼴")


def test_other_paths_are_not_switched_off(monkeypatch):
    monkeypatch.setenv("LEAD_V12", "1")
    monkeypatch.setenv("OBLIGE_CHECK", "0")
    # 1차 길 AI 앞머리: 코드 검사는 그대로 거부 (2026-10-14 "작업자가 이송과 속도를 조정해야 합니다" 사건을 막는 검사)
    assert FU2.check_lead_code_v12("작업자가 이송과 속도를 조정해야 합니다.", [LINE], Q) == "해야 할 일 꼴"
    # 안전 점검 순서 다시 쓰기: 새 "~해야 한다" 꼴은 그대로 거부
    assert FU2.check_safe_unit_v15("먼저 전원을 꺼야 한다", "먼저 전원을 끈다") == "해야 할 일 꼴"
