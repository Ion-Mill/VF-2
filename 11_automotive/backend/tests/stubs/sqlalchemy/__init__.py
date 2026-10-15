"""가짜 sqlalchemy — import만 (tests/stubs/README.md). 엔진을 만들면 오류."""


def create_engine(*a, **kw):
    raise RuntimeError("시험용 가짜 sqlalchemy: 엔진을 만들 수 없음")


def text(sql):
    return sql
