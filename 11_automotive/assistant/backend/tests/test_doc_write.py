"""10차 DOC_WRITE 시험 (2026-10-13 사용자 결정 — 문서 답을 AI가 찾은 줄로 새로 씀). LLM 없이: 쓸지 말지 조건, 자리표, 코드 검사, 줄 목록 칸.
알람·DOC-03·DOC-05·절차·안전 낱말은 새로 쓰지 않는다(규칙 2.5). 쓴 글은 원문에 없는 숫자·영문을 낼 수 없어야 한다."""
import pytest

from backend.config import settings
from backend.services import answer as A
from backend.services import blocks_v2 as BL2
from backend.services import followup_v2 as FU2

ON = ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP", "PARSE_V8", "FOLLOWUP_V2",
      "PARSE_V9", "FLOW_V9", "BLOCKS_V2", "PARSE_V10", "FLOW_V10", "BLOCKS_V3", "DOC_WRITE")
LINE = "야간 교대 보고서 — AI비서 초안 만드는 시각: 05:00 (야간 교대 끝) · 확정: 야간 반장이 06:00 전 확정"
CITE01 = {"doc_id": "DOC-01", "section": "3.3"}


@pytest.fixture
def on(monkeypatch):
    for k in ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("LLM_ENABLED", "1")
    monkeypatch.setenv("LLM_JOBS", "write,route")
    return monkeypatch


def test_write_ok_for_plain_doc_line(on):
    assert A.doc_write_ok_v11(settings(), [LINE], [CITE01], None, False)


@pytest.mark.parametrize("lines, cites, exclude, procedure", [
    ([LINE], [{"doc_id": "DOC-03", "section": "2.11"}], None, False),                 # 고장 대응
    ([LINE], [{"doc_id": "DOC-05", "section": "2"}], None, False),                    # 안전 작업
    (["외함 — 항목: 웨이 커버 · 잠금·표지: ○"], [CITE01], None, False),             # 안전 낱말 줄
    ([LINE], [CITE01], {("DOC-02", "4.11")}, False),                                   # 알람 + 문서 (카드 길)
    ([LINE], [CITE01], None, True),                                                    # 절차
    ([LINE, LINE], [CITE01], None, False),                                             # 줄마다 출처가 없음
])
def test_write_not_for_blocked(on, lines, cites, exclude, procedure):
    assert not A.doc_write_ok_v11(settings(), lines, cites, exclude, procedure)


def test_write_off_without_switch(on):
    on.setenv("DOC_WRITE", "0")
    assert not A.doc_write_ok_v11(settings(), [LINE], [CITE01], None, False)


def test_delex_lines_numbers_across_lines():
    units, vals, owner = FU2.delex_lines([LINE, "세척액 · 물 기반 중성 세척액 5% + 물 95% (예: Elma tec clean N1)"])
    assert len(units) == 2 and "05:00" in vals and "06:00" in vals and "Elma tec clean N1" in vals
    assert all(not any(ch.isdigit() for ch in FU2.PH.sub("", u)) for u in units)   # 자리표 밖에 숫자 없음
    assert set().union(*owner.values()) == {0, 1}   # 2026-10-13: 같은 값을 번호 하나로 묶어 owner는 번호 → 줄 번호 묶음


def test_relex_subset_allows_some_placeholders_only():
    vals = ["05:00", "06:00"]
    assert FU2.relex_subset("야간 반장이 {{2}} 전에 확정해요.", vals) == ("야간 반장이 06:00 전에 확정해요.", None)
    assert FU2.relex_subset("{{3}} 전에 확정해요.", vals)[1] == "없는 자리표"
    assert FU2.relex_subset("아침 6시 전에 확정해요.", vals)[1].startswith("자리표 밖의 숫자·영문")   # 새 숫자는 쓸 수 없다
    assert FU2.relex_subset("06:00 전에 확정해요.", vals)[1].endswith("06:00 → {{2}}")   # 다시 요청 때 자리표 번호를 알려 줌


