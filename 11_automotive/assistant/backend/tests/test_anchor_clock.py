"""비서의 기준일을 시연 시계로 (2026-10-25, 261003_창민/기준일_시연시계_기획_20261025.md).

공용 DB는 10월 데이터(10/1~)이고 시연 시계는 10/26인데, 비서 코드는 기준일 10/1·데이터 기간 9월이 박혀 있어
"어제 알람 몇 건?"이 '미래'로 거절되고 "VF2-01 MTTR"이 '데이터 없음'으로 끝났다.
시계가 없으면(옛 시연 서버·다른 시험) 지금까지와 똑같다 — 그 경로는 기존 시험 전체가 지키고, 여기서는 시계가 있을 때와 두 경로의 경계를 본다."""
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.services import answer as A
from backend.services import sim_clock as SC
from backend.tools import query_tools as T

KST = timezone(timedelta(hours=9))
ON = ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP", "PARSE_V8", "FOLLOWUP_V2", "PARSE_V9")


def clock(at=datetime(2026, 10, 26, 15, 0, tzinfo=KST), history_start=date(2026, 10, 1)):
    return SC.Clock(at, 540, 1080, 1260, 360, history_start)


@pytest.fixture
def flags(monkeypatch):
    for k in ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("NUM_MATCH", "value")


@pytest.fixture
def live(monkeypatch):
    """시연 시계 10/26 15:00 (profile.history_start 10/1)."""
    monkeypatch.setattr(SC, "current", lambda: clock())


# ------------------------------------------------------------ sim_clock
def test_no_clock_keeps_the_old_september_window():
    assert SC.current() is None                       # conftest가 시계를 끈다
    assert SC.data_period() == (date(2026, 9, 1), date(2026, 9, 30))
    assert SC.default_end() == date(2026, 9, 30)
    assert SC.default_range(30) == (date(2026, 9, 1), date(2026, 9, 30))
    assert SC.default_range(1) == (date(2026, 9, 30), date(2026, 9, 30))


def test_clock_gives_october_window(live):
    assert SC.data_period() == (date(2026, 10, 1), date(2026, 10, 26))
    assert SC.default_end() == date(2026, 10, 25)                       # 어제 (데이터가 있는 마지막 끝난 날)
    assert SC.default_range(30) == (date(2026, 10, 1), date(2026, 10, 25))   # 기록 시작 전으로는 안 간다
    assert SC.default_range(1) == (date(2026, 10, 25), date(2026, 10, 25))


def test_first_day_default_end_is_not_before_history(monkeypatch):
    monkeypatch.setattr(SC, "current", lambda: clock(at=datetime(2026, 10, 1, 9, 0, tzinfo=KST)))
    assert SC.default_end() == date(2026, 10, 1)                        # 어제(9/30)는 기록 시작 전이라 시작일


def test_history_start_is_read_from_health():
    doc = {"clock": {"sim_at": "2026-10-26T15:00:00+09:00"},
           "profile": {"history_start": "2026-10-01", "shifts": {"DAY": {"start": "09:00", "end": "18:00"}, "NIGHT": {"start": "21:00", "end": "06:00"}}}}
    c = SC.parse_health(doc)
    assert c is not None and c.history_start == date(2026, 10, 1)
    doc["profile"].pop("history_start")
    assert SC.parse_health(doc).history_start is None                   # 없으면 기준 시각의 날짜로 간다
    monkey = SC.Clock(c.at, 540, 1080, 1260, 360)
    assert monkey.history_start is None


def test_missing_history_start_falls_back_to_reference_day(monkeypatch):
    monkeypatch.setattr(SC, "current", lambda: clock(history_start=None))
    assert SC.data_period()[0] == date(2026, 10, 1)


