영상용(video) 로컬 DB 구성 (2026-10-25) — 이 PC의 Docker에만 만들어지는 DB. 전체 순서는 시연영상/팀원_안내_영상촬영.md
- DB: Docker 컨테이너 mom-video-db (localhost:5433, 볼륨 mom_video_pgdata, 네트워크 mom-video-net). 설정 = backend\.env.local-video
- 켜기: powershell -File 시연영상\로컬DB\start_video_local.ps1   (백엔드 8000·비서 8100·시연 서버 8765·화면 3000)
- 끄기: powershell -File 시연영상\로컬DB\stop_video_local.ps1   (DB 컨테이너는 그대로)
- DB 새로 만들기: bash 시연영상\로컬DB\reload_video_db.sh (과거 기록 out_video 적재 + 시계 10/24 09:00 + 기준점) 그 다음 python add_live_days.py (10/24 work_day·shift 넣고 기준점 다시)
- 처음 한 번: python make_local_env.py (.env.local-video 만들기) → docker network create mom-video-net → docker volume create mom_video_pgdata → docker build -t mom-backend-loader backend
