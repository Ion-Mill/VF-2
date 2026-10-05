"""profiling 공통 경로/도우미. 원본 data/ 는 읽기만 한다."""
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]          # 11_automotive
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent               # profiling/
QS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]


def save_json(obj, name):
    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, (np.ndarray,)):
            return o.tolist()
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")


def quant(s, qs=QS, nd=2):
    s = s.dropna()
    d = {"n": int(len(s)), "mean": round(float(s.mean()), nd)}
    for q in qs:
        d[f"p{int(q*100):02d}"] = round(float(s.quantile(q)), nd)
    d["min"] = round(float(s.min()), nd)
    d["max"] = round(float(s.max()), nd)
    return d


def setup_font():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    return plt
