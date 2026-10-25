"""지금 병목 어디야? 답하기 (2026-10-25) 최소 시험 — 진짜 Claude·네트워크·DB·시연 서버를 부르지 않는다 (가짜 백엔드·시연 서버 값은 바꿔치기).

문제: 낱말표에 병목이 없고 병목을 읽는 도구도 없어 "지금 병목 어디야?"가 문서 길로 가 "현재 값은 찾지 못했어요"(12초·5만 자·Claude 1회)로 끝났다.
지키는 것: 지금 병목은 시연 서버 값으로 프로그램이 답하고(SENSOR_LIVE=1), 못 읽거나 스위치가 꺼져 있으면 "못 읽었다"고 알린다. 지난 병목·이동 기록·잃은 개수는
읽는 곳이 없어 안내만 한다. 뜻·원인·조치·판단 규칙 질문은 건드리지 않는다(문서 길).
"""
import pytest

from backend.repositories import backend_tools as BT
from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON
from backend.tools import query_tools as T
from backend.tools import sim_live

EQ = {"SAW-01": {"process_code": "OP-10"}, "MIL-01": {"process_code": "OP-20"}, "VF2-01": {"process_code": "OP-30"},
      "VF2-02": {"process_code": "OP-30"}, "WSH-01": {"process_code": "OP-40"}, "CMM-01": {"process_code": "OP-50"}}


def twin(process="OP-30", cause="BASE", since="2026-10-22T11:48:00+09:00", at="2026-10-25T08:05:00+09:00"):
    return {"clock": {"sim_at": at}, "bottleneck": {"process_code": process, "cause_code": cause, "alarm_event_id": None, "since_at": since}, "equipment": EQ}


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("SENSOR_LIVE", "1")
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: sim_live.parse_bottleneck(twin()))


def ask(q, role="MNT"):
    a = A.answer(q, role, {"new_chat": "1"})
    a.pop("_followup", None)
    return a


def kind(q):
    return A.bottleneck_kind_v35(q, A.parse(q))


# ------------------------------------------------------------------ 시연 서버 응답 읽기
def test_parse_bottleneck_reads_process_cause_since_and_the_clock():
    got = sim_live.parse_bottleneck(twin("OP-50", "C3", "2026-10-25T07:00:00+09:00"))
    assert got["process_code"] == "OP-50" and got["cause_code"] == "C3" and got["since_at"].startswith("2026-10-25T07:00")
    assert got["sim_at"].startswith("2026-10-25T08:05") and got["equipment_process"]["VF2-01"] == "OP-30" and got["equipment_process"]["CMM-01"] == "OP-50"


def test_parse_bottleneck_accepts_a_missing_start_time():
    assert sim_live.parse_bottleneck(twin(since=None))["since_at"] is None


@pytest.mark.parametrize("doc", [None, [], {}, {"clock": {"sim_at": "2026-10-25T08:05:00+09:00"}}, {"bottleneck": {"process_code": "OP-30", "cause_code": "BASE"}},
                                 {"clock": {"sim_at": "2026-10-25"}, "bottleneck": {"process_code": "OP-30", "cause_code": "BASE"}},
                                 {"clock": {"sim_at": "2026-10-25T08:05:00+09:00"}, "bottleneck": {"process_code": "", "cause_code": "BASE"}},
                                 {"clock": {"sim_at": "2026-10-25T08:05:00+09:00"}, "bottleneck": {"process_code": "OP-30", "cause_code": None}},
                                 {"clock": {"sim_at": "2026-10-25T08:05:00+09:00"}, "bottleneck": "OP-30"}])
def test_parse_bottleneck_returns_none_for_a_missing_or_wrong_shape(doc):
    assert sim_live.parse_bottleneck(doc) is None


# ------------------------------------------------------------------ 조회 도구
def test_tool_returns_one_live_row():
    r = T.bottleneck_now("MNT")
    assert r["tool"] == "병목 조회" and r["live"] and r["as_of"].startswith("2026-10-25T08:05") and r["rows"][0]["process_code"] == "OP-30"
    assert "sim_at" not in r["rows"][0]


def test_tool_is_none_when_the_switch_is_off_and_does_not_call_the_demo_server(monkeypatch):
    monkeypatch.setenv("SENSOR_LIVE", "0")
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: pytest.fail("스위치가 꺼져 있으면 시연 서버를 부르지 않는다"))
    assert T.bottleneck_now("MNT") is None


def test_tool_is_none_when_the_demo_server_cannot_be_read(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: None)
    assert T.bottleneck_now("MNT") is None


def test_tool_is_denied_for_a_role_without_line_view():
    with BT.acting_as("U01", ["alarms"]):
        with pytest.raises(BT.ToolDenied):
            T.bottleneck_now("OPR")


