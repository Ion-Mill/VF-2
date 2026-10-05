# DOC-04 예방 정비 기준서

| 항목 | 내용 |
|---|---|
| 문서 번호 | DOC-04 |
| 문서 이름 | 예방 정비 기준서 |
| 개정 | Rev.0 (2026-10-05) |
| 승인 | 공장 관리자 (MGR) |
| 구분 | **가상 사내 문서** (실제 문서를 바탕으로 작성) |
| 제작 기준 | [가상데이터설계서_v3.md 13장](../가상데이터설계서_v3.md#13-가상-사내-문서-제작-기준), 값은 [설계서 5.12·5.14·15.3·15.5](../가상데이터설계서_v3.md#15-가상-기준값-추천과-근거), 용어는 [00_용어집.md](00_용어집.md) |

---

## 1. 목적과 적용 범위

| 항목 | 내용 |
|---|---|
| 목적 | 설비별 예방 정비 항목·주기·방법·쓰는 소모품을 한곳에 정한다. 예방 정비 일정 기능(MNT-04)이 이 문서의 항목으로 달력을 만들고, AI 운영 비서가 "오늘 할 정비"와 "기한 넘긴 정비"를 이 문서로 안내한다 |
| 적용 설비 | OP-30 Haas VF-2 2대 (VF2-01, VF2-02, NGC 제어기, 표준 사양) — 2장 / OP-10 HCS-80, OP-20 머시닝센터, OP-40 세척기·텀블러, OP-50 3차원 측정기 — 3장 (간단히) |
| 적용하지 않는 것 | VF-2에 달려 있지 않은 옵션 장치의 정비 (2장 머리의 제외 규칙), 고장 뒤 수리(사후 정비 → DOC-03) |
| 정비 전 안전 | "잠금·표지 필요 = ○" 항목은 **DOC-05 §2 잠금·표지 절차**를 먼저 한다. 제어반을 열 때는 DOC-05의 고전압 대기 절차도 따른다 |
| 기록 | 실시하면 **MNT-04 실시 기록**에 남긴다 (5장). 쓴 소모품은 재고(INV-01)에서 자동 차감된다 (4장) |
| 목표 | **예방 정비 제때 실시율 90% 이상** [참고: NASA RCM 지침 2008, 12.10.3 "Schedule Compliance — Target = 90 percent or better", PDF 191쪽. 같은 문서 표 12-4 민간 산업 평균 91%, PDF 190쪽] |

**표시 규칙:** [실제] 원문 그대로 / [참고] 다른 모델·회사 자료의 모양만 빌림 / [가상] 팀이 정함 / [선택 필요] 실제 기계를 보고 정해야 함. 항목 이름은 원문을 그대로 옮겼고, "방법 요약"은 팀이 원문에서 필요한 부분만 정리했다.

**잠금·표지 판단 규칙 [가상]:** ① 원문이 전원 끄기·[EMERGENCY STOP]·공기 차단을 요구하거나, ② 손이 움직이는 부위·제어반 안에 들어가거나, ③ 탱크를 비우는 작업이면 ○. 밖에서 보기만 하는 점검은 —.

**누가 하나 [가상]:** 매일·매주 점검과 절삭유 보충은 작업자, ○ 표시 작업과 매월 이상 항목은 보전 담당자.

---

## 2. OP-30 VF-2 예방 정비

**근거:** Haas VMC Maintenance Schedule RD0080 Rev.B (2025-05) [실제] — 이하 "RD0080 n행"은 `RD0080__RevB-2025-05__20261003__body.md`의 줄 번호. 같은 표가 VF/VM 서비스 매뉴얼 18.1(VFVM-SM-18)에도 있다. 원문 끝 주석: "권장 주기는 평균 사용자 기준이며, 여러 교대로 돌리면 더 자주 점검한다" (VFVM-SM-18 226행).

**VF-2 기본 사양에 맞는 항목만 고른 규칙**

| 규칙 | 근거 |
|---|---|
| VF-2 사양표에 없는 장치(옵션)의 항목은 뺀다 | VF-2 사양: 공구 교환장치 Carousel 20개, 주축 Inline Direct-Drive(기어박스는 옵션), 주축 베어링 윤활 Air/Oil Injection, 절삭유 55 gal (208 L) [실제: VF-2 제품 사양 페이지] |
| 옵션 장치 항목은 우리 VF-2(표준 사양)에 없으므로 **제외**하고 일정에 넣지 않는다 (2장 머리의 적용·제외 표에서 항목마다 판단 완료) | 나중에 옵션을 달면 그 항목을 일정에 더한다 [가상: 팀 규칙] |

| RD0080 묶음 (항목 수) | 판단 | 이유 |
|---|---|---|
| Automatic Pallet Changer (7) | 제외 | 팔레트 교환기 없음 |
| Automatic Tool Changer - SMTC (7) | 제외 | VF-2 표준은 Carousel(우산형). 3개월 항목(캠박스 오일)도 SMTC 것이라 함께 빠짐 |
| Automatic Tool Changer - Umbrella (5) | **4개 적용** | Carousel 20개 = 우산형. "Inspect motors and mechanical sensors." 1개 제외 — 현행 우산형 셔틀은 근접 센서, 롤러 스위치는 옛 기종 [실제: VF/VM 서비스 매뉴얼 4.1·4.5] |
| Auxiliary Filter (2) | 제외 | 보조 필터 옵션 |
| Axis Lubrication (4) | **3개 적용** | "zerk fitting이 달린 볼스크류·리니어 가이드" 1개 제외 — 이 기계는 축 윤활유 자동 공급 방식 (LUBE-SM-02) |
| Counterbalance (1) | 제외 | 유압 균형 장치 또는 전기 브레이크 모터 둘 중 하나가 달림 (VFVM-SM-07 416행). VF-2(NGC)는 Z축 브레이크 모터로 본다 [참고: 2005년 서비스 매뉴얼 압력표에 있던 VF-1,2가 2011년 매뉴얼 표(96-0283D 인쇄 10쪽)에서 빠짐, 현행 VF-2 사양표에 균형 장치 없음 — DOC-03 §2.5]. 설치 때 기둥에 균형 장치 탱크가 보이면 매월 항목으로 다시 넣는다 [가상] |
| Electrical Cabinet (1) | **적용** | — |
| Enclosure (3) | **적용** | — |
| Gearbox (3) | 제외 | 기어박스는 옵션 (Max Torque w/opt Gearbox) |
| Minimum Quantity Lubrication (1) | 제외 | MQL 옵션 |
| Oil Skimmer (1) | 제외 | 오일 스키머 옵션 |
| Pneumatics (3) | **적용** | — |
| Probe System (2) | 제외 | OP-30에 공작물 프로브를 쓰지 않음 [가상] |
| Rotary (4) | 제외 | 회전 테이블(4축) 없음 |
| Standard Coolant System (6) | **5개 적용** | "Verify coolant refill is operating correctly" 1개 제외 — 자동 절삭유 보충(Coolant Refill)은 옵션이다 [실제: NGC-ESM-29 29.1 아날로그 센서 표 "...when machine is equipped with the Coolant Refill option", AD0172 "Installation — Refer to the Coolant Refill installation procedure"]. VF-2 사양표에도 없다 |
| Through Spindle Coolant (TSC) (3) | 제외 | TSC 옵션 |
| Spindle (2) / Spindle Lubrication (2) / Tooling (1) | **적용** | 주축 베어링이 Air/Oil Injection 윤활 |

→ 58항목 중 **적용 24개**, 제외 34개.

### 2.1 매일

| 부위 | 항목 | 방법 요약 | 쓰는 소모품 | 잠금·표지 | 근거·원문 |
|---|---|---|---|---|---|
| 외함 | 창(유리) 손상 점검 | 도어 창에 금·깨짐·긁힘이 없는지 본다. 있으면 가공을 멈추고 보전 담당자에게 알린다 | — | — | [실제] RD0080 99행 "Inspect windows for damage." |
| 외함 | 도어 인터록 작동 점검 | 도어를 연 채로 가공이 시작되지 않는지, 알람 230 도어 열림이 뜨는지 확인한다 | — | — | [실제] RD0080 100행 "Inspect the door interlock operation." |
| 교대 시작 | 절삭유 양 확인 | 교대 시작 때 탱크 수위를 본다. 줄었으면 보충한다 (4.2) | CS-COOL (보충 때) | — | [참고] OSHA 절삭유 매뉴얼 7쪽 "Check the sump level at the start of the shift" / Haas 밀 점검표 54행 "Check coolant level" |
| 교대 시작 | 공기 압력 확인 | 제어기의 공기 압력이 운전 범위 안인지 본다. 공장 공기 최소 80 psi (5.5 bar) | — | — | [실제] Haas 밀 점검표 55행, VF-2 사양 "Air Pressure Min 80 psi" |
| 교대 시작 | 공기 배관 물 빼기 | 에어건 방아쇠를 눌러 배관 속 물을 뺀다. 계속 물이 나오면 공장 공기를 점검한다 | — | — | [실제] Haas 밀 점검표 50~52행 |
| 공구 | 공구 홀더·풀 스터드·테이퍼 손상 점검 | 칩을 털어 내고, 녹·긁힘(galling)이 있는 공구는 뺀다 | — | — | [실제] Haas 밀 점검표 62~64행 |
| 교대 끝 | 웨이 커버 칩 청소, 탱크 위 칩 필터 확인 | 웨이 커버 위 칩을 치우고, 절삭유 탱크 위 칩 필터에 쌓인 칩을 덜어 낸다 | — | — | [실제] Haas 밀 점검표 68~69행 |

- "교대 시작·공구·교대 끝" 줄은 RD0080이 아니라 **Haas 밀 주간 정비 점검표**(Mill Weekly Maintenance Checklist, 개정 표기 없음)에서 가져왔다. MNT-04 달력에는 RD0080 2개만 올리고, 나머지는 교대 시작 점검표로 쓴다 [가상].

### 2.2 매주

| 부위 | 항목 | 방법 요약 | 쓰는 소모품 | 잠금·표지 | 근거·원문 |
|---|---|---|---|---|---|
| 공구 교환장치 | 공구 교환장치의 칩 청소 | 보호 덮개 위 칩을 치우고, 공구 빼기 포크·키가 많이 닳거나 상했는지 본다 | — | ○ | [실제] RD0080 61행 "Clean the chips from the tool changer." / 점검표 80~82행 (UMB) |
| 공압 | 주축 공기 조절기 압력 점검 | 윤활 패널의 공기 조절기 게이지 값이 제어기 표시값과 같고, 허용 범위 안인지 본다 | — | — | [실제] RD0080 127행 "Inspect the spindle air regulator pressure." / 점검표 84~86행 |
| 절삭유 | 절삭유 양 점검 | 탱크 수위계(플로트 게이지)가 제대로 움직이고, 표시가 실제 수위와 같은지 본다 | CS-COOL (보충 때) | — | [실제] RD0080 152행 "Inspect the coolant level." / 점검표 88~90행 |
| 절삭유 | 절삭유 농도 점검, 혼합·정비 기록지 작성 | 굴절계로 재고, 원액 제조사 기준 안인지 본다. 값은 실시 기록에 남긴다 (4.2) | CS-COOL (조정 때) | — | [실제] RD0080 153행 "Inspect the coolant concentration. Fill out the Mixture - Maintenance Log sheet." / 점검표 92~94행 |
| 절삭유 | 혼입유 제거, 필터 칩 제거 | 탱크 표면에 뜬 혼입유를 걷어 내고, 절삭유 필터의 칩을 뺀다 | — | — | [실제] Haas 밀 점검표 96~97행 |

### 2.3 매월

| 부위 | 항목 | 방법 요약 | 쓰는 소모품 | 잠금·표지 | 근거·원문 |
|---|---|---|---|---|---|
| 축 윤활 | 윤활유 저장소 양 점검·보충 | 탱크 양을 보고 보충한다. 전원 끄기 → 주 공기 밸브 닫기 → 압력 해제 밸브 링 당기기 → 탱크 빼기 → 나사산 아래 1/2" (13 mm)까지 채우기 → 손으로 조이고 3/4바퀴 더 (4.1) | **CS-WLUB** | ○ (간이 잠금, DOC-05 §2.4) | [실제] RD0080 78행 "Inspect oil reservoir level and refill." / 방법: LUBE-SM-02 119~129행 |
| 전기함 | 벡터 드라이브 환기구·필터 청소 | 환기구와 필터의 먼지를 털어 낸다 | — | ○ | [실제] RD0080 93행 "Clean vector drive air vents / filter." |
| 외함 | 웨이 커버 점검·윤활 | 웨이 커버가 걸림 없이 움직이는지 보고 그리스를 바른다 | **CS-GRS** (Mobil Grease XHP 222) | ○ | [실제] RD0080 101행 "Inspect waycovers and lubricate." / 그리스: RD0040 Specialty Grease |
| 공구 교환장치 | 모터와 근접 센서 점검 | [EMERGENCY STOP] 뒤, 20개짜리 캐러셀의 근접 센서를 닦는다: ① 캐러셀 모터 판의 센서(캐러셀 모터 센서 2개)를 빼서 칩·찌꺼기를 없애고 주변을 깨끗한 천으로 닦는다 ② 캐리지와 슬립 클러치를 분리(캐리지 고정 볼트 풀기)하고 캐리지를 양쪽으로 밀어 셔틀 IN·OUT 센서 2개를 빼서 닦는다 ③ 뺀 순서 반대로 단다. 상태는 [DIAGNOSTIC] → I/O 탭에서 본다. "기계식 센서" 항목은 옛 기종(롤러 스위치)용이라 제외 | — | ○ | 항목 [실제] RD0080 63행 "Inspect motors and proximity sensors." / 센서 종류 [실제] VF/VM 서비스 매뉴얼 4.1 Shuttle Sensors "The shuttle assembly has two proximity sensors", 4.5 Rail Guides and Proximity Sensors "Older machine models use roller switches in place of the proximity sensors" / 방법 [실제] Umbrella TC Mechanical Switches and Proximity Sensors - Maintenance, 20-Pocket Carousel 절. 실제 기계에서 근접 센서인지 한 번 확인 [가상] |
| 공구 교환장치 | 가이드 레일 그리스 주입 | 가이드 레일 = 셔틀 바퀴가 구르는 **위·아래 V 레일**. 먼저 V 레일과 바퀴에 칩이 없는지, 와이퍼가 닳거나 상하지 않았는지 본다 [실제]. 그 뒤 V 레일에 그리스를 **얇게** 바른다 [참고]. 주입 위치(그리스 니플 유무)·양은 원문에서 찾지 못함 → 첫 실시 때 보전 담당자가 정해 기록한다 [가상] | **CS-GRS** | ○ | 항목 [실제] RD0080 64행 "Grease the guide rails." / 레일·점검 [실제] VF/VM 서비스 매뉴얼 4.5 "Check the top and bottom V-rails, and the wheels for chips. Check for damaged or worn wipers." / 그리스 종류·"얇게" [참고] Haas Mill Maintenance Checklist (Monthly) 검색 요약 "Mobil Grease XHP 222 … lightly grease the V-rail guide rails" — 원본 PDF는 지금 Haas 서버에서 404라 원문 대조 못 함 |
| 공구 교환장치 | 공구 빼기 핑거 그리스 주입 | 위와 같음 | **CS-GRS** | ○ | [실제] RD0080 65행 "Grease the extractor fingers." |
| 주축 윤활 | 주축 윤활 탱크 양 점검 | 탱크 양을 보고 부족하면 지정 오일로 채운다 (4.4) | **CS-SLUB** (Mobil 1 0W-20) | — (보기만) / 채울 때 간이 잠금 (DOC-05 §2.4) | [실제] RD0080 177행 "Inspect lubrication tank level." / 오일: RD0040 Spindle Lubricants |
| 주축 | 주축 테이퍼 점검 | [EMERGENCY STOP] 뒤 손전등으로 마모·손상을 보고, 보풀 없는 천으로 닦고 기계유를 얇게 바른다 | — | ○ | [실제] VFVM-SM-18 18.2, 193~197·212행 |

- 시연 S2: VF2-02의 "윤활유 저장소 양 점검·보충"이 기한을 넘긴 상태에서 알람 2075 축 윤활유 저장소 비워짐이 반복된다 [가상, 설계서 7장]. 이 항목이 밀리면 AI 비서가 2075와 함께 안내한다.

### 2.4 3개월

| 부위 | 항목 | 비고 |
|---|---|---|
| — | 해당 없음 | RD0080의 3개월 항목은 "Inspect the oil level in the cambox." (55행) 하나뿐이고 SMTC 전용이라 VF-2 표준에는 없다 |

### 2.5 6개월

| 부위 | 항목 | 방법 요약 | 쓰는 소모품 | 잠금·표지 | 근거·원문 |
|---|---|---|---|---|---|
| 축 윤활 | 호스 갈라짐 점검 | 축 윤활 호스에 금·새는 곳이 없는지 본다 | — | ○ | [실제] RD0080 79행 "Inspect the hoses for cracking." |
| 축 윤활 | 축 윤활 시험 실시 | [DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]. 알람이 없어질 때까지 반복하고, 시험 사이 최소 1분 기다린다 | — | — | [실제] RD0080 80행 "Perform an Axis Lubrication Test." / LUBE-SM-02 137~145행 |
| 공압 | 호스 갈라짐 점검 | 공압 호스에 금·새는 곳이 없는지 본다 | — | ○ | [실제] RD0080 128행 "Inspect the hoses for cracking." |
| 절삭유 | 절삭유 탱크 완전 청소, 절삭유 교체 | 탱크를 비우고 칩·찌꺼기를 치운 뒤 새 절삭유를 채운다 (4.2) | **CS-COOL** | ○ | [실제] RD0080 154행 "Completely clean the coolant tank and replace the coolant." |
| 절삭유 | 표준 절삭유 필터 청소 (+ 교체) | 필터를 청소한다. **청소할 때 새 필터로 바꾼다** [가상] | **CS-CFLT** 1개 | ○ | [실제] RD0080 155행 "Clean the standard coolant filter." / 교체: 설계서 15.3 [가상] |
| 주축 윤활 | 주축 윤활 시험 실시 | 제어기의 주축 윤활 시험을 돌린다 | — | — | [실제] RD0080 178행 "Perform Spindle Lubrication Test." |

### 2.6 1년

| 부위 | 항목 | 방법 요약 | 쓰는 소모품 | 잠금·표지 | 근거·원문 |
|---|---|---|---|---|---|
| 공압 | 공기 퍼지 솔레노이드 청소 | 솔레노이드를 청소한다 | — | ○ | [실제] RD0080 129행 "Clean the Air Purge Solenoid." |
| 주축 | 주축 드로바 힘 측정 | Haas 드로바 힘 측정 절차를 따른다 | — | ○ | [실제] RD0080 171행 "Spindle drawbar force measurement." |
| 공압 | 공기 필터 교체 | 기계 뒤쪽 **공기·윤활 모듈(CALM)** 점검문 안의 **공기/물 분리기(Air/Water Separator)** 필터를 새것으로 바꾼다. 공기를 차단하고 압력을 뺀 뒤 한다(DOC-05 §3) [가상]. 필터를 빼고 나사산에 Sikaflex를 바르고 끼운다(스파크 플러그 플라이어 같은 공구로 풀고 조임). 케이싱·O링·스크린·캡도 닦는다. CS-AFLT = 이 필터(Haas P/N 58-1391 "Muffler Poly 100 Micron NPT-3/8M") | **CS-AFLT** 1개 | ○ | 위치 [실제] Mill 운영자 매뉴얼 96-8210 Rev V F2.5 "D Consolidated Air-Lubrication Module (CALM)" (PDF 60쪽), F2.9 Detail D "5. Air/Water Separator" (PDF 63쪽, 일반 수직 밀 그림) / 방법·부품번호 [실제] Tool Release Piston TSG "Water Separator Filter" 절 (원문은 공압 고장 때 점검·교체하는 절차) / 주기 [참고] Haas HCS-80 정비 일정 "Replace air-filter — Yearly" (다른 Haas 기계). RD0080에는 교체 주기가 없다 (설계서 15.3) |

### 2.7 필요할 때

| 부위 | 항목 | 언제 | 쓰는 소모품 | 잠금·표지 | 근거·원문 |
|---|---|---|---|---|---|
| 절삭유 | 필터 스크린 청소 | 칩이 쌓여 흐름이 나빠질 때 | — | ○ | [실제] RD0080 151행 "Clean the filter screen." — As Required |
| 주축 | 주축 테이퍼 청소·윤활 | 2.3 매월 점검 외에 더러워졌을 때, 오래 세워 둘 때 (공구를 빼고 방청제로 닦음, 점검표 70~72행) | — | ○ | [실제] RD0080 170행 "Clean and lubricate the spindle taper." |
| 공구 | 풀 스터드 그리스 바르기 | 공구 홀더를 점검할 때 | **CS-GRS** | — | [실제] RD0080 184행 "Grease Pull Studs." |

---

## 3. 다른 공정 예방 정비 (간단히)

공정당 1~2항목만 MNT-04 달력에 올린다 (기획서 MNT-04 표).

### 3.1 OP-10 HCS-80 (SAW-01)

| 항목 | 주기 | 방법 요약 | 잠금·표지 | MNT-04 등록 | 근거 |
|---|---|---|---|---|---|
| 절단 구역 칩·찌꺼기 청소 | 매일 | 절단 구역의 칩을 치운다 | ○ | ○ (톱날 점검과 한 항목) | [실제] HCS-80 5.1 "Clean the cutting area of chips and debris — Daily" |
| 톱날 상태 점검 | 매일 | 톱날 이 빠짐·마모를 본다. 톱날을 만질 때는 베임 방지 장갑 | ○ | ○ | [실제] HCS-80 5.1 "Check blade condition — Daily", 5.2 Caution |
| 가이드 레일 윤활유 레벨 점검·보충 | **매주** | 윤활 캐비닛 안 윤활유 탱크 양을 보고 채운다 (Mobil Way Oil 68 Vactra No. 2, Haas 93-5656). 캐비닛을 열고 채울 때는 [EMERGENCY STOP] → 전원 끄기 → SAW-01-E1 자물쇠 + 표지 → 기동 안 됨 확인 → 보충 → 해제 뒤 경보 5303이 꺼졌는지 본다. 캐비닛을 열지 않고 레벨만 볼 때는 잠금 없음 | ○ (보충 때, **1점 잠금 SAW-01-E1**, DOC-05 §2.4) | ○ | 주기 [참고]: HCS-80 일정에 이 항목은 없고, 같은 표의 기름 레벨 점검이 매주. 경보 5303.00 가이드 레일 윤활유 레벨 낮음이 있어 둠 (설계서 15.3) / 오일 [실제] HCS-80 5.1 "Lubricating Oil 93-5656 Mobil Way Oil 68 Vactra No. 2" / 잠금 [가상] 근거는 DOC-05 §2.4 (HCS-80 2.1 "Motion is possible when the power is on and the machine is not in [EMERGENCY STOP]" [실제], 다른 기종 AD0630 "Power off the machine." [참고]) |
| 기어박스 오일 / 유압유 레벨 점검 | 매주 | 레벨 표시를 본다 | — | — | [실제] HCS-80 5.1 "Inspect the gearbox oil level / hydraulic oil level — Weekly" |
| 앞 바이스 리니어 가이드 그리스 주입 | **매월** | 기계 앞쪽 그리스 니플(zerk)로 Mobilgrease XHP 222(Haas 99-1686, CS-GRS)를 넣는다. 공용 그리스건 사용 | ○ (SAW-01-E1 1점, DOC-05 §2.4와 같게) | ○ | 방법·그리스 [실제] HCS-80 5.1 "Grease the linear guides of the front vise through the zerk fittings (3) in the front of the machine", 윤활유 표 "Grease 99-1686 Mobilgrease XHP 222". 주기는 원문에 없어 [참고]: 같은 Haas의 VF-2 공구 교환장치 가이드 레일 그리스 주입 주기(매월, RD0080 64행, 이 문서 2.3)를 빌림 |
| 공기 필터 교체, 유압유·기어 오일 교체 | 1년 | — | ○ | — | [실제] HCS-80 5.1 "Replace air-filter", "Replace hydraulic oil and gearbox oil — Yearly" |

### 3.2 OP-20 머시닝센터 (MIL-01)

| 항목 | 주기 | 방법 요약 | 잠금·표지 | 근거 |
|---|---|---|---|---|
| 윤활 레벨·습동면 점검 | 매일 | 윤활유 레벨과 습동면에 윤활유가 고르게 있는지 본다 | — | [가상] 기계 제조사를 정하지 않아 근거 문서 없음 (설계서 15.3) |

### 3.3 OP-40 세척기·텀블러 (WSH-01)

| 항목 | 주기 | 방법 요약 | 잠금·표지 | 근거 |
|---|---|---|---|---|
| 텀블러 베어링 그리스 주입 | **8시간 사용마다** | 장비를 끄고(DOC-05 §2.4 1점 잠금), 뒤쪽 구멍으로 베어링 그리스 니플마다 그리스건을 **1번 누른다** (약 1.5 cm³). 그리스는 **CS-GRS (Mobil Grease XHP 222, 리튬 복합·EP·NLGI 2)** 를 쓰고 다른 그리스와 섞지 않는다. 위 덮개는 열지 않는다(회전 추 위험) (4.5) | ○ | 주기 [참고] 진동 바렐 KVF3 매뉴얼 3쪽 "LUBRICATE AFTER EVERY 8 HOURS OF USE WITH GREASE" (다른 모델, 종류 없음) / 그리스 종류 [참고] FAG TPI 197 인쇄 34쪽 "lithium soap greases with EP … penetration class 2" / 양 [참고·가상] 4.5 |
| 세척액 상태 점검 | 매일 | 액 속에 고형 찌꺼기가 보이거나 색이 변했으면 빼고 새로 채운다 | ○ (뺄 때) | [참고] Kerry MKC 매뉴얼 20쪽 4.2.2 "Daily: Check condition of the cleaning fluid" (다른 모델) |
| (참고) 세척액 수위 | 자주 | 운전 수위 아래로 3/8 inch (1 cm) 넘게 내려가지 않게 채운다. 액을 바꿀 때 탱크 오염을 보고 부드러운 천과 물로 닦는다 | ○ (뺄 때) | [참고] Bransonic 매뉴얼 PDF 14쪽 주의, 7.1 표 7.1 Tanks (PDF 68쪽) |

### 3.4 OP-50 3차원 측정기 (CMM-01)

| 항목 | 주기 | 방법 요약 | 잠금·표지 | 근거 |
|---|---|---|---|---|
| 측정기 중간 점검 (기준물 측정) | **매주** [가상] | 기준물(링 게이지 등)과 스타일러스 끝을 먼지 없이 닦고, 평소 측정과 같은 방법·속도로 기준물을 잰다. 결과가 측정기 사양 안인지 본다. 충돌·큰 온도 변화 뒤에는 바로 한 번 더 | — | 주기 [가상]: NPL GPG 42는 "주기는 필요한 성능·환경·사용량에 따라 사용자가 정한다"고만 함 (PDF 60쪽). 방법 [참고]: NPL GPG 42 9장 (PDF 60·66·69쪽) |

---

## 4. 소모품 보충·교체와 재고 차감

품목 번호는 [가상]이다 (Haas 부품 번호를 쓰지 않음, 설계서 5.14). 차감 규칙은 기획서 INV-01을 따른다.

| 품목 번호 | 품목 | 언제 쓰나 | 차감량 | 안전 재고 [가상] | 근거 |
|---|---|---|---|---|---|
| CS-WLUB | 축 윤활유 | 2.3 매월 점검·보충 | 실제로 부은 양 (L) | 4 L | 주기 [실제: RD0080 78행], 소비량 [가상] |
| CS-COOL | 절삭유 원액 | 교대 시작 보충, 2.2 농도 조정, 2.5 탱크 교체 | 보충량 × 보충 농도 (아래 4.2) | 20 L | 4.2 |
| CS-CFLT | 절삭유 필터 | 2.5 6개월 필터 청소 때 교체 | 1개 | 2개 | 청소 [실제: RD0080 155행], 교체 [가상] |
| CS-AFLT | 공기 필터 | 2.6 1년 교체 | 1개 | 2개 | [참고: HCS-80 5.1] |
| CS-SLUB | 주축 윤활유 (Mobil 1 0W-20) | 2.3 매월 탱크 양 점검 때 보충 | 실제로 부은 양 (L) | 4 L (1통) | 4.4 |
| CS-GRS | 그리스 (Mobil Grease XHP 222, 14 oz 카트리지) | 2.3 웨이 커버·가이드 레일·핑거, 2.7 풀 스터드, 3.3 OP-40 텀블러 베어링 (8시간마다) | **새 카트리지를 그리스건에 끼울 때 1개** | **2개** | 4.5 |

- 그리스와 주축 윤활유는 2026-10-05에 재고 품목으로 넣었다 (설계서 5.14·15.5와 같음). 떨어지면 매월 정비를 못 하거나(그리스), 알람 805 주축 윤활 부족·주축 과열로 이어지기 때문이다(주축 윤활유, 4.4) [가상 판단, 근거는 4.4·4.5].
- 세척액(OP-40)과 다른 공정의 윤활유(HCS-80 가이드 레일 오일 등)는 **재고 품목이 아니다.** 실시 기록에만 남긴다. 이유는 4.6.

### 4.1 축 윤활유 (CS-WLUB)

| 항목 | 값 | 근거 |
|---|---|---|
| 탱크 용량 | 약 32 oz (약 0.95 L) | [실제] RD0040 Rev.H "Haas Axis Lubrication Oil — Approximately 32 oz (58 cu-in or 0.95 L)" |
| 보충 단위 | 1 gallon (약 3.78 L) 통 | [실제] LUBE-SM-02 111행 "AXIS LUBE OIL REFILL 1 GALLON" |
| 채우는 높이 | 탱크 나사산 아래 1/2" (13 mm) | [실제] LUBE-SM-02 127행 |
| 한 통이 가는 기간 | 하루 8시간·주 5일 기준 약 10개월~1년 | [실제] LUBE-SM-02 81행 |
| 점검·보충 | 매월 (2.3) | [실제] RD0080 78행 |
| 보충을 빠뜨리면 | 알람 2075 축 윤활유 저장소 비워짐 → 그대로 두면 2073 축 윤활 압력이 감지 불능 | DOC-02 §4, 설계서 7장 S2 |

### 4.2 절삭유 (CS-COOL)

| 단계 | 규칙 | 근거 |
|---|---|---|
| ① 교대 시작 | 탱크 수위를 확인한다 | [참고] OSHA 절삭유 매뉴얼 7쪽 "Check the sump level at the start of the shift" |
| ② 줄었으면 보충 | 매일 또는 수위가 10% 줄면 보충한다. 30% 넘게 낮으면 보충 전에 농도부터 잰다 | [참고] MSC 2023 4쪽 "Top off ... daily or whenever the coolant level drops by 10%" / OSHA 7쪽 "30% below the full mark ... Check the concentration!" |
| ③ 보충 농도 | **약 3%** (알루미늄은 칩에 묻어 나가는 양이 많음). 원액 차감량 = 보충량 × 0.03 | [참고] MSC 2023 4쪽 "aluminum ... add a 3% concentration" |
| ④ 농도 측정 | **매주** 굴절계로 잰다. **농도 = 굴절계 값 × 1.4** (TRIM SC538의 굴절계 계수) | 주기 [실제] RD0080 153행 / 식·계수 [실제] TRIM SC538 제품 자료(한국어) 2쪽 "% 농도 = 굴절률 판독값 x 굴절인수", "냉각수 굴절측정계 인수 % 브릭스 = 1.4" |
| ⑤ 작업 농도 | **목표 7.0% (굴절계 약 5.0)**, 관리 범위 **6.5~8.5% (굴절계 약 4.6~6.1)**. 범위를 벗어나면 원액이나 물을 더해 맞추고 실시 기록에 남긴다 | 범위 [실제] SC538 2쪽 "일반절삭가공 (Moderate duty) 6.5% - 8.5%", 목표 [실제] 같은 쪽 "7% 이상에서 작동 시 최상의 탱크 수명 및 부식 방지 제공" / 제조사 기준을 따르라는 규칙 [실제] Haas 밀 점검표 56~58행. 일반절삭을 고른 이유 [가상]: 엔드밀·드릴·M6 탭을 함께 하는 OP-30 작업. Haas 구형 매뉴얼의 6~7%(2005 서비스 매뉴얼)와도 겹친다 |
| ⑥ 6개월 교체 | 탱크를 완전히 청소하고 새로 채운다. 원액 차감량 = 208 L × 7.0% ≈ **14.6 L** | 주기 [실제] RD0080 154행 / 탱크 55 gal (208 L) [실제: VF-2 사양] / 7.0% = ⑤ 목표 |
| ⑦ 섞는 법 | 물에 원액을 넣는다 (반대로 하지 않는다). 보충도 원액이 아니라 **섞은 액**으로 한다. 미네랄이 없는 물을 쓴다 | [실제] SC538 3쪽 혼합방법 "반드시 용수에 추천량의 원액을 투입하시고 (절대로 반대로 투입하면 안됨)", "보충유를 투입할 때는 반드시 희석액을 투입" |

**원액 제품: TRIM SC538 (Master Fluid Solutions, 반합성 수용성)** — 2026-10-05 결정

| 항목 | 값 | 근거 |
|---|---|---|
| 고른 이유 | 알루미늄용 반합성, 자동차 산업 적용, 한국 사이트에 한국어 제품 자료가 있음 | [실제] SC538 1쪽 "탁월한 알루미늄 가공성 제공", 적용 범위 "가공방법 — 드릴링, 밀링…", "산업 — 다이캐스트, 일반 제작, 자동차…" / Haas는 수용성(soluble oil) 또는 반합성을 쓰고 제조사 권장 농도로 섞으라고 함 [실제: Haas TSC-300/1K 고장 안내 "Always use a soluble oil or a semi-synthetic coolant, mixed to the manufacturer's recommended concentration."] |
| 권장 농도 | 경절삭 4.0~6.5% / 일반절삭 6.5~8.5% / 중절삭 8.5~10.0% / 사용 가능 4.0~10.0% | [실제] SC538 2쪽 "가공별 추천농도" |
| 굴절계 계수 | 1.4 | [실제] SC538 2쪽 |
| 원액 pH (희석액) | 9.4~10.4 | [실제] SC538 2쪽 물리화학적 특성 |
| 포장 단위 | 20 L, 204 L 드럼 | [실제] SC538 3쪽 "포장 단위 20리터 토트, 204리터 드럼" |
| 이전 [참고] 제품 TRIM SC520을 쓰지 않은 이유 | SC520도 알루미늄용 반합성이지만 **한국 사이트에 제품 자료가 없다** ("Data Sheet Not Available", 2026-10-05 확인). 포장도 갤런 단위 | [실제] SC520 제품 자료(북미) 3쪽 포장 1-gallon·5-gallon |
| 안전보건자료(SDS) | **SC538 공개 SDS 없음 (2026-10-05 다시 확인).** 한국·아시아태평양·베트남·중국 사이트의 SC538 "안전 보건 정보" 쪽에 SDS 파일이 없고 "공급사·공식 대리점에서 받으라"는 문장만 있다. 대리점·MSC·SDS 모음 사이트·Wayback에서도 SC538 SDS는 찾지 못했다. **규칙: SC538 실제 SDS(한국어 물질안전보건자료)는 구매 때 받아 바꾼다. 그 전에는 [참고] 같은 회사·같은 계열(알루미늄용 반합성) TRIM SC520 SDS 기준으로 한다 [가상: 팀 규칙].** SC520 SDS 요약 [참고]: GHS 피부 자극 구분 2, 눈 자극 구분 2A, 신호어 "Warning", "Causes skin irritation. Causes serious eye irritation." (1쪽) / 보호구 예방 문구 "Wear eye protection/face protection. Wear protective gloves." (1쪽) / 권장 보호구 눈 "Safety glasses.", 손 "Wear appropriate chemical resistant gloves.", 호흡 "In case of insufficient ventilation, wear suitable respiratory equipment." (3쪽) / 노출 기준 정제 광유 미스트 OSHA PEL 5 mg/m3, ACGIH TWA 5 mg/m3(흡입성) (2~3쪽). 원액(SDS 본문)과 희석액 구분은 pH만 있다(원액 10.2~10.6, 희석액 "pH in aqueous solution 9.6 - 10", 3~4쪽). 응급 조치와 보호구 적용은 DOC-05 §6.5에 적었고, DOC-05 §5 보호구와 다르면 더 엄격한 쪽을 쓴다 | [참고] Master Chemical "SAFETY DATA SHEET TRIM® SC520" (SDS US, Version 02, Revision date 07-30-2015) 1~4쪽 / [실제] SC538 안전 보건 정보 쪽(한국어) "보건안전 관련 자세한 정보는 SDS 자료를 참조하십시오. SDS는 Master Fluid Solutions나 공식대리점을 통해 확인하실 수 있습니다." / (영어, 아시아태평양) "For further information, see the most recent SDS which is available directly from Master Fluid Solutions." |

- 하루 손실은 약 10%로 본다 [참고: CTE 1997 "증발 하루 3~10%, 튐·미스트·끌려 나감까지 하루 5~20%"]. 2대 탱크 416 L × 10% × 3% ≈ 하루 원액 1.25 L (설계서 15.5).
- 보충 농도 3%(③)는 작업 농도(7%)보다 낮다. 물은 증발로만 줄고 원액은 칩에 묻어 나가는 만큼만 줄기 때문이다. SC538 자료도 "수분증발률과 가공 시 묻어나가는 절삭유의 비율을 고려"하라고만 하고 숫자는 주지 않는다 [실제: SC538 3쪽]. 매주 ④에서 잰 값이 범위 아래로 계속 내려가면 보충 농도를 올린다 [가상].

### 4.3 필터

| 필터 | 청소 | 교체 | 근거 |
|---|---|---|---|
| 표준 절삭유 필터 (CS-CFLT) | 6개월 | 6개월 청소 때 교체 | 청소 [실제] RD0080 155행 / 교체 [가상] (Haas 자료에 교체 주기 없음) |
| 절삭유 필터 스크린 | 필요할 때, 매주 칩 제거 | — | [실제] RD0080 151행, 점검표 97행 |
| 벡터 드라이브 필터 | 매월 | — (청소만) | [실제] RD0080 93행 |
| 공기 필터 (CS-AFLT) | — | 1년 | [참고] HCS-80 5.1 "Replace air-filter — Yearly" |

### 4.4 주축 윤활유 (CS-SLUB)

| 항목 | 값 | 근거 |
|---|---|---|
| 오일 | Mobil 1 0W-20 (대체: Mobil 1 5W-20) | [실제] RD0040 Rev.H Spindle Lubricants "Mill — Mobil 1, 0W-20 / Mobil 1, 5W-20" |
| 표의 용량·판매 단위 | 128 oz (3.79 L) | [실제] RD0040 Spindle Lubricants "128 oz (3.79 L)" |
| 윤활 방식 | 공기·오일 분사 (Air / Oil Injection) | [실제] VF-2 사양 "Bearing Lubrication — Air / Oil Injection" |
| 점검·보충 | 매월 탱크 양 점검 (2.3), 6개월 주축 윤활 시험 (2.5) | [실제] RD0080 177·178행 |
| 하루 사용량 | 약 0.02 L (2대) = 0.6 cc/시간 × 16시간 × 2대 | 0.6 cc/시간 [참고] Plant Services 2002 (Mitchell) "set the oil output to 0.03 cc every three minutes. This results in a total consumption of 0.6 cc per hr." — 다른 회사의 공기·오일 윤활 값. Haas 자료에는 소비량이 없다. 하루 16시간 [가상: 설계서 5.2 교대 2개] |
| 한 통이 가는 기간 | 약 7개월 (3.79 L ÷ 0.02 L/일 ÷ 26일) | 위 값으로 계산 [참고] |
| 떨어지면 | 알람 805 LOW SPINDLE LUBRICATION, 주축 과열·소음·고장 | [실제] Haas TG0135 Rev.A Symptom Table "Alarm 805 LOW SPINDLE LUBRICATION — The reservoir oil level is low. Refill the reservoir." |
| 자료끼리 다른 점과 결정 | Haas 자료 셋이 다르게 적는다: ① TG0135 Rev A (2025-06, 갱신 2025-10-15) "Refill the oil reservoir with Mobil SHC 625. If Mobil SHC 625 is not available, use Mobil 1 5W-20 or Mobil 1 10W-30." ② 40T 주축 TSG TG0101 Rev B (2025-11) "use the correct spindle lubrication (SHC 625)" ③ RD0040 **Rev H (2025-12)** Spindle Lubricants "Mill — Mobil 1, 0W-20 / 대체 Mobil 1, 5W-20, 93-4203". **결정: 가장 최근 판이고 Haas 윤활유 기준표인 RD0040 Rev H를 따라 CS-SLUB = Mobil 1 0W-20** [가상: 팀 결정 규칙 "날짜가 늦은 기준표 우선"]. Mobil 1 5W-20은 ①·③ 둘 다 허용하므로 0W-20을 못 구할 때 쓴다. 이미 SHC 625가 들어 있는 기계면 바꾸기 전에 탱크를 비우고, 다른 오일을 섞지 않는다 [가상]. 탱크 표시(라벨)가 다르면 라벨을 따른다 [가상] | [실제] TG0135 Oil Level (`docs/haas/web_snapshots/tsg_spindle_minimum_lubrication.txt`) / [실제] VFVM-SM-09 9.3 TG0101 Lubrication 549행 / [실제] RD0040 Rev H |

### 4.5 그리스 (CS-GRS)

| 항목 | 값 | 근거 |
|---|---|---|
| 그리스 | Mobil Grease XHP 222 (NLGI 2) | [실제] RD0040 Specialty Grease "Mobil Grease XHP 222 — This helps the way covers move more easily across the casting. 99-1686", Mobil Grease 특성표 "XHP 222 — NLGI 2" |
| 단위 | 카트리지 1개 = 14 oz (0.41 L) | [실제] RD0040 Linear Guide/Ball Screw 표에서 같은 부품 번호 99-1686에 "14 oz (0.41 L)" |
| 쓰는 곳 (VF-2 2대) | 매월: 웨이 커버, 공구 교환장치 가이드 레일, 공구 빼기 핑거 / 필요할 때: 풀 스터드 | [실제] RD0080 101·64·65·184행 |
| 차감 | 1회 주입량이 원문에 없어 g 단위로 빼지 않는다. **새 카트리지를 그리스건에 끼울 때 1개** 뺀다 | 주입량: RD0080·VFVM-SM-18에 없음 / 차감 방식 [가상] |
| 안전 재고 | **2개** = 그리스건에 끼워 둔 수 1 (NCS 식의 "장비 부착 수") + 하루 사용량 × 3일 (6 cm³ × 3 = 18 cm³ ≈ 카트리지 0.04개) = 1.04 → 올림 | 식 [실제: NCS 치공구관리 90쪽] / 그리스건 1개 공용 (VF-2·텀블러) [가상] / 올림은 설계서 15.5 M6 탭(7.4 → 8)과 같은 규칙 |
| OP-40 텀블러 — 종류 | **CS-GRS와 같은 그리스로 정함** [가상]. KVF3 매뉴얼에는 "WITH GREASE"뿐이라 종류가 없다. 진동 기계 베어링에는 EP 첨가 리튬 비누 그리스, 주도(penetration) 2급을 권한다는 베어링 회사 자료가 있고, XHP 222는 리튬 복합·EP·NLGI 2다. 다른 진동 바렐 회사 자료도 리튬 계열 그리스를 쓴다 | KVF3 3쪽 [참고, 종류 없음] / FAG TPI 197 인쇄 34쪽 "For normal operating conditions in vibratory machinery, we recommend lithium soap greases with EP (extreme pressure) and anti-corrosion additives corresponding to penetration class 2." [참고] / XHP 222 NLGI 2 [실제: RD0040 Mobil Grease 특성표], "lithium complex manufacturing technology", "Very good anti-wear and EP performance" [참고: Silmid 제품 페이지의 Mobil 설명] / Inovatec PZG(B)200 진동 바렐 운전 안내 6항 "lithium base grease (Q/ST1002-65)ZL—3" (중국 규격 3호, 우리 것보다 한 단계 굳음) [참고] / Inovatec 2025 정비 글 "Use a lithium-based grease … Mobil XHP 222" [참고] |
| OP-40 텀블러 — 양 | 니플 1개당 그리스건 1번(약 1.5 cm³) × 니플 2개 × 하루 2회 = **하루 약 6 cm³** → 카트리지(0.41 L) 1개로 약 68일(약 2.6개월, 월 26일) | 1번 누름 양 [참고] SKF 1077600 H 그리스건 사양 "Volume per stroke: Approx 1,5 cm3 (0.09 in. 3)" (다른 회사 그리스건. 실제 그리스건 사양으로 바꾼다) / "작은 양을 짧은 간격으로" [참고] FAG TPI 197 인쇄 35쪽 "relubricate the bearings with small quantities of grease at short intervals" / 니플 2개 [가상] (KVF3 원문 "BEARING ZERK FITTINGS" 복수, 수는 그림뿐) / 하루 2회 [가상] = 텀블러 16시간 운전(설계서 5.2 교대 2개) ÷ 8시간 |
| OP-40 텀블러 — 주의 | 그리스 종류를 바꾸지 않는다. 실제 설비를 들이면 그 매뉴얼의 그리스·양을 먼저 따른다 [가상: 팀 규칙] | FAG TPI 197 인쇄 34쪽 "Any change of grease type should be avoided if possible." [참고] |

### 4.6 재고 품목으로 넣지 않는 것

| 품목 | 넣지 않는 이유 | 다시 볼 때 |
|---|---|---|
| OP-40 세척액(세척제) | 세척기 기종과 탱크 용량이 [가상]이고, 세척제 제품을 정하지 않았다. 교체가 주기가 아니라 상태로 정해진다 ("Contaminated solution must be drained and replaced") → 하루 사용량을 계산할 수 없다 | 세척기 기종·세척제를 정하면 (탱크 용량 × 희석 농도 × 교체 횟수)로 계산. 교체 횟수는 설계서 알람 WSH-02(세정력 저하, 월 1~2건)를 쓸 수 있다 [Kerry MKC 4.2.2, PDF 20쪽] |
| OP-10 가이드 레일 오일(Mobil Vactra No. 2), 유압유·기어 오일 | 탱크 용량·소비량이 HCS-80 정비 장에 없다. 유압유·기어 오일은 1년에 1번 교체라 그때 따로 산다 | HCS-80 서비스 자료를 받으면 |
| OP-20 윤활유 | 기계 제조사를 정하지 않았다 (3.2) | 제조사를 정하면 |

---

## 5. 실시 기록 방법

MNT-04 화면에서 항목을 열고 아래 칸을 채워 확정한다. 칸 구성은 [가상]이다 (pm_record, 설계서 5.12).

| 칸 | 넣는 것 | 예 |
|---|---|---|
| 설비 | 설비 번호 | VF2-02 |
| 항목 코드 | `PM-{설비 번호}-{이 문서의 절}-{두 자리 순번}`. 순번은 그 절 표에서 그 설비 항목의 위에서부터 01, 02 … [가상] | PM-VF2-02-2.3-01 |
| 항목 | 이 문서의 항목 이름 (절 번호 함께) | 2.3 윤활유 저장소 양 점검·보충 |
| 예정일 | 달력의 기한 (자동) | 2026-09-26 |
| 실시일 | 실제 한 날짜·시각 | 2026-09-29 08:20 |
| 실시자 | 실제로 한 사람. 기본은 로그인 사용자(보전 담당자). 작업자가 하는 항목(1장 "누가 하나")은 보전 담당자가 기록하면서 그 작업자를 고른다 — 기록자는 따로 남는다 [가상] | 보전 담당자 |
| 결과 | 정상 / 보충·교체함 / 이상 있음 | 보충함 |
| 측정값 | 잰 값이 있는 항목만 (절삭유 농도 %, 공기 압력 등) | — |
| 사용 소모품 | 품목 번호와 수량 → **확정하면 재고에서 자동 차감** (INV-01) | CS-WLUB 0.9 L |
| 메모 | 이상 내용, 사진 | — |

| 규칙 | 내용 |
|---|---|
| 이상 있음 | OP-30은 DOC-03 해당 절을 열고 정비 작업지시서를 만든다. 다른 공정은 간이 작업기록 [가상] |
| 다음 기한 | 실시일 + 주기로 다시 잡는다 [가상] |
| 기한 넘김 알림 | 기한이 지나면 **AI 비서**가 담당자에게 알리고, 교대 시작 브리핑에 "점검 기한 n일 지남"으로 넣는다. 관련 알람(예: 2075)이 나면 함께 묶어 보여 준다 [가상] |
| 제때 실시율 | 기한 안에 한 건수 ÷ 기한이 된 건수. 목표 90% 이상 (1장) |
| 고친 기록 | 확정한 기록을 고치면 수정 이력(AST-03)에 남는다 |

---

## 6. 원문 대응표

| 이 문서 | 원문 | 쪽·줄·절 | 언어 | 파일 |
|---|---|---|---|---|
| 2장 (항목·주기) | Haas VMC Maintenance Schedule RD0080 Rev.B (2025-05) | 33~184행 (58항목) | 영어 | `docs/haas/ngc_official/07_예방정비/RD0080_vmc-maintenance-schedule/RD0080__RevB-2025-05__20261003__body.md` |
| 2장 (같은 표, 확인용) | Haas VMC Maintenance Schedule 웹 사본 | — | 영어 | `docs/haas/web_snapshots/howto_vmc_maintenance_schedule.txt` |
| 2.3 주축 테이퍼, 2장 끝 주석 | VF/VM Service Manual 18 Maintenance (VFVM-SM-18) | 18.2, 193~226행 | 영어 | `docs/haas/ngc_official/07_예방정비/VFVM-SM-18_maintenance/VFVM-SM-18__norev__20261003__body.md` |
| 2.1·2.2 교대 점검 | Haas Mill Weekly Maintenance Checklist | 43~99행 | 영어 | `docs/haas/ngc_official/07_예방정비/mill-checklist_mill-weekly-maintenance/mill-checklist__norev__20261003.md` |
| 2장 제외 규칙 | VF-2 제품 사양 | 사양표 | 영어 | `docs/haas/ngc_official/09_설비사양·설치/VF-2-spec_vf-2-product-page/VF-2-spec__norev__20261003__body.md` |
| 2장 균형 장치 | VF/VM Service Manual 7 Axis Motion (VFVM-SM-07) | 416행 | 영어 | `docs/haas/ngc_official/02_서보축_알람대응/VFVM-SM-07_axis-motion/VFVM-SM-07__norev__20261003__body.md` |
| 2.3·2.5, 4.1 축 윤활 | Lubrication Systems SM 2 Haas Axis Lubrication Oil (AD0630 포함) | 69·81·111·119~145행 | 영어 | `docs/haas/ngc_official/05_윤활/LUBE-SM-02_haas-axis-lubrication-oil/LUBE-SM-02__norev__20261003__body.md` |
| 2.3 그리스·주축 오일, 4.1 탱크 용량 | Lubricant, Grease, and Sealant Tables RD0040 Rev.H (2025-12) | Spindle Lubricants, Linear Guide/Ball Screw, Specialty Grease 표 | 영어 | `docs/inventory/haas_rd0040_lubricant_grease_sealant_tables_revH_2025-12.txt` |
| 4.2 ①② | OSHA Metalworking Fluids: Safety and Health Best Practices Manual | PDF 7쪽 | 영어 | `docs/inventory/소모품_사용량/OSHA_절삭유_안전보건_모범관리매뉴얼.pdf` |
| 4.2 ②③ | MSC 2023 절삭유 관리 19가지 | PDF 4쪽 | 영어 | `docs/inventory/소모품_사용량/MSC_2023_19hacks_절삭유관리_보충규칙.pdf` |
| 4.2 ④~⑦, 원액 제품 | Master Fluid Solutions TRIM SC538 제품 자료 (한국어, 2026-10-05 출력) | PDF 1~3쪽 | 한국어 | `docs/inventory/소모품_사용량/masterfluids_TRIM_SC538_제품자료_KR_20261005.pdf` (원문 URL https://www.masterfluids.com/kr/ko/data-sheet/di.php?pid=SC538) |
| 4.2 원액 제품 (쓰지 않은 이유) | Master Fluid Solutions TRIM SC520 제품 자료 (북미) | PDF 2~3쪽 | 영어 | `docs/inventory/소모품_사용량/masterfluids_TRIM_SC520_PDS.pdf` |
| 4.2 원액 종류 | Haas TSC-300/1K Troubleshooting Guide - NGC | 절삭유 종류 문단 (933행) | 영어 | `docs/haas/web_snapshots/tsg_tsc_300_1k_ngc.txt` |
| 4.2 ⑤ (6~7%) | Haas Mill Service Manual (2005) | 절삭유 혼합 문단 | 영어 | `docs/haas/en_mill_service_manual_2005.pdf` |
| 4.4 주축 윤활유 | Haas Spindle Minimum Lubrication System TG0135 Rev.A (2025-06) | Symptom Table, Oil Level | 영어 | `docs/haas/web_snapshots/tsg_spindle_minimum_lubrication.txt` 425~468행 |
| 4.4 주축 윤활유 (오일 비교) | 40T Spindle TSG TG0101 Rev B (2025-11) — VF/VM 서비스 매뉴얼 9.3 | Lubrication 절, 549행 | 영어 | `docs/haas/ngc_official/06_스핀들·기어박스/VFVM-SM-09_40t-spindle/VFVM-SM-09__norev__20261003__body.md` |
| 4.4 주축 윤활 시험 | Haas Mill - Spindle - Lubrication Oil - Collection Test (웹, 2026-02-18 보관본) | 5단계 | 영어 | `docs/haas/web_snapshots/howto_mill_spindle_lube_oil_collection_test_wayback20260218.html` |
| 4.4 하루 사용량 | Plant Services "Precision lubrication for high-speed spindle bearings" (W. Mitchell, 2002-11-15) | 본문 공기·오일 유량 문단 | 영어 | `docs/inventory/소모품_사용량/plantservices_2002_공기오일윤활_주축베어링_Mitchell.html` |
| 4.5 안전 재고 식 | NCS 치공구 관리(밀링가공) 학습모듈 | PDF 90쪽 | 한국어 | `docs/inventory/공구관리/NCS_LM1502010208_치공구관리_밀링가공_16v4.pdf` |
| 4.2 하루 손실 | CTE 1997 Coolant Care (Gedlenske) | 본문 | 영어 | `docs/inventory/소모품_사용량/CTE_1997_Coolant_Care_Gedlenske.html` |
| 2.6 공기 필터, 3.1 | HCS-80 Maintenance 5.1·5.2 (Rev.A 2026-07) | 5.1 정비 일정 표 | 영어 | `docs/haas/web_snapshots/haas_hcs_5_maintenance.html` |
| 2.6 공기 필터 위치 | Mill Operator's Manual NGC 96-8210 Rev V | F2.5 (PDF 60쪽), F2.9 Detail D (PDF 63쪽) | 영어 | `docs/haas/en_mill_ngc_operators_manual_2025.pdf` |
| 2.6 공기 필터 방법·부품번호 | Tool Release Piston (TRP) TSG (2024-10-08 갱신) | Water Separator Filter 절 | 영어 | `docs/haas/web_snapshots/tsg_tool_release_piston.txt` |
| 2장 절삭유 보충 제외 | NGC 전기 매뉴얼 29.1 Analog Sensor Information 표 / Coolant Refill - Operation - Maintenance AD0172 (웹 보관본 2026-04-09) | Coolant Level 줄 / Introduction·Installation | 영어 | `docs/haas/ngc_official/03_센서·공압·진단/NGC-ESM-29_sensors-switches/NGC-ESM-29__norev__20261003__body.md`, `docs/haas/web_snapshots/howto_coolant_refill_AD0172_wayback20260409.html` |
| 2장 균형 장치 제외 [참고] | Mill Service Manual 96-8100 rev L (2005) 1.8절 34쪽 / Mechanical Service Manual 96-0283D (2011) 인쇄 10쪽 | 균형 장치 압력표 | 영어 | `docs/haas/en_mill_service_manual_2005.pdf`, `docs/haas/en_mechanical_service_manual_2011.pdf` |
| 2장 우산형 센서 종류, 2.3 가이드 레일 | VF/VM Service Manual 4 Umbrella Tool Changer (웹 보관본 2025-01-15) | 4.1 Shuttle Sensors, 4.5 Rail Guides and Proximity Sensors | 영어 | `docs/haas/web_snapshots/man_vf_vm_04_umbrella_tool_changer_wayback20250115.html` |
| 2.3 가이드 레일 그리스 [참고] | Haas Mill Maintenance Checklist (Monthly) — 원본 PDF 404, 웹 검색 요약만 확인 | — | 영어 | (저장 못 함) `https://www.haascnc.com/content/dam/haascnc/videos/bonus-content/monthly-mill-maintenance-tasks---haas-service/Mill%20Maintenance%20Checklist%20(Monthly).pdf` |
| 2.3 공구 교환장치 센서 | Umbrella Tool Changer - Mechanical Switches and Proximity Sensors - Maintenance (2018-11-26 갱신, 웹 보관본 2026-02-17) | 20-Pocket Carousel 절 | 영어 | `docs/haas/web_snapshots/howto_umbrella_tc_switches_proximity_wayback20260217.html` |
| 3.3 텀블러 | Kalamazoo KVF3 진동 바렐 매뉴얼 | PDF 3쪽 | 영어 | `docs/maintenance/다른공정_정비/vibratory_finisher_KVF3_manual_Kalamazoo.pdf` |
| 3.3·4.5 텀블러 그리스 종류·양 [참고] | Schaeffler FAG TPI 197 "FAG Special Spherical Roller Bearings for Vibratory Machinery" | 인쇄 34쪽 Grease lubrication, 35쪽 relubrication (PDF 36·37쪽) | 영어 | `docs/maintenance/다른공정_정비/FAG_TPI197_진동기계용_구면롤러베어링_그리스.pdf` (원문 URL https://www.schaeffler.com/remotemedien/media/_shared_media/08_media_library/01_publications/schaeffler_2/tpi/downloads_8/tpi_197_de_en.pdf) |
| 4.5 텀블러 그리스 종류 [참고] | Inovatec Machinery PZG(B)200 진동 바렐 제품·운전 안내 (2026-10-05 저장) | 운전 안내 6항 | 영어 | `docs/maintenance/다른공정_정비/Inovatec_PZGB200_진동바렐_운전안내_20261005.html` (https://www.shinysmooth.com/u-shape-bowl-with-separating-unit-vibratory-machine-1578) |
| 4.5 텀블러 그리스 종류 [참고] | Inovatec "Vibratory Finishing Machine Maintenance: Complete 8-Step Checklist" (E. Zhang, 2025-06-22) | a. Grease Type and Recommendation, 정비 표 | 영어 | `docs/maintenance/다른공정_정비/Inovatec_2025_진동바렐_정비체크리스트_20261005.html` (https://www.inovatecmachinery.com/vibratory-finishing-machine-maintenance/) |
| 4.5 XHP 222 리튬 복합·EP [참고] | Silmid Mobilgrease XHP 222 제품 페이지 (Mobil 설명 인용) | 제품 설명 | 영어 | `docs/maintenance/다른공정_정비/Mobilgrease_XHP222_silmid_제품페이지_20261005.html` (https://www.silmid.com/lubricants/greases/Mobilgrease-XHP-222-Lithium-Grease/) |
| 4.5 그리스건 1번 누름 양 [참고] | SKF 1077600 H 그리스건 사양 (판매처 페이지) | Technical specifications | 영어 | `docs/maintenance/다른공정_정비/SKF_1077600H_그리스건_사양_slsbearings_20261005.html` (https://shop.slsbearings.com/sg/skf-grease-gun-1077600-h.html) |
| 4.2 SDS | Master Fluid Solutions TRIM SC538 안전 보건 정보 쪽 (한국어·아시아태평양 영어, 2026-10-05 저장) | 본문 1문장 | 한국어·영어 | `docs/inventory/소모품_사용량/masterfluids_TRIM_SC538_안전보건정보페이지_KR_20261005.html`, `..._AP_20261005.html` (https://www.masterfluids.com/kr/ko/products/show-product-health.php?pid=SC538) |
| 4.2 SDS [참고] | Master Chemical TRIM SC520 SAFETY DATA SHEET (SDS US, Version 02, Revision date 07-30-2015, MSC 게시본) | 1쪽 2장, 2쪽 4장, 2~3쪽 8장, 3~4쪽 9장 | 영어 | `docs/inventory/소모품_사용량/masterfluids_TRIM_SC520_SDS_미국판_2015-07-30.pdf` (http://www1.mscdirect.com/MSDS/MSDS00028/72761703-20160518.PDF) |
| 3.1 가이드 레일 보충 잠금 | HCS-80 Safety 2.1 / AD0630 (LUBE-SM-02 안) | 2.1 Safety Notes / 119·121행 | 영어 | `docs/haas/web_snapshots/haas_hcs_2_safety.html`, `docs/haas/ngc_official/05_윤활/LUBE-SM-02_haas-axis-lubrication-oil/LUBE-SM-02__norev__20261003__body.md` |
| 3.3 세척액 | Kerry MKC 운전·정비 매뉴얼 Issue 9 (2003) | 20쪽 4.2 | 영어 | `docs/maintenance/다른공정_정비/ultrasonic_cleaner_MKC_OM_manual_Kerry_Issue9_2003.pdf` |
| 3.3 세척액 수위 | Bransonic Ultrasonic Bath 사용 설명서 | PDF 14쪽, PDF 68쪽 표 7.1 | 영어 | `docs/line/branson_bransonic_manual_en_5410610.pdf` |
| 3.4 측정기 | NPL GPG 42 Issue 2 CMM 검증 | 9장, PDF 60·66·69쪽 | 영어 | `docs/maintenance/다른공정_정비/CMM_verification_NPL_GPG42_Issue2.pdf` |
| 1장 목표 | NASA RCM Guide (2008) 12장 | 12.10.3 PDF 191쪽, 표 12-4 PDF 190쪽 | 영어 | `docs/maintenance/정비지표/Maintenance_KPI_benchmarks_NASA_RCM_Guide2008.pdf` |
| 4장 품목·안전 재고, 3.2 | 가상 운영 데이터 설계서 v3 | 5.12, 5.14, 15.3, 15.5 | 한국어 | `가상데이터설계서_v3.md` |
| 2장·3장 항목 목록, 4장 차감 | 기획서 v4 | MNT-04, INV-01 | 한국어 | `기획서_v4.md` |

- 원문(Haas 등)은 저작권 때문에 공개 저장소에 올리지 않는다. 이 문서는 필요한 항목만 옮기고 정리했다.

---

## 7. 개정 기록

| 개정 | 날짜 | 내용 | 승인 |
|---|---|---|---|
| Rev.0 | 2026-10-05 | 처음 작성: OP-30 VF-2 RD0080 적용 24항목 (+ 밀 점검표 교대 점검), 다른 공정 4개, 소모품 차감 규칙, 실시 기록 방법. 같은 날 보충: 5장 "항목 코드" 줄(`PM-{설비}-{절}-{순번}`), "실시자" 줄(작업자 항목은 보전 담당자가 기록) | MGR |
