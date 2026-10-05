"""D. Haas NGC SHDR(zip, ST-40 선반 4.3시간) + probe/current XML 프로파일링"""
import re
import zipfile
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET

from common_prof import DATA, OUT, quant, save_json, setup_font

plt = setup_font()
H = DATA / "haas_ngc_mtconnect"
S = {}

SENS = ["SpindleMotorTemp", "ElectronicsTemp", "AirPressure", "DcVolt", "AcLine", "CoolantPressure", "SpindleLoadPct", "Sload", "Xload", "Zload",
        "Bload", "Cload", "ToolLoad", "CPU", "CPUAverage", "SpindleActualRPM", "FeedRate", "accelerometerX", "accelerometerY", "accelerometerZ",
        "ANALOG_AIR_PRESSURE", "SPINDLE_MOTOR_TEMPERATURE", "HPU_1_HYDRAULIC_PRESSURE", "CHIP_CONVEYOR_CURRENT", "COOLANT_LEVEL",
        "AMBIENT_TEMPERATURE", "OIL_TEMP_HPU_1", "NextSpindleLubeTime", "NextAxisLubeTime"]
STATE = ["RunningFlag", "BeaconStatus", "alarm0", "message", "AlarmSafetyLevel", "ProgramName", "ThisCycle", "LastCycle", "TimeRemaining",
         "ToolUsage", "ToolHoleCount", "ActiveTool", "FeedTime", "TotalTime", "SpindleDirection", "ActiveIconsList"]
TS_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}$")


def secs(t):
    return int(t[11:13]) * 3600 + int(t[14:16]) * 60 + int(t[17:19]) + int(t[20:23]) / 1000.0


vals = defaultdict(list)           # key -> [(sec, float)]
vals_run = defaultdict(list)       # key -> [(float, runflag)]
st = defaultdict(list)             # key -> [(sec, value str)]
keys_all = Counter()
rec_t = []
run_flag = "PROGRAM_STATUS_OFF"
n_rec = 0
t_first = t_last = None
with zipfile.ZipFile(H / "shdr_1665494517.txt.zip") as z:
    with z.open("1665494517.txt") as f:
        for raw in f:
            for ch in raw.split(b"\x02"):
                s = ch.decode("utf-8", "ignore").strip("\x03\r\n ").replace("\\n", "")
                p = s.split("|")
                if len(p) < 3 or not TS_RE.match(p[0]):
                    continue
                n_rec += 1
                t_first = t_first or p[0]
                t_last = p[0]
                sec = secs(p[0])
                rec_t.append(sec)
                for k, v in zip(p[1::2], p[2::2]):
                    keys_all[k] += 1
                    if k in SENS:
                        try:
                            x = float(v)
                        except ValueError:
                            continue
                        vals[k].append((sec, x))
                        vals_run[k].append((x, run_flag))
                    elif k in STATE:
                        if k == "RunningFlag":
                            run_flag = v
                        st[k].append((sec, v))

S["records"] = n_rec
S["period"] = [t_first, t_last]
S["span_h"] = round((secs(t_last) - secs(t_first)) / 3600, 2)
S["distinct_keys_incl_noise"] = len(keys_all)
S["keys_with_part_in_name"] = [k for k in keys_all if "part" in k.lower()]
S["keys_with_cycle_in_name"] = [k for k in keys_all if "cycle" in k.lower()]
S["keys_with_count_in_name"] = [k for k in keys_all if "count" in k.lower()]
rt = np.array(rec_t)
d_ms = np.diff(rt) * 1000
d_ms = d_ms[d_ms >= 0]
S["record_interval_ms"] = quant(pd.Series(d_ms), nd=1)
S["records_per_second_mean"] = round(n_rec / (rt[-1] - rt[0]), 1)

# 센서별 분포 + 갱신 간격
rows = []
for k in SENS:
    if k not in vals:
        continue
    a = np.array(vals[k])
    x = pd.Series(a[:, 1])
    dt = np.diff(a[:, 0]) * 1000
    r = {"key": k, "n": len(x), "mean": round(x.mean(), 2)}
    for q in [.01, .05, .25, .5, .75, .95, .99]:
        r[f"p{int(q*100):02d}"] = round(float(x.quantile(q)), 2)
    r["min"], r["max"] = round(float(x.min()), 2), round(float(x.max()), 2)
    r["n_unique"] = int(x.nunique())
    r["update_dt_ms_median"] = round(float(np.median(dt[dt >= 0])), 1) if len(dt) else None
    r["update_dt_ms_p95"] = round(float(np.percentile(dt[dt >= 0], 95)), 1) if len(dt) else None
    rows.append(r)
