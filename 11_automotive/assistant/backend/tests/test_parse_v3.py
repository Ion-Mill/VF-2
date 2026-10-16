"""규칙 보강 2차 시험 (PARSE_V3·SPLIT_Q, 2026-10-10 2차 — research_notes/로컬 LLM 연결/남은문제_업계해법_조사_20261010.md).
봉인 시험 E에서 step4가 틀린 원인별로, 고친 동작과 반대 사례(바뀌면 안 되는 것)를 함께 본다. 실제 LLM 서버 없이 본다."""
from datetime import date

import pytest

from backend.llm import jobs
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import routing as R
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)


@pytest.fixture
def v3(monkeypatch):
    monkeypatch.setenv("PARSE_V2", "1")
    monkeypatch.setenv("PARSE_V3", "1")


def _sec(doc, sec):
    return [c.title + "\n" + c.text for c in load_corpus() if c.doc_id == doc and (c.section == sec or c.section.startswith(sec + "."))]


# ---------------------------------------------------------------- 날짜 (과거 우선)
@pytest.mark.parametrize("q,start,end,shift", [
    ("26일 밤 교대는 몇개 뽑았어", date(2026, 9, 26), date(2026, 9, 26), "N"),
    ("그저께 밤 야간조는 실적 몇 개 찍었어?", date(2026, 9, 29), date(2026, 9, 29), "N"),
    ("그저께 주간에 1호기 멈춘 게 몇 번이에요?", date(2026, 9, 29), date(2026, 9, 29), "D"),
    ("18일 낮에 세척기 몇 번 섰어?", date(2026, 9, 18), date(2026, 9, 18), "D"),
    ("21일 밤에 황삭기 MIL-01 몇번 멈췃어", date(2026, 9, 21), date(2026, 9, 21), "N"),
    ("26일은 2호기가 계속 말썽이었는데. 그날 주야간 통틀어서 몇 번 멈췄어?", date(2026, 9, 26), date(2026, 9, 26), None),
    ("3일 전 1호기 몇 번 섰어?", date(2026, 9, 28), date(2026, 9, 28), None),
    ("지난주 2호기 몇 번 멈췄어?", date(2026, 9, 21), date(2026, 9, 27), None),
])
def test_dates_past_first(v3, q, start, end, shift):
    p = A.parse(q)
    assert (p["start"], p["end"], p["shift"]) == (start, end, shift), p
    assert p["intents"], p


@pytest.mark.parametrize("q", ["반복 알람은 7일 안에 몇 번이면 떠?", "보관은 30일 기준이야?", "이 정비는 3일치 소모품이면 돼?",
                               "지난 주간 교대 실적 알려줘"])
def test_durations_and_shift_words_are_not_dates(v3, q):
    p = A.parse(q)
    assert p["start"] is None or q.startswith("지난 주간"), p
    if q.startswith("지난 주간"):
        assert p["start"] is None and p["shift"] == "D"


def test_off_by_default():
    assert A.parse("26일 밤 교대는 몇개 뽑았어")["start"] is None   # 스위치를 끄면 예전 그대로


# ---------------------------------------------------------------- 붙은 말·정의 꼴·로트·공구
@pytest.mark.parametrize("q", ["M6 정지게이지는 몇바퀴까지 들어가도 합격이야?", "세척조 과열 정지 걸리면 몇 도에서 서고, 몇 도까지 내려가야 다시 돌아?",
                               "그리스 재고는 언제 한 개씩 까지는 거임?", "비상정지 버튼은 어디 있어?"])
def test_compounds_and_rule_questions_go_to_docs(v3, q):
    assert A.parse(q)["intents"] == [], A.parse(q)


@pytest.mark.parametrize("q", ["MTBF 우리말로 뭐라고 해", "툴 라이프라고 쓰면 안 된다던데 문서에 쓰는 표준어가 뭐예요?", "OEE 약자가 뭐야"])
def test_term_questions_go_to_docs(v3, q):
    assert A.parse(q)["intents"] == [], A.parse(q)


