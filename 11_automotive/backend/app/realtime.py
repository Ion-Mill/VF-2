"""실시간 이벤트: PostgreSQL LISTEN mom_events → 연결된 화면들(SSE)에 나눠 보냄.

DB 트리거(trg_notify_event)가 알림·알람·설비 상태가 바뀔 때 {table, op, id, equipment_id}를 보낸다.
내용은 싣지 않는다 — 화면은 이벤트를 받으면 권한이 걸린 API(/api/line/twin, /api/notifications)를 다시 부른다.
DB 연결 하나로 듣고(서버 프로세스마다 1개, 스레드), 화면마다 큐를 하나씩 둔다.
"""
from __future__ import annotations

import asyncio
import logging
import threading

import psycopg

from .config import get_settings

log = logging.getLogger("mom.realtime")
CHANNEL = "mom_events"
RESYNC = '{"table": "*", "op": "RESYNC"}'


def psycopg_dsn(sqlalchemy_url: str) -> str:
    """postgresql+psycopg://... → postgresql://... (psycopg가 직접 여는 주소)"""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


class Broadcaster:
    def __init__(self, queue_size: int = 100):
        self._subs: set[asyncio.Queue[str]] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._queue_size = queue_size

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=self._queue_size)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subs.discard(q)

    def publish(self, payload: str) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:  # 느린 화면은 오래된 것을 버리고 "다시 불러오기"만 알게 한다
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                q.put_nowait(RESYNC)

    def _listen_blocking(self, loop: asyncio.AbstractEventLoop, stop: threading.Event) -> None:
        """스레드에서 도는 LISTEN (동기 연결). psycopg 비동기 연결은 Windows 기본 이벤트 루프(Proactor)에서 못 쓰므로
        운영체제와 상관없이 돌게 스레드 + 동기 연결로 듣고, 받은 것은 이벤트 루프로 넘긴다"""
        dsn = psycopg_dsn(get_settings().database_url)
        delay = 1.0
        while not stop.is_set():
            try:
                with psycopg.connect(dsn, autocommit=True) as conn:
                    conn.execute(f"LISTEN {CHANNEL}")
                    log.info("LISTEN %s 시작", CHANNEL)
                    delay = 1.0
                    loop.call_soon_threadsafe(self.publish, RESYNC)   # 다시 연결되면 화면이 전체를 다시 부르게
                    while not stop.is_set():
                        for n in conn.notifies(timeout=1.0):          # 1초마다 멈춤 신호를 본다
                            loop.call_soon_threadsafe(self.publish, n.payload)
            except Exception:
                if stop.is_set():
                    break
                log.exception("LISTEN 연결 끊김 — %.0f초 뒤 다시", delay)
                stop.wait(delay)
                delay = min(delay * 2, 30.0)

    def start(self) -> None:
        if self._thread is None:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._listen_blocking, args=(asyncio.get_running_loop(), self._stop),
                                            name="mom-listen", daemon=True)
            self._thread.start()

    async def stop(self) -> None:
        if self._thread is not None:
            self._stop.set()
            await asyncio.to_thread(self._thread.join, 5.0)
            self._thread = None


broadcaster = Broadcaster()
