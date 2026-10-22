"""Claude 연결 — 점수·비용 비교 실험 전용 (2026-10-14 사용자 결정, NFR-SEC-08의 한시 예외).

- `client.chat_json`이 `LLM_PROVIDER=claude`일 때만 여기로 넘긴다. 기본(local)은 이 파일을 부르지 않는다.
- 방식 둘 (`MOM_CLAUDE_VIA`): **cli**(기본) = 이 PC의 Claude Code(`claude -p`, 구독 로그인 — `claude_cli.py`), **api** = Anthropic API(`ANTHROPIC_API_KEY`).
- 앱(8000)은 쓰지 않는다. 시험용 복사본의 비교 평가에서만 켜진다: 환경변수 `MOM_EXTERNAL_LLM_OK=1`(config가 os.environ에서만 읽음)과
  `MOM_USAGE_LEDGER`(사용량 기록 경로, `usage_<이름>.jsonl`)가 있어야 하고, api는 `ANTHROPIC_API_KEY`(os.environ에서만 — `.env`·`LLM_API_KEY`·평가 모드 환경에는 두지 않는다),
  cli는 `claude` 실행 파일이 있어야 한다.
- 같은 서명·같은 예외(`LlmUnavailable`·`LlmBadOutput`)로 돌려주어 부른 쪽 코드(jobs.py·followup_v2.py)는 그대로다.
- 5.5 계열은 temperature·top_p 같은 샘플링과 seed가 없다 → 보내지 않는다(결과가 매번 조금 다를 수 있어 평가는 2번 반복한다).
- 구조화 출력은 JSON 스키마. `minLength/maxLength/minItems/maxItems/minimum/maximum`은 지원하지 않아 스키마에서 빼고,
  받은 뒤 같은 제약을 코드로 다시 검사한다(로컬에서는 문법이 막아 주던 것). `grammar`(GBNF)는 받되 쓰지 않는다 — 대신 코드 검사(자리표·허락·지시·판정)가 막는다.
- 호출마다 토큰·지연·비용을 기록한다. 질문·답 글은 기록하지 않는다. 누적 비용(cli는 API 가격표로 환산한 값 — 청구가 아님)이 상한에 닿으면 더 부르지 않는다.
- 열쇠 값은 어디에도 출력·기록하지 않는다.
"""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from backend.config import Settings, settings
from backend.llm import claude_cli as CLI
from backend.llm import deadline as DL
from backend.llm import external as EXT
from backend.llm.client import LlmBadOutput, LlmUnavailable
from backend.privacy import outbound_guard as OG

# 1M 토큰당 달러 (입력, 출력). 출처: claude-api skill 표(2026-10-06 캐시) — api는 실제 청구를 Anthropic Console에서 확인한다.
# cli는 결과 JSON의 total_cost_usd(CLI가 같은 가격표로 환산)를 쓰고, 없으면 이 표로 계산한다.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
CONTINUE_JOB = "continue"   # 짧은 후속 질문의 이어짐 판단 (services/continuation.JOB — 같은 까닭으로 글자로 둔다). 재료 단계(MATERIAL_JOBS)가 아니라 실패해도 지금 동작으로 간다. PURE_MODEL(Haiku)로 부른다
PURE_ANSWER_JOB = "pure_answer"   # 순수 길 본 답변의 작업 이름 (services/pure_external.JOB — import하면 순환이라 글자로 두고 시험이 같은지 단정한다). PURE_MODEL은 이 호출에만 쓰인다
SCREEN_SUMMARY_JOB = "screen_summary"   # 화면 정보판 요약 (services/screen_summary.JOB). 본 답과 같이 PURE_MODEL(Haiku)로 부른다
MIN_MAX_TOKENS = 1500   # api: 생각 토큰이 max_tokens를 같이 쓴다 — 로컬용 120·300 같은 값이면 "길이 초과"로 잘린다
BREAK_S = 30.0
TIMEOUT_TRIPS = 2
LIMIT_TRIPS = 3         # cli: 사용 한도·속도 제한 오류가 연속 3번이면 이 프로세스에서는 더 부르지 않는다 (한도를 끝까지 태우지 않음)
# 스키마에서 빼는 제약 (Anthropic 구조화 출력이 지원하지 않음). 받은 뒤 validate_constraints가 다시 본다.
UNSUPPORTED = ("minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf")

