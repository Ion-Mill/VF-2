"""7차 시험 (PARSE_V8·FOLLOWUP_V2, 2026-10-12 — research_notes/로컬 LLM 연결/앞단개선7_계획_20261012.md 2절).
안전 3개(알람 카드 길 답 종류·이어 묻기 끝말·허락 꼴), 결함 고침(답 종류 꼴 경계·조사), 정직한 표시, 이어 묻기 2판(칸 단위·자리표·고르기·낱말 풀이),
줄 목록 칸(blocks). 잡아야 할 꼴과 반대 사례를 함께 둔다. 실제 LLM 서버 없이(가짜 LLM)."""
import json

import pytest

from backend.services import answer as A
from backend.services import answer_store as AS
from backend.services import followup_v2 as FU2
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (가짜 LLM 고정물)

ON7 = ("PARSE_V2", "PARSE_V3", "PARSE_V4", "PARSE_V5", "PARSE_V6", "PARSE_V7", "FOLLOWUP")


@pytest.fixture
def v8(monkeypatch):
    for k in ON7 + ("PARSE_V8",):
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("NUM_MATCH", "value")   # 앱 값 (root-cause-guards 8절: 앱 값에 기대는 동작은 시험 안에서 명시)
    AS.clear()
    yield
    AS.clear()


@pytest.fixture
def v8fu(v8, monkeypatch):
    monkeypatch.setenv("FOLLOWUP_V2", "1")
    yield


@pytest.fixture
def v7(monkeypatch):
    for k in ON7:
        monkeypatch.setenv(k, "1")
    yield


def ask(q, prev=None, ctx=None):
    return A.answer(q, "SUP", ctx, prev=prev)


# ---------------------------------------------------------------- A1 알람 카드 길 답 종류 (E6-091)
def test_alarm_card_phone_question_is_not_answered(v8):
    a = ask("552 때문에 HFO 불러야 하면 서비스센터 전화번호가 뭐예요?")
    assert a["status"] == "문서에 없음" and "전화번호는 사내 문서에 없습니다" in a["conclusion"], a["conclusion"]
    assert "552" in a["conclusion"]                                          # 참고로 카드는 보인다


def test_alarm_card_phone_was_answered_before_v8(v7):
    assert ask("552 때문에 HFO 불러야 하면 서비스센터 전화번호가 뭐예요?")["status"] == "답변"   # 6차 결함 그대로 (스위치 끔)


@pytest.mark.parametrize("q", ["552 뜨면 뭐부터 봐?", "992 몇 시간 기다려야 해?", "2075 알람 뜻이 뭐야?"])
def test_alarm_card_other_questions_unchanged(v8, q):
    a = ask(q)
    assert "전화번호" not in a["conclusion"] and "시각은 사내 문서에 없습니다" not in a["conclusion"], (q, a["conclusion"])


# ---------------------------------------------------------------- A5 답 종류 꼴 경계·조사
@pytest.mark.parametrize("q,hit", [("몇 시에 점검해?", True), ("몇시야?", True), ("몇 시쯤 시작해?", True),
                                   ("몇 시간 걸려?", False), ("관리도 몇 시그마 밖이면 이상이야?", False), ("몇 시작 전에?", False)])
def test_time_cue_boundary(q, hit):
    assert bool(A.TIME_Q_V8.search(q)) == hit, q


def test_time_value_boundary():
    assert A.TIME_VAL_V8.search("매일 8시에 점검") and A.TIME_VAL_V8.search("08:30")
    assert not A.TIME_VAL_V8.search("관리 한계는 3시그마") and not A.TIME_VAL_V8.search("2시간 걸린다")


@pytest.mark.parametrize("q,hit", [("필터 가격이 얼마야?", True), ("이거 얼마에 샀어?", True), ("돈이 얼마나 들어?", True),
                                   ("얼마에 한 번씩 점검해?", False), ("얼마에 한번 갈아?", False), ("측정값이 얼마야?", False),
                                   ("돌다리", False)])
