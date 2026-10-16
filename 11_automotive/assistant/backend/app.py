"""FastAPI 앱 (목업 저장소 = simulator/out CSV + 메모리 시연 상태). 실행: uvicorn backend.app:app --port 8000

역할은 시연 모드에서 X-Role(+ X-User) 머리말로 받는다 (로그인 방식은 [선택 필요: 기술 회의]). 권한 검사는 서버에서 한다.
설비 조작·설정 변경·자동 승인 API는 없다 (ai-operations-assistant 규칙 2.6).

주소 이름·오류 형식은 API명세서_v1에 맞춘다 (2026-10-11 멈춤 ③ P4 — 옛 주소는 두지 않는다):
지침카드 MNT-01 `/api/maint/guide-card/{alarm_event_id}`, 사내 문서 DOCS-01 `/api/internal-docs/…`, 알림 처리 NTF-03 `…/resolve`,
실시간 STR-01 `/api/stream/events`, 시연 SIM-01·03 `/api/sim/inject`·`/api/sim/reset`, 교대 보고서 확정 RPT-03
`/api/reports/shift/{shift_id}/confirm`. 오류는 {code, message, detail} (backend/errors.py).
명세에 없는 우리 주소: /api/health, /api/users, /api/assistant/examples, /api/ops/{tool}, /api/internal-docs(목록·본문) [제안].
"""
from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.auth.permissions import NotLoggedIn, PermissionDenied, require
from backend.config import DATA_LABEL, REFERENCE_AT, settings
from backend.errors import ApiError, body as error_body, install as install_errors
from backend.llm import claude_client as CC
from backend.llm import external as EXT
from backend.llm import think as THINK
from backend.llm.client import probe
from backend.demo_state import STATE_NOTE, ScenarioAlreadyInjected, ScenarioNotFound, get_state
from backend.rag.chunker import CorpusError, load_corpus
from backend.rag.doc_view import doc_body, doc_list
from backend.services import briefing as B
from backend.services import guide_card as G
from backend.services import notifications as N
from backend.services import answer_store as AS
from backend.services import shift_reports as SR
from backend.services import steplog as SL
from backend.services.answer import answer, examples
from backend.tools import query_tools as T

app = FastAPI(title="MOM AI 비서 (목업 API)", version="0.3.0")
DEMO_MODE = True  # 시연 모드 (역할 바꿔 보기·사건 넣기). 운영에서는 끈다
install_errors(app)


@app.exception_handler(T.ToolInputError)
def _bad_input(_, exc):
    return JSONResponse(status_code=422, content=error_body("VALIDATION", str(exc)))


def _demo_only() -> None:
    if not DEMO_MODE:
        raise ApiError("INVALID_STATE", "시연 모드가 아닙니다")


class ChatContext(BaseModel):
    screen: str | None = Field(default=None, max_length=20)
    equipment_id: str | None = Field(default=None, max_length=20)
    alarm_key: str | None = Field(default=None, max_length=20)
    alarm_event_id: str | None = Field(default=None, max_length=40)


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: ChatContext | None = None
    # 이어 묻기 (2026-10-12, FOLLOWUP=1 — API명세서에 없는 우리 추가 칸 [제안]): 바로 앞 답의 answer_id. 서버 기억에서 꺼낸다
    prev_answer_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,40}$")
    # 외부 LLM 선택 스위치 (2026-10-15, 사용자 결정 — API명세서에 없는 우리 추가 칸 [제안]): 없거나 "local"이면 서버 기본(로컬 Qwen), "claude"면 이 요청만 외부 Claude Sonnet 5.5
    llm: Literal["local", "claude"] | None = None
    # Qwen "깊게 생각" 버튼 (2026-10-15, 사용자 결정 — 우리 추가 칸 [제안]): 없거나 0이면 서버 기본(생각 끔), 6000이면 이 요청만 생각 예산 6,000토큰. 다른 값은 422
    think: Literal[0, 6000] | None = None