sens = pd.DataFrame(rows)
sens.to_csv(OUT / "haas_sensor_quantiles.csv", index=False)
# 가동 상태별(RUNNING vs 그 외) 부하/온도
rr = []
for k in ["SpindleLoadPct", "Sload", "Xload", "Zload", "ToolLoad", "SpindleActualRPM", "FeedRate", "SpindleMotorTemp", "AirPressure", "DcVolt", "CPU"]:
    if k in vals_run:
        df = pd.DataFrame(vals_run[k], columns=["x", "flag"])
        df["grp"] = np.where(df.flag == "PROGRAM_STATUS_RUNNING", "RUNNING", "NOT_RUNNING")
        for g, gg in df.groupby("grp"):
            rr.append({"key": k, "group": g, "n": len(gg), "p05": gg.x.quantile(.05), "p50": gg.x.median(), "p95": gg.x.quantile(.95), "max": gg.x.max()})
pd.DataFrame(rr).round(2).to_csv(OUT / "haas_sensor_by_running.csv", index=False)

# RunningFlag / 비콘 시간 비율
def seg(seq, end_t):
    out = []
    for (t0, v), (t1, _) in zip(seq, seq[1:] + [(end_t, None)]):
        out.append((v, t1 - t0, t0))
    return out


tend = rt[-1]
for k in ["RunningFlag", "BeaconStatus"]:
    seq = []
    for t, v in st[k]:
        if not seq or seq[-1][1] != v:
            seq.append((t, v))
    sg = seg(seq, tend)
    tot = sum(x[1] for x in sg)
    S[k + "_time_share_pct"] = {v: round(sum(x[1] for x in sg if x[0] == v) / tot * 100, 2) for v in {x[0] for x in sg}}
    S[k + "_changes"] = len(seq)
    if k == "RunningFlag":
        runs = [x for x in sg if x[0] == "PROGRAM_STATUS_RUNNING"]
        S["running_segments"] = {"n": len(runs), "duration_s": quant(pd.Series([x[1] for x in runs]), nd=1)}
        gaps = [b[2] - (a[2] + a[1]) for a, b in zip(runs, runs[1:])]
        S["gap_between_running_segments_s"] = quant(pd.Series(gaps), nd=1)
        # 연속 구간 병합(공백 10초 이하는 같은 사이클로 간주)
        merged, cur = [], None
        for v, dur, t0 in runs:
            if cur and t0 - (cur[0] + cur[1]) <= 10:
                cur = (cur[0], t0 + dur - cur[0])
            else:
                if cur:
                    merged.append(cur)
                cur = (t0, dur)
        merged.append(cur)
        S["running_segments_merged_10s"] = {"n": len(merged), "duration_s": quant(pd.Series([m[1] for m in merged]), nd=1)}
        pd.DataFrame([{"start_s": r[2], "dur_s": r[1]} for r in runs]).to_csv(OUT / "haas_running_segments.csv", index=False)
# 비콘 분포 표
bs = []
seq = []
for t, v in st["BeaconStatus"]:
    if not seq or seq[-1][1] != v:
        seq.append((t, v))
for v in sorted({x[1] for x in seq}):
    ds = [x[1] for x in seg(seq, tend) if x[0] == v]
    bs.append({"beacon": v, "visits": len(ds), "total_min": round(sum(ds) / 60, 1), "median_s": round(float(np.median(ds)), 1)})
pd.DataFrame(bs).to_csv(OUT / "haas_beacon.csv", index=False)

# ThisCycle / LastCycle
tc = [(t, int(v)) for t, v in st["ThisCycle"] if re.fullmatch(r"-?\d+", v)]
S["ThisCycle_samples"] = len(tc)
resets = [(a, b) for a, b in zip(tc, tc[1:]) if b[1] < a[1] - 500]
S["ThisCycle_resets"] = len(resets)
S["ThisCycle_value_before_reset"] = quant(pd.Series([a[1] for a, b in resets]), nd=0) if resets else None
if len(tc) > 3:
    dts = np.diff([t for t, _ in tc])
    dv = np.diff([v for _, v in tc])
    ok = (dts > 0) & (dv > 0) & (dts < 5)
    S["ThisCycle_units_per_second_median"] = round(float(np.median(dv[ok] / dts[ok])), 2)
    S["ThisCycle_max"] = int(max(v for _, v in tc))
