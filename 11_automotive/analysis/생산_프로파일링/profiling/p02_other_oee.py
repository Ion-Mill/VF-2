"""B. 벽돌 라인 정지 기록(zenodo 17855209) + 블로우 성형 라인(zenodo 17116973) 프로파일링"""
import numpy as np
import pandas as pd
from scipy import stats

from common_prof import DATA, OUT, quant, save_json, setup_font

plt = setup_font()
BR = DATA / "other_oee" / "zenodo_17855209_oee_clay"
S = {}


def load_dt(name):
    d = pd.read_csv(BR / name, low_memory=False)
    d = d.loc[:, ~d.columns.str.startswith("Unnamed")].dropna(how="all")
    d.columns = ["date", "product", "group", "stop", "type", "location", "extra", "start", "end", "dur"]
    d["start"] = pd.to_datetime(d.start, errors="coerce")   # afterLSS 파일에는 헤더가 한 번 더 들어 있음
    d["end"] = pd.to_datetime(d.end, errors="coerce")
    d["dur"] = pd.to_numeric(d.dur, errors="coerce")
    d = d.dropna(subset=["start", "dur"])
    return d.sort_values("start").reset_index(drop=True)


def fit(x):
    """로그정규/와이블/지수 적합(위치=0). KS 통계량과 AIC 포함."""
    x = x[x > 0]
    r = {}
    sh, loc, sc = stats.lognorm.fit(x, floc=0)
    ll = stats.lognorm.logpdf(x, sh, 0, sc).sum()
    r["lognorm"] = {"sigma": round(sh, 3), "mu_ln": round(float(np.log(sc)), 3), "median": round(sc, 2),
                    "ks": round(stats.kstest(x, "lognorm", args=(sh, 0, sc)).statistic, 3), "aic": round(2 * 2 - 2 * ll, 1)}
    c, loc, sc = stats.weibull_min.fit(x, floc=0)
    ll = stats.weibull_min.logpdf(x, c, 0, sc).sum()
    r["weibull"] = {"shape_k": round(c, 3), "scale": round(sc, 2),
                    "ks": round(stats.kstest(x, "weibull_min", args=(c, 0, sc)).statistic, 3), "aic": round(2 * 2 - 2 * ll, 1)}
    loc_, sc = stats.expon.fit(x, floc=0)
    ll = stats.expon.logpdf(x, 0, sc).sum()
    r["expon"] = {"mean": round(sc, 2), "ks": round(stats.kstest(x, "expon", args=(0, sc)).statistic, 3), "aic": round(2 * 1 - 2 * ll, 1)}
    return r


