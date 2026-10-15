-- 생성: supabase/build_migration.sh — db/schema → functions → views → seed (db/apply.sh 순서). 손으로 고치지 않는다
-- 만든 때: 2026-10-15T00:29:41Z
SET client_min_messages = warning;

-- ===================== db/schema/00_extensions.sql =====================
-- =====================================================================
-- 00_extensions.sql — 확장 기능
-- PostgreSQL 16 기준. 공식 postgres:16 이미지에 들어 있는 contrib만 쓴다.
-- =====================================================================

-- 설비 상태 구간 겹침 금지(R-04)를 EXCLUDE 제약으로 지키려면
-- 문자열(equipment_id) 같음(=)과 시각 범위 겹침(&&)을 한 GiST 인덱스에 섞어야 한다.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 문서 검색용 벡터(pgvector)는 임베딩 모델과 차원이 정해진 뒤 따로 넣는다.
--   → db/later/doc_chunk_embedding.sql  [선택 필요: 기술 회의]

-- ===================== db/schema/10_master.sql =====================
-- =====================================================================
-- 10_master.sql — A 기준 정보 (+ H의 role·app_user, E의 inventory_item)
-- 근거: 논리ERD_최종본 5.A, 5.H.1·5.H.2, 5.E.5, 6장 코드 목록
-- 규칙:
--   * 테이블·칼럼 이름은 논리 ERD 이름을 그대로 쓴다.
--   * 기준 정보는 지우지 않고 is_active = false 로 "사용 중지"한다 (6.53 MASTER).
--   * 코드는 varchar + CHECK. 한국어 표시 이름은 code_label 표(90_physical_extras.sql).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 역할 (6.37)
-- ---------------------------------------------------------------------
CREATE TABLE role (
    role_code   varchar(3)  PRIMARY KEY CHECK (role_code IN ('OPR','MNT','SUP','MGR')),
    role_name   varchar(20) NOT NULL
);
COMMENT ON TABLE role IS '역할 4종 (6.37)';

-- ---------------------------------------------------------------------
-- 공정 (5.A.1)
-- ---------------------------------------------------------------------
CREATE TABLE process (
    process_code        varchar(5)  PRIMARY KEY CHECK (process_code ~ '^OP-[0-9]{2}$'),
    process_name        varchar(20) NOT NULL,
    seq                 smallint    NOT NULL UNIQUE CHECK (seq > 0),
    is_base_bottleneck  boolean     NOT NULL DEFAULT false,
    is_active           boolean     NOT NULL DEFAULT true
);
COMMENT ON TABLE process IS '라인 공정 5개 OP-10~OP-50 (5.A.1)';
-- 기준 병목은 한 공정뿐 (OP-30)
CREATE UNIQUE INDEX ux_process_base_bottleneck ON process (is_base_bottleneck) WHERE is_base_bottleneck;

-- ---------------------------------------------------------------------
-- 사용자 (5.H.1) + 물리 추가: 로그인 칸 (11장 #11, NFR-SEC-07)
-- user_id 형식 [제안]: 역할 소문자 + 두 자리 (U02, U07, U10, U12)
--   — CMM 결과 파일 예시의 operator 값(U06)과 같은 모양
-- ---------------------------------------------------------------------
CREATE TABLE app_user (
    user_id            varchar(20) PRIMARY KEY CHECK (user_id ~ '^[A-Za-z0-9_]{2,20}$'),
    user_name          varchar(40) NOT NULL,
    role_code          varchar(3)  NOT NULL REFERENCES role,
    home_shift_type    varchar(5)  CHECK (home_shift_type IN ('DAY','NIGHT')),
    home_process_code  varchar(5)  REFERENCES process,
    -- 두 번째 담당 공정 (2026-10-10, 논리 ERD 5.H.1): OPR만. 교대당 3명이 5공정 (OP-10 → OP-20, OP-50 → OP-40).
    -- "담당 공정"을 쓰는 곳(알람 처리 책임 OPR, 작업자 요약, 현장 보기)은 두 칸을 함께 본다
    home_process_code_2 varchar(5) REFERENCES process,
    is_active          boolean     NOT NULL DEFAULT true,
    -- 물리 추가 (로그인)
    password_hash      text,                         -- scrypt (app/security.py). 비면 로그인 불가
    created_at         timestamptz NOT NULL DEFAULT now(),
    last_login_at      timestamptz,
    CONSTRAINT ck_app_user_process_2 CHECK (home_process_code_2 IS NULL OR
        (role_code = 'OPR' AND home_process_code IS NOT NULL AND home_process_code_2 <> home_process_code))
);
COMMENT ON TABLE app_user IS '사용자 (5.H.1). 퇴사해도 행을 지우지 않고 is_active=false (6.53 USER)';
COMMENT ON COLUMN app_user.password_hash IS '물리 추가: scrypt$N$r$p$salt$hash 형식. 평문 저장 금지 (NFR-SEC-06·07)';

-- ---------------------------------------------------------------------
-- 설비 (5.A.2)
-- ---------------------------------------------------------------------
CREATE TABLE equipment (
    equipment_id     varchar(10)  PRIMARY KEY,
    process_code     varchar(5)   NOT NULL REFERENCES process,
    model            varchar(60)  NOT NULL,
    controller       varchar(40),
    std_cycle_min    numeric(6,2) CHECK (std_cycle_min > 0),
    batch_qty        integer      CHECK (batch_qty > 0),
    batch_time_min   numeric(6,2) CHECK (batch_time_min > 0),
    has_sensor       boolean      NOT NULL DEFAULT false,
    size_x_mm        integer      NOT NULL CHECK (size_x_mm > 0),
    size_y_mm        integer      NOT NULL CHECK (size_y_mm > 0),
    size_z_mm        integer      NOT NULL CHECK (size_z_mm > 0),
    center_x_mm      integer      NOT NULL,
    center_y_mm      integer      NOT NULL,
    facing           varchar(5)   NOT NULL DEFAULT 'NEG_Y' CHECK (facing IN ('NEG_Y','POS_Y','NEG_X','POS_X')),
    size_source_tag  varchar(9)   NOT NULL CHECK (size_source_tag IN ('REAL','REFERENCE','VIRTUAL')),
    ref_model        varchar(120),
    is_active        boolean      NOT NULL DEFAULT true,
    -- 크기 근거가 [참고]면 참고 모델이 있어야 한다 (5.A.2 ref_model "조건")
    CONSTRAINT ck_equipment_ref_model CHECK (size_source_tag <> 'REFERENCE' OR ref_model IS NOT NULL),
    -- 묶음 설비(WSH-01)는 묶음 수량·시간을 함께 가진다
    CONSTRAINT ck_equipment_batch CHECK ((batch_qty IS NULL) = (batch_time_min IS NULL)),
    -- 공정 실적·작업지시서가 "그 공정의 설비"인지 복합 FK로 확인하려고 둔다
    CONSTRAINT ux_equipment_process UNIQUE (equipment_id, process_code)
);
COMMENT ON TABLE equipment IS '설비 6대 (5.A.2). 외형·배치 좌표는 mm, 원점·축은 plant_layout (R-83)';

-- ---------------------------------------------------------------------
-- 차단 지점 (5.A.3)
-- ---------------------------------------------------------------------
CREATE TABLE isolation_point (
    isolation_point_id  varchar(16)  PRIMARY KEY,
    equipment_id        varchar(10)  NOT NULL REFERENCES equipment,
    point_name          varchar(60)  NOT NULL,
    energy_type         varchar(11)  NOT NULL CHECK (energy_type IN ('ELEC','ELEC_SUPPLY','AIR')),
    location            varchar(120) NOT NULL,
    lock_method         varchar(120) NOT NULL,
    seq                 smallint     NOT NULL CHECK (seq > 0),
    CONSTRAINT ck_isolation_point_id CHECK (isolation_point_id LIKE equipment_id || '-%'),
    CONSTRAINT ux_isolation_point_seq UNIQUE (equipment_id, seq)
);
COMMENT ON TABLE isolation_point IS '설비별 에너지 차단 지점 (5.A.3, DOC-05 §3)';

-- ---------------------------------------------------------------------
-- 재고 품목 (5.E.5) — product가 가리키므로 여기서 먼저 만든다
-- on_hand_qty는 inventory_txn 트리거가 유지하는 저장 계산값 (R-11, 02_물리ERD 6장)
-- ---------------------------------------------------------------------
CREATE TABLE inventory_item (
    item_no              varchar(20)   PRIMARY KEY CHECK (item_no ~ '^(TL|CS|RM|FG)-[A-Z0-9-]+$'),
    category             varchar(10)   NOT NULL CHECK (category IN ('TOOL','CONSUMABLE','MATERIAL','FINISHED')),
    item_name            varchar(60)   NOT NULL,
    unit                 varchar(4)    NOT NULL CHECK (unit IN ('개','L','개분')),
    owner_role           varchar(3)    NOT NULL REFERENCES role CHECK (owner_role IN ('MNT','SUP')),
    safety_stock         numeric(12,3) CHECK (safety_stock >= 0),
    product_note         varchar(120),
    on_hand_qty          numeric(12,3) NOT NULL DEFAULT 0,
    safety_stock_set_by  varchar(20)   REFERENCES app_user,
    safety_stock_set_at  timestamptz,
    is_active            boolean       NOT NULL DEFAULT true,
    -- R-11 재고 수량은 음수가 될 수 없다 (트리거가 거래마다 더하고, 이 제약이 막는다)
    CONSTRAINT ck_inventory_item_on_hand CHECK (on_hand_qty >= 0),
    -- 완제품은 안전 재고·부족 알림이 없다 (6.27, R-39)
    CONSTRAINT ck_inventory_item_fg_safety CHECK (category <> 'FINISHED' OR safety_stock IS NULL),
    CONSTRAINT ck_inventory_item_set CHECK ((safety_stock_set_by IS NULL) = (safety_stock_set_at IS NULL))
);
COMMENT ON TABLE inventory_item IS '재고 품목 13개: 공구 5, 소모품 6, 원자재 1, 완제품 1 (5.E.5, 6.27)';
COMMENT ON COLUMN inventory_item.on_hand_qty IS '계산 저장: 입고 − 사용·출하 ± 조정. inventory_txn INSERT 트리거만 바꾼다';

-- ---------------------------------------------------------------------
-- 제품 (5.A.4)
-- ---------------------------------------------------------------------
CREATE TABLE product (
    product_code         varchar(20)  PRIMARY KEY,
    product_name         varchar(60)  NOT NULL,
    material             varchar(40)  NOT NULL,
    line_base_cycle_min  numeric(6,2) NOT NULL CHECK (line_base_cycle_min > 0),
    material_item_no     varchar(20)  NOT NULL REFERENCES inventory_item,
    is_active            boolean      NOT NULL DEFAULT true
);

-- ---------------------------------------------------------------------
-- 근무일 (5.A.5) · 교대 (5.A.6)
-- ---------------------------------------------------------------------
CREATE TABLE work_day (
    work_date         date    PRIMARY KEY,
    is_workday        boolean NOT NULL,
    daily_target_qty  integer CHECK (daily_target_qty >= 0),
    CONSTRAINT ck_work_day_target CHECK (NOT is_workday OR daily_target_qty IS NOT NULL)
);

CREATE TABLE shift (
    shift_id            varchar(12) PRIMARY KEY,
    work_date           date        NOT NULL REFERENCES work_day,
    shift_type          varchar(5)  NOT NULL CHECK (shift_type IN ('DAY','NIGHT')),
    start_at            timestamptz NOT NULL,
    end_at              timestamptz NOT NULL,
    planned_time_min    integer     NOT NULL CHECK (planned_time_min > 0),
    target_qty          integer     NOT NULL CHECK (target_qty >= 0),
    -- 이월 (5.A.6, R-88): 야간만 = max(0, 같은 생산일 주간 목표 − 주간 실적). 프로그램이 채운다 (fn_refresh_carry_over)
    carry_over_qty      integer     NOT NULL DEFAULT 0 CHECK (carry_over_qty >= 0),
    supervisor_user_id  varchar(20) NOT NULL REFERENCES app_user,
    CONSTRAINT ux_shift_day_type UNIQUE (work_date, shift_type),
    CONSTRAINT ck_shift_time CHECK (end_at > start_at),
    -- R-88 이월은 같은 생산일 주간 → 야간만. 주간은 늘 0 (앞 근무일 야간의 부족은 넘기지 않는다)
    CONSTRAINT ck_shift_carry_over_day CHECK (shift_type = 'NIGHT' OR carry_over_qty = 0),
    -- shift_id = {생산일}-D / {생산일}-N  (야간이 자정을 넘어도 시작한 날짜)
    CONSTRAINT ck_shift_id CHECK (
        shift_id = to_char(work_date, 'YYYY-MM-DD') || '-' || CASE shift_type WHEN 'DAY' THEN 'D' ELSE 'N' END)
);
COMMENT ON TABLE shift IS '교대 (5.A.6). 야간 교대는 다음 날 05:00에 끝나도 work_date는 시작한 날 — 날짜 계산은 DATE(시각)이 아니라 이 칸으로';
COMMENT ON COLUMN shift.carry_over_qty IS '이월 (R-88). 총 목표 = target_qty + carry_over_qty. 하루 목표(work_day.daily_target_qty 180)에는 더하지 않는다';

-- ---------------------------------------------------------------------
-- 재공 위치 (5.A.7)
-- ---------------------------------------------------------------------
CREATE TABLE wip_buffer (
    buffer_code        varchar(10) PRIMARY KEY CHECK (buffer_code ~ '^WIP-[0-9]{2}-[0-9]{2}$'),
    from_process_code  varchar(5)  NOT NULL UNIQUE REFERENCES process,
    to_process_code    varchar(5)  NOT NULL UNIQUE REFERENCES process,
    limit_qty          integer     NOT NULL CHECK (limit_qty > 0),
    warn_over_qty      integer     CHECK (warn_over_qty >= 0),
    warn_enabled       boolean     NOT NULL,
    use_in_bottleneck  boolean     NOT NULL,
    CONSTRAINT ck_wip_buffer_warn CHECK (NOT warn_enabled OR warn_over_qty IS NOT NULL),
    CONSTRAINT ck_wip_buffer_order CHECK (from_process_code <> to_process_code)
);

-- ---------------------------------------------------------------------
-- 공장 배치 (5.A.8) · 배치 물체 (5.A.9) · 설비 부품 도형 (5.A.10)
-- ---------------------------------------------------------------------
CREATE TABLE plant_layout (
    layout_id         varchar(10) PRIMARY KEY,
    width_x_mm        integer     NOT NULL CHECK (width_x_mm > 0),
    depth_y_mm        integer     NOT NULL CHECK (depth_y_mm > 0),
    ceiling_z_mm      integer     NOT NULL CHECK (ceiling_z_mm > 0),
    origin_desc       text        NOT NULL,
    axis_desc         text        NOT NULL,
    equipment_gap_mm  integer     NOT NULL CHECK (equipment_gap_mm >= 0),
    aisle_width_mm    integer     NOT NULL CHECK (aisle_width_mm > 0),
    work_band_mm      integer     NOT NULL CHECK (work_band_mm > 0),
    -- 계산 (5.A.8 floor_area_m2): 가로 × 세로
    floor_area_m2     numeric(10,1) GENERATED ALWAYS AS (round(width_x_mm::numeric * depth_y_mm / 1000000, 1)) STORED
);

CREATE TABLE layout_object (
    object_id     varchar(10)  PRIMARY KEY,
    layout_id     varchar(10)  NOT NULL REFERENCES plant_layout,
    object_kind   varchar(13)  NOT NULL CHECK (object_kind IN
                    ('MATERIAL_RACK','INFEED','WIP_SPOT','SOAK_SHELF','FG_SPOT','AISLE','DOOR','EXIT')),
    object_name   varchar(80)  NOT NULL,
    x_min_mm      integer      NOT NULL,
    x_max_mm      integer      NOT NULL,
    y_min_mm      integer      NOT NULL,
    y_max_mm      integer      NOT NULL,
    height_mm     integer      CHECK (height_mm > 0),
    source_tag    varchar(9)   NOT NULL CHECK (source_tag IN ('REAL','REFERENCE','VIRTUAL')),
    buffer_code   varchar(10)  UNIQUE REFERENCES wip_buffer,
    CONSTRAINT ck_layout_object_x CHECK (x_max_mm >= x_min_mm),
    CONSTRAINT ck_layout_object_y CHECK (y_max_mm > y_min_mm),
    -- 재공 자리만 재공 위치를 가리키고, 재공 자리는 반드시 가리킨다 (5.A.9 buffer_code "조건")
    CONSTRAINT ck_layout_object_buffer CHECK ((object_kind = 'WIP_SPOT') = (buffer_code IS NOT NULL))
);

CREATE TABLE equipment_part_shape (
    equipment_id  varchar(10) NOT NULL REFERENCES equipment,
    shape_seq     smallint    NOT NULL CHECK (shape_seq > 0),
    part_code     varchar(16),
    part_name     varchar(40) NOT NULL,
    shape_kind    varchar(8)  NOT NULL CHECK (shape_kind IN ('BOX','CYLINDER')),
    size_x_mm     integer     NOT NULL CHECK (size_x_mm > 0),
    size_y_mm     integer     CHECK (size_y_mm > 0),
    size_z_mm     integer     CHECK (size_z_mm > 0),
    offset_x_mm   integer,
    offset_y_mm   integer,
    -- 논리 ERD는 필수(○)지만 R1 표의 CMM-01 터치스크린에는 값이 없다 → 비움 허용 (02_물리ERD 9장 #3)
    offset_z_mm   integer,
    source_tag    varchar(9)  NOT NULL CHECK (source_tag IN ('REAL','REFERENCE','VIRTUAL')),
    PRIMARY KEY (equipment_id, shape_seq),
    -- 원기둥은 지름을 size_x = size_y로 둔다 (6.50)
    CONSTRAINT ck_part_shape_cylinder CHECK (shape_kind <> 'CYLINDER' OR size_y_mm IS NULL OR size_y_mm = size_x_mm)
);

-- ===================== db/schema/20_production.sql =====================
-- =====================================================================
-- 20_production.sql — B 생산 (원자재 로트·작업지시·생산 로트·공정 실적·재공)
-- 근거: 논리ERD_최종본 5.B, 6.7~6.9, R-05~R-08, R-13, R-19
-- bottleneck_log는 alarm_event 뒤(30), lot_hold는 tool 뒤(40)에 만든다.
-- 업무 번호 형식은 CHECK로 막는다 → 생성기 CSV 번호가 어긋나면 적재 때 바로 드러난다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 원자재 로트 (5.B.1)
-- ---------------------------------------------------------------------
CREATE TABLE raw_material_lot (
    material_lot_no   varchar(16) PRIMARY KEY CHECK (material_lot_no ~ '^MAT-[0-9]{4}-[0-9]{2,3}$'),
    item_no           varchar(20) NOT NULL REFERENCES inventory_item,
    received_date     date        NOT NULL,
    received_qty      integer     NOT NULL CHECK (received_qty > 0),
    supplier_cert_no  varchar(40) NOT NULL,
    heat_batch_no     varchar(40),
    status            varchar(18) NOT NULL DEFAULT 'WAIT_RECEIPT_CHECK'
                      CHECK (status IN ('WAIT_RECEIPT_CHECK','AVAILABLE','RECEIPT_HOLD'))
);
COMMENT ON TABLE raw_material_lot IS '원자재 로트 (5.B.1). AVAILABLE일 때만 생산 로트에 쓸 수 있다 (R-06a, 트리거)';

-- ---------------------------------------------------------------------
-- 생산 작업지시 (5.B.2)
-- ---------------------------------------------------------------------
CREATE TABLE production_order (
    order_no      varchar(12) PRIMARY KEY CHECK (order_no ~ '^PO-[0-9]{4}-[0-9]{3}$'),
    product_code  varchar(20) NOT NULL REFERENCES product,
    order_qty     integer     NOT NULL CHECK (order_qty > 0),
    created_at    timestamptz NOT NULL,
    due_at        timestamptz NOT NULL,
    status        varchar(11) NOT NULL DEFAULT 'WAITING'
                  CHECK (status IN ('WAITING','IN_PROGRESS','DONE','CANCELLED')),
    started_at    timestamptz,
    completed_at  timestamptz,
    -- "생산 중"부터 시작 시각 필수 (대기 중 취소는 시작 시각 없음)
    CONSTRAINT ck_production_order_started CHECK (status NOT IN ('IN_PROGRESS','DONE') OR started_at IS NOT NULL),
    CONSTRAINT ck_production_order_done CHECK (status <> 'DONE' OR completed_at IS NOT NULL),
    CONSTRAINT ck_production_order_due CHECK (due_at > created_at)
);

-- ---------------------------------------------------------------------
-- 생산 로트 (5.B.3)
-- completed_qty(R-05)·expected_complete_at은 계산 → v_production_lot (03_views)
-- ---------------------------------------------------------------------
CREATE TABLE production_lot (
    lot_no           varchar(20) PRIMARY KEY,
    order_no         varchar(12) NOT NULL REFERENCES production_order,
    lot_seq          smallint    NOT NULL CHECK (lot_seq > 0),
    input_shift_id   varchar(12) NOT NULL REFERENCES shift,
    material_lot_no  varchar(16) NOT NULL REFERENCES raw_material_lot,
    input_qty        integer     NOT NULL CHECK (input_qty > 0),
    status           varchar(15) NOT NULL DEFAULT 'IN_PROCESS' CHECK (status IN
                     ('IN_PROCESS','WAIT_INSPECTION','WAIT_JUDGEMENT','HOLD_REVIEW',
                      'PASSED','ON_HOLD','RELEASED','SCRAPPED')),
    scrap_qty        integer     NOT NULL DEFAULT 0 CHECK (scrap_qty >= 0),
    judged_at        timestamptz,
    CONSTRAINT ux_production_lot_seq UNIQUE (order_no, lot_seq),
    -- LOT-2609-041-1 = 'LOT-' + 작업지시 번호 몸통(2609-041) + '-' + 순번
    CONSTRAINT ck_production_lot_no CHECK (lot_no = 'LOT-' || substr(order_no, 4) || '-' || lot_seq),
    CONSTRAINT ck_production_lot_scrap CHECK (scrap_qty <= input_qty),
    -- 합격·보류 검토가 되면 판정 시각 필수 (5.B.3 judged_at)
    CONSTRAINT ck_production_lot_judged CHECK (status NOT IN ('PASSED','HOLD_REVIEW') OR judged_at IS NOT NULL)
);
CREATE INDEX ix_production_lot_shift ON production_lot (input_shift_id);
CREATE INDEX ix_production_lot_material ON production_lot (material_lot_no);
CREATE INDEX ix_production_lot_status ON production_lot (status);

-- ---------------------------------------------------------------------
-- 공정 실적 (5.B.4)
-- ---------------------------------------------------------------------
CREATE TABLE operation_report (
    op_report_id    bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    lot_no          varchar(20) NOT NULL REFERENCES production_lot,
    process_code    varchar(5)  NOT NULL REFERENCES process,
    equipment_id    varchar(10) NOT NULL,
    worker_user_id  varchar(20) NOT NULL REFERENCES app_user,
    shift_id        varchar(12) NOT NULL REFERENCES shift,
    start_at        timestamptz NOT NULL,
    end_at          timestamptz,
    pq              integer     NOT NULL CHECK (pq >= 0),
    gq              integer     NOT NULL CHECK (gq >= 0),
    rq              integer     NOT NULL CHECK (rq >= 0),
    sq              integer     NOT NULL CHECK (sq >= 0),
    -- "그 공정의 설비여야 함" → 복합 FK
    CONSTRAINT fk_operation_report_equipment FOREIGN KEY (equipment_id, process_code)
        REFERENCES equipment (equipment_id, process_code),
    CONSTRAINT ux_operation_report UNIQUE (lot_no, process_code, equipment_id, shift_id),
    CONSTRAINT ck_operation_report_time CHECK (end_at IS NULL OR end_at > start_at),
    -- R-19 생산 수량 = 양품 + 재작업 + 불량
    CONSTRAINT ck_operation_report_qty CHECK (pq = gq + rq + sq)
);
CREATE INDEX ix_operation_report_shift ON operation_report (shift_id, process_code);
CREATE INDEX ix_operation_report_equipment_time ON operation_report (equipment_id, start_at);

-- ---------------------------------------------------------------------
-- 재공 기록 (5.B.5) — L2 시계열 (1년 → 1시간 집계 wip_hourly)
-- ---------------------------------------------------------------------
CREATE TABLE wip_log (
    buffer_code     varchar(10) NOT NULL REFERENCES wip_buffer,
    logged_at       timestamptz NOT NULL,
    wip_qty         integer     NOT NULL CHECK (wip_qty >= 0),
    soak_shelf_qty  integer     CHECK (soak_shelf_qty >= 0),
    interval_type   varchar(4)  NOT NULL CHECK (interval_type IN ('MIN5','MIN1')),
    PRIMARY KEY (buffer_code, logged_at),
    -- 온도 맞춤 선반 수량은 WIP-40-50에만 (재공에 세지 않음, R-13)
    CONSTRAINT ck_wip_log_soak CHECK (soak_shelf_qty IS NULL OR buffer_code = 'WIP-40-50')
);
CREATE INDEX ix_wip_log_time ON wip_log USING brin (logged_at);

-- ===================== db/schema/30_equipment_alarm.sql =====================
-- =====================================================================
-- 30_equipment_alarm.sql — C 설비·알람 (+ B의 bottleneck_log)
-- 근거: 논리ERD_최종본 5.C, 5.B.6, 6.1~6.6, 6.11, 6.38, 6.40, R-01·R-04·R-21~R-24
-- equipment_state_log는 pm_record를 가리켜서 50_maintenance.sql에 둔다.
-- alarm_guide_map은 internal_doc을 가리켜서 70_documents.sql에 둔다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 알람 코드집 (5.C.1) — 내용(원문 이름·설명)은 생성기 기준 정보 CSV로 넣는다.
-- 원문(Haas·Siemens) 글은 저작권 때문에 공개 저장소에 시드로 두지 않는다 (CLAUDE.md).
-- ---------------------------------------------------------------------
CREATE TABLE alarm_master (
    alarm_code       varchar(20)  PRIMARY KEY,
    process_code     varchar(5)   NOT NULL REFERENCES process,
    name_en          varchar(120),
    name_ko          varchar(200) NOT NULL,
    original_desc    text,
    easy_desc        text,
    severity         varchar(5)   NOT NULL CHECK (severity IN ('STOP','WARN','GUIDE')),
    responder        varchar(3)   NOT NULL CHECK (responder IN ('OPR','MNT')),
    responder_note   varchar(120),
    lockout_level    varchar(9)   NOT NULL CHECK (lockout_level IN ('FULL','TWO_POINT','ONE_POINT','UNPLUG','NONE')),
    chain_rule       varchar(120),
    doc02_section    varchar(20)  NOT NULL,
    source_ref       varchar(200),            -- 사람이 근거를 추적하는 용도만. 화면·비서 답에 쓰지 않음 (R-85)
    is_virtual_code  boolean      NOT NULL DEFAULT false,
    is_active        boolean      NOT NULL DEFAULT true
);
COMMENT ON COLUMN alarm_master.source_ref IS '원문 근거 위치. 화면·지침카드·비서 답에 표시 금지 (R-85)';

-- ---------------------------------------------------------------------
-- 알람 이벤트 (5.C.3) — L3 (2년)
-- R-24 알람은 그 알람의 공정 설비에서만 → 트리거 (functions/20_integrity.sql)
-- ---------------------------------------------------------------------
CREATE TABLE alarm_event (
    alarm_event_id       bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    equipment_id         varchar(10) NOT NULL REFERENCES equipment,
    alarm_code           varchar(20) NOT NULL REFERENCES alarm_master,
    severity_at_event    varchar(5)  NOT NULL CHECK (severity_at_event IN ('STOP','WARN','GUIDE')),
    occurred_at          timestamptz NOT NULL,
    cleared_at           timestamptz,
    lot_no               varchar(20) REFERENCES production_lot,
    prev_alarm_event_id  bigint      REFERENCES alarm_event,
    is_injected          boolean     NOT NULL DEFAULT false,
    scenario_code        varchar(2)  CHECK (scenario_code IN ('S1','S2','S3','S4','S5','S6')),
    CONSTRAINT ck_alarm_event_cleared CHECK (cleared_at IS NULL OR cleared_at >= occurred_at),
    CONSTRAINT ck_alarm_event_injected CHECK (NOT is_injected OR scenario_code IS NOT NULL),
    CONSTRAINT ck_alarm_event_prev CHECK (prev_alarm_event_id IS DISTINCT FROM alarm_event_id)
);
-- 반복 알람(같은 설비·같은 알람 7일 안 3번, R-70)과 같은 사례 찾기(FR-MNT-05-11)
CREATE INDEX ix_alarm_event_repeat ON alarm_event (equipment_id, alarm_code, occurred_at);
CREATE INDEX ix_alarm_event_time ON alarm_event (occurred_at);
CREATE INDEX ix_alarm_event_lot ON alarm_event (lot_no) WHERE lot_no IS NOT NULL;

-- ---------------------------------------------------------------------
-- 정지 사유 코드 (5.C.5, 6.5)
-- ---------------------------------------------------------------------
CREATE TABLE downtime_reason (
    reason_code   varchar(3)  PRIMARY KEY CHECK (reason_code ~ '^[FMSOP][0-9]{2}$'),
    reason_group  varchar(10) NOT NULL CHECK (reason_group IN ('FAILURE','MATERIALS','SETUP','OPERATION','PLANNED')),
    reason_name   varchar(40) NOT NULL,
    usual_state   varchar(7)  CHECK (usual_state IN ('RUN','IDLE','BLOCKED','SETUP','DOWN','MAINT')),
    six_loss      varchar(40),
    is_loss       boolean     NOT NULL,
    is_active     boolean     NOT NULL DEFAULT true,
    -- 계획(PLANNED) 그룹만 손실이 아니다
    CONSTRAINT ck_downtime_reason_loss CHECK (is_loss = (reason_group <> 'PLANNED')),
    -- 코드 첫 글자 = 그룹 (F 고장, M 자재·흐름, S 준비, O 조작, P 계획)
    CONSTRAINT ck_downtime_reason_prefix CHECK (left(reason_code, 1) =
        CASE reason_group WHEN 'FAILURE' THEN 'F' WHEN 'MATERIALS' THEN 'M' WHEN 'SETUP' THEN 'S'
                          WHEN 'OPERATION' THEN 'O' ELSE 'P' END)
);

-- ---------------------------------------------------------------------
-- 센서 항목 (5.C.6) — 알람 기준값 칸은 두지 않는다
-- ---------------------------------------------------------------------
CREATE TABLE sensor_item (
    sensor_code        varchar(20)  PRIMARY KEY,
    sensor_name        varchar(40)  NOT NULL,
    unit               varchar(10)  NOT NULL,
    normal_min         numeric(10,2) NOT NULL,
    normal_max         numeric(10,2) NOT NULL,
    normal_median      numeric(10,2),
    linked_alarm_code  varchar(20)  REFERENCES alarm_master,
    CONSTRAINT ck_sensor_item_range CHECK (normal_max >= normal_min)
);

-- ---------------------------------------------------------------------
-- 센서 값 (5.C.7) — 시계열. interval_type으로 나눠 둔다 (L1 5초 90일 / L2 1분 평균 1년). 코드 MIN1_AVG·SEC5 (논리 ERD 2026-10-14)
-- PK에 interval_type을 넣는다: 파티션 키는 PK에 있어야 하고,
-- 사건 구간에서 1분 평균과 5초 값이 같은 시각을 가질 수 있다.
-- ---------------------------------------------------------------------
CREATE TABLE sensor_sample (
    equipment_id   varchar(10) NOT NULL REFERENCES equipment,
    sensor_code    varchar(20) NOT NULL REFERENCES sensor_item,
    sampled_at     timestamptz NOT NULL,
    interval_type  varchar(8)  NOT NULL CHECK (interval_type IN ('MIN1_AVG','SEC5')),
    value          real        NOT NULL,
    PRIMARY KEY (equipment_id, sensor_code, sampled_at, interval_type)
) PARTITION BY LIST (interval_type);

CREATE TABLE sensor_sample_5s PARTITION OF sensor_sample FOR VALUES IN ('SEC5');
CREATE TABLE sensor_sample_1m PARTITION OF sensor_sample FOR VALUES IN ('MIN1_AVG');
CREATE INDEX ix_sensor_sample_5s_time ON sensor_sample_5s USING brin (sampled_at);
CREATE INDEX ix_sensor_sample_1m_time ON sensor_sample_1m USING brin (sampled_at);
COMMENT ON TABLE sensor_sample IS 'OP-30 센서 값 (5.C.7). 1S = 알람·병목 앞뒤 30분, 1M = 평소 1분 평균. 30일 넘게 운영하면 월별 하위 파티션으로 나눈다 (02_물리ERD 8장)';

-- ---------------------------------------------------------------------
-- 병목 기록 (5.B.6) — 다음 행까지가 한 구간. interval_end_at·planned_qty는 v_bottleneck_interval
-- actual_qty·failure_loss_qty·speed_loss_qty는 구간이 끝날 때 저장 (설계서 5.18 "계산해 저장")
-- ---------------------------------------------------------------------
CREATE TABLE bottleneck_log (
    bottleneck_log_id  bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    changed_at         timestamptz  NOT NULL UNIQUE,
    prev_process_code  varchar(5)   REFERENCES process,
    new_process_code   varchar(5)   NOT NULL REFERENCES process,
    cause_code         varchar(7)   NOT NULL CHECK (cause_code IN ('C1','C2','C3','C4','FAILURE','BASE')),
    alarm_event_id     bigint       REFERENCES alarm_event,
    actual_qty         numeric(10,2),
    failure_loss_qty   numeric(10,2),
    speed_loss_qty     numeric(10,2),
    -- 이전 줄과 공정 또는 원인이 달라야 함 (논리 ERD 5.B.6, 2026-10-13 — 기준 병목 OP-30 → OP-30 원인 ①도 한 줄)
    --   → 행끼리 비교라 CHECK가 아닌 트리거 trg_bottleneck_changed (functions/20_integrity.sql)
    -- 원인이 고장이면 알람 필수
    CONSTRAINT ck_bottleneck_failure CHECK (cause_code <> 'FAILURE' OR alarm_event_id IS NOT NULL)
);

-- ---------------------------------------------------------------------
-- 알람 관련 재고 품목 (5.C.8, 2026-10-08 팀 결정 — R-89) — 보고 순위 "같은 원인 한 줄" (DOC-07 §10.5, DOC-04 5장)
--   예: 2075 반복 알람 + 축 윤활유(CS-WLUB) 점검 기한 넘김(예방 정비 항목의 기본 소모품) + 축 윤활유 재고 부족 → 한 줄
--   사내 문서에 적힌 연결만 넣는다 (fn_seed_alarm_related_items, 근거 = 사내 문서 §)
-- ---------------------------------------------------------------------
CREATE TABLE alarm_related_item (
    alarm_code     varchar(20)  NOT NULL REFERENCES alarm_master,
    item_no        varchar(20)  NOT NULL REFERENCES inventory_item,
    relation_note  text         NOT NULL,
    source_section varchar(80)  NOT NULL,     -- 사내 문서 이름·번호·§ (R-85: 원문 출처는 쓰지 않음)
    PRIMARY KEY (alarm_code, item_no)
);
COMMENT ON TABLE alarm_related_item IS '알람 ↔ 관련 재고 품목 (같은 원인 묶기). 예방 정비 항목은 pm_task.default_item_no로 이어진다';

-- ===================== db/schema/40_tool_shipment.sql =====================
-- =====================================================================
-- 40_tool_shipment.sql — E 공구·출하 (+ B의 lot_hold)
-- 근거: 논리ERD_최종본 5.E.1~5.E.4, 5.E.7·5.E.8, 5.B.7, 6.24~6.26, 6.44·6.45
-- inventory_txn은 작업기록서·예방 정비를 가리켜서 50_maintenance.sql 끝에 둔다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 공구 종류 (5.E.1) — 공구 품목과 1:1
-- ---------------------------------------------------------------------
CREATE TABLE tool_type (
    item_no                varchar(20)   PRIMARY KEY REFERENCES inventory_item,
    usage_unit             varchar(5)    NOT NULL CHECK (usage_unit IN ('HOLES','FEED')),
    usage_per_part         numeric(8,3)  NOT NULL CHECK (usage_per_part > 0),
    life_limit             numeric(10,2) NOT NULL CHECK (life_limit > 0),
    limit_basis            text          NOT NULL,
    deduct_qty_per_change  integer       NOT NULL DEFAULT 1 CHECK (deduct_qty_per_change > 0)
);

-- ---------------------------------------------------------------------
-- 공구 (5.E.2) — VF-2에 꽂힌 공구 자리. usage_rate_pct는 v_tool_life
-- ---------------------------------------------------------------------
CREATE TABLE tool (
    tool_id          varchar(16)   PRIMARY KEY,
    equipment_id     varchar(10)   NOT NULL REFERENCES equipment,
    tool_no          varchar(3)    NOT NULL CHECK (tool_no ~ '^T[0-9]{2}$'),
    item_no          varchar(20)   NOT NULL REFERENCES tool_type,
    tool_role        varchar(6)    NOT NULL DEFAULT 'IN_USE' CHECK (tool_role IN ('IN_USE','SPARE')),
    cum_usage        numeric(12,3) NOT NULL DEFAULT 0 CHECK (cum_usage >= 0),
    last_changed_at  timestamptz,
    is_active        boolean       NOT NULL DEFAULT true,
    CONSTRAINT ux_tool_slot UNIQUE (equipment_id, tool_no),
    CONSTRAINT ck_tool_id CHECK (tool_id = equipment_id || '-' || tool_no)
);

-- ---------------------------------------------------------------------
-- 공구 교체 기록 (5.E.4)
-- ---------------------------------------------------------------------
CREATE TABLE tool_change (
    tool_change_id          bigint        GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    tool_id                 varchar(16)   NOT NULL REFERENCES tool,
    changed_at              timestamptz   NOT NULL,
    changed_by              varchar(20)   NOT NULL REFERENCES app_user,
    cum_before              numeric(12,3) NOT NULL CHECK (cum_before >= 0),
    change_reason           varchar(9)    NOT NULL CHECK (change_reason IN ('LIFE_90','ALARM_362','ALARM_174','BROKEN','OTHER')),
    related_alarm_event_id  bigint        REFERENCES alarm_event,
    CONSTRAINT ux_tool_change_time UNIQUE (tool_id, changed_at)
);

-- ---------------------------------------------------------------------
-- 공구 사용 기록 (5.E.3) — [제안] 공정 실적 + 교체로 구간을 나눔 (B안)
-- 한 공정 실적 도중 공구를 바꾸면 seg 1 (교체 전) / seg 2 (교체 후, tool_change_id)로 나눈다.
-- ---------------------------------------------------------------------
CREATE TABLE tool_usage (
    tool_id         varchar(16)   NOT NULL REFERENCES tool,
    op_report_id    bigint        NOT NULL REFERENCES operation_report,
    seg             smallint      NOT NULL DEFAULT 1 CHECK (seg >= 1),
    parts_qty       integer       NOT NULL CHECK (parts_qty > 0),
    usage_qty       numeric(12,3) NOT NULL CHECK (usage_qty > 0),
    cum_after       numeric(12,3) NOT NULL CHECK (cum_after >= 0),
    tool_change_id  bigint        REFERENCES tool_change,
    recorded_at     timestamptz   NOT NULL,
    PRIMARY KEY (tool_id, op_report_id, seg),
    -- 두 번째 구간부터는 그 구간을 연 교체 기록이 있어야 한다
    CONSTRAINT ck_tool_usage_seg CHECK (seg = 1 OR tool_change_id IS NOT NULL)
);
CREATE INDEX ix_tool_usage_op_report ON tool_usage (op_report_id);

-- ---------------------------------------------------------------------
-- 로트 보류 기록 (5.B.7) — 사람 결정(누가·언제·왜). 역할 확인은 트리거
-- result 코드 [제안]: OPEN 진행 중 / RELEASED 해제 / SCRAPPED 폐기
-- ---------------------------------------------------------------------
CREATE TABLE lot_hold (
    hold_id                 bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    lot_no                  varchar(20) NOT NULL REFERENCES production_lot,
    trigger_type            varchar(15) NOT NULL CHECK (trigger_type IN ('AI_SUSPECT','INSPECTION_FAIL','SUPERVISOR')),
    related_alarm_event_id  bigint      REFERENCES alarm_event,
    related_tool_id         varchar(16) REFERENCES tool,
    hold_reason             text        NOT NULL CHECK (btrim(hold_reason) <> ''),
    held_by                 varchar(20) NOT NULL REFERENCES app_user,
    held_at                 timestamptz NOT NULL,
    enhanced_next_lots      smallint    NOT NULL CHECK (enhanced_next_lots IN (1,2)),
    released_by             varchar(20) REFERENCES app_user,
    released_at             timestamptz,
    released_pass_qty       integer     CHECK (released_pass_qty >= 0),   -- 물리 추가: 해제 때 고른 합격 수량 (R-69 ②)
    scrap_proposed_qty      integer     CHECK (scrap_proposed_qty >= 0),
    scrap_proposed_by       varchar(20) REFERENCES app_user,
    scrap_approved_by       varchar(20) REFERENCES app_user,
    scrap_approved_at       timestamptz,
    normal_resumed_by       varchar(20) REFERENCES app_user,
    normal_resumed_at       timestamptz,
    result                  varchar(11) NOT NULL DEFAULT 'IN_PROGRESS' CHECK (result IN ('IN_PROGRESS','RELEASED','SCRAPPED')),
    CONSTRAINT ck_lot_hold_release CHECK (result <> 'RELEASED' OR (released_by IS NOT NULL AND released_at IS NOT NULL)),
    CONSTRAINT ck_lot_hold_scrap CHECK (result <> 'SCRAPPED' OR (scrap_approved_by IS NOT NULL AND scrap_approved_at IS NOT NULL)),
    CONSTRAINT ck_lot_hold_release_pair CHECK ((released_by IS NULL) = (released_at IS NULL)),
    CONSTRAINT ck_lot_hold_resume_pair CHECK ((normal_resumed_by IS NULL) = (normal_resumed_at IS NULL)),
    CONSTRAINT ck_lot_hold_time CHECK (released_at IS NULL OR released_at >= held_at)
);
-- 한 로트에 열린 보류는 하나
CREATE UNIQUE INDEX ux_lot_hold_open ON lot_hold (lot_no) WHERE result = 'IN_PROGRESS';
COMMENT ON COLUMN lot_hold.released_pass_qty IS '물리 추가: 해제 때 전수 검사로 고른 합격 수량. 이만큼만 완제품 입고 (R-69, 6.8 RELEASED)';

-- ---------------------------------------------------------------------
-- 출하 (5.E.7) · 출하 내역 (5.E.8)
-- 확정은 fn_confirm_shipment()만 한다 (R-67 합격 로트만·R-68 FIFO·출하 출고 거래)
-- ---------------------------------------------------------------------
CREATE TABLE shipment (
    shipment_no       varchar(12) PRIMARY KEY CHECK (shipment_no ~ '^SHP-[0-9]{4}-[0-9]{3}$'),
    shipped_at        timestamptz,
    customer_code     varchar(8)  NOT NULL CHECK (customer_code ~ '^CUST-[0-9]{2}$'),
    due_date          date        NOT NULL,
    confirmed_by      varchar(20) REFERENCES app_user,
    status            varchar(9)  NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','CONFIRMED','REVISED')),
    fifo_skip_reason  text,
    memo              text,
    current_version   integer     NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    -- 계산 (5.E.7 is_late): 출하 날짜 > 납기일
    is_late           boolean     GENERATED ALWAYS AS ((shipped_at AT TIME ZONE 'Asia/Seoul')::date > due_date) STORED,
    CONSTRAINT ck_shipment_confirmed CHECK (status = 'DRAFT' OR (confirmed_by IS NOT NULL AND shipped_at IS NOT NULL))
);
CREATE INDEX ix_shipment_shipped ON shipment (shipped_at);

CREATE TABLE shipment_line (
    shipment_no    varchar(12) NOT NULL REFERENCES shipment ON DELETE CASCADE,  -- 작성 중(DRAFT) 출하를 지울 때만
    lot_no         varchar(20) NOT NULL REFERENCES production_lot,
    qty            integer     NOT NULL CHECK (qty >= 1),
    lot_passed_at  timestamptz NOT NULL,
    PRIMARY KEY (shipment_no, lot_no)
);
CREATE INDEX ix_shipment_line_lot ON shipment_line (lot_no);

-- ===================== db/schema/50_maintenance.sql =====================
-- =====================================================================
-- 50_maintenance.sql — D 정비 (+ C의 equipment_state_log, E의 inventory_txn)
-- 근거: 논리ERD_최종본 5.D, 5.C.4, 5.E.6, 6.13~6.15, 6.19~6.23, 6.28, 6.42
--       R-01~R-04, R-21~R-23, R-31a~R-34, R-41·R-42, R-55, R-69, R-71
-- 업무 번호 (논리 ERD 5.D.1·5.D.4, 설계서 5.11): 작업지시서 MW-0901, 작업기록서 MR-0901, 간이 MR-S-0901 (월 + 두 자리)
--   (문서의 MW-0901 형식은 연도가 없어 15년 보관 때 번호가 겹친다 → 05_결정기록 D-01)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 예방 정비 항목 (5.D.7) — next_due_date는 v_pm_task_due
-- ---------------------------------------------------------------------
CREATE TABLE pm_task (
    pm_task_id       varchar(30)  PRIMARY KEY,
    equipment_id     varchar(10)  NOT NULL REFERENCES equipment,
    doc04_section    varchar(10)  NOT NULL,
    area             varchar(40),
    item_name        varchar(120) NOT NULL,
    cycle_code       varchar(12)  NOT NULL CHECK (cycle_code IN
                     ('DAILY','WEEKLY','MONTHLY','HALF_YEAR','YEARLY','AS_REQUIRED','EVERY_8H_USE')),
    lockout_level    varchar(9)   NOT NULL CHECK (lockout_level IN ('FULL','TWO_POINT','ONE_POINT','UNPLUG','NONE')),
    default_role     varchar(3)   NOT NULL CHECK (default_role IN ('OPR','MNT')),
    default_item_no  varchar(20)  REFERENCES inventory_item,
    on_calendar      boolean      NOT NULL DEFAULT true,
    source_tag       varchar(9)   NOT NULL CHECK (source_tag IN ('REAL','REFERENCE','VIRTUAL')),
    is_active        boolean      NOT NULL DEFAULT true,
    -- PM-{설비 ID}-{DOC-04 절}-{두 자리 순번} (5.D.7 [가상] 팀 확정)
    CONSTRAINT ck_pm_task_id CHECK (pm_task_id LIKE 'PM-' || equipment_id || '-' || doc04_section || '-__')
);

-- ---------------------------------------------------------------------
-- 예방 정비 실시 기록 (5.D.8) — 수정 이력 대상 (PM_RECORD)
-- status 코드 (논리 ERD 5.D.8, 2026-10-13): DRAFT 작성 중 / CONFIRMED 확정 — 확정 뒤 고치면 새 버전 + 사유, 상태는 CONFIRMED 그대로 (R-35)
-- ---------------------------------------------------------------------
CREATE TABLE pm_record (
    pm_record_id     bigint        GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    pm_task_id       varchar(30)   NOT NULL REFERENCES pm_task,
    due_date         date          NOT NULL,
    done_at          timestamptz   NOT NULL,
    done_by          varchar(20)   NOT NULL REFERENCES app_user,
    recorded_by      varchar(20)   NOT NULL REFERENCES app_user,
    result           varchar(8)    NOT NULL CHECK (result IN ('NORMAL','REFILLED','ABNORMAL')),
    measured_value   numeric(12,3),
    measured_unit    varchar(10),
    memo             text,
    status           varchar(9)    NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','CONFIRMED')),
    current_version  integer       NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    -- 계산 (5.D.8 is_on_time): 실시일 ≤ 예정일 (한국 시간 날짜)
    is_on_time       boolean       GENERATED ALWAYS AS ((done_at AT TIME ZONE 'Asia/Seoul')::date <= due_date) STORED,
    CONSTRAINT ck_pm_record_unit CHECK (measured_value IS NULL OR measured_unit IS NOT NULL)
);
CREATE INDEX ix_pm_record_task ON pm_record (pm_task_id, done_at);

-- ---------------------------------------------------------------------
-- 설비 상태 기록 (5.C.4) — 구간. L3 (2년)
-- ---------------------------------------------------------------------
CREATE TABLE equipment_state_log (
    state_log_id           bigint        GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    equipment_id           varchar(10)   NOT NULL REFERENCES equipment,
    state_code             varchar(7)    NOT NULL CHECK (state_code IN ('RUN','IDLE','BLOCKED','SETUP','DOWN','MAINT')),
    mtconnect_execution    varchar(7)    CHECK (mtconnect_execution IN ('ACTIVE','READY','STOPPED')),
    start_at               timestamptz   NOT NULL,
    end_at                 timestamptz,
    -- 계산 (5.C.4 duration_min): 끝 − 시작 (분). 지금 구간이면 비움
    duration_min           numeric(10,2) GENERATED ALWAYS AS (round(extract(epoch FROM (end_at - start_at)) / 60, 2)) STORED,
    warn_marker            boolean       NOT NULL DEFAULT false,
    reason_suggested_code  varchar(3)    REFERENCES downtime_reason,
    reason_code            varchar(3)    REFERENCES downtime_reason,
    reason_status          varchar(9)    CHECK (reason_status IN ('SUGGESTED','ENTERED','CONFIRMED')),
    reason_entered_by      varchar(20)   REFERENCES app_user,
    reason_confirmed_by    varchar(20)   REFERENCES app_user,
    reason_confirmed_at    timestamptz,
    -- 알람 1건 = DOWN 1구간 (논리 ERD 5.C.4 UK). 주의 등급으로 멈춘 IDLE은 휴식 시간을 끼면 두 구간으로 나뉘어
    -- 같은 알람을 가리킬 수 있다 (생성기 9월 기록 8건) → 고유는 DOWN 구간에만 (ux_state_log_alarm_down)
    alarm_event_id         bigint        REFERENCES alarm_event,
    pm_record_id           bigint        UNIQUE REFERENCES pm_record,
    stop_loss_qty          numeric(10,2),     -- 설계서 5.10 "계산해 저장": 구간이 끝날 때 채움
    CONSTRAINT ck_state_time CHECK (end_at IS NULL OR end_at > start_at),
    -- R-04 한 설비의 구간은 겹치지 않는다 (지금 구간은 끝을 무한대로 본다)
    CONSTRAINT ex_state_no_overlap EXCLUDE USING gist (
        equipment_id WITH =,
        tstzrange(start_at, coalesce(end_at, 'infinity'::timestamptz), '[)') WITH &&),
    -- SETUP·MAINT는 실제 데이터 값이 없다 (6.2)
    CONSTRAINT ck_state_mtconnect CHECK (state_code NOT IN ('SETUP','MAINT') OR mtconnect_execution IS NULL),
    -- R-21 RUN이면 정지 사유를 비운다
    CONSTRAINT ck_state_run_reason CHECK (state_code <> 'RUN' OR
        (reason_code IS NULL AND reason_status IS NULL AND reason_suggested_code IS NULL)),
    -- R-21 사유 확정은 사유·확정자·확정 시각이 함께 (확정자 = SUP는 트리거)
    CONSTRAINT ck_state_reason_confirmed CHECK (reason_status IS DISTINCT FROM 'CONFIRMED' OR
        (reason_code IS NOT NULL AND reason_confirmed_by IS NOT NULL AND reason_confirmed_at IS NOT NULL)),
    -- R-01 DOWN 구간은 정지 등급 알람 1건을 가리킨다 (등급 확인은 트리거)
    CONSTRAINT ck_state_down_alarm CHECK (state_code <> 'DOWN' OR alarm_event_id IS NOT NULL),
    -- R-23 MAINT 구간은 예방 정비 기록을 가리킨다. 단 반복 알람 2단계 원인 점검 MAINT는 비움 — 그 시간은 작업기록서가 가진다
    -- (논리 ERD 5.C.4, 2026-10-13). 행 하나로는 가를 수 없어 적재 점검(validate_loaded_data.sql #19)이 확인한다
    CONSTRAINT ck_state_maint_pm CHECK (state_code = 'MAINT' OR pm_record_id IS NULL)
);
CREATE UNIQUE INDEX ux_state_log_alarm_down ON equipment_state_log (alarm_event_id) WHERE state_code = 'DOWN';
CREATE INDEX ix_state_equipment_time ON equipment_state_log (equipment_id, start_at);
CREATE INDEX ix_state_open ON equipment_state_log (equipment_id) WHERE end_at IS NULL;
-- 사유 미입력 N건 (SCR-14)
CREATE INDEX ix_state_reason_pending ON equipment_state_log (start_at)
    WHERE state_code <> 'RUN' AND (reason_status IS NULL OR reason_status <> 'CONFIRMED');

-- ---------------------------------------------------------------------
-- 정비 작업지시서 (5.D.1) — OP-30만 (트리거)
-- trigger_kind(여러 값)는 따로 저장하지 않는다: 계기 FK 세 칸 중 채워진 칸이 곧 계기다
--   alarm_event_id → STOP_ALARM, trigger_notification_id → REPEAT_STAGE2, pm_record_id → PM_ABNORMAL
--   (v_work_order.trigger_kinds 로 보인다 — 02_물리ERD 5장)
-- trigger_notification_id FK는 notification이 생긴 뒤 95_deferred_fks.sql에서 건다
-- ---------------------------------------------------------------------
CREATE TABLE maintenance_work_order (
    wo_no                    varchar(12)  PRIMARY KEY CHECK (wo_no ~ '^MW-[0-9]{4,5}$'),
    alarm_event_id           bigint       UNIQUE REFERENCES alarm_event,
    pm_record_id             bigint       UNIQUE REFERENCES pm_record,
    trigger_notification_id  bigint       UNIQUE,
    equipment_id             varchar(10)  NOT NULL REFERENCES equipment,
    lot_no                   varchar(20)  REFERENCES production_lot,
    created_at               timestamptz  NOT NULL,
    title                    varchar(200) NOT NULL,
    symptom                  text         NOT NULL,
    status                   varchar(11)  NOT NULL DEFAULT 'AI_DRAFT' CHECK (status IN
                             ('AI_DRAFT','EDITING','APPROVED','IN_PROGRESS','DONE','CANCELLED')),
    assignee_user_id         varchar(20)  REFERENCES app_user,
    approved_by              varchar(20)  REFERENCES app_user,
    approved_at              timestamptz,
    cancelled_by             varchar(20)  REFERENCES app_user,
    cancelled_at             timestamptz,
    cancel_reason            text,
    safety_block_doc_rev     varchar(20)  NOT NULL,
    has_high_voltage_notice  boolean      NOT NULL,
    completed_at             timestamptz,
    current_version          integer      NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    -- 계기는 1개 이상 (6.42)
    CONSTRAINT ck_wo_trigger CHECK (num_nonnulls(alarm_event_id, pm_record_id, trigger_notification_id) >= 1),
    -- R-31a 승인 뒤 단계는 담당자·승인자·승인 시각이 있어야 한다
    CONSTRAINT ck_wo_approved CHECK (status NOT IN ('APPROVED','IN_PROGRESS','DONE') OR
        (assignee_user_id IS NOT NULL AND approved_by IS NOT NULL AND approved_at IS NOT NULL)),
    CONSTRAINT ck_wo_cancel CHECK (status <> 'CANCELLED' OR
        (cancelled_by IS NOT NULL AND cancelled_at IS NOT NULL AND btrim(coalesce(cancel_reason, '')) <> '')),
    CONSTRAINT ck_wo_done CHECK (status <> 'DONE' OR completed_at IS NOT NULL)
);
CREATE INDEX ix_wo_equipment ON maintenance_work_order (equipment_id, created_at);
CREATE INDEX ix_wo_status ON maintenance_work_order (status);

CREATE TABLE work_order_step (
    wo_no           varchar(12) NOT NULL REFERENCES maintenance_work_order ON DELETE CASCADE,
    step_no         smallint    NOT NULL CHECK (step_no > 0),
    step_text       text        NOT NULL,
    source_section  varchar(40) NOT NULL,   -- "DOC-03 §2.1" — 원문 출처는 넣지 않는다 (R-85)
    PRIMARY KEY (wo_no, step_no)
);

CREATE TABLE work_order_part (
    wo_no          varchar(12)   NOT NULL REFERENCES maintenance_work_order ON DELETE CASCADE,
    item_no        varchar(20)   NOT NULL REFERENCES inventory_item,
    suggested_qty  numeric(12,3) NOT NULL CHECK (suggested_qty > 0),
    PRIMARY KEY (wo_no, item_no)
);

-- ---------------------------------------------------------------------
-- 작업기록서 (5.D.4) — FULL 작업기록서 / SIMPLE 간이 작업기록
-- cause_check_notification_id FK는 95_deferred_fks.sql
-- ---------------------------------------------------------------------
CREATE TABLE work_record (
    record_no                    varchar(14)   PRIMARY KEY,
    record_type                  varchar(6)    NOT NULL CHECK (record_type IN ('FULL','SIMPLE')),
    wo_no                        varchar(12)   UNIQUE REFERENCES maintenance_work_order,
    alarm_event_id               bigint        UNIQUE REFERENCES alarm_event,
    cause_check_notification_id  bigint        UNIQUE,
    equipment_id                 varchar(10)   NOT NULL REFERENCES equipment,
    lot_no                       varchar(20)   REFERENCES production_lot,
    cause                        text,
    action                       text          NOT NULL,
    worker_memo                  text,
    start_at                     timestamptz   NOT NULL,
    end_at                       timestamptz,
    repair_min                   numeric(8,2)  CHECK (repair_min >= 0),
    safety_block_required        boolean       NOT NULL,
    status                       varchar(9)    NOT NULL CHECK (status IN ('AI_DRAFT','EDITING','CONFIRMED','CHECKED')),
    confirmed_by                 varchar(20)   REFERENCES app_user,
    confirmed_at                 timestamptz,
    checked_by                   varchar(20)   REFERENCES app_user,
    checked_at                   timestamptz,
    current_version              integer       NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    -- 번호 형식은 종류를 따른다
    CONSTRAINT ck_work_record_no CHECK (
        (record_type = 'FULL'   AND record_no ~ '^MR-[0-9]{4,5}$') OR
        (record_type = 'SIMPLE' AND record_no ~ '^MR-S-[0-9]{4,5}$')),
    -- 작업기록서는 작업지시서 1건과 짝, 간이는 작업지시서가 없다
    CONSTRAINT ck_work_record_wo CHECK ((record_type = 'FULL') = (wo_no IS NOT NULL)),
    -- 간이는 알람 1건 또는 원인 점검 요청 1건 중 하나에 딸린다
    CONSTRAINT ck_work_record_simple_src CHECK (record_type <> 'SIMPLE' OR
        num_nonnulls(alarm_event_id, cause_check_notification_id) = 1),
    -- 간이에는 AI비서 초안·확인(CHECKED) 단계가 없다 (6.15)
    CONSTRAINT ck_work_record_simple_status CHECK (record_type <> 'SIMPLE' OR status IN ('EDITING','CONFIRMED')),
    CONSTRAINT ck_work_record_confirmed CHECK (status NOT IN ('CONFIRMED','CHECKED') OR
        (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND end_at IS NOT NULL)),
    -- 작업기록서 확정 때 원인 필수 (5.D.4 cause)
    CONSTRAINT ck_work_record_cause CHECK (record_type <> 'FULL' OR status NOT IN ('CONFIRMED','CHECKED') OR
        btrim(coalesce(cause, '')) <> ''),
    CONSTRAINT ck_work_record_checked CHECK (status <> 'CHECKED' OR (checked_by IS NOT NULL AND checked_at IS NOT NULL)),
    CONSTRAINT ck_work_record_time CHECK (end_at IS NULL OR end_at >= start_at)
);
CREATE INDEX ix_work_record_equipment ON work_record (equipment_id, start_at);

CREATE TABLE work_record_check (
    record_no       varchar(14) NOT NULL REFERENCES work_record ON DELETE CASCADE,
    check_seq       smallint    NOT NULL CHECK (check_seq > 0),
    check_kind      varchar(4)  NOT NULL CHECK (check_kind IN ('STEP','LOTO')),
    wo_no           varchar(12),
    step_no         smallint,
    loto_step_code  varchar(3)  CHECK (loto_step_code IN ('6.1','6.2','6.3','6.4','6.5','6.6','7.1','7.2','7.3')),
    is_checked      boolean     NOT NULL DEFAULT false,
    checked_by      varchar(20) REFERENCES app_user,
    checked_at      timestamptz,
    PRIMARY KEY (record_no, check_seq),
    CONSTRAINT fk_work_record_check_step FOREIGN KEY (wo_no, step_no) REFERENCES work_order_step (wo_no, step_no),
    CONSTRAINT ck_work_record_check_step CHECK (check_kind <> 'STEP' OR (wo_no IS NOT NULL AND step_no IS NOT NULL)),
    CONSTRAINT ck_work_record_check_loto CHECK ((check_kind = 'LOTO') = (loto_step_code IS NOT NULL)),
    CONSTRAINT ck_work_record_check_by CHECK (NOT is_checked OR (checked_by IS NOT NULL AND checked_at IS NOT NULL))
);
-- 한 기록에 잠금·표지 단계마다 1행 (5.D.5)
CREATE UNIQUE INDEX ux_work_record_check_loto ON work_record_check (record_no, loto_step_code)
    WHERE loto_step_code IS NOT NULL;

CREATE TABLE work_record_part (
    record_no         varchar(14)   NOT NULL REFERENCES work_record ON DELETE CASCADE,
    item_no           varchar(20)   NOT NULL REFERENCES inventory_item,
    qty               numeric(12,3) NOT NULL CHECK (qty > 0),
    proposed_by_kind  varchar(5)    NOT NULL CHECK (proposed_by_kind IN ('AI','HUMAN')),
    PRIMARY KEY (record_no, item_no)
);

-- ---------------------------------------------------------------------
-- 입출고 거래 (5.E.6) — 수불대장. 추가만 한다 (고치기·지우기 금지 트리거)
-- 거래가 들어오면 트리거가 inventory_item.on_hand_qty를 바꾸고, 음수면 막힌다 (R-11)
-- ---------------------------------------------------------------------
CREATE TABLE inventory_txn (
    txn_id               bigint        GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    item_no              varchar(20)   NOT NULL REFERENCES inventory_item,
    txn_type             varchar(8)    NOT NULL CHECK (txn_type IN ('IN','USE','ADJUST','FG_IN','SHIP_OUT')),
    qty_change           numeric(12,3) NOT NULL CHECK (qty_change <> 0),
    txn_at               timestamptz   NOT NULL,
    txn_by               varchar(20)   REFERENCES app_user,
    source_kind          varchar(16)   NOT NULL CHECK (source_kind IN
                         ('RECEIPT','MATERIAL_RECEIPT','LOT_PASS','SHIPMENT','WORK_RECORD',
                          'PM_RECORD','TOOL_CHANGE','LOT_INPUT','STOCKTAKE')),
    work_record_no       varchar(14),
    work_record_item_no  varchar(20),
    pm_record_id         bigint        REFERENCES pm_record,
    tool_change_id       bigint        REFERENCES tool_change,
    lot_no               varchar(20)   REFERENCES production_lot,
    material_lot_no      varchar(16)   REFERENCES raw_material_lot,
    fg_lot_no            varchar(20)   REFERENCES production_lot,
    shipment_no          varchar(12),
    ship_lot_no          varchar(20),
    memo                 text,
    CONSTRAINT fk_inventory_txn_work_record_part FOREIGN KEY (work_record_no, work_record_item_no)
        REFERENCES work_record_part (record_no, item_no),
    CONSTRAINT fk_inventory_txn_shipment_line FOREIGN KEY (shipment_no, ship_lot_no)
        REFERENCES shipment_line (shipment_no, lot_no),
    -- 부호: 입고·합격 입고 +, 사용·출하 출고 −, 조정 ±
    CONSTRAINT ck_inventory_txn_sign CHECK (
        (txn_type IN ('IN','FG_IN') AND qty_change > 0) OR
        (txn_type IN ('USE','SHIP_OUT') AND qty_change < 0) OR
        txn_type = 'ADJUST'),
    -- 조정은 사유 필수 (6.28 STOCKTAKE)
    CONSTRAINT ck_inventory_txn_adjust_memo CHECK (txn_type <> 'ADJUST' OR btrim(coalesce(memo, '')) <> ''),
    -- 출처 종류 ↔ 거래 종류
    CONSTRAINT ck_inventory_txn_kind_type CHECK (
        (source_kind IN ('RECEIPT','MATERIAL_RECEIPT') AND txn_type = 'IN') OR
        (source_kind = 'LOT_PASS' AND txn_type = 'FG_IN') OR
        (source_kind = 'SHIPMENT' AND txn_type IN ('SHIP_OUT','ADJUST')) OR
        (source_kind IN ('WORK_RECORD','PM_RECORD','TOOL_CHANGE','LOT_INPUT') AND txn_type = 'USE') OR
        (source_kind = 'STOCKTAKE' AND txn_type = 'ADJUST')),
    -- R-55 거래는 출처 기록을 정확히 하나 가리킨다 (입고 등록·월말 실사는 없음, 완제품 실사는 로트 선택)
    CONSTRAINT ck_inventory_txn_source CHECK (CASE source_kind
        WHEN 'RECEIPT'          THEN num_nonnulls(work_record_no, pm_record_id, tool_change_id, lot_no, material_lot_no, fg_lot_no, shipment_no) = 0
        WHEN 'STOCKTAKE'        THEN num_nonnulls(work_record_no, pm_record_id, tool_change_id, lot_no, material_lot_no, shipment_no) = 0
        WHEN 'MATERIAL_RECEIPT' THEN material_lot_no IS NOT NULL AND num_nonnulls(work_record_no, pm_record_id, tool_change_id, lot_no, fg_lot_no, shipment_no) = 0
        WHEN 'LOT_INPUT'        THEN lot_no IS NOT NULL AND num_nonnulls(work_record_no, pm_record_id, tool_change_id, material_lot_no, fg_lot_no, shipment_no) = 0
        WHEN 'LOT_PASS'         THEN fg_lot_no IS NOT NULL AND num_nonnulls(work_record_no, pm_record_id, tool_change_id, lot_no, material_lot_no, shipment_no) = 0
        WHEN 'SHIPMENT'         THEN shipment_no IS NOT NULL AND ship_lot_no IS NOT NULL AND num_nonnulls(work_record_no, pm_record_id, tool_change_id, lot_no, material_lot_no, fg_lot_no) = 0
        WHEN 'WORK_RECORD'      THEN work_record_no IS NOT NULL AND work_record_item_no = item_no AND num_nonnulls(pm_record_id, tool_change_id, lot_no, material_lot_no, fg_lot_no, shipment_no) = 0
        WHEN 'PM_RECORD'        THEN pm_record_id IS NOT NULL AND num_nonnulls(work_record_no, tool_change_id, lot_no, material_lot_no, fg_lot_no, shipment_no) = 0
        WHEN 'TOOL_CHANGE'      THEN tool_change_id IS NOT NULL AND num_nonnulls(work_record_no, pm_record_id, lot_no, material_lot_no, fg_lot_no, shipment_no) = 0
    END)
);
-- 출처 1건에 거래 1건 (R-41·R-42·R-69, 5.E.6)
CREATE UNIQUE INDEX ux_inventory_txn_tool_change ON inventory_txn (tool_change_id) WHERE tool_change_id IS NOT NULL;
CREATE UNIQUE INDEX ux_inventory_txn_lot_input   ON inventory_txn (lot_no) WHERE source_kind = 'LOT_INPUT';
CREATE UNIQUE INDEX ux_inventory_txn_material    ON inventory_txn (material_lot_no) WHERE source_kind = 'MATERIAL_RECEIPT';
CREATE UNIQUE INDEX ux_inventory_txn_lot_pass    ON inventory_txn (fg_lot_no) WHERE source_kind = 'LOT_PASS';
CREATE UNIQUE INDEX ux_inventory_txn_ship_out    ON inventory_txn (shipment_no, ship_lot_no) WHERE txn_type = 'SHIP_OUT';
CREATE INDEX ix_inventory_txn_item_time ON inventory_txn (item_no, txn_at);

-- ===================== db/schema/60_quality.sql =====================
-- =====================================================================
-- 60_quality.sql — F 품질 (검사 항목·불량 코드·검사 방식·CMM 가져오기·검사 결과·불량 기록)
-- 근거: 논리ERD_최종본 5.F, 6.29~6.34, 6.46~6.48, R-09·R-25~R-31·R-78~R-82
--       DOC-06 Rev.2 §3.5·§3.6 (2026-10-07 품질 추가 2건: 측정 위치·가공 설비)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 검사 항목 (5.F.1)
-- ---------------------------------------------------------------------
CREATE TABLE inspection_item (
    product_code          varchar(20)   NOT NULL REFERENCES product,
    item_seq              smallint      NOT NULL CHECK (item_seq > 0),
    item_name             varchar(60)   NOT NULL,
    spec_text             varchar(120)  NOT NULL,
    nominal               numeric(10,4),
    lsl                   numeric(10,4),
    usl                   numeric(10,4),
    method                varchar(6)    NOT NULL CHECK (method IN ('CMM','GAUGE','VISUAL')),
    char_class            varchar(7)    NOT NULL CHECK (char_class IN ('SPECIAL','GENERAL')),
    cpk_min               numeric(4,2),
    in_sampling           boolean       NOT NULL,
    enhanced_extension    varchar(120),
    is_full_check_by_cpk  boolean       NOT NULL DEFAULT false,
    PRIMARY KEY (product_code, item_seq),
    -- 3차원 측정기 항목은 위 한계가 있어야 판정을 다시 계산할 수 있다 (평면도는 아래 한계 없음)
    CONSTRAINT ck_inspection_item_limits CHECK (method <> 'CMM' OR usl IS NOT NULL),
    CONSTRAINT ck_inspection_item_lsl_usl CHECK (lsl IS NULL OR usl IS NULL OR lsl <= usl),
    -- 게이지·육안은 Cpk 기준이 없다
    CONSTRAINT ck_inspection_item_cpk CHECK (method = 'CMM' OR cpk_min IS NULL)
);

-- ---------------------------------------------------------------------
-- 불량 코드 (5.F.2) — grade는 기본 등급, 예외는 grade_rule 글로 (예: DIM-01 "1번은 치명")
-- ---------------------------------------------------------------------
CREATE TABLE defect_code (
    defect_code     varchar(6)   PRIMARY KEY CHECK (defect_code ~ '^[A-Z]{3}-[0-9]{2}$'),
    defect_name     varchar(60)  NOT NULL,
    related_items   varchar(20)  NOT NULL,
    grade           varchar(8)   NOT NULL CHECK (grade IN ('CRITICAL','MAJOR','MINOR')),
    grade_rule      varchar(120),
    common_cause    varchar(200),             -- 비서가 불량 원인 안내에 쓰지 않는다 (FR-MNT-01-12)
    is_active       boolean      NOT NULL DEFAULT true
);

-- ---------------------------------------------------------------------
-- 검사 방식 (5.F.3) — 로트 1 : 1. planned_measure_qty는 v_production_lot
-- ---------------------------------------------------------------------
CREATE TABLE inspection_plan (
    lot_no          varchar(20) PRIMARY KEY REFERENCES production_lot,
    plan_mode       varchar(8)  NOT NULL DEFAULT 'NORMAL' CHECK (plan_mode IN ('NORMAL','ENHANCED')),
    enhance_reason  varchar(8)  CHECK (enhance_reason IN ('HOLD_LOT','NEXT_LOT')),
    hold_id         bigint      REFERENCES lot_hold,
    gauge_pass_qty  integer     CHECK (gauge_pass_qty >= 0),
    gauge_fail_qty  integer     CHECK (gauge_fail_qty >= 0),
    judgement       varchar(11) CHECK (judgement IN ('PASS','HOLD_REVIEW')),
    judged_at       timestamptz,
    -- 강화면 사유·보류 필수, 보통이면 둘 다 비움
    CONSTRAINT ck_inspection_plan_enhanced CHECK (
        (plan_mode = 'ENHANCED') = (enhance_reason IS NOT NULL) AND
        (plan_mode = 'ENHANCED') = (hold_id IS NOT NULL)),
    CONSTRAINT ck_inspection_plan_judged CHECK ((judgement IS NULL) = (judged_at IS NULL))
);

-- ---------------------------------------------------------------------
-- 측정 지시 [제안: 물리 추가] — 논리 ERD 11장 #20 "측정 지시 파일과 측정 시작 기록을 엔터티로 둘지"
-- 플랫폼이 측정기에 넘긴 지시(로트·순번·검사 방식). 결과 파일이 이것과 같아야 기록한다 (R-78, FR-QLT-01-15).
-- started_at은 결과 미수신(CMM_NO_RESULT) 판단의 시작점이다.
-- ---------------------------------------------------------------------
CREATE TABLE cmm_instruction (
    instruction_id  bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    lot_no          varchar(20) NOT NULL REFERENCES production_lot,
    part_seq        integer     NOT NULL CHECK (part_seq > 0),
    insp_kind       varchar(8)  NOT NULL CHECK (insp_kind IN ('FIRST','SAMPLE','ENHANCED')),
    enhance_reason  varchar(8)  CHECK (enhance_reason IN ('HOLD_LOT','NEXT_LOT')),
    issued_at       timestamptz NOT NULL,
    started_at      timestamptz,
    started_by      varchar(20) REFERENCES app_user,
    status          varchar(9)  NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','STARTED','DONE','CANCELLED')),
    CONSTRAINT ck_cmm_instruction_started CHECK (status NOT IN ('STARTED','DONE') OR started_at IS NOT NULL),
    CONSTRAINT ck_cmm_instruction_enhanced CHECK ((insp_kind = 'ENHANCED') = (enhance_reason IS NOT NULL))
);
-- 같은 부품·같은 검사 방식에 열린 지시는 하나
CREATE UNIQUE INDEX ux_cmm_instruction_open ON cmm_instruction (lot_no, part_seq, insp_kind)
    WHERE status IN ('ISSUED','STARTED');

-- ---------------------------------------------------------------------
-- 측정 결과 파일 가져오기 (5.F.6)
-- 물리 추가: format_version, sample_no_raw, raw_header(양식에 없는 머리 칸을 그대로 보관), instruction_id
-- ---------------------------------------------------------------------
CREATE TABLE cmm_import (
    cmm_import_id      bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    file_name          varchar(200) NOT NULL UNIQUE,
    received_at        timestamptz  NOT NULL,
    status             varchar(11)  NOT NULL CHECK (status IN ('SUCCESS','FAILED','NEEDS_CHECK')),
    error_kind         varchar(12)  CHECK (error_kind IN ('FORMAT','LOT_MISMATCH','INCOMPLETE')),
    error_text         text,
    original_file_ref  varchar(300) NOT NULL,   -- "처리됨"/"오류" 칸의 위치. 원본은 지우지 않는다 (R-80)
    instrument_id      varchar(10)  REFERENCES equipment,
    lot_no             varchar(20)  REFERENCES production_lot,
    part_seq           integer      CHECK (part_seq > 0),
    insp_kind          varchar(8)   CHECK (insp_kind IN ('FIRST','SAMPLE','ENHANCED')),
    program_name_rev   varchar(60),
    measure_start_at   timestamptz,
    measure_end_at     timestamptz,
    machine_temp_c     numeric(5,2),
    temp_comp_on       boolean,
    -- 물리 추가
    format_version     varchar(40),
    sample_no_raw      varchar(10),
    raw_header         jsonb,
    instruction_id     bigint       REFERENCES cmm_instruction,
    -- 실패·확인 필요면 오류 종류와 내용 필수 (6.48). 성공이면 오류 칸을 비운다
    CONSTRAINT ck_cmm_import_error CHECK (
        (status = 'SUCCESS' AND error_kind IS NULL) OR
        (status <> 'SUCCESS' AND error_kind IS NOT NULL AND btrim(coalesce(error_text,'')) <> '')),
    CONSTRAINT ck_cmm_import_time CHECK (measure_end_at IS NULL OR measure_start_at IS NULL OR measure_end_at >= measure_start_at)
);
CREATE INDEX ix_cmm_import_received ON cmm_import (received_at);
CREATE INDEX ix_cmm_import_problem ON cmm_import (received_at) WHERE status <> 'SUCCESS';

-- ---------------------------------------------------------------------
-- 검사 결과 (5.F.4) — 측정한 부품만 (R-26). 측정값은 지우지 않는다 (R-75)
-- position (논리 ERD 5.F.4, 2026-10-14): 빈칸(NULL) = 표준 위치, TOP 위 / MID 중간 / BOTTOM 아래 (강화 때 부싱 구멍 3단).
--   UNIQUE는 NULLS NOT DISTINCT (PostgreSQL 15+) — NULL끼리도 같은 값으로 보아 같은 행이 두 번 들어오지 않는다.
-- machined_equipment_id([제안] P-11 — 논리 ERD 규칙 번호 없음)는 저장하지 않고 v_inspection_result 에서 로트의 OP-30 실적으로 계산한다:
--   측정하는 순간에는 로트의 나머지 부품이 아직 다른 설비에서 가공 중일 수 있어, 저장값이 나중에 틀린다.
-- ---------------------------------------------------------------------
CREATE TABLE inspection_result (
    result_id              bigint        GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    lot_no                 varchar(20)   NOT NULL REFERENCES production_lot,
    part_seq               integer       NOT NULL CHECK (part_seq > 0),
    product_code           varchar(20)   NOT NULL,
    item_seq               smallint      NOT NULL,
    insp_kind              varchar(8)    NOT NULL CHECK (insp_kind IN ('FIRST','SAMPLE','ENHANCED')),
    position               varchar(6)    CHECK (position IN ('TOP','MID','BOTTOM')),
    measured_value         numeric(10,4),
    judgement              varchar(4)    NOT NULL CHECK (judgement IN ('PASS','FAIL')),
    instrument_id          varchar(10)   NOT NULL REFERENCES equipment,
    inspector_id           varchar(20)   NOT NULL REFERENCES app_user,
    measured_at            timestamptz   NOT NULL,
    room_temp_c            numeric(5,2),
    part_temp_c            numeric(5,2),
    temp_comp_used         boolean,
    input_method           varchar(8)    NOT NULL CHECK (input_method IN ('CMM_AUTO','TABLET','MANUAL')),
    cmm_import_id          bigint        REFERENCES cmm_import,
    cmm_judgement          varchar(4)    CHECK (cmm_judgement IN ('PASS','FAIL')),
    -- 계산 (R-79): 측정기 판정 ≠ 플랫폼 판정
    is_judgement_mismatch  boolean       GENERATED ALWAYS AS (cmm_judgement IS NOT NULL AND cmm_judgement <> judgement) STORED,
    -- 계산 (R-82): 부품 온도가 16~26 ℃ 밖 (DOC-06 §6)
    is_temp_flag           boolean       GENERATED ALWAYS AS (part_temp_c IS NOT NULL AND (part_temp_c < 16 OR part_temp_c > 26)) STORED,
    check_status           varchar(11)   NOT NULL DEFAULT 'NORMAL' CHECK (check_status IN ('NORMAL','NEEDS_CHECK','CHECKED')),
    checked_by             varchar(20)   REFERENCES app_user,
    checked_at             timestamptz,
    remeasure_seq          smallint      NOT NULL DEFAULT 1 CHECK (remeasure_seq >= 1),
    use_for_judgement      boolean       NOT NULL,
    entered_by             varchar(20)   REFERENCES app_user,
    CONSTRAINT fk_inspection_result_item FOREIGN KEY (product_code, item_seq) REFERENCES inspection_item,
    CONSTRAINT ux_inspection_result UNIQUE NULLS NOT DISTINCT (lot_no, part_seq, item_seq, insp_kind, position, remeasure_seq),
    -- 3차원 측정기(자동·수동) 값은 측정값이 있어야 한다. 태블릿(게이지·외관)은 측정값 없음
    CONSTRAINT ck_inspection_result_value CHECK ((input_method = 'TABLET') = (measured_value IS NULL)),
    -- 자동 입력이면 가져오기 기록·측정기 판정·부품 온도 필수 (R-78·R-82)
    CONSTRAINT ck_inspection_result_auto CHECK ((input_method = 'CMM_AUTO') = (cmm_import_id IS NOT NULL)),
    CONSTRAINT ck_inspection_result_auto_fields CHECK (input_method <> 'CMM_AUTO' OR
        (cmm_judgement IS NOT NULL AND part_temp_c IS NOT NULL)),
    -- 수동 입력은 입력자를 남기고 "확인 필요"에서 시작 (R-81)
    CONSTRAINT ck_inspection_result_manual CHECK (input_method <> 'MANUAL' OR
        (entered_by IS NOT NULL AND check_status <> 'NORMAL')),
    CONSTRAINT ck_inspection_result_checked CHECK (check_status <> 'CHECKED' OR
        (checked_by IS NOT NULL AND checked_at IS NOT NULL)),
    CONSTRAINT ck_inspection_result_checked_pair CHECK ((checked_by IS NULL) = (checked_at IS NULL))
);
-- R-81 같은 부품·항목·측정 위치에서 판정에 쓰는 값은 하나. 강화 검사의 부싱 구멍 3단(TOP·MID·BOTTOM)은 위치마다 1개씩
-- 판정에 쓴다 (생성기 2026-10-14 — 3단 모두 규격 안이어야 합격). 표준 위치(NULL)끼리도 같은 값으로 본다
CREATE UNIQUE INDEX ux_inspection_result_judgement ON inspection_result (lot_no, part_seq, item_seq, position)
    NULLS NOT DISTINCT WHERE use_for_judgement;
CREATE INDEX ix_inspection_result_cpk ON inspection_result (product_code, item_seq, measured_at)
    WHERE use_for_judgement AND measured_value IS NOT NULL;
CREATE INDEX ix_inspection_result_import ON inspection_result (cmm_import_id) WHERE cmm_import_id IS NOT NULL;
CREATE INDEX ix_inspection_result_check ON inspection_result (lot_no) WHERE check_status = 'NEEDS_CHECK';

-- ---------------------------------------------------------------------
-- 불량 기록 (5.F.5)
-- ---------------------------------------------------------------------
CREATE TABLE defect_record (
    defect_record_id  bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    lot_no            varchar(20) NOT NULL REFERENCES production_lot,
    process_code      varchar(5)  NOT NULL REFERENCES process,
    defect_code       varchar(6)  NOT NULL REFERENCES defect_code,
    qty               integer     NOT NULL CHECK (qty >= 1),
    disposition       varchar(6)  NOT NULL CHECK (disposition IN ('SCRAP','REWORK')),
    result_id         bigint      UNIQUE REFERENCES inspection_result,
    found_at          timestamptz NOT NULL,
    recorded_by       varchar(20) NOT NULL REFERENCES app_user
);
CREATE INDEX ix_defect_record_lot ON defect_record (lot_no);
CREATE INDEX ix_defect_record_time ON defect_record (found_at);

-- ===================== db/schema/70_documents.sql =====================
-- =====================================================================
-- 70_documents.sql — G 문서·AI 비서 (+ C의 alarm_guide_map)
-- 근거: 논리ERD_최종본 5.G, 5.C.2, 6.16~6.18, 6.52, R-35~R-37, R-52, R-72·R-73, R-85
-- 비서 질문·답은 저장하지 않는다 (6.53 #18). 지침카드·브리핑도 저장하지 않는다 (1.3).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 사내 문서 (5.G.5) — DOC-01~07 + 용어집
-- status 코드 [제안]: PENDING 승인 대기 / APPROVED 승인
-- ---------------------------------------------------------------------
CREATE TABLE internal_doc (
    doc_no            varchar(10)  PRIMARY KEY CHECK (doc_no ~ '^(DOC-[0-9]{2}|GLOSSARY)$'),
    doc_kind          varchar(10)  NOT NULL CHECK (doc_kind IN ('MANUAL_DOC','GLOSSARY')),
    doc_name          varchar(40)  NOT NULL,
    current_rev       varchar(10)  NOT NULL CHECK (current_rev ~ '^Rev\.[0-9]+$'),
    rev_date          date         NOT NULL,
    status            varchar(8)   NOT NULL DEFAULT 'APPROVED' CHECK (status IN ('PENDING','APPROVED')),
    approved_by       varchar(20)  REFERENCES app_user,
    approved_at       timestamptz,
    is_search_target  boolean      NOT NULL DEFAULT true,
    file_ref          varchar(200) NOT NULL,
    CONSTRAINT ck_internal_doc_kind CHECK ((doc_kind = 'GLOSSARY') = (doc_no = 'GLOSSARY')),
    CONSTRAINT ck_internal_doc_approved CHECK ((approved_by IS NULL) = (approved_at IS NULL))
);

-- ---------------------------------------------------------------------
-- 알람-고장 대응 연결 (5.C.2) — 원문 출처 칸 없음 (R-85)
-- ---------------------------------------------------------------------
CREATE TABLE alarm_guide_map (
    alarm_code  varchar(20) NOT NULL REFERENCES alarm_master,
    seq         smallint    NOT NULL CHECK (seq > 0),
    doc_no      varchar(10) NOT NULL REFERENCES internal_doc,
    section     varchar(20) NOT NULL,
    PRIMARY KEY (alarm_code, seq)
);

-- ---------------------------------------------------------------------
-- 사내 문서 조각 (5.G.6) — 검색용. 임베딩 칸은 모델을 고른 뒤 db/later/ 로 더한다
-- ---------------------------------------------------------------------
CREATE TABLE doc_chunk (
    chunk_id    bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    doc_no      varchar(10) NOT NULL REFERENCES internal_doc,
    doc_rev     varchar(10) NOT NULL,
    section     varchar(20) NOT NULL,
    chunk_text  text        NOT NULL,
    built_at    timestamptz NOT NULL
);
CREATE INDEX ix_doc_chunk_doc ON doc_chunk (doc_no, section);

-- ---------------------------------------------------------------------
-- 교대 보고서 (5.G.1) — 교대 1 : 보고서 0..1. 확정자 = 그 교대 반장 (R-36, 트리거)
-- availability_pct [제안]: OP-30 설비별 2개 값 → jsonb {"VF2-01": 81.2, "VF2-02": 77.0}
-- ---------------------------------------------------------------------
CREATE TABLE shift_report (
    shift_id          varchar(12) PRIMARY KEY REFERENCES shift,
    status            varchar(9)  NOT NULL DEFAULT 'AI_DRAFT' CHECK (status IN ('AI_DRAFT','EDITING','CONFIRMED','REVISED')),
    target_qty        integer     NOT NULL CHECK (target_qty >= 0),
    actual_qty        integer     NOT NULL CHECK (actual_qty >= 0),
    defect_qty        integer     NOT NULL CHECK (defect_qty >= 0),
    availability_pct  jsonb       NOT NULL CHECK (jsonb_typeof(availability_pct) = 'object'),
    notable_text      text        NOT NULL,
    handover_text     text        NOT NULL,
    confirmed_by      varchar(20) REFERENCES app_user,
    confirmed_at      timestamptz,
    current_version   integer     NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    CONSTRAINT ck_shift_report_confirmed CHECK (status NOT IN ('CONFIRMED','REVISED') OR
        (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- 일일 보고서 (5.G.2) — 생산일 다음 날 06:00 초안 (R-72). 확정 = MGR (트리거)
-- ---------------------------------------------------------------------
CREATE TABLE daily_report (
    work_date         date          PRIMARY KEY REFERENCES work_day,
    status            varchar(9)    NOT NULL DEFAULT 'AI_DRAFT' CHECK (status IN ('AI_DRAFT','EDITING','CONFIRMED','REVISED')),
    target_qty        integer       NOT NULL CHECK (target_qty >= 0),
    actual_qty        integer       NOT NULL CHECK (actual_qty >= 0),
    defect_qty        integer       NOT NULL CHECK (defect_qty >= 0),
    oee_pct           numeric(6,2)  NOT NULL CHECK (oee_pct >= 0),
    failure_loss_qty  numeric(10,2) NOT NULL CHECK (failure_loss_qty >= 0),
    speed_loss_qty    numeric(10,2) NOT NULL,
    issues_summary    text          NOT NULL,
    confirmed_by      varchar(20)   REFERENCES app_user,
    confirmed_at      timestamptz,
    current_version   integer       NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    CONSTRAINT ck_daily_report_confirmed CHECK (status NOT IN ('CONFIRMED','REVISED') OR
        (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- 문서 버전 (5.G.3) · 버전 변경 칸 (5.G.4) — 추가만 한다 (트리거가 고치기·지우기를 막음)
-- doc_key는 문서 종류마다 키 형식이 달라(문자·날짜·정수) FK 없이 문자로 둔다 → 서버·fn_save_revision이 확인
-- content_snapshot [제안]: jsonb (비서 출력 JSON 칸과 같은 모양)
-- ---------------------------------------------------------------------
CREATE TABLE document_revision (
    revision_id       bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    doc_type          varchar(12) NOT NULL CHECK (doc_type IN
                      ('WORK_ORDER','WORK_RECORD','SHIFT_REPORT','DAILY_REPORT','INTERNAL_DOC','PM_RECORD','SHIPMENT')),
    doc_key           varchar(30) NOT NULL,
    version_no        integer     NOT NULL CHECK (version_no >= 0),
    author_kind       varchar(5)  NOT NULL CHECK (author_kind IN ('AI','HUMAN')),
    author_user_id    varchar(20) REFERENCES app_user,
    created_at        timestamptz NOT NULL,
    reason            text,
    status_after      varchar(11) NOT NULL,
    content_snapshot  jsonb       NOT NULL,
    internal_doc_rev  varchar(10),
    CONSTRAINT ux_document_revision UNIQUE (doc_type, doc_key, version_no),
    -- 사람이면 작성자 필수, AI면 비움. AI는 v0(AI비서 초안)만 (R-35)
    CONSTRAINT ck_document_revision_author CHECK ((author_kind = 'AI') = (author_user_id IS NULL)),
    CONSTRAINT ck_document_revision_ai_v0 CHECK (author_kind <> 'AI' OR version_no = 0),
    CONSTRAINT ck_document_revision_internal CHECK (doc_type <> 'INTERNAL_DOC' OR internal_doc_rev IS NOT NULL)
);
CREATE INDEX ix_document_revision_time ON document_revision (created_at);

CREATE TABLE document_revision_change (
    revision_id   bigint      NOT NULL REFERENCES document_revision,
    field_name    varchar(60) NOT NULL,
    before_value  text,
    after_value   text,
    PRIMARY KEY (revision_id, field_name),
    CONSTRAINT ck_document_revision_change CHECK (before_value IS DISTINCT FROM after_value)
);

-- ---------------------------------------------------------------------
-- 채팅 기록 (5.G.7, 2026-10-13 팀 회의 — 관계 125). AI 비서 사이드바 채팅 탭의 질문·답 1쌍.
-- 사용자마다 따로, 본인 기록만 본다 [제안]. 질문 시각부터 30일 지나면 삭제 (6.53 #18, fn_purge_chat_log).
-- status 코드 [제안: 물리] (API-AST-02 status): OK 정상 / NOT_IN_DOCS 문서에 없음 / OUT_OF_ROLE 권한 밖 /
--   NO_RESPONSE 응답 없음 / REFUSED 거부(설비 명령 요청 등 — 따로 둘지는 [선택 필요: LLM 담당], 지금은 칸을 둠)
-- screen_context·sources 저장 형식은 [선택 필요: 기술 회의] → jsonb (화면이 보낸 그대로 / 출처 목록)
-- 시연 시작(10/1) 때 0행 (가상 과거 데이터 없음)
-- ---------------------------------------------------------------------
CREATE TABLE chat_log (
    chat_id         bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id         varchar(20)  NOT NULL REFERENCES app_user,
    asked_at        timestamptz  NOT NULL,
    screen_context  jsonb,
    question        text         NOT NULL CHECK (btrim(question) <> ''),
    answer          text,
    sources         jsonb        CHECK (sources IS NULL OR jsonb_typeof(sources) = 'array'),
    status          varchar(11)  NOT NULL CHECK (status IN ('OK','NOT_IN_DOCS','OUT_OF_ROLE','NO_RESPONSE','REFUSED')),
    -- 물리 추가: 이어서 물은 앞 질문 (API-AST-02 "이어서 물을 때 앞 chat_id" [제안])
    prev_chat_id    bigint       REFERENCES chat_log ON DELETE SET NULL,
    CONSTRAINT ck_chat_log_answer CHECK (status = 'NO_RESPONSE' OR answer IS NOT NULL)
);
CREATE INDEX ix_chat_log_user ON chat_log (user_id, asked_at DESC);
COMMENT ON TABLE chat_log IS '채팅 기록 (5.G.7). 본인 것만 보고 30일 보관 (6.53 #18, R-87). 밖으로 보내지 않음';

-- ===================== db/schema/80_notification_auth.sql =====================
-- =====================================================================
-- 80_notification_auth.sql — H 권한·알림 + 물리 추가 접속 기록
-- 근거: 논리ERD_최종본 5.H.3~5.H.6, 6.35·6.36·6.43·6.54, R-38·R-50·R-70·R-76
-- =====================================================================

-- ---------------------------------------------------------------------
-- 역할별 권한 (5.H.3) — 기획서 13.1·13.2 표를 데이터로. 서버가 이 표로 막는다 (NFR-SEC-05)
-- scope 코드 [제안]: ALL 전체 / OWN 자기 문서만 / SUMMARY 요약만 / PROXY 대리 / OWNED_ITEMS 관리 품목만
-- ---------------------------------------------------------------------
CREATE TABLE role_permission (
    role_code  varchar(3)  NOT NULL REFERENCES role,
    target     varchar(30) NOT NULL,
    action     varchar(10) NOT NULL CHECK (action IN
               ('VIEW','CREATE','EDIT','CONFIRM','APPROVE','CHECK','ASSIGN','CANCEL','INPUT','SETTING')),
    scope      varchar(11) NOT NULL DEFAULT 'ALL' CHECK (scope IN ('ALL','OWN','SUMMARY','PROXY','OWNED_ITEMS')),
    PRIMARY KEY (role_code, target, action)
);

-- ---------------------------------------------------------------------
-- 알림 규칙 (5.H.4) — 규칙이 정하고 비서는 문장만 (R-38)
-- 물리 추가 [제안] (6.36 "알림 종류별 처리"·6.43 보고 순위를 서버가 쓰도록 칸으로):
--   process_mode, processor_roles, recipient_roles, report_rank, rank_group
-- ---------------------------------------------------------------------
CREATE TABLE notification_rule (
    rule_code        varchar(20)  PRIMARY KEY,
    rule_name        varchar(60)  NOT NULL,
    condition_text   text         NOT NULL,
    importance       varchar(7)   NOT NULL CHECK (importance IN ('URGENT','CAUTION','INFO')),
    -- 전달 방식 (2026-10-13 팀 회의, 6.36 아래): POPUP 긴급 팝업(ALARM_STOP) / BUBBLE 이브 말풍선(문서 알림 6종) / LIST 목록
    delivery_kind    varchar(6)   NOT NULL DEFAULT 'LIST' CHECK (delivery_kind IN ('POPUP','BUBBLE','LIST')),
    is_enabled       boolean      NOT NULL DEFAULT true,
    updated_by       varchar(20)  REFERENCES app_user,
    updated_at       timestamptz,
    -- 물리 추가
    process_mode     varchar(6)   NOT NULL CHECK (process_mode IN ('AUTO','MANUAL','BOTH')),
    processor_roles  varchar(3)[] NOT NULL DEFAULT '{}',
    recipient_roles  varchar(3)[] NOT NULL DEFAULT '{}',
    report_rank      varchar(4)   NOT NULL CHECK (report_rank IN ('R1','R2','R3','R4')),
    rank_group       smallint     NOT NULL DEFAULT 0 CHECK (rank_group >= 0),
    CONSTRAINT ck_notification_rule_updated CHECK ((updated_by IS NULL) = (updated_at IS NULL))
);
COMMENT ON COLUMN notification_rule.report_rank IS '기본 보고 순위 (6.43). 24시간 넘게 처리 안 된 주의 알림은 v_report_items에서 R0_1로 올린다';
COMMENT ON COLUMN notification_rule.rank_group IS '순위 3 안 묶음 순서 ①~⑤ (6.43), 순위 2 안 순서';

-- ---------------------------------------------------------------------
-- 알림 (5.H.5) — L3 (2년). report_rank는 계산 (시간이 지나면 바뀌므로 저장하지 않음)
-- message_source 코드 [제안]: ASSISTANT 비서 문장 / DEFAULT 기본 문구
-- ---------------------------------------------------------------------
CREATE TABLE notification (
    notification_id             bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    rule_code                   varchar(20) NOT NULL REFERENCES notification_rule,
    importance                  varchar(7)  NOT NULL CHECK (importance IN ('URGENT','CAUTION','INFO')),
    raised_at                   timestamptz NOT NULL,
    message                     text        NOT NULL,
    related_info                text,
    message_source              varchar(9)  NOT NULL DEFAULT 'DEFAULT' CHECK (message_source IN ('ASSISTANT','DEFAULT')),
    repeat_count                integer     NOT NULL DEFAULT 1 CHECK (repeat_count >= 1),
    is_flood                    boolean     NOT NULL DEFAULT false,
    is_processed                boolean     NOT NULL DEFAULT false,
    process_kind                varchar(6)  CHECK (process_kind IN ('AUTO','MANUAL')),
    processed_by                varchar(20) REFERENCES app_user,
    process_memo                text,
    processed_at                timestamptz,
    alarm_event_id              bigint      REFERENCES alarm_event,
    equipment_id                varchar(10) REFERENCES equipment,
    lot_no                      varchar(20) REFERENCES production_lot,
    item_no                     varchar(20) REFERENCES inventory_item,
    pm_task_id                  varchar(30) REFERENCES pm_task,
    tool_id                     varchar(16) REFERENCES tool,
    wo_no                       varchar(12) REFERENCES maintenance_work_order,
    bottleneck_log_id           bigint      REFERENCES bottleneck_log,
    revision_id                 bigint      REFERENCES document_revision,
    result_id                   bigint      REFERENCES inspection_result,
    shift_id                    varchar(12) REFERENCES shift,
    buffer_code                 varchar(10) REFERENCES wip_buffer,
    cmm_import_id               bigint      REFERENCES cmm_import,
    prev_stage_notification_id  bigint      REFERENCES notification,
    repeat_stage_status         varchar(10) CHECK (repeat_stage_status IN
                                ('S1_OPEN','S1_CLOSED','S2_OPEN','S2_CHECKED','EFFECTIVE','ESCALATED')),
    effect_check_due_at         timestamptz,
    -- R-38 알림마다 관련 기록이 있어야 한다
    CONSTRAINT ck_notification_related CHECK (num_nonnulls(alarm_event_id, equipment_id, lot_no, item_no, pm_task_id,
        tool_id, wo_no, bottleneck_log_id, revision_id, result_id, shift_id, buffer_code, cmm_import_id,
        prev_stage_notification_id) >= 1),
    CONSTRAINT ck_notification_processed CHECK (is_processed = (process_kind IS NOT NULL AND processed_at IS NOT NULL)),
    CONSTRAINT ck_notification_manual CHECK (process_kind IS DISTINCT FROM 'MANUAL' OR processed_by IS NOT NULL),
    -- 반복 알람(1단계)을 사람이 처리하면 조치 계획 한 줄 필수 (6.36 처리 표)
    CONSTRAINT ck_notification_repeat_memo CHECK (rule_code <> 'REPEAT_ALARM' OR process_kind IS DISTINCT FROM 'MANUAL'
        OR btrim(coalesce(process_memo, '')) <> ''),
    -- 반복 알람 2단계·원인 점검 요청은 앞 단계 알림을 가리킨다
    CONSTRAINT ck_notification_prev_stage CHECK (rule_code NOT IN ('REPEAT_ALARM_2','CAUSE_CHECK_REQUEST')
        OR prev_stage_notification_id IS NOT NULL),
    CONSTRAINT ck_notification_stage CHECK ((rule_code IN ('REPEAT_ALARM','REPEAT_ALARM_2')) = (repeat_stage_status IS NOT NULL)),
    CONSTRAINT ck_notification_prev_self CHECK (prev_stage_notification_id IS DISTINCT FROM notification_id)
);
CREATE INDEX ix_notification_open ON notification (raised_at) WHERE NOT is_processed;
CREATE INDEX ix_notification_rule_time ON notification (rule_code, raised_at);
CREATE INDEX ix_notification_alarm ON notification (alarm_event_id) WHERE alarm_event_id IS NOT NULL;
CREATE INDEX ix_notification_equipment ON notification (equipment_id, raised_at) WHERE equipment_id IS NOT NULL;

CREATE TABLE notification_recipient (
    notification_id  bigint      NOT NULL REFERENCES notification,
    user_id          varchar(20) NOT NULL REFERENCES app_user,
    popup_sound      boolean     NOT NULL DEFAULT false,
    read_at          timestamptz,
    PRIMARY KEY (notification_id, user_id)
);
CREATE INDEX ix_notification_recipient_unread ON notification_recipient (user_id) WHERE read_at IS NULL;

-- ---------------------------------------------------------------------
-- 접속 기록 [물리 추가] — 6.53 ACCESS_LOG (1년). 논리 ERD에 엔터티가 없어서 더함
-- ---------------------------------------------------------------------
CREATE TABLE access_log (
    access_log_id  bigint      GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id        varchar(20) REFERENCES app_user,
    at             timestamptz NOT NULL DEFAULT now(),
    action         varchar(12) NOT NULL CHECK (action IN ('LOGIN','LOGIN_FAIL','LOGOUT','API')),
    method         varchar(7),
    path           varchar(200),
    status_code    smallint,
    client_ip      inet,
    detail         jsonb
);
CREATE INDEX ix_access_log_time ON access_log USING brin (at);
COMMENT ON TABLE access_log IS '물리 추가: 접속 기록 1년 보관 (6.53 ACCESS_LOG, 개인정보 안전성 확보조치 기준 제8조). 실제 시각(now) 기준';

-- ===================== db/schema/90_physical_extras.sql =====================
-- =====================================================================
-- 90_physical_extras.sql — 논리 ERD에 없고 물리 설계에서 더한 표
-- 각각 왜 필요한지는 docs/02_물리ERD.md 3장
-- =====================================================================

-- 코드 한국어 이름 (6장 코드 목록). 화면·비서가 같은 이름을 쓰도록 한 곳에 둔다
CREATE TABLE code_label (
    code_group  varchar(40)  NOT NULL,     -- 예: 'equipment_state_log.state_code'
    code        varchar(20)  NOT NULL,
    name_ko     varchar(200) NOT NULL,
    sort_order  smallint     NOT NULL DEFAULT 0,
    source_ref  varchar(40),               -- 예: '6.1'
    PRIMARY KEY (code_group, code)
);

-- 업무 번호 카운터 (PO-, SHP-, MW-, MR-, MR-S-, MAT-) — 월마다 1부터. fn_next_doc_no()가 쓴다
CREATE TABLE doc_number_seq (
    prefix   varchar(8) NOT NULL,
    yymm     char(4)    NOT NULL CHECK (yymm ~ '^[0-9]{4}$'),
    last_no  integer    NOT NULL CHECK (last_no >= 0),
    PRIMARY KEY (prefix, yymm)
);

-- 시연 시계 (NFR-DATA-10): 평소 1초 = 1분 같은 빠른 진행, 다음 날 06:00으로 건너뛰기.
-- 업무 시각은 모두 app_now()로 정한다 (now() 직접 사용 금지 — 02_물리ERD 4장)
CREATE TABLE sim_clock (
    id           smallint     PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    mode         varchar(4)   NOT NULL DEFAULT 'REAL' CHECK (mode IN ('REAL','SIM')),
    real_anchor  timestamptz  NOT NULL DEFAULT now(),
    sim_anchor   timestamptz  NOT NULL DEFAULT now(),
    speed        numeric(8,3) NOT NULL DEFAULT 1 CHECK (speed > 0),
    is_paused    boolean      NOT NULL DEFAULT false,
    updated_at   timestamptz  NOT NULL DEFAULT now()
);
INSERT INTO sim_clock (id) VALUES (1);

-- 데이터 묶음 정보 (R-59, NFR-DATA-08 가상 표시를 묶음 단위로) + 생성기 manifest
CREATE TABLE dataset_info (
    id              smallint    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    is_virtual      boolean     NOT NULL DEFAULT true,
    label           varchar(80) NOT NULL DEFAULT '가상 운영 데이터',
    seed            bigint,
    config_sha256   char(64),
    period_from     date,
    period_to       date,
    loaded_at       timestamptz,
    manifest        jsonb
);
INSERT INTO dataset_info (id) VALUES (1);

-- L2 집계 (6.53): 1년 지난 센서 1분 값·재공 값을 1시간 집계로 줄여 2년 보관
CREATE TABLE sensor_hourly (
    equipment_id  varchar(10) NOT NULL REFERENCES equipment,
    sensor_code   varchar(20) NOT NULL REFERENCES sensor_item,
    hour_at       timestamptz NOT NULL CHECK (date_trunc('hour', hour_at) = hour_at),
    min_value     real        NOT NULL,
    avg_value     real        NOT NULL,
    max_value     real        NOT NULL,
    sample_count  integer     NOT NULL CHECK (sample_count > 0),
    PRIMARY KEY (equipment_id, sensor_code, hour_at)
);

CREATE TABLE wip_hourly (
    buffer_code  varchar(10)  NOT NULL REFERENCES wip_buffer,
    hour_at      timestamptz  NOT NULL CHECK (date_trunc('hour', hour_at) = hour_at),
    avg_qty      numeric(8,2) NOT NULL,
    max_qty      integer      NOT NULL,
    PRIMARY KEY (buffer_code, hour_at)
);


-- QR 찍은 기록 [제안: 물리 추가, 2026-10-13 가정 "재고·로트는 QR로 관리"] — 논리 ERD 밖.
-- QR 안에는 번호만 있다 (MOM:LOT:LOT-2609-041-1 / MOM:MAT:MAT-2609-12 / MOM:ITEM:TL-EM10 — app/domain/qr.py).
-- 무엇을 찍었고(조회·입고·실사·출하 확인·측정 시작) 결과가 어땠는지를 남긴다. 출하 확인 여부는 이 기록으로 계산한다
-- (shipment_line에 칸을 더하지 않음). 추가만 한다 (86_qr.sql 트리거).
CREATE TABLE qr_scan (
    scan_id         bigint       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    scanned_at      timestamptz  NOT NULL,
    user_id         varchar(20)  NOT NULL REFERENCES app_user,
    raw_code        varchar(120),                 -- 찍은 글자 그대로. 라벨이 상해 못 찍었으면(MANUAL) 비움
    code_kind       varchar(4)   NOT NULL CHECK (code_kind IN ('LOT','MAT','ITEM','NONE')),
    ref_no          varchar(20),                  -- 읽어 낸 번호 (로트·원자재 로트·품목)
    purpose         varchar(13)  NOT NULL CHECK (purpose IN ('LOOKUP','RECEIPT','STOCKTAKE','SHIP_CHECK','MEASURE_START')),
    result          varchar(9)   NOT NULL CHECK (result IN ('OK','NOT_FOUND','MISMATCH','MANUAL')),
    shipment_no     varchar(12)  REFERENCES shipment,
    instruction_id  bigint       REFERENCES cmm_instruction,
    txn_id          bigint       REFERENCES inventory_txn,
    detail          text,
    CONSTRAINT ck_qr_scan_kind CHECK ((code_kind = 'NONE') = (ref_no IS NULL)),
    -- 못 찍었으면 사유 필수, 찍었으면 찍은 글자 필수
    CONSTRAINT ck_qr_scan_manual CHECK (
        (result = 'MANUAL' AND raw_code IS NULL AND btrim(coalesce(detail, '')) <> '') OR
        (result <> 'MANUAL' AND raw_code IS NOT NULL)),
    CONSTRAINT ck_qr_scan_ship CHECK (purpose <> 'SHIP_CHECK' OR shipment_no IS NOT NULL),
    CONSTRAINT ck_qr_scan_measure CHECK (purpose <> 'MEASURE_START' OR instruction_id IS NOT NULL)
);
CREATE INDEX ix_qr_scan_time ON qr_scan (scanned_at);
CREATE INDEX ix_qr_scan_ship ON qr_scan (shipment_no, ref_no) WHERE purpose = 'SHIP_CHECK' AND result = 'OK';
COMMENT ON TABLE qr_scan IS '물리 추가 [제안]: QR 찍은 기록 (재고·로트 QR 가정, 2026-10-13). 출하 전 로트 확인·측정 시작 로트 확인의 근거';

-- ===================== db/schema/95_deferred_fks.sql =====================
-- =====================================================================
-- 95_deferred_fks.sql — 서로를 가리키는 외래 키 (순환)
--   notification.wo_no            → maintenance_work_order
--   maintenance_work_order.trigger_notification_id → notification   (반복 알람 2단계 원인 점검)
--   work_record.cause_check_notification_id        → notification   (다른 공정 원인 점검 간이 기록)
-- 한 트랜잭션 안에서 순서 없이 넣을 수 있게 DEFERRABLE INITIALLY DEFERRED로 건다
-- (생성기 CSV 적재·워크플로 함수 둘 다 커밋 때 확인된다).
-- =====================================================================

ALTER TABLE maintenance_work_order
    ADD CONSTRAINT fk_wo_trigger_notification FOREIGN KEY (trigger_notification_id)
        REFERENCES notification (notification_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE work_record
    ADD CONSTRAINT fk_work_record_cause_check FOREIGN KEY (cause_check_notification_id)
        REFERENCES notification (notification_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE notification
    DROP CONSTRAINT IF EXISTS notification_wo_no_fkey,
    ADD CONSTRAINT fk_notification_wo FOREIGN KEY (wo_no)
        REFERENCES maintenance_work_order (wo_no) DEFERRABLE INITIALLY DEFERRED;

-- ===================== db/schema/96_demo_snapshot.sql =====================
-- =====================================================================
-- 96_demo_snapshot.sql — 시연 기준점 (API명세서 SIM-03 "시연 데이터 처음으로", 2026-10-08)
-- 운영 데이터를 통째로 복사해 두는 곳. 앱 계정(mom_app)·비서 계정(mom_ai_ro)은 이 스키마를 못 읽는다 (권한 없음).
-- 복사·되돌리기는 SECURITY DEFINER 함수 fn_demo_snapshot / fn_demo_reset (functions/80_demo_reset.sql)만 한다.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS demo_snapshot;

CREATE TABLE demo_snapshot.meta (
    id          smallint     PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    taken_at    timestamptz  NOT NULL,          -- 실제 시각
    sim_at      timestamptz  NOT NULL,          -- 그때 시연 시계 (되돌리면 이 시각으로)
    clock_mode  varchar(4)   NOT NULL,
    speed       numeric(8,3) NOT NULL,
    tables      text[]       NOT NULL           -- 복사한 표 (FK 순서와 상관없이 한꺼번에 비우고 채운다)
);
COMMENT ON SCHEMA demo_snapshot IS '시연 기준점 복사본 (SIM-03). 운영에서는 쓰지 않는다';

-- ===================== db/functions/10_clock_numbering.sql =====================
-- =====================================================================
-- 10_clock_numbering.sql — 시연 시계와 업무 번호
-- =====================================================================

-- ---------------------------------------------------------------------
-- app_now(): 업무 시각. REAL이면 now(), SIM이면 기준점 + (지난 실제 시간 × 배속)
-- 한 트랜잭션 안에서는 같은 값 (now()가 트랜잭션 시작 시각이므로)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_now() RETURNS timestamptz
LANGUAGE sql STABLE AS $$
    SELECT CASE
             WHEN c.mode = 'REAL' THEN now()
             WHEN c.is_paused THEN c.sim_anchor
             ELSE c.sim_anchor + (now() - c.real_anchor) * c.speed
           END
    FROM sim_clock c WHERE c.id = 1;
$$;
COMMENT ON FUNCTION app_now() IS '업무 시각 (시연 시계). 업무 칼럼(occurred_at 등)에는 now() 대신 이것을 쓴다';

-- 시연 시계 바꾸기: 모드·시각·배속. p_sim_at을 비우면 지금 시연 시각을 이어 간다
CREATE OR REPLACE FUNCTION fn_sim_set(p_mode text, p_sim_at timestamptz DEFAULT NULL,
                                      p_speed numeric DEFAULT NULL, p_paused boolean DEFAULT NULL)
RETURNS timestamptz LANGUAGE plpgsql AS $$
DECLARE
    v_now_sim timestamptz := app_now();
BEGIN
    IF p_mode NOT IN ('REAL','SIM') THEN
        RAISE EXCEPTION 'mode는 REAL 또는 SIM' USING ERRCODE = '22023';
    END IF;
    UPDATE sim_clock
       SET mode        = p_mode,
           real_anchor = now(),
           sim_anchor  = coalesce(p_sim_at, v_now_sim),
           speed       = coalesce(p_speed, speed),
           is_paused   = coalesce(p_paused, is_paused),
           updated_at  = now()
     WHERE id = 1;
    RETURN app_now();
END $$;
COMMENT ON FUNCTION fn_sim_set(text, timestamptz, numeric, boolean) IS
    '시연 시계 설정. 예: 다음 날 06:00으로 건너뛰기 = fn_sim_set(''SIM'', ''2026-09-16 06:00+09'')';

-- ---------------------------------------------------------------------
-- 업무 번호 (doc_number_seq). 월은 한국 시간 기준. 동시에 불러도 겹치지 않는다 (행 잠금)
--   번호 모양은 논리 ERD 5장 (생성기와 같음):
--   fn_next_doc_no('PO',  t)    → PO-2609-001      fn_next_doc_no('SHP', t) → SHP-2609-001
--   fn_next_doc_no('MAT', t, 2) → MAT-2609-01
--   fn_next_doc_no('MW',  t)    → MW-0901 (월 + 두 자리)   'MR' → MR-0901, 'MR-S' → MR-S-0901  (설계서 5.11)
--   카운터 칸(yymm)은 모두 연월(YYMM) — 월 + 두 자리 번호도 해가 바뀌면 따로 센다
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_next_doc_no(p_prefix text, p_at timestamptz, p_width int DEFAULT 3)
RETURNS text LANGUAGE sql AS $$
    INSERT INTO doc_number_seq AS s (prefix, yymm, last_no)
    VALUES (p_prefix, to_char(p_at AT TIME ZONE 'Asia/Seoul', 'YYMM'), 1)
    ON CONFLICT (prefix, yymm) DO UPDATE SET last_no = s.last_no + 1
    RETURNING CASE WHEN s.prefix IN ('MW','MR','MR-S')
                   THEN s.prefix || '-' || substr(s.yymm, 3, 2) || lpad(s.last_no::text, 2, '0')
                   ELSE s.prefix || '-' || s.yymm || '-' || lpad(s.last_no::text, p_width, '0') END;
$$;

-- 생성기 데이터를 넣은 뒤 카운터를 이미 있는 번호의 최대값에 맞춘다 (안 하면 시연 중 번호가 겹친다)
CREATE OR REPLACE FUNCTION fn_sync_doc_numbers() RETURNS TABLE (prefix text, yymm text, last_no int)
LANGUAGE sql AS $$
    WITH nums AS (
        SELECT 'PO'   AS p, substr(order_no, 4, 4) AS ym, substr(order_no, 9)::int AS n FROM production_order
        UNION ALL SELECT 'SHP',  substr(shipment_no, 5, 4), substr(shipment_no, 10)::int FROM shipment
        -- MW-0901 / MR-0901 / MR-S-0901: 번호에 해가 없어 만든 시각의 해(한국 시간)를 붙인다
        UNION ALL SELECT 'MW',   to_char(created_at AT TIME ZONE 'Asia/Seoul', 'YY') || substr(wo_no, 4, 2), substr(wo_no, 6)::int
                    FROM maintenance_work_order
        UNION ALL SELECT 'MR',   to_char(start_at AT TIME ZONE 'Asia/Seoul', 'YY') || substr(record_no, 4, 2), substr(record_no, 6)::int
                    FROM work_record WHERE record_type = 'FULL'
        UNION ALL SELECT 'MR-S', to_char(start_at AT TIME ZONE 'Asia/Seoul', 'YY') || substr(record_no, 6, 2), substr(record_no, 8)::int
                    FROM work_record WHERE record_type = 'SIMPLE'
        UNION ALL SELECT 'MAT',  substr(material_lot_no, 5, 4), substr(material_lot_no, 10)::int FROM raw_material_lot
    ), mx AS (
        SELECT p, ym, max(n) AS n FROM nums GROUP BY p, ym
    )
    INSERT INTO doc_number_seq AS s (prefix, yymm, last_no)
    SELECT p, ym, n FROM mx
    ON CONFLICT (prefix, yymm) DO UPDATE SET last_no = greatest(s.last_no, EXCLUDED.last_no)
    RETURNING s.prefix::text, s.yymm::text, s.last_no;
$$;

-- ===================== db/functions/20_integrity.sql =====================
-- =====================================================================
-- 20_integrity.sql — 여러 표를 봐야 하는 규칙 (트리거)
-- 원칙 (docs/02_물리ERD.md 7장):
--   * 한 행 안에서 되는 규칙은 CHECK (schema/), 여러 표를 보는 규칙은 여기 트리거.
--   * "상태가 바뀌는 순간"의 규칙(예: 확정하려면 잠금·표지 9개 체크)은 UPDATE 때만 확인한다.
--     생성기가 이미 확정된 과거 기록을 INSERT로 넣을 때는 순서상 하위 행이 아직 없기 때문이다.
--     그런 기록은 db/checks/validate_loaded_data.sql 의 점검 쿼리로 확인한다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 공통 도우미
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_user_role(p_user_id text) RETURNS text
LANGUAGE sql STABLE AS $$ SELECT role_code FROM app_user WHERE user_id = p_user_id $$;

-- 사람 칸에 정해진 역할만 들어오게 한다 (R-50·R-51). 비서는 app_user가 아니므로 여기서 걸린다
CREATE OR REPLACE FUNCTION fn_require_role(p_user_id text, p_roles text[], p_what text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_role text;
BEGIN
    IF p_user_id IS NULL THEN RETURN; END IF;
    SELECT role_code INTO v_role FROM app_user WHERE user_id = p_user_id AND is_active;
    IF v_role IS NULL THEN
        RAISE EXCEPTION '%: 사용 중인 사용자가 아님 (%)', p_what, p_user_id USING ERRCODE = '23514';
    END IF;
    IF NOT v_role = ANY (p_roles) THEN
        RAISE EXCEPTION '%: % 역할만 할 수 있음 (% = %)', p_what, array_to_string(p_roles, '·'), p_user_id, v_role
            USING ERRCODE = '23514';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_equipment_process(p_equipment_id text) RETURNS text
LANGUAGE sql STABLE AS $$ SELECT process_code FROM equipment WHERE equipment_id = p_equipment_id $$;

-- ---------------------------------------------------------------------
-- 교대 반장은 SUP (5.A.6)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_shift_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.supervisor_user_id, ARRAY['SUP'], 'shift.supervisor_user_id');
    RETURN NEW;
END $$;
CREATE TRIGGER shift_check BEFORE INSERT OR UPDATE OF supervisor_user_id ON shift
    FOR EACH ROW EXECUTE FUNCTION trg_shift_check();

-- ---------------------------------------------------------------------
-- 안전 재고는 MGR만 정한다 (R-58)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_inventory_item_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.safety_stock_set_by, ARRAY['MGR'], 'inventory_item.safety_stock_set_by');
    RETURN NEW;
END $$;
CREATE TRIGGER inventory_item_check BEFORE INSERT OR UPDATE OF safety_stock_set_by ON inventory_item
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_item_check();

-- ---------------------------------------------------------------------
-- R-06a 생산 로트의 원자재 로트는 투입 때 "사용 가능"
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_production_lot_material() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_status text;
BEGIN
    SELECT status INTO v_status FROM raw_material_lot WHERE material_lot_no = NEW.material_lot_no;
    IF v_status IS DISTINCT FROM 'AVAILABLE' THEN
        RAISE EXCEPTION 'R-06a: 원자재 로트 %는 사용 가능 상태가 아님 (%)', NEW.material_lot_no, v_status
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER production_lot_material BEFORE INSERT OR UPDATE OF material_lot_no ON production_lot
    FOR EACH ROW EXECUTE FUNCTION trg_production_lot_material();

-- ---------------------------------------------------------------------
-- R-24a 로트 상태는 6.8 순서로만 (UPDATE 때)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_production_lot_status() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
    IF NEW.status = OLD.status THEN RETURN NEW; END IF;
    -- 생성기 10/1 기록이 9월 끝 로트를 덮어쓸 때(적재)는 이미 지나간 상태 흐름의 마지막 값이 온다 — 단계 확인은 운영 중에만
    IF current_setting('app.loading', true) = 'on' THEN RETURN NEW; END IF;
    ok := CASE OLD.status
        WHEN 'IN_PROCESS'      THEN NEW.status IN ('WAIT_INSPECTION','ON_HOLD')
        WHEN 'WAIT_INSPECTION' THEN NEW.status IN ('WAIT_JUDGEMENT','HOLD_REVIEW','PASSED','ON_HOLD')
        WHEN 'WAIT_JUDGEMENT'  THEN NEW.status IN ('PASSED','HOLD_REVIEW','ON_HOLD')
        WHEN 'HOLD_REVIEW'     THEN NEW.status IN ('ON_HOLD','PASSED')
        WHEN 'ON_HOLD'         THEN NEW.status IN ('RELEASED','SCRAPPED')
        WHEN 'RELEASED'        THEN NEW.status IN ('PASSED')
        ELSE false END;
    IF NOT ok THEN
        RAISE EXCEPTION 'R-24a: 로트 % 상태를 %에서 %로 바꿀 수 없음', NEW.lot_no, OLD.status, NEW.status
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER production_lot_status BEFORE UPDATE OF status ON production_lot
    FOR EACH ROW EXECUTE FUNCTION trg_production_lot_status();

-- ---------------------------------------------------------------------
-- R-13 재공은 한도 이하
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_wip_log_limit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_limit int;
BEGIN
    SELECT limit_qty INTO v_limit FROM wip_buffer WHERE buffer_code = NEW.buffer_code;
    IF NEW.wip_qty > v_limit THEN
        RAISE EXCEPTION 'R-13: % 재공 %개가 한도 %개를 넘음', NEW.buffer_code, NEW.wip_qty, v_limit USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER wip_log_limit BEFORE INSERT OR UPDATE ON wip_log
    FOR EACH ROW EXECUTE FUNCTION trg_wip_log_limit();

-- ---------------------------------------------------------------------
-- R-24 알람은 그 알람의 적용 공정 설비에서만 난다
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_alarm_event_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_alarm_process text;
BEGIN
    SELECT process_code INTO v_alarm_process FROM alarm_master WHERE alarm_code = NEW.alarm_code;
    IF v_alarm_process IS DISTINCT FROM fn_equipment_process(NEW.equipment_id) THEN
        RAISE EXCEPTION 'R-24: 알람 %는 % 공정 알람인데 설비 %에서 남', NEW.alarm_code, v_alarm_process, NEW.equipment_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER alarm_event_check BEFORE INSERT OR UPDATE OF alarm_code, equipment_id ON alarm_event
    FOR EACH ROW EXECUTE FUNCTION trg_alarm_event_check();

-- ---------------------------------------------------------------------
-- 설비 상태 구간: R-01·R-22 DOWN = 정지 등급 알람(같은 설비), R-21 사유 확정 = SUP
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_state_log_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sev text; v_eq text;
BEGIN
    IF NEW.alarm_event_id IS NOT NULL THEN
        SELECT severity_at_event, equipment_id INTO v_sev, v_eq FROM alarm_event WHERE alarm_event_id = NEW.alarm_event_id;
        IF v_eq <> NEW.equipment_id THEN
            RAISE EXCEPTION '상태 구간의 알람 %는 다른 설비(%) 알람', NEW.alarm_event_id, v_eq USING ERRCODE = '23514';
        END IF;
        IF NEW.state_code = 'DOWN' AND v_sev <> 'STOP' THEN
            RAISE EXCEPTION 'R-22: DOWN은 정지 등급 알람만 (알람 % 등급 %)', NEW.alarm_event_id, v_sev USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM fn_require_role(NEW.reason_confirmed_by, ARRAY['SUP'], 'R-21 정지 사유 확정');
    PERFORM fn_require_role(NEW.reason_entered_by, ARRAY['OPR','MNT','SUP'], '정지 사유 입력');
    RETURN NEW;
END $$;
CREATE TRIGGER state_log_check BEFORE INSERT OR UPDATE ON equipment_state_log
    FOR EACH ROW EXECUTE FUNCTION trg_state_log_check();

-- ---------------------------------------------------------------------
-- 공구는 OP-30 설비에만 (5.E.2), 공구 교체는 OPR·MNT (13.2)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_tool_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF fn_equipment_process(NEW.equipment_id) <> 'OP-30' THEN
        RAISE EXCEPTION '공구는 OP-30 설비에만 (%)', NEW.equipment_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tool_check BEFORE INSERT OR UPDATE OF equipment_id ON tool
    FOR EACH ROW EXECUTE FUNCTION trg_tool_check();

CREATE OR REPLACE FUNCTION trg_tool_change_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.changed_by, ARRAY['OPR','MNT'], '공구 교체 기록');
    RETURN NEW;
END $$;
CREATE TRIGGER tool_change_check BEFORE INSERT OR UPDATE ON tool_change
    FOR EACH ROW EXECUTE FUNCTION trg_tool_change_check();

-- ---------------------------------------------------------------------
-- 로트 보류·해제·폐기의 사람 (R-27, 5.B.7): 보류·해제 SUP·MGR, 폐기 제안 SUP, 폐기 승인 MGR, 보통 복귀 SUP
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_lot_hold_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.held_by, ARRAY['SUP','MGR'], '로트 보류');
    PERFORM fn_require_role(NEW.released_by, ARRAY['SUP','MGR'], '로트 해제');
    PERFORM fn_require_role(NEW.scrap_proposed_by, ARRAY['SUP'], '폐기 제안');
    PERFORM fn_require_role(NEW.scrap_approved_by, ARRAY['MGR'], '폐기 승인');
    PERFORM fn_require_role(NEW.normal_resumed_by, ARRAY['SUP'], '보통 검사 복귀');
    RETURN NEW;
END $$;
CREATE TRIGGER lot_hold_check BEFORE INSERT OR UPDATE ON lot_hold
    FOR EACH ROW EXECUTE FUNCTION trg_lot_hold_check();

-- ---------------------------------------------------------------------
-- 예방 정비 기록 저장은 MNT (5.D.8)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_pm_record_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.recorded_by, ARRAY['MNT'], '예방 정비 기록 저장');
    RETURN NEW;
END $$;
CREATE TRIGGER pm_record_check BEFORE INSERT OR UPDATE OF recorded_by ON pm_record
    FOR EACH ROW EXECUTE FUNCTION trg_pm_record_check();

-- ---------------------------------------------------------------------
-- 정비 작업지시서 (5.D.1, R-02·R-31a·R-71, 6.13)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_work_order_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sev text; v_eq text; v_rule text; ok boolean;
BEGIN
    IF fn_equipment_process(NEW.equipment_id) <> 'OP-30' THEN
        RAISE EXCEPTION 'R-02: 작업지시서는 OP-30 설비만 (%)', NEW.equipment_id USING ERRCODE = '23514';
    END IF;
    IF NEW.alarm_event_id IS NOT NULL THEN
        SELECT severity_at_event, equipment_id INTO v_sev, v_eq FROM alarm_event WHERE alarm_event_id = NEW.alarm_event_id;
        IF v_sev <> 'STOP' OR v_eq <> NEW.equipment_id THEN
            RAISE EXCEPTION 'R-02: 작업지시서 알람은 같은 설비의 정지 등급이어야 함 (알람 %: %·%)',
                NEW.alarm_event_id, v_eq, v_sev USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.trigger_notification_id IS NOT NULL THEN
        SELECT rule_code INTO v_rule FROM notification WHERE notification_id = NEW.trigger_notification_id;
        IF v_rule IS NOT NULL AND v_rule <> 'REPEAT_ALARM_2' THEN
            RAISE EXCEPTION 'R-71: 계기 알림은 반복 알람 2단계여야 함 (%)', v_rule USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM fn_require_role(NEW.assignee_user_id, ARRAY['MNT'], '작업지시서 담당');
    PERFORM fn_require_role(NEW.approved_by, ARRAY['SUP','MGR'], '작업지시서 승인');
    PERFORM fn_require_role(NEW.cancelled_by, ARRAY['MGR'], '작업지시서 취소');
    IF TG_OP = 'UPDATE' AND NEW.status <> OLD.status THEN
        ok := CASE OLD.status
            WHEN 'AI_DRAFT'    THEN NEW.status IN ('EDITING','CANCELLED')
            WHEN 'EDITING'     THEN NEW.status IN ('APPROVED','CANCELLED')
            WHEN 'APPROVED'    THEN NEW.status IN ('IN_PROGRESS','CANCELLED')
            WHEN 'IN_PROGRESS' THEN NEW.status IN ('DONE')
            ELSE false END;
        IF NOT ok THEN
            RAISE EXCEPTION '6.13: 작업지시서 % 상태를 %에서 %로 바꿀 수 없음', NEW.wo_no, OLD.status, NEW.status
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER work_order_check BEFORE INSERT OR UPDATE ON maintenance_work_order
    FOR EACH ROW EXECUTE FUNCTION trg_work_order_check();

-- ---------------------------------------------------------------------
-- 작업기록서 (5.D.4, R-32, 6.15)
--   확정자: 작업기록서 = MNT / 간이: 주의 등급 = OPR·MNT, 다른 공정 정지 등급 = MNT, 원인 점검 = MNT
--   확인자 = SUP
--   확정 순간(UPDATE로 CONFIRMED가 될 때): 잠금·표지가 필요한 기록은 9단계 모두 체크 (R-32)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_work_record_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sev text; v_proc text; v_roles text[]; v_loto int; v_wo_eq text;
BEGIN
    IF NEW.wo_no IS NOT NULL THEN
        SELECT equipment_id INTO v_wo_eq FROM maintenance_work_order WHERE wo_no = NEW.wo_no;
        IF v_wo_eq <> NEW.equipment_id THEN
            RAISE EXCEPTION '작업기록서 설비(%)가 작업지시서 설비(%)와 다름', NEW.equipment_id, v_wo_eq USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.confirmed_by IS NOT NULL THEN
        IF NEW.record_type = 'FULL' OR NEW.cause_check_notification_id IS NOT NULL THEN
            v_roles := ARRAY['MNT'];
        ELSE
            SELECT a.severity_at_event, e.process_code INTO v_sev, v_proc
              FROM alarm_event a JOIN equipment e USING (equipment_id) WHERE a.alarm_event_id = NEW.alarm_event_id;
            v_roles := CASE WHEN v_sev = 'STOP' THEN ARRAY['MNT'] ELSE ARRAY['OPR','MNT'] END;
        END IF;
        PERFORM fn_require_role(NEW.confirmed_by, v_roles, '작업기록 확정');
    END IF;
    PERFORM fn_require_role(NEW.checked_by, ARRAY['SUP'], '작업기록서 확인');
    IF TG_OP = 'UPDATE' AND NEW.status = 'CONFIRMED' AND OLD.status IN ('AI_DRAFT','EDITING')
       AND NEW.safety_block_required THEN
        SELECT count(*) INTO v_loto FROM work_record_check
         WHERE record_no = NEW.record_no AND check_kind = 'LOTO' AND is_checked;
        IF v_loto < 9 THEN
            RAISE EXCEPTION 'R-32: 잠금·표지 9단계 중 %단계만 체크됨 — 확정할 수 없음 (%)', v_loto, NEW.record_no
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER work_record_check BEFORE INSERT OR UPDATE ON work_record
    FOR EACH ROW EXECUTE FUNCTION trg_work_record_check();

-- ---------------------------------------------------------------------
-- 보고서·출하 확정자 (R-36, 13.1)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_shift_report_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_sup text;
BEGIN
    IF NEW.confirmed_by IS NOT NULL THEN
        SELECT supervisor_user_id INTO v_sup FROM shift WHERE shift_id = NEW.shift_id;
        IF NEW.confirmed_by <> v_sup THEN
            RAISE EXCEPTION 'R-36: 교대 보고서는 그 교대 반장(%)만 확정 (%)', v_sup, NEW.confirmed_by USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER shift_report_check BEFORE INSERT OR UPDATE OF confirmed_by ON shift_report
    FOR EACH ROW EXECUTE FUNCTION trg_shift_report_check();

CREATE OR REPLACE FUNCTION trg_daily_report_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.confirmed_by, ARRAY['MGR'], 'R-36 일일 보고서 확정');
    RETURN NEW;
END $$;
CREATE TRIGGER daily_report_check BEFORE INSERT OR UPDATE OF confirmed_by ON daily_report
    FOR EACH ROW EXECUTE FUNCTION trg_daily_report_check();

CREATE OR REPLACE FUNCTION trg_shipment_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.confirmed_by, ARRAY['SUP'], '출하 확정');
    RETURN NEW;
END $$;
CREATE TRIGGER shipment_check BEFORE INSERT OR UPDATE OF confirmed_by ON shipment
    FOR EACH ROW EXECUTE FUNCTION trg_shipment_check();

-- ---------------------------------------------------------------------
-- 검사 결과: 측정자 = OPR, 반장 확인 = SUP (5.F.4)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_inspection_result_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.inspector_id, ARRAY['OPR'], '측정자');
    PERFORM fn_require_role(NEW.checked_by, ARRAY['SUP'], '측정값 반장 확인');
    RETURN NEW;
END $$;
CREATE TRIGGER inspection_result_check BEFORE INSERT OR UPDATE OF inspector_id, checked_by ON inspection_result
    FOR EACH ROW EXECUTE FUNCTION trg_inspection_result_check();

-- ---------------------------------------------------------------------
-- 설정은 MGR (R-58, NFR-SEC-04)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_notification_rule_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.updated_by, ARRAY['MGR'], '알림 규칙 설정');
    RETURN NEW;
END $$;
CREATE TRIGGER notification_rule_check BEFORE INSERT OR UPDATE ON notification_rule
    FOR EACH ROW EXECUTE FUNCTION trg_notification_rule_check();

CREATE OR REPLACE FUNCTION trg_internal_doc_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_require_role(NEW.approved_by, ARRAY['MGR'], '사내 문서 개정 승인');
    RETURN NEW;
END $$;
CREATE TRIGGER internal_doc_check BEFORE INSERT OR UPDATE OF approved_by ON internal_doc
    FOR EACH ROW EXECUTE FUNCTION trg_internal_doc_check();

-- ---------------------------------------------------------------------
-- 입출고 거래
--   (1) 기록자: 입고 등록·월말 실사 = 그 품목의 관리 역할 (R-77), 로트 합격 입고 = 시스템(비움)
--   (2) 들어오면 재고 수량에 더한다 → 음수면 inventory_item CHECK가 막는다 (R-11)
--   (3) 거래는 고치지 않는다. 지우기는 보관 기간 작업만 (세션 설정 app.allow_purge = on)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_inventory_txn_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_owner text;
BEGIN
    IF NEW.source_kind IN ('RECEIPT','STOCKTAKE','MATERIAL_RECEIPT') THEN
        SELECT owner_role INTO v_owner FROM inventory_item WHERE item_no = NEW.item_no;
        IF NEW.txn_by IS NULL THEN
            RAISE EXCEPTION 'R-77: 입고·실사 거래는 기록자 필수' USING ERRCODE = '23514';
        END IF;
        PERFORM fn_require_role(NEW.txn_by, ARRAY[v_owner], 'R-77 품목 관리 역할 (' || NEW.item_no || ')');
    ELSIF NEW.source_kind = 'LOT_PASS' AND NEW.txn_by IS NOT NULL THEN
        RAISE EXCEPTION '로트 합격 입고는 시스템 거래 (txn_by 비움)' USING ERRCODE = '23514';
    ELSIF NEW.source_kind = 'SHIPMENT' THEN
        PERFORM fn_require_role(NEW.txn_by, ARRAY['SUP'], '출하 출고');
    ELSIF NEW.source_kind = 'TOOL_CHANGE' THEN
        PERFORM fn_require_role(NEW.txn_by, ARRAY['OPR','MNT'], '공구 사용');
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER inventory_txn_check BEFORE INSERT ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_txn_check();

CREATE OR REPLACE FUNCTION trg_inventory_txn_apply() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE inventory_item SET on_hand_qty = on_hand_qty + NEW.qty_change WHERE item_no = NEW.item_no;
    RETURN NULL;
EXCEPTION WHEN check_violation THEN
    RAISE EXCEPTION 'R-11: % 재고가 음수가 됨 (거래 %)', NEW.item_no, NEW.qty_change USING ERRCODE = '23514';
END $$;
CREATE TRIGGER inventory_txn_apply AFTER INSERT ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_inventory_txn_apply();

-- 추가만 하는 표 (수불대장·문서 버전·접속 기록)
CREATE OR REPLACE FUNCTION trg_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.allow_purge', true) = 'on' THEN
        RETURN OLD;   -- 보관 기간 작업 (db/functions/40_retention.sql)
    END IF;
    RAISE EXCEPTION '%은(는) 추가만 할 수 있음 (%)', TG_TABLE_NAME, TG_OP USING ERRCODE = '42501';
END $$;
CREATE TRIGGER inventory_txn_append_only BEFORE UPDATE OR DELETE ON inventory_txn
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();
CREATE TRIGGER document_revision_append_only BEFORE UPDATE OR DELETE ON document_revision
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();
CREATE TRIGGER document_revision_change_append_only BEFORE UPDATE OR DELETE ON document_revision_change
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();
CREATE TRIGGER access_log_append_only BEFORE UPDATE OR DELETE ON access_log
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();

-- ---------------------------------------------------------------------
-- R-35 확정된 문서는 잠긴다 — 확정 뒤 내용을 바꾸려면
--   ① current_version을 1 올리고 ② 그 버전의 document_revision(사유 있음)이 먼저 있어야 한다.
-- 워크플로 칸(상태·확정자·시각 등)만 바뀌는 것은 허용한다.
-- 인자: TG_ARGV[0] 문서 종류, [1] 키 칼럼, [2] 잠긴 상태들(쉼표), [3] 내용 비교에서 뺄 칼럼들(쉼표)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_doc_lock() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_locked  text[] := string_to_array(TG_ARGV[2], ',');
    v_exempt  text[] := string_to_array(TG_ARGV[3], ',') || ARRAY['current_version'];
    v_old     jsonb := to_jsonb(OLD) - v_exempt;
    v_new     jsonb := to_jsonb(NEW) - v_exempt;
    v_key     text  := to_jsonb(NEW) ->> TG_ARGV[1];
    v_reason  text;
BEGIN
    IF NOT (OLD.status = ANY (v_locked)) OR v_old = v_new THEN
        RETURN NEW;
    END IF;
    IF NEW.current_version <> OLD.current_version + 1 THEN
        RAISE EXCEPTION 'R-35: 확정된 %(%)는 새 버전으로만 고칠 수 있음 (current_version % → %)',
            TG_ARGV[0], v_key, OLD.current_version, NEW.current_version USING ERRCODE = '23514';
    END IF;
    SELECT reason INTO v_reason FROM document_revision
     WHERE doc_type = TG_ARGV[0] AND doc_key = v_key AND version_no = NEW.current_version;
    IF btrim(coalesce(v_reason, '')) = '' THEN
        RAISE EXCEPTION 'R-35: 확정 뒤 수정은 사유가 있는 문서 버전(v%)이 먼저 있어야 함 (% %)',
            NEW.current_version, TG_ARGV[0], v_key USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER shift_report_lock BEFORE UPDATE ON shift_report FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('SHIFT_REPORT', 'shift_id', 'CONFIRMED,REVISED', 'status,confirmed_by,confirmed_at');
CREATE TRIGGER daily_report_lock BEFORE UPDATE ON daily_report FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('DAILY_REPORT', 'work_date', 'CONFIRMED,REVISED', 'status,confirmed_by,confirmed_at');
CREATE TRIGGER work_record_lock BEFORE UPDATE ON work_record FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('WORK_RECORD', 'record_no', 'CONFIRMED,CHECKED', 'status,confirmed_by,confirmed_at,checked_by,checked_at');
CREATE TRIGGER work_order_lock BEFORE UPDATE ON maintenance_work_order FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('WORK_ORDER', 'wo_no', 'APPROVED,IN_PROGRESS,DONE,CANCELLED',
        'status,approved_by,approved_at,cancelled_by,cancelled_at,cancel_reason,completed_at,trigger_notification_id');
CREATE TRIGGER pm_record_lock BEFORE UPDATE ON pm_record FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('PM_RECORD', 'pm_record_id', 'CONFIRMED', 'status');
CREATE TRIGGER shipment_lock BEFORE UPDATE ON shipment FOR EACH ROW
    EXECUTE FUNCTION trg_doc_lock('SHIPMENT', 'shipment_no', 'CONFIRMED,REVISED', 'status,confirmed_by,shipped_at,fifo_skip_reason');

-- ---------------------------------------------------------------------
-- 알림이 생기거나 처리되면 실시간 채널로 알린다 (SSE: app/routers/stream.py가 LISTEN)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_notify_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- 생성기 대량 적재 중에는 알리지 않는다 (db/load/load_generated.sh가 app.loading=on으로 둔다)
    IF current_setting('app.loading', true) = 'on' THEN RETURN NULL; END IF;
    PERFORM pg_notify('mom_events', json_build_object(
        'table', TG_TABLE_NAME, 'op', TG_OP,
        'id', CASE TG_TABLE_NAME
                WHEN 'notification' THEN (to_jsonb(NEW) ->> 'notification_id')
                WHEN 'equipment_state_log' THEN (to_jsonb(NEW) ->> 'state_log_id')
                WHEN 'alarm_event' THEN (to_jsonb(NEW) ->> 'alarm_event_id')
                WHEN 'wip_log' THEN (to_jsonb(NEW) ->> 'buffer_code')
                WHEN 'bottleneck_log' THEN (to_jsonb(NEW) ->> 'bottleneck_log_id')
                WHEN 'document_revision' THEN (to_jsonb(NEW) ->> 'doc_key')
                WHEN 'work_record' THEN (to_jsonb(NEW) ->> 'record_no')
              END,
        'equipment_id', to_jsonb(NEW) ->> 'equipment_id',
        -- 실시간 사건 이름을 정하는 데 필요한 것만 (API명세서 3장): 알림 중요도(긴급 팝업), 문서 종류, 상태
        'importance', to_jsonb(NEW) ->> 'importance',
        'doc_type', to_jsonb(NEW) ->> 'doc_type',
        'status', to_jsonb(NEW) ->> 'status')::text);
    RETURN NULL;
END $$;
CREATE TRIGGER notification_notify AFTER INSERT OR UPDATE ON notification
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER state_log_notify AFTER INSERT OR UPDATE ON equipment_state_log
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER alarm_event_notify AFTER INSERT ON alarm_event
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
-- 재공·병목·문서 버전·작업기록서 확정(지표 다시 계산) — 화면이 해당 API를 다시 부른다 (API명세서 3장)
CREATE TRIGGER wip_log_notify AFTER INSERT ON wip_log
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER bottleneck_log_notify AFTER INSERT ON bottleneck_log
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER document_revision_notify AFTER INSERT ON document_revision
    FOR EACH ROW EXECUTE FUNCTION trg_notify_event();
CREATE TRIGGER work_record_notify AFTER UPDATE OF status ON work_record
    FOR EACH ROW WHEN (NEW.status IN ('CONFIRMED','CHECKED') AND OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION trg_notify_event();

-- 병목 기록: 바로 앞 줄과 공정 또는 원인이 달라야 한다 (논리 ERD 5.B.6, 2026-10-13). 앞 줄의 새 병목 = 이 줄의 이전 병목
CREATE OR REPLACE FUNCTION trg_bottleneck_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p bottleneck_log%ROWTYPE;
BEGIN
    SELECT * INTO p FROM bottleneck_log WHERE changed_at < NEW.changed_at AND bottleneck_log_id <> NEW.bottleneck_log_id
     ORDER BY changed_at DESC LIMIT 1;
    IF FOUND AND p.new_process_code = NEW.new_process_code AND p.cause_code = NEW.cause_code THEN
        RAISE EXCEPTION '병목 기록: 앞 줄(%)과 공정·원인이 같음 (%·%)', p.changed_at, NEW.new_process_code, NEW.cause_code
            USING ERRCODE = '23514';
    END IF;
    IF FOUND AND NEW.prev_process_code IS DISTINCT FROM p.new_process_code THEN
        RAISE EXCEPTION '병목 기록: 이전 병목(%)이 앞 줄의 새 병목(%)과 다름', NEW.prev_process_code, p.new_process_code
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER bottleneck_changed BEFORE INSERT ON bottleneck_log FOR EACH ROW EXECUTE FUNCTION trg_bottleneck_changed();

-- ===================== db/functions/30_workflows.sql =====================
-- =====================================================================
-- 30_workflows.sql — 업무 트랜잭션 함수
-- 여러 표를 한꺼번에 바꿔야 하는 일(출하 확정·로트 합격·공구 교체·작업기록서 확정·알림 …)을
-- DB 함수 하나로 묶었다. 서버(app/)는 권한을 먼저 보고 이 함수를 부른다.
-- 함수 안에서도 "사람·역할" 규칙을 다시 확인한다 (NFR-SEC-05, 비서·다른 경로로 들어와도 막힘).
-- 시각 인자를 비우면 app_now() (시연 시계).
-- =====================================================================

-- =====================================================================
-- 1. 알림 (R-38: 규칙이 정하고 비서는 문장만)
-- =====================================================================

-- 알림 1건 만들기. p_refs = {"alarm_event_id": 1, "equipment_id": "VF2-01", ...}
-- 받는 사람: p_recipients가 비면 규칙의 recipient_roles 역할 사용자 전원
-- 묶기 (DOC-07 10.2): 같은 규칙·같은 설비·같은 알람 번호가 1분 안에 3번째부터는 새 알림 없이 repeat_count만 올린다
-- 폭주 (DOC-07 10.3): 최근 10분 긴급·주의 알림이 10건을 넘으면 is_flood
CREATE OR REPLACE FUNCTION fn_raise_notification(
    p_rule text, p_message text, p_refs jsonb DEFAULT '{}'::jsonb, p_at timestamptz DEFAULT NULL,
    p_related_info text DEFAULT NULL, p_message_source text DEFAULT 'DEFAULT',
    p_repeat_stage text DEFAULT NULL, p_prev_stage bigint DEFAULT NULL, p_recipients text[] DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at    timestamptz := coalesce(p_at, app_now());
    r       notification_rule%ROWTYPE;
    v_id    bigint;
    v_alarm text;
    v_same  int;
    v_flood int;
BEGIN
    SELECT * INTO r FROM notification_rule WHERE rule_code = p_rule;
    IF NOT FOUND THEN RAISE EXCEPTION '알림 규칙 % 없음', p_rule USING ERRCODE = '23503'; END IF;
    IF NOT r.is_enabled THEN RETURN NULL; END IF;

    -- 묶기: 알람 알림만
    IF p_rule IN ('ALARM_STOP','ALARM_WARN','ALARM_GUIDE') AND p_refs ? 'alarm_event_id' THEN
        SELECT alarm_code INTO v_alarm FROM alarm_event WHERE alarm_event_id = (p_refs->>'alarm_event_id')::bigint;
        SELECT count(*) INTO v_same FROM alarm_event
         WHERE equipment_id = p_refs->>'equipment_id' AND alarm_code = v_alarm
           AND occurred_at > v_at - interval '1 minute' AND occurred_at <= v_at;
        IF v_same >= 3 THEN
            UPDATE notification n SET repeat_count = n.repeat_count + 1
             WHERE n.notification_id = (
                SELECT n2.notification_id FROM notification n2 JOIN alarm_event a USING (alarm_event_id)
                 WHERE n2.rule_code = p_rule AND n2.equipment_id = p_refs->>'equipment_id' AND a.alarm_code = v_alarm
                   AND n2.raised_at > v_at - interval '1 minute' AND NOT n2.is_processed
                 ORDER BY n2.raised_at DESC LIMIT 1)
            RETURNING n.notification_id INTO v_id;
            IF v_id IS NOT NULL THEN RETURN v_id; END IF;
        END IF;
    END IF;

    SELECT count(*) INTO v_flood FROM notification
     WHERE importance IN ('URGENT','CAUTION') AND raised_at > v_at - interval '10 minutes' AND raised_at <= v_at;

    INSERT INTO notification (rule_code, importance, raised_at, message, related_info, message_source, is_flood,
        alarm_event_id, equipment_id, lot_no, item_no, pm_task_id, tool_id, wo_no, bottleneck_log_id,
        revision_id, result_id, shift_id, buffer_code, cmm_import_id, prev_stage_notification_id,
        repeat_stage_status)
    VALUES (p_rule, r.importance, v_at, p_message, p_related_info, p_message_source, v_flood >= 10,
        (p_refs->>'alarm_event_id')::bigint, p_refs->>'equipment_id', p_refs->>'lot_no', p_refs->>'item_no',
        p_refs->>'pm_task_id', p_refs->>'tool_id', p_refs->>'wo_no', (p_refs->>'bottleneck_log_id')::bigint,
        (p_refs->>'revision_id')::bigint, (p_refs->>'result_id')::bigint, p_refs->>'shift_id',
        p_refs->>'buffer_code', (p_refs->>'cmm_import_id')::bigint, p_prev_stage, p_repeat_stage)
    RETURNING notification_id INTO v_id;

    INSERT INTO notification_recipient (notification_id, user_id, popup_sound)
    SELECT v_id, u.user_id, r.importance = 'URGENT'
      FROM app_user u
     WHERE u.is_active AND (CASE WHEN p_recipients IS NOT NULL THEN u.user_id = ANY (p_recipients)
                                 ELSE u.role_code = ANY (r.recipient_roles) END)
    ON CONFLICT DO NOTHING;
    RETURN v_id;
END $$;

-- 사람이 [처리] (6.36 "알림 종류별 처리" 표). 반복 알람 1단계는 조치 계획 한 줄 필수 → 1단계 닫힘
CREATE OR REPLACE FUNCTION fn_process_notification(p_id bigint, p_actor text, p_memo text DEFAULT NULL,
                                                   p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    n notification%ROWTYPE; r notification_rule%ROWTYPE;
BEGIN
    SELECT * INTO n FROM notification WHERE notification_id = p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '알림 % 없음', p_id USING ERRCODE = '23503'; END IF;
    IF n.is_processed THEN RAISE EXCEPTION '알림 %는 이미 처리됨', p_id USING ERRCODE = '23514'; END IF;
    SELECT * INTO r FROM notification_rule WHERE rule_code = n.rule_code;
    IF r.process_mode = 'AUTO' THEN
        RAISE EXCEPTION '% 알림은 기록이 생기면 자동 처리됨 (사람 처리 없음)', n.rule_code USING ERRCODE = '23514';
    END IF;
    PERFORM fn_require_role(p_actor, r.processor_roles, n.rule_code || ' 알림 처리');
    UPDATE notification
       SET is_processed = true, process_kind = 'MANUAL', processed_by = p_actor, process_memo = p_memo,
           processed_at = v_at,
           repeat_stage_status = CASE WHEN rule_code = 'REPEAT_ALARM' THEN 'S1_CLOSED' ELSE repeat_stage_status END,
           effect_check_due_at = CASE WHEN rule_code = 'REPEAT_ALARM' THEN v_at + interval '7 days' ELSE effect_check_due_at END
     WHERE notification_id = p_id;
END $$;

-- 기록이 생겨서 저절로 처리 (process_kind = AUTO, 처리자 = 그 기록을 남긴 사람)
CREATE OR REPLACE FUNCTION fn_auto_process(p_ids bigint[], p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE sql AS $$
    WITH u AS (
        UPDATE notification SET is_processed = true, process_kind = 'AUTO', processed_by = p_actor,
               processed_at = coalesce(p_at, app_now())
         WHERE notification_id = ANY (p_ids) AND NOT is_processed
        RETURNING 1)
    SELECT count(*)::int FROM u;
$$;

-- 재고 부족 확인 (R-39): 안전 재고 이하면 알림(없을 때만), 넘으면 열린 알림 자동 처리. 완제품은 대상 아님
CREATE OR REPLACE FUNCTION fn_check_stock(p_item_no text, p_actor text DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE i inventory_item%ROWTYPE; v_open bigint[];
BEGIN
    SELECT * INTO i FROM inventory_item WHERE item_no = p_item_no;
    IF i.safety_stock IS NULL THEN RETURN; END IF;
    SELECT array_agg(notification_id) INTO v_open FROM notification
     WHERE rule_code = 'STOCK_LOW' AND item_no = p_item_no AND NOT is_processed;
    IF i.on_hand_qty <= i.safety_stock THEN
        IF v_open IS NULL THEN
            PERFORM fn_raise_notification('STOCK_LOW',
                format('%s 재고 %s%s — 안전 재고 %s 이하', i.item_name, i.on_hand_qty::float8, i.unit, i.safety_stock::float8),
                jsonb_build_object('item_no', p_item_no), p_at,
                p_recipients => (SELECT array_agg(user_id) FROM app_user
                                  WHERE is_active AND role_code IN (i.owner_role, 'MGR')));
        END IF;
    ELSIF v_open IS NOT NULL THEN
        PERFORM fn_auto_process(v_open, p_actor, p_at);
    END IF;
END $$;

-- =====================================================================
-- 2. 문서 버전 (R-35, FR-AST-03)
-- =====================================================================

-- 문서의 지금 상태 (doc_type + doc_key 다형 참조를 여기서 확인)
CREATE OR REPLACE FUNCTION fn_doc_status(p_doc_type text, p_doc_key text) RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE v text;
BEGIN
    CASE p_doc_type
        WHEN 'WORK_ORDER'   THEN SELECT status INTO v FROM maintenance_work_order WHERE wo_no = p_doc_key;
        WHEN 'WORK_RECORD'  THEN SELECT status INTO v FROM work_record WHERE record_no = p_doc_key;
        WHEN 'SHIFT_REPORT' THEN SELECT status INTO v FROM shift_report WHERE shift_id = p_doc_key;
        WHEN 'DAILY_REPORT' THEN SELECT status INTO v FROM daily_report WHERE work_date = p_doc_key::date;
        WHEN 'INTERNAL_DOC' THEN SELECT status INTO v FROM internal_doc WHERE doc_no = p_doc_key;
        WHEN 'PM_RECORD'    THEN SELECT status INTO v FROM pm_record WHERE pm_record_id = p_doc_key::bigint;
        WHEN 'SHIPMENT'     THEN SELECT status INTO v FROM shipment WHERE shipment_no = p_doc_key;
        ELSE RAISE EXCEPTION '문서 종류 % 없음', p_doc_type USING ERRCODE = '22023';
    END CASE;
    RETURN v;
END $$;

-- 새 버전 저장. 문서 본문(각 표)은 서버가 같은 트랜잭션에서 current_version과 함께 고친다.
-- p_changes = [{"field": "특이 사항", "before": "...", "after": "..."}]
-- 반환: 새 version_no
CREATE OR REPLACE FUNCTION fn_save_revision(
    p_doc_type text, p_doc_key text, p_author_kind text, p_author text, p_reason text,
    p_status_after text, p_content jsonb, p_changes jsonb DEFAULT '[]'::jsonb,
    p_internal_doc_rev text DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_status text := fn_doc_status(p_doc_type, p_doc_key);
    v_next   int;
    v_rev    bigint;
    v_locked boolean;
    v_roles  text[];
    v_to     text[];
BEGIN
    IF v_status IS NULL AND NOT EXISTS (SELECT 1 FROM document_revision WHERE doc_type = p_doc_type AND doc_key = p_doc_key) THEN
        -- 첫 버전(v0)은 문서 행보다 먼저 저장될 수 있다 (같은 트랜잭션)
        NULL;
    END IF;
    SELECT coalesce(max(version_no) + 1, 0) INTO v_next FROM document_revision
     WHERE doc_type = p_doc_type AND doc_key = p_doc_key;
    v_locked := v_status = ANY (CASE p_doc_type
        WHEN 'WORK_ORDER'  THEN ARRAY['APPROVED','IN_PROGRESS','DONE','CANCELLED']
        WHEN 'WORK_RECORD' THEN ARRAY['CONFIRMED','CHECKED']
        WHEN 'INTERNAL_DOC' THEN ARRAY['APPROVED']
        ELSE ARRAY['CONFIRMED','REVISED'] END);
    IF v_locked THEN
        IF btrim(coalesce(p_reason, '')) = '' THEN
            RAISE EXCEPTION 'R-35: 확정된 문서(% %)를 고치려면 사유 필수', p_doc_type, p_doc_key USING ERRCODE = '23514';
        END IF;
        -- 확정 뒤 수정은 그 문서의 확정 권한자만 (R-35)
        v_roles := CASE p_doc_type
            WHEN 'SHIFT_REPORT' THEN ARRAY['SUP'] WHEN 'DAILY_REPORT' THEN ARRAY['MGR']
            WHEN 'WORK_RECORD'  THEN ARRAY['MNT','OPR'] WHEN 'WORK_ORDER' THEN ARRAY['MNT','SUP','MGR']
            WHEN 'PM_RECORD'    THEN ARRAY['MNT'] WHEN 'SHIPMENT' THEN ARRAY['SUP']
            WHEN 'INTERNAL_DOC' THEN ARRAY['MGR'] END;
        PERFORM fn_require_role(p_author, v_roles, 'R-35 확정 뒤 수정 (' || p_doc_type || ')');
        IF p_doc_type = 'SHIFT_REPORT' AND p_author <> (SELECT supervisor_user_id FROM shift WHERE shift_id = p_doc_key) THEN
            RAISE EXCEPTION 'R-35: 교대 보고서 확정 뒤 수정은 그 교대 반장만' USING ERRCODE = '23514';
        END IF;
    END IF;
    INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, reason,
                                   status_after, content_snapshot, internal_doc_rev)
    VALUES (p_doc_type, p_doc_key, v_next, p_author_kind, p_author, coalesce(p_at, app_now()), p_reason,
            p_status_after, p_content, p_internal_doc_rev)
    RETURNING revision_id INTO v_rev;
    INSERT INTO document_revision_change (revision_id, field_name, before_value, after_value)
    SELECT v_rev, c->>'field', c->>'before', c->>'after' FROM jsonb_array_elements(p_changes) c;
    -- 문서 수정 알림 (FR-AST-03-07, DOC-07 10.2, 6.36 DOC_REVISED): 확정된 문서를 사유와 함께 고치면
    --   작업지시서 → 담당 보전원, 교대·일일 보고서 → 관리자(MGR), 사내 문서 개정 → 관련 역할 전체. 고친 사람 본인은 뺀다
    IF v_locked THEN
        IF p_doc_type = 'WORK_ORDER' THEN
            SELECT array_remove(ARRAY[assignee_user_id], NULL) INTO v_to FROM maintenance_work_order WHERE wo_no = p_doc_key;
        ELSIF p_doc_type IN ('SHIFT_REPORT','DAILY_REPORT') THEN
            SELECT array_agg(user_id) INTO v_to FROM app_user WHERE is_active AND role_code = 'MGR';
        ELSIF p_doc_type = 'INTERNAL_DOC' THEN
            SELECT array_agg(user_id) INTO v_to FROM app_user WHERE is_active;
        END IF;
        v_to := array_remove(v_to, p_author);
        IF cardinality(v_to) > 0 THEN
            PERFORM fn_raise_notification('DOC_REVISED',
                format('%s %s 수정 (v%s): %s', CASE p_doc_type WHEN 'WORK_ORDER' THEN '작업지시서'
                           WHEN 'SHIFT_REPORT' THEN '교대 보고서' WHEN 'DAILY_REPORT' THEN '일일 보고서' ELSE '사내 문서' END,
                       p_doc_key, v_next, p_reason),
                jsonb_build_object('revision_id', v_rev), p_at, p_recipients => v_to);
        END IF;
    END IF;
    RETURN v_next;
END $$;

-- =====================================================================
-- 3. 로트·검사 (R-25~R-29, R-67~R-69, R-79·R-81)
-- =====================================================================

-- 로트 완료 수량 (R-05): OP-50 공정 실적의 양품 + 재작업
CREATE OR REPLACE FUNCTION fn_lot_completed_qty(p_lot_no text) RETURNS int
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(gq + rq), 0)::int FROM operation_report WHERE lot_no = p_lot_no AND process_code = 'OP-50';
$$;

-- 검사 방식 만들기 (로트를 처음 넣을 때). 열린 보류의 "다음 1~2개 로트"면 강화 (R-28)
CREATE OR REPLACE FUNCTION fn_create_inspection_plan(p_lot_no text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_hold bigint; v_mode text;
BEGIN
    SELECT plan_mode INTO v_mode FROM inspection_plan WHERE lot_no = p_lot_no;
    IF FOUND THEN RETURN v_mode; END IF;
    SELECT h.hold_id INTO v_hold FROM lot_hold h
     WHERE h.lot_no <> p_lot_no
       AND (SELECT count(*) FROM inspection_plan p WHERE p.hold_id = h.hold_id AND p.enhance_reason = 'NEXT_LOT')
           < h.enhanced_next_lots
     ORDER BY h.held_at DESC LIMIT 1;
    IF v_hold IS NOT NULL THEN
        INSERT INTO inspection_plan (lot_no, plan_mode, enhance_reason, hold_id) VALUES (p_lot_no, 'ENHANCED', 'NEXT_LOT', v_hold);
        RETURN 'ENHANCED';
    END IF;
    INSERT INTO inspection_plan (lot_no, plan_mode) VALUES (p_lot_no, 'NORMAL');
    RETURN 'NORMAL';
END $$;

-- 측정할 부품 순번 (R-09): 보통 = 1번과 5의 배수, 강화 = 전부
CREATE OR REPLACE FUNCTION fn_planned_parts(p_lot_no text) RETURNS SETOF int
LANGUAGE sql STABLE AS $$
    SELECT g FROM production_lot l
      JOIN inspection_plan p USING (lot_no)
      CROSS JOIN LATERAL generate_series(1, l.input_qty) g
     WHERE l.lot_no = p_lot_no AND (p.plan_mode = 'ENHANCED' OR g = 1 OR g % 5 = 0);
$$;

-- 로트 보류 (R-27·R-28, FR-PRD-05-06·07). 사람만 (SUP·MGR) — 비서는 제안까지
CREATE OR REPLACE FUNCTION fn_lot_hold(p_lot_no text, p_actor text, p_trigger text, p_reason text,
    p_next_lots int DEFAULT 2, p_alarm_event_id bigint DEFAULT NULL, p_tool_id text DEFAULT NULL,
    p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); v_hold bigint;
BEGIN
    PERFORM 1 FROM production_lot WHERE lot_no = p_lot_no FOR UPDATE;
    IF EXISTS (SELECT 1 FROM shipment_line sl JOIN shipment s USING (shipment_no)
                WHERE sl.lot_no = p_lot_no AND s.status <> 'DRAFT') THEN
        RAISE EXCEPTION '6.8: 이미 출하한 로트 %는 보류할 수 없음', p_lot_no USING ERRCODE = '23514';
    END IF;
    INSERT INTO lot_hold (lot_no, trigger_type, related_alarm_event_id, related_tool_id, hold_reason, held_by, held_at,
                          enhanced_next_lots)
    VALUES (p_lot_no, p_trigger, p_alarm_event_id, p_tool_id, p_reason, p_actor, v_at, p_next_lots)
    RETURNING hold_id INTO v_hold;
    UPDATE production_lot SET status = 'ON_HOLD' WHERE lot_no = p_lot_no;   -- 순서 확인은 트리거
    INSERT INTO inspection_plan (lot_no, plan_mode, enhance_reason, hold_id)
    VALUES (p_lot_no, 'ENHANCED', 'HOLD_LOT', v_hold)
    ON CONFLICT (lot_no) DO UPDATE SET plan_mode = 'ENHANCED', enhance_reason = 'HOLD_LOT', hold_id = v_hold;
    RETURN v_hold;
END $$;

-- 로트 합격 (R-69 ①): 합격 수량(로트 완료 수량)이 완제품 합격 입고 1건으로
CREATE OR REPLACE FUNCTION fn_lot_pass(p_lot_no text, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    l production_lot%ROWTYPE; v_qty int; v_fg text;
BEGIN
    SELECT * INTO l FROM production_lot WHERE lot_no = p_lot_no FOR UPDATE;
    UPDATE production_lot SET status = 'PASSED', judged_at = coalesce(judged_at, v_at) WHERE lot_no = p_lot_no;
    UPDATE inspection_plan SET judgement = 'PASS', judged_at = v_at WHERE lot_no = p_lot_no;
    IF EXISTS (SELECT 1 FROM inventory_txn WHERE source_kind = 'LOT_PASS' AND fg_lot_no = p_lot_no) THEN
        RETURN 0;   -- 해제 때 이미 입고됨 (해제 → 합격)
    END IF;
    v_qty := fn_lot_completed_qty(p_lot_no);   -- 완료 = OP-50 양품 + 재작업 (폐기한 부품은 이미 빠짐)
    SELECT item_no INTO STRICT v_fg FROM inventory_item WHERE category = 'FINISHED';
    IF v_qty > 0 THEN
        INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, fg_lot_no)
        VALUES (v_fg, 'FG_IN', v_qty, v_at, 'LOT_PASS', p_lot_no);
    END IF;
    RETURN v_qty;
END $$;

-- 로트 판정 (R-25·R-27): 측정할 부품을 모두 쟀고 확인 필요 값이 없을 때만.
-- 반환: 'PASS' / 'HOLD_REVIEW' / 'NOT_READY'
CREATE OR REPLACE FUNCTION fn_lot_judge(p_lot_no text, p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    l production_lot%ROWTYPE; p inspection_plan%ROWTYPE; v_missing int; v_fail boolean;
BEGIN
    SELECT * INTO l FROM production_lot WHERE lot_no = p_lot_no FOR UPDATE;
    IF l.status NOT IN ('WAIT_INSPECTION','WAIT_JUDGEMENT') THEN
        RAISE EXCEPTION '로트 %는 판정할 상태가 아님 (%)', p_lot_no, l.status USING ERRCODE = '23514';
    END IF;
    PERFORM fn_create_inspection_plan(p_lot_no);
    SELECT * INTO p FROM inspection_plan WHERE lot_no = p_lot_no;
    IF EXISTS (SELECT 1 FROM inspection_result WHERE lot_no = p_lot_no AND check_status = 'NEEDS_CHECK') THEN
        RETURN 'NOT_READY';
    END IF;
    SELECT count(*) INTO v_missing
      FROM fn_planned_parts(p_lot_no) part
     CROSS JOIN inspection_item i
     WHERE i.product_code = (SELECT product_code FROM production_order WHERE order_no = l.order_no)
       AND i.method = 'CMM' AND i.in_sampling
       AND NOT EXISTS (SELECT 1 FROM inspection_result r
                        WHERE r.lot_no = p_lot_no AND r.part_seq = part AND r.item_seq = i.item_seq AND r.use_for_judgement);
    IF v_missing > 0 THEN
        IF l.status = 'WAIT_INSPECTION' THEN
            UPDATE production_lot SET status = 'WAIT_JUDGEMENT' WHERE lot_no = p_lot_no;
        END IF;
        RETURN 'NOT_READY';
    END IF;
    v_fail := EXISTS (SELECT 1 FROM inspection_result WHERE lot_no = p_lot_no AND use_for_judgement AND judgement = 'FAIL')
              OR EXISTS (SELECT 1 FROM inspection_result WHERE lot_no = p_lot_no AND input_method = 'TABLET' AND judgement = 'FAIL')
              OR coalesce(p.gauge_fail_qty, 0) > 0;
    IF v_fail THEN
        UPDATE production_lot SET status = 'HOLD_REVIEW', judged_at = v_at WHERE lot_no = p_lot_no;
        UPDATE inspection_plan SET judgement = 'HOLD_REVIEW', judged_at = v_at WHERE lot_no = p_lot_no;
        RETURN 'HOLD_REVIEW';
    END IF;
    PERFORM fn_lot_pass(p_lot_no, v_at);
    RETURN 'PASS';
END $$;

-- 로트 해제 (R-69 ②): 전수 검사로 고른 합격 수량만 완제품으로
CREATE OR REPLACE FUNCTION fn_lot_release(p_hold_id bigint, p_actor text, p_pass_qty int, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); h lot_hold%ROWTYPE; v_fg text;
BEGIN
    SELECT * INTO h FROM lot_hold WHERE hold_id = p_hold_id FOR UPDATE;
    IF h.result <> 'IN_PROGRESS' THEN RAISE EXCEPTION '보류 %는 이미 끝남 (%)', p_hold_id, h.result USING ERRCODE = '23514'; END IF;
    -- [제안] 해제 = 전수 검사로 골라낸 합격품을 출하 가능으로 (6.8). 합격 0개면 해제가 아니라 폐기로 간다
    IF coalesce(p_pass_qty, 0) <= 0 THEN
        RAISE EXCEPTION '해제 합격 수량은 1개 이상 (로트 % 완료 수량 %) — 전부 불량이면 폐기, 생산 중이면 검사 뒤 해제',
            h.lot_no, fn_lot_completed_qty(h.lot_no) USING ERRCODE = '23514';
    END IF;
    IF p_pass_qty > fn_lot_completed_qty(h.lot_no) THEN
        RAISE EXCEPTION '해제 합격 수량 %가 로트 완료 수량보다 많음', p_pass_qty USING ERRCODE = '23514';
    END IF;
    UPDATE lot_hold SET result = 'RELEASED', released_by = p_actor, released_at = v_at, released_pass_qty = p_pass_qty
     WHERE hold_id = p_hold_id;
    UPDATE production_lot SET status = 'RELEASED' WHERE lot_no = h.lot_no;
    SELECT item_no INTO STRICT v_fg FROM inventory_item WHERE category = 'FINISHED';
    IF p_pass_qty > 0 THEN
        INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, fg_lot_no)
        VALUES (v_fg, 'FG_IN', p_pass_qty, v_at, 'LOT_PASS', h.lot_no);
    END IF;
END $$;

-- 폐기: SUP 제안 → MGR 승인 (R-27, FR-PRD-05-08)
CREATE OR REPLACE FUNCTION fn_lot_scrap_propose(p_hold_id bigint, p_actor text, p_qty int) RETURNS void
LANGUAGE sql AS $$
    UPDATE lot_hold SET scrap_proposed_by = p_actor, scrap_proposed_qty = p_qty WHERE hold_id = p_hold_id AND result = 'IN_PROGRESS';
$$;
CREATE OR REPLACE FUNCTION fn_lot_scrap_approve(p_hold_id bigint, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE h lot_hold%ROWTYPE; v_at timestamptz := coalesce(p_at, app_now());
BEGIN
    SELECT * INTO h FROM lot_hold WHERE hold_id = p_hold_id FOR UPDATE;
    IF h.result <> 'IN_PROGRESS' OR h.scrap_proposed_by IS NULL THEN
        RAISE EXCEPTION '폐기 승인은 반장의 폐기 제안이 있는 열린 보류만' USING ERRCODE = '23514';
    END IF;
    UPDATE lot_hold SET result = 'SCRAPPED', scrap_approved_by = p_actor, scrap_approved_at = v_at WHERE hold_id = p_hold_id;
    UPDATE production_lot SET status = 'SCRAPPED', scrap_qty = least(input_qty, coalesce(h.scrap_proposed_qty, input_qty))
     WHERE lot_no = h.lot_no;
END $$;

-- 출하 확정 (R-67 합격 로트만, R-68 FIFO, 출하 출고 거래). 반환: 로트 줄 수
CREATE OR REPLACE FUNCTION fn_confirm_shipment(p_shipment_no text, p_actor text, p_fifo_skip_reason text DEFAULT NULL,
                                               p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at  timestamptz := coalesce(p_at, app_now());
    s shipment%ROWTYPE; ln record; v_fg text; v_n int := 0; v_maxkey text; v_skipped text;
BEGIN
    SELECT * INTO s FROM shipment WHERE shipment_no = p_shipment_no FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '출하 % 없음', p_shipment_no USING ERRCODE = '23503'; END IF;
    IF s.status <> 'DRAFT' THEN RAISE EXCEPTION '출하 %는 작성 중이 아님 (%)', p_shipment_no, s.status USING ERRCODE = '23514'; END IF;
    PERFORM fn_require_role(p_actor, ARRAY['SUP'], '출하 확정');
    SELECT item_no INTO STRICT v_fg FROM inventory_item WHERE category = 'FINISHED';

    FOR ln IN
        SELECT sl.lot_no, sl.qty, l.status,
               (SELECT t.txn_at FROM inventory_txn t WHERE t.source_kind = 'LOT_PASS' AND t.fg_lot_no = sl.lot_no) AS passed_at,
               (SELECT coalesce(sum(t.qty_change), 0) FROM inventory_txn t
                 WHERE t.item_no = v_fg AND (t.fg_lot_no = sl.lot_no OR t.ship_lot_no = sl.lot_no)) AS remaining
          FROM shipment_line sl JOIN production_lot l USING (lot_no)
         WHERE sl.shipment_no = p_shipment_no
         FOR UPDATE OF l
    LOOP
        v_n := v_n + 1;
        IF ln.status NOT IN ('PASSED','RELEASED') OR ln.passed_at IS NULL THEN
            RAISE EXCEPTION 'R-67: 로트 %는 출하할 수 없음 (상태 %)', ln.lot_no, ln.status USING ERRCODE = '23514';
        END IF;
        IF v_at <= ln.passed_at THEN
            RAISE EXCEPTION 'R-67: 출하 시각이 로트 % 합격 시각보다 빠름', ln.lot_no USING ERRCODE = '23514';
        END IF;
        IF ln.qty > ln.remaining THEN
            RAISE EXCEPTION 'R-67: 로트 % 출하 수량 %가 남은 완제품 %보다 많음', ln.lot_no, ln.qty, ln.remaining
                USING ERRCODE = '23514';
        END IF;
        UPDATE shipment_line SET lot_passed_at = ln.passed_at WHERE shipment_no = p_shipment_no AND lot_no = ln.lot_no;
    END LOOP;
    IF v_n = 0 THEN RAISE EXCEPTION '출하 %에 로트 줄이 없음', p_shipment_no USING ERRCODE = '23514'; END IF;

    -- R-68 FIFO: 이번 출하에서 가장 늦게 합격한 로트보다 먼저 합격했는데 빠진 로트(남은 수량 > 0)가 있으면 사유 필수
    -- 순서 = 합격 날짜(한국 시간) → 로트 번호
    SELECT max(to_char(sl.lot_passed_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD') || '|' || sl.lot_no) INTO v_maxkey
      FROM shipment_line sl WHERE sl.shipment_no = p_shipment_no;
    SELECT string_agg(c.lot_no, ', ' ORDER BY c.lot_no) INTO v_skipped
      FROM (SELECT l.lot_no, t.txn_at,
                   (SELECT coalesce(sum(x.qty_change), 0) FROM inventory_txn x
                     WHERE x.item_no = v_fg AND (x.fg_lot_no = l.lot_no OR x.ship_lot_no = l.lot_no)) AS remaining
              FROM production_lot l
              JOIN inventory_txn t ON t.source_kind = 'LOT_PASS' AND t.fg_lot_no = l.lot_no
             WHERE l.status IN ('PASSED','RELEASED')
               AND l.lot_no NOT IN (SELECT lot_no FROM shipment_line WHERE shipment_no = p_shipment_no)) c
     WHERE c.remaining > 0
       AND to_char(c.txn_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD') || '|' || c.lot_no < v_maxkey;
    IF v_skipped IS NOT NULL AND btrim(coalesce(p_fifo_skip_reason, '')) = '' THEN
        RAISE EXCEPTION 'R-68: 먼저 합격한 로트(%)를 두고 나중 로트를 고름 — FIFO 건너뜀 사유 필수', v_skipped
            USING ERRCODE = '23514';
    END IF;

    UPDATE shipment SET status = 'CONFIRMED', confirmed_by = p_actor, shipped_at = v_at,
                        fifo_skip_reason = CASE WHEN v_skipped IS NOT NULL THEN p_fifo_skip_reason END
     WHERE shipment_no = p_shipment_no;
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, shipment_no, ship_lot_no)
    SELECT v_fg, 'SHIP_OUT', -sl.qty, v_at, p_actor, 'SHIPMENT', sl.shipment_no, sl.lot_no
      FROM shipment_line sl WHERE sl.shipment_no = p_shipment_no;
    RETURN v_n;
END $$;

-- =====================================================================
-- 4. 공구 (R-10·R-40·R-41)
-- =====================================================================

-- 공정 실적에 부품 수만큼 공구 사용량을 더한다 (공구 사용 기록 B안: 교체가 끼면 구간을 나눔)
CREATE OR REPLACE FUNCTION fn_add_tool_usage(p_op_report_id bigint, p_parts_qty int, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    op operation_report%ROWTYPE; t record; cur tool_usage%ROWTYPE; v_change tool_change%ROWTYPE;
    v_usage numeric; v_new_cum numeric; v_n int := 0;
BEGIN
    SELECT * INTO op FROM operation_report WHERE op_report_id = p_op_report_id;
    IF op.process_code <> 'OP-30' THEN RETURN 0; END IF;
    FOR t IN SELECT tl.tool_id, tl.cum_usage, tt.usage_per_part, tt.life_limit
               FROM tool tl JOIN tool_type tt USING (item_no)
              WHERE tl.equipment_id = op.equipment_id AND tl.tool_role = 'IN_USE' AND tl.is_active
              FOR UPDATE OF tl
    LOOP
        v_usage := p_parts_qty * t.usage_per_part;
        v_new_cum := t.cum_usage + v_usage;
        SELECT * INTO v_change FROM tool_change
         WHERE tool_id = t.tool_id AND changed_at >= op.start_at AND changed_at <= v_at
         ORDER BY changed_at DESC LIMIT 1;
        SELECT * INTO cur FROM tool_usage WHERE tool_id = t.tool_id AND op_report_id = p_op_report_id
         ORDER BY seg DESC LIMIT 1;
        IF cur.seg IS NULL THEN
            INSERT INTO tool_usage VALUES (t.tool_id, p_op_report_id, 1, p_parts_qty, v_usage, v_new_cum, v_change.tool_change_id, v_at);
        ELSIF v_change.tool_change_id IS NOT NULL AND cur.tool_change_id IS DISTINCT FROM v_change.tool_change_id
              AND v_change.changed_at > cur.recorded_at THEN
            INSERT INTO tool_usage VALUES (t.tool_id, p_op_report_id, cur.seg + 1, p_parts_qty, v_usage, v_new_cum, v_change.tool_change_id, v_at);
        ELSE
            UPDATE tool_usage SET parts_qty = parts_qty + p_parts_qty, usage_qty = usage_qty + v_usage,
                                  cum_after = v_new_cum, recorded_at = v_at
             WHERE tool_id = t.tool_id AND op_report_id = p_op_report_id AND seg = cur.seg;
        END IF;
        UPDATE tool SET cum_usage = v_new_cum WHERE tool_id = t.tool_id;
        -- R-40 사용률 90%를 넘는 순간 교체 알림 (열린 것이 없을 때만)
        IF v_new_cum >= 0.9 * t.life_limit AND t.cum_usage < 0.9 * t.life_limit
           AND NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TOOL_LIFE_90' AND tool_id = t.tool_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('TOOL_LIFE_90',
                format('%s 공구 수명 %s%% — 교체 준비', t.tool_id, round(100 * v_new_cum / t.life_limit)),
                jsonb_build_object('tool_id', t.tool_id, 'equipment_id', op.equipment_id), v_at);
        END IF;
        v_n := v_n + 1;
    END LOOP;
    RETURN v_n;
END $$;

-- 공구 교체: 교체 기록 + 누적 0 + 재고 차감(페이스밀 5개) + 수명 알림 자동 처리
CREATE OR REPLACE FUNCTION fn_tool_change(p_tool_id text, p_actor text, p_reason text,
                                          p_alarm_event_id bigint DEFAULT NULL, p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now()); t record; v_id bigint; v_open bigint[];
BEGIN
    SELECT tl.*, tt.deduct_qty_per_change INTO t FROM tool tl JOIN tool_type tt USING (item_no)
     WHERE tl.tool_id = p_tool_id FOR UPDATE OF tl;
    IF NOT FOUND THEN RAISE EXCEPTION '공구 % 없음', p_tool_id USING ERRCODE = '23503'; END IF;
    INSERT INTO tool_change (tool_id, changed_at, changed_by, cum_before, change_reason, related_alarm_event_id)
    VALUES (p_tool_id, v_at, p_actor, t.cum_usage, p_reason, p_alarm_event_id)
    RETURNING tool_change_id INTO v_id;
    UPDATE tool SET cum_usage = 0, last_changed_at = v_at WHERE tool_id = p_tool_id;
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, tool_change_id)
    VALUES (t.item_no, 'USE', -t.deduct_qty_per_change, v_at, p_actor, 'TOOL_CHANGE', v_id);
    SELECT array_agg(notification_id) INTO v_open FROM notification
     WHERE rule_code = 'TOOL_LIFE_90' AND tool_id = p_tool_id AND NOT is_processed;
    IF v_open IS NOT NULL THEN PERFORM fn_auto_process(v_open, p_actor, v_at); END IF;
    PERFORM fn_check_stock(t.item_no, p_actor, v_at);
    RETURN v_id;
END $$;

-- =====================================================================
-- 5. 정비 (R-02·R-32·R-34·R-70·R-71)
-- =====================================================================

-- 작업기록 확정: 잠금·표지·역할 확인(트리거) → 사용 부품 재고 차감 → 작업지시서 완료 → 알림 자동 처리
CREATE OR REPLACE FUNCTION fn_confirm_work_record(p_record_no text, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    w work_record%ROWTYPE; v_alarm bigint; v_ids bigint[]; v_stage bigint; p record;
BEGIN
    SELECT * INTO w FROM work_record WHERE record_no = p_record_no FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '작업기록 % 없음', p_record_no USING ERRCODE = '23503'; END IF;
    IF w.status NOT IN ('AI_DRAFT','EDITING') THEN
        RAISE EXCEPTION '작업기록 %는 확정할 상태가 아님 (%)', p_record_no, w.status USING ERRCODE = '23514';
    END IF;
    UPDATE work_record
       SET status = 'CONFIRMED', confirmed_by = p_actor, confirmed_at = v_at, end_at = coalesce(end_at, v_at),
           repair_min = coalesce(repair_min, round(extract(epoch FROM (coalesce(end_at, v_at) - start_at)) / 60, 2))
     WHERE record_no = p_record_no;

    -- R-34 사용 부품만큼 재고 사용 거래
    FOR p IN SELECT * FROM work_record_part WHERE record_no = p_record_no LOOP
        INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, txn_by, source_kind, work_record_no, work_record_item_no)
        VALUES (p.item_no, 'USE', -p.qty, v_at, p_actor, 'WORK_RECORD', p_record_no, p.item_no);
        PERFORM fn_check_stock(p.item_no, p_actor, v_at);
    END LOOP;

    v_alarm := w.alarm_event_id;
    IF w.record_type = 'FULL' THEN
        -- 작업지시서 완료 계기 = 짝 작업기록서 확정 (6.13)
        UPDATE maintenance_work_order SET status = 'DONE', completed_at = v_at WHERE wo_no = w.wo_no
        RETURNING coalesce(v_alarm, alarm_event_id), trigger_notification_id INTO v_alarm, v_stage;
        IF v_stage IS NOT NULL THEN
            UPDATE notification SET repeat_stage_status = 'S2_CHECKED', effect_check_due_at = v_at + interval '7 days'
             WHERE notification_id = v_stage;
            PERFORM fn_auto_process(ARRAY[v_stage], p_actor, v_at);
        END IF;
    END IF;
    -- 알람 알림 자동 처리 (6.36: ALARM_STOP·ALARM_WARN)
    IF v_alarm IS NOT NULL THEN
        SELECT array_agg(notification_id) INTO v_ids FROM notification
         WHERE alarm_event_id = v_alarm AND rule_code IN ('ALARM_STOP','ALARM_WARN') AND NOT is_processed;
        IF v_ids IS NOT NULL THEN PERFORM fn_auto_process(v_ids, p_actor, v_at); END IF;
    END IF;
    -- 다른 공정 원인 점검 간이 기록 → 원인 점검 요청·2단계 알림 처리 (R-70)
    IF w.cause_check_notification_id IS NOT NULL THEN
        SELECT prev_stage_notification_id INTO v_stage FROM notification WHERE notification_id = w.cause_check_notification_id;
        PERFORM fn_auto_process(ARRAY[w.cause_check_notification_id], p_actor, v_at);
        IF v_stage IS NOT NULL THEN
            UPDATE notification SET repeat_stage_status = 'S2_CHECKED', effect_check_due_at = v_at + interval '7 days'
             WHERE notification_id = v_stage;
            PERFORM fn_auto_process(ARRAY[v_stage], p_actor, v_at);
        END IF;
    END IF;
END $$;

-- 반복 알람 판정 (R-70): 알람 1건이 들어온 뒤 부른다. 반환: 'NONE' / 'STAGE1' / 'STAGE2'
--   1단계 = 같은 설비·같은 알람 7일 안 3번 이상 (조치 진행 중인 알람은 빼고 센다 — 1분 묶음은 1번)
--   2단계 = 1단계 닫힘(조치 계획 저장) 뒤 7일 안에 다시 남
-- 문장(message)은 기본 문구. 비서 문장은 AI 비서 ②가 나중에 고친다 (message_source = ASSISTANT)
CREATE OR REPLACE FUNCTION fn_check_repeat_alarm(p_alarm_event_id bigint) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    a alarm_event%ROWTYPE; v_cnt int; v_prev notification%ROWTYPE; v_id bigint; v_proc text;
BEGIN
    SELECT * INTO a FROM alarm_event WHERE alarm_event_id = p_alarm_event_id;
    -- 이미 열린 1·2단계가 있으면 새로 만들지 않는다 (재발로 2단계가 될지만 본다)
    SELECT n.* INTO v_prev FROM notification n JOIN alarm_event e USING (alarm_event_id)
     WHERE n.rule_code IN ('REPEAT_ALARM','REPEAT_ALARM_2') AND e.equipment_id = a.equipment_id
       AND e.alarm_code = a.alarm_code AND n.repeat_stage_status IN ('S1_CLOSED','S2_CHECKED','S1_OPEN','S2_OPEN')
     ORDER BY n.raised_at DESC LIMIT 1;
    IF v_prev.notification_id IS NOT NULL THEN
        IF v_prev.repeat_stage_status IN ('S1_OPEN','S2_OPEN') THEN RETURN 'NONE'; END IF;
        IF a.occurred_at <= v_prev.effect_check_due_at THEN
            UPDATE notification SET repeat_stage_status = 'ESCALATED' WHERE notification_id = v_prev.notification_id;
            v_id := fn_raise_notification('REPEAT_ALARM_2',
                format('%s 알람 %s — 지난 조치 효과 없음 (조치 뒤 7일 안 재발)', a.equipment_id, a.alarm_code),
                jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id),
                a.occurred_at, p_repeat_stage => 'S2_OPEN', p_prev_stage => v_prev.notification_id);
            v_proc := fn_equipment_process(a.equipment_id);
            IF v_proc <> 'OP-30' THEN
                -- 다른 공정: 작업지시서 없이 MNT에게 원인 점검 요청 (R-71)
                PERFORM fn_raise_notification('CAUSE_CHECK_REQUEST',
                    format('%s 알람 %s 원인 점검 요청', a.equipment_id, a.alarm_code),
                    jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id),
                    a.occurred_at, p_prev_stage => v_id);
            END IF;
            RETURN 'STAGE2';
        END IF;
        UPDATE notification SET repeat_stage_status = 'EFFECTIVE'
         WHERE notification_id = v_prev.notification_id AND repeat_stage_status IN ('S1_CLOSED','S2_CHECKED');
    END IF;
    SELECT count(DISTINCT date_trunc('minute', e.occurred_at)) INTO v_cnt FROM alarm_event e
     WHERE e.equipment_id = a.equipment_id AND e.alarm_code = a.alarm_code
       AND e.occurred_at > a.occurred_at - interval '7 days' AND e.occurred_at <= a.occurred_at
       AND NOT EXISTS (SELECT 1 FROM work_record w WHERE w.alarm_event_id = e.alarm_event_id AND w.status IN ('AI_DRAFT','EDITING')
                         AND w.alarm_event_id <> a.alarm_event_id);
    IF v_cnt >= 3 THEN
        PERFORM fn_raise_notification('REPEAT_ALARM',
            format('%s 알람 %s 7일 안 %s번', a.equipment_id, a.alarm_code, v_cnt),
            jsonb_build_object('alarm_event_id', a.alarm_event_id, 'equipment_id', a.equipment_id),
            a.occurred_at, p_repeat_stage => 'S1_OPEN');
        RETURN 'STAGE1';
    END IF;
    RETURN 'NONE';
END $$;

-- =====================================================================
-- 6. 교대 목표 이월·총 목표 (R-46·R-88, DOC-07 §4.1 — 2026-10-07 팀 UI 검토)
--   이월은 같은 생산일 주간 → 야간만: 야간 carry_over_qty = max(0, 주간 목표 − 주간 실적). 주간은 늘 0.
--   총 목표 = target_qty + carry_over_qty. 하루 목표(work_day.daily_target_qty 180)는 고정 — 이월을 더하지 않고,
--   야간이 못 채운 수량은 다음 날로 넘기지 않고 그날 부족(180 − 하루 실적)으로 남는다.
-- =====================================================================

-- R-46 교대 실적 = 그 교대에 OP-50을 마친 GQ + RQ (원기록 집계)
CREATE OR REPLACE FUNCTION fn_shift_actual_qty(p_shift_id text) RETURNS int
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(gq + rq), 0)::int FROM operation_report WHERE shift_id = p_shift_id AND process_code = 'OP-50';
$$;

-- 그 생산일 야간 이월을 다시 계산한다. 반환: 야간 이월 값 (그날 야간 교대가 없으면 NULL)
--   주간 실적 = 주간 교대 보고서가 확정됐으면 그 실적, 아니면 원기록 집계 (이때 이월은 "잠정" — v_shift_target)
--   주간 기록(교대 보고서도 공정 실적도)이 없으면 0
-- 부르는 곳: 주간 교대 보고서 초안(17:00, 야간 시작 전), 주간 교대 보고서 확정(다시 계산), 스케줄러(지금 야간),
--           생성기 데이터 적재 뒤(tools/load_generated.py)
CREATE OR REPLACE FUNCTION fn_refresh_carry_over(p_work_date date) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE
    d shift%ROWTYPE; v_night shift%ROWTYPE; v_confirmed int; v_carry int := 0;
BEGIN
    SELECT * INTO v_night FROM shift WHERE work_date = p_work_date AND shift_type = 'NIGHT';
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT * INTO d FROM shift WHERE work_date = p_work_date AND shift_type = 'DAY';
    IF FOUND AND (EXISTS (SELECT 1 FROM shift_report r WHERE r.shift_id = d.shift_id)
                  OR EXISTS (SELECT 1 FROM operation_report o WHERE o.shift_id = d.shift_id)) THEN
        SELECT r.actual_qty INTO v_confirmed FROM shift_report r
         WHERE r.shift_id = d.shift_id AND r.status IN ('CONFIRMED','REVISED');
        v_carry := greatest(0, d.target_qty - coalesce(v_confirmed, fn_shift_actual_qty(d.shift_id)));
    END IF;
    UPDATE shift SET carry_over_qty = v_carry WHERE shift_id = v_night.shift_id AND carry_over_qty <> v_carry;
    -- 아직 확정 전인 야간 교대 보고서 초안의 총 목표(프로그램 칸)도 맞춘다. 확정된 보고서는 고치지 않는다 (R-35)
    UPDATE shift_report SET target_qty = v_night.target_qty + v_carry
     WHERE shift_id = v_night.shift_id AND status IN ('AI_DRAFT','EDITING') AND target_qty <> v_night.target_qty + v_carry;
    RETURN v_carry;
END $$;

-- 고장 손실 수량 (추정, R-47·DOC-07 5.3): [p_from, p_to) 안에서 시작한 고장 정지 구간(정지 사유 FAILURE 그룹, 또는 DOWN)의
-- 정지 손실 합. 아직 끝나지 않은 구간은 p_to까지의 길이 ÷ 그 설비 기준 사이클로 센다 (3D 라인 뷰 "지금까지 손실")
CREATE OR REPLACE FUNCTION fn_failure_loss_qty(p_from timestamptz, p_to timestamptz) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(round(sum(CASE WHEN st.end_at IS NULL OR st.end_at > p_to
                                   THEN extract(epoch FROM (p_to - st.start_at)) / 60 / nullif(e.std_cycle_min, 0)
                                   ELSE st.stop_loss_qty END), 2), 0)
      FROM equipment_state_log st
      JOIN equipment e USING (equipment_id)
      LEFT JOIN downtime_reason dr ON dr.reason_code = coalesce(st.reason_code, st.reason_suggested_code)
     WHERE st.state_code <> 'RUN' AND (st.state_code = 'DOWN' OR dr.reason_group = 'FAILURE')
       AND st.start_at >= p_from AND st.start_at < p_to;
$$;

-- 속도 손실 수량 (추정, R-47): [p_from, p_to) 안에서 바뀐 병목 구간의 속도 손실 합 (구간이 끝날 때 저장된 값)
CREATE OR REPLACE FUNCTION fn_speed_loss_qty(p_from timestamptz, p_to timestamptz) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(speed_loss_qty), 0) FROM bottleneck_log WHERE changed_at >= p_from AND changed_at < p_to;
$$;

-- =====================================================================
-- 7. 알람 관련 재고 품목 (alarm_related_item, 논리 ERD 5.C.8·R-89) — 보고 순위 같은 원인 묶기
--   사내 문서에 적힌 연결만. 알람 코드집·재고 품목은 생성기·목업이 넣으므로, 있는 코드만 넣고 여러 번 불러도 된다.
--   부르는 곳: 시드(seed/40), 목업(dev/10), 생성기 적재 뒤(tools/load_generated.py). 반환: 새로 넣은 줄 수
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_seed_alarm_related_items() RETURNS int
LANGUAGE sql AS $$
    WITH ins AS (
        INSERT INTO alarm_related_item (alarm_code, item_no, relation_note, source_section)
        SELECT v.alarm_code, v.item_no, v.note, v.src
          FROM (VALUES
            ('2075', 'CS-WLUB', '축 윤활유 저장소가 비면 나는 알람 — 탱크를 채운다 (매월 윤활유 저장소 양 점검·보충)',
             '알람 코드집 DOC-02 §4.11, 예방 정비 기준서 DOC-04 §4.1'),
            ('2073', 'CS-WLUB', '축 윤활 압력 감지 불능 — 윤활유 탱크를 먼저 본다. 2075를 두면 2073으로 이어짐',
             '알람 코드집 DOC-02 §4.10, 예방 정비 기준서 DOC-04 §4.1'),
            ('805',  'CS-SLUB', '주축 윤활 부족 — 주축 윤활유 저장소 양이 적음 (매월 탱크 양 점검 때 보충)',
             '예방 정비 기준서 DOC-04 §4.4')
          ) AS v(alarm_code, item_no, note, src)
         WHERE EXISTS (SELECT 1 FROM alarm_master m WHERE m.alarm_code = v.alarm_code)
           AND EXISTS (SELECT 1 FROM inventory_item i WHERE i.item_no = v.item_no)
        ON CONFLICT (alarm_code, item_no) DO NOTHING
        RETURNING 1)
    SELECT count(*)::int FROM ins;
$$;

-- 불량을 폐기로 처분하면 로트 폐기 수량을 더한다 (production_lot.scrap_qty = 폐기한 부품 수, 생성기와 같은 뜻).
-- 로트 전체 폐기(보류 → 폐기 승인)는 fn_lot_scrap_approve가 따로 채운다. 대량 적재 중에는 CSV 값을 그대로 둔다
CREATE OR REPLACE FUNCTION trg_defect_scrap() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.disposition = 'SCRAP' AND current_setting('app.loading', true) IS DISTINCT FROM 'on' THEN
        UPDATE production_lot SET scrap_qty = least(input_qty, scrap_qty + NEW.qty) WHERE lot_no = NEW.lot_no;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER defect_scrap AFTER INSERT ON defect_record FOR EACH ROW EXECUTE FUNCTION trg_defect_scrap();

-- 생성기 적재 뒤 "지금 상태" 칸 맞추기 (tools/load_generated.py가 부름). 기준 정보 CSV(masters)는 9/1 시작 상태라서
--   공구 누적 사용량·마지막 교체 시각 = 마지막 사용·교체 기록 (R-10, T05 9/30 끝 90% — 1014 수정사항 3.1)
-- 반환: 고친 공구 수
CREATE OR REPLACE FUNCTION fn_sync_after_load() RETURNS int LANGUAGE plpgsql AS $$
DECLARE n int;
BEGIN
    WITH last_use AS (
        SELECT DISTINCT ON (tool_id) tool_id, cum_after, recorded_at FROM tool_usage ORDER BY tool_id, recorded_at DESC, seg DESC
    ), last_change AS (
        SELECT tool_id, max(changed_at) AS changed_at FROM tool_change GROUP BY tool_id
    ), u AS (
        UPDATE tool t SET cum_usage = CASE WHEN c.changed_at IS NOT NULL AND (lu.recorded_at IS NULL OR lu.recorded_at < c.changed_at)
                                           THEN 0 ELSE coalesce(lu.cum_after, t.cum_usage) END,
                          last_changed_at = coalesce(c.changed_at, t.last_changed_at)
          FROM tool t2 LEFT JOIN last_use lu USING (tool_id) LEFT JOIN last_change c USING (tool_id)
         WHERE t.tool_id = t2.tool_id AND (lu.tool_id IS NOT NULL OR c.tool_id IS NOT NULL)
        RETURNING 1)
    SELECT count(*) INTO n FROM u;
    -- 10/1 실시간 기록의 예방 정비 기록(작성 중 DRAFT)은 문서 버전이 없다 → 사람이 처음 저장한 v0을 남긴다 (R-35)
    INSERT INTO document_revision (doc_type, doc_key, version_no, author_kind, author_user_id, created_at, reason, status_after,
                                   content_snapshot)
    SELECT 'PM_RECORD', p.pm_record_id::text, 0, 'HUMAN', p.recorded_by, p.done_at, NULL, p.status,
           jsonb_build_object('pm_task_id', p.pm_task_id, 'result', p.result, 'memo', p.memo)
      FROM pm_record p
     WHERE p.current_version = 0
       AND NOT EXISTS (SELECT 1 FROM document_revision r WHERE r.doc_type = 'PM_RECORD' AND r.doc_key = p.pm_record_id::text);
    -- 교대 보고서가 아직 없는 날(10/1 실시간)의 야간 이월 (R-88)
    PERFORM fn_refresh_carry_over(w.work_date) FROM work_day w
     WHERE EXISTS (SELECT 1 FROM shift s WHERE s.work_date = w.work_date)
       AND NOT EXISTS (SELECT 1 FROM shift s JOIN shift_report r USING (shift_id) WHERE s.work_date = w.work_date);
    RETURN n;
END $$;

-- ===================== db/functions/40_cmm_import.sql =====================
-- =====================================================================
-- 40_cmm_import.sql — OP-50 측정 결과 파일 자동 기록 (R-78~R-82, DOC-06 Rev.2 §3.6)
-- 파일 읽기(CSV 해석)는 서버(app/domain/cmm_csv.py)가 하고, 해석된 값을 이 함수에 넘긴다.
--   양식 오류(열 빠짐·숫자 아님)로 해석 못 하면 → fn_record_cmm_failure (기록 안 함, 알림)
--   해석되면 → fn_import_cmm (지시와 대조, 판정 다시 계산, 재측정 보관)
-- =====================================================================

CREATE OR REPLACE FUNCTION fn_record_cmm_failure(p_file_name text, p_file_ref text, p_error_kind text,
    p_error_text text, p_header jsonb DEFAULT '{}'::jsonb, p_received_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_id bigint; v_at timestamptz := coalesce(p_received_at, app_now());
BEGIN
    INSERT INTO cmm_import (file_name, received_at, status, error_kind, error_text, original_file_ref,
                            format_version, sample_no_raw, raw_header)
    VALUES (p_file_name, v_at, 'FAILED', p_error_kind, p_error_text, p_file_ref,
            p_header->>'format', p_header->>'sample_no', p_header)
    RETURNING cmm_import_id INTO v_id;
    PERFORM fn_raise_notification('CMM_FILE_ERROR', format('측정 결과 파일을 읽지 못함: %s (%s)', p_file_name, p_error_text),
                                  jsonb_build_object('cmm_import_id', v_id), v_at);
    RETURN v_id;
END $$;

-- p_header (app/domain/cmm_csv.py가 만든 값):
--   {format, cmm_id, program, lot_no, part_seq, sample_no, insp_kind, operator, measured_at,
--    measure_start_at, measure_end_at, room_temp_c, part_temp_c, machine_temp_c, temp_comp, ...그 밖 머리 칸}
-- p_rows: [{item_seq, position, actual, cmm_judgement}]  (position: 빈칸·없음 = 표준, TOP/MID/BOTTOM)
-- 반환: cmm_import_id
CREATE OR REPLACE FUNCTION fn_import_cmm(p_file_name text, p_file_ref text, p_header jsonb, p_rows jsonb,
                                         p_received_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at        timestamptz := coalesce(p_received_at, app_now());
    v_lot       text := p_header->>'lot_no';
    v_part      int  := (p_header->>'part_seq')::int;
    v_kind      text := p_header->>'insp_kind';
    v_measured  timestamptz := coalesce((p_header->>'measure_end_at')::timestamptz, (p_header->>'measured_at')::timestamptz);
    v_product   text;
    v_instr     cmm_instruction%ROWTYPE;
    v_import    bigint;
    v_status    text := 'SUCCESS';
    v_err_kind  text;
    v_err_text  text;
    v_inspector text;
    v_missing   text;
    rw          jsonb;
    it          inspection_item%ROWTYPE;
    v_value     numeric;
    v_judge     text;
    v_cmm       text;
    v_pos       text;
    v_reseq     int;
    v_check     text;
    v_result    bigint;
    v_mismatch  bigint[] := '{}';
BEGIN
    SELECT o.product_code INTO v_product FROM production_lot l JOIN production_order o USING (order_no) WHERE l.lot_no = v_lot;
    IF v_product IS NULL THEN
        -- 없는 로트면 측정값을 기록할 곳이 없다 → 실패
        RETURN fn_record_cmm_failure(p_file_name, p_file_ref, 'LOT_MISMATCH',
            format('결과 파일의 로트 %s가 없음', coalesce(v_lot, '(비어 있음)')), p_header, v_at);
    END IF;

    -- R-78 측정 지시와 같아야 정상
    SELECT * INTO v_instr FROM cmm_instruction
     WHERE lot_no = v_lot AND part_seq = v_part AND insp_kind = v_kind AND status IN ('ISSUED','STARTED')
     ORDER BY issued_at DESC LIMIT 1;
    IF v_instr.instruction_id IS NULL THEN
        v_status := 'NEEDS_CHECK'; v_err_kind := 'LOT_MISMATCH';
        v_err_text := format('지시와 다름: 로트 %s 순번 %s %s에 열린 측정 지시가 없음', v_lot, v_part, v_kind);
    END IF;

    -- 측정자: 측정 시작 때 태블릿에서 확인한 사람 → 파일의 operator (사용자로 있을 때만) → 그 시각 교대의 측정 담당
    --   (OP-50 담당 OPR — 두 번째 담당 공정 포함, P-45 [제안]). 생성기 10/1 결과 파일에는 operator 칸이 없다 (2026-10-14)
    v_inspector := coalesce(v_instr.started_by,
                            (SELECT user_id FROM app_user WHERE user_id = p_header->>'operator' AND role_code = 'OPR'),
                            (SELECT u.user_id FROM app_user u JOIN shift s ON s.shift_type = u.home_shift_type
                              WHERE u.is_active AND u.role_code = 'OPR' AND 'OP-50' IN (u.home_process_code, u.home_process_code_2)
                                AND coalesce(v_measured, v_at) >= s.start_at AND coalesce(v_measured, v_at) < s.end_at + interval '3 hours'
                              ORDER BY s.start_at DESC, (u.home_process_code = 'OP-50') DESC, u.user_id LIMIT 1));
    IF v_inspector IS NULL THEN
        RETURN fn_record_cmm_failure(p_file_name, p_file_ref, 'LOT_MISMATCH',
            '측정자를 알 수 없음 (측정 시작 기록도, 파일의 operator도, 그 교대 측정 담당도 없음)', p_header, v_at);
    END IF;

    -- 불완전: 이 검사 방식에 필요한 3차원 측정기 항목 중 빠진 것 (강화 1번은 3단 위치로 와도 됨)
    SELECT string_agg(i.item_seq::text, ',' ORDER BY i.item_seq) INTO v_missing
      FROM inspection_item i
     WHERE i.product_code = v_product AND i.method = 'CMM' AND (i.in_sampling OR v_kind = 'ENHANCED')
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_rows) r
                        WHERE (r->>'item_seq')::int = i.item_seq);
    IF v_missing IS NOT NULL THEN
        v_status := 'NEEDS_CHECK'; v_err_kind := coalesce(v_err_kind, 'INCOMPLETE');
        v_err_text := concat_ws(' / ', v_err_text, '불완전: 항목 ' || v_missing || ' 없음');
    END IF;

    INSERT INTO cmm_import (file_name, received_at, status, error_kind, error_text, original_file_ref, instrument_id,
                            lot_no, part_seq, insp_kind, program_name_rev, measure_start_at, measure_end_at,
                            machine_temp_c, temp_comp_on, format_version, sample_no_raw, raw_header, instruction_id)
    VALUES (p_file_name, v_at, v_status, v_err_kind, v_err_text, p_file_ref,
            (SELECT equipment_id FROM equipment WHERE equipment_id = p_header->>'cmm_id'),
            v_lot, v_part, v_kind, p_header->>'program',
            (p_header->>'measure_start_at')::timestamptz, coalesce((p_header->>'measure_end_at')::timestamptz, v_measured),
            (p_header->>'machine_temp_c')::numeric, (p_header->>'temp_comp')::boolean,
            p_header->>'format', p_header->>'sample_no', p_header, v_instr.instruction_id)
    RETURNING cmm_import_id INTO v_import;

    FOR rw IN SELECT * FROM jsonb_array_elements(p_rows) LOOP
        SELECT * INTO it FROM inspection_item WHERE product_code = v_product AND item_seq = (rw->>'item_seq')::int;
        IF it.item_seq IS NULL OR it.method <> 'CMM' THEN
            CONTINUE;   -- 3차원 측정기 항목이 아니면 무시 (게이지·외관은 태블릿 버튼)
        END IF;
        v_value := (rw->>'actual')::numeric;
        v_cmm   := rw->>'cmm_judgement';
        v_pos   := nullif(rw->>'position', '');
        -- R-79 플랫폼이 DOC-06 §2 기준으로 다시 계산한 판정
        v_judge := CASE WHEN (it.lsl IS NULL OR v_value >= it.lsl) AND v_value <= it.usl THEN 'PASS' ELSE 'FAIL' END;
        -- R-81 같은 부품·항목·측정 위치가 다시 오면 재측정 순번을 올리고 덮어쓰지 않는다
        SELECT coalesce(max(remeasure_seq), 0) + 1 INTO v_reseq FROM inspection_result
         WHERE lot_no = v_lot AND part_seq = v_part AND item_seq = it.item_seq AND insp_kind = v_kind AND position IS NOT DISTINCT FROM v_pos;
        v_check := CASE WHEN v_status <> 'SUCCESS' OR v_cmm IS DISTINCT FROM v_judge OR v_reseq > 1
                        THEN 'NEEDS_CHECK' ELSE 'NORMAL' END;
        INSERT INTO inspection_result (lot_no, part_seq, product_code, item_seq, insp_kind, position, measured_value,
            judgement, instrument_id, inspector_id, measured_at, room_temp_c, part_temp_c, temp_comp_used,
            input_method, cmm_import_id, cmm_judgement, check_status, remeasure_seq, use_for_judgement)
        VALUES (v_lot, v_part, v_product, it.item_seq, v_kind, v_pos, v_value, v_judge,
            coalesce((SELECT equipment_id FROM equipment WHERE equipment_id = p_header->>'cmm_id'), 'CMM-01'),
            v_inspector, coalesce(v_measured, v_at),
            (p_header->>'room_temp_c')::numeric, (p_header->>'part_temp_c')::numeric, (p_header->>'temp_comp')::boolean,
            'CMM_AUTO', v_import, v_cmm, v_check, v_reseq,
            -- 판정에 쓰는 값: 그 위치(표준 또는 강화 3단 TOP·MID·BOTTOM)의 첫 측정. 재측정이 오면 반장이 고른다 (R-81)
            v_reseq = 1)
        RETURNING result_id INTO v_result;
        IF v_cmm IS DISTINCT FROM v_judge THEN
            v_mismatch := v_mismatch || v_result;
        END IF;
    END LOOP;

    IF v_instr.instruction_id IS NOT NULL THEN
        UPDATE cmm_instruction SET status = 'DONE', started_at = coalesce(started_at, (p_header->>'measure_start_at')::timestamptz, v_at)
         WHERE instruction_id = v_instr.instruction_id;
        -- 결과가 왔으므로 결과 미수신 알림은 자동 처리
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'CMM_NO_RESULT' AND lot_no = v_lot AND NOT is_processed),
                                v_inspector, v_at);
    END IF;
    IF v_status <> 'SUCCESS' THEN
        PERFORM fn_raise_notification('CMM_FILE_ERROR', format('측정 결과 확인 필요: %s — %s', p_file_name, v_err_text),
                                      jsonb_build_object('cmm_import_id', v_import, 'lot_no', v_lot), v_at);
    END IF;
    IF array_length(v_mismatch, 1) > 0 THEN
        PERFORM fn_raise_notification('CMM_JUDGE_MISMATCH',
            format('CMM 판정 불일치: %s 순번 %s 항목 %s', v_lot, v_part,
                   (SELECT string_agg(item_seq::text, ',') FROM inspection_result WHERE result_id = ANY (v_mismatch))),
            jsonb_build_object('result_id', v_mismatch[1], 'lot_no', v_lot), v_at);
    END IF;
    RETURN v_import;
END $$;

-- 반장 확인 (R-81·R-79): 확인 필요 값을 확인하고, 재측정이 있으면 판정에 쓸 값을 고른다
CREATE OR REPLACE FUNCTION fn_check_measurement(p_result_id bigint, p_actor text, p_use_for_judgement boolean,
                                                p_at timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE r inspection_result%ROWTYPE; v_at timestamptz := coalesce(p_at, app_now());
BEGIN
    SELECT * INTO r FROM inspection_result WHERE result_id = p_result_id FOR UPDATE;
    PERFORM fn_require_role(p_actor, ARRAY['SUP'], '측정값 반장 확인');
    IF p_use_for_judgement THEN
        -- 같은 부품·항목의 다른 값은 판정에서 뺀다 (하나만 참)
        UPDATE inspection_result SET use_for_judgement = false
         WHERE lot_no = r.lot_no AND part_seq = r.part_seq AND item_seq = r.item_seq AND result_id <> p_result_id;
    END IF;
    UPDATE inspection_result SET check_status = 'CHECKED', checked_by = p_actor, checked_at = v_at,
                                 use_for_judgement = p_use_for_judgement
     WHERE result_id = p_result_id;
    PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                   WHERE rule_code = 'CMM_JUDGE_MISMATCH' AND result_id = p_result_id AND NOT is_processed),
                            p_actor, v_at);
END $$;

-- ===================== db/functions/50_retention.sql =====================
-- =====================================================================
-- 50_retention.sql — 데이터 보관 기간 (NFR-DATA-13, 논리 ERD 6.53, R-75)
-- 실제 삭제·집계·보관 저장소 이동 방식은 [선택 필요: 기술 회의]라서,
-- 여기서는 "기간이 지난 행이 몇 개인지" 보여 주는 보고 함수만 둔다 (지우지 않음).
-- 30일 가상 데이터에서는 모든 값이 0이어야 한다 (설계서 5.19 "시연에서 지워지는 기록은 없다").
-- =====================================================================

CREATE OR REPLACE FUNCTION fn_retention_report(p_now timestamptz DEFAULT NULL)
RETURNS TABLE (rule_no int, stage text, table_name text, keep_for text, after_that text, rows_past bigint)
LANGUAGE sql STABLE AS $$
    WITH n AS (SELECT coalesce(p_now, app_now()) AS now)
    -- #1 L1 센서 5초(SEC5): 90일. 단, 정지 등급 알람 + 작업기록서가 있는 구간(앞뒤 30분)은 2년
    SELECT 1, 'L1', 'sensor_sample_5s', '90일 (정지 알람+작업기록서 구간 2년)', '삭제',
           (SELECT count(*) FROM sensor_sample_5s s, n
             WHERE s.sampled_at < n.now - interval '90 days'
               AND NOT (s.sampled_at >= n.now - interval '2 years' AND EXISTS (
                    SELECT 1 FROM alarm_event a JOIN work_record w ON w.alarm_event_id = a.alarm_event_id
                                                 OR w.wo_no IN (SELECT wo_no FROM maintenance_work_order m WHERE m.alarm_event_id = a.alarm_event_id)
                     WHERE a.equipment_id = s.equipment_id AND a.severity_at_event = 'STOP'
                       AND s.sampled_at BETWEEN a.occurred_at - interval '30 minutes' AND a.occurred_at + interval '30 minutes')))
    UNION ALL
    SELECT 2, 'L2', 'sensor_sample_1m', '1년', '1시간 집계(sensor_hourly)로 줄임',
           (SELECT count(*) FROM sensor_sample_1m, n WHERE sampled_at < n.now - interval '1 year')
    UNION ALL
    SELECT 3, 'L2', 'wip_log', '1년', '1시간 집계(wip_hourly)로 줄임',
           (SELECT count(*) FROM wip_log, n WHERE logged_at < n.now - interval '1 year')
    UNION ALL
    SELECT 2, 'L2', 'sensor_hourly', '집계 2년', '삭제',
           (SELECT count(*) FROM sensor_hourly, n WHERE hour_at < n.now - interval '2 years')
    UNION ALL
    SELECT 4, 'L3', 'equipment_state_log', '2년', '삭제',
           (SELECT count(*) FROM equipment_state_log, n WHERE coalesce(end_at, start_at) < n.now - interval '2 years')
    UNION ALL
    -- #5 보류·의심 로트와 연결된 알람은 15년 (#9와 같이)
    SELECT 5, 'L3', 'alarm_event', '2년 (보류 로트 연결 알람은 15년)', '삭제',
           (SELECT count(*) FROM alarm_event a, n WHERE a.occurred_at < n.now - interval '2 years'
               AND NOT EXISTS (SELECT 1 FROM lot_hold h WHERE h.related_alarm_event_id = a.alarm_event_id))
    UNION ALL
    SELECT 6, 'L3', 'bottleneck_log', '2년', '삭제',
           (SELECT count(*) FROM bottleneck_log, n WHERE changed_at < n.now - interval '2 years')
    UNION ALL
    SELECT 7, 'L3', 'notification', '2년', '삭제',
           (SELECT count(*) FROM notification, n WHERE raised_at < n.now - interval '2 years')
    UNION ALL
    -- #8 공구·소모품·예비품 입출고 = 원자재·완제품 아닌 것 (DOC-07 §11 Rev.2)
    SELECT 8, 'L3', 'inventory_txn (공구·소모품)', '2년', '삭제',
           (SELECT count(*) FROM inventory_txn t JOIN inventory_item i USING (item_no), n
             WHERE i.category NOT IN ('MATERIAL','FINISHED') AND t.txn_at < n.now - interval '2 years')
    UNION ALL
    -- L4는 운영 DB 2년 → 보관 저장소(읽기 전용) → 15년 뒤 삭제 [15년은 임시값]
    SELECT 9, 'L4', 'production_lot (로트 추적 사슬)', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM production_lot l, n
             WHERE coalesce((SELECT max(s.shipped_at) FROM shipment_line sl JOIN shipment s USING (shipment_no)
                              WHERE sl.lot_no = l.lot_no), l.judged_at) < n.now - interval '2 years')
    UNION ALL
    -- #9 로트 추적 사슬에 원자재 투입·완제품 입출고(inventory_txn)와 검사 계획(inspection_plan)도 들어간다 (DOC-07 §11 Rev.2)
    SELECT 9, 'L4', 'inventory_txn (원자재·완제품)', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM inventory_txn t JOIN inventory_item i USING (item_no), n
             WHERE i.category IN ('MATERIAL','FINISHED') AND t.txn_at < n.now - interval '2 years')
    UNION ALL
    SELECT 9, 'L4', 'inspection_plan', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM inspection_plan p JOIN production_lot l USING (lot_no), n
             WHERE coalesce(p.judged_at, l.judged_at) < n.now - interval '2 years')
    UNION ALL
    SELECT 10, 'L4', 'inspection_result', '운영 2년 → 보관 15년', '보관 저장소로 이동 (측정값 삭제 금지)',
           (SELECT count(*) FROM inspection_result, n WHERE measured_at < n.now - interval '2 years')
    UNION ALL
    -- cmm_import·원본 결과 파일의 기간은 [선택 필요: 팀] (논리 ERD 6.53 #10) — #10과 같게 하는 것을 [제안]으로 셈
    SELECT 10, 'L4', 'cmm_import', '[선택 필요: 팀] (제안: #10과 같게)', '보관 저장소로 이동 (제안)',
           (SELECT count(*) FROM cmm_import, n WHERE received_at < n.now - interval '2 years')
    UNION ALL
    SELECT 11, 'L4', 'shipment', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM shipment, n WHERE shipped_at < n.now - interval '2 years')
    UNION ALL
    SELECT 12, 'L4', 'work_record', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM work_record, n WHERE confirmed_at < n.now - interval '2 years')
    UNION ALL
    SELECT 14, 'L4', 'shift_report', '운영 2년 → 보관 15년', '보관 저장소로 이동',
           (SELECT count(*) FROM shift_report r JOIN shift s USING (shift_id), n WHERE r.confirmed_at < n.now - interval '2 years')
    UNION ALL
    SELECT 18, 'CHAT', 'chat_log', '30일 (질문 시각부터, 2026-10-13)', '삭제 (fn_purge_chat_log — 스케줄러가 매일)',
           (SELECT count(*) FROM chat_log, n WHERE asked_at < n.now - interval '30 days')
    UNION ALL
    SELECT 19, 'ACCESS_LOG', 'access_log', '1년', '삭제',
           (SELECT count(*) FROM access_log WHERE at < now() - interval '1 year')
    ORDER BY 1, 3;
$$;
COMMENT ON FUNCTION fn_retention_report(timestamptz) IS
    '보관 기간이 지난 행 수 보고 (지우지 않음). 실제 삭제·집계·이동은 [선택 필요: 기술 회의]';

-- AI 비서 채팅 기록 30일 삭제 (6.53 #18, R-75·R-87 — 2026-10-13 팀 결정 [가상]). 다른 보관 규칙과 달리 이것만 실제로 지운다:
-- 팀이 기간과 처리(삭제)를 정했고, 개인 질문 기록이라 오래 둘 이유가 없다. 반환: 지운 행 수
CREATE OR REPLACE FUNCTION fn_purge_chat_log(p_now timestamptz DEFAULT NULL) RETURNS int
LANGUAGE sql AS $$
    WITH d AS (DELETE FROM chat_log WHERE asked_at < coalesce(p_now, app_now()) - interval '30 days' RETURNING 1)
    SELECT count(*)::int FROM d;
$$;

-- ===================== db/functions/60_ingest.sql =====================
-- =====================================================================
-- 60_ingest.sql — 설비 쪽 사건 받기와 AI비서 초안 저장
--   fn_ingest_alarm            : 시뮬레이터(또는 실제 설비 수집기)가 알람 1건을 보낼 때
--   fn_create_work_order_draft : AI 비서 ②가 만든 작업지시서 초안(정해진 JSON 칸)을 저장할 때
--   fn_issue_cmm_instruction   : OP-50 측정 지시 (R-78, FR-QLT-01-15)
-- 데이터는 설비 → 플랫폼 한 방향 (FR-AST-COM-11). 이 함수들은 설비에 아무것도 보내지 않는다.
-- =====================================================================

-- 알람 1건 받기: 기록 → 등급별 알림(R-38) → 반복 알람 판정(R-70). 반환: alarm_event_id
-- 받는 사람 (6.36, 2026-10-13 팀 회의):
--   정지(ALARM_STOP) = 사용 중인 전원 — 긴급 팝업은 로그인한 사람 화면에 뜬다 (실시간 채널). 처리 책임은 그 설비 OPR·MNT
--   주의(ALARM_WARN) = 그 공정 작업자(담당 공정 두 칸) + 보전 담당자 / 조작 안내(ALARM_GUIDE) = 그 공정 작업자
CREATE OR REPLACE FUNCTION fn_ingest_alarm(p_equipment_id text, p_alarm_code text, p_occurred_at timestamptz DEFAULT NULL,
    p_lot_no text DEFAULT NULL, p_prev_alarm_event_id bigint DEFAULT NULL, p_is_injected boolean DEFAULT false,
    p_scenario_code text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at  timestamptz := coalesce(p_occurred_at, app_now());
    m     alarm_master%ROWTYPE;
    v_id  bigint;
    v_proc text := fn_equipment_process(p_equipment_id);
    v_rule text;
    v_recipients text[];
BEGIN
    SELECT * INTO m FROM alarm_master WHERE alarm_code = p_alarm_code;
    IF NOT FOUND THEN RAISE EXCEPTION '알람 코드집에 없는 알람 %', p_alarm_code USING ERRCODE = '23503'; END IF;
    INSERT INTO alarm_event (equipment_id, alarm_code, severity_at_event, occurred_at, lot_no, prev_alarm_event_id, is_injected, scenario_code)
    VALUES (p_equipment_id, p_alarm_code, m.severity, v_at, p_lot_no, p_prev_alarm_event_id, p_is_injected, p_scenario_code)
    RETURNING alarm_event_id INTO v_id;
    v_rule := CASE m.severity WHEN 'STOP' THEN 'ALARM_STOP' WHEN 'WARN' THEN 'ALARM_WARN' ELSE 'ALARM_GUIDE' END;
    SELECT array_agg(user_id) INTO v_recipients FROM app_user
     WHERE is_active AND (m.severity = 'STOP'
                          OR (role_code = 'OPR' AND (v_proc IN (home_process_code, home_process_code_2) OR home_process_code IS NULL))
                          OR (role_code = 'MNT' AND m.severity = 'WARN'));
    PERFORM fn_raise_notification(v_rule, format('%s 알람 %s (%s)', p_equipment_id, p_alarm_code, m.name_ko),
                                  jsonb_build_object('alarm_event_id', v_id, 'equipment_id', p_equipment_id, 'lot_no', p_lot_no),
                                  v_at, p_recipients => v_recipients);
    IF m.severity <> 'GUIDE' THEN
        PERFORM fn_check_repeat_alarm(v_id);
    END IF;
    RETURN v_id;
END $$;

-- 작업지시서 AI비서 초안 저장 (R-02·R-33·R-71). 반환: wo_no
-- p_steps = [{"step_text": "...", "source_section": "DOC-03 §2.1"}], p_parts = [{"item_no": "CS-WLUB", "qty": 1}]
-- 고정 서식 블록(잠금·표지 6+3단계·고전압·보호구)은 AI가 쓰지 않는다: safety_block_doc_rev로 붙었다는 표시만 (R-33)
CREATE OR REPLACE FUNCTION fn_create_work_order_draft(p_equipment_id text, p_title text, p_symptom text,
    p_alarm_event_id bigint DEFAULT NULL, p_trigger_notification_id bigint DEFAULT NULL, p_pm_record_id bigint DEFAULT NULL,
    p_steps jsonb DEFAULT '[]'::jsonb, p_parts jsonb DEFAULT '[]'::jsonb, p_lot_no text DEFAULT NULL, p_at timestamptz DEFAULT NULL,
    p_author text DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_wo text;
    v_doc05 text;
    -- p_author 가 없으면 AI비서 초안(AI_DRAFT, v0 = AI), 있으면 보전 담당자가 직접 만든 것(EDITING, v0 = HUMAN)
    v_status text := CASE WHEN p_author IS NULL THEN 'AI_DRAFT' ELSE 'EDITING' END;
BEGIN
    PERFORM fn_require_role(p_author, ARRAY['MNT'], '작업지시서 작성');
    -- 정지 등급 알람과 2단계가 겹치면 작업지시서 1개 (R-71): 이미 이 알람의 작업지시서가 있으면 계기만 더한다
    IF p_alarm_event_id IS NOT NULL THEN
        SELECT wo_no INTO v_wo FROM maintenance_work_order WHERE alarm_event_id = p_alarm_event_id;
    END IF;
    IF v_wo IS NULL AND p_trigger_notification_id IS NOT NULL THEN
        SELECT m.wo_no INTO v_wo FROM maintenance_work_order m JOIN notification n ON n.alarm_event_id = m.alarm_event_id
         WHERE n.notification_id = p_trigger_notification_id;
    END IF;
    IF v_wo IS NOT NULL THEN
        UPDATE maintenance_work_order SET trigger_notification_id = coalesce(trigger_notification_id, p_trigger_notification_id)
         WHERE wo_no = v_wo;
        INSERT INTO work_order_step (wo_no, step_no, step_text, source_section)
        SELECT v_wo, (SELECT coalesce(max(step_no), 0) FROM work_order_step WHERE wo_no = v_wo) + ord, s->>'step_text', s->>'source_section'
          FROM jsonb_array_elements(p_steps) WITH ORDINALITY AS x(s, ord);
        RETURN v_wo;
    END IF;
    SELECT 'DOC-05 ' || current_rev INTO v_doc05 FROM internal_doc WHERE doc_no = 'DOC-05';
    v_wo := fn_next_doc_no('MW', v_at);
    INSERT INTO maintenance_work_order (wo_no, alarm_event_id, pm_record_id, trigger_notification_id, equipment_id, lot_no, created_at,
                                        title, symptom, status, safety_block_doc_rev, has_high_voltage_notice, current_version)
    VALUES (v_wo, p_alarm_event_id, p_pm_record_id, p_trigger_notification_id, p_equipment_id, p_lot_no, v_at,
            p_title, p_symptom, v_status, coalesce(v_doc05, 'DOC-05'), fn_equipment_process(p_equipment_id) = 'OP-30', 0);
    INSERT INTO work_order_step (wo_no, step_no, step_text, source_section)
    SELECT v_wo, ord, s->>'step_text', s->>'source_section' FROM jsonb_array_elements(p_steps) WITH ORDINALITY AS x(s, ord);
    INSERT INTO work_order_part (wo_no, item_no, suggested_qty)
    SELECT v_wo, p->>'item_no', (p->>'qty')::numeric FROM jsonb_array_elements(p_parts) p;
    PERFORM fn_save_revision('WORK_ORDER', v_wo, CASE WHEN p_author IS NULL THEN 'AI' ELSE 'HUMAN' END, p_author, NULL, v_status,
        jsonb_build_object('title', p_title, 'symptom', p_symptom, 'steps', p_steps, 'parts', p_parts), '[]'::jsonb, NULL, v_at);
    RETURN v_wo;
END $$;

-- 측정 지시 (R-78, FR-QLT-01-15): 로트의 검사 방식으로 검사 구분을 정한다. 반환: instruction_id
CREATE OR REPLACE FUNCTION fn_issue_cmm_instruction(p_lot_no text, p_part_seq int, p_first boolean DEFAULT false,
                                                    p_at timestamptz DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE p inspection_plan%ROWTYPE; v_kind text; v_id bigint;
BEGIN
    PERFORM fn_create_inspection_plan(p_lot_no);
    SELECT * INTO p FROM inspection_plan WHERE lot_no = p_lot_no;
    v_kind := CASE WHEN p.plan_mode = 'ENHANCED' THEN 'ENHANCED' WHEN p_first THEN 'FIRST' ELSE 'SAMPLE' END;
    IF v_kind = 'SAMPLE' AND NOT (p_part_seq = 1 OR p_part_seq % 5 = 0) THEN
        RAISE EXCEPTION 'R-09: 발췌 로트의 측정 부품은 1번과 5의 배수 (요청 %)', p_part_seq USING ERRCODE = '23514';
    END IF;
    INSERT INTO cmm_instruction (lot_no, part_seq, insp_kind, enhance_reason, issued_at)
    VALUES (p_lot_no, p_part_seq, v_kind, CASE WHEN v_kind = 'ENHANCED' THEN p.enhance_reason END, coalesce(p_at, app_now()))
    RETURNING instruction_id INTO v_id;
    RETURN v_id;
END $$;

-- ===================== db/functions/70_realtime.sql =====================
-- =====================================================================
-- 70_realtime.sql — 시뮬레이터(또는 설비 수집기)가 실시간으로 보내는 것 받기
--   fn_state_change      : 설비 상태가 바뀜 → 열린 구간 닫고 새 구간 열기 (R-04 겹침은 EXCLUDE가 막음)
--   fn_report_production : 공정 실적(양품·재작업·불량) 더하기 → OP-30이면 공구 사용 누적 (공구 사용 기록 단위 B)
--   trg_state_log_loss   : 구간이 끝나면 정지 손실 수량 = 구간 길이 ÷ 기준 사이클 (계획 정지는 계산하지 않음)
-- 데이터는 설비 → 플랫폼 한 방향 (FR-AST-COM-11).
-- 재공(wip_log)·센서(sensor_sample)는 단순 INSERT라 app/sql/ingest.sql 에 둔다.
-- =====================================================================

-- 정지 손실 수량 (논리 ERD stop_loss_qty: 구간 길이 ÷ 그 설비 기준 사이클 시간, PLANNED 그룹은 계산 안 함)
-- 생성기가 값을 넣어 적재한 행(INSERT 때 값 있음)은 건드리지 않는다. 끝 시각·사유가 바뀌면 다시 계산한다.
CREATE OR REPLACE FUNCTION trg_state_log_loss() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_cycle numeric; v_group text;
BEGIN
    IF NEW.end_at IS NULL OR NEW.state_code = 'RUN' THEN
        IF NEW.state_code = 'RUN' THEN NEW.stop_loss_qty := NULL; END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'INSERT' AND NEW.stop_loss_qty IS NOT NULL THEN RETURN NEW; END IF;
    IF TG_OP = 'UPDATE' AND OLD.end_at IS NOT DISTINCT FROM NEW.end_at AND OLD.reason_code IS NOT DISTINCT FROM NEW.reason_code
       AND NEW.stop_loss_qty IS NOT NULL THEN
        RETURN NEW;
    END IF;
    SELECT reason_group INTO v_group FROM downtime_reason WHERE reason_code = coalesce(NEW.reason_code, NEW.reason_suggested_code);
    IF v_group = 'PLANNED' OR NEW.state_code = 'MAINT' THEN
        NEW.stop_loss_qty := NULL;
        RETURN NEW;
    END IF;
    SELECT std_cycle_min INTO v_cycle FROM equipment WHERE equipment_id = NEW.equipment_id;
    NEW.stop_loss_qty := round(extract(epoch FROM (NEW.end_at - NEW.start_at)) / 60 / nullif(v_cycle, 0), 2);
    RETURN NEW;
END $$;
SET client_min_messages = warning;
DROP TRIGGER IF EXISTS state_log_loss ON equipment_state_log;
RESET client_min_messages;
CREATE TRIGGER state_log_loss BEFORE INSERT OR UPDATE OF end_at, reason_code, state_code ON equipment_state_log
    FOR EACH ROW EXECUTE FUNCTION trg_state_log_loss();

-- 설비 상태 바뀜. 같은 상태가 이미 열려 있으면 새로 만들지 않고 그 구간 번호를 돌려준다 (중복 전송에 안전).
-- DOWN이면 정지 등급 알람(p_alarm_event_id), MAINT면 예방 정비 기록(p_pm_record_id)이 있어야 한다 (테이블 CHECK).
CREATE OR REPLACE FUNCTION fn_state_change(p_equipment_id text, p_state_code text, p_at timestamptz DEFAULT NULL,
    p_execution text DEFAULT NULL, p_warn_marker boolean DEFAULT false, p_reason_suggested_code text DEFAULT NULL,
    p_alarm_event_id bigint DEFAULT NULL, p_pm_record_id bigint DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at  timestamptz := coalesce(p_at, app_now());
    cur   equipment_state_log%ROWTYPE;
    v_id  bigint;
BEGIN
    SELECT * INTO cur FROM equipment_state_log
     WHERE equipment_id = p_equipment_id AND end_at IS NULL FOR UPDATE;
    IF FOUND THEN
        IF cur.state_code = p_state_code AND cur.alarm_event_id IS NOT DISTINCT FROM p_alarm_event_id
           AND cur.warn_marker = coalesce(p_warn_marker, false) THEN
            RETURN cur.state_log_id;
        END IF;
        IF v_at <= cur.start_at THEN
            RAISE EXCEPTION 'R-04: % 상태 바뀐 시각 %이 지금 구간 시작 %보다 앞', p_equipment_id, v_at, cur.start_at
                USING ERRCODE = '23514';
        END IF;
        UPDATE equipment_state_log SET end_at = v_at WHERE state_log_id = cur.state_log_id;
    END IF;
    INSERT INTO equipment_state_log (equipment_id, state_code, mtconnect_execution, start_at, warn_marker,
                                     reason_suggested_code, reason_status, alarm_event_id, pm_record_id)
    VALUES (p_equipment_id, p_state_code, CASE WHEN p_state_code IN ('SETUP','MAINT') THEN NULL ELSE p_execution END, v_at,
            coalesce(p_warn_marker, false),
            CASE WHEN p_state_code <> 'RUN' THEN p_reason_suggested_code END,
            CASE WHEN p_state_code <> 'RUN' AND p_reason_suggested_code IS NOT NULL THEN 'SUGGESTED' END,
            p_alarm_event_id, p_pm_record_id)
    RETURNING state_log_id INTO v_id;
    RETURN v_id;
END $$;

-- 공정 실적 더하기 (같은 로트·공정·설비·교대면 한 행에 더함 — ux_operation_report).
-- 생산 수량 = 양품 + 재작업 + 불량 (R-19). OP-30이면 이번에 더한 부품 수만큼 공구 사용을 누적한다.
CREATE OR REPLACE FUNCTION fn_report_production(p_lot_no text, p_equipment_id text, p_worker text, p_gq int, p_rq int DEFAULT 0,
    p_sq int DEFAULT 0, p_at timestamptz DEFAULT NULL, p_shift_id text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_at    timestamptz := coalesce(p_at, app_now());
    v_proc  text := fn_equipment_process(p_equipment_id);
    v_shift text := p_shift_id;
    v_id    bigint;
    v_pq    int := coalesce(p_gq, 0) + coalesce(p_rq, 0) + coalesce(p_sq, 0);
BEGIN
    IF v_pq <= 0 THEN RAISE EXCEPTION '실적 수량이 0' USING ERRCODE = '22023'; END IF;
    IF v_shift IS NULL THEN
        SELECT shift_id INTO v_shift FROM shift WHERE start_at <= v_at AND end_at > v_at;
        IF v_shift IS NULL THEN
            RAISE EXCEPTION '% 시각에 해당하는 교대가 없음 (휴식·교대 사이 실적)', v_at USING ERRCODE = '23514';
        END IF;
    END IF;
    INSERT INTO operation_report AS r (lot_no, process_code, equipment_id, worker_user_id, shift_id, start_at, pq, gq, rq, sq)
    VALUES (p_lot_no, v_proc, p_equipment_id, p_worker, v_shift, v_at, v_pq, coalesce(p_gq, 0), coalesce(p_rq, 0), coalesce(p_sq, 0))
    ON CONFLICT (lot_no, process_code, equipment_id, shift_id) DO UPDATE
       SET pq = r.pq + EXCLUDED.pq, gq = r.gq + EXCLUDED.gq, rq = r.rq + EXCLUDED.rq, sq = r.sq + EXCLUDED.sq,
           end_at = greatest(coalesce(r.end_at, r.start_at + interval '1 second'), v_at)
    RETURNING op_report_id INTO v_id;
    IF v_proc = 'OP-30' THEN
        PERFORM fn_add_tool_usage(v_id, v_pq, v_at);
    END IF;
    RETURN v_id;
END $$;

-- 작업지시 만들기 (시뮬레이터·생성기 쪽 계획). 번호 PO-YYMM-NNN
CREATE OR REPLACE FUNCTION fn_create_order(p_product_code text, p_order_qty int, p_due_at timestamptz,
    p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE v_at timestamptz := coalesce(p_at, app_now()); v_no text;
BEGIN
    v_no := fn_next_doc_no('PO', v_at);
    INSERT INTO production_order (order_no, product_code, order_qty, created_at, due_at)
    VALUES (v_no, p_product_code, p_order_qty, v_at, p_due_at);
    RETURN v_no;
END $$;

-- 로트 투입 (OP-10 시작): 로트 번호 = LOT-<작업지시 몸통>-<순번>, 투입 교대 = 그 시각의 교대,
-- 원자재 사용 거래(부품 1개 = 원자재 1단위 [제안]), 검사 방식(보통/강화, R-28), 작업지시 → 생산 중.
-- 원자재 로트가 사용 가능이 아니면 트리거가 막는다 (R-06a). 투입 합이 작업지시 수량을 넘으면 막는다 (R-08).
CREATE OR REPLACE FUNCTION fn_start_lot(p_order_no text, p_material_lot_no text, p_input_qty int,
    p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    o production_order%ROWTYPE; v_seq int; v_lot text; v_shift text; v_item text; v_used int;
BEGIN
    SELECT * INTO o FROM production_order WHERE order_no = p_order_no FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '작업지시 % 없음', p_order_no USING ERRCODE = '23503'; END IF;
    IF o.status NOT IN ('WAITING','IN_PROGRESS') THEN
        RAISE EXCEPTION '작업지시 %는 투입할 수 없는 상태 (%)', p_order_no, o.status USING ERRCODE = '23514';
    END IF;
    SELECT coalesce(sum(input_qty), 0) INTO v_used FROM production_lot WHERE order_no = p_order_no;
    IF v_used + p_input_qty > o.order_qty THEN
        RAISE EXCEPTION 'R-08: 투입 합 %가 작업지시 수량 %를 넘음', v_used + p_input_qty, o.order_qty USING ERRCODE = '23514';
    END IF;
    SELECT shift_id INTO v_shift FROM shift WHERE start_at <= v_at AND end_at > v_at;
    IF v_shift IS NULL THEN RAISE EXCEPTION '% 시각에 교대가 없음 — 투입 불가', v_at USING ERRCODE = '23514'; END IF;
    SELECT coalesce(max(lot_seq), 0) + 1 INTO v_seq FROM production_lot WHERE order_no = p_order_no;
    v_lot := 'LOT-' || substr(p_order_no, 4) || '-' || v_seq;
    INSERT INTO production_lot (lot_no, order_no, lot_seq, input_shift_id, material_lot_no, input_qty)
    VALUES (v_lot, p_order_no, v_seq, v_shift, p_material_lot_no, p_input_qty);
    SELECT material_item_no INTO v_item FROM product WHERE product_code = o.product_code;
    INSERT INTO inventory_txn (item_no, txn_type, qty_change, txn_at, source_kind, lot_no)
    VALUES (v_item, 'USE', -p_input_qty, v_at, 'LOT_INPUT', v_lot);
    PERFORM fn_check_stock(v_item, NULL, v_at);
    PERFORM fn_create_inspection_plan(v_lot);
    IF o.status = 'WAITING' THEN
        UPDATE production_order SET status = 'IN_PROGRESS', started_at = v_at WHERE order_no = p_order_no;
    END IF;
    RETURN v_lot;
END $$;

-- 로트가 OP-50에 도착 → 검사 대기 (6.8: 생산 중 → 검사 대기만)
CREATE OR REPLACE FUNCTION fn_lot_to_inspection(p_lot_no text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE production_lot SET status = 'WAIT_INSPECTION' WHERE lot_no = p_lot_no AND status = 'IN_PROCESS';
    IF NOT FOUND THEN
        RAISE EXCEPTION '로트 %는 생산 중이 아님 — 검사 대기로 바꿀 수 없음', p_lot_no USING ERRCODE = '23514';
    END IF;
END $$;

-- 근무일·교대 만들기 (시연 10/1부터 — 생성기 9월 기록에는 9/30까지만 있다). 이미 있으면 그대로. 반환: 새로 만든 교대 수
-- 값은 가장 최근 근무일을 본뜬다 (주간 08:00~17:00·야간 20:00~05:00, 계획 시간·목표·반장, 하루 목표 180 — 설계서 5.2).
-- 야간 이월(carry_over_qty)은 0으로 두고 주간이 끝나면 fn_refresh_carry_over가 채운다 (R-88). 휴무일 지정은 MGR이 work_day에서
CREATE OR REPLACE FUNCTION fn_ensure_work_day(p_date date) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE tpl date; n int := 0;
BEGIN
    SELECT max(work_date) INTO tpl FROM work_day WHERE is_workday AND work_date < p_date
       AND EXISTS (SELECT 1 FROM shift s WHERE s.work_date = work_day.work_date);
    IF tpl IS NULL THEN RETURN 0; END IF;
    INSERT INTO work_day (work_date, is_workday, daily_target_qty)
    SELECT p_date, true, daily_target_qty FROM work_day WHERE work_date = tpl
    ON CONFLICT (work_date) DO NOTHING;
    IF NOT (SELECT is_workday FROM work_day WHERE work_date = p_date) THEN RETURN 0; END IF;
    WITH ins AS (
        INSERT INTO shift (shift_id, work_date, shift_type, start_at, end_at, planned_time_min, target_qty, carry_over_qty,
                           supervisor_user_id)
        SELECT to_char(p_date, 'YYYY-MM-DD') || '-' || left(s.shift_type, 1), p_date, s.shift_type,
               s.start_at + (p_date - tpl) * interval '1 day', s.end_at + (p_date - tpl) * interval '1 day',
               s.planned_time_min, s.target_qty, 0, s.supervisor_user_id
          FROM shift s WHERE s.work_date = tpl
        ON CONFLICT DO NOTHING RETURNING 1)
    SELECT count(*) INTO n FROM ins;
    RETURN n;
END $$;
COMMENT ON FUNCTION fn_ensure_work_day(date) IS '근무일·교대 2개를 가장 최근 근무일을 본떠 만든다 (적재 뒤 10/1, 스케줄러가 오늘·내일)';

-- ===================== db/functions/80_demo_reset.sql =====================
-- =====================================================================
-- 80_demo_reset.sql — 시연 데이터 처음으로 (API명세서 SIM-03, NFR-DATA-10, 2026-10-08)
--   fn_demo_snapshot(): 지금 운영 데이터를 시연 기준점(demo_snapshot 스키마)으로 복사 (목업·생성기 적재 뒤 자동)
--   fn_demo_reset()   : 운영 데이터를 기준점으로 되돌리고 시연 시계를 그때 시각에 멈춰 둔다. 화면에는 RESYNC
-- 대상 = public의 운영 표 전부 (파티션은 부모로). 빼는 것: 설정·계정·코드(role·role_permission·code_label·notification_rule·
--   app_user — 시연 중 바꾼 설정은 남김), 접속 기록(access_log — 감사 기록은 지우지 않음), dataset_info, sim_clock,
--   그리고 이 표들이 가리키는 기준 표(process).
-- 센서 값(sensor_sample, 9월 약 98만 행·DB 약 120MB)은 복사하지 않는다: 추가만 되는 시계열이라 되돌릴 때
--   "기준점 시연 시각 이후 값"만 지운다 — 복사본을 두면 DB가 두 배가 되어 Supabase 무료 한도(500MB)에 가까워진다 (1014 수정사항 7장).
--   센서를 기준점 뒤에 따로 넣어도(--sensor-only) 그대로 남는다.
-- 되돌릴 때는 트리거를 끈 채(session_replication_role = replica) 그대로 채운다 — 재고 수량 같은 계산 값도 복사본 그대로.
-- 이 설정은 슈퍼유저만 바꿀 수 있어 두 함수는 스키마 주인 권한으로 돈다 (Docker의 POSTGRES_USER는 슈퍼유저).
-- =====================================================================

-- 남기는 표가 가리키는 기준 표(예: app_user → process)도 뺀다 — TRUNCATE는 남기는 표의 외래 키를 깨지 못한다
CREATE OR REPLACE FUNCTION fn_demo_tables() RETURNS SETOF text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    -- 남기는 표 + 그 표가 (여러 단계로) 가리키는 기준 표 전부 (예: sensor_sample → sensor_item → alarm_master)
    WITH RECURSIVE keep(oid) AS (
        SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relname IN ('role', 'role_permission', 'code_label', 'notification_rule', 'app_user',
                                                      'access_log', 'dataset_info', 'sim_clock', 'sensor_sample', 'sensor_hourly')
        UNION
        SELECT f.confrelid FROM pg_constraint f JOIN keep k ON f.conrelid = k.oid WHERE f.contype = 'f'
    )
    SELECT c.relname::text
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind IN ('r','p') AND NOT c.relispartition
       AND c.oid NOT IN (SELECT oid FROM keep)
     ORDER BY c.relname;
$$;

CREATE OR REPLACE FUNCTION fn_demo_snapshot() RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE t text; v_tables text[] := ARRAY(SELECT fn_demo_tables());
BEGIN
    FOR t IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'demo_snapshot' AND c.relkind = 'r' AND c.relname <> 'meta' LOOP
        EXECUTE format('DROP TABLE demo_snapshot.%I', t);
    END LOOP;
    FOREACH t IN ARRAY v_tables LOOP
        EXECUTE format('CREATE TABLE demo_snapshot.%I AS SELECT * FROM public.%I', t, t);
    END LOOP;
    INSERT INTO demo_snapshot.meta (id, taken_at, sim_at, clock_mode, speed, tables)
    SELECT 1, now(), app_now(), mode, speed, v_tables FROM sim_clock WHERE id = 1
    ON CONFLICT (id) DO UPDATE SET taken_at = EXCLUDED.taken_at, sim_at = EXCLUDED.sim_at, clock_mode = EXCLUDED.clock_mode,
                                   speed = EXCLUDED.speed, tables = EXCLUDED.tables;
    RETURN cardinality(v_tables);
END $$;
COMMENT ON FUNCTION fn_demo_snapshot() IS '시연 기준점 만들기 (SIM-03). 목업(dev/90)·생성기 적재 뒤 부른다';

-- 반환: {"tables": 되돌린 표 수, "sim_at": 시연 시계}
-- session_replication_role = replica (트리거·외래 키 확인 끔)는 함수 안에서만 — 끝나면 원래대로
-- 함수 SET 절이나 set_config()로 걸지 않고 EXECUTE 'SET LOCAL …'로 건다: Supabase는 postgres 역할이 슈퍼유저가 아니라
-- SET 문으로만 이 값을 바꿀 수 있다 (2026-10-15 실제 프로젝트에서 확인 — SET 절·set_config는 permission denied)
CREATE OR REPLACE FUNCTION fn_demo_reset() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    m demo_snapshot.meta%ROWTYPE; t text; v_cols text; r record;
    v_prev text := current_setting('session_replication_role');
BEGIN
    SELECT * INTO m FROM demo_snapshot.meta WHERE id = 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION '시연 기준점이 없음 — 먼저 fn_demo_snapshot() (POST /api/sim/snapshot)' USING ERRCODE = '23514';
    END IF;
    SET CONSTRAINTS ALL IMMEDIATE;     -- 같은 트랜잭션에 미뤄 둔 외래 키 확인이 있으면 먼저 끝낸다 (TRUNCATE 전)
    EXECUTE 'SET LOCAL session_replication_role = replica';
    EXECUTE 'TRUNCATE ' || (SELECT string_agg(format('public.%I', x), ', ') FROM unnest(m.tables) x);
    FOREACH t IN ARRAY m.tables LOOP
        -- 생성 칼럼(GENERATED ALWAYS)은 빼고 넣는다
        SELECT string_agg(format('%I', a.attname), ', ' ORDER BY a.attnum) INTO v_cols
          FROM pg_attribute a
         WHERE a.attrelid = format('public.%I', t)::regclass AND a.attnum > 0 AND NOT a.attisdropped AND a.attgenerated = ''
           AND EXISTS (SELECT 1 FROM information_schema.columns c
                        WHERE c.table_schema = 'demo_snapshot' AND c.table_name = t AND c.column_name = a.attname);
        EXECUTE format('INSERT INTO public.%I (%s) OVERRIDING SYSTEM VALUE SELECT %s FROM demo_snapshot.%I', t, v_cols, v_cols, t);
    END LOOP;
    -- 센서: 기준점 시각 이후 값만 지운다 (위 설명)
    DELETE FROM sensor_sample WHERE sampled_at >= m.sim_at;
    -- 일련번호를 되돌린 데이터의 최대값에 맞춘다
    FOR r IN SELECT c.table_name, c.column_name FROM information_schema.columns c
              WHERE c.table_schema = 'public' AND c.is_identity = 'YES' AND c.table_name = ANY (m.tables) LOOP
        EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, %L), coalesce((SELECT max(%I) FROM public.%I), 0) + 1, false)',
                       'public.' || r.table_name, r.column_name, r.column_name, r.table_name);
    END LOOP;
    -- 시연 시계: 기준점 시각에 멈춰 둔다 (발표자가 다시 돌린다)
    PERFORM fn_sim_set(m.clock_mode, m.sim_at, m.speed, true);
    PERFORM pg_notify('mom_events', '{"table": "*", "op": "RESYNC"}');   -- 화면이 전부 다시 읽게 (connection 사건)
    EXECUTE format('SET LOCAL session_replication_role = %s', v_prev);   -- 원래대로 (origin)
    RETURN jsonb_build_object('tables', cardinality(m.tables), 'sim_at', m.sim_at, 'snapshot_taken_at', m.taken_at);
END $$;
COMMENT ON FUNCTION fn_demo_reset() IS '시연 데이터 처음으로 (SIM-03): 기준점으로 되돌리고 시연 시계를 그 시각에 멈춤';

-- ===================== db/functions/85_access.sql =====================
-- =====================================================================
-- 85_access.sql — 역할별 권한을 DB에서도 한 번 더 (기획서 13.2, API명세서 INV-02)
--   · 원자재 로트는 원자재 품목만. 입고 거래는 품목 관리 역할만(R-77, 20_integrity)이라
--     MNT가 자기 관리 품목(정비 소모품)을 "원자재 로트"로 등록할 수 있던 틈을 막는다.
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_raw_material_lot_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_cat text;
BEGIN
    SELECT category INTO v_cat FROM inventory_item WHERE item_no = NEW.item_no;
    IF v_cat IS DISTINCT FROM 'MATERIAL' THEN
        RAISE EXCEPTION '원자재 로트에는 원자재 품목만 (% 은 %)', NEW.item_no, coalesce(v_cat, '없는 품목')
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
SET client_min_messages = warning;
DROP TRIGGER IF EXISTS raw_material_lot_item ON raw_material_lot;
RESET client_min_messages;
CREATE TRIGGER raw_material_lot_item BEFORE INSERT OR UPDATE OF item_no ON raw_material_lot
    FOR EACH ROW EXECUTE FUNCTION trg_raw_material_lot_item();

-- ===================== db/functions/86_qr.sql =====================
-- =====================================================================
-- 86_qr.sql — QR 찍은 기록 (2026-10-13 가정 "재고·로트는 QR로 관리" [제안])
--   · qr_scan은 추가만 한다 (고치기·지우기 금지 — 수불대장과 같은 규칙)
--   · 출하 줄마다 QR 확인 여부: fn_ship_qr_unchecked(출하 번호) = 아직 안 찍은 로트 목록
-- =====================================================================
SET client_min_messages = warning;
DROP TRIGGER IF EXISTS qr_scan_append_only ON qr_scan;
RESET client_min_messages;
CREATE TRIGGER qr_scan_append_only BEFORE UPDATE OR DELETE ON qr_scan
    FOR EACH ROW EXECUTE FUNCTION trg_append_only();

CREATE OR REPLACE FUNCTION fn_ship_qr_unchecked(p_shipment_no text) RETURNS text[]
LANGUAGE sql STABLE AS $$
    SELECT coalesce(array_agg(sl.lot_no ORDER BY sl.lot_passed_at, sl.lot_no), '{}')
      FROM shipment_line sl
     WHERE sl.shipment_no = p_shipment_no
       AND NOT EXISTS (SELECT 1 FROM qr_scan q
                        WHERE q.purpose = 'SHIP_CHECK' AND q.result = 'OK'
                          AND q.shipment_no = sl.shipment_no AND q.ref_no = sl.lot_no);
$$;

-- ===================== db/views/10_views.sql =====================
-- =====================================================================
-- 10_views.sql — 계산 속성과 화면·비서 조회용 뷰
-- 논리 ERD에서 "계산" 표시가 붙은 속성 중 저장하지 않기로 한 것은 모두 여기서 계산한다
-- (docs/02_물리ERD.md 6장). 시간에 따라 바뀌는 값은 app_now()(시연 시계)를 쓴다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 생산 로트 + 완료 수량(R-05) + 측정할 부품 수(R-09) + 완제품·출하 수량(R-69)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_production_lot AS
SELECT l.lot_no, l.order_no, l.lot_seq, l.input_shift_id, l.material_lot_no, l.input_qty, l.status, l.scrap_qty,
       l.judged_at, o.product_code, o.due_at,
       coalesce(c.completed_qty, 0)                                    AS completed_qty,
       c.op50_done_at,
       NULL::timestamptz                                               AS expected_complete_at,  -- 계산 방법 [선택 필요: 기술 회의]
       p.plan_mode, p.enhance_reason, p.judgement AS plan_judgement,
       CASE WHEN p.plan_mode = 'ENHANCED' THEN l.input_qty ELSE 1 + l.input_qty / 5 END AS planned_measure_qty,
       fg.fg_in_qty, fg.passed_at,
       coalesce(sh.shipped_qty, 0)                                     AS shipped_qty,
       coalesce(fg.fg_in_qty, 0) - coalesce(sh.shipped_qty, 0)        AS fg_remaining_qty,
       sh.shipment_nos
  FROM production_lot l
  JOIN production_order o USING (order_no)
  LEFT JOIN inspection_plan p USING (lot_no)
  LEFT JOIN LATERAL (SELECT sum(r.gq + r.rq)::int AS completed_qty, max(r.end_at) AS op50_done_at
                       FROM operation_report r WHERE r.lot_no = l.lot_no AND r.process_code = 'OP-50') c ON true
  LEFT JOIN LATERAL (SELECT sum(t.qty_change)::int AS fg_in_qty, min(t.txn_at) AS passed_at
                       FROM inventory_txn t WHERE t.source_kind = 'LOT_PASS' AND t.fg_lot_no = l.lot_no) fg ON true
  LEFT JOIN LATERAL (SELECT sum(sl.qty)::int AS shipped_qty, string_agg(sl.shipment_no, ',' ORDER BY sl.shipment_no) AS shipment_nos
                       FROM shipment_line sl JOIN shipment s USING (shipment_no)
                      WHERE sl.lot_no = l.lot_no AND s.status <> 'DRAFT') sh ON true;

-- ---------------------------------------------------------------------
-- 병목 구간 (5.B.6): 다음 기록까지가 한 구간. 계획 생산 수 = 구간 ÷ 라인 기준 사이클(3.5분)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_bottleneck_interval AS
SELECT b.*,
       lead(b.changed_at) OVER w                                        AS interval_end_at,
       round((extract(epoch FROM (coalesce(lead(b.changed_at) OVER w, app_now()) - b.changed_at)) / 60
              / (SELECT min(line_base_cycle_min) FROM product WHERE is_active))::numeric, 2) AS planned_qty
  FROM bottleneck_log b
WINDOW w AS (ORDER BY b.changed_at);

-- ---------------------------------------------------------------------
-- 작업지시서 + 계기(여러 값, 6.42) + 승인 대기 분
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_work_order AS
SELECT m.*,
       array_remove(ARRAY[
           CASE WHEN m.alarm_event_id IS NOT NULL THEN 'STOP_ALARM' END,
           CASE WHEN m.trigger_notification_id IS NOT NULL THEN 'REPEAT_STAGE2' END,
           CASE WHEN m.pm_record_id IS NOT NULL THEN 'PM_ABNORMAL' END], NULL)::varchar[] AS trigger_kind,
       CASE WHEN m.status IN ('AI_DRAFT','EDITING')
            THEN round(extract(epoch FROM (app_now() - m.created_at)) / 60) END        AS approval_wait_min,
       -- 13.1 MGR "승인(대리)": 승인자가 MGR이면 반장 대신 승인한 것 (저장 칸 없이 승인자 역할로 계산)
       (SELECT u.role_code = 'MGR' FROM app_user u WHERE u.user_id = m.approved_by)    AS approved_as_proxy
  FROM maintenance_work_order m;

-- ---------------------------------------------------------------------
-- 예방 정비 다음 기한 (R-43): 마지막 실시일 + 주기. 필요할 때·8시간 사용마다는 날짜 기한 없음
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_pm_task_due AS
SELECT t.*, last.done_at AS last_done_at,
       (last.done_at AT TIME ZONE 'Asia/Seoul')::date + CASE t.cycle_code
            WHEN 'DAILY' THEN interval '1 day' WHEN 'WEEKLY' THEN interval '7 days'
            WHEN 'MONTHLY' THEN interval '1 month' WHEN 'HALF_YEAR' THEN interval '6 months'
            WHEN 'YEARLY' THEN interval '1 year' END                    AS next_due_ts,
       ((last.done_at AT TIME ZONE 'Asia/Seoul')::date + CASE t.cycle_code
            WHEN 'DAILY' THEN interval '1 day' WHEN 'WEEKLY' THEN interval '7 days'
            WHEN 'MONTHLY' THEN interval '1 month' WHEN 'HALF_YEAR' THEN interval '6 months'
            WHEN 'YEARLY' THEN interval '1 year' END)::date              AS next_due_date
  FROM pm_task t
  LEFT JOIN LATERAL (SELECT max(r.done_at) AS done_at FROM pm_record r WHERE r.pm_task_id = t.pm_task_id) last ON true;

-- ---------------------------------------------------------------------
-- 공구 수명 (R-40): 사용률 = 누적 ÷ 한도 × 100, 남은 수명 = 100 − 사용률
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tool_life AS
SELECT tl.tool_id, tl.equipment_id, tl.tool_no, tl.item_no, i.item_name, tl.tool_role, tl.cum_usage,
       tt.usage_unit, tt.usage_per_part, tt.life_limit, tl.last_changed_at,
       round(100 * tl.cum_usage / tt.life_limit, 1)                       AS usage_rate_pct,
       round(100 - 100 * tl.cum_usage / tt.life_limit, 1)                 AS remaining_pct,
       floor(greatest(tt.life_limit - tl.cum_usage, 0) / tt.usage_per_part)::int AS parts_left
  FROM tool tl JOIN tool_type tt USING (item_no) JOIN inventory_item i USING (item_no)
 WHERE tl.is_active;

-- ---------------------------------------------------------------------
-- 출하 + 합계 수량·근거 작업지시 (5.E.7 계산)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shipment AS
SELECT s.*, coalesce(x.total_qty, 0) AS total_qty, x.line_count, x.basis_order_nos
  FROM shipment s
  LEFT JOIN LATERAL (
      SELECT sum(sl.qty)::int AS total_qty, count(*)::int AS line_count,
             string_agg(DISTINCT l.order_no, ',') AS basis_order_nos
        FROM shipment_line sl JOIN production_lot l USING (lot_no)
       WHERE sl.shipment_no = s.shipment_no) x ON true;

-- ---------------------------------------------------------------------
-- 검사 결과 + 기준 + 가공 설비 ([제안] 05 결정기록 P-11 — 논리 ERD에는 규칙 번호가 없다. R-88은 이월·총 목표)
--   가공 설비 = 그 로트의 OP-30 공정 실적 설비가 1대뿐이면 그 설비, 2대에 나뉘면 NULL("설비 미상")
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_inspection_result AS
SELECT r.*, i.item_name, i.spec_text, i.nominal, i.lsl, i.usl, i.char_class, i.method,
       (SELECT CASE WHEN count(DISTINCT o.equipment_id) = 1 THEN min(o.equipment_id) END
          FROM operation_report o WHERE o.lot_no = r.lot_no AND o.process_code = 'OP-30') AS machined_equipment_id
  FROM inspection_result r
  JOIN inspection_item i USING (product_code, item_seq);

-- ---------------------------------------------------------------------
-- 재고 현황 (FR-INV-01, R-39)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_inventory_status AS
SELECT i.*,
       i.safety_stock IS NOT NULL AND i.on_hand_qty <= i.safety_stock AS is_low,
       CASE WHEN i.safety_stock > 0 THEN round(i.on_hand_qty / i.safety_stock, 2) END AS stock_ratio
  FROM inventory_item i
 WHERE i.is_active;

-- ---------------------------------------------------------------------
-- 잠금·표지 중인 설비 (R-53): 6.4 체크 뒤 7.3 체크 전
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_lock_status AS
SELECT w.equipment_id, w.record_no, c64.checked_at AS locked_since, c64.checked_by AS locked_by
  FROM work_record w
  JOIN work_record_check c64 ON c64.record_no = w.record_no AND c64.loto_step_code = '6.4' AND c64.is_checked
 WHERE NOT EXISTS (SELECT 1 FROM work_record_check c73
                    WHERE c73.record_no = w.record_no AND c73.loto_step_code = '7.3' AND c73.is_checked);

-- ---------------------------------------------------------------------
-- 설비 지금 상태 (3D·현장 보기·하단 패널)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_equipment_now AS
SELECT e.equipment_id, e.process_code, e.model,
       st.state_code, st.start_at AS state_since, st.warn_marker, st.reason_code, st.reason_status,
       round(extract(epoch FROM (app_now() - st.start_at)) / 60, 1) AS state_minutes,
       al.alarm_event_id AS open_alarm_event_id, al.alarm_code AS open_alarm_code, al.severity_at_event AS open_alarm_severity,
       lk.record_no AS lock_record_no, lk.locked_since,
       cur.lot_no AS current_lot_no,
       st.alarm_event_id AS state_alarm_event_id          -- DOWN 구간을 만든 정지 등급 알람 (R-22)
  FROM equipment e
  LEFT JOIN LATERAL (SELECT * FROM equipment_state_log s WHERE s.equipment_id = e.equipment_id
                      ORDER BY s.start_at DESC LIMIT 1) st ON true
  LEFT JOIN LATERAL (SELECT a.* FROM alarm_event a WHERE a.equipment_id = e.equipment_id AND a.cleared_at IS NULL
                      ORDER BY a.occurred_at DESC LIMIT 1) al ON true
  LEFT JOIN LATERAL (SELECT * FROM v_lock_status v WHERE v.equipment_id = e.equipment_id
                      ORDER BY v.locked_since LIMIT 1) lk ON true
  LEFT JOIN LATERAL (SELECT o.lot_no FROM operation_report o WHERE o.equipment_id = e.equipment_id
                      ORDER BY o.start_at DESC LIMIT 1) cur ON true
 WHERE e.is_active;

-- ---------------------------------------------------------------------
-- 보고 순위 (6.43, R-73 "전부 보고·정해진 순서") — 브리핑·교대 보고서 인계·일일 보고서 "오늘의 문제"
-- 개수를 자르지 않는다. 정렬: rank_order → rank_group → sort_value(큰 순) → occurred_at(이른 순)
-- v_report_items = 모은 항목 하나하나, v_report_lines = 같은 설비·같은 원인을 한 줄로 묶은 화면 줄 (아래)
-- group_key: 같은 설비·같은 원인 = 같은 설비 + 같은 알람 번호 (알람·반복 알람 1·2단계·원인 점검 요청·DOWN 설비),
--   여기에 관련 예방 정비(기본 소모품)·재고 부족을 알람 ↔ 재고 품목 연결(alarm_related_item)로 붙인다 (R-89)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_report_items AS
WITH now_ AS (SELECT app_now() AS t),
open_n AS (
    SELECT n.*, r.report_rank, r.rank_group, r.rule_name,
           a.alarm_code, coalesce(n.equipment_id, a.equipment_id) AS alarm_equipment,
           pt.equipment_id AS pm_equipment, pt.default_item_no AS pm_item,
           CASE WHEN n.rule_code = 'STOCK_LOW' THEN n.item_no END AS stock_item
      FROM notification n JOIN notification_rule r USING (rule_code)
      LEFT JOIN alarm_event a ON a.alarm_event_id = n.alarm_event_id
      LEFT JOIN pm_task pt ON pt.pm_task_id = n.pm_task_id
     WHERE NOT n.is_processed
), base AS (
-- 0 안전: 잠금·표지 중인 설비
SELECT 'R0'::text AS report_rank, 0 AS rank_order, 0 AS rank_group, 'LOCK'::text AS item_kind,
       NULL::bigint AS notification_id, NULL::text AS rule_code, v.equipment_id, NULL::text AS lot_no,
       '잠금·표지 중: ' || v.equipment_id AS title, v.locked_since AS occurred_at, NULL::numeric AS sort_value,
       NULL::text AS alarm_equipment, NULL::text AS alarm_code, NULL::text AS pm_equipment, NULL::text AS pm_item,
       NULL::text AS stock_item
  FROM v_lock_status v
UNION ALL
-- 0-1 오래 방치: 24시간 넘게 처리 안 된 주의 알림 (건수는 "주의"에 센다)
SELECT 'R0_1', 1, 0, 'NOTIFICATION', n.notification_id, n.rule_code, n.equipment_id, n.lot_no,
       n.message, n.raised_at, extract(epoch FROM (now_.t - n.raised_at)) / 3600,
       n.alarm_equipment, n.alarm_code, n.pm_equipment, n.pm_item, n.stock_item
  FROM open_n n, now_
 WHERE n.importance = 'CAUTION' AND n.raised_at < now_.t - interval '24 hours'
UNION ALL
-- 1·2·3·4 순위의 알림 (0-1로 올라간 것은 빼고)
SELECT n.report_rank, CASE n.report_rank WHEN 'R1' THEN 2 WHEN 'R2' THEN 3 WHEN 'R3' THEN 4 ELSE 5 END,
       n.rank_group, 'NOTIFICATION', n.notification_id, n.rule_code, n.equipment_id, n.lot_no,
       n.message, n.raised_at, n.repeat_count::numeric,
       n.alarm_equipment, n.alarm_code, n.pm_equipment, n.pm_item, n.stock_item
  FROM open_n n, now_
 WHERE NOT (n.importance = 'CAUTION' AND n.raised_at < now_.t - interval '24 hours')
UNION ALL
-- 1 긴급: 지금 DOWN인 설비 (같은 설비·같은 알람의 정지 알람 알림이 있으면 그 줄로 묶인다)
SELECT 'R1', 2, 0, 'DOWN', NULL, NULL, e.equipment_id, e.current_lot_no,
       '고장 정지 중: ' || e.equipment_id, e.state_since, e.state_minutes,
       e.equipment_id, coalesce(sa.alarm_code, e.open_alarm_code), NULL, NULL, NULL
  FROM v_equipment_now e
  LEFT JOIN alarm_event sa ON sa.alarm_event_id = e.state_alarm_event_id
 WHERE e.state_code = 'DOWN'
UNION ALL
-- 3 주의 ③ 품질: 보류·보류 검토 로트
SELECT 'R3', 4, 30, 'LOT', NULL, NULL, NULL, l.lot_no,
       CASE l.status WHEN 'ON_HOLD' THEN '보류 로트: ' ELSE '보류 검토 로트: ' END || l.lot_no,
       coalesce(h.held_at, l.judged_at), NULL, NULL, NULL, NULL, NULL, NULL
  FROM production_lot l
  LEFT JOIN lot_hold h ON h.lot_no = l.lot_no AND h.result = 'IN_PROGRESS'
 WHERE l.status IN ('ON_HOLD','HOLD_REVIEW')
UNION ALL
-- 3 주의 ③ 품질: 강화 검사 중인 로트 (보류 로트의 다음 1~2개, 판정 전 — FR-PRD-02-08 인계 사항)
SELECT 'R3', 4, 30, 'LOT', NULL, NULL, NULL, l.lot_no, '강화 검사 로트: ' || l.lot_no,
       h.held_at, NULL, NULL, NULL, NULL, NULL, NULL
  FROM production_lot l
  JOIN inspection_plan p USING (lot_no)
  LEFT JOIN lot_hold h ON h.hold_id = p.hold_id
 WHERE p.plan_mode = 'ENHANCED' AND p.enhance_reason = 'NEXT_LOT'
   AND l.status IN ('IN_PROCESS','WAIT_INSPECTION','WAIT_JUDGEMENT')
)
-- 같은 원인 (group_key): ① 알람이 있는 항목 = 설비|알람 번호 ② 예방 정비 알림 = 그 설비의 관련 알람 줄이 있으면 그 줄
--   (alarm_related_item: 알람 ↔ 정비 항목의 기본 소모품), 없으면 설비|item:소모품 ③ 재고 부족 = 관련 알람 줄 → 같은 소모품의
--   예방 정비 줄 순. 예: 2075 반복 알람 + 축 윤활유 점검 기한 넘김 + 축 윤활유 재고 부족 → 한 줄 (DOC-07 §10.5, DOC-04 5장)
SELECT b.report_rank, b.rank_order, b.rank_group, b.item_kind, b.notification_id, b.rule_code, b.equipment_id, b.lot_no,
       b.title, b.occurred_at, b.sort_value,
       CASE
         WHEN b.alarm_code IS NOT NULL THEN b.alarm_equipment || '|' || b.alarm_code
         WHEN b.pm_item IS NOT NULL THEN coalesce(
             (SELECT min(a.alarm_equipment || '|' || a.alarm_code) FROM base a
                JOIN alarm_related_item r ON r.alarm_code = a.alarm_code
               WHERE a.alarm_equipment = b.pm_equipment AND r.item_no = b.pm_item),
             b.pm_equipment || '|item:' || b.pm_item)
         WHEN b.stock_item IS NOT NULL THEN coalesce(
             (SELECT min(a.alarm_equipment || '|' || a.alarm_code) FROM base a
                JOIN alarm_related_item r ON r.alarm_code = a.alarm_code WHERE r.item_no = b.stock_item),
             (SELECT min(x.pm_equipment || '|item:' || x.pm_item) FROM base x WHERE x.pm_item = b.stock_item))
       END AS group_key
  FROM base b;

-- 화면 줄 (FR-AST-COM-21): 같은 group_key는 한 줄로 묶어 가장 높은 순위 항목 자리에 둔다. 묶인 줄은 1건
--   (전체 N = 줄 수). member_count = 묶인 항목 수, members = 묶인 항목 전부 (자세히 펼칠 때)
CREATE OR REPLACE VIEW v_report_lines AS
WITH k AS (
    SELECT i.*, coalesce(i.group_key, i.item_kind || ':' || coalesce(i.notification_id::text, i.equipment_id, i.lot_no)) AS line_key
      FROM v_report_items i
), r AS (
    SELECT k.*,
           row_number() OVER (PARTITION BY line_key
                              ORDER BY rank_order, rank_group, sort_value DESC NULLS LAST, occurred_at) AS rn,
           count(*) OVER (PARTITION BY line_key) AS member_count
      FROM k
)
SELECT r.line_key, r.report_rank, r.rank_order, r.rank_group, r.item_kind, r.notification_id, r.rule_code,
       r.equipment_id, (SELECT e.process_code FROM equipment e WHERE e.equipment_id = r.equipment_id) AS process_code,
       r.lot_no, r.title, r.occurred_at, r.sort_value, r.member_count::int AS member_count,
       CASE r.report_rank WHEN 'R0' THEN 'SAFETY' WHEN 'R1' THEN 'URGENT' WHEN 'R2' THEN 'PRODUCTION'
                          WHEN 'R4' THEN 'INFO' ELSE 'CAUTION' END AS count_bucket,   -- 0-1은 주의에 센다
       (SELECT jsonb_agg(jsonb_build_object('item_kind', m.item_kind, 'report_rank', m.report_rank,
                         'notification_id', m.notification_id, 'rule_code', m.rule_code, 'title', m.title,
                         'occurred_at', m.occurred_at)
                         ORDER BY m.rank_order, m.rank_group, m.sort_value DESC NULLS LAST, m.occurred_at)
          FROM k m WHERE m.line_key = r.line_key) AS members
  FROM r WHERE r.rn = 1;

-- ---------------------------------------------------------------------
-- 교대 × 설비 지표 (R-44·R-45, DOC-07 6장)
--   PBT = 계획 가동 시간 − 그 설비 MAINT 시간 / A = RUN ÷ PBT / E = 기준 사이클 × PQ ÷ RUN / QBR = (GQ+RQ) ÷ PQ
--   상태 구간은 교대 시간 창으로 잘라서 센다. 진행 중 구간의 끝은 app_now()
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_equipment_kpi AS
WITH seg AS (
    SELECT s.shift_id, st.equipment_id, st.state_code,
           extract(epoch FROM (least(coalesce(st.end_at, app_now()), s.end_at) - greatest(st.start_at, s.start_at))) / 60 AS minutes
      FROM shift s
      JOIN equipment_state_log st ON st.start_at < s.end_at AND coalesce(st.end_at, 'infinity'::timestamptz) > s.start_at
), t AS (
    SELECT shift_id, equipment_id,
           sum(minutes) FILTER (WHERE state_code = 'RUN')   AS run_min,
           sum(minutes) FILTER (WHERE state_code = 'MAINT') AS maint_min,
           sum(minutes) FILTER (WHERE state_code = 'DOWN')  AS down_min
      FROM seg WHERE minutes > 0 GROUP BY 1, 2
), q AS (
    SELECT shift_id, equipment_id, sum(pq) AS pq, sum(gq) AS gq, sum(rq) AS rq, sum(sq) AS sq
      FROM operation_report GROUP BY 1, 2
)
SELECT s.shift_id, s.work_date, s.shift_type, e.equipment_id, e.process_code,
       s.planned_time_min,
       round(s.planned_time_min - coalesce(t.maint_min, 0), 2)                     AS pbt_min,
       round(coalesce(t.run_min, 0), 2) AS run_min, round(coalesce(t.down_min, 0), 2) AS down_min,
       round(coalesce(t.maint_min, 0), 2) AS maint_min,
       coalesce(q.pq, 0) AS pq, coalesce(q.gq, 0) AS gq, coalesce(q.rq, 0) AS rq, coalesce(q.sq, 0) AS sq,
       round(100 * coalesce(t.run_min, 0) / nullif(s.planned_time_min - coalesce(t.maint_min, 0), 0), 1) AS availability_pct,
       round(100 * e.std_cycle_min * q.pq / nullif(t.run_min, 0), 1)               AS performance_pct,
       round(100 * (q.gq + q.rq)::numeric / nullif(q.pq, 0), 1)                    AS quality_pct,
       round(100 * (coalesce(t.run_min, 0) / nullif(s.planned_time_min - coalesce(t.maint_min, 0), 0))
                 * (e.std_cycle_min * q.pq / nullif(t.run_min, 0))
                 * ((q.gq + q.rq)::numeric / nullif(q.pq, 0)), 1)                  AS oee_pct
  FROM shift s
 CROSS JOIN equipment e
  LEFT JOIN t ON t.shift_id = s.shift_id AND t.equipment_id = e.equipment_id
  LEFT JOIN q ON q.shift_id = s.shift_id AND q.equipment_id = e.equipment_id
 WHERE e.is_active;

-- 라인 OEE (R-44: OP-30 2대 합, 계획 가동 시간 = 480분 × 2대 — 한 대의 예방 정비는 빼지 않음)
CREATE OR REPLACE VIEW v_shift_line_oee AS
SELECT k.shift_id, k.work_date, k.shift_type,
       sum(k.planned_time_min) AS line_pbt_min, sum(k.run_min) AS run_min, sum(k.pq) AS pq,
       round(100 * sum(k.run_min) / nullif(sum(k.planned_time_min), 0), 1) AS availability_pct,
       round(100 * sum(e.std_cycle_min * k.pq) / nullif(sum(k.run_min), 0), 1) AS performance_pct,
       round(100 * sum(k.gq + k.rq)::numeric / nullif(sum(k.pq), 0), 1) AS quality_pct,
       round(100 * (sum(k.run_min) / nullif(sum(k.planned_time_min), 0))
                 * (sum(e.std_cycle_min * k.pq) / nullif(sum(k.run_min), 0))
                 * (sum(k.gq + k.rq)::numeric / nullif(sum(k.pq), 0)), 1) AS oee_pct
  FROM v_shift_equipment_kpi k JOIN equipment e USING (equipment_id)
 WHERE k.process_code = 'OP-30'
 GROUP BY k.shift_id, k.work_date, k.shift_type;

-- ---------------------------------------------------------------------
-- 로트 추적 (PRD-05, FR-PRD-05-01): 원자재 → 공정 5개 → 검사 → 보류 → 출하 한 줄
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_lot_trace AS
SELECT l.lot_no, l.status,
       jsonb_build_object(
         'material', (SELECT jsonb_build_object('material_lot_no', m.material_lot_no, 'received_date', m.received_date,
                                                'supplier_cert_no', m.supplier_cert_no, 'heat_batch_no', m.heat_batch_no)
                        FROM raw_material_lot m WHERE m.material_lot_no = l.material_lot_no),
         'order', (SELECT jsonb_build_object('order_no', o.order_no, 'order_qty', o.order_qty, 'due_at', o.due_at, 'status', o.status)
                     FROM production_order o WHERE o.order_no = l.order_no),
         'operations', (SELECT jsonb_agg(jsonb_build_object('process_code', r.process_code, 'equipment_id', r.equipment_id,
                                         'shift_id', r.shift_id, 'start_at', r.start_at, 'end_at', r.end_at,
                                         'pq', r.pq, 'gq', r.gq, 'rq', r.rq, 'sq', r.sq) ORDER BY p.seq, r.start_at)
                          FROM operation_report r JOIN process p USING (process_code) WHERE r.lot_no = l.lot_no),
         'inspection', (SELECT jsonb_build_object('plan_mode', ip.plan_mode, 'enhance_reason', ip.enhance_reason,
                                                  'judgement', ip.judgement, 'judged_at', ip.judged_at,
                                                  'fail_count', (SELECT count(*) FROM inspection_result x
                                                                  WHERE x.lot_no = l.lot_no AND x.use_for_judgement AND x.judgement = 'FAIL'))
                          FROM inspection_plan ip WHERE ip.lot_no = l.lot_no),
         'holds', (SELECT jsonb_agg(jsonb_build_object('hold_id', h.hold_id, 'trigger_type', h.trigger_type, 'held_at', h.held_at,
                                     'held_by', h.held_by, 'reason', h.hold_reason, 'result', h.result) ORDER BY h.held_at)
                     FROM lot_hold h WHERE h.lot_no = l.lot_no),
         'alarms', (SELECT jsonb_agg(jsonb_build_object('alarm_event_id', a.alarm_event_id, 'alarm_code', a.alarm_code,
                                      'equipment_id', a.equipment_id, 'occurred_at', a.occurred_at) ORDER BY a.occurred_at)
                      FROM alarm_event a WHERE a.lot_no = l.lot_no),
         'shipments', (SELECT jsonb_agg(jsonb_build_object('shipment_no', s.shipment_no, 'shipped_at', s.shipped_at,
                                         'customer_code', s.customer_code, 'qty', sl.qty) ORDER BY s.shipped_at)
                         FROM shipment_line sl JOIN shipment s USING (shipment_no)
                        WHERE sl.lot_no = l.lot_no AND s.status <> 'DRAFT')
       ) AS trace
  FROM production_lot l;

-- ---------------------------------------------------------------------
-- 교대 총 목표 (R-88, DOC-07 §4.1): 총 목표 = 목표 + 이월 (주간은 이월 0)
--   carry_over_is_provisional: 야간 이월이 "잠정" = 같은 날 주간 교대 보고서가 아직 확정 전 (확정되면 다시 계산)
--   is_report_confirmed = false 인 교대의 값을 다른 곳(브리핑·이월·일일 보고서)에서 쓰면 "잠정" (FR-AST-02-17)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_target AS
SELECT s.shift_id, s.work_date, s.shift_type, s.start_at, s.end_at, s.planned_time_min, s.supervisor_user_id,
       s.target_qty, s.carry_over_qty, s.target_qty + s.carry_over_qty AS total_target_qty,
       -- 주간 기록(보고서·공정 실적)이 없으면 이월은 0으로 정해져 잠정이 아니다 (fn_refresh_carry_over와 같은 기준)
       s.shift_type = 'NIGHT'
         AND EXISTS (SELECT 1 FROM shift d WHERE d.work_date = s.work_date AND d.shift_type = 'DAY'
                        AND (EXISTS (SELECT 1 FROM shift_report x WHERE x.shift_id = d.shift_id)
                             OR EXISTS (SELECT 1 FROM operation_report o WHERE o.shift_id = d.shift_id)))
         AND NOT EXISTS (SELECT 1 FROM shift d JOIN shift_report dr USING (shift_id)
                          WHERE d.work_date = s.work_date AND d.shift_type = 'DAY' AND dr.status IN ('CONFIRMED','REVISED'))
                                                                        AS carry_over_is_provisional,
       r.status AS report_status,
       coalesce(r.status IN ('CONFIRMED','REVISED'), false)            AS is_report_confirmed
  FROM shift s
  LEFT JOIN shift_report r USING (shift_id);

-- ---------------------------------------------------------------------
-- 교대 진행·예측 (R-48·R-88, DOC-07 8장, FR-PRD-01-15·16, FR-AST-02-04). 지난 교대는 교대 끝 시각 기준 값
--   교대 안 휴식 1시간 [가상: 팀 결정 2026-10-08]: 주간 12:00~13:00, 야간 00:00~01:00 (교대 사이 17:00~20:00·05:00~08:00은
--     라인 정지). 지난 계획 시간 = 교대 시작부터 지난 분 − 그중 휴식 분 (최대 계획 가동 시간) — DOC-07 8장 예 "4시간(240분) 뒤
--     … 남은 240분"과 같음 (12:00 = 휴식 시작)
--   속도 = 최근 계획 60분(휴식이 끼면 그만큼 앞으로 늘린 창)의 실적 ÷ 60, 교대 시작 후 1시간 안은 지금까지 실적 ÷ 지난 계획 시간
--   예측 = 실적 + 속도 × 남은 계획 시간 (반올림한 개수). 부족 = max(0, 총 목표 − 예측)
--   목표 미달 위험 = 예측 < 총 목표 × 90% (총 목표 90이면 81개, 93이면 83.7개)
--   손실(추정) = 고장 손실 + 속도 손실. 3D 라인 뷰는 합 하나, 교대·일일 보고서는 따로 (FR-PRD-01-16)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_shift_progress AS
WITH b0 AS (
    SELECT t.*, least(greatest(app_now(), t.start_at), t.end_at) AS as_of,
           CASE t.shift_type WHEN 'DAY' THEN (t.work_date + time '12:00') AT TIME ZONE 'Asia/Seoul'
                             ELSE (t.work_date + 1 + time '00:00') AT TIME ZONE 'Asia/Seoul' END AS break_start_at
      FROM v_shift_target t
), b AS (
    SELECT b0.*, b0.break_start_at + interval '1 hour' AS break_end_at,
           -- 최근 계획 60분 창의 시작: 휴식이 끼면 그만큼 앞으로
           b0.as_of - interval '60 minutes'
             - greatest(interval '0', least(b0.as_of, b0.break_start_at + interval '1 hour')
                                      - greatest(b0.as_of - interval '60 minutes', b0.break_start_at)) AS rate_from_at
      FROM b0
), m AS (
    SELECT b.*,
           least(b.planned_time_min,
                 greatest(0, (extract(epoch FROM (b.as_of - b.start_at))
                              - extract(epoch FROM greatest(interval '0', least(b.as_of, b.break_end_at)
                                                                          - greatest(b.start_at, b.break_start_at)))) / 60)
                )::numeric AS elapsed_min,
           (SELECT coalesce(sum(o.gq + o.rq), 0) FROM operation_report o
             WHERE o.shift_id = b.shift_id AND o.process_code = 'OP-50' AND o.end_at <= b.as_of)::int AS actual_qty,
           (SELECT coalesce(sum(o.gq + o.rq), 0) FROM operation_report o
             WHERE o.shift_id = b.shift_id AND o.process_code = 'OP-50' AND o.end_at <= b.as_of
               AND o.end_at > b.rate_from_at)::int AS last_hour_qty,
           (SELECT coalesce(sum(o.sq), 0) FROM operation_report o
             WHERE o.shift_id = b.shift_id AND o.end_at <= b.as_of)::int AS defect_qty,
           fn_failure_loss_qty(b.start_at, b.as_of) AS failure_loss_qty,
           fn_speed_loss_qty(b.start_at, b.as_of)   AS speed_loss_qty
      FROM b
), f AS (
    SELECT m.*,
           CASE WHEN m.elapsed_min <= 0 THEN NULL
                WHEN m.elapsed_min < 60 THEN m.actual_qty / m.elapsed_min
                ELSE m.last_hour_qty / 60.0 END AS rate_per_min
      FROM m
), p AS (
    SELECT f.*, round(f.actual_qty + f.rate_per_min * (f.planned_time_min - f.elapsed_min))::int AS forecast_qty FROM f
)
SELECT p.shift_id, p.work_date, p.shift_type, p.start_at, p.end_at, p.as_of, p.planned_time_min, p.supervisor_user_id,
       p.break_start_at, p.break_end_at,
       p.target_qty, p.carry_over_qty, p.total_target_qty, p.carry_over_is_provisional, p.report_status, p.is_report_confirmed,
       p.actual_qty, p.defect_qty,
       round(p.elapsed_min, 1) AS elapsed_min, round(p.planned_time_min - p.elapsed_min, 1) AS remaining_min,
       p.last_hour_qty, round(p.rate_per_min, 3) AS rate_per_min, p.forecast_qty,
       greatest(0, p.total_target_qty - p.forecast_qty)                AS shortfall_qty,
       p.forecast_qty < 0.9 * p.total_target_qty                        AS is_target_risk,
       p.failure_loss_qty, p.speed_loss_qty, p.failure_loss_qty + p.speed_loss_qty AS loss_qty,
       true                                                             AS loss_is_estimated
  FROM p;

-- ---------------------------------------------------------------------
-- MTTR·MTBF (R-45a, DOC-07 6.2) — 설비별 최근 30일. 3D 지표 카드에서 빼고 비서 질문으로 본다 (2026-10-07 UI 검토)
--   고장 = 정지 등급 DOWN만 (R-22). MTTR = DOWN 시간 합 ÷ 고장 횟수 (분)
--   MTBF = 고장 간격(그 기간 RUN 시간) 합 ÷ 고장 횟수 (시간) [제안: ISO 22400 TBF = 가동 시간]. 고장 0건이면 NULL("—")
--   MTTR 주의 = 120분 초과 (DOC-07 10.1)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_equipment_reliability_30d AS
WITH w AS (SELECT app_now() - interval '30 days' AS t0, app_now() AS t1),
seg AS (
    SELECT st.equipment_id, st.state_code,
           extract(epoch FROM (least(coalesce(st.end_at, w.t1), w.t1) - greatest(st.start_at, w.t0))) / 60 AS minutes,
           st.start_at >= w.t0 AS started_in_window
      FROM equipment_state_log st, w
     WHERE st.start_at < w.t1 AND coalesce(st.end_at, 'infinity'::timestamptz) > w.t0
)
SELECT e.equipment_id, e.process_code,
       count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window)::int        AS failure_count,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 1)                      AS down_min,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'RUN'), 1)                       AS run_min,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window)
             / nullif(count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 0), 1) AS mttr_min,
       round(sum(s.minutes) FILTER (WHERE s.state_code = 'RUN') / 60
             / nullif(count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 0), 1) AS mtbf_hours,
       coalesce(sum(s.minutes) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window)
             / nullif(count(*) FILTER (WHERE s.state_code = 'DOWN' AND s.started_in_window), 0) > 120, false) AS is_mttr_warn
  FROM equipment e
  LEFT JOIN seg s USING (equipment_id)
 WHERE e.is_active
 GROUP BY e.equipment_id, e.process_code;

-- ===================== db/views/20_report_functions.sql =====================
-- =====================================================================
-- 20_report_functions.sql (views 단계에서 만든다 — v_report_items 등 뷰를 쓰므로) — 교대·일일 보고서 AI비서 초안의 "숫자 칸" 만들기 (PRD-02·04, R-12·R-46·R-54·R-72·R-73)
-- 숫자는 프로그램이 계산한다 (FR-AST-COM-05). 문장 칸(특이 사항·오늘의 문제 문장)은 AI 비서 ②가
-- 나중에 같은 버전 안에서 채우거나, 비서가 꺼져 있으면 기본 문구로 둔다.
-- 생성 시각 (R-72, 2026-10-13): 교대 보고서 = 교대 끝(17:00·05:00) + 그 교대 반장에게 확정 요청 알림,
--           일일 보고서 = 그 생산일 야간 교대 보고서가 확정되는 즉시 (trg_shift_report_confirmed), 06:00까지 확정이 없으면
--           06:00 (스케줄러가 부름) + MGR에게 일일 보고서 확정 요청(DAILY_REPORT_PENDING). 교대 보고서가 확정되면 칸을 다시 채운다
-- =====================================================================

-- 보고 항목 목록 글 (6.43 순서, 개수 자르지 않음 — R-73, FR-AST-COM-21)
--   머리 "전체 N건 (안전 a · 긴급 b · 생산 c · 주의 d · 참고 e)" — N = 묶은 뒤 줄 수, 0-1 오래 방치는 주의에 셈
--   순위마다 한 칸. 빈 순위는 "-", 순위 0이 비면 "잠금·표지 중인 설비 없음" (DOC-01 §3.3, DOC-07 §10.5)
CREATE OR REPLACE FUNCTION fn_report_items_text() RETURNS text
LANGUAGE sql STABLE AS $$
    WITH ranks(report_rank, rank_order, rank_name) AS (
        VALUES ('R0', 0, '0 안전'), ('R0_1', 1, '0-1 오래 방치'), ('R1', 2, '1 긴급'), ('R2', 3, '2 생산 위험'),
               ('R3', 4, '3 주의'), ('R4', 5, '4 참고')
    ), lines AS (SELECT * FROM v_report_lines)
    SELECT format('전체 %s건 (안전 %s · 긴급 %s · 생산 %s · 주의 %s · 참고 %s)',
                  (SELECT count(*) FROM lines),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'SAFETY'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'URGENT'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'PRODUCTION'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'CAUTION'),
                  (SELECT count(*) FROM lines WHERE count_bucket = 'INFO'))
        || E'\n' || string_agg(
            '[' || k.rank_name || '] ' ||
            coalesce((SELECT string_agg(E'\n- ' || l.title
                                        || CASE WHEN l.member_count > 1 THEN format(' (같은 원인 %s건 묶음)', l.member_count) ELSE '' END,
                                        '' ORDER BY l.rank_group, l.sort_value DESC NULLS LAST, l.occurred_at)
                        FROM lines l WHERE l.report_rank = k.report_rank),
                     CASE WHEN k.report_rank = 'R0' THEN '잠금·표지 중인 설비 없음' ELSE '-' END),
            E'\n' ORDER BY k.rank_order)
      FROM ranks k;
$$;

-- 교대 보고서 초안. 이미 있으면 그대로 둔다. 반환: 'CREATED' / 'EXISTS'
CREATE OR REPLACE FUNCTION fn_create_shift_report_draft(p_shift_id text, p_at timestamptz DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    s shift%ROWTYPE; v_actual int; v_defect int; v_avail jsonb; v_handover text; v_content jsonb;
BEGIN
    -- 이미 있거나, 지워졌어도 버전 기록이 남아 있으면 다시 만들지 않는다 (문서는 지우지 않는 것이 원칙)
    IF EXISTS (SELECT 1 FROM shift_report WHERE shift_id = p_shift_id)
       OR EXISTS (SELECT 1 FROM document_revision WHERE doc_type = 'SHIFT_REPORT' AND doc_key = p_shift_id) THEN
        RETURN 'EXISTS';
    END IF;
    SELECT * INTO STRICT s FROM shift WHERE shift_id = p_shift_id;
    -- R-46 교대 실적 = 그 교대에 OP-50을 마친 GQ + RQ
    v_actual := fn_shift_actual_qty(p_shift_id);
    SELECT coalesce(sum(sq), 0) INTO v_defect FROM operation_report WHERE shift_id = p_shift_id;
    -- 가동률은 OP-30 설비별 2개 값
    SELECT coalesce(jsonb_object_agg(equipment_id, availability_pct), '{}'::jsonb) INTO v_avail
      FROM v_shift_equipment_kpi WHERE shift_id = p_shift_id AND process_code = 'OP-30';
    v_handover := fn_report_items_text();
    -- 생산 칸 목표 = 총 목표 (목표 + 이월, R-88 — FR-PRD-02-02)
    v_content := jsonb_build_object('target_qty', s.target_qty + s.carry_over_qty, 'shift_target_qty', s.target_qty,
                                    'carry_over_qty', s.carry_over_qty, 'actual_qty', v_actual, 'defect_qty', v_defect,
                                    'availability_pct', v_avail, 'handover_text', v_handover);
    INSERT INTO shift_report (shift_id, status, target_qty, actual_qty, defect_qty, availability_pct, notable_text, handover_text,
                              current_version)
    VALUES (p_shift_id, 'AI_DRAFT', s.target_qty + s.carry_over_qty, v_actual, v_defect, v_avail, '(비서 문장 대기)',
            v_handover, 0);
    PERFORM fn_save_revision('SHIFT_REPORT', p_shift_id, 'AI', NULL, NULL, 'AI_DRAFT', v_content, '[]'::jsonb, NULL, v_at);
    -- 교대 보고서 확정 요청 → 그 교대 반장 (FR-AST-02-17, 6.36 SHIFT_REPORT_PENDING — 2026-10-07 최종 검토로 교대 끝).
    -- 확정하면 자동 처리 (trg_shift_report_confirmed). 확정 전 그 교대 값은 쓰는 곳마다 "잠정"
    PERFORM fn_raise_notification('SHIFT_REPORT_PENDING', format('%s 교대 보고서 확정 요청', p_shift_id),
                                  jsonb_build_object('shift_id', p_shift_id), v_at, p_recipients => ARRAY[s.supervisor_user_id]);
    -- 주간이 끝나면 같은 날 야간 이월을 채운다 (야간 시작 전, R-88)
    IF s.shift_type = 'DAY' THEN
        PERFORM fn_refresh_carry_over(s.work_date);
    END IF;
    RETURN 'CREATED';
END $$;

-- 일일 보고서 초안 (야간 교대 보고서 확정 즉시, 늦어도 다음 날 06:00 — R-72). 확정 안 된 교대 칸은 원기록 집계 + "잠정".
-- 반환: 잠정 교대 수 (이미 있으면 0)
--   확정 요청(SHIFT_REPORT_PENDING)은 교대 끝 초안 때 이미 갔다 — 여기서 다시 보내지 않는다 (2026-10-07 최종 검토).
--   교대 초안이 빠져 있으면 여기서 만든다 (그때 확정 요청도 같이 감).
--   하루 목표 = work_day.daily_target_qty (180 고정, 이월을 더하지 않음). 부족 = 180 − 하루 실적 (R-88, 조회 때 계산)
CREATE OR REPLACE FUNCTION fn_create_daily_report_draft(p_work_date date, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    d work_day%ROWTYPE; v_actual int; v_defect int; v_oee numeric; v_fail numeric; v_speed numeric;
    v_start timestamptz; v_end timestamptz; v_pending int := 0; sh record; v_issues text; v_rev bigint;
BEGIN
    SELECT * INTO STRICT d FROM work_day WHERE work_date = p_work_date;
    IF NOT d.is_workday OR EXISTS (SELECT 1 FROM daily_report WHERE work_date = p_work_date)
       OR EXISTS (SELECT 1 FROM document_revision WHERE doc_type = 'DAILY_REPORT' AND doc_key = p_work_date::text) THEN
        RETURN 0;
    END IF;
    FOR sh IN SELECT s.shift_id, s.supervisor_user_id, r.status FROM shift s LEFT JOIN shift_report r USING (shift_id)
               WHERE s.work_date = p_work_date LOOP
        IF sh.status IS NULL THEN
            PERFORM fn_create_shift_report_draft(sh.shift_id, v_at);
        END IF;
        IF coalesce(sh.status, 'AI_DRAFT') NOT IN ('CONFIRMED','REVISED') THEN
            v_pending := v_pending + 1;
        END IF;
    END LOOP;
    -- R-12 교대 보고서 2개 실적 합 (잠정 교대는 원기록 집계로 만든 초안 값)
    SELECT coalesce(sum(r.actual_qty), 0), coalesce(sum(r.defect_qty), 0) INTO v_actual, v_defect
      FROM shift_report r JOIN shift s USING (shift_id) WHERE s.work_date = p_work_date;
    SELECT min(start_at), max(end_at) INTO v_start, v_end FROM shift WHERE work_date = p_work_date;
    -- 라인 OEE (OP-30 2대, 두 교대 합)
    SELECT round(100 * (sum(k.run_min) / nullif(sum(k.planned_time_min), 0))
                     * (sum(e.std_cycle_min * k.pq) / nullif(sum(k.run_min), 0))
                     * (sum(k.gq + k.rq)::numeric / nullif(sum(k.pq), 0)), 2)
      INTO v_oee FROM v_shift_equipment_kpi k JOIN equipment e USING (equipment_id)
     WHERE k.work_date = p_work_date AND k.process_code = 'OP-30';
    -- 고장 손실 = 고장 정지 손실 합, 속도 손실 = 병목 구간 속도 손실 합 (추정 — 일일 보고서는 따로 보인다)
    v_fail := fn_failure_loss_qty(v_start, v_end);
    v_speed := fn_speed_loss_qty(v_start, v_end);
    v_issues := fn_report_items_text();
    INSERT INTO daily_report (work_date, status, target_qty, actual_qty, defect_qty, oee_pct, failure_loss_qty, speed_loss_qty,
                              issues_summary, current_version)
    VALUES (p_work_date, 'AI_DRAFT', coalesce(d.daily_target_qty, 0), v_actual, v_defect, coalesce(v_oee, 0), v_fail, v_speed,
            v_issues || CASE WHEN v_pending > 0 THEN format(E'\n(잠정: 확정 안 된 교대 %s개)', v_pending) ELSE '' END, 0);
    PERFORM fn_save_revision('DAILY_REPORT', p_work_date::text, 'AI', NULL, NULL, 'AI_DRAFT',
        jsonb_build_object('actual_qty', v_actual, 'defect_qty', v_defect, 'oee_pct', v_oee, 'pending_shifts', v_pending),
        '[]'::jsonb, NULL, v_at);
    -- 일일 보고서 확정 요청 → MGR (6.36 DAILY_REPORT_PENDING, 2026-10-13). 가리키는 기록 = 그 보고서의 v0 (근무일 칸이 없어서)
    SELECT revision_id INTO v_rev FROM document_revision
     WHERE doc_type = 'DAILY_REPORT' AND doc_key = p_work_date::text AND version_no = 0;
    PERFORM fn_raise_notification('DAILY_REPORT_PENDING', format('%s 일일 보고서 확정 요청', p_work_date),
                                  jsonb_build_object('revision_id', v_rev), v_at);
    RETURN v_pending;
END $$;

-- 교대 보고서가 확정되면 확정 전 일일 보고서의 그 칸(실적·불량·잠정 표시)을 다시 채우고 수정 이력 1줄 (DOC-01 §3.3, R-72).
-- 이력의 작성자 = 확정한 반장 (AI 작성자는 v0만 — ck_document_revision_ai_v0). 반환: 새 버전 (바뀐 것이 없으면 그대로, 없으면 NULL)
CREATE OR REPLACE FUNCTION fn_refill_daily_report(p_work_date date, p_actor text, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    d daily_report%ROWTYPE; v_actual int; v_defect int; v_pending int; v_issues text; v_ver int;
    v_changes jsonb := '[]'::jsonb;
BEGIN
    SELECT * INTO d FROM daily_report WHERE work_date = p_work_date;
    IF NOT FOUND OR d.status NOT IN ('AI_DRAFT','EDITING') THEN RETURN NULL; END IF;
    SELECT coalesce(sum(r.actual_qty), 0), coalesce(sum(r.defect_qty), 0) INTO v_actual, v_defect
      FROM shift_report r JOIN shift s USING (shift_id) WHERE s.work_date = p_work_date;
    SELECT count(*) INTO v_pending FROM shift s LEFT JOIN shift_report r USING (shift_id)
     WHERE s.work_date = p_work_date AND coalesce(r.status, 'AI_DRAFT') NOT IN ('CONFIRMED','REVISED');
    v_issues := regexp_replace(d.issues_summary, '\n?\(잠정: 확정 안 된 교대 [0-9]+개\)', '', 'g')
                || CASE WHEN v_pending > 0 THEN format(E'\n(잠정: 확정 안 된 교대 %s개)', v_pending) ELSE '' END;
    IF v_actual <> d.actual_qty THEN
        v_changes := v_changes || jsonb_build_object('field', 'actual_qty', 'before', d.actual_qty, 'after', v_actual);
    END IF;
    IF v_defect <> d.defect_qty THEN
        v_changes := v_changes || jsonb_build_object('field', 'defect_qty', 'before', d.defect_qty, 'after', v_defect);
    END IF;
    IF v_issues <> d.issues_summary THEN
        v_changes := v_changes || jsonb_build_object('field', 'issues_summary', 'before', d.issues_summary, 'after', v_issues);
    END IF;
    IF jsonb_array_length(v_changes) = 0 THEN RETURN d.current_version; END IF;
    v_ver := fn_save_revision('DAILY_REPORT', p_work_date::text, 'HUMAN', p_actor, '교대 보고서 확정으로 칸을 다시 채움 (R-72)',
                              d.status, jsonb_build_object('actual_qty', v_actual, 'defect_qty', v_defect,
                                                           'pending_shifts', v_pending), v_changes, NULL, p_at);
    UPDATE daily_report SET actual_qty = v_actual, defect_qty = v_defect, issues_summary = v_issues, current_version = v_ver
     WHERE work_date = p_work_date;
    RETURN v_ver;
END $$;

-- 확정되면 확정 요청 알림 자동 처리 (6.36 SHIFT_REPORT_PENDING).
-- 주간 교대 보고서가 확정되면 그날 야간 이월을 확정 실적으로 다시 계산한다 (R-88, 잠정이 풀림).
-- 일일 보고서가 이미 있으면(확정 전) 그 칸을 다시 채운다 (R-72)
CREATE OR REPLACE FUNCTION trg_shift_report_confirmed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('CONFIRMED','REVISED') AND OLD.status NOT IN ('CONFIRMED','REVISED') THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'SHIFT_REPORT_PENDING' AND shift_id = NEW.shift_id AND NOT is_processed),
                                NEW.confirmed_by, NEW.confirmed_at);
        IF (SELECT shift_type FROM shift WHERE shift_id = NEW.shift_id) = 'DAY' THEN
            PERFORM fn_refresh_carry_over((SELECT work_date FROM shift WHERE shift_id = NEW.shift_id));
        END IF;
        PERFORM fn_refill_daily_report((SELECT work_date FROM shift WHERE shift_id = NEW.shift_id), NEW.confirmed_by,
                                       NEW.confirmed_at);
        -- 야간 교대 보고서가 확정되면 그 생산일 일일 보고서 초안을 바로 만든다 (R-72, 2026-10-13). 이미 있으면 그대로
        IF (SELECT shift_type FROM shift WHERE shift_id = NEW.shift_id) = 'NIGHT' THEN
            PERFORM fn_create_daily_report_draft((SELECT work_date FROM shift WHERE shift_id = NEW.shift_id),
                                                 coalesce(NEW.confirmed_at, app_now()));
        END IF;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER shift_report_confirmed AFTER UPDATE OF status ON shift_report
    FOR EACH ROW EXECUTE FUNCTION trg_shift_report_confirmed();

-- 작업지시서 상태가 바뀔 때 (6.36 처리 표, 2026-10-13):
--   승인·취소 → 승인 대기 알림(APPROVAL_WAIT_*) 자동 처리. 승인 → 담당 MNT에게 "작업지시서 배정"(WO_ASSIGNED)
--   AI비서 초안 → 수정 중(보전 담당자가 저장) → 초안 검토 알림(WO_DRAFT_READY) 자동 처리
--   승인 → 진행 중([작업 시작]) → 배정 알림 자동 처리 (담당 MNT가 작업지시서를 "열면"도 처리 — API-MNT-06 GET)
--   작업지시서를 취소하면 남은 초안 검토·배정 알림도 닫는다
CREATE OR REPLACE FUNCTION trg_work_order_approved() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('APPROVED','CANCELLED') AND OLD.status IN ('AI_DRAFT','EDITING') THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code IN ('APPROVAL_WAIT_30M','APPROVAL_WAIT_2H') AND wo_no = NEW.wo_no AND NOT is_processed),
                                coalesce(NEW.approved_by, NEW.cancelled_by), coalesce(NEW.approved_at, NEW.cancelled_at));
    END IF;
    IF NEW.status = 'APPROVED' AND OLD.status IN ('AI_DRAFT','EDITING') AND NEW.assignee_user_id IS NOT NULL THEN
        PERFORM fn_raise_notification('WO_ASSIGNED', format('작업지시서 %s 배정 (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id),
                                      NEW.approved_at, p_recipients => ARRAY[NEW.assignee_user_id]);
    END IF;
    IF OLD.status = 'AI_DRAFT' AND NEW.status <> 'AI_DRAFT' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_DRAFT_READY' AND wo_no = NEW.wo_no AND NOT is_processed),
                                NULL, app_now());
    END IF;
    IF (NEW.status = 'IN_PROGRESS' AND OLD.status = 'APPROVED') OR NEW.status = 'CANCELLED' THEN
        PERFORM fn_auto_process(ARRAY(SELECT notification_id FROM notification
                                       WHERE rule_code = 'WO_ASSIGNED' AND wo_no = NEW.wo_no AND NOT is_processed),
                                CASE WHEN NEW.status = 'IN_PROGRESS' THEN NEW.assignee_user_id END, app_now());
    END IF;
    RETURN NULL;
END $$;

-- 작업지시서 AI비서 초안이 생기면 → 그 설비 MNT에게 "작업지시서 초안 검토" (6.36 WO_DRAFT_READY, 2026-10-13).
-- 받는 사람 = 보전 담당자 전원 (긴급 알림 처리 책임 MNT와 같은 사람 — 설비별 담당 MNT 칸이 없어 MNT 전원 [제안])
CREATE OR REPLACE FUNCTION trg_work_order_draft_ready() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'AI_DRAFT' AND current_setting('app.loading', true) IS DISTINCT FROM 'on' THEN
        PERFORM fn_raise_notification('WO_DRAFT_READY', format('작업지시서 초안 검토: %s (%s)', NEW.wo_no, NEW.title),
                                      jsonb_build_object('wo_no', NEW.wo_no, 'equipment_id', NEW.equipment_id), NEW.created_at);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER work_order_draft_ready AFTER INSERT ON maintenance_work_order
    FOR EACH ROW EXECUTE FUNCTION trg_work_order_draft_ready();

-- 일일 보고서를 MGR이 확정하면 확정 요청 알림 자동 처리 (6.36 DAILY_REPORT_PENDING)
CREATE OR REPLACE FUNCTION trg_daily_report_confirmed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('CONFIRMED','REVISED') AND OLD.status NOT IN ('CONFIRMED','REVISED') THEN
        PERFORM fn_auto_process(ARRAY(SELECT n.notification_id FROM notification n
                                        JOIN document_revision v ON v.revision_id = n.revision_id
                                       WHERE n.rule_code = 'DAILY_REPORT_PENDING' AND v.doc_type = 'DAILY_REPORT'
                                         AND v.doc_key = NEW.work_date::text AND NOT n.is_processed),
                                NEW.confirmed_by, NEW.confirmed_at);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER daily_report_confirmed AFTER UPDATE OF status ON daily_report
    FOR EACH ROW EXECUTE FUNCTION trg_daily_report_confirmed();
CREATE TRIGGER work_order_approved AFTER UPDATE OF status ON maintenance_work_order
    FOR EACH ROW EXECUTE FUNCTION trg_work_order_approved();

-- 스케줄러가 몇 분마다 부르는 시간 규칙 알림 (승인 대기·예방 정비 기한·CMM 결과 미수신·목표 미달 위험) + 지금 야간 이월. 반환: 새 알림 수
CREATE OR REPLACE FUNCTION fn_run_time_rules(p_cmm_wait_min int DEFAULT 10, p_at timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_at timestamptz := coalesce(p_at, app_now());
    v_today date := (v_at AT TIME ZONE 'Asia/Seoul')::date;
    v_n int := 0; r record;
BEGIN
    -- 승인 대기 30분(참고)·2시간(주의) — DOC-07 10.2
    FOR r IN SELECT wo_no, equipment_id, created_at FROM maintenance_work_order
              WHERE status IN ('AI_DRAFT','EDITING') AND created_at <= v_at - interval '30 minutes' LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_30M' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_30M', format('작업지시서 %s 승인 대기 30분', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
        IF r.created_at <= v_at - interval '2 hours'
           AND NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'APPROVAL_WAIT_2H' AND wo_no = r.wo_no) THEN
            PERFORM fn_raise_notification('APPROVAL_WAIT_2H', format('작업지시서 %s 승인 대기 2시간', r.wo_no),
                                          jsonb_build_object('wo_no', r.wo_no, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 예방 정비 기한 하루 전(참고)·넘김(주의) — 달력에 있는 항목만
    FOR r IN SELECT pm_task_id, equipment_id, item_name, next_due_date FROM v_pm_task_due
              WHERE is_active AND on_calendar AND next_due_date IS NOT NULL AND next_due_date <= v_today + 1 LOOP
        IF r.next_due_date = v_today + 1 AND NOT EXISTS (SELECT 1 FROM notification
                WHERE rule_code = 'PM_DUE_SOON' AND pm_task_id = r.pm_task_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('PM_DUE_SOON', format('%s 예방 정비 내일: %s', r.equipment_id, r.item_name),
                                          jsonb_build_object('pm_task_id', r.pm_task_id, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        ELSIF r.next_due_date < v_today AND NOT EXISTS (SELECT 1 FROM notification
                WHERE rule_code = 'PM_OVERDUE' AND pm_task_id = r.pm_task_id AND NOT is_processed) THEN
            PERFORM fn_raise_notification('PM_OVERDUE', format('%s 예방 정비 기한 넘김: %s', r.equipment_id, r.item_name),
                                          jsonb_build_object('pm_task_id', r.pm_task_id, 'equipment_id', r.equipment_id), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- CMM 결과 미수신 (대기 시간은 [선택 필요: 기술 회의])
    FOR r IN SELECT instruction_id, lot_no, part_seq FROM cmm_instruction
              WHERE status = 'STARTED' AND started_at < v_at - make_interval(mins => p_cmm_wait_min) LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'CMM_NO_RESULT' AND lot_no = r.lot_no AND NOT is_processed) THEN
            PERFORM fn_raise_notification('CMM_NO_RESULT', format('측정 결과 미수신: %s 순번 %s', r.lot_no, r.part_seq),
                                          jsonb_build_object('lot_no', r.lot_no, 'equipment_id', 'CMM-01'), v_at);
            v_n := v_n + 1;
        END IF;
    END LOOP;
    -- 지금 야간 교대의 이월 (R-88). 주간 초안·확정 때 채우지만, 적재한 데이터·늦은 확정에 대비해 다시 맞춘다
    PERFORM fn_refresh_carry_over(work_date) FROM shift WHERE shift_type = 'NIGHT' AND start_at <= v_at AND end_at > v_at;
    -- 목표 미달 위험 (R-48·R-88, FR-AST-02-04): 지금 교대의 예측 < 총 목표(목표 + 이월) × 90% → 반장. 교대마다 1번.
    --   교대 시작 1시간 뒤부터 본다 [제안] — 시작 직후는 첫 부품이 OP-50에 닿기 전이라 예측이 0에 가깝다 (DOC-07 8장)
    FOR r IN SELECT shift_id, forecast_qty, total_target_qty, shortfall_qty, carry_over_qty FROM v_shift_progress
              WHERE start_at <= v_at AND end_at > v_at AND elapsed_min >= 60 AND is_target_risk LOOP
        IF NOT EXISTS (SELECT 1 FROM notification WHERE rule_code = 'TARGET_RISK' AND shift_id = r.shift_id) THEN
            PERFORM fn_raise_notification('TARGET_RISK',
                format('목표 미달 위험: 이 속도면 목표보다 %s개 부족 (예측 %s / 총 목표 %s)', r.shortfall_qty, r.forecast_qty,
                       r.total_target_qty),
                jsonb_build_object('shift_id', r.shift_id), v_at,
                p_related_info => format('총 목표 = 목표 %s + 이월 %s (DOC-07 §4.1·8장)', r.total_target_qty - r.carry_over_qty,
                                         r.carry_over_qty));
            v_n := v_n + 1;
        END IF;
    END LOOP;
    RETURN v_n;
END $$;

-- ===================== db/seed/10_code_labels.sql =====================
-- 생성: tools/gen_code_labels.py (논리ERD_최종본 6장). 손으로 고치지 말고 스크립트를 다시 돌린다.
INSERT INTO code_label (code_group, code, name_ko, sort_order, source_ref) VALUES
  ('equipment_state_log.state_code', 'RUN', '가공 중', 1, '6.1'),
  ('equipment_state_log.state_code', 'IDLE', '대기', 2, '6.1'),
  ('equipment_state_log.state_code', 'BLOCKED', '막힘', 3, '6.1'),
  ('equipment_state_log.state_code', 'SETUP', '셋업(준비)', 4, '6.1'),
  ('equipment_state_log.state_code', 'DOWN', '고장 정지', 5, '6.1'),
  ('equipment_state_log.state_code', 'MAINT', '계획 정비', 6, '6.1'),
  ('equipment_state_log.mtconnect_execution', 'ACTIVE', '실행 중', 1, '6.2'),
  ('equipment_state_log.mtconnect_execution', 'READY', '준비됨 (실행 안 함)', 2, '6.2'),
  ('equipment_state_log.mtconnect_execution', 'STOPPED', '멈춤', 3, '6.2'),
  ('alarm_master.severity', 'STOP', '정지', 1, '6.3'),
  ('alarm_master.severity', 'WARN', '주의', 2, '6.3'),
  ('alarm_master.severity', 'GUIDE', '조작 안내', 3, '6.3'),
  ('alarm_master.responder', 'OPR', '작업자', 1, '6.4'),
  ('alarm_master.responder', 'MNT', '보전 담당자', 2, '6.4'),
  ('downtime_reason.reason_code', 'F01', '서보·앰프', 1, '6.5'),
  ('downtime_reason.reason_code', 'F02', '주축', 2, '6.5'),
  ('downtime_reason.reason_code', 'F03', '공구 교환장치', 3, '6.5'),
  ('downtime_reason.reason_code', 'F04', '윤활', 4, '6.5'),
  ('downtime_reason.reason_code', 'F05', '공압', 5, '6.5'),
  ('downtime_reason.reason_code', 'F06', '절삭유', 6, '6.5'),
  ('downtime_reason.reason_code', 'M01', '소재 대기', 7, '6.5'),
  ('downtime_reason.reason_code', 'M02', '앞 공정 대기', 8, '6.5'),
  ('downtime_reason.reason_code', 'M03', '뒤 공정 막힘', 9, '6.5'),
  ('downtime_reason.reason_code', 'S01', '작업지시 교체 (로트 교체)', 10, '6.5'),
  ('downtime_reason.reason_code', 'S02', '공구 교체', 11, '6.5'),
  ('downtime_reason.reason_code', 'S03', '초품 검사', 12, '6.5'),
  ('downtime_reason.reason_code', 'S04', '교대 시작·끝 점검 — VF-2 교대 시작(절삭유·공기 압력·물 빼기·공구 홀더)·끝(칩 청소), DOC-04 2.1 (2026-10-13)', 13, '6.5'),
  ('downtime_reason.reason_code', 'O01', '프로그램 오류', 14, '6.5'),
  ('downtime_reason.reason_code', 'O02', '모드 오류', 15, '6.5'),
  ('downtime_reason.reason_code', 'O03', '도어 열림', 16, '6.5'),
  ('downtime_reason.reason_code', 'O04', '부품 교체 대기 — 한 부품을 끝내고 다음 부품을 올리기까지 (MIL-01·VF-2, 1분 이상이면 기록, NIST READY) (2026-10-13)', 17, '6.5'),
  ('downtime_reason.reason_code', 'P01', '예방 정비', 18, '6.5'),
  ('downtime_reason.reason_code', 'P02', '휴식', 19, '6.5'),
  ('downtime_reason.reason_code', 'P03', '계획 없음', 20, '6.5'),
  ('equipment_state_log.reason_status', 'SUGGESTED', '추천 (AI비서 초안)', 1, '6.6'),
  ('equipment_state_log.reason_status', 'ENTERED', '입력', 2, '6.6'),
  ('equipment_state_log.reason_status', 'CONFIRMED', '확정', 3, '6.6'),
  ('production_order.status', 'WAITING', '대기', 1, '6.7'),
  ('production_order.status', 'IN_PROGRESS', '생산 중', 2, '6.7'),
  ('production_order.status', 'DONE', '완료', 3, '6.7'),
  ('production_order.status', 'CANCELLED', '취소', 4, '6.7'),
  ('production_lot.status', 'IN_PROCESS', '생산 중', 1, '6.8'),
  ('production_lot.status', 'WAIT_INSPECTION', '검사 대기', 2, '6.8'),
  ('production_lot.status', 'WAIT_JUDGEMENT', '판정 대기', 3, '6.8'),
  ('production_lot.status', 'HOLD_REVIEW', '보류 검토', 4, '6.8'),
  ('production_lot.status', 'PASSED', '합격 (출하 가능)', 5, '6.8'),
  ('production_lot.status', 'ON_HOLD', '보류', 6, '6.8'),
  ('production_lot.status', 'RELEASED', '해제', 7, '6.8'),
  ('production_lot.status', 'SCRAPPED', '폐기', 8, '6.8'),
  ('raw_material_lot.status', 'WAIT_RECEIPT_CHECK', '입고 검사 대기', 1, '6.9'),
  ('raw_material_lot.status', 'AVAILABLE', '사용 가능', 2, '6.9'),
  ('raw_material_lot.status', 'RECEIPT_HOLD', '입고 보류', 3, '6.9'),
  ('shift.shift_type', 'DAY', '주간', 1, '6.10'),
  ('shift.shift_type', 'NIGHT', '야간', 2, '6.10'),
  ('bottleneck_log.cause_code', 'C1', '사이클 시간 증가 (공구 수명 80% 넘음, 7.0 → 8.0~8.5분)', 1, '6.11'),
  ('bottleneck_log.cause_code', 'C2', '설비 1대만 가동 (예방 정비·긴 셋업·반복 알람 2단계 원인 점검)', 2, '6.11'),
  ('bottleneck_log.cause_code', 'C3', '검사 강화 (0.9 → 5.0분/개)', 3, '6.11'),
  ('bottleneck_log.cause_code', 'C4', '묶음 대기 (OP-40 로트별 묶음, 최대 30개) — 병목 판단에서 제외', 4, '6.11'),
  ('bottleneck_log.cause_code', 'FAILURE', '설비 DOWN', 5, '6.11'),
  ('bottleneck_log.cause_code', 'BASE', '조건에 맞는 공정이 없어 기준 병목 OP-30으로 돌아옴', 6, '6.11'),
  ('lot_hold.trigger_type', 'AI_SUSPECT', 'AI 비서 의심 로트 제안 (정지 등급 알람·공구 수명 초과 중 가공) → 반장 보류', 1, '6.12'),
  ('lot_hold.trigger_type', 'INSPECTION_FAIL', '측정 불합격 → 보류 검토 → 반장 보류', 2, '6.12'),
  ('lot_hold.trigger_type', 'SUPERVISOR', '반장 판단 (그 밖)', 3, '6.12'),
  ('maintenance_work_order.status', 'AI_DRAFT', 'AI비서 초안', 1, '6.13'),
  ('maintenance_work_order.status', 'EDITING', '수정 중', 2, '6.13'),
  ('maintenance_work_order.status', 'APPROVED', '승인', 3, '6.13'),
  ('maintenance_work_order.status', 'IN_PROGRESS', '진행 중', 4, '6.13'),
  ('maintenance_work_order.status', 'DONE', '완료', 5, '6.13'),
  ('maintenance_work_order.status', 'CANCELLED', '취소', 6, '6.13'),
  ('work_record.record_type', 'FULL', '작업기록서', 1, '6.14'),
  ('work_record.record_type', 'SIMPLE', '간이 작업기록', 2, '6.14'),
  ('work_record.status', 'AI_DRAFT', 'AI비서 초안', 1, '6.15'),
  ('work_record.status', 'EDITING', '수정 중', 2, '6.15'),
  ('work_record.status', 'CONFIRMED', '확정', 3, '6.15'),
  ('work_record.status', 'CHECKED', '확인', 4, '6.15'),
  ('report.status', 'AI_DRAFT', 'AI비서 초안', 1, '6.16'),
  ('report.status', 'EDITING', '수정 중', 2, '6.16'),
  ('report.status', 'CONFIRMED', '확정', 3, '6.16'),
  ('report.status', 'REVISED', '확정 후 수정', 4, '6.16'),
  ('document_revision.doc_type', 'WORK_ORDER', '작업지시서', 1, '6.17'),
  ('document_revision.doc_type', 'WORK_RECORD', '작업기록서 (간이 포함)', 2, '6.17'),
  ('document_revision.doc_type', 'SHIFT_REPORT', '교대 보고서', 3, '6.17'),
  ('document_revision.doc_type', 'DAILY_REPORT', '일일 보고서', 4, '6.17'),
  ('document_revision.doc_type', 'INTERNAL_DOC', '사내 문서 (용어집 포함 — GLOSSARY, 6.52)', 5, '6.17'),
  ('document_revision.doc_type', 'PM_RECORD', '예방 정비 실시 기록', 6, '6.17'),
  ('document_revision.doc_type', 'SHIPMENT', '출하 기록 (최종본 추가)', 7, '6.17'),
  ('author_kind', 'AI', 'AI 비서 (AI비서 초안)', 1, '6.18'),
  ('author_kind', 'HUMAN', '사람', 2, '6.18'),
  ('work_record_check.loto_step_code', '6.1', '기기 등의 운전정지 준비', 1, '6.19'),
  ('work_record_check.loto_step_code', '6.2', '기기 등의 운전정지', 2, '6.19'),
  ('work_record_check.loto_step_code', '6.3', '기기 등의 차단', 3, '6.19'),
  ('work_record_check.loto_step_code', '6.4', '잠금장치 또는 표지의 설치', 4, '6.19'),
  ('work_record_check.loto_step_code', '6.5', '저장 또는 축적된 에너지의 관리', 5, '6.19'),
  ('work_record_check.loto_step_code', '6.6', '차단 확인', 6, '6.19'),
  ('work_record_check.loto_step_code', '7.1', '기기 등의 점검', 7, '6.19'),
  ('work_record_check.loto_step_code', '7.2', '작업자 확인', 8, '6.19'),
  ('work_record_check.loto_step_code', '7.3', '잠금장치·표지의 제거', 9, '6.19'),
  ('lockout_level', 'FULL', '§2 전부 (6+3단계 + 설비 차단 지점 전부)', 1, '6.20'),
  ('lockout_level', 'TWO_POINT', '보충용 2점 잠금 (주 차단기 E1 + 공압 주 밸브 P1)', 2, '6.20'),
  ('lockout_level', 'ONE_POINT', '1점 잠금', 3, '6.20'),
  ('lockout_level', 'UNPLUG', '플러그 뽑기 (자물쇠 없음)', 4, '6.20'),
  ('lockout_level', 'NONE', '없음', 5, '6.20'),
  ('isolation_point.energy_type', 'ELEC', '전기', 1, '6.21'),
  ('isolation_point.energy_type', 'ELEC_SUPPLY', '전기 (공급원) — 공급 분전반 차단기', 2, '6.21'),
  ('isolation_point.energy_type', 'AIR', '공압', 3, '6.21'),
  ('pm_task.cycle_code', 'DAILY', '매일', 1, '6.22'),
  ('pm_task.cycle_code', 'WEEKLY', '매주', 2, '6.22'),
  ('pm_task.cycle_code', 'MONTHLY', '매월', 3, '6.22'),
  ('pm_task.cycle_code', 'HALF_YEAR', '6개월', 4, '6.22'),
  ('pm_task.cycle_code', 'YEARLY', '1년', 5, '6.22'),
  ('pm_task.cycle_code', 'AS_REQUIRED', '필요할 때', 6, '6.22'),
  ('pm_task.cycle_code', 'EVERY_8H_USE', '8시간 사용마다', 7, '6.22'),
  ('pm_record.result', 'NORMAL', '정상', 1, '6.23'),
  ('pm_record.result', 'REFILLED', '보충·교체함', 2, '6.23'),
  ('pm_record.result', 'ABNORMAL', '이상 있음 (OP-30은 작업지시서, 다른 공정은 간이 작업기록)', 3, '6.23'),
  ('tool_type.usage_unit', 'HOLES', '구멍 수', 1, '6.24'),
  ('tool_type.usage_unit', 'FEED', '이송 시간 (분)', 2, '6.24'),
  ('tool.tool_role', 'IN_USE', '사용 중', 1, '6.26'),
  ('tool.tool_role', 'SPARE', '예비 (코드만 둠 — 처음 값에는 없음, 2026-10-10)', 2, '6.26'),
  ('tool_change.change_reason', 'LIFE_90', '수명 90% 교체 알림을 보고 교체', 3, '6.26'),
  ('tool_change.change_reason', 'ALARM_362', '알람 362 공구 수명 한계 도달', 4, '6.26'),
  ('tool_change.change_reason', 'ALARM_174', '알람 174 공구 부하가 초과됨', 5, '6.26'),
  ('tool_change.change_reason', 'BROKEN', '파손 ("일부는 일찍 파손")', 6, '6.26'),
  ('tool_change.change_reason', 'OTHER', '기타', 7, '6.26'),
  ('inventory_txn.txn_type', 'IN', '입고', 1, '6.28'),
  ('inventory_txn.txn_type', 'USE', '사용', 2, '6.28'),
  ('inventory_txn.txn_type', 'ADJUST', '조정', 3, '6.28'),
  ('inventory_txn.txn_type', 'FG_IN', '완제품 합격 입고 (최종본)', 4, '6.28'),
  ('inventory_txn.txn_type', 'SHIP_OUT', '출하 출고 (최종본)', 5, '6.28'),
  ('inventory_txn.source_kind', 'RECEIPT', '입고 등록 (공구·소모품)', 6, '6.28'),
  ('inventory_txn.source_kind', 'MATERIAL_RECEIPT', '원자재 입고', 7, '6.28'),
  ('inventory_txn.source_kind', 'LOT_PASS', '로트 합격 (최종본)', 8, '6.28'),
  ('inventory_txn.source_kind', 'SHIPMENT', '출하 (최종본)', 9, '6.28'),
  ('inventory_txn.source_kind', 'WORK_RECORD', '작업기록서', 10, '6.28'),
  ('inventory_txn.source_kind', 'PM_RECORD', '예방 정비', 11, '6.28'),
  ('inventory_txn.source_kind', 'TOOL_CHANGE', '공구 교체', 12, '6.28'),
  ('inventory_txn.source_kind', 'LOT_INPUT', '로트 투입', 13, '6.28'),
  ('inventory_txn.source_kind', 'STOCKTAKE', '월말 실사', 14, '6.28'),
  ('inspection_item.char_class', 'SPECIAL', '특별 특성 ◆', 1, '6.30'),
  ('inspection_item.char_class', 'GENERAL', '일반', 2, '6.30'),
  ('inspection_item.method', 'CMM', '3차원 측정기', 1, '6.31'),
  ('inspection_item.method', 'GAUGE', '나사 통과·정지 게이지', 2, '6.31'),
  ('inspection_item.method', 'VISUAL', '육안', 3, '6.31'),
  ('insp_kind', 'FIRST', '초품', 1, '6.32'),
  ('insp_kind', 'SAMPLE', '발췌', 2, '6.32'),
  ('insp_kind', 'ENHANCED', '강화', 3, '6.32'),
  ('inspection_plan.plan_mode', 'NORMAL', '보통 (발췌)', 4, '6.32'),
  ('inspection_plan.plan_mode', 'ENHANCED', '검사 강화 (전수 + 항목 확대)', 5, '6.32'),
  ('inspection_plan.enhance_reason', 'HOLD_LOT', '보류 로트', 6, '6.32'),
  ('inspection_plan.enhance_reason', 'NEXT_LOT', '보류 다음 로트', 7, '6.32'),
  ('inspection_result.judgement', 'PASS', '합격', 1, '6.33'),
  ('inspection_result.judgement', 'FAIL', '불합격', 2, '6.33'),
  ('inspection_plan.judgement', 'PASS', '합격', 3, '6.33'),
  ('inspection_plan.judgement', 'HOLD_REVIEW', '보류 검토', 4, '6.33'),
  ('defect_code', 'DIM-01', '치수 큼 (상한 넘음)', 1, '6.34'),
  ('defect_code', 'DIM-02', '치수 작음 (하한 밑)', 2, '6.34'),
  ('defect_code', 'DIM-03', '구멍 간 거리 벗어남', 3, '6.34'),
  ('defect_code', 'DIM-04', '평면도 벗어남', 4, '6.34'),
  ('defect_code', 'THR-01', '나사 통과 게이지 안 들어감', 5, '6.34'),
  ('defect_code', 'THR-02', '나사 정지 게이지 2회전 넘게 들어감', 6, '6.34'),
  ('defect_code', 'SUR-01', '버 남음', 7, '6.34'),
  ('defect_code', 'SUR-02', '구성인선 흔적 (뜯긴 면)', 8, '6.34'),
  ('defect_code', 'SUR-03', '찍힘·긁힘', 9, '6.34'),
  ('defect_code', 'MAT-01', '원자재 성적서 불일치', 10, '6.34'),
  ('defect_code.grade', 'CRITICAL', '치명결함', 11, '6.34'),
  ('defect_code.grade', 'MAJOR', '중결함', 12, '6.34'),
  ('defect_code.grade', 'MINOR', '경결함', 13, '6.34'),
  ('importance', 'URGENT', '긴급', 1, '6.35'),
  ('importance', 'CAUTION', '주의', 2, '6.35'),
  ('importance', 'INFO', '참고', 3, '6.35'),
  ('notification_rule.rule_code', 'ALARM_STOP', '알람 발생 (정지)', 1, '6.36'),
  ('notification_rule.rule_code', 'ALARM_WARN', '알람 발생 (주의)', 2, '6.36'),
  ('notification_rule.rule_code', 'ALARM_GUIDE', '알람 발생 (조작 안내)', 3, '6.36'),
  ('notification_rule.rule_code', 'REPEAT_ALARM', '반복 알람 (1단계)', 4, '6.36'),
  ('notification_rule.rule_code', 'REPEAT_ALARM_2', '반복 알람 2단계 "지난 조치 효과 없음" (최종본)', 5, '6.36'),
  ('notification_rule.rule_code', 'CAUSE_CHECK_REQUEST', '원인 점검 요청 (다른 공정, 최종본)', 6, '6.36'),
  ('notification_rule.rule_code', 'TARGET_RISK', '목표 미달 위험', 7, '6.36'),
  ('notification_rule.rule_code', 'BOTTLENECK_MOVE', '병목 발생·이동', 8, '6.36'),
  ('notification_rule.rule_code', 'WIP_WARN', '재공 경고', 9, '6.36'),
  ('notification_rule.rule_code', 'LOT_DUE_RISK', '로트 납기 지연 위험', 10, '6.36'),
  ('notification_rule.rule_code', 'STOCK_LOW', '재고 부족', 11, '6.36'),
  ('notification_rule.rule_code', 'PM_DUE_SOON', '예방 정비 기한 하루 전', 12, '6.36'),
  ('notification_rule.rule_code', 'PM_OVERDUE', '예방 정비 기한 넘김', 13, '6.36'),
  ('notification_rule.rule_code', 'TOOL_LIFE_90', '공구 수명', 14, '6.36'),
  ('notification_rule.rule_code', 'APPROVAL_WAIT_30M', '승인 대기', 15, '6.36'),
  ('notification_rule.rule_code', 'APPROVAL_WAIT_2H', '승인 대기', 16, '6.36'),
  ('notification_rule.rule_code', 'WO_ASSIGNED', '작업지시서 배정 (2026-10-13)', 17, '6.36'),
  ('notification_rule.rule_code', 'WO_DRAFT_READY', '작업지시서 초안 검토 (2026-10-13)', 18, '6.36'),
  ('notification_rule.rule_code', 'DAILY_REPORT_PENDING', '일일 보고서 확정 요청 (2026-10-13)', 19, '6.36'),
  ('notification_rule.rule_code', 'DOC_REVISED', '문서 수정', 20, '6.36'),
  ('notification_rule.rule_code', 'SPC_OUT', '관리도 이상', 21, '6.36'),
  ('notification_rule.rule_code', 'SHIFT_REPORT_PENDING', '교대 보고서 확정 요청', 22, '6.36'),
  ('notification_rule.rule_code', 'CMM_FILE_ERROR', 'CMM 결과 파일 오류 (최종본)', 23, '6.36'),
  ('notification_rule.rule_code', 'CMM_JUDGE_MISMATCH', 'CMM 판정 불일치 (최종본)', 24, '6.36'),
  ('notification_rule.rule_code', 'CMM_NO_RESULT', 'CMM 결과 미수신 (최종본)', 25, '6.36'),
  ('role.role_code', 'OPR', '현장 작업자', 1, '6.37'),
  ('role.role_code', 'MNT', '보전 담당자', 2, '6.37'),
  ('role.role_code', 'SUP', '라인 반장', 3, '6.37'),
  ('role.role_code', 'MGR', '공장 관리자', 4, '6.37'),
  ('alarm_event.scenario_code', 'S1', '충돌 의심 (메인, 고장) — VF2-01 108 → 994 → 992, 의심 로트(예시 LOT-2609-041-1) 보류', 1, '6.40'),
  ('alarm_event.scenario_code', 'S2', '축 윤활 부족 — 2075 반복 (과거 기록, 사건 버튼 없음)', 2, '6.40'),
  ('alarm_event.scenario_code', 'S3', '공구 수명 — T05 사용률 90% 교체 알림 → (교체 안 하면) 362', 3, '6.40'),
  ('alarm_event.scenario_code', 'S4', '공기 압력 저하 — 120', 4, '6.40'),
  ('alarm_event.scenario_code', 'S5', '조작 오류 — 314. 사건 버튼 없음 (2026-10-13): 10/1 알람에는 쓰이지 않고, 314는 9월 과거 기록(scenario_code 비움)으로만 있음', 5, '6.40'),
  ('alarm_event.scenario_code', 'S6', '병목 (고장 아님) — VF2-02 예방 정비 90분', 6, '6.40'),
  ('source_tag', 'REAL', '', 1, '6.41'),
  ('source_tag', 'REFERENCE', '', 2, '6.41'),
  ('source_tag', 'VIRTUAL', '', 3, '6.41'),
  ('maintenance_work_order.trigger_kind', 'STOP_ALARM', '정지 등급 알람', 1, '6.42'),
  ('maintenance_work_order.trigger_kind', 'REPEAT_STAGE2', '반복 알람 2단계 (원인 점검)', 2, '6.42'),
  ('maintenance_work_order.trigger_kind', 'PM_ABNORMAL', '예방 정비 중 이상', 3, '6.42'),
  ('notification.report_rank', 'R0', '안전', 1, '6.43'),
  ('notification.report_rank', 'R0_1', '오래 방치', 2, '6.43'),
  ('notification.report_rank', 'R1', '긴급 (정지)', 3, '6.43'),
  ('notification.report_rank', 'R2', '생산 위험', 4, '6.43'),
  ('notification.report_rank', 'R3', '주의', 5, '6.43'),
  ('notification.report_rank', 'R4', '참고', 6, '6.43'),
  ('shipment.status', 'DRAFT', '작성 중', 1, '6.44'),
  ('shipment.status', 'CONFIRMED', '확정', 2, '6.44'),
  ('shipment.status', 'REVISED', '확정 후 수정', 3, '6.44'),
  ('shipment.customer_code', 'CUST-01', '가상 고객사 (1곳). 실제 회사 이름은 쓰지 않는다', 1, '6.45'),
  ('inspection_result.input_method', 'CMM_AUTO', 'CMM 자동 (결과 파일)', 1, '6.46'),
  ('inspection_result.input_method', 'TABLET', '태블릿 버튼 (사람)', 2, '6.46'),
  ('inspection_result.input_method', 'MANUAL', '수동 입력', 3, '6.46'),
  ('inspection_result.check_status', 'NORMAL', '정상', 1, '6.47'),
  ('inspection_result.check_status', 'NEEDS_CHECK', '확인 필요', 2, '6.47'),
  ('inspection_result.check_status', 'CHECKED', '반장 확인', 3, '6.47'),
  ('cmm_import.status', 'SUCCESS', '성공', 1, '6.48'),
  ('cmm_import.status', 'FAILED', '실패', 2, '6.48'),
  ('cmm_import.status', 'NEEDS_CHECK', '확인 필요', 3, '6.48'),
  ('cmm_import.error_kind', 'FORMAT', '양식 오류', 4, '6.48'),
  ('cmm_import.error_kind', 'LOT_MISMATCH', '지시와 다름', 5, '6.48'),
  ('cmm_import.error_kind', 'INCOMPLETE', '불완전', 6, '6.48'),
  ('layout_object.object_kind', 'MATERIAL_RACK', '봉재 랙', 1, '6.49'),
  ('layout_object.object_kind', 'INFEED', '투입 대', 2, '6.49'),
  ('layout_object.object_kind', 'WIP_SPOT', '재공 자리', 3, '6.49'),
  ('layout_object.object_kind', 'SOAK_SHELF', '온도 맞춤 선반', 4, '6.49'),
  ('layout_object.object_kind', 'FG_SPOT', '완성품 자리', 5, '6.49'),
  ('layout_object.object_kind', 'AISLE', '통로', 6, '6.49'),
  ('layout_object.object_kind', 'DOOR', '반입문', 7, '6.49'),
  ('layout_object.object_kind', 'EXIT', '비상구', 8, '6.49'),
  ('equipment_part_shape.shape_kind', 'BOX', '상자', 1, '6.50'),
  ('equipment_part_shape.shape_kind', 'CYLINDER', '원기둥', 2, '6.50'),
  ('equipment.facing', 'NEG_Y', '−Y (남쪽, 주 통로 쪽) — SAW-01 말고 5대', 1, '6.51'),
  ('equipment.facing', 'POS_Y', '+Y (북쪽)', 2, '6.51'),
  ('equipment.facing', 'NEG_X', '−X (서쪽)', 3, '6.51'),
  ('equipment.facing', 'POS_X', '+X (동쪽) — SAW-01 (재료가 뒤 → 앞으로 흐름, 2026-10-10)', 4, '6.51'),
  ('internal_doc.doc_kind', 'MANUAL_DOC', '사내 문서', 1, '6.52'),
  ('internal_doc.doc_kind', 'GLOSSARY', '용어집', 2, '6.52'),
  ('retention_stage', 'L1', '세밀 시계열', 1, '6.53'),
  ('retention_stage', 'L2', '시계열', 2, '6.53'),
  ('retention_stage', 'L3', '사건·운영 기록', 3, '6.53'),
  ('retention_stage', 'L4', '품질·추적·확정 문서', 4, '6.53'),
  ('retention_stage', 'ACCESS_LOG', '특별: 접속 기록', 5, '6.53'),
  ('retention_stage', 'USER', '특별: 사용자 계정', 6, '6.53'),
  ('retention_stage', 'MASTER', '기준 정보', 7, '6.53'),
  ('notification.repeat_stage_status', 'S1_OPEN', '1단계 열림', 1, '6.54'),
  ('notification.repeat_stage_status', 'S1_CLOSED', '1단계 닫힘', 2, '6.54'),
  ('notification.repeat_stage_status', 'S2_OPEN', '2단계 열림', 3, '6.54'),
  ('notification.repeat_stage_status', 'S2_CHECKED', '원인 점검 확정', 4, '6.54'),
  ('notification.repeat_stage_status', 'EFFECTIVE', '효과 확인', 5, '6.54'),
  ('notification.repeat_stage_status', 'ESCALATED', '다음 단계로 넘어감', 6, '6.54')
ON CONFLICT (code_group, code) DO UPDATE SET name_ko = EXCLUDED.name_ko, sort_order = EXCLUDED.sort_order,
    source_ref = EXCLUDED.source_ref;

-- ===================== db/seed/11_code_labels_physical.sql =====================
-- 물리 설계에서 정한 코드 [제안] (논리 ERD 6장에 영어 코드가 없던 칸)
INSERT INTO code_label (code_group, code, name_ko, sort_order, source_ref) VALUES
    ('inspection_result.position', 'TOP', '위', 1, '5.F.4'),
  ('inspection_result.position', 'MID', '중간', 2, '5.F.4'),
  ('inspection_result.position', 'BOTTOM', '아래', 3, '5.F.4'),
  ('lot_hold.result', 'IN_PROGRESS', '진행 중', 1, '5.B.7'),
  ('lot_hold.result', 'RELEASED', '해제', 2, '5.B.7'),
  ('lot_hold.result', 'SCRAPPED', '폐기', 3, '5.B.7'),
  ('pm_record.status', 'DRAFT', '작성 중', 1, '5.D.8'),
  ('pm_record.status', 'CONFIRMED', '확정', 2, '5.D.8'),
  ('internal_doc.status', 'PENDING', '승인 대기', 1, '5.G.5'),
  ('internal_doc.status', 'APPROVED', '승인', 2, '5.G.5'),
  ('notification.message_source', 'ASSISTANT', '비서 문장', 1, '5.H.5'),
  ('notification.message_source', 'DEFAULT', '기본 문구', 2, '5.H.5'),
  ('notification.process_kind', 'AUTO', '자동', 1, '5.H.5'),
  ('notification.process_kind', 'MANUAL', '사람', 2, '5.H.5'),
  ('role_permission.scope', 'ALL', '전체', 1, '5.H.3'),
  ('role_permission.scope', 'OWN', '자기 문서만', 2, '5.H.3'),
  ('role_permission.scope', 'SUMMARY', '요약만', 3, '5.H.3'),
  ('role_permission.scope', 'PROXY', '대리', 4, '5.H.3'),
  ('role_permission.scope', 'OWNED_ITEMS', '관리 품목만', 5, '5.H.3'),
  ('inventory_item.category', 'TOOL', '공구', 1, '6.27'),
  ('inventory_item.category', 'CONSUMABLE', '소모품', 2, '6.27'),
  ('inventory_item.category', 'MATERIAL', '원자재', 3, '6.27'),
  ('inventory_item.category', 'FINISHED', '완제품', 4, '6.27'),
  ('downtime_reason.reason_group', 'FAILURE', '고장', 1, '6.5'),
  ('downtime_reason.reason_group', 'MATERIALS', '자재·흐름', 2, '6.5'),
  ('downtime_reason.reason_group', 'SETUP', '준비', 3, '6.5'),
  ('downtime_reason.reason_group', 'OPERATION', '조작', 4, '6.5'),
  ('downtime_reason.reason_group', 'PLANNED', '계획', 5, '6.5'),
  ('defect_record.disposition', 'SCRAP', '폐기', 1, '5.F.5'),
  ('defect_record.disposition', 'REWORK', '재작업', 2, '5.F.5'),
  ('work_record_check.check_kind', 'STEP', '작업 순서', 1, '5.D.5'),
  ('work_record_check.check_kind', 'LOTO', '잠금·표지', 2, '5.D.5'),
  ('wip_log.interval_type', 'MIN5', '5분', 1, '5.B.5'),
  ('wip_log.interval_type', 'MIN1', '1분 (사건 앞뒤 30분)', 2, '5.B.5'),
  ('sensor_sample.interval_type', 'MIN1_AVG', '1분 평균', 1, '5.C.7'),
  ('sensor_sample.interval_type', 'SEC5', '5초 (주의·정지 알람·OP-30 병목 앞뒤 30분)', 2, '5.C.7'),
  ('cmm_instruction.status', 'ISSUED', '지시함', 1, '물리 추가'),
  ('cmm_instruction.status', 'STARTED', '측정 시작', 2, '물리 추가'),
  ('cmm_instruction.status', 'DONE', '결과 받음', 3, '물리 추가'),
  ('cmm_instruction.status', 'CANCELLED', '취소', 4, '물리 추가'),
  ('notification_rule.process_mode', 'AUTO', '기록이 생기면 자동 처리', 1, '6.36'),
  ('notification_rule.process_mode', 'MANUAL', '사람이 처리', 2, '6.36'),
  ('notification_rule.process_mode', 'BOTH', '자동 또는 사람', 3, '6.36')
ON CONFLICT (code_group, code) DO UPDATE SET name_ko = EXCLUDED.name_ko, sort_order = EXCLUDED.sort_order;

-- ===================== db/seed/20_roles_permissions.sql =====================
-- =====================================================================
-- 역할 (6.37)과 역할별 권한 (기획서 13.1 문서별·13.2 기능별 → role_permission)
-- target 이름 [제안]. 서버(app/security.py require())가 이 표로 막는다 (NFR-SEC-05).
-- MGR은 모든 기능·문서 조회 (R-76) — 맨 아래에서 VIEW를 한꺼번에 넣는다.
-- =====================================================================
INSERT INTO role (role_code, role_name) VALUES
  ('OPR', '현장 작업자'), ('MNT', '보전 담당자'), ('SUP', '라인 반장'), ('MGR', '공장 관리자')
ON CONFLICT (role_code) DO UPDATE SET role_name = EXCLUDED.role_name;

DELETE FROM role_permission;
INSERT INTO role_permission (role_code, target, action, scope) VALUES
-- ---- 13.1 문서별 ----
  ('OPR','GUIDE_CARD','VIEW','ALL'), ('MNT','GUIDE_CARD','VIEW','ALL'), ('SUP','GUIDE_CARD','VIEW','ALL'),
  ('OPR','WORK_ORDER','VIEW','ALL'),
  ('MNT','WORK_ORDER','VIEW','ALL'), ('MNT','WORK_ORDER','CREATE','ALL'), ('MNT','WORK_ORDER','EDIT','ALL'),
  ('SUP','WORK_ORDER','VIEW','ALL'), ('SUP','WORK_ORDER','ASSIGN','ALL'), ('SUP','WORK_ORDER','APPROVE','ALL'),
  ('MGR','WORK_ORDER','APPROVE','PROXY'), ('MGR','WORK_ORDER','CANCEL','ALL'),
  -- 작업기록서 (정식)
  ('MNT','WORK_RECORD','VIEW','ALL'), ('MNT','WORK_RECORD','CREATE','ALL'), ('MNT','WORK_RECORD','EDIT','ALL'),
  ('MNT','WORK_RECORD','CONFIRM','ALL'),
  ('SUP','WORK_RECORD','VIEW','ALL'), ('SUP','WORK_RECORD','CHECK','ALL'),
  -- 간이 작업기록: OPR은 주의 등급만 확정 (다른 공정 정지 등급·원인 점검은 MNT — DB 트리거가 다시 확인)
  ('OPR','WORK_RECORD_SIMPLE','VIEW','ALL'), ('OPR','WORK_RECORD_SIMPLE','CREATE','ALL'),
  ('OPR','WORK_RECORD_SIMPLE','EDIT','ALL'), ('OPR','WORK_RECORD_SIMPLE','CONFIRM','ALL'),
  ('MNT','WORK_RECORD_SIMPLE','VIEW','ALL'), ('MNT','WORK_RECORD_SIMPLE','CREATE','ALL'),
  ('MNT','WORK_RECORD_SIMPLE','EDIT','ALL'), ('MNT','WORK_RECORD_SIMPLE','CONFIRM','ALL'),
  ('SUP','WORK_RECORD_SIMPLE','VIEW','ALL'),
  -- 예방 정비 실시 기록 (OPR 없음 — 13.1 "—", 작업자가 한 항목은 MNT가 실시자로 골라 기록)
  ('MNT','PM_RECORD','VIEW','ALL'), ('MNT','PM_RECORD','CREATE','ALL'), ('MNT','PM_RECORD','EDIT','ALL'),
  ('MNT','PM_RECORD','CONFIRM','ALL'),
  ('SUP','PM_RECORD','VIEW','ALL'),
  -- 교대 보고서
  ('OPR','SHIFT_REPORT','VIEW','ALL'), ('MNT','SHIFT_REPORT','VIEW','ALL'),
  ('SUP','SHIFT_REPORT','VIEW','ALL'), ('SUP','SHIFT_REPORT','EDIT','ALL'), ('SUP','SHIFT_REPORT','CONFIRM','ALL'),
  -- 일일 보고서 (OPR 없음)
  ('MNT','DAILY_REPORT','VIEW','ALL'), ('SUP','DAILY_REPORT','VIEW','ALL'),
  ('MGR','DAILY_REPORT','EDIT','ALL'), ('MGR','DAILY_REPORT','CONFIRM','ALL'),
  -- 출하 기록
  ('OPR','SHIPMENT','VIEW','ALL'), ('MNT','SHIPMENT','VIEW','ALL'),
  ('SUP','SHIPMENT','VIEW','ALL'), ('SUP','SHIPMENT','CREATE','ALL'), ('SUP','SHIPMENT','EDIT','ALL'),
  ('SUP','SHIPMENT','CONFIRM','ALL'),
  -- 사내 문서 세트
  ('OPR','INTERNAL_DOC','VIEW','ALL'), ('MNT','INTERNAL_DOC','VIEW','ALL'), ('SUP','INTERNAL_DOC','VIEW','ALL'),
  ('MGR','INTERNAL_DOC','APPROVE','ALL'),
  -- 수정 이력 (OPR은 자기 문서만)
  ('OPR','REVISION_HISTORY','VIEW','OWN'), ('MNT','REVISION_HISTORY','VIEW','ALL'), ('SUP','REVISION_HISTORY','VIEW','ALL'),
-- ---- 13.2 기능별 ----
  ('OPR','FIELD_VIEW','VIEW','ALL'), ('MNT','FIELD_VIEW','VIEW','ALL'), ('SUP','FIELD_VIEW','VIEW','ALL'),
  ('OPR','LINE_VIEW','VIEW','ALL'), ('MNT','LINE_VIEW','VIEW','ALL'), ('SUP','LINE_VIEW','VIEW','ALL'),
  ('OPR','ASSISTANT','INPUT','ALL'), ('MNT','ASSISTANT','INPUT','ALL'), ('SUP','ASSISTANT','INPUT','ALL'),
  ('MGR','ASSISTANT','INPUT','ALL'),
  ('OPR','BRIEFING','VIEW','SUMMARY'), ('MNT','BRIEFING','VIEW','ALL'), ('SUP','BRIEFING','VIEW','ALL'),
  ('OPR','NOTIFICATION','VIEW','ALL'), ('MNT','NOTIFICATION','VIEW','ALL'), ('SUP','NOTIFICATION','VIEW','ALL'),
  ('OPR','DOWNTIME_REASON','VIEW','ALL'), ('OPR','DOWNTIME_REASON','INPUT','ALL'),
  ('MNT','DOWNTIME_REASON','VIEW','ALL'), ('MNT','DOWNTIME_REASON','INPUT','ALL'),
  ('SUP','DOWNTIME_REASON','VIEW','ALL'), ('SUP','DOWNTIME_REASON','CONFIRM','ALL'),
  ('SUP','LOT_TRACE','VIEW','ALL'), ('OPR','LOT_TRACE','VIEW','ALL'), ('MNT','LOT_TRACE','VIEW','ALL'),
  ('SUP','LOT_HOLD','INPUT','ALL'), ('MGR','LOT_HOLD','INPUT','ALL'),
  ('SUP','LOT_SCRAP','CREATE','ALL'), ('MGR','LOT_SCRAP','APPROVE','ALL'),
  ('OPR','INVENTORY','VIEW','ALL'), ('MNT','INVENTORY','VIEW','ALL'), ('SUP','INVENTORY','VIEW','ALL'),
  ('OPR','INV_USE','INPUT','OWNED_ITEMS'), ('MNT','INV_USE','INPUT','ALL'),
  ('MNT','INV_RECEIPT','INPUT','OWNED_ITEMS'), ('SUP','INV_RECEIPT','INPUT','OWNED_ITEMS'),
  ('SUP','MATERIAL_CHECK','INPUT','ALL'),
  ('MGR','SAFETY_STOCK','SETTING','ALL'),
  ('OPR','TOOL_CHANGE','INPUT','ALL'), ('MNT','TOOL_CHANGE','INPUT','ALL'),
  ('OPR','TOOL_LIFE','VIEW','ALL'), ('MNT','TOOL_LIFE','VIEW','ALL'), ('SUP','TOOL_LIFE','VIEW','ALL'),
  -- 예방 정비 일정은 전원 조회 (API명세서 PM-01 "전" — 현장 보기의 기한 넘김 표시)
  ('OPR','PM_SCHEDULE','VIEW','ALL'), ('MNT','PM_SCHEDULE','VIEW','ALL'), ('SUP','PM_SCHEDULE','VIEW','ALL'),
  -- 품질 조회는 전원 (API명세서 QLT-01·04·05 "전"). 입력은 측정 담당 작업자(OP-50 — 처리기가 담당 공정 확인)와 반장
  ('SUP','QUALITY','VIEW','ALL'), ('SUP','QUALITY','CHECK','ALL'), ('OPR','QUALITY','VIEW','ALL'),
  ('OPR','QUALITY','INPUT','ALL'), ('MNT','QUALITY','VIEW','ALL'),
  ('SUP','KPI','VIEW','ALL'), ('MNT','KPI','VIEW','ALL'), ('OPR','KPI','VIEW','ALL'),
  ('MGR','SETTINGS','SETTING','ALL'),
  ('SUP','PRODUCTION','VIEW','ALL'), ('SUP','PRODUCTION','INPUT','ALL'), ('OPR','PRODUCTION','VIEW','ALL'),
  ('OPR','PRODUCTION','INPUT','ALL'), ('MNT','PRODUCTION','VIEW','ALL');

-- R-76 MGR은 모든 기능·문서 조회
INSERT INTO role_permission (role_code, target, action, scope)
SELECT DISTINCT 'MGR', target, 'VIEW', 'ALL' FROM role_permission
ON CONFLICT DO NOTHING;

-- ===================== db/seed/30_notification_rules.sql =====================
-- =====================================================================
-- 알림 규칙 처음 값 25행 (논리 ERD 6.36, 2026-10-13: WO_ASSIGNED·WO_DRAFT_READY·DAILY_REPORT_PENDING 추가)
--   규칙 코드·이름·조건·중요도·전달 방식 = 생성기 masters/notification_rule.csv 와 같은 글 (생성기 적재 때 그대로 덮어씀)
--   + 처리 방법(6.36 처리 표) + 받는 역할 + 보고 순위(6.43) — 물리 추가 칸
-- 기준 숫자는 DOC-07 10장 값만 (condition_text). 바꾸는 사람은 MGR (설정 화면)
-- 전달 방식 (2026-10-13): POPUP = ALARM_STOP 긴급 팝업 (받는 사람 = 로그인한 전원, 처리 책임은 그 설비 OPR·MNT) /
--   BUBBLE = 문서 알림 6종 (이브 말풍선) / LIST = 나머지 (이브 아이콘 숫자·사이드바 알림 탭)
-- rank_group: 같은 순위 안 묶음 순서 (6.43 순위 3의 ①~⑤ = 10~50, 순위 2 = 목표 미달 10·병목 20·납기 30)
-- =====================================================================
INSERT INTO notification_rule (rule_code, rule_name, condition_text, importance, delivery_kind, process_mode, processor_roles,
                               recipient_roles, report_rank, rank_group) VALUES
  ('ALARM_STOP', '알람 발생 (정지)', '정지 등급 알람 발생 → 로그인한 전원에게 중앙 팝업 (처리 책임은 그 설비 OPR·MNT)', 'URGENT', 'POPUP', 'AUTO', '{}', '{OPR,MNT,SUP,MGR}', 'R1', 0),
  ('ALARM_WARN', '알람 발생 (주의)', '주의 등급 알람 발생', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,MNT}', 'R3', 20),
  ('ALARM_GUIDE', '알람 발생 (조작 안내)', '조작 안내 등급 알람 발생', 'INFO', 'LIST', 'MANUAL', '{OPR,SUP}', '{OPR}', 'R4', 0),
  ('REPEAT_ALARM', '반복 알람 (1단계)', '같은 설비·같은 알람(주의·정지 등급)이 7일 안에 3번 이상 → MNT·SUP', 'CAUTION', 'LIST', 'MANUAL', '{MNT,SUP}', '{MNT,SUP}', 'R3', 11),
  ('REPEAT_ALARM_2', '반복 알람 2단계 (지난 조치 효과 없음)', '1단계 조치 계획을 저장한 뒤 7일 안에 같은 설비·같은 알람이 다시 남 → MNT·SUP', 'CAUTION', 'LIST', 'AUTO', '{}', '{MNT,SUP}', 'R3', 10),
  ('CAUSE_CHECK_REQUEST', '원인 점검 요청 (다른 공정)', '다른 공정의 반복 알람 2단계 → MNT에게 원인 점검 요청', 'CAUTION', 'LIST', 'AUTO', '{}', '{MNT}', 'R3', 10),
  ('TARGET_RISK', '목표 미달 위험', '예측 실적 < 총 목표(목표 + 이월)의 90%. 교대 시작 1시간 뒤부터 판단, 교대에 처음 1번', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 10),
  ('BOTTLENECK_MOVE', '병목 발생·이동', '병목 공정(또는 원인)이 바뀜. 관련 정보 = DOC-07 §7.5의 해당 원인 조치 줄', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 20),
  ('WIP_WARN', '재공 경고', '공정 사이 재공이 경고 기준(wip_buffer.warn_over_qty) 초과 — 20개, WIP-20-30은 한도 30 도달(OP-20 막힘). WIP-30-40 제외. 재공 위치마다 교대에 처음 1번', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 20),
  ('LOT_DUE_RISK', '로트 납기 지연 위험', '로트 예상 완료 시각 > 납기', 'CAUTION', 'LIST', 'MANUAL', '{SUP}', '{SUP}', 'R2', 30),
  ('STOCK_LOW', '재고 부족', '재고 수량 ≤ 안전 재고 → 그 품목의 관리 역할 + MGR', 'CAUTION', 'LIST', 'BOTH', '{MGR}', '{MGR}', 'R3', 40),
  ('PM_DUE_SOON', '예방 정비 기한 하루 전', '기한 하루 전 (주 1회 이상 주기 항목만 — 매일·교대 점검은 점검표)', 'INFO', 'LIST', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('PM_OVERDUE', '예방 정비 기한 넘김', '기한 넘김 (주 1회 이상 주기 항목만)', 'CAUTION', 'LIST', 'AUTO', '{}', '{MNT}', 'R3', 40),
  ('TOOL_LIFE_90', '공구 수명', '사용률 90%', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,MNT}', 'R3', 40),
  ('APPROVAL_WAIT_30M', '승인 대기', '작업지시서 승인 대기 30분 이상', 'INFO', 'BUBBLE', 'AUTO', '{}', '{SUP}', 'R4', 0),
  ('APPROVAL_WAIT_2H', '승인 대기', '작업지시서 승인 대기 2시간 이상', 'CAUTION', 'BUBBLE', 'AUTO', '{}', '{SUP}', 'R3', 50),
  ('WO_ASSIGNED', '작업지시서 배정', '작업지시서가 승인됨 → 담당 MNT', 'INFO', 'BUBBLE', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('WO_DRAFT_READY', '작업지시서 초안 검토', '작업지시서 AI비서 초안이 생길 때 → 그 설비 MNT', 'INFO', 'BUBBLE', 'AUTO', '{}', '{MNT}', 'R4', 0),
  ('DAILY_REPORT_PENDING', '일일 보고서 확정 요청', '일일 보고서 AI비서 초안이 생길 때 (야간 교대 보고서 확정 즉시, 늦어도 06:00) → MGR', 'INFO', 'BUBBLE', 'AUTO', '{}', '{MGR}', 'R4', 0),
  ('DOC_REVISED', '문서 수정', '작업지시서 수정 → 담당 보전원, 보고서 수정 → 관리자, 사내 문서 개정 → 관련 역할 전체', 'INFO', 'BUBBLE', 'AUTO', '{}', '{}', 'R4', 0),
  ('SPC_OUT', '관리도 이상', '점 1개가 +3σ 위 또는 −3σ 아래 → 반장', 'CAUTION', 'LIST', 'AUTO', '{}', '{SUP}', 'R3', 30),
  ('SHIFT_REPORT_PENDING', '교대 보고서 확정 요청', '교대 끝(주간 17:00, 야간 05:00) 교대 보고서 AI비서 초안이 생길 때 → 그 교대 반장', 'INFO', 'BUBBLE', 'AUTO', '{}', '{}', 'R4', 0),
  ('CMM_FILE_ERROR', 'CMM 결과 파일 오류', '결과 파일을 읽지 못함 또는 확인 필요 → 작업자·반장', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,SUP}', 'R3', 30),
  ('CMM_JUDGE_MISMATCH', 'CMM 판정 불일치', '측정기 판정 ≠ 플랫폼 판정 → 반장', 'CAUTION', 'LIST', 'AUTO', '{}', '{SUP}', 'R3', 30),
  ('CMM_NO_RESULT', 'CMM 결과 미수신', '측정 시작 뒤 정한 시간 안에 결과 파일이 오지 않음 → 작업자·반장 (시간은 [선택 필요: 기술 회의])', 'CAUTION', 'LIST', 'AUTO', '{}', '{OPR,SUP}', 'R3', 30)
ON CONFLICT (rule_code) DO UPDATE SET rule_name = EXCLUDED.rule_name, condition_text = EXCLUDED.condition_text,
    importance = EXCLUDED.importance, delivery_kind = EXCLUDED.delivery_kind, process_mode = EXCLUDED.process_mode,
    processor_roles = EXCLUDED.processor_roles, recipient_roles = EXCLUDED.recipient_roles, report_rank = EXCLUDED.report_rank,
    rank_group = EXCLUDED.rank_group;


-- ===================== db/seed/40_alarm_related_items.sql =====================
-- 알람 관련 재고 품목 (논리 ERD 5.C.8, R-89). 알람 코드집·재고 품목이 아직 없으면 0줄 — 목업·생성기 적재 뒤 다시 부른다
SELECT fn_seed_alarm_related_items() AS alarm_related_items;
