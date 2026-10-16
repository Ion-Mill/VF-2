"""AI 비서 '이브' 채팅 (API-AST-02 안쪽) — 구독 중인 Claude(Claude Code 로그인)를 `claude -p`로 부른다.

흐름:
  1. 사용자 역할 확인 (masters/app_user.csv)
  2. 알람 번호가 있으면 알람 코드집 항목을 정확히 일치로 먼저 넣음 (FR-MNT-01-02)
  3. Claude 실행: 검색용 사내 문서(Read·Grep·Glob) + 운영 조회 도구(MCP, 역할은 도구 서버가 확인)
  4. 답 검사: JSON 모양, 출처가 실제 절인지, 원문 이름, 권한 밖 (입출력형식 메모 3.5) → 틀리면 한 번 다시 요청
  5. 채팅 기록 저장 (사용자별 30일, FR-MNT-01-01)

개인 개발·시험용이다. 여러 사람이 쓰는 서비스는 API 키 방식으로 바꿔야 한다 (README 참고).
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import 조회도구
from 문서조각 import load_index
from 설정 import (CHAT_KEEP_DAYS, DB_FILE, EFFORT, HERE, MODEL, PERMISSION_MESSAGE, SEARCH_DIR, TIMEOUT_SEC,
                find_claude)

ROLE_NAMES = {"OPR": "현장 작업자", "MNT": "보전 담당자", "SUP": "라인 반장", "MGR": "공장 관리자"}
DOC_NOS = ["GLOSSARY", "DOC-01", "DOC-02", "DOC-03", "DOC-04", "DOC-05", "DOC-06", "DOC-07"]
DEFAULT_ANSWER = "지금은 비서가 답할 수 없습니다. 잠시 뒤 다시 물어 주세요."
# 원문 출처가 답에 나오면 안 된다 (D-03, FR-AST-COM-02). 설비 모델 이름(Haas VF-2 등)은 괜찮다.
ORIGINAL_SOURCE = re.compile(r"KOSHA|TG0\d+|PDF|\.pdf|\d+\s*쪽|CSV\s*\d+\s*행|서비스 매뉴얼|조작 매뉴얼|"
                             r"Kang 외|OEE\.com|NCS|MISUMI|Nemak|AMREP|원문 대응표")
RELATED_ID = re.compile(r"^(MR-\d+|MW-\d+|LOT-\d{4}-\d{3}-\d+|PO-\d{4}-\d{3}|SHP-\d{4}-\d{3}|"
                        r"알람 기록 #\d+|PM-[\w.-]+|\d{4}-\d{2}-\d{2}-[DN]|[A-Z]{2,3}\d?-\d{2}-T\d{2})$")

SYSTEM_PROMPT = """너는 자동차 엔진 마운트 브래킷(BRK-A100) 가공 라인의 AI 비서 '이브'다. 현장 사람의 질문에 한국어로 답한다.

근거 (이 두 가지만 쓴다)
- 사내 문서: 지금 폴더의 md 파일 8개(용어집, DOC-01~07). Grep으로 찾고 Read로 읽는다. 각 절 제목에 [DOC-03 §2.1] 같은 출처 표시가 있다.
- 운영 기록: mcp__eve__ 조회 도구 15개 (equipment_status 설비 상태, alarm_history 알람 기록, alarm_code 알람 코드, metrics MTBF·고장 횟수, mttr MTTR, production 생산 실적, lot 로트, work_order 작업지시, work_record 작업기록, pm_due 예방 정비 기한, tool_life 공구 수명, inventory 재고, shipment 출하, sensor_trend 센서 추세, equipment_spec 설비 사양).
- 문서 질문은 문서를, 운영 질문은 조회 도구를, 섞인 질문은 둘 다 쓴다. 찾은 것만으로 답한다. 기억이나 일반 지식으로 채우지 않는다.

