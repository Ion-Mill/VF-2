"""안전 영역 새로쓰기 (2026-10-14 사용자 결정 "대체 방식·단계적·엄격"): 점검 순서를 쉬운 말로 1:1 다시 쓰는 길의 엄격한 검사.

하나라도 실패하면 새 글 전부를 버리고(None) 부른 쪽이 원문만 보인다. 이 파일은 AI 없이 검사·흐름을 본다 (chat_json을 바꿔 끼움).
"""
import pytest

from backend.llm.client import LlmUnavailable
from backend.services import answer as A
from backend.services import followup_v2 as FU2

SRC = "[EMERGENCY STOP]을 누르고 전원을 끈 뒤 잠금 장치를 건다 → 5분 이상 기다린다"


@pytest.mark.parametrize("new, why", [
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 잠금 장치를 건다 → 5분 이상 기다린다", None),   # 쉬워졌지만 모든 것이 그대로
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 장치를 건다 → 5분 이상 기다린다", "안전 낱말 빠짐: 잠금"),
    ("[EMERGENCY STOP]을 눌러 전기를 끄고 잠금 장치를 건다 → 5분 이상 기다린다", "새 안전 낱말: 전기"),
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 잠금 장치를 건다 → 5분 기다린다", "빠진 조건 말: 이상"),
    ("[비상 정지]를 눌러 전원을 끄고 잠금 장치를 건다 → 5분 이상 기다린다", "[ ] 안의 글(버튼 이름 등)이 다름"),
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 잠금 장치를 건다. 5분 이상 기다린다", "순서 표시(→)가 다름"),
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 잠금 장치를 건다 → 5분 이상 기다리세요", "명령형"),   # 어떤 동사든 새 명령형은 거부
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 잠금 장치를 건다 → ①5분 이상 기다린다", "숫자 모양 글자"),
    ("[EMERGENCY STOP]을 눌러 전원을 끄고 잠금 장치를 건다 → 5분 이상 기다려도 돼요", "허락 꼴"),
    ("", "빈 글"),
])
def test_check_safe_unit(new, why):
    got = FU2.check_safe_unit_v15(new, SRC)
    assert (got is None) if why is None else (got is not None and got.startswith(why))


def test_check_safe_unit_keeps_qualified_person_mark_and_existing_order_words():
    src = "전기 측정은 자격자/HFO 작업이다"
    assert FU2.check_safe_unit_v15("전기 측정은 자격자/HFO 작업이다", src) is None
    assert FU2.check_safe_unit_v15("전기를 재는 일은 HFO 작업이다", src).startswith("표시 빠짐: 자격자")
    # 원문에 "~하세요"가 이미 있으면 그 꼴은 새로 생긴 것이 아니다
    assert FU2.check_safe_unit_v15("먼저 확인하세요", "먼저 확인하세요") is None


def _fake(monkeypatch, texts, judge=True, raise_judge=False, raise_write=False):
    calls = []

    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        calls.append(name)
        if name == "safe_simplify":
            if raise_write:
                raise LlmUnavailable("끔")
            return {"texts": texts[min(len(calls) - 1, len(texts) - 1)] if isinstance(texts[0], list) else texts}
        if raise_judge:
            raise LlmUnavailable("끔")
        return {"same_meaning": judge, "problem": "" if judge else "숫자를 바꿈"}
    monkeypatch.setattr(FU2, "chat_json", fake)
    return calls


UNITS = ["밸브를 닫는다 (5분 이상)", "[RESET]을 누르지 않는다"]


def test_write_safe_steps_ok_and_restores_values(monkeypatch):
    _fake(monkeypatch, ["밸브를 닫아요 ({{1}}분 이상)", "[{{1}}]을 누르면 안 돼요 않는다"])
    out, tr = FU2.write_safe_steps_v15(UNITS)
    assert out == ["밸브를 닫아요 (5분 이상)", "[RESET]을 누르면 안 돼요 않는다"] and tr["used"] is True


