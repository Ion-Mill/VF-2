# 03. API 명세

> **주소·오류 코드는 `11_automotive/API명세서_v1.md`(API 63개)를 그대로 따른다** (2026-10-08). API ID ↔ 처리기 대응은 6장.
> 서버를 띄우면 `/docs`(OpenAPI)가 요청·응답 모델까지 보여 준다. 이 문서는 사람이 읽는 요약이다.
> 4장 표는 `tools/gen_api_doc.py`가 라우터에서 만든다 (권한 칸 = 처리기에 걸린 `require(...)`).

## 1. 공통 (API명세서 1장)

| 항목 | 규칙 |
|---|---|
| 주소 | 모두 `/api/...`, 요청·응답은 JSON. 상태 확인 `GET /api/health` |
| 로그인 | `POST /api/auth/login` → `{"access_token", "role_code", "home"}` → 이후 `Authorization: Bearer <token>`. `POST /api/auth/logout`, `GET /api/me` |
| 서비스 (명세서 밖) | 시뮬레이터 `X-Service-Key: <MOM_INGEST_KEY>` (`/api/ingest/*`), AI 비서 서비스 `X-Service-Key: <MOM_ASSISTANT_KEY>` (`/api/assistant/tools·drafts·notifications/*`) |
| 권한 | 처리기마다 `role_permission`(target·action)으로 막는다. 없으면 403 `FORBIDDEN`. "누가 확정·승인"은 DB가 한 번 더. MGR은 모든 조회 |
| 이름 | 응답 칸 이름은 논리 ERD 속성 이름 (`target_qty`, `carry_over_qty` …) |
| 시각 | ISO 8601 + 시간대 (`2026-09-15T13:00:00+09:00`). 교대는 `shift_id` (`2026-09-15-D`). 기간을 비우면 시연 시계 기준 최근 24시간(일부 7일·2시간) |
| 숫자 | 수량·시간은 DB가 계산한 값 그대로. 추정 값은 `loss_is_estimated` 등으로 표시 |
| 가상 표시 | 운영 데이터 응답마다 `is_synthetic: true` (NFR-DATA-08) — 객체는 맨 위, **목록은 줄마다** [제안], 머리글 `X-Synthetic-Data`. 로그인·`/api/me`·오류·실시간·서버끼리 API에는 없음 |
| 목록 | `limit` (기본 100, 최대 500~1000). 페이지 번호 대신 기간·상태로 거른다 |
| 고치기 | 문서를 고치는 요청은 `version`(지금 버전)을 함께 보낸다 — 다르면 409 `CONFLICT_VERSION`. 본문 `{"version": n, "changes": {칸: 새 값}}` → `{"version_no": n+1}` |
| 확정 후 수정 | `reason` 필수 → 새 버전 + 문서 수정 알림 (보고서 `…/revise`, 작업지시서·작업기록서는 `PATCH` + `reason`) |
| 출처 | 비서·지침카드의 출처는 `{doc_name, doc_no, rev, section}`만 (원문 출처 없음, D-03) |

**오류 형식:** `{"code": "...", "message": "쉬운 한국어 문장", "detail": {...}}` — 코드 7개 (`app/errors.py`, 자세한 갈래는 `detail.reason`)

| code | HTTP | 예 |
|---|---|---|
| `UNAUTHORIZED` | 401 | 로그인 없이 요청, 토큰 만료, 비밀번호 틀림 |
| `FORBIDDEN` | 403 | OPR가 교대 보고서 확정, 받은 사람이 아닌데 긴급 팝업 확인 |
| `NOT_FOUND` | 404 | 없는 로트 번호, 없는 주소, 없는 품목(외래 키 23503) |
| `VALIDATION` | 422 | 값이 틀림·빠짐(요청 검증), 바뀐 칸 없음(`NO_CHANGE`), 확정 뒤 수정에 사유 없음(`REASON_REQUIRED`) |
| `INVALID_STATE` | 409 | 승인 전 작업 시작, 담당 없이 승인, 체크 9칸 덜 채우고 확정(R-32), 보류 로트 출하, 다른 교대 반장의 확정(R-36), 잠정 칸이 있는 일일 보고서 확정 — DB 업무 규칙 글(R-번호) 그대로 |
| `CONFLICT_VERSION` | 409 | 두 사람이 같은 문서를 동시에 고침 (`detail.current_version`) |
| `ASSISTANT_UNAVAILABLE` | 503 | AI 비서 서비스가 없거나·멈추거나·형식이 틀림 → 화면은 기본 문구 |

그 밖 예상 못 한 서버 오류만 500 `INTERNAL_ERROR` (명세서 밖, 내용은 싣지 않음).

**실시간 (STR-01):** `GET /api/stream/events?token=<JWT>` (SSE). 사건 `state_changed`·`wip_changed`·`bottleneck_changed`·`alarm`·`urgent_popup`·`notification`·`kpi_updated`·`document_changed`·`connection`, 데이터 `{"table","op","id","equipment_id",…,"at"}` → 화면이 해당 API를 다시 부름. `connection`(다시 연결·RESYNC)이면 전부 다시.

## 2. 역할별 첫 화면 (로그인 응답 `home`, UI 설계서 4.1)

이번 교대 첫 로그인이면 MNT·SUP·MGR은 SCR-02 브리핑을 먼저 연다 — 이 판단(실제 시각 vs 시연 시계)은 화면 쪽에서 하거나 API에 더한다 [선택 필요] (`05_결정기록.md`).

| 역할 | 첫 화면 | 자주 쓰는 API |
|---|---|---|
| OPR 현장 작업자 | SCR-26 현장 보기 | `/api/line/twin`, `/api/assistant/briefing`(요약형), `/api/notifications`, `/api/maint/guide-card/{id}`, `PATCH /api/downtimes/{id}`, `/api/maint/quick-records`, `/api/inspection/results`, `/api/tools/{id}/change` |
| MNT 보전 담당자 | SCR-18 문서함 (내 할 일) | `/api/documents?mine=true`, `/api/maint/work-orders`, `/api/maint/work-records/{id}`, `/api/maint/pm-schedule`, `/api/maint/pm-records` |
| SUP 라인 반장 | SCR-04 3D 라인 뷰 | `/api/assistant/briefing`, `/api/production/target`, `/api/maint/work-orders/{no}/approve`, `/api/lots/{no}/hold`, `/api/shipments`, `/api/reports/shift/{id}/confirm` |
| MGR 공장 관리자 | SCR-16 일일 보고서 | `/api/reports/daily/{date}`·`/confirm`, `/api/kpi`, `/api/lots/{no}/scrap/approve`, `/api/settings/*` |

## 3. 주요 흐름 (시험 `tests/test_routers_db.py`에서 이 순서로 돌려 봄)

**알람 → 작업지시서 → 작업기록서 확정**

1. 시뮬레이터 `POST /api/ingest/alarms {"equipment_id":"VF2-02","alarm_code":"254"}` → 긴급 알림(그 공정 작업자 + 보전 담당자 + 반장) → SSE `urgent_popup`
2. AI 비서 서비스 `POST /api/assistant/drafts/work-order` → `MW-0902` (AI비서 초안, v0 = AI). 보전 담당자가 직접 `POST /api/maint/work-orders`로 만들면 수정 중·v0 = 사람에서 시작
3. MNT `PATCH /api/maint/work-orders/MW-0902 {"version":0,"changes":{"title":"…"}}` → 수정 중 v1 (AI비서 초안 그대로는 승인 불가)
4. SUP `POST …/assign {"mnt_user_id":"U07"}` → `POST …/approve {"version":1}` (담당자 없으면 409 `INVALID_STATE`)
5. MNT `POST …/start` → `POST /api/maint/work-records {"wo_no":"MW-0902", …}` → 잠금·표지 9단계 + 작업 순서 체크칸
6. MNT `PATCH /api/maint/work-records/MR-0902 {"version":0,"checks":[{"check_seq":1},…],"parts":[{"item_no":"CS-SLUB","qty":0.5}]}` → `POST …/confirm {"version":0}` (9단계 덜 되면 409 "R-32") → 작업지시서 완료·알람 알림 자동 처리·부품 재고 차감·SSE `kpi_updated`
7. SUP `POST …/check` (반장 확인). 확정 뒤 고치면 `reason` 필수 + 확인 표시가 풀림

