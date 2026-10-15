"""가상 데이터 표시 (API명세서 1장 "모든 운영 데이터 응답에 is_synthetic: true", NFR-DATA-08, R-59). DB 없이 도는 순수 로직.

응답이 객체면 맨 위에 하나, 목록이면 줄마다 하나 붙인다 [제안] — R-59 "묶음 단위 / 줄마다"는 [선택 필요: 기술 회의]라서,
목록은 감싸지 않고(응답 모양을 바꾸지 않으려고) 줄마다 둔다. 이미 같은 칸이 있으면 그대로 둔다.
"""
from __future__ import annotations

from typing import Any

FIELD = "is_synthetic"
# 운영 데이터가 아닌 응답: 로그인·내 정보·역할 바꾸기·상태 확인·실시간·서버끼리(설비 데이터 받기, AI 비서 서비스)
SKIP_PREFIXES = ("/api/auth/", "/api/demo/", "/api/me", "/api/health", "/api/stream/", "/api/ingest/",
                 "/api/assistant/tools", "/api/assistant/drafts", "/api/assistant/notifications")


def applies(path: str) -> bool:
    return path.startswith("/api/") and not path.startswith(SKIP_PREFIXES)


def mark(data: Any, flag: bool) -> Any:
    if isinstance(data, dict):
        return data if FIELD in data else {**data, FIELD: flag}
    if isinstance(data, list):
        return [mark(x, flag) if isinstance(x, dict) else x for x in data]
    return data
