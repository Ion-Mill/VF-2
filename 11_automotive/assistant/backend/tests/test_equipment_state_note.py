"""설비 상태 질문에 시연 서버 값 재료 붙이기 (2026-10-25, 지시문 방식) 필수 시험 — 진짜 Claude·네트워크·DB·시연 서버를 부르지 않는다 (가짜 `claude` 실행기·가짜 시연 서버 값).

문제: "고장은 어디야?"·"지금 설비 상태"는 낱말표에 없어 문서 길로 가 "상태 기록이 없다"고 답했다.
지키는 것: 설비 상태 질문에는 시연 서버의 지금 설비 상태 표와 쓰는 법을 Claude 시스템 지시 끝에 붙이고, 그 밖의 질문에는 붙이지 않는다. 값을 못 읽으면 붙이지 않고 예전 길 그대로다.
Claude가 값을 맞게 옮기는지는 이 시험이 보지 않는다 (진짜 Claude로 사람이 확인한다).
"""
import json
from types import SimpleNamespace

import pytest

from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.repositories import backend_tools as BT
from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON
from backend.tools import query_tools as T
from backend.tools import sim_live

HAIKU = "claude-haiku-5-5"      # 앱의 외부 요청은 Haiku 5.5 + 노력 단계 medium으로 부른다 (config.py claude_model·claude_effort) — 가짜 실행기도 그 이름으로 답하고, 받은 명령줄의 모델·노력 단계를 시험이 확인한다


def eq(proc, state, since="2026-10-25T07:20:00+09:00", alarm=None):
    return {"process_code": proc, "state_code": state, "since_at": since, "minutes": 30.0, "alarm": alarm}


TWIN = {"clock": {"sim_at": "2026-10-25T09:00:00+09:00"},
        "equipment": {"SAW-01": eq("OP-10", "RUN"), "MIL-01": eq("OP-20", "RUN"), "VF2-01": eq("OP-30", "DOWN", alarm={"alarm_code": "992", "severity": "STOP", "cleared_at": None}),
                      "VF2-02": eq("OP-30", "IDLE"), "WSH-01": eq("OP-40", "BLOCKED"), "CMM-01": eq("OP-50", "RUN")}}

POSITIVE = ["고장은 어디야?", "지금 설비 상태", "지금 설비 상태 알려줘", "지금 설비 어때?", "설비 상태 알려줘", "지금 고장 난 설비가 어디야?",
            "지금 멈춰 있는 설비 있어?", "어떤 설비가 멈췄어?", "지금 VF2-01 상태 어때?", "지금 고장 난 설비 있어?", "고장 난 곳이 어디야?", "지금 정지한 설비 알려줘"]
NEGATIVE = ["병목이 뭐야?", "지금 병목 어디야?", "고장 났을 때 어떻게 해?", "VF2-01 정비 상태는?", "어제 VF2-01 몇 번 멈췄어?", "정지 이력 보여줘", "362 알람 뭐야?",
            "설비 상태는 어떻게 구분해?", "고장 원인이 뭐야?", "예방 정비 기한 언제야?", "LOT-2609-041-1 어디까지 갔어?", "재고 부족한 품목 있어?",
            "오늘 VF2-01 멈춘 적 있어?", "이번 교대 고장 난 설비 알려줘"]


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    for k, v in {"SENSOR_LIVE": "1", "PURE_EXTERNAL": "1", "PURE_KEEP_SIGNALS": "1", "EXTERNAL_LLM_APP": "1", "LLM_ENABLED": "1", "PURE_TOPK": "8", "STEP_LOG": "0"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sim_live, "fetch_states", lambda url, equipment_id=None: sim_live.parse_states(TWIN, equipment_id))
    yield
    CC.use_runner(None)


class Runner:
    """가짜 `claude` 실행기 — 시스템 지시와 사용자 글을 기록하고 정해진 답을 돌려준다."""

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"system": cmd[cmd.index("--system-prompt") + 1], "user": stdin_text, "model": cmd[cmd.index("--model") + 1], "effort": cmd[cmd.index("--effort") + 1]})
        payload = {"answer": "시연 화면 시계 2026-10-25 09:00 기준, VF2-01이 고장 정지예요.", "cited": [], "insufficient": False}
        out = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1, "total_cost_usd": 0.01,
               "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {HAIKU: {"inputTokens": 10}}, "structured_output": payload}
        return SimpleNamespace(returncode=0, stdout=json.dumps(out, ensure_ascii=False), stderr="")


