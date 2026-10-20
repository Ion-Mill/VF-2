"""줄 목록 칸 2판 (BLOCKS_V2, 8차 2026-10-12 — research_notes/로컬 LLM 연결/앞단개선8_계획_20261012.md 1절, 7차 노트 5.11절) [제안].

화면 표시 전용이다. conclusion 글자(채점 대상)는 바꾸지 않는다 — 채점·스냅숏은 이 칸을 보지 않는다.
7차 줄 목록 칸(answer.answer_blocks)은 문서 줄만 나눴고 운영 답·표 칸·줄마다 출처는 글자 하나로 버렸다. 공통 근본 원인은
"구조를 아는 서버가 구조를 버리고 글자로 이은 뒤, 화면이 그 글자를 다시 나누려 한 것"이다. 이 판은 서버가 구조를 그대로 보낸다:
- 운영 답: 머리 + 항목 목록 {kind: "ops", head, items, source} — 화면은 번호 목록(1. 2. 3.)으로 그린다.
  항목은 프로그램 초안 조각 그대로라 숫자가 초안과 같아야 쓴다(다듬은 conclusion은 이미 초안과 숫자 양방향 검사를 지났다).
- 문서 표 줄: "머리 — 칸: 값 · 칸: 값"이면 {head, cells[{name, value}]} — 화면이 칸마다 줄을 바꾼다 (글자로 자르지 않는다).
- 줄마다 출처: {cite: {doc_id, section, …}} — 규칙 2.1 "답변 전체 끝에 출처 하나로 뭉뚱그리지 않는다".
API 명세에 없는 칸 모양이다 → 기획문서_대조_API_테스트계획_20261011.md에 [제안]으로 적는다.
"""
from __future__ import annotations

import re
from collections import Counter

from backend.services import followup_v2 as FU2

NUM = re.compile(r"\d+(?:\.\d+)?")


def numbers(text: str) -> Counter:
    return Counter(NUM.findall(text or ""))


def doc_line(text: str, cite: dict | None) -> dict:
    """문서 줄 하나. 표 줄이면 머리·칸을 함께 담는다 (글자 text는 그대로)."""
    b = {"kind": "line", "text": text, "safety": FU2.is_safety(text)}
    head, cells = FU2.split_line(text)
    if head is not None:
        b["head"] = head
        b["cells"] = [{"name": n, "value": v} for n, v in (c.split(": ", 1) for c in cells)]
    if cite:
        b["cite"] = cite
    return b


def ops_blocks(entries: list[dict], ops_texts: list[str], ops_final: str) -> list[dict]:
    """운영 답 칸. 항목·머리의 숫자 묶음이 운영 초안(ops_texts)과 같을 때만 항목 목록으로, 아니면 다듬은 글 한 칸 (어긋난 숫자를 보이지 않게)."""
    if not entries:
        return [{"kind": "text", "text": ops_final}]
    shown = []
    out = []
    for e in entries:
        if e["items"]:
            out.append({"kind": "ops", "head": e["head"], "items": list(e["items"]), "source": e.get("source")})
            shown += [e["head"]] + list(e["items"])
            if e.get("notes"):   # 9차 BLOCKS_V3 (F): 정지 답의 "교대 보고서 기준" 줄은 작은 제목 + 따로 목록
                out[-1].update(notes_head=e["notes_head"], notes=list(e["notes"]))
                shown += [e["notes_head"]] + list(e["notes"])
        elif e["text"]:
            out.append({"kind": "text", "text": e["text"]})
            shown.append(e["text"])
    if not out or numbers(" ".join(shown)) != numbers(" ".join(ops_texts)):
        return [{"kind": "text", "text": ops_final}]
    return out


