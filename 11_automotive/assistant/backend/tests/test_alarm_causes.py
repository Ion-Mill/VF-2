"""알람 답의 "가능한 원인"(2026-10-19) 시험. 진짜 `claude`·네트워크·DB를 부르지 않는다 (가짜 백엔드·LLM 끔, 해요체 시험은 가짜 실행기).

배경: 채팅에서 "알람의 원인은?"을 물어도 답이 "쉬운 설명 + 점검 순서"뿐이었다. 사내 문서 DOC-03 알람 절에는 "가능한 원인" 표(§2.x) 또는 "원인 후보"(§3.x)가 있는데
알람 답 조립이 이를 읽지 않았고, 질문의 "원인·이유·왜"는 "카드가 이미 다루는 말"로 취급돼 문서 추가 검색도 안 했다
(분석: 261003_창민/알람_원인_질문_가능한원인_누락_분석_20261019.md). 이제 원인을 물을 때만 설명 바로 뒤에 소제목 "가능한 원인 (사내 문서)" 덩어리를 **원문 그대로** 붙인다.
지키는 것: ① 정답은 구현과 독립으로 DOC-03 파일에서 직접 읽는다 ② 원인 낱말이 없는 질문의 답은 그대로 ③ D-03: "근거 수준" 열·원문 출처 꼬리표는 보이지 않는다
④ "가능한 원인이 뭐야?"에서 다른 알람 절이 섞이지 않는다 ⑤ 해요체 다시 쓰기(CARD_REWRITE)는 원인 줄을 건드리지 않는다.
"""
import json
import re
from types import SimpleNamespace

import pytest

from backend.chat_mapping import to_answer_text
from backend.config import DOCS_DIR
from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.services import answer as A

APP_ON = ["PARSE_V2", "PARSE_V3", "SPLIT_Q", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP", "PARSE_V8", "FOLLOWUP_V2", "PARSE_V9", "FLOW_V9",
          "BLOCKS_V2", "PARSE_V10", "FLOW_V10", "BLOCKS_V3", "DOC_WRITE", "PARSE_V11", "LEAD_V12", "TERM_V13", "CTX_NARROW"]
SECTION = "■ 가능한 원인 (사내 문서)"
D03_TAG = re.compile(r"\[(실제|참고|가상|제안)[^\]]*?:[^\]]*\]")        # D-03: 원문 출처 꼬리표는 "[참고]"처럼 줄여 보인다 (rag/sanitize.py)
norm = lambda s: D03_TAG.sub(r"[\1]", re.sub(r"\s+", " ", s.replace("**", "")).strip())   # noqa: E731


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")


def _doc03_rows() -> dict[str, list[str]]:
    """절 번호 → 원인 글 목록. DOC-03 원본 파일을 시험이 직접 읽는다 (구현과 독립)."""
    text = next(DOCS_DIR.glob("DOC-03_*.md")).read_text(encoding="utf-8")
    out = {}
    for sec in re.split(r"(?m)^(?=### )", text):
        m = re.match(r"### ([23]\.\d+) ", sec)
        if not m:
            continue
        t = re.search(r"\| 가능한 원인[^\n]*\n\|[-| ]+\n((?:\|[^\n]*\n)+)", sec)
        if t:
            out[m.group(1)] = [norm([c.strip() for c in ln.strip().strip("|").split("|")][0]) for ln in t.group(1).strip().splitlines()]
        else:
            r = re.search(r"(?m)^\| 원인 후보\s*\|\s*(.+?)\s*\|\s*$", sec)
            if r:
                out[m.group(1)] = [norm(r.group(1))]
    return out


ROWS = _doc03_rows()
ALARMS = [(code, m["doc03_section"].split("§")[1].strip()) for code, m in A.alarm_codes().items() if "§" in (m.get("doc03_section") or "")
          and m["doc03_section"].split("§")[1].strip() in ROWS]
CAUSE_QS = ["{c} 알람 원인은?", "{c} 알람 왜 떠?", "{c} 알람 이유가 뭐야", "{c} 알람 가능한 원인이 뭐야?"]


def ask(q, ctx=None):
    a = A.answer(q, "MNT", ctx if ctx is not None else {"new_chat": "1"})
    a.pop("_followup", None)
    return a


