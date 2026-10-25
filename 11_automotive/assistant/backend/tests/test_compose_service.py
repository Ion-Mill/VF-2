"""문장 입구(`POST /compose/{kind}`) 시험 — 기본 문장 줄을 외부 Claude로 다듬는다 (2026-10-17, NFR-SEC-08·NFR-AIQ-04·FR-AST-02-14).
진짜 `claude`는 부르지 않는다. 가짜 실행기가 부른 횟수와 받은 글을 기록해서 "스위치를 끄면 외부 연결 0", "사람·계정 글은 안 나감"을 확인한다."""
import json
import subprocess
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import chat_service as CS
from backend import config as C
from backend.llm import claude_client as CC
from backend.llm import client as LC
from backend.llm import external as EXT
from backend.privacy import outbound_guard as OG

pytestmark = pytest.mark.own_backend
KEY = "test-service-key"
H = {"X-Service-Key": KEY}
SONNET = "claude-haiku-5-5"          # 외부 앱 다듬기(compose)가 요청하는 모델. 가짜 응답의 모델 이름이 이와 같아야 글 검사까지 간다
client = TestClient(CS.app)

SHIFT = [{"id": "s1", "text": "실적 87개 / 총 목표 90개 (-3개)."},
         {"id": "s2", "text": "필수 정지 1건, 합계 12분 — 가장 긴 것 VF2-01 윤활 12분 (고장 손실 약 1.7개, 추정)."},
         {"id": "s3", "text": "병목은 기준 병목(OP-30) 그대로."}]


