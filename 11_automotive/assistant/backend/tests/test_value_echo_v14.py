"""10차 보강 (2026-10-14, 사용자 결정 "이름 되풀이 + 열거 이름 빠짐 · 스위치 없이 바로 고침"): 값 없는 새 답을 코드가 막는다.

복사본 시험 "OEE 예시 PQ·GQ·RQ 각각 얼마" 질문에서 새로 쓴 답 "PQ는 PQ이고, GQ는 GQ, 그리고 QBR은 …"(RQ 없음)이 따로 판정을 지났다.
판정 AI에 지시를 더하지 않고(답 거부가 늘었던 전례) 코드가 두 꼴만 좁게 본다 — 걸리면 한 번 다시 쓰게 하고, 안 되면 원문 줄로 돌아간다.
"""
import pytest

from backend.services import followup_v2 as FU2

LINES = ["PQ · 46개", "GQ · 45개", "RQ · 0개"]
Q = "OEE 계산 예시에서 PQ, GQ, RQ 값이 각각 얼마야?"


@pytest.mark.parametrize("answer, hit", [
    ("PQ는  PQ이고, GQ는 GQ예요.", "PQ"),               # 값 자리에 이름 되풀이 (두 칸 띄움 — 자리표 되채우기 흔적)
    ("PQ는 PQ이고 GQ는 45개예요.", "PQ"),
    ("PQ는 46개, GQ는 45개, RQ는 0개예요.", None),
    ("PQ가 46개이고 GQ는 45개예요.", None),             # 같은 이름이 다시 나오지만 값이 따로 있음
    ("MTBF는 평균 고장 간격이에요.", None),
])
def test_echo_name(answer, hit):
    assert FU2.echo_name_v14(answer, " ".join(LINES), Q) == hit


def test_echo_name_allowed_for_english_name_question_and_source_phrase():
    assert FU2.echo_name_v14("OEE는 OEE예요.", "OEE 설비종합효율", "OEE 영어 이름이 뭐야?") is None   # 영어 이름 질문의 맞는 답
    assert FU2.echo_name_v14("OEE는 OEE예요.", "OEE는 OEE라고 쓴다", "OEE가 뭐야?") is None            # 원문 줄에 같은 꼴
    assert FU2.echo_name_v14("OEE는 OEE예요.", "OEE 설비종합효율", "OEE가 뭐야?") == "OEE"


@pytest.mark.parametrize("q, names", [
    (Q, ["PQ", "GQ", "RQ"]),
    ("MTTR와 MTBF 차이가 뭐예요?", ["MTTR", "MTBF"]),
    ("MTTR/MTBF가 뭐야", ["MTTR", "MTBF"]),
    ("PQ하고 GQ 알려 줘", ["PQ", "GQ"]),
    ("OEE가 뭐야?", []),                                # 이름 하나는 나열이 아님
    ("VF2-01, VF2-02 상태 알려 줘", []),                # 설비 ID는 이름 나열이 아님
    ("2075 알람이 왜 떠?", []),
])
def test_listed_names(q, names):
    assert FU2.listed_names_v14(q) == names


def test_missing_listed_names():
    assert FU2.missing_listed_v14("PQ는 46개, GQ는 45개예요.", Q) == "RQ"
    assert FU2.missing_listed_v14("PQ는 46개, GQ는 45개, RQ는 0개예요.", Q) is None
    assert FU2.missing_listed_v14("PQ 46개", "OEE가 뭐야?") is None
    assert FU2.missing_listed_v14("RQ2는 아니에요", "RQ, GQ 뭐야") == "RQ"       # RQ2는 RQ가 아님 (뒤 경계)


def test_check_answer_rejects_value_less_answers_but_not_good_ones():
    bad = FU2.check_answer_v11("문서에 따르면 PQ는  PQ이고, GQ는 GQ예요.", LINES, {0, 1}, question=Q)
    assert bad is not None and bad.startswith("값 자리에 이름을 되풀이함")
    miss = FU2.check_answer_v11("PQ는 46개, GQ는 45개예요.", LINES, {0, 1}, question=Q)
    assert miss is not None and miss.startswith("질문이 나열한 이름이 답에 없음")
    assert FU2.check_answer_v11("PQ는 46개, GQ는 45개, RQ는 0개예요.", LINES, {0, 1, 2}, question=Q) is None
    # 질문을 안 주면 나열 검사는 하지 않는다 (이름 되풀이만 본다)
    assert FU2.check_answer_v11("PQ는 46개, GQ는 45개예요.", LINES, {0, 1}) is None
    assert FU2.check_answer_v11("PQ는 PQ이고요.", LINES, {0}) is not None
