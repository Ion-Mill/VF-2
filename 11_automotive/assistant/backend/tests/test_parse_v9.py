"""8차 시험 (PARSE_V9·FLOW_V9·BLOCKS_V2, 2026-10-12 — research_notes/로컬 LLM 연결/앞단개선8_계획_20261012.md 1절).
규칙 보강 8차("얘기해"·"몇 건씩"·"리스트 줘" 좁은 예외·모양 이어 묻기·용어집 풀이), 흐름 바꾸기(알람 + 문서 함께·카드 영문명·섞인 질문의
문서 쪽 따로 답하기·줄 고르기 대상 한정과 같은 표 형제 줄 거르기), 줄 목록 칸 2판(표시만). 잡아야 할 꼴과 반대 사례를 함께 둔다.
실제 LLM 서버 없이(가짜 LLM)."""
import re
from collections import Counter

import pytest

from backend.llm import prompts
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import blocks_v2 as BL2
from backend.services import followup_v2 as FU2
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (가짜 LLM 고정물)
from backend.tests.test_parse_v5 import _seen_items

ON8 = ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP", "PARSE_V8", "FOLLOWUP_V2")


@pytest.fixture
def v8(monkeypatch):
    for k in ON8:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("NUM_MATCH", "value")   # 앱 값 (root-cause-guards 8절: 앱 값에 기대는 동작은 시험 안에서 명시)
    AS.clear()
    yield
    AS.clear()


@pytest.fixture
def v9(v8, monkeypatch):
    monkeypatch.setenv("PARSE_V9", "1")


@pytest.fixture
def flow(v8, monkeypatch):
    monkeypatch.setenv("FLOW_V9", "1")


@pytest.fixture
def bl(v8, monkeypatch):
    monkeypatch.setenv("BLOCKS_V2", "1")


@pytest.fixture
def all9(v8, monkeypatch):
    for k in ("PARSE_V9", "FLOW_V9", "BLOCKS_V2"):
        monkeypatch.setenv(k, "1")


def ask(q, prev=None, ctx=None):
    return A.answer(q, "SUP", ctx, prev=prev)


def record(q, ctx=None):
    return ask(q, ctx=ctx).pop("_followup")


def _chunk(doc, sec):
    return next(c for c in load_corpus() if c.doc_id == doc and c.section == sec)


CTX_2073 = {"screen": "SCR-09", "alarm_key": "2073"}


# ---------------------------------------------------------------- PARSE_V9: "얘기해" (E7-077)
def test_old_followup_words_all_in_v9_list():
    """6차 옛 목록(FU_STOP)의 낱말이 새 감지 목록에 모두 있어야 한다 (7차 새 목록이 "얘기해"를 빠뜨렸다 — root-cause-guards 8절)."""
    assert A.FU_STOP - A.FU_FILL_V8 == {"얘기해"}            # 7차 결함 기록
    assert A.FU_STOP <= A.FU_FILL_V9


def test_yaegihae_followup_detected():
    q = "아까 말한 거 더 간단하게 얘기해 줄 수 있어?"            # E7-077
    assert A.followup_kind_v9(q, "공기 최소 압력 80 psi") == "simple"
    assert A.followup_kind_v8(q, "공기 최소 압력 80 psi") is None   # 7차 결함 그대로 (스위치 끔)


def test_yaegihae_followup_answer_is_not_refused(v9):
    prev = record("VF-2에 들어가는 공장 공기 최소 압력이 몇 psi예요?")
    a = ask("아까 말한 거 더 간단하게 얘기해 줄 수 있어?", prev=prev)
    assert a["status"] == "답변" and a.get("followup", {}).get("kind") == "simple", (a["status"], a["conclusion"])
    assert ask("아까 말한 거 더 간단하게 얘기해 줄 수 있어?")["status"] == "확인 필요"   # 앞 답 없으면 되묻기


def test_yaegihae_was_refused_before_v9(v8):
    prev = record("VF-2에 들어가는 공장 공기 최소 압력이 몇 psi예요?")
    assert ask("아까 말한 거 더 간단하게 얘기해 줄 수 있어?", prev=prev)["status"] == "안내"


