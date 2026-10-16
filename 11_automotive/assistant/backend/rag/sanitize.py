"""검색 조각에서 원문 출처를 지운다 (D-03, FR-MNT-01-10, FR-AST-COM-02).

사내 문서 본문 안의 원문 출처는 사람의 근거 추적용이므로 파일에는 그대로 두고,
비서가 쓰는 검색 조각·답·화면에서만 뺀다. [실제]/[참고]/[가상] 꼬리표는 남긴다.
원문 문서를 가리키는 "Haas …" 이름은 "제조사 …"로 바꿔 보인다 (HAAS_DOC, 2026-10-11 사용자 결정).
"Haas" 낱말 없이 쓴 원문 이름("**원문:**" 줄, 매뉴얼 이름 + 장 번호, 판 연도, 영문 표 이름)과 지운 뒤 남은 찌꺼기도
정리한다 (SOURCE_LINE·SRC_NAME·RESIDUE, 2026-10-11 사용자 결정 "⑤ E5 전에 함께").
"""
import re

SOURCE_COLUMN = re.compile(r"원문|출처|근거")
DROP_ROW_FIRST_CELL = {"원문", "근거", "출처", "근거·원문", "원문 위치"}
# "**원문:** …" 줄 (DOC-03 §2.1~2.15 — 원문 절 이름을 영어로 늘어놓은 줄)은 문서 보기처럼 조각에서도 뺀다 (2026-10-11).
# 줄 하나만 본다([ \t]) — 다음 줄로 넘어가지 않는다
SOURCE_LINE = re.compile(r"^[ \t]*(?:\*\*)?원문(?:\*\*)?[ \t]*:.*(?:\n|$)", re.M)

# "(원문 …)" 괄호는 출처일 때만 지운다. "(원문 값 ±20%)"처럼 값·뜻을 담은 괄호는 남긴다
# (2026-10-08: 앞 글자만 보고 지워 552 점검 7의 허용 오차가 빠진 문제)
SOURCE_PAREN = re.compile(r"\((?:원문|출처|KOSHA)[^)]*\)")
CITE_MARK = re.compile(r"\b(?:TG|RD|AD|ID)-?\d{4}|NGC|VFVM|LUBE|96-|\bRev\b|쪽|\d행|p\.\s?\d|Haas|KOSHA|B-M-|알람 목록|CSV|PDF"
                       r"|URL|https?://|매뉴얼|Manual|Guide|사양|\.pdf|\.html", re.I)
META_ONLY = re.compile(r"^\((?:원문|출처|KOSHA)(?:은|의)?[\s:,·]*(?:그대로|이름|뜻 그대로 줄임|그대로 줄임|번호[^)]*)?[\s:,·]*\)$")


def _source_paren(m: re.Match) -> str:
    s = m.group(0)
    return "" if CITE_MARK.search(s) or META_ONLY.match(s) else s


def _ref(m: re.Match) -> str:
    """원문 번호·수집 파일 이름을 지운다. 바로 뒤에 한글 조사가 붙어 있으면 "원문"으로 바꿔 문장을 남긴다
    ("RD0080의 3개월" → "원문의 3개월", "RD0080 99행" → " 99행"은 그대로 지움)."""
    s = m.group(0)
    if s.startswith("(") or s[-1:].isspace() or s.endswith(")"):
        return ""   # 괄호째·빈칸까지 지운 덧붙임 ("목차(B-M-25-2026)에는", "GUIDE B-M-25-2026 에너지") — 뒤 글은 앞 낱말 것이다
    nxt = m.string[m.end():m.end() + 1]
    return "원문" if "가" <= nxt <= "힣" else ""