# ------------------------------------------------------------------ 질문 가르기 (37개: 지금 15 · 지난 7 · 잃은 개수 1 · 손대지 않음 14)
NOW = ["지금 병목 어디야?", "지금 병목어디야?", "현재 병목 공정이 어디예요?", "병목 공정 어디야", "지금 어느 공정이 병목이야?", "지금 병목 공정 알려줘",
       "지금 병목으로 표시된 공정이 어디예요? 검사 쪽인가요?", "지금 라인에서 제일 막히는 곳이 어디야?", "라인이 어디서 막혀?", "지금 병목이 OP-30이야?",
       "병목이 풀렸어?", "병목 언제부터 그랬어?", "지금 병목 원인이 뭐야?", "VF2-01이 지금 병목이야?", "VF2-02 때문에 병목 생겼어?",
       "지금 어느 공정이 제일 느려?", "지금 라인 속도를 정하는 공정이 어디야?"]      # 병목 낱말 없이 같은 뜻으로 묻는 말 (2026-10-25 말투별 시험에서 더함)
PAST = ["병목이 어디로 옮겨 갔어?", "최근 병목 이동 기록 보여줘", "병목이 몇 번 바뀌었어?", "이번 교대 병목 구간 알려줘", "어제 야간에 병목이 어디였어?",
        "어제 병목 원인이 뭐였어?", "지난주 병목 공정이 어디였어?"]
LOSS = ["오늘 병목 때문에 잃은 개수는?", "병목 때문에 몇 개 잃었어?"]
UNTOUCHED = ["재공이 제일 많이 쌓인 구간이 어디야?", "제일 느린 설비 알려줘", "LOT-2609-041-1 때문에 병목이 OP-50으로 갔어?",
             "병목이 뭐야?", "병목은 어떻게 판단해?", "병목 원인이 뭐야?", "병목 조치 방법은?", "병목 걸리면 누가 뭘 해?", "병목이랑 고장은 뭐가 달라?",
             "VF2-01 지금 상태 어때?", "오늘 생산 실적 몇 개야?", "VF2-02 공구 수명 얼마나 남았어?", "재고 부족한 품목 있어?",
             # 문서 질문 몇 개 더 — 병목 낱말이 있어도 값을 묻지 않는다
             "병목 원인 쉽게 설명해", "병목 원인 쉽게 요약해", "병목 원인별 조치가 뭐야?", "지금 병목 어떻게 풀어?", "병목은 속도 손실이야 고장 손실이야?",
             "병목 이동 알림은 언제 떠?", "OP-30이 왜 병목이야?", "2075 알람이 병목이랑 관계 있어?"]


@pytest.mark.parametrize("q", NOW)
def test_now_questions(q):
    assert kind(q) == "now", q


@pytest.mark.parametrize("q", PAST)
def test_past_questions(q):
    assert kind(q) == "past", q


@pytest.mark.parametrize("q", LOSS)
def test_loss_questions(q):
    assert kind(q) == "loss", q


@pytest.mark.parametrize("q", UNTOUCHED)
def test_other_questions_are_left_alone(q):
    assert kind(q) is None, q


# ------------------------------------------------------------------ 답
def test_now_answer_uses_the_demo_server_value_without_claude():
    a = ask("지금 병목 어디야?")
    c = a["conclusion"]
    assert a["status"] == "답변" and a["mode"].startswith("규칙") and "Claude 호출 없음" in a["mode"]
    assert "지금 병목은 OP-30이에요" in c and "2026-10-25 08:05 기준, 시연 화면 시계" in c and "기준 병목(OP-30)" in c and "10/22 11:48부터 이 상태예요" in c
    assert "찾지 못" not in c and a["is_synthetic"] and a["current_data"][0]["tool"] == "병목 조회" and a["current_data"][0]["as_of"].startswith("2026-10-25T08:05")
    assert [e["doc_id"] + e["section"] for e in a["evidence"]] == ["DOC-077.3"] and a["blocks"] == [{"kind": "text", "text": c}]


def test_base_bottleneck_cause_question_says_there_is_no_special_cause():
    c = ask("지금 병목 원인이 뭐야?")["conclusion"]
    assert "기준 병목(OP-30)" in c and "따로 병목 원인으로 잡힌 것" in c
    assert "따로 병목 원인으로 잡힌 것" not in ask("지금 병목 어디야?")["conclusion"]


@pytest.mark.parametrize("cause,name", [("C1", "원인 ① 사이클 시간 증가 (공구 마모)"), ("C2", "원인 ② OP-30 1대만 가동"), ("C3", "원인 ③ 검사 강화"), ("FAILURE", "고장")])
def test_named_causes(monkeypatch, cause, name):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: sim_live.parse_bottleneck(twin("OP-50" if cause == "C3" else "OP-30", cause)))
    c = ask("지금 병목 어디야?")["conclusion"]
    assert f"병목 원인: {name}." in c and "10/22 11:48부터 이어지고 있어요." in c and "기준 병목" not in c


