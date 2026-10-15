"""app/sql/*.sql 의 모든 이름 붙은 쿼리를 실제 DB에 PREPARE 해 본다 (실행은 하지 않음).

칼럼·테이블 이름이 스키마와 맞는지, 매개변수 형식을 알 수 있는지 확인한다.
쓰는 법: python tools/check_queries.py --psql "psql -d mom"
"""
import argparse
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.sqlfiles import PARAM, load_all  # noqa: E402


def to_dollar(sql: str) -> str:
    names: list[str] = []

    def repl(m):
        n = m.group(1)
        if n not in names:
            names.append(n)
        return f"${names.index(n) + 1}"

    return PARAM.sub(repl, sql)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psql", default="psql -d mom")
    a = ap.parse_args()
    queries = load_all()
    lines = ["\\set ON_ERROR_STOP 0"]
    for i, (name, sql) in enumerate(queries.items()):
        lines.append(f"\\echo @@{name}")
        lines.append(f"PREPARE q{i} AS {to_dollar(sql)};")
    lines.append("DEALLOCATE ALL;")
    current, errors = None, {}
    # psql은 오류를 stderr로, echo를 stdout으로 낸다 → 순서대로 받으려고 2>&1
    proc = subprocess.run(["bash", "-c", " ".join(shlex.quote(x) for x in shlex.split(a.psql) + ["-X", "-q"]) + " 2>&1"],
                          input="\n".join(lines) + "\n", capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if line.startswith("@@"):
            current = line[2:]
        elif "ERROR" in line and current:
            errors.setdefault(current, []).append(line.split("ERROR:", 1)[-1].strip())
    ok = len(queries) - len(errors)
    print(f"쿼리 {len(queries)}개 중 PREPARE 성공 {ok}개")
    for n, e in errors.items():
        print(f"  X {n}: {e[0]}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
