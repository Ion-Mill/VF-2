"""병목 질문 지시문 방식 (2026-10-25, A안) 시험 — 진짜 Claude·네트워크·DB·시연 서버를 부르지 않는다 (가짜 `claude` 실행기·가짜 시연 서버 값).

지키는 것: 지금 병목 값 질문은 말투와 상관없이 시연 서버의 병목 값 + 설비 상태 재료와 지시문이 Claude 시스템 지시에 실리고(외부 Claude 요청일 때),
지난 병목·병목으로 잃은 개수·시연 서버를 못 읽음은 Claude를 부르지 않는 고정 안내이며, 뜻·방법 질문은 값 재료를 붙이지 않는다.
외부 Claude 요청이 아니면 예전 프로그램 문장 그대로다. 진짜 Claude가 값을 맞게 옮기는지는 이 시험이 보지 않는다 (말투별 전체 테스트 스크립트로 사람이 확인한다).
"""
import json
from types import SimpleNamespace

import pytest

from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON
from backend.tools import sim_live

HAIKU = "claude-haiku-5-5"      # 앱 외부 요청 = Haiku 5.5 + medium (config.py) — 가짜 실행기도 그 이름으로 답한다


def eq(proc, state, since="2026-10-25T07:20:00+09:00", alarm=None):
    return {"process_code": proc, "state_code": state, "since_at": since, "minutes": 30.0, "alarm": alarm}


ALARM = {"alarm_code": "992", "severity": "STOP", "cleared_at": None}
TWIN = {"clock": {"sim_at": "2026-10-25T09:00:00+09:00"},
        "bottleneck": {"process_code": "OP-30", "cause_code": "FAILURE", "alarm_event_id": 294, "since_at": "2026-10-24T09:35:00+09:00"},
        "equipment": {"SAW-01": eq("OP-10", "IDLE"), "MIL-01": eq("OP-20", "IDLE"), "VF2-01": eq("OP-30", "DOWN", "2026-10-24T09:35:00+09:00", ALARM),
                      "VF2-02": eq("OP-30", "IDLE"), "WSH-01": eq("OP-40", "IDLE"), "CMM-01": eq("OP-50", "IDLE")}}

# 말투별 지금 값 질문 (스크립트 병목지시문_말투별_테스트와 같은 집합)
NOW = ["병목 어디야", "지금 병목 뭐야", "병목 어느 공정?", "병목 걸린 데 어디", "병목 풀렸어", "지금 병목이 어느 공정인지 알려 주시겠어요?", "현재 병목 공정이 어디인지 확인 부탁드립니다.",
       "병목이 어디서 생기고 있는지 궁금합니다.", "야 지금 어디가 제일 막혀?", "라인 어디서 막히고 있냐", "지금 어느 쪽이 병목이냐", "병목 지금 어디서 터졌어?", "지금병목어디야", "병목어디냐",
       "병목이어디야?", "현재병목공정?", "VF2-01이 병목이야?", "병목 때문에 VF2-02가 멈춘 거야?", "OP-30이 지금도 병목이야?",
       "오늘 아침부터 라인이 느린 것 같은데 지금 병목이 어디서 생기고 있는지 알려줄래?", "생산이 밀리는 것 같아서 그러는데 현재 병목 공정이랑 원인이 뭔지 알려 줘",
       "지금 병목 어디야?", "지금 병목어디야?", "현재 병목 공정이 어디예요?", "병목 공정 어디야", "지금 어느 공정이 병목이야?", "지금 병목 공정 알려줘",
       "지금 병목으로 표시된 공정이 어디예요? 검사 쪽인가요?", "지금 라인에서 제일 막히는 곳이 어디야?", "라인이 어디서 막혀?", "지금 병목이 OP-30이야?", "병목이 풀렸어?",
       "병목 언제부터 그랬어?", "지금 병목 원인이 뭐야?", "병목어디서 발생해?", "VF2-01이 지금 병목이야?", "VF2-02 때문에 병목 생겼어?",
       "지금 어느 공정이 제일 느려?", "지금 라인 속도를 정하는 공정이 어디야?", "가장 느려진 공정 어디야"]      # 병목 낱말 없이 같은 뜻으로 묻는 말
