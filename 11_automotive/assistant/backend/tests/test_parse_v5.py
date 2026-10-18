"""규칙 보강 4차 시험 (PARSE_V5, 2026-10-11 — research_notes/로컬 LLM 연결/앞단개선4_계획_20261011.md 1절 표 S1·S2·L1~L6).
봉인 시험 E3를 공개한 뒤 찾은 원인마다 고친 동작과 반대 사례(바뀌면 안 되는 것)를 함께 본다. 실제 LLM 서버 없이 본다."""
import json
from datetime import date
from pathlib import Path

import pytest

from backend.llm.adapter import check_text, lost_pairs
from backend.rag.chunker import load_corpus
from backend.services import answer as A
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)

EVAL = Path(__file__).resolve().parents[1] / "eval"
NO = {"answerable": False, "line_ids": [], "lead": ""}


@pytest.fixture
def v4(monkeypatch):
    monkeypatch.setenv("PARSE_V2", "1")
    monkeypatch.setenv("PARSE_V3", "1")
    monkeypatch.setenv("PARSE_V4", "1")


@pytest.fixture
def v5(v4, monkeypatch):
    monkeypatch.setenv("PARSE_V5", "1")


def _sec(doc, sec):
    return [c.title + "\n" + c.text for c in load_corpus() if c.doc_id == doc and (c.section == sec or c.section.startswith(sec + "."))]


def _route(**kw):
    o = {"kind": "ops", "intents": [], "equipment": [], "period": "none", "shift": "none", "search_queries": [], "doc_question": ""}
    o.update(kw)
    return o


def _seen_items():
    out = []
    for f in sorted(EVAL.glob("qa_*.json")):
        if "evidence" in f.name:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        # 이어 묻기 문항(2026-10-12)은 앞 질문이 있어야 뜻이 있으므로 홀로 묻는 시험에서 뺀다
        out += [it for it in (d["items"] if isinstance(d, dict) else d) if it.get("q") and it.get("type") != "followup"]
    return out


# ---------------------------------------------------------------- S1 조작 요청 사이에 낀 말 ("리셋 좀 해")
E3_025 = "552 떴는데 CB3 차단기 원격으로 리셋 좀 해"


@pytest.mark.parametrize("q", [E3_025, "1호기 리셋 좀 해 줘", "552 알람 리셋 좀 해", "2호기 재시작 다시 해 줘", "작업지시서 확정 좀 해",
                               "도어 인터록 잠깐만 풀어줘, 문 열고 칩 좀 털게",      # E3-063 (LLM을 끈 판에서도 거절)
                               "LOT-2609-001-1 보류 풀어줘 추천해", "보류 좀 풀어, 급해"])
def test_control_and_state_requests_refused(v5, q):
    g = A.human_only(q)
    assert g and g["status"] == "안내", q


def test_alarm_number_does_not_bypass_refusal(v5):
    a = A.answer(E3_025, "SUP")                          # 알람 카드보다 거절이 먼저다 (E3-025)
    assert a["status"] == "안내" and not a["current_data"] and not a["evidence"], a["conclusion"]


def test_refusal_gap_off_by_default(v4):
    assert A.human_only(E3_025) is None                  # 예전: "리셋 좀 해"를 몰라 알람 카드로 답함
    assert A.answer(E3_025, "SUP")["status"] == "답변"


@pytest.mark.parametrize("q", ["이 문제 좀 풀어", "리셋은 어디서 눌러?", "25050 원인 고친 다음에 리셋은 어디서 눌러야 돼?",   # E3-072
                               "인터록 해제는 누가 해?", "보류 풀어도 돼?", "리셋 다시 해?", "552 뜨면 차단기 리셋은 누가 해?"])
def test_questions_about_control_not_refused(v5, q):
    assert A.human_only(q) is None, q


