"""단계별 로그 STEP_LOG 시험 (2026-10-15, `research_notes/단계별로그_STEP_LOG_총기획서_20261015.md` 시험 계획 T1~T11).

진짜 AI 서버도 외부 Claude도 부르지 않는다 — 로컬 쪽은 가짜 전송(`C.use_transport` + `httpx.MockTransport`), 외부 쪽은 가짜 `claude` 실행기(`CC.use_runner`)를 끼운다.
저장 폴더는 pytest 임시 폴더다(conftest가 STEP_LOG_DIR을 시험마다 따로 돌린다) — `C:\\llm\\logs`에는 쓰지 않는다.
지키는 것: ① 꺼져 있으면 파일이 안 생기고 답이 한 글자도 안 달라진다 ② 켜면 질문 하나에 한 줄, 4단계에 후보 줄·LLM이 고른 줄 번호가 남는다
③ 알람·운영 질문은 줄 고르기 칸이 없다 ④ 표 채우기 전후 줄 번호 ⑤ LLM 호출의 성공·시간 초과·형식 오류 ⑥ 외부 Claude 실패가 재료/다듬기로 나뉜다
⑦ 폴더 쓰기 실패·상한 초과에도 답이 나온다 ⑧ 비밀값이 없고 크기 상한이 지켜진다 ⑨ 두 요청이 섞이지 않는다 ⑩ 기본값이 모두 0 ⑪ 읽기 도구가 단계 표를 보인다.
"""
import dataclasses
import importlib.util
import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import Settings, settings
from backend.demo_state import get_state
from backend.eval import run_eval as R
from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import external as EXT
from backend.llm import schemas
from backend.llm.client import LlmBadOutput, LlmUnavailable
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import steplog as SL

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app_module.app)
Q_TABLE = "VF2-01 전원을 켜고 원점 복귀할 때 사람이 조심할 게 뭐야?"   # 문서 질문 — 1차 문지기는 못 지나고(사내 문서에 없는 낱말 "조심") 2차 문지기가 DOC-01 §4.3 표를 고른다
Q_COOLANT = "쿨런트가 뭐야?"                                          # 분류(route)를 부르는 다른 문서 질문
Q_ALARM = "552 뜨면 뭐부터 해?"                                       # 알람 번호 질문 — 규칙·카드만 (카드가 다루지 않는 주제 낱말이 없어 문서 찾기를 붙이지 않는다)
Q_OPS = "어제 야간 VF2-01 몇 번 멈췄어?"                              # 운영 질문 — 규칙으로 조회하고 문장 다듬기(phrase)만 LLM을 부른다 (ROUTE_POLICY=rescue)
CHUNK_ID = "DOC-01:4.3:1"
MSGS = [{"role": "system", "content": "시스템 지시"}, {"role": "user", "content": "질문 글"}]
ROUTE_DOC = {"kind": "doc", "intents": [], "equipment": [], "period": "none", "shift": "none",
             "search_queries": ["전원 켜기 원점 복귀 주의", "POWER UP 원점 복귀"], "doc_question": ""}


@pytest.fixture(autouse=True)
def fresh():
    get_state().reset()
    SL.reset_counters()
    yield
    C.use_transport(None)
    CC.use_runner(None)
    assert not SL.on()   # 어떤 시험이 끝나도 기록 상자가 남아 있으면 안 된다 (다음 요청에 새면 안 됨)


# ------------------------------------------------------------------ 도우미
def flow_env(monkeypatch, step_log="1", **over):
    """문서 질문이 분류 → 2차 문지기 줄 고르기 → 따로 검증까지 가는 앱 값 (새로 쓰기·안전 새로쓰기는 끔 — 이 시험은 줄 고르기까지 본다)."""
    for k, v in R.MODES["step20-gate"].items():
        monkeypatch.setenv(k, v)
    for k in ("DOC_WRITE", "SAFE_WRITE_CARD", "SAFE_WRITE_DOC", "SAFE_WRITE_PROC", "SAFE_WRITE_WORDS"):
        monkeypatch.setenv(k, "0")
    monkeypatch.setenv("TABLE_FILL_V18", "1")
    monkeypatch.setenv("STEP_LOG", step_log)
    for k, v in over.items():
        monkeypatch.setenv(k, v)


def completion(payload=None, raw=None):
    content = raw if raw is not None else json.dumps(payload, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]})


def picked_rows(numbers="2-5"):
    """전원 켜기 표(DOC-01 §4.3 ①)의 줄 글 — 화면에서 본 꼴(2~5번만 고름)을 흉내 낸다."""
    plain = A.plain_lines(next(c for c in load_corpus() if c.chunk_id == CHUNK_ID))
    rows = [t for t in plain if re.match(rf"^[{numbers}] — 할 일: ", t)][:4 if numbers == "2-5" else 6]
    assert rows
    return rows


