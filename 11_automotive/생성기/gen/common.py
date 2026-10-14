"""생성기 공통 부분: 설정·기준 정보 읽기, seed 난수, 시각 모양, CSV 쓰기, manifest.

규칙은 기준정보_목록.md 1장·2.2절을 따른다.
- 칸 이름 = 논리 ERD 속성 이름, 계산 칸은 넣지 않는다
- UTF-8 (BOM 없음), 쉼표, 참·거짓 true/false, 빈칸 = 값 없음
- 날짜시각 2026-09-01T08:00:00+09:00, 날짜 2026-09-01
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import platform
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent          # 생성기/
PROJECT = ROOT.parent                                   # 11_automotive/
KST = timezone(timedelta(hours=9))


# ---------- 설정·기준 정보 ----------

def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.json"
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: Path) -> list[dict]:
    with io.open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_masters(cfg: dict) -> dict[str, list[dict]]:
    mdir = ROOT / cfg["run"]["masters_dir"]
    return {p.stem: read_csv(p) for p in sorted(mdir.glob("*.csv"))}


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {r[key]: r for r in rows}


# ---------- 난수 ----------

class Rng:
    """seed 하나로 만든 난수. 용도마다 하위 난수를 따로 떼어 써서,
    한 곳의 난수 사용량이 바뀌어도 다른 곳 결과가 흔들리지 않게 한다."""

    def __init__(self, seed: int):
        self.seed = seed
        self._root = np.random.SeedSequence(seed)
        self._cache: dict[str, np.random.Generator] = {}

    def stream(self, name: str) -> np.random.Generator:
        if name not in self._cache:
            key = int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "little")
            self._cache[name] = np.random.default_rng([self.seed, key])
        return self._cache[name]


# ---------- 시각 ----------

def parse_hm(hm: str) -> tuple[int, int]:
    h, m = hm.split(":")
    return int(h), int(m)


def at(d: date, hm: str) -> datetime:
    h, m = parse_hm(hm)
    return datetime(d.year, d.month, d.day, h, m, tzinfo=KST)


def fmt_dt(v: datetime | None) -> str:
    if v is None:
        return ""
    return v.astimezone(KST).replace(microsecond=0).isoformat()


def fmt_date(v: date | None) -> str:
    return "" if v is None else v.isoformat()


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


WEEKDAY = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


# ---------- CSV 쓰기 ----------

def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, datetime):
        return fmt_dt(v)
    if isinstance(v, date):
        return fmt_date(v)
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


class Out:
    """out/ 폴더 쓰기. 엔터티마다 칸 순서를 정해 두고, 기본 키 순서로 정렬해 쓴다."""

    def __init__(self, cfg: dict):
        self.dir = ROOT / cfg["run"]["out_dir"]
        self.dir.mkdir(exist_ok=True)
        self.counts: dict[str, int] = {}

    def clear(self):
        for p in self.dir.glob("*.csv"):
            p.unlink()

    def write(self, entity: str, columns: list[str], rows: list[dict], sort_key=None):
        if sort_key is not None:
            rows = sorted(rows, key=sort_key)
        with io.open(self.dir / f"{entity}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\r\n")
            w.writerow(columns)
            for r in rows:
                unknown = {k for k in r if not k.startswith("_")} - set(columns)   # "_" 칸은 계산용 (쓰지 않음)
                if unknown:
                    raise KeyError(f"{entity}: ERD에 없는 칸 {sorted(unknown)}")
                w.writerow([_cell(r.get(c)) for c in columns])
        self.counts[entity] = len(rows)

    def write_tuples(self, entity: str, columns: list[str], rows: list[tuple]):
        """행이 아주 많은 엔터티(센서 값)용: 칸 순서대로 된 튜플을 기본 키 순서로 정렬해 쓴다."""
        rows.sort(key=lambda r: r[:3])
        with io.open(self.dir / f"{entity}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\r\n")
            w.writerow(columns)
            w.writerows([_cell(v) for v in r] for r in rows)
        self.counts[entity] = len(rows)


def sha256_of(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()


def write_manifest(cfg: dict, out: Out, stage: str, validation: dict | None = None, extra: dict | None = None):
    import pandas
    manifest = {
        "stage": stage,
        "created_at": fmt_dt(datetime.now(KST)),
        "seed": cfg["run"]["seed"],
        "config_sha256": sha256_of([ROOT / "config.json"]),
        "masters_sha256": sha256_of(list((ROOT / cfg["run"]["masters_dir"]).glob("*.csv"))),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pandas.__version__,
        "rows": dict(sorted(out.counts.items())),
        "validation": validation,
    }
    manifest.update(extra or {})
    with io.open(out.dir / "manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return manifest


def check_python():
    if sys.version_info[:2] != (3, 12):
        print(f"[주의] Python {platform.python_version()} — 생성기는 3.12 기준이다 (실행_안내.md)")
