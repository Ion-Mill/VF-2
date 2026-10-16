"""교대 시작 브리핑 API 시험 (AST-01 `GET /api/assistant/briefing`, 2026-10-11 멈춤 ④ P3). 시험 이름 앞머리 = 시험 ID.

- 대응표: tests/req_map.json. 숫자는 요구사항정의서_최종본 수용 기준과 테스트계획서_v1 4장에서 가져온다.
- 시연 시각은 2026-10-01 08:00(주간 시작)이다 — 지난 교대 = 9/30 야간(SR-260930-N 확정), 이번 교대 = 10/1 주간.
- 가상 데이터의 교대 보고서는 모두 확정이라, 잠정을 보려면 시연 상태에 초안을 겹쳐 둔다(SR.draft).
"""
import json
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import demo_state as DS
from backend.app import app
from backend.demo_state import get_state
from backend.repositories.csv_repo import get_repo
from backend.services import metrics as M
from backend.services import notifications as N
from backend.services import shift_reports as SR
from backend.services import shifts as SH
from backend.services.report_rank import RANKS
from backend.tests.test_llm import FakeLlm, llm  # noqa: F401  (fixture)

client = TestClient(app)
URL = "/api/assistant/briefing"
NIGHT_0930 = datetime(2026, 9, 30, 20, 0, tzinfo=SH.KST)   # 9/30 야간 시작 (반장 SUP-02, OP-30 작업자 OPR-05)


def H(role, user=""):
    return {"X-Role": role, "X-User": user}


def get(role, user="", **params):
    return client.get(URL, params=params, headers=H(role, user))


@pytest.fixture(autouse=True)
def fresh_state():
    get_state().reset()
    yield
    get_state().reset()


# ---------------------------------------------------------------- FR-AST-01-01 화면이지 문서가 아니다
def test_T_FR_AST_01_01_1_screen_not_document():
    """불러도 시연 상태(처리 기록·SSE 사건·보고서 겹침·폭주 상태)가 바뀌지 않고, 버전·확정 칸이 없다 (수정 이력 대상 아님).
    교대 시작 때 화면이 저절로 열리는 것은 화면 몫이라 아직 없다 → 대응표 "일부"."""
    s = get_state()
    before = (len(s.events), dict(s.processed), dict(s.reports), s.storm)
    for role, user in (("SUP", "SUP-01"), ("MNT", "MNT-01"), ("MGR", "MGR-01"), ("OPR", "OPR-02")):
        assert get(role, user).status_code == 200
    assert (len(s.events), dict(s.processed), dict(s.reports), s.storm) == before
    j = get("SUP", "SUP-01").json()
    assert not {"version", "status", "confirmed_by", "revisions"} & set(j)
    assert j["is_synthetic"] is True and j["message_source"] == "기본 문구"


# ---------------------------------------------------------------- FR-AST-01-02 입력 모으기
def test_T_FR_AST_01_02_1_collects_every_open_problem():
    """처리 안 된 문제가 하나도 빠지지 않고 한 줄에만 들어간다. 여섯 순위가 이름과 함께 모두 나온다.
    전체형(SUP·MNT·MGR)은 알림 받는 사람과 상관없이 같은 목록이다. 데이터·알림이 아직 없는 종류(잠금·표지, 생산 위험,
    품질, 승인 대기 …)는 not_built로 밝힌다 → 대응표 "일부"."""
    p = get("SUP", "SUP-01").json()["priorities"]
    open_ids = {n["id"] for n in N.all_notifications(get_state()) if not n["processed"]}
    listed = [i for it in p["items"] for i in it["notification_ids"]]
    assert sorted(listed) == sorted(open_ids) and len(listed) == len(set(listed))
    assert [(r["rank"], r["rank_name"]) for r in p["ranks"]] == RANKS
    for role, user in (("MNT", "MNT-01"), ("MGR", "MGR-01")):
        assert get(role, user).json()["priorities"]["items"] == p["items"]
    assert any("잠금·표지" in x for x in p["not_built"]) and any("품질" in x for x in p["not_built"])
    assert any("승인 대기" in x for x in p["not_built"]) and any("순위 2" in x for x in p["not_built"])


