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
