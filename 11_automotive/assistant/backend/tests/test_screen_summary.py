"""화면 정보판 요약 — 가짜 Claude. 진짜 호출·공용 DB·서버는 쓰지 않는다."""
from backend.config import settings
from backend.llm.claude_client import CONTINUE_JOB, PURE_ANSWER_JOB, SCREEN_SUMMARY_JOB
from backend.llm.external import MATERIAL_JOBS, ExternalLlmFailure
from backend.services import answer as A
from backend.services import screen_summary as SS
from backend.services.screen_summary import summarize


def test_job_uses_haiku_bucket_and_fails_closed():
    assert SS.JOB == SCREEN_SUMMARY_JOB == "screen_summary"
    assert SS.JOB in MATERIAL_JOBS
    assert SS.JOB in (PURE_ANSWER_JOB, CONTINUE_JOB, SCREEN_SUMMARY_JOB)


def test_prompt_describes_the_panel_only():
    assert "더 물어볼" not in SS.SYSTEM
    assert "칸 이름" in SS.SYSTEM


def test_question_filter():
    assert SS.is_screen_question("이 화면 설명해 줘")
    assert SS.is_screen_question("이 화면 요약해 줘")
    assert SS.is_screen_question("여기 뭐가 떠 있어?")
    assert not SS.is_screen_question("992 뜨면 뭐부터 봐?")
    assert not SS.is_screen_question("2075 알람 뭐야")
    assert not SS.is_screen_question("잠금·표지는 내가 지금 해?")


def test_switch_defaults_off(monkeypatch):
    monkeypatch.delenv("PURE_SCREEN_SUMMARY", raising=False)
    assert settings().pure_screen_summary is False
    monkeypatch.setenv("PURE_SCREEN_SUMMARY", "maybe")
    assert settings().pure_screen_summary is False
    monkeypatch.setenv("PURE_SCREEN_SUMMARY", "1")
    assert settings().pure_screen_summary is True


def test_summarize_sends_panel_and_strips(monkeypatch):
    seen = {}

    def fake(messages, schema, name, max_tokens, s):
        seen["messages"] = messages
        seen["name"] = name
        seen["max_tokens"] = max_tokens
        return {"answer": "  생산 102입니다.  "}

    monkeypatch.setattr(SS.C, "chat_json", fake)
    out = summarize("이 화면 설명해 줘", "SCR-04", "생산\n102\n102", object())
    assert out == "생산 102입니다."
    assert seen["name"] == "screen_summary" and seen["max_tokens"] == 900
    assert "[화면 글자]\n생산\n102" in seen["messages"][1]["content"]
    assert seen["messages"][1]["content"].count("\n102") == 1


def test_empty_answer_fails(monkeypatch):
    monkeypatch.setattr(SS.C, "chat_json", lambda *a, **k: {"answer": "  "})
    try:
        summarize("이 화면 설명해 줘", "SCR-04", "생산 102", object())
    except ExternalLlmFailure as e:
        assert e.job == "screen_summary"
    else:
        raise AssertionError("빈 답")


def test_switch_off_keeps_fixed_phrase(monkeypatch):
    monkeypatch.setenv("PURE_SCREEN_SUMMARY", "0")
    called = []
    monkeypatch.setattr(SS, "summarize", lambda *a, **k: called.append(1) or "요약")
    a = A.answer("이 화면 설명해 줘", "OPR", {"screen": "SCR-09"}, screen_text="알람 362")
    assert called == []
    assert a["mode"] == "화면 안내 (프로그램 고정 문구)"
    assert "지침카드" in a["conclusion"]


def test_switch_on_uses_panel_summary(monkeypatch):
    monkeypatch.setenv("PURE_SCREEN_SUMMARY", "1")
    monkeypatch.setattr(SS, "summarize", lambda q, code, text, s: f"{code}:{text}")
    a = A.answer("이 화면 요약해 줘", "OPR", {"screen": "SCR-04"}, screen_text="생산 102")
    assert a["mode"] == "화면 요약 (순수 LLM)"
    assert a["status"] == "안내"
    assert a["conclusion"] == "SCR-04:생산 102"


def test_switch_on_without_panel_keeps_fixed_phrase(monkeypatch):
    monkeypatch.setenv("PURE_SCREEN_SUMMARY", "1")
    a = A.answer("이 화면 설명해 줘", "OPR", {"screen": "SCR-09"}, screen_text="  ")
    assert a["mode"] == "화면 안내 (프로그램 고정 문구)"


def test_context_drops_screen_text():
    from backend.chat_service import _context
    ctx = _context({"screen": "SCR-04", "screen_text": "생산 102"})
    assert ctx == {"screen": "SCR-04"}
