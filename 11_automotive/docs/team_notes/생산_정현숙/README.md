# production — 생산 파트 자료 모음

> 정리일: 2026-10-03 / 범위: 5공정(OP-10~50) 흐름, 작업지시, 생산실적, AI 비서 역할
> 원본은 `11_automotive/docs/`, `data/`에 그대로 있고, 이 폴더에는 **생산 파트에 필요한 것만 복사**했다. (조사로 새로 받은 파일은 `research/`로 옮겼다.)

## 폴더 구성

```
production/
├─ README.md                      이 문서
├─ 01_생산파트_기능정의.md          플랫폼에서 생산 파트가 보여줄 기능
├─ 02_AI비서_역할.md               생산 파트에서 AI 비서가 하는 일
├─ TEAM_DECISIONS_AND_NEEDS.md    팀이 정할 것, 더 필요한 문서·확인 사항
├─ reference/                     기존 문서 중 생산 파트에 쓰는 것 (복사본)
│   ├─ 01_작업지시_데이터모델/
│   ├─ 02_생산지표_KPI/
│   ├─ 03_품질_검사_공차/
│   ├─ 04_설비_공정별_매뉴얼/
│   ├─ 05_절삭조건_셋업/
│   └─ 06_안전_KOSHA/
└─ research/                      새로 찾은 문서와 가상 데이터 기준 조사
    ├─ INDEX.md                   찾은 문서 목록 (항목 1~8)
    ├─ BENCHMARKS.md              외부 벤치마크 수치
    ├─ PROFILING_REPORT.md        로컬 실제 데이터 분석
    ├─ CRITERIA_SUMMARY.md        위 둘을 합친 가상 데이터 기준표
    ├─ profiling/                 분석 스크립트, CSV, 그림
    └─ (새로 받은 문서 15개)       B2MML, OPC UA, MTConnect, 관리계획서, 불량·정지 코드, 절삭조건 등
```

## 1. 먼저 읽을 문서

| 순서 | 문서 | 내용 |
|---|---|---|
| 1 | [01_생산파트_기능정의.md](01_생산파트_기능정의.md) | 기능 8개, 화면, 데이터, 권한, API, 시연 |
| 2 | [02_AI비서_역할.md](02_AI비서_역할.md) | 브리핑, 알림, 질문 답변, 보고서, 하지 않는 일, 평가 |
| 3 | [research/CRITERIA_SUMMARY.md](research/CRITERIA_SUMMARY.md) | 가상 데이터를 만들 때 유지·조정할 값 |
| 4 | [research/INDEX.md](research/INDEX.md) | 새로 찾은 문서와 못 찾은 문서 |
| 5 | [TEAM_DECISIONS_AND_NEEDS.md](TEAM_DECISIONS_AND_NEEDS.md) | 팀 결정 사항, 더 필요한 것 |

## 2. reference/ — 기존 문서 (생산 파트용)

| 폴더 | 파일 | 쓰임 |
|---|---|---|
| 01_작업지시_데이터모델 | opcua_isa95_jobcontrol_v2.md / .html | 작업지시 상태 구조(Job Order·Job Response) |
| 02_생산지표_KPI | 05_NIST_ISO22400_KPI_paper_2016.pdf, nist_ams200-1.pdf, nist_jres124_004.pdf | 가동률·OEE·MTTR 계산식 |
| 03_품질_검사_공차 | enerpac PPAP 매뉴얼, Ford·Cummins 협력사 요구사항, IATF Ford PPAP, ISO 2768 일반 공차, 구멍 공차·기하공차·표면조도(MISUMI), 6061-T6 자료, NIST 측정 결과(QIF 2개, SPC xlsx) | 검사 기준서, 관리계획서 항목, Cpk 기준 |
| 04_설비_공정별_매뉴얼 | Haas HCS-80(OP-10), Haas NGC 데이터 수집·VF-2 사양·정비 일정, Branson 초음파 세척기(OP-40), Hexagon 측정기 오류 코드(OP-50) | 공정별 설비 문서, 설비 데이터 항목 |
| 05_절삭조건_셋업 | NIST 가공 준비표(xlsx·doc), 가공 프로그램(.NC), YG-1 탭 가공 문제 해결 | 셋업·작업 순서 예시 |
| 06_안전_KOSHA | M-9-2023(절단), M-21-2012(절삭유), P-68-2012(알루미늄 분진), B-M-25-2026(잠금·표지), C-C-67-2026(위험성평가) | OP-10·40 안전, 작업 표준 근거 |

