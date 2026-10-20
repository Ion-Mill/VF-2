"""작업기록서 메모 정리 입구 — 백엔드 `POST /api/maint/work-records/{번호}/assist`(API-MNT-10, FR-MNT-05-02)가 부르는
`POST /work-record-assist` (2026-10-20). chat_service의 서비스 키(X-Service-Key)가 그대로 걸린다.

  · 보전 담당자 메모(자유 글)를 원인(cause)·조치(action) 두 칸 AI비서 초안으로 나눠 다듬는다. 저장하지 않는다 — 사람이 PATCH로 넣는다.
  · 메모에 없는 사실·숫자를 만들지 않는다 (FR-AST-COM-05): 메모의 숫자가 빠지거나 새 숫자가 생기면 거부하고 한 번 다시 묻는다.
  · 근거(sources)는 사내 문서 조각 검색(BM25) 결과 — 사내 문서 칸(doc_name·doc_no·rev·section)만 (D-03·R-85). 프로그램이 고른다.
  · 사용 부품(parts)은 LLM이 아니라 프로그램이 고른다: 백엔드가 보낸 재고 품목(items) 이름·번호가 메모에 있으면 그 품목,
    바로 뒤 숫자(+단위)가 있으면 수량. 없으면 빈 목록 (지어내지 않음).
  · 외부 LLM(Claude)으로만 간다. 스위치 셋(ASSISTANT_PROVIDER=claude, EXTERNAL_LLM_APP=1, LLM_ENABLED=1)이 모두 맞아야 하고,
    아니면 외부로 한 글자도 안 보내고 503. user_id는 받기만 하고 외부로 보내지 않는다 (NFR-SEC-08 — 메모 속 이름·ID는 outbound_guard가 가림).
  · 실패는 모두 503 ASSISTANT_UNAVAILABLE(retryable). 까닭은 서버 로그에만. 백엔드는 503을 받으면 화면에 기본 문구를 보인다.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend import config as C
from backend.llm import adapter, numbers, prompts
from backend.llm import client as LC
from backend.llm import deadline as DL
from backend.llm import external as EXT
from backend.privacy import outbound_guard as OG
from backend.rag.search import search

log = logging.getLogger("assistant")

router = APIRouter()
TRIES = 2                      # 첫 요청 + 사유를 붙인 다시 요청 1번
MAX_MEMO = 2000
CAUSE_MAX, ACTION_MAX = 300, 500
SOURCES_K = 3


class AssistUnavailable(Exception):
    """메모 정리를 줄 수 없다 — chat_service가 503 ASSISTANT_UNAVAILABLE로 바꾼다."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_no: str = Field(pattern=r"^[A-Za-z0-9_-]{1,30}$")
    item_name: str = Field(min_length=1, max_length=100)


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")          # 정해진 칸만 — 사람·계정 칸을 끼워 보낼 길이 없다
    record_no: str = Field(pattern=r"^MR-[A-Z0-9-]{1,20}$")
    equipment_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")
    memo: str = Field(min_length=1, max_length=MAX_MEMO)
    user_id: str | None = Field(None, max_length=40)   # 백엔드 계약 칸 — 외부로 보내지 않는다
    alarm_code: str | None = Field(None, max_length=20)
    items: list[ItemIn] = Field(default_factory=list, max_length=300)


def _provider_is_claude(env) -> bool:
    return env("ASSISTANT_PROVIDER", "local").strip().lower() == "claude"


def sources_for(alarm_code: str | None, memo: str) -> list[dict]:
    """근거 조각: 알람 번호 + 메모로 사내 문서 검색 (용어집 뺌). 사내 문서 칸만"""
    out, seen = [], set()
    for _, c in search(f"{alarm_code or ''} {memo}".strip(), k=SOURCES_K * 3):
        if c.doc_id == "GLOSSARY" or (c.doc_id, c.section) in seen:
            continue
        seen.add((c.doc_id, c.section))
        out.append({"doc_name": c.doc_name, "doc_no": c.doc_id, "rev": c.revision, "section": f"§{c.section}"})
        if len(out) >= SOURCES_K:
            break
    return out


_QTY = re.compile(r"^\s*(?:을|를|은|는|이|가)?\s*(\d+(?:\.\d+)?)\s*(개|ea|EA|L|ℓ|l|mL|ml|kg|g|m)?")


