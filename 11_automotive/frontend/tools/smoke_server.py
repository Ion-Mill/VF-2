"""시연 데이터 서버의 읽기(GET) 길을 한 번씩 불러 500 오류가 없는지 본다 — 켜 놓은 채로 어느 프로필이든 (쓰는 길을 누르지 않아 시연 중에도 괜찮다).
실행: ../생성기/.venv/Scripts/python tools/smoke_server.py [포트]   (2026-10-24, 재고 화면 500 오류를 놓쳤던 뒤에 만듦)"""
import json
import sys
import urllib.error
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8765"
BASE = f"http://127.0.0.1:{PORT}/api/"


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None


h = get("health")[1]
prof = h["profile"]
last = get("reports/daily")[1]["reports"][-1]["work_date"]
paths = ["health", "sim/clock", "stream/events?after=0", "line/twin", "production/target", "kpi", "production/orders", "downtimes",
         "notifications/past-open", "internal-docs", "internal-docs/search?q=992", "internal-docs/DOC-03/sections/2.1", "maint/pm-schedule",
         "maint/history", "reports/shift", "reports/daily", f"reports/daily/{last}", f"reports/shift/{last}-N", "documents/revisions",
         "lots", "inspection/cmm-imports", "quality/summary", "inventory", "shipments", "tools", "settings", "users",
         "replay?from=" + prof["live_start"] + ":00%2B09:00&to=" + prof["live_start"][:11] + "23:00:00%2B09:00"]
bad = []
for p in paths:
    s, _ = get(p)
    print(("OK " if s == 200 else "!! "), s, p)
    if s >= 500:
        bad.append(p)
print("500 오류:", bad or "없음")
sys.exit(1 if bad else 0)
