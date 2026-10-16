"""시험 ↔ 요구사항 대응표 점검 (tests/req_map.json, 테스트계획서_v1 시험 ID 방식 T-<요구사항 ID>-<번호>, 2026-10-11 P2).

- 시험 ID 꼴과 요구사항 ID가 맞는지, 요구사항 ID가 요구사항정의서_최종본에 있는지
- 테스트계획서_v1 4장의 경계·예외 시험 30개가 모두 대응표에 있는지 (없는 것도 '없음'으로 적는다)
- 대응표에 적은 시험 함수가 실제로 있는지 — 시험 이름을 바꾸면 대응표도 함께 고친다
기준 문서는 팀 문서를 읽기만 한다. 위치는 두 곳 중 문서 두 개가 모두 있는 곳을 쓴다(2026-10-15 사용자 결정 "추천대로" — 기획 문서가
`참고문서/매뉴얼/11_automotive/` ↔ `기획서 최종본/`을 오갔다: 2026-10-14에 `기획서 최종본/`으로 옮겨졌다가 2026-10-15 01:59 이후 다시 `11_automotive/`에 있고
`기획서 최종본/`은 비어 있었다). 둘 다 없으면 `기획서 최종본/`을 가리켜 파일 없음 오류로 실패한다 — 말없이 건너뛰지 않는다.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLAN_FILES = ("요구사항정의서_최종본.md", "테스트계획서_v1.md")
PLAN_DIRS = (ROOT / "기획서 최종본", ROOT / "참고문서" / "매뉴얼" / "11_automotive")


def _plan_dir() -> Path:
    for d in PLAN_DIRS:
        if all((d / f).is_file() for f in PLAN_FILES):
            return d
    return PLAN_DIRS[0]   # 어디에도 없으면 첫 위치를 가리켜 시험이 파일 없음으로 실패하게 한다


PLAN_DIR = _plan_dir()
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
    text = (PLAN_DIR / "요구사항정의서_최종본.md").read_text(encoding="utf-8")
    assert [it["req_id"] for it in MAP if f"| {it['req_id']} |" not in text] == []


def test_all_boundary_tests_in_plan_are_mapped():
    text = (PLAN_DIR / "테스트계획서_v1.md").read_text(encoding="utf-8")
    sec4 = text.split("## 4.")[1].split("\n## ")[0]
    plan = set(re.findall(rf"\| (T-{REQ_ID}-\d+) \|", sec4))
    assert len(plan) == 30   # 테스트계획서_v1 4장 (v1 2026-10-07) — 계획서가 개정되면 다시 센다
    assert plan == {it["test_id"] for it in MAP if it["kind"] == "경계"}


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
