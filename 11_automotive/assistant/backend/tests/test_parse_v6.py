"""규칙 보강 5차 시험 (PARSE_V6, 2026-10-11 — research_notes/로컬 LLM 연결/앞단개선5_계획_20261011.md 1절 표 S1′·S2′·L1~L6).
봉인 시험 E4를 공개한 뒤 찾은 원인(본 세트)과 원문 이름 고침 때 찾은 근소 동점마다, 고친 동작과 반대 사례(바뀌면 안 되는 것)를
함께 본다. LLM을 끈 판(v6-fallback)으로 본다 — 실제 LLM 서버 없이."""
from datetime import date

import pytest

from backend.services import answer as A


@pytest.fixture
def v5(monkeypatch):
    for k in ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5"):
        monkeypatch.setenv(k, "1")


@pytest.fixture
def v6(v5, monkeypatch):
    monkeypatch.setenv("PARSE_V6", "1")


def ask(q, ctx=None):
    return A.answer(q, "SUP", ctx)


# ---------------------------------------------------------------- 기본값이면 예전과 같다
def test_switch_off_keeps_v5_behaviour(v5):
    a = ask("T05 공구 수명 카운터 0으로 초기화 좀 해 줄래?")          # E4-008: V5에서는 데이터가 나갔다
    assert a["status"] == "답변" and a["current_data"]
    assert not A.request_form_v5("T05 공구 수명 카운터 0으로 초기화 좀 해 줄래?")


# ---------------------------------------------------------------- S1′ 물음표가 붙은 부탁 꼴 (E4-008)
@pytest.mark.parametrize("q", ["T05 공구 수명 카운터 0으로 초기화 좀 해 줄래?", "보류 풀어 줄래?", "알람 리셋해 주실래요?",
                               "작업지시 승인해 주시겠어요?", "이 기록 지워 줄 수 있어?"])
def test_S1_ask_forms_are_refused(v6, q):
    a = ask(q)
    assert a["status"] == "안내" and not a["current_data"], (q, a["conclusion"])


@pytest.mark.parametrize("q", ["공구 수명은 어떻게 초기화해 줄 수 있어?",     # 의문사가 있으면 묻는 말이다
                               "몇 번 났는지 알려 줄래?", "공구 수명 알려 줄 수 있어?", "어제 실적 보여 주실래요?"])
def test_S1_questions_and_info_requests_are_not_refused(v6, q):
    assert not A.request_form_v6(q), q
    assert ask(q)["status"] != "안내", q


# ---------------------------------------------------------------- S2′ 1차 문지기 답 종류 검사 (E4-084)
def test_S2_first_gate_refuses_missing_phone_number(v6):
    a = ask("잠금 표지에 적을 야간 보전 담당자 전화번호 좀 알려 줘")
    assert a["status"] == "문서에 없음"


def test_S2_keeps_questions_that_do_not_ask_those_values(v6):
    a = ask("표지에 무엇을 적어?")                                   # 전화번호를 묻지 않는다 → 그대로 답
    assert a["status"] == "답변" and "전화번호" in a["conclusion"]
    assert A.first_gate_type_ok_v6("절삭유 농도 값이 몇이야?", "농도는 6~8%로 맞춘다")   # 측정값 "값이"는 가격으로 보지 않는다
    assert not A.first_gate_type_ok_v6("필터 가격이 얼마야?", "필터는 매월 청소한다")
    assert A.first_gate_type_ok_v6("몇 시에 교대해?", "주간 08:00~17:00")


# ---------------------------------------------------------------- L1 세척기 과열 (E4-036)
def test_L1_washer_overheat_without_id_is_the_alarm(v6):
    p = A.parse("세척기 과열로 서면 몇 도에서 멈추고 몇 도까지 식어야 다시 돌아가요?")
    assert [a["code"] for a in p["alarms"]] == ["WSH-01"] and "WSH-01" not in p["equipment"]
    a = ask("세척기 과열로 서면 몇 도에서 멈추고 몇 도까지 식어야 다시 돌아가요?")
    assert "75" in a["conclusion"] and "69" in a["conclusion"] and not a["current_data"]


@pytest.mark.parametrize("q", ["어제 세척기 몇 번 멈췄어?", "세척기 온도 기준이 뭐야?", "세척기 과열로 몇 번 섰어?"])
def test_L1_other_washer_questions_unchanged(v5, monkeypatch, q):
    before = A.parse(q)
    monkeypatch.setenv("PARSE_V6", "1")
    assert A.parse(q) == before, q


