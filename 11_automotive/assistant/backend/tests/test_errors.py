"""API 오류 형식 {code, message, detail} — 코드 7개 (API명세서_v1 1장 "오류 형식", 2026-10-11 멈춤 ③ P4).

HTTP 상태 번호는 명세에 없어 [제안]으로 정했다 (backend/errors.py 표). detail은 늘 객체다.
"""
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.demo_state import get_state
from backend.services import shift_reports as SR

client = TestClient(app_module.app)


def H(role="", user=""):
    return {"X-Role": role, "X-User": user}


@pytest.fixture(autouse=True)
def fresh_state():
    get_state().reset()
    yield
    get_state().reset()


def _err(r, status, code):
    assert r.status_code == status, (r.status_code, r.text)
    j = r.json()
    assert set(j) == {"code", "message", "detail"} and j["code"] == code, j
    assert isinstance(j["message"], str) and j["message"] and isinstance(j["detail"], dict), j
    return j


def test_unauthorized_without_role_or_with_wrong_user():
    _err(client.post("/api/assistant/chat", json={"question": "쿨런트가 뭐야?"}), 401, "UNAUTHORIZED")
    _err(client.get("/api/notifications", headers=H("ZZZ")), 401, "UNAUTHORIZED")              # 모르는 역할
    _err(client.get("/api/notifications", headers=H("SUP", "OPR-02")), 401, "UNAUTHORIZED")     # 사용자와 역할이 다름
    _err(client.get("/api/stream/events", params={"role": "", "user": ""}), 401, "UNAUTHORIZED")


def test_forbidden_for_role_without_permission():
    _err(client.post("/api/assistant/chat", json={"question": "x"}, headers=H("MON")), 403, "FORBIDDEN")
    _err(client.get("/api/internal-docs", headers=H("MON")), 403, "FORBIDDEN")


def test_not_found_record_and_route():
    _err(client.get("/api/maint/guide-card/ALM-XXXX", headers=H("OPR")), 404, "NOT_FOUND")
    _err(client.get("/api/internal-docs/DOC-99", headers=H("OPR")), 404, "NOT_FOUND")
    _err(client.post("/api/notifications/N-XXXX/resolve", json={}, headers=H("SUP", "SUP-01")), 404, "NOT_FOUND")
    _err(client.post("/api/sim/inject", json={"scenario_code": "S9"}, headers=H("SUP")), 404, "NOT_FOUND")
    _err(client.get("/api/no-such-route", headers=H("OPR")), 404, "NOT_FOUND")
    # 옛 주소는 남기지 않았다 (2026-10-11 P4)
    for old in ("/api/guide-cards/ALM-00279", "/api/docs", "/api/events"):
        assert client.get(old, headers=H("OPR")).status_code == 404, old


def test_validation_wrong_or_missing_values():
    j = _err(client.post("/api/assistant/chat", json={"question": ""}, headers=H("OPR")), 422, "VALIDATION")
    assert j["detail"]["errors"]                                                                  # 어느 칸이 틀렸는지
    _err(client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": ""}, headers=H("SUP", "SUP-01")),
         422, "VALIDATION")                                                                       # 반복 알람은 조치 계획 필수
    _err(client.get("/api/ops/stops", params={"equipment_id": "XX-99"}, headers=H("MGR")), 422, "VALIDATION")
    _err(client.post("/api/reports/shift/2026-9-30/confirm", json={"version": 0}, headers=H("SUP", "SUP-01")), 422, "VALIDATION")


def test_invalid_state():
    ok = client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": "체크밸브 점검"}, headers=H("SUP", "SUP-01"))
    assert ok.status_code == 200
    _err(client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": "y"}, headers=H("MNT", "MNT-01")),
         409, "INVALID_STATE")                                                                    # 이미 처리
    assert client.post("/api/sim/inject", json={"scenario_code": "S1"}, headers=H("SUP")).status_code == 200
    _err(client.post("/api/sim/inject", json={"scenario_code": "S1"}, headers=H("SUP")), 409, "INVALID_STATE")   # 이미 넣음
    _err(client.post("/api/reports/shift/2026-09-30-D/confirm", json={"version": 0}, headers=H("SUP", "SUP-01")),
         409, "INVALID_STATE")                                                                    # 이미 확정


def test_invalid_state_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    _err(client.post("/api/sim/reset", headers=H("SUP")), 409, "INVALID_STATE")


def test_conflict_version():
    SR.draft(get_state(), "2026-09-30-D")
    j = _err(client.post("/api/reports/shift/2026-09-30-D/confirm", json={"version": 2}, headers=H("SUP", "SUP-01")),
             409, "CONFLICT_VERSION")
    assert j["detail"]["current_version"] == 0 and j["detail"]["sent_version"] == 2


def test_assistant_unavailable_when_answer_crashes(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("시험용 고장")
    monkeypatch.setattr(app_module, "answer", boom)
    j = _err(client.post("/api/assistant/chat", json={"question": "쿨런트가 뭐야?"}, headers=H("OPR")), 503, "ASSISTANT_UNAVAILABLE")
    assert j["detail"]["reason"] == "RuntimeError"
