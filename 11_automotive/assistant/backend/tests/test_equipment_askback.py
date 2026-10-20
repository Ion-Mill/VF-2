"""설비 이름만 든 글 · 되묻기 답 이어받기 · 못 읽은 조각 안내 · 기간 안내 (2026-10-20, 기획 설비이름_되묻기_안내).

문제 4가지 (2026-10-01 실제 질문 7개로 확인):
 1. 설비 이름만 있는 글("VF2-01)")을 안전 질문으로 봤다 — `is_safety`가 설비 이름(EQUIPMENT_RE)만으로 참이라 안전 안내가 나오고, "VF2-01 정비 상태는?"에는 안전 문구가 붙었다.
 2. "설비를 알려 주세요"에 설비 이름으로 답해도 앞 질문과 잇지 못했다.
 3. 규칙이 못 읽은 조각(센서·정비현황·브리핑)을 말없이 버렸다.
 4. 날짜를 안 말한 지표는 9월 한 달 값인데, 하루 값과 MTTR·MTBF(30일 고정)가 한 줄에 섞여도 말이 없었다.

질문 은행 62개(이 파일 CASES)는 개인 측정 도구(질문은행.json)와 **같은 질문·같은 기대**다. 질문을 빼거나 기대를 느슨하게 바꾸지 않는다.
방법은 측정 도구와 같다: 조회는 가짜 백엔드, Claude는 부르지 않는다. 길 판정은 외부 Claude를 고른 요청과 같은 설정으로 `pure_scope_v19`로만 보고,
규칙 길이면 LLM을 끈 설정으로 `answer()`를 돌려 `status`·`conclusion`을 본다 (직전 턴의 `_followup`을 prev로 넘긴다).
"""
from __future__ import annotations

import pytest

from backend.config import settings
from backend.llm import external as EXT
from backend.services import answer as A
from backend.services import pure_external as PURE
from backend.tests.test_doc_recall import APP_FLAGS

SAFETY_MARK = "설비 이름뿐인 안전 질문"
ALL_TOOLS = ["equipment_status", "alarms", "kpi", "production", "lot", "work_orders", "work_records", "pm_due", "tool_life", "inventory",
             "reliability", "stop_reasons", "sensor_trend", "equipment_spec"]
OPR_TOOLS = [t for t in ALL_TOOLS if t not in ("reliability", "sensor_trend", "equipment_spec")]


@pytest.fixture(autouse=True)
def app_flags(monkeypatch):
    """실제 실행과 같은 설정: 파서 보강·이어 묻기·순수 길(신호는 기존 길)·안전망·규칙/고장 질문 라우팅."""
    for k, v in APP_FLAGS.items():
        monkeypatch.setenv(k, v)
    for k, v in {"PURE_KEEP_SIGNALS": "1", "PURE_EXPAND": "1", "PURE_SAFETY": "1", "PURE_PERIOD": "1", "PURE_RULE": "1", "PURE_FAULT": "1",
                 "PURE_FAULTDOC": "1", "PURE_RULE_WIDE": "1"}.items():
        monkeypatch.setenv(k, v)


def route_label(question: str, prev: dict | None, monkeypatch) -> tuple[str, str]:
    """실제 흐름(answer._answer)의 앞부분을 따라 길 이름을 정한다 (측정 도구 route_label과 같다)."""
    monkeypatch.setenv("LLM_ENABLED", "1")
    with EXT.external_request("claude"):
        s = settings()
        p = A.parse(question)
        p["raw"] = question
        if A.human_only(question, general=not s.followup):
            return "거절", "human_only"
        if A.DEFECT_CAUSE.search(question):
            return "거절", "불량 원인"
        if s.followup:
            prev_text = " ".join([prev["question"], prev["conclusion"]] + list(prev.get("doc_lines") or [])) if prev else ""
            kind = (A.followup_kind_v9 if A.v9_on(s) else A.followup_kind_v8 if A.v8_on(s) else A.followup_kind)(question, prev_text)
            if kind:
                return "이어묻기", str(kind)
        why = A.pure_scope_v19(p, s, question)
    if not why:
        return "규칙길", ""
    return ("안전길" if SAFETY_MARK in why else "순수길"), why[:60]


