# API 명세서

| 항목 | 내용 |
|---|---|
| 문서 버전 | **v1** (2026-10-07, 첫 작성) |
| 근거 | [기획서_최종본.md](기획서_최종본.md) 12.5·13장, [요구사항정의서_최종본.md](요구사항정의서_최종본.md), [UI설계서_최종본.md](UI설계서_최종본.md) 5장, [논리ERD_최종본.md](논리ERD_최종본.md) |
| 함께 보는 문서 | [테스트계획서_v1.md](테스트계획서_v1.md) (API ID를 시험 항목에 씀) |
| 범위 | 화면·서버·비서가 주고받는 **약속**(주소, 보내는 값, 돌려받는 값, 권한, 오류). 서버 안쪽 구현·비서 안쪽(모델·검색 방식)은 다루지 않음 |

표시: **[제안]** 팀 확정 전 / **[선택 필요: 기술 회의]** 기술을 고른 뒤 정함 / **[보류]** 제작 보류 기능

---

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 주소·형식 | `/api/...` 아래, 요청·응답은 JSON [제안]. 실제 방식(REST 등)·서버 프레임워크는 [선택 필요: 기술 회의] |
| 로그인 | `API-AUTH-01`로 로그인 뒤 모든 요청에 로그인 정보를 붙임. 방식(세션·토큰)은 [선택 필요: 기술 회의] (NFR-SEC-07) |
| 권한 | 기획서 13장 권한표 그대로. 화면에서 버튼을 숨겨도 **서버가 다시 확인하고 거부** (NFR-SEC-05). MGR은 모든 조회 가능 |
| 이름 | 응답 칸 이름은 논리 ERD 속성 이름을 그대로 씀 (예: `target_qty`, `carry_over_qty`) |
| 시각 | `2026-10-01T10:20:00+09:00` 모양. 교대는 `shift_id` (예: `2026-10-01-D`) |
| 숫자 | 단위 칸을 함께 (`psi`·`bar` 둘 다). 추정 값은 `is_estimated: true` (FR-AST-COM-19) |
| 가상 표시 | 모든 운영 데이터 응답에 `is_synthetic: true` (NFR-DATA-08) |
| 문서 공통 | 문서 응답에 `status`(AI비서 초안 / 수정 중 / 확정 …), `version`, 칸별 출처(`ai` / `edited_by` / `program`) |
| 고치기 | 문서를 고치는 요청은 `version`을 함께 보냄. 다르면 `CONFLICT_VERSION` (다른 사람이 먼저 고침) |
| 확정 후 수정 | `reason` 필수 → 새 버전 + 수정 알림 (FR-AST-03-06·07) |
| 출처 | 비서·지침카드·초안의 출처는 `{doc_name, doc_no, rev, section}`만. **원문 출처 칸 없음** (D-03) |
| 목록 | 긴 목록은 `page`, `size`로 나눔 [제안] |

**오류 형식:** `{ "code": "...", "message": "쉬운 한국어 문장", "detail": {...} }`

| code | 뜻 | 예 |
|---|---|---|
| `UNAUTHORIZED` | 로그인 안 됨 | 로그인 없이 요청 |
| `FORBIDDEN` | 역할에 권한 없음 | OPR가 교대 보고서 확정 |
| `NOT_FOUND` | 없는 기록 | 없는 로트 번호 |
| `VALIDATION` | 값이 틀림·빠짐 | 확정 후 수정에 사유 없음 |
| `INVALID_STATE` | 지금 상태에서 할 수 없음 | 승인 전 [작업 시작], 담당 없이 승인, 체크 9칸 덜 채우고 확정, 보류 로트 출하 |
| `CONFLICT_VERSION` | 버전 충돌 | 두 사람이 같은 문서를 동시에 고침 |
| `ASSISTANT_UNAVAILABLE` | 비서 응답 없음·형식 틀림 | 로컬 LLM이 멈춤 → 화면은 기본 문구로 (FR-AST-02-14, NFR-AIQ-09) |

---

## 2. API 목록

역할: O = OPR, M = MNT, S = SUP, G = MGR, 전 = 전원. "조회"는 MGR 포함.

