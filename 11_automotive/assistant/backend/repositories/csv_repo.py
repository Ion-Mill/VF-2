"""읽기 전용 저장소. 지금은 simulator/out CSV를 읽고, 나중에 PostgreSQL 구현으로 바꾼다 (같은 메서드 이름 유지)."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from backend.config import SIM_MASTERS, SIM_OUT


class RepositoryError(RuntimeError):
    pass


class CsvRepository:
    def __init__(self, out_dir: Path = SIM_OUT, masters_dir: Path = SIM_MASTERS):
        self.out_dir, self.masters_dir = out_dir, masters_dir
        if not (out_dir / "alarm_event.csv").exists():
            raise RepositoryError(f"가상 운영 데이터가 없습니다: {out_dir} — simulator/generate.py를 먼저 실행하세요")

    def _read(self, path: Path) -> list[dict]:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def table(self, name: str) -> list[dict]:
        return _cached(self.out_dir / f"{name}.csv")

    def master(self, name: str) -> list[dict]:
        return _cached(self.masters_dir / f"{name}.csv")


@lru_cache(maxsize=64)
def _cached(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


_repo: CsvRepository | None = None


def get_repo() -> CsvRepository:
    global _repo
    if _repo is None:
        _repo = CsvRepository()
    return _repo
