"""이어 묻기 2판 (FOLLOWUP_V2, 7차 2026-10-12 — research_notes/로컬 LLM 연결/앞단개선7_계획_20261012.md 2.2절) [제안].

6차 이어 묻기는 알아보기는 했지만 LLM이 실제로 바꾼 글이 0이었다(E6 바꿔 쓴 비율 0%, 2026-10-12 사용자 화면 4묶음). 까닭은 프로그램 설계다:
줄 끝 칸 "잠금·표지: ○" 하나 때문에 줄 전체를 막았고(안전 낱말을 줄 단위로 봄), 숫자를 하나도 빼면 안 되는 검사라 "짧게"가 구조상 불가능했다.
이 판은 업계 방법을 쓴다:
- 칸 단위 안전 판정: 표 줄("머리 — 칸: 값 · 칸: 값")을 칸으로 나눠 안전 낱말 칸만 원문 그대로 둔다 (구조화 블록을 코드가 조립).
- 자리표(delexicalization): 숫자·번호·영문 이름을 {{n}}으로 바꿔 LLM에 보내고, 프로그램이 되채운다 — LLM은 숫자를 볼 수도 바꿀 수도 없다.
- "짧게"는 고르기: LLM은 남길 조각 번호만 고르고, 프로그램이 원문 조각을 그대로 옮기며 "줄임"을 밝힌다. 앞 답에 LLM 앞머리(이미 검사를
  통과해 화면에 보인 한 문장 요약)가 있으면 그것을 쓴다.
- "쉽게"에 낱말 풀이: 답에 나온 용어집 표준어 가운데 LLM이 고른 것(3개 이하)의 영어 이름·다른 말을 프로그램이 용어집에서 붙인다.
알람·점검 순서·절차·DOC-03·DOC-05 답은 지금처럼 바꿔 쓰지 않는다(규칙 2.5 — answer._rewrite_blocked).
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import replace
from functools import lru_cache

from backend.config import settings
from backend.llm import prompts, schemas
from backend.llm.adapter import DENY, KO_NUM, MARKERS
from backend.llm.client import LlmBadOutput, LlmUnavailable, chat_json
from backend.rag.chunker import load_corpus
from backend.rag.sanitize import FORBIDDEN

PH = re.compile(r"\{\{(\d+)\}\}")
# 숫자·번호·영문 이름 (띄어 쓴 영숫자 묶음은 하나로: "Mobil Grease XHP 222", "NLGI 2", "VF2-01", "2026-09-30")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-/%℃°:+~]*(?:\s+[A-Za-z0-9][A-Za-z0-9.\-/%℃°:+~]*)*")
STRICT_WORDS = ("이상", "이하", "초과", "미만", "금지", "않", "못", "불가", "반드시", "필수", "먼저", "전에", "뒤에")
SAFETY_WORDS = ("잠금", "표지", "고전압", "전기", "저항", "차단", "LOTO", "케이블", "앰프")   # answer.SAFETY_WORDS와 같다
CELL_SEP = " · "


def delex(text: str) -> tuple[str, list[str]]:
    """숫자·번호·영문 이름을 {{1}}, {{2}} …로 바꾼 글과 값 목록."""
    vals: list[str] = []

    def rep(m):
        vals.append(m.group(0))
        return "{{%d}}" % len(vals)
    return TOKEN.sub(rep, text), vals


def relex(text: str, vals: list[str]) -> tuple[str | None, str | None]:
    """자리표를 값으로 되채운다. 자리표가 빠지거나 겹치거나 새로 생기면, 자리표 밖에 숫자·영문이 있으면 거부."""
    got = [int(i) for i in PH.findall(text)]
    want = list(range(1, len(vals) + 1))
    if sorted(got) != want:
        missing = sorted(set(want) - set(got))
        return None, ("빠진 자리표: " + ", ".join(map(str, missing[:5]))) if missing else "겹치거나 새 자리표"
    if re.search(r"[A-Za-z0-9]", PH.sub("", text)):
        return None, "자리표 밖의 숫자·영문"
    return PH.sub(lambda m: vals[int(m.group(1)) - 1], text), None


def check_unit(new: str, src: str) -> str | None:
    """되채운 글 한 조각 검사 (원문 조각과 견줌). 숫자·영문 이름은 자리표가 지킨다. 통과면 None."""
    if not new.strip():
        return "빈 글"
    if FORBIDDEN.search(new):
        return "원문 출처 표기"
    if KO_NUM.search(new) and not KO_NUM.search(src):
        return "한글 수사"
    if (c := numlike_new_v14(new, src)):   # 10차 보강 (2026-10-14): 원문에 없던 ①·１·Ⅰ·² 같은 숫자 모양
        return f"숫자 모양 글자: {c}"
    if DENY.search(new) and not DENY.search(src):
        return "허락·지시 문구"
    if new.count("§") != src.count("§"):
        return "출처 표기"
    lost = [m for m in MARKERS if src.count(m) > new.count(m)]
    if lost:
        return "빠진 꼬리표: " + ", ".join(lost)
    lost = [w for w in STRICT_WORDS if new.count(w) < src.count(w)]
    if lost:
        return "빠진 조건 말: " + ", ".join(lost)
    if len(new) > max(80, int(len(src) * 1.6) + 40):
        return "너무 김"
    if term_v13_on() and (w := avoid_new_v13(new, src, "")):   # 10차 보강 TERM_V13: 이어 묻기 다시 쓴 칸에도 같은 검사
        return f"쓰지 않는 말: {w}"
    return None


def split_line(line: str) -> tuple[str | None, list[str]]:
    """표 줄("머리 — 칸: 값 · 칸: 값", answer.plain_lines 꼴)이면 (머리, 칸 목록), 아니면 (None, [줄])."""
    if " — " in line:
        head, rest = line.split(" — ", 1)
        cells = rest.split(CELL_SEP)
        if len(cells) >= 2 and all(": " in c for c in cells):
            return head, cells
    return None, [line]


def join_line(head: str | None, cells: list[str]) -> str:
    return (head + " — " + CELL_SEP.join(cells)) if head is not None else cells[0]


def is_safety(text: str) -> bool:
    return any(w in text for w in SAFETY_WORDS)


def units_of(segs: list[str]) -> list[dict]:
    """다시 쓰기 단위: 표 줄은 칸마다(칸 이름은 그대로 두고 값만), 다른 줄은 줄 통째. fixed = 안전 낱말이 든 단위(원문 그대로)."""
    out = []
    for si, seg in enumerate(segs):
        head, cells = split_line(seg)
        if head is None:
            out.append({"seg": si, "cell": None, "name": None, "text": seg, "fixed": is_safety(seg)})
            continue
        for ci, cell in enumerate(cells):
            name, val = cell.split(": ", 1)
            out.append({"seg": si, "cell": ci, "name": name, "text": val, "fixed": is_safety(cell)})
    return out


def assemble(segs: list[str], units: list[dict], texts: list[str]) -> list[str]:
    """단위별 새 글(texts, units와 같은 순서)로 조각을 다시 맞춘다. 칸 순서·칸 이름·머리는 원문 그대로."""
    out = []
    for si, seg in enumerate(segs):
        head, cells = split_line(seg)
        mine = [(u, t) for u, t in zip(units, texts) if u["seg"] == si]
        if head is None:
            out.append(mine[0][1] if mine else seg)
        else:
            out.append(join_line(head, [f"{u['name']}: {t}" for u, t in mine]))
    return out


# ---------------------------------------------------------------- 낱말 풀이 (용어집 — 영어 | 표준어 | 쓰지 않는 말 | 근거)
@lru_cache(maxsize=1)
def glossary_rows() -> tuple[dict, ...]:
    """용어집 표 줄. 보이는 칸(영어·표준어·다른 말)에 숫자가 있는 줄은 뺀다 — 앞 답에 없던 숫자를 만들지 않게."""
    out = []
    for c in load_corpus():
        if c.doc_id != "GLOSSARY":
            continue
        header = None
        for line in c.text.splitlines():
            s = line.strip()
            if not s.startswith("|"):
                header = None
                continue
            cells = [x.strip().replace("**", "") for x in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if header is None:
                header = cells
                continue
            if header[:3] != ["영어", "표준어", "쓰지 않는 말"] or len(cells) < 3:
                continue
            eng, std, avoid = cells[0], cells[1], cells[2]
            if re.search(r"\d", eng + std + avoid) or not std:
                continue
            terms = [t.strip() for t in re.split(r"[/(),·]", std) if len(t.strip()) >= 2 and re.search(r"[가-힣]", t)]
            out.append({"section": c.section, "eng": eng, "std": std, "avoid": "" if avoid in ("—", "-", "") else avoid,
                        "terms": terms, "cite": c.cite, "chunk": c})
    return tuple(out)


def term_candidates(text: str, limit: int = 8) -> list[dict]:
    """답 글에 나오는 용어집 표준어 (긴 낱말 먼저, 같은 줄은 한 번)."""
    found = []
    for r in glossary_rows():
        hit = max((t for t in r["terms"] if t in text), key=len, default=None)
        if hit:
            found.append((len(hit), hit, r))
    found.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for _, hit, r in found:
        if hit in seen or any(hit in s for s in seen):
            continue
        seen.add(hit)
        out.append({**r, "hit": hit})
        if len(out) >= limit:
            break
    return out


def term_note(r: dict, v9: bool = False) -> str:
    """낱말 풀이 한 줄. v9(8차 PARSE_V9): 여러 낱말이 " / "로 묶인 줄(예: "Availability / Performance / Quality rate | 가동률 / 성능 / 양품률")은
    맞은 낱말 자리의 영어 이름만 보인다 — 묶음 전체를 붙이면 "가동률 = 영어 Availability / Performance / Quality rate"처럼 지저분했다
    (7차 노트 5.3a FU09). 괄호가 있거나 나눈 개수가 다르면 자리를 맞출 수 없어 지금처럼 통째로. 묶인 줄의 "다른 말"은 자리가 맞을 때만."""
    eng, avoid = r["eng"], r["avoid"]
    if v9 and " / " in r["std"] and not re.search(r"[()]", r["eng"] + r["std"]):
        ko, en = [x.strip() for x in r["std"].split(" / ")], [x.strip() for x in r["eng"].split(" / ")]
        idx = next((i for i, x in enumerate(ko) if r["hit"] in x), None)
        if len(ko) == len(en) and idx is not None:
            eng = en[idx]
            av = [x.strip() for x in avoid.split(" / ")] if avoid else []
            avoid = av[idx] if len(av) == len(ko) and av[idx] not in ("—", "-") else ""
    note = f"{r['hit']} = 영어 {eng}"
    if avoid:
        note += f", 다른 말 {avoid}"
    return note


# ---------------------------------------------------------------- LLM 작업 (정해진 칸, 실패하면 원문 그대로 — fail closed)
def _trace(job: str) -> dict:
    return {"job": job, "used": False, "reason": None, "tries": 0, "ms": 0}


def rewrite_units(srcs: list[str], terms: list[str]) -> tuple[list[str] | None, list[int], dict]:
    """조각마다 자리표를 씌워 쉽게 다시 쓴다. 돌려주는 값 = (조각마다 새 글 — 검사를 못 지난 조각은 원문, 고른 낱말 번호(0부터), trace).
    LLM 오류·형식 오류면 (None, [], trace). 다시 요청은 1번(사유를 붙여)."""
    tr, t0, s = _trace("simplify"), time.monotonic(), settings()
    dl = [delex(x) for x in srcs]
    sent = [d[0] for d in dl]
    term_ids = [f"T{i + 1}" for i in range(len(terms))]
    feedback = None
    for _ in range(2):
        tr["tries"] += 1
        try:
            out = chat_json(prompts.simplify_v2(sent, terms, feedback),
                            schemas.simplify_v2(len(sent), max(len(x) for x in sent), term_ids), "simplify",
                            min(2048, sum(len(x) for x in sent) * 2 + 200))
        except (LlmUnavailable, LlmBadOutput) as e:
            tr["reason"] = f"LLM 오류: {e}"
            break
        texts = out.get("texts") if isinstance(out, dict) and set(out) == {"texts", "terms"} else None
        picks = out.get("terms") if isinstance(out, dict) else None
        if not isinstance(texts, list) or len(texts) != len(sent) or not all(isinstance(t, str) and t.strip() for t in texts) \
                or not isinstance(picks, list) or not set(picks) <= set(term_ids):
            tr["reason"], feedback = "형식 오류", "형식 오류: 조각 수만큼 글을 쓰고, terms에는 낱말 후보 번호만 넣는다"
            continue
        result, reasons = [], []
        for (t, (_, vals)), src in zip(zip(texts, dl), srcs):
            new, why = relex(t.strip(), vals)
            why = why or check_unit(new, src)
            if why:
                reasons.append(why)
                result.append(src)   # 이 조각은 원문 그대로 (fail closed)
            else:
                result.append(new)
        changed = sum(1 for a, b in zip(result, srcs) if a != b)
        picked = sorted({term_ids.index(p) for p in picks})[:3]
        if changed or picked or not reasons:
            tr.update(used=True, reason=("일부 조각 원문: " + reasons[0]) if reasons else None,
                      ms=int((time.monotonic() - t0) * 1000), changed=changed, terms=len(picked))
            return result, picked, tr
        tr["reason"], feedback = reasons[0], reasons[0]
        if time.monotonic() - t0 > s.budget_s - 5:
            break
    tr["ms"] = int((time.monotonic() - t0) * 1000)
    return None, [], tr


def pick_short(units: list[str]) -> tuple[list[int] | None, dict]:
    """"짧게": 남길 조각 번호(0부터, 문서 순서). 실패하면 None."""
    tr, t0 = _trace("pick"), time.monotonic()
    tr["tries"] = 1
    ids = [f"U{i + 1}" for i in range(len(units))]
    try:
        out = chat_json(prompts.pick_units(units), schemas.pick_units(ids), "pick", 120)
    except (LlmUnavailable, LlmBadOutput) as e:
        tr.update(reason=f"LLM 오류: {e}", ms=int((time.monotonic() - t0) * 1000))
        return None, tr
    keep = out.get("keep") if isinstance(out, dict) and set(out) == {"keep"} else None
    if not isinstance(keep, list) or not keep or not set(keep) <= set(ids) or len(set(keep)) >= len(ids):
        tr.update(reason="형식 오류", ms=int((time.monotonic() - t0) * 1000))
        return None, tr
    tr.update(used=True, ms=int((time.monotonic() - t0) * 1000))
    return sorted({ids.index(k) for k in keep}), tr


# ---------------------------------------------------------------- 10차 DOC_WRITE (2026-10-13 사용자 결정)
# 문서 답을 찾은 줄로 새로 쓴다(해요체 1~3문장). 숫자·번호·영문 이름은 자리표로 가려 LLM이 새로 만들 수 없게 하고,
# 쓴 글은 코드 검사 + 따로 판정(answer_faith)을 모두 지나야 쓴다. 하나라도 못 지나면 부른 쪽이 지금처럼 원문 줄을 보인다.
JOIN_V11 = " ¶ "   # 줄 사이 — TOKEN의 \s+가 줄을 넘어 영숫자를 잇지 않게 영숫자가 아닌 글자를 둔다
KEEP_MARKS_V11 = ("[가상]", "추정", "잠정", "가상 규칙")
MAX_SENTENCES_V11 = 3


def delex_lines(lines: list[str]) -> tuple[list[str], list[str], dict[int, set[int]]]:
    """줄 여럿을 한꺼번에 자리표로 가린다. 같은 값은 번호 하나로 묶는다(2026-10-13: "MTBF"가 {{2}}·{{4}}로 갈려 AI가 헷갈림).
    (가린 줄들, 값 목록, 자리표 번호 → 그 값이 나온 줄 번호들)."""
    text, raw_vals = delex(JOIN_V11.join(lines))
    vals: list[str] = []
    for v in raw_vals:
        if v not in vals:
            vals.append(v)
    text = PH.sub(lambda m: "{{%d}}" % (vals.index(raw_vals[int(m.group(1)) - 1]) + 1), text)
    units = [u.strip() for u in text.split(JOIN_V11.strip())]
    owner: dict[int, set[int]] = {}
    for li, u in enumerate(units):
        for m in PH.finditer(u):
            owner.setdefault(int(m.group(1)), set()).add(li)
    return units, vals, owner


SHORT_NUM_V11 = re.compile(r"\d{1,2}")


def delex_question_v11(question: str, vals: list[str]) -> str:
    """질문 속에서 문서 줄에도 있는 값만 같은 자리표로 가린다 — AI가 묻는 낱말을 자리표로 가리킬 수 있게(업계의 delexicalization은
    입력과 출력을 같은 자리표로 가린다). 질문에만 있는 값(문서에 없는 설비 번호 등)은 가리지 않아 답에 쓸 수 없다(문법이 막음).
    숫자 한두 글자("6단계"의 6)는 문서의 다른 6과 섞일 수 있어 묶지 않는다."""
    def rep(m):
        w = m.group(0)
        if w in vals and not SHORT_NUM_V11.fullmatch(w):
            return "{{%d}}" % (vals.index(w) + 1)
        return w
    return TOKEN.sub(rep, question)


def relex_subset(text: str, vals: list[str]) -> tuple[str | None, str | None]:
    """자리표 일부만 써도 된다. 없는 번호·자리표 밖 숫자·영문이면 거부."""
    if any(not 1 <= int(i) <= len(vals) for i in PH.findall(text)):
        return None, "없는 자리표"
    outside = TOKEN.findall(PH.sub(" ", text))
    if outside:   # 다시 요청할 때 어느 자리표로 쓸지 알려 준다 (5문항 확인: "MTBF"를 글자로 씀)
        hints = [f"{w} → {{{{{vals.index(w) + 1}}}}}" if w in vals else w for w in outside[:3]]
        return None, "자리표 밖의 숫자·영문: " + ", ".join(hints)
    return PH.sub(lambda m: vals[int(m.group(1)) - 1], text), None


# 되채운 값 뒤의 띄어쓰기·조사 (5차 확인 "5% 과 물 95% 를" → "5%와 물 95%를"). 숫자·%·℃로 끝나는 값만 받침을 안다 — 영문은 건드리지 않는다
JOSA_PAIRS_V11 = (("과", "와"), ("을", "를"), ("이", "가"), ("은", "는"), ("으로", "로"))
DIGIT_BATCHIM_V11 = {"0": True, "1": True, "2": False, "3": True, "4": False, "5": False, "6": True, "7": True, "8": True, "9": False,
                     "%": False, "℃": False, "°": False}
JOSA_RE_V11 = re.compile(r"([0-9%℃°])\s+(과|와|을|를|이|가|은|는|으로|로)(?![가-힣])")


def tidy_answer_v11(text: str) -> str:
    def fix(m):
        last, particle = m.group(1), m.group(2)
        has = DIGIT_BATCHIM_V11.get(last)
        for a, b in JOSA_PAIRS_V11:
            if particle in (a, b) and has is not None:
                particle = a if has else b
        return last + particle
    return JOSA_RE_V11.sub(fix, text)


# 10차 보강 (PARSE_V11, 2026-10-14 사용자 결정 — 앱 화면 "보고서에 적힌 MTBF은"): 되채운 값이 대문자 약어(글자로 끝남)이면
# 끝 글자를 알파벳 이름으로 읽어 조사를 맞춘다. L(엘)·M(엠)·N(엔)·R(알)만 받침이 있고, L·R은 ㄹ 받침이라 "으로" 대신 "로".
# 낱말처럼 읽는 영문(Lube 등 소문자 섞임)은 읽는 법을 몰라 건드리지 않는다.
ACRONYM_V11B = re.compile(r"[A-Z][A-Z0-9-]*[A-Z]")
LETTER_BATCHIM_V11B = {"L": "ㄹ", "M": "ㅁ", "N": "ㄴ", "R": "ㄹ"}


def tidy_acronym_v11b(text: str, vals: list[str]) -> str:
    for v in sorted({x for x in vals if ACRONYM_V11B.fullmatch(x)}, key=len, reverse=True):
        batchim = LETTER_BATCHIM_V11B.get(v[-1])

        def fix(m, batchim=batchim):
            p = m.group(1)
            if p in ("으로", "로"):
                return v + ("으로" if batchim and batchim != "ㄹ" else "로")
            for a, b in JOSA_PAIRS_V11:
                if p in (a, b):
                    return v + (a if batchim else b)
            return m.group(0)
        text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(v) + r"\s*(으로|과|와|을|를|이|가|은|는|로)(?![가-힣])", fix, text)
    return text


TIME_UNIT_V11 = re.compile(r"\d{1,2}:\d{2}\s*시(?![가-힣])")
# 2026-10-13 사용자 결정: 허락·지시 검사를 꼴로 넓힌다 (DENY는 "해도 돼요"·정해진 조작 동사만 잡아 "돌려도 돼요"를 놓쳤다).
# 허락 = "~도 돼요·됩니다·괜찮아요", "가능해요·가능합니다" — 앞 동사가 무엇이든. 지시 = 기계를 움직이는 동사 + "~하세요·주세요·십시오"
# ("확인하세요"·"물어보세요"는 통과). 원문 줄에 원래 같은 꼴이 있으면 막지 않는다(새로 생긴 것만).
PERMIT_V11 = re.compile(r"도\s*(?:돼|되요|됩니다|된다|괜찮)|가능(?:해요|합니다|하다)")
OPS_VERBS_V11 = ("리셋", "재시작", "재기동", "재가동", "해제", "교체", "가동", "정지", "투입", "작동", "운전", "시동", "분해",
                 "켜", "꺼", "끄", "올려", "올리", "돌려", "돌리", "열어", "닫아", "풀어", "조여", "바꿔", "바꾸")
ORDER_V11 = re.compile(r"(?:%s)(?:하|해)?\s*(?:주)?(?:세요|십시오)" % "|".join(OPS_VERBS_V11))


# 10차 보강 (2026-10-14, 사용자 결정 "숫자 모양 전부 · 스위치 없이 바로 고침"): 쓰는 순간 문법은 ASCII 숫자·라틴 글자만 막아
# 동그라미 숫자 "①"·전각 "１"·로마 "Ⅰ"·위첨자 "²"가 문법·코드 검사를 모두 지났다 (복사본 시험 "OEE 예시" 질문: "PQ는 ①, GQ는 ③" →
# 따로 판정도 통과). 숫자 모양 글자(유니코드 Nd·No·Nl)와 동그라미 글자(라틴 Ⓐ·한글 ㉠·㈠)를 같이 막는다.
CIRCLED_LETTERS_V14 = ((0x24B6, 0x24E9), (0x3200, 0x321E), (0x3260, 0x327F))   # 동그라미·괄호 라틴/한글 글자 (번호 표지로 쓰임)


def _is_numlike_v14(c: str) -> bool:
    o = ord(c)
    if o < 128:
        return False
    if unicodedata.category(c) in ("Nd", "No", "Nl"):
        return True
    return any(a <= o <= b for a, b in CIRCLED_LETTERS_V14)


def numlike_chars_v14(text: str) -> set[str]:
    """글 속의 ASCII 아닌 숫자 모양 글자 (①·１·Ⅰ·²·㉠ …)."""
    return {c for c in text if _is_numlike_v14(c)}


def numlike_new_v14(text: str, src: str) -> str | None:
    """text에 있고 src(원문 줄·질문)에는 없는 숫자 모양 글자 하나 (없으면 None) — 숫자 검사와 같은 '새로 생긴 것' 기준."""
    new = numlike_chars_v14(text) - numlike_chars_v14(src)
    return sorted(new)[0] if new else None


@lru_cache(maxsize=1)
def _numlike_class_v14() -> str:
    """GBNF 글자 모임에 넣을 숫자 모양 글자 범위 (BMP). \\uXXXX-\\uXXXX 꼴."""
    cps = [o for o in range(128, 0x10000) if not (0xD800 <= o <= 0xDFFF) and _is_numlike_v14(chr(o))]
    out, start, prev = [], None, None
    for o in cps:
        if start is None:
            start = prev = o
        elif o == prev + 1:
            prev = o
        else:
            out.append((start, prev))
            start = prev = o
    if start is not None:
        out.append((start, prev))
    return "".join(f"\\u{a:04X}" if a == b else f"\\u{a:04X}-\\u{b:04X}" for a, b in out)


def answer_grammar_v11(n: int) -> str:
    """① 쓰는 순간에 막기 (GBNF): {"answer": "…"} 안에서 자리표 밖에는 숫자(ASCII·동그라미·전각·로마·위첨자)·라틴 글자·중괄호·따옴표·역슬래시·
    줄바꿈을 쓸 수 없고, 자리표는 {{1}} … {{n}}만 쓸 수 있다. 구절(허락 문구 등)은 문법으로 막을 수 없어 check_answer_v11이 맡는다."""
    nums = " | ".join(f'"{i}"' for i in range(1, n + 1)) if n else None
    ph = f' | "{{{{" ( {nums} ) "}}}}"' if nums else ""
    return ('root ::= "{" ws "\\"answer\\"" ws ":" ws "\\"" content "\\"" ws "}"\n'
            f'content ::= ( [^0-9A-Za-z{{}}"\\\\\\n{_numlike_class_v14()}]{ph} )*\n'
            'ws ::= [ \\t\\n]*')


def restore_literals_v11(text: str, vals: list[str]) -> tuple[str, int]:
    """② 코드가 바로 고치기: 가린 값(숫자·영문 이름)을 자리표 대신 글자로 쓴 곳을 그 자리표로 되돌린다(긴 값부터). (글, 고친 수)."""
    fixed = 0
    for i in sorted(range(len(vals)), key=lambda k: -len(vals[k])):
        v = vals[i]
        parts = PH.split(text)   # 자리표 안은 건드리지 않는다 — split은 [밖, 번호, 밖, 번호, …]
        for j in range(0, len(parts), 2):
            pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(v) + r"(?![A-Za-z0-9])")
            parts[j], k = pat.subn("{{%d}}" % (i + 1), parts[j])
            fixed += k
        text = "".join(p if j % 2 == 0 else "{{%s}}" % p for j, p in enumerate(parts))
    return text, fixed


# 10차 보강 LEAD_V12 (2026-10-14 사용자 결정 "원문에 없을 때만 막기"): 해야 할 일을 말하는 꼴 ("조정해야 합니다").
# 고른 줄이나 질문에 같은 꼴이 있으면 통과 — 질문이 "뭐라고 써야 해요?"면 답의 "써야 해요"는 질문을 받은 말이다.
OBLIGE_V12 = re.compile(r"야\s*(?:합니다|해요|한다|함|하며|하고|돼요|됩니다|된다)")


def oblige_new_v12(text: str, src: str, question: str) -> bool:
    if not OBLIGE_V12.search(text) or OBLIGE_V12.search(src) or OBLIGE_V12.search(question):
        return False
    # WRITE_RULES_V17: 질문이 "~해야 돼?·해야 하죠?·확정해야 됨?"처럼 의무 꼴로 물었으면 답의 "~해야 해요"는 질문을 받은 말이다
    # (공개 세트 막힌 글 9건 모두 맞는 말이었고 질문에 이 꼴이 있었다 — OBLIGE_V12는 "야 합니다·해요…"만 질문에서 찾았다)
    return not (v17_on() and OBLIGE_Q_V17.search(question))


# ---------------------------------------------------------------- WRITE_RULES_V17 (2026-10-14 시급한 문제 2 "원문 복사", 계획 승인)
# 근거: 공개 세트 E8·E9·CMP30의 새 글 후보 66개를 별도 라벨러(Opus)가 라벨링 — 코드 규칙이 막은 24개 중 22개가 원문과 뜻이 같았다.
# 먼저 조이고(뒤집힘: 원문에 없는 "수 있"·접근 금지 경고 줄 제외) 그다음 푼다(질문이 받은 "~해야 한다"·"~만 가능"+부정·불 끄기·안전 낱말은 답에 쓴 칸에서만).
def v17_on() -> bool:
    s = settings()
    return bool(s.parse_v8 and s.write_rules_v17)


OBLIGE_Q_V17 = re.compile(r"야\s*(?:합|해|한|함|하|돼|되|됨|될|할)")
RESTRICT_PERMIT_V17 = re.compile(r"만\s*가능(?:해요|합니다|하다)")
NEG_V17 = re.compile(r"없|않|못|불가|(?<![가-힣])안\s")
FIRE_V17 = re.compile(r"불|화재|소화")
FIRE_OFF_V17 = re.compile(r"(?:소화제|소화기|소화|모래|불|화재|분진)[가-힣]{0,3}?(?:으로|로|을|를)?\s*(?:끄|꺼)\s*(?:주)?(?:세요|십시오)")
POSSIB_V17 = re.compile(r"수\s*있")
# 접근 금지 경고: "사람이 떨어져 있어라"(Stay away)가 주어 없이 "…에서 떨어진다"로 적힌 줄 — 9B가 "떨어질 수 있으니"로 뒤집어 읽었다 (2026-10-14 접근금지 보고서)
KEEPAWAY_V16 = re.compile(r"에서\s*떨어진다|떨어져\s*(?:있|서|야)")


def is_keepaway_v16(line: str) -> bool:
    """접근 금지·자동 이동 경고 줄인가 ("…에서 떨어진다"·"떨어져 있…"). "압력이 떨어졌다"·"떨어뜨리고"·"떨어지면"은 아니다."""
    return bool(KEEPAWAY_V16.search(line))


def permit_new_v11(text: str, src: str) -> bool:
    """허락 꼴이 새로 생겼나. WRITE_RULES_V17: 부정이 함께 있는 "~에서만 가능합니다"는 허락이 아니라 제한이다."""
    t = RESTRICT_PERMIT_V17.sub("", text) if (v17_on() and NEG_V17.search(text)) else text
    return bool(PERMIT_V11.search(t)) and not PERMIT_V11.search(src)


def _without_fire_off_v17(text: str) -> str:
    """WRITE_RULES_V17: "소화제로·모래로·불을 끄세요"는 기계를 끄라는 말이 아니다 — 불 끄기 꼴("불·화재·소화·모래·분진" + 끄세요)만 지우고 본다.
    "화재가 났으니 주축 전원을 끄세요"는 기계 전원이므로 지우지 않는다."""
    if not (v17_on() and FIRE_V17.search(text)):
        return text
    return FIRE_OFF_V17.sub("", text)


def order_new_v11(text: str, src: str) -> bool:
    """조작 지시가 새로 생겼나."""
    return bool(ORDER_V11.search(_without_fire_off_v17(text))) and not ORDER_V11.search(src)


def deny_new_v11(text: str, src: str) -> bool:
    """허락·지시 문구(DENY)가 새로 생겼나."""
    return bool(DENY.search(_without_fire_off_v17(text))) and not DENY.search(src)


def possib_new_v17(text: str, src: str, question: str) -> bool:
    """원문 줄·질문에 없는 가능성 꼴("수 있")이 새로 생겼나 — 의무·허락·지시와 같은 '새 양태' 검사 (뜻이 뒤집힌 "떨어질 수 있으니")."""
    return v17_on() and bool(POSSIB_V17.search(text)) and not POSSIB_V17.search(src) and not POSSIB_V17.search(question)


JOSA_V17 = re.compile(r"(?:으로|에서|까지|마다|은|는|이|가|을|를|의|에|도|만|과|와|로)$")


def _toks_v17(t: str) -> set[str]:
    out = set()
    for w in re.findall(r"[가-힣]{2,}|[A-Za-z0-9][A-Za-z0-9.\-/%]*", t):
        if re.match(r"[가-힣]", w) and len(w) >= 3:
            w = JOSA_V17.sub("", w)
        if len(w) >= 2 or w.isdigit():
            out.add(w)
    return out


def used_src_v17(answer: str, lines: list[str], question: str) -> str:
    """답에 쓴 칸의 글: 표 줄은 칸마다, 다른 줄은 줄 통째를 한 단위로 보고, 답에만 있는 낱말(질문에 없는 낱말)이 가장 많이 겹치는 단위(동점 포함).
    겹침이 하나도 없으면 줄 전체 — 지금처럼 엄격하게."""
    at = _toks_v17(answer) - _toks_v17(question)
    units = []
    for ln in lines:
        head, cells = split_line(ln)
        if head is None:
            units.append((ln, len(_toks_v17(ln) & at)))
        else:
            units += [(head + " — " + c, len(_toks_v17(c) & at)) for c in cells]
    best = max((n for _, n in units), default=0)
    return " ".join(u for u, n in units if n == best) if best > 0 else " ".join(lines)


# 10차 보강 TERM_V13 (2026-10-14 사용자 결정): 용어집 "쓰지 않는 말"이 원문 줄·질문에 없는데 AI 글에 새로 나오면 막는다
# (앱 화면 "이송 속도의 표준 영어 표현은 피드 레이트(Feed Rate)" — 피드는 Feed의 쓰지 않는 말).
# 조건이 붙은 말("차단기(단독)"·"(괄호로만)"·"(…원문에서만)")은 언제 써도 되는지 코드가 가를 수 없어 빼고, 영문 낱말은 자리표가 지킨다.
# 낱말 경계: 앞은 한글이 아니고, 뒤는 끝·한글 아님·조사 하나 ("에어건"의 "에어"는 잡지 않음).
ENGLISH_Q_V13 = re.compile(r"영어\s*(?:로|이름|명|표기|표현)|영문\s*(?:이름|명|표기)?|영어로는")
AVOID_PARTICLES_V13 ="(?:으로|이라고|라고|은|는|이|가|을|를|의|에|로|와|과|도|만)"


@lru_cache(maxsize=1)
def avoid_words_v13() -> tuple[str, ...]:
    out = set()
    for r in glossary_rows():
        for w in re.split(r"[,，]", r["avoid"] or ""):
            w = w.strip()
            if not w or "(" in w or re.search(r"[A-Za-z]", w) or len(re.sub(r"\s", "", w)) < 2:
                continue
            out.add(w)
    return tuple(sorted(out, key=len, reverse=True))


def avoid_new_v13(text: str, src: str, question: str) -> str | None:
    """text에 새로 나온 쓰지 않는 말(원문·질문에 없음) 하나, 없으면 None."""
    for w in avoid_words_v13():
        pat = re.compile(r"(?<![가-힣])" + re.escape(w) + r"(?=$|[^가-힣]|" + AVOID_PARTICLES_V13 + r"(?![가-힣]))")
        if pat.search(text) and not pat.search(src) and not pat.search(question):
            return w
    return None


def term_v13_on() -> bool:
    s = settings()
    return bool(s.parse_v8 and s.term_v13)


def check_lead_code_v12(lead: str, lines: list[str], question: str) -> str | None:
    """1차 문지기 길 AI 앞머리의 코드 검사 — 새로 쓴 답(check_answer_v11)과 같은 꼴 + "~해야 한다". 통과면 None."""
    src = " ".join(lines)
    if (c := numlike_new_v14(lead, src + " " + question)):   # 10차 보강 (2026-10-14): 원문·질문에 없던 숫자 모양 글자
        return f"숫자 모양 글자: {c}"
    if permit_new_v11(lead, src):
        return "허락 꼴"
    if order_new_v11(lead, src):
        return "조작 지시"
    if oblige_new_v12(lead, src, question):
        return "해야 할 일 꼴"
    if possib_new_v17(lead, src, question):   # WRITE_RULES_V17: 뜻 뒤집힘 ("떨어질 수 있고")
        return "가능성 꼴 (원문·질문에 없음)"
    if any(w in lead for w in SAFETY_WORDS) and not any(w in src for w in SAFETY_WORDS):
        return "안전 낱말"
    if term_v13_on() and (w := avoid_new_v13(lead, src, question)):
        return f"쓰지 않는 말: {w}"
    return None


def check_lead_v12(question: str, lead: str, lines: list[str]) -> tuple[bool, dict]:
    """앞머리를 보여도 되나: 코드 검사 → 따로 판정(answer_faith 지시문, 오류면 빼기 — fail closed). (통과, LLM 기록)."""
    tr, t0 = _trace("lead_faith"), time.monotonic()
    why = check_lead_code_v12(lead, lines, question)
    if why:
        tr.update(reason=why, rejected=[{"text": lead[:300], "reason": why}])
        return False, tr
    tr["tries"] = 1
    try:
        out = chat_json(prompts.answer_faith(lines, lead), schemas.ANSWER_FAITH, "lead_faith", 120)
        ok = isinstance(out, dict) and set(out) == {"faithful", "problem"} and out["faithful"] is True
        tr.update(used=ok, reason=None if ok else "문서와 다름")
        if not ok:
            tr["rejected"] = [{"text": lead[:300], "reason": str((out or {}).get("problem") or "")[:120]}]
    except (LlmUnavailable, LlmBadOutput) as e:
        ok = False
        tr["reason"] = f"LLM 오류: {e}"
    tr["ms"] = int((time.monotonic() - t0) * 1000)
    return ok, tr


# 10차 보강 (2026-10-14, 사용자 결정 "이름 되풀이 + 열거 이름 빠짐 · 스위치 없이 바로 고침"): 따로 판정(answer_faith)이 "질문에 답했나"를
# 보지 않아 값 없는 답이 통과했다 (복사본 시험 "OEE 예시" 질문: "PQ는 PQ이고, GQ는 GQ, … " — 값 자리에 이름을 되풀이하고 RQ를 뺌).
# 판정 AI에 지시를 더하지 않고(전례: 답 거부가 늘었음) 코드가 이 두 꼴만 좁게 본다.
ECHO_NAME_V14 = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9\-]*)(?:은|는|이|가)\s+\1(?![A-Za-z0-9])")
LIST_NAME_V14 = r"[A-Z][A-Z0-9]{1,5}"
LIST_SEP_V14 = r"\s*(?:,|·|/|、|와|과|및|랑|하고)\s*"
LISTED_V14 = re.compile(r"(?<![A-Za-z0-9])(" + LIST_NAME_V14 + r"(?:" + LIST_SEP_V14 + LIST_NAME_V14 + r")+)(?![A-Za-z0-9])")


def echo_name_v14(answer: str, src: str, question: str | None) -> str | None:
    """"PQ는 PQ이고"처럼 영문 이름이 자기 자신을 뜻으로 되풀이한 꼴 하나 (없으면 None). 원문 줄에 같은 꼴이 있거나
    영어 이름을 묻는 질문이면 통과 ("OEE의 영어 이름은 OEE예요"는 맞는 답)."""
    if question and ENGLISH_Q_V13.search(question):
        return None
    for m in ECHO_NAME_V14.finditer(answer):
        if m.group(0) not in src:
            return m.group(1)
    return None


def listed_names_v14(question: str) -> list[str]:
    """질문이 "PQ, GQ, RQ"처럼 나열한 영문 이름 (나열이 없으면 [])."""
    out: list[str] = []
    for m in LISTED_V14.finditer(question):
        for n in re.findall(LIST_NAME_V14, m.group(1)):
            if n not in out:
                out.append(n)
    return out


def missing_listed_v14(answer: str, question: str) -> str | None:
    """질문이 나열한 이름 가운데 답에 없는 첫 이름 (없으면 None)."""
    for n in listed_names_v14(question):
        if not re.search(r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])", answer):
            return n
    return None


def check_answer_v11(answer: str, lines: list[str], used_lines: set[int], question: str | None = None, oblige: bool = True) -> str | None:
    """되채운 답 글 검사 (원문 줄과 견줌). 통과면 None. question을 주면(LEAD_V12) "~해야 한다" 꼴도 본다.
    oblige=False (OBLIGE_CHECK=0 실험, 일반 새로 쓰기에서만): "~해야 한다" 꼴 검사 하나만 건너뛴다 — 다른 검사는 그대로."""
    src = " ".join(lines)
    if oblige and question is not None and settings().lead_v12 and oblige_new_v12(answer, src, question):
        return "해야 할 일 꼴 (원문·질문에 없음)"
    if question is not None and possib_new_v17(answer, src, question):   # WRITE_RULES_V17: 뜻 뒤집힘 ("떨어질 수 있으니")
        return "가능성 꼴 (원문·질문에 없음)"
    if question is not None and term_v13_on() and (w := avoid_new_v13(answer, src, question)):
        return f"쓰지 않는 말: {w} (원문·질문에 없음)"
    if not answer.strip():
        return "빈 글"
    if len(answer) > 300:   # 문법으로 묶으면 스키마의 maxLength가 없어 코드가 본다
        return "너무 김"
    # 2026-10-13 사용자 결정 "합니다체 허용": 말투(~합니다·~입니다)는 막지 않는다 — 허락 문구("해도 됩니다")는 아래 DENY가 따로 막는다
    if TIME_UNIT_V11.search(answer):
        return "시각 뒤에 '시'를 또 붙임 — 자리표 값을 그대로 쓴다"
    if FORBIDDEN.search(answer) or "§" in answer or "DOC-" in answer:
        return "출처 표기"
    if KO_NUM.search(answer) and not KO_NUM.search(src):
        return "한글 수사"
    if (c := numlike_new_v14(answer, src + " " + (question or ""))):   # 10차 보강 (2026-10-14): 원문·질문에 없던 숫자 모양 글자
        return f"숫자 모양 글자: {c}"
    if (n := echo_name_v14(answer, src, question)):   # 10차 보강 (2026-10-14): "PQ는 PQ이고" — 값 자리에 이름을 되풀이
        return f"값 자리에 이름을 되풀이함: {n} — 문서 줄의 값 자리표를 쓴다"
    if question is not None and (n := missing_listed_v14(answer, question)):   # 질문이 나열한 이름이 답에 빠짐
        return f"질문이 나열한 이름이 답에 없음: {n}"
    if deny_new_v11(answer, src):
        return "허락·지시 문구"
    if permit_new_v11(answer, src):
        return "허락·지시 문구 (허락 꼴)"
    if order_new_v11(answer, src):
        return "허락·지시 문구 (조작 지시)"
    if any(w in answer for w in SAFETY_WORDS) and not any(w in src for w in SAFETY_WORDS):
        return "안전 낱말"
    lost = [m for m in KEEP_MARKS_V11 if m not in answer and any(m in lines[i] for i in used_lines)]
    if lost:
        return "빠진 꼬리표: " + ", ".join(lost)
    if len([x for x in re.split(r"(?<=[.!?])\s+", answer.strip()) if x]) > MAX_SENTENCES_V11:
        return "문장이 너무 많음"
    return None


# ---------------------------------------------------------------- 안전 영역 새로쓰기 (2026-10-14 사용자 결정 "대체 방식·엄격")
# 점검 순서·안전 줄을 쉬운 말로 1:1 다시 쓴다. 숫자·단위·이름·[버튼]은 자리표로 가리고, 안전 낱말·조건 말·순서 표시·"자격자/HFO"를 지키는지
# 코드가 엄격히 보고(check_safe_unit_v15), 따로 판정(faith)까지 지나야 쓴다. 하나라도 실패하면 새 글 전부를 버리고 부른 쪽이 원문만 보인다.
# 고정 서식(LOTO 6+3·고전압 5분 문구·보호구·차단 지점 표)은 이 함수로 보내지 않는다 — 프로그램이 원문 그대로 붙인다 (안전 규칙 2.5).
SAFE_KEEP_V15 = ("자격자", "HFO", "원문·현장 확인 필요")
BRACKET_V15 = re.compile(r"\[[^\]\n]{1,40}\]")
IMPERATIVE_V15 = re.compile(r"(?:세요|십시오)(?![가-힣])")   # 안전 영역은 어떤 동사든 새 명령형을 만들지 않는다 (ORDER_V11은 조작 동사만 봄)


def check_safe_unit_v15(new: str, src: str) -> str | None:
    """안전 영역 다시 쓴 조각 한 개의 엄격한 검사 (원문 조각과 견줌). 통과면 None."""
    why = check_unit(new, src)   # 빈 글·출처·한글 수사·숫자 모양·허락·§·꼬리표·조건 말·길이·쓰지 않는 말
    if why:
        return why
    for w in SAFETY_WORDS:
        if w in src and w not in new:
            return f"안전 낱말 빠짐: {w}"
        if w in new and w not in src:
            return f"새 안전 낱말: {w}"
    for w in SAFE_KEEP_V15:
        if w in src and w not in new:
            return f"표시 빠짐: {w}"
    if sorted(BRACKET_V15.findall(src)) != sorted(BRACKET_V15.findall(new)):
        return "[ ] 안의 글(버튼 이름 등)이 다름"
    if src.count("→") != new.count("→"):
        return "순서 표시(→)가 다름"
    if numlike_chars_v14(src) - numlike_chars_v14(new):
        return "단계 번호 표시 빠짐"
    for rx, name in ((PERMIT_V11, "허락 꼴"), (ORDER_V11, "조작 지시"), (OBLIGE_V12, "해야 할 일 꼴"), (IMPERATIVE_V15, "명령형 (원문에 없음)")):
        if rx.search(new) and not rx.search(src):
            return name
    return None


def write_safe_steps_v15(texts: list[str]) -> tuple[list[str] | None, dict]:
    """점검 순서 글 조각 n개를 같은 개수·순서로 쉬운 말로 다시 쓴다. 돌려주는 값 = (새 글 n개 또는 None, trace).
    조각 하나라도 검사에 실패하면 전부 버린다(None) — 다시 요청은 1번(사유를 붙여). LLM 오류·판정 실패도 None (fail closed)."""
    tr, t0, s = _trace("safe_simplify"), time.monotonic(), settings()
    tr["rejected"] = []
    if not texts or any(not t.strip() for t in texts):
        tr["reason"] = "다시 쓸 글이 없음"
        return None, tr
    dl = [delex(x) for x in texts]
    sent = [d[0] for d in dl]
    s_long = replace(s, read_s=max(s.read_s, 12.0))   # 8단계쯤 되는 점검 순서는 8초 안에 못 쓸 수 있다 (남은 시간 예산이 위에서 줄인다)
    feedback = None
    for _ in range(2):
        tr["tries"] += 1
        try:
            out = chat_json(prompts.safe_simplify_v15(sent, feedback), schemas.simplify(len(sent), max(len(x) for x in sent)),
                            "safe_simplify", min(3000, sum(len(x) for x in sent) * 2 + 300), s=s_long)
        except (LlmUnavailable, LlmBadOutput) as e:
            tr["reason"] = f"LLM 오류: {e}"
            break
        got = out.get("texts") if isinstance(out, dict) and set(out) == {"texts"} else None
        if not isinstance(got, list) or len(got) != len(sent) or not all(isinstance(t, str) and t.strip() for t in got):
            tr["reason"], feedback = "형식 오류", "형식 오류: 조각 수만큼 글을 쓴다"
            continue
        result, reasons = [], []
        for i, (t, (_, vals), src) in enumerate(zip(got, dl, texts), 1):
            new, why = relex(t.strip(), vals)
            why = why or check_safe_unit_v15(new, src)
            if why:
                reasons.append(f"{i}번 조각: {why}")
            result.append(new or t)
        if reasons:
            tr["rejected"].append({"text": " / ".join(result)[:300], "reason": "; ".join(reasons)[:200]})
            tr["reason"], feedback = reasons[0], "; ".join(reasons[:3])
            if time.monotonic() - t0 > s.budget_s - 5:
                break
            continue
        try:   # 따로 판정: 원문 조각과 새 글이 같은 뜻인가 (LLM 오류면 쓰지 않는다)
            ver = chat_json(prompts.faith(texts, result), schemas.FAITH, "safe_faith", 160)
        except (LlmUnavailable, LlmBadOutput) as e:
            tr["reason"] = f"판정 LLM 오류: {e}"
            break
        if isinstance(ver, dict) and set(ver) == {"same_meaning", "problem"} and ver["same_meaning"] is True:
            tr.update(used=True, reason=None, ms=int((time.monotonic() - t0) * 1000), changed=sum(1 for a, b in zip(result, texts) if a != b))
            return result, tr
        problem = str((ver or {}).get("problem") or "뜻이 다름")[:120]
        tr["rejected"].append({"text": " / ".join(result)[:300], "reason": "판정: " + problem})
        tr["reason"], feedback = "문서와 다름: " + problem, "원문과 뜻이 다르다는 판정: " + problem
        if time.monotonic() - t0 > s.budget_s - 5:
            break
    tr["ms"] = int((time.monotonic() - t0) * 1000)
    return None, tr


def check_answer_safe_v15(answer: str, lines: list[str], question: str | None = None) -> str | None:
    """안전 영역 새로쓰기 2·4단계의 추가 검사 (check_answer_v11 위에): 찾은 줄에 있는 안전 낱말·조건 말·'자격자/HFO' 표시는 새 글에도 있어야 하고,
    새 명령형(세요·십시오)은 원문에 없으면 거부. 요약이라 줄 수만큼 길 수는 없으므로 '낱말이 하나라도 남았나'로 본다. 통과면 None.
    WRITE_RULES_V17(question을 줄 때): 안전 낱말은 줄 전체가 아니라 답에 쓴 칸(답에만 있는 낱말이 가장 많이 겹친 칸)에서만 요구한다 —
    답과 상관없는 칸의 "잠금·표지: ○" 때문에 맞는 답이 막혔다. 칸을 못 찾으면 줄 전체(지금처럼)."""
    src = " ".join(lines)
    safe_src = used_src_v17(answer, lines, question) if (question is not None and v17_on()) else src
    for w in SAFETY_WORDS:
        if w in safe_src and w not in answer:
            return f"안전 낱말 빠짐: {w}"
    for w in STRICT_WORDS:
        if w in safe_src and w not in answer:   # V17: 조건 말도 답에 쓴 칸에서만 (다른 칸의 "않"·"먼저"가 맞는 답을 막았다)
            return f"조건 말 빠짐: {w}"
    for w in SAFE_KEEP_V15:
        if w in src and w not in answer:
            return f"표시 빠짐: {w}"
    if IMPERATIVE_V15.search(answer) and not IMPERATIVE_V15.search(src):
        return "명령형 (원문에 없음)"
    return None


def title_words_cmp(titles: list[str] | None, n: int) -> list[str] | None:
    """WRITE_TITLES (2026-10-14 비교 실험): 줄마다 절 제목에서 한글·빈칸만 남긴다(숫자·영문은 답에 옮겨 쓰면 코드 검사가 거부한다).
    줄 수와 맞지 않거나 쓸 제목이 하나도 없으면 None."""
    if not titles or len(titles) != n:
        return None
    out = [" ".join(re.sub(r"[^가-힣\s]", " ", t or "").split())[:30] for t in titles]
    return out if any(out) else None


def write_doc_answer(question: str, lines: list[str], safe: bool = False, titles: list[str] | None = None) -> tuple[str | None, list[dict]]:
    """새 답 글(되채운 것) 또는 None, 그리고 LLM 기록(write_answer·answer_faith). 다시 요청은 1번(사유를 붙여).
    safe (안전 영역 새로쓰기 2·4단계): check_answer_safe_v15를 더해 건다.
    titles (WRITE_TITLES): 줄마다 절 제목 — 스위치가 꺼져 있으면 쓰지 않는다."""
    traces: list[dict] = []
    tr, t0, s = _trace("write_answer"), time.monotonic(), settings()
    units, vals, owner = delex_lines(lines)
    shots = bool(s.write_shots)
    ttl = title_words_cmp(titles, len(units)) if s.write_titles else None
    feedback, answer = None, None
    tr["rejected"] = []   # 0단계 (2026-10-13 사용자 결정): 걸린 글과 까닭을 AI 기록에 남긴다 (화면에는 안 보임)
    for _ in range(2):
        tr["tries"] += 1
        try:
            out = chat_json(prompts.write_answer(delex_question_v11(question, vals), units, feedback, shots=shots, titles=ttl),
                            schemas.WRITE_ANSWER, "write_answer", 400,
                            grammar=answer_grammar_v11(len(vals)))   # ① 쓰는 순간에 막기: 자리표 밖 숫자·영문, 없는 자리표 번호
        except (LlmUnavailable, LlmBadOutput) as e:
            tr["reason"] = f"LLM 오류: {e}"
            break
        raw = out.get("answer") if isinstance(out, dict) and set(out) == {"answer"} else None
        if not isinstance(raw, str) or not raw.strip():
            tr["reason"], feedback = "형식 오류", "형식 오류: answer 칸에 글을 쓴다"
            continue
        raw, fixed = restore_literals_v11(raw.strip(), vals)   # ② 코드가 바로 고치기: 가린 값을 글자로 쓴 곳을 자리표로 되돌림
        tr["fixed"] = tr.get("fixed", 0) + fixed
        new, why = relex_subset(raw, vals)
        new = tidy_answer_v11(new) if new else new
        if new and s.parse_v8 and s.parse_v11:   # 10차 보강: 영문 약어 뒤 조사 ("MTBF은" → "MTBF는")
            new = tidy_acronym_v11b(new, vals)
        used_lines = {li for i in PH.findall(raw) for li in owner.get(int(i), ())}
        # 질문은 늘 준다 — "~해야 한다"·쓰지 않는 말 검사는 안에서 스위치(lead_v12·term_v13)를 본다 (2026-10-14)
        # OBLIGE_CHECK=0 실험: 일반 새로 쓰기(safe=False)에서만 "해야 할 일 꼴" 검사를 끈다 — 안전 영역 새로쓰기(safe=True)는 켠 채로 둔다
        why = why or check_answer_v11(new, lines, used_lines, question=question, oblige=(s.oblige_check or safe))
        if not why and safe and new:
            why = check_answer_safe_v15(new, lines, question)   # 안전 영역: 안전 낱말·조건 말 보존 (2026-10-14; V17: 답에 쓴 칸에서만)
        if not why and new and s.parse_v8 and s.term_v13 and ENGLISH_Q_V13.search(question) and not re.search(r"[A-Za-z]", new):
            # 10차 보강 TERM_V13 (2026-10-14 짝 질문 로그): 영어 이름을 묻는데 답에 영어 이름(자리표)이 없다 —
            # "로트 해제의 영어 이름은 로트 해제예요"를 판정(answer_faith)이 통과시켰다. 질문에 답했는지를 코드가 이 꼴만큼 본다
            why = "영어 이름을 묻는데 답에 영어 이름이 없음 — 문서 줄의 영어 이름 자리표를 쓴다"
        if not why:
            answer = new
            tr.update(used=True, reason=None)
            break
        tr["rejected"].append({"text": (new or raw)[:300], "reason": why})
        tr["reason"], feedback = why, why
        if time.monotonic() - t0 > s.budget_s - 5:
            break
    tr["ms"] = int((time.monotonic() - t0) * 1000)
    traces.append(tr)
    if answer is None:
        return None, traces
    ftr, t1 = _trace("answer_faith"), time.monotonic()
    ftr["tries"] = 1
    try:
        out = chat_json(prompts.answer_faith(lines, answer), schemas.ANSWER_FAITH, "answer_faith", 120)
        ok = isinstance(out, dict) and set(out) == {"faithful", "problem"} and out["faithful"] is True
        ftr.update(used=ok, reason=None if ok else ("문서와 다름" if isinstance(out, dict) and "faithful" in out else "형식 오류"))
        if not ok:   # 0단계: 판정이 막은 글과 그 까닭 (판정이 바꿔 쓴 글에 치우쳤는지 사람이 볼 수 있게)
            ftr["rejected"] = [{"text": answer[:300], "reason": str((out or {}).get("problem") or "")[:120]}]
    except (LlmUnavailable, LlmBadOutput) as e:   # 판정을 못 받으면 쓰지 않는다 (fail closed)
        ok = False
        ftr["reason"] = f"LLM 오류: {e}"
    ftr["ms"] = int((time.monotonic() - t1) * 1000)
    traces.append(ftr)
    return (answer if ok else None), traces
