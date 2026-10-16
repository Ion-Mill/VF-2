"""끝에서 끝 확인 — 진짜 백엔드(8010)에 로그인해서 비서에게 몇 가지를 묻는다.

    cd 11_automotive/assistant
    .venv\\Scripts\\python.exe e2e_check.py            # 먼저 아래 "준비"가 되어 있어야 한다

준비 (순서대로):
  1. backend/.env.supabase 의 두 비밀번호(<여기에 …>)를 채운다 — DB 담당에게 받는다
  2. assistant/.env.e2e 의 시연 비밀번호를 채운다 — U01~U12 로그인 비밀번호, DB 담당에게 받는다
  3. 백엔드:  cd backend && .venv\\Scripts\\python.exe tools\\check_connection.py --env-file .env.supabase      (모두 OK 여야 한다)
  4. 백엔드:  cd backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --env-file .env.supabase --port 8010
  5. 비서:    cd assistant && .venv\\Scripts\\python.exe -m uvicorn backend.chat_service:app --host 127.0.0.1 --port 8100

주의 — 이 스크립트는 **팀 공용 DB에 기록을 남긴다**: 로그인 기록(access_log)과 질문·답(chat_log)이 시험 계정(U01·U07)으로 쌓인다. 그래서 질문은 아래
10개로 고정했고 늘리지 않는다 (2026-10-16: 새 형식 문서 질문 2개를 더함). 끝난 뒤 DB 담당에게 U01·U07의 오늘 시험 기록을 지워 달라고 말한다. 비밀번호·토큰은 출력하지 않는다.
시연 되돌리기(SIM-03) 같은 쓰기 API는 부르지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUESTIONS = [
    # (사용자, 질문, 기대 상태, 답에 꼭 있어야 하는 글, 답에 있으면 안 되는 글)
    ("U01", "쿨런트가 뭐야?", "OK", "절삭유", None),                          # 문서 질문 — 전원
    ("U01", "설비 전원 꺼 줘", "REFUSED", None, None),                         # 설비 조작 거절
    ("U01", "VF2-01 MTTR 알려줘", "OUT_OF_ROLE", None, r"\d"),                 # 작업자는 MTTR 값을 못 본다 — 값(숫자) 없음
    ("U01", "재고 부족한 거 알려줘", "OK", None, None),                        # 운영 조회 (작업자 허용 여부는 백엔드 권한표가 정한다)
    ("U07", "VF2-01 OEE 알려줘", "OK", "OEE", None),                           # 보전 담당자 — 지표
    ("U07", "VF2-01 MTTR 알려줘", "OK", "MTTR", None),                         # 보전 담당자는 MTTR 값을 본다
    ("U07", "공구 수명 90% 넘은 거 있어?", "OK", None, None),
    ("U07", "9월 알람 2075 몇 번 났어", "OK", "2075", None),
    # 추가 묶음(순수 외부 LLM + 말투·형식)이 켜져 있으면 소제목(■)·번호 목록으로 나온다. 꺼져 있어도 OK 이므로 상태만 본다
    ("U01", "윤활유가 부족하면 어떻게 해?", "OK", None, None),
    ("U01", "잠금 표지 순서가 어떻게 돼?", "OK", "주의", None),                # 안전 질문 — 끝에 안전 문구(주의: …)가 붙어야 한다
]


def load_env(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def call(base: str, path: str, body: dict | None = None, token: str | None = None):
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET",
                                 data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=150) as r:     # 외부 Claude는 한 질문에 20초 넘게 걸릴 수 있다 (비서 서비스의 시간 예산 120초)
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": type(e).__name__}


def main() -> int:
    envp = HERE / ".env.e2e"
    if not envp.exists():
        print("assistant/.env.e2e 가 없다"); return 2
    env = load_env(envp)
    pw, base = env.get("MOM_E2E_LOGIN_PASSWORD", ""), (os.environ.get("MOM_E2E_BACKEND") or env.get("MOM_E2E_BACKEND", "http://127.0.0.1:8010")).rstrip("/")
    if not pw or "<" in pw:
        print("assistant/.env.e2e 의 MOM_E2E_LOGIN_PASSWORD 를 채워야 한다 (DB 담당이 알려 주는 시연 비밀번호)"); return 2
    if not base.startswith("http://127.0.0.1") and not base.startswith("http://localhost"):
        print("이 확인은 내 PC의 백엔드(127.0.0.1)에만 쓴다"); return 2

    code, h = call(base, "/api/health")
    print(f"백엔드 {base}: {'응답함' if code else '응답 없음'}")
    if not code:
        return 3

    tokens: dict[str, tuple[str, str]] = {}
    for uid in sorted({q[0] for q in QUESTIONS}):
        code, j = call(base, "/api/auth/login", {"user_id": uid, "password": pw})
        if code != 200:
            print(f"로그인 실패 {uid}: HTTP {code} — 비밀번호나 계정을 확인한다"); return 4
        tokens[uid] = (j["access_token"], j["role_code"])
        print(f"로그인 {uid} → 역할 {j['role_code']}")

    bad = 0
    for uid, q, want, must, never in QUESTIONS:
        t0 = time.time()
        code, j = call(base, "/api/assistant/chat", {"question": q, "context": {"screen": "SCR-10"}}, tokens[uid][0])
        took = time.time() - t0
        status, ans = j.get("status"), (j.get("answer") or "")
        ok = code == 200 and status == want and (must is None or must in ans) and (never is None or not re.search(never, ans))
        if not ok:
            bad += 1
        src = [(s.get("doc_no"), s.get("section")) for s in (j.get("sources") or [])][:2]
        print(f"{'OK  ' if ok else 'FAIL'} [{uid}/{tokens[uid][1]}] {q!r} → HTTP {code} {status} (기대 {want}) {took:.1f}초 chat_id={j.get('chat_id')} 출처={src}")
        print(f"       {ans[:90]!r}")
    print(f"\n{len(QUESTIONS) - bad}/{len(QUESTIONS)} 맞음" + ("" if bad == 0 else " — FAIL 줄을 본다 (비서 서비스 로그·백엔드 로그)"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
