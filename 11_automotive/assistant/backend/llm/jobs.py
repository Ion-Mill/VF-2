"""LLM 작업 세 가지 (정해진 순서로 부르는 workflow — 모델이 스스로 도구를 고르는 에이전트가 아니다).

- 다듬기(phrase): 운영 답의 기본 문장을 읽기 쉽게. 숫자·번호·꼬리표는 양방향 검사(adapter.check_text).
- 고르기(select): 문서 답에서 후보 줄 번호만 고르고 앞머리 한 문장. 줄 글은 원문 그대로 옮긴다.
- 분류(route): 낱말 규칙이 못 알아들은 질문만 조회 종류·설비·기간 이름으로 분류. 날짜는 코드가 정한다.

점검 순서·안전 서식·주의 문구·관련 줄은 어느 작업에도 보내지 않는다. 실패하면 늘 기본 동작으로 돌아간다.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from pathlib import Path

from backend.config import settings
from backend.llm import numbers, prompts, schemas
from backend.llm.adapter import DENY, KO_NUM, check_text, tidy, tokens
from backend.llm.client import LlmBadOutput, LlmUnavailable, chat_json
from backend.rag.sanitize import FORBIDDEN
from backend.services import steplog as SL

MAX_PHRASE_CHARS = 1200   # 이보다 긴 기본 문장(행이 많은 조회)은 다듬지 않는다 — 빠뜨릴 위험이 크다 [제안]
MAX_SELECT_CHARS = 6000   # 고르기 후보 줄 총 글자 수 [제안]


def _trace(job: str) -> dict:
    return {"job": job, "used": False, "reason": None, "tries": 0, "ms": 0}


class PhraseAdapter:
    """adapter.write_answer에 끼우는 다듬기 어댑터."""

    def __init__(self):
        self.name = f"{settings().llm_label} 문장 ({settings().llm_model_name})"

    def write(self, facts: dict, feedback: str | None = None) -> str:
        draft = facts["draft_conclusion"]
        if len(draft) > MAX_PHRASE_CHARS:
            raise LlmBadOutput("기본 문장이 길어 다듬지 않음")
        out = chat_json(prompts.phrase(draft, feedback), schemas.phrase(len(draft)), "phrase",
                        max_tokens=min(2048, len(draft) * 2 + 200))
        return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------- 고르기 (문서 답)
def offer(chunks, line_fn) -> list[tuple[str, object, str]]:
    """후보 줄에 L1… 번호를 붙인다. 돌려주는 값 = [(번호, 조각, 줄 글)] (검색 순위·문서 순서 유지)."""
    out, size = [], 0
    for c in chunks:
        for text in line_fn(c):
            if size + len(text) > MAX_SELECT_CHARS:
                return out
            out.append((f"L{len(out) + 1}", c, text))
            size += len(text)
    return out


def validate_select(out: dict, offered: list[tuple[str, object, str]], check_lead: bool = True) -> tuple[dict | None, str | None]:
    """check_lead=False: 앞머리를 쓰지 않는 곳(SPLIT_Q의 2차 문지기)은 앞머리를 비우고 검사하지 않는다."""
    if not isinstance(out, dict) or set(out) != {"answerable", "line_ids", "lead"}:
        return None, "형식 오류"
    ids, lead = out["line_ids"], out["lead"] if check_lead else ""
    if out["answerable"] is not True:
        return None, "답할 줄 없음(answerable=false)"
    known = {i: (c, t) for i, c, t in offered}
    if not isinstance(ids, list) or not ids or len(ids) > 6 or len(set(ids)) != len(ids) or not set(ids) <= set(known):
        return None, "줄 번호 오류"
    if not isinstance(lead, str) or len(lead) > 160:
        return None, "앞머리 길이"
    if FORBIDDEN.search(lead) or "DOC-" in lead or "§" in lead:
        return None, "앞머리에 출처 표기"
    if KO_NUM.search(lead):
        return None, "한글 수사"
    order = [i for i, _, _ in offered if i in ids]  # 문서 순서로 옮긴다
    lines = [known[i][1] for i in order]
    lead = tidy(lead, " ".join(lines))
    if settings().num_match == "value":
        lead = numbers.tidy(lead, " ".join(lines))
    if DENY.search(lead) and not any(DENY.search(t) for t in lines):
        return None, "허락·지시 문구"
    if settings().num_match == "value":  # 값으로 비교: 단위는 그 줄에 있을 때만 붙일 수 있다 (numbers.py)
        extra = numbers.lead_unsupported(lead, lines)
    else:
        extra = sorted(tokens(lead) - tokens(" ".join(lines)))
    if extra:
        return None, "고른 줄에 없는 숫자·번호: " + ", ".join(extra[:5])
    chunks = []
    for i in order:
        c = known[i][0]
        if c not in chunks:
            chunks.append(c)
    # line_chunks (8차): 고른 줄마다 그 줄의 조각 — 줄 목록 칸의 줄마다 출처·같은 표 형제 줄 거르기에 쓴다 (예전 칸은 그대로)
    return {"lead": lead.strip(), "lines": lines, "chunks": chunks, "line_chunks": [known[i][0] for i in order]}, None


def _sl_select(strict: bool, offered, attempts: list, sel: dict | None, tr: dict) -> None:
    """STEP_LOG 4단계 "줄 고르기": LLM에게 보인 후보 줄(L번호·조각·앞 40자), 시도마다 LLM이 낸 값(answerable·line_ids·앞머리)과 코드 검사 결과,
    끝내 고른 줄 번호와 그 줄 전문. "어떤 줄 번호를 골랐나"를 기록으로 확인하려는 단계다. 읽기만 한다 — 부르는 쪽은 `if SL.on()`로 감싼다."""
    try:
        chosen = None
        if sel:
            passed = next((a.get("line_ids") for a in reversed(attempts) if a.get("검사") == "통과"), None) or []
            chosen = [i for i, _, _ in offered if i in set(passed)]   # 문서 순서
        SL.step("4 줄 고르기", 모드="엄격(2차 문지기)" if strict else "일반(1차 문지기)", 후보수=len(offered),
                후보=[{"L": i, "조각": c.chunk_id, "앞40자": SL.cut(t)} for i, c, t in offered],
                시도=attempts, 고른번호=chosen, 고른줄=list(sel["lines"]) if sel else None, 앞머리=(sel["lead"] or None) if sel else None,
                결과="성공" if sel else (tr.get("reason") or "실패"), ms=tr.get("ms"))
    except Exception:   # 기록 도우미의 실패가 답을 막지 않는다
        SL.note_error()


def select_lines(question: str, chunks, line_fn, head_fn, strict: bool = False) -> tuple[dict | None, dict]:
    """strict = 2차 문지기의 엄격한 고르기 (prompts.select_strict)."""
    tr, t0, s = _trace("select"), time.monotonic(), settings()
    offered = offer(chunks, line_fn)
    attempts: list = []   # STEP_LOG 4단계 기록용 (기록 중이 아니면 채우지 않는다)
    if not offered:
        tr["reason"] = "후보 줄 없음"
        if SL.on():
            _sl_select(strict, offered, attempts, None, tr)
        return None, tr
    blocks = []
    for i, c, t in offered:
        if not blocks or blocks[-1][0] != head_fn(c):
            blocks.append((head_fn(c), []))
        blocks[-1][1].append((i, t))
    feedback = None
    for _ in range(2):
        tr["tries"] += 1
        try:
            msgs = (prompts.select_strict(question, blocks, feedback) if strict
                    else prompts.select(question, blocks, feedback))
            out = chat_json(msgs, schemas.select([i for i, _, _ in offered]), "select", 300)
        except (LlmUnavailable, LlmBadOutput) as e:
            tr["reason"] = f"LLM 오류: {e}"
            if SL.on():
                attempts.append({"LLM": "호출 실패", "까닭": str(e)})
            break
        sel, reason = validate_select(out, offered, check_lead=not (strict and s.split_q))
        if SL.on():
            o = out if isinstance(out, dict) else {}
            attempts.append({"answerable": o.get("answerable"), "line_ids": o.get("line_ids"), "앞머리": o.get("lead"),
                             "검사": "통과" if sel else reason})
        if sel:
            tr.update(used=True, reason=None)
            tr["ms"] = int((time.monotonic() - t0) * 1000)
            if SL.on():
                _sl_select(strict, offered, attempts, sel, tr)
            return sel, tr
        tr["reason"], feedback = reason, reason
        if reason.startswith("답할 줄 없음") or time.monotonic() - t0 > s.budget_s - 5:
            break
    tr["ms"] = int((time.monotonic() - t0) * 1000)
    if SL.on():
        _sl_select(strict, offered, attempts, None, tr)
    return None, tr


# ---------------------------------------------------------------- 분류 (낱말 규칙이 못 알아들었을 때만)
def validate_route(out: dict) -> tuple[dict | None, str | None]:
    if not isinstance(out, dict) or set(out) != {"kind", "intents", "equipment", "period", "shift"}:
        return None, "형식 오류"
    if out["kind"] not in ("doc", "ops", "mixed", "none") or out["period"] not in schemas.PERIODS or out["shift"] not in ("none", "D", "N"):
        return None, "값 오류"
    if not set(out["intents"]) <= set(schemas.INTENTS) or not set(out["equipment"]) <= set(schemas.ROUTE["properties"]["equipment"]["items"]["enum"]):
        return None, "값 오류"
    if out["kind"] not in ("ops", "mixed") or not out["intents"]:
        return None, f"운영 조회 아님(kind={out['kind']})"
    return out, None


def route(question: str) -> tuple[dict | None, dict]:
    tr, t0 = _trace("route"), time.monotonic()
    tr["tries"] = 1
    try:
        out = chat_json(prompts.route(question), schemas.ROUTE, "route", 256)  # 120 → 256 (2026-10-10: 길이 초과로 잘림 방지)
    except (LlmUnavailable, LlmBadOutput) as e:
        tr["reason"] = f"LLM 오류: {e}"
        tr["ms"] = int((time.monotonic() - t0) * 1000)
        return None, tr
    got, reason = validate_route(out)
    tr.update(used=bool(got), reason=reason, ms=int((time.monotonic() - t0) * 1000))
    return got, tr


# ---------------------------------------------------------------- 분류 v2 (2026-10-10 계획 3단계, ROUTE_POLICY=llm_primary·llm_guarded)
ROUTE_EXAMPLES = Path(__file__).with_name("route_examples.json")
_NUM = re.compile(r"\d+(?:\.\d+)?")


@lru_cache(maxsize=1)
def route_examples() -> list[dict]:
    """지시문 예시 (qa_route.json pool에서 옮김 — 정책 고르기용 dev 문항과 겹치지 않는다)."""
    return json.loads(ROUTE_EXAMPLES.read_text(encoding="utf-8"))["examples"]


def validate_route_v2(out: dict, question: str) -> tuple[dict | None, str | None]:
    if not isinstance(out, dict) or set(out) != {"kind", "intents", "equipment", "period", "shift", "search_queries"}:
        return None, "형식 오류"
    if out["kind"] not in schemas.KINDS_V2 or out["period"] not in schemas.PERIODS or out["shift"] not in ("none", "D", "N"):
        return None, "값 오류"
    if not isinstance(out["intents"], list) or not set(out["intents"]) <= set(schemas.INTENTS):
        return None, "값 오류"
    if not isinstance(out["equipment"], list) or not set(out["equipment"]) <= set(schemas.ROUTE_V2["properties"]["equipment"]["items"]["enum"]):
        return None, "값 오류"
    if out["kind"] in ("ops", "mixed") and not out["intents"]:
        return None, "값 오류: 운영 조회인데 의도 없음"
    queries = []
    for q in out["search_queries"] if isinstance(out["search_queries"], list) else []:
        if not isinstance(q, str) or not q.strip() or len(q) > 40 or FORBIDDEN.search(q) or "DOC-" in q or "§" in q:
            continue
        if set(_NUM.findall(q)) - set(_NUM.findall(question)):  # 질문에 없는 숫자를 넣은 검색어는 버린다
            continue
        queries.append(q.strip())
    return {**out, "search_queries": queries[:3] if out["kind"] in ("doc", "mixed") else []}, None


def route_v2(question: str, hint: dict) -> tuple[dict | None, dict]:
    """정해진 메뉴 안의 주 분류. hint = 낱말 규칙의 분류 {kind, intents}. 실패하면 None (부른 쪽이 규칙을 쓴다)."""
    tr, t0 = _trace("route"), time.monotonic()
    tr["tries"] = 1
    try:
        out = chat_json(prompts.route_v2(question, hint, route_examples()), schemas.ROUTE_V2, "route", 256)
    except (LlmUnavailable, LlmBadOutput) as e:
        tr["reason"] = f"LLM 오류: {e}"
        tr["ms"] = int((time.monotonic() - t0) * 1000)
        return None, tr
    got, reason = validate_route_v2(out, question)
    tr.update(used=bool(got), reason=reason, ms=int((time.monotonic() - t0) * 1000))
    if got:
        tr["kind"] = got["kind"]  # 평가용 (질문 글·검색어는 넣지 않는다)
    return got, tr


# ---------------------------------------------------------------- 따로 검증 (2026-10-10 계획 4단계, DOC_GATE=tiered)
def verify(question: str, lines: list[str]) -> tuple[bool, dict]:
    """고른 줄만 보고 질문에 답할 수 있나. 별도 호출이다 (줄 고르기와 같은 판단을 두 번 받지 않도록 지시문이 다르다)."""
    tr, t0 = _trace("verify"), time.monotonic()
    tr["tries"] = 1
    try:
        out = chat_json(prompts.verify(question, lines), schemas.VERIFY, "verify", 120)
    except (LlmUnavailable, LlmBadOutput) as e:
        tr["reason"] = f"LLM 오류: {e}"
        tr["ms"] = int((time.monotonic() - t0) * 1000)
        if SL.on():   # STEP_LOG 5단계: 따로 검증 — LLM 호출이 실패했다 (거부로 치지 않는다)
            SL.step("5 따로 검증", 판정="호출 실패", 까닭=str(e), 줄=[SL.cut(x) for x in lines])
        return False, tr
    ok = isinstance(out, dict) and set(out) == {"answers", "missing"} and out["answers"] is True
    tr.update(used=ok, reason=None if ok else ("답 못 함" if isinstance(out, dict) and "answers" in out else "형식 오류"),
              ms=int((time.monotonic() - t0) * 1000))
    if SL.on():   # STEP_LOG 5단계: 따로 검증 — 보일 줄만 보고 질문에 답할 수 있다고 했나 (answers)와 모자란 것(missing)
        SL.step("5 따로 검증", 판정="답할 수 있음" if ok else tr["reason"], answers=out.get("answers") if isinstance(out, dict) else None,
                missing=out.get("missing") if isinstance(out, dict) else None, 줄=[SL.cut(x) for x in lines], ms=tr["ms"])
    return ok, tr


__all__ = ["PhraseAdapter", "select_lines", "route", "route_v2", "verify", "validate_select", "validate_route",
           "validate_route_v2", "check_text", "simplify", "faith", "check_rewrite"]


# ---------------------------------------------------------------- 이어 묻기 (2026-10-12, FOLLOWUP=1)
# 앞 답의 글(안전·절차가 아닌 문서 줄, 운영 초안 글)을 쉽게·짧게 다시 쓴다. 프로그램 검사를 모두 통과하고 따로 뜻 검사(faith)도
# 통과해야 쓴다. 하나라도 실패하면 부른 쪽이 원문 그대로 보인다(fail closed — 따로 검증 verify와 달리 LLM 오류도 거부로 친다).
STRICT_WORDS = ("이상", "이하", "초과", "미만", "금지", "않", "못", "불가", "반드시", "필수", "먼저", "전에", "뒤에", "말고", "말 것", "마세요")   # "말고·말 것·마세요" = 금지 지시 (A2: "~하지 말고"가 "~하지 않고"로 약해진 것을 잡는다)
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")


def check_rewrite(new: str, src: str) -> tuple[str, str | None]:
    """바꿔 쓴 글 한 조각 검사. (다듬은 글, 거부 사유 또는 None)."""
    new = numbers.tidy(tidy(new, src), src)
    if new.count("DOC-") > src.count("DOC-") or new.count("§") > src.count("§"):   # 원문에 없는 출처 표기를 새로 쓰면 거부 — 원문 줄에 이미 있는 절 참조("§2.1 점검 2~5")를 그대로 옮긴 것은 괜찮다 (2026-10-18, 알람 카드 다시 쓰기)
        return new, "출처 표기"
    reason = check_text(new, src, num_match="value")   # 원문 출처·한글 수사·허락/지시·꼬리표·숫자 양방향
    if reason:
        return new, reason
    a, b = set(LATIN.findall(src)), set(LATIN.findall(new))
    if a - b:
        return new, "빠진 영문 이름·번호: " + ", ".join(sorted(a - b)[:5])
    if b - a:
        return new, "새 영문 이름·번호: " + ", ".join(sorted(b - a)[:5])
    lost = [w for w in STRICT_WORDS if new.count(w) < src.count(w)]
    if lost:
        return new, "빠진 조건 말: " + ", ".join(lost)
    if len(new) > max(80, int(len(src) * 1.6) + 40):
        return new, "너무 김"
    return new, None


def simplify(segments: list[str], kind: str) -> tuple[list[str] | None, dict]:
    """조각마다 쉽게(simple)·짧게(short) 다시 쓴 글. 실패하면 None. 다시 요청은 1번(사유를 붙여)."""
    tr, t0, s = _trace("simplify"), time.monotonic(), settings()
    total = sum(len(x) for x in segments)
    feedback = None
    for _ in range(2):
        tr["tries"] += 1
        try:
            out = chat_json(prompts.simplify(segments, kind, feedback), schemas.simplify(len(segments), max(len(x) for x in segments)),
                            "simplify", min(2048, total * 2 + 200))
        except (LlmUnavailable, LlmBadOutput) as e:
            tr["reason"] = f"LLM 오류: {e}"
            break
        texts = out.get("texts") if isinstance(out, dict) and set(out) == {"texts"} else None
        if not isinstance(texts, list) or len(texts) != len(segments) or not all(isinstance(t, str) and t.strip() for t in texts):
            tr["reason"], feedback = "형식 오류", "형식 오류: 조각 수만큼 글을 써야 한다"
        else:
            fixed, reason = [], None
            for i, (t, src) in enumerate(zip(texts, segments)):
                t2, reason = check_rewrite(t.strip(), src)
                if reason:
                    reason = f"{i + 1}번 조각 — {reason}"
                    break
                fixed.append(t2)
            if not reason:
                tr.update(used=True, reason=None, ms=int((time.monotonic() - t0) * 1000))
                return fixed, tr
            tr["reason"], feedback = reason, reason
        if time.monotonic() - t0 > s.budget_s - 5:
            break
    tr["ms"] = int((time.monotonic() - t0) * 1000)
    return None, tr


def faith(segments: list[str], rewrites: list[str]) -> tuple[bool, dict]:
    """바꿔 쓴 글이 원문과 뜻이 같은가 (따로 판정). LLM 오류·형식 오류는 False (fail closed)."""
    tr, t0 = _trace("faith"), time.monotonic()
    tr["tries"] = 1
    try:
        out = chat_json(prompts.faith(segments, rewrites), schemas.FAITH, "faith", 120)
    except (LlmUnavailable, LlmBadOutput) as e:
        tr["reason"] = f"LLM 오류: {e}"
        tr["ms"] = int((time.monotonic() - t0) * 1000)
        return False, tr
    ok = isinstance(out, dict) and set(out) == {"same_meaning", "problem"} and out["same_meaning"] is True
    tr.update(used=ok, reason=None if ok else ("뜻이 다름" if isinstance(out, dict) and "same_meaning" in out else "형식 오류"),
              ms=int((time.monotonic() - t0) * 1000))
    return ok, tr


# ---------------------------------------------------------------- 분류 v3 (2026-10-10 2차, SPLIT_Q)
def validate_route_v3(out: dict, question: str) -> tuple[dict | None, str | None]:
    if not isinstance(out, dict) or "doc_question" not in out:
        return None, "형식 오류"
    dq = out.get("doc_question")
    got, reason = validate_route_v2({k: v for k, v in out.items() if k != "doc_question"}, question)
    if got is None:
        return None, reason
    ok = (isinstance(dq, str) and dq.strip() and len(dq) <= 80 and not FORBIDDEN.search(dq) and "DOC-" not in dq and "§" not in dq
          and not (set(_NUM.findall(dq)) - set(_NUM.findall(question))))
    return {**got, "doc_question": dq.strip() if ok and got["kind"] == "mixed" else ""}, None


def route_v3(question: str, hint: dict) -> tuple[dict | None, dict]:
    """route_v2 + 섞인 질문의 문서 쪽 질문 글."""
    tr, t0 = _trace("route"), time.monotonic()
    tr["tries"] = 1
    try:
        out = chat_json(prompts.route_v3(question, hint, route_examples()), schemas.ROUTE_V3, "route", 320)
    except (LlmUnavailable, LlmBadOutput) as e:
        tr["reason"] = f"LLM 오류: {e}"
        tr["ms"] = int((time.monotonic() - t0) * 1000)
        return None, tr
    got, reason = validate_route_v3(out, question)
    tr.update(used=bool(got), reason=reason, ms=int((time.monotonic() - t0) * 1000))
    if got:
        tr["kind"] = got["kind"]
    return got, tr