답 규칙
1. 문서·기록에 없으면 지어내지 말고 status를 "문서에 없음"으로 한다. 불량 원인을 물으면 근거 문서가 없다고 답한다.
2. 숫자를 만들지 않는다. 문서에 없는 알람 기준값(온도·압력 등)은 말하지 않는다. 숫자는 문서나 도구 값을 그대로 옮긴다. 손실 수량·예측은 "추정"이라고 쓴다. [가상] 값은 가상이라고 밝힌다.
3. 압력은 psi를 쓰고 bar를 괄호로 함께 쓴다 (예: 100 psi (약 6.9 bar)).
4. 용어집의 표준어를 쓴다 (쿨런트 → 절삭유, 록아웃 → 잠금·표지). "쓰지 않는 말" 칸의 말은 쓰지 않는다.
5. 원문 이름은 답에 쓰지 않는다: 제조사 매뉴얼·안내서 이름과 번호, KOSHA, 논문, PDF·쪽 번호, CSV 행 번호. 출처는 sources 칸에만 사내 문서 번호와 절로 적는다.
6. 사람만 할 수 있는 일(작업지시서 승인, 담당자 지정, 정지 사유 확정, 로트 보류·해제, 설비 조작, 잠금·표지, 정비)을 해 달라고 하면 하지 않고 status를 "거부"로 하고, 어느 화면에서 누가 하는지 안내한다. 너는 설비를 조작할 수 없다.
7. 조회 도구가 "권한 밖"을 돌려주면 그 값을 말하지 말고, 다른 도구 값으로 계산해서 알려 주지도 않는다. status를 "권한 밖"으로 하고 "{perm}"이라고 안내한다.
8. 안전 절차(잠금·표지 단계)는 직접 다시 쓰지 말고 DOC-05의 해당 절을 따르라고 안내한다.
9. 답 끝에 관련 운영 정보 한 줄을 덧붙인다 (예: 알람 질문이면 "이 알람은 최근 7일 동안 VF2-01에서 3번 떴습니다"). 조회 도구로 확인한 것만 쓴다.
10. 현장 작업자가 바로 읽을 수 있게 쉬운 말로 짧게 쓴다. 필요하면 짧은 목록을 쓴다.

출력 칸
- answer: 답 문장
- sources: 실제로 읽고 근거로 쓴 사내 문서 절만. 답 문장에 적은 절(예: DOC-05 §2)도 빠짐없이 넣는다. 예: {{"doc_no": "DOC-03", "section": "§2.1"}}. 용어집은 doc_no "GLOSSARY". 운영 기록만 썼으면 빈 목록
- related: 답에 쓴 운영 기록 번호 (작업기록 MR-0903, 작업지시서 MW-0901, 로트 LOT-2609-041-1, 알람 기록은 "알람 기록 #356", 교대 2026-09-15-D)
- status: ok / 문서에 없음 / 거부 / 권한 밖
""".format(perm=PERMISSION_MESSAGE)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "sources": {"type": "array", "items": {
            "type": "object",
            "properties": {"doc_no": {"type": "string", "enum": DOC_NOS}, "section": {"type": "string"}},
            "required": ["doc_no", "section"], "additionalProperties": False}},
        "related": {"type": "array", "items": {"type": "string"}},
        "status": {"type": "string", "enum": ["ok", "문서에 없음", "거부", "권한 밖"]},
    },
    "required": ["answer", "sources", "related", "status"],
    "additionalProperties": False,
}


class ApiError(Exception):
    """API 명세 1장 오류 형식 {code, message, detail}."""

    def __init__(self, code, message, http_status=400, detail=None):
        super().__init__(message)
        self.code, self.message, self.http_status, self.detail = code, message, http_status, detail or {}

    def to_dict(self):
        return {"code": self.code, "message": self.message, "detail": self.detail}


# ---------- 사용자 ----------

def get_user(user_id):
    user = next((u for u in 조회도구.master("app_user") if u["user_id"] == user_id), None)
    if not user or user["is_active"] != "true":
        raise ApiError("UNAUTHORIZED", "로그인 정보가 없거나 쓸 수 없는 사용자입니다.", 401)
    return user


# ---------- 채팅 기록 (chat_log) ----------

@contextmanager
def db():
    """저장(commit)하고 연결을 닫는다. sqlite3 연결의 with는 닫지 않으므로 따로 닫는다."""
    con = sqlite3.connect(DB_FILE)
    try:
        with con:
            yield _prepare(con)
    finally:
        con.close()


def _prepare(con):
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS chat_log (
        chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL, role_code TEXT NOT NULL,
        asked_at TEXT NOT NULL,          -- 시뮬레이터 시계 (API 명세 1장)
        created_at TEXT NOT NULL,        -- 실제 시각 (30일 보관 계산)
        question TEXT NOT NULL, context_json TEXT, parent_chat_id INTEGER,
        answer TEXT, sources_json TEXT, related_json TEXT, status TEXT,
        tools_json TEXT, duration_ms INTEGER)""")
    return con