### 2.1 로그인·공통

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| AUTH-01 | POST `/api/auth/login` | 로그인 (시연: 가상 사용자 고르기) | 전 | `user_id` (+ 비밀번호 [선택 필요]) | 사용자, 역할, 담당 공정, 첫 화면 | SCR-01, NFR-SEC-01·07, NFR-USE-08 |
| AUTH-02 | POST `/api/auth/logout` | 로그아웃 | 전 | — | — | SCR-01 |
| AUTH-03 | GET `/api/me` | 내 정보·권한 | 전 | — | 역할, 할 수 있는 일 목록 | 2.9, NFR-SEC-02·03 |
| AUTH-04 | POST `/api/demo/role` | 역할 바꿔 보기 (**시연 모드만**) | 전 | `role` | 바뀐 역할, 첫 화면 | NFR-DATA-12 |

### 2.2 3D 라인 뷰·생산 (PRD-01·03·06)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| LINE-01 | GET `/api/line/layout` | 공장·설비 실제 크기 배치 | 전 | — | 공장 크기, 배치 물체, 설비 외형·좌표, 부품 도형 | SCR-04·05·06·26, FR-PRD-01-01·27 |
| LINE-02 | GET `/api/line/twin` | 지금 상태 한 번에 | 전 | `shift_id` | 설비별 상태·지속 시간·현재 로트·현재 알람·이번 교대 실적/목표·정지 시간·손실 합계, 재공 WIP-1~4, 병목(공정·원인·시작) | SCR-04·05·26, FR-PRD-01-03~13·16 |
| LINE-03 | GET `/api/production/target` | 목표 대비 실적·예측 | 전 | `shift_id` | `target_qty`, `carry_over_qty`, 총 목표, 실적, 예측, 부족 수량, 위험 여부, 시간대별 실적(그래프) | SCR-02~05·15·26, FR-PRD-01-15, FR-AST-02-04 |
| LINE-04 | GET `/api/kpi` | 지표 | 전 | 범위(라인/설비), `from`, `to` | OEE, 가동률, 성능, 양품률, MTTR·MTBF(30일), 주의 표시 | SCR-04 [8], SCR-10 [6], SCR-16, FR-PRD-01-20~23 |
| LINE-05 | GET `/api/production/orders` | 작업지시 진행 표 | 전 | `shift_id` | 작업지시별 목표·완료·불량·로트·공정·납기·지연 여부·상태 | SCR-04 [11], FR-PRD-03-01~04 |
| LINE-06 | GET `/api/replay` | 다시 보기 | 전 | `from`, `to` | 시각별 상태·재공·센서(1초/1분)·알람·병목 사건 | SCR-06, FR-PRD-06-01~09 |
| LINE-07 | GET `/api/downtimes` | 정지 구간 목록 + 비서 추천 | 전 | `shift_id`, 설비, 미확정만 | 구간, 길이, 상태, 사유, 추천 사유(AI비서 초안) | SCR-14 **(필요 여부 판단 중)**, FR-PRD-01-18·19 |
| LINE-08 | PATCH `/api/downtimes/{id}` | 정지 사유 입력 / 확정 | 입력 O·M / 확정 S | `reason_code` 또는 `confirm` | 바뀐 구간 | SCR-14, FR-PRD-01-19 |

### 2.3 알림·실시간 (AST-02)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| NTF-01 | GET `/api/notifications` | 알림 목록 | 전 (자기 역할분, MGR 전부) | 처리 상태, 정렬(최근/보고 순위), 중요도, 설비 | 알림 카드(중요도, 보고 순위, ×N 묶음, 폭주 묶음 = 1건, 24시간 넘음, 관련 정보 한 줄, 처리할 사람), 전체 N건·순위별 건수 | SCR-07, FR-AST-02-01~19 |
| NTF-02 | POST `/api/notifications/{id}/read` | 읽음 (처리 아님) | 받는 사람 | — | — | SCR-07 |
| NTF-03 | POST `/api/notifications/{id}/resolve` | 처리 | 처리 칸의 역할만 | 반복 알람은 `action_plan` 필수, 메모 | 처리 시각·사람 | SCR-07, FR-AST-02-13·03 |
| NTF-04 | POST `/api/notifications/{id}/ack` | 긴급 팝업 확인 (소리 끔, 처리 아님) | 받는 O·M | — | — | SCR-08, FR-AST-02-02 |
| STR-01 | GET `/api/stream/events` | **실시간** 서버 → 화면 | 전 | — | 아래 3장 사건 | 전 화면, NFR-PERF-02 |