rows_q = []
for tag, fn, oee in [("before", "DowntimeDataset.csv", "OEEdataset.csv"), ("afterLSS", "DowntimeDataset_afterLSS.csv", "OEEdataset_afterLSS.csv")]:
    d = load_dt(fn)
    s = {"events": len(d), "period": [str(d.start.min()), str(d.start.max())], "days": int(d.start.dt.date.nunique()),
         "span_days": int((d.start.max().normalize() - d.start.min().normalize()).days + 1)}
    s["dur_all"] = quant(d.dur)
    s["by_type"] = {t: quant(g.dur) for t, g in d.groupby("type")}
    s["by_group"] = {t: quant(g.dur) for t, g in d.groupby("group")}
    s["group_share_events_pct"] = (d.group.value_counts(normalize=True) * 100).round(1).to_dict()
    s["group_share_minutes_pct"] = (d.groupby("group").dur.sum() / d.dur.sum() * 100).round(1).to_dict()
    s["type_share_events_pct"] = (d.type.value_counts(normalize=True) * 100).round(1).to_dict()
    s["location_share_events_pct"] = (d.location.value_counts(normalize=True) * 100).round(1).head(8).to_dict()
    un = d[d.type == "Unplanned"]
    s["unplanned_events"] = len(un)
    s["unplanned_per_calendar_day"] = round(len(un) / s["span_days"], 2)
    s["unplanned_per_day_with_data"] = quant(un.groupby(un.start.dt.date).size(), nd=1)
    s["unplanned_min_per_day"] = quant(un.groupby(un.start.dt.date).dur.sum(), nd=1)
    # 분포 적합
    s["fit_unplanned"] = fit(un.dur)
    s["fit_failure"] = fit(d[d.group == "FAILURE"].dur)
    s["fit_all"] = fit(d.dur)
    s["failure_share_of_unplanned_events_pct"] = round(float((un.group == "FAILURE").mean() * 100), 1)
    # 도착 간격 (비계획 정지): 전체 / 같은 날 안
    gaps = un.start.diff().dt.total_seconds().dropna() / 60
    same_day = un.start.dt.date.eq(un.start.dt.date.shift()).iloc[1:]
    s["interarrival_unplanned_min_all"] = quant(gaps)
    s["interarrival_unplanned_min_same_day"] = quant(gaps[same_day.values])
    s["interarrival_cv_same_day"] = round(float(gaps[same_day.values].std() / gaps[same_day.values].mean()), 2)
    s["fit_interarrival_same_day"] = fit(gaps[same_day.values])
    fl = d[d.group == "FAILURE"]
    fg = fl.start.diff().dt.total_seconds().dropna() / 60
    s["failure_interarrival_min"] = quant(fg)
    # 시작 시각(정지가 일어난 시간대)
    hr = d.start.dt.hour.value_counts().sort_index().reindex(range(24), fill_value=0)
    hu = un.start.dt.hour.value_counts().sort_index().reindex(range(24), fill_value=0)
    s["hour_all_top5"] = (hr / hr.sum() * 100).round(1).sort_values(ascending=False).head(5).to_dict()
    s["hour_range_with_data"] = [int(d.start.dt.hour.min()), int(d.start.dt.hour.max())]
    dw = d.start.dt.dayofweek.value_counts().sort_index().reindex(range(7), fill_value=0)
    s["weekday_share_pct"] = dict(zip(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], (dw / dw.sum() * 100).round(1)))
    pd.DataFrame({"hour": range(24), "events_all": hr.values, "events_unplanned": hu.values,
                  "share_all_pct": (hr / hr.sum() * 100).round(2).values}).to_csv(OUT / f"brick_hour_{tag}.csv", index=False)
    gh = d.groupby("group").dur.describe(percentiles=[.1, .5, .9]).round(2)
    gh["share_events_pct"] = (d.group.value_counts(normalize=True) * 100).round(1)
    gh["share_minutes_pct"] = (d.groupby("group").dur.sum() / d.dur.sum() * 100).round(1)
    gh.to_csv(OUT / f"brick_by_group_{tag}.csv", encoding="utf-8-sig")
    top_stop = d.groupby(["group", "stop"]).dur.agg(["size", "median", "sum"]).sort_values("size", ascending=False).head(15).round(1)
    top_stop.to_csv(OUT / f"brick_top_stops_{tag}.csv", encoding="utf-8-sig")
    # 일별 가동률
    o = pd.read_csv(BR / oee).dropna(how="all")
    o = o.loc[:, ~o.columns.str.startswith("Unnamed")]
    o.columns = ["date", "OEE", "avail", "perf", "qual", "good_s", "slow_s", "planned_s", "ideal_qty", "plan_stop_s", "unplan_stop_s", "good_qty", "total_qty"]
    o["date"] = pd.to_datetime(o.date, format="%m/%d/%y", errors="coerce")
    o = o.dropna(subset=["date"])
    for c in o.columns[1:]:
        o[c] = pd.to_numeric(o[c], errors="coerce")
    s["oee_days"] = len(o)
    for c in ["avail", "perf", "qual", "OEE"]:
        s[f"daily_{c}"] = quant(o[c], nd=3)
    s["daily_reject_pct"] = quant((1 - o.good_qty / o.total_qty) * 100, nd=3)
    s["daily_unplanned_share_of_planned_pct"] = quant(o.unplan_stop_s / o.planned_s * 100, nd=1)
    s["daily_planned_time_h"] = quant(o.planned_s / 3600, nd=1)
    s["daily_total_qty"] = quant(o.total_qty, nd=0)
    s["avail_below_0.5_days_pct"] = round(float((o.avail < .5).mean() * 100), 1)
    s["avail_weekday_median"] = o.groupby(o.date.dt.dayofweek).avail.median().round(3).to_dict()
    o.to_csv(OUT / f"brick_daily_oee_{tag}.csv", index=False)
    S[tag] = s
    if tag == "before":
        D, U, O = d, un, o

# 비교용 요약표
cmp = []
for k in ["events", "unplanned_events", "unplanned_per_calendar_day"]:
    cmp.append({"metric": k, "before": S["before"][k], "afterLSS": S["afterLSS"][k]})
for k in ["dur_all", "daily_avail", "daily_OEE"]:
    cmp.append({"metric": k + "_median", "before": S["before"][k]["p50"], "afterLSS": S["afterLSS"][k]["p50"]})
pd.DataFrame(cmp).to_csv(OUT / "brick_before_after.csv", index=False)

# ---- 블로우 성형 라인 (xlsx) ----
bx = DATA / "other_oee" / "zenodo_17116973_blow" / "blow_molding_downtime.xlsx"
raw = pd.read_excel(bx, sheet_name=None, header=None)
b = {}
p = raw["Production data"].dropna(how="all").reset_index(drop=True)
p = p.iloc[1:].reset_index(drop=True)
p.columns = ["date", "leader", "tech1", "tech2", "cycle_s", "hourly_target", "target_pcs", "actual", "good", "reject", "planned_min", "run_min", "good_min",
             "reject_min", "mould_changes", "break_min", "downtime", "logged_downtime", "others", "avail", "perf", "qual", "oee", "remarks"]
for c in p.columns[1:23]:
    p[c] = pd.to_numeric(p[c], errors="coerce")
