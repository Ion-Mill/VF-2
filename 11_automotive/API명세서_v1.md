# API 명세서

| 항목 | 내용 |
|---|---|
| 문서 버전 | **v1** (2026-10-07, 첫 작성. 2026-10-08 시연 API 수정, 2026-10-13 일일 보고서 제작 확정, 2026-10-13 AI 비서 사이드바·알림 전달, 2026-10-17 비서 LLM 외부 Claude 확정 — 7장) |
| 근거 | [기획서_최종본.md](기획서_최종본.md) 12.5·13장, [요구사항정의서_최종본.md](요구사항정의서_최종본.md), [UI설계서_최종본.md](UI설계서_최종본.md) 5장, [논리ERD_최종본.md](논리ERD_최종본.md) |
| 함께 보는 문서 | [테스트계획서_v1.md](테스트계획서_v1.md) (API ID를 시험 항목에 씀) |
| 범위 | 화면·서버·비서가 주고받는 **약속**(주소, 보내는 값, 돌려받는 값, 권한, 오류). 서버 안쪽 구현·비서 안쪽(모델·검색 방식)은 다루지 않음 |

표시: **[제안]** 팀 확정 전 / **[선택 필요: 기술 회의]** 기술을 고른 뒤 정함 / **[보류]** 제작 보류 기능 (2026-10-13 일일 보고서 해제 뒤 해당 없음)

---

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 주소·형식 | `/api/...` 아래, 요청·응답은 JSON [제안]. 실제 방식(REST 등)·서버 프레임워크는 [선택 필요: 기술 회의] |
| 로그인 | `API-AUTH-01`로 로그인 뒤 모든 요청에 로그인 정보를 붙임. 방식(세션·토큰)은 [선택 필요: 기술 회의] (NFR-SEC-07) |
| 권한 | 기획서 13장 권한표 그대로. 화면에서 버튼을 숨겨도 **서버가 다시 확인하고 거부** (NFR-SEC-05). MGR은 모든 조회 가능 |
| 이름 | 응답 칸 이름은 논리 ERD 속성 이름을 그대로 씀 (예: `target_qty`, `carry_over_qty`) |
| 시각 | `2026-10-01T10:20:00+09:00` 모양. 교대는 `shift_id` (예: `2026-10-01-D`). **시연 모드에서는 모든 시각이 시뮬레이터 시계 기준** (일시정지·배속·넘기기를 따름, NFR-DATA-10) |
| 숫자 | 단위 칸을 함께 (`psi`·`bar` 둘 다). 추정 값은 `is_estimated: true` (FR-AST-COM-19) |
| 가상 표시 | 모든 운영 데이터 응답에 `is_synthetic: true` (NFR-DATA-08) |
| 문서 공통 | 문서 응답에 `status`(AI비서 초안 / 수정 중 / 확정 …), `version`, 칸별 출처(`ai` / `edited_by` / `program`) |
| 고치기 | 문서를 고치는 요청은 `version`을 함께 보냄. 다르면 `CONFLICT_VERSION` (다른 사람이 먼저 고침) |
| 확정 후 수정 | `reason` 필수 → 새 버전 + 수정 알림 (FR-AST-03-06·07) |
| 출처 | 비서·지침카드·초안의 출처는 `{doc_name, doc_no, rev, section}`만. **원문 출처 칸 없음** (D-03) |
| API ID | 모든 API ID 앞에 `API-`를 붙인다 (예: `API-MNT-01`, `API-DOC-01`, `API-QLT-01`). 기능 ID(MNT-01 지침카드 등)·사내 문서 번호(DOC-01 등)와 헷갈리지 않게 하려는 것 (2026-10-10). 다른 문서에서도 같은 모양으로 쓴다 |
| 목록 | 긴 목록은 `page`, `size`로 나눔 [제안] |

**오류 형식:** `{ "code": "...", "message": "쉬운 한국어 문장", "detail": {...} }`

| code | 뜻 | 예 |
|---|---|---|
| `UNAUTHORIZED` | 로그인 안 됨 | 로그인 없이 요청 |
| `FORBIDDEN` | 역할에 권한 없음 | OPR가 교대 보고서 확정 |
| `NOT_FOUND` | 없는 기록 | 없는 로트 번호 |
| `VALIDATION` | 값이 틀림·빠짐 | 확정 후 수정에 사유 없음 |
| `INVALID_STATE` | 지금 상태에서 할 수 없음 | 승인 전 [작업 시작], 담당 없이 승인, 체크 9칸 덜 채우고 확정, 보류 로트 출하, 잠긴 사건 버튼 |
| `CONFLICT_VERSION` | 버전 충돌 | 두 사람이 같은 문서를 동시에 고침 |
| `ASSISTANT_UNAVAILABLE` | 비서 응답 없음·형식 틀림 | 외부 LLM 호출 실패(설정을 끔·로그인 만료·한도·외부 장애) → 화면은 기본 문구로 (FR-AST-02-14, NFR-AIQ-09) |

---

## 2. API 목록

역할: O = OPR, M = MNT, S = SUP, G = MGR, 전 = 전원. "조회"는 MGR 포함.

