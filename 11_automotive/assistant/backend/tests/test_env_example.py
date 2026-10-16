"""`.env.example`을 복사해 쓰는 사람이 값 옆에 `# 설명`을 붙여도 값이 깨지지 않게 하는 약속 ([11_automotive 이식 2026-10-16]).

config._dotenv()는 `KEY=값   # 설명`의 설명까지 값으로 읽는다(`EXTERNAL_LLM_APP=1   # …`는 '1'이 아니게 되어 조용히 꺼지고, `LLM_JOBS=write,route   # …`는
`route   # …`라는 이름의 작업이 된다). 그래서 예시 파일은 설명을 항상 윗줄에 둔다.
"""
import re
from pathlib import Path

import pytest

from backend import config as C

pytestmark = pytest.mark.own_backend            # 가짜 백엔드가 .env 읽기(_dotenv)를 막아 두므로 이 파일은 그 기본을 끈다
EXAMPLE =Path(__file__).resolve().parents[2] / ".env.example"


def test_example_has_no_inline_comments():
    bad = [l for l in EXAMPLE.read_text(encoding="utf-8").splitlines() if re.match(r"\s*[A-Za-z_]\w*=", l) and re.search(r"\s#", l)]
    assert bad == [], bad


def test_example_values_are_read_back_clean(monkeypatch):
    monkeypatch.setattr(C, "ROOT", EXAMPLE.parent / "nonexistent")      # 개발 PC의 .env 말고
    text = EXAMPLE.read_text(encoding="utf-8")
    tmp = {}
    for line in text.splitlines():
        m = re.match(r"([A-Za-z_]\w*)=(.*)", line)
        if m:
            tmp[m.group(1)] = m.group(2).strip()
    assert tmp["EXTERNAL_LLM_APP"] == "0" and tmp["LLM_ENABLED"] == "0" and tmp["ASSISTANT_PROVIDER"] == "local"   # 기본은 외부로 안 나감
    assert tmp["LLM_JOBS"] == "write,route"
    assert all("#" not in v for v in tmp.values())


@pytest.mark.parametrize("line,expected", [("EXTERNAL_LLM_APP=1", True), ("EXTERNAL_LLM_APP=1   # 설명", False)])
def test_documented_pitfall_is_real(tmp_path, monkeypatch, line, expected):
    """이 약속이 필요한 까닭: 값 옆 설명이 있으면 켜지지 않는다 (config 쪽을 고치면 이 시험은 지워도 된다)."""
    (tmp_path / ".env").write_text(line + "\n", encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.delenv("EXTERNAL_LLM_APP", raising=False)
    assert C.settings().external_app is expected
