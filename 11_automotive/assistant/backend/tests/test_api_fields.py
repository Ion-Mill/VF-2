"""운영 데이터 응답의 가상 표시와 출처 칸 이름 (API명세서_v1 1장 공통 규칙, 2026-10-11 P1).

- T-NFR-DATA-08-1: 운영 데이터 응답마다 `is_synthetic: true`. 비서 답은 가상 운영 데이터(조회·관련 기록)를 쓴 답만 True,
  사내 문서만 쓴 답은 False (사내 문서는 "가상 사내 문서"로 따로 표시).
- T-FR-AST-COM-02-1: 출처 칸에 명세 이름 `doc_no`·`rev`가 있고 옛 칸(`doc_id`·`revision`)과 값이 같다. 원문 출처 칸은 없다 (D-03).
"""
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.demo_state import get_state
from backend.rag.sanitize import FORBIDDEN
from backend.services.answer import answer

client = TestClient(app)


def H(role, user=""):
    return {"X-Role": role, "X-User": user}


@pytest.fixture(autouse=True)
def fresh_state():
    get_state().reset()
    yield
    get_state().reset()


def _cite_ok(e):
    assert e["doc_no"] == e["doc_id"] and e["rev"] == e["revision"], e
    assert e["doc_name"] and e["section"], e
    assert not FORBIDDEN.search(str(e)), e


def test_T_NFR_DATA_08_1_answer_marks_synthetic_only_with_ops_data():
    ops = answer("오늘 공구 수명 90% 넘은 거 있어?", "SUP")
    assert ops["current_data"] and ops["is_synthetic"] is True
    assert all(d["is_synthetic"] is True for d in ops["current_data"])
    doc = answer("쿨런트가 뭐야?", "OPR")
    assert doc["status"] == "답변" and doc["is_synthetic"] is False and not doc["current_data"]
    denied = answer("x", "MON")
    assert denied["is_synthetic"] is False


def test_T_NFR_DATA_08_1_api_responses_have_is_synthetic():
    assert client.get("/api/users").json()["is_synthetic"] is True
    lst = client.get("/api/notifications", headers=H("MGR")).json()
    assert lst["is_synthetic"] is True and lst["notifications"]
    assert all(n["is_synthetic"] is True for n in lst["notifications"])
    alarm = next(a for a in get_state().alarms() if a["severity"] == "STOP")
    # 주소는 2026-10-11 P4에서 명세 이름으로 (옛 /api/guide-cards/…, /api/demo/scenario/S1, /api/demo/reset)
    card = client.get(f"/api/maint/guide-card/{alarm['alarm_event_id']}", headers=H("MNT")).json()
    assert card["is_synthetic"] is True
    assert card["production"] is None or (card["production"]["is_synthetic"] is True and card["production"]["is_estimated"] is True)
    assert client.get("/api/ops/tool_life", headers=H("MGR")).json()["is_synthetic"] is True
    sc = client.post("/api/sim/inject", json={"scenario_code": "S1"}, headers=H("SUP")).json()
    assert sc["is_synthetic"] is True
    assert all(ev["data"]["is_synthetic"] is True for ev in get_state().events)   # SSE 데이터
    assert client.post("/api/sim/reset", headers=H("SUP")).json()["is_synthetic"] is True


def test_T_NFR_DATA_08_1_processed_notification_marks_synthetic():
    n = None
    for role, user in (("OPR", "OPR-01"), ("OPR", "OPR-02"), ("OPR", "OPR-03"), ("MNT", "MNT-01"), ("SUP", "SUP-01")):
        lst = client.get("/api/notifications", headers=H(role, user)).json()
        n = next((x for x in lst["notifications"] if x["can_process"]), None)
        if n:
            break
    assert n, "처리할 수 있는 알림이 없다 — 시험 가정 확인 필요"
    plan = "윤활 라인 누설 점검 (보전 1, 오늘 안)" if n["needs_plan"] else ""
    r = client.post(f"/api/notifications/{n['id']}/resolve", json={"action_plan": plan}, headers=H(role, user))  # 명세 NTF-03
    assert r.status_code == 200 and r.json()["is_synthetic"] is True
    assert get_state().events[-1]["data"]["is_synthetic"] is True


def test_T_FR_AST_COM_02_1_cite_fields_doc_no_rev():
    a = answer("992 뜨면 뭐부터 봐?", "OPR")
    assert a["evidence"]
    for e in a["evidence"]:
        _cite_ok(e)
    alarm = next(a for a in get_state().alarms() if a["severity"] == "STOP")
    card = client.get(f"/api/maint/guide-card/{alarm['alarm_event_id']}", headers=H("MNT")).json()
    for e in card["sources"]:
        _cite_ok(e)
    assert card["safety"]["cite"]["doc_no"] == "DOC-05"
    sec = client.get("/api/internal-docs/DOC-03/sections/2.1", headers=H("MNT")).json()
    assert sec["doc_no"] == "DOC-03" and sec["rev"] == sec["revision"]
    lst = client.get("/api/notifications", headers=H("MGR")).json()
    for n in lst["notifications"]:
        for e in n["evidence"]:
            _cite_ok(e)