**로트 보류 → 출하**

1. SUP `POST /api/lots/LOT-2609-041-1/hold {"trigger_type":"AI_SUSPECT","reason":"충돌 의심"}` → 다음 1~2개 로트 강화 검사
2. 검사 뒤 `POST /api/lots/LOT-2609-041-1/release {"pass_qty": 30}` (합격 0개면 409 — 전부 불량은 폐기 `…/scrap` → MGR `…/scrap/approve`)
3. `GET /api/shipments/candidates` (합격·해제 로트, FIFO 순) → `POST /api/shipments {"customer_code":…,"due_date":…,"lines":[{"lot_no":…,"qty":30}],"confirm":true}` (먼저 합격한 로트를 건너뛰면 `fifo_skip_reason` 필수, R-68). 줄 단위 편집은 `PUT·DELETE /api/shipments/{no}/lines/{lot}` + `POST …/confirm`

**측정 결과**

1. `POST /api/inspection/instructions {"lot_no":…,"part_seq":5}` (발췌 로트는 1·5의 배수만) → OPR `POST …/{id}/start`
2. 측정기 PC가 공유 폴더에 CSV → 감시가 받음 (또는 `POST /api/inspection/cmm-imports` 파일 올리기, `POST /api/ingest/cmm` 내용 보내기)
3. `GET /api/inspection/cmm-imports?status=PROBLEM` → 확인 필요 값은 SUP `POST /api/inspection/results/{id}/select`. 수동 입력은 `POST /api/inspection/results {"measured_value":…}` ("수동", 확인 필요에서 시작)

**보고서**

1. 17:00 스케줄러가 교대 보고서 AI비서 초안 + 그 교대 반장에게 확정 요청 → SUP `PATCH /api/reports/shift/{id} {"version":0,…}` → `POST …/confirm {"version":1}` (주간이면 야간 이월 다시 계산)
2. 다음 날 06:00 일일 보고서 초안 → 교대 보고서가 확정될 때마다 칸을 다시 채움 → MGR `POST /api/reports/daily/{date}/confirm` (잠정 칸이 있으면 409)

**AI 비서**

1. 화면 `POST /api/assistant/chat {"question":"VF2-01 주축 부하 괜찮아?","context":{…}}` → 백엔드가 AI 비서 서비스(`MOM_ASSISTANT_URL/chat`)로 넘김 → `{"answer","sources","related","status"}` (없으면 503)
2. 비서 서비스 `GET /api/assistant/tools?on_behalf_of=U02` → 그 사용자가 쓸 수 있는 도구 JSON Schema (OPR에게는 `work_records` 없음)
3. `POST /api/assistant/tools/kpi {"on_behalf_of":"U10","args":{"from_date":"2026-09-15","to_date":"2026-09-15"}}` → `{"rows":[…], "now": …}` (읽기 전용 계정, 접근 기록)
4. 초안 저장: `POST /api/assistant/drafts/work-order`, `/drafts/work-record` / 알림 문장: `PUT /api/assistant/notifications/{id}/message`

## 4. 엔드포인트 목록