@pytest.mark.parametrize("q", ["552 알람 얘기해 줄 수 있어?", "웨이 커버 그리스 얘기 좀 해 줘", "공기 압력 기준 얘기해 줘"])
def test_yaegihae_info_request_not_refused(v9, q):
    assert A.human_only(q) is None, q


@pytest.mark.parametrize("q", ["552 차단기 리셋해 줘", "VF2-01 속도 올려 줘", "LOT-2609-001-1 보류 풀어 줘"])
def test_control_requests_still_refused_v9(v9, q):
    assert A.human_only(q) is not None, q


# ---------------------------------------------------------------- PARSE_V9: 모양 이어 묻기 (2026-10-12 사용자 화면)
PREV_TEXT = "웨이 커버 그리스 이름이 뭐야? 그리스 · Mobil Grease XHP 222 (NLGI 2)"


@pytest.mark.parametrize("q,kind", [("방금내용 줄바꿈해서 가독성있게 요약해", "short"), ("방금 거 줄바꿈해서 보여 줘", "layout"),
                                    ("위 내용 번호 매겨서 보기 좋게 다시 보여 줘", "layout"), ("방금 답 한 줄씩 나눠서 보여 줄래?", "layout"),
                                    ("방금 거 쉽게 설명해 줘", "simple")])
def test_layout_followup_kinds(q, kind):
    assert A.followup_kind_v9(q, PREV_TEXT) == kind, q


@pytest.mark.parametrize("q", ["재고 부족 목록 줘", "속도 줄여 줘", "작업지시 번호 목록 보여 줘", "그거 다시 켜도 돼?"])
def test_layout_counter_examples(q):
    assert A.followup_kind_v9(q, PREV_TEXT) is None, q


def test_layout_was_new_question_before_v9():
    assert A.followup_kind_v8("방금내용 줄바꿈해서 가독성있게 요약해", PREV_TEXT) is None   # "줄바꿈해서·가독성있게"를 주제 낱말로 봄


def test_layout_reshows_previous_answer(all9):
    prev = record("웨이 커버 그리스 이름이 뭐야?")
    a = ask("방금 거 줄바꿈해서 보여 줘", prev=prev)
    assert a["status"] == "답변" and a["followup"]["kind"] == "layout" and not a["followup"]["rewritten"]
    assert a["conclusion"] == A.FU_LAYOUT_LEAD_V9 + " " + prev["conclusion"]
    assert not re.search(r"\d", A.FU_LAYOUT_LEAD_V9)                        # 안내 글에 숫자를 넣지 않는다 (S9)
    assert not any(t.get("used") for t in a.get("llm_trace") or [])
    if len(prev["blocks"]) > 1:
        assert a["blocks"][1:] == prev["blocks"]


def test_layout_without_prev_asks_back(v9):
    assert ask("방금 거 줄바꿈해서 보여 줘")["status"] == "확인 필요"


def test_record_keeps_blocks_only_with_v9(v8, monkeypatch):
    assert "blocks" not in record("웨이 커버 그리스 이름이 뭐야?")
    monkeypatch.setenv("PARSE_V9", "1")
    assert "blocks" in record("웨이 커버 그리스 이름이 뭐야?")


# ---------------------------------------------------------------- PARSE_V9: "몇 건씩" (E7-071)
E7_071 = "공구 부하 초과 174 알람이 지난달 장비마다 몇 건씩 찍혔는지 궁금합니다"


def test_count_with_ssik_is_alarm_count(v9):
    assert "alarm_count" in A.parse(E7_071)["intents"]
    a = ask(E7_071)
    assert re.search(r"VF2-0[12] \d+번", a["conclusion"]), a["conclusion"]


def test_count_with_ssik_missed_before_v9(v8):
    assert "alarm_count" not in A.parse(E7_071)["intents"]


@pytest.mark.parametrize("q", ["하루에 몇 건씩 처리해야 해?", "작업지시는 몇 건씩 묶어서 내?"])
def test_ssik_counter_examples(v9, q):
    assert "alarm_count" not in A.parse(q)["intents"], q


