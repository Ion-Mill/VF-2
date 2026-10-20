"""chat_service 시험 — 기존 백엔드가 부르는 POST /chat ([11_automotive 이식 2026-10-16]). 실제 LLM·네트워크·DB를 부르지 않는다."""
import re

import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend import config as C
from backend.llm import external as EXT

pytestmark = pytest.mark.own_backend            # 서비스 키·설정을 이 파일이 직접 준비한다 (conftest의 기본을 끈다)
KEY = "test-service-key"
H = {"X-Service-Key": KEY}
client = TestClient(CS.app)


@pytest.fixture(autouse=True)
def _service_env(monkeypatch):
    monkeypatch.setattr(C, "_dotenv", lambda: {})          # 개발 PC의 .env가 시험을 바꾸지 않게
    monkeypatch.setenv("MOM_ASSISTANT_KEY", KEY)
    monkeypatch.delenv("ASSISTANT_PROVIDER", raising=False)


def body(q, role="OPR", **kw):
    return {"question": q, "context": {}, "allowed_tools": [], "out_of_role": [], "history": [],
            "user": {"user_id": "U01", "role_code": role}, **kw}


def ok_answer(**kw):
    return {"status": "답변", "conclusion": "답입니다.", "steps": [], "evidence": [], "related": None, "caution": None, **kw}


# ---------------------------------------------------------------- 서비스 키
def test_missing_or_wrong_key_is_401():
    assert client.post("/chat", json=body("쿨런트가 뭐야?")).status_code == 401
    assert client.post("/chat", json=body("쿨런트가 뭐야?"), headers={"X-Service-Key": "nope"}).status_code == 401


def test_key_not_configured_rejects_everything(monkeypatch):
    monkeypatch.delenv("MOM_ASSISTANT_KEY")
    assert client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H).status_code == 401
    assert client.post("/chat", json=body("쿨런트가 뭐야?"), headers={"X-Service-Key": ""}).status_code == 401


def test_no_automatic_docs_pages():
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404


def test_health_needs_the_key_and_shows_no_model_names():
    assert client.get("/health").status_code == 401
    r = client.get("/health", headers=H)
    assert r.status_code == 200 and r.json()["corpus"]["status"] == "ok"
    assert not re.search(r"sonnet|opus|claude-|qwen", r.text, re.I)


# ---------------------------------------------------------------- 실제 답 (규칙 + 사내 문서, LLM 꺼짐)
def test_document_question_returns_the_contract_fields():
    r = client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H)
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"answer", "sources", "related", "status"}
    assert j["status"] == "OK" and isinstance(j["answer"], str) and "절삭유" in j["answer"]
    assert j["sources"] and all(set(s) == {"doc_name", "doc_no", "rev", "section"} for s in j["sources"])
    assert j["related"] == []


def test_machine_control_request_is_refused():
    j = client.post("/chat", json=body("설비 전원 꺼 줘"), headers=H).json()
    assert j["status"] == "REFUSED" and j["sources"] == []


def test_question_outside_the_documents_is_not_in_docs():
    j = client.post("/chat", json=body("오늘 점심 뭐 먹지"), headers=H).json()
    assert j["status"] == "NOT_IN_DOCS"


