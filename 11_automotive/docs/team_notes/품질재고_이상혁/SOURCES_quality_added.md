# QLT-01 보강 자료 목록 (quality_added)

- 접근일: 모든 항목 2026-10-03
- 대상 제품: 6061-T6 알루미늄 바 소재 파워트레인 브래킷 (톱 절단 → 황삭 → Haas VF-2: 포켓, Ø45 H7 보링, M6 탭 → 디버링/초음파 세척 → CMM 전수검사)
- 판정: 적합 = 바로 근거로 사용 가능 / 부분 적합 = 일부 내용만 쓸 수 있거나 출처·범위에 제약 있음
- 공통 약관: 모든 문서는 각 발행처의 저작권을 따릅니다. 내부 학습·설계 참고용으로만 쓰고 재배포하지 않습니다. 단, NIST 자료(미국 정부 저작물)와 MIL-STD-1916(배포 표기 A, 공개 승인)은 예외로 공개 자료입니다.

## 1. Cpk/Ppk 계산, 시그마 추정, 관리도 이상 판정 규칙, 오경보

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| nist_pmc16.htm | https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm | NIST/SEMATECH e-Handbook 6.1.6 (영문) | Cp, Cpk, Cpm 정의와 추정식(hat), Cpu/Cpl, 비정규 분포 처리, 신뢰구간. Ppk는 다루지 않음 | 적합 |
| nist_pmc32.htm | .../pmc/section3/pmc32.htm | NIST 6.3.2 | 변량형 관리도 개요, WECO(Western Electric) 이상 판정 규칙, 3σ 한계의 오경보(평균 371점마다 1회), ARL | 적합 |
| nist_pmc321.htm | .../pmc/section3/pmc321.htm | NIST 6.3.2.1 | X̄-R / X̄-S 관리도, 관리한계 공식(c4, d2 등 상수), ARL 표 | 적합 |
| nist_pmc322.htm | .../pmc/section3/pmc322.htm | NIST 6.3.2.2 | 개별값-이동범위(I-MR) 관리도. MR̄/1.128로 시그마 추정 | 적합 |
| nist_pmc332.htm | .../pmc/section3/pmc332.htm | NIST 6.3.3.2 | p 관리도(불량률). 불량 추이 차트에 활용 | 부분 적합 |
| minitab_normal_capability_potential-capability.html | https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/normal-capability-analysis/methods-and-formulas/potential-capability/ | Minitab 지원 페이지(영문) | 군내(within) σ 기준의 Cp, CPU, CPL, Cpk 공식과 신뢰구간 | 적합 |
| minitab_normal_capability_overall-capability.html | .../methods-and-formulas/overall-capability/ | Minitab | 전체(overall) σ 기준의 Pp, PPU, PPL, Ppk, Cpm 공식. Cpk와 Ppk의 차이를 명시 | 적합 |
| minitab_normal_capability_methods.html | .../methods-and-formulas/methods/ | Minitab | 군내 σ 추정법(합동 표준편차+c4, S̄/c4, R̄/d2, MR̄/d2, 중앙값 MR)과 전체 σ, 편향 보정 상수 | 적합 |

## 2. 로트 판정 샘플링, 보류·재검사

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| nist_pmc2.htm, nist_pmc21.htm, nist_pmc22.htm, nist_pmc23.htm | https://www.itl.nist.gov/div898/handbook/pmc/section2/pmc2.htm (pmc21, 22, 23) | NIST 6.2 | 로트 합격 샘플링의 개념, AQL/LTPD, 생산자·소비자 위험, 단일 샘플링 방식과 OC 곡선 | 적합 |
| mil_std_1916_1996.pdf | https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=120287 (Transient PDF로 받음) | 미 국방부(DoD) MIL-STD-1916, 1996-04-01 기본본, 33쪽, 2014년 재활성 상태 Active. 배포 표기 A(공개) | 합격판정개수 0(accept-on-zero) 계수·계량·연속 샘플링 표, 검증 수준(VL), 일반/강화/완화 전환 규칙, 불합격 로트의 전수 선별(screening)과 원인 조치 | 적합 |
| nemak_sqm_2023.pdf | https://www.nemak.com/media/2636/nemak-supplier-quality-manual_21082023_final-version.pdf | Nemak 공급자 품질 매뉴얼, 2023-08, 30쪽(영문). 알루미늄 자동차 부품 업체 | 초기 Ppk 기준(n=50: 특별특성 1.67, 기타 1.33 / n=30: 2.00, 1.60), 기준 미달 시 100% 검사, 교대당 연속 3개 샘플링, X̄-R 관리도, 셋업 초품·종품 검증, 식별·추적성(태그·로트 번호·바코드·레이저 마킹), 봉쇄·격리구역·MRB, 클린 포인트 | 적합 |
| heorr_sqam.pdf | https://www.heorr.com/wp-content/uploads/2019/05/Supplier-Quality-Assurance-Manual.pdf | Herbert E. Orr Co. SQAM Rev.01, 52쪽 | 부적합 발생 시 24시간 내 봉쇄 계획, 의심품 전수 인증과 "certified" 라벨, 재고 수준별 선별 방법, 용어집 | 부분 적합 |
| ks_meta_KSQISO2859-1.html | https://standard.go.kr/KSCI/standardIntro/getStandardSearchView.do?ksNo=KSQISO2859-1&tmprKsNo=KSQISO2859-1 | 국가기술표준원 e-나라표준인증, 메타데이터만 | KS Q ISO 2859-1(AQL 지표형 계수 샘플링) 한글 표준명, 적용범위, ISO 2859-1:1999 IDT, 최종 확인 2023-12-29. 본문은 없음 | 부분 적합 |