# ---------------------------------------------------------------- PARSE_V9: "리스트 줘" 좁은 예외 (E6-043)
E6_043 = "현재 재고가 기준치보다 모자란 품목 리스트 줘"


def test_list_request_not_refused(v9):
    assert A.human_only(E6_043) is None
    a = ask("재고 부족 품목 리스트 줘")
    assert a["status"] == "답변" and any(d["tool"] for d in a["current_data"]), a["conclusion"]


def test_list_request_refused_before_v9(v8):
    assert A.human_only(E6_043) is not None


@pytest.mark.parametrize("q", ["보류 로트 명단 지워 줘", "승인 대기 목록 확정해 줘", "작업지시 목록 삭제해 줘", "리셋할 설비 리스트 줘",
                               "처리 안 된 알림 목록 처리해 줘", "야간조 근무자 명단 정해 줘", "보류 로트 리스트 해제해 줘"])
def test_list_with_state_words_still_refused(v9, q):
    assert A.human_only(q) is not None, q


def test_seen_guard_and_action_items_still_refused_v9(v8, monkeypatch):
    """보이는 세트 + qa_route의 모든 조작 요청·action 문항: V9를 켜도 거절이 줄지 않는다 (거절을 푸는 예외는 좁게)."""
    qs = [it["q"] for it in _seen_items() if it.get("type") == "guard" or it.get("kind") == "action"]
    assert len(qs) >= 40
    before = {q for q in qs if A.human_only(q)}
    monkeypatch.setenv("PARSE_V9", "1")
    after = {q for q in qs if A.human_only(q)}
    assert before <= after, before - after


def test_seen_guard_items_refused_full_answer_all_switches(all9):
    guards = [it for it in _seen_items() if it.get("type") == "guard"]
    assert len(guards) >= 40
    bad = [it["q"] for it in guards if (lambda a: a["status"] != "안내" or a.get("current_data"))(ask(it["q"]))]
    assert not bad, bad[:5]


def test_seen_new_unrefusals_are_list_or_yaegihae_only(v8, monkeypatch):
    """V9가 거절을 푼 보이는 문항은 "리스트 줘"·"얘기해" 꼴뿐이어야 한다 (다른 꼴을 말없이 풀지 않게)."""
    qs = [it["q"] for it in _seen_items()]
    before = {q for q in qs if A.human_only(q)}
    monkeypatch.setenv("PARSE_V9", "1")
    freed = before - {q for q in qs if A.human_only(q)}
    assert all(A.list_request_v9(q) or A.INFO_REQ_V9.search(q) for q in freed), freed


# ---------------------------------------------------------------- PARSE_V9: 용어집 풀이 정리
def _row(std_part):
    return next(r for r in FU2.glossary_rows() if std_part in r["std"])


def test_glossary_bundled_row_shows_only_its_english():
    # 2026-10-14 용어집 Rev.4가 묶인 줄 "가동률 / 성능 / 양품률"을 낱말마다 나눠 실제 줄이 없어졌다(시험 가정이 바뀜 — 코드 결함 아님).
    # 원래 시험: r = _row("가동률 / 성능 / 양품률"). 묶인 줄 분기는 남겼으므로 같은 모양의 줄을 만들어 본다.
    r = {"eng": "Availability / Performance / Quality rate", "std": "가동률 / 성능 / 양품률",
         "avoid": "", "terms": ["가동률", "성능", "양품률"]}
    assert FU2.term_note({**r, "hit": "가동률"}, v9=True) == "가동률 = 영어 Availability"
    assert FU2.term_note({**r, "hit": "성능"}, v9=True) == "성능 = 영어 Performance"
    assert "Performance" in FU2.term_note({**r, "hit": "가동률"})          # 스위치 끄면 지금처럼 통째


def test_glossary_rev4_split_rows():
    """용어집 Rev.4 (2026-10-14): 나뉜 줄은 그 낱말 하나만 — 스위치와 관계없이 같은 풀이."""
    for std, eng in (("가동률", "Availability"), ("성능", "Performance"), ("일일 보고서", "Daily Report")):
        r = next(x for x in FU2.glossary_rows() if x["std"] == std)
        assert r["eng"] == eng
        assert FU2.term_note({**r, "hit": std}, v9=True) == FU2.term_note({**r, "hit": std})
    assert not any(r["std"] in ("가동률 / 성능 / 양품률", "평균 수리 시간(MTTR) / 평균 고장 간격(MTBF)") for r in FU2.glossary_rows())


