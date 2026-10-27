"""원문 문서 이름 고침 (2026-10-11, 사용자 결정 "A만 바꿔 보이기" — research_notes/사내문서_Haas낱말_목록_20261011.md).

비서 검색 조각·사내 문서 보기(SCR-24)에서 Haas 원문 문서·목록·자료를 가리키는 말은 "제조사"로 바뀌어야 하고,
설비·기능 이름(Haas VF-2·NGC·ATM), 부품번호(Haas P/N …), 서비스 부서(Haas 서비스·HFO)는 그대로 남아야 한다.
검사 꼴은 sanitize의 HAAS_DOC와 따로 쓴 엄격한 꼴이다 — 같은 정규식을 쓰면 함께 놓친다 (root-cause-guards 8절).
"""
import re

import pytest

from backend.rag import chunker
from backend.rag.chunker import load_corpus
from backend.rag.doc_view import _files, doc_body
from backend.rag.sanitize import sanitize

# 원문을 가리키는 "Haas": 낱말 0~4개 뒤의 문서 명사, "Haas는 …", 근거 꼬리표, 5분 대기, 참고값, 용어집 근거 표시, 영문 제목
STRICT = re.compile(
    r"Haas\s*(?:[^\s|()\[\]]+\s+){0,4}?(?:매뉴얼|설명서|목록|안내|절차|자료|웹\s*사이트|기준표|점검표|표본|"
    r"Schedule|Checklist|Manual|Guide|Safety|Troubleshooting)"
    r"|Haas(?:는|가|도)\s|\[실제\]\s*Haas|Haas\s*\[실제\]|Haas\s+\d+분|Haas\s+기계의|\[Haas\s+(?:알람|매뉴얼)\]"
    r"|Mill Weekly Maintenance|VMC Maintenance", re.I)


def _view_texts():
    for d in _files():
        for s in doc_body(d)["sections"]:
            yield d, s["section"], s["title"] + "\n" + s["text"]


def test_chunks_have_no_haas_document_names():
    left = [(c.doc_id, c.section, STRICT.search(c.title + "\n" + c.text).group(0)) for c in load_corpus()
            if STRICT.search(c.title + "\n" + c.text)]
    assert left == []


def test_doc_view_has_no_haas_document_names():
    left = [(d, s, STRICT.search(t).group(0)) for d, s, t in _view_texts() if STRICT.search(t)]
    assert left == []


def test_strict_pattern_finds_the_old_forms():
    """검사 꼴이 실제로 잡는지: 고치기 전 사내 문서의 꼴 (2026-10-11 목록의 A 30곳에서 고름)."""
    for s in ("**Haas 공식 NGC 알람 목록의 알람 362", "Haas 웹사이트 알람 검색", "Haas 드로바 힘 측정 절차를 따른다",
              "**Haas 밀 주간 정비 점검표**", "Haas VMC Maintenance Schedule", "Haas는 공급원에서 끄고 잠금·표지를 하라고 한다",
              "| [실제] Haas 알람 |", "| Haas [실제] |", "Haas 5분 대기", "Haas 기계의 안전 작동 최대 온도",
              "[Haas 매뉴얼] =", "원문 근거(Haas 서보 앰프 고장 대응 안내 Electrical Safety)는", "Haas 원시 표본은"):
        assert STRICT.search(s), s


@pytest.mark.parametrize("keep", [
    "Haas VF-2 수직 머시닝센터", "Haas HCS-80", "Haas NGC", "Haas 고급 공구 관리(ATM)", "Haas ATM의 LIFE",
    "화면에 Haas 로고가 보일 때까지", "Haas P/N 93-5656", "(Haas 99-1686, CS-GRS)", "Haas P/N 58-1391",
    "Haas 서비스(HFO)를 부른다", "Haas 공인 서비스점", "(Haas HFO 등)", "(Haas: [POWER OFF])", "Haas MTConnect 항목",
])
def test_equipment_part_service_names_stay(keep):
    """설비·기능·부품·서비스 이름은 원문 출처가 아니므로 그대로 둔다 — 조각이나 문서 보기 어딘가에 그대로 있어야 한다."""
    texts = [c.title + "\n" + c.text for c in load_corpus()] + [t for _, _, t in _view_texts()]
    assert any(keep in t for t in texts), keep
    assert not STRICT.search(keep), keep