### 2.1 로그인·공통

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-AUTH-01 | POST `/api/auth/login` | 로그인 (시연: 가상 사용자 고르기) | 전 | `user_id` (+ 비밀번호 [선택 필요]) | 사용자, 역할, 담당 공정(OPR은 두 개까지), 첫 화면 (팝업 없음 — 확정 안 된 일일 보고서는 DAILY_REPORT_PENDING 알림 말풍선으로, API-NTF-01) | SCR-01, NFR-SEC-01·07, NFR-USE-08 |
| API-AUTH-02 | POST `/api/auth/logout` | 로그아웃 | 전 | — | — | SCR-01 |
| API-AUTH-03 | GET `/api/me` | 내 정보·권한 | 전 | — | 역할, 할 수 있는 일 목록 | UI설계서 2.9, NFR-SEC-02·03 |
| API-AUTH-04 | POST `/api/demo/role` | 역할 바꿔 보기 (**시연 모드만**) | 전 | `role` | 바뀐 역할, 첫 화면 (API-AUTH-01과 같음) | NFR-DATA-12 |

### 2.2 3D 라인 뷰·생산 (PRD-01·03·06)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-LINE-01 | GET `/api/line/layout` | 공장·설비 실제 크기 배치 | 전 | — | 공장 크기, 배치 물체, 설비 외형·좌표, 부품 도형 | SCR-04·05·06·26, FR-PRD-01-01·27 |
| API-LINE-02 | GET `/api/line/twin` | 지금 상태 한 번에 | 전 | `shift_id` | 설비별 상태·지속 시간·현재 로트·현재 알람·이번 교대 실적/목표·정지 시간·손실 합계, 재공 WIP-1~4, 병목(공정·원인·시작) | SCR-04·05·26, FR-PRD-01-03~13·16 |
| API-LINE-03 | GET `/api/production/target` | 목표 대비 실적·예측 | 전 | `shift_id` | `target_qty`, `carry_over_qty`, 총 목표, 실적, 예측, 부족 수량, 위험 여부, 시간대별 실적(그래프) | SCR-02~05·15·26, FR-PRD-01-15, FR-AST-02-04 |
| API-LINE-04 | GET `/api/kpi` | 지표 | 전 | 범위(라인/설비), `from`, `to` | OEE, 가동률, 성능, 양품률, MTTR·MTBF(30일), 주의 표시 | SCR-04 [8], SCR-10 [6], SCR-16, FR-PRD-01-20~23 |
| API-LINE-05 | GET `/api/production/orders` | 작업지시 진행 표 | 전 | `shift_id` | 작업지시별 목표·완료·불량·로트·공정·납기·지연 여부·상태 | SCR-04 [11], FR-PRD-03-01~04 |
| API-LINE-06 | GET `/api/replay` | 다시 보기 | 전 | `from`, `to` | 시각별 상태·재공·센서(5초/1분)·알람·병목 사건 | SCR-06, FR-PRD-06-01~09 |
| API-LINE-07 | GET `/api/downtimes` | 정지 구간 목록 + 비서 추천 | 전 | `shift_id`, 설비, 미확정만 | 구간, 길이, 상태, 사유, 추천 사유(AI비서 초안) | SCR-14 **(필요 여부 판단 중)**, FR-PRD-01-18·19 |
| API-LINE-08 | PATCH `/api/downtimes/{id}` | 정지 사유 입력 / 확정 | 입력 O·M / 확정 S | `reason_code` 또는 `confirm` | 바뀐 구간 | SCR-14, FR-PRD-01-19 |

### 2.3 알림·실시간 (AST-02)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-NTF-01 | GET `/api/notifications` | 알림 목록 | 전 (자기 역할분, MGR 전부) | 처리 상태, 정렬(최근/보고 순위), 중요도, 설비, 칸(고장·확인 / 문서) | 알림 카드(중요도, 보고 순위, ×N 묶음, 폭주 묶음 = 1건, 24시간 넘음, 관련 정보 한 줄, 처리할 사람, **전달 방식**(팝업 / 말풍선 / 목록 — `delivery_kind`), 문서 알림이면 열 문서 주소), 전체 N건·순위별 건수, 처리 안 된 수(이브 아이콘 숫자 = 고장·확인 + 문서) | SCR-07(사이드바 알림 탭), FR-AST-02-01~19 |
| API-NTF-02 | POST `/api/notifications/{id}/read` | 읽음 (처리 아님) | 받는 사람 | — | — | SCR-07 |
| API-NTF-03 | POST `/api/notifications/{id}/resolve` | 처리 | 처리 칸의 역할만 | 반복 알람은 `action_plan` 필수, 메모 | 처리 시각·사람 | SCR-07, FR-AST-02-13·03 |
| API-NTF-04 | POST `/api/notifications/{id}/ack` | 긴급 팝업 확인 (소리 끔, 처리 아님) | 로그인한 전원 (팝업을 받은 사람. 처리 책임은 그 설비 O·M, 처리는 작업기록서·간이 작업기록 확정 때 자동) | — | — | SCR-08, FR-AST-02-02 |
| API-STR-01 | GET `/api/stream/events` | **실시간** 서버 → 화면 | 전 | — | 아래 3장 사건 | 전 화면, NFR-PERF-02 |

