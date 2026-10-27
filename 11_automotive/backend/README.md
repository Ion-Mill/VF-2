# MOM 백엔드 — 자동차 부품 절삭가공 라인 운영 관리 (AI 운영 비서)

`11_automotive` 문서(논리 ERD 최종본 59개 엔터티·설계서·UI 설계서·기획서·API 명세서 v1·DOC-01~07, **구현_중_수정사항 2026-10-14까지 반영**)를 바탕으로 만든 **백엔드 설계 + PostgreSQL DDL + 실행 뼈대**다.
**가상 데이터 생성기 9월 기록(seed 20260901)·가상 사내 문서 8개를 실제로 넣어 확인했다** (적재 점검 20개 0건 — `docs/04`).

- DB: PostgreSQL 16 — 테이블 72개(논리 엔터티 59개 — `chat_log` 포함 + 물리 추가, 파티션 제외, 2026-10-27 코드로 센 값), 뷰 18개, 업무 함수 55개, 트리거 47개로 업무 규칙(R-xx)을 막는다
- API: Python FastAPI + SQLAlchemy 2(Core) + psycopg 3 — 엔드포인트 168개(2026-10-27 코드로 센 값 — API명세서과 맞는 83개 + 시뮬레이터 입구·비서 도구·QR·묶음 조회 등 서버끼리·보조, 대조는 API명세서 2.11절), SQL은 `app/sql/*.sql` 이름 붙은 쿼리 285개
- 실시간: PostgreSQL `LISTEN/NOTIFY` → SSE (`/api/stream/events`, 사건 이름은 API명세서 3장)
- 가상 표시: 운영 데이터 응답마다 `is_synthetic` (객체는 맨 위, 목록은 줄마다) + 머리글 `X-Synthetic-Data`
- 시연: `POST /api/sim/reset` = 시연 기준점(10/1 08:00 = 9월 끝, `demo_snapshot` 스키마, 생성기 적재 뒤 자동)으로 되돌리기 — 시연 모드만. 센서는 복사하지 않고 기준점 뒤 값만 지움
- 데이터: 생성기 CSV(`tools/load_generated.py`) + 사내 문서 조각(`tools/load_docs.py`) — 한 번에 `scripts/load_all.sh`. Docker는 처음 띄울 때 자동, Supabase는 `supabase/`
- 아직 없는 것·필요한 자료: **[`docs/07_남은_자료와_할일.md`](docs/07_남은_자료와_할일.md)**
- **품질 측정값**은 설비(측정기 CMM-01)가 결과 파일로 보내 자동 기록, **재고·로트는 QR**로 조회·입고·실사·출하 전 확인·측정 시작 확인 (2026-10-13 가정 [제안] — `docs/01` 11·11a장)
- 워커: 시간 규칙 스케줄러(승인 대기·예방 정비 기한·CMM 결과 미수신·보고서 초안), CMM 결과 파일 감시
- 모든 결정은 `docs/05_결정기록.md`. 표시: **[제안]** = 이번에 정해 적용한 것, **[선택 필요]** = 팀이 정해야 하는 것, **[확인 필요]** = 문서끼리 맞춰 봐야 하는 것

## 문서

| 문서 | 내용 |
|---|---|
| [docs/01_백엔드_설계서.md](docs/01_백엔드_설계서.md) | 구조, 계층별 책임, 트랜잭션·권한·실시간·워커·AI 비서 경계, 오류 처리 |
| [docs/02_물리ERD.md](docs/02_물리ERD.md) | 논리 → 물리 변환 규칙, 테이블 목록(실제 DB에서 생성), 영역별 관계 그림 |
| [docs/03_API_명세.md](docs/03_API_명세.md) | 엔드포인트 136개와 권한, 공통 규칙(오류 형식·시각·페이지), 주요 흐름 예, **API명세서 API ID ↔ 이 서버 주소 대응표** |
| [docs/04_데이터적재_약속.md](docs/04_데이터적재_약속.md) | 생성기 CSV 약속(논리 ERD 11.1), 적재 순서·점검 20개, 사내 문서 조각, CMM 결과 파일 양식 2가지 |
| [docs/05_결정기록.md](docs/05_결정기록.md) | [제안]·[선택 필요]·[확인 필요] 목록과 이유 |
| [docs/06_역할별_권한.md](docs/06_역할별_권한.md) | OPR·MNT·SUP·MGR 권한 — 세 겹(관문·범위·DB), 역할별 할 수 있는 일, scope·"그 사람만" 규칙, 채팅 권한, 시험 |
| [docs/07_남은_자료와_할일.md](docs/07_남은_자료와_할일.md) | 이 백엔드·DB에 아직 없는 문서·데이터, 팀이 정할 것, 확인 못 한 것 |
| [docs/09_화면_백엔드_연결_설계.md](docs/09_화면_백엔드_연결_설계.md) | **화면 → 백엔드 → DB가 기본 (2026-10-24)**: 화면 기능별로 어디로 가는지, 시뮬레이터가 주인인 표, 진행 중 교대 미리보기, 여러 명 접속(트윈 함께 쓰기·연결 줄), 진행자 PC 켜는 법, 아직 브라우저에 남은 것 |
| [supabase/README.md](supabase/README.md) | Supabase에 올리는 법 (마이그레이션·계정·잠그기·데이터) |

