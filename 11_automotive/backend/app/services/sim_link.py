"""백엔드 → 시뮬레이터(시연 서버) 연결 (2026-10-23, 화면 → 백엔드 전환 C2 — 기획서 12.1 "화면은 백엔드만").

화면은 백엔드만 부른다. 시뮬레이터(가짜 공장)가 주인인 일은 MOM_SIM_URL(예 http://127.0.0.1:8765)이 있으면
백엔드가 로그인·권한을 확인한 뒤 시뮬레이터에 넘긴다:
  시연 시계·사건 버튼·[처음으로]·[상황 일으키기], 로트 보류·해제, 공구 교체, 예방 정비 시작·끝, 작업기록서 확정 뒤 설비 복귀.
시뮬레이터가 바꾼 기록은 DB 중계(frontend/tools/db_relay.py → /api/ingest/sync)가 DB에 넣는다.
백엔드가 같은 표에 따로 쓰면 다음 중계가 덮어쓰거나 번호가 겹치므로 쓰는 쪽을 시뮬레이터 하나로 둔다.
[처음으로]는 시뮬레이터에만 넘긴다 — 회차가 바뀌면 중계가 DB를 시연 기준점으로 되돌린다 (fn_demo_reset을 두 번 하지 않게).
MOM_SIM_URL이 없으면 이 모듈은 쓰이지 않고 예전 동작(DB 시계·알람 넣기) 그대로다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import get_settings
from ..errors import AppError

TIMEOUT_SEC = 10


def enabled() -> bool:
    return bool(get_settings().sim_url)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """시뮬레이터의 /api/<path>를 부른다. 시뮬레이터 오류({code, message, detail})는 같은 상태·코드로 돌려준다"""
    url = get_settings().sim_url.rstrip("/") + "/api/" + path.lstrip("/")
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if method != "GET" else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as r:     # noqa: S310 — 설정한 시뮬레이터 주소만
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read() or b"{}")
        except ValueError:
            err = {}
        raise AppError(e.code, err.get("code") or "INVALID_STATE", err.get("message") or f"시뮬레이터 오류 {e.code}",
                       err.get("detail") or {}) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AppError(503, "INVALID_STATE", "시뮬레이터(시연 서버)에 연결하지 못함", {"reason": str(e)[:200]}) from None
