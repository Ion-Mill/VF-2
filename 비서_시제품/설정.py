"""AI 비서 시제품 공통 설정 (경로, 역할 권한, Claude 실행 파일)."""

import glob
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AUTO = ROOT / "11_automotive"

DOC_SRC = AUTO / "가상사내문서"            # 원본 md (사람이 고치는 곳)
SEARCH_DIR = HERE / "검색용문서"          # 원문 출처를 뺀 사본 (스크립트가 만듦)
INDEX_FILE = SEARCH_DIR / "조각.jsonl"    # 절 단위 조각 목록
MASTERS = AUTO / "생성기" / "masters"
GEN_OUT = AUTO / "생성기" / "out"         # 과거 30일
GEN_RT = AUTO / "생성기" / "out_realtime" # 실시간(시연) 이어 붙인 기록
DB_FILE = HERE / "채팅기록.sqlite3"

# 시연 시각: 지정하지 않으면 실시간 데이터의 now_at을 쓴다 (API 명세 1장 "시뮬레이터 시계 기준")
NOW_OVERRIDE = os.environ.get("EVE_NOW")

# 채팅 권한 [가상: 2026-10-13 팀 결정] — MTTR·센서 데이터는 MNT·MGR만 (FR-MNT-01-04)
GATED_TOOLS = {"mttr": {"MNT", "MGR"}, "sensor_trend": {"MNT", "MGR"}}
PERMISSION_MESSAGE = "이 정보(MTTR·센서 데이터)는 보전 담당자·관리자만 볼 수 있습니다."  # [제안] 문구

STATUSES = ["ok", "문서에 없음", "거부", "권한 밖", "응답 없음"]
CHAT_KEEP_DAYS = 30                       # FR-MNT-01-01, 30일 저장

MODEL = os.environ.get("EVE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("EVE_EFFORT", "medium")
TIMEOUT_SEC = int(os.environ.get("EVE_TIMEOUT", "300"))


def find_claude() -> str:
    """claude 실행 파일: 환경 변수 CLAUDE_CLI → PATH → VS Code 확장 안의 파일(가장 새 버전)."""
    if os.environ.get("CLAUDE_CLI"):
        return os.environ["CLAUDE_CLI"]
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    pattern = str(Path.home() / ".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude*")
    def version_key(path: str) -> list:
        ver = path.split("anthropic.claude-code-")[1].split("-")[0]
        return [int(p) if p.isdigit() else 0 for p in ver.split(".")]

    found = sorted(glob.glob(pattern), key=version_key)
    if found:
        return found[-1]
    raise FileNotFoundError(
        "claude 실행 파일을 찾지 못했습니다. Claude Code를 설치하거나 CLAUDE_CLI 환경 변수에 경로를 넣으세요."
    )