## 폴더

```
backend/
├─ app/                  FastAPI 앱
│  ├─ main.py            진입점 (라우터·미들웨어·워커 시작)
│  ├─ config.py db.py security.py errors.py audit.py realtime.py sqlfiles.py
│  ├─ routers/           API (auth, line, alarms, notifications, stream, production, maintenance, qr,
│  │                     inventory, quality, documents, assistant, ingest, master)
│  ├─ services/          여러 쿼리를 묶는 일 (문서 버전 저장, 기록 만들기, CMM 파일 받기)
│  ├─ domain/            DB 없이 도는 순수 로직 (CMM CSV 읽기, QR 읽기, 비밀번호, 토큰, 권한표)
│  ├─ assistant/tools.py AI 비서 조회 도구 14개 (JSON Schema + 입력 확인)
│  ├─ workers/           scheduler.py (시간 규칙·보고서 초안), cmm_watcher.py (결과 파일 감시)
│  └─ sql/*.sql          이름 붙은 쿼리 ("-- name: x") — 코드에 SQL 문자열을 두지 않는다
├─ db/
│  ├─ schema/            DDL (00 확장 → 10 기준 정보 … 90 물리 추가 → 95 지연 FK)
│  ├─ functions/         트리거·업무 함수 (번호·시계, 무결성, 업무 흐름, CMM, 보관, 받기, 실시간)
│  ├─ views/             계산 속성 뷰, 보고서 초안 함수
│  ├─ seed/              코드 이름, 역할·권한, 알림 규칙
│  ├─ dev/               시험용 작은 목업 (9/14~9/15, 사용자 U01~U12) — 시연 데이터는 생성기
│  ├─ tests/             SQL 시험 (BEGIN … ROLLBACK)
│  ├─ checks/            생성기 데이터 적재 뒤 점검 20개
│  ├─ later/             정해진 뒤 넣을 것 (pgvector)
│  ├─ roles.sql          DB 계정 나누기 (mom_app, mom_ai_ro)
│  └─ apply.sh           스키마 → 함수 → 뷰 → 시드 (→ --dev)
├─ tools/                점검·생성 도구 (관계·속성·코드 대조, 쿼리 PREPARE, 적재, 문서 생성)
├─ tests/                파이썬 시험 (+ stubs/: FastAPI 없이 import만 하는 가짜 모듈)
├─ scripts/              load_all.sh (데이터 한 번에), test_all.sh, docker-entrypoint.sh
├─ supabase/             Supabase 마이그레이션·잠그기·데이터 넣기
├─ dist/                 DB 덤프 — 덤프 파일은 git에 안 올림 (로컬 백업, 다시 뜨는 법 dist/README.md)
├─ docs/품질·재고관리/   품질·재고 화면 시안(SCR-19~22)·가정·비서 AI에 넘길 일
├─ docs/08_팀문서_수정제안.md  팀 문서(11_automotive)에 넣자고 제안할 것
├─ Dockerfile  docker-compose.yml  requirements.txt  .env.example  .env.supabase.example
```

## 실행

### 팀원: 받아서 공용 Supabase에 붙여 켜기 (보통 이것)

DB는 Supabase `mom-db` 하나를 모두 같이 쓴다. 데이터는 이미 들어 있으니 **코드를 받고 설정 파일 하나만 만들면 된다**.

