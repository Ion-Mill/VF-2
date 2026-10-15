"""논리 ERD 7장 관계 정의표 ↔ 실제 DB 외래 키 대조.

쓰는 법:
    python tools/check_relations.py <논리ERD_최종본.md 경로> --psql "psql -d mom"

표준 라이브러리만 쓴다. DB 조회는 psql 명령으로 한다 (드라이버 없이도 돌아가게).
결과: 관계마다 OK / MISSING(외래 키 없음) / 예외 목록(물리 설계에서 뷰·계산으로 바꾼 것)을 출력하고,
MISSING이 하나라도 있으면 종료 코드 1.
"""
import argparse
import re
import shlex
import subprocess
import sys

# 물리 설계에서 외래 키 대신 다른 방법으로 지키는 관계 (docs/02_물리ERD.md 9장)
PHYSICAL_EXCEPTIONS = {
    ("equipment", "inspection_result", "machined_equipment_id"):
        "뷰 v_inspection_result 에서 계산 ([제안] P-11) — 저장하지 않음",
    ("*", "document_revision", "doc_type"):
        "doc_type + doc_key 다형 참조 (문서 7종, 키 형식이 서로 다름) — fn_save_revision·문서 잠금 트리거가 확인",
}

FK_SQL = r"""
SELECT ccu.table_name AS parent, kcu.table_name AS child, kcu.column_name AS col
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
"""


def load_fks(psql_cmd):
    out = subprocess.run(shlex.split(psql_cmd) + ["-AtF", "|", "-c", FK_SQL],
                         check=True, capture_output=True, text=True).stdout
    fks = set()
    for line in out.splitlines():
        parent, child, col = line.split("|")
        fks.add((parent, child, col))
    return fks


def parse_relations(md_path):
    text = open(md_path, encoding="utf-8").read()
    sec = text.split("## 7. 관계 정의표", 1)[1].split("## 8.", 1)[0]
    rels = []
    for line in sec.splitlines():
        m = re.match(r"^\| (\d+) \| ([^|]+)\| ([^|]+)\| ([^|]+)\|", line)
        if not m:
            continue
        no, name, parent, child = (s.strip() for s in m.groups())
        parent = parent.strip("` ")
        # 자식 칸 예: "equipment (process_code)", "inspection_result (machined_equipment_id)"
        cm = re.match(r"`?(\w+)`?\s*\(([^)]*)\)", child)
        if not cm:
            rels.append((int(no), name, parent, child, []))
            continue
        cols = [c.strip(" `") for c in re.split(r"[,·/]| 및 ", cm.group(2)) if c.strip()]
        rels.append((int(no), name, parent, cm.group(1), cols))
    return rels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("erd")
    ap.add_argument("--psql", default="psql -d mom")
    a = ap.parse_args()
    fks = load_fks(a.psql)
    rels = parse_relations(a.erd)
    missing, ok, other = [], 0, []
    for no, name, parent, child, cols in rels:
        if not cols:
            other.append((no, name, parent, child, "자식 칸 형식을 못 읽음"))
            continue
        col_ok = []
        for col in cols:
            col = col.split()[0]
            hit = (parent, child, col) in fks
            exc = PHYSICAL_EXCEPTIONS.get((parent, child, col)) or PHYSICAL_EXCEPTIONS.get(("*", child, col))
            if col == "각":
                # "알림의 관련 기록"처럼 부모 여러 개가 자식 하나를 각각 가리키는 묶음 줄
                parents = [x.strip() for x in parent.split(",")]
                lacking = [x for x in parents if not any(f[0] == x and f[1] == child for f in fks)]
                hit = not lacking
                if lacking:
                    missing.append((no, name, ",".join(lacking), f"{child}.(각)"))
                    col_ok.append(False)
                    continue
            if hit:
                col_ok.append(True)
            elif exc:
                other.append((no, name, parent, f"{child}.{col}", exc))
                col_ok.append(True)
            else:
                col_ok.append(False)
                missing.append((no, name, parent, f"{child}.{col}"))
        if all(col_ok):
            ok += 1
    print(f"관계 {len(rels)}개 중 외래 키 일치 {ok}개")
    for o in other:
        print("  예외:", o)
    for m in missing:
        print("  MISSING:", m)
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
