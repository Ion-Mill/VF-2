"""로컬 LLM 서버(llama.cpp llama-server, OpenAI 호환) 연결 (NFR-SEC-08, NFR-AIQ-09).

- 주소는 루프백만 쓴다(config.settings가 막는다). 새 패키지 없이 httpx로 부른다.
- 요청마다 생각(thinking) 모드를 끄고(`enable_thinking: false`) JSON 스키마로 출력 칸을 강제한다.
  Qwen3.5는 생각 모드가 기본으로 켜져 있고, 켜진 채로는 llama.cpp가 JSON 강제를 무시한다(#20345).
  예외 (2026-10-15 사용자 결정): 비서 창 [Qwen 깊게 생각] 버튼을 누른 요청은 **그 요청만** 문법 없는 JSON 스키마 호출에서 생각을 켠다
  (예산 6,000토큰, `thinking_budget_tokens` — 무제한은 끝나지 않아 예산을 건다, `think.py`). 새 글 쓰기(문법 길)는 켜지 않는다.
- 스키마에 `$ref`를 쓰지 않는다(#21228: 강제가 조용히 꺼짐).
- 서버가 죽거나 연속 2번 시간 초과면 30초 동안 부르지 않는다(차단기). 실패는 예외로 알리고, 부른 쪽이 기본 문장을 쓴다.
- 한 답 전체의 시간 예산(deadline.py) 안에서만 기다린다. 남은 시간이 모자라면 부르지 않는다 (2026-10-10).
- 연결 유지는 서버보다 짧게 둔다. llama-server(cpp-httplib 0.60.0)는 쉬는 연결을 5초 뒤 닫는데(`Keep-Alive: timeout=5`,
  2026-10-10 실측 5.03초), httpx 기본 연결 유지도 5초라 막 닫힌 연결에 요청을 보내면 RemoteProtocolError가 났다
  (2026-10-10 23:52 시험용 복사본 평가가 이 오류로 멈춤, encode/httpx discussion #2056). 요청이 서버에 닿지 않은 경우라
  새 연결로 한 번만 다시 보낸다. 그 밖의 연결 오류도 앱을 멈추지 않고 실패로 알린다(부른 쪽이 기본 문장을 씀).
"""
from __future__ import annotations

import json
import threading
import time

import httpx

from backend.config import Settings, settings
from backend.llm import deadline as DL
from backend.llm import external as EXT
from backend.llm import think as THINK
from backend.services import steplog as SL

BREAK_S = 30.0
_lock = threading.Lock()
_clients: dict[tuple, httpx.Client] = {}
_down_until: dict[str, float] = {}
_timeouts: dict[str, int] = {}   # 연속 시간 초과 횟수
TIMEOUT_TRIPS = 2
KEEPALIVE_S = 2.0   # 서버(5초)보다 짧게 — 서버가 닫기 전에 클라이언트가 먼저 버린다
_transport: httpx.BaseTransport | None = None  # 시험에서 가짜 서버를 끼운다


class LlmUnavailable(RuntimeError):
    """서버가 없거나 응답하지 않음."""


class LlmBadOutput(RuntimeError):
    """응답은 왔지만 쓸 수 없음 (길이 초과로 잘림, 생각 글 섞임, 형식 깨짐)."""


def use_transport(t: httpx.BaseTransport | None) -> None:
    """시험용: 실제 서버 대신 httpx.MockTransport를 쓴다."""
    global _transport
    with _lock:
        _transport = t
        for c in _clients.values():
            c.close()
        _clients.clear()
        _down_until.clear()
        _timeouts.clear()


def _client(s: Settings) -> httpx.Client:
    key = (s.llm_url, s.connect_s, s.read_s, id(_transport))
    with _lock:
        c = _clients.get(key)
        if c is None:
            c = httpx.Client(base_url=s.llm_url, transport=_transport, trust_env=False,  # 프록시 환경 변수를 타지 않는다
                             timeout=httpx.Timeout(s.read_s, connect=s.connect_s),
                             limits=httpx.Limits(keepalive_expiry=KEEPALIVE_S))
            _clients[key] = c
        return c


def _headers(s: Settings) -> dict:
    return {"Authorization": f"Bearer {s.api_key}"} if s.api_key else {}