def test_glossary_single_row_unchanged():
    r = _row("그리스")
    assert FU2.term_note({**r, "hit": "그리스"}, v9=True) == FU2.term_note({**r, "hit": "그리스"}) == "그리스 = 영어 Grease, 다른 말 구리스"


def test_glossary_bracket_or_uneven_rows_kept_whole():
    rows = [r for r in FU2.glossary_rows() if " / " in r["std"] and (re.search(r"[()]", r["eng"] + r["std"])
                                                                    or len(r["std"].split(" / ")) != len(r["eng"].split(" / ")))]
    assert rows
    for r in rows:
        hit = r["terms"][0]
        assert FU2.term_note({**r, "hit": hit}, v9=True) == FU2.term_note({**r, "hit": hit}), r["std"]


# ---------------------------------------------------------------- FLOW_V9: 알람 카드 영문명 (E7-094·E6-008)
def test_alarm_name_has_english():
    m = A.alarm_codes()
    assert A.alarm_name_v9(m["991"]) == "온도가 초과한 증폭기(AMPLIFIER OVER TEMPERATURE)"
    assert A.alarm_name_v9(m["992"]) == m["992"]["name_ko"]                  # 이미 영문이 들어 있음 — 다시 붙이지 않음
    assert A.alarm_name_v9(m["230"]) == m["230"]["name_ko"]
    assert A.alarm_name_v9(m["302"]) == m["302"]["name_ko"]                  # 조작 안내 알람은 영문 칸이 비어 있음


def test_alarm_card_english_name_in_answer(flow):
    assert "AMPLIFIER OVER TEMPERATURE" in ask("알람 991 영문 이름이 뭐였지?")["conclusion"]
    assert "AMPLIFIER OVERLOAD" in ask("994 알람 영문명 뭐임?")["conclusion"]
    assert ask("992 뜨면 뭐부터 봐?")["conclusion"].count("AMPLIFIER OVER CURRENT") == 1


def test_alarm_card_without_english_before_flow(v8):
    assert "AMPLIFIER OVER TEMPERATURE" not in ask("알람 991 영문 이름이 뭐였지?")["conclusion"]


# ---------------------------------------------------------------- FLOW_V9: 알람 + 문서 함께
def _card(code):
    c, steps, _ = A.alarm_doc_answer({"code": code, "axis": "", "sub": ""}, en=True)
    return c + " " + " ".join(steps)


@pytest.mark.parametrize("q", ["552 뜨면 뭐부터 봐?", "992 왜 떠?", "알람 991 영문 이름이 뭐였지?", "2075 알람 뜻이 뭐야?",
                               "174 알람 지난달에 몇 번 났어?", "2075 알람 몇 번 났고 왜 나는 거야?", "이 알람 누가 조치해? 작업자가 해도 돼?",
                               "992 뜨기 바로 전에 994가 먼저 떠 있었으면 뭘 의심해야 돼?"])   # 카드 쉬운 설명에 "바로 앞 … 의심"이 있음
def test_alarm_plain_questions_card_only(flow, q):
    al = [{"code": "2075"}] if "이 알람" in q else A.parse(q)["alarms"][:1]
    assert A.alarm_doc_plan_v9(q, al, _card(al[0]["code"])) is None, (q, A.alarm_topic_left_v9(q, al, _card(al[0]["code"])))


@pytest.mark.parametrize("q,want", [
    ("축윤활유 저장소 비워짐 알람 9월에 몇 번 났어? 저장소 보충은 원래 얼마마다 하게 돼 있어?", "저장소 보충은 원래"),   # E7-050
    ("이번 달 2075 몇 번 떴지? 축 윤활유 채우는 건 원래 얼마마다 하게 돼 있어?", "채우는 건 원래"),                   # E6-051
    ("2075 보충하려면 자물쇠 어디어디 채워야 돼?", "2075 보충하려면 자물쇠")])                                      # 한 마디, 주제 "자물쇠"