def make_handler(picked=None, seen=None, barrier=None, verify_ok=True, select_fail=False):
    """가짜 로컬 AI 서버: route(문서 질문) · select(picked에 든 줄만 고름) · verify(답할 수 있음). 그 밖의 작업은 HTTP 500.
    verify_ok=False면 따로 검증이 "답 못 함", select_fail=True면 줄 고르기 호출이 HTTP 500."""
    picked = list(picked or [])

    def handler(req):
        if not req.content:
            return httpx.Response(200, json={"status": "ok"})
        body = json.loads(req.content)
        name = ((body.get("response_format") or {}).get("json_schema") or {}).get("name") or ("grammar" if body.get("grammar") else "?")
        if seen is not None:
            seen.append(name)
        user = body["messages"][-1]["content"]
        if name == "route":
            if barrier is not None:
                try:
                    barrier.wait(10)
                except threading.BrokenBarrierError:
                    pass
            return completion(ROUTE_DOC)
        if name == "select":
            if select_fail:
                return httpx.Response(500, json={"error": "시험: 줄 고르기 실패"})
            by_id = {m.group(1): m.group(2) for m in re.finditer(r"^(L\d+): (.*)$", user, re.M)}
            ids = [i for i, t in by_id.items() if t in picked]
            return completion({"answerable": bool(ids), "line_ids": ids[:6], "lead": "원점 복귀 전 순서와 주의"})
        if name == "verify":
            return completion({"answers": True, "missing": ""} if verify_ok else {"answers": False, "missing": "시험: 모자란 것"})
        return httpx.Response(500, json={"error": f"시험: 모르는 작업 {name}"})
    return handler


def log_dir(tmp_path):
    return tmp_path / "steplog"


def read_log(tmp_path) -> list[dict]:
    out = []
    for f in sorted(log_dir(tmp_path).glob("steps_*.jsonl")):
        out += [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines()]
    return out


def steps_named(rec, name):
    return [s for s in rec["단계"] if s["단계"] == name]


def norm(v):
    """답 비교용 — 시간(ms)과 로그 번호는 실행마다 다르다."""
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items() if k not in ("ms", "step_log_id")}
    if isinstance(v, list):
        return [norm(x) for x in v]
    return v


def run_table(monkeypatch, step_log="1", **over):
    flow_env(monkeypatch, step_log, **over)
    seen: list[str] = []
    C.use_transport(httpx.MockTransport(make_handler(picked_rows(), seen)))
    return A.answer(Q_TABLE, "OPR"), seen


# ------------------------------------------------------------------ T1 꺼짐: 파일이 안 생기고 답이 같다
def test_t1_off_writes_nothing_and_the_answer_is_identical(monkeypatch, tmp_path):
    a_off, seen_off = run_table(monkeypatch, "0")
    assert a_off["status"] == "답변" and "step_log_id" not in a_off
    assert not log_dir(tmp_path).exists()                                     # 폴더도 만들지 않는다
    assert SL.status() == {"written": 0, "skipped": 0, "errors": 0}
    a_on, seen_on = run_table(monkeypatch, "1")
    assert a_on["step_log_id"] and seen_on == seen_off                        # 켜도 LLM을 부른 순서·횟수가 같다 (기록은 읽기만 한다)
    assert norm(a_on) == norm(a_off)                                          # 답이 한 글자도 다르지 않다 (로그 번호·ms 빼고)


def test_t1_off_calls_skip_the_logging_wrapper(monkeypatch, tmp_path):
    flow_env(monkeypatch, "0")
    C.use_transport(httpx.MockTransport(make_handler()))
    monkeypatch.setattr(C, "_chat_json_logged", lambda *a, **k: (_ for _ in ()).throw(AssertionError("꺼진 요청이 기록 껍데기를 탔다")))
    assert C.chat_json(MSGS, schemas.ANSWER_FAITH, "verify", 120) == {"answers": True, "missing": ""}
    assert not SL.on() and SL.now_ms() is None and SL.current_id() is None


# ------------------------------------------------------------------ T2 켬 + 문서 질문: 한 줄, 유효한 JSON, 4단계 후보 줄·고른 line_ids
def test_t2_document_question_leaves_one_valid_line_with_candidates_and_chosen_ids(monkeypatch, tmp_path):
    a, seen = run_table(monkeypatch)
    assert a["status"] == "답변" and seen == ["route", "select", "verify"]
    recs = read_log(tmp_path)
    assert len(recs) == 1
    rec = recs[0]
    assert a["step_log_id"] == rec["log_id"] and re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", rec["log_id"])
    assert rec["형식"] == 1 and rec["질문"] == Q_TABLE and rec["역할"] == "OPR" and rec["공급자"] == "로컬 Qwen" and rec["앞답있음"] is False
    assert [s["t_ms"] for s in rec["단계"]] == sorted(s["t_ms"] for s in rec["단계"])      # 시간 순서
    names = [s["단계"] for s in rec["단계"]]
    for must in ("1 규칙", "2 질문 분류", "3 찾기", "4 줄 고르기", "5 따로 검증", "6 코드 검사"):
        assert must in names, names
    first = steps_named(rec, "3 찾기")[0]
    assert first["길"] == "1차 문지기" and first["통과"] is False and "조심" in first["낱말"]   # 1차에서 막힌 까닭이 남는다
    sel = steps_named(rec, "4 줄 고르기")[0]
    cands = [c for c in sel["후보"] if c["조각"] == CHUNK_ID]
    for n in range(1, 7):                                                     # 표의 1~6번 줄이 모두 LLM에게 후보로 보였다
        assert any(c["앞40자"].startswith(f"{n} — 할 일: ") for c in cands), n
    assert all(len(c["앞40자"]) <= SL.CAND_CHARS + 1 for c in sel["후보"])    # 후보 줄은 앞 40자만
    chosen = [c for c in sel["후보"] if c["L"] in sel["고른번호"]]
    assert [c["앞40자"][:1] for c in chosen] == ["2", "3", "4", "5"]          # LLM이 고른 줄 번호가 2~5번 줄이다
    assert sel["시도"][0]["line_ids"] == sel["고른번호"] and sel["시도"][0]["검사"] == "통과" and sel["결과"] == "성공"
    assert sel["고른줄"] == picked_rows()                                      # 고른 줄은 전문
    ver = steps_named(rec, "5 따로 검증")[0]
    assert ver["answers"] is True
    cat = steps_named(rec, "6 코드 검사")[0]
    assert cat["길"] == "2차 문지기" and cat["결과"] == "통과" and cat["답종류검사"] is True
    calls = rec["LLM호출"]
    assert [c["작업"] for c in calls] == ["route", "select", "verify"] and all(c["결과"] == "성공" and c["구분"] == "재료" for c in calls)
    assert calls[1]["받은JSON"]["line_ids"] == sel["고른번호"]                 # LLM이 돌려준 JSON도 그대로 남는다
    fin = rec["최종"]
    assert fin["status"] == "답변" and fin["줄"] and "DOC-01" in " ".join(fin["출처"]) and fin["llm_trace"]


