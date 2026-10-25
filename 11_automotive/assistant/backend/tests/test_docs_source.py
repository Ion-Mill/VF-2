"""사내 문서를 공용 DB에서 읽기 (DOCS_SOURCE=db, 2026-10-25) — 파일 모드와 같은 조각을 만들고, 실패하면 파일로 돌아간다.

DB 모양의 입력은 팀의 적재 도구(backend/tools/load_docs.py의 sections)가 로컬 문서로 만든 것과 같다 — 진짜 공용 DB를 부르지 않는다.
진짜 DB와의 일치도(195/195)는 261003_창민/문서_DB읽기_성과_20261025.md 에 잰 값을 적었다.
"""
import importlib.util
import re
from pathlib import Path

import pytest

from backend.config import DOCS_DIR
from backend.rag import chunker as K
from backend.rag import db_corpus as D
from backend.rag import search as S

LOAD_DOCS = Path(__file__).resolve().parents[3] / "backend" / "tools" / "load_docs.py"


def _load_docs_module():
    spec = importlib.util.spec_from_file_location("load_docs_for_test", LOAD_DOCS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _payload() -> dict:
    """백엔드 GET /api/assistant/docs 와 같은 모양: 로컬 문서를 DB에 넣는 도구(load_docs.sections)가 만든 조각 + 문서 목록."""
    ld = _load_docs_module()
    docs, chunks, n = [], [], 0
    for p in sorted(DOCS_DIR.glob("*.md")):
        if not p.name.startswith(("00_", "DOC-")):
            continue
        raw = p.read_text(encoding="utf-8-sig")
        doc_no, doc_name, rev = K._doc_meta(p, K.normalize_md(raw))
        m = re.match(r"(Rev\.\d+) \(([\d-]+)\)", rev)
        docs.append({"doc_no": doc_no, "doc_name": doc_name, "current_rev": m.group(1), "rev_date": m.group(2)})
        for section, body in ld.sections(raw, f"{doc_name} ({doc_no})"):
            n += 1
            chunks.append({"doc_no": doc_no, "doc_rev": m.group(1), "section": section, "chunk_text": body, "chunk_id": n})
    return {"docs": docs, "chunks": chunks}


@pytest.fixture(autouse=True)
def _clean_cache():
    K.load_corpus.cache_clear()
    S.synonyms.cache_clear()
    K._SRC.clear()
    K._SRC["source"] = "files"
    yield
    K.load_corpus.cache_clear()
    S.synonyms.cache_clear()
    K._SRC.clear()
    K._SRC["source"] = "files"


def test_default_is_files(monkeypatch):
    monkeypatch.delenv("DOCS_SOURCE", raising=False)
    assert len(K.load_corpus()) == 195
    assert K.corpus_source() == {"source": "files"}


@pytest.mark.parametrize("value", ["", "files", "DB2", "yes", "x"])
def test_unknown_value_means_files(monkeypatch, value):
    from backend.config import docs_source
    monkeypatch.setenv("DOCS_SOURCE", value)
    assert docs_source() == "files"


def test_db_chunks_equal_file_chunks():
    """DB 조각을 다시 만든 것이 로컬 파일로 만든 조각과 모든 칸에서 같다 (파일 지문 file_hash만 다르다)."""
    files = K._load_files(DOCS_DIR)
    built = D.build_chunks(_payload())
    assert len(built) == len(files) == 195
    assert [c.chunk_id for c in built] == [c.chunk_id for c in files]
    for a, b in zip(files, built):
        assert (a.doc_id, a.doc_name, a.revision, a.section, a.title, a.text) == (b.doc_id, b.doc_name, b.revision, b.section, b.title, b.text), a.chunk_id


def test_db_mode_loads_and_reports(monkeypatch):
    monkeypatch.setenv("DOCS_SOURCE", "db")
    payload = _payload()
    monkeypatch.setattr(D, "fetch", lambda base, key, timeout=D.TIMEOUT_S: payload)
    got = K.load_corpus()
    assert len(got) == 195
    src = K.corpus_source()
    assert src["source"] == "db" and "fallback" not in src and "glossary" not in src
    assert src["revisions"]["DOC-05"].startswith("Rev.") and len(src["revisions"]) == 8


def test_glossary_synonyms_same_from_db(monkeypatch):
    from_file = dict(S.synonyms())
    S.synonyms.cache_clear()
    monkeypatch.setenv("DOCS_SOURCE", "db")
    payload = _payload()
    monkeypatch.setattr(D, "fetch", lambda base, key, timeout=D.TIMEOUT_S: payload)
    assert dict(S.synonyms()) == from_file and len(from_file) > 100


@pytest.mark.parametrize("failure", [D.CorpusError("HTTP 401"), D.CorpusError("URLError"), OSError("boom")])
def test_db_failure_falls_back_to_files(monkeypatch, failure):
    monkeypatch.setenv("DOCS_SOURCE", "db")

    def boom(base, key, timeout=D.TIMEOUT_S):
        raise failure
    monkeypatch.setattr(D, "fetch", boom)
    assert len(K.load_corpus()) == 195                     # 로컬 파일로 계속
    src = K.corpus_source()
    assert src["source"] == "files" and src["fallback"]
    assert "boom" not in src["fallback"]                   # 예외 문장은 CorpusError만 싣는다 (다른 예외는 종류 이름만)


def test_wrong_doc_count_is_not_used(monkeypatch):
    """DB에 문서가 덜 있으면(8개 아님) DB 조각을 쓰지 않고 파일로 돌아간다."""
    monkeypatch.setenv("DOCS_SOURCE", "db")
    payload = _payload()
    payload["docs"] = payload["docs"][:5]
    monkeypatch.setattr(D, "fetch", lambda base, key, timeout=D.TIMEOUT_S: payload)
    assert len(K.load_corpus()) == 195
    assert K.corpus_source()["source"] == "files" and "5개" in K.corpus_source()["fallback"]


def test_skip_titles_are_not_chunks():
    """DB에는 개정 기록·목차 같은 절도 조각으로 있다 — 로컬 chunker처럼 빼야 한다."""
    payload = _payload()
    titles = [c["chunk_text"].split("\n", 1)[0] for c in payload["chunks"]]
    assert any("개정 기록" in t or "원문 대응표" in t or "쓰는 규칙" in t for t in titles)
    built = D.build_chunks(payload)
    assert not any(any(s in c.title for s in K.SKIP_TITLES) for c in built)


def test_fetch_errors_do_not_carry_address_or_key(monkeypatch):
    import urllib.request

    def refuse(req, timeout=0):
        raise urllib.error.URLError("http://fake-host.invalid:5432 pw=dummy-value")
    import urllib.error
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(D.CorpusError) as e:
        D.fetch("http://127.0.0.1:8020", "KEY-DUMMY")
    assert "fake-host" not in str(e.value) and "dummy-value" not in str(e.value) and "KEY-DUMMY" not in str(e.value)
    with pytest.raises(D.CorpusError):
        D.fetch("", "")


def test_fetch_over_http_sends_key_and_reads_json():
    """진짜 HTTP로 GET /api/assistant/docs 를 한 번 불러 본다 (내 PC 임시 서버): 서비스 키 머리글을 보내고, 받은 JSON으로 같은 조각을 만든다."""
    import http.server
    import json
    import threading
    payload = _payload()
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen["path"], seen["key"] = self.path, self.headers.get("X-Service-Key")
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200 if seen["key"] == "k-test" else 401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body if seen["key"] == "k-test" else b"{}")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        got = D.fetch(base, "k-test")
        assert seen == {"path": "/api/assistant/docs", "key": "k-test"}
        assert len(D.build_chunks(got)) == 195
        with pytest.raises(D.CorpusError, match="HTTP 401"):
            D.fetch(base, "wrong-key")
    finally:
        srv.shutdown()