### 2.4 비서·사내 문서 (AST-01, MNT-01) — 바깥 모양만, 안쪽은 LLM 담당

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-AST-01 | GET `/api/assistant/briefing` | 교대 시작 브리핑 | 전형 S·M·G / 요약형 O | `shift_id`, `view`(full/operator) | 지난 교대 3줄(양품·손실 / 설명 / 나머지, 잠정 여부), 먼저 챙길 일(보고 순위 목록 전부, 전체 N건·순위별), 이번 교대 3줄(총 목표 = 목표 + 이월 / 작업지시 / 예방 정비). 화면은 자동으로 열지 않고 이브 말풍선("이번 교대 브리핑이 준비됐어요") → 사이드바 브리핑 탭에서 부름 | SCR-02·03·26, FR-AST-01-01~07, FR-AST-COM-21 |
| API-AST-02 | GET·POST `/api/assistant/chat` | **POST** = 비서에게 질문 (질문·답을 `chat_log`에 저장) / **GET** = 내 채팅 기록 (30일, 본인 것만 [제안]) | 전 (답은 역할이 볼 수 있는 것만. **채팅 권한: MTTR(지표)·센서 데이터(센서 추세)는 M·G만** [가상: 2026-10-13 팀 결정], 사내 문서 검색은 전원. 서버가 조회 도구를 부르기 전에 역할 확인) | POST: `question`, `context`(화면·설비·알람), 이어서 물을 때 앞 `chat_id` [제안] / GET: 기간(30일 안) | POST: `chat_id`, `answer`, `sources[]`, `related[]`(기록 번호), `status`(ok / 문서에 없음 / 거부 / **권한 밖** / 응답 없음 — 권한 밖이면 값 없이 누가 볼 수 있는지만) / GET: 내 기록 목록(질문 시각, 질문, 답, 출처, 상태) | SCR-10 (채팅·채팅 기록 탭), FR-MNT-01-01~12, FR-AST-COM-01~20, NFR-SEC-05 |
| API-DOCS-01 | GET `/api/internal-docs/{doc_no}/sections/{section}` | 출처 요약 카드·팝업 창 | 전 | `view`(card/full) | 문서 이름·번호·개정·절 제목, 앞 2~3줄 또는 본문 | SCR-24, FR-MNT-01-09 |
| API-DOCS-02 | POST `/api/internal-docs/{doc_no}/revisions/{rev}/approve` | 사내 문서 개정 승인 | G | — | 새 현행판, 수정 알림 | SCR-24, FR-AST-03-09 |

**API-AST-02 딸림 — 채팅 마이크 (2026-10-20 [제안], API 수 63개 그대로):** 이브 채팅 입력줄의 마이크 버튼이 쓰는 두 경로. 둘 다 API-AST-02와 같은 권한(로그인 전원, 권한 `ASSISTANT INPUT`)이다.
- **POST `/api/assistant/transcribe`**: 본문 = 녹음된 소리 **원본 바이트**(`Content-Type`은 브라우저가 만든 `audio/webm;codecs=opus`·`audio/mp4` 등, 상한 약 1.5MB, 길이는 비서 설정 `VOICE_MAX_SECONDS`(기본 20초·최대 60초)). 백엔드가 사내 서버의 AI 비서(`POST /transcribe`)로 그대로 넘기고, 돌려받은 `{text, reason, seconds, ms}`를 준다. `text`가 비면 `reason`(`too_short`·`no_speech`·`hallucination`·`repeated`·`hint_echo`)이 까닭이다. 소리는 저장하지 않고, 접근 기록에는 길이·걸린 시간·글자 수만 남기며 글자는 남기지 않는다. 글자를 질문으로 보내는 것은 사용자가 입력창에서 확인한 뒤 API-AST-02 POST로 한다.
- **GET `/api/assistant/voice`**: `{enabled, ready, max_seconds}` — 마이크 버튼을 보일지. 비서가 없거나 음성 스위치가 꺼져 있으면 `enabled=false`(오류로 돌려주지 않는다).
- 오류는 새 코드 없이 위 7개로: 음성 꺼짐 = `NOT_FOUND`, 소리가 비었거나 읽지 못함·너무 큼·너무 김 = `VALIDATION`, 인식이 바쁨·시간 초과·실패·비서 연결 안 됨 = `ASSISTANT_UNAVAILABLE`. 자세한 갈래는 `detail.reason`(`VOICE_OFF`·`BAD_AUDIO`·`AUDIO_TOO_LARGE`·`AUDIO_TOO_LONG`·`VOICE_BUSY`·`VOICE_TIMEOUT`·`VOICE_FAILED` 등).

