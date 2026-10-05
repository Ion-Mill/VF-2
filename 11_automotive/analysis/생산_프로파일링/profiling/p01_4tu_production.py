"""A. 4TU Production_Data 프로파일링 (작업지시/공정/수량/시간/불량/부하/리드타임)"""
import re
from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats

from common_prof import DATA, OUT, QS, quant, save_json, setup_font

plt = setup_font()
S = {}

d = pd.read_csv(DATA / "4tu" / "data" / "Production_Data.csv")
d.columns = [" ".join(c.split()) for c in d.columns]
d["s"] = pd.to_datetime(d["Start Timestamp"])
d["e"] = pd.to_datetime(d["Complete Timestamp"])
d["elapsed_min"] = (d.e - d.s).dt.total_seconds() / 60


def span_min(x):
    m = re.match(r"^(\d+):(\d\d)$", x)
    if m:
        return int(m[1]) * 60 + int(m[2])
    m = re.match(r"^1899/12/(\d+) (\d+):(\d+)", x)      # 엑셀 날짜 오염 1건
    return ((int(m[1]) - 30) * 24 + int(m[2])) * 60 + int(m[3]) if m else np.nan


d["span_min"] = d["Span"].map(span_min)
d["qty_ok"] = d["Qty Completed"]
d["qty_rej"] = d["Qty Rejected"]
d["qty_mrb"] = d["Qty for MRB"]
d["woq"] = d["Work Order Qty"]


def family(a):
    a = " ".join(a.split())
    a = re.sub(r"^SETUP\s+", "", a, flags=re.I)
    a = re.sub(r"\s*-\s*Machine \d+M?$", "", a)
    a = re.sub(r"^Setup$", "Setup", a)
    return a.replace("Round Q.C.", "Round Grinding - Q.C.")


d["family"] = d["Activity"].map(family)
d["is_qc"] = d["family"].str.contains(r"Q\.C\.|Inspection", regex=True)
d = d.sort_values(["Case ID", "s", "e"]).reset_index(drop=True)

# ---------- A1 컬럼 정의 ----------
cols = []
for c in ["Case ID", "Activity", "Resource", "Start Timestamp", "Complete Timestamp", "Span", "Work Order Qty",
          "Part Desc.", "Worker ID", "Report Type", "Qty Completed", "Qty Rejected", "Qty for MRB", "Rework"]:
    s = d[c]
    cols.append({"column": c, "dtype": str(s.dtype), "null": int(s.isna().sum()), "nunique": int(s.nunique()),
                 "example": str(s.dropna().iloc[0])})
pd.DataFrame(cols).to_csv(OUT / "4tu_columns.csv", index=False, encoding="utf-8-sig")

# 보고유형 D/S/B
d = d.sort_values(["Case ID", "s", "e"]).reset_index(drop=True)
d["prev_type"] = d.groupby("Case ID")["Report Type"].shift().fillna("START")
rt = []
for t, g in d.groupby("Report Type"):
    rt.append({
        "type": t, "rows": len(g), "share_pct": round(len(g) / len(d) * 100, 1),
        "span_min_median": g.span_min.median(), "span_min_p25": g.span_min.quantile(.25), "span_min_p75": g.span_min.quantile(.75),
        "elapsed_min_median": g.elapsed_min.median(),
        "qty_completed_sum": int(g.qty_ok.sum()), "rows_qty_gt0_pct": round((g.qty_ok > 0).mean() * 100, 1),
        "qty_rejected_sum": int(g.qty_rej.sum()), "mrb_sum": int(g.qty_mrb.sum()),
        "is_qc_activity_pct": round(g.is_qc.mean() * 100, 1),
        "first_in_case_pct": round((g.prev_type == "START").mean() * 100, 1),
        "prev_S_pct": round((g.prev_type == "S").mean() * 100, 1),
        "prev_D_pct": round((g.prev_type == "D").mean() * 100, 1),
        "prev_B_pct": round((g.prev_type == "B").mean() * 100, 1),
        "hour_peak_start": int(g.s.dt.hour.value_counts().idxmax()),
        "start_midnight_pct": round(((g.s.dt.hour == 0) & (g.s.dt.minute == 0)).mean() * 100, 1),
    })
