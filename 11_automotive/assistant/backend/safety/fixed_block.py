"""채팅의 고정 서식 병기 (FIXED_BLOCK=1, A2b, 2026-10-18).

배경: 채팅에서 "잠금·표지·순서"를 물으면 Claude가 6+3단계를 자기 말로 풀어 썼고 프로그램이 붙이는 원문 블록이 없었으며 단계 번호도 1~6, 1~3으로 바뀌었다
(요구사항 FR-AST-COM-13 "고정 서식은 프로그램이 그대로 붙인다"와 어긋남). 사용자 결정(2026-10-18): 채팅 탭에서만 풀어 써도 되지만 **원문 블록을 병기**하고,
풀이가 단계를 빠뜨리거나 번호를 바꾸면 풀이를 버리고 원문 블록만 보인다.

이 모듈이 하는 일 (모두 코드 규칙이고 AI가 아니다):
 - select: 질문에 맞는 고정 서식 0~2개 (before6 · after3 · high_voltage · ppe)
 - reference_note: Claude에게 줄 공식 단계 번호·이름 (필터가 "원문 제목" 열을 지워 비서가 모르던 것)
 - blocks: 답 아래에 그대로 붙일 블록 (글자는 safety/templates.py 상수 = DOC-05 §7 블록)
 - wants_full / check_answer: 순서 **전체**를 물었는데 풀이가 단계(6.1~6.6·7.1~7.3)를 빠뜨리거나 없는 번호를 쓰면 이유를 돌려준다
"""
import re

from backend.safety import templates as T

KEYS = ("before6", "after3", "high_voltage", "ppe")
FALLBACK_LEAD = "순서는 아래 고정 서식 그대로예요."

_LOCK = re.compile(r"잠금|잠그|잠가|잠궈|잠글|표지|LOTO|로토|락아웃|lockout|자물쇠|태그|tagout|저장 ?에너지|차단 ?확인|운전 ?정지|6 ?단계|3 ?단계|[67]\.[1-6]", re.I)
_AFTER = re.compile(r"푸는|풀 ?때|풀고|풀어|풀기|풀 ?뒤|풀린|해제|제거|뗄|떼|뗀|떼는|작업 ?후|끝나고|끝난|다 ?하고 ?나서|3 ?단계|7\.[1-3]")
_BEFORE = re.compile(r"거는|걸어|걸고|걸 ?때|걸기|걸기 ?전|작업 ?전|정비 ?전|하기 ?전|들어가기 ?전|들어가기전|잠글|잠그는|잠가야|잠그고|설치|뭐부터|6 ?단계|6\.[1-6]|저장 ?에너지|차단 ?확인|운전 ?정지")
_BOTH = re.compile(r"푸는.{0,6}(?:까지|뒤까지)|걸고 ?(?:\S{0,4} )?푸|잠그고 ?푸|걸기 ?전부터|처음부터 ?끝|끝까지|모두|전체|둘 ?다|6 ?단계.{0,8}3 ?단계|잠금.{0,8}해제.{0,8}(?:모두|전체|다)|걸고 ?풀|잠금표지 ?걸기전부터")
_PROC = re.compile(r"순서|단계|절차|방법|어떻게|뭐부터|먼저|뭘 ?해|하는 ?법|거는|푸는|풀 ?때|걸 ?때|뭐 ?해|뭘 ?봐|뭘 ?확인|뭘로|누구|알려|확인")
# 고전압 서식: 낱말 하나만으로 붙이지 않는다 (2026-10-21 — "정비 몇 분 남았어"에 붙던 오탐, 질문 은행 62건 중 57건이 무관)
_HV_STRONG = re.compile(r"고전압|잔류 ?전압|전원.{0,8}(?:내린|끈|끄고|차단).{0,10}(?:기다|대기|뒤|후)|제어반.{0,10}(?:열기|열고|열 ?때|작업).{0,10}(?:기다|대기|몇 ?분)|표시등.{0,10}꺼.{0,12}(?:몇 ?분|5 ?분|기다|뒤|후|때까지)")
_HV_WEAK = re.compile(r"표시등|충전|잔류|기다려|5 ?분|몇 ?분")                  # 흔한 낱말 — 전기 낱말이 함께 있어야 한다
_HV_CTX = re.compile(r"전원|제어반|전압|전기|감전|방전|벡터|드라이브")
_HV_TIME_ONLY = re.compile(r"5 ?분|몇 ?분")
_HV_DURATION = re.compile(r"남았|남은|걸려|걸리|걸린|잡아|MTTR|MTBF|수리 ?시간", re.I)  # 시간만 있는 말에 이게 있으면 걸리는 시간·남은 시간 질문