def test_t2_a_line_per_question_and_early_returns_are_logged(monkeypatch, tmp_path):
    flow_env(monkeypatch)
    C.use_transport(httpx.MockTransport(make_handler()))
    A.answer("VF2-01 켜 줘", "OPR")                                           # 사람만 할 일 — 규칙이 거절하고 끝난다
    A.answer("이 화면 설명해 줘", "OPR", {"screen": "SCR-10"})
    A.answer("아무거나", "MON")                                                # 비서를 쓸 수 없는 역할
    recs = read_log(tmp_path)
    assert len(recs) == 3 and SL.status()["written"] == 3
    assert any("사람만 할 일" in s.get("결과", "") for s in recs[0]["단계"])
    assert any(s.get("결과") == "화면 설명 질문" for s in recs[1]["단계"])
    assert recs[2]["최종"]["status"] == "권한이 없습니다"


def test_t2_refusals_and_failures_at_each_stage_are_visible(monkeypatch, tmp_path):
    """LLM이 "답할 줄 없음"이라 했을 때 / 줄 고르기 호출이 실패했을 때 / 따로 검증이 "답 못 함"일 때 — 어느 단계에서 왜 막혔는지 로그에 남는다."""
    flow_env(monkeypatch)
    C.use_transport(httpx.MockTransport(make_handler(picked=[])))                       # 고를 줄이 없다
    a1 = A.answer(Q_TABLE, "OPR")
    C.use_transport(httpx.MockTransport(make_handler(picked=picked_rows(), select_fail=True)))
    a2 = A.answer(Q_TABLE, "OPR")
    C.use_transport(httpx.MockTransport(make_handler(picked=picked_rows(), verify_ok=False)))
    a3 = A.answer(Q_TABLE, "OPR")
    assert [a["status"] for a in (a1, a2, a3)] == ["문서에 없음"] * 3
    r1, r2, r3 = read_log(tmp_path)
    s1 = steps_named(r1, "4 줄 고르기")[0]
    assert s1["고른번호"] is None and s1["결과"].startswith("답할 줄 없음") and s1["시도"][0]["answerable"] is False and not steps_named(r1, "5 따로 검증")
    s2 = steps_named(r2, "4 줄 고르기")[0]
    assert s2["고른번호"] is None and s2["시도"] == [{"LLM": "호출 실패", "까닭": "HTTP 500"}] and "LLM 오류" in s2["결과"]
    assert [c["결과"] for c in r2["LLM호출"] if c["작업"] == "select"] == ["실패"]
    v3 = steps_named(r3, "5 따로 검증")[0]
    assert v3["판정"] == "답 못 함" and v3["answers"] is False and v3["missing"] == "시험: 모자란 것"
    assert steps_named(r3, "4 줄 고르기")[0]["결과"] == "성공" and not steps_named(r3, "6 코드 검사")


def write_flow(monkeypatch, answer_text):
    """새로 쓰기를 켠 문서 질문 한 번 — 용어집 "Coolant" 줄을 고르고, 새로 쓰는 호출(문법 길)이 answer_text를 돌려준다."""
    flow_env(monkeypatch, DOC_WRITE="1")
    seen: list[str] = []

    def handler(req):
        body = json.loads(req.content)
        name = ((body.get("response_format") or {}).get("json_schema") or {}).get("name") or ("grammar" if body.get("grammar") else "?")
        seen.append(name)
        user = body["messages"][-1]["content"]
        if name == "route":
            return completion({**ROUTE_DOC, "search_queries": ["쿨런트 뜻"]})
        if name == "select":
            by_id = {m.group(1): m.group(2) for m in re.finditer(r"^(L\d+): (.*)$", user, re.M)}
            ids = [i for i, t in by_id.items() if t.startswith("Coolant — 표준어")][:1]
            return completion({"answerable": bool(ids), "line_ids": ids, "lead": ""})
        if name == "verify":
            return completion({"answers": True, "missing": ""})
        if name == "grammar":
            return completion({"answer": answer_text})
        if name in ("answer_faith", "lead_faith"):
            return completion({"faithful": True, "problem": ""})
        return httpx.Response(500, json={"error": name})

    C.use_transport(httpx.MockTransport(handler))
    return A.answer(Q_COOLANT, "OPR"), seen