rt = pd.DataFrame(rt)
rt.to_csv(OUT / "4tu_report_type.csv", index=False, encoding="utf-8-sig")
nxt = d.groupby("Case ID")["Report Type"].shift(-1).fillna("END")
pd.crosstab(d["Report Type"], nxt, normalize="index").round(3).to_csv(OUT / "4tu_report_type_next.csv", encoding="utf-8-sig")
# S 뒤에 같은 공정의 D 가 오는지
d["same_act_next"] = d.groupby("Case ID")["Activity"].shift(-1) == d["Activity"]
S["S_followed_by_D_same_activity_pct"] = round(float(((d["Report Type"] == "S") & (nxt == "D") & d.same_act_next).sum() / (d["Report Type"] == "S").sum() * 100), 1)
S["B_machine_activity_only"] = bool(~d[d["Report Type"] == "B"].is_qc.any())
S["span_vs_elapsed_within_1min_pct"] = round(float(((d.span_min - d.elapsed_min).abs() <= 1).mean() * 100), 1)
S["rows_start_at_midnight_pct"] = round(float(((d.s.dt.hour == 0) & (d.s.dt.minute == 0)).mean() * 100), 1)
S["rows_span_zero_pct"] = round(float((d.span_min == 0).mean() * 100), 1)
S["rework_Y_rows"] = int((d.Rework == "Y").sum())
S["rework_Y_activities"] = d[d.Rework == "Y"].family.value_counts().to_dict()
S["rework_Y_report_type"] = d[d.Rework == "Y"]["Report Type"].value_counts().to_dict()
S["period"] = [str(d.s.min()), str(d.e.max())]

# ---------- 작업지시 단위 ----------
cases = d.groupby("Case ID").agg(
    rows=("Case ID", "size"), woq=("woq", "max"), woq_nuniq=("woq", "nunique"), part=("Part Desc.", "first"),
    first_start=("s", "min"), last_end=("e", "max"), n_act=("Activity", "nunique"), n_family=("family", "nunique"),
    n_workers=("Worker ID", "nunique"), n_res=("Resource", "nunique"),
    span_h=("span_min", lambda x: x.sum() / 60), ok=("qty_ok", "sum"), rej=("qty_rej", "sum"), mrb=("qty_mrb", "sum"))
cases["lead_days"] = (cases.last_end - cases.first_start).dt.total_seconds() / 86400
S["cases"] = len(cases)
S["woq_nunique_gt1_cases"] = int((cases.woq_nuniq > 1).sum())

# A5 수량
q_woq = quant(cases.woq, nd=1)
S["order_qty"] = q_woq
sh, loc, sc = stats.lognorm.fit(cases.woq, floc=0)
S["order_qty_lognorm"] = {"sigma": round(sh, 3), "median": round(sc, 1)}
S["order_qty_share_in_24_60_pct"] = round(float(cases.woq.between(24, 60).mean() * 100), 1)
bp = cases.groupby("part").agg(orders=("woq", "size"), woq_median=("woq", "median"), woq_p25=("woq", lambda x: x.quantile(.25)), woq_p75=("woq", lambda x: x.quantile(.75)),
                                n_family_median=("n_family", "median")).sort_values("orders", ascending=False)
bp.to_csv(OUT / "4tu_order_qty_by_part.csv", encoding="utf-8-sig")
S["parts_n"] = int(bp.shape[0])
S["part_top5_share_pct"] = round(float(bp.orders.head(5).sum() / len(cases) * 100), 1)

# A2 공정 수·경로
S["rows_per_case"] = quant(cases.rows, nd=1)
S["n_activity_per_case"] = quant(cases.n_act, nd=1)
S["n_family_per_case"] = quant(cases.n_family, nd=1)
routes = d.groupby("Case ID").apply(lambda g: tuple(dict.fromkeys(g.sort_values(["s", "e"]).family)), include_groups=False)
rc = Counter(routes)
rtab = pd.DataFrame([{"rank": i + 1, "cases": n, "share_pct": round(n / len(routes) * 100, 1), "route": " > ".join(r)}
                     for i, (r, n) in enumerate(rc.most_common(10))])
