# 이상혁 — 품질 + 재고 담당 자료

기획서(`../AUTOMOTIVE_MACHINING_MOM_PLATFORM_PLAN.md`)와 가상 데이터 설계서(`../AUTOMOTIVE_MACHINING_SYNTHETIC_DATA_PLAN.md`)를 기준으로, 품질·재고 기능 구현에 쓸 문서를 모은 폴더입니다.

- 공유용 요약 페이지(자료집): https://claude.ai/artifact/PwwbWF29417Gsxt8tf7MVi
- 작성일: 2026-10-03

## 폴더 구성

| 경로 | 내용 |
|---|---|
| [기능구현계획.md](기능구현계획.md) | 기능별 구현 방법 (데이터, 규칙, API, 화면, 가상 데이터, 일정) |
| [AI비서활용.md](AI비서활용.md) | AI 비서가 품질·재고 기능을 어떻게 쓰는지 (알림, 브리핑, 조회 도구, 답변) |
| `01_기존문서/` | 공유 폴더(`docs/`, `data/`)에 있던 문서 중 쓸 것을 복사 |
| `02_추가문서/` | 이번에 새로 찾은 문서. 기능별 → 근거별로 정리 |
| `02_추가문서/_출처목록/` | 추가 문서마다 원본 URL, 판·날짜, 이용 조건, 확인한 내용, 판정 |

## 담당 기능

| 기능 | 기획서 상태 | 비고 |
|---|---|---|
| **QLT-01** 검사 기록·불량 집계 | 7장 권장, 8장 상세 있음 | |
| **로트 보류** 의심 로트 보류·검사 강화·해제 | 5장·11장·시나리오 S1에만 나옴, **8장 상세 없음** | 기능 정의 필요 |
| **INV-A** 예비 부품·소모품 재고 | 7.1 **제외 기능** | 제외 이유("Haas 부품 번호 문서 미확보")는 해소됨. 팀 합의 필요 |
| **INV-B** 공구 재고 | 없음 (ML-01과 연결) | 팀 합의 필요 |
| **INV-C** 원소재·완제품 로트 | 없음 (로트 보류와 같은 구조) | 팀 합의 필요 |

판정 표시: **적합** 바로 근거로 사용 / **부분(일부)** 표시한 부분만 사용 / **부분(확인)** 출처가 약해 다른 문서와 대조 / **부분(용어)** 원문 없음, 명칭만

---

## 01_기존문서

### QLT-01_검사기록

