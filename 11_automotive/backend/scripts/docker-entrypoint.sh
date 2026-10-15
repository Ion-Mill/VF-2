#!/usr/bin/env bash
# api 컨테이너 시작: DB가 비어 있으면 처음 한 번만 채우고 서버를 띄운다.
#   MOM_LOAD_DATA=1 (기본): 생성기 데이터(기준 정보 + 9월) + 사내 문서 조각 — scripts/load_all.sh
#                           (/data/automotive = VF-2/11_automotive 를 읽기 전용으로 붙임, docker-compose.yml)
#     MOM_LOAD_SENSOR=1   : 센서 약 98만 행도 (약 15초, DB +약 120MB)
#     MOM_LOAD_REALTIME=1 : 10/1 리허설 기록도 (SIM-03을 누르면 사라짐)
#     MOM_DEMO_PASSWORD   : U01~U12 시연 비밀번호 (개발·시연 전용)
#   MOM_LOAD_DATA=0       : 스키마만 (+ MOM_DEV_SEED=1 이면 작은 개발 목업 — 시험용)
# 스키마 주인 계정 접속: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE
# 앱 계정 접속(mom_app·mom_ai_ro): MOM_DATABASE_URL, MOM_READONLY_DATABASE_URL
set -euo pipefail
cd /srv
until pg_isready -q; do echo "DB 기다리는 중..."; sleep 1; done
if [[ "$(psql -X -tA -c "SELECT to_regclass('public.app_user') IS NOT NULL")" != "t" ]]; then
  if [[ "${MOM_LOAD_DATA:-1}" == "1" ]]; then
    AUTO=${MOM_AUTOMOTIVE_DIR:-/data/automotive}
    if [[ ! -d "$AUTO/생성기/masters" ]]; then
      echo "생성기 폴더가 없음: $AUTO/생성기 — docker-compose.yml 의 AUTOMOTIVE_DIR 확인 (또는 MOM_LOAD_DATA=0)"; exit 1
    fi
    echo "DB가 비어 있음 → 스키마 + 생성기 데이터 + 사내 문서"
    GEN_DIR="$AUTO/생성기" DOCS_DIR="$AUTO" ./scripts/load_all.sh \
      $([[ "${MOM_LOAD_SENSOR:-0}" == "1" ]] && echo --sensor) $([[ "${MOM_LOAD_REALTIME:-0}" == "1" ]] && echo --realtime)
  else
    echo "DB가 비어 있음 → 스키마만"
    if [[ "${MOM_DEV_SEED:-0}" == "1" ]]; then ./db/apply.sh --dev; else ./db/apply.sh; fi
    psql -X -q -v ON_ERROR_STOP=1 -v app_password="${MOM_APP_DB_PASSWORD:?}" -v ai_password="${MOM_AI_DB_PASSWORD:?}" \
         -f db/roles.sql
  fi
fi
mkdir -p "${MOM_CMM_INBOX_DIR:-/data/cmm/inbox}" "${MOM_CMM_PROCESSED_DIR:-/data/cmm/processed}" "${MOM_CMM_ERROR_DIR:-/data/cmm/error}"
exec "$@"