@pytest.mark.parametrize("answer, reason", [
    ("야간 반장이 06:00 전에 확정해요.", None),
    ("야간 반장이 06:00 전에 확정해도 돼요.", "허락·지시 문구"),
    ("야간 반장이 06:00 전까지 확정해야 합니다.", None),           # 2026-10-13 사용자 결정: 합니다체 허용
    ("야간 반장이 06:00 전에 확정해도 됩니다.", "허락·지시 문구"),   # 허락 문구는 말투와 따로 막는다
    ("야간 반장이 06:00 시 전까지 확정해요.", "시각 뒤에"),
    ("바로 돌려도 돼요.", "허락·지시 문구"),                     # 2026-10-13: "해도"가 아닌 허락 꼴
    ("켜도 괜찮아요.", "허락·지시 문구"),
    ("06:00 전에 확정이 가능해요.", "허락·지시 문구"),
    ("공구를 바로 교체하세요.", "허락·지시 문구"),               # 조작 동사 지시
    ("설비를 가동해 주세요.", "허락·지시 문구"),
    ("06:00 전에 확정했는지 확인하세요.", None),                # 확인하라는 말은 통과
    ("교체 주기를 반장에게 물어보세요.", None),                 # "교체 주기"는 지시가 아님
    ("세 번 확인해요.", "한글 수사"),
    ("DOC-01 §3.3에 따라 확정해요.", "출처 표기"),
    ("확정해요. 반장이 해요. 06:00 전이에요. 초안은 미리 나와요.", "문장이 너무 많음"),
])
def test_check_answer(answer, reason):
    got = FU2.check_answer_v11(answer, [LINE], {0})
    assert (got is None) if reason is None else (got is not None and got.startswith(reason))


@pytest.mark.parametrize("raw, want", [
    ("중성 세척액 5% 과 물 95% 를 섞어 써요.", "중성 세척액 5%와 물 95%를 섞어 써요."),
    ("목표는 90 개예요.", "목표는 90 개예요."),               # 조사가 아니면 그대로
    ("06:00 이 기준이에요.", "06:00이 기준이에요."),          # 0은 받침 있음(영)
    ("Mobil Grease XHP 222 를 써요.", "Mobil Grease XHP 222를 써요."),   # 2는 받침 없음(이)
])
def test_tidy_answer_josa_after_values(raw, want):
    assert FU2.tidy_answer_v11(raw) == want


def test_answer_grammar_allows_only_listed_placeholders():
    g = FU2.answer_grammar_v11(3)
    assert '"{{" ( "1" | "2" | "3" ) "}}"' in g and "[^0-9A-Za-z{}" in g   # 자리표 밖 숫자·영문·중괄호 금지
    assert '"{{"' not in FU2.answer_grammar_v11(0)                          # 값이 없으면 자리표도 없음


def test_same_value_one_placeholder_and_question_masked_with_it():
    units, vals, owner = FU2.delex_lines(["MTTR / MTBF — 표준어: 평균 수리 시간(MTTR) / 평균 고장 간격(MTBF)"])
    assert vals == ["MTTR", "MTBF"] and units[0].count("{{2}}") == 2 and owner[2] == {0}
    q = FU2.delex_question_v11("보고서에 MTBF라고 적혀 있던데 VF2-03은? 6단계", vals + ["6"])
    assert q == "보고서에 {{2}}라고 적혀 있던데 VF2-03은? 6단계"   # 문서에 없는 값·짧은 숫자는 가리지 않음


def test_permission_kept_when_source_has_it():
    src = "보충 — 방법: 막 채운 뒤에는 바로 돌려도 된다"
    assert FU2.check_answer_v11("막 채운 뒤에는 바로 돌려도 돼요.", [src], {0}) is None   # 원문에 있던 허락은 옮겨도 됨


def test_restore_literals_turns_masked_values_back_into_placeholders():
    assert FU2.restore_literals_v11("MTBF는 {{1}}과 달라요.", ["MTTR", "MTBF"]) == ("{{2}}는 {{1}}과 달라요.", 1)
    assert FU2.restore_literals_v11("{{12}}는 그대로", ["1", "2"])[0] == "{{12}}는 그대로"   # 자리표 안은 건드리지 않음
    assert FU2.restore_literals_v11("XMTBF는", ["MTBF"]) == ("XMTBF는", 0)                   # 다른 낱말의 일부는 그대로


def test_check_answer_keeps_markers_of_used_lines():
    line = "교대 목표 — 값: 90개 [가상] · 구분: 팀 정의"
    assert FU2.check_answer_v11("교대 목표는 90개예요.", [line], {0}).startswith("빠진 꼬리표")
    assert FU2.check_answer_v11("교대 목표는 90개 [가상]예요.", [line], {0}) is None


