"""실시간 모드 (10/1 08:00 ~). 설계서 4장, API-SIM-02·03.

실행 (생성기 폴더에서):
  .venv\\Scripts\\python realtime.py                 리허설 대본(scenarios/리허설_버튼없음.json)을 기다리지 않고 돌림
                                                    → out_realtime/ 에 10/1 기록 + 점검
  .venv\\Scripts\\python realtime.py --script 파일   다른 대본
  .venv\\Scripts\\python realtime.py --live          실제 시간으로 돌리며 키보드로 조작 (화면 연결 전 확인용)
                                                    1·2·3·4 = 180·60·10·1배, 스페이스 = 일시정지/다시 시작,
                                                    s = 17:00으로 넘기기, r = 처음으로, q = 끝 (끝날 때 out_realtime/에 저장)

먼저 generate.py를 한 번 돌려 out/ 이 있어야 한다 (번호를 과거 기록 뒤에 이어 붙임).
"""
from __future__ import annotations

import argparse
import sys
import time

from gen.common import ROOT, check_python, load_config, load_masters, set_profile_from_args
from gen.realtime import Realtime, load_script


def summary(rt: Realtime, man: dict):
    c = rt.clock()
    print(f"시연 시각 {c['sim_at']}  배속 ×{c['speed']}  {'일시정지' if c['paused'] else '진행'}")
    print(f"조작 {man['ops']}개, 사건 {man['events']}개 → {rt.rt['out_dir']}/")
    print("  " + ", ".join(f"{k} {v}" for k, v in man["rows"].items()))


STATE_KO = {"RUN": "가공", "IDLE": "대기", "BLOCKED": "막힘", "SETUP": "셋업", "DOWN": "고장", "MAINT": "정비"}
HELP = ("시계: 1=180배  2=60배  3=10배  4=1배  스페이스=일시정지/다시  s=17:00 넘기기  r=처음으로  q=끝(저장)\n"
        "사건 버튼: 5=S1 충돌  6=S3 공구(T05)  7=S4 공기 압력  8=S6 VF2-02 정비\n"
        "화면 조작: h=의심 로트 보류  t=T05 공구 교체 기록  w=작업기록서 확정(VF2-01 복귀)  u=보류 로트 해제\n"
        "    (한글 입력 상태여도 됨. 10배·1배는 공장 시계가 느리게 가서 멈춘 것처럼 보일 수 있음 — 초를 보면 움직임)")


