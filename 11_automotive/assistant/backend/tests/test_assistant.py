import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.rag.chunker import CorpusError, chunk_file, load_corpus
from backend.rag.sanitize import FORBIDDEN, sanitize
from backend.services.answer import answer, parse
from backend.tools import query_tools as T

QA = json.loads((Path(__file__).resolve().parents[1] / "eval" / "qa_set.json").read_text(encoding="utf-8"))["items"]
client = TestClient(app)


# ---------------------------------------------------------------- 코퍼스
def test_corpus_eight_files_and_no_source_markers():
    chunks = load_corpus()
    assert {c.doc_id for c in chunks} == {"GLOSSARY", "DOC-01", "DOC-02", "DOC-03", "DOC-04", "DOC-05", "DOC-06", "DOC-07"}
    assert all(re.match(r"Rev\.\d+ \(2026-\d\d-\d\d\)$", c.revision) for c in chunks)  # 문서마다 개정 번호가 다를 수 있다 (2026-10-08: 용어집 Rev.3, DOC-01·07 Rev.2)
    assert not [c.chunk_id for c in chunks if FORBIDDEN.search(c.text)]
    assert not [c for c in chunks if "원문 대응표" in c.title or "개정 기록" in c.title]


def test_corpus_stops_when_file_count_differs(tmp_path):
    (tmp_path / "DOC-01_x.md").write_text("# DOC-01 x\n", encoding="utf-8")
    load_corpus.cache_clear()
    try:
        with pytest.raises(CorpusError):
            load_corpus(tmp_path)
    finally:
        load_corpus.cache_clear()


def test_sanitize_strips_sources():
    s = sanitize("| 고장 대응 | DOC-03 §2.1 ← 서보 앰프 TG0125 Rev F (NGC) |\n- 근거 [실제: TG0125 Rev F 증상표]")
    assert "TG0125" not in s and "[실제]" in s and "DOC-03 §2.1" in s


@pytest.mark.parametrize("raw,want", [
    # 2026-10-11: 원문 번호 바로 뒤에 조사가 붙으면 \b가 없어 지우지도 잡지도 못했다 (DOC-04 §2·§2.1·§2.4에 남음)
    ("RD0080의 3개월 항목", "원문의 3개월 항목"),
    ("줄은 RD0080이 아니라 점검표", "줄은 원문이 아니라 점검표"),
    ("TG0125의 절차", "원문의 절차"),
    ("이하 줄은 `RD0080__RevB-2025-05__20261003__body.md`의 줄 번호", "이하 줄은 원문의 줄 번호"),   # 수집 파일 이름
    ("주입량: VFVM-SM-18에 없음", "주입량: 원문에 없음"),
    ("B-M-25-2026에 따라", "원문에 따라"),
    ("윤활유 기준표인 RD0040 Rev H를 따라", "윤활유 기준표인 원문을 따라"),   # 조사는 받침에 맞춤 (예전: "기준표인 를 따라")
    ("원문 목차(B-M-25-2026 PDF 3쪽)에는 6.6이", "원문 목차에는 6.6이"),       # 괄호째 지울 때는 "원문"을 넣지 않음
    ("KOSHA GUIDE B-M-25-2026 에너지 차단장치", "KOSHA GUIDE 에너지 차단장치"),  # 빈칸까지 지울 때도 넣지 않음
    ("RD0080 기준", "기준"),                     # 빈칸이 뒤따르면 예전처럼 지운다
])
def test_sanitize_doc_numbers_with_particles(raw, want):
    out = sanitize(raw)
    assert out == want and not FORBIDDEN.search(out)


@pytest.mark.parametrize("text", ["DOC-04 §2.1", "VF2-01의 알람", "LOT-260915-01", "ID 카드", "MR-0908", "WSH-01은"])
def test_sanitize_keeps_own_ids(text):
    assert sanitize(text) == text and not FORBIDDEN.search(text)


def test_forbidden_catches_particle_forms():
    for s in ("RD0080의", "TG0125이", "RD0080__RevB", "VFVM-SM-18에"):
        assert FORBIDDEN.search(s), s


