"""알람 건수 말투·번호 없는 건수·"이번 달"·로트 상태 한글·설비 상태 값 표의 "N분째" (2026-10-25 AWS 점검 보고 후속) 최소 시험 — 진짜 Claude·네트워크·DB를 부르지 않는다.

문제: ① "어제 알람 몇 번 떴어?"가 조회 도구 길에서 번호를 되묻고, "몇 개 / 건수 / 횟수 / 얼마나 떴어"는 문서 길로 가 "찾지 못했어요"였다 ② 로트 답에 DB 코드(IN_PROCESS)가 그대로 나왔다
③ 설비 상태 값 표에 "몇 분째"가 없고(가동 중 설비는 시각도 없음) 지시문이 묻지 않은 설비까지 나열시켰다.
지키는 것: 번호가 없으면 기간 안 전체 건수(설비를 말하면 그 설비), 번호가 있으면 그 번호, 기준·방법을 묻는 말은 건수가 아니다 / 로트는 공식 한글 이름(DB 시드와 같음) / 모든 설비 줄에 시작 시각과 N분째.
"""
import re
from datetime import date
from pathlib import Path

import pytest

from backend.repositories import backend_tools as BT
from backend.services import answer as A
from backend.services import lookup_turn as LT
from backend.services import sim_clock as SC
from backend.tests.fake_backend import FakeBackend
from backend.tests.test_anchor_clock import _answer_text, _count_answer, _own_backend, flags, live      # noqa: F401  (flags·live는 시험 도우미)
from backend.tools import query_tools as T

COUNT_Q = ["어제 알람 몇 건이야?", "10월에 알람 몇 건 있었어?", "어제 알람 몇 개 떴어?", "알람 건수 알려줘", "10월 알람 횟수 알려줘", "어제 알람 얼마나 떴어?",
           "경보 몇 개 났어?", "오늘 알람 몇 번 났어?", "어제 알람 몇 번 떴어?", "이번 달 알람 몇 번이나 떴어?", "알람 몇 건 있었어?"]
NOT_COUNT_Q = ["알람 몇 건 이상이면 보고해?", "알람 몇 개 이상이면 반복 알람이야?", "알람 건수 집계 기준은?", "알람 횟수는 어떻게 세?", "작업지시서 몇 건이야?"]


# ------------------------------------------------------------------ 말투
@pytest.mark.parametrize("q", COUNT_Q)
def test_count_phrasings_are_alarm_count(flags, live, q):
    assert "alarm_count" in A.parse(q)["intents"], q


@pytest.mark.parametrize("q", NOT_COUNT_Q)
def test_rule_and_threshold_questions_are_not_counts(flags, live, q):
    assert "alarm_count" not in A.parse(q)["intents"], q


def test_this_month_is_the_month_of_the_clock_and_old_behavior_without_a_clock(flags, monkeypatch):
    p = A.parse("이번 달 알람 몇 번이나 떴어?")
    assert p["start"] is None and p["end"] is None      # 시계 없음: 10월은 기록 밖이라 예전처럼 날짜 없음
    monkeypatch.setattr(SC, "current", lambda: __import__("backend.tests.test_anchor_clock", fromlist=["clock"]).clock())
    p = A.parse("이번 달 알람 몇 번이나 떴어?")
    assert p["start"] == date(2026, 10, 1) and p["end"] == SC.data_period()[1]


# ------------------------------------------------------------------ 번호 없는 건수 — 규칙 길
@pytest.mark.parametrize("q", ["어제 알람 몇 개 떴어?", "알람 건수 알려줘 어제", "어제 알람 얼마나 떴어?", "어제 알람 몇 번 떴어?", "어제 알람 몇 건이야?"])
def test_total_count_is_answered_for_every_phrasing(flags, live, monkeypatch, q):
    out, fb = _count_answer(monkeypatch, q)
    text = _answer_text(out)
    assert out["status"] == "답변" and "알람 5건" in text and "VF2-01 3건" in text and "알람 번호" not in text, text       # 가짜 백엔드: VF2-01 3건 + VF2-02 2건


def test_a_code_keeps_the_code_branch(flags, live, monkeypatch):
    out, fb = _count_answer(monkeypatch, "알람 2075 어제 몇 번 떴어?")
    assert "알람 2075 발생" in _answer_text(out)


# ------------------------------------------------------------------ 번호 없는 건수 — 조회 도구 길 (외부 Claude 채팅)
def test_lookup_prepare_no_longer_blocks_a_count_without_a_code():
    ready, blocked = LT.prepare([{"name": "알람 횟수", "equipment": "", "kind": "", "period": "어제"}])
    assert blocked == [] and [r["name"] for r in ready] == ["alarm_count"]


