"""보내기 직전 거르기 시험 — 요구사항 NFR-SEC-08 (2026-10-17), 테스트계획서 T-NFR-SEC-08-1.
진짜 `claude`는 부르지 않는다. 가짜 실행기가 받은 글(--system-prompt 값과 표준 입력)을 가로채 검사한다."""
import json
import logging
from types import SimpleNamespace

import pytest

from backend.llm import claude_client as CC
from backend.llm import client as C
from backend.llm import schemas
from backend.privacy import outbound_guard as OG
from backend.rag.chunker import load_corpus

OPUS = "claude-opus-5-5"
SERVICE_KEY = "svc-key-9f3a77c1d2e8"

# 사람·계정에 해당하는 글 — 외부로 나가는 글에 하나라도 남으면 안 된다
LEAKS = ["U07", "보전 담당 1", "작업자 주간 3", "사번: E12345", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJVMDcifQ.c2lnbmF0dXJl",
         "Bearer abcdef1234567890", "postgresql://user:pw@host:5432/db", "비밀번호: hunter22", SERVICE_KEY]


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setenv("MOM_ASSISTANT_KEY", SERVICE_KEY)
    OG.reset_cache()
    yield
    OG.reset_cache()


class FakeRun:
    """가로채기용 CLI 실행기: 받은 명령·표준 입력을 기록하고 정해 둔 결과를 돌려준다."""

    def __init__(self, payload=None):
        self.payload, self.calls = payload or {"answer": "답이에요."}, []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"cmd": cmd, "stdin": stdin_text})
        d = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 10, "duration_api_ms": 5, "num_turns": 1,
             "total_cost_usd": 0.001, "structured_output": self.payload,
             "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
             "modelUsage": {OPUS: {"inputTokens": 10}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(d, ensure_ascii=False), stderr="")


@pytest.fixture
def cli(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("MOM_CLAUDE_VIA", "cli")
    monkeypatch.setenv("MOM_CLAUDE_MODEL", OPUS)
    monkeypatch.setenv("MOM_CLAUDE_EFFORT", "low")
    monkeypatch.setenv("MOM_CLAUDE_COST_CAP_USD", "20")
    monkeypatch.setenv("MOM_EXTERNAL_LLM_OK", "1")
    monkeypatch.setenv("MOM_USAGE_LEDGER", str(tmp_path / "usage_t.jsonl"))
    fake = FakeRun()
    CC.use_runner(fake)
    yield fake
    CC.use_runner(None)


# ------------------------------------------------------------------ 글 한 덩어리
def test_user_ids_names_empno_and_account_info_are_masked():
    text = ("담당 U07(보전 담당 1)이 작업자 주간 3과 함께 점검. 사번: E12345. "
            "토큰 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJVMDcifQ.c2lnbmF0dXJl, Bearer abcdef1234567890, "
            "접속 postgresql://user:pw@host:5432/db, 비밀번호: hunter22, 서비스 키 " + SERVICE_KEY)
    out, hits = OG.scrub_text(text)
    for leak in LEAKS:
        assert leak not in out, leak
    assert hits["person"] >= 3 and hits["empno"] == 1 and hits["account"] >= 5
    assert "점검" in out and "담당" in out           # 일반 글은 그대로


def test_scrub_is_idempotent_and_ignores_non_text():
    once, _ = OG.scrub_text("U07 보전 담당 1")
    assert OG.scrub_text(once) == (once, {})
    assert OG.scrub_text("") == ("", {}) and OG.scrub_text(None) == (None, {})


def test_near_misses_are_not_masked():
    text = "U13 은 없는 ID, ABU07X 는 다른 낱말, 보전 담당 12 는 목록에 없음, 알람 992, 설비 VF2-01, 로트 LOT-2609-041-1"
    assert OG.scrub_text(text) == (text, {})


def test_role_title_that_already_appears_in_internal_documents_is_kept():
    out, hits = OG.scrub_text("폐기 승인은 공장 관리자 (MGR)가 한다")
    assert "공장 관리자" in out and not hits           # 사내 문서(DOC-06)에 나오는 직무명 — 사람 이름이 아니다


def test_internal_document_chunks_are_not_changed():
    changed = [c.cite for c in load_corpus() for f in (c.text, getattr(c, "title", "")) if OG.scrub_text(f)[0] != f]
    assert changed == []


def test_missing_user_list_falls_back_to_the_generic_id_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(OG, "USER_FILE", tmp_path / "nope.csv")
    OG.reset_cache()
    out, hits = OG.scrub_text("U99 가 점검")
    assert "U99" not in out and hits == {"person": 1}


def test_log_has_kinds_and_counts_but_never_the_masked_text(caplog):
    with caplog.at_level(logging.INFO, logger="assistant"):
        OG.scrub_messages([{"role": "user", "content": "U07 보전 담당 1 비밀번호: hunter22"}])
    assert "person" in caplog.text and "account" in caplog.text
    for leak in ("U07", "보전 담당", "hunter22"):
        assert leak not in caplog.text


def test_assert_clean_blocks_material_with_people_and_passes_plain_values():
    OG.assert_clean({"equipment": "VF2-01", "alarm": 992, "count": 3})
    with pytest.raises(OG.OutboundBlocked) as e:
        OG.assert_clean({"equipment": "VF2-01", "confirmed_by": "U07"})
    assert e.value.kinds == {"person": 1} and "U07" not in str(e.value)


# ------------------------------------------------------------------ 외부로 나가는 입구 (T-NFR-SEC-08-1)
def test_nothing_personal_reaches_the_claude_process(cli):
    msgs = [{"role": "system", "content": "시스템 지시: 담당 U07 보전 담당 1 은 알려 주지 않는다. " + SERVICE_KEY},
            {"role": "user", "content": "알람 992 점검. 작업자 주간 3, 사번: E12345, eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJVMDcifQ.c2lnbmF0dXJl, "
                                        "Bearer abcdef1234567890, postgresql://user:pw@host:5432/db, 비밀번호: hunter22"}]
    assert C.chat_json(msgs, schemas.WRITE_ANSWER, "write_answer", 400) == {"answer": "답이에요."}
    call = cli.calls[0]
    cmd = call["cmd"]
    sent = call["stdin"] + "\n" + cmd[cmd.index("--system-prompt") + 1] + "\n" + " ".join(cmd)
    for leak in LEAKS:
        assert leak not in sent, leak
    assert "알람 992 점검" in sent and "[사람]" in sent and "[계정정보]" in sent       # 값은 남고 사람·계정만 가려졌다


def test_original_messages_are_not_modified(cli):
    msgs = [{"role": "user", "content": "U07 질문"}]
    C.chat_json(msgs, schemas.WRITE_ANSWER, "write_answer", 400)
    assert msgs == [{"role": "user", "content": "U07 질문"}]
