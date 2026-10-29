"""5단계 ①: 측정한 부품의 항목별 측정값(inspection_result)과 측정 결과 파일 가져오기 기록(cmm_import).

설계서 5.15, DOC-06 §2·§3·§6, 논리 ERD 5.F.4·5.F.6.
- 측정값 = 규격 가운데 근처 정규분포. 공정능력 Cpk는 항목마다 정한 범위 안 (1번 구멍 1.67 이상 — DOC-06 §2).
- 평균이 움직인 부품(공구 사용률 90% 넘음, 108·충돌 직후)은 평균을 조금 옮긴다 [가상].
- 치수 불량 부품(시간 흐름에서 정함)은 그 항목 값을 규격 밖으로. 판정은 값으로 다시 계산 (= 측정기 판정, 불일치 0).
- 부품 온도 = 뉴턴 냉각식 (DOC-06 §6.1: 세척 뒤 50 ± 3 ℃, 측정실 20 ℃, 시간 상수 48분).
"""
from __future__ import annotations

import math

from .flow import OPR_BY_PROC, Sim

COLS = {
    "inspection_result": ["result_id", "lot_no", "part_seq", "product_code", "item_seq", "insp_kind", "position",
                          "measured_value", "judgement", "instrument_id", "inspector_id", "measured_at", "room_temp_c",
                          "part_temp_c", "temp_comp_used", "input_method", "cmm_import_id", "cmm_judgement",
                          "check_status", "checked_by", "checked_at", "remeasure_seq", "use_for_judgement",
                          "entered_by"],
    "cmm_import": ["cmm_import_id", "file_name", "received_at", "status", "error_kind", "error_text",
                   "original_file_ref", "instrument_id", "lot_no", "part_seq", "insp_kind", "program_name_rev",
                   "measure_start_at", "measure_end_at", "machine_temp_c", "temp_comp_on"],
}
DIM_ITEMS = {"DIM-01": [1, 2, 3, 8], "DIM-02": [1, 2, 3, 8], "DIM-03": [4], "DIM-04": [5]}
POSITIONS = ["TOP", "MID", "BOTTOM"]          # 강화 때 부싱 구멍 3단 (ERD position 위·중간·아래) [제안: 코드]


def _num(x):
    return float(x) if x not in (None, "") else None


class Process:
    """항목마다 공정 분포 (평균, 표준편차). 한 번 정하면 30일 내내 같음."""

    def __init__(self, items, q, r):
        self.p = {}
        for it in items:
            seq, lsl, usl = int(it["item_seq"]), _num(it["lsl"]), _num(it["usl"])
            if usl is None:
                continue
            cmin = _num(it["cpk_min"]) or 1.33
            lo, hi = q["cpk_item1"] if seq == 1 else q["cpk_normal"]
            cpk = float(r.uniform(max(lo, cmin), hi))
            if lsl is None:                       # 한쪽 규격 (평면도): 평균 = 상한의 40% [가상]
                mean = usl * q["one_sided_mean_ratio"]
                sd = (usl - mean) / (3 * cpk)
            else:
                mean = (lsl + usl) / 2
                sd = (usl - lsl) / (6 * cpk)
            self.p[seq] = (mean, sd, lsl, usl, cpk)


def _judge(v, lsl, usl):
    return "PASS" if (lsl is None or v >= lsl - 1e-12) and v <= usl + 1e-12 else "FAIL"


FILE_COLS = ["lot_no", "part_seq", "insp_kind", "program_name_rev", "item_seq", "position", "nominal", "upper_tol",
             "lower_tol", "measured_value", "judgement", "instrument_id", "measure_start_at", "measure_end_at",
             "part_temp_c", "machine_temp_c", "temp_comp_on"]     # 결과 파일 양식 (CMM 조사 5.2 [제안])