def test_term_words_keep_ops_with_equipment(v3):
    assert A.parse("1호기 MTBF 얼마야?")["intents"] == ["kpi"]                # 반대 사례: 설비가 있으면 운영 질문
    assert A.parse("어제 1호기 MTBF 뭐라고 나왔어?")["intents"] == ["kpi"]


def test_lot_id_and_tool_wording(v3):
    p = A.parse("LOT-2609-105-2 판정 났어? 지금 상태 알려줘")
    assert "lots" in p["intents"] and "equipment_status" not in p["intents"]
    assert A.parse("교체할 때 된 공구 알려 주세요")["intents"] == ["tool_life"]
    assert "alarm_count" in A.parse("이거 9월에 몇 번이나 떴어요?")["intents"]
    assert A.parse("필수 정지 몇 번이야?")["intents"] == ["stops"]   # 반대 사례: 필수 정지는 붙은 말로 빼지 않는다


# ---------------------------------------------------------------- 조작 요청 꼴
@pytest.mark.parametrize("q", ["SAW-01 지금 당장 비상정지 시켜", "2호기 다시 돌려줘, 사이클 스타트 좀 눌러", "1호기 꺼 줘"])
def test_control_requests_refused(v3, q):
    g = A.human_only(q)
    assert g and "조작하지 않습니다" in g["conclusion"], q


@pytest.mark.parametrize("q", ["비상정지는 언제 눌러?", "사이클 스타트 누르기 전에 뭘 확인해?", "2호기 지금 돌아가?"])
def test_control_questions_not_refused(v3, q):
    assert A.human_only(q) is None, q


# ---------------------------------------------------------------- 알람 세부 (값 종류 검사)
def test_alarm_detail_missing_needs_value_next_to_anchor():
    t552 = _sec("DOC-02", "4.14") + _sec("DOC-03", "2.14")
    assert A.alarm_detail_missing("552 때 갈아 끼울 CB3 차단기 부품번호 좀 알려줘", t552) is not None   # 93-2609는 임펠러 부품번호
    assert A.alarm_detail_missing("552 때 임펠러 부품번호 알려줘", t552) is None
    t966 = _sec("DOC-02", "4.7") + _sec("DOC-03", "2.7")
    assert A.alarm_detail_missing("966 관련된 Setting 245 기본값이 몇으로 돼 있어?", t966) is not None
    t254 = _sec("DOC-02", "4.9") + _sec("DOC-03", "2.9")
    assert A.alarm_detail_missing("254 떠서 주축 멈췄는데, 몇 분 식히고 다시 돌리면 돼?", t254) is not None   # 5분은 고전압 대기
    assert A.alarm_detail_missing("254 뜨면 뭐부터 봐?", t254) is None                                        # 세부를 묻지 않음


@pytest.mark.parametrize("q", ["552 때 갈아 끼울 CB3 차단기 부품번호 좀 알려줘", "966 관련된 Setting 245 기본값이 몇으로 돼 있어?",
                               "254 떠서 주축 멈췄는데, 몇 분 식히고 다시 돌리면 돼?"])
def test_alarm_detail_question_answers_not_in_docs(v3, q):
    a = A.answer(q, "SUP")
    assert a["status"] == "문서에 없음" and a["evidence"] and not a["current_data"], a["conclusion"]


def test_plain_alarm_question_unchanged(v3):
    a = A.answer("992 뜨면 뭐부터 봐?", "SUP")
    assert a["status"] == "답변" and a["steps"]


# ---------------------------------------------------------------- 섞인 질문 · 화면 알람 주제
@pytest.mark.parametrize("q,want", [
    ("일호기 9월 OEE 몇 나왔어? 몇 % 밑으로 가면 주의 떠?", "OEE 몇 % 밑으로 가면 주의 떠?"),
    ("이호기 MTTR 얼마나 나왔어? 그거 몇 분 넘으면 주의로 봐?", "MTTR 몇 분 넘으면 주의로 봐?"),
    ("지금 재고 모자란거 뭐야? 부족 알림은 누구한테 가?", "재고 부족 알림은 누구한테 가?"),
    ("어제 야간 VF2-01 몇 번 멈췄어?", "어제 야간 VF2-01 몇 번 멈췄어?"),
])
def test_doc_question_of_mixed(q, want):
    assert A.doc_question_v3(q) == want