def test_corpus_has_no_doc_numbers_after_sanitize():
    # 원래 꼴은 매뉴얼 번호를 96-8210만 보았다. 2026-10-11에 96-xxxx 전체(96-8100·96-0283D)와 서비스 알림 SA0018이
    # 조각·문서 보기에 남은 것을 찾아 넓혔다 (부품번호 93-xxxx는 원문 출처가 아니므로 넣지 않는다)
    strict = re.compile(r"(?<![A-Za-z0-9])(?:TG|RD|AD|ID)-?\d{4}(?![0-9])|(?<![0-9])96-(?:KO)?\d{4}|(?<![A-Za-z0-9])SA\d{4}(?![0-9])"
                        r"|VFVM-SM|NGC-ESM|LUBE-SM|haascnc", re.I)
    left = [(c.doc_id, c.section) for c in load_corpus() if strict.search(c.title + "\n" + c.text)]
    assert left == []
    from backend.rag.doc_view import _files, doc_body
    left = [(d, s["section"]) for d in _files() for s in doc_body(d)["sections"] if strict.search(s["title"] + "\n" + s["text"])]
    assert left == []


# ---------------------------------------------------------------- 질문 구조화
def test_alarm_key_keeps_axis():
    a = parse("1.992 알람이 떴어")["alarms"][0]
    assert (a["control"], a["axis"], a["code"]) == ("NGC", "1", "992")


def test_alarm_with_josa_and_other_process_code():
    assert parse("2075가 왜 자꾸 떠?")["alarms"][0]["code"] == "2075"
    assert parse("6302.00 알람")["alarms"][0]["code"] == "6302.00"


# ---------------------------------------------------------------- 답
def test_exact_alarm_match_comes_first():
    a = answer("992 뜨면 뭐부터 봐?", "OPR")
    assert a["evidence"][0]["cite"] == "알람 코드집 DOC-02 §4.1"
    assert a["steps"][0].startswith("★1")


def test_not_in_docs_and_defect_cause():
    assert answer("회사 점심 메뉴 뭐야?", "SUP")["status"] == "문서에 없음"
    assert answer("불량 원인이 뭐야?", "SUP")["status"] == "근거 없음"


@pytest.mark.parametrize("item", QA, ids=[i["id"] for i in QA])
def test_no_source_leak_in_any_answer(item):
    a = answer(item["q"], "SUP")
    assert not FORBIDDEN.search(json.dumps(a, ensure_ascii=False))
    for e in a["evidence"]:
        assert re.fullmatch(r"(?:.+ DOC-0\d|용어집) §[\d.]+", e["cite"])


def test_ops_numbers_match_tool_output():
    a = answer("공구 수명 90% 넘은 거 있어?", "SUP")
    rows = T.tool_life("SUP", None, 90)["rows"]
    for r in rows:
        assert f"{r['usage_pct']}%" in a["conclusion"]
    assert a["data_label"] == "가상 운영 데이터"


def test_tool_input_validation():
    with pytest.raises(T.ToolInputError):
        T.alarms("SUP", "VF9-99")


# ---------------------------------------------------------------- API·권한(서버)
def test_api_chat_and_roles():
    r = client.post("/api/assistant/chat", json={"question": "쿨런트가 뭐야?"}, headers={"X-Role": "OPR"})
    assert r.status_code == 200 and r.json()["evidence"][0]["cite"].startswith("용어집 §")
    assert client.post("/api/assistant/chat", json={"question": "x"}, headers={"X-Role": "MON"}).status_code == 403
    # 원래 기대값 403 → 2026-10-11 P4에서 401 UNAUTHORIZED: 역할 머리말이 없으면 권한이 아니라 로그인 문제 (backend/errors.py)
    r = client.post("/api/assistant/chat", json={"question": "x"})
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED"


def test_api_confirm_only_sup():
    # 주소·칸은 2026-10-11 P4에서 명세 RPT-03으로 (옛 POST /api/shift-reports/SR-260930-N/confirm + {"user"}).
    # 확정자 = X-User. 가상 데이터의 보고서는 모두 확정이라 시연 상태에 초안을 겹쳐 둔 뒤 확정한다 (services/shift_reports.py)
    from backend.demo_state import get_state
    from backend.services import shift_reports as SR
    try:
        SR.draft(get_state(), "2026-09-30-N")
        r = client.post("/api/reports/shift/2026-09-30-N/confirm", json={"version": 0}, headers={"X-Role": "OPR", "X-User": "OPR-05"})
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
        r = client.post("/api/reports/shift/2026-09-30-N/confirm", json={"version": 0}, headers={"X-Role": "SUP", "X-User": "SUP-02"})
        assert r.status_code == 200 and r.json()["confirmed_by"] == "SUP-02" and r.json()["status"] == "확정"
    finally:
        get_state().reset()


def test_api_doc_section_has_no_source():
    # 주소는 2026-10-11 P4에서 명세 DOCS-01 접두어로 (옛 /api/docs/…)
    r = client.get("/api/internal-docs/DOC-03/sections/2.1", headers={"X-Role": "MNT"})
    assert r.status_code == 200 and not FORBIDDEN.search(r.text)
    assert client.get("/api/internal-docs/DOC-03/sections/99", headers={"X-Role": "MNT"}).status_code == 404