def test_blocks_mark_written_lead_and_orig_lines():
    written = "야간 반장이 06:00 전에 확정해요."
    c = f"{written} {A.DOC_WRITE_SEP_V11} {LINE}"
    out = BL2.build([c], None, [], [], [LINE], [{"cite": "공정별 운영 매뉴얼 DOC-01 §3.3"}], c, written=written)
    assert out[0] == {"kind": "lead", "text": written, "written": True}
    assert out[1]["kind"] == "line" and out[1].get("orig") is True
    plain = BL2.build([LINE], None, [], [], [LINE], [{"cite": "x"}], LINE)   # 쓰지 않은 답은 그대로
    assert all(not b.get("orig") and not b.get("written") for b in plain)


# ---------------------------------------------------------------- 10차 보강 PARSE_V11 (2026-10-14 사용자 결정, 앱 화면 "MTBF은"·"?" 흔들림)
@pytest.mark.parametrize("raw, vals, want", [
    ("보고서에 적힌 MTBF은 평균 고장 간격이에요.", ["MTTR", "MTBF"], "보고서에 적힌 MTBF는 평균 고장 간격이에요."),
    ("MTBF 이 길면 좋아요.", ["MTBF"], "MTBF가 길면 좋아요."),
    ("OEE를 봐요.", ["OEE"], "OEE를 봐요."),                       # 이미 맞음
    ("OEE을 봐요.", ["OEE"], "OEE를 봐요."),
    ("CS-WLUB은 축 윤활유예요.", ["CS-WLUB"], "CS-WLUB는 축 윤활유예요."),   # B(비) — 받침 없음
    ("PLM는 시스템이에요.", ["PLM"], "PLM은 시스템이에요."),          # M(엠) 받침
    ("URL으로 열어요.", ["URL"], "URL로 열어요."),                    # L(엘) ㄹ 받침 → "로"
    ("PLM로 관리해요.", ["PLM"], "PLM으로 관리해요."),
    ("MTBF이라고 써요.", ["MTBF"], "MTBF이라고 써요."),               # 뒤에 한글이 이어지면 조사로 보지 않음
    ("Lube은 윤활이에요.", ["Lube"], "Lube은 윤활이에요."),           # 소문자 섞인 낱말은 읽는 법을 몰라 그대로
    ("CB3은 차단기예요.", ["CB3"], "CB3은 차단기예요."),              # 숫자로 끝나면 이 고침이 아님
])
def test_acronym_josa_v11b(raw, vals, want):
    assert FU2.tidy_acronym_v11b(raw, vals) == want


@pytest.mark.parametrize("q, hit", [
    ("보고서에 MTBF라고 적혀 있던데 한국어 표준 용어로 바꾸면 뭐라고 써", True),
    ("쿨런트 표준어가 뭐야?", True),
    ("절삭유를 쓰지 않는 말로 뭐라고 해?", True),
    ("이건 정식 명칭이 뭐야?", True),
    ("절삭유는 어떻게 써?", False),              # 쓰는 법 질문 — 용어 질문이 아님
    ("MTBF 몇 시간이야?", False),
])
def test_term_question_pattern_v11b(q, hit):
    assert bool(A.TERM_Q_V11B.search(q)) is hit


def test_tier2_puts_glossary_first_only_when_on(on, monkeypatch):
    from types import SimpleNamespace as NS
    doc07 = NS(chunk_id="DOC-07:6.2", doc_id="DOC-07")
    other = NS(chunk_id="DOC-07:3", doc_id="DOC-07")
    gloss = NS(chunk_id="GLOSSARY:8", doc_id="GLOSSARY")
    monkeypatch.setattr(A, "search", lambda q, k=15: [(9.0, doc07), (8.0, other), (7.0, gloss)])
    route = NS(queries=["MTBF 평균 고장 간격"])
    q = "보고서에 MTBF라고 적혀 있던데 한국어 표준 용어로 바꾸면 뭐라고 써"
    on.setenv("PARSE_V11", "0")
    assert A._tier2_cands(q, route)[0][0].chunk_id == "DOC-07:6.2"      # 꺼짐 = 예전 순서
    on.setenv("PARSE_V11", "1")
    cands = A._tier2_cands(q, route)[0]
    assert cands[0].chunk_id == "GLOSSARY:8" and {c.chunk_id for c in cands} >= {"DOC-07:6.2", "DOC-07:3"}   # 뺀 것 없이 순서만
    assert A._tier2_cands("MTBF는 어떻게 계산해?", route)[0][0].chunk_id == "DOC-07:6.2"   # 용어 질문이 아니면 그대로


