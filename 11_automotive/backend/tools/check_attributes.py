"""논리 ERD 5장 엔터티 정의서의 속성 ↔ 실제 DB 칼럼 대조.

쓰는 법:
    python tools/check_attributes.py <논리ERD_최종본.md 경로> --psql "psql -d mom"

물리 설계에서 일부러 칼럼으로 두지 않은 속성(계산 → 뷰)은 VIEW_ATTRS에 적고,
그 뷰에 정말 그 칼럼이 있는지도 확인한다. 빠진 칼럼이 있으면 종료 코드 1.
"""
import argparse
import re
import shlex
import subprocess
import sys

# 엔터티.속성 → 그 값을 보여 주는 뷰 (docs/02_물리ERD.md 6장 "계산 속성")
VIEW_ATTRS = {
    "production_lot.completed_qty": "v_production_lot",
    "production_lot.expected_complete_at": "v_production_lot",
    "bottleneck_log.interval_end_at": "v_bottleneck_interval",
    "bottleneck_log.planned_qty": "v_bottleneck_interval",
    "maintenance_work_order.trigger_kind": "v_work_order",
    "pm_task.next_due_date": "v_pm_task_due",
    "tool.usage_rate_pct": "v_tool_life",
    "shipment.basis_order_nos": "v_shipment",
    "shipment.total_qty": "v_shipment",
    "inspection_plan.planned_measure_qty": "v_production_lot",
    "inspection_result.machined_equipment_id": "v_inspection_result",
    "notification.report_rank": "v_report_items",
}
# 모델을 고른 뒤 더하는 칼럼 (db/later/)
LATER_ATTRS = {"doc_chunk.embedding": "db/later/doc_chunk_embedding.sql (임베딩 모델·차원 결정 뒤)"}

COL_SQL = """SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public';"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("erd")
    ap.add_argument("--psql", default="psql -d mom")
    a = ap.parse_args()
    out = subprocess.run(shlex.split(a.psql) + ["-AtF", "|", "-c", COL_SQL],
                         check=True, capture_output=True, text=True).stdout
    cols = {tuple(l.split("|")) for l in out.splitlines()}
    text = open(a.erd, encoding="utf-8").read()
    sec = text.split("## 5. 엔터티 정의서", 1)[1].split("## 6. 코드 목록", 1)[0]
    ent, n_attr, missing, viewed, later = None, 0, [], [], []
    entities = set()
    for line in sec.splitlines():
        m = re.match(r"^#### 5\.\w\.\d+ `(\w+)`", line)
        if m:
            ent = m.group(1)
            entities.add(ent)
            continue
        if ent and line.startswith("| "):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(c) >= 6 and re.match(r"^[a-z_0-9]+$", c[0]):
                key = f"{ent}.{c[0]}"
                n_attr += 1
                if (ent, c[0]) in cols:
                    continue
                if key in VIEW_ATTRS:
                    v = VIEW_ATTRS[key]
                    (viewed if (v, c[0]) in cols else missing).append(f"{key} → {v}")
                elif key in LATER_ATTRS:
                    later.append(f"{key} → {LATER_ATTRS[key]}")
                else:
                    missing.append(key)
    tables = {t for t, _ in cols}
    missing_tables = sorted(entities - tables)
    print(f"엔터티 {len(entities)}개 (테이블 없음 {len(missing_tables)}개), 속성 {n_attr}개")
    print(f"  칼럼으로 있음: {n_attr - len(viewed) - len(later) - len(missing)}")
    print(f"  뷰에서 계산: {len(viewed)}")
    for v in viewed:
        print("    ", v)
    for l in later:
        print("  나중에:", l)
    for t in missing_tables:
        print("  테이블 없음:", t)
    for m in missing:
        print("  MISSING:", m)
    sys.exit(1 if (missing or missing_tables) else 0)


if __name__ == "__main__":
    main()