def test_doc_view_keeps_part_and_service_parens():
    """문서 보기가 "(Haas …)" 괄호를 통째로 지우던 결함 (2026-10-11 고침): 부품번호·서비스·버튼 괄호가 보여야 한다."""
    view = "\n".join(t for _, _, t in _view_texts())
    for s in ("(Haas P/N 58-1391", "(Haas 99-1686, CS-GRS)", "(Haas 공인 서비스점 HFO 등)", "(Haas HFO 등)",
              "(Haas: [POWER OFF])", "(Haas 키)"):
        assert s in view, s


@pytest.mark.parametrize("raw, want", [
    ("Haas는 공급원에서 끄고 잠금·표지를 하라고 한다 [실제]", "제조사는 공급원에서 끄고 잠금·표지를 하라고 한다 [실제]"),
    ("Haas 알람 목록에는 심각도가 없다.", "제조사 알람 목록에는 심각도가 없다."),
    ("HCS-80 자체의 정밀도 값은 Haas 자료에서 찾지 못했다.", "HCS-80 자체의 정밀도 값은 제조사 자료에서 찾지 못했다."),
    ("이 목록은 Haas 웹사이트 알람 검색(haascnc.com/service/alarm-search)의 2025-01-30 자료다.",
     "이 목록은 제조사 웹사이트 알람 검색의 2025-01-30 자료다."),           # 예전 찌꺼기 "검색( 2025"
    ("\"STATUS, BUSY\"는 Haas 한국어 조작 매뉴얼(2015) 101쪽, \"IDLE\"은",
     "\"STATUS, BUSY\"는 제조사 한국어 조작 매뉴얼, \"IDLE\"은"),             # 예전 찌꺼기 "(2015) ,"
    ("출처: Haas NGC 알람 목록 [실제]. 알람 공식 페이지는 `docs/haas/ngc_official/x/`.",
     "출처: 제조사 NGC 알람 목록 [실제]."),                                    # 예전 찌꺼기 "페이지는 ."
    ("**Haas 밀 주간 정비 점검표**(Mill Weekly Maintenance Checklist, 개정 표기 없음)에서",
     "**제조사 밀 주간 정비 점검표**에서"),
    ("| 한도 도달 | — | [실제] Haas 알람 |", "| 한도 도달 | — | [실제] 제조사 알람 |"),
    ("제어기 전원을 끈다 (Haas: [POWER OFF])", "제어기 전원을 끈다 (Haas: [POWER OFF])"),         # 버튼 이름: 그대로
    ("반장은 외부 서비스(Haas 공인 서비스점 HFO 등) 요청을 검토", "반장은 외부 서비스(Haas 공인 서비스점 HFO 등) 요청을 검토"),
    # 목록에 없던 원문 번호 (같은 날 찾음): 매뉴얼 번호 96-xxxx·서비스 알림 SA0000은 지우고, 부품번호 93-xxxx는 남긴다
    ("VF-1,2가 있었지만(96-8100 rev L, 1.8절 ) 2011년 매뉴얼 표에는", "VF-1,2가 있었지만 2011년 매뉴얼 표에는"),
    ("대형 기종만 남았다(96-0283D, 인쇄 Counterbalance Air Pressure) ② 현행", "대형 기종만 남았다 ② 현행"),
    ("개선 서보 케이블이 있음, 서비스 알림 SA0018) [실제]", "개선 서보 케이블이 있음, 서비스 알림) [실제]"),
    ("지정 윤활유로 보충한다: Haas P/N 93-5656 또는 Mobil Vactra No. 2", "지정 윤활유로 보충한다: Haas P/N 93-5656 또는 Mobil Vactra No. 2"),
])
def test_sanitize_haas_examples(raw, want):
    assert sanitize(raw) == want


def test_original_edition_section_is_not_indexed():
    """DOC-03 §1.2 "쓰는 원문 판"은 원문 문서 이름·장 번호 표라 조각에서 뺀다 (문서 보기는 숨김)."""
    assert not [c for c in load_corpus() if c.doc_id == "DOC-03" and c.section == "1.2"]
    sec = next(s for s in doc_body("DOC-03")["sections"] if s["section"] == "1.2")
    assert sec["hidden"]


