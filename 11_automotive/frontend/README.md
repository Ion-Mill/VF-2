# 데이터적용본 — 확정 3D 시안 + 데이터 전부

팀 확정 3D 시안(`화면시안/확정시안/export/factory-dashboard-next/`)의 사본에 `데이터md파일/`의 데이터·설계를 전부 넣은 판이다 (2026-10-15).
`화면시안/확정시안/데이터적용본/`에서 모노레포 `frontend/`로 옮겼다 (2026-10-15).

- 3D: 색·모델·조명은 원본 그대로 두고(사용자 결정), 데이터는 전부 넣었다 — 실제 좌표·크기, 정비·막힘·기록 없음 상태, ▲·⚠, 이름표 상태 글자, 데이터 재공 수, 병목 주황 테두리, 사이클·배속·일시정지, BRK-A100 가공물.
- 화면: UI설계서 SCR-01~26 전부.
- 데이터: 생성기 10/1 실시간 모드 + 9월 과거 기록(**백엔드 DB**, 못 쓰면 생성기 `out/` CSV) + 가상 사내 문서를 시연 데이터 서버가 API로 내준다 (2026-10-23).
- **2026-10-24부터 화면 → 백엔드 → DB가 기본이다** (사용자 결정). 화면은 백엔드만 부르고, 시연 데이터 서버는 "가짜 공장"으로 10/1 기록을 DB에 중계한다. 설계·켜는 법·남은 것: `backend/docs/09_화면_백엔드_연결_설계.md`.

## 실행

서버 세 개를 켠다: 백엔드(:8000) · 시연 데이터 서버(:8765, 가짜 공장) · 화면(:3000). 생성기 가상환경(`11_automotive/생성기/.venv`, Python 3.12)과 백엔드 가상환경이 먼저 설치돼 있어야 한다 (`npm run setup`).

한 번에: `11_automotive/`에서 `npm run dev` (2026-10-24부터 백엔드까지 셋 다. 예전 두 개만은 `npm run dev:sim-web` + `.env.local`에 `NEXT_PUBLIC_MOM_BACKEND=0`).
화면이 움직이려면 **진행자 PC 한 대**의 `backend/.env.supabase`에 `MOM_SIM_SYNC=true`·`MOM_SIM_URL=http://127.0.0.1:8765`·`MOM_RUN_WORKERS=true`·`MOM_SCHEDULER_SECONDS=5`가 있어야 한다 — 시연 서버가 그 파일을 읽어 DB 중계를 스스로 켠다 (아래 "10/1 기록을 DB에도 넣기"). 따로 켤 때는 아래처럼.

```
# 1) 시연 데이터 서버 (포트 8765) — 이 폴더에서
..\생성기\.venv\Scripts\python.exe tools\sim_server.py

# 2) 화면 (처음 한 번 npm install)
npm run dev            # http://localhost:3000  (3000을 쓰는 중이면 npm run dev -- -p 3100)
```

Git Bash에서 한글이 깨지면 1) 앞에 `PYTHONIOENCODING=utf-8`을 붙인다.

**9월 기록은 DB에서 읽는다 (2026-10-23).** 시연 서버가 켜질 때와 [처음으로] 때 9월 표 24개(보고서·문서 이력·알림·정비·검사·출하·재고·공구 기록)를 DB에서 읽는다. 10/1 08:00 전 기록만 읽어 실시간 부분과 겹치지 않는다. 어느 DB인지는 아래 순서로 정하고, 켤 때 `과거 기록 = DB (…)` 줄과 `/api/health`의 `past_source`로 보인다.

| 순서 | 어디서 | 비고 |
|---|---|---|
| 1 | 환경 변수 `MOM_PAST_DB_URL` | `postgresql://…`. `off`면 CSV |
| 2 | `backend/<MOM_ENV_FILE>`(기본 `.env.supabase`)의 `MOM_READONLY_DATABASE_URL` | `npm run dev:api`와 같은 DB, 읽기 전용 계정 |
| 3 | 그 파일에 `MOM_AI_DB_PASSWORD`만 있으면(Docker `.env`) | 로컬 Docker DB(127.0.0.1:5432/mom)의 `mom_ai_ro` |

