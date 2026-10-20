"""9차 시험 (PARSE_V10·FLOW_V10·BLOCKS_V3, 2026-10-13 — research_notes/로컬 LLM 연결/앞단개선9_계획_20261013.md 1절).
1부 화면 대화 분석(research_notes/Qwen 모델 교체 효과 검증 20261013/1부_…)의 원인 A~J를 고친 것:
띄어쓰기(H), 섞인 알람 질문의 운영 조회를 마디마다(I), 카드 칸 "원문 설명" 빼기(D), 알람 답 "짧게"는 프로그램이(B),
줄 목록 칸 3판(표시만 — A 앞 답 그대로·C 덩어리 제목과 점검 순서 자리·F 정지 기준 따로·G 꼬리표). 잡아야 할 꼴과 반대 사례를 함께 둔다.
실제 LLM 서버 없이(LLM 끔)."""
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import blocks_v2 as BL2

ON9 = ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP", "PARSE_V8", "FOLLOWUP_V2",
       "PARSE_V9", "FLOW_V9", "BLOCKS_V2")
NEW = ("PARSE_V10", "FLOW_V10", "BLOCKS_V3")
EVAL = Path(__file__).resolve().parents[1] / "eval"
SNAP = Path(__file__).resolve().parent / "snapshots" / "fallback_answers.json"


@pytest.fixture
def v9(monkeypatch):
    """step11과 같은 스위치 (LLM 끔) — 9차 스위치는 아직 꺼짐."""
    for k in ON9:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("NUM_MATCH", "value")   # 앱 값 (root-cause-guards 8절: 앱 값에 기대는 동작은 시험 안에서 명시)
    AS.clear()
    yield monkeypatch
    AS.clear()


@pytest.fixture
def all10(v9):
    for k in NEW:
        v9.setenv(k, "1")
    return v9


def ask(q, prev=None, ctx=None, role="MNT"):
    return A.answer(q, role, ctx, prev=prev)


def record(q, ctx=None):
    return ask(q, ctx=ctx).pop("_followup")


def nums(t):
    return Counter(re.findall(r"\d+(?:\.\d+)?", t or ""))


# ---------------------------------------------------------------- H 띄어쓰기 (PARSE_V10)
@pytest.mark.parametrize("q, want, gone", [
    ("공기·윤활 매니폴드가뭐야?", "매니폴드", "매니폴드가뭐"),
    ("웨이 커버 그리스 이름이뭐야?", "이름", "이름이뭐"),
    ("웨이 커버 그리스를언제쓰나?", "그리스", "그리스를언제쓰나"),
    ("그리스는언제교체해?", "교체", "그리스는언제교체"),
])
def test_glued_question_word_split(all10, q, want, gone):
    words = A.content_words(q)
    assert want in words and gone not in words
    assert A.unknown_terms(q) == []


def test_glued_question_word_kept_before_v10(v9):
    """9차 전에는 붙여 쓴 낱말이 "사내 문서에 없는 개념"으로 남아 1차 문지기가 막았다 (1부 3번)."""
    assert A.unknown_terms("공기·윤활 매니폴드가뭐야?") == ["매니폴드가뭐"]


@pytest.mark.parametrize("q", ["주차장이어디야?", "월급날이언제야?"])
def test_glued_unknown_topic_stays_unknown(all10, q):
    """앞 조각이 사내 문서 낱말이 아니면 나누지 않는다 — 문서에 없는 주제는 그대로 "문서에 없음" 쪽."""
    assert A.unknown_terms(q)


def test_corpus_words_are_not_split(all10):
    """사내 문서에 있는 낱말은 묻는 말 글자("어디·얼마·몇" …)가 들어 있어도 건드리지 않는다 — 그런 낱말 전부를 본다.
    (처음에는 "앞 2글자 뒤에 묻는 말이 든 4글자 이상 낱말" 하나를 골라 보려 했으나 사내 문서에 그런 낱말이 없었다 — 시험 가정, 2026-10-13)"""
    hits = [w for w in A.corpus_words() if re.fullmatch(r"[가-힣]{2,}", w) and A.QWORD_GLUE_V10.search(w)]
    assert hits
    assert all(A.split_glued_v10(w) == [w] for w in hits)


@pytest.mark.parametrize("q, kept", [("LOTO 자물쇠는 무슨 색 쓰는 게 규정이에요?", "무슨"),
                                     ("공기 필터 나사산에 바르는 Sikaflex는 정확히 무슨 품번 써?", "무슨"),
                                     ("몇번 멈췄어", "몇번")])
