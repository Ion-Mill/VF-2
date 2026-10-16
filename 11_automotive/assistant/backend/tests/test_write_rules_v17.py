"""새 글 규칙 정밀도 시험 (WRITE_RULES_V17, 2026-10-14 시급한 문제 2 "원문 복사", 계획 승인).

근거: 공개 세트 E8·E9·CMP30의 앱 설정(step20) 기록에서 새 글 후보 66개를 모아 별도 라벨러(Opus, 막은 결과를 모르는 채)가
"원문과 뜻이 같은가"를 판정했다. 코드 규칙이 막은 24개 중 22개가 뜻이 같았다.
`snapshots/write_rules_v17_cases.json`의 pass 13개(스위치를 켜면 풀려야 함)와 block 4개(계속 막혀야 함)를 고정한다.
스위치를 끈 상태는 예전 그대로 막혀야 한다(fixture의 old_reason). 새 글이 틀리게 풀리지 않는지(지어낸 의무·뒤집힘·기계 끄기·허락)도 따로 본다.
AI 서버는 부르지 않는다.
"""
import json
from pathlib import Path

import pytest

from backend.eval import run_eval as R
from backend.services import followup_v2 as FU2

CASES = json.loads((Path(__file__).parent / "snapshots" / "write_rules_v17_cases.json").read_text(encoding="utf-8"))["cases"]


def _mode(monkeypatch, name):
    for k, v in R.MODES[name].items():
        monkeypatch.setenv(k, v)


def _check(c):
    """실제 길: 코드 검사(check_answer_v11) 먼저, 안전 낱말·조건 말 이유로 막힌 글이면 안전 영역 검사(check_answer_safe_v15)도."""
    why = FU2.check_answer_v11(c["text"], c["lines"], set(), question=c["question"])
    if why is None and c["old_reason"].startswith(("안전 낱말 빠짐", "조건 말 빠짐")):
        why = FU2.check_answer_safe_v15(c["text"], c["lines"], c["question"])
    return why


def test_step20_rules_adds_only_the_switch():
    """평가 모드 step20-rules = step20 + WRITE_RULES_V17. 다른 모드는 모두 꺼짐 (새 스위치는 다섯 곳에 기본 꺼짐으로 고정)."""
    assert R._BASE["WRITE_RULES_V17"] == "0"
    a, b = R.MODES["step20"], R.MODES["step20-rules"]
    assert {k for k in b if b[k] != a[k]} == {"WRITE_RULES_V17"} and b["WRITE_RULES_V17"] == "1"
    assert all(R.MODES[m]["WRITE_RULES_V17"] == "0" for m in R.MODES if m not in ("step20-rules", "step20-v17"))


PASS = [c for c in CASES if c["expect"] == "pass"]
BLOCK = [c for c in CASES if c["expect"] == "block"]


@pytest.mark.parametrize("c", PASS, ids=[f"{c['kind']}-{c['id']}" for c in PASS])
def test_labeled_faithful_texts_pass_only_when_the_switch_is_on(monkeypatch, c):
    assert c["label"][0] == "yes"   # 라벨러가 원문과 뜻이 같다고 본 글
    _mode(monkeypatch, "step20")
    off = _check(c)
    assert off is not None and off.startswith(c["old_reason"][:6]), off   # 예전 동작: 막힘 (사유 같음)
    _mode(monkeypatch, "step20-rules")
    assert _check(c) is None


@pytest.mark.parametrize("c", BLOCK, ids=[f"{c['kind']}-{c['id']}" for c in BLOCK])
def test_texts_that_must_stay_blocked(monkeypatch, c):
    _mode(monkeypatch, "step20-rules")
    assert _check(c) is not None


# ── 해야 할 일 꼴: 지어낸 의무는 계속 막고, 질문이 받은 꼴만 푼다 ──
FEED = ["이송 속도 — 표준어: 이송 속도 · 영어: Feed Rate"]


def test_invented_duty_is_still_rejected(monkeypatch):
    _mode(monkeypatch, "step20-rules")
    txt = "이송 속도는 작업자가 조정해야 해요."
    assert FU2.check_answer_v11(txt, FEED, set(), question="이송 속도 뭐야").startswith("해야 할 일 꼴")      # 앱 로그의 지어낸 의무
    assert FU2.check_answer_v11(txt, FEED, set(), question="이송 속도는 누가 조정해야 돼?") is None        # 질문이 의무 꼴로 물었다
    assert FU2.check_answer_v11(txt, FEED, set(), question="이송 속도는 누가 조정해야 하죠?") is None
    assert FU2.check_answer_v11(txt, FEED, set(), question="이송 속도 조정은 누가 해야 됨?") is None


# ── 가능성 꼴(뜻 뒤집힘): 원문·질문에 없는 "수 있"은 막는다 ──
WARN = ["[POWER UP]을 누르면 바로 자동으로 움직인다. 주축·테이블·공구 교환장치에서 떨어진다"]