# ---------------------------------------------------------------- 10차 보강 LEAD_V12 (2026-10-14 사용자 결정): 1차 길 AI 앞머리 검사
FEED_LINE = "Feed Rate — 표준어: 이송 속도 · 쓰지 않는 말: —"


@pytest.mark.parametrize("lead, lines, q, why", [
    ("이송 속도는 Feed Rate로 표기하며, 작업자가 이송과 속도를 조정해야 합니다.", [FEED_LINE], "이송 속도 영어로 뭐라고 해", "해야 할 일 꼴"),  # 앱 로그
    ("배치도를 바꿔도 돼요.", ["배치도 — 표준어: 배치도"], "배치도가 뭐야", "허락 꼴"),
    ("이송 속도를 올려 주세요.", [FEED_LINE], "이송 속도 뭐야", "조작 지시"),
    ("잠금 장치를 먼저 확인합니다.", [FEED_LINE], "이송 속도 뭐야", "안전 낱말"),
    ("이송 속도의 영어 이름은 Feed Rate예요.", [FEED_LINE], "이송 속도 영어로 뭐라고 해", None),
    ("MTBF는 평균 고장 간격이라고 써야 해요.", ["MTBF — 표준어: 평균 고장 간격(MTBF)"], "뭐라고 써야 해요?", None),   # 질문의 꼴을 받은 말
    ("출하 전 검사를 해야 한다.", ["출하 전 반드시 검사를 해야 한다"], "출하 전에 뭐 해", None),               # 원문에 있던 꼴
])
def test_lead_code_check_v12(lead, lines, q, why):
    assert FU2.check_lead_code_v12(lead, lines, q) == why


def test_lead_v12_faith_and_fail_closed(monkeypatch):
    lines = [FEED_LINE]
    monkeypatch.setattr(FU2, "chat_json", lambda *a, **k: {"faithful": False, "problem": "문서에 없는 읽는 법"})
    ok, tr = FU2.check_lead_v12("이송 속도 영어로?", "이송 속도는 피드 레이트(Feed Rate)예요.", lines)
    assert not ok and tr["rejected"][0]["reason"] == "문서에 없는 읽는 법"
    monkeypatch.setattr(FU2, "chat_json", lambda *a, **k: {"faithful": True, "problem": ""})
    assert FU2.check_lead_v12("이송 속도 영어로?", "이송 속도의 영어 이름은 Feed Rate예요.", lines)[0]

    def boom(*a, **k):
        raise FU2.LlmUnavailable("down")
    monkeypatch.setattr(FU2, "chat_json", boom)
    ok, tr = FU2.check_lead_v12("이송 속도 영어로?", "이송 속도의 영어 이름은 Feed Rate예요.", lines)
    assert not ok and tr["reason"].startswith("LLM 오류")   # 판정을 못 받으면 앞머리를 뺀다 (fail closed)


def test_answer_check_oblige_only_with_question(monkeypatch):
    lines = [FEED_LINE]
    txt = "이송 속도는 작업자가 조정해야 해요."
    assert FU2.check_answer_v11(txt, lines, set()) is None                                   # 스위치 끔 = 예전 그대로
    # 2026-10-14 TERM_V13: question은 LEAD_V12 또는 TERM_V13일 때 넘기므로 "해야" 검사는 LEAD_V12를 따로 본다(시험 가정을 넓힘 — 코드 결함 아님)
    monkeypatch.setenv("LEAD_V12", "1")
    assert FU2.check_answer_v11(txt, lines, set(), question="이송 속도 뭐야").startswith("해야 할 일 꼴")
    monkeypatch.setenv("LEAD_V12", "0")
    assert FU2.check_answer_v11(txt, lines, set(), question="이송 속도 뭐야") is None


# ---------------------------------------------------------------- 10차 보강 TERM_V13 (2026-10-14 사용자 결정)
@pytest.fixture
def term_on(on):
    on.setenv("TERM_V13", "1")
    return on


def test_avoid_words_skip_conditional_and_latin():
    words = FU2.avoid_words_v13()
    assert "피드" in words and "쿨런트" in words and "일보" in words
    assert not any("(" in w for w in words)                      # "차단기(단독)"·"(괄호로만)" 같은 조건 붙은 말은 뺌
    assert "ATC" not in words and "WIP(괄호로만)" not in words