@app.get("/api/health")
def health():
    try:
        n = len(load_corpus())
        corpus = {"status": "ok", "chunks": n}
    except CorpusError as e:
        corpus = {"status": "경로 없음·확인 필요", "detail": str(e)}
    st = get_state()
    s = settings()
    llm_status = {**probe(s), "jobs": sorted(s.llm_jobs) if s.llm_enabled else [], "retrieval": s.retrieval, "flags": s.flags()}
    if not llm_status["enabled"]:
        llm_text = f"{s.llm_label} 꺼짐 (기본 문장) — 모델 {s.llm_model_name} (2026-10-08 결정)"
    elif llm_status["alive"]:
        llm_text = f"{s.llm_label} {s.llm_model_name} 연결됨 ({', '.join(llm_status['jobs'])})"
    else:
        llm_text = f"{s.llm_label} {s.llm_model_name} 응답 없음 — 기본 문장으로 답함 ({llm_status['reason']})"
    return {"status": "ok", "reference_at": REFERENCE_AT, "now": st.now.isoformat(), "data_label": DATA_LABEL, "corpus": corpus,
            "llm": llm_text, "llm_status": llm_status, "demo_mode": DEMO_MODE,
            # 외부 LLM 선택 스위치 (2026-10-15): 서버 끄는 스위치·모델·사용 가능 여부·이 프로세스의 호출 수·환산 비용 추정(기록 파일 아님, 다시 켜면 사라짐)
            "external_llm": CC.external_status(),
            # Qwen "깊게 생각" 버튼 (2026-10-15): 서버 허용 스위치·생각 예산·지금 다른 깊은 생각이 돌고 있는지(동시에 하나만)
            "think": {"server_switch": s.think_app, "budget": THINK.DEEP_BUDGET, "busy": THINK.busy()},
            # 단계별 로그 (2026-10-15, STEP_LOG): 켜짐 여부·폴더·이 프로세스가 쓴 줄 수/상한 때문에 쓰지 않은 수/쓰기 실패 수 (다시 켜면 0부터)
            "step_log": {"enabled": s.step_log, "dir": s.step_log_dir, **SL.status()},
            "scenarios": sorted(st.scenarios), "state_note": STATE_NOTE, "events": len(st.events),
            # 이어 묻기 기억 (2026-10-12): 이 프로세스에만 있다 — 백엔드를 다시 켜면 비워지고 이어 물으면 되묻는다
            "followup_store": {"enabled": s.followup, "answers": AS.size(), "max": AS.MAX_ITEMS, "ttl_hours": AS.TTL_S // 3600,
                               "note": "백엔드 프로세스 메모리에만 둠 (다시 켜면 비워짐)"}}


# ---------------------------------------------------------------- 사용자 (SCR-01)
ROLE_KO = {"OPR": "현장 작업자", "MNT": "보전 담당자", "SUP": "라인 반장", "MGR": "공장 관리자", "MON": "모니터링 계정"}


@app.get("/api/users")
def users():
    # 모니터링 계정은 "추가 예정"(UI설계서 9.5 #20, 2026-10-08 갱신판) → 로그인 목록에서 숨긴다. 권한표의 MON은 남김
    out = []
    for u in get_state().users():
        if u["read_only"] == "true":
            continue
        out.append({**u, "role_ko": ROLE_KO.get(u["role"], u["role"]), "read_only": False})
    return {"users": out, "data_label": DATA_LABEL, "is_synthetic": True,  # 가상 사용자 12명 (2026-10-11 P1)
            "login_note": "로그인 방식은 [선택 필요: 기술 회의] — 시연 모드에서는 사용자 고르기만 한다"}


def _user(x_role: str, x_user: str) -> None:
    """X-User가 오면 그 사람의 역할과 X-Role이 같아야 한다 — 다르면 UNAUTHORIZED (2026-10-11 P4, 전에는 403)."""
    if x_user:
        u = get_state().user(x_user)
        if u is None or u["role"] != x_role.upper():
            raise NotLoggedIn()