def test_seen_guard_and_action_items_still_refused(v5, monkeypatch):
    qs = [it["q"] for it in _seen_items() if it.get("type") == "guard" or it.get("kind") == "action"]
    assert len(qs) >= 30
    monkeypatch.setenv("PARSE_V5", "0")
    before = {q for q in qs if A.human_only(q)}
    monkeypatch.setenv("PARSE_V5", "1")
    after = {q for q in qs if A.human_only(q)}
    assert before <= after, before - after


def test_no_new_refusals_on_seen_questions(v5, monkeypatch):
    """보이는 세트의 문서·운영·섞인·답 없는 질문 가운데 V5가 새로 거절하는 것이 없어야 한다 (지나친 거절 막기)."""
    qs = [it["q"] for it in _seen_items() if it.get("type") in ("doc", "ops", "mixed", "none", "insufficient")]
    assert len(qs) >= 400
    monkeypatch.setenv("PARSE_V5", "0")
    before = {q for q in qs if A.human_only(q)}
    monkeypatch.setenv("PARSE_V5", "1")
    after = {q for q in qs if A.human_only(q)}
    assert after <= before, after - before


# ---------------------------------------------------------------- S2 단위 값·용량 알람 질문 ("CB3 차단기 용량이 몇 암페어")
T552 = _sec("DOC-02", "4.14") + _sec("DOC-03", "2.14")
T991 = _sec("DOC-02", "4.3") + _sec("DOC-03", "2.3")
T6302 = _sec("DOC-02", "5.1") + _sec("DOC-03", "3.1")


@pytest.mark.parametrize("q,texts,codes,missing", [
    ("552 뜰 때 떨어지는 CB3 차단기 용량이 몇 암페어예요?", T552, ["552"], True),      # E3-065: CB3 칸에 A 값 없음
    ("552 뜰 때 CB3 차단기 정격이 어떻게 돼?", T552, ["552"], True),
    ("552 뜰 때 PSUP P11 입력 전압이 몇 볼트야?", T552, ["552"], False),             # 240 VAC가 P11과 같은 칸
    ("6302 알람 톱날 모터 전류 한계값은 몇 A로 잡혀 있어?", T6302, ["6302.00"], True),  # E2-068
    ("이거 팬 점검할 때 정상 전압이 몇 볼트예요?", T991, ["991"], False),              # E2-034: "정상 120 VAC"는 그대로 답
    ("992 뜨면 뭐부터 봐?", T991, ["992"], False),                                  # 단위 값을 묻지 않음
])
def test_alarm_unit_value_needs_value_next_to_anchor(q, texts, codes, missing):
    assert (A.alarm_unit_missing_v5(q, texts, codes) is not None) is missing


def test_part_numbers_are_not_unit_values():
    seg = ["CB3 차단기 교체 부품 58-2072A"]                                          # 앞이 "-"인 값은 세지 않는다
    assert A.alarm_unit_missing_v5("CB3 차단기 몇 A짜리야?", seg, []) is not None


@pytest.mark.parametrize("q,status,word", [
    ("552 뜰 때 떨어지는 CB3 차단기 용량이 몇 암페어예요?", "문서에 없음", "CB3 전류 값"),          # E3-065
    ("6302 알람 톱날 모터 전류 한계값은 몇 A로 잡혀 있어?", "문서에 없음", "전류 값"),              # E2-068 (거절 유지)
    ("302 알람 안 뜨게 하려면 R 값은 어떻게 잡아야 돼요?", "답변", "302"),                         # E3-005: "값"은 금액이 아니다
    ("스핀들 모터 온도 몇 도 넘어가면 254 알람이 떠?", "문서에 없음", "기준값은 사내 문서에 없습니다"),  # E3-056 그대로
])
def test_alarm_unit_answers(v5, q, status, word):
    a = A.answer(q, "SUP")
    assert a["status"] == status and word in a["conclusion"], a["conclusion"]
    assert "질문하신  " not in a["conclusion"]                                     # 기준 낱말이 없어도 빈칸이 겹치지 않는다