주소가 없거나, 접속이 안 되거나, DB의 생성기 데이터가 이 PC의 `생성기/out/`과 다르면(`dataset_info.config_sha256`) 예전처럼 CSV를 읽고 그 까닭을 한 줄로 찍는다. 처음 한 번 `npm run setup:sim`(또는 `생성기\.venv\Scripts\python -m pip install -r 생성기\requirements.txt`)으로 `psycopg`를 깐다. 기준 정보(`masters/`)는 생성기 실시간 모드가 같은 파일을 쓰므로 CSV 그대로다.

**10/1 기록을 DB에도 넣기 (DB 중계, 2026-10-23 — `tools/db_relay.py`. 2026-10-24부터 백엔드 환경 파일에 `MOM_SIM_SYNC=true`면 스스로 켜짐).** 켜면 시뮬레이터가 만드는 10/1 기록(작업지시·로트·실적·설비 상태·알람·병목·재공·공구·검사·측정 결과·불량·보류·예방 정비·재고 거래·센서 = `out_realtime` CSV와 같은 17개 표)을 3초마다 바뀐 줄만 **백엔드가 쓰는 DB(공용 Supabase `mom-db`)**에 넣는다. 새 알람의 알림·반복 알람 판정·작업지시서 초안, 재공 경고·병목 이동 알림은 DB가 만든다. DB 시계도 시연 시계를 따라간다. **[처음으로]를 누르면(그리고 시연 서버를 켤 때) DB도 시연 기준점(10/1 08:00)으로 되돌린다.**

**DB 1개 = 공장 1개.** 모두가 같은 DB를 보므로, 누가 [처음으로]를 눌러도 **모두의 10/1 기록이 지워진다**(채팅 기록 포함). 여러 명이 동시에 중계를 켜면 기록이 겹친다 → **중계는 시연 진행자 한 명만 켠다.** 화면 리허설만 할 때는 켤 필요가 없다(화면의 10/1 값은 시연 서버가 바로 준다).

| 순서 | 할 일 |
|---|---|
| 1 | 백엔드 env(`backend/.env.supabase`)에 `MOM_SIM_SYNC=true`를 넣고 백엔드를 다시 켠다. `MOM_INGEST_KEY`가 있어야 한다 |
| 2 | (2026-10-24부터 할 일 없음) 시연 서버가 같은 파일(`MOM_ENV_FILE`, 기본 `.env.supabase`)의 `MOM_SIM_SYNC`·`MOM_INGEST_KEY`를 읽어 `MOM_BACKEND_URL`(기본 `http://127.0.0.1:8000`, `start_all.ps1`은 8020을 넣어 줌)로 중계한다. 다른 주소면 `MOM_DB_RELAY_URL`, 끄려면 `MOM_DB_RELAY_URL=off` |
| 3 | 시연 서버를 켜면 `[DB 중계] 켜짐`, `[DB 중계] DB 처음으로 …` 줄이 보인다. `꺼짐 — … MOM_SIM_SYNC` 이면 1이 안 된 것 |

`[DB 중계] 꺼짐 — DB 시연 기준점이 시뮬레이터 시작점과 다름`이 나오면 DB 기준점(`fn_demo_snapshot`)과 생성기 시작점(10/1 08:00, 9월 마지막 번호)이 어긋난 것이다. 나중에 10/1 뒤 기록을 DB에 채우거나 실제 시간으로 바꿀 때는 둘을 함께 옮긴다. 로컬 Docker DB(`backend/.env`, 8000)에서도 같은 방법으로 된다.