def test_t2_a_written_answer_is_logged_with_the_raw_placeholders_and_the_restored_text(monkeypatch, tmp_path):
    a, seen = write_flow(monkeypatch, "{{1}}의 표준어는 '절삭유'예요.")
    assert a["status"] == "답변" and a["written"] is True and seen == ["route", "select", "verify", "grammar", "answer_faith"]
    rec = read_log(tmp_path)[0]
    assert steps_named(rec, "7 새로 써도 되나")[0]["결과"] == "plain"
    w = steps_named(rec, "9 새로 쓰기")[0]
    assert w["길"] == "1차 문지기" and w["새글있음"] is True and w["쓴글"] == "Coolant의 표준어는 '절삭유'예요."
    assert [t["job"] for t in w["시도"]] == ["write_answer", "answer_faith"] and all(t["used"] for t in w["시도"])
    call = {c["작업"]: c for c in rec["LLM호출"]}
    assert call["write_answer"]["문법"] is True and call["write_answer"]["구분"] == "다듬기"
    assert call["write_answer"]["받은JSON"] == {"answer": "{{1}}의 표준어는 '절삭유'예요."}     # LLM이 쓴 자리표 그대로 — 되채운 글(쓴글)과 나란히 본다
    fin = rec["최종"]
    assert fin["새로쓴답"] == w["쓴글"] and "AI가 문서를 보고 쓴 답 · 원문 아래" in fin["꼬리표"] and fin["줄"][0].startswith("Coolant — 표준어")


def test_t2_a_rejected_written_answer_keeps_the_rejected_text_and_the_reason(monkeypatch, tmp_path):
    a, seen = write_flow(monkeypatch, "{{1}}는 아무 때나 써도 돼요.")
    assert a["status"] == "답변" and "written" not in a and a["conclusion"].count("Coolant — 표준어") == 1      # 걸리면 원문 줄로 돌아간다
    rec = read_log(tmp_path)[0]
    w = steps_named(rec, "9 새로 쓰기")[0]
    assert w["새글있음"] is False and w["쓴글"] is None
    t = w["시도"][0]
    assert t["job"] == "write_answer" and t["tries"] == 2 and t["used"] is False
    assert t["rejected"] and all("허락" in r["reason"] and r["text"] == "Coolant는 아무 때나 써도 돼요." for r in t["rejected"])
    assert [c["작업"] for c in rec["LLM호출"]].count("write_answer") == 2 and rec["최종"]["새로쓴답"] is None


def test_the_alarm_plus_document_question_logs_both_card_and_selection(monkeypatch, tmp_path):
    """카드와 문서 찾기를 함께 하는 알람 질문("552 알람 뜨면 어떻게 해?")은 카드 단계와 줄 고르기 단계가 한 줄에 나란히 남는다."""
    flow_env(monkeypatch)
    C.use_transport(httpx.MockTransport(make_handler()))
    A.answer("552 알람 뜨면 어떻게 해?", "OPR")
    rec = read_log(tmp_path)[0]
    names = [s["단계"] for s in rec["단계"]]
    assert "알람 카드" in names and "4 줄 고르기" in names and names.index("알람 카드") < names.index("4 줄 고르기")
    assert steps_named(rec, "3 찾기 준비")[0]["알람과문서함께"] is True and steps_named(rec, "3 찾기 준비")[0]["카드가보인절"]


# ------------------------------------------------------------------ T3 알람·운영 질문은 해당 단계만
def test_t3_alarm_question_has_card_and_route_skip_but_no_line_selection(monkeypatch, tmp_path):
    flow_env(monkeypatch)
    seen: list[str] = []
    C.use_transport(httpx.MockTransport(make_handler(seen=seen)))
    a = A.answer(Q_ALARM, "OPR")
    rec = read_log(tmp_path)[0]
    names = [s["단계"] for s in rec["단계"]]
    assert a["status"] == "답변" and "알람 카드" in names and "1 규칙" in names
    assert "4 줄 고르기" not in names and "5 따로 검증" not in names and rec["LLM호출"] == [] and seen == []
    skip = steps_named(rec, "2 질문 분류")[0]
    assert skip["사용"] is False and "알람 번호" in skip["까닭"]
    assert steps_named(rec, "알람 카드")[0]["알람"] == "552" and steps_named(rec, "알람 카드")[0]["점검순서수"] >= 1
    assert steps_named(rec, "1 규칙")[0]["파싱"]["alarms"][0]["code"] == "552"


def test_t3_ops_question_has_the_lookup_step_and_no_line_selection(monkeypatch, tmp_path):
    flow_env(monkeypatch, LLM_JOBS="write", ROUTE_POLICY="rescue")
    seen: list[str] = []
    C.use_transport(httpx.MockTransport(make_handler(seen=seen)))
    a = A.answer(Q_OPS, "SUP")
    rec = read_log(tmp_path)[0]
    names = [s["단계"] for s in rec["단계"]]
    assert a["status"] == "답변" and "운영 조회" in names
    assert "4 줄 고르기" not in names and "5 따로 검증" not in names and "3 찾기" not in names
    look = steps_named(rec, "운영 조회")[0]
    assert look["의도"] and look["도구"] and all(t["tool"] for t in look["도구"]) and look["초안"]
    assert steps_named(rec, "2 질문 분류")[0]["사용"] is False
    phrase = [c for c in rec["LLM호출"] if c["작업"] == "phrase"]
    assert phrase and phrase[0]["결과"] == "실패" and phrase[0]["구분"] == "다듬기" and "500" in phrase[0]["까닭"]   # 다듬기 실패는 원문(기본 문장)으로 답한다
    assert "phrase" in seen


