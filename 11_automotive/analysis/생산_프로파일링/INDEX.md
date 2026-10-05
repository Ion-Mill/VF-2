# 생산 파트 가상데이터 근거문서 보강 INDEX (production_extra)

작성: 2026-10-03. 대상: 6061-T6 브래킷 5공정(OP-10 절단 ~ OP-50 3차원 측정)의 공정 흐름·작업지시·생산실적 가상데이터.
기존 자료(EXPLORATION_REPORT, SYNTHETIC_DATA_PLAN, docs/ 하위, data/4tu)는 먼저 훑었고, 아래는 그 외 '부족한 문서'만 정리했다.

**확인 수준 표기**
- **[읽음]** WebFetch로 페이지/PDF 본문을 받아 내용을 확인함 (WebFetch는 소형 모델 요약을 거치므로 세부 수치는 원문 재확인 권장)
- **[검색요약]** 검색 결과 스니펫/요약만 봄. 본문은 직접 읽지 못함
- **[로컬]** 이미 로컬에 있는 파일을 직접 분석함
- 저장 파일은 같은 폴더(`production/research/`)에 있다. 저작권 문서는 **내부 참고용**이며 재배포 금지.

---

## 0. 요약: 찾은 것 / 못 찾은 것

| 항목 | 결과 | 한 줄 요약 |
|---|---|---|
| 1 공정흐름도·CP·PFMEA 실예시 | **일부** | 알루미늄 브래킷 관리계획서 예시(특성·사양·계측기·샘플링) 1건 확인. 가공품 PFMEA 전체 행 예시는 공개본 못 찾음. AIAG 원본 서식은 유료 |
| 2 SOP/셋업시트 (절단·MC·세척·CMM) | **일부** | 셋업시트: Fusion 360 문서 확보. 절단/세척/CMM 표준작업서 실물 및 한국어 작업표준서 공개본은 **못 찾음** |
| 3 불량 사유 코드/스크랩 코드 | **일부** | 12개 대분류 + 세부코드 분류표(Fabrico) 확인. 4TU/IATF 공식 코드표, 한국 업종별 불량코드표는 **못 찾음** |
| 4 정지 사유 코드 표준 | **찾음** | TeepTrak 표준 코드 17개 + Six Big Losses 매핑 확인. ISO 22400-2 원문은 유료이나 해설 논문 확보 |
| 5 생산실적/작업지시 데이터 모델 | **찾음(핵심)** | B2MML V0700 XSD(OperationsSchedule/Performance) + 문서 PDF 직접 확보, OPC UA Job Response 필드 확인, MTConnect PartCount 하위유형 확인 |
| 6 4TU Production_Data 설명 | **일부** | 원 설명 PDF(MI_-Eng.pdf)는 38쪽 슬라이드로 **컬럼 정의 없음**. D/S/B 의미는 문서에 없어 데이터로 추정(아래 6절) |
| 7 6061 절삭조건·세척조건 | **일부** | Harvey/RobbJack/YG-1/Haas 표 확인. Sandvik/Kennametal 6061 수치는 **못 찾음**(제품 페이지만). 사이클타임·셋업시간 산정 문서 못 찾음. 세척 조건은 40 kHz, 45~60 C 등 복수 출처 |
| 8 한국 중소 생산일보/작업지시서 양식 | **일부** | 양식 사이트 2곳 확인(1곳 로그인/유료, 1곳 무료는 조립 작업지도서). 실제 가공업체 생산일보 파일은 **못 찾음** |

핵심 한계: 한국어 공개 문서(작업표준서, 불량코드, 생산일보)는 실물을 거의 못 찾았다. 가상데이터의 코드 체계는 아래 근거(Fabrico, TeepTrak, 4TU)를 조합해 **프로젝트 자체 정의**로 만드는 것을 권장한다.

---

