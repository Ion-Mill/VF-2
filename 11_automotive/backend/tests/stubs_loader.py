"""FastAPI·SQLAlchemy·psycopg가 없으면 tests/stubs 의 가짜 모듈을 쓴다. 있으면 아무것도 안 함."""
import importlib.util
import os
import sys

STUBS = os.path.join(os.path.dirname(__file__), "stubs")


def use_stubs_if_needed() -> bool:
    missing = [m for m in ("fastapi", "sqlalchemy", "psycopg", "starlette") if importlib.util.find_spec(m) is None]
    if missing and STUBS not in sys.path:
        sys.path.insert(0, STUBS)
    return bool(missing)
