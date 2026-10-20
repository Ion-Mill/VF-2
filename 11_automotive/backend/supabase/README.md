# Supabase에 올리기 (2026-10-15 실제 프로젝트에 올림)

이 폴더는 MOM DB를 Supabase 프로젝트(PostgreSQL 17)에 올리는 데 쓰는 파일이다. 2026-10-15 실제 프로젝트(`mom-db`, 서울, 무료)에 스키마·9월 데이터·사내 문서를 올리고 확인했다 — 맨 아래 "실제로 올린 기록".

| 파일 | 하는 일 |
|---|---|
| `migrations/20261014000000_mom_schema.sql` | 스키마·함수·뷰·기준 시드 한 파일 (`db/apply.sh`와 같은 순서, 개발 목업 없음). `build_migration.sh`가 만든다 |
| `build_migration.sh` | `db/`를 고친 뒤 위 파일을 다시 만든다 |
| `sql/lockdown.sql` | `anon`·`authenticated` 권한을 모두 거두고, 모든 표에 RLS + `mom_app`(읽기·쓰기)·`mom_ai_ro`(읽기) 정책만, DB 시간대 = 한국 |
| `load_data.sh` | 계정(`db/roles.sql`) → 잠그기 → 생성기 데이터·사내 문서·점검 (`scripts/load_all.sh --keep`) |

## 순서

```bash
# 0) Supabase 대시보드에서 프로젝트를 만든다 (지역: 서울 ap-northeast-2). DB 비밀번호를 적어 둔다
# 1) 접속 값 — 대시보드 Connect → "Direct / Connection string" 카드 → 방식 "Session pooler" (IPv4 됨. LISTEN/NOTIFY를 쓰므로
#    Transaction pooler 6543은 안 됨 — host는 같고 포트만 다르다). PGHOST에는 접속 문자열 전체가 아니라 @ 뒤 host만
export PGHOST=aws-0-ap-northeast-2.pooler.supabase.com PGPORT=5432 PGUSER=postgres.<project-ref> \
       PGPASSWORD='<DB 비밀번호>' PGDATABASE=postgres PGSSLMODE=require

# 2) 스키마 — 둘 중 하나
supabase link --project-ref <project-ref> && supabase db push       # Supabase CLI (backend 폴더에서)
psql -v ON_ERROR_STOP=1 -f supabase/migrations/20261014000000_mom_schema.sql   # 또는 psql

# 3) 계정·잠그기·데이터 (생성기·사내 문서 폴더가 필요)
export GEN_DIR=../생성기 DOCS_DIR=..
export MOM_APP_DB_PASSWORD='<새로 정함>' MOM_AI_DB_PASSWORD='<새로 정함>' MOM_DEMO_PASSWORD='<시연 비밀번호>'
./supabase/load_data.sh              # 센서도: --sensor (DB 약 160MB) / 10/1 리허설도: --realtime
```

덤프로 올려도 된다 (생성기 폴더 없이): `pg_restore --no-owner --no-privileges -d "$DATABASE_URL" dist/mom_main_20261014.dump`
→ `psql -f db/roles.sql`(비밀번호 두 개) → `psql -f supabase/sql/lockdown.sql` → `tools/gen_dev_users.py --update '<비밀번호>' | psql`
→ (센서) `pg_restore --data-only -d "$DATABASE_URL" dist/mom_sensor_20261014.dump`. 자세히는 `dist/README.md`.

## API 서버를 Supabase에 붙일 때