PAST = ["어제 병목 어디였어?", "병목 몇 번 바뀌었는지 알려줘", "이번 교대 병목 이동 기록 보여줘", "병목이 어디로 옮겨 갔어?", "최근 병목 이동 기록 보여줘", "병목이 몇 번 바뀌었어?",
        "이번 교대 병목 구간 알려줘", "어제 야간에 병목이 어디였어?", "어제 병목 원인이 뭐였어?", "지난주 병목 공정이 어디였어?"]
LOSS = ["오늘 병목 때문에 잃은 개수는?", "병목 때문에 몇 개 잃었어?"]
DOC = ["병목이 뭐예요?", "병목 생기면 어떻게 해야 돼?", "병목 판단은 뭘로 해?", "병목이 뭐야?", "병목은 어떻게 판단해?", "병목 원인이 뭐야?", "병목 조치 방법은?",
       "병목 걸리면 누가 뭘 해?", "병목이랑 고장은 뭐가 달라?", "병목 원인 쉽게 설명해", "병목이란?",
       "지금 병목 어떻게 풀어?", "병목은 속도 손실이야 고장 손실이야?", "병목 이동 알림은 언제 떠?", "OP-30이 왜 병목이야?"]
OOS = ["재공이 제일 많이 쌓인 구간이 어디야?", "제일 느린 설비 알려줘", "LOT-2609-041-1 때문에 병목이 OP-50으로 갔어?"]


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    for k, v in {"SENSOR_LIVE": "1", "PURE_EXTERNAL": "1", "PURE_KEEP_SIGNALS": "1", "EXTERNAL_LLM_APP": "1", "LLM_ENABLED": "1", "PURE_TOPK": "8", "STEP_LOG": "0"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: sim_live.parse_bottleneck(TWIN))
    yield
    CC.use_runner(None)


class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"system": cmd[cmd.index("--system-prompt") + 1], "user": stdin_text, "model": cmd[cmd.index("--model") + 1], "effort": cmd[cmd.index("--effort") + 1]})
        payload = {"answer": "시연 화면 시계 2026-10-25 09:00 기준 병목은 OP-30이에요.", "cited": [], "insufficient": False}
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


def kind(q):
    return A.bottleneck_kind_v35(q, A.parse(q))


# ------------------------------------------------------------------ 말투별 질문 가르기
@pytest.mark.parametrize("q", NOW)
def test_now_questions_in_every_tone(q):
    assert kind(q) == "now", q


@pytest.mark.parametrize("q", PAST)
def test_past_questions(q):
    assert kind(q) == "past", q


@pytest.mark.parametrize("q", LOSS)
def test_loss_questions(q):
    assert kind(q) == "loss", q


@pytest.mark.parametrize("q", DOC + OOS)
def test_meaning_method_and_out_of_scope_are_left_alone(q):
    assert kind(q) is None, q


# ------------------------------------------------------------------ 값 재료 글
def test_note_has_bottleneck_values_equipment_states_and_pinned_clock():
    note = A.bottleneck_note_v37({"rows": [sim_live.parse_bottleneck(TWIN) | {"sim_at": None}], "as_of": "2026-10-25T09:00:00+09:00"})
    assert "[지금 병목 — 시연 서버가 준 값, 2026-10-25 09:00 기준 시연 화면 시계]" in note
    assert "- 병목 공정: OP-30" in note and "- 병목 원인: 고장" in note and "10/24 09:35부터" in note
    assert "- VF2-01 (OP-30): 고장 정지 (10/24 09:35부터, 30분째, 열린 알람 992)" in note and "- VF2-02 (OP-30): 대기 (07:20부터, 30분째)" in note and "- CMM-01 (OP-50): 대기 (07:20부터, 30분째)" in note
    assert "'시연 화면 시계 2026-10-25 09:00 기준'을 위 글자 그대로(연도 포함)" in note and "{clock}" not in note
    assert "대기인 설비를 '가동 중'이라고 부르지 않는다" in note and "insufficient는 false" in note and note.rstrip().endswith("이 값을 쓰지 않는다.")