# ---------------------------------------------------------------- 비서 (SCR-10)
@app.post("/api/assistant/chat")
def chat(body: ChatIn, x_role: str = Header(default=""), x_user: str = Header(default="")):
    require(x_role, "chat")
    _user(x_role, x_user)
    # 이어 묻기 (FOLLOWUP=1): 앞 답 기록은 서버 기억에서만 꺼낸다 (없음·만료·남의 답 → None → answer()가 되묻는다)
    prev = AS.get(body.prev_answer_id, x_user, x_role) if settings().followup else None
    provider = body.llm or "local"
    if provider == "claude" and not settings().external_app:   # 서버 끄는 스위치 — 꺼져 있으면 외부로 한 글자도 안 보낸다 (최종기획서 4.1절)
        raise ApiError("EXTERNAL_LLM_DISABLED")
    # Qwen "깊게 생각" 버튼 (2026-10-15): 외부 Claude를 고른 요청에는 적용하지 않는다(로컬 Qwen 전용). 서버 스위치가 꺼져 있으면 거절하고,
    # 이미 다른 깊은 생각이 돌고 있으면 기다리지 않고 THINK_BUSY로 알린다(동시에 하나만 — 서버가 2칸이라 겹치면 다른 질문이 막힌다).
    think = (body.think or 0) if provider == "local" else 0
    if think and not settings().think_app:
        raise ApiError("THINK_DISABLED")
    held = False
    if think:
        held = THINK.try_acquire()
        if not held:
            raise ApiError("THINK_BUSY")
    try:
        try:
            with EXT.external_request(provider) as ext, THINK.think_request(think) as tk:   # 요청 단위 선택 — 고르지 않으면 ext·tk는 None이고 아무것도 안 바뀐다. 끝나면 되돌린다
                a = answer(body.question, x_role.upper(), body.context.model_dump() if body.context else None, prev=prev)
                if tk is not None:   # 생각을 켠 호출 수(실패 포함) — 0이면 규칙만으로 답한 것이라 화면이 그렇게 밝힌다
                    a["think"] = {"budget": tk.budget, "calls": tk.calls, "failures": tk.failures}
                if ext is not None:
                    miss = ext.material_failure()   # 재료를 정하는 단계의 외부 호출 실패 → 오류 (자동으로 로컬로 바꾸지 않는다)
                    if miss:
                        raise EXT.ExternalLlmFailure(*miss)
                    s_ext = settings()   # 요청 안이라 외부 모드 설정
                    a["llm"] = {"provider": "claude", "label": s_ext.llm_label, "model": s_ext.claude_model, "effort": s_ext.claude_effort,
                                "calls": ext.calls}   # 0이면 규칙만으로 답함(외부로 보낸 것 없음) — 화면이 사실대로 표시한다
                    polish = ext.polish_failures()   # 다듬고 검사하는 단계 실패 → 이미 정해진 재료로 폴백(원문 줄·기본 문장)해 답하고 표시한다
                    if polish:
                        a["llm"]["partial_failure"] = [j for j, _ in polish]
                        a["external_note"] = "외부 LLM 일부 단계 실패 — 원문으로 답함"
        except EXT.ExternalLlmFailure as e:
            raise ApiError("EXTERNAL_LLM_UNAVAILABLE", detail={"job": e.job, "reason": e.reason}) from e
        except (ApiError, PermissionDenied):
            raise
        except Exception as e:  # 답을 만들다 멈춤 → ASSISTANT_UNAVAILABLE. LLM 실패는 answer() 안에서 기본 문장으로 답하므로 여기에 오지 않는다
            raise ApiError("ASSISTANT_UNAVAILABLE", detail={"reason": type(e).__name__}) from e
    finally:
        if held:   # 어떤 길로 끝나도(성공·오류·예외) 깊은 생각 자리를 반드시 놓는다
            THINK.release()
    record = a.pop("_followup", None)   # 내부 기록은 화면에 보내지 않는다
    if record is not None:
        a["answer_id"] = AS.put(record, x_user, x_role)
    return a


@app.get("/api/assistant/examples")
def assistant_examples(screen: str | None = None, alarm: str | None = None, x_role: str = Header(default="")):
    require(x_role, "chat")
    return {"screen": screen, "examples": examples(screen, alarm)}


# ---------------------------------------------------------------- 교대 시작 브리핑 (AST-01, SCR-02·03 — 화면은 아직 없음)
@app.get("/api/assistant/briefing")
def assistant_briefing(shift_id: str | None = None, view: str | None = None, process: str | None = None,
                       x_role: str = Header(default=""), x_user: str = Header(default="")):
    """전체형(view=full: MNT·SUP·MGR)·작업자 요약형(view=operator: OPR·MGR). 프로그램이 전부 모아 보고 순위대로 (services/briefing.py).
    shift_id는 지금 교대만(두 꼴 다 받음), process는 작업자형에서 MGR이 공정을 골라 볼 때 [제안]. 저장·확정 없음."""
    return B.build(get_state(), x_role, x_user or None, shift_id, view, process)