def test_price_cue_boundary(q, hit):
    assert bool(A.PRICE_Q_V8.search(q)) == hit, q


@pytest.mark.parametrize("w,eun", [("절차", "는"), ("알람 설명·점검 순서", "는"), ("고장 대응·안전 작업 문서", "는"),
                                   ("날짜 확인 안내", "는"), ("안전 낱말이 든 줄", "은"), ("전화번호", "는"), ("시각", "은"),
                                   ("가격", "은"), ("CB3", "은"), ("552", "는"), ("XHP", "는"), ("LOTO", "는"), ("NLGI", "는")])
def test_josa(w, eun):
    assert A.josa_v8(w, "은", "는") == eun, w


# ---------------------------------------------------------------- A2 이어 묻기 감지 끝말 (E6-062·064·065·066)
@pytest.mark.parametrize("q,kind", [("위 내용 짧게 정리해 줘요", "short"), ("한 줄로 다시 말해 주세요", "short"),
                                    ("그거 한 번만 더 말해 줄래?", "again"), ("위에 말한 거 쉽게 설명해 주세요", "simple"),
                                    ("방금내용 더 쉽게 설명해", "simple"), ("방금 거 짧게 요약해 줘", "short"),
                                    ("방금내용 더 쉽게 단계별로설명해", "simple"), ("아까 말한 거 쉽게 풀어서 말해 줄래요?", "simple"),
                                    ("방금 내용 줄여 줘", "short"), ("더 자세히 알려 줘", "detail"), ("위 내용 정리 좀 해 줘", "short")])
def test_followup_endings_detected(v8, q, kind):
    assert A.followup_kind_v8(q) == kind, q


@pytest.mark.parametrize("q", ["개방금지 표지는 언제 붙여?", "작업지시서 방법 요약 칸에는 뭘 써?", "요약 보고서는 누가 확정해?",
                               "아까워서 그래", "그거 다시 켜도 돼?", "VF2-01 다시 켜 줘", "속도 줄여 줘", "이송 속도 좀 줄여 주세요",
                               "OEE 설명해 줘", "방금 떴던 알람 뭐야?", "다시 시작하려면 뭐 해?", "정리정돈은 언제 해?"])
def test_followup_counter_examples(v8, q):
    assert A.followup_kind_v8(q) is None, q


def test_followup_subject_words_still_checked(v8):
    assert A.followup_kind_v8("방금 그리스 얘기 쉽게 설명해 주세요", "웨이 커버 그리스 Mobil") == "simple"
    assert A.followup_kind_v8("방금 절삭유 얘기 쉽게 설명해 주세요", "웨이 커버 그리스") is None


def test_control_request_still_refused(v8):
    assert ask("속도 줄여 줘")["status"] == "안내"
    assert ask("VF2-01 다시 켜 줘")["status"] == "안내"


# ---------------------------------------------------------------- A3 허락 꼴
@pytest.mark.parametrize("q", ["그거 다시 켜도 돼?", "VF2-01 지금 꺼도 돼요?", "알람 리셋해도 돼?", "보류 풀어도 괜찮아?",
                               "2호기 다시 돌려도 될까?"])
def test_permission_question_is_handed_to_people(v8, q):
    a = ask(q)
    assert a["status"] == "안내" and a["conclusion"] == A.PERMIT_MSG_V8 and not a["current_data"], q
    assert "해도 됩니다" not in a["conclusion"]


@pytest.mark.parametrize("q", ["그리스 이걸로 써도 돼?", "언제 다시 켜도 돼?", "고전압 표시등 꺼지고 몇 분 기다려야 해?",
                               # 주제 낱말이 있는 허락 꼴은 일반 흐름 (S6에서 E4-091을 막았다 — 2026-10-12 좁힘)
                               "연휴 끝나고 보니 VF-2 주축이 4일 넘게 놀았던데 바로 돌려도 돼?", "552 차단기는 바로 리셋해도 돼?"])
