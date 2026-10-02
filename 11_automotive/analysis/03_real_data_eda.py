"""실제 공개 데이터 3종을 열어 본다.
 (1) 4TU 가공 공장 생산 기록 (작업지시·수량·불량)
 (2) NIST 시험 공장의 CNC 설비 상태 기록 (MTConnect)
 (3) Haas NGC 제어기가 내보내는 데이터 항목 (MTConnect probe)
결과: outputs/real_data_summary.json, fig_4tu_rejects.png, fig_nist_execution.png"""
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

from common import DATA, OUT, save_json

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
res = {}

# ---------- 1. 4TU 생산 기록 ----------
df = pl.read_csv(DATA / "4tu" / "data" / "Production_Data.csv", infer_schema_length=5000)
df = df.rename({c: " ".join(c.split()) for c in df.columns})
fmt = "%Y/%m/%d %H:%M:%S%.3f"
df = df.with_columns(pl.col("Start Timestamp").str.strptime(pl.Datetime, fmt, strict=False).alias("start"),
                     pl.col("Complete Timestamp").str.strptime(pl.Datetime, fmt, strict=False).alias("end"))
df = df.with_columns(((pl.col("end") - pl.col("start")).dt.total_minutes() / 60).alias("hours"))
done, rej, mrb = int(df["Qty Completed"].sum()), int(df["Qty Rejected"].sum()), int(df["Qty for MRB"].sum())
res["4tu"] = {
    "rows": df.height, "columns": df.columns[:14],
    "work_orders": df["Case ID"].n_unique(), "activities": df["Activity"].n_unique(), "resources": df["Resource"].n_unique(),
    "machines": df.filter(pl.col("Resource").str.contains("Machine"))["Resource"].n_unique(),
    "workers": df["Worker ID"].n_unique(), "parts": df["Part Desc."].n_unique(),
    "first": str(df["start"].min()), "last": str(df["end"].max()),
    "report_type": dict(df["Report Type"].value_counts().iter_rows()),
    "qty_completed": done, "qty_rejected": rej, "qty_mrb": mrb,
    "reject_ratio_pct": round(rej / (done + rej) * 100, 2),
    "rows_with_reject": df.filter(pl.col("Qty Rejected") > 0).height,
    "orders_with_reject": df.filter(pl.col("Qty Rejected") > 0)["Case ID"].n_unique(),
    "rework_rows": df.filter(pl.col("Rework") == "Y").height,
    "events_per_order_median": float(df.group_by("Case ID").len()["len"].median()),
    "event_hours_median": round(float(df["hours"].median()), 2),
    "order_qty_median": float(df.group_by("Case ID").agg(pl.col("Work Order Qty").max())["Work Order Qty"].median()),
}
by_act = (df.group_by("Activity").agg(pl.len().alias("events"), pl.col("Qty Completed").sum().alias("done"),
                                      pl.col("Qty Rejected").sum().alias("rejected"), pl.col("hours").sum().round(1).alias("hours"))
          .with_columns((pl.col("rejected") / (pl.col("done") + pl.col("rejected")) * 100).round(2).alias("reject_pct"))
          .sort("rejected", descending=True))
by_act.write_csv(OUT / "4tu_by_activity.csv")
res["4tu"]["top_reject_activities"] = by_act.head(8).to_dicts()
by_type = df.group_by("Report Type").agg(pl.len().alias("rows"), pl.col("hours").median().round(2).alias("median_hours"), pl.col("hours").sum().round(0).alias("total_hours"))
res["4tu"]["by_report_type"] = by_type.to_dicts()
routes = df.sort("start").group_by("Case ID", maintain_order=True).agg(pl.col("Activity").unique(maintain_order=True).alias("route"))
res["4tu"]["route_len_median"] = float(routes["route"].list.len().median())
res["4tu"]["example_route"] = routes.filter(pl.col("route").list.len() == int(routes["route"].list.len().median()))["route"][0].to_list()

top = by_act.head(8).sort("rejected")
fig, ax = plt.subplots(figsize=(9, 4))
ax.barh(top["Activity"].to_list(), top["rejected"].to_list(), color="#2a78d6", height=0.55)
for i, (v, p) in enumerate(zip(top["rejected"].to_list(), top["reject_pct"].to_list())):
    ax.text(v + 2, i, f"{v}개 ({p}%)", va="center", fontsize=9)
ax.set_xlabel("불량 수량")
ax.set_title("4TU 가공 공장 기록: 공정별 불량 수량 (2012년 1~3월)", loc="left", fontsize=12)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color="#e1e0d9", linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "fig_4tu_rejects.png", dpi=130)

# ---------- 2. NIST 시험 공장 설비 상태 ----------
EXEC = {"ACTIVE", "READY", "FEED_HOLD", "STOPPED", "INTERRUPTED", "PROGRAM_STOPPED", "PROGRAM_COMPLETED", "OPTIONAL_STOP", "WAIT"}