class Measurer:
    """측정 1건(부품 1개) → 측정값 줄들 + 결과 파일 가져오기 줄 (과거 기록·실시간이 같은 코드)."""

    def __init__(self, cfg, masters, r, cal, r_values=None):
        """r: 공정 분포(Cpk)를 정하는 난수 — 과거·실시간이 같은 값. r_values: 측정값 난수 (실시간은 따로)."""
        self.q, self.cal = cfg["quality"], cal
        items = [it for it in masters["inspection_item"] if it["product_code"] == "BRK-A100"]
        self.proc = Process(items, self.q, r)
        self.r = r_values or r
        self.items = {int(it["item_seq"]): it for it in items}
        self.cmm_items = [int(it["item_seq"]) for it in items if it["method"] == "CMM" and it["in_sampling"] == "true"]

    def measure(self, ev, rid0: int, iid: int):
        q, r, cal = self.q, self.r, self.cal
        part, lot = ev["part"], ev["lot"]
        kind = "ENHANCED" if ev["enhanced"] else ("FIRST" if part.idx == 1 else "SAMPLE")
        start, end = cal.to_dt(ev["start_m"]), cal.to_dt(ev["end_m"])
        sh = cal.shift_or_near(ev["start_m"])
        inspector = OPR_BY_PROC[sh.shift_type]["OP-50"]
        room = q["room_temp_c"]
        arr = ev["arr50"] if ev["arr50"] is not None else ev["start_m"]
        t_out = float(r.uniform(*q["wash_exit_temp_c"]))
        part_t = round(room + (t_out - room) * math.exp(-(ev["start_m"] - arr) / q["soak_tau_min"]), 1)
        dim = part.defect[1] if part.defect and part.defect[1].startswith("DIM") else None
        bad_item = int(r.choice(DIM_ITEMS[dim])) if dim else None
        boosted = part.boost_tool is not None or part.boost_alarm
        sign = float(r.choice([-1.0, 1.0]))
        fname = f"BRK-A100_{lot.lot_no}_{part.idx:03d}_{end:%Y%m%d%H%M}.csv"
        imp = {"cmm_import_id": iid, "file_name": fname, "received_at": cal.to_dt(ev["end_m"] + 1), "status": "SUCCESS",
               "error_kind": None, "error_text": None, "original_file_ref": f"처리됨/{fname}", "instrument_id": "CMM-01",
               "lot_no": lot.lot_no, "part_seq": part.idx, "insp_kind": kind, "program_name_rev": q["cmm_program"],
               "measure_start_at": start, "measure_end_at": end, "machine_temp_c": room, "temp_comp_on": True}
        rows = []
        for seq in self.cmm_items:
            mean, sd, lsl, usl, _ = self.proc.p[seq]
            for pos in (POSITIONS if (kind == "ENHANCED" and seq == 1) else [None]):
                if seq == bad_item and (pos is None or pos == "MID"):   # 치수 불량: 규격 밖 (3단이면 가운데만)
                    over = float(r.uniform(0.2, 1.5)) * sd
                    v = (lsl - over) if dim == "DIM-02" else ((usl + over) if (dim != "DIM-03" or sign > 0) else (lsl - over))
                else:
                    v = float(r.normal(mean + (sign * q["boost_mean_shift_sigma"] * sd if boosted else 0.0), sd))
                    if lsl is None:
                        v = max(v, 0.0)
                    # 정상 부품이 우연히 규격 밖으로 나가지 않게 (불합격은 시간 흐름이 정한 불량만)
                    v = min(max(v, lsl + 0.1 * sd if lsl is not None else 0.0), usl - 0.1 * sd)
                v = round(v, 4)
                rows.append((seq, pos, v, _judge(v, lsl, usl), "CMM_AUTO", iid))
        if not ev["recheck"]:                     # M6 나사 게이지 (태블릿 버튼) — 처음 잴 때만
            thr = bool(part.defect and part.defect[1].startswith("THR"))
            rows.append((6, None, None, "FAIL" if thr else "PASS", "TABLET", None))
        if kind == "ENHANCED":                    # 강화: 외관을 확대경으로 (DOC-06 §3.3)
            sur = bool(part.defect and part.defect[1].startswith("SUR"))
            rows.append((7, None, None, "FAIL" if sur else "PASS", "TABLET", None))
        res, fail_rid = [], None
        for k, (seq, pos, v, j, method, cid) in enumerate(rows):
            rid = rid0 + k
            cmm = method == "CMM_AUTO"
            res.append({"result_id": rid, "lot_no": lot.lot_no, "part_seq": part.idx, "product_code": "BRK-A100",
                        "item_seq": seq, "insp_kind": kind, "position": pos, "measured_value": v, "judgement": j,
                        "instrument_id": "CMM-01", "inspector_id": inspector, "measured_at": start,
                        "room_temp_c": room if cmm else None, "part_temp_c": part_t if cmm else None,
                        "temp_comp_used": True if cmm else None, "input_method": method, "cmm_import_id": cid,
                        "cmm_judgement": j if cmm else None, "check_status": "NORMAL", "checked_by": None,
                        "checked_at": None, "remeasure_seq": 1, "use_for_judgement": True, "entered_by": None})
            if j == "FAIL" and fail_rid is None:
                fail_rid = rid
        return res, imp, fail_rid

    def file_rows(self, res: list[dict], imp: dict) -> list[dict]:
        """측정기가 공유 폴더에 쓰는 결과 파일 내용 (CMM 항목만, 항목마다 한 줄)."""
        out = []
        for x in res:
            if x["input_method"] != "CMM_AUTO":
                continue
            it = self.items[x["item_seq"]]
            nom = _num(it["nominal"])
            lsl, usl = _num(it["lsl"]), _num(it["usl"])
            out.append({"lot_no": x["lot_no"], "part_seq": x["part_seq"], "insp_kind": x["insp_kind"],
                        "program_name_rev": imp["program_name_rev"], "item_seq": x["item_seq"], "position": x["position"],
                        "nominal": nom, "upper_tol": round(usl - (nom or 0.0), 4),
                        "lower_tol": round(lsl - nom, 4) if (lsl is not None and nom is not None) else None,
                        "measured_value": x["measured_value"], "judgement": x["cmm_judgement"],
                        "instrument_id": "CMM-01", "measure_start_at": imp["measure_start_at"],
                        "measure_end_at": imp["measure_end_at"], "part_temp_c": x["part_temp_c"],
                        "machine_temp_c": imp["machine_temp_c"], "temp_comp_on": True})
        return out


def build_inspection(cfg, sim: Sim, masters, rng):
    """돌려주는 값: (inspection_result 줄, cmm_import 줄, 불량 부품 pid → 불합격 result_id, 측정기)."""
    me = Measurer(cfg, masters, rng.stream("measure"), sim.cal)
    res, imp, fail_rid = [], [], {}
    for ev in sorted(sim.measure_log, key=lambda e: (e["end_m"], e["lot"].lot_no, e["part"].idx)):
        rows, row_imp, frid = me.measure(ev, len(res) + 1, len(imp) + 1)
        res += rows
        imp.append(row_imp)
        if frid is not None and ev["part"].pid not in fail_rid:
            fail_rid[ev["part"].pid] = frid
    return res, imp, fail_rid, me
