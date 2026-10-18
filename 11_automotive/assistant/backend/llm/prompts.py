"""LLM 지시문 (한국어). 모델은 문장만 다루고 숫자·순서·출처·안전 문구는 프로그램이 정한다 (규칙 2.3·2.5).

여기 글에는 운영 데이터·사내 문서가 들어가지만 로컬 서버(127.0.0.1)로만 보낸다 (NFR-SEC-08).
"""
from __future__ import annotations

import json

COMMON = ("너는 자동차 부품 가공 공장(OP-30 Haas VF-2) 운영 비서의 문장 담당이다. "
          "설비를 움직이거나 승인·판단하지 않는다. 원인·허락·지시를 새로 만들지 않는다. "
          "출처·문서 번호·§ 표시는 쓰지 않는다(프로그램이 붙인다). JSON 칸으로만 답한다.")


def phrase(draft: str, feedback: str | None = None) -> list[dict]:
    rules = ("아래 '기본 문장'은 프로그램이 계산해 만든 운영 조회 결과다. 현장 사람이 읽기 쉬운 한국어로 다듬어 conclusion 칸에 쓴다.\n"
             "- 숫자·단위·날짜·설비 이름·기록 번호는 하나도 바꾸거나 빼거나 새로 더하지 않는다. 숫자는 아라비아 숫자 그대로 쓴다.\n"
             "- '(추정)', '[가상]', '잠정' 같은 꼬리표와 계산식을 지우지 않는다.\n"
             "- 항목을 빼거나 순서를 바꾸지 않는다. 길게 늘이지 않는다.")
    user = f"기본 문장:\n{draft}"
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}. 이 점을 고쳐 다시 쓴다."
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": user}]


def select(question: str, blocks: list[tuple[str, list[tuple[str, str]]]], feedback: str | None = None) -> list[dict]:
    """blocks = [(조각 머리 "문서 이름 DOC-0n §절 제목", [(줄 번호, 줄 글), ...]), ...]"""
    rules = ("질문에 답하는 줄을 아래 사내 문서 후보 줄에서 고른다.\n"
             "- line_ids에는 후보 줄 번호(L1, L2 …)만 넣는다. 질문에 직접 답하는 줄만, 많아야 6개.\n"
             "- 후보 줄에 답이 없으면 answerable=false, line_ids는 빈 목록.\n"
             "- lead는 고른 줄의 내용을 160자 안의 한 문장으로 요약한다. 고른 줄에 없는 숫자·사실·허락·지시는 쓰지 않는다. "
             "숫자는 고른 줄에 있는 그대로 쓴다.")
    body = "\n\n".join(head + "\n" + "\n".join(f"{i}: {t}" for i, t in lines) for head, lines in blocks)
    user = f"질문: {question}\n\n후보 줄:\n{body}"
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}."
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": user}]


def route(question: str) -> list[dict]:
    rules = ("질문을 보고 어떤 조회가 필요한지 분류한다. 답을 쓰지 않고 분류만 한다.\n"
             "- kind: doc(사내 문서의 규칙·절차·정의), ops(운영 기록 조회), mixed(둘 다), none(공장 업무와 무관하거나 모름)\n"
             "- intents (ops·mixed일 때): stops=설비가 멈춘·선 기록, production=생산 실적·개수, inventory=재고·소모품, "
             "tool_life=공구 수명, kpi=OEE·가동률·성능·양품률·MTTR(평균 수리 시간)·MTBF, lots=로트, work_orders=정비 작업지시, "
             "pm_due=예방 정비 기한, work_records=작업기록·지난 조치, alarm_count=알람이 몇 번 났나, equipment_status=지금 설비 상태\n"
             "- equipment: SAW-01(절단), MIL-01(황삭), VF2-01(1호기), VF2-02(2호기), WSH-01(세척), CMM-01(측정). 말하지 않았으면 빈 목록.\n"
             "- period: today=오늘, yesterday=어제, last_shift=지난 교대, recent_7=최근 일주일, recent_30=이번 달·최근 30일, none=말하지 않음. "
             "날짜를 직접 쓰지 않는다.\n"
             "- shift: D=주간·낮, N=야간·밤, none=말하지 않음\n"
             "- 확실하지 않으면 kind=none.")
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": f"질문: {question}"}]


