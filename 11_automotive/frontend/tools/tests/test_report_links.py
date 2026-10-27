"""시연 서버 보고서 칸 시험 (2026-10-20 정비 탭 확인 요청 1·2) — 백엔드(FastAPI)와 같은 규칙인지.

실행 (frontend/ 폴더에서):  ..\\데이터생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
지키는 것: ① 오늘의 문제 글 끝 "관리자 메모: …"를 메모로 떼어 낸다(백엔드 fn_split_memo와 같음) ② 글은 그대로 두고 memo 칸만 더한다
③ 정지 ↔ 작업지시서: 정지 알람으로 만든 것 먼저, 없으면 그 알람의 반복 알람 2단계 알림으로 만든 것 ④ 상태는 보고서 시점 기준
"""
import io
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "데이터생성기"))

_out, sys.stdout = sys.stdout, io.StringIO()     # sim_server가 sys.stdout.buffer를 감싸 바꾸므로(콘솔 한글) 시험 출력 잡기와 부딪히지 않게
import sim_server  # noqa: E402
sys.stdout = _out
from server_live import Live  # noqa: E402


def test_split_memo_generator_and_sim_forms():
    assert sim_server.split_memo("전체 6건 … 8건 관리자 메모: 내일 오전 정비 일정 확인.") == ("전체 6건 … 8건", "내일 오전 정비 일정 확인.")
    assert sim_server.split_memo("오늘의 문제 / 관리자 메모: 공구 주문") == ("오늘의 문제", "공구 주문")
    assert sim_server.split_memo("메모 없는 글") == ("메모 없는 글", None)
    assert sim_server.split_memo(None) == (None, None)


def test_with_memo_keeps_summary():
    d = sim_server.with_memo({"issues_summary": "A 관리자 메모: B"})
    assert d == {"issues_summary": "A 관리자 메모: B", "memo": "B"}          # 글은 그대로 (지금 화면이 떼어 보인다)
    assert sim_server.with_memo({"issues_summary": "A 관리자 메모: B", "memo": "확정 때 메모"})["memo"] == "확정 때 메모"


def _live(work_orders, notifications):
    live = Live.__new__(Live)
    live.P = SimpleNamespace(work_orders=work_orders, notifications=notifications)
    return live


WO = dict(cancelled_at="", completed_at="", approved_at="")


def test_wo_link_direct_and_repeat_stage2():
    live = _live(
        [{**WO, "wo_no": "MW-0903", "alarm_event_id": "160", "trigger_notification_id": "", "status": "DONE",
          "created_at": "2026-09-14T12:00:00+09:00", "approved_at": "2026-09-14T12:10:00+09:00", "completed_at": "2026-09-14T15:00:00+09:00"},
         {**WO, "wo_no": "MW-0904", "alarm_event_id": "", "trigger_notification_id": "417", "status": "DONE",
          "created_at": "2026-09-14T14:41:00+09:00", "approved_at": "2026-09-14T14:55:00+09:00", "completed_at": "2026-09-15T11:49:00+09:00"}],
        [{"notification_id": "417", "alarm_event_id": "167"}])
    end = datetime.fromisoformat("2026-09-15T05:00:00+09:00")
    assert live.wo_link(160, end) == {"wo_no": "MW-0903", "wo_status": "DONE", "wo_status_at_report": "DONE"}
    assert live.wo_link(167, end) == {"wo_no": "MW-0904", "wo_status": "DONE", "wo_status_at_report": "IN_PROGRESS"}   # 반복 2단계 경유
    assert live.wo_link(999, end)["wo_no"] is None
    assert live.wo_link(None, end)["wo_no"] is None
    early = datetime.fromisoformat("2026-09-14T14:45:00+09:00")
    assert live.wo_link(167, early)["wo_status_at_report"] == "WAITING_APPROVAL"                                     # 승인 전
    before = datetime.fromisoformat("2026-09-14T14:30:00+09:00")
    assert live.wo_link(167, before)["wo_status_at_report"] is None                                                  # 아직 없던 것