rtab.to_csv(OUT / "4tu_routes_top10.csv", index=False, encoding="utf-8-sig")
S["route_unique"] = len(rc)
S["route_top10_cover_pct"] = round(float(rtab.share_pct.sum()), 1)
# 핵심 경로(재작업/수정 제외, 연속 중복 제거)
core_drop = ("Rework", "Fix", "Change Version", "Setup", "Stress Relief", "Nitration")
def core(r):
    r2 = [x for x in r if not any(k in x for k in core_drop)]
    return tuple(r2)
croutes = routes.map(core)
S["core_n_family_per_case"] = quant(croutes.map(len), nd=1)
cc = Counter(croutes)
pd.DataFrame([{"rank": i + 1, "cases": n, "share_pct": round(n / len(croutes) * 100, 1), "route": " > ".join(r)}
              for i, (r, n) in enumerate(cc.most_common(10))]).to_csv(OUT / "4tu_routes_core_top10.csv", index=False, encoding="utf-8-sig")
# 가공(비-QC) 공정 수, QC 횟수
S["machining_family_per_case"] = quant(pd.Series([sum(1 for x in r if "Q.C." not in x and "Inspection" not in x and "Packing" not in x) for r in croutes]), nd=1)
S["cases_end_with_packing_pct"] = round(float(np.mean([r[-1] == "Packing" for r in routes]) * 100), 1)
S["cases_start_family_top"] = Counter(r[0] for r in routes).most_common(5)
S["cases_contain_final_inspection_pct"] = round(float(np.mean([any("Final Inspection" in x for x in r) for r in routes]) * 100), 1)

# A3 수량 흐름 (D 보고 합계, 공정군별)
dd = d[d["Report Type"] == "D"]
cf = dd.groupby(["Case ID", "family"]).agg(ok=("qty_ok", "sum"), rej=("qty_rej", "sum"), mrb=("qty_mrb", "sum")).reset_index().merge(cases[["woq"]], left_on="Case ID", right_index=True)
cf["ok_ratio_woq"] = cf.ok / cf.woq
fam_flow = cf.groupby("family").agg(cases=("ok", "size"), ok_ratio_woq_median=("ok_ratio_woq", "median"), ok_ratio_p25=("ok_ratio_woq", lambda x: x.quantile(.25)),
                                    ok_ratio_p75=("ok_ratio_woq", lambda x: x.quantile(.75)), rej_sum=("rej", "sum"), ok_sum=("ok", "sum")).query("cases>=10").sort_values("cases", ascending=False)
fam_flow.round(3).to_csv(OUT / "4tu_qty_vs_orderqty_by_family.csv", encoding="utf-8-sig")
# 인접 공정쌍 수량 비
pairs = []
cfi = cf.set_index(["Case ID", "family"])
for cid, r in routes.items():
    r2 = [x for x in core(r) if (cid, x) in cfi.index]
    for a, b in zip(r2[:-1], r2[1:]):
        oa, ob = cfi.loc[(cid, a), "ok"], cfi.loc[(cid, b), "ok"]
        if oa > 0:
            pairs.append({"from": a, "to": b, "ratio": ob / oa, "ok_from": oa, "ok_to": ob})
pr = pd.DataFrame(pairs)
pr_s = pr.groupby(["from", "to"]).agg(n=("ratio", "size"), ratio_median=("ratio", "median"), ratio_p25=("ratio", lambda x: x.quantile(.25)),
                                      ratio_p75=("ratio", lambda x: x.quantile(.75)), ok_from=("ok_from", "sum"), ok_to=("ok_to", "sum")).reset_index()
