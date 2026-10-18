# 데이터적용본 — 확정 3D 시안 + 데이터 전부

팀 확정 3D 시안(`화면시안/확정시안/export/factory-dashboard-next/`)의 사본에 `데이터md파일/`의 데이터·설계를 전부 넣은 판이다 (2026-10-15).
`화면시안/확정시안/데이터적용본/`에서 모노레포 `frontend/`로 옮겼다 (2026-10-15).

- 3D: 색·모델·조명은 원본 그대로 두고(사용자 결정), 데이터는 전부 넣었다 — 실제 좌표·크기, 정비·막힘·기록 없음 상태, ▲·⚠, 이름표 상태 글자, 데이터 재공 수, 병목 주황 테두리, 사이클·배속·일시정지, BRK-A100 가공물.
- 화면: UI설계서 SCR-01~26 전부.
- 데이터: 생성기 10/1 실시간 모드 + 9월 과거 CSV + 가상 사내 문서를 시연 데이터 서버가 API로 내준다.

## 실행

서버 두 개를 켠다. 생성기 가상환경(`11_automotive/생성기/.venv`, Python 3.12)이 먼저 설치돼 있어야 한다 (`생성기/실행_안내.md`).

한 번에: `11_automotive/`에서 `npm run dev` (시연 데이터 서버 + 화면을 같이 켬, 백엔드까지는 `npm run dev:full`). 따로 켤 때는 아래처럼.

```
# 1) 시연 데이터 서버 (포트 8765) — 이 폴더에서
..\생성기\.venv\Scripts\python.exe tools\sim_server.py

# 2) 화면 (처음 한 번 npm install)
npm run dev            # http://localhost:3000  (3000을 쓰는 중이면 npm run dev -- -p 3100)
```

Git Bash에서 한글이 깨지면 1) 앞에 `PYTHONIOENCODING=utf-8`을 붙인다.
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
  server_past.py       생성기/out/ 9월 CSV, masters, 가상사내문서 읽기·검색
  server_assistant.py  AI 비서 (규칙 기반: 알람 코드·지표·병목·재공·공구·재고 + 사내 문서 검색, 역할 권한)
  llm_compose.py       비서(8100)의 POST /compose/{kind}를 백그라운드로 불러 다듬은 문장을 받아 두었다가 내줌 (기다리지 않음, 기본 꺼짐 MOM_LLM_COMPOSE=1)
  build_data.py        masters·사내 문서 → src/shell/generated.ts, tools/data.json (masters가 바뀌면 다시 돌림)
  check_server.py      서버 자가 점검
  tests/               llm_compose·시연 서버 입구 시험 (`..\생성기\.venv\Scripts\python.exe -m pytest tools/tests -q`)
src/components/FactoryDashboard.tsx   원본 3D (+ dataMode: applyLive, 실제 좌표 배치, 재공 맞춤, 병목·상태 표시)
src/shell/            화면 틀(App)·2D 화면 전부·알림 규칙(rules.ts)·API 연결(live.ts)
src/shell/assistText.ts  비서가 다듬은 문장을 시연 서버에 묻는 호출 (지침카드 풀이 등, 꺼져 있으면 아무것도 안 더해짐)
next.config.mjs       /api → http://127.0.0.1:8765 (환경 변수 SIM_SERVER로 바꿈)
```

## 원본·설계서와 다른 점 (남은 한계)

| 항목 | 내용 |
|---|---|
| 3D 색·모델 | 원본(가공 초록 등, 둥근 모델·조명·블룸). 상태 색 규칙 C·단순 도형은 안 함 (사용자 결정) |
| 지게차·자동창고·크레인 | 원본 그대로 남김. 공장 동쪽 벽(28 m) 밖으로 밀어 둠 |
| 설비 모양 | 자리·크기만 데이터. SAW-01 정면 방향은 안 돌림 |
| 재공 그림 | 숫자는 데이터 값 그대로. 3D에 쌓이는 부품은 원본 그릇 크기까지만 (회전 테이블 11개, 상자 30개) |
| AI 비서 | 규칙 기반 (답에 `engine: rule`). 외부 LLM은 기본 꺼짐 — 시연 서버를 `MOM_LLM_COMPOSE=1`로 켜면 비서(8100)가 교대·일일 보고서, 작업지시서 제목·증상, 지침카드 풀이 문장을 다듬는다 (`assistant/실행_안내.md` 6-3). 채팅 탭은 별도 스위치(`NEXT_PUBLIC_MOM_API`) |
| 저장 | 화면에서 만든 작업지시서·작업기록서·간이 기록·정지 사유·알림 처리는 브라우저(localStorage, 시연 회차별). 보고서·로트 보류·재고·출하·설정은 서버 메모리 — 서버를 끄면 사라짐. DB 없음 |
| 3D 느림 | 처음 30프레임 뒤 4초 평균이 8 fps 미만이면 2D 배치도로 바뀜 ([3D 다시 보기]로 돌아감) |

3D에 무엇을 넣고 무엇을 남겼는지 항목별 표는 `../못들어가는것들.md` 6장.

## 참고 (원본에서)
- FactoryDashboard.tsx는 원본 대형 파일이라 타입 검사를 꺼 두었다(@ts-nocheck). `src/shell/`은 strict.
- reactStrictMode는 꺼 두었다. 켜면 개발 모드에서 3D 장면이 두 번 만들어진다.
