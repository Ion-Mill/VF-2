"""영상용 로컬 DB 설정 파일 backend/.env.local-video 를 만든다 (git 제외: backend/.gitignore 의 .env.*).
비밀번호는 이 PC 로컬 DB 전용으로 무작위로 만든다. 비서 키(MOM_ASSISTANT_KEY)는 assistant/.env 와 같게 맞춘다. 값은 화면에 찍지 않는다."""
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # 11_automotive
out = ROOT / "backend" / ".env.local-video"


def read(p):
    d = {}
    for l in p.read_text(encoding="utf-8-sig").splitlines():
        s = l.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _, v = s.partition("="); d[k.strip()] = v.strip()
    return d


assistant = read(ROOT / "assistant" / ".env")
if out.exists():
    old = read(out)
    owner, app, ai = old["MOM_OWNER_DB_PASSWORD"], old["MOM_APP_DB_PASSWORD"], old["MOM_AI_DB_PASSWORD"]
    jwt, ingest = old["MOM_JWT_SECRET"], old["MOM_INGEST_KEY"]
else:
    owner, app, ai = (secrets.token_urlsafe(18) for _ in range(3))
    jwt, ingest = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
PORT = 5433
text = f"""# 영상용(video) 로컬 DB 설정 — 이 PC 전용, 저장소에 올리지 않음 (backend/.gitignore 의 .env.*). 2026-10-25
# DB = Docker 컨테이너 mom-video-db (localhost:{PORT}). 공용 Supabase 주소는 들어 있지 않다.
MOM_OWNER_DB_PASSWORD={owner}
MOM_APP_DB_PASSWORD={app}
MOM_AI_DB_PASSWORD={ai}
MOM_DATABASE_URL=postgresql+psycopg://mom_app:{app}@127.0.0.1:{PORT}/mom
MOM_READONLY_DATABASE_URL=postgresql+psycopg://mom_ai_ro:{ai}@127.0.0.1:{PORT}/mom
MOM_DB_POOL_SIZE=5
MOM_DB_MAX_OVERFLOW=5
MOM_JWT_SECRET={jwt}
MOM_JWT_MINUTES=720
MOM_INGEST_KEY={ingest}
MOM_ASSISTANT_KEY={assistant['MOM_ASSISTANT_KEY']}
MOM_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
# 시연 모드(영상용 로컬 DB 전용): 시계 조작·사건 버튼·DB 중계 받기
MOM_DEMO_MODE=true
MOM_SIM_SYNC=true
MOM_SIM_URL=http://127.0.0.1:8765
MOM_SIM_CONTROL_USERS=
MOM_RUN_WORKERS=true
MOM_CMM_INBOX_DIR=./cmm/inbox
MOM_CMM_PROCESSED_DIR=./cmm/processed
MOM_CMM_ERROR_DIR=./cmm/error
MOM_ASSISTANT_URL=http://127.0.0.1:8100
MOM_ASSISTANT_TIMEOUT_SECONDS=130
MOM_DEMO_PASSWORD=0000
"""
out.write_text(text, encoding="utf-8", newline="\n")
print("만듦:", out.name, "| 키", len([l for l in text.splitlines() if l and not l.startswith('#')]), "개 | 비서 키 일치:", read(out)["MOM_ASSISTANT_KEY"] == assistant["MOM_ASSISTANT_KEY"])