**화면 → 백엔드 (C2, 2026-10-23 → 2026-10-24 기본값 — `src/shell/backendApi.ts`·`backendDocs.ts`).** 기획서 12.1처럼 화면 → 백엔드 → DB. 화면의 `/api/...` 호출을 백엔드 API로 바꿔 부르고 화면이 쓰던 모양으로 돌려준다. 로그인도 백엔드가 비밀번호를 확인한다. 작업지시서·작업기록서·간이 기록·알림도 백엔드(DB)에서 읽고 쓴다 — 작업지시서 초안·알림은 DB가 만든다. 시연 조작·로트 보류·공구 교체·정비 시작·끝·설비 복귀는 백엔드가 권한을 확인한 뒤 시뮬레이터(이 시연 서버)에 넘긴다.

| 항목 | 내용 |
|---|---|
| 기본 | 켜짐. 화면 서버(`next.config.mjs`)가 `/api`를 `MOM_BACKEND_URL`(기본 `http://127.0.0.1:8000`)로 넘긴다 — 같은 주소라 CORS 필요 없음. `NEXT_PUBLIC_MOM_API`가 있으면 브라우저가 그 주소를 직접 부른다(CORS 필요) |
| 끄기 | `frontend/.env.local`에 `NEXT_PUBLIC_MOM_BACKEND=0` → `npm run dev:sim-web` (예전처럼 시연 서버 직접, 문서·알림은 브라우저) |
| 진행 중 교대 보고서 | 저장하지 않는 미리보기(백엔드가 DB 저장점 안에서 계산하고 되돌림). 교대가 끝나면 진행자 백엔드의 스케줄러가 초안을 만들어 저장·확정할 수 있다 |
| 시연 조작 | 백엔드 `MOM_SIM_CONTROL_USERS`에 든 사람만 (비우면 누구나). 아니면 [시연] 버튼이 잠긴다 |
| 확인 | `node tools/backend_flow_check.mjs [백엔드] [--read-only]` — 화면 코드 그대로 역할 4개 읽기 + S1 대본 끝까지 (⚠ `--read-only`가 아니면 [처음으로]부터 DB에 씀). 대조는 `node tools/backend_adapter_check.mjs <시연서버> <백엔드> U10` |

아직 화면 안(브라우저)에 두는 것: 품질 게이지·외관·수동 측정값, 폐기 제안·승인, 예방 정비 초안 확인, 정지 사유 칸 — 시뮬레이터가 주인인 표라 백엔드가 직접 쓰면 번호가 겹친다 (`backend/docs/09_화면_백엔드_연결_설계.md` 2-1). 시연 서버와 숫자가 다른 곳은 `구현_중_수정사항/1023_수정간단내용.md` 10장.

로그인에서 사용자를 고르면 시작된다. 시연 조작(사건 S1·S3·S4·S6, 배속, 일시정지, 17:00으로, 처음으로)은 상단 [시연 ▾].

점검 (서버가 켜진 채로, **처음으로 되돌리므로 시연 중에는 돌리지 말 것**):

```
..\생성기\.venv\Scripts\python.exe tools\check_server.py     # → check_server: OK
npx tsc --noEmit
```

## 구조

