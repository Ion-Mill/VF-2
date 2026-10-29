"""시험 ↔ 요구사항 대응표 점검 (tests/req_map.json, 테스트계획서_v1 시험 ID 방식 T-<요구사항 ID>-<번호>, 2026-10-11 P2).

- 시험 ID 꼴과 요구사항 ID가 맞는지, 요구사항 ID가 요구사항정의서에 있는지
- 경계·예외 시험 30개(테스트계획서 4장에서 가져온 것)가 대응표에 모두 있는지 (없는 것도 '없음'으로 적는다).
  테스트계획서 문서가 저장소에서 빠져서(2026-10-27) 이 시험은 문서를 읽지 않고 대응표 자체만 점검한다
- 대응표에 적은 시험 함수가 실제로 있는지 — 시험 이름을 바꾸면 대응표도 함께 고친다
기준 문서는 요구사항정의서 하나이고 읽기만 한다. 위치는 `11_automotive/`(= assistant의 한 단계 위)이다.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLAN_DIR = ROOT.parent   # 11_automotive/ — 요구사항정의서.md가 있는 곳 (없으면 파일 없음 오류로 실패한다, 말없이 건너뛰지 않는다)
MAP = json.loads((HERE / "req_map.json").read_text(encoding="utf-8"))["items"]
REQ_ID = r"(?:FR-[A-Z]{3}-(?:\d{2}|COM)-\d{2}|NFR-[A-Z]{3,4}-\d{2})"
STATUS = {"있음", "일부", "일부+불일치", "없음"}


def test_ids_have_plan_form():
    for it in MAP:
        assert re.fullmatch(rf"T-{REQ_ID}-\d+", it["test_id"]), it["test_id"]
        assert it["test_id"].startswith("T-" + it["req_id"] + "-"), it
        assert it["status"] in STATUS and it["kind"] in {"경계", "추가"}, it
    ids = [it["test_id"] for it in MAP]
    assert len(ids) == len(set(ids))


def test_req_ids_exist_in_requirements():
    text = (PLAN_DIR / "요구사항정의서.md").read_text(encoding="utf-8")
    assert [it["req_id"] for it in MAP if f"| {it['req_id']} |" not in text] == []


def test_all_boundary_tests_in_plan_are_mapped():
    # 경계·예외 시험은 30개 (테스트계획서 v1 4장, 2026-10-07). 문서 없이 대응표만 본다
    boundary = [it["test_id"] for it in MAP if it["kind"] == "경계"]
    assert len(boundary) == 30
    assert len(set(boundary)) == 30


def test_listed_tests_exist():
    for it in MAP:
        if it["status"] == "있음":
            assert it["tests"], it
        if it["status"] == "없음":
            assert not it["tests"], it
        for t in it["tests"]:
            f, fn = t.split("::")
            src = (HERE / f).read_text(encoding="utf-8")
            assert re.search(rf"^def {re.escape(fn)}\(", src, re.M), t
