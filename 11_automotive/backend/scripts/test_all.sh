#!/usr/bin/env bash
# 전체 시험: DB 시험 → 쿼리 PREPARE → 파이썬 시험 (DB 없이 + DB로)
# 쓰는 법: PGHOST=... PGPORT=... [PGUSER=...] ./scripts/test_all.sh
#   만드는 DB: mom_test (지우고 새로), mom_svc_*·mom_router_test (시험 중에만)
set -euo pipefail
cd "$(dirname "$0")/.."
PSQL_BASE="psql ${PGHOST:+-h $PGHOST} ${PGPORT:+-p $PGPORT} ${PGUSER:+-U $PGUSER}"

echo "== 1. DB 시험 (db/tests)"
./db/tests/run_tests.sh

echo "== 2. 이름 붙은 쿼리 PREPARE (app/sql)"
python3 tools/check_queries.py --psql "$PSQL_BASE -d mom_test"

echo "== 3. 파이썬 시험 (DB 없이: CSV 읽기·QR 읽기·비밀번호·토큰·권한·역할×API 기대표·도구·쿼리 호출 정적 확인·직원 관리 규칙)"
python3 -m unittest tests.test_cmm_csv tests.test_domain tests.test_qr tests.test_static_calls tests.test_role_matrix tests.test_staff

echo "== 4. 파이썬 시험 (DB로: 서비스·라우터 처리기 흐름)"
MOM_TEST_PSQL="$PSQL_BASE" python3 -m unittest tests.test_services_db tests.test_routers_db
echo "모두 통과"