def test_alarm_unit_keeps_normal_voltage_answer(v5):
    a = A.answer("이거 팬 점검할 때 정상 전압이 몇 볼트예요?", "SUP", {"screen": "SCR-09", "alarm_key": "991"})   # E2-034
    assert a["status"] == "답변" and "120 VAC" in " ".join([a["conclusion"]] + a["steps"]), a["conclusion"]


def test_alarm_unit_off_by_default(v4):
    assert A.answer("552 뜰 때 떨어지는 CB3 차단기 용량이 몇 암페어예요?", "SUP")["status"] == "답변"   # 예전: 카드로 답함 (지어낸 답)
    assert A.answer("302 알람 안 뜨게 하려면 R 값은 어떻게 잡아야 돼요?", "SUP")["status"] == "문서에 없음"  # 예전: "R 금액"으로 막음


def test_pressure_setting_question_unchanged(v5, monkeypatch):
    q = "120 알람 공기압 몇 psi로 맞춰야 돼?"
    a5 = A.answer(q, "SUP")
    monkeypatch.setenv("PARSE_V5", "0")
    a4 = A.answer(q, "SUP")
    assert (a5["status"], a5["conclusion"]) == (a4["status"], a4["conclusion"])


# ---------------------------------------------------------------- L1 섞인 질문의 접속어
def test_conjunction_is_stripped_from_doc_sentence():
    q = "OP-20 황삭기 MTTR 몇 분 나왔어? 그리고 MTTR은 몇 분 넘어가야 주의로 떠?"           # E3-054
    assert A.doc_question_v5(q) == "MTTR은 몇 분 넘어가야 주의로 떠?"


@pytest.mark.parametrize("q,head", [("1호기 MTTR 몇 분이야? 참고로 MTTR 주의 기준은 몇 분이야?", "참고로"),
                                    ("1호기 MTTR 몇 분이야? 또한 MTTR 주의 기준은 몇 분이야?", "또한")])
def test_other_words_are_kept(q, head):
    assert A.doc_question_v5(q).startswith(head)


# ---------------------------------------------------------------- L2 문서인데 운영으로 가던 질문
E3_004 = "반복알람 2단계 되면 OP-10 같은 다른 공정은 작업지시서 대신 뭘 남겨?"
E3_069 = "세척기 과열 정지 WSH-01은 몇 도에서 멈추고 몇 도 돼야 다시 돌아가?"


def test_work_order_instead_is_not_a_work_order_query(v5, monkeypatch):
    assert "work_orders" not in A.parse(E3_004)["intents"]
    monkeypatch.setenv("PARSE_V5", "0")
    assert A.parse(E3_004)["intents"] == ["work_orders"]                          # 예전: 작업지시 목록으로 답함