# 경계 (2026-10-11): 파이썬 re는 한글도 \w로 보므로 "RD0080의"처럼 조사가 붙으면 \b가 없다.
# 영숫자 토큰(문서 번호·Rev) 앞뒤는 \b 대신 (?<![A-Za-z0-9])·(?![0-9])로 막는다 (root-cause-guards 8절).
_NB = r"(?<![A-Za-z0-9])"
INLINE = [
    (re.compile(r"\[(실제|참고|가상|제안)[^\]]*?:[^\]]*\]"), r"[\1]"),     # [실제: TG0125 …] → [실제]
    (re.compile(r"\s*←\s*[^|\n]*"), ""),                                  # "DOC-03 §2.1 ← 원문 이름" → "DOC-03 §2.1"
    (re.compile(r"`[^`]*(?:docs/|\.pdf|\.html|\.csv|\.txt|_manifest|__body|__Rev)[^`]*`"), _ref),   # 수집 파일 이름
    (SOURCE_PAREN, _source_paren),
    (re.compile(r"https?://\S+"), ""),
    (re.compile(_NB + r"(?:TG|RD|AD|ID)-?\d{4}(?![0-9])(?:\s*Rev\.?\s*[A-Z](?![A-Za-z0-9])(?:\s*\([^)]*\))?)?"), _ref),
    # 괄호 안의 원문 번호는 괄호째만 지운다 (2026-10-11): 아래 "번호 + 뒤 글" 줄이 괄호 뒤의 사내 문서 글까지 지웠다
    # ("고 쓴다(VFVM-SM-07 45행) ④ 점검 9 모터 브레이크 절차가 …"의 ④ 문장, "18.1(VFVM-SM-18)에도 있다"의 "에도 있다")
    (re.compile(r"\(\s*" + _NB + r"(?:96-(?:KO)?8210|VFVM-SM-\d+|NGC-ESM-\d+|LUBE-SM-\d+|KOSHA\s*[A-Z]-[A-Z]-\d+-\d+)(?![0-9])[^()\n]*\)"), ""),
    # 장 번호가 뒤따르는 KOSHA 지침 번호: 번호와 장 번호(원문 위치)를 빼고 "KOSHA 지침"으로 남긴다 — Haas 매뉴얼 장 번호와 같은 원칙
    # ("KOSHA B-M-25-2026 6장(작업 전)과 7장(작업 후)의 순서를 그대로 따른다" → "KOSHA 지침의 순서를 그대로 따른다")
    (re.compile(_NB + r"KOSHA\s*[A-Z]-[A-Z]-\d+-\d+(?![0-9])\s+\d+장(?:\([^)\n]*\))?(?:\s*(?:과|와|·)\s*\d+장(?:\([^)\n]*\))?)*"),
     "KOSHA 지침"),
    (re.compile(_NB + r"(?:96-(?:KO)?8210|VFVM-SM-\d+|NGC-ESM-\d+|LUBE-SM-\d+|KOSHA\s*[A-Z]-[A-Z]-\d+-\d+)(?=[가-힣])"), "원문"),
    # 번호 뒤 이름(지침 제목 등)까지 지우되 줄은 넘지 않는다 (2026-10-11: 줄을 넘어 DOC-05 §7 안전 서식 끝의 사내 출처 줄을 지웠다)
    (re.compile(_NB + r"(?:96-(?:KO)?8210|VFVM-SM-\d+|NGC-ESM-\d+|LUBE-SM-\d+|KOSHA\s*[A-Z]-[A-Z]-\d+-\d+)\b[^,|.;\n]*"), ""),
    # 목록에 없던 원문 번호 (2026-10-11 원문 이름 고침 때 찾음): 매뉴얼 번호 "96-xxxx"(부품번호 93-xxxx와 다르다)와 서비스 알림 "SA0018"
    (re.compile(r"\(\s*" + _NB + r"96-[A-Z]{0,2}\d{4}[A-Z]?(?![0-9])[^)]*\)"), ""),   # "(96-8100 rev L, 1.8절 )" 괄호째
    (re.compile(_NB + r"96-[A-Z]{0,2}\d{4}[A-Z]?(?![0-9])"), _ref),
    (re.compile(r"\s*" + _NB + r"SA\d{4}(?![0-9])"), _ref),
    (re.compile(_NB + r"Rev\.?\s*[A-Z](?![A-Za-z0-9])(?!\.\d)"), _ref),
    # 쪽·행 번호. "1·3쪽"처럼 가운뎃점으로 이은 번호도 통째로 (2026-10-11: "3쪽"만 지워 "WSC 2001, 1·)"이 남았다)
    (re.compile(r"(?:CSV|PDF)\s*\d+(?:[~·]\d+)*\s*(?:행|쪽)"), ""),
    (re.compile(r"\d+(?:[~·]\d+)*행"), ""),
    (re.compile(r"(?:본문\s*)?\d+(?:[~·]\d+)*쪽"), ""),
    (re.compile(r"\(?" + _NB + r"B-M-\d+-\d{4}(?![0-9])\s*\)?"), _ref),     # KOSHA 지침 번호
    (SOURCE_PAREN, _source_paren),                                       # 앞 줄들이 번호를 지우고 남은 "(원문: )" 등
    # 닫는 괄호는 남긴다 (2026-10-11): "검색(haascnc.com/…)의"에서 ")의"까지 지워 "검색( 2025-01-30"이 남던 찌꺼기
    (re.compile(r"haascnc[^\s|)]*", re.I), ""),
    (re.compile(r"\s*알람 공식 페이지는\s*\."), ""),                       # 주소를 지우고 남은 빈 문장 (DOC-02 §4)
]

