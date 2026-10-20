"""알람 점검 순서 시드 만들기 → db/seed/50_alarm_check_steps.sql (2026-10-20, 작업지시서 초안 자동 생성 — FR-MNT-03-01·05).

쓰는 법: python tools/gen_alarm_steps.py ../frontend/tools/data.json > db/seed/50_alarm_check_steps.sql
원본은 가상사내문서 DOC-03 (화면 도구 frontend/tools/build_data.py가 DOC-03 머리말 "점검 순서"에서 뽑은 data.json의 alarms).
  SYMPTOM = 증상 첫 문장, OPR = ★ 작업자 줄(steps), MNT = 보전 줄(maint). 문서 문장은 바꾸지 않는다.
DOC-03을 고치면 build_data.py → 이 도구 순서로 다시 만든다. 표준 라이브러리만.
"""
import json
import sys


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main():
    alarms = json.load(open(sys.argv[1], encoding="utf-8"))["alarms"]
    rows = []
    for code, a in alarms.items():
        seq = 0
        if a.get("symptom"):
            rows.append((code, seq, "SYMPTOM", a["symptom"]))
        for kind, key in (("OPR", "steps"), ("MNT", "maint")):
            for text in a.get(key) or []:
                seq += 1
                rows.append((code, seq, kind, text))
    print("-- 생성: tools/gen_alarm_steps.py (frontend/tools/data.json ← 가상사내문서 DOC-03). 손으로 고치지 말고 다시 만든다.")
    print("-- 알람 점검 순서 (작업지시서 초안 자동 생성, 2026-10-20). SYMPTOM = 증상 첫 문장, OPR = ★ 작업자 줄, MNT = 보전 줄")
    print("DELETE FROM alarm_check_step;")
    print("INSERT INTO alarm_check_step (alarm_code, seq, step_kind, step_text) VALUES")
    print(",\n".join(f"  ({q(c)}, {s}, {q(k)}, {q(t)})" for c, s, k, t in rows) + ";")


if __name__ == "__main__":
    main()