pr_s["agg_ratio"] = pr_s.ok_to / pr_s.ok_from
pr_s = pr_s.query("n>=15").sort_values("n", ascending=False)
pr_s.round(3).to_csv(OUT / "4tu_qty_flow_pairs.csv", index=False, encoding="utf-8-sig")
S["flow_pairs_all_agg_ratio"] = round(float(pr.ok_to.sum() / pr.ok_from.sum()), 3)
S["flow_pairs_all_ratio_median"] = round(float(pr.ratio.median()), 3)
S["flow_pairs_ratio_le_1_pct"] = round(float((pr.ratio <= 1).mean() * 100), 1)
# 작업지시 완료 수량/지시 수량: 마지막 공정(Packing 포함 시) 기준
pk = cf[cf.family == "Packing"]
S["packing_ok_over_woq"] = quant(pk.ok_ratio_woq, nd=3)
fi = cf[cf.family == "Final Inspection Q.C."]
S["final_insp_ok_over_woq"] = quant(fi.ok_ratio_woq, nd=3)
S["case_total_ok_over_woq_per_row_sumdiv"] = None

# A6 불량/재작업 (공정군별)
rj = d.groupby("family").agg(rows=("family", "size"), ok=("qty_ok", "sum"), rej=("qty_rej", "sum"), mrb=("qty_mrb", "sum"),
                              rows_with_rej=("qty_rej", lambda x: int((x > 0).sum()))).reset_index()
rj["reject_pct"] = (rj.rej / (rj.ok + rj.rej) * 100).round(2)
rj["share_of_total_rej_pct"] = (rj.rej / rj.rej.sum() * 100).round(1)
rj["is_qc"] = rj.family.str.contains(r"Q\.C\.|Inspection")
rj.sort_values("rej", ascending=False).to_csv(OUT / "4tu_reject_by_family.csv", index=False, encoding="utf-8-sig")
tot_ok, tot_rej, tot_mrb = int(d.qty_ok.sum()), int(d.qty_rej.sum()), int(d.qty_mrb.sum())
S["reject_total"] = {"ok": tot_ok, "rej": tot_rej, "mrb": tot_mrb, "reject_pct_of_ok_plus_rej": round(tot_rej / (tot_ok + tot_rej) * 100, 3)}
S["reject_qc_share_pct"] = round(float(rj[rj.is_qc].rej.sum() / rj.rej.sum() * 100), 1)
# 검사 공정만 분모로 한 불량률(같은 부품이 여러 공정에서 중복 집계되는 것을 피함)
qcr = rj[rj.is_qc]
S["reject_pct_qc_only"] = round(float(qcr.rej.sum() / (qcr.ok.sum() + qcr.rej.sum()) * 100), 2)
S["mrb_by_family_top"] = rj.sort_values("mrb", ascending=False).head(5)[["family", "mrb"]].to_dict("records")
# 작업지시당 불량률
cases["rej_pct"] = cases.rej / (cases.ok + cases.rej).replace(0, np.nan) * 100
S["orders_with_reject_pct"] = round(float((cases.rej > 0).mean() * 100), 1)
S["order_reject_rate_pct_quantiles_among_with_reject"] = quant(cases[cases.rej > 0].rej_pct)
S["order_reject_count_among_with_reject"] = quant(cases[cases.rej > 0].rej, nd=1)
# 불량이 나오는 보고 행의 불량 수 분포
rr = d[d.qty_rej > 0]
S["reject_rows"] = {"n": len(rr), "qty_quantiles": quant(rr.qty_rej, nd=1)}
by_part = cases.groupby("part").agg(orders=("rej", "size"), ok=("ok", "sum"), rej=("rej", "sum"))
by_part["rej_pct"] = (by_part.rej / (by_part.ok + by_part.rej) * 100).round(2)
by_part.sort_values("rej", ascending=False).head(10).to_csv(OUT / "4tu_reject_by_part_top10.csv", encoding="utf-8-sig")

# A4 개당 사이클타임 / 셋업시간
dm = dd[(dd.qty_ok > 0) & (dd.span_min > 0)].copy()
dm["min_per_pc"] = dm.span_min / dm.qty_ok
ct = []
for f, g in dm.groupby("family"):
    if len(g) >= 20:
        r = quant(g.min_per_pc, nd=2); r["family"] = f; r["qty_median"] = float(g.qty_ok.median()); ct.append(r)