| 폴더 | 파일 | 쓰는 곳 | 판정 |
|---|---|---|---|
| 1_공차 | misumi_kr_a0189·a0190·a0191 (+hole_table.png) | Ø45 H7 = +25/0 µm (그림 표) | 적합 |
| | emile_maurin_iso_tolerances.pdf | ISO 286 IT7 교차 확인 (프랑스어) | 부분(확인) |
| | enersys_general_tolerances_iso2768.pdf | ISO 2768-m 값. 출처 표기는 KS B ISO 2768-1 권장 | 부분(일부) |
| | misumi_kr_a0194, a0188 | 보통 허용차, 평면도 등 기하공차 정의 | 부분(일부) |
| 2_고객요구사항_CSR | iatf_ford_csr_2026-06.pdf | 양산 Ppk>1.33(p35), **Table A 보류 범위(p36)**, 출하 중지·해제(p18), 특채(p34), 추적성(p26·32), 기록 2년 | 적합 |
| | iatf_ford_ppap_specifics_2026-06.pdf | 승인 Ppk≥1.67·25×5(p16~17), 측정 오차 %Tol(p12), 관리계획 요건(p11) | 적합 |
| | cummins_supplier_handbook_csr.pdf | 1.67/1.33(p17), MSA 10/30%(p14), 격리 24h(p31), PPM(p10) | 적합 |
| | iatf_gm_csr_2025-10.pdf, iatf_stellantis_csr_2025-06.pdf | 출하 전 검사·EPC, 선제 격리 | 적합(범위 제한) |
| | iatf_maqmsr_subtier_2nd_ed.pdf | 하위 협력사 IATF 조항 체크리스트 | 적합 |
| | motherson_hyundai_kia_csr_R02.pdf | 유일한 현대·기아 관련 근거. 셋업 검증, 부적합품 격리 | 적합 |
| | danfoss_sqm_AH492546005846.pdf | MSA ndc(p18), 격리·특채(p22~23), **FIFO·추적 항목(p30)**, PPM(p38) | 부분(일부) |
| | enerpac_supplier_ppap_manual.pdf | MSA 표(p17), **관리계획서 양식 그림(p16)**, Cpk 방식(p21~24) | 부분(일부) |
| | diehl_sqm.pdf, melecs_special_characteristics.pdf | 특성 등급별 Cpk 기준, 부적합품 표시(Diehl p21) | 부분(일부) |
| | smp_greenville_sqm_2018.pdf | 격리 24h, CAR 10일 | 부분(일부) |
| 3_불량집계_지표 | 05_NIST_ISO22400_KPI_paper_2016.pdf | 스크랩률·재작업률·양품률 식(p10). 인용만 | 부분(일부) |
| | Production_Data.csv (4TU) | 불량이 검사 공정에 81%, 불량률 0.64% | 적합 |
| 4_측정데이터_측정기 | FAIR_Box/Plate_Results.qif | 검사 기록 칸 구성. 소재 미확인 → "알루미늄 실측"이라 쓰지 말 것 | 적합 |
| | box_MultiSPC.xlsx | **Cpk/Ppk 계산 코드 정답값** | 적합 |
| | nist_jres124_004.pdf | QIF 데이터셋 출처 | 적합 |
| | hexagon_pcdmis_*.html | 측정기 오류 범주만 가져와 가상 코드로 | 부분(일부) |
| 5_불량원인 | yg1_threading_troubleshooting.pdf | M6 나사 불량 원인 | 부분(일부) |

### 로트보류_추적

| 파일 | 쓰는 곳 | 판정 |
|---|---|---|
| opcua_isa95_jobcontrol_v2.md | 작업지시의 자재 요구·실적(MaterialLotID) | 부분(일부) |
| rightonblackburns_6061T6_extrusions.pdf | 압출 봉 성질(EN 755-2). 판매사 참고 자료 | 부분(일부) |

※ 로트 보류의 핵심 근거(Ford, Danfoss, Diehl, Cummins)는 `QLT-01_검사기록/2_고객요구사항_CSR`에 있습니다.

### INV-A_예비부품

| 폴더 | 파일 | 쓰는 곳 | 판정 |
|---|---|---|---|
| HCS-80_정비 | haas_hcs_5_maintenance.html | HCS-80 부품 P/N 약 50개, 교체 주기 | 적합 |
| VF-2_예방정비일정 | howto_vmc_maintenance_schedule.txt | 예방 정비 주기 → 예정 소요량 (P/N 없음) | 적합 |
| 고장대응안내_교체부품 | tsg_*.txt (53편), tsg_index.csv | 고장 시 교체 부품 P/N → 정비 작업지시서 "필요 부품" | 적합 |

### 복사하지 않고 원래 위치를 쓰는 것 (용량이 큼)

| 파일 | 위치 | 쓰는 곳 |
|---|---|---|
| Haas 밀 조작 매뉴얼 2025 (영어, 22MB) | `../docs/haas/en_mill_ngc_operators_manual_2025.pdf` | INV-B 고급 공구 관리 4.55~4.58절 |
| Haas 밀 조작 매뉴얼 (한국어, 93MB) | `../docs/haas/ko_96-KO8210_Mill.pdf` | INV-B 같은 내용 한국어 |

### 쓰지 않는 기존 문서