def test_alarm_doc_plan_picks_doc_clause(flow, q, want):
    al = A.parse(q)["alarms"][:1]
    dq = A.alarm_doc_plan_v9(q, al, _card(al[0]["code"]))
    assert dq and want in dq and "몇 번 났어" not in dq and "몇 번 떴지" not in dq, dq


def test_alarm_doc_plan_adds_name_for_screen_alarm():
    dq = A.alarm_doc_plan_v9("이 알람은 프로그램 돌아가는 중에도 떠요?", [{"code": "2073"}], _card("2073"))
    assert dq and dq.startswith("축 윤활 압력이 감지 불능"), dq
    dq = A.alarm_doc_plan_v9("축윤활유 저장소 비워짐 알람 9월에 몇 번 났어? 저장소 보충은 원래 얼마마다 하게 돼 있어?", [{"code": "2075"}],
                             _card("2075"))
    assert dq == "저장소 보충은 원래 얼마마다 하게 돼 있어?", dq                  # 나눈 마디에는 이름을 붙이지 않는다 (E2-062·E4-030)


@pytest.mark.parametrize("q", ["이 알람 지난달 몇 번 났어? 몇 번 나야 반복 알람으로 잡혀?",                         # E2-062
                               "축 윤활유 저장소 비워짐 알람 한 달 새 몇 번 났어요? 그리고 몇 번 나면 반복 알람으로 잡혀요?"])   # E4-030
def test_rule_doc_clause_kept_for_alarm_questions(flow, q):
    """규칙이 고른 문서 쪽 마디(운영 낱말을 붙임)가 있으면 그것으로 찾는다 — 반복 알람 기준(DOC-03 §1.4)을 놓치지 않게."""
    a = ask(q, ctx={"screen": "SCR-09", "alarm_key": "2075"})
    assert any(e["doc_id"] in ("DOC-03", "DOC-07") and e["section"] in ("1.4", "10.4") for e in a["evidence"]), \
        [e["cite"] for e in a["evidence"]]


def test_card_lines_are_not_doc_candidates():
    own = A.alarm_own_sections_v9([{"code": "2073"}])
    d3, d2 = _chunk("DOC-03", "2.10"), _chunk("DOC-02", "4.10")
    l3, l2 = A.plain_lines(d3), A.plain_lines(d2)
    assert [t for t in l3 if A.card_line_v9(d3, t, own)] == [t for t in l3 if A.STEP_ROW_V9.match(t)] and len(l3) > 7
    assert any(t.startswith("증상·알람") and not A.card_line_v9(d3, t, own) for t in l3)    # 카드에 없는 줄은 남긴다 (E6-032)
    assert any(t.startswith("쉬운 설명") and A.card_line_v9(d2, t, own) for t in l2)
    assert any(t.startswith("원문 설명") and not A.card_line_v9(d2, t, own) for t in l2)
    other = _chunk("DOC-03", "2.11")                                           # 다른 알람의 점검 순서는 이 판단 밖
    assert not any(A.card_line_v9(other, t, own) for t in A.plain_lines(other))


def test_screen_alarm_question_gets_symptom_line(flow):
    a = ask("이 알람은 프로그램 돌아가는 중에도 떠요?", ctx=CTX_2073)           # E6-032
    assert "뜨지 않" in a["conclusion"], a["conclusion"]
    assert len(a["steps"]) == len(A.doc03_steps("DOC-03 §2.10", "2073"))      # 카드 점검 순서는 자르지 않는다
    assert "★1 — 누가" not in a["conclusion"]                                  # 카드가 보인 점검 순서 행을 문서 줄로 다시 보이지 않는다


def test_screen_alarm_question_without_flow(v8):
    assert "뜨지 않" not in ask("이 알람은 프로그램 돌아가는 중에도 떠요?", ctx=CTX_2073)["conclusion"]