def test_screen_alarm_is_the_subject(v3):
    a = A.answer("이거 뒤에 994, 992가 줄줄이 뜨면 뭘 의심해야 돼?", "SUP", {"screen": "SCR-09", "alarm_key": "108"})
    assert a["status"] == "답변" and "충돌" in a["conclusion"], a["conclusion"]


def test_mixed_question_gets_doc_part_without_llm(v3):
    a = A.answer("이호기 MTTR 얼마나 나왔어? 그거 몇 분 넘으면 주의로 봐?", "SUP")
    assert a["current_data"] and any(e["cite"].startswith("설비 데이터·지표 정의서 DOC-07") for e in a["evidence"]), a["evidence"]


# ---------------------------------------------------------------- 질문 나누기 (SPLIT_Q, LLM)
def _out(**kw):
    o = {"kind": "mixed", "intents": ["kpi"], "equipment": ["VF2-01"], "period": "none", "shift": "none", "search_queries": [],
         "doc_question": ""}
    o.update(kw)
    return o


def test_validate_route_v3():
    q = "일호기 9월 OEE 몇 나왔어? 몇 % 밑으로 가면 주의 떠?"
    got, _ = jobs.validate_route_v3(_out(doc_question="OEE 몇 % 밑이면 주의 알림이 뜨나?"), q)
    assert got["doc_question"] == "OEE 몇 % 밑이면 주의 알림이 뜨나?"
    got, _ = jobs.validate_route_v3(_out(doc_question="OEE 59% 밑이면?"), q)
    assert got["doc_question"] == ""                                   # 질문에 없는 숫자
    got, _ = jobs.validate_route_v3(_out(kind="ops", doc_question="OEE 기준"), q)
    assert got["doc_question"] == ""                                   # 섞인 질문이 아니면 쓰지 않음
    assert jobs.validate_route_v3({k: v for k, v in _out().items() if k != "doc_question"}, q)[1] == "형식 오류"


