"""화면 알람 이어받기(CTX_NARROW)와 비서 서비스의 앞 답 보관(이어 묻기) 시험 (2026-10-18). 실제 LLM·네트워크·DB를 부르지 않는다.

문제: 화면이 직전 답의 알람 번호를 alarm_key로 보내면 예전 규칙은 "원인·점검·먼저·안전·뭐부터" 낱말만 보고 직전 알람에 묶어서
"안전하게 자물쇠 제거 어떻게 해?"까지 2075 카드로 답할 수 있었다. 또 비서 서비스가 앞 답(prev)을 받지 않아 이어 묻기가 동작하지 않았다.
지키는 것:
① 자기 대상이 없는 질문("원인은?"·"원인이뭐야"·"뭐부터봐?")만 이어받고 ② 자기 대상이 있는 질문·과거 지시어("아까 …")·이어 묻기 문장은 안 이어받는다
③ CTX_NARROW=0이면 예전 규칙 그대로 ④ 이어받으면 답 맨 앞에 "N 알람 기준으로 답해요."를 밝히고, 안 이어받으면 없다
⑤ 앞 답 보관: 사용자별 하나, 30분, 새 대화 신호(context.new_chat)로 지움, 화면·백엔드로 안 나감.
"""
import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend import config as C
from backend.config import settings
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import pure_external as PURE

FLAGS = {"PARSE_V2": "1", "PARSE_V3": "1", "CTX_NARROW": "1"}


@pytest.fixture
def narrow(monkeypatch):
    for k, v in FLAGS.items():
        monkeypatch.setenv(k, v)
    with EXT.external_request("claude"):
        yield


def subjectless(q):
    return A.ctx_subjectless(q, A.parse(q))


# ---------------------------------------------------------------- ① 대상 없는 질문은 이어받는다
CARRY = ["원인은?", "원인이뭐야", "그럼 뭐부터 봐?", "뭐부터봐?", "심각도는?", "누가 해야 돼?", "누가해야돼?", "점검 순서 알려줘", "점검순서는?",
         "또 뜨면 어떡해?", "얼마나 급해?", "원인부터 알려줘", "재발 방지는?", "시간 얼마나 걸려?", "바로 재가동해도 돼?", "방금 그 알람 누가 처리해?",
         "그건 작업자가 해도 돼?", "당장 세워야 돼?", "어떻게 대응하면 될까요?", "반복되면 어떻게 돼?"]


@pytest.mark.parametrize("q", CARRY)
def test_subjectless_questions_are_carried(narrow, q):
    assert subjectless(q), q


# ---------------------------------------------------------------- ② 자기 대상이 있으면 안 이어받는다
OWN_SUBJECT = ["안전하게 자물쇠 제거 어떻게 해?", "사람이 없는데 자물쇠 제거 어떻게헤", "정비 전에 먼저 뭘 차단해야 해?", "점검표는 어디서 봐?",
               "VF2-01 워밍업 먼저 해야 돼?", "OEE 원인 분석 어떻게 해?", "992는 왜 떠?", "재고 점검은 언제 해?", "구성인선 원인이 뭐야?",
               "잠금 표지 순서가 어떻게 돼?", "쿨런트 교체 먼저 하는 이유가 뭐야?", "점검 주기는 어디에 나와?", "로트 보류하면 누가 풀어?", "병목 원인이 뭐야?"]


@pytest.mark.parametrize("q", OWN_SUBJECT)
def test_questions_with_their_own_subject_are_not_carried(narrow, q):
    assert not subjectless(q), q


@pytest.mark.parametrize("q", ["아까 알람 원인은?", "전에 뜬 그거 원인은?", "어제 그 알람 뭐였지?", "저번에 나온 알람 점검 순서 알려줘"])
def test_past_references_are_not_carried_they_are_asked_back(narrow, q):
    assert not subjectless(q), q


