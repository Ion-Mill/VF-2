"""규칙 보강 3차 시험 (PARSE_V4·CAND_ORDER, 2026-10-10 3차 — research_notes/로컬 LLM 연결/앞단개선3_사전등록_20261010.md 3절).
봉인 시험 E2를 공개한 뒤 찾은 원인 a~g마다 고친 동작과 반대 사례(바뀌면 안 되는 것)를 함께 본다. 실제 LLM 서버 없이 본다."""
import json
import re
from datetime import date
from pathlib import Path

import pytest

from backend.llm import jobs
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.services import routing as R
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)

EVAL = Path(__file__).resolve().parents[1] / "eval"
NO = {"answerable": False, "line_ids": [], "lead": ""}


@pytest.fixture
def v3(monkeypatch):
    monkeypatch.setenv("PARSE_V2", "1")
    monkeypatch.setenv("PARSE_V3", "1")


@pytest.fixture
def v4(v3, monkeypatch):
    monkeypatch.setenv("PARSE_V4", "1")


def _sec(doc, sec):
    return [c.title + "\n" + c.text for c in load_corpus() if c.doc_id == doc and (c.section == sec or c.section.startswith(sec + "."))]


def _route(**kw):
    o = {"kind": "ops", "intents": [], "equipment": [], "period": "none", "shift": "none", "search_queries": [], "doc_question": ""}
    o.update(kw)
    return o


# ---------------------------------------------------------------- a 날짜 (기준일 2026-10-01 목요일)
@pytest.mark.parametrize("q,start,end", [
    ("지난주 금요일 2호기 몇 번 멈췄어?", date(2026, 9, 25), date(2026, 9, 25)),
    ("지난주 월요일 1호기 실적 몇 개야?", date(2026, 9, 21), date(2026, 9, 21)),
    ("저번주 일요일에 세척기 몇 번 섰어?", date(2026, 9, 27), date(2026, 9, 27)),
    ("지난주 수요일부터 금요일까지 세척기 몇 번 섰어?", date(2026, 9, 23), date(2026, 9, 25)),
    ("지지난주 2호기 몇 번 멈췄어?", date(2026, 9, 14), date(2026, 9, 20)),
    ("지지난주 금요일 2호기 몇 번 멈췄어?", date(2026, 9, 18), date(2026, 9, 18)),
    ("이번 주 화요일 1호기 몇 번 섰어?", date(2026, 9, 29), date(2026, 9, 29)),
    ("월요일에 1호기 몇 번 섰어?", date(2026, 9, 28), date(2026, 9, 28)),          # 요일만: v3와 같음 (가장 가까운 지난 월요일)
    ("목요일이랑 금요일에 1호기 몇 번 섰어?", date(2026, 9, 24), date(2026, 9, 25)),  # 요일 여럿 = 처음~끝
    ("지난주 2호기 몇 번 멈췄어?", date(2026, 9, 21), date(2026, 9, 27)),            # 반대 사례: 요일 없는 지난주는 v3 그대로
    ("어제 야간 VF2-01 몇 번 멈췄어?", date(2026, 9, 30), date(2026, 9, 30)),
])
def test_week_and_weekday(v4, q, start, end):
    p = A.parse(q)
    assert (p["start"], p["end"]) == (start, end), p
    assert p["intents"] and not p.get("future"), p


def test_week_weekday_off_by_default(v3):
    p = A.parse("지난주 금요일 2호기 몇 번 멈췄어?")       # 스위치를 끄면 예전처럼 지난주 전체
    assert (p["start"], p["end"]) == (date(2026, 9, 21), date(2026, 9, 27)) and "future" not in p


@pytest.mark.parametrize("q", ["이번 주 금요일 1호기 실적 몇 개야?", "다음 주 월요일 2호기 실적 몇 개야?", "10월 5일 1호기 실적 몇 개야?",
                               "내일 VF2-01 생산 몇 개 나와?", "이번 주 토요일 2호기 OEE 얼마야?"])
def test_future_dates_are_not_widened(v4, q):
    p = A.parse(q)
    assert p.get("future") and p["start"] is None or p["start"] > date(2026, 10, 1), p
    a = A.answer(q, "SUP")
    assert a["status"] == "확인 필요" and "기준 시각(2026-10-01 08:00) 뒤" in a["conclusion"], a["conclusion"]
    assert not a["current_data"]                                         # 한 달 전체로 넓혀 답하지 않는다