def test_alarm_doc_lines_sent_to_llm_have_no_step_rows(flow, llm):  # noqa: F811
    seen = []

    def select(body):
        seen.append(body["messages"][-1]["content"])
        return {"answerable": False, "line_ids": [], "lead": ""}
    llm(FakeLlm(select=select, verify={"answers": False, "missing": ""}, phrase={"conclusion": "x"}))
    a = ask("이 알람은 프로그램 돌아가는 중에도 떠요?", ctx=CTX_2073)
    assert seen, a["llm_trace"]
    assert not any(re.search(r"L\d+: ★?\d+ — 누가: ", s) and "§2.10" in s for s in seen), seen[0][:400]
    assert "질문: 축 윤활 압력이 감지 불능" in seen[0]                       # 알람 이름을 붙인 검색 글로 고른다


# ---------------------------------------------------------------- FLOW_V9: 섞인 질문의 문서 쪽 따로 답하기 (⑤)
def _route_out(**kw):
    o = {"kind": "mixed", "intents": ["production"], "equipment": [], "period": "none", "shift": "none", "search_queries": [],
         "doc_question": ""}
    o.update(kw)
    return o


def test_mixed_doc_side_is_routed_on_its_own(flow, llm, monkeypatch):  # noqa: F811
    for k, v in (("ROUTE_POLICY", "llm_guarded"), ("SPLIT_Q", "1"), ("DOC_GATE", "tiered")):
        monkeypatch.setenv(k, v)
    routed, selected = [], []

    def route(body):
        q = body["messages"][-1]["content"]
        routed.append(q)
        if "몇 개 뽑았어" in q:
            return _route_out()
        return _route_out(kind="doc", intents=[], search_queries=["교대 목표 수량"])

    def select(body):
        selected.append(body["messages"][-1]["content"])
        return {"answerable": False, "line_ids": [], "lead": ""}
    llm(FakeLlm(route=route, select=select, verify={"answers": False, "missing": ""}, phrase={"conclusion": "x"}))
    a = ask("9월 15일 주간조 몇 개 뽑았어? 교대 목표가 몇 개였더라?")     # E7-079 꼴
    assert len(routed) == 2 and "질문: 교대 목표가 몇 개였더라?" in routed[1], routed
    assert selected and all(s.startswith("질문: 교대 목표가 몇 개였더라?") for s in selected), selected
    assert a["conclusion"].endswith(A.MIXED_DOC_MISS_V9) and "실적" in a["conclusion"], a["conclusion"]
    assert not re.search(r"\d", A.MIXED_DOC_MISS_V9)


def test_mixed_doc_side_refused_clause_is_dropped(flow):
    assert A.doc_side_route_v9("LOT-2609-001-1 보류 풀어 줘", A.settings(), []) is None


def test_single_clause_mixed_unchanged(flow, v8):
    """나눌 수 없는 섞인 질문은 지금 동작 그대로 (꼬리 안내 없음)."""
    a = ask("어제 야간 VF2-01 몇 번 멈췄어? 왜?")
    assert A.MIXED_DOC_MISS_V9 not in a["conclusion"]


# ---------------------------------------------------------------- FLOW_V9: 줄 고르기 대상 한정 + 같은 표 형제 줄 (ⓔ)
def _grease_sel(lead=""):
    d23, d45 = _chunk("DOC-04", "2.3"), _chunk("DOC-04", "4.5")
    rows = [t for t in A.plain_lines(d23) if t.startswith(("외함", "공구 교환장치 — 항목: 가이드", "공구 교환장치 — 항목: 공구 빼기"))]
    grease = next(t for t in A.plain_lines(d45) if t.startswith("그리스 · Mobil"))
    lines = rows + [grease]
    return {"lead": lead, "lines": lines, "chunks": [d23, d45], "line_chunks": [d23] * len(rows) + [d45]}


def test_sibling_rows_in_same_table_are_dropped():
    sel = _grease_sel()
    assert len(sel["lines"]) == 4
    out = A.sibling_filter_v9("웨이 커버 그리스 이름이 뭐야?", sel)
    assert [t[:2] for t in out["lines"]] == ["외함", "그리"], out["lines"]     # 같은 표의 공구 교환장치 줄 2개만 빠짐
    assert any("Mobil Grease XHP 222" in t for t in out["lines"])             # 다른 표의 정답 줄은 남는다
    assert out["dropped"] == 2 and [c.section for c in out["line_chunks"]] == ["2.3", "4.5"]