def _wants_high_voltage(q: str) -> bool:
    if _HV_STRONG.search(q):
        return True
    if not _HV_CTX.search(q):
        return False
    hits = {m.group(0) for m in _HV_WEAK.finditer(q)}
    if not hits:
        return False
    if all(_HV_TIME_ONLY.fullmatch(h) for h in hits) and _HV_DURATION.search(q):
        return False
    return True
_PPE = re.compile(r"보호구|보안경|보안겅|안전화|장갑|귀마개|청력|방진|보호 ?안경|뭐 ?착용|착용해야|착용할|뭐 ?써야|뭐 ?껴|뭘 ?껴|뭘 ?써")
_PPE_WEAR = re.compile(r"착용|써야|써도|껴야|끼면|끼고|끼는|끼라|입어|신어|뭐 ?써|뭘 ?써|어떤|필수|금지|면장갑|써|껴|껴도|써야돼|어디서 ?써")
_NOT_PROC = re.compile(r"신청|지급|구매|청구|반납|재고|누구한테 ?신청|교체 ?주기|세탁")
_PARTIAL = re.compile(r"사람이 ?없|없는데|퇴근|검전|전화|누구|왜|언제|얼마|몇|이유|까닭|뭘 ?확인|뭐 ?확인|확인.{0,4}뭐|어디|뭘 ?봐|뭘 ?해|뭘로|뭐 ?해|에서 ?뭐|저장 ?에너지|차단 ?확인|운전 ?정지|[67]\.[1-6]")
_FULL = re.compile(r"순서|단계|절차|6 ?단계|3 ?단계|뭐부터|어떻게 ?(?:돼|되|해|하)")
_UNIT = r"(?:bar|psi|kPa|MPa|mm|cm|m\b|℃|°|분|초|시간|V\b|kV|A\b|kg|N\b|%|Hz|배|회|개|번)"
_CODE = re.compile(r"(?<![\d.])([67]\.\d)(?![\d.])(?!\s?" + _UNIT + ")")      # "6.9 bar"처럼 단위가 붙은 값은 단계 번호가 아니다


def select(question: str) -> list[str]:
    """질문에 붙일 고정 서식 키 (0~2개, 잠금 서식이 먼저)"""
    q = question
    out: list[str] = []
    if _LOCK.search(q) and (_PROC.search(q) or _AFTER.search(q) or _BEFORE.search(q)):
        after, before = bool(_AFTER.search(q)), bool(_BEFORE.search(q))
        if _BOTH.search(q) or (after and before and not _PARTIAL.search(q) and not re.search(r"작업 ?전|정비 ?전|하기 ?전|들어가기 ?전", q)):
            out = ["before6", "after3"]            # 걸고 푸는 것 모두 ("처음부터 끝까지", "잠금표지 순서"처럼 어느 쪽인지 안 가린 말)
        elif after and not before:
            out = ["after3"]
        elif before and not after:
            out = ["before6"]
        elif before and after:
            out = ["before6"]                       # "작업 전 …"처럼 시점이 앞이면 작업 전 서식 (푸는 말이 함께 있어도)
        else:
            out = ["before6", "after3"]             # 어느 쪽인지 모르는 순서 질문
    if len(out) < 2 and _wants_high_voltage(q) and not _NOT_PROC.search(q):
        out.append("high_voltage")
    if len(out) < 2 and _PPE.search(q) and _PPE_WEAR.search(q) and not _NOT_PROC.search(q):
        out.append("ppe")
    return out[:2]


def reference_note(keys: list[str]) -> str | None:
    """Claude에게 줄 공식 단계 번호·이름 (시스템 지시문 끝에 붙인다)"""
    if not keys:
        return None
    lines = ["[고정 서식] 아래는 안전 작업 기준서의 고정 서식이다. 프로그램이 답 아래에 이 서식을 그대로 붙인다. "
             "답에서 잠금·표지 단계를 말할 때는 번호와 이름을 아래 그대로 쓴다. 번호를 바꾸거나 새 번호를 만들거나 단계를 빼지 않는다."]
    if "before6" in keys:
        lines.append("작업 전 6단계: " + ", ".join(f"{c} {n}" for c, n in T.BEFORE))
    if "after3" in keys:
        lines.append("작업 후 3단계: " + ", ".join(f"{c} {n}" for c, n in T.AFTER))
    if "before6" in keys or "after3" in keys:   # 소제목에 문서에 없는 번호 범위("작업 전 (1~3단계)")를 지어내던 것 (2026-10-21)
        lines.append("묶음 소제목은 '작업 전 6단계'·'작업 후 3단계'처럼 쓰고, '1~3단계'·'4~6단계' 같은 새 번호 범위를 만들지 않는다. 단계를 가리킬 때는 위의 공식 번호(6.1~6.6·7.1~7.3)만 쓴다.")
    return "\n".join(lines)