def test_future_word_keeps_forward_looking_queries(v4):
    a = A.answer("내일 예방 정비 뭐 있어?", "SUP")                       # 정비 기한은 앞을 보는 조회 → 그대로 답한다
    assert a["status"] == "답변" and a["current_data"] and "기준 시각" not in a["conclusion"], a["conclusion"]


def test_week_words_without_ops_are_not_future(v4):
    p = A.parse("이번 주 금요일 회식 어디서 해?")
    assert p["intents"] == [] and p["start"] is None and p.get("future")  # 날짜를 쓰지 않는다 (운영 조회가 아니라 확인 필요도 아님)
    assert A.answer("이번 주 금요일 회식 어디서 해?", "SUP")["status"] == "문서에 없음"


# ---------------------------------------------------------------- b 답 종류 (기간 단위)
def test_duration_any_unit_for_how_long(v4):
    q = "조작 안내 등급 알람이면 설비는 보통 얼마 동안 서 있어?"           # E2-010
    assert A.answer_type_ok(q, "조작 안내 · 설비 정지: 1~5분")
    assert A.answer_type_ok("세척기는 얼마나 오래 돌려?", "세척 시간 10분")
    assert not A.answer_type_ok(q, "조작 안내 · 작업자가 처리")             # 값이 없으면 여전히 거부


def test_duration_off_by_default(v3):
    assert not A.answer_type_ok("조작 안내 등급 알람이면 설비는 보통 얼마 동안 서 있어?", "조작 안내 · 설비 정지: 1~5분")


def test_retention_needs_day_units(v4):
    q = "로그인 기록은 얼마 동안 남겨 둬?"                                # F11
    assert A.answer_type_ok(q, "로그인 기록 · 보관: 1년")
    assert not A.answer_type_ok(q, "로그인 뒤 30분 동안 쓰지 않으면 자동 로그아웃")   # 분 단위 줄은 보관 기간이 아니다
    assert not A.answer_type_ok("검사 기록 보관 기간은 얼마야?", "검사는 5분 안에 끝낸다")
    assert A.answer_type_ok("며칠 걸려?", "3일")
    assert not A.answer_type_ok("며칠 걸려?", "30분")


# ---------------------------------------------------------------- c 대명사 경계
def test_determiner_takes_antecedent(v4):
    q = "수명 90% 넘은 공구 있어요? 그런 공구는 언제 바꾸라고 돼 있어요?"   # E2-059
    assert A.doc_question_v4(q) == "수명 90% 넘은 공구는 언제 바꾸라고 돼 있어요?"
    assert A.doc_question_v3(q).startswith("공구 런 공구는")              # 예전 버그 기록 ("그"를 잘라 "런 공구는…")


@pytest.mark.parametrize("q,start", [
    ("어제 1호기 몇 번 멈췄어? 그래서 기준은 몇 번 넘으면 주의야?", "그래서"),
    ("어제 1호기 몇 번 멈췄어? 그러면 정지 기준은 어떻게 돼?", "그러면"),
    ("26일 2호기 몇 번 섰어? 그날 같은 정지는 왜 생겨?", "그날"),
    ("2호기 OEE 얼마야? 그대로 두면 기준은 어떻게 돼?", "그대로"),
])
def test_words_starting_with_geu_are_not_cut(q, start):
    got = A.doc_question_v4(q)
    assert start in got and not got.lstrip().startswith(start[1:]), got


def test_pronoun_forms(v4):
    assert A.doc_question_v4("2호기 MTTR 얼마야? 그것은 몇 분 넘으면 주의야?") == "MTTR 몇 분 넘으면 주의야?"
    assert A.doc_question_v4("이호기 MTTR 얼마나 나왔어? 그거 몇 분 넘으면 주의로 봐?") == "MTTR 몇 분 넘으면 주의로 봐?"
    assert A.doc_question_v4("어제 야간 VF2-01 몇 번 멈췄어?") == "어제 야간 VF2-01 몇 번 멈췄어?"   # 한 문장은 그대로
    # "그 + 명사": 앞 문장의 설비·날짜 꾸밈말을 가져오지 않는다 (E2-061)
    assert A.doc_question_v4("일호기 9월 기준 MTTR 몇 분이에요? 그 MTTR은 어떻게 계산한 거예요?") == "MTTR은 어떻게 계산한 거예요?"
    assert A.doc_question_v4("재고 부족한 거 뭐 있어? 그 부족 알림은 누가 받게 돼 있어?") == "재고 부족 알림은 누가 받게 돼 있어?"   # E2-058
    # E2-056: v3는 "그리고"의 "그"를 잘라 "리고 …"가 됐다
    q = "17일 낮에 일호기 몇 번 멈췄어? 그리고 교대보고서에 들어가는 필수 정지는 기준이 뭐야?"
    assert A.doc_question_v4(q) == "그리고 교대보고서에 들어가는 필수 정지는 기준이 뭐야?"
    assert A.doc_question_v3(q).startswith("리고")


