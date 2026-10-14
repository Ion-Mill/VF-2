"""과거 기록 모드 시간 흐름 (9/1 ~ 10/1 08:00). generate.py와 실시간 모드(realtime)가 같이 쓴다."""
from __future__ import annotations

from .calendar import build_calendar
from .common import Rng
from .flow import Sim
from .plan import plan_alarms, plan_maint, plan_material


def run_once(cfg, masters, force_t05_m=None, finish=True):
    rng = Rng(cfg["run"]["seed"])
    cal = build_calendar(cfg)
    mats = plan_material(cfg, cal, rng)
    alarms = plan_alarms(cfg, cal, masters, rng)
    maint = plan_maint(cfg, cal, masters, rng)
    sim = Sim(cfg, cal, masters, rng, mats, alarms, maint, force_t05_m=force_t05_m).run(finish=finish)
    return sim, rng


def _t05_parts(sim) -> int:
    t = sim.mach["VF2-01"].tools["T05"]
    return round(t.cum / t.per)


def search_t05(cfg, masters):
    """9/30 끝 VF2-01 T05가 목표 90%(10/1 브리핑 교체 권고 대상)가 되게 마지막 교체 시각을 찾는다 (같은 seed로 여러 번 돎).
    교체 한 번이 그 뒤 흐름(셋업 시간·부품 순서)을 바꿔 결과가 91·93처럼 건너뛰므로, 정확히 목표가 안 나오면
    허용 범위(config tools.end_state, 기본 90~94%) 안의 첫 값을 쓴다. 찾는 순서가 정해져 있어 누가 돌려도 같다.
    돌려주는 값: (sim, rng, 교체 시각 분 또는 [분, 셋업 분] 또는 None)."""
    es = cfg["tools"]["end_state"]
    target = es["VF2-01-T05_pct_at_0930_end"]
    lo_pct, hi_pct = es.get("VF2-01-T05_pct_range", [target, target])
    sim, rng = run_once(cfg, masters)
    t = sim.mach["VF2-01"].tools["T05"]
    need = round(t.limit * target / 100 / t.per)          # 90% = 360구멍 = 부품 90개
    lo_n, hi_n = round(t.limit * lo_pct / 100 / t.per), round(t.limit * hi_pct / 100 / t.per)
    if _t05_parts(sim) == need:
        return sim, rng, None
    best = None                                            # 범위 안에서 목표에 가장 가까운 것 (같으면 먼저 찾은 것)

    def check(s2, r2, f):
        nonlocal best
        got = _t05_parts(s2)
        if lo_n <= got <= hi_n and (best is None or abs(got - need) < abs(best[3] - need)):
            best = (s2, r2, f, got)
        return got == need

    # 교체 시각 후보: 교체를 넣은 실행의 부품 시각으로 "끝에서 목표 개수 전" 위치를 다시 계산하며 모은다
    force, cands = sim.vf_done_times["VF2-01"][-need], []
    for _ in range(8):
        if force in cands:
            break
        cands.append(force)
        s2, r2 = run_once(cfg, masters, force_t05_m=force)
        if check(s2, r2, force):
            return s2, r2, force
        force = s2.vf_done_times["VF2-01"][-need]
    # 후보 시각 앞뒤 2분 × 셋업 3~8분(설계 범위 안)에서 정확한 값을 더 찾음 (앞 후보 2개만 — 시간 제한)
    lo, hi = cfg["states"]["setup_tool_change_min"]
    for f0 in cands[:2]:
        for f in (f0, f0 + 1, f0 - 1, f0 + 2, f0 - 2):
            for su in range(lo, hi + 1):
                s2, r2 = run_once(cfg, masters, force_t05_m=(f, su))
                if check(s2, r2, [f, su]):
                    return s2, r2, [f, su]
    if best:
        return best[:3]
    raise RuntimeError("9/30 끝 T05가 허용 범위에 드는 교체 시각을 못 찾음 — seed나 설정을 확인")