### 2.5 정비 (MNT-02~05)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-MNT-01 | GET `/api/maint/guide-card/{alarm_event_id}` | 지침카드 | 전 | — | 알람·심각도·누가·연쇄 알람·먼저 할 일·안전 블록(고정 서식)·생산 영향·지난 기록·출처 목록·버튼 | SCR-09, FR-MNT-02-01~14 |
| API-MNT-02 | GET `/api/maint/work-orders` | 작업지시서 목록 | 전 | 상태, 내 것만 | 목록 | SCR-18 |
| API-MNT-03 | GET `/api/maint/work-orders/{id}` | 작업지시서 | 전 | — | 계기, 자동 칸, 제목·증상, 작업 순서, 차단 지점, 안전 블록(읽기 전용), 비슷한 과거, 예상 부품, 담당, 상태, 승인 대기 시간, 출처 | SCR-11, FR-MNT-03-01~14 |
| API-MNT-04 | PATCH `/api/maint/work-orders/{id}` | 내용 수정 | M | `version`, 고친 칸 | 새 버전 | SCR-11 |
| API-MNT-05 | POST `.../work-orders/{id}/assign` | 담당 지정 | S | `mnt_user_id` | — | FR-MNT-03-14 |
| API-MNT-06 | POST `.../work-orders/{id}/approve` | 승인 (MGR 대리 승인) | S·G | `version` | 상태 = 승인 (담당 없으면 `INVALID_STATE`). 승인되면 담당 MNT에게 "작업지시서 배정" 알림 (`WO_ASSIGNED`) | FR-MNT-03-13·14 |
| API-MNT-07 | POST `.../work-orders/{id}/start` | 작업 시작 | 담당 M | — | 상태 = 진행 중 (승인 전이면 거부) | FR-MNT-03-02 |
| API-MNT-08 | POST `.../work-orders/{id}/cancel` | 취소 | G | `reason` | 상태 = 취소 | SCR-11 |
| API-MNT-09 | GET·PATCH `/api/maint/work-records/{id}` | 작업기록서 조회·수정 | 조회 전 / 수정 M | `version`, 고친 칸, 체크 9칸, 사용 부품 | 칸 전부 | SCR-12, FR-MNT-05-01~08 |
| API-MNT-10 | POST `.../work-records/{id}/assist` | 메모를 비서로 정리 | M | `memo` | AI비서 초안 칸 | FR-MNT-05-02 |
| API-MNT-11 | POST `.../work-records/{id}/confirm` | 확정 → 작업지시서 완료, 재고 차감, MTTR 다시 계산 | M | `version` | 확정, 바뀐 기록 번호 (체크 9칸 덜 차면 거부) | FR-MNT-05-05·09·10·14 |
| API-MNT-12 | POST `/api/maint/quick-records` · `/{id}/confirm` | 간이 작업기록 저장·확정 | 저장 O·M / 확정: 주의 O·M, 다른 공정 정지 M | 알람(또는 원인 점검 요청), 조치, 체크 9칸 | 기록 번호 | SCR-13, FR-MNT-05-13·15 |
| API-PM-01 | GET `/api/maint/pm-schedule` | 예방 정비 일정 | 전 | 설비, 기간 | 항목·주기·다음 기한·상태, 제때 실시율, 잠금·표지 판단 | SCR-23, FR-MNT-04-01~04·08·09 |
| API-PM-02 | POST `/api/maint/pm-records` | 정비 시작·끝 기록 (MAINT 상태). 시연 모드의 S6 정비는 시작·끝을 시뮬레이터가 기록하고 MNT는 실시 기록을 확인 | M | `pm_task_id`, 시작/끝, 실시자 | 실시 기록 (소모품 차감, MAINT 상태) | SCR-23, FR-MNT-04-05~07·10 |

### 2.6 보고서·문서 (PRD-02·04, AST-03)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-RPT-01 | GET `/api/reports/shift/{shift_id}` | 교대 보고서 | 조회 전 | — | 생산(총 목표·실적·불량·가동률), 로트, 필수 정지, 병목, 정비, 특이 사항, 인계 사항, 상태 | SCR-15, FR-PRD-02-01~12 |
| API-RPT-02 | PATCH `/api/reports/shift/{shift_id}` | 저장 | 그 교대 S | `version`, 고친 칸 | 새 버전 | FR-PRD-02-10 |
| API-RPT-03 | POST `.../shift/{shift_id}/confirm` | 확정 | 그 교대 S | `version` | 확정·잠김 | FR-PRD-02-11 |
| API-RPT-04 | POST `.../shift/{shift_id}/revise` | 확정 후 수정 | 그 교대 S | `reason`, 고친 칸 | 새 버전, 수정 알림 | FR-AST-03-06·07 |
| API-RPT-05 | GET·PATCH `/api/reports/daily/{date}` · `/confirm` | 일일 보고서 | 조회 S·M·G / 확정 G | `version` | 하루 생산(목표 180·실적·부족), 손실, 알람, 정비, 로트, 재고, 오늘의 문제 | SCR-16, FR-PRD-04-01~10 |
| API-DOC-01 | GET `/api/documents` | 문서함 | 전 (역할분) | 종류, 상태, 내 할 일 | 문서 목록 | SCR-18, FR-MNT-05-11·12 |
| API-DOC-02 | GET `/api/documents/{type}/{id}/revisions` | 수정 이력 | 전 (OPR은 자기 문서) | — | 버전 목록, 바뀐 칸, 사유 | SCR-17, FR-AST-03-01~09 |

