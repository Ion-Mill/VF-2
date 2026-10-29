-- =====================================================================
-- 10_dev_masters.sql — 개발·시험용 기준 정보
-- 값은 논리ERD 5.A·6장 표 그대로. 생성기 기준 정보 CSV(simulator/masters/)가 오면
-- 그것을 넣는다 (같은 값이어야 함 — db/checks/compare_masters.sql 대조) .
-- 알람 코드집은 원문 이름을 저장소에 두지 않으려고 자리표시 이름만 쓴다 (저작권, CLAUDE.md).
-- =====================================================================

INSERT INTO process (process_code, process_name, seq, is_base_bottleneck) VALUES
  ('OP-10', '절단', 1, false), ('OP-20', '황삭', 2, false), ('OP-30', '정밀 가공', 3, true),
  ('OP-40', '세척·디버링', 4, false), ('OP-50', '측정', 5, false);

INSERT INTO equipment (equipment_id, process_code, model, controller, std_cycle_min, batch_qty, batch_time_min, has_sensor,
                       size_x_mm, size_y_mm, size_z_mm, center_x_mm, center_y_mm, facing, size_source_tag, ref_model) VALUES
  ('SAW-01', 'OP-10', 'Haas HCS-80', 'Haas', 1.0, NULL, NULL, false, 2300, 2260, 2210, 6300, 4930, 'NEG_Y', 'REAL', NULL),
  ('MIL-01', 'OP-20', '3축 머시닝센터', 'Siemens 840D sl', 3.5, NULL, NULL, false, 2757, 1864, 2935, 9829, 4732, 'NEG_Y', 'REFERENCE',
      'DMG MORI CMX 600 V (크기만 빌림)'),
  ('VF2-01', 'OP-30', 'Haas VF-2', 'Haas NGC', 7.0, NULL, NULL, true, 3147, 2249, 2724, 13781, 4925, 'NEG_Y', 'REAL', NULL),
  ('VF2-02', 'OP-30', 'Haas VF-2', 'Haas NGC', 7.0, NULL, NULL, true, 3147, 2249, 2724, 17928, 4925, 'NEG_Y', 'REAL', NULL),
  ('WSH-01', 'OP-40', '초음파 세척기 + 텀블러', NULL, NULL, 30, 25, false, 3000, 1500, 1291, 22001, 4550, 'NEG_Y', 'VIRTUAL',
      '진동 바렐 Kalamazoo KVF3급 + 초음파 세척기 Branson CPX8800H-E급'),
  ('CMM-01', 'OP-50', '3차원 측정기', NULL, 0.9, NULL, NULL, false, 1110, 1266, 2414, 25923, 4433, 'NEG_Y', 'REFERENCE',
      'Hexagon TIGO SF 05.06.05');

INSERT INTO wip_buffer (buffer_code, from_process_code, to_process_code, limit_qty, warn_over_qty, warn_enabled, use_in_bottleneck) VALUES
  ('WIP-10-20', 'OP-10', 'OP-20', 30, 20, true, true),
  ('WIP-20-30', 'OP-20', 'OP-30', 30, 20, true, true),
  ('WIP-30-40', 'OP-30', 'OP-40', 60, NULL, false, false),
  ('WIP-40-50', 'OP-40', 'OP-50', 30, 20, true, true);

INSERT INTO plant_layout (layout_id, width_x_mm, depth_y_mm, ceiling_z_mm, origin_desc, axis_desc, equipment_gap_mm, aisle_width_mm, work_band_mm)
VALUES ('BLDG', 29000, 7000, 4000, '공장 안쪽 남서쪽 벽 모서리, 바닥',
        'X = 동쪽(+), 공정 흐름 OP-10 → OP-50 / Y = 북쪽(+), 주 통로에서 멀어지는 쪽 / Z = 위(+), 바닥 0 / 단위 mm',
        1000, 2000, 1000);

