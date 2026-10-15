#!/usr/bin/env bash
# db/ 의 스키마·함수·뷰·기준 시드를 Supabase 마이그레이션 파일 하나로 묶는다 (db/apply.sh 와 같은 순서, --dev 목업은 빼고).
# 쓰는 법: ./supabase/build_migration.sh  → supabase/migrations/20261014000000_mom_schema.sql
#   Supabase CLI: supabase link --project-ref <ref> && supabase db push
#   또는 SQL 편집기·psql 로 그 파일을 그대로 실행
# 스키마를 고치면 다시 돌려 파일을 새로 만든다 (이미 올린 프로젝트에는 바뀐 부분만 새 마이그레이션으로 — README)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=supabase/migrations/20261014000000_mom_schema.sql
{
  echo "-- 생성: supabase/build_migration.sh — db/schema → functions → views → seed (db/apply.sh 순서). 손으로 고치지 않는다"
  echo "-- 만든 때: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "SET client_min_messages = warning;"
  for d in schema functions views seed; do
    for f in db/$d/*.sql; do
      echo; echo "-- ===================== $f ====================="
      sed 's/\r$//' "$f"
    done
  done
} > "$OUT"
echo "만듦: $OUT ($(wc -l < "$OUT")줄)"