@pytest.mark.parametrize("q", ["방금 내용 쉽게 설명해", "요약해 줘", "한 번 더 말해 줘", "그거 쉽게 설명해 줘"])
def test_follow_up_phrasing_is_not_an_alarm_carry(narrow, q):
    s = settings()
    assert A._ctx_use_v2(q, A.parse(q), s, {}) is None            # 이어 묻기 길이 처리한다 — "N 알람 기준" 안내가 붙지 않게


# ---------------------------------------------------------------- ③ 스위치를 끄면 예전 규칙 그대로
def test_switch_off_keeps_the_old_rule(monkeypatch):
    for k in ("PARSE_V2", "PARSE_V3"):
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("CTX_NARROW", "0")
    s = settings()
    assert not s.ctx_narrow
    for q, expect in [("안전하게 자물쇠 제거 어떻게 해?", True), ("원인은?", True), ("심각도는?", False), ("방금 그 알람 누가 처리해?", False)]:
        assert bool(A._ctx_use_v2(q, A.parse(q), s, {})) is expect, q     # 옛 규칙: 낱말(뭐부터·먼저·점검·원인·안전)만 본다


def test_switch_default_is_off_and_reads_clean(monkeypatch):
    monkeypatch.delenv("CTX_NARROW", raising=False)
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    assert settings().ctx_narrow is False
    monkeypatch.setenv("CTX_NARROW", "1")
    assert settings().ctx_narrow is True


# ---------------------------------------------------------------- ④ 답: 이어받았을 때만 "N 알람 기준으로 답해요."
def test_carried_answer_says_which_alarm_it_is_about(narrow):
    a = A.answer("원인은?", "OPR", {"alarm_key": "2075"})
    assert a["status"] == "답변"
    assert a["conclusion"].startswith("2075 알람 기준으로 답해요."), a["conclusion"][:60]
    assert any(e["doc_id"] in ("DOC-02", "DOC-03") for e in a["evidence"]), a["evidence"]


def test_not_carried_answer_has_no_note(narrow):
    a = A.answer("안전하게 자물쇠 제거 어떻게 해?", "OPR", {"alarm_key": "2075"})
    assert "알람 기준으로 답해요" not in (a.get("conclusion") or "")
    assert "2075" not in (a.get("conclusion") or "")


def test_explicit_this_alarm_is_the_old_behaviour_without_a_note(narrow):
    a = A.answer("이 알람 뭐야?", "OPR", {"alarm_key": "2075"})
    assert "알람 기준으로 답해요" not in (a.get("conclusion") or "")        # 사용자가 "이 알람"이라고 말했으니 안내는 군더더기


def test_unknown_alarm_key_does_not_get_a_note(narrow):
    a = A.answer("원인은?", "OPR", {"alarm_key": "99999"})
    assert "알람 기준으로 답해요" not in (a.get("conclusion") or "")


# ---------------------------------------------------------------- ⑤ 비서 서비스의 앞 답 보관
KEY = "test-service-key"
H = {"X-Service-Key": KEY}
client = TestClient(CS.app)


def body(q, user="U01", **ctx):
    return {"question": q, "context": ctx, "allowed_tools": [], "out_of_role": [], "history": [], "user": {"user_id": user, "role_code": "OPR"}}


@pytest.fixture
def svc(monkeypatch):
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    monkeypatch.setenv("MOM_ASSISTANT_KEY", KEY)
    monkeypatch.delenv("ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("FOLLOWUP", "1")
    CS._prev.clear()
    yield
    CS._prev.clear()


@pytest.mark.own_backend
def test_previous_answer_is_kept_per_user_and_never_leaves_the_service(svc):
    j = client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H).json()
    assert set(j) == {"answer", "sources", "related", "status"}          # _followup 기록이 밖으로 나가지 않는다
    assert "U01" in CS._prev and "U02" not in CS._prev
    r = client.post("/chat", json=body("그거 다시 말해 줘"), headers=H).json()
    assert "절삭유" in r["answer"], r["answer"]                            # 앞 답이 이어졌다
    other = client.post("/chat", json=body("그거 다시 말해 줘", user="U02"), headers=H).json()
    assert "절삭유" not in other["answer"] and "이어받지 못" in other["answer"], other["answer"]   # 다른 사용자는 못 이어받는다


