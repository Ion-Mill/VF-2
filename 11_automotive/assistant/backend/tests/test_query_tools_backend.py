"""query_tools 시험 — 백엔드 조회 도구 결과를 원본이 돌려주던 행 모양으로 번역한다 ([11_automotive 이식 2026-10-16]). 가짜 백엔드, 네트워크 없음."""
from datetime import date

import pytest

from backend.repositories import backend_tools as BT
from backend.tools import query_tools as T
from backend.tests.fake_backend import NOW, FakeBackend

pytestmark = pytest.mark.own_backend            # 가짜 백엔드·호출 사용자를 이 파일이 직접 준비한다 (conftest의 기본을 끈다)
ALL = {"equipment_status", "alarms", "kpi", "production", "lot", "work_orders", "work_records", "pm_due", "tool_life", "inventory",
       "reliability", "stop_reasons", "sensor_trend", "equipment_spec"}


@pytest.fixture
def fb(monkeypatch):
    fake = FakeBackend().install(monkeypatch)
    with BT.acting_as("U07", ALL):
        yield fake


def test_result_shape_is_the_original_one(fb):
    r = T.inventory("MNT")
    assert {"tool", "as_of", "range", "is_synthetic", "label", "rows", "empty"} <= set(r)
    assert r["is_synthetic"] is True and r["as_of"] == NOW and r["empty"] is False


def test_unknown_equipment_is_rejected_without_a_call(fb):
    with pytest.raises(T.ToolInputError):
        T.equipment_status("MNT", "XXX-99")
    assert fb.calls == []


# ---------------------------------------------------------------- 설비 상태·알람
def test_equipment_status_rows(fb):
    r = T.equipment_status("MNT", "VF2-02")
    assert fb.calls[0]["args"] == {"equipment_id": "VF2-02"}
    row = r["rows"][0]
    assert (row["equipment_id"], row["last_state"], row["open_alarm_code"], row["is_locked"]) == ("VF2-02", "DOWN", "992", True)
    assert row["minutes"] == 20.0 and row["since"].startswith("2026-10-01T07:40")


def test_alarms_are_aggregated_and_flagged_partial(fb):
    r = T.alarms("MNT", None, "2075", start=date(2026, 9, 1), end=date(2026, 9, 30))
    assert [(x["equipment_id"], x["times"]) for x in r["rows"]] == [("VF2-01", 3), ("VF2-02", 2)]
    assert r["partial"] is True and r["aggregated"] is True
    assert fb.calls[0]["args"] == {"from": "2026-09-01T00:00:00+09:00", "to": "2026-10-01T00:00:00+09:00", "alarm_code": "2075"}


def test_alarms_shift_windows_and_merge(fb):
    r = T.alarms("MNT", "VF2-01", "2075", start=date(2026, 9, 28), end=date(2026, 9, 29), shift="N")
    assert [(c["args"]["from"], c["args"]["to"]) for c in fb.calls] == [
        ("2026-09-28T20:00:00+09:00", "2026-09-29T05:00:00+09:00"), ("2026-09-29T20:00:00+09:00", "2026-09-30T05:00:00+09:00")]
    assert r["rows"][0]["times"] == 6                         # 두 구간의 횟수를 더한다
    assert r["range"] == "2026-09-28 ~ 2026-09-29 야간"
    fb.calls.clear()
    T.alarms("MNT", "VF2-01", None, start=date(2026, 9, 28), end=date(2026, 9, 28), shift="D")
    assert (fb.calls[0]["args"]["from"], fb.calls[0]["args"]["to"]) == ("2026-09-28T08:00:00+09:00", "2026-09-28T17:00:00+09:00")


def test_long_periods_are_split_under_the_backend_limit(fb):
    T.alarms("MNT", None, None, start=date(2026, 9, 1), end=date(2026, 10, 15))
    assert len(fb.calls) == 2                                 # 45일 → 30일 + 15일 (백엔드 상한 31일)
    assert fb.calls[1]["args"]["from"] == "2026-10-01T00:00:00+09:00"


# ---------------------------------------------------------------- 정지 (손실 정지만)
def test_stops_group_loss_stops_and_say_so(fb):
    r = T.stops("MNT", "VF2-01", start=date(2026, 9, 1), end=date(2026, 9, 30))
    assert r["partial"] is True and r["all_empty"] is False
    assert (r["total_count"], r["total_minutes"], r["loss_qty_est_total"]) == (3, 90.0, 13)
    groups = {g["group"]: g for g in r["by_group"]}
    assert groups["FAILURE"]["count"] == 2 and groups["FAILURE"]["minutes"] == 70.0 and groups["SETUP"]["count"] == 1
    assert "PLANNED" not in groups                            # 계획 정지는 도구가 주지 않는다 — "0번"이라고 하지 않는다
    assert groups["FAILURE"]["reasons"][0] == {"code": "F01", "name": "공구 파손", "count": 2, "minutes": 70.0}


def test_stops_empty(fb):
    fb.rows["stop_reasons"] = []
    r = T.stops("MNT", "VF2-01")
    assert r["all_empty"] is True and r["total_count"] == 0


# ---------------------------------------------------------------- 지표
def test_kpi_aggregates_shifts_and_includes_reliability_when_allowed(fb):
    r = T.kpi("MNT", "VF2-01", start=date(2026, 9, 29), end=date(2026, 9, 29))
    k = r["rows"][0]
    # A = (384+288)/(480+480), E = 가동 시간 가중 평균, QBR = (77+1)/80... 아니라 (47+1+30)/(50+30), OEE = PBT 가중 평균
    assert (k["availability_pct"], k["performance_pct"], k["qbr_pct"], k["oee_pct"]) == (70.0, 81.4, 97.5, 55.2)
    assert (k["mttr_30d_min"], k["mtbf_30d_h"], k["failures_30d"], k["reliability_hidden"]) == (50.0, 168.0, 4, False)
    assert fb.tools_called() == ["kpi", "reliability"]