def run_turns(turns: list[str], role: str, monkeypatch) -> dict:
    prev, last = None, {}
    for q in turns:
        label, why = route_label(q, prev, monkeypatch)
        last = {"route": label, "why": why, "conclusion": "", "status": None}
        if label == "규칙길":
            monkeypatch.setenv("LLM_ENABLED", "0")
            a = A.answer(q, role, {}, prev=prev)
            last.update(status=a.get("status"), conclusion=a.get("conclusion") or "", blocks=a.get("blocks"))
            prev = a.get("_followup") or prev
        else:
            prev = None   # 순수 길·안전 길 뒤의 이어 묻기 기록은 이 시험이 만들지 않는다 (Claude를 부르지 않는다)
    return last


def judge(last: dict, chk: dict) -> list[str]:
    bad, text = [], last["conclusion"]
    if chk.get("route_in") and last["route"] not in chk["route_in"]:
        bad.append(f"길이 {chk['route_in']} 중 하나여야 하는데 {last['route']}")
    if any(k in chk for k in ("contains", "not_contains", "also_contains_any")) and last["route"] != "규칙길":
        return bad + [f"답 글을 검사할 수 없는 길({last['route']})"]   # 답을 만들지 않는 길에서는 글자 검사를 통과로 세지 않는다 (빈 글이라 '없어야 함'이 거저 통과하는 것을 막는다)
    if chk.get("route_not_safety") and last["route"] == "안전길":
        bad.append("안전 길로 감")
    if chk.get("route_safety") and last["route"] != "안전길":
        bad.append(f"안전 길이어야 하는데 {last['route']}")
    bad += [f"없음: {w}" for w in chk.get("contains", []) if w not in text]
    bad += [f"있으면 안 됨: {w}" for w in chk.get("not_contains", []) if w in text]
    anys = chk.get("also_contains_any")
    if anys and not any(w in text for w in anys):
        bad.append(f"다음 중 하나가 있어야 함: {anys}")
    return bad


