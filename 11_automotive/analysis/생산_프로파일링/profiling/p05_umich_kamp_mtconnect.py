"""E. umich / kamp(mirror) / mtconnect(공개 데모 에이전트) 쓸모 판정"""
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

from common_prof import DATA, OUT, quant, save_json

S = {}

# ---- umich ----
um = DATA / "umich"
tr = pd.read_csv(um / "train.csv")
rows = []
for i in range(1, 19):
    d = pd.read_csv(um / f"experiment_{i:02d}.csv")
    mp = d["Machining_Process"].value_counts()
    rows.append({"No": i, "rows": len(d), "sec_at_100ms": len(d) * 0.1, **{f"n_{k.replace(' ', '_')}": int(v) for k, v in mp.items()}})
ex = pd.DataFrame(rows).merge(tr, on="No")
ex.to_csv(OUT / "umich_experiments.csv", index=False)
S["umich"] = {"experiments": len(ex), "columns": int(d.shape[1]), "sampling_ms": 100,
              "duration_s_per_experiment": quant(ex.sec_at_100ms, nd=1),
              "duration_by_feedrate_median_s": ex.groupby("feedrate").sec_at_100ms.median().round(1).to_dict(),
              "completed_pct": round(float((ex.machining_finalized == "yes").mean() * 100), 1),
              "passed_inspection_of_all_pct": round(float(((ex.machining_finalized == "yes") & (ex.passed_visual_inspection == "yes")).mean() * 100), 1),
              "tool_condition": ex.tool_condition.value_counts().to_dict(),
              "has_alarm_or_order_or_partcount_columns": False,
              "columns_sample": list(d.columns[:6]) + list(d.columns[-4:])}
# ---- kamp mirror ----
km = DATA / "kamp" / "mirror_chakihwan"
kt = pd.read_csv(km / "train.csv")
a = pd.read_csv(um / "experiment_01.csv")
b = pd.read_csv(km / "experiment_01.csv")
same_rows = len(a) == len(b)
ca = a.iloc[:, 0].values[: len(b)]
cb = b.iloc[:, 0].values[: len(a)]
S["kamp_mirror"] = {"experiments": len(kt), "train_material": kt.material.unique().tolist(), "umich_train_material": tr.material.unique().tolist(),
                    "same_row_count_as_umich_exp01": bool(same_rows), "corr_X_ActualPosition_vs_umich": round(float(np.corrcoef(ca, cb)[0, 1]), 4) if same_rows else None,
                    "exact_equal_cells_pct_exp01": round(float((a.values == b.values).mean() * 100), 1) if a.shape == b.shape else None,
                    "first18_meta_identical_except_material": bool((kt.drop(columns="material").iloc[:18].reset_index(drop=True).fillna("NA") == tr.drop(columns="material").reset_index(drop=True).fillna("NA")).all().all()),
                    "bad_label_pct": round(float(1 - ((kt.machining_finalized == "yes") & (kt.passed_visual_inspection == "yes")).mean()) * 100, 1),
                    "rowcount_equal_for_exp01_18": all(len(pd.read_csv(um / f"experiment_{i:02d}.csv")) == len(pd.read_csv(km / f"experiment_{i:02d}.csv")) for i in range(1, 19)),
                    "extra_experiments_19_25": 7,
                    "kamp_site_files": ["kamp_home.html", "kamp_detail_cnc_seq3.html", "aihub_search.html", "datagokr_search.html", "gh_kamp_cnc.json"],
                    "kamp_site_has_downloadable_data_locally": False}
# ---- mtconnect ----
mt = DATA / "mtconnect"
mts = {}
for p in sorted(mt.glob("*_probe.xml")):
    root = ET.fromstring(p.read_text(encoding="utf-8", errors="ignore").strip())
    items = [e for e in root.iter() if e.tag.split("}")[-1] == "DataItem"]
    types = Counter(e.get("type") for e in items)
    devs = sorted({e.get("name") for e in root.iter() if e.tag.split("}")[-1] == "Device"})
    mts[p.name] = {"devices": devs, "data_items": len(items), "PART_COUNT": types.get("PART_COUNT", 0), "EXECUTION": types.get("EXECUTION", 0),
                   "PROGRAM": types.get("PROGRAM", 0), "ALARM_CONDITIONS": sum(1 for e in items if e.get("category") == "CONDITION"),
                   "category": dict(Counter(e.get("category") for e in items))}
S["mtconnect_probe"] = mts
cur = {}
for p in sorted(mt.glob("*_current.xml")):
    root = ET.fromstring(p.read_text(encoding="utf-8", errors="ignore").strip())
    v = {}
    for e in root.iter():
        tag = e.tag.split("}")[-1]
        if tag in ("PartCount", "Execution") and e.text:
            v.setdefault(tag, []).append(e.text.strip())
    cur[p.name] = v
S["mtconnect_current"] = cur


def t(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


ev = {}
for fn in ["demo_sample_events_conditions.xml", "mazak_5610_sample_events_conditions.xml"]:
    root = ET.parse(mt / fn).getroot()
    ex_ = sorted((t(e.get("timestamp")), (e.text or "").strip()) for e in root.iter() if e.tag.split("}")[-1] == "Execution")
    pc = sorted((t(e.get("timestamp")), (e.text or "").strip()) for e in root.iter() if e.tag.split("}")[-1] == "PartCount")
    cond = Counter(e.tag.split("}")[-1] for e in root.iter() if e.tag.split("}")[-1] in ("Normal", "Warning", "Fault"))
    segs = [(a[1], (b[0] - a[0]).total_seconds()) for a, b in zip(ex_, ex_[1:])]
    out = {"execution_events": len(ex_), "partcount_events": len(pc), "condition_counts": dict(cond),
           "state_visits": dict(Counter(s for s, _ in segs))}
    act = [d for s, d in segs if s == "ACTIVE"]
    if act:
        out["ACTIVE_seconds"] = [round(x, 1) for x in act]
        out["ACTIVE_median_s"] = round(float(np.median(act)), 1)
    out["span_min"] = round((max(x[0] for x in ex_ + pc) - min(x[0] for x in ex_ + pc)).total_seconds() / 60, 1) if ex_ else None
    ev[fn] = out
S["mtconnect_events"] = ev
S["verdict"] = {
    "umich": "생산 파트: 쓸모없음(실험실 18회, 작업지시/수량/알람 없음). 참고: 작은 부품 1개 가공 시간 100~200초대, 100ms 샘플링",
    "kamp_mirror": "쓸모없음 + 사용 금지(umich 복제·변형본, 재료 라벨만 aluminum으로 바뀜, 출처 불명)",
    "mtconnect": "쓸모없음(공개 데모/시뮬레이터 에이전트의 일부 스냅샷, 시험 시나리오 값). 항목 이름 참고만",
}
save_json(S, "other_summary.json")
print(ex[["No", "feedrate", "clamp_pressure", "tool_condition", "rows", "sec_at_100ms"]].to_string())
