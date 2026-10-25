"""시간 규칙 스케줄러 (시연 시계 app_now 기준).

  · 몇 분마다: 승인 대기 30분·2시간, 예방 정비 기한, CMM 결과 미수신, 목표 미달 위험(총 목표 기준), 지금 야간 이월
    (fn_run_time_rules)
  · 교대가 끝나면(shift.end_at — 주간·야간): 교대 보고서 AI비서 초안 + 그 교대 반장에게 확정 요청 알림 (FR-AST-02-17),
    주간이면 같은 날 야간 이월 계산 (R-88)
  · 일일 보고서 초안 = 야간 교대 보고서 확정 즉시 (DB 트리거). 야간 교대 끝 1시간 뒤(교대 09~18/21~06이면 07:00)까지
    확정이 없으면 여기서 만든다
    (확정 안 된 교대 칸은 잠정 — 교대 보고서가 확정되면 다시 채움, R-72) + MGR에게 확정 요청 (DAILY_REPORT_PENDING)
  · 오늘·내일 근무일·교대가 없으면 만든다 (fn_ensure_work_day), AI 비서 채팅 기록 30일 지난 것 삭제 (6.53 #18)
여러 서버가 떠도 한 번만 돌게 advisory lock을 잡는다. 일마다 트랜잭션을 따로 둔다 (하나가 실패해도 나머지는 진행).
시연 시계를 빨리 돌리면(1초 = 1분) 진짜 60초마다 도는 이 루프가 시연 시간으로 1시간씩 건너뛴다 — 시간 규칙은
"지났는지"로 판단하므로 놓치지 않는다.
"""
from __future__ import annotations

import asyncio
import logging

from ..config import get_settings
from ..db import Db, engine

log = logging.getLogger("mom.scheduler")
LOCK_KEY = 72_002


def tick() -> dict:
    s = get_settings()
    out: dict = {"time_rules": 0, "shift_drafts": [], "daily_drafts": []}
    with engine().begin() as conn:
        db = Db(conn)
        if not db.scalar("common.try_lock", key=LOCK_KEY):
            return {"skipped": "다른 서버가 돌리는 중"}
        out["new_shifts"] = db.scalar("reports.ensure_days")
        out["time_rules"] = db.scalar("reports.time_rules", cmm_wait_min=s.cmm_no_result_minutes)
        out["chat_purged"] = db.scalar("reports.purge_chat")
        shifts = [r["shift_id"] for r in db.all("reports.ended_shifts")]
        due = [r["work_date"] for r in db.all("reports.daily_due")]
    for shift_id in shifts:
        try:
            with engine().begin() as conn:
                out["shift_drafts"].append((shift_id, Db(conn).scalar("reports.shift_draft", shift_id=shift_id)))
        except Exception:
            log.exception("교대 보고서 초안 실패: %s", shift_id)
    for work_date in due:
        try:
            with engine().begin() as conn:
                out["daily_drafts"].append((str(work_date), Db(conn).scalar("reports.daily_draft", work_date=work_date)))
        except Exception:
            log.exception("일일 보고서 초안 실패: %s", work_date)
    return out


async def run_forever(interval_seconds: float = 60.0) -> None:
    log.info("스케줄러 시작 (%.0f초마다)", interval_seconds)
    while True:
        try:
            result = await asyncio.to_thread(tick)
            if any(result.get(k) for k in ("time_rules", "shift_drafts", "daily_drafts", "new_shifts", "chat_purged")):
                log.info("스케줄러: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("스케줄러 오류")
        await asyncio.sleep(interval_seconds)