p["date"] = pd.to_datetime(p.date)
b["production_rows"] = len(p)
b["production_period"] = [str(p.date.min()), str(p.date.max())]
b["shifts_per_day_median"] = float(p.groupby("date").size().median())
b["days"] = int(p.date.nunique())
b["cycle_s"] = quant(p.cycle_s)
b["cycle_s_value_counts"] = p.cycle_s.value_counts().head(6).to_dict()
b["actual_per_shift"] = quant(p.actual, nd=0)
b["reject_pct_per_shift"] = quant(p.reject / p.actual * 100, nd=2)
b["reject_pct_total"] = round(float(p.reject.sum() / p.actual.sum() * 100), 2)
for c in ["avail", "perf", "qual", "oee"]:
    b[c] = quant(p[c], nd=3)
b["planned_min_per_shift"] = quant(p.planned_min, nd=0)
b["mould_changes_per_shift"] = quant(p.mould_changes.fillna(0), nd=2)
b["break_min_when_present"] = quant(p.break_min.dropna(), nd=1)
b["downtime_min_per_shift"] = quant(p.downtime.fillna(0), nd=1)
dt = raw["Downtime"].dropna(how="all").reset_index(drop=True)
dt = dt.iloc[1:].reset_index(drop=True)
dt.columns = ["no", "date", "shift", "group", "machine", "po", "product", "repair_min", "defect", "cause", "loss_cat"]
dt["repair_min"] = pd.to_numeric(dt.repair_min, errors="coerce")
dt["date"] = pd.to_datetime(dt.date)
b["downtime_events"] = len(dt)
b["downtime_repair_min"] = quant(dt.repair_min)
b["loss_cat_share_pct"] = (dt.loss_cat.value_counts(normalize=True) * 100).round(1).to_dict()
b["loss_cat_median_min"] = dt.groupby("loss_cat").repair_min.median().round(1).to_dict()
b["machines_n"] = int(dt.machine.nunique())
b["events_per_day"] = quant(dt.groupby("date").size(), nd=1)
b["events_per_machine_shift_day"] = quant(dt.groupby(["date", "shift", "machine"]).size(), nd=1)
b["fit_repair"] = fit(dt.repair_min.dropna())
b["po_per_day_machine"] = quant(dt.groupby(["date", "machine"]).po.nunique(), nd=1)
b["products_n"] = int(dt["product"].nunique())
dt.groupby("loss_cat").repair_min.describe(percentiles=[.1, .5, .9]).round(1).to_csv(OUT / "blow_downtime_by_loss.csv", encoding="utf-8-sig")
S["blow"] = b
save_json(S, "other_oee_summary.json")

# ---- 그림 ----
fig, ax = plt.subplots(2, 3, figsize=(16, 8.5))
x = U.dur.values
ax[0, 0].hist(np.clip(x, 0, 80), bins=40, density=True, color="#4C78A8", alpha=.8)
xs = np.linspace(.5, 80, 300)
f = S["before"]["fit_unplanned"]
ax[0, 0].plot(xs, stats.lognorm.pdf(xs, f["lognorm"]["sigma"], 0, f["lognorm"]["median"]), "r", label=f"로그정규 σ={f['lognorm']['sigma']}")
ax[0, 0].plot(xs, stats.weibull_min.pdf(xs, f["weibull"]["shape_k"], 0, f["weibull"]["scale"]), "g", label=f"와이블 k={f['weibull']['shape_k']}")
ax[0, 0].set_title("비계획 정지 길이 (분, 80분 초과 묶음)"); ax[0, 0].legend()
g = D.groupby("group").dur.sum().sort_values()
ax[0, 1].barh(g.index, g.values / 60, color="#F58518"); ax[0, 1].set_title("정지 그룹별 누적 시간(시간)")
hr = pd.read_csv(OUT / "brick_hour_before.csv")
ax[0, 2].bar(hr.hour, hr.events_all, color="#54A24B"); ax[0, 2].set_title("정지 시작 시각 분포(건)")
dw = D.start.dt.dayofweek.value_counts().sort_index().reindex(range(7), fill_value=0)
ax[1, 0].bar(["월", "화", "수", "목", "금", "토", "일"], dw.values, color="#B279A2"); ax[1, 0].set_title("요일별 정지 건수")
gp = (U.start.diff().dt.total_seconds() / 60).dropna()
gp = gp[U.start.dt.date.eq(U.start.dt.date.shift()).iloc[1:].values]
ax[1, 1].hist(np.clip(gp, 0, 240), bins=40, color="#E45756"); ax[1, 1].set_title("비계획 정지 간격 (같은 날, 분)")
ax[1, 2].hist(O.avail, bins=20, color="#4C78A8"); ax[1, 2].axvline(O.avail.median(), color="r", ls="--"); ax[1, 2].set_title(f"일별 가동률 (중앙값 {O.avail.median():.2f})")
plt.tight_layout(); plt.savefig(OUT / "fig_brick_downtime.png", dpi=110); plt.close()
print("done other_oee")