def test_write_safe_steps_rejects_everything_if_one_unit_fails(monkeypatch):
    calls = _fake(monkeypatch, ["밸브를 닫아요 ({{1}}분 이상)", "[{{1}}]을 눌러요"])   # 둘째 조각이 "않" 조건 말을 뺌
    out, tr = FU2.write_safe_steps_v15(UNITS)
    assert out is None and tr["used"] is False and "빠진 조건 말" in tr["rejected"][0]["reason"]
    assert calls.count("safe_simplify") == 2 and "safe_faith" not in calls   # 다시 요청 1번, 판정까지 가지 못함


def test_write_safe_steps_retry_can_fix_then_judge(monkeypatch):
    _fake(monkeypatch, [["밸브를 닫아요 ({{1}}분)", "[{{1}}]을 누르지 않아요"], ["밸브를 닫아요 ({{1}}분 이상)", "[{{1}}]을 누르지 않아요"]])
    out, tr = FU2.write_safe_steps_v15(UNITS)
    assert out == ["밸브를 닫아요 (5분 이상)", "[RESET]을 누르지 않아요"] and tr["tries"] == 2


def test_write_safe_steps_judge_no_or_error_or_llm_error_or_wrong_count(monkeypatch):
    ok_texts = ["밸브를 닫아요 ({{1}}분 이상)", "[{{1}}]을 누르지 않아요"]
    _fake(monkeypatch, ok_texts, judge=False)
    assert FU2.write_safe_steps_v15(UNITS)[0] is None            # 판정이 "뜻이 다르다"
    _fake(monkeypatch, ok_texts, raise_judge=True)
    assert FU2.write_safe_steps_v15(UNITS)[0] is None            # 판정을 못 받으면 쓰지 않는다 (fail closed)
    _fake(monkeypatch, ok_texts, raise_write=True)
    assert FU2.write_safe_steps_v15(UNITS)[0] is None            # LLM 오류
    _fake(monkeypatch, ["밸브를 닫아요 ({{1}}분 이상)"])
    assert FU2.write_safe_steps_v15(UNITS)[0] is None            # 조각 수가 다름
    assert FU2.write_safe_steps_v15([])[0] is None and FU2.write_safe_steps_v15([" "])[0] is None


def test_steps_easy_keeps_number_and_role_prefix_and_fails_closed(monkeypatch):
    steps = ["1 (작업자) 밸브를 닫는다 (5분 이상)", "★2 (보전 담당자) [RESET]을 누르지 않는다"]
    seen = {}

    def fake(texts):
        seen["texts"] = texts
        return ["밸브를 닫아요 (5분 이상)", "[RESET]을 누르지 않아요"], {"job": "safe_simplify", "used": True}
    monkeypatch.setattr(A.FU2, "write_safe_steps_v15", fake)
    traces = []
    assert A.safe_steps_easy_v15(steps, traces) == ["1 (작업자) 밸브를 닫아요 (5분 이상)", "★2 (보전 담당자) [RESET]을 누르지 않아요"]
    assert seen["texts"] == ["밸브를 닫는다 (5분 이상)", "[RESET]을 누르지 않는다"] and len(traces) == 1   # AI는 할 일 글만 본다
    monkeypatch.setattr(A.FU2, "write_safe_steps_v15", lambda t: (None, {"job": "safe_simplify", "used": False}))
    assert A.safe_steps_easy_v15(steps, []) is None
    # 띄어쓰기만 다른 조각은 원문 그대로 — 모두 그렇다면 None (거짓 꼬리표 없음), 하나라도 진짜 바뀌면 그 조각만 새 글
    monkeypatch.setattr(A.FU2, "write_safe_steps_v15",
                        lambda t: (["밸브를 닫는다 (5 분 이상)", "[RESET]을 누르지 않는다"], {"job": "safe_simplify", "used": True}))
    traces = []
    assert A.safe_steps_easy_v15(steps, traces) is None and traces[0]["used"] is False
    monkeypatch.setattr(A.FU2, "write_safe_steps_v15",
                        lambda t: (["밸브를 닫는다 (5 분 이상)", "[RESET]을 누르면 안 된다 않는다"], {"job": "safe_simplify", "used": True}))
    assert A.safe_steps_easy_v15(steps, []) == ["1 (작업자) 밸브를 닫는다 (5분 이상)", "★2 (보전 담당자) [RESET]을 누르면 안 된다 않는다"]
    traces = []
    assert A.safe_steps_easy_v15(["머리 없는 글"], traces) is None and "읽지 못해" in traces[0]["reason"]