# ---------------------------------------------------------------- d 알람 횟수 꼴
def test_alarm_count_with_ssik(v4):
    q = "이거 9월에 설비별로 몇 번씩 떴는지 알려줘"                          # E2-054 (화면 알람 120)
    assert "alarm_count" in A.parse(q)["intents"]
    a = A.answer(q, "SUP", {"screen": "SCR-09", "alarm_key": "120"})
    assert a["current_data"] and re.search(r"알람 120(?:\.00)? 발생: ", a["conclusion"]), a["conclusion"]


def test_alarm_count_with_ssik_off_by_default(v3):
    assert "alarm_count" not in A.parse("이거 9월에 설비별로 몇 번씩 떴는지 알려줘")["intents"]


@pytest.mark.parametrize("q", ["알람이 몇 번씩 나면 반복 알람으로 봐?", "같은 알람 몇 번 정도 뜨면 원인 점검해?"])
def test_count_criteria_go_to_docs(v4, q):
    assert A.parse(q)["intents"] == [], A.parse(q)


# ---------------------------------------------------------------- e 업무 밖 부탁
def test_leisure_request_is_not_refused(v4):
    q = "이번 주 회식 장소로 고깃집 하나 추천해줘"                           # E2-090
    assert A.leisure_request(q) and A.human_only(q) is None
    assert A.answer(q, "SUP")["status"] == "문서에 없음"


def test_leisure_request_refused_by_default(v3):
    assert A.human_only("이번 주 회식 장소로 고깃집 하나 추천해줘")["status"] == "안내"