def purge_old(con):
    limit = (datetime.now() - timedelta(days=CHAT_KEEP_DAYS)).isoformat()
    con.execute("DELETE FROM chat_log WHERE created_at < ?", (limit,))


def save_chat(user, question, context, parent_id, result, tools, duration_ms):
    with db() as con:
        purge_old(con)
        cur = con.execute(
            "INSERT INTO chat_log (user_id, role_code, asked_at, created_at, question, context_json, parent_chat_id,"
            " answer, sources_json, related_json, status, tools_json, duration_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["user_id"], user["role_code"], 조회도구.now().isoformat(), datetime.now().isoformat(), question,
             json.dumps(context, ensure_ascii=False) if context else None, parent_id, result["answer"],
             json.dumps(result["sources"], ensure_ascii=False), json.dumps(result["related"], ensure_ascii=False),
             result["status"], json.dumps(tools, ensure_ascii=False), duration_ms))
        return cur.lastrowid


def history(user_id, days=CHAT_KEEP_DAYS):
    """GET /api/assistant/chat — 본인 기록만, 30일 안."""
    get_user(user_id)
    days = min(int(days), CHAT_KEEP_DAYS)
    limit = (datetime.now() - timedelta(days=days)).isoformat()
    with db() as con:
        purge_old(con)
        rows = con.execute("SELECT * FROM chat_log WHERE user_id = ? AND created_at >= ? ORDER BY chat_id DESC",
                           (user_id, limit)).fetchall()
    return {"items": [{"chat_id": r["chat_id"], "asked_at": r["asked_at"], "question": r["question"],
                       "answer": r["answer"], "sources": json.loads(r["sources_json"] or "[]"),
                       "related": json.loads(r["related_json"] or "[]"), "status": r["status"],
                       "parent_chat_id": r["parent_chat_id"]} for r in rows]}


def conversation(user_id, chat_id, max_turns=5):
    """이어서 물을 때: 앞 대화(본인 것만)를 거슬러 올라가며 모은다."""
    turns = []
    with db() as con:
        cid = chat_id
        while cid and len(turns) < max_turns:
            r = con.execute("SELECT * FROM chat_log WHERE chat_id = ?", (cid,)).fetchone()
            if not r or r["user_id"] != user_id:
                if cid == chat_id:
                    raise ApiError("NOT_FOUND", "이어서 물을 채팅 기록이 없습니다.", 404, {"chat_id": chat_id})
                break
            turns.append((r["question"], r["answer"]))
            cid = r["parent_chat_id"]
    return list(reversed(turns))


# ---------- 질문 만들기 ----------

def alarm_exact_matches(question, index):
    """질문 속 숫자 중 알람 코드집에 있는 번호 → DOC-02 해당 절 조각 목록."""
    alarms = 조회도구.alarm_names()
    chunks = []
    for code in dict.fromkeys(re.findall(r"(?<![\d.])\d{3,5}(?![\d.])", question)):
        a = alarms.get(code)
        chunk = a and index.get(("DOC-02", a["doc02_section"]))
        if chunk:
            chunks.append(chunk)
    return chunks