# ---- 2차 (2026-10-25): 문서만 따로 정한 백엔드(DOCS_BACKEND_URL)에서 가져오기 — start_all.ps1 -SupabaseDocs 가 8021을 켜고 주소를 준다 ----
def test_docs_backend_defaults_to_main_backend(monkeypatch):
    from backend.config import docs_backend
    for k in ("DOCS_BACKEND_URL", "DOCS_BACKEND_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MOM_BACKEND_URL", "http://127.0.0.1:8020")
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "k-main")
    assert docs_backend() == ("http://127.0.0.1:8020", "k-main")


def test_docs_backend_own_url_and_key_win(monkeypatch):
    from backend.config import docs_backend
    monkeypatch.setenv("MOM_BACKEND_URL", "http://127.0.0.1:8020")
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "k-main")
    monkeypatch.setenv("DOCS_BACKEND_URL", "http://127.0.0.1:8021")
    assert docs_backend() == ("http://127.0.0.1:8021", "k-main")           # 키를 따로 안 주면 비서 키 그대로
    monkeypatch.setenv("DOCS_BACKEND_KEY", "k-docs")
    assert docs_backend() == ("http://127.0.0.1:8021", "k-docs")
    monkeypatch.setenv("DOCS_BACKEND_URL", "   ")                          # 빈 값(공백)은 안 준 것과 같다
    assert docs_backend()[0] == "http://127.0.0.1:8020"


@pytest.mark.parametrize("docs_url,via", [("", "main_backend"), ("http://127.0.0.1:8021", "docs_backend")])
def test_db_mode_asks_the_docs_backend_and_reports_via(monkeypatch, docs_url, via):
    monkeypatch.setenv("DOCS_SOURCE", "db")
    monkeypatch.setenv("MOM_BACKEND_URL", "http://127.0.0.1:8020")
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "k-main")
    monkeypatch.setenv("DOCS_BACKEND_URL", docs_url)
    monkeypatch.delenv("DOCS_BACKEND_KEY", raising=False)
    payload, asked = _payload(), {}

    def fake(base, key, timeout=D.TIMEOUT_S):
        asked.update(base=base, key=key)
        return payload
    monkeypatch.setattr(D, "fetch", fake)
    assert len(K.load_corpus()) == 195
    assert asked == {"base": docs_url or "http://127.0.0.1:8020", "key": "k-main"}
    src = K.corpus_source()
    assert src["source"] == "db" and src["via"] == via
    assert "127.0.0.1" not in str(src)                                      # 주소는 /health에 싣지 않는다


def test_docs_backend_down_falls_back_to_files(monkeypatch):
    """문서 백엔드(8021)가 꺼져 있으면 운영 백엔드(8020)로 몰래 바꾸지 않고 파일로 돌아간다."""
    monkeypatch.setenv("DOCS_SOURCE", "db")
    monkeypatch.setenv("MOM_BACKEND_URL", "http://127.0.0.1:8020")
    monkeypatch.setenv("DOCS_BACKEND_URL", "http://127.0.0.1:1")           # 아무도 안 듣는 포트
    monkeypatch.setenv("MOM_ASSISTANT_KEY", "k")
    assert len(K.load_corpus()) == 195
    src = K.corpus_source()
    assert src["source"] == "files" and src["fallback"]
