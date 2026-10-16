"""chat_mapping 시험 — 묶음의 답을 기존 백엔드의 비서 응답 계약으로 바꾸는 순수 함수 ([11_automotive 이식 2026-10-16])."""
import pytest

from backend.chat_mapping import UnknownStatus, map_status, role_gate, to_answer_text, to_backend, to_sources

MNT_MGR = {"tool": "reliability", "about": "MTTR·MTBF", "roles": ["MNT", "MGR"]}
SENSOR = {"tool": "sensor_trend", "about": "센서 데이터", "roles": ["MNT", "MGR"]}


@pytest.mark.parametrize("bundle,backend", [
    ({"status": "답변"}, "OK"),
    ({"status": "확인 필요"}, "OK"),
    ({"status": "문서에 없음"}, "NOT_IN_DOCS"),
    ({"status": "근거 없음"}, "NOT_IN_DOCS"),
    ({"status": "권한이 없습니다"}, "OUT_OF_ROLE"),
    ({"status": "안내", "mode": "규칙"}, "REFUSED"),                                  # 설비 조작·사람만 하는 일 거절 (human_only)
    ({"status": "안내", "mode": "화면 안내 (프로그램 고정 문구)"}, "OK"),               # 화면 설명은 거절이 아니다
])
def test_status_table(bundle, backend):
    assert map_status(bundle) == backend


def test_unknown_status_is_not_silently_ok():
    with pytest.raises(UnknownStatus):
        map_status({"status": "처음 보는 상태"})
    with pytest.raises(UnknownStatus):
        map_status({})


def test_answer_text_joins_conclusion_steps_related_and_caution():
    a = {"conclusion": "알람 992 설명.", "steps": ["1 (보전 담당자) 전원 확인", {"no": "★2", "who": "작업자", "text": "표지 건다"}],
         "related": "이 알람은 최근 7일 2번 났습니다", "caution": "근거 안내이며 실행 지시가 아닙니다."}
    t = to_answer_text(a)
    assert t.startswith("알람 992 설명.")
    assert "1 (보전 담당자) 전원 확인" in t and "★2 (작업자) 표지 건다" in t
    assert "이 알람은 최근 7일 2번 났습니다" in t
    assert t.rstrip().endswith("주의: 근거 안내이며 실행 지시가 아닙니다.")


def test_answer_text_with_only_conclusion():
    assert to_answer_text({"conclusion": "문서에 없음 — 근거를 찾지 못했습니다.", "steps": [], "related": None, "caution": None}) \
        == "문서에 없음 — 근거를 찾지 못했습니다."


def test_sources_keep_only_the_four_public_fields_and_dedupe():
    ev = [{"doc_name": "알람 코드집", "doc_no": "DOC-02", "rev": "Rev.1 (2026-10-07)", "section": "4.1", "snippet": "원문 일부", "cite": "x", "title": "t",
           "doc_id": "DOC-02", "revision": "Rev.1 (2026-10-07)"},
          {"doc_name": "알람 코드집", "doc_no": "DOC-02", "rev": "Rev.1 (2026-10-07)", "section": "4.1"},     # 같은 절 두 번
          "not a dict",
          {"doc_name": "용어집", "doc_id": "GLOSSARY", "revision": "Rev.4 (2026-10-14)", "section": "5"}]    # 옛 칸 이름만 있는 경우
    out = to_sources({"evidence": ev})
    assert out == [{"doc_name": "알람 코드집", "doc_no": "DOC-02", "rev": "Rev.1 (2026-10-07)", "section": "4.1"},
                   {"doc_name": "용어집", "doc_no": "GLOSSARY", "rev": "Rev.4 (2026-10-14)", "section": "5"}]


def test_to_backend_has_exactly_the_contract_fields():
    out = to_backend({"status": "답변", "conclusion": "x", "evidence": [], "mode": "규칙", "blocks": [1], "answer_id": "a", "llm": {"model": "m"}})
    assert set(out) == {"answer", "sources", "related", "status"}
    assert out["related"] == [] and out["status"] == "OK"


def test_role_gate_blocks_value_questions_without_the_role():
    out = role_gate("VF2-01 MTTR 알려줘", [MNT_MGR])
    assert out["status"] == "OUT_OF_ROLE" and out["sources"] == [] and out["related"] == []
    assert "보전 담당자(MNT)" in out["answer"] and "공장 관리자(MGR)" in out["answer"]
    assert not any(ch.isdigit() for ch in out["answer"])               # 값은 없다


def test_role_gate_covers_sensor_data():
    assert role_gate("VF2-01 센서 추세 보여줘", [SENSOR])["status"] == "OUT_OF_ROLE"


def test_role_gate_lets_definition_questions_through():
    assert role_gate("MTTR이 뭐야?", [MNT_MGR]) is None                  # 용어 질문은 사내 문서 검색 — 전원 허용


def test_role_gate_only_for_topics_that_are_out_of_role():
    assert role_gate("VF2-01 MTTR 알려줘", []) is None                  # 이 역할은 볼 수 있다
    assert role_gate("VF2-01 MTTR 알려줘", [SENSOR]) is None            # 센서만 빠진 역할이 MTTR을 묻는 경우
    assert role_gate("VF2-01 오늘 생산 실적 알려줘", [MNT_MGR, SENSOR]) is None