def test_new_possibility_form_is_rejected(monkeypatch):
    _mode(monkeypatch, "step20-rules")
    q = "원점 복귀할 때 조심할 게 뭐야?"
    assert FU2.check_answer_v11("공구 교환장치에서 떨어질 수 있으니 주의하세요.", WARN, set(), question=q) == "가능성 꼴 (원문·질문에 없음)"
    assert FU2.check_answer_v11("사람은 공구 교환장치에서 떨어져 있어야 해요.", WARN, set(), question="원점 복귀 때 사람이 해야 할 일은?") is None
    # 원문 줄이나 질문에 "수 있"이 있으면 새로 생긴 꼴이 아니다
    assert FU2.check_answer_v11("재고에서 뺄 수 있어요.", ["재고 — 뺄 수 있다"], set(), question="뭐야") is None
    assert FU2.check_answer_v11("뺄 수 있어요.", ["재고 — 뺀다"], set(), question="뺄 수 있어?") is None
    _mode(monkeypatch, "step20")   # 스위치를 끄면 예전 그대로 (이 검사 없음)
    assert FU2.check_answer_v11("공구 교환장치에서 떨어질 수 있으니 주의하세요.", WARN, set(), question=q) is None


def test_keepaway_detector_is_narrow():
    for yes in ("주축·테이블·공구 교환장치에서 떨어진다", "사람은 테이블에서 떨어져 있는다", "도어에서 떨어져 서서"):
        assert FU2.is_keepaway_v16(yes)
    for no in ("정상보다 빨리 떨어졌다", "실질적으로 떨어뜨리고", "재고가 떨어지면 알림", "회로 차단기가 떨어졌다", "압력이 떨어진 경우"):
        assert not FU2.is_keepaway_v16(no)


# ── 허락 꼴: 부정과 함께 쓴 "~에서만 가능"만 푼다. 허락은 계속 막는다 ──
def test_only_restrictive_possible_is_released(monkeypatch):
    _mode(monkeypatch, "step20-rules")
    src = ["보류 로트 — 출하할 수 없다"]
    q = "보류된 로트 출하해도 돼?"
    assert FU2.check_answer_v11("보류 로트는 출하할 수 없어요. 합격한 로트에서만 가능합니다.", src, set(), question=q) is None
    assert FU2.check_answer_v11("보류 로트도 출하해도 됩니다.", src, set(), question=q) == "허락·지시 문구"
    assert FU2.check_answer_v11("이 로트는 출하가 가능합니다.", src, set(), question=q) == "허락·지시 문구 (허락 꼴)"   # 부정 없는 "가능합니다"
    assert FU2.check_answer_v11("이 로트는 출하가 가능해요, 다만 불가한 경우도 있어요.", src, set(), question=q) == "허락·지시 문구 (허락 꼴)"   # "만 가능"이 아니다


# ── 불 끄기: 소화 문장의 "끄세요"만 풀고, 기계를 끄라는 말은 계속 막는다 ──
def test_fire_extinguishing_is_not_a_machine_off_order(monkeypatch):
    _mode(monkeypatch, "step20-rules")
    src = ["알루미늄 분진 화재 — 물을 쓰지 않는다. 마른 모래로 끈다"]
    q = "알루미늄 분진에 불 붙으면 뭘로 꺼야 돼?"
    assert FU2.check_answer_v11("알루미늄 분진 화재는 마른 모래로 끄세요.", src, set(), question=q) is None
    assert FU2.check_answer_v11("주축 전원을 끄세요.", src, set(), question=q) == "허락·지시 문구"
    assert FU2.check_answer_v11("화재가 났으니 주축 전원을 끄세요.", src, set(), question=q) == "허락·지시 문구"   # 화재 말이 같은 문장에 있어도 기계 전원은 막는다
    _mode(monkeypatch, "step20")
    assert FU2.check_answer_v11("알루미늄 분진 화재는 마른 모래로 끄세요.", src, set(), question=q) == "허락·지시 문구"


# ── 안전 낱말·조건 말: 답에 쓴 칸에서만 요구한다 ──
GREASE = ["그리스 주입 — 주기: 8시간마다 · 방법 요약: 장비를 끄고 잠금을 건 뒤 넣는다 · 쓰는 소모품: 그리스 1개"]


def test_safety_word_is_required_only_in_the_used_cell(monkeypatch):
    q = "그리스는 얼마마다 넣어?"
    _mode(monkeypatch, "step20")
    assert FU2.check_answer_safe_v15("그리스는 8시간마다 넣어요.", GREASE, q).startswith("안전 낱말 빠짐")          # 예전: 줄 전체
    _mode(monkeypatch, "step20-rules")
    assert FU2.check_answer_safe_v15("그리스는 8시간마다 넣어요.", GREASE, q) is None                           # 쓴 칸 = 주기 칸
    # 답이 안전 칸의 내용을 쓰면 그 칸의 안전 낱말은 여전히 요구한다
    assert FU2.check_answer_safe_v15("장비를 끄고 그리스를 넣어요.", GREASE, q).startswith("안전 낱말 빠짐: 잠금")
    # 겹침이 하나도 없으면 줄 전체(예전처럼)
    assert FU2.check_answer_safe_v15("알 수 없어요.", GREASE, q).startswith("안전 낱말 빠짐")
    # question을 주지 않으면 예전 그대로
    assert FU2.check_answer_safe_v15("그리스는 8시간마다 넣어요.", GREASE).startswith("안전 낱말 빠짐")