def lines(keys: list[str]) -> list[str]:
    out: list[str] = []
    if "before6" in keys:
        out += ["작업 전 6단계 (잠금·표지를 거는 순서)"] + [f"{c} {n}" for c, n in T.BEFORE]
    if "after3" in keys:
        out += ["작업 후 3단계 (잠금·표지를 푸는 순서)"] + [f"{c} {n}" for c, n in T.AFTER]
    if "high_voltage" in keys:
        out += [T.HIGH_VOLTAGE_HEAD] + list(T.HIGH_VOLTAGE)
    if "ppe" in keys:
        out += ["보호구"] + list(T.PPE)
    if keys:
        out += [T.BASIS, T.SOURCE]
    return out


def blocks(keys: list[str]) -> list[dict]:
    """답 아래에 붙일 화면 블록 (소제목 + 줄들). 글자는 templates.py 상수 그대로 — AI가 쓰지 않는다"""
    if not keys:
        return []
    return [{"kind": "section", "text": T.TITLE}] + [{"kind": "line", "text": ln} for ln in lines(keys)]


def wants_full(question: str, keys: list[str]) -> bool:
    """순서 **전체**를 묻는 질문인가 (한 단계만 묻는 말이 있으면 아니다)"""
    return bool(("before6" in keys or "after3" in keys) and _FULL.search(question) and not _PARTIAL.search(question))


def expected_codes(keys: list[str]) -> list[str]:
    return ([c for c, _ in T.BEFORE] if "before6" in keys else []) + ([c for c, _ in T.AFTER] if "after3" in keys else [])


_RANGE = re.compile(r"(?<![\d.])\d+\s*~\s*\d+\s*단계(?![\d.])")      # "1~3단계"(점 없는 숫자 범위). "6.1~6.3"·"3단계"는 걸리지 않는다
_STEP_START = re.compile(r"(\d+\.\d+)\s")


def fix_titles(sections: list[dict]) -> list[tuple[str, str]]:
    """고정 서식 질문의 풀이에서 묶음 소제목에 지어낸 번호 범위("작업 전 (1~3단계)")가 있으면 고친다 — 그 묶음 항목이 모두 공식 단계 번호로 시작하면 범위를
    첫~끝 번호("작업 전 (6.1~6.3)")로 바꾸고, 아니면 범위만 지운다. 소제목만 바꾸고 본문은 그대로다. 바꾼 (옛 소제목, 새 소제목) 목록을 돌려준다."""
    changed: list[tuple[str, str]] = []
    for sec in sections:
        title = sec.get("title") or ""
        if not _RANGE.search(title):
            continue
        items = sec.get("items") or []
        codes = [m.group(1) for m in (_STEP_START.match(x) for x in items) if m]
        if codes and len(codes) == len(items):
            rng = codes[0] if len(codes) == 1 else f"{codes[0]}~{codes[-1]}"
            new = _RANGE.sub(rng, title, count=1)
        else:
            new = _RANGE.sub("", title, count=1)
        new = re.sub(r"\(\s*\)", "", new)
        new = re.sub(r"\s{2,}", " ", new).strip()
        if new and new != title:
            sec["title"] = new
            changed.append((title, new))
    return changed


def check_answer(text: str, keys: list[str], full: bool) -> str | None:
    """풀이(Claude가 쓴 글)가 고정 서식과 어긋나면 이유, 아니면 None.
    - 풀이에 쓴 단계 번호는 모두 공식 번호(6.1~6.6·7.1~7.3)여야 한다 (6.7·7.4 같은 없는 번호 금지)
    - 순서 전체를 물었으면 해당 단계 번호가 모두, 순서대로 나와야 한다 (부분열: 사이에 다른 번호·되풀이가 끼어도 공식 순서가 한 번 이어지면 통과)"""
    official = {c for c, _ in T.BEFORE} | {c for c, _ in T.AFTER}
    got = _CODE.findall(text or "")
    bad = [c for c in got if c not in official]
    if bad:
        return "없는 단계 번호: " + ", ".join(sorted(set(bad)))
    if full:
        want = expected_codes(keys)
        miss = [c for c in want if c not in got]
        if miss:
            return "빠진 단계: " + ", ".join(miss)
        it = iter(got)                                 # 공식 순서가 풀이 속에 "차례대로" 한 번 나오면 된다 — 머리말의 "6.1~6.6" 같은
        if not all(c in it for c in want):             # 범위 말이 먼저 나와도 되고, 본문이 뒤바뀌거나 단계가 빠지면 어긋난 것
            return "단계 순서가 다름"
    return None
