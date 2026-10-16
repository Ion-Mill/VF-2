"""API 오류 형식 (API명세서_v1 1장 "오류 형식", 2026-10-11 멈춤 ③ P4).

모든 오류 응답 = {"code": 코드, "message": 쉬운 한국어 한 문장, "detail": {…}} — detail은 늘 객체다.

| code | 뜻 | HTTP [제안] |
|---|---|---|
| UNAUTHORIZED | 로그인 안 됨 (역할 머리말 없음·모름, 사용자와 역할이 다름) | 401 |
| FORBIDDEN | 역할에 권한 없음 | 403 |
| NOT_FOUND | 없는 기록·주소 | 404 |
| VALIDATION | 값이 틀림·빠짐 | 422 |
| INVALID_STATE | 지금 상태에서 할 수 없음 (이미 처리·이미 확정·이미 넣음·시연 모드 아님) | 409 |
| CONFLICT_VERSION | 버전 충돌 | 409 |
| ASSISTANT_UNAVAILABLE | 비서가 답을 만들다 멈춤 (LLM 실패는 지금처럼 기본 문장으로 답하므로 여기에 오지 않는다) | 503 |
| EXTERNAL_LLM_DISABLED | 외부 LLM을 골랐는데 서버 스위치(EXTERNAL_LLM_APP)가 꺼져 있음 (2026-10-15 앱 스위치, API명세서에 없는 우리 추가 [제안]) | 503 |
| EXTERNAL_LLM_UNAVAILABLE | 외부 LLM 호출이 재료를 정하는 단계(분류·줄 고르기·검증)에서 실패함 — 자동으로 로컬로 바꾸지 않고 오류로 끝낸다 (우리 추가 [제안]) | 503 |
| THINK_DISABLED | [Qwen 깊게 생각]을 눌렀는데 서버 스위치(THINK_APP)가 꺼져 있음 (2026-10-15, 우리 추가 [제안]) | 503 |
| THINK_BUSY | 다른 깊은 생각 요청이 돌고 있어 받지 못함 — 동시에 하나만 받는다(서버가 2칸이라 4~5분짜리가 겹치면 다른 질문이 막힘) (우리 추가 [제안]) | 503 |

HTTP 상태 번호는 명세에 없어 [제안]으로 정했다(불일치 아님 — 명세가 정하지 않음).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.auth.permissions import NotLoggedIn, PermissionDenied

STATUS = {"UNAUTHORIZED": 401, "FORBIDDEN": 403, "NOT_FOUND": 404, "VALIDATION": 422, "INVALID_STATE": 409,
          "CONFLICT_VERSION": 409, "ASSISTANT_UNAVAILABLE": 503, "EXTERNAL_LLM_DISABLED": 503, "EXTERNAL_LLM_UNAVAILABLE": 503,
          "THINK_DISABLED": 503, "THINK_BUSY": 503}
CODE_OF_STATUS = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "NOT_FOUND", 409: "INVALID_STATE",
                  422: "VALIDATION", 503: "ASSISTANT_UNAVAILABLE"}
MESSAGE = {"UNAUTHORIZED": "로그인 정보가 없거나 맞지 않습니다", "FORBIDDEN": "권한이 없습니다", "NOT_FOUND": "없는 기록입니다",
           "VALIDATION": "보낸 값이 틀렸거나 빠졌습니다", "INVALID_STATE": "지금 상태에서는 할 수 없습니다",
           "CONFLICT_VERSION": "다른 사람이 먼저 고쳤습니다 — 다시 불러온 뒤 고칩니다",
           "ASSISTANT_UNAVAILABLE": "비서가 지금 답하지 못합니다. 화면의 숫자·문서는 그대로 쓸 수 있습니다",
           "EXTERNAL_LLM_DISABLED": "외부 LLM이 서버에서 꺼져 있습니다. 로컬 LLM(Qwen)으로 질문해 주세요",
           "EXTERNAL_LLM_UNAVAILABLE": "외부 LLM이 지금 답하지 못합니다. [Qwen으로 다시 묻기]로 로컬 LLM에 물어볼 수 있습니다",
           "THINK_DISABLED": "깊게 생각하는 기능이 서버에서 꺼져 있습니다. 버튼을 끄고 다시 질문해 주세요",
           "THINK_BUSY": "다른 질문이 지금 깊게 생각하는 중입니다(한 번에 하나만 처리합니다). 끝난 뒤 다시 눌러 주세요"}


class ApiError(Exception):
    def __init__(self, code: str, message: str | None = None, detail: dict | None = None):
        if code not in STATUS:
            raise ValueError(f"모르는 오류 코드: {code}")
        super().__init__(message or MESSAGE[code])
        self.code, self.message, self.detail = code, message or MESSAGE[code], dict(detail or {})


def body(code: str, message: str | None = None, detail: dict | None = None) -> dict:
    return {"code": code, "message": message or MESSAGE[code], "detail": dict(detail or {})}


def _json(code: str, message: str | None = None, detail: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=STATUS[code], content=body(code, message, detail))


def install(app: FastAPI) -> None:
    """앱의 오류 처리기를 한곳에 모은다. 더 좁은 예외(NotLoggedIn)가 넓은 예외(PermissionDenied)보다 먼저 잡힌다
    (Starlette는 예외 종류의 MRO 순서로 처리기를 찾는다)."""

    @app.exception_handler(ApiError)
    def _api(_: Request, exc: ApiError):
        return _json(exc.code, exc.message, exc.detail)

    @app.exception_handler(NotLoggedIn)
    def _login(_: Request, exc: NotLoggedIn):
        return _json("UNAUTHORIZED", detail=getattr(exc, "detail", None))

    @app.exception_handler(PermissionDenied)
    def _denied(_: Request, __: PermissionDenied):
        return _json("FORBIDDEN")

    @app.exception_handler(RequestValidationError)
    def _invalid(_: Request, exc: RequestValidationError):
        errors = [{"where": ".".join(str(x) for x in e.get("loc", ())), "what": e.get("msg", "")} for e in exc.errors()]
        return _json("VALIDATION", detail={"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    def _http(_: Request, exc: StarletteHTTPException):
        code = CODE_OF_STATUS.get(exc.status_code, "VALIDATION" if 400 <= exc.status_code < 500 else "ASSISTANT_UNAVAILABLE")
        message = exc.detail if isinstance(exc.detail, str) and exc.detail and exc.status_code != 404 else None
        return _json(code, message, {"http_status": exc.status_code})