def test_standalone_question_word_untouched(all10, q, kept):
    """홀로 선 묻는 말은 건드리지 않는다 — 처음 판은 "무슨·몇번"도 버렸다가, 사내 문서에 없는 "무슨"이 막아 주던 답 없는 질문
    (E3-003·E3-052·E5-010 꼴)에 답하게 되어 뺐다 (LLM 끈 비교, 2026-10-13). 원래 질문 글은 그 문항들을 줄여 옮김."""
    assert kept in A.unknown_terms(q) or kept in A.content_words(q)
    assert A.split_glued_v10(kept) == [kept]


def test_spaced_and_glued_give_same_doc_answer(all10):
    """띄어쓰기만 다른 두 질문은 같은 답을 낸다 (1부 3·4번 — 전에는 하나는 "문서에 없음", 하나는 답)."""
    a, b = ask("공기·윤활 매니폴드가뭐야?"), ask("공기·윤활 매니폴드가 뭐야?")
    assert a["status"] == b["status"] == "답변" and a["conclusion"] == b["conclusion"]


# ---------------------------------------------------------------- I 섞인 알람 질문 (FLOW_V10)
MIXED = "2075가 왜 자꾸 떠? 어제 야간 VF2-01 몇 번 멈췄어?"


def test_mixed_alarm_ops_scoped_per_clause(all10):
    a = ask(MIXED)
    ranges = {d["tool"]: d["range"] for d in a["current_data"]}
    assert ranges["알람 조회"] == "2026-09-01 ~ 2026-09-30"           # 알람 마디: 날짜가 없으니 기본 기간
    assert any("2026-09-30" in r and "야간" in r for t, r in ranges.items() if "정지" in t)   # 정지 마디: 어제 야간
    assert "VF2-02 4번" in a["conclusion"] and "알람 2075 발생: 없음" not in a["conclusion"]
    assert "정지 전체 8번 169분" in a["conclusion"]


def test_mixed_alarm_ops_bled_before_v10(v9):
    """9차 전: 둘째 마디의 날짜·설비가 알람 조회에 걸려 "발생: 없음" (1부 8번 — 같은 답 관련 줄은 "30일 4번")."""
    assert "알람 2075 발생: 없음" in ask(MIXED)["conclusion"]


@pytest.mark.parametrize("q", ["2075가 왜 자꾸 떠?", "어제 야간 VF2-01 몇 번 멈췄어?", "2075 뜨면 뭐부터 해?"])
def test_single_clause_unchanged_by_split(v9, q):
    """마디가 하나인 질문은 나누지 않는다 (FLOW_V10을 켜도 결론이 같다)."""
    before = ask(q)["conclusion"]
    v9.setenv("FLOW_V10", "1")
    assert ask(q)["conclusion"] == before


def test_split_needs_ops_in_other_clause(all10):
    p = A.parse("2075가 왜 자꾸 떠? 보충은 어떻게 해?")
    p["raw"] = "2075가 왜 자꾸 떠? 보충은 어떻게 해?"
    assert A.alarm_ops_split_v10(p["raw"], p, A.settings()) is None


# ---------------------------------------------------------------- D "원문 설명" (FLOW_V10)
def _orig_line():
    """원문은 표 칸("| 원문 설명 | … |")이고, 답에 쓰는 줄은 plain_lines 꼴("원문 설명 · …")이다."""
    return next((c, t) for c in load_corpus() if c.doc_id == "DOC-02" for t in A.plain_lines(c) if t.startswith("원문 설명 · "))


def test_original_description_stays_in_llm_candidates(all10):
    """LLM 후보 줄은 step11과 같다 — 후보 한 줄을 빼자 E7-096의 줄 고르기가 "답할 줄 없음"으로 바뀌었다(2026-10-13 빠른 확인)."""
    c, text = _orig_line()
    own = {(c.doc_id, c.section)}
    assert not A.card_line_v9(c, text, own)
    all10.setenv("FLOW_V10", "0")
    assert not A.card_line_v9(c, text, own)


