"""읽기 전용 저장소. 지금은 simulator/out CSV를 읽고, 나중에 PostgreSQL 구현으로 바꾼다 (같은 메서드 이름 유지)."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from backend.config import SIM_MASTERS, SIM_OUT


class RepositoryError(RuntimeError):
    pass


# ---------------------------------------------------------------- [11_automotive 이식 2026-10-16] 기준표 열 이름 맞춤
# 묶음은 옛 simulator/masters의 열 이름(code·control·severity_ko·who·doc03_section …)을 읽는다. 이 저장소의 생성기 기준표는
# 논리 ERD 이름(alarm_code·process_code·severity·responder …)이다. 여기서 옛 이름을 더해 돌려준다 (원래 열은 그대로 둔다).
# 심각도·담당 표현은 DOC-02 알람 절의 "심각도"·"누가 조치" 칸과 같다 (정지/주의/조작 안내, 보전 담당자/작업자).
_SEVERITY_KO = {"STOP": "정지", "WARN": "주의", "GUIDE": "조작 안내"}
_RESPONDER_KO = {"MNT": "보전 담당자", "OPR": "작업자", "SUP": "반장", "MGR": "공장 관리자"}


def _controller_by_process(equipment_rows: list[dict]) -> dict[str, str]:
    """공정마다 설비 제어기 이름 ("Haas NGC" → "NGC"). 제어기가 적힌 설비가 없는 공정(세척·측정)은 빠진다."""
    out: dict[str, str] = {}
    for e in equipment_rows:
        c = (e.get("controller") or "").strip()
        if c:
            out.setdefault(e["process_code"], c.removeprefix("Haas ").strip() or c)
    return out


def _alarm_master_compat(rows: list[dict], guide_rows: list[dict], equipment_rows: list[dict]) -> list[dict]:
    first: dict[str, dict] = {}
    for g in sorted(guide_rows, key=lambda g: int(g["seq"])):
        first.setdefault(g["alarm_code"], g)          # 알람마다 첫 고장 대응 절 (seq 1)
    controller = _controller_by_process(equipment_rows)
    out = []
    for r in rows:
        g = first.get(r["alarm_code"])
        # control = 원본에서는 제어기 이름(NGC …). 제어기가 없는 공정(OP-40 세척 등)은 공정 코드를 쓴다
        doc02 = (r.get("doc02_section") or "").strip()      # 원본은 "DOC-02 §4.10" 꼴 — 생성기는 "§4.10"만 있다 (answer.py가 문서 번호로 절을 찾는다)
        out.append({**r, "code": r["alarm_code"], "control": controller.get(r["process_code"], r["process_code"]),
                    "doc02_section": f"DOC-02 {doc02}" if doc02.startswith("§") else doc02,
                    "severity_ko": _SEVERITY_KO.get(r["severity"], r["severity"]),
                    "who": r.get("responder_note") or _RESPONDER_KO.get(r["responder"], r["responder"]),
                    "doc03_section": f"{g['doc_no']} {g['section']}" if g else ""})
    return out


def _equipment_compat(rows: list[dict]) -> list[dict]:
    return [{**r, "cycle_min": r["std_cycle_min"], "process": r["process_code"]} for r in rows]


def _downtime_reason_compat(rows: list[dict]) -> list[dict]:
    return [{**r, "code": r["reason_code"], "name": r["reason_name"], "group": r["reason_group"]} for r in rows]


_MASTER_COMPAT = {"equipment": _equipment_compat, "downtime_reason": _downtime_reason_compat}


class CsvRepository:
    def __init__(self, out_dir: Path = SIM_OUT, masters_dir: Path = SIM_MASTERS):
        self.out_dir, self.masters_dir = out_dir, masters_dir
        self._compat: dict[str, list[dict]] = {}
        if not (out_dir / "alarm_event.csv").exists():
            raise RepositoryError(f"가상 운영 데이터가 없습니다: {out_dir} — simulator/generate.py를 먼저 실행하세요")

    def _read(self, path: Path) -> list[dict]:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def table(self, name: str) -> list[dict]:
        return _cached(self.out_dir / f"{name}.csv")

    def master(self, name: str) -> list[dict]:
        rows = _cached(self.masters_dir / f"{name}.csv")
        if name == "alarm_master":
            if name not in self._compat:             # 요청마다 다시 만들지 않는다 (기준표는 바뀌지 않는다)
                self._compat[name] = _alarm_master_compat(rows, _cached(self.masters_dir / "alarm_guide_map.csv"),
                                                          _cached(self.masters_dir / "equipment.csv"))
            return self._compat[name]
        fn = _MASTER_COMPAT.get(name)
        if fn is None:
            return rows
        if name not in self._compat:
            self._compat[name] = fn(rows)
        return self._compat[name]


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
