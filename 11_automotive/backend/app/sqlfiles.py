"""app/sql/*.sql 의 이름 붙은 쿼리 읽기 (표준 라이브러리만).

파일 안에서 `-- name: 쿼리이름` 줄 다음부터 다음 `-- name:`까지가 한 쿼리다.
전체 이름은 "파일이름.쿼리이름" (예: line.plant). 서버는 db.all("line.plant") 처럼 이름으로만 부른다.
쿼리를 코드 안에 흩어 두지 않으므로 tools/check_queries.py 가 모든 쿼리를 실제 DB에 PREPARE 해 볼 수 있다.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SQL_DIR = Path(__file__).parent / "sql"
_NAME = re.compile(r"^--\s*name:\s*([A-Za-z0-9_]+)\s*$", re.M)
# SQLAlchemy text()와 같은 규칙: 앞이 콜론·글자·역슬래시가 아니고 뒤가 콜론이 아닌 :이름
PARAM = re.compile(r"(?<![:\w\\]):([A-Za-z_]\w*)(?!:)")


def parse(text: str, prefix: str) -> dict[str, str]:
    queries: dict[str, str] = {}
    parts = _NAME.split(text)
    for i in range(1, len(parts), 2):
        name, body = parts[i], parts[i + 1]
        sql = "\n".join(line for line in body.strip().splitlines() if not line.lstrip().startswith("--")).strip()
        if sql.endswith(";"):
            sql = sql[:-1].rstrip()
        key = f"{prefix}.{name}"
        if key in queries:
            raise ValueError(f"쿼리 이름 중복: {key}")
        queries[key] = sql
    return queries


@lru_cache(maxsize=1)
def load_all(sql_dir: str | None = None) -> dict[str, str]:
    d = Path(sql_dir) if sql_dir else SQL_DIR
    out: dict[str, str] = {}
    for f in sorted(d.glob("*.sql")):
        out.update(parse(f.read_text(encoding="utf-8"), f.stem))
    return out


def params_of(sql: str) -> list[str]:
    seen: list[str] = []
    for m in PARAM.finditer(sql):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen
