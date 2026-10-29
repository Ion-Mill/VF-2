# API 명세서

| 항목 | 내용 |
|---|---|
| 문서 버전 | **v1** (2026-10-07, 첫 작성. 2026-10-08 시연 API 수정, 2026-10-13 일일 보고서 제작 확정, 2026-10-13 AI 비서 사이드바·알림 전달, 2026-10-17 비서 LLM 외부 Claude 확정 — 7장. **2026-10-24 교대 시각 변경(주간 09~18·야간 21~06)과 프로필(영상용·최종용)·기록 기간 반영**) |
| 근거 | [기획서.md](기획서.md) 12.5·13장, [요구사항정의서.md](요구사항정의서.md), [UI설계서.md](UI설계서.md) 5장, [논리ERD.md](논리ERD.md) |
| 함께 보는 문서 | 테스트계획서_v1.md (API ID를 시험 항목에 씀) |
| 범위 | 화면·서버·비서가 주고받는 **약속**(주소, 보내는 값, 돌려받는 값, 권한, 오류). 서버 안쪽 구현·비서 안쪽(모델·검색 방식)은 다루지 않음 |

표시: **[제안]** 팀 확정 전 / **[선택 필요: 기술 회의]** 기술을 고른 뒤 정함 / **[보류]** 제작 보류 기능 (2026-10-13 일일 보고서 해제 뒤 해당 없음)

---

> **2026-10-24 바뀜**: 교대를 **주간 09:00~18:00 · 야간 21:00~06:00**으로 바꿨다 (교대 사이 라인 정지 18:00~21:00·06:00~09:00, 교대 보고서 초안 18:00·06:00, 일일 보고서 늦어도 07:00, 야간 반장 확정 06:00~07:00). 기록 기간과 시연 시작은 **프로필**로 정한다: 영상용(과거 10/1~10/23, 시연 10/24 09:00 가속 시계), 최종용(과거 10/1~10/25, 10/26 09:00~15:00 미리 짠 사건 → 15:00부터 실제 시각). 이 문서의 시각·날짜·번호 예시는 그 기준으로 고쳤고, 개정 기록·결정표처럼 **옛 값을 인용한 이력은 그 당시 기록이라 그대로** 둔다. 프로필별 값은 [가상데이터설계서.md](가상데이터설계서.md)의 "읽는 법" 표, 결정은 [기획서.md](기획서.md) 21장.

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 주소·형식 | `/api/...` 아래, 요청·응답은 JSON. **REST, 서버는 FastAPI** (2026-10-27 코드 기준, `backend/app/routers/`) |
| 로그인 | `API-AUTH-01`로 로그인 뒤 모든 요청에 로그인 정보를 붙임. 방식은 **JWT 토큰**(`Authorization: Bearer`, 유효 12시간, 2026-10-27 코드 기준). 실시간 채널(SSE)은 머리글을 못 붙이므로 `?token=`으로 받는다. 시뮬레이터·AI 비서 서비스는 사람 로그인과 따로 서비스 키(`X-Service-Key`)를 쓴다 (NFR-SEC-07) |
| 권한 | 기획서 13장 권한표 그대로. 화면에서 버튼을 숨겨도 **서버가 다시 확인하고 거부** (NFR-SEC-05). MGR은 모든 조회 가능 |
| 이름 | 응답 칸 이름은 논리 ERD 속성 이름을 그대로 씀 (예: `target_qty`, `carry_over_qty`) |
| 시각 | `2026-10-24T11:20:00+09:00` 모양. 교대는 `shift_id` (예: `2026-10-01-D`). **시연 모드에서는 모든 시각이 시뮬레이터 시계 기준** (일시정지·배속·넘기기를 따름, NFR-DATA-10) |
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
| API-AUTH-01 | POST `/api/auth/login` | 로그인 (아이디 + 비밀번호, 2026-10-24부터) | 전 | `user_id`, `password`(필수). 틀리면 401 `UNAUTHORIZED` | `access_token`·`token_type`(JWT), 사용자, 역할, 담당 공정(OPR은 두 개까지), 첫 화면 (팝업 없음 — 확정 안 된 일일 보고서는 DAILY_REPORT_PENDING 알림 말풍선으로, API-NTF-01) | SCR-01, NFR-SEC-01·07, NFR-USE-08 |
| API-AUTH-02 | POST `/api/auth/logout` | 로그아웃 | 전 | — | — | SCR-01 |
| API-AUTH-03 | GET `/api/me` | 내 정보·권한 | 전 | — | 역할, 할 수 있는 일 목록 | UI설계서 2.9, NFR-SEC-02·03 |
| API-AUTH-04 | POST `/api/demo/role` | 역할 바꿔 보기 (**시연 모드만**) | 로그인 없이도 호출됨 — 시연 모드가 꺼져 있으면 404 `NOT_FOUND`로 막음 | `role`, 선택 `user_id` | 바뀐 역할, 첫 화면 (API-AUTH-01과 같음) | NFR-DATA-12 |

### 2.2 3D 라인 뷰·생산 (PRD-01·03·06)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-LINE-01 | GET `/api/line/layout` | 공장·설비 실제 크기 배치 | 전 | — | 공장 크기, 배치 물체, 설비 외형·좌표, 부품 도형 | SCR-04·05·06·26, FR-PRD-01-01·27 |
| API-LINE-02 | GET `/api/line/twin` | 지금 상태 한 번에 | 전 | `shift_id`, `full`(true면 `sim_control` 등 추가 칸) | 설비별 상태·지속 시간·현재 로트·현재 알람·이번 교대 실적/목표·정지 시간·손실 합계, 재공 WIP-1~4, 병목(공정·원인·바뀐 시각 `changed_at`) | SCR-04·05·26, FR-PRD-01-03~13·16 |
| API-LINE-03 | GET `/api/production/target` | 목표 대비 실적·예측 | 전 | `shift_id` | `target_qty`, `carry_over_qty`, 총 목표, 실적, 예측, 부족 수량, 위험 여부, 시간대별 실적(그래프) | SCR-02~05·15·26, FR-PRD-01-15, FR-AST-02-04 |
| API-LINE-04 | GET `/api/kpi` | 지표 | 전 | `scope`(라인/설비), `shift_id`, `equipment_id`, `from`, `to`(날짜, 31일 넘으면 `VALIDATION`) | OEE, 가동률, 성능, 양품률, MTTR·MTBF(30일), 주의 표시 | SCR-04 [8], SCR-10 [6], SCR-16, FR-PRD-01-20~23 |
| API-LINE-05 | GET `/api/production/orders` | 작업지시 진행 표 | 전 | `shift_id` | 작업지시별 목표·완료·불량·로트·공정·납기·지연 여부·상태 | SCR-04 [11], FR-PRD-03-01~04 |
| API-LINE-06 | GET `/api/replay` | 다시 보기 | 전 | `from`, `to`(24시간까지), `equipment_id`(주면 그 설비 센서만 — 6시간까지, 넘으면 `VALIDATION`) | 시각별 상태·재공·센서(저장된 값을 그대로 돌려줌: 평소 1분 평균, 알람·병목 앞뒤 30분은 5초 간격 — 생성기 `SEC5`와 같음. 백엔드 코드 주석의 "1초"는 옛 설명, 2026-10-27 확인)·알람·병목 사건 | SCR-06, FR-PRD-06-01~09 |
| API-LINE-07 | GET `/api/downtimes` | 정지 구간 목록 + 비서 추천 | 전 | `shift_id`, 설비, 미확정만 | 구간, 길이, 상태, 사유, 추천 사유(AI비서 초안), 기록 칸(이어진 기록 번호 / 기록 없음 / 필요 없음, 2026-10-24 FR-MNT-05-24) **[백엔드 미구현]**: 응답에 작업기록 번호·상태 칸이 없음. 있는 칸은 `reason_suggested_code`·`duration_min`·`reason_status`·`pm_record_id`·`stop_loss_qty` | SCR-14 **(필요 여부 판단 중)**, FR-PRD-01-18·19 |
| API-LINE-08 | PATCH `/api/downtimes/{id}` | 정지 사유 입력 / 확정 | 입력 O·M / 확정 S | `reason_code` 또는 `confirm` | 바뀐 구간 | SCR-14, FR-PRD-01-19 |