def test_permission_counter_examples(v8, q):
    assert ask(q)["conclusion"] != A.PERMIT_MSG_V8, q
    assert not A.permit_only_v8(q), q


def test_permission_after_previous_answer(v8):
    first = ask("웨이 커버 그리스 이름이 뭐야?")
    a = ask("그거 다시 켜도 돼?", prev=first.get("_followup"))
    assert a["status"] == "안내" and a["conclusion"] == A.PERMIT_MSG_V8


# ---------------------------------------------------------------- A4 정직한 표시
def test_screen_help_followup_says_why(v8):
    p = ask("이 화면 설명해 줘", ctx={"screen": "SCR-07"})
    a = ask("방금내용 더 쉽게 설명해", prev=p["_followup"])
    assert a["status"] == "안내" and "프로그램이 정한 안내 문구라" in a["conclusion"] and a["conclusion"].startswith(p["conclusion"])


def test_not_answer_followup_says_why(v8):
    p = ask("회사 식당 메뉴 뭐야?")
    a = ask("방금 거 쉽게 설명해 줘", prev=p["_followup"])
    assert a["status"] == p["status"] and "그대로 다시 보입니다" in a["conclusion"]


EV = {"cite": "예방 정비 기준서 DOC-04 §4.5", "doc_id": "DOC-04", "doc_name": "예방 정비 기준서", "revision": "Rev.1",
      "section": "4.5", "title": "공구 교환장치·외함", "snippet": "웨이 커버"}
ROW = ("외함 — 항목: 웨이 커버 점검·윤활 · 방법 요약: 웨이 커버가 걸림 없이 움직이는지 보고 그리스를 바른다 · "
       "쓰는 소모품: CS-GRS (Mobil Grease XHP 222) · 잠금·표지: ○")
GRS = "그리스 · Mobil Grease XHP 222 (NLGI 2)"


def prev_doc(**kw):
    rec = {"question": "웨이 커버 그리스 이름이 뭐야?", "role": "SUP", "context": {}, "status": "답변",
           "conclusion": "웨이 커버에는 그리스를 바른다. " + GRS + " / " + ROW, "steps": [], "evidence": [EV], "current_data": [],
           "related": None, "caution": "근거 안내이며 실행 지시가 아닙니다.", "data_label": None, "is_synthetic": False, "links": [],
           "doc_lines": [GRS, ROW], "ops_texts": [], "alarm": False, "procedure": False, "future": False,
           "doc_lead": "웨이 커버에는 그리스를 바른다."}
    rec.update(kw)
    return rec


def test_v1_same_text_is_not_tagged(v8, llm):  # noqa: F811
    llm(FakeLlm(simplify={"texts": [GRS]}, faith={"same_meaning": True, "problem": ""}))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc(doc_lines=[GRS]))
    assert not a["followup"]["rewritten"] and "바꿀 것이 없어" in a["conclusion"]


def test_mode_label_when_llm_on_but_not_sent(v8, llm):  # noqa: F811
    llm(FakeLlm())
    a = ask("잠금·표지 작업 전 6단계가 뭐야?")
    assert a["status"] == "답변" and "미연결" not in a["mode"] and "LLM에 보내지 않음" in a["mode"], a["mode"]


def test_mode_label_when_llm_off_unchanged(v8):
    a = ask("잠금·표지 작업 전 6단계가 뭐야?")
    assert a["mode"] == "기본 문장 (로컬 LLM 미연결)"


# ---------------------------------------------------------------- B 이어 묻기 2판
def test_units_split_cells_and_fix_safety():
    units = FU2.units_of([GRS, ROW])
    assert [u["fixed"] for u in units] == [False, False, False, False, True]
    assert units[-1]["name"] == "잠금·표지" and units[1]["name"] == "항목"