# ------------------------------------------------------------------ T4 표 채우기 전후 줄 번호
def test_t4_table_fill_shows_the_row_numbers_before_and_after(monkeypatch, tmp_path):
    a, _ = run_table(monkeypatch)
    shown = [n for n in range(1, 7) if re.search(rf"(?<![0-9]){n} — 할 일: ", a["conclusion"])]
    assert shown == [1, 2, 3, 4, 5, 6]
    rec = read_log(tmp_path)[0]
    fill = steps_named(rec, "보인 줄 채우기")[0]
    assert fill["바뀜"] is True and fill["전번호"] == [2, 3, 4, 5] and fill["후번호"] == [1, 2, 3, 4, 5, 6] and fill["조각"] == [CHUNK_ID]
    assert fill["전"][0].startswith("2 — 할 일: ") and fill["후"][0].startswith("1 — 할 일: ") and fill["후"][5].startswith("6 — 할 일: ")
    sel = steps_named(rec, "4 줄 고르기")[0]      # 고른 줄(2~5번) → 채운 뒤 보인 줄(1~6번): 두 칸을 나란히 보면 어느 단계에서 늘었는지 알 수 있다
    assert len(sel["고른번호"]) == 4 and len(rec["최종"]["줄"]) == 6


def test_t4_the_log_also_says_when_the_fill_is_off(monkeypatch, tmp_path):
    a, _ = run_table(monkeypatch, TABLE_FILL_V18="0")
    shown = [n for n in range(1, 7) if re.search(rf"(?<![0-9]){n} — 할 일: ", a["conclusion"])]
    assert shown == [2, 3, 4, 5]                                              # 스위치를 끄면 화면에서 본 꼴 그대로
    fill = steps_named(read_log(tmp_path)[0], "보인 줄 채우기")[0]
    assert fill["바뀜"] is False and "꺼져" in fill["까닭"] and fill["전번호"] == [2, 3, 4, 5]


# ------------------------------------------------------------------ T5 LLM 호출 기록: 성공·시간 초과·형식 오류
def test_t5_llm_call_records_success_timeout_bad_json_and_http_error(monkeypatch, tmp_path):
    flow_env(monkeypatch)
    state = {"mode": "ok"}

    def handler(req):
        if state["mode"] == "timeout":
            raise httpx.ReadTimeout("시험: 시간 초과")
        if state["mode"] == "http500":
            return httpx.Response(500, json={"error": "x"})
        return completion(raw="JSON이 아닌 글" if state["mode"] == "garbage" else None, payload={"faithful": True, "problem": ""})

    C.use_transport(httpx.MockTransport(handler))
    box = SL.begin(str(log_dir(tmp_path)), question="질문", role="SUP", provider="로컬 Qwen")
    try:
        assert C.chat_json(MSGS, schemas.ANSWER_FAITH, "answer_faith", 120) == {"faithful": True, "problem": ""}
        state["mode"] = "timeout"
        with pytest.raises(LlmUnavailable, match="시간 초과"):
            C.chat_json(MSGS, schemas.VERIFY, "verify", 120)
        state["mode"] = "garbage"
        with pytest.raises(LlmBadOutput, match="JSON 아님"):
            C.chat_json(MSGS, schemas.FAITH, "faith", 120)
        state["mode"] = "http500"
        with pytest.raises(LlmUnavailable, match="HTTP 500"):
            C.chat_json(MSGS, {"type": "object"}, "select", 300)
    finally:
        SL.end(box, final={"단계": "12 최종"})
    ok, to, bad, http = read_log(tmp_path)[0]["LLM호출"]
    sent = len("시스템 지시") + len("질문 글")
    assert (ok["작업"], ok["구분"], ok["결과"], ok["공급자"], ok["보낸글자수"]) == ("answer_faith", "다듬기", "성공", "로컬 Qwen", sent)
    assert ok["받은JSON"] == {"faithful": True, "problem": ""} and isinstance(ok["ms"], int) and "예외" not in ok
    assert (to["작업"], to["구분"], to["결과"], to["예외"]) == ("verify", "재료", "실패", "LlmUnavailable") and "시간 초과" in to["까닭"] and "받은JSON" not in to
    assert (bad["작업"], bad["구분"], bad["예외"], bad["까닭"]) == ("faith", "다듬기", "LlmBadOutput", "JSON 아님")
    assert (http["작업"], http["구분"], http["예외"], http["까닭"]) == ("select", "재료", "LlmUnavailable", "HTTP 500")
    assert all(c["시작ms"] is not None and c["시작ms"] >= 0 for c in (ok, to, bad, http))


# ------------------------------------------------------------------ T6 외부 Claude 요청: 실패가 재료/다듬기로 나뉘어 남는다
class Runner:
    """가짜 `claude` 실행기 (test_external_switch.py와 같은 방식): 늘 시간 초과."""

    def __init__(self):
        self.calls = 0

    def __call__(self, cmd, stdin_text, timeout):
        self.calls += 1
        raise subprocess.TimeoutExpired(cmd, timeout)


