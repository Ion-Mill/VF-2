"""MNT-01 질문 답변 (FR-MNT-01-01~12, ai-operations-assistant 규칙 3.2·3.5).

순서: 질문 구조화 → 알람 번호 정확 일치(DOC-02) → 문서 검색(사내 문서 + 용어집) / 조회 도구 → 찾은 것만으로 답.
출처는 사내 문서 이름·번호·§절만 쓴다(원문 출처 없음). 근거가 없으면 "문서에 없음".
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache

from backend.auth.permissions import PermissionDenied, require
from backend.config import DATA_LABEL, REFERENCE_AT, settings
from backend.llm import external as EXT
from backend.safety import fixed_block as FB
from backend.llm import jobs
from backend.llm import think as THINK
from backend.llm.adapter import FallbackAdapter, write_answer
from backend.llm.deadline import answer_deadline
from backend.rag.chunker import Chunk, load_corpus
from backend.rag.sanitize import FORBIDDEN
from backend.rag.dense import dense_last_error, dense_search, rrf
from backend.rag.search import search, synonyms, tokens
from backend.repositories.csv_repo import get_repo
from backend.services import blocks_v2 as BL2
from backend.services import followup_v2 as FU2
from backend.services import pure_external as PURE   # 순수 외부 LLM 연결 (2026-10-15, PURE_EXTERNAL — 시험용 복사본 전용)
from backend.services import steplog as SL
from backend.services.routing import DOC_WORDS, Route, decide_route
from backend.tools import query_tools as T

JOSA = ("에서는", "으로는", "이에요", "인가요", "에게", "에서", "으로", "이랑", "하고", "까지", "부터", "이야", "예요", "은", "는",
        "이", "가", "을", "를", "에", "의", "로", "와", "과", "도", "만", "랑", "야", "요")
ENDINGS = ("해야", "하는", "할때", "했어", "하나", "되나", "인가", "할", "해", "했", "돼", "되")
DEFINITION = re.compile(r"뭐야|뭔가|무엇|이란|란\?|기준|정의|계산식|어떻게 계산|어떻게 돼|순서|방법|어떻게 해|어떻게 처리|어떻게 점검"
                        r"|보관|몇 년|기간|누가 해|누가 떼|어떤 경우")
# 기준 질문 (2026-10-08 평가 근본 원인 분석): "2단계 기준"처럼 단계라는 낱말이 이름에 들어 있어도 절차가 아니라 조건·값을 묻는다
CRITERIA = re.compile(r"기준|조건|언제부터|언제 시작|몇 번이면|어떤 경우|몇 [년개일분번%]|얼마|몇 년")
FOCUS = [re.compile(r"(?:무엇을|뭘|뭐를)\s*([가-힣A-Za-z0-9]+)"), re.compile(r"([가-힣A-Za-z0-9]+)(?:은|는|이|가)\s*(?:뭐야|어떻게|언제|누가|얼마|몇)")]
UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:일|번|분|시간|개|%|년|℃|mm|psi|bar)")
CRITERIA_HEADER = re.compile(r"조건|언제|기준|판단|한도")
# 동사·형용사 꼴(연결·반말 어미)로 끝나는 낱말은 "문서에 없는 개념"으로 세지 않는다 (예: 껴도, 넘겨, 바뀔)
VERB_TAIL = ("도", "면", "게", "서", "고", "며", "지", "야", "요", "까", "니", "는", "은", "어", "아", "겨", "려", "워", "져", "쳐", "혀", "릴", "을", "할", "될")
QUESTION_WORDS = {"뭐야", "뭐", "무엇", "어떻게", "왜", "알려줘", "알려", "있어", "있나", "봐", "되나", "하나", "해", "돼", "재",
                  "뜨면", "떠", "가", "얼마", "몇", "어디", "언제", "누가", "인가", "건가", "할까", "하는", "해야", "되는", "좀",
                  "되면", "떴어", "뭐부터", "기다려"}


# ---------------------------------------------------------------- 단계별 로그 도우미 (STEP_LOG, 2026-10-15 — 읽기만 한다. 부르는 곳은 모두 `if SL.on():`로 감싼다)
def _sl_chunk(c) -> dict:
    """로그에 남길 조각 표지 (조각 번호·절 제목)."""
    return {"조각": c.chunk_id, "제목": c.title}


def _sl_lines(lines) -> list[str]:
    """보인 줄 목록을 앞 40자만 (후보·거르기 전후 기록용 — 고른 줄 전문은 최종 단계에 남는다)."""
    return [SL.cut(x) for x in lines]


def _sl_nums(lines) -> list[int | None]:
    """표 줄의 첫 칸 번호 ("2 — 할 일: …" → 2). 표 줄이 아니면 None — 절차 표 채우기 전후를 번호로 읽는 데 쓴다."""
    return [int(m.group(1)) if (m := re.match(r"^(\d+) — ", x)) else None for x in lines]


def content_words(question: str) -> list[str]:
    """질문의 핵심 낱말 (조사·의문 낱말을 뗀 것). 근거 조각과의 겹침을 재는 데 쓴다.
    6차(PARSE_V7): 답 모양 낱말(쉽게·설명해·요약해 …)은 다른 내용 낱말이 남을 때만 뺀다 — "쉽게 설명"이 DOC-02 칸 이름
    "쉬운 설명"에 걸려 겹침 검사를 통과했다 (2026-10-12 사용자 테스트)."""
    # "6단계"처럼 숫자+한글은 한 낱말로 둔다 (절 제목 "작업 전 6단계"와 맞추기 위해)
    tokens = re.findall(r"\d+[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", question.lower())
    if v10_on():   # 9차 (1부 원인 H): "매니폴드가뭐야"처럼 붙여 쓴 묻는 말을 뗀다
        tokens = [t for w in tokens for t in split_glued_v10(w)]
    out = _content_of(tokens)
    if out and v7_on():
        trimmed = _content_of([w for w in tokens if not SHAPE_TOKEN_V7.fullmatch(w)])
        if trimmed:
            return trimmed
    return out


# 9차 PARSE_V10 (1부 원인 H, 2026-10-13 사용자 화면 대화): 빈칸 없이 붙여 쓴 묻는 말. 사내 문서에 없는 한글 낱말 안에서만 찾는다
QWORD_GLUE_V10 = re.compile(r"뭐예요|뭐에요|뭐야|뭐지|뭔지|뭔가|뭐임|무엇|무슨|언제|어떻게|어디|얼마|몇|누가|누구|왜")


def _in_corpus_v10(w: str) -> bool:
    return any(w in v for v in corpus_words())


def split_glued_v10(w: str) -> list[str]:
    """붙여 쓴 묻는 말 앞에서 낱말을 나눈다: "매니폴드가뭐야" → ["매니폴드가"], "그리스를언제쓰나" → ["그리스를"].
    나누는 것은 (1) 한글 4글자 이상이고 (2) 낱말 전체(조사를 뗀 것)가 사내 문서에 없고 (3) 묻는 말 앞 조각(조사를 뗀 것)이
    사내 문서 낱말일 때만이다 — 사내 문서에 있는 낱말("어디서나" 같은 것)은 건드리지 않는다. 묻는 말은 버린다(어차피 핵심 낱말이 아님).
    묻는 말 뒤 글은 같은 규칙으로 다시 보고, 그중 사내 문서 낱말(조사를 뗀 것)만 남긴다 — 뒤 글은 대개 동사 꼬리("쓰나·마다발라야해")다.
    홀로 선 묻는 말("무슨"·"몇번")은 건드리지 않는다 — 처음 판은 이것도 버렸다가, 사내 문서에 없는 "무슨"이 막아 주던 답 없는 질문
    ("LOTO 자물쇠는 무슨 색…", "무슨 품번…")에 답하게 되어 뺐다 (LLM 끈 비교 2026-10-13, 거부 묶음 지어낸 답 +4)."""
    if not re.fullmatch(r"[가-힣]{4,}", w):
        return [w]
    whole = _content_of([w])
    if not whole or _in_corpus_v10(whole[0]):
        return [w]
    for m in QWORD_GLUE_V10.finditer(w):
        if m.start() < 2:
            continue
        left = w[: m.start()]
        stem = _content_of([left])
        if not stem or not _in_corpus_v10(stem[0]):
            continue
        rest = split_glued_v10(w[m.end():]) if len(w) - m.end() >= 3 else []   # 2글자 이하("쓰나·해")는 동사 꼬리
        return [left] + [t for t in rest if (c := _content_of([t])) and _in_corpus_v10(c[0])]
    return [w]


def _content_of(tokens: list[str]) -> list[str]:
    out = []
    for w in tokens:
        if w in QUESTION_WORDS:
            continue
        for _ in range(2):  # "기준이야" → "기준이" → "기준"
            before = w
            for e in ENDINGS + JOSA:  # "시작할" → "시작", "점검해" → "점검"
                if len(w) > len(e) + 1 and w.endswith(e):
                    w = w[: -len(e)]
                    break
            if w == before:
                break
        if len(w) >= 2 and w not in QUESTION_WORDS:
            out.append(w)
    return sorted(set(out))


REF_DATE = date.fromisoformat(REFERENCE_AT[:10])
MIN_SCORE = 5.0          # BM25 점수 하한 [가상: 2026-10-07 평가 세트 48문항으로 맞춘 값]
MIN_OVERLAP = 0.4        # 질문 핵심 낱말 중 근거 조각에 들어 있어야 하는 비율 [가상: "문서에 없음" 문항 최대 0.33, 문서 문항 최소 0.4]
EQUIP_RE = re.compile(r"\b(VF2-0[12]|SAW-01|MIL-01|WSH-01|CMM-01)\b", re.I)
# 4차 (PARSE_V5, L6): 파이썬 re에서 한글은 \w라 "VF2-01은"의 \b가 맞지 않는다 — 영숫자 경계로 본다 ("VF2-011"은 아님)
EQUIP_RE_V5 = re.compile(r"(?<![A-Za-z0-9])(VF2-0[12]|SAW-01|MIL-01|WSH-01|CMM-01)(?![A-Za-z0-9])", re.I)
SAFETY_WORDS = ("잠금", "표지", "고전압", "전기", "저항", "차단", "LOTO", "케이블", "앰프")
DEFECT_CAUSE = re.compile(r"불량.*(원인|왜)|왜.*불량")

OPS_INTENTS = [
    ("stops", ("멈췄", "멈춘", "정지", "섰", "고장 났")),
    ("production", ("실적", "생산", "몇 개", "만들었")),
    ("inventory", ("재고", "부족", "남았")),
    ("tool_life", ("공구 수명", "공구 교체", "수명")),
    ("kpi", ("가동률", "oee", "성능", "양품률", "mttr", "mtbf", "설비종합효율")),
    ("lots", ("로트",)),
    ("work_orders", ("작업지시",)),
    ("pm_due", ("예방 정비", "정비 기한", "기한")),
    ("work_records", ("작업기록", "조치 기록", "지난 조치", "어떻게 고쳤")),
    ("alarm_count", ("몇 번", "자주", "왜 자꾸", "또 떠", "또 떴")),
    ("equipment_status", ("지금 상태", "상태 어때", "돌아가")),
]
# 규칙 보강 (PARSE_V2=1, 2026-10-10 계획 3단계 A). 조정 세트 F·qa_route에서 찾은 낱말 오분류를 고친다:
# "몇 개월" → 생산, "연차 며칠 남았는지" → 재고, "돌아가는 기계" → 설비 상태, "몇 번 멈췄어" → 알람 횟수(알람 없음)
OPS_INTENTS_V2 = [
    ("stops", re.compile(r"멈췄|멈춘|정지|섰|서\s*있었|멈춰\s*있었|고장\s*났")),
    ("production", re.compile(r"실적|생산|만들었|몇\s*개\s*(?:만들|나왔|했)")),
    ("inventory", re.compile(r"재고|부족|모자라|모자란|(?:소모품|윤활유|절삭유|그리스|원액|필터|원자재|공구|탭|엔드밀|드릴)\S*\s*(?:얼마나\s*)?남았")),
    ("tool_life", re.compile(r"공구\s*수명|공구\s*교체|수명|(?:갈아|바꿔|교체해)\S*\s*(?:할|하는|될)?\s*공구")),
    ("kpi", re.compile(r"가동률|oee|성능|양품률|mttr|mtbf|설비종합효율|평균\s*수리|수리\s*시간|고장\s*간격|평균.*(?:고치|고쳐)")),
    ("lots", re.compile(r"로트")),
    ("work_orders", re.compile(r"작업지시")),
    ("pm_due", re.compile(r"예방\s*정비|정비\s*기한|기한")),
    ("work_records", re.compile(r"작업기록|조치\s*기록|지난\s*조치|어떻게\s*고쳤")),
    ("alarm_count", re.compile(r"(?:알람|경보)\S*\s*(?:몇\s*번|자주)|몇\s*번\s*(?:났|떴|울렸|발생)|자주\s*(?:나|떠|뜨)|왜\s*자꾸|또\s*떠|또\s*떴")),
    ("equipment_status", re.compile(r"지금\s*상태|상태\s*어때|돌아가(?:\?|$|요|나|니|고\s*있|는지)|가동\s*중|멈춰\s*있(?!었)")),
]
NIGHT_V2 = re.compile(r"야간|간밤|어젯밤|밤|새벽")
DAY_V2 = re.compile(r"주간|낮(?!음|은|춰|추|아|게|다|으)")
YESTERDAY_V2 = re.compile(r"어제|어젯|간밤|전날")
EQUIP_ALIAS_V2 = [(re.compile(r"1\s*호기|일호기|1번\s*(?:기계|설비)"), "VF2-01"), (re.compile(r"2\s*호기|이호기|2번\s*(?:기계|설비)"), "VF2-02")]
RECENT_WEEK_V2 = re.compile(r"(?:최근|지난)\s*(?:일주일|1주일|한\s*주)|일주일\s*(?:동안|간)")
RECENT_MONTH_V2 = re.compile(r"(?:최근|지난)\s*(?:한\s*달|30일)|지난\s*달|지난달")
# 규칙 보강 2차 (PARSE_V3=1, 2026-10-10 2차 계획 — research_notes/로컬 LLM 연결/남은문제_업계해법_조사_20261010.md).
# 봉인 시험 E에서 step4가 틀린 원인: 날짜만 있는 말·상대 날짜, 붙은 말 오분류, 두 가지를 같이 묻는 질문, 조작 요청 꼴, 알람의 없는 세부.
OPS_INTENTS_V3 = [
    ("stops", re.compile(r"멈[췄췃쳤]|멈춘|정지|섰|섯|서\s*있었|멈춰\s*있었|고장\s*났")),  # 오타("멈췃", "섯")도
    ("production", re.compile(r"실적|생산|만들었|뽑았|몇\s*개\s*(?:만들|나왔|했|뽑)")),
    ("inventory", re.compile(r"재고|부족|모자라|모자란|(?:소모품|윤활유|절삭유|그리스|원액|필터|원자재|공구|탭|엔드밀|드릴)\S*\s*(?:얼마나\s*)?남았")),
    ("tool_life", re.compile(r"공구\s*수명|공구\s*교체|수명|(?:갈아|바꿔|교체해)\S*\s*(?:할|하는|될)?\s*공구|(?:갈|바꿀|교체할)\s*때\s*(?:가\s*)?된\s*공구")),
    ("kpi", re.compile(r"가동률|oee|성능|양품률|mttr|mtbf|설비종합효율|평균\s*수리|수리\s*시간|고장\s*간격|평균.*(?:고치|고쳐)")),
    ("lots", re.compile(r"로트|lot-\d{4}")),
    ("work_orders", re.compile(r"작업지시")),
    ("pm_due", re.compile(r"예방\s*정비|정비\s*기한|기한")),
    ("work_records", re.compile(r"작업기록|조치\s*기록|지난\s*조치|어떻게\s*고쳤")),
    ("alarm_count", re.compile(r"(?:알람|경보)\S*\s*(?:몇\s*번|자주)|몇\s*번\s*(?:이나\s*)?(?:났|떴|울렸|발생)|자주\s*(?:나|떠|뜨)|왜\s*자꾸|또\s*떠|또\s*떴")),
    ("equipment_status", re.compile(r"지금\s*상태|상태\s*어때|돌아가(?:\?|$|요|나|니|고\s*있|는지)|가동\s*중|멈춰\s*있(?!었)")),
]
# 사내 문서의 복합어 가운데 의도 낱말("정지")이 든 것 — 의도를 볼 때 이 글자 범위를 뺀다 (긴 것 우선, spaCy EntityRuler 방식)
COMPOUND_MASK_V3 = re.compile(r"통과\s*·?\s*정지\s*게이지|정지\s*게이지|비상\s*정지|과열\s*정지|정지\s*등급")
# 설비·날짜·로트가 없는데 규칙·기준을 묻는 꼴 → 문서 질문 (DEFINITION에 더함)
# 용어의 이름·뜻을 묻는 꼴("MTBF 우리말로 뭐라고 해")도 문서(용어집) 질문이다 — 규칙이 kpi로 잘못 힌트를 주던 것 (2026-10-10 E001)
DEF_EXTRA_V3 = re.compile(r"언제|어디|몇\s*도|몇\s*%|몇\s*퍼센트|몇\s*바퀴|몇\s*(?:번|회)\s*(?:이면|나면|넘으면)"
                          r"|몇\s*(?:분|개|시간)\s*(?:넘|밑|이상|이하|아래|부터|까지)|잡혀|정해져"
                          r"|뭐라고\s*(?:해|하|불러|부르|적|써|읽|말)|우리말|한국말|영어로|약자|줄임말|무슨\s*뜻|뜻이|뜻은|뜻을|표준어")
# 운영 질문에 붙은 설명 요청 (섞인 질문 → 문서도 찾는다)
DOC_CUE_V3 = re.compile(r"왜|어떻게|방법|순서|기준|정의|범위|누가|누구|언제|어디|몇\s*(?:번|회)\s*(?:이면|나면|넘으면|이상)"
                        r"|몇\s*(?:분|%|퍼센트|개|시간|도|일)\s*(?:넘|밑|이상|이하|아래|부터|까지|로|이면)|잡혀|잡히|정해|주의\s*(?:떠|로|가)|알림은")
# 섞인 질문의 문서 쪽 문장에 붙일 운영 낱말 (대명사 "그거"를 바꿀 때)
OPS_NOUNS_V3 = re.compile(r"OEE|MTTR|MTBF|가동률|양품률|실적|목표|재고|공구\s*수명|공구|작업지시서|작업지시|예방\s*정비|필수\s*정지|정지|반복\s*알람|알람|로트", re.I)
PRONOUN_V3 = re.compile(r"^(?:그거|그건|그게|이거|이건|그것|이것|그)\s*")
# 날짜 (과거 우선 — 운영 기록 조회이므로. Amazon Lex AMAZON.Date의 "미래 우선"과 반대인 이유)
DAY_BEFORE_YESTERDAY_V3 = re.compile(r"그저께|그제(?=\s|$|[?,.]|에|는|도|밤|낮|주간|야간)")
DAYS_AGO_V3 = re.compile(r"(?<!\d)(\d{1,2})\s*일\s*전")
DAY_ONLY_V3 = re.compile(r"(?<![\d.\-/월])(?<!최근\s)(?<!지난\s)(\d{1,2})\s*일"
                         r"(?!\s*(?:전|후|동안|간|째|치|분|마다|이내|넘|이상|이하|안|씩|기준|평균|단위|창|정도|쯤|만에|만|요일))")
LAST_WEEK_V3 = re.compile(r"(?:지난|저번)\s*주(?!일|간)")   # "지난 주간"(지난 낮 교대)은 아님
THIS_WEEK_V3 = re.compile(r"이번\s*주(?!일|간)")
WEEKDAY_V3 = re.compile(r"(?:지난\s*|저번\s*)?([월화수목금토일])요일")
WEEKDAY_NO = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
# 알람 질문의 없는 세부 (값 종류 검사, SMART·SQuAD 2.0 방식). (이름, 질문 꼴(기준 낱말 잡기), 값 꼴)
# 값은 질문의 기준 낱말과 같은 조각(" / "·"|"로 나눈 칸) 안에 있어야 한다 — 같은 줄의 다른 항목 값(예: 임펠러 부품번호)을 잘못 쓰지 않게
ALARM_DETAIL_V3 = [
    ("부품번호", re.compile(r"([A-Za-z0-9가-힣]+)\s*(?:의\s*)?(?:부품\s*번호|품번|P/?N|파트\s*넘버)", re.I), re.compile(r"(?<![\d-])\d{2,3}-\d{3,5}(?![\d-])")),
    ("설정 기본값", re.compile(r"((?:Setting|설정|세팅)\s*\d+|[A-Za-z0-9가-힣]+)\s*(?:의\s*)?(?:기본\s*값|기본값|초기값|초깃값)", re.I), re.compile(r"기본\s*값|기본값|초기값|초깃값|default", re.I)),
    ("시간", re.compile(r"몇\s*(?:분|초|시간)\s*(?:동안\s*|정도\s*)?([가-힣]{2,})"), re.compile(r"\d+\s*(?:분|초|시간)")),
    ("금액", re.compile(r"([가-힣A-Za-z0-9]+)\s*(?:의\s*)?(?:가격|비용|금액|값)"), re.compile(r"\d[\d,]*\s*(?:원|만\s*원|달러|USD|\$)")),
]


EQUIP_ALIAS_V3 = [(re.compile(r"세척기"), "WSH-01"), (re.compile(r"3차원\s*측정기|측정기"), "CMM-01"),
                  (re.compile(r"절단기"), "SAW-01"), (re.compile(r"황삭기"), "MIL-01")]
BOTH_SHIFTS_V3 = re.compile(r"주\s*야간|주·야|낮\s*밤|하루\s*종일|통틀어|종일")


def resolve_dates_v3(q: str, intents: list[str], start, end):
    """날짜만 있는 말·상대 날짜를 기준일(REF_DATE) 앞의 날짜로 바꾼다. 이미 정한 날짜가 있으면 그대로 둔다."""
    if start is not None:
        return start, end
    y = REF_DATE - timedelta(days=1)
    if DAY_BEFORE_YESTERDAY_V3.search(q):
        d = REF_DATE - timedelta(days=2)
        return d, d
    m = DAYS_AGO_V3.search(q)
    if m:
        d = REF_DATE - timedelta(days=int(m.group(1)))
        return d, d
    if LAST_WEEK_V3.search(q):  # 지난주 = 지난 월요일 ~ 일요일
        mon = REF_DATE - timedelta(days=REF_DATE.weekday() + 7)
        return mon, mon + timedelta(days=6)
    if THIS_WEEK_V3.search(q):  # 이번 주 = 이번 월요일 ~ 어제
        mon = REF_DATE - timedelta(days=REF_DATE.weekday())
        return (mon, y) if mon <= y else (None, None)
    m = WEEKDAY_V3.search(q)
    if m and intents:
        back = (REF_DATE.weekday() - WEEKDAY_NO[m.group(1)]) % 7 or 7
        d = REF_DATE - timedelta(days=back)
        return d, d
    m = DAY_ONLY_V3.search(q)
    if m and intents:  # 운영 질문일 때만 — "7일 안에 3번"처럼 기간을 뜻하는 말을 날짜로 읽지 않게
        n = int(m.group(1))
        d = y
        for _ in range(62):  # 기준일 앞에서 가장 가까운 n일 (과거 우선)
            if d.day == n:
                return d, d
            d -= timedelta(days=1)
    return None, None


def _segments(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        for cell in line.split("|"):
            out += [s for s in re.split(r"\s/\s", cell) if s.strip()]
    return out


def alarm_detail_missing(question: str, texts: list[str], v5: bool = False) -> tuple[str, str] | None:
    """알람 질문이 묻는 세부 값(부품번호·기본값·시간·금액)이 그 알람의 사내 문서 칸에 없으면 (이름, 기준 낱말).
    v5: 금액 꼴에서 맨 "값"을 뺀다 (PARSE_V5, ALARM_DETAIL_V5)."""
    segs = [s for t in texts for s in _segments(t)]
    for name, cue, want in (ALARM_DETAIL_V5 if v5 else ALARM_DETAIL_V3):
        m = cue.search(question)
        if not m:
            continue
        anchor = m.group(1)
        stem = anchor if re.match(r"[A-Za-z0-9]", anchor) else anchor[:2]
        codes = re.findall(r"[A-Z]{1,4}\d+", question)  # CB3 같은 부품 기호도 기준 낱말로
        keys = [stem] + [c for c in codes if c not in stem]
        if not any(any(k and k.lower() in s.lower() for k in keys) and want.search(s) for s in segs):
            return name, anchor
    return None


def doc_question_v3(question: str) -> str:
    """두 문장 질문에서 문서 쪽(설명 요청) 문장을 고르고, 대명사는 앞 문장의 운영 낱말로 바꾼다. 못 고르면 원래 질문."""
    sents = [x.strip() for x in re.split(r"(?<=[?？.!])\s+", question.strip()) if x.strip()]
    if len(sents) < 2:
        return question
    cue = [x for x in sents if DOC_CUE_V3.search(x) or any(w in x for w in DOC_WORDS)]
    if not cue:
        return question
    d = cue[-1]
    others = " ".join(x for x in sents if x is not d)
    nouns = list(dict.fromkeys(m.group(0) for m in OPS_NOUNS_V3.finditer(others)))
    d2 = PRONOUN_V3.sub("", d)
    if d2 != d or not OPS_NOUNS_V3.search(d):
        d2 = (" ".join(nouns) + " " + d2).strip()
    return d2 if len(d2) >= 12 else question  # 너무 짧으면("어디어디 잠가?") 원래 질문으로 찾는다


# ---------------------------------------------------------------- 규칙 보강 3차 (PARSE_V4=1, PARSE_V2·V3 위에서만 동작)
# 봉인 시험 E2를 공개한 뒤 찾은 원인 (research_notes/로컬 LLM 연결/앞단개선3_사전등록_20261010.md 3절 a~g).
# d 알람 횟수: "몇 번씩·몇 번 정도 떴는지"도 알람 횟수. "뜨면"은 기준 질문이라 넣지 않는다(DEF_EXTRA_V4가 문서로 보냄)
OPS_INTENTS_V4 = [(n, re.compile(r"(?:알람|경보)\S*\s*(?:몇\s*번|자주)|몇\s*번\s*(?:이나\s*|씩\s*|정도\s*)?(?:났|떴|떠(?=요|\?|\s|$)|울렸|발생)"
                                 r"|자주\s*(?:나|떠|뜨)|왜\s*자꾸|또\s*떠|또\s*떴")) if n == "alarm_count" else (n, rx)
                  for n, rx in OPS_INTENTS_V3]
_CRIT_V4 = r"|몇\s*(?:번|회)\s*(?:씩\s*|정도\s*)?(?:이면|나면|넘으면|뜨면|떠야|나야|울리면)"
DEF_EXTRA_V4 = re.compile(DEF_EXTRA_V3.pattern + _CRIT_V4)
DOC_CUE_V4 = re.compile(DOC_CUE_V3.pattern + _CRIT_V4)
# c 대명사: 홀로 쓴 "그·이"는 뒤가 빈칸일 때만 ("그런"의 "그", "그래서", "그날"을 자르지 않게 — E2-059 "런 공구는…").
# "그런·이런 N"은 앞 문장에서 N으로 끝나는 말로 바꾼다 ("수명 90% 넘은 공구는 언제…")
PRONOUN_V4 = re.compile(r"^(그거를|그것은|그것이|그것을|그거|그건|그게|그걸|그것|이거를|이것은|이것이|이것을|이거|이건|이게|이걸|이것"
                        r"|그런|이런|저런|그|이)(?=\s|$)\s*")
DETERMINER_V4 = {"그런", "이런", "저런"}   # "그·이 + 명사"는 대명사처럼 (앞 문장의 운영 낱말만 붙임, E2-058 "그 부족 알림은" → "재고 부족 알림은")
# a 날짜: 지난주·지지난주·이번 주 + 요일 = 그날, 요일 여럿 = 처음~끝, 기준 시각 뒤 = 확인 필요 (한 달 전체로 넓히지 않음)
TWO_WEEKS_AGO_V4 = re.compile(r"지지난\s*주(?!일|간)")
FUTURE_V4 = re.compile(r"다음\s*주(?!일|간)|내일|모레|다음\s*달")
WEEKDAYS_V4 = re.compile(r"([월화수목금토일])요일")
# g 가정 질문: "36개짜리 로트면 … 몇 개" — 운영 조회가 아니라 문서의 기준을 묻는다
HYPO_V4 = re.compile(r"(?<![\d.])\d+\s*개\s*짜리|(?<![\d.])\d+\s*(?:개|대|명)\s*(?:면|이면|라면)(?=\s)")
# e 업무 밖 부탁: 거절이 기본이다. 추천·소개 부탁이고 업무 대상이 없을 때만 일반 흐름으로 (→ 문서에 없음, E2-090 "고깃집 추천해줘")
LEISURE_REQ_V4 = re.compile(r"추천해|추천\s*좀|추천\s*부탁|골라\s*(?:줘|주세요)|소개해|알아봐\s*(?:줘|주세요)")
# f 알람 기준값: 트립 값(넘으면·밑이면·되면 뜨나)·다시 켜는 값(몇 도까지 식혀야)을 물으면, 그 알람 문서 한 조각에
# 같은 단위 값과 트립·복귀 표현이 바로 붙어 있을 때만 답한다 (규칙 2.2: 공식 원문에 없는 트립 온도·압력·전류는 만들지 않는다)
# 단위 뒤에 조건 말(넘으면·밑이면·이상·에서·까지·되면·면 …)이 붙을 때만 기준값 질문이다 — "몇 psi로 맞춰야 돼?"(공급·설정 값)는 아님.
# "몇 도구·도어"는 온도가 아니다. 영문 단위는 뒤에 영문이 붙지 않을 때만
THRESH_Q_V4 = re.compile(r"몇\s*(?:(도)(?!구|어|장|착|움|전|입)|(℃|°c)|(psi|bar|mpa|kpa|a|v)(?![a-z])|(암페어|볼트))"
                         r"\s*(?:정도\s*)?(?:가|이|를|은|는)?\s*(?:넘|밑|이상|이하|아래|초과|미만|에서|부터|까지|되면|이면|면|떨어|올라|도달)", re.I)
THRESH_UNIT_V4 = {"온도": r"(?:℃|°C|°F|도)", "압력": r"(?:psi|PSI|bar|MPa|kPa)", "전류": r"(?:A|암페어)(?![A-Za-z])",
                  "전압": r"(?:V|볼트)(?![A-Za-z])"}
RESET_Q_V4 = re.compile(r"까지\s*(?:식|내려|떨어|기다)|식혀|식히|식을|내려가야|다시\s*(?:돌|켜|가동|시작)")
TRIP_NEAR_V4 = (r"[^/|]{0,20}?(?:에서\s*(?:정지|동작|멈|뜬|뜨|난|작동)|아래로\s*떨어지|(?:넘|초과|이상|미만|이하|밑)(?:으면|이면|하면|으로|로|을)"
                r"|에\s*도달)")
RESET_NEAR_V4 = r"\S{0,3}\s*(?:로|까지|이하로)\s*(?:내려가|떨어지|식)"


def _thresh_kind(unit: str) -> str:
    u = unit.lower()
    return {"도": "온도", "℃": "온도", "°c": "온도", "psi": "압력", "bar": "압력", "mpa": "압력", "kpa": "압력",
            "암페어": "전류", "a": "전류", "볼트": "전압", "v": "전압"}[u]


def alarm_threshold_v4(question: str, texts: list[str]) -> tuple[bool, str, str] | None:
    """알람이 뜨는(또는 다시 켜는) 기준값을 묻는 질문이면 (문서에 있나, 종류, 찾은 조각). 그런 질문이 아니면 None."""
    m = THRESH_Q_V4.search(question)
    if not m:
        return None
    kind = _thresh_kind(m.group(m.lastindex))
    reset = bool(RESET_Q_V4.search(question))
    value = r"\d+(?:\.\d+)?\s*" + THRESH_UNIT_V4[kind]
    near = re.compile(value + (RESET_NEAR_V4 if reset else TRIP_NEAR_V4))
    for t in texts:
        for seg in _segments(t):
            if near.search(seg):
                return True, ("다시 켜는 " if reset else "") + kind, seg.replace("**", "").strip()
    return False, ("다시 켜는 " if reset else "") + kind, ""


DATED_INTENTS_V4 = ("stops", "production", "kpi", "alarm_count")  # 날짜로 찾는 운영 조회 (기준 시각 뒤 날짜면 기록이 없음)


def resolve_dates_v4(q: str, intents: list[str], start, end):
    """v3 + 주 단위 말과 요일을 함께 읽는다. 돌려주는 값 = (시작, 끝, 기준 시각 뒤 날짜를 물었나).
    "지난주 금요일"처럼 주와 요일을 함께 말하면 날짜가 분명하므로 운영 낱말이 없어도 그날로 둔다(LLM 분류의 기간보다 우선).
    요일만 있는 말·요일 여럿은 v3처럼 운영 질문일 때만 날짜로 읽는다."""
    if start is not None:
        return start, end, start > REF_DATE
    if FUTURE_V4.search(q):
        return None, None, True
    days = sorted({WEEKDAY_NO[x] for x in WEEKDAYS_V4.findall(q)})
    week = -2 if TWO_WEEKS_AGO_V4.search(q) else (-1 if LAST_WEEK_V3.search(q) else (0 if THIS_WEEK_V3.search(q) else None))
    if week is not None and days:  # "지난주 금요일" = 그날, "지난주 월~수요일" = 처음~끝
        mon = REF_DATE - timedelta(days=REF_DATE.weekday()) + timedelta(weeks=week)
        s, e = mon + timedelta(days=days[0]), mon + timedelta(days=days[-1])
        if s > REF_DATE:  # "이번 주 금요일"(10/2) — 기준 시각 뒤
            return None, None, True
        return s, min(e, REF_DATE), False
    if week == -2:  # 지지난주 = 지지난 월요일 ~ 일요일
        mon = REF_DATE - timedelta(days=REF_DATE.weekday() + 14)
        return mon, mon + timedelta(days=6), False
    if week is None and len(days) > 1 and intents:  # 요일 여럿("목요일이랑 금요일") = 가장 가까운 지난 날들의 처음~끝
        ds = sorted(REF_DATE - timedelta(days=(REF_DATE.weekday() - d) % 7 or 7) for d in days)
        return ds[0], ds[-1], False
    s, e = resolve_dates_v3(q, intents, None, None)
    return s, e, False


def doc_question_v4(question: str) -> str:
    """doc_question_v3 + 대명사 경계·"그런 N"의 앞 문장 말 가져오기 (PARSE_V4)."""
    sents = [x.strip() for x in re.split(r"(?<=[?？.!])\s+", question.strip()) if x.strip()]
    if len(sents) < 2:
        return question
    cue = [x for x in sents if DOC_CUE_V4.search(x) or any(w in x for w in DOC_WORDS)]
    if not cue:
        return question
    d = cue[-1]
    others = " ".join(x for x in sents if x is not d)
    nouns = list(dict.fromkeys(m.group(0) for m in OPS_NOUNS_V3.finditer(others)))
    m = PRONOUN_V4.match(d)
    if m and m.group(1) in DETERMINER_V4:  # "그런 공구는 …" = 그런 종류 → 앞 문장에서 그 명사로 끝나는 말(꾸밈말 포함)로 바꾼다
        rest = d[m.end():]
        head = re.match(r"([가-힣A-Za-z0-9%]+?)(?:은|는|이|가|을|를|의|도|만|에서|에|으로|로)?(?=\s|$)", rest)
        noun = head.group(1) if head else ""
        ante = re.search(r"([^?？.!,]*?" + re.escape(noun) + ")", others) if noun else None
        d2 = (ante.group(1).strip() + rest[len(noun):]) if ante else rest
    elif m:  # 그거·그건·"그 MTTR은"… → 앞 문장의 운영 낱말 중 뒤에 없는 것만 붙인다 (설비·날짜 꾸밈말은 문서 검색에 잡음이라 가져오지 않음)
        rest = d[m.end():]
        d2 = (" ".join(n for n in nouns if n not in rest) + " " + rest).strip()
    else:
        d2 = d if OPS_NOUNS_V3.search(d) else (" ".join(nouns) + " " + d).strip()
    return d2 if len(d2) >= 12 else question


# ---------------------------------------------------------------- 규칙 보강 4차 (PARSE_V5=1, PARSE_V2~V4 위에서만 동작)
# 봉인 시험 E3를 공개한 뒤 찾은 원인 (research_notes/로컬 LLM 연결/앞단개선4_계획_20261011.md 1절 표 S1·S2·L1~L6).
# S1(조작 요청 꼴)은 human_only 앞의 조작 요청 절에 있다.
# S2 단위 값·용량: 알람 질문이 "몇 A·V·kW"나 용량·정격·규격을 물으면, 그 알람 문서의 같은 칸에 기준 낱말과 같은 단위 값이 있을 때만 답한다
# (E3-065 "CB3 차단기 용량이 몇 암페어" → 문서에 없음). 앞이 "-"·숫자·영문인 값(부품번호 "58-2072A")은 세지 않는다
UNIT_Q_V5 = re.compile(r"몇\s*(?:(암페어|볼트|킬로와트|와트)|(VAC|VDC|kW|A|V|W))(?![A-Za-z0-9])|(용량|정격|규격)")
_VAL_V5 = r"(?<![\d\-.A-Za-z])\d+(?:\.\d+)?\s*"
UNIT_VALUE_V5 = {
    "전류": re.compile(_VAL_V5 + r"(?:A|암페어)(?![A-Za-z0-9\-])"),
    "전압": re.compile(_VAL_V5 + r"(?:VAC|VDC|V|볼트)(?![A-Za-z0-9\-])"),
    "전력": re.compile(_VAL_V5 + r"(?:kW|KW|W|킬로와트|와트)(?![A-Za-z0-9\-])"),
    "용량": re.compile(_VAL_V5 + r"(?:VAC|VDC|kW|KW|A|V|W|L|ℓ|mL|ml|cc|kg|암페어|볼트|와트|리터|갤런)(?![A-Za-z0-9\-])"),
}
_UNIT_KIND_V5 = {"암페어": "전류", "a": "전류", "볼트": "전압", "v": "전압", "vac": "전압", "vdc": "전압",
                 "와트": "전력", "킬로와트": "전력", "w": "전력", "kw": "전력"}
ALARM_DETAIL_V5 = [d if d[0] != "금액" else ("금액", re.compile(r"([가-힣A-Za-z0-9]+)\s*(?:의\s*)?(?:가격|비용|금액)"), d[2])
                   for d in ALARM_DETAIL_V3]   # 금액 꼴에서 맨 "값"을 뺀다 ("R 값은 어떻게 잡아야", E3-005)
UNIT_STOP_V5 = {"알람", "경보", "얼마", "어떻게", "정도", "기준", "값은", "값이"}
# L1 섞인 질문의 문서 쪽 문장 앞 접속어 (E3-054 "그리고 MTTR은 …"). "또한·참고로"는 떼지 않는다
CONJ_V5 = re.compile(r"^(?:그리고|그럼|그러면|근데|그런데|그래서|또|참)(?=[\s,])[\s,]*")
# L2 문서인데 운영으로 감: "작업지시서 대신·말고·없이"는 작업지시 조회가 아니다 (E3-004)
WO_NOT_V5 = re.compile(r"작업\s*지시\S{0,2}\s*(?:대신|말고|없이)")
WSH_ALARM_V5 = re.compile(r"(?<![A-Za-z0-9])(WSH-0[12])(?![A-Za-z0-9])", re.I)
WSH_HEAT_V5 = re.compile(r"과열|몇\s*도|온도")
COUNT_WORDS_V5 = re.compile(r"몇\s*(?:번|회|건)|횟수|자주")
# L4 섞인 질문 둘째 마디: 목표·기준치·한도·정격을 몇·얼마로 물으면 문서 쪽 단서 (E3-028 "교대 목표는 몇 개야?")
DOC_CUE_V5 = re.compile(DOC_CUE_V4.pattern + r"|(?:목표|기준치|한도|정격)\S{0,2}\s*(?:몇|얼마)")
# "몇 건 찍혔"은 알람 횟수 (E3-024), "몇 번 멈춰?"는 정지 조회
OPS_INTENTS_V5 = [(n, re.compile(rx.pattern + r"|몇\s*건\s*(?:이나\s*|정도\s*)?(?:찍혔|찍힌|떴|떠(?=요|\?|\s|$)|울렸)")) if n == "alarm_count"
                  else (n, re.compile(rx.pattern + r"|몇\s*번\s*(?:이나\s*|정도\s*)?멈춰(?=\?|요|\s*$)")) if n == "stops"
                  else (n, rx) for n, rx in OPS_INTENTS_V4]
# 8차 (PARSE_V9): "몇 건씩 찍혔는지"(E7-071 — "건"과 끝말 사이의 "씩"을 놓쳐 횟수 없이 알람 카드만 답함)
OPS_INTENTS_V9 = [(n, re.compile(rx.pattern + r"|몇\s*건\s*씩\s*(?:찍혔|찍힌|떴|떠(?=요|\?|\s|$)|울렸|났|발생)")) if n == "alarm_count"
                  else (n, rx) for n, rx in OPS_INTENTS_V5]
# "N월"(날은 없음): 9월은 가상 데이터 기간 전체, 그 밖의 달은 기록이 없다 → "확인 필요" (한 달 전체·다른 달로 답하지 않음)
MONTH_V5 = re.compile(r"(?<![\d.])(\d{1,2})\s*월(?!\s*\d)")


def alarm_names_v5(question: str, master: dict[str, dict]) -> list[str]:
    """L3: 질문에 알람 번호가 없고 "알람·경보"가 있으면, 알람 마스터의 한국어 이름(괄호·공백을 뺀 4자 이상, %1 든 이름 빼고)으로 번호를 찾는다
    (E3-086 "축 서보 과부하 알람 9월에 몇 번" → 108). 긴 이름부터."""
    q = re.sub(r"\s+", "", question)
    out = []
    for code, a in master.items():
        name = re.sub(r"\s+", "", re.sub(r"\([^)]*\)", "", a.get("name_ko") or ""))
        if len(name) >= 4 and "%" not in name and name in q:
            out.append((len(name), code))
    return [c for _, c in sorted(out, reverse=True)]


def alarm_unit_missing_v5(question: str, texts: list[str], alarm_codes_: list[str]) -> tuple[str, str] | None:
    """S2: 알람 질문이 묻는 단위 값(전류·전압·전력·용량)이 그 알람 문서의 같은 칸에 기준 낱말과 함께 없으면 (이름, 기준 낱말).
    기준 낱말 = 질문 속 부품 기호(CB3·P11 …)가 있으면 그것, 없으면 질문의 핵심 낱말."""
    found = list(UNIT_Q_V5.finditer(question))
    if not found:
        return None
    unit = next(((m.group(1) or m.group(2)).lower() for m in found if m.group(1) or m.group(2)), "")  # 단위를 적었으면 그 단위가 먼저
    kind = _UNIT_KIND_V5.get(unit, "용량") if unit else "용량"
    want = UNIT_VALUE_V5[kind]
    codes = [c for c in re.findall(r"(?<![A-Za-z0-9])[A-Z]{1,4}\d+(?![0-9])", question) if c not in alarm_codes_]
    keys = codes or [w for w in content_words(question) if w not in UNIT_STOP_V5 and not w.isdigit() and w not in alarm_codes_]
    segs = [s for t in texts for s in _segments(t)]
    if any(any(k.lower() in s.lower() for k in keys) and want.search(s) for s in segs):
        return None
    return kind + " 값", (codes[0] if codes else "")


def doc_question_v5(question: str) -> str:
    """doc_question_v4 + "…고, …" 마디 나누기(L4) + 문서 쪽 문장 앞 접속어 떼기(L1) + 목표·기준치 단서(DOC_CUE_V5)."""
    sents = [x.strip() for x in re.split(r"(?<=[?？.!])\s+|(?<=고),\s*", question.strip()) if x.strip()]
    if len(sents) < 2:
        return question
    cue = [x for x in sents if DOC_CUE_V5.search(x) or any(w in x for w in DOC_WORDS)]
    if not cue:
        return question
    d = cue[-1]
    others = " ".join(x for x in sents if x is not d)
    d = CONJ_V5.sub("", d)
    if not d:
        return question
    nouns = list(dict.fromkeys(m.group(0) for m in OPS_NOUNS_V3.finditer(others)))
    m = PRONOUN_V4.match(d)
    if m and m.group(1) in DETERMINER_V4:
        rest = d[m.end():]
        head = re.match(r"([가-힣A-Za-z0-9%]+?)(?:은|는|이|가|을|를|의|도|만|에서|에|으로|로)?(?=\s|$)", rest)
        noun = head.group(1) if head else ""
        ante = re.search(r"([^?？.!,]*?" + re.escape(noun) + ")", others) if noun else None
        d2 = (ante.group(1).strip() + rest[len(noun):]) if ante else rest
    elif m:
        rest = d[m.end():]
        d2 = (" ".join(n for n in nouns if n not in rest) + " " + rest).strip()
    else:
        d2 = d if OPS_NOUNS_V3.search(d) else (" ".join(nouns) + " " + d).strip()
    return d2 if len(d2) >= 12 else question


def v5_on(s=None) -> bool:
    s = s or settings()
    return bool(s.parse_v2 and s.parse_v3 and s.parse_v4 and s.parse_v5)


def doc_cue(question: str, s=None) -> bool:
    s = s or settings()
    if s.parse_v4 and s.parse_v5:
        return bool(DOC_CUE_V5.search(question))
    return bool((DOC_CUE_V4 if s.parse_v4 else DOC_CUE_V3).search(question))


# ---------------------------------------------------------------- 규칙 보강 5차 (PARSE_V6=1, PARSE_V2~V5 위에서만 동작)
# 봉인 시험 E4를 공개한 뒤 찾은 원인과 원문 이름 고침 때 찾은 근소 동점 (research_notes/로컬 LLM 연결/앞단개선5_계획_20261011.md 1절 표).
# S1′(물음표가 붙은 부탁 꼴)은 human_only 앞의 조작 요청 절에, S2′(1차 문지기 답 종류 검사)는 _doc_part에, L6(근소 동점)은 _doc_search에 있다.
WSH_NAME_V6 = re.compile(r"세척기|세척\s*설비|세척\s*장비")   # L1: 설비 ID 없이 "세척기 + 과열 + 몇 도·온도" (E4-036)
HEAT_DEG_V6 = re.compile(r"몇\s*도|온도")
LAST_MONTH_DAY_V6 = re.compile(r"(?:지난\s*달|저번\s*달)\s*(\d{1,2})\s*일")   # L2: "지난달 18일" = 그날 (E4-040)
NAME_TAIL_V6 = re.compile(r"(?:됨|함|음|임)$")                              # L3: 알람 이름 끝의 어미 (E4-033 "공구 부하가 초과됨")
PARTICLE_TAIL_V6 = re.compile(r"(?:가|이|을|를|은|는|의|에)$")               # L3: 이름 가운데 낱말 끝의 조사 ("부하가" → "부하")
# L5: 알람 질문이 조임 값(토크)을 물으면 그 알람 문서 칸에서 토크 값 줄을 찾아 붙인다 (E4-038 "고정 볼트는 몇으로 조여?")
TORQUE_Q_V6 = re.compile(r"조여|조이|조임|토크|체결\s*(?:힘|값)")
TORQUE_VAL_V6 = re.compile(r"(?<![\d.])\d+(?:\.\d+)?\s*(?:ft[-·\s]?lbs?|lb[-·]?ft|N[·.]?m|kgf[·.]?(?:cm|m)|in[-·]?lbs?)(?![A-Za-z])", re.I)
NEAR_TIE_V6 = 0.02   # L6: 다시 줄 세운 점수가 1등의 98% 이상이면 근소 동점으로 본다 [가상: 보이는 세트로 정함, 4단계 기록]


def v6_on(s=None) -> bool:
    s = s or settings()
    return bool(v5_on(s) and s.parse_v6)


def alarm_names_v6(question: str, master: dict[str, dict]) -> list[str]:
    """L3: 4차 이름 맞추기 + 조사·어미를 뺀 꼴(4자 이상)도 맞춘다 — 가운데 낱말(3자 이상) 끝의 조사와 끝 낱말의 됨·함·음·임
    ("공구 부하가 초과됨" → "공구부하초과": "공구 부하 초과 알람 지난달에 몇 번" → 174). 긴 꼴부터."""
    q = re.sub(r"\s+", "", question)
    out = {}
    for code, a in master.items():
        toks = re.sub(r"\([^)]*\)", "", a.get("name_ko") or "").split()
        if not toks or any("%" in t for t in toks):
            continue
        stem = [PARTICLE_TAIL_V6.sub("", t) if len(t) >= 3 else t for t in toks[:-1]] + [NAME_TAIL_V6.sub("", toks[-1])]
        for n in ("".join(toks), "".join(stem)):
            if len(n) >= 4 and n in q:
                out[code] = max(out.get(code, 0), len(n))
    return [c for c, _ in sorted(out.items(), key=lambda x: -x[1])]


def ops_clause_v6(question: str, def_extra) -> bool:
    """L4: 마디(문장·"…고,")가 둘 이상이고, 정의·기준을 묻지 않는 마디에 운영 의도가 있으면 True (E4-030 —
    "몇 번 났어요? 그리고 몇 번 나면 반복 알람으로 잡혀요?"에서 뒷 마디가 앞 마디의 횟수 질문을 지웠다)."""
    clauses = [x.strip() for x in re.split(r"(?<=[?？.!])\s+|(?<=고),\s*", question.strip()) if x.strip()]
    if len(clauses) < 2:
        return False
    for c in clauses:
        if PREMISE_V7.search(c) and v7_on():   # 6차: 전제 마디("…안 만든다며.")는 운영 마디로 세지 않는다 (E5-072)
            continue
        cm = COMPOUND_MASK_V3.sub(" ", c.lower())
        if any(rx.search(cm) for _, rx in OPS_INTENTS_V5) and not (DEFINITION.search(c) or def_extra.search(c)):
            return True
    return False


def alarm_torque_v6(question: str, texts: list[str]) -> tuple[bool, str] | None:
    """L5: 조임 값을 묻는 알람 질문이면 (문서에 있나, 찾은 칸). 질문 낱말이 든 칸을 먼저 고른다. 그런 질문이 아니면 None."""
    if not TORQUE_Q_V6.search(question):
        return None
    segs = [s for t in texts for s in _segments(t) if TORQUE_VAL_V6.search(s)]
    if not segs:
        return False, ""
    words = [w for w in content_words(question) if not w.isdigit()]
    best = next((s for s in segs if any(w in s for w in words)), segs[0])
    return True, best.replace("**", "").strip()


# ---------------------------------------------------------------- 규칙 보강 6차 (PARSE_V7=1, PARSE_V2~V6 위에서만 동작)
# 2026-10-12 사용자 테스트와 E5 공개 뒤 원인 (research_notes/로컬 LLM 연결/앞단개선6_계획_20261012.md 3.2절).
# 답 모양 낱말: 질문의 주제가 아니라 답을 어떤 꼴로 달라는 말. 낱말 겹침·BM25 질문에서 뺀다(다른 내용 낱말이 남을 때만).
# "요약 보고서"·"정리정돈"·"설명서" 같은 명사는 빼지 않는다 — 요약·정리는 "…해" 꼴일 때만, 설명은 "쉬운 설명" 칸과 겹쳐 맨 꼴도 뺀다.
# "다시"는 빼지 않는다 — "다시 시작하려면"처럼 주제의 일부다 (보이는 세트 비교 전 확인, "다시 말해 줘"는 이어 묻기 감지가 맡음)
SHAPE_TOKEN_V7 = re.compile(r"쉽게|쉬운|짧게|간단히|간단하게|자세히|자세하게|방금(?:내용|답|말)?|아까(?:내용|답|말)?"
                            r"|설명(?:해(?:줘|주세요|줄래|줄래요|봐|봐요|요)?)?|(?:요약|정리)해(?:줘|주세요|줄래|줄래요|봐|봐요|요)?"
                            r"|풀어(?:서|줘|주세요|줄래|봐)?")   # "정리해야"(정리정돈을 해야)는 부탁 꼴이 아니라 빼지 않는다 (E2-009)
# E5-072: 앞 말을 받는 전제 마디("…안 만든다며.")는 물음이 아니다 — 운영 마디로 세지 않는다
PREMISE_V7 = re.compile(r"(?:다며|다면서|라며|라면서|잖아|잖아요|다던데|라던데|댔는데|다고\s*했는데)\s*[.!?。]?$")
# E5-075: "무슨 모델·어느 회사 제품" — 줄의 이름이 묻는 대상의 것일 때만 답한다 ("TRIM SC538의 굴절계 계수"는 절삭유 이름)
MODEL_Q_V7 = re.compile(r"([가-힣A-Za-z0-9]+?)(?:은|는|이|가|도)?\s*(?:무슨|어느|어떤)\s*(?:회사\s*)?(?:모델|제품|회사|상표|브랜드|메이커|기종)")
NAME_V7 = r"[A-Za-z][A-Za-z0-9\-/]*(?:\s+[A-Za-z0-9][A-Za-z0-9\-/]*)*"


# 주제가 아닌 두루뭉술한 말 ("방금 내용", "위 내용", "그거") — 이것과 답 모양 낱말만 남는 질문은 찾을 주제가 없다
GENERIC_V7 = {"내용", "거", "것", "답", "말", "글", "부분", "얘기", "그거", "그것", "이거", "이것", "저거", "위", "앞", "이전", "더", "좀"}


def v7_on(s=None) -> bool:
    s = s or settings()
    return bool(v6_on(s) and s.parse_v7)


# ---------------------------------------------------------------- 7차 (PARSE_V8=1, PARSE_V2~V7 위에서만 동작)
# 봉인 시험 E6 공개 뒤 원인과 사용자 화면 대화 (research_notes/로컬 LLM 연결/앞단개선7_계획_20261012.md 2.1절).
# A1 알람 카드 길 답 종류 검사는 _answer의 알람 절에, A3 허락 꼴은 human_only에, A5 답 종류 꼴 경계는 ANSWER_TYPE_V8에 있다.
def v8_on(s=None) -> bool:
    s = s or settings()
    return bool(v7_on(s) and s.parse_v8)


# 8차 스위치 (2026-10-12, research_notes/로컬 LLM 연결/앞단개선8_계획_20261012.md 1절) — 셋 다 PARSE_V2~V8 위에서만 동작
def v9_on(s=None) -> bool:
    """PARSE_V9: 규칙 보강 8차 ("얘기해"·"몇 건씩"·"리스트 줘" 좁은 예외·모양 이어 묻기·용어집 풀이 정리)."""
    s = s or settings()
    return bool(v8_on(s) and s.parse_v9)


def flow_on(s=None) -> bool:
    """FLOW_V9: 흐름 바꾸기 (알람 + 문서 함께·카드 영문명, 섞인 질문의 문서 쪽 따로 답하기, 줄 고르기 대상 한정)."""
    s = s or settings()
    return bool(v8_on(s) and s.flow_v9)


def blocks_on(s=None) -> bool:
    """BLOCKS_V2: 줄 목록 칸 2판 (표시만 — 운영 항목 목록·표 줄 칸·줄마다 출처). conclusion 글자는 바꾸지 않는다."""
    s = s or settings()
    return bool(v8_on(s) and s.blocks_v2)


def v10_on(s=None) -> bool:
    """PARSE_V10 (9차): 띄어쓰기 — 사내 문서 낱말 + 조사 + 묻는 말이 붙은 낱말을 나눈다 (1부 원인 H)."""
    s = s or settings()
    return bool(v8_on(s) and s.parse_v10)


def flow10_on(s=None) -> bool:
    """FLOW_V10 (9차): 섞인 알람 질문의 운영 조회를 마디마다 (I), 카드 칸 "원문 설명"을 보일 줄에서 빼기 (D — LLM 후보는 그대로),
    알람 답 "짧게"는 프로그램이 (B)."""
    s = s or settings()
    return bool(v8_on(s) and s.flow_v10)


def blocks3_on(s=None) -> bool:
    """BLOCKS_V3 (9차): 줄 목록 칸 3판 (표시만 — conclusion 글자는 바꾸지 않는다). 앞 답 그대로 답의 줄 목록 (A),
    덩어리 제목·점검 순서 자리 (C), 정지 답의 교대 보고서 기준 따로 (F), 꼬리표를 실제대로 (G)."""
    s = s or settings()
    return bool(v8_on(s) and s.blocks_v3)


def josa_v8(word: str, with_final: str, without_final: str) -> str:
    """받침에 맞춘 조사 (A5 — "절차은(는)"을 고침). 한글은 받침, 숫자는 읽는 소리(0·1·3·6·7·8은 받침), 영문 L·M·N·R은 받침으로 본다."""
    w = re.sub(r"[\s)\]」』'\"]+$", "", word or "")
    if not w:
        return without_final
    ch = w[-1]
    if "가" <= ch <= "힣":
        return with_final if (ord(ch) - 0xAC00) % 28 else without_final
    if ch.isdigit():
        return with_final if ch in "013678" else without_final
    return with_final if ch.lower() in "lmnr" else without_final


def no_subject_v7(question: str) -> bool:
    """답 모양 낱말·두루뭉술한 말을 빼면 내용 낱말이 하나도 없는 질문 ("방금 내용 더 쉽게 설명해", "위 내용 요약해 줘").
    문서를 찾지 않는다 — 찾으면 "쉬운 설명"·"방법 요약" 같은 칸 이름에 걸려 엉뚱한 줄로 답한다 (2026-10-12 사용자 테스트)."""
    tokens = re.findall(r"\d+[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", question.lower())
    rest = [w for w in tokens if not SHAPE_TOKEN_V7.fullmatch(w) and w not in GENERIC_V7]
    return bool(tokens) and not [w for w in _content_of(rest) if w not in GENERIC_V7]


def strip_shape_v7(question: str) -> str:
    """BM25 질문에서 답 모양 낱말을 뺀 글. 뺀 뒤 내용 낱말이 없으면 원래 질문 그대로."""
    kept = [w for w in question.split() if not SHAPE_TOKEN_V7.fullmatch(re.sub(r"[?!.,~]+$", "", w).lower())]
    out = " ".join(kept)
    return out if kept and _content_of(re.findall(r"\d+[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", out.lower())) else question


def model_name_ok_v7(question: str, text: str) -> bool:
    """E5-075: 모델·제품·회사를 묻는 질문이면, 묻는 대상(바로 앞 명사, 용어집 동의어 포함) 바로 뒤에 이름이 오거나
    (대상: 이름 / 대상 (이름) / 대상 — 이름) 이름 바로 뒤 괄호에 대상이 있어야 한다 (이름 (대상)). 묻지 않으면 True."""
    m = MODEL_Q_V7.search(question)
    if not m:
        return True
    obj = re.sub(r"(?:은|는|이|가|도)$", "", m.group(1))
    if len(obj) < 2:
        return True
    names = {obj}
    for k, v in synonyms().items():
        if k == obj or v == obj:
            names |= {k, v}
    for o in names:
        e = re.escape(o)
        if re.search(rf"{e}\s*(?:[:：=—-]\s*|\(\s*|은\s+|는\s+)\(?\s*{NAME_V7}", text) or re.search(rf"{NAME_V7}\s*\([^)]*{e}", text):
            return True
    return False


# ---------------------------------------------------------------- 이어 묻기 (FOLLOWUP=1, 2026-10-12 사용자 결정 "3번까지" — [제안], 요구사항에 없음)
# 앞 답을 가리키는 질문("방금 내용 더 쉽게 설명해")을 알아본다. 비서는 앞 대화를 받지 않으므로, 서버가 기억한 바로 앞 답(prev)이
# 있을 때만 그 답의 근거 안에서 다시 말하고, 없으면 되묻는다. 상세: research_notes/로컬 LLM 연결/앞단개선6_계획_20261012.md 3.1·3.3절
FU_REF = re.compile(r"(?<![가-힣])(?:방금|아까(?![워운])|위|앞|이전|그)\s*(?:의\s*)?(?:내용|답|말|글|설명|얘기|거|것)"
                    r"|(?<![가-힣])(?:그거|그것|방금|아까(?![워운]))")
FU_KIND = [("detail", re.compile(r"자세히|자세하게|더\s*알려|구체적")),
           ("short", re.compile(r"요약|짧게|줄여|간추려|한\s*줄로|한\s*문장으로")),
           ("again", re.compile(r"다시\s*(?:말해|보여|알려|설명|읽어)|한\s*번\s*더|또\s*말해")),
           ("simple", re.compile(r"쉽게|쉬운\s*말|풀어|간단히|간단하게|알아듣게|이해하기\s*쉽|설명"))]
FU_PERMIT = re.compile(r"(?:해도|켜도|꺼도|돌려도|써도|눌러도|열어도|풀어도|바꿔도|올려도|내려도)\s*(?:돼|되|될|괜찮)")
FU_REF_WORDS = {"방금", "아까", "이전", "그", "의"}
# 이어 묻기 요청 말 가운데 주제가 아닌 것 ("다시 말해 줘", "한 번 더 알려 줘")
FU_STOP = {"다시", "한", "번", "더", "또", "말해", "말해줘", "얘기해", "알려", "알려줘", "보여", "보여줘", "읽어", "줘", "주세요", "줄래", "봐"}
FU_MAX_CHARS = 1500   # 이보다 긴 앞 답은 바꿔 쓰지 않는다 [제안] — 빠뜨릴 위험이 크다
FU_LEAD = {"simple": "쉬운 말로 다시 쓴 글입니다 (AI가 바꿔 씀, 근거는 앞 답과 같음):",
           "short": "짧게 줄인 글입니다 (AI가 바꿔 씀, 근거는 앞 답과 같음):"}


def followup_kind(question: str, prev_text: str = "") -> str | None:
    """이어 묻기 종류 (simple·short·again·detail) 또는 None (새 질문).
    허락·조작 꼴("그거 다시 켜도 돼?")은 아니다. 주제 낱말이 남으면 가리키는 말이 있고 그 낱말이 모두 앞 질문·답에 있을 때만."""
    q = question.strip()
    if FU_PERMIT.search(q) or CONTROL_VERB_V5.search(q):
        return None
    kind = next((k for k, rx in FU_KIND if rx.search(q)), None)
    if not kind:
        return None
    tokens = re.findall(r"\d+[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", q.lower())
    rest = [w for w in _content_of([t for t in tokens if not SHAPE_TOKEN_V7.fullmatch(t) and t not in GENERIC_V7
                                    and t not in FU_REF_WORDS and t not in FU_STOP])
            if w not in GENERIC_V7 and w not in FU_STOP and not any(rx.search(w) for _, rx in FU_KIND)]
    if rest and not (FU_REF.search(q) and prev_text and all(w in prev_text.lower() for w in rest)):
        return None
    return kind


# 7차 A2 (PARSE_V8): 이어 묻기 감지는 검색용 낱말 정리(_content_of — 2글자 낱말은 조사를 떼지 않음)를 다시 쓰지 않는다.
# E6에서 "위 내용 짧게 정리해 줘요"·"한 줄로 다시 말해 주세요"·"그거 한 번만 더 말해 줄래?"·"위에 말한 거 쉽게 설명해 주세요"를 놓쳤다
# ("줘요·줄로·번만·위에·말한"이 주제 낱말로 남음, "정리"가 짧게 꼴에 없음, "한 번만 더"가 다시 꼴에 없음)
FU_KIND_V8 = [("detail", re.compile(r"자세히|자세하게|더\s*알려|구체적")),
              ("short", re.compile(r"요약|짧게|줄여|간추려|한\s*줄로|한\s*문장으로|정리\s*(?:해|좀)")),
              ("again", re.compile(r"다시\s*(?:말해|보여|알려|설명|읽어)|한\s*번\s*(?:만\s*)?더|또\s*말해")),
              ("simple", re.compile(r"쉽게|쉬운\s*말|풀어|간단히|간단하게|알아듣게|이해하기\s*쉽|설명"))]
FU_REF_V8 = re.compile(FU_REF.pattern + r"|(?<![가-힣])(?:위에|위의|앞에|앞의|아까|방금)\s*(?:말한|말했던|한|했던|나온|쓴|얘기한)")
# 이어 묻기 말 가운데 주제가 아닌 것 (끝말·답 모양·가리키는 말). 반말·존댓말·묻는 꼴 끝말을 모두 넣는다
FU_FILL_V8 = frozenset((
    "줘 줘요 주세요 줄래 줄래요 주라 줘라 주실래요 주시겠어요 줄 수 있어 있어요 있나요 봐 봐요 해 해요 해줘 해줘요 해주세요 해줄래 해줄래요 "
    "하게 해서 다오 쉽게 쉬운 쉬운말로 말 말로 짧게 간단히 간단하게 요약 요약해 정리 정리해 줄여 줄여줘 간추려 한 줄로 문장으로 번 번만 "
    "더 다시 또 말해 말해줘 말해줄래 말해주세요 알려 알려줘 알려주세요 보여 보여줘 읽어 설명 설명해 설명해줘 풀어 풀어서 풀어줘 "
    "자세히 자세하게 구체적으로 알아듣게 이해하기 단계별로 단계별 차근차근 하나씩 방금 아까 위 위에 위의 앞 앞에 앞의 이전 "
    "그 그거 그것 그걸 그거를 이거 이것 내용 답 거 것 걸 부분 얘기 글 말한 말했던 했던 나온 쓴 얘기한 좀 조금 제발 그냥 한번 요 혹시 저기").split())
FU_GLUED_V8 = ("설명해줘", "설명해", "설명", "요약해", "정리해", "말해줘", "말해", "알려줘")   # 붙여 쓴 꼴 ("단계별로설명해")
FU_CTRL_OK_V8 = re.compile(r"(?:방금|아까|위|앞|이전|그)\s*(?:의\s*)?(?:내용|답|말|글|설명|거|것)\S{0,2}\s*(?:좀\s*)?(?:(?:짧게|간단히|간단하게|간략히|간략하게)\s*)?줄여")   # "방금 내용 짧게 줄여줘"도 이어 묻기 (2026-10-18: 조작 요청으로 거절되던 말)


def _fu_rest_v8(question: str, fill: frozenset = FU_FILL_V8, glued: tuple = FU_GLUED_V8) -> list[str]:
    out = []
    for t in re.findall(r"\d+[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", question.lower()):
        w = t
        for suf in glued:
            if w.endswith(suf) and w != suf and w[: -len(suf)] in fill:
                w = suf
                break
        stem = re.sub(r"(?:을|를|은|는|이|가|에|의|도|만|요|로|으로)$", "", w)
        if any(x in fill or x in GENERIC_V7 or SHAPE_TOKEN_V7.fullmatch(x) for x in (w, stem)) or len(stem) < 2:
            continue
        out.append(stem)
    return out


def followup_kind_v8(question: str, prev_text: str = "", kinds: list = FU_KIND_V8, fill: frozenset = FU_FILL_V8,
                     glued: tuple = FU_GLUED_V8) -> str | None:
    """followup_kind의 7차 판 (A2). 허락 꼴·조작 요청은 아니다 — 다만 "방금 내용 줄여 줘"는 이어 묻기 ("속도 줄여 줘"는 조작 요청 그대로).
    kinds·fill·glued는 8차 판(followup_kind_v9)이 바꿔 넣는다."""
    q = question.strip()
    if FU_PERMIT.search(q) or PERMIT_CTRL_V8.search(q):
        return None
    if CONTROL_VERB_V5.search(q) and not FU_CTRL_OK_V8.search(q):
        return None
    kind = next((k for k, rx in kinds if rx.search(q)), None)
    if not kind:
        return None
    rest = _fu_rest_v8(q, fill, glued)
    if rest and not (FU_REF_V8.search(q) and prev_text and all(w in prev_text.lower() for w in rest)):
        return None
    return kind


# 8차 (PARSE_V9): 감지 낱말을 6차 옛 목록(FU_STOP)과 대조해 빠진 "얘기해"를 넣는다 (E7-077 "아까 말한 거 더 간단하게 얘기해 줄 수 있어?"를
# 부탁 꼴로 거절했다 — 과잉 거절). 보이는 모양을 바꿔 달라는 말(줄바꿈·가독성·번호·목록으로 …)도 주제 낱말로 세지 않는다
# (2026-10-12 사용자 화면 "방금내용 줄바꿈해서 가독성있게 요약해" → 그 말로 문서를 찾아 "문서에 없음"). 모양만 바꿔 달라면 새 kind "layout"
FU_LAYOUT_WORDS_V9 = frozenset((
    "얘기해 얘기해줘 얘기해줘요 얘기해주세요 얘기해줄래 얘기해줄래요 얘기해봐 이야기해 이야기해줘 이야기해주세요 "
    "줄바꿈 줄바꿈해 줄바꿈해서 줄바꿔서 바꿔서 바꿈 줄씩 가독성 가독성있게 있게 보기 보기좋게 좋게 읽기 읽기쉽게 번호 번호로 매겨 매겨서 "
    "붙여서 달아서 목록 목록으로 목록처럼 나눠 나눠서 나눠서요 항목별 항목별로 깔끔하게 정돈해서 표로 보기쉽게").split())
FU_FILL_V9 = FU_FILL_V8 | FU_LAYOUT_WORDS_V9
FU_GLUED_V9 = FU_GLUED_V8 + ("얘기해줘", "얘기해")
FU_LAYOUT_V9 = re.compile(r"줄\s*바꿈|줄\s*바꿔서|줄\s*나눠|가독성|보기\s*좋게|읽기\s*쉽게|번호\s*(?:를|로)?\s*(?:매겨|붙여|달아)"
                          r"|목록\s*으로|목록처럼|항목별로|한\s*줄씩|표로\s*(?:보여|정리)|깔끔하게")
# "요약해 + 줄바꿈해서"는 짧게(줄인 글도 줄로 나눠 보인다), "읽기 쉽게 줄바꿈해서"는 모양만 — 쉽게(simple)보다 먼저 본다
FU_KIND_V9 = [FU_KIND_V8[0], FU_KIND_V8[1], ("layout", FU_LAYOUT_V9), FU_KIND_V8[2], FU_KIND_V8[3]]


def followup_kind_v9(question: str, prev_text: str = "") -> str | None:
    """followup_kind의 8차 판 (PARSE_V9): "얘기해"·모양 낱말을 주제 낱말로 세지 않고, 모양만 바꿔 달라는 말은 kind "layout"."""
    return followup_kind_v8(question, prev_text, FU_KIND_V9, FU_FILL_V9, FU_GLUED_V9)


def _same_as_prev(prev: dict) -> dict:
    return {k: prev[k] for k in ("steps", "evidence", "current_data", "related", "caution", "data_label", "is_synthetic", "links")}


def _rewrite_blocked(prev: dict) -> str | None:
    """앞 답 중 바꿔 쓰면 안 되는 것 (안전·절차 — 규칙 2.5·3.1, FR-AST-COM-13). 이유 글 또는 None."""
    if prev["alarm"] or prev["steps"]:
        return "알람 설명·점검 순서"
    if prev["procedure"]:
        return "절차"
    if any(e["doc_id"] in ("DOC-03", "DOC-05") for e in prev["evidence"]):
        return "고장 대응·안전 작업 문서"
    if prev["future"]:
        return "날짜 확인 안내"
    return None   # 안전 낱말이 든 줄은 줄마다 원문 그대로 둔다 (_followup_answer)


# 9차 FLOW_V10 (1부 원인 B): 알람 답의 "짧게"는 LLM 없이 프로그램이 줄인다. 안내 글에 숫자를 넣지 않는다 (이어 묻기 S9 "새 숫자 0")
FU_ALARM_SHORT_V10 = ("짧게 줄인 글입니다 (프로그램이 줄임, LLM에 보내지 않음 — 알람 설명과 점검 순서는 그대로 두고, "
                      "운영 기록·문서에서 더 찾은 줄은 앞 답에 있습니다):")


def _same_blocks_v10(prev: dict, s, lead: str | None = None, tail: str | None = None) -> list[dict] | None:
    """9차 BLOCKS_V3 (1부 원인 A): "앞 답 그대로" 답에도 앞 답의 줄 목록 칸을 싣는다 (화면이 한 문단으로 보이지 않게).
    conclusion 글자는 그대로다 — 안내 글(lead·tail) + 앞 답 줄 목록이 conclusion과 같은 글이다."""
    b = list(prev.get("blocks") or [])
    if not blocks3_on(s) or not b:
        return None
    return ([{"kind": "lead", "text": lead}] if lead else []) + b + ([{"kind": "text", "text": tail}] if tail else [])


def _alarm_short_v10(prev: dict, base: dict, s, same: dict, fu: dict) -> dict:
    """알람 답 "짧게" (9차 B): 카드 문장 + 점검 순서 전부(자르지 않음 — 규칙 8절). 운영 목록·문서에서 더 찾은 줄·조회 칩은 뺀다.
    LLM에 보내지 않으므로 "AI가 다시 쓴 글"이 아니다 (rewritten = False)."""
    card = prev["alarm_card"]
    out = {**base, **same, "status": "답변", "conclusion": FU_ALARM_SHORT_V10 + " " + card, "current_data": [],
           "mode": "규칙 (이어 묻기 — 프로그램이 줄임, LLM에 보내지 않음)",
           "followup": {**fu, "reason": "프로그램이 줄임", "reduced": True}}
    if blocks3_on(s):
        out["blocks"] = ([{"kind": "lead", "text": FU_ALARM_SHORT_V10}, {"kind": "text", "text": card}]
                         + ([{"kind": "steps"}] if same["steps"] else []))
    return out


def _pure_followup_rewrite(kind: str, prev: dict, base: dict, s, same: dict, fu: dict) -> dict | None:
    """PURE_FOLLOW_REWRITE=1: 순수 길(Claude가 쓴) 답의 "쉽게/짧게"를 **그 답의 글**에 해서 보인다 (2026-10-18).
    옛 방식은 근거 원문 줄을 바꿔 써서 답과 무관한 글이 나왔다 → 답의 블록(첫 문장·본문·번호 목록의 머리와 항목)을 조각으로 삼아 7차 이어 묻기의 도구를 그대로 쓴다.
    쉽게 = `FU2.rewrite_units`(숫자·영문 이름을 자리표로 가려 새로 못 만들게 + 조각별 검사) 뒤 `jobs.faith`(뜻 판정), 짧게 = `FU2.pick_short`(남길 조각을 LLM이 고르고 나머지는 뺌, 첫 문장은 항상 남김).
    안전 낱말이 든 조각은 보내지 않고 원문 그대로, 소제목·원문 줄 블록도 그대로. 외부 Claude 요청이 아니거나, 바꿀 조각이 없거나, 검사·판정·호출 어느 하나라도 걸리면
    None → 부른 쪽이 앞 답을 그대로 보인다 (fail closed)."""
    if EXT.current() is None or not s.job("write") or prev.get("status") != "답변":
        return None
    blocks = [b for b in (prev.get("blocks") or []) if isinstance(b, dict)]
    if not blocks:
        return None
    units: list[dict] = []   # 조각: 블록 번호 i, 칸 field, 목록 번호 j, 글, 그대로 둘 조각인가
    lead_seen = False
    for i, b in enumerate(blocks):
        cand: list[tuple[str, int | None, str]] = []
        if b.get("kind") in ("lead", "text") and isinstance(b.get("text"), str):
            cand = [("text", None, b["text"])]
        elif b.get("kind") == "ops":
            if isinstance(b.get("head"), str):
                cand.append(("head", None, b["head"]))
            cand += [("items", j, x) for j, x in enumerate(b.get("items") or []) if isinstance(x, str)]
        for field, j, txt in cand:
            if not txt.strip():
                continue
            fixed = any(w in txt for w in SAFETY_WORDS)
            if b.get("kind") == "lead" and not lead_seen:
                lead_seen = True
                fixed = fixed or kind == "short"   # "짧게"는 핵심 답인 첫 문장을 항상 남긴다
            units.append({"key": (i, field, j), "text": txt, "fixed": fixed})
    free = [u for u in units if not u["fixed"]]
    if not free or len(" ".join(u["text"] for u in free)) > FU_MAX_CHARS:
        return None
    traces: list[dict] = []
    if kind == "short":
        if len(free) < 2:
            return None
        keep, tr = FU2.pick_short([u["text"] for u in free])
        traces.append(tr)
        if keep is None:
            return None
        drop = {free[k]["key"] for k in range(len(free)) if k not in keep}
        nb: list[dict] = []
        for i, b in enumerate(blocks):
            if b.get("kind") == "ops":
                items = [x for j, x in enumerate(b.get("items") or []) if (i, "items", j) not in drop]
                head = "" if (i, "head", None) in drop else b.get("head")
                if not items and not head:
                    continue
                nb.append({**b, "head": head, "items": items})
            elif (i, "text", None) in drop:
                continue
            else:
                nb.append(dict(b))
        def _empty_section(k: int) -> bool:   # 소제목 뒤에 화면에 보이는 블록(첫 문장·본문·목록)이 없이 다음 소제목이나 끝이 오면 내용이 다 빠진 소제목 (원문 줄 블록은 글로 안 보인다)
            nxt = next((x.get("kind") for x in nb[k + 1:] if x.get("kind") in ("section", "lead", "text", "ops")), None)
            return nb[k].get("kind") == "section" and nxt in (None, "section")
        nb = [b for k, b in enumerate(nb) if not _empty_section(k)]
        nb.append({"kind": "text", "text": "(줄임: 일부를 뺐습니다 — 전체는 바로 앞 답에 있습니다)"})
        lead_txt = FU_LEAD_V2["short"]
    else:
        srcs = [u["text"] for u in free]
        new, _, tr = FU2.rewrite_units(srcs, [])
        traces.append(tr)
        if new is None:
            return None
        changed = [k for k in range(len(srcs)) if new[k] != srcs[k]]
        if not changed:
            return None
        ok, ftr = jobs.faith([srcs[k] for k in changed], [new[k] for k in changed])
        traces.append(ftr)
        if not ok:
            return None
        nb = [({**b, "items": list(b.get("items") or [])} if b.get("kind") == "ops" else dict(b)) for b in blocks]
        for u, txt in zip(free, new):
            i, field, j = u["key"]
            if field == "items":
                nb[i]["items"][j] = txt
            else:
                nb[i][field] = txt
        lead_txt = FU_LEAD_V2["simple"].format(extra="")
    parts: list[str] = []
    for b in nb:   # 화면 글이 아닌 conclusion(이어 묻기 기억·로그용): join_layout과 같은 모양으로 다시 이은 글
        if b.get("kind") == "section" and b.get("text"):
            parts.append(str(b["text"]) + ":")
        elif b.get("kind") in ("lead", "text") and b.get("text"):
            parts.append(str(b["text"]))
        elif b.get("kind") == "ops":
            if b.get("head"):
                parts.append(str(b["head"]))
            if b.get("items"):
                parts.append(" ".join(f"{n}) {x}" for n, x in enumerate(b["items"], 1)))
    used = [JOB_KO.get(t["job"], t["job"]) for t in traces if t["used"]]
    out = {**base, **same, "status": "답변", "conclusion": lead_txt + " " + " ".join(parts),
           "blocks": [{"kind": "lead", "text": lead_txt}] + nb, "llm_trace": traces,
           "mode": f"{s.llm_label} {s.llm_model_name} ({', '.join(dict.fromkeys(used))}) + 프로그램 검사",
           "followup": {**fu, "rewritten": True, "reason": "순수 길 답을 다시 씀" if kind != "short" else "순수 길 답을 줄임", "parts": len(free)}}
    if FORBIDDEN.search(" ".join(str(v) for v in (out["conclusion"], out["blocks"]))):   # 원문 출처가 새면 내보내지 않는다 (D-03)
        return None
    return out


def _followup_answer(kind: str, role: str, prev: dict | None, base: dict, s, memo: dict) -> dict:
    """이어 묻기 답. prev = 서버가 기억한 바로 앞 답(처음 답)의 기록. 쉽게·짧게는 바꿔 쓸 수 있는 글만 LLM이 한 번 바꿔 쓰고 한 번 검사한다.
    하나라도 실패하면(LLM 오류·시간 부족 포함) 앞 답 원문 그대로 보인다(fail closed)."""
    fu = {"kind": kind, "rewritten": False, "reason": None}
    if prev is None:
        return {**base, "status": "확인 필요", "mode": "규칙 (이어 묻기)", "followup": {**fu, "reason": "앞 답 없음"},
                "conclusion": "확인 필요 — 앞 답을 이어받지 못합니다. 무엇을 쉽게 설명할지 함께 적어 주세요 "
                              "(예: \"웨이 커버 그리스 이름 쉽게 설명해 줘\")."}
    memo["root"] = prev
    same = _same_as_prev(prev)
    if prev["status"] != "답변":  # 앞 답이 거절·문서에 없음·확인 필요면 같은 상태 그대로 (새 답을 만들지 않는다)
        concl = prev["conclusion"]
        why = ""
        if v8_on(s):  # 7차 A4: 왜 그대로인지 화면에 한 줄 (화면 안내 "이 화면 설명해 줘" 뒤 "더 쉽게"가 말없이 그대로였다)
            why = ("(앞 답은 프로그램이 정한 안내 문구라 바꿔 쓰지 않고 그대로 다시 보입니다.)" if prev["status"] == "안내"
                   else f"(앞 답이 '{prev['status']}'이라 새로 답하지 않고 그대로 다시 보입니다.)")
            concl += " " + why
        out = {**base, **same, "status": prev["status"], "conclusion": concl,
               "mode": "규칙 (이어 묻기 — 앞 답 그대로)", "followup": {**fu, "reason": "앞 답이 답변 아님"}}
        blocks = _same_blocks_v10(prev, s, tail=why or None)
        if blocks:
            out["blocks"] = blocks
        return out
    if kind == "layout":   # 8차 (PARSE_V9): 모양만 바꿔 달라는 말 — 앞 답을 줄 목록대로 다시 보인다 (새로 쓰지 않음, LLM 안 씀)
        out = {**base, **same, "status": "답변", "conclusion": FU_LAYOUT_LEAD_V9 + " " + prev["conclusion"],
               "mode": "규칙 (이어 묻기 — 앞 답을 줄 나눠 다시 보기)", "followup": {**fu, "reason": "줄 나눠 다시 보기"}}
        if len(prev.get("blocks") or []) > 1:
            out["blocks"] = [{"kind": "lead", "text": FU_LAYOUT_LEAD_V9}] + list(prev["blocks"])
        return out
    if kind == "detail":
        return {**base, "status": "확인 필요", "mode": "규칙 (이어 묻기)", "followup": {**fu, "reason": "자세히"},
                "conclusion": "확인 필요 — 앞 답에서 무엇을 더 알고 싶은지 대상과 함께 적어 주세요 "
                              "(예: \"웨이 커버 그리스는 얼마마다 발라?\")."}
    if kind == "again":
        if prev["current_data"]:  # 운영 답은 지금 기록으로 새로 다시 조회한다 (앞 답 숫자를 되풀이하지 않음)
            sub: dict = {}
            fresh = _answer(prev["question"], role, prev["context"], memo=sub)
            memo.pop("root", None)
            memo.update(sub, record_question=prev["question"], record_context=prev["context"])
            return {**fresh, "followup": {**fu, "reason": "운영 조회 다시"}}
        out = {**base, **same, "status": "답변", "conclusion": prev["conclusion"],
               "mode": "규칙 (이어 묻기 — 앞 답 그대로)", "followup": {**fu, "reason": "다시 보기"}}
        blocks = _same_blocks_v10(prev, s)
        if blocks:
            out["blocks"] = blocks
        return out
    if prev.get("pure") and kind in ("simple", "short"):   # 순수 길 답: 옛 방식은 원문 줄을 바꿔 써서 답과 무관한 글이 나온다 → 그 답의 글을 다시 쓰거나(PURE_FOLLOW_REWRITE=1), 못 하면 앞 답을 그대로 (fail closed)
        rewritten = _pure_followup_rewrite(kind, prev, base, s, same, fu) if getattr(s, "pure_follow_rewrite", False) else None
        if rewritten is not None:
            return rewritten
        note ="이 답은 바로 앞에서 AI가 쉬운 말로 쓴 글이라 다시 바꿔 쓰지 않고 그대로 보입니다."
        out = {**base, **same, "status": "답변", "conclusion": note + " " + prev["conclusion"],
               "mode": "규칙 (이어 묻기 — 앞 답 그대로)", "followup": {**fu, "reason": "순수 길 답은 그대로"}}
        blocks = _same_blocks_v10(prev, s, lead=note)
        if blocks:
            out["blocks"] = blocks
        return out
    if kind == "short" and flow10_on(s) and prev.get("alarm") and prev.get("alarm_card"):
        return _alarm_short_v10(prev, base, s, same, fu)   # 9차 B
    traces: list[dict] = []
    segs = list(prev["doc_lines"]) + list(prev["ops_texts"])
    if s.followup_v2 and v8_on(s):   # 7차: 이어 묻기가 실제로 일하게 (칸 단위·자리표·고르기·낱말 풀이)
        return _followup_answer_v2(kind, prev, base, s, same, segs)
    # 안전 낱말(잠금·표지·고전압 …)이 든 줄은 LLM에 보내지 않고 그 자리에 원문 그대로 둔다 (규칙 2.5 — 안전 글은 바꿔 쓰지 않는다)
    keep = [any(w in x for w in SAFETY_WORDS) for x in segs]
    send = [x for x, k in zip(segs, keep) if not k]
    blocked = _rewrite_blocked(prev) or (("안전 낱말이 든 줄" if segs else None) if not send else None)
    new = None
    if blocked:
        note = (f"{blocked}{josa_v8(blocked, '은', '는')} 쉽게 바꿔 쓰지 않아 앞 답을 원문 그대로 다시 보입니다." if v8_on(s)
                else f"{blocked}은(는) 쉽게 바꿔 쓰지 않아 앞 답을 원문 그대로 다시 보입니다.")
    elif not segs:
        note = "쉽게 바꿀 글이 없어 앞 답을 그대로 보입니다."
    elif not s.job("write"):
        note = "쉽게 바꿔 쓰기는 로컬 LLM이 켜져 있을 때만 됩니다 — 앞 답을 그대로 보입니다."
    elif len(" ".join(send)) > FU_MAX_CHARS:
        note = "앞 답이 길어 쉽게 바꾸지 않고 그대로 보입니다."
    else:
        note = "쉽게 바꾸지 못해 앞 답을 원문 그대로 보입니다."
        new, tr = jobs.simplify(send, kind)
        traces.append(tr)
        if new:
            ok, ftr = jobs.faith(send, new)
            traces.append(ftr)
            if not ok:
                new = None
        if new and v8_on(s) and all(a.strip() == b.strip() for a, b in zip(new, send)):
            # 7차 A4: 돌려받은 글이 원문과 같으면 "AI가 다시 쓴 글" 꼬리표를 붙이지 않는다 (사용자 화면 B·D 묶음)
            new, note = None, "바꿀 것이 없어 앞 답을 원문 그대로 다시 보입니다."
    if new:
        it = iter(new)
        merged = [("(원문 그대로) " + x) if k else next(it) for x, k in zip(segs, keep)]
        used = [JOB_KO[t["job"]] for t in traces if t["used"]]
        out = {**base, **same, "status": "답변", "conclusion": FU_LEAD[kind] + " " + " / ".join(merged),
               "steps": ["원문 — " + x for x in segs], "llm_trace": traces,
               "mode": f"{s.llm_label} {s.llm_model_name} ({', '.join(dict.fromkeys(used))}) + 프로그램 검사",
               "followup": {**fu, "rewritten": True, "kept_lines": sum(keep)}}
    else:
        out = {**base, **same, "status": "답변", "conclusion": note + " " + prev["conclusion"], "llm_trace": traces,
               "mode": "규칙 (이어 묻기 — 앞 답 그대로)", "followup": {**fu, "reason": blocked or note}}
        blocks = _same_blocks_v10(prev, s, lead=note)   # 9차 A
        if blocks:
            out["blocks"] = blocks
    blob = " ".join(str(v) for v in (out["conclusion"], out["steps"], out["evidence"], out["related"], out["caution"]))
    if FORBIDDEN.search(blob):  # 원문 출처가 새어 나가면 내보내지 않는다 (D-03)
        return {**base, "status": "확인 필요", "mode": out["mode"], "conclusion": "확인 필요 — 답에 원문 출처 표기가 섞여 내보내지 않았습니다."}
    return out


FU_LAYOUT_LEAD_V9 = "앞 답을 줄을 나눠 다시 보입니다 (내용은 앞 답과 같음):"   # 숫자를 넣지 않는다 (이어 묻기 S9 "새 숫자 0")
FU_LEAD_V2 = {"simple": "쉬운 말로 다시 쓴 글입니다 (AI가 바꿔 씀, 근거는 앞 답과 같음{extra}):",
              "short": "짧게 줄인 글입니다 (AI가 고름, 근거는 앞 답과 같음):"}
OPS_UNIT_V2 = re.compile(r"(?<=[.])\s+|\s+—\s+|\s+·\s+")


def _short_units_v2(segs: list[str], ops: bool) -> tuple[list[dict], callable]:
    """"짧게" 단위와 다시 맞추는 함수. 조각이 둘 이상이면 조각, 하나면 표 칸(문서)·마디(운영)."""
    if len(segs) >= 2:
        units = [{"text": x, "fixed": FU2.is_safety(x)} for x in segs]
        return units, lambda kept: [u["text"] for u in kept]
    head, cells = FU2.split_line(segs[0]) if segs else (None, [])
    if head is not None:
        units = [{"text": c, "fixed": FU2.is_safety(c)} for c in cells]
        return units, lambda kept: [FU2.join_line(head, [u["text"] for u in kept])]
    parts = [x.strip() for x in OPS_UNIT_V2.split(segs[0]) if x.strip()] if (segs and ops) else segs
    units = [{"text": x, "fixed": FU2.is_safety(x)} for x in parts]
    return units, lambda kept: [" · ".join(u["text"] for u in kept)]


def _followup_answer_v2(kind: str, prev: dict, base: dict, s, same: dict, segs: list[str]) -> dict:
    """이어 묻기 2판 (7차 FOLLOWUP_V2, backend/services/followup_v2.py). 쉽게 = 칸 단위 자리표 다시 쓰기 + 용어집 낱말 풀이,
    짧게 = 앞 답의 LLM 앞머리(이미 검사를 지나 화면에 보인 한 문장) 또는 LLM이 남길 조각을 고름. 하나라도 실패하면 원문 그대로.
    바꾼 것이 없으면 "AI가 다시 쓴 글" 꼬리표를 붙이지 않는다 (A4)."""
    fu = {"kind": kind, "rewritten": False, "reason": None}
    traces: list[dict] = []
    blocked = _rewrite_blocked(prev)
    body, extra_ev, note = None, [], None
    if blocked:
        note = f"{blocked}{josa_v8(blocked, '은', '는')} 바꿔 쓰지 않아 앞 답을 원문 그대로 다시 보입니다."
    elif not segs:
        note = "바꿀 글이 없어 앞 답을 그대로 보입니다."
    elif not s.job("write"):
        note = "다시 쓰기는 로컬 LLM이 켜져 있을 때만 됩니다 — 앞 답을 그대로 보입니다."
    elif len(" ".join(segs)) > FU_MAX_CHARS:
        note = "앞 답이 길어 바꾸지 않고 그대로 보입니다."
    elif kind == "short":
        lead = (prev.get("doc_lead") or "").strip()
        if lead and not prev["ops_texts"] and not FU2.is_safety(lead):
            # 안내 글에 숫자를 넣지 않는다 — 앞 답에 없던 숫자처럼 보인다 (이어 묻기 S9 "새 숫자 0", 2026-10-12)
            body = [lead, "(줄임: 앞 답의 한 문장 요약 — 원문은 아래)"]
        else:
            units, rebuild = _short_units_v2(segs, ops=bool(prev["ops_texts"]))
            free = [i for i, u in enumerate(units) if not u["fixed"]]
            if len(units) < 2 or len(free) < 2:
                note = "이미 짧거나 안전 낱말이 든 글이라 줄이지 않고 원문 그대로 다시 보입니다."
            else:
                keep, tr = FU2.pick_short([units[i]["text"] for i in free])
                traces.append(tr)
                if keep is None:
                    note = "짧게 줄이지 못해 앞 답을 원문 그대로 보입니다."
                else:
                    kept_free = {free[i] for i in keep}
                    kept = [u for i, u in enumerate(units) if u["fixed"] or i in kept_free]
                    body = rebuild(kept) + ["(줄임: 일부를 뺐습니다 — 전체는 원문 아래)"]
    else:   # simple (쉽게)
        units = FU2.units_of(segs)
        send = [i for i, u in enumerate(units) if not u["fixed"]]
        # 낱말 풀이 후보는 LLM에 보내는 칸에서만 뽑는다 (안전 칸의 낱말도 요청에 싣지 않는다)
        terms = [t for t in FU2.term_candidates(" ".join(units[i]["text"] for i in send)) if not FU2.is_safety(t["hit"])]
        texts = [u["text"] for u in units]
        picked: list[int] = []
        if send:   # 안전 낱말 칸만 남은 글은 LLM에 보내지 않는다 (규칙 2.5)
            new, picked, tr = FU2.rewrite_units([units[i]["text"] for i in send], [t["hit"] for t in terms])
            traces.append(tr)
            if new is not None:
                for i, t in zip(send, new):
                    texts[i] = t
                changed = [i for i in send if texts[i] != units[i]["text"]]
                if changed:
                    ok, ftr = jobs.faith([units[i]["text"] for i in changed], [texts[i] for i in changed])
                    traces.append(ftr)
                    if not ok:
                        texts = [u["text"] for u in units]
        notes = [FU2.term_note(terms[i], v9=v9_on(s)) for i in picked if i < len(terms)]   # 8차: 묶인 줄은 그 낱말의 영어 이름만
        new_segs = FU2.assemble(segs, units, texts)
        if new_segs == segs and not notes:
            note = ("안전 낱말이 든 글이라 바꿔 쓰지 않아 앞 답을 원문 그대로 다시 보입니다." if not send
                    else "바꿀 것이 없어 앞 답을 원문 그대로 다시 보입니다." if any(t["used"] for t in traces)
                    else "쉽게 바꾸지 못해 앞 답을 원문 그대로 보입니다.")
        else:
            body = [("(원문 그대로) " + x) if (x == o and FU2.is_safety(o)) else x for x, o in zip(new_segs, segs)]
            if notes:
                body.append("낱말 풀이 — " + "; ".join(notes))
                seen = {e["cite"] for e in same["evidence"]}
                for i in picked:
                    if i < len(terms) and terms[i]["cite"] not in seen:
                        seen.add(terms[i]["cite"])
                        extra_ev.append(_cite(terms[i]["chunk"]))
    if body:
        used = [JOB_KO.get(t["job"], t["job"]) for t in traces if t["used"]]
        lead_txt = FU_LEAD_V2[kind if kind == "short" else "simple"].format(extra=" + 용어집" if extra_ev else "")
        if kind == "short" and not traces:   # 앞 답의 LLM 앞머리를 다시 보임 — 이번에 AI가 고른 것이 아니다
            lead_txt = "짧게 줄인 글입니다 (앞 답에서 AI가 쓴 한 문장 요약, 근거는 앞 답과 같음):"
        out = {**base, **same, "status": "답변", "conclusion": lead_txt + " " + " / ".join(body),
               "steps": ["원문 — " + x for x in segs], "evidence": same["evidence"] + extra_ev, "llm_trace": traces,
               "mode": (f"{s.llm_label} {s.llm_model_name} ({', '.join(dict.fromkeys(used))}) + 프로그램 검사" if used
                        else "규칙 (이어 묻기 — 앞 답의 한 문장 요약)"),
               "followup": {**fu, "rewritten": True, "v2": True},
               "blocks": [{"kind": "lead", "text": lead_txt}] + [{"kind": "line", "text": x} for x in body]}
    else:
        out = {**base, **same, "status": "답변", "conclusion": note + " " + prev["conclusion"], "llm_trace": traces,
               "mode": "규칙 (이어 묻기 — 앞 답 그대로)", "followup": {**fu, "reason": blocked or note}}
        blocks = _same_blocks_v10(prev, s, lead=note)   # 9차 A
        if blocks:
            out["blocks"] = blocks
    blob = " ".join(str(v) for v in (out["conclusion"], out["steps"], out["evidence"], out["related"], out["caution"]))
    if FORBIDDEN.search(blob):  # 원문 출처가 새어 나가면 내보내지 않는다 (D-03)
        return {**base, "status": "확인 필요", "mode": out["mode"], "conclusion": "확인 필요 — 답에 원문 출처 표기가 섞여 내보내지 않았습니다."}
    return out


def followup_record(question: str, role: str, context: dict | None, a: dict, memo: dict) -> dict:
    """서버 기억(answer_store)에 둘 답 기록 — 이어 묻기를 또 이어 물어도 처음 답을 쓴다 (바꿔 쓴 글을 다시 바꿔 쓰지 않음)."""
    if memo.get("root") is not None:
        return memo["root"]
    rec = {"question": memo.get("record_question", question), "role": role,
            "context": memo.get("record_context", context) or {}, "status": a["status"], "conclusion": a["conclusion"],
            "steps": list(a.get("steps") or []), "evidence": list(a.get("evidence") or []),
            "current_data": list(a.get("current_data") or []), "related": a.get("related"), "caution": a.get("caution"),
            "data_label": a.get("data_label"), "is_synthetic": bool(a.get("is_synthetic")), "links": list(a.get("links") or []),
            "doc_lines": list(memo.get("doc_lines") or []), "ops_texts": list(memo.get("ops_texts") or []),
            "alarm": bool(memo.get("alarm")), "procedure": bool(memo.get("procedure")), "future": bool(memo.get("future")),
            "doc_lead": memo.get("doc_lead") or ""}   # 7차 B3
    rec["pure"] = bool(memo.get("pure_answer"))
    if v9_on():   # 8차: 모양 이어 묻기(layout)가 줄 목록대로 다시 보인다
        rec["blocks"] = list(a.get("blocks") or [])
    if flow10_on():   # 9차 B: 알람 답 "짧게"가 카드 문장만 다시 보인다
        rec["alarm_card"] = memo.get("alarm_card") or ""
    return rec


def alarm_codes() -> dict[str, dict]:
    return {a["code"]: a for a in get_repo().master("alarm_master")}


# 질문대로 답하기 1단계 (2026-10-21): "2075 …지난 두 번 조치가 뭐였어?"는 작업기록 규칙(`지난\s*조치`)에 걸리지 않아 알람 기본 카드가 나갔다.
# "지난 N번/N건 조치"·"전에 조치"·"어떻게 고쳤어" 꼴을 읽어 N건(숫자가 없으면 2건)을 낸다. 알람 번호가 없어도 읽는다(그때는 설비·전체 기록).
PAST_NUM_V22 = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
PAST_ACTION_V22 = re.compile(
    r"(?:지난|이전|저번|전에|전엔|예전|과거|앞선|직전)\s*(?:(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|\d{1,2})\s*)?(?:번|건|차례|회)?\s*(?:의\s*)?"
    r"(?:조치|처리\s*내용|처리했|고쳤|해결했|수리했)"
    r"|어떻게\s*(?:조치|처리|해결|대응|수리)\s*했|어떻게\s*고쳤")
# 지난 조치만 묻는 질문에서 알람 카드를 내지 않는다 — 카드가 묻는 말(뜻·점검 순서·원인 …)이 같이 있으면 지금처럼 카드도 낸다
CARD_ASK_V22 = re.compile(r"뭐야|뭔데|뭐예요|뭔가요|무슨\s*(?:알람|뜻)|뜻|의미|설명|점검|순서|뭐부터|먼저|원인|이유|절차|방법|뜨면|나오면|발생하면|심각도")
MAX_PAST_V22 = 10


def past_action_n_v22(question: str) -> int | None:
    """지난 조치를 묻는 말이면 보여 줄 건수(1~10, 숫자가 없으면 2), 아니면 None."""
    m = PAST_ACTION_V22.search(question)
    if not m:
        return None
    tok = m.group(1)
    if tok is None:
        return 2
    n = PAST_NUM_V22.get(tok) or int(tok)
    return max(1, min(n, MAX_PAST_V22))


def past_action_line_v22(w: dict) -> str:
    """작업기록 한 건을 한 줄로 — 기록 번호·설비·확정일·(원인)·조치 원문·(수리 분). 조치 문장은 기록 원문 그대로다."""
    action = str(w.get("action") or "").strip() or "조치 내용 없음"
    cause = str(w.get("cause") or "").strip()
    try:
        tail = f" ({float(w['repair_min']):g}분)" if w.get("repair_min") not in (None, "") else ""
    except (TypeError, ValueError):
        tail = ""
    return (f"{w.get('record_no') or w.get('work_record_id')} · {w.get('equipment_id') or '설비 미상'} · {str(w.get('start') or '')[:10]} · "
            + (f"원인 {cause} · " if cause else "") + action + tail)


# 질문대로 답하기 1단계: "축 윤활유 재고는 안전 재고보다 얼마나 부족해?"는 부족 품목 전체를 늘어놓았다. 질문에 품목이 있으면 그 품목만 읽고
# 부족분(안전 재고 − 현재 재고)을 프로그램이 계산해 고정 문장으로 답한다 (LLM에 숫자를 맡기지 않는다).
INV_ALIAS_V22 = {"CS-AFLT": ("공기필터",), "CS-CFLT": ("절삭유필터",), "CS-COOL": ("절삭유원액", "절삭유"), "CS-GRS": ("그리스",),
                 "CS-SLUB": ("주축윤활유",), "CS-WLUB": ("축윤활유",), "RM-6061": ("봉재", "6061"), "FG-BRK-A100": ("완제품", "brk-a100"),
                 "TL-BB45": ("보링바",), "TL-DR50": ("드릴",), "TL-EM10": ("엔드밀",), "TL-FM50": ("페이스밀",), "TL-TAP6": ("m6탭", "탭")}


def inventory_items_asked_v22(question: str, rows: list[dict]) -> list[dict]:
    """질문에 이름(또는 짧은 이름)이 든 재고 품목. 더 긴 이름 안에 든 짧은 이름은 뺀다 ("주축 윤활유" 안의 "축 윤활유"). 없으면 빈 목록."""
    q = re.sub(r"\s+", "", question).lower()
    spans: list[tuple[int, int, str]] = []
    for x in rows:
        names = {re.sub(r"\s+", "", str(x.get("name") or "")).lower(), *INV_ALIAS_V22.get(x.get("item_no"), ())}
        for nm in filter(None, names):
            spans += [(m.start(), m.end(), x["item_no"]) for m in re.finditer(re.escape(nm), q)]
    keep = [s for s in spans if not any(o[0] <= s[0] and s[1] <= o[1] and (o[1] - o[0]) > (s[1] - s[0]) for o in spans)]
    nos: list[str] = []
    for s in sorted(keep):
        if s[2] not in nos:
            nos.append(s[2])
    return [x for n in nos for x in rows if x["item_no"] == n]


def _qty_v22(v: float, unit: str) -> str:
    """수량 글자 — 영문 단위(L)는 띄우고(3.6 L) 한글 단위(개)는 붙인다(2개)."""
    return f"{v:g} {unit}" if unit.isascii() and unit else f"{v:g}{unit}"


def inventory_sentence_v22(x: dict) -> str:
    unit = str(x.get("unit") or "")
    on = float(x.get("on_hand") or 0)
    name = x.get("name") or x.get("item_no")
    if x.get("safety_stock") in (None, ""):
        return f"{name} {_qty_v22(on, unit)} (안전 재고 기준이 없습니다)."
    sf = float(x["safety_stock"])
    diff = round(sf - on, 3)
    base = f"{name} {_qty_v22(on, unit)}, 안전 재고 {_qty_v22(sf, unit)}"
    if diff > 0:
        return f"{base}보다 {_qty_v22(diff, unit)} 부족해요."
    if diff == 0:
        return f"{base} — 같아서 부족분은 0이에요 (재고 부족 기준은 안전 재고 이하)."
    return f"{base}보다 {_qty_v22(-diff, unit)} 많아요."


def parse(question: str) -> dict:
    q = question.strip()
    ql = q.lower()
    master = alarm_codes()
    alarms = []
    # 한글 조사("2075가")는 붙어도 되므로 앞뒤 경계는 영숫자·기호만 본다
    for m in re.finditer(r"(?<![0-9A-Za-z.\-])(?:(\d{1,2})\.)?(\d{3,5})(?:\.(\d{2,3}))?(?![0-9A-Za-z\-%])", q):
        axis, code, sub = m.group(1), m.group(2), m.group(3)
        key = f"{code}.{sub}" if sub else code
        if key in master or f"{code}.00" in master:
            alarms.append({"control": master.get(key, master.get(f"{code}.00"))["control"], "axis": axis or "",
                           "code": key if key in master else f"{code}.00", "sub": sub or ""})
    for name in ("MP-170", "TempComp-202"):
        if name.lower() in ql:
            alarms.append({"control": master[name]["control"], "axis": "", "code": name, "sub": ""})
    if "알람" in q:
        for name in ("WSH-01", "WSH-02"):
            if name.lower() in ql:
                alarms.append({"control": "OP-40", "axis": "", "code": name, "sub": ""})
    v5 = v5_on()
    v6 = v5 and settings().parse_v6
    if v5 and not alarms and re.search(r"알람|경보", q):  # L3 알람 이름 → 번호 (번호가 없고 "알람·경보"가 있을 때만)
        for code in (alarm_names_v6 if v6 else alarm_names_v5)(q, master):  # 5차: 이름 끝 어미를 뺀 꼴도
            alarms.append({"control": master[code]["control"], "axis": "", "code": code, "sub": ""})
    equipment = sorted({m.group(1).upper() for m in (EQUIP_RE_V5 if v5 else EQUIP_RE).finditer(q)} - {a["code"] for a in alarms})
    if "1호기" in q:
        equipment.append("VF2-01")
    if "2호기" in q:
        equipment.append("VF2-02")
    v2 = settings().parse_v2
    if v2:  # 설비 별명 (일호기·1번 기계 …). "VF-2"만 있으면 정하지 않는다
        for rx, eq in EQUIP_ALIAS_V2:
            if rx.search(q) and eq not in equipment:
                equipment.append(eq)
    v3 = v2 and settings().parse_v3
    if v3:  # 다른 공정 설비 별명 (2026-10-10 2차). "톱"은 "톱날"과 겹쳐 넣지 않는다
        for rx, eq in EQUIP_ALIAS_V3:
            if rx.search(q) and eq not in equipment:
                equipment.append(eq)
    start = end = None
    future = False
    shift = "N" if "야간" in q else ("D" if "주간" in q else None)
    if v2:  # 밤·간밤·새벽 → 야간, 낮 근무·낮에 → 주간 ("낮음·낮은·낮춰"는 아님)
        shift = "N" if NIGHT_V2.search(q) else ("D" if DAY_V2.search(q) else None)
    if v3 and BOTH_SHIFTS_V3.search(q):  # "주야간 통틀어" → 교대를 정하지 않는다
        shift = None
    if "어제" in q or (v2 and YESTERDAY_V2.search(q)):
        start = end = REF_DATE - timedelta(days=1)
    elif "오늘" in q:
        start = end = REF_DATE
    elif "지난 교대" in q:  # 기준 시각 10/1 08:00의 지난 교대 = 9/30 야간
        start = end = REF_DATE - timedelta(days=1)
        shift = "N"
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일|(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", q)
    if m:
        mo, d = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(4)))
        start = end = date(2026, mo, d)
    m = re.search(r"최근\s*(\d+)\s*일", q)
    if m:
        end, start = REF_DATE - timedelta(days=1), REF_DATE - timedelta(days=int(m.group(1)))
    if v6 and start is None:  # 5차 L2: "지난달 18일" = 그날 (E4-040 — "지난달"이 한 달 전체로 정해 "18일"을 버렸다)
        md = LAST_MONTH_DAY_V6.search(q)
        last = REF_DATE.replace(day=1) - timedelta(days=1)   # 지난달 마지막 날
        if md and 1 <= int(md.group(1)) <= last.day:
            start = end = last.replace(day=int(md.group(1)))
    if v2 and start is None and RECENT_WEEK_V2.search(q):
        end, start = REF_DATE - timedelta(days=1), REF_DATE - timedelta(days=7)
    elif v2 and start is None and RECENT_MONTH_V2.search(q):
        end, start = REF_DATE - timedelta(days=1), REF_DATE - timedelta(days=30)
    v4 = v3 and settings().parse_v4
    if v3:  # 붙은 말("정지게이지", "과열 정지") 안의 의도 낱말은 보지 않는다 (긴 것 우선)
        qm = COMPOUND_MASK_V3.sub(" ", ql)
        intents = [name for name, rx in (OPS_INTENTS_V9 if v5 and v9_on() else OPS_INTENTS_V5 if v5 else OPS_INTENTS_V4 if v4
                                         else OPS_INTENTS_V3) if rx.search(qm)]
    elif v2:
        intents = [name for name, rx in OPS_INTENTS_V2 if rx.search(ql)]
    else:
        intents = [name for name, words in OPS_INTENTS if any(w in ql for w in words)]
    if alarms and "자꾸" in q:  # 섞인 질문: 작업기록 + 정비 일정 + 문서 (FR-MNT-01-05, 기획서 4.2)
        intents += [i for i in ("work_records", "pm_due") if i not in intents]
    lot = re.search(r"LOT-\d{4}-\d{3}-\d+", q, re.I)
    order = re.search(r"PO-\d{4}-\d{3}", q, re.I)
    if v3:
        if lot and "lots" not in intents:  # 로트 번호가 있으면 로트 조회 ("LOT-… 판정 났어?")
            intents.append("lots")
        if (lot or order) and "equipment_status" in intents and not equipment:
            intents.remove("equipment_status")
        if v4:  # 지난주·이번 주 + 요일, 기준 시각 뒤 날짜 (2026-10-10 3차)
            start, end, future = resolve_dates_v4(q, intents, start, end)
        else:
            start, end = resolve_dates_v3(q, intents, start, end)  # 날짜만 있는 말·상대 날짜 (과거 우선)
    if v5 and "work_orders" in intents and WO_NOT_V5.search(q):  # L2 "작업지시서 대신 뭘 남겨"는 작업지시 조회가 아니다 (E3-004)
        intents.remove("work_orders")
    outside = None
    if v5 and start is None and any(i in DATED_INTENTS_V4 for i in intents):
        # L4 "N월": 9월 = 데이터 기간, 다른 달 = 기록 없음. 날짜로 찾는 조회일 때만 읽고, 정의 질문 판정보다 먼저 둔다
        # ("이 알람 9월에 몇 건 찍혔는지 …, 1단계는 몇 번이 기준인지" — "기준" 때문에 운영 의도가 지워지던 E3-024)
        mm = MONTH_V5.search(q)
        if mm and 1 <= int(mm.group(1)) <= 12:
            if int(mm.group(1)) == 9:
                start, end = date(2026, 9, 1), date(2026, 9, 30)
            else:
                outside = f"{int(mm.group(1))}월"
    # 설비·날짜·로트 없이 정의·기준·방법을 묻는 질문은 문서 질문이다 ("필수 정지가 뭐야?", "재공 경고 기준은?")
    def_extra = DEF_EXTRA_V4 if v4 else DEF_EXTRA_V3
    if (DEFINITION.search(q) or (v3 and def_extra.search(q))) and not (equipment or start or lot or order) and "자꾸" not in q \
            and not (v6 and ops_clause_v6(q, def_extra)):   # 5차 L4: 정의를 묻지 않는 마디의 운영 의도는 지우지 않는다 (E4-030)
        intents = []
    if v4 and HYPO_V4.search(q) and not (lot or order or start):
        # 가정 질문("36개짜리 로트면 … 몇 개")은 문서의 기준을 묻는다. 날짜·로트·작업지시가 있으면 진짜 운영 질문이라 건드리지 않는다
        # ("어제 야간 실적 몇 개야? 90개면 목표 채운 거지?")
        intents = []
    if outside and not any(i in DATED_INTENTS_V4 for i in intents):
        outside = None
    if v5 and start is None and "알람" not in q and WSH_HEAT_V5.search(q) and not COUNT_WORDS_V5.search(q):
        # L2 세척기 과열: "WSH-01은 몇 도에서 멈추고 …"는 설비 상태가 아니라 알람 WSH-01을 묻는다 (E3-069).
        # 날짜·횟수 말이 있으면 운영 조회 그대로 ("어제 WSH-01 과열로 몇 번 섰어?"). "세척기" 별명이 설비로 다시 들어가지 않게 뺀다
        mw = WSH_ALARM_V5.search(q)
        code = mw.group(1).upper() if mw else None
        if code is None and v6 and WSH_NAME_V6.search(q) and "과열" in q and HEAT_DEG_V6.search(q):
            code = "WSH-01"   # 5차 L1: 설비 ID 없이 "세척기 과열 … 몇 도" (E4-036)
        if code and code in master:
            if code not in [a["code"] for a in alarms]:
                alarms.append({"control": master[code]["control"], "axis": "", "code": code, "sub": ""})
            equipment = [e for e in equipment if e != "WSH-01"]
            intents = [i for i in intents if i != "equipment_status"]
    past_n = past_action_n_v22(q)   # 질문대로 답하기 1단계: 정의 질문 판정이 의도를 지운 뒤에 붙인다 ("…조치가 뭐였어?"의 '뭐')
    if past_n is not None and "work_records" not in intents:
        intents.append("work_records")
    out = {"alarms": alarms, "equipment": equipment, "start": start, "end": end, "shift": shift, "intents": intents,
           "lot": lot.group(0).upper() if lot else None, "order": order.group(0).upper() if order else None}
    if past_n is not None:
        out["past_n"] = past_n
    if v4 and future:  # 기준 시각 뒤 날짜 — 날짜로 찾는 조회면 _answer가 "확인 필요"로 알린다 (한 달 전체로 넓히지 않음)
        out["future"] = True
    if outside:  # 데이터 기간 밖의 달 (PARSE_V5) — _answer가 "확인 필요"로 알린다
        out["outside"] = outside
    return out


# ---------------------------------------------------------------- 문서 쪽
def _rows(chunk: Chunk) -> list[list[str]]:
    out = []
    for line in chunk.text.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                out.append(cells)
    return out


def _field(chunk: Chunk, name: str) -> str:
    for cells in _rows(chunk):
        if len(cells) >= 2 and cells[0] == name:
            return cells[1]
    return ""


def _chunk(doc_id: str, sec: str) -> Chunk | None:
    return next((c for c in load_corpus() if c.doc_id == doc_id and c.section == sec), None)


def _cite(c: Chunk, snippet: str = "") -> dict:
    # doc_no·rev는 API명세서_v1 공통 규칙의 출처 칸 이름 {doc_name, doc_no, rev, section} (2026-10-11 P1).
    # 화면이 옮겨 갈 때까지 옛 칸(doc_id·revision)도 둔다. 값은 같다 — services/cite.evidence와 같은 모양
    plain = re.sub(r"\s+", " ", re.sub(r"[|#*]", " ", c.text)).strip()
    return {"cite": c.cite, "doc_id": c.doc_id, "doc_name": c.doc_name, "revision": c.revision, "section": c.section,
            "title": c.title, "snippet": snippet or plain[:160], "doc_no": c.doc_id, "rev": c.revision}


def _clean(s: str) -> str:
    s = re.sub(r"\[(실제|참고|가상|제안)\]", "", s.replace("**", "")).strip().strip("|")
    s = re.sub(r"\s+", " ", re.sub(r"\s*\|\s*", " · ", s)).strip(" ·")
    return re.sub(r"\s+([.,])", r"\1", s)  # 꼬리표를 지운 자리에 남는 " ." 정리


def alarm_name_v9(m: dict) -> str:
    """8차 (FLOW_V9, E7-094 "알람 991 영문 이름이 뭐였지?"·E6-008): 카드 이름에 영문명을 붙인다 (규칙 4.1 — 알람 번호·영문명·한국어명).
    알람 마스터의 name_en(DOC-02 "영문 이름" 칸에서 만든 값, 지침카드도 같은 칸을 씀). 한국어 이름에 이미 영문이 들어 있으면(992·230)
    다시 붙이지 않고, 영문 칸이 없는 조작 안내 알람은 한국어 이름만. 꼴은 992 마스터와 같은 "한국어(영문)"."""
    ko, en = m.get("name_ko") or "", (m.get("name_en") or "").strip()
    if not en or en.lower() in ko.lower():
        return ko
    return f"{ko}({en})"


def alarm_doc_answer(a: dict, en: bool = False) -> tuple[str, list[str], list[dict]] | None:
    m = alarm_codes().get(a["code"])
    if not m:
        return None
    d2 = _chunk("DOC-02", m["doc02_section"].split("§")[1]) if "§" in m["doc02_section"] else None
    d3 = _chunk("DOC-03", m["doc03_section"].split("§")[1]) if "§" in m["doc03_section"] else None
    key = f"{a['axis']}.{a['code']}" if a["axis"] else a["code"]
    easy = _clean(_field(d2, "쉬운 설명")) if d2 else ""
    sev, who = m["severity_ko"], m["who"]
    conclusion = f"알람 {key} {alarm_name_v9(m) if en else m['name_ko']}"
    if easy:
        conclusion += f": {easy}" + ("" if easy.endswith(".") else ".")
    # 심각도·누가는 팀 정의라 DOC-02가 [가상]을 붙인다. 답에도 그 꼬리표를 그대로 옮긴다 (규칙 2.2·4.1, 2026-10-08)
    tag = lambda name: " [가상]" if d2 is None or "[가상]" in _field(d2, name) else ""  # noqa: E731
    conclusion += f" 심각도는 {sev}{tag('심각도')}, 조치는 {who}{tag('누가 조치')}입니다."
    steps = [f"{s['no']} ({s['who']}) {s['text']}" for s in doc03_steps(m["doc03_section"], a["code"])]
    evidence = [_cite(c) for c in (d2, d3) if c]
    return conclusion, steps, evidence  # 점검 순서는 자르지 않는다 (2026-10-08: 6개에서 잘라 552의 7·8단계가 빠졌음)


def doc03_steps(ref: str, code: str) -> list[dict]:
    """DOC-03 알람 절의 점검 순서 (지침카드 "먼저 할 일"과 비서 답이 같이 쓴다).

    - 머리가 "# | 누가 | 할 일"인 **점검 순서 표만** 읽는다. 첫 칸이 숫자인 다른 표(알람 번호 목록 등)는 읽지 않는다.
    - 절이 검색 조각 여러 개로 나뉘어도 모두 읽는다. 개수를 자르지 않는다.
    - 조작 안내 공통 절(점검 순서 표가 없음)은 "공통 순서"(★1→★2→★3)와 **그 알람 번호의 줄**만 쓴다.
    """
    if "§" not in ref:
        return []
    doc, sec = (x.strip() for x in ref.split("§"))
    text = "\n".join(c.text for c in load_corpus() if c.doc_id == doc and c.section == sec)
    lines = text.splitlines()
    steps, header = [], None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        if SEP.fullmatch(s):
            continue
        cells = [c.replace("**", "").strip() for c in _cells(s)]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if header is None and SEP.fullmatch(nxt or "x"):
            header = cells
            continue
        if header and "누가" in header and "할 일" in header and re.fullmatch(r"★?\d+", cells[0]):
            steps.append({"no": cells[0], "who": cells[header.index("누가")], "text": _clean(cells[header.index("할 일")]),
                          "operator": cells[0].startswith("★")})
    if steps:
        return steps
    # 다른 공정 알람(§3.x): 점검 순서가 "점검" 칸 한 줄에 "★1 … / ★2 … / 4 …"로 이어져 있다. ★ = 작업자 줄(DOC-03 §1.1)
    for line in lines:
        cells = [c.replace("**", "").strip() for c in _cells(line)] if line.strip().startswith("|") else []
        if len(cells) >= 2 and cells[0] == "점검":
            for part in cells[1].split(" / "):
                m = re.match(r"\s*(★?\d+)\s+(.+)", part)
                if m:
                    star = m.group(1).startswith("★")
                    steps.append({"no": m.group(1), "who": "작업자" if star else "보전", "text": _clean(m.group(2)), "operator": star})
            if steps:
                return steps
    common = re.search(r"공통 순서:\**\s*(.+)", text)
    if not common:
        return []
    own = None
    header = None
    for i, line in enumerate(lines):  # 그 알람 번호의 줄 ("알람 | 볼 곳 | 고치는 법" 표)
        s = line.strip()
        if s.startswith("|") and not SEP.fullmatch(s):
            cells = [c.replace("**", "").strip() for c in _cells(s)]
            if header is None and i + 1 < len(lines) and SEP.fullmatch(lines[i + 1].strip() or "x"):
                header = cells
            elif header and cells[0] == code:
                own = " · ".join(f"{h}: {_clean(v)}" for h, v in zip(header[1:], cells[1:]) if _clean(v))
    for part in common.group(1).split("→"):
        m = re.match(r"\s*\**(★\d+)\**\s*(.+)", part)
        if not m:
            continue
        steps.append({"no": m.group(1), "who": "작업자", "text": _clean(m.group(2)), "operator": True})
        if m.group(1) == "★2" and own:
            steps.append({"no": "★2-1", "who": "작업자", "text": f"알람 {code} — {own}", "operator": True})
    return steps


# 2026-10-19: 알람 답의 "가능한 원인". 사용자가 원인·이유·왜를 물으면 DOC-03 그 알람 절의 원인 표를 **원문 그대로** 카드 뒤에 붙인다(LLM을 거치지 않는다).
# 이전에는 알람 답이 "쉬운 설명 + 점검 순서 표"만 쓰고 이 표를 읽는 코드가 없었고, 질문의 "원인·이유·왜"는 ALARM_PLAIN_V9에 들어 "카드가 이미 다루는 말"로 취급돼
# 문서 추가 검색도 안 했다(카드에는 원인 표가 없는데). 분석: 261003_창민/알람_원인_질문_가능한원인_누락_분석_20261019.md
CAUSE_Q = re.compile(r"원인|이유|왜|때문")
CAUSE_POSSIBLE = re.compile(r"가능한\s*(원인|이유)")     # "가능한 원인이 뭐야?"의 "가능한"은 주제 낱말이 아니라 원인 질문의 일부다
CAUSE_HEAD = "가능한 원인(사내 문서): "


def cause_question(question: str) -> bool:
    """알람 질문이 원인을 묻나 (원인·이유·왜·때문 — 정책 규칙 DEFECT_CAUSE(불량 원인)는 이 함수보다 앞에서 걸러진다)."""
    return bool(CAUSE_Q.search(question))


def _plain_cell(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("**", "")).strip()


def doc03_causes(ref: str) -> list[str]:
    """DOC-03 알람 절의 원인 줄 (원문 그대로, 새로 쓰지 않는다 — 문서 규칙 "원문이 실제로 적은 원인만").

    - §2.x(OP-30): "가능한 원인" 표의 **모든 행**(원인 글). 문서 원본에는 "근거 수준·출처" 열이 있으나 **검색 조각에서 D-03(원문 출처 비표시)에 따라 지워져 있어**(rag/sanitize.py
      SOURCE_COLUMN) 답에도 보이지 않는다 — 우회하지 않는다. 출처는 답의 출처 알약(사내 문서 이름·번호·§)이 맡는다.
    - §3.x(다른 공정): "칸 | 내용" 표의 "원인 후보" 한 줄을 "원인 후보: …"로 ([가상] 꼬리표 그대로).
    - 절이 검색 조각 여러 개로 나뉘어도 모두 읽는다. 표가 없으면 빈 목록(→ 붙이지 않는다)."""
    if "§" not in ref:
        return []
    doc, sec = (x.strip() for x in ref.split("§"))
    lines = "\n".join(c.text for c in load_corpus() if c.doc_id == doc and c.section == sec).splitlines()
    out, header = [], None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        if SEP.fullmatch(s):
            continue
        cells = [c.replace("**", "").strip() for c in _cells(s)]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if header is None and SEP.fullmatch(nxt or "x"):
            header = cells
            continue
        if not header or not cells or not cells[0]:
            continue
        if header[0] == "가능한 원인":
            out.append(_plain_cell(cells[0]))
        elif header[0] == "칸" and cells[0] == "원인 후보" and len(cells) > 1 and cells[1]:
            out.append(f"원인 후보: {_plain_cell(cells[1])}")
    return out


def focus_words(question: str) -> set[str]:
    """질문의 핵심 낱말: "무엇을 X", "X는 어떻게/뭐야/…"의 X (조사·어미를 뗀 꼴)."""
    out = set()
    for pat in FOCUS:
        for m in pat.finditer(question):
            out.update(content_words(m.group(1)))
    return out


@lru_cache(maxsize=1)
def corpus_words() -> tuple[str, ...]:
    """사내 문서(검색 조각)에 나오는 모든 한글·영숫자 낱말 (조사가 붙은 꼴 그대로)."""
    words = set()
    for c in load_corpus():
        words.update(re.findall(r"[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", (c.title + " " + c.text).lower()))
    return tuple(sorted(words))


def unknown_terms(question: str) -> list[str]:
    """사내 문서 어디에도 (조사가 붙은 꼴로도) 나오지 않는 질문 낱말. 동사·부사 꼴로 끝나는 낱말은 세지 않는다.
    이런 낱말이 있으면 그 개념은 문서에 없다고 본다 (예: "주차장", "월급날")."""
    syn = synonyms()
    vocab = corpus_words()
    out = []
    for w in content_words(question):
        if not re.fullmatch(r"[가-힣]{2,}", w) or w.endswith(VERB_TAIL) or w in syn:
            continue
        if not any(w in v for v in vocab):
            out.append(w)
    return out


def doc_search_answer(question: str) -> tuple[str, list[dict], float] | None:
    got = _doc_search(question)
    return (got["conclusion"], got["evidence"], got["score"]) if got else None


# 8차 ④ (FLOW_V9): 알람 + 문서 함께 답할 때, 카드가 이미 보인 줄(그 알람 DOC-03 절의 점검 순서 행, DOC-02 절의 번호·이름·쉬운 설명·
# 심각도·누가 칸)은 문서 쪽 후보 줄에서 뺀다 — 점검 순서는 LLM에 보내지 않고(규칙 3.4) 같은 글을 두 번 보이지 않는다.
# 절을 통째로 빼지 않는다: E6-032 "이 알람은 프로그램 돌아가는 중에도 떠요?"의 답은 그 알람 DOC-03 절의 "증상·알람" 줄에 있다
CARD_FIELDS_V9 = ("알람 번호", "영문 이름", "한국어 이름", "쉬운 설명", "심각도", "누가 조치", "고장 대응")
STEP_ROW_V9 = re.compile(r"★?\d+(?:-\d+)? — 누가: ")


def card_line_v9(c: Chunk, text: str, own) -> bool:
    """이 줄이 알람 카드가 이미 보인 줄인가 (own = 그 알람의 (doc_id, 절) 묶음)."""
    if not own or not any(c.doc_id == d and (c.section == sec or c.section.startswith(sec + ".")) for d, sec in own):
        return False
    if c.doc_id == "DOC-03":
        return bool(STEP_ROW_V9.match(text))
    return c.doc_id == "DOC-02" and any(text.startswith(f + " · ") for f in CARD_FIELDS_V9)


# 9차 FLOW_V10 (1부 원인 D): DOC-02 "원문 설명" 칸은 카드의 쉬운 설명과 같은 뜻이라 보일 줄에서 뺀다.
# LLM 후보 줄(card_line_v9)에서는 빼지 않는다 — 처음 판은 후보에서 뺐는데, 답 줄(DOC-03 §2.10 "증상·알람")이 그대로 있는데도
# 후보 한 줄이 빠지자 줄 고르기가 "답할 줄 없음"으로 바뀌어 E7-096 "2073은 … 몇 번 연속으로"를 잃었다(빠른 확인, 번갈아 3번 모두 같음,
# 2026-10-13). 그래서 고르기·따로 검증·코드 검사가 step11과 같은 줄을 본 뒤에, 보일 줄에서만 뺀다.
ORIG_FIELD_V10 = "원문 설명 · "


def drop_card_orig_v10(lines: list[str], cites: list[dict], own) -> tuple[list[str], list[dict]]:
    """보일 줄에서 그 알람 DOC-02 절의 "원문 설명" 줄을 뺀다(cites = 줄마다 출처). 모두 빠지게 되면 그대로 둔다."""
    if not own or len(cites) != len(lines):
        return lines, cites

    def orig(t: str, lc: dict) -> bool:
        return (t.startswith(ORIG_FIELD_V10) and lc.get("doc_id") == "DOC-02"
                and any(d == "DOC-02" and (lc.get("section") == sec or str(lc.get("section")).startswith(sec + ".")) for d, sec in own))

    keep = [i for i, (t, lc) in enumerate(zip(lines, cites)) if not orig(t, lc)]
    if not keep or len(keep) == len(lines):
        return lines, cites
    if SL.on():   # STEP_LOG: 보인 줄 거르기 — 알람 카드와 같은 뜻인 DOC-02 "원문 설명" 줄을 뺐다
        SL.step("보인 줄 거르기", 종류="카드와 같은 뜻인 원문 설명 줄", 뺀수=len(lines) - len(keep), 전=_sl_lines(lines), 후=_sl_lines([lines[i] for i in keep]))
    return [lines[i] for i in keep], [cites[i] for i in keep]


def _doc_search(question: str) -> dict | None:
    """문서 검색 + 줄 고르기(기본). LLM 고르기에 쓸 후보 조각(reranked)과 절차 질문 여부도 돌려준다."""
    unknown = unknown_terms(question)
    if unknown:
        if SL.on():   # STEP_LOG 3단계: 1차 문지기(낱말) — 사내 문서에 없는 낱말이 있으면 찾지 않고 막는다
            SL.step("3 찾기", 질문=question, 길="1차 문지기", 통과=False, 까닭="사내 문서에 없는 낱말", 낱말=unknown[:8])
        return None
    if v7_on() and no_subject_v7(question):   # 6차: 찾을 주제가 없는 질문
        if SL.on():
            SL.step("3 찾기", 질문=question, 길="1차 문지기", 통과=False, 까닭="찾을 주제 낱말이 없음")
        return None
    qs = strip_shape_v7(question) if v7_on() else question   # 6차: 답 모양 낱말은 검색 낱말에서 뺀다
    hits = search(qs, 15)
    dense = dense_search(qs, 15) if settings().retrieval == "hybrid" else None
    if not hits and not dense:
        if SL.on():
            SL.step("3 찾기", 질문=question, 길="1차 문지기", 통과=False, 까닭="검색 결과 없음")
        return None
    words = content_words(question)
    syn = synonyms()

    def has(w, body):
        return w in body or bool(syn.get(w) and syn[w].lower() in body)

    def title_ratio(c):  # 절 제목이 질문 낱말을 많이 담을수록 위로 (예: "측정 결과 자동 기록" → DOC-06 §3.6)
        t = c.title.lower()
        return sum(1 for w in words if has(w, t)) / max(len(words), 1)

    def rank(h):
        r = title_ratio(h[1])
        full = 1.3 if r == 1 else 1.0
        return -(h[0] * (1 + r) ** 2 * full)

    def overlap(c):
        body = (c.title + " " + c.text).lower()
        return sum(1 for w in words if has(w, body)) / max(len(words), 1)

    reranked = sorted(hits, key=rank)
    retrieval = {"mode": settings().retrieval, "dense_used": False, "reason": None}
    # 답할지("문서에 없음"인지)와 기본 답은 BM25 경로 그대로 정한다 (2026-10-08 실측: 하이브리드 1위로 정하면
    # 조정용 D01·D02·D25의 절이 바뀌고, 벡터만의 문턱은 "문서에 없음" 문항과 겹쳐 정할 근거가 없었다).
    # 하이브리드는 LLM 고르기의 후보 조각만 넓힌다.
    if not reranked:
        return None
    score, top = reranked[0]
    if v6_on() and overlap(top) < MIN_OVERLAP:
        # 5차 L6 근소 동점: 1등이 낱말 겹침 문턱을 못 넘을 때, 다시 줄 세운 점수가 1등과 아주 가까운(NEAR_TIE_V6) 다음 후보가
        # 문턱을 넘으면 그 조각을 쓴다 (E088 — 원문 이름 고침으로 조각 길이가 바뀌어 30.50 대 30.30으로 뒤집혔다)
        r0 = -rank(reranked[0])
        for h in reranked[1:3]:
            if -rank(h) >= r0 * (1 - NEAR_TIE_V6) and h[0] >= MIN_SCORE and overlap(h[1]) >= MIN_OVERLAP:
                reranked = [h] + [x for x in reranked if x is not h]
                score, top = h
                break
    if SL.on():   # STEP_LOG 3단계: 1차 문지기(낱말 검색) — 상위 조각과 점수, 낱말 겹침이 문턱을 넘었나
        SL.step("3 찾기", 질문=question, 길="1차 문지기", 통과=bool(score >= MIN_SCORE and overlap(top) >= MIN_OVERLAP),
                점수=round(score, 2), 점수문턱=MIN_SCORE, 낱말겹침=round(overlap(top), 2), 겹침문턱=MIN_OVERLAP,
                상위=[{**_sl_chunk(c), "점수": round(s_, 2)} for s_, c in reranked[:5]])
    if score < MIN_SCORE or overlap(top) < MIN_OVERLAP:
        return None
    second = [c for s_, c in reranked[1:2] if s_ >= score * 0.85]
    candidates = [c for s_, c in reranked[:3] if s_ >= score * 0.5]
    if dense:
        order = rrf([c for _, c in reranked], [c for _, c in dense])
        candidates = [top] + [c for c in order if c.chunk_id != top.chunk_id][:2]
        retrieval.update(dense_used=True)
    elif settings().retrieval == "hybrid":
        retrieval["reason"] = f"뜻으로 찾기 못 씀 → BM25 후보만 ({dense_last_error()})"
    best = pick_lines(qs, words, top, has)
    conclusion = " / ".join(best) if best else _clean(top.text[:200])
    evidence = [_cite(top)] + [_cite(c) for c in second]
    procedure = bool(PROCEDURE.search(question)) and not CRITERIA.search(question)
    return {"conclusion": conclusion, "evidence": evidence, "score": score, "procedure": procedure,
            "candidates": candidates, "retrieval": retrieval}


def plain_lines(chunk: Chunk) -> list[str]:
    """조각의 줄을 답 문장 꼴로 (pick_lines와 같은 변환: 3열 이상 표는 머리 이름을 붙임). LLM 고르기 후보로 쓴다."""
    raw, out, header = chunk.text.splitlines(), [], None
    for i, line in enumerate(raw):
        s = line.strip()
        nxt = raw[i + 1].strip() if i + 1 < len(raw) else ""
        if not s.startswith("|"):
            header = None
        elif SEP.fullmatch(nxt or "x"):
            header = _cells(s)
            continue
        elif SEP.fullmatch(s):
            continue
        if s.startswith("|") and header and len(header) >= 3:
            cells = _cells(s)
            plain = _clean(cells[0]) + " — " + " · ".join(f"{_clean(h)}: {_clean(v)}" for h, v in zip(header[1:], cells[1:]) if _clean(v))
        else:
            plain = _clean(line)
        if len(plain) >= 8 and not set(plain) <= set("-: |·—"):
            out.append(plain)
    return out


def _head(chunk: Chunk) -> str:
    return f"[{chunk.doc_name} {chunk.doc_id} §{chunk.section} {chunk.title}]"


RECENT_RECORDS = 4  # 작업기록은 최근 4건만 문장에 넣고, 넘으면 전체 건수를 밝힌다
MAX_TABLE_ROWS = 12  # 절차 질문에서 표를 옮길 때 한 번에 보이는 줄 수. 넘으면 "외 N줄"을 붙인다
PROCEDURE = re.compile(r"단계|순서|방법|절차|어떻게 점검|어떻게 재|무엇을 점검")
SEP = re.compile(r"\|?[\s\-:|]+\|?")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def pick_lines(question: str, words: list[str], chunk: Chunk, has) -> list[str]:
    """근거 조각에서 답 문장을 고른다. 문장은 조각 안의 글을 그대로 옮기며 새로 만들지 않는다.

    - 표 행은 3열 이상이면 머리 이름을 붙여 옮긴다 ("경고: 20개 초과").
    - 절차 질문: 점수가 가장 높은 표의 행을 문서 순서대로 (최대 6줄)
    - 그 밖: 질문 낱말·숫자가 많이 들어 있고, 첫 칸이 질문 대상인 줄 (최대 3줄)
    """
    raw = chunk.text.splitlines()
    numbers = set(re.findall(r"\d+", question))
    focus = focus_words(question)
    criteria = bool(CRITERIA.search(question))
    procedure = bool(PROCEDURE.search(question)) and not criteria
    weight = {w: (2 if w in focus else 1) for w in words}
    cand, header, table_no, caption, crit_tables = [], None, 0, "", set()
    for i, line in enumerate(raw):
        s_line = line.strip()
        nxt = raw[i + 1].strip() if i + 1 < len(raw) else ""
        if not s_line.startswith("|"):
            header = None
            if s_line:
                caption = s_line
        elif SEP.fullmatch(nxt or "x"):
            header, table_no = _cells(s_line), table_no + 1
            if any(CRITERIA_HEADER.search(h) for h in header[1:]):
                crit_tables.add(table_no)
            continue  # 표 머리 줄은 답 문장으로 쓰지 않는다
        elif SEP.fullmatch(s_line):
            continue
        if s_line.startswith("|") and header and len(header) >= 3:
            cells = _cells(s_line)
            plain = _clean(cells[0]) + " — " + " · ".join(f"{_clean(h)}: {_clean(v)}" for h, v in zip(header[1:], cells[1:]) if _clean(v))
        else:
            plain = _clean(line)
        if len(plain) < 8 or set(plain) <= set("-: |·—"):
            continue
        low = plain.lower()
        first = _clean(_cells(s_line)[0]).lower() if s_line.startswith("|") else ""
        s = 2 * sum(weight[w] for w in words if has(w, low)) + 0.5 * sum(1 for t in tokens(question) if t in low)
        s += 3 * sum(1 for n in numbers if re.search(rf"(?<!\d){n}(?!\d)", low))
        s += 1.5 * sum(1 for w in words + list(numbers) if w and first and (first == w or w in first))
        if criteria and UNIT.search(low):  # 기준 질문은 숫자+단위가 든 줄(조건·한도)을 앞으로
            s += 3
        tbl = table_no if s_line.startswith("|") else 0
        cap = 2 * sum(weight[w] for w in words if has(w, caption.lower())) if tbl else 0
        if criteria and tbl in crit_tables:  # 머리에 조건·언제·기준·한도 칸이 있는 표
            cap += 4
        cand.append((i, s, plain, tbl, cap))
    if procedure or (criteria and crit_tables):
        tables = {}
        for i, s, p, tbl, cap in cand:
            if tbl:
                tables.setdefault(tbl, [0.0, []])
                tables[tbl][0] += s
                tables[tbl][1].append((i, p, cap))
        if tables:
            best = max(tables.values(), key=lambda t: t[0] / len(t[1]) + t[1][0][2])
            if len(best[1]) >= 2:
                rows = [p for _, p, _ in best[1]]
                if len(rows) > MAX_TABLE_ROWS:  # 자를 때는 반드시 남은 줄 수를 밝힌다 (말없이 자르지 않음)
                    return rows[:MAX_TABLE_ROWS] + [f"… 외 {len(rows) - MAX_TABLE_ROWS}줄 — 출처를 눌러 전체를 봅니다"]
                return rows
    cand.sort(key=lambda x: (-x[1], x[0]))
    return [p for i, s, p, _, _ in cand[:3] if s > 0]


# ---------------------------------------------------------------- 운영 쪽
def _range_text(p):
    if p["start"] and p["end"] and p["start"] == p["end"]:
        return f"{p['start'].isoformat()}" + (" 야간" if p["shift"] == "N" else " 주간" if p["shift"] == "D" else "")
    if p["start"]:
        return f"{p['start']} ~ {p['end']}"
    return "2026-09-01 ~ 2026-09-30"


def stops_pieces(r: dict, rng: str, eq: str | None) -> tuple[str, list[str], list[str]]:
    """정지 답의 조각 (머리, 사유 그룹들, 교대 보고서 기준 세 줄) — stops_text와 줄 목록 칸(8차 BLOCKS_V2)이 같이 쓴다."""
    groups = []
    for g in r["by_group"]:
        s = f"{g['group_ko']} {g['count']}번" + (f" {g['minutes']:g}분" if g["count"] else "")
        if g["reasons"]:
            s += "(" + ", ".join(f"{x['name']} {x['count']}번 {x['minutes']:g}분" for x in g["reasons"]) + ")"
        groups.append(s)
    cyc = r["cycle_min"]
    basis = ("기준 사이클 " + ", ".join(f"{k} {v:.1f}분" for k, v in cyc.items())) if cyc else "그 설비의 기준 사이클"
    if r.get("partial"):   # [11_automotive 이식 2026-10-16] 백엔드 조회 도구는 손실 정지만 준다 — "정지 전체"·필수 정지·순간 정지는 말하지 않는다
        return (f"{rng} {eq or '라인 전체'} 손실 정지 {r['total_count']}번 {r['total_minutes']:g}분", groups,
                [f"고장 손실 약 {r['loss_qty_est_total']}개(추정 = 정지 1건마다 정지 시간 ÷ {basis})"])
    head = f"{rng} {eq or '라인 전체'} 정지 전체 {r['total_count']}번 {r['total_minutes']:g}분"
    report = [f"필수 정지(고장 5분 이상) {len(r['rows'])}번 {r['total_failure_min']:g}분",
              f"고장 손실 약 {r['loss_qty_est_total']}개(추정 = 정지 1건마다 정지 시간 ÷ {basis})",
              f"순간 정지(조작 5분 미만) {r['micro_count']}번 {r['micro_minutes']:g}분"]
    return head, groups, report


def stops_text(r: dict, rng: str, eq: str | None) -> str:
    """정지 답: 멈춘 기록 전부를 사유 그룹별로 + 교대 보고서 기준(필수 정지·순간 정지) + 손실 계산식 (DOC-07 §5.1·§5.3·§5.4)."""
    head, groups, report = stops_pieces(r, rng, eq)
    if r.get("partial"):   # [11_automotive 이식 2026-10-16] "교대 보고서 기준"이 아니라 손실 추정 한 줄
        return head + " — " + " · ".join(groups) + ". " + ", ".join(report)
    return head + " — " + " · ".join(groups) + ". 교대 보고서 기준: " + ", ".join(report)


def ops_answer(role: str, p: dict, needs: list[str] | None = None,
               entries: list[dict] | None = None) -> tuple[list[str], list[dict], list[dict]]:
    """운영 조회 답 문장·조회 결과·문장에 쓴 정의의 사내 문서 출처.
    needs를 주면(PARSE_V2) 조회에 필요한데 질문에 없는 항목(설비·로트 번호·알람 번호)을 모은다 — 예전에는 말없이 건너뛰었다.
    entries를 주면(8차 BLOCKS_V2) 답 문장마다 머리 + 항목 목록을 모은다 — 화면이 번호 목록으로 보인다. 문장 글자는 바꾸지 않는다."""
    texts, data, defs = [], [], []
    eq = p["equipment"][0] if p["equipment"] else None
    kw = dict(start=p["start"], end=p["end"], shift=p["shift"])
    rng = _range_text(p)

    def add(head: str, items: list[str], text: str, r: dict | None, notes: tuple[str, list[str]] | None = None) -> None:
        if entries is not None:   # items가 비면 화면은 text 한 줄로 보인다
            entries.append({"head": head, "items": list(items), "text": text,
                            "source": {k: r.get(k) for k in ("tool", "range", "as_of", "label")} if r else None})
            if notes:   # 9차 BLOCKS_V3 (F): 다른 종류의 줄은 작은 제목 + 따로 목록
                entries[-1].update(notes_head=notes[0], notes=list(notes[1]))

    for intent in p["intents"]:
        if intent == "stops":
            r = T.stops(role, eq, **kw)
            data.append(r)
            if r["all_empty"]:
                texts.append(f"{rng} {eq or '라인'} 정지 기록: 데이터 없음")
                add("", [], texts[-1], r)
            else:
                texts.append(stops_text(r, rng, eq))
                head, groups, report = stops_pieces(r, rng, eq)
                lead_ko = "손실 추정" if r.get("partial") else "교대 보고서 기준"   # [11_automotive 이식 2026-10-16]
                if blocks3_on():   # 9차 F: 사유 그룹(번호 목록)과 교대 보고서 기준(작은 제목 + 따로 목록)을 나눈다
                    add(head, groups, texts[-1], r, notes=(lead_ko, report))
                else:
                    add(head, groups + [lead_ko + " — " + x for x in report], texts[-1], r)
                # 사유 그룹·필수 정지·손실 계산식의 정의 출처
                defs += [_cite(c) for c in (_chunk("DOC-07", "5.1"), _chunk("DOC-07", "5.4"), _chunk("DOC-07", "5.3")) if c]
        elif intent == "production":
            r = T.production(role, **kw)
            data.append(r)
            if r["empty"]:
                texts.append(f"{rng} 생산 실적: 데이터 없음 (가상 데이터 기간 2026-09-01 ~ 09-30)")
                add("", [], texts[-1], r)
            rows_txt = []
            for row in r["rows"]:
                texts.append(f"{row['prod_date']} {'주간' if row['shift'] == 'D' else '야간'} 실적 {row['output']}개 "
                             f"(목표 {row['target']}개), 불량 {row['scrap']}개, 보고서 {row['report_id']} {row['status']}")
                rows_txt.append(texts[-1])
            if rows_txt:   # 실적 줄은 한 줄씩 따로 문장이다 — 머리에 숫자를 넣지 않는다(숫자 대조가 맞게)
                add("생산 실적", rows_txt, " ".join(rows_txt), r)
        elif intent == "inventory":
            r_all = T.inventory(role)
            asked = inventory_items_asked_v22(p.get("raw", ""), r_all["rows"])
            if asked:   # 질문대로 답하기 1단계: 질문에 품목이 있으면 그 품목만, 부족분은 프로그램이 계산
                r = {**r_all, "rows": asked, "empty": False}
                data.append(r)
                sentences = [inventory_sentence_v22(x) for x in asked]
                texts.append("재고: " + " ".join(sentences))
                add("재고 확인", sentences, texts[-1], r)
                continue
            r = r_all
            if "부족" in p.get("raw", ""):
                r = {**r_all, "rows": [x for x in r_all["rows"] if x["short"] == "true"]}
                r["empty"] = not r["rows"]
            data.append(r)
            short = [i for i in r["rows"] if i["short"] == "true"]
            items = [f"{i['name']} {float(i['on_hand']):g}{i['unit']} (안전 재고 {i['safety_stock']})" for i in short]
            texts.append("재고 부족: " + (", ".join(items) or "없음"))
            add("재고 부족", items, texts[-1], r)
        elif intent == "tool_life":
            r = T.tool_life(role, eq, min_pct=90 if not eq else 0)
            data.append(r)
            rows = r["rows"]  # 설비를 정하면 그 설비 공구 전부, 아니면 90% 이상 전부 (자르지 않음)
            items = [f"{t['equipment_id']} {t['tool_no']} {t['tool_name']} {t['usage_pct']}% ({float(t['used']):g}/{t['limit']})" for t in rows]
            texts.append("공구 수명: " + (", ".join(items) or "90% 이상 없음"))
            add("공구 수명", items, texts[-1], r)
        elif intent == "kpi" and eq:
            r = T.kpi(role, eq, **kw)
            data.append(r)
            if r["empty"]:
                texts.append(f"{eq} 지표: 데이터 없음")
            else:
                k = r["rows"][0]
                texts.append(f"{eq} {rng}: OEE {k['oee_pct']}% (가동률 {k['availability_pct']}%, 성능 {k['performance_pct']}%, "
                             f"양품률 {k['qbr_pct']}%)")
                if not k.get("reliability_hidden"):   # [11_automotive 이식 2026-10-16] MTTR·MTBF는 MNT·MGR만 — 못 보는 역할에는 "—"도 보이지 않는다
                    mttr = "—" if k["mttr_30d_min"] is None else f"{k['mttr_30d_min']:g}분"
                    mtbf = "—" if k["mtbf_30d_h"] is None else f"{k['mtbf_30d_h']:g}시간"
                    texts[-1] += f", MTTR {mttr}, MTBF {mtbf} (30일, 고장 {k['failures_30d']}건)"
            add("", [], texts[-1], r)   # 지표는 한 문장
        elif intent == "kpi" and needs is not None:
            needs.append("설비 (예: VF2-01)")
        elif intent == "lots" and (p["lot"] or p["order"]):
            r = T.lots(role, p["lot"], p["order"])
            data.append(r)
            items = [f"{l['lot_id']} {l['qty']}개 {l['status']}" for l in r["rows"]]
            if r.get("unsupported"):   # [11_automotive 이식 2026-10-16] 작업지시 번호로 로트를 찾는 조회는 백엔드 도구에 없다 — "데이터 없음"이라고 하지 않는다
                texts.append("로트: 작업지시 번호로는 아직 찾을 수 없습니다. 로트 번호(예: LOT-2609-001-1)로 물어봐 주세요")
            else:
                texts.append("로트: " + (", ".join(items) or "데이터 없음"))
            add("로트", items, texts[-1], r)
        elif intent == "lots" and needs is not None:
            needs.append("로트 번호 (예: LOT-2609-001-1) 또는 작업지시 번호")
        elif intent == "work_orders":
            r = T.work_orders(role, eq)
            data.append(r)
            items = [f"{w['work_order_id']}({w['triggers']})" for w in r["rows"]]
            texts.append(f"정비 작업지시서 {len(r['rows'])}건: " + ", ".join(items))
            add(f"정비 작업지시서 {len(r['rows'])}건", items, texts[-1], r)
        elif intent == "pm_due":
            r = T.pm_due(role, eq)
            data.append(r)
            over = [x for x in r["rows"] if x["overdue"] == "true"]
            plan = [x for x in r["rows"] if x["frequency"] == "계획"]
            over_items = [f"{x['equipment_id']} {x['item']}(기한 {x['next_due']})" for x in over]
            plan_items = [f"{x['equipment_id']} {x['next_due'][11:16]} {x['item']}" for x in plan]
            texts.append("기한 넘긴 예방 정비: " + (", ".join(over_items) or "없음")
                         + ("; 10/1 계획: " + ", ".join(plan_items) if plan else ""))
            add("기한 넘긴 예방 정비", over_items, "기한 넘긴 예방 정비: 없음", r)
            if plan:
                add("10/1 계획", plan_items, "", r)
        elif intent == "work_records":
            code = p["alarms"][0]["code"] if p["alarms"] else None
            r = T.work_records(role, eq, code)
            data.append(r)
            if p.get("past_n") is not None:   # 질문대로 답하기 1단계: "지난 두 번 조치" — 최근 N건을 최근 것부터, 조치 문장은 기록 원문 그대로
                last = list(reversed(r["rows"]))[:p["past_n"]]
                scope = " ".join(x for x in (eq, f"알람 {code}" if code else None) if x) or "라인"
                head = f"{scope} 지난 조치 (최근 {len(last)}건)"
                if last:
                    items = [past_action_line_v22(w) for w in last]
                    texts.append(head + ": " + " / ".join(items))
                    add(head, items, texts[-1], r)
                else:
                    texts.append(f"{scope} 지난 조치: 확정된 작업기록이 없습니다")
                    add("", [], texts[-1], r)
                continue
            recent = r["rows"][-RECENT_RECORDS:]
            more = f" (최근 {len(recent)}건, 전체 {len(r['rows'])}건)" if len(r["rows"]) > len(recent) else ""
            items = [f"{w['work_record_id']}({w['kind']}, {w['start'][:10]}{', 원인 ' + w['cause'] if w['cause'] else ''})" for w in recent]
            texts.append("작업기록: " + (", ".join(items) + more if recent else "데이터 없음"))
            add("작업기록" + more, items, texts[-1], r)
        elif intent == "alarm_count" and p["alarms"]:
            code = p["alarms"][0]["code"]
            r = T.alarms(role, eq, code, start=p["start"], end=p["end"], shift=p["shift"])
            data.append(r)
            by_eq = {}
            for a in r["rows"]:   # [11_automotive 이식 2026-10-16] 백엔드 알람 도구는 설비·알람별 집계(times)다 — 건별 행이 아니다
                by_eq[a["equipment_id"]] = by_eq.get(a["equipment_id"], 0) + int(a.get("times", 1))
            items = [f"{k} {v}번" for k, v in sorted(by_eq.items())]
            texts.append(f"{rng} 알람 {code} 발생: " + (", ".join(items) or "없음"))
            add(f"{rng} 알람 {code} 발생", items, texts[-1], r)
        elif intent == "alarm_count" and needs is not None:
            needs.append("알람 번호 (예: 2075)")
        elif intent == "equipment_status":
            r = T.equipment_status(role, eq)
            data.append(r)
            # [11_automotive 이식 2026-10-16] 원본은 "마지막 상태 (HH:MM까지)" — 지금 상태 조회는 "상태 (HH:MM부터 N분)" + 열린 알람·잠금
            items = [f"{s['equipment_id']} {s['last_state']} ({(s.get('since') or '')[11:16]}부터 {s.get('minutes') or 0:g}분)"
                     + (f", 알람 {s['open_alarm_code']}" if s.get("open_alarm_code") else "") + (", 잠금" if s.get("is_locked") else "") for s in r["rows"]]
            texts.append("설비 상태: " + ", ".join(items))
            add("설비 상태", items, texts[-1], r)
    return texts, data, defs


def related_line(role: str, p: dict) -> str | None:
    """관련 운영 정보 한 줄 (FR-MNT-01-08)."""
    if not p["alarms"]:
        return None
    code = p["alarms"][0]["code"]
    # [11_automotive 이식 2026-10-16] 알람 횟수는 집계(times)로 센다. 반복 알람 단계·"처리 안 된 알림 N건"은 백엔드 조회 도구에 없어 말하지 않는다
    r7 = T.alarms(role, None, code, start=REF_DATE - timedelta(days=7), end=REF_DATE - timedelta(days=1))
    r30 = T.alarms(role, None, code)
    n7, n30 = sum(int(x["times"]) for x in r7["rows"]), sum(int(x["times"]) for x in r30["rows"])
    return f"이 알람은 최근 7일 {n7}번, 30일 {n30}번 났습니다 [{DATA_LABEL}]"


# ---------------------------------------------------------------- 사람만 하는 일·설비 조작 (SCR-10 [4], FR-AST-COM-10·11)
CONTROL_OBJECT = re.compile(r"설비|기계|VF2|SAW|MIL|WSH|CMM|주축|스핀들|파라미터|설정|이송|속도|오프셋|프로그램|전원|공압|에어|문|도어|축")
CONTROL_VERB = re.compile(r"(켜|꺼|끄|정지시켜|멈춰|돌려|기동해|재시작해|리셋해|바꿔|올려|내려|변경해|수정해|움직여|열어|닫아)\s*(줘|주세요|줄래|라)")
HUMAN_ONLY = [
    (re.compile(r"승인"), "승인은 반장이 작업지시서 화면에서 합니다.", ("작업지시서 열기", "SCR-11")),
    (re.compile(r"담당자?\s*(지정|정해|배정)|지정해"), "담당자 지정은 반장이 작업지시서 화면에서 합니다.", ("작업지시서 열기", "SCR-11")),
    (re.compile(r"교대\s*보고서.*확정|확정.*교대\s*보고서"), "교대 보고서 확정은 그 교대 반장이 교대 보고서 화면에서 합니다.", ("교대 보고서 열기", "SCR-15")),
    (re.compile(r"일일\s*보고서.*확정|확정.*일일\s*보고서"), "일일 보고서 확정은 공장 관리자가 일일 보고서 화면에서 합니다.", ("일일 보고서 열기", "SCR-16")),
    (re.compile(r"작업\s*기록.*확정|확정.*작업\s*기록"), "작업기록서 확정은 보전 담당자가 작업기록서 화면에서 합니다.", ("작업기록서 열기", "SCR-12")),
    (re.compile(r"보류|해제"), "로트 보류·해제는 반장이 로트 추적 화면에서 합니다.", ("로트 추적 열기", "SCR-19")),
    (re.compile(r"알림.*처리|처리.*알림"), "알림 처리는 그 알림을 받은 사람이 알림 화면에서 합니다.", ("알림 열기", "SCR-07")),
    (re.compile(r"확정"), "확정은 권한이 있는 사람이 해당 문서 화면에서 합니다. 비서는 확정하지 않습니다.", ("문서함 열기", "SCR-18")),
]
REQUEST = re.compile(r"(해\s*줘|해\s*주세요|해\s*줄래|시켜\s*줘|좀\s*해|처리해|해\s*놔)")
# 요청 꼴 안전장치 (PARSE_V2, 2026-10-10): 시키는 꼴인데 알려·보여 같은 정보 요청이 아니고 의문사가 없으면 사람만 할 일로 본다.
# 기준선 E에서 조작·상태 변경 요청 10문항 중 3문항에 운영 데이터가 나갔다 ("보류 풀어줘" 같은 꼴을 못 알아봄)
CONTROL_VERB_V2 = re.compile(r"(켜|꺼|끄|정지시켜|멈춰|세워|돌려|기동해|재시작해|리셋해|초기화해|바꿔|올려|내려|낮춰|높여|줄여|늘려|변경해|수정해|움직여|열어|닫아|지워|삭제해)\s*(줘|주세요|줄래|라)")
REQ_END_V2 = re.compile(r"(?:줘|주세요|줄래|줄래요|주라|줘요|놔|둬|부탁해|부탁합니다|부탁드려요)\s*[.!~]*\s*$")
STATE_CHANGE_V2 = re.compile(r"(?:확정|승인|해제|처리|지정|배정|삭제|변경|수정|리셋|초기화|등록|입력|저장|보류|취소|마감|발행)\s*(?:해|하세요|해요|해라|하시오|시켜)\s*[.!~]*\s*$")
INFO_REQ_V2 = re.compile(r"(?:알려|보여|설명해|정리해|찾아|요약해|비교해|읽어|말해|가르쳐|계산해|봐)\s*(?:줘|주세요|줄래|줄래요|주라|줘요)")
QWORD_V2 = re.compile(r"누가|누구|언제|어떻게|왜|뭐|무엇|몇|어디|얼마|어느")
# 조작 요청 꼴 넓히기 (PARSE_V3, 2026-10-10 2차): 띄어 쓴 동사("정지 시켜"), 명령형 끝("눌러", "시켜"), 설비 별명·버튼 이름.
# 봉인 시험 E: "SAW-01 지금 당장 비상정지 시켜", "2호기 다시 돌려줘, 사이클 스타트 좀 눌러"를 거절 안내 대신 "문서에 없음"으로 답했다
CONTROL_VERB_V3 = re.compile(r"(켜|꺼|끄|정지\s*시켜|시켜|멈춰|세워|돌려|기동해|재시작해|리셋해|초기화해|바꿔|올려|내려|낮춰|높여|줄여|늘려"
                             r"|변경해|수정해|움직여|열어|닫아|지워|삭제해|눌러)\s*(줘|주세요|줄래|라|요)?\s*[.!~]*\s*(?:,|$)")
CONTROL_OBJECT_V3 = re.compile(CONTROL_OBJECT.pattern + r"|\d\s*호기|일호기|이호기|사이클|스타트|비상\s*정지|버튼"
                               r"|SAW-01|MIL-01|WSH-01|CMM-01|VF2-0[12]")
# 3차 (PARSE_V4): 차단기도 조작 대상 (E2-095 "CB3 차단기 원격으로 다시 올려"는 "때문에"의 "문"이 잡혀 우연히 거절되던 것)
CONTROL_OBJECT_V4 = re.compile(CONTROL_OBJECT_V3.pattern + r"|차단기|브레이커|CB\d")
# 업무 대상 낱말 (업무 밖 부탁 예외를 쓰지 않을 때) — 설비·기록·문서·알람·로트·작업지시·값·설정·ID 등
WORK_TARGET_V4 = re.compile(CONTROL_OBJECT_V4.pattern + r"|기록|문서|보고서|작업지시|작업기록|알림|알람|로트|LOT-|MW-|MR-|STP-|PO-"
                            r"|재고|정지|사유|공구|정비|값|기준|한도|결재|승인|담당|교대|검사|출하|부품|보류|해제|확정|처리|삭제|지정|배정"
                            r"|라인|공정|OP-\d|절삭유|소재|원자재|제품"
                            # 사람 배정·일 맡기기도 업무다 ("야간조 근무자 골라 줘"는 거절) — 거절이 기본이라 넓게 잡는다
                            r"|작업|근무|인원|사람|조원|당번|배치|스케줄|일정|점검|청소|업무|맡겨|맡길|시킬|시켜", re.I)


# 4차 (PARSE_V5, S1): 상태·조작 명사와 "해" 사이에 낀 말("리셋 좀 해", E3-025 — 알람 번호가 있어도 거절이 먼저다).
# "다시·지금·한 번"은 줘·주세요가 붙을 때만. "풀어"는 상태 명사(보류·잠금·인터록·LOTO) 뒤에서만 본다 — "이 문제 좀 풀어"는 거절하지 않는다.
# 끝말 추천해·골라·정해도 시키는 꼴이다 ("LOT-… 보류 풀어줘 추천해"). 업무 밖 추천 부탁은 leisure_request가 일반 흐름으로 돌린다
_CTRL_NOUN_V5 = r"(?:리셋|초기화|재시작|기동|정지|중지|변경|수정|삭제)"
_RELEASE_V5 = (r"(?:보류|잠금|인터록|인터락|도어\s*락|LOTO|홀드)\S{0,2}\s*(?:(?:좀|잠깐|잠깐만|다시|빨리|지금|얼른|당장)\s*)*풀어"
               r"\s*(?:줘|주세요|줄래|라|요|놔|둬)?\s*[.!~]*\s*(?:,|$)")
CONTROL_VERB_V5 = re.compile(
    r"(?:" + CONTROL_VERB_V3.pattern + r")"
    r"|(?:" + _CTRL_NOUN_V5 + r"\s*(?:좀|빨리|당장|얼른)\s*(?:해|시켜)\s*(?:줘|주세요|줄래|라|요)?\s*[.!~]*\s*(?:,|$))"
    r"|(?:" + _CTRL_NOUN_V5 + r"\s*(?:다시|지금|한\s*번)\s*(?:해|시켜)\s*(?:줘|주세요|줄래)\s*[.!~]*\s*(?:,|$))"
    r"|(?:" + _RELEASE_V5 + r")", re.I)
STATE_CHANGE_V5 = re.compile(r"(?:확정|승인|해제|처리|지정|배정|삭제|변경|수정|리셋|초기화|등록|입력|저장|보류|취소|마감|발행|재시작|기동|정지|중지)"
                             r"\s*(?:(?:좀|빨리|당장|얼른)\s*)?(?:해|하세요|해요|해라|하시오|시켜)\s*[.!~]*\s*(?:,|$)")
STATE_RELEASE_V5 = re.compile(_RELEASE_V5, re.I)
REQ_END_V5 = re.compile(r"(?:줘|주세요|줄래|줄래요|주라|줘요|놔|둬|부탁해|부탁합니다|부탁드려요|추천해|골라|정해)\s*[.!~]*\s*$")


def request_form_v5(question: str) -> bool:
    """request_form + 낀 말·풀어·끝말 추천해·골라·정해 (PARSE_V5). 정보 요청(알려·보여 …)과 의문사가 있으면 아니다."""
    q = question.strip()
    return (bool(REQ_END_V5.search(q) or STATE_CHANGE_V5.search(q) or STATE_RELEASE_V5.search(q))
            and not INFO_REQ_V2.search(q) and not QWORD_V2.search(q))


# 5차 (PARSE_V6, S1′): 물음표가 붙은 부탁 꼴도 시키는 꼴이다 — "초기화 좀 해 줄래?"(E4-008, LLM 끈 판에서 공구 수명 데이터가 나갔다).
# 줄래·주실래요·주시겠어요·해 줄 수 있어 + 물음표. 의문사가 있거나(QWORD_V2) 정보 요청(알려·보여 … + 줄 수 있어 포함)이면 아니다
REQ_ASK_V6 = re.compile(r"(?:줄래|줄래요|주실래요|주시겠어요|주시겠습니까|줄\s*수\s*(?:있어|있어요|있나요|있니|있을까|있을까요|있겠어))"
                        r"\s*[?？.!~]*\s*$")
INFO_REQ_V6 = re.compile(r"(?:알려|보여|설명해|정리해|찾아|요약해|비교해|읽어|말해|가르쳐|계산해|봐)"
                         r"\s*(?:줘|주세요|줄래|줄래요|주라|줘요|주실래요|주시겠어요|주시겠습니까|줄\s*수)")


def request_form_v6(question: str) -> bool:
    """request_form_v5 + 물음표가 붙은 부탁 꼴 (PARSE_V6, S1′)."""
    q = question.strip()
    return request_form_v5(q) or (bool(REQ_ASK_V6.search(q)) and not INFO_REQ_V6.search(q) and not QWORD_V2.search(q))


def leisure_request(question: str) -> bool:
    """업무 밖 추천·소개 부탁인가 (PARSE_V4): 거절 안내 대신 일반 흐름(→ 문서에 없음)으로 보낸다."""
    return bool(LEISURE_REQ_V4.search(question)) and not WORK_TARGET_V4.search(question)


# 8차 (PARSE_V9): "얘기해 줘·얘기해 줄 수 있어?"는 정보 요청이다 (E7-077 — 6차 감지 목록에는 있었고 7차 새 목록에서 빠졌다)
INFO_REQ_V9 = re.compile(r"(?:얘기|이야기)\s*(?:좀\s*)?해\s*(?:줘|주세요|줄래|줄래요|주라|줘요|주실래요|주시겠어요|주시겠습니까|줄\s*수)")


def request_form_v9(question: str) -> bool:
    """request_form_v6 + "얘기해 …"는 시키는 꼴이 아니다 (PARSE_V9)."""
    return request_form_v6(question) and not INFO_REQ_V9.search(question)


# 8차 (PARSE_V9): "리스트·목록·명단 + 줘"는 정보 요청이다 (E6-043 "기준치보다 모자란 품목 리스트 줘"를 거절했다 — 과잉 거절).
# 거절이 기본이라 좁게: 조작 동사·상태 낱말(승인·보류·해제·삭제·리셋 …)이 하나라도 있으면 지금처럼 거절한다 ("보류 로트 명단 지워 줘")
LIST_REQ_V9 = re.compile(r"(?:리스트|목록|명단)\S{0,3}\s*(?:(?:좀|다|전부|싹|한번)\s*)*(?:뽑아\s*|보여\s*)?"
                         r"(?:줘|주세요|줄래|줄래요|주라|줘요|주실래요|주시겠어요|줄\s*수\s*있어(?:요)?)\s*[?？.!~]*\s*$")
LIST_BLOCK_V9 = re.compile(_CTRL_NOUN_V5 + r"|확정|승인|해제|보류|처리|지정|배정|삭제|지워|지우|등록|취소|마감|발행|리셋|초기화|저장|입력"
                           r"|켜|꺼|끄|바꿔|올려|내려|돌려|멈춰|세워|눌러|풀어|맡겨|시켜")


def list_request_v9(question: str) -> bool:
    """"리스트·목록·명단 + 요청 끝말"이고 조작 동사·상태 낱말·허락 꼴이 하나도 없으면 True (정보 질문으로 본다)."""
    q = question.strip()
    return (bool(LIST_REQ_V9.search(q)) and not LIST_BLOCK_V9.search(q) and not CONTROL_VERB_V5.search(q)
            and not STATE_RELEASE_V5.search(q) and not PERMIT_CTRL_V8.search(q))


def request_form(question: str) -> bool:
    """사람에게 시키는 꼴인가 (PARSE_V2): 문장 끝이 줘·주세요·부탁해… 또는 \"확정해\" 같은 상태 바꾸기 명령이고,
    알려·보여 같은 정보 요청이 아니며, 의문사가 없다."""
    q = question.strip()
    return bool(REQ_END_V2.search(q) or STATE_CHANGE_V2.search(q)) and not INFO_REQ_V2.search(q) and not QWORD_V2.search(q)


BUILT_SCREENS = {"SCR-07", "SCR-09", "SCR-10", "SCR-24"}  # 묶음 A에서 만든 화면 (나머지 링크는 비활성 + 이유)
SCREEN_HELP = {
    "SCR-07": "알림 목록입니다. 규칙이 정한 알림을 처리 안 됨 / 전체로 거르고, 최근 순 또는 보고 순위 순(안전 → 긴급 → 생산 위험 → 주의 → 참고)으로 봅니다. "
              "머리의 \"전체 N건\"은 같은 설비·같은 원인을 묶은 뒤의 수입니다. [처리]는 표에 정한 사람에게만 보이고, 정지 알람은 작업기록서 확정 때 자동으로 처리됩니다.",
    "SCR-09": "지침카드입니다. 칸 순서는 고정입니다: 알람 → 심각도 → 누가 → 먼저 할 일 → 안전 → 생산 영향 → 지난 기록. "
              "먼저 할 일은 고장 대응 매뉴얼의 작업자(★) 줄이고, 안전 칸은 고정 서식이라 비서가 쓰거나 고치지 않습니다. 손실 수량은 계산식이 붙은 추정값입니다.",
    "SCR-24": "사내 문서 보기입니다. 문서 목록에서 문서를 고르면 본문을 보고, 출처를 눌러 열면 그 절로 이동합니다. 원문 출처는 화면에 표시하지 않습니다.",
    "SCR-10": "비서 창입니다. 사내 문서(DOC-01~07, 용어집)와 정해진 운영 조회로만 답하고, 근거가 없으면 \"문서에 없음\"이라고 답합니다.",
}
EXAMPLES = {
    "SCR-09": ["이 화면 설명해 줘", "{alarm} 뜨면 뭐부터 봐?", "모터 케이블 저항은 어떻게 재?"],
    "SCR-07": ["이 화면 설명해 줘", "2075가 왜 자꾸 떠?", "어제 야간 VF2-01 몇 번 멈췄어?"],
    "SCR-24": ["이 화면 설명해 줘", "쿨런트가 뭐야?", "필수 정지가 뭐야?"],
}
DEFAULT_EXAMPLES = ["992 뜨면 뭐부터 봐?", "어제 야간 VF2-01 몇 번 멈췄어?", "쿨런트가 뭐야?"]


def examples(screen: str | None, alarm: str | None = None) -> list[str]:
    items = EXAMPLES.get((screen or "").upper(), DEFAULT_EXAMPLES)
    return [q.replace("{alarm}", alarm or "992") for q in items]


def _link(label: str, screen: str) -> dict:
    ok = screen in BUILT_SCREENS
    return {"label": label, "screen": screen, "enabled": ok, "reason": None if ok else "이 화면은 다음 묶음에서 연결합니다"}


# 7차 A3 (PARSE_V8): 조작을 해도 되느냐고 묻는 허락 꼴 ("그거 다시 켜도 돼?") — 비서는 판단하지 않고 사람에게 넘긴다 (규칙 2.6).
# 6차에는 FU_PERMIT가 이어 묻기를 빼는 데만 쓰여, 앞 답 없이 물으면 "문서에 없음"이 나왔다. "써도 돼"(소모품)·의문사가 든 질문("언제 켜도 돼?")은 아니다
PERMIT_CTRL_V8 = re.compile(r"(?:켜도|꺼도|돌려도|리셋\s*해도|재기동\s*해도|재시작\s*해도|기동\s*해도|가동\s*해도|재가동\s*해도|해제\s*해도"
                            r"|(?:보류|잠금|인터록|인터락|LOTO|락|홀드)\S{0,2}\s*풀어도)\s*(?:돼|되|될|괜찮)", re.I)
PERMIT_MSG_V8 = ("설비를 다시 켜거나 끄거나 잠금·보류를 풀어도 되는지는 비서가 판단하지 않습니다. "
                 "반장·보전 담당자가 현장에서 확인하고 정합니다. 비서는 설비를 조작하지 않습니다.")
# 주제 없이 허락만 묻는 말에만 쓴다. 주제 낱말(주축·4일·552·차단기 …)이 있으면 지금처럼 일반 흐름(문서 답 또는 LLM 분류의 거절) —
# S6에서 E4-091 "연휴 끝나고 … 주축이 4일 넘게 놀았던데 바로 돌려도 돼?"(문서에 워밍업 안내가 있음)를 막았다 (2026-10-12)
PERMIT_GENERIC_V8 = frozenset("지금 바로 다시 이제 그냥 좀 당장 얼른 한번 설비 기계 장비 알람 경보 그거 그것 이거 이것 저거 저것".split())


def permit_only_v8(question: str) -> bool:
    """허락 꼴(PERMIT_CTRL_V8)이고, 그 말과 가리키는 말·설비 이름을 빼면 주제 낱말이 남지 않는다."""
    m = PERMIT_CTRL_V8.search(question)
    if not m:
        return False
    rest = question[: m.start()] + " " + question[m.end():]
    for t in re.findall(r"\d+[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*|[가-힣]+", rest.lower()):
        w = re.sub(r"(?:을|를|은|는|이|가|에|의|도|만|요|로|으로)$", "", t)
        if (len(w) < 2 or w in PERMIT_GENERIC_V8 or w in FU_FILL_V8 or t in PERMIT_GENERIC_V8
                or EQUIP_RE_V5.fullmatch(w) or re.fullmatch(r"\d+호기|일호기|이호기|[1-9]번", w)):
            continue
        return False
    return True


def human_only(question: str, general: bool = True) -> dict | None:
    """사람만 할 일·설비 조작 요청이면 거절 안내. general=False면 마지막의 일반 요청 꼴("…해 줘") 거절만 건너뛴다 —
    이어 묻기(FOLLOWUP)가 "쉽게 해 줘"·"다시 해 줘"를 먼저 알아보고, 아니면 부른 쪽이 general=True로 다시 부른다 (2026-10-12)."""
    v2 = settings().parse_v2
    v4 = v2 and settings().parse_v3 and settings().parse_v4
    v5 = v4 and settings().parse_v5
    v6 = v5 and settings().parse_v6
    if v8_on() and permit_only_v8(question) and not QWORD_V2.search(question):
        return {"status": "안내", "mode": "규칙", "links": [], "conclusion": PERMIT_MSG_V8}
    if v2 and settings().parse_v3 and not QWORD_V2.search(question) \
            and (CONTROL_VERB_V5 if v5 else CONTROL_VERB_V3).search(question) and (CONTROL_OBJECT_V4 if v4 else CONTROL_OBJECT_V3).search(question):
        return {"status": "안내", "mode": "규칙",
                "conclusion": "플랫폼은 설비를 조작하지 않습니다. 설비를 켜고 끄거나 설정을 바꾸는 일은 권한 있는 사람이 현장에서 합니다.",
                "links": []}
    if (CONTROL_VERB_V2 if v2 else CONTROL_VERB).search(question) and CONTROL_OBJECT.search(question):
        return {"status": "안내", "mode": "규칙",
                "conclusion": "플랫폼은 설비를 조작하지 않습니다. 설비를 켜고 끄거나 설정을 바꾸는 일은 권한 있는 사람이 현장에서 합니다.",
                "links": []}
    v9 = v6 and v9_on()
    asked = v2 and (request_form_v9(question) if v9 else request_form_v6(question) if v6 else request_form_v5(question) if v5
                    else request_form(question))
    if not REQUEST.search(question) and not asked:
        return None
    for pat, msg, (label, screen) in HUMAN_ONLY:
        if pat.search(question):
            return {"status": "안내", "mode": "규칙", "conclusion": msg + " 비서는 상태를 바꾸지 않습니다.",
                    "links": [_link(label, screen)]}
    if asked and general:
        if v4 and leisure_request(question):  # 업무 밖 추천·소개 부탁은 일반 흐름으로 (→ 문서에 없음, E2-090). 업무 대상이 있으면 거절 그대로
            return None
        if v9 and list_request_v9(question):  # 8차: "… 리스트 줘"(조작·상태 낱말 없음)는 정보 질문 (E6-043). HUMAN_ONLY·조작 검사는 이미 지났다
            return None
        return {"status": "안내", "mode": "규칙", "links": [],
                "conclusion": "비서는 기록·상태·설비를 바꾸지 않습니다. 이 일은 권한이 있는 사람이 해당 화면이나 현장에서 합니다."}
    return None


JOB_KO = {"select": "줄 고르기", "write": "문장 다듬기", "route": "질문 분류", "verify": "따로 검증",
          "simplify": "쉽게 다시 쓰기", "faith": "바꿔 쓴 글 검사",   # 이어 묻기 (2026-10-12)
          "pick": "짧게 고르기",   # 이어 묻기 2판 (7차)
          "write_answer": "답 쓰기", "answer_faith": "쓴 답 검사",   # 10차 DOC_WRITE (2026-10-13)
          "lead_faith": "앞머리 검사",   # 10차 보강 LEAD_V12 (2026-10-14)
          "safe_simplify": "점검 순서를 쉬운 말로 다시 쓰기",   # 안전 영역 새로쓰기 (2026-10-14)
          "pure_answer": "순수 연결 답 (검사 없음)"}   # 순수 외부 LLM 연결 (2026-10-15)


LLM_SAID_NO_V10 = ("답할 줄 없음", "답 못 함")


def none_mode_v10(traces: list[dict], s, default: str = "규칙") -> str:
    """9차 BLOCKS_V3 (1부 원인 G): "문서에 없음"·"확인 필요" 답의 꼬리표. LLM을 불렀으면(쓴 일 + "답할 수 없다"고 판단한 일)
    그대로 밝힌다 — 전에는 늘 "규칙"이라 LLM이 거절한 답과 LLM을 부르지 않은 답이 같아 보였다. 표시만 (conclusion 그대로)."""
    if not blocks3_on(s):
        return default
    used = [JOB_KO.get(t["job"], t["job"]) for t in traces if t.get("used")]
    said_no = [JOB_KO.get(t["job"], t["job"]) + " — 답할 줄 없다고 판단" for t in traces
               if not t.get("used") and (t.get("reason") or "").startswith(LLM_SAID_NO_V10)]
    if not used and not said_no:
        return default
    return f"{s.llm_label} {s.llm_model_name} ({', '.join(dict.fromkeys(used + said_no))}) + 프로그램 검사"


def merge_route(p: dict, r: dict) -> dict:
    """LLM 분류(기간 이름)를 parse() 결과 꼴로 바꾼다. 사용자가 적은 날짜·설비·교대는 그대로 둔다."""
    q = dict(p, intents=list(r["intents"]))
    if not q["equipment"]:
        q["equipment"] = list(r["equipment"])
    if q["start"] is None:
        per = r["period"]
        if per == "today":
            q["start"] = q["end"] = REF_DATE
        elif per == "yesterday":
            q["start"] = q["end"] = REF_DATE - timedelta(days=1)
        elif per == "last_shift":  # 기준 시각 10/1 08:00의 지난 교대 = 9/30 야간 (parse와 같음)
            q["start"] = q["end"] = REF_DATE - timedelta(days=1)
            q["shift"] = q["shift"] or "N"
        elif per == "recent_7":
            q["start"], q["end"] = REF_DATE - timedelta(days=7), REF_DATE - timedelta(days=1)
    if q["shift"] is None and r["shift"] in ("D", "N"):
        q["shift"] = r["shift"]
    return q


# ---------------------------------------------------------------- 조립
TIER2_MIN_OVERLAP = 0.2   # 2차 문지기: 원래 질문 낱말(+용어집 동의어) 중 고른 줄에 있어야 하는 비율 [가상: 조정 세트 F로 맞춘 시작값]
TIER2_PREFIX = "문서에서 찾은 관련 내용입니다:"
# 답 종류 낱말 검사 (2차 문지기): 질문이 이런 값을 물으면 고른 줄에 그 꼴의 값이 있어야 한다
ANSWER_TYPE = [
    (re.compile(r"가격|비용|금액|값이|얼마에|몇\s*원|돈"), re.compile(r"\d[\d,]*\s*(?:원|만\s*원|달러|USD|\$)")),
    (re.compile(r"전화|연락처"), re.compile(r"\d{2,4}-\d{3,4}-\d{4}")),
    (re.compile(r"몇\s*시(?!간)"), re.compile(r"\d{1,2}:\d{2}|\d{1,2}\s*시(?!간)")),
    (re.compile(r"몇\s*도"), re.compile(r"\d\s*(?:℃|°C|도)")),
    (re.compile(r"몇\s*(?:%|퍼센트|프로)"), re.compile(r"\d\s*%")),
    (re.compile(r"몇\s*(?:A|V|암페어|볼트)\b"), re.compile(r"\d\s*(?:A|V)(?![A-Za-z])")),
    (re.compile(r"몇\s*(?:분|시간|초)|얼마나\s*걸"), re.compile(r"\d\s*(?:분|시간|초)")),
    (re.compile(r"며칠|몇\s*(?:일|주|달|개월|년)|얼마\s*동안|얼마나\s*(?:오래|보관|남겨)"), re.compile(r"\d\s*(?:일|주|개월|달|년)")),
    (re.compile(r"몇\s*(?:개|번|회|건|명|대|단계)"), re.compile(r"\d")),
    (re.compile(r"누가|누구"), re.compile(r"작업자|보전|반장|관리자|담당|OPR|MNT|SUP|MGR|책임자")),
]


# 3차 (PARSE_V4, b): "얼마 동안·얼마나 오래"는 초·분·시간·일·주·개월·년 어느 단위든 된다 (E2-010 "얼마 동안 서 있어" → 1~5분).
# 보관·남겨 두는 기간을 묻는 질문은 지금처럼 일 단위 이상만 (F11 "로그인 기록은 얼마 동안 남겨 둬" → 1년, 분 단위 줄은 거부)
ANSWER_TYPE_V4 = ANSWER_TYPE[:7] + [
    (re.compile(r"며칠|몇\s*(?:일|주|달|개월|년)"), re.compile(r"\d\s*(?:일|주|개월|달|년)")),
    (re.compile(r"^(?=.*(?:보관|보존|남겨|남기))(?=.*(?:얼마|며칠|몇|언제까지|기간))"), re.compile(r"\d\s*(?:일|주|개월|달|년)")),
    (re.compile(r"얼마\s*동안|얼마나\s*오래"), re.compile(r"\d\s*(?:초|분|시간|일|주|개월|달|년)")),
] + ANSWER_TYPE[8:]


# 4차 (PARSE_V5, L6): "몇 암페어야?"처럼 한글이 붙으면 \b가 맞지 않아 이 검사가 죽어 있었다 — 영숫자 경계로 본다 ("몇 A4"는 아님).
# 값 꼴은 "120 VAC"·"20~30 VDC"도 받는다
ANSWER_TYPE_V5 = [(re.compile(r"몇\s*(?:A|V|암페어|볼트)(?![A-Za-z0-9])"), re.compile(r"\d\s*(?:VAC|VDC|A|V|암페어|볼트)(?![A-Za-z])"))
                  if i == 5 else row for i, row in enumerate(ANSWER_TYPE_V4)]


# 시급한 문제 1 "지어낸 답" (ANSWER_GATE_V17, 2026-10-14, 사용자 결정 D1·D2): 봉인 비교 세트 CMP30의 CMP-022 "절삭유 필터 부품번호가 뭐야?"를
# Qwen·Claude 세 모델 모두 지어냈다 — 부품번호 꼴(NN-NNNN)을 보는 답 종류 검사가 알람 카드 길(ALARM_DETAIL_V3)에만 있고 문서 길(1차·2차 문지기)에는
# 없었다. 길마다 표가 따로라 생긴 구멍이라 두 길에 같은 항목(부품번호·기본값)을 더한다. 또 낱말 겹침 문턱 0.2는 구어체 질문("노랗게 깜빡"↔"황색 점멸",
# "반년"↔"6개월")의 맞는 답을 죽였다 — 모든 평가 기록에서 이 검사가 거부한 문항 27개는 전부 답이 있는 질문이었고(거부가 정답인 질문은 0개),
# 문턱을 0.1로 낮추면 그중 9개가 맞게 된다(0.0이면 13개, 대신 틀리게 답한 것 3개). 0.1을 후보로 쓴다.
PARTNO_Q_V17 = re.compile(r"부품\s*번호|품번|(?<![A-Za-z])P/?N(?![A-Za-z])|파트\s*넘버", re.I)
PARTNO_VAL_V17 = re.compile(r"(?<![\d-])\d{2,3}-\d{3,5}[A-Za-z]?(?![\d-])")
DEFAULT_Q_V17 = re.compile(r"기본\s*값|기본값|초기값|초깃값")
DEFAULT_VAL_V17 = re.compile(r"기본\s*값|기본값|초기값|초깃값|default", re.I)
DETAIL_TYPES_V17 = [(PARTNO_Q_V17, PARTNO_VAL_V17), (DEFAULT_Q_V17, DEFAULT_VAL_V17)]
TIER2_MIN_OVERLAP_V17 = 0.1


def gate_v17_on(s=None) -> bool:
    s = s or settings()
    return bool(s.parse_v8 and s.answer_gate_v17)


def detail_types_ok_v17(question: str, text: str) -> bool:
    """문서 길의 답 종류 표에 부품번호·기본값을 더한 항목: 질문이 그 값을 물으면 고른 줄에 그 꼴이 있어야 한다."""
    return all(want.search(text) for cue, want in DETAIL_TYPES_V17 if cue.search(question))


def tier2_min_overlap(s=None) -> float:
    return min(TIER2_MIN_OVERLAP, TIER2_MIN_OVERLAP_V17) if gate_v17_on(s) else TIER2_MIN_OVERLAP


def answer_type_ok(question: str, text: str) -> bool:
    if v7_on() and not model_name_ok_v7(question, text):   # 6차: "무슨 모델" 꼴 (E5-075)
        return False
    if gate_v17_on() and not detail_types_ok_v17(question, text):   # ANSWER_GATE_V17: 부품번호·기본값 (CMP-022)
        return False
    if v8_on():   # 7차 A5: 시각·가격 꼴의 경계
        return all(want.search(text) for cue, want in ANSWER_TYPE_V8 if cue.search(question))
    if v5_on():
        return all(want.search(text) for cue, want in ANSWER_TYPE_V5 if cue.search(question))
    table = ANSWER_TYPE_V4 if (settings().parse_v2 and settings().parse_v3 and settings().parse_v4) else ANSWER_TYPE
    return all(want.search(text) for cue, want in table if cue.search(question))


# 5차 (PARSE_V6, S2′): 1차 문지기로 고른 줄에도 답 종류 검사를 하되 가격·전화번호·시각 세 가지만 (E4-084 "야간 보전 담당자
# 전화번호 좀 알려 줘" → "표지에 전화번호를 적는다" 줄로 답함). 가격은 맨 "값이"를 빼고 본다 — 측정값을 묻는 질문을 막지 않게
ANSWER_TYPE_FIRST_V6 = [
    (re.compile(r"가격|비용|금액|몇\s*원|얼마\s*(?:주고|에\s*(?:사|샀|산|구매|구입))"), ANSWER_TYPE[0][1]),
    ANSWER_TYPE[1],   # 전화·연락처
    ANSWER_TYPE[2],   # 몇 시
]


# 7차 A5 (PARSE_V8): 답 종류 꼴의 뒤 경계 — "몇 시그마"를 시각으로(E6-023), "얼마에 한 번씩"을 가격으로(E6-020), "측정값이"를 가격으로 보던 결함.
# 시각은 "몇 시" 뒤가 조사·끝일 때만(몇 시간·몇 시그마·몇 시작 아님), 값도 "6시그마"를 시각으로 세지 않는다
TIME_Q_V8 = re.compile(r"몇\s*시(?:에|쯤|부터|까지|경|에서|인지|야|예요|요|죠)?(?![가-힣])")
TIME_VAL_V8 = re.compile(r"\d{1,2}:\d{2}|\d{1,2}\s*시(?:에|부터|까지|경|쯤|에서)?(?![가-힣])")
PRICE_Q_V8 = re.compile(r"가격|비용|금액|(?<![가-힣])값이|얼마에(?!\s*(?:한\s*번|한번|\d+\s*번|마다))|몇\s*원"
                        r"|(?<![가-힣])돈(?:이|은|을|도)?(?![가-힣])")
ANSWER_TYPE_V8 = [(PRICE_Q_V8, ANSWER_TYPE[0][1]), ANSWER_TYPE_V5[1], (TIME_Q_V8, TIME_VAL_V8)] + ANSWER_TYPE_V5[3:]
ANSWER_TYPE_FIRST_V8 = [ANSWER_TYPE_FIRST_V6[0], ANSWER_TYPE_FIRST_V6[1], (TIME_Q_V8, TIME_VAL_V8)]
ALARM_TYPE_NAMES_V8 = ("가격", "전화번호", "시각")   # ANSWER_TYPE_FIRST_V8과 같은 순서


def first_gate_type_ok_v6(question: str, text: str) -> bool:
    if v7_on() and not model_name_ok_v7(question, text):   # 6차: "무슨 모델" 꼴도 1차 문지기에서 본다 (E5-075)
        return False
    if gate_v17_on() and not detail_types_ok_v17(question, text):   # ANSWER_GATE_V17: 부품번호·기본값 (CMP-022)
        return False
    table = ANSWER_TYPE_FIRST_V8 if v8_on() else ANSWER_TYPE_FIRST_V6
    return all(want.search(text) for cue, want in table if cue.search(question))


def alarm_type_missing_v8(question: str, texts: list[str]) -> tuple[str, str] | None:
    """A1: 알람 카드 길에도 1차 문지기와 같은 답 종류 표(가격·전화번호·시각). 질문이 그 값을 묻는데 알람 문서·카드에 그 꼴이 없으면
    (이름, "") — E6-091 "552 … 서비스센터 전화번호"가 알람 카드로 답했다."""
    blob = " ".join(texts)
    for name, (cue, want) in zip(ALARM_TYPE_NAMES_V8, ANSWER_TYPE_FIRST_V8):
        if cue.search(question) and not want.search(blob):
            return name, ""
    return None


def is_procedure(question: str) -> bool:
    """절차 질문 (표 전체를 그대로 옮기고 LLM에 보내지 않는다)."""
    return bool(PROCEDURE.search(question)) and not CRITERIA.search(question)


def use_llm_route(question: str, p: dict, s) -> bool:
    """LLM 분류를 부를 질문인가 (계획 3단계): 정책이 llm_*이고 route 작업이 켜져 있고, 알람·절차·안전 질문이 아닐 때.
    알람·절차·안전 질문과 사람만 할 일(human_only)은 규칙이 처리한다."""
    return (s.route_policy in ("llm_primary", "llm_guarded") and s.job("route") and not p["alarms"]
            and not is_procedure(question) and not any(w in question for w in SAFETY_WORDS))


def _route_skip_reason(question: str, p: dict, s) -> str:
    """STEP_LOG 2단계: use_llm_route가 False인 까닭 (로그에 적는 글 — use_llm_route와 같은 순서로 따진다. 읽기만 한다)."""
    if s.route_policy not in ("llm_primary", "llm_guarded"):
        return f"분류 정책이 규칙 전용 (ROUTE_POLICY={s.route_policy})"
    if not s.job("route"):
        return "LLM route 작업이 꺼져 있음 (LLM_ENABLED·LLM_JOBS)"
    if p["alarms"]:
        return "알람 번호 질문 — 규칙이 처리"
    if is_procedure(question):
        return "절차 질문 — 규칙이 처리"
    if any(w in question for w in SAFETY_WORDS):
        return "안전 낱말 질문 — 규칙이 처리"
    if PURE.enabled(s):
        return "순수 외부 LLM — 분류 LLM을 부르지 않음 (PURE_KEEP_SIGNALS=1: 규칙 신호가 있어 규칙 길로 처리)"
    return "알 수 없음"


# 10차 DOC_WRITE (2026-10-13 사용자 결정): 문서 답을 AI가 찾은 줄로 새로 쓴다 — 해요체 1~3문장, 원문 줄은 아래에 그대로(화면은 접음).
# 빼는 것: 알람 + 문서(카드 길), 절차, 고장 대응(DOC-03)·안전 작업(DOC-05) 줄, 안전 낱말이 든 줄(규칙 2.5). 쓴 글은 자리표·코드 검사·
# 따로 판정(answer_faith)을 모두 지나야 쓴다(followup_v2.write_doc_answer). 결론은 "새 답 + 문서 원문: + 원문 줄" — 채점·한 문단 보기는 원문을 계속 본다
DOC_WRITE_SEP_V11 = "문서 원문:"


# 안전 영역 새로쓰기 1단계 (SAFE_WRITE_CARD, 2026-10-14 사용자 결정 "대체 방식·엄격"): 알람 답의 점검 순서(steps)를 AI가 쉬운 말로 1:1 다시 쓴다.
# steps(원문)는 그대로 두고 새 글은 steps_easy로 따로 싣는다 — 화면은 새 글을 먼저 보이고 원문은 [원문 보기]로 접는다.
# "번호 (누가)" 머리는 프로그램이 그대로 붙인다(AI는 할 일 글만 본다). 하나라도 검사에 실패하면 None → 원문만 (규칙 2.5: 단계는 자르거나 바꾸지 않는다).
STEP_PREFIX_V15 = re.compile(r"^(\S+ \([^)]*\)) (.+)$", re.S)


def safe_steps_easy_v15(steps: list[str], traces: list) -> list[str] | None:
    parts = [STEP_PREFIX_V15.match(x) for x in steps]
    if not steps or not all(parts):
        traces.append({"job": "safe_simplify", "used": False, "reason": "점검 순서 글 모양을 읽지 못해 원문만", "tries": 0, "ms": 0})
        return None
    new, tr = FU2.write_safe_steps_v15([m.group(2) for m in parts])
    traces.append(tr)
    if not new:
        return None
    # 띄어쓰기만 다른 조각은 원문 그대로 둔다 ("P코드" → "P 코드", "FNC로" → "FNC 로" — 자리표를 되채울 때 AI가 낀 빈칸이 코드 이름을 바꿔 보이게 한다).
    # 한 조각도 안 바뀌었으면 None — "AI가 쉬운 말로 바꿔 씀" 꼬리표를 거짓으로 붙이지 않는다 (7차 규칙)
    squash = lambda x: re.sub(r"\s+", "", x)  # noqa: E731
    texts = [m.group(2) for m in parts]
    new = [o if squash(n) == squash(o) else n for n, o in zip(new, texts)]
    if new == texts:
        tr.update(used=False, reason="바꿀 것이 없어 원문 그대로")
        return None
    return [f"{m.group(1)} {t}" for m, t in zip(parts, new)]


# 안전 영역 새로쓰기 (2026-10-14 사용자 결정 "대체 방식·단계적·엄격"): 2단계 DOC-03·DOC-05 줄, 4단계 안전 낱말 줄은 스위치가 켜졌을 때만 새로 쓴다.
# 고정 서식 쪽은 어떤 스위치로도 쓰지 않는다 (안전 규칙 2.5 — 프로그램이 원문 그대로 붙이는 것):
# DOC-05 §3 차단 지점·§5 보호구·§7 고정 서식 (프로그램이 템플릿으로 붙이는 것).
# 2026-10-14 사용자 요청("잠금·표지 6단계도 새로쓰기 적용해줘")으로 §2 잠금·표지 절차(LOTO 6+3 표)와 그 안의 "고전압" 대기 줄은 이 목록에서 뺐다 —
# 새로 쓰기는 가능하지만 안전 모드 엄격 검사(안전 낱말 "고전압"·조건 말 "이상"·숫자 "5분"의 자리표 보존)를 모두 지나야 하고, 실패하면 원문이다.
FIXED_DOC05_SECTIONS_V15 = ("3", "5", "7")


def fixed_format_v15(lines: list[str], cites: list[dict]) -> bool:
    return any((c or {}).get("doc_id") == "DOC-05" and str((c or {}).get("section", "")).split(".")[0] in FIXED_DOC05_SECTIONS_V15
               for c in cites)


def doc_write_mode_v15(s, lines: list[str], cites: list[dict], exclude, procedure) -> str | None:
    """새로 쓸 수 있나. None = 쓰지 않음, "plain" = 지금까지의 새로쓰기, "safe" = 안전 영역(엄격 검사 추가).
    STEP_LOG 7단계: 결과와 쓰지 않는 까닭을 로그에 남긴다(읽기만 한다)."""
    def verdict(mode: str | None, why: str | None):
        if SL.on():
            SL.step("7 새로 써도 되나", 결과=mode or "쓰지 않음", 까닭=why)
        return mode

    if not (v8_on(s) and s.doc_write and s.job("write")):
        return verdict(None, "새로 쓰기가 꺼져 있음 (DOC_WRITE·PARSE_V8·LLM write 작업)")
    if exclude:
        return verdict(None, "알람 카드와 함께 답하는 문서 줄")
    if procedure:
        return verdict(None, "절차 질문")
    if not lines:
        return verdict(None, "보일 줄이 없음")
    if len(cites) != len(lines):
        return verdict(None, "줄과 출처 수가 다름")
    if s.write_rules_v17 and any(FU2.is_keepaway_v16(x) for x in lines):   # WRITE_RULES_V17 (접근금지 보고서 안 B): "사람이 떨어져 있어라" 경고 줄은 새로 쓰지 않는다
        return verdict(None, "접근 금지 경고 줄")
    safe = False
    if any((c or {}).get("doc_id") in ("DOC-03", "DOC-05") for c in cites):
        if not s.safe_write_doc or fixed_format_v15(lines, cites):
            return verdict(None, "고장 대응·안전 작업 줄 (고정 서식이거나 SAFE_WRITE_DOC 꺼짐)")
        safe = True
    if any(FU2.is_safety(x) for x in lines):
        if not s.safe_write_words or fixed_format_v15(lines, cites):
            return verdict(None, "안전 낱말이 든 줄 (고정 서식이거나 SAFE_WRITE_WORDS 꺼짐)")
        safe = True
    return verdict("safe" if safe else "plain", None)


def doc_write_ok_v11(s, lines: list[str], cites: list[dict], exclude, procedure) -> bool:
    return doc_write_mode_v15(s, lines, cites, exclude, procedure) is not None


def safe_lines_easy_v15(lines: list[str], traces: list) -> list[str] | None:
    """안전 영역 새로쓰기 3단계 (SAFE_WRITE_PROC): 절차 줄을 1:1로 쉬운 말로 다시 쓴다. 표 줄은 머리·칸 이름을 그대로 두고 값 글만 쓴다(units_of/assemble).
    검사는 1단계와 같다 — 하나라도 실패하면 None, 띄어쓰기만 다르면 원문, 한 줄도 안 바뀌면 None."""
    units = FU2.units_of(lines)
    texts = [u["text"] for u in units]
    new, tr = FU2.write_safe_steps_v15(texts)
    traces.append(tr)
    if not new:
        return None
    squash = lambda x: re.sub(r"\s+", "", x)  # noqa: E731
    new = [o if squash(n) == squash(o) else n for n, o in zip(new, texts)]
    if new == texts:
        tr.update(used=False, reason="바꿀 것이 없어 원문 그대로")
        return None
    return FU2.assemble(lines, units, new)


def _doc_part(question: str, route: Route | None, s, traces: list, rule_doc: bool = False,
              memo: dict | None = None, exclude=None) -> tuple[str, list[dict], dict] | None:
    """문서 쪽 답 = 1차 문지기(낱말) → AI 줄 고르기 (예전과 같음).
    DOC_GATE=veto·tiered: AI 줄 고르기가 "찾은 글로 답할 수 없다"(answerable=false)고 하거나, 보일 줄을 따로 검증해
    "답 못 함"이면 낱말 결과를 쓰지 않는다.
    DOC_GATE=tiered: 1차에서 막혔거나 AI가 답할 수 없다고 한 문서 질문을 2차 문지기로 다시 본다 (계획 4단계).
    8차: exclude = 알람 카드가 보인 그 알람의 절(FLOW_V9 알람 + 문서 — 그 절의 카드 줄만 후보에서 뺀다), 줄 고르기는 대상에 해당하는 줄만 +
    같은 표 형제 줄 거르기(FLOW_V9), 보인 줄마다 출처를 memo["doc_cites"]에 둔다(BLOCKS_V2 줄 목록 칸이 쓴다)."""
    flow = flow_on(s)
    line_fn = (lambda ch: [t for t in plain_lines(ch) if not card_line_v9(ch, t, exclude)]) if exclude else plain_lines
    got = _doc_search(question)
    if got and exclude:   # 낱말 결과 줄에서도 카드가 보인 줄을 뺀다 (모두 빠지면 1차는 찾지 못한 것)
        top = got["candidates"][0] if got.get("candidates") else None
        kept = [x for x in got["conclusion"].split(" / ") if x and not (top and card_line_v9(top, x, exclude))]
        got = {**got, "conclusion": " / ".join(kept)} if kept else None
    if got:
        c, evidence = got["conclusion"], got["evidence"]
        lead_shown = ""   # 10차 보강 LEAD_V12: 보일 AI 앞머리
        lines = [x for x in c.split(" / ") if x]  # 보일 줄 (AI 고르기가 실패하면 낱말 결과 줄)
        line_cites = [_line_cite(got["candidates"][0])] * len(lines) if got.get("candidates") else []
        fill_chunks_v18 = None   # TABLE_FILL_V18: AI가 고른 줄의 조각 (줄과 같은 길이일 때만 표를 채운다)
        if s.job("write") and not got["procedure"]:
            sel, tr = jobs.select_lines(question, got["candidates"], line_fn, _head)
            traces.append(tr)
            if sel and flow:
                sel = sibling_filter_v9(question, sel)
                if sel.get("dropped"):
                    tr["sibling_dropped"] = sel["dropped"]
            if sel:
                c = (sel["lead"] + " " if sel["lead"] else "") + " / ".join(sel["lines"])
                lead_shown = sel["lead"]
                evidence = [_cite(ch) for ch in sel["chunks"]]
                lines = sel["lines"]
                line_cites = [_line_cite(ch) for ch in sel.get("line_chunks") or []]
                fill_chunks_v18 = list(sel.get("line_chunks") or [])
            elif s.doc_gate in ("veto", "tiered") and (tr.get("reason") or "").startswith("답할 줄 없음"):
                got = None
            if got and s.doc_gate in ("veto", "tiered"):
                # 따로 검증: 보일 줄로 질문에 답할 수 있나. AI가 "답 못 함"이라고 판정했을 때만 거부한다 —
                # AI 서버 오류·시간 초과는 거부로 치지 않는다(AI가 죽어도 예전처럼 답함). 2026-10-10 F25 (고른 줄이 다른 것을 답함)
                ok, vtr = jobs.verify(question, lines)
                traces.append(vtr)
                if not ok and vtr.get("reason") == "답 못 함":
                    got = None
        if got and v6_on(s):
            type_ok = first_gate_type_ok_v6(question, " / ".join(lines))
            if SL.on():   # STEP_LOG 6단계: 1차 문지기로 고른 줄에도 답 종류 검사 (가격·전화번호·시각 …)
                SL.step("6 코드 검사", 길="1차 문지기", 답종류검사="통과" if type_ok else "실패 — 묻는 값의 꼴이 줄에 없음", 줄=_sl_lines(lines))
            if not type_ok:
                got = None   # 5차 S2′: 1차 문지기로 고른 줄에도 답 종류 검사 (가격·전화번호·시각) — E4-084
        if got and exclude and flow10_on(s):   # 9차 D: 검사를 다 지난 뒤 보일 줄에서만 "원문 설명"을 뺀다
            kept, kept_cites = drop_card_orig_v10(lines, line_cites, exclude)
            if len(kept) < len(lines):
                lines, line_cites = kept, kept_cites
                c = " / ".join(lines)   # 앞머리는 뺀 줄까지 요약했을 수 있어 비운다 (8차 형제 줄 거르기와 같음)
                lead_shown = ""
        if got and fill_chunks_v18 is not None and (f18 := table_fill_v18(lines, fill_chunks_v18, s)):   # TABLE_FILL_V18: 검사를 다 지난 뒤 번호 붙은 절차 표의 나머지 줄을 채움
            lines, fchs = f18
            line_cites = [_line_cite(ch) for ch in fchs]
            c = f"{TIER2_PREFIX} " + " / ".join(lines)   # AI 앞머리는 처음 고른 줄의 요약이라 채운 표를 말하지 못한다 — 비우고 프로그램 머리글(2차 문지기 답과 같은 꼴)
            lead_shown = ""
        if got and (g := gloss_only_v13(question, lines, line_cites, s)):   # 10차 보강 TERM_V13 ②: 용어 질문은 용어집 줄만
            lines, line_cites = g
            c = f"{TIER2_PREFIX} " + " / ".join(lines)   # 머리글은 2차 문지기 답과 같은 꼴 (끝의 "?"에 따라 머리글이 갈리던 것)
            lead_shown = ""
            evidence = [e for e in evidence if e.get("doc_id") == "GLOSSARY"] or evidence
        tpl = english_template_v13(question, lines, line_cites, s) if got else None   # TERM_V13 ③ 영어 이름 틀 답
        if tpl:
            c = f"{tpl} " + " / ".join(lines)
            lead_shown = ""
        written = None
        wmode = doc_write_mode_v15(s, lines, line_cites, exclude, got.get("procedure")) if got and not tpl else None
        if wmode:   # 10차: 찾은 줄로 답을 새로 씀 (안전 영역은 SAFE_WRITE_DOC·WORDS가 켜졌을 때만, 엄격 검사 추가)
            written, wtr = FU2.write_doc_answer(question, lines, safe=(wmode == "safe"), titles=_cite_titles(line_cites, lines))
            traces.extend(wtr)
            if SL.on():   # STEP_LOG 7~11단계: 새로 쓴 글(코드 검사·따로 판정을 모두 지났을 때만 있음)과 시도 기록(거부된 글·까닭은 rejected)
                SL.step("9 새로 쓰기", 길="1차 문지기", 방식=wmode, 새글있음=bool(written), 쓴글=written, 시도=wtr)
            if written:
                c = f"{written} {DOC_WRITE_SEP_V11} " + " / ".join(lines)
        elif (got and not tpl and got.get("procedure") and not exclude and v8_on(s) and s.safe_write_proc and s.job("write")
              and lines and len(line_cites) == len(lines) and not fixed_format_v15(lines, line_cites)):
            # 안전 영역 새로쓰기 3단계 (SAFE_WRITE_PROC): 절차 줄을 1:1로 대체 — 새 글을 "새로 쓴 답" 자리에 놓고 원문 줄은 아래에 접는다
            easy = safe_lines_easy_v15(lines, traces)
            if SL.on():   # STEP_LOG 안전 새로쓰기 3단계: 절차 줄을 1:1로 쉬운 말로 (traces[-1] = 그 시도의 기록)
                SL.step("안전 새로쓰기", 대상="절차 줄", 새글있음=bool(easy), 시도=traces[-1] if traces else None)
            if easy:
                written = " / ".join(easy)
                c = f"{written} {DOC_WRITE_SEP_V11} " + " / ".join(lines)
        if got and not written and lead_shown and lead_v12_on(s) and c == f"{lead_shown} " + " / ".join(lines):
            # 10차 보강 LEAD_V12 (2026-10-14 사용자 결정): 새로 쓴 답이 없어 AI 앞머리가 그대로 보일 때, 새로 쓴 답과 같은 검사를 건다.
            # 앱 로그에서 본 것: "작업자가 이송과 속도를 조정해야 합니다", "피드 레이트(Feed Rate)" — 줄 고르기의 앞머리는 숫자·출처·좁은 허락 꼴만 봤다.
            ok, ltr = FU2.check_lead_v12(question, lead_shown, lines)
            traces.append(ltr)
            if SL.on():   # STEP_LOG: 1차 문지기 길 AI 앞머리 한 문장 검사 (못 지나면 프로그램 머리글 + 원문 줄)
                SL.step("앞머리 검사", 통과=bool(ok), 앞머리=lead_shown, 호출=ltr)
            if not ok:
                c = f"{TIER2_PREFIX} " + " / ".join(lines)   # 앞머리 대신 프로그램 머리글 (2차 문지기 답과 같은 꼴)
                lead_shown = ""
        if got:
            if memo is not None:   # 이어 묻기 기록: 보인 문서 줄 (원문 그대로, AI 앞머리 없이)
                memo["doc_lines"] = list(lines)
                memo["doc_cites"] = list(line_cites) if len(line_cites) == len(lines) else []   # 8차: 줄마다 출처
                # 7차 B3: 화면에 보인 AI 앞머리(검사를 지난 한 문장 요약)도 따로 기억한다 — "짧게"에 쓴다
                memo["doc_lead"] = written or tpl or (lead_shown if lead_v12_on(s) else
                                               (c[: -len(" / ".join(lines))].strip() if lines and c.endswith(" / ".join(lines)) else ""))
                memo["doc_written"] = written or ""
            return c, evidence, got["retrieval"]
    if route is None and rule_doc and s.parse_v2 and s.parse_v3:  # 규칙으로 분류한 문서 질문(안전 낱말 등)도 2차 문지기 (2026-10-10 2차)
        route = Route("doc", [], [], None, None, None, [], "규칙")
    if s.doc_gate == "tiered" and route is not None and route.kind in ("doc", "mixed") and s.job("write") and not is_procedure(question):
        side: dict = {}
        got2 = _tier2(question, route, traces, line_fn=line_fn if exclude else None, side=side)
        if got2 and exclude and flow10_on(s):   # 9차 D: 2차 문지기 답도 검사 뒤 보일 줄에서만 뺀다
            lines2 = [x for x in got2[0].removeprefix(TIER2_PREFIX).strip().split(" / ") if x]
            kept, kept_cites = drop_card_orig_v10(lines2, side.get("line_cites") or [], exclude)
            if len(kept) < len(lines2):
                side["line_cites"] = kept_cites
                got2 = (TIER2_PREFIX + " " + " / ".join(kept), got2[1], got2[2])
        written = None
        tpl2 = None
        if got2:
            lines2 = side.get("lines") or [x for x in got2[0].removeprefix(TIER2_PREFIX).strip().split(" / ") if x]
            if got2[0].removeprefix(TIER2_PREFIX).strip() != " / ".join(lines2):   # 9차 D로 줄을 뺐으면 지금 결론의 줄로
                lines2 = [x for x in got2[0].removeprefix(TIER2_PREFIX).strip().split(" / ") if x]
            if (side.get("line_chunks") is not None and len(side["line_chunks"]) == len(lines2)
                    and (f18 := table_fill_v18(lines2, side["line_chunks"], s))):   # TABLE_FILL_V18: 검사를 다 지난 뒤 번호 붙은 절차 표의 나머지 줄을 채움
                lines2, fchs = f18
                side["lines"], side["line_chunks"], side["line_cites"] = lines2, fchs, [_line_cite(ch) for ch in fchs]
                got2 = (TIER2_PREFIX + " " + " / ".join(lines2), got2[1], got2[2])
            if (g := gloss_only_v13(question, lines2, side.get("line_cites") or [], s)):   # 10차 보강 TERM_V13 ②
                lines2, side["line_cites"] = g
                side["lines"] = lines2
                got2 = (TIER2_PREFIX + " " + " / ".join(lines2),
                        [e for e in got2[1] if e.get("doc_id") == "GLOSSARY"] or got2[1], got2[2])
            tpl2 = english_template_v13(question, lines2, side.get("line_cites") or [], s)   # TERM_V13 ③ 영어 이름 틀 답
            if tpl2:
                got2 = (f"{tpl2} " + " / ".join(lines2), got2[1], got2[2])
            elif (wmode2 := doc_write_mode_v15(s, lines2, side.get("line_cites") or [], exclude, False)):   # 10차: 2차 문지기 답도 새로 씀
                written, wtr = FU2.write_doc_answer(question, lines2, safe=(wmode2 == "safe"),
                                                    titles=_cite_titles(side.get("line_cites") or [], lines2))
                traces.extend(wtr)
                if SL.on():   # STEP_LOG 7~11단계: 2차 문지기 답의 새로 쓰기
                    SL.step("9 새로 쓰기", 길="2차 문지기", 방식=wmode2, 새글있음=bool(written), 쓴글=written, 시도=wtr)
                if written:
                    got2 = (f"{written} {DOC_WRITE_SEP_V11} " + " / ".join(lines2), got2[1], got2[2])
        if got2 and memo is not None:
            memo["doc_lines"] = [x for x in got2[0].removeprefix(TIER2_PREFIX).strip().split(" / ") if x] if not (written or tpl2) else lines2
            memo["doc_cites"] = side.get("line_cites") or []
            memo["doc_lead"] = written or tpl2 or ""   # 2차 문지기 답은 AI 앞머리가 없다 (머리글은 프로그램 고정 문구) — 10차: 새로 쓴 답은 둔다
            memo["doc_written"] = written or ""
        return got2
    return None


def _cite_titles(line_cites: list, lines: list) -> list[str] | None:
    """줄마다 그 줄이 있는 절의 제목 (WRITE_TITLES, 2026-10-14). 줄과 출처 수가 다르면 None — 어긋난 제목을 붙이지 않는다."""
    if not line_cites or len(line_cites) != len(lines):
        return None
    return [str((c or {}).get("title") or "") for c in line_cites]


def _line_cite(c: Chunk) -> dict:
    """줄 목록 칸의 줄마다 출처 (8차 BLOCKS_V2) — 출처 팝업이 쓰는 칸만 (사내 문서 이름·번호·§절, 원문 출처 없음)."""
    return {"cite": c.cite, "doc_id": c.doc_id, "doc_name": c.doc_name, "revision": c.revision, "section": c.section,
            "title": c.title, "snippet": "", "doc_no": c.doc_id, "rev": c.revision}


# 8차 ⓔ (FLOW_V9): 줄 고르기 거르기 — LLM이 같은 표에서 대상이 아닌 형제 줄을 함께 고르면(2026-10-12 사용자 화면: "웨이 커버 그리스 이름"에
# 공구 교환장치 줄 2개가 섞임) 대상이 아닌 형제 줄을 뺀다. 다른 표·다른 절의 줄은 건드리지 않는다 — 정답 줄
# "그리스 · Mobil Grease XHP 222"(DOC-04 §4.5 품목 표)에는 "웨이 커버"가 없어서 "대상 낱말이 없는 줄은 뺀다"로 하면 지워진다.
# 고장 대응(DOC-03)·안전 작업(DOC-05) 줄은 거르지 않는다 (절차는 자르지 않는다, root-cause-guards 8절).
# 좁힘 (2026-10-13 S6에서 찾음): 처음 판은 어떤 질문에나 걸어 "병목은 어떻게 판단해?"의 규칙 ①③ 줄(H08)과 "작업지시 바뀌면 준비하는 데
# 얼마나 걸려?"의 답 줄 "시간 — 10~20분"(C02)을 지웠다 → 물건의 이름·종류를 묻는 질문(NAME_ASK_V9)에서, 가르는 낱말이 남길 줄의
# 머리·첫 칸(부위·항목)에 있을 때만 건다
ASK_V9 = frozenset("이름 종류 제품 모델 상표 뭐 뭘 뭔지 무엇 얼마 언제 누가 누구 어디 어떤 무슨 몇 방법 기준 주기 값 써 쓰는 쓰나 사용 알려 말해".split())
SIBLING_SKIP_DOCS_V9 = ("DOC-03", "DOC-05")
NAME_ASK_V9 = re.compile(r"이름|종류|제품|모델|상표|품명|브랜드|(?:뭐|뭘|무엇을|무슨\s*\S+|어떤\s*\S+)\s*(?:를\s*|을\s*)?(?:써|쓰|발라|바르|넣|채워)")


def _row_id_v9(line: str) -> str:
    """표 줄의 머리 + 첫 칸 값 (부위·항목 — 이 줄이 무엇에 대한 줄인지). "외함 — 항목: 웨이 커버 점검·윤활 · …" → "외함 웨이 커버 점검·윤활"."""
    head, cells = FU2.split_line(line)
    if head is None:
        return line.split(" · ")[0]
    return head + " " + cells[0].split(": ", 1)[1]


def row_meta_v9(chunk: Chunk) -> dict[str, int]:
    """조각의 줄 글(plain_lines와 같은 변환) → 표 번호 (표가 아닌 줄은 0). pick_lines와 같은 규칙으로 표를 센다."""
    raw, out, header, table_no = chunk.text.splitlines(), {}, None, 0
    for i, line in enumerate(raw):
        s = line.strip()
        nxt = raw[i + 1].strip() if i + 1 < len(raw) else ""
        if not s.startswith("|"):
            header = None
        elif SEP.fullmatch(nxt or "x"):
            header, table_no = _cells(s), table_no + 1
            continue
        elif SEP.fullmatch(s):
            continue
        if s.startswith("|") and header and len(header) >= 3:
            cells = _cells(s)
            plain = _clean(cells[0]) + " — " + " · ".join(f"{_clean(h)}: {_clean(v)}" for h, v in zip(header[1:], cells[1:]) if _clean(v))
        else:
            plain = _clean(line)
        if len(plain) >= 8 and not set(plain) <= set("-: |·—"):
            out.setdefault(plain, table_no if s.startswith("|") else 0)
    return out


def sibling_filter_v9(question: str, sel: dict) -> dict:
    """고른 줄을 (조각, 표)로 묶어, 줄이 둘 이상인 묶음에서 "가르는 대상 낱말"(질문 내용 낱말 − 묻는 말, 용어집 동의어 포함 — 묶음의 일부
    줄에만 든 낱말)이 하나도 없는 줄을 뺀다. 묶음의 모든 줄에 든 낱말(예: 모든 줄이 그리스 줄일 때 "그리스")은 가르지 않는다.
    두 대상을 함께 물으면 두 대상 줄이 다 남는다. 줄을 모두 빼게 되면 그대로. 줄을 뺐으면 LLM 앞머리를 비운다.
    이름·종류를 묻는 질문(NAME_ASK_V9)에만 걸고, 가르는 낱말이 남길 줄의 머리·첫 칸(_row_id_v9)에 있는 묶음만 거른다."""
    lines, chs = list(sel["lines"]), list(sel.get("line_chunks") or [])
    words = [w.lower() for w in content_words(question) if w not in ASK_V9 and not w.isdigit()]
    if not words or len(chs) != len(lines) or len(lines) < 2 or not NAME_ASK_V9.search(question):
        return sel
    syn = synonyms()

    def present(t: str) -> set[str]:
        low = t.lower()
        return {w for w in words if w in low or bool(syn.get(w) and syn[w].lower() in low)}

    groups: dict = {}
    for i, (t, c) in enumerate(zip(lines, chs)):
        if c.doc_id in SIBLING_SKIP_DOCS_V9:
            continue
        tbl = row_meta_v9(c).get(t, 0)
        if tbl:
            groups.setdefault((c.chunk_id, tbl), []).append(i)
    drop = set()
    for idx in groups.values():
        if len(idx) < 2:
            continue
        has = {i: present(lines[i]) for i in idx}
        split = set().union(*has.values()) - set.intersection(*has.values())   # 묶음의 일부 줄에만 든 대상 낱말
        kept = [i for i in idx if has[i] & split]
        if split and all(present(_row_id_v9(lines[i])) & split for i in kept):   # 가르는 낱말이 남길 줄의 머리·첫 칸에 있다
            drop |= {i for i in idx if not (has[i] & split)}
    if not drop or len(drop) >= len(lines):
        return sel
    keep = [i for i in range(len(lines)) if i not in drop]
    new_lines, new_chs = [lines[i] for i in keep], [chs[i] for i in keep]
    if SL.on():   # STEP_LOG: 보인 줄 거르기 — LLM이 함께 고른 같은 표의 대상 아닌 형제 줄을 뺐다
        SL.step("보인 줄 거르기", 종류="같은 표 형제 줄", 뺀수=len(drop), 전=_sl_lines(lines), 후=_sl_lines(new_lines))
    chunks, seen = [], set()
    for c in new_chs:
        if c.chunk_id not in seen:
            seen.add(c.chunk_id)
            chunks.append(c)
    # 앞머리는 처음 고른 줄 전체의 요약이라 뺀 줄 내용을 말할 수 있다 ("공구 교환장치 … 에도 같은 그리스", 빠른 확인 2026-10-13) — 비운다
    return {**sel, "lead": "", "lines": new_lines, "chunks": chunks, "line_chunks": new_chs, "dropped": len(drop)}


# 번호 붙은 절차 표 채우기 (TABLE_FILL_V18, 2026-10-15 사용자 승인 계획 "전원 켜기 표 1·6번 빠짐"): 앱 화면에서 "전원을 켜고 원점 복귀할 때 사람이 조심할 게
# 뭐야?"에 DOC-01 §4.3 ①의 6줄 표 중 2~5번만 나왔다 — 줄 고르기(LLM)가 "질문에 직접 답하는 줄만" 골랐고, 다른 단계는 줄을 빼지 않았다(로그 없이 추정).
# 시동 절차를 말없이 일부만 보이면 안 된다(root-cause-guards 8절 "절차 목록은 자르지 않는다"). LLM 지시문·입력은 건드리지 않고(9차 E7-096: 지시 한 줄이
# 줄 고르기를 흔들었다), 줄 고르기·따로 검증·코드 검사를 모두 지난 뒤 보일 줄에서만 같은 표의 나머지 줄을 문서 순서대로 채운다.
# 대상: 모든 데이터 줄의 첫 칸이 1, 2, 3 … 으로 이어지는 표(줄 수 2 이상 MAX_TABLE_ROWS 이하). 고장 대응(DOC-03)·안전 작업(DOC-05) 줄은 건드리지 않는다
# (이미 규칙이 처리). 12줄을 넘는 표는 줄이는 일이 아니라 늘리는 일이라 그대로 둔다.
def table_fill_on(s=None) -> bool:
    s = s or settings()
    return bool(v8_on(s) and s.table_fill_v18)


def numbered_tables_v18(chunk: Chunk) -> dict[int, list[str]]:
    """조각 안의 번호 붙은 절차 표 → {표 번호: [줄 글(plain_lines와 같은 변환), …] 문서 순서}. row_meta_v9와 같은 규칙으로 표를 센다."""
    raw, header, table_no = chunk.text.splitlines(), None, 0
    rows: dict[int, list[tuple[str, str]]] = {}
    for i, line in enumerate(raw):
        s_line = line.strip()
        nxt = raw[i + 1].strip() if i + 1 < len(raw) else ""
        if not s_line.startswith("|"):
            header = None
            continue
        if SEP.fullmatch(nxt or "x"):
            header, table_no = _cells(s_line), table_no + 1
            continue
        if SEP.fullmatch(s_line) or not header:
            continue
        cells = _cells(s_line)
        if len(header) >= 3:
            plain = _clean(cells[0]) + " — " + " · ".join(f"{_clean(h)}: {_clean(v)}" for h, v in zip(header[1:], cells[1:]) if _clean(v))
        else:
            plain = _clean(line)
        rows.setdefault(table_no, []).append((_clean(cells[0]), plain))
    out: dict[int, list[str]] = {}
    for no, items in rows.items():
        firsts = [f for f, _ in items]
        if 2 <= len(items) <= MAX_TABLE_ROWS and firsts == [str(n) for n in range(1, len(items) + 1)]:
            out[no] = [p for _, p in items if len(p) >= 8 and not set(p) <= set("-: |·—")]
    return out


def table_fill_v18(lines: list[str], chunks: list, s=None) -> tuple[list[str], list] | None:
    """고른 줄(lines)과 그 줄의 조각(chunks, 같은 길이) → 번호 붙은 절차 표의 줄이면 그 표의 나머지 줄을 문서 순서로 채운 (줄, 조각). 바뀐 것이 없으면 None."""
    if not table_fill_on(s) or not lines or len(chunks) != len(lines):
        if SL.on() and lines:   # STEP_LOG: 채우기를 하지 않은 까닭 (꺼져 있는지 / 줄과 조각이 어긋났는지)
            SL.step("보인 줄 채우기", 종류="번호 붙은 절차 표 채우기 (TABLE_FILL_V18)", 바뀜=False,
                    까닭="스위치가 꺼져 있음" if not table_fill_on(s) else "줄과 조각의 수가 다름", 전번호=_sl_nums(lines))
        return None
    out_lines, out_chunks, done = [], [], set()
    for t, ch in zip(lines, chunks):
        tbl = 0 if ch.doc_id in SIBLING_SKIP_DOCS_V9 else row_meta_v9(ch).get(t, 0)
        rows = numbered_tables_v18(ch).get(tbl) if tbl else None
        if not rows or t not in rows:
            out_lines.append(t)
            out_chunks.append(ch)
            continue
        if (ch.chunk_id, tbl) in done:
            continue   # 이 표는 앞 줄에서 통째로 넣었다
        done.add((ch.chunk_id, tbl))
        out_lines.extend(rows)
        out_chunks.extend([ch] * len(rows))
    changed = out_lines != list(lines)
    if SL.on():   # STEP_LOG: 번호 붙은 절차 표 채우기 — 채우기 전후의 표 줄 번호 (화면에서 2~5번만 나온 일을 이 칸으로 확인한다)
        SL.step("보인 줄 채우기", 종류="번호 붙은 절차 표 채우기 (TABLE_FILL_V18)", 바뀜=changed, 전번호=_sl_nums(lines), 후번호=_sl_nums(out_lines),
                전=_sl_lines(lines), 후=_sl_lines(out_lines) if changed else None, 조각=sorted({ch.chunk_id for ch in chunks}))
    return None if not changed else (out_lines, out_chunks)


@lru_cache(maxsize=1)
def _corpus_index() -> dict[str, int]:
    return {c.chunk_id: i for i, c in enumerate(load_corpus())}


def _corpus_pos(chunk: Chunk) -> int:
    """문서 순서 (용어집 → DOC-01 … DOC-07, 절 순서 = 사내 문서 파일 안의 차례)."""
    return _corpus_index().get(chunk.chunk_id, 10**6)


def _budgeted(cands: list[Chunk]):
    """고르기 후보 글자 한도(jobs.MAX_SELECT_CHARS)에 드는 줄을 **순위 순서로** 먼저 정한다. 순서를 바꿔도 같은 줄만 보이게
    (돌려주는 값 = 줄이 하나라도 든 조각(순위 순서), 그 조각의 든 줄만 돌려주는 줄 함수)."""
    keep, size = {}, 0
    for c in cands:
        lines = []
        for t in plain_lines(c):
            if size + len(t) > jobs.MAX_SELECT_CHARS:
                break
            lines.append(t)
            size += len(t)
        if lines:
            keep[c.chunk_id] = lines
        if size + 1 > jobs.MAX_SELECT_CHARS or len(lines) < len(plain_lines(c)):
            break
    return [c for c in cands if c.chunk_id in keep], (lambda c: keep.get(c.chunk_id, []))


def _tier2(question: str, route: Route, traces: list, line_fn=None, side: dict | None = None) -> tuple[str, list[dict], dict] | None:
    """2차 문지기 (DOC_GATE=tiered): 원래 질문과 LLM이 바꿔 쓴 검색어(검색에만 씀)로 다시 찾고,
    엄격한 줄 고르기 → 따로 검증 → 코드 검사(낱말 겹침·답 종류)를 모두 통과할 때만 원문 줄 그대로 보인다(AI 앞머리 없음).
    하나라도 실패하면 None (문서에 없음). 업계 근거: 충분한 문맥 판정·다시 쓰기 검색 (개선안_업계표준_조사_20261010.md 1절).
    8차: line_fn = 후보 줄 함수(알람 + 문서 함께일 때 카드가 보인 줄을 뺀 것), side = 줄마다 출처를 담아 돌려줄 곳."""
    got = _tier2_cands(question, route)
    if got is None:
        return None
    cands, dense_used = got
    return _tier2_decide(question, cands, traces, dense_used, line_fn=line_fn, side=side)


def _tier2_cands(question: str, route: Route) -> tuple[list[Chunk], bool] | None:
    """2차 문지기 후보 조각 (원래 질문 + LLM 검색어 [+ 뜻 검색]을 합친 순위 3개 [+ 원래 질문 1등]), 뜻 검색을 썼나."""
    if v7_on() and no_subject_v7(question):   # 6차: 찾을 주제가 없는 질문은 LLM 검색어로도 찾지 않는다
        if SL.on():
            SL.step("3 찾기", 질문=question, 길="2차 문지기", 통과=False, 까닭="찾을 주제 낱말이 없음")
        return None
    own =[c for _, c in search(strip_shape_v7(question) if v7_on() else question, 15)]   # 6차: 답 모양 낱말 뺌
    rankings = [own] + [[c for _, c in search(q, 15)] for q in route.queries]
    dense_used = False
    if settings().retrieval == "hybrid":
        d = dense_search(question, 15)
        if d:
            rankings.append([c for _, c in d])
            dense_used = True
    sl_queries = ([question] + list(route.queries)) if SL.on() else None   # STEP_LOG: 질문별 상위 조각 (rankings에서 빈 목록을 빼기 전의 짝)
    sl_tops = [[c.chunk_id for c in r[:3]] for r in rankings] if SL.on() else None
    rankings = [r for r in rankings if r]
    if not rankings:
        if SL.on():
            SL.step("3 찾기", 질문=question, 길="2차 문지기", 통과=False, 까닭="검색 결과 없음", 검색어=list(route.queries))
        return None
    cands = rrf(*rankings)[:3]
    if settings().split_q and own and own[0].chunk_id not in {c.chunk_id for c in cands}:
        # LLM이 바꿔 쓴 검색어는 찾는 범위를 넓히는 데만 쓴다 — 원래 질문의 1등 조각이 밀려났으면 4번째 후보로 붙인다.
        # 2026-10-10 F02(답이 있는 DOC-05 §6.5가 밀려남)·F14에서 이득. 3번째 자리를 바꾸면 C01의 답 조각을 잃어 붙이기로 함.
        # 같은 서버 상태에서 붙임/뺌을 이어 돌린 비교(흔들린 문항 16개 × 3번): 붙이면 F02·F14 맞음, 나머지 같음. 글자 상한 6,000자는 그대로
        cands = cands + [own[0]]
    if v11b_on() and TERM_Q_V11B.search(question):
        # 10차 보강 (PARSE_V11, 2026-10-14 사용자 결정): 표준 용어를 묻는 질문은 용어집 조각을 후보 맨 앞에 둔다.
        # 앱 화면 "MTBF … 한국어 표준 용어로 바꾸면 뭐라고 써(?)": 줄 고르기가 "표준어" 낱말이 없는 DOC-07 §6.2 줄을 골라
        # 따로 검증이 경계에 섰고, 끝의 "?" 하나로 답·"문서에 없음"이 갈렸다 (로그 2026-10-14). 순서만 바꾸고 뺄 것은 없다.
        gloss = next((c for r in rankings for c in r[:15] if c.doc_id == "GLOSSARY"), None)
        if gloss is not None:
            cands = [gloss] + [c for c in cands if c.chunk_id != gloss.chunk_id]
    if SL.on():   # STEP_LOG 3단계: 2차 문지기 — 원래 질문과 LLM 검색어로 각각 찾은 상위 조각, 합쳐 고른 후보 조각 (후보 순서가 줄 고르기의 입력 순서)
        SL.step("3 찾기", 질문=question, 길="2차 문지기", 통과=True, 검색어=list(route.queries), 질문별상위=dict(zip(sl_queries, sl_tops)),
                후보=[_sl_chunk(c) for c in cands], 뜻검색=dense_used)
    return cands, dense_used


# 표준 용어를 묻는 꼴 (10차 보강). "어떻게 써"는 쓰는 법(사용법) 질문과 겹쳐 넣지 않는다.
TERM_Q_V11B = re.compile(r"표준\s*(?:용어|어)|정식\s*(?:용어|명칭)|쓰지\s*않는\s*말|뭐라고\s*(?:써|적|불러|부르|해야)")


# 10차 보강 TERM_V13 ② (2026-10-14 사용자 결정 "보일 줄에서만 빼기"): 용어(표준어·영어 이름)를 묻는 질문에서 고른 줄에 용어집 줄이 있으면
# 다른 문서 줄은 보일 줄에서 뺀다 — 앱 화면 "이송 속도 영어로 뭐라고 해"에 DOC-03 알람 점검 줄 둘이 섞였다.
# 줄 고르기·따로 검증·코드 검사를 모두 지난 뒤에만 한다(LLM 입력은 그대로 — 9차 E7-096). 줄을 뺐으면 AI 앞머리를 비운다.
TERM_Q_V13 = re.compile(TERM_Q_V11B.pattern + r"|영어\s*(?:로|이름|명)|영문\s*(?:이름|명)|뭐라고\s*(?:해|불러|부르)")


def term_v13_on(s=None) -> bool:
    s = s or settings()
    return bool(v8_on(s) and s.term_v13)


def gloss_only_v13(question: str, lines: list[str], cites: list[dict], s=None) -> tuple[list[str], list[dict]] | None:
    """뺄 것이 있으면 (용어집 줄, 그 출처), 없으면 None. 용어집 줄이 하나도 없거나 모두 용어집이면 그대로."""
    if not term_v13_on(s) or not TERM_Q_V13.search(question) or len(cites) != len(lines):
        return None
    keep = [i for i, c in enumerate(cites) if (c or {}).get("doc_id") == "GLOSSARY"]
    if not keep or len(keep) == len(lines):
        return None
    if SL.on():   # STEP_LOG: 보인 줄 거르기 — 용어(표준어·영어 이름)를 묻는 질문은 용어집 줄만 남겼다
        SL.step("보인 줄 거르기", 종류="용어 질문은 용어집 줄만 (TERM_V13)", 뺀수=len(lines) - len(keep), 전=_sl_lines(lines), 후=_sl_lines([lines[i] for i in keep]))
    return [lines[i] for i in keep], [cites[i] for i in keep]


# 10차 보강 TERM_V13 ③ 틀 답 (2026-10-14 사용자 결정 "틀 답 넣기"): 영어 이름을 묻는 질문은 9B가 영문 자리표를 쓰지 못해 새로 쓴 답이
# 늘 막혔다(짝 질문 6/6). 보일 줄이 모두 용어집 줄이고 질문 속 낱말과 표준어가 맞는 줄이 하나뿐이면, 프로그램이 원문 칸으로 문장을 만든다
# ("이송 속도의 영어 이름은 Feed Rate입니다." — 조사가 필요 없는 꼴). LLM은 쓰지 않는다.
GLOSS_ROW_V13 = re.compile(r"^(?P<eng>[^—]+?) — 표준어: (?P<std>[^·]+?)(?: · |$)")


def english_template_v13(question: str, lines: list[str], cites: list[dict], s=None) -> str | None:
    if not term_v13_on(s) or not FU2.ENGLISH_Q_V13.search(question) or not lines or len(cites) != len(lines):
        return None
    if any((c or {}).get("doc_id") != "GLOSSARY" for c in cites):
        return None
    q = re.sub(r"\s", "", question)
    hits = []
    for line in lines:
        m = GLOSS_ROW_V13.match(line)
        if not m:
            continue
        std = re.sub(r"\s*\([^)]*\)", "", m["std"]).replace("**", "").strip()
        eng = m["eng"].strip()
        if std and re.search(r"[A-Za-z]", eng) and re.sub(r"\s", "", std) in q:
            hits.append((len(std), std, eng))
    hits.sort(reverse=True)
    if not hits or (len(hits) > 1 and hits[0][0] == hits[1][0]):
        return None
    _, std, eng = hits[0]
    if SL.on():   # STEP_LOG: LLM 없이 프로그램이 만든 영어 이름 틀 답
        SL.step("영어 이름 틀 답", 표준어=std, 영문=eng, 줄=_sl_lines(lines))
    return f"{std}의 영어 이름은 {eng}입니다."


def lead_v12_on(s=None) -> bool:
    """LEAD_V12: 1차 문지기 길 AI 앞머리 검사 (10차 보강, 2026-10-14)."""
    s = s or settings()
    return bool(v8_on(s) and s.lead_v12)


def v11b_on(s=None) -> bool:
    """PARSE_V11: 10차 보강 (표준 용어 질문의 용어집 줄 앞에 — 영문 약어 조사는 followup_v2.tidy_acronym_v11b)."""
    s = s or settings()
    return bool(v8_on(s) and s.parse_v11)


def _tier2_decide(question: str, cands: list[Chunk], traces: list, dense_used: bool = False,
                  line_fn=None, side: dict | None = None) -> tuple[str, list[dict], dict] | None:
    """2차 문지기 판정: 엄격한 줄 고르기 → 따로 검증 → 코드 검사. line_fn을 주면(후보 순서 실험) 순서를 그대로 쓴다.
    8차 (FLOW_V9): 같은 표 형제 줄을 거른 뒤 따로 검증한다. side["line_cites"] = 줄마다 출처.
    대상 한정 지시 한 줄(prompts.SELECT_TARGET_V9)은 여기(엄격한 고르기)에는 넣지 않는다 — 빠른 확인에서 E4-050 "25050 … RESET은 어디서"의
    답 줄을 "답할 줄 없음"으로 거부하게 만들었다(그 줄만 끄면 두 번 모두 고름, 2026-10-13). 형제 줄은 코드 거르기가 맡는다."""
    order = "rank" if line_fn else settings().cand_order
    flow = flow_on()
    if order == "rank":
        sel, tr = jobs.select_lines(question, cands, line_fn or plain_lines, _head, strict=True)
        tr["tier"] = 2
        traces.append(tr)
    else:  # 후보 순서 실험 (CAND_ORDER, 2026-10-10 3차 — 보이는 세트에서만 잰다)
        chosen, line_fn = _budgeted(cands)
        orders = [sorted(chosen, key=_corpus_pos)] if order == "doc" else [chosen, chosen[::-1]]
        sel = None
        for k, cs in enumerate(orders):  # dual: 순위 순서로 못 고르면 역순으로 한 번 더 (하나라도 답할 수 있으면 따로 검증)
            sel, tr = jobs.select_lines(question, cs, line_fn, _head, strict=True)
            tr.update(tier=2, cand_order=order if k == 0 else order + ":reversed")
            traces.append(tr)
            if sel or (tr.get("reason") or "").startswith("LLM 오류"):
                break
    if not sel:
        return None
    if flow:
        sel = sibling_filter_v9(question, sel)
        if sel.get("dropped"):
            tr["sibling_dropped"] = sel["dropped"]
    if side is not None:
        side["line_cites"] = [_line_cite(ch) for ch in sel.get("line_chunks") or []]
        side["line_chunks"] = list(sel.get("line_chunks") or [])   # TABLE_FILL_V18: 줄마다 그 줄의 조각 (표를 찾는 데 쓴다)
        side["lines"] = list(sel["lines"])   # 10차: 줄 글 안에도 " / "가 있어(용어집 "MTTR / MTBF") 결론을 다시 쪼개지 않게 그대로 넘긴다
    ok, vtr = jobs.verify(question, sel["lines"])
    traces.append(vtr)
    if not ok:
        return None
    words, syn = content_words(question), synonyms()
    body = " ".join(sel["lines"]).lower()
    hit = sum(1 for w in words if w in body or bool(syn.get(w) and syn[w].lower() in body))
    min_overlap = tier2_min_overlap()   # ANSWER_GATE_V17: 0.2 → 0.1 (구어체 질문의 맞는 답을 죽이던 문턱)
    if words and hit / len(words) < min_overlap and settings().parse_v2 and settings().parse_v3:
        # 용어집 질문("레귤레이터라고 부르는 거 …"): 질문의 별명과 그 표준어가 고른 줄에 있으면 겹친 것으로 본다
        ql_ = question.lower()
        if any(len(k) >= 2 and k.lower() in ql_ and (k.lower() in body or v.lower() in body) for k, v in syn.items()):
            hit = len(words)
    if words and hit / len(words) < min_overlap:
        vtr.update(used=False, reason=f"코드 검사: 질문 낱말 겹침 {hit}/{len(words)}")
        if SL.on():   # STEP_LOG 6단계: 2차 문지기 코드 검사 — 질문 낱말이 고른 줄에 충분히 있나 (문턱 미달이면 "문서에 없음")
            SL.step("6 코드 검사", 길="2차 문지기", 결과="실패", 까닭="질문 낱말 겹침 문턱 미달", 겹침=f"{hit}/{len(words)}", 문턱=min_overlap,
                    낱말=words[:12], 줄=_sl_lines(sel["lines"]))
        return None
    type_ok = answer_type_ok(question, " ".join(sel["lines"]))
    if SL.on():   # STEP_LOG 6단계: 낱말 겹침은 지났다. 답 종류(가격·전화번호·시각·부품번호 …) 검사 결과
        SL.step("6 코드 검사", 길="2차 문지기", 결과="통과" if type_ok else "실패", 까닭=None if type_ok else "묻는 값의 꼴이 줄에 없음",
                겹침=f"{hit}/{len(words)}" if words else "낱말 없음", 문턱=min_overlap, 답종류검사=bool(type_ok), 줄=_sl_lines(sel["lines"]))
    if not type_ok:
        vtr.update(used=False, reason="코드 검사: 묻는 값의 꼴이 줄에 없음")
        return None
    return (TIER2_PREFIX + " " + " / ".join(sel["lines"]), [_cite(ch) for ch in sel["chunks"]],
            {"mode": settings().retrieval, "dense_used": dense_used, "reason": None, "basis": "llm_relaxed"})


# 8차 ④ (FLOW_V9): 알람 번호 + 설명 질문은 알람 카드와 문서 검색을 함께 한다 (E7-050 "2075 … 보충은 원래 얼마마다"·E6-032 —
# 지금은 doc_cue 낱말이 있을 때만 문서를 찾아 카드만 답했다). 카드가 이미 다루는 말(번호·이름·뜻·원인·조치·점검·누가·심각도)과
# 운영 조회 말(횟수·날짜·설비)을 빼고도 주제 낱말이 남을 때만 찾는다 — "552 뜨면 뭐부터 해?"는 카드만
ALARM_PLAIN_V9 = ("알람", "경보", "뜨", "떴", "떠", "뜬", "났", "나면", "나는", "찍혔", "찍힌", "발생", "울렸", "횟수", "자주", "자꾸",
                  "지난", "이번", "최근", "어제", "오늘", "그저께", "야간", "주간", "밤", "낮", "장비", "설비", "호기", "일호", "이호",
                  "몇", "건", "번", "의미", "뜻", "설명", "내용", "정체", "이름", "영문", "영어", "한국", "한글", "우리말", "원인", "이유",
                  "조치", "대응", "처리", "해결", "점검", "순서", "먼저", "뭐", "무슨", "무엇", "어떤", "누가", "누구", "심각", "위험", "등급",
                  "어떻게", "왜", "작업자", "보전", "이거", "이것", "그거", "화면", "다시", "계속", "또",
                  "때문", "직접", "제일", "같이", "다음", "지금", "새로", "정확", "어느", "나와", "나오")
ALARM_PLAIN_EXACT_V9 = frozenset(("전에", "뒤에", "후에", "앞에", "중에", "때도", "때는"))   # 때 말 (앞글자로 보면 "전기·전압·후드"까지 빠진다)


def alarm_topic_left_v9(question: str, alarms_: list[dict], card: str = "") -> list[str]:
    """한 마디 알람 질문에서 카드·운영 조회가 다루지 않는 주제 낱말 (없으면 빈 목록 → 카드만). 세지 않는 말: 번호·날짜, 알람 이름,
    카드·조회 말(ALARM_PLAIN_V9), 묻는 말, 동사 꼴로 끝나는 말("돼요·하면"), 사내 문서에 없는 말("거예·주세"), 카드 글(card)에 이미 있는 말."""
    master = alarm_codes()
    question = CAUSE_POSSIBLE.sub(r"\1", question)   # "가능한 원인이 뭐야?" — "가능한"이 남아 문서 추가 검색을 켜면 다른 알람 절을 끌어온다 (기준선 21/23)
    names: set[str] = set()
    for a in alarms_:
        m = master.get(a["code"]) or {}
        for nm in (m.get("name_ko") or "", m.get("name_en") or ""):
            names |= {w.lower() for w in re.findall(r"[가-힣]+|[A-Za-z]+", nm) if len(w) >= 2}
    vocab, card = corpus_words(), card.lower()
    out = []
    for w in content_words(question):
        lw = w.lower()
        if (re.match(r"\d", lw) or lw.startswith(ALARM_PLAIN_V9) or EQUIP_RE_V5.fullmatch(w)   # 숫자로 시작 = 번호·날짜("9월에")
                or any(lw in n or n in lw for n in names) or lw in GENERIC_V7 or SHAPE_TOKEN_V7.fullmatch(lw)
                or lw in FU_FILL_V9 or lw in ASK_V9 or lw in ALARM_PLAIN_EXACT_V9 or len(lw) < 2):
            continue
        if (re.fullmatch(r"[가-힣]+", lw) and lw.endswith(VERB_TAIL)) or lw in card or not any(lw in v for v in vocab):
            continue
        out.append(w)
    return out


def _clauses_v9(question: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[?？.!])\s+|(?<=고),\s*", question.strip()) if x.strip()]


SCOPE_KEYS_V10 = ("start", "end", "shift", "equipment", "lot", "order")


def alarm_ops_split_v10(question: str, p: dict, s) -> tuple[dict, dict] | None:
    """9차 FLOW_V10 (1부 원인 I): 알람 번호가 든 질문을 물음 마디로 나눌 수 있으면 운영 조회를 마디마다 해석한다.
    "2075가 왜 자꾸 떠? 어제 야간 VF2-01 몇 번 멈췄어?"를 한 번에 풀면 둘째 마디의 날짜·설비가 알람 횟수·작업기록에도 걸려
    "09-30 야간 알람 2075 발생: 없음"이 됐다(같은 답의 관련 줄은 "30일 4번"). 알람 마디는 그 마디의 해석(날짜가 없으면 기본 기간),
    다른 마디는 그 마디의 날짜·설비로 조회한다. 나눌 수 없거나, 다른 마디에 운영 의도가 없거나, 범위가 원래와 같으면 None (지금 동작)."""
    codes = {a["code"] for a in p["alarms"]}
    clauses = _clauses_v9(question)
    if not codes or len(clauses) < 2:
        return None
    a_cl = [c for c in clauses if codes & {a["code"] for a in parse(c)["alarms"]}]
    o_cl = [c for c in clauses if c not in a_cl]
    if not a_cl or not o_cl:
        return None
    subs = []
    for text in (" ".join(a_cl), " ".join(o_cl)):
        q = parse(text)
        q["raw"] = text
        if s.parse_v2 and s.parse_v3 and s.parse_v4 and (q.get("future") or (v5_on(s) and q.get("outside"))):
            q = dict(q, intents=[i for i in q["intents"] if i not in DATED_INTENTS_V4])   # 기준 시각 뒤·기간 밖 날짜 (원래 길과 같게)
        subs.append(q)
    pa, po = subs
    if not po["intents"] or all(pa.get(k) == p.get(k) for k in SCOPE_KEYS_V10):
        return None
    return pa, po


def alarm_doc_plan_v9(question: str, alarms_: list[dict], card: str) -> str | None:
    """알람 + 문서 함께의 문서 검색 글, 찾지 않을 질문이면 None.
    - 운영 마디(횟수·날짜 조회)와 다른 마디가 함께 있으면 다른 마디를 문서 질문으로 (E7-050·E6-051·E5-020 — "… 몇 번 났어? 보충은 원래
      얼마마다 …"의 뒷 마디. 카드에 "보충" 낱말이 있어도 카드는 주기를 답하지 않는다).
    - 그 밖(한 마디 질문)은 카드가 다루지 않는 주제 낱말이 남을 때만 질문 전체로 ("552 뜨면 뭐부터 봐?"는 카드만).
    한 마디 질문은 검색 글에 알람 번호·이름이 없으면 알람 한국어 이름을 앞에 붙인다 (E6-032 화면 알람 "이 알람은 프로그램 돌아가는 중에도
    떠요?" — 번호 없이 찾아 다른 알람의 조작 안내 줄을 찾았다). 나눈 마디에는 붙이지 않는다 — 붙이면 검색이 그 알람 절 쪽으로 쏠려
    "몇 번 나면 반복 알람으로 잡혀요?"(DOC-03 §1.4)를 놓쳤다 (E2-062·E4-030, LLM 끈 비교에서 찾음)."""
    clauses = _clauses_v9(question)
    if len(clauses) >= 2:
        ops = [c for c in clauses if any(rx.search(COMPOUND_MASK_V3.sub(" ", c.lower())) for _, rx in OPS_INTENTS_V9)]
        rest = [CONJ_V5.sub("", c) for c in clauses if c not in ops]
        if ops and any(rest):
            return " ".join(r for r in rest if r)
    if not alarm_topic_left_v9(question, alarms_, card):
        return None
    q = question
    code = alarms_[0]["code"]
    m = alarm_codes().get(code) or {}
    name = re.sub(r"\([^)]*\)", "", m.get("name_ko") or "").strip()
    squash = lambda t: re.sub(r"\s+", "", t)  # noqa: E731 — "축윤활유 저장소"처럼 띄어쓰기가 달라도 같은 이름
    if name and squash(name) not in squash(q) and not re.search(rf"(?<![0-9A-Za-z.]){re.escape(code.split('.')[0])}(?![0-9])", q):
        q = name + " " + q
    return q


def alarm_own_sections_v9(alarms_: list[dict]) -> set[tuple[str, str]]:
    """알람 카드가 이미 보인 절 (DOC-02 알람 절·DOC-03 점검 순서 절) — 함께 하는 문서 검색의 후보에서 뺀다
    (점검 순서는 LLM에 보내지 않는다, 규칙 3.4. 같은 글을 두 번 보이지 않는다)."""
    out = set()
    master = alarm_codes()
    for a in alarms_:
        m = master.get(a["code"]) or {}
        for ref in (m.get("doc02_section") or "", m.get("doc03_section") or ""):
            if "§" in ref:
                d, sec = (x.strip() for x in ref.split("§"))
                out.add((d, sec))
    return out


# 8차 ⑤ (FLOW_V9): 섞인 질문의 문서 쪽 마디는 홀로 선 질문으로 다시 분류(그 마디만의 검색어)해 문서 흐름 전체(1차 문지기 → 줄 고르기 →
# 따로 검증 → 2차 문지기)로 답한다 (E7-059·079, E6-051·052·054 — 운영 답만 나가고 문서 쪽이 빠졌다). 운영 쪽은 지금 길 그대로
MIXED_DOC_MISS_V9 = "기준·규칙을 물으신 부분은 사내 문서에서 찾지 못했습니다."   # 숫자를 넣지 않는다


def doc_side_route_v9(doc_q: str, s, traces: list) -> Route | None:
    """섞인 질문의 문서 쪽 마디를 문서 질문으로 분류한 Route (검색어는 LLM 분류에서). 마디가 사람만 할 일·조작 요청 꼴이면 None (문서 쪽을 버림)."""
    if human_only(doc_q):
        return None
    pd = parse(doc_q)
    pd["raw"] = doc_q
    if use_llm_route(doc_q, pd, s):
        r = decide_route(doc_q, pd, s)
        if r.trace:
            traces.append(r.trace)
        if r.kind == "action":
            return None
        return Route("doc", [], [], None, None, None, list(r.queries), r.source + " (문서 쪽 마디)")
    return Route("doc", [], [], None, None, None, [], "규칙 (문서 쪽 마디)")


def answer_blocks(parts: list[str], ops_final: str | None, doc_lines: list[str], conclusion: str,
                  tail: list[str] | tuple = ()) -> list[dict]:
    """줄 목록 칸 (7차 C, 화면 표시 전용 — conclusion 글자는 그대로, 채점·스냅숏은 보지 않는다).
    프로그램이 문서 줄을 " / "로 잇는 곳에서 줄을 다시 나눈다 (사내 문서 안에도 " / "가 있어 화면에서는 쪼갤 수 없다).
    다시 이은 글이 conclusion과 다르면 통째 한 칸으로 돌려준다 (어긋난 줄을 보이지 않게). tail = 8차 꼬리 안내(운영 글 뒤)."""
    joined = " / ".join(doc_lines)
    out = []
    for p in parts:
        if doc_lines and p.endswith(joined):
            head = p[: len(p) - len(joined)].strip()
            if head:
                out.append({"kind": "lead", "text": head})
            out += [{"kind": "line", "text": x, "safety": FU2.is_safety(x)} for x in doc_lines]
        else:
            out.append({"kind": "text", "text": p})
    if ops_final:
        out.append({"kind": "text", "text": ops_final})
    out += [{"kind": "text", "text": t} for t in tail]
    rebuilt = " ".join(parts + ([ops_final] if ops_final else []) + list(tail))
    return out if rebuilt == conclusion else [{"kind": "text", "text": conclusion}]


# ---------------------------------------------------------------- 순수 외부 LLM 연결 (PURE_EXTERNAL, 2026-10-15 — 시험용 복사본 전용, research_notes/순수외부LLM_연결_20261015.md)
# 문서 질문 답 = 낱말 검색 상위 조각(PURE_TOPK) + 질문 → 외부 Claude 1번 → 그 답을 그대로 보인다. 줄 고르기·따로 검증·새 글 검사(코드 검사·안전 엄격 검사·뜻 판정·재시도)·
# 낱말 겹침·답 종류 검사·표 채우기·분류 LLM은 이 길에서 부르지 않는다(코드는 그대로 두고 건너뛴다). 프로그램이 하는 일: 검색, 조각 번호 → 출처 변환, 근거 조각의 원문 줄 붙이기,
# 원문 출처 표기 차단(FORBIDDEN — 저작권 규칙 D-03, 답 내용 검사가 아니다), 고정 주의 문구.
PURE_MODE_V19 = "순수 연결 (검사 없음, 원문 출처 표기 차단만)"
PURE_NO_DOC_V19 = "문서에 없음 — 사내 문서(DOC-01~07, 용어집)에서 질문에 답할 근거를 찾지 못해 답을 만들지 않았습니다."
PURE_CAUTION_SAFETY_V19 = ("근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, "
                           "전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.")
PURE_CAUTION_V19 = "근거 안내이며 실행 지시가 아닙니다."
# 말투 바꾸기(PURE_STYLE=1, 2026-10-15): 검색 결과가 없어 Claude를 부르지 않을 때의 짧은 해요체 문구 (끔이면 위 PURE_NO_DOC_V19 그대로). 끝 안전 문구는 두 말투 모두 위 상수 그대로다
PURE_NO_DOC_CHAT_V19 = "사내 문서에서 관련 내용을 찾지 못했어요. 쓰신 낱말을 바꿔서 다시 물어봐 주세요."
# 안전 질문(PURE_SAFETY=1)의 "답 없음" 문구 (2026-10-18): 못 찾은 것을 "문서에 없다"고 말하지 않는다. 상태는 기존 "확인 필요"(API로는 OK) — 새 상태 값을 만들지 않는다.
PURE_UNSURE_V19 = "자동으로 확인하지 못했습니다. 문서에 없다는 뜻은 아닙니다. 안전에 관한 질문이니 아래 안전 작업 기준서(DOC-05) 절을 직접 확인하거나 현장 담당자에게 확인해 주세요."
PURE_UNSURE_CHAT_V19 = "자동으로 확인하지 못했어요. 문서에 없다는 뜻은 아니에요. 안전에 관한 질문이니 아래 안전 작업 기준서(DOC-05) 절을 직접 확인하거나 현장 담당자에게 확인해 주세요."


# ---------------------------------------------------------------- 설비 이름만 든 글 · 되묻기 답 이어받기 · 못 읽은 조각 안내 · 기간 안내 (2026-10-20, 기획 설비이름_되묻기_안내)
# 설비 이름만 있는 글("VF2-01)")을 안전 질문으로 보던 것을 고치고, "설비를 알려 주세요"에 설비 이름으로 답하면 앞 질문과 잇고,
# 규칙이 못 읽은 조각(센서·정비현황·브리핑)과 기간이 다른 값을 말없이 넘기지 않는다. 새 스위치는 없다 (버그 수정 — 되돌릴 때는 git revert).
EQUIP_DOC_WHY_V21 = "신호가 설비 이름뿐이고 안전 낱말이 없는 질문 — 문서 질문으로 보고 안전망 없이 순수 길로 (2026-10-20)"
EQUIP_ONLY_END_V21 = re.compile(r"(?:이?요|이에요|예요|입니다|이야|야|은|는|이|가|을|를|도|만|에|의|로|으로)?")
ASKBACK_NEED_V21 = re.compile(r"알려 주세요: 설비 \(예: [^)]*\)\.?\s*$")   # ops_answer가 설비 하나만 되물은 답 ("… 다음을 알려 주세요: 설비 (예: VF2-01).")
EQUIP_ONLY_NOTE_V21 = "{names}에 대해 무엇을 볼까요? 예: '{e} OEE 어제값', '{e} 지금 상태 어때?', '{e} 정비 기한'"
UNREAD_V21 = [(re.compile(r"센서"), "센서 값"), (re.compile(r"정비\s*현황"), "정비현황"), (re.compile(r"브리핑"), "브리핑")]   # 이 채팅이 아직 못 하는 일의 이름 (목록 밖의 말은 추측하지 않는다)
UNREAD_NOTE_V21 = "이 채팅에서는 아직 {names}을 답하지 못했어요. 해당 화면에서 확인해 주세요."
KPI_DATED_WORDS_V21 = re.compile(r"OEE|가동률|성능|양품|지표|효율|KPI", re.I)
KPI_30D_ONLY_V21 = re.compile(r"MTTR|MTBF|평균\s*수리|평균\s*고장", re.I)
NO_DATE_NOTE_V21 = "기간을 정하지 않아 9월 한 달(9/1~9/30) 값이에요. 날짜를 말씀해 주시면 그날 값을 드려요 (예: '어제', '오늘')."
MIXED_PERIOD_NOTE_V21 = "OEE·가동률은 {rng} 값이고, MTTR·MTBF는 최근 30일 값이에요."


def equipment_only_v21(question: str, p: dict) -> bool:
    """설비 이름·별명·기호·조사뿐인 글인가 ("VF2-01)"·"vf2-01"·"1호기"·"2호기요"·"VF2-01 이요"). 규칙이 설비를 읽었고, 알람·날짜·운영 낱말·로트가 없고, 안전 낱말이 없고,
    이름을 지운 나머지가 조사뿐일 때만 참이다. 이름에 다른 말이 붙은 글("VF2-01 정비 상태는?")은 거짓."""
    if not p.get("equipment") or p.get("alarms") or p.get("intents") or p.get("start") or p.get("lot") or p.get("order"):
        return False
    if PURE.is_safety(question):
        return False
    rest = EQUIP_RE_V5.sub(" ", question)
    for rx, _ in EQUIP_ALIAS_V2 + EQUIP_ALIAS_V3:
        rest = rx.sub(" ", rest)
    return EQUIP_ONLY_END_V21.fullmatch(re.sub(r"[\W_]+", "", rest)) is not None


def equipment_only_answer_v21(base: dict, p: dict) -> dict:
    """설비 이름뿐인 글에 대한 안내 한 줄 (규칙 고정 문구 — Claude를 부르지 않는다)."""
    eqs = list(dict.fromkeys(p["equipment"]))
    text = EQUIP_ONLY_NOTE_V21.format(names="·".join(eqs), e=eqs[0])
    return {**base, "status": "안내", "mode": "규칙 (설비 이름뿐인 글 — 안내 고정 문구)", "conclusion": text, "blocks": [{"kind": "text", "text": text}]}


def askback_merge_v21(question: str, p: dict, prev: dict | None) -> tuple[str, str] | None:
    """바로 앞 답이 "설비를 알려 주세요"(확인 필요)였고 이번 글이 설비 이름 하나뿐이면 (앞 질문, 설비). 아니면 None — 설비를 다음 질문들에 계속 가져가지 않고, 되묻기 직후 한 번만 잇는다
    (이어받은 답은 상태가 '답변'이라 다음 글은 이 조건에 걸리지 않는다). 알람 번호·로트 번호를 되물은 답은 잇지 않는다."""
    if not prev or prev.get("status") != "확인 필요" or not ASKBACK_NEED_V21.search(prev.get("conclusion") or ""):
        return None
    pq = (prev.get("question") or "").strip()
    eqs = list(dict.fromkeys(p.get("equipment") or []))
    if not pq or len(eqs) != 1 or not equipment_only_v21(question, p):
        return None
    return pq, eqs[0]


def with_askback_note_v21(a: dict, prev_question: str, eq: str) -> dict:
    """이어받아 답한 사실을 답 끝에 한 줄 밝힌다 (정상 답·안내일 때만 — 앞 질문을 설비와 합쳐 다시 풀었다는 것을 숨기지 않는다)."""
    if not isinstance(a, dict) or a.get("status") not in ("답변", "안내"):
        return a
    pq = prev_question if len(prev_question) <= 40 else prev_question[:40] + "…"
    note = f"앞서 물으신 '{pq}'을 {eq} 기준으로 답했어요."
    a["conclusion"] = f"{a.get('conclusion') or ''} {note}".strip()
    if isinstance(a.get("blocks"), list):
        a["blocks"] = list(a["blocks"]) + [{"kind": "text", "text": note}]
    return a


def unread_note_v21(question: str) -> str | None:
    """규칙 길 답이 읽지 못한 조각 중 알려진 못 하는 일(센서·정비현황·브리핑)이 질문에 보이면 그 이름을 든 한 줄. 목록 밖의 말은 보지 않는다."""
    names = [label for rx, label in UNREAD_V21 if rx.search(question)]
    return UNREAD_NOTE_V21.format(names="·".join(names)) if names else None


def period_notes_v21(question: str, p: dict, ops_texts: list[str]) -> list[str]:
    """기간 안내. ① 날짜를 정하지 않은 지표(OEE 등) 질문은 9월 한 달 값임을 ② 하루·며칠 값과 MTTR·MTBF(30일 고정)가 한 줄이면 기간 차이를 밝힌다 (MTTR이 보이지 않는 역할에는 붙이지 않는다)."""
    if "kpi" not in p["intents"] or not p["equipment"] or not any("OEE" in x for x in ops_texts):
        return []
    if p["start"] is None:
        return [] if (KPI_30D_ONLY_V21.search(question) and not KPI_DATED_WORDS_V21.search(question)) else [NO_DATE_NOTE_V21]
    full_month = p["start"] == date(2026, 9, 1) and p["end"] == date(2026, 9, 30)
    if not full_month and any("MTTR" in x for x in ops_texts):
        return [MIXED_PERIOD_NOTE_V21.format(rng=_range_text(p))]
    return []


def pure_scope_v19(p: dict, s, question: str = "") -> str | None:
    """이 질문이 순수 외부 LLM 길로 가나 — 가는 까닭 글, 아니면 None. (권한·화면 설명·위험한 부탁·불량 원인·이어 묻기는 이 함수보다 앞에서 이미 처리됐다.)
    PURE_KEEP_SIGNALS=0(기본): 알람 번호·날짜·설비·운영 낱말 신호가 있어도 전부 순수 길.
    PURE_KEEP_SIGNALS=1: 규칙이 그 신호를 하나라도 찾은 질문은 기존 길(알람 카드·운영 조회) 그대로, 하나도 못 찾은 질문만 순수 길. (예외: PURE_SAFETY=1이고 신호가 설비 이름뿐인 안전 질문은 문서 질문이라 순수 길 — 안전망을 거친다.)"""
    if not PURE.enabled(s):
        return None
    if not s.pure_keep_signals:
        return "신호 끔(PURE_KEEP_SIGNALS=0) — 알람 번호·날짜·설비·운영 낱말 길을 거치지 않고 순수 길로"
    if PURE.has_signals(p):
        only_equipment = bool(p.get("equipment")) and not (p.get("alarms") or p.get("intents") or p.get("start") or p.get("lot") or p.get("order"))
        if s.pure_safety and question and only_equipment:
            if equipment_only_v21(question, p):   # "VF2-01)"·"1호기"·"2호기요": 설비 이름뿐인 글 — Claude를 부르지 않고 규칙이 안내한다 (_answer, 2026-10-20)
                return None
            if PURE.is_safety(question):   # "VF2-01 차단 지점"·"SAW-01 정비 전에 어디를 차단해?": 운영 조회가 아니라 안전 문서 질문
                return "신호가 설비 이름뿐인 안전 질문 — 문서 질문으로 보고 순수 길로 (PURE_SAFETY=1)"
            return EQUIP_DOC_WHY_V21   # "VF2-01 정비 상태는?"·"2호기 정비 상태는?": 설비 이름에 다른 말이 붙었고 안전 낱말은 없다 — 문서 질문, 안전망은 켜지 않는다
        if s.pure_rule and question and PURE.rule_question(question, p):   # "소모품 재고는 누가 관리해?"·"홀드 걸린 로트도 내보낼 수 있어?": 운영 낱말뿐인 규칙 질문은 문서 길로 (문서에 없으면 아래에서 되돌린다)
            return PURE.RULE_WHY
        if getattr(s, "pure_rule_wide", False) and question and PURE.rule_question_wide(question, p):   # PURE_RULE_WIDE=1: 규칙 낱말이 없는 규칙 질문("출하 로트 확정은 반장이 해?")도 문서 길로 — 조회 말투는 거른다 (문서에 없으면 아래에서 되돌린다)
            return PURE.RULE_WHY
        if s.pure_fault and question and PURE.fault_question(question, p):   # "툴 수명 다 됐다고 뜨는데 예비 날이 없어. 어떻게 해?"·"멈췄어. 내가 다시 돌려도 돼?": 운영 낱말뿐인 고장 대응 절차 질문은 문서 길로 (문서에 없으면 원래 기존 길로 되돌린다)
            return PURE.FAULT_WHY
        return None
    return "규칙이 알람 번호·설비·날짜·운영 낱말을 하나도 못 찾은 질문 (PURE_KEEP_SIGNALS=1)"


def _pure_layout_blocks_v20(sections: list[dict], written: bool) -> list[dict]:
    """묶음 목록 형식(PURE_LAYOUT=1)의 화면 블록: 묶음 순서대로 — title이 있으면 소제목(section), items가 있으면 머리(text, 비면 "") + 번호 목록(ops),
    items가 없고 text가 있으면 한 문장 본문(text). 전체에서 맨 처음 나오는 한 문장 본문 하나만 lead(근거 조각이 있으면 written)다. 원문 줄 블록은 부른 쪽이 뒤에 붙인다."""
    blocks: list[dict] = []
    lead_done = False
    for sec in sections:
        if sec["title"]:
            blocks.append({"kind": "section", "text": sec["title"]})
        if sec["items"]:
            blocks.append({"kind": "ops", "head": sec["text"], "items": list(sec["items"]), "source": None})
        elif sec["text"]:
            if lead_done:
                blocks.append({"kind": "text", "text": sec["text"]})
            else:
                blocks.append({"kind": "lead", "text": sec["text"], **({"written": True} if written else {})})
                lead_done = True
    return blocks


def _pure_answer_v19(question: str, p: dict, base: dict, s, memo: dict, prev: dict | None, why: str) -> dict:
    """순수 외부 LLM 길의 답. 외부 호출이 실패하면 ExternalLlmFailure가 그대로 올라가 앱 입구가 EXTERNAL_LLM_UNAVAILABLE로 끝낸다 (자동 대체 없음)."""
    k = s.pure_topk
    style = bool(s.pure_style)   # 말투 바꾸기 (PURE_STYLE=1): 지시문·스키마·응답 조립만 다르다. 끄면 아래 모든 줄이 지금과 같다
    layout = style and bool(s.pure_layout)   # 묶음 목록 형식 (PURE_LAYOUT=1, PURE_STYLE=1일 때만): 답을 sections로 받아 묶음마다 블록 하나씩. 끄면 PURE_STYLE=1의 지금 조립 그대로
    hits = PURE.context(question, k, s)         # PURE_EXPAND=1이면 상위 조각의 아래 절을 더한다 ("잠금 표지 순서" 결함 수정). 끄면 retrieve()와 같다
    chunks = [c for _, c in hits]
    safety_guard = bool(s.pure_safety) and PURE.is_safety(question) and why not in (PURE.RULE_WHY, PURE.FAULT_WHY)   # 안전 질문(규칙 질문 라우팅으로 온 "안전 재고" 같은 말은 제외 — 그 질문은 "문서에 없음"이면 기존 길로 되돌려야 한다): DOC-05를 통째로 받았고, 그래도 답이 없으면 "문서에 없다"고 하지 않는다 (PURE_SAFETY=1)
    mode = f"{s.pure_label} · {PURE_MODE_V19}"   # PURE_MODEL이 있으면 실제로 부른 모델 이름 (비면 llm_label과 같은 글자)
    traces: list[dict] = []
    retrieval = {"mode": "bm25", "dense_used": False, "reason": None, "pure": True, "top_k": k, "chunk_ids": [c.chunk_id for c in chunks]}
    if s.pure_expand:
        retrieval["expanded_ids"] = [c.chunk_id for sc, c in hits if sc == 0.0]       # 확장으로 더해진 조각 (끄면 이 칸이 없다 — 응답이 지금과 같다)
    if s.pure_safety:
        retrieval["safety_added_ids"] = [c.chunk_id for sc, c in hits if sc == PURE.SAFETY_SCORE]       # 안전 문서 통째로 더해진 조각 (끄면 이 칸이 없다)
    if getattr(s, "pure_faultdoc", False):
        retrieval["faultdoc_added_ids"] = [c.chunk_id for sc, c in hits if sc == PURE.FAULTDOC_SCORE]       # DOC-03 통째로 더해진 조각 (끄면 이 칸이 없다)
    base = {**base, "route": {"kind": "doc", "source": "순수 외부 LLM (분류 LLM 없음)"}}
    memo.update(ops_texts=[], procedure=is_procedure(question), future=False, doc_lines=[], doc_cites=[], doc_lead="", doc_written="")
    memo["pure_answer"] = True   # 이어 묻기 기록 표시: 이 답의 글은 Claude가 쓴 것이다 — 검색된 원문 줄(doc_lines)을 바꿔 쓰는 옛 이어 묻기는 답과 무관한 글이 된다 (2026-10-18)
    if SL.on():   # STEP_LOG: 순수 길로 간 까닭 · 분류 LLM 생략 · 찾은 조각 (읽기만 한다)
        SL.step("1 규칙 판정", 결과="순수 외부 LLM 길", 까닭=why, 앞답있음=prev is not None)
        SL.step("2 질문 분류", 사용=False, 까닭="순수 외부 LLM — 분류 LLM을 부르지 않음")
        SL.step("3 찾기", 길="순수 외부 LLM", 질문=question, 방식="낱말 검색(BM25) — 원래 질문 그대로, 문턱·문지기·순위 바꾸기 없음", 요청조각수=k,
                조각수=len(chunks), 상위=[{**_sl_chunk(c), "점수": round(sc, 2), "글자수": len(c.text), **({"확장으로 더해짐": True} if s.pure_expand and sc == 0.0 else {}), **({"안전 문서 통째로 더해짐": True} if sc == PURE.SAFETY_SCORE else {})} for sc, c in hits])
    if not chunks:   # 찾은 조각이 하나도 없으면 Claude를 부르지 않는다 — 호출 0번이라 화면이 "외부 LLM 호출 없음"이라고 사실대로 밝힌다
        if safety_guard:   # ② 안전 질문은 검색이 비어도 "문서에 없다"고 하지 않는다
            return _pure_unsure_v19(question, hits, base, mode, retrieval, traces, style)
        if SL.on():
            SL.step("종료 사유", 결과="답 없음", 까닭="낱말 검색 결과가 없어 Claude를 부르지 않음")
        return {**base, "status": "문서에 없음", "mode": f"{mode} — 검색 결과가 없어 Claude를 부르지 않음", "retrieval": retrieval,
                "llm_trace": traces, "conclusion": PURE_NO_DOC_CHAT_V19 if style else PURE_NO_DOC_V19}
    fixed_keys = FB.select(question) if getattr(s, "fixed_block", False) else []   # FIXED_BLOCK: 이 질문에 맞는 고정 서식 (0~2개)
    got = PURE.ask(question, chunks, prev, s, ops_note=(why in (PURE.RULE_WHY, PURE.FAULT_WHY)), **({"fixed_note": FB.reference_note(fixed_keys)} if fixed_keys else {}))
    traces.append({"job": PURE.JOB, "used": True, "reason": None, "tries": 1, "ms": got["ms"]})
    if got["insufficient"] and s.pure_retry and not safety_guard and why not in (PURE.RULE_WHY, PURE.FAULT_WHY):   # PURE_RETRY=1: 첫 호출이 "조각에 답이 없다"고 했다 — 정답 조각이 상위 조각 밖(검색 9~50위)이라 못 본 것일 수 있어 더 넓게 한 번 다시 묻는다. 안전 질문·규칙 질문 경로는 제외
        wide_hits = PURE.context(question, s.pure_retry_topk, s)
        wide_chunks = [c for _, c in wide_hits]
        have = {c.chunk_id for c in chunks}
        if any(c.chunk_id not in have for c in wide_chunks):   # 넓혀도 새 조각이 없으면 다시 물을 이유가 없다
            ext = EXT.current()
            failed_before = len(ext.failures) if ext is not None else 0
            try:
                got2 = PURE.ask(question, wide_chunks, prev, s, retry_note=True, **({"fixed_note": FB.reference_note(fixed_keys)} if fixed_keys else {}))
            except EXT.ExternalLlmFailure:   # 재시도는 오류를 새로 만들지 않는다 — 첫 결과("문서에 없음")를 그대로 낸다 (실패 기록도 이 호출 몫만 지운다)
                got2 = None
                if ext is not None:
                    del ext.failures[failed_before:]
            traces.append({"job": PURE.JOB, "used": True, "reason": None if got2 else "넓게 다시 본 호출이 실패해 첫 결과를 씀", "tries": 1, "ms": got2["ms"] if got2 else 0, "retry": True})
            retrieval["retry"] = {"top_k": s.pure_retry_topk, "chunk_ids": [c.chunk_id for c in wide_chunks], "new": sum(1 for c in wide_chunks if c.chunk_id not in have), "failed": got2 is None}
            if SL.on():   # STEP_LOG: 첫 호출이 "답 없음"이라 넓게 다시 물은 것 (읽기만 한다)
                SL.step("넓게 다시 보기", 조각수=len(wide_chunks), 새조각수=retrieval["retry"]["new"], 실패=got2 is None, 충분하지않음=(got2["insufficient"] if got2 else None), ms=(got2["ms"] if got2 else None))
            if got2 is not None:
                got, hits, chunks = got2, wide_hits, wide_chunks   # 아래 인용 변환·조립은 넓힌 조각과 두 번째 답으로 한다
                mode = f"{mode} · 넓게 다시 봄 (조각 {len(chunks)}개)"
    cited, dropped = PURE.resolve_cites(got["cited_raw"], chunks)
    if SL.on():   # STEP_LOG: Claude가 낸 답·인용 번호·"문서에 없음" 판단, 그리고 번호 → 출처 변환 결과 (모델이 쓴 출처 글자는 쓰지 않고 버린다)
        SL.step("순수 호출 결과", 보낸글자수=got["sent_chars"], ms=got["ms"], 충분하지않음=got["insufficient"], 답=got["answer"], 받은인용=got["cited_raw"])
        SL.step("출처 변환", 변환=[c.cite for c in cited], 버린항목=dropped)
        if layout:   # STEP_LOG: 묶음 목록 형식 켬일 때만 — 받은 묶음 짜임 (읽기만 한다)
            secs = got["sections"]
            SL.step("순수 짜임", 말투바꾸기=True, 배치="묶음", 묶음수=len(secs), 소제목수=sum(1 for x in secs if x["title"]),
                    목록항목수=[len(x["items"]) for x in secs], 충분하지않음=got["insufficient"])
        elif style:   # STEP_LOG: 말투 바꾸기 켬일 때만 — 받은 짜임 (읽기만 한다. 끔이면 이 줄은 없다)
            SL.step("순수 짜임", 말투바꾸기=True, 항목수=len(got["points"]), 마무리있음=bool(got["closing"]), 머리글자수=len(got["opening"]), 충분하지않음=got["insufficient"])
    if got["insufficient"]:   # Claude가 "조각에 답이 없다"고 했다 — 지금 앱의 "문서에 없음" 응답 모양
        if safety_guard:   # ② Claude가 "조각에 답이 없다"고 해도 안전 질문은 "문서에 없다"고 하지 않는다 (Claude가 쓴 문장은 버린다)
            return _pure_unsure_v19(question, hits, base, mode, retrieval, traces, style)
        if not style:
            return {**base, "status": "문서에 없음", "mode": mode, "retrieval": retrieval, "llm_trace": traces, "conclusion": PURE_NO_DOC_V19}
        # 말투 바꾸기: 고정 문구 대신 Claude가 쓴 이유와 다음 방법(opening — 묶음 형식에서는 모든 묶음 text를 이은 글)을 보인다. 상태 "문서에 없음"·근거·블록 없음은 그대로. 원문 출처 표기는 여기서도 막는다(D-03)
        ins_text = got["answer"] if layout else got["opening"]
        if FORBIDDEN.search(ins_text):
            return {**base, "status": "확인 필요", "mode": mode, "retrieval": retrieval, "llm_trace": traces,
                    "conclusion": "확인 필요 — 답에 원문 출처 표기가 섞여 내보내지 않았습니다."}
        return {**base, "status": "문서에 없음", "mode": mode, "retrieval": retrieval, "llm_trace": traces, "conclusion": ins_text}
    evidence = [_cite(c) for c in cited]
    orig_lines: list[str] = []
    line_cites: list[dict] = []
    for c in cited:   # 근거 조각의 줄들 — 화면이 [원문 보기]로 접는다 (DOC_WRITE 새 글과 같은 응답 모양: lead.written + line.orig)
        for ln in plain_lines(c):
            orig_lines.append(ln)
            line_cites.append(_line_cite(c))
    memo.update(doc_lines=list(orig_lines), doc_cites=list(line_cites), doc_lead="", doc_written=got["answer"] if cited else "")   # doc_lead는 비운다: 검사를 안 지난 글을 "검사 지난 앞머리"로 이어 묻기가 다시 쓰지 않게
    if layout:   # 묶음 목록 형식: 묶음 순서대로 소제목(section) · 머리 + 번호 목록(ops) · 한 문장(text, 맨 처음 문단 하나만 lead) — 화면은 이미 이 칸들을 그린다
        blocks = _pure_layout_blocks_v20(got["sections"], bool(cited))
    elif style:   # 말투 바꾸기: 항목이 있으면 머리 + 번호 목록(ops), 없으면 본문 한 칸(lead), 마무리가 있으면 그 아래 본문(text) — 화면은 이미 이 칸들을 그린다
        blocks = ([{"kind": "ops", "head": got["opening"], "items": list(got["points"]), "source": None}] if got["points"]
                  else [{"kind": "lead", "text": got["opening"], **({"written": True} if cited else {})}])
        if got["closing"]:
            blocks.append({"kind": "text", "text": got["closing"]})
    else:
        blocks = [{"kind": "lead", "text": got["answer"], **({"written": True} if cited else {})}]
    blocks += [{**BL2.doc_line(x, cite), "orig": True} for x, cite in zip(orig_lines, line_cites)]
    safety = any(w in (question + " ".join(e["title"] + e["snippet"] for e in evidence)) for w in SAFETY_WORDS)
    caution = PURE_CAUTION_SAFETY_V19 if safety else (PURE_CAUTION_V19 if evidence else None)
    out = {**base, "status": "답변", "conclusion": got["answer"], "evidence": evidence, "caution": caution,
           "mode": mode if cited else f"{mode} · 근거 조각 번호 없음", "llm_trace": traces, "retrieval": retrieval, "blocks": blocks}
    if cited:
        out["written"] = True   # 화면 꼬리표 "AI가 문서를 보고 쓴 답 · 원문 아래" + 원문 줄 접기
    if fixed_keys:   # FIXED_BLOCK: 고정 서식을 프로그램이 그대로 붙인다. 풀이가 순서 전체를 묻는 질문에서 단계를 빠뜨리거나 없는 번호를 쓰면 풀이를 버리고 서식만 보인다
        bad = FB.check_answer(got["answer"], fixed_keys, FB.wants_full(question, fixed_keys))
        keep = [b for b in out["blocks"] if isinstance(b, dict) and b.get("orig")]   # 원문 줄(접어 두는 칸)은 그대로
        out["blocks"] = ([{"kind": "lead", "text": FB.FALLBACK_LEAD}] if bad else [b for b in out["blocks"] if not (isinstance(b, dict) and b.get("orig"))]) + FB.blocks(fixed_keys) + keep
        if bad:
            out["conclusion"] = FB.FALLBACK_LEAD
        out["fixed_block"] = {"keys": fixed_keys, "fallback": bad}
    blob = " ".join(str(v) for v in (out["conclusion"], out["steps"], out["evidence"], out["related"], out["caution"]))
    if FORBIDDEN.search(blob):   # 원문 출처가 새어 나가면 내보내지 않는다 (D-03) — 답 내용 검사가 아니라 저작권 차단
        return {**base, "status": "확인 필요", "mode": mode, "retrieval": retrieval, "llm_trace": traces,
                "conclusion": "확인 필요 — 답에 원문 출처 표기가 섞여 내보내지 않았습니다."}
    return out


def _pure_unsure_v19(question: str, hits: list, base: dict, mode: str, retrieval: dict, traces: list, style: bool) -> dict:
    """안전 질문의 "답 없음" (PURE_SAFETY=1): "문서에 없다" 대신 "자동으로 확인하지 못했어요 — 문서에 없다는 뜻은 아니다" + 가까운 DOC-05 절 후보.
    상태는 기존 "확인 필요"(chat_mapping에서 OK) — 백엔드·화면의 상태 값 목록을 늘리지 않는다. 끝 안전 문구는 그대로 붙인다."""
    cand = PURE.unsure_candidates(question, hits)
    head = PURE_UNSURE_CHAT_V19 if style else PURE_UNSURE_V19
    text = head + (" 가까운 절: " + ", ".join(f"DOC-05 §{c.section} {c.title}" for c in cand) + "." if cand else "")
    if FORBIDDEN.search(text):   # 절 제목에 원문 출처 표기가 섞이면 (D-03) 이름 없이 고정 문구만
        text = head
    if SL.on():
        SL.step("종료 사유", 결과="자동으로 확인하지 못함", 까닭="안전 질문 — 답이 없어도 \"문서에 없다\"고 하지 않음 (PURE_SAFETY=1)", 후보=[c.chunk_id for c in cand])
    return {**base, "status": "확인 필요", "mode": f"{mode} · 안전 질문 — 자동으로 확인하지 못함", "retrieval": retrieval, "llm_trace": traces,
            "conclusion": text, "evidence": [_cite(c) for c in cand], "caution": PURE_CAUTION_SAFETY_V19}


def _final_step_log(a: dict, memo: dict) -> dict:
    """STEP_LOG "12 최종" — 화면에 나간 것: 상태·꼬리표(mode)·보인 문서 줄(전문)·새로 쓴 답·출처·LLM 기록(llm_trace). 읽기만 한다."""
    tags = [a.get("mode")]
    if a.get("written"):
        tags.append("AI가 문서를 보고 쓴 답 · 원문 아래")
    if a.get("steps_easy"):
        tags.append("점검 순서를 쉬운 말로 · 원문 접음")
    fu = a.get("followup") or {}
    if fu.get("rewritten"):
        tags.append("AI가 다시 쓴 글 · 원문 아래")
    ext, think = EXT.current(), THINK.current()
    return {"단계": "12 최종", "status": a.get("status"), "mode": a.get("mode"), "꼬리표": [t for t in tags if t],
            "결론": SL.cut(a.get("conclusion") or "", 600),
            "줄": list(memo.get("doc_lines") or []), "새로쓴답": memo.get("doc_written") or None,
            "출처": [e.get("cite") for e in (a.get("evidence") or []) if isinstance(e, dict)],
            "점검순서수": len(a.get("steps") or []), "followup": fu or None, "llm_trace": a.get("llm_trace"),
            "외부호출": None if ext is None else {"호출수": ext.calls, "실패": [list(f) for f in ext.failures]},
            "생각호출": None if think is None else {"호출수": think.calls, "실패": think.failures}}


# ---------------------------------------------------------------- 채팅 알람 카드 해요체 다시 쓰기 (CARD_REWRITE=1, A2, 2026-10-18)
# 알람 번호가 있는 질문은 프로그램이 카드(설명 문장 + ★ 점검 순서)를 문서 그대로 조립해 Claude를 거치지 않아 말투가 다른 답과 달랐다. 채팅에서만 Claude가 해요체로 다시 쓴다.
# 안전 때문에 문장 단위로 검사한다: jobs.simplify(plain)가 숫자(값 기준)·영문 이름·[가상] 꼬리표·조건 말 개수·허락/지시 문구·길이를 보고, jobs.faith가 뜻이 같은지 따로 판정한다.
# 하나라도 걸리거나 시간이 부족하면 원문 카드 그대로(fail closed). 운영 데이터 줄·주의 문구·출처는 프로그램이 붙이는 칸이라 건드리지 않는다.
CARD_STEP_HEAD = re.compile(r"^(★?\d+ \([^)]*\) )")     # "★1 (작업자) " — 번호·역할 표시는 구조라 다시 쓰지 않는다
CARD_REWRITE_MAX_CHARS = 3000


def _rewrite_alarm_card(a: dict, memo: dict) -> dict:
    card = (memo.get("alarm_card") or "").strip()
    steps = a.get("steps") or []
    if a.get("status") != "답변" or not card or not steps or not all(isinstance(x, str) for x in steps) or card not in (a.get("conclusion") or ""):
        return a
    heads, bodies = [], []
    for st in steps:
        m = CARD_STEP_HEAD.match(st)
        heads.append(m.group(1) if m else "")
        bodies.append(st[len(m.group(1)):] if m else st)
    segs = [card] + bodies
    if len(" ".join(segs)) > CARD_REWRITE_MAX_CHARS:
        return {**a, "card_rewrite": {"applied": False, "reason": "카드가 너무 김"}}
    new, tr = jobs.simplify(segs, "plain")
    reason = tr.get("reason") if new is None else None
    if new is not None:
        ok, ftr = jobs.faith(segs, new)
        if not ok:
            new, reason = None, "뜻 판정: " + str(ftr.get("reason"))
    if new is None:
        return {**a, "card_rewrite": {"applied": False, "reason": reason or "다시 쓰지 못함"}}
    out = {**a, "steps": [h + n for h, n in zip(heads, new[1:])], "conclusion": a["conclusion"].replace(card, new[0], 1),
           "card_rewrite": {"applied": True, "reason": None}}
    if isinstance(a.get("blocks"), list):
        out["blocks"] = [({**b, "text": b["text"].replace(card, new[0])} if isinstance(b, dict) and isinstance(b.get("text"), str) and card in b["text"] else b) for b in a["blocks"]]
    memo["alarm_card"] = new[0]   # 이어 묻기 "짧게"가 같은 카드 문장을 보이게 (answer()가 이 기록으로 앞 답 기록을 만든다)
    return out


# ---------------------------------------------------------------- 화면 알람 이어받기 (CTX_NARROW=1, 2026-10-18)
# 화면이 직전 답의 알람 번호를 alarm_key로 보내 주면, "원인은?"처럼 **자기 대상이 없는** 질문만 그 알람으로 푼다. 예전 규칙은 "원인·점검·먼저·안전·뭐부터" 낱말만 보고 묶어서
# "안전하게 자물쇠 제거 어떻게 해?"까지 직전 알람 카드로 답할 수 있었다. 여기서는 질문의 한글 낱말이 **모두** 알람 일반 낱말(CTX_GENERIC)과 조사·어미 조각(CTX_PIECES)으로 쪼개질 때만
# 대상이 없는 질문으로 본다 — 쪼개지지 않는 내용 낱말(자물쇠·제거·워밍업 …)이 하나라도 있으면 자기 대상이 있는 질문이다 (그래서 틀리게 이어받는 쪽보다 놓치는 쪽으로 틀린다).
# 낱말 사이를 띄우지 않은 질문("원인이뭐야")도 쪼개 본다. "아까·전에·어제" 같은 과거 지시어는 어느 알람인지 불확실하므로 이어받지 않는다.
CTX_GENERIC = frozenset("""
알람 경보 알림 원인 이유 왜 점검 순서 먼저 우선 일단 바로 당장 그냥 뭐부터 어디부터 뭐 뭘 무엇 무슨 어디 누가 누구 누구한테 누구에게 언제 얼마나 얼마 어떻게 어떡해 어떻해 어쩌지 어째 어찌 어떤 어느 정도
조치 해결 해결책 대책 처리 대처 대응 방법 복구 재발 방지 재가동 가동 재시작 시작 리셋 심각도 심각 심각한 등급 위험 위험도 급해 급한 급함 안급함 급하 의미 뜻 설명 자세히 정확히
또 다시 계속 자꾸 반복 반복돼 반복되면 뜨면 뜨는 뜨나 뜨는지 뜨네 뜬 떴어 떴는데 나면 나는 났어 났는데 나오면 나요 그다음 다음 그럼 그러면 그래서 이 상태 이대로 그대로 두면 두고 둬 둬도 놔도 놔둬 놔둬도
괜찮 괜찮아 괜찮나 괜찮은 괜찮을까 안전 안전해 안전한가 안전하나 라인 멈춰 멈춰도 멈추나 세워 세우 세워야 돌려 돌려도 쓰면 써 써도 가도 누르면 눌러 꺼도 꺼야 켜도
하나 하면 하지 하는 해야 봐야 봐 보면 확인 알려 알려줘 알려줘요 말해 말해줘 담당 담당자 작업자 반장 보전 보고 연락 부르면 불러 부르나 해줘 할까 할까요 하죠 걸려 걸리 걸리나 걸림 시간 오래 금방 곧
며칠 몇 번 몇번 빈도 자주 가끔 처음 이번 지금 방금 그거 그게 그건 그 이거 이게 이건 이것 저거 요거 풀려 풀리나 사라져 없어져 곳 일 이미 벌써 아직 시도 대로 정도 상관 문제 상황 경우 때 후 뒤 호출 부르 불러야 불러야돼 신고 요청 부탁 맡기 맡겨 손대 손봐 손보 고치 고쳐 고쳐야 고쳐야돼 수리 직접 스스로 혼자 같이 함께 눌러도 꺼 켜 복귀 복원 해제 풀어 풀고 무시 넘어가 넘기 놔두 방치 미루 기다려 기다리 지켜 지켜봐 이렇게 저렇게 그렇게 이런 저런 그런 이래 저래 그래 뭔데 뭔지 뭔가 뭐길래 왜이래 왜이렇게 혹시 아니면 아님 긴급 큰일 별일 문제없 내가 제가 우리 저희 나 저 너 사람 팀 보전팀 현장 관리자 어디서 어디로 어떻게든 하려면 하려고 할수 있어 있나 있는 있는지 없나 없는지 맞아 맞나 맞는지 아닌가 어려워 쉬워 간단 복잡 가능 불가능 필요 괜히 일부러 꼭 반드시 굳이 대충 모두 전부 전체 일부
""".split())
CTX_PIECES = frozenset("""
이 가 은 는 을 를 에 의 도 만 요 로 으로 야 이야 예요 에요 이에요 인 인가 인가요 인지 인데 인걸 이래 래 나 나요 까 까요 할 할까 할까요 될까 될까요 하나요 하죠 이죠 죠 네 네요 니 냐 어 아 지 게 라
해 해요 해도 해야 해야돼 해야되 돼 돼요 되 되요 되나 되나요 됩니까 합니까 하면 으면 면 려면 는데 한 하 하세요 세요 줘 줘요 주세요 좀 거 건 걸 거야 거예요 것 은데 던 었 았 했 한가 한가요 한지 부터 까지 임 거임 인거 인거야 건가 건가요 건데 인데요 잖아 잖아요 는지 은지 할지 될지 한데 던데 거든 거든요 이라고 라고 라는 라서 라서요 이라서 니까 니까요 으니까 어서 아서 해서 하고 하는데 하는지 해보 해봐 해봐도 봐도 돼도 되도 되죠 고 며 면서 다가 다고 다는 다면 라면 이라면 이면 거면 니다 습니다 습니까 입니다 입니까 합니다 됩니다 부터 까지 에서 한테 에게 처럼 보다 랑 이랑 와 과 이나 나 라도 이라도 마다
""".split())
CTX_PAST_REF = re.compile(r"아까|전에|어제|엊그제|저번|지난|예전|그때|이전")


CTX_WORDS = CTX_GENERIC | frozenset(w for w in FU_FILL_V9 if len(w) >= 2)   # 일반 낱말 조각 (한 글자짜리 이어 묻기 군더더기는 뺀다)


def _ctx_generic_token(tok: str, vocab) -> bool:
    """한글 낱말 하나가 vocab 조각으로 완전히 쪼개지고, 그 조각 가운데 일반 낱말(CTX_WORDS)이 하나 이상 있나 ("원인이뭐야" = 원인+이+뭐+야).
    조사·어미 한 글자 조각만으로 쪼개지는 내용 낱말("에어건" = 에+어+건)은 일반 낱말이 아니다. 조각 하나짜리 어미("거야"·"인가요")는 일반이다."""
    if tok in CTX_PIECES:
        return True
    n = len(tok)
    plain = [True] + [False] * n     # 조각만으로 도달
    word = [False] * (n + 1)         # 일반 낱말 조각을 하나 이상 쓰고 도달
    for i in range(n):
        if not (plain[i] or word[i]):
            continue
        for j in range(i + 1, min(n, i + 8) + 1):
            piece = tok[i:j]
            if piece in CTX_WORDS:
                word[j] = True
            elif piece in vocab:
                word[j] = word[j] or word[i]
                plain[j] = plain[j] or plain[i]
    return word[n]


def ctx_subjectless(question: str, p: dict) -> bool:
    """질문에 자기 대상이 없나 — 알람·설비·날짜·로트·운영 낱말 신호가 없고, 과거 지시어가 없고, 한글 낱말이 모두 알람 일반 낱말·조사·어미로 쪼개진다."""
    if PURE.has_signals(p) or CTX_PAST_REF.search(question):
        return False
    vocab = FU_FILL_V9 | CTX_GENERIC | CTX_PIECES
    for tok in re.findall(r"[가-힣]+|[0-9A-Za-z][0-9A-Za-z.\-]*", question.lower()):
        if tok[0].isascii():
            if not tok.isdigit():
                return False          # 영문·번호가 섞인 말(OEE, CB3, 5303.00 …)은 자기 대상이 있는 질문으로 본다
            continue
        if not _ctx_generic_token(tok, vocab):
            return False
    return True


def _ctx_use_v2(question: str, p: dict, s, memo: dict):
    """화면 알람(alarm_key)이 있고 질문에 알람 번호가 없을 때(parse_v2 판), 질문을 그 알람으로 풀지. CTX_NARROW=0이면 예전 규칙 그대로."""
    explicit = re.search(r"이 알람|이 경보|이거|이것", question)   # "이 알람·이거"는 화면 알람을 가리킨다 (예전부터)
    if not getattr(s, "ctx_narrow", False):
        return explicit or (not p["intents"] and re.search(r"뭐부터|먼저|점검|원인|안전", question))
    if explicit:
        return explicit
    if ctx_subjectless(question, p) and not followup_kind_v9(question, ""):   # "쉽게 설명해"·"요약해 줘" 같은 이어 묻기는 알람 이어받기가 아니다 (이어 묻기 길이 처리한다)
        memo["ctx_alarm_pending"] = True   # 실제로 알람이 정해졌을 때만 "N 알람 기준"을 밝힌다 (parse가 못 읽은 번호면 안 밝힘)
        return True
    return None


CARRY_STEPS = re.compile(r"점검|순서|뭐부터|먼저|누가|누구")
_CARRY_SECTION = {"cause": "가능한 원인 (사내 문서)", "steps": "점검 순서 (사내 문서)"}


def carry_focus(question: str) -> str | None:
    """대상 없는 이어받기에서 남길 덩어리. 원인·이유·왜·때문이 점검·누구보다 먼저다 ("원인부터").
    어느 쪽도 아니면 None — 알람 카드 전체를 그대로 둔다 (심각도·재가동처럼 한 덩어리로 못 자르는 질문)."""
    if cause_question(question):
        return "cause"
    if CARRY_STEPS.search(question):
        return "steps"
    return None


def _slice_blocks(blocks: list, title: str) -> list | None:
    """소제목 title부터 다음 소제목 전까지. 그 소제목이 없으면 None."""
    start = next((i for i, b in enumerate(blocks) if isinstance(b, dict) and b.get("kind") == "section" and b.get("text") == title), None)
    if start is None:
        return None
    kept = [blocks[start]]
    for b in blocks[start + 1:]:
        if isinstance(b, dict) and b.get("kind") == "section":
            break
        kept.append(b)
    if not any(isinstance(b, dict) and b.get("kind") in ("line", "text", "steps") for b in kept):
        return None
    return kept


def _narrow_carried_alarm(a: dict, focus: str, cause_lines: list | None = None) -> dict:
    """묻는 덩어리만 남긴다. 안내 줄은 부른 쪽이 이 다음에 붙인다. 주의·출처는 그대로 두고, 최근 횟수(related)는 뺀다.
    원인 질문은 원인 줄로 conclusion을 바꿔 BLOCKS_V3를 켜고 꺼도 결론이 같게 한다 (표시만 다른 계약)."""
    if a.get("status") != "답변":
        return a
    lines = [x for x in (cause_lines or []) if x] if focus == "cause" else []
    blocks = a.get("blocks") if isinstance(a.get("blocks"), list) else None
    kept = _slice_blocks(blocks, _CARRY_SECTION[focus]) if blocks else None
    if focus == "steps":
        if not kept:
            return a
        lines = [b["text"] for b in kept if b.get("kind") in ("line", "text") and b.get("text")]
        lines.extend(str(s) for s in (a.get("steps") or []) if s)
    elif not lines:
        return a
    out = {**a, "conclusion": " ".join(lines), "related": None}
    if kept:
        out["blocks"] = kept
    if focus == "cause":
        out["steps"] = []
        out.pop("steps_easy", None)
    if not a.get("current_data"):
        out["is_synthetic"] = False
        out["data_label"] = None
    return out


def _with_ctx_note(a: dict, code: str) -> dict:
    """질문에 대상이 없어 직전 알람으로 이어받았으면, 어느 알람 기준인지 답 맨 앞에 밝힌다 (정상 답일 때만)."""
    if not isinstance(a, dict) or a.get("status") != "답변":
        return a
    note = f"{code} 알람 기준으로 답해요."
    a["conclusion"] = f"{note} {a.get('conclusion') or ''}".strip()
    if isinstance(a.get("blocks"), list) and a["blocks"]:
        a["blocks"] = [{"kind": "lead", "text": note}] + list(a["blocks"])
    return a


def answer(question: str, role: str, context: dict | None = None, prev: dict | None = None) -> dict:
    """질문 하나에 답한다. 한 답 전체의 LLM 시간 예산을 하나로 센다 (2026-10-10 계획 3단계 B).
    FOLLOWUP=1이면 prev(서버가 기억한 바로 앞 답의 기록)를 받아 이어 묻기에 쓰고, 답에 내부 칸 `_followup`(이 답의 기록)을 붙인다 —
    부른 쪽(app.py·평가)이 빼서 기억에 두고, 화면에는 보내지 않는다 (2026-10-12).
    STEP_LOG=1이면 질문 하나의 단계별 기록을 한 줄 남기고 답에 `step_log_id`를 붙인다 (2026-10-15 — 읽기만 한다. 꺼져 있으면 아무 일도 하지 않는다)."""
    memo: dict = {}
    s0 = settings()
    box = SL.begin(s0.step_log_dir, question=question, role=role, provider="외부 Claude" if s0.llm_provider == "claude" else "로컬 Qwen",
                   context=context, has_prev=prev is not None) if s0.step_log else None
    try:
        with answer_deadline(s0.budget_s):
            a = _answer(question, role, context, prev=prev, memo=memo)
            focus = carry_focus(question) if memo.get("ctx_alarm_note") else None
            # 번호를 적은 원인 질문("2075 알람 원인은?")도 원인만 남긴다. 횟수까지 물은 질문(ops_texts)과 점검 순서를 같이 물은 질문은 카드 전체.
            if (focus is None and memo.get("alarm") and cause_question(question)
                    and not memo.get("ops_texts") and not CARRY_STEPS.search(question)):
                focus = "cause"
            # 원인만 남기면 설명·점검 순서를 화면에 안 보이므로 해요체 다시 쓰기를 건너뛴다 (원인 줄은 원문 그대로)
            if memo.get("alarm") and s0.card_rewrite and s0.job("write") and EXT.current() is not None and focus != "cause":
                a = _rewrite_alarm_card(a, memo)
            if focus:
                narrowed = _narrow_carried_alarm(a, focus, memo.get("cause_lines"))
                if narrowed is not a:
                    a = narrowed
                    memo["alarm_card"] = ""   # 화면에 안 보인 설명으로 다음 "짧게"가 돌아가지 않게
            if memo.get("ctx_alarm_note"):   # CTX_NARROW: 대상 없는 질문을 직전 알람으로 이어받았으면 어느 알람 기준인지 밝힌다
                a = _with_ctx_note(a, memo["ctx_alarm_note"])
        if settings().followup:
            a["_followup"] = followup_record(question, role, context, a, memo)
    except BaseException as e:
        if box is not None:   # 오류로 끝나도(재료 단계의 외부 호출 실패 등) 거기까지의 기록을 남긴다
            SL.end(box, error=e)
        raise
    if box is not None:
        try:
            final = _final_step_log(a, memo)
        except Exception:
            final = {"단계": "12 최종", "status": a.get("status"), "mode": a.get("mode")}
        if SL.end(box, final=final):   # 실제로 파일에 쓴 줄만 번호를 알린다 (상한·쓰기 실패면 응답에 step_log_id가 없다)
            a["step_log_id"] = box.log_id
    return a


def _answer(question: str, role: str, context: dict | None = None, prev: dict | None = None, memo: dict | None = None) -> dict:
    memo = {} if memo is None else memo
    try:
        require(role, "chat")
    except PermissionDenied:
        return {"status": "권한이 없습니다", "question": question, "conclusion": "권한이 없습니다", "steps": [], "evidence": [],
                "current_data": [], "related": None, "caution": None, "data_label": None, "is_synthetic": False, "mode": "규칙",
                "links": []}
    context = context or {}
    s = settings()
    p = parse(question)
    p["raw"] = question
    pure_drop = PURE.drops_signals(s)   # 순수 외부 LLM (PURE_EXTERNAL=1 + 외부 요청 + PURE_KEEP_SIGNALS=0): 알람·날짜·설비·운영 길을 끈다
    # 지금 화면의 알람 (SCR-10 [1]): 질문에 알람 번호도 운영 질문도 없으면 화면의 알람을 질문 배경으로 쓴다
    ctx_alarm = (context.get("alarm_key") or "").strip()
    if pure_drop:   # 순수 방식: 화면 알람 맥락으로 알람을 정하지 않는다 (이어 묻기 감지가 보는 ctx_alarm은 그대로 둔다)
        pass
    elif not p["alarms"] and ctx_alarm:
        if s.parse_v2:  # "이 알람·이거"는 운영 낱말이 있어도 화면 알람으로 먼저 푼다 (2026-10-10: "이 알람 몇 번 났어?" → 문서에 없음이던 버그)
            use_ctx = _ctx_use_v2(question, p, s, memo)
        else:
            use_ctx = not p["intents"] and re.search(r"이 알람|이거|뭐부터|먼저|점검|원인|안전", question)
        if use_ctx:
            p["alarms"] = parse(ctx_alarm)["alarms"][:1]
            if memo.pop("ctx_alarm_pending", False) and p["alarms"]:
                memo["ctx_alarm_note"] = p["alarms"][0]["code"]
    elif ctx_alarm and s.parse_v2 and s.parse_v3 and re.search(r"이 알람|이 경보|이거|이것", question):
        # "이거 뒤에 994, 992가 뜨면 …": 질문 속 다른 알람 번호가 있어도 주제는 화면 알람 (2026-10-10 2차, E004)
        ctx = parse(ctx_alarm)["alarms"][:1]
        if ctx and ctx[0]["code"] not in [a["code"] for a in p["alarms"]]:
            p["alarms"] = ctx + p["alarms"]
    # is_synthetic (API명세서_v1 공통 규칙·NFR-DATA-08, 2026-10-11 P1): 답에 가상 운영 데이터(조회 결과·관련 기록)가 들어가면 True.
    # 사내 문서만 쓴 답은 False (사내 문서는 따로 "가상 사내 문서"로 표시한다)
    base = {"question": question, "steps": [], "evidence": [], "current_data": [], "related": None, "caution": None,
            "data_label": None, "is_synthetic": False, "links": [],
            "context": {k: context.get(k) for k in ("screen", "equipment_id", "alarm_key") if context.get(k)},
            "parsed": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in p.items() if k != "raw"}}
    if SL.on():   # STEP_LOG 1단계: 규칙이 질문에서 찾은 것 (알람·설비·날짜·로트·작업지시·조회 의도), 절차 질문인가
        SL.step("1 규칙", 파싱=base["parsed"], 절차질문=is_procedure(question), 화면알람=ctx_alarm or None)

    if re.search(r"이 화면.*(설명|뭐)", question):
        help_text = SCREEN_HELP.get((context.get("screen") or "").upper())
        if SL.on():
            SL.step("1 규칙 판정", 결과="화면 설명 질문", 안내문구있음=bool(help_text))
        if help_text:
            return {**base, "status": "안내", "mode": "화면 안내 (프로그램 고정 문구)", "conclusion": help_text}
        return {**base, "status": "확인 필요", "mode": "규칙", "conclusion": "확인 필요 — 이 화면의 안내 문구가 아직 없습니다."}

    guard = human_only(question, general=not s.followup)   # 이어 묻기: 일반 요청 꼴 거절은 이어 묻기 감지 뒤로
    if guard:
        if SL.on():
            SL.step("1 규칙 판정", 결과="사람만 할 일·조작 요청 — 규칙이 거절·안내", status=guard.get("status"), mode=guard.get("mode"))
        return {**base, **guard}

    if DEFECT_CAUSE.search(question):
        if SL.on():
            SL.step("1 규칙 판정", 결과="불량 원인 안내 요청 — 근거 없음으로 답")
        return {**base, "status": "근거 없음", "mode": "규칙",
                "conclusion": "불량 원인 안내는 하지 않습니다. 근거가 되는 사내 문서가 없어 원인을 지어낼 위험이 큽니다 (FR-MNT-01-12). "
                              "검사 결과·로트 기록은 운영 조회로 볼 수 있습니다."}

    if s.followup:  # 이어 묻기 (2026-10-12): 화면 알람을 가리키는 "이거·이것·이 알람"은 지금처럼 화면 알람으로 푼다
        screen_this = bool(ctx_alarm) and re.search(r"이 알람|이 경보|이거|이것", question)
        prev_text = " ".join([prev["question"], prev["conclusion"]] + list(prev.get("doc_lines") or [])) if prev else ""
        kind = None if screen_this else (followup_kind_v9 if v9_on(s) else followup_kind_v8 if v8_on(s) else followup_kind)(question, prev_text)
        if SL.on():   # STEP_LOG 1단계: 앞 답을 가리키는 질문인가 (종류가 없으면 새 질문)
            SL.step("1 규칙 판정", 이어묻기종류=kind, 화면알람지시=bool(screen_this), 앞답있음=prev is not None)
        if kind:
            return _followup_answer(kind, role, prev, base, s, memo)
        guard = human_only(question)   # 이어 묻기가 아니면 일반 요청 꼴 거절을 지금 한다
        if guard:
            if SL.on():
                SL.step("1 규칙 판정", 결과="사람만 할 일·조작 요청 — 규칙이 거절·안내", status=guard.get("status"), mode=guard.get("mode"))
            return {**base, **guard}

    # 순수 외부 LLM 연결 (PURE_EXTERNAL, 2026-10-15): 위 단계(권한·화면 설명·위험한 부탁 거절·불량 원인·이어 묻기)에서 걸러지지 않은 질문은
    # 알람 카드·운영 조회·LLM 질문 분류를 거치지 않고 "낱말 검색 상위 조각 + 질문 → 외부 Claude 1번 → 답 그대로"로 답한다.
    if s.followup and not pure_drop:   # 설비 이름뿐인 글 (2026-10-20): 앞 답이 "설비를 알려 주세요"면 앞 질문과 이어 답한다
        merged = askback_merge_v21(question, p, prev)
        if merged:
            if SL.on():
                SL.step("1 규칙 판정", 결과="되묻기 답 이어받기 — 앞 질문 + 설비로 다시 풀어 답함", 앞질문=merged[0], 설비=merged[1])
            new_q = f"{merged[0]} {merged[1]}"
            memo["record_question"] = new_q
            return with_askback_note_v21({**_answer(new_q, role, context, prev=None, memo=memo), "question": question}, merged[0], merged[1])
    if not pure_drop and equipment_only_v21(question, p):   # 아니면 무엇을 볼지 안내한다 (안전 안내도, 엉뚱한 문서 줄도 아니다)
        if SL.on():
            SL.step("1 규칙 판정", 결과="설비 이름뿐인 글 — 규칙이 안내 (Claude 호출 없음)", 설비=p["equipment"])
        return equipment_only_answer_v21(base, p)
    pure_why = pure_scope_v19(p, s, question)
    if pure_why:
        memo_before = dict(memo)
        rule_route = pure_why in (PURE.RULE_WHY, PURE.FAULT_WHY)   # 규칙 질문·고장 대응 질문: 문서에 없음/호출 실패면 원래 기존 길로 되돌린다
        ext = EXT.current()
        failed_before = len(ext.failures) if ext is not None else 0
        try:
            out = _pure_answer_v19(question, p, base, s, memo, prev, pure_why)
        except EXT.ExternalLlmFailure:
            if not rule_route:
                raise
            out = None   # PURE_RULE: 규칙 질문일 수도 있다고 추측해 보낸 문서 길의 Claude 호출이 실패했다 — 원래 기존 길이 답하게 한다 (실패 기록도 이 호출 몫만 지운다)
            if ext is not None:
                del ext.failures[failed_before:]
        if out is not None and not (rule_route and out.get("status") == "문서에 없음"):
            return out
        # PURE_RULE: 규칙 질문으로 보고 문서 길로 보냈는데 문서에 답이 없다 → 진짜 운영 조회였을 수 있으니 원래 기존 길로 이어서 처리한다 (늘어나는 것은 Claude 호출 1회뿐)
        memo.clear()
        memo.update(memo_before)
        if SL.on():
            SL.step("1 규칙 판정", 결과="규칙 질문으로 문서 길에 보냈으나 문서에 없음 — 원래 기존 길로 되돌림 (PURE_RULE=1)")

    traces: list[dict] = []
    retrieval = None
    parts, steps, evidence = [], [], []
    # 질문대로 답하기 1단계: 알람 번호가 있어도 "지난 두 번 조치"만 물었으면 기본 카드(설명·점검 순서·횟수 줄)를 내지 않고 작업기록만 답한다.
    # 카드가 묻는 말(뜻·점검 순서·원인 …)이 같이 있으면 지금처럼 카드도 낸다 (카드 전체를 없애는 일은 2·3단계)
    skip_card = bool(p["alarms"]) and p.get("past_n") is not None and not CARD_ASK_V22.search(question)
    if skip_card and SL.on():
        SL.step("1 규칙 판정", 결과="지난 조치만 묻는 알람 질문 — 알람 카드 없이 작업기록만 답함", 건수=p["past_n"])
    for a in (p["alarms"][:1] if not skip_card else []):  # 알람 답(의미·점검 순서)은 LLM에 보내지 않는다 — 사내 문서 그대로
        got = alarm_doc_answer(a, en=flow_on(s))   # 8차 FLOW_V9: 카드 이름에 영문명
        if got:
            c, steps, evidence = got
            parts.append(c)
            if SL.on():   # STEP_LOG: 알람 번호 정확 일치(DOC-02) → 알람 카드 (설명·점검 순서는 LLM에 보내지 않는다)
                SL.step("알람 카드", 알람=a["code"], 점검순서수=len(steps), 출처=[e.get("cite") for e in evidence])
            memo["alarm"] = True   # 이어 묻기: 알람 설명·점검 순서는 바꿔 쓰지 않는다
            memo["alarm_card"] = c   # 9차 B: 알람 답 "짧게"는 이 카드 문장 + 점검 순서 전부 (아래에서 기준값·토크 줄이 붙으면 다시 적음)
            if s.parse_v2 and s.parse_v3:  # 알람 질문이 묻는 세부 값이 문서에 없으면 답하지 않는다 (2026-10-10 2차, E026·E050·E082)
                texts = [ch.title + "\n" + ch.text for e in evidence for ch in load_corpus()
                         if ch.doc_id == e["doc_id"] and (ch.section == e["section"] or ch.section.startswith(e["section"] + "."))]
                v5 = v5_on(s)
                miss = alarm_detail_missing(question, texts + [c] + [str(x) for x in steps], v5=v5)
                if not miss and v5:  # 단위 값·용량 (S2, E3-065 "CB3 차단기 용량이 몇 암페어") — 같은 칸에 기준 낱말과 같은 단위 값이 있어야 답한다
                    miss = alarm_unit_missing_v5(question, texts, [x["code"] for x in p["alarms"]])
                if not miss and v8_on(s):  # 7차 A1: 전화번호·가격·시각도 (E6-091)
                    miss = alarm_type_missing_v8(question, texts + [c] + [str(x) for x in steps])
                if miss:
                    if SL.on():
                        SL.step("6 코드 검사", 길="알람 카드", 결과="문서에 없음", 까닭="질문이 묻는 세부 값이 알람 문서에 없음", 값=list(miss))
                    eun = josa_v8(miss[0], "은", "는") if v8_on(s) else "은(는)"
                    return {**base, "status": "문서에 없음", "mode": "규칙", "evidence": evidence, "llm_trace": traces,
                            "conclusion": f"문서에 없음 — 질문하신 {(miss[1] + ' ') if miss[1] else ''}{miss[0]}{eun} 사내 문서에 없습니다. "
                                          f"참고로 알람 {a['code']} 설명: {c}"}
                # 알람이 뜨는(다시 켜는) 기준값: 그 알람 문서 한 조각에 같은 단위 값과 트립·복귀 표현이 붙어 있을 때만 답한다.
                # 없으면 카드는 참고로만 보이고 "문서에 없음" (규칙 2.2: 근거 없는 임계값을 만들지 않는다. 2026-10-10 3차 f, E2-067)
                th = alarm_threshold_v4(question, texts) if s.parse_v4 else None
                if th and not th[0]:
                    if SL.on():
                        SL.step("6 코드 검사", 길="알람 카드", 결과="문서에 없음", 까닭="알람 기준값이 문서에 없음", 값=th[1])
                    return {**base, "status": "문서에 없음", "mode": "규칙", "evidence": evidence, "llm_trace": traces,
                            "conclusion": f"문서에 없음 — 알람 {a['code']}의 {th[1]} 기준값은 사내 문서에 없습니다. "
                                          f"참고로 알람 {a['code']} 설명: {c}"}
                if th:
                    seg = _clean(th[2]).lstrip("- ").strip()
                    if seg and seg not in c:
                        parts[-1] = c = c + f" 문서의 {th[1]} 값: {seg}"
                        memo["alarm_card"] = c
                # 5차 L5: 조임 값(토크)을 물으면 그 알람 문서 칸의 토크 값 줄을 붙인다. 없으면 그 세부는 문서에 없음 (E4-038)
                tq = alarm_torque_v6(question, texts) if v6_on(s) else None
                if tq and not tq[0]:
                    if SL.on():
                        SL.step("6 코드 검사", 길="알람 카드", 결과="문서에 없음", 까닭="조임 값(토크)이 문서에 없음")
                    return {**base, "status": "문서에 없음", "mode": "규칙", "evidence": evidence, "llm_trace": traces,
                            "conclusion": f"문서에 없음 — 알람 {a['code']}의 조임 값(토크)은 사내 문서에 없습니다. "
                                          f"참고로 알람 {a['code']} 설명: {c}"}
                if tq:
                    seg = _clean(tq[1]).lstrip("- ").strip()
                    if seg and seg not in c:
                        parts[-1] = c = c + f" 문서의 조임 값: {seg}"
                        memo["alarm_card"] = c
            if cause_question(question):   # 원인을 묻는 알람 질문: DOC-03 그 알람 절의 원인 표를 원문 그대로 카드 뒤에 (parts[-1]이 카드라는 위 가정이 끝난 뒤에 붙인다)
                cl = doc03_causes((alarm_codes().get(a["code"]) or {}).get("doc03_section") or "")
                if cl:
                    parts.append(CAUSE_HEAD + " / ".join(cl))
                    memo["cause_lines"] = cl
                    memo["cause_cite"] = next((e for e in evidence if e.get("doc_id") == "DOC-03"), None)
    if steps and v8_on(s) and s.safe_write_card and s.job("write"):   # 안전 영역 새로쓰기 1단계 (2026-10-14): 점검 순서를 쉬운 말로 1:1 대체 표시
        memo["steps_easy"] = safe_steps_easy_v15(steps, traces)
        if SL.on():   # STEP_LOG 안전 새로쓰기 1단계: 점검 순서를 쉬운 말로 1:1 다시 쓰기 시도 (traces[-1] = 그 시도의 기록, 거부 까닭은 rejected)
            SL.step("안전 새로쓰기", 대상="알람 점검 순서", 새글있음=bool(memo["steps_easy"]), 시도=traces[-1] if traces else None)
    # 질문 분류 (ROUTE_POLICY): llm_*면 LLM이 정해진 메뉴 안에서 주 분류, 규칙은 힌트 (계획 3단계 C)
    route = None
    if use_llm_route(question, p, s) and not PURE.enabled(s):   # 순수 방식에서는 분류 LLM(route)을 부르지 않는다 — PURE_KEEP_SIGNALS=1의 신호 있는 질문은 규칙 분류로(아래 else 길)
        route = decide_route(question, p, s)
        if route.trace:
            traces.append(route.trace)
        if v9_on(s) and route.kind == "action" and list_request_v9(question):
            # 8차: "… 리스트 줘"(조작·상태 낱말 없음)를 LLM이 조작 요청으로 봐도 정보 질문으로 (E6-043). 규칙이 찾은 조회가 있으면 그것을 쓴다
            route.kind, route.intents = ("ops", list(p["intents"])) if p["intents"] else ("doc", [])
        if s.parse_v2 and s.parse_v3 and s.parse_v4 and route.kind in ("ops", "mixed") and HYPO_V4.search(question) \
                and not (p["lot"] or p["order"] or p["start"]):
            # 가정 질문("36개짜리 로트면 … 몇 개")은 운영 기록이 아니라 문서의 기준을 묻는다 → 문서 Route로 2차 문지기까지 (2026-10-10 3차 g)
            route.kind, route.intents = "doc", []
        if v5_on(s) and route.kind in ("ops", "mixed") and "work_orders" in route.intents and WO_NOT_V5.search(question):
            # "작업지시서 대신 뭘 남겨"는 작업지시 조회가 아니다 — LLM 분류 뒤에도 같은 보정 (4차 L2, E3-004)
            route.intents = [i for i in route.intents if i != "work_orders"]
            if not route.intents:
                route.kind = "doc"
        p = route.apply(p)
        base = {**base, "route": {"kind": route.kind, "source": route.source},
                "parsed": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in p.items() if k != "raw"}}
        if SL.on():   # STEP_LOG 2단계: LLM(또는 실패 때 규칙)이 정한 질문 종류·조회 의도·설비·검색어 — 호출은 trace(작업·성공 여부·까닭·시간)
            SL.step("2 질문 분류", 사용=True, kind=route.kind, intents=route.intents, equipment=route.equipment, 검색어=route.queries,
                    문서쪽질문=route.doc_question or None, 출처=route.source, 호출=route.trace)
        doc_like = route.kind in ("doc", "mixed", "none") or any(w in question for w in DOC_WORDS)
        if route.kind == "action" and s.parse_v2 and s.parse_v3 and not QWORD_V2.search(question) \
                and not (s.parse_v4 and leisure_request(question)):  # 업무 밖 추천 부탁은 거절 안내 대신 일반 흐름 (E2-090)
            return {**base, "status": "안내", "mode": "규칙 + 로컬 LLM 분류", "links": [], "llm_trace": traces,
                    "conclusion": "비서는 기록·상태·설비를 바꾸지 않습니다. 이 일은 권한이 있는 사람이 해당 화면이나 현장에서 합니다."}
    else:
        # 운영 질문에는 "왜·어떻게·기준" 같은 설명 요청이 있을 때만 문서 검색을 붙인다 (섞인 질문, FR-MNT-01-05)
        doc_like = not p["intents"] or any(w in question for w in DOC_WORDS)
        if SL.on():   # STEP_LOG 2단계: LLM 분류를 건너뛴 까닭 (규칙이 처리하는 질문이거나 분류 작업이 꺼져 있음)
            SL.step("2 질문 분류", 사용=False, 까닭=_route_skip_reason(question, p, s), 문서도찾기=bool(doc_like))
    v3 = s.parse_v2 and s.parse_v3
    v4 = v3 and s.parse_v4
    if v3 and doc_cue(question, s):  # 운영 질문에 붙은 설명 요청 → 문서도 찾는다 (2026-10-10 2차)
        doc_like = True
    if skip_card:   # 지난 조치만 물었으면 "어떻게 고쳤어"의 '어떻게'로 문서를 따로 찾아 붙이지 않는다
        doc_like = False
    future_note = None
    if v4 and p.get("future") and any(i in DATED_INTENTS_V4 for i in p["intents"]):
        # 기준 시각 뒤 날짜의 정지·실적·지표·알람 횟수는 기록이 없다 — 날짜를 버리고 한 달 전체로 답하지 않는다 (2026-10-10 3차 a)
        p = dict(p, intents=[i for i in p["intents"] if i not in DATED_INTENTS_V4])
        future_note = (f"확인 필요 — 물으신 날짜는 기준 시각({REFERENCE_AT[:10]} {REFERENCE_AT[11:16]}) 뒤라 "
                       "운영 기록이 없습니다 (가상 데이터 기간 2026-09-01 ~ 09-30).")
    elif v4 and v5_on(s) and p.get("outside") and any(i in DATED_INTENTS_V4 for i in p["intents"]):
        # 데이터 기간 밖의 달("8월에 몇 번?") — 0번이라 하거나 9월로 답하지 않는다 (4차 L4)
        p = dict(p, intents=[i for i in p["intents"] if i not in DATED_INTENTS_V4])
        future_note = (f"확인 필요 — 물으신 기간({p['outside']})은 가상 데이터 기간(2026-09-01 ~ 09-30) 밖이라 "
                       "운영 기록이 없습니다.")
    # 섞인 질문의 문서 쪽 글: 규칙으로 고른 문장(PARSE_V3, 질문 글 그대로) → LLM이 나눈 글(SPLIT_Q) → 원래 질문.
    # 규칙이 먼저인 까닭: LLM이 나눈 글이 운영 쪽 말을 그대로 품으면("MTTR는 얼마나 나왔고 몇 분 넘으면 주의로 봐?")
    # 문서 줄 고르기가 "답할 줄 없음"으로 거부한다 (2026-10-10 E024·E054). LLM 글은 규칙이 못 나눈 한 문장 질문에만 쓴다.
    rule_q = (doc_question_v5 if v5_on(s) else doc_question_v4 if v4 else doc_question_v3)(question) if v3 else question
    doc_q = (rule_q if rule_q != question else
             route.doc_question if (route is not None and s.split_q and route.doc_question) else question)
    alarm_doc = v3 and bool(evidence) and bool(p["alarms"]) and doc_cue(question, s)
    flow = flow_on(s)
    exclude = None
    if flow and v3 and bool(evidence) and bool(p["alarms"]):
        # 8차 ④: 알람 번호 + 설명 질문은 카드와 문서 검색을 함께 (운영 마디 밖의 마디, 또는 카드가 다루지 않는 주제 낱말이 있을 때).
        # 카드가 이미 보인 줄(점검 순서 행 등)은 문서 쪽 후보에서 뺀다
        plan = alarm_doc_plan_v9(question, p["alarms"][:1], " ".join(parts + [str(x) for x in steps]))
        alarm_doc = alarm_doc or plan is not None
        if alarm_doc:
            doc_like = True
            exclude = alarm_own_sections_v9(p["alarms"][:1])
            if plan and doc_q == question:   # 규칙이 이미 문서 쪽 마디를 골랐으면(doc_question_v5 — 운영 낱말을 붙여 줌) 그것을 쓴다
                doc_q = plan
    # 8차 ⑤: 섞인 질문의 문서 쪽 마디를 나눌 수 있으면 홀로 선 문서 질문으로 따로 답한다 (알람 질문은 ④가 맡는다)
    split_doc = flow and v3 and doc_like and bool(p["intents"]) and not p["alarms"] and doc_q != question
    if SL.on():   # STEP_LOG 3단계 준비: 문서를 찾을 질문 글과 찾을지 여부 (알람 카드가 보인 절은 후보에서 뺀다)
        SL.step("3 찾기 준비", 문서도찾기=bool(doc_like and (not evidence or alarm_doc)), 문서질문=(doc_q if doc_q != question else "(원래 질문 그대로)"),
                알람과문서함께=bool(alarm_doc), 섞인질문문서쪽따로=bool(split_doc),
                카드가보인절=sorted(f"{d} §{sec}" for d, sec in exclude) if exclude else None)
    tail: list[str] = []
    searched = False
    if doc_like and (not evidence or alarm_doc):
        searched = True
        # 규칙으로 문서 질문이 된 것과, 알람 카드에 설명 요청이 붙은 것("2075 보충할 때도 자물쇠 걸어야 돼? 어디어디 잠가?")은
        # 낱말 문지기에서 막혀도 2차 문지기로 다시 본다 (알람 카드는 그대로 앞에 둔다. 2026-10-10 E030)
        if split_doc:
            r_doc = doc_side_route_v9(doc_q, s, traces)
            dp = _doc_part(doc_q, r_doc, s, traces, rule_doc=True, memo=memo) if r_doc is not None else None
            if not dp:
                tail.append(MIXED_DOC_MISS_V9)
        else:
            dp = _doc_part(doc_q, route, s, traces, rule_doc=v3 and route is None and ((not p["intents"] and not p["alarms"]) or alarm_doc),
                           memo=memo, exclude=exclude)
        if dp:
            c, ev_doc, retrieval = dp
            evidence = evidence + [e for e in ev_doc if e["cite"] not in [x["cite"] for x in evidence]] if alarm_doc else ev_doc
            parts.append(c)
    # 예전 경로 (ROUTE_POLICY=rescue): 낱말 규칙이 알아듣지 못한 질문만 LLM 분류로 조회 종류를 구한다. 날짜는 코드가 정한다
    if route is None and s.route_policy == "rescue" and not parts and not p["intents"] and not p["alarms"] and s.job("route"):
        r, tr = jobs.route(question)
        traces.append(tr)
        if SL.on():   # STEP_LOG 2단계: 예전 경로(rescue) — 규칙이 아무것도 못 찾았을 때만 LLM이 조회 종류를 구한다
            SL.step("2 질문 분류", 사용=True, 경로="예전(rescue)", 결과=r, 호출=tr)
        if r:
            p = merge_route(p, r)
    needs: list[str] = []
    ops_entries: list[dict] = []
    p_rel = p
    split = alarm_ops_split_v10(question, p, s) if (flow10_on(s) and p["alarms"] and p["intents"] and not skip_card) else None
    if split:   # 9차 I: 섞인 알람 질문은 운영 조회를 마디마다 (알람 마디 → 다른 마디 순서)
        ops_texts, data, ops_defs = [], [], []
        for sub in split:
            t_, d_, f_ = ops_answer(role, sub, needs if s.parse_v2 else None, entries=ops_entries if blocks_on(s) else None)
            ops_texts += t_
            data += d_
            ops_defs += [f for f in f_ if f["cite"] not in [x["cite"] for x in ops_defs]]
        p_rel = split[0]   # 관련 줄(반복 알람·지난 조치)은 알람 마디의 해석으로
    else:
        ops_texts, data, ops_defs = (ops_answer(role, p, needs if s.parse_v2 else None, entries=ops_entries if blocks_on(s) else None)
                                     if p["intents"] else ([], [], []))
    if SL.on() and (p["intents"] or split):   # STEP_LOG: 운영 조회 — 프로그램이 부른 읽기 도구와 범위 (숫자는 코드가 계산, LLM은 문장만 다듬는다)
        SL.step("운영 조회", 의도=p["intents"], 마디별조회=bool(split), 필요한항목=sorted(set(needs)) or None,
                도구=[{k: d.get(k) for k in ("tool", "range", "as_of")} for d in data], 초안=SL.cut(" ".join(ops_texts), 300))
    if tail and not ops_texts:   # 운영 조회가 비었으면 "문서 쪽 못 찾음" 안내만 남기지 않는다 (아래 문서에 없음·확인 필요 길로)
        tail = []
    tail += period_notes_v21(question, p, ops_texts)   # 기간 안내 (2026-10-20): 날짜 없는 지표는 9월 한 달 값, 하루 값과 MTTR·MTBF(30일)가 한 줄이면 기간 차이
    if (parts or ops_texts) and (unread := unread_note_v21(question)):   # 못 읽은 조각 안내 (2026-10-20): 센서·정비현황·브리핑은 아직 이 채팅이 답하지 못한다
        tail.append(unread)
    # 이어 묻기 기록: 운영 답의 프로그램 초안 글(다듬기 전), 절차 질문인가, 날짜 확인 안내가 있나 (2026-10-12)
    memo.update(ops_texts=list(ops_texts), procedure=is_procedure(question), future=bool(future_note))
    if s.parse_v2 and not parts and not ops_texts and not searched and not evidence and not future_note:
        # 운영 조회가 비었으면 문서도 찾아본다 (PARSE_V2: 낱말이 운영으로 잘못 보낸 문서 질문을 놓치지 않게)
        dp = _doc_part(question, route, s, traces, memo=memo)
        if dp:
            c, evidence, retrieval = dp
            parts.append(c)
    if future_note and (parts or ops_texts):  # 다른 답(문서·날짜와 무관한 조회)이 있으면 함께 알린다
        parts.append(future_note)

    if not parts and not ops_texts:
        none_mode = none_mode_v10(traces, s)   # 9차 G: LLM을 불렀으면 꼬리표가 "규칙"이 아니다 (표시만)
        if SL.on():   # STEP_LOG: 문서도 운영 조회도 답을 만들지 못한 까닭
            SL.step("종료 사유", 결과="답 없음", 까닭=("기준 시각 뒤·기간 밖 날짜" if future_note else "운영 조회에 필요한 항목이 질문에 없음" if (s.parse_v2 and needs)
                                                  else "문서 찾기·운영 조회 모두 비어 있음"), 필요한항목=sorted(set(needs)) or None)
        if future_note:
            return {**base, "status": "확인 필요", "mode": none_mode, "llm_trace": traces, "conclusion": future_note}
        if s.parse_v2 and needs:  # 조회에 필요한 항목이 질문에 없으면 "문서에 없음" 대신 무엇이 필요한지 알린다
            return {**base, "status": "확인 필요", "mode": none_mode, "llm_trace": traces,
                    "conclusion": "확인 필요 — 운영 기록을 찾으려면 다음을 알려 주세요: " + ", ".join(dict.fromkeys(needs)) + "."}
        return {**base, "status": "문서에 없음", "mode": none_mode, "llm_trace": traces,
                "conclusion": "문서에 없음 — 사내 문서(DOC-01~07, 용어집)와 운영 조회에서 근거를 찾지 못해 답을 만들지 않았습니다."}

    safety = any(w in (question + " ".join(e["title"] + e["snippet"] for e in evidence) + " ".join(steps)) for w in SAFETY_WORDS)
    caution = ("근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, "
               "전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.") if safety else (
               "근거 안내이며 실행 지시가 아닙니다." if evidence else None)
    # 운영 답에 쓴 정의(정지 사유 그룹·필수 정지·손실식)의 사내 문서 출처를 붙인다. 주의 문구 판단에는 넣지 않는다
    evidence = evidence + [d for i, d in enumerate(ops_defs) if d["cite"] not in [e["cite"] for e in evidence + ops_defs[:i]]]
    facts = {"draft_conclusion": " ".join(parts + ops_texts + tail), "draft_related": None if skip_card else related_line(role, p_rel), "draft_caution": caution,
             "steps": steps, "evidence": evidence, "data": data}
    if ops_texts and s.job("write"):  # LLM 다듬기는 운영 문장에만. 문서·알람 부분은 그대로 앞에 둔다 (8차 꼬리 안내는 운영 글 뒤)
        f_ops, mode, trace = write_answer({**facts, "draft_conclusion": " ".join(ops_texts)}, jobs.PhraseAdapter(), budget_s=s.budget_s)
        fields = f_ops.model_copy(update={"conclusion": " ".join(parts + [f_ops.conclusion] + tail)})
    else:
        fields, mode, trace = write_answer(facts)
    traces.append(trace)
    used = [JOB_KO[t["job"]] for t in traces if t["used"]]
    if used:
        mode = f"{s.llm_label} {s.llm_model_name} ({', '.join(dict.fromkeys(used))}) + 프로그램 검사"
    elif v8_on(s) and mode == FallbackAdapter.name and s.llm_enabled:
        # 7차 A4: LLM이 켜져 있는데 일부러 보내지 않은 답(알람 카드·절차·안전 낱말 질문)에 "로컬 LLM 미연결"을 붙이지 않는다
        if any((t.get("reason") or "").startswith("LLM 오류") for t in traces):
            mode = f"기본 문장 ({s.llm_label} 응답 없음)"
        else:
            why = "알람 카드" if memo.get("alarm") else "절차" if is_procedure(question) else "사내 문서 원문"
            mode = f"규칙 ({why} 그대로 — LLM에 보내지 않음)"
    if retrieval and retrieval["dense_used"] and any(t["job"] == "select" and t["used"] for t in traces):
        mode += f" + 뜻으로 찾기 후보({s.embed_model})"
    ops_final = ((f_ops.conclusion if s.job("write") else " ".join(ops_texts)) if ops_texts else None)
    out = {**base, "status": "답변", "conclusion": fields.conclusion, "steps": steps, "evidence": evidence,
           "current_data": [{k: d[k] for k in ("tool", "range", "as_of", "label", "is_synthetic")} for d in data],
           "related": fields.related, "caution": fields.caution,
           "data_label": DATA_LABEL if data or fields.related else None, "is_synthetic": bool(data or fields.related),
           "mode": mode, "llm_trace": traces, "retrieval": retrieval,
           "blocks": (BL2.build(parts, ops_final, ops_texts, ops_entries, memo.get("doc_lines") or [], memo.get("doc_cites") or [],
                                fields.conclusion, tail, v3=blocks3_on(s),
                                card=memo.get("alarm_card") if memo.get("alarm") else None, steps=bool(steps),
                                written=memo.get("doc_written") or None, causes=memo.get("cause_lines"), cause_head=CAUSE_HEAD,
                                cause_cite=memo.get("cause_cite")) if blocks_on(s)
                      else answer_blocks(parts, ops_final, memo.get("doc_lines") or [], fields.conclusion, tail))}
    if memo.get("doc_written"):   # 10차 DOC_WRITE: 화면이 꼬리표 "AI가 문서를 보고 쓴 답"과 원문 줄 접기를 그린다
        out["written"] = True
    if memo.get("steps_easy"):   # 안전 영역 새로쓰기 1단계: 새 글을 먼저 보이고 steps(원문)는 [원문 보기]로 접는다 (steps와 같은 개수·순서)
        out["steps_easy"] = memo["steps_easy"]
    if not out["evidence"] and not data:  # 출처 없는 답은 내보내지 않는다 (FR-AST-COM-02, SCR-10 상태 표)
        return {**base, "status": "근거 없음", "mode": mode, "conclusion": "근거를 찾지 못했습니다."}
    blob = " ".join(str(v) for v in (out["conclusion"], out["steps"], out["evidence"], out["related"], out["caution"]))
    if FORBIDDEN.search(blob):  # 원문 출처가 새어 나가면 내보내지 않는다 (D-03)
        return {**base, "status": "확인 필요", "mode": mode, "conclusion": "확인 필요 — 답에 원문 출처 표기가 섞여 내보내지 않았습니다."}
    return out
