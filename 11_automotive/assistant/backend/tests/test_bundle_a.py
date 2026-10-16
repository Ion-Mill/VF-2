"""묶음 A (UI설계서 16:00판): 알림·지침카드·고정 안전 서식·SCR-24 본문·비서 안내·SSE 거르기·권한."""
import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import DOCS_DIR
from backend.demo_state import DemoState, get_state
from backend.rag.doc_view import doc_body, doc_list
from backend.rag.sanitize import FORBIDDEN
from backend.safety import templates as S
from backend.services import notifications as N
from backend.services.answer import answer

client = TestClient(app)


def H(role, user=""):
    return {"X-Role": role, "X-User": user}


@pytest.fixture(autouse=True)
def fresh_state():
    get_state().reset()
    yield
    get_state().reset()


# ------------------------------------------------------------ 고정 안전 서식
def _doc05_block() -> list[str]:
    raw = next(DOCS_DIR.glob("DOC-05_*.md")).read_text(encoding="utf-8")
    sec7 = raw.split("## 7. 작업지시서에 붙는 고정 서식")[1]
    body = sec7.split("```")[1].strip("\n").splitlines()
    return [l for l in body if not l.startswith("━")]


def test_safety_block_matches_doc05_except_kosha_names():
    block = S.stop_block("VF2-01")
    got = S.render_text(block)
    want = _doc05_block()
    for pat, rep in S.KOSHA_STRIPS:
        want = [pat.sub(rep, l) for l in want]
    # 설비·차단 지점·저장 에너지 칸만 채운 것이 다르다
    want = [l for l in want if not l.startswith(("설비:", "저장 에너지:"))]
    got = [l for l in got if not l.startswith(("설비:", "저장 에너지:"))]
    assert [l.rstrip() for l in got] == [l.rstrip() for l in want]
    assert not any("KOSHA" in l or "Haas" in l for l in S.render_text(block))
    assert block["loto_steps"] == ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "7.1", "7.2", "7.3"]


def test_high_voltage_line_only_op30():
    assert any(s["head"].startswith("[고전압 대기]") for s in S.stop_block("VF2-02")["sections"])
    other = S.stop_block("SAW-01")
    assert not any("고전압" in s["head"] for s in other["sections"])
    assert any(s["head"] == "§3 저장 에너지 확인" for s in other["sections"])


def test_isolation_points_from_doc05_no_invented_ids():
    pts = S.isolation("VF2-01")["points"]
    assert pts and all(re.match(r"VF2-01-[EP]\d ", p) for p in pts)
    assert not any("Breaker 4" in p or "P-01" in p for p in pts)


def test_short_task_2075_from_doc05_24():
    s = S.short_task("2075", "VF2-02")
    assert s["line"].startswith("축 윤활유 저장소 보충 (알람 2075)") and "보충용 2점 잠금" in s["line"]
    assert "VF2-02-E1" in s["detail"] and "VF2-0x" not in s["detail"]


# ------------------------------------------------------------ 알림
def test_initial_notifications_and_24h_rank():
    r = client.get("/api/notifications", headers=H("MGR", "MGR-01")).json()
    open_ = {n["id"]: n for n in r["notifications"] if not n["processed"]}
    assert open_["N-ALM-00279"]["rank"] == "0-1" and open_["N-ALM-00279"]["over_24h"]
    assert "N-TOOL-VF2-01-T05" in open_ and open_["N-TOOL-VF2-01-T05"]["rank"] == "3"
    # 같은 설비·같은 원인(2075 알람 + 반복 1단계)은 한 줄로 센다
    line = next(l for l in r["report"]["lines"] if "N-ALM-00279" in l["ids"])
    assert set(line["ids"]) == {"N-ALM-00279", "N-RPT-VF2-02-2075-1"} and line["rank"] == "0-1" and not line["folded"]
    assert r["report"]["total"] == len(r["report"]["lines"]) < r["unprocessed"]


def test_receivers_filter():
    sup = {n["id"] for n in client.get("/api/notifications", headers=H("SUP", "SUP-01")).json()["notifications"]}
    mnt = {n["id"] for n in client.get("/api/notifications", headers=H("MNT", "MNT-01")).json()["notifications"]}
    assert "N-INV-TL-TAP6" in sup and "N-INV-TL-TAP6" not in mnt          # 공구는 SUP 관리
    assert "N-INV-CS-WLUB" in mnt and "N-INV-CS-WLUB" not in sup          # 정비 소모품은 MNT 관리
    opr_other = {n["id"] for n in client.get("/api/notifications", headers=H("OPR", "OPR-01")).json()["notifications"]}
    assert not any(i.startswith("N-ALM-00279") for i in opr_other)        # OP-10·20 작업자에게 OP-30 알람 없음


