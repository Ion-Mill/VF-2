"""음성 입구 — 채팅 마이크 버튼의 소리를 글자로 바꾼다 (`POST /transcribe`, `GET /voice/status`, 2026-10-20).

chat_service 의 서비스 키(X-Service-Key)가 그대로 걸린다(`app.include_router(..., dependencies=[Depends(service_key)])`). 호출자는 백엔드(8020)다 —
브라우저는 서비스 키를 가질 수 없어서 백엔드가 로그인 확인 뒤 소리를 그대로 넘겨 준다.
  · 요청 본문 = 녹음된 소리 원본 바이트(webm/opus·mp4·wav). 업로드 패키지(python-multipart) 없이 바이트로 받는다.
  · 응답 = {"text", "reason", "seconds", "ms"}. text 가 비어 있으면 reason(too_short·no_speech·hallucination·repeated·hint_echo)을 본다.
  · 실패는 VoiceError → chat_service 가 {"code","message","detail"} JSON 으로 바꾼다 (404 꺼짐·400 소리 이상·413 큼·429 바쁨·503 시간 초과/실패).
  · 스위치 ASSISTANT_VOICE=0(기본)이면 404 — 기존 동작은 바뀌지 않는다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from backend.voice import pipeline as V
from backend.voice.settings import settings

router = APIRouter()


@asynccontextmanager
async def lifespan(_app):
    """서버를 켤 때 스위치가 켜져 있으면 모델을 미리 올린다 (기다리지 않는다)."""
    V.preload()
    yield


@router.get("/voice/status")
def voice_status() -> dict:
    return V.status()


@router.post("/transcribe")
async def transcribe(request: Request) -> dict:
    cap = settings().max_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cap:
        raise V._err("AUDIO_TOO_LARGE")
    buf = bytearray()
    async for chunk in request.stream():          # 머리말이 거짓이거나 없어도 상한을 넘으면 읽기를 멈춘다
        buf += chunk
        if len(buf) > cap:
            raise V._err("AUDIO_TOO_LARGE")
    return await run_in_threadpool(V.transcribe, bytes(buf))
