"""단계별 로그 STEP_LOG (2026-10-15, `research_notes/단계별로그_STEP_LOG_총기획서_20261015.md`).

질문 하나가 답이 되기까지 각 단계(1 규칙 → 2 질문 분류 → 3 찾기 → 4 줄 고르기 → 5 따로 검증 → 6 코드 검사 → 7~ 새로 쓰기 → 12 최종)에서
무슨 일이 있었는지를 파일에 한 줄(JSON Lines)씩 남긴다. 목적: "LLM이 어떤 줄 번호를 골랐나" 같은, 지금까지 추정에 머물던 것을 기록으로 확인한다.

- **읽기만 한다.** LLM에 보내는 글·지시문·검사 규칙·답 내용을 바꾸지 않는다. 꺼져 있으면(기본) 이 모듈은 아무 일도 하지 않는다.
- 요청마다 별도 상자(contextvars — `llm/external.py`·`llm/think.py`·`llm/deadline.py`와 같은 방식)라 두 요청이 섞이지 않는다.
- 쓰기에 실패하거나 상한을 넘어도 **답을 막거나 바꾸지 않는다** — `end()`는 예외를 삼키고 `errors`만 센다. 상한을 넘으면 쓰지 않고 `skipped`만 센다.
- 비밀값은 읽지도 저장하지도 않는다: 설정·요청 머리글·API 키·`.env` 값·서버 주소·사용자 이름. 저장 대상은 질문·역할 코드·화면 맥락·줄 글·LLM이 돌려준 JSON·단계 값뿐이다.
  LLM에 보낸 글 전체는 남기지 않고 글자 수만 남긴다.
- 상한: 한 줄 120KB, 하루 파일 50MB(`steps_YYYYMMDD.jsonl`), 후보 줄은 앞 40자(호출하는 쪽이 `cut()`으로 자름), LLM이 돌려준 JSON은 호출당 4,000자까지,
  글 한 칸 4,000자·목록 한 칸 300개. 자동 삭제는 하지 않는다(폴더 비우기는 사용자가 한다).
- 이 모듈은 backend의 다른 모듈을 import하지 않는다(config가 import해도 순환이 없게).
"""
from __future__ import annotations

import contextvars
import json
import math
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

DEFAULT_DIR = r"C:\llm\logs"
MAX_LINE_BYTES = 120 * 1024          # 한 줄(질문 하나)
MAX_FILE_BYTES = 50 * 1024 * 1024    # 하루 파일
MAX_TEXT = 4000                      # 글 한 칸 (고른 줄은 전문이라 이 안에 들어간다 — 조각 하나가 3,500자 이하)
MAX_RECEIVED = 4000                  # LLM이 돌려준 JSON, 호출당
MAX_ITEMS = 300                      # 목록 한 칸
MAX_KEYS = 100
CAND_CHARS = 40                      # 후보 줄은 앞 40자만
_MAX_DEPTH = 8


@dataclass
class Box:
    """질문 하나의 기록 상자."""
    log_id: str
    dir: str
    ts: datetime
    t0: float
    head: dict
    steps: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    token: object = None


_current: contextvars.ContextVar[Box | None] = contextvars.ContextVar("step_log_box", default=None)
_lock = threading.Lock()
_counters = {"written": 0, "skipped": 0, "errors": 0}


def _bump(name: str) -> None:
    with _lock:
        _counters[name] += 1


def status() -> dict:
    """/api/health용 — 이 프로세스가 쓴 줄 수·상한 때문에 쓰지 않은 수·실패 수 (다시 켜면 0부터)."""
    with _lock:
        return dict(_counters)


def note_error() -> None:
    """기록하는 쪽 도우미가 실패했음을 센다 (답에는 영향이 없다 — 호출한 쪽이 삼킨다)."""
    _bump("errors")


def reset_counters() -> None:
    """시험용."""
    with _lock:
        for k in _counters:
            _counters[k] = 0


def on() -> bool:
    """지금 이 요청이 기록 중인가. 꺼져 있으면 호출하는 쪽은 아무것도 만들지 않는다(`if SL.on():`)."""
    return _current.get() is not None


def current_id() -> str | None:
    box = _current.get()
    return box.log_id if box else None


def now_ms() -> int | None:
    """이 요청이 시작한 뒤 지난 밀리초 (기록 중이 아니면 None)."""
    box = _current.get()
    return int((time.perf_counter() - box.t0) * 1000) if box else None


# ---------------------------------------------------------------- 값 정리 (복사본을 만든다 — 나중에 호출한 쪽이 목록을 고쳐도 기록은 그대로)
def cut(text: object, n: int = CAND_CHARS) -> str:
    t = str(text)
    return t if len(t) <= n else t[:n] + "…"


def _clip(text: str, n: int = MAX_TEXT) -> str:
    return text if len(text) <= n else text[:n] + f"…(+{len(text) - n}자)"