def test_switches_default_off_and_response_has_no_steps_easy():
    s = A.settings()
    assert not (s.safe_write_card or s.safe_write_doc or s.safe_write_proc or s.safe_write_words)
    a = A.answer("알람 2075 점검 순서 알려줘", "MNT")
    assert a["steps"] and "steps_easy" not in a


# ── 2~4단계 (2026-10-14): DOC-03·05 줄(SAFE_WRITE_DOC)·절차 줄(SAFE_WRITE_PROC)·안전 낱말 줄(SAFE_WRITE_WORDS) ──
from dataclasses import replace  # noqa: E402


def _s(**kw):
    base = replace(A.settings(), llm_enabled=True, llm_jobs=frozenset({"write"}), doc_write=True,
                   parse_v2=True, parse_v3=True, parse_v4=True, parse_v5=True, parse_v6=True, parse_v7=True, parse_v8=True)   # v8_on은 앞 스위치 위에서만 켜진다
    return replace(base, **kw)


def _c(doc, sec):
    return {"doc_id": doc, "section": sec}


@pytest.mark.parametrize("flags, lines, cites, procedure, want", [
    ({}, ["그리스 · 이름"], [_c("DOC-04", "4.5")], False, "plain"),                                        # 스위치 없이도 지금 새로쓰기는 그대로
    ({}, ["알람 설명"], [_c("DOC-03", "2.1")], False, None),                                               # DOC-03은 스위치가 꺼져 있으면 뺀다
    ({"safe_write_doc": True}, ["알람 설명"], [_c("DOC-03", "2.1")], False, "safe"),                          # 2단계
    ({"safe_write_doc": True}, ["케이블을 본다"], [_c("DOC-03", "2.1")], False, None),                       # 안전 낱말 줄은 4단계가 필요
    ({"safe_write_doc": True, "safe_write_words": True}, ["케이블을 본다"], [_c("DOC-03", "2.1")], False, "safe"),
    ({"safe_write_words": True}, ["전기 측정은 자격자 작업"], [_c("DOC-04", "2.1")], False, "safe"),          # 4단계 (DOC-04 안전 낱말 줄)
    ({"safe_write_doc": True, "safe_write_words": True}, ["잠금 단계"], [_c("DOC-05", "2.1")], False, "safe"),   # 2026-10-14 사용자 요청: §2 잠금·표지 절차도 새로쓰기 대상(엄격 검사)
    ({"safe_write_doc": True, "safe_write_words": True}, ["차단 지점 표"], [_c("DOC-05", "3.1")], False, None),
    ({"safe_write_doc": True, "safe_write_words": True}, ["보호구"], [_c("DOC-05", "5")], False, None),
    ({"safe_write_doc": True, "safe_write_words": True}, ["서식"], [_c("DOC-05", "7")], False, None),
    ({"safe_write_doc": True, "safe_write_words": True}, ["고전압 표시등이 5분 꺼짐"], [_c("DOC-05", "4.1")], False, "safe"),   # 2026-10-14 사용자 요청: 고전압 줄도 새로쓰기 대상(엄격 검사)
    ({"safe_write_doc": True}, ["전기 작업의 범위"], [_c("DOC-05", "4.1")], False, "safe"),                  # 고정 서식이 아닌 DOC-05 §4 (안전 낱말 "전기" 때문에 4단계도 필요)
    ({"safe_write_doc": True, "safe_write_words": True}, ["a"], [_c("DOC-04", "2")], True, None),           # 절차는 새로쓰기 길이 아니라 3단계 1:1 길
])
def test_doc_write_mode(flags, lines, cites, procedure, want):
    mode = A.doc_write_mode_v15(_s(**flags), lines, cites, None, procedure)
    if want == "safe" and flags.get("safe_write_doc") and not flags.get("safe_write_words") and A.FU2.is_safety(lines[0]):
        want = None
    assert mode == want