# ---------------------------------------------------------------- 사내 문서 (SCR-24 팝업, DOCS-01)
# 주소 접두어 /api/internal-docs는 명세 DOCS-01을 따른다. 목록·본문 주소는 명세에 없는 우리 주소 [제안] (2026-10-11 P4)
@app.get("/api/internal-docs")
def docs(x_role: str = Header(default="")):
    require(x_role, "view_docs")
    return {"docs": doc_list(), "note": "가상 사내 문서 (개정 번호는 문서마다 다름) — 원문 출처는 화면에 표시하지 않습니다 (D-03)"}


@app.get("/api/internal-docs/{doc_no}")
def doc(doc_no: str, x_role: str = Header(default="")):
    require(x_role, "view_docs")
    b = doc_body(doc_no)
    if b is None:
        raise ApiError("NOT_FOUND", "사내 문서에 없는 문서 번호입니다", {"doc_no": doc_no})
    return b


@app.get("/api/internal-docs/{doc_no}/sections/{section}")
def doc_section(doc_no: str, section: str, x_role: str = Header(default="")):
    """사내 문서 §절 하나 (DOCS-01, FR-MNT-01-09). 명세의 view=card(마우스 올림 요약 카드)는 2026-10-08 사용자 결정으로 없앴다 —
    요약(summary)과 본문(text)을 함께 돌려준다(불일치로 기록). 원문 출처는 넣지 않는다."""
    require(x_role, "view_doc_section")
    doc_id = doc_no
    chunks = [c for c in load_corpus() if c.doc_id == doc_id.upper() and c.section == section]
    if not chunks:
        raise ApiError("NOT_FOUND", "이 절이 없습니다 (개정으로 바뀌었을 수 있음)", {"doc_no": doc_no, "section": section})
    c = chunks[0]
    text = "\n".join(x.text for x in chunks)
    lines = [l for l in text.splitlines() if l.strip() and not set(l.strip()) <= set("|-: ")]
    return {"doc_id": c.doc_id, "doc_name": c.doc_name, "revision": c.revision, "section": c.section, "title": c.title,
            "cite": c.cite, "summary": " ".join(lines[:3])[:240], "text": text,
            "doc_no": c.doc_id, "rev": c.revision}  # API명세서_v1 출처 칸 이름 (2026-10-11 P1, 옛 칸도 둠)


# ---------------------------------------------------------------- 알림 (SCR-07·08, NTF-01·03)
class ResolveIn(BaseModel):
    action_plan: str = Field(default="", max_length=400)   # 명세 NTF-03: 반복 알람은 action_plan 필수 (전에는 plan)


@app.get("/api/notifications")
def notifications(x_role: str = Header(default=""), x_user: str = Header(default="")):
    return N.listing(get_state(), x_role, x_user or None)


@app.post("/api/notifications/{nid}/resolve")
def resolve_notification(nid: str, body: ResolveIn, x_role: str = Header(default=""), x_user: str = Header(default="")):
    try:
        return N.process(get_state(), nid, x_role, x_user or None, body.action_plan)
    except N.NotFound:
        raise ApiError("NOT_FOUND", "알림이 없습니다", {"id": nid})
    except N.InvalidInput as e:
        raise ApiError("VALIDATION", str(e), {"id": nid})
    except N.InvalidState as e:
        raise ApiError("INVALID_STATE", str(e), {"id": nid})


@app.get("/api/stream/events")
async def events(request: Request, role: str = "", user: str = "", last: int = 0,
                 last_event_id: str | None = Header(default=None)):
    """SSE (STR-01). EventSource는 머리말을 못 보내므로 role·user를 주소 값으로 받는다(명세는 값 없음 — 불일치로 기록).
    받는 사람 거르기는 서버에서 한다. 사건 이름: notification(change = created·processed), urgent_popup (명세 3장)."""
    st = get_state()
    v = N.viewer(st, role, user or None)
    start = int(last_event_id) if (last_event_id or "").isdigit() else max(0, last)

    async def gen():
        seen, idle = start, 0
        yield "retry: 3000\n\n"
        while True:
            if await request.is_disconnected():
                break
            evs, seen_now = st.events_after(seen, v.role, v.user_id)
            # 이벤트 id는 1부터 늘어나므로, 다시 이을 때 Last-Event-ID 뒤만 보내면 중복이 없다 (거른 이벤트는 다시 걸러짐)
            for ev in evs:
                yield f"id: {ev['id']}\nevent: {ev['type']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
            seen = seen_now
            idle += 1
            if idle >= 30:
                idle = 0
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- 지침카드 (SCR-09, MNT-01)
@app.get("/api/maint/guide-card/{alarm_event_id}")
def guide_card(alarm_event_id: str, x_role: str = Header(default="")):
    try:
        return G.build(get_state(), alarm_event_id, x_role)
    except G.NotFound:
        raise ApiError("NOT_FOUND", "알람 기록이 없습니다", {"alarm_event_id": alarm_event_id})


