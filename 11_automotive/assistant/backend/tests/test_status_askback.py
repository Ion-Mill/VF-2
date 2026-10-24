"""상태 질문에서 빈 칸만 되묻기 (2026-10-22).

설비와 종류가 둘 다 있으면 그 항목만 답한다. 하나라도 없으면 여섯 대를 펼치지 않고 되묻는다.
현재·지금은 가동이 아니다. 정비 중은 지금 하는 일이고, 정비 상태는 정비 기한이다.
재고·생산·로트·알람은 이 되묻기에 넣지 않는다. 가짜 백엔드 — 진짜 Claude·네트워크·DB를 부르지 않는다.
"""
import pytest

from backend.services import answer as A
from backend.tests.fake_backend import FakeBackend


@pytest.fixture
def v3(monkeypatch):
    for k in ("PARSE_V2", "PARSE_V3", "PARSE_V5", "PURE_EXTERNAL", "PURE_KEEP_SIGNALS", "PURE_SAFETY"):
        monkeypatch.setenv(k, "1")


def _text(a: dict) -> str:
    return " ".join(str(x) for x in (a.get("conclusion"), a.get("current_data")))


@pytest.mark.parametrize("q,part", [
    ("현재 상태는", "어느 설비인지, 가동 상태인지 정비 기한인지도"),
    ("지금 상태", "어느 설비인지, 가동 상태인지 정비 기한인지도"),
    ("상태 어때", "어느 설비인지, 가동 상태인지 정비 기한인지도"),
    ("가동 상태는", "어느 설비의 가동 상태인지"),
    ("돌아가?", "어느 설비의 가동 상태인지"),
    ("멈춰 있어?", "어느 설비의 가동 상태인지"),
    ("정비상태는", "어느 설비의 정비 기한인지"),
    ("정비 상태는?", "어느 설비의 정비 기한인지"),
    ("정비 중이야?", "어느 설비가 지금 정비 중인지"),
    ("수리 중이야?", "어느 설비가 지금 수리 중인지"),
    ("VF2-01 상태는", "VF2-01의 가동 상태인지, 정비 기한인지"),
    ("1호기 상태는", "VF2-01의 가동 상태인지, 정비 기한인지"),
    ("현재 vf2-01 상태는", "VF2-01의 가동 상태인지, 정비 기한인지"),
    ("모든 설비 상태는", "모든 설비의 가동 상태인지, 정비 기한인지"),
    ("라인 상태는", "설비 여섯 대의 가동 상태인지, 라인의 생산·OEE인지"),
    ("공장 상태는", "설비 여섯 대의 가동 상태인지, 라인의 생산·OEE인지"),
    ("OP-30 상태는", "OP-30은 VF2-01·VF2-02입니다"),
])
def test_missing_slot_asks_and_does_not_list_machines(v3, monkeypatch, q, part):
    FakeBackend().install(monkeypatch)
    a = A.answer(q, "OPR", {})
    assert a["status"] == "확인 필요" and part in a["conclusion"], q
    assert "설비 상태:" not in a["conclusion"] and a.get("current_data") == [], q


@pytest.mark.parametrize("q,absent", [
    ("재고 상태는", "정비 기한"),
    ("생산 상태는", "정비 기한"),
    ("로트 상태는", "정비 기한"),
    ("알람 상태는", "가동 상태인지"),
])
def test_other_subjects_are_not_the_equipment_ask(v3, q, absent):
    assert A.status_gap_v29(q, A.parse(q)) is None
    assert "equipment_status" not in A.parse(q)["intents"]


def test_named_maintenance_stays_off_the_live_tool(v3):
    p = A.parse("VF2-01 정비 상태는?")
    gap = A.status_gap_v29("VF2-01 정비 상태는?", p)
    assert "equipment_status" not in p["intents"]
    assert gap is not None and gap["drop_live"] and not gap["ask"]