```
tools/
  sim_server.py        시연 데이터 서버 (표준 라이브러리 HTTP). /api/... 전부, 오류 형식 {code, message, detail}
  server_live.py       10/1 실시간 계산: 트윈·생산·OEE·손실·작업지시·로트·재고·공구·정비·다시 보기·교대 보고서 초안
  server_past.py       9월 기록(백엔드 DB, 못 쓰면 생성기/out/ CSV), masters, 가상사내문서 읽기·검색
  server_assistant.py  AI 비서 (규칙 기반: 알람 코드·지표·병목·재공·공구·재고 + 사내 문서 검색, 역할 권한)
  llm_compose.py       비서(8100)의 POST /compose/{kind}를 백그라운드로 불러 다듬은 문장을 받아 두었다가 내줌 (기다리지 않음, 기본 꺼짐 MOM_LLM_COMPOSE=1)
  build_data.py        masters·사내 문서 → src/shell/generated.ts, tools/data.json (masters가 바뀌면 다시 돌림)
  check_server.py      서버 자가 점검
  backend_adapter_check.mjs  화면 → 백엔드 전환(C2) 대조: 같은 시각 시연 서버와 backendApi.ts 응답을 칸마다 비교 (두 서버가 켜진 채로)
  backend_flow_check.mjs     화면 → 백엔드 흐름 점검 (2026-10-24): backendApi.ts·backendDocs.ts로 역할 4개 읽기 + S1 대본(작업지시서~복귀) — DB에 씀, --read-only
  tests/               llm_compose·시연 서버 입구·9월 DB 읽기(test_past_db) 시험 (`..\생성기\.venv\Scripts\python.exe -m pytest tools/tests -q`)
src/components/FactoryDashboard.tsx   원본 3D (+ dataMode: applyLive, 실제 좌표 배치, 재공 맞춤, 병목·상태 표시)
src/shell/            화면 틀(App)·2D 화면 전부·알림 규칙(rules.ts)·API 연결(live.ts)
src/shell/backendApi.ts  화면 → 백엔드 (C2, 기본 켜짐 — 끄기 NEXT_PUBLIC_MOM_BACKEND=0): 시연 서버 주소 이름 → 백엔드 API, 응답을 화면 모양으로
src/shell/backendDocs.ts 작업지시서·작업기록서·간이 기록·알림을 백엔드에서 읽고 쓰기 (2026-10-24)
src/shell/assistText.ts  비서가 다듬은 문장을 시연 서버에 묻는 호출 (지침카드 풀이 등, 꺼져 있으면 아무것도 안 더해짐)
next.config.mjs       /api → 백엔드 MOM_BACKEND_URL (기본 :8000). NEXT_PUBLIC_MOM_BACKEND=0이면 시연 서버 SIM_SERVER (기본 :8765)
```

## 원본·설계서와 다른 점 (남은 한계)

| 항목 | 내용 |
|---|---|
| 3D 색·모델 | 원본(가공 초록 등, 둥근 모델·조명·블룸). 상태 색 규칙 C·단순 도형은 안 함 (사용자 결정) |
| 지게차·자동창고·크레인 | 원본 그대로 남김. 공장 동쪽 벽(28 m) 밖으로 밀어 둠 |
| 설비 모양 | 자리·크기만 데이터. SAW-01 정면 방향은 안 돌림 |
| 재공 그림 | 숫자는 데이터 값 그대로. 3D에 쌓이는 부품은 원본 그릇 크기까지만 (회전 테이블 11개, 상자 30개) |
| AI 비서 | 규칙 기반 (답에 `engine: rule`). 외부 LLM은 기본 꺼짐 — 시연 서버를 `MOM_LLM_COMPOSE=1`로 켜면 비서(8100)가 교대·일일 보고서, 작업지시서 제목·증상, 지침카드 풀이 문장을 다듬는다 (`assistant/실행_안내.md` 6-3). 채팅 탭은 별도 스위치(`NEXT_PUBLIC_MOM_API`) |
| 저장 | **백엔드 모드(기본)**: 작업지시서·작업기록서·간이 기록·알림 처리·보고서·입고·출하·설정은 백엔드 → DB, 로트 보류·공구 교체·정비 시작·끝은 시뮬레이터 → DB 중계 — 모두가 같이 본다. 품질 게이지·수동 측정·폐기 제안·예방 정비 초안 확인·정지 사유는 아직 브라우저 (위 "화면 → 백엔드"). 예전 길(`NEXT_PUBLIC_MOM_BACKEND=0`)은 문서·알림이 브라우저, 보고서·보류·재고·출하·설정이 시연 서버 메모리 |
| 3D 느림 | 처음 30프레임 뒤 4초 평균이 8 fps 미만이면 2D 배치도로 바뀜 ([3D 다시 보기]로 돌아감) |

3D에 무엇을 넣고 무엇을 남겼는지 항목별 표는 `../못들어가는것들.md` 6장.

## 참고 (원본에서)
- FactoryDashboard.tsx는 원본 대형 파일이라 타입 검사를 꺼 두었다(@ts-nocheck). `src/shell/`은 strict.
- reactStrictMode는 꺼 두었다. 켜면 개발 모드에서 3D 장면이 두 번 만들어진다.
