"""생성기 시험 (pytest). 실행: .venv\\Scripts\\python -m pytest"""
import io
import json

from gen.calendar import build_calendar
from gen.common import ROOT, Rng, load_config, load_masters
from gen.plan import plan_alarms

import validate


def test_calendar():
    cfg = load_config()
    cal = build_calendar(cfg)
    assert len(cal.workdays) == sum(1 for d in cal.days if d.weekday() != 6) and len(cal.shifts) == 2 * len(cal.workdays)
    assert (cal.shifts[0].start.hour, cal.shifts[0].end.hour, cal.shifts[1].start.hour, cal.shifts[1].end.hour) == (9, 18, 21, 6)
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
    """5단계 ③ 엔터티 6개: 교대 보고서(교대 수), 일일 보고서(근무일 수), 문서 버전·바뀐 칸, 알림·받는 사람."""
    cfg = load_config()
    out = ROOT / cfg["run"]["out_dir"]
    man = json.load(io.open(out / "manifest.json", encoding="utf-8"))
    cal = build_calendar(cfg)
    assert man["rows"]["shift_report"] == len(cal.shifts) and man["rows"]["daily_report"] == len(cal.workdays)
    for e in ["document_revision", "document_revision_change", "notification", "notification_recipient"]:
        assert man["rows"].get(e, 0) > 0, e


def test_realtime_same_script_same_result():
    """실시간 모드: 같은 대본이면 사건·조작 기록이 같고, 되돌리기 뒤에도 프로필의 실시간 시작 시각에서 같은 상태로 시작한다."""
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
    assert a.clock()["sim_at"] == cfg["realtime"]["start"] + ":00+09:00" and a.prev_state == b.__class__(cfg, m).prev_state


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


def test_realtime_skip_to_night_start():
    """시연 넘기기: 오늘 주간 끝 다음 야간 시작으로 (2026-10-19). 옛 이름(TODAY_17:00·TODAY_20:00)도 받는다 (2026-10-24)."""
    from gen.realtime import Realtime
    cfg = load_config()
    a = Realtime(cfg, load_masters(cfg))
    day = cfg["realtime"]["start"][:10]
    a.skip("TODAY_DAY_END")
    assert a.clock()["sim_at"] == f"{day}T{cfg['shifts']['DAY']['end']}:00+09:00"
    a.skip("TODAY_20:00")
    assert a.clock()["sim_at"] == f"{day}T{cfg['shifts']['NIGHT']['start']}:00+09:00"


def test_realtime_preview_fire():
    """알림 미리보기: 주의·고장·공기압은 그 등급 알람이 바로 나고, 정비는 고장 3분 뒤 수리 정비(MAINT)로 바뀐다 (2026-10-21)."""
    from gen.realtime import Realtime
    cfg = load_config()
    a = Realtime(cfg, load_masters(cfg))
    sev = {"warn": "WARN", "stop": "STOP", "air": "WARN", "maint": "STOP"}
    fired = {}
    for kind in ("warn", "stop", "air", "maint"):
        r = fired[kind] = a.fire(kind)
        a.tick(60 / a.speed)                                     # 1분
        al = [e for e in a.events if e["type"] == "alarm"][-1]
        assert (al["alarm_code"], al["equipment_id"], al["severity"]) == (r["alarm_code"], r["equipment_id"], sev[kind])
    assert r["alarm_code"] and [e for e in a.events if e["type"] == "alarm"][-2]["alarm_code"] == "120"
    a.speed = 1
    eq, seen = r["equipment_id"], []
    for _ in range(6):                                           # 6분: 고장 → (가동 없이) 바로 정비
        a.tick(60)
        seen.append(a.sim.mach[eq].cur_state[0])
    assert seen[-1] == "MAINT" and "RUN" not in seen[seen.index("DOWN"):], seen
    assert fired["maint"]["equipment_id"] != fired["stop"]["equipment_id"]   # 이미 고장 난 설비는 피함