INSERT INTO layout_object (object_id, layout_id, object_kind, object_name, x_min_mm, x_max_mm, y_min_mm, y_max_mm, height_mm, source_tag, buffer_code) VALUES
  ('RACK-01', 'BLDG', 'MATERIAL_RACK', '봉재 랙', 1000, 5000, 6300, 6900, NULL, 'VIRTUAL', NULL),
  ('INF-01',  'BLDG', 'INFEED', 'SAW-01 투입 대', 1000, 5000, 3800, 5000, 925, 'VIRTUAL', NULL),
  ('WIP-1',   'BLDG', 'WIP_SPOT', '재공 OP-10→20 (한도 30, 상자 1)', 7350, 8550, 2000, 2800, NULL, 'VIRTUAL', 'WIP-10-20'),
  ('WIP-2',   'BLDG', 'WIP_SPOT', '재공 OP-20→30 (한도 30, 상자 1)', 11107, 12307, 2000, 2800, NULL, 'VIRTUAL', 'WIP-20-30'),
  ('WIP-3',   'BLDG', 'WIP_SPOT', '재공 OP-30→40 (한도 60, 상자 2)', 19401, 20601, 2000, 2800, NULL, 'VIRTUAL', 'WIP-30-40'),
  ('WIP-4',   'BLDG', 'WIP_SPOT', '재공 OP-40→50 (한도 30, 상자 1)', 23401, 24601, 2000, 2800, NULL, 'VIRTUAL', 'WIP-40-50'),
  ('SOAK-01', 'BLDG', 'SOAK_SHELF', '온도 맞춤 선반', 24501, 25701, 5900, 6400, NULL, 'VIRTUAL', NULL),
  ('FG-01',   'BLDG', 'FG_SPOT', '완성품 자리', 27478, 28678, 2000, 2800, NULL, 'VIRTUAL', NULL),
  ('AISLE-1', 'BLDG', 'AISLE', '주 통로', 0, 29000, 0, 2000, NULL, 'VIRTUAL', NULL),
  ('DOOR-1',  'BLDG', 'DOOR', '반입문 (동쪽 벽)', 29000, 29000, 0, 2600, 2600, 'VIRTUAL', NULL),
  ('EXIT-1',  'BLDG', 'EXIT', '비상구 (서쪽 벽)', 0, 0, 500, 1500, 2000, 'VIRTUAL', NULL);

INSERT INTO equipment_part_shape (equipment_id, shape_seq, part_code, part_name, shape_kind, size_x_mm, size_y_mm, size_z_mm,
                                  offset_x_mm, offset_y_mm, offset_z_mm, source_tag) VALUES
  ('WSH-01', 1, 'WSH-01-T', '진동 바렐 (KVF3급)', 'BOX', 914, 686, 914, -943, -307, 0, 'REFERENCE'),
  ('WSH-01', 2, 'WSH-01-B', '작업대', 'BOX', 1700, 750, 900, 550, -275, 0, 'VIRTUAL'),
  ('WSH-01', 3, 'WSH-01-U', '초음파 세척기 (CPX8800H-E급)', 'BOX', 597, 465, 391, 49, -275, 900, 'REFERENCE'),
  ('WSH-01', 4, 'WSH-01-R', '헹굼조', 'BOX', 597, 465, 391, 696, -275, 900, 'VIRTUAL'),
  ('WSH-01', 5, 'WSH-01-D', '건조 자리', 'BOX', 356, 750, NULL, 1222, -275, 900, 'VIRTUAL'),
  ('CMM-01', 1, NULL, '터치스크린 (본체 서쪽)', 'BOX', 867, NULL, NULL, -988, 0, NULL, 'REFERENCE');