def test_lookup_execute_gives_the_total_without_a_code(flags, live, monkeypatch):
    fb, _ = _own_backend(monkeypatch, {})
    ready, _ = LT.prepare([{"name": "알람 횟수", "equipment": "", "kind": "", "period": "어제"}])
    with BT.acting_as("U07", ["alarms", "equipment_status"]):
        texts, data = LT.execute("MNT", ready, "어제 알람 몇 번 떴어?")
    assert any("알람 5건" in t for t in texts) and "alarms" in fb.tools_called(), texts


def test_lookup_execute_for_one_equipment_and_for_a_code(flags, live, monkeypatch):
    fb, _ = _own_backend(monkeypatch, {})
    ready, _ = LT.prepare([{"name": "알람 횟수", "equipment": "VF2-01", "kind": "", "period": "어제"}])
    with BT.acting_as("U07", ["alarms", "equipment_status"]):
        texts, _d = LT.execute("MNT", ready, "VF2-01 어제 알람 몇 번 떴어?")
    assert any("VF2-01" in t and "알람 3건" in t for t in texts), texts
    ready, _ = LT.prepare([{"name": "알람 횟수", "equipment": "", "kind": "2075", "period": "어제"}])
    with BT.acting_as("U07", ["alarms", "equipment_status"]):
        texts, _d = LT.execute("MNT", ready, "2075 어제 몇 번 떴어?")
    assert any("알람 2075 발생" in t for t in texts), texts


def test_other_lookups_without_equipment_are_still_blocked():
    ready, blocked = LT.prepare([{"name": "가동 상태", "equipment": "", "kind": "", "period": ""}, {"name": "MTTR", "equipment": "", "kind": "", "period": ""}])
    assert ready == [] and len(blocked) == 2        # 가동 상태·MTTR은 설비 이름이 없으면 예전처럼 되묻는다


# ------------------------------------------------------------------ 로트 상태 한글
SEED = Path(__file__).resolve().parents[3] / "backend" / "db" / "seed" / "10_code_labels.sql"


def test_lot_status_names_equal_the_database_seed():
    if not SEED.exists():
        pytest.skip("DB 시드 파일이 없는 배치")
    seed = dict(re.findall(r"\('production_lot\.status',\s*'([A-Z_]+)',\s*'([^']+)'", SEED.read_text(encoding="utf-8")))
    assert seed and seed == T.LOT_STATUS_KO


def test_lot_line_uses_korean_names_and_adds_the_judgement_state():
    line = A.lot_line_v38
    assert line({"lot_id": "LOT-1", "qty": 36, "status": "IN_PROCESS", "status_ko": "생산 중"}) == "LOT-1 36개 생산 중, 아직 합격 판정 전"
    assert line({"lot_id": "LOT-1", "qty": 31, "status": "PASSED", "status_ko": "합격 (출하 가능)", "passed_at": "2026-09-14T16:00:00+09:00"}) == "LOT-1 31개 합격 (출하 가능), 합격 판정 9/14 16:00"
    assert line({"lot_id": "LOT-1", "qty": 59, "status": "RELEASED", "status_ko": "해제"}) == "LOT-1 59개 해제"
    assert line({"lot_id": "LOT-1", "qty": 5, "status": "NEW_STATE"}) == "LOT-1 5개 NEW_STATE"      # 모르는 코드는 그대로 (지어내지 않는다)
    assert line({"lot_id": "LOT-1", "qty": 5, "status": "PASSED", "status_ko": "합격 (출하 가능)", "passed_at": None}) == "LOT-1 5개 합격 (출하 가능)"


@pytest.mark.parametrize("status,ko", [("IN_PROCESS", "생산 중"), ("WAIT_INSPECTION", "검사 대기"), ("WAIT_JUDGEMENT", "판정 대기"), ("HOLD_REVIEW", "보류 검토"),
                                       ("PASSED", "합격"), ("ON_HOLD", "보류"), ("RELEASED", "해제"), ("SCRAPPED", "폐기")])
def test_lot_answer_shows_no_database_code(flags, monkeypatch, status, ko):
    row = {"lot_no": "LOT-2610-097-1", "status": status, "input_qty": 28, "completed_qty": 0, "plan_mode": "NORMAL", "passed_at": None,
           "shipped_qty": 0, "shipment_nos": None, "trace": []}
    FakeBackend(rows={"lot": [row]}).install(monkeypatch)
    with BT.acting_as("U07", ["lot"]):
        text = _answer_text(A.answer("LOT-2610-097-1 상태 알려줘", "MNT"))
    assert ko in text and status not in text, text


