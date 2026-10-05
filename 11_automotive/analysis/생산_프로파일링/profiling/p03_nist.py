"""C. NIST 설비 상태 기록: 상태 전이 행렬, 상태 지속시간, 알람, 부품 수/사이클"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import re

import numpy as np
import pandas as pd
from scipy import stats

from common_prof import DATA, OUT, quant, save_json, setup_font

plt = setup_font()
NIST = DATA / "nist"
S = {}


def ts(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


def read_raw(path):
    """MTConnect SHDR 한 줄 -> (시각, 키, 값, 나머지칸). 한 줄에 키/값이 여러 개인 tdp 파일도 처리."""
    ev, cond = [], []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if len(p) < 3:
                continue
            try:
                t = ts(p[0])
            except ValueError:
                continue
            if len(p) >= 6 and p[2] in ("Normal", "Warning", "Fault", "Unavailable"):
                cond.append((t, p[1], p[2], p[3], p[-1]))
            else:
                for k, v in zip(p[1::2], p[2::2]):
                    ev.append((t, k, v))
    return ev, cond


def intervals(seq):
    """[(t,state)] -> 같은 값 연속 제거 후 (state, 길이초, 다음 state)."""
    seq = [x for x in seq if x[1] != "UNAVAILABLE"]
    ded = []
    for t, v in seq:
        if not ded or ded[-1][1] != v:
            ded.append((t, v))
    tail = (ded[-1][1], (seq[-1][0] - ded[-1][0]).total_seconds()) if ded else None   # 마지막 상태가 관측 끝까지 이어진 시간(끝이 잘린 구간)
    return [(a[1], (b[0] - a[0]).total_seconds(), b[1], a[0]) for a, b in zip(ded, ded[1:])], ded, tail


def state_at(ded, t):
    lo = None
    for tt, v in ded:
        if tt <= t:
            lo = v
        else:
            break
    return lo


def lognorm(x):
    x = np.asarray([v for v in x if v > 0])
    if len(x) < 8:
        return None
    sh, _, sc = stats.lognorm.fit(x, floc=0)
    return {"n": len(x), "sigma": round(sh, 3), "median_s": round(sc, 1)}


# ---------- Execution 상태 (Mazak01, Mazak03) ----------
all_iv, per_file = [], {}
alarm_rows, alarm_state_rows = [], []
for name, key in [("Mazak01-20170111-20170112.txt", "execution"), ("Mazak03-20180815-20180816.txt", "execution")]:
    ev, cond = read_raw(NIST / "raw" / name)
    day = re.search(r"-(\d{8})-", name).group(1)
    day0 = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
    seq = [(t, v) for t, k, v in ev if k == key and t >= day0]   # 기존 03 스크립트와 같은 기준(당일 00:00 UTC 이후)
    iv, ded, tail = intervals(seq)
    vcount = Counter(v for _, v in ded)
    tot_s = sum(x[1] for x in iv)
    tot_all = tot_s + tail[1]
    per_file[name] = {"trailing_state": tail[0], "trailing_hours": round(tail[1] / 3600, 2),
                      "observed_hours_incl_trailing": round(tot_all / 3600, 2),
                      "active_pct_incl_trailing": round(sum(x[1] for x in iv if x[0] == "ACTIVE") / tot_all * 100, 1),
                      "ready_pct_incl_trailing": round((sum(x[1] for x in iv if x[0] == "READY") + (tail[1] if tail[0] == "READY" else 0)) / tot_all * 100, 1),
                      "stopped_pct_incl_trailing": round(sum(x[1] for x in iv if x[0] == "STOPPED") / tot_all * 100, 1),"state_changes_excl_unavailable": len(ded), "observed_hours": round(tot_s / 3600, 2),
                      "active_pct": round(sum(x[1] for x in iv if x[0] == "ACTIVE") / tot_s * 100, 1),
                      "ready_pct": round(sum(x[1] for x in iv if x[0] == "READY") / tot_s * 100, 1),
                      "stopped_pct": round(sum(x[1] for x in iv if x[0] == "STOPPED") / tot_s * 100, 1),
                      "feedhold_pct": round(sum(x[1] for x in iv if x[0] == "FEED_HOLD") / tot_s * 100, 2),
                      "state_visits": dict(vcount), "first": str(ded[0][0]), "last": str(ded[-1][0])}
    for st, sec, nxt, t0 in iv:
        all_iv.append({"file": name[:8], "state": st, "dur_s": sec, "next": nxt, "start": t0})
    # 모드(AUTOMATIC/MANUAL)
    modes = [(t, v) for t, k, v in ev if k == "mode"]
    miv, _, _ = intervals(modes)
    per_file[name]["mode_minutes"] = {m: round(sum(x[1] for x in miv if x[0] == m) / 60, 1) for m in {x[0] for x in miv}}
    # 알람 에피소드: 조건 키별로 Warning/Fault 시작 -> Normal 복귀
    by_key = defaultdict(list)
    for t, k, lvl, code, txt in cond:
        by_key[k].append((t, lvl, code, txt))
    for k, rows in by_key.items():
        rows.sort(key=lambda r: r[0])
        for i, (t, lvl, code, txt) in enumerate(rows):
            if lvl in ("Warning", "Fault") and t >= day0:
                end = next((r[0] for r in rows[i + 1:] if r[1] == "Normal" or (r[1], r[2]) != (lvl, code)), None)
                dur = (end - t).total_seconds() if end else np.nan
                alarm_rows.append({"file": name[:8], "cond_key": k, "level": lvl, "code": code, "text": " ".join(txt.split()), "start": t, "dur_s": dur,
                                   "exec_state_at_start": state_at(ded, t)})
    # 카운터 단위 확인
    for ck in ["total_time", "auto_time", "cut_time"]:
        vals = [(t, float(v)) for t, k, v in ev if k == ck and v.replace(".", "").isdigit()]
        if len(vals) > 10:
            v0, v1 = vals[0], vals[-1]
            per_file[name][f"{ck}_delta_over_elapsed_s"] = round((v1[1] - v0[1]) / (v1[0] - v0[0]).total_seconds(), 3)
            per_file[name][f"{ck}_delta_raw"] = v1[1] - v0[1]
    # PartCountAct 값
    pc = sorted({v for t, k, v in ev if k == "PartCountAct" and v != "UNAVAILABLE"})
    per_file[name]["PartCountAct_values"] = pc
S["files"] = per_file

iv = pd.DataFrame(all_iv)
iv.to_csv(OUT / "nist_state_intervals.csv", index=False)
# 전이 확률 행렬
trans = pd.crosstab(iv.state, iv.next)
trans_p = trans.div(trans.sum(axis=1), axis=0).round(3)
trans.to_csv(OUT / "nist_transition_counts.csv")
trans_p.to_csv(OUT / "nist_transition_prob.csv")
S["transition_counts"] = trans.to_dict()
S["transition_prob"] = trans_p.to_dict("index")
# 파일별 전이행렬
for f, g in iv.groupby("file"):
    pd.crosstab(g.state, g.next, normalize="index").round(3).to_csv(OUT / f"nist_transition_prob_{f}.csv")
# 지속시간
dur_rows = []
for st, g in iv.groupby("state"):
    q = quant(g.dur_s, nd=1)
    q["state"] = st
    q["lognorm"] = lognorm(g.dur_s)
    q["total_min"] = round(float(g.dur_s.sum() / 60), 1)
    dur_rows.append(q)
dd = pd.DataFrame(dur_rows)
dd = dd[["state"] + [c for c in dd.columns if c != "state"]]
dd.drop(columns=["lognorm"]).to_csv(OUT / "nist_state_duration_s.csv", index=False)
S["state_duration_s"] = {r["state"]: {k: v for k, v in r.items() if k != "state"} for r in dur_rows}
# 시간비율(두 날 합)
tt = iv.groupby("state").dur_s.sum()
S["time_share_pct_pooled"] = (tt / tt.sum() * 100).round(1).to_dict()
S["visits_share_pct_pooled"] = (iv.state.value_counts(normalize=True) * 100).round(1).to_dict()
# 자동 모드 중에서만(생산 중) 상태 비율
# STOPPED 의 앞/뒤 상태
S["stopped_prev_state"] = iv[iv.next == "STOPPED"].state.value_counts().to_dict()
S["state_changes_per_hour_observed"] = round(len(iv) / (iv.dur_s.sum() / 3600), 2)

# ---------- 알람 ----------
al = pd.DataFrame(alarm_rows)
al.to_csv(OUT / "nist_alarm_episodes.csv", index=False)
S["alarm_episodes"] = len(al)
S["alarm_level_share_pct"] = (al.level.value_counts(normalize=True) * 100).round(1).to_dict()
S["alarm_level_by_file"] = al.groupby(["file", "level"]).size().unstack(fill_value=0).to_dict("index")
S["alarm_by_cond_key"] = al.groupby(["cond_key", "level"]).size().unstack(fill_value=0).to_dict("index")
al["code_text"] = al.code + " " + al.text.str.replace(r"^\s*\d+\s*", "", regex=True)
top = al.groupby(["level", "code", "text"]).size().sort_values(ascending=False).reset_index(name="n")
top["share_pct"] = (top.n / top.n.sum() * 100).round(1)
top.to_csv(OUT / "nist_alarm_types.csv", index=False, encoding="utf-8-sig")
S["alarm_distinct_codes"] = int(al.code.nunique())
S["alarm_dur_s"] = quant(al.dur_s, nd=1) if al.dur_s.notna().sum() > 3 else None
S["alarm_dur_s_by_level"] = {l: quant(g.dur_s, nd=1) for l, g in al.groupby("level") if g.dur_s.notna().sum() > 2}
S["alarm_exec_state_at_start"] = al.exec_state_at_start.value_counts().to_dict()
S["alarm_per_observed_hour"] = round(len(al) / (iv.dur_s.sum() / 3600), 2)
S["alarm_per_file_per_observed_hour"] = {f: round(len(g) / (iv[iv.file == f].dur_s.sum() / 3600), 2) for f, g in al.groupby("file")}
al["hour"] = al.start.dt.hour
S["alarm_hour_dist"] = al.hour.value_counts().sort_index().to_dict()
# 알람 직후 10분 내 STOPPED 전이 여부
stop_t = iv[iv.next == "STOPPED"][["file", "start", "dur_s"]]
stop_t = stop_t.assign(t=stop_t.start + pd.to_timedelta(stop_t.dur_s, unit="s"))
hit = 0
for _, a in al.iterrows():
    m = stop_t[(stop_t.file == a.file) & (stop_t.t >= a.start - pd.Timedelta(minutes=1)) & (stop_t.t <= a.start + pd.Timedelta(minutes=10))]
    hit += len(m) > 0
S["alarm_followed_by_STOPPED_within_10min_pct"] = round(hit / len(al) * 100, 1)

# ---------- Hurco: 사이클/부품 수 ----------
hur = {}
for name, path in [("Hurco02_clean_2017-02-01", NIST / "tdp" / "2-1-2017-Hurco02-Clean.txt"), ("Hurco02_box_op1", NIST / "tdp" / "Box-OP1-Hurco02-05of20.txt"),
                   ("Hurco01_raw_20170518", NIST / "raw" / "Hurco01-20170518-20170519.txt")]:
    ev, _ = read_raw(path)
    ps = [(t, v) for t, k, v in ev if k == "Program_Status"]
    iv_h, ded_h, _ = intervals(ps)
    h = {"events": len(ev), "span_hours": round((ev[-1][0] - ev[0][0]).total_seconds() / 3600, 2) if ev else 0,
         "program_status_transitions": len(ded_h)}
    h["time_by_state_min"] = {s: round(sum(x[1] for x in iv_h if x[0] == s) / 60, 1) for s in {x[0] for x in iv_h}}
    # 사이클: ACTIVE 시작 -> PROGRAM_COMPLETED
    cyc = []
    for i, (t, v) in enumerate(ded_h):
        if v == "ACTIVE":
            for t2, v2 in ded_h[i + 1:]:
                if v2 in ("PROGRAM_COMPLETED", "PROGRAM_STOPPED", "READY"):
                    cyc.append({"start": t, "end_state": v2, "min": (t2 - t).total_seconds() / 60})
                    break
    h["active_to_end"] = [{"end_state": c["end_state"], "min": round(c["min"], 2)} for c in cyc]
    pcs = [(t, v) for t, k, v in ev if k == "Part_Count" and v != "UNAVAILABLE"]
    h["part_count_values"] = [v for _, v in pcs]
    if len(pcs) >= 3:
        gaps = [(b[0] - a[0]).total_seconds() / 60 for a, b in zip(pcs, pcs[1:])]
        h["part_count_interval_min"] = [round(g, 1) for g in gaps]
        h["part_count_interval_stats"] = quant(pd.Series(gaps), nd=1)
    hur[name] = h
S["hurco"] = hur
ok = [c["min"] for c in hur["Hurco02_clean_2017-02-01"]["active_to_end"] if c["end_state"] == "PROGRAM_COMPLETED"]
S["hurco02_completed_cycle_min"] = quant(pd.Series(ok), nd=2) if len(ok) >= 3 else ok
save_json(S, "nist_summary.json")

# ---------- 그림 ----------
fig, ax = plt.subplots(1, 3, figsize=(17, 5))
im = ax[0].imshow(trans_p.values, cmap="Blues", vmin=0, vmax=1)
ax[0].set_xticks(range(len(trans_p.columns))); ax[0].set_xticklabels(trans_p.columns, rotation=40, ha="right", fontsize=8)
ax[0].set_yticks(range(len(trans_p.index))); ax[0].set_yticklabels(trans_p.index, fontsize=8)
for i in range(trans_p.shape[0]):
    for j in range(trans_p.shape[1]):
        ax[0].text(j, i, f"{trans_p.values[i, j]:.2f}", ha="center", va="center", fontsize=8, color="w" if trans_p.values[i, j] > .5 else "k")
ax[0].set_title("상태 전이 확률 (행=현재, 열=다음; Mazak 2일 합산)")
for st, c in [("ACTIVE", "#4C78A8"), ("READY", "#B0B0B0"), ("STOPPED", "#E45756"), ("FEED_HOLD", "#F58518")]:
    x = iv[iv.state == st].dur_s / 60
    if len(x) > 3:
        ax[1].hist(np.clip(x, 0, 60), bins=30, alpha=.55, label=f"{st} (n={len(x)}, 중앙값 {x.median():.1f}분)", color=c)
ax[1].set_title("상태별 한 번 지속시간 (분, 60분 초과 묶음)"); ax[1].legend(fontsize=8)
lv = al.groupby(["code_text"]).size().sort_values().tail(10)
ax[2].barh([s[:34] for s in lv.index], lv.values, color="#54A24B"); ax[2].set_title("알람 종류 상위 10 (Mazak 2일)"); ax[2].tick_params(axis="y", labelsize=7)
plt.tight_layout(); plt.savefig(OUT / "fig_nist_state.png", dpi=110); plt.close()
print("done nist")
print(trans_p.to_string())
print(dd.drop(columns=["lognorm"]).to_string())