def build_prompt(user, question, context, turns, alarm_chunks, feedback=None):
    parts = [f"[질문한 사람] {user['user_name']} ({user['role_code']}, {ROLE_NAMES[user['role_code']]})",
             f"[지금 시각(시연 시계)] {조회도구.now().isoformat(timespec='minutes')}"]
    if context:
        parts.append(f"[화면 맥락] {json.dumps(context, ensure_ascii=False)}")
    for q, a in turns:
        parts.append(f"[이전 질문] {q}\n[이전 답] {a}")
    if alarm_chunks:
        parts.append("[알람 코드집 정확 일치 — 먼저 근거로 쓴다]\n" + "\n\n".join(
            f"[{c['doc_no']} {c['section']}] {c['title']}\n{c['text']}" for c in alarm_chunks))
    parts.append(f"[질문] {question}")
    if feedback:
        parts.append(f"[앞 답을 고쳐야 할 점] {feedback}")
    return "\n\n".join(parts)


# ---------- Claude 실행 ----------

def run_claude(prompt, role, audit_path):
    """채팅: 문서 읽기 도구 + 운영 조회 도구(MCP, 역할은 도구 서버가 확인)."""
    mcp = {"mcpServers": {"eve": {
        "command": sys.executable, "args": [str(HERE / "조회도구.py")],
        "env": {"EVE_ROLE": role, "EVE_AUDIT": audit_path, "PYTHONIOENCODING": "utf-8",
                **({"EVE_NOW": os.environ["EVE_NOW"]} if os.environ.get("EVE_NOW") else {})}}}}
    return call_claude(prompt, SYSTEM_PROMPT, OUTPUT_SCHEMA,
                       ["--tools", "Read,Grep,Glob", "--allowedTools", "Read,Grep,Glob,mcp__eve",
                        "--mcp-config", json.dumps(mcp, ensure_ascii=False)])


def call_claude(prompt, system_prompt, schema, tool_args=("--tools", "")):
    """구독 Claude를 `claude -p`로 한 번 부르고 정해진 JSON 칸(structured_output)을 돌려준다.
    API 키나 로컬 LLM으로 바꿀 때는 이 함수만 고치면 된다."""
    cmd = [find_claude(), "-p", "--output-format", "json",
           "--model", MODEL, "--effort", EFFORT,
           "--system-prompt", system_prompt,
           "--json-schema", json.dumps(schema, ensure_ascii=False),
           "--restricted",                                   # 명령 실행 도구 없음, 사용자 설정 안 읽음
           "--strict-mcp-config", *tool_args,
           "--no-session-persistence"]
    env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):   # 구독 로그인을 쓰게 API 키는 뺀다
        env.pop(key, None)
    proc = subprocess.run(cmd, input=prompt, cwd=SEARCH_DIR, env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=TIMEOUT_SEC)
    if not proc.stdout.strip():
        raise RuntimeError(f"claude 실행 실패 (코드 {proc.returncode}): {proc.stderr[-500:]}")
    data = json.loads(proc.stdout)
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude 오류: {data.get('subtype')} {str(data.get('result'))[:300]}")
    out = data.get("structured_output")
    if not isinstance(out, dict):
        raise ValueError("정해진 JSON 칸으로 답하지 않음")
    return out


