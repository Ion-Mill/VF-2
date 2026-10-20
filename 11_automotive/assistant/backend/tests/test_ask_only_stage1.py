"""질문대로 답하기 1단계 (2026-10-21) 시험 — 진짜 `claude`·네트워크·DB를 부르지 않는다 (가짜 백엔드·LLM 끔).

계기: 시연 채팅 #1 (261003_창민/시연_채팅_질문테스트지_20261021.md)에서 두 질문이 질문과 다른 답을 냈다.
 ① "2075 알람이 이번 주 세 번째인데, 지난 두 번 조치가 뭐였어?" → 알람 설명 카드(지난 조치 없음). 작업기록 규칙이 `지난\\s*조치`만 잡았다.
 ② "축 윤활유 재고는 안전 재고보다 얼마나 부족해?" → 부족 품목 전체. 품목 필터와 부족분 계산이 없었다.
지키는 것: 지난 조치 N건(최근 것부터, 조치 원문 그대로)·카드 없음, 카드가 묻는 말이 같이 있으면 카드도, 재고는 질문의 품목만 + 프로그램이 계산한 부족분,
조회 머리 줄의 "■ " 표지(소제목 바로 뒤가 아닐 때만 — 알람 카드가 깨지지 않게).
"""
import pytest

from backend.chat_mapping import to_answer_text
from backend.repositories import backend_tools as BT
from backend.services import answer as A
from backend.tests.fake_backend import FakeBackend
from backend.tests.test_alarm_causes import APP_ON

ALL = {"equipment_status", "alarms", "kpi", "production", "lot", "work_orders", "work_records", "pm_due", "tool_life", "inventory",
       "reliability", "stop_reasons", "sensor_trend", "equipment_spec"}
Q1 = "2075 알람이 이번 주 세 번째인데, 지난 두 번 조치가 뭐였어?"
Q2 = "축 윤활유 재고는 안전 재고보다 얼마나 부족해?"

# 실제 공용 DB의 재고 값 (2026-10-21 읽기 전용 조회). 단위·안전 재고 모양을 맞춘다
INVENTORY = [
    {"item_no": "CS-AFLT", "item_name": "공기 필터", "category": "CONSUMABLE", "unit": "개", "on_hand_qty": 2.0, "safety_stock": 2.0, "is_low": True, "shipped_7d": 0.0},
    {"item_no": "CS-GRS", "item_name": "그리스", "category": "CONSUMABLE", "unit": "개", "on_hand_qty": 2.0, "safety_stock": 2.0, "is_low": True, "shipped_7d": 0.0},
    {"item_no": "CS-SLUB", "item_name": "주축 윤활유", "category": "CONSUMABLE", "unit": "L", "on_hand_qty": 7.63, "safety_stock": 4.0, "is_low": False, "shipped_7d": 0.0},
    {"item_no": "CS-WLUB", "item_name": "축 윤활유", "category": "CONSUMABLE", "unit": "L", "on_hand_qty": 3.6, "safety_stock": 4.0, "is_low": True, "shipped_7d": 0.0},
    {"item_no": "TL-TAP6", "item_name": "M6 탭", "category": "TOOL", "unit": "개", "on_hand_qty": 6.0, "safety_stock": 8.0, "is_low": True, "shipped_7d": 0.0},
    {"item_no": "FG-BRK-A100", "item_name": "BRK-A100 완제품", "category": "FG", "unit": "개", "on_hand_qty": 175.0, "safety_stock": None, "is_low": False, "shipped_7d": 0.0},
]
# 실제 공용 DB의 2075 작업기록 모양 (9/29 VF2-02, 9/30 VF2-01) — 가짜 백엔드는 최근 것부터 준다
WORK_RECORDS = [
    {"record_no": "MR-S-0959", "record_type": "SIMPLE", "equipment_id": "VF2-01", "alarm_code": "2075", "cause": "", "repair_min": 12,
     "action": "저장소 수위를 확인하고 알람을 지움. 보충은 예방 정비(2.3 윤활유 저장소 양 점검·보충) 때 하기로 함", "confirmed_at": "2026-09-30T11:16:00+09:00"},
    {"record_no": "MR-S-0957", "record_type": "SIMPLE", "equipment_id": "VF2-02", "alarm_code": "2075", "cause": "", "repair_min": 7,
     "action": "저장소 수위를 확인하고 알람을 지움. 보충은 예방 정비(2.3 윤활유 저장소 양 점검·보충) 때 하기로 함", "confirmed_at": "2026-09-29T23:24:00+09:00"},
    {"record_no": "MR-S-0946", "record_type": "SIMPLE", "equipment_id": "VF2-02", "alarm_code": "2075", "cause": "필터 막힘", "repair_min": 10,
     "action": "필터를 교체", "confirmed_at": "2026-09-24T02:17:00+09:00"},
]


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")


@pytest.fixture
def real_like(monkeypatch):
    """conftest의 기본 가짜 백엔드 대신 실제 DB 모양 자료를 꽂는다."""
    fake = FakeBackend(rows={"inventory": INVENTORY, "work_records": WORK_RECORDS}).install(monkeypatch)
    with BT.acting_as("U07", ALL):
        yield fake


def ask(q, ctx=None, role="MNT"):
    a = A.answer(q, role, ctx if ctx is not None else {"new_chat": "1"})
    a.pop("_followup", None)
    return a


