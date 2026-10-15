"""code_label(논리 ERD 6장 코드) ↔ 테이블 CHECK 제약의 허용 값 대조.

쓰는 법: python tools/check_codes.py --psql "psql -d mom"
code_label 그룹 이름이 '테이블.칼럼'인 것만 본다. 다르면 종료 코드 1.
"""
import argparse
import re
import shlex
import subprocess
import sys

SQL_CHECKS = r"""SELECT conrelid::regclass::text, regexp_replace(pg_get_constraintdef(oid), '\s+', ' ', 'g') FROM pg_constraint
                WHERE contype = 'c' AND connamespace = 'public'::regnamespace;"""
SQL_LABELS = "SELECT code_group, code FROM code_label;"
# 그룹 이름 → 실제 칼럼 (code_label 그룹이 여러 칼럼에 같이 쓰이는 경우)
ALIASES = {"report.status": ["shift_report.status", "daily_report.status"],
           "insp_kind": ["inspection_result.insp_kind", "cmm_instruction.insp_kind", "cmm_import.insp_kind"],
           "lockout_level": ["alarm_master.lockout_level", "pm_task.lockout_level"],
           "source_tag": ["equipment.size_source_tag", "layout_object.source_tag", "equipment_part_shape.source_tag", "pm_task.source_tag"],
           "author_kind": ["document_revision.author_kind", "work_record_part.proposed_by_kind"],
           "importance": ["notification_rule.importance", "notification.importance"],
           "inspection_plan.enhance_reason": ["inspection_plan.enhance_reason", "cmm_instruction.enhance_reason"]}
# CHECK 대신 표(FK)로 지키는 코드 그룹
FK_GROUPS = {"downtime_reason.reason_code", "notification_rule.rule_code", "role.role_code", "defect_code",
             "notification.report_rank", "retention_stage", "maintenance_work_order.trigger_kind",
             "shipment.customer_code"}


def run(psql, sql):
    out = subprocess.run(shlex.split(psql) + ["-AtF", "\t", "-c", sql], check=True, capture_output=True, text=True).stdout
    return [l.split("\t") for l in out.splitlines() if l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psql", default="psql -d mom")
    a = ap.parse_args()
    allowed = {}
    for table, cdef in run(a.psql, SQL_CHECKS):
        for m in re.finditer(r"\(\"?(\w+)\"?\)::text = ANY \(\(ARRAY\[(.*?)\]\)", cdef):
            col, vals = m.group(1), re.findall(r"'([^']*)'", m.group(2))
            allowed.setdefault(f"{table}.{col}", set()).update(vals)
    labels = {}
    for g, c in run(a.psql, SQL_LABELS):
        labels.setdefault(g, set()).add(c)
    bad = 0
    for g, codes in sorted(labels.items()):
        if g in FK_GROUPS:
            continue
        targets = ALIASES.get(g, [g])
        for t in targets:
            if t not in allowed:
                print(f"  ?  {g}: CHECK 목록 없음 ({t})")
                continue
            miss, extra = codes - allowed[t], allowed[t] - codes
            if miss or extra:
                bad += 1
                print(f"  X  {t}: 코드 목록에만 {sorted(miss)} / CHECK에만 {sorted(extra)}")
            else:
                print(f"  OK {t} ({len(codes)})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