-- 재고 품목 13개 (6.27)
INSERT INTO inventory_item (item_no, category, item_name, unit, owner_role, safety_stock, product_note) VALUES
  ('TL-EM10', 'TOOL', '엔드밀 Ø10', '개', 'SUP', 9, NULL),
  ('TL-DR50', 'TOOL', '드릴 Ø5.0 (M6 탭 아랫구멍)', '개', 'SUP', 5, NULL),
  ('TL-TAP6', 'TOOL', 'M6 탭', '개', 'SUP', 8, NULL),
  ('TL-BB45', 'TOOL', '보링바 인서트', '개', 'SUP', 4, NULL),
  ('TL-FM50', 'TOOL', '페이스밀 인서트', '개', 'SUP', 14, NULL),
  ('CS-WLUB', 'CONSUMABLE', '축 윤활유', 'L', 'MNT', 4, NULL),
  ('CS-COOL', 'CONSUMABLE', '절삭유 원액', 'L', 'MNT', 20, 'TRIM SC538'),
  ('CS-CFLT', 'CONSUMABLE', '절삭유 필터', '개', 'MNT', 2, NULL),
  ('CS-AFLT', 'CONSUMABLE', '공기 필터', '개', 'MNT', 2, NULL),
  ('CS-SLUB', 'CONSUMABLE', '주축 윤활유', 'L', 'MNT', 4, 'Mobil 1 0W-20'),
  ('CS-GRS',  'CONSUMABLE', '그리스 (14 oz 카트리지)', '개', 'MNT', 2, 'Mobil Grease XHP 222'),
  ('RM-6061', 'MATERIAL', '6061-T6 봉재', '개분', 'SUP', 200, NULL),
  ('FG-BRK-A100', 'FINISHED', 'BRK-A100 완제품', '개', 'SUP', NULL, NULL);

INSERT INTO product (product_code, product_name, material, line_base_cycle_min, material_item_no)
VALUES ('BRK-A100', '엔진 마운트 브래킷', '알루미늄 6061-T6', 3.5, 'RM-6061');

-- 공구 종류 5개 (6.25)
INSERT INTO tool_type (item_no, usage_unit, usage_per_part, life_limit, limit_basis, deduct_qty_per_change) VALUES
  ('TL-FM50', 'FEED', 0.5, 400, '[가상]', 5),
  ('TL-EM10', 'FEED', 2.5, 200, '[참고] 알루미늄 엔드밀 시험 약 200분 급마모', 1),
  ('TL-BB45', 'HOLES', 1, 400, '[가상]', 1),
  ('TL-DR50', 'HOLES', 4, 1000, '[가상]', 1),
  ('TL-TAP6', 'HOLES', 4, 400, '[참고] 알루미늄 M6 탭 수백~500구멍', 1);

-- 정지 사유 18개 (6.5)
INSERT INTO downtime_reason (reason_code, reason_group, reason_name, usual_state, six_loss, is_loss) VALUES
  ('F01','FAILURE','서보·앰프','DOWN','고장 정지 로스',true), ('F02','FAILURE','주축','DOWN','고장 정지 로스',true),
  ('F03','FAILURE','공구 교환장치','DOWN','고장 정지 로스',true), ('F04','FAILURE','윤활','DOWN','고장 정지 로스',true),
  ('F05','FAILURE','공압','DOWN','고장 정지 로스',true), ('F06','FAILURE','절삭유','DOWN','고장 정지 로스',true),
  ('M01','MATERIALS','소재 대기','IDLE',NULL,true), ('M02','MATERIALS','앞 공정 대기','IDLE',NULL,true),
  ('M03','MATERIALS','뒤 공정 막힘','BLOCKED',NULL,true),
  ('S01','SETUP','작업지시 교체 (로트 교체)','SETUP','준비 교체 로스',true), ('S02','SETUP','공구 교체','SETUP','준비 교체 로스',true),
  ('S03','SETUP','초품 검사','SETUP','준비 교체 로스',true),
  ('O01','OPERATION','프로그램 오류','IDLE','순간 정지 로스',true), ('O02','OPERATION','모드 오류','IDLE','순간 정지 로스',true),
  ('O03','OPERATION','도어 열림','IDLE','순간 정지 로스',true),
  ('P01','PLANNED','예방 정비','MAINT',NULL,false), ('P02','PLANNED','휴식',NULL,NULL,false), ('P03','PLANNED','계획 없음',NULL,NULL,false);

