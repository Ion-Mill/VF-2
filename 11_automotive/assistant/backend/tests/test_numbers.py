"""값으로 비교하는 검사관 (backend/llm/numbers.py, 2026-10-10 계획 2단계 — 스위치 NUM_MATCH=value).

낱말 비교가 막던 맞는 답은 통과하고, 뜻이 바뀌는 것(세는 말 묶음 바꾸기, 물리 단위 빼기·바꾸기,
날짜 일부만 쓰기, 새 숫자)은 거부되는지 본다.
"""
import json
from pathlib import Path

from backend.llm.numbers import lead_unsupported, quantities, two_way

SNAP = Path(__file__).parent / "snapshots" / "fallback_answers.json"


def ok(text, draft):
    return two_way(text, draft) == ([], [])


def test_same_value_other_spelling():
    assert ok("OEE 65.6%", "OEE 65.60%")
    assert ok("실적 1335개", "실적 1,335개")
    assert ok("농도 7%", "농도 7.0%")
    assert ok("합계 169.0분", "합계 169분")
    assert not ok("농도 7.5%", "농도 7.0%")          # 허용 오차 없음


def test_counter_may_be_added_or_dropped_but_not_changed():
    assert ok("목표 90개", "목표 90")                 # 원문 맨숫자에 세는 말 붙이기 (C08 같은 경우)
    assert ok("정지 8, 합계 169분", "정지 8번, 합계 169분")  # 세는 말 빼기
    assert ok("정지 3회", "정지 3번")                 # 같은 묶음 {번·회·차례}
    assert not ok("정지 8개", "정지 8번")             # 다른 묶음으로 바꾸기
    assert not ok("담당 2명", "설비 2대")


def test_physical_unit_must_stay():
    assert not ok("평균 7.0", "평균 7.0분")           # 물리 단위 빼기
    assert not ok("온도 42%", "온도 42℃")            # 물리 단위 바꾸기
    assert ok("16~26도", "16~26 ℃")                  # 같은 단위의 다른 표기
    assert ok("80 psi", "80psi")


def test_unit_on_bare_number_needs_same_line():
    line = "단위: ℃ · 정상 범위: 28~42"
    assert lead_unsupported("정상 범위는 42℃까지입니다", [line]) == []       # D12 같은 경우
    assert lead_unsupported("42%까지입니다", [line]) == ["42%"]
    assert lead_unsupported("42℃까지", ["정상 범위: 28~42", "단위: ℃"]) == ["42℃"]  # 다른 줄의 단위는 안 됨
    assert lead_unsupported("목표는 90개입니다", ["교대 목표 90 + 이월"]) == []


def test_range_unit_applies_to_both_ends():
    assert [(q.value, q.unit) for q in quantities("부품 온도 16~26 ℃")] == [("16", "℃"), ("26", "℃")]
    assert [(q.value, q.unit) for q in quantities("셋업 10~20분")] == [("10", "분"), ("20", "분")]
    assert lead_unsupported("26℃ 이하에서 잰다", ["부품 온도 16~26 ℃ 를 확인"]) == []


def test_dates_times_and_ids_are_whole():
    assert ok("9월 30일 야간", "2026-09-30 야간")
    assert ok("2026년 9월 30일", "2026-09-30")
    assert ok("9/30 야간", "2026-09-30 야간")
    assert not ok("30일 야간", "2026-09-30 야간")    # 날짜 일부만 쓰기
    assert not ok("9월 29일", "2026-09-30")
    assert ok("6시 전에 확정", "06:00 전 확정")
    assert ok("오후 5시", "17:00")
    assert not ok("5시", "17:00")
    assert ok("16시간 운전", "16시간 운전")          # 시간(길이)은 시각이 아니다
    assert not ok("VF2-02 정지", "VF2-01 정지")
    assert not ok("MR-2609-008", "MR-2609-007")
    assert [q.kind for q in quantities("Haas VF-2, Mobil 1 0W-20, M6 탭")] == ["code", "num", "code", "code"]


def test_new_and_missing_numbers():
    assert two_way("정지 8번 169분, 다음 교대 3번 더", "정지 8번 169분") == ([], ["3번"])
    assert two_way("정지 8번", "정지 8번 169분") == (["169분"], [])
    assert two_way("1/2인치까지", "나사산 아래 1/2\" (13 mm)") == (["13 mm"], [])
    assert lead_unsupported("목표 95개", ["교대 목표 90 + 이월"]) == ["95개"]


