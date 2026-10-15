-- 업무 번호·시연 시계
BEGIN;
-- 목업 데이터에 PO-2609-041까지 있으므로 다음은 042 (fn_sync_doc_numbers)
SELECT t.eq(fn_next_doc_no('PO', '2026-09-15 12:00+09'), 'PO-2609-042', '적재 뒤 다음 작업지시 번호');
SELECT t.eq(fn_next_doc_no('PO', '2026-09-15 12:01+09'), 'PO-2609-043', '번호는 하나씩 오른다');
SELECT t.eq(fn_next_doc_no('MW', '2026-09-30 23:59+09'), 'MW-0902', '작업지시서 번호 (9월)');
SELECT t.eq(fn_next_doc_no('MW', '2026-10-01 00:01+09'), 'MW-1001', '달이 바뀌면 01부터 (한국 시간)');
SELECT t.eq(fn_next_doc_no('MR-S', '2026-09-15 12:00+09'), 'MR-S-0901', '간이 작업기록 번호');
SELECT t.eq(fn_next_doc_no('SHP', '2026-09-15 14:00+09'), 'SHP-2609-001', '출하 번호');
-- 만든 번호가 테이블 형식 제약을 통과하는지
SELECT t.ok('MR-S-0901' ~ '^MR-S-[0-9]{4,5}$', '간이 번호가 work_record 형식과 맞음 (MR-S-0901, 설계서 5.11)');

-- 시연 시계: 다음 날 06:00으로 건너뛰기 (멈춤)
SELECT t.freeze('2026-09-16 06:00+09');
SELECT t.eq(app_now(), '2026-09-16 06:00+09'::timestamptz, '시연 시계 건너뛰기');
-- 60배속으로 진행 (트랜잭션 안에서는 now()가 같아서 시작점과 같다)
SELECT fn_sim_set('SIM', '2026-09-15 08:00+09', 60, false);
SELECT t.eq(app_now(), '2026-09-15 08:00+09'::timestamptz, '배속 진행 시작점');
SELECT fn_sim_set('REAL');
SELECT t.ok(abs(extract(epoch FROM app_now() - now())) < 1, '실제 시계 모드');
ROLLBACK;
