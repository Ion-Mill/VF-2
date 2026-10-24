"""작업지시서·작업기록서 (설계서 5.11, ERD 5.D.1~5.D.6).

- OP-30 정지 등급 알람 1건 = 작업지시서 1건 = 작업기록서 1건 (충돌 연쇄는 마지막 992에만)
- 반복 알람 사례 ② 2단계 = 원인 점검 작업지시서 1건 + 작업기록서 1건 (MAINT 구간)
- 주의 등급 알람(OP-30)과 다른 공정 정지·주의 알람 = 간이 작업기록 1건씩
과거 기록은 모두 완료·확정이다. AI비서 초안 버전(수정 이력)은 5단계에서 붙인다.
"""
from __future__ import annotations

from datetime import timedelta

from .flow import MNT_BY_SHIFT, OPR_BY_PROC

WO_COLS = ["wo_no", "trigger_kind", "alarm_event_id", "pm_record_id", "trigger_notification_id", "equipment_id",
           "lot_no", "created_at", "title", "symptom", "status", "assignee_user_id", "approved_by", "approved_at",
           "cancelled_by", "cancelled_at", "cancel_reason", "safety_block_doc_rev", "has_high_voltage_notice",
           "completed_at", "current_version"]
STEP_COLS = ["wo_no", "step_no", "step_text", "source_section"]
WOP_COLS = ["wo_no", "item_no", "suggested_qty"]
WR_COLS = ["record_no", "record_type", "wo_no", "alarm_event_id", "cause_check_notification_id", "equipment_id",
           "lot_no", "cause", "action", "worker_memo", "start_at", "end_at", "repair_min", "safety_block_required",
           "status", "confirmed_by", "confirmed_at", "checked_by", "checked_at", "current_version"]
CHK_COLS = ["record_no", "check_seq", "check_kind", "wo_no", "step_no", "loto_step_code", "is_checked", "checked_by",
            "checked_at"]
WRP_COLS = ["record_no", "item_no", "qty", "proposed_by_kind"]
LOTO = ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "7.1", "7.2", "7.3"]

# 작업자 메모: "일부러 대충 쓴 말투" (설계서 5.11, AI비서 초안 정리 시험용) [가상]
MEMO = {
    "crash": ["X축 쪽에서 쿵 소리 남. 엔드밀 부러져있음 고정구 살짝 밀림", "충돌같음. 공구 깨짐 테이블쪽 확인함 볼스크류 손으로 돌려봄 걸림없음"],
    "servo": ["앰프 쪽 냄새남, 케이블 봤는데 절삭유 묻어있음", "알람 리셋하고 다시 돌리니 또 뜸. 커넥터 다시 꽂음", "축 손으로 돌려봄 뻑뻑한데 없음. 앰프 온도 높았음"],
    "spindle": ["주축 소리 평소보다 큼, 식히고 다시 돌림", "공구 흔들림 있었음 홀더 교체함"],
    "lube": ["윤활 압력 안올라옴. 탱크 확인 호스 연결부 새는거 같음", "윤활유 탱크 바닥 보임"],
    "breaker": ["차단기 떨어져있었음. 절삭유 펌프 쪽 확인", "펌프 모터 저항 재봄 정상범위"],
}
GROUP = {"992": "crash", "994": "servo", "991": "servo", "993": "servo", "103": "servo", "254": "spindle",
         "966": "spindle", "2073": "lube", "552": "breaker"}