### 2.7 로트·품질 (PRD-05, QLT-01)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-LOT-01 | GET `/api/lots` · `/{lot_no}/trace` | 로트 목록 · 추적 | 전 | 작업지시, 상태 | 원자재 → 공정 실적 → 검사 → 출하, 의심 로트 제안 | SCR-19, FR-PRD-05-01~05·09~11 |
| API-LOT-02 | POST `/api/lots/{lot_no}/hold` · `/release` | 보류 · 해제 | S·G | `reason` (해제는 합격 수량) | 로트 상태 | SCR-19, FR-PRD-05-06·07 |
| API-LOT-03 | POST `/api/lots/{lot_no}/scrap` · `/scrap/approve` | 폐기 제안 · 승인 | 제안 S / 승인 G | `reason` | 로트 상태 | FR-PRD-05-08 |
| API-QLT-01 | GET `/api/inspection/results` | 검사 기록 | 전 | 로트 | 측정값, 입력 방식(자동/수동), 부품 온도, 확인 상태 | SCR-20, FR-QLT-01-01~07 |
| API-QLT-02 | POST `/api/inspection/results` | 게이지·외관 결과 / 수동 입력 ("수동" 표시) | O(측정 담당)·S | 로트, 부품 번호, 항목, 결과 | 기록 | SCR-20, FR-QLT-01-01·19 |
| API-QLT-03 | POST `/api/inspection/results/{id}/select` | 재측정 값 고르기 · 반장 확인 | S | 고른 측정 | 확인 상태 = 반장 확인 | FR-QLT-01-20~22 |
| API-QLT-04 | GET `/api/inspection/cmm-imports` | 결과 파일 기록·오류 목록 | 전 | 상태 | 파일 이름, 받은 시각, 상태, 오류 | SCR-20, FR-QLT-01-14~18 |
| API-QLT-05 | GET `/api/quality/summary` | 불량 집계·관리도·Cpk | 전 | 기간 | 불량 코드별 수, 관리도, Cpk (50개 미만이면 "계산 중") | SCR-20, FR-QLT-01-08~13 |

- 측정 결과 파일 읽기(공유 폴더 감시 → `cmm_import`)는 **서버 안쪽 일**이라 API가 아니다. 폴더 위치·감시 방식은 [선택 필요: 기술 회의].

### 2.8 재고·출하·공구 (INV-01, ML-01)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-INV-01 | GET `/api/inventory` | 재고 13품목 | 전 | — | 재고, 안전 재고, 관리 역할, 부족 여부, 완제품·보류 수량 | SCR-21, FR-INV-01-01~03·09·11 |
| API-INV-02 | POST `/api/inventory/txns` | 입고 · 실사 조정 | 그 품목 관리 역할 (소모품 M / 공구·원자재·완제품 S) | 품목, 종류, 수량, 사유 | 거래 기록 | FR-INV-01-04·08·13 |
| API-INV-03 | POST `/api/raw-lots/{id}/inspect` | 원자재 입고 검사 (성적서 대조) | S | 결과 | 사용 가능 / 입고 보류 | FR-INV-01-04 |
| API-INV-04 | GET·POST `/api/shipments` · PATCH `/{id}` | 출하 조회 · 등록 · 확정 후 수정 | 조회 전 / 등록 S | 출하처, 로트·수량 (합격 로트만, 먼저 합격한 로트부터 제안) / 수정은 `reason` | 출하 번호 (보류 로트면 `INVALID_STATE`) | SCR-21, FR-INV-01-12 |
| API-INV-05 | PATCH `/api/inventory/items/{id}/safety-stock` | 안전 재고 설정 | G | 값 | — | SCR-25, FR-INV-01-06 |
| API-TOOL-01 | GET `/api/tools` | 공구 수명 | 전 | 설비 | 사용률·단위·한도·남은 수명(남은 부품 수) | SCR-22, FR-ML-01-01~05·08 |
| API-TOOL-02 | POST `/api/tools/{id}/change` | 공구 교체 기록 → 사용량 0, 재고 사용 | O·M | 사유 | 교체 기록 | SCR-22, FR-ML-01-06, FR-INV-01-05 |

### 2.9 설정·시연 (MGR, 시연 모드)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-SET-01 | GET·PATCH `/api/settings/notification-rules` | 알림 기준값·재발 확인 기간 | G | 값 | — | SCR-25, FR-AST-02-16 |
| API-SET-02 | GET·PATCH `/api/settings/targets` | 교대 목표(90)·하루 목표(180) | G | 값 | — | SCR-25 |
| API-SET-03 | GET·PATCH `/api/settings/users` | 사용자·역할 | G | 값 | — | SCR-25, NFR-SEC-04 |
| API-SIM-01 | POST `/api/sim/inject` | **사건 버튼** — 누른 때(시연 시계 지금) 사건 시작 (S1·S3·S4·S6, S2·S5는 과거 기록이라 버튼 없음) | 시연 모드 | `scenario_code` (시각은 보내지 않음) | 사건 ID(실행 중에만 쓰는 번호, DB 엔터티 아님 — 알람에는 `scenario_code`로 남음), 대상 설비, 시작 시각. 대상 설비가 가공 중(RUN)이 아니거나 진행 중인 사건이 있으면 `INVALID_STATE` (같은 사건 반복은 앞 사건이 끝난 뒤 가능) | NFR-DATA-10, 설계서 7장 |
| API-SIM-02 | GET·POST `/api/sim/clock` | 시연 시계: 조회 / 배속(180·60·10·1배)·일시정지·다시 시작·넘기기 (지금 → 17:00. 넘기는 동안 남은 주간 교대를 만든다. 다음 날 06:00으로 넘기기는 없음, 2026-10-13) | 시연 모드 | POST: `speed` 또는 `paused` 또는 넘길 시각 | 지금 시연 시각, 배속, 일시정지 여부, 진행 중 사건, 버튼별 누를 수 있는지(잠긴 이유) | NFR-DATA-10, 기획서 15장 |
| API-SIM-03 | POST `/api/sim/reset` | 시연 데이터 처음으로 — 10/1 08:00(9/30 끝 상태)으로 되돌림 (리허설용) | 시연 모드 | — | 시연 시각 08:00 | NFR-DATA-10, 테스트계획서 6장 |

