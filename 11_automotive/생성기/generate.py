"""과거 기록 모드: 2026-09-01 ~ 09-30 가상 운영 데이터를 out/에 만든다 (설계서 4장, 4단계 범위). 10/1 실시간 모드는 realtime.py.

실행: .venv\\Scripts\\python generate.py
"""
from __future__ import annotations

import sys

from datetime import date

from gen import notify as NT
from gen import records as R
from gen import reports as RP
from gen import quality as Q
from gen import stage4 as S4
from gen.calendar import SHIFT_COLS, WORK_DAY_COLS, shift_rows, work_day_rows
from gen.common import Out, check_python, load_config, load_masters, write_manifest
from gen.doc03 import load_doc03
from gen.mnt_docs import CHK_COLS, STEP_COLS, WO_COLS, WOP_COLS, WR_COLS, WRP_COLS, build_mnt
from gen.past import search_t05
from gen.pm import COLS as PM_COLS, build_pm

STAGE = "5단계 ③: 과거 30일 + 측정값 판정 + 보고서·수정 이력·알림"


def main():
    check_python()
    cfg = load_config()
    masters = load_masters(cfg)
    sim, rng, force = search_t05(cfg, masters)
    R.fill_shift_actuals(sim)
    doc03 = load_doc03()
    pm_rows, maint_ids = build_pm(cfg, sim.cal, masters, rng, sim.maint_done)
    mnt = build_mnt(cfg, sim, masters, doc03, rng, pm_rows)
    rep_rows, rep_ids = R.report_rows(sim)
    usage, changes = R.tool_rows(sim, rep_ids)
    insp, cmm, fail_rid, _ = Q.build_inspection(cfg, sim, masters, rng)
    states = S4.state_arrays(sim)
    bn = S4.build_bottleneck(cfg, sim, states)
    order_due = {o["order_no"]: o["due_at"].date() for o in R.order_rows(sim, cfg)}
    ship_heads, ship_lines, _ = S4.build_shipments(cfg, sim, order_due)
    inv = S4.build_inventory(cfg, sim, masters, rng, pm_rows, mnt, ship_lines, ship_heads)
    sensors = S4.build_sensors(cfg, sim, rng, bn)
    # 5단계 ③: 보고서·수정 이력·알림 (작업지시서 계기 알림·문서 버전도 여기서 채움 → 작업지시서는 이 뒤에 씀)
    ctx = {"inv": inv, "bn": bn, "mnt": mnt, "pm_rows": pm_rows, "ship_heads": ship_heads, "ship_lines": ship_lines,
           "overdue": {k: date.fromisoformat(v) for k, v in cfg["sim"]["pm_plan"]["overdue_due"].items()}}
    nb = NT.start(cfg, sim, masters, rng, ctx, insp)
    reps = RP.build_reports(cfg, sim, masters, rng, ctx)
    revs, chg, rev_info = RP.build_revisions(cfg, sim, masters, rng, ctx, reps)
    notis, recips = NT.finish(nb, reps, rev_info, revs)

    out = Out(cfg)
    out.clear()
    out.write("work_day", WORK_DAY_COLS, work_day_rows(sim.cal, cfg))
    out.write("shift", SHIFT_COLS, shift_rows(sim.cal))
    out.write("raw_material_lot", R.COLS["raw_material_lot"], R.material_rows(sim))
    out.write("production_order", R.COLS["production_order"], R.order_rows(sim, cfg))
    out.write("production_lot", R.COLS["production_lot"], S4.lot_rows(sim))
    out.write("operation_report", R.COLS["operation_report"], rep_rows)
    out.write("wip_log", R.COLS["wip_log"], S4.wip_rows(cfg, sim, S4.event_centers(sim, bn)))
    out.write("alarm_event", R.COLS["alarm_event"], R.alarm_rows(sim))
    out.write("equipment_state_log", R.COLS["equipment_state_log"], R.state_rows(sim, maint_ids))
    out.write("tool_usage", R.COLS["tool_usage"], usage, sort_key=lambda x: (x["op_report_id"], x["tool_id"]))
    out.write("tool_change", R.COLS["tool_change"], changes)
    out.write("defect_record", R.COLS["defect_record"], R.defect_rows(sim, fail_rid))
    out.write("pm_record", PM_COLS, pm_rows)
    out.write("maintenance_work_order", WO_COLS, mnt["maintenance_work_order"])
    out.write("work_order_step", STEP_COLS, mnt["work_order_step"], sort_key=lambda x: (x["wo_no"], x["step_no"]))
    out.write("work_order_part", WOP_COLS, mnt["work_order_part"])
    out.write("work_record", WR_COLS, mnt["work_record"], sort_key=lambda x: x["record_no"])
    out.write("work_record_check", CHK_COLS, mnt["work_record_check"],
              sort_key=lambda x: (x["record_no"], x["check_seq"]))
    out.write("work_record_part", WRP_COLS, mnt["work_record_part"])
    out.write("inspection_plan", S4.COLS["inspection_plan"], S4.inspection_rows(sim))
    out.write("lot_hold", S4.COLS["lot_hold"], S4.hold_rows(sim))
    out.write("inspection_result", Q.COLS["inspection_result"], insp)
    out.write("cmm_import", Q.COLS["cmm_import"], cmm)
    out.write("shipment", S4.COLS["shipment"], ship_heads)
    out.write("shipment_line", S4.COLS["shipment_line"], ship_lines)
    out.write("inventory_txn", S4.COLS["inventory_txn"], inv)
    out.write("bottleneck_log", S4.COLS["bottleneck_log"], bn)
    out.write("shift_report", RP.SHIFT_COLS, reps["shift_report"])
    out.write("daily_report", RP.DAILY_COLS, reps["daily_report"])
    out.write("document_revision", RP.REV_COLS, revs)
    out.write("document_revision_change", RP.CHG_COLS, chg)
    out.write("notification", NT.COLS["notification"], notis)
    out.write("notification_recipient", NT.COLS["notification_recipient"], recips)
    out.write_tuples("sensor_sample", S4.COLS["sensor_sample"], sensors)

    import validate
    result = validate.run(cfg, out.dir, masters)
    write_manifest(cfg, out, STAGE, result, extra={"t05_force_m": force})
    t = sim.mach["VF2-01"].tools["T05"]
    print(f"out/ {len(out.counts)}개 파일, VF2-01 T05 9/30 끝 {t.cum / t.limit * 100:.0f}%")
    print(f"점검: 통과 {result['passed']} / 실패 {result['failed']} / 참고 {result['warned']}")
    for line in result["lines"]:
        if line["result"] != "PASS":
            print(f"  [{line['result']}] {line['name']}: {line['detail']}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
