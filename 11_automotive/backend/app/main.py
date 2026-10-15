"""MOM 백엔드 진입점: uvicorn app.main:app — 주소·오류 코드는 11_automotive/API명세서_v1.md (docs/03_API_명세.md 6장)

  /api/auth·me·demo        로그인 (AUTH)      /api/line·replay·production·kpi   3D 라인 뷰·생산 (LINE)
  /api/notifications       알림 (NTF)         /api/assistant/briefing·chat       비서 (AST)
  /api/maint/...           정비 (MNT·PM)      /api/reports·documents·internal-docs  보고서·문서 (RPT·DOC·DOCS)
  /api/lots                로트 (LOT)         /api/inspection·quality            품질 (QLT)
  /api/inventory·shipments·raw-lots·tools  재고·출하·공구 (INV·TOOL)
  /api/settings            설정 (SET)         /api/sim                           시연 (SIM)
  /api/stream/events       실시간 (STR)
  명세서 밖 (서버끼리): /api/ingest (설비 데이터, 서비스 키), /api/assistant/tools·drafts (AI 비서 서비스, 서비스 키)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import errors
from .audit import log_access
from .config import get_settings
from .db import Db, engine
from .domain import synthetic
from .domain.tokens import decode_token
from .realtime import broadcaster
from .routers import (alarms, assistant, auth, documents, ingest, inventory, line, maintenance, master, notifications,
                      production, qr, quality, stream)
from .workers import cmm_watcher, scheduler

log = logging.getLogger("mom")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    broadcaster.start()
    tasks: list[asyncio.Task] = []
    if s.run_workers:
        tasks = [asyncio.create_task(scheduler.run_forever(), name="mom-scheduler"),
                 asyncio.create_task(cmm_watcher.run_forever(), name="mom-cmm-watcher")]
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await broadcaster.stop()
    engine().dispose()


app = FastAPI(title="MOM 백엔드 — 자동차 부품 절삭가공 라인 운영 관리", version="0.1.0", lifespan=lifespan)
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth, master, line, alarms, notifications, stream, production, maintenance, inventory, qr, quality, documents,
          assistant, ingest):
    app.include_router(r.router)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
NOT_LOGGED = ("/api/auth/", "/api/demo/", "/api/ingest/", "/api/assistant/")   # 로그인·서비스 키·비서 질문은 따로 남긴다


@app.middleware("http")
async def access_log(request: Request, call_next):
    """사람이 바꾼 요청은 접근 기록에 남긴다 (NFR-SEC-04). 조회는 남기지 않는다 [선택 필요: 기술 회의 — 조회 기록 범위]"""
    response = await call_next(request)
    path = request.url.path
    if request.method in WRITE_METHODS and path.startswith("/api/") and not path.startswith(NOT_LOGGED):
        user_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            try:
                user_id = decode_token(auth_header[7:], get_settings().jwt_secret)["sub"]
            except jwt.PyJWTError:
                pass
        await run_in_threadpool(log_access, user_id, "API", request.method, path[:200], response.status_code,
                                request.client.host if request.client else None, None)
    return response


_synthetic = {"at": -1e9, "flag": True}


def synthetic_flag() -> bool:
    """dataset_info.is_virtual (60초 기억). 읽지 못하면 앞 값 — 처음 값은 가상(true)"""
    if time.monotonic() - _synthetic["at"] > 60:
        try:
            with engine().connect() as conn:
                v = Db(conn).scalar("common.is_synthetic")
            _synthetic.update(at=time.monotonic(), flag=True if v is None else bool(v))
        except Exception:
            log.exception("가상 데이터 표시 값을 읽지 못함")
    return _synthetic["flag"]


@app.middleware("http")
async def synthetic_marker(request: Request, call_next):
    """모든 운영 데이터 응답에 is_synthetic (API명세서 1장, NFR-DATA-08) — 객체는 맨 위, 목록은 줄마다 (app/domain/synthetic.py).
    머리글 X-Synthetic-Data 도 붙인다. 오류 응답·로그인·실시간·서버끼리 API는 그대로"""
    response = await call_next(request)
    if (not synthetic.applies(request.url.path) or response.status_code >= 300
            or not response.headers.get("content-type", "").startswith("application/json")):
        return response
    raw = b"".join([chunk async for chunk in response.body_iterator])
    flag = await run_in_threadpool(synthetic_flag)
    headers = {k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "content-type")}
    headers["X-Synthetic-Data"] = "true" if flag else "false"
    return JSONResponse(synthetic.mark(json.loads(raw), flag), status_code=response.status_code, headers=headers)


@app.get("/api/health", tags=["상태"])
def health():
    with engine().connect() as conn:
        conn.exec_driver_sql("SELECT 1")
    return {"ok": True}