- 사건 알람(S1·S3·S4)이 뜨면 시뮬레이터가 **스스로 배속 ×10으로 감속**하고 `sim_clock` 사건을 보낸다 (3장). 다시 올리는 것은 발표자(API-SIM-02).
- 사건 버튼과 시계 조작판은 시연 모드에서만 화면 안에 작게 보인다 (UI설계서 2.1 [14]·9.6).
- **생성기와 잇는 방법** (2026-10-14 [제안], 서버 연결 방식은 [선택 필요: 기술 회의]): 실시간 모드는 생성기 `생성기/gen/realtime.py`의 `Realtime` 객체다. 서버가 이 객체를 만들고 실제 시간마다 `tick(초)`를 부르면 그동안 생긴 사건 목록이 돌아온다.

| API | 생성기 함수 | 비고 |
|---|---|---|
| API-SIM-01 사건 버튼 | `inject("S1"·"S3"·"S4"·"S6")` | 누를 수 없으면 이유("대상 설비 가공 중 아님" / "진행 중 사건 있음")와 함께 거절 → `INVALID_STATE`. 버튼별 상태는 `button_state()` |
| API-SIM-02 시계 | `clock()`, `set_speed()`, `pause()`, `resume()`, `skip()` | 사건 알람이 뜨면 생성기가 스스로 ×10 |
| API-SIM-03 처음으로 | `reset()` | 10/1 08:00, 약 1초 |
| API-LOT-02 로트 보류 | `hold_lot(로트, 반장)` | 그 로트부터 전수 검사 (OP-50 느려짐). S1 의심 로트는 `suspect_lot()` |
| 보류 해제 (로트 판정 뒤) | `release_lot(로트, 반장, 관리자)` | 폐기가 있으면 관리자 승인을 같이 남김 |
| API-TOOL-02 공구 교체 | `record_tool_change(공구, 작업자)` | 사용량 0, SETUP 3~8분 |
| API-MNT-11 작업기록서 확정 | `confirm_work_record(설비)` | S1 고장 설비 복귀 (그 전까지 DOWN) |

| 생성기 사건 (`tick()`) | 3장 실시간 사건 | 내용 |
|---|---|---|
| `state_changed`, `wip_changed`, `bottleneck_changed`, `alarm`, `sim_clock` | 같은 이름 | `alarm`에 `scenario_code` (사건 버튼이면) |
| `event_started` / `event_ended` | `sim_clock` (진행 중 사건·버튼 잠금) | 사건 버튼 시작·끝 |
| `tool_life` | 알림 재료 (공구 사용률 90%, DOC-07 §9) | 서버가 교체 알림을 만듦 |
| `cmm_file` | 측정 결과 파일 도착 | 결과 파일은 `생성기/out_realtime/cmm_drop/`에 실제로 떨어짐 (CMM 조사 5.2 양식, 부품 1개 = 파일 1개). 서버의 결과 파일 읽기(FR-QLT-01-14)를 이 폴더로 시험 |
| `part_count`, `sensor`, `shift_end` | 3D 실적·센서 값·교대 끝 | 교대 끝에 서버가 교대 보고서 AI비서 초안을 만듦 |

  멈춘 때까지의 기록은 `export()`로 `out_realtime/` CSV가 된다 (번호는 9월 다음부터, 논리 ERD 11.1).

---

## 3. 실시간 사건 (API-STR-01)

전송 방식(SSE 등)은 [선택 필요: 기술 회의]. 반영 주기는 NFR-PERF-02 [선택 필요].

| 사건 | 언제 | 담는 것 | 받는 화면 |
|---|---|---|---|
| `state_changed` | 설비 상태가 바뀔 때 | 설비, 새 상태, 시각 | SCR-04·05·26 |
| `wip_changed` / `bottleneck_changed` | 재공 기록 / 병목 바뀜 | 재공 자리별 수 / 병목 공정·원인 | SCR-04·05·26 |
| `alarm` | 알람 발생 | 알람 이벤트, 심각도 | SCR-04·09·26 |
| `urgent_popup` | 정지 등급 알람 | 설비, 알람, 받는 사람(**로그인한 전원**), 처리 책임(그 설비 O·M) | SCR-08 (어느 화면에 있든 중앙 팝업), SCR-26 큰 팝업 |
| `notification` | 알림 생김·처리됨 | 알림 카드, 전달 방식(팝업 / 말풍선 / 목록) | 사이드바 알림 탭(SCR-07), 이브 아이콘 숫자, 말풍선이면 이브 말풍선 |
| `kpi_updated` | 작업기록서 확정 등으로 다시 계산 | 바뀐 지표 | SCR-04 [8] |
| `document_changed` | 초안 생김·확정·수정 | 문서 종류·번호·상태 | SCR-11·12·15·18 |
| `connection` | 연결 끊김·다시 연결 | 마지막 갱신 시각 | 알림 띠 (UI설계서 2.8) |
| `sim_clock` | (시연 모드) 배속·일시정지·넘기기·되돌리기·자동 감속, 사건 시작·끝 | 시연 시각, 배속, 일시정지 여부, 진행 중 사건, 버튼 잠금 상태 | 상단 바 시각, 시연 조작판 |

---

## 4. 서버가 스스로 하는 일 (API 아님)