_lock = threading.Lock()
_injected = None              # 시험이 가짜 API 클라이언트를 끼운다
_runner = None                # 시험이 가짜 CLI 실행기를 끼운다 (cmd, stdin_text, timeout) -> CompletedProcess 꼴
_real = {}                    # (read_s, connect_s) → anthropic.Anthropic
_down_until = 0.0
_timeouts = 0
_limit_hits = 0
_totals = {"base": None, "own": 0.0, "path": None}   # base = 다른 기록 파일들의 합(프로세스 시작 때 한 번), own = 이 프로세스가 쓴 만큼
# 앱 스위치용 (2026-10-15, 사용자 결정 Q6): 파일 기록 없이 이 프로세스 메모리에만 두는 호출 수·환산 비용 추정. /api/health에 보인다(다시 켜면 사라진다)
_counters = {"calls": 0, "usd_est": 0.0, "since": datetime.now().isoformat(timespec="seconds")}
_sem = None                   # 동시 claude 프로세스 상한 (PC 보호용 — 사용량 제한이 아님)
_sem_n = 0


def counters() -> dict:
    with _lock:
        return dict(_counters)


@contextmanager
def _proc_slot(s: Settings, wait: float):
    """동시에 띄우는 `claude` 프로세스 수를 s.proc_limit으로 막는다. 자리가 날 때까지 최대 wait초 기다리고(한 답의 예산에 포함), 못 얻으면 LlmUnavailable."""
    global _sem, _sem_n
    with _lock:
        if _sem is None or _sem_n != s.proc_limit:
            _sem, _sem_n = threading.BoundedSemaphore(max(1, s.proc_limit)), s.proc_limit
        sem = _sem
    if not sem.acquire(timeout=max(0.1, wait)):
        raise LlmUnavailable(f"동시 처리 한도({s.proc_limit}) 초과")
    try:
        yield
    finally:
        sem.release()


def _reset() -> None:
    global _down_until, _timeouts, _limit_hits
    _real.clear()
    _down_until, _timeouts, _limit_hits = 0.0, 0, 0
    _totals.update(base=None, own=0.0, path=None)
    CLI._version_cache.clear()


def use_client(fake) -> None:
    """시험용: anthropic.Anthropic 대신 가짜(`.messages.create(**kw)`를 가진 객체)를 쓴다. None이면 되돌린다."""
    global _injected
    with _lock:
        _injected = fake
        _reset()


def use_runner(fake) -> None:
    """시험용: 진짜 `claude` 프로세스 대신 가짜 실행기를 쓴다. None이면 되돌린다."""
    global _runner
    with _lock:
        _runner = fake
        _reset()


# ------------------------------------------------------------------ 잠금·비용
def gate_problem(s: Settings) -> str | None:
    """외부 호출을 막는 이유 (없으면 None). 키 값은 돌려주지 않는다.
    앱 스위치 경로(s.claude_app, 2026-10-15)는 서버 스위치(EXTERNAL_LLM_APP)가 문이라 환경변수 잠금·사용량 기록 경로·비용 상한을 요구하지 않는다 —
    사용자 결정: 기록 안 남김·사용 상한 없음. 평가 경로(claude_app 아님)는 예전과 똑같이 셋 다 요구한다."""
    if not s.claude_app and os.environ.get("MOM_EXTERNAL_LLM_OK") != "1":
        return "외부 LLM 잠금: 비교 실험 전용(MOM_EXTERNAL_LLM_OK=1 없음)"
    if s.claude_via == "api":
        if not os.environ.get("ANTHROPIC_API_KEY") and _injected is None:
            return "ANTHROPIC_API_KEY 없음"
    elif _runner is None and CLI.find_bin() is None:
        return "claude 실행 파일 없음 (MOM_CLAUDE_BIN 또는 Cursor·VS Code 확장 폴더)"
    if not s.claude_app:
        led = os.environ.get("MOM_USAGE_LEDGER")
        if not led:
            return "사용량 기록 경로(MOM_USAGE_LEDGER) 없음 — 비용을 못 재면 외부로 부르지 않는다"
        if not (Path(led).name.startswith("usage_") and Path(led).suffix == ".jsonl"):   # 누적 상한이 같은 폴더의 usage_*.jsonl 합이다
            return "사용량 기록 파일 이름은 usage_<이름>.jsonl 꼴이어야 한다"
    if s.claude_model not in PRICES:
        return f"알 수 없는 모델: {s.claude_model}"
    if not s.claude_app and s.claude_cost_cap_usd <= 0:
        return "비용 상한이 0 이하"
    return None