# ---------------------------------------------------------------- FR-AST-01-03 칸 구성
def test_T_FR_AST_01_03_1_four_sections_and_first_lines():
    """칸 넷: 먼저 챙길 일·지난 교대·이번 교대·출처. 지난 교대 3줄의 첫 줄 = 양품·손실, 이번 교대 3줄의 첫 줄 =
    "총 N개 (목표 90 + 이월 N)". 모은 입력 건수 줄은 [선택 필요: 팀]이라 두지 않는다."""
    j = get("SUP", "SUP-01").json()
    assert {"priorities", "last_shift", "this_shift", "sources"} <= set(j)
    last, this = j["last_shift"], j["this_shift"]
    assert len(last["lines"]) == 3 and len(this["lines"]) == 3
    assert last["shift_key"] == "SHIFT-260930-N" and last["report_id"] == "SR-260930-N"
    assert last["lines"][0] == "양품 82개 · 고장 손실 약 3개 (추정, 속도 손실은 데이터 없음)"   # SR-260930-N 양품 82, 손실 추정 3
    # 9/30 야간 총 목표 = 90 + 이월 8(주간 82) = 98 → −16, 하루 82 + 82 = 164 / 180 (야간 부족은 다음 날로 넘기지 않음)
    assert last["lines"][1] == ("필수 정지 1번 20분 (VF2-02 1번 20분) → 고장 손실 약 3개 (추정) · 총 목표 98개 대비 -16개"
                                " · 하루 164 / 180개 (16개 부족 — 다음 날로 넘기지 않음)")
    assert (last["actual_qty"], last["defect_qty"], last["failure_loss_qty"], last["speed_loss_qty"]) == (82, 0, 3, None)
    assert this["lines"][0] == "총 90개 (목표 90 + 이월 0)"                                     # 주간은 이월 0
    assert this["records"] == ["PO-2609-112", "PO-2609-113", "PO-2609-114"]
    assert this["actual_qty"] is None                                                            # 이번 교대 실적은 데이터 없음
    assert j["sources"] and {s["doc_no"] for s in j["sources"]} == {"DOC-07"}


# ---------------------------------------------------------------- FR-AST-01-04 먼저 챙길 일 (전체 N건)
def test_T_FR_AST_01_04_1_header_count_and_order():
    """화면 항목 수 = 프로그램이 모은 수(묶은 뒤) = 머리의 N. 순서 = 보고 순위 표. 순위 0·0-1·1은 접지 않는다.
    0-1(오래 방치)은 머리에서 "주의"에 센다. 같은 설비·같은 원인은 한 줄로 묶는다 (VF2-02 알람 2075 + 그 반복 알람 1단계)."""
    p = get("SUP", "SUP-01").json()["priorities"]
    assert p["total"] == len(p["items"]) == sum(p["counts"].values()) == 6
    assert p["header"] == "전체 6건 (안전 - · 긴급 - · 생산 - · 주의 6 · 참고 -)"
    order = [r for r, _ in RANKS]
    ranks = [it["rank"] for it in p["items"]]
    assert ranks == sorted(ranks, key=order.index)
    assert all(not it["folded"] for it in p["items"] if it["rank"] in ("0", "0-1", "1"))
    assert p["counts"]["주의"] == sum(1 for it in p["items"] if it["rank"] in ("0-1", "3"))
    line = next(it for it in p["items"] if "2075" in it["title"])
    assert line["count"] == 2 and line["notification_ids"] == ["N-ALM-00279", "N-RPT-VF2-02-2075-1"]