| 일 | 언제 | 근거 |
|---|---|---|
| 교대 보고서 AI비서 초안 만들기 + 그 교대 SUP에게 확정 요청 알림 | 교대 끝 17:00·05:00 | FR-PRD-02-01, FR-AST-02-17 |
| 일일 보고서 AI비서 초안 만들기 + MGR에게 일일 보고서 확정 요청 알림 (`DAILY_REPORT_PENDING`, 말풍선) | 그 생산일 야간 교대 보고서가 확정될 때(API-RPT-03 성공, 05:00~06:00). 06:00까지 확정이 없으면 06:00 (미확정 교대 칸은 잠정) | FR-PRD-04-01·09 |
| 작업지시서 AI비서 초안 + 그 설비 MNT에게 작업지시서 초안 검토 알림 (`WO_DRAFT_READY`, 말풍선) | OP-30 정지 등급 알람·반복 알람 2단계 | FR-MNT-03-01 |
| 알림 규칙 판단, 보고 순위 매기기 | 기록이 생길 때마다 | FR-AST-02-01~19, FR-AST-COM-21 |
| 지표·손실·이월 계산 | 기록이 생길 때·교대 시작 | DOC-07 6~8장, R-88 |
| 측정 결과 파일 읽기 · 측정 지시 파일 넘기기 | 파일이 생길 때 · 측정 시작 때 | FR-QLT-01-14·15 |
| 보관 기간이 지난 데이터 처리 | 주기 [선택 필요: 기술 회의] | NFR-DATA-13 |
| (시연 모드) 화면 조작을 시뮬레이터에 넘기기: 로트 보류(API-LOT-02) → 그 로트부터 전수 검사, 공구 교체(API-TOOL-02) → 그 공구 사용량 0, 작업기록서 확정(API-MNT-11) → 고장 설비 복귀 | 그 API가 성공할 때 | NFR-DATA-10, 설계서 4장 |
| (시연 모드) 시뮬레이터 시계 따르기: 24시간 미처리·목표 예측·교대 끝 초안 등 시각 계산 | 늘 | NFR-DATA-10 |

---

## 5. 기능 ↔ API 대응

| 기능 | API | 기능 | API |
|---|---|---|---|
| PRD-01 3D 라인 뷰 | API-LINE-01~04·07·08, API-STR-01 | MNT-02 지침카드 | API-MNT-01 |
| PRD-02 교대 보고서 | API-RPT-01~04 | MNT-03 작업지시서 | API-MNT-02~08 |
| PRD-03 작업지시 진행 | API-LINE-05 | MNT-04 예방 정비 | API-PM-01·02 |
| PRD-04 일일 보고서 | API-RPT-05 | MNT-05 작업기록서 | API-MNT-09~12 |
| PRD-05 로트 추적 | API-LOT-01~03 | QLT-01 검사 | API-QLT-01~05 |
| PRD-06 다시 보기 | API-LINE-06 | INV-01 재고·출하 | API-INV-01~05 |
| AST-01 브리핑 | API-AST-01 | ML-01 공구 수명 | API-TOOL-01·02 |
| AST-02 알림 | API-NTF-01~04, API-STR-01, API-SET-01 | AST-03 수정 이력 | API-DOC-01·02, API-RPT-04, API-DOCS-02 |
| MNT-01 질문 답변 | API-AST-02, API-DOCS-01 | AST-COM 비서 공통 | API-AST-01·02, API-MNT-01·10 |
| 공통·권한·시연 | API-AUTH-01~04, API-SET-02·03, API-SIM-01~03 | | |

---

## 6. 남은 [선택 필요]·[보류]

| 항목 | 정할 곳 |
|---|---|
| 주소·형식 방식, 서버 프레임워크, 로그인 방식, 실시간 전송 방식·주기 | 기술 회의 |
| 비서 API 안쪽(모델, 검색 방식, 도구 호출 형식) — 바깥 모양(API-AST-01·02)만 이 문서에서 정함 | LLM 담당 팀원 |
| 권한 밖 답변 문구 (API-AST-02 `status` = 권한 밖일 때, 값 없이 누가 볼 수 있는지만 알리는 방식 [제안]) | LLM 담당 팀원 |
| API-LINE-07·08 정지 사유 화면 | 팀 (필요 여부) |
| 측정 결과 파일 폴더·감시 방식, 보관 기간 처리 주기 | 기술 회의 |

## 7. 개정 기록

