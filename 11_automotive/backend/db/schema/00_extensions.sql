-- =====================================================================
-- 00_extensions.sql — 확장 기능
-- PostgreSQL 16 기준. 공식 postgres:16 이미지에 들어 있는 contrib만 쓴다.
-- =====================================================================

-- 설비 상태 구간 겹침 금지(R-04)를 EXCLUDE 제약으로 지키려면
-- 문자열(equipment_id) 같음(=)과 시각 범위 겹침(&&)을 한 GiST 인덱스에 섞어야 한다.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 문서 검색용 벡터(pgvector)는 임베딩 모델과 차원이 정해진 뒤 따로 넣는다.
--   → db/later/doc_chunk_embedding.sql  [선택 필요: 기술 회의]
