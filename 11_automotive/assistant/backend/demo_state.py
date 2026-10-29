"""시연 상태 저장소 (메모리). 시작 데이터 = simulator/out CSV + 기준 시각 REFERENCE_AT.

- 시나리오 사건 넣기(S1 등), 알림 처리 기록, 반복 알람 조치 계획, 폭주 상태, SSE 이벤트 기록을 메모리에 둔다.
- 서버를 다시 켜면 처음 상태로 돌아간다 (운영 DB PostgreSQL은 0b단계). 화면에도 이 사실을 표시한다.
- 설비를 조작하지 않는다. 넣는 것은 가상 운영 기록(알람 이벤트)뿐이다.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta

from backend.config import PROJECT_ROOT, REFERENCE_AT
from backend.repositories.csv_repo import get_repo
from backend.services.shifts import shift_id_of

SCENARIO_DIR = PROJECT_ROOT / "데이터생성기" / "scenarios"   # [11_automotive 이식 2026-10-16] 원본: ROOT/simulator/scenarios
# 시나리오 시작 시각 [가상]: UI설계서 SCR-07·SCR-09 그림의 10:58 발생 (기획서 15장 시연 2막)
SCENARIO_START = {"S1": "2026-10-01T10:58:00+09:00"}
STATE_NOTE = "시연 상태는 메모리에만 있습니다. 서버를 다시 켜면 처음(2026-10-01 08:00)으로 돌아갑니다."
DEMO_SPEED = 1  # 사건을 넣은 뒤 시연 시계가 흐르는 배속 [제안] (UI설계서 2.1 [3] "시간 ×60"은 [선택 필요])


class ScenarioError(ValueError):
    pass


class ScenarioNotFound(ScenarioError):
    """없는 시나리오 → API 오류 NOT_FOUND (2026-10-11 P4)."""


class ScenarioAlreadyInjected(ScenarioError):
    """이미 넣은 시나리오 → API 오류 INVALID_STATE (2026-10-11 P4)."""


def shift_of(t: datetime) -> str:
    """주간 08:00~17:00 / 야간 20:00~05:00 (가상데이터설계서 5.2). 교대 사이는 다음 교대로 본다."""
    h = t.hour
    return "D" if 5 <= h < 17 else "N"


class DemoState:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with self.lock:
            self._base = datetime.fromisoformat(REFERENCE_AT)
            self._wall: float | None = None   # 시나리오를 넣기 전에는 시계가 기준 시각에 멈춰 있다
            self.injected: list[dict] = []
            self.processed: dict[str, dict] = {}     # 알림 id → {by, role, at, plan}
            self.events: list[dict] = []              # SSE 이벤트 기록 (id는 1부터)
            self.storm = False
            self.scenarios: set[str] = set()
            # 교대 보고서 상태 겹침 (교대 번호 → 수정 이력 문서, services/shift_reports.py). 가상 데이터의 보고서는 모두 '확정'이고,
            # 초안·확정 변화는 여기에만 둔다 — 시연 초기화·서버 재시작으로 지워진다 (2026-10-11 P4)
            self.reports: dict[str, object] = {}

    @property
    def now(self) -> datetime:
        if self._wall is None:
            return self._base
        return self._base + timedelta(seconds=(time.monotonic() - self._wall) * DEMO_SPEED)

    def set_now(self, t: datetime) -> None:
        self._base, self._wall = t, time.monotonic()

    # ------------------------------------------------------------ 데이터
    def alarms(self) -> list[dict]:
        return list(get_repo().table("alarm_event")) + list(self.injected)

    def users(self) -> list[dict]:
        return list(get_repo().master("app_user"))

    def user(self, user_id: str) -> dict | None:
        return next((u for u in self.users() if u["user_id"] == user_id), None)

    def equipment(self) -> dict[str, dict]:
        return {e["equipment_id"]: e for e in get_repo().master("equipment")}

    # ------------------------------------------------------------ 이벤트 (SSE)
    def emit(self, type_: str, data: dict, roles: set[str] | None = None, users: set[str] | None = None) -> dict:
        """roles·users가 None이면 모두에게. 받는 사람 거르기는 SSE 보낼 때 서버에서 한다.
        시연 상태의 사건은 모두 가상 운영 기록이라 SSE 데이터에 is_synthetic을 붙인다 (API명세서 공통 규칙, 2026-10-11 P1)."""
        with self.lock:
            ev = {"id": len(self.events) + 1, "type": type_, "data": {**data, "is_synthetic": True}, "roles": roles, "users": users,
                  "at": self.now.isoformat()}
            self.events.append(ev)
            return ev

    def events_after(self, last_id: int, role: str, user_id: str) -> tuple[list[dict], int]:
        """last_id 뒤 이벤트 중 이 사람이 받을 것만. 돌려주는 두 번째 값 = 지금까지 본 마지막 id (거른 것 포함)."""
        with self.lock:
            out = []
            for ev in self.events[last_id:]:
                if role == "MGR" and ev["type"] != "urgent_popup":
                    out.append(ev)
                    continue
                if ev["users"] is not None and user_id not in ev["users"]:
                    continue
                if ev["roles"] is not None and role not in ev["roles"]:
                    continue
                out.append(ev)
            return out, len(self.events)

    # ------------------------------------------------------------ 시나리오
    def popup_targets(self, equipment_id: str, at: datetime) -> set[str]:
        """긴급 팝업 받는 사람: 해당 설비 공정의 이번 교대 OPR + 이번 교대 MNT (UI설계서 2.5)."""
        proc = self.equipment()[equipment_id]["process"]
        sh = shift_of(at)
        out = set()
        for u in self.users():
            if u["shift"] != sh:
                continue
            if u["role"] == "OPR" and proc in u["assigned_process"].split(";"):
                out.add(u["user_id"])
            if u["role"] == "MNT":
                out.add(u["user_id"])
        return out

    def inject(self, scenario_id: str) -> list[dict]:
        sid = scenario_id.upper()
        path = SCENARIO_DIR / f"{sid}.json"
        if sid not in SCENARIO_START or not path.exists():
            raise ScenarioNotFound(f"없는 시나리오: {scenario_id}")
        with self.lock:
            if sid in self.scenarios:
                raise ScenarioAlreadyInjected(f"{sid}는 이미 넣었습니다. 시연 초기화나 서버를 다시 켜면 처음으로 돌아갑니다.")
            spec = json.loads(path.read_text(encoding="utf-8"))
            master = {a["code"]: a for a in get_repo().master("alarm_master")}
            eq = spec["equipment_id"]
            proc = self.equipment()[eq]["process"]
            start = datetime.fromisoformat(SCENARIO_START[sid])
            added = []
            for i, e in enumerate(spec["events"], 1):
                t = start + timedelta(seconds=e["offset_sec"])
                m = master.get(e["code"], {})
                row = {
                    "alarm_event_id": f"ALM-{sid}-{i:02d}", "equipment_id": eq, "process": proc, "control": e["control"],
                    "axis": e["axis"], "code": e["code"], "sub": e["sub"], "alarm_code": e["code"],
                    "name_ko": m.get("name_ko", ""), "severity": e["severity"], "occurred_at": t.isoformat(),
                    # 교대 번호는 services/shifts.shift_id_of — 자정 뒤(00:00~05:00)는 전날 야간 (2026-10-11 P3 고침)
                    "cleared_at": "", "stop_min": "", "shift_id": shift_id_of(t), "processed": "false",
                    "processed_at": "", "work_order_id": "", "work_record_id": "", "is_synthetic": "true",
                }
                self.injected.append(row)
                added.append(row)
            self.set_now(start + timedelta(seconds=spec["events"][-1]["offset_sec"]))
            self.scenarios.add(sid)
            return added


_state: DemoState | None = None


def get_state() -> DemoState:
    global _state
    if _state is None:
        _state = DemoState()
    return _state
