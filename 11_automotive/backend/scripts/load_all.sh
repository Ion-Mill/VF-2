#!/usr/bin/env bash
# 빈 DB 하나에 스키마 → 계정 권한 → 생성기 데이터(기준 정보 + 9월) → 사내 문서 조각 → (개발·시연 비밀번호) → 점검 → (센서)
# 쓰는 법 (Git Bash·Linux·Docker 안 모두):
#   PGHOST=localhost PGPORT=5432 PGUSER=mom_owner PGPASSWORD=… PGDATABASE=mom \
#   GEN_DIR=../생성기 DOCS_DIR=.. \
#   MOM_APP_DB_PASSWORD=… MOM_AI_DB_PASSWORD=… [MOM_DEMO_PASSWORD=…] ./scripts/load_all.sh [--sensor] [--realtime] [--keep]
#   --sensor   센서 CSV(9월 약 98만 행, 약 15초)도 넣음 — 기본은 뺌 (Supabase 무료 한도를 보고 정함)
#   --realtime 10/1 리허설 기록(out_realtime)도 붙임 (SIM-03을 누르면 사라짐)
#   --keep     DB에 이미 표가 있어도 스키마를 다시 만들지 않고 데이터만 넣음 (이미 넣은 단계는 아래처럼 건너뜀)
#   MOM_DEMO_PASSWORD 가 있으면 U01~U12 비밀번호를 그 값으로 (개발·시연 전용, 운영 금지)
#   PYTHON=python  (안 주면 python3 → python 순으로 실제로 도는 것을 고름 — Windows의 python3 가짜 실행 파일 피함)
# 다시 돌려도 된다: 생성기 데이터가 이미 있으면(dataset_info.loaded_at) 3단계, 센서가 이미 있으면 7단계를 건너뛴다.
#   사내 문서(4)는 문서마다 지우고 다시 넣고, 비밀번호(5)는 빈 사용자에게만 넣으므로 그대로 돈다.
#   단 4단계가 시연 기준점(SIM-03)을 다시 만드므로 시연 도중에는 다시 돌리지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "${PYTHON:-}" ]]; then PY=$PYTHON
elif python3 -c 'import sys' >/dev/null 2>&1; then PY=python3
else PY=python; fi
export PYTHONUTF8=1 PGCLIENTENCODING=${PGCLIENTENCODING:-UTF8}   # Windows 콘솔 코드 페이지(CP949)와 섞이지 않게
: "${GEN_DIR:?GEN_DIR = 생성기 폴더 (masters/ out/)}"
: "${DOCS_DIR:?DOCS_DIR = 11_automotive 폴더 (가상사내문서/)}"
# 2026-10-24: 프로필 폴더. 최종용 GEN_OUT_DIR=out_final GEN_RT_DIR=out_realtime_final, 영상용 out_video·out_realtime_video.
#   2026-10-25: 안 주면 최종용(10월 데이터 — 팀 결정으로 9월 out/은 더 쓰지 않음)
OUT_DIR_OPT="--out-dir ${GEN_OUT_DIR:-out_final} --rt-dir ${GEN_RT_DIR:-out_realtime_final}"
SENSOR=0; REALTIME=0; KEEP=0
for a in "$@"; do
  case "$a" in --sensor) SENSOR=1 ;; --realtime) REALTIME=1 ;; --keep) KEEP=1 ;; *) echo "모르는 옵션 $a"; exit 2 ;; esac
done
PSQL_CMD="psql${PGHOST:+ -h $PGHOST}${PGPORT:+ -p $PGPORT}${PGUSER:+ -U $PGUSER} -d ${PGDATABASE:?PGDATABASE 필요}"

has_schema=$(psql -X -tA -c "SELECT to_regclass('public.app_user') IS NOT NULL")
if [[ "$has_schema" == "t" && $KEEP == 0 ]]; then
  echo "이미 스키마가 있음 — 빈 DB에서 돌리거나 --keep (데이터만)"; exit 2
fi
if [[ "$has_schema" != "t" ]]; then
  echo "== 1. 스키마·시드"; ./db/apply.sh
fi
if [[ -n "${MOM_APP_DB_PASSWORD:-}" && -n "${MOM_AI_DB_PASSWORD:-}" ]]; then
  echo "== 2. 앱·비서 계정 권한"
  psql -X -q -v ON_ERROR_STOP=1 -v app_password="$MOM_APP_DB_PASSWORD" -v ai_password="$MOM_AI_DB_PASSWORD" -f db/roles.sql
else
  if [[ -n "${MOM_ROLES_DONE:-}" ]]; then echo "== 2. (앞에서 함) 앱·비서 계정 권한"
  else echo "== 2. (건너뜀) MOM_APP_DB_PASSWORD·MOM_AI_DB_PASSWORD 가 없어 계정 권한을 걸지 않음"; fi
fi
if [[ "$(psql -X -tA -c "SELECT loaded_at IS NOT NULL FROM dataset_info WHERE id = 1")" == "t" ]]; then
  echo "== 3. (건너뜀) 생성기 데이터가 이미 있음 ($(psql -X -tA -c "SELECT loaded_at FROM dataset_info WHERE id = 1")) — 처음부터 다시 하려면 빈 DB에서"
else
  echo "== 3. 생성기 데이터 (기준 정보 + 9월$([[ $REALTIME == 1 ]] && echo ' + 10/1 리허설'))"
  "$PY" tools/load_generated.py "$GEN_DIR" --psql "$PSQL_CMD" $OUT_DIR_OPT $([[ $REALTIME == 1 ]] && echo --realtime)
fi
echo "== 4. 사내 문서 조각"
"$PY" tools/load_docs.py "$DOCS_DIR" --psql "$PSQL_CMD"
if [[ -n "${MOM_DEMO_PASSWORD:-}" ]]; then
  echo "== 5. 개발·시연 비밀번호 (U01~U12)"
  "$PY" tools/gen_dev_users.py --update "$MOM_DEMO_PASSWORD" | psql -X -q -v ON_ERROR_STOP=1
fi
echo "== 6. 적재 점검"
psql -X -q -v ON_ERROR_STOP=1 -f db/checks/validate_loaded_data.sql | tee /tmp/mom_validate.txt
if grep -q "확인 필요" /tmp/mom_validate.txt; then echo "점검에 '확인 필요'가 있음"; exit 3; fi
if [[ $SENSOR == 1 && "$(psql -X -tA -c "SELECT EXISTS (SELECT 1 FROM sensor_sample)")" == "t" ]]; then
  echo "== 7. (건너뜀) 센서가 이미 있음"
elif [[ $SENSOR == 1 ]]; then
  echo "== 7. 센서 (따로)"
  "$PY" tools/load_generated.py "$GEN_DIR" --psql "$PSQL_CMD" --sensor-only $OUT_DIR_OPT $([[ $REALTIME == 1 ]] && echo --realtime)
fi
# 한글은 SQL 밖에서 찍는다 — Windows psql은 명령줄 인자를 시스템 글자(CP949)로 넘겨 서버가 UTF8 오류로 거절한다 (2026-10-25)
echo "DB 크기 $(psql -X -tA -c "SELECT pg_size_pretty(pg_database_size(current_database()))")"
echo "완료"