def test_original_description_dropped_from_shown_lines():
    c, text = _orig_line()
    own = {(c.doc_id, c.section)}
    lc = A._line_cite(c)
    other = "증상·알람 · 다른 줄"
    assert A.drop_card_orig_v10([text, other], [lc, lc], own) == ([other], [lc])
    assert A.drop_card_orig_v10([text], [lc], own) == ([text], [lc])                 # 모두 빠지게 되면 그대로
    assert A.drop_card_orig_v10([text, other], [lc, lc], {("DOC-02", "9.9")}) == ([text, other], [lc, lc])   # 다른 알람 절은 그대로
    assert A.drop_card_orig_v10([text, other], [lc], own) == ([text, other], [lc])   # 줄마다 출처가 없으면 건드리지 않음


# ---------------------------------------------------------------- B 알람 답 "짧게" (FLOW_V10)
def test_alarm_short_is_program_reduced(all10):
    prev = record("2075가 왜 자꾸 떠?")
    a = ask("짧게 요약해", prev=prev)
    fu = a["followup"]
    assert fu["kind"] == "short" and fu["rewritten"] is False and fu.get("reduced") is True
    assert a["steps"] == prev["steps"] and len(a["steps"]) == 8          # 점검 순서는 자르지 않는다 (규칙 8절)
    assert a["current_data"] == [] and a["evidence"] == prev["evidence"]
    assert "프로그램이 줄임" in a["mode"] and "LLM" in a["mode"]
    new = nums(a["conclusion"]) - nums(prev["conclusion"])
    assert not new                                                        # 안내 글에 새 숫자 없음 (S9)
    assert len(a["conclusion"]) < len(prev["conclusion"])
    assert "MR-S-" not in a["conclusion"]                                  # 운영 목록은 빠짐


def test_alarm_short_unchanged_without_flow10(v9):
    prev = record("2075가 왜 자꾸 떠?")
    a = ask("짧게 요약해", prev=prev)
    assert a["followup"]["reason"] == "알람 설명·점검 순서" and a["conclusion"].endswith(prev["conclusion"])


def test_doc03_short_stays_as_is(all10):
    """DOC-03 답(알람 카드가 아닌 문서 줄)은 지금처럼 그대로 (B는 알람 카드만)."""
    prev = record("공기·윤활 매니폴드가 뭐야?")
    a = ask("방금 내용 짧게 요약해", prev=prev)
    assert a["followup"]["reason"] == "고장 대응·안전 작업 문서" and a["conclusion"].endswith(prev["conclusion"])


# ---------------------------------------------------------------- A "앞 답 그대로" 줄 목록 (BLOCKS_V3)
def test_same_answer_keeps_previous_blocks(all10):
    prev = record("공기·윤활 매니폴드가 뭐야?")
    a = ask("방금 내용 짧게 요약해", prev=prev)
    note = a["conclusion"][: len(a["conclusion"]) - len(prev["conclusion"])].strip()
    assert a["blocks"][0] == {"kind": "lead", "text": note}
    assert a["blocks"][1:] == prev["blocks"]


def test_same_answer_has_no_blocks_before_v10(v9):
    prev = record("공기·윤활 매니폴드가 뭐야?")
    assert "blocks" not in ask("방금 내용 짧게 요약해", prev=prev)


def test_again_keeps_previous_blocks(all10):
    prev = record("웨이 커버 그리스 이름이 뭐야?")
    a = ask("그거 한 번만 더 말해 줘", prev=prev)
    assert a["conclusion"] == prev["conclusion"] and a["blocks"] == prev["blocks"]


def test_non_answer_prev_has_no_blocks(all10):
    prev = record("주차장 어디야?")
    a = ask("방금 거 쉽게 설명해 줘", prev=prev)
    assert a["status"] == "문서에 없음" and "blocks" not in a


# ---------------------------------------------------------------- C 덩어리 제목·점검 순서 자리 (BLOCKS_V3)
def test_alarm_answer_sections_follow_guide_card_order(all10):
    a = ask("2075가 자꾸 떠?")
    secs = [b["text"] for b in a["blocks"] if b["kind"] == "section"]
    assert secs[:2] == ["알람 설명", "점검 순서 (사내 문서)"] and secs[-1] == "운영 기록 [가상]"
    kinds = [b["kind"] for b in a["blocks"]]
    assert kinds[:4] == ["section", "text", "section", "steps"]
    assert not any(re.search(r"\d", t) for t in secs)                       # 제목에 숫자 없음