# ------------------------------------------------------------ 도구의 기본 기간
def test_tool_default_period_follows_the_clock(live):
    assert T._period(None, None) == (date(2026, 10, 1), date(2026, 10, 25))
    assert T._period(None, None, default_days=1) == (date(2026, 10, 25), date(2026, 10, 25))
    assert T._period(date(2026, 10, 20), None) == (date(2026, 10, 20), date(2026, 10, 25))
    assert T._period(None, date(2026, 10, 10)) == (date(2026, 10, 1), date(2026, 10, 10))   # 끝만 말해도 기록 시작 전으로 안 간다


def test_tool_default_period_without_clock_is_unchanged():
    assert T._period(None, None) == (date(2026, 9, 1), date(2026, 9, 30))
    assert T._period(None, None, default_days=1) == (date(2026, 9, 30), date(2026, 9, 30))
    assert T._period(date(2026, 9, 10), None) == (date(2026, 9, 10), date(2026, 9, 30))


# ------------------------------------------------------------ 규칙 층 판독
ALARM_QS = ["어제 알람 몇 건이야?", "10월에 알람 몇 건 있었어?", "어제 VF2-01 알람 몇 건 있었어?", "오늘 알람 몇 건이야?", "지난주 알람 몇 건이야?",
            "9월에 알람 몇 건 있었어?", "알람 몇 건 있었어?", "경보 몇 건이나 났어?"]


@pytest.mark.parametrize("q", ALARM_QS)
def test_alarm_count_wording_is_read_as_ops(flags, live, q):
    assert "alarm_count" in A.parse(q)["intents"], q


@pytest.mark.parametrize("q", ["작업지시서 몇 건이야?", "하루에 몇 건 처리해?", "알람 몇 건 이상이면 반복 알람이야?", "알람이 몇 건 이상 나면 3단계야?"])
def test_count_wording_without_alarm_or_with_threshold_is_not_alarm_count(flags, live, q):
    assert "alarm_count" not in A.parse(q)["intents"], q


def test_new_wording_needs_parse_v9(monkeypatch, live):
    """PARSE_V9가 꺼진 옛 설정의 동작은 그대로다 (test_parse_v9: 'V9 이전에는 못 읽었다')."""
    for k in ON[:-1]:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("PARSE_V9", "0")
    assert "alarm_count" not in A.parse("어제 알람 몇 건이야?")["intents"]


def test_yesterday_and_today_are_not_future(flags, live):
    y = A.parse("어제 알람 몇 건이야?")
    assert (y["start"], y["end"]) == (date(2026, 10, 25),) * 2 and not y.get("future")
    t = A.parse("오늘 알람 몇 건이야?")
    assert (t["start"], t["end"]) == (date(2026, 10, 26),) * 2 and not t.get("future")


def test_tomorrow_is_still_future(flags, live):
    p = A.parse("내일 알람 몇 건 날 것 같아?")
    assert p.get("future") is True or p["start"] is None


def test_last_week_follows_the_clock(flags, live):
    p = A.parse("지난주 알람 몇 건이야?")
    assert (p["start"], p["end"]) == (date(2026, 10, 19), date(2026, 10, 25))


def test_october_is_data_and_september_is_outside(flags, live):
    o = A.parse("10월에 알람 몇 건 있었어?")
    assert (o["start"], o["end"]) == (date(2026, 10, 1), date(2026, 10, 26)) and not o.get("outside")
    s = A.parse("9월에 알람 몇 건 있었어?")
    assert s["start"] is None and s.get("outside") == "9월"


def test_without_clock_september_is_data_and_october_is_outside(flags):
    s = A.parse("9월에 알람 몇 건 있었어?")
    assert (s["start"], s["end"]) == (date(2026, 9, 1), date(2026, 9, 30))
    o = A.parse("10월에 알람 몇 건 있었어?")
    assert o["start"] is None and o.get("outside") == "10월"
    y = A.parse("어제 알람 몇 건이야?")
    assert y["start"] == date(2026, 9, 30)                                # 옛 동작: 기준 시각 10/1의 어제


def test_month_in_data_period_edges(live):
    assert A.month_in_data_period(10) == (date(2026, 10, 1), date(2026, 10, 26))
    assert A.month_in_data_period(9) is None and A.month_in_data_period(11) is None and A.month_in_data_period(12) is None


