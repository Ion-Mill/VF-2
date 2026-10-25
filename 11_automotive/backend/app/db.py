"""DB 연결 (SQLAlchemy 2 Core + psycopg 3). 쿼리는 app/sql/*.sql 의 이름으로만 부른다.

요청 1건 = 트랜잭션 1개 (get_db). 업무 규칙 위반은 DB가 오류로 막고(app/errors.py가 409로 바꿈),
여러 표를 함께 바꾸는 일은 DB 함수(fn_*) 하나로 부른다 (db/functions/).
"""
from __future__ import annotations

import json
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from .config import get_settings
from .sqlfiles import load_all

_engine: Engine | None = None
_ro_engine: Engine | None = None
_side_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_engine(s.database_url, pool_pre_ping=True, pool_size=int(s.db_pool_size),
                                max_overflow=int(s.db_max_overflow),
                                connect_args={"options": "-c timezone=Asia/Seoul"})
    return _engine


def side_engine() -> Engine:
    """요청 밖 짧은 일(접근 기록 쓰기, 가상 데이터 표시 읽기)용 작은 연결 줄 (2026-10-24).
    이 일들은 미들웨어에서 요청이 아직 자기 연결을 쥐고 있을 때 돈다 — 같은 줄(engine)을 쓰면 접속자가 많을 때
    모두가 서로의 연결을 기다리다 30초 뒤 TimeoutError가 난다(여러 명 접속 시험에서 실제로 남). 줄을 따로 두면 서로 막지 않는다"""
    global _side_engine
    if _side_engine is None:
        s = get_settings()
        _side_engine = create_engine(s.database_url, pool_pre_ping=True, pool_size=1, max_overflow=1, pool_timeout=10,
                                     connect_args={"options": "-c timezone=Asia/Seoul"})
    return _side_engine


def readonly_engine() -> Engine:
    """비서 조회 도구용. 읽기 전용 계정이 없으면 같은 DB를 읽기 전용 트랜잭션으로 연다."""
    global _ro_engine
    if _ro_engine is None:
        s = get_settings()
        url = s.readonly_database_url or s.database_url
        _ro_engine = create_engine(url, pool_pre_ping=True, pool_size=max(1, int(s.db_pool_size) // 2),
                                   max_overflow=max(0, int(s.db_max_overflow) // 2),
                                   connect_args={"options": "-c timezone=Asia/Seoul -c default_transaction_read_only=on"})
    return _ro_engine


def _prep(params: dict[str, Any]) -> dict[str, Any]:
    # dict·list는 JSON 글로 넘긴다 (SQL 쪽에서 CAST(:x AS jsonb))
    return {k: (json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v)
            for k, v in params.items()}


class Db:
    """이름 붙은 쿼리 실행기. 시험에서는 같은 메서드를 가진 tests/psqldb.py 로 바꿔 끼운다."""

    def __init__(self, conn: Connection):
        self.conn = conn
        self._q = load_all()

    def _run(self, name: str, params: dict[str, Any]):
        return self.conn.execute(text(self._q[name]), _prep(params))

    def all(self, name: str, **params) -> list[dict]:
        return [dict(r) for r in self._run(name, params).mappings()]

    def one(self, name: str, **params) -> dict | None:
        r = self._run(name, params).mappings().first()
        return dict(r) if r else None

    def scalar(self, name: str, **params):
        return self._run(name, params).scalar()

    def exec(self, name: str, **params) -> int:
        return self._run(name, params).rowcount


def get_db() -> Iterator[Db]:
    """FastAPI 의존성: 요청마다 트랜잭션 하나. 처리기에서 예외가 나면 되돌린다."""
    with engine().begin() as conn:
        yield Db(conn)


def get_ro_db() -> Iterator[Db]:
    with readonly_engine().begin() as conn:
        yield Db(conn)