class Runner:
    """가짜 `claude` 실행기: 부른 횟수·받은 글을 기록하고, 정해 둔 답(dict) 또는 예외를 차례로 돌려준다."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, cmd, stdin_text, timeout):
        self.calls.append({"cmd": cmd, "stdin": stdin_text})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        d = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 10, "duration_api_ms": 5, "num_turns": 1,
             "total_cost_usd": 0.001, "structured_output": r,
             "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
             "modelUsage": {SONNET: {"inputTokens": 10}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(d, ensure_ascii=False), stderr="")


def out(*texts, ids=("s1", "s2", "s3")):
    return {"lines": [{"id": i, "text": t} for i, t in zip(ids, texts)]}


GOOD = out("실적은 87개로 총 목표 90개보다 적습니다 (-3개).",
           "필수 정지는 1건, 합계 12분이었고 가장 긴 것은 VF2-01 윤활 12분입니다 (고장 손실 약 1.7개, 추정).",
           "병목은 기준 병목(OP-30) 그대로입니다.")


LOCAL_CALLS: list[str] = []


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    LOCAL_CALLS.clear()

    def local_handler(req):            # 로컬 LLM 서버는 이 프로젝트에서 쓰지 않는다 — 불리면 기록하고 연결 실패로 돌려준다
        LOCAL_CALLS.append(str(req.url))
        raise httpx.ConnectError("시험: 로컬 서버 없음")
    LC.use_transport(httpx.MockTransport(local_handler))
    monkeypatch.setattr(C, "_dotenv", lambda: {})
    monkeypatch.setenv("MOM_ASSISTANT_KEY", KEY)
    monkeypatch.setenv("ASSISTANT_PROVIDER", "claude")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "1")
    monkeypatch.setenv("LLM_ENABLED", "1")
    OG.reset_cache()
    yield
    CC.use_runner(None)
    LC.use_transport(None)


def use(*replies) -> Runner:
    r = Runner(*replies)
    CC.use_runner(r)
    return r


def post(kind="shift_report", lines=SHIFT, **kw):
    return client.post(f"/compose/{kind}", json={"lines": lines}, headers=H, **kw)


def assert_503(r):
    assert r.status_code == 503 and r.json()["code"] == "ASSISTANT_UNAVAILABLE" and r.json()["detail"] == {"retryable": True}
    assert "sonnet" not in r.text.lower() and "claude" not in r.text.lower()       # 안쪽 사정은 응답에 없다


# ------------------------------------------------------------------ 열쇠·입력 모양
def test_service_key_is_required():
    r = use()
    assert client.post("/compose/shift_report", json={"lines": SHIFT}).status_code == 401
    assert client.post("/compose/shift_report", json={"lines": SHIFT}, headers={"X-Service-Key": "nope"}).status_code == 401
    assert r.calls == []


@pytest.mark.parametrize("bad", [
    {"lines": SHIFT, "user_id": "U07"},                                   # 정해진 칸 밖은 받지 않는다
    {"lines": [{"id": "s1", "text": "x", "by": "U07"}]},
    {"lines": []},
    {"lines": [{"id": "한글 id", "text": "x"}]},
    {"lines": [{"id": "s1", "text": ""}]},
    {},
])
def test_bad_request_shapes_are_422_and_nothing_is_sent(bad):
    r = use()
    assert client.post("/compose/shift_report", json=bad, headers=H).status_code == 422
    assert r.calls == []


def test_unknown_kind_is_422():
    assert client.post("/compose/chat", json={"lines": SHIFT}, headers=H).status_code == 422


# ------------------------------------------------------------------ 다듬기 성공
def test_polishes_each_line_and_keeps_ids_order_and_numbers():
    r = use(GOOD)
    res = post()
    assert res.status_code == 200
    j = res.json()
    assert j["kind"] == "shift_report" and j["tries"] == 1
    assert [l["id"] for l in j["lines"]] == ["s1", "s2", "s3"]
    assert "87개" in j["lines"][0]["text"] and "(고장 손실 약 1.7개, 추정)" in j["lines"][1]["text"]
    assert len(r.calls) == 1
    assert "s1: 실적 87개 / 총 목표 90개 (-3개)." in r.calls[0]["stdin"]
    assert EXT.override() is None                                         # 요청이 끝나면 외부 상태가 새지 않는다


# ------------------------------------------------------------------ 외부로 한 글자도 안 나가는 경우 (T-NFR-SEC-08-2)
def test_server_switch_off_sends_nothing_and_is_503(monkeypatch):
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")
    r = use(GOOD)
    assert_503(post())
    assert r.calls == [] and LOCAL_CALLS == []         # 외부 연결 0, 로컬 LLM 서버로도 새지 않는다


def test_provider_not_claude_sends_nothing_and_is_503(monkeypatch):
    monkeypatch.setenv("ASSISTANT_PROVIDER", "local")
    r = use(GOOD)
    assert_503(post())
    assert r.calls == [] and LOCAL_CALLS == []         # 외부 연결 0, 로컬 LLM 서버로도 새지 않는다


def test_llm_disabled_sends_nothing_and_is_503(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "0")
    r = use(GOOD)
    assert_503(post())
    assert r.calls == [] and LOCAL_CALLS == []         # 외부 연결 0, 로컬 LLM 서버로도 새지 않는다


# ------------------------------------------------------------------ 사람·계정 글은 나가지 않는다 (T-NFR-SEC-08-1)
@pytest.mark.parametrize("leak", ["담당 U07 점검", "보전 담당 1 점검", "사번: E12345 점검", "비밀번호: hunter22 점검", "Bearer abcdef1234567890 점검"])
def test_material_with_people_or_account_info_is_not_sent(leak):
    r = use(GOOD)
    assert_503(post(lines=[{"id": "s1", "text": f"실적 87개. {leak}."}]))
    assert r.calls == []


# ------------------------------------------------------------------ 검사에 걸리면 거부하고 한 번 다시 요청한다
def test_changed_number_is_rejected_then_retry_with_reason_succeeds():
    bad = out("실적은 88개, 총 목표 90개라서 2개 모자랍니다.", GOOD["lines"][1]["text"], GOOD["lines"][2]["text"])
    r = use(bad, GOOD)
    res = post()
    assert res.status_code == 200 and res.json()["tries"] == 2
    assert "거부" in r.calls[1]["stdin"] and "s1" in r.calls[1]["stdin"]       # 다시 요청에 사유가 붙는다


def test_two_rejections_end_in_503_and_never_loop_further():
    bad = out("실적은 88개, 총 목표 90개입니다.", GOOD["lines"][1]["text"], GOOD["lines"][2]["text"])
    r = use(bad, bad)
    assert_503(post())
    assert len(r.calls) == 2


@pytest.mark.parametrize("name,mutate", [
    ("꼬리표 '추정' 삭제", lambda g: out(g["lines"][0]["text"], "필수 정지는 1건, 합계 12분이었고 가장 긴 것은 VF2-01 윤활 12분입니다 (고장 손실 약 1.7개).", g["lines"][2]["text"])),
    ("설비 번호 바꿈", lambda g: out(g["lines"][0]["text"], g["lines"][1]["text"].replace("VF2-01", "VF2-02"), g["lines"][2]["text"])),
    ("줄 순서 바꿈", lambda g: {"lines": [g["lines"][1], g["lines"][0], g["lines"][2]]}),
    ("줄 빠짐", lambda g: {"lines": g["lines"][:2]}),
    ("문장 수 늘림", lambda g: out("실적은 87개입니다. 총 목표는 90개입니다.", g["lines"][1]["text"], g["lines"][2]["text"])),
    ("줄바꿈", lambda g: out("실적은 87개로\n총 목표 90개보다 적습니다 (-3개).", g["lines"][1]["text"], g["lines"][2]["text"])),
    ("마크다운", lambda g: out("**" + g["lines"][0]["text"] + "**", g["lines"][1]["text"], g["lines"][2]["text"])),
    ("허락 문구", lambda g: out(g["lines"][0]["text"], g["lines"][1]["text"], "병목은 기준 병목(OP-30) 그대로라 문제 없습니다.")),
])
def test_unsafe_rewrites_are_rejected(name, mutate):
    r = use(mutate(GOOD), mutate(GOOD))
    assert_503(post())
    assert len(r.calls) == 2, name


def test_daily_report_items_must_not_contain_the_separators_the_screen_splits_on():
    items = [{"id": "i1", "text": "VF2-01 윤활 정지 12분"}, {"id": "i2", "text": "병목 OP-30 유지"}]
    ok = {"lines": [{"id": "i1", "text": "VF2-01은 윤활 때문에 12분 멈췄습니다"}, {"id": "i2", "text": "병목은 OP-30 그대로입니다"}]}
    bad = {"lines": [{"id": "i1", "text": "정지: VF2-01 윤활 12분"}, {"id": "i2", "text": "병목 OP-30 유지"}]}
    r = use(bad, ok)
    res = post("daily_report", items)
    assert res.status_code == 200 and res.json()["tries"] == 2
    assert all(":" not in l["text"] and " / " not in l["text"] for l in res.json()["lines"])
    assert "금지 글자" in r.calls[1]["stdin"]


# ------------------------------------------------------------------ 외부 실패는 몰래 다른 길로 가지 않는다
def test_claude_process_timeout_is_503():
    r = use(subprocess.TimeoutExpired(["claude"], 60))
    assert_503(post())
    assert len(r.calls) == 1


def test_unreadable_claude_output_is_503():
    r = use({"unexpected": "shape"}, {"unexpected": "shape"})
    assert_503(post())


# ------------------------------------------------------------------ 화면이 기대는 모양 (마침표로 문장 쪼개기, 앞머리 꼬리표)
def test_sentence_end_mark_must_be_kept_because_the_screen_splits_on_it():
    no_dot = out("실적은 87개로 총 목표 90개보다 적습니다 (-3개)", GOOD["lines"][1]["text"], GOOD["lines"][2]["text"])
    r = use(no_dot, no_dot)
    assert_503(post())
    assert len(r.calls) == 2 and "끝 부호" in r.calls[1]["stdin"]


def test_leading_category_tag_of_a_daily_item_must_be_kept():
    items = [{"id": "i1", "text": "[긴급] VF2-01 고장 85분"}, {"id": "i2", "text": "[주의] 보류 로트 LOT-2609-041-1"}]
    dropped = {"lines": [{"id": "i1", "text": "VF2-01이 85분 고장이었습니다"}, {"id": "i2", "text": "[주의] 로트 LOT-2609-041-1이 보류 중입니다"}]}
    kept = {"lines": [{"id": "i1", "text": "[긴급] VF2-01이 85분 동안 고장이었습니다"}, {"id": "i2", "text": "[주의] 로트 LOT-2609-041-1이 보류 중입니다"}]}
    r = use(dropped, kept)
    res = post("daily_report", items)
    assert res.status_code == 200 and res.json()["tries"] == 2 and "꼬리표" in r.calls[1]["stdin"]
    assert [l["text"][:4] for l in res.json()["lines"]] == ["[긴급]", "[주의]"]


def test_format_error_from_the_model_is_retried_once_not_given_up():
    short = out(GOOD["lines"][0]["text"], GOOD["lines"][1]["text"], ids=("s1", "s2"))        # 줄이 모자란 응답(스키마 위반)
    r = use(short, GOOD)
    res = post()
    assert res.status_code == 200 and res.json()["tries"] == 2 and len(r.calls) == 2


# ------------------------------------------------------------------ 작업지시서 제목·증상
WO = [{"id": "title", "text": "VF2-01 알람 2075 (공기압 낮음) 점검"}, {"id": "symptom", "text": "공기압이 낮다는 알람 2075가 떴다."}]


def test_work_order_title_and_symptom_are_polished_and_the_title_stays_short():
    good = {"lines": [{"id": "title", "text": "VF2-01 알람 2075 공기압 낮음 점검"}, {"id": "symptom", "text": "공기압이 낮다는 알람 2075가 발생했다."}]}
    use(good)
    res = post("work_order", WO)
    assert res.status_code == 200 and [l["id"] for l in res.json()["lines"]] == ["title", "symptom"]
    long_title = {"lines": [{"id": "title", "text": "VF2-01 알람 2075 공기압 낮음 점검 " + "아주 " * 20 + "급함"}, good["lines"][1]]}
    r = use(long_title, long_title)
    assert_503(post("work_order", WO))
    assert len(r.calls) == 2 and "제목이" in r.calls[1]["stdin"]


# ------------------------------------------------------------------ 알람 지침카드 '먼저 할 일' (알람 992 — DOC-03 ★ 줄)
CARD = [{"id": "g1", "text": "축을 움직이지 말고 알람 이력을 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호"},
        {"id": "g2", "text": "도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다"},
        {"id": "g3", "text": "외함·주축·공구·고정구에 손상이 있는지 본다 (손상 = 충돌 징후)"},
        {"id": "g4", "text": "공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 부른다"}]
CARD_GOOD = ["축을 움직이지 말고 알람 이력부터 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호다",
             "도어 밖에서 공구, 고정구, 공작물이 외함과 부딪혔는지 확인한다",
             "외함, 주축, 공구, 고정구에 손상이 있는지 확인한다 (손상 = 충돌 징후)",
             "공구가 무뎌졌거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 부른다"]


def card_out(*texts):
    return {"lines": [{"id": f"g{i + 1}", "text": t} for i, t in enumerate(texts)]}


def test_guide_card_lines_are_polished_when_the_meaning_is_unchanged():
    use(card_out(*CARD_GOOD))
    res = post("guide_card", CARD)
    assert res.status_code == 200 and res.json()["tries"] == 1 and len(res.json()["lines"]) == 4
    assert "말고" in res.json()["lines"][0]["text"] and "보전 담당자" in res.json()["lines"][3]["text"]


@pytest.mark.parametrize("why,mut", [
    ("'말고'(하지 말라)를 빼고 바꿔 씀", lambda g: [g[0].replace("움직이지 말고", "움직이지 마세요"), *g[1:]]),
    ("원문에 없는 안전 용어(전원)를 더함", lambda g: [g[0], g[1] + ", 전원 상태도 본다", *g[2:]]),
    ("108을 바꿈", lambda g: [g[0].replace("108", "180"), *g[1:]]),
    ("원문과 너무 다르게 바꿔 씀", lambda g: [g[0], "외함이 충돌했는지 먼저 확인합니다", *g[2:]]),
    ("줄 합침", lambda g: [g[0] + " " + g[1], *g[2:]]),
])
def test_guide_card_rewrites_that_change_the_meaning_are_rejected(why, mut):
    bad = card_out(*mut(CARD_GOOD)) if "줄 합침" not in why else {"lines": [{"id": "g1", "text": mut(CARD_GOOD)[0]}]}
    r = use(bad, bad)
    assert_503(post("guide_card", CARD))
    assert len(r.calls) == 2, why


MAINT = [{"id": "g1", "text": "잠금·표지 후, 충돌 징후가 없으면 볼스크류가 손으로 도는지 본다"}]


def test_guide_card_keeps_lockout_words_already_in_the_step():
    use({"lines": [{"id": "g1", "text": "잠금·표지 후, 충돌 징후가 없으면 볼스크류가 손으로 도는지 확인한다"}]})
    res = post("guide_card", MAINT)
    assert res.status_code == 200 and "잠금" in res.json()["lines"][0]["text"] and "표지" in res.json()["lines"][0]["text"]


def test_guide_card_rejects_dropping_lockout_words_that_were_in_the_source():
    dropped = {"lines": [{"id": "g1", "text": "충돌 징후가 없으면 볼스크류가 손으로 도는지 확인한다"}]}
    r = use(dropped, dropped)
    assert_503(post("guide_card", MAINT))
    assert len(r.calls) == 2 and "안전 용어가 빠짐" in r.calls[1]["stdin"]


CITE = [{"id": "g1", "text": "충돌이 확인되면 볼스크류 커플링 정렬도 본다 (§2.5 점검 8)"}]


def test_guide_card_prompt_keeps_section_and_check_numbers():
    from backend.llm.compose import system_prompt
    text = system_prompt("guide_card")
    assert "§2.5 점검 8" in text and "빼거나 풀어 쓰지 않고" in text


def test_guide_card_keeps_section_numbers_already_in_the_step():
    use({"lines": [{"id": "g1", "text": "충돌이 확인되면 볼스크류 커플링 정렬도를 본다 (§2.5 점검 8)"}]})
    res = post("guide_card", CITE)
    assert res.status_code == 200 and "2.5" in res.json()["lines"][0]["text"] and "8" in res.json()["lines"][0]["text"]


def test_guide_card_rejects_dropping_section_numbers():
    dropped = {"lines": [{"id": "g1", "text": "충돌이 확인되면 볼스크류 커플링 정렬도를 본다"}]}
    r = use(dropped, dropped)
    assert_503(post("guide_card", CITE))
    assert len(r.calls) == 2 and "빠진 숫자" in r.calls[1]["stdin"]


# ------------------------------------------------------------------ 설비 이름의 '#1'은 마크다운이 아니다 (실행 안내 검증 중 발견)
def test_hash_in_equipment_name_is_not_treated_as_markdown_but_real_markdown_still_is():
    lines = [{"id": "title", "text": "VF-2 #1 알람 2075 (전류가 높은 증폭기) 점검"}, {"id": "symptom", "text": "서보 앰프가 큰 전류를 감지했다."}]
    keep = {"lines": [{"id": "title", "text": "VF-2 #1 알람 2075 (전류가 높은 증폭기) 점검"}, {"id": "symptom", "text": "서보 앰프가 큰 전류를 감지했습니다."}]}
    use(keep)
    assert post("work_order", lines).status_code == 200                                    # '#1'을 그대로 둔 줄은 통과
    bold = {"lines": [{"id": "title", "text": "**VF-2 #1 알람 2075 (전류가 높은 증폭기) 점검**"}, keep["lines"][1]]}
    heading = {"lines": [{"id": "title", "text": "# VF-2 #1 알람 2075 (전류가 높은 증폭기) 점검"}, keep["lines"][1]]}
    for bad in (bold, heading):
        use(bad, bad)
        assert_503(post("work_order", lines))


# ------------------------------------------------------------------ 브리핑 항목 (2026-10-19): 꼬리표·덧붙임은 코드가 지키고 본문만 보낸다
from backend.llm import compose as CMP  # noqa: E402

ITEMS = [{"id": "L01", "text": "[재고 부족] 축 윤활유 재고가 안전 재고(4) 이하 · 9/10"},
         {"id": "L02", "text": "[예방 정비 기한 넘김] VF2-02 윤활유 저장소 양 점검·보충 — 기한 넘김 (기한 09/28) · 9/29"},
         {"id": "L03", "text": "▲ VF2-01 362 공구 수명 한계 도달 · 09:56부터 처리 안 됨"},
         {"id": "L04", "text": "M6 탭 재고가 안전 재고(8) 이하 (24시간 넘게 처리 안 됨) (인계)"}]
ITEM_BODIES = ["축 윤활유 재고가 안전 재고(4) 이하입니다", "VF2-02 윤활유 저장소 양 점검·보충이 기한 넘김입니다",
               "VF2-01 362 공구가 수명 한계에 도달했습니다", "M6 탭 재고가 안전 재고(8) 이하입니다"]


def item_out(*texts):
    return {"lines": [{"id": f"L0{i + 1}", "text": t} for i, t in enumerate(texts)]}


@pytest.mark.parametrize("text,head,body,tail", [
    ("[재고 부족] 축 윤활유 재고가 안전 재고(4) 이하 · 9/10", "[재고 부족] ", "축 윤활유 재고가 안전 재고(4) 이하", " · 9/10"),
    ("[예방 정비 기한 넘김] VF2-02 윤활유 저장소 양 점검·보충 — 기한 넘김 (기한 09/28) · 9/29", "[예방 정비 기한 넘김] ", "VF2-02 윤활유 저장소 양 점검·보충 — 기한 넘김", " (기한 09/28) · 9/29"),
    ("[반복 알람 (1단계)] VF2-01 알람 108 — 7일 안 3번 (반복 알람 1단계, 처리할 때 조치 계획 필수)", "[반복 알람 (1단계)] ", "VF2-01 알람 108 — 7일 안 3번", " (반복 알람 1단계, 처리할 때 조치 계획 필수)"),
    ("▲ VF2-01 362 공구 수명 한계 도달 · 09:56부터 처리 안 됨", "▲ ", "VF2-01 362 공구 수명 한계 도달", " · 09:56부터 처리 안 됨"),
    ("VF2-02 주축 윤활 탱크 양 점검 — 기한 하루 전 (기한 09/29) / 추가: 다음 교대 첫 작업지시 순서 확인 (인계)", "", "VF2-02 주축 윤활 탱크 양 점검 — 기한 하루 전", " (기한 09/29) / 추가: 다음 교대 첫 작업지시 순서 확인 (인계)"),
    ("[예방 정비 기한 넘김] VF2-01 창(유리) 손상 점검 — 기한 10/1 넘김", "[예방 정비 기한 넘김] ", "VF2-01 창(유리) 손상 점검 — 기한 10/1 넘김", ""),
    ("(인계)", "", "(인계)", ""),                                 # 본문이 비면 줄 전체를 본문으로 둔다
])
def test_split_item_separates_tag_body_and_tail_and_joins_back(text, head, body, tail):
    assert CMP.split_item(text) == (head, body, tail)
    assert "".join(CMP.split_item(text)) == text


def test_briefing_sends_only_the_body_and_puts_tags_and_tails_back_unchanged():
    r = use(item_out(*ITEM_BODIES))
    res = post("briefing", ITEMS)
    assert res.status_code == 200 and res.json()["tries"] == 1
    got = [l["text"] for l in res.json()["lines"]]
    assert got == ["[재고 부족] 축 윤활유 재고가 안전 재고(4) 이하입니다 · 9/10",
                   "[예방 정비 기한 넘김] VF2-02 윤활유 저장소 양 점검·보충이 기한 넘김입니다 (기한 09/28) · 9/29",
                   "▲ VF2-01 362 공구가 수명 한계에 도달했습니다 · 09:56부터 처리 안 됨",
                   "M6 탭 재고가 안전 재고(8) 이하입니다 (24시간 넘게 처리 안 됨) (인계)"]
    sent = r.calls[0]["stdin"]
    assert "[재고 부족]" not in sent and "· 9/10" not in sent and "(인계)" not in sent and "▲" not in sent      # 꼬리표·덧붙임은 나가지 않는다
    assert "L01: 축 윤활유 재고가 안전 재고(4) 이하" in sent


def test_briefing_dangling_end_is_rejected_then_the_retry_succeeds():
    bad = item_out(ITEM_BODIES[0], "VF2-02 윤활유 저장소 양 점검·보충이 기한 넘김이고", *ITEM_BODIES[2:])      # '~이고'로 끝나면 이어지는 말이라 끝맺지 않은 줄
    r = use(bad, item_out(*ITEM_BODIES))
    res = post("briefing", ITEMS)
    assert res.status_code == 200 and res.json()["tries"] == 2
    assert "문장이 끝나지 않음" in r.calls[1]["stdin"]


def test_briefing_trailing_period_is_removed_because_the_item_has_none():
    use(item_out(*[b + "." for b in ITEM_BODIES]))
    res = post("briefing", ITEMS)
    assert res.status_code == 200 and res.json()["tries"] == 1
    assert res.json()["lines"][0]["text"] == "[재고 부족] 축 윤활유 재고가 안전 재고(4) 이하입니다 · 9/10"


def test_briefing_only_the_bad_line_goes_back_to_the_original_and_the_rest_is_kept():
    bad = item_out(ITEM_BODIES[0], "VF2-02 윤활유 저장소 양 점검·보충이 기한 넘김입니다 (기한 09/29)", *ITEM_BODIES[2:])      # 숫자를 바꾼 줄 하나
    r = use(bad, bad)
    res = post("briefing", ITEMS)
    assert res.status_code == 200 and len(r.calls) == 2
    got = [l["text"] for l in res.json()["lines"]]
    assert got[1] == ITEMS[1]["text"]                                       # 틀린 줄은 프로그램 문구 그대로
    assert got[0].endswith("이하입니다 · 9/10") and got[2].startswith("▲ ") and got[3].endswith("(인계)")      # 나머지는 다듬은 문장


def test_briefing_when_every_line_is_bad_it_returns_all_originals_not_a_failure():
    bad = item_out(*[b.replace("4", "5").replace("8", "9").replace("362", "363").replace("02", "03") for b in ITEM_BODIES])
    use(bad, bad)
    res = post("briefing", ITEMS)
    assert res.status_code == 200
    assert [l["text"] for l in res.json()["lines"]] == [i["text"] for i in ITEMS]


def test_briefing_wrong_line_ids_are_still_a_failure_not_a_partial():
    bad = {"lines": [{"id": "L01", "text": ITEM_BODIES[0]}, {"id": "L03", "text": ITEM_BODIES[2]}]}
    r = use(bad, bad)
    assert_503(post("briefing", ITEMS))
    assert len(r.calls) == 2


def test_briefing_bodies_with_people_or_account_info_are_not_sent():
    r = use(item_out(*ITEM_BODIES))
    assert_503(post("briefing", [{"id": "L01", "text": "[참고] 담당 U07 점검 · 9/10"}]))
    assert r.calls == []


def test_other_kinds_are_not_salvaged_one_bad_line_still_fails_the_whole_call():
    bad = out("실적은 88개, 총 목표 90개입니다.", GOOD["lines"][1]["text"], GOOD["lines"][2]["text"])
    use(bad, bad)
    assert_503(post())


# ------------------------------------------------------------------ 알림 탭 알람 상세 본문 (2026-10-19): 식별 낱말·심각도·해제는 코드가 지킨다
NOTE = "VF2-01(OP-30)에서 알람 992 — 정지. 사건 S1. 로트 LOT-2610-001-1. 설비 알람 09:20 해제."
NOTE_GOOD = "VF2-01(OP-30)에서 알람 992가 발생했습니다 (정지). 사건 S1. 로트 LOT-2610-001-1. 설비 알람이 09:20에 해제되었습니다."
NOTE_UNKNOWN = "VF2-01(OP-30)에서 알람 9999 — 알람 코드집에 없음, 보전 담당자 호출. 로트 LOT-2610-001-1."
NOTE_UNKNOWN_GOOD = "VF2-01(OP-30)에서 알람 9999가 났는데 알람 코드집에 없음, 보전 담당자 호출. 로트 LOT-2610-001-1."


def note_out(text):
    return {"lines": [{"id": "L01", "text": text}]}


def test_alarm_notice_line_is_polished_and_keeps_every_identifier():
    r = use(note_out(NOTE_GOOD))
    res = post("alarm_notice", [{"id": "L01", "text": NOTE}])
    assert res.status_code == 200 and res.json()["tries"] == 1
    got = res.json()["lines"][0]["text"]
    assert got == NOTE_GOOD
    for token in ("VF2-01", "OP-30", "992", "S1", "LOT-2610-001-1", "09:20"):
        assert token in got
    assert NOTE in r.calls[0]["stdin"]                                    # 프로그램이 만든 기본 문장이 그대로 간다


def test_alarm_notice_not_in_master_sentence_is_polished_too():
    use(note_out(NOTE_UNKNOWN_GOOD))
    res = post("alarm_notice", [{"id": "L01", "text": NOTE_UNKNOWN}])
    assert res.status_code == 200 and "코드집에 없음" in res.json()["lines"][0]["text"] and "보전 담당자 호출" in res.json()["lines"][0]["text"]


def test_alarm_notice_unchanged_line_is_accepted():
    assert CMP._line_problem("alarm_notice", NOTE, NOTE) is None           # 원문이 이미 읽기 쉬우면 그대로 돌려줘도 된다


@pytest.mark.parametrize("why,text,expect", [
    ("알람 번호를 바꿈", NOTE_GOOD.replace("992", "922"), "식별 낱말"),
    ("설비 이름을 바꿈", NOTE_GOOD.replace("VF2-01", "1호기"), "식별 낱말"),
    ("로트 번호를 뺌", NOTE_GOOD.replace("LOT-2610-001-1", "해당"), "식별 낱말"),
    ("시각을 글자로 풀어 씀", NOTE_GOOD.replace("09:20", "9시 20분"), "식별 낱말"),
    ("심각도를 바꿈", NOTE_GOOD.replace("(정지)", "(주의)"), "'정지'"),
    ("해제를 다른 말로 바꿈", NOTE_GOOD.replace("해제되었습니다", "꺼졌습니다"), "'해제'"),
    ("없던 '사건'이 생김", NOTE_UNKNOWN_GOOD.replace("알람 9999가 났는데", "알람 9999 사건이 났는데"), "'사건'"),
    ("원인을 새로 말함", NOTE_GOOD.replace("사건 S1.", "사건 S1이며 원인은 충돌입니다."), "원문에 없던 낱말"),
    ("해야 할 일을 새로 말함", NOTE_GOOD.replace("로트 LOT-2610-001-1.", "로트 LOT-2610-001-1, 점검이 필요합니다."), "원문에 없던 낱말"),
    ("안전 용어를 새로 씀", NOTE_GOOD.replace("사건 S1.", "사건 S1, 전원을 확인합니다."), "원문에 없던 낱말"),
    ("문장을 합침", NOTE_GOOD.replace(". 사건", ", 사건"), "문장 수"),
])
def test_alarm_notice_rewrites_that_change_the_meaning_are_rejected(why, text, expect):
    reason = CMP._line_problem("alarm_notice", NOTE_UNKNOWN if "없던" in why else NOTE, text)       # '없던 사건이 생김'만 원문에 사건이 없는 문장으로 본다
    assert reason and expect in reason, f"{why}: {reason}"


def test_alarm_notice_too_different_a_rewrite_is_rejected():
    reason = CMP._line_problem("alarm_notice", "VF2-01(OP-30)에서 알람 992 — 정지.", "정지 등급의 알람이 지금 이 설비에서 울렸으며 번호는 992이고 설비는 VF2-01(OP-30)입니다.")
    assert reason and "너무 다르게" in reason


def test_alarm_notice_bad_twice_is_a_failure_and_the_second_request_carries_the_reason():
    bad = note_out(NOTE_GOOD.replace("992", "922"))
    r = use(bad, bad)
    assert_503(post("alarm_notice", [{"id": "L01", "text": NOTE}]))
    assert len(r.calls) == 2 and "식별 낱말" in r.calls[1]["stdin"]


def test_alarm_notice_with_people_or_account_info_is_not_sent():
    r = use(note_out(NOTE_GOOD))
    assert_503(post("alarm_notice", [{"id": "L01", "text": NOTE + " 담당 U07."}]))
    assert r.calls == []
