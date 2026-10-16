"""묶음의 답(answer() 결과)을 기존 백엔드의 비서 응답 계약으로 바꾼다 (순수 함수 — DB·LLM·네트워크 없음).

기존 백엔드(`11_automotive/backend/app/assistant/client.py`)가 받는 모양:
  {answer: str, sources: [{doc_name, doc_no, rev, section}], related: [str], status: OK|NOT_IN_DOCS|OUT_OF_ROLE|REFUSED|NO_RESPONSE}
묶음의 답은 conclusion·steps·evidence·caution·status("답변"·"안내" …)로 나뉘어 있고 칸이 더 많다. 내부 칸(blocks·followup·answer_id·llm …)은 내보내지 않는다.
"""
from __future__ import annotations

import re

# 묶음의 한국어 상태 → 백엔드 상태 코드. 표에 없는 값은 몰래 OK로 두지 않고 UnknownStatus로 올린다(시험이 잡고, 서비스는 503으로 답한다).
STATUS_MAP = {
    "답변": "OK",
    "확인 필요": "OK",                # 되묻는 글 (설비·로트 번호 등이 빠졌을 때)
    "문서에 없음": "NOT_IN_DOCS",
    "근거 없음": "NOT_IN_DOCS",
    "권한이 없습니다": "OUT_OF_ROLE",
}
SOURCE_KEYS = ("doc_name", "doc_no", "rev", "section")     # 출처는 사내 문서 이름·번호·개정·§만 (D-03, R-85)

# 백엔드 채팅 권한 (2026-10-13 [가상]): MTTR·MTBF·센서 데이터는 MNT·MGR만. 묶음은 이 규칙을 모른다 → 서비스가 막는다.
ROLE_KO = {"OPR": "작업자", "MNT": "보전 담당자", "SUP": "반장", "MGR": "공장 관리자"}
TOPIC_RE = {
    "reliability": re.compile(r"mttr|mtbf|평균\s*수리|수리\s*시간|고장\s*간격", re.I),
    "sensor_trend": re.compile(r"센서|모터\s*온도|공기\s*압|압력|psi|전압|부하\s*(?:값|추세)|추세", re.I),
}
EQUIPMENT_RE = re.compile(r"\b(?:SAW|MIL|VF2|WSH|CMM)-\d{2}\b", re.I)
VALUE_ASK_RE = re.compile(r"얼마|몇|알려|보여|현재|지금|최근|값|수치|추세|어때|어떻")


class UnknownStatus(ValueError):
    pass


def map_status(a: dict) -> str:
    s = a.get("status")
    if s == "안내":
        # 같은 "안내"라도 설비 조작·사람만 하는 일을 거절하는 문구(human_only → mode "규칙")는 REFUSED, 화면 안내(mode "화면 안내 …")는 OK
        return "REFUSED" if a.get("mode") == "규칙" else "OK"
    if s in STATUS_MAP:
        return STATUS_MAP[s]
    raise UnknownStatus(f"알 수 없는 상태: {s!r}")


def _step_text(s) -> str:
    if isinstance(s, str):
        return s
    if isinstance(s, dict):
        no, who, text = s.get("no"), s.get("who"), s.get("text")
        return " ".join(x for x in (str(no) if no else "", f"({who})" if who else "", text or "") if x)
    return str(s)


def to_answer_text(a: dict) -> str:
    """conclusion + 점검 순서(steps) + 관련 운영 정보 한 줄(related) + 주의(caution)를 한 글로."""
    parts = [(a.get("conclusion") or "").strip()]
    steps = [_step_text(s).strip() for s in (a.get("steps") or []) if s]
    if steps:
        parts.append("\n".join(steps))
    related = a.get("related")
    if isinstance(related, str) and related.strip():
        parts.append(related.strip())           # 묶음의 related는 기록 번호 목록이 아니라 문장 한 줄이라 본문에 붙인다
    caution = a.get("caution")
    if isinstance(caution, str) and caution.strip():
        parts.append("주의: " + caution.strip())
    return "\n\n".join(p for p in parts if p)


def to_sources(a: dict) -> list[dict]:
    out, seen = [], set()
    for e in a.get("evidence") or []:
        if not isinstance(e, dict):
            continue
        src = {"doc_name": e.get("doc_name"), "doc_no": e.get("doc_no") or e.get("doc_id"),
               "rev": e.get("rev") or e.get("revision"), "section": e.get("section")}
        key = (src["doc_no"], src["section"])
        if key in seen or not src["doc_no"]:
            continue
        seen.add(key)
        out.append(src)                        # 네 칸만 — snippet·cite·title 같은 안쪽 칸과 원문 출처는 넣지 않는다
    return out


def to_backend(a: dict) -> dict:
    status = map_status(a)
    return {"answer": to_answer_text(a), "sources": to_sources(a), "related": [], "status": status}


def role_gate(question: str, out_of_role: list[dict]) -> dict | None:
    """권한 밖 질문이면 값 없이 "누가 볼 수 있는지"만 담은 응답을, 아니면 None.

    out_of_role = 백엔드가 이 사용자 역할 때문에 뺀 도구 [{tool, about, roles}]. 값을 묻는 질문일 때만 막는다
    ("MTTR이 뭐야?" 같은 용어 질문은 사내 문서 검색이라 전원 허용 — 기획서 13장, API-AST-02)."""
    asks_values = bool(EQUIPMENT_RE.search(question)) or bool(VALUE_ASK_RE.search(question))
    if not asks_values:
        return None
    for item in out_of_role or []:
        pat = TOPIC_RE.get(item.get("tool"))
        if pat is None or not pat.search(question):
            continue
        who = "와 ".join(f"{ROLE_KO.get(r, r)}({r})" for r in item.get("roles") or []) or "권한이 있는 사람"
        about = item.get("about") or "이 정보"
        return {"answer": f"{about}은(는) {who}만 볼 수 있어요. 값은 알려 드리지 않습니다.", "sources": [], "related": [], "status": "OUT_OF_ROLE"}
    return None
