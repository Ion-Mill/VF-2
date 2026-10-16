"""규칙 보강 6차 시험 (PARSE_V7, 2026-10-12 — research_notes/로컬 LLM 연결/앞단개선6_계획_20261012.md 3.2절).
답 모양 낱말 빼기(사용자 테스트 "방금내용 더 쉽게 설명해"), 전제 마디(E5-072), "무슨 모델" 꼴(E5-075)마다 고친 동작과
반대 사례(바뀌면 안 되는 것)를 함께 본다. LLM을 끈 판(v7-fallback의 PARSE_V7 부분)으로 본다 — 실제 LLM 서버 없이."""
import pytest

from backend.services import answer as A


@pytest.fixture
def v6(monkeypatch):
    for k in ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6"):
        monkeypatch.setenv(k, "1")


@pytest.fixture
def v7(v6, monkeypatch):
    monkeypatch.setenv("PARSE_V7", "1")


def ask(q, ctx=None):
    return A.answer(q, "SUP", ctx)


# ---------------------------------------------------------------- 기본값이면 예전과 같다
def test_switch_off_keeps_v6_behaviour(v6):
    # 사용자 테스트(2026-10-12)와 같은 꼴: V6에서는 "방금"이 "개방금지"(DOC-05 §2)에 걸려 엉뚱하게 답했다
    a = ask("방금 내용 더 쉽게 설명해")
    assert a["status"] == "답변"
    assert "쉽게" in A.content_words("웨이 커버 그리스 쉽게 설명해 줘")


# ---------------------------------------------------------------- 답 모양 낱말·주제 없는 질문
@pytest.mark.parametrize("q", ["방금 내용 더 쉽게 설명해", "방금내용 더 쉽게 설명해", "위 내용 요약해 줘", "더 쉽게 설명해 줘",
                               "이거 더 자세히 설명해 줘", "그거 다시 말해 줘"])
def test_no_subject_questions_do_not_search(v7, q):
    a = ask(q)
    assert a["status"] in ("문서에 없음", "근거 없음", "확인 필요"), (q, a["conclusion"][:80])


def test_shape_words_dropped_only_when_subject_remains(v7):
    assert A.content_words("웨이 커버 그리스 쉽게 설명해 줘") == ["그리스", "웨이", "커버"]
    assert A.strip_shape_v7("웨이 커버 그리스 쉽게 설명해 줘") == "웨이 커버 그리스 줘"
    assert A.no_subject_v7("방금 내용 더 쉽게 설명해") and not A.no_subject_v7("웨이 커버 그리스 쉽게 설명해 줘")


@pytest.mark.parametrize("q,word", [("요약 보고서는 누가 확정해?", "요약"), ("설명서는 어디 있어?", "설명서"),
                                    ("교대 끝나기 전에 작업자가 정리해야 되는 거 뭐 있어요?", "정리해야"),
                                    ("다시 시작하려면 뭐 해?", "다시")])
def test_shape_words_keep_nouns_and_real_verbs(v7, q, word):
    # 명사·진짜 뜻의 동사는 빼지 않는다 (E2-009 "정리해야", "다시 시작"은 보이는 세트 비교 전에 찾음)
    assert any(word in w or w in word for w in A.content_words(q)), (q, A.content_words(q))


def test_restart_question_still_answers(v7):
    a = ask("다시 시작하려면 뭐 해?")   # "다시"를 답 모양 낱말로 빼면 문서에 없음이 되던 것 (2026-10-12 조정 중 찾음)
    assert a["status"] == "답변"


# ---------------------------------------------------------------- E5-072 전제 마디
def test_premise_clause_is_not_an_ops_clause(v7):
    import re
    q = "반복 알람 2단계 돼도 세척 공정은 작업지시서 안 만든다며. 그럼 원인 점검 결과는 어디에 남겨?"
    assert not A.ops_clause_v6(q, re.compile(r"(?!)"))
    assert A.PREMISE_V7.search("세척 공정은 작업지시서 안 만든다며.")


def test_premise_fix_keeps_e4_030(v7):
    import re
    q = "축 윤활유 저장소 비워짐 알람 한 달 새 몇 번 났어요? 그리고 몇 번 나면 반복 알람으로 잡혀요?"
    assert A.ops_clause_v6(q, re.compile(r"(?!)"))   # 5차 L4의 고친 동작(E4-030)은 그대로


def test_premise_off_switch(v6):
    import re
    q = "반복 알람 2단계 돼도 세척 공정은 작업지시서 안 만든다며. 그럼 원인 점검 결과는 어디에 남겨?"
    assert A.ops_clause_v6(q, re.compile(r"(?!)"))   # V6에서는 전제 마디도 운영 마디로 셌다 (E5-072)


# ---------------------------------------------------------------- E5-075 "무슨 모델" 꼴
def test_model_question_needs_name_of_the_asked_object(v7):
    line = "④ 농도 측정 · 매주 굴절계로 잰다. 농도 = 굴절계 값 × 1.4 (TRIM SC538의 굴절계 계수) / 굴절계 계수 · 1.4"
    assert not A.model_name_ok_v7("절삭유 농도 재는 굴절계는 무슨 모델 써?", line)   # TRIM SC538은 절삭유 이름
    assert not A.answer_type_ok("절삭유 농도 재는 굴절계는 무슨 모델 써?", line)
    assert not A.first_gate_type_ok_v6("절삭유 농도 재는 굴절계는 무슨 모델 써?", line)


def test_model_question_keeps_real_answers(v7):
    # F25: "CS-AFLT = 이 필터(Haas P/N 58-1391 …)" — 필터 바로 뒤 괄호에 이름이 있다
    assert A.model_name_ok_v7("OP-30 공기 필터는 어느 회사 제품 써?", "CS-AFLT = 이 필터(Haas P/N 58-1391 \"Muffler\")")
    assert A.model_name_ok_v7("웨이 커버 그리스는 무슨 제품 써?", "CS-GRS — 품목: 그리스 (Mobil Grease XHP 222, 14 oz 카트리지)")
    assert A.model_name_ok_v7("웨이 커버 그리스 이름이 뭐예요?", "아무 줄")    # 모델·제품을 묻지 않으면 검사하지 않는다


def test_lock_brand_question_refused(v7):
    a = ask("LOTO할 때 쓰는 개인 자물쇠는 어느 회사 제품이에요?")   # E003 (본 세트): V6는 자물쇠 줄로 답함
    assert a["status"] in ("문서에 없음", "근거 없음", "확인 필요")
