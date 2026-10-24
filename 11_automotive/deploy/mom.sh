#!/usr/bin/env bash
# 서버에서 전체를 켜고 끄는 한 파일. 사용: ./mom.sh up | down | status | logs [서비스] | update | rollback <git 주소> | health
set -euo pipefail
cd "$(dirname "$0")"

need() {
  for f in .env backend.env assistant.env; do
    [[ -f "$f" ]] || { echo "없음: deploy/$f — $f.example 을 복사해서 서버에서 값을 채우세요 (배포_안내.md 4장)"; exit 1; }
  done
}

case "${1:-help}" in
  up)
    need
    git rev-parse HEAD > .last_ref 2>/dev/null || true
    docker compose up -d --build
    docker compose ps
    ;;
  down) docker compose down ;;
  status) docker compose ps ;;
  logs) shift; docker compose logs -f --tail=100 "$@" ;;
  health)
    # 서버 안쪽에서 시연 서버의 건강 확인(프로필·시연 시각) — 바깥 주소는 접속 비밀번호가 필요하니 브라우저로 본다
    docker compose exec -T sim python -c "import urllib.request,json; d=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/health')); print(json.dumps({'ok':d['ok'],'profile':d['profile']['name'],'clock_mode':d['profile']['clock_mode'],'sim_at':d['clock']['sim_at']}, ensure_ascii=False))"
    ;;
  update)
    need
    cp .last_ref .prev_ref 2>/dev/null || true
    git pull --ff-only
    "$0" up
    ;;
  rollback)
    ref="${2:-$(cat .prev_ref 2>/dev/null || true)}"
    [[ -n "$ref" ]] || { echo "되돌릴 git 주소(커밋 또는 태그)를 주세요: ./mom.sh rollback <주소>"; exit 1; }
    git checkout "$ref"
    "$0" up
    ;;
  *) sed -n '2,2p' "$0" ;;
esac