lc = [v for t, v in st["LastCycle"]]
S["LastCycle_values"] = dict(Counter(lc).most_common(10))
S["LastCycle_changes"] = len(lc)
S["ToolHoleCount_values"] = dict(Counter(v for _, v in st["ToolHoleCount"]).most_common(5))
S["ToolUsage_n_values"] = len({v for _, v in st["ToolUsage"]})
S["ActiveTool_changes"] = len(st["ActiveTool"])
S["ActiveTool_dist"] = dict(Counter(v for _, v in st["ActiveTool"]).most_common(12))
S["FeedTime_TotalTime_sample"] = [st["FeedTime"][0][1], st["FeedTime"][-1][1], st["TotalTime"][0][1], st["TotalTime"][-1][1]] if st["FeedTime"] else None
S["ProgramName_values"] = dict(Counter(v for _, v in st["ProgramName"]))
# 알람/메시지
S["alarm0_changes"] = [(round(t - rt[0]), v) for t, v in st["alarm0"]]
S["AlarmSafetyLevel_values"] = dict(Counter(v for _, v in st["AlarmSafetyLevel"]))
msgs = Counter(v.strip(">").strip() for _, v in st["message"] if v.strip())
S["message_top"] = msgs.most_common(10)
S["message_events"] = int(sum(msgs.values()))
icons = Counter()
for _, v in st["ActiveIconsList"]:
    for i in v.split(","):
        icons[i.strip()] += 1
S["ActiveIcons_top"] = icons.most_common(12)

# ---------- probe / current XML ----------
probe = {}
for p in sorted(H.glob("*_probe.xml")):
    root = ET.fromstring(p.read_text(encoding="utf-8", errors="ignore").strip())
    items = [e for e in root.iter() if e.tag.split("}")[-1] == "DataItem"]
    types = Counter(e.get("type") for e in items)
    probe[p.name] = {"data_items": len(items), "category": dict(Counter(e.get("category") for e in items)),
                     "has_PART_COUNT": any("PART" in (e.get("type") or "") for e in items),
                     "has_PROGRAM": types.get("PROGRAM", 0), "has_EXECUTION": types.get("EXECUTION", 0), "has_CONTROLLER_MODE": types.get("CONTROLLER_MODE", 0),
                     "has_ALARM_condition": sum(1 for e in items if e.get("category") == "CONDITION"),
                     "types_part_cycle": [t for t in types if t and ("PART" in t or "CYCLE" in t or "COUNT" in t)],
                     "n_types": len(types)}
S["probe"] = probe
cur = {}
for p in sorted(H.glob("*_current.xml")):
    root = ET.fromstring(p.read_text(encoding="utf-8", errors="ignore").strip())
    vals_c = {}
    for e in root.iter():
        tag = e.tag.split("}")[-1]
        if tag in ("Execution", "ControllerMode", "PartCount", "PartCountAll", "Availability", "EmergencyStop", "Program") and e.text:
            vals_c[tag] = e.text.strip()
    cur[p.name] = vals_c
S["current_examples"] = cur
save_json(S, "haas_summary.json")

# ---------- 그림 ----------
fig, ax = plt.subplots(2, 3, figsize=(16, 8.5))
for a, k, c in zip(ax.flat, ["SpindleMotorTemp", "AirPressure", "DcVolt", "SpindleLoadPct", "Sload", "Xload"], ["#E45756", "#4C78A8", "#54A24B", "#F58518", "#B279A2", "#72B7B2"]):
    if k in vals:
        x = np.array(vals[k])[:, 1]
        a.hist(x, bins=50, color=c)
        a.axvline(np.median(x), color="k", ls="--", lw=.8)
        a.set_title(f"{k} (중앙값 {np.median(x):.1f}, n={len(x)})")
plt.tight_layout(); plt.savefig(OUT / "fig_haas_sensors.png", dpi=110); plt.close()
print("done haas", n_rec)