### 2.3 알림·실시간 (AST-02)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-NTF-01 | GET `/api/notifications` | 알림 목록 | 전 (자기 역할분, MGR 전부) | 처리 상태, 정렬(최근/보고 순위), 중요도, 설비, 칸(고장·확인 / 문서) | 알림 카드(중요도, 보고 순위, ×N 묶음, 폭주 묶음 = 1건, 24시간 넘음, 관련 정보 한 줄, 처리할 사람, **전달 방식**(팝업 / 말풍선 / 목록 — `delivery_kind`), 문서 알림이면 `doc_type`+`doc_key`), 전체 N건·순위별 건수, 처리 안 된 수 `badge`(`fault` + `doc` = `total`, 이브 아이콘 숫자 = 고장·확인 + 문서) | SCR-07(사이드바 알림 탭), FR-AST-02-01~19 |
| API-NTF-02 | POST `/api/notifications/{id}/read` | 읽음 (처리 아님) | 받는 사람 (MGR은 받는 사람이 아니어도 가능). 아니면 403 `NOT_RECIPIENT` | — | `{updated, processed}` | SCR-07 |
| API-NTF-03 | POST `/api/notifications/{id}/resolve` | 처리 | 처리 칸의 역할만 (DB 함수가 `processor_roles`로 확인) | 반복 알람은 `action_plan` 필수(없으면 `VALIDATION`), 메모 | `notification_id`, `processed_at`, `processed_by` | SCR-07, FR-AST-02-13·03 |
| API-NTF-04 | POST `/api/notifications/{id}/ack` | 긴급 팝업 확인 (소리 끔, 처리 아님) | 로그인한 전원 (팝업을 받은 사람. 처리 책임은 그 설비 O·M, 처리는 작업기록서·간이 작업기록 확정 때 자동) | — | — | SCR-08, FR-AST-02-02 |
| API-STR-01 | GET `/api/stream/events` | **실시간** 서버 → 화면 | 전 | — | 아래 3장 사건 | 전 화면, NFR-PERF-02 |

### 2.4 비서·사내 문서 (AST-01, MNT-01) — 바깥 모양만, 안쪽은 LLM 담당

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-AST-01 | GET `/api/assistant/briefing` | 교대 시작 브리핑 | 전형 S·M·G / 요약형 O | `shift_id`, `view`(full/operator) | 지난 교대 3줄(양품·손실 / 설명 / 나머지, 잠정 여부), 먼저 챙길 일(보고 순위 목록 전부, 전체 N건·순위별), 이번 교대 3줄(총 목표 = 목표 + 이월 / 작업지시 / 예방 정비). 화면은 자동으로 열지 않고 이브 말풍선("이번 교대 브리핑이 준비됐어요") → 사이드바 브리핑 탭에서 부름 | SCR-02·03·26, FR-AST-01-01~07, FR-AST-COM-21 |
| API-AST-02 | GET·POST `/api/assistant/chat` | **POST** = 비서에게 질문 (질문·답을 `chat_log`에 저장) / **GET** = 내 채팅 기록 (30일, 본인 것만 [제안]) | 전 (답은 역할이 볼 수 있는 것만. **채팅 권한: MTTR(지표)·센서 데이터(센서 추세)는 M·G만** [가상: 2026-10-13 팀 결정], 사내 문서 검색은 전원. 서버가 조회 도구를 부르기 전에 역할 확인) | POST: `question`, `context`(화면·설비·알람), 이어서 물을 때 앞 `prev_chat_id`, 선택 `screen_text`(화면 글) / GET: `since`, `limit` (30일은 서버에 고정) | POST: `chat_id`, `answer`, `sources[]`, `related[]`(기록 번호), `status`(OK / NOT_IN_DOCS 문서에 없음 / REFUSED 거부 / **OUT_OF_ROLE 권한 밖** / NO_RESPONSE 응답 없음 — 권한 밖이면 값 없이 누가 볼 수 있는지만) / GET: 내 기록 목록(질문 시각, 질문, 답, 출처, 상태) | SCR-10 (채팅·채팅 기록 탭), FR-MNT-01-01~12, FR-AST-COM-01~20, NFR-SEC-05 |
| API-DOCS-01 | GET `/api/internal-docs/{doc_no}/sections/{section}` | 출처 요약 카드·팝업 창 | 전 | `view`(card/full) | 문서 이름·번호·개정·절 제목(합친 본문 첫 줄의 "문서 > 장 > 절" 경로 머리글), 앞 2~3줄 또는 본문 | SCR-24, FR-MNT-01-09 |
| API-DOCS-02 | POST `/api/internal-docs/{doc_no}/revisions/{rev}/approve` | 사내 문서 개정 승인 | G | — | 새 현행판, 수정 알림 | SCR-24, FR-AST-03-09 |

**API-AST-02 딸림 — 채팅 마이크 (2026-10-20 [제안], API 수 63개 그대로):** 이브 채팅 입력줄의 마이크 버튼이 쓰는 두 경로. 둘 다 API-AST-02와 같은 권한(로그인 전원, 권한 `ASSISTANT INPUT`)이다.
- **POST `/api/assistant/transcribe`**: 본문 = 녹음된 소리 **원본 바이트**(`Content-Type`은 브라우저가 만든 `audio/webm;codecs=opus`·`audio/mp4` 등, 상한 약 1.5MB, 길이는 비서 설정 `VOICE_MAX_SECONDS`(기본·최대 60초)). 백엔드가 사내 서버의 AI 비서(`POST /transcribe`)로 그대로 넘기고, 돌려받은 `{text, reason, seconds, ms}`를 준다. `text`가 비면 `reason`(`too_short`·`no_speech`·`hallucination`·`repeated`·`hint_echo`)이 까닭이다. 소리는 저장하지 않고, 접근 기록에는 길이·걸린 시간·글자 수만 남기며 글자는 남기지 않는다. 글자를 질문으로 보내는 것은 사용자가 입력창에서 확인한 뒤 API-AST-02 POST로 한다.
- **GET `/api/assistant/voice`**: `{enabled, ready, max_seconds}` — 마이크 버튼을 보일지. 비서가 없거나 음성 스위치가 꺼져 있으면 `enabled=false`(오류로 돌려주지 않는다).
- 오류는 새 코드 없이 위 7개로: 음성 꺼짐 = `NOT_FOUND`, 소리가 비었거나 읽지 못함·너무 큼·너무 김 = `VALIDATION`, 인식이 바쁨·시간 초과·실패·비서 연결 안 됨 = `ASSISTANT_UNAVAILABLE`. 자세한 갈래는 `detail.reason`(`VOICE_OFF`·`BAD_AUDIO`·`AUDIO_TOO_LARGE`·`AUDIO_TOO_LONG`·`VOICE_BUSY`·`VOICE_TIMEOUT`·`VOICE_FAILED` 등).

