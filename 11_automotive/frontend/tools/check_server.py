"""시연 데이터 서버 자가 점검 — 서버를 켠 채로 실행: python tools/check_server.py
처음으로(reset)를 부르므로 시연 중에는 돌리지 말 것."""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765/api/"


def call(path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def ok(path, body=None):
    s, j = call(path, body)
    assert s == 200, (path, s, j)
    return j


ok("sim/reset", {})
ok("sim/clock", {"speed": 180})
for p in ["health", "line/twin", "production/target", "kpi", "production/orders", "downtimes", "notifications/past-open",
          "internal-docs", "internal-docs/search?q=994", "internal-docs/DOC-03/sections/2.1", "maint/pm-schedule", "maint/history",
          "reports/shift", "reports/daily", "reports/daily/2026-09-30", "reports/shift/2026-09-30-N", "documents/revisions",
          "lots", "inspection/cmm-imports", "quality/summary", "inventory", "shipments", "tools", "settings", "users",
          "replay?from=2026-10-01T08:00:00%2B09:00&to=2026-10-01T09:00:00%2B09:00"]:
    ok(p)

# 잘못된 몸통은 400 (서버가 죽지 않음)
assert call("assistant/chat", raw="{\"question\": \"\xbe\"}".encode("latin-1"))[0] == 400
# 권한: 작업자는 MTTR 못 봄, 정비는 봄
assert ok("assistant/chat", {"question": "VF2-01 MTTR", "role": "OPR"})["status"] == "권한 밖"
assert "MTTR" in ok("assistant/chat", {"question": "VF2-01 MTTR", "role": "MNT"})["answer"]
# 권한: 설정은 MGR만, 출하는 SUP만
assert call("settings", {"role": "OPR", "user_id": "x", "shift_target": 80})[0] == 403
assert call("shipments", {"role": "OPR", "lot_no": "x", "qty": 1})[0] == 403

# S6 정비 → VF2-02 MAINT, 진행 중엔 다른 사건 잠김
for _ in range(60):  # 대상 설비가 가공 중일 때만 받음 (409) → 시계가 흐르며 다시 시도
    if call("sim/inject", {"scenario_code": "S6"})[0] == 200:
        break
    time.sleep(0.5)
for _ in range(40):
    t = ok("line/twin")
    if t["equipment"]["VF2-02"]["state_code"] == "MAINT":
        break
    time.sleep(0.5)
assert t["equipment"]["VF2-02"]["state_code"] == "MAINT", t["equipment"]["VF2-02"]
assert t["buttons"]["S4"], "사건 진행 중엔 S4 잠김이어야 함"
assert call("sim/inject", {"scenario_code": "S4"})[0] >= 400

ok("sim/reset", {})
print("check_server: OK")