def build_mnt(cfg, sim, masters, doc03, rng, pm_recs, live_from_alarm: int | None = None, wo_offset: int = 0,
              simple_offset: int = 0, now_dt=None) -> dict[str, list[dict]]:
    """live_from_alarm 가 있으면 실시간 구간용 (2026-10-24): 그 번호보다 큰 알람 중 **끝난 것**(복귀·확정까지 간 것)만 문서로 만들고,
    번호는 과거 기록 뒤(wo_offset·simple_offset)부터 이어 붙인다. 작업기록 확정 시각 = 알람이 풀린 시각(사람이 [확정]한 때),
    반장 확인이 지금(now_dt)보다 뒤면 아직 확정 상태(CONFIRMED)로 둔다."""
    live = live_from_alarm is not None
    r = rng.stream("mnt-live" if live else "mnt")
    cal = sim.cal
    am = {x["alarm_code"]: x for x in masters["alarm_master"]}
    gm = {}
    for x in masters["alarm_guide_map"]:
        gm.setdefault(x["alarm_code"], []).append(x["section"].lstrip("§"))
    proc_of = {e["equipment_id"]: e["process_code"] for e in masters["equipment"]}
    evs = {e["id"]: e for e in sim.alarm_events}
    prev_ids = {e.get("prev") for e in sim.alarm_events if e.get("prev")}
    wo, steps, wop, wr, chk, wrp = [], [], [], [], [], []
    full_items = []          # (created_m, kind, data)

    for e in sim.alarm_events:
        eq, code, sev = e["equipment_id"], e["alarm_code"], e["severity"]
        if e["id"] in prev_ids:
            continue                                  # 충돌 연쇄의 앞 알람 (108·994)
        if live and (e["id"] <= live_from_alarm or e["cleared_m"] is None):
            continue                                  # 실시간: 과거 알람과 아직 안 끝난 알람은 문서가 아직 없다
        if proc_of[eq] == "OP-30" and sev == "STOP":
            full_items.append((e["occurred_m"], "STOP", e))
    c2 = [e for e in sim.alarm_events if e.get("case") == "case2_stage2"]
    cc = [w for w in sim.maint_done if w["window"].kind == "CAUSE_CHECK"]
    if not live and len(c2) >= 4 and cc:
        full_items.append((c2[3]["occurred_m"], "REPEAT", (c2[3], cc[0])))
    full_items.sort(key=lambda x: x[0])

    def shift_people(m):
        sh = cal.shift_or_near(m)
        return sh, MNT_BY_SHIFT[sh.shift_type][int(r.integers(0, len(MNT_BY_SHIFT[sh.shift_type])))]

    mm = f"{cal.days[0]:%m}"                          # 번호의 월 두 자리 (MW-1001: 10월 1번째)
    for n, (m0, kind, data) in enumerate(full_items, 1 + wo_offset):
        wo_no, rec_no = f"MW-{mm}{n:02d}", f"MR-{mm}{n:02d}"
        if kind == "STOP":
            e = data
            sec = gm[e["alarm_code"]][0]
            d3 = doc03[sec]
            start_m, end_m = e["occurred_m"], e["cleared_m"]
            sh, mnt = shift_people(start_m)
            title = f"{e['equipment_id']} 알람 {e['alarm_code']} {am[e['alarm_code']]['name_ko']} — 점검·수리"
            symptom = d3["symptom"] or am[e["alarm_code"]]["easy_desc"]
            stp = d3["steps"]
            cause = d3["causes"][0] if e["alarm_code"] == "992" else str(r.choice(d3["causes"]))
            action = d3["action"]
            memo = str(r.choice(MEMO[GROUP[e["alarm_code"]]]))
            trig, alarm_id, lot = "STOP_ALARM", e["id"], e["lot_no"]
            parts = [("TL-EM10", 1)] if e["alarm_code"] == "992" else []
        else:
            e4, w = data
            d3 = doc03["2.6"]
            start_m, end_m = w["start_m"], w["end_m"]
            sh, mnt = shift_people(e4["occurred_m"])
            title = f"{e4['equipment_id']} 알람 108 반복 — 원인 점검 (반복 알람 2단계)"
            symptom = "같은 설비·같은 알람(108 축 서보 과부하)이 7일 안에 3번 난 뒤 조치 계획을 실행했는데 다시 났다 (지난 조치 효과 없음)"
            stp = [s for s in d3["steps"] if not s[0].startswith("★")]
            cause = "볼스크류 정렬 불량"
            action = "축을 전체 행정으로 조그하며 서보 부하가 일정한지 확인 → 일정하지 않아 정렬 절차대로 볼스크류 정렬"
            memo = "Y축 끝으로 갈때 부하 튐. 볼스크류 정렬 다시 봄 커플링 쪽 틀어져있었음"
            trig, alarm_id, lot = "REPEAT_STAGE2", None, e4["lot_no"]
            parts = []
        created = cal.to_dt(m0 + 1)
        approved = created + timedelta(minutes=int(r.integers(*cfg["sim"]["wo_approve_after_min"])))
        end_dt = cal.to_dt(end_m)
        confirmed = end_dt + timedelta(minutes=int(r.integers(5, 21)))
        checked = confirmed + timedelta(minutes=int(r.integers(30, 121)))
        if live:
            confirmed = end_dt                       # 사람이 [확정]을 누른 때 = 설비가 복귀한 때 (반장 확인 시각은 위에서 뽑은 값 그대로)
        wo.append({"wo_no": wo_no, "trigger_kind": trig, "alarm_event_id": alarm_id, "pm_record_id": None,
                   "trigger_notification_id": None, "equipment_id": data[0]["equipment_id"] if kind == "REPEAT"
                   else data["equipment_id"], "lot_no": lot, "created_at": created, "title": title,
                   "symptom": symptom, "status": "DONE", "assignee_user_id": mnt, "approved_by": sh.supervisor,
                   "approved_at": approved, "safety_block_doc_rev": "DOC-05 Rev.2", "has_high_voltage_notice": True,
                   "completed_at": confirmed, "current_version": 0})
        sec_txt = f"DOC-03 §{gm[data['alarm_code']][0] if kind == 'STOP' else '2.6'}"
        for i, (_no, _who, text) in enumerate(stp, 1):
            steps.append({"wo_no": wo_no, "step_no": i, "step_text": text, "source_section": sec_txt})
        for item, q in parts:
            wop.append({"wo_no": wo_no, "item_no": item, "suggested_qty": q})
            wrp.append({"record_no": rec_no, "item_no": item, "qty": q, "proposed_by_kind": "HUMAN"})
        start_dt = cal.to_dt(start_m)
        wr.append({"record_no": rec_no, "record_type": "FULL", "wo_no": wo_no, "alarm_event_id": alarm_id,
                   "cause_check_notification_id": None, "equipment_id": wo[-1]["equipment_id"], "lot_no": lot,
                   "cause": cause, "action": action, "worker_memo": memo, "start_at": start_dt, "end_at": end_dt,
                   "repair_min": end_m - start_m, "safety_block_required": True, "status": "CHECKED",
                   "confirmed_by": mnt, "confirmed_at": confirmed, "checked_by": sh.supervisor,
                   "checked_at": checked, "current_version": 0})
        if live and now_dt is not None and checked > now_dt:      # 반장 확인은 아직 안 한 때 — 작업기록서는 확정까지만
            wr[-1].update({"status": "CONFIRMED", "checked_by": None, "checked_at": None})
        # 체크: 잠금·표지 작업 전 6단계 → 작업 순서 → 작업 후 3단계
        times = sorted(int(x) for x in r.integers(start_m, max(start_m + 1, end_m), len(stp) + 9))
        seq = 0
        for j, code in enumerate(LOTO[:6]):
            seq += 1
            chk.append({"record_no": rec_no, "check_seq": seq, "check_kind": "LOTO", "wo_no": None, "step_no": None,
                        "loto_step_code": code, "is_checked": True, "checked_by": mnt,
                        "checked_at": cal.to_dt(times[j])})
        for i in range(len(stp)):
            seq += 1
            chk.append({"record_no": rec_no, "check_seq": seq, "check_kind": "STEP", "wo_no": wo_no,
                        "step_no": i + 1, "loto_step_code": None, "is_checked": True, "checked_by": mnt,
                        "checked_at": cal.to_dt(times[6 + i])})
        for j, code in enumerate(LOTO[6:]):
            seq += 1
            chk.append({"record_no": rec_no, "check_seq": seq, "check_kind": "LOTO", "wo_no": None, "step_no": None,
                        "loto_step_code": code, "is_checked": True, "checked_by": mnt,
                        "checked_at": cal.to_dt(times[6 + len(stp) + j])})

    # 간이 작업기록
    k = simple_offset
    for e in sim.alarm_events:
        eq, code, sev = e["equipment_id"], e["alarm_code"], e["severity"]
        proc = proc_of[eq]
        if sev == "GUIDE" or e["id"] in prev_ids:
            continue
        if live and (e["id"] <= live_from_alarm or e["cleared_m"] is None):
            continue
        if proc == "OP-30" and sev == "STOP":
            continue
        k += 1
        rec_no = f"MR-S-{mm}{k:02d}"
        sec = gm[code][0]
        d3 = doc03.get(sec, {})
        if proc == "OP-30":
            star = [s for s in d3.get("steps", []) if s[0].startswith("★")]
            action = star[min(1, len(star) - 1)][2] if star else d3.get("action", "")
        else:
            action = d3.get("action", "")
        if code == "2075":
            action = "저장소 수위를 확인하고 알람을 지움. 보충은 예방 정비(2.3 윤활유 저장소 양 점검·보충) 때 하기로 함"
        sh = cal.shift_or_near(e["occurred_m"])
        stop_other = proc != "OP-30" and sev == "STOP"
        who = MNT_BY_SHIFT[sh.shift_type][0] if stop_other else OPR_BY_PROC[sh.shift_type][proc]
        end_m = e["cleared_m"] if e["cleared_m"] is not None else e["occurred_m"]
        conf = cal.to_dt(end_m) + timedelta(minutes=int(r.integers(5, 16)))
        wr.append({"record_no": rec_no, "record_type": "SIMPLE", "wo_no": None, "alarm_event_id": e["id"],
                   "cause_check_notification_id": None, "equipment_id": eq, "lot_no": e["lot_no"], "cause": None,
                   "action": action, "worker_memo": None, "start_at": cal.to_dt(e["occurred_m"]),
                   "end_at": cal.to_dt(end_m), "repair_min": end_m - e["occurred_m"],
                   "safety_block_required": stop_other, "status": "CONFIRMED", "confirmed_by": who,
                   "confirmed_at": conf, "checked_by": None, "checked_at": None, "current_version": 0})
        if stop_other:
            ts = sorted(int(x) for x in r.integers(e["occurred_m"], max(e["occurred_m"] + 1, end_m), 9))
            for j, lc in enumerate(LOTO):
                chk.append({"record_no": rec_no, "check_seq": j + 1, "check_kind": "LOTO", "wo_no": None,
                            "step_no": None, "loto_step_code": lc, "is_checked": True, "checked_by": who,
                            "checked_at": cal.to_dt(ts[j])})
    return {"maintenance_work_order": wo, "work_order_step": steps, "work_order_part": wop, "work_record": wr,
            "work_record_check": chk, "work_record_part": wrp}
