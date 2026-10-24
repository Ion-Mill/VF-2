"""접근 기록 (NFR-SEC-04). 요청 트랜잭션과 따로 저장한다 — 요청이 실패해 되돌려져도 기록은 남아야 하므로."""
from __future__ import annotations

import logging
from typing import Any

from .db import Db, side_engine

log = logging.getLogger("mom.audit")


def log_access(user_id: str | None, action: str, method: str | None = None, path: str | None = None,
               status_code: int | None = None, client_ip: str | None = None, detail: dict[str, Any] | None = None) -> None:
    try:
        with side_engine().begin() as conn:     # 요청 연결과 다른 줄 (db.side_engine — 여러 명 접속 때 서로 막지 않게)
            Db(conn).exec("common.access_log", user_id=user_id, action=action, method=method, path=path,
                          status_code=status_code, client_ip=client_ip, detail=detail)
    except Exception:  # 기록 실패가 업무를 막지 않게 (로그만)
        log.exception("접근 기록 실패: %s %s", action, path)
