"""오류 → HTTP 응답 (API명세서 1장).

형식: {"code": "...", "message": "쉬운 한국어 문장", "detail": {...}}. 코드는 명세서의 7개만 쓴다:
  UNAUTHORIZED 401 · FORBIDDEN 403 · NOT_FOUND 404 · VALIDATION 422 · INVALID_STATE 409 · CONFLICT_VERSION 409 ·
  ASSISTANT_UNAVAILABLE 503
DB가 막은 업무 규칙(CHECK·트리거·함수의 RAISE)은 INVALID_STATE로, DB 글(R-번호 포함)을 그대로 보인다.
더 자세한 갈래는 detail.reason (예: NO_CHANGE, RULE_VIOLATION, DUPLICATE)과 detail.sqlstate에 남긴다.
예상 못 한 서버 오류만 500 INTERNAL_ERROR (명세서 밖 — 내용은 싣지 않음).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
VALIDATION = "VALIDATION"
INVALID_STATE = "INVALID_STATE"
CONFLICT_VERSION = "CONFLICT_VERSION"
ASSISTANT_UNAVAILABLE = "ASSISTANT_UNAVAILABLE"
CODES = (UNAUTHORIZED, FORBIDDEN, NOT_FOUND, VALIDATION, INVALID_STATE, CONFLICT_VERSION, ASSISTANT_UNAVAILABLE)

# PostgreSQL SQLSTATE → (HTTP 상태, 코드, detail.reason)
SQLSTATE_MAP = {
    "23514": (409, INVALID_STATE, "RULE_VIOLATION"),   # check_violation (CHECK, 트리거·함수의 업무 규칙)
    "23505": (409, INVALID_STATE, "DUPLICATE"),        # unique_violation
    "23P01": (409, INVALID_STATE, "OVERLAP"),          # exclusion_violation (상태 구간 겹침 R-04)
    "23503": (404, NOT_FOUND, "NOT_FOUND_REF"),        # foreign_key_violation / 없는 대상 (함수의 "… 없음")
    "23502": (422, VALIDATION, "REQUIRED"),            # not_null_violation
    "22023": (422, VALIDATION, "INVALID_VALUE"),
    "22P02": (422, VALIDATION, "INVALID_VALUE"),
    "22007": (422, VALIDATION, "INVALID_VALUE"),
    "42501": (403, FORBIDDEN, "NOT_ALLOWED"),          # 추가만 하는 표 고치기 등
    "25006": (403, FORBIDDEN, "READ_ONLY"),            # 읽기 전용 트랜잭션에서 쓰기 (비서 조회 도구)
}
HTTP_STATUS_CODE = {401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND, 405: NOT_FOUND, 409: INVALID_STATE,
                    422: VALIDATION, 503: ASSISTANT_UNAVAILABLE}


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.detail = status, code, message, detail or {}


def not_found(what: str) -> AppError:
    return AppError(404, NOT_FOUND, f"{what} 없음")


def validation(message: str, **detail: Any) -> AppError:
    return AppError(422, VALIDATION, message, detail)


def invalid_state(message: str, **detail: Any) -> AppError:
    return AppError(409, INVALID_STATE, message, detail)


def body(code: str, message: str, detail: dict | None = None) -> dict:
    return {"code": code, "message": message, "detail": detail or {}}


def install(app: "FastAPI") -> None:
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from sqlalchemy.exc import DBAPIError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(AppError)
    async def _app_error(_req: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content=body(exc.code, exc.message, exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, exc: RequestValidationError):
        errs = [{"loc": list(e.get("loc", ())), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=body(VALIDATION, "보낸 값이 틀리거나 빠짐", {"errors": errs}))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req: Request, exc: StarletteHTTPException):
        code = HTTP_STATUS_CODE.get(exc.status_code, NOT_FOUND if exc.status_code < 500 else "INTERNAL_ERROR")
        return JSONResponse(status_code=exc.status_code, content=body(code, str(exc.detail)))

    @app.exception_handler(DBAPIError)
    async def _db_error(_req: Request, exc: DBAPIError):
        orig = getattr(exc, "orig", None)
        state = getattr(orig, "sqlstate", None)
        status, code, reason = SQLSTATE_MAP.get(state or "", (500, "INTERNAL_ERROR", "DB_ERROR"))
        diag = getattr(orig, "diag", None)
        message = getattr(diag, "message_primary", None) or str(orig or exc).splitlines()[0]
        detail = {"reason": reason, "sqlstate": state, "constraint": getattr(diag, "constraint_name", None)}
        if status == 500:
            message = "DB 오류"   # 내부 내용은 응답에 싣지 않는다
        return JSONResponse(status_code=status, content=body(code, message, detail))