def ask_external(q, role="MNT"):
    r = Runner()
    CC.use_runner(r)
    with EXT.external_request("claude"):
        a = A.answer(q, role, {"new_chat": "1"})
    a.pop("_followup", None)
    return a, r


# ------------------------------------------------------------------ 감지
@pytest.mark.parametrize("q", POSITIVE)
def test_state_questions_get_the_live_values(q):
    assert A.equipment_state_question_v36(q, A.parse(q)), q


@pytest.mark.parametrize("q", NEGATIVE)
def test_other_questions_do_not(q):
    assert not A.equipment_state_question_v36(q, A.parse(q)), q


# ------------------------------------------------------------------ 값 표 글
def test_note_lists_each_machine_and_only_the_stopped_ones_get_time_and_alarm():
    note = A.equipment_states_note_v36(T.equipment_states_now("MNT"))
    assert "2026-10-25 09:00 기준 시연 화면 시계" in note
    assert "- VF2-01 (OP-30): 고장 정지 (07:20부터, 열린 알람 992)" in note
    assert "- VF2-02 (OP-30): 대기 (07:20부터)" in note and "- WSH-01 (OP-40): 막힘 (07:20부터)" in note
    assert "- SAW-01 (OP-10): 가공 중\n" in note and "- CMM-01 (OP-50): 가공 중\n" in note
    assert note.rstrip().endswith("이 값을 쓰지 않는다.") and "insufficient는 false" in note
    assert "'시연 화면 시계 2026-10-25 09:00 기준'을 위 글자 그대로(연도 포함)" in note and "{clock}" not in note      # 시계 글자를 박아 둔다 (연도 오기 방지)
    assert "대기인 설비를 '가동 중'이라고 부르지 않고" in note


def test_tool_is_none_when_off_or_unreadable_and_denied_without_line_view(monkeypatch):
    monkeypatch.setenv("SENSOR_LIVE", "0")
    assert T.equipment_states_now("MNT") is None
    monkeypatch.setenv("SENSOR_LIVE", "1")
    monkeypatch.setattr(sim_live, "fetch_states", lambda url, equipment_id=None: None)
    assert T.equipment_states_now("MNT") is None
    with BT.acting_as("U01", ["alarms"]):
        with pytest.raises(BT.ToolDenied):
            T.equipment_states_now("OPR")


# ------------------------------------------------------------------ Claude 요청에 실리는지 (가짜 실행기)
def test_the_values_and_rules_go_into_the_claude_system_prompt():
    a, r = ask_external("고장은 어디야?")
    assert (r.calls[0]["model"], r.calls[0]["effort"]) == (HAIKU, "medium")      # 앱 외부 요청 = Haiku 5.5 medium
    assert len(r.calls) == 1 and "[지금 설비 상태 — 시연 서버가 준 값" in r.calls[0]["system"] and "VF2-01 (OP-30): 고장 정지" in r.calls[0]["system"]
    assert a["status"] == "답변" and a["conclusion"].startswith("시연 화면 시계") and a["is_synthetic"] and a["current_data"][0]["tool"] == "설비 상태 조회"


def test_a_document_question_gets_no_values():
    a, r = ask_external("쿨런트가 뭐야?")
    assert len(r.calls) == 1 and "[지금 설비 상태" not in r.calls[0]["system"]


def test_unreadable_demo_server_keeps_the_old_path(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_states", lambda url, equipment_id=None: None)
    a, r = ask_external("고장은 어디야?")
    assert all("[지금 설비 상태" not in c["system"] for c in r.calls)      # 값을 못 읽으면 아무것도 안 붙인다 (예전 길이 답한다)


def test_switch_off_keeps_the_old_path(monkeypatch):
    monkeypatch.setenv("SENSOR_LIVE", "0")
    a, r = ask_external("고장은 어디야?")
    assert all("[지금 설비 상태" not in c["system"] for c in r.calls)
