"""문서·데이터 연결 점검 (2026-10-24, DB 담당 전달용).

과거 기록(out_*/)과 실시간 기록(out_realtime_*/)을 **DB에 넣는 모양 그대로 합쳐서** 아래를 본다.
  1. 번호 중복 없음 (표마다 기본 키)
  2. 외래 키 — 가리키는 값이 있음 (validate.py와 같은 목록, 합친 데이터에서)
  3. 문서 ↔ 데이터: OP-30 정지 알람 ↔ 작업지시서 ↔ 작업기록서 ↔ 설비 상태(DOWN) ↔ 사용 부품 ↔ 재고 거래 ↔ 로트 보류
  4. 실시간이 과거 기록 뒤에 이어짐 (번호·시각·열린 구간)
실행: .venv\\Scripts\\python check_links.py --profile final      (video 도 같다)
결과 줄: PASS / FAIL (고쳐야 함) / INFO (알아 둘 것). 실패가 있으면 종료 코드 1.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import validate
from gen.common import ROOT, load_config, load_masters, set_profile_from_args

# 실시간 기록이 과거 기록의 같은 번호 행을 덮어쓰는 표 (DB에는 덮어쓰기) — 나머지는 이어 붙임
OVERRIDE = {"production_order": ["order_no"], "production_lot": ["lot_no"], "inspection_plan": ["lot_no"], "lot_hold": ["hold_id"]}
# 기본 키 (표 하나에 칸 하나인 것)
PK = {"alarm_event": "alarm_event_id", "equipment_state_log": "state_log_id", "operation_report": "op_report_id",
      "tool_change": "tool_change_id", "inspection_result": "result_id", "cmm_import": "cmm_import_id",
      "defect_record": "defect_record_id", "pm_record": "pm_record_id", "inventory_txn": "txn_id", "lot_hold": "hold_id",
      "bottleneck_log": "bottleneck_log_id", "maintenance_work_order": "wo_no", "work_record": "record_no",
      "production_order": "order_no", "production_lot": "lot_no", "shift": "shift_id", "work_day": "work_date",
      "notification": "notification_id", "shipment": "shipment_no", "raw_material_lot": "material_lot_no",
      "inspection_plan": "lot_no"}


def read_dir(d: Path) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted(d.glob("*.csv")) if p.stem != "sensor_sample"}


def merge(past: dict, rt: dict) -> dict[str, pd.DataFrame]:
    out = dict(past)
    for name, df in rt.items():
        if name not in out:
            out[name] = df
        elif name in OVERRIDE:
            both = pd.concat([out[name], df], ignore_index=True)
            out[name] = both.drop_duplicates(OVERRIDE[name], keep="last").reset_index(drop=True)
        else:
            out[name] = pd.concat([out[name], df], ignore_index=True)
    return out


def main() -> int:
    set_profile_from_args()
    cfg = load_config()
    masters = load_masters(cfg)
    pdir, rdir = ROOT / cfg["run"]["out_dir"], ROOT / cfg["realtime"]["out_dir"]
    if not (pdir / "manifest.json").exists() or not (rdir / "manifest.json").exists():
        print(f"먼저 generate.py --profile {cfg['profile']['name']} 와 realtime.py --profile {cfg['profile']['name']} 를 돌려 {pdir.name}/ 과 {rdir.name}/ 을 만든다")
        return 2
    P, R = read_dir(pdir), read_dir(rdir)
    T = merge(P, R)
    lines: list[tuple[str, str, str]] = []

    def add(name, ok, detail="", info=False):
        lines.append(("INFO" if info and not ok else ("PASS" if ok else "FAIL"), name, str(detail)))

    ts = lambda s: pd.to_datetime(s)

    # ---- 1. 기본 키 중복 ----
    dup = {k: int(T[k][col].duplicated().sum()) for k, col in PK.items() if k in T}
    add("번호 중복 없음 (과거 + 실시간 합친 표, 표마다 기본 키)", not any(dup.values()), {k: v for k, v in dup.items() if v})
    comp = {"work_order_step": ["wo_no", "step_no"], "work_record_check": ["record_no", "check_seq"],
            "work_record_part": ["record_no", "item_no"], "work_order_part": ["wo_no", "item_no"]}
    cd = {k: int(T[k].duplicated(cols).sum()) for k, cols in comp.items() if k in T}
    add("복합 번호 중복 없음 (작업 단계·체크·부품)", not any(cd.values()), {k: v for k, v in cd.items() if v})

    # ---- 2. 외래 키 ----
    bad = []
    for tab, col, valid in validate.foreign_keys(T, masters):
        v = T[tab][col]
        v = v[v != ""]
        miss = set(v) - set(valid)
        if miss:
            bad.append(f"{tab}.{col} {len(miss)}개 (예: {sorted(miss)[:3]})")
    add("외래 키 — 가리키는 값이 있음 (합친 데이터)", not bad, "; ".join(bad))

    # ---- 3. 문서 ↔ 데이터 ----
    al, wo, wr = T["alarm_event"].set_index("alarm_event_id"), T["maintenance_work_order"], T["work_record"]
    proc = {e["equipment_id"]: e["process_code"] for e in masters["equipment"]}
    prev = set(al.prev_alarm_event_id[al.prev_alarm_event_id != ""]) if "prev_alarm_event_id" in al.columns else set()
    stop30 = al[(al.severity_at_event == "STOP") & (al.equipment_id.map(proc) == "OP-30") & ~al.index.isin(prev)]
    wo_alarm = wo[wo.trigger_kind == "STOP_ALARM"]
    add("OP-30 정지 알람마다 작업지시서 1건 (충돌 연쇄는 마지막 992에만, 아직 안 끝난 알람 제외)",
        set(wo_alarm.alarm_event_id) == set(stop30[stop30.cleared_at != ""].index) and not wo_alarm.alarm_event_id.duplicated().any(),
        f"정지 알람 {len(stop30)}건 (끝난 것 {int((stop30.cleared_at != '').sum())}), 작업지시서 {len(wo_alarm)}건")
    j = wr[wr.record_type == "FULL"].merge(wo, on="wo_no", suffixes=("", "_wo"))
    add("작업기록서(FULL) = 작업지시서 1건씩, 같은 알람·설비·로트", len(j) == len(wo) and len(wr[wr.record_type == "FULL"]) == len(wo)
        and (j.alarm_event_id.where(j.alarm_event_id != "", None).fillna("") == j.alarm_event_id_wo.where(j.alarm_event_id_wo != "", None).fillna("")).all()
        and (j.equipment_id == j.equipment_id_wo).all() and (j.lot_no == j.lot_no_wo).all(), f"작업지시서 {len(wo)}, 작업기록서(FULL) {len(wr[wr.record_type == 'FULL'])}")
    a = wo_alarm.join(al, on="alarm_event_id", rsuffix="_al")
    add("작업지시서의 설비·로트 = 그 알람의 설비·로트", (a.equipment_id == a.equipment_id_al).all() and (a.lot_no == a.lot_no_al).all())
    add("작업지시서 시각: 알람 직후 만들고(≤5분) → 반장 승인 → 완료 = 작업기록 확정",
        bool(((ts(a.created_at) - ts(a.occurred_at)) <= pd.Timedelta(minutes=5)).all()
             and (ts(a.approved_at) >= ts(a.created_at)).all() and (ts(a.completed_at) >= ts(a.approved_at)).all()))
    jf = wr[(wr.record_type == "FULL") & (wr.alarm_event_id != "")].join(al, on="alarm_event_id", rsuffix="_al")
    ok_t = bool((ts(jf.start_at) == ts(jf.occurred_at)).all() and (ts(jf.end_at) == ts(jf.cleared_at)).all()
                and (ts(jf.confirmed_at) >= ts(jf.end_at)).all() and ((ts(jf.end_at) - ts(jf.start_at)).dt.total_seconds() / 60 == jf.repair_min.astype(float)).all())
    add("작업기록서 시각: 시작 = 알람, 끝 = 알람 풀림, 확정 ≥ 끝, 수리 시간 = 끝 − 시작", ok_t)
    # R-35 (DB 점검과 같은 규칙): 문서마다 v0 ~ current_version 이 빠짐없이 document_revision 에 있음
    rv = T["document_revision"]
    cnt = rv.assign(v=rv.version_no.astype(int)).groupby(["doc_type", "doc_key"]).v.apply(set)
    miss = []
    for dt, tab, key in (("WORK_ORDER", "maintenance_work_order", "wo_no"), ("WORK_RECORD", "work_record", "record_no"),
                         ("SHIFT_REPORT", "shift_report", "shift_id"), ("DAILY_REPORT", "daily_report", "work_date"),
                         ("PM_RECORD", "pm_record", "pm_record_id"), ("SHIPMENT", "shipment", "shipment_no")):
        for row in T[tab].itertuples():
            cv = int(getattr(row, "current_version"))
            if not set(range(cv + 1)) <= cnt.get((dt, str(getattr(row, key))), set()):
                miss.append(f"{dt} {getattr(row, key)}")
    add("문서 버전: 문서마다 v0 ~ 현재 버전이 document_revision 에 빠짐없이 있음 (DB 점검 R-35)", not miss, miss[:5])
    chk = T["work_record_check"]
    steps = T["work_order_step"].groupby("wo_no").size()
    bad_chk = []
    for rec in wr[wr.record_type == "FULL"].itertuples():
        c = chk[chk.record_no == rec.record_no]
        n_step = int(steps.get(rec.wo_no, 0))
        if (c.check_kind == "STEP").sum() != n_step or (c.check_kind == "LOTO").sum() != 9 or list(c.check_seq.astype(int)) != list(range(1, len(c) + 1)):
            bad_chk.append(rec.record_no)
    add("작업기록 체크: 잠금·표지 9단계 + 작업 단계 수, 순번 연속", not bad_chk, bad_chk[:5])
    st = T["work_order_step"].merge(chk[chk.check_kind == "STEP"], on=["wo_no", "step_no"], how="right")
    add("체크가 가리키는 작업 단계가 작업지시서에 있음", not st.step_text.isna().any())
    inv, wrp = T["inventory_txn"], T["work_record_part"]
    use = inv[inv.source_kind == "WORK_RECORD"].groupby(["work_record_no", "work_record_item_no"]).qty_change.apply(lambda x: -x.astype(float).sum())
    need = wrp.assign(qty=wrp.qty.astype(float)).set_index(["record_no", "item_no"]).qty
    add("작업기록서 사용 부품 = 재고 거래(사용)와 수량 일치", use.sort_index().equals(need.sort_index()), f"부품 {len(need)}건, 재고 거래 {len(use)}건")
    sl = T["equipment_state_log"]
    down = sl[(sl.state_code == "DOWN") & (sl.alarm_event_id != "") & (sl.equipment_id.map(proc) == "OP-30")]
    dj = down.merge(wo_alarm[["alarm_event_id", "wo_no"]], on="alarm_event_id", how="left")
    add("정지(DOWN)가 있는 OP-30 알람 = 작업지시서가 있음", not dj.wo_no.isna().any(), f"OP-30 DOWN {len(down)}구간")
    lh, lots = T["lot_hold"], T["production_lot"].set_index("lot_no")
    ai = lh[lh.trigger_type == "AI_SUSPECT"]
    ai_al = ai.join(al[["alarm_code"]], on="related_alarm_event_id")
    crash = ai_al[ai_al.alarm_code == "992"]
    add("비서 의심 로트 보류: 충돌(992)이 이유면 그 알람의 작업지시서가 있고, 그 밖(공구 한도 362)은 알람이 있음",
        crash.related_alarm_event_id.isin(wo_alarm.alarm_event_id).all() and not ai_al.alarm_code.isna().any(),
        f"충돌 {len(crash)}건, 그 밖 {len(ai_al) - len(crash)}건")
    add("보류 로트의 상태가 보류 흐름과 맞음 (진행 중 보류 = ON_HOLD·HOLD_REVIEW 등)",
        all(lots.loc[x.lot_no].status in ("ON_HOLD", "HOLD_REVIEW", "RELEASED", "SCRAPPED") for x in lh.itertuples() if x.lot_no in lots.index),
        lh.result.value_counts().to_dict())

    # ---- 4. 실시간이 과거 뒤에 이어짐 ----
    man = __import__("json").load(open(rdir / "manifest.json", encoding="utf-8"))
    start = ts(man["start_at"])
    after = {k: int(R[k][c].astype(int).min()) if k in R and len(R[k]) else None
             for k, c in (("alarm_event", "alarm_event_id"), ("equipment_state_log", "state_log_id"), ("operation_report", "op_report_id"),
                          ("inventory_txn", "txn_id"), ("tool_change", "tool_change_id"), ("inspection_result", "result_id"),
                          ("cmm_import", "cmm_import_id"), ("bottleneck_log", "bottleneck_log_id"), ("pm_record", "pm_record_id"))}
    nxt = {k: len(P[k]) + 1 for k in after}
    add("실시간 번호가 과거 마지막 번호 바로 다음부터", all(v is None or v == nxt[k] for k, v in after.items()),
        {k: (v, nxt[k]) for k, v in after.items() if v is not None and v != nxt[k]})
    open_past = P["equipment_state_log"][P["equipment_state_log"].end_at == ""]
    if len(open_past):
        add("과거 마지막 설비 상태 구간(end_at 빈칸)은 실시간 시작 시각으로 닫혀야 한다 — 적재할 때 처리", False,
            f"열린 구간 {len(open_past)}개 (설비 {sorted(open_past.equipment_id)}), 실시간 시작 {start:%m/%d %H:%M}", info=True)
    over = [r for r in P["equipment_state_log"].itertuples() if r.end_at != "" and ts(r.end_at) > start]
    add("과거 상태 구간이 실시간 시작 시각을 넘지 않음", not over, f"{len(over)}개")
    first_rt = R["equipment_state_log"].groupby("equipment_id").start_at.min()
    add("실시간 상태 기록이 설비마다 실시간 시작 시각부터", all(ts(v) == start for v in first_rt), dict(first_rt))
    add("실시간 기록이 가리키는 교대·근무일이 함께 들어 있음 (shift·work_day)", all(k in R and len(R[k]) for k in ("shift", "work_day")),
        {k: len(R.get(k, [])) for k in ("work_day", "shift")})
    lo, hi = min(ts(R["shift"].start_at)), max(ts(R["shift"].end_at))
    rep_shift = set(R["operation_report"].shift_id)
    add("실시간 공정 실적의 교대가 그 교대 행에 있음", rep_shift <= set(T["shift"].shift_id), sorted(rep_shift))
    add("실시간 구간의 알림·교대 보고서·일일 보고서는 생성기가 만들지 않음 (백엔드가 이 기록을 보고 만든다)", False,
        "notification·shift_report·daily_report 는 과거 기록만 들어 있다", info=True)

    for r, n, d in lines:
        print(f"[{r}] {n}" + (f"  {d}" if d not in ("", "{}", "[]") else ""))
    fail = sum(1 for r, _, _ in lines if r == "FAIL")
    print(f"통과 {sum(1 for r, _, _ in lines if r == 'PASS')} / 실패 {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