### 2.4 비서·사내 문서 (AST-01, MNT-01) — 바깥 모양만, 안쪽은 LLM 담당

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| AST-01 | GET `/api/assistant/briefing` | 교대 시작 브리핑 | 전형 S·M·G / 요약형 O | `shift_id`, `view`(full/operator) | 지난 교대 3줄(양품·손실 / 설명 / 나머지, 잠정 여부), 먼저 챙길 일(보고 순위 목록 전부, 전체 N건·순위별), 이번 교대 3줄(총 목표 = 목표 + 이월 / 작업지시 / 예방 정비) | SCR-02·03·26, FR-AST-01-01~07, FR-AST-COM-21 |
| AST-02 | POST `/api/assistant/chat` | 비서에게 질문 | 전 (답은 역할이 볼 수 있는 것만) | `question`, `context`(화면·설비·알람) | `answer`, `sources[]`, `related[]`(기록 번호), `status`(ok / 문서에 없음 / 거부 / 응답 없음) | SCR-10, FR-MNT-01-01~12, FR-AST-COM-01~20 |
| DOCS-01 | GET `/api/internal-docs/{doc_no}/sections/{section}` | 출처 요약 카드·팝업 창 | 전 | `view`(card/full) | 문서 이름·번호·개정·절 제목, 앞 2~3줄 또는 본문 | SCR-24, FR-MNT-01-09 |
| DOCS-02 | POST `/api/internal-docs/{doc_no}/revisions/{rev}/approve` | 사내 문서 개정 승인 | G | — | 새 현행판, 수정 알림 | SCR-24, FR-AST-03-09 |

### 2.5 정비 (MNT-02~05)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| MNT-01 | GET `/api/maint/guide-card/{alarm_event_id}` | 지침카드 | 전 | — | 알람·심각도·누가·연쇄 알람·먼저 할 일·안전 블록(고정 서식)·생산 영향·지난 기록·출처 목록·버튼 | SCR-09, FR-MNT-02-01~14 |
| MNT-02 | GET `/api/maint/work-orders` | 작업지시서 목록 | 전 | 상태, 내 것만 | 목록 | SCR-18 |
| MNT-03 | GET `/api/maint/work-orders/{id}` | 작업지시서 | 전 | — | 계기, 자동 칸, 제목·증상, 작업 순서, 차단 지점, 안전 블록(읽기 전용), 비슷한 과거, 예상 부품, 담당, 상태, 승인 대기 시간, 출처 | SCR-11, FR-MNT-03-01~14 |
| MNT-04 | PATCH `/api/maint/work-orders/{id}` | 내용 수정 | M | `version`, 고친 칸 | 새 버전 | SCR-11 |
| MNT-05 | POST `.../work-orders/{id}/assign` | 담당 지정 | S | `mnt_user_id` | — | FR-MNT-03-14 |
| MNT-06 | POST `.../work-orders/{id}/approve` | 승인 (MGR 대리 승인) | S·G | `version` | 상태 = 승인 (담당 없으면 `INVALID_STATE`) | FR-MNT-03-13·14 |
| MNT-07 | POST `.../work-orders/{id}/start` | 작업 시작 | 담당 M | — | 상태 = 진행 중 (승인 전이면 거부) | FR-MNT-03-02 |
| MNT-08 | POST `.../work-orders/{id}/cancel` | 취소 | G | `reason` | 상태 = 취소 | SCR-11 |
| MNT-09 | GET·PATCH `/api/maint/work-records/{id}` | 작업기록서 조회·수정 | 조회 전 / 수정 M | `version`, 고친 칸, 체크 9칸, 사용 부품 | 칸 전부 | SCR-12, FR-MNT-05-01~08 |
| MNT-10 | POST `.../work-records/{id}/assist` | 메모를 비서로 정리 | M | `memo` | AI비서 초안 칸 | FR-MNT-05-02 |
| MNT-11 | POST `.../work-records/{id}/confirm` | 확정 → 작업지시서 완료, 재고 차감, MTTR 다시 계산 | M | `version` | 확정, 바뀐 기록 번호 (체크 9칸 덜 차면 거부) | FR-MNT-05-05·09·10·14 |
| MNT-12 | POST `/api/maint/quick-records` · `/{id}/confirm` | 간이 작업기록 저장·확정 | 저장 O·M / 확정: 주의 O·M, 다른 공정 정지 M | 알람(또는 원인 점검 요청), 조치, 체크 9칸 | 기록 번호 | SCR-13, FR-MNT-05-13·15 |
| PM-01 | GET `/api/maint/pm-schedule` | 예방 정비 일정 | 전 | 설비, 기간 | 항목·주기·다음 기한·상태, 제때 실시율, 잠금·표지 판단 | SCR-23, FR-MNT-04-01~04·08·09 |
| PM-02 | POST `/api/maint/pm-records` | 정비 시작·끝 기록 (MAINT 상태) | M | `pm_task_id`, 시작/끝, 실시자 | 실시 기록 (소모품 차감, MAINT 상태) | SCR-23, FR-MNT-04-05~07·10 |

