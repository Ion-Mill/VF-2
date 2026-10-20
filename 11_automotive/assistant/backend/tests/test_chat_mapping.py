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


# ---------------------------------------------------------------- 블록 → 글자 ([11_automotive 이식 2026-10-16], 화면 디자인은 안 바꾸고 글자로 푼다)
from backend.chat_mapping import blocks_to_text  # noqa: E402


def test_blocks_alarm_card_gets_section_headings_and_steps():
    a = {"conclusion": "알람 2075 설명.", "steps": ["★1 (작업자) 수위를 본다", "5 (보전) 체크밸브를 본다"], "related": "이 알람은 최근 7일 3번 났습니다", "caution": "근거 안내입니다.",
         "blocks": [{"kind": "section", "text": "알람 설명"}, {"kind": "text", "text": "알람 2075 설명."},
                    {"kind": "section", "text": "점검 순서 (사내 문서)"}, {"kind": "steps"}]}
    assert to_answer_text(a) == ("■ 알람 설명\n알람 2075 설명.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 수위를 본다\n5 (보전) 체크밸브를 본다"
                                 "\n\n이 알람은 최근 7일 3번 났습니다\n\n주의: 근거 안내입니다.")


def test_blocks_pure_layout_lead_sections_lists_and_closing_text():
    a = {"conclusion": "무시되는 한 줄", "caution": "근거 안내이며 실행 지시가 아닙니다.",
         "blocks": [{"kind": "lead", "text": "윤활유를 채우면 돼요.", "written": True},
                    {"kind": "section", "text": "이유"}, {"kind": "ops", "head": "", "items": ["압력이 떨어져요.", "저장소가 비었어요."], "source": None},
                    {"kind": "section", "text": "확인할 것"}, {"kind": "ops", "head": "", "items": ["수위를 봐요."]},
                    {"kind": "text", "text": "계속 뜨면 보전 담당자에게 알려요."},
                    {"kind": "line", "text": "원문 줄 하나", "orig": True}, {"kind": "line", "text": "원문 줄 둘", "orig": True}]}
    t = to_answer_text(a)
    assert t == ("윤활유를 채우면 돼요.\n\n■ 이유\n1. 압력이 떨어져요.\n2. 저장소가 비었어요.\n\n■ 확인할 것\n1. 수위를 봐요.\n\n"
                 "계속 뜨면 보전 담당자에게 알려요.\n\n주의: 근거 안내이며 실행 지시가 아닙니다.")
    assert "무시되는 한 줄" not in t and "원문 줄" not in t            # conclusion 은 블록을 쓸 때 중복으로 붙이지 않고, 접던 원문 줄은 글자로 안 보낸다


def test_blocks_ops_with_head_and_numbered_items():
    """질문대로 답하기 1단계(2026-10-21): 목록이 딸린 조회 머리 줄이 혼자 서 있으면 "■ "를 붙여 화면이 소제목으로 그린다."""
    a = {"blocks": [{"kind": "ops", "head": "정지 전체 3번", "items": ["고장 2번", "준비 1번"], "source": None}]}
    assert to_answer_text(a) == "■ 정지 전체 3번\n1. 고장 2번\n2. 준비 1번"


def test_blocks_ops_head_right_after_a_section_gets_no_second_marker():
    """소제목 바로 뒤의 조회 머리 줄은 일반 줄 — 한 덩어리에 ■가 둘이면 알람 카드 파서가 모르는 모양이라 카드가 평문으로 떨어진다."""
    a = {"blocks": [{"kind": "section", "text": "운영 기록 [가상]"},
                    {"kind": "ops", "head": "2026-09-01 ~ 2026-09-30 알람 2075 발생", "items": ["VF2-01 3번"], "source": None}]}
    t = to_answer_text(a)
    assert t == "■ 운영 기록 [가상]\n2026-09-01 ~ 2026-09-30 알람 2075 발생\n1. VF2-01 3번"
    assert t.count("■") == 1


def test_blocks_ops_without_items_stays_a_plain_sentence():
    """목록이 없는 조회 한 줄(예: OEE 한 문장)은 제목이 아니라 답 자체라 ■를 붙이지 않는다."""
    a = {"blocks": [{"kind": "ops", "head": "VF2-01 OEE 68.4%", "items": [], "source": None}]}
    assert to_answer_text(a) == "VF2-01 OEE 68.4%"


def test_blocks_consecutive_lines_stay_together_and_unknown_kinds_are_skipped():
    a = {"blocks": [{"kind": "lead", "text": "문서에는 이렇게 있어요."}, {"kind": "line", "text": "첫째 줄"}, {"kind": "line", "text": "둘째 줄"},
                    {"kind": "mystery", "text": "새면 안 되는 글"}, "문자열 블록", {"kind": "text", "text": ""}]}
    assert to_answer_text(a) == "문서에는 이렇게 있어요.\n\n첫째 줄\n둘째 줄"


def test_blocks_missing_steps_block_still_keeps_the_steps():
    a = {"steps": ["1 (작업자) 확인한다"], "blocks": [{"kind": "text", "text": "본문"}]}
    assert to_answer_text(a) == "본문\n\n1 (작업자) 확인한다"
    a2 = {"steps": ["1 (작업자) 확인한다"], "blocks": [{"kind": "text", "text": "본문"}, {"kind": "steps"}]}
    assert to_answer_text(a2).count("1 (작업자) 확인한다") == 1          # 점검 순서 칸이 있으면 두 번 붙이지 않는다


@pytest.mark.parametrize("blocks", [None, [], [{"kind": "line", "text": "원문", "orig": True}], [{"kind": "section", "text": ""}], [{"kind": "mystery"}]])
def test_blocks_that_produce_no_text_fall_back_to_the_old_way(blocks):
    a = {"conclusion": "결론 글", "steps": ["1 단계"], "blocks": blocks}
    assert blocks_to_text(a) is None
    assert to_answer_text(a) == "결론 글\n\n1 단계"


def test_to_backend_with_blocks_still_has_exactly_the_contract_fields():
    out = to_backend({"status": "답변", "conclusion": "x", "evidence": [], "blocks": [{"kind": "text", "text": "본문"}]})
    assert set(out) == {"answer", "sources", "related", "status"} and out["answer"] == "본문"
