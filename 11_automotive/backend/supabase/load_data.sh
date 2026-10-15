#!/usr/bin/env bash
# Supabase 프로젝트에 데이터 넣기 (스키마는 마이그레이션으로 먼저 — README 2단계).
# 쓰는 법 (Supabase 대시보드 → Connect → "Direct / Connection string" → 방식 Session pooler, IPv4에서도 됨):
#   PGHOST에는 접속 문자열 전체가 아니라 @ 뒤 ~ :5432 앞의 host만 넣는다 (예: aws-0-ap-northeast-2.pooler.supabase.com)
#   Windows: psql은 PostgreSQL 설치에서 Command Line Tools만 (export PATH="$PATH:/c/Program Files/PostgreSQL/18/bin")
#   다시 돌려도 된다 — 이미 넣은 생성기 데이터·센서는 건너뛴다 (scripts/load_all.sh)
#   export PGHOST=aws-0-ap-northeast-2.pooler.supabase.com PGPORT=5432 PGUSER=postgres.<project-ref> PGPASSWORD=… \
#          PGDATABASE=postgres PGSSLMODE=require
#   export GEN_DIR=../생성기 DOCS_DIR=..
#   export MOM_APP_DB_PASSWORD=… MOM_AI_DB_PASSWORD=… [MOM_DEMO_PASSWORD=…]
#   ./supabase/load_data.sh [--sensor] [--realtime] [--schema]
#   --schema : 스키마도 여기서 만든다 (마이그레이션을 안 쓸 때 — db/apply.sh)
# 하는 일: (스키마) → 계정(mom_app·mom_ai_ro) → 잠그기(lockdown.sql: anon·authenticated 권한 거둠 + RLS) → 데이터·문서 → 점검
set -euo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?Supabase 접속 값(PGHOST 등)을 먼저}"
SCHEMA=0; PASS=()
for a in "$@"; do case "$a" in --schema) SCHEMA=1 ;; *) PASS+=("$a") ;; esac; done
if [[ $SCHEMA == 1 ]]; then echo "== 스키마 (db/apply.sh)"; ./db/apply.sh; fi
if [[ "$(psql -X -tA -c "SELECT to_regclass('public.app_user') IS NOT NULL")" != "t" ]]; then
  echo "스키마가 없음 — 마이그레이션을 먼저 올리거나(supabase db push) --schema"; exit 2
fi
echo "== 계정"
psql -X -q -v ON_ERROR_STOP=1 -v app_password="${MOM_APP_DB_PASSWORD:?}" -v ai_password="${MOM_AI_DB_PASSWORD:?}" -f db/roles.sql
echo "== 잠그기 (RLS·anon 권한)"
psql -X -q -v ON_ERROR_STOP=1 -f supabase/sql/lockdown.sql
echo "== 데이터·문서"
MOM_ROLES_DONE=1 MOM_APP_DB_PASSWORD= MOM_AI_DB_PASSWORD= ./scripts/load_all.sh --keep ${PASS[@]+"${PASS[@]}"}
echo "완료 — API 서버 .env: MOM_DATABASE_URL=postgresql+psycopg://mom_app.<project-ref>:<비밀번호>@<pooler 주소>:5432/postgres?sslmode=require"