### 2.6 보고서·문서 (PRD-02·04, AST-03)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| RPT-01 | GET `/api/reports/shift/{shift_id}` | 교대 보고서 | 조회 전 | — | 생산(총 목표·실적·불량·가동률), 로트, 필수 정지, 병목, 정비, 특이 사항, 인계 사항, 상태 | SCR-15, FR-PRD-02-01~12 |
| RPT-02 | PATCH `/api/reports/shift/{shift_id}` | 저장 | 그 교대 S | `version`, 고친 칸 | 새 버전 | FR-PRD-02-10 |
| RPT-03 | POST `.../shift/{shift_id}/confirm` | 확정 | 그 교대 S | `version` | 확정·잠김 | FR-PRD-02-11 |
| RPT-04 | POST `.../shift/{shift_id}/revise` | 확정 후 수정 | 그 교대 S | `reason`, 고친 칸 | 새 버전, 수정 알림 | FR-AST-03-06·07 |
| RPT-05 | GET·PATCH `/api/reports/daily/{date}` · `/confirm` | 일일 보고서 **[보류]** | 조회 S·M·G / 확정 G | `version` | 하루 생산(목표 180·실적·부족), 손실, 알람, 정비, 로트, 재고, 오늘의 문제 | SCR-16, FR-PRD-04-01~10 |
| DOC-01 | GET `/api/documents` | 문서함 | 전 (역할분) | 종류, 상태, 내 할 일 | 문서 목록 | SCR-18, FR-MNT-05-11·12 |
| DOC-02 | GET `/api/documents/{type}/{id}/revisions` | 수정 이력 | 전 (OPR은 자기 문서) | — | 버전 목록, 바뀐 칸, 사유 | SCR-17, FR-AST-03-01~09 |

### 2.7 로트·품질 (PRD-05, QLT-01)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| LOT-01 | GET `/api/lots` · `/{lot_no}/trace` | 로트 목록 · 추적 | 전 | 작업지시, 상태 | 원자재 → 공정 실적 → 검사 → 출하, 의심 로트 제안 | SCR-19, FR-PRD-05-01~05·09~11 |
| LOT-02 | POST `/api/lots/{lot_no}/hold` · `/release` | 보류 · 해제 | S·G | `reason` (해제는 합격 수량) | 로트 상태 | SCR-19, FR-PRD-05-06·07 |
| LOT-03 | POST `/api/lots/{lot_no}/scrap` · `/scrap/approve` | 폐기 제안 · 승인 | 제안 S / 승인 G | `reason` | 로트 상태 | FR-PRD-05-08 |
| QLT-01 | GET `/api/inspection/results` | 검사 기록 | 전 | 로트 | 측정값, 입력 방식(자동/수동), 부품 온도, 확인 상태 | SCR-20, FR-QLT-01-01~07 |
| QLT-02 | POST `/api/inspection/results` | 게이지·외관 결과 / 수동 입력 ("수동" 표시) | O(측정 담당)·S | 로트, 부품 번호, 항목, 결과 | 기록 | SCR-20, FR-QLT-01-01·19 |
| QLT-03 | POST `/api/inspection/results/{id}/select` | 재측정 값 고르기 · 반장 확인 | S | 고른 측정 | 확인 상태 = 반장 확인 | FR-QLT-01-20~22 |
| QLT-04 | GET `/api/inspection/cmm-imports` | 결과 파일 기록·오류 목록 | 전 | 상태 | 파일 이름, 받은 시각, 상태, 오류 | SCR-20, FR-QLT-01-14~18 |
| QLT-05 | GET `/api/quality/summary` | 불량 집계·관리도·Cpk | 전 | 기간 | 불량 코드별 수, 관리도, Cpk (50개 미만이면 "계산 중") | SCR-20, FR-QLT-01-08~13 |