def test_doc_write_mode_off_when_exclude_or_empty_or_switch_off():
    assert A.doc_write_mode_v15(_s(), ["x"], [_c("DOC-04", "1")], {"c"}, False) is None            # 알람 + 문서(카드 길)
    assert A.doc_write_mode_v15(_s(), [], [], None, False) is None
    assert A.doc_write_mode_v15(_s(doc_write=False), ["x"], [_c("DOC-04", "1")], None, False) is None
    assert A.doc_write_mode_v15(_s(), ["x", "y"], [_c("DOC-04", "1")], None, False) is None      # 줄마다 출처가 없으면 안 씀


@pytest.mark.parametrize("answer, why", [
    ("케이블 점검은 자격자가 해요. 먼저 전원을 꺼야 해요", None),
    ("점검은 자격자가 해요. 먼저 전원을 꺼야 해요", "안전 낱말 빠짐: 케이블"),
    ("케이블 점검은 자격자가 해요", "조건 말 빠짐: 먼저"),
    ("케이블 점검을 하세요. 먼저 전원을 꺼야 해요", "표시 빠짐: 자격자"),
])
def test_check_answer_safe(answer, why):
    lines = ["케이블 점검은 자격자 작업이다", "먼저 전원을 끈다"]
    got = FU2.check_answer_safe_v15(answer, lines)
    assert (got is None) if why is None else (got is not None and got.startswith(why))
    assert FU2.check_answer_safe_v15("케이블 점검은 자격자가 하세요. 먼저 전원을 꺼요", lines + ["하세요"]) is None   # 원문에 있는 꼴은 통과


def test_write_doc_answer_safe_flag_adds_the_check(monkeypatch):
    lines = ["케이블 점검은 자격자 작업이다"]

    def fake(messages, schema, name, max_tokens=400, s=None, grammar=None):
        if name == "write_answer":
            return {"answer": "점검은 자격자가 해요."}   # 케이블이 빠짐
        return {"faithful": True, "problem": ""}
    monkeypatch.setattr(FU2, "chat_json", fake)
    assert FU2.write_doc_answer("케이블 점검은 누가 해?", lines, safe=False)[0] is not None
    out, tr = FU2.write_doc_answer("케이블 점검은 누가 해?", lines, safe=True)
    assert out is None and "안전 낱말 빠짐: 케이블" in tr[0]["rejected"][0]["reason"]


def test_safe_lines_easy_rewrites_cell_values_only(monkeypatch):
    lines = ["6.1 — 할 일: 운전을 멈춘다 · 누가: 작업자", "한 줄 글"]
    seen = {}

    def fake(texts):
        seen["texts"] = texts
        return ["운전을 멈춘다", "작업자", "한 줄 글"][:len(texts)] and ["운전을 멈춰요", "작업자", "한 줄 글"], {"job": "safe_simplify", "used": True}
    monkeypatch.setattr(A.FU2, "write_safe_steps_v15", fake)
    got = A.safe_lines_easy_v15(lines, [])
    assert got == ["6.1 — 할 일: 운전을 멈춰요 · 누가: 작업자", "한 줄 글"]            # 머리·칸 이름은 그대로, 값 글만
    assert seen["texts"] == ["운전을 멈춘다", "작업자", "한 줄 글"]
    monkeypatch.setattr(A.FU2, "write_safe_steps_v15", lambda t: (list(t), {"job": "safe_simplify", "used": True}))
    traces = []
    assert A.safe_lines_easy_v15(lines, traces) is None and traces[0]["used"] is False   # 하나도 안 바뀌면 보내지 않음