def test_sibling_filter_clears_lead():
    """줄을 뺐으면 앞머리를 비운다 — 앞머리는 처음 고른 줄 전체의 요약이라 뺀 줄 내용을 말할 수 있다 (빠른 확인에서 찾음:
    "… 공구 교환장치의 가이드 레일과 공구 빼기 핑거에도 같은 그리스를 사용한다"). 처음 시험은 "숫자가 뒷받침되면 둔다"였다 (2026-10-13 고침)."""
    out = A.sibling_filter_v9("웨이 커버 그리스 이름이 뭐야?", _grease_sel(lead="웨이 커버와 공구 교환장치 가이드 레일에 같은 그리스를 바른다"))
    assert out["lead"] == "" and out["dropped"] == 2
    sel = _grease_sel(lead="앞머리")
    assert A.sibling_filter_v9("그거 이름이 뭐야?", sel)["lead"] == "앞머리"   # 줄을 빼지 않으면 그대로


def test_sibling_filter_counter_examples():
    sel = _grease_sel()
    both = A.sibling_filter_v9("웨이 커버랑 공구 교환장치 가이드 레일 그리스 뭐 써?", sel)
    assert len(both["lines"]) >= 3                                            # 둘 다 물으면 둘 다 남긴다
    assert A.sibling_filter_v9("그거 이름이 뭐야?", sel) is sel                # 대상 낱말이 없으면 그대로
    d5 = _chunk("DOC-05", "2.1")
    rows = A.plain_lines(d5)[:3]
    s5 = {"lead": "", "lines": rows, "chunks": [d5], "line_chunks": [d5] * len(rows)}
    assert A.sibling_filter_v9("운전정지 준비는 뭘 해?", s5) is s5            # 안전 작업 문서는 거르지 않는다


def test_select_prompt_unchanged():
    """대상 한정 지시 한 줄은 S6에서 답 줄 거부를 늘려 뺐다 (E4-050·E7-058·E024·H12, 2026-10-13 — 처음 시험은 "스위치를 켜면 줄이 들어간다"였다).
    고르기 지시문은 7차 그대로다."""
    blocks = [("[문서 DOC-04 §2.3 매월]", [("L1", "외함 — 항목: 웨이 커버 점검·윤활")])]
    assert not hasattr(prompts, "SELECT_TARGET_V9")
    assert "대상" not in prompts.select("q", blocks)[0]["content"]


def _rows_of(doc, sec, starts):
    c = _chunk(doc, sec)
    rows = [t for t in A.plain_lines(c) if t.startswith(starts)]
    return {"lead": "", "lines": rows, "chunks": [c], "line_chunks": [c] * len(rows)}


def test_sibling_filter_only_for_name_questions():
    """S6 반대 사례 (2026-10-13): 규칙 줄(H08 병목 판단)·답 줄(C02 "시간 — 10~20분")을 지우지 않는다."""
    sel = _grease_sel()
    assert A.sibling_filter_v9("웨이 커버에 뭐 발라?", sel)["dropped"] == 2          # "뭐 발라"도 이름을 묻는 꼴
    assert A.sibling_filter_v9("웨이 커버 그리스는 얼마마다 발라?", sel) is sel       # 주기 질문 — 이름 질문이 아니다
    h08 = {**sel, "lines": ["① — 규칙: 최근 30분 동안 그 공정의 바로 앞 재공이 늘었고", "② — 규칙: 앞 공정이 BLOCKED이면 그 공정을 병목으로 본다"]}
    assert A.sibling_filter_v9("병목은 어떻게 판단해?", h08) is h08