def run_live(rt: Realtime):
    """실제 시간으로 돌리며 키보드로 조작한다. 아래 한 줄 = 지금 상태, 위로 쌓이는 줄 = 사건 기록."""
    try:
        import msvcrt
    except ImportError:
        print("--live는 Windows 터미널(PowerShell·명령 프롬프트)에서만 키 입력을 받는다")
        return
    speed_keys = {"1": 180, "2": 60, "3": 10, "4": 1}
    alias = {"ㄴ": "s", "ㄱ": "r", "ㅂ": "q", "ㅗ": "h", "ㅅ": "t", "ㅈ": "w", "ㅕ": "u",
             "S": "s", "R": "r", "Q": "q", "H": "h", "T": "t", "W": "w", "U": "u"}
    buttons = {"5": "S1", "6": "S3", "7": "S4", "8": "S6"}

    def act(label, fn, *a):
        try:
            fn(*a)
            log(f"[조작] {label}")
        except ValueError as e:
            log(f"[조작 안 됨] {label} — {e}")
    rname = {d["reason_code"]: d["reason_name"] for d in rt.M["downtime_reason"]}
    print(HELP)
    print()

    def log(text: str):
        print("\r\x1b[2K" + text, flush=True)

    last = time.monotonic()
    try:
        while True:
            while msvcrt.kbhit():
                k = msvcrt.getwch()
                k = alias.get(k, k)
                if k in speed_keys:
                    rt.set_speed(speed_keys[k])
                    log(f"[조작] 배속 ×{speed_keys[k]}")
                elif k == " ":
                    if rt.paused:
                        rt.resume()
                        log("[조작] 다시 시작")
                    else:
                        rt.pause()
                        log("[조작] 일시정지 — 스페이스를 다시 누르면 이어서 감")
                elif k == "s":
                    before = rt.clock()["sim_at"][11:16]
                    rt.skip()
                    log(f"[조작] {before} → 17:00 넘기기 (17:00이 지났으면 그대로)")
                elif k == "r":
                    log("[조작] 처음으로 (10/1 08:00) — 1초쯤 걸림")
                    rt.reset()
                elif k in buttons:
                    act(f"사건 버튼 {buttons[k]}", rt.inject, buttons[k])
                elif k == "h":
                    lot = rt.suspect_lot() or next((l.lot_no for l in rt.sim.lots if l.review_m is not None
                                                    and not l.on_hold and l.judged_m is None), None)
                    if lot:
                        act(f"로트 보류 {lot}", rt.hold_lot, lot)
                    else:
                        log("[조작 안 됨] 보류할 의심 로트 없음 (S1 충돌 뒤에 누름)")
                elif k == "t":
                    act("T05 공구 교체 기록", rt.record_tool_change, "VF2-01-T05")
                elif k == "w":
                    act("작업기록서 확정 → VF2-01 복귀", rt.confirm_work_record, "VF2-01")
                elif k == "u":
                    held = [l.lot_no for l in rt.sim.lots if l.on_hold]
                    if held:
                        act(f"보류 해제 {held[0]}", rt.release_lot, held[0])
                    else:
                        log("[조작 안 됨] 보류 중인 로트 없음")
                elif k == "q":
                    log("[조작] 끝 — out_realtime/ 에 저장")
                    return
            now = time.monotonic()
            evs = rt.tick(now - last)
            last = now
            for e in evs:
                t = e.get("at", "")[11:16]
                if e["type"] == "state_changed":
                    log(f"{t} {e['equipment_id']:<6} → {STATE_KO.get(e['state'], e['state'])}"
                        + (f" — {rname.get(e['reason'], '')} ({e['reason']})" if e["reason"] else ""))
                elif e["type"] == "bottleneck_changed":
                    log(f"{t} ★ 병목 바뀜: {e['prev_process_code']} → {e['process_code']} (원인 {e['cause_code']})")
                elif e["type"] == "alarm":
                    log(f"{t} ! 알람 {e['equipment_id']} {e['alarm_code']} ({e['severity']})"
                        + (f" — 사건 {e['scenario_code']}" if e.get("scenario_code") else ""))
                elif e["type"] in ("event_started", "event_ended"):
                    log(f"{t} ◆ 사건 {e['scenario_code']} {'시작' if e['type'] == 'event_started' else '끝 — ' + e['how']}")
                elif e["type"] == "tool_life":
                    log(f"{t} ▲ 공구 {e['tool_id']} 사용률 {e['usage_pct']}% — 교체 알림")
                elif e["type"] == "cmm_file":
                    log(f"{e['at'][11:16]} ▣ 측정 결과 파일 {e['file_name']}")
                elif e["type"] == "shift_end":
                    log(f"{t} ── 교대 끝 {e['shift_id']} ──")
                elif e["type"] == "sim_clock" and e.get("reason") == "end":
                    log("10/2 08:00 — 10/1 운영 끝 (q로 저장)")
            c = rt.clock()
            sec = int(rt.ms // 1000) % 60                         # 다음 분까지 흐른 공장 초
            w = rt.prev_wip or {}
            print(f"\r\x1b[2K[{c['sim_at'][11:16]}:{sec:02d}] ×{c['speed']:<3} {'일시정지' if c['paused'] else '진행'}  "
                  f"완료 {rt.done_today}  재공 {w.get('WIP-10-20', 0)}/{w.get('WIP-20-30', 0)}/"
                  f"{w.get('WIP-30-40', 0)}/{w.get('WIP-40-50', 0)}  병목 {rt.judge.cur[0]}({rt.judge.cur[1]})"
                  f"  사건 {c['running_event'] or '-'}",
                  end="", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        log("[Ctrl+C] 끝 — out_realtime/ 에 저장")
    except Exception:
        import traceback
        print()
        traceback.print_exc()
        print("오류로 멈춤 — 위 내용을 데이터·ML 담당에게 보내 주세요. 지금까지 기록은 저장합니다")


def main():
    check_python()
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--profile", default=None)
    a = ap.parse_args()
    set_profile_from_args(["--profile", a.profile] if a.profile else [])
    cfg = load_config()
    masters = load_masters(cfg)
    if not (ROOT / cfg["run"]["out_dir"] / "manifest.json").exists():
        print("먼저 generate.py로 과거 기록(out/)을 만든다")
        return 1
    rt = Realtime(cfg, masters)
    if a.live:
        run_live(rt)
        print()
    else:
        rt.play(load_script(a.script or cfg["realtime"]["rehearsal_script"]))
    man = rt.export()
    summary(rt, man)
    import validate
    res = validate.run_realtime(cfg, ROOT / cfg["realtime"]["out_dir"], ROOT / cfg["run"]["out_dir"], masters)
    print(f"점검: 통과 {res['passed']} / 실패 {res['failed']}")
    for line in res["lines"]:
        if line["result"] != "PASS":
            print(f"  [{line['result']}] {line['name']}: {line['detail']}")
    return 0 if res["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