def test_period_texts_follow_the_clock(live):
    assert A.period_text() == "2026-10-01 ~ 10-26"
    assert A.ref_time_text() == "2026-10-26 15:00"


def test_period_texts_without_clock_are_the_old_ones():
    assert A.period_text() == "2026-09-01 ~ 09-30"
    assert A.ref_time_text() == "2026-10-01 08:00"


# ------------------------------------------------------------ MTTR: 지표가 비어도 신뢰도(최근 30일)는 읽는다
def _own_backend(monkeypatch, rows):
    from backend.repositories import backend_tools as BT
    from backend.tests.fake_backend import FakeBackend
    fb = FakeBackend(rows=rows).install(monkeypatch)
    return fb, BT


def test_reliability_tool_reads_thirty_days(monkeypatch):
    fb, BT = _own_backend(monkeypatch, {})
    with BT.acting_as("U07", ["reliability", "kpi"]):
        r = T.reliability("MNT", "VF2-01")
    k = r["rows"][0]
    assert (k["mttr_30d_min"], k["mtbf_30d_h"], k["failures_30d"]) == (50.0, 168.0, 4) and r["range"] == "최근 30일" and not r["reliability_hidden"]
    assert fb.tools_called() == ["reliability"]


def test_reliability_tool_hidden_for_roles_without_permission(monkeypatch):
    fb, BT = _own_backend(monkeypatch, {})
    with BT.acting_as("U02", ["kpi"]):
        r = T.reliability("OPR", "VF2-01")
    assert r["rows"] == [] and r["reliability_hidden"] is True and fb.tools_called() == []     # 못 보는 역할이면 부르지도 않는다


def test_mttr_question_answers_even_when_kpi_rows_are_empty(flags, live, monkeypatch):
    """공용 DB 10월: 지표(kpi) 기본 기간이 비어도 MTTR은 최근 30일 값으로 답한다."""
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, {"kpi": []})
    with BT.acting_as("U07", ["reliability", "kpi", "equipment_status"]):
        out = A.answer("VF2-01 MTTR 알려줘", "MNT")
    text = out.get("conclusion", "") + " ".join(b.get("text", "") for b in out.get("blocks", []) if isinstance(b, dict))
    assert "50" in text and "168" in text and "데이터 없음" not in text, text
    assert "reliability" in fb.tools_called()


def test_mttr_question_still_empty_when_no_reliability_row(flags, live, monkeypatch):
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, {"kpi": [], "reliability": []})
    with BT.acting_as("U07", ["reliability", "kpi", "equipment_status"]):
        out = A.answer("VF2-01 MTTR 알려줘", "MNT")
    text = out.get("conclusion", "") + " ".join(b.get("text", "") for b in out.get("blocks", []) if isinstance(b, dict))
    assert "50" not in text and "168" not in text                       # 값이 없으면 지어내지 않는다


def test_oee_question_with_empty_kpi_is_unchanged(flags, live, monkeypatch):
    """OEE를 묻는 질문은 지표가 비면 그대로 '데이터 없음' — 신뢰도 값을 대신 보여 주지 않는다."""
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, {"kpi": []})
    with BT.acting_as("U07", ["reliability", "kpi", "equipment_status"]):
        out = A.answer("VF2-01 OEE 알려줘", "MNT")
    assert "reliability" not in fb.tools_called()


# ------------------------------------------------------------ 답까지: 어제·10월 알람 건수가 조회로 간다
def _answer_text(out):
    return out.get("conclusion", "") + " " + " ".join(b.get("text", "") for b in out.get("blocks", []) if isinstance(b, dict))


@pytest.mark.parametrize("q,start,end", [("어제 알람 몇 건이야?", "2026-10-25", "2026-10-25"), ("오늘 알람 몇 건이야?", "2026-10-26", "2026-10-26"),
                                         ("10월에 알람 몇 건 있었어?", "2026-10-01", "2026-10-26"), ("지난주 알람 몇 건이야?", "2026-10-19", "2026-10-25")])
