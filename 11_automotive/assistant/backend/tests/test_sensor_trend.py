"""센서 값 조회 `sensor_trend` 시험 (2026-10-19, 기획 `센서조회_화면안내_기획_20261019.md` 3-1·5장). 진짜 Claude·DB·팀 백엔드(8020)를 부르지 않는다 —
조회 도구는 가짜 백엔드(`tests/fake_backend.py`의 센서 7종 × VF2-01·VF2-02), Claude는 가짜 실행기(`claude_client.use_runner`).

문제: "VF2-01 센서 추세"·"VF2-01 주축 부하 괜찮아?"는 `intents: []`이라 팀 백엔드의 `sensor_trend`를 한 번도 안 부르고 문서 문장만 돌려줬다 (요구사항 FR-PRD-01-14 합격 문장이 통과하지 못함).
또 OPR·SUP는 센서 낱말만 든 문서 질문("몇 psi 필요해요?")까지 권한 밖으로 막혔다.
지키는 것: ① MNT·MGR 값 질문은 정확한 인자로 도구를 1번 부르고 문장 속 숫자 = 도구 값, psi 옆 bar(소수 1자리), 정상 범위마다 [참고], 기준 시각(공용 DB 시계), 판정 말·"지금/현재" 없음
② OPR·SUP 값 질문은 백엔드 0번 + 권한 밖 안내, 문서 질문은 막지 않음 ③ 설비 함정·기간 한도·기록 없음/도구 오류 구별 ④ 다른 의도와 겹치면 기존 의도가 이김, 문서 질문은 센서 의도로 안 감
⑤ 다듬기: 센서 전용 검사가 변형을 모두 거절 ⑥ 이어 묻기가 [참고]·bar·기준 시각을 지우지 않음 ⑦ 스위치(PURE_KEEP_SIGNALS 0/1, 외부 스위치 꺼짐).
"""
import glob
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend.chat_mapping import role_gate
from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.llm import sensor_check as SC
from backend.repositories import backend_tools as BT
from backend.services import answer as A
from backend.services import sensor as SN
from backend.tests import fake_backend as F
from backend.tests.fake_backend import KEY, FakeBackend
from backend.tools import query_tools as T

pytestmark = pytest.mark.own_backend            # 가짜 백엔드를 이 파일이 직접 준비한다
H = {"X-Service-Key": KEY}
client = TestClient(CS.app)
HERE = Path(__file__).resolve().parent
ALL = ["equipment_status", "alarms", "kpi", "production", "lot", "work_orders", "work_records", "pm_due", "tool_life", "inventory",
       "reliability", "stop_reasons", "sensor_trend", "equipment_spec"]
NO_SENSOR = [t for t in ALL if t not in ("reliability", "sensor_trend")]            # OPR·SUP: 팀 백엔드 routers/assistant.py가 빼는 두 도구
GATE = [{"tool": "reliability", "about": "MTTR·MTBF", "roles": ["MNT", "MGR"]}, {"tool": "sensor_trend", "about": "센서 데이터", "roles": ["MNT", "MGR"]}]
PROD = {k: "1" for k in ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "PARSE_V8", "PARSE_V9", "PARSE_V10", "PARSE_V11",
                         "FLOW_V9", "FLOW_V10", "BLOCKS_V2", "BLOCKS_V3")}
JUDGE_WORDS = ("이상입니다", "정상입니다", "안정적", "괜찮습니다", "안전합니다", "위험합니다", "문제 없", "양호")
NOW_WORDS = ("지금", "현재", "방금", "실시간")


@pytest.fixture
def fb(monkeypatch):
    monkeypatch.delenv("ASSISTANT_PROVIDER", raising=False)             # 앞선 시험이 환경에 남긴 공급자 값이 이 시험의 /chat을 외부 스위치 검사로 보내지 않게 (test_chat_service·test_chat_carry와 같은 방식)
    return FakeBackend().install(monkeypatch)


@pytest.fixture(params=["legacy", "prod"])
def mode(request, monkeypatch):
    """legacy = 시험 기본(낱말 규칙 옛 판, 블록 없음) / prod = 앱이 켜 두는 규칙 보강·블록 스위치 (화면 글은 번호 목록으로 풀린다)"""
    if request.param == "prod":
        for k, v in PROD.items():
            monkeypatch.setenv(k, v)
    return request.param


def post(q, role="MNT", user="U07", allowed=ALL, out_of_role=None, context=None):
    return client.post("/chat", headers=H, json={"question": q, "context": context or {}, "allowed_tools": allowed, "out_of_role": out_of_role or [],
                                                 "history": [], "user": {"user_id": user, "role_code": role}})


def lowrole(q, role="OPR", context=None):
    return post(q, role=role, user="U01", allowed=NO_SENSOR, out_of_role=GATE, context=context)


def sensor_calls(fb):
    return [c for c in fb.calls if c["tool"] == "sensor_trend"]


def sensor_lines(text):
    """답에서 "센서 이름 → 최소 … 줄" (legacy는 "- ", prod는 "1. " 머리)"""
    return {m.group(1).strip(): m.group(2) for m in re.finditer(r"^(?:\d+\. |- )?([^:\n]+): (최소 [^\n]*)$", text, re.M)}


def pairs(line):
    return {lab: float(v) for lab, v in re.findall(r"(최소|평균|최대|마지막) (-?\d+(?:\.\d+)?)", line)}