ct = pd.DataFrame(ct).sort_values("n", ascending=False)
ct = ct[["family"] + [c for c in ct.columns if c != "family"]]
ct.to_csv(OUT / "4tu_cycle_min_per_piece_by_family.csv", index=False, encoding="utf-8-sig")
# 로그정규 적합
fits = []
for f, g in dm.groupby("family"):
    if len(g) >= 40:
        sh, loc, sc = stats.lognorm.fit(g.min_per_pc, floc=0)
        fits.append({"family": f, "n": len(g), "lognorm_sigma": round(sh, 3), "lognorm_median_min": round(sc, 2)})
pd.DataFrame(fits).to_csv(OUT / "4tu_cycle_lognorm_fit.csv", index=False, encoding="utf-8-sig")
S["cycle_min_per_piece_all_machining"] = quant(dm[~dm.is_qc].min_per_pc)
S["cycle_min_per_piece_qc"] = quant(dm[dm.is_qc].min_per_pc)
# 한 번에 보고하는 수량(배치) 분포
S["d_report_qty_when_gt0"] = quant(dd[dd.qty_ok > 0].qty_ok, nd=1)
# 셋업
ss = d[d["Report Type"] == "S"]
sett = []
for f, g in ss.groupby("family"):
    if len(g) >= 15:
        r = quant(g.span_min, nd=1); r["family"] = f; sett.append(r)
pd.DataFrame(sett).sort_values("n", ascending=False).to_csv(OUT / "4tu_setup_min_by_family.csv", index=False, encoding="utf-8-sig")
S["setup_rows_min"] = quant(ss.span_min, nd=1)
S["setup_total_per_case_min"] = quant(ss.groupby("Case ID").span_min.sum(), nd=1)
S["setup_cases_pct"] = round(float(ss["Case ID"].nunique() / len(cases) * 100), 1)
# 작업지시당 가공시간 합 / 수량
cases["span_h_per_pc"] = cases.span_h / cases.woq
S["case_total_span_hours"] = quant(cases.span_h)
S["case_total_span_hours_per_piece"] = quant(cases.span_h_per_pc, nd=3)
# 한 작업지시 안에서 하나의 공정에 재진입 (같은 공정 레코드 여러 개)
reps = d.groupby(["Case ID", "family"]).size()
S["rows_per_case_family"] = quant(reps, nd=1)

# A7 작업자/설비 부하
wl = d.groupby("Worker ID").agg(rows=("Worker ID", "size"), span_h=("span_min", lambda x: x.sum() / 60), orders=("Case ID", "nunique"),
                                resources=("Resource", "nunique"), days=("s", lambda x: x.dt.normalize().nunique()))
wl["h_per_active_day"] = wl.span_h / wl.days
wl.sort_values("span_h", ascending=False).round(2).to_csv(OUT / "4tu_worker_load.csv", encoding="utf-8-sig")
S["workers"] = {"n": len(wl), "rows": quant(wl.rows, nd=1), "span_hours": quant(wl.span_h, nd=1), "orders": quant(wl.orders, nd=1),
                "resources_per_worker": quant(wl.resources, nd=1), "active_days": quant(wl.days, nd=1), "h_per_active_day": quant(wl.h_per_active_day)}
rl = d.groupby("Resource").agg(rows=("Resource", "size"), span_h=("span_min", lambda x: x.sum() / 60), orders=("Case ID", "nunique"),
                               workers=("Worker ID", "nunique"), days=("s", lambda x: x.dt.normalize().nunique()))
rl["h_per_active_day"] = rl.span_h / rl.days
nd_all = (d.e.max().normalize() - d.s.min().normalize()).days + 1
S["calendar_days"] = int(nd_all)
rl["util_vs_calendar_pct"] = rl.span_h / (nd_all * 24) * 100
rl.sort_values("span_h", ascending=False).round(2).to_csv(OUT / "4tu_resource_load.csv", encoding="utf-8-sig")
mach = rl[rl.index.str.contains("Machine")]
S["machines"] = {"n": len(mach), "span_hours": quant(mach.span_h, nd=1), "orders": quant(mach.orders, nd=1), "workers_per_machine": quant(mach.workers, nd=1),
                 "util_vs_calendar_pct": quant(mach.util_vs_calendar_pct), "h_per_active_day": quant(mach.h_per_active_day)}
