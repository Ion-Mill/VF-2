"""접근 금지 경고의 뜻 뒤집힘 시험 (2026-10-14, 앱 화면 "VF2-01 전원을 켜고 원점 복귀할 때 사람이 조심할 게 뭐야?").

앱 화면 답: "…주축·테이블·공구 교환장치에서 떨어질 수 있으니 주의하세요." — 문서(DOC-01 §4.3)와 제조사 원문은 "사람이 떨어져 있어라(Stay away)"는 뜻이다.
분석과 계획: research_notes/접근금지경고_뜻뒤집힘_원인과_시험계획_20261014.md 4.1절 (사용자 결정: 고치는 안 A 문서 / B 코드와 무관한 행동 시험을 먼저, 빨강부터).

이 파일의 `RED` 시험은 **고치기 전에는 실패하는 것이 정상**이었다. xfail(strict)로 두었다가 고쳐서 통과하기 시작하면 RED 표시를 지운다.
2026-10-14 저녁: 스위치 WRITE_RULES_V17(followup_v2.is_keepaway_v16·possib_new_v17, answer.doc_write_mode_v15)로 고쳐 RED 표시를 모두 지웠다 —
고친 동작은 스위치를 켠 상태(`step20-rules`)에서 시험한다. 스위치를 끈 상태(= 지금 앱)는 아직 빨강이다(test_off_state_is_still_red).
줄 글은 하드코딩하지 않고 사내 문서에서 읽는다(문서가 바뀌면 시험이 알려 준다). AI 서버는 부르지 않는다(chat_json을 가짜로 끼움).
"""
import re
from dataclasses import replace

import pytest

from backend.eval import run_eval as R
from backend.llm.client import LlmUnavailable
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import followup_v2 as FU2

Q = "VF2-01 전원을 켜고 원점 복귀할 때 사람이 조심할 게 뭐야?"
# 접근 금지가 "떨어질 가능성"으로 바뀐 꼴 (관측된 오답: "떨어질 수 있으니 주의하세요")
FALL = re.compile(r"떨어질\s*(?:수|것)|떨어지(?:니|므로)|떨어질까")

NEEDLE_POWER_UP = "[POWER UP]을 누르면 바로 자동으로 움직인다"      # DOC-01 §4.3 ①-5 주의 칸
NEEDLE_POWER_OFF = "전원 켜기·끄기·공구 교환장치 동작 중에는"        # DOC-01 §4.3 안전 표


def _find(needle: str):
    """사내 문서에서 줄 하나와 그 출처 (줄, 출처 칸)."""
    for ch in load_corpus():
        for t in A.plain_lines(ch):
            if needle in t:
                return t, {"doc_id": ch.doc_id, "section": ch.section}
    raise AssertionError(f"사내 문서에서 줄을 찾지 못함: {needle}")


def _s(**kw):
    base = replace(A.settings(), llm_enabled=True, llm_jobs=frozenset({"write"}), doc_write=True,
                   parse_v2=True, parse_v3=True, parse_v4=True, parse_v5=True, parse_v6=True, parse_v7=True, parse_v8=True,
                   safe_write_doc=False, safe_write_words=False, write_rules_v17=True)
    return replace(base, **kw)


FLAG_SETS = [{}, {"safe_write_doc": True, "safe_write_words": True}]   # 앱 값(안전 영역 새로쓰기 켬)과 꺼짐 둘 다


# ── T1 새로 쓰기 문지기: 접근 금지·자동 이동 경고 줄은 AI가 다시 쓰지 않는다 (WRITE_RULES_V17 켬) ──
@pytest.mark.parametrize("flags", FLAG_SETS, ids=["안전새로쓰기_끔", "안전새로쓰기_켬"])
@pytest.mark.parametrize("needle", [NEEDLE_POWER_UP, NEEDLE_POWER_OFF], ids=["455행_주의칸", "542행_안전표"])
def test_t1_keepaway_warning_lines_are_not_rewritten(needle, flags):
    line, cite = _find(needle)
    assert A.doc_write_mode_v15(_s(**flags), [line], [cite], None, False) is None


# ── T1-끔: 스위치를 끈 상태는 예전 동작 그대로다 (아직 앱 값이 아님 — 이 줄은 앱에 켜기 전의 안전망) ──
@pytest.mark.parametrize("needle", [NEEDLE_POWER_UP, NEEDLE_POWER_OFF], ids=["455행_주의칸", "542행_안전표"])
def test_t1_off_state_keeps_old_behavior(needle):
    line, cite = _find(needle)
    assert A.doc_write_mode_v15(_s(write_rules_v17=False), [line], [cite], None, False) is not None


# ── T2 과차단 방지: 다른 뜻의 "떨어"가 든 줄은 막지 않는다 (지금도 초록, 고친 뒤에도 초록이어야 함) ──
@pytest.mark.parametrize("needle, flags", [
    ("정상보다 빨리 떨어졌다", {}),                                  # DOC-02 §4.11 알람 2075 (압력이 떨어짐)
    ("실질적으로 떨어뜨리고", {}),                                   # DOC-06 §8.1 중결함 정의 (실용성이 떨어짐)
    ("알람 805 LOW SPINDLE LUBRICATION", {}),                      # DOC-04 §4.4 "떨어지면" (재고가 떨어지면)
    ("회로 차단기가 떨어졌다", FLAG_SETS[1]),                         # DOC-02 §4.14 알람 552 (차단기가 트립됨 — 안전 낱말이라 켠 뒤에만)
])
def test_t2_other_meanings_of_fall_are_not_blocked(needle, flags):
    line, cite = _find(needle)
    assert A.doc_write_mode_v15(_s(**flags), [line], [cite], None, False) is not None