def chat_json(messages: list[dict], schema: dict, name: str, max_tokens: int = 400, s: Settings | None = None,
              grammar: str | None = None) -> dict:
    """JSON 칸으로만 답을 받는다. 돌려주는 값은 파싱한 dict. (모든 LLM 호출의 단일 입구 — 로컬 Qwen·외부 Claude 모두 여기를 지난다.)
    grammar (10차 DOC_WRITE, 2026-10-13): GBNF 문법을 주면 json_schema 대신 그 문법으로 출력을 묶는다 — b11491은 json_schema의
    string "pattern"을 지키지 않았고(글자 그대로 "MTBF"가 나옴), GBNF는 지켰다(같은 날 시험). 출력은 여전히 JSON 객체여야 한다.
    단계별 로그 (STEP_LOG, 2026-10-15): 기록 중인 요청이면 이 호출의 작업 이름·걸린 시간·성공/실패·까닭·받은 JSON을 남긴다. 읽기만 한다 —
    예외는 그대로 다시 던지고(LlmUnavailable·LlmBadOutput·ExternalLlmFailure …), 기록하지 않는 요청은 아래 본문을 곧바로 부른다."""
    if not SL.on():
        return _chat_json_dispatch(messages, schema, name, max_tokens, s, grammar)
    return _chat_json_logged(messages, schema, name, max_tokens, s, grammar)


def _chat_json_logged(messages: list[dict], schema: dict, name: str, max_tokens: int, s: Settings | None, grammar: str | None) -> dict:
    """STEP_LOG가 켜진 요청의 호출 한 번 — 본문(_chat_json_dispatch)을 감싸 기록만 더한다. 기록 때문에 호출이 달라지거나 막히지 않는다."""
    t_ms, t0 = SL.now_ms(), time.perf_counter()
    try:
        s_ = s or settings()
        provider = "외부 Claude" if s_.llm_provider == "claude" else "로컬 Qwen"
        think = s_.think_budget if (s_.llm_provider != "claude" and s_.think_budget > 0 and not grammar) else 0
        sent = sum(len(str(m.get("content", ""))) for m in messages)
    except Exception:
        provider, think, sent = "알 수 없음", 0, 0
    kind = "재료" if name in EXT.MATERIAL_JOBS else "다듬기"
    try:
        out = _chat_json_dispatch(messages, schema, name, max_tokens, s, grammar)
    except BaseException as e:
        SL.llm_call(name, kind=kind, provider=provider, t_ms=t_ms, ms=int((time.perf_counter() - t0) * 1000), ok=False,
                    reason=getattr(e, "reason", None) or str(e), error=type(e).__name__, sent_chars=sent, grammar=bool(grammar), think=think)
        raise
    SL.llm_call(name, kind=kind, provider=provider, t_ms=t_ms, ms=int((time.perf_counter() - t0) * 1000), ok=True,
                sent_chars=sent, received=out, grammar=bool(grammar), think=think)
    return out


def _chat_json_dispatch(messages: list[dict], schema: dict, name: str, max_tokens: int, s: Settings | None, grammar: str | None) -> dict:
    s = s or settings()
    if s.llm_provider == "claude":  # 비교 실험 전용 (2026-10-14) — local(기본)일 때 아래 요청 본문은 한 글자도 바뀌지 않는다
        from backend.llm import claude_client
        return claude_client.chat_json_claude(messages, schema, name, max_tokens, s, grammar)
    # Qwen "깊게 생각" 버튼 (2026-10-15): 이 요청이 켰고(s.think_budget) 문법 없는 JSON 스키마 호출일 때만 생각을 켠다. 문법 길(새 글 쓰기)은 켜면
    # 답이 생각 칸으로 들어가 본문이 비므로(llama.cpp #20345) 켜지 않는다. 꺼져 있으면(기본) 아래 요청 본문은 예전과 한 글자도 다르지 않다.
    think = s.think_budget if (s.think_budget > 0 and not grammar) else 0
    if not think:
        return _chat_json_local(messages, schema, name, max_tokens, s, grammar, 0)
    THINK.note_call()
    try:
        return _chat_json_local(messages, schema, name, max_tokens, s, grammar, think)
    except (LlmUnavailable, LlmBadOutput):
        THINK.note_failure()   # 그 단계는 부른 쪽의 기본 동작(원문 줄·기본 문장)으로 돌아간다 — 응답 think.failures로 사실대로 밝힌다
        raise


