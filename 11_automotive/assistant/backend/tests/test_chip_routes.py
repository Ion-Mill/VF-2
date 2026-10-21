"""선택 말풍선(frontend/src/shell/chips.ts)의 알람 번호 질문이 규칙 길로 막힘 없이 풀리는지 — 진짜 Claude·네트워크·DB를 부르지 않는다 (가짜 백엔드·LLM 끔).

2026-10-21: `992 지난 조치` 말풍선이 매뉴얼 번호 때문에 "확인 필요"로 막힌 일이 있었다. 말풍선 문구를 chips.ts 에서 직접 읽어
(번호가 들어가는 `${code} …` 꼴) 모든 문구가 "답변/안내"로 끝나는지 본다. 문서 길(Claude)로 가는 고정 문구('잠금 표지 순서' 등)는 여기서 못 돌린다.
"""
import re
from pathlib import Path

import pytest

from backend.services import answer as A
from backend.tests.test_alarm_causes import APP_ON

CHIPS = (Path(__file__).resolve().parents[3] / "frontend" / "src" / "shell" / "chips.ts").read_text(encoding="utf-8")
TEMPLATES = sorted(set(re.findall(r"`\$\{code\} ([^`]+)`", CHIPS)))


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    for k in APP_ON:
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("ASK_ONLY", "1")
    monkeypatch.setenv("ALARM_CHAIN", "1")


def test_the_chip_file_has_the_expected_number_questions():
    assert {"원인은", "먼저 할 일", "내가 해야 할 일", "점검 순서", "지난 조치", "최근 몇 번 났어?"} <= set(TEMPLATES)


@pytest.mark.parametrize("role", ["OPR", "SUP", "MNT", "MGR"])
@pytest.mark.parametrize("tail", TEMPLATES)
def test_number_chips_are_answered_by_the_rules(role, tail):
    a = A.answer(f"992 {tail}", role, {"new_chat": "1", "screen": "SCR-09", "alarm_key": "992"})
    a.pop("_followup", None)
    assert a["status"] in ("답변", "안내"), (role, tail, a["status"], a["conclusion"][:80])
    assert a["mode"].startswith("규칙") or "카드" in a["mode"] or a["status"] == "답변", (role, tail, a["mode"])
