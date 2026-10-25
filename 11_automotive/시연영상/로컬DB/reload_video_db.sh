#!/usr/bin/env bash
# (2026-10-25 main의 적재 도구가 manifest profile로 날짜를 읽는다 — --live-start 불필요) 영상용 로컬 DB를 새로 만들고 과거 기록(out_video)만 넣은 뒤, 시연 시계를 10/24 09:00에 멈춰 기준점을 다시 찍는다.
set -euo pipefail
AUTO="$(cd "$(dirname "$0")/../.." && pwd -W 2>/dev/null || pwd)"      # 11_automotive (Windows 경로)
cd "$AUTO/backend"
set -a; . <(grep -E '^MOM_(OWNER|APP|AI)_DB_PASSWORD=' .env.local-video); set +a
export MSYS_NO_PATHCONV=1
docker run -d --name mom-video-db --network mom-video-net -e POSTGRES_DB=mom -e POSTGRES_USER=mom_owner \
  -e "POSTGRES_PASSWORD=$MOM_OWNER_DB_PASSWORD" -e TZ=Asia/Seoul -e PGTZ=Asia/Seoul \
  -p 127.0.0.1:5433:5432 -v mom_video_pgdata:/var/lib/postgresql/data postgres:16 >/dev/null
until docker exec mom-video-db pg_isready -q -U mom_owner -d mom; do sleep 2; done
sleep 3
docker run --rm --network mom-video-net \
  -e PGHOST=mom-video-db -e PGUSER=mom_owner -e "PGPASSWORD=$MOM_OWNER_DB_PASSWORD" -e PGDATABASE=mom \
  -e "MOM_APP_DB_PASSWORD=$MOM_APP_DB_PASSWORD" -e "MOM_AI_DB_PASSWORD=$MOM_AI_DB_PASSWORD" -e MOM_DEMO_PASSWORD=0000 \
  -e MOM_LOAD_DATA=1 -e MOM_LOAD_REALTIME=1 -e MOM_LOAD_SENSOR=1 -e GEN_OUT_DIR=out_video -e GEN_RT_DIR=out_realtime_video \
  -e MOM_AUTOMOTIVE_DIR=/data/automotive \
  -v "$AUTO:/data/automotive:ro" \
  mom-backend-loader true 2>&1 | tail -n 6
docker exec -e PGPASSWORD="$MOM_OWNER_DB_PASSWORD" mom-video-db psql -X -q -U mom_owner -d mom -c   "SELECT app_now() AS 시계, (SELECT sim_at FROM demo_snapshot.meta WHERE id=1) AS 기준점시각, (SELECT period_from||' ~ '||period_to FROM dataset_info WHERE id=1) AS 데이터기간, (SELECT count(*) FROM sensor_sample) AS 센서행"
echo "reload done"