def test_unit_does_not_cross_lines():
    assert [(q.value, q.unit) for q in quantities("합계 42\nA 등급")] == [("42", None)]


def test_every_snapshot_answer_passes_itself():
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    assert len(snap) >= 80
    for q, a in snap.items():
        for text in [a["conclusion"], *a.get("steps", [])]:
            assert two_way(text, text) == ([], []), q
            assert lead_unsupported(text, [text]) == [], q


# ---------------------------------------------------------------- 스위치 연결 (adapter.check_text, jobs.validate_select)
def test_check_text_switch(monkeypatch):
    from backend.llm.adapter import check_text
    draft = "2026-09-30 야간 VF2-01 정지 전체 8번 169분, 실적 1,335개, 고장 손실 약 0개(추정), 작업기록 MR-2609-007"
    text = "2026-09-30 야간 VF2-01은 모두 8 차례가 아니라 8번, 169분 멈췄고 실적은 1335개입니다. 고장 손실 약 0개(추정), 작업기록 MR-2609-007"
    text = text.replace("8 차례가 아니라 ", "")
    assert check_text(text, draft) is not None                      # 기본(token): "1,335"를 "1335"로 쓰면 거부
    monkeypatch.setenv("NUM_MATCH", "value")
    assert check_text(text, draft) is None                          # value: 같은 값의 다른 표기는 통과
    assert check_text(text.replace("8번", "8"), draft) is None      # 세는 말 빼기는 통과
    assert check_text(text.replace("8번", "8개"), draft).startswith(("빠진", "새"))       # 세는 말 묶음 바꿈
    assert check_text(text.replace("2026-09-30", "30일"), draft).startswith(("빠진", "새"))  # 날짜 일부만
    assert check_text(text + " 세 번", draft) == "한글 수사"            # 다른 검사는 그대로


def test_validate_select_switch(monkeypatch):
    from backend.llm.jobs import validate_select
    offered = [("L1", "c1", "주축 모터 온도 — 단위: ℃ · 정상 범위: 28~42"), ("L2", "c1", "교대 목표 90 + 이월")]
    out = {"answerable": True, "line_ids": ["L1"], "lead": "정상 범위는 42℃까지입니다."}
    sel, reason = validate_select(out, offered)
    assert sel is None and reason.startswith("고른 줄에 없는")     # 기본(token): D12 같은 거부
    monkeypatch.setenv("NUM_MATCH", "value")
    sel, reason = validate_select(out, offered)
    assert reason is None and sel["lines"] == [offered[0][2]]
    bad = dict(out, lead="정상 범위는 42%까지입니다.")
    assert validate_select(bad, offered)[1].startswith("고른 줄에 없는")
    goal = {"answerable": True, "line_ids": ["L2"], "lead": "목표는 90개입니다."}
    assert validate_select(goal, offered)[1] is None                # C08 같은 경우


def test_tidy_joins_korean_unit_only_when_source_has_it():
    from backend.llm.numbers import tidy
    assert tidy("1 년 동안 보관", "운영 DB 보관: 1년") == "1년 동안 보관"          # F11 같은 경우
    assert tidy("3 일반 절삭", "농도 3%") == "3 일반 절삭"                        # 원문에 "3일"이 없으면 그대로


def test_phrase_keeps_date_form_but_lead_may_reword(monkeypatch):
    from backend.llm.adapter import check_text
    monkeypatch.setenv("NUM_MATCH", "value")
    draft = "2026-09-01 ~ 2026-09-30 알람 108 발생: VF2-02 4번"
    reworded = "2026년 9월 1일부터 2026년 9월 30일까지 VF2-02에서 알람 108이 4번 났습니다."
    assert check_text(reworded, draft).startswith(("빠진", "새"))                # 다듬기: 날짜 표기를 바꾸면 거부 (C16)
    assert check_text("2026-09-01 ~ 2026-09-30, 알람 108은 VF2-02에서 4번 났습니다.", draft) is None
    assert lead_unsupported("9월 15일 주간부터", ["예: 9/15 08:00 ~ 9/16 05:00"]) == []  # 앞머리는 같은 날 표기 허용
