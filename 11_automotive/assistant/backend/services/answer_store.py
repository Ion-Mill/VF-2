"""이어 묻기용 답 기억 (2026-10-12, FOLLOWUP=1 — [제안], 사용자 결정 "3번까지").

비서는 질문마다 따로 답한다. 화면이 바로 앞 답 번호(prev_answer_id)를 보내면, 서버가 그 번호로 기억해 둔 답의 기록
(answer.followup_record — 원문 줄·출처·운영 초안 글 등)을 꺼내 이어 묻기에 쓴다. 화면이 보낸 글은 믿지 않는다.

- 이 프로세스 메모리에만 둔다 (최근 500개, 4시간). 백엔드를 다시 켜면 비워지고, 그때 이어 물으면 "확인 필요"로 되묻는다 (안전).
- 주인: 같은 사용자(X-User)만, 사용자가 없으면 같은 역할만 꺼낸다. 없음·만료·남의 답은 같은 결과(None)를 낸다.
- 시연 초기화·사건 넣기 때 비운다 (운영 데이터가 바뀌므로).
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from collections import OrderedDict

MAX_ITEMS = 500
TTL_S = 4 * 3600
ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,40}$")

_lock = threading.Lock()
_items: OrderedDict[str, tuple[float, str, str, dict]] = OrderedDict()   # id → (저장 시각, 사용자, 역할, 기록)


def put(record: dict, user: str, role: str, now: float | None = None) -> str:
    aid = secrets.token_urlsafe(16)
    t = time.time() if now is None else now
    with _lock:
        _items[aid] = (t, user or "", (role or "").upper(), record)
        while len(_items) > MAX_ITEMS:
            _items.popitem(last=False)
    return aid


def get(aid: str | None, user: str, role: str, now: float | None = None) -> dict | None:
    if not aid or not ID_RE.match(aid):
        return None
    t = time.time() if now is None else now
    with _lock:
        got = _items.get(aid)
        if got is None:
            return None
        saved, owner, owner_role, record = got
        if t - saved > TTL_S:
            _items.pop(aid, None)
            return None
    if owner_role != (role or "").upper() or (owner or user) and owner != (user or ""):
        return None
    return record


def clear() -> None:
    with _lock:
        _items.clear()


def size() -> int:
    with _lock:
        return len(_items)
