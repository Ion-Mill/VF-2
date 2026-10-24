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
from ..errors import ASSISTANT_UNAVAILABLE, NOT_FOUND, VALIDATION, AppError

SOURCE_KEYS = ("doc_name", "doc_no", "rev", "section")     # 출처는 사내 문서 이름·번호·개정·§만 (D-03, R-85)
# chat_log.status 와 같은 코드 (2026-10-13: OUT_OF_ROLE 권한 밖 — 값 없이 누가 볼 수 있는지만)
CHAT_STATUS = ("OK", "NOT_IN_DOCS", "OUT_OF_ROLE", "REFUSED", "NO_RESPONSE")


def _unavailable(message: str, reason: str) -> AppError:
    return AppError(503, ASSISTANT_UNAVAILABLE, message, {"reason": reason})


_PUBLIC_BASE = "비서가 지금 답하지 못합니다. 잠시 후 다시 시도해 주세요"
_PUBLIC_TAILS = {
    "Gemini가 바빠 503을 냈습니다.",
    "Gemini가 응답 시간 안에 답을 주지 않았습니다.",
    "Gemini 호출이 그 밖으로 실패했습니다.",
}


def public_assistant_message(message: str) -> str | None:
    """비서가 화면에 내도 된다고 정한 문장만 통과시킨다. 그 밖은 연결 실패로 본다."""
    if message == _PUBLIC_BASE:
        return message
    head, sep, tail = message.partition("\n")
    if sep and head == _PUBLIC_BASE and tail in _PUBLIC_TAILS:
        return message
    return None


def _http_error(e: urllib.error.HTTPError) -> AppError:
    try:
        body = json.loads(e.read().decode("utf-8"))
        message = body.get("message") if isinstance(body, dict) else None
    except (ValueError, OSError, AttributeError, UnicodeDecodeError):
        message = None
    if isinstance(message, str):
        public = public_assistant_message(message)
        if public:
            return _unavailable(public, "ASSISTANT_MESSAGE")
    return _unavailable("AI 비서가 응답하지 않음 — 기본 문구로 보여 준다", f"HTTP_{e.code}")


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
    except urllib.error.HTTPError as e:
        raise _http_error(e) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise _unavailable("AI 비서가 응답하지 않음 — 기본 문구로 보여 준다", type(e).__name__) from None
    if not isinstance(data, dict):
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    return data


# ---- 음성 입력 (2026-10-20): 화면의 마이크 소리를 비서의 POST /transcribe 로 그대로 넘긴다. 비서 서비스가 사내 서버에서 글자로 바꾼다.
# 비서가 돌려주는 오류 코드 → 명세서의 7개 코드 (errors.py: 새 코드를 만들지 않는다). 원래 코드는 detail.reason 에 남긴다.
VOICE_TIMEOUT_S = 45.0     # 비서의 음성 시간 제한(기본 15초, 녹음을 60초까지 늘리면 40초)보다 조금 길게. 채팅 답처럼 130초를 기다리지 않는다 (2026-10-20: 20 → 45초)
VOICE_ERRORS: dict[str, tuple[int, str, str]] = {
    "VOICE_OFF": (404, NOT_FOUND, "음성 입력이 꺼져 있음"),
    "EMPTY_AUDIO": (422, VALIDATION, "녹음이 비어 있음"),
    "BAD_AUDIO": (422, VALIDATION, "녹음을 읽지 못함"),
    "AUDIO_TOO_LARGE": (422, VALIDATION, "녹음이 너무 큼"),
    "AUDIO_TOO_LONG": (422, VALIDATION, "녹음이 너무 김"),
    "VOICE_BUSY": (503, ASSISTANT_UNAVAILABLE, "음성 인식이 바쁨 — 잠시 후 다시"),
    "VOICE_TIMEOUT": (503, ASSISTANT_UNAVAILABLE, "음성 인식이 오래 걸려 멈춤"),
    "VOICE_FAILED": (503, ASSISTANT_UNAVAILABLE, "음성 인식에 실패함"),
}


def _voice_http_error(e: urllib.error.HTTPError) -> AppError:
    try:
        code = json.loads(e.read().decode("utf-8")).get("code")
    except (ValueError, OSError, AttributeError):
        code = None
    if code in VOICE_ERRORS:
        status, app_code, message = VOICE_ERRORS[code]
        return AppError(status, app_code, message, {"reason": code})
    return _unavailable("AI 비서가 음성 요청을 받지 못함", "SERVICE_KEY" if e.code == 401 else f"HTTP_{e.code}")


def call_voice(method: str, path: str, data: bytes | None = None) -> dict[str, Any]:
    s = get_settings()
    if not s.assistant_url:
        raise _unavailable("AI 비서 서비스가 연결되지 않음", "NOT_CONFIGURED")
    headers = {"X-Service-Key": s.assistant_key}
    if data is not None:
        headers["Content-Type"] = "application/octet-stream"        # 소리 원본 바이트 (webm/opus·mp4·wav) — 서버가 내용으로 알아본다
    req = urllib.request.Request(s.assistant_url.rstrip("/") + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=VOICE_TIMEOUT_S) as r:   # noqa: S310 (설정한 내부 주소만)
            out = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:           # URLError 의 하위 — 먼저 잡는다
        raise _voice_http_error(e) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise _unavailable("AI 비서가 응답하지 않음", type(e).__name__) from None
    if not isinstance(out, dict):
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    return out


def voice_status() -> dict[str, Any]:
    out = call_voice("GET", "/voice/status")
    if not isinstance(out.get("enabled"), bool):
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    return {"enabled": out["enabled"], "ready": bool(out.get("ready")), "max_seconds": float(out.get("max_seconds") or 0)}


def voice_transcribe(audio: bytes) -> dict[str, Any]:
    """글자(text, 비어 있을 수 있음)·거절 까닭(reason)·소리 길이(seconds)·걸린 시간(ms)만 돌려준다 — 소리는 저장하지도 되돌려 주지도 않는다."""
    out = call_voice("POST", "/transcribe", audio)
    if not isinstance(out.get("text"), str):
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    reason = out.get("reason")
    return {"text": out["text"], "reason": reason if isinstance(reason, str) else None,
            "seconds": float(out.get("seconds") or 0), "ms": int(out.get("ms") or 0)}


def chat_answer(data: dict[str, Any]) -> dict[str, Any]:
    """AST-02 응답 모양 확인: answer·sources[]·related[]·status. 출처는 사내 문서 칸만 남긴다"""
    answer, status = data.get("answer"), str(data.get("status", "OK")).upper()
    if not isinstance(answer, str) or status not in CHAT_STATUS:
        raise _unavailable("AI 비서 응답 형식이 틀림", "FORMAT")
    sources = [{k: s.get(k) for k in SOURCE_KEYS} for s in data.get("sources") or [] if isinstance(s, dict)]
    related = [str(x) for x in data.get("related") or []]
    return {"answer": answer, "sources": sources, "related": related, "status": status}