def test_sibling_filter_needs_target_in_row_id():
    """가르는 낱말이 남길 줄의 머리·첫 칸(부위·항목)에 없으면 거르지 않는다 (값 칸에만 든 낱말로 형제 줄을 가르지 않게)."""
    sel = _grease_sel()
    assert A._row_id_v9(sel["lines"][0]).startswith("외함 웨이 커버 점검")
    s2 = A.sibling_filter_v9("가이드 레일 그리스 이름이 뭐야?", sel)
    assert s2.get("dropped") == 2 and all("가이드 레일" in t or "Mobil" in t for t in s2["lines"]), s2["lines"]


# ---------------------------------------------------------------- BLOCKS_V2: 줄 목록 칸 2판 (표시만)
def _nums(text):
    return Counter(re.findall(r"\d+(?:\.\d+)?", text))


def test_ops_answer_becomes_item_list(bl):
    a = ask("어제 야간 VF2-01 몇 번 멈췄어?")
    ops = [b for b in a["blocks"] if b["kind"] == "ops"]
    assert ops and "정지 전체" in ops[0]["head"] and len(ops[0]["items"]) >= 4, a["blocks"]
    assert ops[0]["source"]["tool"]
    shown = " ".join([ops[0]["head"]] + ops[0]["items"])
    assert _nums(shown) == _nums(a["conclusion"])                             # 숫자는 conclusion과 같다


def test_doc_lines_carry_cells_and_source(bl):
    a = ask("웨이 커버 그리스 이름이 뭐야?")
    lines = [b for b in a["blocks"] if b["kind"] == "line"]
    assert lines and all(b.get("cite", {}).get("doc_id") for b in lines), a["blocks"]
    assert all(b["cite"]["section"] and "§" in b["cite"]["cite"] for b in lines)
    rows = [b for b in lines if b.get("cells")]
    assert all(b["text"] == b["head"] + " — " + " · ".join(f"{c['name']}: {c['value']}" for c in b["cells"]) for b in rows)


def test_blocks_v2_does_not_change_conclusion(v8, monkeypatch):
    qs = [it["q"] for it in _seen_items() if it.get("type") in ("doc", "ops", "mixed")][:80]
    before = [A.answer(q, "SUP")["conclusion"] for q in qs]
    monkeypatch.setenv("BLOCKS_V2", "1")
    after = [A.answer(q, "SUP")["conclusion"] for q in qs]
    assert before == after


def test_ops_blocks_fall_back_when_numbers_differ():
    e = [{"head": "공구 수명", "items": ["VF2-01 T05 M6 탭 92%"], "text": "", "source": None}]
    assert BL2.ops_blocks(e, ["공구 수명: VF2-01 T05 M6 탭 93%"], "다듬은 글") == [{"kind": "text", "text": "다듬은 글"}]
    assert BL2.ops_blocks(e, ["공구 수명: VF2-01 T05 M6 탭 92%"], "다듬은 글")[0]["kind"] == "ops"


def test_build_falls_back_when_text_differs():
    assert BL2.build(["A"], None, [], [], [], [], "B") == [{"kind": "text", "text": "B"}]
    out = BL2.build(["앞머리 줄1 / 줄2"], "운영", ["운영"], [], ["줄1", "줄2"], [{"cite": "x"}, {"cite": "y"}], "앞머리 줄1 / 줄2 운영 꼬리",
                    ["꼬리"])
    assert [b["kind"] for b in out] == ["lead", "line", "line", "text", "text"] and out[1]["cite"] == {"cite": "x"}


def test_v7_blocks_keep_tail():
    out = A.answer_blocks(["문서"], "운영", [], "문서 운영 꼬리", ["꼬리"])
    assert [b["text"] for b in out] == ["문서", "운영", "꼬리"]
    assert A.answer_blocks(["문서"], "운영", [], "문서 운영", []) == [{"kind": "text", "text": "문서"}, {"kind": "text", "text": "운영"}]


def test_switches_need_v8(monkeypatch):
    for k in ("PARSE_V9", "FLOW_V9", "BLOCKS_V2"):
        monkeypatch.setenv(k, "1")
    assert not (A.v9_on() or A.flow_on() or A.blocks_on())                    # PARSE_V2~V8이 꺼지면 동작하지 않는다
    assert "AMPLIFIER OVER TEMPERATURE" not in ask("알람 991 영문 이름이 뭐였지?")["conclusion"]