def test_long_sections_split_on_line_boundaries():
    """긴 절은 줄 경계에서 나눈다 (2026-10-11): 글자 수로 자르면 "두께·폭 공|차"처럼 낱말·표 줄이 갈렸다."""
    body = "\n".join(f"| {i} | " + "가" * 50 + " |" for i in range(200))
    parts = chunker._split_long(body)
    assert len(parts) > 1 and all(len(p) <= chunker.MAX_CHARS for p in parts)
    assert "\n".join(parts) == body
    assert all(p.startswith("| ") and p.endswith(" |") for p in parts)
    assert chunker._split_long("나" * (chunker.MAX_CHARS + 10)) == ["나" * chunker.MAX_CHARS, "나" * 10]  # 한 줄이 길면 글자 수로
    split = [c for c in load_corpus() if c.chunk_id.count(":") >= 2]
    assert split, "나뉜 절이 없다 — 시험 가정 확인 필요"
    for c in split:
        assert not c.text.startswith((" ", "\t")), c.chunk_id
    assert any("두께·폭 공차(EN 755-5" in c.text for c in load_corpus() if c.doc_id == "DOC-06")


def test_chunk_count():
    """사내 문서 현행판(2026-10-07)의 조각 수: 196 → 195 (DOC-03 §1.2 뺌, 2026-10-11). 문서가 개정되면 다시 센다."""
    assert len(load_corpus()) == 195


# ---------------------------------------------------------------- "Haas" 낱말 없는 원문 이름·지운 뒤 찌꺼기
# 2026-10-11 사용자 결정 "⑤ E5 전에 함께" (사내문서_Haas낱말_목록_20261011.md 4.6절 ①). 검사 꼴은 sanitize의 SRC_NAME·RESIDUE와
# 따로 쓴 엄격한 꼴이다. 용어집의 낱말 뜻 "Troubleshooting Guide (TSG)"는 원문 이름이 아니라 남는다.
STRICT_NO_HAAS = re.compile(
    r"^[ \t]*(?:\*\*)?원문(?:\*\*)?[ \t]*:"                                                   # "**원문:**" 줄
    r"|(?:서비스|조작|운영자)\s*매뉴얼(?:\s*본문)?\s*\(?\s*(?:한국어판\s*)?\d+\.\d+"             # 매뉴얼 이름 + 장 번호
    r"|(?:19|20)\d{2}년\s*(?:서비스\s*)?매뉴얼|영문\s*\d{4}판"                                # 판 연도
    # 처음 꼴은 "Circuit Breaker"였다 → 용어집 낱말 뜻("Circuit Breaker | 회로 차단기")까지 잡아 시험 가정이 틀렸다 (2026-10-11).
    # 원문 이름인 "… Circuit Breaker TSG"만 본다
    r"|Symptom Table|Circuit Breaker TSG|Spindle Lubricant|\d+T\s*주축\s*TSG"
    r"|KOSHA\s*(?:GUIDE\s*)?[A-Z]-[A-Z]-\d+-\d+", re.M)                                         # KOSHA 지침 번호
# KOSHA 지침 장 번호("KOSHA 지침 6장")는 검색 조각에서만 뺀다. 문서 보기는 2026-10-07 설계대로 번호만 "KOSHA 지침"으로 바꾸고 장은 남긴다
KOSHA_CHAPTER = re.compile(r"KOSHA 지침\s*\d+장")
RESIDUE_STRICT = re.compile(r"\(\s*[.,;·]\s|\(\s*,|,\s*\)|·\s*\)|:[ \t]+\.(?:[ \t]|$)|\S[ \t]+\.(?:[ \t]|$)|,[ \t]*$", re.M)


def _all_texts():
    yield from (("조각", c.chunk_id, c.title + "\n" + c.text) for c in load_corpus())
    yield from (("문서 보기", f"{d}§{s}", t) for d, s, t in _view_texts())


def test_no_unnamed_source_names_in_chunks_or_doc_view():
    left = [(w, k, STRICT_NO_HAAS.search(t).group(0)) for w, k, t in _all_texts() if STRICT_NO_HAAS.search(t)]
    assert left == []
    assert [c.chunk_id for c in load_corpus() if KOSHA_CHAPTER.search(c.text)] == []


