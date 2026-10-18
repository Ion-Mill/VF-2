"""고정 안전 서식 (UI설계서 6.5, DOC-05 §7). AI가 쓰거나 고치지 않는다 (ai-operations-assistant 규칙 2.5).

- 블록 글자는 DOC-05 Rev.2 §7 블록을 그대로 옮긴 상수다. `{ }` 칸만 DOC-05 §3 설비별 차단 지점에서 채운다.
- 규칙 2.5 "블록 글자에 Haas·KOSHA 원문 이름을 넣지 않는다"가 DOC-05 §7·UI설계서 6.5보다 엄격하므로,
  [작업 전]/[작업 후] 머리의 KOSHA 지침 이름과 근거 줄의 KOSHA 지침 이름만 뺀다 (단계 글자·순서는 그대로).
  이 차이는 불일치로 기록한다 (2026-10-07). 테스트가 DOC-05 §7 원본과 한 줄씩 대조한다.
- 고전압 줄은 OP-30(VF2-01·VF2-02)에만 둔다. 다른 설비는 그 자리에 "§3 저장 에너지 확인"을 둔다.
"""
from __future__ import annotations

import re

from backend.rag.chunker import load_corpus

# DOC-05 Rev.2 §7 블록 (KOSHA 원문 이름만 뺌). 체크칸 9개(6.1~7.3)는 작업기록서 잠금·표지 체크와 같다.
BEFORE = [
    ("6.1", "기기 등의 운전정지 준비"),
    ("6.2", "기기 등의 운전정지"),
    ("6.3", "기기 등의 차단"),
    ("6.4", "잠금장치 또는 표지의 설치"),
    ("6.5", "저장 또는 축적된 에너지의 관리"),
    ("6.6", "차단 확인"),
]
AFTER = [
    ("7.1", "기기 등의 점검"),
    ("7.2", "작업자 확인"),
    ("7.3", "잠금장치·표지의 제거"),
]
HIGH_VOLTAGE = ["고전압 표시등이 꺼진 뒤 최소 5분 기다린 뒤 제어반 작업 시작", "(안전 작업 기준서 DOC-05 §4.1)"]
HIGH_VOLTAGE_HEAD = "[고전압 대기]  (VF2-01·VF2-02 제어반 작업 때)"
PPE = [
    "보안경 · 안전화 · (소음 구역) 청력 보호구",
    "회전체를 다룰 때 면장갑 금지 — 손에 밀착되는 장갑만 (법 제95조)",
    "톱날·칩·공작물을 멈춘 상태에서 다룰 때 베임 방지 장갑",
]
BASIS = "근거: 산업안전보건기준에 관한 규칙 제92조·제95조"
SOURCE = "출처: DOC-05 안전 작업 기준서 Rev.2 §2·§4·§5"
TITLE = "안전 작업 (고정 서식 · AI 작성 아님)"
OTHER_PROCESS_LINE = "§3 저장 에너지 확인"
OP30 = {"VF2-01", "VF2-02"}
DOC05_SECTION = {"SAW-01": "3.1", "MIL-01": "3.2", "VF2-01": "3.3", "VF2-02": "3.4", "WSH-01": "3.5", "CMM-01": "3.6"}

# DOC-05 §7 원본에서 빼는 글자 (테스트 대조용)
KOSHA_STRIPS = [(re.compile(r"\s+KOSHA GUIDE B-M-25-2026 [67]장"), ""), (re.compile(r", KOSHA B-M-25-2026"), "")]


def _rows(text: str) -> list[list[str]]:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip().replace("**", "") for c in s.strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                out.append(cells)
    return out


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\[(실제|참고|가상|제안)[^\]]*\]", "", s)).strip()


def isolation(equipment_id: str) -> dict:
    """DOC-05 §3 설비별 차단 지점·저장 에너지 (조각은 이미 원문 출처를 뺀 것)."""
    sec = DOC05_SECTION[equipment_id]
    chunks = [c for c in load_corpus() if c.doc_id == "DOC-05" and c.section == sec]
    text = "\n".join(c.text for c in chunks)
    points, energy = [], []
    for cells in _rows(text):
        if re.fullmatch(rf"{re.escape(equipment_id)}-[EP]\d", cells[0]) and len(cells) >= 2:
            points.append(f"{cells[0]} {_clean(cells[1])}")
        elif cells[0] not in ("번호", "저장 에너지") and len(cells) >= 2 and not re.match(r"[A-Z]{3}-\d", cells[0]):
            energy.append(_clean(cells[0]))
    if not energy and equipment_id == "VF2-02":  # §3.4 "VF2-01과 같은 모델이라 §3.3과 같다"
        energy = isolation("VF2-01")["energy"]
    return {"points": points, "energy": energy, "section": sec}