```bash
cp .env.supabase.example .env.supabase        # <...> 만 채운다 (앱·비서 계정 비밀번호, JWT 키)
python tools/check_connection.py --env-file .env.supabase   # 앱·읽기 계정 로그인, 읽기 전용, LISTEN/NOTIFY, 왕복 시간
uvicorn app.main:app --env-file .env.supabase                # → http://localhost:8000/docs
```
- 주소는 Session pooler(5432)만 — 실시간 알림(LISTEN)이 Transaction pooler(6543)에서는 안 된다. 사용자 이름 뒤에 `.<project-ref>`
- Session pooler는 역할마다 Pool Size(무료 기본 15)까지만 접속을 받는다 → `.env.supabase.example`은 서버 1대가 앱 계정 연결을 최대 7개 쓰게 줄여 둠 (`MOM_DB_POOL_SIZE=4`, `MOM_DB_MAX_OVERFLOW=2`). 같은 DB에 서버를 2대 넘게 붙이면 늘어난 만큼 Pool Size를 올리거나 값을 더 줄인다
- 스케줄러(`MOM_RUN_WORKERS=true`)는 같은 DB에 붙은 서버 중 한 대만
- 직접 연결(`db.<ref>.supabase.co:5432`)은 IPv6만 된다

## 알아 둘 것

| 항목 | 내용 |
|---|---|
| 화면이 Supabase API(PostgREST)를 직접 부르지 않는다 | 화면 → 우리 API 서버 → DB. 그래서 `anon` 키로는 아무 표도 못 읽게 잠근다 (lockdown). Supabase 보안 점검의 "RLS 꺼짐" 경고도 없어진다 |
| 무료 한도 500MB | 센서 빼면 약 40MB, 넣으면 약 160MB (시연 기준점 복사본 포함 — 센서는 복사하지 않음) |
| 확장 | `btree_gist`(설비 상태 겹침 금지) — Supabase에 있음. 나중에 `pgvector`(`db/later/`)도 있음 |
| **SIM-03 시연 되돌리기** | `fn_demo_reset`이 트리거를 끈 채(`session_replication_role = replica`) 복사본으로 채운다. Supabase `postgres`는 슈퍼유저가 아니어서 **함수 SET 절·`set_config()`로는 permission denied, `SET` 문은 됨** (2026-10-15 실제 프로젝트 PG 17.11에서 확인). 그래서 함수 안에서 `EXECUTE 'SET LOCAL …'`로 걸고 끝에 되돌린다 — 앱 계정이 불러도 됨 |
| 시간대 | 앱 연결은 `Asia/Seoul`을 따로 건다. lockdown이 DB 기본 시간대도 한국으로 바꾼다 |
| 스키마를 고치면 | 이미 올린 프로젝트에는 바뀐 부분만 새 마이그레이션 파일(`migrations/<시각>_<이름>.sql`)로. 처음부터면 프로젝트를 리셋하고 `build_migration.sh` → 2) 3) |
| 비밀 값 | 비밀번호·키는 `.env`·셸 변수로만 (저장소에 넣지 않음, NFR-SEC-06) |


## 실제로 올린 기록 (2026-10-15, 프로젝트 `mom-db`)