### 2.5 정비 (MNT-02~05)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-MNT-01 | GET `/api/maint/guide-card/{alarm_event_id}` | 지침카드 | 전 | — | 알람·심각도·누가·연쇄 알람·먼저 할 일(`guide_sections`·`easy_desc`·`responder_note`)·안전 블록(고정 서식)·생산 영향·지난 기록·출처 목록·버튼 | SCR-09, FR-MNT-02-01~14 |
| API-MNT-02 | GET `/api/maint/work-orders` | 작업지시서 목록 | 전 | 상태, 내 것만 | 목록 | SCR-18 |
| API-MNT-03 | GET `/api/maint/work-orders/{id}` | 작업지시서 | 전 | — | 계기(`trigger_kind`), 자동 칸, 제목·증상, 작업 순서, 안전 블록(읽기 전용, `safety_block_doc_rev`·`has_high_voltage_notice`), 예상 부품, 담당, 상태, 승인 대기 시간, 출처 | SCR-11, FR-MNT-03-01~14. 차단 지점·비슷한 과거는 이 응답이 아니라 API-MNT-01(`isolation_points`·`same_cases`)에 있다 |
| API-MNT-04 | PATCH `/api/maint/work-orders/{id}` | 내용 수정 | M | `version`, 고친 칸(제목·증상·작업 순서만), 확정된 문서면 `reason` 필수(`REASON_REQUIRED`) | 새 버전 | SCR-11 |
| API-MNT-05 | POST `.../work-orders/{id}/assign` | 담당 지정 | S | `mnt_user_id` | — | FR-MNT-03-14 |
| API-MNT-06 | POST `.../work-orders/{id}/approve` | 승인 (반장만) | S | `version` | 상태 = 승인 (담당 없으면 `INVALID_STATE`). 관리자는 거절. 승인되면 담당 MNT에게 "작업지시서 배정" 알림 (`WO_ASSIGNED`). 응답 `proxy` 는 거짓 | FR-MNT-03-13·14 |
| API-MNT-07 | POST `.../work-orders/{id}/start` | 작업 시작 | 담당 M | — | 상태 = 진행 중 (승인 전이면 거부) | FR-MNT-03-02 |
| API-MNT-08 | POST `.../work-orders/{id}/cancel` | 취소 (권한 없음) | — | `reason` | 거절. 상태 칸은 남음 | SCR-11 |
| API-MNT-09 | GET·PATCH `/api/maint/work-records/{id}` | 작업기록서 조회·수정 | 조회 전 (단 OPR은 간이 기록만, 정식 기록은 403) / 수정 M (간이 기록은 OPR도) | `version`, 고친 칸, 체크 9칸, 사용 부품 | 칸 전부 | SCR-12, FR-MNT-05-01~08 |
| API-MNT-10 | POST `.../work-records/{id}/assist` | 메모를 비서로 정리 | M (선조치 간이 작업기록은 O·M으로 하기로 했으나 **[백엔드 미구현]**: 지금 코드는 MNT만, OPR은 403). 비서가 없으면 `ASSISTANT_UNAVAILABLE` | `memo` | AI비서 초안 칸 (원인은 고장 대응 안내 DOC-03의 원인 중에서, 없으면 "모름"). 사진은 비서로 보내지 않음 | FR-MNT-05-02·18 |
| API-MNT-11 | POST `.../work-records/{id}/confirm` | 확정 → 작업지시서 완료, 재고 차감, MTTR 다시 계산 | M | `version` | `{record_no, status: CONFIRMED}` (작업지시서 완료·재고 차감·MTTR는 DB 함수가 하고 결과는 응답에 없음) (체크 9칸 덜 차면 거부) | FR-MNT-05-05·09·10·14 |
| API-MNT-12 | POST `/api/maint/quick-records` · `/{id}/confirm` | 간이 작업기록 저장·확정 | 저장 O·M / 확정: 주의 O·M, 다른 공정 정지 M | 알람(또는 원인 점검 요청), 조치, 체크 9칸. 코드 요청 칸은 `equipment_id`(필수), `start_at`, `lot_no`, `worker_memo`, `safety_block_required`. **선조치 기록이면** (2026-10-24, **[백엔드 미구현]**: `urgent_reason_*`·`loto_skip_reason`·작업 끝 시각이 아직 코드에 없음) 알람 비움, 작업 시작·끝 시각, `urgent_reason_code`·`urgent_reason_text`, 잠금·표지 안 했으면 `loto_skip_reason` 필수 | `{record_no}`. 선조치 기록 확정 (**[백엔드 미구현]**): 재고 차감, 이어진 정지 구간에 사유 추천, MTTR·MTBF에는 넣지 않음. 보전 범위 일을 했거나, 잠금·표지를 했거나, 부품을 쓴 선조치 기록은 M만 확정 | SCR-13, FR-MNT-05-13·15·18~20·22 |
| API-MNT-13 | GET `/api/maint/unrecorded-stops` | 기록 없는 정지 목록 (2026-10-24) | 전 | 설비, `shift_id` | 구간마다 `state_log_id`, 설비, 시작·끝, 길이, 상태(DOWN·IDLE), 사유(비었음 / 고장 F 그룹), 알림 등급(ⓘ 참고 / ▲ 주의) | SCR-07·14·15, FR-MNT-05-23·24, FR-AST-02-20 |
| API-MNT-14 | POST `/api/maint/quick-records/after-the-fact` | 선조치 기록 만들기 — 알람 없이 먼저 한 일 (2026-10-24) | O·M | `state_log_id` (정지 구간에서) **또는** `equipment_id` + 작업 시작·끝 시각 (설비를 돌린 채 한 일), `urgent_reason_code`, `urgent_reason_text`(선택), `memo`(선택) | 기록 번호(`SIMPLE`, `MR-S-…`), `after_the_fact` = 참, 채운 작업 시각, 정지 구간과 시각이 다르면 경고. 미래 시각·진행 중인 일이면 `VALIDATION`. 이어 쓰기·저장·확정은 API-MNT-12, 메모 정리는 API-MNT-10(같은 `work_record` 번호) | SCR-13·14·18·26, 알림(SCR-07)·교대 보고서(SCR-15)에서 열기, FR-MNT-05-16~20 |
| API-MNT-15 | GET·POST `/api/maint/work-records/{id}/photos` · GET·DELETE `/{photo_seq}` | 작업기록 사진 목록·올리기·내려받기·빼기 (2026-10-24) — 간이 작업기록·작업기록서 모두 | 보기 전 / 올리기·빼기 그 기록을 쓰는 O·M | POST: 사진 파일 (multipart, JPG·PNG, 한 장 10MB 이하 [가상]) | `photo_seq`(1~3), `uploaded_by`, `uploaded_at`, 내려받기는 파일. 4장째·형식·크기 틀림 `VALIDATION`, 확정 뒤 올리기·빼기 `INVALID_STATE` | SCR-12·13, FR-MNT-05-26 |
| API-MNT-16 | POST `/api/maint/quick-records/{id}/check` | 선조치 기록 반장 확인 (2026-10-24) | S | `version` | `checked_by`, 확인 시각, 상태 = 확인. 확정 전이거나 선조치 기록이 아니면 `INVALID_STATE`. 확인 대기 알림(`AFTER_RECORD_CHECK_WAIT`)은 처리됨 | SCR-13, FR-MNT-05-21, FR-AST-02-21 |
| API-PM-01 | GET `/api/maint/pm-schedule` | 예방 정비 일정 | 전 | `equipment_id`, `from`·`to`(제때 실시율에만 적용, 일정 목록은 안 거름) | `items`(항목명·주기·다음 기한·`days_overdue`·`last_status`·`lockout_level`), `on_time`(제때 실시율), `today_records`, `open_windows` | SCR-23, FR-MNT-04-01~04·08·09 |
| API-PM-02 | POST `/api/maint/pm-records` | 정비 시작·끝 기록 (MAINT 상태). 시연 모드의 S6 정비는 시작·끝을 시뮬레이터가 기록하고 MNT는 실시 기록을 확인 | M | `pm_task_id`, `due_date`·`result`(필수), `done_by`, `done_at`, `measured_*`, `memo`. **시작·끝은 따로**: POST `/api/maint/pm-tasks/{id}/start`(실시 기록을 만들고 MAINT 구간을 엶), POST `/api/maint/pm-records/{id}/end`(MAINT 구간을 닫고 결과를 적음) (2026-10-27 코드 기준) | `{pm_record_id}`. 소모품 차감은 확정(POST `/api/maint/pm-records/{id}/confirm`)에서 한다 | SCR-23, FR-MNT-04-05~07·10 |

- **선조치 기록 규칙** (2026-10-24, 근거 `화면시안/재기획/사후작업기록_페이지구성_초안.md`): 선조치 기록도 간이 작업기록(`SIMPLE`)이라 새 문서 종류가 없다. 기록 없는 정지 = 5분 이상, 겹치는 작업기록서·간이 작업기록·예방 정비 실시 기록 없음, DOWN이거나 IDLE인데 사유가 비었거나 F 그룹 (SETUP·MAINT·BLOCKED 뺌). 기록을 저장만 해도, 사유를 O·P 그룹으로 넣어도 목록에서 빠진다.
- **시각 표시** (FR-MNT-05-25): 간이 작업기록·작업기록서 조회(API-MNT-09, 간이도 같은 `work_record` 번호)는 알람 시각(있으면)·작업 시작·끝·작성 시각(수정 이력 v0)을 함께 준다. "늦게 씀" 같은 꼬리표·판정 칸은 없다. 기한·별도 보고서·긴급 작업지시서 API도 없다 (FR-MNT-05-27).
- 선조치 기록·사진 칸은 논리 ERD `work_record`(`after_the_fact`, `state_log_id`, `urgent_reason_code`, `urgent_reason_text`, `loto_skip_reason`)와 새 표 `work_record_photo`(`record_no`, `photo_seq`, `file_ref`, `uploaded_by`, `uploaded_at`) 이름 그대로.