# ---------------------------------------------------------------- ① 값 답: 정확한 인자 1번, 숫자 = 도구 값
def test_requirement_sentence_calls_the_tool_once_with_exact_args(fb, mode):
    """요구사항 FR-PRD-01-14의 합격 문장 — 지금까지는 도구를 한 번도 안 불렀다 (intents [])"""
    j = post("VF2-01 주축 부하 괜찮아?").json()
    assert j["status"] == "OK" and set(j) == {"answer", "sources", "related", "status"}
    calls = sensor_calls(fb)
    assert len(calls) == 1 and fb.tools_called() == ["sensor_trend"]
    assert calls[0]["args"] == {"equipment_id": "VF2-01", "minutes": 60, "sensor_code": "SpindleLoadPct"}
    assert calls[0]["headers"] == {"X-Service-Key": KEY} and calls[0]["on_behalf_of"] == "U07"
    assert set(sensor_lines(j["answer"])) == {"주축 부하"}


@pytest.mark.parametrize("role,user", [("MNT", "U07"), ("MGR", "U09")])
def test_chip_question_returns_all_seven_sensors_for_mnt_and_mgr(fb, mode, role, user):
    j = post("VF2-01 센서 추세", role=role, user=user).json()
    assert [c["args"] for c in sensor_calls(fb)] == [{"equipment_id": "VF2-01", "minutes": 60}]        # 센서를 가리지 않으면 sensor_code를 보내지 않는다
    assert list(sensor_lines(j["answer"])) == [n for _, n, *_ in F.SENSORS]                            # 7종 전부, 마스터 순서
    assert "equipment_spec" not in fb.tools_called()


def test_every_number_in_the_answer_is_the_tool_value(fb, mode):
    ans = post("VF2-02 센서 추세").json()["answer"]
    lines = sensor_lines(ans)
    for code, name, unit, lo, hi in F.SENSORS:
        mn, av, mx, last = F.SENSOR_VALUES["VF2-02"][code]
        assert pairs(lines[name]) == {"최소": mn, "평균": av, "최대": mx, "마지막": last}, lines[name]
        assert f"정상 범위 {lo:g}~{hi:g}" in lines[name]


def test_psi_lines_carry_bar_with_one_decimal_by_the_formula(fb, mode):
    line = sensor_lines(post("VF2-01 공기 압력 알려줘").json()["answer"])["공기 압력"]
    found = re.findall(r"(\d+(?:\.\d+)?) psi\(약 (\d+\.\d) bar\)", line)
    assert len(found) == 4                                                       # 최소·평균·최대·마지막 모두 bar 병기
    for psi, bar in found:
        assert bar == f"{round(float(psi) * 0.0689476, 1):.1f}"
    assert "정상 범위 100~110 psi(약 6.9~7.6 bar) [참고]" in line               # 요구사항의 "100~110 psi(약 6.9~7.6 bar)"


def test_every_normal_range_is_tagged_reference_and_no_alarm_threshold_words(fb, mode):
    ans = post("VF2-01 센서 추세").json()["answer"]
    assert ans.count("정상 범위") == ans.count("[참고]") == 8                    # 센서 7줄 + 맺음 줄
    assert not re.search(r"알람 기준|기준값|트립", ans)                            # 알람 기준값은 내지 않는다 (DB에도 없다)


def test_clock_comes_from_the_tool_not_from_the_code(fb, mode, monkeypatch):
    monkeypatch.setattr(F, "NOW", "2026-10-02T09:30:00+09:00")
    ans = post("VF2-01 주축 부하 알려줘").json()["answer"]
    assert "2026-10-02 09:30 기준, 공용 DB 시계" in ans and "2026-10-01 08:00" not in ans


def test_unknown_clock_is_not_invented(fb, mode, monkeypatch):
    real = fb._post
    monkeypatch.setattr(fb, "_post", lambda *a, **k: {k2: v for k2, v in real(*a, **k).items() if k2 != "now"})
    monkeypatch.setattr(BT, "_post", fb._post)
    ans = post("VF2-01 주축 부하 알려줘").json()["answer"]
    assert "기준 시각은 공용 DB 시계" in ans and not re.search(r"20\d\d-\d\d-\d\d", ans)


def test_sample_count_and_last_time_come_from_the_tool(fb, mode):
    ans = post("VF2-01 모터 온도 최근 30분").json()["answer"]
    assert "직전 30분" in ans and "값 29개" in ans and "마지막 값 시각 07:59" in ans          # 창 N분의 1분 평균은 N-1개 (시계 08:00 값은 아직 없다)
    assert "분 평균" not in ans                                                              # 5초 값이 섞일 수 있어 "분 평균"이라 쓰지 않는다


@pytest.mark.parametrize("q", ["VF2-01 센서 추세", "VF2-02 모터 온도 어때?", "VF2-01 X축 부하 괜찮니", "VF2-01 센서 이상 있어?", "vf2-01 모터온도 좀 높은거 같은데 확인해줘",
                               "VF2-01 지금 주축 부하 얼마야", "VF2-02 공기 압력 정상 범위 안이야?", "VF2-01 센서 전부 보여줘"])
def test_no_verdict_words_and_no_now_words(fb, mode, q):
    ans = post(q).json()["answer"]
    assert sensor_calls(fb), q
    assert not any(w in ans for w in JUDGE_WORDS) and not any(w in ans for w in NOW_WORDS), ans
    assert not SC.JUDGE.search(ans) and not SC.NOW_WORDS.search(ans)


def test_out_of_normal_sensor_is_stated_as_a_fact_only(fb, mode):
    ans = post("VF2-01 센서 추세").json()["answer"]
    assert "정상 범위 [참고] 밖 값이 있는 센서: 주축 모터 온도" in ans                  # 가짜 값: 모터 온도 최소 27.7 < 정상 최소 28 (서 있는 설비의 식은 온도)
    assert not any(w in ans for w in JUDGE_WORDS)