@pytest.mark.own_backend
def test_new_chat_signal_forgets_the_previous_answer(svc):
    client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H)
    r = client.post("/chat", json=body("그거 다시 말해 줘", new_chat="1"), headers=H).json()
    assert "이어받지 못" in r["answer"] and "절삭유" not in r["answer"]


@pytest.mark.own_backend
def test_previous_answer_expires_after_the_time_limit(svc, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(CS, "_now", lambda: now[0])
    client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H)
    now[0] += CS.PREV_TTL_S - 1
    assert CS._prev_take("U01", False) is not None
    now[0] += 2
    assert CS._prev_take("U01", False) is None and "U01" not in CS._prev


@pytest.mark.own_backend
def test_followup_switch_off_keeps_nothing(svc, monkeypatch):
    monkeypatch.setenv("FOLLOWUP", "0")
    client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H)
    assert CS._prev == {}


@pytest.mark.own_backend
def test_store_is_capped(svc, monkeypatch):
    monkeypatch.setattr(CS, "PREV_MAX_USERS", 3)
    for i in range(5):
        CS._prev_keep(f"U{i}", {"n": i})
    assert len(CS._prev) == 3 and "U4" in CS._prev and "U0" not in CS._prev


@pytest.mark.own_backend
def test_new_chat_is_an_accepted_context_key():
    assert "new_chat" in CS.CONTEXT_KEYS and CS._context({"new_chat": "1", "x": "y"}) == {"new_chat": "1"}


# ---------------------------------------------------------------- ⑥ 순수 길(Claude가 쓴) 답의 이어 묻기는 원문 줄을 바꿔 쓰지 않는다
@pytest.mark.own_backend
def test_pure_route_answer_follow_up_returns_the_answer_not_rewritten_source_lines(svc, monkeypatch):
    """옛 이어 묻기는 앞 답의 근거 원문 줄(doc_lines)을 바꿔 썼다. 순수 길 답은 Claude가 쓴 글이라, 그대로 쓰면 "쉽게 설명해줘"에
    답과 무관한 용어집 줄이 나왔다(2026-10-18 진짜 Claude로 발견). 지금은 앞 답을 그대로 보이고 Claude를 더 부르지 않는다."""
    from backend.llm import claude_client as CC
    from backend.tests.test_pure_expand import APP_FLAGS, Runner
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    runner = Runner()
    CC.use_runner(runner)
    try:
        j1 = client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H).json()
        assert "답이에요" in j1["answer"], j1                      # 가짜 Claude의 답 — 순수 길로 갔다
        assert CS._prev["U01"][1].get("pure") is True               # 보관 기록에 순수 길 표시
        calls = len(runner.calls)
        j2 = client.post("/chat", json=body("방금 내용 쉽게 설명해줘"), headers=H).json()
        assert "다시 바꿔 쓰지 않고 그대로" in j2["answer"] and "답이에요" in j2["answer"], j2["answer"]
        assert "Axis Lubrication" not in j2["answer"] and "표준어" not in j2["answer"]    # 엉뚱한 원문 줄이 나오지 않는다
        assert len(runner.calls) == calls                           # 이어 묻기에서 Claude를 더 부르지 않았다
    finally:
        CC.use_runner(None)


# ---------------------------------------------------------------- ⑦ 순수 길 답의 "쉽게/짧게"를 실제로 다시 쓴다 (PURE_FOLLOW_REWRITE=1)
import json
import re
from types import SimpleNamespace