# ── T3·T4 끝에서 끝 (가짜 LLM): 뜻이 뒤집힌 글이 화면에 나가면 안 된다 ──
def _run_with_fake_llm(monkeypatch, write_answer_for):
    """앱 설정(step20) + WRITE_RULES_V17(step20-rules)로 질문 하나를 돌린다. write_answer_for(k) = 새로 쓴 답 (k = '[POWER UP]'을 가린 자리표 번호)."""
    for k, v in R.MODES["step20-rules"].items():
        monkeypatch.setenv(k, v)
    calls = []

    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        calls.append(name)
        user = messages[-1]["content"]
        if name == "route":
            return {"kind": "doc", "intents": [], "equipment": ["VF2-01"], "period": "none", "shift": "none",
                    "search_queries": ["VF2-01 원점 복귀 안전 주의사항", "절삭기 전원 켜기 안전 수칙"], "doc_question": ""}
        if name == "select":   # 관측된 줄 고르기(2026-10-14 로그): 455행 주의 칸 줄 + 비상 정지·도어·외함·프로그램 실행 중 줄 6개
            # 한 줄만 고르면 낱말 겹침 검사(질문 낱말 1/7)에서 먼저 끊긴다 — 실제 모델이 6줄을 골라 통과했다
            picks = ("바로 자동으로 움직인다", "[EMERGENCY STOP] — 하는 일", "도어가 닫혀 있지 않거나", "기계가 도는 동안 도어를 닫아",
                     "외함 안에 들어가기 전에", "프로그램 실행 중에는 테이블")
            by_id = {m.group(1): m.group(2) for m in re.finditer(r"^(L\d+): (.*)$", user, re.M)}
            ids = [i for p in picks for i, t in by_id.items() if p in t][:6]
            return {"answerable": True, "line_ids": ids, "lead": "원점 복귀 때 주축·테이블·공구 교환장치에서 떨어질 수 있고"}
        if name == "verify":
            return {"answers": True, "missing": ""}
        if name == "write_answer":
            m = re.search(r"\[\{\{(\d+)\}\}\]을 누른다", user)
            return {"answer": write_answer_for(m.group(1) if m else "1")}
        if name in ("answer_faith", "lead_faith"):
            return {"faithful": True, "problem": ""}   # 관측: 같은 모델이라 오독을 공유해 통과시킴
        raise LlmUnavailable("이 시험은 모르는 작업")

    monkeypatch.setattr(A.jobs, "chat_json", fake)
    monkeypatch.setattr(FU2, "chat_json", fake)
    return A.answer(Q, "MNT"), calls


def _inverted(k):
    return "원점 복귀 시 [{{" + k + "}}]를 누르면 축이 자동으로 움직이므로 주축·테이블·공구 교환장치에서 떨어질 수 있으니 주의하세요."


def _correct(k):
    return "[{{" + k + "}}]를 누르면 축이 자동으로 움직이므로 사람은 주축·테이블·공구 교환장치에서 떨어져 있어야 해요."


def test_t3_inverted_sentence_never_reaches_the_screen(monkeypatch):
    a, calls = _run_with_fake_llm(monkeypatch, _inverted)
    assert a["status"] == "답변"
    assert not FALL.search(a["conclusion"]), a["conclusion"][:200]
    assert not a.get("written")


def test_t4_correct_sentence_is_shown_or_original_lines_but_never_inverted(monkeypatch):
    a, calls = _run_with_fake_llm(monkeypatch, _correct)
    assert a["status"] == "답변"
    assert not FALL.search(a["conclusion"])
    if a.get("written"):   # 새 글이 나갔다면 접근 금지 뜻이어야 한다
        assert "떨어져 있" in a["conclusion"].split("문서 원문:")[0]
    else:                  # 아니면 원문 줄 (주어 없는 "…에서 떨어진다" 그대로)
        assert "떨어진다" in a["conclusion"]


# ── T5 1차 길 앞머리: 줄 고르기가 함께 낸 한 문장 요약도 같은 오독을 막아야 한다 ──
def test_t5_inverted_lead_is_rejected_by_the_lead_check(monkeypatch):
    for k, v in R.MODES["step20-rules"].items():
        monkeypatch.setenv(k, v)
    line, _ = _find(NEEDLE_POWER_UP)
    lead = "전원 켜기와 원점 복귀 시 주의할 점은 POWER UP 누르면 축이 자동으로 움직이며 주축·테이블·공구 교환장치에서 떨어질 수 있고"
    assert FU2.check_lead_code_v12(lead, [line], Q) is not None


# ── T6 경고 줄 판별 (함수 이름 `is_keepaway_v16`은 시험이 먼저 정한 제안 — 바꾸려면 이 시험과 함께) ──
KEEPAWAY_TRUE = [NEEDLE_POWER_UP, NEEDLE_POWER_OFF]
KEEPAWAY_FALSE = ["정상보다 빨리 떨어졌다", "실질적으로 떨어뜨리고", "알람 805 LOW SPINDLE LUBRICATION", "회로 차단기가 떨어졌다"]


@pytest.mark.parametrize("needle, want", [(n, True) for n in KEEPAWAY_TRUE] + [(n, False) for n in KEEPAWAY_FALSE])
def test_t6_keepaway_line_detector(needle, want):
    fn = getattr(FU2, "is_keepaway_v16", None)
    assert fn is not None, "경고 줄 판별 함수가 아직 없음 (followup_v2.is_keepaway_v16 제안)"
    line, _ = _find(needle)
    assert fn(line) is want