# ------------------------------------------------------------------ 설비 상태 값 표 — 시작 시각과 N분째
SIM = "2026-10-24T09:04:00+09:00"


def _row(eq, proc, state, since="2026-10-24T09:00:00+09:00", minutes=4.0, alarm=None):
    return {"equipment_id": eq, "process_code": proc, "last_state": state, "since": since, "minutes": minutes, "open_alarm_code": alarm}


@pytest.mark.parametrize("m,text", [(None, ""), (0, "방금 시작"), (4, "4분째"), (59, "59분째"), (60, "1시간째"), (65, "1시간 5분째"), (1440, "1일째"), (1500, "1일 1시간째")])
def test_minutes_text(m, text):
    assert A._minutes_text_v38(m) == text


def test_minutes_come_from_the_server_or_are_computed_from_the_clock():
    assert A._state_minutes_v38(_row("A", "OP-10", "RUN", minutes=12.0), SIM) == 12
    assert A._state_minutes_v38(_row("A", "OP-10", "RUN", minutes=0), SIM) == 4          # 서버가 0이면 시계 − 시작 시각
    assert A._state_minutes_v38({"since": "", "minutes": 0}, SIM) is None                  # 둘 다 모르면 지어내지 않는다
    assert A._state_minutes_v38({"since": "2026-10-24T09:10:00+09:00", "minutes": 0}, SIM) == 0      # 시작이 시계보다 늦으면 음수 없이 0


def test_every_equipment_line_has_a_start_time_and_minutes():
    lines = A._eq_state_lines_v37([_row("WSH-01", "OP-40", "RUN"), _row("VF2-01", "OP-30", "DOWN", since="2026-10-24T08:40:00+09:00", minutes=24.0, alarm="992"),
                                   _row("MIL-01", "OP-20", "SETUP", since="2026-10-23T09:00:00+09:00", minutes=0)], SIM)
    assert lines[0] == "- WSH-01 (OP-40): 가공 중 (09:00부터, 4분째)"
    assert lines[1] == "- VF2-01 (OP-30): 고장 정지 (08:40부터, 24분째, 열린 알람 992)"
    assert lines[2] == "- MIL-01 (OP-20): 셋업 (10/23 09:00부터, 1일째)"


def test_a_running_machine_never_shows_an_alarm_even_if_the_server_sent_one():
    line = A._eq_state_lines_v37([_row("WSH-01", "OP-40", "RUN", alarm="992")], SIM)[0]
    assert "알람" not in line and line.endswith("(09:00부터, 4분째)")


def test_status_scope_rules_are_in_the_note_and_the_ask_only_rule_is_not_contradicted():
    from backend.services import pure_external as PURE
    note = A.EQS_RULES_V36
    assert "다른 설비 이야기는 하지 않는다" in note and "나열하지 않는다" in note and "'[상태별 대수]' 줄을 그대로 옮기고(직접 세지 않는다)" in note
    assert "나머지 설비는 값에 적힌 상태별로 한 줄로 묶는다" not in note       # 묻는 것에만 답하라는 ASK_ONLY_NOTE와 부딪히던 옛 문장
    assert "다른 설비나 다른 품목 이야기도 쓰지 않는다" in PURE.ASK_ONLY_NOTE


def test_state_count_line_is_counted_by_the_program():
    rows = [_row("A", "OP-10", "SETUP"), _row("B", "OP-20", "RUN"), _row("C", "OP-30", "SETUP"), _row("D", "OP-30", "SETUP"), _row("E", "OP-40", "RUN"), _row("F", "OP-50", "RUN")]
    assert A._state_count_line_v38(rows) == "[상태별 대수] 모두 6대: 가공 중 3대, 셋업 3대"      # Claude가 "6대 중 4대"로 틀리게 센 적이 있다
    rows[1] = _row("B", "OP-20", "DOWN", alarm="992")
    rows[4] = _row("E", "OP-40", "BLOCKED")
    assert A._state_count_line_v38(rows) == "[상태별 대수] 모두 6대: 고장 정지 1대, 막힘 1대, 가공 중 1대, 셋업 3대"      # 고장·막힘이 먼저
    assert A._state_count_line_v38([_row("A", "OP-10", "WEIRD")]) == "[상태별 대수] 모두 1대: WEIRD 1대"      # 모르는 코드는 그대로
    note = A.equipment_states_note_v36({"rows": rows, "as_of": SIM})
    assert note.index("[상태별 대수]") < note.index("[이 값 쓰는 법]")