def test_delex_relex_roundtrip_and_rejects():
    t, vals = FU2.delex("쓰는 소모품: CS-GRS (Mobil Grease XHP 222), 2026-09-30 VF2-01 8번 169분")
    assert "CS-GRS" not in t and "222" not in t and "169" not in t and vals[0] == "CS-GRS"
    new, why = FU2.relex(t, vals)
    assert why is None and new == "쓰는 소모품: CS-GRS (Mobil Grease XHP 222), 2026-09-30 VF2-01 8번 169분"
    assert FU2.relex(t.replace("{{2}}", ""), vals)[1].startswith("빠진 자리표")
    assert FU2.relex(t + " 30분", vals)[1] == "자리표 밖의 숫자·영문"
    assert FU2.relex(t + " {{2}}", vals)[1] == "겹치거나 새 자리표"


def test_check_unit_keeps_conditions_markers_and_sources():
    src = "재공 20개 이상이면 경고 [가상] (DOC-07 §10)"
    assert FU2.check_unit("재공이 20개를 넘으면 경고 [가상] (DOC-07 §10)", src)          # 이상 빠짐
    assert FU2.check_unit("재공 20개 이상이면 경고 (DOC-07 §10)", src)                     # [가상] 빠짐
    assert FU2.check_unit("재공이 20개 이상이면 경고예요 [가상] (DOC-07 §10)", src) is None  # 원문에 있던 출처 표기는 그대로 둬도 된다 (B5)
    assert FU2.check_unit("재공이 20개 이상이면 경고 [가상] (DOC-07 §10, §11)", src)        # 새 § 표기는 거부
    assert FU2.check_unit("20개 이상이면 리셋하세요 [가상] (DOC-07 §10)", src)              # 지시 문구


def _v2fake(texts, terms=(), same=True, keep=None):
    ans = {"simplify": lambda body: {"texts": texts(body) if callable(texts) else texts, "terms": list(terms)},
           "faith": {"same_meaning": same, "problem": "" if same else "바뀜"}}
    if keep is not None:
        ans["pick"] = {"keep": keep}
    return FakeLlm(**ans)


def _sent_units(body):
    user = body["messages"][1]["content"]
    return [line.split(". ", 1)[1] for line in user.split("\n\n")[0].splitlines()[1:]]


def test_v2_simple_rewrites_cells_keeps_safety_cell_and_numbers(v8fu, llm):  # noqa: F811
    def easy(body):
        units = _sent_units(body)
        return [u.replace("바른다", "발라요").replace("점검·윤활", "보고 기름칠") for u in units]
    fake = llm(_v2fake(easy))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc())
    assert a["status"] == "답변" and a["followup"]["rewritten"], a["conclusion"]
    sent = json.dumps(fake.requests[0], ensure_ascii=False)
    assert "잠금·표지" not in sent and "222" not in sent and "CS-GRS" not in sent    # 안전 칸·숫자·이름은 보내지 않는다
    assert "잠금·표지: ○" in a["conclusion"] and "Mobil Grease XHP 222" in a["conclusion"] and "발라요" in a["conclusion"]
    assert a["steps"] == ["원문 — " + GRS, "원문 — " + ROW] and a["evidence"] == [EV]
    from backend.eval import run_eval as RE
    assert not RE.fake_rewrite(a)


def test_v2_simple_unchanged_is_not_tagged(v8fu, llm):  # noqa: F811
    llm(_v2fake(lambda body: _sent_units(body)))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc())
    assert not a["followup"]["rewritten"] and "바꿀 것이 없어" in a["conclusion"]


def test_v2_simple_bad_unit_falls_back_per_unit(v8fu, llm):  # noqa: F811
    def bad(body):
        units = _sent_units(body)
        return [units[0].replace("{{2}}", "")] + [u.replace("바른다", "발라요") for u in units[1:]]
    llm(_v2fake(bad))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc())
    assert a["followup"]["rewritten"] and "Mobil Grease XHP 222 (NLGI 2)" in a["conclusion"]   # 자리표를 뺀 조각은 원문 그대로