def test_no_removal_residue_in_chunks_or_doc_view():
    """번호·쪽을 지운 뒤 남던 "쓴다(. 설치"·"보고서(, 펌프"·"(starvation, )"·"WSC 2001, 1·)"·"칸 설명: ."·"(흡입성) ." 꼴이 없다."""
    left = [(w, k, t[max(0, m.start() - 20):m.end() + 5]) for w, k, t in _all_texts() for m in RESIDUE_STRICT.finditer(t)]
    assert left == []


def test_strict_no_haas_patterns_find_the_old_forms():
    """검사 꼴이 실제로 잡는지: 고치기 전 조각의 꼴 (2026-10-11 노트 4.6절과 찌꺼기 훑기에서 고름)."""
    for s in ("**원문:** 제조사 알람 목록 992 / — Symptom Table", "같은 표가 VF/VM 서비스 매뉴얼 18.1(.",
              "조작 매뉴얼 본문(한국어판 4.9.2, 영문 2025판 4.55~4.56)", "① 2005년 서비스 매뉴얼 균형 장치",
              "② 40T 주축 TSG \"use", "③ ** (2025-12)** Spindle Lubricants \"Mill", "/ .4 Circuit Breaker TSG"):
        assert STRICT_NO_HAAS.search(s), s
    for s in ("고 쓴다(. 설치 때", "점검 보고서(, 펌프 일련번호", "굶음(starvation, ): 앞", "(Roser 외, WSC 2001, 1·). 판단",
              "칸 설명: . 오프셋이", "mg/m3(흡입성) . 원액", "제92조·제95조, \n출처"):
        assert RESIDUE_STRICT.search(s), s


def test_removed_text_came_back():
    """원문 번호 뒤 글까지 지우던 규칙이 사내 문서 글을 지웠다 (2026-10-11 고침): 괄호 안 번호는 괄호째만, 줄은 넘지 않는다."""
    chunks = {(c.doc_id, c.section): c.text for c in load_corpus()}
    assert "④ 점검 9 모터 브레이크 절차가 이 기계에 그대로 쓰인다" in chunks[("DOC-03", "2.5")]
    assert "같은 표가 제조사 서비스 매뉴얼에도 있다" in chunks[("DOC-04", "2")]
    # KOSHA 지침 번호와 장 번호(원문 위치)는 빼고 문장은 남긴다. 처음에는 "KOSHA 지침 6장(작업 전)과 7장(작업 후)의"로 남겼는데,
    # "작업 전" 낱말이 DOC-05 §2를 "잠금·표지 작업 전 6단계가 뭐야?"의 검색 1등으로 올려 6단계 표(§2.1) 대신 일반 규칙으로 답했다 (2026-10-11)
    assert "LOTO)는 KOSHA 지침의 순서를 그대로 따른다" in chunks[("DOC-05", "2")]
    assert "제95조\n출처: DOC-05 안전 작업 기준서 Rev.3 §2·§4·§5" in chunks[("DOC-05", "7")]   # 안전 서식 끝의 사내 출처 줄
    view = "\n".join(t for _, _, t in _view_texts())
    # 문서 보기는 원래 PRE가 지침 번호만 바꿔 이 문장이 바르게 보였다 (장 번호 남김) — 그대로인지 본다
    for s in ("④ 점검 9 모터 브레이크 절차가 이 기계에 그대로 쓰인다", "LOTO)는 KOSHA 지침 6장(작업 전)과 7장(작업 후)의 순서를 그대로 따른다"):
        assert s in view, s


def test_glossary_term_stays():
    gl = "\n".join(c.text for c in load_corpus() if c.doc_id == "GLOSSARY")
    assert "Troubleshooting Guide (TSG)" in gl