def test_t6_external_material_failure_is_logged_with_the_error_and_the_split(monkeypatch, tmp_path):
    flow_env(monkeypatch, EXTERNAL_LLM_APP="1")
    CC.use_runner(Runner())
    local_seen: list[str] = []
    C.use_transport(httpx.MockTransport(make_handler(seen=local_seen)))
    with EXT.external_request("claude"):
        with pytest.raises(EXT.ExternalLlmFailure) as ei:
            A.answer(Q_COOLANT, "SUP")                                        # 재료 단계(route)의 외부 호출 실패 → 오류로 끝난다 (답을 바꾸지 않는다)
    assert ei.value.job == "route" and local_seen == []                       # 로컬 Qwen으로 몰래 바꾸지 않았다
    rec = read_log(tmp_path)[0]                                               # 오류로 끝나도 거기까지의 기록은 남는다
    assert rec["공급자"] == "외부 Claude" and "step_log_id" not in rec
    call = rec["LLM호출"][0]
    assert (call["작업"], call["구분"], call["결과"], call["공급자"]) == ("route", "재료", "실패", "외부 Claude") and "시간 초과" in call["까닭"]
    err = rec["최종"]["오류"]
    assert err["종류"] == "ExternalLlmFailure" and err["작업"] == "route" and err["까닭"]
    assert SL.status()["written"] == 1


def test_t6_external_polish_failure_is_logged_as_polish_and_the_answer_still_comes(monkeypatch, tmp_path):
    flow_env(monkeypatch, EXTERNAL_LLM_APP="1", LLM_JOBS="write", ROUTE_POLICY="rescue")
    runner = Runner()
    CC.use_runner(runner)
    with EXT.external_request("claude") as ext:
        a = A.answer(Q_OPS, "SUP")                                            # 다듬기(phrase) 실패 → 기본 문장(원문)으로 답한다
    assert a["status"] == "답변" and a["step_log_id"] and ext.failures
    rec = read_log(tmp_path)[0]
    calls = [c for c in rec["LLM호출"] if c["작업"] == "phrase"]
    assert calls and all((c["구분"], c["결과"], c["공급자"]) == ("다듬기", "실패", "외부 Claude") for c in calls)
    fin = rec["최종"]
    assert fin["외부호출"]["호출수"] == ext.calls == runner.calls and fin["외부호출"]["실패"] and fin["외부호출"]["실패"][0][0] == "phrase"
    assert rec["공급자"] == "외부 Claude"


# ------------------------------------------------------------------ T7 폴더 쓰기 실패·상한 초과에도 답이 나온다
def test_t7_unwritable_folder_does_not_block_the_answer(monkeypatch, tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("파일이라 그 밑에는 폴더를 만들 수 없다", encoding="utf-8")
    a_off, _ = run_table(monkeypatch, "0")
    a, _ = run_table(monkeypatch, "1", STEP_LOG_DIR=str(blocker / "sub"))
    assert a["status"] == "답변" and "step_log_id" not in a                   # 쓰지 못했으니 번호도 알리지 않는다
    assert norm(a) == norm(a_off)                                             # 답은 그대로
    assert SL.status() == {"written": 0, "skipped": 0, "errors": 1}


def test_t7_file_and_line_limits_skip_without_touching_the_answer(monkeypatch, tmp_path):
    a1, _ = run_table(monkeypatch)
    f = next(log_dir(tmp_path).glob("steps_*.jsonl"))
    size = f.stat().st_size
    monkeypatch.setattr(SL, "MAX_FILE_BYTES", size + 10)                       # 하루 파일 상한: 이미 찬 파일에는 더 쓰지 않는다
    a2, _ = run_table(monkeypatch)
    assert a2["status"] == "답변" and "step_log_id" not in a2 and norm(a2) == norm(a1)
    assert f.stat().st_size == size and SL.status() == {"written": 1, "skipped": 1, "errors": 0}
    monkeypatch.setattr(SL, "MAX_FILE_BYTES", 50 * 1024 * 1024)
    monkeypatch.setattr(SL, "MAX_LINE_BYTES", 500)                              # 한 줄 상한: 너무 큰 줄은 쓰지 않는다
    a3, _ = run_table(monkeypatch)
    assert a3["status"] == "답변" and "step_log_id" not in a3
    assert f.stat().st_size == size and SL.status() == {"written": 1, "skipped": 2, "errors": 0}


# ------------------------------------------------------------------ T8 비밀값 없음 · 크기 상한
def test_t8_no_secrets_in_the_log(monkeypatch, tmp_path):
    key, key2 = "sk-FAKE-steplog-0123456789", "sk-ant-FAKE-steplog-abcdef"
    a, _ = run_table(monkeypatch, LLM_API_KEY=key, ANTHROPIC_API_KEY=key2, LLM_URL="http://127.0.0.1:8080")
    assert a["step_log_id"]
    text = next(log_dir(tmp_path).glob("steps_*.jsonl")).read_text(encoding="utf-8")
    for needle in (key, key2, "sk-", "Bearer", "127.0.0.1", "api_key", "Authorization", "X-Role", "X-User"):
        assert needle not in text, needle
    assert Q_TABLE in text                                                     # 질문은 남는다 (가상 데이터) — 사용자 이름·설정은 읽지도 않는다


def test_t8_size_caps_clip_texts_lists_and_received_json(tmp_path):
    box = SL.begin(str(log_dir(tmp_path)), question="질문", role="SUP", provider="로컬 Qwen", context={"screen": "SCR-10", "alarm_key": ""})
    SL.step("시험", 글="가" * 10000, 목록=list(range(1000)), 사전={f"k{i}": i for i in range(300)}, 짧은=SL.cut("나" * 100))
    SL.llm_call("select", kind="재료", provider="로컬 Qwen", t_ms=0, ms=5, ok=True, received={"큰": "다" * 10000})
    SL.llm_call("select", kind="재료", provider="로컬 Qwen", t_ms=0, ms=5, ok=False, reason="라" * 3000, error="LlmBadOutput")
    assert SL.end(box, final={"단계": "12 최종"}) == box.log_id
    rec = read_log(tmp_path)[0]
    st = rec["단계"][0]
    assert len(st["글"]) < 4100 and "…(+6000자)" in st["글"]
    assert len(st["목록"]) == SL.MAX_ITEMS + 1 and "+700개" in st["목록"][-1]
    assert len(st["사전"]) == SL.MAX_KEYS + 1 and len(st["짧은"]) == SL.CAND_CHARS + 1
    ok, bad = rec["LLM호출"]
    assert ok["받은JSON"]["잘림"] is True and len(ok["받은JSON"]["앞부분"]) == SL.MAX_RECEIVED
    assert len(bad["까닭"]) < 600
    assert rec["화면맥락"] == {"screen": "SCR-10"}                              # 빈 칸은 남기지 않는다


def test_t8_a_failing_logger_never_raises_and_never_leaks_its_box(tmp_path):
    class Bomb:
        def __str__(self):
            raise RuntimeError("시험: 글로 바꿀 수 없는 값")

    box = SL.begin(str(log_dir(tmp_path)), question="질문", role="SUP", provider="로컬 Qwen")
    SL.step("시험", 값=Bomb())                                                   # 기록 도우미가 실패해도 예외를 올리지 않는다
    SL.llm_call("select", kind="재료", provider="로컬 Qwen", t_ms=0, ms=1, ok=False, reason=Bomb(), error="X")
    assert SL.end(box, final={"값": Bomb()}) is None
    assert SL.status()["errors"] == 3 and SL.status()["written"] == 0
    assert not SL.on()                                                           # 쓰기에 실패해도 상자는 닫힌다 (다음 요청에 새지 않음)


def test_t8_a_failing_final_summary_does_not_break_the_answer(monkeypatch, tmp_path):
    flow_env(monkeypatch)
    C.use_transport(httpx.MockTransport(make_handler(picked_rows())))
    monkeypatch.setattr(A, "_final_step_log", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("시험: 최종 요약 실패")))
    a = A.answer(Q_TABLE, "OPR")
    assert a["status"] == "답변" and a["step_log_id"]                              # 요약이 실패해도 답은 나오고 줄도 남는다 (최소한의 최종 칸으로)
    assert read_log(tmp_path)[0]["최종"]["status"] == "답변"