```bash
git clone <저장소 주소> && cd <폴더>
python -m venv .venv && source .venv/Scripts/activate        # Windows Git Bash (macOS·Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.supabase.example .env.supabase                       # <...> 를 채운다 — 비밀번호는 DB 담당에게 개인 메시지로 (git에 안 올라감)
python tools/check_connection.py --env-file .env.supabase    # 4개 모두 OK
python -m uvicorn app.main:app --env-file .env.supabase --reload
# http://localhost:8000/docs — POST /api/auth/login 로 U01~U12 / 시연 비밀번호
```

- 화면(프런트, React)은 `http://localhost:3000`에서 띄우고 API는 `http://localhost:8000`을 부른다 (CORS 기본값이 3000, 여러 개면 `MOM_CORS_ORIGINS`에 쉼표로). 둘을 한 번에 켜려면 `11_automotive/`에서 `npm run dev`.
  로그인 → `Authorization: Bearer <토큰>`, 실시간은 `GET /api/stream/events?token=<토큰>` (이름 붙은 사건 — `addEventListener`로 받음).
- `MOM_RUN_WORKERS=true`는 DB 담당 서버 한 대만. 연결 수 한도(무료 15개) 때문에 팀원 서버는 `MOM_DB_POOL_SIZE=2`.
- 스키마(`db/`)를 고쳤으면 Supabase에도 반영해야 한다 — [supabase/README.md](supabase/README.md).

### Docker (DB까지 내 컴퓨터에) — 처음 띄우면 생성기 데이터·사내 문서까지 넣음

```bash
# 폴더 모양: VF-2/11_automotive/backend (이 폴더) — 상위 폴더(..)가 11_automotive (생성기·가상사내문서)
cp .env.example .env          # 비밀번호·MOM_JWT_SECRET·서비스 키·MOM_DEMO_PASSWORD 를 채운다
docker compose up --build     # 빈 DB → 스키마 + 계정 + 생성기 기준 정보·9월 + 사내 문서 209조각 + 점검 (약 20초)
# http://localhost:8000/docs  (OpenAPI) — 로그인 U01~U12 / MOM_DEMO_PASSWORD
docker compose down -v        # 처음부터 다시 (DB 볼륨 지움)
```

`.env`: `MOM_LOAD_SENSOR=1`(센서 약 98만 행, DB +약 120MB), `MOM_LOAD_REALTIME=1`(10/1 리허설 기록), `AUTOMOTIVE_DIR`(11_automotive 위치가 다르면).
사용자 12명: `U01~U06` 작업자(주간 U01·U02·U03 / 야간 U04·U05·U06, OP-30 = U02·U05, 측정 OP-50 = U03·U06), `U07~U09` 보전, `U10` 주간 반장, `U11` 야간 반장, `U12` 관리자.

### 직접 (Git Bash·Linux)

```bash
createdb mom
export PGDATABASE=mom GEN_DIR=../데이터생성기 DOCS_DIR=.. \
       MOM_APP_DB_PASSWORD=... MOM_AI_DB_PASSWORD=... MOM_DEMO_PASSWORD=...
./scripts/load_all.sh [--sensor] [--realtime]      # 스키마 → 계정 → 데이터 → 문서 → 비밀번호 → 점검 (PYTHON=python 으로 바꿀 수 있음)
pip install -r requirements.txt
export MOM_DATABASE_URL=postgresql+psycopg://mom_app:...@localhost:5432/mom
export MOM_READONLY_DATABASE_URL=postgresql+psycopg://mom_ai_ro:...@localhost:5432/mom
export MOM_JWT_SECRET=... MOM_INGEST_KEY=... MOM_ASSISTANT_KEY=... MOM_DEMO_MODE=true
uvicorn app.main:app --reload
```

덤프로 바로 (덤프는 git에 없음 — DB 담당에게 받거나 다시 뜬다): `pg_restore --no-owner --no-privileges -d mom dist/mom_main_20261014.dump` (+ 센서 `pg_restore --data-only -d mom dist/mom_sensor_20261014.dump`) → `db/roles.sql` → `tools/gen_dev_users.py --update` ([dist/README.md](dist/README.md)).

### Supabase

