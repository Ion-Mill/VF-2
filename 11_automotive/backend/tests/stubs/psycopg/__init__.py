"""가짜 psycopg — import만."""


class AsyncConnection:
    @classmethod
    async def connect(cls, *a, **kw):
        raise RuntimeError("시험용 가짜 psycopg")


def connect(*a, **kw):
    raise RuntimeError("시험용 가짜 psycopg")