def test_run_state_answers_only_the_named_machine(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    text = _text(A.answer("VF2-01 가동 상태", "OPR", {}))
    assert "VF2-01" in text and "RUN" in text and "VF2-02" not in text and "확인 필요" not in text


def test_all_equipment_run_state_lists_the_machines(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    text = _text(A.answer("모든 설비 가동 상태", "OPR", {}))
    assert "VF2-01" in text and "VF2-02" in text and "확인 필요" not in text


def test_process_run_state_is_only_that_process(v3, monkeypatch):
    assert A.status_gap_v29("OP-30 가동 상태는", A.parse("OP-30 가동 상태는"))["ids"] == ["VF2-01", "VF2-02"]
    FakeBackend().install(monkeypatch)
    text = _text(A.answer("OP-10 가동 상태는", "OPR", {}))
    assert "확인 필요" not in text and "VF2-01" not in text and "VF2-02" not in text


def test_named_work_in_progress_still_answers(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    text = _text(A.answer("VF2-02 지금 정비 중이야?", "OPR", {}))
    assert "설비 상태" in text and "VF2-02" in text and "VF2-01" not in text


def test_equipment_reply_continues_a_run_question(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("가동 상태는", "OPR", {})
    second = A.answer("VF2-01", "OPR", {}, prev=first["_status_ask"])
    assert "RUN" in second["conclusion"] and "VF2-02" not in second["conclusion"]
    assert second["conclusion"].endswith("앞서 물으신 '가동 상태는'을 VF2-01 기준으로 답했어요.")


def test_all_equipment_reply_continues_a_run_question(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("돌아가?", "OPR", {})
    second = A.answer("모든 설비", "OPR", {}, prev=first["_status_ask"])
    assert "VF2-01" in second["conclusion"] and "VF2-02" in second["conclusion"]


def test_kind_reply_continues_a_named_question(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("현재 vf2-01 상태는", "OPR", {})
    second = A.answer("가동 상태", "OPR", {}, prev=first["_status_ask"])
    assert "VF2-01" in second["conclusion"] and "RUN" in second["conclusion"] and "VF2-02" not in second["conclusion"]


def test_kind_reply_on_a_process_answers_those_machines(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("OP-30 상태는", "OPR", {})
    second = A.answer("가동 상태", "OPR", {}, prev=first["_status_ask"])
    assert "VF2-01" in second["conclusion"] and "VF2-02" in second["conclusion"]


def test_one_machine_after_a_process_asks_only_that_kind(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("OP-30 상태는", "OPR", {})
    second = A.answer("VF2-01", "OPR", {}, prev=first["_status_ask"])
    assert "VF2-01의 가동 상태인지, 정비 기한인지" in second["conclusion"]
    assert "VF2-02" not in second["conclusion"]
    assert "무엇을 볼까요" not in second["conclusion"]


def test_all_right_after_a_process_asks_the_kind_again(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("OP-30 상태는", "OPR", {})
    second = A.answer("전부다", "OPR", {}, prev=first["_status_ask"])
    assert "VF2-01·VF2-02" in second["conclusion"]
    assert "가동 상태인지, 정비 기한인지" in second["conclusion"]
    assert "무엇을 볼까요" not in second["conclusion"]


def test_all_after_one_machine_answers_run_and_pm(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("OP-30 상태는", "OPR", {})
    second = A.answer("VF2-01", "OPR", {}, prev=first["_status_ask"])
    third = A.answer("전부다", "OPR", {}, prev=second["_status_ask"])
    text = third["conclusion"]
    assert "VF2-01" in text and "07:12부터 48분" in text and "가이드 레일 윤활" in text
    assert "VF2-02" not in text and "무엇을 볼까요" not in text


def test_a_bare_name_does_not_continue_when_both_slots_were_missing(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("현재 상태는", "OPR", {})
    second = A.answer("VF2-01", "OPR", {}, prev=first["_status_ask"])
    assert second["status"] == "안내" and "설비 상태" not in second["conclusion"]


def test_a_bare_name_does_not_continue_a_line_question(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    first = A.answer("라인 상태는", "OPR", {})
    second = A.answer("VF2-01", "OPR", {}, prev=first["_status_ask"])
    assert second["status"] == "안내" and "여섯 대" not in second["conclusion"]


def test_status_ask_is_remembered_once_when_followup_is_off():
    from backend import chat_service as CS
    CS._status_prev.clear()
    rec = {"status": "확인 필요", "question": "가동 상태는", "conclusion": "확인 필요 — 예: VF2-01, 모든 설비."}
    CS._status_prev_keep("U01", rec)
    assert CS._status_prev_take("U01", False) == rec
    assert CS._status_prev_take("U01", False) is None


def test_period_word_yesterday_ignores_a_calendar_date():
    from backend.services import lookup_turn as LT
    start, end, _ = LT.period_window("어제 2026-10-20")
    assert start.isoformat() == "2026-09-30" and end.isoformat() == "2026-09-30"
    assert LT.period_window("2026-09-30")[:2] == (None, None)


def test_all_equipment_words_are_the_six():
    from backend.services import lookup_turn as LT
    assert LT.equipment_scope("모든설비") == list(LT.SIX)
    assert LT.equipment_scope("모든 설비") == list(LT.SIX)
    assert LT.equipment_scope("") is None
    assert LT.equipment_scope("VF2-01") == ["VF2-01"]


def test_empty_equipment_does_not_run_status_stops_or_mttr():
    from backend.services import lookup_turn as LT
    ready, blocked = LT.prepare([
        {"name": "가동상태", "equipment": "", "kind": "", "period": ""},
        {"name": "정비 기한", "equipment": "", "kind": "", "period": ""},
        {"name": "정지 횟수", "equipment": "", "kind": "", "period": "어제"},
        {"name": "MTTR", "equipment": "", "kind": "", "period": ""},
    ])
    assert ready == []
    assert blocked == ["equipment_status", "pm_due", "stops", "mttr"]


def test_inventory_without_equipment_is_prepared():
    from backend.services import lookup_turn as LT
    ready, blocked = LT.prepare([{"name": "재고", "equipment": "", "kind": "", "period": ""}])
    assert blocked == [] and ready[0]["name"] == "inventory" and ready[0]["equipment"] is None


def test_a_question_alongside_a_lookup_does_not_run(monkeypatch):
    from backend.services import lookup_turn as LT
    assert LT.question_only({"question": "어느 설비인가요?", "lookups": [{"name": "정지 횟수", "equipment": "VF2-01", "kind": "", "period": "어제"}]}) == "어느 설비인가요?"
    called = {}

    def boom(*_a, **_k):
        called["yes"] = True
        return [], []

    monkeypatch.setattr(LT, "execute", boom)
    ready, _ = LT.prepare([{"name": "정지 횟수", "equipment": "VF2-01", "kind": "", "period": "어제"}])
    assert ready and "yes" not in called


def test_upper_sentence_drops_the_original_block():
    from backend.services import lookup_turn as LT
    text = "어제 멈춘 횟수를 말했어요.\n\n■ 원문 보기\n2026-09-30 VF2-01 손실 정지 35번 259분"
    assert LT.upper_sentence(text) == "어제 멈춘 횟수를 말했어요."
    safe = "순서는 이렇게예요.\n\n■ 안전 작업 (고정 서식 · AI 작성 아님)\n6.1 운전정지\n\n주의: 근거 안내이며 실행 지시가 아닙니다."
    assert LT.upper_sentence(safe) == "순서는 이렇게예요."


def test_yesterday_stop_query_uses_the_reference_date(v3):
    from backend.services import lookup_turn as LT
    ready, blocked = LT.prepare([{"name": "정지 횟수", "equipment": "VF2-01", "kind": "", "period": "어제"}])
    assert blocked == []
    texts, _ = LT.execute("MNT", ready, "어제 VF2-01 몇 번 멈췄어?")
    assert texts and "2026-09-30" in texts[0] and "VF2-01" in texts[0]


def test_two_lookups_both_run(v3):
    from backend.services import lookup_turn as LT
    ready, blocked = LT.prepare([
        {"name": "정지 횟수", "equipment": "VF2-01", "kind": "", "period": "어제"},
        {"name": "재고", "equipment": "", "kind": "", "period": ""},
    ])
    assert blocked == [] and len(ready) == 2
    texts, _ = LT.execute("MNT", ready, "어제 VF2-01 몇 번 멈췄고 재고도 알려줘")
    blob = " ".join(texts)
    assert "2026-09-30" in blob and "재고 부족" in blob and "부족 30개" in blob and "멈췄고" not in blob


def test_inventory_kind_is_the_only_item_name(v3):
    from backend.services import lookup_turn as LT
    ready, blocked = LT.prepare([{"name": "재고", "equipment": "", "kind": "알루미늄 봉재 6061", "period": ""}])
    assert blocked == []
    texts, _ = LT.execute("MNT", ready, "어제 VF2-01 몇 번 멈췄고 재고도 알려줘")
    blob = " ".join(texts)
    assert "알루미늄 봉재 6061" in blob and "멈췄고" not in blob and "브래킷" not in blob


def test_all_equipment_run_state_queries_the_six(v3):
    from backend.services import lookup_turn as LT
    ready, blocked = LT.prepare([{"name": "가동 상태", "equipment": "모든설비", "kind": "", "period": ""}])
    assert blocked == [] and ready[0]["equipment"] == list(LT.SIX)
    texts, _ = LT.execute("MNT", ready, "모든 설비 가동 상태")
    blob = " ".join(texts)
    assert "VF2-01" in blob and "VF2-02" in blob


def test_lookup_path_stays_off_when_the_llm_is_off(v3):
    from backend.config import settings
    from backend.services import lookup_turn as LT
    q = "VF2-01 지금 상태 어때?"
    assert LT.applies(q, A.parse(q), settings(), []) is False