# ---------------------------------------------------------------- 2026-10-10 계획 3·4단계
def route_v2(question: str, hint: dict, examples: list[dict]) -> list[dict]:
    """분류 v2 (ROUTE_POLICY=llm_primary·llm_guarded). 낱말 규칙의 결과는 힌트로만 준다. '모르면 none' 문구는 없다."""
    rules = ("질문을 보고 어떤 조회가 필요한지 분류한다. 답을 쓰지 않고 분류만 한다.\n"
             "- kind: doc = 사내 문서에 적혀 있을 규칙·절차·정의·기준·담당자·주기·정해 둔 값을 묻는다 / "
             "ops = 운영 기록(실제로 멈춘 횟수, 생산 실적, 재고, 공구 수명, 지표, 로트, 작업지시, 예방 정비 기한, 작업기록, 알람 횟수, 지금 설비 상태)을 묻는다 / "
             "mixed = 운영 기록과 문서 설명을 함께 묻는다 / "
             "none = 공장 업무와 관계없다 (급여·휴가·식당·날씨·교통·개인 연락처·물건값 같은 것) / "
             "action = 비서에게 무엇을 바꾸거나 하라고 시킨다 (승인·확정·보류 해제·알림 처리·설비 조작·설정 변경)\n"
             "- intents (kind가 ops·mixed일 때만): stops=멈춘·선 기록, production=생산 실적·개수, inventory=재고·소모품, "
             "tool_life=공구 수명·곧 바꿀 공구, kpi=OEE·가동률·성능·양품률·MTTR(평균 수리 시간)·MTBF, lots=로트, work_orders=정비 작업지시, "
             "pm_due=예방 정비 기한, work_records=작업기록·지난 조치, alarm_count=알람이 몇 번 났나, equipment_status=지금 설비 상태\n"
             "- equipment: SAW-01(절단), MIL-01(황삭), VF2-01(1호기), VF2-02(2호기), WSH-01(세척), CMM-01(측정). 말하지 않았으면 빈 목록\n"
             "- period: today=오늘, yesterday=어제·간밤, last_shift=지난 교대, recent_7=최근 일주일, recent_30=최근 한 달, none=말하지 않음. 날짜를 직접 쓰지 않는다\n"
             "- shift: D=주간·낮, N=야간·밤, none=말하지 않음\n"
             "- search_queries: kind가 doc·mixed면 사내 문서에서 찾기 좋은 말로 바꾼 검색어 1~3개 (각 40자 이하). "
             "현장 말·줄임말은 문서에 쓰일 낱말로 바꾼다. 질문에 없는 숫자를 넣지 않는다. 그 밖에는 빈 목록\n"
             "- '낱말 규칙의 분류'는 힌트다. 틀릴 수 있으니 질문 전체의 뜻으로 정한다.")
    shots = "\n".join(f"질문: {e['q']}\n분류: {json.dumps(e['out'], ensure_ascii=False)}" for e in examples)
    user = f"낱말 규칙의 분류: kind={hint['kind']}, intents={json.dumps(hint['intents'], ensure_ascii=False)}\n질문: {question}"
    return [{"role": "system", "content": COMMON + "\n" + rules + "\n\n예시:\n" + shots}, {"role": "user", "content": user}]


def select_strict(question: str, blocks: list[tuple[str, list[tuple[str, str]]]], feedback: str | None = None) -> list[dict]:
    """2차 문지기의 엄격한 줄 고르기. 낱말 문지기가 막은 질문이라 후보가 질문과 어긋날 수 있다.
    (사내 문서에 없는 질문 낱말을 "주의 낱말"로 알려 주던 줄은 2026-10-10 뺐다: 9B 모델이 "퍼센트"↔"%", "목장갑"↔"면장갑"처럼
    같은 뜻의 다른 표기도 없다고 보고 조정 세트 F의 바꿔 말한 문서 질문 4개를 모두 거부했다. 거르는 일은 따로 검증·코드 검사가 한다)"""
    msgs = select(question, blocks, feedback)
    extra = ("\n- 이 질문은 낱말 검색으로는 근거가 약했다. 질문이 묻는 바로 그것(값·사람·시기·방법)이 줄에 그대로 있을 때만 "
             "answerable=true. 비슷한 주제만 있고 묻는 것이 없으면 answerable=false.")
    msgs[0] = {**msgs[0], "content": msgs[0]["content"] + extra}
    return msgs


