"""시험용 Db: app.db.Db와 같은 메서드(all/one/scalar/exec)를 psql 명령으로 실행한다.

SQLAlchemy·psycopg 없이도 서비스 코드(app/services)가 실제 DB에서 도는지 확인하려고 쓴다.
매개변수는 SQL 글자로 바꿔 넣는다 (시험 전용 — 운영 코드는 반드시 바인딩 매개변수 사용).
"""
from __future__ import annotations

import csv
import datetime as dt
import decimal
import io
import json
import shlex
import subprocess

from app.sqlfiles import PARAM, load_all


def literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float, decimal.Decimal)):
        return str(v)
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, default=str)
    if isinstance(v, (dt.date, dt.datetime)):
        v = v.isoformat()
    return "'" + str(v).replace("'", "''") + "'"


class PsqlError(Exception):
    pass


class PsqlDb:
    def __init__(self, psql: str, prefix: str = ""):
        self.psql = shlex.split(psql)
        self.prefix = prefix          # 예: "SET ROLE mom_ai_ro;" (같은 psql 세션에서 먼저 실행)
        self.q = load_all()

    def render(self, name: str, params: dict) -> str:
        sql = self.q[name]

        def repl(m):
            key = m.group(1)
            if key not in params:
                raise KeyError(f"{name}: 매개변수 {key} 없음")
            return literal(params[key])

        return PARAM.sub(repl, sql)

    def _run(self, sql: str, quiet: bool) -> str:
        # SQL은 표준 입력으로 넘긴다 (-f -). 명령줄 인자(-c)로 넘기면 Windows 코드 페이지에서 한글이 깨진다 (2026-10-20)
        args = self.psql + ["-X", "--csv", "-v", "ON_ERROR_STOP=1"] + (["-q"] if quiet else []) + ["-f", "-"]
        p = subprocess.run(args, capture_output=True, text=True, input=self.prefix + sql, encoding="utf-8")
        if p.returncode != 0:
            raise PsqlError(p.stderr.strip())
        return p.stdout

    def all(self, name: str, **params) -> list[dict]:
        out = self._run(self.render(name, params), quiet=True)
        if not out.strip():
            return []
        # psql --csv는 참·거짓을 't'·'f' 글자로 낸다 → 진짜 드라이버(psycopg)처럼 bool로 바꾼다
        # (그대로 두면 'f'가 참으로 읽혀 is_active 같은 확인이 시험에서만 통과해 버린다)
        return [{k: (True if v == "t" else False if v == "f" else v) for k, v in row.items()}
                for row in csv.DictReader(io.StringIO(out))]

    def one(self, name: str, **params) -> dict | None:
        rows = self.all(name, **params)
        return rows[0] if rows else None

    def scalar(self, name: str, **params):
        row = self.one(name, **params)
        return None if row is None else next(iter(row.values()))

    def exec(self, name: str, **params) -> int:
        out = self._run(self.render(name, params), quiet=False).strip().splitlines()
        tag = out[-1] if out else ""
        parts = tag.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0


def clone_db(psql: str, template: str, name: str) -> str:
    """template DB를 복사해 시험용 DB를 만든다 (빠름). 반환: 그 DB에 붙는 psql 명령"""
    base = shlex.split(psql)
    for sql in (f"DROP DATABASE IF EXISTS {name}", f"CREATE DATABASE {name} TEMPLATE {template}"):
        p = subprocess.run(base + ["-X", "-q", "-d", "postgres", "-c", sql], capture_output=True, text=True)
        if p.returncode != 0:
            raise PsqlError(p.stderr.strip())
    return f"{psql} -d {name}"


def drop_db(psql: str, name: str) -> None:
    subprocess.run(shlex.split(psql) + ["-X", "-q", "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {name}"],
                   capture_output=True, text=True)