# ---------------------------------------------------------------- 시연 (SIM-01·03 — 설비 조작 아님: 가상 운영 기록만 넣는다)
class InjectIn(BaseModel):
    scenario_code: str = Field(min_length=1, max_length=10)   # 명세 SIM-01 "사건" (S1~S6, 지금은 S1만)


@app.post("/api/sim/inject")
def sim_inject(body: InjectIn, x_role: str = Header(default=""), x_user: str = Header(default="")):
    _demo_only()
    require(x_role, "run_demo_scenario")
    _user(x_role, x_user)
    st = get_state()
    try:
        rows = st.inject(body.scenario_code)
    except ScenarioNotFound as e:
        raise ApiError("NOT_FOUND", str(e), {"scenario_code": body.scenario_code})
    except ScenarioAlreadyInjected as e:
        raise ApiError("INVALID_STATE", str(e), {"scenario_code": body.scenario_code})
    N.created_events(st, rows)
    AS.clear()   # 운영 데이터가 바뀌었으므로 이어 묻기 기억을 비운다 (2026-10-12)
    return {"scenario": body.scenario_code.upper(), "added": [r["alarm_event_id"] for r in rows], "now": st.now.isoformat(),
            "data_label": DATA_LABEL, "is_synthetic": True, "state_note": STATE_NOTE}


@app.post("/api/sim/reset")
def sim_reset(x_role: str = Header(default="")):
    """시연 상태를 처음(기준 시각, 넣은 사건·처리 기록·교대 보고서 겹침 없음)으로 되돌린다. 시연 모드 전용."""
    _demo_only()
    require(x_role, "run_demo_scenario")
    get_state().reset()
    AS.clear()   # 이어 묻기 기억도 비운다 (2026-10-12)
    return {"now": get_state().now.isoformat(), "is_synthetic": True, "state_note": STATE_NOTE}


# ---------------------------------------------------------------- 읽기 전용 조회 도구 (명세에 없는 우리 주소 — 화면 확인용)
@app.get("/api/ops/{tool}")
def ops(tool: str, x_role: str = Header(default=""), equipment_id: str | None = None):
    """읽기 전용 조회 도구 (화면 확인용). 설비 조작·변경·삭제 API는 없다."""
    fn = T.TOOLS.get(tool)
    if fn is None or tool in ("lots",):
        raise ApiError("NOT_FOUND", "없는 조회 도구입니다", {"tool": tool})
    if tool == "kpi":
        return fn(x_role.upper(), equipment_id or "VF2-01")
    if tool in ("production", "inventory"):
        return fn(x_role.upper())
    return fn(x_role.upper(), equipment_id)


# ---------------------------------------------------------------- 교대 보고서 확정 (RPT-03, FR-PRD-02-11)
class ConfirmIn(BaseModel):
    version: int | None = None   # 명세: 문서를 고치는 요청은 version을 함께 보낸다. 다르면 CONFLICT_VERSION


@app.post("/api/reports/shift/{shift_id}/confirm")
def confirm_shift_report(shift_id: str, body: ConfirmIn, x_role: str = Header(default=""), x_user: str = Header(default="")):
    """그 교대의 반장만 확정한다 (확정자 = X-User, 교대 달력의 sup). shift_id는 2026-09-30-D·SHIFT-260930-D 둘 다 받는다.
    이미 확정 → INVALID_STATE, 버전 다름 → CONFLICT_VERSION. 상태는 시연 상태에 겹쳐 둔다(services/shift_reports.py)."""
    return SR.confirm(get_state(), shift_id, x_user, x_role, body.version)
