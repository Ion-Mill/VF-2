"""논리 ERD 6장 코드 목록 → db/seed/10_code_labels.sql 생성.

쓰는 법:
    python tools/gen_code_labels.py <논리ERD.md> > db/seed/10_code_labels.sql

코드 목록이 바뀌면 이 스크립트를 다시 돌린다 (손으로 고치지 않음). 표준 라이브러리만 쓴다.
"""
import re
import sys

# 절 번호 → (code_group, 코드 칸 번호, 이름 칸 번호). code_group이 None이면 '칸' 열 값으로 정한다.
CONF = {
    "6.1": ("equipment_state_log.state_code", 0, 1), "6.2": ("equipment_state_log.mtconnect_execution", 0, 1),
    "6.3": ("alarm_master.severity", 0, 1), "6.4": ("alarm_master.responder", 0, 1),
    "6.5": ("downtime_reason.reason_code", 1, 2), "6.6": ("equipment_state_log.reason_status", 0, 1),
    "6.7": ("production_order.status", 0, 1), "6.8": ("production_lot.status", 0, 1),
    "6.9": ("raw_material_lot.status", 0, 1), "6.10": ("shift.shift_type", 0, 1),
    "6.11": ("bottleneck_log.cause_code", 0, 2), "6.12": ("lot_hold.trigger_type", 0, 1),
    "6.13": ("maintenance_work_order.status", 0, 1), "6.14": ("work_record.record_type", 0, 1),
    "6.15": ("work_record.status", 0, 1), "6.16": ("report.status", 0, 1),
    "6.17": ("document_revision.doc_type", 0, 1), "6.18": ("author_kind", 0, 1),
    "6.19": ("work_record_check.loto_step_code", 0, 1), "6.20": ("lockout_level", 0, 1),
    "6.21": ("isolation_point.energy_type", 0, 1), "6.22": ("pm_task.cycle_code", 0, 1),
    "6.23": ("pm_record.result", 0, 1), "6.24": ("tool_type.usage_unit", 0, 1),
    "6.26": (None, 1, 2), "6.28": (None, 1, 2), "6.30": ("inspection_item.char_class", 0, 1),
    "6.31": ("inspection_item.method", 0, 1), "6.32": (None, 1, 2), "6.33": (None, 1, 2),
    "6.34": ("defect_code", 0, 1), "6.35": ("importance", 0, 1), "6.36": ("notification_rule.rule_code", 0, 1),
    "6.37": ("role.role_code", 0, 1), "6.40": ("alarm_event.scenario_code", 0, 1), "6.41": ("source_tag", 0, 1),
    "6.42": ("maintenance_work_order.trigger_kind", 0, 1), "6.43": ("notification.report_rank", 0, 2),
    "6.44": ("shipment.status", 0, 1), "6.45": ("shipment.customer_code", 0, 1),
    "6.46": ("inspection_result.input_method", 0, 1), "6.47": ("inspection_result.check_status", 0, 1),
    "6.48": (None, 1, 2), "6.49": ("layout_object.object_kind", 0, 1), "6.50": ("equipment_part_shape.shape_kind", 0, 1),
    "6.51": ("equipment.facing", 0, 1), "6.52": ("internal_doc.doc_kind", 0, 1), "6.53": ("retention_stage", 0, 1),
    "6.54": ("notification.repeat_stage_status", 0, 1),
}
# '칸' 열 값 → code_group
KAN = {"tool_role": "tool.tool_role", "change_reason": "tool_change.change_reason",
       "txn_type": "inventory_txn.txn_type", "source_kind": "inventory_txn.source_kind",
       "insp_kind (부품)": "insp_kind", "plan_mode (로트)": "inspection_plan.plan_mode",
       "enhance_reason": "inspection_plan.enhance_reason", "inspection_result": "inspection_result.judgement",
       "inspection_plan": "inspection_plan.judgement", "status": "cmm_import.status", "error_kind": "cmm_import.error_kind"}
# 결함 등급 (6.34 두 번째 표)
GRADE_HEADER = "결함 등급 코드"


def clean(s):
    s = re.sub(r"\*\*|`", "", s).strip()
    s = re.sub(r"\s*\[(제안|가상|참고|실제)[^\]]*\]", "", s)
    return s.strip()


def q(s):
    return "'" + s.replace("'", "''") + "'"


def main(path):
    text = open(path, encoding="utf-8").read()
    sec = text.split("## 6. 코드 목록", 1)[1].split("## 7. 관계 정의표", 1)[0]
    parts = re.split(r"\n### (6\.\d+) ", sec)
    rows = []
    for i in range(1, len(parts), 2):
        num, body = parts[i], parts[i + 1]
        if num not in CONF:
            continue
        group, ci, ni = CONF[num]
        order = 0
        grade_mode = False
        first_done = False   # 절마다 첫 표만 쓴다 (6.36 "알림 종류별 처리" 같은 둘째 표는 코드 목록이 아님)
        seen_rows = False
        for line in body.splitlines():
            if not line.startswith("|"):
                if seen_rows:
                    first_done = True
                continue
            if line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if GRADE_HEADER in cells[0]:
                grade_mode = True
                continue
            if first_done and not grade_mode:
                continue
            seen_rows = True
            if cells[0] in ("코드", "칸", "그룹") or cells[0].startswith("코드 [") or cells[0].startswith("규칙 코드"):
                continue
            if grade_mode:
                g, c, n = "defect_code.grade", clean(cells[0]), clean(cells[1])
            else:
                g = group or KAN.get(clean(cells[0]))
                c, n = clean(cells[ci]), clean(cells[ni])
            if not g or not c or c.startswith("(") or not re.match(r"^[A-Za-z0-9_.\-]+$", c):
                continue
            if c.isdigit():   # 6.53 아래 "엔터티별 보관 기간" 표처럼 번호 줄은 코드가 아님
                continue
            order += 1
            rows.append((g, c, n, order, num))
    print("-- 생성: tools/gen_code_labels.py (논리ERD 6장). 손으로 고치지 말고 스크립트를 다시 돌린다.")
    print("INSERT INTO code_label (code_group, code, name_ko, sort_order, source_ref) VALUES")
    print(",\n".join(f"  ({q(g)}, {q(c)}, {q(n)}, {o}, {q(s)})" for g, c, n, o, s in rows))
    print("ON CONFLICT (code_group, code) DO UPDATE SET name_ko = EXCLUDED.name_ko, sort_order = EXCLUDED.sort_order,")
    print("    source_ref = EXCLUDED.source_ref;")
    print(f"-- {len(rows)}행", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