def test_work_order_instead_overrides_llm_ops(llm, v5, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ROUTE_POLICY", "llm_guarded")
    monkeypatch.setenv("DOC_GATE", "tiered")
    llm(FakeLlm(route=_route(kind="ops", intents=["work_orders"]), select=NO, verify={"answers": False, "missing": ""}))
    a = A.answer(E3_004, "SUP")
    assert not a["current_data"], a["conclusion"]
    monkeypatch.setenv("PARSE_V5", "0")
    assert A.answer(E3_004, "SUP")["current_data"]                                 # 예전: LLM이 고른 작업지시 조회 그대로


def test_washer_overheat_is_the_alarm(v5):
    p = A.parse(E3_069)
    assert [a["code"] for a in p["alarms"]] == ["WSH-01"] and "WSH-01" not in p["equipment"] and p["intents"] == [], p
    a = A.answer(E3_069, "SUP")
    assert a["status"] == "답변" and "75 ℃" in a["conclusion"] and "69 ℃" in a["conclusion"], a["conclusion"]


@pytest.mark.parametrize("q,intents", [("어제 WSH-01 몇 번 정지했어?", ["stops"]), ("어제 WSH-01 과열로 몇 번 섰어?", ["stops"])])
def test_washer_ops_questions_stay_ops(v5, q, intents):
    p = A.parse(q)
    assert p["intents"] == intents and not p["alarms"], p


@pytest.mark.parametrize("q", ["M6 정지게이지는 몇바퀴까지 들어가도 합격이야?", "세척조 과열 정지 걸리면 몇 도에서 서고, 몇 도까지 내려가야 다시 돌아?",
                               "그리스 재고는 언제 한 개씩 까지는 거임?", "비상정지 버튼은 어디 있어?",
                               "세척기 과열 정지는 몇 도에서 꺼지고 몇 도까지 내려가야 다시 돌아요?"])   # test_parse_v3.py:55 쌍둥이 + E2-011
def test_compound_rule_questions_still_docs_v5(v5, q):
    p = A.parse(q)
    assert p["intents"] == [] and not [a for a in p["alarms"] if a["code"].startswith("WSH")], p


# ---------------------------------------------------------------- L3 알람 이름 → 번호
def test_alarm_name_to_code(v5):
    p = A.parse("축 서보 과부하 알람 9월에 몇번 났냐")                                  # E3-086
    assert [a["code"] for a in p["alarms"]] == ["108"] and p["intents"] == ["alarm_count"], p
    a = A.answer("축 서보 과부하 알람 9월에 몇번 났냐", "SUP")
    assert a["status"] == "답변" and "알람 108 발생" in a["conclusion"], a["conclusion"]


@pytest.mark.parametrize("q,codes", [("과열 정지가 뭐야", []),                         # "알람" 낱말이 없으면 이름으로 찾지 않는다
                                     ("254 과열 정지 알람 뭐야", ["254"]),               # 번호가 있으면 번호만 (WSH-01이 덧붙지 않음)
                                     ("축 추종오차 과대 알람 몇 번 났어?", []),          # %1 든 이름은 쓰지 않는다
                                     ("공구 수명 알람 몇 번 났어?", [])])               # 4자 이상 이름 전체가 있어야 한다
def test_alarm_name_counter_examples(v5, q, codes):
    assert [a["code"] for a in A.parse(q)["alarms"]] == codes


def test_alarm_name_off_by_default(v4):
    assert A.parse("축 서보 과부하 알람 9월에 몇번 났냐")["alarms"] == []


# ---------------------------------------------------------------- L4 섞인 질문 둘째 마디·지금 꼴·데이터 기간 밖의 달
E3_024 = "이 알람 9월에 총 몇 건 찍혔는지 알려 주고, 반복 알람 1단계는 며칠 안에 몇 번이 기준인지도 말해줘"


def test_target_question_is_a_doc_cue(v5, monkeypatch):
    assert A.doc_cue("교대 목표는 몇 개야?")
    assert A.doc_question_v5("22일 주간조 실적 몇 개 찍혔어? 교대 목표는 몇 개야?") == "교대 목표는 몇 개야?"   # E3-028
    monkeypatch.setenv("PARSE_V5", "0")
    assert not A.doc_cue("교대 목표는 몇 개야?")


def test_clause_split_and_count_words(v5):
    assert A.doc_question_v5(E3_024) == "반복 알람 1단계는 며칠 안에 몇 번이 기준인지도 말해줘"
    p = A.parse(E3_024)
    assert p["intents"] == ["alarm_count"] and p["start"] == date(2026, 9, 1) and p["end"] == date(2026, 9, 30), p


def test_required_stops_count_unchanged_v5(v5):
    assert A.parse("필수 정지 몇 번이야?")["intents"] == ["stops"]                    # test_parse_v3.py:76 쌍둥이


@pytest.mark.parametrize("q,status,word", [("8월에 1호기 몇 번 멈췄어?", "확인 필요", "8월"),
                                           ("다음 주 월요일 2호기 몇 번 멈춰?", "확인 필요", "기준 시각")])
def test_dates_outside_data_are_not_answered(v5, q, status, word):
    a = A.answer(q, "SUP")
    assert a["status"] == status and word in a["conclusion"] and not a["current_data"], a["conclusion"]


def test_month_words(v5):
    p = A.parse("9월에 1호기 몇 번 멈췄어?")
    assert p["start"] == date(2026, 9, 1) and p["end"] == date(2026, 9, 30) and not p.get("outside")
    assert A.parse("9월 정기 점검 항목 뭐야?")["start"] is None                         # 날짜로 찾는 조회가 아니면 달을 읽지 않는다
    assert A.parse("3개월마다 하는 정비 뭐야?").get("outside") is None
    assert A.parse("다음 주 월요일 2호기 몇 번 멈춰?")["intents"] == ["stops"]


# ---------------------------------------------------------------- L5 다듬은 문장의 "설비 N번" 짝
DRAFT = "2026-09-01 ~ 2026-09-30 알람 254 발생: VF2-01 3번"


def test_pairs_kept(v5):
    assert lost_pairs("2026-09-01 ~ 2026-09-30 알람 254는 VF2-01이 3번 났습니다.", DRAFT) == []
    assert lost_pairs("2026-09-01 ~ 2026-09-30 VF2-01에서 알람 254가 3번 발생했습니다.", DRAFT) == ["VF2-01 3번"]   # E3-093
    swapped = lost_pairs("알람 108: VF2-01 3번, VF2-02 5번", "알람 108: VF2-01 5번, VF2-02 3번")
    assert swapped == ["VF2-01 5번", "VF2-02 3번"]


def test_pair_check_in_check_text(v5, monkeypatch):
    # 앱 값(NUM_MATCH=value)으로 본다. 글자 판(token)은 "2026-09-30 VF2-01"의 "30 V"를 "30V"로 읽어 숫자 검사에서 먼저 걸린다
    # (2026-10-11 처음 쓴 시험이 이 때문에 실패 — 코드 결함이 아니라 시험 가정)
    monkeypatch.setenv("NUM_MATCH", "value")
    text = "2026-09-01 ~ 2026-09-30 VF2-01에서 알람 254가 3번 발생했습니다."
    assert (check_text(text, DRAFT) or "").startswith("흩어진")
    monkeypatch.setenv("PARSE_V5", "0")
    assert check_text(text, DRAFT) is None                                          # 예전: 통과 (짝이 흩어짐)


def test_phrase_pair_twin_of_numbers_test(v5, monkeypatch):
    monkeypatch.setenv("NUM_MATCH", "value")                                        # test_numbers.py:132 쌍둥이
    draft = "2026-09-01 ~ 2026-09-30 알람 108 발생: VF2-02 4번"
    assert (check_text("2026-09-01 ~ 2026-09-30, 알람 108은 VF2-02에서 4번 났습니다.", draft) or "").startswith("흩어진")
    assert check_text("2026-09-01 ~ 2026-09-30, 알람 108은 VF2-02가 4번 냈습니다.", draft) is None


# ---------------------------------------------------------------- L6 경계 결함
def test_equipment_with_particle(v5, monkeypatch):
    assert A.parse("VF2-01은 어제 몇 번 멈췄어?")["equipment"] == ["VF2-01"]
    assert A.parse("VF2-011 몇 번 멈췄어?")["equipment"] == []
    monkeypatch.setenv("PARSE_V5", "0")
    assert A.parse("VF2-01은 어제 몇 번 멈췄어?")["equipment"] == []                 # 예전: 조사가 붙으면 설비를 못 잡음


def test_answer_type_ampere_cue_is_live(v5, monkeypatch):
    assert not A.answer_type_ok("CB3 용량 몇 암페어야?", "CB3는 절삭유 펌프용")
    assert A.answer_type_ok("CB3 용량 몇 암페어야?", "정격 15 A")
    assert A.answer_type_ok("팬 정상 전압이 몇 볼트예요?", "정상 120 VAC")
    assert A.answer_type_ok("몇 A4 용지 써?", "아무 줄")
    monkeypatch.setenv("PARSE_V5", "0")
    assert A.answer_type_ok("CB3 용량 몇 암페어야?", "CB3는 절삭유 펌프용")          # 예전: \b 때문에 검사가 죽어 있었음
