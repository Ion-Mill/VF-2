"""시연 서버가 9월 기록을 DB에서 읽는 부분 시험 (2026-10-23, server_past.py) — DB 없이 도는 것만.

실행 (frontend/ 폴더에서):  ..\\생성기\\.venv\\Scripts\\python -m pytest tools/tests -q
지키는 것: ① DB 값을 생성기 CSV와 같은 글자로 바꾼다 ② 접속 주소를 고르는 순서(MOM_PAST_DB_URL → 백엔드 환경 파일 → 로컬 Docker)
③ 주소가 없거나 DB를 못 읽으면 CSV로 돈다 ④ 표마다 10/1 시작 전 조건이 있다
DB 값 = CSV 값 대조는 DB가 있어야 해서 여기서는 안 한다 (구현_중_수정사항/1023_수정간단내용.md에 결과).
"""
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "생성기"))

from gen.common import KST  # noqa: E402
import server_past  # noqa: E402
from server_past import PAST_WHERE, Past, db_text, past_db_target  # noqa: E402

ROOT = HERE.parent.parent
CUT = datetime(2026, 10, 1, 8, tzinfo=KST)


def test_db_text_matches_generator_csv():
    assert db_text(None) == ""
    assert db_text(True) == "true" and db_text(False) == "false"
    assert db_text(datetime(2026, 9, 1, 17, 16, tzinfo=KST)) == "2026-09-01T17:16:00+09:00"
    assert db_text(date(2026, 9, 1)) == "2026-09-01"
    assert db_text(Decimal("61.60")) == "61.6" and db_text(Decimal("8.00")) == "8" and db_text(Decimal("0.005")) == "0.005"
    assert db_text(90) == "90"
    assert db_text({"a": "가"}) == '{"a": "가"}'


def _backend(tmp_path, name, text):
    (tmp_path / "backend").mkdir(exist_ok=True)
    (tmp_path / "backend" / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_target_order(tmp_path, monkeypatch):
    monkeypatch.delenv("MOM_PAST_DB_URL", raising=False)
    monkeypatch.delenv("MOM_ENV_FILE", raising=False)
    assert past_db_target(tmp_path)[0] is None                                            # 환경 파일 없음 → CSV
    _backend(tmp_path, ".env.supabase", "MOM_READONLY_DATABASE_URL=postgresql+psycopg://ro:pw@db.example:5432/postgres\n")
    assert past_db_target(tmp_path)[0] == "postgresql://ro:pw@db.example:5432/postgres"     # 백엔드와 같은 DB, 읽기 계정
    _backend(tmp_path, ".env", "# 주석=무시\nMOM_AI_DB_PASSWORD=p@ss/word\n")
    monkeypatch.setenv("MOM_ENV_FILE", ".env")
    assert past_db_target(tmp_path)[0] == "postgresql://mom_ai_ro:p%40ss%2Fword@127.0.0.1:5432/mom"   # Docker .env
    monkeypatch.setenv("MOM_PAST_DB_URL", "postgresql://x@h/db")
    assert past_db_target(tmp_path)[0] == "postgresql://x@h/db"
    monkeypatch.setenv("MOM_PAST_DB_URL", "off")
    assert past_db_target(tmp_path)[0] is None


def test_falls_back_to_csv_when_db_fails(monkeypatch):
    monkeypatch.setenv("MOM_PAST_DB_URL", "postgresql://u@127.0.0.1:1/mom")
    def boom(*a, **k):
        raise OSError("접속 안 됨")
    monkeypatch.setattr(server_past, "read_past_db", boom)
    logs = []
    p = Past(ROOT, cutoff=CUT, log=logs.append)
    assert p.source == "csv" and "DB 읽기 실패" in logs[0]
    assert len(p.alarms) > 0 and p.materials                                              # CSV로 9월 기록이 있다


def test_every_past_table_has_a_cutoff():
    for t, where in PAST_WHERE.items():
        assert "%(c)s" in where or "%(d)s" in where, t