# ---------------------------------------------------------------- 질문 해석
@pytest.mark.parametrize("q,n", [
    (Q1, 2), ("2075 지난 3번 조치 알려줘", 3), ("2075 지난 2건 조치 보여줘", 2), ("2075 지난 한 번 조치가 뭐였어?", 1), ("2075 지난 조치 알려줘", 2),
    ("2075 지난번 조치는?", 2), ("2075 전에 조치한 거 뭐야", 2), ("2075 이전 조치 기록 보여줘", 2), ("2075 전에는 어떻게 고쳤어?", 2),
    ("2075 예전에 어떻게 처리했어?", 2), ("2075 지난 15번 조치", 10),
])
def test_past_action_question_is_read_with_its_count(q, n):
    p = A.parse(q)
    assert p["past_n"] == n, p
    assert "work_records" in p["intents"], p


@pytest.mark.parametrize("q", ["지난 고장 대응 매뉴얼 알려줘", "2075 조치 방법은?", "992 뜨면 뭐부터 해?", "2075가 뭐야?", "지난 교대 필수 정지 손실은?", "2075 몇 번 났어?"])
def test_other_questions_are_not_read_as_past_action(q):
    assert A.parse(q).get("past_n") is None


# ---------------------------------------------------------------- 지난 조치 답
def test_q1_answers_the_last_two_records_without_the_default_card(real_like):
    a = ask(Q1)
    t = to_answer_text(a)
    assert "MR-S-0959" in t and "MR-S-0957" in t and "MR-S-0946" not in t                       # 최근 2건
    assert t.index("MR-S-0959") < t.index("MR-S-0957")                                           # 최근 것부터
    assert t.count("저장소 수위를 확인하고 알람을 지움. 보충은 예방 정비(2.3 윤활유 저장소 양 점검·보충) 때 하기로 함") == 2   # 조치 원문 그대로
    assert "■ 알람 2075 지난 조치 (최근 2건)" in t
    for gone in ("■ 알람 설명", "■ 점검 순서", "최근 7일", "30일"):                              # 기본 카드·횟수 줄이 없다
        assert gone not in t, gone
    assert a["related"] is None and a["steps"] == []
    assert a["status"] == "답변" and a["is_synthetic"] is True


def test_count_in_the_question_sets_how_many_records(real_like):
    one = to_answer_text(ask("2075 지난 한 번 조치가 뭐였어?"))
    assert "MR-S-0959" in one and "MR-S-0957" not in one and "(최근 1건)" in one
    three = to_answer_text(ask("2075 지난 3번 조치 알려줘"))
    assert all(x in three for x in ("MR-S-0959", "MR-S-0957", "MR-S-0946")) and "원인 필터 막힘" in three and "(10분)" in three


def test_equipment_in_the_question_filters_the_records(real_like):
    t = to_answer_text(ask("VF2-02 2075 지난 두 번 조치가 뭐였어?"))
    assert "MR-S-0957" in t and "MR-S-0946" in t and "MR-S-0959" not in t and "VF2-02 알람 2075 지난 조치" in t


def test_no_records_says_so_instead_of_a_card(real_like):
    t = to_answer_text(ask("992 지난 조치 알려줘"))
    assert "확정된 작업기록이 없습니다" in t and "■ 알람 설명" not in t


def test_when_the_question_also_asks_for_the_card_both_come(real_like):
    t = to_answer_text(ask("2075 지난 두 번 조치랑 점검 순서 알려줘"))
    assert "■ 알람 설명" in t and "■ 점검 순서" in t and "MR-S-0959" in t


def test_a_plain_alarm_question_still_gets_the_card(real_like):
    """기본 카드를 없애는 일은 2·3단계 — 1단계는 지난 조치만 물은 질문의 카드만 뺀다."""
    t = to_answer_text(ask("2075가 뭐야?"))
    assert "■ 알람 설명" in t and "■ 점검 순서" in t and "MR-S-0959" not in t


# ---------------------------------------------------------------- 재고
def test_q2_answers_only_the_asked_item_with_the_computed_shortfall(real_like):
    a = ask(Q2)
    t = to_answer_text(a)
    assert "축 윤활유 3.6 L, 안전 재고 4 L보다 0.4 L 부족해요." in t
    for other in ("공기 필터", "그리스", "M6 탭", "주축 윤활유"):
        assert other not in t, other
    assert t.startswith("■ 재고 확인\n1. ")
    assert a["status"] == "답변"


def test_longer_item_name_wins_over_the_name_inside_it(real_like):
    t = to_answer_text(ask("주축 윤활유 재고는 안전 재고보다 얼마나 남았어?"))
    assert "주축 윤활유 7.63 L, 안전 재고 4 L보다 3.63 L 많아요." in t and "축 윤활유 3.6" not in t


def test_item_at_the_safety_stock_has_zero_shortfall(real_like):
    t = to_answer_text(ask("그리스 재고는 안전 재고보다 얼마나 부족해?"))
    assert "그리스 2개, 안전 재고 2개 — 같아서 부족분은 0이에요" in t


def test_two_items_in_one_question(real_like):
    t = to_answer_text(ask("그리스랑 M6 탭 재고 얼마나 부족해?"))
    assert "그리스 2개" in t and "M6 탭 6개, 안전 재고 8개보다 2개 부족해요." in t and "축 윤활유" not in t


def test_item_without_a_safety_stock(real_like):
    t = to_answer_text(ask("완제품 재고 얼마나 있어?"))
    assert "BRK-A100 완제품 175개 (안전 재고 기준이 없습니다)." in t


def test_without_an_item_the_short_list_is_as_before(real_like):
    t = to_answer_text(ask("재고 부족한 거 알려줘"))
    assert "공기 필터 2개" in t and "축 윤활유 3.6L" in t and "M6 탭 6개" in t and "주축 윤활유" not in t and "완제품" not in t