## 1. 공정흐름도·관리계획서·PFMEA 실제 작성 예시

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 1-1 | Control Plan in Manufacturing: Requirements & Example — https://amrepinspect.com/blog/control-plan-in-manufacturing-requirements-example | AMREP Inspect, 2026-06 | 'Aluminum Suspension Bracket AB-7721-R3' 관리계획서: OP10 선삭/OP20 드릴/OP30 최종검사, 특성 8개(외경 48.00±0.05, Ra≤1.6, 홀위치 TP0.15 등), 계측기, 샘플 크기·빈도, 반응계획 | `process_step`(공정·특성 마스터), `inspection_plan`(특성, 규격, 계측기, 샘플링 빈도), 특수특성(SC/YC) 칼럼 | 무료 | 중(벤더 블로그, 가상 예시) | 읽음 | `amrep_control_plan_aluminum_bracket.html` (저작권 있음, 내부 참고용) |
| 1-2 | PFMEA - CNC machining (Elsmar Cove 스레드) — https://elsmar.com/elsmarqualityforum/threads/pfmea-cnc-machining.87083/ | Elsmar Cove 포럼 | 가공 일반 고장모드 목록(클램핑 변형, 공구마모, 공구파손, 오장착, 지그 이물, 프로그램 무단 변경, 셋업 불량 등). 전체 PFMEA 표는 없음(엑셀 첨부 언급만) | PFMEA 고장모드 → 불량 사유 코드(3절) 후보 도출 | 무료 | 낮음~중(포럼 의견) | 읽음 | 미저장(포럼) |
| 1-3 | Understanding Core Tools: PFMEA and Control Plans (Omnex 과정 안내) — https://opex.omnex.com/webmedia/Documents/download/Automotive-Core-Tools/understanding-core-tools-pfmea-control-plans.pdf | Omnex | 3쪽짜리 교육과정 소개. PFD→PFMEA→CP 연계 목차만 있고 작성 예시는 없음 | 문서 간 연계 구조 설명용(참고 수준) | 무료 | 중 | 읽음(로컬 확인 후 가치 낮아 삭제) | 미저장 |
| 1-4 | AIAG APQP 2nd Ed. / CP 서식 (AIAG 원본) — ANSI 웹스토어 미리보기 | AIAG | 원본 서식은 유료. 미리보기 PDF는 403으로 받지 못함 | CP 헤더/칼럼 표준 | **유료** | 높음 | 검색요약 | 미저장 |
| 1-5 | 한국어 관리계획서/PFMEA 실예시 | — | **못 찾음** (검색 결과는 교육·템플릿 판매 페이지뿐) | — | — | — | — | — |

---

## 2. 표준작업서(SOP)·셋업시트 예시 (절단 / 머시닝센터 / 세척 / 3차원 측정)

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 2-1 | Create a setup sheet (Fusion 360 3-axis) — https://files.upskill-dev.autodesk.com/public/fusion-360-3-axis-machining-professional/2022/pdf/221114_M4-02_Create-setup-sheet.pdf | Autodesk, 2022 | 15쪽. OP별 셋업시트 생성 방법: 공구 목록, 작업좌표(WCS), 예상 가공시간, 프로그램 번호 | OP-30 `setup_sheet`(공구번호, 공구명, 회전수, 이송, 예상시간, 오프셋), `tool_list` | 무료 | 중상(CAD/CAM 벤더 교육자료) | 읽음 | `autodesk_fusion360_create_setup_sheet.pdf` (저작권 있음, 내부 참고용) |
| 2-2 | CNC machine daily pre-op inspection (MangoApps) — https://www.mangoapps.com/templates/inspections/cnc-machine-daily-pre-op-inspection | MangoApps | 가공기 일상점검 체크리스트 템플릿(방호, 절삭유, 윤활, 공구, 오프셋, 워크홀딩) | OP-20/30 시업점검, 초품검사 흐름(셋업→초품→양산→종료) | 무료(템플릿 사용은 가입 필요 가능) | 낮음~중 | 검색요약 | 미저장 |
| 2-3 | Haas Mill Setup Sheets (PDF, tinkerine 미러) | 불명 | 다운로드 실패(응답 없음). 출처 신뢰 불명 | — | — | 낮음 | 검색요약 | 미저장 |
| 2-4 | 기존 확보분 (중복 방지) | — | `docs/haas/`의 Haas 조작/서비스 매뉴얼, `docs/line/`의 Branson 초음파세척기·Hexagon CMM 오류코드 등은 이미 있음 | OP-30/40/50 설비 사양 | — | — | — | — |
| 2-5 | 절단(밴드쏘)·세척·3차원 측정 표준작업서 실물, 한국어 작업표준서 | — | **못 찾음** | — | — | — | — | — |