# ---------------------------------------------------------------- FR-AST-01-05 기록 링크
def test_T_FR_AST_01_05_1_items_have_record_links():
    """항목마다 화면 링크가 있고, 반복 알람이 묶인 줄은 지난 작업기록 번호(MR-…)를 함께 보인다.
    공구·재고·예방 정비 화면은 이번 범위 밖이라 링크가 꺼져 있고 까닭을 적는다 → 대응표 "일부"."""
    p = get("SUP", "SUP-01").json()["priorities"]
    for it in p["items"]:
        assert it["links"], it["title"]
        assert all(ln["enabled"] or ln.get("reason") for ln in it["links"]), it["links"]
    line = next(it for it in p["items"] if "2075" in it["title"])
    assert line["records"] == ["MR-S-0932", "MR-S-0937"]
    assert line["links"][0] == {"label": "지침카드", "screen": "SCR-09", "target": "ALM-00279", "enabled": True}


# ---------------------------------------------------------------- FR-AST-01-06 오래된 알림
def test_T_FR_AST_01_06_1_briefing_long_open_first_oldest_first():
    """브리핑에서도 24시간 넘게 처리 안 된 주의 알림(0-1)이 맨 앞(잠금·표지 줄은 데이터 없음)이고 처리 안 된 시간이 긴 순."""
    p = get("SUP", "SUP-01").json()["priorities"]
    longs = [it for it in p["items"] if it["rank"] == "0-1"]
    assert len(longs) == 3 and p["items"][:3] == longs
    assert all(it["over_24h"] for it in longs)
    assert [it["occurred_at"] for it in longs] == sorted(it["occurred_at"] for it in longs)


# ---------------------------------------------------------------- FR-AST-01-07 작업자 요약 5줄
def test_T_FR_AST_01_07_1_operator_summary_five_lines():
    """OPR은 요약 5줄만: ① 잠금·표지 ② 지난 교대 양품 ③ 담당 공정 처리 안 된 긴급·주의 알람 ④ 담당 공정 공구 90% 이상
    ⑤ 총 목표 + 담당 설비 예방 정비 시각. 승인 대기·재고 부족·반복 알람 지난 조치·정지 원인·다른 공정 일은 나오지 않는다."""
    j = get("OPR", "OPR-02").json()                                     # OPR-02 = OP-30 주간
    assert j["view"] == "operator" and j["processes"] == ["OP-30"]
    assert not {"priorities", "last_shift"} & set(j)
    assert [l["no"] for l in j["lines"]] == [1, 2, 3, 4, 5]
    texts = [l["text"] for l in j["lines"]]
    assert texts[0].startswith("데이터 없음")
    assert texts[1] == "양품 82개"
    assert texts[2] == "전체 1건 — VF2-02 알람 2075 축 윤활유 저장소 비워짐 · 24시간 넘게 처리 안 됨"
    assert texts[3] == "VF2-01 T05 M6 탭 92%"
    assert texts[4] == "총 90개 · 10:30 VF2-02 월간 예방 정비 (축 윤활 포함), 14:00 VF2-01 주간 예방 정비"
    flat = json.dumps(j["lines"], ensure_ascii=False)
    for banned in ("재고", "반복", "MR-", "N-RPT-", "정지", "승인"):
        assert banned not in flat, banned
    other = get("OPR", "OPR-01").json()                                 # OPR-01 = OP-10·20 — OP-30 일은 나오지 않는다
    assert other["processes"] == ["OP-10", "OP-20"]
    assert [l["text"] for l in other["lines"]][2:] == ["없음", "없음", "총 90개 · 예방 정비 없음"]


