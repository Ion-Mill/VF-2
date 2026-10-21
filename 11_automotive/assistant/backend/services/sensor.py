"""센서 값 조회 질문 (2026-10-19, 기획 `센서조회_화면안내_기획_20261019.md` 3-1) — 질문 이해와 답 문장. 순수 함수 (DB·LLM·네트워크 없음).

OP-30 설비(VF2-01·VF2-02)의 센서 값은 팀 백엔드 조회 도구 `sensor_trend`가 준다 (공용 DB 시계 기준 최근 N분, 센서별 최소·평균·최대·마지막과 정상 범위 [참고]).
이 파일이 하는 일:
  · 질문이 "센서 값을 묻는 꼴"인가 (`is_value_question`) — 문서 질문(정상 범위·보관·간격·알람 기준값 …)은 아니다. parse()와 role_gate가 함께 쓴다.
  · 어느 설비·센서·기간인가 (`plan`) — 풀리지 않는 설비 ID 모양·센서 없는 설비·과거 기간은 값을 만들지 않고 안내만 한다.
  · 도구 결과로 답 문장 (`render`) — 판정 말("괜찮습니다·이상입니다")을 쓰지 않고, psi 옆 bar(소수 1자리)·정상 범위마다 [참고]·기준 시각(공용 DB 시계)을 반드시 적는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TOOL = "센서 추세 조회"                      # query_tools.sensor_trend 결과의 tool 이름
SOURCE = ("DOC-07", "3")                    # 출처: 설비 데이터·지표 정의서 §3 센서 (OP-30만)
SENSOR_EQUIPMENT = ("VF2-01", "VF2-02")     # 센서가 있는 설비 (OP-30)
DEFAULT_MINUTES, MAX_MINUTES = 60, 360
BAR_PER_PSI = 0.0689476
ORDER = ["SpindleLoadPct", "SpindleMotorTemp", "AirPressure", "Xload", "Yload", "Zload", "DcVolt"]     # 마스터(sensor_item) 순서
LOADS = ["SpindleLoadPct", "Xload", "Yload", "Zload"]
ONLY_OP30 = "센서는 OP-30 VF2-01·VF2-02만 기록해요"

# ---------------------------------------------------------------- 질문 이해
EQUIP_SHAPE = re.compile(r"(?<![A-Za-z0-9])(?:SAW|MIL|VF2|WSH|CMM)-\d+(?![A-Za-z0-9])", re.I)     # 설비 ID 모양 (VF2-03·VF2-1·VF2-001 포함)
BOTH_EQUIP = re.compile(r"VF2\s*(?:설비\s*)?(?:두\s*대|두대|둘|2\s*대|모두|전부|양쪽|전체)|(?:설비|기계|장비)?\s*(?:두\s*대|두대|두\s*설비|양쪽|둘\s*(?:다|중|모두|비교))", re.I)
# 공정 묶음 이름 (2026-10-19 2차): OP-30 = VF2-01·VF2-02 둘. 다른 공정(OP-10 절단·OP-20 황삭·OP-40 세척·OP-50 측정)은 센서가 없다. "정밀 가공 설비"처럼 공정 이름을 풀어 쓴 일반 명칭은 공정 언급으로 세지 않는다
PROCESS_CODE = re.compile(r"(?<![A-Za-z0-9])OP-?\s?(\d{2})(?![A-Za-z0-9])", re.I)
PROCESS_NAME = re.compile(r"(정밀\s*가공|절단|황삭|세척\s*[·ㆍ]?\s*디버링|세척|측정)\s*공정")
PROCESS_BY_NAME = {"정밀가공": "OP-30", "절단": "OP-10", "황삭": "OP-20", "세척디버링": "OP-40", "세척": "OP-40", "측정": "OP-50"}

NAMED = {  # 센서 이름 낱말 (현장 말 포함)
    "SpindleMotorTemp": re.compile(r"(?:주축|스핀들)\s*(?:모터\s*)?온도|모터\s*온도|모터온도"),
    "SpindleLoadPct": re.compile(r"(?:주축|스핀들)\s*부하|주축부하"),
    "AirPressure": re.compile(r"공기\s*압(?:력)?|공기압|에어\s*압(?:력)?|(?<![A-Za-z])psi(?![A-Za-z])", re.I),
    "DcVolt": re.compile(r"직류\s*(?:버스\s*)?전압|직류전압|버스\s*전압|(?<![고저])전압"),
}
AXES = re.compile(r"((?:[xyzXYZ]\s*(?:[,·ㆍ/&]|와|과|랑|하고)?\s*)+)\s*축\s*부하")
AXES_ALL = re.compile(r"(?<![주A-Za-z])(?:[세3]\s*)?축\s*부하")
GENERIC = {"온도": ["SpindleMotorTemp"], "압력": ["AirPressure"], "부하": LOADS}
GENERIC_RE = re.compile(r"온도|압력|부하")
# 다른 대상의 온도·압력·부하(절삭유 온도·윤활 압력·공구 부하 …)는 센서 7종의 일반 낱말로 세지 않는다
OTHER_THING = re.compile(r"(?:절삭유|냉각수|세척조|세척액|실내|외기|주변)\s*온도|(?:윤활|유압|펌프|토출|출구|에어건|그리퍼|절삭유|냉각수)\s*압력|(?:공구|펌프)\s*부하")
GENERIC_EQUIP = re.compile(r"(?:이|그|저|해당|우리)\s*(?:설비|기계|장비)|(?:정밀\s*)?가공\s*(?:설비|기계|장비)")     # 설비 ID 없는 일반 명칭 — 설비 언급으로 세지 않는다 (화면 설비 또는 되묻기)
SENSOR_WORD = re.compile(r"센서")
ALL_WORDS = re.compile(r"모든\s*센서|전체\s*센서|센서\s*(?:값\s*)?(?:전부|전체|모두|다\b)")

# 값이 아니라 문서·기준·사양·절차를 묻는 말 (이 말이 있으면 센서 값 질문이 아니다 — 기준값 낱말은 센서 intent에서 뺀다)
HARD_DOC = re.compile(
    r"기준(?!\s*시각)|보관|주기|간격|몇\s*(?:초|분|시간|일)\s*(?:마다|간격|단위)|며칠|얼마나\s*(?:오래|자주)|"
    r"뜻|의미|정의|뭐야|뭔가|뭐예요|무엇|뭘|무슨|어떤\s*(?:거|게|것|센서|종류|값)|종류|왜|어떻게|방법|절차|순서|"
    r"누가|언제부터|언제까지|어디(?:서|에서|를|로)|어디\s*(?:에\s*)?(?:있|설치|달|붙|위치|나와|나오|봐|보)|몇\s*(?:종|가지|번|회|건)|통계|엑셀|내려\s*받|다운로드|저장|출력|"
    r"알람|경보|트립|조치|대응|해결|수리|고치|넘으면|넘어가면|넘어서면|이상이면|이하면|아래면|밑이면|초과(?:하면|되면|시)|미만이면|"
    r"(?:떨어지|내려가|올라가|오르|높아지|낮아지|벗어나|모자라)(?:으)?면|"
    r"필요|요구|권장|사양|스펙|규격|정격|하한|상한|임계|설정|변경|교체|정비|점검\s*(?:순서|방법|주기)|잠금|차단|LOTO|안전|감전|보호구|작업\s*전|"
    r"(?:어야|아야|해야|야)\s*(?:돼|되|해|하|한다)|들어와야|기다|대기|빠질|전원|때까지|"
    r"가능|수\s*있|(?:기록|데이터|기능|화면|그래프|패널|센서)\s*(?:이|가|은|는|도)?\s*(?:따로\s*)?(?:있|없)", re.I)
# "최근 한 시간 기준으로"의 기준은 기간의 기준이지 알람 기준이 아니다 — 문서 낱말 검사 전에 뺀다
PERIOD_BASIS = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:분|시간)|(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|반)\s*시간(?:\s*반)?|하루|최근|지금|현재|오늘|요즘|방금)\s*기준(?:으로|이|에서|의)?")
# 사양·임계 값을 묻는 꼴 ("몇 psi 짜리", "몇 psi까지 괜찮아", "최소 몇 psi"): 값 단서가 있어도 센서 값 질문이 아니다 (문서 길). "최대가 얼마야/어디까지 올랐어"처럼 **잰 값의 극값**을 묻는 꼴은 값 질문 (MEASURED)
_U = r"(?:psi|bar|mpa|kpa|℃|°c|도(?![구어장착움전입])|%|퍼센트|볼트|v(?![a-z]))"
SPEC_Q = re.compile(
    rf"몇\s*{_U}\s*(?:짜리|이상|이하|미만|초과|아래|밑|넘|부터)|"
    rf"몇\s*{_U}\s*(?:까지)?\s*(?:로|는|은)?\s*(?:괜찮|돼|되|가능|허용|써|쓰|맞춰|맞추|설정|유지|필요|견|버티|측정|지원)|"
    r"(?:얼마|어디)\s*(?:까지|이하|이상|아래|밑)\s*(?:는|은)?\s*(?:괜찮|돼|되|가능|허용)|"
    r"까지\s*(?:는|은)?\s*(?:괜찮|돼|되|가능|허용|견)|"
    rf"(?:최소|최대|최저|최고|하한|상한)\s*(?:로\s*)?몇\s*{_U}", re.I)
MEASURED = re.compile(r"올랐|올라갔|떨어졌|내려갔|내렸|찍혔|찍었|나왔|튀었|높았|낮았|있었|갔|였|이었|됐|변했|변화|기록했|기록됐|나온|올라간|떨어진|내려간|찍은")
SOFT_DOC = re.compile(r"정상|범위|중앙값")                                   # 정상 범위를 묻는 말: 값을 함께 물을 때만 값 질문
LIVE_CUE = re.compile(r"값|수치|추세|얼마|몇\s*(?:도|%|퍼센트|psi|볼트)|어때|어떻|괜찮|높|낮|올랐|떨어|내렸|튀었|변화|확인|보여|봐\s*(?:줘|주|줄)|살펴|체크|알려|평균|최대|최소|최고|최저|제일|가장|마지막|최근|지금|현재|방금|요즘|"
                      r"\d+\s*(?:분|시간)|이상\s*(?:있|없)|문제\s*(?:없|있)|정상\s*(?:이야|이에요|인가|인지|이니|맞)|안\s*(?:이야|인가|이에요|에\s*있|인지)|밖|벗어|넘었|넘어")
STRICT_CUE = re.compile(r"추세|얼마|몇\s*(?:도|%|퍼센트|psi|볼트)|어때|어떻|괜찮|보여|봐\s*(?:줘|주|줄)|살펴|체크|알려|확인|평균|최대|최소|최고|최저|제일|가장|변화|마지막|최근|요즘|\d+\s*(?:분|시간)|이상\s*(?:있|없)|높|낮")
DOC_STYLE = re.compile(r"뭐|뭘|무슨|왜|어떻게|어떤|누가|언제|어디(?!\s*(?:까지|가))|있어|없어|있나|있는지|있습니까|할\s*수|하나요|인가요|입니까")   # 설비 없이 묻는 문서 질문 꼴


def process_groups(q: str) -> tuple[bool, list[str]]:
    """질문 속 공정 묶음 이름 → (OP-30을 말했나, 센서 없는 공정 코드 목록). 설비 ID를 따로 말했는지는 부른 쪽이 본다."""
    codes = [f"OP-{m.group(1)}" for m in PROCESS_CODE.finditer(q)]
    codes += [PROCESS_BY_NAME[re.sub(r"[\s·ㆍ]", "", m.group(1))] for m in PROCESS_NAME.finditer(q)]
    codes = list(dict.fromkeys(codes))
    return "OP-30" in codes, [c for c in codes if c != "OP-30"]


def has_equipment(q: str, resolved: list[str] | None = None) -> bool:
    return bool(resolved) or bool(EQUIP_SHAPE.search(q)) or bool(BOTH_EQUIP.search(q)) or bool(PROCESS_CODE.search(q)) or bool(PROCESS_NAME.search(q))


def is_value_question(q: str, resolved: list[str] | None = None) -> bool:
    """센서 값을 묻는 질문인가. resolved = parse()가 푼 설비 (별명 "1호기" 포함). 알람 번호·다른 운영 낱말은 부른 쪽(parse)이 먼저 거른다."""
    eq = has_equipment(q, resolved)
    q_generic = OTHER_THING.sub(" ", q)
    named = any(rx.search(q) for rx in NAMED.values()) or bool(AXES.search(q)) or bool(AXES_ALL.search(q))
    sensor_word = bool(SENSOR_WORD.search(q))
    if eq:
        # 온도·압력·부하 같은 일반 낱말만 있으면 센서 설비(VF2 계열)를 말했을 때만 값 질문이다 ("세척기 온도가 몇 도로 돼 있어?"는 문서 질문)
        vf2 = bool(re.search(r"VF2", q, re.I)) or any(e in SENSOR_EQUIPMENT for e in (resolved or [])) or process_groups(q)[0]
        if not (named or sensor_word or (vf2 and GENERIC_RE.search(q_generic))):
            return False
    elif not (named or sensor_word or (GENERIC_EQUIP.search(q) and GENERIC_RE.search(q_generic))):
        return False
    if HARD_DOC.search(PERIOD_BASIS.sub(" ", q)):
        return False
    if SPEC_Q.search(q) and not MEASURED.search(q):      # 사양·임계 값을 묻는 꼴 (…짜리·…까지 괜찮·최소 몇 …) — 잰 값의 극값("최대가 어디까지 올랐어")은 MEASURED라 값 질문
        return False
    if SOFT_DOC.search(q) and not (eq and LIVE_CUE.search(q)):
        return False
    if eq:
        return bool(named or sensor_word or LIVE_CUE.search(q))       # 설비 + 센서 이름이면 값 질문, 일반 낱말(온도·압력·부하)만 있으면 값 단서가 있어야
    return not DOC_STYLE.search(q) and bool(STRICT_CUE.search(q))


def pick_sensors(q: str) -> list[str] | None:
    """질문이 고른 센서 코드 (마스터 순서). None = 센서를 가리지 않음(전부)."""
    if ALL_WORDS.search(q):
        return None
    got: set[str] = set()
    for code, rx in NAMED.items():
        if rx.search(q):
            got.add(code)
    m = AXES.search(q)
    if m:
        got |= {f"{ch.upper()}load" for ch in re.findall(r"[xyzXYZ]", m.group(1))}
    if not m and AXES_ALL.search(q):
        got |= {"Xload", "Yload", "Zload"}
    if not got:
        q_generic = OTHER_THING.sub(" ", q)
        for word, codes in GENERIC.items():
            if word in q_generic:
                got |= set(codes)
    return [c for c in ORDER if c in got] if got else None


# ---------------------------------------------------------------- 기간
PAST_RE = re.compile(r"어제|어젯|그제|그저께|엊그제|지난\s*(?:주|달|교대|밤|번)|저번\s*(?:주|달)|이번\s*(?:주|달)|(?<!\d)\d{1,2}\s*월(?:\s*\d{1,2}\s*일)?|(?<!\d)\d{1,2}\s*/\s*\d{1,2}(?!\d)|"
                     r"야간|주간|새벽|아침|오전|오후|저녁|내일|모레|다음\s*(?:주|달)|(?<![\d.])\d{1,2}\s*시(?!\s*간)|"
                     r"(?:\d+|한|두|세|네|다섯|여섯)\s*(?:분|시간|일|주|개월|달)\s*전(?!\s*(?:부터|이후|동안))|며칠\s*전")      # "10분 전부터"는 최근 10분 창이라 과거가 아니다
KO_HOUR = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
HOUR_MIN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*시간(?:\s*(\d+)\s*분|\s*(반))?")
KO_HOUR_RE = re.compile(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*시간(\s*반)?|(반)\s*시간")
MIN_RE = re.compile(r"(?<![\d.])(\d+)\s*분")
SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
SINO_MIN_RE = re.compile(r"((?:[일이삼사오육칠팔구]?십)?[일이삼사오육칠팔구]?)\s*분")
LONG_RE = re.compile(r"(?<![\d.])(\d+)\s*일(?!\s*전)|하루|이틀|사흘|일주일|1\s*주일|한\s*주|반나절|종일|(?<![\d.])(\d+)\s*주(?!축)")


def _sino(s: str) -> int | None:
    if not s:
        return None
    n = 0
    if "십" in s:
        head, _, tail = s.partition("십")
        n += (SINO.get(head, 1) if head else 1) * 10
        s = tail
    return n + (SINO.get(s, 0) if s else 0) or None


def period(q: str) -> tuple[str, int | None, str]:
    """(종류, 분, 질문 속 기간 말). 종류 = default(말 없음→60분) | ok(1~360분) | past(과거·특정 시각·교대 — 조회 못 함) | over(360분 초과) | bad(1분 미만)."""
    q = re.sub(r"(?<![A-Za-z0-9])[A-Za-z]{2,3}\d?-\d+(?![A-Za-z0-9])", " ", q)       # 설비 ID(VF2-01 …)의 숫자를 기간으로 읽지 않는다
    m = PAST_RE.search(q)
    if m:
        return "past", None, m.group(0).strip()
    m = HOUR_MIN_RE.search(q)
    mins, phrase = None, ""
    if m:
        mins, phrase = round(float(m.group(1)) * 60) + int(m.group(2) or 0) + (30 if m.group(3) else 0), m.group(0).strip()
    elif (m := KO_HOUR_RE.search(q)):
        mins, phrase = (30 if m.group(3) else KO_HOUR[m.group(1)] * 60 + (30 if m.group(2) else 0)), m.group(0).strip()
    elif (m := MIN_RE.search(q)):
        mins, phrase = int(m.group(1)), m.group(0).strip()
    elif (m := SINO_MIN_RE.search(q)) and _sino(m.group(1)):
        mins, phrase = _sino(m.group(1)), m.group(0).strip()
    elif (m := LONG_RE.search(q)):
        return "over", None, m.group(0).strip()
    if mins is None:
        return "default", DEFAULT_MINUTES, ""
    if mins < 1:
        return "bad", None, phrase
    if mins > MAX_MINUTES:
        return "over", None, phrase
    return "ok", mins, phrase


# ---------------------------------------------------------------- 계획 (질문 → 설비·기간·센서·안내)
@dataclass
class Plan:
    equipment: list[str] = field(default_factory=list)      # 도구를 부를 설비 (센서가 있는 것만)
    minutes: int | None = None                              # None = 조회하지 않음 (기간을 지원하지 않음)
    sensor_code: str | None = None                          # 센서 하나를 골랐을 때만 (도구 인자)
    wanted: list[str] | None = None                         # 보일 센서 코드 (None = 도구가 준 전부)
    messages: list[str] = field(default_factory=list)       # 값 대신 알리는 안내
    ask: bool = False                                       # 설비를 몰라 되물어야 함
    compare: bool = False                                   # 두 설비를 견주는 질문 — 값을 나란히도 보인다


PAIR_SHORT = re.compile(r"(?<![A-Za-z0-9])VF2-0(\d)\s*(?:/|·|,|&|와|과|랑|이랑|하고|및)\s*0(\d)(?![\d-]|\s*(?:분|시간|일|%|psi|도))", re.I)      # "VF2-01/02", "VF2-01과 02": 뒤 번호도 설비 ID


def _ids(q: str, resolved: list[str]) -> tuple[list[str], list[str]]:
    mentions = [m.group(0).upper() for m in EQUIP_SHAPE.finditer(q)]
    mentions += [f"VF2-0{m.group(2)}" for m in PAIR_SHORT.finditer(q)]
    seen: dict[str, None] = {}
    for e in list(resolved or []) + mentions:
        seen[e] = None
    ids = list(seen)
    return [e for e in SENSOR_EQUIPMENT if e in ids], [e for e in ids if e not in SENSOR_EQUIPMENT]


COMPARE_RE = re.compile(r"비교|중에|보다|둘\s*중|어느\s*(?:쪽|설비)|어디가|더\s*(?:높|낮|크|작|많|적)|차이|나란히|대비|vs", re.I)


def plan(q: str, resolved: list[str], screen_equipment: str | None = None) -> Plan:
    """resolved = parse()가 푼 설비. 질문에 설비 ID 언급이 있으면 그것만 쓰고(풀리지 않는 ID도 화면 설비로 바꾸지 않는다), 전혀 없을 때만 화면에서 고른 설비를 쓴다."""
    p = Plan()
    ok_eq, bad_eq = _ids(q, resolved)
    op30, other_proc = process_groups(q)
    bad_eq += [c for c in other_proc if c not in bad_eq]
    mentioned = bool(ok_eq or bad_eq)
    if BOTH_EQUIP.search(q) or (op30 and not ok_eq):      # "VF2 두 대", "OP-30": 센서 있는 설비 둘 — 화면 설비 한 대로 줄이지 않는다 (VF2-01만 말했으면 그것만)
        ok_eq = list(SENSOR_EQUIPMENT) if not ok_eq or BOTH_EQUIP.search(q) else ok_eq
        mentioned = True
    if not mentioned and screen_equipment:
        scr = screen_equipment.strip().upper()
        if scr in SENSOR_EQUIPMENT:
            ok_eq = [scr]
        else:
            p.messages.append(f"화면에서 고른 설비({scr})는 센서 기록이 없어요. {ONLY_OP30}.")
    elif not mentioned:
        p.ask = True
    if bad_eq:
        p.messages.append(f"물으신 설비({', '.join(bad_eq)})는 센서 기록이 없어요. {ONLY_OP30}.")
    kind, mins, phrase = period(q)
    if kind in ("past", "over", "bad"):
        if kind == "past":
            p.messages.append(f"물으신 기간({phrase})은 조회할 수 없어요. 센서 조회는 공용 DB 시계 기준 최근 1~360분만 돼요 (예: 최근 120분).")
        elif kind == "over":
            p.messages.append(f"물으신 기간({phrase})은 한도를 넘어요. 센서 조회는 공용 DB 시계 기준 최근 1~360분(6시간)까지만 돼요 (예: 최근 120분).")
        else:
            p.messages.append(f"물으신 기간({phrase})은 조회할 수 없어요. 센서 조회는 공용 DB 시계 기준 최근 1~360분만 돼요 (예: 최근 120분).")
        p.ask = False
        return p
    p.compare = len(ok_eq) >= 2 and bool(COMPARE_RE.search(q))
    p.equipment, p.minutes = ok_eq, mins
    picked = pick_sensors(q)
    p.wanted = picked
    p.sensor_code = picked[0] if picked and len(picked) == 1 else None
    return p


# ---------------------------------------------------------------- 답 문장
def _num(x) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def bar(psi: float) -> str:
    return f"{round(psi * BAR_PER_PSI, 1):.1f}"


def _val(x: float, unit: str) -> str:
    if unit == "psi":
        return f"{fmt(x)} psi(약 {bar(x)} bar)"
    return f"{fmt(x)}{unit}" if unit in ("%", "℃") else f"{fmt(x)} {unit}"


def _range(lo: float | None, hi: float | None, unit: str) -> str | None:
    if lo is None or hi is None:
        return None
    if unit == "psi":
        return f"정상 범위 {fmt(lo)}~{fmt(hi)} psi(약 {bar(lo)}~{bar(hi)} bar) [참고]"
    tail = unit if unit in ("%", "℃") else f" {unit}"
    return f"정상 범위 {fmt(lo)}~{fmt(hi)}{tail} [참고]"


def _range_plain(lo: float | None, hi: float | None, unit: str) -> str:
    """참고 범위 글 ("참고 범위 28~42℃") — 비정상으로 판정한 줄에서만 쓴다. psi는 bar를 함께."""
    if unit == "psi":
        return f"참고 범위 {fmt(lo)}~{fmt(hi)} psi(약 {bar(lo)}~{bar(hi)} bar)"
    tail = unit if unit in ("%", "℃") else f" {unit}"
    return f"참고 범위 {fmt(lo)}~{fmt(hi)}{tail}"


def verdict(v: float | None, lo: float | None, hi: float | None, unit: str) -> tuple[str, str]:
    """지금 값 하나의 판정 (프로그램이 숫자로 비교, 경계는 범위 안). (줄 끝 글, 상태) — 상태는 normal / high / low / none.
    정상 범위는 선반 자료에서 빌린 참고 값이라 "정상 [참고]"처럼 참고 표시를 달고, 알람 판정이 아니다."""
    if v is None or lo is None or hi is None:
        return "판정 기준 없음", "none"
    if v > hi:
        return f"비정상(높음, {_range_plain(lo, hi, unit)}) [참고]", "high"
    if v < lo:
        return f"비정상(낮음, {_range_plain(lo, hi, unit)}) [참고]", "low"
    return "정상 [참고]", "normal"


def clock_text(r: dict) -> str:
    """기준 시각 문구. 도구가 준 기준 시각(공용 DB 시계)이 있으면 그것으로, 없으면 시각 없이 "기준 시각은 공용 DB 시계"만 (지어내지 않는다)."""
    t = r.get("as_of") if r.get("clock_known") else None
    if isinstance(t, str) and len(t) >= 16 and t[4] == "-" and t[10] in "T ":
        return f"{t[:10]} {t[11:16]} 기준, " + ("시연 화면 시계" if r.get("live") else "공용 DB 시계")
    return "기준 시각은 공용 DB 시계"


def _hhmm(t) -> str | None:
    return t[11:16] if isinstance(t, str) and len(t) >= 16 and t[10] in "T " else None


@dataclass
class Part:
    text: str                 # 설비 하나의 답 전체 (머리 + "- " 줄들 + 맺음)
    head: str = ""
    items: list[str] = field(default_factory=list)
    closing: str = ""


def render(eq: str, r: dict, wanted: list[str] | None = None) -> Part:
    """도구 결과(query_tools.sensor_trend) → 설비 하나의 답. 도구가 준 값만 쓰고(파생값은 bar·개수·시각뿐) 판정 말·"지금/현재"를 쓰지 않는다."""
    minutes = r.get("minutes")
    clock = clock_text(r)
    rows = [x for x in r.get("rows") or [] if x.get("equipment_id", eq) == eq]
    if wanted is not None:
        rows = [x for x in rows if x.get("sensor_code") in wanted]
    if not rows:
        t = f"{eq} 센서 기록 없음 ({clock} · 직전 {minutes}분). {ONLY_OP30}."
        return Part(text=t, head="", items=[], closing="")
    order = {c: i for i, c in enumerate(ORDER)}
    rows = sorted(rows, key=lambda x: order.get(x.get("sensor_code"), len(order)))
    if r.get("live"):      # SENSOR_LIVE: 시연 서버의 지금 값 하나씩 (최소·평균·최대가 따로 없다)
        items, out_of = [], []
        for x in rows:
            unit = x.get("unit") or ""
            v, lo, hi = _num(x.get("last_value")), _num(x.get("normal_min")), _num(x.get("normal_max"))
            name = x.get("sensor_name") or x.get("sensor_code")
            if v is None:
                items.append(f"{name}: 값 없음")
                continue
            tail, state = verdict(v, lo, hi, unit)
            items.append(f"{name}: {_val(v, unit)} — {tail}")
            if state in ("high", "low"):
                out_of.append(name)
        head = f"{eq} 센서 ({clock} · 지금 값)"
        closing = ("비정상으로 표시된 센서: " + (", ".join(out_of) if out_of else "없음")
                   + ". 참고 범위 기준 판정이며 알람 판정이 아니에요. 지난 시간의 변화(추세)는 공용 DB 시계가 시연 시계를 따라가지 않아 지금은 보여 드리지 못해요")
        return Part(text=head + "\n" + "\n".join("- " + it for it in items) + "\n" + closing, head=head, items=items, closing=closing)
    counts = {x.get("samples") for x in rows}
    lasts = {_hhmm(x.get("last_at")) for x in rows}
    shared_n = counts.pop() if len(counts) == 1 else None
    shared_last = lasts.pop() if len(lasts) == 1 else None
    head = f"{eq} 센서 ({clock} · 직전 {minutes}분"
    head += f" · 값 {shared_n}개" if shared_n is not None else ""
    head += f" · 마지막 값 시각 {shared_last}" if shared_last else ""
    head += ")"
    items, out_of = [], []
    for x in rows:
        unit = x.get("unit") or ""
        mn, av, mx, last = (_num(x.get(k)) for k in ("min_value", "avg_value", "max_value", "last_value"))
        lo, hi = _num(x.get("normal_min")), _num(x.get("normal_max"))
        parts = [f"{lab} {_val(v, unit)}" for lab, v in (("최소", mn), ("평균", av), ("최대", mx), ("마지막", last)) if v is not None]
        line = f"{x.get('sensor_name') or x.get('sensor_code')}: " + " · ".join(parts)
        if shared_n is None and x.get("samples") is not None:
            line += f" · 값 {x['samples']}개"
        if shared_last is None and _hhmm(x.get("last_at")):
            line += f" · 마지막 값 시각 {_hhmm(x['last_at'])}"
        rng = _range(lo, hi, unit)
        if rng:
            line += f" ({rng})"
        items.append(line)
        flag = x.get("is_out_of_normal")
        if flag is None and None not in (mn, mx, lo, hi):
            flag = mn < lo or mx > hi
        if flag:
            out_of.append(x.get("sensor_name") or x.get("sensor_code"))
    closing = "정상 범위 [참고] 밖 값이 있는 센서: " + (", ".join(out_of) if out_of else "없음")
    if wanted is not None:
        have = {x.get("sensor_code") for x in rows}
        gone = [c for c in wanted if c not in have]
        if gone:
            names = {c: n for c, n in (("SpindleLoadPct", "주축 부하"), ("SpindleMotorTemp", "주축 모터 온도"), ("AirPressure", "공기 압력"),
                                       ("Xload", "X축 부하"), ("Yload", "Y축 부하"), ("Zload", "Z축 부하"), ("DcVolt", "직류 버스 전압"))}
            closing += ". 기록이 없는 센서: " + ", ".join(names.get(c, c) for c in gone)
    text = head + "\n" + "\n".join("- " + it for it in items) + "\n" + closing
    return Part(text=text, head=head, items=items, closing=closing)


def compare_text(results: dict[str, dict], wanted: list[str] | None = None) -> str | None:
    """두 설비의 같은 센서를 한 줄에 나란히 (도구 값 그대로 — 어느 쪽이 낫다는 말은 하지 않는다). 둘 다 값이 있는 센서만."""
    eqs = [e for e in SENSOR_EQUIPMENT if e in results]
    if len(eqs) < 2:
        return None
    if all(results[e].get("live") for e in eqs):      # SENSOR_LIVE: 지금 값 한 줄씩
        by_live: dict[str, dict[str, dict]] = {}
        for e in eqs:
            for x in results[e].get("rows") or []:
                if x.get("equipment_id", e) == e and (wanted is None or x.get("sensor_code") in wanted):
                    by_live.setdefault(x.get("sensor_code"), {})[e] = x
        order_l = {c: i for i, c in enumerate(ORDER)}
        lines_l = []
        for code in sorted(by_live, key=lambda c: order_l.get(c, len(order_l))):
            got = by_live[code]
            vals = [(e, _num(got[e].get("last_value"))) for e in eqs if e in got]
            if len(vals) == len(eqs) and all(v is not None for _, v in vals):
                unit = got[eqs[0]].get("unit") or ""
                lines_l.append(f"{got[eqs[0]].get('sensor_name') or code} 비교 — 지금 " + " · ".join(f"{e} {_val(v, unit)}" for e, v in vals))
        return ("두 설비 나란히 보기 (지금 값)\n" + "\n".join(lines_l)) if lines_l else None
    by: dict[str, dict[str, dict]] = {}
    for e in eqs:
        for x in results[e].get("rows") or []:
            if x.get("equipment_id", e) == e and (wanted is None or x.get("sensor_code") in wanted):
                by.setdefault(x.get("sensor_code"), {})[e] = x
    order = {c: i for i, c in enumerate(ORDER)}
    lines = []
    for code in sorted(by, key=lambda c: order.get(c, len(order))):
        got = by[code]
        if len(got) < len(eqs):
            continue
        unit = got[eqs[0]].get("unit") or ""
        segs = []
        for lab, key in (("최소", "min_value"), ("평균", "avg_value"), ("최대", "max_value"), ("마지막", "last_value")):
            vals = [(e, _num(got[e].get(key))) for e in eqs]
            if all(v is not None for _, v in vals):
                segs.append(f"{lab} " + " · ".join(f"{e} {_val(v, unit)}" for e, v in vals))
        if segs:
            lines.append(f"{got[eqs[0]].get('sensor_name') or code} 비교 — " + " / ".join(segs))
    if not lines:
        return None
    return "두 설비 나란히 보기 (같은 기간)\n" + "\n".join(lines)
