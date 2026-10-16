"""LLM 출력 검사 (NFR-AIQ-09, FR-AST-COM-05). LLM이 틀려도 답은 막히지 않고 기본 문장이 나와야 한다."""
import json

from backend.llm.adapter import FallbackAdapter, check_text, write_answer

DRAFT = "2026-09-30 야간 VF2-01 정지 전체 8번 169분, 고장 손실 약 0개(추정), 작업기록 MR-2609-007"
FACTS = {"draft_conclusion": DRAFT, "draft_related": "이 알람은 최근 7일 1번", "draft_caution": "근거 안내이며 실행 지시가 아닙니다."}


class Fake:
    name = "가짜 LLM"

    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []

    def write(self, facts, feedback=None):
        self.calls.append(feedback)
        out = self.outputs.pop(0) if self.outputs else self.outputs_last
        self.outputs_last = out
        if isinstance(out, Exception):
            raise out
        return out


def _j(text, **extra):
    return json.dumps({"conclusion": text, **extra}, ensure_ascii=False)


def test_check_two_way_numbers_and_ids():
    ok = "VF2-01은 2026-09-30 야간에 모두 8번, 169분 멈췄습니다. 고장 손실 약 0개(추정), 작업기록 MR-2609-007"
    assert check_text(ok, DRAFT) is None
    assert check_text(ok.replace("8번", "9번"), DRAFT).startswith(("빠진", "새"))       # 틀린 숫자
    assert check_text(ok.replace(", 작업기록 MR-2609-007", ""), DRAFT).startswith("빠진")  # 기록 번호 빠짐
    assert check_text(ok + " 다음 교대에 3번 더", DRAFT).startswith("새")                # 지어낸 숫자
    assert check_text(ok.replace("169분", "169.0분"), DRAFT) is None                     # 같은 값의 다른 표기


def test_check_blocks_korean_numbers_permission_and_sources():
    base = "VF2-01은 2026-09-30 야간 8번 169분, 손실 약 0개(추정), MR-2609-007"
    assert check_text(base + ", 세 번은 조작", DRAFT) == "한글 수사"
    assert check_text(base + ". 리셋해도 됩니다", DRAFT) == "허락·지시 문구"
    assert check_text(base + ". 다시 올려도 괜찮습니다", DRAFT) == "허락·지시 문구"
    assert check_text(base + ". 차단기를 리셋하세요", DRAFT) == "허락·지시 문구"
    assert check_text(base + " (TG0125 참고)", DRAFT) == "원문 출처 표기"


def test_write_answer_uses_valid_llm_text_and_program_caution():
    text = "VF2-01은 2026-09-30 야간에 8번, 169분 멈췄습니다. 고장 손실 약 0개(추정). 작업기록 MR-2609-007"
    fields, mode, trace = write_answer(FACTS, Fake(_j(text, caution="안전합니다", related="지어낸 줄")))
    assert fields.conclusion == text and mode == "가짜 LLM" and trace["used"]
    assert fields.caution == FACTS["draft_caution"] and fields.related == FACTS["draft_related"]  # LLM이 보낸 주의·관련은 버림


def test_write_answer_falls_back_with_reason_and_feedback():
    bad = Fake(_j("8번 멈춤"), _j("9번 멈췄습니다"))
    fields, mode, trace = write_answer(FACTS, bad)
    assert fields.conclusion == DRAFT and "LLM 결과를 쓰지 않음" in mode and not trace["used"]
    assert trace["tries"] == 2 and bad.calls[0] is None and bad.calls[1].startswith("빠진")  # 두 번째 요청에 사유를 붙인다


def test_write_answer_survives_broken_json_and_server_error():
    for out in ("not json", "{\"answer\": 1}", ConnectionError("down")):
        fields, mode, trace = write_answer(FACTS, Fake(out, out))
        assert fields.conclusion == DRAFT and not trace["used"]


def test_fallback_is_unchanged_draft():
    fields, mode, trace = write_answer(FACTS, FallbackAdapter())
    assert fields.conclusion == DRAFT and mode == FallbackAdapter.name and trace["tries"] == 0
