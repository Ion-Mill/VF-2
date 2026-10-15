#!/usr/bin/env bash
# DB 시험: 새 DB를 만들고 스키마 + 개발 데이터 + 계정 권한을 넣은 뒤 tests/*.sql 을 두 번 돌린다.
#   1) 스키마 주인 계정으로   2) 앱 계정(mom_app, 최소 권한)으로 — 앱 권한만으로 업무 함수가 다 도는지
# 시험 파일은 BEGIN ... ROLLBACK 이라 서로 영향을 주지 않는다.
# 쓰는 법: PGHOST=... PGPORT=... ./db/tests/run_tests.sh   (DB 이름 mom_test를 새로 만듦)
set -euo pipefail
cd "$(dirname "$0")/.."
DB=${TEST_DB:-mom_test}
psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB"
PGDATABASE=$DB ./apply.sh --dev > /dev/null
# DB 계정(mom_app·mom_ai_ro) 권한도 시험 DB에 건다 — 비밀번호는 시험용 (계정은 클러스터 공용)
PGDATABASE=$DB psql -X -q -v ON_ERROR_STOP=1 -v app_password=test-only -v ai_password=test-only -f roles.sql > /dev/null
pass=0; fail=0
run_all() {   # $1 = 표시, $2 = PGOPTIONS, $3.. = 시험 파일
  local label=$1 opts=$2; shift 2
  for f in "$@"; do
    if out=$(PGOPTIONS="$opts" PGDATABASE=$DB psql -X -q -v ON_ERROR_STOP=1 -f "$f" 2>&1); then
      n=$(grep -c "NOTICE:  ok - " <<< "$out" || true)
      echo "PASS $label $f ($n checks)"; pass=$((pass+1))
    else
      echo "FAIL $label $f"; echo "$out" | grep -E "ERROR|FAIL" | head -5; fail=$((fail+1))
    fi
  done
}
run_all "[주인]" "" tests/[0-9]*.sql
# 시험 도우미(t 스키마)를 앱 계정도 쓰게 한 뒤 같은 시험을 앱 계정으로
PGDATABASE=$DB psql -X -q -c "GRANT USAGE ON SCHEMA t TO mom_app; GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA t TO mom_app;"
run_all "[mom_app]" "-c role=mom_app" tests/[1-9]*.sql    # 00_helpers(스키마 만들기)는 주인만
echo "files: pass=$pass fail=$fail"
[[ $fail -eq 0 ]]
