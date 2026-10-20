"""시연 서버 → 백엔드 DB 중계 (2026-10-20, 1단계: 알람·설비 상태·시연 시계).

팀과 논의/비서_시뮬레이터_DB_연결_논의_20261017.md 3-1 "정한 방향" 그대로:
  - 시연 서버가 사건을 화면으로 밀어 주는 곳(State._push)에서 백엔드 수집 입구(/api/ingest/*)로도 보낸다.
    화면이 느려지지 않게 별도 스레드 큐로 보낸다. 생성기 코드는 건드리지 않는다.
  - 쓰는 DB는 **사람마다 로컬 DB(Docker)**. 공용 mom-db에는 쓰지 않는다.
  - 기본은 꺼짐. 켜기: 환경 변수 MOM_DB_RELAY_URL(예: http://127.0.0.1:8020) + MOM_INGEST_KEY(백엔드 .env의 MOM_INGEST_KEY)
잠금 두 겹:
  ① 주소가 localhost·127.0.0.1·::1이 아니면 켜지지 않는다.
  ② 처음에 시계 입구(/api/ingest/clock)를 부른다. 백엔드가 시연 모드가 아니면(공용 DB 서버는 늘 꺼짐) 409 → 중계가 스스로 꺼진다.
알람 번호: 맞추려 하지 않는다. "시뮬레이터 번호 → DB가 돌려준 번호" 대응표를 들고, 설비 상태(DOWN)의 알람 번호를 바꿔 보낸다.
  시뮬레이터는 DOWN 상태를 그 알람보다 먼저 보낼 때가 있어(같은 분), 알람이 올 때까지 상태를 잡아 둔다.
  같은 사건(scenario_code)의 앞 알람을 연쇄(prev_alarm_event_id)로 잇는다 (S1 108 → 994 → 992) [제안].
2단계(생산·병목·재공·로트)·3단계(센서·CMM)는 아직 — 생산 실적 없이 병목만 보내면 속도 손실이 틀리게 나온다.
시연 서버 [처음으로]는 DB를 되돌리지 않는다 — 로컬 DB는 docker compose down -v 뒤 up (3-1 "되돌리기").
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import Callable
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
CLOCK_EVERY_SEC = 5.0               # 시계는 5초마다 맞춘다 (배속·일시정지·넘기기·처음으로 모두 따라감)
PENDING_MAX = 200                   # 알람을 기다리는 상태 최대 수 (넘치면 오래된 것부터 버림)


class DbRelay:
    def __init__(self, url: str, key: str, clock_fn: Callable[[], dict], post: Callable | None = None, log=print):
        self.url = url.rstrip("/")
        self.key = key
        self.clock_fn = clock_fn
        self.log = log
        self._post_impl = post or self._http_post
        self.q: queue.Queue = queue.Queue()
        self.enabled = True
        self.amap: dict[int, int] = {}            # 시뮬레이터 알람 번호 → DB 알람 번호
        self.pending: dict[int, list[dict]] = {}  # DB 번호를 기다리는 설비 상태 (시뮬레이터 알람 번호별)
        self.last_in_scenario: dict[tuple, int] = {}   # (사건, 설비) → 마지막 DB 알람 번호 (연쇄)
        self.stats = {"alarms": 0, "states": 0, "clock": 0, "errors": 0, "dropped": 0}
        self._thread: threading.Thread | None = None

    # ---------------- 켜기
    @classmethod
    def from_env(cls, clock_fn: Callable[[], dict], log=print) -> "DbRelay | None":
        url, key = os.environ.get("MOM_DB_RELAY_URL", "").strip(), os.environ.get("MOM_INGEST_KEY", "").strip()
        if not url:
            return None
        host = urlparse(url).hostname or ""
        if host not in LOCAL_HOSTS:
            log(f"[DB 중계] 꺼짐 — 주소가 로컬이 아님 ({host}). 공용 DB에 시연 사건을 쓰지 않는다")
            return None
        if not key:
            log("[DB 중계] 꺼짐 — MOM_INGEST_KEY가 없음")
            return None
        return cls(url, key, clock_fn, log=log)

    def start(self) -> bool:
        """시계를 한 번 맞춰 보고(시연 모드 확인) 보내는 스레드를 켠다. 반환: 켜졌는지"""
        st, body = self._post("/api/ingest/clock", self._clock_body())
        if st != 200:
            self.enabled = False
            why = body.get("detail", {}).get("reason") if isinstance(body, dict) else None
            self.log(f"[DB 중계] 꺼짐 — 백엔드가 시계를 받지 않음 (HTTP {st}{', ' + why if why else ''}). "
                     "로컬 Docker 백엔드(MOM_DEMO_MODE=true)에서만 켜진다")
            return False
        self.stats["clock"] += 1
        self._thread = threading.Thread(target=self._loop, name="db-relay", daemon=True)
        self._thread.start()
        self.log(f"[DB 중계] 켜짐 → {self.url} (알람·설비 상태·시계)")
        return True

    # ---------------- 시연 서버가 부름
    def feed(self, events: list[dict]) -> None:
        if self.enabled:
            for e in events:
                if e.get("type") in ("alarm", "state_changed"):
                    self.q.put(e)

    def reset(self) -> None:
        """시연 서버 [처음으로]: 대응표만 비운다 (DB는 그대로 — 로컬 DB는 docker compose down -v)"""
        self.q.put({"type": "_reset"})

    # ---------------- 스레드
    def _loop(self) -> None:
        next_clock = time.monotonic() + CLOCK_EVERY_SEC
        while self.enabled:
            try:
                e = self.q.get(timeout=max(0.05, next_clock - time.monotonic()))
                self.handle(e)
            except queue.Empty:
                pass
            except Exception as ex:          # 중계가 죽어도 시연 화면은 그대로
                self.stats["errors"] += 1
                self.log(f"[DB 중계] 처리 오류: {ex}")
            if time.monotonic() >= next_clock:
                self.sync_clock()
                next_clock = time.monotonic() + CLOCK_EVERY_SEC

    def handle(self, e: dict) -> None:
        t = e.get("type")
        if t == "_reset":
            self.amap.clear(); self.pending.clear(); self.last_in_scenario.clear()
            self.log("[DB 중계] 시연 처음으로 — 알람 대응표를 비움 (DB는 그대로)")
        elif t == "alarm":
            self._alarm(e)
        elif t == "state_changed":
            self._state(e)

    def sync_clock(self) -> None:
        st, _ = self._post("/api/ingest/clock", self._clock_body())
        if st == 200:
            self.stats["clock"] += 1

    def _clock_body(self) -> dict:
        c = self.clock_fn()
        return {"sim_at": c["sim_at"], "speed": c.get("speed") or 1, "paused": bool(c.get("paused"))}

    def _alarm(self, e: dict) -> None:
        sc = e.get("scenario_code")
        prev = self.last_in_scenario.get((sc, e.get("equipment_id"))) if sc else None
        st, body = self._post("/api/ingest/alarms", {
            "equipment_id": e["equipment_id"], "alarm_code": e["alarm_code"], "occurred_at": e.get("at"),
            "prev_alarm_event_id": prev, "is_injected": sc is not None, "scenario_code": sc})
        if st != 200 or not isinstance(body, dict) or body.get("alarm_event_id") is None:
            return
        db_id = int(body["alarm_event_id"])
        self.stats["alarms"] += 1
        if e.get("alarm_event_id") is not None:
            self.amap[int(e["alarm_event_id"])] = db_id
            for s in self.pending.pop(int(e["alarm_event_id"]), []):
                self._state(s)
        if sc:
            self.last_in_scenario[(sc, e.get("equipment_id"))] = db_id

    def _state(self, e: dict) -> None:
        sim_id = e.get("alarm_event_id")
        db_id = None
        if sim_id is not None:
            db_id = self.amap.get(int(sim_id))
            if db_id is None:                       # 알람이 아직 안 옴 → 잡아 둔다
                lst = self.pending.setdefault(int(sim_id), [])
                lst.append(e)
                if sum(len(v) for v in self.pending.values()) > PENDING_MAX:
                    oldest = min(self.pending)
                    self.pending[oldest].pop(0)
                    if not self.pending[oldest]:
                        del self.pending[oldest]
                    self.stats["dropped"] += 1
                return
        st, _ = self._post("/api/ingest/state", {
            "equipment_id": e["equipment_id"], "state_code": e["state"], "at": e.get("at"),
            "execution": e.get("mtconnect_execution"), "warn_marker": bool(e.get("warn")),
            "reason_suggested_code": e.get("reason") if e["state"] != "RUN" else None, "alarm_event_id": db_id})
        if st == 200:
            self.stats["states"] += 1

    # ---------------- HTTP
    def _post(self, path: str, body: dict) -> tuple[int, dict]:
        try:
            st, out = self._post_impl(self.url + path, body, self.key)
        except Exception as ex:
            st, out = 0, {"message": str(ex)}
        if st != 200:
            self.stats["errors"] += 1
            if path != "/api/ingest/clock" or st not in (0,):
                msg = out.get("message") if isinstance(out, dict) else out
                self.log(f"[DB 중계] {path} 실패 HTTP {st}: {str(msg)[:160]}")
        return st, out

    @staticmethod
    def _http_post(url: str, body: dict, key: str) -> tuple[int, dict]:
        req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "X-Service-Key": key})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:     # noqa: S310 (로컬 주소만 — from_env가 확인)
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}