def test_alarm_list_covers_op30_and_other_processes():
    assert len(ALARMS) == 23 and sum(sec.startswith("2.") for _, sec in ALARMS) == 15 and sum(sec.startswith("3.") for _, sec in ALARMS) == 8
    assert sum(len(ROWS[sec]) for _, sec in ALARMS) == 75          # 정답 원인 행 (§2 67 + §3 8)


# ---------------------------------------------------------------- 원인 읽기 (doc03_causes)
def test_doc03_causes_2075_is_the_table_verbatim():
    assert A.doc03_causes("DOC-03 §2.11") == [
        "윤활유 저장소가 비어 있음", "윤활 라인에 공기가 들어감 (빈 저장소가 가장 흔한 공기 유입 원인)", "체크밸브가 걸려 오일을 많이 씀",
        "HALO 매니폴드나 압력 센서 앞의 이물", "매니폴드·윤활 라인 누설", "월 1회 점검을 하지 않고 알람을 방치 → 라인에 공기 유입"]


def test_doc03_causes_other_process_keeps_the_virtual_tag():
    ref = A.alarm_codes()["WSH-01"]["doc03_section"]
    assert A.doc03_causes(ref) == ["원인 후보: 과열 / 세척액 수위 낮음 [참고]"]
    assert A.doc03_causes(A.alarm_codes()["6302.00"]["doc03_section"]) == ["원인 후보: 톱날 마모·손상, 이송 과다, 재료 걸림 [가상]"]   # [가상] 꼬리표를 지우지 않는다


@pytest.mark.parametrize("ref", ["", "DOC-03", "DOC-03 §9.99", "DOC-02 §4.11"])
def test_doc03_causes_empty_when_there_is_no_cause_table(ref):
    assert A.doc03_causes(ref) == []          # 표가 없으면 아무것도 붙이지 않는다 (DOC-02 §4.11은 설명 표뿐)


# ---------------------------------------------------------------- 원인 질문의 답
@pytest.mark.parametrize("code,sec", ALARMS)
def test_every_alarm_shows_all_its_causes_verbatim(code, sec):
    t = norm(to_answer_text(ask(f"{code} 알람 원인은?")))
    for row in ROWS[sec]:
        assert row in t, (code, row)
    assert SECTION in to_answer_text(ask(f"{code} 알람 원인은?"))


@pytest.mark.parametrize("tpl", CAUSE_QS)
def test_cause_words_all_trigger_the_section(tpl):
    t = to_answer_text(ask(tpl.format(c="2075")))
    assert SECTION in t and "월 1회 점검을 하지 않고 알람을 방치" in t


def test_section_order_is_description_causes_steps():
    a = ask("2075 알람 원인은?")
    secs = [b["text"] for b in a["blocks"] if b.get("kind") == "section"]
    assert secs[:3] == ["알람 설명", "가능한 원인 (사내 문서)", "점검 순서 (사내 문서)"], secs
    t = to_answer_text(a)
    assert t.index("■ 알람 설명") < t.index(SECTION) < t.index("■ 점검 순서")


def test_causes_are_one_chunk_so_the_screen_card_reads_them_as_one_section():
    t = to_answer_text(ask("2075 알람 원인은?"))
    chunk = next(c for c in t.split("\n\n") if c.startswith(SECTION))
    assert chunk.splitlines() == [SECTION] + A.doc03_causes("DOC-03 §2.11")


def test_carry_over_cause_question_gets_the_section_and_the_note():
    a = ask("원인은?", {"alarm_key": "2075"})
    t = to_answer_text(a)
    assert t.startswith("2075 알람 기준으로 답해요.") and SECTION in t and "HALO 매니폴드나 압력 센서 앞의 이물" in t


def test_causes_carry_the_alarm_doc_as_the_line_source_and_keep_the_evidence():
    a = ask("2075 알람 원인은?")
    assert {(e["doc_id"], e["section"]) for e in a["evidence"]} == {("DOC-02", "4.11"), ("DOC-03", "2.11")}      # 새 근거를 더하지 않는다 (같은 알람 절뿐)
    lines = [b for b in a["blocks"] if b.get("kind") == "line"]
    assert len(lines) == 6 and all(b["cite"]["doc_id"] == "DOC-03" and b["cite"]["section"] == "2.11" for b in lines)


