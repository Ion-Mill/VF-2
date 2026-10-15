"""설정 (환경 변수). 비밀 값은 코드·저장소에 두지 않는다 (NFR-SEC-06) → .env.example 참고."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "postgresql+psycopg://mom:mom@localhost:5432/mom"
    # 비서 조회 도구용 읽기 전용 계정 (db/roles.sql 의 mom_ai_ro). 비우면 database_url을 읽기 전용 트랜잭션으로 쓴다
    readonly_database_url: str | None = None
    # 연결 수. Supabase Session pooler는 "역할+DB"마다 Pool Size(무료 기본 15)를 넘는 접속을 막는다 —
    # 여러 명이 각자 서버를 띄우면 그 합이 넘지 않게 줄인다 (.env.supabase.example: 4 + 2)
    db_pool_size: int = 10
    db_max_overflow: int = 10
    jwt_secret: str = ""
    jwt_minutes: int = 12 * 60
    # 시뮬레이터·AI 비서 서비스가 부르는 API의 키 (사람 로그인과 따로)
    ingest_key: str = ""
    assistant_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]  # 프론트(React) 개발 서버
    demo_mode: bool = False          # NFR-DATA-12 역할 바꿔 보기, 시연 시계 조작
    cmm_inbox_dir: str = "/data/cmm/inbox"
    cmm_processed_dir: str = "/data/cmm/processed"
    cmm_error_dir: str = "/data/cmm/error"
    cmm_poll_seconds: float = 2.0
    run_workers: bool = True         # 스케줄러·CMM 파일 감시를 이 프로세스에서 돌릴지 (여러 대면 한 곳만 true)
    cmm_no_result_minutes: int = 10  # [선택 필요: 기술 회의] 측정 시작 뒤 결과를 기다리는 시간 (측정 2.5분·강화 5.0분보다 길게)
    # AI 비서 서비스 (로컬 LLM, 백엔드 밖) 주소 — 비서 질문(/api/assistant/chat)·작업기록 메모 정리를 넘긴다.
    # 비우면 ASSISTANT_UNAVAILABLE (화면은 기본 문구). 넘기는 형식은 LLM 담당 팀원과 맞춘다 [선택 필요: 기술 회의]
    assistant_url: str | None = None
    assistant_timeout_seconds: float = 30.0
    # [제안] 출하 확정 전에 출하 줄의 로트 QR을 모두 찍어야 하는지 (2026-10-13 QR 가정). 기본은 끔 —
    # 라벨이 상하거나 QR 찍개가 없을 때 출하가 멈추지 않게. 켜면 안 찍은 로트가 있을 때 확정이 409 QR_NOT_CHECKED
    qr_ship_check_required: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        def env(name: str, default=None):
            return os.environ.get("MOM_" + name.upper(), default)

        data = {}
        for field in cls.model_fields:
            v = env(field)
            if v is None:
                continue
            if field == "cors_origins":
                data[field] = [x.strip() for x in v.split(",") if x.strip()]
            elif field in ("demo_mode", "run_workers", "qr_ship_check_required"):
                data[field] = v.lower() in ("1", "true", "yes", "on")
            else:
                data[field] = v
        return cls(**data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings.from_env()
    if not s.jwt_secret:
        raise RuntimeError("MOM_JWT_SECRET 환경 변수가 없음 (.env.example 참고)")
    return s