# 질문 은행 62개: G1 설비 이름만(16) · S 안전 질문은 안전 길 그대로(10) · M 되묻기 답 합치기(9) · N 합치면 안 되는 것(8) · U 못 읽은 조각 안내(7) · P 기간 안내(8) · R 회귀 대조(4)
# turns의 여러 질문은 앞 턴에 이어 보내는 질문이다. role 기본은 MNT(MTTR·MTBF가 보이는 역할), OPR는 안 보이는 역할.
CASES = [
    {'id': 'G1-01', 'turns': ['VF2-01)'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['안전', 'DOC-05']}},
    {'id': 'G1-02', 'turns': ['VF2-01'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['안전', 'DOC-05']}},
    {'id': 'G1-03', 'turns': ['VF2-02'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['안전', 'DOC-05']}},
    {'id': 'G1-04', 'turns': ['SAW-01'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['안전', 'DOC-05']}},
    {'id': 'G1-05', 'turns': ['vf2-01'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['안전', 'DOC-05']}},
    {'id': 'G1-06', 'turns': ['VF2-01 정비 상태는?'], 'check': {'route_in': ['순수길']}},
    {'id': 'G1-07', 'turns': ['VF2-01 정비 현황 알려줘'], 'check': {'route_in': ['순수길']}},
    {'id': 'G1-08', 'turns': ['2호기 정비 상태는?'], 'check': {'route_in': ['순수길']}},
    {'id': 'G1-09', 'turns': ['MIL-01 정비현황'], 'check': {'route_in': ['순수길']}},
    {'id': 'G1-10', 'turns': ['VF2-01 상태 알려줘'], 'check': {'route_in': ['순수길']}},
    {'id': 'G1-11', 'turns': ['VF2-01 센서 주세요'], 'check': {'route_in': ['순수길']}},
    {'id': 'G1-12', 'turns': ['VF2-01 지금 상태 어때?'], 'check': {'route_not_safety': True, 'contains': ['VF2-01']}},
    {'id': 'G1-13', 'turns': ['VF2-01 정비 기한 넘긴 거 있어?'], 'check': {'route_not_safety': True}},
    {'id': 'G1-14', 'turns': ['1호기'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['순간 정지', 'DOC-05']}},
    {'id': 'G1-15', 'turns': ['2호기요'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['순간 정지', 'DOC-05']}},
    {'id': 'G1-16', 'turns': ['VF2-01 이요'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['안전', 'DOC-05']}},
    {'id': 'S-01', 'turns': ['VF2-01 정비 전에 어디를 차단해?'], 'check': {'route_safety': True}},
    {'id': 'S-02', 'turns': ['SAW-01 정비 전에 어디를 차단해?'], 'check': {'route_safety': True}},
    {'id': 'S-03', 'turns': ['VF2-01 차단 지점'], 'check': {'route_safety': True}},
    {'id': 'S-04', 'turns': ['VF2-01 잠금 표지 순서'], 'check': {'route_safety': True}},
    {'id': 'S-05', 'turns': ['VF2-02 고전압 대기 몇 분이야?'], 'check': {'route_safety': True}},
    {'id': 'S-06', 'turns': ['VF2-01 정비할 때 보호구는?'], 'check': {'route_safety': True}},
    {'id': 'S-07', 'turns': ['VF2-01 전원 끄고 케이블 만져도 돼?'], 'check': {'route_safety': True}},
    {'id': 'S-08', 'turns': ['VF2-01 감전 위험 있어?'], 'check': {'route_safety': True}},
    {'id': 'S-09', 'turns': ['CMM-01 정비 시작 전에 뭐 해야 돼?'], 'check': {'route_safety': True}},
    {'id': 'S-10', 'turns': ['VF2-01 주축 점검할 때 주의할 점'], 'check': {'route_safety': True}},
    {'id': 'M-01', 'turns': ['OEE 오늘값', 'VF2-01'], 'check': {'contains': ['VF2-01', 'OEE'], 'not_contains': ['확인 필요', '안전']}},
    {'id': 'M-02', 'turns': ['OEE 현재값', 'VF2-02'], 'check': {'contains': ['VF2-02', 'OEE'], 'not_contains': ['확인 필요', '안전']}},
    {'id': 'M-03', 'turns': ['OEE라인 어제상태는?', 'VF2-01)'], 'check': {'contains': ['VF2-01', 'OEE'], 'not_contains': ['확인 필요', '안전']}},
    {'id': 'M-04', 'turns': ['OEE 어제값', '1호기'], 'check': {'contains': ['VF2-01'], 'not_contains': ['확인 필요']}},
    {'id': 'M-05', 'turns': ['OEE 어제값', '2호기요'], 'check': {'contains': ['VF2-02'], 'not_contains': ['확인 필요']}},
    {'id': 'M-06', 'turns': ['MTTR 알려줘', 'vf2-01'], 'check': {'contains': ['VF2-01', 'MTTR'], 'not_contains': ['확인 필요']}},
    {'id': 'M-07', 'turns': ['가동률 어제', 'VF2-01 이요'], 'check': {'contains': ['VF2-01'], 'not_contains': ['확인 필요']}},
    {'id': 'M-08', 'turns': ['OEE 오늘값', 'VF2-01'], 'check': {'contains': ['VF2-01', 'OEE'], 'not_contains': ['확인 필요', 'MTTR']}, 'role': 'OPR'},
    {'id': 'M-09', 'turns': ['양품률 오늘', 'VF2-02'], 'check': {'contains': ['VF2-02'], 'not_contains': ['확인 필요']}},
    {'id': 'N-01', 'turns': ['OEE 오늘값', 'VF2-01 센서 추세'], 'check': {'route_in': ['순수길']}},
    {'id': 'N-02', 'turns': ['VF2-01 OEE 어제값은', 'VF2-02'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['OEE 6', 'OEE 5', 'OEE 7', '가동률 ', 'MTTR ']}},
    {'id': 'N-03', 'turns': ['OEE 오늘값', 'VF2-01 정비 전에 어디를 차단해?'], 'check': {'route_safety': True}},
    {'id': 'N-04', 'turns': ['OEE 오늘값', 'VF2-99'], 'check': {'route_in': ['순수길']}},
    {'id': 'N-05', 'turns': ['OEE 오늘값', '고마워'], 'check': {'route_in': ['순수길']}},
    {'id': 'N-06', 'turns': ['OEE 오늘값', 'VF2-01', 'VF2-02'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['OEE 6', 'OEE 5', 'OEE 7', '가동률 ', 'MTTR ']}},
    {'id': 'N-07', 'turns': ['알람 몇 번 났어?', 'VF2-01'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['OEE 6', 'OEE 5', 'OEE 7', '가동률 ', 'MTTR ']}},
    {'id': 'N-08', 'turns': ['로트 판정 났어?', 'VF2-01'], 'check': {'route_in': ['규칙길'], 'contains': ['예:'], 'not_contains': ['OEE 6', 'OEE 5', 'OEE 7', '가동률 ', 'MTTR ']}},
    {'id': 'U-01', 'turns': ['F2-01-MTTR 알려줘 VF2-01 센서 주세요 2075 알람 뭐요?  OEE라인 현재값 뭐요? 정비현황 브리핑 현재값은'], 'check': {'contains': ['센서', '정비현황', '브리핑'], 'also_contains_any': ['2075', 'OEE']}},
    {'id': 'U-02', 'turns': ['2075 알람 뭐요? 센서도 보여줘'], 'check': {'contains': ['센서', '2075']}},
    {'id': 'U-03', 'turns': ['VF2-01 OEE 어제값 알려주고 브리핑도 보여줘'], 'check': {'contains': ['OEE', '브리핑']}},
    {'id': 'U-04', 'turns': ['정비현황 브리핑 현재값은'], 'check': {'route_not_safety': True}},
    {'id': 'U-05', 'turns': ['2075 알람 뭐요?'], 'check': {'not_contains': ['아직 답하지 못', '답하지 못했']}},
    {'id': 'U-06', 'turns': ['VF2-01 OEE 어제값은'], 'check': {'not_contains': ['아직 답하지 못', '답하지 못했']}},
    {'id': 'U-07', 'turns': ['VF2-01 MTTR 알려줘 2075 알람 뭐요?'], 'check': {'not_contains': ['아직 답하지 못', '답하지 못했']}},
    {'id': 'P-01', 'turns': ['VF2-01 OEE 현재값'], 'check': {'contains': ['9월'], 'also_contains_any': ['기간을 정하지', '날짜를 말씀']}},
    {'id': 'P-02', 'turns': ['VF2-01 OEE'], 'check': {'contains': ['9월'], 'also_contains_any': ['기간을 정하지', '날짜를 말씀']}},
    {'id': 'P-03', 'turns': ['VF2-01 OEE라인 어제값은'], 'check': {'contains': ['9-30', 'OEE'], 'also_contains_any': ['최근 30일', '30일 값']}},
    {'id': 'P-04', 'turns': ['VF2-01 MTTR 알려줘'], 'check': {'contains': ['MTTR'], 'not_contains': ['기간을 정하지']}},
    {'id': 'P-05', 'turns': ['VF2-01 OEE 9월'], 'check': {'not_contains': ['기간을 정하지']}},
    {'id': 'P-06', 'turns': ['VF2-01 OEE 어제값은'], 'check': {'not_contains': ['MTTR', '최근 30일']}, 'role': 'OPR'},
    {'id': 'P-07', 'turns': ['VF2-01 가동률 지난주'], 'check': {'not_contains': ['기간을 정하지']}},
    {'id': 'P-08', 'turns': ['오늘 VF2-01 OEE'], 'check': {'not_contains': ['기간을 정하지']}},
    {'id': 'R-01', 'turns': ['OEE 현재값'], 'check': {'contains': ['확인 필요', '설비']}},
    {'id': 'R-02', 'turns': ['OEE 오늘값'], 'check': {'contains': ['확인 필요', '설비']}},
    {'id': 'R-03', 'turns': ['OEE라인 어제상태는?'], 'check': {'contains': ['확인 필요', '설비']}},
    {'id': 'R-04', 'turns': ['2075 알람 뭐요?'], 'check': {'contains': ['2075']}},
]