def test_note_for_the_base_bottleneck_names_the_rule():
    doc = {**TWIN, "bottleneck": {"process_code": "OP-30", "cause_code": "BASE", "alarm_event_id": None, "since_at": None}}
    note = A.bottleneck_note_v37({"rows": [sim_live.parse_bottleneck(doc)], "as_of": "2026-10-25T09:00:00+09:00"})
    assert "- 병목 원인: 기준 병목" in note and "병목 기록이 이 상태가 된 시각" not in note and "기준 병목(OP-30)으로 표시된 것" in note


# ------------------------------------------------------------------ Claude 요청에 실리는지 (가짜 실행기)
@pytest.mark.parametrize("q", ["병목 어디야", "야 지금 어디가 제일 막혀?", "VF2-01이 병목이야?", "생산이 밀리는 것 같아서 그러는데 현재 병목 공정이랑 원인이 뭔지 알려 줘"])
def test_now_question_sends_values_and_rules_to_claude(q):
    a, r = ask_external(q)
    assert len(r.calls) == 1 and (r.calls[0]["model"], r.calls[0]["effort"]) == (HAIKU, "medium")
    sysmsg = r.calls[0]["system"]
    assert "[지금 병목 — 시연 서버가 준 값" in sysmsg and "- 병목 공정: OP-30" in sysmsg and "VF2-01 (OP-30): 고장 정지" in sysmsg
    assert a["status"] == "답변" and a["mode"].startswith("외부 LLM") and a["is_synthetic"] and a["current_data"][0]["tool"] == "병목 조회"


@pytest.mark.parametrize("q", ["어제 병목 어디였어?", "병목이 몇 번 바뀌었어?", "이번 교대 병목 이동 기록 보여줘"])
def test_past_question_is_the_fixed_notice_and_claude_is_not_called(q):
    a, r = ask_external(q)
    assert r.calls == [] and a["conclusion"] == A.BN_PAST_NOTE_V35 and a["status"] == "확인 필요"


@pytest.mark.parametrize("q", LOSS)
def test_loss_question_is_the_fixed_notice_and_claude_is_not_called(q):
    a, r = ask_external(q)
    assert r.calls == [] and a["conclusion"] == A.SPEED_LOSS_NOTE_V24


@pytest.mark.parametrize("q", ["병목이 뭐야?", "병목은 어떻게 판단해?", "병목이란?"])
def test_meaning_question_goes_to_the_document_path_without_values(q):
    a, r = ask_external(q)
    assert len(r.calls) == 1 and "[지금 병목" not in r.calls[0]["system"]


def test_unreadable_demo_server_is_the_fixed_notice_and_claude_is_not_called(monkeypatch):
    monkeypatch.setattr(sim_live, "fetch_bottleneck", lambda url: None)
    a, r = ask_external("병목 어디야")
    assert r.calls == [] and a["conclusion"] == A.BN_UNREAD_NOTE_V35 and a["status"] == "확인 필요"


def test_switch_off_is_the_fixed_notice(monkeypatch):
    monkeypatch.setenv("SENSOR_LIVE", "0")
    a, r = ask_external("병목 어디야")
    assert r.calls == [] and a["conclusion"] == A.BN_UNREAD_NOTE_V35


def test_a_non_external_request_keeps_the_program_sentence():
    CC.use_runner(Runner())
    a = A.answer("병목 어디야", "MNT", {"new_chat": "1"})
    assert a["mode"].startswith("규칙 (지금 병목") and a["conclusion"].startswith("지금 병목은 OP-30이에요") and "OP-30 설비: VF2-01 고장 정지" in a["conclusion"]