def test_same_day_start_time_has_no_date(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: sim_live.parse_bottleneck(twin("OP-50", "C3", "2026-10-25T07:20:00+09:00")))
    c = ask("지금 병목 어디야?")["conclusion"]
    assert "지금 병목은 OP-50이에요" in c and c.endswith(" 07:20부터 이어지고 있어요.") and "10/25 07:20" not in c


def test_missing_start_time_is_not_made_up(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: sim_live.parse_bottleneck(twin("OP-50", "C3", None)))
    c = ask("지금 병목 어디야?")["conclusion"]
    assert c.endswith("병목 원인: 원인 ③ 검사 강화.") and "부터" not in c


@pytest.mark.parametrize("q,tail", [("VF2-01이 지금 병목이야?", "VF2-01은 OP-30 공정이라 지금 병목에 해당해요."), ("VF2-02 때문에 병목 생겼어?", "VF2-02는 OP-30 공정이라 지금 병목에 해당해요."),
                                    ("WSH-01이 지금 병목이야?", "WSH-01은 OP-40 공정이라 지금 병목이 아니에요.")])
def test_a_named_equipment_gets_its_process_checked(q, tail):
    c = ask(q)["conclusion"]
    assert c.endswith(tail) and "지금 병목은 OP-30이에요" in c


def test_two_equipment_names_add_no_equipment_sentence():
    c = ask("VF2-01하고 SAW-01 중에 지금 병목이 어디야?")["conclusion"]
    assert "지금 병목은 OP-30이에요" in c and "공정이라" not in c


def test_unreadable_demo_server_says_so_instead_of_inventing(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: None)
    a = ask("지금 병목 어디야?")
    assert a["status"] == "확인 필요" and a["conclusion"] == A.BN_UNREAD_NOTE_V35 and "OP-" not in a["conclusion"] and "주황 테두리" in a["conclusion"]


def test_switch_off_gives_the_same_notice(monkeypatch):
    monkeypatch.setenv("SENSOR_LIVE", "0")
    assert ask("지금 병목 어디야?")["conclusion"] == A.BN_UNREAD_NOTE_V35


def test_past_questions_get_the_fixed_notice_and_never_call_the_demo_server(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: pytest.fail("지난 병목은 시연 서버를 부르지 않는다"))
    for q in ("어제 야간에 병목이 어디였어?", "최근 병목 이동 기록 보여줘"):
        a = ask(q)
        assert a["status"] == "확인 필요" and a["conclusion"] == A.BN_PAST_NOTE_V35 and "SCR-15" in a["conclusion"] and "SCR-06" in a["conclusion"]


def test_loss_question_reuses_the_speed_loss_notice():
    a = ask("오늘 병목 때문에 잃은 개수는?")
    assert a["status"] == "확인 필요" and a["conclusion"] == A.SPEED_LOSS_NOTE_V24


def test_a_role_without_line_view_is_denied_not_answered():
    with BT.acting_as("U01", ["alarms"]):
        with pytest.raises(BT.ToolDenied):
            ask("지금 병목 어디야?", "OPR")


def test_the_rule_runs_before_the_continue_judge(monkeypatch):
    """앞 답이 있어도(이어짐 판단이 Claude를 부르는 때) 병목 값 질문은 그 판단을 거치지 않는다."""
    from backend.services import continuation as CONT
    monkeypatch.setattr(CONT, "judge", lambda *a, **k: pytest.fail("이어짐 판단(Claude)을 부르면 안 된다"))
    prev = {"question": "어제 주간 교대 보고서 작성됐어?", "conclusion": "확정됐어요.", "doc_lines": []}
    a = A.answer("지금 병목 어디야?", "MNT", {}, prev=prev)
    assert a["conclusion"].startswith("지금 병목은 OP-30이에요")


# ------------------------------------------------------------------ 병목 공정의 설비 줄 (2026-10-25, "어떤 설비 VF2-01인지도")
def eq_state(proc, state, since="2026-10-25T07:20:00+09:00", alarm=None):
    return {"process_code": proc, "state_code": state, "since_at": since, "minutes": 30.0, "alarm": alarm}


ALARM = {"alarm_code": "992", "severity": "STOP", "cleared_at": None}


def twin_states(vf01, vf02, **over):
    eq = {"SAW-01": eq_state("OP-10", "RUN"), "MIL-01": eq_state("OP-20", "RUN"), "VF2-01": vf01, "VF2-02": vf02,
          "WSH-01": eq_state("OP-40", "RUN"), "CMM-01": eq_state("OP-50", "IDLE")}
    return {**twin(cause="FAILURE", since="2026-10-24T09:35:00+09:00"), "equipment": eq, **over}