## 3. M6 6H 암나사, 통과·정지 게이지

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| asmc_metric_internal_thread_6H.pdf | https://www.asmc.net/product_images/ASMC_reference_full/metintthread.pdf | ASMC Industrial(체결부품 유통사), 1쪽, 2000년 작성·2021년 수정 | 6H 암나사 표(DIN 13 / ISO 68). M6: 유효지름 D2 5.350–5.500, 내경 D1 4.917–5.153, 정상 체결 길이 3–9 mm | 부분 적합(유통사 자료이므로 값은 ISO 965-2와 교차 확인 권장) |
| emuge_tap_drill_wall_chart_6H.pdf | https://ahbinc.com/get-document?file=AHB+-+Cutting+Tools%2FEmuge+Tap+Drill+Wall+Chart.pdf | EMUGE Corp. 탭 드릴 월차트, 2쪽, 2013. 대리점 AHB 호스팅 | DIN ISO 965-1 기준 6H 내경 한계(M6: 4.917–5.153)와 권장 탭 드릴 5.0 mm. 유효지름은 없음 | 부분 적합 |
| vermontgage_internal_thread_inspection.html | https://vermontgage.com/support/detail/internal-part-thread-inspection-quality-magazine | Vermont Gage(게이지 제조사), Quality Magazine 기고 | 통과(GO) 플러그 = 최소 유효지름의 누적 검사, 정지(NO-GO) = 최대 유효지름 검사, 판정 원리와 한계, ASME B1 인용 | 적합 |

## 4. 알루미늄 가공 품질 문제(버, 구성인선, 채터, 면조도, 보링)

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| sandvik_milling_troubleshooting_snapshot.txt | https://www.sandvik.coromant.com/en-us/knowledge/milling/troubleshooting-milling | Sandvik Coromant. JS로 렌더링되는 페이지라 브라우저에서 텍스트를 발췌한 스냅샷 | 진동, 칩 막힘, 면조도 불량, 구성인선(BUE)·버 발생 시 원인과 대책. 알루미늄 BUE는 vc·fz 증가와 포지티브 형상으로 대응. 런아웃 0.02 mm 미만 | 적합 |
| sandvik_boring_troubleshooting_snapshot.txt | https://www.sandvik.coromant.com/en-us/knowledge/boring/troubleshooting | Sandvik Coromant, 동일 방식 | 황삭·정삭 보링의 칩 처리, 진동, 이송 자국, 마찰 절삭 대책 | 적합 |
| iscar_milling_applications_cutter_basics.pdf | https://www.iscar.com/Catalogs/Publication/english_1/Milling_Applications_and_Cutter_Basics_Guide/Milling_Applications_and_Cutter_Basics_Guide.pdf | ISCAR Reference Guide, 2025-07, 96쪽 | 밀링 진동·채터(46–50쪽), 고면조도 정면밀링(78쪽~), 공구 교체 시점(버 포함, 69쪽) | 부분 적합 |
| iscar_milling_aluminum_intelligently.html | https://www.iscar.com/newarticles.aspx/lang/en/newarticleid/2557 | ISCAR 기술 기사 | 알루미늄 BUE 발생 기전, 칩 포켓 부족에 따른 막힘, Si 함량 영향, 공구 형상·코팅 선택 | 부분 적합 |
| harvey_aluminum_machining_guide.html | https://www.harveyperformance.com/in-the-loupe/aluminum-machining-guide/ | Harvey Performance "In The Loupe" | 알루미늄용 엔드밀 날 수, 헬릭스각, 칩 배출, 가변 헬릭스로 채터 저감, 6061 절삭속도 800–1500 SFM | 부분 적합 |
| yg1_alu_power_endmill_AL6061.pdf | https://yg1.solutions/_include/download.asp?uploadFile=2018090410301737.pdf&uploadFile2=... (YE-AP18) | YG-1(한국 인천), ALU-POWER 브로셔 YE-AP18, 2018, 14쪽(영문 유럽판) | AL6061 시험 조건(Ø10, 7,500 rpm, 1,750–2,500 mm/min)과 Ra 0.497 µm 결과, 알루미늄 권장 절삭조건 표. 트러블슈팅 표는 없음 | 부분 적합 |