def parse_day(path):
    day = re.search(r"-(\d{8})-", path.name).group(1)
    day0 = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
    ev, cond, keys, n = defaultdict(list), [], set(), 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            n += 1
            parts = line.rstrip("\n").split("|")
            if len(parts) < 3:
                continue
            try:
                ts = datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
            except ValueError:
                continue
            keys.add(parts[1])
            if len(parts) >= 6 and parts[2] in ("Normal", "Warning", "Fault", "Unavailable"):
                if parts[2] in ("Warning", "Fault") and ts >= day0:
                    cond.append((parts[2], parts[3], parts[-1]))
            elif parts[2] in EXEC or parts[2] in ("AUTOMATIC", "MANUAL", "MANUAL_DATA_INPUT", "EDIT", "SEMI_AUTOMATIC"):
                ev[parts[1]].append((ts, parts[2]))
    exec_key = max((k for k in ev if any(v in EXEC for _, v in ev[k])), key=lambda k: len(ev[k]), default=None)
    out = {"file": path.name, "lines": n, "keys": len(keys), "execution_key": exec_key}
    if exec_key:
        seq = [(t, v) for t, v in sorted(ev[exec_key]) if t >= day0]
        dur = Counter()
        for (t0, v0), (t1, _) in zip(seq, seq[1:]):
            dur[v0] += (t1 - t0).total_seconds() / 60
        out["execution_changes"] = len(seq)
        out["observed_minutes"] = round(sum(dur.values()), 1)
        out["minutes_by_state"] = {k: round(v, 1) for k, v in dur.most_common()}
        if seq:
            out["first_change"], out["last_change"] = str(seq[0][0]), str(seq[-1][0])
    out["warnings"] = sum(1 for c in cond if c[0] == "Warning")
    out["faults"] = sum(1 for c in cond if c[0] == "Fault")
    out["top_alarm_texts"] = Counter(f"{lvl} {code} {txt}" for lvl, code, txt in cond).most_common(6)
    return out


nist = [parse_day(p) for p in sorted((DATA / "nist" / "raw").glob("*.txt"))]
res["nist_raw_days"] = nist
tree = json.loads((DATA / "nist" / "gh_tree.json").read_text(encoding="utf-8"))
blobs = tree.get("tree", tree if isinstance(tree, list) else [])
per = Counter()
for b in blobs:
    m = re.match(r"raw/([A-Za-z]+\d+)/", b.get("path", ""))
    if m and b.get("type") == "blob":
        per[m.group(1)] += 1
res["nist_archive_day_files"] = dict(per)

show = [d for d in nist if d.get("minutes_by_state")]
if show:
    states = ["ACTIVE", "READY", "FEED_HOLD", "STOPPED", "INTERRUPTED", "PROGRAM_STOPPED", "PROGRAM_COMPLETED"]
    colors = {"ACTIVE": "#2a78d6", "READY": "#b9b7ae", "FEED_HOLD": "#eda100", "STOPPED": "#eb6834", "INTERRUPTED": "#e87ba4", "PROGRAM_STOPPED": "#1baf7a", "PROGRAM_COMPLETED": "#4a3aa7"}
    fig, ax = plt.subplots(figsize=(9, 1.2 + 0.7 * len(show)))
    for i, d in enumerate(show):
        left, tot = 0, sum(d["minutes_by_state"].values())
        for s in states:
            v = d["minutes_by_state"].get(s, 0) / tot * 100 if tot else 0
            if v:
                ax.barh(i, v, left=left, color=colors[s], height=0.5, edgecolor="#fcfcfb", linewidth=2, label=s if s not in ax.get_legend_handles_labels()[1] else None)
                if v > 7:
                    ax.text(left + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=9, color="white" if s not in ("READY", "FEED_HOLD") else "#0b0b0b")
                left += v
    ax.set_yticks(range(len(show)))
    ax.set_yticklabels([d["file"].replace(".txt", "") + f"\n(관측 {d['observed_minutes']:.0f}분)" for d in show], fontsize=9)
    ax.set_xlabel("실행 상태별 시간 비율 (%)")
    ax.set_title("NIST 시험 공장 CNC 설비의 하루 실행 상태 (MTConnect Execution)", loc="left", fontsize=12)
    ax.legend(ncol=5, fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.32))
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_nist_execution.png", dpi=130)

# ---------- 3. Haas NGC 제어기의 데이터 항목 ----------
haas = {}
for p in sorted((DATA / "haas_ngc_mtconnect").glob("*_probe.xml")):
    root = ET.fromstring(p.read_text(encoding="utf-8", errors="ignore").strip())
    items = [e for e in root.iter() if e.tag.endswith("DataItem")]
    haas[p.name] = {"data_items": len(items), "by_category": dict(Counter(e.get("category") for e in items)),
                    "event_types": sorted({e.get("type") for e in items if e.get("category") == "EVENT"}),
                    "condition_types": sorted({e.get("type") for e in items if e.get("category") == "CONDITION"})}
res["haas_ngc_probe"] = haas
for p in sorted((DATA / "haas_ngc_mtconnect").glob("vf6*_current.xml"))[:1]:
    root = ET.fromstring(p.read_text(encoding="utf-8", errors="ignore").strip())
    cur = {}
    for e in root.iter():
        tag = e.tag.split("}")[-1]
        if tag in ("Execution", "ControllerMode", "Availability", "EmergencyStop", "Program", "PathFeedrateOverride") and e.text:
            cur[tag] = e.text.strip()
    res["haas_ngc_current_example"] = {"file": p.name, "values": cur}

save_json("real_data_summary.json", res)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:7000])