@pytest.mark.parametrize("role, user, params, status, code", [
    ("MON", "", {}, 403, "FORBIDDEN"),                         # 모니터링 계정은 업무 화면을 열지 않는다
    ("OPR", "OPR-02", {"view": "full"}, 403, "FORBIDDEN"),     # 작업자는 전체형을 보지 않는다
    ("OPR", "OPR-02", {"process": "OP-10"}, 403, "FORBIDDEN"), # 남의 공정 요약
    ("SUP", "SUP-01", {"view": "operator"}, 403, "FORBIDDEN"),
    ("MNT", "MNT-01", {"view": "operator"}, 403, "FORBIDDEN"),
    ("", "", {}, 401, "UNAUTHORIZED"),
    ("SUP", "OPR-02", {}, 401, "UNAUTHORIZED"),                # 사용자와 역할이 다름
    ("OPR", "", {}, 422, "VALIDATION"),                        # 담당 공정을 모름 (X-User 없음)
    ("MGR", "MGR-01", {"view": "operator", "process": "OP-99"}, 422, "VALIDATION"),
    ("SUP", "SUP-01", {"view": "x"}, 422, "VALIDATION"),
])
def test_T_FR_AST_01_07_1_who_sees_which_view(role, user, params, status, code):
    r = get(role, user, **params)
    assert r.status_code == status and r.json()["code"] == code, r.json()


def test_mgr_sees_both_views():
    """MGR은 모든 기능을 조회한다(D-11): 전체형이 기본이고, 작업자 요약형은 공정을 골라 보거나 안 고르면 전체 공정 [제안]."""
    assert get("MGR", "MGR-01").json()["view"] == "full"
    j = get("MGR", "MGR-01", view="operator", process="OP-30").json()
    assert j["processes"] == ["OP-30"] and [l["text"] for l in j["lines"]] == [l["text"] for l in get("OPR", "OPR-02").json()["lines"]]
    assert get("MGR", "MGR-01", view="operator").json()["processes"] == ["전체 공정"]


# ---------------------------------------------------------------- FR-AST-COM-21 빈 순위
def test_T_FR_AST_COM_21_2_empty_ranks_show_dash():
    """건수 0인 순위도 이름과 "-" (긴급 0건 → "1 긴급 -"). 순위 0은 요구사항 문장("잠금·표지 중인 설비 없음") 대신 "데이터 없음" —
    잠금·표지 체크 기록이 없어 '없음'이라는 안전 확인을 지어내지 않는다 (불일치 기록). 현장 보기 띠 "외 N건"은 SCR-26이 없어
    시험하지 않는다 → 대응표 "일부"."""
    p = get("SUP", "SUP-01").json()["priorities"]
    by = {r["rank"]: r for r in p["ranks"]}
    assert (by["1"]["rank_name"], by["1"]["count"], by["1"]["count_text"]) == ("긴급", 0, "-")
    assert "긴급 -" in p["header"]
    assert all(r["count_text"] == (str(r["count"]) if r["count"] else "-") for r in p["ranks"])
    assert by["0"]["count_text"] == "-" and by["0"]["data_status"] == "데이터 없음"
    assert "잠금·표지 중인 설비 없음" not in json.dumps(p, ensure_ascii=False)


# ---------------------------------------------------------------- FR-AST-COM-08 잠정
def test_T_FR_AST_COM_08_1_provisional_until_confirmed():
    """교대 보고서가 미확정이면 다음 교대 브리핑의 지난 교대 칸이 "잠정", 그 교대 반장이 확정하면 다시 계산해 잠정이 빠진다.
    9/30 야간 반장 = SUP-02 (교대 달력)."""
    SR.draft(get_state(), "2026-09-30-N")
    last = get("SUP", "SUP-01").json()["last_shift"]
    assert last["is_provisional"] is True and last["status"] == "AI비서 초안"
    assert last["lines"][0].endswith("(잠정 — 교대 보고서 미확정)")
    assert get("OPR", "OPR-02").json()["lines"][1]["text"] == "양품 82개 (잠정)"
    r = client.post("/api/reports/shift/2026-09-30-N/confirm", json={"version": 0}, headers=H("SUP", "SUP-02"))
    assert r.status_code == 200
    last = get("SUP", "SUP-01").json()["last_shift"]
    assert last["is_provisional"] is False and last["status"] == "확정" and "잠정" not in json.dumps(last["lines"], ensure_ascii=False)
    assert get("OPR", "OPR-02").json()["lines"][1]["text"] == "양품 82개"