@pytest.mark.parametrize("raw, want", [
    ("**원문:** Haas 알람 목록 992 (TG0125 Rev F) / — Symptom Table, Mechanical Blockage\n다음 줄", "다음 줄"),
    ("같은 표가 VF/VM 서비스 매뉴얼 18.1(VFVM-SM-18)에도 있다. 원문 끝 주석: \"권장 주기는 …\" (VFVM-SM-18 226행).",
     "같은 표가 제조사 서비스 매뉴얼에도 있다. 원문 끝 주석: \"권장 주기는 …\"."),
    ("\"…달린다\"고 쓴다(VFVM-SM-07 45행) ④ 점검 9 모터 브레이크 절차가 이 기계에 그대로 쓰인다.",
     "\"…달린다\"고 쓴다 ④ 점검 9 모터 브레이크 절차가 이 기계에 그대로 쓰인다."),
    ("잠금·표지(Lockout/Tagout, LOTO)는 KOSHA B-M-25-2026 6장(작업 전)과 7장(작업 후)의 순서를 그대로 따른다.",
     "잠금·표지(Lockout/Tagout, LOTO)는 KOSHA 지침의 순서를 그대로 따른다."),
    ("근거: 산업안전보건기준에 관한 규칙 제92조·제95조, KOSHA B-M-25-2026\n출처: DOC-05 안전 작업 기준서 Rev.3 §2·§4·§5",
     "근거: 산업안전보건기준에 관한 규칙 제92조·제95조\n출처: DOC-05 안전 작업 기준서 Rev.3 §2·§4·§5"),
    ("병목으로 본다 (Roser 외, WSC 2001, 1·3쪽). 판단 창", "병목으로 본다 (Roser 외, WSC 2001). 판단 창"),
    ("굶음(starvation, 15쪽): 앞 버퍼가 비면", "굶음(starvation): 앞 버퍼가 비면"),
    ("펌프 교체 전 절삭유 펌프 점검 보고서(ID0013, 펌프 일련번호 필요) [실제: TG0138].",
     "펌프 교체 전 절삭유 펌프 점검 보고서(펌프 일련번호 필요) [실제]."),
    ("ACGIH TWA 5 mg/m3(흡입성) (2~3쪽). 원액(SDS 본문)과", "ACGIH TWA 5 mg/m3(흡입성). 원액(SDS 본문)과"),
    ("- 공구 오프셋 화면의 칸 설명: PDF 158쪽. 오프셋이 없으면 알람 814", "- 공구 오프셋 화면의 칸 설명. 오프셋이 없으면 알람 814"),
    ("① 2005년 서비스 매뉴얼 균형 장치 압력표에는 VF-1,2가 있었지만(96-8100 rev L, 1.8절 34쪽) 2011년 매뉴얼 표에는",
     "① 제조사 옛 서비스 매뉴얼 균형 장치 압력표에는 VF-1,2가 있었지만 그 뒤 판 매뉴얼 표에는"),
    ("② 40T 주축 TSG TG0101 Rev B (2025-11) \"use the correct spindle lubrication (SHC 625)\" ③ RD0040 **Rev H (2025-12)** "
     "Spindle Lubricants \"Mill\"",
     "② 제조사 주축 고장 대응 안내 \"use the correct spindle lubrication (SHC 625)\" ③ 제조사 주축 윤활유 표 \"Mill\""),
    ("조작 매뉴얼 본문(한국어판 4.9.2, 영문 2025판 4.55~4.56)에는 리셋 키 순서가 없다.", "제조사 조작 매뉴얼 본문에는 리셋 키 순서가 없다."),
    ("아이콘 표(PDF 111쪽)는 \"…\", 설정 설명(PDF 446쪽, 영문 2025판 PDF 529쪽)은 \"…\"이다", "아이콘 표는 \"…\", 설정 설명은 \"…\"이다"),
    ("**근거:** Haas VMC Maintenance Schedule RD0080 Rev.B (2025-05) [실제] — 이하 \"RD0080 n행\"은 "
     "`RD0080__RevB-2025-05__20261003__body.md`의 줄 번호. 같은 표가", "**근거:** 제조사 정비 주기표 [실제]. 같은 표가"),
    ("(예외는 플러그형 장비·핫탭뿐, 5.1(2), 3쪽). 미국", "(예외는 플러그형 장비·핫탭뿐, 5.1(2)). 미국"),
    # 그대로 두는 것: 용어집 낱말 뜻, 사내 설계서 링크
    ("| Troubleshooting Guide (TSG) | 고장 대응 안내 (사내: 고장 대응 매뉴얼) | 트러블슈팅 |",
     "| Troubleshooting Guide (TSG) | 고장 대응 안내 (사내: 고장 대응 매뉴얼) | 트러블슈팅 |"),
    ("출처: [설계서 5.1](../가상데이터설계서.md#51-설비). CMM-01 [참고]", "출처: [설계서 5.1](../가상데이터설계서.md#51-설비). CMM-01 [참고]"),
])
def test_sanitize_unnamed_source_examples(raw, want):
    assert sanitize(raw) == want