def test_t8_a_line_over_the_limit_is_skipped_and_nothing_is_written(tmp_path):
    box = SL.begin(str(log_dir(tmp_path)), question="질문", role="SUP", provider="로컬 Qwen")
    for i in range(60):
        SL.step(f"큰 단계 {i}", 글="마" * 3900)                                 # 약 230KB → 한 줄 상한(120KB) 초과
    assert SL.end(box, final={}) is None
    assert SL.status() == {"written": 0, "skipped": 1, "errors": 0} and not list(log_dir(tmp_path).glob("steps_*.jsonl"))


# ------------------------------------------------------------------ T9 요청 두 개가 섞이지 않는다
def test_t9_two_concurrent_requests_do_not_mix(monkeypatch, tmp_path):
    flow_env(monkeypatch)
    barrier = threading.Barrier(2)                                             # 두 요청이 모두 route 호출 안에 있는 동안 서로 겹친다
    C.use_transport(httpx.MockTransport(make_handler(picked_rows(), barrier=barrier)))
    results, errors = {}, []

    def work(key, q):
        try:
            results[key] = A.answer(q, "OPR")
        except BaseException as e:   # noqa: BLE001 — 스레드 안 오류도 시험이 알아야 한다
            errors.append(e)

    ts = [threading.Thread(target=work, args=("a", Q_TABLE)), threading.Thread(target=work, args=("b", Q_COOLANT))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert not errors and set(results) == {"a", "b"}
    recs = {r["질문"]: r for r in read_log(tmp_path)}
    assert set(recs) == {Q_TABLE, Q_COOLANT} and SL.status()["written"] == 2
    assert results["a"]["step_log_id"] == recs[Q_TABLE]["log_id"] and results["b"]["step_log_id"] == recs[Q_COOLANT]["log_id"]
    assert recs[Q_TABLE]["log_id"] != recs[Q_COOLANT]["log_id"]
    for q, rec in recs.items():
        assert {s["질문"] for s in rec["단계"] if s["단계"] == "3 찾기"} <= {q}      # 다른 요청의 단계가 섞여 들어오지 않았다
        assert [c["작업"] for c in rec["LLM호출"]].count("route") == 1
    assert "4 줄 고르기" in [s["단계"] for s in recs[Q_TABLE]["단계"]]
    assert recs[Q_COOLANT]["최종"]["status"] != "답변" or recs[Q_COOLANT]["LLM호출"]   # 쿨런트 질문의 호출은 자기 줄에만 있다


# ------------------------------------------------------------------ T10 기본값 · 상태 표시
def test_t10_defaults_are_off_in_all_five_places_and_visible_in_flags_and_health(monkeypatch, tmp_path):
    fields = {f.name: f.default for f in dataclasses.fields(Settings)}
    assert fields["step_log"] is False and fields["step_log_dir"] == "C:\\llm\\logs"          # ① config 설정 칸
    assert R._BASE["STEP_LOG"] == "0" and all(R.MODES[m]["STEP_LOG"] == "0" for m in R.MODES)  # ③ 평가 모드
    for rel, needle in (("backend/tests/conftest.py", 'setenv("STEP_LOG", "0")'),               # ② 시험 고정물
                        ("backend/eval/route_eval.py", '"STEP_LOG": "0"'),                      # ④ 분류 시험 (두 곳 중 환경을 덮는 곳)
                        ("backend/tests/test_fallback_snapshot.py", '"STEP_LOG": "0"')):        # ⑤ 스냅숏 만들기 명령
        assert needle in (ROOT / rel).read_text(encoding="utf-8"), rel
    assert (ROOT / "backend/eval/route_eval.py").read_text(encoding="utf-8").count('"STEP_LOG"') >= 2   # 저장해 둔 값을 되돌리는 목록에도 있다
    s = settings()
    assert s.step_log is False and s.flags()["step_log"] is False
    assert s.step_log_dir == str(tmp_path / "steplog")                       # 시험은 임시 폴더만 쓴다
    monkeypatch.setenv("STEP_LOG_DIR", "")
    assert settings().step_log_dir == "C:\\llm\\logs"                         # 폴더를 비워 두면 기본 폴더
    h = client.get("/api/health").json()
    assert h["step_log"] == {"enabled": False, "dir": "C:\\llm\\logs", "written": 0, "skipped": 0, "errors": 0}
    assert h["llm_status"]["flags"]["step_log"] is False
    monkeypatch.setenv("STEP_LOG", "1")
    monkeypatch.setenv("STEP_LOG_DIR", str(log_dir(tmp_path)))
    h2 = client.get("/api/health").json()
    assert h2["step_log"]["enabled"] is True and h2["step_log"]["dir"] == str(log_dir(tmp_path)) and h2["llm_status"]["flags"]["step_log"] is True


def test_t10_chat_endpoint_returns_step_log_id_only_when_logging(monkeypatch, tmp_path):
    flow_env(monkeypatch, "0", LLM_ENABLED="0")
    r = client.post("/api/assistant/chat", json={"question": Q_ALARM}, headers={"X-Role": "SUP"})
    assert r.status_code == 200 and "step_log_id" not in r.json() and not log_dir(tmp_path).exists()
    monkeypatch.setenv("STEP_LOG", "1")
    r = client.post("/api/assistant/chat", json={"question": Q_ALARM}, headers={"X-Role": "SUP"})
    j = r.json()
    assert r.status_code == 200 and j["step_log_id"] == read_log(tmp_path)[0]["log_id"]
    assert client.get("/api/health").json()["step_log"]["written"] == 1


# ------------------------------------------------------------------ T11 읽기 도구
def load_viewer():
    spec = importlib.util.spec_from_file_location("step_log_view_for_test", ROOT / "scripts" / "step_log_view.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_t11_viewer_prints_a_step_table_and_is_read_only(monkeypatch, tmp_path, capsys):
    run_table(monkeypatch)
    f = next(log_dir(tmp_path).glob("steps_*.jsonl"))
    before = (f.read_bytes(), f.stat().st_mtime_ns)
    mod = load_viewer()
    monkeypatch.setattr(sys, "argv", ["step_log_view.py", "--dir", str(log_dir(tmp_path)), "--last", "1"])
    assert mod.main() == 0
    out = capsys.readouterr().out
    for must in (Q_TABLE, "단계 4 줄 고르기", "★", "LLM이 고른 줄 번호", "단계 보인 줄 채우기", "줄 번호 전 [2, 3, 4, 5] → 후 [1, 2, 3, 4, 5, 6]",
                 "LLM 호출 select (재료, 로컬 Qwen) 성공", "LLM 호출 3번: route ×1, select ×1, verify ×1", "단계 3 찾기"):
        assert must in out, must
    assert len(re.findall(r"^    ★ L\d+ ", out, re.M)) == 4                              # 고른 줄 4개에만 별표 (사내 문서 글에도 ★가 있어 표지 칸만 센다)
    assert (f.read_bytes(), f.stat().st_mtime_ns) == before                     # 읽기 전용 — 파일을 건드리지 않는다


def test_t11_viewer_command_line_filters_and_exit_codes(monkeypatch, tmp_path):
    run_table(monkeypatch)
    script = str(ROOT / "scripts" / "step_log_view.py")

    def run(*args):
        return subprocess.run([sys.executable, "-X", "utf8", script, *args], capture_output=True, text=True, encoding="utf-8", timeout=60)

    d = str(log_dir(tmp_path))
    hit = run("--dir", d, "--last", "5", "--grep", "원점")
    assert hit.returncode == 0 and "★" in hit.stdout and "기록 " in hit.stdout
    log_id = read_log(tmp_path)[0]["log_id"]
    by_id = run("--dir", d, "--id", log_id)
    assert by_id.returncode == 0 and log_id in by_id.stdout
    raw = run("--file", str(next(log_dir(tmp_path).glob("steps_*.jsonl"))), "--json")
    assert raw.returncode == 0 and json.loads(raw.stdout)["log_id"] == log_id
    assert run("--dir", d, "--grep", "이런낱말은없음").returncode == 1            # 맞는 기록이 없으면 1
    assert run("--dir", str(tmp_path / "없는폴더")).returncode == 2               # 폴더가 없으면 2
    assert run("--모르는인자").returncode == 2                                     # 모르는 인자는 오류로 끝난다
