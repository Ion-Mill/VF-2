"""경계·예외 시험 (테스트계획서_v1 4장, 2026-10-11 P2). 시험 이름 앞머리 = 시험 ID `T-<요구사항 ID>-<번호>`.

- 대응표: tests/req_map.json (시험 ID → 요구사항 ID → 이 파일의 시험 함수, 상태 있음·일부·없음).
- 계산기 수준 시험은 그 계산을 쓰는 화면·알림이 아직 없으면 대응표에 "일부"로 적는다.
- 숫자는 요구사항정의서 수용 기준에서 가져온다 (root-cause-guards 8절: 운영 질문의 정답 기준은 수용 기준에서).
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.demo_state import get_state
from backend.repositories.csv_repo import get_repo
from backend.services import metrics as M
from backend.services import notifications as N
from backend.services import shift_reports as SR
from backend.services.repeat_alarm import stage1_at
from backend.services.report_rank import Item, rank_report
from backend.tools import query_tools as T

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    get_state().reset()
    yield
    get_state().reset()


# ---------------------------------------------------------------- 목표 미달 위험 (FR-AST-02-04)
def test_T_FR_AST_02_04_1_target_risk_80_vs_81():
    """총 목표 90(이월 0): 예측 80개 → 위험(알림), 81개 → 없음. 위험 = 예측 < 총 목표 × 90% [가상] (DOC-07 §8).
    알림 만들기는 아직 없다(알림 목록 not_built) → 대응표 "일부"."""
    assert M.target_risk(80, 90) is True
    assert M.target_risk(81, 90) is False
    # 예측 = 현재 실적 + 최근 1시간 속도 × 남은 시간 (분 단위로 넣음)
    assert M.forecast_output(60, 0.1, 200) == 80.0 and M.target_risk(M.forecast_output(60, 0.1, 200), 90) is True
    assert M.forecast_output(61, 0.1, 200) == 81.0 and M.target_risk(M.forecast_output(61, 0.1, 200), 90) is False


def test_T_FR_AST_02_04_2_target_risk_with_carry_over_93():
    """우리 번호: 야간 총 목표 93(= 90 + 이월 3) → 기준 83.7개 — 예측 83개 → 위험, 84개 → 없음 (FR-AST-02-04 수용 기준 둘째 줄).
    이월 계산 자체(FR-PRD-01-15)는 멈춤 ④에서 만든다 → 대응표 "일부"."""
    assert M.target_risk(83, 93) is True
    assert M.target_risk(84, 93) is False


# ---------------------------------------------------------------- 반복 알람 1단계 (FR-AST-02-03)
def test_T_FR_AST_02_03_1_repeat_stage1_two_vs_three():
    """같은 설비·같은 알람이 (1분 묶기 뒤) 7일 안에 2번 → 1단계 아님, 3번 → 3번째에 1단계 (DOC-07 §10.2·§10.4 [가상]).
    "7일 안"은 지금 구현대로 **7일 미만**으로 읽는다 — 첫 알람에서 정확히 7일 0분 뒤의 세 번째는 세지 않는다 (해석 기록, 2026-10-11)."""
    t0 = datetime(2026, 9, 1, 8, 0)
    assert stage1_at([t0, t0 + timedelta(days=3)]) is None
    assert stage1_at([t0, t0 + timedelta(days=3), t0 + timedelta(days=6)]) == t0 + timedelta(days=6)
    # 1분 안 3번은 1건으로 묶는다 (DOC-07 §10.2 "1분 안에 3번 이상") → 묶은 뒤 2번
    burst = [t0, t0 + timedelta(seconds=20), t0 + timedelta(seconds=40)]
    assert stage1_at(burst + [t0 + timedelta(days=2)]) is None
    # 7일 미만 경계
    assert stage1_at([t0, t0 + timedelta(days=3), t0 + timedelta(days=7)]) is None
    assert stage1_at([t0, t0 + timedelta(days=3), t0 + timedelta(days=7) - timedelta(minutes=1)]) is not None


# ---------------------------------------------------------------- 공구 수명 (FR-AST-02-09)
def _tool(eq, used):
    return {"equipment_id": eq, "tool_no": "T05", "tool_name": "M6 탭", "usage_unit": "HOLES", "used": str(used),
            "limit": "400", "since": "2026-09-30T08:00:00+09:00", "is_synthetic": "true"}


def test_T_FR_AST_02_09_1_tool_life_359_vs_360(monkeypatch):
    """T05 M6 탭 한도 400구멍: 359구멍 = 89%(버림) → 알림 없음, 360구멍 = 90% → 주의 알림 (FR-AST-02-09 수용 기준).
    알림은 조회 도구(90% 이상 거르기)와 알림 목록(tool_90)을 함께 본다. 앞선 설명의 "공구 80/81%"는 잘못이었다 —
    80/81은 목표 미달 예측(FR-AST-02-04)의 수량이다 (2026-10-11 바로잡음)."""
    assert M.tool_usage_pct(359, 400) == 89
    assert M.tool_usage_pct(360, 400) == 90
    repo = get_repo()
    real = repo.table
    rows = [_tool("VF2-01", 359), _tool("VF2-02", 360)]
    monkeypatch.setattr(repo, "table", lambda name: rows if name == "tool_state" else real(name))
    assert [t["equipment_id"] for t in T.tool_life("MGR", min_pct=90)["rows"]] == ["VF2-02"]
    notes = [n for n in N.all_notifications(get_state()) if n["kind"] == "tool_90"]
    assert [(n["equipment_id"], n["title"]) for n in notes] == [("VF2-02", "공구 수명 90% — T05 M6 탭")]
    assert notes[0]["importance"] == "주의" and notes[0]["is_synthetic"] is True


# ---------------------------------------------------------------- 오래 방치 순서 (FR-AST-01-06)
def test_T_FR_AST_01_06_2_long_open_oldest_first():
    """우리 번호: 24시간 넘게 처리 안 된 주의 알림(순위 0-1)은 **처리 안 된 시간이 긴 순** (FR-AST-01-06).
    2026-10-11 고침: 전에는 원래 알림 종류의 하위 순서(①~⑤)를 먼저 써서 더 새 알림이 앞에 올 수 있었다."""
    newer = datetime(2026, 9, 29, 8, 0)
    older = datetime(2026, 9, 28, 12, 0)
    items = [Item("new", "0-1", "공구 90% (30시간)", newer.isoformat(), sub_order=1, sort_value=-newer.timestamp()),
             Item("old", "0-1", "재고 부족 (50시간)", older.isoformat(), sub_order=5, sort_value=-older.timestamp())]
    assert [l.items[0].item_id for l in rank_report(items)["lines"]] == ["old", "new"]
    # 순위 3은 하위 순서(반복 2단계 ① … 재고 부족 ⑤)를 그대로 쓴다
    items3 = [Item("inv", "3", "재고 부족", "2026-09-28T00:00", sub_order=5),
              Item("rep", "3", "반복 알람 2단계", "2026-09-30T00:00", sub_order=1)]
    assert [l.items[0].item_id for l in rank_report(items3)["lines"]] == ["rep", "inv"]
    # 순위 1·4 등은 발생 시각이 이른 순 (하위 순서를 쓰지 않음)
    items4 = [Item("b", "4", "참고 b", "2026-09-30T10:00", sub_order=1), Item("a", "4", "참고 a", "2026-09-30T09:00", sub_order=3)]
    assert [l.items[0].item_id for l in rank_report(items4)["lines"]] == ["a", "b"]


# ---------------------------------------------------------------- 교대 보고서 확정 권한 (FR-PRD-02-11, RPT-03)
# 2026-10-11 P4: 주소·칸을 명세 RPT-03으로 바꿈 (옛 POST /api/shift-reports/SR-260930-D/confirm + {"user"}) — 확정자 = X-User,
# 몸에는 version. 가상 데이터의 교대 보고서는 모두 확정이라, 확정되는 경우를 보려면 시연 상태에 초안을 겹쳐 둔다(SR.draft).
CONFIRM = "/api/reports/shift/2026-09-30-D/confirm"   # 9/30 주간 — 교대 달력의 반장 SUP-01


@pytest.mark.parametrize("role, user", [("OPR", "OPR-02"), ("MNT", "MNT-01"), ("MGR", "MGR-01"), ("SUP", "SUP-02")])
def test_T_FR_PRD_02_11_1_others_cannot_confirm(role, user):
    """OPR·MNT·MGR·다른 교대 반장(SUP-02)이 확정 API로 직접 보내면 모두 `FORBIDDEN` (테스트계획서 4장).
    다른 교대 반장 거절은 2026-10-11 P2에 구현, 오류 코드는 P4."""
    SR.draft(get_state(), "2026-09-30-D")
    r = client.post(CONFIRM, json={"version": 0}, headers={"X-Role": role, "X-User": user})
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_T_FR_PRD_02_11_1_that_shift_sup_confirms():
    SR.draft(get_state(), "2026-09-30-D")
    r = client.post(CONFIRM, json={"version": 0}, headers={"X-Role": "SUP", "X-User": "SUP-01"})
    assert r.status_code == 200
    assert r.json()["confirmed_by"] == "SUP-01" and r.json()["status"] == "확정" and r.json()["is_synthetic"] is True
    again = client.post(CONFIRM, json={"version": 0}, headers={"X-Role": "SUP", "X-User": "SUP-01"})
    assert again.status_code == 409 and again.json()["code"] == "INVALID_STATE"        # 이미 확정


def test_confirm_needs_current_version():
    SR.draft(get_state(), "SHIFT-260930-D")                                              # 데이터 꼴 교대 번호도 받는다
    r = client.post(CONFIRM, json={"version": 3}, headers={"X-Role": "SUP", "X-User": "SUP-01"})
    assert r.status_code == 409 and r.json()["code"] == "CONFLICT_VERSION" and r.json()["detail"]["current_version"] == 0


def test_confirm_user_role_must_match_header():
    """확정자(X-User)의 역할이 X-Role과 다르면 거절 — SUP-01 이름을 OPR 머리말로 보내도 확정되지 않는다.
    원래 기대값 403 → 2026-10-11 P4에서 401 UNAUTHORIZED (사용자와 역할이 다른 것은 로그인 문제)."""
    SR.draft(get_state(), "2026-09-30-D")
    r = client.post(CONFIRM, json={"version": 0}, headers={"X-Role": "OPR", "X-User": "SUP-01"})
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED"


def test_confirm_already_confirmed_data_report():
    """가상 데이터 그대로(겹침 없음)의 보고서는 이미 확정이다 → INVALID_STATE."""
    r = client.post(CONFIRM, json={"version": 0}, headers={"X-Role": "SUP", "X-User": "SUP-01"})
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATE"
