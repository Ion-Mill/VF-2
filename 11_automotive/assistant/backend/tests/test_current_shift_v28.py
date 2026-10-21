"""'오늘 교대 / 이번 교대'를 현재 교대 범위로 읽기 (2026-10-21, 기획 `오늘교대_현재교대범위_기획_20261021`).

사용자 시험: "오늘 교대에서 고장으로 잃은 개수…"가 교대 하나가 아니라 그날 하루 전체로 조회됐다. 파서에는 시계가 없어서, 교대 인자를 쓰는 조회 앞단에서
백엔드 업무 시각(equipment_status의 기준 시각)으로 가장 최근에 시작한 교대를 정한다. Claude·공용 DB는 부르지 않는다 (가짜 백엔드).
"""
from __future__ import annotations

from datetime import date

import pytest

from backend.services import answer as A
from backend.tests.test_doc_recall import APP_FLAGS
from backend.tools import query_tools as T

NIGHT = [("2026-10-01T20:00:00+09:00", "2026-10-02T05:00:00+09:00")]


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LLM_ENABLED", "0")


def clock(monkeypatch, iso):
    monkeypatch.setattr(T, "equipment_status", lambda role, equipment_id=None: {"as_of": iso})


@pytest.mark.parametrize("iso,want", [("2026-10-01T10:00:00+09:00", (date(2026, 10, 1), "D")), ("2026-10-01T18:00:00+09:00", (date(2026, 10, 1), "D")),
                                      ("2026-10-01T22:15:00+09:00", (date(2026, 10, 1), "N")), ("2026-10-02T02:00:00+09:00", (date(2026, 10, 1), "N")),
                                      ("2026-10-02T06:00:00+09:00", (date(2026, 10, 1), "N"))])
def test_current_shift_by_clock(monkeypatch, iso, want):
    clock(monkeypatch, iso)
    assert T.current_shift("MNT") == want


def test_clock_failure_keeps_old_behavior(monkeypatch):
    def boom(role, equipment_id=None):
        raise RuntimeError("backend down")
    monkeypatch.setattr(T, "equipment_status", boom)
    assert T.current_shift("MNT") is None


def windows_of(monkeypatch, q, iso="2026-10-01T22:15:00+09:00"):
    seen = {}

    def fake_gather(name, windows, extra):
        seen["w"] = list(windows)
        return [], "2026-10-02T00:00:00+09:00"

    clock(monkeypatch, iso)
    monkeypatch.setattr(T, "_gather", fake_gather)
    A.answer(q, "MNT", {"screen": "SCR-15"})
    return seen.get("w")


@pytest.mark.parametrize("q", ["오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘", "이번 교대 고장 손실 몇 개야?", "지금 교대 몇 번 멈췄어?"])
def test_this_shift_question_reads_current_shift_only(monkeypatch, q):
    assert windows_of(monkeypatch, q) == NIGHT   # 22:15 → 10/1 20:00 ~ 10/2 05:00 야간 하나


@pytest.mark.parametrize("q", ["오늘 고장 손실 몇 개야?", "지난 교대 몇 번 멈췄어?", "어제 야간 몇 번 멈췄어?", "오늘 주간 몇 번 멈췄어?"])
def test_other_questions_do_not_depend_on_clock(monkeypatch, q):
    assert windows_of(monkeypatch, q, "2026-10-01T22:15:00+09:00") == windows_of(monkeypatch, q, "2026-10-01T10:00:00+09:00")