## 5. 6061-T6 소재, 밀시트(EN 10204 3.1)

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| kaiser_6061_rod_bar_datasheet.pdf | https://online.kaiseraluminum.com/depot/PublicProductInformation/Document/1025/Kaiser_Aluminum_6061_Rod_and_Bar.pdf | Kaiser Aluminum KA-RBH-6061-8.10, 2쪽 | 6061 봉재 화학성분 한계, T6/T651 대표 기계적 성질(UTS 310 / YS 276 MPa / 연신율 17% / HB 95), 적용 규격(냉간인발 ASTM B211, 압출 ASTM B221, AMS), 물성 | 적합 |
| aluminum_association_teal_sheet_2018.pdf | https://www.aluminum.org/sites/default/files/2021-10/Teal%20Sheet.pdf | The Aluminum Association, 2018-08 개정, 45쪽 | 국제 합금 등록 화학성분 한계(6061 포함, 20쪽)와 밀도. 밀시트 성분 판정의 근거 | 적합 |
| flexmetallic_en10204_inspection_documents.html | https://www.flexmetallic.com/resources/tools/summary-of-inspection-documents | Flexmetallic Industries(영국 개스킷 제조사) | EN 10204 2.1/2.2/3.1/3.2 비교표: 비특정/특정 검사, 발행·확인 주체(제조부서와 독립된 검사원) | 적합 |
| penflex_en10204_type31_bulletin.html | https://www.penflex.com/news/bs-en-10204-2004-products-types-inspection-documents/ | Penflex(제조사) 기술 게시물 | 3.1 정의, 원소재 시험결과를 3.1로 옮겨 적는 것(transfer) 허용 | 부분 적합 |
| ks_d_6763_standard_go_kr_meta.html | https://standard.go.kr/KSCI/standardIntro/getStandardSearchView.do?...ksNo=KSD6763... | 국가기술표준원, 메타데이터만 | KS D 6763 알루미늄 및 알루미늄 합금 봉 및 선. 제정 1978-06-07, 최종 확인 2023-07-12, ISO 209-1 / 6362-2/3/5 MOD, 인용 KS B 0801/0802. 본문(성질 표)은 없음 | 부분 적합 |

## 6. 한국 OEM·KS 관련

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| hyundai_transys_supplier_registration_HT-Q-I-42-08.pdf | https://www.hyundai-transys.com/resources/ko/data/esg/esg_shared_growth/major-4-practices-for-subcontracting02.pdf | 현대트랜시스 HT-Q-I-42-08 개정 14(2024-10-07), 4쪽, 국문 | 협력사 신규등록 평가: 품질경영체제(개발 40, 제조현장 40, 경영 20) 70점 이상, 신청 시 SQ인증서 제출, 품질 5스타 3스타 이상 1차사는 평가 면제 | 부분 적합(등록 절차 문서이며 공정 품질 요구사항은 없음) |
| ks_meta_KSQISO22514-1.html / -2 / -4 | standard.go.kr (ksNo=KSQISO22514-1 / -2 / -4) | 국가기술표준원, 메타데이터 | 공정능력·성능 관련 KS 표준의 한글 명칭(능력과 성능, 시간종속적 공정 모델, 공정능력 추정 및 성능 측정), ISO 22514 IDT, 적용범위 요약 | 부분 적합(한글 용어·인용용) |
| ks_meta_KSQISO7870-2.html | standard.go.kr (ksNo=KSQISO7870-2) | 국가기술표준원 | KS Q ISO 7870-2 "관리도 — 제2부: 슈하트 관리도", ISO 7870-2:2023 IDT, 최종 확인 2026-03-27 | 부분 적합 |