# M-06은 기획의 기대("MTTR 알려줘" 뒤 "vf2-01"이 앞 질문과 이어진다)와 앞 턴의 실제 동작이 다르다: "MTTR 알려줘"는 설비를 되묻지 않고 용어 설명(상태 '답변')으로 답한다.
# 기획 4장 변경 B의 조건은 "바로 앞 답이 '확인 필요 — 설비'"일 때뿐이라 이어받지 않는다. 기대를 고치지 않고 사용자 결정(성과 문서)을 기다린다.
M06_PENDING = pytest.mark.xfail(strict=True, reason="앞 턴이 설비를 되묻지 않는 용어 답이라 변경 B의 이어받기 조건(앞 답 = 확인 필요 — 설비)에 안 걸린다 — 사용자 결정 대기")


@pytest.mark.parametrize("case", [pytest.param(c, marks=M06_PENDING) if c["id"] == "M-06" else c for c in CASES], ids=[c["id"] for c in CASES])
def test_question_bank(case, monkeypatch):
    from backend.repositories import backend_tools as BT
    tools = OPR_TOOLS if case.get("role") == "OPR" else ALL_TOOLS
    with BT.acting_as("U07", tools):
        last = run_turns(case["turns"], case.get("role", "MNT"), monkeypatch)
    assert not judge(last, case["check"]), (case["id"], judge(last, case["check"]), last["route"], last["conclusion"][:200])