def test_alarm_count_questions_reach_the_alarm_tool_with_october_dates(flags, live, monkeypatch, q, start, end):
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, {})
    with BT.acting_as("U07", ["alarms", "equipment_status", "kpi", "reliability"]):
        out = A.answer(q, "MNT")
    calls = [c for c in fb.calls if c["tool"] == "alarms"]
    assert calls, (q, fb.tools_called())
    day_after = (date.fromisoformat(end) + timedelta(days=1)).isoformat()                  # 도구 인자는 [시작, 끝) 시각 — 끝날의 다음 날 0시
    assert {c["args"].get("from", "")[:10] for c in calls} == {start} and {c["args"].get("to", "")[:10] for c in calls} == {day_after}, calls
    assert "기준 시각" not in _answer_text(out) and "확인 필요" not in _answer_text(out), _answer_text(out)


def test_september_question_says_outside_with_the_october_period(flags, live, monkeypatch):
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, {})
    with BT.acting_as("U07", ["alarms", "equipment_status", "kpi", "reliability"]):
        out = A.answer("9월에 알람 몇 건 있었어?", "MNT")
    text = _answer_text(out)
    assert "2026-10-01 ~ 10-26" in text and "2026-09-01" not in text, text
    assert "alarms" not in fb.tools_called()


def test_tomorrow_alarm_question_uses_the_live_reference_time(flags, live, monkeypatch):
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, {})
    with BT.acting_as("U07", ["alarms", "equipment_status", "kpi", "reliability"]):
        out = A.answer("내일 알람 몇 건이야?", "MNT")
    text = _answer_text(out)
    if "기준 시각" in text:
        assert "2026-10-26 15:00" in text and "2026-10-01 08:00" not in text, text


# ------------------------------------------------------------ 알람 번호 없이 전체 건수
def _count_answer(monkeypatch, q, rows=None):
    from backend.repositories import backend_tools as BT
    fb, _ = _own_backend(monkeypatch, rows or {})
    with BT.acting_as("U07", ["alarms", "equipment_status", "kpi", "reliability"]):
        return A.answer(q, "MNT"), fb


def test_total_alarm_count_without_a_code(flags, live, monkeypatch):
    out, fb = _count_answer(monkeypatch, "어제 알람 몇 건이야?")
    text = _answer_text(out)
    assert out["status"] == "답변" and "2026-10-25 알람 5건" in text, text          # 가짜 백엔드: VF2-01 3건 + VF2-02 2건
    assert "VF2-01 3건" in text and "VF2-02 2건" in text and "알람 번호" not in text


def test_total_alarm_count_for_one_equipment(flags, live, monkeypatch):
    out, fb = _count_answer(monkeypatch, "어제 VF2-01 알람 몇 건 있었어?")
    text = _answer_text(out)
    assert "VF2-01 2026-10-25 알람 3건" in text and fb.calls[-1]["args"].get("equipment_id") == "VF2-01", text


def test_alarm_count_with_a_code_still_uses_the_code_branch(flags, live, monkeypatch):
    out, fb = _count_answer(monkeypatch, "알람 2075 어제 몇 건 있었어?")
    text = _answer_text(out)
    assert "알람 2075 발생" in text, text


def test_total_alarm_count_with_no_alarms_says_zero(flags, live, monkeypatch):
    out, fb = _count_answer(monkeypatch, "어제 알람 몇 건이야?", {"alarms": []})
    assert "2026-10-25 알람 0건" in _answer_text(out)


def test_how_many_times_without_a_code_now_answers_the_total_too(flags, monkeypatch):
    """"몇 번" 말투도 번호가 없으면 기간 안 전체 건수로 답한다 (2026-10-25 AWS 점검 보고 — 전에는 알람 번호를 되물었다)."""
    out, fb = _count_answer(monkeypatch, "알람 몇 번 났어?")
    text = _answer_text(out)
    assert out["status"] == "답변" and "알람 번호" not in text and "알람 5건" in text and "alarms" in fb.tools_called(), text