-- 알람 코드집 — 개발용 자리표시 (실제 이름·설명은 생성기 CSV에서). 등급·담당·절은 DOC-02 3장 표
INSERT INTO alarm_master (alarm_code, process_code, name_ko, severity, responder, lockout_level, doc02_section, is_virtual_code) VALUES
  ('992', 'OP-30', '(개발용) 알람 992', 'STOP', 'MNT', 'FULL', '§4.1', false),
  ('994', 'OP-30', '(개발용) 알람 994', 'STOP', 'MNT', 'FULL', '§4.2', false),
  ('108', 'OP-30', '(개발용) 알람 108', 'WARN', 'OPR', 'NONE', '§4.6', false),
  ('174', 'OP-30', '(개발용) 알람 174', 'WARN', 'OPR', 'NONE', '§4.8', false),
  ('254', 'OP-30', '(개발용) 알람 254', 'STOP', 'MNT', 'FULL', '§4.9', false),
  ('2075','OP-30', '(개발용) 알람 2075', 'WARN', 'OPR', 'TWO_POINT', '§4.11', false),
  ('120', 'OP-30', '(개발용) 알람 120', 'WARN', 'OPR', 'NONE', '§4.12', false),
  ('362', 'OP-30', '(개발용) 알람 362', 'WARN', 'OPR', 'NONE', '§4.13', false),
  ('314', 'OP-30', '(개발용) 알람 314', 'GUIDE', 'OPR', 'NONE', '§4.15', false),
  ('6302.00', 'OP-10', '(개발용) 알람 6302.00', 'STOP', 'MNT', 'FULL', '§5.1', false),
  ('5303.00', 'OP-10', '(개발용) 알람 5303.00', 'WARN', 'OPR', 'ONE_POINT', '§5.2', false),
  ('MP-170', 'OP-50', '(개발용) 알람 MP-170', 'STOP', 'MNT', 'FULL', '§5.7', true),
  ('TempComp-202', 'OP-50', '(개발용) 알람 TempComp-202', 'WARN', 'OPR', 'NONE', '§5.8', true);

-- 센서 항목 7개 (6.38) — 알람 기준값 없음
INSERT INTO sensor_item (sensor_code, sensor_name, unit, normal_min, normal_max, normal_median, linked_alarm_code) VALUES
  ('SpindleLoadPct', '주축 부하', '%', 0, 185, 38, '174'),
  ('SpindleMotorTemp', '주축 모터 온도', '℃', 28, 42, NULL, '254'),
  ('AirPressure', '공기 압력', 'psi', 100, 110, 105.3, '120'),
  ('Xload', 'X축 부하', '%', 0, 65, NULL, '108'),
  ('Yload', 'Y축 부하', '%', 0, 65, NULL, '108'),
  ('Zload', 'Z축 부하', '%', 0, 65, NULL, '108'),
  ('DcVolt', '직류 버스 전압', 'V', 300, 330, 317, NULL);

-- 검사 항목 8개 (6.29). 4번 기준 치수 110.000은 CMM 결과 파일 예시의 임시값 [가상] — 도면 값이 정해지면 바꿈
INSERT INTO inspection_item (product_code, item_seq, item_name, spec_text, nominal, lsl, usl, method, char_class, cpk_min,
                             in_sampling, enhanced_extension) VALUES
  ('BRK-A100', 1, '부싱 압입 구멍 지름', 'Ø45 H7 (+0.025 / 0 mm)', 45.000, 45.000, 45.025, 'CMM', 'SPECIAL', 1.67, true,
      '부싱 구멍 위·중간·아래 3단 측정 (기록만)'),
  ('BRK-A100', 2, '전체 길이', '150 ± 0.5 mm', 150.000, 149.500, 150.500, 'CMM', 'GENERAL', 1.33, true, NULL),
  ('BRK-A100', 3, '두께', '12 ± 0.2 mm', 12.000, 11.800, 12.200, 'CMM', 'GENERAL', 1.33, true, NULL),
  ('BRK-A100', 4, '구멍 간 거리', '± 0.1 mm (기준 치수 임시값 110)', 110.000, 109.900, 110.100, 'CMM', 'GENERAL', 1.33, true,
      '모든 구멍의 구멍 간 거리'),
  ('BRK-A100', 5, '평면도 (부착면)', '0.05 mm 이하', 0.000, NULL, 0.050, 'CMM', 'GENERAL', 1.33, true, NULL),
  ('BRK-A100', 6, 'M6 나사 (6H)', '통과 게이지 끝까지, 정지 게이지 2회전 넘게 안 들어감', NULL, NULL, NULL, 'GAUGE', 'GENERAL', NULL, true, NULL),
  ('BRK-A100', 7, '외관', '버·찍힘·구성인선 흔적 없음', NULL, NULL, NULL, 'VISUAL', 'GENERAL', NULL, false, '확대경으로 구성인선 흔적 확인'),
  ('BRK-A100', 8, '폭', '55 ± 0.3 mm', 55.000, 54.700, 55.300, 'CMM', 'GENERAL', 1.33, true, NULL);