def test_bank_is_complete():
    """62개가 그대로 있다 — 질문을 빼서 통과 수를 맞추지 못하게 한다."""
    assert len(CASES) == 62
    groups = {}
    for c in CASES:
        groups.setdefault(c["id"].split("-")[0], []).append(c)
    assert {g: len(v) for g, v in groups.items()} == {"G1": 16, "S": 10, "M": 9, "N": 8, "U": 7, "P": 8, "R": 4}


# ---------------------------------------------------------------- 낱낱 확인


@pytest.mark.parametrize("q", ["VF2-01", "VF2-01)", "SAW-01", "VF2-01 정비 상태는?", "2호기 정비 상태는?", "CMM", "VF-2"])
def test_is_safety_ignores_equipment_names(q):
    """설비 이름만으로는 안전 질문이 아니다 (예전: EQUIPMENT_RE만으로 참 — 안전 안내·안전 문구·DOC-05 통째 붙이기가 한꺼번에 걸렸다)."""
    assert not PURE.is_safety(q)


@pytest.mark.parametrize("q", ["VF2-01 정비 전에 어디를 차단해?", "VF2-01 감전 위험 있어?", "SAW-01 정비 전에 어디를 차단해?", "VF2-01 주축 점검할 때 주의할 점", "CMM-01 정비 시작 전에 뭐 해야 돼?"])
def test_safety_words_still_trigger(q):
    assert PURE.is_safety(q)


@pytest.mark.parametrize("q, expected", [
    ("VF2-01", True), ("VF2-01)", True), ("vf2-01", True), ("SAW-01", True), ("1호기", True), ("2호기요", True), ("VF2-01 이요", True), ("일호기", True),
    ("VF2-01 정비 상태는?", False), ("2호기 정비 상태는?", False), ("VF2-01 OEE", False), ("VF2-01 지금 상태 어때?", False),
    ("VF2-01 정비 전에 어디를 차단해?", False), ("VF2-99", False), ("OEE 오늘값", False), ("2075 VF2-01", False), ("VF2-01 어제", False),
])
def test_equipment_only_truth_table(q, expected):
    assert A.equipment_only_v21(q, A.parse(q)) is expected