# ---------------------------------------------------------------- L2 "지난달 N일" (E4-040)
def test_L2_last_month_day(v6):
    p = A.parse("지난달 18일 주간에 세척기 멈춘 횟수랑 시간 좀 알려 주세요")
    assert (p["start"], p["end"], p["shift"]) == (date(2026, 9, 18), date(2026, 9, 18), "D")


@pytest.mark.parametrize("q, want", [("지난달 세척기 몇 번 멈췄어?", (date(2026, 9, 1), date(2026, 9, 30))),
                                     ("지난달 31일 세척기 몇 번 멈췄어?", (date(2026, 9, 1), date(2026, 9, 30)))])  # 9월 31일은 없다 → 한 달
def test_L2_other_last_month_forms(v6, q, want):
    p = A.parse(q)
    assert (p["start"], p["end"]) == want, q


# ---------------------------------------------------------------- L3 알람 이름의 조사·어미 (E4-033)
def test_L3_alarm_name_without_particle_and_ending(v6):
    assert [a["code"] for a in A.parse("공구 부하 초과 알람 지난달에 몇 번 떴어?")["alarms"]] == ["174"]
    assert A.parse("공구 부하 초과 지난달에 몇 번 떴어?")["alarms"] == []      # "알람·경보"가 없으면 이름으로 찾지 않는다


def test_L3_v5_forms_still_match(v6):
    assert [a["code"] for a in A.parse("축 서보 과부하 알람 9월에 몇 번")["alarms"]] == ["108"]


# ---------------------------------------------------------------- L4 마디별 정의 판정 (E4-030)
def test_L4_ops_clause_survives_definition_clause(v6):
    q = "축 윤활유 저장소 비워짐 알람 한 달 새 몇 번 났어요? 그리고 몇 번 나면 반복 알람으로 잡혀요?"
    p = A.parse(q)
    assert "alarm_count" in p["intents"]
    a = ask(q)
    assert "VF2-02 4번" in a["conclusion"] and "7일 안에 3번" in a["conclusion"]


@pytest.mark.parametrize("q", ["반복 알람은 몇 번 나면 잡혀?", "필수 정지가 뭐야?", "재공 경고 기준은?"])
def test_L4_single_definition_questions_unchanged(v6, q):
    assert A.parse(q)["intents"] == [], q


# ---------------------------------------------------------------- L5 알람 + 조임 값 (E4-038)
def test_L5_torque_value_line_is_added(v6):
    a = ask("6302 떠서 톱날 갈았는데 고정 볼트는 몇으로 조여?")
    assert "40 ft-lbs" in a["conclusion"]


def test_L5_torque_missing_is_document_absent(v6):
    a = ask("992 뜨면 서보 모터 고정 볼트는 몇으로 조여?")                 # 992 문서 칸에는 토크 값이 없다
    assert a["status"] == "문서에 없음" and "조임 값" in a["conclusion"]


def test_L5_other_alarm_value_questions_unchanged(v5, monkeypatch):
    """조임 값이 아닌 값 질문은 V6가 바꾸지 않는다. 처음에는 E2-034를 흉내 낸 "552 알람 떴는데 절삭유 펌프 정상 전압이 몇 볼트예요?"
    → "120 VAC"로 적었는데 실패했다 — V5에서도 같은 "문서에 없음"이라 **시험 가정이 틀린 것**이다(실제 E2-034는 화면 알람 991
    문맥의 팬 전압 질문이고, "120 VAC"는 LLM을 켠 판의 답이다, 2026-10-11). 그래서 V5와 V6의 답이 같은지 본다."""
    qs = [("552 떴는데 CB3 차단기 용량이 몇 암페어예요?", None),                                  # E3-065 (4차 → 문서에 없음)
          ("이거 팬 점검할 때 정상 전압이 몇 볼트예요?", {"screen": "SCR-09", "alarm_key": "991"})]   # E2-034
    before = [(ask(q, c)["status"], ask(q, c)["conclusion"]) for q, c in qs]
    monkeypatch.setenv("PARSE_V6", "1")
    assert [(ask(q, c)["status"], ask(q, c)["conclusion"]) for q, c in qs] == before
    assert before[0][0] == "문서에 없음"


# ---------------------------------------------------------------- L6 근소 동점 (E088)
def test_L6_near_tie_second_candidate(v6):
    a = ask("에어건 출구 압력은 얼마 이하로 써야 하나요?")
    assert a["status"] == "답변" and "0.2 MPa" in a["conclusion"]


def test_L6_off_is_document_absent(v5):
    assert ask("에어건 출구 압력은 얼마 이하로 써야 하나요?")["status"] == "문서에 없음"   # 원문 이름 고침 뒤 V5에서는 근소 동점으로 막힘
