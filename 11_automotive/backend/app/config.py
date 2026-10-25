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
    # 시연 서버 DB 중계 받기 (2026-10-23, "DB 1개 = 공장 1개"): /api/ingest/sync·reset·clock만 연다 (시연 모드의 다른 문은 안 엶).
    #   켜면 시뮬레이터 10/1 기록이 이 DB에 쌓이고, 시연 서버 [처음으로]가 이 DB를 시연 기준점으로 되돌린다 — 모두가 같이 봄
    sim_sync: bool = False
    # 시뮬레이터(시연 서버) 주소 (2026-10-23, 화면 → 백엔드 전환 C2): 있으면 시연 시계·사건 버튼·처음으로와 시뮬레이터가 주인인 기록
    #   (로트 보류·해제, 공구 교체, 예방 정비 시작·끝, 설비 복귀)을 백엔드가 권한 확인 뒤 시뮬레이터에 넘긴다 (app/services/sim_link.py)
    sim_url: str | None = None
    # 시연 조작(시계·사건 버튼·[처음으로]·[상황 일으키기])을 할 수 있는 사용자 (2026-10-24, 여러 명이 같은 공장을 볼 때).
    #   비우면 로그인한 누구나 (지금까지와 같음). 배포처럼 여러 명이 쓰면 진행자만: 예 MOM_SIM_CONTROL_USERS=U12
    sim_control_users: list[str] = []
    # 최종용(실제 시각) 시연 서버의 [처음으로]는 발표자 키가 있어야 한다 (2026-10-25, 1024 팀원별 요청 4장). 화면이 보낸
    #   X-Presenter-Key를 그대로 넘기고, 화면이 안 보냈으면 이 값(시연 서버 MOM_PRESENTER_KEY와 같게)을 넘긴다. 비우면 화면 값만
    presenter_key: str = ""
    # 화면이 1초마다 부르는 /api/line/twin?full=true 결과를 이만큼 서버에 두고 같이 쓴다 (2026-10-24, 여러 명 접속).
    #   한 번 계산에 쿼리 19개 — 접속자 수와 관계없이 1초에 한 번만 DB를 읽는다. 0이면 끔
    twin_cache_seconds: float = 1.0
    # 스케줄러가 시간 규칙·교대 끝 보고서 초안을 보는 간격(진짜 초). 시연 시계 ×60이면 60초 = 시연 1시간이라 5초쯤으로 줄인다
    scheduler_seconds: float = 60.0
    cmm_inbox_dir: str = "/data/cmm/inbox"
    cmm_processed_dir: str = "/data/cmm/processed"
    cmm_error_dir: str = "/data/cmm/error"
    cmm_poll_seconds: float = 2.0
    run_workers: bool = True         # 스케줄러·CMM 파일 감시를 이 프로세스에서 돌릴지 (여러 대면 한 곳만 true)
    cmm_no_result_minutes: int = 10  # [선택 필요: 기술 회의] 측정 시작 뒤 결과를 기다리는 시간 (측정 2.5분·강화 5.0분보다 길게)
    # AI 비서 서비스 (로컬 LLM, 백엔드 밖) 주소 — 비서 질문(/api/assistant/chat)·작업기록 메모 정리를 넘긴다.
    # 비우면 ASSISTANT_UNAVAILABLE (화면은 기본 문구). 넘기는 형식은 LLM 담당 팀원과 맞춘다 [선택 필요: 기술 회의]
    assistant_url: str | None = None
    assistant_timeout_seconds: float = 130.0      # 화면 assistantApi.ts가 130초 + 여유로 기다린다 (2026-10-20, 전 30초)
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
            if field in ("cors_origins", "sim_control_users"):
                data[field] = [x.strip() for x in v.split(",") if x.strip()]
            elif field in ("demo_mode", "sim_sync", "run_workers", "qr_ship_check_required"):
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