### 2.6 보고서·문서 (PRD-02·04, AST-03)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-RPT-01 | GET `/api/reports/shift/{shift_id}` | 교대 보고서 | 조회 전 | — | 생산(총 목표·실적·불량·가동률), 로트, 필수 정지, 병목, 정비, 특이 사항, 인계 사항, 상태, `current_version`(공통 규칙의 `version`) | SCR-15, FR-PRD-02-01~12 |
| API-RPT-02 | PATCH `/api/reports/shift/{shift_id}` | 저장 | 그 교대 S | `version`, 고친 칸 | `{version_no}`(새 버전 번호) | FR-PRD-02-10 |
| API-RPT-03 | POST `.../shift/{shift_id}/confirm` | 확정 | 그 교대 S | `version` | 확정·잠김 | FR-PRD-02-11 |
| API-RPT-04 | POST `.../shift/{shift_id}/revise` | 확정 후 수정 | 그 교대 S | `reason`, 고친 칸 | `{version_no}`, 수정 알림 | FR-AST-03-06·07 |
| API-RPT-05 | GET·PATCH `/api/reports/daily/{date}` · `/confirm` · `/revise` | 일일 보고서 | 조회 S·M·G / 확정 G | `version`. 저장은 `issues_summary`·`memo`만 고칠 수 있음. 확정은 선택 `memo`(관리자 메모, 2000자). `/revise`(확정 후 수정, 관리자)는 `reason` 필수 | 하루 생산(목표 180·실적·부족), 손실, 알람, 정비, 로트, 재고, 오늘의 문제 | SCR-16, FR-PRD-04-01~10 |
| API-DOC-01 | GET `/api/documents` | 문서함 | 전 (역할분) | 종류, 상태, 내 할 일 | 문서 목록 | SCR-18, FR-MNT-05-11·12 |
| API-DOC-02 | GET `/api/documents/{type}/{id}/revisions` | 수정 이력 | 전 (OPR은 **자기가 고친 버전만** — 목록은 거르고, 남의 버전을 번호로 열면 403 `NOT_OWN_REVISION`) | — | 버전 목록(바뀐 칸 수 `changed_fields`, 사유), 버전 1건 보기(GET `/api/documents/revisions/{id}`)에 바뀐 칸 전/후 `changes` | SCR-17, FR-AST-03-01~09 |

### 2.7 로트·품질 (PRD-05, QLT-01)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-LOT-01 | GET `/api/lots` · `/{lot_no}/trace` | 로트 목록 · 추적 | 전 | 작업지시, 상태 | 원자재 → 공정 실적 → 검사 → 출하, 의심 로트 제안 | SCR-19, FR-PRD-05-01~05·09~11 |
| API-LOT-02 | POST `/api/lots/{lot_no}/hold` · `/release` | 보류 · 해제 | S·G | 보류: `reason`, 선택 `trigger_type`·`next_lots`(1~2)·`alarm_event_id`·`tool_id` / 해제: `pass_qty` | 로트 상태 | SCR-19, FR-PRD-05-06·07 |
| API-LOT-03 | POST `/api/lots/{lot_no}/scrap` · `/scrap/approve` | 폐기 제안 · 승인 | 제안 S / 승인 G | 제안: `qty`(폐기 수량. 사유 칸은 코드에 없음) / 승인: 본문 없음 | 로트 상태 | FR-PRD-05-08 |
| API-QLT-01 | GET `/api/inspection/results` | 검사 기록 | 전 | 로트 | 측정값, 입력 방식(`CMM_AUTO`·`TABLET`·`MANUAL`), 부품 온도, 확인 상태 | SCR-20, FR-QLT-01-01~07 |
| API-QLT-02 | POST `/api/inspection/results` | 게이지·외관 결과 / 수동 입력 ("수동" 표시) | O(측정 담당)·S | `lot_no`, `part_seq`, `item_seq`, `insp_kind`(FIRST·SAMPLE·ENHANCED), 결과(`judgement` PASS·FAIL 또는 `measured_value`, 둘 다 없으면 `VALIDATION`), 선택 `inspector_id` | 기록 | SCR-20, FR-QLT-01-01·19 |
| API-QLT-03 | POST `/api/inspection/results/{id}/select` | 재측정 값 고르기 · 반장 확인 | S | 경로의 `result_id`, 본문 `use_for_judgement`(기본 true) | `check_status: CHECKED`(반장 확인) | FR-QLT-01-20~22 |
| API-QLT-04 | GET `/api/inspection/cmm-imports` | 결과 파일 기록·오류 목록 | 전 | 상태 | 파일 이름, 받은 시각, 상태, 오류 | SCR-20, FR-QLT-01-14~18 |
| API-QLT-05 | GET `/api/quality/summary` | 불량 집계·관리도·Cpk | 전 | 기간 | 불량 코드별 수, 관리도, Cpk (50개 미만이면 "계산 중") | SCR-20, FR-QLT-01-08~13 |

- 측정 결과 파일 읽기(공유 폴더 감시 → `cmm_import`)는 **서버 안쪽 일**이라 API가 아니다. 서버의 감시 작업(`workers/cmm_watcher.py`)이 받는 폴더(`inbox`)를 2초마다 보고, 읽은 파일은 `processed`로, 양식 오류 파일은 `error`로 옮긴다 (2026-10-27 코드 기준, 폴더 위치는 환경 설정 `CMM_*_DIR`). 결과가 정한 시간(10분) 안에 안 오면 알림.

### 2.8 재고·출하·공구 (INV-01, ML-01)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-INV-01 | GET `/api/inventory` | 재고 13품목 | 전 | — | 재고, 안전 재고, 관리 역할, 부족 여부, 완제품·보류 수량 | SCR-21, FR-INV-01-01~03·09·11 |
| API-INV-02 | POST `/api/inventory/txns` | 입고 · 실사 조정 | 그 품목 관리 역할 (소모품 M / 공구·원자재·완제품 S) | `item_no`, `kind`(RECEIPT·ADJUST), `qty`, `reason`(실사 조정은 필수), 선택 `fg_lot_no` | `{txn_id, item_no, kind}`. 맡은 품목이 아니면 `FORBIDDEN`(`reason: NOT_ITEM_OWNER`) | FR-INV-01-04·08·13 |
| API-INV-03 | POST `/api/raw-lots/{id}/inspect` | 원자재 입고 검사 (성적서 대조) | S | 결과 | 사용 가능 / 입고 보류 | FR-INV-01-04 |
| API-INV-04 | GET·POST `/api/shipments` · PATCH `/{id}` | 출하 조회 · 등록 · 확정 후 수정 | 조회 전 / 등록 S | 등록: 출하처, `due_date`(필수), 로트·수량 (합격 로트만, 먼저 합격한 로트부터 제안), 선택 `memo`·`confirm`·`fifo_skip_reason` / 조회: `status`·`limit`·`lines` / 수정(PATCH, SUP만): `changes`(실제로는 `memo`만)·`version`, 확정 뒤엔 `reason` 필수(`REASON_REQUIRED`) | 등록 `{shipment_no, status}` (확정 때 로트가 합격·해제 상태가 아니면 `INVALID_STATE`), 수정 `{version_no}` | SCR-21, FR-INV-01-12 |
| API-INV-05 | PATCH `/api/inventory/items/{id}/safety-stock` | 안전 재고 설정 | G | `safety_stock`(0 이상) | 완제품은 `INVALID_STATE` | SCR-25, FR-INV-01-06 |
| API-TOOL-01 | GET `/api/tools` | 공구 수명 | 전 | 설비 | 사용률·단위·한도·남은 수명(남은 부품 수) | SCR-22, FR-ML-01-01~05·08 |
| API-TOOL-02 | POST `/api/tools/{id}/change` | 공구 교체 기록 → 사용량 0, 재고 사용 | O·M | `reason`(LIFE_90·ALARM_362·ALARM_174·BROKEN·OTHER), 선택 `alarm_event_id` | 교체 기록. 시뮬레이터가 연결돼 있으면 시뮬레이터가 교체를 기록하고 `{tool_change_id: null, via: "simulator"}` | SCR-22, FR-ML-01-06, FR-INV-01-05 |