<!-- BEGIN:api -->
<!-- tools/gen_api_doc.py 가 만든 표 (145개). -->
| 방법 | 경로 | 권한 (role_permission target·action) | 설명 |
|---|---|---|---|
| POST | `/api/auth/login` | 없음 | 아이디·비밀번호 로그인 → JWT. 실패도 접근 기록에 남는다 |
| POST | `/api/auth/logout` | 로그인 | 로그아웃 (AUTH-02). 토큰은 화면이 버린다 (서버에 세션 없음 — 로그인 방식은 [선택 필요: 기술 회의]). 접근 기록에 남긴다 |
| POST | `/api/demo/role` | 없음 | 역할 바꿔 보기 (AUTH-04, 시연 모드만 — NFR-DATA-12). 바뀐 역할의 토큰·첫 화면. 시연 모드가 아니면 없음과 같다 |
| GET | `/api/me` | 로그인 | 내 정보·권한 (AUTH-03): 역할·담당 공정·첫 화면·할 수 있는 일 목록 (화면이 버튼을 숨길 때 씀 — 막는 것은 서버) |
| GET | `/api/codes` | 로그인 | 코드 한국어 이름 (논리 ERD 6장). 화면과 비서가 같은 이름을 쓰게 한다. |
| GET | `/api/dataset` | 로그인 | 가상 데이터 정보 (R-59, NFR-DATA-08). 화면 구석의 '가상 운영 데이터' 표시는 2026-10-07 팀 UI 검토로 뺐다 — |
| GET | `/api/admin/retention` | `SETTINGS·SETTING` | 보관 기간이 지난 행 수 (지우지 않음). 실제 삭제·집계 방식은 [선택 필요: 기술 회의] |
| GET | `/api/settings/targets` | `SETTINGS·SETTING` | 교대 목표(90)·하루 목표(180) — 지금 교대와 다가오는 교대 (SET-02). 총 목표 = 목표 + 이월 (R-88) |
| PATCH | `/api/settings/targets` | `SETTINGS·SETTING` | 목표 바꾸기 (MGR, SET-02). 아직 시작하지 않은 교대·근무일에만 — 지난·진행 중 값은 그대로. 야간 이월을 다시 계산한다 |
| GET | `/api/settings/users` | `SETTINGS·SETTING` | 사용자·역할 목록 (SET-03, NFR-SEC-04). 비밀번호 해시는 내보내지 않는다 |
| PATCH | `/api/settings/users` | `SETTINGS·SETTING` | 사용자·역할 고치기 (MGR, SET-03). 권한 표는 다음 요청부터 (60초 캐시) |
| GET | `/api/sim/clock` | 로그인 | 시연 시계 지금 값 (app_now) |
| POST | `/api/sim/clock` | 로그인 | 시연 시계 배속·일시정지·넘기기 (API-SIM-02, NFR-DATA-10). 시연 모드에서는 누구나 배속·일시정지·17:00 넘기기, |
| POST | `/api/sim/inject` | 로그인 | 시연 사건 넣기 (SIM-01, NFR-DATA-11) — 알람 1건을 '주입' 표시로 기록 (알림·반복 알람 판정은 실제와 같게). |
| POST | `/api/sim/reset` | 로그인 | 시연 데이터 처음으로 (SIM-03, 시연 모드만): 운영 데이터를 시연 기준점으로 되돌리고 시연 시계를 그 시각에 멈춘다. |
| POST | `/api/sim/snapshot` | `SETTINGS·SETTING` | 시연 기준점 만들기 (시연 모드, MGR): 지금 운영 데이터를 SIM-03의 "처음"으로 삼는다. |
| GET | `/api/line/layout` | `LINE_VIEW·VIEW` 또는 `FIELD_VIEW·VIEW` | 공장·설비 실제 크기 배치 (LINE-01) — 바닥·통로·재공 자리·설비 외형·부품 도형. 3D 장면을 처음 그릴 때 한 번 |
| GET | `/api/line/twin` | `LINE_VIEW·VIEW` 또는 `FIELD_VIEW·VIEW` | 지금 상태 한 번에 (LINE-02): 설비별 상태·지속 시간·현재 로트·현재 알람, 재공, 병목, 교대 진행(총 목표 = 목표 + 이월, |
| GET | `/api/replay` | `LINE_VIEW·VIEW` | 다시 보기 (LINE-06, PRD-06): 시각별 상태·재공·알람·병목 사건, equipment_id를 주면 그 설비 센서 값 |
| GET | `/api/alarms` | `LINE_VIEW·VIEW` 또는 `FIELD_VIEW·VIEW` 또는 `GUIDE_CARD·VIEW` | 기간 안 알람 목록 (기본 최근 24시간) |
| GET | `/api/alarms/{alarm_event_id}` | `LINE_VIEW·VIEW` 또는 `FIELD_VIEW·VIEW` 또는 `GUIDE_CARD·VIEW` | 알람 1건 + 코드집 내용 |
| GET | `/api/maint/guide-card/{alarm_event_id}` | `GUIDE_CARD·VIEW` | 지침카드 (MNT-01, FR-MNT-02): 알람·심각도·누가·연쇄 알람·먼저 할 일·안전 블록·생산 영향·지난 기록·출처 목록. |
| GET | `/api/downtimes` | `DOWNTIME_REASON·VIEW` | 정지 구간 목록 + 비서 추천 사유 (LINE-07, SCR-14 — 필요 여부 판단 중). shift_id 또는 기간(기본 최근 24시간) |
| PATCH | `/api/downtimes/{state_log_id}` | `DOWNTIME_REASON·INPUT` 또는 `DOWNTIME_REASON·CONFIRM` | 정지 사유 입력 (OPR·MNT) / 확정 (SUP) — LINE-08, R-21. 바뀐 구간을 돌려준다 |
| GET | `/api/notifications` | `NOTIFICATION·VIEW` | 알림 목록 (API-NTF-01, 이브 사이드바 알림 탭): 자기 역할분, MGR은 전부 (R-76). 카드마다 중요도·보고 순위·×N 묶음·폭주· |
| GET | `/api/notifications/{notification_id}` | `NOTIFICATION·VIEW` | 알림 1건 — 받은 사람만, MGR은 전부 (R-76) |
| POST | `/api/notifications/{notification_id}/read` | `NOTIFICATION·VIEW` | 읽음 (NTF-02, 처리 아님 — 받는 사람 본인). 문서 수정 알림만은 받은 사람이 열면 처리된다 (6.36). |
| POST | `/api/notifications/{notification_id}/resolve` | `NOTIFICATION·VIEW` | 처리 (NTF-03). 처리할 수 있는 역할은 규칙의 processor_roles (DB가 확인, 자동 처리 규칙은 INVALID_STATE). |
| POST | `/api/notifications/{notification_id}/ack` | `NOTIFICATION·VIEW` | 긴급 팝업 확인 (API-NTF-04): 소리 끔·읽음 표시. 처리는 아니다 — 긴급 팝업은 로그인한 전원이 받고(2026-10-13), |
| GET | `/api/assistant/briefing` | `BRIEFING·VIEW` | 교대 시작 브리핑 재료 (AST-01, FR-AST-01-02~07, FR-AST-COM-21). 비서는 이 순서대로 문장만 쓴다. |
| GET | `/api/assistant/briefing/checks` | `BRIEFING·VIEW` | 브리핑 "먼저 챙길 일"에서 본인이 체크한 항목 (2026-10-20). 다시 열어도 체크가 남게 한다 — 개인 메모일 뿐 |
| POST | `/api/assistant/briefing/checks` | `BRIEFING·VIEW` | 체크하기·풀기 (checked = true / false). 같은 요청을 거듭 보내도 결과가 같다 (체크한 적 없는 걸 풀어도 오류 아님) |
| GET | `/api/settings/notification-rules` | `SETTINGS·VIEW` | 알림 규칙 목록 (SET-01, 6.36) |
| PATCH | `/api/settings/notification-rules` | `SETTINGS·SETTING` | 알림 규칙 켜기·끄기·설명 (SET-01, MGR — DB 트리거가 다시 확인). 기준 숫자 바꾸기는 [선택 필요: 기술 회의] |
| GET | `/api/stream/events` | 로그인 (?token=) | 실시간 사건 (STR-01, SSE). 바뀐 것의 종류·번호만 보낸다 — 화면이 해당 API를 다시 부른다. ?token= (EventSource). |
| GET | `/api/production/target` | `LINE_VIEW·VIEW` 또는 `FIELD_VIEW·VIEW` 또는 `PRODUCTION·VIEW` | 목표 대비 실적·예측 (LINE-03, FR-PRD-01-15, FR-AST-02-04). 총 목표 = 목표 + 이월 (이월은 같은 날 |
| GET | `/api/production/orders` | `PRODUCTION·VIEW` | 작업지시 진행 표 (LINE-05, PRD-03): 목표·완료·불량·로트·지금 공정·납기·지연 여부·상태 |
| GET | `/api/kpi` | `KPI·VIEW` | 지표 (LINE-04): OEE·가동률·성능·양품률(교대별)과 주의 표시, MTTR·MTBF(설비별 30일, 주의 = MTTR 120분 초과). |
| GET | `/api/kpi/stops` | `KPI·VIEW` | 정지 사유 순위 (손실 정지만, 계획 정지 제외). 3D 화면에서는 뺐고 교대 보고서 필수 정지 칸·비서 질문에 쓴다 |
| GET | `/api/lots` | `PRODUCTION·VIEW` | 로트 목록 (LOT-01) — 작업지시·상태로 거르기 |
| GET | `/api/lots/suspects` | `LOT_TRACE·VIEW` | 의심 로트 제안 목록 (API-LOT-01, FR-PRD-05-05, 2026-10-20): 정지 등급 알람 때 그 설비에서 가공 중이던 로트(연쇄 알람은 첫 |
| GET | `/api/lots/{lot_no}` | `PRODUCTION·VIEW` | 로트 1개 (완료 수량·검사 방식·출하 수량) |
| GET | `/api/lots/{lot_no}/trace` | `LOT_TRACE·VIEW` | 로트 추적 (LOT-01, FR-PRD-05): 원자재 → 공정·설비·작업자 → 검사 → 보류 → 출하 + 의심 로트 제안 이유(suspect, 2026-10-20) |
| POST | `/api/lots/{lot_no}/judge` | `QUALITY·CHECK` | 로트 판정 다시 돌리기 (보통은 검사 결과가 들어올 때 DB가 부른다). PASS / HOLD_REVIEW / NOT_READY |
| GET | `/api/holds` | `LOT_TRACE·VIEW` | 보류 목록 (열린 것만 기본) |
| POST | `/api/lots/{lot_no}/hold` | `LOT_HOLD·INPUT` | 보류 (LOT-02, 사람만 — 비서는 제안만, R-51). 보류되면 측정은 강화 검사로 바뀐다. 로트 상태를 돌려준다 |
| POST | `/api/lots/{lot_no}/release` | `LOT_HOLD·INPUT` | 보류 해제 (LOT-02, SUP·MGR) — 합격 수량을 정해 출하 가능으로 (합격 0개면 INVALID_STATE — 전부 불량은 폐기) |
| POST | `/api/lots/{lot_no}/scrap` | `LOT_SCRAP·CREATE` | 폐기 제안 (LOT-03, SUP) → 승인 (MGR) |
| POST | `/api/holds/{hold_id}/resume-normal` | `LOT_HOLD·INPUT` | 강화 → 보통 검사 복귀 (R-29, FR-QLT-01-07, DOC-06 3.3 — 2026-10-20). 반장이 확인한다. ⓐ 보류 뒤 원인 조치 기록(확정된 |
| POST | `/api/lots/{lot_no}/scrap/approve` | `LOT_SCRAP·APPROVE` | 폐기 승인 (LOT-03, MGR) |
| GET | `/api/maint/work-orders` | `WORK_ORDER·VIEW` | 작업지시서 목록 (MNT-02). mine = 내가 담당인 것만 |
| GET | `/api/maint/work-orders/{wo_no}` | `WORK_ORDER·VIEW` | 작업지시서 (MNT-03): 계기·자동 칸·제목·증상·작업 순서·안전 블록 표시·예상 부품·담당·상태·승인 대기 시간. |
| POST | `/api/maint/work-orders` | `WORK_ORDER·CREATE` | 보전 담당자가 직접 만들기 → 수정 중(v0 = 사람). AI비서 초안과 같은 DB 함수 (같은 알람·2단계가 겹치면 기존 것에 더함, R-71) |
| PATCH | `/api/maint/work-orders/{wo_no}` | `WORK_ORDER·EDIT` | 내용 수정 = 새 버전 (MNT-04, AI비서 초안 → 수정 중) |
| POST | `/api/maint/work-orders/{wo_no}/assign` | `WORK_ORDER·ASSIGN` | 담당 지정 (MNT-05, SUP — 승인 전 필수) |
| POST | `/api/maint/work-orders/{wo_no}/approve` | `WORK_ORDER·APPROVE` | 승인 (MNT-06, SUP — MGR 대리). 담당 없이·AI비서 초안 그대로는 INVALID_STATE (사람이 열어 수정 중이 되어야 함, 6.13) |
| POST | `/api/maint/work-orders/{wo_no}/start` | `WORK_ORDER·EDIT` | 작업 시작 (MNT-07, 담당 MNT만): 승인됨 → 진행 중. 승인 전이면 INVALID_STATE (6.13), 담당이 아니면 FORBIDDEN |
| POST | `/api/maint/work-orders/{wo_no}/cancel` | `WORK_ORDER·CANCEL` | 취소 (MNT-08, MGR — 사유 필수) |
| GET | `/api/maint/work-records` | `WORK_RECORD·VIEW` 또는 `WORK_RECORD_SIMPLE·VIEW` | 작업기록 목록 (OPR은 간이 기록만). 설비·알람 번호로 거르기 (같은 사례 찾기 — 2026-10-20) |
| GET | `/api/maint/work-records/{record_no}` | `WORK_RECORD·VIEW` 또는 `WORK_RECORD_SIMPLE·VIEW` | 작업기록서 조회 (MNT-09): 칸 전부 + 체크 항목(잠금·표지 9칸·작업 순서) + 쓴 부품 |
| POST | `/api/maint/work-records` | `WORK_RECORD·CREATE` | 정식 작업기록서 만들기 (작업지시서 1건 = 1건). 잠금·표지 9단계 + 작업 순서 체크칸이 함께 생긴다 |
| PATCH | `/api/maint/work-records/{record_no}` | `WORK_RECORD·EDIT` 또는 `WORK_RECORD_SIMPLE·EDIT` | 작업기록서 수정 (MNT-09): 고친 칸(새 버전)·체크·사용 부품을 한 번에. 칸 전부를 돌려준다 |
| POST | `/api/maint/work-records/{record_no}/checks/{check_seq}` | `WORK_RECORD·EDIT` 또는 `WORK_RECORD_SIMPLE·EDIT` | 체크 1칸 (잠금·표지 단계·작업 순서 — 체크한 사람·시각이 남는다) |
| PUT | `/api/maint/work-records/{record_no}/parts` | `WORK_RECORD·EDIT` 또는 `WORK_RECORD_SIMPLE·EDIT` | 쓴 부품 1줄 (확정할 때 재고에서 빠진다) |
| POST | `/api/maint/work-records/{record_no}/assist` | `WORK_RECORD·EDIT` | 메모를 비서로 정리 (MNT-10): AI 비서 서비스가 원인·조치 칸 AI비서 초안을 돌려준다 (저장하지 않음 — 보전 담당자가 |
| POST | `/api/maint/work-records/{record_no}/confirm` | `WORK_RECORD·CONFIRM` 또는 `WORK_RECORD_SIMPLE·CONFIRM` | 확정 (MNT-11): 작업지시서 완료·사용 부품 재고 차감·알람 알림 자동 처리·MTTR 다시 계산 (정식 = MNT). |
| POST | `/api/maint/work-records/{record_no}/check` | `WORK_RECORD·CHECK` | 반장 확인 표시 (정식 기록, 확정 뒤) |
| POST | `/api/maint/quick-records` | `WORK_RECORD_SIMPLE·CREATE` | 간이 작업기록 저장 (MNT-12): 주의 등급 알람·다른 공정 알람·원인 점검 요청. AI비서 초안 없음. |
| POST | `/api/maint/quick-records/{record_no}/confirm` | `WORK_RECORD_SIMPLE·CONFIRM` | 간이 작업기록 확정 (MNT-12): 주의 등급은 OPR·MNT, 다른 공정 정지 등급·원인 점검은 MNT만 (DB가 다시 확인) |
| GET | `/api/maint/pm-schedule` | `PM_SCHEDULE·VIEW` | 예방 정비 일정 (PM-01): 항목·주기·다음 기한·넘긴 날 수·잠금·표지 수준, 제때 실시율(기간, 기본 최근 30일 — 목표 90%) |
| POST | `/api/maint/pm-records` | `PM_RECORD·CREATE` | 예방 정비 실시 기록 (PM-02) 저장 (v0). 확정하면 소모품 재고 차감 (…/confirm) |
| POST | `/api/maint/pm-tasks/{pm_task_id}/start` | `PM_RECORD·CREATE` | [정비 시작] (FR-MNT-04-10, API-PM-02 — 2026-10-20): 실시 기록(수정 중)을 만들고 그 설비에 MAINT 구간을 연다. |
| POST | `/api/maint/pm-records/{pm_record_id}/end` | `PM_RECORD·CREATE` | [정비 끝 · 실시 기록] (FR-MNT-04-10): MAINT 구간을 닫고 실시 시각 = 끝난 시각, 결과를 적는다 (v0). 확정은 …/confirm |
| GET | `/api/maint/pm-records/{pm_record_id}` | `PM_RECORD·VIEW` | 예방 정비 실시 기록 1건 |
| PATCH | `/api/maint/pm-records/{pm_record_id}` | `PM_RECORD·EDIT` | 예방 정비 기록 고치기 = 새 버전 |
| POST | `/api/maint/pm-records/{pm_record_id}/confirm` | `PM_RECORD·CONFIRM` | 예방 정비 기록 확정 → 소모품 재고 차감·기한 알림 자동 처리 |
| GET | `/api/inventory` | `INVENTORY·VIEW` | 재고 13품목 (INV-01): 재고·안전 재고·관리 역할·부족 여부, 완제품·보류 수량 |
| GET | `/api/inventory/{item_no}/txns` | `INVENTORY·VIEW` | 품목 1개의 거래 내역 (잔량 누계) |
| POST | `/api/inventory/txns` | `INV_RECEIPT·INPUT` | 입고 · 실사 조정 (INV-02): 그 품목 관리 역할만 (소모품 MNT / 공구·원자재·완제품 SUP — R-77, DB 확인). |
| PATCH | `/api/inventory/items/{item_no}/safety-stock` | `SAFETY_STOCK·SETTING` | 안전 재고 설정 (INV-05, MGR). 완제품은 대상 아님 |
| POST | `/api/raw-lots` | `INV_RECEIPT·INPUT` | 원자재 입고 → 원자재 로트(입고 검사 대기) + 입고 거래. 원자재 품목만, 관리 역할(SUP)만 (13.2) |
| POST | `/api/raw-lots/{material_lot_no}/inspect` | `MATERIAL_CHECK·INPUT` | 원자재 입고 검사 (INV-03, SUP — 성적서 대조) → 사용 가능 / 입고 보류 |
| GET | `/api/shipments` | `SHIPMENT·VIEW` | 출하 목록 (INV-04) |
| GET | `/api/shipments/candidates` | `SHIPMENT·VIEW` | 출하할 수 있는 로트 (합격·해제, 남은 완제품 있음) — 먼저 합격한 순 (FIFO 제안, R-67) |
| GET | `/api/shipments/{shipment_no}` | `SHIPMENT·VIEW` | 출하 1건 + 줄 |
| POST | `/api/shipments` | `SHIPMENT·CREATE` | 출하 등록 (INV-04, SUP): 출하처·로트·수량 (합격·해제 로트만 — 보류 로트면 INVALID_STATE). confirm이면 확정까지. |
| PUT | `/api/shipments/{shipment_no}/lines/{lot_no}` | `SHIPMENT·EDIT` | 출하 줄 넣기·수량 바꾸기 (초안, 합격한 로트만) |
| DELETE | `/api/shipments/{shipment_no}/lines/{lot_no}` | `SHIPMENT·EDIT` | 출하 줄 빼기 (초안만) |
| POST | `/api/shipments/{shipment_no}/confirm` | `SHIPMENT·CONFIRM` | 출하 확정 (SUP): FIFO·남은 수량 확인 → 완제품 재고 차감 → 잠금. QR 확인 필수 설정이면 안 찍은 로트가 없어야 함 |
| PATCH | `/api/shipments/{shipment_no}` | `SHIPMENT·EDIT` | 출하 고치기 = 새 버전 (INV-04 확정 후 수정 — reason 필수) |
| GET | `/api/tools` | `TOOL_LIFE·VIEW` | 공구 수명 (TOOL-01): 사용률·단위·한도·남은 부품 수 |
| GET | `/api/tools/{tool_id}/changes` | `TOOL_LIFE·VIEW` | 공구 교체 내역 |
| POST | `/api/tools/{tool_id}/change` | `TOOL_CHANGE·INPUT` | 공구 교체 기록 (TOOL-02): 사용량 0 + 재고 차감 + 수명 알림 자동 처리 |
| POST | `/api/qr/scan` | `INVENTORY·VIEW` | QR 조회: 로트·원자재 로트·품목의 지금 상태 + 이 역할이 할 수 있는 일. 없는 번호면 found=false (기록은 남김) |
| GET | `/api/qr/label/{kind}/{no}` | `INVENTORY·VIEW` | 라벨에 넣을 QR 내용과 사람이 읽을 줄. QR 그림은 화면(브라우저)이 그린다 — 서버는 글자만 준다 |
| POST | `/api/qr/inventory` | `INV_RECEIPT·INPUT` | 품목 QR로 입고·실사 (INV-02와 같은 권한 — 그 품목 관리 역할만). 원자재는 로트로 입고(/api/raw-lots), |
| POST | `/api/shipments/{shipment_no}/qr-check` | `SHIPMENT·EDIT` | 출하 전 확인 (출하 등록 3단계): 내보낼 로트 꼬리표를 찍어 출하 줄과 맞는지 본다. 작성 중(DRAFT) 출하만. |
| GET | `/api/qr/scans` | `INVENTORY·VIEW` | 찍은 기록 (최근 순): 누가·언제·무엇을·결과. 비서가 "이 로트 출하 전에 확인했어?"에 답할 때도 씀 |
| GET | `/api/inspection/results` | `QUALITY·VIEW` | 검사 기록 (QLT-01): 로트의 측정값·입력 방식(자동/수동/태블릿)·부품 온도·확인 상태 (재측정 포함, 판정에 쓰는 값 표시) |
| POST | `/api/inspection/results` | `QUALITY·INPUT` 또는 `QUALITY·CHECK` | 게이지·외관 결과 (태블릿 합격·불합격, FR-QLT-01-20) 또는 3차원 측정기 값 수동 입력 (QLT-02, FR-QLT-01-19 — "수동" 표시, |
| POST | `/api/inspection/results/{result_id}/select` | `QUALITY·CHECK` | 재측정 값 고르기 · 반장 확인 (QLT-03, SUP, FR-QLT-01-20~22) → 확인 상태 = 반장 확인 |
| GET | `/api/inspection/cmm-imports` | `QUALITY·VIEW` | 결과 파일 기록·오류 목록 (QLT-04): 파일 이름·받은 시각·상태·오류 |
| POST | `/api/inspection/cmm-imports` | `QUALITY·INPUT` 또는 `QUALITY·CHECK` | 결과 파일 직접 올리기 (보통은 공유 폴더 감시 app/workers/cmm_watcher.py가 받는다). 측정 담당·반장 |
| GET | `/api/inspection/instructions` | `QUALITY·VIEW` | 열린 측정 지시 |
| POST | `/api/inspection/instructions` | `QUALITY·INPUT` 또는 `QUALITY·CHECK` | 측정 지시 (R-78). 발췌 로트는 1·5의 배수 순번만, 보류 로트는 강화 검사 — DB가 정한다. 측정 담당·반장 |
| POST | `/api/inspection/instructions/{instruction_id}/start` | `QUALITY·INPUT` | 측정 시작 (측정 담당 작업자가 부품을 CMM에 올림). 이때부터 결과 미수신 시간을 잰다. |
| GET | `/api/quality/summary` | `QUALITY·VIEW` | 불량 집계·관리도·Cpk (QLT-05, FR-QLT-01-08~13): 불량 코드별 수(기본 최근 7일), 기준값이 있는 항목마다 관리도 점(최근 |
| GET | `/api/quality/cpk` | `QUALITY·VIEW` | Cpk (I-MR) 항목 하나. 50개 미만이면 '계산 중'. 설비별(가공 설비 — 05 결정기록 P-11)은 참고용 |
| POST | `/api/quality/items/{product_code}/{item_seq}/resume-sampling` | `SETTINGS·SETTING` | 전수 측정 → 보통(발췌) (DOC-06 §5.2 "다시 기준 이상 → 관리자 승인 후 보통", 2026-10-20). Cpk 기준 미달이면 교대 보고서 초안 때 |
| GET | `/api/quality/defects` | `QUALITY·VIEW` | 불량 코드별 수량 (기본 최근 7일) |
| GET | `/api/reports/shift/{shift_id}` | `SHIFT_REPORT·VIEW` | 교대 보고서 (RPT-01): 생산(총 목표 = 목표 + 이월·실적·불량·가동률), 특이 사항, 인계 사항, 상태, 버전, 필수 정지 stops[] |
| PATCH | `/api/reports/shift/{shift_id}` | `SHIFT_REPORT·EDIT` | 저장 (RPT-02, 그 교대 반장) = 새 버전. 확정 뒤에는 /revise |
| POST | `/api/reports/shift/{shift_id}/confirm` | `SHIFT_REPORT·CONFIRM` | 확정 (RPT-03, 그 교대 반장만 — DB 트리거 R-36) → 잠김. 확정 요청 알림 자동 처리, 주간이면 야간 이월 다시 계산, |
| POST | `/api/reports/shift/{shift_id}/revise` | `SHIFT_REPORT·CONFIRM` | 확정 후 수정 (RPT-04, 그 교대 반장): 사유 필수 → 새 버전 + 관리자에게 문서 수정 알림 (FR-AST-03-06·07) |
| GET | `/api/reports/daily/{work_date}` | `DAILY_REPORT·VIEW` | 일일 보고서 (RPT-05, 조회 S·M·G): 하루 생산(목표 180 고정·실적·부족 = 180 − 실적), 손실, OEE, 오늘의 문제, 관리자 메모, 필수 정지 |
| PATCH | `/api/reports/daily/{work_date}` | `DAILY_REPORT·EDIT` | 일일 보고서 저장 = 새 버전 (RPT-05, MGR). 확정 뒤에는 /revise |
| POST | `/api/reports/daily/{work_date}/confirm` | `DAILY_REPORT·CONFIRM` | 일일 보고서 확정 (RPT-05, MGR) + 관리자 메모(memo, 선택). 잠정 칸(확정 안 된 교대 보고서)이 있으면 INVALID_STATE (R-72) |
| POST | `/api/reports/daily/{work_date}/revise` | `DAILY_REPORT·CONFIRM` | 일일 보고서 확정 후 수정 (MGR): 사유 필수 → 새 버전 |
| GET | `/api/documents` | `REVISION_HISTORY·VIEW` | 문서함 (DOC-01, SCR-18): 문서 6종 중 역할이 볼 수 있는 것만. mine = 내 할 일만 (할 일이 위로) |
| GET | `/api/documents/{doc_type}/{doc_key}/revisions` | `REVISION_HISTORY·VIEW` | 수정 이력 (DOC-02): 버전 목록·바뀐 칸 수·사유 (누가·언제·왜). OPR은 자기가 고친 것만 (OWN) |
| GET | `/api/documents/revisions/{revision_id}` | `REVISION_HISTORY·VIEW` | 버전 1개 + 바뀐 칸 (전/후). OPR(OWN)은 목록과 같은 규칙 — 자기가 고친 버전만 (번호로 직접 열어도) |
| GET | `/api/internal-docs` | `INTERNAL_DOC·VIEW` | 사내 문서 목록 (DOC-01~07 + 용어집). 원문 출처는 내보내지 않는다 (R-85) |
| GET | `/api/internal-docs/{doc_no}` | `INTERNAL_DOC·VIEW` | 사내 문서 1건 (Rev·승인 정보) |
| GET | `/api/internal-docs/{doc_no}/sections/{section}` | `INTERNAL_DOC·VIEW` | 출처 요약 카드·팝업 (DOCS-01, R-85): 문서 이름·번호·개정·절 제목 + 앞 2~3줄(card) 또는 그 절 본문(full). |
| POST | `/api/internal-docs/{doc_no}/revisions/{rev}/approve` | `INTERNAL_DOC·APPROVE` | 사내 문서 개정 승인 (DOCS-02, MGR, R-52): 새 현행판 + 문서 버전 + 관련 역할 전체에게 문서 수정 알림 |
| GET | `/api/assistant/tools` | 서비스 키 `assistant` | 이 사용자가 쓸 수 있는 도구의 JSON Schema (LLM 도구 정의에 그대로) |
| POST | `/api/assistant/tools/{name}` | 서비스 키 `assistant` | 조회 도구 실행 (읽기 전용). 대신 묻는 사용자의 권한으로 거르고 접근 기록에 남긴다 |
| POST | `/api/assistant/drafts/work-order` | 서비스 키 `assistant` | 작업지시서 AI비서 초안 (고정 서식 블록은 AI가 쓰지 않고 붙었다는 표시만, R-33). 겹치면 기존 것에 더함 (R-71) |
| POST | `/api/assistant/drafts/work-record` | 서비스 키 `assistant` | 정식 작업기록서 AI비서 초안 (v0 = AI). 확정은 보전 담당자 |
| PUT | `/api/assistant/notifications/{notification_id}/message` | 서비스 키 `assistant` | 알림 문장을 비서 문장으로 바꾸기 (알릴지·중요도는 못 바꿈, R-38) |
| POST | `/api/assistant/chat` | `ASSISTANT·INPUT` | 비서에게 질문 (API-AST-02 POST, FR-MNT-01, FR-AST-COM): chat_id·answer·sources[](사내 문서 이름·번호·개정·§만)· |
| GET | `/api/assistant/chat` | `ASSISTANT·INPUT` | 내 채팅 기록 (API-AST-02 GET, 이브 사이드바 채팅 기록 탭): 본인 것만, 30일 안 (질문 시각·질문·답·출처·상태) |
| GET | `/api/assistant/chat/{chat_id}` | `ASSISTANT·INPUT` | 채팅 기록 1건 (본인 것만 — 다른 사람 것은 없는 것처럼 404) |
| POST | `/api/ingest/alarms` | 서비스 키 `ingest` | 알람 1건 → 기록 + 등급별 알림 + 반복 알람 판정 |
| POST | `/api/ingest/alarms/{alarm_event_id}/clear` | 서비스 키 `ingest` | 알람 해제 시각 |
| POST | `/api/ingest/state` | 서비스 키 `ingest` | 설비 상태 바뀜 → 구간 닫고 열기 (같은 상태 다시 오면 그대로) |
| POST | `/api/ingest/production` | 서비스 키 `ingest` | 공정 실적 더하기 (OP-30이면 공구 사용 누적·수명 알림) |
| POST | `/api/ingest/wip` | 서비스 키 `ingest` | 재공 수량 (한도 넘김은 DB가 막음, R-13) |
| POST | `/api/ingest/sensors` | 서비스 키 `ingest` | 센서 값 여러 개 (최대 5000) |
| POST | `/api/ingest/bottleneck` | 서비스 키 `ingest` | 병목 공정 바뀜 |
| POST | `/api/ingest/orders` | 서비스 키 `ingest` | 작업지시 만들기 (시뮬레이터 계획) → PO-YYMM-NNN |
| POST | `/api/ingest/lots` | 서비스 키 `ingest` | 로트 투입 (OP-10 시작): 원자재 사용·검사 방식·작업지시 생산 중 (R-06a·R-08·R-28) |
| POST | `/api/ingest/lots/{lot_no}/arrived` | 서비스 키 `ingest` | 로트가 OP-50에 도착 → 검사 대기 |
| POST | `/api/ingest/cmm` | 서비스 키 `ingest` | CMM 결과 파일 내용 (공유 폴더 대신 API로 보낼 때) |
| POST | `/api/ingest/clock` | 서비스 키 `ingest` | 시연 시계를 시뮬레이터 시계에 맞춘다 (팀과 논의/비서_시뮬레이터_DB_연결_논의 3-1 "서비스 키로 부르는 시계 입구", 2026-10-20). |
| POST | `/api/ingest/sync` | 서비스 키 `ingest` | 시뮬레이터 10/1 기록을 표째로 DB에 맞춘다 (시연 서버 DB 중계, 2026-10-23 — app/services/sim_sync.py). |
| POST | `/api/ingest/reset` | 서비스 키 `ingest` | 시연 데이터 처음으로 (시연 서버 [처음으로]·켤 때, 2026-10-23): 운영 데이터를 시연 기준점으로 되돌리고 그 뒤 센서 값을 지운다 |
<!-- END:api -->

이 밖에 `GET /api/health` (DB 연결 확인, 권한 없음).

## 5. 비서 조회 도구 14개 (`app/assistant/tools.py`)

| 도구 | 입력 (굵게 = 필수) | 권한 | 내용 |
|---|---|---|---|
| `equipment_status` | equipment_id | LINE_VIEW | 설비 지금 상태·경과 분·열린 알람·잠금·가공 중 로트 |
| `alarms` | **from, to**, equipment_id, alarm_code (31일까지) | LINE_VIEW | 알람 횟수·처음·마지막·정지 분 |
| `kpi` | **from_date, to_date**, equipment_id, shift_type | KPI | 교대·설비별 가동률·성능·품질·OEE |
| `production` | **from_date, to_date** | PRODUCTION | 교대별 총 목표(목표 + 이월·잠정 여부)·실적·불량·예측·부족·손실(고장 + 속도), 하루 목표 180 |
| `lot` | **lot_no** | LOT_TRACE | 로트 상태·수량·추적 |
| `work_orders` | equipment_id, open_only | WORK_ORDER | 작업지시서 최근 20건 |
| `work_records` | equipment_id, alarm_code | WORK_RECORD | 확정된 작업기록 원인·조치 (지난 사례) |
| `pm_due` | **within_days** (0~31), equipment_id | PM_SCHEDULE | 기한 다가오는·넘긴 예방 정비 |
| `tool_life` | equipment_id | TOOL_LIFE | 공구 사용률·남은 부품 |
| `inventory` | item_no | INVENTORY | 재고·안전 재고·부족·최근 7일 출하 |
| `reliability` | equipment_id | KPI | 설비별 30일 MTTR(분)·MTBF(시간)·고장 횟수, MTTR 120분 초과 주의 (3D 카드에서 뺌) |
| `stop_reasons` | **from, to**, equipment_id (31일까지) | KPI | 정지 원인 순위 (설비·사유별 횟수·분·손실 추정, 계획 정지 제외) |
| `sensor_trend` | **equipment_id**, sensor_code, minutes (1~360, 기본 60) | LINE_VIEW | OP-30 센서 최소·평균·최대·마지막 값 + 정상 범위 [참고]. 알람 기준값 없음 (FR-PRD-01-14) |
| `equipment_spec` | equipment_id | LINE_VIEW | 모델·제어기·기준 사이클·외형 크기와 크기 근거 (3D 하단 패널에서 뺌) |

모르는 입력 칸, 형식이 틀린 값, 너무 넓은 기간은 422로 거절한다. 도구 입력 칸 = SQL 매개변수 (`tests/test_static_calls.py`가 확인).

## 6. API명세서_v1 ↔ 이 서버 (2026-10-08 — 주소를 명세서에 맞춤)

명세서 63개는 **명세서 주소 그대로**다. 아래는 API ID → 처리기 (`app/routers/파일.함수`)와 명세서보다 더한 것.

| API ID | 주소 | 처리기 | 비고 |
|---|---|---|---|
| AUTH-01~04 | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/me`, `POST /api/demo/role` | auth.login·logout·me·demo_role | 로그인은 비밀번호도 받음 [선택 필요: 기술 회의]. demo/role은 `{"role"}`(+ `user_id`) → 그 역할 토큰 |
| LINE-01·02 | `GET /api/line/layout`, `GET /api/line/twin` | line.layout·twin | twin = 설비·재공·병목·교대 진행(총 목표·예측·손실 합)·라인 OEE |
| LINE-03 | `GET /api/production/target` | production.target | 총 목표·이월(잠정)·예측·부족·위험·시간대별 실적·휴식 시각 |
| LINE-04 | `GET /api/kpi?scope=line\|equipment` | production.kpi | 주의 표시(OEE 59%·가동률 60% — OP-30), `reliability` = MTTR·MTBF 30일 |
| LINE-05 | `GET /api/production/orders` | production.orders | 목표·완료·불량·로트·지금 공정·지연 |
| LINE-06 | `GET /api/replay` | line.replay | `equipment_id`를 주면 센서 (6시간까지) |
| LINE-07·08 | `GET /api/downtimes`, `PATCH /api/downtimes/{id}` | alarms.downtimes·downtime_patch | `{"reason_code"}` 입력(O·M) / `{"confirm":true}` 확정(S). SCR-14 필요 여부 판단 중 |
| NTF-01~04 | `GET /api/notifications`, `POST …/{id}/read·resolve·ack` | notifications.mine·read·resolve·ack | 목록 = `{"counts","items"}`, resolve 반복 알람은 `action_plan` 필수, ack = 소리 끔 |
| STR-01 | `GET /api/stream/events` | stream.stream | 사건 이름은 1장 |
| AST-01·02 | `GET /api/assistant/briefing`, `POST /api/assistant/chat` | notifications.briefing, assistant.chat | chat은 AI 비서 서비스로 넘김. 브리핑 "먼저 챙길 일" 체크 저장(2026-10-20)은 `GET·POST /api/assistant/briefing/checks` (notifications.briefing_checks, briefing_check) |
| DOCS-01·02 | `GET /api/internal-docs/{doc_no}/sections/{section}`, `POST …/revisions/{rev}/approve` | documents.internal_doc_section·approve | 절 내용 = 현행판 문서 조각(doc_chunk). 승인하면 전원에게 문서 수정 알림 |
| MNT-01 | `GET /api/maint/guide-card/{alarm_event_id}` | alarms.guide_card | |
| MNT-02~08 | `/api/maint/work-orders…` (`assign {"mnt_user_id"}`, `approve {"version"}`, `start`, `cancel {"reason"}`) | maintenance.wo_* | `GET ?mine=true` = 내 담당 |
| MNT-09~11 | `GET·PATCH /api/maint/work-records/{id}`, `…/assist`, `…/confirm {"version"}` | maintenance.wr_get·wr_edit·wr_assist·wr_confirm | PATCH = 고친 칸 + `checks[]` + `parts[]` 한 번에. assist = AI 비서 서비스 |
| MNT-12 | `POST /api/maint/quick-records`, `…/{id}/confirm` | maintenance.quick_create·quick_confirm | 체크 9칸은 work-records PATCH |
| PM-01·02 | `GET /api/maint/pm-schedule`, `POST /api/maint/pm-records` | maintenance.pm_schedule·pm_record_create | 제때 실시율 `on_time` (기본 최근 30일) |
| RPT-01~04 | `GET·PATCH /api/reports/shift/{id}`, `…/confirm`, `…/revise` | documents.shift_report* | PATCH는 확정 전만, 확정 뒤는 revise |
| RPT-05 | `GET·PATCH /api/reports/daily/{date}`, `…/confirm` | documents.daily_report* | **계속 만든다** (2026-10-08). 잠정 칸이 있으면 확정 불가. `…/revise` 더함 |
| DOC-01·02 | `GET /api/documents`, `GET /api/documents/{type}/{id}/revisions` | documents.inbox·revisions | `?mine=true` = 내 할 일 |
| LOT-01~03 | `GET /api/lots`·`/{no}/trace`, `POST /api/lots/{no}/hold·release·scrap·scrap/approve` | production.* | 해제·폐기는 로트 번호로 (열린 보류를 서버가 찾음) |
| QLT-01~05 | `GET·POST /api/inspection/results`, `…/{id}/select`, `GET /api/inspection/cmm-imports`, `GET /api/quality/summary` | quality.* | POST는 게이지·외관(judgement) 또는 수동 입력(measured_value) |
| INV-01~05 | `GET /api/inventory`, `POST /api/inventory/txns`, `POST /api/raw-lots/{no}/inspect`, `GET·POST /api/shipments`·`PATCH /{no}`, `PATCH /api/inventory/items/{no}/safety-stock` | inventory.* | 출하 등록은 `lines`·`confirm`까지 한 번에 |
| TOOL-01·02 | `GET /api/tools`, `POST /api/tools/{id}/change` | inventory.tools·tool_change | |
| SET-01~03 | `GET·PATCH /api/settings/notification-rules·targets·users` | notifications.rules·rule_update, master.targets*·users* | PATCH 본문에 `rule_code`·`user_id`. 목표는 아직 시작 안 한 교대·근무일만 |
| SIM-01·02 | `POST /api/sim/inject`, `POST /api/sim/clock` | master.inject·set_sim_clock | inject는 `scenario_code`(S1~S6) 필수 |
| SIM-03 | `POST /api/sim/reset` | master.sim_reset | 시연 모드만. 시연 기준점으로 되돌리고 시연 시계를 그 시각에 멈춤 (설정·계정·접속 기록은 그대로). 기준점은 목업·생성기 적재 뒤 자동, 바꾸기는 `POST /api/sim/snapshot`(MGR) |

**명세서보다 더한 것 (명세서 주소 체계 안에 둠):** `GET /api/alarms`·`/{id}`, `GET /api/kpi/stops`, `GET /api/lots/{no}`·`POST …/judge`, `GET /api/holds`, `POST /api/maint/work-orders`·`/work-records`(만들기)·`…/checks/{seq}`·`…/parts`·`…/check`, `GET·PATCH /api/maint/pm-records/{id}`·`…/confirm`, `POST /api/reports/daily/{date}/revise`, `GET /api/documents/revisions/{id}`, `GET /api/internal-docs`·`/{doc_no}`, `GET·POST /api/inspection/instructions`·`…/start`, `POST /api/inspection/cmm-imports`(올리기), `GET /api/quality/cpk`·`/defects`, `GET /api/inventory/{no}/txns`, `POST /api/raw-lots`(원자재 입고), `GET /api/shipments/candidates`·`/{no}`, `PUT·DELETE /api/shipments/{no}/lines/{lot}`, `POST /api/shipments/{no}/confirm`, `GET /api/tools/{id}/changes`, `GET /api/codes`·`/dataset`·`/sim/clock`·`/admin/retention`, `POST /api/sim/snapshot`. 서버끼리: `/api/ingest/*`, `/api/assistant/tools·drafts·notifications/*` (서비스 키).

**명세서와 다른 점:** 없음 (63개 모두). 명세서 밖으로 더한 것은 위 목록, 오류는 예상 못 한 서버 오류에만 500 `INTERNAL_ERROR`.

## 7. 화면 → 백엔드 전환 (C2, 2026-10-23) — 화면 한 번에 읽기·시뮬레이터 연결

화면(`frontend/src/shell/backendApi.ts`, 스위치 `NEXT_PUBLIC_MOM_BACKEND=1`)이 시연 서버 대신 이 서버만 부를 때 쓰는 것. 기존 응답 모양은 바꾸지 않고 칸·주소를 더했다. 권한은 각 화면의 상세 조회와 같다 (`tests/test_role_matrix.py`).

| 주소 | 하는 일 | 권한 |
|---|---|---|
| `GET /api/line/twin?full=true` | 트윈 + 시간대별 실적·설비별 지표·MTTR·작업지시·공구·실시간 구간 알람·지금 센서·설비별 멈춘 분/고장 손실·지금 사유·오늘 완제품·마지막 측정 24개·의심 로트·병목 기록·`live_from`·시뮬레이터 시계(`sim`) | LINE·FIELD 보기 |
| `GET /api/replay` (칸 더함) | `alarms`(알람 전체 칸), `bottleneck`(원인·앞 공정, 구간 앞 1줄 포함), `done`(OP-50 실적 줄 끝 시각·합격 수), 상태 줄에 `reason_suggested_code`·`alarm_event_id` | LINE 보기 |
| `GET /api/reports/shift`, `GET /api/reports/daily` | 보고서 목록 (상태·버전, 교대는 시각·반장) | 각 보고서 보기 |
| `GET /api/reports/shift/{id}` (칸 더함) | `start_at`·`end_at` | 그대로 |
| `GET /api/documents/revisions?limit=` | 모든 문서의 최근 버전 + 바뀐 칸(`changes{번호: […]}`), 볼 수 있는 문서만, OPR은 자기 것 | 수정 이력 보기 |
| `GET /api/internal-docs/{doc}?sections=true` | 현행판 문서 조각(`doc_chunk`)을 절 목록 `{section, title, level, text}`로 | 사내 문서 보기 |
| `GET /api/maint/history` | 실시간 구간 앞(시연: 9월) 작업지시서·단계·작업기록서·점검·부품·알람 | 지침카드 보기 |
| `GET /api/maint/pm-schedule` (칸 더함) | `today_records`(오늘·초안 실시 기록), `open_windows`(지금 열린 정비 구간) | 그대로 |
| `GET /api/lots/screen?lot=` | 모든 로트(검사 방식·판정·게이지 합불·공정별 완료 수·마지막 보류·출하 내역) + 고른 로트의 실적 줄·알람 + 실시간 구간 앞 보류 + 원자재 로트 | 생산 보기 |
| `GET /api/inventory/screen` | 13품목 + 실시간 구간 시작 때 재고(`stock_at_start`) + 실시간 거래 전부·그 앞 거래 | 재고 보기 |
| `GET /api/tools/changes` | 공구 교체 — 실시간 구간(`changes_today`)·그 앞(`past_changes`) | 공구 보기 |
| `GET /api/shipments?lines=true` | 출하마다 로트 줄까지 | 출하 보기 |
| `GET /api/inspection/cmm-imports?limit=` | 최대 5000 (500 → 5000) | 그대로 |

**시뮬레이터 연결 (`MOM_SIM_URL`이 있을 때만, `app/services/sim_link.py`).** 시뮬레이터가 주인인 일은 이 서버가 로그인·권한을 확인한 뒤 시뮬레이터에 넘기고, 기록은 DB 중계(`/api/ingest/sync`)로 들어온다 — 같은 표에 둘이 쓰지 않게.

| 주소 | 시뮬레이터가 이어져 있을 때 | 권한 |
|---|---|---|
| `GET·POST /api/sim/clock`, `POST /api/sim/inject`, `POST /api/sim/reset` | 시뮬레이터 시계·사건 버튼·처음으로로 넘김 (inject는 `scenario_code`만). reset은 시뮬레이터만 — DB는 중계가 되돌림 | 로그인 |
| `POST /api/sim/fire` `{kind: warn·stop·air·maint}` | 알림 미리보기 [상황 일으키기] | 로그인 |
| `POST /api/sim/work-record-confirmed` `{equipment_id}` | 작업기록서 확정 뒤 고장 설비 복귀 | 작업기록서·간이 기록 확정 |
| `POST /api/sim/pm-start`·`/api/sim/pm-end` | [정비 시작]·[정비 끝] | 예방 정비 기록 만들기 (MNT) |
| `POST /api/lots/{lot}/hold`·`/release` | 시뮬레이터가 보류·해제 (`via: simulator`) | 그대로 (SUP·MGR) |
| `POST /api/tools/{id}/change` | 시뮬레이터가 교체 (`via: simulator`) | 그대로 (OPR·MNT) |

시뮬레이터에 연결하지 못하면 503 `INVALID_STATE` "시뮬레이터(시연 서버)에 연결하지 못함". 시뮬레이터가 거절하면 그 상태·코드·문장 그대로.
