"""시연 서버용 문장 다듬기 도우미 — 비서 서비스(8100)의 `POST /compose/{kind}`를 부른다 (2026-10-17).

역할: 프로그램이 만든 '기본 문장' 줄을 비서(외부 Claude)에게 보내 읽기 쉽게 다듬은 줄을 받아 두었다가, 준비되면 화면 응답의 문장 칸에 바꿔 끼운다.
  · 호출은 5~20초 걸리므로 **요청을 처리하는 스레드(시연 서버의 S.lock 안)에서 기다리지 않는다.** `polished()`는 바로 돌아오고(준비 전이면 None),
    준비되지 않았으면 백그라운드 스레드가 비서를 부른다. 준비되면 다음 요청부터 다듬은 줄이 나간다. 그 사이 화면은 지금의 기본 문장을 그대로 본다.
  · 실패(비서 꺼짐·스위치 꺼짐·검사 탈락·시간 초과)는 기본 문장 그대로다. 몰래 다른 길로 가지 않고, 실패 뒤에는 잠깐 쉬었다 다시 해 본다(백오프).
  · 기본 꺼짐: 환경변수 MOM_LLM_COMPOSE=1일 때만 움직인다. 비서 서비스 쪽에도 자기 스위치 셋(ASSISTANT_PROVIDER=claude, EXTERNAL_LLM_APP=1, LLM_ENABLED=1)이 따로 있다.
  · 서비스 키는 환경변수 MOM_ASSISTANT_KEY, 없으면 assistant/.env의 같은 이름 한 줄만 읽는다. 값은 로그·응답 어디에도 쓰지 않는다.
  · 주소(MOM_ASSISTANT_URL, 기본 http://127.0.0.1:8100)는 이 PC(127.0.0.1·localhost)만 허용한다 — 서비스 키와 운영 글이 다른 곳으로 나가지 않게.
  · 시뮬레이터 '처음으로'(run_id가 바뀜) 때 받아 둔 것을 비우고, 늦게 도착한 결과는 run_id가 다르면 버린다.
표준 라이브러리만 쓴다 (시연 서버와 같은 가상환경).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                                   # 11_automotive
DEFAULT_URL = "http://127.0.0.1:8100"
HTTP_TIMEOUT_S = 130.0                                   # 비서의 시간 예산(120초)보다 조금 길게
MAX_PARALLEL = 2                                         # 보고서·작업지시서·브리핑·알림이 동시에 비서를 부르는 수
GUIDE_PARALLEL = 2                                       # 지침카드 두 칸(먼저 할 일·보전)은 위 자리와 따로. 보고서가 자리를 잡아도 같이 시작한다
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    """글을 마침표 뒤 공백 기준 문장 목록으로 쪼갠다 (화면 Briefing.tsx와 같은 기준)."""
    return [x for x in _SENT.split((text or "").strip()) if x]


class ComposeHttpError(Exception):
    def __init__(self, status: int | None, why: str):
        super().__init__(why)
        self.status, self.why = status, why


def _read_key() -> str:
    k = os.environ.get("MOM_ASSISTANT_KEY", "").strip()
    if k:
        return k
    env = ROOT / "assistant" / ".env"
    try:
        for line in env.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*MOM_ASSISTANT_KEY\s*=\s*(\S+)", line)
            if m:
                return m.group(1).strip("'\"")
    except OSError:
        pass
    return ""


def http_post(kind: str, lines: list[dict]) -> dict:
    """비서 서비스에 줄을 보내 다듬은 줄을 받는다. 실패는 ComposeHttpError(상태, 까닭) — 까닭에 키·글 내용은 넣지 않는다."""
    url = os.environ.get("MOM_ASSISTANT_URL", DEFAULT_URL).rstrip("/")
    if urlparse(url).hostname not in LOCAL_HOSTS:
        raise ComposeHttpError(None, "비서 주소가 이 PC가 아님")
    key = _read_key()
    if not key:
        raise ComposeHttpError(None, "서비스 키 없음")
    req = urllib.request.Request(f"{url}/compose/{kind}", data=json.dumps({"lines": lines}, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Service-Key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:        # noqa: S310 — 위에서 로컬 주소만 허용
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ComposeHttpError(e.code, f"HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ComposeHttpError(None, type(e).__name__) from None
    except ValueError as e:
        raise ComposeHttpError(None, "응답을 읽지 못함") from e


@dataclass
class Entry:
    hash: str
    state: str = "pending"                 # pending | ready | failed
    texts: list[str] = field(default_factory=list)
    fails: int = 0
    next_try: float = 0.0


class Composer:
    def __init__(self, run_id=lambda: 0, post=http_post, enabled: bool | None = None, now=time.monotonic):
        self._run, self._post, self._now = run_id, post, now
        self.enabled = (os.environ.get("MOM_LLM_COMPOSE", "") == "1") if enabled is None else enabled
        self._lock = threading.Lock()
        self._sem = threading.Semaphore(MAX_PARALLEL)
        self._guide_sem = threading.Semaphore(GUIDE_PARALLEL)
        self._e: dict[tuple, Entry] = {}
        self.threads: list[threading.Thread] = []      # 시험이 끝나기를 기다릴 때 쓴다

    @staticmethod
    def _hash(kind: str, texts: list[str], ids: list[str]) -> str:
        return hashlib.sha1(json.dumps([kind, ids, texts], ensure_ascii=False).encode("utf-8")).hexdigest()

    def clear(self) -> None:
        with self._lock:
            self._e.clear()

    def polished(self, kind: str, key: str, texts: list[str], ids: list[str] | None = None) -> list[str] | None:
        """texts(기본 문장 줄)에 대응하는 다듬은 줄. 준비돼 있으면 같은 개수의 줄, 아니면 None.
        준비돼 있지 않고 쉬는 중도 아니면 백그라운드로 비서를 부른다. 절대 기다리지 않는다."""
        if not self.enabled or not texts:
            return None
        ids = ids or [f"L{i + 1}" for i in range(len(texts))]
        h = self._hash(kind, texts, ids)
        k = (self._run(), kind, key)
        with self._lock:
            e = self._e.get(k)
            if e is not None and e.hash == h:
                if e.state == "ready":
                    return list(e.texts)
                if e.state == "pending" or self._now() < e.next_try:
                    return None
                e.state = "pending"                       # 쉬는 시간이 지났다 — 다시 해 본다
            else:
                self._e[k] = Entry(hash=h)                # 처음이거나 입력이 바뀜
            t = threading.Thread(target=self._work, args=(k, h, kind, texts, ids), daemon=True, name=f"compose-{kind}")
            self.threads.append(t)
            t.start()
        return None

    def _work(self, k: tuple, h: str, kind: str, texts: list[str], ids: list[str]) -> None:
        t0 = time.monotonic()
        out, why, status = None, "", None
        try:
            with (self._guide_sem if kind == "guide_card" else self._sem):
                res = self._post(kind, [{"id": i, "text": t} for i, t in zip(ids, texts)])
            got = [l["text"] for l in res["lines"]]
            if len(got) == len(texts) and all(isinstance(g, str) and g.strip() for g in got):
                out = got
            else:
                why = "응답 줄 수가 다름"
        except ComposeHttpError as e:
            why, status = e.why, e.status
        except Exception as e:  # noqa: BLE001 — 응답 모양이 틀려도 시연 서버는 계속 돈다
            why = f"{type(e).__name__}"
        ms = int((time.monotonic() - t0) * 1000)
        with self._lock:
            e = self._e.get(k)
            if e is None or e.hash != h or self._run() != k[0]:      # 처음으로 되돌렸거나 입력이 바뀜 — 늦게 온 결과는 버린다
                return
            if out is not None:
                e.state, e.texts = "ready", out
                print(f"[문장] {kind} {k[2]} 준비됨 ({ms}ms)")
            else:
                e.state, e.fails = "failed", e.fails + 1
                wait = 900.0 if status in (401, 404, 422) else min(30.0 * 2 ** (e.fails - 1), 300.0)
                e.next_try = self._now() + wait
                print(f"[문장] {kind} {k[2]} 실패: {why} — {int(wait)}초 뒤 다시 ({ms}ms)")

    def wait_idle(self, timeout: float = 5.0) -> None:
        """시험용: 백그라운드 호출이 끝나기를 기다린다."""
        for t in list(self.threads):
            t.join(timeout)
        self.threads[:] = [t for t in self.threads if t.is_alive()]

    def stats(self) -> dict:
        with self._lock:
            c = {"ready": 0, "pending": 0, "failed": 0}
            for e in self._e.values():
                c[e.state] += 1
        return {"enabled": self.enabled, **c}