def verify(question: str, lines: list[str]) -> list[dict]:
    """따로 검증: 고른 줄만 보고 질문에 답할 수 있나 (판정만, 답을 쓰지 않는다)."""
    rules = ("아래 '줄'은 사내 문서에서 그대로 옮긴 글이다. 이 줄만 보고 질문에 답할 수 있는지 판정한다. 답을 쓰지 않는다.\n"
             "- 질문이 묻는 바로 그것(값·사람·시기·방법·가능 여부)이 줄에 그대로 있으면 answers=true.\n"
             "- 주제만 비슷하고 묻는 것이 없으면 answers=false, missing에 빠진 것을 짧게 쓴다.\n"
             "- 줄에 없는 지식으로 채우지 않는다.")
    body = "\n".join(f"- {t}" for t in lines)
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": f"질문: {question}\n\n줄:\n{body}"}]


def simplify(segments: list[str], kind: str, feedback: str | None = None) -> list[dict]:
    """이어 묻기 (2026-10-12): 앞 답의 글 조각을 현장 사람이 알아듣기 쉬운 말로 다시 쓴다. 조각마다 하나씩, 같은 순서.
    안전·절차 글은 프로그램이 처음부터 보내지 않는다 (answer._rewrite_blocked)."""
    how = ("조각마다 한 문장으로 짧게 줄인다" if kind == "short"
           else "조각마다 현장 작업자에게 말하듯 해요체(~해요, ~이에요)로 다시 쓴다. 문장 수·순서·내용은 그대로 두고 말투와 어려운 낱말만 바꾼다" if kind == "plain"
           else "조각마다 어려운 낱말을 쉬운 말로 풀어, 현장 작업자가 바로 알아듣게 다시 쓴다")
    rules = (f"아래 번호 붙인 '원문 조각'을 {how}. texts 칸에 같은 순서로 조각 수만큼 쓴다.\n"
             "- 원문에 없는 사실·원인·조언·허락·지시를 더하지 않는다. 원문의 사실·조건·대상을 빼지 않는다.\n"
             "- 숫자·단위·날짜·부품번호·제품 이름·영문 이름·기록 번호는 원문 그대로 쓴다(바꾸거나 빼지 않는다). 숫자는 아라비아 숫자.\n"
             "- 이상·이하·초과·미만·금지·않·못·불가·반드시·필수·먼저·전에·뒤에 같은 조건 말은 빼거나 바꾸지 않는다.\n"
             "- '[가상]', '(추정)', '잠정' 같은 꼬리표를 지우지 않는다.")
    if kind == "plain":   # 알람 카드·안전 설명의 해요체 다시 쓰기 (A2, 2026-10-18) — 명령형·허락·안심 말로 바뀌면 프로그램 검사(DENY)가 거부한다
        rules += ("\n- 조각 하나는 원문과 같은 문장 수로 쓴다. 조각을 합치거나 나누거나 빼거나 더하지 않는다.\n"
                  "- '~하세요'·'~십시오' 같은 명령형과 '~해도 돼요'·'괜찮아요'·'안전해요' 같은 허락·안심 말은 쓰지 않는다. 원문이 '~한다'면 '~해요'로 옮긴다.\n"
                  "- [DIAGNOSTICS]·[F2]·[RESET] 같은 대괄호 버튼 이름, 탭 이름, 부품·밸브 이름은 원문 그대로 쓴다.\n"
                  "- 원문에 있는 절 참조(§2.1, §2.5 점검 8, DOC-06 §6 …)는 지우거나 바꾸지 말고 그대로 옮긴다. 원문에 없는 절 번호나 문서 번호는 새로 쓰지 않는다.")
    body = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(segments))
    user = f"원문 조각:\n{body}"
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}. 이 점을 고쳐 다시 쓴다."
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": user}]


