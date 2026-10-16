"""Claude Code CLI(`claude -p`) 호출 도우미 — 점수·비용 비교 실험 전용 (2026-10-14 사용자 결정: API 키 대신 이 PC의 구독 로그인을 쓴다).

- 호출마다 `claude.exe -p` 프로세스 하나. 도구·MCP·스킬·설정·세션 저장을 모두 끄고, 시스템 지시는 `--system-prompt`로 바꿔 "순수 LLM 호출"에 가깝게 한다.
  `--bare`는 쓰지 않는다 — `--help`에 "Anthropic auth is strictly ANTHROPIC_API_KEY"라 구독 로그인(OAuth)을 읽지 않는다.
- 자식 프로세스 환경에서 `CLAUDE*`·`ANTHROPIC*`를 모두 뺀다: 이 코드를 부르는 쪽(예: Claude Code 안의 셸)이 `CLAUDECODE`·`CLAUDE_CODE_MESSAGING_*`·`CLAUDE_EFFORT` 같은 값을
  들고 있으면 자식이 그 대화에 붙거나 설정이 섞이고, `ANTHROPIC_API_KEY`가 있으면 구독이 아니라 API 요금이 나간다.
- 작업 폴더는 저장소 밖 빈 폴더 — 이 저장소의 `CLAUDE.md`·`.claude/rules`가 자동으로 읽히는 것을 막는다.
- 열쇠·사용자 글·답 글을 어디에도 출력하지 않는다. 오류 설명에는 종료 코드와 stderr 끝부분(열쇠 꼴은 가림)만 쓴다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

DEFAULT_CWD = Path(r"C:\llm\claude_cli_cwd")
# 사용 한도·속도 제한을 알리는 CLI 문구 (모양은 스모크에서 확인 — 모르는 문구는 일반 오류로 센다)
LIMIT_RE = re.compile(r"usage limit|limit reached|rate.?limit|too many requests|overloaded|\b429\b|quota|한도", re.I)
KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")
_version_cache: dict[str, str] = {}


def clean_env(env: dict | None = None) -> dict:
    """자식 프로세스에 넘길 환경: `CLAUDE*`·`ANTHROPIC*` 이름을 모두 뺀다(대소문자 무시). 나머지(PATH·USERPROFILE·APPDATA …)는 구독 로그인을 읽는 데 필요하다."""
    src = os.environ if env is None else env
    return {k: v for k, v in src.items() if not k.upper().startswith(("CLAUDE", "ANTHROPIC"))}


def _version_key(p: Path) -> tuple:
    m = re.search(r"claude-code-(\d+(?:\.\d+)*)", p.parent.parent.parent.name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def find_bin() -> Path | None:
    """`claude` 실행 파일. MOM_CLAUDE_BIN(os.environ) → PATH → Cursor·VS Code 확장 폴더의 가장 새 `anthropic.claude-code-*` 순."""
    given = os.environ.get("MOM_CLAUDE_BIN")
    if given:
        return Path(given) if Path(given).is_file() else None
    from shutil import which
    w = which("claude")
    if w:
        return Path(w)
    found: list[Path] = []
    for ide in (".cursor", ".vscode", ".vscode-insiders"):
        found += list((Path.home() / ide / "extensions").glob("anthropic.claude-code-*/resources/native-binary/claude*"))
    found = [p for p in found if p.is_file() and p.suffix.lower() in ("", ".exe")]
    return max(found, key=_version_key) if found else None


def work_dir() -> Path:
    """저장소 밖 빈 작업 폴더 (없으면 만든다). MOM_CLAUDE_CWD로 바꿀 수 있다."""
    p = Path(os.environ.get("MOM_CLAUDE_CWD") or DEFAULT_CWD)
    p.mkdir(parents=True, exist_ok=True)
    return p


def build_cmd(binary: Path | str, model: str, effort: str, system: str, schema: dict) -> list[str]:
    """명령줄. 사용자 글은 stdin으로 보낸다(명령줄 길이·따옴표 문제 회피). 스키마는 호출 쪽이 제약을 뺀 것을 넘긴다."""
    return [str(binary), "-p", "--output-format", "json",
            "--json-schema", json.dumps(schema, ensure_ascii=True, separators=(",", ":")),
            "--model", model, "--effort", effort,
            "--system-prompt", system or "너는 요청에 JSON으로만 답하는 도우미다.",
            "--tools", "", "--no-session-persistence", "--setting-sources", "",
            "--strict-mcp-config", "--disable-slash-commands"]


def user_text(messages: list[dict]) -> str:
    """system이 아닌 메시지를 stdin 글 하나로 (보통 user 하나)."""
    rest = [m for m in messages if m["role"] != "system"]
    if len(rest) == 1:
        return str(rest[0]["content"])
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in rest)


def run(cmd: list[str], stdin_text: str, timeout: float) -> subprocess.CompletedProcess:
    """실제 실행기 (시험이 `claude_client.use_runner`로 가짜를 끼운다)."""
    return subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=clean_env(), cwd=str(work_dir()), timeout=timeout)


def safe_tail(text: str | None, n: int = 160) -> str:
    return KEY_RE.sub("sk-ant-…", (text or "").strip())[-n:]


def cli_version(binary: Path | str) -> str:
    """`claude --version` 한 줄 (프로세스당 한 번). 못 읽으면 '알 수 없음'."""
    k = str(binary)
    if k not in _version_cache:
        try:
            r = subprocess.run([k, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env=clean_env(), cwd=str(work_dir()), timeout=30)
            _version_cache[k] = (r.stdout or "").strip().splitlines()[0] if r.returncode == 0 and (r.stdout or "").strip() else "알 수 없음"
        except (OSError, subprocess.TimeoutExpired):
            _version_cache[k] = "알 수 없음"
    return _version_cache[k]


def auth_status(binary: Path | str) -> dict:
    """`claude auth status`에서 로그인 여부·방식·구독 종류만 (이메일·조직은 돌려주지 않는다)."""
    try:
        r = subprocess.run([str(binary), "auth", "status"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=clean_env(), cwd=str(work_dir()), timeout=30)
        d = json.loads(r.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"loggedIn": False, "error": "상태를 읽지 못함"}
    return {k: d.get(k) for k in ("loggedIn", "authMethod", "subscriptionType")}


def parse_result(stdout: str) -> dict:
    """`--output-format json`의 결과 한 덩어리. 한 줄 JSON이거나 마지막 줄이 결과일 수 있어 둘 다 받는다. 못 읽으면 ValueError."""
    s = (stdout or "").strip()
    if not s:
        raise ValueError("빈 출력")
    try:
        d = json.loads(s)
    except ValueError:
        d = json.loads(s.splitlines()[-1])
    if isinstance(d, list):   # stream 모양이 배열로 오면 type == result 인 것
        d = next((x for x in reversed(d) if isinstance(x, dict) and x.get("type") == "result"), None)
    if not isinstance(d, dict):
        raise ValueError("결과 모양이 다름")
    return d


def payload_of(d: dict):
    """구조화 결과: `structured_output`이 있으면 그것, 없으면 `result` 글을 JSON으로. 못 읽으면 ValueError."""
    if isinstance(d.get("structured_output"), dict):
        return d["structured_output"]
    res = d.get("result")
    if isinstance(res, dict):
        return res
    if isinstance(res, str) and res.strip():
        t = res.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-z]*\s*|\s*```$", "", t)
        return json.loads(t)
    raise ValueError("구조화 결과 없음")


def usage_of(d: dict) -> dict:
    """토큰·비용·모델 — 기록용. 모르는 칸은 0/None."""
    u = d.get("usage") or {}
    g = lambda k: int(u.get(k) or 0)  # noqa: E731
    models = list((d.get("modelUsage") or {}).keys())
    return {"in": g("input_tokens"), "out": g("output_tokens"), "cache_read": g("cache_read_input_tokens"),
            "cache_write": g("cache_creation_input_tokens"), "models": models,
            "usd": d.get("total_cost_usd"), "api_ms": d.get("duration_api_ms"), "turns": d.get("num_turns")}
