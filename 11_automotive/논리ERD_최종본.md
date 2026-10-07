# AI 운영 비서 기반 자동차 부품 절삭가공 라인 운영 관리 플랫폼 — 논리 ERD

| 항목 | 내용 |
|---|---|
| 문서명 | 논리 ERD (논리 데이터 모델) |
| 문서 버전 | **최종본** (2026-10-07, 2026-10-06 문서 검토 회의 반영) |
| 날짜 | 처음 작성 2026-10-05 (v1) → 최종본 2026-10-07 |
| 상태 | **최종본 — 물리 ERD는 기술 선택 뒤 [선택 필요: 기술 회의]** (비서 LLM은 로컬 LLM으로 확정, 나머지 기술은 팀 선택) |
| 근거 문서 | [가상데이터설계서_최종본.md](가상데이터설계서_최종본.md) 5장·9장, [기획서_최종본.md](기획서_최종본.md) 4.3·4.4·4.5·5장·12.4·13장·19장, [요구사항정의서_최종본.md](요구사항정의서_최종본.md), [UI설계서_최종본.md](UI설계서_최종본.md), [가상사내문서/](가상사내문서/) DOC-01~07 (Rev.1), [00_용어집.md](가상사내문서/00_용어집.md) |
| 최종본 조사 근거 | R1 `docs/line/3D_설비규격/3D_설비규격_조사.md` (설비 크기·공장 배치), R2 `docs/background/데이터보관/데이터보관기간_조사.md` (보관 기간), R3 `docs/quality/CMM_자동입력/CMM_자동입력_조사.md` (CMM 자동 입력), R4 `docs/production/운영기준_근거/병목조치_반복알람_우선순위_조사.md` (반복 알람 2단계·보고 순위·필수 정지), R5 `docs/production/운영기준_근거/완제품_재고담당_현장화면_조사.md` (완제품·출하·재고 담당·06:00) |
| 다음 문서 | 물리 ERD, API 명세서, AI 비서 설계 (기획서 18장 7·8·9번) |
| 엔터티 수 | **58개** (8개 주제 영역) |
| 코드 목록·관계·규칙 | 코드 목록 **54개** (6.1~6.54), 관계 **124개** (1~124), 규칙 **R-01~R-87** |

> 이 문서는 **논리 모델만** 다룬다: 엔터티, 속성, 키(PK/FK), 관계, 카디널리티, 필수 여부, 값의 뜻, 코드 목록. DB 제품·물리 자료형·인덱스·파티션은 정하지 않는다 → **물리 ERD에서 [선택 필요: 기술 회의]**.
> 기획서 12.4와 설계서 5장의 이름이 다르면 **설계서 5장 이름**을 쓰고 10장 대응표에 적는다. 최종본에서 더한 엔터티·속성 이름은 **2026-10-07 변경 명세 4장 이름**(모든 문서 공통)을 쓴다.
> 운영 데이터는 **JSON 파일이 아니라 DB**에 저장한다. JSON은 설정 파일(라인 구성·알림 기준값·교대 시간), 비서 ↔ 프로그램이 주고받는 형식, 시뮬레이터 사건 넣기에만 쓴다 (2026-10-06 회의 D-18).

---

## 목차

1. [목적과 범위](#1-목적과-범위)
2. [표기법](#2-표기법)
3. [주제 영역 묶음표](#3-주제-영역-묶음표)
4. [ERD 그림](#4-erd-그림)
5. [엔터티 정의서](#5-엔터티-정의서)
6. [코드 목록](#6-코드-목록)
7. [관계 정의표](#7-관계-정의표)
8. [무결성·업무 규칙](#8-무결성업무-규칙)
9. [요구사항 ↔ 엔터티 추적표](#9-요구사항--엔터티-추적표)
10. [기획서 12.4 ↔ 이 문서 이름 대응표](#10-기획서-124--이-문서-이름-대응표)
11. [물리 ERD로 넘기는 것](#11-물리-erd로-넘기는-것)
12. [개정 기록](#12-개정-기록)

---

## 1. 목적과 범위

### 1.1 목적

| 항목 | 내용 |
|---|---|
| 왜 만드나 | 요구사항 정의서의 요구사항을 **어떤 데이터로 지키는지** 정한다. 물리 ERD·API 명세서·가상 데이터 생성기가 이 문서의 엔터티 이름과 규칙을 같이 쓴다 |
| 누가 보나 | 백엔드·DB 담당 (물리 ERD), 데이터·ML 담당 (생성기), AI 비서 담당 (조회 도구), 프론트엔드 (화면 칸), 심사위원 |
| 무엇을 담나 | 58개 엔터티의 속성·키·관계, 코드 목록, 무결성 규칙 (설계서 9장 점검 기준 + 문서 흐름 규칙), 데이터 종류별 보관 기간(논리 분류), 요구사항 추적 |

### 1.2 논리 모델과 물리 모델의 구분

| 구분 | 논리 ERD (이 문서) | 물리 ERD (다음 문서) |
|---|---|---|
| 이름 | 엔터티·속성 이름 (영어 snake_case + 한국어 이름) | 테이블·칼럼 이름 (보통 같게 씀) |
| 형식 | 쉬운 말: 문자, 긴 문자, 정수, 소수, 날짜, 날짜시각, 참·거짓, 코드 | DB 자료형 (예: 문자 길이, 소수 자리), 시간대 |
| 키 | PK, FK, UK(겹치면 안 되는 묶음) | 기본 키 생성 방식 (일련번호 등), 외래 키 제약 이름 |
| 관계 | 1:1, 1:N, 선택·필수 | 삭제·변경 때 동작 (함께 지움 등) |
| 성능 | 다루지 않음 | 인덱스, 파티션 (예: 1초 간격 센서 값) |
| 보관 기간 | 데이터 종류별 **보관 기간과 지난 뒤 처리**(삭제 / 집계로 줄임 / 보관 저장소 이동)를 정함 (6.53, R-75, NFR-DATA-13) | 실제 삭제·집계·이동 방식 **[선택 필요: 기술 회의]** |
| 계산 값 | "계산" 표시만 (저장할지 안 할지는 정하지 않음) | 저장 칼럼 / 뷰 / 화면 계산 중 선택 |
| DB 제품 | 정하지 않음 | **[선택 필요: 기술 회의]** (기획서 12.2 [제안] — 팀 선택) |

### 1.3 범위

| 포함 | 제외 (까닭) |
|---|---|
| BRK-A100 라인 5개 공정 6대 설비의 운영 데이터 (설계서 5장 전체) | 구매·발주, ERP 연동 (기획서 8.1) |
| 문서 흐름: 작업지시서 → 작업기록서 → 교대 보고서 → 일일 보고서, 수정 이력 (기획서 5장, 4.5) | 지침카드·교대 시작 브리핑의 **저장** — 둘 다 화면이고 확정하지 않는다 (기획서 5.1, FR-AST-01-01). 화면은 다른 엔터티를 모아 만든다 |
| 알림·권한·사용자 (기획서 4.3, 13장) | 설비로 보내는 명령 (FR-AST-COM-11, NFR-SAFE-01) — 데이터는 설비 → 플랫폼 한 방향 |
| AI 비서 문서 검색 저장소 (사내 문서 조각) — **엔터티 이름과 칸만**. 검색 대상은 사내 문서 DOC-01~07 + 용어집 (원문은 검색하지 않음) | 문서 나누기 방식, 임베딩 모델·차원, 검색 방식 → **AI 비서 설계에서 [선택 필요: 기술 회의]**. 비서 LLM은 **로컬 LLM으로 확정**, 모델·컴퓨터 사양·실행 도구는 [선택 필요: 기술 회의] |
| 다시 보기(PRD-06) — 새 엔터티 없이 기존 기록을 다시 그림 (설계서 5.19, FR-PRD-06-05) | 다시 보기 전용 테이블 (FR-PRD-06-05 "다시 보기만을 위한 테이블이 없다") |
| 3D 라인 뷰 배치: 공장 크기, 설비·배치 물체의 **실제 치수와 좌표**, 설비 주요 부품 도형(상자·원기둥) (FR-PRD-01-27, R1) | 사실적인 3D 모델·질감 (기획서 8.1 유지 — 크기만 실제), 3D 엔진의 좌표 변환 ([선택 필요: 기술 회의]) |
| 완제품(BRK-A100) 재고와 **출하 기록** (FR-INV-01-11·12, R5) | 주문 접수, ERP 연동 (FR-INV-01-10), 차량번호·운전자·송장·포장·라벨 (물류) |
| OP-50 측정 결과 **파일 가져오기 기록**과 측정값 자동 입력 칸 (FR-QLT-01-14~22, R3) | 측정기 쪽 측정 프로그램, 공유 폴더 위치·파일 감시 방식 ([선택 필요: 기술 회의]) |
| — | AI 비서 질문·답 기록 — **저장하지 않음** (R2 #18, MNT-01) |
| — | 공구 수명 예측 모델의 학습 데이터 (실제 VF-1 실험 CSV, 설계서 5.13) — 운영 DB 밖 |

---

## 2. 표기법

### 2.1 표시 규칙 (CLAUDE.md)

| 표시 | 뜻 |
|---|---|
| **[실제]** | 공개 문서·데이터 그대로 |
| **[가상]** | 팀이 정한 값 |
| **[참고]** | 다른 회사·산업 값의 모양만 빌림 |
| **[제안]** | 이 문서가 처음 제안하는 것 (팀 확정 전) |
| **[선택 필요]** | 아직 정하지 않음. 뒤에 정할 곳을 적는다 |

- 숫자는 설계서·기획서·DOC에 있는 값만 쓴다. 근거 없는 숫자는 만들지 않는다.
- 엔터티 정의서의 "출처" 칸은 절까지 적는다. 예: "설계서 5.5", "DOC-07 2.2", "[제안]".

### 2.2 이름 규칙

| 대상 | 규칙 | 예 |
|---|---|---|
| 엔터티 | 영어 **snake_case 단수형** + 한국어 이름 | `production_lot` 생산 로트 |
| 속성 | 영어 snake_case. 수량은 `_qty`, 분은 `_min`, 시각은 `_at`, 날짜는 `_date`, 비율은 `_pct`, 참·거짓은 `is_` / `has_` | `input_qty`, `repair_min`, `occurred_at` |
| 외래 키 | 가리키는 엔터티의 키 이름을 그대로 쓴다. 같은 엔터티를 두 번 가리키면 앞에 뜻을 붙인다 | `prev_process_code`, `new_process_code` |
| 사용자를 가리키는 칸 | `~_by` (누가) + `~_at` (언제) 짝 | `confirmed_by`, `confirmed_at` |
| 코드 값 | 6장의 코드. 영어 대문자 코드는 [제안], 한국어 이름은 출처 문서 그대로 | `STOP` = 정지 (DOC-02 2장) |
| 업무 번호 | 출처 문서의 번호 형식을 그대로 키로 쓴다 | `PO-2609-001`, `LOT-2609-041-1`, `MAT-2609-01`, `MW-0901`, `MR-0901`, `MR-S-0901`, `SHP-2609-001` (출하, R5 [가상]) |
| 길이·좌표 | mm, 이름 끝에 `_mm` | `size_x_mm`, `center_x_mm` |

### 2.3 키 표시

| 표시 | 뜻 |
|---|---|
| **PK** | 기본 키. 한 줄을 하나로 정한다. 둘 이상 칸이면 묶어서 PK |
| **FK** | 외래 키. 다른 엔터티의 PK를 가리킨다 |
| **UK** | 겹치면 안 되는 칸 (또는 묶음). PK는 아니지만 업무상 하나여야 함 |
| **PK, FK** | 기본 키이면서 외래 키 (부모에 딸린 엔터티) |

### 2.4 논리 형식

| 논리 형식 | 뜻 | mermaid 그림의 형식 이름 |
|---|---|---|
| 문자 | 짧은 글자 (이름, 번호) | `text` |
| 긴 문자 | 문장·문단 (원인, 메모, 원문 설명) | `longtext` |
| 정수 | 개수 (수량, 순번) | `int` |
| 소수 | 측정값, 분, 비율 | `decimal` |
| 날짜 | 날짜만 | `date` |
| 날짜시각 | 날짜 + 시각 | `datetime` |
| 참·거짓 | 예 / 아니오 | `bool` |
| 코드 | 6장 코드 목록 중 하나 | `code` |

- mermaid 그림은 영어 형식 이름만 받으므로 위 표처럼 바꿔 적는다. 물리 자료형이 아니다.
- **계산** 표시가 있는 속성은 다른 기록에서 계산되는 값이다. 저장할지 화면에서 계산할지는 물리 ERD에서 정한다.

### 2.5 카디널리티 기호 (mermaid erDiagram)

| 기호 | 뜻 | 예 |
|---|---|---|
| `\|\|--\|\|` | 1 : 정확히 1 | 생산 로트 1 : 검사 방식 1 |
| `\|\|--o\|` | 1 : 0 또는 1 | 교대 1 : 교대 보고서 0..1 |
| `\|\|--o{` | 1 : 0 이상 | 설비 1 : 알람 이벤트 0..N |
| `\|\|--\|{` | 1 : 1 이상 | 작업지시 1 : 생산 로트 1..N |
| `\|o--o{` | 0 또는 1 : 0 이상 (자식의 FK가 비어도 됨) | 정지 사유 0..1 : 상태 구간 0..N |
| `\|o--o\|` | 0 또는 1 : 0 또는 1 | 알람 이벤트 0..1 : 작업지시서 0..1 |

- 왼쪽이 부모(PK 쪽), 오른쪽이 자식(FK 쪽)이다. 7장 표의 카디널리티도 "부모 : 자식"으로 적는다.

### 2.6 필수 표시

| 표시 | 뜻 |
|---|---|
| ○ | 늘 값이 있어야 함 |
| — | 비어도 됨 |
| 조건 | 조건에 따라 필수 (값·규칙 칸에 조건을 적음) |

---

## 3. 주제 영역 묶음표

| # | 영역 | 엔터티 (한국어 이름) | 수 | 주로 쓰는 기능 |
|---|---|---|---|---|
| A | **기준 정보** | `process` 공정, `equipment` 설비, `isolation_point` 차단 지점, `product` 제품, `work_day` 근무일, `shift` 교대, `wip_buffer` 재공 위치, **`plant_layout` 공장 배치**, **`layout_object` 배치 물체**, **`equipment_part_shape` 설비 부품 도형** | 10 | 전체, PRD-01 (3D 라인 뷰·현장 보기) |
| B | **생산** | `raw_material_lot` 원자재 로트, `production_order` 생산 작업지시, `production_lot` 생산 로트, `operation_report` 공정 실적, `wip_log` 재공 기록, `bottleneck_log` 병목 기록, `lot_hold` 로트 보류 기록 | 7 | PRD-01·02·03·04·05 |
| C | **설비·알람** | `alarm_master` 알람 코드집, `alarm_guide_map` 알람-고장 대응 연결, `alarm_event` 알람 이벤트, `equipment_state_log` 설비 상태 기록, `downtime_reason` 정지 사유 코드, `sensor_item` 센서 항목, `sensor_sample` 센서 값 | 7 | PRD-01·06, MNT-01·02, AST-02 |
| D | **정비** | `maintenance_work_order` 정비 작업지시서, `work_order_step` 작업지시서 작업 순서, `work_order_part` 작업지시서 예상 부품, `work_record` 작업기록서, `work_record_check` 작업기록서 체크, `work_record_part` 작업기록서 사용 부품, `pm_task` 예방 정비 항목, `pm_record` 예방 정비 실시 기록 | 8 | MNT-03·04·05 |
| E | **공구·재고** (출하 포함) | `tool_type` 공구 종류, `tool` 공구, `tool_usage` 공구 사용 기록, `tool_change` 공구 교체 기록, `inventory_item` 재고 품목, `inventory_txn` 입출고 거래, **`shipment` 출하**, **`shipment_line` 출하 내역** | 8 | ML-01, INV-01, PRD-05 (출하까지 추적) |
| F | **품질** | `inspection_item` 검사 항목, `defect_code` 불량 코드, `inspection_plan` 검사 방식, `inspection_result` 검사 결과, `defect_record` 불량 기록, **`cmm_import` 측정 결과 파일 가져오기** | 6 | QLT-01, PRD-05 |
| G | **문서·AI 비서** | `shift_report` 교대 보고서, `daily_report` 일일 보고서, `document_revision` 문서 버전, `document_revision_change` 버전 변경 칸, `internal_doc` 사내 문서, `doc_chunk` 사내 문서 조각 | 6 | PRD-02·04, AST-03, MNT-01 |
| H | **사용자·권한·알림** | `app_user` 사용자, `role` 역할, `role_permission` 역할별 권한, `notification` 알림, `notification_recipient` 알림 받는 사람, `notification_rule` 알림 규칙 | 6 | AST-01·02·03, 권한 |
| | **합계** | | **58** | |

- 굵은 글씨 6개는 **최종본에서 더한 엔터티**다 (2026-10-06 회의 D-02·D-14·D-17, 변경 명세 4장). v1의 52개는 이름·번호를 바꾸지 않았다.

---

## 4. ERD 그림

### 4.0 전체 ERD (엔터티와 관계만)

- 그림을 읽기 쉽게 하려고 **`app_user`와의 관계(작성자·확정자·승인자 등 `~_by` 칸)와 `notification`의 선택 연결**은 뺐다. 모두 7장 관계 정의표에 있다.
- `document_revision`은 일곱 종류 문서(최종본에서 출하 기록 추가) 중 **하나만** 가리킨다 (8장 R-35).
- 최종본에서 더한 관계(7장 107~124)는 그림 맨 아래에 모아 두었다.

```mermaid
erDiagram
    process ||--|{ equipment : "속한 설비"
    process ||--o| wip_buffer : "앞 공정"
    process ||--o| wip_buffer : "뒤 공정"
    equipment ||--|{ isolation_point : "차단 지점"
    work_day ||--o{ shift : "교대"
    product ||--o{ production_order : "제품"
    product ||--|{ inspection_item : "검사 항목"
    inventory_item ||--o{ product : "원자재 품목"
    inventory_item ||--o{ raw_material_lot : "원자재 품목"
    production_order ||--o{ production_lot : "로트로 나눔"
    raw_material_lot ||--o{ production_lot : "투입 원자재"
    shift ||--o{ production_lot : "투입 교대"
    production_lot ||--o{ operation_report : "공정 실적"
    process ||--o{ operation_report : "공정"
    equipment ||--o{ operation_report : "설비"
    shift ||--o{ operation_report : "처리 교대"
    wip_buffer ||--o{ wip_log : "재공 기록"
    process ||--o{ bottleneck_log : "새 병목"
    process |o--o{ bottleneck_log : "이전 병목"
    alarm_event |o--o{ bottleneck_log : "고장 원인"
    production_lot ||--o{ lot_hold : "보류"
    alarm_event |o--o{ lot_hold : "보류 계기 알람"
    tool |o--o{ lot_hold : "보류 계기 공구"
    process ||--o{ alarm_master : "적용 공정"
    alarm_master ||--o{ alarm_guide_map : "고장 대응 절"
    internal_doc ||--o{ alarm_guide_map : "DOC-03"
    alarm_master ||--o{ alarm_event : "알람 번호"
    equipment ||--o{ alarm_event : "발생 설비"
    production_lot |o--o{ alarm_event : "가공 중 로트"
    alarm_event |o--o{ alarm_event : "선행 알람"
    equipment ||--o{ equipment_state_log : "상태 구간"
    downtime_reason |o--o{ equipment_state_log : "정지 사유"
    alarm_event |o--o| equipment_state_log : "멈춘 구간"
    pm_record |o--o| equipment_state_log : "정비 구간"
    alarm_master |o--o{ sensor_item : "연결 알람"
    sensor_item ||--o{ sensor_sample : "센서"
    equipment ||--o{ sensor_sample : "OP-30 설비"
    alarm_event |o--o| maintenance_work_order : "작업지시서"
    pm_record |o--o| maintenance_work_order : "정비 중 이상"
    equipment ||--o{ maintenance_work_order : "설비"
    production_lot |o--o{ maintenance_work_order : "로트"
    maintenance_work_order ||--|{ work_order_step : "작업 순서"
    maintenance_work_order ||--o{ work_order_part : "예상 부품"
    inventory_item ||--o{ work_order_part : "품목"
    maintenance_work_order |o--o| work_record : "작업기록서"
    alarm_event |o--o| work_record : "간이 작업기록"
    equipment ||--o{ work_record : "설비"
    production_lot |o--o{ work_record : "로트"
    work_record ||--o{ work_record_check : "체크"
    work_order_step |o--o{ work_record_check : "수행 단계"
    work_record ||--o{ work_record_part : "사용 부품"
    inventory_item ||--o{ work_record_part : "품목"
    equipment ||--o{ pm_task : "정비 항목"
    inventory_item |o--o{ pm_task : "기본 소모품"
    pm_task ||--o{ pm_record : "실시 기록"
    inventory_item ||--o| tool_type : "공구 품목"
    tool_type ||--o{ tool : "종류"
    equipment ||--o{ tool : "꽂힌 설비"
    tool ||--o{ tool_usage : "사용"
    operation_report ||--o{ tool_usage : "가공 실적"
    tool ||--o{ tool_change : "교체"
    alarm_event |o--o{ tool_change : "교체 계기 알람"
    inventory_item ||--o{ inventory_txn : "거래"
    work_record_part |o--o| inventory_txn : "부품 사용"
    pm_record |o--o{ inventory_txn : "소모품 사용"
    tool_change |o--o| inventory_txn : "공구 차감"
    production_lot |o--o| inventory_txn : "원자재 투입"
    raw_material_lot |o--o| inventory_txn : "원자재 입고"
    production_lot ||--|| inspection_plan : "검사 방식"
    lot_hold |o--o{ inspection_plan : "강화 사유"
    production_lot ||--o{ inspection_result : "측정값"
    inspection_item ||--o{ inspection_result : "항목"
    equipment ||--o{ inspection_result : "측정기"
    production_lot ||--o{ defect_record : "불량"
    defect_code ||--o{ defect_record : "불량 코드"
    process ||--o{ defect_record : "발견 공정"
    inspection_result |o--o| defect_record : "불합격 측정"
    shift ||--o| shift_report : "교대 보고서"
    work_day ||--o| daily_report : "일일 보고서"
    maintenance_work_order ||--|{ document_revision : "버전"
    work_record ||--|{ document_revision : "버전"
    shift_report ||--|{ document_revision : "버전"
    daily_report ||--|{ document_revision : "버전"
    internal_doc ||--|{ document_revision : "버전"
    pm_record ||--|{ document_revision : "버전"
    document_revision ||--o{ document_revision_change : "바뀐 칸"
    internal_doc ||--o{ doc_chunk : "문서 조각"
    role ||--o{ app_user : "역할"
    role ||--o{ role_permission : "권한"
    notification_rule ||--o{ notification : "규칙"
    notification ||--|{ notification_recipient : "받는 사람"
    app_user ||--o{ notification_recipient : "사용자"
    plant_layout ||--o{ layout_object : "배치 물체"
    wip_buffer |o--o| layout_object : "재공 자리"
    equipment ||--o{ equipment_part_shape : "부품 도형"
    shipment ||--|{ shipment_line : "로트 줄"
    production_lot ||--o{ shipment_line : "출하한 로트"
    shipment_line |o--o| inventory_txn : "출하 출고"
    production_lot |o--o{ inventory_txn : "완제품 거래"
    role ||--o{ inventory_item : "관리 역할"
    equipment ||--o{ cmm_import : "측정기"
    production_lot |o--o{ cmm_import : "결과 파일 로트"
    cmm_import |o--o{ inspection_result : "자동 입력"
    cmm_import |o--o{ notification : "결과 파일 알림"
    notification |o--o{ notification : "앞 단계 알림"
    notification |o--o| maintenance_work_order : "원인 점검 작업지시서"
    notification |o--o| work_record : "원인 점검 간이 기록"
    shipment ||--|{ document_revision : "버전"
```

### 4.1 A 기준 정보

```mermaid
erDiagram
    process {
        code process_code PK "OP-10~OP-50"
        text process_name "절단, 황삭, 정밀 가공, 세척·디버링, 측정"
        int seq UK "공정 순서 1~5"
        bool is_base_bottleneck "기준 병목, OP-30만 참"
    }
    equipment {
        text equipment_id PK "SAW-01 등 6대"
        code process_code FK "공정"
        text model "Haas VF-2 등"
        text controller "Haas NGC, Siemens 840D sl 등"
        decimal std_cycle_min "기준 사이클 시간 분/개"
        int batch_qty "묶음 수량, WSH-01만 30"
        decimal batch_time_min "묶음 시간, WSH-01만 25분"
        bool has_sensor "센서 기록, OP-30만 참"
        int size_x_mm "외형 가로 X"
        int size_y_mm "외형 세로 Y"
        int size_z_mm "외형 높이 Z"
        int center_x_mm "배치 가운데 X"
        int center_y_mm "배치 가운데 Y"
        code facing "정면 방향, 모두 남쪽"
        code size_source_tag "크기 근거 실제, 참고, 가상"
        text ref_model "참고 모델, 예 Hexagon TIGO SF"
    }
    isolation_point {
        text isolation_point_id PK "VF2-01-E1 등"
        text equipment_id FK "설비"
        text point_name "VF2-01 주 차단기 등"
        code energy_type "전기, 전기 공급원, 공압"
        text location "위치"
        text lock_method "잠금 방법"
        int seq "차단 순서"
    }
    product {
        text product_code PK "BRK-A100"
        text product_name "엔진 마운트 브래킷"
        text material "알루미늄 6061-T6"
        decimal line_base_cycle_min "라인 기준 속도 3.5분/개"
        text material_item_no FK "원자재 품목 RM-6061"
    }
    work_day {
        date work_date PK "달력 날짜"
        bool is_workday "근무일 여부, 일요일 휴무"
        int daily_target_qty "하루 목표 180"
    }
    shift {
        text shift_id PK "예 2026-09-29-D"
        date work_date FK "근무일"
        code shift_type "주간, 야간"
        datetime start_at "교대 시작"
        datetime end_at "교대 끝"
        int planned_time_min "계획 가동 시간 480"
        int target_qty "교대 목표 90"
        text supervisor_user_id FK "해당 교대 반장"
    }
    wip_buffer {
        code buffer_code PK "WIP-10-20 등 4곳"
        code from_process_code FK "앞 공정"
        code to_process_code FK "뒤 공정"
        int limit_qty "한도 30, OP-30에서 40은 60"
        int warn_over_qty "경고 기준 20 초과"
        bool warn_enabled "경고 사용, OP-30에서 40은 거짓"
        bool use_in_bottleneck "병목 판단 사용, OP-30에서 40은 거짓"
    }
    plant_layout {
        text layout_id PK "BLDG"
        int width_x_mm "공장 가로 29000"
        int depth_y_mm "공장 세로 7000"
        int ceiling_z_mm "천장 4000"
        text origin_desc "원점, 남서쪽 벽 모서리 바닥"
        text axis_desc "X 동쪽 공정 흐름, Y 북쪽, Z 위, mm"
        int equipment_gap_mm "설비 사이 간격 1000"
        int aisle_width_mm "주 통로 폭 2000"
        int work_band_mm "설비 앞 작업 띠 1000"
        decimal floor_area_m2 "바닥 넓이, 계산"
    }
    layout_object {
        text object_id PK "RACK-01, WIP-1 등 11개"
        text layout_id FK "공장 배치"
        code object_kind "봉재 랙, 재공 자리 등"
        text object_name "이름"
        int x_min_mm "X 시작"
        int x_max_mm "X 끝"
        int y_min_mm "Y 시작"
        int y_max_mm "Y 끝"
        int height_mm "높이, 미정이면 비움"
        code source_tag "실제, 참고, 가상"
        code buffer_code FK, UK "재공 위치, WIP-1~4만"
    }
    equipment_part_shape {
        text equipment_id PK, FK "설비"
        int shape_seq PK "순번"
        text part_code "예 WSH-01-T"
        text part_name "진동 바렐, 톱날 등"
        code shape_kind "상자, 원기둥"
        int size_x_mm "가로 또는 지름"
        int size_y_mm "세로 또는 지름"
        int size_z_mm "높이"
        int offset_x_mm "설비 가운데 기준 X"
        int offset_y_mm "설비 가운데 기준 Y"
        int offset_z_mm "바닥에서 높이"
        code source_tag "실제, 참고, 가상"
    }
    process ||--|{ equipment : "속한 설비"
    equipment ||--|{ isolation_point : "차단 지점"
    process ||--o| wip_buffer : "앞 공정"
    process ||--o| wip_buffer : "뒤 공정"
    work_day ||--o{ shift : "교대"
    inventory_item ||--o{ product : "원자재 품목"
    app_user ||--o{ shift : "담당 반장"
    plant_layout ||--o{ layout_object : "배치 물체"
    wip_buffer |o--o| layout_object : "재공 자리"
    equipment ||--o{ equipment_part_shape : "부품 도형"
```

### 4.2 B 생산

```mermaid
erDiagram
    raw_material_lot {
        text material_lot_no PK "MAT-2609-01"
        text item_no FK "RM-6061"
        date received_date "입고일"
        int received_qty "입고 수량 개분"
        text supplier_cert_no "공급사 성적서 번호"
        text heat_batch_no "성적서의 로트 코드"
        code status "입고 검사 대기, 사용 가능, 입고 보류"
    }
    production_order {
        text order_no PK "PO-2609-001"
        text product_code FK "BRK-A100"
        int order_qty "24~60"
        datetime created_at "작업지시 만든 시각"
        datetime due_at "납기"
        code status "대기, 생산 중, 완료, 취소"
        datetime started_at "생산 시작"
        datetime completed_at "생산 완료"
    }
    production_lot {
        text lot_no PK "LOT-2609-041-1"
        text order_no FK "작업지시"
        int lot_seq "순번"
        text input_shift_id FK "OP-10 투입 교대"
        text material_lot_no FK "원자재 로트"
        int input_qty "투입 수량 1~60"
        code status "로트 상태"
        int completed_qty "완료 수량, 계산"
        int scrap_qty "폐기 수량"
        datetime expected_complete_at "예상 완료, 계산"
        datetime judged_at "로트 판정 시각"
    }
    operation_report {
        int op_report_id PK "일련번호"
        text lot_no FK "로트"
        code process_code FK "공정"
        text equipment_id FK "설비"
        text worker_user_id FK "작업자"
        text shift_id FK "처리 교대"
        datetime start_at "시작"
        datetime end_at "끝"
        int pq "생산 수량"
        int gq "양품"
        int rq "재작업"
        int sq "불량"
    }
    wip_log {
        code buffer_code PK, FK "재공 위치"
        datetime logged_at PK "기록 시각"
        int wip_qty "재공 수"
        int soak_shelf_qty "온도 맞춤 선반 수, 재공에 안 셈"
        code interval_type "5분, 1분"
    }
    bottleneck_log {
        int bottleneck_log_id PK "일련번호"
        datetime changed_at "병목이 바뀐 시각"
        code prev_process_code FK "이전 병목"
        code new_process_code FK "새 병목"
        code cause_code "원인 번호"
        int alarm_event_id FK "원인이 고장이면 알람"
        datetime interval_end_at "다음 기록 시각, 계산"
        decimal planned_qty "계획 생산 수, 계산"
        decimal actual_qty "실제 생산 수"
        decimal failure_loss_qty "고장 손실 수량"
        decimal speed_loss_qty "속도 손실 수량 추정"
    }
    lot_hold {
        int hold_id PK "일련번호"
        text lot_no FK "로트"
        code trigger_type "보류 계기"
        int related_alarm_event_id FK "계기 알람"
        text related_tool_id FK "계기 공구"
        longtext hold_reason "보류 사유"
        text held_by FK "보류한 사람 SUP, MGR"
        datetime held_at "보류 시각"
        int enhanced_next_lots "강화할 다음 로트 수 1, 2"
        text released_by FK "해제한 사람"
        datetime released_at "해제 시각"
        int scrap_proposed_qty "폐기 제안 수량"
        text scrap_proposed_by FK "폐기 제안 SUP"
        text scrap_approved_by FK "폐기 승인 MGR"
        datetime scrap_approved_at "폐기 승인 시각"
        text normal_resumed_by FK "보통 복귀 확인 SUP"
        datetime normal_resumed_at "보통 복귀 시각"
        code result "진행 중, 해제, 폐기"
    }
    inventory_item ||--o{ raw_material_lot : "원자재 품목"
    product ||--o{ production_order : "제품"
    production_order ||--o{ production_lot : "로트로 나눔"
    raw_material_lot ||--o{ production_lot : "투입 원자재"
    shift ||--o{ production_lot : "투입 교대"
    production_lot ||--o{ operation_report : "공정 실적"
    process ||--o{ operation_report : "공정"
    equipment ||--o{ operation_report : "설비"
    shift ||--o{ operation_report : "처리 교대"
    wip_buffer ||--o{ wip_log : "재공 기록"
    process ||--o{ bottleneck_log : "새 병목"
    process |o--o{ bottleneck_log : "이전 병목"
    alarm_event |o--o{ bottleneck_log : "고장 원인"
    production_lot ||--o{ lot_hold : "보류"
    alarm_event |o--o{ lot_hold : "계기 알람"
    tool |o--o{ lot_hold : "계기 공구"
```

### 4.3 C 설비·알람

```mermaid
erDiagram
    alarm_master {
        text alarm_code PK "992, 6302.00, WSH-01, TempComp-202 등"
        code process_code FK "적용 공정"
        text name_en "영문 이름"
        text name_ko "한국어 이름, 원문 그대로"
        longtext original_desc "원문 설명"
        longtext easy_desc "쉬운 설명, 팀 요약"
        code severity "정지, 주의, 조작 안내"
        code responder "작업자, 보전 담당자"
        text responder_note "반복되면 보전 담당자 등"
        code lockout_level "잠금·표지 판단"
        text chain_rule "연쇄 알람 순서, 예 108-994-992"
        text doc02_section "DOC-02 절"
        text source_ref "원문 위치"
        bool is_virtual_code "번호가 가상인지, WSH-01·02만 참"
    }
    alarm_guide_map {
        text alarm_code PK, FK "알람"
        int seq PK "순번"
        text doc_no FK "DOC-03"
        text section "절, 예 2.1"
    }
    alarm_event {
        int alarm_event_id PK "일련번호"
        text equipment_id FK "발생 설비"
        text alarm_code FK "알람 번호"
        code severity_at_event "발생 때 심각도"
        datetime occurred_at "발생 시각"
        datetime cleared_at "해제 시각"
        text lot_no FK "가공 중 로트"
        int prev_alarm_event_id FK "선행 알람"
        bool is_injected "시연 사건 넣기로 생김"
        code scenario_code "S1~S6"
    }
    equipment_state_log {
        int state_log_id PK "일련번호"
        text equipment_id FK "설비"
        code state_code "RUN, IDLE, BLOCKED, SETUP, DOWN, MAINT"
        code mtconnect_execution "ACTIVE, READY, STOPPED"
        datetime start_at "구간 시작"
        datetime end_at "구간 끝"
        decimal duration_min "길이 분, 계산"
        bool warn_marker "주의 등급 알람 노란 표시"
        code reason_suggested_code FK "AI비서 초안 추천 사유"
        code reason_code FK "입력·확정 정지 사유"
        code reason_status "추천, 입력, 확정"
        text reason_entered_by FK "입력한 사람 OPR, MNT"
        text reason_confirmed_by FK "확정한 사람 SUP"
        datetime reason_confirmed_at "확정 시각"
        int alarm_event_id FK "멈추게 한 알람"
        int pm_record_id FK "MAINT 구간의 정비 기록"
        decimal stop_loss_qty "정지 손실 수량 추정, 계산"
    }
    downtime_reason {
        code reason_code PK "F01~P03"
        code reason_group "FAILURE 등 5그룹"
        text reason_name "사유"
        code usual_state "보통 상태"
        text six_loss "6대 로스"
        bool is_loss "손실로 셈, PLANNED는 거짓"
    }
    sensor_item {
        code sensor_code PK "SpindleLoadPct 등 7개"
        text sensor_name "주축 부하 등"
        text unit "%, ℃, psi, V"
        decimal normal_min "정상 범위 아래"
        decimal normal_max "정상 범위 위"
        decimal normal_median "중앙값"
        text linked_alarm_code FK "연결 알람"
    }
    sensor_sample {
        text equipment_id PK, FK "VF2-01, VF2-02"
        code sensor_code PK, FK "센서"
        datetime sampled_at PK "시각"
        decimal value "값"
        code interval_type "1분 평균, 1초"
    }
    process ||--o{ alarm_master : "적용 공정"
    alarm_master ||--o{ alarm_guide_map : "고장 대응 절"
    internal_doc ||--o{ alarm_guide_map : "DOC-03"
    alarm_master ||--o{ alarm_event : "알람 번호"
    equipment ||--o{ alarm_event : "발생 설비"
    production_lot |o--o{ alarm_event : "가공 중 로트"
    alarm_event |o--o{ alarm_event : "선행 알람"
    equipment ||--o{ equipment_state_log : "상태 구간"
    downtime_reason |o--o{ equipment_state_log : "정지 사유"
    alarm_event |o--o| equipment_state_log : "멈춘 구간"
    pm_record |o--o| equipment_state_log : "정비 구간"
    alarm_master |o--o{ sensor_item : "연결 알람"
    sensor_item ||--o{ sensor_sample : "센서"
    equipment ||--o{ sensor_sample : "OP-30 설비"
```

### 4.4 D 정비

```mermaid
erDiagram
    maintenance_work_order {
        text wo_no PK "MW-0901"
        code trigger_kind "계기 1개 이상, 정지 등급 알람, 반복 알람 2단계 등"
        int alarm_event_id FK, UK "정지 등급 알람 OP-30"
        int pm_record_id FK, UK "예방 정비 중 이상"
        int trigger_notification_id FK, UK "반복 알람 2단계 알림"
        text equipment_id FK "VF2-01, VF2-02"
        text lot_no FK "로트"
        datetime created_at "만든 시각"
        text title "제목"
        longtext symptom "증상"
        code status "작업지시서 상태"
        text assignee_user_id FK "담당 보전 담당자"
        text approved_by FK "승인 SUP 또는 MGR 대리"
        datetime approved_at "승인 시각"
        text cancelled_by FK "취소 MGR"
        datetime cancelled_at "취소 시각"
        longtext cancel_reason "취소 사유"
        text safety_block_doc_rev "DOC-05 Rev.1"
        bool has_high_voltage_notice "고전압 대기 문구"
        datetime completed_at "완료 시각"
        int current_version "현재 버전"
    }
    work_order_step {
        text wo_no PK, FK "작업지시서"
        int step_no PK "단계 번호"
        longtext step_text "작업 순서"
        text source_section "DOC-03 절만 (원문 출처 없음)"
    }
    work_order_part {
        text wo_no PK, FK "작업지시서"
        text item_no PK, FK "재고 품목"
        decimal suggested_qty "제안 수량"
    }
    work_record {
        text record_no PK "MR-0901, MR-S-0901"
        code record_type "작업기록서, 간이 작업기록"
        text wo_no FK, UK "작업지시서"
        int alarm_event_id FK, UK "알람"
        int cause_check_notification_id FK, UK "원인 점검 요청 알림, 다른 공정"
        text equipment_id FK "설비"
        text lot_no FK "로트"
        longtext cause "원인"
        longtext action "조치"
        longtext worker_memo "작업자 메모"
        datetime start_at "시작"
        datetime end_at "끝"
        decimal repair_min "수리 시간 분"
        bool safety_block_required "잠금·표지 블록 필요"
        code status "작업기록서 상태"
        text confirmed_by FK "확정 MNT 또는 OPR"
        datetime confirmed_at "확정 시각"
        text checked_by FK "확인 SUP"
        datetime checked_at "확인 시각"
        int current_version "현재 버전"
    }
    work_record_check {
        text record_no PK, FK "작업기록서"
        int check_seq PK "순번"
        code check_kind "작업 순서, 잠금·표지"
        text wo_no FK "작업지시서"
        int step_no FK "작업 순서 단계"
        code loto_step_code "6.1~7.3"
        bool is_checked "체크"
        text checked_by FK "체크한 사람"
        datetime checked_at "체크 시각"
    }
    work_record_part {
        text record_no PK, FK "작업기록서"
        text item_no PK, FK "재고 품목"
        decimal qty "수량"
        code proposed_by_kind "AI, 사람"
    }
    pm_task {
        text pm_task_id PK "예 PM-VF2-02-2.3-01"
        text equipment_id FK "설비"
        text doc04_section "DOC-04 절"
        text area "부위"
        text item_name "항목 이름 원문 그대로"
        code cycle_code "매일, 매주, 매월 등"
        code lockout_level "잠금·표지 판단"
        code default_role "작업자, 보전 담당자"
        text default_item_no FK "기본 소모품"
        bool on_calendar "MNT-04 달력 등록"
        code source_tag "실제, 참고, 가상"
        date next_due_date "다음 기한, 계산"
    }
    pm_record {
        int pm_record_id PK "일련번호"
        text pm_task_id FK "정비 항목"
        date due_date "예정일"
        datetime done_at "실시 시각"
        text done_by FK "실시자 (작업자 항목은 OPR)"
        text recorded_by FK "기록자 MNT"
        code result "정상, 보충·교체함, 이상 있음"
        decimal measured_value "측정값"
        text measured_unit "단위"
        longtext memo "메모"
        bool is_on_time "기한 안 실시, 계산"
        code status "작성 중, 확정"
        int current_version "현재 버전"
    }
    alarm_event |o--o| maintenance_work_order : "작업지시서"
    pm_record |o--o| maintenance_work_order : "정비 중 이상"
    equipment ||--o{ maintenance_work_order : "설비"
    production_lot |o--o{ maintenance_work_order : "로트"
    maintenance_work_order ||--|{ work_order_step : "작업 순서"
    maintenance_work_order ||--o{ work_order_part : "예상 부품"
    inventory_item ||--o{ work_order_part : "품목"
    maintenance_work_order |o--o| work_record : "작업기록서"
    alarm_event |o--o| work_record : "간이 작업기록"
    equipment ||--o{ work_record : "설비"
    production_lot |o--o{ work_record : "로트"
    work_record ||--o{ work_record_check : "체크"
    work_order_step |o--o{ work_record_check : "수행 단계"
    work_record ||--o{ work_record_part : "사용 부품"
    inventory_item ||--o{ work_record_part : "품목"
    equipment ||--o{ pm_task : "정비 항목"
    inventory_item |o--o{ pm_task : "기본 소모품"
    pm_task ||--o{ pm_record : "실시 기록"
    notification |o--o| maintenance_work_order : "원인 점검 작업지시서"
    notification |o--o| work_record : "원인 점검 간이 기록"
```

### 4.5 E 공구·재고

```mermaid
erDiagram
    tool_type {
        text item_no PK, FK "TL-TAP6 등 5종"
        code usage_unit "HOLES, FEED"
        decimal usage_per_part "부품 1개당 사용량"
        decimal life_limit "수명 한도"
        text limit_basis "한도 근거 표시"
        int deduct_qty_per_change "교체 1회 차감 수 1, 5"
    }
    tool {
        text tool_id PK "예 VF2-01-T05"
        text equipment_id FK "VF2-01, VF2-02"
        text tool_no "공구 번호 T01~T05"
        text item_no FK "공구 종류"
        code tool_role "사용 중, 예비"
        decimal cum_usage "교체 뒤 누적 사용량"
        datetime last_changed_at "마지막 교체"
        decimal usage_rate_pct "사용률, 계산"
    }
    tool_usage {
        text tool_id PK, FK "공구"
        int op_report_id PK, FK "OP-30 공정 실적"
        int parts_qty "가공 부품 수"
        decimal usage_qty "더한 사용량"
        decimal cum_after "더한 뒤 누적"
        datetime recorded_at "기록 시각"
    }
    tool_change {
        int tool_change_id PK "일련번호"
        text tool_id FK "공구"
        datetime changed_at "교체 시각"
        text changed_by FK "OPR, MNT"
        decimal cum_before "교체 전 누적"
        code change_reason "교체 사유"
        int related_alarm_event_id FK "362, 174 알람"
    }
    inventory_item {
        text item_no PK "TL-EM10 등 13개"
        code category "공구, 소모품, 원자재, 완제품"
        text item_name "품목 이름"
        code unit "개, L, 개분"
        code owner_role FK "관리 역할 MNT, SUP"
        decimal safety_stock "안전 재고, 완제품은 비움"
        text product_note "제품 이름, 예 TRIM SC538"
        decimal on_hand_qty "현재 수량, 계산"
        text safety_stock_set_by FK "안전 재고 정한 MGR"
        datetime safety_stock_set_at "정한 시각"
    }
    inventory_txn {
        int txn_id PK "일련번호"
        text item_no FK "품목"
        code txn_type "입고, 사용, 조정, 합격 입고, 출하 출고"
        decimal qty_change "변화량, 부호 있음"
        datetime txn_at "거래 시각"
        text txn_by FK "기록한 사람"
        code source_kind "거래 출처"
        text work_record_no FK "작업기록서"
        text work_record_item_no FK "작업기록서 품목"
        int pm_record_id FK "예방 정비 기록"
        int tool_change_id FK, UK "공구 교체"
        text lot_no FK, UK "원자재 투입 로트"
        text material_lot_no FK, UK "원자재 입고 로트"
        text fg_lot_no FK "완제품 거래 로트"
        text shipment_no FK "출하"
        text ship_lot_no FK "출하 로트 줄"
        longtext memo "메모, 실사 차이 등"
    }
    shipment {
        text shipment_no PK "SHP-2609-001"
        datetime shipped_at "출하 일시"
        code customer_code "출하처 CUST-01"
        text basis_order_nos "근거 작업지시, 계산"
        date due_date "납기일"
        int total_qty "수량 합, 계산"
        text confirmed_by FK "출하 확인자 SUP"
        code status "작성 중, 확정, 확정 후 수정"
        longtext fifo_skip_reason "FIFO 안 지킨 사유"
        bool is_late "납기 지남, 계산"
        longtext memo "비고, 부분 출하 사유 등"
        int current_version "현재 버전"
    }
    shipment_line {
        text shipment_no PK, FK "출하"
        text lot_no PK, FK "생산 로트"
        int qty "수량"
        datetime lot_passed_at "로트 합격 시각, FIFO 확인"
    }
    inventory_item ||--o| tool_type : "공구 품목"
    tool_type ||--o{ tool : "종류"
    equipment ||--o{ tool : "꽂힌 설비"
    tool ||--o{ tool_usage : "사용"
    operation_report ||--o{ tool_usage : "가공 실적"
    tool ||--o{ tool_change : "교체"
    alarm_event |o--o{ tool_change : "교체 계기 알람"
    inventory_item ||--o{ inventory_txn : "거래"
    work_record_part |o--o| inventory_txn : "부품 사용"
    pm_record |o--o{ inventory_txn : "소모품 사용"
    tool_change |o--o| inventory_txn : "공구 차감"
    production_lot |o--o| inventory_txn : "원자재 투입"
    raw_material_lot |o--o| inventory_txn : "원자재 입고"
    role ||--o{ inventory_item : "관리 역할"
    shipment ||--|{ shipment_line : "로트 줄"
    production_lot ||--o{ shipment_line : "출하한 로트"
    shipment_line |o--o| inventory_txn : "출하 출고"
    production_lot |o--o{ inventory_txn : "완제품 거래"
    app_user |o--o{ shipment : "출하 확인자"
```

### 4.6 F 품질

```mermaid
erDiagram
    inspection_item {
        text product_code PK, FK "BRK-A100"
        int item_seq PK "DOC-06 2장 번호 1~8"
        text item_name "부싱 압입 구멍 지름 등"
        text spec_text "기준 글"
        decimal nominal "기준값 mm"
        decimal lsl "아래 한계"
        decimal usl "위 한계"
        code method "3차원 측정기, 게이지, 육안"
        code char_class "특별 특성, 일반"
        decimal cpk_min "Cpk 기준 1.67, 1.33"
        bool in_sampling "발췌 때 측정"
        text enhanced_extension "강화 때 늘리는 것"
        bool is_full_check_by_cpk "Cpk 미달로 전수 중"
    }
    defect_code {
        code defect_code PK "DIM-01 등 10개"
        text defect_name "이름"
        text related_items "관련 검사 항목 번호"
        code grade "치명, 중, 경"
        text grade_rule "등급 규칙"
        text common_cause "자주 보는 원인"
    }
    inspection_plan {
        text lot_no PK, FK "로트"
        code plan_mode "보통, 강화"
        code enhance_reason "강화 사유"
        int hold_id FK "강화 계기 보류"
        int planned_measure_qty "측정할 부품 수, 계산"
        int gauge_pass_qty "게이지·육안 합격 수"
        int gauge_fail_qty "게이지·육안 불합격 수"
        code judgement "합격, 보류 검토"
        datetime judged_at "판정 시각"
    }
    inspection_result {
        int result_id PK "일련번호"
        text lot_no FK "로트"
        int part_seq "부품 순번"
        text product_code FK "제품"
        int item_seq FK "검사 항목"
        code insp_kind "초품, 발췌, 강화"
        code position "위, 중간, 아래"
        decimal measured_value "측정값 mm"
        code judgement "플랫폼 판정, 합격, 불합격"
        text instrument_id FK "측정기 CMM-01"
        text inspector_id FK "측정자 OPR"
        datetime measured_at "측정 시각"
        decimal room_temp_c "측정실 온도, 방 공기"
        decimal part_temp_c "부품 온도"
        bool temp_comp_used "부품 온도 보정 사용"
        code input_method "입력 방식, CMM 자동, 태블릿 버튼, 수동"
        int cmm_import_id FK "결과 파일"
        code cmm_judgement "측정기 판정"
        bool is_judgement_mismatch "판정 불일치, 계산"
        bool is_temp_flag "온도 확인 표시, 계산"
        code check_status "확인 상태"
        text checked_by FK "확인한 반장"
        datetime checked_at "확인 시각"
        int remeasure_seq "재측정 순번, 처음 1"
        bool use_for_judgement "판정에 씀"
        text entered_by FK "수동 입력자"
    }
    cmm_import {
        int cmm_import_id PK "일련번호"
        text file_name UK "결과 파일 이름"
        datetime received_at "받은 시각"
        code status "성공, 실패, 확인 필요"
        code error_kind "오류 종류"
        longtext error_text "오류 내용"
        text original_file_ref "원본 파일 보관 위치"
        text instrument_id FK "측정기 CMM-01"
        text lot_no FK "파일의 로트"
        int part_seq "파일의 부품 순번"
        code insp_kind "파일의 검사 방식"
        text program_name_rev "측정 프로그램 이름과 개정"
        datetime measure_start_at "측정 시작, 측정기 시계"
        datetime measure_end_at "측정 끝, 측정기 시계"
        decimal machine_temp_c "측정기 온도"
        bool temp_comp_on "온도 보정 켬"
    }
    defect_record {
        int defect_record_id PK "일련번호"
        text lot_no FK "로트"
        code process_code FK "발견 공정"
        code defect_code FK "불량 코드"
        int qty "수량"
        code disposition "폐기, 재작업"
        int result_id FK, UK "불합격 측정값"
        datetime found_at "발견 시각"
        text recorded_by FK "기록한 사람"
    }
    product ||--|{ inspection_item : "검사 항목"
    production_lot ||--|| inspection_plan : "검사 방식"
    lot_hold |o--o{ inspection_plan : "강화 사유"
    production_lot ||--o{ inspection_result : "측정값"
    inspection_item ||--o{ inspection_result : "항목"
    equipment ||--o{ inspection_result : "측정기"
    production_lot ||--o{ defect_record : "불량"
    defect_code ||--o{ defect_record : "불량 코드"
    process ||--o{ defect_record : "발견 공정"
    inspection_result |o--o| defect_record : "불합격 측정"
    equipment ||--o{ cmm_import : "측정기"
    production_lot |o--o{ cmm_import : "결과 파일 로트"
    cmm_import |o--o{ inspection_result : "자동 입력"
    app_user |o--o{ inspection_result : "확인, 수동 입력"
```

### 4.7 G 문서·AI 비서

```mermaid
erDiagram
    shift_report {
        text shift_id PK, FK "교대"
        code status "문서 상태"
        int target_qty "목표"
        int actual_qty "실적"
        int defect_qty "불량"
        decimal availability_pct "가동률 OP-30 설비별"
        longtext notable_text "특이 사항 3~5문장"
        longtext handover_text "인계 사항"
        text confirmed_by FK "해당 교대 반장"
        datetime confirmed_at "확정 시각"
        int current_version "현재 버전"
    }
    daily_report {
        date work_date PK, FK "근무일"
        code status "문서 상태"
        int target_qty "하루 목표 180"
        int actual_qty "실적"
        int defect_qty "불량"
        decimal oee_pct "OEE"
        decimal failure_loss_qty "고장 손실 추정"
        decimal speed_loss_qty "속도 손실 추정"
        longtext issues_summary "오늘의 문제, 전체 N건"
        text confirmed_by FK "MGR"
        datetime confirmed_at "확정 시각"
        int current_version "현재 버전"
    }
    document_revision {
        int revision_id PK "일련번호"
        code doc_type "문서 종류"
        text doc_key UK "문서 번호"
        int version_no UK "버전 0은 AI비서 초안"
        code author_kind "AI, 사람"
        text author_user_id FK "고친 사람"
        datetime created_at "저장 시각"
        longtext reason "사유, 확정 뒤 수정이면 필수"
        code status_after "저장 뒤 문서 상태"
        longtext content_snapshot "그 버전 전체 내용"
        text internal_doc_rev "사내 문서 개정 번호"
    }
    document_revision_change {
        int revision_id PK, FK "버전"
        text field_name PK "바뀐 칸"
        longtext before_value "고치기 전"
        longtext after_value "고친 뒤"
    }
    internal_doc {
        text doc_no PK "DOC-01~07, GLOSSARY"
        code doc_kind "사내 문서, 용어집"
        text doc_name "문서 이름"
        text current_rev "현재 개정 예 Rev.1"
        date rev_date "개정 날짜"
        code status "승인 대기, 승인"
        text approved_by FK "승인 MGR"
        datetime approved_at "승인 시각"
        bool is_search_target "비서 검색 대상"
        text file_ref "파일 위치"
    }
    doc_chunk {
        int chunk_id PK "일련번호"
        text doc_no FK "사내 문서"
        text doc_rev "개정 번호"
        text section "절"
        longtext chunk_text "조각 본문"
        text embedding "임베딩, 형식은 AI 비서 설계"
        datetime built_at "만든 시각"
    }
    shift ||--o| shift_report : "교대 보고서"
    work_day ||--o| daily_report : "일일 보고서"
    maintenance_work_order ||--|{ document_revision : "버전"
    work_record ||--|{ document_revision : "버전"
    shift_report ||--|{ document_revision : "버전"
    daily_report ||--|{ document_revision : "버전"
    internal_doc ||--|{ document_revision : "버전"
    pm_record ||--|{ document_revision : "버전"
    document_revision ||--o{ document_revision_change : "바뀐 칸"
    internal_doc ||--o{ doc_chunk : "문서 조각"
    internal_doc ||--o{ alarm_guide_map : "DOC-03"
    shipment ||--|{ document_revision : "버전"
```

### 4.8 H 사용자·권한·알림

```mermaid
erDiagram
    app_user {
        text user_id PK "사용자 ID"
        text user_name "이름"
        code role_code FK "OPR, MNT, SUP, MGR"
        code home_shift_type "담당 교대"
        code home_process_code FK "담당 공정, OPR"
        bool is_active "사용 중"
    }
    role {
        code role_code PK "OPR, MNT, SUP, MGR"
        text role_name "현장 작업자 등"
    }
    role_permission {
        code role_code PK, FK "역할"
        code target PK "문서 또는 기능"
        code action PK "보기, 작성, 확정 등"
        code scope "전체, 자기 문서, 요약만"
    }
    notification_rule {
        code rule_code PK "알림 종류 코드"
        text rule_name "알림 종류"
        text condition_text "조건"
        code importance "긴급, 주의, 참고"
        bool is_enabled "사용"
        text updated_by FK "고친 MGR"
        datetime updated_at "고친 시각"
    }
    notification {
        int notification_id PK "일련번호"
        code rule_code FK "알림 규칙"
        code importance "긴급, 주의, 참고"
        datetime raised_at "발생 시각"
        longtext message "알림 문장"
        longtext related_info "관련 정보 한 줄"
        code message_source "비서 문장, 기본 문구"
        int repeat_count "묶은 횟수"
        bool is_flood "폭주 묶음 표시"
        code report_rank "보고 순위 0, 0-1, 1~4, 계산"
        bool is_processed "처리됨"
        code process_kind "자동, 사람"
        text processed_by FK "처리한 사람"
        longtext process_memo "처리 메모"
        datetime processed_at "처리 시각"
        int alarm_event_id FK "알람"
        text equipment_id FK "설비"
        text lot_no FK "로트"
        text item_no FK "재고 품목"
        text pm_task_id FK "정비 항목"
        text tool_id FK "공구"
        text wo_no FK "작업지시서"
        int bottleneck_log_id FK "병목 기록"
        int revision_id FK "문서 버전"
        int result_id FK "검사 결과"
        text shift_id FK "교대"
        code buffer_code FK "재공 위치"
        int cmm_import_id FK "결과 파일"
        int prev_stage_notification_id FK "앞 단계 반복 알람 알림"
        code repeat_stage_status "반복 알람 단계 상태"
        datetime effect_check_due_at "효과 확인 기한, 계산"
    }
    notification_recipient {
        int notification_id PK, FK "알림"
        text user_id PK, FK "받는 사람"
        bool popup_sound "팝업과 소리"
        datetime read_at "읽은 시각"
    }
    role ||--o{ app_user : "역할"
    role ||--o{ role_permission : "권한"
    process |o--o{ app_user : "담당 공정"
    notification_rule ||--o{ notification : "규칙"
    notification ||--|{ notification_recipient : "받는 사람"
    app_user ||--o{ notification_recipient : "사용자"
    app_user |o--o{ notification : "처리한 사람"
    alarm_event |o--o{ notification : "알람"
    equipment |o--o{ notification : "설비"
    production_lot |o--o{ notification : "로트"
    inventory_item |o--o{ notification : "재고 품목"
    pm_task |o--o{ notification : "정비 항목"
    tool |o--o{ notification : "공구"
    maintenance_work_order |o--o{ notification : "작업지시서"
    bottleneck_log |o--o{ notification : "병목"
    document_revision |o--o{ notification : "문서 수정"
    inspection_result |o--o{ notification : "관리도 이상"
    shift |o--o{ notification : "교대"
    wip_buffer |o--o{ notification : "재공 경고"
    cmm_import |o--o{ notification : "결과 파일 알림"
    notification |o--o{ notification : "앞 단계 알림"
    role ||--o{ inventory_item : "관리 역할"
```

---

## 5. 엔터티 정의서

- 표의 칸: **속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처**.
- "대략 건수(30일)"는 **설계서·DOC에 있는 값만** 적는다. 없으면 "값 없음"이라고 적고 만들지 않는다.
- 사람을 가리키는 칸(`~_by`, `~_user_id`)은 모두 `app_user.user_id`를 가리킨다. 역할 제한은 값·규칙 칸에 적는다.

### 5.A 기준 정보

#### 5.A.1 `process` 공정

| 항목 | 내용 |
|---|---|
| 설명 | 라인의 5개 공정. 공정 순서, 재공 위치, 병목 판단의 단위 |
| 쓰는 요구사항 | FR-PRD-01-01·06·08, FR-PRD-05-03, FR-MNT-02-13, NFR-DATA-01 |
| 대략 건수 | 5행 (OP-10~OP-50) |
| 출처 | 설계서 5.1, DOC-07 2.1. 엔터티 자체는 [제안] (설계서·기획서 12.4에 테이블 이름 없음) |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| process_code | 공정 코드 | 코드 | PK | ○ | OP-10, OP-20, OP-30, OP-40, OP-50 | 설계서 5.1 |
| process_name | 공정 이름 | 문자 | | ○ | 절단, 황삭, 정밀 가공, 세척·디버링, 측정 | 설계서 5.1 |
| seq | 공정 순서 | 정수 | UK | ○ | 1~5. 부품은 이 순서로만 흐른다 | 설계서 5.5 |
| is_base_bottleneck | 기준 병목 여부 | 참·거짓 | | ○ | OP-30만 참. 병목 조건에 맞는 공정이 없을 때 표시 | DOC-07 7.3 ④ |

#### 5.A.2 `equipment` 설비

| 항목 | 내용 |
|---|---|
| 설명 | 라인 설비 6대. 기준 사이클 시간은 성능(E)과 고장 손실 수량 계산에 쓴다. 최종본에서 **실제 치수 외형과 공장 안 배치 좌표**를 더했다 (3D 라인 뷰를 실제 크기로, D-02) |
| 쓰는 요구사항 | FR-PRD-01-01·03·12·16·20·21·27·28, FR-MNT-03-10, FR-PRD-05-03, NFR-DATA-01, NFR-SEC-04 |
| 대략 건수 | 6행 |
| 출처 | 설계서 5.1, DOC-07 2.1, 기획서 12.4 `equipment`, R1 3장·7장, DOC-01 §2.4 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| equipment_id | 설비 ID | 문자 | PK | ○ | SAW-01, MIL-01, VF2-01, VF2-02, WSH-01, CMM-01 | 설계서 5.1 |
| process_code | 공정 | 코드 | FK | ○ | → process. OP-30만 2대 | 설계서 5.1 |
| model | 모델 | 문자 | | ○ | Haas HCS-80, 3축 머시닝센터, Haas VF-2, 초음파 세척기 + 텀블러, 3차원 측정기 | 설계서 5.1 (모델 [실제]/[가상]) |
| controller | 제어기 | 문자 | | — | Haas, Siemens 840D sl, Haas NGC. WSH-01·CMM-01은 비움 | 설계서 5.1 |
| std_cycle_min | 기준 사이클 시간 | 소수 | | 조건 | 분/개. SAW-01 1.0, MIL-01 3.5, VF2-01·02 7.0, CMM-01 평소 0.9 (강화 5.0은 검사 방식 코드 6.32). WSH-01은 비움 | 설계서 5.1, DOC-07 2.1 [가상] |
| batch_qty | 묶음 수량 | 정수 | | 조건 | WSH-01만 30 | 설계서 5.1 |
| batch_time_min | 묶음 시간 | 소수 | | 조건 | WSH-01만 25분 | 설계서 5.1 |
| has_sensor | 센서 기록 여부 | 참·거짓 | | ○ | VF2-01·02만 참 | DOC-07 3장 |
| size_x_mm | 외형 가로 (X) | 정수 | | ○ | mm. 아래 표 | R1 3장·7장 |
| size_y_mm | 외형 세로 (Y) | 정수 | | ○ | mm. 아래 표 | R1 3장·7장 |
| size_z_mm | 외형 높이 (Z) | 정수 | | ○ | mm. 아래 표. 클릭 확대 때 카메라 목표점 높이 = size_z_mm ÷ 2 (계산) | R1 7장·9장 |
| center_x_mm | 배치 가운데 X | 정수 | | ○ | 바닥 사각형 가운데. 좌표 규칙은 `plant_layout` | R1 2장·7장 [가상] |
| center_y_mm | 배치 가운데 Y | 정수 | | ○ | 같음 | R1 7장 [가상] |
| facing | 정면 방향 | 코드 | | ○ | 6.51. **모두 −Y (남쪽, 통로 쪽)** — 작업자는 통로 쪽에서 문·조작반을 씀 | R1 2장 [가상] |
| size_source_tag | 크기 근거 | 코드 | | ○ | 6.41 ([실제] / [참고] / [가상]). 자리(좌표)는 모두 [가상] | R1 7장 |
| ref_model | 참고 모델 | 문자 | | 조건 | 크기를 다른 모델에서 빌린 설비만 (크기 근거가 [참고]). **model 칸은 바꾸지 않는다** (MIL-01은 계속 "3축 머시닝센터 [가상]") | R1 3.2·3.4, R3 4장 |

**설비별 외형·배치 값** (R1 7장 3D 배치 기준표 그대로)

| 설비 | 외형 X × Y × Z (mm) | 가운데 (X, Y) | 크기 근거 | 참고 모델 |
|---|---|---|---|---|
| SAW-01 | 2,300 × 2,260 × 2,210 | (6,300, 4,930) | [실제: Haas HCS-80 사양표] | — |
| MIL-01 | 2,757 × 1,864 × 2,935 | (9,829, 4,732) | [참고] | DMG MORI CMX 600 V (크기만 빌림. 판매 목록 값, 칩 컨베이어 포함 여부 모름) |
| VF2-01 | 3,147 × 2,249 × 2,724 | (13,781, 4,925) | [실제: Haas VF-2 배치도 MLD] | — |
| VF2-02 | 3,147 × 2,249 × 2,724 | (17,928, 4,925) | [실제: Haas VF-2 배치도 MLD] | — |
| WSH-01 | 3,000 × 1,500 × 1,291 (구역) | (22,001, 4,550) | [가상] (안의 설비는 `equipment_part_shape`) | 진동 바렐 Kalamazoo KVF3급 + 초음파 세척기 Branson CPX8800H-E급 |
| CMM-01 | 1,110 × 1,266 × 2,414 (본체, 화면 제외) | (25,923, 4,433) | [참고] | Hexagon TIGO SF 05.06.05 (측정 범위 500 × 580 × 500 mm [실제]) |

- 설비는 여전히 **단순 도형(상자·원기둥)의 조합**으로 그린다. 크기만 실제이고 사실적인 모델링·질감은 하지 않는다 (기획서 8.1 유지).
- 값이 바뀌면(예: CMM-01 공식 데이터시트) R1 7장 좌표의 X를 다시 계산한다 (R1 3.5).

#### 5.A.3 `isolation_point` 차단 지점

| 항목 | 내용 |
|---|---|
| 설명 | 설비마다 잠금·표지를 거는 에너지 차단 지점. 작업지시서·지침카드 안전 칸이 여기서 가져온다 |
| 쓰는 요구사항 | FR-MNT-03-10, FR-MNT-02-07·08, FR-MNT-04-09, NFR-SAFE-02 |
| 대략 건수 | 15행 (SAW-01 2, MIL-01 3, VF2-01 3, VF2-02 3, WSH-01 2, CMM-01 2 — DOC-05 §3) |
| 출처 | 설계서 5.1 "차단 지점 2~3개", DOC-05 §3 [가상]. 기획서 12.4는 `equipment` 안 칸으로 둠 → 분리 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| isolation_point_id | 차단 지점 번호 | 문자 | PK | ○ | `{설비 ID}-E1`, `-E2`, `-P1` 형식 (예: VF2-01-E1) | DOC-05 §3 [가상] |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment | DOC-05 §3 |
| point_name | 차단 지점 이름 | 문자 | | ○ | 예: "VF2-01 주 차단기", "VF2-01 공압 주 밸브" | 설계서 5.1, DOC-05 §3 |
| energy_type | 에너지 종류 | 코드 | | ○ | 6.21 (전기 / 전기(공급원) / 공압) | DOC-05 §3 |
| location | 위치 | 문자 | | ○ | 예: "기계 뒤쪽 제어반의 오른쪽 위" | DOC-05 §3 |
| lock_method | 잠금 방법 | 문자 | | ○ | 예: "밸브를 닫고 잠금 + 잔압 빼기" | DOC-05 §3 |
| seq | 차단 순서 | 정수 | | ○ | 주 차단기 → 공압 주 밸브 → 공급 분전반 차단기 순 | DOC-05 §2.1 6.3 |

#### 5.A.4 `product` 제품

| 항목 | 내용 |
|---|---|
| 설명 | 라인이 만드는 제품. 1종뿐이지만 검사 항목·작업지시가 가리킨다 |
| 쓰는 요구사항 | FR-PRD-05-02, FR-QLT-01-02, FR-PRD-01-15 |
| 대략 건수 | 1행 (BRK-A100) |
| 출처 | 설계서 5.3. 엔터티 이름은 [제안] (설계서에 테이블 이름 없음) |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| product_code | 제품 코드 | 문자 | PK | ○ | BRK-A100 | 설계서 5.3 [가상] |
| product_name | 제품 이름 | 문자 | | ○ | 엔진 마운트 브래킷 | 설계서 5.3 |
| material | 재질 | 문자 | | ○ | 알루미늄 6061-T6 | 설계서 5.3 (재질은 실제 규격) |
| line_base_cycle_min | 라인 기준 속도 | 소수 | | ○ | 3.5분/개 (OP-30 7.0 ÷ 2대). 계획 생산 수 계산에 씀 | 설계서 5.3, DOC-07 5.3 |
| material_item_no | 원자재 품목 | 문자 | FK | ○ | → inventory_item (RM-6061) | 설계서 5.14 |

#### 5.A.5 `work_day` 근무일

| 항목 | 내용 |
|---|---|
| 설명 | 달력 날짜. 근무일이면 교대 2개와 일일 보고서 1개가 붙는다 |
| 쓰는 요구사항 | FR-PRD-04-01·02, FR-AST-02-16, NFR-DATA-01 |
| 대략 건수 | 30행 (2026-09-01~09-30), 그중 근무일 26 |
| 출처 | 설계서 5.2. 기획서 12.4 `shift_target`의 하루 목표를 여기에 둠 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| work_date | 날짜 | 날짜 | PK | ○ | 2026-09-01 ~ 09-30 | 설계서 5.2 |
| is_workday | 근무일 여부 | 참·거짓 | | ○ | 월~토 참, 일요일(6·13·20·27일) 거짓 | 설계서 5.2 [가상] |
| daily_target_qty | 하루 목표 | 정수 | | 조건 | 근무일이면 180. MGR만 정함 | 설계서 5.3, 기획서 13.2 |

#### 5.A.6 `shift` 교대

| 항목 | 내용 |
|---|---|
| 설명 | 교대 1회 (주간 또는 야간). 목표·계획 가동 시간·담당 반장을 가진다. 교대 보고서·로트 투입·공정 실적이 가리킨다 |
| 쓰는 요구사항 | FR-PRD-01-15, FR-PRD-02-01·11, FR-AST-01-01, FR-AST-02-04·16, FR-PRD-05-02, NFR-DATA-01 |
| 대략 건수 | 52행 |
| 출처 | 설계서 5.2·5.3, DOC-07 4.1, 기획서 12.4 `shift_target` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| shift_id | 교대 ID | 문자 | PK | ○ | `{날짜}-D` (주간) / `{날짜}-N` (야간). 예: 2026-09-29-D | [제안] |
| work_date | 근무일 | 날짜 | FK | ○ | → work_day. 야간이 다음 날 05:00에 끝나도 시작한 날짜 | 설계서 5.2 |
| shift_type | 교대 구분 | 코드 | | ○ | 6.10 (주간 / 야간). (work_date, shift_type)은 UK | 설계서 5.2 |
| start_at | 시작 시각 | 날짜시각 | | ○ | 주간 08:00, 야간 20:00 | 설계서 5.2 [가상] |
| end_at | 끝 시각 | 날짜시각 | | ○ | 주간 17:00, 야간 다음 날 05:00 (휴식 1시간 포함) | 설계서 5.2 [가상] |
| planned_time_min | 계획 가동 시간 | 정수 | | ○ | 480분 (휴식 제외) | 설계서 5.2, DOC-07 4.1 |
| target_qty | 교대 목표 | 정수 | | ○ | 90개. MGR만 정함 | 설계서 5.3, FR-AST-02-16 |
| supervisor_user_id | 담당 반장 | 문자 | FK | ○ | → app_user, 역할 SUP. 교대 보고서를 확정할 사람 | 설계서 5.16·5.17 |

#### 5.A.7 `wip_buffer` 재공 위치

| 항목 | 내용 |
|---|---|
| 설명 | 공정 사이 재공을 두는 4곳과 그 한도·경고 기준. BLOCKED 판단, 재공 경고, 병목 판단이 쓴다 |
| 쓰는 요구사항 | FR-PRD-01-03·06·07·08, FR-AST-02-05 |
| 대략 건수 | 4행 |
| 출처 | 설계서 5.6, DOC-07 7.1·7.2, 기획서 19장. 엔터티는 [제안] (설계서에는 `wip_log`만 있음) |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| buffer_code | 재공 위치 코드 | 코드 | PK | ○ | WIP-10-20, WIP-20-30, WIP-30-40, WIP-40-50 (6.39) | [제안] |
| from_process_code | 앞 공정 | 코드 | FK, UK | ○ | → process | 설계서 5.6 |
| to_process_code | 뒤 공정 | 코드 | FK, UK | ○ | → process. 앞 공정 seq + 1 | 설계서 5.6 |
| limit_qty | 재공 한도 | 정수 | | ○ | 30개 (대차 1대분). **WIP-30-40만 60개** (대차 2대분) | 설계서 5.6, 기획서 19장 [가상] |
| warn_over_qty | 경고 기준 | 정수 | | 조건 | 20개 **초과**면 경고. WIP-30-40은 비움 | 설계서 5.6, DOC-07 7.2 [가상] |
| warn_enabled | 경고 사용 | 참·거짓 | | ○ | WIP-30-40만 거짓 (묶음 대기) | DOC-07 7.2 |
| use_in_bottleneck | 병목 판단 사용 | 참·거짓 | | ○ | WIP-30-40만 거짓 | DOC-07 7.3 ⑤ |

#### 5.A.8 `plant_layout` 공장 배치 — 최종본 새 엔터티

| 항목 | 내용 |
|---|---|
| 설명 | 공장 전체의 크기와 좌표 규칙. 3D 라인 뷰가 **공장 전체를 담은 처음 각도**와 설비·배치 물체 좌표의 기준으로 쓴다 |
| 쓰는 요구사항 | FR-PRD-01-27·28, FR-PRD-01-01 |
| 대략 건수 | **1행** |
| 출처 | R1 2장·5장·6장 [가상], DOC-01 §2.4, 변경 명세 4장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| layout_id | 공장 배치 ID | 문자 | PK | ○ | `BLDG` | R1 7장 |
| width_x_mm | 공장 가로 (X) | 정수 | | ○ | 29,000 mm (서쪽 벽 여유 + 투입 대 + 설비·간격 + 완성품 자리 → 1 m 단위로 올림) | R1 6장 [가상] |
| depth_y_mm | 공장 세로 (Y) | 정수 | | ○ | 7,000 mm (통로 2,000 + 재공 띠 800 + 작업 띠 1,000 + 가장 깊은 설비 + 뒤 여유 → 올림) | R1 6장 [가상] |
| ceiling_z_mm | 천장 높이 | 정수 | | ○ | 4,000 mm (가장 높은 설비 MIL-01 2,935 [참고], 산업안전보건기준 규칙 제84조의 "4미터" 공기 부피 기준 [실제]). 천장 크레인은 없다고 가정 | R1 6장 [가상] |
| origin_desc | 원점 | 문자 | | ○ | "공장 안쪽 남서쪽 벽 모서리, 바닥" | R1 2장 [가상] |
| axis_desc | 축 방향 | 문자 | | ○ | "X = 동쪽(+), 공정 흐름 OP-10 → OP-50 / Y = 북쪽(+), 주 통로에서 멀어지는 쪽 / Z = 위(+), 바닥 0 / 단위 mm" | R1 2장 [가상] |
| equipment_gap_mm | 설비 사이 간격 | 정수 | | ○ | 1,000 mm (Haas VF-2 둘레 여유 914 mm [실제] ≥ 일본 노동안전위생규칙 제543조 80 cm [참고] → 100 mm 단위로 올림) | R1 4장·5장 [가상] |
| aisle_width_mm | 주 통로 폭 | 정수 | | ○ | 2,000 mm (KOSHA A-G-17-2026 "화물 폭 + 60 cm" [참고] + 비켜 설 여유) | R1 5장 [가상] |
| work_band_mm | 설비 앞 작업 띠 | 정수 | | ○ | 1,000 mm (Y 2,800 ~ 3,800). 설비 정면 선 Y = 3,800 | R1 5장 [가상] |
| floor_area_m2 | 바닥 넓이 | 소수 | | — | **계산**: 가로 × 세로 (203 m²) | R1 6장 |

- 한국 산업안전보건기준 규칙 제22조에는 일반 작업장 통로 폭·기계 사이 간격 숫자가 없다 (R1 4장 L7). 위 간격 값은 [가상]이고 근거를 함께 적었다.
- 3D 엔진의 좌표로 바꾸는 방법(엔진마다 위쪽 축이 다름)은 [선택 필요: 기술 회의] (R1 2장).
- 남은 점: 천장 크레인 없음 가정, 비상구 조항(제17조) 적용 대상인지 판단 안 함, 확인 못 한 값은 R1 8장.

#### 5.A.9 `layout_object` 배치 물체 — 최종본 새 엔터티

| 항목 | 내용 |
|---|---|
| 설명 | 설비가 아닌 바닥 위 물체: 봉재 랙, 투입 대, 재공 자리, 온도 맞춤 선반, 완성품 자리, 주 통로, 반입문, 비상구. 재공 자리는 재공 위치(`wip_buffer`)와 이어져 3D에서 재공 수를 그 자리에 보인다 |
| 쓰는 요구사항 | FR-PRD-01-27·28, FR-PRD-01-06·07 |
| 대략 건수 | 11행 (아래 표) |
| 출처 | R1 3.6·6장·7장, 변경 명세 4장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| object_id | 배치 물체 ID | 문자 | PK | ○ | R1 7장 ID 그대로 (RACK-01, INF-01, WIP-1~4, SOAK-01, FG-01, AISLE-1, DOOR-1, EXIT-1) | R1 7장 [가상] |
| layout_id | 공장 배치 | 문자 | FK | ○ | → plant_layout (BLDG) | — |
| object_kind | 종류 | 코드 | | ○ | 6.49 | R1 7장 |
| object_name | 이름 | 문자 | | ○ | 예: "재공 OP-10→20 (한도 30, 상자 1)" | R1 7장 |
| x_min_mm | X 시작 | 정수 | | ○ | 문(벽 위 물체)은 X 시작 = X 끝 (벽의 X) | R1 7장 |
| x_max_mm | X 끝 | 정수 | | ○ | X 시작 이상 | R1 7장 |
| y_min_mm | Y 시작 | 정수 | | ○ | — | R1 7장 |
| y_max_mm | Y 끝 | 정수 | | ○ | Y 시작보다 큼 | R1 7장 |
| height_mm | 높이 | 정수 | | — | 바닥 표시만인 것(재공 자리·통로)과 "미정"인 것(봉재 랙, 온도 맞춤 선반)은 비움. 문은 높이 (반입문은 "이상") | R1 7장 |
| source_tag | 근거 | 코드 | | ○ | 6.41. INF-01은 크기 [가상]·높이 925 [실제] → 이 칸은 [가상], 높이 근거는 아래 표 | R1 7장 |
| buffer_code | 재공 위치 | 코드 | FK, UK | 조건 | → wip_buffer. **재공 자리(WIP-1~4)만 필수**, 나머지는 비움. WIP-1 = WIP-10-20, WIP-2 = WIP-20-30, WIP-3 = WIP-30-40, WIP-4 = WIP-40-50 | R1 7장, 6.39 |

**배치 물체 처음 값** (R1 7장 그대로, 단위 mm)

| object_id | 종류 | X 범위 | Y 범위 | 크기·높이 | 재공 위치 | 근거 |
|---|---|---|---|---|---|---|
| RACK-01 | 봉재 랙 | 1,000 ~ 5,000 | 6,300 ~ 6,900 | 4,000 × 600 × (미정) | — | [가상] (봉 길이 3,658 mm — 설계서 5.4) |
| INF-01 | SAW-01 투입 대 | 1,000 ~ 5,000 | 3,800 ~ 5,000 | 4,000 × 1,200 × 925 | — | 크기 [가상], 높이 [실제: HCS-80 재료 받침 925] |
| WIP-1 | 재공 자리 | 7,350 ~ 8,550 | 2,000 ~ 2,800 | 1,200 × 800 | WIP-10-20 | [가상] (상자 VDA R-KLT 6429 [참고] 1개) |
| WIP-2 | 재공 자리 | 11,107 ~ 12,307 | 2,000 ~ 2,800 | 1,200 × 800 | WIP-20-30 | [가상] (상자 1개) |
| WIP-3 | 재공 자리 | 19,401 ~ 20,601 | 2,000 ~ 2,800 | 1,200 × 800 | WIP-30-40 | [가상] (한도 60, 상자 2개) |
| WIP-4 | 재공 자리 | 23,401 ~ 24,601 | 2,000 ~ 2,800 | 1,200 × 800 | WIP-40-50 | [가상] (상자 1개) |
| SOAK-01 | 온도 맞춤 선반 | 24,501 ~ 25,701 | 5,900 ~ 6,400 | 1,200 × 500 × (미정) | — (재공에 안 셈, R-13) | [가상] |
| FG-01 | 완성품 자리 | 27,478 ~ 28,678 | 2,000 ~ 2,800 | 1,200 × 800 | — | [가상] |
| AISLE-1 | 주 통로 | 0 ~ 29,000 | 0 ~ 2,000 | 바닥 표시 | — | [가상] (통로 위 2 m 안 장애물 없음 — 산업안전보건기준 규칙 제22조 [실제]) |
| DOOR-1 | 반입문 (동쪽 벽) | 29,000 | 0 ~ 2,600 | 폭 2,600 × 높이 2,600 이상 | — | [가상] (VF-2 운송 포장 2,570 × 2,510 × 2,570 [실제]이 지나가게. 옆에 사람 문) |
| EXIT-1 | 비상구 (서쪽 벽) | 0 | 500 ~ 1,500 | 폭 1,000 × 높이 2,000 | — | [가상] (모양 [실제: 제17조]) |

- 공장(BLDG)은 `plant_layout`, CMM-01 터치스크린과 WSH-01 구역 안 설비는 `equipment_part_shape`에 둔다.
- 재공 자리 ID(WIP-1~4)와 재공 위치 코드(WIP-10-20 등)는 **다른 키**다. 자리는 바닥 위치, 재공 위치는 한도·경고 기준을 가진 공정 사이 칸이다.

#### 5.A.10 `equipment_part_shape` 설비 부품 도형 — 최종본 새 엔터티

| 항목 | 내용 |
|---|---|
| 설명 | 설비 하나를 이루는 주요 부품의 단순 도형(상자·원기둥)과 설비 가운데 기준 상대 위치. 3D에서 설비를 실제 크기의 도형 조합으로 그린다 |
| 쓰는 요구사항 | FR-PRD-01-27 |
| 대략 건수 | 값 없음 (WSH-01 구역 안 5행 + CMM-01 화면 1행이 R1에 좌표가 있음. 다른 설비 부품은 R1 3장 크기만 있음) |
| 출처 | R1 3장·7장 "WSH-01 구역 안", 변경 명세 4장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| equipment_id | 설비 | 문자 | PK, FK | ○ | → equipment | — |
| shape_seq | 순번 | 정수 | PK | ○ | 1부터 | [제안] |
| part_code | 부품 코드 | 문자 | | — | R1에 ID가 있는 것만 (예: WSH-01-T 진동 바렐) | R1 7장 |
| part_name | 부품 이름 | 문자 | | ○ | 예: 진동 바렐, 작업대, 초음파 세척기, 헹굼조, 건조 자리, 터치스크린, 톱날, 테이블 | R1 3장 |
| shape_kind | 도형 종류 | 코드 | | ○ | 6.50 (상자 / 원기둥) | 변경 명세 4장 |
| size_x_mm | 가로 (원기둥은 지름) | 정수 | | ○ | mm | R1 3장 |
| size_y_mm | 세로 (원기둥은 지름) | 정수 | | 조건 | 상자면 필수. 모르면 비움 (예: CMM-01 화면 "본체 깊이 안") | R1 3장·7장 |
| size_z_mm | 높이 (원기둥은 두께·길이) | 정수 | | — | 바닥 표시만이면 비움 | R1 3장 |
| offset_x_mm | 상대 위치 X | 정수 | | 조건 | 부품 가운데 − 설비 가운데 (mm). R1에 좌표가 없는 부품은 3D를 만들 때 비율로 정함 [가상] | R1 7장, R1 8장 |
| offset_y_mm | 상대 위치 Y | 정수 | | 조건 | 같음 | R1 7장 |
| offset_z_mm | 바닥에서 높이 | 정수 | | ○ | 부품 바닥면 높이 (작업대 위 부품은 900) | R1 7장 |
| source_tag | 근거 | 코드 | | ○ | 6.41 | R1 7장 |

**R1에 좌표가 있는 부품** (상대 위치는 R1 7장 절대 좌표 − 설비 가운데로 계산, 단위 mm)

| 설비 | part_code | 부품 | 도형 | 크기 X × Y × Z | 상대 위치 (X, Y), 바닥 높이 | 근거 |
|---|---|---|---|---|---|---|
| WSH-01 | WSH-01-T | 진동 바렐 (KVF3급) | 상자 | 914 × 686 × 914 | (−943, −307), 0 | 크기 [참고] |
| WSH-01 | WSH-01-B | 작업대 | 상자 | 1,700 × 750 × 900 | (550, −275), 0 | [가상] |
| WSH-01 | WSH-01-U | 초음파 세척기 (CPX8800H-E급) | 상자 | 597 × 465 × 391 | (49, −275), 900 | 크기 [참고] |
| WSH-01 | WSH-01-R | 헹굼조 | 상자 | 597 × 465 × 391 | (696, −275), 900 | [가상] |
| WSH-01 | WSH-01-D | 건조 자리 | 상자 | 356 × 750 (작업대 위 표시) | (1,222, −275), 900 | [가상] |
| CMM-01 | — | 터치스크린 (본체 서쪽) | 상자 | 867 × (본체 깊이 안) | (−988, 0), — | [참고] |

- 크기만 있는 부품 예 (R1 3장): SAW-01 톱날 Ø315 × 1.7 mm 원기둥 [실제], VF-2 테이블 914 × 356 mm [실제], VF-2 앞문 열림 폭 939 mm [실제], VF-2 펜던트 높이 1,411 mm [실제]. 위치 값은 R1에 없어 3D를 만들 때 정한다 (근거 없는 좌표를 이 문서에서 만들지 않음).

### 5.B 생산

#### 5.B.1 `raw_material_lot` 원자재 로트

| 항목 | 내용 |
|---|---|
| 설명 | 입고된 봉재 묶음. 원자재 로트 1개 → 생산 로트 여러 개 |
| 쓰는 요구사항 | FR-PRD-05-01·02·03·09, FR-INV-01-03·04 |
| 대략 건수 | 주 3회 입고, 1회 약 360개분 (30일 건수는 설계서에 없음) |
| 출처 | 설계서 5.4, DOC-06 §7, 기획서 12.4 `raw_material_lot` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| material_lot_no | 원자재 로트 번호 | 문자 | PK | ○ | `MAT-2609-01` 형식 | 설계서 5.4 [가상] |
| item_no | 품목 | 문자 | FK | ○ | → inventory_item (RM-6061 6061-T6 봉재) | 설계서 5.14 |
| received_date | 입고일 | 날짜 | | ○ | 주 3회 | 설계서 5.4 |
| received_qty | 입고 수량 | 정수 | | ○ | 개분. 1회 약 360개분 | 설계서 5.4 [가상] |
| supplier_cert_no | 공급사 성적서 번호 | 문자 | | ○ | 가상 번호. 성적서 종류는 EN 10204 3.1. 성분·강도 값은 만들지 않음 | 설계서 5.4, DOC-06 §7 |
| heat_batch_no | 성적서 로트 코드 | 문자 | | — | 성적서의 히트·배치 번호. 입고품 표시와 대조 | DOC-06 §7 순서 3 [제안: 칸] |
| status | 원자재 로트 상태 | 코드 | | ○ | 6.9 (입고 검사 대기 / 사용 가능 / 입고 보류). **사용 가능일 때만** 생산 로트에 쓸 수 있다 | DOC-06 §7 순서 3·5 |

#### 5.B.2 `production_order` 생산 작업지시

| 항목 | 내용 |
|---|---|
| 설명 | 무엇을 몇 개 만들지 정한 지시. 교대·원자재 로트가 바뀌면 생산 로트 여러 개로 나뉜다 |
| 쓰는 요구사항 | FR-PRD-03-01·03·04, FR-PRD-05-02, FR-AST-01-02, FR-AST-02-06, FR-PRD-02-08 |
| 대략 건수 | 30일 약 110~130건 (하루 4~5건) |
| 출처 | 설계서 5.5, DOC-07 4.2, 기획서 12.4 `production_order` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| order_no | 작업지시 번호 | 문자 | PK | ○ | `PO-2609-001` 형식 | 설계서 5.5 |
| product_code | 제품 | 문자 | FK | ○ | → product (BRK-A100) | 설계서 5.5 |
| order_qty | 수량 | 정수 | | ○ | 24~60개, 중앙값 약 36개 | 설계서 5.5 (4TU [실제] 모양) |
| created_at | 만든 시각 | 날짜시각 | | ○ | — | [제안] |
| due_at | 납기 | 날짜시각 | | ○ | **납기 G2**: 주간 교대에 시작한 작업지시는 생산일 + 1일, 야간 교대에 시작한 작업지시는 생산일 + 2일, 일요일이면 월요일 (설계서 5.5 "투입 후 1~2일"을 구체화. 생산일 = 첫 OP-10 투입의 생산일). 출하 납기일(`shipment.due_date`)이 된다 | 설계서 5.5, R5 1.7 G1·G2 [가상] |
| status | 상태 | 코드 | | ○ | 6.7 (대기 → 생산 중 → 완료 / 취소) | 설계서 5.5, DOC-07 4.2 |
| started_at | 생산 시작 | 날짜시각 | | 조건 | 첫 로트의 OP-10 투입 시각. "생산 중"부터 필수 | [제안] |
| completed_at | 생산 완료 | 날짜시각 | | 조건 | "완료"면 필수 | [제안] |

#### 5.B.3 `production_lot` 생산 로트

| 항목 | 내용 |
|---|---|
| 설명 | 작업지시를 **OP-10 투입 기준**으로 ① 교대가 바뀌거나 ② 원자재 로트가 바뀌면 나눈 단위. 추적·보류·검사의 단위. 부품 일련번호는 없다 |
| 쓰는 요구사항 | FR-PRD-05-01~11, FR-PRD-02-03, FR-PRD-04-06, FR-AST-02-06, FR-MNT-02-09, FR-QLT-01-06, FR-INV-01-11·12 |
| 대략 건수 | 30일 약 130~160개 |
| 최종본 | 합격(해제 포함) 로트는 **완제품 재고**가 되고(합격 입고 거래, R-69), **출하 내역**(`shipment_line`)으로 나간다. 추적: 원자재 로트 → 생산 로트 → 검사 → 출하 (FR-PRD-05-01). 로트별 남은 완제품 수량은 계산 (R-69) |
| 출처 | 설계서 5.5, DOC-07 4.2, DOC-06 4.1, DOC-01 (로트 번호 예), 기획서 12.4 `production_lot` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| lot_no | 로트 번호 | 문자 | PK | ○ | `LOT-2609-041-1` = 작업지시 번호 뒷부분 + `-순번` | 설계서 5.5, DOC-01 |
| order_no | 작업지시 | 문자 | FK | ○ | → production_order. 작업지시 1 : 로트 1..N | 설계서 5.5 |
| lot_seq | 순번 | 정수 | | ○ | 1, 2 … (order_no, lot_seq)은 UK | 설계서 5.5 |
| input_shift_id | 투입 교대 | 문자 | FK | ○ | → shift. OP-10 투입이 모두 이 교대 안 (R-07) | 설계서 5.5·9장 |
| material_lot_no | 원자재 로트 | 문자 | FK | ○ | → raw_material_lot. 1개만 | 설계서 5.5, IATF FAQ [참고] |
| input_qty | 투입 수량 | 정수 | | ○ | 1~60. 같은 작업지시의 합 = 작업지시 수량 (취소된 작업지시는 ≤, R-08) | 설계서 5.5 |
| status | 로트 상태 | 코드 | | ○ | 6.8 (생산 중, 검사 대기, 판정 대기, 보류 검토, 합격, 보류, 해제, 폐기) | 설계서 5.5·5.15, DOC-06 4.1 |
| completed_qty | 완료 수량 | 정수 | | 조건 | **계산**: OP-50 공정 실적의 양품 + 재작업(GQ + RQ) 합 (R-05) | 설계서 5.5·9장, DOC-07 4.3 |
| scrap_qty | 폐기 수량 | 정수 | | — | 폐기 승인된 부품 수 | 설계서 5.5 "폐기 수량 일부" |
| expected_complete_at | 예상 완료 시각 | 날짜시각 | | — | **계산**. 납기보다 늦으면 로트 납기 지연 위험 알림. 계산 방법은 [선택 필요: 기술 회의] | DOC-07 8장, FR-AST-02-06 |
| judged_at | 판정 시각 | 날짜시각 | | 조건 | 측정 부품을 모두 잰 뒤 (R-25). 합격·보류 검토가 되면 필수. **합격이면 이 시각에 완제품 합격 입고** (해제 로트는 lot_hold.released_at) | 설계서 5.15, R5 표 A2·A3 |

#### 5.B.4 `operation_report` 공정 실적

| 항목 | 내용 |
|---|---|
| 설명 | 로트·공정·설비·작업자·교대마다 시작·끝과 수량을 남긴 기록. 지표·교대 실적·로트 추적의 바탕 |
| 쓰는 요구사항 | FR-PRD-01-15·20·21, FR-PRD-02-02, FR-PRD-03-01, FR-PRD-05-03·10·11, FR-ML-01-01 |
| 대략 건수 | 값 없음 (설계서에 건수 없음) |
| 출처 | 설계서 5.5 (4TU 칸 구성 [참고]), DOC-07 4.3, 기획서 12.4 `operation_report` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| op_report_id | 공정 실적 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| lot_no | 로트 | 문자 | FK | ○ | → production_lot | 설계서 5.5 |
| process_code | 공정 | 코드 | FK | ○ | → process | 설계서 5.5 |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment. 그 공정의 설비여야 함 | 설계서 5.5 |
| worker_user_id | 작업자 | 문자 | FK | ○ | → app_user (OPR) | 설계서 5.5 |
| shift_id | 처리 교대 | 문자 | FK | ○ | → shift. 그 공정을 처리한 교대 (로트의 투입 교대와 다를 수 있음). (lot_no, process_code, equipment_id, shift_id)는 UK [제안] | 설계서 5.5 |
| start_at | 시작 | 날짜시각 | | ○ | — | 설계서 5.5 |
| end_at | 끝 | 날짜시각 | | 조건 | 진행 중이면 비움. 시작보다 늦음 | 설계서 5.5 |
| pq | 생산 수량 | 정수 | | ○ | 양품 + 재작업 + 불량 (R-19) | DOC-07 4.3 [실제: ISO 22400 PQ] |
| gq | 양품 | 정수 | | ○ | 처음부터 기준에 맞은 부품 | DOC-07 4.3 |
| rq | 재작업 | 정수 | | ○ | 고쳐서 합격한 부품 | DOC-07 4.3 |
| sq | 불량 | 정수 | | ○ | 폐기한 부품. 약 80%는 OP-50에서 기록 | 설계서 5.5, DOC-07 4.3 |

#### 5.B.5 `wip_log` 재공 기록

| 항목 | 내용 |
|---|---|
| 설명 | 공정 사이 재공 수를 일정 간격으로 남긴 기록. 재공 표시·경고·병목 판단·다시 보기에 쓴다 |
| 쓰는 요구사항 | FR-PRD-01-03·06·07·08, FR-PRD-06-01·06, NFR-PERF-03 |
| 대략 건수 | 4곳 × 5분 간격 (시연 사건 전후 30분은 1분) |
| 출처 | 설계서 5.6·5.19, DOC-07 7.1, 기획서 12.4 `wip_log` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| buffer_code | 재공 위치 | 코드 | PK, FK | ○ | → wip_buffer | 설계서 5.6 |
| logged_at | 기록 시각 | 날짜시각 | PK | ○ | — | 설계서 5.6 |
| wip_qty | 재공 수 | 정수 | | ○ | 앞 공정 완료 수 − 다음 공정 투입 수. 0 이상, 한도 이하 (R-13) | 설계서 5.6, DOC-07 7.1 |
| soak_shelf_qty | 온도 맞춤 선반 수 | 정수 | | 조건 | WIP-40-50만. **재공(wip_qty)에 세지 않는다** | 설계서 5.15, DOC-06 §6 [가상] |
| interval_type | 기록 간격 | 코드 | | ○ | 5분 / 1분 (사건 전후 30분) | 설계서 5.19 |

#### 5.B.6 `bottleneck_log` 병목 기록

| 항목 | 내용 |
|---|---|
| 설명 | 병목 공정이 바뀐 때마다 1행. 다음 행까지를 한 병목 구간으로 보고 속도 손실 수량을 남긴다 |
| 쓰는 요구사항 | FR-PRD-01-08·09·16, FR-PRD-02-05, FR-PRD-04-03, FR-AST-02-05, FR-PRD-06-04 |
| 대략 건수 | 값 없음. 고장이 아닌 원인 ①~④가 30일에 5.18 빈도만큼 (① 주 1~2회, ② 4~6회, ③ 2~3회, ④ 매일) |
| 출처 | 설계서 5.10·5.18, DOC-07 5.3·7.3·7.4, 기획서 12.4 `bottleneck_log` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| bottleneck_log_id | 병목 기록 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| changed_at | 바뀐 시각 | 날짜시각 | | ○ | — | 설계서 5.18 |
| prev_process_code | 이전 병목 | 코드 | FK | — | → process. 첫 기록이면 비움 | 설계서 5.18 |
| new_process_code | 새 병목 | 코드 | FK | ○ | → process. 이전 병목과 달라야 함 | 설계서 5.18 |
| cause_code | 원인 번호 | 코드 | | ○ | 6.11 (① ② ③ ④ / 고장 / 기준 병목 복귀 [제안]) | 설계서 5.18, DOC-07 7.3 ⑥ |
| alarm_event_id | 고장 알람 | 정수 | FK | 조건 | 원인이 "고장"이면 필수. → alarm_event | [제안] |
| interval_end_at | 구간 끝 | 날짜시각 | | — | **계산**: 다음 병목 기록의 changed_at | [제안] |
| planned_qty | 계획 생산 수 | 소수 | | — | **계산**: 구간 시간 ÷ 3.5분 | DOC-07 5.3 |
| actual_qty | 실제 생산 수 | 소수 | | — | 구간 동안 OP-50 교대 실적과 같은 기준 | DOC-07 5.3 |
| failure_loss_qty | 고장 손실 수량 | 소수 | | — | 구간 안 정지의 고장 손실 합 | DOC-07 5.3 |
| speed_loss_qty | 속도 손실 수량 (추정) | 소수 | | — | **계산**: 계획 − 실제 − 고장 손실. 화면에 "추정" 표시 | 설계서 5.10, DOC-07 5.3 |

#### 5.B.7 `lot_hold` 로트 보류 기록

| 항목 | 내용 |
|---|---|
| 설명 | 로트 보류·해제·폐기의 사람 결정 기록 (누가·언제·왜). 보류는 검사 강화의 계기다 |
| 쓰는 요구사항 | FR-PRD-05-05·06·07·08, FR-QLT-01-05·07, FR-AST-COM-10, NFR-REL-03 |
| 대략 건수 | 30일 보류 2~3건, 해제 1~2건 |
| 출처 | 설계서 5.5 "로트 보류 기록", DOC-06 4.1·4.2·3.3. 기획서 12.4는 `production_lot` 안 칸 → 분리 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| hold_id | 보류 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| lot_no | 로트 | 문자 | FK | ○ | → production_lot | DOC-06 4.2 |
| trigger_type | 보류 계기 | 코드 | | ○ | 6.12 (AI 의심 로트 제안 / 검사 보류 검토 / 반장 판단) | DOC-06 3.3·4.2 |
| related_alarm_event_id | 계기 알람 | 정수 | FK | — | → alarm_event (정지 등급 알람 중 가공) | DOC-06 4.2 |
| related_tool_id | 계기 공구 | 문자 | FK | — | → tool (공구 수명 초과 중 가공) | DOC-06 4.2 |
| hold_reason | 보류 사유 | 긴 문자 | | ○ | 비면 보류 안 됨 | FR-PRD-05-06 |
| held_by | 보류한 사람 | 문자 | FK | ○ | → app_user, SUP 또는 MGR만. 비서는 안 됨 | 기획서 4.4·13.2 |
| held_at | 보류 시각 | 날짜시각 | | ○ | — | NFR-REL-03 |
| enhanced_next_lots | 강화할 다음 로트 수 | 정수 | | ○ | 원인이 공구이고 교체 완료면 1, 충돌·정지 등급·원인 모름이면 2 | DOC-06 3.3 [가상] |
| released_by | 해제한 사람 | 문자 | FK | 조건 | SUP 또는 MGR. 해제면 필수 | DOC-06 4.1 |
| released_at | 해제 시각 | 날짜시각 | | 조건 | 해제면 필수 | DOC-06 4.1 |
| scrap_proposed_qty | 폐기 제안 수량 | 정수 | | — | — | DOC-06 4.1 |
| scrap_proposed_by | 폐기 제안한 사람 | 문자 | FK | 조건 | SUP | DOC-06 4.1 |
| scrap_approved_by | 폐기 승인한 사람 | 문자 | FK | 조건 | **MGR만**. 승인 없으면 폐기 상태가 되지 않음 | DOC-06 4.1, FR-PRD-05-08 |
| scrap_approved_at | 폐기 승인 시각 | 날짜시각 | | 조건 | — | DOC-06 4.1 |
| normal_resumed_by | 보통 복귀 확인 | 문자 | FK | 조건 | SUP. 원인 조치 완료 + 강화 로트 모두 합격일 때 | DOC-06 3.3 |
| normal_resumed_at | 보통 복귀 시각 | 날짜시각 | | 조건 | — | DOC-06 3.3 |
| result | 결과 | 코드 | | ○ | 진행 중 / 해제 / 폐기 | DOC-06 4.1 |

### 5.C 설비·알람

#### 5.C.1 `alarm_master` 알람 코드집

| 항목 | 내용 |
|---|---|
| 설명 | 라인에서 쓰는 알람의 번호·이름·뜻·심각도·조치 담당. 지침카드와 질문 답변이 **번호로 정확히** 찾는다 |
| 쓰는 요구사항 | FR-MNT-02-01·02·03·04·06·07·08·13·14, FR-MNT-01-02, FR-AST-02-01, FR-AST-COM-16, NFR-DATA-07 |
| 대략 건수 | 31행 (OP-30 15 + 다른 공정 8 + OP-30 조작 안내 8 — DOC-02 3장) |
| 출처 | DOC-02, 설계서 5.8, 기획서 12.4 `alarm_master` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| alarm_code | 알람 번호 | 문자 | PK | ○ | 예: 992, 2075, 6302.00, 25050, WSH-01, MP-170, TempComp-202. 숫자가 아닌 것도 있어 문자. **WSH-01(알람)은 설비 ID WSH-01과 이름만 같다** | DOC-02 3장 |
| process_code | 적용 공정 | 코드 | FK | ○ | → process | DOC-02 3장 |
| name_en | 영문 이름 | 문자 | | — | 예: AMPLIFIER OVER CURRENT | DOC-02 4장 [실제] |
| name_ko | 한국어 이름 | 문자 | | ○ | **원문 그대로** (Haas 한국어 알람 목록, Siemens 한국어 매뉴얼). 예: "전류가 높은 증폭기(AMPLIFIER OVER CURRENT)" | DOC-02 1장, 용어집 1장 [실제] |
| original_desc | 원문 설명 | 긴 문자 | | — | 고치지 않고 옮김 | DOC-02 4장 [실제] |
| easy_desc | 쉬운 설명 | 긴 문자 | | — | 팀이 쓴 요약 | DOC-02 4장 |
| severity | 심각도 | 코드 | | ○ | 6.3 (정지 / 주의 / 조작 안내) | DOC-02 2장 [가상] |
| responder | 조치 담당 | 코드 | | ○ | 6.4 (작업자 / 보전 담당자) | DOC-02 3장 "누가" |
| responder_note | 조치 담당 보충 | 문자 | | — | 예: "작업자 (반복되면 보전 담당자)" (108), "작업자 → 계속되면 보전 담당자" (120) | DOC-02 3장 |
| lockout_level | 잠금·표지 판단 | 코드 | | ○ | 6.20. 정지 등급 = §2 전부, 2075 = 보충용 2점 잠금, 5303.00 = 1점 잠금 등 | DOC-05 §1·§2.4 |
| chain_rule | 연쇄 알람 순서 | 문자 | | — | 예: 992에 "108 → 994 → 992" (과부하 뒤 과전류는 충돌 신호) | 설계서 5.8, DOC-03 |
| doc02_section | DOC-02 절 | 문자 | | ○ | 예: §4.1 | DOC-02 |
| source_ref | 원문 위치 | 문자 | | — | 예: "Haas 알람 목록 CSV 1016행". **사람이 근거를 추적하는 용도만** — 비서 답·지침카드·화면에는 표시하지 않는다 (R-85) | DOC-02 4장, D-03 |
| is_virtual_code | 가상 번호 여부 | 참·거짓 | | ○ | WSH-01·WSH-02만 참 | DOC-02 3장, 설계서 9장 |

#### 5.C.2 `alarm_guide_map` 알람-고장 대응 연결

| 항목 | 내용 |
|---|---|
| 설명 | 알람 → 고장 대응 매뉴얼(DOC-03) 절. 지침카드 "먼저 할 일"과 출처 표시("고장 대응 매뉴얼 DOC-03 §2.1")의 근거. **원문 출처는 두지 않는다** (최종본에서 `original_source` 칸 삭제, R-85) |
| 쓰는 요구사항 | FR-MNT-02-05·12, FR-MNT-01-07, FR-MNT-03-05, FR-AST-02-18 (반복 알람 1·2단계에 붙이는 DOC-03 근거) |
| 대략 건수 | 알람마다 1행 이상 (DOC-02 3장 "고장 대응" 칸 31개) |
| 출처 | DOC-02 3장, 기획서 12.4 `alarm_guide_map` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| alarm_code | 알람 | 문자 | PK, FK | ○ | → alarm_master | DOC-02 3장 |
| seq | 순번 | 정수 | PK | ○ | 1부터. 한 알람에 고장 대응 절이 둘 이상일 수 있음 (예: 993 = 서보 앰프 + 축 서보 모터·케이블) | DOC-02 4.4 |
| doc_no | 사내 문서 | 문자 | FK | ○ | → internal_doc (DOC-03) | DOC-02 3장 |
| section | 절 | 문자 | | ○ | 예: §2.1, §3.5, §4. 출처 표시 = 사내 문서 이름 + 문서 번호 + §절 (R-85) | DOC-02 3장, D-03 |

#### 5.C.3 `alarm_event` 알람 이벤트

| 항목 | 내용 |
|---|---|
| 설명 | 설비에서 알람이 난 기록 1건. 상태 구간, 작업지시서, 간이 작업기록, 알림, 의심 로트의 출발점 |
| 쓰는 요구사항 | FR-MNT-02-01·09·10·13·14, FR-AST-02-01·03·11·18, FR-PRD-01-05, FR-PRD-04-04, FR-PRD-05-03·05, FR-PRD-06-04, FR-MNT-01-08, FR-MNT-03-01 |
| 대략 건수 | VF-2 1대당 조작 안내 하루 3~8건, 주의 하루 0~2건, 정지 30일 2~4건. 다른 공정은 공정당 30일 0~4건 (설계서 5.8 표). 반복 2075는 VF2-02 9월 마지막 주 3번 + 9월 초 1번 (1단계 시연 사례). **반복 알람 2단계 사례 1건 [가상]**: VF2-02 알람 108 — 9/8·9/9·9/10 → 1단계, 9/14 재발 → 2단계, 9/15 원인 점검 작업기록서 확정 (설계서_최종본 5.8) |
| 출처 | 설계서 5.8, 기획서 12.4 `alarm_event` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| alarm_event_id | 알람 이벤트 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| equipment_id | 발생 설비 | 문자 | FK | ○ | → equipment. 알람의 적용 공정 설비여야 함 | 설계서 5.8 |
| alarm_code | 알람 번호 | 문자 | FK | ○ | → alarm_master | 설계서 5.8 |
| severity_at_event | 발생 때 심각도 | 코드 | | ○ | 발생 순간의 alarm_master.severity를 옮겨 둔다 (코드집이 개정돼도 과거 기록이 바뀌지 않게) | [제안] |
| occurred_at | 발생 시각 | 날짜시각 | | ○ | — | 설계서 5.8 |
| cleared_at | 해제 시각 | 날짜시각 | | — | 정지 등급이면 DOWN 구간 끝과 같음 | 설계서 5.7 |
| lot_no | 가공 중 로트 | 문자 | FK | — | → production_lot. 지침카드 "생산 영향", 의심 로트 제안에 씀 | 설계서 5.11, FR-MNT-02-09 |
| prev_alarm_event_id | 선행 알람 | 정수 | FK | — | → alarm_event (자기 참조). 예: 992의 선행 = 994, 994의 선행 = 108 | 설계서 5.8 |
| is_injected | 사건 넣기 여부 | 참·거짓 | | ○ | 시연 실시간 모드에서 넣은 알람이면 참 | 설계서 7장, NFR-DATA-10 |
| scenario_code | 시연 사건 | 코드 | | 조건 | 6.40 (S1~S6). is_injected 참이면 필수 | 설계서 7장 |

#### 5.C.4 `equipment_state_log` 설비 상태 기록

| 항목 | 내용 |
|---|---|
| 설명 | 설비 상태가 바뀔 때마다 1행 (구간). RUN이 아닌 구간에는 정지 사유가 붙는다. 가동률·MTTR·손실·3D 색의 바탕 |
| 쓰는 요구사항 | FR-PRD-01-03·04·05·16·17·18·19·20·22·26, FR-MNT-04-07, FR-PRD-02-02·04, FR-PRD-06-01, NFR-DATA-05·11 |
| 대략 건수 | VF-2 하루 상태 변화 60~120회 (설계서 5.7, NIST 98~101회 [실제]) |
| 출처 | 설계서 5.7·5.10, DOC-07 2.2·5.1·5.3, 기획서 12.4 `equipment_state_log` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| state_log_id | 상태 기록 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment. 한 설비의 구간끼리 겹치지 않음 (R-04) | 설계서 9장 |
| state_code | 상태 | 코드 | | ○ | 6.1 (RUN, IDLE, BLOCKED, SETUP, DOWN, MAINT) | DOC-07 2.2 |
| mtconnect_execution | 실제 데이터 값 | 코드 | | — | 6.2 (ACTIVE / READY / STOPPED). SETUP·MAINT는 비움 (작업자 입력·정비 기록) | DOC-07 2.2 [실제] |
| start_at | 구간 시작 | 날짜시각 | | ○ | — | 설계서 5.7 |
| end_at | 구간 끝 | 날짜시각 | | 조건 | 지금 구간이면 비움 | 설계서 5.7 |
| duration_min | 구간 길이 | 소수 | | — | **계산**: end_at − start_at (분) | [제안] |
| warn_marker | 주의 표시 (▲) | 참·거짓 | | ○ | 주의 등급 알람이 떠 있으면 참. 상태 색은 그대로 | DOC-07 2.2, FR-PRD-01-05 |
| reason_suggested_code | 추천 정지 사유 | 코드 | FK | — | → downtime_reason. 비서의 추천 (AI비서 초안) | 기획서 4.4, FR-PRD-01-19 |
| reason_code | 정지 사유 | 코드 | FK | 조건 | → downtime_reason. **RUN이면 비움, 아니면 사유 1개** (R-21). 확정 전에는 입력값 | DOC-07 5.1, FR-PRD-01-18 |
| reason_status | 사유 상태 | 코드 | | 조건 | 6.6 (추천 / 입력 / 확정). RUN이면 비움 | 기획서 13.2 [제안: 코드] |
| reason_entered_by | 사유 입력자 | 문자 | FK | — | → app_user, OPR 또는 MNT | 기획서 13.2 |
| reason_confirmed_by | 사유 확정자 | 문자 | FK | 조건 | → app_user, **SUP만**. 확정이면 필수 | 기획서 13.2, FR-PRD-01-19 |
| reason_confirmed_at | 사유 확정 시각 | 날짜시각 | | 조건 | — | NFR-REL-03 |
| alarm_event_id | 멈추게 한 알람 | 정수 | FK, UK | 조건 | → alarm_event. **DOWN이면 필수** (정지 등급 알람 1건 = DOWN 1구간). 주의 등급으로 멈춘 IDLE + ▲에도 넣음 | 설계서 9장, DOC-07 2.2 |
| pm_record_id | 정비 기록 | 정수 | FK, UK | 조건 | → pm_record. MAINT면 필수 | 설계서 5.7 |
| stop_loss_qty | 정지 손실 수량 (추정) | 소수 | | — | **계산**: 구간 길이 ÷ 그 설비 기준 사이클 시간. 계획(PLANNED) 그룹은 계산하지 않음. FAILURE 그룹의 합이 "고장 손실" | 설계서 5.10, DOC-07 5.3 |

#### 5.C.5 `downtime_reason` 정지 사유 코드

| 항목 | 내용 |
|---|---|
| 설명 | RUN이 아닌 시간에 붙이는 사유. 5개 그룹 18개 코드 |
| 쓰는 요구사항 | FR-PRD-01-05·17·18·19, FR-PRD-04-03 |
| 대략 건수 | 18행 (DOC-07 5.1). 하루 건수(라인): 고장 1~3, 자재·흐름 3~6, 준비 4~6, 조작 3~8 (설계서 5.10) |
| 출처 | 설계서 5.10, DOC-07 5.1 (코드 번호 [가상]), 기획서 12.4 `downtime_reason` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| reason_code | 사유 코드 | 코드 | PK | ○ | F01~F06, M01~M03, S01~S03, O01~O03, P01~P03 (6.5) | DOC-07 5.1 [가상] |
| reason_group | 그룹 | 코드 | | ○ | FAILURE 고장 / MATERIALS 자재·흐름 / SETUP 준비 / OPERATION 조작 / PLANNED 계획 | DOC-07 5.1 [참고: 벽돌 라인] |
| reason_name | 사유 | 문자 | | ○ | 예: 서보·앰프, 뒤 공정 막힘, 작업지시 교체 (로트 교체) | DOC-07 5.1 |
| usual_state | 보통 상태 | 코드 | | ○ | 6.1의 상태 (F04·F05는 주의 등급이면 IDLE + ▲) | DOC-07 5.1 |
| six_loss | 6대 로스 | 문자 | | — | 예: 고장 정지 로스, 준비 교체 로스, 순간 정지 로스 | DOC-07 5.1·5.2 [참고: NCS] |
| is_loss | 손실로 셈 | 참·거짓 | | ○ | PLANNED 그룹(P01~P03)만 거짓 | DOC-07 5.1 "손실로 보지 않음" |

#### 5.C.6 `sensor_item` 센서 항목

| 항목 | 내용 |
|---|---|
| 설명 | OP-30에서 기록하는 센서 항목과 [참고] 정상 범위. **알람 기준값 칸은 두지 않는다** |
| 쓰는 요구사항 | FR-PRD-01-12·14, NFR-DATA-09, FR-AST-COM-06 |
| 대략 건수 | 7행 (DOC-07 3장의 5종, X·Y·Z축 부하를 따로 셈) |
| 출처 | 설계서 5.9, DOC-07 3장. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| sensor_code | 센서 코드 | 코드 | PK | ○ | SpindleLoadPct, SpindleMotorTemp, AirPressure, Xload, Yload, Zload, DcVolt (6.38) | DOC-07 3장 [실제: Haas 원시 표본 이름] |
| sensor_name | 센서 이름 | 문자 | | ○ | 주축 부하, 주축 모터 온도, 공기 압력, X·Y·Z축 부하, 직류 버스 전압 | DOC-07 3장 |
| unit | 단위 | 문자 | | ○ | %, ℃, psi, V. 공기 압력은 화면에 "psi (bar)" | DOC-07 3장, 용어집 규칙 5 |
| normal_min | 정상 범위 아래 | 소수 | | ○ | 예: 주축 모터 온도 28 | DOC-07 3장 [참고] |
| normal_max | 정상 범위 위 | 소수 | | ○ | 예: 주축 모터 온도 42 | DOC-07 3장 [참고] |
| normal_median | 중앙값 | 소수 | | — | 주축 부하 38, 공기 압력 105.3, 직류 버스 전압 317 | DOC-07 3장 [참고] |
| linked_alarm_code | 연결 알람 | 문자 | FK | — | → alarm_master. 174, 254, 120, 108 (축 부하). 직류 버스 전압은 비움 | DOC-07 3장 |

#### 5.C.7 `sensor_sample` 센서 값

| 항목 | 내용 |
|---|---|
| 설명 | OP-30 설비의 센서 값. 하단 패널 추세와 다시 보기에 쓴다 |
| 쓰는 요구사항 | FR-PRD-01-12·14, FR-PRD-06-02·06, NFR-PERF-03 |
| 대략 건수 | 평소 1분 평균, 알람·병목 전후 30분은 1초 간격 (30일 전부를 1초로 만들지 않음) |
| 출처 | 설계서 5.9·5.19, DOC-07 3장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| equipment_id | 설비 | 문자 | PK, FK | ○ | → equipment. VF2-01·02만 (has_sensor 참) | DOC-07 3장 |
| sensor_code | 센서 | 코드 | PK, FK | ○ | → sensor_item | DOC-07 3장 |
| sampled_at | 시각 | 날짜시각 | PK | ○ | — | 설계서 5.19 |
| value | 값 | 소수 | | ○ | sensor_item 단위 | 설계서 5.9 |
| interval_type | 기록 간격 | 코드 | | ○ | 1분 평균 / 1초 | 설계서 5.19 |

### 5.D 정비

#### 5.D.1 `maintenance_work_order` 정비 작업지시서

| 항목 | 내용 |
|---|---|
| 설명 | 해야 할 정비 일을 작업 순서·안전 절차·담당으로 문서화한 것. **OP-30에서만** 만든다. AI비서 초안 → MNT 수정 → SUP 담당 지정·승인. 최종본에서 **계기** 칸을 더했다: 정지 등급 알람 / 반복 알람 2단계(원인 점검) / 예방 정비 중 이상 |
| 쓰는 요구사항 | FR-MNT-03-01~14, FR-MNT-02-11, FR-AST-02-10·18, FR-AST-03-01·07, FR-PRD-02-06, FR-PRD-04-05, FR-AST-01-02 |
| 대략 건수 | 30일 **약 5~9건** (OP-30 정지 등급 알람 짝 4~8건 + 반복 알람 2단계 원인 점검 1건 — 설계서 5.8 빈도로 계산, 설계서_최종본 5.11. 작업기록서와 같은 수) |
| 출처 | 설계서 5.11, 기획서 MNT-03·5.1·5.2, DOC-05 §7, 기획서 12.4 `maintenance_work_order` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| wo_no | 작업지시서 번호 | 문자 | PK | ○ | `MW-0901` 형식 | 설계서 5.11 |
| trigger_kind | 계기 | 코드 (여러 값) | | ○ | 6.42 (정지 등급 알람 / 반복 알람 2단계 / 예방 정비 중 이상). **1개 이상** 적는다. 계기마다 맞는 칸을 채운다: 정지 등급 알람 → alarm_event_id, 반복 알람 2단계 → trigger_notification_id, 예방 정비 중 이상 → pm_record_id. **OP-30 정지 등급 알람이 동시에 반복 알람 2단계이면 작업지시서는 1개만** 만들고 두 계기를 함께 적으며(alarm_event_id와 trigger_notification_id 둘 다 채움), 작업 순서 끝에 원인 점검 단계를 덧붙인다 [가상] (R-71). 여러 값을 한 칸에 둘지 따로 표로 둘지는 물리 ERD [선택 필요: 기술 회의] | D-09, 2026-10-07 총괄 정정, FR-MNT-03-01, R4 3.2 |
| alarm_event_id | 알람 | 정수 | FK, UK | 조건 | → alarm_event. 계기 = 정지 등급 알람이면 필수. OP-30 **정지 등급** 알람만, 알람 1건에 1건 (R-02) | 설계서 5.11, 기획서 5.2 |
| pm_record_id | 예방 정비 기록 | 정수 | FK, UK | 조건 | → pm_record. 계기 = 예방 정비 중 이상이면 필수 (정비 중 "이상 있음") | DOC-04 5장 |
| trigger_notification_id | 반복 알람 2단계 알림 | 정수 | FK, UK | 조건 | → notification (규칙 REPEAT_ALARM_2). 계기 = 반복 알람 2단계면 필수. **OP-30 설비만** (R-71). 원인 점검 작업지시서 AI비서 초안: DOC-03 해당 절의 보전 줄(★ 아닌 줄)과 아직 확인 안 된 원인을 작업 순서로 | R4 3.2, FR-AST-02-18 |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment. VF2-01·VF2-02만 | 기획서 5.2 |
| lot_no | 로트 | 문자 | FK | — | → production_lot | 설계서 5.11 |
| created_at | 만든 시각 | 날짜시각 | | ○ | 자동 | FR-MNT-03-03 |
| title | 제목 | 문자 | | ○ | 비서가 지침카드에서 씀 | FR-MNT-03-04 |
| symptom | 증상 | 긴 문자 | | ○ | 비서가 지침카드에서 씀 | FR-MNT-03-04 |
| status | 상태 | 코드 | | ○ | 6.13 (AI비서 초안 → 수정 중 → 승인 → 진행 중 → 완료 / 취소). 과거 기록은 모두 완료 | 기획서 MNT-03, 설계서 5.11 |
| assignee_user_id | 담당 보전 담당자 | 문자 | FK | 조건 | → app_user, MNT. **반장이 지정**. 비면 승인 안 됨 | FR-MNT-03-14 |
| approved_by | 승인자 | 문자 | FK | 조건 | → app_user, SUP (MGR 대리 승인 가능). 비서는 안 됨 | 기획서 13.1, FR-MNT-03-14 |
| approved_at | 승인 시각 | 날짜시각 | | 조건 | 승인 대기 시간(30분 참고 / 2시간 주의 알림) 계산의 끝 | FR-AST-02-10 |
| cancelled_by | 취소한 사람 | 문자 | FK | 조건 | → app_user, MGR | 기획서 13.1 |
| cancelled_at | 취소 시각 | 날짜시각 | | 조건 | — | 기획서 13.1 |
| cancel_reason | 취소 사유 | 긴 문자 | | 조건 | 취소면 필수 [제안] | NFR-REL-03 |
| safety_block_doc_rev | 안전 블록 문서·개정 | 문자 | | ○ | 예: "DOC-05 Rev.1". 6+3단계·보호구 고정 서식이 붙었다는 표시. 누구도 지울 수 없음 | DOC-05 §7, FR-MNT-03-07 |
| has_high_voltage_notice | 고전압 대기 문구 | 참·거짓 | | ○ | OP-30 설비면 참 (고정 문구) | FR-MNT-03-08, DOC-05 §4 |
| completed_at | 완료 시각 | 날짜시각 | | 조건 | 완료면 필수 | [제안] |
| current_version | 현재 버전 | 정수 | | ○ | 0 = AI비서 초안. document_revision의 가장 큰 version_no | 기획서 4.5 |

- 차단 지점은 `equipment_id` → `isolation_point`에서 가져온다. 문서를 확정한 뒤 차단 지점 표가 바뀌어도 그 문서 내용은 `document_revision.content_snapshot`에 남는다.

#### 5.D.2 `work_order_step` 작업지시서 작업 순서

| 항목 | 내용 |
|---|---|
| 설명 | 작업지시서의 작업 순서 단계. 비서가 DOC-03 점검 순서로 정리하고, 작업기록서에서 단계마다 체크한다 |
| 쓰는 요구사항 | FR-MNT-03-05, FR-MNT-05-04 |
| 대략 건수 | 값 없음 (작업지시서마다 여러 단계) |
| 출처 | 기획서 MNT-03 "작업 순서", 설계서 5.11. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| wo_no | 작업지시서 | 문자 | PK, FK | ○ | → maintenance_work_order | — |
| step_no | 단계 번호 | 정수 | PK | ○ | 1부터 | [제안] |
| step_text | 작업 순서 | 긴 문자 | | ○ | DOC-03 점검 순서 [실제]를 단계로 정리 | 설계서 5.11 |
| source_section | 출처 | 문자 | | ○ | 단계마다 DOC-03 절 (예: "DOC-03 §2.1"). **원문 출처는 넣지 않는다** (R-85) | FR-MNT-03-05, D-03 |

- 잠금·표지 6+3단계는 이 엔터티에 넣지 않는다. 고정 서식이라 코드 목록 6.19로 둔다 (FR-AST-COM-13).

#### 5.D.3 `work_order_part` 작업지시서 예상 부품

| 항목 | 내용 |
|---|---|
| 설명 | 비서가 제안한 예상 부품·공구. 화면에는 현재 재고 수량을 함께 보인다 |
| 쓰는 요구사항 | FR-MNT-03-12 |
| 대략 건수 | 값 없음 |
| 출처 | 기획서 MNT-03 "예상 부품·공구". 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| wo_no | 작업지시서 | 문자 | PK, FK | ○ | → maintenance_work_order | — |
| item_no | 재고 품목 | 문자 | PK, FK | ○ | → inventory_item. 재고 품목에 없는 이름은 넣을 수 없음 | FR-MNT-05-07 |
| suggested_qty | 제안 수량 | 소수 | | ○ | 0보다 큼 | [제안] |

#### 5.D.4 `work_record` 작업기록서

| 항목 | 내용 |
|---|---|
| 설명 | 실제로 한 정비 기록. **작업기록서**(작업지시서 1건마다 1건)와 **간이 작업기록**(주의 등급 알람, 다른 공정 알람마다 1건, 그리고 최종본에서 **다른 공정 반복 알람 2단계의 원인 점검 요청마다 1건**) 두 종류 |
| 쓰는 요구사항 | FR-MNT-05-01~13, FR-PRD-01-22·26, FR-MNT-02-10, FR-MNT-03-11, FR-AST-02-03·18, FR-AST-03-01, FR-PRD-02-06, FR-PRD-04-05 |
| 대략 건수 | 작업기록서 30일 **약 5~9건** (작업지시서와 같은 수, 설계서_최종본 5.11). 간이 작업기록은 주의 등급 알람 수만큼 (설계서 5.8 빈도) |
| 출처 | 설계서 5.11, 기획서 MNT-05·5.2, 기획서 12.4 `work_record` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| record_no | 기록 번호 | 문자 | PK | ○ | 작업기록서 `MR-0901`, 간이 작업기록 `MR-S-0901` | 설계서 5.11 |
| record_type | 종류 | 코드 | | ○ | 6.14 (작업기록서 / 간이 작업기록) | 설계서 5.11 |
| wo_no | 작업지시서 | 문자 | FK, UK | 조건 | → maintenance_work_order. **작업기록서면 필수**, 간이면 비움 | 설계서 5.11 |
| alarm_event_id | 알람 | 정수 | FK, UK | 조건 | → alarm_event. **간이면 필수** (원인 점검 간이 기록은 비움). 작업기록서는 작업지시서의 알람과 같음 (반복 알람 2단계 작업지시서는 비움) | 기획서 5.2 |
| cause_check_notification_id | 원인 점검 요청 알림 | 정수 | FK, UK | 조건 | → notification (규칙 CAUSE_CHECK_REQUEST). **다른 공정(OP-10·20·40·50) 반복 알람 2단계의 원인 점검 간이 기록이면 필수**, 그 밖은 비움. 확정하면 2단계 알림이 자동 처리 (R-70) [제안: 칸] | R4 3.2, D-09, FR-AST-02-18 |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment. 작업지시서·알람과 같음 | FR-MNT-05-03 |
| lot_no | 로트 | 문자 | FK | — | → production_lot | FR-MNT-05-03 |
| cause | 원인 | 긴 문자 | | 조건 | 고장 대응 안내에 **적힌 원인** 중에서. AI비서 초안 → MNT 확정. 작업기록서 확정 때 필수 | 설계서 5.11 [실제 원인] |
| action | 조치 | 긴 문자 | | ○ | 같은 안내의 조치 문장. 간이는 작업자가 고른 조치 | 설계서 5.11 |
| worker_memo | 작업자 메모 | 긴 문자 | | — | 일부러 대충 쓴 말투 (AI비서 초안 정리 시험용) | 설계서 5.11 |
| start_at | 시작 시각 | 날짜시각 | | ○ | — | FR-MNT-05-08 |
| end_at | 끝 시각 | 날짜시각 | | 조건 | 확정 때 필수 | FR-MNT-05-08 |
| repair_min | 수리 시간 | 소수 | | 조건 | 분. 작업기록서는 **DOWN 구간 길이와 같음 (오차 1분 이내)**, 30~180분 | 설계서 5.11·9장 |
| safety_block_required | 잠금·표지 블록 필요 | 참·거짓 | | ○ | 작업기록서, 다른 공정 정지 등급의 간이 기록, DOC-05 §2.4 "보충용 2점 잠금" 줄이 붙는 간이 기록(예: 2075)이면 참 → 9개 체크 필수 | FR-MNT-05-05·13·15, DOC-05 §2.4·§7 |
| status | 상태 | 코드 | | ○ | 6.15. 과거 기록은 모두 확정 | 기획서 5.1, 설계서 5.16 |
| confirmed_by | 확정자 | 문자 | FK | 조건 | 작업기록서 = MNT. 간이: 주의 등급 = OPR 또는 MNT, **다른 공정 정지 등급 = MNT만** (OPR은 입력·저장만), **원인 점검 간이 기록 = MNT** (원인 점검 요청을 받는 사람, R4 3.2) | 기획서 13.1, FR-MNT-05-13, UI설계서 9장 #5, DOC-02 3장 "누가" |
| confirmed_at | 확정 시각 | 날짜시각 | | 조건 | 확정 뒤 MTTR·정지 원인 다시 계산, 재고 차감 | FR-MNT-05-10 |
| checked_by | 확인자 | 문자 | FK | — | SUP만 (작업기록서) | FR-MNT-05-09 |
| checked_at | 확인 시각 | 날짜시각 | | — | — | FR-MNT-05-09 |
| current_version | 현재 버전 | 정수 | | ○ | 0 = AI비서 초안 (간이 작업기록은 AI비서 초안이 없어 0 = 사람이 처음 저장한 것) | 기획서 4.5, FR-AST-03-02 |

#### 5.D.5 `work_record_check` 작업기록서 체크

| 항목 | 내용 |
|---|---|
| 설명 | 작업기록서(잠금·표지를 하는 간이 작업기록 포함)의 체크칸: 작업 순서 단계 체크, 잠금·표지 9단계 체크 |
| 쓰는 요구사항 | FR-MNT-05-04·05·15, FR-MNT-03-06, FR-PRD-02-09, NFR-SAFE-03 |
| 대략 건수 | 작업기록서마다 작업 순서 단계 수 + 9 |
| 출처 | 기획서 MNT-05, 설계서 5.11 "작업 전 6단계, 해제 3단계 모두 체크", DOC-05 §2·§7. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| record_no | 작업기록서 | 문자 | PK, FK | ○ | → work_record | — |
| check_seq | 순번 | 정수 | PK | ○ | 1부터 | [제안] |
| check_kind | 체크 종류 | 코드 | | ○ | STEP 작업 순서 / LOTO 잠금·표지 | [제안] |
| wo_no | 작업지시서 | 문자 | FK | 조건 | STEP이면 필수. (wo_no, step_no) → work_order_step | FR-MNT-05-04 |
| step_no | 작업 순서 단계 | 정수 | FK | 조건 | STEP이면 필수 | FR-MNT-05-04 |
| loto_step_code | 잠금·표지 단계 | 코드 | | 조건 | LOTO면 필수. 6.19 (6.1~6.6, 7.1~7.3). 한 기록에 단계마다 1행 | DOC-05 §2.1·2.2 [실제 제목] |
| is_checked | 체크 | 참·거짓 | | ○ | — | — |
| checked_by | 체크한 사람 | 문자 | FK | 조건 | 체크면 필수 | NFR-REL-03 |
| checked_at | 체크 시각 | 날짜시각 | | 조건 | 6.4 체크 뒤 7.3 체크 전이면 "잠금 중" (인계 사항 맨 위, R-53) | DOC-05 §2.3 |

#### 5.D.6 `work_record_part` 작업기록서 사용 부품

| 항목 | 내용 |
|---|---|
| 설명 | 정비에 쓴 부품·공구. 작업기록서 확정 때 재고 사용 거래가 생긴다 |
| 쓰는 요구사항 | FR-MNT-05-02·07·10, FR-INV-01-02 |
| 대략 건수 | 값 없음 |
| 출처 | 설계서 5.11 "사용 부품: 재고 품목에서 고름", 기획서 MNT-05. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| record_no | 작업기록서 | 문자 | PK, FK | ○ | → work_record | — |
| item_no | 재고 품목 | 문자 | PK, FK | ○ | → inventory_item. 재고 품목에 없는 이름은 넣을 수 없음 | FR-MNT-05-07 |
| qty | 수량 | 소수 | | ○ | 0보다 큼. 품목 단위 (개, L) | 설계서 5.14 |
| proposed_by_kind | 작성 주체 | 코드 | | ○ | 6.18 (AI / 사람). 메모 정리로 비서가 넣었는지 | FR-MNT-05-02 |

#### 5.D.7 `pm_task` 예방 정비 항목

| 항목 | 내용 |
|---|---|
| 설명 | 설비별 예방 정비 항목과 주기. MNT-04 달력이 이것으로 만들어진다 |
| 쓰는 요구사항 | FR-MNT-04-01·02·03·04·09, FR-AST-02-08, FR-AST-01-02 |
| 대략 건수 | VF-2 한 대당 24항목 (Haas 정비 일정 58항목 중 기본 사양), 다른 공정은 공정당 1~2항목 (DOC-04 2장·3장) |
| 출처 | 설계서 5.12, DOC-04 2장·3장·5장, 기획서 12.4 `pm_task` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| pm_task_id | 정비 항목 ID | 문자 | PK | ○ | `PM-{설비 ID}-{DOC-04 절}-{두 자리 순번}` (예: PM-VF2-02-2.3-01). 순번은 그 절 표의 위에서부터. **[가상] 팀 확정** — DOC-04 5장 "항목 코드" 줄에 같은 규칙을 넣음 | [가상] DOC-04 5장 |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment | DOC-04 5장 |
| doc04_section | DOC-04 절 | 문자 | | ○ | 예: 2.3 (매월), 3.1 | DOC-04 5장 "절 번호 함께" |
| area | 부위 | 문자 | | — | 예: 축 윤활, 공구 교환장치 | DOC-04 2장 |
| item_name | 항목 이름 | 문자 | | ○ | 원문을 그대로 옮긴 이름. 예: "윤활유 저장소 양 점검·보충" | DOC-04 2장 [실제] |
| cycle_code | 주기 | 코드 | | ○ | 6.22 (매일, 매주, 매월, 6개월, 1년, 필요할 때, 8시간 사용마다) | DOC-04 |
| lockout_level | 잠금·표지 판단 | 코드 | | ○ | 6.20. 예: 축 윤활유 보충 = 보충용 2점 잠금 | DOC-05 §2.4, FR-MNT-04-09 |
| default_role | 하는 사람 | 코드 | | ○ | 매일·매주·절삭유 보충 = 작업자, 잠금·표지 ○ 작업과 매월 이상 = 보전 담당자 | DOC-04 1장 [가상] |
| default_item_no | 기본 소모품 | 문자 | FK | — | → inventory_item. 예: CS-WLUB | DOC-04 2장 "쓰는 소모품" |
| on_calendar | 달력 등록 | 참·거짓 | | ○ | 교대 시작 점검표 줄은 거짓 (매일 표에서 RD0080 2개만 달력) | DOC-04 2.1 |
| source_tag | 근거 구분 | 코드 | | ○ | 6.41 ([실제] / [참고] / [가상]). 다른 공정 항목은 반드시 표시 | FR-MNT-04-03 |
| next_due_date | 다음 기한 | 날짜 | | ○ | **계산**: 마지막 실시일 + 주기. 하루 전 참고, 넘기면 주의 알림 | DOC-04 5장 |

#### 5.D.8 `pm_record` 예방 정비 실시 기록

| 항목 | 내용 |
|---|---|
| 설명 | 예방 정비를 한 기록. 확정하면 쓴 소모품이 재고에서 빠진다. MAINT 상태 구간과 이어진다 |
| 쓰는 요구사항 | FR-MNT-04-05·06·07·08·10, FR-INV-01-02, FR-AST-03-01 |
| 대략 건수 | 매일·매주 항목 90~95% 제때 실시, 매월 일부 늦음. 시연용 기한 넘긴 항목 2~3개 (건수 자체는 값 없음) |
| 출처 | 설계서 5.12, DOC-04 5장, 기획서 12.4 `pm_record` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| pm_record_id | 실시 기록 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| pm_task_id | 정비 항목 | 문자 | FK | ○ | → pm_task | DOC-04 5장 |
| due_date | 예정일 | 날짜 | | ○ | 달력 기한 (자동) | DOC-04 5장 |
| done_at | 실시 시각 | 날짜시각 | | ○ | — | DOC-04 5장 |
| done_by | 실시자 | 문자 | FK | ○ | → app_user. 실제로 한 사람. 기본은 기록자와 같음. **작업자가 하는 항목**(DOC-04 1장: 매일·매주 점검, 절삭유 보충)은 OPR [제안] | DOC-04 1장·5장, FR-MNT-04-05, UI설계서 9.3 #7 |
| recorded_by | 기록자 | 문자 | FK | ○ | → app_user, **MNT만** (기록 저장은 MNT, 기획서 13.2 OPR "—") [제안] | 기획서 13.2, FR-MNT-04-05 |
| result | 결과 | 코드 | | ○ | 6.23 (정상 / 보충·교체함 / 이상 있음) | DOC-04 5장 |
| measured_value | 측정값 | 소수 | | — | 잰 값이 있는 항목만 (절삭유 농도 %, 공기 압력 등) | DOC-04 5장 |
| measured_unit | 측정 단위 | 문자 | | 조건 | 측정값이 있으면 필수 | DOC-04 5장 |
| memo | 메모 | 긴 문자 | | — | 이상 내용, 사진(사진 저장은 [선택 필요: 기술 회의]) | DOC-04 5장 |
| is_on_time | 기한 안 실시 | 참·거짓 | | ○ | **계산**: 실시일 ≤ 예정일. 제때 실시율 계산에 씀 | DOC-07 6.2, FR-MNT-04-08 |
| status | 상태 | 코드 | | ○ | 작성 중 / 확정 (확정 뒤 고치면 새 버전 + 사유, 다시 확정 없음 — R-35) | DOC-04 5장 "확정한다" |
| current_version | 현재 버전 | 정수 | | ○ | 0 = 사람이 처음 저장한 것 (AI비서 초안 없음). **수정 이력 대상** (문서 종류 PM_RECORD, 6.17) [제안] | DOC-04 5장 "고친 기록은 수정 이력(AST-03)에 남는다", FR-AST-03-01 |

### 5.E 공구·재고

#### 5.E.1 `tool_type` 공구 종류

| 항목 | 내용 |
|---|---|
| 설명 | OP-30 공구 5종의 사용량 단위·부품당 사용량·수명 한도. 공구 품목(재고)과 1:1 |
| 쓰는 요구사항 | FR-ML-01-01·02, FR-INV-01-03 |
| 대략 건수 | 5행 |
| 출처 | 설계서 5.13, DOC-07 9장. 엔터티는 [제안] (기획서 12.4 `tool` 안 칸을 분리) |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| item_no | 공구 품목 | 문자 | PK, FK | ○ | → inventory_item. TL-TAP6, TL-DR50, TL-BB45, TL-EM10, TL-FM50 | 설계서 5.14 |
| usage_unit | 사용량 단위 | 코드 | | ○ | 6.24 (HOLES 구멍 수 / FEED 이송 시간 분) | 설계서 5.13 [실제: Haas ATM] |
| usage_per_part | 부품 1개당 사용량 | 소수 | | ○ | 탭 4, 드릴 4, 보링 1 (구멍) / 엔드밀 2.5, 페이스밀 0.5 (분) | 설계서 5.13 [가상] |
| life_limit | 수명 한도 | 소수 | | ○ | 탭 400, 드릴 1,000, 보링 400 (구멍) / 엔드밀 200, 페이스밀 400 (분) | 설계서 5.13, DOC-07 9장 |
| limit_basis | 한도 근거 | 문자 | | ○ | [참고] 탭·엔드밀, [가상] 드릴·보링·페이스밀 | 설계서 5.13 |
| deduct_qty_per_change | 교체 1회 차감 수 | 정수 | | ○ | 1개. 페이스밀 인서트만 5개 | 설계서 5.13 |

#### 5.E.2 `tool` 공구

| 항목 | 내용 |
|---|---|
| 설명 | VF-2에 꽂힌 공구 (공구 번호 자리). 교체하면 누적 사용량이 0이 된다 |
| 쓰는 요구사항 | FR-ML-01-03·04·05, FR-AST-02-09, FR-PRD-01-12, FR-PRD-02-08, FR-AST-01-02 |
| 대략 건수 | VF-2 한 대당 5종 + 예비 (8~12개) |
| 출처 | 설계서 5.13, 기획서 12.4 `tool` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| tool_id | 공구 ID | 문자 | PK | ○ | `{설비 ID}-{공구 번호}` (예: VF2-01-T05) | [제안] |
| equipment_id | 설비 | 문자 | FK | ○ | → equipment. VF2-01·02만 | 설계서 5.13 |
| tool_no | 공구 번호 | 문자 | | ○ | 사용 중 5종은 6.25: T01 페이스밀 인서트, T02 엔드밀 Ø10, T03 보링바 인서트, T04 드릴 Ø5.0, T05 M6 탭 [가상] (두 대 같음). 예비는 남은 자리 T06~T20 [가상]. 공구 교환기 20개 자리 [실제] | 설계서 5.13, 7장 S3 |
| item_no | 공구 종류 | 문자 | FK | ○ | → tool_type | 설계서 5.13 |
| tool_role | 쓰임 | 코드 | | ○ | 사용 중 / 예비 [제안] | 설계서 5.13 "+ 예비" |
| cum_usage | 누적 사용량 | 소수 | | ○ | 교체 뒤 가공한 부품마다 부품당 사용량을 더함. 교체 때 0 (R-10) | 설계서 5.13 |
| last_changed_at | 마지막 교체 | 날짜시각 | | — | — | [제안] |
| usage_rate_pct | 공구 수명 (사용률) | 소수 | | — | **계산**: 누적 ÷ 한도 × 100. 화면의 "공구 수명 N%" = 사용률. 남은 수명은 100 − 사용률이고 "남은 수명"이라고 적음 | DOC-07 9장 |

#### 5.E.3 `tool_usage` 공구 사용 기록

| 항목 | 내용 |
|---|---|
| 설명 | OP-30 공정 실적마다 공구에 더한 사용량. 로트 추적(공구 상태)과 누적 사용량의 근거 |
| 쓰는 요구사항 | FR-ML-01-01·03, FR-PRD-05-03 |
| 대략 건수 | 값 없음 |
| 출처 | 설계서 5.13 "사용 기록", 기획서 12.4 `tool_usage` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| tool_id | 공구 | 문자 | PK, FK | ○ | → tool | — |
| op_report_id | 공정 실적 | 정수 | PK, FK | ○ | → operation_report. OP-30, 같은 설비 | 설계서 5.13 |
| parts_qty | 가공 부품 수 | 정수 | | ○ | 그 실적의 생산 수량(PQ) | 설계서 5.13 |
| usage_qty | 더한 사용량 | 소수 | | ○ | 가공 부품 수 × 부품당 사용량 | 설계서 5.13 |
| cum_after | 더한 뒤 누적 | 소수 | | ○ | 직전 누적 + usage_qty | 설계서 9장 |
| recorded_at | 기록 시각 | 날짜시각 | | ○ | — | [제안] |

- 부품 1개 단위로 쌓을지 공정 실적 단위로 쌓을지는 물리 ERD에서 정한다 [선택 필요: 기술 회의]. 논리 규칙(R-10)은 같다.

#### 5.E.4 `tool_change` 공구 교체 기록

| 항목 | 내용 |
|---|---|
| 설명 | 공구를 바꾼 기록. 누적 사용량을 0으로 하고 재고에서 뺀다 (OPR·MNT가 기록) |
| 쓰는 요구사항 | FR-ML-01-06, FR-INV-01-03·05, FR-PRD-05-03, FR-QLT-01-04 |
| 대략 건수 | 30일 2대 합: 탭 약 47회, 드릴 약 19회, 보링 인서트 약 12회, 엔드밀 약 58회, 페이스밀 약 6회 |
| 출처 | 설계서 5.13. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| tool_change_id | 교체 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| tool_id | 공구 | 문자 | FK | ○ | → tool | — |
| changed_at | 교체 시각 | 날짜시각 | | ○ | 공구 교체 SETUP 구간(3~8분)과 겹침 | 설계서 5.7 |
| changed_by | 교체한 사람 | 문자 | FK | ○ | → app_user, OPR 또는 MNT | 기획서 13.2 |
| cum_before | 교체 전 누적 | 소수 | | ○ | 수명 편차 분석에 씀 | 설계서 5.13 |
| change_reason | 교체 사유 | 코드 | | ○ | 6.26 [제안] | 설계서 5.13 |
| related_alarm_event_id | 계기 알람 | 정수 | FK | — | → alarm_event (362, 174) | 설계서 5.13 |

#### 5.E.5 `inventory_item` 재고 품목

| 항목 | 내용 |
|---|---|
| 설명 | 공구·소모품·원자재·**완제품** 품목과 안전 재고·**관리 역할**. 현재 수량은 거래에서 계산 |
| 쓰는 요구사항 | FR-INV-01-01·06·07·11·13, FR-AST-02-07, FR-MNT-05-07, FR-MNT-03-12, FR-PRD-04-07 |
| 대략 건수 | **13행** (공구 5, 소모품 6, 원자재 1, 완제품 1) |
| 출처 | 설계서 5.14·15.5, DOC-04 4장, 기획서 12.4 `inventory_item`, R5 1.3·2.3, D-13·D-14 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| item_no | 품목 번호 | 문자 | PK | ○ | 6.27 (TL-EM10 등, 완제품 FG-BRK-A100). Haas 실제 부품 번호를 쓰지 않음 | 설계서 5.14 [가상], R5 표 A1 [가상] |
| category | 구분 | 코드 | | ○ | 공구 / 소모품 / 원자재 / **완제품** (6.27) | 설계서 5.14, D-14 |
| item_name | 품목 이름 | 문자 | | ○ | 예: M6 탭, 축 윤활유, BRK-A100 완제품 | 설계서 5.14 |
| unit | 단위 | 코드 | | ○ | 개 / L / 개분 (완제품은 개) | 설계서 5.14, R5 표 A1 |
| owner_role | 관리 역할 | 코드 | FK | ○ | → role. **MNT** = 정비용 소모품 6종 / **SUP** = 절삭 공구 5종, 원자재, 완제품. 관리 역할이 **입고 등록·월 1회 실사·조정**을 한다. 재고 부족 알림은 관리 역할 + MGR (R-77). 이 칸은 MGR만 바꾼다 (R-58) | D-13, R5 표 D, FR-INV-01-13 |
| safety_stock | 안전 재고 | 소수 | | 조건 | 처음 값 6.27. 식 [참고]: 설비에 달린 수 + 하루 사용량 × 3일분. **MGR만 바꿈**. **완제품은 비움** (안전 재고·부족 알림 없음 — 주문·납기 관리가 범위 밖이라 기준을 정할 근거가 없음) [제안] | 설계서 5.14·15.5, 기획서 13.2, R5 표 A10 |
| product_note | 제품 이름 | 문자 | | — | 예: TRIM SC538, Mobil 1 0W-20, Mobil Grease XHP 222 | 설계서 5.14 |
| on_hand_qty | 현재 수량 | 소수 | | ○ | **계산**: 입고(합격 입고 포함) − 사용·출하 ± 조정. 음수 없음 (R-11). 완제품 = 합격 입고 합 − 출하 합 ± 조정 (R-69) | 설계서 9장, R5 표 A7 |
| safety_stock_set_by | 안전 재고 정한 사람 | 문자 | FK | — | → app_user, MGR | FR-INV-01-06 |
| safety_stock_set_at | 정한 시각 | 날짜시각 | | — | — | NFR-REL-03 |

#### 5.E.6 `inventory_txn` 입출고 거래

| 항목 | 내용 |
|---|---|
| 설명 | 입고·사용·조정·**완제품 합격 입고·출하 출고** 1건. 어디서 생긴 거래인지 출처 기록을 하나 가리킨다 (수불대장 모양) |
| 쓰는 요구사항 | FR-INV-01-02·03·04·05·08·09·11·12, FR-PRD-04-07, FR-MNT-05-10, FR-MNT-04-06 |
| 대략 건수 | 값 없음. 입고: 공구·소모품 주 1회, 원자재 주 3회. 조정: 월말 1~2건 (완제품 실사 조정 0~1건). 완제품 합격 입고 = 합격 로트 수, 출하 출고 = 출하 로트 줄 수 |
| 출처 | 설계서 5.14, 기획서 12.4 `inventory_txn`, NCS 수불대장 [참고], R5 1.4 표 B |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| txn_id | 거래 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| item_no | 품목 | 문자 | FK | ○ | → inventory_item | 설계서 5.14 |
| txn_type | 거래 종류 | 코드 | | ○ | 6.28 (입고 / 사용 / 조정 / **완제품 합격 입고** / **출하 출고**) | 설계서 5.14, D-14 |
| qty_change | 변화량 | 소수 | | ○ | 부호 있음: 입고·합격 입고 +, 사용·출하 출고 −, 조정 ±. 0이 아님 | [제안] |
| txn_at | 거래 시각 | 날짜시각 | | ○ | 합격 입고 = 로트 판정(해제) 시각, 출하 출고 = 출하 확정 시각 | 설계서 5.14, R5 표 B |
| txn_by | 기록한 사람 | 문자 | FK | 조건 | → app_user. **입고·조정(월말 실사) = 그 품목의 관리 역할** (소모품 MNT, 공구·원자재·완제품 SUP — R-77), 공구 사용 = OPR·MNT, 출하 출고 = 출하 확인자 SUP. **완제품 합격 입고는 시스템 거래라 비움** (검사 결과에서 자동) | D-13, R5 표 B·D, UI설계서 SCR-21 [4] |
| source_kind | 거래 출처 | 코드 | | ○ | 6.28 (입고 등록 / 원자재 입고 / 작업기록서 / 예방 정비 / 공구 교체 / 로트 투입 / 월말 실사 / **로트 합격** / **출하**) | 설계서 5.14, R5 표 B |
| work_record_no | 작업기록서 | 문자 | FK | 조건 | 출처가 작업기록서면 필수. (work_record_no, work_record_item_no) → work_record_part | FR-MNT-05-10 |
| work_record_item_no | 작업기록서 품목 | 문자 | FK | 조건 | 위와 같음. item_no와 같아야 함 | — |
| pm_record_id | 예방 정비 기록 | 정수 | FK | 조건 | 출처가 예방 정비면 필수 | FR-MNT-04-06 |
| tool_change_id | 공구 교체 | 정수 | FK, UK | 조건 | 출처가 공구 교체면 필수. 교체 1회 = 거래 1건 | 설계서 5.13 |
| lot_no | 원자재 투입 로트 | 문자 | FK, UK | 조건 | 출처가 로트 투입이면 필수. 수량 = 로트 투입 수량 | FR-INV-01-03 |
| material_lot_no | 원자재 입고 로트 | 문자 | FK, UK | 조건 | 출처가 원자재 입고면 필수 | 설계서 5.4 |
| fg_lot_no | 완제품 거래 로트 | 문자 | FK | 조건 | → production_lot. **출처가 로트 합격이면 필수** (로트마다 합격 입고 1건 — (fg_lot_no, source_kind 로트 합격)은 UK). 완제품 월말 실사 조정은 로트를 알 수 있으면 적음. 원자재 투입 로트(lot_no)와 다른 칸 (한 로트가 두 거래를 가짐) | R5 표 A2·A7·B, R-69 |
| shipment_no | 출하 | 문자 | FK | 조건 | 출처가 출하면 필수. (shipment_no, ship_lot_no) → shipment_line, 로트 줄 1개에 거래 1건 (UK) | R5 표 A5·B |
| ship_lot_no | 출하 로트 줄 | 문자 | FK | 조건 | 위와 같음. 수량 = 로트 줄 수량 | R5 표 C |
| memo | 메모 | 긴 문자 | | — | 실사 차이 사유 등. **조정이면 사유 필수** (완제품 조정 포함) | NCS [참고], R5 표 A8 |

#### 5.E.7 `shipment` 출하 — 최종본 새 엔터티

| 항목 | 내용 |
|---|---|
| 설명 | 완제품을 공장 밖으로 내보낸 기록 1건 (출하 머리: 언제·어디로·누가). 로트 줄(`shipment_line`)이 여러 개 붙는다. **SUP가 등록·확정**하면 로트 줄마다 출하 출고 거래가 생긴다. 주문 접수·ERP 연동은 범위 밖 (FR-INV-01-10) |
| 쓰는 요구사항 | FR-INV-01-12·11, FR-PRD-05-01, FR-PRD-04-07 |
| 대략 건수 | 30일 **25건** (납기일 하루 1번, 14:00 [가상]. 9월 1일 출하 없음, 9월 2일 첫 출하 — 설계서_최종본 5.20) |
| 출처 | R5 1.5 표 C·1.7, 설계서_최종본 5.20, DOC-01 §5.5, DOC-06 §4.3, 변경 명세 4장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| shipment_no | 출하 번호 | 문자 | PK | ○ | `SHP-2609-001` 형식 (다른 번호 규칙 PO-, LOT-과 같은 모양) | R5 표 C [가상] |
| shipped_at | 출하 일시 | 날짜시각 | | 조건 | 출하 확정 시각. 확정이면 필수. 가상 데이터는 납기일 주간 교대 중 하루 1번, 14:00 [가상] | R5 표 C [참고], 1.7 G3 [가상] |
| customer_code | 출하처 | 코드 | | ○ | 6.45 (`CUST-01` 가상 고객사 1곳). **실제 회사 이름은 쓰지 않는다** | R5 표 C [가상] |
| basis_order_nos | 근거 작업지시 | 문자 | | — | **계산**: 로트 줄의 생산 로트 → 작업지시 번호 목록 (1개 이상) | R5 표 C [제안] |
| due_date | 납기일 | 날짜 | | ○ | 근거 작업지시의 납기 (production_order.due_at의 날짜, 납기 G2). 가상 데이터는 "납기일에 출하" | R5 표 C·1.7 G2 [가상] |
| total_qty | 출하 수량 합 | 정수 | | — | **계산**: 로트 줄 수량의 합 | R5 표 C [참고] |
| confirmed_by | 출하 확인자 | 문자 | FK | 조건 | → app_user, **SUP만** (ISO 9001 8.6 "내보내기를 승인한 사람" [참고]). 확정이면 필수. 비서는 안 됨 | R5 표 C, D-13 |
| status | 상태 | 코드 | | ○ | 6.44 (작성 중 → 확정 / 확정 후 수정). **확정 때 출하 전 확인**(R-67·R-68)을 통과해야 한다. 확정 뒤 고치면 새 버전 + 사유 필수 (R-35) | R5 표 C [제안] |
| fifo_skip_reason | FIFO 예외 사유 | 긴 문자 | | 조건 | 먼저 합격한 로트(보류 아님)를 두고 나중 로트를 고르면 필수 (R-68) | R5 표 C "아니면 사유" |
| is_late | 납기 지남 | 참·거짓 | | — | **계산**: 출하 날짜 > 납기일. 보류·판정 대기로 빠졌던 로트를 다음 출하에 넣을 때 "납기 지남" 표시 | R5 1.7 G5 |
| memo | 비고 | 긴 문자 | | 조건 | 부분 출하·늦은 출하 사유. **부분 출하면 필수** (그날 납기 로트 중 보류·판정 대기 로트를 뺀 경우) | R5 표 C, 1.7 G5 |
| current_version | 현재 버전 | 정수 | | ○ | 0 = 사람이 처음 저장한 것 (AI비서 초안 없음). 수정 이력 대상 (문서 종류 SHIPMENT, 6.17) [제안] | R5 표 C "FR-AST-03 모양" |

- 뺀 칸: 차량번호·운전자·송장·포장·라벨 (물류 범위 밖, R5 표 C).
- 이미 출하한 로트가 나중에 의심 로트가 되면 로트 추적 화면에 출하 번호·출하처까지 보인다. 고객 통보·회수는 범위 밖 (R5 표 A11).

#### 5.E.8 `shipment_line` 출하 내역 — 최종본 새 엔터티

| 항목 | 내용 |
|---|---|
| 설명 | 출하 1건에 들어간 로트와 수량. 로트 줄이 있어야 출하 → 생산 로트 → 원자재 로트로 거슬러 갈 수 있다 |
| 쓰는 요구사항 | FR-INV-01-12, FR-PRD-05-01 |
| 대략 건수 | 값 없음 (출하마다 그날 납기 로트 수) |
| 출처 | R5 1.5 표 C "출하 로트 줄", 변경 명세 4장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| shipment_no | 출하 | 문자 | PK, FK | ○ | → shipment | R5 표 C |
| lot_no | 생산 로트 | 문자 | PK, FK | ○ | → production_lot. **합격(해제 포함) 로트만** 고를 수 있음 (R-67). 출하 화면의 로트 목록에도 합격·해제 로트만 나온다 | R5 표 C·1.6, DOC-06 §4.1 |
| qty | 수량 | 정수 | | ○ | 1 이상, 그 로트의 남은 완제품 수량 이하 (R-67). 가상 데이터는 로트를 쪼개지 않음 (로트 남은 수량 전부) | R5 표 C, 1.7 G4 |
| lot_passed_at | 로트 합격 시각 | 날짜시각 | | ○ | 로트 기록에서 가져옴 (합격 = production_lot.judged_at, 해제 = lot_hold.released_at). FIFO 확인용. 출하 시각 > 합격 시각 | R5 표 C, 생성 뒤 점검 |

### 5.F 품질

#### 5.F.1 `inspection_item` 검사 항목

| 항목 | 내용 |
|---|---|
| 설명 | BRK-A100 검사 항목과 기준 (가상 도면). 판정과 Cpk 기준의 출처 |
| 쓰는 요구사항 | FR-QLT-01-02·03·08·09 |
| 대략 건수 | 8행 (DOC-06 §2) |
| 출처 | 설계서 5.15, DOC-06 §2·§5.2. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| product_code | 제품 | 문자 | PK, FK | ○ | → product | — |
| item_seq | 항목 번호 | 정수 | PK | ○ | DOC-06 §2 번호 1~8 (6.29) | DOC-06 §2 |
| item_name | 항목 이름 | 문자 | | ○ | 예: 부싱 압입 구멍 지름 | DOC-06 §2 |
| spec_text | 기준 | 문자 | | ○ | 예: Ø45 H7 (+0.025 / 0 mm) | DOC-06 §2 |
| nominal | 기준값 | 소수 | | 조건 | 치수 항목만 (mm) | DOC-06 §2 [가상 치수] |
| lsl | 아래 한계 | 소수 | | 조건 | 치수 항목만. 평면도는 비움 (위 한계만) | DOC-06 §2 |
| usl | 위 한계 | 소수 | | 조건 | 치수 항목만 | DOC-06 §2 |
| method | 측정 방법 | 코드 | | ○ | 6.31 (3차원 측정기 / 게이지 / 육안) | DOC-06 §2 |
| char_class | 특성 구분 | 코드 | | ○ | 6.30 (특별 특성 ◆ / 일반) | DOC-06 §2 [가상] |
| cpk_min | Cpk 기준 | 소수 | | 조건 | 특별 1.67, 일반 1.33. 게이지·육안은 비움 | DOC-06 §5.2 [실제: Nemak] |
| in_sampling | 발췌 측정 항목 | 참·거짓 | | ○ | 1~6번, 8번 참. 7번(외관) 거짓 | DOC-06 §3.2 |
| enhanced_extension | 강화 때 늘리는 것 | 문자 | | — | 예: 부싱 구멍 위·중간·아래 3단 측정 (기록만) | DOC-06 §3.3 |
| is_full_check_by_cpk | Cpk 미달 전수 중 | 참·거짓 | | ○ | Cpk 기준 미만이면 참 → 그 항목 전수. 관리자 승인 뒤 거짓 | DOC-06 §5.2 |

#### 5.F.2 `defect_code` 불량 코드

| 항목 | 내용 |
|---|---|
| 설명 | 불량 코드와 결함 등급. 불량 집계의 단위 |
| 쓰는 요구사항 | FR-QLT-01-11 |
| 대략 건수 | 10행 (DOC-06 §8.2) |
| 출처 | DOC-06 §8.1·8.2 [가상]. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| defect_code | 불량 코드 | 코드 | PK | ○ | 6.34 (DIM-01~04, THR-01~02, SUR-01~03, MAT-01) | DOC-06 §8.2 |
| defect_name | 이름 | 문자 | | ○ | 예: 치수 큼 (상한 넘음) | DOC-06 §8.2 |
| related_items | 관련 검사 항목 | 문자 | | ○ | 예: "1~3, 8" (항목 번호 글). 여러 항목이라 글로 둠 | DOC-06 §8.2 |
| grade | 결함 등급 | 코드 | | ○ | 6.34 (치명 / 중 / 경) | DOC-06 §8.1 |
| grade_rule | 등급 규칙 | 문자 | | — | 예: "1번은 치명, 나머지 중", "경 (치수에 영향 있으면 중)" | DOC-06 §8.2 |
| common_cause | 자주 보는 원인 | 문자 | | — | 비서가 **불량 원인 안내에 쓰지 않는다** (FR-MNT-01-12) | DOC-06 §8.2 |

#### 5.F.3 `inspection_plan` 검사 방식

| 항목 | 내용 |
|---|---|
| 설명 | 로트마다 검사 방식 (보통 발췌 / 강화 전수)과 로트 판정. 게이지·육안 부품의 합격·불합격 수량도 여기에 둔다 |
| 쓰는 요구사항 | FR-QLT-01-03·05·06·07·12·13, FR-PRD-05-04·07 |
| 대략 건수 | 로트 수와 같음 (30일 약 130~160). 강화는 2~3회 (보류 로트와 다음 1~2개) |
| 출처 | 설계서 5.15·5.18 ③, DOC-06 §3, 기획서 12.4 `inspection_plan` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| lot_no | 로트 | 문자 | PK, FK | ○ | → production_lot. 로트 1 : 검사 방식 1 | 설계서 5.15 |
| plan_mode | 검사 방식 | 코드 | | ○ | 6.32 (보통 / 강화). 처음 값 보통 | DOC-06 §3 |
| enhance_reason | 강화 사유 | 코드 | | 조건 | 강화면 필수. 6.32 (보류 로트 / 보류 다음 로트) | DOC-06 §3.3 |
| hold_id | 강화 계기 보류 | 정수 | FK | 조건 | 강화면 필수. → lot_hold. 다음 로트도 같은 보류를 가리킴 | DOC-06 §3.3 |
| planned_measure_qty | 측정할 부품 수 | 정수 | | ○ | **계산**: 보통 = 1 + (투입 수량 ÷ 5의 몫) (36개 → 8개), 강화 = 투입 수량 전부 | DOC-06 §3.2·3.3, 설계서 9장 |
| gauge_pass_qty | 게이지·육안 합격 수 | 정수 | | — | 측정하지 않은 부품 (측정값을 남기지 않음) | DOC-06 §3.5 |
| gauge_fail_qty | 게이지·육안 불합격 수 | 정수 | | — | 위와 같음 | DOC-06 §3.5 |
| judgement | 로트 판정 | 코드 | | — | 합격 / 보류 검토. **측정 부품을 모두 잰 뒤**에만 넣음 (R-25) | 설계서 5.15, DOC-06 4.1 |
| judged_at | 판정 시각 | 날짜시각 | | 조건 | 판정이 있으면 필수 | 설계서 5.15 |

#### 5.F.4 `inspection_result` 검사 결과

| 항목 | 내용 |
|---|---|
| 설명 | **측정한 부품만** 남기는 항목별 측정값과 판정. Cpk·관리도의 데이터. 최종본: OP-50 측정값은 **사람이 손으로 적지 않고** 측정기 결과 파일(`cmm_import`)에서 자동으로 기록한다. M6 게이지·외관은 태블릿 버튼, 측정자는 로그인, 로트는 바코드 확인. 사람은 확인만 한다 (D-17) |
| 쓰는 요구사항 | FR-QLT-01-01·04·06·08·10·12·14~22, FR-PRD-05-03 |
| 대략 건수 | 값 없음 (발췌 로트는 측정 부품 수 × 측정 항목 수, 재측정은 따로 더함) |
| 출처 | 설계서 5.15, DOC-06 §3.5·§3.6·§6, 기획서 12.4 `inspection_result`, R3 5.2·5.3·5.4·7.1 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| result_id | 결과 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| lot_no | 로트 | 문자 | FK | ○ | → production_lot | DOC-06 §3.5 |
| part_seq | 부품 순번 | 정수 | | ○ | 1 ~ 로트 투입 수량. 발췌는 1번과 5의 배수 번째 | DOC-06 §3.2·3.5 |
| product_code | 제품 | 문자 | FK | ○ | (product_code, item_seq) → inspection_item | — |
| item_seq | 검사 항목 | 정수 | FK | ○ | 위와 같음 | DOC-06 §3.5 |
| insp_kind | 검사 구분 | 코드 | | ○ | 6.32 (초품 / 발췌 / 강화). 초품은 발췌 측정 1개로 셈 | DOC-06 §3.1·3.5 |
| position | 측정 위치 | 코드 | | — | 위 / 중간 / 아래 (강화 때 부싱 구멍 3단). (lot_no, part_seq, item_seq, insp_kind, position, remeasure_seq)는 UK | DOC-06 §3.3, R3 5.4 |
| measured_value | 측정값 | 소수 | | 조건 | mm. 3차원 측정기 항목이면 필수 (결과 파일에서 자동). 게이지 항목은 비움. **측정값을 지우거나 합격·불합격만 남기지 않는다** (R-75) | DOC-06 §3.5, R2 #10 |
| judgement | 판정 (플랫폼) | 코드 | | ○ | 6.33 (합격 / 불합격). **플랫폼이 측정값으로 DOC-06 §2 기준에 따라 다시 계산한 판정**을 쓴다 (R-79). 게이지는 통과·정지 결과로 판정 | DOC-06 §3.5, R3 5.1 6번·FR-QLT-01-16 |
| instrument_id | 측정기 | 문자 | FK | ○ | → equipment (CMM-01). 자동이면 결과 파일의 측정기 | DOC-06 §3.5, R3 5.3 |
| inspector_id | 측정자 | 문자 | FK | ○ | → app_user, OPR. **OP-50 태블릿 로그인**으로 채움, 측정 시작 때 본인 확인 (반자동) | DOC-06 1장, R3 5.3 |
| measured_at | 측정 시각 | 날짜시각 | | ○ | 결과 파일의 측정 시각 (측정기 시계 — 플랫폼 시계와 맞춤 필요). 받은 시각은 cmm_import.received_at. 발췌 측정 부품은 **세척 완료 + 온도 맞춤 대기 뒤** (R-25) | 설계서 5.15, R3 5.2·5.3 |
| room_temp_c | 측정실 온도 (방 공기) | 소수 | | 조건 | ℃. 환경 센서가 있으면 측정 시각에 가장 가까운 값 자동, **없으면 사람이 온도계 값 입력**. CMM 항목이면 필수 | DOC-06 §3.5, R3 3.5·5.3 |
| part_temp_c | 부품 온도 | 소수 | | 조건 | ℃. **측정기 부품 온도 센서에서 자동** (보정을 못 쓸 때는 사람 입력). CMM 항목이면 필수. 16~26 ℃ 밖이면 "온도 확인" 표시 (is_temp_flag, R-82) | DOC-06 §6, R3 3.5·5.3·FR-QLT-01-21 |
| temp_comp_used | 부품 온도 보정 사용 | 참·거짓 | | — | 결과 파일의 "온도 보정 켬/끔". 보정을 못 쓰면 140분 이상 대기 | DOC-06 §6, R3 5.2 |
| input_method | 입력 방식 | 코드 | | ○ | 6.46 (CMM 자동 / 태블릿 버튼 / 수동). CMM 항목은 자동이 기본, 게이지(6번)·외관(7번)은 태블릿 버튼, 자동 입력이 안 될 때만 수동 | R3 5.3·5.4, FR-QLT-01-14·19·20 |
| cmm_import_id | 결과 파일 | 정수 | FK | 조건 | → cmm_import. **입력 방식이 CMM 자동이면 필수**, 그 밖은 비움 | R3 5.1, FR-QLT-01-14 |
| cmm_judgement | 측정기 판정 | 코드 | | 조건 | 6.33 (합격 / 불합격). 결과 파일의 측정기 판정 그대로. CMM 자동이면 필수 | R3 5.2 |
| is_judgement_mismatch | 판정 불일치 | 참·거짓 | | — | **계산**: 측정기 판정 ≠ 플랫폼 판정. 참이면 "CMM 판정 불일치" 주의 알림 → 반장 확인 (R-79) | R3 5.4, FR-QLT-01-16 |
| is_temp_flag | 온도 확인 표시 | 참·거짓 | | — | **계산**: 부품 온도가 DOC-06 §6 범위(16~26 ℃) 밖 | R3 FR-QLT-01-21, DOC-06 §6 |
| check_status | 확인 상태 | 코드 | | ○ | 6.47 (정상 / 확인 필요 / 반장 확인, DOC-06 §3.5). 판정 불일치·지시와 다른 로트·순번·불완전·수동 입력은 "확인 필요" → **로트 판정에 쓰지 않는다** (반장 확인 뒤 씀) | R3 5.4, FR-QLT-01-15·16·19 |
| checked_by | 확인한 반장 | 문자 | FK | 조건 | → app_user, **SUP**. 확인 상태가 "반장 확인"이면 필수 | R3 5.4, FR-QLT-01-19 |
| checked_at | 확인 시각 | 날짜시각 | | 조건 | 같음 | NFR-REL-03 |
| remeasure_seq | 재측정 순번 | 정수 | | ○ | 1 = 처음 측정, 같은 부품 결과가 다시 오면 2, 3 … **덮어쓰지 않는다** (R-81) | R3 5.4, FR-QLT-01-22 |
| use_for_judgement | 판정에 씀 | 참·거짓 | | ○ | 같은 부품·항목에서 **하나만 참**. 처음 값은 1회차. 재측정이 있으면 어느 것을 쓸지 **반장이 고른다** | R3 5.4, FR-QLT-01-22 |
| entered_by | 수동 입력자 | 문자 | FK | 조건 | → app_user. **입력 방식이 수동이면 필수** ("수동" 표시와 입력자를 남김) | R3 5.4, FR-QLT-01-19 |

- 칸별 자동/사람 (R3 5.3): 로트 번호·부품 순번·검사 방식·강화 사유·항목·측정값·CMM 판정·측정기·시각·부품 온도 = 자동, 측정실 온도 = 센서 있으면 자동, 측정자 = 로그인(반자동), 로트 = 바코드 확인, M6 게이지·외관 = 사람(태블릿 버튼).
- 수동 입력과 자동 입력을 나눠 두어 Cpk(FR-QLT-01-08) 계산 때 수동 입력 값만 따로 볼 수 있다 (R3 5.4).

#### 5.F.5 `defect_record` 불량 기록

| 항목 | 내용 |
|---|---|
| 설명 | 로트·공정·불량 코드별 불량 수량. 불량 코드별 집계와 재작업·폐기 처리 |
| 쓰는 요구사항 | FR-QLT-01-11, FR-PRD-05-10 |
| 대략 건수 | 값 없음. 전체 불량률 0.5~1.0%, OP-50 약 80% |
| 출처 | 설계서 5.5, DOC-06 §8. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| defect_record_id | 불량 기록 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| lot_no | 로트 | 문자 | FK | ○ | → production_lot | — |
| process_code | 발견 공정 | 코드 | FK | ○ | → process | 설계서 5.5 |
| defect_code | 불량 코드 | 코드 | FK | ○ | → defect_code | DOC-06 §8.2 |
| qty | 수량 | 정수 | | ○ | 1 이상 | — |
| disposition | 처리 | 코드 | | ○ | 폐기 / 재작업 (경결함은 OP-40 다시 디버링 후 재검사) | DOC-06 §8.1 |
| result_id | 불합격 측정값 | 정수 | FK, UK | — | → inspection_result (측정 불합격에서 나온 경우) | — |
| found_at | 발견 시각 | 날짜시각 | | ○ | — | — |
| recorded_by | 기록한 사람 | 문자 | FK | ○ | → app_user | — |

#### 5.F.6 `cmm_import` 측정 결과 파일 가져오기 — 최종본 새 엔터티

| 항목 | 내용 |
|---|---|
| 설명 | 측정기(CMM-01) 소프트웨어가 **부품 1개 측정마다** 공유 폴더에 쓴 결과 파일(정한 양식의 CSV) 1개를 플랫폼이 읽은 기록. 읽은 결과(성공·실패·확인 필요)와 원본 파일 보관 위치를 남긴다. 성공하면 측정값(`inspection_result`)이 자동으로 생긴다 |
| 쓰는 요구사항 | FR-QLT-01-14·15·16·17·18·22 |
| 대략 건수 | 값 없음 (측정 부품 1개 = 파일 1개). 30일 데이터에 오류·재측정을 몇 건 넣을지는 설계서_최종본 5.15 |
| 출처 | R3 5장 (5.1 흐름, 5.2 결과 파일 양식, 5.4 못 읽었을 때) [제안], DOC-06 §3.6, 변경 명세 4장 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| cmm_import_id | 가져오기 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| file_name | 파일 이름 | 문자 | UK | ○ | 측정기가 쓴 이름 그대로 (파일 이름 규칙은 [선택 필요: 기술 회의]). 쓰는 중에는 임시 이름 → 다 쓰면 이름 바꿈 (다 쓴 파일만 읽음) | R3 5.1 5번 |
| received_at | 받은 시각 | 날짜시각 | | ○ | 플랫폼이 읽은 시각 (측정 시각과 따로 저장) | R3 5.3 |
| status | 상태 | 코드 | | ○ | 6.48 (성공 / 실패 / 확인 필요). **실패면 측정값을 기록하지 않는다**. 확인 필요면 측정값은 남기되 로트 판정에 쓰지 않는다 | R3 5.4, FR-QLT-01-17 |
| error_kind | 오류 종류 | 코드 | | 조건 | 6.48. 상태가 실패·확인 필요면 필수 | R3 5.4 |
| error_text | 오류 내용 | 긴 문자 | | 조건 | 예: "열 빠짐: 측정값", "지시한 로트와 다름". 상태가 실패·확인 필요면 필수 | R3 5.4 |
| original_file_ref | 원본 파일 보관 위치 | 문자 | | ○ | "처리됨" 칸 또는 "오류" 칸의 위치. **원본 파일은 지우지 않는다**. 폴더 이름·형식은 [선택 필요: 기술 회의] | R3 5.1 7번, FR-QLT-01-17 |
| instrument_id | 측정기 | 문자 | FK | — | → equipment (CMM-01). 파일에서 읽음 (못 읽으면 비움) | R3 5.2 |
| lot_no | 로트 번호 | 문자 | FK | — | → production_lot. 파일의 로트 번호 (지시 파일 → 그대로 돌려받음). 못 읽거나 없는 로트면 비움 + 오류 | R3 5.2, FR-QLT-01-15 |
| part_seq | 부품 순번 | 정수 | | — | 파일의 부품 순번 | R3 5.2 |
| insp_kind | 검사 방식 | 코드 | | — | 6.32 (초품 / 발췌 / 강화). 파일에 돌아온 지시 값 | R3 5.2 |
| program_name_rev | 측정 프로그램 이름·개정 | 문자 | | — | 예: "BRK-A100_OP50 Rev.0" [가상] | R3 5.2 |
| measure_start_at | 측정 시작 | 날짜시각 | | — | 측정기 시계 | R3 5.2 |
| measure_end_at | 측정 끝 | 날짜시각 | | — | 측정기 시계 | R3 5.2 |
| machine_temp_c | 측정기 온도 | 소수 | | — | ℃. 측정기 제어기에서 자동 (스케일 온도) | R3 3.5·5.2 |
| temp_comp_on | 온도 보정 켬 | 참·거짓 | | — | 측정 프로그램의 보정 사용 여부 (DOC-06 §6) | R3 5.2 |

- 결과 파일 양식 (R3 5.2, 부품 1개·항목마다 1줄): 로트 번호, 부품 순번, 검사 방식, 측정 프로그램 이름·개정, 항목 번호(DOC-06 2장 번호), 공칭값·+공차·−공차, 측정값, 측정기 판정, 측정기, 측정 시작·끝 시각, 부품 온도·측정기 온도, 온도 보정 켬/끔. 항목 줄의 값은 `inspection_result`로, 파일 머리 값은 이 엔터티로 간다.
- 측정 지시(로트 번호·부품 순번·검사 방식·강화 사유)는 플랫폼이 지시 파일(또는 바코드)로 측정기에 넘긴다. 지시 파일을 DB 엔터티로 둘지, 결과 미수신(R-80) 판단의 "측정 시작" 시각(바코드 확인 시각)을 어디에 둘지는 **[선택 필요: 기술 회의]** (공유 폴더·파일 감시 방식과 함께 정함, 11장 #20).
- 대안 방식(QIF Results ISO 23952, OPC UA 40210)으로 바꾸어도 이 엔터티의 칸(받은 시각·상태·오류·원본 위치)은 그대로 쓴다 [제안].

### 5.G 문서·AI 비서

#### 5.G.1 `shift_report` 교대 보고서

| 항목 | 내용 |
|---|---|
| 설명 | 교대 근무자 사이 인수인계 문서. 숫자 칸은 프로그램, 특이 사항·인계 문장은 비서. **해당 교대 반장**이 확정 |
| 쓰는 요구사항 | FR-PRD-02-01~12, FR-AST-01-02, FR-PRD-04-01, FR-AST-03-01 |
| 대략 건수 | 52행 (교대마다 1개) |
| 출처 | 설계서 5.16, 기획서 PRD-02·5.1, 기획서 12.4 `shift_report` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| shift_id | 교대 | 문자 | PK, FK | ○ | → shift. 교대 1 : 보고서 0..1 (교대가 끝나면 1) | 설계서 5.16 |
| status | 상태 | 코드 | | ○ | 6.16. 과거 52개는 모두 확정 | 설계서 5.16 |
| target_qty | 목표 | 정수 | | ○ | 교대 목표 (90) | 기획서 PRD-02 |
| actual_qty | 실적 | 정수 | | ○ | 그 교대 OP-50 GQ + RQ (R-46). 3D 라인 뷰 값과 같음 | DOC-07 4.3, FR-PRD-02-02 |
| defect_qty | 불량 | 정수 | | ○ | 그 교대 SQ | 기획서 PRD-02 |
| availability_pct | 가동률 | 소수 | | ○ | **OP-30 설비별 2개 값 (VF2-01, VF2-02)** — 가동률 주의를 거는 범위와 같다. **계산**: 그 교대 equipment_state_log에서 (R-45). 확정 때 값은 content_snapshot에 남음 | 기획서 PRD-02, DOC-07 10.1, UI설계서 9.3 #5, FR-PRD-02-02 |
| notable_text | 특이 사항 | 긴 문자 | | ○ | 비서가 3~5문장. 문장 속 숫자는 표와 대조 | FR-PRD-02-07·10 |
| handover_text | 인계 사항 | 긴 문자 | | ○ | 미해결 알람, 진행 중 작업지시, 기한 임박 정비, 교체할 공구, 재고 부족 (없으면 "없음"). **잠금 중 설비는 맨 위**, 그 아래는 보고 순위(6.43) 순서. 비서는 순서를 바꾸거나 빼지 않는다 (R-73) | FR-PRD-02-08·09, DOC-01 §3.3, R4 4.3 |
| confirmed_by | 확정자 | 문자 | FK | 조건 | → app_user. **shift.supervisor_user_id와 같아야 함** | 설계서 5.16, FR-PRD-02-11 |
| confirmed_at | 확정 시각 | 날짜시각 | | 조건 | — | — |
| current_version | 현재 버전 | 정수 | | ○ | 0 = AI비서 초안 | 기획서 4.5 |

- 로트·**필수 정지**·병목·정비 칸은 기록에서 계산해 보인다. 확정한 순간의 전체 내용은 `document_revision.content_snapshot`에 남는다.
- **필수 정지 칸** (최종본, "정지 상위 3건 칸"을 바꿈): 정지 사유가 고장 그룹(F01~F06)이고 5분 이상인 정지 **전부**, 개수 제한 없음 (R-74). 칸: 설비, 원인, 시간, 손실 수량.
- AI비서 초안 생성 시각: 주간 17:00, 야간 05:00 (R-72).

#### 5.G.2 `daily_report` 일일 보고서

| 항목 | 내용 |
|---|---|
| 설명 | 2교대 하루 운영 보고서. 재료는 교대 보고서 2개 + 하루 집계. **생산일 다음 날 06:00에 AI비서 초안 생성** (확정 안 된 교대 칸은 잠정, R-72). **MGR이 확정** |
| 쓰는 요구사항 | FR-PRD-04-01~10, FR-AST-03-01, FR-AST-COM-21, FR-INV-01-11 |
| 대략 건수 | 26행 (근무일마다 1개) |
| 출처 | 설계서 5.16, 기획서 PRD-04·5.1, 기획서 12.4 `daily_report` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| work_date | 근무일 (생산일) | 날짜 | PK, FK | ○ | → work_day (근무일만). 생산일 = 주간이 시작한 날 (D일 08:00 ~ D+1일 05:00). 예: 9/15 08:00 ~ 9/16 05:00 → "9/15 일일 보고서", 생성 9/16 06:00 | 설계서 5.16, R5 표 H3 [가상] |
| status | 상태 | 코드 | | ○ | 6.16 | 설계서 5.16 |
| target_qty | 하루 목표 | 정수 | | ○ | 180 | 기획서 PRD-04 |
| actual_qty | 실적 | 정수 | | ○ | 교대 보고서 2개 실적 합 (R-12) | 설계서 9장 |
| defect_qty | 불량 | 정수 | | ○ | — | 기획서 PRD-04 |
| oee_pct | OEE | 소수 | | ○ | 라인 OEE (OP-30 2대 합) | DOC-07 6.2 |
| failure_loss_qty | 고장 손실 (추정) | 소수 | | ○ | 하루 FAILURE 그룹 정지 손실 합 | DOC-07 5.3 |
| speed_loss_qty | 속도 손실 (추정) | 소수 | | ○ | 하루 병목 구간 속도 손실 합 | DOC-07 5.3 |
| issues_summary | 오늘의 문제 (전체 N건) | 긴 문자 | | ○ | (최종본에서 `top3_summary` "오늘 가장 중요한 3가지"를 바꿈.) **프로그램이 정해진 목록·기준으로 문제를 전부 모으고 보고 순위(6.43) 순서로 정렬**, 비서는 그 순서대로 문장만 쓴다. 개수 제한 없음, 머리에 "전체 N건" + 순위별 건수. 숫자는 표와 대조 | FR-PRD-04-08, FR-AST-COM-21, R-73 |
| confirmed_by | 확정자 | 문자 | FK | 조건 | → app_user, **MGR만** | FR-PRD-04-09 |
| confirmed_at | 확정 시각 | 날짜시각 | | 조건 | — | — |
| current_version | 현재 버전 | 정수 | | ○ | 0 = AI비서 초안 | 기획서 4.5 |

- 손실 칸: "가장 큰 손실 3건" → **손실 전체, 큰 순서** (FR-PRD-04-03). 기록에서 계산.
- **완제품 줄** (최종본): 시작 재고, 입고(합격), 출하, 조정, 종료 재고, 보류 수량(참고 — 재고에 넣지 않음). `inventory_txn`·`production_lot`에서 계산 (R-69). 06:00 기준 값이라 06:00 뒤 판정된 야간 로트의 입고는 다음 생산일 보고서에 들어간다 (R-72).

#### 5.G.3 `document_revision` 문서 버전

| 항목 | 내용 |
|---|---|
| 설명 | 일곱 종류 문서(작업지시서, 작업기록서(간이 포함), 교대 보고서, 일일 보고서, 사내 문서(용어집 포함), 예방 정비 실시 기록, **출하 기록** — 최종본에서 추가 [제안])의 모든 버전. v0 = AI비서 초안 (간이 작업기록·예방 정비 실시 기록·출하 기록은 사람이 처음 저장한 것) |
| 쓰는 요구사항 | FR-AST-03-01~09, FR-AST-COM-07·08, NFR-REL-01·02·03, FR-INV-01-12 |
| 대략 건수 | 문서마다 1~3버전. 약 60%는 사람이 고친 v1·v2가 있음 |
| 출처 | 설계서 5.16, 기획서 4.5·AST-03, 기획서 12.4 `document_revision` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| revision_id | 버전 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| doc_type | 문서 종류 | 코드 | UK | ○ | 6.17 (작업지시서 / 작업기록서 / 교대 보고서 / 일일 보고서 / 사내 문서 / 예방 정비 실시 기록 / 출하 기록) | FR-AST-03-01, R5 표 C |
| doc_key | 문서 번호 | 문자 | UK | ○ | doc_type에 따라 가리키는 키: MW-…, MR-… / MR-S-…, shift_id, 근무일 날짜, DOC-… / GLOSSARY, pm_record_id, SHP-… (R-35) | FR-AST-03-02 |
| version_no | 버전 | 정수 | UK | ○ | 0부터. (doc_type, doc_key, version_no)는 UK. 0 = AI비서 초안 (사내 문서는 Rev.0 원본, 간이 작업기록·예방 정비 실시 기록·출하 기록은 사람이 처음 저장한 것) | 기획서 4.5, FR-AST-03-02 |
| author_kind | 작성 주체 | 코드 | | ○ | 6.18 (AI / 사람). v0만 AI일 수 있음 | FR-AST-03-03 |
| author_user_id | 고친 사람 | 문자 | FK | 조건 | → app_user. 사람이면 필수, AI면 비움 | FR-AST-03-02 |
| created_at | 저장 시각 | 날짜시각 | | ○ | — | FR-AST-03-02 |
| reason | 사유 | 긴 문자 | | 조건 | **확정 뒤 고친 버전이면 필수** (비면 저장 안 됨) | FR-AST-03-06 |
| status_after | 저장 뒤 상태 | 코드 | | ○ | 그 문서 종류의 상태 코드 (6.13·6.15·6.16) | 기획서 4.5 |
| content_snapshot | 전체 내용 | 긴 문자 | | ○ | 그 버전의 모든 칸. 저장 형식은 [선택 필요: 기술 회의] | [제안] |
| internal_doc_rev | 사내 문서 개정 | 문자 | | 조건 | 사내 문서면 필수 (예: Rev.1) | FR-AST-03-09 |

#### 5.G.4 `document_revision_change` 버전 변경 칸

| 항목 | 내용 |
|---|---|
| 설명 | 한 버전에서 바뀐 칸의 전·후. 수정 이력 화면의 "바뀐 부분 강조"에 쓴다 |
| 쓰는 요구사항 | FR-AST-03-02·03·04 |
| 대략 건수 | 사람이 고친 버전마다 1~2곳 (설계서 5.16 "1~2곳 고친 v1·v2") |
| 출처 | 기획서 4.5 "바뀐 내용(전·후)". 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| revision_id | 버전 | 정수 | PK, FK | ○ | → document_revision | — |
| field_name | 바뀐 칸 | 문자 | PK | ○ | 예: 특이 사항, 원인, 작업 순서 3단계 | 설계서 5.16 |
| before_value | 고치기 전 | 긴 문자 | | — | 새로 넣은 칸이면 비움 | 기획서 4.5 |
| after_value | 고친 뒤 | 긴 문자 | | — | 지운 칸이면 비움 | 기획서 4.5 |

- v0(AI비서 초안)은 바뀐 칸이 없다. 고정 서식 블록(잠금·표지, 고전압, 보호구)은 바뀐 칸이 될 수 없다 (R-33).

#### 5.G.5 `internal_doc` 사내 문서

| 항목 | 내용 |
|---|---|
| 설명 | 가상 사내 문서 세트(DOC-01~07)와 용어집. 개정은 MGR 승인 뒤 반영. **비서 문서 검색 대상 = DOC-01~07 + 용어집** (원문은 검색하지 않음, D-05) |
| 쓰는 요구사항 | FR-AST-03-01·09, FR-MNT-01-03·09, FR-AST-COM-04, FR-MNT-02-12 |
| 대략 건수 | 8행 (GLOSSARY + DOC-01~07). 2026-10-07 Rev.1 개정 (고칠 것이 없는 문서는 Rev.0 유지 — 각 문서 표지) |
| 출처 | 설계서 13.6, 기획서 10장, 기획서 12.4 `internal_doc` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| doc_no | 문서 번호 | 문자 | PK | ○ | DOC-01 ~ DOC-07, GLOSSARY | 각 문서 표지 |
| doc_kind | 문서 종류 | 코드 | | ○ | 6.52 (사내 문서 / 용어집). 둘 다 검색 대상 | D-05, 변경 명세 4장 |
| doc_name | 문서 이름 | 문자 | | ○ | 예: 알람 코드집, 용어집. 출처 표시에 쓴다 ("고장 대응 매뉴얼 DOC-03 §2.1", "용어집 §4") | 각 문서 표지, D-03 |
| current_rev | 현재 개정 | 문자 | | ○ | 예: Rev.1 (2026-10-07) | 각 문서 표지 |
| rev_date | 개정 날짜 | 날짜 | | ○ | — | 각 문서 표지 |
| status | 상태 | 코드 | | ○ | 승인 대기 / 승인 [제안]. 승인 뒤에만 비서 검색에 반영 | FR-AST-03-09 |
| approved_by | 승인자 | 문자 | FK | 조건 | → app_user, MGR | 기획서 13.1 |
| approved_at | 승인 시각 | 날짜시각 | | 조건 | — | — |
| is_search_target | 비서 검색 대상 | 참·거짓 | | ○ | **DOC-01~07, GLOSSARY 모두 참** (최종본에서 용어집 추가 — 예: "쿨런트가 뭐야?" → 용어집 근거로 "절삭유") | FR-MNT-01-03, FR-AST-COM-04, D-05 |
| file_ref | 파일 위치 | 문자 | | ○ | 예: 가상사내문서/DOC-02_알람코드집.md. 출처를 클릭하면 이 문서가 팝업 창으로 열리고 그 절로 이동·강조 (D-04) | FR-MNT-01-09 |

#### 5.G.6 `doc_chunk` 사내 문서 조각

| 항목 | 내용 |
|---|---|
| 설명 | 비서 검색용 사내 문서 조각. **엔터티 이름과 칸만 둔다.** 나누는 방법·임베딩 형식·검색 방식은 AI 비서 설계에서 [선택 필요: 기술 회의] |
| 쓰는 요구사항 | FR-MNT-01-03·06·07·09·10, FR-AST-COM-02·03·04, NFR-SEC-08 |
| 대략 건수 | 값 없음 |
| 출처 | 기획서 12.4 `doc_chunk`, 설계서 13.6 |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| chunk_id | 조각 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| doc_no | 사내 문서 | 문자 | FK | ○ | → internal_doc | FR-MNT-01-10 |
| doc_rev | 개정 번호 | 문자 | | ○ | 조각을 만든 개정 (출처 호버 요약 카드에 나옴. 출처 글자는 이름 + 번호 + §절만) | FR-MNT-01-10 |
| section | 절 | 문자 | | ○ | 예: §2.1. 출처 표시는 **문서 이름 + 문서 번호 + §절**만 (쪽 번호 안 씀) | FR-MNT-01-07, D-03 |
| chunk_text | 조각 본문 | 긴 문자 | | ○ | 사내 문서의 "원문 대응표" 절은 조각으로 만들지 않는다 [제안] | D-03 |
| embedding | 임베딩 | 문자 | | — | 임베딩 모델·형식·차원은 [선택 필요: 기술 회의] (논리 형식 "문자"는 자리만 잡은 것). 로컬에서 만들고 밖으로 보내지 않음 (NFR-SEC-08) | NFR-AIQ-05, D-18 |
| built_at | 만든 시각 | 날짜시각 | | ○ | 개정되면 다시 만든다 | FR-MNT-01-10 |

- **최종본에서 `original_source`(원문 출처) 칸을 삭제했다** (D-03): 비서 답·지침카드·문서 초안·화면 어디에도 원문 출처를 표시하지 않는다. 사내 문서 **본문 안**의 [실제]/[참고] 출처와 원문 대응표는 그대로 두되(사람이 근거를 추적하는 용도) 비서는 인용하지 않는다.

### 5.H 사용자·권한·알림

#### 5.H.1 `app_user` 사용자

| 항목 | 내용 |
|---|---|
| 설명 | 플랫폼 사용자. 역할 1개를 가진다 |
| 쓰는 요구사항 | NFR-SEC-01·07, FR-AST-02-02, FR-AST-03-07·08, 모든 `~_by` 칸 |
| 대략 건수 | 12행 (OPR 6, MNT 3, SUP 2, MGR 1) |
| 출처 | 설계서 5.17, 기획서 13장, 기획서 12.4 `app_user` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| user_id | 사용자 ID | 문자 | PK | ○ | 형식은 [선택 필요: 기술 회의] (로그인 방식과 함께, NFR-SEC-07) | — |
| user_name | 이름 | 문자 | | ○ | 가상 이름 | 설계서 5.17 |
| role_code | 역할 | 코드 | FK | ○ | → role | 설계서 5.17 |
| home_shift_type | 담당 교대 | 코드 | | — | 주간 / 야간. SUP는 2명이 주간·야간 하나씩 | 설계서 5.17 |
| home_process_code | 담당 공정 | 코드 | FK | — | → process. OPR은 "교대·공정별" (긴급 알림의 "해당 설비 작업자") | 설계서 5.17, 기획서 4.3 |
| is_active | 사용 중 | 참·거짓 | | ○ | — | [제안] |

- 로그인 칸(비밀번호 등)은 넣지 않는다 → [선택 필요: 기술 회의] (NFR-SEC-07).

#### 5.H.2 `role` 역할

| 항목 | 내용 |
|---|---|
| 설명 | 계정 역할 4종 |
| 쓰는 요구사항 | NFR-SEC-01·02·03 |
| 대략 건수 | 4행 |
| 출처 | 기획서 3.2·13장, 설계서 5.17. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| role_code | 역할 코드 | 코드 | PK | ○ | OPR, MNT, SUP, MGR (6.37) | 기획서 13장 |
| role_name | 역할 이름 | 문자 | | ○ | 현장 작업자, 보전 담당자, 라인 반장, 공장 관리자 | 설계서 5.17 |

#### 5.H.3 `role_permission` 역할별 권한

| 항목 | 내용 |
|---|---|
| 설명 | 기획서 13.1(문서별)·13.2(기능별) 권한표를 데이터로 둔 것. 서버도 이 표로 막는다 |
| 쓰는 요구사항 | NFR-SEC-02·03·04·05, FR-AST-03-08, FR-AST-01-07 |
| 대략 건수 | 값 없음 (13.1·13.2 표의 칸 수만큼) |
| 출처 | 기획서 13.1·13.2. 엔터티는 [제안]. 표로 둘지 코드에 넣을지는 [선택 필요: 기술 회의] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| role_code | 역할 | 코드 | PK, FK | ○ | → role | — |
| target | 대상 | 코드 | PK | ○ | 문서 종류(6.17 + 지침카드) 또는 기능 (정지 사유, 로트 보류·해제, 재고 입고, 안전 재고 설정, 예방 정비 기록, 공구 교체, 설정 등) | 기획서 13.1·13.2 |
| action | 동작 | 코드 | PK | ○ | 보기 / 작성 / 수정 / 확정 / 승인 / 확인 / 담당 지정 / 취소 / 입력 / 설정 | 기획서 13.1·13.2 |
| scope | 범위 | 코드 | | ○ | 전체 / 자기 문서만 (OPR 수정 이력) / 요약만 (OPR 브리핑) / 대리 (MGR 승인) / **관리 품목만** (재고 입고·실사: MNT = 정비 소모품, SUP = 공구·원자재·완제품) | 기획서 13.1·13.2, D-13 |

- **MGR = 모든 기능·문서 "보기" 범위 전체** (D-11, R-76). 작성·수정·확정·승인 권한은 바꾸지 않는다. 처음 값에서 MGR의 (target, 보기) 행이 빠진 대상이 없어야 한다 (MNT-02 지침카드, MNT-04, ML-01 등 포함).
- 출하 등록·확정은 SUP (target "출하", action 작성·확정). 재고 품목의 관리 역할 바꾸기는 MGR (target "설정").

#### 5.H.4 `notification_rule` 알림 규칙

| 항목 | 내용 |
|---|---|
| 설명 | 알릴지 말지와 중요도를 정하는 규칙. **규칙이 정하고 비서는 문장만** 붙인다. MGR만 바꾼다 |
| 쓰는 요구사항 | FR-AST-02-01~12·14·16~19, FR-AST-COM-15, FR-AST-03-07, FR-QLT-01-10·16·17·18 |
| 대략 건수 | 6.36 표의 행 수 (최종본 22행) |
| 출처 | 기획서 4.3·AST-02, DOC-07 10장. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| rule_code | 규칙 코드 | 코드 | PK | ○ | 6.36 (예: ALARM_STOP, REPEAT_ALARM, TARGET_RISK) [제안] | — |
| rule_name | 알림 종류 | 문자 | | ○ | 예: 반복 알람 | DOC-07 10장 |
| condition_text | 조건 | 문자 | | ○ | 예: "같은 설비·같은 알람이 7일 안에 3번 이상". 기준 숫자는 DOC-07 10장 값만 | DOC-07 10장 |
| importance | 중요도 | 코드 | | ○ | 6.35 (긴급 / 주의 / 참고) | 기획서 4.3 |
| is_enabled | 사용 | 참·거짓 | | ○ | — | FR-AST-02-16 |
| updated_by | 고친 사람 | 문자 | FK | — | → app_user, **MGR만** | FR-AST-02-16 |
| updated_at | 고친 시각 | 날짜시각 | | — | — | — |

- 기준 숫자(7일·3번 등)를 따로 칸으로 나눌지는 [선택 필요: 기술 회의]. 숫자는 DOC-07 10장 값만 쓴다.

#### 5.H.5 `notification` 알림

| 항목 | 내용 |
|---|---|
| 설명 | 규칙이 낸 알림 1건. 관련 기록을 하나 이상 가리킨다. 처리 여부는 24시간 규칙에 쓴다 |
| 쓰는 요구사항 | FR-AST-02-01~15·17·18·19, FR-AST-01-02·04·06, FR-AST-COM-21, FR-AST-03-07, FR-QLT-01-10·16·17·18, FR-INV-01-07, FR-ML-01-04, FR-MNT-04-04, NFR-AIQ-09 |
| 대략 건수 | 값 없음. 점검 목표: 평소 운전원 1명당 긴급+주의 10분에 1건 미만, 중요도 비율 긴급 약 5%·주의 약 15%·참고 약 80% [참고] |
| 출처 | 기획서 4.3·AST-02, DOC-07 10장, 기획서 12.4 `notification` |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| notification_id | 알림 번호 | 정수 | PK | ○ | 일련번호 | [제안] |
| rule_code | 알림 규칙 | 코드 | FK | ○ | → notification_rule | — |
| importance | 중요도 | 코드 | | ○ | 규칙의 중요도를 옮겨 둠 (규칙이 바뀌어도 과거 알림은 그대로) | 기획서 4.3 |
| raised_at | 발생 시각 | 날짜시각 | | ○ | — | — |
| message | 알림 문장 | 긴 문자 | | ○ | 비서가 쓰거나, 비서가 꺼져 있거나 **비서 출력이 정해진 JSON 칸 형식에 맞지 않으면** 기본 문구 (R-87) | FR-AST-02-14, NFR-AIQ-09 |
| related_info | 관련 정보 한 줄 | 긴 문자 | | — | 예: 지난 조치 작업기록서 번호 + **DOC-03 해당 절** (반복 알람 1·2단계), **DOC-07 §7.5의 해당 원인 조치 줄** (병목 발생·이동, R-84). 출처는 사내 문서 번호·§절만 | FR-AST-02-03·18·19, D-03 |
| message_source | 문장 출처 | 코드 | | ○ | 비서 문장 / 기본 문구 [제안] | FR-AST-02-14, NFR-AIQ-09 |
| repeat_count | 묶은 횟수 | 정수 | | ○ | 1부터. 같은 설비·같은 알람이 1분 안에 3번 이상이면 1건으로 묶고 횟수만 올림 | FR-AST-02-11 |
| is_flood | 폭주 묶음 | 참·거짓 | | ○ | 10분에 10건 넘으면 참, 10분에 5건 아래로 내려가면 풀림 | FR-AST-02-12 |
| report_rank | 보고 순위 | 코드 | | — | **계산**: 6.43 (0 안전 / 0-1 오래 방치 / 1 긴급 / 2 생산 위험 / 3 주의 / 4 참고). 브리핑·교대 보고서 인계·일일 보고서 "오늘의 문제"의 순서. 프로그램이 정하고 비서는 바꾸지 않는다 (R-73) | FR-AST-COM-21, R4 4.3 |
| is_processed | 처리됨 | 참·거짓 | | ○ | 24시간 넘게 거짓인 주의 알림은 보고 순위 **0-1** (잠금·표지 다음, 브리핑 위쪽) | FR-AST-02-13, FR-AST-01-06, R4 4.3 |
| process_kind | 처리 방법 | 코드 | | 조건 | 처리됨이면 필수. AUTO 자동 (알림이 요구한 기록이 생김) / MANUAL 사람 [처리]. 종류별로 6.36 아래 "알림 종류별 처리" 표 [제안] | FR-AST-02-13, UI설계서 9장 #4 |
| processed_by | 처리한 사람 | 문자 | FK | 조건 | → app_user. MANUAL이면 필수 — 그 알림 종류의 **책임 역할만** (6.36 아래 "알림 종류별 처리" 표). AUTO면 그 기록을 남긴 사람. 비서는 안 됨. [읽음]은 처리가 아님 (read_at은 notification_recipient) | FR-AST-02-13, UI설계서 9장 #4·SCR-07, 기획서 4.4 |
| process_memo | 처리 메모 | 긴 문자 | | 조건 | 반복 알람을 사람이 처리하면 **조치 계획 한 줄 필수**, 그 밖은 선택 | UI설계서 SCR-07 [4] |
| processed_at | 처리 시각 | 날짜시각 | | 조건 | 처리됨이면 필수 | FR-AST-02-13 |
| alarm_event_id | 알람 | 정수 | FK | — | → alarm_event | — |
| equipment_id | 설비 | 문자 | FK | — | → equipment | — |
| lot_no | 로트 | 문자 | FK | — | → production_lot (납기 지연 위험) | — |
| item_no | 재고 품목 | 문자 | FK | — | → inventory_item (재고 부족) | — |
| pm_task_id | 정비 항목 | 문자 | FK | — | → pm_task (기한) | — |
| tool_id | 공구 | 문자 | FK | — | → tool (수명 90%) | — |
| wo_no | 작업지시서 | 문자 | FK | — | → maintenance_work_order (승인 대기, 수정) | — |
| bottleneck_log_id | 병목 기록 | 정수 | FK | — | → bottleneck_log | — |
| revision_id | 문서 버전 | 정수 | FK | — | → document_revision (수정 알림) | — |
| result_id | 검사 결과 | 정수 | FK | — | → inspection_result (관리도 이상) | DOC-06 5.3 |
| shift_id | 교대 | 문자 | FK | — | → shift (목표 미달 위험) | — |
| buffer_code | 재공 위치 | 코드 | FK | — | → wip_buffer (재공 경고) | DOC-07 10.1 |
| cmm_import_id | 결과 파일 | 정수 | FK | — | → cmm_import (CMM 결과 파일 오류) | R3 5.4, FR-QLT-01-17 |
| prev_stage_notification_id | 앞 단계 알림 | 정수 | FK | 조건 | → notification (자기 참조). **반복 알람 2단계 알림이면 필수**: 1단계 알림(조치 계획 한 줄이 있는 것) 또는 앞의 2단계 알림. 원인 점검 요청 알림은 그 2단계 알림을 가리킴 [제안: 칸] | R4 3.2, FR-AST-02-18 |
| repeat_stage_status | 반복 알람 단계 상태 | 코드 | | 조건 | 6.54. **REPEAT_ALARM·REPEAT_ALARM_2 알림이면 필수**. 1단계: 열림 → **1단계 닫힘**(조치 계획 한 줄 저장) → (7일 안 재발 → 2단계 알림 생김) / 7일 재발 없음 → 효과 확인. 2단계: 열림 → 원인 점검 확정(원인 점검 기록 확정) → **효과 확인**(확정 뒤 7일 재발 없음) / 재발 → 다시 2단계 | D-09, R4 3.2·3.3, 2026-10-07 총괄 정정 |
| effect_check_due_at | 효과 확인 기한 | 날짜시각 | | — | **계산**: 1단계 = 조치 계획 저장 시각(조치 작업이 있으면 그 기록 확정 시각) + 7일, 2단계 = 원인 점검 기록 확정 시각 + 7일. 이 시각까지 같은 설비·같은 알람이 없으면 "효과 확인" | R4 3.3 나안 [가상] 7일 |

- 관련 FK는 알림 종류에 따라 최소 1개가 있어야 한다 (8장 R-38). 어떤 FK가 필수인지는 6.36 표의 "가리키는 기록" 칸.
- 보고 순위는 알림이 아닌 항목(잠금·표지 중 설비, 지금 DOWN인 설비, 보류·강화 로트 등)에도 같은 6.43 순위를 쓴다. 그런 항목은 저장하지 않고 화면·보고서에서 계산한다.

#### 5.H.6 `notification_recipient` 알림 받는 사람

| 항목 | 내용 |
|---|---|
| 설명 | 알림을 누구에게 보냈는지. 긴급은 해당 설비 작업자·보전 담당자에게 팝업 + 소리 |
| 쓰는 요구사항 | FR-AST-02-02, FR-AST-03-07 |
| 대략 건수 | 값 없음 |
| 출처 | 기획서 4.3·4.5. 엔터티는 [제안] |

| 속성(영문) | 한국어 이름 | 논리 형식 | 키 | 필수 | 값·규칙 | 출처 |
|---|---|---|---|---|---|---|
| notification_id | 알림 | 정수 | PK, FK | ○ | → notification | — |
| user_id | 받는 사람 | 문자 | PK, FK | ○ | → app_user | 기획서 4.3 |
| popup_sound | 팝업과 소리 | 참·거짓 | | ○ | 긴급만 참 | 기획서 4.3, FR-AST-02-02 |
| read_at | 읽은 시각 | 날짜시각 | | — | — | [제안] |

---

## 6. 코드 목록

- **한국어 이름은 출처 문서 값 그대로** 쓴다. 영어 대문자 코드는 [제안] (물리 ERD에서 그대로 쓰거나 바꿀 수 있음). 이미 실제 값이 있는 코드(RUN, ACTIVE, F01, OP-10 등)는 그대로 쓴다.
- 코드 목록을 별도 표(엔터티)로 둘지, 값 제약으로 둘지는 물리 ERD에서 정한다 [선택 필요: 기술 회의]. 이 문서에서 엔터티로 둔 것: 공정, 정지 사유, 알람, 센서, 재고 품목, 공구 종류, 검사 항목, 불량 코드, 역할, 알림 규칙.

### 6.1 설비 상태 (`equipment_state_log.state_code`)

| 코드 | 이름 | 실제 데이터 값 | 판단 조건 | 화면 표시 (색 규칙 C) | 출처 |
|---|---|---|---|---|---|
| RUN | 가공 중 | ACTIVE (Q500 BUSY) | 로트가 있고 알람이 없음 | 진한 회색 + 옅은 초록 테두리 + "가공" | DOC-07 2.2 |
| IDLE | 대기 | READY (Q500 IDLE) | 앞 재공 0 (앞 공정 대기) 또는 로트 없음. 주의 등급 알람으로 멈춘 시간도 IDLE + ▲ | 밝은 회색 + "대기" | DOC-07 2.2 |
| BLOCKED | 막힘 | READY | 뒤 재공이 한도에 참 (30개, WIP-30-40만 60개) | 주황 + ⛔ + "막힘" | DOC-07 2.2·7.2 |
| SETUP | 셋업(준비) | (작업자 입력) | 작업지시 교체 10~20분, 공구 교체 3~8분 | 회색 + 🔧 + "준비" | DOC-07 2.2 |
| DOWN | 고장 정지 | STOPPED + 정지 등급 알람 | 정지 등급 알람으로 멈춘 때부터 다시 가공할 때까지 | 빨강 + ⚠ + "고장" | DOC-07 2.2, 기획서 19장 |
| MAINT | 계획 정비 | (정비 작업 진행 기록) | 예방 정비 시간 | 회색 빗금 + "정비" | DOC-07 2.2 |

- 상태 이름 6개와 판단 조건은 [가상], 실제 데이터 값(ACTIVE·READY·STOPPED)은 [실제: Haas MTConnect `Execution`].

### 6.2 실제 데이터 값 (`mtconnect_execution`)

| 코드 | 뜻 | 대응 상태 | 출처 |
|---|---|---|---|
| ACTIVE | 실행 중 | RUN | DOC-07 2.2 [실제] |
| READY | 준비됨 (실행 안 함) | IDLE, BLOCKED | DOC-07 2.2 [실제] |
| STOPPED | 멈춤 | DOWN | DOC-07 2.2 [실제] |
| (비움) | 작업자 입력 또는 정비 기록 | SETUP, MAINT | DOC-07 2.2 |

### 6.3 알람 심각도 (`alarm_master.severity`)

| 코드 | 이름 | 판단 규칙 | 설비 상태 | 문서 흐름 (OP-30) | 알림 중요도 | 출처 |
|---|---|---|---|---|---|---|
| STOP | 정지 | 축 정지·서보 꺼짐·충돌·단락·과전류, 제어반을 열거나 차단기를 다시 올려야 함, 식을 때까지 기다려야 함 | DOWN | 지침카드 → 작업지시서 → 작업기록서 | 긴급 | DOC-02 2장 [가상] |
| WARN | 주의 | 작업자가 보충·조건 조정·공구 교체로 바로 다시 돌릴 수 있음 | 짧은 정지 5~25분 (IDLE + ▲) | 지침카드 + 간이 작업기록 | 주의 | DOC-02 2장 [가상] |
| GUIDE | 조작 안내 | 프로그램·설정·모드 오류 | 대기 1~5분 (IDLE) | 지침카드만 | 참고 | DOC-02 2장 [가상] |

- OP-10·20·40·50은 정지 등급이어도 **지침카드 + 간이 작업기록**까지만 (작업지시서는 OP-30만). 반복 알람 2단계도 같다: 원인 점검 작업지시서는 OP-30만, 다른 공정은 MNT 원인 점검 요청 + 간이 작업기록 (R-71).

### 6.4 조치 담당 (`alarm_master.responder`, `pm_task.default_role`)

| 코드 | 이름 | 출처 |
|---|---|---|
| OPR | 작업자 | DOC-02 3장 "누가" |
| MNT | 보전 담당자 | DOC-02 3장 |

### 6.5 정지 사유 (`downtime_reason`, 18개)

| 그룹 | 코드 | 사유 | 보통 상태 | 6대 로스 [참고: NCS] |
|---|---|---|---|---|
| 고장 (FAILURE) | F01 | 서보·앰프 | DOWN | 고장 정지 로스 |
| | F02 | 주축 | DOWN | 고장 정지 로스 |
| | F03 | 공구 교환장치 | DOWN | 고장 정지 로스 |
| | F04 | 윤활 | DOWN (주의 등급이면 IDLE + ▲) | 고장 정지 로스 |
| | F05 | 공압 | DOWN (주의 등급이면 IDLE + ▲) | 고장 정지 로스 |
| | F06 | 절삭유 | DOWN | 고장 정지 로스 |
| 자재·흐름 (MATERIALS) | M01 | 소재 대기 | IDLE | (설비 밖 원인) |
| | M02 | 앞 공정 대기 | IDLE | (흐름 손실) |
| | M03 | 뒤 공정 막힘 | BLOCKED | (흐름 손실) |
| 준비 (SETUP) | S01 | 작업지시 교체 (로트 교체) | SETUP | 준비 교체 로스 |
| | S02 | 공구 교체 | SETUP | 준비 교체 로스 |
| | S03 | 초품 검사 | SETUP | 준비 교체 로스 |
| 조작 (OPERATION) | O01 | 프로그램 오류 | IDLE (1~5분) | 순간 정지 로스 |
| | O02 | 모드 오류 | IDLE (1~5분) | 순간 정지 로스 |
| | O03 | 도어 열림 | IDLE (1~5분) | 순간 정지 로스 |
| 계획 (PLANNED) | P01 | 예방 정비 | MAINT | (계획 정지 — 손실 아님) |
| | P02 | 휴식 | — | (계획 가동 시간 밖) |
| | P03 | 계획 없음 | — | (계획 가동 시간 밖) |

출처: DOC-07 5.1 (코드 번호 [가상], 그룹 [참고: 벽돌 라인 정지 기록]).

### 6.6 정지 사유 상태 (`equipment_state_log.reason_status`)

| 코드 | 이름 | 누가 | 출처 |
|---|---|---|---|
| SUGGESTED | 추천 (AI비서 초안) | 비서 | 기획서 4.4 [제안: 코드] |
| ENTERED | 입력 | OPR, MNT | 기획서 13.2 |
| CONFIRMED | 확정 | SUP | 기획서 13.2 |

### 6.7 생산 작업지시 상태 (`production_order.status`)

| 코드 | 이름 | 다음 | 출처 |
|---|---|---|---|
| WAITING | 대기 | 생산 중, 취소 | 설계서 5.5, DOC-07 4.2 |
| IN_PROGRESS | 생산 중 | 완료, 취소 | 같음 |
| DONE | 완료 | — | 같음 |
| CANCELLED | 취소 | — | 같음 |

### 6.8 생산 로트 상태 (`production_lot.status`)

| 코드 | 이름 | 뜻 | 누가 바꾸나 | 다음 상태 | 출처 |
|---|---|---|---|---|---|
| IN_PROCESS | 생산 중 | OP-10~40 진행 중 | 시스템 | 검사 대기 | DOC-06 4.1 |
| WAIT_INSPECTION | 검사 대기 | OP-50 도착, 검사 전 | 시스템 | 판정 대기, 보류 | DOC-06 4.1 |
| WAIT_JUDGEMENT | **판정 대기** | 게이지·육안은 끝났고, 온도 맞춤 중인 측정 부품이 남음 | 시스템 | 합격, 보류 검토 | **설계서 5.15**, DOC-06 4.1 (같은 날 줄 추가, 12장 #1) |
| HOLD_REVIEW | 보류 검토 | 측정한 부품 중 1개라도 불합격. 남은 부품은 전수 | 시스템이 표시 | 보류, 합격 (반장이 측정 오류로 확인) | DOC-06 4.1, 설계서 5.15 |
| PASSED | 합격 (출하 가능) | 측정·게이지·육안 모두 합격. **판정 시각에 합격 수량이 완제품 재고로 들어옴** (R-69) | 시스템 | — | DOC-06 4.1, DOC-06 §4.3 |
| ON_HOLD | 보류 | 출하·다음 공정 이동 금지. 검사 강화 대상 | **SUP** (MGR) | 해제, 폐기 | DOC-06 4.1, 기획서 13.2 |
| RELEASED | 해제 | 전수 검사로 불량을 골라낸 뒤 나머지를 출하 가능으로. **해제 시각에 고른 합격 수량만 완제품 재고로** (폐기 수량은 안 들어옴) | **SUP** (MGR) | 합격 | DOC-06 4.1, R5 표 A3 |
| SCRAPPED | 폐기 | 로트 전체 폐기 (부분 폐기는 `scrap_qty`만 늘고 해제로 감) | 반장 제안 → **MGR 승인** | — | DOC-06 4.1 |

- 상태 흐름: 생산 중 → 검사 대기 → (판정 대기) → 합격 / 보류 검토 → 보류 → 해제·폐기. 이 순서로만 바뀐다 (FR-PRD-05-04).
- **출하할 수 있는 상태는 합격·해제뿐**이다. 생산 중·검사 대기·판정 대기·보류 검토·보류·폐기 로트는 완제품 재고가 아니고 출하할 수 없다 (판정 대기·보류 검토·보류는 "보류 수량"으로 따로 보임, R-67·R-69, R5 1.6). 이미 출하한 로트는 보류할 수 없고, 로트 추적에 "출하됨 — SHP-…"을 보인다.
- 의심 로트는 **상태가 아니다.** 비서의 제안이고 상태를 바꾸지 않는다. 알림 종류도 아니다 — 지침카드 생산 영향 칸과 로트 추적 화면에만 보인다 (FR-PRD-05-05, UI설계서 SCR-09 [7]·SCR-19 [3]). 저장하는 엔터티는 없고, 반장이 보류하면 `lot_hold.trigger_type` = AI_SUSPECT로 남는다.

### 6.9 원자재 로트 상태 (`raw_material_lot.status`)

| 코드 | 이름 | 출처 |
|---|---|---|
| WAIT_RECEIPT_CHECK | 입고 검사 대기 | DOC-06 §7 순서 3 "생산 흐름에 내보내기 전에 끝낸다" → [제안] |
| AVAILABLE | 사용 가능 | DOC-06 §7 순서 5 |
| RECEIPT_HOLD | 입고 보류 | DOC-06 §7 순서 5 |

- 입고 검사 전 상태를 **따로 둔다** [제안]: 입고 등록(**SUP** — 최종본, 원자재 관리 역할) → 입고 검사 대기(성적서 대조도 SUP) → 성적서 대조 결과로 사용 가능 / 입고 보류. 사용 가능이 아닌 원자재 로트는 생산 로트(OP-10 투입)에 쓸 수 없다 (R-06a). 근거: DOC-06 §7 순서 3·5, UI설계서 9.3 #1, FR-INV-01-04. 과거 생성 데이터는 모두 사용 가능.

### 6.10 교대 구분 (`shift.shift_type`)

| 코드 | 이름 | 시간 | 출처 |
|---|---|---|---|
| DAY | 주간 | 08:00~17:00 | 설계서 5.2 [가상] |
| NIGHT | 야간 | 20:00~다음 날 05:00 | 설계서 5.2 [가상] |

### 6.11 병목 원인 (`bottleneck_log.cause_code`)

| 코드 | 번호 | 원인 | 병목 위치 | 손실 | 출처 |
|---|---|---|---|---|---|
| C1 | ① | 사이클 시간 증가 (공구 수명 80% 넘음, 7.0 → 8.0~8.5분) | OP-30 | 속도 손실 | 설계서 5.18, DOC-07 7.4 |
| C2 | ② | 설비 1대만 가동 (예방 정비·긴 셋업) | OP-30 | 속도 손실 | 같음 |
| C3 | ③ | 검사 강화 (0.9 → 5.0분/개) | OP-50 | 속도 손실 | 같음 |
| C4 | ④ | 묶음 대기 (OP-40 30개 묶음) — **병목 판단에서 제외** | OP-30→40 사이 | — | 같음 |
| FAILURE | (고장) | 설비 DOWN | 멈춘 공정 | 고장 손실 | 같음 |
| BASE | — | 조건에 맞는 공정이 없어 기준 병목 OP-30으로 돌아옴 | OP-30 | — | DOC-07 7.3 ④ (코드는 [제안]) |

### 6.12 보류 계기 (`lot_hold.trigger_type`)

| 코드 | 이름 | 출처 |
|---|---|---|
| AI_SUSPECT | AI 비서 의심 로트 제안 (정지 등급 알람·공구 수명 초과 중 가공) → 반장 보류 | DOC-06 3.3 ②·4.2 |
| INSPECTION_FAIL | 측정 불합격 → 보류 검토 → 반장 보류 | DOC-06 3.3 ① |
| SUPERVISOR | 반장 판단 (그 밖) | [제안] |

### 6.13 작업지시서 상태 (`maintenance_work_order.status`)

| 코드 | 이름 | 누가 바꾸나 | 다음 | 출처 |
|---|---|---|---|---|
| AI_DRAFT | AI비서 초안 | 시스템 (OP-30 정지 등급 알람, **OP-30 반복 알람 2단계**면 자동 — 계기 6.42) | 수정 중, 취소 | 기획서 MNT-03, FR-MNT-03-01 |
| EDITING | 수정 중 | MNT | 승인, 취소 | 같음 |
| APPROVED | 승인 | SUP (MGR 대리) — 담당자가 있어야 함 | 진행 중, 취소 | 같음, 기획서 13.1 |
| IN_PROGRESS | 진행 중 | MNT ([작업 시작]) | 완료 | 같음, UI설계서 SCR-11 |
| DONE | 완료 | 시스템 (짝 작업기록서 확정 때 자동) [제안] | — | 같음, UI설계서 9.3 #3 |
| CANCELLED | 취소 | MGR | — | 기획서 13.1 |

- 승인 전에는 진행 중으로 바꿀 수 없다 (FR-MNT-03-02). **완료 계기 = 짝 작업기록서(work_record.wo_no) 확정** — [완료] 버튼은 없다 (작업지시서 1 : 작업기록서 1, FR-MNT-05-01, UI설계서 SCR-11 [1]).

### 6.14 작업기록서 종류 (`work_record.record_type`)

| 코드 | 이름 | 번호 형식 | 언제 | 출처 |
|---|---|---|---|---|
| FULL | 작업기록서 | MR-0901 | OP-30 정지 등급 알람의 작업지시서 1건마다 | 설계서 5.11 |
| SIMPLE | 간이 작업기록 | MR-S-0901 | OP-30 주의 등급 알람, OP-10·20·40·50의 정지·주의 등급 알람마다. **최종본: 다른 공정 반복 알람 2단계의 원인 점검 요청마다** (cause_check_notification_id, 확정 = MNT) | 설계서 5.11, 기획서 5.2, R4 3.2 |

### 6.15 작업기록서 상태 (`work_record.status`)

| 코드 | 이름 | 누가 | 작업기록서 | 간이 작업기록 | 출처 |
|---|---|---|---|---|---|
| AI_DRAFT | AI비서 초안 | 비서 (작업지시서 + 메모 정리) | ○ | — (조치를 고름) | 기획서 MNT-05 |
| EDITING | 수정 중 | MNT / 간이는 OPR·MNT | ○ | ○ | 같음 |
| CONFIRMED | 확정 | MNT / 간이: 주의 등급 OPR·MNT, 다른 공정 정지 등급 MNT만 | ○ | ○ | 기획서 13.1, UI설계서 9장 #5 |
| CHECKED | 확인 | SUP | ○ | — | 기획서 5.1·13.1 |

- 간이 작업기록에는 **AI비서 초안 단계를 두지 않는다** — 작업자가 DOC-03 조치 선택지에서 골라 확정한다 (기획서 5.2, UI설계서 SCR-13, FR-MNT-05-13). 첫 저장 버전이 v0(사람).
- 작업기록서가 확인(CHECKED) 뒤 확정 후 수정되면 확인 표시가 풀려 SUP가 다시 확인한다 [제안] (FR-AST-03-06).

### 6.16 보고서 상태 (`shift_report.status`, `daily_report.status`)

| 코드 | 이름 | 뜻 | 출처 |
|---|---|---|---|
| AI_DRAFT | AI비서 초안 | v0. 교대 보고서는 교대 끝(17:00, 05:00), 일일 보고서는 **생산일 다음 날 06:00**에 자동 생성 (R-72) | 기획서 4.5, D-08 |
| EDITING | 수정 중 | 사람이 고침 (v1, v2 …) | 기획서 4.5 |
| CONFIRMED | 확정 | 잠김. 고칠 수 없음 | 기획서 4.5 |
| REVISED | 확정 후 수정 | 확정 뒤 고친 새 버전 (사유 필수). **다시 확정 절차 없음** — 확정 권한자만 고칠 수 있고, 저장하면 그 버전이 바로 확정본(잠김) [제안] | 기획서 4.5, FR-AST-03-06, UI설계서 2.6·9.3 #2 |

### 6.17 문서 종류 (`document_revision.doc_type`)

| 코드 | 이름 | doc_key가 가리키는 것 | 출처 |
|---|---|---|---|
| WORK_ORDER | 작업지시서 | maintenance_work_order.wo_no | FR-AST-03-01 |
| WORK_RECORD | 작업기록서 (간이 포함) | work_record.record_no | 같음 |
| SHIFT_REPORT | 교대 보고서 | shift_report.shift_id | 같음 |
| DAILY_REPORT | 일일 보고서 | daily_report.work_date | 같음 |
| INTERNAL_DOC | 사내 문서 (**용어집 포함** — GLOSSARY, 6.52) | internal_doc.doc_no | 같음, D-05 |
| PM_RECORD | 예방 정비 실시 기록 | pm_record.pm_record_id | FR-AST-03-01 (같은 날 추가), DOC-04 5장 |
| SHIPMENT | 출하 기록 (최종본 추가) [제안] | shipment.shipment_no | R5 표 C "확정 뒤 수정은 사유 필수 (FR-AST-03 모양)" |

- 지침카드(화면)는 문서 종류가 아니다 (확정하지 않음).
- 출하 기록을 **넣었다** [제안]: 확정하면 완제품 재고가 빠지는 기록이라 고친 내역(누가·언제·사유)이 필요하다 (NFR-REL-02·03, R5 표 C). 요구사항 FR-AST-03-01·기획서 AST-03·4.5·UI설계서 SCR-17도 일곱 종류로 맞췄다 (교차 점검 2026-10-07, 12장 #17).
- 예방 정비 실시 기록을 **넣었다** [제안]: 기획서 4.5 "모든 문서에 버전, 수정한 사람, 시각, 바뀐 내용, 사유가 남는다", DOC-04 5장 "확정한 기록을 고치면 수정 이력(AST-03)에 남는다", 확정하면 재고가 빠지는 기록이라 고친 내역이 필요하다 (NFR-REL-02·03). 기획서_최종본 AST-03 표·13.1에도 반영됐다 (최종본에서 출하 기록을 더해 일곱 종류, 12장 #6·#17). 보기 권한은 13.1 "수정 이력" 줄을 따른다.

### 6.18 작성 주체 (`author_kind`, `proposed_by_kind`)

| 코드 | 이름 | 출처 |
|---|---|---|
| AI | AI 비서 (AI비서 초안) | 기획서 4.5 |
| HUMAN | 사람 | 기획서 4.5 |

### 6.19 잠금·표지 단계 (`work_record_check.loto_step_code`) — 고정 서식

| 코드 | 원문 제목 [실제] | 구분 |
|---|---|---|
| 6.1 | 기기 등의 운전정지 준비 | 작업 전 |
| 6.2 | 기기 등의 운전정지 | 작업 전 |
| 6.3 | 기기 등의 차단 | 작업 전 |
| 6.4 | 잠금장치 또는 표지의 설치 | 작업 전 |
| 6.5 | 저장 또는 축적된 에너지의 관리 | 작업 전 |
| 6.6 | 차단 확인 | 작업 전 |
| 7.1 | 기기 등의 점검 | 작업 후 |
| 7.2 | 작업자 확인 | 작업 후 |
| 7.3 | 잠금장치·표지의 제거 | 작업 후 |

출처: KOSHA GUIDE B-M-25-2026 (DOC-05 §2.1·2.2, 기획서 MNT-03). **글자를 바꾸지 않는다** (공공누리 변경금지, NFR-COPY-03).

### 6.20 잠금·표지 판단 (`lockout_level`)

| 코드 | 이름 | 예 | 출처 |
|---|---|---|---|
| FULL | §2 전부 (6+3단계 + 설비 차단 지점 전부) | 정지 등급 알람 조치, 절삭유 탱크 교체 | DOC-05 §1·§2.4 |
| TWO_POINT | 보충용 2점 잠금 (주 차단기 E1 + 공압 주 밸브 P1) | 축 윤활유 보충 (2075), 주축 윤활유 보충 | DOC-05 §2.4 |
| ONE_POINT | 1점 잠금 | SAW-01 가이드 레일 윤활유 보충 (SAW-01-E1), WSH-01 텀블러 그리스 (WSH-01-E2) | DOC-05 §2.4 |
| UNPLUG | 플러그 뽑기 (자물쇠 없음) | WSH-01 세척액 보충·교체 | DOC-05 §2.4 |
| NONE | 없음 | 탱크 수위 확인만, 절삭유 보충 | DOC-05 §2.4 |

### 6.21 에너지 종류 (`isolation_point.energy_type`)

| 코드 | 이름 | 출처 |
|---|---|---|
| ELEC | 전기 | DOC-05 §3 |
| ELEC_SUPPLY | 전기 (공급원) — 공급 분전반 차단기 | DOC-05 §3 |
| AIR | 공압 | DOC-05 §3 |

### 6.22 예방 정비 주기 (`pm_task.cycle_code`)

| 코드 | 이름 | 출처 |
|---|---|---|
| DAILY | 매일 | DOC-04 2.1·3장 |
| WEEKLY | 매주 | DOC-04 2.2·3장 |
| MONTHLY | 매월 | DOC-04 2.3·3.1 |
| HALF_YEAR | 6개월 | DOC-04 2.5 |
| YEARLY | 1년 | DOC-04 2.6·3.1 |
| AS_REQUIRED | 필요할 때 | DOC-04 2.7 |
| EVERY_8H_USE | 8시간 사용마다 | DOC-04 3.3 (OP-40 텀블러) |

- 3개월은 VF-2 표준 사양에 해당 항목이 없어 코드를 두지 않는다 (DOC-04 2.4).

### 6.23 예방 정비 결과 (`pm_record.result`)

| 코드 | 이름 | 출처 |
|---|---|---|
| NORMAL | 정상 | DOC-04 5장 |
| REFILLED | 보충·교체함 | DOC-04 5장 |
| ABNORMAL | 이상 있음 (OP-30은 작업지시서, 다른 공정은 간이 작업기록) | DOC-04 5장 |

### 6.24 공구 사용량 단위 (`tool_type.usage_unit`)

| 코드 | 이름 | 쓰는 공구 | 출처 |
|---|---|---|---|
| HOLES | 구멍 수 | M6 탭, 드릴, 보링바 인서트 | DOC-07 9장 [실제: Haas ATM] |
| FEED | 이송 시간 (분) | 엔드밀, 페이스밀 인서트 | 같음 |

- Haas ATM의 USAGE(호출 횟수)는 쓰지 않는다. LIFE(남은 수명 비율)는 "남은 수명"으로 계산한다.

### 6.25 공구 종류 (`tool_type`, 5개)

| 품목 번호 | 공구 | 공구 번호 [가상] | 단위 | 부품 1개당 [가상] | 수명 한도 | 한도 근거 | 교체 1회 차감 |
|---|---|---|---|---|---|---|---|
| TL-FM50 | 페이스밀 인서트 | T01 | 이송 시간 | 0.5분 | 400분 (약 부품 800개) | [가상] | 5 |
| TL-EM10 | 엔드밀 Ø10 | T02 | 이송 시간 | 2.5분 | 200분 (약 부품 80개) | [참고] | 1 |
| TL-BB45 | 보링바 인서트 (Ø45 H7) | T03 | 구멍 수 | 1 | 400구멍 (약 부품 400개) | [가상] | 1 |
| TL-DR50 | 드릴 Ø5.0 | T04 | 구멍 수 | 4 | 1,000구멍 (약 부품 250개) | [가상] | 1 |
| TL-TAP6 | M6 탭 | T05 | 구멍 수 | 4 | 400구멍 (약 부품 100개) | [참고] | 1 |

출처: 설계서 5.13·5.14, DOC-07 9장, DOC-01 7.1. 공구 번호는 [가상]: T05(M6 탭)만 설계서 7장 S3에 먼저 있었고, 나머지는 가공 순서(면 → 외곽·포켓 → 압입 구멍 보링 → M6 아랫구멍 → 나사)로 같은 날 정했다. 두 대(VF2-01·02)가 같은 번호를 쓴다.

### 6.26 공구 쓰임·교체 사유 (`tool.tool_role`, `tool_change.change_reason`) [제안]

| 칸 | 코드 | 이름 | 근거 |
|---|---|---|---|
| tool_role | IN_USE | 사용 중 | 설계서 5.13 |
| tool_role | SPARE | 예비 | 설계서 5.13 "+ 예비" |
| change_reason | LIFE_90 | 수명 90% 교체 알림을 보고 교체 | DOC-07 9장 |
| change_reason | ALARM_362 | 알람 362 공구 수명 한계 도달 | 설계서 5.13 |
| change_reason | ALARM_174 | 알람 174 공구 부하가 초과됨 | 설계서 5.13 |
| change_reason | BROKEN | 파손 ("일부는 일찍 파손") | 설계서 5.13 |
| change_reason | OTHER | 기타 | — |

### 6.27 재고 품목 (`inventory_item`, 13개)

| 구분 (category) | 품목 번호 | 품목 | 단위 | 안전 재고 (처음 값) | 관리 역할 (owner_role) | 사용(차감) 기록 |
|---|---|---|---|---|---|---|
| 공구 TOOL | TL-EM10 | 엔드밀 Ø10 | 개 | 9 | SUP | OPR·MNT 공구 교체 |
| 공구 TOOL | TL-DR50 | 드릴 Ø5.0 (M6 탭 아랫구멍) | 개 | 5 | SUP | 같음 |
| 공구 TOOL | TL-TAP6 | M6 탭 | 개 | 8 | SUP | 같음 |
| 공구 TOOL | TL-BB45 | 보링바 인서트 | 개 | 4 | SUP | 같음 |
| 공구 TOOL | TL-FM50 | 페이스밀 인서트 | 개 | 14 | SUP | 같음 |
| 소모품 CONSUMABLE | CS-WLUB | 축 윤활유 | L | 4 | MNT | 작업기록서·예방 정비 기록 |
| 소모품 CONSUMABLE | CS-COOL | 절삭유 원액 (TRIM SC538) | L | 20 | MNT | 같음 |
| 소모품 CONSUMABLE | CS-CFLT | 절삭유 필터 | 개 | 2 | MNT | 같음 |
| 소모품 CONSUMABLE | CS-AFLT | 공기 필터 | 개 | 2 | MNT | 같음 |
| 소모품 CONSUMABLE | CS-SLUB | 주축 윤활유 (Mobil 1 0W-20) | L | 4 | MNT | 같음 |
| 소모품 CONSUMABLE | CS-GRS | 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) | 개 | 2 | MNT | 같음 |
| 원자재 MATERIAL | RM-6061 | 6061-T6 봉재 | 개분 | 200 | SUP (입고 검사 = 성적서 대조도 SUP) | 로트 투입 때 자동 |
| **완제품 FINISHED** | **FG-BRK-A100** | **BRK-A100 완제품** | 개 | **없음** (부족 알림 없음) [제안] | SUP | 출하 기록 (SUP) |

출처: 설계서 5.14·15.5 (품목 번호·안전 재고 [가상], 식 [참고: NCS]). 세척액(OP-40)·다른 공정 윤활유는 품목이 아니다 (DOC-04 4.6). 완제품 품목 번호는 R5 표 A1 예 [가상]. 관리 역할은 D-13, R5 표 D (근거: NCS 공작기계 보전관리·치공구 관리·자재창고 운영관리 [참고]). 안전 재고는 모든 품목 MGR이 정함.

### 6.28 거래 종류·출처 (`inventory_txn`)

| 칸 | 코드 | 이름 | 생기는 조건 | 출처 |
|---|---|---|---|---|
| txn_type | IN | 입고 | 공구·소모품 주 1회, 원자재 주 3회 | 설계서 5.14 |
| txn_type | USE | 사용 | 공구 교체, 작업기록서 사용 부품, 예방 정비 소모품, 로트 투입 | 설계서 5.14 |
| txn_type | ADJUST | 조정 | 월말 실사 차이 1~2건 (완제품 0~1건, ±1~2개) | 설계서 5.14, R5 1.7 G9 |
| txn_type | FG_IN | 완제품 합격 입고 (최종본) | 로트가 합격(해제)된 순간, 합격 수량 + | D-14, R5 표 A2·A3 |
| txn_type | SHIP_OUT | 출하 출고 (최종본) | 출하 확정 때 로트 줄마다, 수량 − | D-14, R5 표 A5 |
| source_kind | RECEIPT | 입고 등록 (공구·소모품) | **품목 관리 역할이 등록**: 공구 SUP, 소모품 MNT | FR-INV-01-04, D-13 |
| source_kind | MATERIAL_RECEIPT | 원자재 입고 | raw_material_lot 1건. SUP가 등록 | 설계서 5.4, D-13 |
| source_kind | LOT_PASS | 로트 합격 (최종본) | 완제품 합격 입고 1건 (fg_lot_no). 시스템 | R5 표 B |
| source_kind | SHIPMENT | 출하 (최종본) | 출하 로트 줄 1개마다 1건 (shipment_no, ship_lot_no) | R5 표 B |
| source_kind | WORK_RECORD | 작업기록서 | 확정 때 사용 부품마다 | FR-MNT-05-10 |
| source_kind | PM_RECORD | 예방 정비 | 확정 때 쓴 소모품 (절삭유 보충 = 보충량 × 약 3%) | FR-MNT-04-06, DOC-04 4.2 |
| source_kind | TOOL_CHANGE | 공구 교체 | 교체 1회 = 1개 (페이스밀 5개) | 설계서 5.13 |
| source_kind | LOT_INPUT | 로트 투입 | 로트 투입 수량만큼 RM-6061 | FR-INV-01-03 |
| source_kind | STOCKTAKE | 월말 실사 | 조정. **품목 관리 역할이 기록** (소모품 MNT, 공구·원자재·완제품 SUP), 사유 필수 | 설계서 5.14, D-13, R5 표 A8 |

### 6.29 검사 항목 (`inspection_item`, 8개)

| 번호 | 항목 | 기준 | 측정 방법 | 특성 | Cpk 기준 | 발췌 측정 |
|---|---|---|---|---|---|---|
| 1 | 부싱 압입 구멍 지름 | Ø45 H7 = +0.025 / 0 mm (45.000~45.025) | 3차원 측정기 | 특별 특성 ◆ | 1.67 | ○ |
| 2 | 전체 길이 | 150 ± 0.5 mm | 3차원 측정기 | 일반 | 1.33 | ○ |
| 3 | 두께 | 12 ± 0.2 mm | 3차원 측정기 | 일반 | 1.33 | ○ |
| 4 | 구멍 간 거리 | ± 0.1 mm | 3차원 측정기 | 일반 | 1.33 | ○ |
| 5 | 평면도 (부착면) | 0.05 mm 이하 | 3차원 측정기 | 일반 | 1.33 | ○ |
| 6 | M6 나사 (6H) | 통과 게이지 끝까지, 정지 게이지 2회전 넘게 안 들어감 | 나사 통과·정지 게이지 | 일반 | — | ○ (나머지 부품도 게이지) |
| 7 | 외관 | 버·찍힘·구성인선 흔적 없음 | 육안 | 일반 | — | — (전 부품 육안) |
| 8 | 폭 | 55 ± 0.3 mm | 3차원 측정기 | 일반 | 1.33 | ○ |

출처: DOC-06 §2·§3.2·§5.2, 설계서 5.15 (등급 [실제], 치수 [가상]).

### 6.30 특성 구분 (`inspection_item.char_class`)

| 코드 | 이름 | 출처 |
|---|---|---|
| SPECIAL | 특별 특성 ◆ | DOC-06 §2 [가상] |
| GENERAL | 일반 | DOC-06 §2 |

### 6.31 측정 방법 (`inspection_item.method`)

| 코드 | 이름 | 출처 |
|---|---|---|
| CMM | 3차원 측정기 | DOC-06 §2 |
| GAUGE | 나사 통과·정지 게이지 | DOC-06 §2 |
| VISUAL | 육안 | DOC-06 §2 |

### 6.32 검사 구분·검사 방식·강화 사유

| 칸 | 코드 | 이름 | 뜻 | OP-50 시간 [가상] | 출처 |
|---|---|---|---|---|---|
| insp_kind (부품) | FIRST | 초품 | 작업지시 교체·새 로트·공구 교체 뒤·정지 등급 알람 뒤 첫 부품, 전 항목 | — | DOC-06 §3.1 |
| insp_kind (부품) | SAMPLE | 발췌 | 첫 부품 + 5개마다 1개 | 측정 2.5분/개 | DOC-06 §3.2·3.4 |
| insp_kind (부품) | ENHANCED | 강화 | 모든 부품 + 항목 확대 | 5.0분/개 | DOC-06 §3.3·3.4 |
| plan_mode (로트) | NORMAL | 보통 (발췌) | 평소 | 평균 약 0.9분/개 | DOC-06 §3 |
| plan_mode (로트) | ENHANCED | 검사 강화 (전수 + 항목 확대) | 보류 로트와 다음 1~2개 | 5.0분/개 | DOC-06 §3.3 |
| enhance_reason | HOLD_LOT | 보류 로트 | 반장이 보류한 로트 | — | DOC-06 §3.3 ① |
| enhance_reason | NEXT_LOT | 보류 다음 로트 | 다음 1개 (공구 원인·교체 완료) 또는 2개 (충돌·정지 등급·원인 모름) | — | DOC-06 §3.3 ② |

- Cpk 미달 전수는 로트 단위가 아니라 **항목 단위**라서 `inspection_item.is_full_check_by_cpk`에 둔다 (DOC-06 §5.2).

### 6.33 판정 (`judgement`)

| 칸 | 코드 | 이름 | 출처 |
|---|---|---|---|
| inspection_result | PASS | 합격 | DOC-06 §3.5 |
| inspection_result | FAIL | 불합격 | DOC-06 §3.5 |
| inspection_plan | PASS | 합격 | DOC-06 4.1 |
| inspection_plan | HOLD_REVIEW | 보류 검토 | DOC-06 4.1 |

### 6.34 불량 코드와 결함 등급 (`defect_code`, 10개)

| 코드 | 이름 | 항목 (§2) | 등급 | 자주 보는 원인 |
|---|---|---|---|---|
| DIM-01 | 치수 큼 (상한 넘음) | 1~3, 8 | 1번은 치명, 나머지 중 | 공구 마모, 공구 오프셋 |
| DIM-02 | 치수 작음 (하한 밑) | 1~3, 8 | 1번은 치명, 나머지 중 | 공구 오프셋, 충돌 뒤 위치 틀어짐 |
| DIM-03 | 구멍 간 거리 벗어남 | 4 | 중 | 공작물 오프셋, 고정 불량 |
| DIM-04 | 평면도 벗어남 | 5 | 중 | 고정 변형, 떨림 |
| THR-01 | 나사 통과 게이지 안 들어감 | 6 | 중 | 탭 마모·파손, 기초 구멍 작음 |
| THR-02 | 나사 정지 게이지 2회전 넘게 들어감 | 6 | 중 | 탭 크기·흔들림 |
| SUR-01 | 버 남음 | 7 | 경 | OP-40 디버링 부족 |
| SUR-02 | 구성인선 흔적 (뜯긴 면) | 7 | 경 (치수에 영향 있으면 중) | 알루미늄이 날 끝에 붙는 구성인선 |
| SUR-03 | 찍힘·긁힘 | 7 | 경 | 운반·세척 중 부딪힘 |
| MAT-01 | 원자재 성적서 불일치 | §7 | 중 | 로트 코드·성분 불일치 |

| 결함 등급 코드 | 이름 | 처리 [가상] | 출처 |
|---|---|---|---|
| CRITICAL | 치명결함 | 로트 보류 + 검사 강화, 불합격 부품 폐기 (관리자 승인) | DOC-06 §8.1 [실제 정의] |
| MAJOR | 중결함 | 보류 검토 → 반장 판단, 불합격 부품 폐기 | DOC-06 §8.1 |
| MINOR | 경결함 | 재작업 (OP-40 다시 디버링) 후 재검사 | DOC-06 §8.1 |

출처: DOC-06 §8 (코드 [가상], 모양 [참고: Fabrico]).

### 6.35 알림 중요도 (`importance`)

| 코드 | 이름 | 보내는 방식 | 예 | 출처 |
|---|---|---|---|---|
| URGENT | 긴급 | 화면 팝업 + 소리, 해당 설비 작업자·보전 담당자 | 정지 등급 알람 | 기획서 4.3 |
| CAUTION | 주의 | 알림 목록 + 브리핑에 포함 | 주의 등급 알람, 반복 알람, 병목, 목표 미달 위험, 재고 부족 등 | 기획서 4.3 |
| INFO | 참고 | 알림 목록, 브리핑·보고서 | 조작 안내 알람, 문서 수정 알림 | 기획서 4.3 |

### 6.36 알림 종류 (`notification_rule` 처음 값)

| 규칙 코드 [제안] | 알림 종류 | 조건 | 중요도 | 가리키는 기록 (notification FK) | 출처 |
|---|---|---|---|---|---|
| ALARM_STOP | 알람 발생 (정지) | 정지 등급 알람 발생 | 긴급 | alarm_event, equipment | DOC-07 10.2, DOC-02 2장 |
| ALARM_WARN | 알람 발생 (주의) | 주의 등급 알람 발생 | 주의 | alarm_event, equipment | 같음 |
| ALARM_GUIDE | 알람 발생 (조작 안내) | 조작 안내 등급 알람 발생 | 참고 | alarm_event, equipment | 같음 |
| REPEAT_ALARM | 반복 알람 (**1단계**) | 같은 설비·같은 알람이 7일 안에 3번 이상 → MNT·SUP. 관련 정보: 지난 조치(작업기록서·간이 작업기록 번호) + **DOC-03 해당 절 근거** + 관련 예방 정비 기한 | 주의 | alarm_event | DOC-07 10.2·§10.4, R4 3.2, D-09 |
| REPEAT_ALARM_2 | 반복 알람 2단계 "지난 조치 효과 없음" (최종본) | 1단계 조치 계획을 저장한 뒤 7일 안에 같은 설비·같은 알람이 다시 남 (R-70) → MNT·SUP. 관련 정보: 1단계 조치 계획 원문 + 그 뒤 발생 기록 + 같은 알람의 발생·조치 이력. **OP-30이면 원인 점검 작업지시서 AI비서 초안 제안**, 다른 공정이면 DOC-03 §3 간이 대응 근거 + 원인 점검 요청(CAUSE_CHECK_REQUEST) | 주의 (등급은 DOC-02 심각도에서 나오므로 주의 유지) | alarm_event, equipment, notification (prev_stage) | R4 3.2, DOC-07 §10.4, DOC-03 §1.4, FR-AST-02-18 |
| CAUSE_CHECK_REQUEST | 원인 점검 요청 (다른 공정, 최종본) | 다른 공정(OP-10·20·40·50)의 반복 알람 2단계 → **MNT에게** 원인 점검 요청. 결과는 간이 작업기록 | 주의 (2단계와 같게) [제안] | equipment, alarm_event, notification (prev_stage = 2단계 알림) | R4 3.2, DOC-03 §1.4, FR-AST-02-18 |
| TARGET_RISK | 목표 미달 위험 | 예측 실적 < 교대 목표의 90% (81개) | 주의 | shift | DOC-07 8장·10.1 |
| BOTTLENECK_MOVE | 병목 발생·이동 | 병목 공정이 바뀜. 관련 정보 = **DOC-07 §7.5의 해당 원인 조치 줄** (비서는 제안만, 조치는 SUP — R-84) | 주의 | bottleneck_log | DOC-07 10.1·§7.5, FR-AST-02-19 |
| WIP_WARN | 재공 경고 | 공정 사이 재공 20개 초과 (WIP-30-40 제외) | 주의 | buffer_code | DOC-07 10.1 |
| LOT_DUE_RISK | 로트 납기 지연 위험 | 로트 예상 완료 시각 > 납기 | 주의 | production_lot | DOC-07 10.1 |
| STOCK_LOW | 재고 부족 | 재고 수량 ≤ 안전 재고 → **그 품목의 관리 역할(owner_role) + MGR** (공구·원자재 = SUP·MGR, 정비 소모품 = MNT·MGR). 완제품은 없음 | 주의 | inventory_item | DOC-07 10.2, D-13, R5 표 D |
| PM_DUE_SOON | 예방 정비 기한 하루 전 | 기한 하루 전 | 참고 | pm_task | DOC-07 10.2 |
| PM_OVERDUE | 예방 정비 기한 넘김 | 기한 넘김 | 주의 | pm_task | DOC-07 10.2 |
| TOOL_LIFE_90 | 공구 수명 | 사용률 90% | 주의 | tool | DOC-07 9장·10.2 |
| APPROVAL_WAIT_30M | 승인 대기 | 작업지시서 승인 대기 30분 이상 | 참고 | maintenance_work_order | DOC-07 10.2 |
| APPROVAL_WAIT_2H | 승인 대기 | 작업지시서 승인 대기 2시간 이상 | 주의 | maintenance_work_order | DOC-07 10.2 |
| DOC_REVISED | 문서 수정 | 작업지시서 수정 → 담당 보전원, 보고서 수정 → 관리자, 사내 문서 개정 → 관련 역할 전체 | 참고 | document_revision | 기획서 4.5, FR-AST-03-07 |
| SPC_OUT | 관리도 이상 | 점 1개가 +3σ 위 또는 −3σ 아래 → 반장 | 주의 | inspection_result | DOC-06 5.3 |
| SHIFT_REPORT_PENDING | 교대 보고서 확정 요청 | **06:00** 일일 보고서 초안을 만들 때 그 생산일 교대 보고서가 미확정 → 그 교대 반장(SUP) | 참고 | shift | FR-AST-02-17, UI설계서 9장 #2, D-08 |
| CMM_FILE_ERROR | CMM 결과 파일 오류 (최종본) | 결과 파일을 읽지 못함(양식 오류·열 빠짐·숫자 아님) 또는 확인 필요(지시와 다른 로트·순번, 항목 일부만 옴) → 작업자·반장 | 주의 [제안] | cmm_import | R3 5.4, FR-QLT-01-17 |
| CMM_JUDGE_MISMATCH | CMM 판정 불일치 (최종본) | 측정기 판정 ≠ 플랫폼 판정 → 반장 (공차·측정 프로그램 확인) | 주의 | inspection_result | R3 5.4, FR-QLT-01-16 |
| CMM_NO_RESULT | CMM 결과 미수신 (최종본) | 측정 시작 뒤 정한 시간 안에 결과 파일이 오지 않음 → 작업자·반장. **시간은 [선택 필요: 기술 회의]** (측정 시간 2.5분/개, 강화 5.0분/개보다 길게) | 주의 [제안] | production_lot, equipment (CMM-01) | R3 5.4, FR-QLT-01-18 |

- **묶기 규칙**(새 알림 종류가 아님): 같은 설비·같은 알람이 1분 안에 3번 이상 → 1건으로 묶고 `repeat_count`를 올린다. 10분에 10건 넘으면 `is_flood` 참, 10분에 5건 아래로 내려가면 푼다 (DOC-07 10.2·10.3).
- **오래된 알림**: 24시간 넘게 처리 안 된 주의 알림은 새 알림을 만들지 않고 보고 순위 **0-1**(잠금·표지 다음)로 올린다 (DOC-07 10.2·§10.5, R4 4.3).
- 반복 알람 1·2단계를 셀 때는 묶기(1분 안 3번)를 **먼저** 적용한다 (R-70).
- CMM 알림 3종의 중요도: 판정 불일치는 R3이 "주의 알림"으로 적음. 파일 오류·결과 미수신은 R3에 중요도가 없어 주의로 [제안] (품질 묶음, 보고 순위 3).
- 지표 카드 주의(가동률 60% 미만 등)는 화면 표시이고 알림 규칙이 아니다 (DOC-07 10.1 "지표 카드 주의").
- 의심 로트 제안은 알림 종류가 아니다 (6.8 아래, FR-PRD-05-05).

**알림 종류별 처리** (`notification.process_kind`·`processed_by`, UI설계서 9장 #4·SCR-07 표) [제안]

| 규칙 코드 | 처리 방법 | 처리되는 때 / 처리할 수 있는 역할 |
|---|---|---|
| ALARM_STOP | 자동 | OP-30: 작업기록서 확정 / 다른 공정: 간이 작업기록 확정 |
| ALARM_WARN | 자동 | 간이 작업기록 확정 |
| ALARM_GUIDE | 사람 | 받은 OPR 또는 SUP |
| REPEAT_ALARM | 사람 | MNT 또는 SUP, process_memo(조치 계획 한 줄) 필수 |
| REPEAT_ALARM_2 | 자동 | 원인 점검 작업기록서 확정 (OP-30, 계기에 2단계가 있는 작업지시서의 짝) / 원인 점검 간이 작업기록 확정 (다른 공정). 확정 뒤 7일 재발 없으면 "효과 확인"으로 닫힘 (R-70) |
| CAUSE_CHECK_REQUEST | 자동 | 원인 점검 간이 작업기록(cause_check_notification_id) 확정 (MNT) |
| CMM_FILE_ERROR | 자동 | 그 부품 결과가 다시 출력된 파일(성공) 또는 수동 입력으로 기록됨 (반장이 확인) [제안] |
| CMM_JUDGE_MISMATCH | 자동 | 반장이 그 측정값을 확인 (check_status = 반장 확인) |
| CMM_NO_RESULT | 자동 | 결과 파일이 들어오거나 수동 입력 기록 저장 (반장 확인) [제안] |
| TARGET_RISK, BOTTLENECK_MOVE, WIP_WARN, LOT_DUE_RISK | 사람 | SUP (예측이 다시 올라가도 자동 처리하지 않음) |
| STOCK_LOW | 자동 또는 사람 | 입고로 재고가 안전 재고를 넘으면 자동, 또는 MGR (받는 사람은 관리 역할 + MGR) |
| PM_DUE_SOON, PM_OVERDUE | 자동 | 실시 기록 저장 |
| TOOL_LIFE_90 | 자동 | 공구 교체 기록 |
| APPROVAL_WAIT_30M, APPROVAL_WAIT_2H | 자동 | 승인 또는 취소 |
| SPC_OUT | 자동 | 다음 부품 측정 기록 저장 |
| DOC_REVISED | 자동 | 받은 사람이 열면 |
| SHIFT_REPORT_PENDING | 자동 | 그 교대 보고서 확정 |

### 6.37 역할 (`role`)

| 코드 | 이름 | 인원 | 재고 관리 (입고 등록·월 실사) — 최종본 | 보기 범위 — 최종본 | 출처 |
|---|---|---|---|---|---|
| OPR | 현장 작업자 | 6 (교대·공정별) | 없음 (공구 교체 기록으로 공구 사용만) | 역할 권한대로. 첫 화면 = SCR-26 현장 보기 | 설계서 5.17, D-12·D-15 |
| MNT | 보전 담당자 | 3 | 정비용 소모품 6종 | 역할 권한대로 | 설계서 5.17, D-13 |
| SUP | 라인 반장 | 2 (주간·야간) | 절삭 공구 5종, 원자재(입고 검사 포함), 완제품 + **출하 등록·확정** | 역할 권한대로 | 설계서 5.17, D-13·D-14 |
| MGR | 공장 관리자 | 1 | 없음. **안전 재고·관리 역할 설정** | **모든 기능·문서 조회** (작성·확정·승인 권한은 그대로) | 설계서 5.17, D-11 |

### 6.38 센서 항목 (`sensor_item`, 7개)

| 코드 [실제 이름] | 이름 | 단위 | 정상 범위 [참고] | 연결 알람 |
|---|---|---|---|---|
| SpindleLoadPct | 주축 부하 | % | 0~185 (중앙값 38) | 174 |
| SpindleMotorTemp | 주축 모터 온도 | ℃ | 28~42 | 254 (온도 기준값 없음) |
| AirPressure | 공기 압력 | psi (bar) | 100~110 (약 6.9~7.6 bar) | 120 |
| Xload | X축 부하 | % | 0~65 | 108 → 994 → 992 |
| Yload | Y축 부하 | % | 0~65 | 108 → 994 → 992 |
| Zload | Z축 부하 | % | 0~65 | 108 → 994 → 992 |
| DcVolt | 직류 버스 전압 | V | 300~330 (중앙값 317) | (전원 관련, 선택) |

출처: DOC-07 3장, 설계서 5.9. **알람 기준값은 만들지 않는다.**

### 6.39 재공 위치 (`wip_buffer`, 4곳)

| 코드 [제안] | 위치 | 한도 | 경고 | 병목 판단 |
|---|---|---|---|---|
| WIP-10-20 | OP-10 → OP-20 | 30 | 20 초과 | 씀 |
| WIP-20-30 | OP-20 → OP-30 | 30 | 20 초과 | 씀 |
| WIP-30-40 | OP-30 → OP-40 | **60** | 경고 안 함 | 안 씀 |
| WIP-40-50 | OP-40 → OP-50 | 30 (온도 맞춤 선반 부품은 안 셈) | 20 초과 | 씀 |

출처: 설계서 5.6·5.15, DOC-07 7.2, 기획서 19장.

### 6.40 시연 사건 (`alarm_event.scenario_code`)

| 코드 | 이름 | 출처 |
|---|---|---|
| S1 | 충돌 의심 (메인, 고장) — VF2-01 108 → 994 → 992, LOT-2609-041-1 보류 | 설계서 7장 |
| S2 | 축 윤활 부족 — 2075 반복 | 설계서 7장 |
| S3 | 공구 수명 — T05 360구멍(90%) | 설계서 7장 |
| S4 | 공기 압력 저하 — 120 | 설계서 7장 |
| S5 | 조작 오류 — 314 | 설계서 7장 |
| S6 | 병목 (고장 아님) — VF2-02 예방 정비 90분 | 설계서 7장 |

### 6.41 근거 구분 (`pm_task.source_tag`, 최종본: `equipment.size_source_tag`, `layout_object.source_tag`, `equipment_part_shape.source_tag`)

| 코드 | 이름 | 출처 |
|---|---|---|
| REAL | [실제] | CLAUDE.md |
| REFERENCE | [참고] | CLAUDE.md |
| VIRTUAL | [가상] | CLAUDE.md |

### 6.42 작업지시서 계기 (`maintenance_work_order.trigger_kind`) — 최종본

| 코드 | 이름 | 채우는 칸 | 언제 | 출처 |
|---|---|---|---|---|
| STOP_ALARM | 정지 등급 알람 | alarm_event_id | OP-30 정지 등급 알람 1건마다 (기존) | 기획서 5.2, FR-MNT-03-01 ① |
| REPEAT_STAGE2 | 반복 알람 2단계 (원인 점검) | trigger_notification_id | **OP-30만**. 반복 알람 2단계 알림(REPEAT_ALARM_2) 1건마다 원인 점검 작업지시서 AI비서 초안 1건 | D-09, R4 3.2, FR-MNT-03-01 ② |
| PM_ABNORMAL | 예방 정비 중 이상 | pm_record_id | OP-30 예방 정비 결과 "이상 있음" (기존) | DOC-04 5장 |

- 계기는 **1개 이상**이다. OP-30 정지 등급 알람이 동시에 2단계이면 작업지시서는 1개, 계기 = STOP_ALARM + REPEAT_STAGE2, 작업 순서 끝에 원인 점검 단계를 덧붙인다 [가상] (R-71, 2026-10-07 총괄 정정).
- 다른 공정(OP-10·20·40·50)은 어떤 계기로도 작업지시서를 만들지 않는다 (DOC-02 §2).

### 6.43 보고 순위 (`notification.report_rank`, 계산) — 최종본

"전부 보고"(FR-AST-COM-21)의 순서. 프로그램이 정해진 목록·기준으로 문제를 **전부** 모으고 이 순서로 정렬한다. 비서는 그 순서대로 문장만 쓴다.

| 코드 | 순위 | 이름 | 들어가는 것 | 같은 순위 안 정렬 | 접기 | 근거 |
|---|---|---|---|---|---|---|
| R0 | **0** | 안전 | 잠금·표지 중인 설비 (R-53) | 잠금 시작 시각 이른 순 | **접지 않음**. 없으면 "잠금·표지 중인 설비 없음" | DOC-05 §2.3, R4 4.3 |
| R0_1 | 0-1 | 오래 방치 | 24시간 넘게 처리 안 된 주의 알림 | 처리 안 된 시간 긴 순 | 접지 않음 | FR-AST-01-06, R4 4.3 |
| R1 | **1** | 긴급 (정지) | 처리 안 된 정지 등급 알람 (ALARM_STOP), 지금 DOWN인 설비 | ① 지금 멈춰 있는 것 먼저 ② 정지 시간 긴 순 ③ 같으면 병목 공정(OP-30) 먼저 | 접지 않음 | R4 4.3 [참고: ISA-18.2 틀] |
| R2 | **2** | 생산 위험 | 목표 미달 위험 (TARGET_RISK), 병목 발생·이동 (BOTTLENECK_MOVE, 재공 20개 초과 WIP_WARN 포함), 로트 납기 지연 위험 (LOT_DUE_RISK) | 목표 미달(부족 수량 큰 순) → 병목(속도 손실 수량 큰 순) → 납기(납기 이른 순) | 위에서 일부만 펼치고 나머지 접음 | R4 4.3 |
| R3 | **3** | 주의 | ① 반복 알람 2단계(REPEAT_ALARM_2·CAUSE_CHECK_REQUEST) → 1단계(REPEAT_ALARM) ② 처리 안 된 주의 등급 알람 (ALARM_WARN) ③ 품질: 관리도 이상 (SPC_OUT), 보류·강화 로트, 의심 로트 제안, CMM 알림 3종 ④ 공구 수명 90% 이상 (TOOL_LIFE_90), 예방 정비 기한 넘김 (PM_OVERDUE), 재고 부족 (STOCK_LOW) ⑤ 승인 대기 2시간 이상 (APPROVAL_WAIT_2H) | 묶음 순서는 ①~⑤. 묶음 안: 반복 알람 = 발생 횟수 많은 순 / 공구 = 사용률 높은 순 / 정비 = 넘긴 일수 많은 순 / 재고 = (재고 ÷ 안전 재고) 작은 순 / 승인 = 대기 시간 긴 순 | 같음 | R4 4.3 (묶음 순서 [제안]) |
| R4 | **4** | 참고 | 조작 안내 알람 (ALARM_GUIDE), 예방 정비 하루 전 (PM_DUE_SOON), 승인 대기 30분 (APPROVAL_WAIT_30M), 교대 보고서 확정 요청 (SHIFT_REPORT_PENDING), 문서 수정 알림 (DOC_REVISED) | 발생 시각 이른 순 | 기본으로 접음 | R4 4.3 |

- 모든 순위 공통: 화면 맨 위에 "전체 N건 (안전 a · 긴급 b · 생산 c · 주의 d · 참고 e)"를 항상 보인다. 건수 0인 순위도 이름과 "없음". 같은 설비·같은 원인은 한 줄로 묶어 높은 순위 쪽에 둔다. 동점은 발생 시각 이른 순. **개수를 잘라서 보여 주지 않는다** — 항목마다 한 줄은 항상 보이고, 자세한 내용만 접는다 (D-07, R4 4.3).
- 알림이 아닌 항목(잠금·표지 중 설비, DOWN 설비, 보류·강화 로트, 의심 로트 제안)도 같은 순위를 쓴다 — 저장하지 않고 계산.

### 6.44 출하 상태 (`shipment.status`) — 최종본

| 코드 | 이름 | 뜻 | 누가 | 출처 |
|---|---|---|---|---|
| DRAFT | 작성 중 | 로트 줄을 고르는 중. 재고가 빠지지 않음 | SUP | R5 표 C [제안] |
| CONFIRMED | 확정 | 출하 전 확인 통과 → 로트 줄마다 출하 출고 거래 생성. 잠김 | SUP | R5 표 C [제안] |
| REVISED | 확정 후 수정 | 확정 뒤 고친 새 버전 (사유 필수, 다시 확정 없음 — 6.16 REVISED와 같은 규칙). 바뀐 수량만큼 조정 거래 [제안] | SUP | R5 표 C "다른 문서와 같은 규칙" |

### 6.45 출하처 (`shipment.customer_code`) — 최종본

| 코드 | 이름 | 출처 |
|---|---|---|
| CUST-01 | 가상 고객사 (1곳). **실제 회사 이름은 쓰지 않는다** | R5 표 C·1.7 G7 [가상] |

### 6.46 측정 입력 방식 (`inspection_result.input_method`) — 최종본

| 코드 | 이름 | 쓰는 항목 | 출처 |
|---|---|---|---|
| CMM_AUTO | CMM 자동 (결과 파일) | CMM 항목 1~5, 8 — 기본 | R3 5.3, FR-QLT-01-14 |
| TABLET | 태블릿 버튼 (사람) | M6 나사 게이지(6번) "통과 / 불합격", 외관(7번) + 불량 코드 | R3 3.4·5.3, FR-QLT-01-20 |
| MANUAL | 수동 입력 | 자동 입력이 안 될 때만 (측정기·공유 폴더 고장 등). "수동" 표시 + 입력자, 반장 확인 | R3 5.4, FR-QLT-01-19 |

### 6.47 측정 확인 상태 (`inspection_result.check_status`) — 최종본

| 코드 | 이름 | 언제 | 로트 판정에 쓰나 | 출처 |
|---|---|---|---|---|
| NORMAL | 정상 | 자동 입력, 지시와 같은 로트·순번, 판정 일치, 항목 모두 옴 (측정 시작 때 바코드·측정자 확인은 끝남) | 예 | R3 5.3·FR-QLT-01-20 |
| NEEDS_CHECK | 확인 필요 | 판정 불일치, 지시와 다른 로트·순번, 항목 일부만 옴(불완전 — 그 부품 판정 보류), 수동 입력, 재측정 결과가 둘 이상 | **아니요** | R3 5.4 |
| CHECKED | 반장 확인 | SUP가 확인함 (맞는 로트를 고르거나, 쓸 결과를 고름) | 예 | R3 5.4 |

### 6.48 결과 파일 가져오기 상태·오류 종류 (`cmm_import.status`, `error_kind`) — 최종본

| 칸 | 코드 | 이름 | 뜻 | 출처 |
|---|---|---|---|---|
| status | SUCCESS | 성공 | 다 읽고 측정값 기록. 원본은 "처리됨" 칸으로 | R3 5.1 7번 |
| status | FAILED | 실패 | **기록하지 않음**. 원본은 "오류" 칸으로, 오류 목록 + 알림 (CMM_FILE_ERROR) | R3 5.4, FR-QLT-01-17 |
| status | NEEDS_CHECK | 확인 필요 | 측정값은 남기되 확인 필요(6.47)로 — 로트 판정에 쓰지 않음 + 알림 | R3 5.4 |
| error_kind | FORMAT | 양식 오류 | 열 빠짐, 숫자 아님 → 실패 | R3 5.4 |
| error_kind | LOT_MISMATCH | 지시와 다름 | 로트·순번이 측정 지시와 다름 → 확인 필요 | R3 5.4, FR-QLT-01-15 |
| error_kind | INCOMPLETE | 불완전 | 항목 일부만 옴 → 확인 필요, 다시 측정 | R3 5.4 |

- 같은 부품 결과가 두 번 오는 것은 오류가 아니다: 두 번째는 **재측정**으로 따로 저장 (`inspection_result.remeasure_seq` = 2, R-81).
- 공유 폴더·네트워크가 끊기면 측정기 쪽에 파일이 남아 있으므로 다시 연결되면 순서대로 읽는다 (R3 5.4).

### 6.49 배치 물체 종류 (`layout_object.object_kind`) — 최종본

| 코드 | 이름 | 예 (object_id) | 출처 |
|---|---|---|---|
| MATERIAL_RACK | 봉재 랙 | RACK-01 | R1 3.6·7장 |
| INFEED | 투입 대 | INF-01 (SAW-01 연장 베드) | R1 3.1·7장 |
| WIP_SPOT | 재공 자리 | WIP-1~4 (`wip_buffer`와 연결) | R1 3.6·7장 |
| SOAK_SHELF | 온도 맞춤 선반 | SOAK-01 (재공에 안 셈) | R1 3.6·7장 |
| FG_SPOT | 완성품 자리 | FG-01 | R1 3.6·7장 |
| AISLE | 통로 | AISLE-1 (바닥 표시) | R1 5장·7장 |
| DOOR | 반입문 | DOOR-1 | R1 6장·7장 |
| EXIT | 비상구 | EXIT-1 | R1 6장·7장 |

### 6.50 도형 종류 (`equipment_part_shape.shape_kind`) — 최종본

| 코드 | 이름 | 크기 칸의 뜻 | 출처 |
|---|---|---|---|
| BOX | 상자 | X × Y × Z | D-02 "단순 도형(상자·원기둥)" |
| CYLINDER | 원기둥 | size_x_mm = size_y_mm = 지름, size_z_mm = 두께·길이 | D-02 |

### 6.51 정면 방향 (`equipment.facing`) — 최종본

| 코드 | 이름 | 출처 |
|---|---|---|
| NEG_Y | −Y (남쪽, 주 통로 쪽) — **지금 모든 설비** | R1 2장 [가상] |
| POS_Y | +Y (북쪽) | (지금 쓰지 않음) |
| NEG_X | −X (서쪽) | (지금 쓰지 않음) |
| POS_X | +X (동쪽) | (지금 쓰지 않음) |

### 6.52 사내 문서 종류 (`internal_doc.doc_kind`) — 최종본

| 코드 | 이름 | 문서 | 비서 검색 대상 | 출처 표시 예 | 출처 |
|---|---|---|---|---|---|
| MANUAL_DOC | 사내 문서 | DOC-01 ~ DOC-07 | 예 | "고장 대응 매뉴얼 DOC-03 §2.1" | D-03·D-05 |
| GLOSSARY | 용어집 | 00_용어집 | **예 (최종본에서 추가)** | "용어집 §4" | D-05 |

### 6.53 데이터 보관 단계 (NFR-DATA-13) — 최종본

보관 기간은 엔터티 칸으로 두지 않고 **데이터 종류별 규칙**으로 둔다 (R-75). 실제 삭제·집계·이동 방식은 물리 ERD **[선택 필요: 기술 회의]**. 가상 데이터는 30일(NFR-DATA-01)이라 시연에서 지워지는 데이터는 없다.

| 코드 | 단계 | 무엇 | 운영 DB 보관 | 그 뒤 | 표시 | 핵심 근거 |
|---|---|---|---|---|---|---|
| L1 | 세밀 시계열 | OP-30 센서 **1초** 구간 | 90일 | 삭제 (1분 평균은 L2에 있음) | [가상] | 30일 지표 창 3개분. 법·고객 요구 없음 |
| L2 | 시계열 | 센서 1분 평균, 재공 5분(1분) | 1년 | **1시간 집계**(최소·평균·최대)로 줄임 → 집계는 2년 뒤 삭제 | [가상] + [참고] | 12개월 비교. 원본 짧게 + 집계 길게 (히스토리언·시계열 DB 방식 [참고]) |
| L3 | 사건·운영 기록 | 설비 상태, 알람, 병목, 알림, 공구·소모품 입출고 | 2년 | 삭제 (교대·일 집계는 보고서에 남음) | [참고] | Ford CSR: 공정 관리 데이터·대응 기록 최소 2년 |
| L4 | 품질·추적·확정 문서 | 로트 추적 사슬, 검사 측정값, **출하**, 확정 문서와 수정 이력 | 2년 | **보관 저장소로 이동**(읽기 전용) → 기준일부터 **15년** 뒤 삭제 | [참고] + [실제] | Bosch·Danfoss 15년, Diehl 10년, 제조물책임법 제7조② 10년 [실제], IATF "생산·서비스 기간 + 1년" |
| ACCESS_LOG | 특별: 접속 기록 | 로그인·화면 접속 기록 | 1년 | 삭제 | [실제] | 개인정보의 안전성 확보조치 기준 제8조 "1년 이상" |
| USER | 특별: 사용자 계정 | 이름·역할 (`app_user`) | 사용 중 유지 | **지우지 않고 비활성** (`is_active`). 이름 처리는 [선택 필요: 팀 회의·개인정보 담당] | [실제] + [선택 필요] | 개인정보 보호법 제21조 |
| MASTER | 기준 정보 | 공정, 설비, 제품, 알람 코드집, 검사 항목, 불량 코드, 공장 배치 등 | 계속 | 지우지 않고 "사용 중지" 표시 | [제안] | 15년 기록이 이 값을 가리킴 |

- **15년은 임시값**이다. 고객사가 정해지면 그 고객 CSR 값을 따른다 [선택 필요]. 기준일은 따로 적지 않으면 기록이 생긴 날(확정 문서는 확정일).

**엔터티별 보관 기간** (R2 2장 표 그대로, 엔터티 이름은 이 문서 이름)

| # | 데이터 종류 (엔터티) | 단계 | 보관 기간 | 기간이 지나면 | 표시 |
|---|---|---|---|---|---|
| 1 | OP-30 센서 값 1초 구간 (알람·병목 전후 30분) (`sensor_sample`) | L1 | 90일 | 삭제. 단, **정지 등급 알람 + 작업기록서가 있는 구간은 2년** (작업기록서 [다시 보기], FR-MNT-05-14) | [가상] |
| 2 | OP-30 센서 값 1분 평균 (`sensor_sample`) | L2 | 1년 | 1시간 집계(최소·평균·최대)로 줄임 → 집계는 2년 뒤 삭제 | [가상] + [참고] |
| 3 | 재공 기록 5분 (사건 전후 30분 1분) (`wip_log`) | L2 | 1년 | 1시간 집계(평균·최대)로 줄임 → 2년 뒤 삭제 | [가상] |
| 4 | 설비 상태 기록 (`equipment_state_log`) | L3 | 2년 | 삭제 (교대·일 가동률은 보고서에 남음) | [참고] |
| 5 | 알람 기록 (`alarm_event`) | L3 | 2년 | 삭제. 단, **보류·의심 로트와 연결된 알람은 #9와 같이 15년** | [참고] |
| 6 | 병목 기록 (`bottleneck_log`) | L3 | 2년 | 삭제 | [가상] |
| 7 | 알림과 처리 기록 (`notification`, `notification_recipient`) | L3 | 2년 | 삭제 | [가상] |
| 8 | 공구·소모품·예비품 입출고 (`inventory_txn` 중 원자재·완제품 아닌 것) | L3 | 2년 | 삭제 | [가상] |
| 9 | 로트 추적 사슬: `raw_material_lot`, `production_order`, `production_lot`, `operation_report`, `lot_hold`, `defect_record`, 원자재 투입·완제품 입출고 `inventory_txn`, 로트별 `tool_usage`·`tool_change`, `inspection_plan` | L4 | **로트 출하일부터 15년** | 운영 DB 2년 → 보관 저장소(읽기 전용) → 15년 뒤 삭제 | [참고] + [실제] |
| 10 | 검사 결과 측정값 (`inspection_result`) — 최종본: 결과 파일 가져오기 기록 `cmm_import`도 같게 [제안] | L4 | 로트 출하일부터 15년 | #9와 같음. **합격·불합격만 남기고 측정값을 지우면 안 됨** | [참고] |
| 11 | 완제품 출하 기록 (`shipment`, `shipment_line`) | L4 | 출하일부터 15년 | #9와 같음 | [참고] |
| 12 | 작업지시서·작업기록서 (잠금·표지 체크 포함) (`maintenance_work_order`, `work_order_step`, `work_order_part`, `work_record`, `work_record_check`, `work_record_part`) | L4 | 확정일부터 15년 | 운영 DB 2년 → 보관 저장소 → 삭제 | [참고] + [가상] |
| 13 | 예방 정비 실시 기록 (`pm_record`) | L4 | 확정일부터 15년 | #12와 같음 | [참고] + [가상] |
| 14 | 교대 보고서·일일 보고서 (`shift_report`, `daily_report`) | L4 | 확정일부터 15년 | #12와 같음 | [가상] |
| 15 | 사내 문서 개정판 (`internal_doc`) | L4 | 현행판: 유효한 동안 / 폐기판: 폐기일부터 15년 | 폐기판은 보관 저장소로 | [가상] |
| 16 | 수정 이력 (`document_revision`, `document_revision_change`) | L4 | **본문 문서와 같음** | 본문과 함께 이동·삭제 | [가상] |
| 17 | 사내 문서 조각 (`doc_chunk`) | — | 현행판 조각만 | 문서 개정 때 지우고 다시 만듦 (파생 데이터) | [가상] |
| 18 | AI 비서 질문·답 기록 | — | **저장하지 않음** (현재 설계) | — | [실제: 프로젝트 문서] |
| 19 | 접속 기록 (로그인·접속 일시·한 일) | ACCESS_LOG | 1년 | 삭제 | [실제] |
| 20 | 사용자 계정 (`app_user`) | USER | 사용 중 유지 | 행은 지우지 않고 비활성 | [실제] + [선택 필요] |
| 21 | 기준 정보 (`process`, `equipment`, `isolation_point`, `product`, `work_day`, `shift`, `wip_buffer`, `plant_layout`, `layout_object`, `equipment_part_shape`, `alarm_master`, `alarm_guide_map`, `downtime_reason`, `sensor_item`, `pm_task`, `tool_type`, `tool`, `inventory_item`, `inspection_item`, `defect_code`, `role`, `role_permission`, `notification_rule`) | MASTER | 계속 | 지우지 않고 "사용 중지" 표시 | [제안] |

- 출처: R2 2장 (근거 칸은 R2 2장·3장). #10의 `cmm_import`, #21의 최종본 새 엔터티 3개, #9의 `inspection_plan`·완제품 거래는 R2 표에 이름이 없어 가장 가까운 줄에 넣었다 [제안].

### 6.54 반복 알람 단계 상태 (`notification.repeat_stage_status`) — 최종본

| 코드 | 이름 | 단계 | 언제 | 다음 | 출처 |
|---|---|---|---|---|---|
| S1_OPEN | 1단계 열림 | 1단계 (REPEAT_ALARM) | 같은 설비·같은 알람 7일 안 3번 이상 | 1단계 닫힘 | DOC-07 10.2, D-09 |
| S1_CLOSED | **1단계 닫힘** | 1단계 | MNT·SUP가 조치 계획 한 줄 저장 (= 처리, FR-AST-02-13) | 효과 확인 (7일 재발 없음) / 2단계로 올라감 (7일 안 재발) | R4 3.2 |
| S2_OPEN | 2단계 열림 | 2단계 (REPEAT_ALARM_2) | 1단계 닫힘 뒤 7일 안 재발 (R-70) | 원인 점검 확정 | R4 3.2 |
| S2_CHECKED | 원인 점검 확정 | 2단계 | 원인 점검 작업기록서(OP-30) 또는 원인 점검 간이 작업기록(다른 공정) 확정 → 알림 자동 처리 | 효과 확인 / 다시 2단계 (7일 안 재발) | R4 3.2 |
| EFFECTIVE | **효과 확인** | 1·2단계 | 닫힘·확정 뒤 **7일 동안 재발 없음** → 닫음 | — | R4 3.3 [가상] 7일 |
| ESCALATED | 다음 단계로 넘어감 | 1·2단계 | 7일 안 재발로 새 2단계 알림이 생김 (새 알림이 이 알림을 prev_stage로 가리킴) | — | R4 3.2 "(2단계 반복)" |

- 가상 사례 [가상] (설계서_최종본 5.8): VF2-02 알람 108 — 9/8·9/9·9/10 세 번 → 1단계 열림 → 조치 계획 저장(1단계 닫힘) → 9/14 재발 → 2단계 열림 (원인 점검 작업지시서 AI비서 초안, 계기 REPEAT_STAGE2) → 9/15 원인 점검 작업기록서 확정 (원인 점검 확정) → 7일 재발 없으면 효과 확인.
- 2075 1단계 사례(시연)는 2단계로 이어지지 않는다 (R4 5장 #7).

---

## 7. 관계 정의표

- 카디널리티는 **부모 : 자식**. "1 : 0..N"은 부모 1개에 자식이 없거나 여러 개. 자식 쪽 FK가 비어도 되면 부모를 "0..1"로 적는다.

| # | 관계 | 부모 | 자식 (FK) | 카디널리티 | 규칙 |
|---|---|---|---|---|---|
| 1 | 공정에 속한 설비 | process | equipment (process_code) | 1 : 1..N | OP-30만 2대 |
| 2 | 설비의 차단 지점 | equipment | isolation_point (equipment_id) | 1 : 1..N | 설비마다 2~3개 |
| 3 | 재공 위치의 앞 공정 | process | wip_buffer (from_process_code) | 1 : 0..1 | OP-50은 앞 공정인 위치가 없음 |
| 4 | 재공 위치의 뒤 공정 | process | wip_buffer (to_process_code) | 1 : 0..1 | OP-10은 뒤 공정인 위치가 없음 |
| 5 | 근무일의 교대 | work_day | shift (work_date) | 1 : 0..N | 근무일 2개, 휴무일 0개 |
| 6 | 교대 담당 반장 | app_user | shift (supervisor_user_id) | 1 : 0..N | 역할 SUP |
| 7 | 제품의 원자재 품목 | inventory_item | product (material_item_no) | 1 : 0..N | 원자재 구분 품목만 |
| 8 | 제품의 작업지시 | product | production_order (product_code) | 1 : 0..N | — |
| 9 | 작업지시의 로트 | production_order | production_lot (order_no) | 1 : 0..N | 로트 수량 합 = 작업지시 수량 (취소면 ≤, R-08) |
| 10 | 로트의 원자재 로트 | raw_material_lot | production_lot (material_lot_no) | 1 : 0..N | 로트마다 정확히 1개 (R-06) |
| 11 | 로트의 투입 교대 | shift | production_lot (input_shift_id) | 1 : 0..N | OP-10 투입이 모두 이 교대 안 (R-07) |
| 12 | 원자재 로트의 품목 | inventory_item | raw_material_lot (item_no) | 1 : 0..N | RM-6061 |
| 13 | 로트의 공정 실적 | production_lot | operation_report (lot_no) | 1 : 0..N | 완료되면 5개 공정 모두 있음 |
| 14 | 공정 실적의 공정 | process | operation_report (process_code) | 1 : 0..N | — |
| 15 | 공정 실적의 설비 | equipment | operation_report (equipment_id) | 1 : 0..N | 설비의 공정 = 실적의 공정 |
| 16 | 공정 실적의 처리 교대 | shift | operation_report (shift_id) | 1 : 0..N | — |
| 17 | 공정 실적의 작업자 | app_user | operation_report (worker_user_id) | 1 : 0..N | 역할 OPR |
| 18 | 재공 위치의 기록 | wip_buffer | wip_log (buffer_code) | 1 : 0..N | 5분 간격 (사건 전후 1분) |
| 19 | 새 병목 공정 | process | bottleneck_log (new_process_code) | 1 : 0..N | — |
| 20 | 이전 병목 공정 | process | bottleneck_log (prev_process_code) | 0..1 : 0..N | 첫 기록은 비움 |
| 21 | 병목의 고장 원인 | alarm_event | bottleneck_log (alarm_event_id) | 0..1 : 0..N | 원인 = 고장이면 필수 |
| 22 | 로트의 보류 | production_lot | lot_hold (lot_no) | 1 : 0..N | — |
| 23 | 보류 계기 알람 | alarm_event | lot_hold (related_alarm_event_id) | 0..1 : 0..N | — |
| 24 | 보류 계기 공구 | tool | lot_hold (related_tool_id) | 0..1 : 0..N | — |
| 25 | 보류·해제·폐기한 사람 | app_user | lot_hold (held_by, released_by, scrap_proposed_by, scrap_approved_by, normal_resumed_by) | 1 : 0..N (각 칸) | held_by·released_by = SUP·MGR, scrap_approved_by = MGR |
| 26 | 알람의 적용 공정 | process | alarm_master (process_code) | 1 : 0..N | — |
| 27 | 알람의 고장 대응 절 | alarm_master | alarm_guide_map (alarm_code) | 1 : 0..N | 고장 대응 칸이 있는 알람은 1..N |
| 28 | 고장 대응 문서 | internal_doc | alarm_guide_map (doc_no) | 1 : 0..N | DOC-03 |
| 29 | 알람 번호 | alarm_master | alarm_event (alarm_code) | 1 : 0..N | — |
| 30 | 알람 발생 설비 | equipment | alarm_event (equipment_id) | 1 : 0..N | 설비 공정 = 알람 적용 공정 |
| 31 | 알람 때 가공 중 로트 | production_lot | alarm_event (lot_no) | 0..1 : 0..N | — |
| 32 | 선행 알람 (자기 참조) | alarm_event | alarm_event (prev_alarm_event_id) | 0..1 : 0..N | 같은 설비, 선행이 먼저 발생 |
| 33 | 설비의 상태 구간 | equipment | equipment_state_log (equipment_id) | 1 : 0..N | 구간끼리 겹치지 않음 (R-04) |
| 34 | 상태 구간의 정지 사유 | downtime_reason | equipment_state_log (reason_code, reason_suggested_code) | 0..1 : 0..N | RUN이면 비움, 아니면 1개 (R-21) |
| 35 | 상태 구간을 만든 알람 | alarm_event | equipment_state_log (alarm_event_id) | 0..1 : 0..1 | **정지 등급 알람 1 : DOWN 구간 1** (R-01) |
| 36 | MAINT 구간의 정비 기록 | pm_record | equipment_state_log (pm_record_id) | 0..1 : 0..1 | MAINT면 필수 |
| 37 | 정지 사유 입력·확정한 사람 | app_user | equipment_state_log (reason_entered_by, reason_confirmed_by) | 1 : 0..N | 확정 = SUP |
| 38 | 센서의 연결 알람 | alarm_master | sensor_item (linked_alarm_code) | 0..1 : 0..N | — |
| 39 | 센서 값의 센서 | sensor_item | sensor_sample (sensor_code) | 1 : 0..N | — |
| 40 | 센서 값의 설비 | equipment | sensor_sample (equipment_id) | 1 : 0..N | has_sensor 참인 설비만 (VF2-01·02) |
| 41 | 알람의 작업지시서 | alarm_event | maintenance_work_order (alarm_event_id) | 0..1 : 0..1 | **OP-30 정지 등급 알람 1 : 작업지시서 1** (R-02) |
| 42 | 정비 중 이상의 작업지시서 | pm_record | maintenance_work_order (pm_record_id) | 0..1 : 0..1 | 결과 "이상 있음"인 OP-30 기록만 |
| 43 | 작업지시서의 설비 | equipment | maintenance_work_order (equipment_id) | 1 : 0..N | VF2-01·02만 |
| 44 | 작업지시서의 로트 | production_lot | maintenance_work_order (lot_no) | 0..1 : 0..N | — |
| 45 | 작업지시서 담당·승인·취소 | app_user | maintenance_work_order (assignee_user_id, approved_by, cancelled_by) | 1 : 0..N (각 칸) | 담당 = MNT, 승인 = SUP·MGR, 취소 = MGR |
| 46 | 작업지시서의 작업 순서 | maintenance_work_order | work_order_step (wo_no) | 1 : 1..N | 단계마다 DOC-03 출처 |
| 47 | 작업지시서의 예상 부품 | maintenance_work_order | work_order_part (wo_no) | 1 : 0..N | — |
| 48 | 예상 부품의 품목 | inventory_item | work_order_part (item_no) | 1 : 0..N | — |
| 49 | 작업지시서의 작업기록서 | maintenance_work_order | work_record (wo_no) | 0..1 : 0..1 | 작업기록서(FULL)는 작업지시서 1개에 정확히 1개 (완료 뒤) |
| 50 | 알람의 간이 작업기록 | alarm_event | work_record (alarm_event_id) | 0..1 : 0..1 | 간이(SIMPLE)는 알람 1개에 정확히 1개 |
| 51 | 작업기록서의 설비 | equipment | work_record (equipment_id) | 1 : 0..N | — |
| 52 | 작업기록서의 로트 | production_lot | work_record (lot_no) | 0..1 : 0..N | — |
| 53 | 작업기록서 확정·확인 | app_user | work_record (confirmed_by, checked_by) | 1 : 0..N (각 칸) | 확정 = MNT (간이 = OPR), 확인 = SUP |
| 54 | 작업기록서의 체크 | work_record | work_record_check (record_no) | 1 : 0..N | 잠금·표지 블록이 필요하면 LOTO 9행 (R-32) |
| 55 | 체크의 작업 순서 단계 | work_order_step | work_record_check (wo_no, step_no) | 0..1 : 0..N | 같은 작업지시서의 단계만 |
| 56 | 작업기록서의 사용 부품 | work_record | work_record_part (record_no) | 1 : 0..N | — |
| 57 | 사용 부품의 품목 | inventory_item | work_record_part (item_no) | 1 : 0..N | — |
| 58 | 설비의 정비 항목 | equipment | pm_task (equipment_id) | 1 : 0..N | VF-2는 24항목 |
| 59 | 정비 항목의 기본 소모품 | inventory_item | pm_task (default_item_no) | 0..1 : 0..N | — |
| 60 | 정비 항목의 실시 기록 | pm_task | pm_record (pm_task_id) | 1 : 0..N | — |
| 61 | 정비 실시자·기록자 | app_user | pm_record (done_by, recorded_by) | 1 : 0..N (각 칸) | 기록자 = MNT, 실시자 = 실제로 한 사람 (작업자 항목은 OPR) |
| 62 | 공구 품목의 공구 종류 | inventory_item | tool_type (item_no) | 1 : 0..1 | 구분이 공구인 품목만 1 |
| 63 | 공구 종류의 공구 | tool_type | tool (item_no) | 1 : 0..N | — |
| 64 | 공구가 꽂힌 설비 | equipment | tool (equipment_id) | 1 : 0..N | VF2-01·02만 |
| 65 | 공구의 사용 기록 | tool | tool_usage (tool_id) | 1 : 0..N | — |
| 66 | 사용 기록의 공정 실적 | operation_report | tool_usage (op_report_id) | 1 : 0..N | OP-30 실적, 공구와 같은 설비 |
| 67 | 공구의 교체 기록 | tool | tool_change (tool_id) | 1 : 0..N | — |
| 68 | 교체 계기 알람 | alarm_event | tool_change (related_alarm_event_id) | 0..1 : 0..N | 362, 174 |
| 69 | 공구 교체한 사람 | app_user | tool_change (changed_by) | 1 : 0..N | OPR, MNT |
| 70 | 품목의 거래 | inventory_item | inventory_txn (item_no) | 1 : 0..N | — |
| 71 | 사용 부품의 거래 | work_record_part | inventory_txn (work_record_no, work_record_item_no) | 0..1 : 0..1 | 작업기록서 확정 때 1건 |
| 72 | 예방 정비의 거래 | pm_record | inventory_txn (pm_record_id) | 0..1 : 0..N | 소모품마다 1건 |
| 73 | 공구 교체의 거래 | tool_change | inventory_txn (tool_change_id) | 0..1 : 0..1 | 교체 1회 = 1건 (R-41) |
| 74 | 로트 투입의 거래 | production_lot | inventory_txn (lot_no) | 0..1 : 0..1 | 수량 = 투입 수량 (R-42) |
| 75 | 원자재 입고의 거래 | raw_material_lot | inventory_txn (material_lot_no) | 0..1 : 0..1 | 수량 = 입고 수량 |
| 76 | 거래 기록한 사람 | app_user | inventory_txn (txn_by) | 1 : 0..N | — |
| 77 | 안전 재고 정한 사람 | app_user | inventory_item (safety_stock_set_by) | 0..1 : 0..N | MGR |
| 78 | 제품의 검사 항목 | product | inspection_item (product_code) | 1 : 1..N | 8개 |
| 79 | 로트의 검사 방식 | production_lot | inspection_plan (lot_no) | 1 : 1 | 로트를 만들 때 보통으로 생김 |
| 80 | 검사 강화의 계기 보류 | lot_hold | inspection_plan (hold_id) | 0..1 : 0..N | 보류 로트 + 다음 1~2개 (R-28) |
| 81 | 로트의 측정값 | production_lot | inspection_result (lot_no) | 1 : 0..N | 측정한 부품만 (R-26) |
| 82 | 측정값의 항목 | inspection_item | inspection_result (product_code, item_seq) | 1 : 0..N | — |
| 83 | 측정기 | equipment | inspection_result (instrument_id) | 1 : 0..N | CMM-01 |
| 84 | 측정자 | app_user | inspection_result (inspector_id) | 1 : 0..N | OPR |
| 85 | 로트의 불량 | production_lot | defect_record (lot_no) | 1 : 0..N | — |
| 86 | 불량 코드 | defect_code | defect_record (defect_code) | 1 : 0..N | — |
| 87 | 불량 발견 공정 | process | defect_record (process_code) | 1 : 0..N | — |
| 88 | 불합격 측정의 불량 | inspection_result | defect_record (result_id) | 0..1 : 0..1 | 판정이 불합격인 측정값만 |
| 89 | 교대의 교대 보고서 | shift | shift_report (shift_id) | 1 : 0..1 | 교대가 끝나면 1 |
| 90 | 교대 보고서 확정자 | app_user | shift_report (confirmed_by) | 0..1 : 0..N | = 그 교대 담당 반장 |
| 91 | 근무일의 일일 보고서 | work_day | daily_report (work_date) | 1 : 0..1 | 근무일만 1 |
| 92 | 일일 보고서 확정자 | app_user | daily_report (confirmed_by) | 0..1 : 0..N | MGR |
| 93 | 문서의 버전 (7종) | maintenance_work_order / work_record / shift_report / daily_report / internal_doc / pm_record / shipment | document_revision (doc_type + doc_key) | 1 : 1..N | 버전은 일곱 중 **하나만** 가리킴 (R-35. shipment 쪽은 관계 124) |
| 94 | 버전을 고친 사람 | app_user | document_revision (author_user_id) | 0..1 : 0..N | AI면 비움 |
| 95 | 버전의 바뀐 칸 | document_revision | document_revision_change (revision_id) | 1 : 0..N | v0은 0 |
| 96 | 사내 문서의 조각 | internal_doc | doc_chunk (doc_no) | 1 : 0..N | 승인된 개정만 |
| 97 | 사내 문서 승인자 | app_user | internal_doc (approved_by) | 0..1 : 0..N | MGR |
| 98 | 역할의 사용자 | role | app_user (role_code) | 1 : 0..N | 사용자마다 역할 1개 |
| 99 | 사용자의 담당 공정 | process | app_user (home_process_code) | 0..1 : 0..N | OPR |
| 100 | 역할의 권한 | role | role_permission (role_code) | 1 : 0..N | 기획서 13장 |
| 101 | 알림 규칙의 알림 | notification_rule | notification (rule_code) | 1 : 0..N | — |
| 102 | 알림 규칙 고친 사람 | app_user | notification_rule (updated_by) | 0..1 : 0..N | MGR |
| 103 | 알림의 받는 사람 | notification | notification_recipient (notification_id) | 1 : 1..N | — |
| 104 | 받는 사용자 | app_user | notification_recipient (user_id) | 1 : 0..N | — |
| 105 | 알림 처리한 사람 | app_user | notification (processed_by) | 0..1 : 0..N | — |
| 106 | 알림의 관련 기록 | alarm_event, equipment, production_lot, inventory_item, pm_task, tool, maintenance_work_order, bottleneck_log, document_revision, inspection_result, shift, wip_buffer | notification (각 FK) | 0..1 : 0..N (각 칸) | 알림 종류마다 6.36의 기록이 있어야 함 (R-38) |

**최종본에서 더한 관계 (107~124)**

| # | 관계 | 부모 | 자식 (FK) | 카디널리티 | 규칙 |
|---|---|---|---|---|---|
| 107 | 공장 배치의 배치 물체 | plant_layout | layout_object (layout_id) | 1 : 0..N | 공장 1개 (BLDG), 물체 11개 |
| 108 | 재공 위치의 바닥 자리 | wip_buffer | layout_object (buffer_code) | 0..1 : 0..1 | 재공 자리(WIP-1~4)만, 재공 위치 1개에 자리 1개 |
| 109 | 설비의 부품 도형 | equipment | equipment_part_shape (equipment_id) | 1 : 0..N | 단순 도형(상자·원기둥)만 |
| 110 | 출하의 로트 줄 | shipment | shipment_line (shipment_no) | 1 : 1..N | 확정하려면 로트 줄 1개 이상 |
| 111 | 출하한 로트 | production_lot | shipment_line (lot_no) | 1 : 0..N | **합격·해제 로트만** (R-67), 로트 출하 합 ≤ 합격 수량 |
| 112 | 출하 확인자 | app_user | shipment (confirmed_by) | 0..1 : 0..N | SUP만 |
| 113 | 출하 줄의 출고 거래 | shipment_line | inventory_txn (shipment_no, ship_lot_no) | 0..1 : 0..1 | 확정 때 로트 줄 1개 = 출하 출고 1건 (R-69) |
| 114 | 로트의 완제품 거래 | production_lot | inventory_txn (fg_lot_no) | 0..1 : 0..N | 합격 입고는 로트당 정확히 1건 (합격·해제 때), 완제품 실사 조정은 0..N |
| 115 | 품목의 관리 역할 | role | inventory_item (owner_role) | 1 : 0..N | MNT·SUP만 (R-77) |
| 116 | 결과 파일의 측정기 | equipment | cmm_import (instrument_id) | 0..1 : 0..N | CMM-01 |
| 117 | 결과 파일의 로트 | production_lot | cmm_import (lot_no) | 0..1 : 0..N | 지시한 로트와 같아야 성공 (R-78) |
| 118 | 결과 파일에서 자동 입력한 측정값 | cmm_import | inspection_result (cmm_import_id) | 0..1 : 0..N | 입력 방식이 CMM 자동이면 필수. 실패 파일은 자식 0개 |
| 119 | 측정값 확인·수동 입력한 사람 | app_user | inspection_result (checked_by, entered_by) | 0..1 : 0..N (각 칸) | 확인 = SUP, 수동 입력 = 입력한 사람 |
| 120 | 알림의 결과 파일 | cmm_import | notification (cmm_import_id) | 0..1 : 0..N | CMM_FILE_ERROR |
| 121 | 앞 단계 알림 (자기 참조) | notification | notification (prev_stage_notification_id) | 0..1 : 0..N | 2단계 알림 → 1단계(또는 앞 2단계) 알림, 원인 점검 요청 → 2단계 알림 |
| 122 | 2단계의 원인 점검 작업지시서 | notification | maintenance_work_order (trigger_notification_id) | 0..1 : 0..1 | **OP-30만** (R-71). 정지 등급 알람과 겹치면 같은 작업지시서에 계기 2개 |
| 123 | 원인 점검 요청의 간이 작업기록 | notification | work_record (cause_check_notification_id) | 0..1 : 0..1 | 다른 공정만, 간이 작업기록 1건, 확정 = MNT |
| 124 | 출하의 버전 | shipment | document_revision (doc_type SHIPMENT + doc_key) | 1 : 1..N | 관계 93과 같은 규칙 (버전은 일곱 종류 중 하나만 가리킴, R-35) |

---

## 8. 무결성·업무 규칙

- **지키는 곳** 칸: 이 규칙을 지키는 데 필요한 엔터티·속성. 규칙을 DB 제약·서버 코드·생성기 점검 중 어디서 지킬지는 물리 ERD·API 명세에서 정한다 [선택 필요: 기술 회의].
- 설계서 9장의 점검은 **생성기가 만든 데이터를 확인하는 기준**이면서, 플랫폼이 운영 중에 지켜야 할 규칙이다. 범위 점검(비율·개수)은 8.6에 따로 모았다.

### 8.1 알람·상태·문서 흐름

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-01 | **정지 등급 알람 1건 ↔ DOWN 구간 1개.** DOWN 구간은 반드시 정지 등급 알람을 가리킨다 (alarm_event_id 필수, 알람 1개에 구간 1개). 주의 등급 알람으로 멈춘 시간은 DOWN이 아니라 **IDLE + ▲** (warn_marker 참) + FAILURE 그룹 사유 | equipment_state_log.alarm_event_id (UK), state_code, warn_marker | 설계서 9장, DOC-07 2.2, 기획서 19장 |
| R-02 | **OP-30 정지 등급 알람만 작업지시서 1건 → 작업기록서 1건.** OP-30 주의 등급과 OP-10·20·40·50의 정지·주의 등급은 **간이 작업기록 1건**만 (작업지시서 없음). 조작 안내는 지침카드만 (기록 없음). **최종본**: 작업지시서 계기에 OP-30 반복 알람 2단계가 더해졌다 (6.42, R-71) | maintenance_work_order.trigger_kind·alarm_event_id (UK)·trigger_notification_id (UK), work_record.record_type·wo_no·alarm_event_id | 기획서 5.2, 설계서 9장 (19장 결정 반영), FR-MNT-02-13, FR-MNT-03-01 |
| R-03 | **작업기록서 수리 시간 = 그 알람의 DOWN 구간 길이** (오차 1분 이내) | work_record.repair_min ↔ equipment_state_log.duration_min | 설계서 9장, FR-MNT-05-08 |
| R-04 | 한 설비의 상태 구간은 서로 겹치지 않는다. 한 시점에 상태는 하나 | equipment_state_log (equipment_id, start_at, end_at) | 설계서 9장, DOC-07 2.2 |
| R-05 | 로트 완료 수량 = 마지막 공정(OP-50) 공정 실적의 양품 + 재작업 합 | production_lot.completed_qty ↔ operation_report | 설계서 9장, DOC-07 4.3 |
| R-06 | 모든 생산 로트에 원자재 로트가 정확히 1개 | production_lot.material_lot_no (필수) | 설계서 9장 |
| R-06a | 생산 로트의 원자재 로트는 투입 때 **사용 가능** 상태여야 한다 (입고 검사 대기·입고 보류는 투입 불가) [제안] | raw_material_lot.status, production_lot.material_lot_no | DOC-06 §7 순서 3·5, FR-INV-01-04 |
| R-07 | 한 생산 로트의 OP-10 투입(공정 실적)은 모두 로트의 투입 교대 안 | operation_report (OP-10).shift_id = production_lot.input_shift_id | 설계서 9장, FR-PRD-05-02 |
| R-08 | 작업지시마다 로트 투입 수량 합 = 작업지시 수량. **취소된 작업지시는 이미 투입한 로트까지만 남아 합 ≤ 작업지시 수량** (대기 중 취소면 로트 0개, 취소 뒤 새 로트 없음) [제안: 로트는 OP-10 투입 때 생김] | production_lot.input_qty ↔ production_order.order_qty·status | 설계서 9장, FR-PRD-05-02, UI설계서 9.3 #8 |
| R-19 | 공정 실적: 생산 수량(PQ) = 양품(GQ) + 재작업(RQ) + 불량(SQ) | operation_report | DOC-07 4.3 |
| R-21 | RUN이 아닌 구간마다 정지 사유 1개. 멈춘 시간 5분 미만은 순간 정지(조작 그룹), 5분 이상은 고장 정지. 사유 확정은 SUP만, 비서는 추천만 | equipment_state_log.reason_code·reason_status·reason_confirmed_by | DOC-07 2.2·5.1, FR-PRD-01-18·19 |
| R-22 | DOWN은 정지 등급 알람 전용. MTTR·MTBF의 고장 횟수·수리 시간은 **정지 등급 DOWN만** 센다. SETUP·MAINT·BLOCKED·IDLE은 고장이 아니다 | equipment_state_log, alarm_event.severity_at_event | DOC-07 2.2·6.2, FR-PRD-01-22 |
| R-23 | MAINT 구간은 예방 정비 기록을 가리킨다. MAINT는 고장으로 세지 않는다 | equipment_state_log.pm_record_id | 설계서 5.7, FR-MNT-04-07 |
| R-24 | 알람은 그 알람의 적용 공정 설비에서만 난다. 센서 값은 OP-30 설비만 | alarm_event.equipment_id ↔ alarm_master.process_code, sensor_sample ↔ equipment.has_sensor | DOC-02, DOC-07 3장 |
| R-70 | **반복 알람 2단계 판정** (최종본). ① 1단계 = 같은 설비·같은 알람 7일 안 3번 이상 (기존) → 주의 알림 + 지난 조치 + DOC-03 해당 절 근거, MNT·SUP가 조치 계획 한 줄 저장 = 1단계 닫힘. ② 1단계 조치 계획 저장 뒤 **7일 [가상] 안에** 같은 설비·같은 알람이 **1번이라도 다시 나면 2단계** ("지난 조치 효과 없음" 주의 알림). ③ **셀 때 제외**: 먼저 1분 안 3번 묶기(FR-AST-02-11)를 적용한 뒤 센다. 조치 작업이 **진행 중**(그 작업지시서·작업기록서·간이 작업기록이 아직 확정 안 됨)일 때 난 알람은 세지 않는다 — 그 기록이 확정된 뒤부터 센다. ④ 2단계 처리 = 원인 점검 작업기록서(OP-30) 또는 원인 점검 간이 작업기록(다른 공정) 확정 → 자동. ⑤ 확정 뒤 7일 재발 없으면 "효과 확인"으로 닫고, 7일 안 재발하면 다시 2단계 (앞의 원인 점검 결과를 붙임, 외부 서비스 요청은 SUP 검토). 7일은 1단계와 같은 판단 창 — 새 숫자를 만들지 않음. 가상 사례: VF2-02 108 (6.54) | notification (REPEAT_ALARM, REPEAT_ALARM_2, CAUSE_CHECK_REQUEST).prev_stage_notification_id·repeat_stage_status·effect_check_due_at·repeat_count, alarm_event, maintenance_work_order, work_record | D-09, R4 3.2·3.3, DOC-07 §10.4, DOC-03 §1.4, FR-AST-02-03·13·18 |
| R-71 | **2단계 원인 점검 작업지시서는 OP-30만** (최종본). OP-30: 원인 점검 작업지시서 AI비서 초안 (DOC-03 해당 절의 보전 줄과 아직 확인 안 된 원인을 작업 순서로) → MNT 수정 → SUP 승인 (기존 흐름). **OP-30 정지 등급 알람이 동시에 2단계이면 작업지시서는 1개**: 계기 = 정지 등급 알람 + 반복 알람 2단계, 작업 순서 끝에 원인 점검 단계를 덧붙임 [가상]. **다른 공정(OP-10·20·40·50)**: 작업지시서를 만들지 않는 기존 범위(DOC-02 §2)를 지키고, 2단계 주의 알림 + DOC-03 §3 간이 대응 근거 + **MNT에게 원인 점검 요청** (CAUSE_CHECK_REQUEST) → 원인 점검 결과는 **간이 작업기록** (확정 = MNT) | maintenance_work_order.trigger_kind·trigger_notification_id·equipment_id, work_record.cause_check_notification_id·confirmed_by | D-09, R4 3.2, 2026-10-07 총괄 정정, DOC-03 §1.4 |
| R-74 | **필수 정지** (최종본, 교대 보고서 "정지 상위 3건" → "필수 정지 칸"): 정지 사유가 **고장 그룹(F01~F06)이고 5분 이상**인 정지 **전부** (정지 등급 DOWN 전부 + 주의 등급으로 멈춘 IDLE + ▲), 모든 공정, 개수 제한 없음. 정렬: ① 정지 시간 긴 순 ② 고장 손실 수량 큰 순 ③ 시작 이른 순. 순간 정지(5분 미만, 조작 그룹)는 **건수·합계 시간 한 줄**만. 넣지 않는 것: 소재 대기(M01 — 흐름 정지, 병목 칸), 준비(S), 계획 정비(P01), 흐름(M02·M03). 칸: 설비, 원인, 시간, 손실 수량 (+ 알람·사유 코드·작업지시서·작업기록 번호). 5분은 기존 경계(DOC-07 2.2) — 새 숫자 없음 | equipment_state_log.reason_code·duration_min·stop_loss_qty, downtime_reason.reason_group | D-06, R4 4.4, DOC-07 §5.4, FR-PRD-02-04 |

### 8.2 재공·병목

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-13 | **재공 = 앞 공정 완료 수 − 다음 공정 투입 수**, 0 이상, 한도 이하. 한도는 **30개, WIP-30-40만 60개**. **온도 맞춤 선반의 부품은 WIP-40-50 재공에 세지 않는다** (soak_shelf_qty에 따로) | wip_log.wip_qty·soak_shelf_qty, wip_buffer.limit_qty | 설계서 5.6·5.15·9장, 기획서 19장, DOC-06 §6 |
| R-14 | BLOCKED 구간마다 그 시각의 뒤 재공이 한도에 차 있다 | equipment_state_log (BLOCKED) ↔ wip_log | 설계서 9장, FR-PRD-01-03 |
| R-15 | 병목 판단: 최근 30분 동안 바로 앞 재공이 늘고, 앞 공정이 BLOCKED **이거나** 뒤 공정이 IDLE(앞 공정 대기)인 공정. 여럿이면 앞 재공이 가장 많은 공정, 없으면 기준 병목 OP-30. WIP-30-40 증가는 쓰지 않음. **생성기의 병목 기록 = 플랫폼 판단 결과** | bottleneck_log, wip_buffer.use_in_bottleneck, process.is_base_bottleneck | 설계서 5.18·9장, DOC-07 7.3 |
| R-49 | 병목 공정이 바뀌면 병목 기록 1건 (시각, 이전·새 병목, 원인 번호) + "병목 이동" 알림 | bottleneck_log, notification (BOTTLENECK_MOVE) | DOC-07 7.3 ⑥, FR-PRD-01-09 |
| R-56 | 재공 경고: 20개 초과 (WIP-30-40 제외) | wip_buffer.warn_over_qty·warn_enabled | DOC-07 7.2·10.1 |
| R-84 | **병목 조치 제안** (최종본): 병목 발생·이동 알림의 관련 정보에 **DOC-07 §7.5의 해당 원인 조치 줄**(원인 ①~④ + 고장)을 붙인다. 조치는 사람(SUP·MNT·MGR)이 하고 비서는 제안만. 어느 조치도 잠금·표지(DOC-05)와 검사 기준(DOC-06)을 줄이거나 건너뛰게 제안하지 않는다. 병목이 바뀌면 새 병목 기준으로 처음부터 다시 본다. 사람이 고른 조치는 교대 보고서 병목 칸에 원인 번호와 함께 남는다 | notification (BOTTLENECK_MOVE).related_info, bottleneck_log.cause_code | D-10, R4 2.3, DOC-07 §7.5, FR-AST-02-19, FR-AST-COM-10 |

### 8.3 로트·검사·품질

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-09 | 발췌(보통) 로트의 측정 부품 = 첫 부품 + 5개마다 1개 (1 + 투입 수량 ÷ 5의 몫, 36개 → 8개). 강화 로트는 전부 | inspection_plan.planned_measure_qty, inspection_result.part_seq | 설계서 9장, DOC-06 §3.2 |
| R-24a | 로트 상태는 6.8 순서로만 바뀐다. 의심 로트 제안은 상태를 바꾸지 않는다 | production_lot.status | FR-PRD-05-04·05 |
| R-25 | **로트 판정은 그 로트의 측정 부품을 모두 잰 뒤**. 그 전에는 "판정 대기". 발췌 측정 부품의 측정 시각 ≥ 세척 완료 + 온도 맞춤 대기 (보정 사용 90분 이상, 보정 못 쓰면 140분 이상, 초품 약 17분) | inspection_plan.judgement·judged_at, inspection_result.measured_at | 설계서 5.15, DOC-06 §6.1 |
| R-26 | 측정값은 **측정한 부품만** 남긴다. 게이지·육안 부품은 합격·불합격 수량만 (inspection_plan.gauge_pass_qty·gauge_fail_qty). 발췌 로트의 측정값 부품 수 = 측정 부품 수 | inspection_result, inspection_plan | 설계서 5.15, FR-QLT-01-12 |
| R-27 | 측정한 부품 중 1개라도 불합격 → 로트 "보류 검토", 남은 부품 전수. 보류·해제는 SUP·MGR만, 보류 사유 필수. 폐기는 SUP 제안 → MGR 승인 | production_lot.status, lot_hold | DOC-06 4.1, FR-PRD-05-06·08 |
| R-28 | 보류되면 그 로트 + 다음 1~2개 로트의 검사 방식이 강화로 바뀐다 (공구 원인·교체 완료 1개, 충돌·정지 등급·원인 모름 2개) | lot_hold.enhanced_next_lots, inspection_plan.plan_mode·hold_id | DOC-06 3.3, FR-QLT-01-05 |
| R-29 | 강화 → 보통: 원인 조치 완료(작업기록서·공구 교체 기록) **그리고** 강화한 로트가 모두 합격 → 반장 확인 | lot_hold.normal_resumed_by, work_record, tool_change | DOC-06 3.3, FR-QLT-01-07 |
| R-30 | Cpk는 특성마다 측정값 50개 이상으로 계산, 50개 미만이면 "계산 중". 기준(특별 1.67, 일반 1.33) 미만이면 그 항목 전수, 다시 채우면 관리자 승인 뒤 보통 | inspection_item.cpk_min·is_full_check_by_cpk | DOC-06 §5, FR-QLT-01-08·09 |
| R-31 | 관리도 점 1개가 ±3σ 밖이면 반장에게 주의 알림 | notification (SPC_OUT) | DOC-06 5.3, FR-QLT-01-10 |
| R-57 | QLT-01을 줄이면 로트 합격·불합격은 OP-50 공정 실적의 불량 수량으로 보여 준다 (검사 엔터티 없이도 로트 상태가 나옴) | operation_report.sq, production_lot.status | FR-PRD-05-10 |
| R-78 | **CMM 측정 결과 자동 입력** (최종본): OP-50 CMM 항목 측정값은 측정기가 공유 폴더에 쓴 결과 파일(부품 1개 = 파일 1개)에서 자동 기록한다 — **사람이 측정값을 치지 않는다**. 플랫폼은 로트 번호·부품 순번·검사 방식·강화 사유를 측정 지시로 넘기고, **결과 파일에 같은 값이 돌아와야** 기록한다 (다르면 확인 필요, 로트 판정에 안 씀). 측정자 = OP-50 태블릿 로그인, 로트 = 바코드 확인, M6 게이지·외관 = 태블릿 버튼 | cmm_import, inspection_result.input_method·cmm_import_id·check_status·inspector_id | D-17, R3 5.1·5.3, DOC-06 §3.6, FR-QLT-01-14·15·20 |
| R-79 | **판정 재계산**: 플랫폼이 측정값으로 DOC-06 §2 기준 판정을 다시 계산해 그 값(judgement)을 쓴다. 측정기 판정(cmm_judgement)과 다르면 "CMM 판정 불일치" 주의 알림 → 반장 확인 (확인 전에는 로트 판정에 안 씀) | inspection_result.judgement·cmm_judgement·is_judgement_mismatch·check_status, notification (CMM_JUDGE_MISMATCH) | R3 5.4, FR-QLT-01-16 |
| R-80 | **못 읽은 파일·결과 미수신**: 양식 오류(열 빠짐·숫자 아님) 파일은 **기록하지 않고** 오류 목록에 남기며 작업자·반장에게 알린다. 원본 파일은 **지우지 않는다** ("처리됨"/"오류" 칸). 측정 시작 뒤 정한 시간 안에 결과 파일이 오지 않으면 알린다 — 시간은 **[선택 필요: 기술 회의]** (측정 시간 2.5분/개, 강화 5.0분/개 [가상]보다 길게). 네트워크가 끊겼다 다시 이어지면 남은 파일을 순서대로 읽는다 | cmm_import.status·error_kind·original_file_ref, notification (CMM_FILE_ERROR, CMM_NO_RESULT) | R3 5.4, FR-QLT-01-17·18 |
| R-81 | **재측정 보관·수동 입력**: 같은 부품 결과가 다시 오면 덮어쓰지 않고 재측정(remeasure_seq 2, 3 …)으로 따로 보관한다. 같은 부품·항목에서 판정에 쓸 값(use_for_judgement)은 **하나만**, 재측정이 있으면 **반장이 고른다**. 자동 입력이 안 될 때 수동 입력 화면을 쓰고, 수동 기록에는 "수동" 표시·입력자·반장 확인을 남긴다. 로트 판정(R-25)은 판정에 쓰는 값만으로, 확인 필요 값이 남아 있으면 판정하지 않는다 | inspection_result.remeasure_seq·use_for_judgement·input_method·entered_by·checked_by | R3 5.4, FR-QLT-01-19·22 |
| R-82 | **온도 기록**: 측정 기록에 방 온도(환경 센서, 없으면 사람 입력)와 부품 온도(측정기 센서)를 **따로** 저장한다. 부품 온도가 DOC-06 §6 범위(16~26 ℃) 밖이면 "온도 확인" 표시 | inspection_result.room_temp_c·part_temp_c·is_temp_flag | R3 3.5·FR-QLT-01-21, DOC-06 §6 |

### 8.4 정비·안전

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-32 | 작업기록서(그리고 다른 공정 정지 등급·"보충용 2점 잠금" 줄의 간이 기록)는 **잠금·표지 9개 체크가 모두 끝나야 확정**. 확정 = MNT (간이: 주의 등급 OPR·MNT, 다른 공정 정지 등급 MNT만), 확인 = SUP. 작업기록서가 확정되면 짝 작업지시서가 완료 (6.13) | work_record.safety_block_required·status·confirmed_by, work_record_check (LOTO 9행), maintenance_work_order.status | FR-MNT-05-05·09·13·15, FR-MNT-03-02, NFR-SAFE-03 |
| R-33 | 정지 등급의 지침카드·작업지시서·(다른 공정) 간이 작업기록에는 DOC-05 §7 블록(6+3단계, 고전압 대기, 보호구)이 반드시 붙고 **누구도 지울 수 없다**. 고전압 대기 문구는 OP-30 설비만. 블록은 AI가 쓰거나 고치지 않는다 | maintenance_work_order.safety_block_doc_rev·has_high_voltage_notice, 6.19 | DOC-05 §7, FR-MNT-03-06~08, FR-AST-COM-13, NFR-SAFE-02 |
| R-34 | 작업기록서 확정 → 사용 부품만큼 재고 사용 거래 생성, MTTR·정지 원인 다시 계산 | inventory_txn (WORK_RECORD), work_record.confirmed_at | FR-MNT-05-10, FR-PRD-01-26 |
| R-31a | 작업지시서 상태는 6.13 순서로. 담당자가 비면 승인 안 됨. 승인 전 진행 중 불가. 승인은 SUP (MGR 대리), 비서는 지정·승인 안 함 | maintenance_work_order.status·assignee_user_id·approved_by | FR-MNT-03-02·14, FR-AST-COM-10 |
| R-43 | 예방 정비 다음 기한 = 실시일 + 주기. 기한 하루 전 참고, 넘기면 주의 알림. 제때 실시율 = 기한 안 실시 ÷ 기한이 온 항목 (목표 90%) | pm_task.next_due_date, pm_record.is_on_time | DOC-04 1장·5장, DOC-07 6.2 |
| R-17 | VF-2 예방 정비 항목은 Haas 정비 일정(RD0080, 기본 사양 24항목)에 있는 것만. 다른 공정 항목은 [실제]/[참고]/[가상] 표시로 허용 | pm_task.source_tag | 설계서 9장, 요구사항정의서 12장 #3 |
| R-53 | **잠금 중인 설비**: 어떤 작업기록서의 LOTO 6.4가 체크되고 7.3이 아직 체크되지 않았으면 그 설비는 잠금 중 → 교대 보고서 인계 사항 맨 위 | work_record_check | DOC-05 §2.3, FR-PRD-02-09 |

### 8.5 공구·재고

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-10 | 공구 누적 사용량 = 교체 뒤 가공 부품 수 × 부품당 사용량. 교체 때 0 | tool.cum_usage, tool_usage, tool_change | 설계서 9장 |
| R-11 | 재고 수량 = 입고(완제품 합격 입고 포함) − 사용·출하 출고 ± 조정, **음수 없음** | inventory_item.on_hand_qty, inventory_txn.qty_change | 설계서 9장, FR-INV-01-09 |
| R-39 | 재고 부족 = 재고 수량 ≤ 안전 재고 → 주의 알림. **받는 사람 = 그 품목의 관리 역할 + MGR** (최종본). 완제품은 안전 재고가 없어 부족 알림도 없다 | inventory_item.safety_stock·owner_role, notification (STOCK_LOW) | DOC-07 10.2, D-13, R5 표 A10·D |
| R-40 | 공구 사용률 90% → 교체 알림 (주의). 알림 기준은 **사용량**이고 예측 모델 값이 아니다 | tool.usage_rate_pct, notification (TOOL_LIFE_90) | DOC-07 9장, FR-ML-01-08 |
| R-41 | 공구 교체 1회 = 재고 1개 차감 (페이스밀 인서트 5개) | tool_change ↔ inventory_txn (UK) | 설계서 5.13 |
| R-42 | 로트 투입 = 투입 수량만큼 RM-6061 사용 거래 1건 | production_lot ↔ inventory_txn (UK) | FR-INV-01-03 |
| R-55 | 거래는 출처 기록을 정확히 하나 가리킨다 (source_kind에 맞는 FK 하나만 채움. 입고 등록·월말 실사는 FK 없음 — 단, 완제품 실사 조정은 로트를 알면 fg_lot_no를 적을 수 있음. 로트 합격 = fg_lot_no, 출하 = shipment_no + ship_lot_no) | inventory_txn | [제안], R5 표 B |
| R-67 | **출하는 합격 로트만** (최종본): 출하 로트 줄은 **합격(해제 포함) 로트만** 고를 수 있다 — 판정 대기·보류 검토·보류·폐기·생산 중 로트는 출하 불가 (시스템이 막음, 목록에도 안 나옴). 출하 시각 > 그 로트 합격(해제) 시각. 로트마다 출하 합 ≤ 합격 수량. 출하 확정은 SUP만. 이미 출하한 로트는 보류할 수 없고 로트 추적에 출하 번호·출하처를 보인다 (고객 통보·회수는 범위 밖) | shipment_line.lot_no·qty·lot_passed_at, production_lot.status, shipment.confirmed_by | D-14, R5 표 A5·A11·1.6, DOC-06 §4.1·§4.3, DOC-01 §5.5 |
| R-68 | **FIFO 출하**: 출하할 로트는 **먼저 합격한 로트부터** 고른다 (같은 날 합격이면 로트 번호 순). 먼저 합격한 로트(보류 아님)를 두고 나중 로트를 고르면 출하 확정 때 사유(fifo_skip_reason) 필수. 해제 로트도 해제 시각으로 FIFO 순서 안에 든다 | shipment_line.lot_passed_at, shipment.fifo_skip_reason | R5 표 A6·C [참고: IATF 8.5.4.1(Nemak 문장), NCS] |
| R-69 | **완제품 재고 정합**: ① 로트가 합격으로 판정된 순간 그 로트의 합격 수량(OP-50 양품 + 재작업 양품 = 로트 완료 수량)이 **합격 입고 1건**으로 들어온다 (거래 시각 = 판정 시각, 해제 로트는 해제 시각에 고른 합격 수량만, 폐기 수량은 안 들어옴). ② 출하가 확정되면 로트 줄마다 **출하 출고 1건**. ③ 로트 남은 수량 = 그 로트 합격 입고 − 그 로트 출하 (계산, ≥ 0). ④ **완제품 재고 = 합격 입고 합 − 출하 합 ± 조정**, 어느 시각에도 ≥ 0. ⑤ 판정 대기·보류 검토·보류 로트는 재고가 아니다 → "보류 수량"으로 따로 보인다 (재고 합에 안 넣음). ⑥ 월말 실사 조정은 SUP, 사유 필수. ⑦ 완제품은 안전 재고·부족 알림 없음 [제안]. ⑧ 일일 보고서 완제품 줄의 입고·출하 = 그 생산일 거래 합 | inventory_txn (FG_IN, SHIP_OUT, ADJUST).fg_lot_no·shipment_no·ship_lot_no, inventory_item (FG-BRK-A100), production_lot, shipment_line, daily_report | D-14, R5 표 A2~A10·B, FR-INV-01-11·12 |
| R-77 | **재고 관리 역할** (최종본): 품목마다 관리 역할(owner_role)이 **입고 등록과 월 1회 실사·조정**을 한다 — 정비용 소모품 6종 = **MNT**, 절삭 공구 5종·원자재(입고 검사 = 성적서 대조 포함)·완제품 = **SUP**. 사용(차감) 기록은 그대로: 공구 = OPR·MNT 공구 교체 기록, 소모품 = MNT 작업기록서·예방 정비, 원자재 = 로트 투입 자동, 완제품 = SUP 출하. 안전 재고와 관리 역할 설정은 MGR. 재고 부족 알림 = 관리 역할 + MGR. 조회는 모든 역할 (OPR은 보기만 + 공구 교체 기록) | inventory_item.owner_role, inventory_txn.txn_by·source_kind, raw_material_lot.status, role_permission | D-13, R5 표 D, FR-INV-01-04·05·08·13 |

### 8.6 생성 데이터 범위 점검 (설계서 9장 "범위·지표" 줄)

| # | 점검 | 기준 | 보는 엔터티 | 출처 |
|---|---|---|---|---|
| R-60 | VF-2 하루 상태 변화 횟수 | 60~120 | equipment_state_log | 설계서 9장 |
| R-61 | VF-2 RUN 비율 (30일 평균) | 55~75% | equipment_state_log | 설계서 9장 |
| R-62 | 전체 불량률 | 0.5~1.0% | operation_report | 설계서 9장 |
| R-63 | 알람 중 조작 안내 등급 비율 | 70% 이상 | alarm_event | 설계서 9장 |
| R-64 | 교대 실적 | 대부분 75~100개 (목표 90) | operation_report | 설계서 9장 |
| R-65 | 고장이 아닌 병목 원인 ①~④가 30일 안에 5.18 빈도만큼 | 모두 있음 | bottleneck_log | 설계서 9장 |
| R-16 | OP-30 알람 번호는 Haas NGC 목록에, 다른 공정 알람은 각 매뉴얼 목록에 (WSH-01·02만 [가상] 번호) | 100% | alarm_master.is_virtual_code | 설계서 9장 |
| R-18 | 생성기가 계산한 가동률·MTTR·손실 수량 = 플랫폼 계산 값 | 일치 | 8.7 계산 규칙 전부 | 설계서 9장 |
| R-66 | 알림 양: 평소 운전원 1명당 긴급+주의 10분에 1건 미만, 큰 고장 직후 10분 10건 미만, 중요도 비율 약 5·15·80% | 확인 기준 (막는 규칙 아님, 넘으면 점검 결과에 표시) | notification | DOC-07 10.3, FR-AST-02-15 |
| R-86 | **가상 출하 생성** (최종본): 납기 G2 (주간 시작 작업지시 생산일 + 1일, 야간 시작 + 2일, 일요일이면 월요일), 납기일 하루 1번 14:00 [가상] 출하, 그날 납기인 작업지시의 합격 로트 전부를 FIFO로 (로트 안 쪼갬), 보류·판정 대기 로트는 빼고 부분 출하 + 사유 → 해제·합격 뒤 다음 출하에 "납기 지남", 출하처 CUST-01, 출하 확인자 = 그날 주간 SUP, 기초 재고 9/1 0개 (9/1 출하 없음, 9/2 첫 출하), 9/30 완제품 실사 조정 0~1건 (±1~2개). 30일 출하 25건. **생성 뒤 점검 6줄**: 출하 로트 상태(보류 로트 출하 0건) / 출하 시각 > 합격 시각 / 로트 출하 합 ≤ 합격 수량 / 재고 정합 ≥ 0 / FIFO 어김 0건 / 일일 보고서 완제품 줄 = 거래 합 | 모두 맞음 | shipment, shipment_line, inventory_txn, production_order.due_at | R5 1.7 G1~G9·생성 뒤 점검, 설계서_최종본 5.20·9장 |

### 8.7 계산 규칙 (계산 표시 속성)

| # | 계산 | 식 | 출처 |
|---|---|---|---|
| R-44 | 계획 가동 시간 (PBT) | 설비별: 480분 − 그 설비 MAINT 시간. 라인 OEE: 480분 × 2대 (한 대의 예방 정비는 빼지 않음) | DOC-07 6.1·6.2 |
| R-45 | 가동률 A / 성능 E / 양품률 QBR / OEE | A = RUN 시간 ÷ PBT, E = 기준 사이클 × PQ ÷ RUN 시간, QBR = (GQ + RQ) ÷ PQ, OEE = A × E × QBR | DOC-07 6.2 [실제: ISO 22400] |
| R-45a | MTTR / MTBF | MTTR = 정지 등급 DOWN 수리 시간 합 ÷ 고장 횟수, MTBF = 고장 간격 합 ÷ 고장 횟수 (30일, 설비별). 고장 0건이면 "—" | DOC-07 6.2 |
| R-46 | 교대 실적 | 그 교대에 OP-50을 마친 GQ + RQ | 설계서 5.3, DOC-07 4.3 |
| R-47 | 손실 수량 (추정) | 정지 손실 = 정지 시간 ÷ 그 설비 기준 사이클 시간 (정지 1건마다, PLANNED 제외). 속도 손실 = 계획 생산 수(구간 ÷ 3.5분) − 실제 − 고장 손실 (병목 구간마다). 화면에 "추정" | 설계서 5.10, DOC-07 5.3 |
| R-48 | 예측 실적 | 현재 실적 + 최근 1시간 생산 속도 × 남은 시간 (교대 시작 1시간 전에는 시작부터의 평균 속도). 예측 < 목표의 90% → 목표 미달 위험 | DOC-07 8장 |
| R-12 | 교대 보고서 2개의 실적 합 = 일일 보고서 실적 | shift_report.actual_qty ↔ daily_report.actual_qty | 설계서 9장 |
| R-54 | 보고서 숫자 = 상태 기록·실적에서 계산한 값. 비서 문장 속 숫자는 표 값과 대조 | shift_report, daily_report | 설계서 5.16, FR-PRD-02-10·12, FR-AST-COM-05 |

### 8.8 문서·AI 비서·권한

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-35 | 문서 버전: v0 = AI비서 초안 (author_kind AI. 간이 작업기록·예방 정비 실시 기록·출하 기록은 사람). 사람 수정마다 새 버전 (v1, v2 …). 확정된 버전은 고칠 수 없고, **확정 뒤 고치면 새 버전 + 사유 필수**. 확정 뒤 수정은 그 문서의 확정 권한자만 하고, 저장한 버전이 바로 확정본이다 (다시 확정 없음) [제안]. 한 버전은 일곱 종류 문서(최종본에서 출하 기록 추가) 중 하나만 가리키고, (doc_type, doc_key)는 실제로 있는 문서여야 한다 | document_revision | 기획서 4.5, FR-AST-03-05·06 |
| R-36 | 교대 보고서는 교대마다 1개, **해당 교대 반장**이 확정 (confirmed_by = shift.supervisor_user_id). 일일 보고서는 근무일마다 1개, MGR이 확정. 일일 보고서 초안의 재료는 교대 보고서 2개 — **06:00까지 확정 안 된 교대 칸은 원기록 집계 + "잠정"** (R-72, FR-PRD-04-10) | shift_report, daily_report | 설계서 5.16, FR-PRD-02-11, FR-PRD-04-01·09·10, FR-AST-COM-08 |
| R-37 | (생성 데이터) 과거 문서는 모두 확정. 시연 중 새로 생기는 문서만 AI비서 초안에서 시작. 문서마다 1~3버전, 약 60%는 사람이 1~2곳 고친 버전이 있음 | document_revision, 각 문서 status | 설계서 5.16 |
| R-50 | 권한은 기획서 13.1·13.2 표를 따른다 (role_permission 처음 값). 버튼을 숨기는 것만이 아니라 서버에서도 확인. 최종본: MGR 전체 조회(R-76), 재고 관리 역할(R-77), 출하 SUP(R-67) | role_permission | NFR-SEC-02·03·05 |
| R-51 | "사람만" 하는 일(작업지시서 승인, 담당자 지정, 정지 사유 확정, 로트 보류·해제, 잠금·표지, 정비, **출하 확정, 측정값 반장 확인**)의 기록 칸에는 **사람 사용자**가 들어가야 한다. 비서는 제안까지만 (reason_suggested_code, 의심 로트 제안 화면 표시, 병목 조치 제안) | approved_by, assignee_user_id, reason_confirmed_by, held_by, released_by, checked_by, shipment.confirmed_by, inspection_result.checked_by | 기획서 4.4, FR-AST-COM-10, NFR-SAFE-04 |
| R-52 | 사내 문서 개정은 MGR 승인 뒤 반영. 개정되면 문서 조각을 다시 만들고, 조각마다 **문서 번호·개정 번호·절**을 붙인다 (최종본: 원문 출처는 붙이지 않음, 원문 대응표 절은 조각에서 뺌 [제안] — R-85) | internal_doc.status·approved_by, doc_chunk | FR-AST-03-09, FR-MNT-01-10, D-03 |
| R-38 | 알림 여부·중요도는 규칙(notification_rule)이 정하고 비서는 문장만. 알림마다 6.36의 관련 기록이 있어야 함. 1분 안 3번 묶기, 10분 10건 폭주, 24시간 미처리 주의 → **보고 순위 0-1 (잠금·표지 다음)** | notification, notification_rule | 기획서 4.3, FR-AST-02-11~14, FR-AST-01-06, R4 4.3 |
| R-58 | 설정(설비·사용자·알림 규칙·목표 수량·안전 재고·**재고 관리 역할**)은 MGR만. 최종본: 설정 값 중 **라인 구성(공장 배치·배치 물체·설비 외형·부품 도형), 알림 기준값, 교대 시간은 설정 파일(JSON)** 로 둔다 (D-18). 이 문서의 해당 엔터티(plant_layout, layout_object, equipment_part_shape, equipment 배치 칸, notification_rule, shift 시각)는 논리 모양이고, 설정 파일에서 읽어 DB 기준 정보로 넣을지·바로 쓸지는 물리 ERD [선택 필요: 기술 회의]. 운영 데이터는 DB. MGR의 모든 기능 **조회**(R-76)와는 별개로, 설정을 **바꾸는** 것만 MGR로 제한 | notification_rule.updated_by, inventory_item.safety_stock_set_by·owner_role, shift.target_qty | 기획서 13.2, NFR-SEC-04, D-18 |
| R-72 | **보고서 생성 시각** (최종본): 교대 보고서 AI비서 초안 = 교대 끝 (주간 17:00, 야간 05:00). **일일 보고서 AI비서 초안 = 생산일 다음 날 06:00** [가상] (야간 반장이 교대 보고서를 확정할 1시간, 08:00 시작 전). 생산일 = 주간이 시작한 날 (D일 08:00 ~ D+1일 05:00). 06:00까지 확정 안 된 교대 칸은 "잠정" + MGR [확정] 비활성 + 해당 SUP에게 확정 요청 알림 (SHIFT_REPORT_PENDING). 숫자는 06:00 기준 값 — 06:00에 판정 전인 야간 로트는 로트 칸에 "판정 대기", 완제품 입고는 다음 생산일 보고서에. 야간 반장의 05:00~06:00 확정 시간을 근무 계획에 넣을지는 [선택 필요: 팀] (R5 H7) | shift_report, daily_report.work_date, document_revision (v0 created_at), notification (SHIFT_REPORT_PENDING) | D-08, R5 4.3 표 H, FR-PRD-02-01, FR-PRD-04-01, FR-AST-02-17 |
| R-73 | **전부 보고·정해진 순서** (최종본): 교대 시작 브리핑 "먼저 챙길 일 (전체 N건)", 일일 보고서 "오늘의 문제 (전체 N건)", 손실 칸(손실 전체, 큰 순서), 교대 보고서 필수 정지 칸(R-74)·인계 사항은 **프로그램이 정해진 목록·기준으로 문제를 전부 모으고 6.43 순위로 정렬**한다. 비서는 그 순서대로 문장만 쓰고, 고르거나 빼거나 순서를 바꾸지 않는다. 개수를 자르지 않음, "전체 N건" + 순위별 건수 항상 표시, 같은 원인은 한 줄, 순위 0·0-1·1은 접지 않음. 브리핑 1분은 목표이고 1분에 맞추려고 항목을 빼지 않는다 (NFR-USE-07) | notification.report_rank, daily_report.issues_summary, shift_report.handover_text | D-07, R4 4.3, FR-AST-COM-21, FR-AST-01-04, FR-PRD-04-03·08, FR-PRD-02-08 |
| R-76 | **MGR 전체 조회** (최종본): MGR은 **모든 기능·문서를 조회**할 수 있다 (지침카드 MNT-02, 예방 정비 MNT-04, 공구 수명 ML-01, 출하, CMM 결과 파일 기록 포함). 작성·수정·확정·승인 권한은 바꾸지 않는다. role_permission 처음 값에서 MGR의 "보기" 행이 빠진 대상이 없어야 한다 | role_permission (role_code MGR, action 보기, scope 전체) | D-11, NFR-SEC-02·03 |
| R-85 | **출처 표시·검색 대상** (최종본): 비서 답·지침카드 칸·문서 초안·화면의 출처는 **사내 문서 이름 + 문서 번호 + §절**만 (예: "고장 대응 매뉴얼 DOC-03 §2.1", "용어집 §4"). 쪽 번호는 쓰지 않는다. **원문 출처는 저장·표시하지 않는다** (doc_chunk·alarm_guide_map의 원문 출처 칸 삭제, alarm_master.source_ref는 사람 추적용으로만). 검색 대상 = **DOC-01~07 + 용어집** (원문은 검색하지 않음). 출처에 마우스를 올리면 요약 카드(문서 이름, 번호·개정, 절 제목, 그 절 앞부분 2~3줄), 클릭하면 그 사내 문서가 팝업 창으로 열려 그 절로 이동 — 절 제목·앞부분은 그 사내 문서(file_ref)에서 가져온다 | doc_chunk (doc_no, doc_rev, section), internal_doc.doc_kind·is_search_target·file_ref, alarm_guide_map.section, work_order_step.source_section | D-03·D-04·D-05, FR-MNT-01-03·07·09·10, FR-AST-COM-02·04, CLAUDE.md (원문 저작권) |
| R-87 | **로컬 LLM·출력 형식** (최종본): 비서는 **로컬 LLM**으로 돌고 운영 데이터·사내 문서를 외부 서비스로 보내지 않는다 (NFR-SEC-08). 비서 출력은 정해진 JSON 칸으로 받고, 형식이 틀리면 프로그램이 거부하고 다시 요청하거나 **기본 문구**를 쓴다 [제안] (NFR-AIQ-09). AI 비서 질문·답은 저장하지 않는다. 모델·임베딩 모델·컴퓨터 사양·실행 도구는 [선택 필요: 기술 회의] | notification.message·message_source, document_revision.author_kind (AI비서 초안 v0), doc_chunk.embedding | D-18, NFR-SEC-08, NFR-AIQ-09, FR-AST-02-14 |

### 8.9 3D 배치·데이터 보관 (최종본)

| # | 규칙 | 지키는 곳 | 출처 |
|---|---|---|---|
| R-75 | **데이터 보관 기간** (NFR-DATA-13): 데이터 종류별 보관 기간과 지난 뒤 처리는 6.53 표를 따른다 — L1 OP-30 센서 1초 90일 / L2 1분 센서·재공 1년 → 1시간 집계 → 2년 뒤 삭제 / L3 사건 기록(상태·알람·병목·알림·공구·소모품 입출고) 2년 / L4 로트 추적 사슬·검사 결과·출하·확정 문서·수정 이력 15년(운영 DB 2년 → 보관 저장소(읽기 전용) → 삭제) / 접속 기록 1년 / 사용자 계정은 지우지 않고 비활성 / 기준 정보는 사용 중지 표시. 예외: 정지 등급 알람 + 작업기록서가 있는 1초 구간은 2년, 보류·의심 로트와 연결된 알람은 15년. **검사 측정값은 지우거나 합격·불합격만 남기지 않는다.** 보관 저장소로 옮긴 기록도 다시 꺼낼 수 있고 고칠 수 없어야 한다. 15년은 임시값 (고객 CSR이 정해지면 그 값) [선택 필요]. 실제 삭제·집계·이동 방식과 예외 표시 방법은 [선택 필요: 기술 회의]. 가상 데이터 30일(NFR-DATA-01)은 그대로 | 6.53 (모든 엔터티), app_user.is_active, sensor_sample, inspection_result | D-16, R2 1장·2장·4장, NFR-DATA-13, NFR-REL-02, DOC-07 §11 |
| R-83 | **3D 배치 좌표** (FR-PRD-01-27): 좌표 = 공장 안쪽 남서쪽 벽 모서리 바닥 원점, X 동쪽(공정 흐름)·Y 북쪽·Z 위, mm (plant_layout). 설비·배치 물체는 바닥 사각형 가운데(또는 X·Y 범위)와 실제 크기로 둔다. 모든 설비 정면은 −Y(통로 쪽). 설비 사이 간격 ≥ 1,000 mm, 설비 앞 작업 띠 1,000 mm, 주 통로 2,000 mm [가상]. 설비·배치 물체(통로·문 제외)의 바닥 사각형은 서로 겹치지 않는다 (WSH-01 구역 안 부품, CMM-01 화면은 그 설비 도형) [제안]. 크기 근거 표시([실제]/[참고]/[가상])는 비면 안 된다. 크기만 실제이고 단순 도형(상자·원기둥)으로 그린다 — 사실적인 모델링 없음. MIL-01 모델 칸은 "3축 머시닝센터 [가상]" 유지(크기만 [참고]) | plant_layout, layout_object, equipment (size_·center_·facing·size_source_tag·ref_model), equipment_part_shape | D-02, R1 2장·5장·7장 (간격 점검), DOC-01 §2.4, FR-PRD-01-27·28 |
| R-59 | 모든 운영 데이터는 가상이다. 화면에 "가상 운영 데이터" 표시. 데이터 묶음 단위로 가상 표시를 둘지 줄마다 둘지는 [선택 필요: 기술 회의] | (전체) | NFR-DATA-08, NFR-USE-06 |

---

## 9. 요구사항 ↔ 엔터티 추적표

- 기능마다 **주로 쓰는 엔터티**(데이터를 만들거나 바꿈)와 **읽기만 하는 엔터티**를 나눴다. 요구사항 ID는 요구사항정의서_최종본 기준 (최종본 새 ID는 2026-10-07 변경 명세 2장 번호).

| 기능 | 요구사항 | 주로 쓰는 엔터티 | 읽기만 하는 엔터티 |
|---|---|---|---|
| PRD-01 3D 라인 뷰·가동 현황 | FR-PRD-01-01~28 | equipment_state_log, wip_log, bottleneck_log | process, equipment, wip_buffer, plant_layout, layout_object, equipment_part_shape, shift, operation_report, alarm_event, alarm_master, downtime_reason, sensor_item, sensor_sample, tool, production_lot, maintenance_work_order |
| PRD-02 교대 보고서 | FR-PRD-02-01~12 | shift_report, document_revision, document_revision_change | shift, operation_report, equipment_state_log, production_lot, bottleneck_log, maintenance_work_order, work_record, work_record_check, alarm_event, pm_task, tool, inventory_item |
| PRD-03 작업지시 진행 현황 | FR-PRD-03-01~04 | production_order | production_lot, operation_report, process |
| PRD-04 일일 보고서 | FR-PRD-04-01~10 | daily_report, document_revision | work_day, shift_report, equipment_state_log, bottleneck_log, alarm_event, maintenance_work_order, work_record, production_lot, inventory_txn, inventory_item, shipment, notification (report_rank) |
| PRD-05 로트 추적 | FR-PRD-05-01~11 | production_lot, lot_hold | raw_material_lot, production_order, operation_report, alarm_event, tool_usage, tool_change, inspection_plan, inspection_result, defect_record, **shipment, shipment_line** (출하까지) |
| PRD-06 다시 보기 | FR-PRD-06-01~09 | (새 엔터티 없음) | equipment_state_log, wip_log, sensor_sample, alarm_event, bottleneck_log |
| AST-01 교대 시작 브리핑 | FR-AST-01-01~07 | (저장 안 함 — 화면) | shift_report, shift, production_lot, production_order, alarm_event, notification, pm_task, tool, inventory_item, maintenance_work_order, document_revision |
| AST-02 먼저 알리기 | FR-AST-02-01~19 | notification, notification_recipient, notification_rule | alarm_event, shift, shift_report, bottleneck_log, wip_log, production_lot, inventory_item, pm_task, tool, maintenance_work_order, work_record, alarm_guide_map, internal_doc, cmm_import, inspection_result, app_user |
| AST-03 문서 수정 이력·알림 | FR-AST-03-01~09 | document_revision, document_revision_change, internal_doc, notification | maintenance_work_order, work_record, shift_report, daily_report, pm_record, role_permission |
| MNT-01 질문 답변 | FR-MNT-01-01~12 | (질문 기록 저장 안 함) | doc_chunk, internal_doc, alarm_master, alarm_guide_map, 조회 도구 대상 엔터티 (equipment_state_log, alarm_event, 지표, operation_report, production_lot, production_order, work_record, pm_task, tool, inventory_item) |
| MNT-02 지침카드 | FR-MNT-02-01~14 | (저장 안 함 — 화면) | alarm_event, alarm_master, alarm_guide_map, isolation_point, production_lot, equipment_state_log, work_record |
| MNT-03 정비 작업지시서 | FR-MNT-03-01~14 | maintenance_work_order, work_order_step, work_order_part, document_revision | alarm_event, notification (2단계 계기), isolation_point, equipment, work_record, inventory_item, app_user |
| MNT-04 예방 정비 일정 | FR-MNT-04-01~10 | pm_record, pm_task, inventory_txn, equipment_state_log (MAINT 구간), document_revision | equipment, inventory_item, app_user |
| MNT-05 작업기록서 | FR-MNT-05-01~15 | work_record, work_record_check, work_record_part, inventory_txn, document_revision | maintenance_work_order, work_order_step, alarm_event, inventory_item, equipment_state_log |
| INV-01 재고·출하 | FR-INV-01-01~13 | inventory_item, inventory_txn, raw_material_lot (원자재 입고·입고 검사 상태), shipment, shipment_line, document_revision | work_record_part, pm_record, tool_change, production_lot, production_order, lot_hold, role |
| ML-01 공구 수명 | FR-ML-01-01~08 | tool, tool_usage, tool_change | tool_type, operation_report, alarm_event (362·174) |
| QLT-01 검사 기록·불량 집계 | FR-QLT-01-01~22 | inspection_plan, inspection_result, defect_record, inspection_item (Cpk 전수 표시), cmm_import, notification (CMM 알림) | production_lot, lot_hold, defect_code, equipment (CMM-01), app_user |
| AI 비서 공통 | FR-AST-COM-01~21 | (규칙) document_revision.author_kind, equipment_state_log.reason_suggested_code, notification.report_rank (전부 보고 순서, 계산) | doc_chunk, internal_doc, alarm_master, alarm_guide_map, notification_rule |
| 비기능: 데이터 | NFR-DATA-01~13 | 생성기가 모든 엔터티를 만든다 (NFR-DATA-12 역할 바꿔 보기는 화면 기능 — 새 엔터티 없음, app_user·role만 읽음). NFR-DATA-13 보관 기간 = 6.53 (모든 엔터티) | 8장 R-01~R-87 |
| 비기능: 보안·권한 | NFR-SEC-01~08 | app_user, role, role_permission (MGR 전체 조회 R-76) | 모든 `~_by` 칸. NFR-SEC-08(로컬 LLM, 외부 전송 없음)은 새 엔터티 없음 — doc_chunk·internal_doc·운영 기록을 밖으로 보내지 않음 (R-87) |
| 비기능: 안전 | NFR-SAFE-01~05 | work_record_check, maintenance_work_order.safety_block_doc_rev | isolation_point, alarm_master.lockout_level, pm_task.lockout_level |
| 비기능: 신뢰성·감사 | NFR-REL-01~03 | document_revision, `~_by`·`~_at` 칸 | — |
| 비기능: 성능 (기록 간격) | NFR-PERF-03 | wip_log.interval_type, sensor_sample.interval_type | — |
| 비기능: 사용성 | NFR-USE-04·07·08·09 | (화면 규칙 — 새 엔터티 없음) | NFR-USE-09 현장 화면 글자 크기는 화면 계산. notification.report_rank (NFR-USE-07 항목을 빼지 않음) |
| 비기능: AI 품질 | NFR-AIQ-05·09 | notification.message_source (형식이 틀리면 기본 문구) | doc_chunk.embedding |

**최종본 새 ID ↔ 엔터티** (2026-10-07 변경 명세 2장 새 ID 전부)

| 새 ID | 이름 | 주로 쓰는 엔터티·속성 | 읽기만 하는 엔터티 | 규칙 |
|---|---|---|---|---|
| FR-PRD-01-27 | 실제 크기 설비·공장 배치 3D | plant_layout, layout_object, equipment_part_shape, equipment (size_·center_·facing·size_source_tag·ref_model) | wip_buffer, wip_log, equipment_state_log | R-83 |
| FR-PRD-01-28 | 현장 보기 (OPR 큰 모니터) | (저장 안 함 — 화면 SCR-26) | plant_layout, layout_object, equipment_part_shape, equipment, equipment_state_log, notification (처리 안 된 알람), shift, shift_report (브리핑 5줄 요약 재료), tool, pm_task | R-73, R-83 |
| FR-AST-02-18 | 반복 알람 2단계 (조치 계획 뒤 재발) | notification (REPEAT_ALARM_2, CAUSE_CHECK_REQUEST, prev_stage_notification_id, repeat_stage_status, effect_check_due_at), maintenance_work_order (trigger_kind, trigger_notification_id), work_record (cause_check_notification_id) | alarm_event, alarm_guide_map, internal_doc (DOC-03 §1.4·해당 절), equipment | R-70, R-71 |
| FR-AST-02-19 | 병목 조치 제안 | notification (BOTTLENECK_MOVE).related_info | bottleneck_log, internal_doc (DOC-07 §7.5), tool, inventory_item | R-84 |
| FR-AST-COM-21 | 전부 보고·정해진 순서 | notification.report_rank (계산), daily_report.issues_summary, shift_report.handover_text | work_record_check (잠금 중), equipment_state_log, production_lot, lot_hold | R-73, R-74 |
| FR-INV-01-11 | 완제품 재고 | inventory_item (FG-BRK-A100), inventory_txn (FG_IN·ADJUST, fg_lot_no) | production_lot (judged_at, status), lot_hold (released_at), inspection_plan | R-69 |
| FR-INV-01-12 | 출하 기록 | shipment, shipment_line, inventory_txn (SHIP_OUT), document_revision (SHIPMENT) | production_lot, production_order (due_at), app_user | R-67, R-68, R-69, R-86 |
| FR-INV-01-13 | 품목별 관리 역할 | inventory_item.owner_role | role, role_permission | R-77, R-39 |
| FR-QLT-01-14 | CMM 측정 결과 자동 입력 | cmm_import, inspection_result (input_method, cmm_import_id) | equipment (CMM-01), inspection_item | R-78 |
| FR-QLT-01-15 | 측정 지시 넘기기 | cmm_import (lot_no, part_seq, insp_kind), inspection_result.check_status | inspection_plan, lot_hold | R-78 |
| FR-QLT-01-16 | 판정 다시 계산 | inspection_result (judgement, cmm_judgement, is_judgement_mismatch), notification (CMM_JUDGE_MISMATCH) | inspection_item | R-79 |
| FR-QLT-01-17 | 못 읽은 파일 | cmm_import (status, error_kind, error_text, original_file_ref), notification (CMM_FILE_ERROR) | — | R-80 |
| FR-QLT-01-18 | 결과가 안 올 때 | notification (CMM_NO_RESULT) | production_lot, equipment (CMM-01) | R-80 (시간 [선택 필요: 기술 회의]) |
| FR-QLT-01-19 | 수동 입력 남기기 | inspection_result (input_method MANUAL, entered_by, checked_by) | — | R-81 |
| FR-QLT-01-20 | 사람 확인 칸 | inspection_result (inspector_id, input_method TABLET, check_status) | app_user | R-78 |
| FR-QLT-01-21 | 온도 기록 | inspection_result (room_temp_c, part_temp_c, is_temp_flag), cmm_import (machine_temp_c, temp_comp_on) | — | R-82 |
| FR-QLT-01-22 | 재측정 보관 | inspection_result (remeasure_seq, use_for_judgement, checked_by) | cmm_import | R-81 |
| NFR-DATA-13 | 데이터 보관 기간 | (규칙) 6.53, app_user.is_active | 모든 엔터티 | R-75 |
| NFR-USE-09 | 현장 화면 글자 크기 (보는 거리 식) | (화면 규칙 — 새 엔터티 없음) | — | — |
| NFR-SEC-08 | 비서 데이터 외부 전송 없음 (로컬 LLM) | (규칙 — 새 엔터티 없음) | doc_chunk, internal_doc | R-87 |
| NFR-AIQ-09 | 비서 출력 형식(JSON 칸) 확인 | notification.message_source | — | R-87 |
| SCR-26 | 현장 보기 (화면) | FR-PRD-01-28과 같음 | 같음 | — |
| DOC-07 §7.5 | 병목 원인별 조치 (사내 문서 절) | internal_doc (DOC-07), doc_chunk (§7.5) | — | R-84 |

- FR-QLT-01-14~22는 R3 7.1 초안 그대로 9개다 (변경 명세 3장 R3).

**엔터티 → 요구사항 (빠짐 점검)**

| 엔터티 | 요구사항 (대표) | 엔터티 | 요구사항 (대표) |
|---|---|---|---|
| process | FR-PRD-01-01·08 | maintenance_work_order | FR-MNT-03-01~14, FR-AST-02-18 |
| equipment | FR-PRD-01-01·20·27 | work_order_step | FR-MNT-03-05, FR-MNT-05-04 |
| isolation_point | FR-MNT-03-10 | work_order_part | FR-MNT-03-12 |
| product | FR-PRD-05-02, FR-QLT-01-02 | work_record | FR-MNT-05-01~13·15 |
| work_day | FR-PRD-04-01·02 | work_record_check | FR-MNT-05-04·05 |
| shift | FR-PRD-01-15, FR-PRD-02-01 | work_record_part | FR-MNT-05-07·10 |
| wip_buffer | FR-PRD-01-06·07 | pm_task | FR-MNT-04-01~04 |
| raw_material_lot | FR-PRD-05-01·02, FR-INV-01-04 | pm_record | FR-MNT-04-05~08·10 |
| production_order | FR-PRD-03-01·03 | tool_type | FR-ML-01-01·02 |
| production_lot | FR-PRD-05-01~11 | tool | FR-ML-01-03·04 |
| operation_report | FR-PRD-01-20, FR-PRD-05-03 | tool_usage | FR-ML-01-01·03 |
| wip_log | FR-PRD-01-06, FR-PRD-06-06 | tool_change | FR-ML-01-06 |
| bottleneck_log | FR-PRD-01-08·09 | inventory_item | FR-INV-01-01·06·11·13 |
| lot_hold | FR-PRD-05-06·08 | inventory_txn | FR-INV-01-02·08·09·11·12 |
| alarm_master | FR-MNT-02-02~04 | inspection_item | FR-QLT-01-02·08 |
| alarm_guide_map | FR-MNT-02-05, FR-MNT-01-07 | defect_code | FR-QLT-01-11 |
| alarm_event | FR-MNT-02-01, FR-AST-02-01 | inspection_plan | FR-QLT-01-03·05·06 |
| equipment_state_log | FR-PRD-01-03·18 | inspection_result | FR-QLT-01-01·12·14~22 |
| downtime_reason | FR-PRD-01-18 | defect_record | FR-QLT-01-11 |
| sensor_item | FR-PRD-01-14 | shift_report | FR-PRD-02-01~12 |
| sensor_sample | FR-PRD-01-12, FR-PRD-06-06 | daily_report | FR-PRD-04-01~09 |
| app_user | NFR-SEC-01 | document_revision | FR-AST-03-01~06 |
| role | NFR-SEC-01 | document_revision_change | FR-AST-03-02·04 |
| role_permission | NFR-SEC-02·03 | internal_doc | FR-AST-03-09 |
| notification_rule | FR-AST-02-14·16 | doc_chunk | FR-MNT-01-03·10 |
| notification | FR-AST-02-01~15·18·19, FR-AST-COM-21 | notification_recipient | FR-AST-02-02 |
| **plant_layout** | FR-PRD-01-27·28 | **shipment** | FR-INV-01-12 |
| **layout_object** | FR-PRD-01-27·28 | **shipment_line** | FR-INV-01-12, FR-PRD-05-01 |
| **equipment_part_shape** | FR-PRD-01-27 | **cmm_import** | FR-QLT-01-14·15·17 |

- 요구사항이 없는 엔터티: **없음** (58개 모두 위 표에 있음. 굵은 글씨 6개는 최종본 새 엔터티).

---

## 10. 기획서 12.4 ↔ 이 문서 이름 대응표

| 기획서 12.4 [제안] | 설계서 5장 | 이 문서 | 바뀐 점 |
|---|---|---|---|
| equipment | equipment (5.1) | `equipment` + **`isolation_point`** | 차단 지점을 따로 뺌 (설비마다 2~3개라 한 칸에 넣을 수 없음) |
| equipment_state_log | equipment_state_log (5.7) | `equipment_state_log` | 정지 사유·추천·확정 칸을 여기에 붙임 |
| downtime_reason | downtime_reason (5.10) | `downtime_reason` | 코드표로 둠. 정지 1건의 기록은 상태 구간에 |
| alarm_master / alarm_guide_map | (5.8, 이름 없음) | `alarm_master`, `alarm_guide_map` | 같음 |
| alarm_event | alarm_event (5.8) | `alarm_event` | 같음 |
| — | sensor_sample (5.9) | `sensor_sample` + **`sensor_item`** | **기획서 12.4에 없음** → 설계서 이름을 씀. 센서 항목 표를 더함 |
| raw_material_lot | raw_material_lot (5.4) | `raw_material_lot` | 같음 |
| production_order | production_order (5.5) | `production_order` | 같음 |
| production_lot | production_lot (5.5) | `production_lot` + **`lot_hold`** | 보류·해제·폐기의 누가·언제를 따로 뺌 (NFR-REL-03) |
| operation_report | operation_report (5.5) | `operation_report` | 수량을 DOC-07 PQ·GQ·RQ·SQ로 나눔 |
| wip_log | wip_log (5.6) | `wip_log` + **`wip_buffer`** | 위치별 한도·경고 기준을 따로 뺌 |
| bottleneck_log | bottleneck_log (5.18) | `bottleneck_log` | 속도 손실 칸을 더함 (설계서 5.10 "병목 구간마다 저장") |
| shift_target | (5.2·5.3, 이름 없음) | **`shift`** (target_qty), **`work_day`** (daily_target_qty) | 교대 목표를 교대 엔터티 칸으로 넣음 |
| — | (5.3 제품, 이름 없음) | **`product`**, **`process`** | 새로 둠 |
| maintenance_work_order | maintenance_work_order (5.11) | `maintenance_work_order` + **`work_order_step`**, **`work_order_part`** | 작업 순서·예상 부품을 여러 줄로 뺌 |
| work_record | work_record (5.11) | `work_record` + **`work_record_check`**, **`work_record_part`** | 체크칸·사용 부품을 여러 줄로 뺌 |
| pm_task / pm_record | pm_task, pm_record (5.12) | `pm_task`, `pm_record` | 같음 |
| tool / tool_usage | tool, tool_usage (5.13) | `tool`, `tool_usage` + **`tool_type`**, **`tool_change`** | 종류별 단위·한도와 교체 기록을 따로 뺌 |
| inventory_item / inventory_txn | inventory_item, inventory_txn (5.14) | `inventory_item`, `inventory_txn` | 같음 |
| inspection_plan / inspection_result | inspection_result (5.15), inspection_plan (5.15) | `inspection_plan`, `inspection_result` + **`inspection_item`**, **`defect_code`**, **`defect_record`** | 검사 항목·불량 코드·불량 기록을 더함 |
| shift_report / daily_report | shift_report, daily_report (5.16) | `shift_report`, `daily_report` | 같음 |
| document_revision | document_revision (5.16) | `document_revision` + **`document_revision_change`** | 바뀐 칸 전·후를 여러 줄로 뺌 |
| notification | (없음) | `notification` + **`notification_recipient`**, **`notification_rule`** | 받는 사람과 규칙을 따로 뺌 |
| internal_doc / doc_chunk | (13장, 이름 없음) | `internal_doc`, `doc_chunk` | doc_chunk는 칸만 (세부는 AI 비서 설계) |
| app_user | app_user (5.17) | `app_user` + **`role`**, **`role_permission`** | 13장 권한표를 데이터로 둠 |
| (최종본) 3D 배치 | 설계서_최종본 5.1 (설비 크기·참고 모델·배치 좌표), 10장 masters | `equipment` 배치 칸 + **`plant_layout`**, **`layout_object`**, **`equipment_part_shape`** | 공장·배치 물체·부품 도형을 따로 뺌 (D-02, R1) |
| (최종본) 완제품·출하 | 설계서_최종본 5.14 (13품목), 새 5.20 (shipment) | `inventory_item`·`inventory_txn` + **`shipment`**, **`shipment_line`** | 출하 머리와 로트 줄을 나눔 (R5 표 C) |
| (최종본) CMM 자동 입력 | 설계서_최종본 5.15 (입력 방식·결과 파일 가져오기 기록·부품 온도) | `inspection_result` 새 칸 + **`cmm_import`** | 결과 파일 1개의 수신 기록을 따로 뺌 (R3 5장) |

- 기획서 12.4와 설계서 5장의 **이름이 서로 다른 것은 없었다.** 다른 점은 ① 기획서 12.4에 `sensor_sample`이 빠짐 ② 설계서에 이름이 없는 것(제품, 달력·교대, 알람 코드집, 알림, 사내 문서)이었다. ①은 설계서 이름을 쓰고, ②는 기획서 12.4 이름을 쓰거나 새로 [제안]했다.
- 새로 둔 엔터티 **21개**: `process`, `product`, `work_day`, `isolation_point`, `wip_buffer`, `sensor_item`, `lot_hold`, `work_order_step`, `work_order_part`, `work_record_check`, `work_record_part`, `tool_type`, `tool_change`, `inspection_item`, `defect_code`, `defect_record`, `document_revision_change`, `notification_recipient`, `notification_rule`, `role`, `role_permission`. `shift`는 12.4의 `shift_target`을 바꾼 것, `sensor_sample`은 설계서에서 가져온 것.
- 개수 맞추기: 기획서 12.4 30개 (`shift_target` → `shift`) + `sensor_sample` 1개 + 새 엔터티 21개 = **52개** (v1).
- 최종본: 52개 + 2026-10-06 회의로 더한 6개 (`plant_layout`, `layout_object`, `equipment_part_shape`, `shipment`, `shipment_line`, `cmm_import`) = **58개**. 새 엔터티 이름은 변경 명세 4장 이름(모든 문서 공통)을 쓴다. 기획서_최종본 12.4에 이 6개가 없으면 이 문서 이름을 따른다.

---

## 11. 물리 ERD로 넘기는 것

| # | 넘기는 것 | 이 문서에서 한 것 | 물리 ERD에서 정할 것 |
|---|---|---|---|
| 1 | DB 제품 | 정하지 않음. 운영 데이터는 DB에 저장 (JSON 파일 아님, D-18) | **[선택 필요: 기술 회의]** (기획서 12.2 [제안] — 팀 선택) |
| 2 | 물리 자료형 | 쉬운 논리 형식만 (2.4) | 문자 길이, 소수 자리, 날짜시각 정밀도(초·밀리초), **시간대** (야간 교대가 자정을 넘음) |
| 3 | 기본 키 만들기 | "일련번호"·업무 번호 표시만 | 일련번호 방식, 업무 번호(PO-, LOT-, MW-, MR-, SHP-) 자동 매기기 규칙 |
| 4 | 인덱스 | 다루지 않음 | 시각 범위 조회 (상태·재공·센서·알람), 알람 번호·설비로 같은 사례 찾기 (FR-MNT-05-11) |
| 5 | 파티션·보관 | **보관 기간 표는 정함** (6.53, R-75, NFR-DATA-13 — R2) | `sensor_sample` 1초 구간, `wip_log`, `equipment_state_log`의 크기와 파티션. **보관 기간이 지난 데이터의 실제 삭제·1시간 집계로 줄이기·보관 저장소 이동 방식**, 1초 구간 2년 예외·15년 연결 알람 표시 방법, 보관 저장소의 읽기 전용·다시 꺼내기 → **[선택 필요: 기술 회의]** |
| 6 | 계산 속성 | "계산" 표시 (completed_qty, on_hand_qty, usage_rate_pct, next_due_date, stop_loss_qty 등) | 저장 칼럼 / 뷰 / 서버 계산 중 선택, 다시 계산 시점 |
| 7 | 여러 엔터티를 가리키는 칸 | `document_revision`(doc_type + doc_key, 최종본 7종), `notification`(선택 FK 여럿), `inventory_txn`(출처 FK 여럿, 최종본 fg_lot_no·shipment 줄 추가), `maintenance_work_order.trigger_kind`(여러 값) | 칼럼 설계(공통 문서 표, 출처별 칼럼, 연결 표 등)와 제약 |
| 8 | 코드 목록 | 6장 값 | 코드 표 / 값 제약 / 애플리케이션 상수 중 선택, 영어 코드 확정 |
| 9 | 문서 내용 저장 | `content_snapshot` (그 버전 전체 내용) | 저장 형식 (구조화 문서 등) |
| 10 | 사내 문서 조각·임베딩 | `doc_chunk` 칸만 (원문 출처 칸 없음, 검색 대상 DOC-01~07 + 용어집) | 나누는 방법, 임베딩 모델·차원, 검색 저장소 → **AI 비서 설계에서 [선택 필요: 기술 회의]** |
| 11 | 로그인·세션 | 넣지 않음 | 로그인 칸, 비밀번호 저장 방식 (NFR-SEC-07) |
| 12 | 삭제·변경 동작 | 다루지 않음 | 부모를 지울 때 동작. 확정 문서·기록은 지우지 않는 것을 기본으로 [제안] |
| 13 | 권한 저장 | `role_permission` 엔터티 | 표로 둘지 코드로 둘지 |
| 14 | 가상 데이터 표시 | 묶음 단위인지 줄 단위인지 정하지 않음 (R-59) | 표시 방법 |
| 15 | 사진 첨부 | 메모 칸만 (pm_record.memo) | 파일 저장 방식 |
| 16 | 공구 사용 기록 단위 | 공정 실적 단위 | 부품 1개 단위로 쌓을지 |
| 17 | 생성기 설정 | 다루지 않음 (설계서 10장 `config.json` — 설정 파일은 JSON (D-18)) | 운영 DB와 분리 |
| 18 | **로컬 LLM** (최종본) | 비서 LLM은 로컬 LLM으로 확정 (R-87). 비서 질문·답은 저장 안 함. 비서 입출력 JSON 칸은 저장 엔터티 없음 (결과만 notification·document_revision 등에) | **LLM 모델, 임베딩 모델, 컴퓨터 사양(GPU·메모리 등), LLM 실행 도구(형식 강제 기능 포함) → [선택 필요: 기술 회의]** |
| 19 | 설정 파일(JSON)과 기준 정보 (최종본) | 라인 구성(plant_layout·layout_object·equipment_part_shape·equipment 배치 칸), 알림 기준값(notification_rule), 교대 시간(shift 시각)을 논리 엔터티로 둠 (R-58) | 설정 파일에서 읽어 DB 기준 정보로 넣을지, 화면·서버가 바로 읽을지, 바꾼 기록을 어떻게 남길지 → [선택 필요: 기술 회의] |
| 20 | CMM 결과 파일 (최종본) | `cmm_import` 칸 (받은 시각·상태·오류·원본 보관 위치) | 공유 폴더 위치·이름, 파일 이름 규칙, 파일 감시 방식·주기, 측정 지시 파일과 "측정 시작" 기록을 엔터티로 둘지, 결과 미수신 대기 시간, 환경 센서(방 온도) 연결 → [선택 필요: 기술 회의] |
| 21 | 3D 좌표 (최종본) | mm 좌표, 원점·축 (plant_layout, R-83) | 3D 엔진 좌표로 바꾸는 방법 (엔진마다 위쪽 축이 다름), 부품 도형의 세부 위치 → [선택 필요: 기술 회의] |

---

## 12. 개정 기록

| 버전 | 날짜 | 내용 | 작성 |
|---|---|---|---|
| v1 | 2026-10-05 | 처음 작성. 설계서_v3 5장·9장, 기획서_v4 4.3·4.5·5장·12.4·13장·19장, 요구사항정의서_v1, DOC-01·02·04·05·06·07 기준. 엔터티 52개 (8개 영역), 코드 목록 41개, 관계 106개, 규칙 R-01~R-66 | 팀 |
| v1 (같은 날 맞춤) | 2026-10-05 | 요구사항정의서_v1(277개)·UI설계서_v1과 맞춤. "UI 설계" [선택 필요] 9개를 UI설계서 9장·9.3으로 채움: 6.9 입고 검사 대기 + R-06a, 6.13 완료 계기, 6.15 간이 기록 초안 없음·확정자, 6.16 다시 확정 없음, shift_report.availability_pct, inventory_txn.txn_by, pm_record.done_by + **recorded_by·current_version 새 속성**, notification **process_kind·process_memo 새 속성** + 6.36 SHIFT_REPORT_PENDING·처리 표, R-08. 팀 확정 3개: pm_task_id [가상] 확정, 예방 정비 기록을 수정 이력 대상(6.17 PM_RECORD, 관계 93 6종), DOC-06 4.1 판정 대기. 공구 번호 T01~T05 [가상] (6.25, tool.tool_no). 9장 추적표에 새 요구사항 5개 범위 반영. 엔터티 수 52개 그대로 | 팀 |
| **최종본** | 2026-10-07 | **2026-10-06 문서 검토 회의 결정(D-01~D-19) 반영** (변경 명세 4장, 조사 R1~R5). **엔터티 52 → 58** (새 6개: `plant_layout`, `layout_object`, `equipment_part_shape`, `shipment`, `shipment_line`, `cmm_import`). **코드 목록 41 → 54** (새 6.42 작업지시서 계기 ~ 6.54 반복 알람 단계 상태 — 13개), **관계 106 → 124** (새 107~124), **규칙 R-01~R-66 → R-01~R-87** (새 R-67~R-87, 21개). 속성 추가: `equipment`(외형 X·Y·Z, 배치 가운데 X·Y, 정면 방향, 크기 근거, 참고 모델), `inventory_item.owner_role` (품목 13개, 완제품 FG-BRK-A100, 완제품 안전 재고 비움), `inventory_txn`(fg_lot_no·shipment_no·ship_lot_no, 거래 종류 FG_IN·SHIP_OUT, 출처 LOT_PASS·SHIPMENT, txn_by 품목 관리 역할별), `inspection_result`(입력 방식, cmm_import 연결, 측정기 판정과 플랫폼 재계산 판정 분리, 판정 불일치·온도 확인 표시, 확인 상태·확인자, 재측정 순번·판정에 씀, 수동 입력자; 측정실 온도 필수 → 조건), `maintenance_work_order`(계기 trigger_kind — 여러 값, trigger_notification_id), `work_record.cause_check_notification_id`, `notification`(보고 순위 계산, cmm_import_id, prev_stage_notification_id, 반복 알람 단계 상태·효과 확인 기한), `internal_doc.doc_kind`(용어집 검색 대상 참). 속성 삭제: **`doc_chunk.original_source`·`alarm_guide_map.original_source`(원문 출처, D-03)**. 이름 변경: `daily_report.top3_summary` → `issues_summary` "오늘의 문제 (전체 N건)" (D-07). 코드 수정: 6.8(출하 가능 = 합격·해제), 6.13·6.14(2단계), 6.16(06:00), 6.17(용어집·출하 기록 SHIPMENT), 6.27(13개·관리 역할), 6.28, 6.36(REPEAT_ALARM_2·CAUSE_CHECK_REQUEST·CMM 알림 3종 → 22행, 병목 관련 정보 DOC-07 §7.5, 재고 부족 받는 사람), 6.37(재고 관리·MGR 전체 조회), 6.41. 규칙 수정: R-02, R-11, R-35(7종), R-36, R-38(0-1 순위), R-39, R-50, R-51, R-52(원문 출처 삭제), R-55, R-58(재고 관리 역할·설정 파일 JSON). 작업지시서·작업기록서 30일 건수 15~25 → **약 5~9건** (설계서_최종본 5.11). 생성기 설정 `config.yaml` → `config.json` (D-18). 반복 알람 2단계 가상 사례 VF2-02 108 (9/8·9/9·9/10 → 9/14 재발 → 9/15 원인 점검 확정). 30일 출하 25건, 출하 14:00 [가상]. 문서 이름 링크를 최종본으로 | 팀 (편집 담당 E) |
| 최종본 (교차 점검, 2026-10-07) | 2026-10-07 | 문서끼리 맞춤 (엔터티 58개 그대로): 관계 93 "문서의 버전" 6종 → **7종**(shipment 추가, R-35·관계 124와 같게), 6.47 확인 상태 `NOT_NEEDED 확인 필요 없음` → **`NORMAL 정상`** (DOC-06 §3.5 정상 / 확인 필요 / 반장 확인), inspection_result.check_status 설명, 6.36 처리 표 CMM_NO_RESULT "(반장 확인)", doc_chunk.doc_rev 설명(개정은 호버 카드에만), ERD 그림의 source_section "원문" 삭제·current_rev 예 Rev.1·safety_block_doc_rev 예 "DOC-05 Rev.1", daily_report·doc_chunk 표 가운데 끼어 있던 설명 줄을 표 뒤로 옮김, 6.17 설명·12장 #6·#17 "해결", R-75 출처에 DOC-07 §11 | 교차 점검 |

**문서끼리 다르던 점과 이 문서의 선택**

| # | 다른 점 | 이 문서의 선택 |
|---|---|---|
| 1 | 로트 상태 "판정 대기": 설계서 5.15에는 있고 DOC-06 4.1 상태 표에는 없음 | 설계서를 따라 **넣음** (WAIT_JUDGEMENT, 검사 대기와 합격·보류 검토 사이). → 같은 날 **DOC-06 4.1에 "판정 대기" 줄 추가** (해결) |
| 2 | 설계서 9장 "정지 등급 알람 1건마다 작업지시서 1건" ↔ 기획서 5.2 "작업지시서는 OP-30만" | 기획서 5.2 (19장 결정): **OP-30 정지 등급만** (R-02). 요구사항정의서 12장 #2와 같음 |
| 3 | 설계서 9장 재공 한도 "30개" ↔ 기획서 19장 "OP-30→40만 60개" | 19장: `wip_buffer.limit_qty` 30 / WIP-30-40만 60 (R-13) |
| 4 | 설계서 5.5 공정 실적 "완료, 불량, 재작업 수량" ↔ DOC-07 4.3 PQ·GQ·RQ·SQ | DOC-07 (더 자세함): 생산 수량·양품·재작업·불량 4개 (R-19) |
| 5 | DOC-04에 예방 정비 **항목 코드가 없음** (절 번호 + 항목 이름만) | `pm_task_id` 형식 `PM-{설비}-{절}-{순번}`을 **[가상]으로 확정**하고 DOC-04 5장 "항목 코드" 줄에 같은 규칙을 넣음 (해결) |
| 6 | DOC-04 5장 "확정한 실시 기록을 고치면 수정 이력(AST-03)에 남는다" ↔ FR-AST-03-01 대상 문서 5종에 예방 정비 기록이 없음 | **대상에 넣음** [제안] (기획서 4.5 "모든 문서", 5장 흐름도 "모든 문서의 수정은 AST-03 수정 이력에 남음", 재고가 빠지는 확정 기록): 6.17 PM_RECORD, pm_record.current_version, FR-AST-03-01 "여섯 종류"로 고침 (v1 같은 날). 최종본에서 출하 기록을 더해 일곱 종류로 맞춤 (#17) (해결) |
| 7 | 기획서 12.4 `production_lot`에 "상태·보류" 칸 ↔ DOC-06 4.1·4.2 보류·해제·폐기 승인(누가·언제) | `lot_hold`로 분리 (NFR-REL-03 "사람 결정마다 누가·언제") |
| 8 | 기획서 12.4 `equipment`에 "차단 지점" 칸 ↔ DOC-05 §3 설비마다 2~3개 | `isolation_point`로 분리 |
| 9 | 기획서 12.4 `shift_target` ↔ 설계서 5.2·5.3 달력·교대 (테이블 이름 없음) | `shift.target_qty`, `work_day.daily_target_qty`로 넣음 |
| 10 | 기획서 12.4에 `sensor_sample` 없음 ↔ 설계서 5.9 | 설계서 이름 `sensor_sample` |
| 11 | 알람 번호 "WSH-01"·"WSH-02"(DOC-02 [가상 번호]) ↔ 설비 ID "WSH-01" (설계서 5.1) | 서로 다른 엔터티의 키라 그대로 둠. 화면에서 헷갈리지 않게 알람은 "알람 WSH-01"로 표시 [제안] |
| 12 | 공구 번호: 설계서는 M6 탭 T05만 적음 | T01 페이스밀 인서트, T02 엔드밀 Ø10, T03 보링바 인서트, T04 드릴 Ø5.0, T05 M6 탭으로 **[가상] 확정** (6.25). 설계서 5.13, DOC-01 7.1, DOC-07 9장 표에도 같은 번호를 넣음 (해결) |
| 13 | 간이 작업기록의 AI비서 초안 여부, 다른 공정 정지 등급 간이 기록의 확정자 | AI비서 초안 **없음**, 다른 공정 정지 등급 확정자 = **MNT** (UI설계서 9장 #5, 9.3 #4) (해결) |
| 14 | UI 설계로 넘긴 나머지 8개 (원자재 입고 검사 전 상태, 다시 확정 절차, 작업지시서 완료 계기, 교대 보고서 가동률 대상, 재고 조정 기록자, 작업자 예방 정비 기록, 알림 처리 권한, 취소 작업지시의 로트 수량) | UI설계서 9장 #4·9.3 #1~3·5~8로 정함: 6.9 WAIT_RECEIPT_CHECK + R-06a, 6.16 REVISED·R-35, 6.13 DONE, shift_report.availability_pct, inventory_txn.txn_by, pm_record.done_by·recorded_by, notification.process_kind·processed_by·process_memo + 6.36 처리 표, R-08 (해결) |
| 15 | (최종본) R5 표 H5 "06:00 미확정이면 야간 반장 + MGR에게 알림" ↔ 변경 명세 D-08 "해당 SUP에게 확정 요청 알림 (FR-AST-02-17)" | 명세를 따름: SHIFT_REPORT_PENDING 받는 사람 = 그 교대 반장 (MGR은 일일 보고서 화면에서 잠정 표시로 봄) |
| 16 | (최종본) 용어집(GLOSSARY)을 검색 대상에 넣을지 (v1 [선택 필요]) | D-05로 **넣음** (internal_doc.is_search_target 참, 6.52) (해결) |
| 17 | (최종본) R5 표 C "출하 확정 뒤 수정은 사유 필수 (FR-AST-03 모양)" ↔ FR-AST-03-01 대상 문서 6종 | 출하 기록을 수정 이력 대상에 **넣음** [제안] (6.17 SHIPMENT, 관계 124, R-35 7종). 요구사항 FR-AST-03-01·기획서 AST-03·4.5·UI설계서 SCR-17을 7종으로 맞춤 (교차 점검 2026-10-07) (해결) |
| 18 | (최종본) 반복 알람 2단계: OP-30 정지 등급 알람이 재발해 2단계가 되면 작업지시서가 겹침 (R4 3.2 [선택 필요]) | 총괄 정정(2026-10-07): **작업지시서 1개, 계기 2개 함께** + 원인 점검 단계 덧붙임 [가상] (6.42, R-71) (해결) |
| 19 | (최종본) 다른 공정 2단계의 원인 점검 간이 작업기록은 알람 1건에 1건(UK)인 alarm_event_id로 연결할 수 없음 (그 알람에는 이미 간이 기록이 있음) | `work_record.cause_check_notification_id` 칸을 더함 [제안] |
| 20 | (최종본) 설계서 5.5 납기 "투입 후 1~2일" ↔ R5 1.7 G2 | G2로 구체화 (주간 시작 +1일, 야간 시작 +2일, 일요일이면 월요일) — production_order.due_at |
| 21 | (최종본) R3 7.1 "결과가 안 올 때"의 측정 시작 시각을 둘 엔터티가 없음 | 새 엔터티를 만들지 않고 [선택 필요: 기술 회의] (11장 #20) |

**남긴 [선택 필요]**

| 정할 곳 | 항목 |
|---|---|
| 기술 회의 | DB 제품, 물리 자료형·인덱스·파티션 (11장), 사용자 ID·로그인, 여러 엔터티를 가리키는 칸의 물리 설계, 문서 내용 저장 형식, 예상 완료 시각 계산 방법, 알림 규칙의 기준 숫자를 칸으로 나눌지, 코드 목록 저장 방식, 권한 저장 방식, 가상 표시 방법, 사진 저장, 공구 사용 기록 단위. **최종본**: 보관 기간의 실제 삭제·집계·이동 방식, 로컬 LLM 모델·임베딩 모델·컴퓨터 사양·실행 도구, 설정 파일(JSON)과 DB 기준 정보의 관계, CMM 공유 폴더·파일 감시·결과 미수신 대기 시간·측정 시작 기록, 3D 엔진 좌표 변환, 작업지시서 계기(여러 값) 저장 방식 |
| AI 비서 설계 (기술 회의 뒤) | `doc_chunk` 나누기·임베딩·검색 방식 |
| 팀 | 15년 보관 임시값 (고객 CSR이 정해지면), 사용자 이름 처리(비활성 계정), 야간 반장 05:00~06:00 확정 시간을 근무 계획에 넣을지 (R5 H7) |

- UI 설계·팀 확정·데이터 생성 때로 넘겼던 항목은 같은 날 맞춤에서 모두 정했다 (위 #1·5·6·12·13·14).
