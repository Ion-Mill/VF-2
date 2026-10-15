"""docs/ 의 자동 생성 부분을 다시 만든다 (<!-- BEGIN:이름 --> … <!-- END:이름 --> 사이만 바꿈).

쓰는 법: python tools/update_docs.py --psql "psql -d mom_test" [--gen <생성기 폴더>]
  schema   → docs/02_물리ERD.md        (tools/gen_schema_doc.py, DB 필요)
  api      → docs/03_API_명세.md       (tools/gen_api_doc.py)
  contract → docs/04_데이터적재_약속.md (tools/gen_load_contract.py, DB 필요)
"""
import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = [("schema", "docs/02_물리ERD.md", ["tools/gen_schema_doc.py", "--psql", "{psql}"]),
        ("api", "docs/03_API_명세.md", ["tools/gen_api_doc.py"]),
        ("contract", "docs/04_데이터적재_약속.md", ["tools/gen_load_contract.py", "--psql", "{psql}", "{gen}"])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psql", default="psql -d mom")
    ap.add_argument("--gen", help="생성기 폴더 (적재 약속 표에 CSV 칼럼·행 수를 함께)")
    a = ap.parse_args()
    for name, doc, cmd in JOBS:
        args = [sys.executable]
        for c in cmd:
            if c == "{gen}":
                args += ["--gen", a.gen] if a.gen else []
            else:
                args.append(c.replace("{psql}", a.psql))
        out = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
        path = ROOT / doc
        text = path.read_text(encoding="utf-8")
        pat = re.compile(rf"(<!-- BEGIN:{name} -->\n).*?(\n<!-- END:{name} -->)", re.S)
        if not pat.search(text):
            raise SystemExit(f"{doc}: <!-- BEGIN:{name} --> 표시가 없음")
        path.write_text(pat.sub(lambda m: m.group(1) + out + m.group(2), text), encoding="utf-8")
        print(f"{doc}: {name} 갱신")


if __name__ == "__main__":
    main()