# 같은 작업자가 한 작업지시에서 연속 근무 vs 교대(작업자 교체 횟수)
d["worker_change"] = (d.groupby("Case ID")["Worker ID"].shift() != d["Worker ID"]) & (d.groupby("Case ID").cumcount() > 0)
S["worker_change_per_case"] = quant(d.groupby("Case ID").worker_change.sum(), nd=1)
S["workers_per_case"] = quant(cases.n_workers, nd=1)

# A8 일별/요일/시간
d["dow"] = d.s.dt.dayofweek
d["hour"] = d.s.dt.hour
cases["end_date"] = cases.last_end.dt.normalize()
daily = pd.DataFrame({"cases_completed": cases.groupby("end_date").size(),
                      "rows_started": d.groupby(d.s.dt.normalize()).size(),
                      "qty_ok_reported": dd.groupby(dd.e.dt.normalize()).qty_ok.sum()}).fillna(0).astype(int)
daily.index.name = "date"
daily.to_csv(OUT / "4tu_daily.csv", encoding="utf-8-sig")
daily["dow"] = daily.index.dayofweek
wk = daily[daily.dow < 5]
S["daily_cases_completed_all_days"] = quant(daily.cases_completed.reindex(pd.date_range(daily.index.min(), daily.index.max()), fill_value=0))
S["daily_cases_completed_weekdays"] = quant(wk.cases_completed.reindex([x for x in pd.date_range(daily.index.min(), daily.index.max()) if x.dayofweek < 5], fill_value=0))
S["daily_rows"] = quant(daily.rows_started)
S["daily_qty_ok_reported_weekday"] = quant(wk.qty_ok_reported, nd=0)
S["weeks_covered"] = round(nd_all / 7, 1)
S["cases_per_week"] = round(len(cases) / (nd_all / 7), 1)
wd = d.groupby("dow").agg(rows=("dow", "size"), hours=("span_min", lambda x: x.sum() / 60)).reindex(range(7)).fillna(0)
wd["rows_share_pct"] = (wd.rows / wd.rows.sum() * 100).round(1)
wd.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
wd.round(1).to_csv(OUT / "4tu_weekday.csv", encoding="utf-8-sig")
dh = d[~((d.s.dt.hour == 0) & (d.s.dt.minute == 0))]            # 날짜만 있는 기록(00:00) 제외
hr = pd.crosstab(dh.hour, dh["Report Type"]).reindex(range(24), fill_value=0)
hr["all"] = hr.sum(axis=1)
hr["share_pct"] = (hr["all"] / hr["all"].sum() * 100).round(1)
hr.to_csv(OUT / "4tu_hour_start.csv", encoding="utf-8-sig")
S["hour_excluding_midnight_stamp_rows"] = int(len(dh))
ce = dd[~((dd.e.dt.hour == 0) & (dd.e.dt.minute == 0))]
S["hour_of_completion_top3"] = ce.e.dt.hour.value_counts(normalize=True).head(3).round(3).to_dict()
S["weekend_row_share_pct"] = round(float(d.dow.isin([5, 6]).mean() * 100), 1)

# A9 리드타임
S["lead_days_all"] = quant(cases.lead_days)
S["lead_days_with_packing"] = quant(cases[[r[-1] == "Packing" for r in routes.reindex(cases.index)]].lead_days)
S["lead_days_per_family_step"] = quant(cases.lead_days / cases.n_family)
cases["touch_ratio"] = cases.span_h / (cases.lead_days * 24).replace(0, np.nan)
S["touch_time_over_leadtime_pct"] = quant(cases.touch_ratio * 100)
# 공정 간 대기 (앞 공정 종료 ~ 다음 공정군 시작)
wt = []
for cid, g in d.groupby("Case ID"):
    g = g.sort_values(["s", "e"])
    prev_f, prev_end = None, None
    for f, s_, e_ in zip(g.family, g.s, g.e):
        if prev_f is not None and f != prev_f:
            wt.append((e_ if False else s_ - prev_end).total_seconds() / 3600)
        prev_f, prev_end = f, max(e_, prev_end) if prev_end is not None and prev_f == f else e_
