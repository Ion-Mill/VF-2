"""시연 서버의 문장 다듬기 도우미(llm_compose.py) 시험 — 실제 비서·Claude를 부르지 않는다 (가짜 post와 가짜 HTTP 서버).

실행 (frontend/ 폴더에서):  ..\\데이터생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
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


def test_guide_card_parts_start_while_other_jobs_hold_the_shared_seats():
    """보고서·작업지시서가 공유 자리 2개를 잡은 채 멈춰 있어도 지침카드 두 칸은 그 정지가 풀리기 전에 비서를 부른다."""
    entered = []
    lock = threading.Lock()
    others_holding = threading.Event()
    release_others = threading.Event()
    both_guides = threading.Event()

    def post(kind, lines):
        with lock:
            entered.append(kind)
            n_other = sum(1 for k in entered if k != "guide_card")
            n_guide = sum(1 for k in entered if k == "guide_card")
        if n_other >= 2:
            others_holding.set()
        if n_guide >= 2:
            both_guides.set()
        if kind != "guide_card":
            release_others.wait(3)
        return {"lines": [{"id": line["id"], "text": "다듬음: " + line["text"]} for line in lines]}

    c = Composer(run_id=lambda: 1, post=post, enabled=True)
    assert c.polished("daily_report", "D", ["문장"]) is None
    assert c.polished("work_order", "MW-1", ["제목"]) is None
    assert others_holding.wait(1.0)
    assert c.polished("guide_card", "992:steps", ["작업자 줄"]) is None
    assert c.polished("guide_card", "992:maint", ["보전 줄"]) is None
    assert both_guides.wait(1.0), entered
    assert not release_others.is_set()
    release_others.set()
    c.wait_idle()


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


# ------------------------------------------------------------------ 일일 보고서 '오늘의 문제' (생성기가 미리 만든 날짜, 2026-10-19)
def _daily_rows():
    import csv
    path = TOOLS.parents[1] / "데이터생성기" / "out" / "daily_report.csv"
    return list(csv.DictReader(open(path, encoding="utf-8")))


def _draft(rows):
    return next(r for r in rows if r["status"] == "AI_DRAFT")


def test_split_issues_reads_the_real_unconfirmed_row_and_refuses_odd_shapes(monkeypatch):
    SS = _sim_server(monkeypatch)
    head, items = SS.split_issues(_draft(_daily_rows())["issues_summary"])
    assert head.startswith("전체 8건 (") and len(items) == 8
    assert items[0].startswith("[주의] ") and items[-1].startswith("[참고] ")           # 번호("1) ")는 뗀다
    for odd in ("전체 0건", "", None, "전체 3건 (긴급 0): 1) a / 2) b",                    # 항목 수 ≠ 머리의 N
                "전체 2건 (긴급 0): 1) a / 3) b",                                          # 번호가 이어지지 않음
                "전체 1건 (긴급 0): 1) a / b",                                             # 항목 속 ' / '
                "1) a / 2) b"):                                                            # 머리 없음
        assert SS.split_issues(odd) is None


def test_daily_off_touches_nothing(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=False)
    rows = _daily_rows()
    assert [SS.daily_with_llm(dict(r)) for r in rows] == rows
    SS.COMPOSER.wait_idle()
    assert fake.calls == []


def test_daily_on_polishes_only_the_unconfirmed_draft_and_keeps_head_count_order(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    rows = _daily_rows()
    assert [SS.daily_with_llm(dict(r)) for r in rows] == rows                              # 처음엔 모두 준비 전 → 그대로 (기다리지 않는다)
    SS.COMPOSER.wait_idle()
    got = [SS.daily_with_llm(dict(r)) for r in rows]
    draft, polished = _draft(rows), _draft(got)
    changed = [a["work_date"] for a, b in zip(rows, got) if a != b]
    assert changed == [draft["work_date"]]                                                 # 확정된 보고서는 한 줄도 안 바뀐다
    head, items = SS.split_issues(draft["issues_summary"])
    phead, pitems = SS.split_issues(polished["issues_summary"])
    assert phead == head and len(pitems) == len(items) == 8                                # 머리·항목 수 그대로
    assert pitems == ["다듬음: " + t for t in items]
    assert [t.split()[1] for t in pitems] == [t.split()[0] for t in items]                  # [주의]/[참고] 순서 그대로 ("다듬음:" 다음 낱말이 꼬리표)
    assert len(fake.calls) == 1                                                           # 비서는 초안 한 건에 한 번만 불렸다
    kind, lines = fake.calls[0]
    assert kind == "daily_report" and [l["id"] for l in lines] == [f"L{i}" for i in range(1, 9)]
    assert [l["text"] for l in lines] == items and all(l["text"].startswith("[") for l in lines)    # 번호 없이, [주의]/[참고] 꼬리표는 붙인 채로 보낸다
    assert {k: v for k, v in polished.items() if k != "issues_summary"} == {k: v for k, v in draft.items() if k != "issues_summary"}


def test_daily_confirmed_or_edited_rows_are_never_sent(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    draft = _draft(_daily_rows())
    for untouched in ({**draft, "status": "CONFIRMED"}, {**draft, "status": "EDITING"}):
        assert SS.daily_with_llm(untouched) == untouched
    assert SS.daily_with_llm(None) is None
    SS.COMPOSER.wait_idle()
    assert fake.calls == []


def test_daily_failure_keeps_the_default_sentences(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake(ComposeHttpError(503, "HTTP 503"))
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    draft = _draft(_daily_rows())
    assert SS.daily_with_llm(dict(draft)) == draft
    SS.COMPOSER.wait_idle()
    assert SS.daily_with_llm(dict(draft)) == draft and len(fake.calls) == 1                # 실패 뒤에는 쉬는 동안 다시 부르지도 않는다


def test_daily_new_run_drops_the_old_polished_sentences(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake, run = Fake(), [1]
    SS.COMPOSER = Composer(run_id=lambda: run[0], post=fake, enabled=True)
    draft = _draft(_daily_rows())
    SS.daily_with_llm(dict(draft))
    SS.COMPOSER.wait_idle()
    assert SS.daily_with_llm(dict(draft))["issues_summary"] != draft["issues_summary"]
    run[0] = 2                                                                             # 시뮬레이터 '처음으로'
    assert SS.daily_with_llm(dict(draft)) == draft                                         # 옛 회차에서 받아 둔 문장을 가져가지 않는다
    SS.COMPOSER.wait_idle()
    assert len(fake.calls) == 2


def test_daily_confirm_freezes_the_sentence_the_person_saw(monkeypatch):
    SS = _sim_server(monkeypatch)
    default, shown = "전체 1건 (긴급 0): 1) [참고] 원래", "전체 1건 (긴급 0): 1) [참고] 다듬음"
    assert SS.freeze_daily_summary(default, default, None) is None                         # 기본 문장 그대로면 저장할 것이 없다
    assert SS.freeze_daily_summary(shown, default, None) == shown                          # 다듬은 문장을 봤으면 굳힌다
    assert SS.freeze_daily_summary(shown, default, "내일 확인") == shown + " / 관리자 메모: 내일 확인"
    assert SS.freeze_daily_summary(default, default, "메모") == default + " / 관리자 메모: 메모"
    assert SS.freeze_daily_summary(None, default, "메모") is None
    assert SS.freeze_daily_summary(shown, None, None) is None                              # 기본 문장을 모르면(없는 날짜) 굳히지 않는다


def test_daily_after_confirm_the_frozen_sentence_is_not_polished_again(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    draft = _draft(_daily_rows())
    SS.daily_with_llm(dict(draft))
    SS.COMPOSER.wait_idle()
    shown = SS.daily_with_llm(dict(draft))                                                 # 사람이 본 다듬은 문장
    frozen = SS.freeze_daily_summary(shown["issues_summary"], draft["issues_summary"], None)
    confirmed = {**draft, "status": "CONFIRMED", "issues_summary": frozen}
    assert SS.daily_with_llm(dict(confirmed)) == confirmed
    SS.COMPOSER.wait_idle()
    assert len(fake.calls) == 1                                                            # 확정 뒤에는 비서를 다시 부르지 않는다


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


# ------------------------------------------------------------------ 지침카드 '먼저 할 일' 입구
CARD_STEPS = ["축을 움직이지 말고 알람 이력을 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호",
              "도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다"]


def test_guide_card_text_is_two_step_and_keyed_by_alarm_code(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"code": "992", "steps": CARD_STEPS}
    assert SS.guide_card_text(body) == {"ready": False}
    SS.COMPOSER.wait_idle()
    assert SS.guide_card_text(body) == {"ready": True, "lines": ["다듬음: " + s for s in CARD_STEPS]}
    assert SS.guide_card_text({"code": "992", "steps": CARD_STEPS})["ready"]                   # 같은 코드·같은 줄은 한 번만 만든다
    assert len(fake.calls) == 1 and fake.calls[0][0] == "guide_card"


def test_guide_card_maint_is_cached_apart_from_worker_steps(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    steps = {"code": "992", "steps": CARD_STEPS}
    maint = {"code": "992", "part": "maint", "steps": ["잠금·표지 후 볼스크류가 손으로 도는지 본다"]}
    assert SS.guide_card_text(steps) == {"ready": False}
    assert SS.guide_card_text(maint) == {"ready": False}
    SS.COMPOSER.wait_idle()
    assert SS.guide_card_text(steps)["ready"] is True
    got = SS.guide_card_text(maint)
    assert got["ready"] is True and got["lines"] == ["다듬음: 잠금·표지 후 볼스크류가 손으로 도는지 본다"]
    assert len(fake.calls) == 2 and [c[0] for c in fake.calls] == ["guide_card", "guide_card"]


def test_guide_card_text_rejects_unknown_part(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    with pytest.raises(SS.ApiError) as e:
        SS.guide_card_text({"code": "992", "part": "safety", "steps": CARD_STEPS})
    assert e.value.status == 400 and fake.calls == []


def test_guide_card_text_off_means_not_ready(monkeypatch):
    SS = _sim_server(monkeypatch)
    SS.COMPOSER = Composer(run_id=lambda: 1, post=Fake(), enabled=False)
    assert SS.guide_card_text({"code": "992", "steps": CARD_STEPS}) == {"ready": False}


@pytest.mark.parametrize("bad", [{}, {"code": "", "steps": CARD_STEPS}, {"code": "99 2", "steps": CARD_STEPS}, {"code": "992", "steps": []},
                                 {"code": "992", "steps": "문자열"}, {"code": "992", "steps": ["ok", ""]}, {"code": "992", "steps": ["x" * 601]},
                                 {"code": "992", "steps": ["a"] * 13}, {"code": "992", "steps": [1, 2]}])
def test_guide_card_text_rejects_bad_requests(monkeypatch, bad):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    with pytest.raises(SS.ApiError) as e:
        SS.guide_card_text(bad)
    assert e.value.status == 400 and fake.calls == []


# ------------------------------------------------------------------ 브리핑 '먼저 챙길 일' 입구 (순위 묶음별, 2026-10-19)
def _group(rank, n, tag="항목"):
    return {"rank": rank, "lines": [f"[재고 부족] {tag} {i + 1} 재고 {i + 1}개 · 9/{i + 1}" for i in range(n)]}


def test_briefing_text_is_two_step_per_rank_group_and_keyed_by_shift_and_rank(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"shift": "2026-10-01-D", "groups": [_group("0-1", 2), _group("3", 3)]}
    assert SS.briefing_text(body) == {"ready": False, "groups": [{"rank": "0-1", "ready": False}, {"rank": "3", "ready": False}]}
    SS.COMPOSER.wait_idle()
    res = SS.briefing_text(body)
    assert res["ready"] is True and [g["rank"] for g in res["groups"]] == ["0-1", "3"]
    assert res["groups"][1]["lines"] == ["다듬음: " + t for t in body["groups"][1]["lines"]]
    assert len(fake.calls) == 2 and {c[0] for c in fake.calls} == {"briefing"}         # 묶음 둘 = 호출 둘, 다시 물어도 더 안 부른다
    assert [l["id"] for l in fake.calls[0][1]] == ["L01", "L02"] or [l["id"] for l in fake.calls[1][1]] == ["L01", "L02"]


def test_briefing_text_changed_group_is_remade_alone_and_the_old_sentence_is_never_served(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"shift": "S1", "groups": [_group("3", 2), _group("4", 2)]}
    SS.briefing_text(body)
    SS.COMPOSER.wait_idle()
    assert SS.briefing_text(body)["ready"] is True
    changed = {"shift": "S1", "groups": [_group("3", 3), _group("4", 2)]}               # 3 순위에 알람이 하나 늘었다
    res = SS.briefing_text(changed)
    assert res["ready"] is False
    assert [g["ready"] for g in res["groups"]] == [False, True]                          # 바뀐 묶음만 다시, 안 바뀐 묶음은 그대로 준비
    SS.COMPOSER.wait_idle()
    assert SS.briefing_text(changed)["ready"] is True and len(fake.calls) == 3


def test_briefing_text_group_over_40_lines_is_split_in_chunks_and_ready_only_when_all_chunks_are(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"shift": "S1", "groups": [_group("3", 45)]}
    assert SS.briefing_text(body)["ready"] is False
    SS.COMPOSER.wait_idle()
    res = SS.briefing_text(body)
    assert res["ready"] is True and len(res["groups"][0]["lines"]) == 45                 # 40 + 5 줄이 순서대로 이어진다
    assert sorted(len(c[1]) for c in fake.calls) == [5, 40] and res["groups"][0]["lines"][44].startswith("다듬음: ")


def test_briefing_text_a_group_that_fails_stays_original_while_the_others_are_served(monkeypatch):
    SS = _sim_server(monkeypatch)

    class OneBad(Fake):
        def __call__(self, kind, lines):
            if lines[0]["text"].startswith("[재고 부족] 나쁜"):
                raise ComposeHttpError(503, "HTTP 503")
            return super().__call__(kind, lines)
    fake = OneBad()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"shift": "S1", "groups": [_group("3", 2, "나쁜"), _group("4", 2)]}
    SS.briefing_text(body)
    SS.COMPOSER.wait_idle()
    res = SS.briefing_text(body)
    assert res["ready"] is False and [g["ready"] for g in res["groups"]] == [False, True]


def test_briefing_text_off_means_not_ready_and_sends_nothing(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=False)
    res = SS.briefing_text({"shift": "S1", "groups": [_group("3", 2)]})
    assert res == {"ready": False, "groups": [{"rank": "3", "ready": False}]} and fake.calls == []


@pytest.mark.parametrize("bad", [
    {}, {"shift": "", "groups": [_group("3", 1)]}, {"shift": "S 1", "groups": [_group("3", 1)]}, {"shift": "S1", "groups": []},
    {"shift": "S1", "groups": "문자열"}, {"shift": "S1", "groups": [_group("0", 1)]},                       # 안전(0)은 비서에게 보내지 않는다
    {"shift": "S1", "groups": [_group("x", 1)]}, {"shift": "S1", "groups": [_group("3", 1), _group("3", 1)]},
    {"shift": "S1", "groups": [{"rank": "3", "lines": []}]}, {"shift": "S1", "groups": [{"rank": "3", "lines": ["ok", ""]}]},
    {"shift": "S1", "groups": [{"rank": "3", "lines": ["x" * 601]}]}, {"shift": "S1", "groups": [{"rank": "3", "lines": [1, 2]}]},
    {"shift": "S1", "groups": [_group("3", 200), _group("4", 101)]}, {"shift": "S1", "groups": [_group(str(i), 1) for i in range(1, 10)]},
    {"shift": "S1", "groups": ["3"]},
])
def test_briefing_text_rejects_bad_requests(monkeypatch, bad):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    with pytest.raises(SS.ApiError) as e:
        SS.briefing_text(bad)
    assert e.value.status == 400 and fake.calls == []


def test_briefing_text_route_is_post_only(monkeypatch):
    SS = _sim_server(monkeypatch)
    SS.COMPOSER = Composer(run_id=lambda: 1, post=Fake(), enabled=False)
    src = (TOOLS / "sim_server.py").read_text(encoding="utf-8")
    assert 'key == "assist/briefing-text" and method == "POST"' in src


# ------------------------------------------------------------------ 알림 탭 알람 상세 본문 입구 (알림 하나 = 한 줄, 2026-10-19)
ALARM_LINE = "VF2-01(OP-30)에서 알람 992 — 정지. 사건 S1. 로트 LOT-2610-001-1."


def test_alarm_text_is_two_step_one_line_keyed_by_alert_id(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    body = {"id": "a-1203", "text": ALARM_LINE}
    assert SS.alarm_text(body) == {"ready": False}                       # 첫 질문: 바로 돌아오고 백그라운드로 비서를 부른다
    SS.COMPOSER.wait_idle()
    assert SS.alarm_text(body) == {"ready": True, "text": "다듬음: " + ALARM_LINE}
    assert SS.alarm_text(body)["ready"]                                  # 같은 알림·같은 문장은 한 번만 만든다
    assert len(fake.calls) == 1 and fake.calls[0] == ("alarm_notice", [{"id": "L01", "text": ALARM_LINE}])


def test_alarm_text_each_alert_is_made_alone_and_a_changed_sentence_is_remade(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    SS.alarm_text({"id": "a-1", "text": ALARM_LINE})
    SS.alarm_text({"id": "a-2", "text": ALARM_LINE})
    SS.COMPOSER.wait_idle()
    assert len(fake.calls) == 2                                          # 알림마다 따로 (안 연 알림은 안 부른다)
    cleared = ALARM_LINE + " 설비 알람 09:20 해제."
    assert SS.alarm_text({"id": "a-1", "text": cleared}) == {"ready": False}     # 해제돼 문장이 바뀜 — 옛 문장을 주지 않고 다시 만든다
    SS.COMPOSER.wait_idle()
    assert SS.alarm_text({"id": "a-1", "text": cleared}) == {"ready": True, "text": "다듬음: " + cleared}
    assert len(fake.calls) == 3


def test_alarm_text_off_means_not_ready_and_sends_nothing(monkeypatch):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=False)
    assert SS.alarm_text({"id": "a-1203", "text": ALARM_LINE}) == {"ready": False}
    SS.COMPOSER.wait_idle()
    assert fake.calls == []


def test_alarm_text_failure_is_not_ready_and_the_screen_keeps_the_original(monkeypatch):
    SS = _sim_server(monkeypatch)
    SS.COMPOSER = Composer(run_id=lambda: 1, post=Fake(ComposeHttpError(503, "HTTP 503")), enabled=True)
    SS.alarm_text({"id": "a-1203", "text": ALARM_LINE})
    SS.COMPOSER.wait_idle()
    assert SS.alarm_text({"id": "a-1203", "text": ALARM_LINE}) == {"ready": False}


@pytest.mark.parametrize("bad", [{}, {"id": "a-1203"}, {"id": "a-1203", "text": ""}, {"id": "", "text": ALARM_LINE}, {"id": "n-1203", "text": ALARM_LINE},
                                 {"id": "a-12 03", "text": ALARM_LINE}, {"id": "a-1203", "text": "x" * 301}, {"id": "a-" + "1" * 10, "text": ALARM_LINE}])
def test_alarm_text_rejects_bad_requests(monkeypatch, bad):
    SS = _sim_server(monkeypatch)
    fake = Fake()
    SS.COMPOSER = Composer(run_id=lambda: 1, post=fake, enabled=True)
    with pytest.raises(SS.ApiError) as e:
        SS.alarm_text(bad)
    assert e.value.status == 400 and fake.calls == []


def test_alarm_text_route_is_post_only(monkeypatch):
    SS = _sim_server(monkeypatch)
    SS.COMPOSER = Composer(run_id=lambda: 1, post=Fake(), enabled=False)
    src = (TOOLS / "sim_server.py").read_text(encoding="utf-8")
    assert 'key == "assist/alarm-text" and method == "POST"' in src