# ---------------------------------------------------------------- 채팅 권한 (MTTR·센서 = MNT·MGR)
def test_out_of_role_question_never_reaches_answer(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("권한 밖 질문이 answer()까지 갔다")
    monkeypatch.setattr(CS, "answer", boom)
    gate = [{"tool": "reliability", "about": "MTTR·MTBF", "roles": ["MNT", "MGR"]}]
    j = client.post("/chat", json=body("VF2-01 MTTR 알려줘", out_of_role=gate), headers=H).json()
    assert j["status"] == "OUT_OF_ROLE" and not any(ch.isdigit() for ch in j["answer"])


SENSOR_GATE = {"tool": "sensor_trend", "about": "센서 데이터", "roles": ["MNT", "MGR"]}
MTTR_GATE = {"tool": "reliability", "about": "MTTR·MTBF", "roles": ["MNT", "MGR"]}


@pytest.mark.parametrize("q", [
    "고전압 대기는 몇 분 기다려야 해?", "고전압 대기 시간 알려줘", "전원 끈 뒤에 전압이 빠질 때까지 얼마나 기다려?"])
def test_safety_question_is_not_stopped_by_the_sensor_gate(monkeypatch, q):
    """2026-10-21 시연: `고전압`의 `전압`과 `몇 분`의 `몇`이 센서 값 질문으로 읽혀 반장·작업자의 안전 질문이 막혔다."""
    seen = {}

    def fake_answer(question, role, ctx, **k):
        seen["q"] = question
        return ok_answer()
    monkeypatch.setattr(CS, "answer", fake_answer)
    j = client.post("/chat", json=body(q, out_of_role=[MTTR_GATE, SENSOR_GATE]), headers=H).json()
    assert j["status"] != "OUT_OF_ROLE" and seen["q"] == q          # 권한 문을 지나 answer()까지 갔다


@pytest.mark.parametrize("q", [
    "잠금 순서랑 VF2-01 센서 추세 보여줘", "고전압 대기랑 VF2-01 센서 값 알려줘", "VF2-01 센서 추세 보여줘", "VF2-01 모터 온도 지금 몇 도야?"])
def test_a_sensor_value_request_is_still_stopped_even_with_a_safety_word(monkeypatch, q):
    def boom(*a, **k):
        raise AssertionError("센서 값 요청이 권한 문을 지나 answer()까지 갔다")
    monkeypatch.setattr(CS, "answer", boom)
    j = client.post("/chat", json=body(q, out_of_role=[MTTR_GATE, SENSOR_GATE]), headers=H).json()
    assert j["status"] == "OUT_OF_ROLE" and not any(ch.isdigit() for ch in j["answer"])


def test_the_mttr_gate_is_kept_for_a_safety_question_too(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("MTTR 값 요청이 권한 문을 지났다")
    monkeypatch.setattr(CS, "answer", boom)
    j = client.post("/chat", json=body("고전압 대기 알려주고 VF2-01 MTTR 얼마야?", out_of_role=[MTTR_GATE, SENSOR_GATE]), headers=H).json()
    assert j["status"] == "OUT_OF_ROLE"


# ---------------------------------------------------------------- 실패는 모두 503, 안쪽 사정은 안 나간다
def _assert_unavailable(r):
    assert r.status_code == 503
    assert r.json() == {"code": "ASSISTANT_UNAVAILABLE", "message": CS.UNAVAILABLE_MESSAGE, "detail": {"retryable": True}}
    assert not re.search(r"claude|sonnet|opus|EXTERNAL|/opt|Traceback", r.text, re.I)


def test_any_failure_is_503_without_inner_details(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("claude-sonnet-5-5 at /opt/claude/bin EXTERNAL_LLM_UNAVAILABLE")
    monkeypatch.setattr(CS, "answer", boom)
    _assert_unavailable(client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H))


def test_unknown_bundle_status_is_503_not_ok(monkeypatch):
    monkeypatch.setattr(CS, "answer", lambda *a, **k: ok_answer(status="처음 보는 상태"))
    _assert_unavailable(client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H))


def test_invalid_role_is_rejected():
    assert client.post("/chat", json=body("쿨런트가 뭐야?", role="MON"), headers=H).status_code == 422
    assert client.post("/chat", json={"question": "x", "user": {"user_id": "U01"}}, headers=H).status_code == 422


# ---------------------------------------------------------------- 문맥 거르기
def test_context_keeps_only_known_fields_as_strings(monkeypatch):
    seen = {}

    def fake(question, role, ctx, *a, **k):
        seen.update(question=question, role=role, ctx=ctx)
        return ok_answer()
    monkeypatch.setattr(CS, "answer", fake)
    client.post("/chat", json=body("이 알람 뭐야", role="MNT", context={"screen": "SCR-09", "alarm_event_id": 3, "evil": "x", "equipment_id": ""}), headers=H)
    assert seen == {"question": "이 알람 뭐야", "role": "MNT", "ctx": {"screen": "SCR-09", "alarm_event_id": "3"}}


# ---------------------------------------------------------------- 외부 Claude (서버 설정으로만 고정)
def test_claude_provider_with_server_switch_off_is_503_and_answer_not_called(monkeypatch):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    monkeypatch.setattr(CS, "answer", lambda *a, **k: (_ for _ in ()).throw(AssertionError("외부 스위치가 꺼졌는데 answer()가 불렸다")))
    _assert_unavailable(client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H))


def test_claude_state_is_per_request_and_restored(monkeypatch):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")
    inside = []
    monkeypatch.setattr(CS, "answer", lambda *a, **k: (inside.append(EXT.override()), ok_answer())[1])
    assert client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H).status_code == 200
    assert inside == ["claude"] and EXT.override() is None             # 요청이 끝나면 다음 요청에 새지 않는다


def test_local_provider_does_not_touch_external_state(monkeypatch):
    inside = []
    monkeypatch.setattr(CS, "answer", lambda *a, **k: (inside.append(EXT.override()), ok_answer())[1])
    assert client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H).status_code == 200
    assert inside == [None]


def test_claude_material_step_failure_is_503_not_a_silent_fallback(monkeypatch):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")

    def fake(*a, **k):
        EXT.note_failure("route", "timeout")          # 재료를 정하는 단계의 외부 호출 실패
        return ok_answer()
    monkeypatch.setattr(CS, "answer", fake)
    _assert_unavailable(client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H))


def test_claude_polish_step_failure_still_answers(monkeypatch):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")

    def fake(*a, **k):
        EXT.note_failure("write", "timeout")          # 다듬는 단계 실패 — 정해진 재료(기본 문장)로 답한 것
        return ok_answer()
    monkeypatch.setattr(CS, "answer", fake)
    r = client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H)
    assert r.status_code == 200 and r.json()["status"] == "OK"