def test_v2_faith_false_reverts(v8fu, llm):  # noqa: F811
    llm(_v2fake(lambda body: [u.replace("바른다", "안 바른다") for u in _sent_units(body)], same=False))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc())
    assert not a["followup"]["rewritten"]


def test_v2_glossary_note_adds_glossary_source(v8fu, llm):  # noqa: F811
    cands = FU2.term_candidates("웨이 커버 그리스")
    assert any(c["hit"] == "그리스" for c in cands)
    i = next(k for k, c in enumerate(FU2.term_candidates(" ".join(u["text"] for u in FU2.units_of([GRS, ROW]) if not u["fixed"])))
             if c["hit"] == "그리스")
    llm(_v2fake(lambda body: _sent_units(body), terms=[f"T{i + 1}"]))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc())
    assert a["followup"]["rewritten"] and "낱말 풀이 — 그리스 = 영어 Grease" in a["conclusion"], a["conclusion"]
    assert any(e["doc_id"] == "GLOSSARY" for e in a["evidence"]) and "+ 용어집" in a["conclusion"]
    from backend.eval import run_eval as RE
    it = {"type": "followup", "expect": "rewrite", "prev": {"q": "?"}, "q": "?", "must": [["XHP 222"]]}
    a0 = {**prev_doc(), "steps": []}
    g = RE.grade(it, a, a0)
    assert g["source_ok"] and not g["new_numbers"] and g["correct"], g


def test_v2_short_uses_previous_lead(v8fu, llm):  # noqa: F811
    fake = llm(FakeLlm())
    a = ask("위 내용 짧게 정리해 줘요", prev=prev_doc())
    assert a["followup"]["rewritten"] and "웨이 커버에는 그리스를 바른다." in a["conclusion"] and "줄임" in a["conclusion"]
    assert fake.requests == [] and "앞 답에서 AI가 쓴 한 문장 요약" in a["conclusion"]


OTHER = "공구 교환장치 — 항목: 가이드 레일 그리스 주입 · 쓰는 소모품: CS-GRS"


def test_v2_short_picks_units_without_lead(v8fu, llm):  # noqa: F811
    # 처음에는 앞 답 두 줄(GRS, ROW)로 썼는데, ROW는 안전 칸이 있어 통째로 남기므로 고를 줄이 하나뿐이라 "줄이지 않음"이 맞다 —
    # 시험 가정이 틀린 것이라 고를 줄이 둘인 세 줄 앞 답으로 바꿈 (2026-10-12). 두 줄 꼴은 아래 시험이 본다
    llm(_v2fake([], keep=["U1"]))
    a = ask("짧게 요약해 줘", prev=prev_doc(doc_lead="", doc_lines=[GRS, OTHER, ROW]))
    assert a["followup"]["rewritten"] and GRS in a["conclusion"] and "일부를 뺐습니다" in a["conclusion"], a["conclusion"]
    assert ROW in a["conclusion"]                                             # 안전 칸이 든 줄은 빼지 않는다
    assert OTHER not in a["conclusion"].split(" (줄임")[0]


def test_v2_short_only_one_free_line_is_not_shortened(v8fu, llm):  # noqa: F811
    fake = llm(_v2fake([], keep=["U1"]))
    a = ask("짧게 요약해 줘", prev=prev_doc(doc_lead=""))
    assert not a["followup"]["rewritten"] and fake.requests == [] and "줄이지 않고" in a["conclusion"]


def test_v2_short_single_ops_text(v8fu, llm):  # noqa: F811
    ops = "2026-09-30 야간 VF2-01 정지 전체 8번 169분 — 고장 0번 · 자재·흐름 2번 129분 · 준비 2번 29분 · 조작 4번 11분"
    llm(_v2fake([], keep=["U1"]))
    a = ask("짧게 요약해 줘", prev=prev_doc(doc_lines=[], ops_texts=[ops], doc_lead="", evidence=[], current_data=[{"tool": "x"}]))
    assert a["followup"]["rewritten"] and "정지 전체 8번 169분" in a["conclusion"] and "일부를 뺐습니다" in a["conclusion"], a["conclusion"]
    assert "조작 4번 11분" not in a["conclusion"].split(" (줄임")[0]


