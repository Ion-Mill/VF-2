# DB 덤프 (2026-10-14)

생성기 9월 기록(seed 20260901, 5단계 ③) + 기준 정보 22개 + 사내 문서 조각 209개 + 10/1 근무일·교대 + 시연 기준점(10/1 08:00)을
넣은 DB를 그대로 뜬 것이다. 적재 점검 20개 0건. 만든 명령: `scripts/load_all.sh --sensor` → `pg_dump -Fc` (PostgreSQL 16).

| 파일 | 내용 | 크기 | sha256 |
|---|---|---|---|
| `mom_main_20261014.dump` | 스키마 전체 + 센서를 뺀 모든 데이터 + `demo_snapshot` | 1.9MB | `63eda506ef2e1ca99e21e46d23da7511cecee723a93f975e4574cfc361ed66a4` |
| `mom_sensor_20261014.dump` | 센서 값만 (5초 400,092 + 1분 평균 578,179행) | 4.0MB | `c842d84f97d3e166c5d594d0ad10b5cb4db81240d7acdc5061788f89b0dbcf46` |

비밀번호 해시·DB 계정(mom_app·mom_ai_ro)은 들어 있지 않다 — 넣은 뒤 따로 만든다.

```bash
# 빈 DB에 (Docker의 db 컨테이너, 로컬 PostgreSQL, Supabase 모두 같음 — PostgreSQL 15 이상)
pg_restore --no-owner --no-privileges -d "$DATABASE_URL" dist/mom_main_20261014.dump
pg_restore --data-only -d "$DATABASE_URL" dist/mom_sensor_20261014.dump          # 센서 (선택, 약 15초)
psql "$DATABASE_URL" -v app_password='…' -v ai_password='…' -f db/roles.sql       # 앱·비서 계정
psql "$DATABASE_URL" -f supabase/sql/lockdown.sql                                  # Supabase일 때만
python tools/gen_dev_users.py --update '<시연 비밀번호>' | psql "$DATABASE_URL"     # U01~U12 (개발·시연 전용)
psql "$DATABASE_URL" -f db/checks/validate_loaded_data.sql                          # 20개 모두 0
```

생성기를 다시 돌렸거나 스키마를 고쳤으면 덤프를 다시 뜬다 (`scripts/load_all.sh --sensor` → `pg_dump`). 같은 seed면 데이터는 같다.
