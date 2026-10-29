"""만든 데이터 점검 (설계서 9장 중 4단계 범위 + 외래 키).

실행: .venv\\Scripts\\python validate.py   (out/ 을 읽는다)
결과 줄: PASS 통과 / FAIL 실패 (다시 만들어야 함) / WARN 참고 (기준 범위 밖이지만 형태 참고 값)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from gen.common import ROOT, load_config, load_masters, set_profile_from_args


def _read(d: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(d / f"{name}.csv", dtype=str, keep_default_na=False)


def foreign_keys(T: dict, masters: dict) -> list[tuple]:
    """외래 키 목록: (표, 칸, 가리키는 쪽 값 모음). run()과 check_links.py(과거 + 실시간 합친 데이터)가 같이 쓴다."""
    shifts, po, lots, op, al = T["shift"], T["production_order"], T["production_lot"], T["operation_report"], T["alarm_event"]
    wo, rv, nt = T["maintenance_work_order"], T["document_revision"], T["notification"]
    users = {u["user_id"] for u in masters["app_user"]}
    return [("production_lot", "order_no", set(po.order_no)), ("production_lot", "input_shift_id", set(shifts.shift_id)),
          ("operation_report", "lot_no", set(lots.lot_no)), ("operation_report", "worker_user_id", users),
          ("operation_report", "shift_id", set(shifts.shift_id)), ("alarm_event", "lot_no", set(lots.lot_no)),
          ("tool_usage", "op_report_id", set(op.op_report_id)), ("tool_change", "changed_by", users),
          ("defect_record", "lot_no", set(lots.lot_no)),
          ("defect_record", "defect_code", {d["defect_code"] for d in masters["defect_code"]}),
          ("pm_record", "pm_task_id", {p["pm_task_id"] for p in masters["pm_task"]}),
          ("pm_record", "done_by", users), ("pm_record", "recorded_by", users),
          ("work_record", "wo_no", set(wo.wo_no)), ("work_record", "alarm_event_id", set(al.alarm_event_id)),
          ("work_order_step", "wo_no", set(wo.wo_no)), ("equipment_state_log", "alarm_event_id", set(al.alarm_event_id)),
          ("equipment_state_log", "pm_record_id", set(T["pm_record"].pm_record_id)),
          ("equipment_state_log", "reason_code", {d["reason_code"] for d in masters["downtime_reason"]}),
          ("inspection_plan", "lot_no", set(lots.lot_no)), ("inspection_plan", "hold_id", set(T["lot_hold"].hold_id)),
          ("lot_hold", "lot_no", set(lots.lot_no)), ("lot_hold", "related_alarm_event_id", set(al.alarm_event_id)),
          ("lot_hold", "related_tool_id", {t["tool_id"] for t in masters["tool"]}),
          ("lot_hold", "held_by", users), ("lot_hold", "released_by", users),
          ("inventory_txn", "item_no", {i["item_no"] for i in masters["inventory_item"]}),
          ("inventory_txn", "txn_by", users), ("inventory_txn", "pm_record_id", set(T["pm_record"].pm_record_id)),
          ("inventory_txn", "tool_change_id", set(T["tool_change"].tool_change_id)),
          ("inventory_txn", "lot_no", set(lots.lot_no)), ("inventory_txn", "fg_lot_no", set(lots.lot_no)),
          ("inventory_txn", "material_lot_no", set(T["raw_material_lot"].material_lot_no)),
          ("inventory_txn", "work_record_no", set(T["work_record"].record_no)),
          ("inventory_txn", "shipment_no", set(T["shipment"].shipment_no)),
          ("shipment_line", "shipment_no", set(T["shipment"].shipment_no)), ("shipment_line", "lot_no", set(lots.lot_no)),
          ("bottleneck_log", "alarm_event_id", set(al.alarm_event_id)),
          ("inspection_result", "lot_no", set(lots.lot_no)), ("inspection_result", "inspector_id", users),
          ("inspection_result", "cmm_import_id", set(T["cmm_import"].cmm_import_id)),
          ("cmm_import", "lot_no", set(lots.lot_no)),
          ("defect_record", "result_id", set(T["inspection_result"].result_id)),
          ("shift_report", "confirmed_by", users), ("daily_report", "confirmed_by", users),
          ("document_revision", "author_user_id", users), ("document_revision_change", "revision_id", set(rv.revision_id)),
          ("notification", "alarm_event_id", set(al.alarm_event_id)), ("notification", "processed_by", users),
          ("notification", "lot_no", set(lots.lot_no)), ("notification", "tool_id", {t["tool_id"] for t in masters["tool"]}),
          ("notification", "item_no", {i["item_no"] for i in masters["inventory_item"]}),
          ("notification", "pm_task_id", {p["pm_task_id"] for p in masters["pm_task"]}), ("notification", "wo_no", set(wo.wo_no)),
          ("notification", "bottleneck_log_id", set(T["bottleneck_log"].bottleneck_log_id)),
          ("notification", "revision_id", set(rv.revision_id)),
          ("notification", "result_id", set(T["inspection_result"].result_id)),
          ("notification", "shift_id", set(shifts.shift_id)),
          ("notification", "buffer_code", {b["buffer_code"] for b in masters["wip_buffer"]}),
          ("notification", "prev_stage_notification_id", set(nt.notification_id)),
          ("notification_recipient", "notification_id", set(nt.notification_id)),
          ("notification_recipient", "user_id", users),
          ("maintenance_work_order", "trigger_notification_id", set(nt.notification_id))]


def run(cfg: dict, out_dir: Path, masters: dict) -> dict:
    T = {p.stem: _read(out_dir, p.stem) for p in sorted(out_dir.glob("*.csv")) if p.stem != "sensor_sample"}
    lines = []

    def add(name, ok, detail="", warn=False):
        lines.append({"name": name, "result": "PASS" if ok else ("WARN" if warn else "FAIL"), "detail": str(detail)})

    ts = lambda s: pd.to_datetime(s)
    sl = T["equipment_state_log"].copy()
    sl["s"], sl["e"] = ts(sl.start_at), ts(sl.end_at)
    shifts = T["shift"]
    planned_total = int(shifts.planned_time_min.astype(int).sum())
    work = []
    for _, s in shifts.iterrows():
        a, b = pd.Timestamp(s.start_at), pd.Timestamp(s.end_at)
        brk = (a + pd.Timedelta(hours=4), a + pd.Timedelta(hours=5))
        work.append((a, brk[0]))
        work.append((brk[1], b))

    def overlap_min(s, e):
        tot = 0.0
        for a, b in work:
            lo, hi = max(s, a), min(e, b)
            if hi > lo:
                tot += (hi - lo).total_seconds() / 60
        return tot

    # ---- 범위 (9장) ----
    vf = sl[sl.equipment_id.isin(["VF2-01", "VF2-02"])]
    for eq, g in vf.groupby("equipment_id"):
        run_min = sum(overlap_min(s, e) for s, e in zip(g[g.state_code == "RUN"].s, g[g.state_code == "RUN"].e))
        ratio = run_min / planned_total
        lo, hi = cfg["states"]["check_vf2_run_ratio"]
        add(f"{eq} RUN 비율 (계획 가동 시간 대비, 기준 {lo:.0%}~{hi:.0%})", lo <= ratio <= hi, f"{ratio:.1%}")
        in_work = g[[any(a <= s < b for a, b in work) for s in g.s]]
        per_day = len(in_work) / len(T["work_day"][T["work_day"].is_workday == "true"])
        lo, hi = cfg["states"]["check_vf2_daily_state_changes"]
        add(f"{eq} 하루 상태 변화 (기준 {lo}~{hi}회)", lo <= per_day <= hi, f"{per_day:.0f}회")

    op = T["operation_report"].copy()
    for c in ("pq", "gq", "rq", "sq"):
        op[c] = op[c].astype(int)
    made = op[op.process_code == "OP-10"].pq.sum()
    dq = T["defect_record"].qty.astype(int).sum()
    lo, hi = cfg["quality"]["defect_rate"]
    add(f"전체 불량률 (기준 {lo:.1%}~{hi:.1%})", lo <= dq / made <= hi, f"{dq / made:.2%} ({dq}/{made})")

    al = T["alarm_event"]
    g_share = (al.severity_at_event == "GUIDE").mean()
    add(f"알람 중 조작 안내 비율 (기준 {cfg['alarms']['check_guide_share_min']:.0%} 이상)",
        g_share >= cfg["alarms"]["check_guide_share_min"], f"{g_share:.1%}")

    p50 = op[op.process_code == "OP-50"].groupby("shift_id").apply(lambda g: (g.gq + g.rq).sum(), include_groups=False)
    act = shifts.shift_id.map(p50).fillna(0).astype(int)
    lo, hi = cfg["targets"]["shift_actual_typical"]
    share = ((act >= lo) & (act <= hi)).mean()
    add(f"교대 실적 대부분 {lo}~{hi}개 (70% 이상)", share >= 0.7,
        f"{share:.0%} 안 (평균 {act.mean():.1f}, 최소 {act.min()}, 최대 {act.max()})")

    # ---- 맞음 (9장) ----
    prev_ids = set(al.prev_alarm_event_id[al.prev_alarm_event_id != ""])
    stop = al[(al.severity_at_event == "STOP") & ~al.alarm_event_id.isin(prev_ids)]
    down = sl[sl.state_code == "DOWN"]
    add("정지 등급 알람 1건 = DOWN 구간 1개 (충돌 연쇄는 마지막 992만)",
        sorted(stop.alarm_event_id) == sorted(down.alarm_event_id) and down.alarm_event_id.is_unique,
        f"정지 알람 {len(stop)}, DOWN {len(down)}")
    eqp = {e["equipment_id"]: e["process_code"] for e in masters["equipment"]}
    op30_stop = stop[stop.equipment_id.map(eqp) == "OP-30"]
    wo, wr = T["maintenance_work_order"], T["work_record"]
    full = wr[wr.record_type == "FULL"]
    add("OP-30 정지 등급 알람 = 작업지시서 1건·작업기록서 1건",
        sorted(op30_stop.alarm_event_id) == sorted(wo[wo.trigger_kind == "STOP_ALARM"].alarm_event_id)
        and len(full) == len(wo) and set(full.wo_no) == set(wo.wo_no),
        f"OP-30 정지 {len(op30_stop)}, 작업지시서 {len(wo)}, 작업기록서 {len(full)}")
    add("작업지시서마다 계기 1개 이상, 모두 OP-30",
        wo.trigger_kind.isin(["STOP_ALARM", "REPEAT_STAGE2"]).all() and wo.equipment_id.map(eqp).eq("OP-30").all(),
        f"{wo.trigger_kind.value_counts().to_dict()}")
    lo, hi = cfg["maintenance"]["work_orders_30d"]
    add(f"작업지시서 수 (기준 {lo}~{hi}건)", lo <= len(wo) <= hi, f"{len(wo)}건")

    al2 = al.copy()
    al2["t"] = ts(al2.occurred_at)
    reps = []
    for (eq, code), g in al2[(al2.severity_at_event != "GUIDE") & ~al2.alarm_event_id.isin(prev_ids)].groupby(
            ["equipment_id", "alarm_code"]):
        t = sorted(g.t)
        for i in range(len(t)):
            if sum(1 for x in t if t[i] <= x < t[i] + pd.Timedelta(days=7)) >= 3:
                reps.append((eq, code))
                break
    want = sorted((c["equipment"], c["alarm"]) for c in cfg["alarms"]["repeat_cases"])
    add("반복 알람(7일 안 3번)은 사례 2건뿐", sorted(reps) == want, f"{reps}")

    bad = 0
    for eq, g in sl.sort_values("s").groupby("equipment_id"):
        bad += int((g.s.iloc[1:].values != g.e.iloc[:-1].values).sum())
    add("설비 상태 구간이 겹치거나 비지 않음", bad == 0, f"어긋남 {bad}곳")
    add("RUN이 아닌 구간마다 정지 사유 1개, RUN은 비움",
        ((sl.state_code == "RUN") == (sl.reason_code == "")).all())

    lots = T["production_lot"]
    add("모든 생산 로트에 원자재 로트가 있음",
        lots.material_lot_no.isin(T["raw_material_lot"].material_lot_no).all())
    o10 = op[op.process_code == "OP-10"]
    m = o10.merge(lots[["lot_no", "input_shift_id"]], on="lot_no")
    add("한 생산 로트의 OP-10 투입은 모두 한 교대 안 (= 투입 교대)",
        (m.shift_id == m.input_shift_id).all() and o10.lot_no.is_unique)
    po = T["production_order"]
    s_in = lots.assign(q=lots.input_qty.astype(int)).groupby("order_no").q.sum()
    started = po[po.status.isin(["DONE"])]
    add("완료 작업지시: 로트 수량 합 = 작업지시 수량",
        (started.order_no.map(s_in) == started.order_qty.astype(int)).all())
    done_lots = lots[lots.status.isin(["PASSED", "RELEASED"])]
    fin = op[op.process_code == "OP-50"].groupby("lot_no").apply(lambda g: (g.gq + g.rq).sum(), include_groups=False)
    scrap = op.groupby("lot_no").sq.sum()
    chk = (done_lots.lot_no.map(fin).fillna(0) + done_lots.lot_no.map(scrap).fillna(0)) == done_lots.input_qty.astype(int)
    add("판정 로트: OP-50 양품+재작업 + 폐기 = 투입 수량", chk.all(), f"어긋남 {int((~chk).sum())}")

    # 공구 누적 사용량 (교체 때 0, R-10)
    tu, tc = T["tool_usage"].copy(), T["tool_change"].copy()
    tt = {t["item_no"]: float(t["usage_per_part"]) for t in masters["tool_type"]}
    titem = {t["tool_id"]: t["item_no"] for t in masters["tool"]}
    start = {t["tool_id"]: float(t["cum_usage"]) for t in masters["tool"]}
    bad = 0
    for tid in titem:
        per = tt[titem[tid]]
        # 같은 분이면 '부품 완료(사용 기록)'가 먼저, 그다음 부품을 올리기 전 '교체'
        ev = [(pd.Timestamp(r.changed_at), 1, r) for r in tc[tc.tool_id == tid].itertuples()] +              [(pd.Timestamp(r.recorded_at), 0, r) for r in tu[tu.tool_id == tid].itertuples()]
        cum, pending = start[tid], []
        for _, kind, r in sorted(ev, key=lambda x: (x[0], x[1])):
            if kind == 1:                                   # 교체: 교체 전 누적을 기억 (한 실적 안에 여러 번일 수 있음)
                base = cum if not pending else 0.0
                if float(r.cum_before) + 1e-6 < base:
                    bad += 1
                pending.append((base, float(r.cum_before)))
                continue
            n, use, after = int(r.parts_qty), float(r.usage_qty), float(r.cum_after)
            if abs(use - n * per) > 1e-6:
                bad += 1
            if pending:                                     # 이 실적 안(또는 앞)에서 교체가 있었음
                ks = [(b - a_) / per for a_, b in pending] + [after / per]   # 교체 사이마다 깎은 부품 수 + 마지막 교체 뒤
                if any(abs(k - round(k)) > 1e-6 or k < -1e-6 for k in ks) or round(sum(ks)) != n:
                    bad += 1
                pending = []
            elif abs(after - (cum + use)) > 1e-6:
                bad += 1
            cum = after
    add("공구 누적 사용량 = 부품 수 × 부품당 사용량 (교체 때 0)", bad == 0, f"어긋남 {bad}")
    t5 = tu[tu.tool_id == "VF2-01-T05"].sort_values("recorded_at")
    t5_end = float(t5.cum_after.iloc[-1]) / 400 * 100 if len(t5) else -1
    lo_, hi_ = cfg["tools"]["end_state"].get("VF2-01-T05_pct_range", [92, 92])
    add(f"기록 끝 VF2-01 T05 사용률 {lo_}~{hi_}% (목표 90%, 시작 브리핑 교체 권고 대상)", lo_ <= round(t5_end) <= hi_,
        f"{t5_end:.0f}%")

    fm = full.merge(down[["alarm_event_id", "s", "e"]], on="alarm_event_id", how="inner")
    diff = (fm.repair_min.astype(float) - (fm.e - fm.s).dt.total_seconds() / 60).abs()
    add("작업기록서 수리 시간 = DOWN 구간 길이 (1분 이내)", (diff <= 1).all(), f"최대 차이 {diff.max() if len(diff) else 0:.1f}분")

    wl = T["wip_log"].copy()
    wl["q"] = wl.wip_qty.astype(int)
    lim = {w["buffer_code"]: int(w["limit_qty"]) for w in masters["wip_buffer"]}
    add("재공 0 이상, 한도 이하", ((wl.q >= 0) & (wl.q <= wl.buffer_code.map(lim))).all(),
        f"최대 {wl.groupby('buffer_code').q.max().to_dict()}")
    wl["t"] = ts(wl.logged_at)
    out_buf = {"SAW-01": "WIP-10-20", "MIL-01": "WIP-20-30", "VF2-01": "WIP-30-40", "VF2-02": "WIP-30-40",
               "WSH-01": "WIP-40-50"}
    bl = sl[(sl.state_code == "BLOCKED") & ((sl.e - sl.s).dt.total_seconds() >= 600)]
    badb = 0
    for r in bl.itertuples():
        w = wl[(wl.buffer_code == out_buf[r.equipment_id]) & (wl.t >= r.s) & (wl.t < r.e)]
        if len(w) and (w.q < lim[out_buf[r.equipment_id]] - 1).all():
            badb += 1
    add("BLOCKED 구간에는 뒤 재공이 한도에 참 (10분 이상 구간)", badb == 0, f"어긋남 {badb}/{len(bl)}")

    codes = {a["alarm_code"]: a["process_code"] for a in masters["alarm_master"]}
    add("알람 번호가 알람 코드집에 있고, 그 공정 설비에서 남",
        (al.alarm_code.isin(codes) & (al.alarm_code.map(codes) == al.equipment_id.map(eqp))).all())
    add("공정 실적의 설비가 그 공정 설비", (op.equipment_id.map(eqp) == op.process_code).all())

    # ---- 4단계: 검사·보류 (설계서 5.5·5.15, DOC-06 §3.3·§4) ----
    ip, lh = T["inspection_plan"], T["lot_hold"]
    q = cfg["quality"]
    add("로트 상태가 6.8 코드", lots.status.isin(["IN_PROCESS", "WAIT_INSPECTION", "WAIT_JUDGEMENT", "HOLD_REVIEW",
                                                  "PASSED", "ON_HOLD", "RELEASED", "SCRAPPED"]).all(),
        lots.status.value_counts().to_dict())
    jd = lots.set_index("lot_no").judged_at
    add("합격·해제 로트 = 판정 시각 있음 = 검사 방식 판정 (합격 / 보류 검토)",
        ((lots.status.isin(["PASSED", "RELEASED"])) == (lots.judged_at != "")).all()
        and (ip.judged_at.values == jd.reindex(ip.lot_no).values).all()
        and (ip.judgement.isin(["PASS", "HOLD_REVIEW"]) == (ip.judged_at != "")).all())
    enh = ip[ip.plan_mode == "ENHANCED"]
    add("강화 로트마다 강화 사유·계기 보류가 있음", ((enh.enhance_reason != "") & (enh.hold_id != "")).all()
        and (ip[ip.plan_mode == "NORMAL"].hold_id == "").all(), f"강화 {len(enh)}개")
    lo, hi = q["holds_30d"]
    add(f"로트 보류 건수 (기준 {lo}~{hi}건)", lo <= len(lh) <= hi, f"{len(lh)}건", warn=True)
    lo, hi = q["releases_30d"]
    nrel = int((lh.result == "RELEASED").sum())
    add(f"보류 해제 건수 (기준 {lo}~{hi}건)", lo <= nrel <= hi, f"{nrel}건", warn=True)
    ok = True
    for h in lh.itertuples():
        e = enh[enh.hold_id == h.hold_id]
        ok &= bool((e.enhance_reason == "HOLD_LOT").sum() == 1
                   and (e.enhance_reason == "NEXT_LOT").sum() <= int(h.enhanced_next_lots))
        ok &= int(h.enhanced_next_lots) == (q["enhanced_next_lots"]["tool_cause_replaced"] if h.related_tool_id
                                             else q["enhanced_next_lots"]["crash_or_unknown"])
        ok &= (h.held_at < h.released_at) if h.released_at else True
        if h.normal_resumed_at:
            ok &= all(jd[x] != "" and jd[x] <= h.normal_resumed_at for x in e.lot_no) and h.released_at <= h.normal_resumed_at
    add("보류마다: 보류 로트 1 + 다음 로트(공구 1·충돌 2) 강화, 보류 < 해제, 강화 로트 모두 판정 뒤 보통 복귀", bool(ok))
    roles = {u["user_id"]: u["role_code"] for u in masters["app_user"]}
    who = [roles.get(x) for x in list(lh.held_by) + [x for x in lh.released_by if x]]
    add("보류·해제는 SUP·MGR, 폐기 승인은 MGR만", all(r in ("SUP", "MGR") for r in who)
        and all(roles.get(x) == "MGR" for x in lh.scrap_approved_by if x))
    shift_of = {u["user_id"]: u["home_shift_type"] for u in masters["app_user"]}
    day = shifts[shifts.shift_type == "DAY"]
    spans = [(pd.Timestamp(x), pd.Timestamp(y)) for x, y in zip(day.start_at, day.end_at)]
    sc = lh[lh.scrap_approved_at != ""]
    in_day = all(any(a_ <= pd.Timestamp(t) < b_ for a_, b_ in spans) for t, u in zip(sc.scrap_approved_at, sc.scrap_approved_by)
                 if shift_of.get(u) == "DAY")
    add("폐기 승인은 승인자의 근무 교대 안, 승인 ≤ 해제 (폐기 있는 보류는 승인 뒤 해제)",
        in_day and (sc.scrap_approved_at <= sc.released_at).all(), f"폐기 있는 보류 {len(sc)}건")

    # ---- 5단계 ①: 측정값 (설계서 5.15, DOC-06 §2·§3·§6, ERD 5.F.4·5.F.6) ----
    ir, ci = T["inspection_result"].copy(), T["cmm_import"]
    items = {int(i["item_seq"]): i for i in masters["inspection_item"]}
    num = lambda x: float(x) if x != "" else None
    cmm = ir[ir.input_method == "CMM_AUTO"]
    v = cmm.measured_value.astype(float)
    lsl = cmm.item_seq.astype(int).map(lambda k: num(items[k]["lsl"]))
    usl = cmm.item_seq.astype(int).map(lambda k: num(items[k]["usl"]))
    ok_ = ((lsl.isna() | (v >= lsl - 1e-9)) & (v <= usl + 1e-9))
    add("측정값 판정 = 규격(DOC-06 §2)으로 다시 계산한 값 = 측정기 판정 (불일치 0)",
        bool(((ok_ == (cmm.judgement == "PASS")) & (cmm.judgement == cmm.cmm_judgement)).all()))
    pt = cmm.part_temp_c.astype(float)
    add("부품 온도 16~26 ℃ 안, 측정실 20 ℃ (DOC-06 §6)", bool(((pt >= 16) & (pt <= 26)).all()
        and (cmm.room_temp_c.astype(float) == 20.0).all()), f"{pt.min():.1f}~{pt.max():.1f} ℃")
    per_part = cmm.groupby(["lot_no", "part_seq"]).cmm_import_id.nunique()
    add("측정한 부품 1개 = 결과 파일 가져오기 성공 1건, 상태 모두 성공",
        bool((per_part == 1).all() and len(ci) == len(per_part) and (ci.status == "SUCCESS").all()
             and set(cmm.cmm_import_id) == set(ci.cmm_import_id)), f"{len(ci)}건")
    mp = ip.set_index("lot_no").plan_mode
    sampled_ok = True
    for lot_no, g in ir.groupby("lot_no"):
        seqs = set(g.part_seq.astype(int))
        if mp.get(lot_no) == "NORMAL":
            sampled_ok &= all(k == 1 or k % 5 == 0 for k in seqs)
    add("보통 로트의 측정 부품 = 첫 부품 + 5번째마다 (강화 로트는 전부)", bool(sampled_ok))
    enh_lots = set(ip[ip.plan_mode == "ENHANCED"].lot_no)
    pos_ok = all(set(g.position) == {"TOP", "MID", "BOTTOM"} for _, g in
                 cmm[(cmm.item_seq == "1") & cmm.lot_no.isin(enh_lots) & (cmm.insp_kind == "ENHANCED")].groupby(["lot_no", "part_seq"]))
    add("강화 측정: 1번 구멍을 위·중간·아래 3단 (DOC-06 §3.3)", bool(pos_ok))
    dr = T["defect_record"]
    fails = ir[(ir.judgement == "FAIL") & (ir.input_method == "CMM_AUTO")]
    linked = dr[dr.result_id != ""]
    add("측정 불합격 부품마다 불량 기록 1줄이 그 측정값을 가리킴 (DIM 불량)",
        set(linked.result_id) <= set(fails.result_id) and len(linked) == fails.groupby(["lot_no", "part_seq"]).ngroups
        and linked.defect_code.str.startswith("DIM").all(), f"{len(linked)}건")
    fail_lots = set(fails.lot_no)
    add("측정 불합격이 난 로트는 판정이 '보류 검토'이고 보류 기록이 있음 (DOC-06 §4.1)",
        all(ip.set_index("lot_no").judgement.get(l) in ("HOLD_REVIEW", "") for l in fail_lots)
        and fail_lots <= set(T["lot_hold"].lot_no) | set(ip[ip.enhance_reason == "NEXT_LOT"].lot_no),
        f"불합격 로트 {len(fail_lots)}개")
    cpk_bad = []
    for k, g in cmm[cmm.position.isin(["", "MID"])].groupby("item_seq"):
        it = items[int(k)]
        x = g.measured_value.astype(float)
        m_, sd_ = x.mean(), x.std()
        lo_, hi_ = num(it["lsl"]), num(it["usl"])
        cpk = min((hi_ - m_) / (3 * sd_), (m_ - lo_) / (3 * sd_)) if lo_ is not None else (hi_ - m_) / (3 * sd_)
        if cpk < float(it["cpk_min"]):
            cpk_bad.append(f"{k}번 {cpk:.2f}")
    add("항목별 30일 Cpk ≥ 최소 기준 (1번 1.67, 나머지 1.33 — DOC-06 §2)", not cpk_bad, "; ".join(cpk_bad), warn=True)

    # ---- 4단계: 재고·출하 (설계서 5.14·5.20) ----
    inv = T["inventory_txn"].copy()
    inv["q"] = inv.qty_change.astype(float)
    items = {i["item_no"]: i for i in masters["inventory_item"]}
    neg = []
    for it, g in inv.groupby("item_no"):
        bal = g.groupby("txn_at").q.sum().cumsum()
        if (bal < -1e-9).any():
            neg.append(f"{it} {bal.min():.2f}")
    add("재고 = 입고 − 사용 ± 조정, 어느 시각에도 음수 없음", not neg, "; ".join(neg))
    add("재고 품목 13개, 거래 품목이 모두 품목표에 있음", len(items) == 13 and set(inv.item_no) <= set(items))
    own = {"SUP": {u for u, r in roles.items() if r == "SUP"}, "MNT": {u for u, r in roles.items() if r == "MNT"}}
    rx = inv[inv.source_kind.isin(["RECEIPT", "STOCKTAKE", "MATERIAL_RECEIPT"])]
    add("입고·조정 거래의 기록한 사람 = 그 품목의 관리 역할",
        all(b in own[items[i]["owner_role"]] for i, b in zip(rx.item_no, rx.txn_by)))
    add("조정 거래에는 사유(메모)가 있음", (inv[inv.txn_type == "ADJUST"].memo != "").all())
    final = inv.groupby("item_no").q.sum()
    below = sorted(i for i, x in items.items() if x["category"] in ("TOOL", "CONSUMABLE")
                   and final.get(i, 0) < float(x["safety_stock"]))
    add("기록 끝 안전 재고 아래 품목 = 설정값 (축 윤활유·M6 탭)",
        below == sorted(cfg["inventory"]["below_safety_at_month_end"]), f"{below}")
    fg = inv[inv.source_kind == "LOT_PASS"].set_index("fg_lot_no")
    passed = lots[lots.status.isin(["PASSED", "RELEASED"])].set_index("lot_no")
    rel_at = lh[lh.released_at != ""].set_index("lot_no").released_at
    pass_at = passed.judged_at.copy()
    pass_at.update(rel_at)
    fin_q = passed.input_qty.astype(int) - passed.scrap_qty.replace("", "0").astype(int)
    add("완제품 합격 입고 = 합격(해제) 로트 수량, 시각 = 판정(해제) 시각, 다른 로트 입고 0",
        set(fg.index) == set(passed.index) and (fg.q.astype(int) == fin_q.reindex(fg.index)).all()
        and (fg.txn_at == pass_at.reindex(fg.index)).all())
    li = inv[inv.source_kind == "LOT_INPUT"].set_index("lot_no")
    add("원자재 로트 투입 = 생산 로트 투입 수량",
        len(li) == len(lots) and (-li.q.astype(int) == lots.set_index("lot_no").input_qty.astype(int).reindex(li.index)).all())
    tcx = inv[inv.source_kind == "TOOL_CHANGE"]
    add("공구 교체 1회 = 사용 거래 1건 (충돌로 부러진 공구는 작업기록서 사용 부품)",
        tcx.tool_change_id.is_unique and set(tcx.tool_change_id) <= set(T["tool_change"].tool_change_id)
        and len(tcx) == int((T["tool_change"].change_reason != "BROKEN").sum()))
    sh, sln = T["shipment"], T["shipment_line"]
    m2 = sln.merge(sh[["shipment_no", "shipped_at"]], on="shipment_no")
    add("출하 로트 상태: 출하 시각에 모두 합격(해제), 보류 로트 출하 0",
        m2.lot_no.isin(passed.index).all() and (m2.lot_passed_at.values == pass_at.reindex(m2.lot_no).values).all())
    add("출하 시각 > 그 로트 합격(해제) 시각", (m2.shipped_at > m2.lot_passed_at).all())
    shipped_q = sln.assign(n=sln.qty.astype(int)).groupby("lot_no").n.sum()
    add("로트마다 출하 합 ≤ 합격 수량", (shipped_q <= fin_q.reindex(shipped_q.index)).all())
    fifo = 0
    for s_ in sh.itertuples():
        mine = m2[m2.shipment_no == s_.shipment_no]
        gone = set(m2[m2.shipped_at <= s_.shipped_at].lot_no)
        left = [x for x in pass_at.index if pass_at[x] < mine.lot_passed_at.max() and x not in gone]
        if left and not s_.fifo_skip_reason:
            fifo += 1
    add("FIFO: 먼저 합격한 로트를 두고 출하하면 사유가 있음", fifo == 0, f"사유 없는 예외 {fifo}건")
    lo, hi = cfg["shipment"]["late_shipments_30d"]
    late = int(sh.memo.str.contains("늦은 출하").sum())
    add(f"출하 약 {cfg['shipment']['expected_count_30d']}건, 늦은 출하 {lo}~{hi}건",
        abs(len(sh) - cfg["shipment"]["expected_count_30d"]) <= 2 and lo <= late <= hi,
        f"출하 {len(sh)}건, 늦은 출하 {late}건", warn=True)
    add("출하 확인자는 SUP", all(roles.get(x) == "SUP" for x in sh.confirmed_by))
    fgi = inv[inv.item_no == "FG-BRK-A100"]
    fgb = fgi.groupby("txn_at").q.sum().cumsum()
    add("완제품 재고 = 합격 합 − 출하 합 ± 조정, 음수 없음",
        bool((fgb >= 0).all()) and abs(fgb.iloc[-1] - fgi.q.sum()) < 1e-9
        and set(fgi.txn_type) <= {"FG_IN", "SHIP_OUT", "ADJUST"}, f"기록 끝 {fgb.iloc[-1]:.0f}개")

    # ---- 4단계: 재공 선반·병목·센서 (설계서 5.15·5.18·5.19) ----
    w5 = T["wip_log"]
    add("재공 기록 간격: 평소 5분(MIN5), 사건 전후 30분 1분(MIN1). 선반 수는 OP-40→50에만",
        w5.interval_type.isin(["MIN5", "MIN1"]).all() and (w5[w5.buffer_code != "WIP-40-50"].soak_shelf_qty == "").all()
        and (w5[w5.buffer_code == "WIP-40-50"].soak_shelf_qty != "").all(), w5.interval_type.value_counts().to_dict())
    bn = T["bottleneck_log"]
    cnt = bn.cause_code.value_counts().to_dict()
    b = cfg["bottleneck"]
    weeks = len(T["work_day"]) / 6
    want = {"C1": [round(b["cause1_cycle_up"]["per_week"][0] * weeks), round(b["cause1_cycle_up"]["per_week"][1] * weeks)],
            "C2": b["cause2_one_machine"]["count_30d"], "C3": b["cause3_enhanced_inspection"]["count_30d"]}
    for c, (lo, hi) in want.items():
        add(f"병목 원인 {c} 횟수 (기준 {lo}~{hi})", lo <= cnt.get(c, 0) <= hi, f"{cnt.get(c, 0)}회", warn=True)
    prev_ok = (bn.prev_process_code.iloc[1:].values == bn.new_process_code.iloc[:-1].values).all()
    same = (bn.new_process_code == bn.new_process_code.shift()) & (bn.cause_code == bn.cause_code.shift())
    add("병목 기록: 이전 병목 = 앞 줄 새 병목, 공정·원인이 바뀐 때만 한 줄, 고장이면 알람 있음, C4 없음",
        bool(prev_ok) and not same.any() and (bn[bn.cause_code == "FAILURE"].alarm_event_id != "").all() and "C4" not in cnt,
        cnt)
    held = sorted(T["lot_hold"].held_at)
    c3 = bn[bn.cause_code == "C3"].changed_at
    add("병목 원인 ③(검사 강화)은 로트 보류 뒤에만 시작", all(any(h <= t for h in held) for t in c3),
        f"③ {len(c3)}번, 보류 {len(held)}건")
    ss = pd.read_csv(out_dir / "sensor_sample.csv", usecols=["equipment_id", "sensor_code", "sampled_at", "value",
                                                             "interval_type"])
    names = {x["sensor_code"] for x in masters["sensor_item"]}
    step = int(cfg["record_interval"]["sensor_around_event_sec"])
    code = f"SEC{step}"
    sec_s = ss.sampled_at[ss.interval_type == code].str[17:19].astype(int)
    add(f"센서 값: VF2-01·02만, 7개 센서, 간격 MIN1_AVG/{code} ({step}초 값은 {step}초 단위 시각)",
        set(ss.equipment_id) == {"VF2-01", "VF2-02"} and set(ss.sensor_code) == names
        and set(ss.interval_type) <= {"MIN1_AVG", code} and (sec_s % step == 0).all(),
        ss.interval_type.value_counts().to_dict())
    low = ss[(ss.sensor_code == "AirPressure") & ((ss.value < 100) | (ss.value > 110))]
    a120 = al[al.alarm_code == "120"]
    bad = 0
    for eq, g in low.groupby("equipment_id"):
        t = ts(g.sampled_at)
        occ = ts(a120[a120.equipment_id == eq].occurred_at).sort_values()
        ok_ = pd.Series(False, index=g.index)
        for o in occ:
            ok_ |= (t > o - pd.Timedelta(minutes=31)) & (t < o + pd.Timedelta(minutes=1))
        bad += int((~ok_).sum())
    add("공기 압력: 평소 100~110 psi, 밖은 알람 120 앞 30분 하락 구간뿐", bad == 0,
        f"범위 밖 {len(low)}개 중 알람 120 앞이 아닌 것 {bad}개")

    # ---- 보고서·수정 이력·알림 (5단계 ③, 설계서 5.16, ERD 5.G·5.H) ----
    sr, dr = T["shift_report"], T["daily_report"]
    rv, ch = T["document_revision"], T["document_revision_change"]
    nt, nr = T["notification"], T["notification_recipient"]
    sup = dict(zip(shifts.shift_id, shifts.supervisor_user_id))
    tot = dict(zip(shifts.shift_id, shifts.target_qty.astype(int) + shifts.carry_over_qty.astype(int)))
    add("교대 보고서 = 교대마다 1개, 확정자 = 그 교대 반장, 목표 = 목표 + 이월",
        len(sr) == len(shifts) and bool((sr.confirmed_by == sr.shift_id.map(sup)).all())
        and bool((sr.target_qty.astype(int) == sr.shift_id.map(tot)).all()),
        f"{len(sr)}개, 상태 {sr.status.value_counts().to_dict()}")
    sh_end = dict(zip(shifts.shift_id, ts(shifts.end_at)))
    ca = ts(sr.confirmed_at) - sr.shift_id.map(sh_end)
    add("교대 보고서 확정: 교대 끝 뒤 주간 5~30분, 야간 5~55분 [가상]",
        bool(((ca > pd.Timedelta(0)) & (ca <= pd.Timedelta(minutes=60))).all()),
        f"교대 끝 뒤 {int(ca.min().total_seconds() // 60)}~{int(ca.max().total_seconds() // 60)}분")
    dsum = sr.assign(d=sr.shift_id.str[:10]).groupby("d").actual_qty.apply(lambda x: x.astype(int).sum())
    wd = T["work_day"]
    add("일일 보고서: 근무일마다 1개, 실적 = 교대 2개 합, 목표 180",
        len(dr) == int((wd.is_workday == "true").sum())
        and bool((dr.actual_qty.astype(int).values == dsum.loc[dr.work_date].values).all())
        and bool((dr.target_qty == "180").all()), f"{len(dr)}개")
    add("일일 보고서: 마지막 근무일만 확정 대기(AI비서 초안 v0), 나머지 MGR 확정",
        list(dr[dr.status != "CONFIRMED"].work_date) == cfg["reports"]["unconfirmed_daily_reports"]
        and bool((dr[dr.status == "CONFIRMED"].confirmed_by == "U12").all()), dr.status.value_counts().to_dict())
    oee = dr.oee_pct.astype(float)
    add("일일 보고서 라인 OEE (참고: 목표 65%)", bool(oee.between(40, 90).all()),
        f"{oee.min()}~{oee.max()}, 평균 {oee.mean():.1f}", warn=True)
    v0 = rv[rv.version_no == "0"]
    wr_full = set(T["work_record"][T["work_record"].record_type == "FULL"].record_no)
    is_ai_doc = rv.doc_type.isin(["WORK_ORDER", "SHIFT_REPORT", "DAILY_REPORT"]) | (
        (rv.doc_type == "WORK_RECORD") & rv.doc_key.isin(wr_full))
    add("문서 버전: AI비서 초안 문서는 v0 = AI, 사람이 처음 쓰는 문서(간이 작업기록·정비·출하)는 v0 = 사람, v1부터 사람",
        bool(((rv.author_kind == "AI") == (is_ai_doc & (rv.version_no == "0"))).all())
        and bool((rv[rv.author_kind == "HUMAN"].author_user_id != "").all()), rv.groupby("author_kind").size().to_dict())
    cnt = {"WORK_ORDER": len(wo), "WORK_RECORD": len(T["work_record"]), "SHIFT_REPORT": len(sr), "DAILY_REPORT": len(dr),
           "PM_RECORD": len(T["pm_record"]), "SHIPMENT": len(T["shipment"])}
    add("문서 버전: 문서마다 v0 1개", all(int((v0.doc_type == k).sum()) == n for k, n in cnt.items()), cnt)
    docs_ai = rv[is_ai_doc].drop_duplicates(["doc_type", "doc_key"]).shape[0]
    docs_h = rv[is_ai_doc & (rv.author_kind == "HUMAN")].drop_duplicates(["doc_type", "doc_key"]).shape[0]
    share = docs_h / max(1, docs_ai)
    add("AI비서 초안 문서 중 사람이 고친 버전이 있는 비율 (설계서 5.16 약 60%)", 0.45 <= share <= 0.85,
        f"{share:.0%} ({docs_h}/{docs_ai})", warn=True)
    nchg = ch.groupby("revision_id").size()
    add("사람이 고친 버전마다 바뀐 칸 1~2곳", bool(nchg.between(1, 2).all())
        and set(nchg.index) == set(rv[(rv.author_kind == "HUMAN") & (rv.version_no != "0")].revision_id), f"{len(ch)}줄")
    rvd = rv[rv.status_after == "REVISED"]
    add("확정 뒤 고친 버전(REVISED)은 사유가 있음 + 문서 수정 알림", len(rvd) >= 1 and bool((rvd.reason != "").all())
        and set(rvd.revision_id) <= set(nt[nt.rule_code == "DOC_REVISED"].revision_id), f"{len(rvd)}건")
    last = rv.assign(v=rv.version_no.astype(int)).groupby(["doc_type", "doc_key"]).v.max()
    wr = T["work_record"]
    cur = pd.concat([sr.assign(t="SHIFT_REPORT", k=sr.shift_id)[["t", "k", "current_version"]],
                     dr.assign(t="DAILY_REPORT", k=dr.work_date)[["t", "k", "current_version"]],
                     wo.assign(t="WORK_ORDER", k=wo.wo_no)[["t", "k", "current_version"]],
                     wr.assign(t="WORK_RECORD", k=wr.record_no)[["t", "k", "current_version"]]])
    add("문서 행의 현재 버전 = 마지막 버전 번호", all(int(c) == last[(t, k)] for t, k, c in cur.itertuples(index=False)))
    rules = {r["rule_code"]: r for r in masters["notification_rule"]}
    add("알림: 규칙 코드·중요도가 notification_rule과 같음", bool(nt.rule_code.isin(list(rules)).all())
        and bool((nt.importance == nt.rule_code.map(lambda c: rules[c]["importance"])).all()), f"{nt.rule_code.nunique()}종")
    need = {"ALARM_STOP": "alarm_event_id", "ALARM_WARN": "alarm_event_id", "ALARM_GUIDE": "alarm_event_id",
            "REPEAT_ALARM": "alarm_event_id", "REPEAT_ALARM_2": "prev_stage_notification_id", "TARGET_RISK": "shift_id",
            "BOTTLENECK_MOVE": "bottleneck_log_id", "WIP_WARN": "buffer_code", "LOT_DUE_RISK": "lot_no",
            "STOCK_LOW": "item_no", "PM_DUE_SOON": "pm_task_id", "PM_OVERDUE": "pm_task_id", "TOOL_LIFE_90": "tool_id",
            "APPROVAL_WAIT_30M": "wo_no", "APPROVAL_WAIT_2H": "wo_no", "WO_ASSIGNED": "wo_no", "WO_DRAFT_READY": "wo_no",
            "DAILY_REPORT_PENDING": "revision_id", "DOC_REVISED": "revision_id", "SPC_OUT": "result_id",
            "SHIFT_REPORT_PENDING": "shift_id"}
    miss = [c for c, col in need.items() if (nt[nt.rule_code == c][col] == "").any()]
    add("알림마다 종류에 맞는 관련 기록 칸이 있음 (R-38)", not miss, miss)
    pr = nt[nt.is_processed == "true"]
    add("처리된 알림: 방법·처리자·시각이 있고 발생 뒤. 처리 안 된 알림은 비어 있음",
        bool((pr.process_kind != "").all() and (pr.processed_by != "").all())
        and bool((ts(pr.processed_at) >= ts(pr.raised_at)).all())
        and bool((nt[nt.is_processed == "false"].processed_at == "").all()), f"처리 {len(pr)} / 전체 {len(nt)}")
    stop = al[al.severity_at_event == "STOP"]
    ns = nt[nt.rule_code == "ALARM_STOP"]
    add("정지 등급 알람 1건 = 긴급 알림 1건 (팝업·소리는 긴급만)", sorted(ns.alarm_event_id) == sorted(stop.alarm_event_id)
        and bool((nr[nr.notification_id.isin(ns.notification_id)].popup_sound == "true").all())
        and bool((nr[~nr.notification_id.isin(ns.notification_id)].popup_sound == "false").all()), f"{len(ns)}건")
    rep = nt[nt.rule_code.str.startswith("REPEAT")]
    s7 = rep[(rep.equipment_id == "VF2-02") & rep.alarm_event_id.isin(al[al.alarm_code == "2075"].alarm_event_id)]
    add("반복 알람 사례 ① 2075 VF2-02: 1단계 알림, 처리 안 됨 (S1_OPEN, 9장 S-7)",
        len(s7) == 1 and s7.is_processed.iloc[0] == "false" and s7.repeat_stage_status.iloc[0] == "S1_OPEN",
        list(zip(s7.raised_at, s7.repeat_stage_status)))
    r108 = rep[rep.alarm_event_id.isin(al[(al.alarm_code == "108") & (al.equipment_id == "VF2-02")].alarm_event_id)]
    s2 = r108[r108.rule_code == "REPEAT_ALARM_2"]
    add("반복 알람 사례 ② 108 VF2-02: 1단계(조치 계획) → 2단계 → 원인 점검 확정 → 효과 확인, 작업지시서 계기 알림",
        list(r108.rule_code) == ["REPEAT_ALARM", "REPEAT_ALARM_2"] and r108.process_memo.iloc[0] != ""
        and r108.repeat_stage_status.tolist() == ["ESCALATED", "EFFECTIVE"]
        and set(wo[wo.trigger_kind == "REPEAT_STAGE2"].trigger_notification_id) == set(s2.notification_id),
        list(zip(r108.raised_at, r108.repeat_stage_status)))
    add("반복 알람은 위 두 사례뿐 (설계서 5.8 우연한 반복 막기)", len(rep) == 3, f"{len(rep)}건")
    dp = nt[nt.rule_code == "DAILY_REPORT_PENDING"]
    add("일일 보고서 확정 요청 = 근무일마다 1건, 마지막 근무일 것만 처리 안 됨",
        len(dp) == len(dr) and int((dp.is_processed == "false").sum()) == 1,
        f"{len(dp)}건, 처리 안 됨 {int((dp.is_processed == 'false').sum())}")
    sp = nt[nt.rule_code == "SHIFT_REPORT_PENDING"]
    add("교대 보고서 확정 요청 = 교대마다 1건, 모두 처리", len(sp) == len(sr) and bool((sp.is_processed == "true").all()))
    left = nt[nt.is_processed == "false"]
    lines.append({"name": "기록 끝에 남은 알림 (시작 브리핑 재료, 참고)", "result": "PASS",
                  "detail": str(left.rule_code.value_counts().to_dict())})
    imp = nt.importance.value_counts(normalize=True).round(2).to_dict()
    add("알림 중요도 비율 (점검 목표 긴급 약 5%·주의 약 15%·참고 약 80%, DOC-07 10.3)",
        imp.get("CAUTION", 0) <= 0.3, imp, warn=True)
    per10 = ts(nt[nt.importance.isin(["URGENT", "CAUTION"])].raised_at).dt.floor("10min").value_counts()
    add("알림 폭주 없음: 10분에 긴급+주의 10건 넘는 때 없음 (DOC-07 10.3)", int(per10.max()) <= 10,
        f"10분 최대 {int(per10.max())}건")

    # ---- 외래 키 ----
    fk = foreign_keys(T, masters)
    badfk = []
    for tab, col, valid in fk:
        v = T[tab][col]
        v = v[v != ""]
        miss = set(v) - set(valid)
        if miss:
            badfk.append(f"{tab}.{col} {len(miss)}개 (예: {sorted(miss)[:3]})")
    add("외래 키 (가리키는 값이 있음)", not badfk, "; ".join(badfk))
    mt = sl[sl.state_code == "MAINT"]
    add("MAINT 구간에 예방 정비 기록 연결 (원인 점검 구간은 아직 칸 없음)",
        (mt.pm_record_id != "").sum() >= len(mt) - 1, f"MAINT {len(mt)}, 연결 {(mt.pm_record_id != '').sum()}",
        warn=True)

    res = {"passed": sum(l["result"] == "PASS" for l in lines), "failed": sum(l["result"] == "FAIL" for l in lines),
           "warned": sum(l["result"] == "WARN" for l in lines), "lines": lines}
    return res


def run_realtime(cfg: dict, rt_dir: Path, past_dir: Path, masters: dict) -> dict:
    """실시간 모드 기록(out_realtime/) 점검 — 설계서 9장 "시연 데이터 조건" 중 버튼 없는 부분 (리허설마다)."""
    import json
    T = {p.stem: _read(rt_dir, p.stem) for p in sorted(rt_dir.glob("*.csv")) if p.stem != "sensor_sample"}
    P = {k: _read(past_dir, k) for k in ("production_lot", "production_order", "equipment_state_log")}
    man = json.load(open(rt_dir / "manifest.json", encoding="utf-8"))
    lines = []

    def add(name, ok, detail=""):
        lines.append({"name": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    ts = lambda x: pd.to_datetime(x)
    ops = [json.loads(x) for x in open(rt_dir / "run_log.jsonl", encoding="utf-8")]
    start = ts(man["start_at"])
    live = start.date()                                   # 실시간 시작일
    live_s = live.isoformat()
    sl = T["equipment_state_log"].copy()
    bad = 0
    for eq, g in sl.groupby("equipment_id"):
        g = g.sort_values("start_at")
        e = g.end_at.iloc[:-1].values
        bad += int((e != g.start_at.iloc[1:].values).sum()) + int(ts(g.start_at.iloc[0]) != start)
        bad += int(g.end_at.iloc[-1] != "")
    add("설비 상태: 설비마다 실시간 시작 시각부터 빈틈·겹침 없이 이어짐 (마지막 구간은 진행 중)", bad == 0 and sl.equipment_id.nunique() == 6,
        f"어긋남 {bad}")
    add("과거 기록 다음 번호부터 (상태 기록)", int(sl.state_log_id.astype(int).min()) == len(P["equipment_state_log"]) + 1)
    al = T["alarm_event"]
    wait_tool = cfg["realtime"]["wait_human_tool"].split("-T")[0]
    stray = al[(al.scenario_code == "") & ~((al.alarm_code == "362") & (al.equipment_id == wait_tool))]
    add("무작위 알람 없음: 알람은 사건 버튼(scenario_code)이나 교체하지 않은 T05 한도(362)에서만", len(stray) == 0,
        f"알람 {len(al)}건 (사건 {int((al.scenario_code != '').sum())})")
    add("사건 버튼 알람은 is_injected 참", bool((al[al.scenario_code != ""].is_injected == "true").all()))
    nonrun = sl[sl.state_code != "RUN"]
    add("정지 사유는 추천(SUGGESTED)으로 남고 사람 확정 칸은 비움 (화면에서 입력·확정)",
        (nonrun.reason_status == "SUGGESTED").all() and (nonrun.reason_suggested_code != "").all()
        and (sl.reason_confirmed_by == "").all())
    down = sl[sl.state_code == "DOWN"]
    s1_alarms = set(al[al.scenario_code == "S1"].alarm_event_id)
    add("DOWN은 S1 충돌(992)에서만 (고장은 버튼으로만)", bool(down.alarm_event_id.isin(s1_alarms).all()), f"DOWN {len(down)}구간")
    wl = T["wip_log"]
    lim = {w["buffer_code"]: int(w["limit_qty"]) for w in masters["wip_buffer"]}
    q = wl.wip_qty.astype(int)
    add("재공 0 이상, 한도 이하", ((q >= 0) & (q <= wl.buffer_code.map(lim))).all(), wl.groupby("buffer_code").wip_qty.max().to_dict())
    lots_ok = set(P["production_lot"].lot_no) | set(T["production_lot"].lot_no)
    op = T["operation_report"]
    add("공정 실적의 로트가 과거 기록이나 새 로트에 있음", op.lot_no.isin(lots_ok).all())
    add("공정 실적은 실시간 시작일 교대만", op.shift_id.str.startswith(live_s).all(), op.shift_id.unique().tolist())
    o50 = op[op.process_code == "OP-50"]
    day = int((o50[o50.shift_id == f"{live_s}-D"].gq.astype(int) + o50[o50.shift_id == f"{live_s}-D"].rq.astype(int)).sum())
    lines.append({"name": "시작일 주간 실적 (참고, 사건에 따라 달라짐)", "result": "PASS" if 75 <= day <= 115 else "WARN",
                  "detail": f"{day}개"})
    po = T["production_order"]
    new_po = po[~po.order_no.isin(P["production_order"].order_no)]
    add(f"시작일에 새로 만든 작업지시 번호는 PO-{start:%y%m}-", new_po.order_no.str.startswith(f"PO-{start:%y%m}-").all(), f"새 작업지시 {len(new_po)}개")
    ss = pd.read_csv(rt_dir / "sensor_sample.csv")
    ss["t"] = ts(ss.sampled_at)
    rng_ = {x["sensor_code"]: x for x in masters["sensor_item"]}
    ev_al = al[al.scenario_code.isin(["S1", "S4"])]
    out_rng = 0
    for code, g in ss.groupby("sensor_code"):
        lo, hi = float(rng_[code]["normal_min"]), float(rng_[code]["normal_max"])
        if code == "SpindleMotorTemp":
            lo, hi = lo - 1, hi + 1                           # 1분 평균 둘레 잡음
        bad = g[(g.value < lo) | (g.value > hi)]
        for e in ev_al.itertuples():                          # 사건 앞 30분 ~ 알람까지는 범위 밖이 정상 (S1 축 부하, S4 공기 압력)
            o = ts(e.occurred_at)
            bad = bad[~((bad.equipment_id == e.equipment_id) & (bad.t >= o - pd.Timedelta(minutes=31)) & (bad.t <= o + pd.Timedelta(minutes=1)))]
        out_rng += len(bad)
    code = f"SEC{int(cfg['record_interval']['sensor_around_event_sec'])}"
    add(f"센서: VF-2 2대 × 7개, 범위 밖 값은 사건(S1·S4) 알람 앞에서만. {code[3:]}초 값은 주의·정지 알람 앞뒤 30분",
        out_rng == 0 and set(ss.interval_type) <= {"MIN1_AVG", code} and set(ss.equipment_id) == {"VF2-01", "VF2-02"},
        f"그 밖의 범위 밖 {out_rng}, {ss.interval_type.value_counts().to_dict()}")
    ci = T["cmm_import"]
    drop = rt_dir / cfg["realtime"]["cmm_drop_dir"]
    files = sorted(p.name for p in drop.glob("*.csv"))
    ir = T["inspection_result"]
    nrow_ok = True
    for p in list(drop.glob("*.csv"))[:200]:
        x = pd.read_csv(p, dtype=str)
        c = ci[ci.file_name == p.name]
        nrow_ok &= len(c) == 1 and len(x) == int(((ir.cmm_import_id == c.cmm_import_id.iloc[0])).sum())
    add("측정 결과 파일: 측정한 부품마다 공유 폴더 흉내 폴더에 1개, 가져오기 기록·측정값 줄 수와 같음",
        files == sorted(ci.file_name) and bool(nrow_ok) and not list(drop.glob("*.tmp")), f"파일 {len(files)}개")
    pm = T["pm_record"]
    mt = sl[sl.state_code == "MAINT"]
    s6 = pm[pm.memo.fillna("").str.startswith(f"{live.month}/{live.day} 시연 S6")]
    add("S6 정비 기록: 초안(DRAFT), MAINT 구간에 첫 기록 연결", bool((s6.status == "DRAFT").all())
        and (len(s6) == 0 or bool((mt.pm_record_id != "").all())), f"정비 기록 {len(s6)}건")
    routine = pm[pm.memo.fillna("") == ""]
    task = {t["pm_task_id"]: t for t in masters["pm_task"]}
    add("시작일 기한 매일·매주 점검: 그날 주간에 실시, 확정(CONFIRMED)", bool((routine.status == "CONFIRMED").all())
        and bool(routine.pm_task_id.map(lambda x: task[x]["cycle_code"] in ("DAILY", "WEEKLY")).all())
        and bool(routine.done_at.str.startswith(live_s).all()), f"일상 점검 {len(routine)}건")
    failed = [o for o in ops if o["op"] == "failed"]
    add("대본 조작이 모두 됨 (안 된 조작 0)", not failed, "; ".join(f"{o['step']}: {o['why']}" for o in failed))
    times = [o["sim_at"] for o in ops if o["op"] != "reset"]
    add("조작 기록: 시각이 앞으로만 감, 배속은 정해진 값만",
        times == sorted(times) and all(o["value"] in cfg["realtime"]["speeds"] for o in ops if o["op"] == "speed"),
        f"조작 {len(ops)}개")
    tu = T["tool_usage"]
    lim_t = {t["tool_id"]: float({x["item_no"]: x for x in masters["tool_type"]}[t["item_no"]]["life_limit"]) for t in masters["tool"]}
    pct = tu.cum_after.astype(float) / tu.tool_id.map(lim_t)
    add("공구: 한도(100%) 넘는 공구 없음, 362 없음 (공구 수명 사건은 S3 버튼으로만)", bool((pct <= 1.0 + 1e-9).all()),
        f"최대 {pct.max():.0%}")
    bn = T["bottleneck_log"]
    add("병목 기록: 원인 코드가 6.11 안 (고장은 S1 때만)", bool(bn.cause_code.isin(["C1", "C2", "C3", "BASE", "FAILURE"]).all()
        and bn[bn.cause_code == "FAILURE"].alarm_event_id.isin(s1_alarms).all()), bn.cause_code.value_counts().to_dict())
    res = {"passed": sum(l["result"] == "PASS" for l in lines), "failed": sum(l["result"] == "FAIL" for l in lines),
           "warned": sum(l["result"] == "WARN" for l in lines), "lines": lines}
    return res


def main():
    set_profile_from_args()
    cfg = load_config()
    res = run(cfg, ROOT / cfg["run"]["out_dir"], load_masters(cfg))
    for l in res["lines"]:
        print(f"[{l['result']}] {l['name']}  {l['detail']}")
    print(f"통과 {res['passed']} / 실패 {res['failed']} / 참고 {res['warned']}")
    return 0 if res["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
