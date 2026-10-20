"""'정비 중이야?'를 설비 상태 질문으로 읽는다 (2026-10-21 시연 #3).

배경: 질문 "VF2-02 지금 정비 중이야? 몇 분 남았어?"가 설비 상태 조회로 가지 않고 문서 검색으로 가서 "문서에 없음"이 나왔다.
설비 상태 패턴에 '지금 상태·상태 어때·돌아가·가동 중·멈춰 있'만 있었다. 지키는 것: ① '정비/수리/셋업/점검 중이야?'류와 '정비 몇 분 남았어'는 설비 상태로
② '정비 중에는 …' 같은 문서 질문은 그대로 문서 길 ③ 남은 시간을 물으면 끝나는 시각이 기록에 없다고 말한다(지어내지 않는다).
실제 DB·LLM을 부르지 않는다(가짜 백엔드).
"""
import pytest

from backend.services import answer as A
from backend.tests.fake_backend import FakeBackend


@pytest.fixture
def v3(monkeypatch):
    monkeypatch.setenv("PARSE_V2", "1")
    monkeypatch.setenv("PARSE_V3", "1")


@pytest.mark.parametrize("q", [
    "VF2-02 지금 정비 중이야?", "VF2-02 지금 정비 중이야? 몇 분 남았어?", "2호기 수리 중이야?",
    "VF2-01 셋업 중이야?", "1호기 정비 중인가요?", "VF2-02 정비 몇 분 남았어?"])
def test_work_in_progress_question_is_an_equipment_status_question(v3, q):
    assert "equipment_status" in A.parse(q)["intents"], q


@pytest.mark.parametrize("q", [
    "정비 중에는 잠금을 어떻게 해?", "예방 정비 중 안전 수칙 알려줘", "수리 중인 설비에 표지 붙이는 방법은?",
    "셋업 중 알람이 뜨면 어떻게 해?", "정비 중일 때 재공은 어떻게 돼?", "점검 중에는 문을 열어도 돼?"])
def test_document_question_about_work_stays_a_document_question(v3, q):
    assert "equipment_status" not in A.parse(q)["intents"], q


def test_remaining_time_question_says_the_end_time_is_not_recorded(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    a = A.answer("VF2-02 지금 정비 중이야? 몇 분 남았어?", "MNT", {})
    text = " ".join(str(x) for x in (a.get("conclusion"), a.get("steps"), a.get("current_data")))
    assert "설비 상태" in text and "끝나는 시각이나 남은 시간은 기록에 없습니다" in text


def test_plain_status_question_does_not_add_the_note(v3, monkeypatch):
    FakeBackend().install(monkeypatch)
    a = A.answer("VF2-02 지금 상태 어때?", "MNT", {})
    text = " ".join(str(x) for x in (a.get("conclusion"), a.get("steps"), a.get("current_data")))
    assert "설비 상태" in text and "기록에 없습니다" not in text
