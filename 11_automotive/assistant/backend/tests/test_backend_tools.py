"""backend_tools 시험 — 기존 백엔드 조회 도구 호출 ([11_automotive 이식 2026-10-16]). 네트워크 없음 (가짜 백엔드)."""
import threading

import pytest

from backend.repositories import backend_tools as BT
from backend.tests.fake_backend import KEY, NOW, FakeBackend

pytestmark = pytest.mark.own_backend            # 가짜 백엔드·호출 사용자를 이 파일이 직접 준비한다 (conftest의 기본을 끈다)
ALL = {"alarms", "inventory", "kpi"}


@pytest.fixture
def fb(monkeypatch):
    return FakeBackend().install(monkeypatch)


def test_call_sends_key_user_and_drops_empty_args(fb):
    with BT.acting_as("U07", ALL):
        r = BT.call_tool("inventory", {"item_no": None})
    c = fb.calls[0]
    assert c["url"] == "http://backend.test/api/assistant/tools/inventory"
    assert c["headers"] == {"X-Service-Key": KEY} and c["on_behalf_of"] == "U07"
    assert c["args"] == {}                                   # None 인자는 보내지 않는다 (백엔드는 모르는 입력을 422로 거절)
    assert [x["item_no"] for x in r.rows] == ["RM-001", "FG-001"] and r.now == NOW


def test_tool_not_in_allowed_list_is_denied_before_any_http_call(fb):
    with BT.acting_as("U01", {"inventory"}):
        with pytest.raises(BT.ToolDenied) as e:
            BT.call_tool("reliability", {"equipment_id": "VF2-01"})
    assert e.value.tool == "reliability" and fb.calls == []


def test_no_caller_is_an_error(fb):
    with pytest.raises(BT.BackendToolError):
        BT.call_tool("inventory")
    assert fb.calls == []


def test_missing_settings_is_an_error(fb, monkeypatch):
    monkeypatch.delenv("MOM_BACKEND_URL")
    with BT.acting_as("U07", ALL), pytest.raises(BT.BackendToolError):
        BT.call_tool("inventory")
    monkeypatch.setenv("MOM_BACKEND_URL", "http://backend.test")
    monkeypatch.delenv("MOM_ASSISTANT_KEY")
    with BT.acting_as("U07", ALL), pytest.raises(BT.BackendToolError):
        BT.call_tool("inventory")
    assert fb.calls == []


@pytest.mark.parametrize("payload", [None, [], {"rows": "no"}, {"tool": "inventory"}])
def test_bad_response_shape_is_an_error(fb, monkeypatch, payload):
    monkeypatch.setattr(BT, "_post", lambda *a, **k: payload)
    with BT.acting_as("U07", ALL), pytest.raises(BT.BackendToolError):
        BT.call_tool("inventory")


def test_transport_failure_is_an_error(fb):
    fb.fail_with = BT.BackendToolError("HTTP 403")
    with BT.acting_as("U07", ALL), pytest.raises(BT.BackendToolError):
        BT.call_tool("inventory")


def test_acting_as_is_restored_and_nests(fb):
    assert BT.current() is None
    with BT.acting_as("U01", {"alarms"}):
        with BT.acting_as("U02", {"kpi"}):
            assert BT.current().user_id == "U02" and BT.is_allowed("kpi") and not BT.is_allowed("alarms")
        assert BT.current().user_id == "U01"
    assert BT.current() is None


def test_acting_as_is_restored_after_an_error(fb):
    with pytest.raises(RuntimeError):
        with BT.acting_as("U01", ALL):
            raise RuntimeError("boom")
    assert BT.current() is None


def test_caller_does_not_leak_into_other_threads(fb):
    seen = []
    with BT.acting_as("U01", ALL):
        t = threading.Thread(target=lambda: seen.append(BT.current()))
        t.start()
        t.join()
    assert seen == [None]                                    # 다음 사용자의 요청으로 새지 않는다