### 2.9 설정·시연 (MGR, 시연 모드)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-SET-01 | GET·PATCH `/api/settings/notification-rules` | 알림 기준값·재발 확인 기간 | G | `rule_code`, `is_enabled`, `condition_text` (기준 숫자 바꾸기는 [선택 필요]) | GET 규칙 목록 / PATCH `{ok: true}` | SCR-25, FR-AST-02-16 |
| API-SET-02 | GET·PATCH `/api/settings/targets` | 교대 목표(90)·하루 목표(180) | G | `shift_target_qty`·`daily_target_qty` (둘 다 없으면 `VALIDATION` `NO_CHANGE`; 아직 시작하지 않은 교대·근무일만 바뀜) | `{shifts_changed, days_changed}` | SCR-25 |
| API-SET-03 | GET·PATCH `/api/settings/users` | 사용자·역할 — **2026-10-23부터 화면은 쓰지 않음** (설정 사용자 탭을 SCR-27로 옮김 → API-USR-01·03이 대신. 번호와 코드는 남아 있고 PATCH는 API-USR-05와 같은 함수를 부름) | G | 값 | — | SCR-25, NFR-SEC-04 |
| API-SIM-01 | POST `/api/sim/inject` | **사건 버튼** — 누른 때(시연 시계 지금) 사건 시작 (S1·S3·S4·S6·S7, S2·S5는 과거 기록이라 버튼 없음. S7은 알람 없는 25분 정지 — 선조치 기록 시연) | 시연 모드 + 시연 조작 허용 목록(`MOM_SIM_CONTROL_USERS`). 시뮬레이터 없이 시연 모드가 꺼져 있으면 MGR만 | `scenario_code` (시각은 보내지 않음) | 사건 ID(실행 중에만 쓰는 번호, DB 엔터티 아님 — 알람에는 `scenario_code`로 남음), 대상 설비, 시작 시각. 대상 설비가 가공 중(RUN)이 아니거나 진행 중인 사건이 있으면 `INVALID_STATE` (같은 사건 반복은 앞 사건이 끝난 뒤 가능) | NFR-DATA-10, 설계서 7장 |
| API-SIM-02 | GET·POST `/api/sim/clock` | 시연 시계: 조회 / 배속(180·60·10·1배)·일시정지·다시 시작·넘기기 (지금 → 18:00. 넘기는 동안 남은 주간 교대를 만든다. 다음 날 07:00으로 넘기기는 없음, 2026-10-13) | 시연 모드 + 시연 조작 허용 목록. POST는 시연 모드가 꺼졌거나 시각을 지정하면 MGR만 | POST: `speed`, `paused`, `skip`(TODAY_DAY_END·TODAY_NIGHT_START), `sim_at`, `mode`. 지난 시각이면 `PAST_*`, 교대가 없으면 `NO_SHIFT_*`로 거절 | 지금 시연 시각, 배속, 일시정지 여부, 진행 중 사건, 버튼별 누를 수 있는지(잠긴 이유) | NFR-DATA-10, 기획서 15장 |
| API-SIM-03 | POST `/api/sim/reset` | 시연 데이터 처음으로 — 시연 시작 시각(영상용 10/24 09:00, 최종용은 시각 그대로 사람 조작만 지움 — 발표자 키 필요)으로 되돌림 | 시연 모드 + 시연 조작 허용 목록, 발표자 키(헤더 `X-Presenter-Key`). 시연 모드가 꺼지면 MGR도 403 | — | 시연 시각 09:00 | NFR-DATA-10, 테스트계획서 6장 |

- 사건 알람(S1·S3·S4)이 뜨면 시뮬레이터가 **스스로 배속 ×10으로 감속**하고 `sim_clock` 사건을 보낸다 (3장). 다시 올리는 것은 발표자(API-SIM-02).
- 사건 버튼과 시계 조작판은 시연 모드에서만 화면 안에 작게 보인다 (UI설계서 2.1 [14]·9.6).
- **API-SIM-01 딸림 — 알림 미리보기 [상황 일으키기]** (2026-10-21 [제안], API 수 그대로): POST `/api/sim/fire` `{kind}` — `warn` 주의 알람 아무거나 · `stop` 정지 알람 아무거나 · `air` 120 공기압 · `maint` 정지 알람 3분 뒤 보전 담당 수리 정비(MAINT 20~40분, 사유는 그 고장). 시연 시계 지금 분에 진짜 알람으로 나서 팝업·3D·이브·알림 목록이 실제와 같이 반응한다. 이미 고장 난 설비는 피한다. 돌려받는 값: `alarm_code`·`name_ko`·`equipment_id`·`at`. 멈춤·휴무면 `INVALID_STATE`. 화면 담당 확인용 (위 바 [알림 미리보기])
- **생성기와 잇는 방법** (2026-10-14 [제안], 서버 연결 방식은 [선택 필요: 기술 회의]): 실시간 모드는 생성기 `데이터생성기/gen/realtime.py`의 `Realtime` 객체다. 서버가 이 객체를 만들고 실제 시간마다 `tick(초)`를 부르면 그동안 생긴 사건 목록이 돌아온다.

| API | 생성기 함수 | 비고 |
|---|---|---|
| API-SIM-01 사건 버튼 | `inject("S1"·"S3"·"S4"·"S6"·"S7")` | 누를 수 없으면 이유("대상 설비 가공 중 아님" / "진행 중 사건 있음")와 함께 거절 → `INVALID_STATE`. 버튼별 상태는 `button_state()` |
| API-SIM-02 시계 | `clock()`, `set_speed()`, `pause()`, `resume()`, `skip()` | 사건 알람이 뜨면 생성기가 스스로 ×10 |
| API-SIM-03 처음으로 | `reset()` | 시연 시작 시각, 약 1초 |
| API-LOT-02 로트 보류 | `hold_lot(로트, 반장)` | 그 로트부터 전수 검사 (OP-50 느려짐). S1 의심 로트는 `suspect_lot()` |
| 보류 해제 (로트 판정 뒤) | `release_lot(로트, 반장, 관리자)` | 폐기가 있으면 관리자 승인을 같이 남김 |
| API-TOOL-02 공구 교체 | `record_tool_change(공구, 작업자)` | 사용량 0, SETUP 3~8분 |
| API-MNT-11 작업기록서 확정 | `confirm_work_record(설비)` | S1 고장 설비 복귀 (그 전까지 DOWN) |

| 생성기 사건 (`tick()`) | 3장 실시간 사건 | 내용 |
|---|---|---|
| `state_changed`, `wip_changed`, `bottleneck_changed`, `alarm`, `sim_clock` | 같은 이름 | `alarm`에 `scenario_code` (사건 버튼이면) |
| `event_started` / `event_ended` | `sim_clock` (진행 중 사건·버튼 잠금) | 사건 버튼 시작·끝 |
| `tool_life` | 알림 재료 (공구 사용률 90%, DOC-07 §9) | 서버가 교체 알림을 만듦 |
| `cmm_file` | 측정 결과 파일 도착 | 결과 파일은 `데이터생성기/out_realtime/cmm_drop/`에 실제로 떨어짐 (CMM 조사 5.2 양식, 부품 1개 = 파일 1개). 서버의 결과 파일 읽기(FR-QLT-01-14)를 이 폴더로 시험 |
| `part_count`, `sensor`, `shift_end` | 3D 실적·센서 값·교대 끝 | 교대 끝에 서버가 교대 보고서 AI비서 초안을 만듦 |

  멈춘 때까지의 기록은 `export()`로 `out_realtime/` CSV가 된다 (번호는 과거 기록 다음부터, 논리 ERD 11.1).


