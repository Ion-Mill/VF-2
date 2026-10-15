-- =====================================================================
-- [선택 필요: 기술 회의] 사내 문서 검색(RAG)용 벡터 — 임베딩 모델과 차원이 정해지면 적용한다.
-- apply.sh 가 부르지 않는다. 정해진 뒤: psql -v dim=1024 -f db/later/doc_chunk_embedding.sql
--   · 확장: pgvector (postgres 이미지에 없으면 pgvector/pgvector:pg16 이미지를 쓴다)
--   · 문서가 새 Rev로 승인되면 그 문서의 조각을 다시 만든다 (doc_rev가 다르면 검색에서 뺌)
--   · 검색 결과에는 사내 문서 번호·절만 보이고 원문 출처(source_ref)는 내보내지 않는다 (R-85)
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS embedding vector(:dim);
ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS embedding_model varchar(60);

-- 코사인 거리 HNSW 색인 (조각이 수천 개 수준이면 색인 없이도 충분 — 측정 뒤 결정)
CREATE INDEX IF NOT EXISTS ix_doc_chunk_embedding ON doc_chunk USING hnsw (embedding vector_cosine_ops);

-- 지금 Rev 조각만 검색 (승인된 문서의 current_rev)
CREATE OR REPLACE VIEW v_doc_chunk_current AS
SELECT c.chunk_id, c.doc_no, d.doc_name, c.doc_rev, c.section, c.chunk_text, c.embedding
  FROM doc_chunk c JOIN internal_doc d ON d.doc_no = c.doc_no AND d.current_rev = c.doc_rev
 WHERE d.is_search_target AND d.status = 'APPROVED';

-- 사용 예 (app/sql 에 넣을 때): SELECT doc_no, section, chunk_text FROM v_doc_chunk_current
--   ORDER BY embedding <=> CAST(:query_vec AS vector) LIMIT 5;