# ---------------------------------------------------------------- 원인 낱말이 없는 질문은 그대로
@pytest.mark.parametrize("q", ["2075 알람 뭐야", "2075 알람 점검 순서 알려줘", "2075 알람 어떻게 해야 돼?", "992 알람 최근에 몇 번 났어?"])
def test_questions_without_cause_words_are_unchanged(q):
    a = ask(q)
    t = to_answer_text(a)
    assert SECTION not in t and "가능한 원인" not in a["conclusion"] and "doc03" not in str(a.get("blocks"))
    assert not any(b.get("text") == "가능한 원인 (사내 문서)" for b in a["blocks"] if b.get("kind") == "section")


def test_no_cause_words_means_the_answer_is_the_same_text_as_a_cause_question_without_the_cause_part():
    """원인 질문의 답에서 원인 덩어리만 빼면 평소 답과 같은 글이다 (다른 곳이 안 바뀐다)."""
    plain = to_answer_text(ask("2075 알람 뭐야"))
    with_cause = to_answer_text(ask("2075 알람 원인은?"))
    chunk = next(c for c in with_cause.split("\n\n") if c.startswith(SECTION))
    assert with_cause.replace(chunk + "\n\n", "") == plain


# ---------------------------------------------------------------- 엉뚱한 알람 절이 섞이지 않는다
@pytest.mark.parametrize("code,sec", ALARMS)
def test_possible_cause_question_does_not_pull_other_alarm_sections(code, sec):
    a = ask(f"{code} 알람 가능한 원인이 뭐야?")
    own = {sec, "1.4"}
    assert {e["section"] for e in a["evidence"] if e["doc_id"] == "DOC-03"} <= own | {sec.split(".")[0] + "." + sec.split(".")[1]}, (code, a["evidence"])
    assert "문서에서 더 찾은 줄" not in to_answer_text(a)


# ---------------------------------------------------------------- D-03 (원문 출처 비표시)
@pytest.mark.parametrize("code,sec", ALARMS)
def test_no_evidence_level_or_origin_tags_leak(code, sec):
    t = to_answer_text(ask(f"{code} 알람 원인은?"))
    assert "근거 수준" not in t and not re.search(r"\[(?:실제|참고|제안|가상):", t), code


# ---------------------------------------------------------------- 줄 목록 칸이 꺼져도 글에는 들어간다
def test_without_blocks_the_cause_text_is_in_the_conclusion(monkeypatch):
    monkeypatch.setenv("BLOCKS_V2", "0")
    monkeypatch.setenv("BLOCKS_V3", "0")
    a = ask("2075 알람 원인은?")
    assert A.CAUSE_HEAD + " / ".join(A.doc03_causes("DOC-03 §2.11")) in a["conclusion"]
    assert "월 1회 점검을 하지 않고 알람을 방치" in to_answer_text(a)


# ---------------------------------------------------------------- 해요체 다시 쓰기(CARD_REWRITE)는 원인 줄을 건드리지 않는다
class CardRunner:
    def __init__(self):
        self.texts = []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.texts.append(stdin_text)
        if props == ("texts",):
            segs = re.findall(r"^\d+\. (.*)$", stdin_text, re.M)
            so = {"texts": [re.sub(r"다(?=[.\s]|$)", "어요", s) for s in segs]}
        else:
            so = {"same_meaning": True, "problem": ""}
        res = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1, "total_cost_usd": 0.01,
               "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(res, ensure_ascii=False), stderr="")


def test_card_rewrite_leaves_the_cause_lines_as_the_document_wrote_them(monkeypatch):
    for k, v in {"LLM_ENABLED": "1", "LLM_JOBS": "write,route", "EXTERNAL_LLM_APP": "1", "ASSISTANT_PROVIDER": "claude", "CARD_REWRITE": "1"}.items():
        monkeypatch.setenv(k, v)
    r = CardRunner()
    CC.use_runner(r)
    try:
        with EXT.external_request("claude"):
            a = A.answer("2075 알람 원인은?", "OPR", {"new_chat": "1"})
    finally:
        CC.use_runner(None)
    assert a["card_rewrite"]["applied"] is True
    t = to_answer_text(a)
    for row in A.doc03_causes("DOC-03 §2.11"):
        assert row in t                                                    # 원인 줄은 원문 그대로
    assert "어요" in a["conclusion"]                                        # 카드 문장은 해요체로 바뀌었다 (다시 쓰기가 실제로 돌았다)
    assert all("월 1회 점검을 하지 않고" not in x for x in r.texts)         # 원인 줄은 Claude에 보내지도 않는다