def test_when_nothing_is_out_of_normal_it_says_none(fb, mode):
    fb.rows["sensor_trend"] = lambda a: [{**r, "is_out_of_normal": False} for r in F.sensor_trend_rows(a)]
    assert "정상 범위 [참고] 밖 값이 있는 센서: 없음" in post("VF2-01 센서 추세").json()["answer"]


def test_sources_are_doc_07_section_3_and_data_is_marked_synthetic(fb, mode):
    j = post("VF2-01 센서 추세").json()
    assert {"doc_no": "DOC-07", "section": "3"} == {k: j["sources"][0][k] for k in ("doc_no", "section")} and len(j["sources"]) == 1
    with BT.acting_as("U07", ALL):
        a = A.answer("VF2-01 센서 추세", "MNT", {})
    assert a["is_synthetic"] is True and a["current_data"][0]["tool"] == "센서 추세 조회"


@pytest.mark.parametrize("q,minutes", [("VF2-01 최근 30분 주축 부하 알려줘", 30), ("VF2-01 주축 모터 온도 최근 10분", 10), ("VF2-01 모터 온도 90분 추세", 90),
                                       ("VF2-01 지난 3시간 센서 추세", 180), ("VF2-02 X Y Z 축 부하 최근 2시간", 120), ("VF2-01 주축 부하 값 알려줘 (최근 3분)", 3),
                                       ("VF2-02 모터 온도 1시간 평균이랑 최대", 60), ("VF2-01 센서 한 시간", 60), ("VF2-01 센서 1시간 30분", 90),
                                       ("VF2-01 모터 온도 최근 6시간", 360), ("VF2-01 모터 온도 어때?", 60)])
def test_period_words_become_minutes(fb, mode, q, minutes):
    post(q)
    assert [c["args"]["minutes"] for c in sensor_calls(fb)] == [minutes], q


def test_xyz_axes_are_shown_without_the_other_sensors(fb, mode):
    j = post("VF2-01 X, Y, Z 축 부하 다 보여줘").json()
    assert [c["args"] for c in sensor_calls(fb)] == [{"equipment_id": "VF2-01", "minutes": 60}]        # 세 센서 → sensor_code 없이 부르고 보일 때 거른다
    assert list(sensor_lines(j["answer"])) == ["X축 부하", "Y축 부하", "Z축 부하"]


@pytest.mark.parametrize("q,code", [("VF2-01 스핀들 부하 어때?", "SpindleLoadPct"), ("vf2-01 공기압력 psi로 몇이야", "AirPressure"), ("VF2-01 직류 전압 얼마야", "DcVolt"),
                                    ("VF2-01 모터 온도 어때", "SpindleMotorTemp"), ("VF2-01 Y축 부하 괜찮니", "Yload"), ("VF2-02 압력 괜찮아?", "AirPressure")])
def test_sensor_names_including_field_words_pick_one_sensor(fb, mode, q, code):
    post(q)
    assert [c["args"].get("sensor_code") for c in sensor_calls(fb)] == [code], q


# ---------------------------------------------------------------- 설비 규칙
def test_two_equipment_ids_call_both(fb, mode):
    j = post("VF2-01, VF2-02 둘 다 센서 추세 보여줘").json()
    assert [c["args"]["equipment_id"] for c in sensor_calls(fb)] == ["VF2-01", "VF2-02"]
    assert "VF2-01 센서 (" in j["answer"] and "VF2-02 센서 (" in j["answer"]


def test_two_machines_without_ids_call_both(fb, mode):
    post("VF2 두 대 다 모터 온도 어때?")
    assert [(c["args"]["equipment_id"], c["args"]["sensor_code"]) for c in sensor_calls(fb)] == [("VF2-01", "SpindleMotorTemp"), ("VF2-02", "SpindleMotorTemp")]


@pytest.mark.parametrize("q,bad", [("VF2-03 센서 추세", "VF2-03"), ("VF2-1 센서 추세", "VF2-1"), ("VF2-001 센서 추세", "VF2-001"),
                                   ("SAW-01 모터 온도 알려줘", "SAW-01"), ("MIL-01 모터 온도 얼마야?", "MIL-01")])
@pytest.mark.parametrize("screen", [None, "VF2-01"])
def test_unresolved_or_sensorless_equipment_never_falls_back_to_the_screen_equipment(fb, mode, q, bad, screen):
    ctx = {"equipment_id": screen} if screen else None
    j = post(q, context=ctx).json()
    assert fb.calls == []                                                           # 다른 설비·다른 값으로 거짓 답하지 않는다
    assert f"물으신 설비({bad})는 센서 기록이 없어요" in j["answer"] and "센서는 OP-30 VF2-01·VF2-02만 기록해요" in j["answer"]
    assert not re.search(r"최소 \d", j["answer"])


def test_no_equipment_and_no_screen_equipment_asks_which_one(fb, mode):
    j = post("모터 온도 몇 도야").json()
    assert fb.calls == [] and j["status"] == "OK"
    assert "어느 설비의 센서인지" in j["answer"] and "OP-30 VF2-01·VF2-02" in j["answer"]


