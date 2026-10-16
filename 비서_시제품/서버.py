"""이브 시제품 서버 — API-AST-02 (채팅), API-DOCS-01 (출처 요약 카드·본문), API-MNT-01 (지침카드).

  POST /api/assistant/chat                          질문 {question, context?, chat_id?}
  GET  /api/assistant/chat?days=30                  내 채팅 기록 (본인 것만, 30일)
  GET  /api/internal-docs/{doc_no}/sections/{section}?view=card|full
  GET  /api/maint/guide-card/{alarm_event_id}       알람 지침카드 (API-MNT-01)
  GET  /api/test/guide-card?alarm_code=992          시험용: 알람 번호의 가장 최근 기록 카드
  GET  /api/test/alarm-events?limit=40              시험용: 최근 알람 기록 목록
  GET  /                                            시험용 채팅 화면 (실제 UI 아님)

로그인(API-AUTH-01)은 아직 없으므로 `X-User-Id` 헤더로 사용자를 정한다 [제안: 시제품 전용].
서버 프레임워크는 [선택 필요: 기술 회의] — 표준 라이브러리만 쓴 시제품이다.

실행: python 비서_시제품/서버.py  →  http://127.0.0.1:8765
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import 비서
import 지침카드
from 문서조각 import load_index

HOST, PORT = "127.0.0.1", 8765
PAGE = Path(__file__).with_name("시험화면.html")


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError:            # 답을 기다리던 화면이 먼저 닫힘 (답은 채팅 기록에 남아 있음)
            self.log_message("손님이 먼저 연결을 끊음: %s", self.path)

    def fail(self, err):
        self.send_json(err.http_status, err.to_dict())

    def user_id(self):
        uid = self.headers.get("X-User-Id")
        if not uid:
            raise 비서.ApiError("UNAUTHORIZED", "로그인 정보가 없습니다.", 401)
        return uid

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        parts = [unquote(p) for p in url.path.strip("/").split("/")]
        try:
            if url.path == "/":
                body = PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/assistant/chat":
                days = int(query.get("days", ["30"])[0])
                self.send_json(200, 비서.history(self.user_id(), days))
            elif len(parts) == 5 and parts[:2] == ["api", "internal-docs"] and parts[3] == "sections":
                self.user_id()
                self.send_json(200, section(parts[2], parts[4], query.get("view", ["card"])[0]))
            elif len(parts) == 4 and parts[:3] == ["api", "maint", "guide-card"]:      # API-MNT-01
                비서.get_user(self.user_id())
                self.send_json(200, 지침카드.card_for_event(parts[3]))
            elif url.path == "/api/test/guide-card":                                  # 시험용: 알람 번호로
                비서.get_user(self.user_id())
                self.send_json(200, 지침카드.card_for_code(query.get("alarm_code", [""])[0].strip()))
            elif url.path == "/api/test/alarm-events":                                # 시험용: 최근 알람 기록
                self.send_json(200, 지침카드.recent_events(int(query.get("limit", ["40"])[0])))
            else:
                raise 비서.ApiError("NOT_FOUND", "없는 주소입니다.", 404)
        except 비서.ApiError as e:
            self.fail(e)
        except ValueError:
            self.fail(비서.ApiError("VALIDATION", "값이 틀렸습니다.", 400))
        except Exception as e:
            self.log_message("오류: %r", e)
            self.fail(비서.ApiError("INTERNAL", "서버 오류가 났습니다.", 500))

    def do_POST(self):
        try:
            if urlparse(self.path).path != "/api/assistant/chat":
                raise 비서.ApiError("NOT_FOUND", "없는 주소입니다.", 404)
            uid = self.user_id()
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                raise 비서.ApiError("VALIDATION", "JSON 형식이 틀렸습니다.", 400)
            chat_id = body.get("chat_id")
            self.send_json(200, 비서.ask(uid, body.get("question"), body.get("context"),
                                         int(chat_id) if chat_id else None))
        except 비서.ApiError as e:
            self.fail(e)
        except Exception as e:             # 예상 못 한 오류도 정해진 오류 형식으로
            self.log_message("오류: %r", e)
            self.fail(비서.ApiError("ASSISTANT_UNAVAILABLE", 비서.DEFAULT_ANSWER, 500))

    def log_message(self, fmt, *args):
        sys.stderr.write("[서버] " + fmt % args + "\n")


def section(doc_no, sec, view):
    """API-DOCS-01: card = 문서 이름·번호·개정·절 제목 + 앞 2~3줄 / full = 절 본문 (원문 출처 뺀 사본)."""
    c = load_index().get((doc_no, sec if sec.startswith("§") else f"§{sec}"))
    if not c:
        raise 비서.ApiError("NOT_FOUND", "없는 문서 절입니다.", 404, {"doc_no": doc_no, "section": sec})
    data = {k: c[k] for k in ("doc_name", "doc_no", "rev", "section", "title")}
    data["preview" if view == "card" else "text"] = c["preview"] if view == "card" else c["text"]
    return data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    load_index()
    print(f"이브 시제품 서버: http://{HOST}:{PORT}  (끝내려면 Ctrl+C)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
