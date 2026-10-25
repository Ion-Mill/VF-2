"""시연 서버 → 백엔드 DB 중계 (2026-10-20 1단계 알람·설비 상태·시계 → 2026-10-23 생성기 10/1 기록 전부 + [처음으로]).

  - 시연 서버가 중계한다. 화면이 느려지지 않게 별도 스레드에서 보낸다.
  - **DB 1개 = 공장 1개 (2026-10-23 사용자 결정).** 백엔드가 쓰는 DB(공용 Supabase mom-db 포함)에 쌓고, 모두가 같은 기록을 본다.
    여러 명이 동시에 중계를 켜면 기록이 겹치고, 누가 [처음으로]를 눌러도 모두의 10/1 기록이 되돌아간다 — 받아들인 것.
    약속: 중계는 시연 진행자 한 명만 켠다 (기본 꺼짐이라 화면 리허설만 하는 사람은 DB에 쓰지 않는다).
  - 켜기: 환경 변수 MOM_DB_RELAY_URL(백엔드 주소, 예: http://127.0.0.1:8020) + MOM_INGEST_KEY(그 백엔드 env의 MOM_INGEST_KEY)
잠금: 처음에 시계 입구(/api/ingest/clock)를 부른다. 백엔드가 MOM_SIM_SYNC=true(또는 시연 모드)가 아니면 409 → 중계가 스스로 꺼진다.
  (2026-10-20의 "주소가 로컬이어야 함" 잠금은 없앴다 — 공용 DB에도 쓰기로 했으므로 백엔드 스위치 하나로 정한다)
보내는 것 (2026-10-23): 생성기 Realtime.tables() — out_realtime CSV와 같은 17개 표(작업지시·로트·실적·설비 상태·알람·병목·재공·
  공구·검사·측정 결과·불량·보류·예방 정비·재고 거래·센서). SYNC_EVERY_SEC마다 앞에 보낸 것과 비교해 **바뀐 줄만**
  /api/ingest/sync로 보낸다 (백엔드가 기본 키로 덮어씀). 번호는 시뮬레이터 번호 그대로 (9월 번호 다음부터) — 그래서 1단계의
  "알람 번호 대응표"는 없앴다. 새 알람의 알림·반복 알람 판정·재공 경고 등은 백엔드가 실제 받기와 같게 만든다.
[처음으로] (2026-10-23): 시연 회차(run_id)가 바뀌면 먼저 /api/ingest/reset으로 DB를 시연 기준점(9월 끝, 10/1 08:00)으로
  되돌린 뒤 다시 보낸다 (fn_demo_reset — 운영 표 되돌림 + 기준점 뒤 센서 값 지움). 시연 서버를 켤 때도 한 번 되돌린다
  (시뮬레이터가 10/1 08:00부터 다시 시작하므로). 되돌릴 때 시뮬레이터 시작점(Realtime.baseline: 시각·표마다 마지막 번호)을 함께
  보내, DB 기준점과 다르면 백엔드가 되돌리기를 취소하고(409 BASELINE_MISMATCH) 중계가 꺼진다 — 나중에 10/1 뒤 기록을 DB에 채우거나
  실제 시간으로 바꿀 때 기준점과 시뮬레이터 시작점을 함께 옮기라는 안전장치.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request
from typing import Callable
CLOCK_EVERY_SEC = 5.0               # 시계는 5초마다 맞춘다 (배속·일시정지·넘기기·처음으로 모두 따라감)
SYNC_EVERY_SEC = 3.0                # 기록은 3초마다 바뀐 줄만
SENSOR = "sensor_sample"
SENSOR_PK = ("equipment_id", "sensor_code", "sampled_at", "interval_type")
SENSOR_CHUNK = 5000                 # 센서는 한 요청에 5천 줄씩 (그 밖의 표는 하루치를 합쳐도 수천 줄)
# 넣는 순서 (백엔드 app/services/sim_sync.py TABLES와 같게 — 하나씩 다시 보낼 때 부모 먼저)
ORDER = ["production_order", "production_lot", "inspection_plan", "alarm_event", "pm_record", "equipment_state_log",
         "operation_report", "tool_change", "tool_usage", "bottleneck_log", "wip_log", "lot_hold", "cmm_import",
         "inspection_result", "defect_record", "inventory_txn", SENSOR]

# snap(last_sig) → (sig, run_id, tables | None). 상태가 그대로(sig == last_sig)면 tables = None (표를 다시 만들지 않음)
Snap = Callable[[object], tuple[object, int, "dict[str, tuple[list[str], list[tuple]]] | None"]]


def backend_env() -> dict[str, str]:
    """backend/<MOM_ENV_FILE>(기본 .env.supabase)의 KEY=값 줄 (값은 로그에 쓰지 않는다)"""
    name = os.environ.get("MOM_ENV_FILE", "").strip() or ".env.supabase"
    f = Path(__file__).resolve().parents[2] / "backend" / name
    out: dict[str, str] = {}
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class DbRelay:
    def __init__(self, url: str, key: str, clock_fn: Callable[[], dict], snap_fn: Snap, base_fn: Callable[[], dict] | None = None,
                 post: Callable | None = None, log=print):
        self.url = url.rstrip("/")
        self.key = key
        self.clock_fn = clock_fn
        self.snap_fn = snap_fn
        self.base_fn = base_fn                       # 시뮬레이터 시작점 {start_at, id_after} (되돌릴 때 DB 기준점과 비교)
        self.log = log
        self._post_impl = post or self._http_post
        self.enabled = True
        self.run_seen: int | None = None             # DB가 맞춰져 있는 시연 회차 (None = 아직 되돌리지 않음)
        self.sig: object = None
        self.sent: dict[str, set[tuple]] = {}        # 표 → DB에 넣은 줄 (칸 값 튜플)
        self.stats = {"syncs": 0, "rows": 0, "resets": 0, "clock": 0, "errors": 0}
        self._last_err: str | None = None
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    # ---------------- 켜기
    @classmethod
    def from_env(cls, clock_fn: Callable[[], dict], snap_fn: Snap, base_fn: Callable[[], dict] | None = None,
                 log=print) -> "DbRelay | None":
        url, key = os.environ.get("MOM_DB_RELAY_URL", "").strip(), os.environ.get("MOM_INGEST_KEY", "").strip()
        if url.lower() in ("off", "0", "false"):
            return None
        if not url:
            # 2026-10-24 (화면 → 백엔드가 기본): 주소를 따로 안 줘도 백엔드 환경 파일이 중계를 받겠다고(MOM_SIM_SYNC=true) 하면 켠다.
            #   파일 = backend/<MOM_ENV_FILE, 기본 .env.supabase> (npm run dev:api와 같은 파일), 백엔드 주소 = MOM_BACKEND_URL (기본 :8000)
            env = backend_env()
            if env.get("MOM_SIM_SYNC", "").lower() not in ("1", "true", "yes", "on") and \
                    env.get("MOM_DEMO_MODE", "").lower() not in ("1", "true", "yes", "on"):
                return None
            url = os.environ.get("MOM_BACKEND_URL", "").strip() or "http://127.0.0.1:8000"
            key = key or env.get("MOM_INGEST_KEY", "")
            log(f"[DB 중계] 백엔드 환경 파일이 중계를 받음(MOM_SIM_SYNC) → {url}")
        if not key:
            log("[DB 중계] 꺼짐 — MOM_INGEST_KEY가 없음")
            return None
        return cls(url, key, clock_fn, snap_fn, base_fn, log=log)

    def start(self) -> bool:
        """시계를 한 번 맞춰 보고(시연 모드 확인) 보내는 스레드를 켠다. 반환: 켜졌는지"""
        st, body = self._post("/api/ingest/clock", self._clock_body())
        if st != 200:
            self.enabled = False
            why = body.get("detail", {}).get("reason") if isinstance(body, dict) else None
            self.log(f"[DB 중계] 꺼짐 — 백엔드가 시계를 받지 않음 (HTTP {st}{', ' + why if why else ''}). "
                     "백엔드 env에 MOM_SIM_SYNC=true(또는 시연 모드)가 있어야 켜진다")
            return False
        self.stats["clock"] += 1
        self._thread = threading.Thread(target=self._loop, name="db-relay", daemon=True)
        self._thread.start()
        self.log(f"[DB 중계] 켜짐 → {self.url} (10/1 기록 {SYNC_EVERY_SEC:g}초마다 바뀐 줄만, [처음으로] 때 DB도 되돌림)")
        return True

    # ---------------- 시연 서버가 부름
    def reset(self) -> None:
        """시연 서버 [처음으로]: 바로 맞추러 간다 (DB 되돌리기는 회차 번호가 바뀐 것을 보고 스레드가 한다)"""
        self._wake.set()

    # ---------------- 스레드
    def _loop(self) -> None:
        next_clock = time.monotonic() + CLOCK_EVERY_SEC
        while self.enabled:
            try:
                self.sync_once()
            except Exception as ex:          # 중계가 죽어도 시연 화면은 그대로
                self.stats["errors"] += 1
                self._say(f"[DB 중계] 처리 오류: {ex}")
            if time.monotonic() >= next_clock:
                self.sync_clock()
                next_clock = time.monotonic() + CLOCK_EVERY_SEC
            self._wake.wait(SYNC_EVERY_SEC)
            self._wake.clear()

    def sync_once(self) -> None:
        sig, run_id, tables = self.snap_fn(None if self.run_seen is None else self.sig)
        if run_id != self.run_seen:
            if tables is None:                       # 회차가 바뀌었는데 표를 안 줬으면 다시 받는다
                sig, run_id, tables = self.snap_fn(None)
            if not self.reset_db():
                return
            self.run_seen = run_id
        if tables is None:
            return
        if self.send(tables):
            self.sig = sig

    def reset_db(self) -> bool:
        st, body = self._post("/api/ingest/reset", self.base_fn() if self.base_fn else {})
        if st == 409 and isinstance(body, dict) and body.get("detail", {}).get("reason") == "BASELINE_MISMATCH":
            self.enabled = False                     # 기준점이 다르면 보내 봐야 번호가 겹친다 → 끈다
            self.log(f"[DB 중계] 꺼짐 — DB 시연 기준점이 시뮬레이터 시작점과 다름 {body['detail'].get('diff')}. "
                     "기준점을 다시 찍거나(fn_demo_snapshot) 생성기 시작점을 맞춘다")
            return False
        if st != 200:
            return False                             # 다음 차례에 다시 (그동안 줄을 보내지 않음 — 옛 회차와 섞이지 않게)
        self.sent.clear()
        self.sig = None
        self.stats["resets"] += 1
        self.log(f"[DB 중계] DB 처음으로 — 시연 기준점 {body.get('sim_at', '') if isinstance(body, dict) else ''} 으로 되돌림")
        self.sync_clock()
        return True

    def diff(self, tables: dict[str, tuple[list[str], list[tuple]]]) -> dict[str, dict]:
        """앞에 보낸 것과 비교해 바뀐(새로 생기거나 칸이 바뀐) 줄. 센서는 1분 값이 5초 값으로 바뀐 옛 줄을 지운다"""
        out = {}
        for t in ORDER:
            if t not in tables:
                continue
            cols, rows = tables[t]
            cur = set(rows)
            prev = self.sent.get(t, set())
            up = [r for r in rows if r not in prev]
            dels = []
            if t == SENSOR and prev:
                ki = [cols.index(c) for c in SENSOR_PK]
                keep = {tuple(r[i] for i in ki) for r in cur}
                dels = sorted({k for k in (tuple(r[i] for i in ki) for r in prev - cur) if k not in keep})
            if up or dels:
                out[t] = {"columns": cols, "upsert": up, "delete": dels, "_all": cur}
        return out

    def send(self, tables: dict[str, tuple[list[str], list[tuple]]]) -> bool:
        """바뀐 줄을 보낸다. 반환: 다 들어갔는지 (안 들어간 표는 다음 차례에 다시)"""
        d = self.diff(tables)
        if not d:
            return True
        ok = True
        main = {t: v for t, v in d.items() if t != SENSOR}
        if main and not self._post_sync(main):
            ok = False
            for t in [t for t in ORDER if t in main]:   # 함께 안 들어가면 하나씩 — 막힌 표만 남긴다
                ok = self._post_sync({t: main[t]}) and ok
        if SENSOR in d:
            s = d[SENSOR]
            up = s["upsert"]
            parts = [up[i:i + SENSOR_CHUNK] for i in range(0, len(up), SENSOR_CHUNK)] or [[]]
            good = all(self._post_sync({SENSOR: {**s, "upsert": p, "delete": s["delete"] if k == 0 else []}}, mark=False)
                       for k, p in enumerate(parts))
            if good:
                self.sent[SENSOR] = s["_all"]
            ok = ok and good
        if ok:
            self._last_err = None
        return ok

    def _post_sync(self, part: dict[str, dict], mark: bool = True) -> bool:
        body = {"tables": {t: {"columns": v["columns"], "upsert": [list(r) for r in v["upsert"]],
                               "delete": [list(k) for k in v["delete"]]} for t, v in part.items()}}
        st, out = self._post("/api/ingest/sync", body)
        if st != 200:
            return False
        if mark:
            for t, v in part.items():
                self.sent[t] = v["_all"]
        self.stats["syncs"] += 1
        self.stats["rows"] += sum(len(v["upsert"]) + len(v["delete"]) for v in part.values())
        return True

    def sync_clock(self) -> None:
        st, _ = self._post("/api/ingest/clock", self._clock_body())
        if st == 200:
            self.stats["clock"] += 1

    def _clock_body(self) -> dict:
        c = self.clock_fn()
        return {"sim_at": c["sim_at"], "speed": c.get("speed") or 1, "paused": bool(c.get("paused"))}

    def _say(self, msg: str) -> None:
        """같은 오류를 3초마다 되풀이해 찍지 않는다"""
        if msg != self._last_err:
            self._last_err = msg
            self.log(msg)

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
                tabs = ",".join(body.get("tables", {})) if path == "/api/ingest/sync" else ""
                self._say(f"[DB 중계] {path}{' ' + tabs if tabs else ''} 실패 HTTP {st}: {str(msg)[:200]}")
        return st, out

    @staticmethod
    def _http_post(url: str, body: dict, key: str) -> tuple[int, dict]:
        req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "X-Service-Key": key})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:    # noqa: S310 (로컬 주소만 — from_env가 확인)
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}
