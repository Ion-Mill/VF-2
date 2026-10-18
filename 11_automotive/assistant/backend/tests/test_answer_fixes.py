"""2026-10-08 검증에서 찾은 결함의 재발 방지 시험 (0단계: 정지 답·출처 지우기·[가상]·데이터 시각)."""
import csv
import re
from datetime import date

from backend.config import DOCS_DIR, SIM_OUT
from backend.llm.adapter import NUM_TOKEN, _norm
from backend.rag.sanitize import sanitize
from backend.repositories.csv_repo import get_repo
from backend.services.answer import answer
from backend.tools import query_tools as T


def _csv(name):
    with open(SIM_OUT / f"{name}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- 정지 답 (FR-MNT-01-04, DOC-07 §5.1·§5.4)
def test_stops_count_every_record_by_group():
    """'몇 번 멈췄어?'는 고장만이 아니라 멈춘 기록 전부를 센다. 정지 기록 파일에서 따로 센 값과 같아야 한다."""
    shifts = {s["shift_id"]: s for s in _csv("calendar_shift")}
    mine = [d for d in _csv("downtime") if d["equipment_id"] == "VF2-01"
            and shifts[d["shift_id"]]["prod_date"] == "2026-09-30" and shifts[d["shift_id"]]["shift"] == "N"]
    r = T.stops("SUP", "VF2-01", date(2026, 9, 30), date(2026, 9, 30), "N")
    assert r["total_count"] == len(mine) == sum(g["count"] for g in r["by_group"])
    assert r["total_minutes"] == sum(float(d["minutes"]) for d in mine) == sum(g["minutes"] for g in r["by_group"])
    assert [g["group_ko"] for g in r["by_group"]][:5] == ["고장", "자재·흐름", "준비", "조작", "계획"]  # 0건 그룹도 보인다
    assert r["range"].endswith("야간")  # 화면에 N/D를 그대로 내지 않는다


def test_stops_answer_shows_all_groups_formula_and_sources():
    a = answer("어제 야간 VF2-01 몇 번 멈췄어?", "SUP")
    c = a["conclusion"]
    r = T.stops("SUP", "VF2-01", date(2026, 9, 30), date(2026, 9, 30), "N")
    assert f"정지 전체 {r['total_count']}번 {r['total_minutes']:g}분" in c
    for g in r["by_group"]:
        assert f"{g['group_ko']} {g['count']}번" in c
    assert f"필수 정지(고장 5분 이상) {len(r['rows'])}번" in c
    assert "추정 = 정지 1건마다 정지 시간 ÷ 기준 사이클 VF2-01 7.0분" in c  # 추정 손실에는 계산식과 기준 사이클 (규칙 2.2)
    assert {"DOC-07 §5.1", "DOC-07 §5.4"} <= {f"{e['doc_id']} §{e['section']}" for e in a["evidence"]}
    assert a["current_data"][0]["as_of"] and a["current_data"][0]["range"].endswith("야간")
    assert a["caution"] is None  # 운영 답에 정의 출처를 붙였다고 주의 문구가 생기지 않는다


# ---------------------------------------------------------------- 출처 지우기는 출처만 (552 점검 7 "±20%" 빠짐)
def test_sanitize_keeps_content_parentheses():
    assert "(원문 값 ±20%)" in sanitize("원문 표와 비교한다 (원문 값 ±20%)")
    assert "(원문 기준표 참조)" in sanitize("클램프 힘을 잰다 (원문 기준표 참조)")
    for src in ("(원문: TG0125 Rev F 4쪽)", "(원문)", "(원문 그대로)", "(출처 번호 S1~S16)", "(KOSHA B-M-25-2026 6장)",
                "(원문 URL https://example.com/x)"):
        assert sanitize(f"본문 {src} 끝") == "본문 끝", src


def _raw_step_cells(section: str) -> dict[str, str]:
    """사내 문서 '원본 파일'에서 점검 순서 표의 할 일 칸을 읽는다 (검색 조각·sanitize를 거치지 않음 — 구현과 독립)."""
    text = next(DOCS_DIR.glob("DOC-03_*.md")).read_text(encoding="utf-8")
    m = re.search(rf"^### {re.escape(section)} .*?$(.*?)(?=^#{{2,3}} )", text, re.M | re.S)
    out, on = {}, False
    for line in (m.group(1) if m else "").splitlines():
        s = line.strip()
        if s.startswith("| #") and "누가" in s and "할 일" in s:
            on = True
            continue
        if on and s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if re.fullmatch(r"\**★?\d+\**", cells[0]):
                out[cells[0].replace("*", "")] = cells[2]
            continue
        on = False
    return out


def test_alarm_steps_keep_every_number_of_the_source_document():
    """점검 단계의 숫자·단위(±20%, 5분 …)가 사내 문서 원본과 같아야 한다. 단계 수만 세면 글자 빠짐을 못 잡는다."""
    checked = 0
    for m in get_repo().master("alarm_master"):
        if "§" not in m["doc03_section"]:
            continue
        cells = _raw_step_cells(m["doc03_section"].split("§")[1].strip())
        if not cells:
            continue
        a = answer(f"{m['code']} 알람 뜨면 뭐부터 봐?", "SUP")
        by_no = {s.split(" ", 1)[0]: s for s in a["steps"]}
        for no, raw in cells.items():
            body = re.sub(r"\[[^\]]*\]", "", raw)  # [실제: …] 꼬리표 안의 원문 쪽 번호 등은 원래 지운다
            body = re.sub(r"\((?:원문|출처)[^)]*(?:TG|RD|AD|ID)\d{4}[^)]*\)", "", body)
            want = {f"{_norm(x.group(1))}{x.group(2) or ''}" for x in NUM_TOKEN.finditer(body)}
            got_text = by_no.get(no, "")
            got = {f"{_norm(x.group(1))}{x.group(2) or ''}" for x in NUM_TOKEN.finditer(got_text)}
            assert want <= got, (m["code"], no, want - got)
        checked += 1
    assert checked >= 10


# ---------------------------------------------------------------- 팀 정의 값은 [가상] (규칙 2.2·4.1)
def test_alarm_answer_marks_team_defined_severity_and_owner():
    c = answer("552 알람 뜨면 뭐부터 봐?", "SUP")["conclusion"]
    assert "심각도는 정지 [가상]" in c and "보전 담당자 [가상]" in c
