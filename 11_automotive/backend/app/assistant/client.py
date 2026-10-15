"""백엔드 → AI 비서 서비스 (로컬 LLM, 백엔드 밖 — API명세서 2.4 "바깥 모양만, 안쪽은 LLM 담당").

화면이 부르는 비서 질문(AST-02)·작업기록 메모 정리(MNT-10)를 MOM_ASSISTANT_URL로 넘기고 답을 그대로 돌려준다.
서비스가 없거나·멈추거나·형식이 틀리면 503 ASSISTANT_UNAVAILABLE → 화면은 기본 문구 (FR-AST-02-14, NFR-AIQ-09).
넘기는 주소(/chat, /work-record-assist)와 JSON 칸은 [제안] — LLM 담당 팀원이 정하면 여기 한 곳을 고친다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import get_settings
from ..errors import ASSISTANT_UNAVAILABLE, AppError

SOURCE_KEYS = ("doc_name", "doc_no", "rev", "section")     # 출처는 사내 문서 이름·번호·개정·§만 (D-03, R-85)
# chat_log.status 와 같은 코드 (2026-10-13: OUT_OF_ROLE 권한 밖 — 값 없이 누가 볼 수 있는지만)
CHAT_STATUS = ("OK", "NOT_IN_DOCS", "OUT_OF_ROLE", "REFUSED", "NO_RESPONSE")


def _unavailable(message: str, reason: str) -> AppError:
    return AppError(503, ASSISTANT_UNAVAILABLE, message, {"reason": reason})


def call(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    if not s.assistant_url:
        raise _unavailable("AI 비서 서비스가 연결되지 않음 — 기본 문구로 보여 준다", "NOT_CONFIGURED")
    req = urllib.request.Request(
        s.assistant_url.rstrip("/") + path, method="POST",
        data=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Service-Key": s.assistant_key})
    try:
        with urllib.request.urlopen(req, timeout=s.assistant_timeout_seconds) as r:   # noqa: S310 (설정한 내부 주소만)
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise _unavailable("AI 비서가 응답하지 않음 — 기본 문구로 보여 준다", type(e).__name__) from None
    if not isinstance(data, dict):
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    return data


def chat_answer(data: dict[str, Any]) -> dict[str, Any]:
    """AST-02 응답 모양 확인: answer·sources[]·related[]·status. 출처는 사내 문서 칸만 남긴다"""
    answer, status = data.get("answer"), str(data.get("status", "OK")).upper()
    if not isinstance(answer, str) or status not in CHAT_STATUS:
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    sources = [{k: s.get(k) for k in SOURCE_KEYS} for s in data.get("sources") or [] if isinstance(s, dict)]
    related = [str(x) for x in data.get("related") or []]
    return {"answer": answer, "sources": sources, "related": related, "status": status}