| 버전 | 날짜 | 내용 |
|---|---|---|
| v1 | 2026-10-07 | 처음 작성. 기획서 12.5 목록을 API 63개(ID 기준)로 풀고, 공통 규칙·오류 코드·실시간 사건·서버 자동 작업·기능 대응표를 넣음 |
| v1 수정 | 2026-10-08 | 시연 방식 수정 (`구현_중_수정사항/1008_수정간단내용.md`, API 수 63개 그대로): SIM-01 = 사건 버튼(시각 칸 뺌, 잠금 시 `INVALID_STATE`), SIM-02 = GET 조회 + 일시정지, SIM-03 [제안] → 확정(10/1 08:00), 자동 감속, 실시간 사건 `sim_clock`, 시각은 시뮬레이터 시계 기준(1장), 서버 자동 작업에 화면 조작 → 시뮬레이터 넘기기 |
| v1 수정 | 2026-10-10 | API 수 63개 그대로. **모든 API ID 앞에 `API-`** (예: `API-MNT-01`) — 기능 ID·사내 문서 번호와 헷갈리지 않게 (1장 "API ID" 줄, 2장 표, 3·4장 글, 5장 대응표). `API-SIM-02` 배속에 ×180 추가 (`구현_중_수정사항/1010_수정간단내용.md` 9장) |
| v1 수정 | 2026-10-13 | 일일 보고서 제작 확정 (`구현_중_수정사항/1013_수정간단내용.md`, API 수 63개 그대로): API-RPT-05·4장 대응표의 [보류] 뺌, 5장 서버 자동 작업 — 일일 보고서 초안은 **야간 교대 보고서 확정(API-RPT-03) 때**, 없으면 06:00. API-AUTH-01·04 돌려받는 값에 MGR의 확정 안 된 일일 보고서 목록(로그인 팝업용, → 2026-10-13 3차: 말풍선으로 바뀜). API-SIM-02 넘기기는 지금 → 17:00만. 6장에서 일일 보고서·모니터링용 계정 줄 뺌 (모니터링용 계정은 만들지 않음) |
| v1 수정 | 2026-10-13 | 같은 날 2차 (63개 그대로): API-MNT-06 승인 때 담당 MNT에게 작업지시서 배정 알림(`WO_ASSIGNED`). MNT 첫 화면은 SCR-04 (API-AUTH-01 "첫 화면" 값) |
| v1 수정 | 2026-10-13 | 같은 날 3차 — AI 비서 사이드바·알림 전달 (`구현_중_수정사항/1013_수정간단내용.md` 6장, API 수 63개 그대로): API-AUTH-01·04에서 MGR 확정 안 된 일일 보고서 목록(로그인 팝업용) 뺌 → `DAILY_REPORT_PENDING` 말풍선. **API-AST-02 = GET·POST** (POST 질문·답을 `chat_log`에 저장, GET 내 채팅 기록 30일·본인만), 채팅 권한(MTTR·센서 = M·G), `status` "권한 밖". API-AST-01 말풍선으로 엶. API-NTF-01 칸(고장·확인 / 문서) 거르기·전달 방식, API-NTF-04 = 로그인한 전원(처리 아님). 3장 `urgent_popup` 받는 사람 = 로그인한 전원, `notification` 전달 방식. 4장 서버 자동 작업에 `WO_DRAFT_READY`·`DAILY_REPORT_PENDING` 알림. 6장에 권한 밖 답변 문구(LLM 담당) |
| v1 수정 | 2026-10-13 | 같은 날 4차 — S5 버튼 빼기 (`구현_중_수정사항/1013_수정간단내용.md` 9장, API 수 63개 그대로): API-SIM-01 `scenario_code` S1·S3·S4·S6, 자동 감속 알람 S1·S3·S4 |
| v1 수정 | 2026-10-14 | 공구 수명 예측 모델 빼기 (`구현_중_수정사항/1014_수정간단내용.md` 1장, API 수 63개 그대로): API-TOOL-01 응답에서 모델 예측(참고값) 빼고 남은 수명(남은 부품 수) |
| v1 수정 | 2026-10-14 | 같은 날 2차 (`구현_중_수정사항/1014_수정간단내용.md` 3장, API 수 63개 그대로): 2.9 아래 **생성기 실시간 모드와 잇는 방법** [제안] |
| v1 수정 | 2026-10-14 | 같은 날 4차 — 센서 사건 앞뒤 간격 1초 → 5초 (`구현_중_수정사항/1014_수정간단내용.md` 7장, API 수 63개 그대로): API-LINE-06 센서(5초/1분) |
| v1 수정 | 2026-10-14 | 같은 날 3차 (`구현_중_수정사항/1014_수정간단내용.md` 4장, API 수 63개 그대로): 2.9 생성기 연결 표 — 사건 버튼 `inject`, 화면 조작(보류·해제·공구 교체·작업기록서 확정) 함수, 생성기 사건 ↔ 3장 사건, 측정 결과 파일 폴더 |
| v1 수정 | 2026-10-17 | 비서 LLM = 외부 Claude 확정 (`팀과 논의/외부LLM_단일_전환_제안_20261017.md`, API 수 63개 그대로): 오류 코드 `ASSISTANT_UNAVAILABLE`의 예 칸을 "로컬 LLM이 멈춤" → "외부 LLM 호출 실패"로. 주소·값·권한은 그대로 |
| v1 수정 | 2026-10-20 | 채팅 마이크 (`구현_중_수정사항/1020_수정간단내용.md` 45장, API 수 63개 그대로): 2.4 API-AST-02 아래에 딸림 설명 [제안] — POST `/api/assistant/transcribe`(소리 원본 → 글자)·GET `/api/assistant/voice`(마이크 버튼 표시 여부). 같은 권한, 새 오류 코드 없음(`detail.reason`에 `VOICE_*`) |
| v1 수정 | 2026-10-20 | 채팅 마이크 녹음 길이 (`구현_중_수정사항/1020_수정간단내용.md` 47장, API 수 63개 그대로): API-AST-02 딸림 설명의 POST `/api/assistant/transcribe` 상한을 "약 1.5MB·20초"에서 "약 1.5MB, 길이는 서버 설정(기본 20초·최대 60초)"으로. 백엔드는 비서를 최대 45초까지 기다림 |