def test_alarm_answer_with_a_cause_word_puts_causes_between_description_and_steps(all10):
    """2026-10-19: "왜"·"원인"을 물으면 알람 설명 → 가능한 원인 → 점검 순서 → … → 운영 기록 (test_alarm_causes.py가 자세히 본다)."""
    a = ask("2075가 왜 자꾸 떠?")
    secs = [b["text"] for b in a["blocks"] if b["kind"] == "section"]
    assert secs[:3] == ["알람 설명", "가능한 원인 (사내 문서)", "점검 순서 (사내 문서)"] and secs[-1] == "운영 기록 [가상]"
    kinds = [b["kind"] for b in a["blocks"]]
    assert kinds[:4] == ["section", "text", "section", "line"]
    assert not any(re.search(r"\d", t) for t in secs)


def test_single_group_answer_has_no_sections(all10):
    a = ask("웨이 커버 그리스 이름이 뭐야?")
    assert not any(b["kind"] in ("section", "steps") for b in a["blocks"])


def test_sections_v3_drops_group_tags():
    out = BL2.sections_v3([{"kind": "text", "text": "x", "grp": "card"}, {"kind": "line", "text": "y", "grp": "doc"}], False)
    assert all("grp" not in b for b in out) and [b["kind"] for b in out] == ["section", "text", "section", "line"]


# ---------------------------------------------------------------- F 정지 답 기준 따로 (BLOCKS_V3)
def test_stops_report_lines_separate(all10):
    a = ask("어제 야간 VF2-01 몇 번 멈췄어?")
    b = next(x for x in a["blocks"] if x["kind"] == "ops")
    assert len(b["items"]) == 5 and not any(i.startswith("교대 보고서 기준") for i in b["items"])
    assert b["notes_head"] == "교대 보고서 기준" and len(b["notes"]) == 3
    assert nums(" ".join([b["head"]] + b["items"] + b["notes"])) == nums(a["conclusion"])   # 숫자 묶음 같음 (LLM 끔 = 초안 글)


def test_stops_items_before_v10(v9):
    b = next(x for x in ask("어제 야간 VF2-01 몇 번 멈췄어?")["blocks"] if x["kind"] == "ops")
    assert len(b["items"]) == 8 and "notes" not in b


# ---------------------------------------------------------------- G 꼬리표 (BLOCKS_V3)
TR_NO = [{"job": "route", "used": True}, {"job": "select", "used": False, "reason": "답할 줄 없음(answerable=false)"}]


def test_none_mode_names_llm_jobs(all10):
    m = A.none_mode_v10(TR_NO, A.settings())
    assert m.startswith("로컬 LLM ") and "질문 분류" in m and "줄 고르기 — 답할 줄 없다고 판단" in m


def test_none_mode_rule_when_llm_not_called(all10):
    assert A.none_mode_v10([], A.settings()) == "규칙"
    assert A.none_mode_v10([{"job": "write", "used": False, "reason": "LLM 꺼짐"}], A.settings()) == "규칙"


def test_none_mode_before_v10(v9):
    assert A.none_mode_v10(TR_NO, A.settings()) == "규칙"


# ---------------------------------------------------------------- 표시 확인: BLOCKS_V3는 conclusion·status를 바꾸지 않는다
def _followup_pairs():
    d = json.loads((EVAL / "qa_followup.json").read_text(encoding="utf-8"))
    return [(it["prev"]["q"], it["q"]) for it in d["items"] if it.get("prev")]


def test_blocks_v3_changes_display_only(v9):
    """사전 등록 "표시 확인": LLM 끈 스냅숏 질문 전부 + 이어 묻기 두 번 묻기를 BLOCKS_V3 끔·켬으로 답해 결론·상태가 같다."""
    v9.setenv("PARSE_V10", "1")
    v9.setenv("FLOW_V10", "1")
    qs = list(json.loads(SNAP.read_text(encoding="utf-8")))
    seen = {}
    for flag in ("0", "1"):
        v9.setenv("BLOCKS_V3", flag)
        rows = []
        for q in qs:
            a = ask(q, role="SUP")
            rows.append((a["status"], a["conclusion"]))
        for pq, q in _followup_pairs():
            prev = ask(pq, role="SUP").pop("_followup")
            a = ask(q, prev=prev, role="SUP")
            rows.append((a["status"], a["conclusion"]))
        seen[flag] = rows
    diff = [i for i, (x, y) in enumerate(zip(seen["0"], seen["1"])) if x != y]
    assert len(seen["0"]) == len(seen["1"]) > 800 and not diff
