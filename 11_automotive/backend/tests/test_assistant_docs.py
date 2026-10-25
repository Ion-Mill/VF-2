"""비서가 시작할 때 읽는 사내 문서 API — GET /api/assistant/docs (2026-10-25, 비서 DOCS_SOURCE=db).
읽기만 하는지(쓰기 SQL 없음·읽기 전용 연결·서비스 키 전용)를 코드로 확인한다. 진짜 DB는 쓰지 않는다."""
import inspect
import re
import unittest

from tests.stubs_loader import use_stubs_if_needed

use_stubs_if_needed()

from app.routers import assistant as R  # noqa: E402
from app.sqlfiles import load_all  # noqa: E402

WRITE = re.compile(r"\b(insert|update|delete|truncate|alter|drop|create|grant)\b", re.I)


class DocsRoute(unittest.TestCase):
    def test_queries_exist_and_only_read(self):
        q = load_all()
        for name in ("assistant.doc_corpus_docs", "assistant.doc_corpus_chunks"):
            self.assertIn(name, q)
            self.assertIsNone(WRITE.search(q[name]), name)
            self.assertTrue(q[name].lstrip().upper().startswith("SELECT"), name)

    def test_only_current_revision_chunks(self):
        sql = load_all()["assistant.doc_corpus_chunks"]
        self.assertIn("current_rev", sql)          # 현행 개정의 조각만 (옛 개정 조각은 안 줌)

    def test_route_uses_read_only_connection_and_no_access_log(self):
        src = inspect.getsource(R.doc_corpus)
        self.assertIn("Depends(get_ro_db)", src)    # 읽기 전용 연결
        self.assertNotIn("Depends(get_db)", src)    # 쓰기 가능한 연결이 아니다
        self.assertNotIn("log_access", src)         # 사람 질문과 무관한 시작 때 읽기 — 쓰기(access_log)를 만들지 않는다
        self.assertIn("SERVICE", src)               # 비서 서비스 키가 있어야 열린다


if __name__ == "__main__":
    unittest.main()
