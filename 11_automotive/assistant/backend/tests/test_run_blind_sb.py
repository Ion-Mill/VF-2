"""scripts/eval/run_blind_sb.py 인자 시험 (2026-10-14): 권한 규칙이 명령 앞부분만 보므로 복사본을 환경변수 접두 대신 --sandbox 인자로 받는다.
외부 호출은 하지 않는다(인자 분리와 복사본 검사만)."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "eval"


@pytest.fixture
def rb(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("run_blind_sb_under_test", SCRIPTS / "run_blind_sb.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    sys.modules.pop("run_blind_sb_under_test", None)


def test_take_option_removes_the_pair_and_returns_the_value(rb):
    argv = ["--sandbox", "C:/x/sb", "set.json", "claude-haiku"]
    assert rb.take_option(argv, "--sandbox") == "C:/x/sb"
    assert argv == ["set.json", "claude-haiku"]
    assert rb.take_option(argv, "--sandbox") is None
    with pytest.raises(SystemExit, match="값이 없습니다"):
        rb.take_option(["a", "--sandbox"], "--sandbox")


def test_sandbox_argument_must_not_be_the_real_repo(rb, monkeypatch):
    """--sandbox가 실제 저장소(또는 그 안)를 가리키면 외부 호출 전에 멈춘다."""
    monkeypatch.delenv("MOM_SANDBOX", raising=False)
    sets = SCRIPTS.parents[1] / "backend" / "eval" / "qa_set.json"
    repo = str(SCRIPTS.parents[1])
    with pytest.raises(SystemExit, match="실제 저장소|저장소 밖"):
        rb.main(["--sandbox", repo, str(sets), "claude-haiku"])
    import os
    os.environ.pop("MOM_SANDBOX", None)   # main()이 --sandbox 값을 환경에 넣으므로 둘째 경우(복사본 지정 없음) 전에 비운다
    with pytest.raises(SystemExit, match="환경 변수로 주세요"):
        rb.main([str(sets), "claude-haiku"])
    os.environ.pop("MOM_SANDBOX", None)


def test_usage_message_when_arguments_are_missing(rb, monkeypatch):
    monkeypatch.delenv("MOM_SANDBOX", raising=False)
    with pytest.raises(SystemExit, match="사용"):
        rb.main(["only_one_argument"])