- 측정 결과 파일 읽기(공유 폴더 감시 → `cmm_import`)는 **서버 안쪽 일**이라 API가 아니다. 폴더 위치·감시 방식은 [선택 필요: 기술 회의].

### 2.8 재고·출하·공구 (INV-01, ML-01)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| INV-01 | GET `/api/inventory` | 재고 13품목 | 전 | — | 재고, 안전 재고, 관리 역할, 부족 여부, 완제품·보류 수량 | SCR-21, FR-INV-01-01~03·09·11 |
| INV-02 | POST `/api/inventory/txns` | 입고 · 실사 조정 | 그 품목 관리 역할 (소모품 M / 공구·원자재·완제품 S) | 품목, 종류, 수량, 사유 | 거래 기록 | FR-INV-01-04·08·13 |
| INV-03 | POST `/api/raw-lots/{id}/inspect` | 원자재 입고 검사 (성적서 대조) | S | 결과 | 사용 가능 / 입고 보류 | FR-INV-01-04 |
| INV-04 | GET·POST `/api/shipments` · PATCH `/{id}` | 출하 조회 · 등록 · 확정 후 수정 | 조회 전 / 등록 S | 출하처, 로트·수량 (합격 로트만, 먼저 합격한 로트부터 제안) / 수정은 `reason` | 출하 번호 (보류 로트면 `INVALID_STATE`) | SCR-21, FR-INV-01-12 |
| INV-05 | PATCH `/api/inventory/items/{id}/safety-stock` | 안전 재고 설정 | G | 값 | — | SCR-25, FR-INV-01-06 |
| TOOL-01 | GET `/api/tools` | 공구 수명 | 전 | 설비 | 사용률·단위·한도, 모델 예측(참고값) | SCR-22, FR-ML-01-01~05·07·08 |
| TOOL-02 | POST `/api/tools/{id}/change` | 공구 교체 기록 → 사용량 0, 재고 사용 | O·M | 사유 | 교체 기록 | SCR-22, FR-ML-01-06, FR-INV-01-05 |

### 2.9 설정·시연 (MGR, 시연 모드)

| ID | 방식 · 주소 | 하는 일 | 역할 | 보내는 값 | 돌려받는 값 | 화면 · 요구사항 |
|---|---|---|---|---|---|---|
| SET-01 | GET·PATCH `/api/settings/notification-rules` | 알림 기준값·재발 확인 기간 | G | 값 | — | SCR-25, FR-AST-02-16 |
| SET-02 | GET·PATCH `/api/settings/targets` | 교대 목표(90)·하루 목표(180) | G | 값 | — | SCR-25 |
| SET-03 | GET·PATCH `/api/settings/users` | 사용자·역할 | G | 값 | — | SCR-25, NFR-SEC-04 |
| SIM-01 | POST `/api/sim/inject` | 시연 사건 넣기 (S1~S6) | 시연 모드 | 사건, 시각 | — | NFR-DATA-10, 설계서 7장 |
| SIM-02 | POST `/api/sim/clock` | 시연 시계 배속·넘기기 (예: 17:00 → 다음 날 06:00) | 시연 모드 | 배속 또는 넘길 시각 | 지금 시연 시각 | NFR-DATA-10, 기획서 15장 |
| SIM-03 | POST `/api/sim/reset` | 시연 데이터 처음으로 [제안] | 시연 모드 | — | — | 시연 연습 |

---

## 3. 실시간 사건 (STR-01)

전송 방식(SSE 등)은 [선택 필요: 기술 회의]. 반영 주기는 NFR-PERF-02 [선택 필요].

