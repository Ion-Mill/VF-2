"""Claude API가 실패한 호출의 Gemini 대체 (2026-10-24).

채팅 앱만 쓴다. 모델은 gemini-3.8-flash, 노력은 medium, 방식은 generateContent REST다.
HTTP 503과 응답 시간 초과만 3초 뒤 같은 호출을 한 번 더 하고, 한 번의 대기는 20초다.
열쇠는 프로세스 환경 변수 GEMINI_API_KEY가 있으면 그것을 쓰고, 없으면 이 폴더 .env의 같은 이름이다.
값·요청 본문·생각 과정은 로그에 남기지 않는다. 새 패키지는 쓰지 않는다.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from backend.config import _dotenv
from backend.llm import deadline as DL
from backend.llm.client import LlmBadOutput, LlmUnavailable
from backend.privacy import outbound_guard as OG

MODEL = "gemini-3.8-flash"
EFFORT = "medium"
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
ATTEMPT_S = 20.0       # 한 번의 대기. 60초를 한 번에 쓰면 혼잡일 때 재시도가 채팅 제한에 안 들어간다
RETRY_WAIT_S = 3.0     # HTTP 503·응답 시간 초과만, 이만큼 쉬고 같은 호출을 한 번 더
_IN_USD = 0.75    # 100만 토큰당 달러. 공식 소개 가격(연말까지). 상한은 두지 않는다
_OUT_USD = 3.75

_transport = None    # 시험이 (url, body, headers, timeout) -> (status, bytes) 를 끼운다


def gemini_api_key() -> str:
    """빈 값은 없는 것으로 본다. 값은 로그·예외 글에 넣지 않는다."""
    env = os.environ.get("GEMINI_API_KEY", "").strip()
    if env:
        return env
    return _dotenv().get("GEMINI_API_KEY", "").strip()


def use_transport(fn) -> None:
    global _transport
    _transport = fn


def _timeout(s) -> float:
    read = min(ATTEMPT_S, s.read_s)
    d = DL.current()
    if d is None:
        return read
    t = d.timeout_for(read)
    if t is None:
        raise LlmUnavailable("시간 예산 부족")
    return t


def _retryable(exc: BaseException) -> bool:
    """혼잡(503)과 그 대기가 끝난 시간 초과만 다시 부른다. 인증·연결·형식 오류는 한 번으로 끝낸다."""
    return isinstance(exc, LlmUnavailable) and str(exc) in ("HTTP 503", "응답 시간 초과")


def _contents(messages: list[dict]) -> tuple[str, list[dict]]:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system" and m.get("content"))
    contents = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        text = str(m.get("content") or "")
        if not text:
            continue
        contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]})
    return system, contents


def _answer_text(data: dict) -> str:
    cands = data.get("candidates") if isinstance(data, dict) else None
    if not cands:
        raise LlmBadOutput("빈 답")
    first = cands[0] if isinstance(cands[0], dict) else {}
    if first.get("finishReason") == "MAX_TOKENS":
        raise LlmBadOutput("길이 초과로 잘림")
    parts = (first.get("content") or {}).get("parts") or []
    texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text") and not p.get("thought")]
    if not texts:
        raise LlmBadOutput("빈 답")
    return str(texts[-1])


def _reason(code: int) -> str:
    if code == 400:
        return "요청 거절 400"
    if code in (401, 403):
        return f"인증·권한 오류 {code}"
    if code == 429:
        return "속도 제한 429"
    return f"HTTP {code}"


def _post(url: str, body: dict, key: str, timeout: float) -> tuple[int, bytes]:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    if _transport is not None:
        return _transport(url, body, headers, timeout)
    req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        raise LlmUnavailable(_reason(getattr(e, "code", 0) or 0)) from e
    except TimeoutError as e:
        raise LlmUnavailable("응답 시간 초과") from e
    except urllib.error.URLError as e:
        why = str(getattr(e, "reason", "") or "")
        if "timed out" in why.lower():
            raise LlmUnavailable("응답 시간 초과") from e
        raise LlmUnavailable("연결 실패") from e


def _record(name: str, data: dict, ms: int) -> None:
    from backend.llm.claude_client import _write_row
    usage = data.get("usageMetadata") if isinstance(data, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    in_t = int(usage.get("promptTokenCount") or 0)
    out_t = int(usage.get("candidatesTokenCount") or 0)
    usd = (in_t * _IN_USD + out_t * _OUT_USD) / 1_000_000
    _write_row({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "via": "api", "model": MODEL, "effort": EFFORT,
                "job": name, "in": in_t, "out": out_t, "ms": ms, "usd": round(usd, 6)}, usd)


def _exchange(body: dict, key: str, s) -> bytes:
    timeout = _timeout(s)
    code, raw = _post(URL, body, key, timeout)
    if code >= 400:
        raise LlmUnavailable(_reason(code))
    return raw


def chat_json(messages: list[dict], schema: dict, name: str, s) -> dict:
    """같은 문장·같은 JSON 스키마로 호출한다. HTTP 503과 응답 시간 초과만 한 번 더 부른다. 스키마를 어기면 실패다. Claude 차단기는 건드리지 않는다."""
    from backend.llm.claude_client import prepare_schema, validate_constraints
    key = gemini_api_key()
    if not key:
        raise LlmUnavailable("GEMINI_API_KEY 없음")
    messages, _ = OG.scrub_messages(messages)
    system, contents = _contents(messages)
    if not contents:
        raise LlmBadOutput("빈 질문")
    body = {
        "contents": contents,
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": EFFORT},
            "responseMimeType": "application/json",
            "responseJsonSchema": prepare_schema(schema),
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    t0 = time.monotonic()
    try:
        raw = _exchange(body, key, s)
    except LlmUnavailable as e:
        if not _retryable(e):
            raise
        time.sleep(RETRY_WAIT_S)
        raw = _exchange(body, key, s)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise LlmBadOutput("JSON 아님") from e
    text = _answer_text(data)
    try:
        out = json.loads(text or "")
    except json.JSONDecodeError as e:
        raise LlmBadOutput("JSON 아님") from e
    if not isinstance(out, dict):
        raise LlmBadOutput("JSON 객체 아님")
    viol = validate_constraints(out, schema)
    if viol:
        raise LlmBadOutput(f"스키마 제약 위반: {viol}")
    _record(name, data, int((time.monotonic() - t0) * 1000))
    return out