| 단계 | 한 방법 | 결과 |
|---|---|---|
| 스키마 | Claude가 Supabase 연결 도구(`apply_migration`)로 9개로 나눠 올림 (주석 줄만 뺌) | 표 72·함수 88·트리거 47·뷰 18·제약·인덱스·기준 시드가 로컬과 해시까지 같음 |
| 시연 되돌리기 함수 2개 | 대시보드 SQL Editor에 붙여 넣음 (연결 도구는 `DROP`·`TRUNCATE` 글자가 있으면 확인 창을 띄우는데, 그 창이 앱에 보이지 않아 3분 뒤 시간 초과) | 줄 끝(CRLF)만 다르고 같음. 기준점 → 되돌리기 실제로 돎 (표 55개, 끝나면 `origin`) |
| API 서버 연결 점검 | 사용자 PC에서 `tools/check_connection.py --env-file .env.supabase` | 앱 계정·읽기 계정(쓰기 막힘)·**LISTEN/NOTIFY(Session pooler)** 모두 OK (사용자 확인) |
| 계정·잠그기·데이터·문서 | Windows Git Bash에서 `./supabase/load_data.sh` | 점검 20개 위반 0, 문서 조각 209, U01~U12 비밀번호, 공개 키 권한 0, RLS 꺼진 표 0, 정책 142, 43MB |
| 2026-10-20 정비 탭 확인 요청 반영 | Claude가 연결 도구(`apply_migration`, 이름 `check_request_1020`)로 `migrations/20261020000000_check_request_1020.sql`을 올림. 먼저 같은 상태의 로컬 DB(10/15 코드 + 9월 데이터 + 계정·잠그기)에 올려 새 `db/` 원본으로 만든 DB와 같음을 확인 | 알림 규칙 29, `daily_report.memo` 19건(복사본도), 새 표 `notification_pm_task` RLS·정책 2·권한, 트리거 2, 시연 되돌리기 목록에 새 표 |
| 2026-10-20 브리핑 체크 저장 (새 표 `briefing_check`) | `migrations/20261020010000_briefing_check.sql` — **저장소에만 있고 공용 mom-db에는 아직 적용하지 않음**(DB 담당이 올린다). 로컬에서 같은 상태 DB(`db/` 원본 + 계정 + 시연 기준점)에 올려 새로 만든 DB와 표 모양이 같고(RLS·정책만 잠그기 몫으로 더 붙음) `demo_snapshot.meta.tables`에 들어감을 확인 | 올리면 `briefing_check` RLS·정책 2·`mom_app` 쓰기, `mom_ai_ro` 읽기 권한 없음. 올리기 전에는 `/api/assistant/briefing/checks`만 오류 |

**올리면서 걸린 것과 고친 것**

| 걸린 것 | 고친 것 |
|---|---|
| Supabase `postgres`는 슈퍼유저가 아니라 함수 SET 절·`set_config()`로 `session_replication_role`을 못 바꿈 → 스키마 단계에서 멈췄을 것 | `fn_demo_reset`이 `EXECUTE 'SET LOCAL …'`로 걸고 끝에 되돌림 |
| Windows psql은 `\copy` 파일 경로의 한글(`…/생성기/…`)을 못 읽음 | `tools/load_generated.py`가 생성기 폴더에서 psql을 돌리고 CSV를 상대 경로(`masters/x.csv`)로 넘김. 임시 SQL 파일 경로가 한글이면 생성기 폴더에 둠 |
| `roles.sql`·`lockdown.sql`에서 btree_gist 확장 함수(관리 계정 소유)마다 "no privileges" 경고 수백 줄 | 두 파일에서 경고를 숨김 (`client_min_messages = error`). 우리 함수 권한은 그대로 걸림 |
| `load_data.sh`를 다시 돌리면 이미 넣은 생성기 데이터와 부딪혀 멈춤 | `scripts/load_all.sh`가 생성기 데이터(`dataset_info.loaded_at`)·센서가 이미 있으면 그 단계를 건너뜀 |
| Windows의 `python3`는 Store 안내로 이어지는 가짜 실행 파일일 수 있음 | `load_all.sh`가 실제로 도는 파이썬을 고르고 `PYTHONUTF8=1`·`PGCLIENTENCODING=UTF8`을 건다 |

**알아 둘 것**
- Supabase 마이그레이션 기록은 10개(`mom_schema_p01…p07`, `mom_rls_on_until_lockdown`, 2026-10-20 `check_request_1020`)다. Supabase CLI `db push`를 쓰려면 이 저장소의 파일 1개와 맞지 않으니 `supabase migration repair`로 맞춘다.
- 보안 점검(advisor) 남은 경고: 뷰 18개 SECURITY DEFINER(뷰는 RLS를 건너뜀 — 그래서 데이터보다 잠그기가 먼저), 함수 search_path 미지정, btree_gist가 public. 화면은 Supabase API를 부르지 않으므로 당장 문제는 아님.
- Supabase DB 정렬 규칙(collation)이 로컬(C.UTF-8)과 달라 문자열 `ORDER BY` 순서가 조금 다를 수 있다 (시드 값 자체는 같음).
- `load_data.sh`의 4단계(사내 문서)가 시연 기준점을 다시 만든다 — 시연 도중에는 다시 돌리지 않는다.