| 사건 | 언제 | 담는 것 | 받는 화면 |
|---|---|---|---|
| `state_changed` | 설비 상태가 바뀔 때 | 설비, 새 상태, 시각 | SCR-04·05·26 |
| `wip_changed` / `bottleneck_changed` | 재공 기록 / 병목 바뀜 | 재공 자리별 수 / 병목 공정·원인 | SCR-04·05·26 |
| `alarm` | 알람 발생 | 알람 이벤트, 심각도 | SCR-04·09·26 |
| `urgent_popup` | 정지 등급 알람 | 설비, 알람, 받는 사람(그 설비 O·M) | SCR-08 |
| `notification` | 알림 생김·처리됨 | 알림 카드 | SCR-07, 상단 바 🔔 |
| `kpi_updated` | 작업기록서 확정 등으로 다시 계산 | 바뀐 지표 | SCR-04 [8] |
| `document_changed` | 초안 생김·확정·수정 | 문서 종류·번호·상태 | SCR-11·12·15·18 |
| `connection` | 연결 끊김·다시 연결 | 마지막 갱신 시각 | 알림 띠 (2.8) |

---

## 4. 서버가 스스로 하는 일 (API 아님)

| 일 | 언제 | 근거 |
|---|---|---|
| 교대 보고서 AI비서 초안 만들기 + 그 교대 SUP에게 확정 요청 알림 | 교대 끝 17:00·05:00 | FR-PRD-02-01, FR-AST-02-17 |
| 일일 보고서 초안 **[보류]** | 다음 날 06:00 | FR-PRD-04-01 |
| 작업지시서 AI비서 초안 | OP-30 정지 등급 알람·반복 알람 2단계 | FR-MNT-03-01 |
| 알림 규칙 판단, 보고 순위 매기기 | 기록이 생길 때마다 | FR-AST-02-01~19, FR-AST-COM-21 |
| 지표·손실·이월 계산 | 기록이 생길 때·교대 시작 | DOC-07 6~8장, R-88 |
| 측정 결과 파일 읽기 · 측정 지시 파일 넘기기 | 파일이 생길 때 · 측정 시작 때 | FR-QLT-01-14·15 |
| 보관 기간이 지난 데이터 처리 | 주기 [선택 필요: 기술 회의] | NFR-DATA-13 |

---

## 5. 기능 ↔ API 대응

| 기능 | API | 기능 | API |
|---|---|---|---|
| PRD-01 3D 라인 뷰 | LINE-01~04·07·08, STR-01 | MNT-02 지침카드 | MNT-01 |
| PRD-02 교대 보고서 | RPT-01~04 | MNT-03 작업지시서 | MNT-02~08 |
| PRD-03 작업지시 진행 | LINE-05 | MNT-04 예방 정비 | PM-01·02 |
| PRD-04 일일 보고서 [보류] | RPT-05 | MNT-05 작업기록서 | MNT-09~12 |
| PRD-05 로트 추적 | LOT-01~03 | QLT-01 검사 | QLT-01~05 |
| PRD-06 다시 보기 | LINE-06 | INV-01 재고·출하 | INV-01~05 |
| AST-01 브리핑 | AST-01 | ML-01 공구 수명 | TOOL-01·02 |
| AST-02 알림 | NTF-01~04, STR-01, SET-01 | AST-03 수정 이력 | DOC-01·02, RPT-04, DOCS-02 |
| MNT-01 질문 답변 | AST-02, DOCS-01 | AST-COM 비서 공통 | AST-01·02, MNT-01·10 |
| 공통·권한·시연 | AUTH-01~04, SET-02·03, SIM-01~03 | | |

---

## 6. 남은 [선택 필요]·[보류]

| 항목 | 정할 곳 |
|---|---|
| 주소·형식 방식, 서버 프레임워크, 로그인 방식, 실시간 전송 방식·주기 | 기술 회의 |
| 비서 API 안쪽(모델, 검색 방식, 도구 호출 형식) — 바깥 모양(AST-01·02)만 이 문서에서 정함 | LLM 담당 팀원 |
| RPT-05 일일 보고서, LINE-07·08 정지 사유 화면 | 팀 (제작 보류 / 필요 여부) |
| 모니터링용 계정의 권한 | 팀 (일일 보고서 결정 때) |
| 측정 결과 파일 폴더·감시 방식, 보관 기간 처리 주기 | 기술 회의 |

## 7. 개정 기록

| 버전 | 날짜 | 내용 |
|---|---|---|
| v1 | 2026-10-07 | 처음 작성. 기획서 12.5 목록을 API 63개(ID 기준)로 풀고, 공통 규칙·오류 코드·실시간 사건·서버 자동 작업·기능 대응표를 넣음 |