-- 불량 코드 10개 (6.34). grade = 기본 등급, 예외는 grade_rule
INSERT INTO defect_code (defect_code, defect_name, related_items, grade, grade_rule, common_cause) VALUES
  ('DIM-01', '치수 큼 (상한 넘음)', '1~3, 8', 'MAJOR', '1번은 치명, 나머지 중', '공구 마모, 공구 오프셋'),
  ('DIM-02', '치수 작음 (하한 밑)', '1~3, 8', 'MAJOR', '1번은 치명, 나머지 중', '공구 오프셋, 충돌 뒤 위치 틀어짐'),
  ('DIM-03', '구멍 간 거리 벗어남', '4', 'MAJOR', NULL, '공작물 오프셋, 고정 불량'),
  ('DIM-04', '평면도 벗어남', '5', 'MAJOR', NULL, '고정 변형, 떨림'),
  ('THR-01', '나사 통과 게이지 안 들어감', '6', 'MAJOR', NULL, '탭 마모·파손, 기초 구멍 작음'),
  ('THR-02', '나사 정지 게이지 2회전 넘게 들어감', '6', 'MAJOR', NULL, '탭 크기·흔들림'),
  ('SUR-01', '버 남음', '7', 'MINOR', NULL, 'OP-40 디버링 부족'),
  ('SUR-02', '구성인선 흔적 (뜯긴 면)', '7', 'MINOR', '치수에 영향 있으면 중', '알루미늄이 날 끝에 붙는 구성인선'),
  ('SUR-03', '찍힘·긁힘', '7', 'MINOR', NULL, '운반·세척 중 부딪힘'),
  ('MAT-01', '원자재 성적서 불일치', '§7', 'MAJOR', NULL, '로트 코드·성분 불일치');

-- 사내 문서 8종 (6.52). 승인자는 사용자를 넣은 뒤 dev/20에서 채운다
INSERT INTO internal_doc (doc_no, doc_kind, doc_name, current_rev, rev_date, status, is_search_target, file_ref) VALUES
  ('DOC-01', 'MANUAL_DOC', '공정별 운영 매뉴얼', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-01_공정별운영매뉴얼.md'),
  ('DOC-02', 'MANUAL_DOC', '알람 코드집', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-02_알람코드집.md'),
  ('DOC-03', 'MANUAL_DOC', '고장 대응 매뉴얼', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-03_고장대응매뉴얼.md'),
  ('DOC-04', 'MANUAL_DOC', '예방 정비 기준서', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-04_예방정비기준서.md'),
  ('DOC-05', 'MANUAL_DOC', '안전 작업 기준서', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-05_안전작업기준서.md'),
  ('DOC-06', 'MANUAL_DOC', '검사 기준서', 'Rev.2', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-06_검사기준서.md'),
  ('DOC-07', 'MANUAL_DOC', '설비 데이터·지표 정의서', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/DOC-07_설비데이터지표정의서.md'),
  ('GLOSSARY', 'GLOSSARY', '용어집', 'Rev.1', '2026-10-07', 'APPROVED', true, '가상사내문서/00_용어집.md');

-- 알람 ↔ 관련 재고 품목 (보고 순위 같은 원인 묶기 — 2075 ↔ 축 윤활유)
SELECT fn_seed_alarm_related_items() AS alarm_related_items;
