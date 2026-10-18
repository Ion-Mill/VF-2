"""보내기 직전 거르기 — 외부 LLM(Claude)으로 나가는 글에서 사람 이름·사용자 ID·사원 번호·계정 정보를 가린다.

요구사항 NFR-SEC-08 (2026-10-17 확정: 외부로 보내도 되는 것은 질문·사내 문서 조각·가상 운영 값, 보내지 않는 것은 사람 이름·사원 번호·계정 정보).
외부 호출은 `llm/claude_client._chat_json_claude` 한 곳을 지나므로 거기서 `scrub_messages`를 부르면 `/chat`과 새 문장 입구가 모두 덮인다.

무엇을 가리나
  · 사용자 ID — `생성기/masters/app_user.csv`의 user_id (U01 …). 목록을 못 읽으면 `U\\d{2}` 꼴 전부.
  · 사람 이름 — 같은 파일의 user_name. 단, 사내 문서 조각에 이미 나오는 말(예: 직무명 "공장 관리자")은 사람 이름이 아니라서 가리지 않는다.
  · 사원 번호 — "사원번호/사번/employee no" 라벨이 붙은 번호.
  · 계정 정보 — 토큰(JWT·Bearer·sk-…), 접속 주소(postgres://…), "비밀번호/token/api_key: 값" 꼴, 그리고 이 서버 환경의 비밀값 자체(서비스 키 등).
돌려주는 것은 가린 글과 "무엇을 몇 번"(종류별 횟수)뿐이다. 가린 원문은 어디에도 남기지 않는다(로그 포함).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import threading
from pathlib import Path

from backend import config as C

log = logging.getLogger("assistant")

USER_FILE: Path = C.SIM_MASTERS / "app_user.csv"
MASK = {"person": "[사람]", "empno": "[사번]", "account": "[계정정보]"}
MIN_SECRET_LEN = 8
_SECRET_ENV = re.compile(r"(KEY|SECRET|PASSWORD|PASSWD|TOKEN|DATABASE_URL|_DSN)", re.I)

_EMPNO = re.compile(r"(?:사원\s*번호|사번|employee\s*(?:no\.?|number|id))\s*[:：#]?\s*[A-Za-z0-9][A-Za-z0-9-]{2,}", re.I)
_ACCOUNT = [
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"),                      # JWT
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),                                                      # API 키 꼴
    re.compile(r"\b(?:postgres(?:ql)?|mysql|redis|mongodb)(?:\+\w+)?://\S+", re.I),              # 접속 주소
    re.compile(r"(?:password|passwd|pwd|secret|token|api[_-]?key|비밀번호|비밀값|토큰)\s*[:=：]\s*\S+", re.I),
]
_GENERIC_ID = re.compile(r"(?<![A-Za-z0-9_])U\d{2}(?![A-Za-z0-9_])")


class OutboundBlocked(Exception):
    """재료에 가릴 것이 들어 있어 아예 보내지 않는다 — 부른 쪽은 지금의 틀 문장을 그대로 쓴다."""

    def __init__(self, kinds: dict[str, int]):
        super().__init__("보내기 전 검사에 걸림: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
        self.kinds = kinds


_lock = threading.Lock()
_UNSET = object()
_cache: dict = {"stamp": _UNSET, "ids": (), "names": ()}


def _corpus_text() -> str:
    """사내 문서 조각 전체 글 — 여기 이미 나오는 말은 사람 이름으로 보지 않는다."""
    try:
        from backend.rag.chunker import load_corpus
        return "\n".join(f"{getattr(c, 'title', '')}\n{c.text}" for c in load_corpus())
    except Exception:  # noqa: BLE001 — 문서를 못 읽어도 거르기는 멈추지 않는다(더 많이 가리는 쪽으로)
        return ""


def _load_users() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        with USER_FILE.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        log.warning("거르기: 사용자 목록을 못 읽음 — U00 꼴 ID만 가린다")
        return (), ()
    ids = tuple(r["user_id"].strip() for r in rows if r.get("user_id", "").strip())
    corpus = _corpus_text()
    names = sorted({r["user_name"].strip() for r in rows if r.get("user_name", "").strip() and r["user_name"].strip() not in corpus},
                   key=len, reverse=True)       # 긴 이름부터 가려야 짧은 이름이 긴 이름 조각을 먼저 잘라 내지 않는다
    return ids, tuple(names)


def _users() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        stamp = USER_FILE.stat().st_mtime_ns
    except OSError:
        stamp = None
    with _lock:
        if _cache["stamp"] != stamp:        # 처음이거나 파일이 바뀌었을 때만 다시 읽는다
            _cache["ids"], _cache["names"] = _load_users()
            _cache["stamp"] = stamp
        return _cache["ids"], _cache["names"]


def reset_cache() -> None:
    """시험용: 사용자 목록을 다시 읽게 한다."""
    with _lock:
        _cache.update(stamp=_UNSET, ids=(), names=())


def _secret_values() -> list[str]:
    """이 서버 환경(.env 포함)의 비밀값 글자 그대로 — 어디에 섞여 있어도 가린다. 값 자체는 로그에 쓰지 않는다."""
    try:
        env = {**C._dotenv(), **os.environ}
    except Exception:  # noqa: BLE001
        env = dict(os.environ)
    vals = {v.strip() for k, v in env.items() if _SECRET_ENV.search(k) and isinstance(v, str) and len(v.strip()) >= MIN_SECRET_LEN}
    return sorted(vals, key=len, reverse=True)


def scrub_text(text: str) -> tuple[str, dict[str, int]]:
    """글 한 덩어리에서 가릴 것을 가린다. (가린 글, {종류: 횟수}) — 종류는 person·empno·account."""
    hits: dict[str, int] = {}
    if not isinstance(text, str) or not text:
        return text, hits

    def sub(pat: re.Pattern, kind: str, s: str) -> str:
        s, n = pat.subn(MASK[kind], s)
        if n:
            hits[kind] = hits.get(kind, 0) + n
        return s

    for v in _secret_values():                       # 환경의 비밀값 글자 그대로 (가장 먼저 — 다른 규칙이 일부만 잘라 내지 않게)
        if v in text:
            hits["account"] = hits.get("account", 0) + text.count(v)
            text = text.replace(v, MASK["account"])
    for pat in _ACCOUNT:
        text = sub(pat, "account", text)
    text = sub(_EMPNO, "empno", text)
    ids, names = _users()
    for name in names:
        text = sub(re.compile(re.escape(name) + r"(?!\d)"), "person", text)
    if ids:
        for uid in ids:
            text = sub(re.compile(r"(?<![A-Za-z0-9_])" + re.escape(uid) + r"(?![A-Za-z0-9_])"), "person", text)
    else:
        text = sub(_GENERIC_ID, "person", text)
    return text, hits


def scrub_messages(messages: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """LLM 요청 메시지(role·content) 전체를 거른 새 목록과 종류별 횟수. 원본은 바꾸지 않는다."""
    out, total = [], {}
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            c, h = scrub_text(c)
            for k, n in h.items():
                total[k] = total.get(k, 0) + n
            out.append({**m, "content": c})
        else:
            out.append(dict(m))
    if total:
        log.info("외부로 보내기 전 가림: %s", ", ".join(f"{k} {n}" for k, n in sorted(total.items())))   # 종류와 횟수만 — 원문 없음
    return out, total


def assert_clean(material) -> None:
    """재료(dict·list·글)에 가릴 것이 하나라도 있으면 OutboundBlocked — 새 문장 입구는 가려서 보내지 않고 아예 보내지 않는다."""
    text = material if isinstance(material, str) else json.dumps(material, ensure_ascii=False, default=str)
    _, hits = scrub_text(text)
    if hits:
        raise OutboundBlocked(hits)