# 원문 문서 이름 (2026-10-11, 사용자 결정 "A만 바꿔 보이기" — research_notes/사내문서_Haas낱말_목록_20261011.md 3절 ①).
# Haas 원문 문서·목록·자료를 가리키는 말의 "Haas"만 "제조사"로 바꾼다. 머리 명사(목록·매뉴얼·자료…)는 남겨 조사가 그대로 맞는다.
# 설비·기능 이름(Haas VF-2·NGC·HCS-80·ATM·로고), 부품번호(Haas P/N …), 서비스 부서(Haas 서비스·HFO)는 그대로 둔다.
# 낱말 사이에 숫자·괄호·기호가 끼면(VF-2·P/N·서비스(HFO)) 이어 보지 않는다. 앞 경계는 영문자만 막는다 (root-cause-guards 8절).
_HB = r"(?<![A-Za-z])Haas"
_DOC_HEAD = r"(?:매뉴얼|설명서|목록|안내|절차|자료|웹\s*사이트|기준표|점검표|표본)"
HAAS_DOC = [
    (re.compile(r"\s*\(Haas[^)]*?(?:Electrical Safety|Troubleshooting|Manual|Guide)[^)]*\)"), ""),   # 괄호 속 영문 원문 이름: 지움
    (re.compile(_HB + r"\s+VMC Maintenance Schedule(?![A-Za-z])"), "제조사 정비 주기표"),              # 영문 고유 제목
    (re.compile(r"\(Mill Weekly Maintenance Checklist[^)]*\)"), ""),                                     # 한글 이름 뒤 영문 제목 괄호
    (re.compile(_HB + r"(\s+한국어\s+조작\s+매뉴얼)\(\d{4}\)\s*(?=,)"), r"제조사\1"),                  # 쪽을 지우고 남은 "(2015) ,"
    (re.compile(_HB + r"(?=\s+(?:[가-힣A-Za-z·]+\s+){0,3}?" + _DOC_HEAD + ")"), "제조사"),             # 알람 목록·매뉴얼·안내·자료…
    (re.compile(_HB + r"(?=는\s[^.\n|]*?라고\s*한다)"), "제조사"),                                    # "Haas는 …하라고 한다"
    (re.compile(r"(?<=\[실제\]\s)Haas(?=\s+알람)|" + _HB + r"(?=\s*\[실제\]\s*\|)"), "제조사"),        # 근거 꼬리표 "[실제] Haas 알람"·"Haas [실제] |"
    (re.compile(_HB + r"(?=\s+\d+분\s*대기)"), "제조사"),                                               # "Haas 5분 대기"
    (re.compile(_HB + r"(?=\s+기계의\s+안전\s+작동)"), "제조사"),                                     # 원문 참고값
    (re.compile(r"(?<=\[)Haas(?=\s+(?:알람|매뉴얼)\])"), "제조사"),                                    # 용어집 §1 근거 표시 "[Haas 알람]"
]

# "Haas" 낱말 없이 쓴 원문 이름 (2026-10-11 사용자 결정 "⑤ E5 전에 함께" — 사내문서_Haas낱말_목록_20261011.md 4.6절 ①).
# 매뉴얼 이름 + 장 번호, 판 연도, 영문 표·안내 이름을 "제조사 …"로 바꾼다. 머리 명사(매뉴얼·안내·표)는 남겨 문장이 이어진다.
# 용어집의 낱말 뜻("Troubleshooting Guide (TSG)")은 원문 이름이 아니라 그대로 둔다 — 그래서 "TSG"를 통째로 바꾸지 않는다.
SRC_NAME = [
    (re.compile(r"(?<![가-힣])조작 매뉴얼 본문\s*\([^)]*(?:한국어판|영문 \d{4}판)[^)]*\)"), "제조사 조작 매뉴얼 본문"),
    (re.compile(r"\(\s*,?\s*영문 \d{4}판\s*\)"), ""),                                  # 쪽을 지우고 남은 "설정 설명(, 영문 2025판 )"
    (re.compile(r"VF/VM 서비스 매뉴얼\s*\d+(?:\.\d+)*"), "제조사 서비스 매뉴얼"),
    (re.compile(r"(?<![0-9])(?:19|20)\d{2}년 서비스 매뉴얼(.{0,60}?)(?<![0-9])(?:19|20)\d{2}년 매뉴얼"),
     r"제조사 옛 서비스 매뉴얼\1그 뒤 판 매뉴얼"),                                                     # "2005년 … 2011년 매뉴얼" (판 연도)
    (re.compile(r"(?<![A-Za-z0-9])40T 주축 TSG(?![A-Za-z])"), "제조사 주축 고장 대응 안내"),
    (re.compile(r"\*\*\s*\(\d{4}-\d{2}\)\s*\*\*\s*Spindle Lubricants?(?![A-Za-z])"), "제조사 주축 윤활유 표"),
    (re.compile(r'\s*—\s*이하\s*"\s*n행"은\s*원문의\s*줄\s*번호\.'), "."),            # 줄 번호를 모두 지워 뜻이 없어진 안내
]