### 2.10 직원 관리 (USR-01, API-USR-01~05는 MGR만, 2026-10-23 · 04~06은 2026-10-25)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| API-USR-01 | GET `/api/staff` | 직원 명단 + 배치표 (결론 띠는 응답에 별도 칸이 없음) | G | `period` (`today`·`7d`·`30d`·`all`(기록 전체, 2026-10-25) — 옛 값 `sep`도 받음, 처음 `7d`), `include_inactive`(사용 중지 직원도 맨 뒤에, 배치표에는 안 넣음) | 사람마다 `user_id`, `user_name`, `role_code`, `home_shift_type`, `home_process_code`·`home_process_code_2`, `is_active`, `on_shift`(지금 근무), `kpis`(역할별 대표 숫자). 응답 최상위: `period`, `from`·`to`, `shift`(지금 교대), `users`, `board`(배치표: 공정·보전·반장 × 주간·야간 → 사람 목록), `empty`(담당 0명 칸 목록). 역할·교대 거름 쿼리는 없음 | SCR-27, FR-USR-01-01~03·09·12 |
| API-USR-02 | GET `/api/staff/{user_id}/activity` | 직원 상세: 숫자 4칸 + 최근 업무 | G | `period`, `page`·`size` | `kpis`(역할별 4개, 합계만), `items`(시각, 한 일 종류, 대상 번호, 열 화면·키) — 기존 표의 `~_by` 칸을 모은 것, 채팅 기록 없음 | SCR-27, FR-USR-01-07·08·10·11 |
| API-USR-03 | PATCH `/api/staff/assignments` | 배치 바꾸기 (한 번에 여러 사람) | G | `changes`: 사람마다 `user_id`, 바꿀 `home_shift_type`·`home_process_code`·`home_process_code_2`(또는 `procs`) / `reason`은 맨 바깥에 하나(선택). 같은 직원이 두 번 있거나 목록이 비면 `VALIDATION` `CHANGES` | `changed`(사람마다 `user_id`, 수정 이력 `revision_id`(`APP_USER`), `version_no`), `users`, `board`, `empty`(담당 0명 칸) | SCR-27, FR-USR-01-04~06 |

- **API-USR-03 규칙:** 같은 역할만 그 줄에 넣을 수 있고(공정 = OPR, 보전 = MNT, 반장 = SUP), 담당 공정은 최대 2개 — 어기면 `VALIDATION`. 역할(`role_code`)·`is_active`는 이 API로 바꾸지 않고 API-USR-05로 바꾼다 (FR-USR-01-14). 한 사람이라도 틀리면 아무것도 바꾸지 않는다. 저장하면 바로 적용되고, 사람마다 `document_revision`(문서 종류 `APP_USER`, 문서 키 = `user_id`) + 바뀐 칸 전·후를 남겨 **API-DOC-02 수정 이력**으로 보인다.
| API-USR-04 | POST `/api/staff` | 직원 추가 (2026-10-25) | G | `user_id`(비우면 `U` + 다음 번호), `user_name`, `role_code`, `home_shift_type`, `home_process_code`·`home_process_code_2`(또는 `procs`), `password`, `reason`(선택) | 만든 직원(비밀번호·해시 없음), `revision_id`, `version_no`. 수정 이력 v0 "직원 추가" | SCR-27, FR-USR-01-13·15 |
| API-USR-05 | PATCH `/api/staff/{user_id}` | 직원 정보 고치기: 이름·역할·사용 중지/다시 사용·비밀번호 다시 정하기 (2026-10-25) | G | 바꿀 칸만: `user_name`, `role_code`, `is_active`, `password`, (역할을 바꾸며 같이 정할 때) `home_shift_type`·`procs`, `reason`(선택) | 바뀐 직원(비밀번호 없음), `revision_id`, `version_no`. 비밀번호는 이력에 "비밀번호 바꿈"만 | SCR-27, FR-USR-01-14·15 |
| API-USR-06 | GET `/api/users` | 직원 이름·역할·배치 목록 (2026-10-25) — **로그인한 누구나**. 화면이 이름 표시·담당 공정 알림·바꾼 배치를 바로 적용(FR-USR-01-06)하는 데 쓴다 | 로그인 | — | `users`: `user_id`, `user_name`, `role_code`, `home_shift_type`, `home_process_code`·`home_process_code_2`, `is_active` (사용 중지 직원도 — 지난 기록의 이름). 숫자·업무 기록·로그인 시각 없음 | SCR-27, SCR-03, FR-USR-01-06 |

- **API-USR-04·05 규칙 (2026-10-25):** 아이디는 `^[A-Za-z0-9_]{2,20}$`, 이미 있으면 `INVALID_STATE`(409, `reason: DUPLICATE`). 이름 1~40자. 두 번째 담당 공정은 작업자만. 지금 로그인한 관리자는 자기 자신을 사용 중지하거나 관리자가 아닌 역할로 바꿀 수 없고(`SELF`), 사용 중인 관리자가 0명이 되는 변경은 거절(`LAST_MGR`). 비밀번호는 최소 8자 [가상, 서버 설정] — 서버가 해시로만 저장하고 응답·이력·로그에 값이 없다. 지우기 API는 없다(사용 중지만). 규칙 위반은 모두 `VALIDATION`(422) + `detail.reason`(`PROCESS_ROLE`·`PROCESS`·`SHIFT`·`NAME`·`ROLE`·`USER_ID`·`PASSWORD`·`INACTIVE`·`NO_CHANGE`). 사용 중지·역할 변경은 이미 받은 토큰에도 60초 안에 적용된다(3D 라인 뷰 포함).
- MGR이 아니면 API-USR-01~05는 `FORBIDDEN` (NFR-SEC-04·05, 권한 대상 `STAFF`). API-USR-06만 로그인한 누구나.

### 2.11 코드와 명세서 대조 (2026-10-27, 백엔드 `backend/app/routers/` 기준)

백엔드 라우트 168개를 이 명세서의 API ID 표와 경로·메서드로 하나씩 맞춰 보았다. **83개는 명세서와 같고**, 나머지는 아래 두 가지다. 새 ID를 붙일지는 팀이 정한다 [제안].

일치한 83개는 요청·응답 칸과 권한도 코드와 맞춰 2장 표를 고쳤다 (같은 날). 명세서가 코드보다 앞선 부분(백엔드가 아직 안 만든 것)은 표를 고치지 않고 **[백엔드 미구현]**으로 표시했다: API-MNT-10 선조치 권한(O), API-MNT-12 선조치 칸, API-LINE-07 기록 칸, 3장 `sim_clock` 사건. 정리한 것(2026-10-27 최종 구현 기준): API-LOT-03 폐기 제안은 `qty`만 받는다(사유 칸 없음, 요구사항 FR-PRD-05-08도 사유를 요구하지 않음). API-LINE-06 센서 간격은 5초가 맞다(생성기 `SEC5`, 코드 주석 "1초"는 옛 설명).

**가. 명세서에만 있고 백엔드에 없는 것 — 4개 ID (7개 경로)**

| API ID | 경로 | 상태 |
|---|---|---|
| API-MNT-13 | GET `/api/maint/unrecorded-stops` | 백엔드 없음 (선조치 기록, 2026-10-24 추가분). 화면은 자체 기록으로 보여 줌 |
| API-MNT-14 | POST `/api/maint/quick-records/after-the-fact` | 백엔드 없음 |
| API-MNT-15 | GET·POST `/api/maint/work-records/{id}/photos`, GET·DELETE `…/photos/{photo_seq}` | 백엔드 없음 (사진 올리기·빼기) |
| API-MNT-16 | POST `/api/maint/quick-records/{id}/check` | 백엔드 없음. 정식 작업기록서용 `POST /api/maint/work-records/{id}/check`만 있다 |

**나. 백엔드에만 있고 명세서 ID가 없는 것 — 85개 경로.** 화면이 한 번에 읽는 묶음 조회, 시뮬레이터가 보내는 입구(`/api/ingest/*`, 서비스 키), 비서 도구, QR, 알림 1건 조회 같은 것들이다. 사람이 쓰는 입구의 권한은 `backend/docs/06_역할별_권한.md`를 따른다.

