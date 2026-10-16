"""숫자를 값으로 비교하는 검사관 (2026-10-10 계획 2단계, 스위치 NUM_MATCH=value).

업계 방식(숫자는 값으로 정확히 비교, 허용 오차 없음, 단위 묶음은 바뀌면 안 됨)을 따른다
(research_notes/로컬 LLM 연결/개선안_업계표준_조사_20261010.md 2절). 낱말 비교(token)가 막던 맞는 답
("목표 90" → "90개", "단위: ℃ · 정상 범위: 28~42" → "42℃")은 통과시키고, 뜻이 바뀌는 것은 막는다.

- 값: 65.60 = 65.6, 1,335 = 1335, 7.0% = 7%
- 세는 말 묶음 {개} {건} {명} {대} {줄} {가지} {단계} {번·회·차례} …: 빼거나, 원문 맨숫자에 붙이는 것은 된다.
  다른 묶음으로 바뀌면 안 된다 (8번 → 8개 거부).
- 물리 단위(% ℃ mm psi bar MPa kW A V L 분 시간 일 주 개월 년 …): 원문에 붙어 있으면 그대로 있어야 한다
  (7.0분 → 7.0 거부, 42℃ → 42% 거부). 원문 맨숫자에 붙이는 것은 그 숫자가 있는 줄에 같은 단위가 있을 때만 된다.
- 범위 28~42 ℃: 양 끝으로 나누고 뒤 단위를 앞 끝에도 준다.
- 날짜·시각·기록 번호·모델명은 통째로 본다(2026-09-30 안의 30을 따로 세지 않음, VF-2의 2를 숫자로 세지 않음).
  같은 날의 다른 표기(2026-09-30 = 9월 30일 = 9/30)와 같은 시각의 다른 표기(06:00 = 6시, 17:00 = 오후 5시)는 같게 본다.
- 읽지 못한 꼴은 통과시키지 않는다(거부되면 기본 문장을 쓰므로 안전한 쪽으로 틀린다).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# 세는 말 → 묶음 이름 (같은 묶음 안에서는 바꿔 써도 된다)
COUNTERS = {"번": "번", "회": "번", "차례": "번", "개": "개", "건": "건", "명": "명", "대": "대", "줄": "줄",
            "가지": "가지", "단계": "단계", "통": "통", "장": "장", "칸": "칸", "종": "종", "곳": "곳", "바퀴": "바퀴", "쪽": "쪽"}
# 물리 단위 → 표준 이름 (같은 뜻의 다른 표기를 묶는다)
PHYSICAL = {"%": "%", "퍼센트": "%", "℃": "℃", "°C": "℃", "도": "℃",
            "mm": "mm", "cm": "cm", "µm": "µm", "um": "µm", "m": "m",
            "psi": "psi", "bar": "bar", "MPa": "MPa", "kPa": "kPa", "kW": "kW", "W": "W", "A": "A", "V": "V", "VAC": "VAC",
            "L": "L", "mL": "mL", "ml": "mL", "cc": "cc", "oz": "oz", "gal": "gal", "rpm": "rpm", "RPM": "rpm",
            "dBA": "dBA", "dB": "dB", "kg": "kg", "g": "g", "Hz": "Hz",
            "초": "초", "분": "분", "min": "분", "시간": "시간", "일": "일", "주": "주", "주일": "주",
            "개월": "개월", "달": "개월", "년": "년"}
ALIASES: dict[str, list[str]] = {}
for _k, _v in PHYSICAL.items():
    ALIASES.setdefault(_v, []).append(_k)

_HANGUL = re.compile(r"[가-힣]")
_KO_UNITS = sorted((u for u in list(COUNTERS) + list(PHYSICAL) if _HANGUL.search(u)), key=len, reverse=True)
_SYM_UNITS = sorted((u for u in PHYSICAL if not _HANGUL.search(u)), key=len, reverse=True)

# 우선순위 순서: 앞의 꼴이 차지한 글자는 뒤의 꼴이 다시 읽지 않는다
CODE = re.compile(r"(?<![A-Za-z0-9_.])(?:"
                  r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+"   # VF2-01, OP-30, MR-2609-007, LOT-2609-001-1, VF-2, DOC-03
                  r"|[A-Za-z]+\d[A-Za-z0-9]*"                 # M6, H7, SC538, F01, Q500, G54
                  r"|\d+[A-Za-z]+(?:-[A-Za-z0-9]+)+"          # 0W-20
                  r")(?![A-Za-z0-9])")
DATE_FULL = re.compile(r"(?<![\d.])(\d{4})\s*(?:[-./]|년\s*)(\d{1,2})\s*(?:[-./]|월\s*)(\d{1,2})(?:\s*일)?(?![\d.])")
DATE_MD_KO = re.compile(r"(?<![\d.])(\d{1,2})\s*월\s*(\d{1,2})\s*일")
DATE_MD_DASH = re.compile(r"(?<![\d\-.])(0[1-9]|1[0-2])-(\d{2})(?![\d\-.])")
TIME_COLON = re.compile(r"(?<![\d:])([01]?\d|2[0-4]):([0-5]\d)(?![\d:])")
TIME_KO = re.compile(r"(?:(오전|오후|저녁|밤|새벽|아침)\s*)?(?<![\d.])(\d{1,2})\s*시(?!간)(?:\s*(\d{1,2})\s*분)?")
SLASH = re.compile(r"(?<![\d/.])(\d{1,2})/(\d{1,2})(?![\d/.])")  # 9/30(날짜) 또는 1/2(분수) → 통째로
NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
                 r"(?:(" + "|".join(map(re.escape, _KO_UNITS)) + r")"
                 r"|[  ]?(" + "|".join(map(re.escape, _SYM_UNITS)) + r")(?![A-Za-z0-9]))?")
RANGE_SEP = re.compile(r"^\s*[~〜～–]\s*$")


@dataclass(frozen=True)
class Q:
    kind: str            # num | date | time | slash | code
    value: object        # num: 정규화한 값 글 / date: (년|None, 월, 일) / time: (시, 분) / slash: (a, b) / code: 대문자 글
    ukind: str | None    # num만: "count"(세는 말) | "phys"(물리 단위) | None(맨숫자)
    unit: str | None     # count = 묶음 이름, phys = 표준 단위 이름
    text: str            # 원래 글 (거부 사유 보고용)
    start: int


def _num(s: str) -> str | None:
    try:
        return format(Decimal(s.replace(",", "")).normalize(), "f")
    except InvalidOperation:
        return None


def quantities(text: str) -> list[Q]:
    """글에서 숫자·날짜·시각·번호를 차례대로 뽑는다."""
    text = text or ""
    taken: list[tuple[int, int]] = []
    out: list[Q] = []

    def free(m) -> bool:
        a, b = m.span()
        return all(b <= x or a >= y for x, y in taken)

    def add(m, q: Q) -> None:
        taken.append(m.span())
        out.append(q)

    for m in CODE.finditer(text):
        if free(m):
            add(m, Q("code", m.group(0).upper(), None, None, m.group(0), m.start()))
    for rx in (DATE_FULL,):
        for m in rx.finditer(text):
            mo, d = int(m.group(2)), int(m.group(3))
            if free(m) and 1 <= mo <= 12 and 1 <= d <= 31:
                add(m, Q("date", (int(m.group(1)), mo, d), None, None, m.group(0), m.start()))
    for rx in (DATE_MD_KO, DATE_MD_DASH):
        for m in rx.finditer(text):
            mo, d = int(m.group(1)), int(m.group(2))
            if free(m) and 1 <= mo <= 12 and 1 <= d <= 31:
                add(m, Q("date", (None, mo, d), None, None, m.group(0), m.start()))
    for m in TIME_COLON.finditer(text):
        if free(m):
            add(m, Q("time", (int(m.group(1)) % 24, int(m.group(2))), None, None, m.group(0), m.start()))
    for m in TIME_KO.finditer(text):
        h = int(m.group(2))
        if free(m) and h <= 24:
            if m.group(1) in ("오후", "저녁", "밤") and h < 12:
                h += 12
            add(m, Q("time", (h % 24, int(m.group(3) or 0)), None, None, m.group(0), m.start()))
    for m in SLASH.finditer(text):
        if free(m):
            add(m, Q("slash", (int(m.group(1)), int(m.group(2))), None, None, m.group(0), m.start()))
    for m in NUM.finditer(text):
        if not free(m):
            continue
        v = _num(m.group(1) + (m.group(2) or ""))
        if v is None:
            continue
        u = m.group(3) or m.group(4)
        if u in COUNTERS:
            add(m, Q("num", v, "count", COUNTERS[u], m.group(0), m.start()))
        elif u in PHYSICAL:
            add(m, Q("num", v, "phys", PHYSICAL[u], m.group(0), m.start()))
        else:
            add(m, Q("num", v, None, None, m.group(0), m.start()))
    out.sort(key=lambda q: q.start)
    # 범위 "28~42 ℃": 단위가 없는 앞 끝에 뒤 끝의 단위를 준다
    for i in range(len(out) - 1):
        a, b = out[i], out[i + 1]
        if a.kind == b.kind == "num" and a.ukind is None and b.ukind and RANGE_SEP.match(text[a.start + len(a.text):b.start]):
            out[i] = Q("num", a.value, b.ukind, b.unit, a.text, a.start)
    return out


def _line_of(text: str, pos: int) -> str:
    a = text.rfind("\n", 0, pos) + 1
    b = text.find("\n", pos)
    return text[a:] if b < 0 else text[a:b]


def match(t: Q, d: Q, d_line: str) -> bool:
    """t(새 글의 값)가 d(원문의 값)와 같은 뜻인가. d_line = d가 있는 원문 줄 (단위를 붙여도 되는지 볼 때 씀)."""
    if t.kind != d.kind:
        if {t.kind, d.kind} == {"date", "slash"}:  # 2026-09-30 = 9/30
            date, sl = (t, d) if t.kind == "date" else (d, t)
            return date.value[1:] == sl.value
        return False
    if t.kind == "date":
        (ty, tm, td), (dy, dm, dd) = t.value, d.value
        return (tm, td) == (dm, dd) and (ty is None or dy is None or ty == dy)
    if t.kind != "num":
        return t.value == d.value
    if t.value != d.value:
        return False
    if (t.ukind, t.unit) == (d.ukind, d.unit):
        return True
    if d.ukind == "count":                 # 세는 말은 빼도 되지만 다른 묶음으로 바꾸면 안 된다
        return t.ukind is None
    if d.ukind is None:                    # 원문 맨숫자
        if t.ukind == "count":
            return True
        if t.ukind == "phys":              # 같은 줄에 그 단위가 있어야 붙일 수 있다
            return any(alias in d_line for alias in ALIASES.get(t.unit, [t.unit]))
    return False                           # 원문에 붙은 물리 단위를 빼거나 바꿈


def _uniq(xs: list[str]) -> list[str]:
    seen: list[str] = []
    for x in xs:
        if x not in seen:
            seen.append(x)
    return seen


_SPACED_KO = re.compile(r"(\d+(?:\.\d+)?) +(" + "|".join(map(re.escape, _KO_UNITS)) + ")")


def tidy(text: str, source: str) -> str:
    """LLM이 숫자와 한글 단위 사이에 넣은 띄어쓰기("1 년", "2 단계")를 원문이 붙여 쓴 경우에만 붙인다. 내용은 바꾸지 않는다.
    (adapter.tidy와 같은 일을 이 파일의 단위 목록 전체로 한다 — 2026-10-10 F11 "1 년" 거부)"""
    return _SPACED_KO.sub(lambda m: m.group(1) + m.group(2) if m.group(1) + m.group(2) in source else m.group(0), text or "")


def _same_form(t: Q, d: Q) -> bool:
    return re.sub(r"\s+", "", t.text) == re.sub(r"\s+", "", d.text)


def two_way(text: str, draft: str, same_form: bool = False) -> tuple[list[str], list[str]]:
    """(원문에 있는데 새 글에 없는 것, 새 글에 있는데 원문에 없는 것).
    same_form=True면 날짜·시각은 원문 표기 그대로여야 한다 — 문장 다듬기(phrase)용: 지시문이 "날짜를 바꾸지 않는다"이고,
    날짜를 바꿔 쓰면 문장 짜임이 함께 바뀌어 값과 설비가 떨어지기 쉽다 (2026-10-10 C16)."""
    got, want = quantities(text), quantities(draft)
    lines = {id(d): _line_of(draft, d.start) for d in want}

    def ok(t: Q, d: Q) -> bool:
        if same_form and (t.kind in ("date", "time", "slash") or d.kind in ("date", "time", "slash")):
            return _same_form(t, d)
        return match(t, d, lines[id(d)])

    missing = [d.text for d in want if not any(ok(t, d) for t in got)]
    new = [t.text for t in got if not any(ok(t, d) for d in want)]
    return _uniq(missing), _uniq(new)


def lead_unsupported(lead: str, lines: list[str]) -> list[str]:
    """앞머리(lead)의 값 중 고른 줄 어디에도 근거가 없는 것."""
    per = [(ln, quantities(ln)) for ln in lines]
    return _uniq([q.text for q in quantities(lead)
                  if not any(match(q, d, ln) for ln, ds in per for d in ds)])
