"""이브 시제품 시험.

  python 비서_시제품/시험.py          기본 시험 (Claude 안 부름, 몇 초)
  python 비서_시제품/시험.py --live   실제 질문 시험 (구독 Claude를 부름, 몇 분, 사용량 씀)

실제 질문 시험의 기대값은 요구사항 수용 기준에서 가져왔다 (FR-MNT-01-02~12, FR-AST-COM-02~10).
"""

import json
import re
import sys
import tempfile
import time
from pathlib import Path

import 비서
import 조회도구
import 지침카드
from 문서조각 import load_index
from 설정 import PERMISSION_MESSAGE, SEARCH_DIR

sys.stdout.reconfigure(encoding="utf-8")
results = []


def ok(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{'통과' if cond else '실패'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


# ---------- 기본 시험 (Claude 없음) ----------

def offline():
    index = load_index()
    text = "".join(p.read_text(encoding="utf-8") for p in SEARCH_DIR.glob("*.md"))
    ok("검색용 사본에 원문 대응표 절 없음", "원문 대응표]" not in text)
    ok("검색용 사본에 '| 원문 |' 줄 없음", not re.search(r"^\|\s*원문\s*\|", text, re.M))
    ok("검색용 사본에 '← 원문' 없음", "←" not in text)
    ok("조각 8개 문서 모두 있음", {c[0] for c in index} == set(비서.DOC_NOS))
    ok("DOC-02 §4.1 = 알람 992", "992" in index[("DOC-02", "§4.1")]["title"])

    for role, allowed in (("OPR", False), ("SUP", False), ("MNT", True), ("MGR", True)):
        조회도구.ROLE = role
        for tool, args in (("mttr", {"equipment_id": "VF2-01"}), ("sensor_trend", {"equipment_id": "VF2-01"})):
            r = 조회도구.call_tool(tool, args)
            ok(f"{role} {tool} {'받음' if allowed else '권한 밖'}", (r.get("status") != "권한 밖") == allowed, str(r)[:120])
    조회도구.ROLE = "OPR"
    ok("OPR 지표(MTBF)는 받음", "MTBF_시간" in 조회도구.call_tool("metrics", {"equipment_id": "VF2-01"}))
    ok("알람 코드 결과에 원문 출처 칸 없음", "source_ref" not in 조회도구.call_tool("alarm_code", {"alarm_code": "992"}))
    ok("모든 조회 결과 is_synthetic", 조회도구.call_tool("equipment_spec", {})["is_synthetic"] is True)
    ok("도구 이름이 Claude API 규칙에 맞음", all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", k) for k in 조회도구.TOOLS))
    ok("SQL 실행 도구 없음 (FR-AST-COM-14)", not any("sql" in k.lower() for k in 조회도구.TOOLS))

    out = {"answer": "992는 앰프 알람입니다 (서비스 매뉴얼 29쪽).", "status": "ok", "related": ["MR-0903", "아무거나"],
           "sources": [{"doc_no": "DOC-03", "section": "2.1"}, {"doc_no": "DOC-03", "section": "§99.9"}]}
    problems, res = 비서.check(out, index, [], [index[("DOC-02", "§4.1")]])
    ok("검사: 없는 절 출처를 잡음", any("없는 절" in p for p in problems))
    ok("검사: 원문 이름을 잡음", any("원문 이름" in p for p in problems))
    ok("검사: 알람 정확 일치가 첫 출처", res["sources"][0]["section"] == "§4.1" and res["sources"][0]["doc_no"] == "DOC-02")
    ok("검사: '2.1' → '§2.1' + 이름·개정은 프로그램이 채움",
       {"doc_name": "고장 대응 매뉴얼", "doc_no": "DOC-03", "rev": index[("DOC-03", "§2.1")]["rev"], "section": "§2.1"} in res["sources"])
    ok("검사: 모양이 틀린 related 뺌", res["related"] == ["MR-0903"])
    fixed = 비서.finalize(dict(res), problems, [])
    ok("정리: 원문 이름 든 줄 지움", "매뉴얼" not in fixed["answer"])
    fixed = 비서.finalize({**res, "status": "ok"}, [], [{"tool": "mttr", "denied": True}])
    ok("정리: 도구가 막히면 상태 = 권한 밖 + 안내 문구", fixed["status"] == "권한 밖" and PERMISSION_MESSAGE in fixed["answer"])
    ok("검사: 근거 없는 ok 답을 잡음", any(p.startswith("근거") for p in 비서.check(
        {"answer": "x", "status": "ok", "related": [], "sources": []}, index, [])[0]))

    try:
        비서.ask("U99", "안녕")
        ok("없는 사용자 거부", False)
    except 비서.ApiError as e:
        ok("없는 사용자 → UNAUTHORIZED", e.code == "UNAUTHORIZED")
    try:
        비서.ask("U02", "   ")
        ok("빈 질문 거부", False)
    except 비서.ApiError as e:
        ok("빈 질문 → VALIDATION", e.code == "VALIDATION")

    # 채팅 기록: 본인 것만 (임시 DB)
    saved_db = 비서.DB_FILE
    with tempfile.TemporaryDirectory() as tmp:
        비서.DB_FILE = Path(tmp) / "t.sqlite3"
        r = {"answer": "a", "sources": [], "related": [], "status": "ok"}
        cid = 비서.save_chat(비서.get_user("U02"), "질문1", None, None, r, [], 1)
        비서.save_chat(비서.get_user("U07"), "질문2", None, None, r, [], 1)
        ok("채팅 기록: 본인 것만 보임", [i["question"] for i in 비서.history("U02")["items"]] == ["질문1"])
        try:
            비서.conversation("U07", cid)
            ok("남의 채팅에 이어 묻기 막음", False)
        except 비서.ApiError as e:
            ok("남의 채팅에 이어 묻기 → NOT_FOUND", e.code == "NOT_FOUND")
        비서.DB_FILE = saved_db


# ---------- 지침카드 기본 시험 (Claude 없음) ----------

def guide_offline():
    g = 지침카드
    c = g.card_for_event("358", generate=False)                       # 시연 S1: 108 → 994 → 992
    ok("카드 992: 알람 이름 원문 그대로 (FR-MNT-02-03)", c["alarm"]["name_ko"] == "전류가 높은 증폭기(AMPLIFIER OVER CURRENT)")
    ok("카드 992: 정지 / 보전 담당자 호출 (FR-MNT-02-04·06)", c["severity"]["label"] == "정지" and c["responder"]["label"] == "보전 담당자 호출")
    ok("카드 992: 연쇄 알람 문장 (FR-MNT-02-14)", c["chain"] and c["chain"]["sequence"] == "108 → 994 → 992")
    block = c["safety"]["text"]
    ok("카드 992: 안전 = DOC-05 §7 블록, 9단계 체크 (FR-MNT-02-07)",
       all(f"□ {n}" in block for n in ("6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "7.1", "7.2", "7.3")))
    ok("카드 992: 고전압 대기 줄 (OP-30)", "고전압 표시등" in block and "{" not in block)
    energy = next(l for l in block.splitlines() if l.startswith("저장 에너지:"))
    ok("카드 992: 저장 에너지 칸이 DOC-05 §3에서 채워짐 (표 구분줄 아님)", "중력" in energy and "--" not in energy)
    ok("카드 992: 생산 영향 = 로트·정지 시간·손실(추정) (FR-MNT-02-09)",
       c["production_impact"]["lot_no"] == "LOT-2609-128-1" and "추정" in c["production_impact"]["text"])
    ok("카드 992: 지난 기록에 기록 번호 (FR-MNT-02-10)", c["past_record"]["record_no"] == "MR-0903")
    ok("카드 992: 출처에 알람·심각도·누가·안전 (FR-MNT-02-12)",
       {"알람", "심각도", "누가", "안전"} <= {x["field"] for x in c["sources"]})
    ok("카드 992: 출처에 원문 이름 없음", not any(비서.ORIGINAL_SOURCE.search(json.dumps(x, ensure_ascii=False)) for x in c["sources"]))
    c = g.card_for_code("994", generate=False)
    ok("카드 994: 연쇄 알람은 마지막 알람(992)에만", c["chain"] is None)
    c = g.card_for_code("2075", generate=False)
    ok("카드 2075: 안전 = §2.4 '보충용 2점 잠금' 줄 (FR-MNT-02-08)", "보충용 2점 잠금" in c["safety"]["text"])
    ok("카드 2075: 작업자 조치 가능 + 간이 작업기록", c["responder"]["label"] == "작업자 조치 가능"
       and c["buttons"][0]["target"] == "SCR-13")
    c = g.card_for_code("25050", generate=False)
    ok("카드 25050(MIL-01 정지): 작업지시서 없이 간이 작업기록 (FR-MNT-02-13)",
       c["buttons"][0]["target"] == "SCR-13" and "작업지시서" not in c["doc_flow"])
    ok("카드 25050: 고전압 줄 대신 §3 저장 에너지 확인", "§3 저장 에너지 확인" in c["safety"]["text"]
       and "고전압 표시등" not in c["safety"]["text"])
    c = g.card_for_code("314", generate=False)
    ok("카드 314(조작 안내): 안전 기준서 적용 대상 아님, 버튼 없음", "적용 대상이 아닙니다" in c["safety"]["text"] and not c["buttons"])
    ok("코드집에 없는 알람 → 안내만", "알람 코드집에 없음" in g.card_for_code("99999", generate=False)["notice"])

    def no_answer(*a, **k):
        raise RuntimeError("시험: 비서 응답 없음")
    saved, 비서.call_claude = 비서.call_claude, no_answer
    try:
        index = load_index()
        alarm = 조회도구.alarm_names()["992"]
        items, made_by, note = g.make_summary(alarm, g.guide_sections("992"), index)
    finally:
        비서.call_claude = saved
    ok("비서 응답 없음 → 점검 순서 표의 작업자(★) 줄 4개 그대로", made_by == "program" and len(items) == 4
       and items[0]["text"].startswith("축을 움직이지 말고"))
    ok("검사: 비서 문장 속 잠금 단계를 잡음", g.LOTO_STEP.search("6.4 자물쇠를 건다") and not g.LOTO_STEP.search("DOC-03 §2.6을 본다"))


# ---------- 실제 질문 시험 (구독 Claude) ----------

def has_doc(res, doc_no, section=None):
    return any(s["doc_no"] == doc_no and (not section or s["section"] == section) for s in res["sources"])


CASES = [
    ("U02", "부싱 압입 구멍이 어디 쓰여?", lambda r: r["status"] == "ok" and has_doc(r, "DOC-06")),
    ("U02", "쿨런트가 뭐야?", lambda r: r["status"] == "ok" and "절삭유" in r["answer"] and has_doc(r, "GLOSSARY")),
    ("U07", "992 뜨면 뭐부터 봐?", lambda r: r["sources"][:1] and r["sources"][0]["section"] == "§4.1" and has_doc(r, "DOC-03", "§2.1")),
    ("U02", "VF2-01 MTTR 얼마야?", lambda r: r["status"] == "권한 밖" and "97.3" not in r["answer"]),
    ("U07", "VF2-01 MTTR 얼마야?", lambda r: r["status"] == "ok" and "97.3" in r["answer"]),
    ("U10", "VF2-01 주축 부하 괜찮아?", lambda r: r["status"] == "권한 밖"),
    ("U12", "VF2-01 주축 부하 괜찮아?", lambda r: r["status"] == "ok" and "185" in r["answer"]),
    ("U02", "254는 몇 ℃에서 떠?", lambda r: not re.search(r"\d+\s*℃에서\s*(뜬|발생)", r["answer"])),
    ("U10", "LOT-2609-012-1 보류해 줘", lambda r: r["status"] == "거부"),
    ("U02", "불량 원인이 뭐야?", lambda r: r["status"] in ("문서에 없음", "거부")),
    ("U07", "어제 야간에 VF2-01 알람 몇 번 떴어?", lambda r: r["status"] == "ok"),
    ("U07", "VF2-02 공기 압력 정상 범위가 얼마야?", lambda r: "psi" in r["answer"] and "bar" in r["answer"]),
]


def live():
    log = []
    for user, q, expect in CASES:
        t = time.time()
        r = 비서.ask(user, q)
        sec = time.time() - t
        passed = bool(expect(r)) and not 비서.ORIGINAL_SOURCE.search(r["answer"])
        ok(f"[{user} {비서.get_user(user)['role_code']}] {q}  ({sec:.0f}초, {r['status']})", passed,
           r["answer"][:200].replace("\n", " "))
        log.append({"user": user, "question": q, "seconds": round(sec), **r})
    path = Path(__file__).with_name("시험결과_실제질문.json")
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"답 전체: {path}")


if __name__ == "__main__":
    offline()
    guide_offline()
    if "--live" in sys.argv:
        비서.DB_FILE = Path(__file__).with_name("채팅기록_시험.sqlite3")
        live()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} 통과")
    sys.exit(1 if failed else 0)