def build(parts: list[str], ops_final: str | None, ops_texts: list[str], entries: list[dict], doc_lines: list[str],
          doc_cites: list[dict], conclusion: str, tail: list[str] | None = None,
          v3: bool = False, card: str | None = None, steps: bool = False, written: str | None = None,
          causes: list[str] | None = None, cause_head: str = "", cause_cite: dict | None = None) -> list[dict]:
    """줄 목록 칸 2판. 다시 이은 글(parts + 운영 글 + 꼬리)이 conclusion과 다르면 통째 한 칸 (7차와 같은 안전장치).
    v3 (9차 BLOCKS_V3): 덩어리(알람 카드·문서 줄·운영 기록)마다 제목 칸을 두고, 알람 답은 점검 순서 자리(steps)를 카드 바로 뒤에 둔다.
    written (10차 DOC_WRITE): AI가 새로 쓴 답 — 앞머리 칸 {kind: lead, written: true}로 두고, 원문 줄에는 orig: true를 붙인다(화면이 접음).
    causes (2026-10-19): 원인을 물은 알람 답의 "가능한 원인" 줄(DOC-03 원인 표 원문). 조립 글(parts)에 cause_head + " / ".join(causes) 한 덩어리로 들어 있고,
    v3면 알람 설명 → **가능한 원인** → 점검 순서 순서로 제목 칸을 둔다. 줄마다 출처(cause_cite)."""
    tail = list(tail or [])
    rebuilt = " ".join(parts + ([ops_final] if ops_final else []) + tail)
    if rebuilt != conclusion:
        return [{"kind": "text", "text": conclusion}]
    joined = " / ".join(doc_lines)
    cites = doc_cites if len(doc_cites) == len(doc_lines) else [None] * len(doc_lines)
    out: list[dict] = []
    for p in parts:
        if causes and p == cause_head + " / ".join(causes):
            out += [{**doc_line(x, cause_cite), "grp": "cause"} for x in causes]
            continue
        if doc_lines and p.endswith(joined):
            head = p[: len(p) - len(joined)].strip()
            orig = bool(written and head.startswith(written))
            if orig:
                out.append({"kind": "lead", "text": written, "written": True, "grp": "doc"})
            elif head:
                out.append({"kind": "lead", "text": head, "grp": "doc"})
            out += [{**doc_line(x, c), **({"orig": True} if orig else {}), "grp": "doc"} for x, c in zip(doc_lines, cites)]
        else:
            out.append({"kind": "text", "text": p, "grp": "card" if (card and p == card) else "note"})
    if ops_final:
        out += [{**b, "grp": "ops"} for b in ops_blocks(entries, ops_texts, ops_final)]
    out += [{"kind": "text", "text": t, "grp": "note"} for t in tail]
    if v3:
        return sections_v3(out, steps)
    return [{k: v for k, v in b.items() if k != "grp"} for b in out]


# 9차 (1부 원인 C): 덩어리 제목. 알람 답은 지침카드 순서(규칙 4.1 — 알람 설명 → 점검 순서 → … → 운영 기록)를 따른다. 제목에 숫자를 넣지 않는다
SECTION_V3 = {"card": "알람 설명", "steps": "점검 순서 (사내 문서)", "doc_after_card": "문서에서 더 찾은 줄", "doc": "사내 문서",
              "ops": "운영 기록 [가상]", "cause": "가능한 원인 (사내 문서)"}


def sections_v3(blocks: list[dict], steps: bool) -> list[dict]:
    """덩어리가 둘 이상(점검 순서 포함)이면 제목 칸 {kind: "section", text}을 둔다. 점검 순서는 자리표 {kind: "steps"} —
    화면이 그 자리에 점검 순서 목록을 그린다. 덩어리가 하나뿐이면 제목을 두지 않는다 (글자·순서는 그대로)."""
    groups = [g for g in ("card", "cause", "doc", "ops") if any(b["grp"] == g for b in blocks)]
    clean = lambda bs: [{k: v for k, v in b.items() if k != "grp"} for b in bs]   # noqa: E731
    if len(groups) + (1 if steps else 0) < 2:
        return clean(blocks)
    out: list[dict] = []
    for g in ("card", "cause", "steps", "doc", "ops"):
        if g == "steps":
            if steps:
                out += [{"kind": "section", "text": SECTION_V3["steps"]}, {"kind": "steps"}]
            continue
        bs = [b for b in blocks if b["grp"] == g]
        if bs:
            title = SECTION_V3["doc_after_card" if (g == "doc" and "card" in groups) else g]
            out += [{"kind": "section", "text": title}] + clean(bs)
    return out + clean([b for b in blocks if b["grp"] == "note"])