def test_split_q_uses_doc_question(llm, v3, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("SPLIT_Q", "1")
    monkeypatch.setenv("DOC_GATE", "tiered")
    seen = []

    def select(body):
        seen.append(body["messages"][-1]["content"])
        return {"answerable": False, "line_ids": [], "lead": ""}
    fake = llm(FakeLlm(route=_out(doc_question="OEE는 어떻게 구해?"), select=select,
                       verify={"answers": False, "missing": ""}, phrase={"conclusion": "x"}))
    A.answer("일호기 OEE 얼마고 OEE는 어떻게 구해", "SUP")     # 한 문장이라 규칙이 못 나눔 → LLM이 나눈 글
    assert fake.names()[0] == "route" and seen and seen[0].startswith("질문: OEE는 어떻게 구해?"), seen


def test_rule_split_wins_over_llm_doc_question(llm, v3, monkeypatch):  # noqa: F811
    """두 문장 질문은 규칙이 고른 문장(질문 글 그대로)을 쓴다. LLM이 운영 쪽 말까지 품어 나눈 글은 쓰지 않는다 (E054)."""
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("SPLIT_Q", "1")
    monkeypatch.setenv("DOC_GATE", "tiered")
    seen = []

    def select(body):
        seen.append(body["messages"][-1]["content"])
        return {"answerable": False, "line_ids": [], "lead": ""}
    llm(FakeLlm(route=_out(intents=["kpi"], equipment=["VF2-02"], doc_question="MTTR는 얼마나 나왔고 몇 분 넘으면 주의로 봐?"),
                select=select, verify={"answers": False, "missing": ""}, phrase={"conclusion": "x"}))
    A.answer("이호기 MTTR 얼마나 나왔어? 그거 몇 분 넘으면 주의로 봐?", "SUP")
    assert seen and all(x.startswith("질문: MTTR 몇 분 넘으면 주의로 봐?") for x in seen), seen


def test_weak_rule_hint_is_not_given(llm, v3, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("SPLIT_Q", "1")
    seen = []

    def route(body):
        seen.append(body["messages"][-1]["content"])
        return _out(kind="doc", intents=[], equipment=[])
    llm(FakeLlm(route=route, select={"answerable": False, "line_ids": [], "lead": ""}, verify={"answers": False, "missing": ""}))
    A.answer("작업지시 바뀌면 준비하는 데 얼마나 걸려?", "SUP")   # 의도 낱말(작업지시)만 있고 설비·날짜가 없음 → 힌트 없음
    A.answer("어제 1호기 몇 번 멈췄어?", "SUP")                  # 반대 사례: 근거 있는 규칙은 힌트로 준다
    assert "kind=모름" in seen[0] and "kind=ops" in seen[1], seen


def test_tier2_keeps_question_top_hit(llm, v3, monkeypatch):  # noqa: F811
    """LLM 검색어가 원래 질문의 1등 조각을 후보 3개 밖으로 밀어내면 그 조각을 4번째 후보로 붙인다 (F02)."""
    monkeypatch.setenv("SPLIT_Q", "1")
    monkeypatch.setenv("DOC_GATE", "tiered")
    short = sorted((c for c in load_corpus() if A.plain_lines(c)), key=lambda c: sum(map(len, A.plain_lines(c))))
    own, b, c, d = short[:4]

    def fake_search(q, k):
        return [(1.0, own)] if q == "원래 질문" else [(1.0, b), (0.9, c), (0.8, d)]
    monkeypatch.setattr(A, "search", fake_search)
    seen = []

    def select(body):
        seen.append(body["messages"][-1]["content"])
        return {"answerable": False, "line_ids": [], "lead": ""}
    llm(FakeLlm(select=select))
    assert A._tier2("원래 질문", R.Route("doc", [], [], None, None, None, ["검색어 1", "검색어 2"], "로컬 LLM"), []) is None
    assert all(A._head(x) in seen[0] for x in (b, c, d, own)), seen[0]      # 합친 순위 3개는 그대로 + 원래 질문 1등을 4번째로
    monkeypatch.setenv("SPLIT_Q", "0")                       # 반대 사례: 스위치를 끄면 예전처럼 합친 순위 3개만
    A._tier2("원래 질문", R.Route("doc", [], [], None, None, None, ["검색어 1", "검색어 2"], "로컬 LLM"), [])
    assert A._head(own) not in seen[1] and A._head(d) in seen[1]


def test_alarm_question_with_doc_cue_gets_tier2(llm, v3, monkeypatch):  # noqa: F811
    """알람 카드에 설명 요청이 붙은 질문은 낱말 문지기에서 막혀도 2차 문지기로 문서를 다시 본다. 알람 카드는 그대로 (E030)."""
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("SPLIT_Q", "1")
    monkeypatch.setenv("DOC_GATE", "tiered")
    fake = llm(FakeLlm(select={"answerable": False, "line_ids": [], "lead": ""}, verify={"answers": False, "missing": ""}))
    a = A.answer("2075 보충하러 갈 때도 자물쇠 걸어야 돼? 어디어디 잠가?", "SUP")
    assert "select" in fake.names() and "route" not in fake.names(), fake.names()   # 알람 질문은 LLM 분류에 보내지 않는다
    assert a["status"] == "답변" and "2075" in a["conclusion"]
    monkeypatch.setenv("PARSE_V3", "0")                       # 반대 사례: 스위치를 끄면 예전처럼 알람 카드만
    fake = llm(FakeLlm(select={"answerable": False, "line_ids": [], "lead": ""}, verify={"answers": False, "missing": ""}))
    A.answer("2075 보충하러 갈 때도 자물쇠 걸어야 돼? 어디어디 잠가?", "SUP")
    assert "select" not in fake.names(), fake.names()


def test_llm_action_kind_refused_without_question_word(llm, v3, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    llm(FakeLlm(route=_out(kind="action", intents=[], equipment=[])))
    a = A.answer("내일 아침 1호기 워밍업 걸어놔", "SUP")
    assert a["status"] == "안내" and not a["current_data"]
    llm(FakeLlm(route=_out(kind="action", intents=[], equipment=[]), select={"answerable": False, "line_ids": [], "lead": ""}))
    assert A.answer("보류 로트는 누가 해제해?", "SUP")["status"] != "안내"   # 의문사가 있으면 질문으로 본다