def test_screen_equipment_is_used_only_when_the_question_names_none(fb, mode):
    post("모터 온도 몇 도야", context={"equipment_id": "VF2-02", "screen": "SCR-04"})
    assert [c["args"]["equipment_id"] for c in sensor_calls(fb)] == ["VF2-02"]
    fb.calls.clear()
    post("VF2-01 모터 온도 몇 도야", context={"equipment_id": "VF2-02"})
    assert [c["args"]["equipment_id"] for c in sensor_calls(fb)] == ["VF2-01"]         # 질문에 설비 ID가 있으면 화면 설비는 쓰지 않는다


def test_screen_equipment_without_sensors_is_told_so(fb, mode):
    j = post("센서 값 보여줘", context={"equipment_id": "SAW-01"}).json()
    assert fb.calls == [] and "화면에서 고른 설비(SAW-01)는 센서 기록이 없어요" in j["answer"]


def test_alias_one_machine_resolves_like_the_rest_of_the_assistant(fb, mode):
    post("1호기 주축 부하 어때?")                                                       # parse()가 "1호기"를 VF2-01로 푸는 기존 규칙 그대로 (은행은 되묻기를 기대 — 보고서에 적음)
    assert [c["args"]["equipment_id"] for c in sensor_calls(fb)] == ["VF2-01"]


# ---------------------------------------------------------------- 기간 한도
@pytest.mark.parametrize("q", ["VF2-01 주축 부하 지난주", "VF2-01 센서 9월 30일 추세", "VF2-02 센서 추세 내일", "VF2-01 어제 야간 센서 추세", "VF2-01 센서 3시간 전", "VF2-01 모터 온도 어제"])
def test_past_or_future_periods_get_the_limit_notice_and_no_values(fb, mode, q):
    j = post(q).json()
    assert fb.calls == [] and "조회할 수 없어요" in j["answer"] and "최근 1~360분" in j["answer"]
    assert not re.search(r"최소 \d", j["answer"])
    if "9월" in q:
        assert "물으신 기간(9월 30일)" in j["answer"]                                  # 말한 기간을 통째로 되돌려 준다


@pytest.mark.parametrize("q", ["VF2-01 주축 부하 최근 하루", "VF2-01 모터 온도 361분", "VF2-01 센서 8시간 추세", "VF2-01 센서 최근 3일", "VF2-02 센서 일주일"])
def test_over_360_minutes_gets_the_limit_notice_and_no_values(fb, mode, q):
    j = post(q).json()
    assert fb.calls == [] and "한도를 넘어요" in j["answer"] and "360분" in j["answer"]


def test_zero_minutes_is_out_of_range(fb, mode):
    j = post("VF2-02 모터 온도 최근 0분").json()
    assert fb.calls == [] and "조회할 수 없어요" in j["answer"]


# ---------------------------------------------------------------- 기록 없음 vs 도구 오류
def test_no_rows_says_no_record_and_does_not_turn_into_all_clear(fb, mode):
    fb.rows["sensor_trend"] = []
    j = post("VF2-01 주축 부하 괜찮아?").json()
    assert j["status"] == "OK" and "VF2-01 센서 기록 없음" in j["answer"] and "직전 60분" in j["answer"]
    assert not re.search(r"최소 \d", j["answer"]) and not any(w in j["answer"] for w in JUDGE_WORDS) and "정상 범위 [참고] 밖" not in j["answer"]


@pytest.mark.parametrize("exc", [BT.BackendToolError("HTTP 500 http://backend.test/api/assistant/tools/sensor_trend"), BT.BackendToolError("TimeoutError")])
def test_tool_error_is_503_not_a_no_record_answer(fb, mode, exc):
    fb.fail_with = exc
    r = post("VF2-01 주축 부하 괜찮아?")
    assert r.status_code == 503
    assert r.json() == {"code": "ASSISTANT_UNAVAILABLE", "message": CS.UNAVAILABLE_MESSAGE, "detail": {"retryable": True}}
    assert "기록 없음" not in r.text and not re.search(r"backend\.test|HTTP 500|tools/sensor_trend", r.text)


# ---------------------------------------------------------------- ② 권한: OPR·SUP
VALUE_QS = ["VF2-01 주축 부하 괜찮아?", "VF2-01 센서 추세", "VF2-02 모터 온도 어때?", "모터 온도 몇 도야", "VF2-01 공기 압력 얼마야", "VF2-01 Y축 부하 괜찮니", "센서 값 보여줘",
            "VF2-01 최근 30분 주축 부하 알려줘", "VF2 두 대 다 모터 온도 어때?", "1호기 직류 전압 얼마야"]


@pytest.mark.parametrize("role", ["OPR", "SUP"])
@pytest.mark.parametrize("q", VALUE_QS)
def test_opr_sup_value_questions_never_reach_the_backend(fb, mode, role, q):
    j = lowrole(q, role=role).json()
    assert j["status"] == "OUT_OF_ROLE" and j["sources"] == [] and fb.calls == []
    assert "센서 데이터" in j["answer"] and "보전 담당자(MNT)" in j["answer"] and not any(ch.isdigit() for ch in j["answer"])


DOC_QS = ["주축 부하 정상 범위가 어떻게 돼?", "공기 압력은 몇 psi가 정상이야?", "센서 값은 얼마나 오래 보관돼?", "5초 간격 데이터는 며칠 보관해?", "센서 값은 몇 초마다 기록돼?",
          "센서 어떤 거 있어?", "직류 버스 전압이 뭐야?", "센서 값 엑셀로 내려받을 수 있어?", "공기 압력은 몇 psi 필요해요?", "에어건 압력은 얼마 이하로 써야 하나요?",
          "고전압 대기는 몇 분 기다려야 해?", "센서 1초 데이터는 얼마나 보관해?", "VF2-01 주축 부하가 몇 퍼센트 넘으면 알람 떠?", "절단기 SAW-01은 센서 기록 있어?"]