def faith(segments: list[str], rewrites: list[str]) -> list[dict]:
    """바꿔 쓴 글 검사 (이어 묻기): 원문 조각과 바꾼 글이 같은 뜻인가 (판정만)."""
    rules = ("아래 번호마다 '원문'과 '바꾼 글'을 비교한다. 바꾼 글이 원문에 없는 사실·조건·숫자·대상을 더하거나, "
             "원문의 사실·조건·대상을 빼거나 바꿨으면 same_meaning=false, problem에 짧게 쓴다. 표현만 쉬워졌으면 true.")
    body = "\n\n".join(f"{i + 1}. 원문: {a}\n   바꾼 글: {b}" for i, (a, b) in enumerate(zip(segments, rewrites)))
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": body}]


SHOTS_WRITE = (
    "\n\n좋은 답의 모양 예시 (모양만 따른다 — 예시의 낱말·사실은 쓰지 않는다):\n"
    "[예 1] 문서 줄: 1. {{1}}마다 윤활유 양을 본다. 2. 덮개는 잠금·표지를 건 뒤에만 연다.\n"
    "질문: 윤활유는 얼마나 자주 봐?\n"
    "answer: {{1}}마다 윤활유 양을 봐요. 덮개는 잠금·표지를 건 뒤에만 열어요.\n"
    "[예 2] 문서 줄: 1. 값은 {{1}} 이하로 맞춘다. 2. 기록은 작업기록서에 남긴다.\n"
    "질문: 값은 어느 정도로 맞춰?\n"
    "answer: 값은 {{1}} 이하로 맞춰요. 기록은 작업기록서에 남겨요.\n"
    "- 문서 줄에 잠금·표지·자격자 같은 안전 낱말이나 조건 말(이하·이상·반드시 …)이 있으면, 질문과 조금 떨어진 줄이어도 그 말을 답에 남긴다. "
    "줄의 문장을 그대로 베끼지 말고 자기 말로 풀어 쓴다.")


def write_answer(question: str, units: list[str], feedback: str | None = None, shots: bool = False,
                 titles: list[str] | None = None) -> list[dict]:
    """10차 DOC_WRITE (2026-10-13 사용자 결정): 찾은 문서 줄(자리표 품음)로 질문에 바로 답하는 쉬운 글을 새로 쓴다.
    shots (WRITE_SHOTS, 2026-10-14 비교 실험): 좋은 답 예시 2개 + 안전 낱말 남기기 한 줄. titles (WRITE_TITLES): 줄마다 절 제목(한글만) —
    줄의 뜻을 잡는 데만 쓰고 답에 옮기지 않는다. 둘 다 기본 꺼짐."""
    rules = ("아래 '문서 줄'은 사내 문서에서 찾은 글이다. 이 줄만 보고 질문에 바로 답하는 글을 answer 칸에 쓴다.\n"
             "- 신입사원도 알아듣는 쉬운 한국어로, 되도록 해요체(~해요, ~예요)로 1~3문장. 질문에 대한 답을 첫 문장에 쓴다.\n"
             "- {{1}}, {{2}} 같은 자리표는 숫자·이름이다. 필요한 자리표만 그대로 옮기고, 자리표를 바꾸거나 새로 만들지 않는다. "
             "자리표 밖에는 숫자·영문을 쓰지 않는다. 자리표 값은 이미 단위를 품고 있으니(예: 시각·%) 뒤에 '시'·'퍼센트'를 또 붙이지 않는다.\n"
             "- 표준어·쓰지 않는 말을 묻는 질문이면 '○○는 쓰지 않는 말이고, 문서에는 △△라고 써요'처럼 어느 쪽이 표준어인지 바르게 쓴다.\n"
             "- 문서 줄에 없는 사실·원인·조언·허락·지시를 더하지 않는다. 조건 말(이상·이하·초과·미만·금지·반드시·전에·뒤에 …)은 "
             "뜻을 바꾸지 않는다. '[가상]', '(추정)', '잠정' 같은 꼬리표가 있으면 지우지 않는다.\n"
             "- 칸 이름 꼴(예: '— 표준어:', '· 쓰지 않는 말:')은 쓰지 말고 문장으로 푼다.")
    if shots:
        rules += SHOTS_WRITE
    if titles and len(titles) == len(units):
        body = "\n".join(f"{i + 1}. {t}" + (f"  〈절: {ti}〉" if ti else "") for i, (t, ti) in enumerate(zip(units, titles)))
        rules += "\n- 줄 끝의 〈절: …〉은 그 줄이 있는 사내 문서 절의 이름이다. 줄의 뜻을 잡는 데만 쓰고 답에 옮겨 쓰지 않는다."
    else:
        body = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(units))
    user = f"질문: {question}\n\n문서 줄:\n{body}"
    if feedback:
        user += f"\n\n지난 글은 거부되었다: {feedback}. 이 점을 고쳐 다시 쓴다."
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": user}]