def serve(monkeypatch, doc):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: sim_live.parse_bottleneck(doc))


def test_parse_keeps_each_equipment_state_row():
    got = sim_live.parse_bottleneck(twin_states(eq_state("OP-30", "DOWN", alarm=ALARM), eq_state("OP-30", "RUN")))
    row = got["equipment_state"]["VF2-01"]
    assert row["last_state"] == "DOWN" and row["open_alarm_code"] == "992" and row["since"].startswith("2026-10-25T07:20") and set(got["equipment_state"]) == set(EQ) | {"VF2-01"}


def test_parse_skips_equipment_without_a_state_code():
    doc = twin_states({"process_code": "OP-30"}, eq_state("OP-30", "RUN"))
    assert "VF2-01" not in sim_live.parse_bottleneck(doc)["equipment_state"]


def test_the_failed_machine_is_named_with_its_alarm_and_start_time(monkeypatch):
    serve(monkeypatch, twin_states(eq_state("OP-30", "DOWN", alarm=ALARM), eq_state("OP-30", "RUN")))
    c = ask("지금 병목 어디야?")["conclusion"]
    assert c.endswith("OP-30 설비: VF2-01 고장 정지(알람 992, 07:20부터), VF2-02 가공 중."), c
    assert "병목 원인: 고장. 10/24 09:35부터 이어지고 있어요." in c      # 병목 시작 시각과 설비 상태 시작 시각은 따로 말한다


def test_only_machines_of_the_bottleneck_process_are_listed(monkeypatch):
    serve(monkeypatch, twin_states(eq_state("OP-30", "RUN"), eq_state("OP-30", "RUN")))
    c = ask("지금 병목 어디야?")["conclusion"]
    assert "OP-30 설비: VF2-01 가공 중, VF2-02 가공 중." in c and "SAW-01" not in c and "CMM-01" not in c


def test_other_process_bottleneck_lists_its_own_machine(monkeypatch):
    doc = twin_states(eq_state("OP-30", "RUN"), eq_state("OP-30", "RUN"))
    doc["bottleneck"] = {"process_code": "OP-50", "cause_code": "C3", "alarm_event_id": None, "since_at": "2026-10-25T07:00:00+09:00"}
    serve(monkeypatch, doc)
    c = ask("지금 병목 어디야?")["conclusion"]
    assert "지금 병목은 OP-50이에요" in c and c.endswith("OP-50 설비: CMM-01 대기(07:20부터).")


@pytest.mark.parametrize("state,label", [("BLOCKED", "막힘"), ("SETUP", "셋업"), ("MAINT", "계획 정비"), ("IDLE", "대기"), ("WEIRD", "WEIRD")])
def test_state_names(monkeypatch, state, label):
    serve(monkeypatch, twin_states(eq_state("OP-30", state), eq_state("OP-30", "RUN")))
    assert f"VF2-01 {label}(07:20부터)" in ask("지금 병목 어디야?")["conclusion"]


def test_a_cleared_alarm_is_not_shown(monkeypatch):
    serve(monkeypatch, twin_states(eq_state("OP-30", "IDLE", alarm={**ALARM, "cleared_at": "2026-10-25T07:50:00+09:00"}), eq_state("OP-30", "RUN")))
    c = ask("지금 병목 어디야?")["conclusion"]
    assert "VF2-01 대기(07:20부터)" in c and "알람" not in c


def test_a_machine_without_start_time_gets_no_made_up_time(monkeypatch):
    serve(monkeypatch, twin_states(eq_state("OP-30", "DOWN", since=None, alarm=ALARM), eq_state("OP-30", "RUN")))
    assert "VF2-01 고장 정지(알람 992)," in ask("지금 병목 어디야?")["conclusion"]


def test_no_equipment_info_means_no_line(monkeypatch):
    doc = twin_states(eq_state("OP-30", "DOWN"), eq_state("OP-30", "RUN"))
    doc["equipment"] = {}
    serve(monkeypatch, doc)
    c = ask("지금 병목 어디야?")["conclusion"]
    assert "설비:" not in c and c.startswith("지금 병목은 OP-30이에요")


def test_the_machine_line_comes_before_the_named_machine_sentence(monkeypatch):
    serve(monkeypatch, twin_states(eq_state("OP-30", "DOWN", alarm=ALARM), eq_state("OP-30", "RUN")))
    c = ask("VF2-01이 지금 병목이야?")["conclusion"]
    assert c.index("OP-30 설비: VF2-01 고장 정지") < c.index("VF2-01은 OP-30 공정이라") and c.endswith("지금 병목에 해당해요.")