@pytest.mark.parametrize("role", ["OPR", "SUP"])
@pytest.mark.parametrize("q", DOC_QS)
def test_opr_sup_document_questions_with_sensor_words_are_not_blocked(fb, mode, role, q):
    assert role_gate(q, GATE) is None                                               # 예전에는 이 중 대부분이 낱말만 보고 막혔다
    j = lowrole(q, role=role).json()
    assert j["status"] != "OUT_OF_ROLE" and fb.calls == [], j


def test_role_gate_still_blocks_mttr_values_and_sensor_values_but_not_other_roles_questions():
    assert role_gate("VF2-01 MTTR 알려줘", GATE)["status"] == "OUT_OF_ROLE"
    assert role_gate("VF2-01 센서 추세 보여줘", GATE)["status"] == "OUT_OF_ROLE"
    assert role_gate("VF2-01 주축 부하 괜찮아?", GATE)["status"] == "OUT_OF_ROLE"            # 낱말 표에 없던 합격 문장
    assert role_gate("VF2-01 주축 부하 괜찮아?", []) is None                                 # 볼 수 있는 역할이면 막지 않는다
    assert role_gate("주축 부하 정상 범위가 어떻게 돼?", GATE) is None


def test_role_gate_does_not_crash_the_entrance_when_the_judgement_fails(monkeypatch):
    def boom(q):
        raise RuntimeError("시험: 판정 실패")
    monkeypatch.setattr(A, "parse", boom)
    assert role_gate("VF2-01 주축 부하 괜찮아?", GATE) is None          # 입구가 500이 되지 않는다 — 허용 목록에 없는 도구는 백엔드를 부르기 전에 ToolDenied로 막힌다


def test_tool_denied_without_gate_is_still_a_valueless_out_of_role_answer(fb, mode):
    j = post("VF2-01 센서 추세", role="OPR", user="U01", allowed=NO_SENSOR, out_of_role=[]).json()          # 게이트 정보가 비어 있어도 백엔드를 부르기 전에 막는다
    assert j["status"] == "OUT_OF_ROLE" and j["answer"] == CS.DENIED_ANSWER and fb.calls == []