# ------------------------------------------------------------------ 조회 길의 달 말·모든 설비 합계 (2026-10-25 후속)
def test_period_window_understands_this_month_and_a_month_name(flags, live):
    end = SC.data_period()[1]
    assert LT.period_window("이번 달") == (date(2026, 10, 1), end, None)
    assert LT.period_window("이번달") == (date(2026, 10, 1), end, None)
    assert LT.period_window("10월") == (date(2026, 10, 1), end, None)
    assert LT.period_window("10월 야간")[2] == "N"
    assert LT.period_window("10월 23일") == (None, None, None)        # 일까지 적은 달력 날짜는 예전처럼 지운다
    assert LT.period_window("9월") == (None, None, None)              # 시계 있음: 기록이 10/1부터라 9월은 기록 밖 → 날짜 없음 (아래 시험이 "기록 밖" 안내를 확인한다)


def test_a_month_outside_the_record_is_told_not_silently_replaced(flags, live, monkeypatch):
    fb, _ = _own_backend(monkeypatch, {})
    ready, blocked = LT.prepare([{"name": "알람 횟수", "equipment": "모든 설비", "kind": "", "period": "9월"}])
    assert blocked == [] and ready[0]["outside"] == "9월" and ready[0]["start"] is None
    with BT.acting_as("U07", ["alarms", "equipment_status"]):
        texts, data = LT.execute("MNT", ready, "9월 알람 몇 건이야?")
    assert len(texts) == 1 and "9월" in texts[0] and "가상 데이터 기간" in texts[0] and "밖이라 운영 기록이 없습니다" in texts[0], texts
    assert "alarms" not in fb.tools_called()                      # 다른 달 값을 대신 조회하지 않는다
    ok, _b = LT.prepare([{"name": "알람 횟수", "equipment": "", "kind": "", "period": "10월"}])
    assert ok[0]["outside"] is None and ok[0]["start"] == date(2026, 10, 1)


def test_period_window_without_a_clock_keeps_the_old_behavior():
    assert LT.period_window("이번 달") == (None, None, None) and LT.period_window("10월") == (None, None, None)
    assert LT.period_window("9월") == (date(2026, 9, 1), date(2026, 9, 30), None)      # 시계 없음: 9월이 기록 기간 (예전 동작)
    assert LT.period_window("어제")[0] == date(2026, 9, 30)


def test_all_equipment_alarm_count_is_one_lookup_with_a_total(flags, live, monkeypatch):
    fb, _ = _own_backend(monkeypatch, {})
    ready, _ = LT.prepare([{"name": "알람 횟수", "equipment": "모든 설비", "kind": "", "period": "어제"}])
    assert len(ready[0]["equipment"]) == 6
    with BT.acting_as("U07", ["alarms", "equipment_status"]):
        texts, data = LT.execute("MNT", ready, "어제 알람 몇 번 떴어?")
    assert fb.tools_called().count("alarms") == 1, fb.tools_called()          # 여섯 번이 아니라 한 번
    assert len(texts) == 1 and texts[0].startswith("2026-10-25 알람 5건") and "VF2-01 3건" in texts[0], texts


def test_two_named_equipment_still_get_their_own_lines(flags, live, monkeypatch):
    fb, _ = _own_backend(monkeypatch, {})
    ready, _ = LT.prepare([{"name": "알람 횟수", "equipment": "VF2-01, VF2-02", "kind": "", "period": "어제"}])
    with BT.acting_as("U07", ["alarms", "equipment_status"]):
        texts, _d = LT.execute("MNT", ready, "VF2-01하고 VF2-02 어제 알람 몇 번 떴어?")
    assert fb.tools_called().count("alarms") == 2 and len(texts) == 2


def test_the_lookup_instructions_allow_months_and_a_count_without_a_number():
    assert "이번 달·10월" in LT._DECIDE_SYSTEM and "일까지 적은 달력 날짜는 쓰지 않는다" in LT._DECIDE_SYSTEM
    assert "알람 횟수는 알람 번호나 설비 이름이 없어도 조회한다" in LT._DECIDE_SYSTEM and "모든 설비로 둔다" in LT._DECIDE_SYSTEM
    assert "첫 문장에 그 합계를 말하고" in LT._WRITE_SYSTEM and "직접 더하지 않는다" in LT._WRITE_SYSTEM