| 파일 | 이유 |
|---|---|
| innio_cleanliness_JWN890115.pdf | **"CONFIDENTIAL", 무단 사용 금지.** 가스엔진용, 가공 중 부품 적용 제외 |
| kalmar_cleanliness_326097.pdf | 하역 장비 유압유 청정도. 제품과 무관 |
| misumi_uk_surface_roughness, misumi_sg_a0185 | 텍스트 깨짐 / 한국어판과 중복 |
| ks_probe.html, ncs_probe.html | 검색·약관 화면만 저장됨 |
| ford_csr_via_motherson.pdf | Ford 2026 원본의 구판 발췌본 |

---

## 02_추가문서

원본 URL과 상세 판정은 `_출처목록/`의 4개 파일에 있습니다.

### QLT-01_검사기록

| 폴더 | 파일 | 쓰는 곳 | 판정 |
|---|---|---|---|
| 1_공차_나사 | vermontgage_internal_thread_inspection.html | 통과·정지 게이지 판정 원리 | 적합 |
| | asmc_metric_internal_thread_6H.pdf | M6 6H 유효지름 5.350~5.500, 안지름 4.917~5.153 | 부분(확인) |
| | emuge_tap_drill_wall_chart_6H.pdf | 6H 안지름, M6 탭 드릴 5.0 mm | 부분(일부) |
| 2_Cpk_Ppk_계산 | nist_pmc16.htm | Cp·Cpk 식, 비정규 처리 | 적합 |
| | nist_pmc321.htm, nist_pmc322.htm | σ = R̄/d₂ 상수표, 개별값 관리도(MR̄/1.128) | 적합 |
| | minitab_normal_capability_*.html (3개) | **Cpk = 군내 σ, Ppk = 전체 σ**, σ 추정법 | 적합 |
| 3_판정기준_자동차 | nemak_sqm_2023.pdf | **알루미늄 자동차 부품사.** Ppk 1.67/1.33, 미달 시 100% 검사, 교대당 3개, 격리·MRB | 적합 |
| | hyundai_transys_supplier_registration_HT-Q-I-42-08.pdf | 현대트랜시스 협력사 등록 요건(국문) | 부분(일부) |
| 4_관리도_불량추세 | nist_pmc32.htm | 이상 판정 규칙 6개, 오경보 371점/92점에 1회 | 적합 |
| | nist_pmc332.htm | 불량률(p) 관리도 | 부분(일부) |
| 5_측정조건 | npl_gpg41_cmm_measurement_strategies.pdf | 측정점 수, 평면도·구멍 측정 전략 | 적합 |
| | nist_jres121_iso1_2016_revision.pdf | 기준 온도 20 °C | 적합 |
| | nist_jres112_doiron_20C.pdf, mitutoyo_quick_guide_E11003.pdf | 20 °C 배경, 측정기 허용 오차 | 부분(일부) |
| 6_불량원인_알루미늄가공 | sandvik_milling/boring_troubleshooting_snapshot.txt | 구성인선, 떨림, 버, 보링 치수 원인·대책 | 적합 |
| | iscar_*, harvey_*, yg1_alu_power_endmill_AL6061.pdf | 알루미늄 전용 조건, AL6061 Ra 0.497 µm | 부분(일부) |
| 7_근거_관리계획서 | A_cp_applerubber_sample_control_plan_QF417_2017.pdf | 채운 관리계획서 예시 (O-ring) | 부분(일부) |
| | A_cp_applerubber_quality_control_plan_page.pdf | 필수 10항목 | 부분(일부) |
| | A_cp_SL_TN_America_supplier_PPAP_manual_2018.pdf | 특성 번호·게이지 번호·구체적 빈도 요건(p16~17) | 부분(일부) |
| | A_cp_Nemak_supplier_quality_manual_2019.pdf | 특별 특성 표시, CNC별 SPC(p18~22) | 부분(일부) |
| | A_cp_UK_CIH_CPQP_guideline8_control_plan_2022.pdf | 작성 8단계, 개정 이력 예 | 부분(일부) |
| | A_cp_US_Army_PMSPE_QAForm15_...pdf | 빈 양식 (입찰 사이트 사본) | 부분(확인) |
| 8_근거_불량코드_심각도 | A_def_KR_PPS_quality_special_conditions_5074_2023.pdf | **경·중·치명결함 한국어 공식 정의** (조달청) | 적합 |
| | A_def_Boeing_StLouis_IR0451_defect_descriptions_2020.pdf | 대분류 → 불량명 → 정의 구조 | 부분(일부) |
| | A_def_CurtissWright_QP32-05_...pdf | 버·채터·찍힘 판정 기준. **"Proprietary" → 요약만** | 부분(일부) |
| | A_def_CPI_QA500M_mechanical_workmanship_rev02.pdf | 버·표면·나사 작업 품질 기준 | 부분(일부) |
| | A_def_Kohler_GPI2004_global_SQM_korean_r5.pdf | 특성 분류 한국어 용어. **"내부 및 파트너 사용 전용" → 용어만** | 부분(용어) |
| | (MIL-STD-1916은 `로트보류_추적/1_...`에 있음) | 치명·중·경 정의(3.4, 3.8, 3.10) | 적합 |
| 9_KS표준_용어 | ks_meta_KSQISO22514-1/2/4, KSQISO7870-2, KSBISO1 | 한국어 표준 명칭 | 부분(용어) |
| 선택_세척청정도 | cleancontrolling_iso16232_vda19.html | OP-40 확장 시 | 부분(일부) |

