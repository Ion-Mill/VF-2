#!/usr/bin/env bash
# DB 만들기: 스키마 → 함수·트리거 → 뷰 → 기준 시드 (→ --dev 이면 개발용 기준 정보·사용자·목업 데이터)
# 쓰는 법:  PGHOST=... PGUSER=... PGDATABASE=mom ./db/apply.sh [--dev]
#   (docker compose에서는 db/ 를 /docker-entrypoint-initdb.d 로 쓰지 않고, api 컨테이너가 이 스크립트를 부른다)
set -euo pipefail
cd "$(dirname "$0")"
PSQL=(psql -X -q -v ON_ERROR_STOP=1)
run() { echo "  - $1"; "${PSQL[@]}" -f "$1"; }

echo "[1/4] schema";    for f in schema/*.sql;    do run "$f"; done
echo "[2/4] functions"; for f in functions/*.sql; do run "$f"; done
echo "[3/4] views";     for f in views/*.sql;     do run "$f"; done
echo "[4/4] seed";      for f in seed/*.sql;      do run "$f"; done
if [[ "${1:-}" == "--dev" ]]; then
  echo "[dev] 개발용 기준 정보·사용자·목업 데이터"
  for f in dev/*.sql; do run "$f"; done
fi
echo "완료"