# ---------------------------------------------------------------- FR-PRD-01-15 이월
def test_T_FR_PRD_01_15_1_carry_over_rule():
    """야간 이월 = max(0, 교대 목표 90 − 그날 주간 실적). 주간은 늘 0. 그날 주간 기록이 없으면 0 [제안]."""
    assert M.carry_over_qty("N", 87, 90) == 3
    assert M.carry_over_qty("D", 87, 90) == 0
    assert M.carry_over_qty("N", 95, 90) == 0
    assert M.carry_over_qty("N", None, 90) == 0


def test_T_FR_PRD_01_15_1_day_87_gives_night_93(monkeypatch):
    """주간 실적 87 → 야간 총 목표 93 (이월 3), 하루 목표 180 그대로 (테스트계획서 4장). 9/30 주간 실적을 시험에서만 87로 바꾼다."""
    get_state().set_now(NIGHT_0930)
    repo = get_repo()
    real = repo.table
    rows = [dict(r, output="87") if r["shift_id"] == "SHIFT-260930-D" else r for r in real("shift_report")]
    monkeypatch.setattr(repo, "table", lambda name: rows if name == "shift_report" else real(name))
    j = get("SUP", "SUP-02").json()
    this = j["this_shift"]
    assert (this["target_qty"], this["carry_over_qty"], this["total_target_qty"], this["daily_target_qty"]) == (90, 3, 93, 180)
    assert this["lines"][0] == "총 93개 (목표 90 + 이월 3)"
    assert "이번 야간 이월 3개" in j["last_shift"]["lines"][1]
    assert get("OPR", "OPR-05").json()["lines"][4]["text"].startswith("총 93개")   # OPR-05 = OP-30 야간


def test_carry_over_on_real_data_and_report_target_mismatch():
    """가상 데이터 그대로: 9/30 주간 실적 82 → 야간 총 목표 98 (이월 8). 그런데 가상 데이터의 야간 교대 보고서 목표 칸은 90이다 —
    생성기가 이월을 넣지 않았다 (불일치 기록, 2026-10-11). 브리핑은 지난 교대·이번 교대 모두 규칙대로 98을 쓰고,
    보고서 값은 report_target_qty·target_note로 따로 보인다 (같은 화면에서 숫자가 어긋나지 않게)."""
    last = get("SUP", "SUP-01").json()["last_shift"]                       # 10/1 08:00 — 지난 교대 = 9/30 야간
    assert (last["carry_over_qty"], last["total_target_qty"], last["report_target_qty"]) == (8, 98, 90)
    assert "이월이 빠진 값" in last["target_note"]
    rep = next(r for r in get_repo().table("shift_report") if r["shift_id"] == "SHIFT-260930-N")
    assert rep["target"] == "90"
    get_state().set_now(NIGHT_0930)                                        # 9/30 20:00 — 이번 교대 = 9/30 야간
    j = get("SUP", "SUP-02").json()
    assert (j["this_shift"]["carry_over_qty"], j["this_shift"]["total_target_qty"]) == (8, 98)
    assert "target_note" not in j["last_shift"]                            # 9/30 주간은 이월 0이라 보고서 값(90)과 같다


def test_carry_over_provisional_when_day_report_unconfirmed():
    """그날 주간 교대 보고서가 미확정이면 이월도 잠정이라고 밝힌다 (UI설계서 SCR-02)."""
    s = get_state()
    s.set_now(NIGHT_0930)
    SR.draft(s, "2026-09-30-D")
    this = get("SUP", "SUP-02").json()["this_shift"]
    assert this["carry_over_is_provisional"] is True
    assert this["lines"][0] == "총 98개 (목표 90 + 이월 8) — 이월 잠정 (주간 교대 보고서 미확정)"