SONNET = "claude-sonnet-5-5"
SAFE_LINE = "잠금·표지를 건 뒤에 작업해요."
ITEM_A, ITEM_B, ITEM_C = "교체 주기는 3개월이에요.", "농도는 3%로 맞춰요.", "수위는 매 교대 확인해요."
ITEM_D = "지난달에는 두 번 바꿨어요."
FIRST_ANSWER = {"sections": [{"title": "", "text": "쿨런트는 절삭유예요.", "items": []},
                             {"title": "보충 규칙", "text": "", "items": [ITEM_A, ITEM_B, ITEM_C, SAFE_LINE]},
                             {"title": "알아둘 점", "text": "", "items": [ITEM_D]}],
                "cited": ["C1"], "insufficient": False}


class RewriteRunner:
    """처음 질문 → 순수 길 답(구조 있는 답). 이어 묻기 → 조각 다시 쓰기("texts"+"terms"), 남길 조각 고르기("keep"), 뜻 판정(same_meaning)"""

    def __init__(self, mode="good"):
        self.mode, self.calls = mode, []

    def __call__(self, cmd, stdin_text, timeout):
        sch = json.loads(cmd[cmd.index("--json-schema") + 1])
        props = tuple(sorted((sch.get("properties") or {}).keys()))
        self.calls.append((props, stdin_text))
        if "sections" in props:
            so = FIRST_ANSWER
        elif props == ("terms", "texts"):
            segs = re.findall(r"^\d+\. (.*)$", stdin_text, re.M)
            out = ["쉽게 말해, " + s for s in segs]
            if self.mode == "bad_number":   # 자리표를 바꿔 버린다 = 숫자를 새로 만든 것 → 그 조각은 원문 그대로여야 한다
                out = [re.sub(r"\{\{\d+\}\}", "{{9}}", s) for s in out]
            so = {"texts": out, "terms": []}
        elif props == ("keep",):
            so = {"keep": ["U1"]}
        else:
            so = {"same_meaning": self.mode != "faith_no", "problem": "" if self.mode != "faith_no" else "시험: 뜻이 다름"}
        res = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 100, "duration_api_ms": 80, "num_turns": 1,
               "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
               "modelUsage": {SONNET: {"inputTokens": 10}}, "structured_output": so}
        return SimpleNamespace(returncode=0, stdout=json.dumps(res, ensure_ascii=False), stderr="")


@pytest.fixture
def pure_follow(svc, monkeypatch):
    from backend.llm import claude_client as CC
    from backend.tests.test_pure_expand import APP_FLAGS
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("PURE_STYLE", "1")
    monkeypatch.setenv("PURE_LAYOUT", "1")
    monkeypatch.setenv("PURE_FOLLOW_REWRITE", "1")
    yield
    CC.use_runner(None)


def first_then(runner, followup):
    from backend.llm import claude_client as CC
    CC.use_runner(runner)
    j1 = client.post("/chat", json=body("쿨런트가 뭐야?"), headers=H).json()
    assert "절삭유예요" in j1["answer"] and "3개월" in j1["answer"], j1          # 순수 길 구조 답
    assert CS._prev["U01"][1].get("pure") is True and CS._prev["U01"][1].get("blocks"), "보관 기록에 순수 길 표시와 블록이 있어야 한다"
    calls = len(runner.calls)
    return j1, client.post("/chat", json=body(followup), headers=H).json(), calls


@pytest.mark.own_backend
def test_easy_follow_up_really_rewrites_and_the_safety_line_stays_verbatim(pure_follow):
    r = RewriteRunner("good")
    j1, j2, calls = first_then(r, "방금 내용 쉽게 설명해줘")
    a = j2["answer"]
    assert "쉬운 말로 다시 쓴 글입니다" in a, a
    assert "쉽게 말해, 쿨런트는 절삭유예요." in a, a                                                      # 첫 문장도 쉬운 조각에 든다(첫 문장을 고정하는 것은 "짧게"일 때만)
    assert "쉽게 말해, " + ITEM_A in a and "쉽게 말해, " + ITEM_B in a, a                                   # 글이 실제로 다시 쓰였고 숫자(3개월·3%)는 그대로
    assert SAFE_LINE in a and "쉽게 말해, " + SAFE_LINE not in a, a                                       # 안전 낱말(잠금·표지)이 든 줄은 원문 그대로
    assert all(SAFE_LINE not in c[1] for c in r.calls[calls:]), "안전 줄이 다시 쓰기 요청에 실려 나갔다"
    assert "보충 규칙" in a and "다시 바꿔 쓰지 않고 그대로" not in a                                     # 소제목은 그대로, 옛 "그대로" 안내는 없다
    assert [c[0] for c in r.calls[calls:]] == [("terms", "texts"), ("problem", "same_meaning")]            # 다시 쓰기 1번 + 뜻 판정 1번