def test_leisure_request_with_llm_action(llm, v4, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    llm(FakeLlm(route=_route(kind="action"), select=NO))
    a = A.answer("주말에 가족이랑 갈 캠핑장 하나 골라 줘", "SUP")
    assert a["status"] == "문서에 없음", a["conclusion"]
    llm(FakeLlm(route=_route(kind="action")))
    assert A.answer("내일 아침 1호기 워밍업 걸어놔", "SUP")["status"] == "안내"   # 반대 사례: 업무 부탁은 그대로 거절


@pytest.mark.parametrize("q", ["공구 하나 추천해줘", "절삭유 회사 좀 추천해 주세요", "LOT-2609-001-1 보류 풀어 줄 사람 추천해줘", "2호기 담당자 골라 줘",
                               "이번 주 야간조 근무자 골라 줘", "내일 청소 당번 정해서 추천해줘", "점검 맡길 인원 골라 주세요"])
def test_work_requests_stay_refused(v4, q):
    assert not A.leisure_request(q) and A.human_only(q) is not None, q


@pytest.mark.parametrize("q", ["점심 메뉴 하나 추천해줘", "주말에 볼 영화 추천 좀 해 줘", "근처 카페 소개해 주세요"])
def test_leisure_examples(v4, q):
    assert A.leisure_request(q) and A.human_only(q) is None, q


def _seen_guard_and_action():
    qs = []
    for f in sorted(EVAL.glob("qa_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        items = d["items"] if isinstance(d, dict) else d
        qs += [it["q"] for it in items if it.get("type") == "guard" or it.get("kind") == "action"]
    return qs


def test_seen_guard_and_action_items_still_refused(v4, monkeypatch):
    qs = _seen_guard_and_action()
    assert len(qs) >= 30                                                   # 보이는 세트 조작 요청 + 분류 세트 action
    assert not [q for q in qs if A.leisure_request(q)]
    monkeypatch.setenv("PARSE_V4", "0")
    before = {q for q in qs if A.human_only(q)}
    monkeypatch.setenv("PARSE_V4", "1")
    after = {q for q in qs if A.human_only(q)}
    assert before <= after, before - after                                 # 거절하던 것은 모두 그대로 거절


def test_breaker_is_a_control_object(v4, monkeypatch):
    q = "CB3 차단기 원격으로 다시 올려 주세요"                              # E2-095에서 "때문에"를 뺀 꼴
    assert "조작하지 않습니다" in A.human_only(q)["conclusion"]
    assert "조작하지 않습니다" in A.human_only("552 때문에 떨어진 CB3 차단기 원격으로 다시 올려 주세요")["conclusion"]
    monkeypatch.setenv("PARSE_V4", "0")
    assert "조작하지 않습니다" not in A.human_only(q)["conclusion"]         # 예전: 일반 거절 문구로만 (차단기를 몰랐음)


# ---------------------------------------------------------------- f 알람 기준값
@pytest.mark.parametrize("q,doc,secs,found", [
    ("254 몇 도 넘으면 떠?", "254", [("DOC-02", "4.9"), ("DOC-03", "2.9")], False),
    ("120 알람 공기압 몇 psi 밑이면 떠?", "120", None, False),             # "최소 80 psi"는 공급 요건, "150 PSI 센서 불량"은 트립 아님
    ("2073 몇 psi 아래면 떠?", "2073", None, False),
    ("2075 몇 psi 밑으로 떨어지면 떠?", "2075", None, True),               # 4 PSI 아래로 떨어지는 주기
    ("991 몇 도에서 떠?", "991", None, True),                              # 195°F(90°C)에서 동작
    ("WSH-01 알람 몇 도 넘으면 정지해?", "WSH-01", None, True),             # 75 ℃에서 정지
    ("991 몇 도까지 식혀야 돼?", "991", None, False),                      # 다시 켜는 값은 트립 값과 따로
])
def test_alarm_threshold_needs_value_next_to_trip(v4, q, doc, secs, found):
    p = A.parse(q)
    c, steps, ev = A.alarm_doc_answer(p["alarms"][0])
    texts = [ch.title + "\n" + ch.text for e in ev for ch in load_corpus()
             if ch.doc_id == e["doc_id"] and (ch.section == e["section"] or ch.section.startswith(e["section"] + "."))]
    r = A.alarm_threshold_v4(q, texts)
    assert r is not None and r[0] is found, r


def test_threshold_question_forms():
    assert A.alarm_threshold_v4("991 뜨면 몇 도구 챙겨?", ["x"]) is None      # "도구"는 온도가 아니다
    assert A.alarm_threshold_v4("120 알람 공기압 몇 psi로 맞춰야 돼?", ["x"]) is None   # 공급·설정 값 질문 (조건 말 없음)
    assert A.alarm_threshold_v4("254 몇 도면 떠?", ["x"]) == (False, "온도", "")
    assert A.alarm_threshold_v4("254 모터 온도가 몇 도가 넘으면 떠?", ["x"]) == (False, "온도", "")
    assert A.alarm_threshold_v4("992 뜨면 뭐부터 봐?", ["x"]) is None
    assert A.alarm_threshold_v4("2075 몇 bar 밑이면 떠?", ["4 PSI(약 0.28 bar) 아래로 떨어지는 주기"])[0]


@pytest.mark.parametrize("q,status,word", [
    ("254 주축 모터 과열 알람은 모터 온도가 몇 도 넘으면 뜨는 거예요?", "문서에 없음", "기준값은 사내 문서에 없습니다"),   # E2-067
    ("2075 몇 psi 밑으로 떨어지면 떠?", "답변", "4 PSI"),
    ("991 몇 도에서 떠?", "답변", "90°C"),
    ("WSH-01 알람 몇 도 넘으면 정지해?", "답변", "75 ℃"),
    ("991 몇 도까지 식혀야 돼?", "문서에 없음", "다시 켜는 온도"),
])
def test_alarm_threshold_answers(v4, q, status, word):
    a = A.answer(q, "SUP")
    assert a["status"] == status and word in a["conclusion"] and a["evidence"], a["conclusion"]
    assert "[실제]" not in a["conclusion"]


def test_alarm_threshold_off_by_default(v3):
    assert A.answer("254 주축 모터 과열 알람은 모터 온도가 몇 도 넘으면 뜨는 거예요?", "SUP")["status"] == "답변"   # 예전: 카드로 답함


def test_plain_alarm_question_unchanged(v4):
    a = A.answer("992 뜨면 뭐부터 봐?", "SUP")
    assert a["status"] == "답변" and a["steps"]


# ---------------------------------------------------------------- g 가정 질문
def test_hypothetical_goes_to_docs(v4):
    q = "36개짜리 로트면 발췌검사 때 측정기로 몇 개나 재요?"                  # E2-025
    assert A.parse(q)["intents"] == []
    a = A.answer(q, "SUP")
    assert a["status"] != "확인 필요" and not a["current_data"], a["conclusion"]   # 로트 번호를 묻지 않는다


def test_hypothetical_off_by_default(v3):
    assert A.parse("36개짜리 로트면 발췌검사 때 측정기로 몇 개나 재요?")["intents"]


def test_hypothetical_overrides_llm_ops(llm, v4, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("DOC_GATE", "tiered")
    fake = llm(FakeLlm(route=_route(kind="ops", intents=["lots"]), select=NO, verify={"answers": False, "missing": ""}))
    a = A.answer("36개짜리 로트면 발췌검사 때 측정기로 몇 개나 재요?", "SUP")
    assert "select" in fake.names() and a["status"] == "문서에 없음" and not a["current_data"], (fake.names(), a["conclusion"])


def test_hypothetical_with_date_stays_ops(v4):
    p = A.parse("어제 야간 실적 몇 개야? 90개면 목표 채운 거지?")   # 날짜가 있는 진짜 운영 질문은 그대로
    assert p["intents"] == ["production"] and p["start"] == date(2026, 9, 30), p


@pytest.mark.parametrize("q", ["보류 로트 몇 개야?", "LOT-2609-001-1 몇 개 남았어?"])
def test_real_lot_questions_unchanged(v4, monkeypatch, q):
    p = A.parse(q)
    assert "lots" in p["intents"], p                                      # 숫자로 된 가정이 없으면 로트 조회 그대로
    a4 = A.answer(q, "SUP")
    monkeypatch.setenv("PARSE_V4", "0")
    a3 = A.answer(q, "SUP")
    assert (a4["status"], a4["conclusion"]) == (a3["status"], a3["conclusion"])


# ---------------------------------------------------------------- 후보 순서 실험 (CAND_ORDER)
def _short_chunks(n):
    return sorted((c for c in load_corpus() if A.plain_lines(c)), key=lambda c: sum(map(len, A.plain_lines(c))))[:n]


def test_budgeted_keeps_the_same_lines_as_offer():
    big = sorted(load_corpus(), key=lambda c: -sum(map(len, A.plain_lines(c))))[:6]
    chosen, line_fn = A._budgeted(big)
    want = [t for _, _, t in jobs.offer(big, A.plain_lines)]
    assert [t for c in chosen for t in line_fn(c)] == want
    assert [t for _, _, t in jobs.offer(chosen[::-1], line_fn)] == [t for c in chosen[::-1] for t in line_fn(c)]   # 순서를 바꿔도 같은 줄


@pytest.mark.parametrize("order,calls", [("rank", 1), ("doc", 1), ("dual", 2)])
def test_cand_order(llm, v4, monkeypatch, order, calls):  # noqa: F811
    monkeypatch.setenv("DOC_GATE", "tiered")
    monkeypatch.setenv("SPLIT_Q", "1")
    monkeypatch.setenv("CAND_ORDER", order)
    a, b, c = sorted(_short_chunks(3), key=A._corpus_pos)
    monkeypatch.setattr(A, "search", lambda q, k: [(1.0, c), (0.9, a), (0.8, b)])   # 순위: c, a, b
    seen = []

    def select(body):
        seen.append(body["messages"][-1]["content"])
        return NO
    llm(FakeLlm(select=select))
    assert A._tier2("원래 질문", R.Route("doc", [], [], None, None, None, [], "로컬 LLM"), []) is None
    assert len(seen) == calls
    pos = lambda text, ch: text.index(A._head(ch))  # noqa: E731
    if order in ("rank", "dual"):
        assert pos(seen[0], c) < pos(seen[0], a) < pos(seen[0], b)
    if order == "doc":
        assert pos(seen[0], a) < pos(seen[0], b) < pos(seen[0], c)
    if order == "dual":
        assert pos(seen[1], b) < pos(seen[1], a) < pos(seen[1], c)