def test_kpi_hides_mttr_for_roles_without_the_reliability_tool(fb):
    with BT.acting_as("U01", ALL - {"reliability", "sensor_trend"}):
        r = T.kpi("OPR", "VF2-01", start=date(2026, 9, 29), end=date(2026, 9, 29))
    k = r["rows"][0]
    assert k["reliability_hidden"] is True
    assert not {"mttr_30d_min", "mtbf_30d_h", "failures_30d"} & set(k)         # 값도 칸도 없다
    assert "reliability" not in fb.tools_called()                              # 부르지도 않는다


def test_kpi_shift_filter_goes_to_the_backend_as_shift_type(fb):
    T.kpi("MNT", "VF2-01", start=date(2026, 9, 29), end=date(2026, 9, 29), shift="N")
    assert fb.calls[0]["args"]["shift_type"] == "NIGHT"


def test_kpi_needs_an_equipment(fb):
    with pytest.raises(T.ToolInputError):
        T.kpi("MNT", None)


def test_kpi_no_rows_is_empty(fb):
    fb.rows["kpi"] = []
    assert T.kpi("MNT", "VF2-01")["empty"] is True


# ---------------------------------------------------------------- 생산
def test_production_rows_use_total_target_and_label_status(fb):
    r = T.production("MNT", start=date(2026, 9, 29), end=date(2026, 9, 29))
    d, n = r["rows"]
    assert (d["prod_date"], d["shift"], d["target"], d["output"], d["scrap"], d["status"]) == ("2026-09-29", "D", 90, 84, 2, "확정")
    assert (n["shift"], n["target"], n["output"], n["status"]) == ("N", 96, 96, "미확정")        # 야간 총 목표 = 목표 90 + 이월 6
    assert d["report_id"] == "2026-09-29-D"


def test_production_shift_filter(fb):
    r = T.production("MNT", start=date(2026, 9, 29), end=date(2026, 9, 29), shift="N")
    assert [x["shift"] for x in r["rows"]] == ["N"]


# ---------------------------------------------------------------- 로트
def test_lot_by_number(fb):
    r = T.lots("MNT", "LOT-2609-041-1", None)
    assert fb.calls[0]["args"] == {"lot_no": "LOT-2609-041-1"}
    assert (r["rows"][0]["lot_id"], r["rows"][0]["qty"], r["rows"][0]["status"]) == ("LOT-2609-041-1", 30, "PASSED")


def test_lot_by_order_number_is_unsupported_and_makes_no_call(fb):
    r = T.lots("MNT", None, "PO-2609-041")
    assert r["unsupported"] == "order_no" and r["rows"] == [] and fb.calls == []


def test_lot_needs_a_number(fb):
    with pytest.raises(T.ToolInputError):
        T.lots("MNT", None, None)


# ---------------------------------------------------------------- 정비·공구·재고
def test_work_orders_rows_and_status_filter(fb):
    r = T.work_orders("MNT", None)
    assert [(x["work_order_id"], x["triggers"]) for x in r["rows"]] == [("WO-2609-0007", "ALARM"), ("WO-2609-0006", "PM")]
    assert [x["work_order_id"] for x in T.work_orders("MNT", None, "DONE")["rows"]] == ["WO-2609-0006"]


def test_work_records_are_oldest_first(fb):
    r = T.work_records("MNT", "VF2-01", "2075")
    assert fb.calls[0]["args"] == {"equipment_id": "VF2-01", "alarm_code": "2075"}
    assert [x["work_record_id"] for x in r["rows"]] == ["WR-2609-0004", "WR-2609-0009"]
    assert r["rows"][-1]["cause"] == "윤활유 부족" and r["rows"][-1]["start"].startswith("2026-09-28")


def test_pm_due_flags_overdue(fb):
    r = T.pm_due("MNT", "VF2-01")
    assert fb.calls[0]["args"]["within_days"] == 0
    x = r["rows"][0]
    assert (x["item"], x["next_due"], x["overdue"]) == ("가이드 레일 윤활", "2026-09-27", "true")


def test_tool_life_filter_and_order(fb):
    r = T.tool_life("MNT", None, min_pct=90)
    assert [(x["tool_no"], x["usage_pct"], x["tool_name"], x["used"], x["limit"]) for x in r["rows"]] == [("T05", 92.0, "엔드밀 12mm", 460.0, 500.0)]
    assert [x["tool_no"] for x in T.tool_life("MNT", "VF2-01")["rows"]] == ["T05", "T01"]


def test_inventory_short_only(fb):
    r = T.inventory("MNT", short_only=True)
    assert [(x["item_id"], x["name"], x["short"], x["on_hand"]) for x in r["rows"]] == [("RM-001", "알루미늄 봉재 6061", "true", 20.0)]
    assert len(T.inventory("MNT")["rows"]) == 2


# ---------------------------------------------------------------- 권한·실패
def test_not_allowed_tool_is_denied_without_a_call(fb):
    with BT.acting_as("U01", {"inventory"}):
        with pytest.raises(BT.ToolDenied):
            T.work_records("OPR", "VF2-01")
    assert fb.calls == []


def test_backend_failure_propagates(fb):
    fb.fail_with = BT.BackendToolError("HTTP 500")
    with pytest.raises(BT.BackendToolError):
        T.inventory("MNT")
