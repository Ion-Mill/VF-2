"""POST /chat 운영 데이터 질문 시험 — 가짜 백엔드(조회 도구 14개의 열 모양)로 끝에서 끝까지 ([11_automotive 이식 2026-10-16]).

실제 DB·백엔드·LLM을 부르지 않는다. 조회 도구가 어떤 사용자 이름으로, 어떤 도구만, 어떤 키로 불렸는지도 본다.
"""
import re

import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend.repositories import backend_tools as BT
from backend.tests.fake_backend import KEY, FakeBackend

pytestmark = pytest.mark.own_backend            # 가짜 백엔드를 이 파일이 직접 준비한다 (conftest의 기본을 끈다)
H = {"X-Service-Key": KEY}
client = TestClient(CS.app)
ALL = ["equipment_status", "alarms", "kpi", "production", "lot", "work_orders", "work_records", "pm_due", "tool_life", "inventory",
       "reliability", "stop_reasons", "sensor_trend", "equipment_spec"]
NO_RELIABILITY = [t for t in ALL if t not in ("reliability", "sensor_trend")]
MTTR_GATE = [{"tool": "reliability", "about": "MTTR·MTBF", "roles": ["MNT", "MGR"]},
             {"tool": "sensor_trend", "about": "센서 데이터", "roles": ["MNT", "MGR"]}]


@pytest.fixture
def fb(monkeypatch):
    return FakeBackend().install(monkeypatch)


def post(q, role="MNT", user="U07", allowed=ALL, out_of_role=None, context=None):
    return client.post("/chat", headers=H, json={"question": q, "context": context or {}, "allowed_tools": allowed,
                                                 "out_of_role": out_of_role or [], "history": [],
                                                 "user": {"user_id": user, "role_code": role}})


@pytest.mark.parametrize("question,tool,expected", [
    ("재고 부족한 거 알려줘", "inventory", "알루미늄 봉재 6061"),
    ("공구 수명 90% 넘은 거 있어?", "tool_life", "엔드밀 12mm"),
    ("기한 넘긴 예방 정비 있어?", "pm_due", "가이드 레일 윤활"),
    ("VF2-01 작업지시서 보여줘", "work_orders", "WO-2609-0007"),
    ("9월 29일 생산 실적 알려줘", "production", "실적 84개 (목표 90개)"),
    ("VF2-01 지금 상태", "equipment_status", "07:12부터 48분"),
    ("VF2-01 정지 몇 번 했어", "stop_reasons", "손실 정지 3번 90분"),
])
def test_operating_question_is_answered_from_backend_tools(fb, question, tool, expected):
    r = post(question)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "OK" and expected in j["answer"]
    assert set(j) == {"answer", "sources", "related", "status"}
    assert tool in fb.tools_called()
    # 서비스 키와 "누구를 대신해 묻는지"가 매번 실린다
    assert all(c["headers"] == {"X-Service-Key": KEY} and c["on_behalf_of"] == "U07" for c in fb.calls)


def test_alarm_question_adds_related_counts_from_aggregates(fb):
    j = post("2075 알람 뭐야").json()
    assert j["status"] == "OK" and "윤활" in j["answer"]
    assert "최근 7일 5번, 30일 5번" in j["answer"]                      # 두 설비 3 + 2 (집계 times 합)
    assert "반복 알람" not in j["answer"] and "처리 안 된" not in j["answer"]      # 백엔드 도구에 없는 정보는 말하지 않는다


def test_kpi_for_a_role_that_may_see_mttr(fb):
    j = post("VF2-01 OEE 알려줘").json()
    assert "OEE 55.2%" in j["answer"] and "MTTR 50분" in j["answer"] and "MTBF 168시간" in j["answer"]
    assert "reliability" in fb.tools_called()


def test_kpi_for_a_role_that_may_not_see_mttr_shows_no_mttr_at_all(fb):
    j = post("VF2-01 OEE 알려줘", role="OPR", user="U01", allowed=NO_RELIABILITY, out_of_role=MTTR_GATE).json()
    assert j["status"] == "OK" and "OEE 55.2%" in j["answer"]
    assert not re.search(r"MTTR|MTBF", j["answer"])                    # "—"로도 보이지 않는다
    assert "reliability" not in fb.tools_called()


def test_mttr_question_for_a_role_that_may_not_see_it_never_reaches_the_backend(fb):
    j = post("VF2-01 MTTR 알려줘", role="OPR", user="U01", allowed=NO_RELIABILITY, out_of_role=MTTR_GATE).json()
    assert j["status"] == "OUT_OF_ROLE" and not any(ch.isdigit() for ch in j["answer"])
    assert fb.calls == []


def test_tool_not_allowed_for_the_role_is_out_of_role_without_values(fb):
    j = post("재고 부족한 거 알려줘", role="OPR", user="U01", allowed=["alarms"]).json()
    assert j["status"] == "OUT_OF_ROLE" and j["answer"] == CS.DENIED_ANSWER and j["sources"] == []
    assert fb.calls == []                                               # 허용되지 않은 도구는 백엔드를 부르지 않는다


def test_backend_failure_is_503_without_inner_details(fb):
    fb.fail_with = BT.BackendToolError("HTTP 500 http://backend.test/api/assistant/tools/inventory")
    r = post("재고 부족한 거 알려줘")
    assert r.status_code == 503
    assert r.json() == {"code": "ASSISTANT_UNAVAILABLE", "message": CS.UNAVAILABLE_MESSAGE, "detail": {"retryable": True}}
    assert not re.search(r"backend\.test|HTTP 500|tools/inventory", r.text)


def test_document_question_does_not_call_the_backend(fb):
    j = post("쿨런트가 뭐야?", role="OPR", user="U01").json()
    assert j["status"] == "OK" and j["sources"]
    assert fb.calls == []


def test_calls_do_not_leak_between_users(fb):
    post("재고 부족한 거 알려줘", user="U07")
    post("재고 부족한 거 알려줘", user="U01", role="OPR")
    assert [c["on_behalf_of"] for c in fb.calls] == ["U07", "U01"]
    assert BT.current() is None