def _chat_json_local(messages: list[dict], schema: dict, name: str, max_tokens: int, s: Settings, grammar: str | None, think: int) -> dict:
    """로컬 llama-server 호출 한 번. think > 0이면 생각을 켜고(예산 think토큰) 생각 글은 버린다."""
    if _down_until.get(s.llm_url, 0) > time.monotonic():
        raise LlmUnavailable("차단기: 최근 연결 실패·시간 초과")
    read = s.read_s
    d = DL.current()
    if d is not None:  # 한 답 전체의 남은 시간 안에서만 기다린다
        t = d.timeout_for(s.read_s)
        if t is None:
            raise LlmUnavailable("시간 예산 부족")
        read = t
    body = {
        "model": s.llm_model, "messages": messages, "max_tokens": max_tokens,
        "temperature": 0, "top_p": 1, "seed": 7, "presence_penalty": 0,  # 숫자·번호를 그대로 옮기도록 무작위·반복 벌점 없음
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if grammar:
        body.pop("response_format")
        body["grammar"] = grammar
    if think:   # 요청 칸 이름은 2026-10-15 사전 확인으로 우리 판(b11491)에서 받아들여짐을 확인했다(`thinking_budget_tokens`). max_tokens는 생각 예산 + 답 JSON
        body["chat_template_kwargs"] = {"enable_thinking": True}
        body["thinking_budget_tokens"] = think
        body["max_tokens"] = max_tokens + think
    if not s.cache_prompt:  # 앞부분 재사용을 끈다 — llama.cpp 문서: 재사용은 결과를 비트 단위로 같게 보장하지 않는다 (흔들림 확인용, 2026-10-10)
        body["cache_prompt"] = False
    for attempt in (1, 2):
        try:
            r = _client(s).post("/v1/chat/completions", json=body, headers=_headers(s),
                                timeout=httpx.Timeout(read, connect=s.connect_s))
            break
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            _down_until[s.llm_url] = time.monotonic() + BREAK_S
            raise LlmUnavailable(type(e).__name__) from e
        except httpx.TimeoutException as e:
            if read >= s.read_s and not think:  # 예산 때문에 줄인 기다림은 서버 탓으로 세지 않는다. 깊은 생각의 긴 기다림도 차단기에 세지 않는다(다른 사람의 질문까지 막지 않게)
                _timeouts[s.llm_url] = _timeouts.get(s.llm_url, 0) + 1
                if _timeouts[s.llm_url] >= TIMEOUT_TRIPS:
                    _down_until[s.llm_url] = time.monotonic() + BREAK_S
                    _timeouts[s.llm_url] = 0
            raise LlmUnavailable("응답 시간 초과") from e
        except httpx.RemoteProtocolError as e:
            # 서버가 막 닫은 연결을 다시 쓴 경우 — 요청이 서버에 닿지 않았다. 새 연결로 한 번만 다시 보낸다(남은 시간 안에서)
            if attempt == 2:
                raise LlmUnavailable("연결 끊김") from e
            if d is not None:
                t = d.timeout_for(s.read_s)
                if t is None:
                    raise LlmUnavailable("시간 예산 부족") from e
                read = t
        except httpx.TransportError as e:  # 그 밖의 연결 오류도 앱을 멈추지 않는다 (규칙 3.4: AI 서버 오류는 예전 동작으로)
            raise LlmUnavailable(type(e).__name__) from e
    _timeouts[s.llm_url] = 0
    if r.status_code != 200:
        raise LlmUnavailable(f"HTTP {r.status_code}")
    try:
        choice = r.json()["choices"][0]
        msg = choice["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LlmBadOutput("응답 모양이 다름") from e
    if choice.get("finish_reason") == "length":
        raise LlmBadOutput("길이 초과로 잘림")
    if think:   # 생각을 켠 요청: 생각 글(reasoning_content)은 있어도 되고 버린다(저장·표시하지 않는다). 본문에 생각 꼬리표가 섞이면 거부
        if "<think>" in (msg.get("content") or ""):
            raise LlmBadOutput("생각 글이 섞임")
    elif (msg.get("reasoning_content") or "").strip() or "<think>" in (msg.get("content") or ""):
        raise LlmBadOutput("생각 글이 섞임")
    try:
        out = json.loads(msg.get("content") or "")
    except json.JSONDecodeError as e:
        raise LlmBadOutput("JSON 아님") from e
    if not isinstance(out, dict):
        raise LlmBadOutput("JSON 객체 아님")
    return out


_probe_cache: dict[str, tuple[float, dict]] = {}


def probe(s: Settings | None = None) -> dict:
    """서버 상태 (화면 머리·/api/health용). 0.5초 안에 답이 없으면 꺼짐으로 본다. 10초 동안 기억한다."""
    s = s or settings()
    if not s.llm_enabled:
        return {"enabled": False, "alive": False, "model": s.llm_model_name, "reason": s.problem or "LLM_ENABLED=0 (기본 문장)"}
    if s.llm_provider == "claude":  # 서버에 /health가 없다 — 잠금·열쇠·기록 경로가 갖춰졌는지만 본다(실제 연결은 첫 호출에서 드러남)
        from backend.llm import claude_client
        why = claude_client.gate_problem(s)
        return {"enabled": True, "alive": why is None, "model": s.claude_model, "reason": why, "provider": "claude"}
    hit = _probe_cache.get(s.llm_url)
    if hit and time.monotonic() - hit[0] < 10:
        return hit[1]
    try:
        with httpx.Client(transport=_transport, trust_env=False, timeout=0.5) as c:
            r = c.get(f"{s.llm_url}/health", headers=_headers(s))
        alive = r.status_code == 200
        out = {"enabled": True, "alive": alive, "model": s.llm_model, "reason": None if alive else f"HTTP {r.status_code}"}
    except httpx.HTTPError as e:
        out = {"enabled": True, "alive": False, "model": s.llm_model, "reason": type(e).__name__}
    _probe_cache[s.llm_url] = (time.monotonic(), out)
    return out