## 7. CMM 측정 조건(20 °C, 오차, 측정 전략)

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| nist_jres112_doiron_20C.pdf | https://nvlpubs.nist.gov/nistpubs/jres/112/1/V112.N01.A01.pdf | NIST J. Res. 112(1), 2007, Doiron, 23쪽 | 치수측정 기준온도 20 °C의 채택 경위(1931 CIPM) | 부분 적합(배경 자료) |
| nist_jres121_iso1_2016_revision.pdf | https://nvlpubs.nist.gov/nistpubs/jres/121/jres.121.026.pdf | NIST J. Res. 121, 2016, 7쪽 | ISO 1:2016 개정 해설: 표준 기준온도 20 °C의 정의, 비표준 온도에서의 규격 처리, 열팽창과 측정의 관계 | 적합 |
| ks_meta_KSBISO1.html | standard.go.kr (ksNo=KSBISO1) | 국가기술표준원 | KS B ISO 1 "GPS — 표준 기준 온도", ISO 1:2022 IDT, 최종 확인 2024-12-27 | 부분 적합 |
| npl_gpg41_cmm_measurement_strategies.pdf | https://eprintspublications.npl.co.uk/2044/1/mgpg41.pdf | NPL(영국 국립물리연구소) Good Practice Guide No.41, 2014-05 개정, 119쪽, ©Queen's Printer | 형상별 최소 측정점 수(BS 7172 발췌), 점 분포, 평면도·원통 측정 전략, 온도·청결·고정 영향 | 적합 |
| mitutoyo_quick_guide_E11003.pdf | https://www2.mitutoyo.co.jp/eng/support/service/catalog/08/E11003.pdf | Mitutoyo Catalog E11003(7), 39쪽(펼침면). 암호화돼 있으나 열람 가능 | 20 °C 열팽창 차이, CMM 구조, ISO 10360 길이측정 오차 MPE, X̄-R 관리도 등 QC 기본 | 부분 적합 |

## 8. 로트 번호, 라벨, 추적성

| 파일 | URL | 발행처 / 판·날짜 | 내용 요약 | 판정 |
|---|---|---|---|---|
| gs1_global_traceability_standard.pdf | https://www.gs1.org/sites/default/files/docs/traceability/GS1_Global_Traceability_Standard_i2.pdf | GS1 Global Traceability Standard R2.0, 2017-08, 58쪽 | 배치/로트 단위 식별(GTIN + 로트), 상위·하위 추적 데이터 모델, SSCC 연계 | 부분 적합(범용·식품 중심이지만 개념은 그대로 적용 가능) |
| bosch_gtl_guideline_vda4994.pdf | https://assets.bosch.com/media/global/bosch_group/purchasing_and_logistics/information_for_business_partners/downloads/logistics_docs/gtl-guideline.pdf | Robert Bosch GmbH GTL 가이드라인 v1.6, 2025, 41쪽 | VDA 4994 / Odette GTL 라벨 배치, Data Matrix 데이터 식별자(1T 배치 등), 단일·혼재·마스터 라벨 | 적합(라벨 설계 참고) |

## 9. 선택 자료: 세척 청정도(OP-40)

| 파일 | URL | 발행처 | 내용 요약 | 판정 |
|---|---|---|---|---|
| cleancontrolling_iso16232_vda19.html | https://www.cleancontrolling.com/en/technical/infothek/test-standards/iso-16232 | CleanControlling GmbH(독일 청정도 시험기관) | ISO 16232:2018과 VDA 19.1의 관계, 추출 방법, 감쇠(decay) 측정 6단계, 초음파 성능 확인(알루미늄 포일) | 부분 적합(선택 자료) |

## 검토했지만 저장하지 않은 자료

| 후보 | 사유 |
|---|---|
| KORLOY 2023 Tools Selection Guide(KR) PDF | 제품 선정 가이드이며 트러블슈팅 표가 없어 부적합(삭제함) |
| 현대자동차 협력사 행동규범 2023 PDF | 윤리·ESG 문서로 품질 요구사항이 없어 부적합 |
| bizlink.or.kr SQ 인증 페이지 | 비공식 포털. SQ 대상 13개 업종(열처리·도금·주단조·사출 등, 기계가공은 명시되지 않음)과 점수 기준(83/70) 정보는 참고만 함 |
| Harvey Tool Troubleshooting Guide 페이지 | JS 렌더링이라 원문 HTML에 표가 없음. 항목(칩 막힘, 거친 면, 버, 채터 등)만 확인 |
| Kennametal 블로그(채터, BUE) | 단일 페이지 앱(SPA)이라 curl로 본문을 받을 수 없음 |
| Haas 09-0449 M6x1.0-6H 게이지, threadcheck.com | HTTP 403 차단 |
| VDA 4994 원문, AIAG B-10, AIAG SPC/MSA, ISO 965-2 원문, KS 원문 | 유료이거나 원문 다운로드가 허용되지 않음 |