def _ref(section: str) -> dict:
    """DOC-05 절 가리킴. doc_no는 API명세서_v1 출처 칸 이름(2026-10-11 P1) — 옛 칸 doc_id도 둔다.
    문서 이름·개정(rev)이 든 출처 전체는 지침카드가 이 가리킴으로 services.cite.cite()를 불러 붙인다."""
    return {"doc_id": "DOC-05", "doc_no": "DOC-05", "section": section}


def stop_block(equipment_id: str) -> dict:
    """정지 등급 알람의 전체 블록 (지침카드·작업지시서·다른 공정 간이 작업기록)."""
    iso = isolation(equipment_id)
    lines = [
        f"설비: {equipment_id}    차단 지점: {', '.join(iso['points']) or '없음'}",
        f"저장 에너지: {', '.join(iso['energy']) or '없음'}",
    ]
    sections = [
        {"head": "[작업 전]", "items": [f"{n} {t}" for n, t in BEFORE], "check": True},
    ]
    if equipment_id in OP30:
        sections.append({"head": HIGH_VOLTAGE_HEAD, "items": [HIGH_VOLTAGE[0]], "note": HIGH_VOLTAGE[1], "check": True})
    else:
        sections.append({"head": OTHER_PROCESS_LINE, "items": [], "check": False})
    sections += [
        {"head": "[보호구]", "items": PPE, "check": True},
        {"head": "[작업 후]", "items": [f"{n} {t}" for n, t in AFTER], "check": True},
    ]
    return {"kind": "block", "title": TITLE, "equipment_id": equipment_id, "lines": lines, "sections": sections,
            "basis": BASIS, "source": SOURCE, "fixed": True, "loto_steps": [n for n, _ in BEFORE + AFTER],
            "cite": _ref("7")}


def render_text(block: dict) -> list[str]:
    """화면·테스트용 글자 줄 (DOC-05 §7 블록과 같은 순서)."""
    out = list(block["lines"]) + [""]
    for s in block["sections"]:
        out.append(s["head"])
        for it in s["items"]:
            out.append(f" □ {it}")
        if s.get("note"):
            out.append(f"   {s['note']}")
        out.append("")
    return out + [block["basis"], block["source"]]


def short_task(code: str, equipment_id: str) -> dict | None:
    """주의 등급 보충 알람 (예: 2075): 블록 대신 DOC-05 §2.4 판단 표의 해당 줄을 그대로 붙인다."""
    chunks = [c for c in load_corpus() if c.doc_id == "DOC-05" and c.section == "2.4"]
    head = None
    for cells in _rows("\n".join(c.text for c in chunks)):
        if "판단" in cells and "할 일" in cells:
            head = cells
            continue
        if head and len(cells) == len(head) and re.search(rf"알람 {re.escape(code)}\b", cells[0]):
            name = re.sub(r",\s*DOC-04[^)]*", "", cells[0]).strip()
            judge = _clean(cells[head.index("판단")])
            todo = cells[head.index("할 일")].replace("VF2-0x", equipment_id)
            return {"kind": "short", "line": f"{name} — {judge}", "detail": _clean(todo),
                    "source": "출처: DOC-05 안전 작업 기준서 Rev.2 §2.4", "cite": _ref("2.4"), "fixed": True}
    return None


def not_applicable(kind: str) -> dict:
    if kind == "GUIDE":
        return {"kind": "none", "line": "이 알람은 안전 작업 기준서 적용 대상이 아닙니다 (DOC-05 §1)",
                "cite": _ref("1"), "fixed": True}
    return {"kind": "none", "line": "§2 해당 없음 — 짧은 작업 판단 표에 없는 주의 알람입니다 (DOC-05 §2.4)",
            "cite": _ref("2.4"), "fixed": True}