@pytest.mark.own_backend
def test_short_follow_up_keeps_the_first_sentence_and_safety_line_and_drops_the_rest(pure_follow):
    r = RewriteRunner("good")
    j1, j2, calls = first_then(r, "방금 내용 짧게 줄여줘")
    a = j2["answer"]
    assert "짧게 줄인 글입니다" in a, a
    assert "쿨런트는 절삭유예요." in a and ITEM_A in a and SAFE_LINE in a, a                              # 첫 문장·고른 조각·안전 줄은 남고
    assert ITEM_B not in a and ITEM_C not in a and ITEM_D not in a, a                                      # 나머지는 빠졌다
    assert "일부를 뺐습니다" in a and "보충 규칙" in a
    assert "알아둘 점" not in a, a                                                                         # 내용이 다 빠진 소제목은 남기지 않는다
    assert [c[0] for c in r.calls[calls:]] == [("keep",)]                                                   # 고르기 1번 (글은 새로 쓰지 않는다)


@pytest.mark.own_backend
def test_a_unit_whose_number_changed_stays_as_the_original(pure_follow):
    j1, j2, calls = first_then(RewriteRunner("bad_number"), "방금 내용 쉽게 설명해줘")
    a = j2["answer"]
    assert ITEM_A in a and "쉽게 말해, " + ITEM_A not in a, a                                              # 숫자가 든 조각은 원문 그대로
    assert "쉽게 말해, 수위는 매 교대 확인해요." in a, a                                                    # 숫자 없는 조각은 다시 쓰였다


@pytest.mark.own_backend
def test_meaning_check_failure_keeps_the_previous_answer_as_is(pure_follow):
    j1, j2, calls = first_then(RewriteRunner("faith_no"), "방금 내용 쉽게 설명해줘")
    assert "다시 바꿔 쓰지 않고 그대로" in j2["answer"] and "쉽게 말해, " not in j2["answer"], j2["answer"]


@pytest.mark.own_backend
def test_switch_off_keeps_the_previous_answer_and_calls_claude_no_more(pure_follow, monkeypatch):
    monkeypatch.setenv("PURE_FOLLOW_REWRITE", "0")
    r = RewriteRunner("good")
    j1, j2, calls = first_then(r, "방금 내용 쉽게 설명해줘")
    assert "다시 바꿔 쓰지 않고 그대로" in j2["answer"] and len(r.calls) == calls


@pytest.mark.own_backend
@pytest.mark.parametrize("q,kind", [("방금 내용 짧게 줄여줘", "short"), ("방금 내용 줄여줘", "short"), ("위 내용 간단히 줄여 줘", "short"),
                                    ("스핀들 속도 짧게 줄여줘", None), ("이송 속도 줄여줘", None), ("그 알람 리셋해도 돼?", None)])
def test_short_follow_up_phrase_is_not_taken_for_an_equipment_command(pure_follow, q, kind):
    """"방금 내용 짧게 줄여줘"가 "비서는 기록·상태·설비를 바꾸지 않습니다"로 거절되던 것(조작 요청으로 오해)을 푼다. 가리키는 말이 없는 조작 말은 그대로 조작 요청이다."""
    assert A.followup_kind_v8(q, "쿨런트는 절삭유예요.") == kind, q