### 로트보류_추적

| 폴더 | 파일 | 쓰는 곳 | 판정 |
|---|---|---|---|
| 1_보류_샘플링_검사강화 | mil_std_1916_1996.pdf (+ notice2 2014) | 합격 판정 개수 0, 일반·강화·완화 전환, 불합격 로트 전수 선별. 공개 표준 | 적합 |
| | nist_pmc2·21·22·23.htm | 샘플링 계획, OC 곡선 | 적합 |
| | heorr_sqam.pdf | 24h 봉쇄, 의심품 인증 라벨 | 부분(일부) |
| | ks_meta_KSQISO2859-1.html | 샘플링 KS 명칭 | 부분(용어) |
| 2_로트구조_추적성 | bosch_supplier_quality_requirements.pdf | 배치 5만 개 이하, 포장당 배치 2개, 1일 내 추적, FIFO | 적합 |
| | opcua_10030_isa95_common_object_model_v1.00.md | 자재 로트 상태·위치·수량·하위 로트 | 적합 |
| | bosch_gtl_guideline_vda4994.pdf | 로트 라벨, Data Matrix 필드 | 적합 |
| | gs1_global_traceability_standard.pdf | 추적 데이터 모델 개념 | 부분(일부) |
| 3_원소재_성적서 | kaiser_6061_rod_bar_datasheet.pdf, aluminum_association_teal_sheet_2018.pdf | 6061 성분 한계, T6 성질 → 원소재 입고 판정 | 적합 |
| | flexmetallic_en10204_inspection_documents.html | 성적서 2.1/2.2/3.1/3.2 비교 | 적합 |
| | penflex_*, acton_* | 3.1 정의 보조 | 부분(일부)/부분(확인) |
| | ks_d_6763_standard_go_kr_meta.html | KS 봉재 표준 명칭 | 부분(용어) |

### INV-A_예비부품

| 폴더 | 파일 | 쓰는 곳 | 판정 |
|---|---|---|---|
| 1_Haas_부품번호 | haas_rd0040_lubricant_grease_sealant_tables_revH_2025-12.txt | 윤활유·그리스 공식 P/N과 용량 | 적합 |
| | haas_catalog_captures_2026-10-03.txt | 정비 키트 08-1976 품목·가격, 필터 93-2185, 공구 P/N | 적합 |
| | haas_hfo_champions_pm_inspection_levels_rev87_2023.pdf | 정비 단계별 교체 항목 | 부분(일부) |
| 2_재고모형_재주문점 | kocw_2011_so08/so09, sogang_ocw_2014_ch11 | ABC, 재주문점 R=μ+zσ (한국어). KOCW 이용 조건 확인 | 적합 |
| | mit_esd260j_2006_lect7/11/12 | EOQ, 안전재고, 서비스 수준 | 적합 |
| | mit_15-772j_2014_lec14 | 예제 | 부분(일부) |
| 3_근거_중요도분류 | B_tue_driessen_spare_parts_framework.pdf | critical / partially / non-critical, 보험용 예비품 | 적합 |
| | B_fme2024_teixeira_spare_policy.pdf | V/E/D × 가격·리드타임 → 정책 A~E | 적합 |
| | B_dodm4140_01_vol02_wayback20260123.pdf | 필수도 코드, 안전재고 상한 min(3σ, LTD) | 적합 |
| | B_emlyon_*, B_ein_* | 긴급도 지수, 평가 기준 가중치 | 부분(일부) |