[supabase/README.md](supabase/README.md) — 마이그레이션(`supabase/migrations/`) → `supabase/load_data.sh` (계정·RLS 잠그기·데이터). 무료 한도 500MB 안 (센서 빼면 약 40MB, 넣으면 약 160MB). 지금 `mom-db`는 센서까지 넣어 약 166MB.

## 시험

```bash
PGHOST=... PGPORT=... ./scripts/test_all.sh
```

1. DB 시험 15개 파일 — 스키마 주인 계정으로 한 번, **앱 계정(mom_app, 최소 권한)으로 한 번 더**
2. `app/sql` 쿼리 199개 PREPARE (칼럼·형식이 스키마와 맞는지)
3. 파이썬 시험 (DB 없이) 44개 — CMM CSV 읽기, QR 읽기, 비밀번호·토큰·권한표(**역할 4개 × 대표 동작 35개가 기획서 13장대로인지**, **API 주소 110개마다 통과하는 역할이 API명세서 "역할" 칸대로인지**, 실시간 사건 역할별 거르기), 비서 도구 입력 확인, **코드가 부르는 쿼리 이름·매개변수가 SQL과 맞는지(AST 정적 검사)**
4. 파이썬 시험 (DB로) 24개 — 문서 버전 저장, 기록 만들기, CMM 파일 받기·감시 폴더 옮기기, 비서 도구 14개를 읽기 전용 계정으로, 라우터 처리기로 업무 흐름(로그인 → 작업지시서 → 작업기록서 확정, 보류, 출하, 측정 결과 올리기, 보고서 확정, 비서·설비 데이터 받기, 역할별 범위 — 입고 품목 주인·원자재 로트·OPR 수정 이력·대리 승인, QR 조회·입고·실사·출하 전 확인·측정 시작 확인)

문서의 자동 생성 부분(테이블 목록·API 목록·CSV 칼럼 약속)은 스키마·라우터를 바꾼 뒤 `python tools/update_docs.py --psql "psql -d mom_test" --gen <생성기 폴더>`로 다시 만든다.
최신 논리 ERD와 다시 대조: `python tools/check_attributes.py <논리ERD.md> --psql ...` (속성), `tools/check_relations.py` (관계), `tools/gen_code_labels.py` (6장 코드).

## 확인 범위 (솔직하게)

| 확인함 (2026-10-14, Linux · PostgreSQL 16) | 확인 못 함 |
|---|---|
| 최신 논리 ERD 59개 엔터티·574개 속성·관계 125개·6장 코드와 실제 DB 대조 (빠진 칸 0, 관계 예외 2개는 다형 참조) | **Docker 이미지 빌드·compose** (이 환경에서 Docker Hub가 막힘) — 같은 순서를 `load_all.sh`·entrypoint 사본으로 빈 DB에 돌려 확인 |
| **생성기 실제 CSV 적재**: 기준 정보 22 + 9월 33 + 센서 978,271행, 10/1 리허설 17개 — 적재 점검 20개 0건, SIM-03 되돌리기, 센서 따로 | ~~실제 Supabase 프로젝트에 올리기~~ → 2026-10-15 `mom-db`에 올리고 확인 (스키마 해시 일치, 점검 0건, 센서 포함, SIM-03은 Supabase에 맞게 고침 — [supabase/README.md](supabase/README.md)) |
| SQL 시험 15파일 × 2계정, 쿼리 199개 PREPARE, 파이썬 시험 44 + 24개 | AI 비서 서비스와 실제로 주고받기 (서비스가 아직 없음 — 없을 때 `NO_RESPONSE`·채팅 기록 저장만) |
| **진짜 FastAPI·uvicorn으로 적재한 DB에 HTTP**: 로그인 U01~U12, GET 주소 전부 × 3역할 129건 5xx 0건 (RLS 잠근 DB에서도), 채팅·기록·17:00 넘기기·SIM-03, 생성기 CMM 결과 파일을 감시 폴더에 떨어뜨려 기록 | 생성기 실시간 모드(`Realtime`)와 서버 연결 — 연결 방식이 [선택 필요: 기술 회의] (API명세서 2.9) |

서버를 띄울 때: `pip install -r requirements.txt` → `uvicorn app.main:app` → `/docs`에서 로그인·`/api/line/twin` 한 번씩. tests/stubs는 진짜 패키지가 있으면 쓰이지 않는다.