def parts_from_memo(memo: str, items: list[ItemIn]) -> list[dict]:
    """메모에 이름·번호가 나온 재고 품목만. 바로 뒤에 숫자가 있으면 수량, 없으면 qty = None (지어내지 않음)"""
    out = []
    for it in items:
        for key in (it.item_no, it.item_name):
            i = memo.find(key)
            if i >= 0:
                m = _QTY.match(memo[i + len(key):])
                out.append({"item_no": it.item_no, "qty": float(m.group(1)) if m else None})
                break
    return out


def messages(memo: str, ctx: str, feedback: str | None = None) -> list[dict]:
    rules = ("아래 '메모'는 보전 담당자가 정비 뒤 적은 자유 글이다. 작업기록서의 두 칸으로 나눠 현장 사람이 읽기 쉬운 한국어로 쓴다.\n"
             "- cause: 메모에 적힌 고장 원인·확인한 상태. 메모에 원인이 없으면 빈 글(\"\")로 둔다.\n"
             "- action: 메모에 적힌 조치(점검·교체·보충·조정 등)와 결과.\n"
             "- 메모에 없는 사실·원인·부품·숫자를 새로 만들지 않는다. 메모의 숫자·단위·설비 이름·알람 번호·기록 번호는 하나도 빼거나 바꾸지 않는다.\n"
             "- 숫자는 아라비아 숫자 그대로. 사람 이름을 쓰지 않는다. 출처·문서 번호·§는 쓰지 않는다. 길게 늘이지 않는다.")
    user = f"{ctx}\n메모:\n{memo}"
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}. 이 점을 고쳐 다시 쓴다."
    return [{"role": "system", "content": prompts.COMMON + "\n" + rules}, {"role": "user", "content": user}]


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["cause", "action"],
          "properties": {"cause": {"type": "string", "maxLength": CAUSE_MAX},
                         "action": {"type": "string", "minLength": 1, "maxLength": ACTION_MAX}}}


def check(memo: str, out: dict) -> tuple[dict | None, str | None]:
    """통과하면 ({cause, action}, None), 아니면 (None, 사유). 숫자는 두 칸을 합쳐 메모와 맞춘다"""
    cause = adapter.tidy(str(out.get("cause", "")).strip(), memo)
    action = adapter.tidy(str(out.get("action", "")).strip(), memo)
    cause, action = numbers.tidy(cause, memo), numbers.tidy(action, memo)
    if not action:
        return None, "조치 칸이 빔"
    why = adapter.check_text(f"{cause} {action}".strip(), memo, num_match="value")
    if why:
        return None, why
    if OG.scrub_text(cause)[1] or OG.scrub_text(action)[1]:
        return None, "사람 이름·계정 정보"
    return {"cause": cause, "action": action}, None


def assist(req: AssistRequest) -> dict:
    memo = OG.scrub_text(req.memo)[0]                 # 메모 속 이름·ID는 보내기 전에 가린다 (claude_client도 한 번 더 가림)
    ctx = f"설비: {req.equipment_id}" + (f", 알람: {req.alarm_code}" if req.alarm_code else "")
    feedback, why = None, "시도 없음"
    for n in range(1, TRIES + 1):
        try:
            out = LC.chat_json(messages(memo, ctx, feedback), SCHEMA, "work_record_assist", 800)
        except LC.LlmBadOutput as e:
            feedback = why = f"형식 오류: {e}"
            continue
        got, why = check(memo, out)
        if got:
            return {**got, "tries": n}
        feedback = why
        log.info("메모 정리 검사 거부(%d번째): %s", n, why)
    raise AssistUnavailable(f"검사 통과 못 함: {why}")


@router.post("/work-record-assist")
def work_record_assist(req: AssistRequest) -> dict:
    from backend import chat_service as CS      # 서비스 키 환경을 읽는 함수만 빌려 쓴다 (순환 import를 피해 호출 때)
    if not _provider_is_claude(CS._env):
        raise AssistUnavailable("provider is not claude")
    if not C.settings().external_app:
        raise AssistUnavailable("external switch off")
    try:
        with EXT.external_request("claude"):
            s = C.settings()
            if not s.llm_enabled:
                raise AssistUnavailable("llm disabled")
            with DL.answer_deadline(s.budget_s):
                got = assist(req)
    except AssistUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 — 안쪽 사정은 로그에만
        raise AssistUnavailable(type(e).__name__) from e
    return {"record_no": req.record_no, "cause": got["cause"], "action": got["action"],
            "sources": sources_for(req.alarm_code, req.memo), "parts": parts_from_memo(req.memo, req.items)}
