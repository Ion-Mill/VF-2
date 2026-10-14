"""생성기 시험 (pytest). 실행: .venv\\Scripts\\python -m pytest"""
import io
import json

from gen.calendar import build_calendar
from gen.common import ROOT, Rng, load_config, load_masters
from gen.plan import plan_alarms

import validate


def test_calendar():
    cal = build_calendar(load_config())
    assert len(cal.workdays) == 26 and len(cal.shifts) == 52
    assert all(s.planned_min == 480 for s in cal.shifts)


def test_masters_columns_match_erd_codes():
    m = load_masters(load_config())
    assert len(m) == 22
    assert len(m["notification_rule"]) == 25 and len(m["internal_doc"]) == 8
    assert {r["reason_code"] for r in m["downtime_reason"]} >= {"O04", "S04"}


def test_alarm_plan_is_deterministic():
    cfg = load_config()
    m = load_masters(cfg)
    a = plan_alarms(cfg, build_calendar(cfg), m, Rng(cfg["run"]["seed"]))
    b = plan_alarms(cfg, build_calendar(cfg), m, Rng(cfg["run"]["seed"]))
    assert [(x.m, x.equipment_id, x.code) for x in a] == [(x.m, x.equipment_id, x.code) for x in b]


def test_out_passes_validation():
    """generate.py로 만든 out/ 이 9장 점검을 모두 통과해야 한다."""
    cfg = load_config()
    out = ROOT / cfg["run"]["out_dir"]
    man = json.load(io.open(out / "manifest.json", encoding="utf-8"))
    assert man["seed"] == cfg["run"]["seed"]
    res = validate.run(cfg, out, load_masters(cfg))
    assert res["failed"] == 0, [l for l in res["lines"] if l["result"] == "FAIL"]


def test_stage4_files_exist():
    """4단계 엔터티 7개가 out/ 에 있고 비어 있지 않다."""
    cfg = load_config()
    out = ROOT / cfg["run"]["out_dir"]
    man = json.load(io.open(out / "manifest.json", encoding="utf-8"))
    for e in ["inspection_plan", "lot_hold", "inventory_txn", "shipment", "shipment_line", "bottleneck_log",
              "sensor_sample"]:
        assert man["rows"].get(e, 0) > 0, e


def test_stage5_reports_and_notifications_exist():
    """5단계 ③ 엔터티 6개: 교대 보고서 52, 일일 보고서 26, 문서 버전·바뀐 칸, 알림·받는 사람."""
    cfg = load_config()
    out = ROOT / cfg["run"]["out_dir"]
    man = json.load(io.open(out / "manifest.json", encoding="utf-8"))
    assert man["rows"]["shift_report"] == 52 and man["rows"]["daily_report"] == 26
    for e in ["document_revision", "document_revision_change", "notification", "notification_recipient"]:
        assert man["rows"].get(e, 0) > 0, e


def test_realtime_same_script_same_result():
    """실시간 모드: 같은 대본이면 사건·조작 기록이 같고, 되돌리기 뒤에도 10/1 08:00에서 같은 상태로 시작한다."""
    from gen.realtime import Realtime, load_script
    cfg = load_config()
    m = load_masters(cfg)
    script = load_script(cfg["realtime"]["rehearsal_script"])
    a = Realtime(cfg, m)
    a.play(script)
    b = Realtime(cfg, m)
    b.play(script)
    assert a.events == b.events and a.clock() == b.clock()
    assert not any(e["type"] == "alarm" for e in a.events)      # 무작위 알람 없음
    a.reset()
    assert a.clock()["sim_at"] == "2026-10-01T08:00:00+09:00" and a.prev_state == b.__class__(cfg, m).prev_state


def test_wash_batch_one_lot_max_30():
    """세척(OP-40) 한 번 = 한 로트만, 최대 30개 (2026-10-13)."""
    from collections import defaultdict
    from gen.past import run_once
    cfg = load_config()
    force = json.load(io.open(ROOT / cfg["run"]["out_dir"] / "manifest.json", encoding="utf-8"))["t05_force_m"]
    sim, _ = run_once(cfg, load_masters(cfg), force_t05_m=force)
    batches = defaultdict(list)
    for lot in sim.lots:
        for p in lot.parts:
            if "OP-40" in p.start:
                batches[p.start["OP-40"]].append(p.lot.lot_no)
    assert batches and all(len(set(v)) == 1 and len(v) <= cfg["cycle"]["wsh_batch"]["qty"] for v in batches.values())


def test_realtime_event_buttons_same_result():
    """사건 버튼 대본(권장 순서): 같은 대본이면 같은 사건, 네 사건이 모두 시작·끝나고 조작이 모두 됨."""
    from gen.realtime import Realtime, load_script
    cfg = load_config()
    m = load_masters(cfg)
    script = load_script("리허설_권장순서.json")
    a = Realtime(cfg, m)
    a.play(script)
    ev_a = [(e["type"], e.get("scenario_code"), e.get("at")) for e in a.events if e["type"] in ("event_started", "event_ended", "alarm")]
    b = Realtime(cfg, m)
    b.play(script)
    ev_b = [(e["type"], e.get("scenario_code"), e.get("at")) for e in b.events if e["type"] in ("event_started", "event_ended", "alarm")]
    assert ev_a == ev_b
    assert [e["code"] for e in a.event_log] == ["S3", "S6", "S1", "S4"] and all(e.get("end_m") for e in a.event_log)
    assert not [o for o in a.ops if o["op"] == "failed"]