def _clean(v, depth: int = 0):
    if v is None or isinstance(v, (bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else str(v)
    if isinstance(v, str):
        return _clip(v)
    if depth >= _MAX_DEPTH:
        return _clip(str(v), 200)
    if isinstance(v, dict):
        items = list(v.items())
        out = {str(k): _clean(x, depth + 1) for k, x in items[:MAX_KEYS]}
        if len(items) > MAX_KEYS:
            out["…"] = f"+{len(items) - MAX_KEYS}칸"
        return out
    if isinstance(v, (list, tuple, set, frozenset)):
        seq = list(v)
        out = [_clean(x, depth + 1) for x in seq[:MAX_ITEMS]]
        if len(seq) > MAX_ITEMS:
            out.append(f"…(+{len(seq) - MAX_ITEMS}개)")
        return out
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return _clip(str(v), 500)


def _received(out) -> object:
    """LLM이 돌려준 JSON — 호출당 4,000자까지. 넘으면 앞부분만 글로 남긴다."""
    try:
        dumped = json.dumps(out, ensure_ascii=False, default=str)
    except Exception:
        return _clip(str(out), MAX_RECEIVED)
    if len(dumped) <= MAX_RECEIVED:
        return _clean(out)
    return {"잘림": True, "글자수": len(dumped), "앞부분": dumped[:MAX_RECEIVED]}


# ---------------------------------------------------------------- 시작·기록·끝
def begin(directory: str | None, *, question: str, role: str, provider: str, context: dict | None = None,
          has_prev: bool = False) -> Box | None:
    """질문 하나의 상자를 연다. 실패해도 답에 영향이 없게 None을 돌려준다(그러면 이 질문은 기록하지 않는다)."""
    try:
        now = datetime.now()
        box = Box(log_id=f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}", dir=(directory or DEFAULT_DIR), ts=now, t0=time.perf_counter(),
                  head={"시각": now.isoformat(timespec="seconds"), "질문": _clean(question), "역할": _clean(role), "공급자": _clean(provider),
                        "화면맥락": _clean({k: v for k, v in (context or {}).items() if v}), "앞답있음": bool(has_prev)})
        box.token = _current.set(box)
        return box
    except Exception:
        _bump("errors")
        return None


def step(name: str, **fields) -> None:
    """단계 하나를 쌓는다. 단계 이름은 `llm 작동흐름 자세히.md`의 번호를 쓴다("4 줄 고르기" …)."""
    box = _current.get()
    if box is None:
        return
    try:
        box.steps.append({"단계": name, "t_ms": int((time.perf_counter() - box.t0) * 1000), **_clean(fields)})
    except Exception:
        _bump("errors")


def llm_call(job: str, *, kind: str, provider: str, t_ms: int | None, ms: int, ok: bool, reason: str | None = None,
             error: str | None = None, sent_chars: int = 0, received=None, grammar: bool = False, think: int = 0) -> None:
    """LLM 호출 한 번. kind = "재료"(분류·줄 고르기·따로 검증 — 실패하면 외부 모드는 오류로 끝남) | "다듬기"(그 밖 — 실패하면 원문·기본 문장).
    성공이면 받은 JSON을, 실패면 예외 이름과 까닭을 남긴다. 보낸 글 전체는 남기지 않고 글자 수만 남긴다."""
    box = _current.get()
    if box is None:
        return
    try:
        rec = {"작업": job, "구분": kind, "공급자": provider, "시작ms": t_ms, "ms": ms, "결과": "성공" if ok else "실패", "보낸글자수": sent_chars}
        if grammar:
            rec["문법"] = True
        if think:
            rec["생각예산"] = think
        if ok:
            rec["받은JSON"] = _received(received)
        else:
            rec["예외"] = error
            rec["까닭"] = _clip(str(reason), 500)
        box.calls.append(rec)
    except Exception:
        _bump("errors")


def end(box: Box | None, *, final: dict | None = None, error: BaseException | None = None) -> str | None:
    """상자를 닫고 파일에 한 줄 쓴다. 어떤 일이 있어도 예외를 올리지 않는다(실패는 errors로 센다). 쓴 로그 번호를 돌려준다(못 썼으면 None)."""
    if box is None:
        return None
    try:
        try:
            _current.reset(box.token)
        except (ValueError, RuntimeError):   # 다른 맥락에서 닫는 경우 — 이 맥락의 상자만 비운다
            _current.set(None)
        rec = {"log_id": box.log_id, **box.head, "형식": 1,
               "단계": box.steps, "LLM호출": box.calls, "총ms": int((time.perf_counter() - box.t0) * 1000)}
        if error is not None:
            rec["최종"] = _clean({"오류": {"종류": type(error).__name__, "작업": getattr(error, "job", None),
                                         "까닭": getattr(error, "reason", None) or str(error)}})
        else:
            rec["최종"] = _clean(final or {})
        data = (json.dumps(rec, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        if len(data) > MAX_LINE_BYTES:
            _bump("skipped")
            return None
        path = Path(box.dir) / f"steps_{box.ts:%Y%m%d}.jsonl"
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if (path.stat().st_size if path.exists() else 0) + len(data) > MAX_FILE_BYTES:
                _counters["skipped"] += 1
                return None
            with open(path, "ab") as f:   # 바이트로 쓴다 — Windows에서 줄바꿈이 CRLF로 바뀌지 않게
                f.write(data)
            _counters["written"] += 1
        return box.log_id
    except Exception:
        _bump("errors")
        try:
            _current.set(None)
        except Exception:
            pass
        return None