**복사하지 않은 큰 파일** (필요하면 원본 경로로):

| 파일 | 위치 | 크기 |
|---|---|---|
| Haas 밀 조작 매뉴얼 한국어(2015) | `docs/haas/ko_mill_operators_manual_2015.pdf` | 29MB |
| Haas 한국어 매뉴얼 96-KO8210 | `docs/haas/ko_96-KO8210_Mill.pdf` | 93MB |
| Siemens 840D sl 한국어 알람 매뉴얼(OP-20) | `docs/line/siemens_840Dsl_alarms_diagnostics_man_0818_ko-KR.pdf` | — |
| Danfoss 협력사 품질 매뉴얼 | `docs/quality/danfoss_sqm_AH492546005846.pdf` | 9.9MB |
| Haas 알람 목록(한·영) | `docs/haas/haas_alarm_list_20250130_en_ko.csv` | — |

**실제 데이터** (복사하지 않음): `data/4tu`(생산 기록), `data/nist`(설비 상태), `data/other_oee`(정지 기록), `data/haas_ngc_mtconnect`(제어기 항목).
`data/kamp/mirror_chakihwan`은 미시간대 데이터의 사본이라 **쓰지 않는다**.

## 3. research/ — 새로 찾은 문서 (요약)

| 용도 | 파일 |
|---|---|
| 작업지시·실적 필드 | b2mml_v0700_*.xsd 3개, b2mml_v0700_documentation.pdf, opcua_machinery_part3_job_mgmt_7_1.html, mtconnect_partcount_target_v2_6.html |
| 불량·정지 코드 | fabrico_scrap_reason_code_taxonomy.html, teeptrak_downtime_reason_codes.html, scitepress_2020_91758_iso22400_kpi.pdf |
| 관리계획서·셋업시트 | amrep_control_plan_aluminum_bracket.html, autodesk_fusion360_create_setup_sheet.pdf |
| 절삭·세척 조건 | yg1_alu_power_catalog_cutwel.pdf, haas_high_performance_al_speeds_and_feeds.pdf, scl_1999_ultrasonic_aluminum_wax_cleaning_eval.pdf |

## 4. 아직 못 찾은 문서

- 한국어 표준작업서·작업표준서, 절단·세척·3차원 측정 표준작업서 실물
- 한국어 불량 코드표, 4TU·IATF 공식 코드표
- 가공 부품 PFMEA 전체 행 예시, 한국어 관리계획서
- 가공업체 실물 생산일보 (양식 사이트는 유료·로그인)
- 4TU 데이터 컬럼 정의표 (보고유형 D/S/B 뜻은 데이터로 추정만 함)
- Sandvik·Kennametal 6061 수치, 사이클타임·셋업시간 산정 문서
- 자동차 브래킷의 실제 공정흐름도

→ 코드 체계(불량·정지)는 Fabrico, TeepTrak, 4TU를 조합해 **자체 정의**로 만들고 "가상 정의"로 표시한다.

## 5. 이용 시 주의

- Haas, Siemens, Hexagon, 업체 문서 등은 **저작권이 있어서 내부 참고용**이다. 공개 저장소에 올리지 않는다.
- KOSHA 자료는 공공누리 조건(상업 이용 금지 또는 변경 금지)을 따르고 출처를 표시한다.
- 웹 조사 수치는 대부분 검색 요약이므로 발표에 인용하기 전에 원문을 확인한다.
- 저작권 문서를 포함해 로컬에 커밋했다. **원격에는 아직 푸시하지 않았다.** 푸시 전에 저장소 공개 범위를 확인한다.
