from datetime import datetime

import pytest

from backend.auth.permissions import PermissionDenied, can
from backend.repositories.csv_repo import get_repo
from backend.services import metrics as M
from backend.services import revisions as R
from backend.services.repeat_alarm import bundle, stage1_at, stage2_at
from backend.services.report_rank import Item, rank_report


# ---------------------------------------------------------------- DOC-07 계산식
def test_doc07_oee_example():
    # DOC-07 §6.2 계산 예 (VF2-01 한 교대): A 70.0, E 95.8, QBR 97.8, OEE ≈ 65.6
    assert M.availability(336, 480) == 70.0
    assert M.performance(7.0, 46, 336) == 95.8
    assert M.quality_buy_rate(45, 0, 46) == 97.8
    assert M.oee_from(336, 480, 7.0, 46, 45) == 65.6


def test_loss_qty_example():
    assert M.loss_qty_estimate(48, 7.0) == 7  # DOC-07 §5.3 "48분 ÷ 7.0분 ≈ 약 7개"


def test_forecast_example():
    f = M.forecast_output(40, 0.2, 240)  # DOC-07 §8 예
    assert f == 88.0 and not M.target_risk(f, 90)


def test_mttr_none_when_no_failure():
    assert M.mttr([]) is None and M.mtbf([], 0) is None


def test_tool_pct_floor():
    assert M.tool_usage_pct(368, 400) == 92


def test_required_stops_rules():
    stops = [
        M.Stop("a", "VF2-01", "2026-09-01T09:00", "", 30, "F01", 7.0),
        M.Stop("b", "VF2-01", "2026-09-01T10:00", "", 48, "F04", 7.0),
        M.Stop("c", "VF2-01", "2026-09-01T11:00", "", 4, "F05", 7.0),   # 5분 미만 고장 → 필수 정지 아님
        M.Stop("d", "SAW-01", "2026-09-01T12:00", "", 60, "M01", 1.0),  # 소재 대기 → 넣지 않음
        M.Stop("e", "VF2-02", "2026-09-01T13:00", "", 3, "O01", 7.0),   # 순간 정지 → 한 줄
    ]
    r = M.required_stops(stops)
    assert [s.stop_id for s in r["items"]] == ["b", "a"]
    assert r["micro_count"] == 1 and r["micro_minutes"] == 3


# ---------------------------------------------------------------- 보고 순위
def test_rank_groups_and_counts():
    items = [
        Item("ref", "4", "조작 안내", "2026-09-30T09:00"),
        Item("tool", "3", "공구 90%", "2026-09-30T08:00", sub_order=4),
        Item("2075", "0-1", "2075 미처리 25시간", "2026-09-30T02:30", group_key="VF2-02|윤활"),
        Item("pm", "3", "축 윤활 점검 기한 넘김", "2026-09-29T00:00", group_key="VF2-02|윤활"),
        Item("inv", "3", "축 윤활유 재고 부족", "2026-09-30T16:00", group_key="VF2-02|윤활"),
    ]
    r = rank_report(items)
    assert r["total"] == 3                          # 묶은 뒤 항목 수 (요구사항 기준)
    assert [l.rank for l in r["lines"]] == ["0-1", "3", "4"]
    assert r["lines"][0].original_count == 3        # 묶인 원래 건수는 따로 보인다
    assert r["lines"][0].folded is False and r["lines"][2].folded is True
    assert r["counts"] == {"안전": 0, "긴급": 0, "생산": 0, "주의": 2, "참고": 1}  # 0-1은 주의에 센다 (UI설계서 2.5)


# ---------------------------------------------------------------- 반복 알람 (생성 데이터로)
def _times(eq, code):
    return sorted(datetime.fromisoformat(a["occurred_at"][:19]) for a in get_repo().table("alarm_event")
                  if a["equipment_id"] == eq and a["alarm_code"] == code)


def test_repeat_stage1_and_stage2_on_generated_data():
    t108 = _times("VF2-02", "108")
    s1 = stage1_at(t108)
    assert s1.date().isoformat() == "2026-09-10"
    plan = next(datetime.fromisoformat(r["plan_at"][:19]) for r in get_repo().table("repeat_alarm") if r["repeat_id"] == "RPT-VF2-02-108-1")
    assert stage2_at(t108, plan).date().isoformat() == "2026-09-14"
    assert stage1_at(_times("VF2-02", "2075")).date().isoformat() == "2026-09-30"


def test_bundle_one_minute():
    base = datetime(2026, 9, 1, 9, 0)
    ts = [base, base.replace(second=20), base.replace(second=40), base.replace(minute=30)]
    assert len(bundle(ts)) == 2


# ---------------------------------------------------------------- 권한·수정 이력
def test_permissions():
    assert not can("OPR", "confirm_shift_report") and can("SUP", "confirm_shift_report")
    assert can("SUP", "approve_work_order") and not can("MGR", "approve_work_order") and not can("MNT", "approve_work_order")
    assert can("MON", "view_daily_report") and not can("MON", "chat")
    assert not can("OPR", "view_daily_report")


def test_revision_flow():
    d = R.create("작업지시서", "MW-T1", {"steps": "a", "assignee": ""}, "t0")
    assert d.current.label == "AI비서 초안" and d.current.version == 0
    with pytest.raises(PermissionDenied):
        R.edit(d, "OPR-02", "OPR", {"steps": "b"}, "t1")
    R.edit(d, "MNT-01", "MNT", {"steps": "b"}, "t1")
    assert d.current.version == 1 and d.current.changed == {"steps": {"before": "a", "after": "b"}}
    with pytest.raises(PermissionDenied):
        R.confirm(d, "AI", "SUP", "t2")            # AI는 승인하지 않는다
    with pytest.raises(PermissionDenied):
        R.confirm(d, "MNT-01", "MNT", "t2")        # 작업지시서 승인은 SUP
    R.confirm(d, "SUP-01", "SUP", "t2")
    with pytest.raises(R.RevisionError):
        R.edit(d, "MNT-01", "MNT", {"steps": "c"}, "t3")   # 확정 뒤 수정은 사유 필수
    v = R.edit(d, "MNT-01", "MNT", {"steps": "c"}, "t3", reason="현장 확인 결과 반영")
    assert v.label == "확정 뒤 수정" and not d.is_confirmed and len(d.versions) == 3


def test_no_ai_draft_for_human_docs():
    with pytest.raises(R.RevisionError):
        R.create("간이 작업기록", "MR-S-T", {"memo": "x"}, "t0")