@pytest.mark.parametrize("text, src, q, hit", [
    ("이송 속도의 표준 영어 표현은 피드 레이트(Feed Rate)예요.", FEED_LINE, "이송 속도 영어로 뭐라고 해?", "피드"),   # 앱 화면
    ("쿨런트는 쓰지 않는 말이고, 문서에는 절삭유라고 써요.", "Coolant — 표준어: 절삭유 · 쓰지 않는 말: 쿨런트, 쿨란트", "쿨런트가 뭐야?", None),
    ("피드를 줄여요.", FEED_LINE, "피드가 뭐야?", None),           # 질문이 쓴 말은 받을 수 있다
    ("에어건으로 불어요.", "에어건 출구 압력", "에어건은?", None),  # "에어건" 속 "에어"는 잡지 않음
    ("에어를 빼요.", "공기 압력", "공기 빼는 법", "에어"),
])
def test_avoid_new_v13(text, src, q, hit):
    assert FU2.avoid_new_v13(text, src, q) == hit


def test_lead_and_answer_block_avoid_word_only_when_on(on, monkeypatch):
    lead = "이송 속도의 표준 영어 표현은 피드 레이트(Feed Rate)로 정의되어 있습니다."
    assert FU2.check_lead_code_v12(lead, [FEED_LINE], "이송 속도 영어로 뭐라고 해?") is None        # 끔 = 예전 그대로 (앱 로그의 놓침)
    monkeypatch.setenv("TERM_V13", "1")
    assert FU2.check_lead_code_v12(lead, [FEED_LINE], "이송 속도 영어로 뭐라고 해?") == "쓰지 않는 말: 피드"
    assert FU2.check_answer_v11(lead, [FEED_LINE], set(), question="이송 속도 영어로?").startswith("쓰지 않는 말: 피드")
    # 처음 쓴 원문 조각 FEED_LINE에는 "않"(조건 말)이 있어 앞 검사가 먼저 걸렸다 — 시험 가정을 고침(코드 결함 아님)
    assert FU2.check_unit("이송 속도는 피드 레이트예요", "Feed Rate — 표준어: 이송 속도") == "쓰지 않는 말: 피드"


def test_english_name_answer_must_have_english(term_on, monkeypatch):
    """짝 질문 로그(2026-10-14): "로트 해제의 영어 이름은 로트 해제예요"를 판정이 통과시켰다 → 코드가 막는다."""
    line = "Release — 표준어: 해제 · 쓰지 않는 말: —"
    outs = iter([{"answer": "로트 해제의 영어 이름은 로트 해제예요."}, {"answer": "해제는 영어로 {{1}}예요."},
                 {"faithful": True, "problem": ""}])
    monkeypatch.setattr(FU2, "chat_json", lambda *a, **k: next(outs))
    written, traces = FU2.write_doc_answer("로트 해제 영어 이름?", [line])
    assert written == "해제는 영어로 Release예요."
    assert traces[0]["rejected"][0]["reason"].startswith("영어 이름을 묻는데")
    assert FU2.ENGLISH_Q_V13.search("이송 속도 영어로 뭐라고 해") and not FU2.ENGLISH_Q_V13.search("영어 교육 일정")


@pytest.mark.parametrize("q, lines, want", [
    ("이송 속도 영어로 뭐라고 해", [FEED_LINE], "이송 속도의 영어 이름은 Feed Rate입니다."),
    ("로트 해제 영어 이름?", ["Release — 표준어: 해제 · 쓰지 않는 말: —"], "해제의 영어 이름은 Release입니다."),
    ("MTBF 영어 이름이 뭐야", ["MTBF — 표준어: 평균 고장 간격(MTBF) · 쓰지 않는 말: —"], None),        # 질문에 표준어가 없음
    ("평균 고장 간격 영어로?", ["MTBF — 표준어: 평균 고장 간격(MTBF) · 쓰지 않는 말: —"], "평균 고장 간격의 영어 이름은 MTBF입니다."),
    ("이송 속도 영어로 뭐라고 해", [FEED_LINE, "Feed — 표준어: 이송 · 쓰지 않는 말: 피드"], "이송 속도의 영어 이름은 Feed Rate입니다."),  # 긴 쪽
    ("이송 속도 표준어 뭐야", [FEED_LINE], None),                                                     # 영어 이름 질문이 아님
])
def test_english_template_v13(term_on, q, lines, want):
    cites = [{"doc_id": "GLOSSARY", "section": "4"}] * len(lines)
    assert A.english_template_v13(q, lines, cites) == want