def answer_faith(lines: list[str], answer: str) -> list[dict]:
    """10차 DOC_WRITE: 새로 쓴 답이 문서 줄과 어긋나지 않는가 (판정만). 질문과 무관한 줄 내용을 뺀 것은 괜찮다."""
    rules = ("아래 '문서 줄'과 그 줄로 쓴 '답 글'을 비교한다. 답 글이 문서 줄에 없는 사실·조건·숫자·대상·원인·조언을 더했거나, "
             "문서 줄과 다르게 말했거나, 조건(이상·이하·금지·전에 …)의 뜻을 바꿨으면 faithful=false, problem에 짧게 쓴다. "
             "문서 줄의 내용 중 일부만 골라 쓴 것은 괜찮다(true).")
    body = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lines))
    return [{"role": "system", "content": COMMON + "\n" + rules},
            {"role": "user", "content": f"문서 줄:\n{body}\n\n답 글: {answer}"}]


def simplify_v2(units: list[str], terms: list[str], feedback: str | None = None) -> list[dict]:
    """이어 묻기 2판 (7차 FOLLOWUP_V2): 자리표를 품은 조각을 쉬운 말로 다시 쓰고, 풀이할 낱말을 고른다."""
    rules = ("아래 번호 붙인 '원문 조각'을 현장 작업자가 바로 알아듣는 쉬운 한국어로 다시 쓴다. texts 칸에 같은 순서로 조각 수만큼 쓴다.\n"
             "- {{1}}, {{2}} 같은 자리표는 숫자·이름이다. 자리표를 하나도 빼거나 바꾸거나 더하지 말고 그대로 옮긴다. "
             "자리표 밖에는 숫자·영문을 쓰지 않는다.\n"
             "- 어려운 한자말·줄임말·칸 이름 꼴은 쉬운 말로 풀어 짧은 문장으로 쓴다. 이미 쉬우면 그대로 둔다.\n"
             "- 원문에 없는 사실·원인·조언·허락·지시를 더하지 않는다. 원문의 사실·조건·대상을 빼지 않는다.\n"
             "- 이상·이하·초과·미만·금지·않·못·불가·반드시·필수·먼저·전에·뒤에 같은 조건 말은 빼거나 바꾸지 않는다. "
             "'[가상]', '(추정)', '잠정' 같은 꼬리표를 지우지 않는다.")
    if terms:
        rules += ("\n- 아래 '낱말 후보'(T1, T2 …) 가운데 현장 작업자가 모를 수 있는 낱말을 3개 이하로 골라 terms 칸에 번호를 넣는다. "
                  "모두 쉬우면 빈 목록.")
    body = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(units))
    user = f"원문 조각:\n{body}"
    if terms:
        user += "\n\n낱말 후보:\n" + "\n".join(f"T{i + 1}. {t}" for i, t in enumerate(terms))
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}. 이 점을 고쳐 다시 쓴다."
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": user}]


