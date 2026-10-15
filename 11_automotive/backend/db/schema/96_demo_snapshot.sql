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
