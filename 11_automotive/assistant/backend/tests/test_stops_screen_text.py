"""정지 답의 손실 추정 줄 복구 · 고장 그룹 분리 · 같은 사유 합치기 (2026-10-21, 기획 `손실줄복구_고장분리_기획_20261021`).

사용자 시험: "고장 손실 몇 개야?" 답에 "고장 손실 약 N개" 줄이 화면에 없었다 — 화면 글을 만드는 `chat_mapping.to_answer_text`가 ops 블록의 notes를 버렸다.
앞 작업은 conclusion만 확인해 놓쳤으므로 이 시험은 화면 글까지 본다. Claude·공용 DB는 부르지 않는다 (가짜 백엔드 + 만든 사건 행).
"""
from __future__ import annotations

import pytest

from backend import chat_mapping as CM
from backend.services import answer as A
from backend.tests.test_doc_recall import APP_FLAGS
from backend.tools import query_tools as T


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("LLM_ENABLED", "0")


def row(eq, code, name, group, times, minutes, loss):
    return {"equipment_id": eq, "reason_code": code, "reason_name": name, "reason_group": group, "times": times, "minutes": minutes, "loss_qty": loss}


def screen_text(monkeypatch, rows, q="오늘 고장 손실 몇 개야?"):
    monkeypatch.setattr(T, "_gather", lambda n, w, e: (list(rows), "2026-10-01T22:15:00"))
    return CM.to_answer_text(A.answer(q, "MNT", {"screen": "SCR-15"}))


def test_no_failure_stops_loss_is_zero_and_total_is_separate(monkeypatch):
    text = screen_text(monkeypatch, [row("VF2-01", "M01", "앞 공정 대기", "MATERIALS", 7, 191.0, 27.3), row("VF2-02", "M01", "앞 공정 대기", "MATERIALS", 2, 125.0, 17.9),
                                     row("VF2-01", "S01", "작업지시 교체", "SETUP", 3, 45.0, 6.4)])
    assert "고장 정지 0번" in text and "고장 손실 약 0개" in text            # 고장 0번인데 전체 몫이 고장 손실로 나오지 않는다
    assert "손실 정지 전체(고장·자재·준비·조작) 12번 361분, 손실 약 52개" in text   # 다른 그룹은 목록 대신 전체 한 줄
    assert "앞 공정 대기" not in text and "자재·흐름" not in text and "작업지시 교체" not in text   # 고장만 물었으니 다른 그룹 목록은 안 보인다


def test_same_reason_is_merged_in_full_group_list(monkeypatch):
    text = screen_text(monkeypatch, [row("VF2-01", "M01", "앞 공정 대기", "MATERIALS", 7, 191.0, 27.3), row("VF2-02", "M01", "앞 공정 대기", "MATERIALS", 2, 125.0, 17.9),
                                     row("VF2-01", "S01", "작업지시 교체", "SETUP", 3, 45.0, 6.4)], q="오늘 몇 번 멈췄어?")
    assert text.count("앞 공정 대기") == 1 and "앞 공정 대기 9번 316분" in text            # 설비 둘의 같은 사유는 한 줄로 합침 (전체 그룹 질문)
    assert "자재·흐름 9번 316분" in text and "고장 손실 약 0개" in text and "손실 정지 전체(고장·자재·준비·조작) 손실 약 52개" in text


def test_failure_stops_loss_counts_failure_group_only(monkeypatch):
    text = screen_text(monkeypatch, [row("VF2-01", "F01", "공구 파손", "FAILURE", 2, 70.0, 10.0), row("VF2-01", "S01", "작업지시 교체", "SETUP", 1, 20.0, 2.9)])
    assert "고장 정지 2번 70분" in text and "공구 파손 2번 70분" in text and "고장 손실 약 10개" in text
    assert "손실 정지 전체(고장·자재·준비·조작) 3번 90분, 손실 약 13개" in text and "작업지시 교체" not in text


def test_failure_loss_ask_only_when_nothing_else_is_asked():
    for q in ("오늘 고장 손실 몇 개야?", "오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘", "VF2-01 지금까지 고장 손실 몇 개야?"):
        assert A.failure_loss_ask_v27(q), q
    for q in ("오늘 몇 번 멈췄어?", "고장 손실이랑 준비 정지 몇 개야?", "고장 손실 몇 번 났어?", "고장 손실이 뭐야?"):
        assert not A.failure_loss_ask_v27(q), q


def test_failure_only_has_single_line(monkeypatch):
    text = screen_text(monkeypatch, [row("VF2-01", "F01", "공구 파손", "FAILURE", 1, 35.0, 5.0)])
    assert "고장 손실 약 5개" in text and "손실 정지 전체" not in text   # 전체와 같으면 한 줄만


def test_speed_loss_tail_survives_screen_text(monkeypatch):
    text = screen_text(monkeypatch, [row("VF2-01", "F01", "공구 파손", "FAILURE", 1, 35.0, 5.0)], q="오늘 교대에서 고장으로 잃은 개수랑 느려서 잃은 개수를 비교해 줘")
    assert "고장 손실 약 5개" in text and "속도 손실(느려서 잃은 개수)은 이 채팅에서 아직 읽지 못해요" in text   # 꼬리가 가리키는 "위 고장 손실" 숫자가 같은 글에 있다