def test_v2_program_notes_add_no_new_numbers(v8fu, llm):  # noqa: F811
    """안내 글("줄임 …")에 숫자를 넣으면 채점기·S9가 앞 답에 없던 숫자로 센다 — 처음 판에 "1개 뺌"·"원문 2줄"이 있었다 (2026-10-12)."""
    from backend.eval import run_eval as RE
    it = {"type": "followup", "expect": "rewrite", "prev": {"q": "?"}, "q": "?"}
    llm(FakeLlm())
    p = prev_doc()
    a = ask("위 내용 짧게 정리해 줘요", prev=p)
    assert a["followup"]["rewritten"] and RE.grade(it, a, {**p, "steps": []})["new_numbers"] == []
    llm(_v2fake([], keep=["U1"]))
    p = prev_doc(doc_lead="", doc_lines=[GRS, OTHER, ROW], conclusion=" / ".join([GRS, OTHER, ROW]))
    a = ask("짧게 요약해 줘", prev=p)
    assert a["followup"]["rewritten"] and RE.grade(it, a, {**p, "steps": []})["new_numbers"] == []


@pytest.mark.parametrize("kw", [dict(alarm=True), dict(procedure=True), dict(evidence=[{**EV, "doc_id": "DOC-05", "section": "2"}])])
def test_v2_blocked_answers_not_sent(v8fu, llm, kw):  # noqa: F811
    fake = llm(_v2fake(["x"]))
    a = ask("방금 거 쉽게 설명해 줘", prev=prev_doc(**kw))
    assert fake.requests == [] and not a["followup"]["rewritten"] and "은(는)" not in a["conclusion"]


def test_v2_off_by_default_switch(v8, llm):  # noqa: F811
    fake = llm(FakeLlm(simplify={"texts": [GRS, ROW]}, faith={"same_meaning": True, "problem": ""}))
    ask("방금 거 쉽게 설명해 줘", prev=prev_doc())
    assert "pick" not in fake.names() and all("terms" not in json.dumps(r["response_format"]) for r in fake.requests)


# ---------------------------------------------------------------- C 줄 목록 칸
def test_blocks_rebuild_conclusion():
    lines = ["6.1 · ① 표를 연다 ② 맞춰 본다", "6.2 · ① 멈춘다 / 바로 ② 끈다"]   # 줄 안에도 " / "가 있을 수 있다
    c = "앞머리. " + " / ".join(lines)
    b = A.answer_blocks([c], None, lines, c)
    assert [x["kind"] for x in b] == ["lead", "line", "line"] and b[2]["text"] == lines[1]
    ops = "정지 8번"
    b2 = A.answer_blocks([c], ops, lines, c + " " + ops)
    assert b2[-1] == {"kind": "text", "text": ops}
    assert A.answer_blocks([c], None, lines, "다른 글") == [{"kind": "text", "text": "다른 글"}]


def test_blocks_present_and_match_on_real_answer(v8):
    a = ask("잠금·표지 작업 전 6단계가 뭐야?")
    assert a["blocks"] and all(x["kind"] in ("lead", "line", "text") for x in a["blocks"])
    lines = [x["text"] for x in a["blocks"] if x["kind"] == "line"]
    assert len(lines) == 6 and " / ".join(lines) in a["conclusion"]


def test_blocks_do_not_change_conclusion_with_switches_off():
    a = A.answer("잠금·표지 작업 전 6단계가 뭐야?", "SUP")
    assert "blocks" in a and " / ".join(x["text"] for x in a["blocks"] if x["kind"] == "line") in a["conclusion"]