def test_english_template_needs_glossary_only_and_switch(term_on):
    assert A.english_template_v13("이송 속도 영어로 뭐라고 해", [FEED_LINE, "과격한 이송 속도"],
                                  [{"doc_id": "GLOSSARY"}, {"doc_id": "DOC-03"}]) is None
    term_on.setenv("TERM_V13", "0")
    assert A.english_template_v13("이송 속도 영어로 뭐라고 해", [FEED_LINE], [{"doc_id": "GLOSSARY"}]) is None


def test_gloss_only_v13(term_on):
    g = {"doc_id": "GLOSSARY", "section": "4"}
    d3 = {"doc_id": "DOC-03", "section": "2.8"}
    lines = [FEED_LINE, "과격한 이송 속도, 프로그램 오류", "★3 — 누가: 작업자"]
    assert A.gloss_only_v13("이송 속도 영어로 뭐라고 해", lines, [g, d3, d3]) == ([FEED_LINE], [g])
    assert A.gloss_only_v13("이송 속도가 너무 크면 어떻게 해?", lines, [g, d3, d3]) is None    # 용어 질문이 아님
    assert A.gloss_only_v13("이송 속도 영어로 뭐라고 해", lines[1:], [d3, d3]) is None           # 용어집 줄이 없으면 그대로
    assert A.gloss_only_v13("이송 속도 영어로 뭐라고 해", [FEED_LINE], [g]) is None              # 모두 용어집이면 그대로
    term_on.setenv("TERM_V13", "0")
    assert A.gloss_only_v13("이송 속도 영어로 뭐라고 해", lines, [g, d3, d3]) is None            # 끔 = 예전 그대로


# ── 10차 보강 (2026-10-14, 사용자 결정 "숫자 모양 전부 · 스위치 없이 바로 고침"): 동그라미 숫자·전각·로마·위첨자 ──
# 복사본 시험 "OEE 예시 PQ·GQ·RQ" 질문에서 새로 쓴 답 "PQ는 ①, GQ는 ③"이 문법·코드 검사·따로 판정을 모두 지났다.
@pytest.mark.parametrize("ch", ["①", "⑳", "⑴", "⒈", "⓪", "❶", "㈠", "㉠", "ⓐ", "Ⅰ", "ⅷ", "１", "²", "₂", "¼", "٣"])
def test_numlike_chars_detected_v14(ch):
    assert FU2.numlike_chars_v14("값은 " + ch + "예요") == {ch}


@pytest.mark.parametrize("text", ["PQ는 46개예요.", "97.8%예요.", "℃ 단위", "§4.3 참조", "가나다", "공구를 · 교체해요 — 그래요", "°C"])
def test_numlike_not_in_plain_text_v14(text):
    assert FU2.numlike_chars_v14(text) == set()


def test_check_answer_rejects_new_numlike_but_not_copied_v14():
    line = "PQ · 46개 / GQ · 45개"
    assert FU2.check_answer_v11("PQ는 ①, GQ는 ③이에요.", [line], {0}).startswith("숫자 모양 글자")
    assert FU2.check_answer_v11("PQ는 46개, GQ는 45개예요.", [line], {0}) is None
    assert FU2.check_answer_v11("순서는 ① 확인이에요.", ["① 확인 → ② 교체"], {0}) is None        # 원문 줄에 있던 글자는 새로 생긴 것이 아님
    assert FU2.check_answer_v11("순서는 ③ 확인이에요.", ["① 확인 → ② 교체"], {0}).startswith("숫자 모양 글자")
    assert FU2.check_answer_v11("OEE ① 값이에요.", ["OEE 값"], {0}, question="OEE ① 값은?") is None   # 질문에 있던 글자도 통과


def test_lead_and_unit_checks_reject_new_numlike_v14():
    assert FU2.check_lead_code_v12("PQ는 ①예요.", ["PQ · 46개"], "PQ가 뭐야?").startswith("숫자 모양 글자")
    assert FU2.check_lead_code_v12("PQ는 46개예요.", ["PQ · 46개"], "PQ가 뭐야?") is None
    assert FU2.check_unit("PQ는 ①예요.", "PQ · 46개").startswith("숫자 모양 글자")
    assert FU2.check_unit("① 확인해요.", "① 확인해요") is None