# 지운 뒤 남은 찌꺼기 (2026-10-11 같은 결정 — 출처는 아니고 깨진 문장 부호): 빈 자리 앞뒤의 쉼표·마침표
RESIDUE = [
    (re.compile(r"\(\s*,\s*"), "("),                             # "보고서(, 펌프 일련번호 필요)" → "보고서(펌프 …)"
    (re.compile(r"\s*[,·]\s*\)"), ")"),                          # "(starvation, )"·"5.1(2), )"·"WSC 2003, )" → ")"
    (re.compile(r":[ \t]*\.(?=[ \t]|$)", re.M), "."),            # "칸 설명: PDF 158쪽." → "칸 설명."
    (re.compile(r"(?<=\S)[ \t]+\.(?=[ \t]|$)", re.M), "."),      # "(흡입성) (2~3쪽)." → "(흡입성)."
    (re.compile(r",[ \t]*$", re.M), ""),                         # 줄 끝 번호를 지우고 남은 쉼표 ("제92조·제95조, KOSHA …")
]

# 화면·답에 남으면 안 되는 표지 (점검용). 뒤 경계는 숫자만 막는다 — "RD0080의"·"RD0080__RevB"도 잡는다 (2026-10-11)
# 96-8210만 보던 것을 매뉴얼 번호 96-xxxx 전체와 서비스 알림 SA0000으로 넓혔다 (2026-10-11 원문 이름 고침)
FORBIDDEN = re.compile(_NB + r"(?:TG\d{4}|RD\d{4}|AD\d{4}|ID\d{4}|96-(?:KO)?\d{4}|SA\d{4}|VFVM-SM|NGC-ESM|LUBE-SM)(?![0-9])"
                       r"|haascnc|https?://", re.I)


def _split(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def strip_tables(lines: list[str]) -> list[str]:
    out, header_drop = [], None
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            header_drop = None
            out.append(line)
            continue
        cells = _split(s)
        is_sep = all(set(c) <= set("-: ") for c in cells)
        if header_drop is None and not is_sep:
            header_drop = {i for i, c in enumerate(cells) if SOURCE_COLUMN.search(c) and i > 0}
        if not is_sep and cells and cells[0].replace("*", "") in DROP_ROW_FIRST_CELL:
            continue
        keep = [c for i, c in enumerate(cells) if i not in (header_drop or set())]
        out.append("| " + " | ".join(keep) + " |")
    return out


def sanitize(text: str) -> str:
    lines = strip_tables(text.splitlines())
    text = "\n".join(lines)
    text = SOURCE_LINE.sub("", text)
    for pat, rep in INLINE:
        text = pat.sub(rep, text)
    for pat, rep in HAAS_DOC:
        text = pat.sub(rep, text)
    for pat, rep in SRC_NAME:
        text = pat.sub(rep, text)
    # 번호를 "원문"으로 바꾼 자리의 조사를 받침에 맞춘다 ("RD0040 Rev H를" → "원문를" → "원문을")
    text = re.sub(r"원문(를|가|는|와|로)", lambda m: "원문" + {"를": "을", "가": "이", "는": "은", "와": "과", "로": "으로"}[m.group(1)], text)
    # 빈 괄호를 찌꺼기 정리 앞에서 지운다 (2026-10-11: 맨 끝에서 지우면 "(흡입성) () ." 자리의 " ."가 남았다)
    text = re.sub(r"\(\s*[,·]?\s*\)", "", text)
    for pat, rep in RESIDUE:
        text = pat.sub(rep, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