def test_monitoring_account_denied_alerts_and_cards():
    # 주소는 2026-10-11 P4에서 명세 이름으로 바꿈 (옛 /api/guide-cards/…, /api/docs). 코드 FORBIDDEN
    assert client.get("/api/notifications", headers=H("MON", "MON-01")).status_code == 403
    assert client.get("/api/maint/guide-card/ALM-00279", headers=H("MON")).json()["code"] == "FORBIDDEN"
    assert client.get("/api/internal-docs", headers=H("MON")).status_code == 403


def test_user_role_mismatch_denied():
    # 원래 기대값 403 → 2026-10-11 P4에서 401 UNAUTHORIZED: 사용자와 역할이 다른 것은 권한이 아니라 로그인 문제로 본다 (backend/errors.py)
    r = client.get("/api/notifications", headers=H("MGR", "OPR-02"))
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED"


def test_process_rules():
    # 주소·칸은 2026-10-11 P4에서 명세 NTF-03 이름으로 (옛 …/process + plan → …/resolve + action_plan)
    # 반복 1단계: 조치 계획 필수, MNT·SUP만. 조치 계획 없음의 원래 기대값 409 → 422 VALIDATION (값이 빠짐)
    r = client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": ""}, headers=H("SUP", "SUP-01"))
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"
    assert client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": "x"}, headers=H("OPR", "OPR-02")).status_code == 404
    ok = client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": "체크밸브 점검 후 보충"}, headers=H("SUP", "SUP-01"))
    assert ok.status_code == 200
    again = client.post("/api/notifications/N-RPT-VF2-02-2075-1/resolve", json={"action_plan": "y"}, headers=H("MNT", "MNT-01"))
    assert again.status_code == 409 and again.json()["code"] == "INVALID_STATE"
    # 주의 알람은 사람이 [처리]하지 않는다 (간이 작업기록 확정 때 자동) — 설명은 message 칸 (옛 detail 글자)
    r = client.post("/api/notifications/N-ALM-00279/resolve", json={}, headers=H("SUP", "SUP-01"))
    assert r.status_code == 409 and "자동" in r.json()["message"]


def test_bundle_one_minute_and_storm():
    t0 = datetime(2026, 10, 1, 9, 0)
    rows = [{"equipment_id": "VF2-01", "axis": "", "code": "120", "sub": "", "occurred_at": (t0 + timedelta(seconds=s)).isoformat()}
            for s in (0, 20, 40, 300)]
    groups = N.bundle_groups(rows)
    assert sorted(len(g) for g in groups) == [1, 3]
    times = [t0 + timedelta(seconds=30 * i) for i in range(11)]
    now = times[-1]
    assert N.storm_state(times, now, False) is True                   # 10분 안 11건
    assert N.storm_state(times[:6], now, True) is True                # 5건 이상이면 유지
    assert N.storm_state(times[:4], now, True) is False               # 5건 아래면 풀림
    assert N.storm_state(times[:10], now, False) is False             # 10건은 넘지 않음


# ------------------------------------------------------------ 시나리오·SSE 거르기·지침카드
def test_scenario_s1_popup_targets_and_card():
    # 주소는 2026-10-11 P4에서 명세 SIM-01로 (옛 POST /api/demo/scenario/S1)
    r = client.post("/api/sim/inject", json={"scenario_code": "S1"}, headers=H("MNT", "MNT-01"))
    assert r.status_code == 200 and r.json()["added"] == ["ALM-S1-01", "ALM-S1-02", "ALM-S1-03"]
    again = client.post("/api/sim/inject", json={"scenario_code": "S1"}, headers=H("MNT", "MNT-01"))
    assert again.status_code == 409 and again.json()["code"] == "INVALID_STATE"
    st = get_state()
    pops = [e for e in st.events if e["type"] == "urgent_popup"]
    assert len(pops) == 2 and all(e["users"] == {"OPR-02", "MNT-01", "MNT-02"} for e in pops)  # 주간 OP-30 작업자 + 주간 보전
    got, _ = st.events_after(0, "OPR", "OPR-01")
    assert not any(e["type"] == "urgent_popup" for e in got)          # 다른 공정 작업자에게 팝업 없음
    got, seen = st.events_after(0, "OPR", "OPR-02")
    assert sum(e["type"] == "urgent_popup" for e in got) == 2 and seen == len(st.events)
    assert st.events_after(seen, "OPR", "OPR-02")[0] == []            # 다시 이으면 중복 없음

    card = client.get("/api/maint/guide-card/ALM-S1-03", headers=H("OPR")).json()   # 명세 MNT-01 주소 (2026-10-11 P4)
    order = ["alarm", "severity", "who", "chain", "first_steps", "safety", "production", "history", "buttons", "sources"]
    assert [k for k in card if k in order] == order                    # 6.1 칸 순서
    assert card["key"] == "1.992" and card["chain"]["codes"] == ["108", "994", "992"]
    assert all(s["operator"] for s in card["first_steps"]["items"]) and card["first_steps"]["items"][0]["no"] == "★1"
    assert card["safety"]["kind"] == "block" and card["safety"]["equipment_id"] == "VF2-01"
    assert card["production"]["order"] == "PO-2609-112" and "(추정)" in card["production"]["formula"]
    assert not FORBIDDEN.search(str(card))