wt = pd.Series(wt)
S["gap_between_families_hours"] = quant(wt[wt >= 0])
S["gap_between_families_neg_pct"] = round(float((wt < 0).mean() * 100), 1)
cases.round(3).to_csv(OUT / "4tu_cases.csv", encoding="utf-8-sig")
pd.DataFrame([quant(cases.lead_days) | {"metric": "lead_days"}, quant(cases.woq, nd=1) | {"metric": "order_qty"},
              quant(cases.n_family, nd=1) | {"metric": "n_family"}, quant(cases.rows, nd=1) | {"metric": "rows_per_case"},
              quant(cases.span_h) | {"metric": "span_hours"}]).to_csv(OUT / "4tu_case_quantiles.csv", index=False, encoding="utf-8-sig")
save_json(S, "4tu_summary.json")

# ---------- 그림 ----------
fig, ax = plt.subplots(2, 3, figsize=(16, 8.5))
ax[0, 0].hist(cases.woq.clip(upper=500), bins=40, color="#4C78A8")
ax[0, 0].axvline(cases.woq.median(), color="r", ls="--"); ax[0, 0].set_title(f"작업지시 수량 (중앙값 {cases.woq.median():.0f}, 500 초과 묶음)")
ax[0, 0].set_xlabel("개"); ax[0, 0].set_ylabel("작업지시 수")
ax[0, 1].hist(cases.n_family, bins=range(1, int(cases.n_family.max()) + 2), color="#F58518", align="left")
ax[0, 1].set_title(f"작업지시당 공정군 수 (중앙값 {cases.n_family.median():.0f})"); ax[0, 1].set_xlabel("공정군 수")
ax[0, 2].hist(cases.lead_days.clip(upper=60), bins=40, color="#54A24B")
ax[0, 2].axvline(cases.lead_days.median(), color="r", ls="--"); ax[0, 2].set_title(f"리드타임 (중앙값 {cases.lead_days.median():.1f}일, 60일 초과 묶음)"); ax[0, 2].set_xlabel("일")
top = ct.head(10).iloc[::-1]
ax[1, 0].barh(top.family, top.p50, xerr=[top.p50 - top.p25, top.p75 - top.p50], color="#B279A2")
ax[1, 0].set_title("개당 시간 (분/개) 중앙값, 막대=25~75%"); ax[1, 0].tick_params(axis="y", labelsize=8)
ax[1, 1].bar(wd.index, wd.rows_share_pct, color="#4C78A8"); ax[1, 1].set_title("요일별 공정 기록 시작 비율(%)")
ax[1, 2].bar(hr.index, hr.share_pct, color="#E45756"); ax[1, 2].set_title("시작 시각 분포 (00:00 날짜만 있는 기록 제외)"); ax[1, 2].set_xlabel("시")
plt.tight_layout(); plt.savefig(OUT / "fig_4tu_overview.png", dpi=110); plt.close()

fig, ax = plt.subplots(1, 2, figsize=(14, 5))
r10 = rj.sort_values("rej", ascending=False).head(10).iloc[::-1]
ax[0].barh(r10.family, r10.rej, color=["#E45756" if q else "#4C78A8" for q in r10.is_qc]); ax[0].set_title("공정군별 불량 수량 (빨강=검사)"); ax[0].tick_params(axis="y", labelsize=8)
sub = pr_s.head(10).iloc[::-1]
ax[1].barh([f"{a[:18]}>{b[:18]}" for a, b in zip(sub["from"], sub["to"])], sub.ratio_median, color="#54A24B")
ax[1].axvline(1, color="k", lw=.8); ax[1].set_title("인접 공정 간 수량비 (뒤/앞) 중앙값"); ax[1].tick_params(axis="y", labelsize=7)
plt.tight_layout(); plt.savefig(OUT / "fig_4tu_reject_flow.png", dpi=110); plt.close()
print("done 4tu")
print(rt.T.to_string())