# ---------------------------------------------------------------- FR-AST-02-14 비서 꺼짐
def test_T_FR_AST_02_14_1_same_list_when_assistant_down(llm):  # noqa: F811
    """로컬 LLM이 멈춰도 알림은 같은 조건에서 뜨고(기본 문구) 브리핑은 프로그램 목록 전부·같은 순서다 — 브리핑과 알림 목록은
    비서를 부르지 않는다. 가짜 서버는 모든 요청에 연결 끊김을 낸다."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("LLM_ENABLED", "0")
        off = get("SUP", "SUP-01").json()
        off_notes = client.get("/api/notifications", headers=H("SUP", "SUP-01")).json()
        off_op = get("OPR", "OPR-02").json()
    down = httpx.RemoteProtocolError("x")
    fake = llm(FakeLlm(route=down, select=down, verify=down, phrase=down))
    on = get("SUP", "SUP-01").json()
    assert on == off and on["message_source"] == "기본 문구"
    assert on["priorities"]["total"] == len(on["priorities"]["items"]) == 6
    assert client.get("/api/notifications", headers=H("SUP", "SUP-01")).json() == off_notes
    assert get("OPR", "OPR-02").json() == off_op
    assert fake.requests == []


# ---------------------------------------------------------------- 교대 번호 (shift_id 두 꼴, 지금 교대만, 자정 경계)
def test_shift_id_both_forms_and_only_current_shift():
    a = get("SUP", "SUP-01", shift_id="2026-10-01-D")
    b = get("SUP", "SUP-01", shift_id="SHIFT-261001-D")
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert (a.json()["shift_id"], a.json()["shift_key"]) == ("2026-10-01-D", "SHIFT-261001-D")
    r = get("SUP", "SUP-01", shift_id="2026-09-30-N")                  # 지난 교대는 교대 보고서에서 본다
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATE"
    assert r.json()["detail"]["current_shift_id"] == "2026-10-01-D"
    r = get("SUP", "SUP-01", shift_id="2026-10-1")
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"


@pytest.mark.parametrize("hh, mm, expect", [
    (2, 30, "SHIFT-261001-N"),    # 자정 뒤는 전날 야간 (고친 결함: 전에는 SHIFT-261002-N)
    (4, 59, "SHIFT-261001-N"),
    (5, 0, "SHIFT-261002-D"),     # 교대 사이(05:00~08:00)는 다음 교대
    (16, 59, "SHIFT-261002-D"),
    (17, 0, "SHIFT-261002-N"),
    (23, 59, "SHIFT-261002-N"),
])
def test_shift_id_of_midnight_boundary(hh, mm, expect):
    assert SH.shift_id_of(datetime(2026, 10, 2, hh, mm, tzinfo=SH.KST)) == expect


def test_prev_shift_and_window():
    assert SH.prev_shift("SHIFT-261001-D") == "SHIFT-260930-N"
    assert SH.prev_shift("SHIFT-261001-N") == "SHIFT-261001-D"
    start, end = SH.window("SHIFT-260930-N")
    assert (start.isoformat(), end.isoformat()) == ("2026-09-30T20:00:00+09:00", "2026-10-01T05:00:00+09:00")


def test_briefing_after_midnight_is_previous_night():
    get_state().set_now(datetime(2026, 10, 1, 2, 30, tzinfo=SH.KST))
    j = get("SUP", "SUP-02").json()
    assert j["shift_key"] == "SHIFT-260930-N" and j["last_shift"]["shift_key"] == "SHIFT-260930-D"


def test_injected_alarm_after_midnight_belongs_to_previous_night(monkeypatch):
    """자정 뒤 넣은 알람의 교대 번호 = 전날 야간 (demo_state 고침, 2026-10-11 P3). S1의 시작 시각(10:58)을 시험에서만 00:30으로 옮긴다."""
    monkeypatch.setitem(DS.SCENARIO_START, "S1", "2026-10-02T00:30:00+09:00")
    rows = get_state().inject("S1")
    assert rows and {r["shift_id"] for r in rows} == {"SHIFT-261001-N"}