# ---------------------------------------------------------------- ④ 문서 질문·겹침
def eval_questions():
    seen, out = set(), []
    for f in sorted(glob.glob(str(HERE.parent / "eval" / "*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except ValueError:
            continue
        items = d if isinstance(d, list) else d.get("items") or d.get("questions") or d.get("cases") or []
        for it in items if isinstance(items, list) else []:
            q = it.get("q") or it.get("question") if isinstance(it, dict) else None
            if isinstance(q, str) and q and q not in seen:
                seen.add(q)
                out.append(q)
    return out


def test_document_questions_never_get_a_sensor_intent(mode):
    for q in DOC_QS + ["센서 정상 범위 알려줘", "VF2-01 센서 기록 있어?", "공기 압력 센서가 따로 있어?", "주축 모터 온도 정상 범위는?"]:
        assert "sensor_trend" not in A.parse(q)["intents"], q


def test_parse_of_every_evaluation_question_is_unchanged_by_the_sensor_step(mode, monkeypatch):
    """S7: 평가 질문 전체(1,203개)의 parse 결과가 센서 판정을 켜고 끈 것과 같다 — 센서 값 질문 말고는 한 글자도 안 바뀐다"""
    qs = eval_questions()
    assert len(qs) > 1000
    after = [A.parse(q) for q in qs]
    assert not [q for q, p in zip(qs, after) if "sensor_trend" in p["intents"]]
    with monkeypatch.context() as m:
        m.setattr(A.SN, "is_value_question", lambda *a, **k: False)
        before = [A.parse(q) for q in qs]
    assert [(q, b) for q, a, b in zip(qs, after, before) if a != b] == []


@pytest.mark.parametrize("q,other", [("VF2-01 센서 추세랑 MTTR 알려줘", "reliability"), ("2075 알람 났을 때 센서 값도 보여줘", "alarms"),
                                     ("992 알람 이력이랑 VF2-01 축 부하 최근 1시간", "alarms"), ("LOT-2609-128-1 지금 어디까지 갔어? VF2-02 센서도 같이", "lot"),
                                     ("VF2-01 지금 상태랑 센서", "equipment_status"), ("VF2-01 가동률이랑 센서 추세 같이", "kpi"),
                                     ("VF2-01 정지 시간이랑 그동안 주축 부하", "stop_reasons"), ("VF2-01 정지 건수랑 축 부하 최근 1시간", "stop_reasons")])
def test_overlap_the_existing_intent_wins_and_the_sensor_tool_is_not_called(fb, mode, q, other):
    assert "sensor_trend" not in A.parse(q)["intents"]
    j = post(q).json()
    assert j["status"] == "OK" and "sensor_trend" not in fb.tools_called()
    if mode == "prod" or other not in ("lot", "stop_reasons", "kpi", "equipment_status"):       # 옛 낱말 규칙(legacy)은 로트 번호만으로는 조회 의도를 만들지 않는다 — 기존 동작 그대로
        assert other in fb.tools_called()


def test_mixed_value_and_range_question_gets_values_with_the_reference_range(fb, mode):
    j = post("VF2-01 주축 부하 값이랑 정상 범위도 알려줘").json()
    assert [c["args"]["sensor_code"] for c in sensor_calls(fb)] == ["SpindleLoadPct"]
    assert "정상 범위 0~185% [참고]" in j["answer"]
    assert "사내 문서" not in j["answer"] and j["answer"].count("정상 범위") == j["answer"].count("[참고]")        # 문서 표 줄(꼬리표 없는 정상 범위)·엉뚱한 점검 줄을 같이 찾지 않는다


def test_range_in_range_question_gets_only_the_sensor_sentence(fb, mode):
    ans = post("VF2-01 공기 압력 정상 범위 안이야?").json()["answer"]
    assert [c["args"]["sensor_code"] for c in sensor_calls(fb)] == ["AirPressure"]
    assert "점검" not in ans and "사내 문서" not in ans and ans.count("정상 범위") == ans.count("[참고]")


def test_alarm_threshold_question_is_not_a_sensor_value_question(fb, mode):
    j = post("VF2-01 주축 부하가 몇 퍼센트 넘으면 알람 떠?").json()
    assert fb.calls == [] and "sensor_trend" not in A.parse("VF2-01 주축 부하가 몇 퍼센트 넘으면 알람 떠?")["intents"]
    assert j["status"] in ("OK", "NOT_IN_DOCS")


@pytest.mark.parametrize("q", ["VF2-01 절삭유 온도 어때", "VF2-01 윤활 압력 괜찮아?", "VF2-01 공구 부하 어때", "VF2-01 정비 전에 공기 압력 확인해야 해?",
                               "세척기 온도가 몇 도로 돼 있어?", "전원 끈 뒤에 전압이 빠질 때까지 얼마나 기다려?", "이거 뜰 땐 공장 공기가 최소 몇 psi는 들어와야 돼요?"])
def test_other_things_with_sensor_like_words_are_not_sensor_values(mode, q):
    assert "sensor_trend" not in A.parse(q)["intents"], q


@pytest.mark.parametrize("q", ["VF2-01 주축 부하 정상이야?", "VF2-01 센서 문제 없어?", "VF2-02 모터 온도 확인해줘"])
def test_verdict_or_check_style_questions_get_values_and_no_verdict(fb, mode, q):
    ans = post(q).json()["answer"]
    assert len(sensor_calls(fb)) == 1 and "[참고]" in ans
    assert not SC.JUDGE.search(ans) and "조작" not in ans


# ---------------------------------------------------------------- 질문 이해 단위 (services/sensor.py)
@pytest.mark.parametrize("q,expect", [("어제 야간", "past"), ("지난주", "past"), ("9월 30일", "past"), ("내일", "past"), ("3시 30분", "past"), ("3시간 전", "past"),
                                      ("8시간", "over"), ("최근 하루", "over"), ("361분", "over"), ("최근 0분", "bad"), ("최근 360분", "ok"), ("10분", "ok"),
                                      ("2시간 반", "ok"), ("세 시간", "ok"), ("삼십 분", "ok"), ("그냥 센서", "default"), ("VF2-01 센서", "default")])
def test_period_kinds(q, expect):
    kind, minutes, _ = SN.period(q)
    assert kind == expect, (q, kind, minutes)
    if kind == "ok":
        assert 1 <= minutes <= 360


def test_equipment_id_digits_are_not_read_as_a_period():
    assert SN.period("VF2-01 주축 부하 괜찮아?") == ("default", 60, "")                    # "01 주"를 1주로 읽지 않는다
    assert SN.period("VF2-02 센서 시험")[0] == "default"


# ---------------------------------------------------------------- 번역 함수 (query_tools.sensor_trend)
def test_tool_translation_checks_input_and_marks_unknown_clock(fb):
    with BT.acting_as("U07", ALL):
        r = T.sensor_trend("MNT", "VF2-01", 30, "AirPressure")
        assert r["tool"] == "센서 추세 조회" and r["clock_known"] is True and r["minutes"] == 30 and len(r["rows"]) == 1
        assert fb.calls[-1]["args"] == {"equipment_id": "VF2-01", "minutes": 30, "sensor_code": "AirPressure"}
        for bad in (0, 361, "60", None, True, 1.5):
            with pytest.raises(T.ToolInputError):
                T.sensor_trend("MNT", "VF2-01", bad)
        with pytest.raises(T.ToolInputError):
            T.sensor_trend("MNT", "VF2-09", 60)
        with pytest.raises(T.ToolInputError):
            T.sensor_trend("MNT", None, 60)


def test_tool_is_denied_before_the_backend_when_not_allowed(fb):
    with BT.acting_as("U01", NO_SENSOR):
        with pytest.raises(BT.ToolDenied):
            T.sensor_trend("OPR", "VF2-01", 60)
    assert fb.calls == []


# ---------------------------------------------------------------- ⑤ 다듬기 검사
PHRASE_FLAGS = {"LLM_ENABLED": "1", "LLM_JOBS": "write", "EXTERNAL_LLM_APP": "1", "ASSISTANT_PROVIDER": "claude"}
SONNET = "claude-sonnet-5-5"


class PhraseRunner:
    """가짜 Claude: 다듬기 요청(`conclusion` 칸)의 기본 문장을 받아 transform한 글을 돌려준다."""

    def __init__(self, transform):
        self.transform, self.calls = transform, []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        assert tuple(sch["properties"]) == ("conclusion",), sch
        draft = stdin_text.split("기본 문장:\n", 1)[1].split("\n\n지난 답은")[0]
        self.calls.append(draft)
        res = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1, "total_cost_usd": 0.01,
               "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": {"conclusion": self.transform(draft)}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(res, ensure_ascii=False), stderr="")


@pytest.fixture
def polish(fb, monkeypatch):
    for k, v in PHRASE_FLAGS.items():
        monkeypatch.setenv(k, v)
    yield
    CC.use_runner(None)


def ask(q, transform=None, role="MNT"):
    """(답, 가짜 Claude). transform이 None이면 Claude를 끈 채 (프로그램 문장)."""
    runner = PhraseRunner(transform) if transform else None
    CC.use_runner(runner)
    with BT.acting_as("U07", ALL), EXT.external_request("claude" if transform else None):
        return A.answer(q, role, {}), runner


Q7 = "VF2-01 센서 추세"          # 1줄 머리 + 7줄 + 맺음 (1200자 안쪽이라 다듬기 대상)


def swap_values(d):
    return d.replace("평균 0.86%", "평균 @@").replace("평균 0.31%", "평균 0.86%").replace("평균 @@", "평균 0.31%")


VARIANTS = {
    "[참고] 전부 지움": lambda d: d.replace(" [참고]", ""),
    "[참고] 하나만 지움": lambda d: d.replace(" [참고]", "", 1),
    "bar 병기 지움": lambda d: re.sub(r"\(약 [\d.~]+ bar\)", "", d),
    "숫자 바꿈": lambda d: d.replace("평균 105.81", "평균 105.18"),
    "센서 한 줄 뺌": lambda d: re.sub(r"^- X축 부하:.*\n", "", d, flags=re.M),
    "기준 시각 지움": lambda d: d.replace("2026-10-01 08:00 기준, 공용 DB 시계", ""),
    "공용 DB 시계만 지움": lambda d: d.replace("공용 DB 시계", "시스템"),
    "'이상입니다' 더함": lambda d: d + "\n주축 모터 온도는 이상입니다.",
    "'정상입니다' 더함": lambda d: d + "\n모든 센서가 정상입니다.",
    "'안정적' 더함": lambda d: d + "\n전반적으로 안정적인 상태예요.",
    "'괜찮습니다' 더함": lambda d: d + "\n괜찮습니다.",
    "'위험합니다' 더함": lambda d: d + "\n계속 두면 위험합니다.",
    "'정상 범위 안에 있어요' 더함": lambda d: d + "\n나머지는 정상 범위 안에 있어요.",
    "'지금' 끼움": lambda d: d.replace("직전 60분", "지금 직전 60분"),
    "'현재' 끼움": lambda d: "현재 " + d,
    "값 짝을 맞바꿈": swap_values,
    "센서 이름을 바꿈": lambda d: d.replace("주축 부하:", "스핀들 부하:"),
    "맺음 줄을 뺌": lambda d: d.replace("\n정상 범위 [참고] 밖 값이 있는 센서: 주축 모터 온도", ""),
}


@pytest.mark.parametrize("name", list(VARIANTS))
def test_every_bad_polish_is_rejected_and_the_program_sentence_is_used(polish, name):
    base, _ = ask(Q7)
    assert "[참고]" in base["conclusion"]
    a, runner = ask(Q7, VARIANTS[name])
    assert runner.calls, "다듬기가 불리지 않았다"
    assert a["conclusion"] == base["conclusion"], name
    assert a["llm_trace"][0]["used"] is False and a["llm_trace"][0]["reason"], (name, a["llm_trace"])
    assert len(runner.calls) <= 2                                                   # 거부 사유를 붙여 한 번만 다시 요청한다 (retries=1)


@pytest.mark.parametrize("name,fn", [("줄 순서를 뒤집음", lambda d: "\n".join([d.split("\n")[0]] + d.split("\n")[1:-1][::-1] + [d.split("\n")[-1]])),
                                     ("구분점을 쉼표로", lambda d: d.replace(" · ", ", ")),
                                     ("앞에 안내 한 줄", lambda d: "아래는 센서 값이에요.\n" + d)])
def test_harmless_polish_is_accepted(polish, name, fn):
    a, runner = ask(Q7, fn)
    assert a["llm_trace"][0]["used"] is True and a["conclusion"] == fn(ask(Q7)[0]["conclusion"]), name
    assert len(runner.calls) == 1


def test_long_answers_are_not_polished(polish):
    a, runner = ask("VF2-01, VF2-02 둘 다 센서 추세 보여줘", lambda d: d)             # 설비 2대 × 7센서는 1200자를 넘는다
    assert len(a["conclusion"]) > 1200 and runner.calls == []


@pytest.mark.parametrize("draft,text,reason", [
    ("A: 최소 1% (정상 범위 0~5% [참고])", "A: 최소 1% (정상 범위 0~5%)", "빠진 꼬리표"),
    ("공기 압력 (약 7.1 bar)", "공기 압력 7.1", "빠진 꼬리표"),
    ("공용 DB 시계 기준", "시스템 기준", "빠진 꼬리표"),
    ("- 주축 부하: 최소 1% · 평균 2%", "주축 부하는 이상입니다. 최소 1% · 평균 2%", "판정 말"),
    ("기준 시각 직전 60분", "지금 기준 시각 직전 60분", "시점 말"),
    ("VF2-01 센서\n- 주축 부하: 최소 1% · 평균 2%\n- 공기 압력: 최소 3% · 평균 4%", "VF2-01 센서\n- 공기 압력: 최소 3% · 평균 4%", "빠진 센서"),
    ("VF2-01 센서\n- 주축 부하: 최소 1% · 평균 2%\n- 공기 압력: 최소 3% · 평균 4%",
     "VF2-01 센서\n- 주축 부하: 최소 3% · 평균 4%\n- 공기 압력: 최소 1% · 평균 2%", "짝이 어긋남")])
def test_sensor_check_rules_one_by_one(draft, text, reason):
    got = SC.check(text, draft)
    assert got and reason in got, got
    assert SC.check(draft, draft) is None                                          # 초안 자신은 늘 통과


def test_sensor_check_binds_values_per_equipment_block():
    d = ("VF2-01 센서 (x)\n- 주축 부하: 최소 1% · 평균 2%\nVF2-02 센서 (x)\n- 주축 부하: 최소 5% · 평균 6%")
    assert SC.check(d, d) is None
    swapped = ("VF2-01 센서 (x)\n- 주축 부하: 최소 5% · 평균 6%\nVF2-02 센서 (x)\n- 주축 부하: 최소 1% · 평균 2%")
    assert "어긋남" in (SC.check(swapped, d) or "")


# ---------------------------------------------------------------- ⑥ 이어 묻기
@pytest.fixture
def follow(fb, monkeypatch):
    CS._prev.clear()
    monkeypatch.setenv("FOLLOWUP", "1")
    for k, v in PROD.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("FOLLOWUP_V2", "1")
    yield
    CS._prev.clear()
    CC.use_runner(None)


@pytest.mark.parametrize("followup", ["방금 내용 쉽게 설명해줘", "방금 내용 짧게 줄여줘"])
def test_easy_or_short_follow_up_keeps_reference_tags_bar_and_clock(follow, fb, followup):
    CC.use_runner(PhraseRunner(lambda d: d))                                         # 불리면 호출 수로 드러난다
    j1 = post("VF2-01 공기 압력 알려줘").json()
    assert "[참고]" in j1["answer"] and "bar" in j1["answer"] and "공용 DB 시계" in j1["answer"]
    assert CS._prev["U07"][1]["sensor"] is True
    j2 = post(followup).json()
    for keep in ("[참고]", "bar", "공용 DB 시계", "정상 범위 100~110 psi(약 6.9~7.6 bar)"):
        assert keep in j2["answer"], (followup, j2["answer"])
    assert "센서 값 답" in j2["answer"] and "원문 그대로" in j2["answer"]                # 바꿔 쓰지 않고 앞 답 그대로
    assert len(sensor_calls(fb)) == 1                                                  # 이어 묻기에서 도구를 다시 부르지 않았다


def test_again_follow_up_asks_the_tool_again(follow, fb):
    post("VF2-01 공기 압력 알려줘")
    post("다시 알려줘")
    assert len(sensor_calls(fb)) == 2


# ---------------------------------------------------------------- ⑦ 스위치
@pytest.mark.parametrize("keep", ["0", "1"])
def test_external_switch_off_is_still_503_for_sensor_questions(fb, monkeypatch, keep):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    monkeypatch.setenv("PURE_KEEP_SIGNALS", keep)
    r = post("VF2-01 주축 부하 괜찮아?")
    assert r.status_code == 503 and fb.calls == []


SENSOR_ROUTE_QS = ["VF2-01 센서 추세", "VF2-01 주축 부하 괜찮아?", "VF2-02 모터 온도 어때?", "VF2-01 공기 압력 얼마야", "VF2-01 최근 30분 주축 부하 알려줘", "모터 온도 몇 도야",
                   "VF2-01 센서 8시간 추세", "VF2-03 센서 추세", "VF2 두 대 다 모터 온도 어때?", "공기 압력 몇 psi야", "VF2 두 대 주축 부하 비교해줘"]


@pytest.mark.parametrize("keep,expect_ops", [("1", True), ("0", False)])
@pytest.mark.parametrize("q", SENSOR_ROUTE_QS)
def test_keep_signals_decides_whether_the_sensor_road_is_taken(fb, monkeypatch, keep, expect_ops, q):
    """PURE_KEEP_SIGNALS=1일 때만 센서 길(운영 조회)이 선다. 0이면 모든 질문이 순수 문서 길 (팀원 .env에 1이 필요 — 예시 파일 기본 0).
    PURE_SAFETY·RULE·FAULT가 켜져 있어도 센서 값 질문을 문서 길로 가로채지 않는다 (예전에는 "VF2-01 센서 추세"가 설비 이름뿐인 안전 질문으로 가로채였다)."""
    for k in ("PURE_EXTERNAL", "EXTERNAL_LLM_APP", "LLM_ENABLED", "PURE_SAFETY", "PURE_RULE", "PURE_RULE_WIDE", "PURE_FAULT", "PURE_FAULTDOC"):
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("PURE_KEEP_SIGNALS", keep)
    p = A.parse(q)
    p["raw"] = q
    with EXT.external_request("claude"):
        why = A.pure_scope_v19(p, A.settings(), q)
    assert (why is None) is expect_ops, (q, why)


def test_through_the_app_road_with_keep_signals_the_tool_is_called(fb, monkeypatch):
    for k, v in {**PHRASE_FLAGS, "PURE_EXTERNAL": "1", "PURE_KEEP_SIGNALS": "1", "PURE_SAFETY": "1"}.items():
        monkeypatch.setenv(k, v)
    CC.use_runner(PhraseRunner(lambda d: d))
    try:
        j = post("VF2-01 센서 추세").json()
    finally:
        CC.use_runner(None)
    assert fb.tools_called() == ["sensor_trend"] and "정상 범위 [참고] 밖 값이 있는 센서" in j["answer"]


def test_no_new_env_switch_was_added():
    text = (HERE.parent.parent / ".env.example").read_text(encoding="utf-8") if (HERE.parent.parent / ".env.example").exists() else ""
    assert "SENSOR" not in text.upper().replace("SENSOR_TREND", "")
