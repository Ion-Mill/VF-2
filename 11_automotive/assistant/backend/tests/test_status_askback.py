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