def test_guide_card_grades():
    warn = client.get("/api/maint/guide-card/ALM-00279", headers=H("OPR")).json()
    assert warn["safety"]["kind"] == "short"
    guide_id = next(a["alarm_event_id"] for a in get_state().alarms() if a["severity"] == "GUIDE")
    g = client.get(f"/api/maint/guide-card/{guide_id}", headers=H("OPR")).json()
    assert g["safety"]["kind"] == "none" and "적용 대상이 아닙니다" in g["safety"]["line"]
    assert [b["label"] for b in g["buttons"]] == ["더 묻기"]
    missing = client.get("/api/maint/guide-card/ALM-XXXX", headers=H("OPR"))
    assert missing.status_code == 404 and missing.json()["code"] == "NOT_FOUND"


# ------------------------------------------------------------ SCR-24
def test_doc_body_has_no_original_sources():
    docs = doc_list()
    assert len(docs) == 8
    # 원래 꼴의 `\(Haas`(괄호가 "(Haas"로 시작하면 모두 실패)를 2026-10-11에 원문 이름 괄호만으로 좁혔다:
    # 부품번호 "(Haas P/N 58-1391 …)"·서비스 "(Haas HFO 등)"·버튼 "(Haas: [POWER OFF])"는 원문 출처가 아니라 보여야 한다.
    # 원문 이름 전체 검사는 test_haas_names.py (따로 쓴 엄격한 꼴)
    bad = re.compile(r"\b(?:TG|RD|AD|ID)\d{4}\b|96-8210|haascnc|https?://|KOSHA\s*(?:GUIDE\s*)?B-M-|\d+쪽|CSV \d+행"
                     r"|\(Haas[^)]*(?:안내|매뉴얼|목록|Safety|Manual|Guide)|__\d{8}__|지침장")
    for d in docs:
        for s in doc_body(d["doc_id"])["sections"]:
            assert not bad.search(s["text"] + s["title"]), (d["doc_id"], s["section"], bad.search(s["text"] + s["title"]).group(0))
    hidden = [s for s in doc_body("DOC-05")["sections"] if s["hidden"]]
    assert any("원문 대응표" in s["title"] for s in hidden)


# ------------------------------------------------------------ 비서 안내 (SCR-10 [4], 상태 표)
@pytest.mark.parametrize("q", ["VF2-01 켜 줘", "주축 속도 올려 줘", "파라미터 바꿔 줘"])
def test_control_requests_refused(q):
    a = answer(q, "OPR")
    assert a["status"] == "안내" and "설비를 조작하지 않습니다" in a["conclusion"]


def test_human_only_requests_give_link_without_state_change():
    a = answer("작업지시서 승인해 줘", "SUP")
    assert a["status"] == "안내" and "반장" in a["conclusion"] and a["links"][0]["screen"] == "SCR-11"
    a = answer("알림 처리해 줘", "MNT")
    assert a["links"][0]["screen"] == "SCR-07" and a["links"][0]["enabled"]


def test_context_alarm_and_screen_help():
    a = answer("이 알람 뭐부터 봐?", "OPR", {"screen": "SCR-09", "alarm_key": "1.992"})
    assert a["status"] == "답변" and "992" in a["conclusion"] and a["evidence"][0]["doc_id"] in ("DOC-02", "DOC-03")
    h = answer("이 화면 설명해 줘", "OPR", {"screen": "SCR-09"})
    assert h["status"] == "안내" and "고정 서식" in h["conclusion"]


def test_examples_endpoint():
    r = client.get("/api/assistant/examples?screen=SCR-09&alarm=1.992", headers=H("OPR")).json()
    assert "1.992 뜨면 뭐부터 봐?" in r["examples"]


def test_demo_state_reset_isolated():
    st = DemoState()
    assert st.now.isoformat().startswith("2026-10-01T08:00")


def test_login_list_hides_monitoring_account():
    """UI설계서 9.5 #20 (2026-10-08 갱신판): 로그인 사용자는 가상 12명, 모니터링 계정은 추가 예정이라 숨긴다."""
    users = client.get("/api/users").json()["users"]
    assert len(users) == 12 and not any(u["role"] == "MON" for u in users)
    assert sorted({u["role"] for u in users}) == ["MGR", "MNT", "OPR", "SUP"]