def safe_simplify_v15(units: list[str], feedback: str | None = None) -> list[dict]:
    """안전 영역 새로쓰기 (2026-10-14 사용자 결정 "대체 방식·엄격"): 점검 순서 조각을 1:1로 쉬운 말로 다시 쓴다.
    조각 수·순서·안전 낱말·조건 말·자리표를 그대로 지키게 하고, 어긋나면 프로그램이 새 글 전부를 버리고 원문만 보인다."""
    rules = ("아래 번호 붙인 '점검 순서 조각'은 사내 문서의 설비 점검·안전 단계다. 현장 작업자가 바로 알아듣는 쉬운 한국어로 조각마다 다시 쓴다. "
             "texts 칸에 같은 순서로 조각 수만큼 쓴다. 조각을 합치거나 나누거나 순서를 바꾸지 않는다.\n"
             "- {{1}}, {{2}} 같은 자리표는 숫자·단위·이름·버튼 이름이다. 자리표를 하나도 빼거나 바꾸거나 더하지 말고, "
             "조각마다 있는 자리표를 한 번씩 그대로 옮긴다. 자리표 밖에는 숫자·영문을 쓰지 않는다.\n"
             "- 조각 안의 모든 동작·대상·조건을 빠짐없이 쓴다. 원문에 없는 사실·원인·조언·허락·지시를 더하지 않는다.\n"
             "- 잠금·표지·고전압·차단·전기·저항·케이블·앰프 같은 안전 낱말은 원문에 있으면 그대로 쓰고, 원문에 없으면 쓰지 않는다. "
             "'자격자', 대괄호 [ ] 안의 글, '→', ①②③ 같은 순서 표시도 그대로 둔다.\n"
             "- 이상·이하·초과·미만·금지·않·못·불가·반드시·필수·먼저·전에·뒤에 같은 조건 말은 빼거나 바꾸지 않는다. "
             "'[가상]', '(추정)', '잠정' 같은 꼬리표를 지우지 않는다.\n"
             "- 원문을 그대로 베끼지 않는다. 어려운 한자말·줄임말·긴 문장은 쉬운 말과 짧은 문장으로 풀어 쓴다(한 조각 안에서 문장을 나누어도 된다). "
             "다만 뜻·순서·조건은 바꾸지 않는다. 원문에 없는 명령형('~하세요')으로 바꾸지 않는다.")
    body = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(units))
    user = f"점검 순서 조각:\n{body}"
    if feedback:
        user += f"\n\n지난 답은 프로그램 검사에서 거부됐다. 이유: {feedback}. 이 점을 고쳐 다시 쓴다."
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": user}]


def pick_units(units: list[str]) -> list[dict]:
    """이어 묻기 2판 "짧게": 남길 조각 번호만 고른다 (글은 프로그램이 원문 그대로 옮긴다)."""
    rules = ("아래 번호 붙인 조각(U1, U2 …)은 앞 답의 내용이다. 질문한 사람이 '짧게' 해 달라고 했다. "
             "앞 답의 핵심(질문에 바로 답하는 값·이름·대상)을 담은 조각만 골라 keep 칸에 번호를 넣는다. "
             "적어도 1개, 전체 조각 수보다 적게 고른다. 글은 쓰지 않는다.")
    body = "\n".join(f"U{i + 1}. {t}" for i, t in enumerate(units))
    return [{"role": "system", "content": COMMON + "\n" + rules}, {"role": "user", "content": body}]


# 섞인 질문 예시의 문서 쪽 질문 (route_examples.json은 step4와 같게 두고 여기서만 더한다)
DOC_QUESTION_EXAMPLES = {"VF2-01 OEE 얼마고 OEE는 어떻게 구해?": "OEE는 어떻게 구해?",
                         "예방 정비 기한 넘긴 거 있으면 실시 기록에는 뭘 적어?": "예방 정비 실시 기록에는 뭘 적어?"}


def route_v3(question: str, hint: dict, examples: list[dict]) -> list[dict]:
    """분류 v3 (SPLIT_Q): v2 + 섞인 질문의 문서 쪽 질문 글(doc_question)."""
    shots = [{"q": e["q"], "out": {**e["out"], "doc_question": DOC_QUESTION_EXAMPLES.get(e["q"], "")}} for e in examples]
    msgs = route_v2(question, hint, shots)
    extra = ("\n- doc_question: kind가 mixed면 질문 가운데 사내 문서(규칙·기준·담당·방법)로 답할 부분만 짧은 질문으로 쓴다(80자 이하). "
             "\"그거\" 같은 말은 가리키는 낱말로 바꾼다. 질문에 없는 숫자를 넣지 않는다. 그 밖에는 빈 글")
    msgs[0] = {**msgs[0], "content": msgs[0]["content"].replace("\n\n예시:", extra + "\n\n예시:", 1)}
    return msgs