### INV-B_공구

| 폴더 | 파일 | 쓰는 곳 | 판정 |
|---|---|---|---|
| 1_Haas_공구관리 | B_haas_mill_ngc_om_2023_revT.pdf | 수명 한도 단위 USAGE/HOLES/FEED/LOAD (§4.11.2) | 적합 |
| | B_haas_ATM_operation_2013.pdf | 구형 제어기, 보조 | 부분(일부) |
| 2_근거_공구수명 | B_PMC10056421_cuttingfluid_toollife_Al.xml | Ø10 3날 엔드밀, Al7050, 200분 급마모 진입 | 적합(합금 다름) |
| | B_osgblog_A-SFT-AL_* + B_osg_ASFTAL_CuttingData-01~04.png | M6 탭 알루미늄 500홀 후 정상 | 부분(확인) |
| | B_eares_tap_al6061_M8_HSS.pdf | Al6061 탭 450홀 균일 마모 | 부분(확인) |
| | B_osgblog_VP-SC-NRT_*, B_zenodo_*, B_canadianmetalworking_* | 강재 하한, Al6061 마모 추이, 양산 관행 | 부분 |

---

## 이용 조건 (중요)

- 이 폴더에는 저작권이 있는 문서가 많습니다(Haas, Sandvik, ISCAR, 각 회사 품질 매뉴얼). **팀 내부 참고용으로만 쓰고, 공개 저장소에 원문을 올리지 마세요** (기획서 9.3).
- **`02_추가문서/`는 커밋하지 않습니다 (.gitignore 대상).** 이번에 새로 받은 외부 문서 원문이라, 저장소에 올리지 않고 팀 공유 드라이브 등으로 따로 나눕니다. 저장소에는 README와 md 파일, `_출처목록/`의 출처 정보만 남기고, 필요한 사람은 `_출처목록/`의 원본 URL에서 직접 받습니다. 아직 `.gitignore`에 실제로 추가하지는 않았으니, 커밋 전에 저장소 루트의 `.gitignore`에 아래 두 줄을 넣으세요. 폴더 자체(`02_추가문서/`)를 제외하면 안쪽 예외가 먹지 않으므로 `/*` 형태로 씁니다.

  ```gitignore
  11_automotive/이상혁/02_추가문서/*
  !11_automotive/이상혁/02_추가문서/_출처목록/
  ```
- `01_기존문서/`는 이미 저장소에 있는 `docs/`·`data/` 파일의 복사본이라, 저작권 상황은 원래 저장소와 같습니다.
- 특히 `A_def_CurtissWright_*`("Proprietary"), `A_def_Kohler_*`("내부 및 파트너 사용 전용")는 문장·표를 옮기지 말고 요약만 합니다.
- NIST 자료와 MIL-STD-1916은 공개 자료입니다(출처 표시). MIT OCW는 CC BY-NC-SA, Teixeira 2024·Materials 2023·EUREKA 2021은 CC BY입니다.
- 같은 문서가 두 곳에 있는 경우: MIL-STD-1916(`mil_std_1916_1996.pdf` = `A_def_..._base_1996` 내용 동일, 후자는 복사하지 않음), Nemak(2023판은 판정 기준, 2019판은 관리계획서 근거).