def test_no_control_endpoints():
    paths = {r.path for r in app.routes}
    assert not [p for p in paths if re.search(r"start|stop|power|setting|parameter|approve-auto", p)]


# ---------------------------------------------------------------- 2026-10-08 평가 근본 원인 분석에서 나온 규칙
def test_criteria_vs_procedure_intent():
    from backend.services.answer import CRITERIA, PROCEDURE
    q16, q11 = "반복 알람 2단계 기준은 어떻게 돼?", "잠금·표지 작업 전 6단계가 뭐야?"
    assert CRITERIA.search(q16) and PROCEDURE.search(q16)          # 기준 질문 → 절차로 처리하지 않음
    assert PROCEDURE.search(q11) and not CRITERIA.search(q11)      # 진짜 절차 질문은 그대로


def test_criteria_question_picks_condition_table():
    a = answer("반복 알람 2단계 기준은 어떻게 돼?", "SUP")
    assert a["status"] == "답변" and "7일" in a["conclusion"]


def test_focus_word_picks_inspection_table():
    a = answer("교대 시작할 때 무엇을 점검해?", "SUP")
    assert a["status"] == "답변" and "점검" in a["conclusion"]


def test_unknown_terms_not_answered_and_verbs_ignored():
    from backend.services.answer import unknown_terms
    assert unknown_terms("공장 주차장은 어디에 있어?") == ["주차장"]
    assert unknown_terms("교대가 바뀔 때 잠금은 어떻게 넘겨?") == []
    assert answer("작업자 월급날은 언제야?", "SUP")["status"] == "문서에 없음"


def test_retention_question_goes_to_documents():
    a = answer("확정된 작업기록서는 몇 년 보관해?", "SUP")
    assert a["status"] == "답변" and "15년" in a["conclusion"] and a["evidence"][0]["doc_id"] == "DOC-07"


# ---------------------------------------------------------------- 2026-10-08 점검 순서가 잘리던 문제
def _doc03_table_rows(ref):
    """사내 문서 원본에서 점검 순서 표(# | 누가 | 할 일)의 줄 수를 따로 센다 (구현과 독립)."""
    from backend.rag.chunker import load_corpus
    doc, sec = (x.strip() for x in ref.split("§"))
    text = "\n".join(c.text for c in load_corpus() if c.doc_id == doc and c.section == sec)
    n, on = 0, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("| #") and "누가" in s and "할 일" in s:
            on = True
            continue
        if on and s.startswith("|"):
            if re.match(r"\|\s*\**★?\d+\**\s*\|", s):
                n += 1
            continue
        on = False
        if s.startswith("| 점검 |") or s.startswith("| **점검** |"):  # 다른 공정: 한 칸에 "★1 … / ★2 …"
            n += len(re.findall(r"(?:^|/ )\s*★?\d+ ", s.split("|")[2]))
    return n


def test_alarm_steps_not_truncated_for_every_alarm():
    from backend.repositories.csv_repo import get_repo
    checked = 0
    for m in get_repo().master("alarm_master"):
        if "§" not in m["doc03_section"]:
            continue
        expected = _doc03_table_rows(m["doc03_section"])
        if not expected:
            continue
        a = answer(f"{m['code']} 알람 뜨면 뭐부터 봐?", "SUP")
        assert len(a["steps"]) == expected, (m["code"], len(a["steps"]), expected)
        checked += 1
    assert checked >= 23  # OP-30 15개(점검 순서 표) + 다른 공정 8개(점검 칸)


def test_552_answer_has_steps_7_and_8():
    a = answer("552 알람 뜨면 뭐부터 봐?", "SUP")
    joined = " ".join(a["steps"])
    assert len(a["steps"]) == 8 and "AC 클램프 미터" in joined and "PSUP 기판 고장 대응 안내" in joined


def test_guide_alarm_uses_own_row_not_other_alarms():
    a = answer("613 알람 뜨면 뭐부터 봐?", "SUP")
    joined = " ".join(a["steps"])
    assert "알람 613" in joined and "공구 지름 보정" in joined
    assert "도어 장치" not in joined and not any(s.startswith(("230", "302", "314")) for s in a["steps"])


def test_work_records_answer_states_total_when_shortened():
    a = answer("2075가 왜 자꾸 떠?", "SUP")
    line = next((t for t in a["conclusion"].split("작업기록:")[1:]), "")
    assert ("전체" in line) or line.count("MR") <= 4