def test_name_plus_other_words_gets_no_safety_net(monkeypatch):
    """"VF2-01 정비 상태는?"은 안전망 없는 순수 길 — DOC-05를 통째로 더하지 않는다. 안전 낱말이 붙으면 그대로 더한다."""
    s = settings()
    plain = PURE.context("VF2-01 정비 상태는?", s.pure_topk, s)
    safe = PURE.context("VF2-01 정비 전에 어디를 차단해?", s.pure_topk, s)
    assert not [1 for sc, _ in plain if sc == PURE.SAFETY_SCORE]
    assert [1 for sc, _ in safe if sc == PURE.SAFETY_SCORE]


def test_askback_merge_adds_a_visible_note_and_only_once(monkeypatch):
    from backend.repositories import backend_tools as BT
    monkeypatch.setenv("LLM_ENABLED", "0")
    with BT.acting_as("U07", ALL_TOOLS):
        a1 = A.answer("OEE 어제값", "MNT", {})
        assert a1["status"] == "확인 필요"
        a2 = A.answer("1호기", "MNT", {}, prev=a1["_followup"])
        assert a2["status"] == "답변" and "VF2-01" in a2["conclusion"] and a2["question"] == "1호기"
        assert a2["conclusion"].endswith("앞서 물으신 'OEE 어제값'을 VF2-01 기준으로 답했어요.")
        assert a2["blocks"][-1] == {"kind": "text", "text": "앞서 물으신 'OEE 어제값'을 VF2-01 기준으로 답했어요."}
        a3 = A.answer("2호기", "MNT", {}, prev=a2["_followup"])   # 설비를 계속 가져가지 않는다 — 다시 안내
        assert a3["status"] == "안내" and "앞서 물으신" not in a3["conclusion"]


def test_askback_not_merged_when_previous_was_not_an_equipment_askback(monkeypatch):
    from backend.repositories import backend_tools as BT
    monkeypatch.setenv("LLM_ENABLED", "0")
    with BT.acting_as("U07", ALL_TOOLS):
        for first in ["VF2-01 OEE 어제값은", "알람 몇 번 났어?", "로트 판정 났어?"]:
            a1 = A.answer(first, "MNT", {})
            a2 = A.answer("VF2-01", "MNT", {}, prev=a1["_followup"])
            assert a2["status"] == "안내" and "앞서 물으신" not in a2["conclusion"], first


def test_period_notes_follow_the_answer_role(monkeypatch):
    from backend.repositories import backend_tools as BT
    monkeypatch.setenv("LLM_ENABLED", "0")
    with BT.acting_as("U07", ALL_TOOLS):
        mnt = A.answer("VF2-01 OEE 어제값은", "MNT", {})["conclusion"]
        mnt_nodate = A.answer("VF2-01 OEE", "MNT", {})["conclusion"]
        mttr_only = A.answer("VF2-01 MTTR 알려줘", "MNT", {})["conclusion"]
    with BT.acting_as("U07", OPR_TOOLS):
        opr = A.answer("VF2-01 OEE 어제값은", "OPR", {})["conclusion"]
    assert "MTTR·MTBF는 최근 30일 값이에요" in mnt and "MTTR" not in opr
    assert "기간을 정하지 않아 9월 한 달(9/1~9/30) 값이에요" in mnt_nodate
    assert "기간을 정하지 않아" not in mttr_only


def test_unread_note_names_only_listed_items():
    assert A.unread_note_v21("센서 주세요") == "이 채팅에서는 아직 센서 값을 답하지 못했어요. 해당 화면에서 확인해 주세요."
    assert A.unread_note_v21("정비 현황 브리핑 센서") == "이 채팅에서는 아직 센서 값·정비현황·브리핑을 답하지 못했어요. 해당 화면에서 확인해 주세요."
    assert A.unread_note_v21("VF2-01 OEE 어제값은") is None    # 목록 밖의 말은 추측하지 않는다
