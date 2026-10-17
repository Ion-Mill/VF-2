"""문장 입구(`POST /compose/{kind}`) 시험 — 기본 문장 줄을 외부 Claude로 다듬는다 (2026-10-17, NFR-SEC-08·NFR-AIQ-04·FR-AST-02-14).
진짜 `claude`는 부르지 않는다. 가짜 실행기가 부른 횟수와 받은 글을 기록해서 "스위치를 끄면 외부 연결 0", "사람·계정 글은 안 나감"을 확인한다."""
import json
import subprocess
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend import config as C
from backend.llm import claude_client as CC
from backend.llm import client as LC
from backend.llm import external as EXT
from backend.privacy import outbound_guard as OG

pytestmark = pytest.mark.own_backend
KEY = "test-service-key"
H = {"X-Service-Key": KEY}
SONNET = "claude-sonnet-5-5"
client = TestClient(CS.app)

SHIFT = [{"id": "s1", "text": "실적 87개 / 총 목표 90개 (-3개)."},
         {"id": "s2", "text": "필수 정지 1건, 합계 12분 — 가장 긴 것 VF2-01 윤활 12분 (고장 손실 약 1.7개, 추정)."},
         {"id": "s3", "text": "병목은 기준 병목(OP-30) 그대로."}]


class Runner:
    """가짜 `claude` 실행기: 부른 횟수·받은 글을 기록하고, 정해 둔 답(dict) 또는 예외를 차례로 돌려준다."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"cmd": cmd, "stdin": stdin_text})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        d = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 10, "duration_api_ms": 5, "num_turns": 1,
             "total_cost_usd": 0.001, "structured_output": r,
             "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
             "modelUsage": {SONNET: {"inputTokens": 10}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(d, ensure_ascii=False), stderr="")


def out(*texts, ids=("s1", "s2", "s3")):
    return {"lines": [{"id": i, "text": t} for i, t in zip(ids, texts)]}


GOOD = out("실적은 87개로 총 목표 90개보다 적습니다 (-3개).",
           "필수 정지는 1건, 합계 12분이었고 가장 긴 것은 VF2-01 윤활 12분입니다 (고장 손실 약 1.7개, 추정).",
           "병목은 기준 병목(OP-30) 그대로입니다.")


LOCAL_CALLS: list[str] = []


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    LOCAL_CALLS.clear()

    def local_handler(req):            # 로컬 LLM 서버는 이 프로젝트에서 쓰지 않는다 — 불리면 기록하고 연결 실패로 돌려준다
        LOCAL_CALLS.append(str(req.url))
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


def post(kind="shift_report", lines=SHIFT, **kw):
    return client.post(f"/compose/{kind}", json={"lines": lines}, headers=H, **kw)


def assert_503(r):
    assert r.status_code == 503 and r.json()["code"] == "ASSISTANT_UNAVAILABLE" and r.json()["detail"] == {"retryable": True}
    assert "sonnet" not in r.text.lower() and "claude" not in r.text.lower()       # 안쪽 사정은 응답에 없다


# ------------------------------------------------------------------ 열쇠·입력 모양
def test_service_key_is_required():
    r = use()
    assert client.post("/compose/shift_report", json={"lines": SHIFT}).status_code == 401
    assert client.post("/compose/shift_report", json={"lines": SHIFT}, headers={"X-Service-Key": "nope"}).status_code == 401
    assert r.calls == []


@pytest.mark.parametrize("bad", [
    {"lines": SHIFT, "user_id": "U07"},                                   # 정해진 칸 밖은 받지 않는다
    {"lines": [{"id": "s1", "text": "x", "by": "U07"}]},
    {"lines": []},
    {"lines": [{"id": "한글 id", "text": "x"}]},
    {"lines": [{"id": "s1", "text": ""}]},
    {},
])
def test_bad_request_shapes_are_422_and_nothing_is_sent(bad):
    r = use()
    assert client.post("/compose/shift_report", json=bad, headers=H).status_code == 422
    assert r.calls == []


def test_unknown_kind_is_422():
    assert client.post("/compose/chat", json={"lines": SHIFT}, headers=H).status_code == 422


# ------------------------------------------------------------------ 다듬기 성공
def test_polishes_each_line_and_keeps_ids_order_and_numbers():
    r = use(GOOD)
    res = post()
    assert res.status_code == 200
    j = res.json()
    assert j["kind"] == "shift_report" and j["tries"] == 1
    assert [l["id"] for l in j["lines"]] == ["s1", "s2", "s3"]
    assert "87개" in j["lines"][0]["text"] and "(고장 손실 약 1.7개, 추정)" in j["lines"][1]["text"]
    assert len(r.calls) == 1
    assert "s1: 실적 87개 / 총 목표 90개 (-3개)." in r.calls[0]["stdin"]
    assert EXT.override() is None                                         # 요청이 끝나면 외부 상태가 새지 않는다


# ------------------------------------------------------------------ 외부로 한 글자도 안 나가는 경우 (T-NFR-SEC-08-2)
def test_server_switch_off_sends_nothing_and_is_503(monkeypatch):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    r = use(GOOD)
    assert_503(post())
    assert r.calls == [] and LOCAL_CALLS == []         # 외부 연결 0, 로컬 LLM 서버로도 새지 않는다


def test_provider_not_claude_sends_nothing_and_is_503(monkeypatch):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "local")
    r = use(GOOD)
    assert_503(post())
    assert r.calls == [] and LOCAL_CALLS == []         # 외부 연결 0, 로컬 LLM 서버로도 새지 않는다


def test_llm_disabled_sends_nothing_and_is_503(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "0")
    r = use(GOOD)
    assert_503(post())
    assert r.calls == [] and LOCAL_CALLS == []         # 외부 연결 0, 로컬 LLM 서버로도 새지 않는다


# ------------------------------------------------------------------ 사람·계정 글은 나가지 않는다 (T-NFR-SEC-08-1)
@pytest.mark.parametrize("leak", ["담당 U07 점검", "보전 담당 1 점검", "사번: E12345 점검", "비밀번호: hunter22 점검", "Bearer abcdef1234567890 점검"])
def test_material_with_people_or_account_info_is_not_sent(leak):
    r = use(GOOD)
    assert_503(post(lines=[{"id": "s1", "text": f"실적 87개. {leak}."}]))
    assert r.calls == []


# ------------------------------------------------------------------ 검사에 걸리면 거부하고 한 번 다시 요청한다
def test_changed_number_is_rejected_then_retry_with_reason_succeeds():
    bad = out("실적은 88개, 총 목표 90개라서 2개 모자랍니다.", GOOD["lines"][1]["text"], GOOD["lines"][2]["text"])
    r = use(bad, GOOD)
    res = post()
    assert res.status_code == 200 and res.json()["tries"] == 2
    assert "거부" in r.calls[1]["stdin"] and "s1" in r.calls[1]["stdin"]       # 다시 요청에 사유가 붙는다


def test_two_rejections_end_in_503_and_never_loop_further():
    bad = out("실적은 88개, 총 목표 90개입니다.", GOOD["lines"][1]["text"], GOOD["lines"][2]["text"])
    r = use(bad, bad)
    assert_503(post())
    assert len(r.calls) == 2


@pytest.mark.parametrize("name,mutate", [
    ("꼬리표 '추정' 삭제", lambda g: out(g["lines"][0]["text"], "필수 정지는 1건, 합계 12분이었고 가장 긴 것은 VF2-01 윤활 12분입니다 (고장 손실 약 1.7개).", g["lines"][2]["text"])),
    ("설비 번호 바꿈", lambda g: out(g["lines"][0]["text"], g["lines"][1]["text"].replace("VF2-01", "VF2-02"), g["lines"][2]["text"])),
    ("줄 순서 바꿈", lambda g: {"lines": [g["lines"][1], g["lines"][0], g["lines"][2]]}),
    ("줄 빠짐", lambda g: {"lines": g["lines"][:2]}),
    ("문장 수 늘림", lambda g: out("실적은 87개입니다. 총 목표는 90개입니다.", g["lines"][1]["text"], g["lines"][2]["text"])),
    ("줄바꿈", lambda g: out("실적은 87개로\n총 목표 90개보다 적습니다 (-3개).", g["lines"][1]["text"], g["lines"][2]["text"])),
    ("마크다운", lambda g: out("**" + g["lines"][0]["text"] + "**", g["lines"][1]["text"], g["lines"][2]["text"])),
    ("허락 문구", lambda g: out(g["lines"][0]["text"], g["lines"][1]["text"], "병목은 기준 병목(OP-30) 그대로라 문제 없습니다.")),
])
def test_unsafe_rewrites_are_rejected(name, mutate):
    r = use(mutate(GOOD), mutate(GOOD))
    assert_503(post())
    assert len(r.calls) == 2, name


def test_daily_report_items_must_not_contain_the_separators_the_screen_splits_on():
    items = [{"id": "i1", "text": "VF2-01 윤활 정지 12분"}, {"id": "i2", "text": "병목 OP-30 유지"}]
    ok = {"lines": [{"id": "i1", "text": "VF2-01은 윤활 때문에 12분 멈췄습니다"}, {"id": "i2", "text": "병목은 OP-30 그대로입니다"}]}
    bad = {"lines": [{"id": "i1", "text": "정지: VF2-01 윤활 12분"}, {"id": "i2", "text": "병목 OP-30 유지"}]}
    r = use(bad, ok)
    res = post("daily_report", items)
    assert res.status_code == 200 and res.json()["tries"] == 2
    assert all(":" not in l["text"] and " / " not in l["text"] for l in res.json()["lines"])
    assert "금지 글자" in r.calls[1]["stdin"]


# ------------------------------------------------------------------ 외부 실패는 몰래 다른 길로 가지 않는다
def test_claude_process_timeout_is_503():
    r = use(subprocess.TimeoutExpired(["claude"], 60))
    assert_503(post())
    assert len(r.calls) == 1


def test_unreadable_claude_output_is_503():
    r = use({"unexpected": "shape"}, {"unexpected": "shape"})
    assert_503(post())
