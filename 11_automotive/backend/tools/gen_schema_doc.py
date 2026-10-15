"""실제 DB 카탈로그에서 물리 ERD 문서 만들기 → docs/02_물리ERD.md 의 표·그림 부분.

쓰는 법: python tools/gen_schema_doc.py --psql "psql -d mom" > /tmp/schema.md
묶음은 db/schema/*.sql 파일 단위. 그림(mermaid)은 묶음 안 외래 키만, 묶음 밖 연결은 표에 적는다.
"""
import argparse
import re
import shlex
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "10_master": "기준 정보", "20_production": "생산", "30_equipment_alarm": "설비·알람", "40_tool_shipment": "공구·재고·출하",
    "50_maintenance": "정비", "60_quality": "품질", "70_documents": "문서·보고서", "80_notification_auth": "알림·사용자·권한",
    "90_physical_extras": "물리 추가 (논리 ERD 밖)",
}


def rows(psql, sql):
    out = subprocess.run(shlex.split(psql) + ["-X", "-AtF", "\t", "-c", sql], check=True, capture_output=True, text=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psql", default="psql -d mom")
    a = ap.parse_args()
    group_of, head_comment = {}, {}
    for f in sorted((ROOT / "db/schema").glob("*.sql")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"CREATE TABLE (\w+)", line)
            if not m:
                continue
            group_of.setdefault(m.group(1), f.stem)
            j, block = i - 1, []
            while j >= 0 and lines[j].startswith("--"):
                text = lines[j].lstrip("- ").strip()
                if text and not set(text) <= set("-="):
                    block.insert(0, text)
                j -= 1
            if block:
                head_comment.setdefault(m.group(1), block[0])
    tables = rows(a.psql, """
        SELECT c.relname, coalesce(obj_description(c.oid), ''),
               (SELECT count(*) FROM pg_attribute x WHERE x.attrelid = c.oid AND x.attnum > 0 AND NOT x.attisdropped),
               coalesce((SELECT string_agg(a.attname, ', ' ORDER BY k.ord) FROM pg_constraint p
                         CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum, ord)
                         JOIN pg_attribute a ON a.attrelid = p.conrelid AND a.attnum = k.attnum
                         WHERE p.conrelid = c.oid AND p.contype = 'p'), ''),
               (SELECT count(*) FROM pg_constraint p WHERE p.conrelid = c.oid AND p.contype = 'c'),
               (SELECT count(*) FROM pg_constraint p WHERE p.conrelid = c.oid AND p.contype IN ('u','x')),
               (SELECT count(*) FROM pg_trigger g WHERE g.tgrelid = c.oid AND NOT g.tgisinternal),
               c.relkind
          FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r','p') AND NOT c.relispartition
         ORDER BY 1""")
    fks = rows(a.psql, """
        SELECT conrelid::regclass::text, confrelid::regclass::text,
               (SELECT string_agg(a.attname, ',') FROM unnest(conkey) k JOIN pg_attribute a ON a.attrelid = conrelid AND a.attnum = k),
               condeferrable
          FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace AND conparentid = 0
         ORDER BY 1, 2""")
    views = rows(a.psql, "SELECT viewname FROM pg_views WHERE schemaname = 'public' ORDER BY 1")
    funcs = rows(a.psql, """SELECT p.proname FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace
                             AND p.prokind = 'f' AND p.proname ~ '^(fn_|app_now)' ORDER BY 1""")
    out_fk = defaultdict(list)
    for child, parent, cols, deferrable in fks:
        out_fk[child].append((parent, cols, deferrable == "t"))
    by_group = defaultdict(list)
    for t in tables:
        by_group[group_of.get(t[0], "?")].append(t)

    print(f"<!-- tools/gen_schema_doc.py 가 실제 DB에서 만든 부분: 테이블 {len(tables)}개 (파티션 제외), "
          f"외래 키 {len(fks)}개, 뷰 {len(views)}개, 업무 함수 {len(funcs)}개 -->\n")
    for g, title in GROUPS.items():
        ts = by_group.get(g, [])
        if not ts:
            continue
        names = {t[0] for t in ts}
        print(f"### {title} (`db/schema/{g}.sql`, {len(ts)}개)\n")
        edges = [(c, p, cols) for c in sorted(names) for p, cols, _ in out_fk[c] if p in names and p != c]
        if edges:
            print("```mermaid\nerDiagram")
            for c, p, cols in edges:
                print(f'    {p} ||--o{{ {c} : "{cols}"')
            print("```\n")
        print("| 테이블 | 설명 | 칼럼 | PK | 바깥 참조 (FK) | CHECK | UNIQUE·EXCLUDE | 트리거 |")
        print("|---|---|---|---|---|---|---|---|")
        for name, comment, ncol, pk, nchk, nuq, ntrg, kind in ts:
            ext = sorted({f"{p}{' (지연)' if d else ''}" for p, _, d in out_fk[name] if p not in names or p == name})
            desc = (comment or head_comment.get(name, "")).replace("|", "/").replace("\n", " ")
            desc = (desc[:80] + "…" if len(desc) > 80 else desc) + (" · 파티션(1S·1M)" if kind == "p" else "")
            print(f"| `{name}` | {desc} | {ncol} | {pk} | {', '.join(ext) or '—'} | {nchk} | {nuq} | {ntrg} |")
        print()
    print("### 뷰 (계산 속성·화면용 읽기)\n")
    print(", ".join(f"`{v[0]}`" for v in views) + "\n")
    print("### 업무 함수 (여러 표를 함께 바꾸는 일 — db/functions/)\n")
    print(", ".join(f"`{f[0]}`" for f in funcs) + "\n")


if __name__ == "__main__":
    main()