def cost_usd(model: str, in_tok: int, out_tok: int, cache_read: int = 0, cache_write: int = 0) -> float:
    pin, pout = PRICES[model]
    return (in_tok * pin + cache_read * pin * 0.1 + cache_write * pin * 1.25 + out_tok * pout) / 1_000_000


def _spent(ledger: Path) -> float:
    """지금까지 쓴 돈: 같은 폴더의 기록 파일 합(이 프로세스가 시작할 때 이미 있던 만큼, 한 번) + 이 프로세스가 쓴 만큼."""
    if _totals["base"] is None or _totals["path"] != str(ledger):
        base = 0.0
        if ledger.parent.is_dir():
            for f in ledger.parent.glob("usage_*.jsonl"):
                for line in f.read_text(encoding="utf-8").splitlines():
                    try:
                        base += float(json.loads(line).get("usd", 0.0))
                    except (ValueError, TypeError):
                        continue
        _totals.update(base=base, own=0.0, path=str(ledger))
    return _totals["base"] + _totals["own"]


def _write_row(row: dict, usd: float) -> None:
    led = os.environ.get("MOM_USAGE_LEDGER")
    if led:
        Path(led).parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        if row.get("kind") != "trim":   # 앱 스위치 카운터(메모리) — 기록 파일이 없어도 센다
            _counters["calls"] += 1
            _counters["usd_est"] = round(_counters["usd_est"] + usd, 6)
        if not led:   # 앱 스위치 경로: 기록 파일을 만들지 않는다 (사용자 결정 2026-10-15 "기록 안 남김")
            return
        ledger = Path(led)
        _spent(ledger)
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        _totals["own"] += usd


def external_status() -> dict:
    """/api/health용 (앱 스위치, 2026-10-15): 서버 끄는 스위치·모델·사용 가능 여부와 이 프로세스의 메모리 카운터. 프로세스를 띄우거나 외부로 보내지 않는다."""
    base = settings()
    if not base.external_app:
        return {"server_switch": False, "available": False, "reason": "서버에서 꺼져 있음 (EXTERNAL_LLM_APP)", "counters": counters()}
    with EXT.external_request("claude"):
        s = settings()
    why = None if s.llm_enabled else (s.problem or "LLM_ENABLED=0")
    why = why or gate_problem(s)
    return {"server_switch": True, "available": why is None, "reason": why, "model": s.claude_model, "effort": s.claude_effort,
            "via": s.claude_via, "label": s.llm_label, "proc_limit": s.proc_limit, "counters": counters()}


def _record_api(s: Settings, name: str, resp, ms: int) -> float:
    """api 호출 기록 한 줄(jsonl). 글 내용은 쓰지 않는다. 이 호출의 비용을 돌려준다."""
    u = getattr(resp, "usage", None)
    g = lambda k: int(getattr(u, k, 0) or 0)  # noqa: E731
    in_t, out_t, cr, cw = g("input_tokens"), g("output_tokens"), g("cache_read_input_tokens"), g("cache_creation_input_tokens")
    usd = cost_usd(s.claude_model, in_t, out_t, cr, cw)
    _write_row({"t": datetime.now().isoformat(timespec="seconds"), "via": "api", "model": s.claude_model, "effort": s.claude_effort, "job": name,
                "in": in_t, "out": out_t, "cache_read": cr, "cache_write": cw, "ms": ms,
                "stop": getattr(resp, "stop_reason", None), "usd": round(usd, 6)}, usd)
    return usd