---

## 3. 가공 불량 사유 코드 / 스크랩·재작업 코드 체계

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 3-1 | Scrap Reason Code Taxonomy — https://www.fabrico.io/blog/scrap-reason-code-taxonomy/ | Fabrico.io, 2026-09 | 대분류 12개: SET, MAT, DIM, SUR, ASM, CON, HND, EQP, MET, TST, CHG, OTH. DIM-01 과대, 02 과소, 03 위치도, 04 형상, 05 나사/탭/보어, 06 누락/중복가공. SET-01~05(초품, 오프셋 보정, 지그 시험, 공구교체 후 재검증, 워밍업). MAT-01~06(오재질, 개재물/기공, 소재 치수 등) | `defect_code`(대분류/세부), `scrap_event.reason_code`. 버, 표면조도는 SUR/DIM 하위로 자체 정의 필요 (공개 표에 버 전용 코드 없음) | 무료 | 중(벤더 블로그, 표준 아님) | 읽음 | `fabrico_scrap_reason_code_taxonomy.html` (내부 참고용) |
| 3-2 | 4TU Production_Data의 불량 관련 칼럼 (로컬) | Dafna Levy, NooL, 2014 | `Qty Rejected`(폐기), `Qty for MRB`(MRB 심의 대기), `Rework`(Y 표시). 사유 코드 칼럼은 **없음** | 불량 수량 분포(공정별 비율) 참고. 사유 분류는 3-1로 보완 | 무료(4TU 이용약관) | 중 | 로컬 | `data/4tu/data/Production_Data.csv` |
| 3-3 | 알루미늄 주조/가공 결함 분류 자료 (검색 결과: AFS, Techniques de l'Ingenieur 등) | 다수 | 기공, 수축, 냉각균열, 플래시 등 주조 결함 중심. 가공 불량 코드표 아님 | MAT-02(기공/개재물) 세부 설명 근거 | 유료/혼합 | 중 | 검색요약 | 미저장 |
| 3-4 | IATF 16949 / 4TU / 한국 업종별 불량코드표 공식본 | — | **못 찾음** (IATF 원문은 유료, 한국어 불량코드표 공개본 없음) | — | — | — | — | — |

---

## 4. 정지(다운타임) 사유 코드 표준

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 4-1 | Downtime Reason Codes: The Standard List — https://teeptrak.com/en/downtime-reason-codes/ | TeepTrak, 2026-08 | 코드 17개: BRK, SET, ADJ, TOOL, NOM, NOP, BLK, MIN, CLN, SPD, QDF, REW, STU, PM, BRK-PL, MTG, NOD. 각 코드에 OEE 요소(가용성/성능/품질/계획)와 Six Big Losses 번호 매핑 | `downtime_event.reason_code`, `reason_master`(oee_factor, six_big_loss, is_planned) | 무료 | 중(벤더, 표준 아님) | 읽음 | `teeptrak_downtime_reason_codes.html` (내부 참고용) |
| 4-2 | Determination of ISO 22400 KPIs using Simulation Models (Kikolski) — https://www.scitepress.org/Papers/2020/91758/91758.pdf | SCITEPRESS, 2020 | ISO 22400-2 KPI(가동률, 효율, 품질비율, 스크랩/재작업 비율)와 시간상태 모델(PBT, AUBT, AUDT) 설명 | KPI 계산식 정의, `shift_summary` 지표 칼럼 | 무료 | 중상(학술 논문) | 일부(PDF 받아 첫 쪽 확인, 본문 정독 안 함) | `scitepress_2020_91758_iso22400_kpi.pdf` (저작권 있음, 내부 참고용) |
| 4-3 | Eliminating the Six Big Losses (ISO 22400-2) — https://teeptrak.com/en/eliminating-six-big-losses-iso-22400/ | TeepTrak | Six Big Losses와 ISO 22400-2 대응 해설 | 4-1 보조 | 무료 | 중 | 검색요약 | 미저장 |
| 4-4 | ISO 22400-2:2014 원문 — https://iteh.es/catalog/standards/iso/8a9efc01-6c74-42a2-ad8f-ec19e84b48f0/iso-22400-2-2014 | ISO, 2014 | 34개 KPI 정의(검색 요약 기준) | 공식 KPI 정의 | **유료** | 높음 | 검색요약 | 미저장 |
| 4-5 | 기존 로컬 OEE 데이터 (중복 방지) | Zenodo | `data/other_oee/`(clay OEE/Downtime, blow molding)에 정지 사유 사례가 이미 있음 | 사유 분포 참고 | 무료 | 중 | 로컬(존재만 확인) | — |
| 4-6 | MESA, IPC-CFX 정지 코드 | — | IPC-2591(CFX)은 SMT 장비용이며 StationStateChanged/Fault 구조가 있으나 가공 라인용 코드표는 없음. 공개 PDF(능력 목록)는 SMT 전용이라 폐기. MESA 정지 코드표는 **못 찾음** | — | — | — | 검색요약 | — |

---

## 5. 생산실적 보고 / 작업지시 데이터 모델 표준

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 5-1 | B2MML V0700 XSD (OperationsSchedule / OperationsPerformance / Types) — https://github.com/MESAInternational/B2MML-BatchML (Schema/) | MESA International, V0700 2020 (ISA-95 2018/19 대응) | 작업지시(Request)/실적(Response) 필드 정의. 직접 확인한 OpSegmentResponse 필드: ID, ActualStartTime, ActualEndTime, OperationsType, ProcessSegmentID, OperationsRequestID, JobResponseID, SegmentState, SegmentData, PersonnelActual, EquipmentActual, PhysicalAssetActual, MaterialActual. OpMaterialActual: MaterialDefinitionID, MaterialLotID, MaterialUse, Quantity, StorageLocation, TestResult 등 | `work_order`(= OperationsRequest), `production_result`(= SegmentResponse: 시작/종료, 상태, 설비/작업자/자재 실적, 수량) 칼럼 설계의 기준 | 무료(로열티 프리, MESA 크레딧 표기) | 높음(표준 구현체) | 읽음(XSD 직접 파싱) | `b2mml_v0700_operationsperformance.xsd`, `b2mml_v0700_operationsperformancetypes.xsd`, `b2mml_v0700_operationsschedule.xsd` |
| 5-2 | B2MML V0700 Documentation — https://github.com/MESAInternational/B2MML-BatchML/blob/master/Documentation/B2MML-Documentation.pdf | MESA, 2020-08 | ISA-95 Part 2 절(예: 6.3 Operations Performance)과 XSD 파일 대응표, 설명 | 5-1 해설 | 무료 | 높음 | 일부(첫 쪽·목차 grep 확인) | `b2mml_v0700_documentation.pdf` (저작권 있음 MESA, 내부 참고용) |
| 5-3 | OPC UA for Machinery Part 3: Job Management 7.1 — https://reference.opcfoundation.org/specs/OPC-40001-3/7.1 | OPC Foundation, v1.0.1 | ISA-95 Job Order/Job Response를 OPC UA로 표현한 사양. (OPC-40570 6.5 페이지에서 확인한 Job Response 필드: JobResponseID, JobOrderID, StartTime, EndTime, JobState, JobResponseData, PersonnelActuals, EquipmentActuals, PhysicalAssetActuals, MaterialActuals) | Job Order/Response 최소 필드 확인 | 무료 | 높음 | 읽음 | `opcua_machinery_part3_job_mgmt_7_1.html` (내부 참고용) |
| 5-4 | MTConnect PartCount (model v2.6) — https://model.mtconnect.org/Version2.6/ObservationInformationModel/ObservationTypes/EventTypes/PartCountTarget | MTConnect Institute | PartCount Event의 하위유형 ALL, GOOD, BAD, COMPLETE, FAILED, ABORTED, REMAINING, TARGET (정수 카운트) | OP-30 설비 카운터 `qty_good/qty_bad/qty_target` 정의 | 무료 | 높음 | 읽음 | `mtconnect_partcount_target_v2_6.html` (내부 참고용) |
| 5-5 | ISA-95 Part 2 / IEC 62264 원문 | ISA/IEC | 공식 필드 정의 | — | **유료** | 높음 | — | 미저장 (5-1이 대체) |
| 5-6 | 실무 MES 작업지시 스키마 (AVEVA MES Web API WO 스키마 등) — https://docs.aveva.com/bundle/mes-web-api-v1/page/topic181.html | AVEVA | 자바스크립트 렌더링이라 본문을 받지 못함 | WO 필드 참고 후보 | 무료(추정) | 중 | 검색요약 | 미저장 |

---

## 6. 4TU 'Production_Data' (Production Analysis with Process Mining Technology)

- 원 데이터: Dafna Levy (NooL), 2014, DOI 10.4121/uuid:68726926-5ac5-4fab-b873-ee76ea412399, 라이선스 4TU General Terms of Use. **[읽음]** (4TU 페이지와 로컬 `article_12697997.json`).
- 로컬 `data/4tu/data/MI_-Eng.pdf`: 38쪽 Disco 데모 슬라이드. 데이터 출처가 "ERP 또는 MES 내보내기"라는 설명과 분석 주제(병목, 고장, 재작업, 불량, 작업자 비교)는 있으나 **칼럼 정의표·단위 설명은 없음**. **[로컬, 텍스트 추출 확인]**
- 슬라이드에서 확인한 사실: 생산 보고에 Breakdown(고장) 분석 장이 있고, 'Analysis of Breakdowns'가 별도로 있음. D/S 외에 고장 보고가 따로 존재함을 시사.

**로컬 CSV 직접 분석 결과** (Production_Data.csv: 4,543행, 작업지시(Case) 225건, 2012-01-02 ~ 2012-03-31)

| 칼럼 | 의미 (데이터로 확인/추정) |
|---|---|
| Case ID | 작업지시 번호 |
| Activity / Resource | 공정(설비)명, 설비명 (`Turning & Milling - Machine 4`) |
| Start/Complete Timestamp, Span | 보고 구간 시작/종료, 소요시간 `HHH:MM` 형식(분 단위 구간, 예: 006:19 = 6시간 19분) |
| Work Order  Qty | 작업지시 수량 (칼럼명에 공백 2개) |
| Part Desc. | 품명 |
| Worker ID | 작업자 ID (익명) |
| Report Type | **D / S / B** (아래) |
| Qty Completed / Qty Rejected / Qty for MRB | 구간 내 완료 / 폐기 / MRB 심의 대기 수량 (개수) |
| Rework | 재작업이면 'Y', 아니면 공란 (Y 32행) |

**Report Type 값 (문서에 정의 없음 → 데이터 기반 추정, 확정 아님)**
- `D`: 3,785행, 완료수량 합계 92,048 → 실제 가공(생산) 보고. 'Done/Data'의 약자로 추정.
- `S`: 705행, 완료수량 합계 471(대부분 0~1) → 셋업(Setup) 보고로 추정. 구간이 길고(예 6시간 19분) 수량이 거의 없음.
- `B`: 53행, 수량 모두 0 → 고장(Breakdown) 보고로 추정(슬라이드의 Breakdown 분석 장과 부합).
- 단위: 수량은 개수, 시간은 Span(HHH:MM)과 타임스탬프(분 단위 정밀도). 금액·무게 단위 없음.

가상데이터 사용처: `production_report`(구간 보고 행) 구조와 보고유형(셋업/생산/고장) 분리 방식의 참고. D/S/B 정의를 문서로 확정하려면 NooL(dafnal@nool.co.il, 슬라이드 연락처)에 문의해야 한다.

| # | 후보 | 내용 | 확인 |
|---|---|---|---|
| 6-1 | https://data.4tu.nl/articles/dataset/Production_Analysis_with_Process_Mining_Technology/12697997 | 데이터셋 메타데이터, 컬럼 정의 없음 | 읽음 |
| 6-2 | 로컬 MI_-Eng.pdf (이미 보유) | 슬라이드, 정의 없음 | 로컬 |
| 6-3 | 이 데이터를 쓴 논문들(RapidProM arXiv 1703.03740, Springer s10489-024-05347-8 등) | 컬럼 의미 설명 여부 미확인 (Springer는 로그인 리디렉션으로 못 읽음) | 검색요약 |

---

## 7. 6061-T6 절삭조건·사이클타임·셋업시간, 세척 조건

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 7-1 | YG-1 ALU-POWER (Cutwel 배포 14쪽 카탈로그) — https://www.cutwel.co.uk/media/product-pdfs/downloads/Alu-Power.pdf | YG-1, 2018(코드 YE-AP18) | 알루미늄용 초경 엔드밀. 시험조건에 AL6061, 7,500 rpm, 이송 1,750~2,500 mm/min, 슬로팅 사례. 알루미늄 합금별 절삭조건표(RPM, FEED, Vc m/min, Fz) | OP-20/30 `cutting_condition`(rpm, feed, Vc, fz), 사이클타임 산정 | 무료 | 높음(제조사 카탈로그) | 읽음(pdftotext로 AL6061 행 확인) | `yg1_alu_power_catalog_cutwel.pdf` (저작권 있음, 내부 참고용) |
| 7-2 | High Performance AL Speeds and Feeds — https://www.haascnc.com/content/dam/haascnc/ecommerce-assets/speeds-and-feeds/High%20Performance%20AL%20Speeds%20and%20Feeds.pdf | Haas Automation | Haas 인덱서블 엔드밀 차트. ISO N 알루미늄(2024, 6061, 60 HB) vc 3,936 sfm, fz 0.012 ipt (이 값은 고성능 인서트 기준이라 일반 초경엔드밀보다 높음) | Haas VF-2 사용 근거, 황삭/정삭 조건 상한 | 무료 | 높음 | 읽음 | `haas_high_performance_al_speeds_and_feeds.pdf` (저작권 있음, 내부 참고용) |
| 7-3 | Harvey Tool General Machining Guidelines — https://www.harveytool.com/resources/general-machining-guidelines | Harvey Tool(Harvey Performance) | 6061 알루미늄 800~1,500 SFM, 칩로드 1/8in .001 ~ 1in .007 | 엔드밀 직경별 이송 계산 | 무료 | 높음 | 읽음 | 미저장(HTML) |
| 7-4 | RobbJack 6061 Aluminum speeds/feeds — https://www.robbjack.com/speeds-and-feeds/6061-aluminum | RobbJack | 1/4in 공구 SFM 3,930, 60,000 rpm 등 고속 조건(소형 고강성 기준 시작값) | 보조 | 무료 | 중상 | 읽음 | 미저장 |
| 7-5 | Haas VF-2 사양 (중고기 판매 목록 기반) | 다수(exapro, surplusrecord 등) | 주축 8,100 rpm, 급속이송 1,000 ipm, 공구교환 약 4.2초, 칩투칩 4.5초, 행정 30x16x20in | `machine_master`, 비절삭시간 | 무료 | 중(2차 출처, 제조사 사양서 직접 확인 필요) | 검색요약 | 미저장 |
| 7-6 | Cleaning Aluminium with an Ultrasonic Cleaner (Kemet 사례) — http://www.kemet.co.uk/blog/cleaning/cleaning-aluminium | Kemet International | 40 kHz(캐비테이션 침식 감소), 45~60 C, 세정 5~10분, 세제 3~5%, 순수 린스 50~55 C 약 2분(무초음파), 열풍건조 60~65 C 5~10분 | OP-40 세척 `wash_recipe`(주파수, 온도, 시간, 농도, 린스, 건조) | 무료 | 중(장비 벤더 사례) | 읽음 | 미저장(HTML) |
| 7-7 | Evaluation Summary SCL #1999 (알루미늄 쿠폰 왁스 세정) — https://cleanersolutions.org/report/download/5412 | Cleaner Solutions DB(TURI), 1999 | 알루미늄 쿠폰, 40 kHz 초음파 상온 5분 세정효율 99.7%, 침지 130 F 10분 65% 등 비교 | 세척 시간/온도 선택 근거(실험 데이터) | 무료 | 중(오래된 현장 실험) | 읽음 | `scl_1999_ultrasonic_aluminum_wax_cleaning_eval.pdf` |
| 7-8 | Goodson 초음파 세척 팁 — https://goodson.com/blogs/goodson-gazette/tech-tips-for-ultrasonic-cleaning | Goodson | 온도 160 F(71 C) 초과 금지, 알루미늄은 출력 50% 권장, 에칭/변색 원인 | 세척 조건 상한 | 무료 | 중 | 읽음(일부) | 미저장 |
| 7-9 | Sandvik Coromant CoroMill 790 / Kennametal HARVI Ultra 8X | Sandvik, Kennametal | 알루미늄(ISO N)용 제품 페이지만 확인. **6061 구체 절삭속도 수치는 못 찾음** | — | 무료(페이지) | — | 검색요약 | 미저장 |
| 7-10 | 밴드쏘 절단 조건 (sawblade.com 속도/이송 차트, 검색 결과) — https://sawblade.com/tech-tips/band-saw-blade-speed-and-feed-chart | 톱날 업체 | 차트 존재만 확인. 수치는 못 읽음. (알루미늄 밴드쏘 300~350 SFM이라는 검색 스니펫) | OP-10 절단 사이클타임 | 무료 | 낮음~중 | 검색요약 | 미저장 |
| 7-11 | 사이클타임·셋업시간 산정 방법 문서, 6061-T6 브래킷 실제 사이클타임 | — | **못 찾음**. 위 절삭조건(rpm, 이송)과 이동량으로 직접 계산해야 함 | — | — | — | — | — |

---

## 8. 한국 중소 가공업체 생산일보 / 작업지시서 양식

| # | 제목 / URL | 발행처·연도 | 내용 | 가상데이터 사용처 | 접근성 | 신뢰도 | 확인 | 저장 파일 |
|---|---|---|---|---|---|---|---|---|
| 8-1 | 생산일지 양식(비즈폼) — https://www.bizforms.co.kr/form_view/form_110214.asp | 비즈폼 | 칼럼: 작업시간, 품명, 규격, 수량, 공정명, 작업자, 품질공정검사, 검사내용, 결과 | `daily_production_report` 칼럼 구성 | **유료/로그인**(미리보기만 무료, 다운로드는 프리미엄 월 9,000원) | 중(일반 서식 사이트) | 읽음 | 미저장(저작권, 유료) |
| 8-2 | 작업지도서 양식 모음(잡가이버) — https://jab-guyver.co.kr/7237 | 잡가이버(블로그) | 무료 xlsx/pdf: 분야별 작업지도서(자동계산: 표준 vs 실적 시간, 합격률, 위험성 요약), 자동차 부품 조립 작업지도서 등. 가공(절삭)용은 아님 | 작업지도서/작업지시서 구분(지도서=방법, 지시서=무엇을 언제 몇 개), 표준시간 vs 실적시간 칼럼 | 무료(로그인 없음) | 낮음~중(개인 블로그) | 읽음 | 미저장(저작권) |
| 8-3 | Design and Implementation of Smart Factory MES Model Based on Process Visualization for SMBs in Korea — https://www.koreascience.kr/article/JAKO201931262479549.pdf | 인터넷방송통신학회 논문지(JIIBC), 2019, 허정석·정종필 | 한국 중소기업 MES 모델 제안(공정 시각화 중심). 한글이 PDF 인코딩 문제로 추출 시 깨져 본문 세부는 못 읽음 | 중소기업 MES 범위·실적 수집 항목 참고 | 무료 | 중(국내 학술지) | 일부(영문 초록만 확인) | `koreascience_JAKO201931262479549.pdf` (저작권 있음, 내부 참고용) |
| 8-4 | 스마트공장 표준·구축 자료(KITECH, 스마트공장 사업관리시스템 www.smart-factory.kr) | 중기부/KITECH | 검색 결과에 링크만 나옴. 서식 내용 미확인 | 후속 조사 후보 | 무료(추정) | — | 검색요약 | 미저장 |
| 8-5 | 실제 가공업체의 생산일보·작업일보 실물 파일 | — | **못 찾음** | — | — | — | — | — |

---

## 저장 파일 목록 (15개, 약 9 MB, 모두 30 MB 이하)

| 파일 | 출처 | 비고 |
|---|---|---|
| `amrep_control_plan_aluminum_bracket.html` | AMREP Inspect | 저작권, 내부 참고용 |
| `autodesk_fusion360_create_setup_sheet.pdf` | Autodesk | 저작권, 내부 참고용 |
| `b2mml_v0700_documentation.pdf` | MESA | 저작권(MESA), 내부 참고용 |
| `b2mml_v0700_operationsperformance.xsd` | MESA | 로열티 프리, MESA 크레딧 표기 |
| `b2mml_v0700_operationsperformancetypes.xsd` | MESA | 〃 |
| `b2mml_v0700_operationsschedule.xsd` | MESA | 〃 |
| `fabrico_scrap_reason_code_taxonomy.html` | Fabrico.io | 저작권, 내부 참고용 |
| `haas_high_performance_al_speeds_and_feeds.pdf` | Haas Automation | 저작권, 내부 참고용 |
| `koreascience_JAKO201931262479549.pdf` | JIIBC 논문 | 저작권, 내부 참고용 |
| `mtconnect_partcount_target_v2_6.html` | MTConnect Institute | 내부 참고용 |
| `opcua_machinery_part3_job_mgmt_7_1.html` | OPC Foundation | 내부 참고용 |
| `scitepress_2020_91758_iso22400_kpi.pdf` | SCITEPRESS | 저작권, 내부 참고용 |
| `scl_1999_ultrasonic_aluminum_wax_cleaning_eval.pdf` | Cleaner Solutions DB | 내부 참고용 |
| `teeptrak_downtime_reason_codes.html` | TeepTrak | 저작권, 내부 참고용 |
| `yg1_alu_power_catalog_cutwel.pdf` | YG-1 / Cutwel | 저작권, 내부 참고용 |

참고: 이 폴더의 `BENCHMARKS.md`, `profiling/`은 이번 조사에서 만든 파일이 아니다.

## 가상데이터 설계 시 권장 매핑 (요약)

| 가상 테이블 | 기준 문서 |
|---|---|
| `work_order`, `production_result` | 5-1 B2MML OperationsSchedule/Performance, 5-3 OPC UA Job Response, 4TU Production_Data(6절) |
| `process_step`, `inspection_plan` | 1-1 관리계획서 예시 |
| `setup_sheet`, `cutting_condition` | 2-1, 7-1, 7-2, 7-3 |
| `defect_code` | 3-1 (버/표면조도는 자체 정의) |
| `downtime_event`, `reason_master` | 4-1, 4-2 |
| `wash_recipe` | 7-6, 7-7 |
| `qty_good/bad/target` | 5-4 MTConnect PartCount |
