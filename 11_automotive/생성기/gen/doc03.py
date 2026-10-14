"""DOC-03 고장 대응 매뉴얼에서 작업 순서·원인·조치를 읽는다 (작업지시서·작업기록서 재료).

DOC-03은 팀이 쓴 사내 문서다 (원문 아님). 원문 출처 칸은 옮기지 않는다 (R-85).
"""
from __future__ import annotations

import io
import re

from .common import PROJECT

_TAG = re.compile(r"\s*\[(실제|가상|참고)[^\]]*\]")


def _clean(t: str) -> str:
    t = _TAG.sub("", t).replace("**", "").strip()
    return re.sub(r"\s+", " ", t)


def load_doc03() -> dict[str, dict]:
    """절 번호(예: '2.1') → {title, causes[], steps[(no, who, text)], action, symptom}."""
    text = io.open(PROJECT / "가상사내문서" / "DOC-03_고장대응매뉴얼.md", encoding="utf-8").read()
    out: dict[str, dict] = {}
    for m in re.finditer(r"\n### ((?:2|3)\.\d+) ([^\n]*)\n(.*?)(?=\n### |\n## )", text, re.S):
        sec, title, body = m.group(1), m.group(2), m.group(3)
        d = {"title": _clean(title), "causes": [], "steps": [], "action": "", "symptom": ""}
        rows = [ln for ln in body.split("\n") if ln.startswith("|")]
        mode = None
        for ln in rows:
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if c[0] in ("가능한 원인", "원인"):
                mode = "cause"; continue
            if c[0] == "#":
                mode = "step"; continue
            if c[0] in ("칸", "대상") or set(c[0]) <= {"-"}:
                if c[0] in ("칸", "대상"):
                    mode = "kv" if c[0] == "칸" else None
                continue
            if mode == "cause" and len(c) >= 2:
                d["causes"].append(_clean(c[0]))
            elif mode == "step" and len(c) >= 3 and re.match(r"^★?\d+$", c[0]):
                d["steps"].append((c[0], _clean(c[1]), _clean(c[2])))
            elif mode == "kv" and len(c) >= 2:
                if c[0] in ("증상·알람", "증상"):
                    d["symptom"] = _clean(c[1])
                elif c[0] == "조치":
                    d["action"] = _clean(c[1])
                elif c[0] in ("원인", "가능한 원인"):
                    d["causes"] += [_clean(x) for x in re.split(r"[,·] | / ", c[1]) if x.strip()]
                elif c[0] in ("점검", "점검 순서"):
                    for i, x in enumerate(re.split(r" → |\d\) ", c[1]), 1):
                        if x.strip():
                            d["steps"].append((str(i), "", _clean(x)))
        am = re.search(r"\*\*조치:\*\*([^\n]*)", body)
        if am and not d["action"]:
            d["action"] = _clean(am.group(1))
        out[sec] = d
    return out