def _record_cli(s: Settings, name: str, d: dict, ms: int, version: str) -> float:
    """cli 호출 기록 한 줄. 비용은 CLI가 환산해 준 total_cost_usd(없으면 가격표 계산) — 구독이라 청구가 아니다."""
    u = CLI.usage_of(d)
    usd = float(u["usd"]) if isinstance(u["usd"], (int, float)) else cost_usd(s.claude_model, u["in"], u["out"], u["cache_read"], u["cache_write"])
    _write_row({"t": datetime.now().isoformat(timespec="seconds"), "via": "cli", "cli": version, "model": s.claude_model, "models": u["models"],
                "effort": s.claude_effort, "job": name, "in": u["in"], "out": u["out"], "cache_read": u["cache_read"],
                "cache_write": u["cache_write"], "ms": ms, "api_ms": u["api_ms"], "turns": u["turns"],
                "stop": d.get("subtype") or d.get("stop_reason"), "usd": round(usd, 6)}, usd)
    return usd


def ledger_summary(path: str | Path | None = None) -> dict | None:
    """평가 끝에 붙이는 사용량 합계 (호출·토큰·$·작업별). 기록이 없으면 None."""
    p = Path(path or os.environ.get("MOM_USAGE_LEDGER") or "")
    if not p.is_file():
        return None
    allrows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in allrows if r.get("kind") != "trim"]
    trimmed = sum(r.get("n", 0) for r in allrows if r.get("kind") == "trim")
    if not rows:
        return None
    by_job: dict[str, dict] = {}
    for r in rows:
        j = by_job.setdefault(r["job"], {"calls": 0, "in": 0, "out": 0, "usd": 0.0})
        j["calls"] += 1
        j["in"] += r["in"]
        j["out"] += r["out"]
        j["usd"] = round(j["usd"] + r["usd"], 6)
    ms = sorted(r["ms"] for r in rows)
    api = sorted(r["api_ms"] for r in rows if isinstance(r.get("api_ms"), (int, float)))
    out = {"via": rows[0].get("via", "api"), "cli_version": rows[0].get("cli"), "model": rows[0]["model"], "effort": rows[0].get("effort"),
           "calls": len(rows), "in_tokens": sum(r["in"] for r in rows), "out_tokens": sum(r["out"] for r in rows),
           "cache_read_tokens": sum(r.get("cache_read", 0) for r in rows), "cache_write_tokens": sum(r.get("cache_write", 0) for r in rows),
           "usd_equivalent": round(sum(r["usd"] for r in rows), 4), "call_ms_p50": ms[len(ms) // 2],
           "call_ms_p95": ms[min(len(ms) - 1, int(len(ms) * 0.95))],
           "stop_reasons": {str(k): sum(1 for r in rows if r["stop"] == k) for k in {r["stop"] for r in rows}},
           "by_job": by_job}
    if api:
        out["model_ms_p50"], out["model_ms_p95"] = api[len(api) // 2], api[min(len(api) - 1, int(len(api) * 0.95))]
    out["trimmed_diag_fields"] = trimmed   # 진단 칸(missing·problem)을 길이 제한까지 자른 횟수
    return out


# ------------------------------------------------------------------ 스키마
def prepare_schema(schema):
    """지원하지 않는 제약을 뺀 복사본. enum·required·additionalProperties는 그대로 둔다."""
    if isinstance(schema, dict):
        return {k: prepare_schema(v) for k, v in schema.items() if k not in UNSUPPORTED}
    if isinstance(schema, list):
        return [prepare_schema(x) for x in schema]
    return schema


DIAG_KEYS = ("missing", "problem")   # 판정 이유를 적는 진단 칸 — 결정(true/false)에는 쓰이지 않고 기록용이다


def trim_diag(data, schema) -> tuple:
    """진단 칸(missing·problem)이 길이 제한보다 길면 제한까지 자른다. 로컬에서는 문법이 쓰는 순간에 길이를 막아 주던 것을 같은 효과로 맞춘다.
    답으로 나가는 글(answer·lead·texts …)은 자르지 않는다 — 잘린 문장이 나가면 안 되므로 길이 위반은 그대로 실패로 센다. (바뀐 복사본, 자른 개수)"""
    if not (isinstance(data, dict) and isinstance(schema, dict)):
        return data, 0
    props, n, out = schema.get("properties", {}), 0, dict(data)
    for k in DIAG_KEYS:
        lim = (props.get(k) or {}).get("maxLength")
        if isinstance(out.get(k), str) and isinstance(lim, int) and len(out[k]) > lim:
            out[k], n = out[k][:lim], n + 1
    return out, n


def trim_queries(data, schema) -> tuple:
    """검색어(search_queries)가 스키마의 개수·길이 제한을 넘으면 맞춘다: 길이를 넘는 항목은 빼고, 남은 것이 개수 제한을 넘으면 앞에서부터 남긴다.
    내부 검색에만 쓰는 말이라 화면에 나가지 않는다 — 한 항목 때문에 분류 응답 전체를 버리지 않는다(jobs.validate_route_v2가 하던 정리를 검사 앞으로 당긴 것).
    문자열이 아닌 항목은 손대지 않는다(그 뒤 검사가 판단). (바뀐 복사본, 고친 개수)"""
    if not (isinstance(data, dict) and isinstance(schema, dict)):
        return data, 0
    spec = (schema.get("properties") or {}).get("search_queries") or {}
    lim_n, lim_len = spec.get("maxItems"), (spec.get("items") or {}).get("maxLength")
    qs = data.get("search_queries")
    if not isinstance(qs, list):
        return data, 0
    kept = [q for q in qs if not (isinstance(q, str) and isinstance(lim_len, int) and len(q) > lim_len)]
    if isinstance(lim_n, int):
        kept = kept[:lim_n]
    return ({**data, "search_queries": kept}, 1) if kept != qs else (data, 0)


def validate_constraints(data, schema, path: str = "$") -> str | None:
    """원래 스키마의 제약을 받은 값에 다시 건다. 첫 위반의 설명, 없으면 None."""
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if "enum" in schema and data not in schema["enum"]:
        return f"{path}: enum 밖의 값"
    if t == "object" and isinstance(data, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in data:
                return f"{path}.{k}: 필수 칸 없음"
        for k, v in data.items():
            if k in props:
                bad = validate_constraints(v, props[k], f"{path}.{k}")
                if bad:
                    return bad
            elif schema.get("additionalProperties") is False:
                return f"{path}.{k}: 모르는 칸"
    elif t == "array" and isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            return f"{path}: 항목 {len(data)}개 < {schema['minItems']}"
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            return f"{path}: 항목 {len(data)}개 > {schema['maxItems']}"
        for i, x in enumerate(data):
            bad = validate_constraints(x, schema.get("items", {}), f"{path}[{i}]")
            if bad:
                return bad
    elif t == "string" and isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            return f"{path}: 글자 {len(data)} < {schema['minLength']}"
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            return f"{path}: 글자 {len(data)} > {schema['maxLength']}"
    elif t == "boolean" and not isinstance(data, bool):
        return f"{path}: 불리언 아님"
    return None


# ------------------------------------------------------------------ 호출
def _client(s: Settings, read: float):
    if _injected is not None:
        return _injected
    key = (round(read, 1), s.connect_s)
    with _lock:
        c = _real.get(key)
        if c is None:
            try:
                import anthropic  # 지연 import — 패키지가 없어도 앱은 그대로 돈다
            except ImportError as e:
                raise LlmUnavailable("anthropic 패키지 없음") from e
            c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=2,
                                    timeout=anthropic.Timeout(read, connect=max(s.connect_s, 5.0)))
            _real[key] = c
        return c


def chat_json_claude(messages: list[dict], schema: dict, name: str, max_tokens: int = 400, s: Settings | None = None,
                     grammar: str | None = None) -> dict:
    """`client.chat_json`과 같은 서명·같은 결과. grammar는 쓰지 않는다(코드 검사가 대신 막는다).
    앱 스위치 요청(s.claude_app, 2026-10-15)이면 외부 호출 실패를 요청 단위로 남기고, 재료를 정하는 단계(route·select·verify)의 실패는
    ExternalLlmFailure로 올려 앱 입구가 오류로 끝내게 한다(최종기획서 4.3절). 그 밖의 단계는 예전처럼 LlmUnavailable을 던져 부른 쪽의 폴백이 쓴다.
    재료 단계에서는 형식 오류(LlmBadOutput)도 실패로 센다 — 안 그러면 jobs.py가 규칙 답으로 조용히 돌아가 "외부 LLM이 답함"이라는 표시가 거짓이 된다."""
    s = s or settings()
    if s.claude_app:
        EXT.note_call()   # 보내려고 한 횟수(실패 포함) — 응답의 llm.calls
    try:
        return _chat_json_claude(messages, schema, name, max_tokens, s, grammar)
    except (LlmUnavailable, LlmBadOutput) as e:
        if s.claude_app:
            EXT.note_failure(name, str(e))
            if name in EXT.MATERIAL_JOBS:
                raise EXT.ExternalLlmFailure(name, str(e)) from e
        raise


def _chat_json_claude(messages: list[dict], schema: dict, name: str, max_tokens: int, s: Settings, grammar: str | None) -> dict:
    if name in (PURE_ANSWER_JOB, CONTINUE_JOB, SCREEN_SUMMARY_JOB) and s.claude_app and s.pure_model:   # PURE_MODEL(2026-10-19): 이 호출만 다른 모델. 화면 요약도 같다. 설정 복사본을 바꿔 쓰므로 잠금·--model·기록·모델 불일치 검사가 모두 같은 값을 본다. 노력은 그대로
        s = dataclasses.replace(s, claude_model=s.pure_model)
    bad = gate_problem(s)
    if bad:
        raise LlmUnavailable(bad)
    if _down_until > time.monotonic():
        raise LlmUnavailable("차단기: 최근 연결 실패·시간 초과·한도 도달")
    if not s.claude_app:   # 비용 상한은 평가 경로에만 건다. 앱 스위치는 사용 상한 없음(사용자 결정 2026-10-15)
        ledger = Path(os.environ["MOM_USAGE_LEDGER"])
        with _lock:
            if _spent(ledger) >= s.claude_cost_cap_usd:
                raise LlmUnavailable(f"비용 상한 ${s.claude_cost_cap_usd:g}에 닿음")
    read = s.read_s
    d = DL.current()
    if d is not None:
        t = d.timeout_for(s.read_s)
        if t is None:
            raise LlmUnavailable("시간 예산 부족")
        read = t
    messages, _ = OG.scrub_messages(messages)   # NFR-SEC-08: 사람 이름·사용자 ID·사원 번호·계정 정보는 밖으로 나가기 직전에 가린다 (외부 호출은 모두 여기를 지난다)
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    out = (_call_cli if s.claude_via == "cli" else _call_api)(s, messages, system, schema, name, max_tokens, read)
    if not isinstance(out, dict):
        raise LlmBadOutput("JSON 객체 아님")
    out, n_trim = trim_diag(out, schema)
    if n_trim:   # 자른 횟수는 따로 센다(호출 기록과 별개 줄 — 합계는 ledger_summary의 trimmed_diag_fields)
        _write_row({"kind": "trim", "t": datetime.now().isoformat(timespec="seconds"), "job": name, "n": n_trim}, 0.0)
    out, _ = trim_queries(out, schema)   # 검색어는 기록하지 않는다(위 trim 줄은 진단 칸 합계라 섞이지 않게)
    viol = validate_constraints(out, schema)
    if viol:
        raise LlmBadOutput(f"스키마 제약 위반: {viol}")
    return out


def _call_api(s: Settings, messages: list[dict], system: str, schema: dict, name: str, max_tokens: int, read: float):
    global _down_until, _timeouts
    rest = [m for m in messages if m["role"] != "system"]
    kw = {"model": s.claude_model, "max_tokens": max(max_tokens, MIN_MAX_TOKENS), "messages": rest,
          "output_config": {"format": {"type": "json_schema", "schema": prepare_schema(schema)}, "effort": s.claude_effort}}
    if system:
        kw["system"] = system
    t0 = time.monotonic()
    try:
        resp = _client(s, read).messages.create(**kw)
    except LlmUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 — SDK 예외를 이름·상태 코드로 나눈다(패키지가 없어도 시험할 수 있게)
        kind, code = type(e).__name__, getattr(e, "status_code", None)
        if kind == "APITimeoutError":
            _timeouts += 1
            if _timeouts >= TIMEOUT_TRIPS:
                _down_until, _timeouts = time.monotonic() + BREAK_S, 0
            raise LlmUnavailable("응답 시간 초과") from e
        if kind == "APIConnectionError":
            _down_until = time.monotonic() + BREAK_S
            raise LlmUnavailable("연결 실패") from e
        if kind == "RateLimitError" or code == 429:
            raise LlmUnavailable("속도 제한 429") from e
        if kind in ("AuthenticationError", "PermissionDeniedError") or code in (401, 403):
            _down_until = time.monotonic() + 600
            raise LlmUnavailable(f"인증·권한 오류 {code}") from e
        if kind == "BadRequestError" or code == 400:   # 요청 모양 문제 — 점수를 읽기 전에 고쳐야 하는 오류다
            raise LlmBadOutput(f"요청 거절 400: {str(getattr(e, 'message', e))[:80]}") from e
        if code is not None and code >= 500:
            raise LlmUnavailable(f"HTTP {code}") from e
        raise LlmUnavailable(kind) from e
    _timeouts = 0
    ms = int((time.monotonic() - t0) * 1000)
    _record_api(s, name, resp, ms)
    stop = getattr(resp, "stop_reason", None)
    if stop == "refusal":
        raise LlmBadOutput("거절(refusal)")
    if stop == "max_tokens":
        raise LlmBadOutput("길이 초과로 잘림")
    text = next((b.text for b in (resp.content or []) if getattr(b, "type", "") == "text"), "")
    try:
        return json.loads(text or "")
    except json.JSONDecodeError as e:
        raise LlmBadOutput("JSON 아님") from e


def _call_cli(s: Settings, messages: list[dict], system: str, schema: dict, name: str, max_tokens: int, read: float):
    """`claude -p` 한 번. 프로세스가 죽거나 한도에 닿으면 LlmUnavailable, 결과를 못 쓰면 LlmBadOutput. 요청 모델과 다른 모델이 답했으면 실패로 센다."""
    global _down_until, _timeouts, _limit_hits
    binary = CLI.find_bin() or Path("claude")   # 실행 파일이 없으면 gate_problem이 이미 막았다(시험의 가짜 실행기만 여기까지 온다)
    cmd = CLI.build_cmd(binary, s.claude_model, s.claude_effort, system, prepare_schema(schema))
    run = _runner or CLI.run
    t0 = time.monotonic()
    try:
        with _proc_slot(s, read):   # 동시 claude 프로세스 상한 (LlmUnavailable은 아래 except에 안 잡히고 그대로 올라간다)
            r = run(cmd, CLI.user_text(messages), read)
    except subprocess.TimeoutExpired as e:
        _timeouts += 1
        if _timeouts >= TIMEOUT_TRIPS:
            _down_until, _timeouts = time.monotonic() + BREAK_S, 0
        raise LlmUnavailable("응답 시간 초과") from e
    except OSError as e:
        _down_until = time.monotonic() + BREAK_S
        raise LlmUnavailable(f"claude 실행 실패: {type(e).__name__}") from e
    _timeouts = 0
    ms = int((time.monotonic() - t0) * 1000)
    try:
        d = CLI.parse_result(r.stdout)
    except ValueError:
        d = None
    err_text = ""
    if d is None or d.get("is_error") or r.returncode != 0:
        err_text = " ".join(str(x) for x in ((d or {}).get("result") if d else None, (d or {}).get("subtype") if d else None, r.stderr, r.stdout) if x)[:600]
        if CLI.LIMIT_RE.search(err_text):
            _limit_hits += 1
            if _limit_hits >= LIMIT_TRIPS:
                _down_until = time.monotonic() + 3600   # 이 프로세스에서는 더 부르지 않는다 — 러너가 이 오류를 보고 멈춘다
            raise LlmUnavailable(f"사용 한도·속도 제한 ({_limit_hits}/{LIMIT_TRIPS})")
        if d is None:
            raise LlmBadOutput(f"CLI 출력을 읽지 못함 (종료 코드 {r.returncode}): {CLI.safe_tail(r.stderr or r.stdout)}")
        raise LlmUnavailable(f"CLI 오류 (종료 코드 {r.returncode}): {CLI.safe_tail(err_text)}")
    _limit_hits = 0
    version = CLI.cli_version(binary) if _runner is None else "시험"
    _record_cli(s, name, d, ms, version)
    models = CLI.usage_of(d)["models"]
    if models and not any(m == s.claude_model or m.startswith(s.claude_model + "[") for m in models):
        raise LlmBadOutput(f"요청 모델과 다른 모델이 답함: {', '.join(models)[:80]}")
    try:
        return CLI.payload_of(d)
    except ValueError as e:
        raise LlmBadOutput(f"구조화 결과를 읽지 못함: {e}") from e