**알람** (2개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/alarms` | 기간 안 알람 목록 |
| GET `/api/alarms/{alarm_event_id}` | 알람 1건 + 코드집 내용 |

**AI 비서** (9개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/assistant/chat/{chat_id}` | 채팅 기록 1건 |
| GET `/api/assistant/docs` | 사내 문서 조각 전체 |
| POST `/api/assistant/drafts/work-order` | 작업지시서 AI비서 초안 |
| POST `/api/assistant/drafts/work-record` | 정식 작업기록서 AI비서 초안 |
| PUT `/api/assistant/notifications/{notification_id}/message` | 알림 문장을 비서 문장으로 바꾸기 |
| GET `/api/assistant/tools` | 이 사용자가 쓸 수 있는 도구의 JSON Schema |
| POST `/api/assistant/tools/{name}` | 조회 도구 실행 |
| POST `/api/assistant/transcribe` | 채팅 음성 입력 |
| GET `/api/assistant/voice` | 채팅 마이크 버튼을 보일지 |

**알림·브리핑** (3개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/assistant/briefing/checks` | 브리핑 "먼저 챙길 일"에서 본인이 체크한 항목 |
| POST `/api/assistant/briefing/checks` | 체크하기·풀기 |
| GET `/api/notifications/{notification_id}` | 알림 1건 |

**보고서·문서** (7개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/documents/revisions` | 최근 문서 버전 |
| GET `/api/documents/revisions/{revision_id}` | 버전 1개 + 바뀐 칸 |
| GET `/api/internal-docs` | 사내 문서 목록 |
| GET `/api/internal-docs/{doc_no}` | 사내 문서 1건 |
| GET `/api/reports/daily` | 일일 보고서 목록 |
| POST `/api/reports/daily/{work_date}/revise` | 일일 보고서 확정 후 수정 |
| GET `/api/reports/shift` | 교대 보고서 목록 |

**시뮬레이터 → 플랫폼 (서비스 키)** (14개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| POST `/api/ingest/alarms` | 알람 1건 → 기록 + 등급별 알림 + 반복 알람 판정 |
| POST `/api/ingest/alarms/{alarm_event_id}/clear` | 알람 해제 시각 |
| POST `/api/ingest/bottleneck` | 병목 공정 바뀜 |
| POST `/api/ingest/clock` | 시연 시계를 시뮬레이터 시계에 맞춘다 |
| POST `/api/ingest/cmm` | CMM 결과 파일 내용 |
| POST `/api/ingest/lots` | 로트 투입 |
| POST `/api/ingest/lots/{lot_no}/arrived` | 로트가 OP-50에 도착 → 검사 대기 |
| POST `/api/ingest/orders` | 작업지시 만들기 → PO-YYMM-NNN |
| POST `/api/ingest/production` | 공정 실적 더하기 |
| POST `/api/ingest/reset` | 시연 데이터 처음으로 |
| POST `/api/ingest/sensors` | 센서 값 여러 개 |
| POST `/api/ingest/state` | 설비 상태 바뀜 → 구간 닫고 열기 |
| POST `/api/ingest/sync` | 시뮬레이터 10/1 기록을 표째로 DB에 맞춘다 |
| POST `/api/ingest/wip` | 재공 수량 |

**재고·출하·공구** (10개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/inventory/screen` | 재고 화면 한 번에 |
| GET `/api/inventory/{item_no}/txns` | 품목 1개의 거래 내역 |
| POST `/api/raw-lots` | 원자재 입고 → 원자재 로트 + 입고 거래 |
| GET `/api/shipments/candidates` | 출하할 수 있는 로트 |
| GET `/api/shipments/{shipment_no}` | 출하 1건 + 줄 |
| POST `/api/shipments/{shipment_no}/confirm` | 출하 확정 |
| DELETE `/api/shipments/{shipment_no}/lines/{lot_no}` | 출하 줄 빼기 |
| PUT `/api/shipments/{shipment_no}/lines/{lot_no}` | 출하 줄 넣기·수량 바꾸기 |
| GET `/api/tools/changes` | 공구 교체 내역 전체 |
| GET `/api/tools/{tool_id}/changes` | 공구 교체 내역 |

**QR** (5개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| POST `/api/qr/inventory` | 품목 QR로 입고·실사 |
| GET `/api/qr/label/{kind}/{no}` | 라벨에 넣을 QR 내용과 사람이 읽을 줄 |
| POST `/api/qr/scan` | QR 조회 |
| GET `/api/qr/scans` | 찍은 기록 |
| POST `/api/shipments/{shipment_no}/qr-check` | 출하 전 확인 |

**정비** (12개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/maint/history` | 정비 과거 기록 한 번에 |
| GET `/api/maint/pm-records/{pm_record_id}` | 예방 정비 실시 기록 1건 |
| PATCH `/api/maint/pm-records/{pm_record_id}` | 예방 정비 기록 고치기 = 새 버전 |
| POST `/api/maint/pm-records/{pm_record_id}/confirm` | 예방 정비 기록 확정 → 소모품 재고 차감·기한 알림 자동 처리 |
| POST `/api/maint/pm-records/{pm_record_id}/end` | [정비 끝 · 실시 기록] |
| POST `/api/maint/pm-tasks/{pm_task_id}/start` | [정비 시작] |
| POST `/api/maint/work-orders` | 보전 담당자가 직접 만들기 → 수정 중 |
| GET `/api/maint/work-records` | 작업기록 목록 |
| POST `/api/maint/work-records` | 정식 작업기록서 만들기 |
| POST `/api/maint/work-records/{record_no}/check` | 반장 확인 표시 |
| POST `/api/maint/work-records/{record_no}/checks/{check_seq}` | 체크 1칸 |
| PUT `/api/maint/work-records/{record_no}/parts` | 쓴 부품 1줄 |

**기준·설정·시연** (9개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/admin/retention` | 보관 기간이 지난 행 수 |
| POST `/api/assist/{kind}` | 화면이 기본 문장을 보여 주면서 비서가 다듬어 둔 문장이 있는지 묻는다 |
| GET `/api/codes` | 코드 한국어 이름 |
| GET `/api/dataset` | 가상 데이터 정보 |
| POST `/api/sim/fire` | 알림 미리보기 [상황 일으키기] |
| POST `/api/sim/pm-end` | [정비 끝] |
| POST `/api/sim/pm-start` | [정비 시작] |
| POST `/api/sim/snapshot` | 시연 기준점 만들기 |
| POST `/api/sim/work-record-confirmed` | 작업기록서 확정 뒤 고장 설비 복귀 |

**생산·로트** (7개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| GET `/api/holds` | 보류 목록 |
| POST `/api/holds/{hold_id}/resume-normal` | 강화 → 보통 검사 복귀 |
| GET `/api/kpi/stops` | 정지 사유 순위 |
| GET `/api/lots/screen` | 로트 화면 한 번에 |
| GET `/api/lots/suspects` | 의심 로트 제안 목록 |
| GET `/api/lots/{lot_no}` | 로트 1개 |
| POST `/api/lots/{lot_no}/judge` | 로트 판정 다시 돌리기 |

**품질** (7개)

| 메서드 · 경로 | 하는 일 |
|---|---|
| POST `/api/inspection/cmm-imports` | 결과 파일 직접 올리기 |
| GET `/api/inspection/instructions` | 열린 측정 지시 |
| POST `/api/inspection/instructions` | 측정 지시 |
| POST `/api/inspection/instructions/{instruction_id}/start` | 측정 시작 |
| GET `/api/quality/cpk` | Cpk 항목 하나 |
| GET `/api/quality/defects` | 불량 코드별 수량 |
| POST `/api/quality/items/{product_code}/{item_seq}/resume-sampling` | 전수 측정 → 보통 |

---

## 3. 실시간 사건 (API-STR-01)

전송 방식은 **SSE** (`GET /api/stream/events?token=…`, 15초마다 연결 유지 신호, 2026-10-27 코드 기준). 사건에는 무엇이 바뀌었는지만 있고 내용은 없다 — 화면이 권한 있는 API로 다시 읽는다. 알림·긴급 팝업은 받은 사람에게만 가고, 문서 사건은 볼 수 있는 역할에게만 간다. 반영 주기는 NFR-PERF-02 [선택 필요].

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
| `sim_clock` **[백엔드 미구현]** | (시연 모드) 배속·일시정지·넘기기·되돌리기·자동 감속, 사건 시작·끝 — 서버가 이 사건을 보내지 않는다 (사건은 `state_changed`·`wip_changed`·`bottleneck_changed`·`alarm`·`urgent_popup`·`notification`·`kpi_updated`·`document_changed`·`connection` 9개). 시계는 GET `/api/sim/clock`으로 읽는다 | 시연 시각, 배속, 일시정지 여부, 진행 중 사건, 버튼 잠금 상태 | 상단 바 시각, 시연 조작판 |

---

## 4. 서버가 스스로 하는 일 (API 아님)

| 일 | 언제 | 근거 |
|---|---|---|
| 교대 보고서 AI비서 초안 만들기 + 그 교대 SUP에게 확정 요청 알림 | 교대 끝 18:00·06:00 | FR-PRD-02-01, FR-AST-02-17 |
| 일일 보고서 AI비서 초안 만들기 + MGR에게 일일 보고서 확정 요청 알림 (`DAILY_REPORT_PENDING`, 말풍선) | 그 생산일 야간 교대 보고서가 확정될 때(API-RPT-03 성공, 06:00~07:00). 07:00까지 확정이 없으면 07:00 (미확정 교대 칸은 잠정) | FR-PRD-04-01·09 |
| 작업지시서 AI비서 초안 + 그 설비 MNT에게 작업지시서 초안 검토 알림 (`WO_DRAFT_READY`, 말풍선) | OP-30 정지 등급 알람·반복 알람 2단계 | FR-MNT-03-01 |
| 알림 규칙 판단, 보고 순위 매기기 | 기록이 생길 때마다 | FR-AST-02-01~19, FR-AST-COM-21 |
| 기록 없는 정지 찾기 + 그 설비 담당 O·M·그 교대 S에게 알림 (`UNRECORDED_STOP`, ⓘ 참고 → 교대 끝 1시간 전까지 남으면 ▲ 주의) / 선조치 기록 확정 때 반장에게 확인 요청 알림 (`AFTER_RECORD_CHECK_WAIT`, ⓘ 참고) (2026-10-24) | 정지 구간이 끝날 때 · 선조치 기록 확정 때 | FR-AST-02-20·21, FR-MNT-05-23 |
| 지표·손실·이월 계산 | 기록이 생길 때·교대 시작 | DOC-07 6~8장, R-88 |
| 측정 결과 파일 읽기 · 측정 지시 파일 넘기기 | 파일이 생길 때 · 측정 시작 때 | FR-QLT-01-14·15 |
| 보관 기간이 지난 데이터 처리 | 지금은 지난 행 수만 센다 (`GET /api/admin/retention`, 지우지 않음). 실제 삭제·집계 주기는 [선택 필요: 기술 회의] | NFR-DATA-13 |
| (시연 모드) 화면 조작을 시뮬레이터에 넘기기: 로트 보류(API-LOT-02) → 그 로트부터 전수 검사, 공구 교체(API-TOOL-02) → 그 공구 사용량 0, 작업기록서 확정(API-MNT-11) → 고장 설비 복귀 | 그 API가 성공할 때 | NFR-DATA-10, 설계서 4장 |
| (시연 모드) 시뮬레이터 시계 따르기: 24시간 미처리·목표 예측·교대 끝 초안 등 시각 계산 | 늘 | NFR-DATA-10 |

---

## 5. 기능 ↔ API 대응

| 기능 | API | 기능 | API |
|---|---|---|---|
| PRD-01 3D 라인 뷰 | API-LINE-01~04·07·08, API-STR-01 | MNT-02 지침카드 | API-MNT-01 |
| PRD-02 교대 보고서 | API-RPT-01~04 | MNT-03 작업지시서 | API-MNT-02~08 |
| PRD-03 작업지시 진행 | API-LINE-05 | MNT-04 예방 정비 | API-PM-01·02 |
| PRD-04 일일 보고서 | API-RPT-05 | MNT-05 작업기록서 (선조치 기록 포함) | API-MNT-09~16 |
| PRD-05 로트 추적 | API-LOT-01~03 | QLT-01 검사 | API-QLT-01~05 |
| PRD-06 다시 보기 | API-LINE-06 | INV-01 재고·출하 | API-INV-01~05 |
| AST-01 브리핑 | API-AST-01 | ML-01 공구 수명 | API-TOOL-01·02 |
| AST-02 알림 | API-NTF-01~04, API-STR-01, API-SET-01 | AST-03 수정 이력 | API-DOC-01·02, API-RPT-04, API-DOCS-02 |
| MNT-01 질문 답변 | API-AST-02, API-DOCS-01 | AST-COM 비서 공통 | API-AST-01·02, API-MNT-01·10 |
| 공통·권한·시연 | API-AUTH-01~04, API-SET-02·03, API-SIM-01~03 | USR-01 직원 관리 | API-USR-01~06 |

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
| v1 수정 | 2026-10-20 | 채팅 마이크 녹음 길이 (`구현_중_수정사항/1020_수정간단내용.md` 67장, API 수 63개 그대로): API-AST-02 딸림 설명의 POST `/api/assistant/transcribe` 상한을 "약 1.5MB·20초"에서 "약 1.5MB, 길이는 서버 설정(기본·최대 60초)"으로. 백엔드는 비서를 최대 45초까지 기다림 |
| v1 수정 | 2026-10-21 | 알림 미리보기 [상황 일으키기] (`구현_중_수정사항/1021_수정간단내용.md` 55장, API 수 그대로): 10장 시연 API 아래에 API-SIM-01 딸림 POST `/api/sim/fire` [제안] |
| v1 수정 | 2026-10-22 | 작업지시서 승인은 반장만 (`구현_중_수정사항/1022_수정간단내용.md` 6장, API 수 63개 그대로): API-MNT-06 역할 S·G → S, 하는 일에서 관리자 대리 승인을 뺌. API-MNT-08 취소 역할 G → 권한 없음 |
| v1 수정 | 2026-10-24 | 교대 시각 변경(주간 09:00~18:00·야간 21:00~06:00)과 프로필 반영: 넘기기 = 지금 → 18:00, 처음으로 = 시연 시작 시각, 교대 끝 초안 18:00·06:00, 일일 보고서 06:00~07:00. 시연 서버 `GET /api/health`에 `profile`(이름·시계 방식·조작·교대·기록 시작·끝·시연 시작 시각) 추가, 최종용은 시계·사건 조작이 403이고 `POST /api/sim/reset`만 헤더 `X-Presenter-Key`로 (API 수 63개 그대로) |
| v1 수정 | 2026-10-23 | 직원 관리 USR-01 (`구현_중_수정사항/1023_수정간단내용.md` 18장, API 63 → **66개**): 2.10 새 절 — API-USR-01 명단·배치표, API-USR-02 직원 상세, API-USR-03 배치 바꾸기(수정 이력 `APP_USER`). API-SET-03은 쓰지 않음 표시(번호 남김). 5장 대응표에 USR-01 |
| v1 수정 | 2026-10-24 | 사후 작업기록 (근거 `화면시안/재기획/사후작업기록_페이지구성_초안.md`, API 66 → **70개**): 2.5에 API-MNT-13 기록 없는 정지 목록, API-MNT-14 사후 기록 만들기(정지 구간 또는 설비·시각), API-MNT-15 작업기록 사진(최대 3장, 외부 LLM에 안 보냄), API-MNT-16 사후 기록 반장 확인(작업기록서를 반장이 확인하는 API가 없어 새로 둠). API-MNT-12에 사후 기록 칸·확정 규칙, API-MNT-10 사후 기록은 O·M, API-LINE-07에 기록 칸. 4장 서버 자동 작업에 알림 `UNRECORDED_STOP`·`AFTER_RECORD_CHECK_WAIT`. 5장 대응표 MNT-05 = API-MNT-09~16 |
| v1 수정 | 2026-10-24 | 선조치 기록 고침 (2026-10-24, 사용자 요청): 이름 '사후 기록' → **선조치 기록**(사후 작업지시서 → 긴급 작업지시서). 한 일 목록을 **작업자 범위**(칩·이물, 절삭유·윤활유, 도어 밖 손상 확인, 공구, 보전 부름, 기타)와 **보전 범위**(볼스크류·가이드, 커플링, 서보 모터·케이블, 서보 앰프, 주축, 축 윤활, 공압·센서, 부품 교체 — DOC-03 점검 순서의 보전 줄 기준 [가상])로 나눔. 보전 범위는 MNT에게만 보이고, 고르면 MNT만 확정. 긴급 작업지시서 자동 생성(OP-30 보전 범위만)은 **보류**. API-MNT-12 확정 조건에 보전 범위 더함. API 수 그대로 (70개) |
| v1 수정 | 2026-10-27 | 코드 기준 최신화 (`구현_중_수정사항/1027_수정간단내용.md` 1장, API-USR-04~06 그대로): **요청·응답 칸·권한 대조로 2장 표 약 45개 행 고침**(AUTH·LINE·NTF·AST·MNT·PM·RPT·DOC·LOT·QLT·INV·TOOL·SET·SIM·USR), **새 2.11절 "코드와 명세서 대조"**(경로·메서드 83개 일치, MNT-13~16은 백엔드 없음, 백엔드에만 있는 85개 표), API-SIM-01 사건 버튼에 S7, API-USR-01 `period=all`, 1장 공통 규칙(REST·FastAPI, JWT Bearer 12시간, 서비스 키)·3장 실시간(SSE `?token=`)·CMM 폴더 감시·보관 기간(지난 행 수만 셈)의 "기술 회의" 표시를 코드 내용으로 채움 |
