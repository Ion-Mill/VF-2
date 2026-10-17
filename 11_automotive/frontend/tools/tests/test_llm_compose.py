"""시연 서버의 문장 다듬기 도우미(llm_compose.py) 시험 — 실제 비서·Claude를 부르지 않는다 (가짜 post와 가짜 HTTP 서버).

실행 (frontend/ 폴더에서):  ..\\생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
지키는 것: ① 기다리지 않는다(요청 스레드가 막히지 않는다) ② 꺼짐이면 아무것도 안 보낸다 ③ 같은 입력은 한 번만 보낸다 ④ 입력이 바뀌면 옛 문장을 안 쓴다
⑤ 실패는 기본 문장 그대로(None)이고 쉬었다 다시 한다 ⑥ 처음으로(run_id 변경)에 늦게 온 결과는 버린다 ⑦ 이 PC가 아닌 주소·키 없음은 보내지 않는다.
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import llm_compose as LC  # noqa: E402
from llm_compose import ComposeHttpError, Composer, sentences  # noqa: E402

DRAFT = ["실적 87개 / 총 목표 90개 (-3개).", "병목은 기준 병목(OP-30) 그대로."]


class Fake:
    """비서 post 가짜: 호출을 기록하고, 정해 둔 동작(성공 / 예외 / 막기)을 한다."""

    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, []
        self.gate = threading.Event()

    def __call__(self, kind, lines):
        self.calls.append((kind, [dict(l) for l in lines]))
        if self.mode == "block":
            self.gate.wait(5)
        if isinstance(self.mode, Exception):
            raise self.mode
        if self.mode == "short":
            return {"lines": lines[:1]}
        return {"lines": [{"id": l["id"], "text": "다듬음: " + l["text"]} for l in lines]}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(fake, run=lambda: 1, clock=None):
    return Composer(run_id=run, post=fake, enabled=True, now=clock or Clock())


# ------------------------------------------------------------------ 기본 동작
def test_disabled_sends_nothing():
    fake = Fake()
    c = Composer(run_id=lambda: 1, post=fake, enabled=False)
    assert c.polished("shift_report", "S1", DRAFT) is None
    c.wait_idle()
    assert fake.calls == [] and c.stats()["enabled"] is False


def test_enabled_comes_from_the_env_switch(monkeypatch):
    monkeypatch.delenv("MOM_LLM_COMPOSE", raising=False)
    assert Composer().enabled is False
    monkeypatch.setenv("MOM_LLM_COMPOSE", "1")
    assert Composer().enabled is True
    monkeypatch.setenv("MOM_LLM_COMPOSE", "true")           # 정확히 "1"만 켠다
    assert Composer().enabled is False


def test_first_call_returns_none_immediately_then_ready_later():
    fake = Fake()
    c = make(fake)
    assert c.polished("shift_report", "S1", DRAFT) is None          # 기다리지 않는다
    c.wait_idle()
    got = c.polished("shift_report", "S1", DRAFT)
    assert got == ["다듬음: " + t for t in DRAFT]
    assert len(fake.calls) == 1 and fake.calls[0][0] == "shift_report"
    assert [l["id"] for l in fake.calls[0][1]] == ["L1", "L2"]       # 기본 ID는 L1, L2 …


def test_custom_ids_are_sent_as_given():
    fake = Fake()
    c = make(fake)
    c.polished("work_order", "MW-950", ["제목", "증상"], ids=["title", "symptom"])
    c.wait_idle()
    assert [l["id"] for l in fake.calls[0][1]] == ["title", "symptom"]


def test_polished_does_not_block_while_the_assistant_is_slow():
    fake = Fake("block")
    c = make(fake)
    t0 = time.monotonic()
    assert c.polished("shift_report", "S1", DRAFT) is None
    assert c.polished("shift_report", "S1", DRAFT) is None
    assert time.monotonic() - t0 < 0.5                               # 비서가 막혀 있어도 요청 스레드는 바로 돌아온다
    fake.gate.set()
    c.wait_idle()
    assert c.polished("shift_report", "S1", DRAFT) is not None


def test_same_input_is_sent_only_once_even_while_pending():
    fake = Fake("block")
    c = make(fake)
    for _ in range(5):
        c.polished("shift_report", "S1", DRAFT)
    fake.gate.set()
    c.wait_idle()
    for _ in range(5):
        c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert len(fake.calls) == 1


def test_changed_input_never_serves_the_old_polished_text():
    fake = Fake()
    c = make(fake)
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    newer = DRAFT + ["주의 알람 1건 (2075)."]
    assert c.polished("shift_report", "S1", newer) is None           # 입력이 바뀌었으니 옛 문장은 안 나간다
    c.wait_idle()
    assert c.polished("shift_report", "S1", newer) == ["다듬음: " + t for t in newer]
    assert len(fake.calls) == 2


# ------------------------------------------------------------------ 실패는 기본 문장 그대로, 쉬었다 다시
def test_failure_returns_none_and_retries_only_after_the_backoff():
    clock = Clock()
    fake = Fake(ComposeHttpError(503, "HTTP 503"))
    c = make(fake, clock=clock)
    assert c.polished("shift_report", "S1", DRAFT) is None
    c.wait_idle()
    assert c.stats()["failed"] == 1
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert len(fake.calls) == 1                                       # 쉬는 중에는 다시 안 부른다
    clock.t += 31
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert len(fake.calls) == 2                                       # 30초 뒤 다시
    clock.t += 31
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert len(fake.calls) == 2                                       # 두 번째 실패 뒤엔 60초 쉰다 (30 → 60 → …)


def test_config_style_errors_rest_much_longer():
    clock = Clock()
    fake = Fake(ComposeHttpError(401, "HTTP 401"))
    c = make(fake, clock=clock)
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    clock.t += 300
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert len(fake.calls) == 1
    clock.t += 700
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert len(fake.calls) == 2


def test_wrong_line_count_is_a_failure_not_a_partial_serve():
    c = make(Fake("short"))
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert c.polished("shift_report", "S1", DRAFT) is None and c.stats()["failed"] == 1


def test_unexpected_exception_is_contained():
    c = make(Fake(RuntimeError("boom")))
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    assert c.polished("shift_report", "S1", DRAFT) is None and c.stats()["failed"] == 1


# ------------------------------------------------------------------ 처음으로(run_id 변경)
def test_result_arriving_after_a_reset_is_discarded():
    fake = Fake("block")
    run = {"id": 1}
    c = make(fake, run=lambda: run["id"])
    c.polished("shift_report", "S1", DRAFT)
    run["id"] = 2                                                     # 시뮬레이터 '처음으로'
    fake.gate.set()
    c.wait_idle()
    assert c.polished("shift_report", "S1", DRAFT) is None            # 옛 회차의 결과는 새 회차에 안 쓰인다
    assert c.stats()["ready"] == 0


def test_clear_drops_everything():
    fake = Fake()
    c = make(fake)
    c.polished("shift_report", "S1", DRAFT)
    c.wait_idle()
    c.clear()
    assert c.stats() == {"enabled": True, "ready": 0, "pending": 0, "failed": 0}


# ------------------------------------------------------------------ 문장 쪼개기 (화면 Briefing.tsx와 같은 기준)
def test_sentences_split_after_period_and_space_only():
    assert sentences("실적 87개 / 총 목표 90개 (-3개). 필수 정지 1건 (고장 손실 약 1.7개, 추정). 병목은 그대로.") == \
        ["실적 87개 / 총 목표 90개 (-3개).", "필수 정지 1건 (고장 손실 약 1.7개, 추정).", "병목은 그대로."]
    assert sentences("") == [] and sentences("  ") == []


# ------------------------------------------------------------------ 실제 HTTP: 가짜 비서 서버
class Stub:
    def __init__(self):
        self.seen, self.status, self.reply = [], 200, None
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                outer.seen.append({"path": self.path, "key": self.headers.get("X-Service-Key"), "body": body})
                out = outer.reply or {"kind": "x", "lines": [{"id": l["id"], "text": "다듬음: " + l["text"]} for l in body["lines"]], "tries": 1}
                data = json.dumps(out, ensure_ascii=False).encode("utf-8")
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


@pytest.fixture
def stub(monkeypatch):
    s = Stub()
    monkeypatch.setenv("MOM_ASSISTANT_URL", s.url)
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "unit-test-key-123")
    yield s
    s.close()


def test_http_post_sends_the_key_header_and_only_the_lines(stub):
    res = LC.http_post("shift_report", [{"id": "L1", "text": "실적 87개."}])
    assert res["lines"][0]["text"] == "다듬음: 실적 87개."
    seen = stub.seen[0]
    assert seen["path"] == "/compose/shift_report" and seen["key"] == "unit-test-key-123"
    assert seen["body"] == {"lines": [{"id": "L1", "text": "실적 87개."}]}                 # 줄 말고는 아무것도 안 보낸다


def test_http_503_becomes_a_compose_error_without_leaking_anything(stub):
    stub.status, stub.reply = 503, {"code": "ASSISTANT_UNAVAILABLE"}
    with pytest.raises(ComposeHttpError) as e:
        LC.http_post("shift_report", [{"id": "L1", "text": "x"}])
    assert e.value.status == 503 and "unit-test-key-123" not in str(e.value)


def test_non_local_assistant_url_is_refused_before_any_network(monkeypatch):
    monkeypatch.setenv("MOM_ASSISTANT_URL", "http://example.com:8100")
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "unit-test-key-123")
    with pytest.raises(ComposeHttpError) as e:
        LC.http_post("shift_report", [{"id": "L1", "text": "x"}])
    assert e.value.status is None and "이 PC" in e.value.why


def test_missing_key_is_refused(monkeypatch, tmp_path):
    monkeypatch.delenv("MOM_ASSISTANT_KEY", raising=False)
    monkeypatch.setattr(LC, "ROOT", tmp_path)                          # assistant/.env가 없는 곳
    with pytest.raises(ComposeHttpError) as e:
        LC.http_post("shift_report", [{"id": "L1", "text": "x"}])
    assert "서비스 키 없음" in e.value.why


def test_key_falls_back_to_the_assistant_env_file_without_exposing_other_lines(monkeypatch, tmp_path):
    (tmp_path / "assistant").mkdir()
    (tmp_path / "assistant" / ".env").write_text("OTHER=1\nMOM_ASSISTANT_KEY='file-key-9'\nMORE=2\n", encoding="utf-8")
    monkeypatch.delenv("MOM_ASSISTANT_KEY", raising=False)
    monkeypatch.setattr(LC, "ROOT", tmp_path)
    assert LC._read_key() == "file-key-9"


def test_connection_refused_is_a_compose_error(monkeypatch):
    monkeypatch.setenv("MOM_ASSISTANT_URL", "http://127.0.0.1:9")     # 아무도 안 듣는 포트
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "unit-test-key-123")
    monkeypatch.setattr(LC, "HTTP_TIMEOUT_S", 2.0)
    with pytest.raises(ComposeHttpError):
        LC.http_post("shift_report", [{"id": "L1", "text": "x"}])


# ------------------------------------------------------------------ 시연 서버에 끼운 모양
def test_sim_server_only_replaces_finished_unsaved_drafts(monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdout", io.StringIO())          # sim_server가 불러올 때 표준 출력을 바꾸므로, buffer가 없는 것으로 막는다
    import sim_server as SS
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    base = {"shift_id": "2026-10-01-D", "status": "AI_DRAFT", "partial": False, "notable_text": " ".join(DRAFT), "current_version": 0}
    assert SS.shift_with_llm(base) == base                                # 처음엔 준비 전 → 그대로
    SS.COMPOSER.wait_idle()
    got = SS.shift_with_llm(base)
    assert got["notable_text"] == " ".join("다듬음: " + t for t in DRAFT)
    assert got["current_version"] == 0 and got is not base                # 버전은 안 올리고 원본 dict는 안 바꾼다
    assert base["notable_text"] == " ".join(DRAFT)
    for untouched in ({**base, "partial": True}, {**base, "status": "EDITING"}, {**base, "status": "CONFIRMED"}):
        assert SS.shift_with_llm(untouched) == untouched                  # 진행 중·사람이 고친·확정된 보고서는 안 건드린다
    assert SS.shift_with_llm(None) is None


# ------------------------------------------------------------------ 작업지시서 제목·증상 입구
def _sim_server(monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    import sim_server as SS
    return SS


def test_work_order_text_is_two_step_and_sends_title_and_symptom_ids(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"no": "MW-950", "title": "VF2-01 알람 2075 점검", "symptom": "공기압이 낮다는 알람 2075가 떴다."}
    assert SS.work_order_text(body) == {"ready": False}               # 첫 질문: 바로 돌아오고 백그라운드로 비서를 부른다
    SS.COMPOSER.wait_idle()
    res = SS.work_order_text(body)
    assert res == {"ready": True, "title": "다듬음: " + body["title"], "symptom": "다듬음: " + body["symptom"]}
    assert fake.calls[0][0] == "work_order" and [l["id"] for l in fake.calls[0][1]] == ["title", "symptom"]
    assert len(fake.calls) == 1


def test_work_order_text_off_or_changed_text_is_not_ready(monkeypatch):
    SS = _sim_server(monkeypatch)
    SS.COMPOSER = Composer(run_id=lambda: 1, post=Fake(), enabled=False)
    body = {"no": "MW-951", "title": "제목", "symptom": "증상"}
    assert SS.work_order_text(body) == {"ready": False}               # 꺼짐 — 화면은 기본 문장 그대로
    SS.COMPOSER = Composer(run_id=lambda: 1, post=Fake(), enabled=True)
    SS.work_order_text(body)
    SS.COMPOSER.wait_idle()
    assert SS.work_order_text({**body, "title": "사람이 고친 제목"})["ready"] is False      # 입력이 바뀌면 옛 문장을 안 준다


@pytest.mark.parametrize("bad", [{}, {"no": "X-1", "title": "t", "symptom": "s"}, {"no": "MW-950", "title": "", "symptom": "s"},
                                 {"no": "MW-950", "title": "t", "symptom": "x" * 601}, {"no": "MW-950", "title": "t" * 301, "symptom": "s"}])
def test_work_order_text_rejects_bad_requests(monkeypatch, bad):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    with pytest.raises(SS.ApiError) as e:
        SS.work_order_text(bad)
    assert e.value.status == 400 and fake.calls == []