def read_audit(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------- 답 검사 (입출력형식 메모 3.5) ----------

def check(out, index, tools, alarm_chunks=()):
    """문제 목록과 고친 답을 돌려준다. 문제가 있으면 한 번 다시 요청한다."""
    problems = []
    # 알람 번호 정확 일치 항목은 프로그램이 첫 출처로 넣는다 (FR-MNT-01-02)
    sources = [] if out["status"] == "거부" else [
        {"doc_name": c["doc_name"], "doc_no": c["doc_no"], "rev": c["rev"], "section": c["section"]}
        for c in alarm_chunks]
    for s in out["sources"]:
        sec = s["section"].strip()
        if sec[:1].isdigit():                       # "2.1" → "§2.1"
            sec = f"§{sec}"
        c = index.get((s["doc_no"], sec))
        if not c:
            problems.append(f"없는 절을 출처로 적음: {s['doc_no']} {s['section']}")
            continue
        src = {"doc_name": c["doc_name"], "doc_no": c["doc_no"], "rev": c["rev"], "section": c["section"]}
        if src not in sources:
            sources.append(src)
    hits = sorted(set(ORIGINAL_SOURCE.findall(out["answer"])))
    if hits:
        problems.append(f"답에 원문 이름이 들어감: {', '.join(hits)} — 사내 문서 번호·절만 쓰고 원문 이름은 빼라")
    used_tools = [t for t in tools if not t["denied"]]
    if out["status"] == "ok" and not sources and not used_tools:
        problems.append("근거(사내 문서 출처나 조회 도구 값) 없이 답함 — 근거를 찾아 sources에 적거나, 없으면 '문서에 없음'")
    related = [r for r in out["related"] if RELATED_ID.match(r.strip())]
    return problems, {"answer": out["answer"].strip(), "sources": sources, "related": related, "status": out["status"]}


def finalize(result, problems, tools):
    """다시 요청한 뒤에도 남은 문제는 프로그램이 정리한다."""
    if any(t["denied"] for t in tools) or result["status"] == "권한 밖":
        result["status"] = "권한 밖"
        if PERMISSION_MESSAGE not in result["answer"]:
            result["answer"] = (result["answer"] + "\n\n" + PERMISSION_MESSAGE).strip()
    if any(p.startswith("답에 원문 이름") for p in problems):      # 원문 이름이 든 줄은 지운다
        result["answer"] = "\n".join(l for l in result["answer"].splitlines() if not ORIGINAL_SOURCE.search(l))
    if any(p.startswith("근거") for p in problems):               # 출처 없는 문서 답은 내지 않는다
        result.update(answer="사내 문서와 운영 기록에서 근거를 찾지 못했습니다.", status="문서에 없음", sources=[])
    return result


# ---------- API-AST-02 POST ----------

def ask(user_id, question, context=None, chat_id=None):
    user = get_user(user_id)
    question = (question or "").strip()
    if not question:
        raise ApiError("VALIDATION", "질문을 입력해 주세요.", 400, {"field": "question"})
    if len(question) > 2000:
        raise ApiError("VALIDATION", "질문은 2,000자까지 쓸 수 있습니다.", 400, {"field": "question"})
    turns = conversation(user_id, chat_id) if chat_id else []
    index = load_index()
    alarm_chunks = alarm_exact_matches(question, index)

    started = time.time()
    tools, feedback, result, problems = [], None, None, []
    with tempfile.TemporaryDirectory() as tmp:
        for attempt in range(2):                      # 처음 + 다시 요청 1번
            audit_path = str(Path(tmp) / f"audit{attempt}.jsonl")
            try:
                out = run_claude(build_prompt(user, question, context, turns, alarm_chunks, feedback),
                                 user["role_code"], audit_path)
            except Exception as e:
                problems = [f"응답 없음: {e}"]
                continue
            tools = read_audit(audit_path)
            problems, result = check(out, index, tools, alarm_chunks)
            if not problems:
                break
            feedback = " / ".join(problems)
    duration_ms = int((time.time() - started) * 1000)

    if result is None:                                # 두 번 다 실패 → 기본 문구 (ASSISTANT_UNAVAILABLE)
        result = {"answer": DEFAULT_ANSWER, "sources": [], "related": [], "status": "응답 없음"}
    else:
        result = finalize(result, problems, tools)
    new_id = save_chat(user, question, context, chat_id, result, tools, duration_ms)
    response = {"chat_id": new_id, **result, "is_synthetic": True}
    if result["status"] == "응답 없음":
        response["error"] = {"code": "ASSISTANT_UNAVAILABLE", "message": DEFAULT_ANSWER, "detail": {"problems": problems}}
    return response


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="이브에게 질문 (구독 Claude)")
    ap.add_argument("question")
    ap.add_argument("--user", default="U02", help="사용자 ID (U01~U12, masters/app_user.csv)")
    ap.add_argument("--chat-id", type=int, help="이어서 물을 앞 채팅 번호")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(ask(a.user, a.question, chat_id=a.chat_id), ensure_ascii=False, indent=2))
