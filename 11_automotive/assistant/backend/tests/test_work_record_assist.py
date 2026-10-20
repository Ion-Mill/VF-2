"""작업기록서 메모 정리 입구(`POST /work-record-assist`) 시험 (2026-10-20, API-MNT-10·FR-MNT-05-02·NFR-SEC-08).
진짜 `claude`는 부르지 않는다. 가짜 실행기가 받은 글을 기록해서 "스위치를 끄면 외부 연결 0", "user_id·이름은 안 나감"을 확인한다."""
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend import config as C
from backend import work_record_service as WRS
from backend.llm import claude_client as CC
from backend.llm import client as LC
from backend.privacy import outbound_guard as OG

pytestmark = pytest.mark.own_backend
KEY = "test-service-key"
H = {"X-Service-Key": KEY}
client = TestClient(CS.app)
MEMO = "알람 992 뒤 Y축 서보 케이블 커넥터에 절삭유 오염. 커넥터 청소하고 건조 30분, 축 윤활유 0.5L 보충 후 MDI 시험 정상"
ITEMS = [{"item_no": "CS-SLUB", "item_name": "축 윤활유"}, {"item_no": "TL-T05", "item_name": "엔드밀"}]
BODY = {"record_no": "MR-0901", "equipment_id": "VF2-01", "memo": MEMO, "user_id": "U07", "alarm_code": "992", "items": ITEMS}
GOOD = {"cause": "알람 992 뒤 Y축 서보 케이블 커넥터에 절삭유 오염이 있었습니다.",
        "action": "커넥터를 청소하고 30분 건조했으며 축 윤활유 0.5L를 보충한 뒤 MDI 시험이 정상이었습니다."}


class Runner:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"cmd": cmd, "stdin": stdin_text})
        r = self.replies.pop(0)
        d = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 10, "duration_api_ms": 5, "num_turns": 1,
             "total_cost_usd": 0.001, "structured_output": r,
             "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
             "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 10}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(d, ensure_ascii=False), stderr="")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    def local_handler(req):
        raise httpx.ConnectError("시험: 로컬 서버 없음")
    LC.use_transport(httpx.MockTransport(local_handler))
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    monkeypatch.setenv("MOM_ASSISTANT_KEY", KEY)
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")
    monkeypatch.setenv("LLM_ENABLED", "1")
    OG.reset_cache()
    yield
    CC.use_runner(None)
    LC.use_transport(None)


def use(*replies) -> Runner:
    r = Runner(*replies)
    CC.use_runner(r)
    return r


def post(body=None, **kw):
    return client.post("/work-record-assist", json=BODY if body is None else body, headers=H, **kw)


def test_service_key_is_required():
    r = use()
    assert client.post("/work-record-assist", json=BODY).status_code == 401
    assert r.calls == []


@pytest.mark.parametrize("bad", [{**BODY, "memo": ""}, {**BODY, "user_name": "홍길동"}, {k: v for k, v in BODY.items() if k != "memo"}])
def test_bad_shapes_are_422_and_nothing_is_sent(bad):
    r = use()
    assert post(bad).status_code == 422
    assert r.calls == []


def test_ok_shape_sources_and_parts():
    r = use(GOOD)
    res = post()
    assert res.status_code == 200, res.text
    j = res.json()
    assert (j["record_no"], j["cause"], j["action"]) == ("MR-0901", GOOD["cause"], GOOD["action"])
    assert j["parts"] == [{"item_no": "CS-SLUB", "qty": 0.5}]                 # 메모에 나온 품목만, 바로 뒤 숫자 = 수량
    assert j["sources"] and all(set(s) == {"doc_name", "doc_no", "rev", "section"} for s in j["sources"])
    assert all(s["doc_no"].startswith("DOC-") for s in j["sources"])
    assert len(r.calls) == 1


def test_user_id_and_names_are_not_sent_out():
    r = use(GOOD)
    post({**BODY, "memo": MEMO + " (U07 확인)"})
    sent = r.calls[0]["stdin"]
    assert "U07" not in sent


def test_new_number_is_rejected_then_retried():
    bad = {**GOOD, "action": GOOD["action"] + " 다음 점검은 7일 뒤입니다."}
    r = use(bad, GOOD)
    res = post()
    assert res.status_code == 200 and len(r.calls) == 2
    assert "새 숫자" in r.calls[1]["stdin"] or "거부" in r.calls[1]["stdin"]


def test_twice_rejected_is_503():
    bad = {**GOOD, "action": "조치 완료 99개."}
    use(bad, bad)
    res = post()
    assert res.status_code == 503 and res.json()["code"] == "ASSISTANT_UNAVAILABLE"


def test_switch_off_sends_nothing(monkeypatch):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    r = use(GOOD)
    assert post().status_code == 503
    assert r.calls == []


def test_parts_without_quantity_are_null():
    assert WRS.parts_from_memo("엔드밀 교체함", [WRS.ItemIn(**i) for i in ITEMS]) == [{"item_no": "TL-T05", "qty": None}]
